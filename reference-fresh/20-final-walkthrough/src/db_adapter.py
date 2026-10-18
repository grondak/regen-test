from __future__ import annotations

"""TinyWMS database adapter with a narrow SQLite teaching mode."""

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path


class SQLiteCursorAdapter:
    """Adapt SQLite cursors to the small PostgreSQL-flavored SQL subset we teach.

    This is intentionally narrow: it only converts %s placeholders to ? and
    removes FOR UPDATE so the examples remain readable.
    """

    def __init__(self, cursor):
        self._cursor = cursor

    def execute(self, sql, params=None):
        adapted_sql = sql.replace('%s', '?').replace(' FOR UPDATE', '')
        if params is None:
            return self._cursor.execute(adapted_sql)
        return self._cursor.execute(adapted_sql, params)

    def executemany(self, sql, seq_of_params):
        adapted_sql = sql.replace('%s', '?').replace(' FOR UPDATE', '')
        return self._cursor.executemany(adapted_sql, seq_of_params)

    def executescript(self, sql):
        return self._cursor.executescript(sql)

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    def close(self):
        return self._cursor.close()

    @property
    def rowcount(self):
        return self._cursor.rowcount


class SQLiteConnectionAdapter:
    def __init__(self, connection):
        self._connection = connection

    def cursor(self):
        return SQLiteCursorAdapter(self._connection.cursor())

    def commit(self):
        return self._connection.commit()

    def rollback(self):
        return self._connection.rollback()

    def close(self):
        return self._connection.close()


@contextmanager
def open_connection():
    backend = os.environ.get('TINYWMS_DB', 'postgres').strip().lower()
    if backend == 'sqlite':
        db_path = Path(os.environ.get('TINYWMS_SQLITE_PATH', 'tinywms.sqlite3'))
        connection = sqlite3.connect(db_path)
        connection.row_factory = None
        connection.execute('PRAGMA foreign_keys=ON')
        try:
            yield SQLiteConnectionAdapter(connection)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        return

    try:
        import psycopg2  # type: ignore
    except ModuleNotFoundError as exc:
        raise RuntimeError('psycopg2 is required when TINYWMS_DB=postgres') from exc

    dsn = os.environ.get('DATABASE_URL')
    if not dsn:
        raise RuntimeError('DATABASE_URL is required when TINYWMS_DB=postgres')
    connection = psycopg2.connect(dsn)
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
