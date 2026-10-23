#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import sqlite3
from pathlib import Path

try:
    from episode_model import migrate_episode_model
except ImportError:
    from scripts.episode_model import migrate_episode_model


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schema" / "pji_register_schema.sql"
LEXICON_PATH = ROOT / "data" / "antibiotics_lexicon.csv"


def init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as con:
        con.execute("PRAGMA foreign_keys = ON")
        con.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        seed_antibiotics(con)
        migrate_episode_model(con)
        con.commit()


def seed_antibiotics(con: sqlite3.Connection) -> None:
    if not LEXICON_PATH.exists():
        return
    with LEXICON_PATH.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            con.execute(
                """
                INSERT OR IGNORE INTO lkpAntibiotikum
                    (NameNorm, ATC, Klasse, Suchbegriffe, Aktiv)
                VALUES (?, ?, ?, ?, 1)
                """,
                (
                    row.get("name_norm"),
                    row.get("atc") or None,
                    row.get("klasse") or None,
                    row.get("suchbegriffe") or None,
                ),
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or update the local PJI register database.")
    parser.add_argument("--db", default="outputs/pji_register.sqlite", type=Path)
    args = parser.parse_args()
    init_db(args.db)
    print(f"Database ready: {args.db}")


if __name__ == "__main__":
    main()
