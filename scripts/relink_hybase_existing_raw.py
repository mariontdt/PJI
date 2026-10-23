#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

try:
    from import_common import (
        as_iso_date,
        as_text,
        connect_db,
        finish_import_batch,
        get_or_create_source,
        nearest_intervention_for_episode,
        read_table,
        resolve_episode_context,
        start_import_batch,
    )
    from import_hybase import (
        antibiogram_results,
        build_comment,
        discovered_antibiogram_columns,
        optional_int,
        value,
    )
except ImportError:
    from scripts.import_common import (
        as_iso_date,
        as_text,
        connect_db,
        finish_import_batch,
        get_or_create_source,
        nearest_intervention_for_episode,
        read_table,
        resolve_episode_context,
        start_import_batch,
    )
    from scripts.import_hybase import (
        antibiogram_results,
        build_comment,
        discovered_antibiogram_columns,
        optional_int,
        value,
    )


def import_existing_raw_links(args: argparse.Namespace) -> tuple[int, int, int, int]:
    sheet, rows = read_table(args.file, args.sheet)
    if args.limit:
        rows = rows[: args.limit]
    wide_columns = discovered_antibiogram_columns(rows) if not args.antibiotic_col else []

    with connect_db(args.db) as con:
        source_id = get_or_create_source(con, args.file, "HYBASE")
        batch_id = start_import_batch(con, source_id, "hybase_relink_existing_raw")
        existing = {
            (row["SheetName"], int(row["RowNumber"])): row
            for row in con.execute(
                """
                SELECT r.RawHybaseImportID, r.SheetName, r.RowNumber, r.MikrobioID
                FROM tblRawHybaseImport r
                JOIN tblImportBatch b ON b.ImportBatchID = r.ImportBatchID
                WHERE b.SourceFileID = ? AND b.ImportType = 'hybase'
                """,
                (source_id,),
            )
        }
        scanned = 0
        relinked = 0
        micro_count = 0
        antibiogram_count = 0
        try:
            for row_number, row in enumerate(rows, start=2):
                scanned += 1
                raw = existing.get((sheet, row_number))
                if not raw or raw["MikrobioID"]:
                    continue

                sample_date = as_iso_date(value(row, args.date_col))
                context = resolve_episode_context(
                    con,
                    episode_id=optional_int(value(row, args.episode_id_col)),
                    eingriff_id=optional_int(value(row, args.eingriff_id_col)),
                    fallnummer=as_text(value(row, args.fall_col)),
                    patient_no=as_text(value(row, args.patient_col)),
                    salt=args.salt,
                )
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
                    micro_count += 1
                    relinked += 1

                first_antibiogramm_id = None
                for antibiotic, result, mhk, source_column in antibiogram_results(row, args, wide_columns):
                    if not (mikrobio_id and antibiotic):
                        continue
                    cur = con.execute(
                        """
                        INSERT INTO tblAntibiogramm (
                            MikrobioID, Antibiotikum, Ergebnis, MHK, Kommentar, Quelle
                        )
                        VALUES (?, ?, ?, ?, ?, 'HYBASE')
                        """,
                        (mikrobio_id, antibiotic, result, mhk, comment),
                    )
                    antibiogramm_id = int(cur.lastrowid)
                    if first_antibiogramm_id is None:
                        first_antibiogramm_id = antibiogramm_id
                    con.execute(
                        """
                        INSERT INTO tblRawHybaseAntibiogrammLink (
                            RawHybaseImportID, AntibiogrammID, AntibiotikumSpalte
                        )
                        VALUES (?, ?, ?)
                        """,
                        (raw["RawHybaseImportID"], antibiogramm_id, source_column),
                    )
                    antibiogram_count += 1

                if mikrobio_id:
                    con.execute(
                        """
                        UPDATE tblRawHybaseImport
                        SET MikrobioID = ?, AntibiogrammID = ?
                        WHERE RawHybaseImportID = ?
                        """,
                        (mikrobio_id, first_antibiogramm_id, raw["RawHybaseImportID"]),
                    )

            finish_import_batch(
                con,
                batch_id,
                scanned,
                note=(
                    f"relinked_raw_rows={relinked}; normalized_micro={micro_count}; "
                    f"normalized_antibiogram={antibiogram_count}; wide_antibiogram_columns={len(wide_columns)}"
                ),
            )
            con.commit()
            return scanned, relinked, micro_count, antibiogram_count
        except Exception as exc:
            finish_import_batch(con, batch_id, scanned, status="failed", note=str(exc))
            con.commit()
            raise


def main() -> None:
    parser = argparse.ArgumentParser(description="Relink existing HYBASE raw rows after new OrthoDok cases were imported.")
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
    parser.add_argument("--limit", type=int)
    parser.add_argument("--salt", default="pji-register-local-v1")
    args = parser.parse_args()
    scanned, relinked, micro_count, antibiogram_count = import_existing_raw_links(args)
    print(f"Scanned {scanned} HYBASE rows")
    print(f"Relinked raw rows: {relinked}")
    print(f"Normalized microbiology rows: {micro_count}")
    print(f"Normalized antibiogram rows: {antibiogram_count}")


if __name__ == "__main__":
    main()
