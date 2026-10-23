#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
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
        nearest_intervention_for_episode,
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
        nearest_intervention_for_episode,
        read_table,
        resolve_episode_context,
        row_to_json,
        start_import_batch,
    )


def value(row: dict[str, object], column: str | None) -> object | None:
    if not column:
        return None
    return row.get(column)


EMPTY_ANTIBIOGRAM_RESULTS = {"", "#", "-", "n.e.", "n.a.", "na", "none", "null"}
WIDE_ANTIBIOGRAM_HEADER = re.compile(r"^[A-Z0-9]+(?:_[A-Z0-9]+)?\s*\(([^)]+)\)$")


def raw_cell_text(raw: object | None) -> str | None:
    if raw is None:
        return None
    if isinstance(raw, float) and raw.is_integer():
        return str(int(raw))
    text = str(raw).strip()
    return text or None


def optional_int(raw: object | None) -> int | None:
    number = as_float(raw)
    return int(number) if number is not None else None


def is_wide_antibiogram_column(header: str) -> bool:
    if header.startswith("AB_"):
        return True
    return bool(WIDE_ANTIBIOGRAM_HEADER.match(header))


def antibiotic_name_from_column(header: str) -> str:
    match = WIDE_ANTIBIOGRAM_HEADER.match(header)
    if match:
        return match.group(1).strip()
    text = header
    if text.startswith("AB_"):
        text = text[3:]
    text = re.sub(r"_\d+$", "", text)
    return text.replace("_", " ").strip()


def discovered_antibiogram_columns(rows: list[dict[str, object]]) -> list[str]:
    if not rows:
        return []
    return [header for header in rows[0].keys() if is_wide_antibiogram_column(header)]


def antibiogram_results(
    row: dict[str, object],
    args: argparse.Namespace,
    wide_columns: list[str],
) -> list[tuple[str, str | None, str | None, str | None]]:
    if args.antibiotic_col:
        antibiotic = as_text(value(row, args.antibiotic_col))
        if not antibiotic:
            return []
        return [
            (
                antibiotic,
                raw_cell_text(value(row, args.result_col)),
                as_text(value(row, args.mhk_col)),
                args.antibiotic_col,
            )
        ]

    results: list[tuple[str, str | None, str | None, str | None]] = []
    for column in wide_columns:
        result = raw_cell_text(row.get(column))
        if not args.include_empty_antibiogram and (result is None or result.lower() in EMPTY_ANTIBIOGRAM_RESULTS):
            continue
        if result is None:
            continue
        results.append((antibiotic_name_from_column(column), result, None, column))
    return results


def build_comment(row: dict[str, object], args: argparse.Namespace) -> str | None:
    parts: list[str] = []
    status = raw_cell_text(value(row, args.status_col))
    comment = as_text(value(row, args.comment_col))
    if status:
        parts.append(f"Status: {status}")
    if comment:
        parts.append(comment)
    return "; ".join(parts) or None


def micro_key(
    *,
    eingriff_id: int,
    material: str | None,
    sample_date: str | None,
    pathogen: str | None,
    comment: str | None,
) -> tuple[object, ...]:
    return (
        eingriff_id,
        material or "",
        sample_date or "",
        pathogen or "",
        comment or "",
    )


def existing_microbiology_keys(con) -> dict[tuple[object, ...], int]:
    keys: dict[tuple[object, ...], int] = {}
    for row in con.execute(
        """
        SELECT MikrobioID, EingriffID, Material, Entnahmedatum, Erreger, Kommentar
        FROM tblMikrobiologie
        WHERE Quelle = 'HYBASE'
        """
    ):
        key = micro_key(
            eingriff_id=int(row["EingriffID"]),
            material=row["Material"],
            sample_date=row["Entnahmedatum"],
            pathogen=row["Erreger"],
            comment=row["Kommentar"],
        )
        keys.setdefault(key, int(row["MikrobioID"]))
    return keys


def antibiogram_key(
    mikrobio_id: int,
    antibiotic: str,
    result: str | None,
    mhk: str | None,
    comment: str | None,
) -> tuple[object, ...]:
    return (mikrobio_id, antibiotic, result or "", mhk or "", comment or "")


def existing_antibiogram_keys(con) -> dict[tuple[object, ...], int]:
    keys: dict[tuple[object, ...], int] = {}
    for row in con.execute(
        """
        SELECT AntibiogrammID, MikrobioID, Antibiotikum, Ergebnis, MHK, Kommentar
        FROM tblAntibiogramm
        WHERE Quelle = 'HYBASE'
        """
    ):
        key = antibiogram_key(
            int(row["MikrobioID"]),
            row["Antibiotikum"],
            row["Ergebnis"],
            row["MHK"],
            row["Kommentar"],
        )
        keys.setdefault(key, int(row["AntibiogrammID"]))
    return keys


def import_hybase(args: argparse.Namespace) -> tuple[int, int, int, int, int]:
    sheet, rows = read_table(args.file, args.sheet)
    if args.limit:
        rows = rows[: args.limit]
    wide_columns = discovered_antibiogram_columns(rows) if not args.antibiotic_col else []

    with connect_db(args.db) as con:
        source_id = get_or_create_source(con, args.file, "HYBASE")
        batch_id = start_import_batch(con, source_id, "hybase")
        raw_count = 0
        micro_count = 0
        micro_reused = 0
        antibiogram_count = 0
        antibiogram_reused = 0
        known_micro = existing_microbiology_keys(con) if args.skip_existing else {}
        known_antibiogram = existing_antibiogram_keys(con) if args.skip_existing else {}
        context_cache: dict[tuple[object, ...], dict[str, object]] = {}
        try:
            for row_number, row in enumerate(rows, start=2):
                raw_id = con.execute(
                    """
                    INSERT INTO tblRawHybaseImport (
                        ImportBatchID, SheetName, RowNumber, RawJSON
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        batch_id,
                        sheet,
                        row_number,
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

                sample_date = as_iso_date(value(row, args.date_col))
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
                resolved_eingriff_id = context.get("EingriffID") or nearest_intervention_for_episode(
                    con,
                    context.get("EpisodeID"),
                    sample_date,
                )
                material = as_text(value(row, args.material_col))
                pathogen = as_text(value(row, args.pathogen_col))
                comment = build_comment(row, args)
                mikrobio_id = None
                if resolved_eingriff_id and (material or pathogen or sample_date):
                    key = micro_key(
                        eingriff_id=int(resolved_eingriff_id),
                        material=material,
                        sample_date=sample_date,
                        pathogen=pathogen,
                        comment=comment,
                    )
                    mikrobio_id = known_micro.get(key)
                    if mikrobio_id:
                        micro_reused += 1
                    else:
                        cur = con.execute(
                            """
                            INSERT INTO tblMikrobiologie (
                                EingriffID, Material, Entnahmedatum, Erreger, Kommentar, Quelle
                            )
                            VALUES (?, ?, ?, ?, ?, 'HYBASE')
                            """,
                            (resolved_eingriff_id, material, sample_date, pathogen, comment),
                        )
                        mikrobio_id = int(cur.lastrowid)
                        known_micro[key] = mikrobio_id
                        micro_count += 1

                antibiogramm_id = None
                for antibiotic, result, mhk, source_column in antibiogram_results(row, args, wide_columns):
                    if not (mikrobio_id and antibiotic):
                        continue
                    ab_key = antibiogram_key(mikrobio_id, antibiotic, result, mhk, comment)
                    created_antibiogramm_id = known_antibiogram.get(ab_key)
                    if created_antibiogramm_id:
                        antibiogram_reused += 1
                    else:
                        cur = con.execute(
                            """
                            INSERT INTO tblAntibiogramm (
                                MikrobioID, Antibiotikum, Ergebnis, MHK, Kommentar, Quelle
                            )
                            VALUES (?, ?, ?, ?, ?, 'HYBASE')
                            """,
                            (mikrobio_id, antibiotic, result, mhk, comment),
                        )
                        created_antibiogramm_id = int(cur.lastrowid)
                        known_antibiogram[ab_key] = created_antibiogramm_id
                        antibiogram_count += 1
                    if antibiogramm_id is None:
                        antibiogramm_id = created_antibiogramm_id
                    con.execute(
                        """
                        INSERT INTO tblRawHybaseAntibiogrammLink (
                            RawHybaseImportID, AntibiogrammID, AntibiotikumSpalte
                        )
                        VALUES (?, ?, ?)
                        """,
                        (raw_id, created_antibiogramm_id, source_column),
                    )

                con.execute(
                    """
                    UPDATE tblRawHybaseImport
                    SET MikrobioID = ?, AntibiogrammID = ?
                    WHERE RawHybaseImportID = ?
                    """,
                    (mikrobio_id, antibiogramm_id, raw_id),
                )

            finish_import_batch(
                con,
                batch_id,
                raw_count,
                note=(
                    f"normalized_micro={micro_count}; "
                    f"reused_micro={micro_reused}; "
                    f"normalized_antibiogram={antibiogram_count}; "
                    f"reused_antibiogram={antibiogram_reused}; "
                    f"wide_antibiogram_columns={len(wide_columns)}"
                ),
            )
            con.commit()
            return raw_count, micro_count, micro_reused, antibiogram_count, antibiogram_reused
        except Exception as exc:
            finish_import_batch(con, batch_id, raw_count, status="failed", note=str(exc))
            con.commit()
            raise


def main() -> None:
    parser = argparse.ArgumentParser(description="Import HYBASE microbiology/antibiogram lists.")
    parser.add_argument("file", type=Path)
    parser.add_argument("--db", default=Path("outputs/pji_register_orthodok_pseudonymized.sqlite"), type=Path)
    parser.add_argument("--sheet")
    parser.add_argument("--date-col")
    parser.add_argument("--material-col")
    parser.add_argument("--pathogen-col")
    parser.add_argument("--antibiotic-col")
    parser.add_argument("--result-col")
    parser.add_argument("--mhk-col")
    parser.add_argument("--status-col")
    parser.add_argument("--fall-col")
    parser.add_argument("--patient-col")
    parser.add_argument("--episode-id-col")
    parser.add_argument("--eingriff-id-col")
    parser.add_argument("--comment-col")
    parser.add_argument("--include-empty-antibiogram", action="store_true")
    parser.add_argument("--include-identifiers", action="store_true")
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--salt", default=os.environ.get("PJI_HASH_SALT", "pji-register-local-v1"))
    args = parser.parse_args()
    raw_count, micro_count, micro_reused, antibiogram_count, antibiogram_reused = import_hybase(args)
    print(f"Imported {raw_count} HYBASE raw rows into {args.db}")
    print(f"Normalized microbiology rows: {micro_count}")
    if micro_reused:
        print(f"Reused existing microbiology rows: {micro_reused}")
    print(f"Normalized antibiogram rows: {antibiogram_count}")
    if antibiogram_reused:
        print(f"Reused existing antibiogram rows: {antibiogram_reused}")


if __name__ == "__main__":
    main()
