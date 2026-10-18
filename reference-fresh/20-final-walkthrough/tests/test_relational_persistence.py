from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src import db_adapter

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / 'data' / 'schema.sql'
SEED = ROOT / 'data' / 'seed.sql'
INIT = ROOT / 'data' / 'init_db.py'
INVENTORY = ROOT / 'data' / 'inventory.json'


class RelationalPersistenceTests(unittest.TestCase):
    def test_schema_adds_order_tables_without_renaming_inventory_bin(self):
        schema = SCHEMA.read_text(encoding='utf-8')
        self.assertIn('CREATE TABLE inventory', schema)
        self.assertIn('bin_location TEXT NOT NULL', schema)
        self.assertNotIn(' bin ', schema.lower())
        self.assertIn('create table orders (', schema.lower())
        self.assertIn('create table order_lines (', schema.lower())

    def test_seed_matches_inventory_schema(self):
        items = json.loads(INVENTORY.read_text(encoding='utf-8'))
        seed = SEED.read_text(encoding='utf-8')
        self.assertIn('INSERT INTO inventory (sku, description, bin_location, quantity, unit) VALUES', seed)
        for item in items:
            self.assertIn(item['sku'], seed)
            self.assertIn(item['description'], seed)
            self.assertIn(item['bin_location'], seed)
            self.assertIn(str(item['quantity']), seed)
            self.assertIn(item['unit'], seed)

    def test_sqlite_initializer_loads_inventory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / 'tinywms.db'
            env = os.environ.copy()
            env['TINYWMS_DB'] = 'sqlite'
            env['TINYWMS_SQLITE_PATH'] = str(db_path)
            result = subprocess.run(
                [sys.executable, '-m', 'data.init_db'],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            connection = sqlite3.connect(db_path)
            try:
                rows = connection.execute('SELECT sku, description, bin_location, quantity, unit FROM inventory ORDER BY sku').fetchall()
            finally:
                connection.close()
            self.assertEqual(len(rows), 3)
            self.assertEqual(rows[0][0], 'SKU-1001')
            self.assertEqual(rows[0][2], 'A1-01')

    def test_open_connection_sqlite_enables_foreign_keys_and_translates_placeholders(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / 'adapter.db'
            with mock.patch.dict(os.environ, {'TINYWMS_DB': 'sqlite', 'TINYWMS_SQLITE_PATH': str(db_path)}, clear=False):
                with db_adapter.open_connection() as connection:
                    cursor = connection.cursor()
                    cursor.executescript('CREATE TABLE demo (id INTEGER PRIMARY KEY, note TEXT);')
                    cursor.execute('INSERT INTO demo (note) VALUES (%s)', ('hello',))
                    cursor.execute('SELECT note FROM demo')
                    self.assertEqual(cursor.fetchone()[0], 'hello')
                    cursor.close()

    def test_open_connection_postgres_is_lazy_and_visible(self):
        fake_psycopg2 = mock.Mock()
        fake_connection = mock.Mock()
        fake_cursor = mock.Mock()
        fake_connection.cursor.return_value = fake_cursor
        fake_psycopg2.connect.return_value = fake_connection
        with mock.patch.dict(sys.modules, {'psycopg2': fake_psycopg2}):
            with mock.patch.dict(os.environ, {'DATABASE_URL': 'postgresql://example/db'}, clear=False):
                with db_adapter.open_connection() as connection:
                    self.assertIs(connection, fake_connection)
        fake_psycopg2.connect.assert_called_once_with('postgresql://example/db')


if __name__ == '__main__':
    unittest.main()
