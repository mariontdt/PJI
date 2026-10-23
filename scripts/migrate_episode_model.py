#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

try:
    from episode_model import migrate_episode_model
except ImportError:
    from scripts.episode_model import migrate_episode_model


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate an existing PJI register database to the episode model.")
    parser.add_argument("--db", default=Path("outputs/pji_register_orthodok_pseudonymized.sqlite"), type=Path)
    args = parser.parse_args()

    with sqlite3.connect(args.db) as con:
        con.execute("PRAGMA foreign_keys = ON")
        migrate_episode_model(con)
        errors = con.execute("PRAGMA foreign_key_check").fetchall()
        con.commit()

    print(f"Episode model migrated: {args.db}")
    print(f"foreign_key_errors={len(errors)}")


if __name__ == "__main__":
    main()
