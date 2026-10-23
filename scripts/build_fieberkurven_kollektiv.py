#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

try:
    from import_common import connect_db
except ImportError:
    from scripts.import_common import connect_db


DEFAULT_DB = Path("outputs/pji_register_orthodok_pseudonymized.sqlite")
DEFAULT_EXPORT = Path("outputs/fieberkurven_kollektiv_hybase_pji_nah_pos.csv")
KOLLEKTIV_NAME = "HYBASE_PJI_NAH_POS"


PJI_MATERIAL_SQL = """
(
    m.Material LIKE '%Gewebe%'
    OR m.Material LIKE '%Gelenkpunktat%'
    OR m.Material LIKE '%Implantat%'
    OR m.Material LIKE '%Huefte%'
    OR m.Material LIKE '%Hüfte%'
    OR m.Material LIKE '%Knie%'
    OR m.Material LIKE '%Tiefe%'
    OR m.Material LIKE '%tiefe%'
)
"""

STERILE_MATERIAL_SQL = """
(
    m.Material LIKE '%Gewebe%'
    OR m.Material LIKE '%Gelenkpunktat%'
    OR m.Material LIKE '%Implantat%'
)
"""


EXPORT_COLUMNS = [
    "LaufNr",
    "Prioritaet",
    "PrioritaetText",
    "SAPScreenshotStatus",
    "FieberkurveStatus",
    "PatientHash",
    "PatientenzahlSAP",
    "GelenkFallID",
    "EpisodeID",
    "EingriffID",
    "Gelenk",
    "Seite",
    "OPDatum",
    "EpisodeBeginn",
    "SAPFallnummer",
    "MedizinischerFall",
    "ErstePositiveKultur",
    "LetztePositiveKultur",
    "PjiNahPosMikro",
    "SterilPosMikro",
    "LokalPosMikro",
    "ReopPosMikro",
    "PosMikroGesamt",
    "NegMikroGesamt",
    "ErregerListe",
    "MaterialListe",
    "FieberkurveIDs",
    "SAPDateinameVorschlag",
    "ManuellKommentar",
]


def table_exists(con, table_name: str) -> bool:
    row = con.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def short_list(raw: str | None, *, max_chars: int = 500) -> str | None:
    if not raw:
        return None
    parts = []
    seen = set()
    for part in raw.split(","):
        text = part.strip()
        if not text or text in seen:
            continue
        seen.add(text)
        parts.append(text)
    joined = "; ".join(parts)
    if len(joined) <= max_chars:
        return joined
    return joined[: max_chars - 3].rstrip() + "..."


def safe_filename_part(value: object, fallback: str) -> str:
    text = "" if value is None else str(value).strip()
    if not text:
        text = fallback
    text = re.sub(r"[^0-9A-Za-z._-]+", "_", text)
    return text.strip("._-") or fallback


def filename_suggestion(row) -> str:
    patient = safe_filename_part(row["PatientenzahlSAP"] or (row["PatientHash"] or "patient")[:10], "Patient")
    fall = safe_filename_part(row["SAPFallnummer"] or row["MedizinischerFall"] or row["GelenkFallID"], "Fall")
    joint = safe_filename_part(row["Gelenk"], "Gelenk")
    side = safe_filename_part(row["Seite"], "Seite")
    op_date = safe_filename_part(row["OPDatum"] or row["EpisodeBeginn"], "Datum")
    return (
        f"FK_Pat{patient}_Fall{fall}_GF{row['GelenkFallID']}_"
        f"Eingriff{row['EingriffID']}_{joint}_{side}_{op_date}.png"
    )


def candidate_rows(con) -> list[dict[str, object]]:
    sql = f"""
    WITH pji_micro AS (
        SELECT
            m.MikrobioID,
            m.EingriffID,
            a.EpisodeID,
            gf.GelenkFallID,
            gf.PatientID,
            m.Material,
            m.Erreger,
            m.Entnahmedatum,
            e.OPDatum,
            e.EingriffsartID
        FROM tblMikrobiologie m
        JOIN tblEingriff e ON e.EingriffID = m.EingriffID
        JOIN tblAufenthalt a ON a.AufenthaltID = e.AufenthaltID
        JOIN tblGelenkFall gf ON gf.GelenkFallID = a.GelenkFallID
        WHERE m.Quelle = 'HYBASE'
          AND m.Kommentar LIKE 'Status: POS%'
          AND {PJI_MATERIAL_SQL}
    ),
    episode_stats AS (
        SELECT
            EpisodeID,
            MIN(GelenkFallID) AS GelenkFallID,
            MIN(PatientID) AS PatientID,
            COUNT(DISTINCT MikrobioID) AS PjiNahPosMikro,
            SUM(CASE WHEN {STERILE_MATERIAL_SQL.replace("m.", "")} THEN 1 ELSE 0 END) AS SterilPosMikro,
            SUM(CASE WHEN NOT {STERILE_MATERIAL_SQL.replace("m.", "")} THEN 1 ELSE 0 END) AS LokalPosMikro,
            SUM(CASE WHEN EingriffsartID <> 1 THEN 1 ELSE 0 END) AS ReopPosMikro,
            MIN(Entnahmedatum) AS ErstePositiveKultur,
            MAX(Entnahmedatum) AS LetztePositiveKultur,
            GROUP_CONCAT(DISTINCT Erreger) AS ErregerListe,
            GROUP_CONCAT(DISTINCT Material) AS MaterialListe
        FROM pji_micro
        GROUP BY EpisodeID
    ),
    all_micro AS (
        SELECT
            a.EpisodeID,
            SUM(CASE WHEN m.Kommentar LIKE 'Status: POS%' THEN 1 ELSE 0 END) AS PosMikroGesamt,
            SUM(CASE WHEN m.Kommentar LIKE 'Status: NEG%' THEN 1 ELSE 0 END) AS NegMikroGesamt
        FROM tblMikrobiologie m
        JOIN tblEingriff e ON e.EingriffID = m.EingriffID
        JOIN tblAufenthalt a ON a.AufenthaltID = e.AufenthaltID
        WHERE m.Quelle = 'HYBASE'
        GROUP BY a.EpisodeID
    ),
    best_eingriff AS (
        SELECT EpisodeID, EingriffID
        FROM (
            SELECT
                EpisodeID,
                EingriffID,
                ROW_NUMBER() OVER (
                    PARTITION BY EpisodeID
                    ORDER BY
                        CASE WHEN EingriffsartID <> 1 THEN 0 ELSE 1 END,
                        OPDatum IS NULL,
                        OPDatum,
                        EingriffID
                ) AS rn
            FROM pji_micro
        )
        WHERE rn = 1
    ),
    fever AS (
        SELECT
            EpisodeID,
            GROUP_CONCAT(FieberkurveID) AS FieberkurveIDs,
            MAX(CASE WHEN ReviewStatus = 'bearbeitet' THEN 1 ELSE 0 END) AS HatReviewt,
            COUNT(*) AS Anzahl
        FROM tblFieberkurve
        WHERE EpisodeID IS NOT NULL
        GROUP BY EpisodeID
    )
    SELECT
        es.EpisodeID,
        be.EingriffID,
        es.PatientID,
        es.GelenkFallID,
        p.PatientHash,
        p.PatientenzahlSAP,
        gf.Gelenk,
        gf.Seite,
        ep.EpisodeBeginn,
        e.OPDatum,
        a.Fallnummer AS SAPFallnummer,
        a.MedizinischerFall,
        es.PjiNahPosMikro,
        es.SterilPosMikro,
        es.LokalPosMikro,
        es.ReopPosMikro,
        COALESCE(am.PosMikroGesamt, 0) AS PosMikroGesamt,
        COALESCE(am.NegMikroGesamt, 0) AS NegMikroGesamt,
        es.ErstePositiveKultur,
        es.LetztePositiveKultur,
        es.ErregerListe,
        es.MaterialListe,
        CASE
            WHEN f.HatReviewt = 1 THEN 'reviewt'
            WHEN f.Anzahl > 0 THEN 'vorhanden'
            ELSE 'benoetigt'
        END AS FieberkurveStatus,
        f.FieberkurveIDs
    FROM episode_stats es
    JOIN tblEpisode ep ON ep.EpisodeID = es.EpisodeID
    JOIN tblGelenkFall gf ON gf.GelenkFallID = es.GelenkFallID
    JOIN tblPatient p ON p.PatientID = es.PatientID
    JOIN best_eingriff be ON be.EpisodeID = es.EpisodeID
    JOIN tblEingriff e ON e.EingriffID = be.EingriffID
    JOIN tblAufenthalt a ON a.AufenthaltID = e.AufenthaltID
    LEFT JOIN all_micro am ON am.EpisodeID = es.EpisodeID
    LEFT JOIN fever f ON f.EpisodeID = es.EpisodeID
    ORDER BY
        CASE
            WHEN es.ReopPosMikro > 0 AND es.SterilPosMikro > 0 THEN 1
            WHEN es.ReopPosMikro > 0 THEN 2
            WHEN es.SterilPosMikro > 0 THEN 3
            ELSE 4
        END,
        e.OPDatum,
        es.EpisodeID
    """
    return [dict(row) for row in con.execute(sql)]


def priority(row: dict[str, object]) -> tuple[int, str]:
    reop = int(row["ReopPosMikro"] or 0)
    sterile = int(row["SterilPosMikro"] or 0)
    if reop > 0 and sterile > 0:
        return 1, "Reoperation plus sterile/PJI-nahe POS-Kultur"
    if reop > 0:
        return 2, "Reoperation plus lokale POS-Kultur"
    if sterile > 0:
        return 3, "Primaerfall plus sterile/PJI-nahe POS-Kultur"
    return 4, "Primaerfall plus lokale POS-Kultur"


def existing_statuses(con) -> dict[int, dict[str, object]]:
    if not table_exists(con, "tblFieberkurveKollektiv"):
        return {}
    rows = con.execute(
        """
        SELECT EpisodeID, SAPScreenshotStatus, ManuellKommentar
        FROM tblFieberkurveKollektiv
        WHERE KollektivName = ?
        """,
        (KOLLEKTIV_NAME,),
    ).fetchall()
    return {int(row["EpisodeID"]): dict(row) for row in rows}


def screenshot_status(row: dict[str, object], existing: dict[str, object] | None) -> str:
    fever_status = row["FieberkurveStatus"]
    old_status = (existing or {}).get("SAPScreenshotStatus") or "offen"
    if fever_status == "reviewt":
        return "reviewt"
    if fever_status == "vorhanden" and old_status in {"offen", "exportiert"}:
        return "importiert"
    return str(old_status)


def rebuild_table(con) -> int:
    statuses = existing_statuses(con)
    rows = candidate_rows(con)
    con.execute("DELETE FROM tblFieberkurveKollektiv WHERE KollektivName = ?", (KOLLEKTIV_NAME,))
    for row in rows:
        prio, prio_text = priority(row)
        existing = statuses.get(int(row["EpisodeID"]))
        con.execute(
            """
            INSERT INTO tblFieberkurveKollektiv (
                KollektivName, EpisodeID, EingriffID, PatientID, GelenkFallID,
                Prioritaet, PrioritaetText, PatientHash, PatientenzahlSAP,
                Gelenk, Seite, EpisodeBeginn, OPDatum, SAPFallnummer, MedizinischerFall,
                PjiNahPosMikro, SterilPosMikro, LokalPosMikro, ReopPosMikro,
                PosMikroGesamt, NegMikroGesamt, ErstePositiveKultur, LetztePositiveKultur,
                ErregerListe, MaterialListe, FieberkurveStatus, FieberkurveIDs,
                SAPScreenshotStatus, SAPDateinameVorschlag, ManuellKommentar,
                Aktiv, UpdatedAt
            )
            VALUES (
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?,
                1, CURRENT_TIMESTAMP
            )
            """,
            (
                KOLLEKTIV_NAME,
                row["EpisodeID"],
                row["EingriffID"],
                row["PatientID"],
                row["GelenkFallID"],
                prio,
                prio_text,
                row["PatientHash"],
                row["PatientenzahlSAP"],
                row["Gelenk"],
                row["Seite"],
                row["EpisodeBeginn"],
                row["OPDatum"],
                row["SAPFallnummer"],
                row["MedizinischerFall"],
                row["PjiNahPosMikro"],
                row["SterilPosMikro"],
                row["LokalPosMikro"],
                row["ReopPosMikro"],
                row["PosMikroGesamt"],
                row["NegMikroGesamt"],
                row["ErstePositiveKultur"],
                row["LetztePositiveKultur"],
                short_list(row["ErregerListe"]),
                short_list(row["MaterialListe"]),
                row["FieberkurveStatus"],
                row["FieberkurveIDs"],
                screenshot_status(row, existing),
                filename_suggestion(row),
                (existing or {}).get("ManuellKommentar"),
            ),
        )
    return len(rows)


def export_csv(con, output_path: Path) -> int:
    rows = con.execute(
        """
        SELECT
            ROW_NUMBER() OVER (ORDER BY Prioritaet, OPDatum IS NULL, OPDatum, EpisodeID) AS LaufNr,
            Prioritaet, PrioritaetText, SAPScreenshotStatus, FieberkurveStatus,
            PatientHash, PatientenzahlSAP, GelenkFallID, EpisodeID, EingriffID, Gelenk, Seite,
            OPDatum, EpisodeBeginn, SAPFallnummer, MedizinischerFall,
            ErstePositiveKultur, LetztePositiveKultur, PjiNahPosMikro, SterilPosMikro,
            LokalPosMikro, ReopPosMikro, PosMikroGesamt, NegMikroGesamt,
            ErregerListe, MaterialListe, FieberkurveIDs, SAPDateinameVorschlag,
            ManuellKommentar
        FROM tblFieberkurveKollektiv
        WHERE KollektivName = ? AND Aktiv = 1
        ORDER BY Prioritaet, OPDatum IS NULL, OPDatum, EpisodeID
        """,
        (KOLLEKTIV_NAME,),
    ).fetchall()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=EXPORT_COLUMNS, delimiter=";")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row[column] for column in EXPORT_COLUMNS})
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the fever-curve SAP worklist from HYBASE PJI-near positive episodes.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--export", type=Path, default=DEFAULT_EXPORT)
    parser.add_argument("--no-export", action="store_true")
    args = parser.parse_args()

    with connect_db(args.db) as con:
        count = rebuild_table(con)
        exported = 0
        if not args.no_export:
            exported = export_csv(con, args.export)
        con.commit()

    print(f"Built {count} fever-curve candidate episodes in {args.db}")
    if not args.no_export:
        print(f"Exported {exported} rows to {args.export}")


if __name__ == "__main__":
    main()
