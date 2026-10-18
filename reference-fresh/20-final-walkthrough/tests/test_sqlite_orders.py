import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from data.init_db import init_db
from src.db_adapter import open_connection
from src.lambda_inventory import OrderLine, OrderRequest, InventoryShortageError, place_order



class FakeSqsClient:
    def __init__(self):
        self.calls = []

    def send_message(self, **kwargs):
        self.calls.append(kwargs)
        return {'MessageId': f'm-{len(self.calls)}'}


class FakeEventBridgeClient:
    def __init__(self):
        self.calls = []

    def put_events(self, **kwargs):
        self.calls.append(kwargs)
        return {'FailedEntryCount': 0, 'Entries': [{'EventId': 'evt-1'}]}


class SqliteOrderTests(unittest.TestCase):
    """Real SQLite proof: temporary database, schema.sql + seed.sql, persisted rows, rollback."""

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        db_path = Path(self.tempdir.name) / 'tinywms.sqlite3'
        patcher = mock.patch.dict(os.environ, {'TINYWMS_DB': 'sqlite', 'TINYWMS_SQLITE_PATH': str(db_path)})
        patcher.start()
        self.addCleanup(patcher.stop)
        init_db()

    def tearDown(self):
        self.tempdir.cleanup()

    def _count(self, sql, params=()):
        with open_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(sql, params)
            value = cursor.fetchone()[0]
            cursor.close()
            return value

    def _place(self, order):
        with open_connection() as connection:
            return place_order(
                connection,
                order,
                sqs_client=FakeSqsClient(),
                eventbridge_client=FakeEventBridgeClient(),
            )

    def test_accepted_order_persists_rows(self):
        before = self._count('SELECT quantity FROM inventory WHERE sku = %s', ('SKU-1001',))
        result = self._place(OrderRequest('ORD-SQLITE-1', [OrderLine('SKU-1001', 2, 'Blue widget')]))
        self.assertEqual(result['status'], 'accepted')
        self.assertEqual(self._count('SELECT quantity FROM inventory WHERE sku = %s', ('SKU-1001',)), before - 2)
        self.assertEqual(self._count('SELECT COUNT(*) FROM orders WHERE order_id = %s', ('ORD-SQLITE-1',)), 1)
        self.assertEqual(self._count('SELECT COUNT(*) FROM order_lines WHERE order_id = %s', ('ORD-SQLITE-1',)), 1)

    def test_insufficient_inventory_rolls_back(self):
        before = self._count('SELECT quantity FROM inventory WHERE sku = %s', ('SKU-1002',))
        with self.assertRaises(InventoryShortageError):
            self._place(OrderRequest('ORD-SQLITE-2', [OrderLine('SKU-1002', 999, 'Red widget')]))
        self.assertEqual(self._count('SELECT quantity FROM inventory WHERE sku = %s', ('SKU-1002',)), before)
        self.assertEqual(self._count('SELECT COUNT(*) FROM orders WHERE order_id = %s', ('ORD-SQLITE-2',)), 0)
        self.assertEqual(self._count('SELECT COUNT(*) FROM order_lines WHERE order_id = %s', ('ORD-SQLITE-2',)), 0)

    def test_unknown_sku_rolls_back(self):
        with self.assertRaises(InventoryShortageError):
            self._place(OrderRequest('ORD-SQLITE-3', [OrderLine('SKU-DOES-NOT-EXIST', 1, 'Missing item')]))
        self.assertEqual(self._count('SELECT COUNT(*) FROM orders WHERE order_id = %s', ('ORD-SQLITE-3',)), 0)

    def test_sqlite_cannot_prove_row_locking(self):
        # Stage 12 concurrency needs PostgreSQL: SQLite has no row-level FOR UPDATE.
        self.assertEqual(os.environ['TINYWMS_DB'], 'sqlite')


if __name__ == '__main__':
    unittest.main()
