#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sqlite3
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

try:
    from import_common import connect_db, intervention_link_decision, stable_hash
except ImportError:
    from scripts.import_common import connect_db, intervention_link_decision, stable_hash


@dataclass
class Finding:
    episode_id: int
    object_type: str
    object_id: int
    current_intervention_id: int | None
    proposed_intervention_id: int | None
    reason: str
    score: float
    distance_days: int | None
    evidence: dict[str, object]


def ensure_review_table(con: sqlite3.Connection) -> None:
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS tblVerknuepfungsVorschlag (
            VorschlagID INTEGER PRIMARY KEY,
            EpisodeID INTEGER NOT NULL,
            ObjektTyp TEXT NOT NULL,
            ObjektID INTEGER NOT NULL,
            IstEingriffID INTEGER,
            VorschlagEingriffID INTEGER,
            Grund TEXT NOT NULL,
            Score REAL NOT NULL DEFAULT 0,
            AbstandTage INTEGER,
            BelegJSON TEXT,
            ReviewStatus TEXT NOT NULL DEFAULT 'offen',
            CreatedAt TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UpdatedAt TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (ObjektTyp, ObjektID, Grund),
            FOREIGN KEY (EpisodeID) REFERENCES tblEpisode(EpisodeID),
            FOREIGN KEY (IstEingriffID) REFERENCES tblEingriff(EingriffID),
            FOREIGN KEY (VorschlagEingriffID) REFERENCES tblEingriff(EingriffID)
        )
        """
    )
    con.execute(
        "CREATE INDEX IF NOT EXISTS idxVerknuepfungsReviewEpisode ON tblVerknuepfungsVorschlag (EpisodeID, ReviewStatus, ObjektTyp)"
    )
    con.execute(
        "CREATE INDEX IF NOT EXISTS idxRawLabPatientToken ON tblRawLabImport(json_extract(RawJSON, '$.Patient'))"
    )
    # The case audit starts with a pseudonymised raw-import patient token and
    # then resolves its already imported laboratory values.  Without this
    # bridge index SQLite scans the complete pool of unassigned lab rows on
    # every click of "Automatisch prüfen".
    con.execute(
        "CREATE INDEX IF NOT EXISTS idxLaborWertRawImport ON tblLaborWert(RawImportID)"
    )
    proposal_columns = {row[1] for row in con.execute("PRAGMA table_info(tblVerknuepfungsVorschlag)")}
    for name, column_type in [
        ("ReviewKommentar", "TEXT"),
        ("ReviewedAt", "TEXT"),
    ]:
        if name not in proposal_columns:
            con.execute(f"ALTER TABLE tblVerknuepfungsVorschlag ADD COLUMN {name} {column_type}")
    micro_columns = {row[1] for row in con.execute("PRAGMA table_info(tblMikrobiologie)")}
    for name, column_type in [
        ("Zuordnungsstatus", "TEXT NOT NULL DEFAULT 'automatisch'"),
        ("ZuordnungsReviewKommentar", "TEXT"),
    ]:
        if name not in micro_columns:
            con.execute(f"ALTER TABLE tblMikrobiologie ADD COLUMN {name} {column_type}")


def normalize_document_text(value: object) -> str:
    text = str(value or "").lower()
    text = re.sub(r"image_s\d+[-_][\w.-]+", "", text)
    text = re.sub(r"\bseite\s*\d+\b", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def microbiology_findings(con: sqlite3.Connection, episode_id: int | None) -> list[Finding]:
    params: list[object] = []
    where = ""
    if episode_id is not None:
        where = "AND a.EpisodeID = ?"
        params.append(episode_id)
    rows = con.execute(
        f"""
        SELECT m.MikrobioID, m.EingriffID, m.Entnahmedatum, m.Material, m.Erreger,
               m.Quelle, a.EpisodeID, e.OPDatum AS IstOPDatum
        FROM tblMikrobiologie m
        JOIN tblEingriff e ON e.EingriffID = m.EingriffID
        JOIN tblAufenthalt a ON a.AufenthaltID = e.AufenthaltID
        WHERE 1=1 {where}
        ORDER BY a.EpisodeID, m.MikrobioID
        """,
        params,
    ).fetchall()
    findings: list[Finding] = []
    for row in rows:
        decision = intervention_link_decision(
            con,
            int(row["EpisodeID"]),
            row["Entnahmedatum"],
            max_days=30,
        )
        proposed = decision["EingriffID"]
        current = int(row["EingriffID"])
        if proposed == current:
            continue
        reason = str(decision["Grund"])
        findings.append(
            Finding(
                episode_id=int(row["EpisodeID"]),
                object_type="mikrobiologie",
                object_id=int(row["MikrobioID"]),
                current_intervention_id=current,
                proposed_intervention_id=int(proposed) if proposed else None,
                reason=reason,
                score=float(decision["Score"]),
                distance_days=int(decision["AbstandTage"]) if decision["AbstandTage"] is not None else None,
                evidence={
                    "Entnahmedatum": row["Entnahmedatum"],
                    "IstOPDatum": row["IstOPDatum"],
                    "Material": row["Material"],
                    "Erreger": row["Erreger"],
                    "Quelle": row["Quelle"],
                },
            )
        )
    return findings


def ambulance_duplicate_findings(con: sqlite3.Connection, episode_id: int | None) -> list[Finding]:
    params: list[object] = []
    where = "COALESCE(ReviewStatus, 'offen') <> 'geloescht'"
    if episode_id is not None:
        where += " AND EpisodeID = ?"
        params.append(episode_id)
    rows = con.execute(
        f"""
        SELECT AmbulanzKarteiID, EpisodeID, DokumentTyp, DokumentDatum, KontaktDatum,
               BerichtText, OriginalPath
        FROM tblAmbulanzKarteiDokument
        WHERE {where}
        ORDER BY EpisodeID, AmbulanzKarteiID
        """,
        params,
    ).fetchall()
    by_episode: dict[int, list[sqlite3.Row]] = {}
    for row in rows:
        by_episode.setdefault(int(row["EpisodeID"]), []).append(row)
    findings: list[Finding] = []
    for current_episode, documents in by_episode.items():
        for index, left in enumerate(documents):
            left_text = normalize_document_text(left["BerichtText"])
            if len(left_text) < 100:
                continue
            for right in documents[index + 1 :]:
                right_text = normalize_document_text(right["BerichtText"])
                if not right_text:
                    continue
                length_ratio = min(len(left_text), len(right_text)) / max(len(left_text), len(right_text))
                if length_ratio < 0.97:
                    continue
                similarity = SequenceMatcher(None, left_text, right_text, autojunk=False).ratio()
                if similarity < 0.995:
                    continue
                findings.append(
                    Finding(
                        episode_id=current_episode,
                        object_type="ambulanz_dublette",
                        object_id=int(right["AmbulanzKarteiID"]),
                        current_intervention_id=None,
                        proposed_intervention_id=None,
                        reason="nahezu_identisches_dokument",
                        score=round(similarity, 4),
                        distance_days=None,
                        evidence={
                            "OriginalDokumentID": int(left["AmbulanzKarteiID"]),
                            "DubletteDokumentID": int(right["AmbulanzKarteiID"]),
                            "Aehnlichkeit": round(similarity, 4),
                            "OriginalPath": right["OriginalPath"],
                        },
                    )
                )
    return findings


def _raw_patient_token(raw_json: object) -> str | None:
    try:
        payload = json.loads(str(raw_json or "{}"))
    except (json.JSONDecodeError, TypeError):
        return None
    token = str(payload.get("Patient") or "").strip()
    return token if token.startswith("[masked:") else None


def laboratory_findings(con: sqlite3.Connection, episode_id: int | None) -> list[Finding]:
    """Find imported laboratory rows that belong to a known patient but lack an episode.

    The raw import stores only a pseudonymised patient token.  A token is usable
    when another laboratory row with the same token is already linked to an
    episode.  Date proximity then selects an intervention conservatively.
    """
    # Global runs report the backlog separately.  Creating patient-level
    # proposals is intentionally done from an opened case so joint and date
    # context remain visible to the reviewer.
    if episode_id is None:
        return []
    patient_rows = con.execute(
        """
        SELECT DISTINCT p.PatientenzahlSAP
        FROM tblEpisode ep
        JOIN tblGelenkFall gf ON gf.GelenkFallID = ep.GelenkFallID
        JOIN tblPatient p ON p.PatientID = gf.PatientID
        WHERE ep.EpisodeID = ? AND p.PatientenzahlSAP IS NOT NULL
        """,
        (episode_id,),
    ).fetchall()
    relevant_tokens = {
        f"[masked:{stable_hash('Patient', str(row['PatientenzahlSAP']), salt='pji-register-local-v1')}]"
        for row in patient_rows
    }
    if not relevant_tokens:
        return []
    placeholders = ",".join("?" for _ in relevant_tokens)
    candidates = con.execute(
        f"""
        SELECT lw.LaborWertID, lw.Parameter, lw.Wert, lw.WertText, lw.Einheit,
               lw.Datum, lw.Quelle, lw.SourceFileID, r.RawJSON
        FROM tblRawLabImport r INDEXED BY idxRawLabPatientToken
        JOIN tblLaborWert lw INDEXED BY idxLaborWertRawImport
          ON lw.RawImportID = r.RawLabImportID
        WHERE json_extract(r.RawJSON, '$.Patient') IN ({placeholders})
          AND (lw.EpisodeID IS NULL OR (lw.EpisodeID = ? AND lw.EingriffID IS NULL))
        ORDER BY lw.LaborWertID
        """,
        (*tuple(sorted(relevant_tokens)), episode_id),
    ).fetchall()
    findings: list[Finding] = []
    for row in candidates:
        token = _raw_patient_token(row["RawJSON"])
        if token not in relevant_tokens:
            continue
        possible_episodes = {episode_id}
        decisions: list[tuple[int, dict[str, object]]] = []
        for possible_episode in possible_episodes:
            decision = intervention_link_decision(
                con, possible_episode, row["Datum"], max_days=45
            )
            if decision["EingriffID"] is not None:
                decisions.append((possible_episode, decision))
        decisions.sort(key=lambda item: (int(item[1]["AbstandTage"]), -float(item[1]["Score"])))
        if not decisions:
            continue
        if len(decisions) > 1 and decisions[0][1]["AbstandTage"] == decisions[1][1]["AbstandTage"]:
            continue
        target_episode, decision = decisions[0]
        findings.append(
            Finding(
                episode_id=target_episode,
                object_type="labor",
                object_id=int(row["LaborWertID"]),
                current_intervention_id=None,
                proposed_intervention_id=int(decision["EingriffID"]),
                reason="gleicher_patient_token_und_zeitlich_nah",
                score=float(decision["Score"]),
                distance_days=int(decision["AbstandTage"]),
                evidence={
                    "Datum": row["Datum"],
                    "Parameter": row["Parameter"],
                    "Wert": row["Wert"],
                    "WertText": row["WertText"],
                    "Einheit": row["Einheit"],
                    "Quelle": row["Quelle"],
                    "SourceFileID": row["SourceFileID"],
                },
            )
        )
    return findings


def persist_findings(con: sqlite3.Connection, findings: list[Finding]) -> int:
    changed = 0
    for finding in findings:
        before = con.total_changes
        con.execute(
            """
            INSERT INTO tblVerknuepfungsVorschlag (
                EpisodeID, ObjektTyp, ObjektID, IstEingriffID, VorschlagEingriffID,
                Grund, Score, AbstandTage, BelegJSON
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (ObjektTyp, ObjektID, Grund) DO UPDATE SET
                IstEingriffID = excluded.IstEingriffID,
                VorschlagEingriffID = excluded.VorschlagEingriffID,
                Score = excluded.Score,
                AbstandTage = excluded.AbstandTage,
                BelegJSON = excluded.BelegJSON,
                UpdatedAt = CURRENT_TIMESTAMP
            WHERE tblVerknuepfungsVorschlag.ReviewStatus = 'offen'
            """,
            (
                finding.episode_id,
                finding.object_type,
                finding.object_id,
                finding.current_intervention_id,
                finding.proposed_intervention_id,
                finding.reason,
                finding.score,
                finding.distance_days,
                json.dumps(finding.evidence, ensure_ascii=False),
            ),
        )
        changed += con.total_changes - before
    return changed


def audit(con: sqlite3.Connection, episode_id: int | None = None) -> list[Finding]:
    return (
        microbiology_findings(con, episode_id)
        + ambulance_duplicate_findings(con, episode_id)
        + laboratory_findings(con, episode_id)
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prüft medizinische Verknüpfungen konservativ und erzeugt nachvollziehbare Bereinigungsvorschläge."
    )
    parser.add_argument("--db", type=Path, default=Path("outputs/pji_register_orthodok_pseudonymized.sqlite"))
    parser.add_argument("--episode-id", type=int)
    parser.add_argument(
        "--save-proposals",
        action="store_true",
        help="Speichert nur prüfbare Vorschläge; ändert keine klinische Zuordnung.",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    with connect_db(args.db) as con:
        ensure_review_table(con)
        findings = audit(con, args.episode_id)
        if args.save_proposals:
            changed = persist_findings(con, findings)
            con.commit()
        else:
            changed = 0
            con.rollback()

    payload = [finding.__dict__ for finding in findings]
    if args.json:
        print(json.dumps({"findings": payload, "saved": changed}, ensure_ascii=False, indent=2))
    else:
        print(f"Gefundene Verknüpfungsprobleme: {len(findings)}")
        print(f"Gespeicherte/aktualisierte Vorschläge: {changed}")
        for finding in findings:
            target = finding.proposed_intervention_id or "ohne Eingriff"
            print(
                f"Episode {finding.episode_id}: {finding.object_type} #{finding.object_id} "
                f"{finding.current_intervention_id or '-'} -> {target} "
                f"({finding.reason}, Score {finding.score:.2f})"
            )


if __name__ == "__main__":
    main()
