#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

try:
    from import_common import read_table
except ImportError:
    from scripts.import_common import read_table


def main() -> None:
    parser = argparse.ArgumentParser(description="Show columns and sample rows for a CSV/XLSX import file.")
    parser.add_argument("file", type=Path)
    parser.add_argument("--sheet")
    parser.add_argument("--rows", type=int, default=8)
    args = parser.parse_args()

    sheet, rows = read_table(args.file, args.sheet)
    print(f"file: {args.file}")
    print(f"sheet: {sheet or '-'}")
    print(f"rows: {len(rows)}")
    if not rows:
        return
    headers = list(rows[0].keys())
    print("columns:")
    for index, header in enumerate(headers, start=1):
        print(f"  {index:03d}: {header}")
    print("sample:")
    for row in rows[: args.rows]:
        preview = {k: row.get(k) for k in headers[:12]}
        print(preview)


if __name__ == "__main__":
    main()
