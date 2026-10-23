#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from pypdf import PdfReader

try:
    from import_common import (
        as_float,
        as_iso_date,
        connect_db,
        finish_import_batch,
        get_or_create_source,
        nearest_intervention_for_episode,
        resolve_episode_context,
        start_import_batch,
    )
except ImportError:
    from scripts.import_common import (
        as_float,
        as_iso_date,
        connect_db,
        finish_import_batch,
        get_or_create_source,
        nearest_intervention_for_episode,
        resolve_episode_context,
        start_import_batch,
    )


def pdf_files(path: Path) -> list[Path]:
    if path.is_dir():
        return sorted(path.glob("*.pdf"))
    if path.suffix.lower() != ".pdf":
        raise ValueError(f"Histology import expects PDF files: {path}")
    return [path]


def extract_pdf_text(path: Path) -> str:
    reader = PdfReader(str(path))
    chunks: list[str] = []
    for page in reader.pages:
        chunks.append(page.extract_text() or "")
    return "\n".join(chunks).strip()


def first_number(pattern: str, text: str) -> float | None:
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    return as_float(match.group(1))


def extract_histology_fields(text: str) -> dict[str, object]:
    krenn = first_number(r"krenn(?:\s|-)*score[^0-9]{0,20}(\d+(?:[,.]\d+)?)", text)
    pmn = first_number(r"(?:pmn|neutrophile)[^0-9]{0,30}(\d+(?:[,.]\d+)?)", text)
    akut = 1 if re.search(r"\bakut(?:e|er|es|en)?\b", text, re.IGNORECASE) else None
    chronisch = 1 if re.search(r"\bchronisch(?:e|er|es|en)?\b", text, re.IGNORECASE) else None
    return {
        "KrennScore": krenn,
        "PMN": pmn,
        "Akut": akut,
        "Chronisch": chronisch,
    }


def import_histology(args: argparse.Namespace) -> int:
    files = pdf_files(args.path)
    imported = 0
    with connect_db(args.db) as con:
        for pdf in files:
            source_id = get_or_create_source(con, pdf, "Histologie")
            batch_id = start_import_batch(con, source_id, "histologie_pdf")
            try:
                text = extract_pdf_text(pdf)
                extracted = extract_histology_fields(text)
                document_date = args.document_date
                if not document_date:
                    date_match = re.search(r"(\d{1,2}\.\d{1,2}\.\d{2,4})", text)
                    document_date = as_iso_date(date_match.group(1)) if date_match else None

                context = resolve_episode_context(
                    con,
                    episode_id=args.episode_id,
                    eingriff_id=args.eingriff_id,
                    fallnummer=args.fallnummer,
                    patient_no=args.patient_no,
                    salt=args.salt,
                )
                episode_id = context.get("EpisodeID")
                eingriff_id = context.get("EingriffID") or args.eingriff_id
                if not eingriff_id and episode_id:
                    eingriff_id = nearest_intervention_for_episode(con, episode_id, document_date)

                cur = con.execute(
                    """
                    INSERT INTO tblHistologieDokument (
                        EpisodeID, AufenthaltID, EingriffID, SourceFileID,
                        OriginalPath, DokumentDatum, BefundText, ExtractedJSON,
                        ReviewStatus, Kommentar
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'offen', ?)
                    """,
                    (
                        episode_id,
                        context.get("AufenthaltID"),
                        eingriff_id,
                        source_id,
                        str(pdf),
                        document_date,
                        text,
                        json.dumps(extracted, ensure_ascii=False),
                        "Automatisch extrahiert; fachlich pruefen.",
                    ),
                )
                if eingriff_id and any(extracted.get(key) is not None for key in ("KrennScore", "PMN", "Akut", "Chronisch")):
                    con.execute(
                        """
                        INSERT INTO tblHistologie (
                            EingriffID, KrennScore, PMN, Akut, Chronisch, Kommentar, Quelle
                        )
                        VALUES (?, ?, ?, ?, ?, ?, 'HistologiePDF')
                        """,
                        (
                            eingriff_id,
                            extracted.get("KrennScore"),
                            extracted.get("PMN"),
                            extracted.get("Akut"),
                            extracted.get("Chronisch"),
                            f"Aus HistologieDokumentID {cur.lastrowid}; Review erforderlich.",
                        ),
                    )
                finish_import_batch(con, batch_id, 1)
                imported += 1
            except Exception as exc:
                finish_import_batch(con, batch_id, 0, status="failed", note=str(exc))
                con.commit()
                raise
        con.commit()
    return imported


def main() -> None:
    parser = argparse.ArgumentParser(description="Import histology PDFs as reviewable documents and extract Krenn/PMN hints.")
    parser.add_argument("path", type=Path, help="PDF file or folder containing PDFs")
    parser.add_argument("--db", default=Path("outputs/pji_register_orthodok_pseudonymized.sqlite"), type=Path)
    parser.add_argument("--episode-id", type=int)
    parser.add_argument("--eingriff-id", type=int)
    parser.add_argument("--fallnummer")
    parser.add_argument("--patient-no")
    parser.add_argument("--document-date")
    parser.add_argument("--salt", default="pji-register-local-v1")
    args = parser.parse_args()
    count = import_histology(args)
    print(f"Imported {count} histology PDF document(s) into {args.db}")


if __name__ == "__main__":
    main()
