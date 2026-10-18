#!/usr/bin/env python3
from __future__ import annotations

"""Initialize TinyWMS relational storage.

TINYWMS_DB selects the backend:
- postgres (default): use psycopg2 and DATABASE_URL
- sqlite: use the SQLite database at TINYWMS_SQLITE_PATH
"""

import sys
from pathlib import Path

from src.db_adapter import open_connection


def _read_sql(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def init_db() -> None:
    """Apply schema.sql then seed.sql to the database chosen by TINYWMS_DB (sqlite or postgres)."""
    root = Path(__file__).resolve().parents[1]
    schema_path = root / 'data' / 'schema.sql'
    seed_path = root / 'data' / 'seed.sql'

    with open_connection() as connection:
        cursor = connection.cursor()
        try:
            cursor.executescript(_read_sql(schema_path))
            cursor.executescript(_read_sql(seed_path))
        finally:
            cursor.close()
        connection.commit()


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print('Usage: data/init_db.py', file=sys.stderr)
        return 2
    init_db()
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
