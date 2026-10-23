#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openpyxl import load_workbook

try:
    from import_common import (
        connect_db,
        finish_import_batch,
        get_or_create_source,
        start_import_batch,
    )
    from import_orthodok import (
        as_iso_date,
        as_text,
        dict_from_row,
        normalized_headers,
        stable_hash,
    )
except ImportError:
    from scripts.import_common import (
        connect_db,
        finish_import_batch,
        get_or_create_source,
        start_import_batch,
    )
    from scripts.import_orthodok import (
        as_iso_date,
        as_text,
        dict_from_row,
        normalized_headers,
        stable_hash,
    )


DEFAULT_DB = Path("outputs/pji_register_orthodok_pseudonymized.sqlite")
DEFAULT_WORKBOOKS: tuple[tuple[Path, str], ...] = ()


@dataclass
class EnrichmentStats:
    workbook: str
    sheet: str
    rows_seen: int = 0
    patient_candidates: int = 0
    patient_matches: int = 0
    patient_updates: int = 0
    patient_updates_via_fall: int = 0
    patient_conflicts: int = 0
    fall_candidates: int = 0
    fall_matches: int = 0
    fall_updates: int = 0
    med_fall_updates: int = 0
    fall_conflicts: int = 0


def patient_hash_from_row(row: dict[str, Any], *, salt: str) -> str | None:
    patient_no = as_text(row.get("Patient"))
    fall_no = as_text(row.get("Fall"))
    birth = as_iso_date(row.get("Geburtsdatum"))
    last_name = as_text(row.get("Nachname"))
    first_name = as_text(row.get("Vorname"))
    if patient_no:
        patient_key = f"patient:{patient_no}"
    elif any([last_name, first_name, birth]):
        patient_key = f"name_birth:{last_name}|{first_name}|{birth}"
    elif fall_no:
        patient_key = f"fall:{fall_no}"
    else:
        return None
    return stable_hash(patient_key, salt=salt)


def first_text(row: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = as_text(row.get(key))
        if value:
            return value
    return None


def iter_rows(path: Path, sheet_name: str):
    wb = load_workbook(path, read_only=True, data_only=True)
    if sheet_name not in wb.sheetnames:
        raise ValueError(f"Sheet not found in {path.name}: {sheet_name}. Available: {', '.join(wb.sheetnames)}")
    ws = wb[sheet_name]
    iterator = ws.iter_rows(values_only=True)
    headers = normalized_headers(next(iterator))
    for row_number, values in enumerate(iterator, start=2):
        row = dict_from_row(headers, values)
        if any(value is not None and str(value).strip() != "" for value in row.values()):
            yield row_number, row


def enrich_patient(con: sqlite3.Connection, row: dict[str, Any], stats: EnrichmentStats, *, salt: str) -> None:
    patient_no = as_text(row.get("Patient"))
    patient_hash = patient_hash_from_row(row, salt=salt)
    if not patient_no or not patient_hash:
        return
    stats.patient_candidates += 1
    found = con.execute(
        "SELECT PatientID, PatientenzahlSAP FROM tblPatient WHERE PatientHash = ?",
        (patient_hash,),
    ).fetchone()
    if not found:
        return
    stats.patient_matches += 1
    current = as_text(found["PatientenzahlSAP"])
    if current and current != patient_no:
        stats.patient_conflicts += 1
        return
    if current == patient_no:
        return
    cur = con.execute(
        """
        UPDATE tblPatient
        SET PatientenzahlSAP = ?, UpdatedAt = CURRENT_TIMESTAMP
        WHERE PatientID = ? AND (PatientenzahlSAP IS NULL OR PatientenzahlSAP = '')
        """,
        (patient_no, found["PatientID"]),
    )
    stats.patient_updates += cur.rowcount


def enrich_fall(con: sqlite3.Connection, row: dict[str, Any], stats: EnrichmentStats, *, salt: str) -> None:
    fall_no = first_text(row, "Fall", "Med. Fallnr.", "Medizinischer Fall")
    if not fall_no:
        return
    stats.fall_candidates += 1
    fall_hash = stable_hash("fall", fall_no, salt=salt)
    med_fall = first_text(row, "Medizinischer Fall", "Med. Fallnr.", "ISH: Mediz. Fall")
    stays = con.execute(
        """
        SELECT AufenthaltID, Fallnummer, MedizinischerFall
        FROM tblAufenthalt
        WHERE FallHash = ?
        """,
        (fall_hash,),
    ).fetchall()
    if not stays:
        return
    stats.fall_matches += len(stays)
    patient_no = as_text(row.get("Patient"))
    for stay in stays:
        current_fall = as_text(stay["Fallnummer"])
        current_med = as_text(stay["MedizinischerFall"])
        if current_fall and current_fall != fall_no:
            stats.fall_conflicts += 1
            continue
        if not current_fall:
            cur = con.execute(
                """
                UPDATE tblAufenthalt
                SET Fallnummer = ?, UpdatedAt = CURRENT_TIMESTAMP
                WHERE AufenthaltID = ? AND (Fallnummer IS NULL OR Fallnummer = '')
                """,
                (fall_no, stay["AufenthaltID"]),
            )
            stats.fall_updates += cur.rowcount
        if med_fall and not current_med:
            cur = con.execute(
                """
                UPDATE tblAufenthalt
                SET MedizinischerFall = ?, UpdatedAt = CURRENT_TIMESTAMP
                WHERE AufenthaltID = ? AND (MedizinischerFall IS NULL OR MedizinischerFall = '')
                """,
                (med_fall, stay["AufenthaltID"]),
            )
            stats.med_fall_updates += cur.rowcount
        if patient_no:
            patient = con.execute(
                """
                SELECT p.PatientID, p.PatientenzahlSAP
                FROM tblAufenthalt a
                JOIN tblGelenkFall gf ON gf.GelenkFallID = a.GelenkFallID
                JOIN tblPatient p ON p.PatientID = gf.PatientID
                WHERE a.AufenthaltID = ?
                """,
                (stay["AufenthaltID"],),
            ).fetchone()
            if not patient:
                continue
            current_patient = as_text(patient["PatientenzahlSAP"])
            if current_patient and current_patient != patient_no:
                stats.patient_conflicts += 1
                continue
            if not current_patient:
                cur = con.execute(
                    """
                    UPDATE tblPatient
                    SET PatientenzahlSAP = ?, UpdatedAt = CURRENT_TIMESTAMP
                    WHERE PatientID = ? AND (PatientenzahlSAP IS NULL OR PatientenzahlSAP = '')
                    """,
                    (patient_no, patient["PatientID"]),
                )
                stats.patient_updates += cur.rowcount
                stats.patient_updates_via_fall += cur.rowcount


def enrich_workbook(
    con: sqlite3.Connection,
    path: Path,
    sheet_name: str,
    *,
    salt: str,
) -> EnrichmentStats:
    stats = EnrichmentStats(workbook=path.name, sheet=sheet_name)
    source_id = get_or_create_source(con, path, "Orthodok")
    batch_id = start_import_batch(con, source_id, "orthodok_identifier_enrichment")
    try:
        for _row_number, row in iter_rows(path, sheet_name):
            stats.rows_seen += 1
            enrich_patient(con, row, stats, salt=salt)
            enrich_fall(con, row, stats, salt=salt)
        note = (
            f"patient_updates={stats.patient_updates}; fall_updates={stats.fall_updates}; "
            f"patient_updates_via_fall={stats.patient_updates_via_fall}; "
            f"med_fall_updates={stats.med_fall_updates}; patient_conflicts={stats.patient_conflicts}; "
            f"fall_conflicts={stats.fall_conflicts}"
        )
        finish_import_batch(con, batch_id, stats.rows_seen, "finished", note)
        return stats
    except Exception:
        finish_import_batch(con, batch_id, stats.rows_seen, "failed")
        raise


def backup_db(db_path: Path) -> Path:
    stamp = __import__("datetime").datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = db_path.with_name(f"{db_path.stem}.before_identifier_enrichment_{stamp}{db_path.suffix}")
    shutil.copy2(db_path, backup_path)
    return backup_path


def parse_workbook_arg(raw: str) -> tuple[Path, str]:
    if "::" not in raw:
        raise argparse.ArgumentTypeError("Workbook must be passed as /path/file.xlsx::SheetName")
    path_text, sheet_name = raw.split("::", 1)
    return Path(path_text), sheet_name


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Enrich the existing pseudonymized OrthoDok import with SAP patient and fall numbers."
    )
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument(
        "--workbook",
        action="append",
        type=parse_workbook_arg,
        help="Optional workbook specification: /path/file.xlsx::SheetName. Defaults to current hip and knee OrthoDok files.",
    )
    parser.add_argument("--no-backup", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--salt",
        default=os.environ.get("PJI_HASH_SALT", "pji-register-local-v1"),
        help="Salt used by the original OrthoDok import.",
    )
    args = parser.parse_args()

    if not args.db.exists():
        raise FileNotFoundError(args.db)
    workbook_specs = tuple(args.workbook or DEFAULT_WORKBOOKS)
    for path, sheet_name in workbook_specs:
        if not path.exists():
            raise FileNotFoundError(path)
        if not sheet_name:
            raise ValueError(f"Missing sheet name for {path}")

    backup_path = None
    if not args.no_backup and not args.dry_run:
        backup_path = backup_db(args.db)

    with connect_db(args.db) as con:
        stats = [enrich_workbook(con, path, sheet_name, salt=args.salt) for path, sheet_name in workbook_specs]
        if args.dry_run:
            con.rollback()
        else:
            con.commit()

    if backup_path:
        print(f"Backup: {backup_path}")
    if args.dry_run:
        print("Dry run only: no changes committed.")
    for item in stats:
        print(
            f"{item.workbook} [{item.sheet}]: rows={item.rows_seen}; "
            f"patient_matches={item.patient_matches}; patient_updates={item.patient_updates}; "
            f"patient_updates_via_fall={item.patient_updates_via_fall}; "
            f"fall_matches={item.fall_matches}; fall_updates={item.fall_updates}; "
            f"med_fall_updates={item.med_fall_updates}; "
            f"patient_conflicts={item.patient_conflicts}; fall_conflicts={item.fall_conflicts}"
        )


if __name__ == "__main__":
    main()
