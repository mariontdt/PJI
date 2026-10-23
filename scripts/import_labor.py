#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path

try:
    from import_common import (
        as_float,
        as_iso_date,
        as_text,
        connect_db,
        finish_import_batch,
        get_or_create_source,
        mask_identifier_row,
        read_table,
        resolve_episode_context,
        row_to_json,
        start_import_batch,
    )
except ImportError:
    from scripts.import_common import (
        as_float,
        as_iso_date,
        as_text,
        connect_db,
        finish_import_batch,
        get_or_create_source,
        mask_identifier_row,
        read_table,
        resolve_episode_context,
        row_to_json,
        start_import_batch,
    )


def value(row: dict[str, object], column: str | None) -> object | None:
    if not column:
        return None
    return row.get(column)


def optional_int(raw: object | None) -> int | None:
    number = as_float(raw)
    return int(number) if number is not None else None


def parse_parameter_map(items: list[str] | None) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for item in items or []:
        if "=" not in item:
            raise ValueError(f"Invalid parameter map item {item!r}; expected OLD=NEW")
        old, new = item.split("=", 1)
        old = old.strip()
        new = new.strip()
        if not old or not new:
            raise ValueError(f"Invalid parameter map item {item!r}; expected OLD=NEW")
        mapping[old] = new
    return mapping


def mapped_parameter(raw_parameter: str | None, mapping: dict[str, str]) -> str | None:
    if not raw_parameter:
        return None
    return mapping.get(raw_parameter, raw_parameter)


def labor_key(
    *,
    context: dict[str, object],
    parameter: str,
    numeric_value: float | None,
    text_value: str | None,
    unit: str | None,
    lab_date: str | None,
    lab_time: str | None,
    comment: str | None,
    ignore_comment: bool = False,
) -> tuple[object, ...]:
    numeric_key = None if numeric_value is None else round(numeric_value, 7)
    return (
        parameter,
        context.get("FallHash") or "",
        context.get("PatientHash") or "",
        lab_date or "",
        lab_time or "",
        text_value or "",
        unit or "",
        "" if ignore_comment else comment or "",
        numeric_key,
    )


def existing_labor_keys(
    con,
    parameters: set[str],
    *,
    ignore_comment: bool = False,
) -> dict[tuple[object, ...], int]:
    if not parameters:
        return {}
    placeholders = ",".join("?" for _ in parameters)
    rows = con.execute(
        f"""
        SELECT
            LaborWertID, Parameter, FallHash, PatientHash, Datum, AbnahmeZeit,
            WertText, Einheit, Kommentar, Wert
        FROM tblLaborWert
        WHERE Parameter IN ({placeholders})
        """,
        tuple(sorted(parameters)),
    ).fetchall()
    keys: dict[tuple[object, ...], int] = {}
    for row in rows:
        key = (
            row["Parameter"],
            row["FallHash"] or "",
            row["PatientHash"] or "",
            row["Datum"] or "",
            row["AbnahmeZeit"] or "",
            row["WertText"] or "",
            row["Einheit"] or "",
            "" if ignore_comment else row["Kommentar"] or "",
            None if row["Wert"] is None else round(float(row["Wert"]), 7),
        )
        keys.setdefault(key, int(row["LaborWertID"]))
    return keys


def import_labor(args: argparse.Namespace) -> tuple[int, int, int]:
    sheet, rows = read_table(args.file, args.sheet)
    if args.limit:
        rows = rows[: args.limit]
    parameter_map = parse_parameter_map(args.parameter_map)
    parameters = {
        mapped_parameter(
            as_text(value(row, args.parameter_col)) if args.parameter_col else args.parameter,
            parameter_map,
        )
        for row in rows
    }
    parameters = {parameter for parameter in parameters if parameter}

    with connect_db(args.db) as con:
        source_id = get_or_create_source(con, args.file, "Labor")
        batch_label = args.parameter or args.parameter_col or "mixed"
        batch_id = start_import_batch(con, source_id, f"labor_{batch_label}")
        known_keys = (
            existing_labor_keys(con, parameters, ignore_comment=args.skip_existing_ignore_comment)
            if args.skip_existing
            else {}
        )
        context_cache: dict[tuple[object, ...], dict[str, object]] = {}
        raw_count = 0
        imported = 0
        skipped_existing = 0
        try:
            for row_number, row in enumerate(rows, start=2):
                row_parameter = mapped_parameter(
                    as_text(value(row, args.parameter_col)) if args.parameter_col else args.parameter,
                    parameter_map,
                )
                if not row_parameter:
                    continue
                raw_id = con.execute(
                    """
                    INSERT INTO tblRawLabImport (
                        ImportBatchID, SheetName, RowNumber, Parameter, RawJSON
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        batch_id,
                        sheet,
                        row_number,
                        row_parameter,
                        row_to_json(
                            mask_identifier_row(
                                row,
                                include_identifiers=args.include_identifiers,
                                salt=args.salt,
                            )
                        ),
                    ),
                ).lastrowid
                raw_count += 1

                fallnummer = as_text(value(row, args.fall_col))
                patient_no = as_text(value(row, args.patient_col))
                episode_id = optional_int(value(row, args.episode_id_col))
                eingriff_id = optional_int(value(row, args.eingriff_id_col))
                context_key = (episode_id, eingriff_id, fallnummer, patient_no)
                context = context_cache.get(context_key)
                if context is None:
                    context = resolve_episode_context(
                        con,
                        episode_id=episode_id,
                        eingriff_id=eingriff_id,
                        fallnummer=fallnummer,
                        patient_no=patient_no,
                        salt=args.salt,
                    )
                    context_cache[context_key] = context
                lab_date = as_iso_date(value(row, args.date_col))
                raw_value = value(row, args.value_col)
                numeric_value = as_float(raw_value)
                text_value = as_text(raw_value)
                unit = args.unit or as_text(value(row, args.unit_col))
                lab_time = as_text(value(row, args.time_col))
                comment = as_text(value(row, args.comment_col))

                existing_id = None
                key = None
                if args.skip_existing:
                    key = labor_key(
                        context=context,
                        parameter=row_parameter,
                        numeric_value=numeric_value,
                        text_value=text_value,
                        unit=unit,
                        lab_date=lab_date,
                        lab_time=lab_time,
                        comment=comment,
                        ignore_comment=args.skip_existing_ignore_comment,
                    )
                    existing_id = known_keys.get(key)
                if existing_id:
                    con.execute(
                        "UPDATE tblRawLabImport SET LaborWertID = ? WHERE RawLabImportID = ?",
                        (existing_id, raw_id),
                    )
                    skipped_existing += 1
                    continue

                cur = con.execute(
                    """
                    INSERT INTO tblLaborWert (
                        EpisodeID, AufenthaltID, EingriffID, PatientHash, FallHash,
                        Fallnummer, Parameter, Wert, WertText, Einheit, Datum,
                        AbnahmeZeit, Kommentar, SourceFileID, RawImportID, Quelle
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Labor')
                    """,
                    (
                        context.get("EpisodeID"),
                        context.get("AufenthaltID"),
                        context.get("EingriffID"),
                        context.get("PatientHash"),
                        context.get("FallHash"),
                        fallnummer if args.include_identifiers else None,
                        row_parameter,
                        numeric_value,
                        text_value,
                        unit,
                        lab_date,
                        lab_time,
                        comment,
                        source_id,
                        raw_id,
                    ),
                )
                con.execute(
                    "UPDATE tblRawLabImport SET LaborWertID = ? WHERE RawLabImportID = ?",
                    (cur.lastrowid, raw_id),
                )
                if args.skip_existing and key is not None:
                    known_keys[key] = int(cur.lastrowid)
                imported += 1

            finish_import_batch(
                con,
                batch_id,
                raw_count,
                note=f"inserted_labor={imported}; skipped_existing={skipped_existing}",
            )
            con.commit()
            return raw_count, imported, skipped_existing
        except Exception as exc:
            finish_import_batch(con, batch_id, raw_count, status="failed", note=str(exc))
            con.commit()
            raise


def main() -> None:
    parser = argparse.ArgumentParser(description="Import CRP/IL6/Leuko/PCT style lab lists into tblLaborWert.")
    parser.add_argument("file", type=Path)
    parser.add_argument("--db", default=Path("outputs/pji_register_orthodok_pseudonymized.sqlite"), type=Path)
    parser.add_argument("--sheet")
    parser.add_argument("--parameter", help="e.g. CRP, IL6, Leuko, PCT")
    parser.add_argument("--parameter-col", help="Column containing the parameter code/name for mixed lab lists")
    parser.add_argument("--value-col", required=True)
    parser.add_argument("--date-col", required=True)
    parser.add_argument("--time-col")
    parser.add_argument("--unit")
    parser.add_argument("--unit-col")
    parser.add_argument("--fall-col")
    parser.add_argument("--patient-col")
    parser.add_argument("--episode-id-col")
    parser.add_argument("--eingriff-id-col")
    parser.add_argument("--comment-col")
    parser.add_argument("--include-identifiers", action="store_true")
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--skip-existing-ignore-comment", action="store_true")
    parser.add_argument(
        "--parameter-map",
        action="append",
        help="Map a source parameter to a register parameter, e.g. --parameter-map L-CRPN=CRP",
    )
    parser.add_argument("--limit", type=int)
    parser.add_argument("--salt", default=os.environ.get("PJI_HASH_SALT", "pji-register-local-v1"))
    args = parser.parse_args()
    if not args.parameter and not args.parameter_col:
        parser.error("one of --parameter or --parameter-col is required")
    raw_count, inserted, skipped_existing = import_labor(args)
    label = args.parameter or args.parameter_col
    print(f"Imported {inserted} {label} lab rows into {args.db}")
    print(f"Raw rows stored: {raw_count}")
    if skipped_existing:
        print(f"Skipped existing lab rows: {skipped_existing}")


if __name__ == "__main__":
    main()
