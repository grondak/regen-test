"""Walk orders through the real place_order() against a throwaway SQLite database.

Run from 20-final-walkthrough:
    PYTHONPATH=.:../lessons/support python3 ../lessons/support/order_demo.py
"""
import os
import sqlite3
import tempfile

from fake_aws import FakeEventBridge, FakeSQS, show

db = os.path.join(tempfile.mkdtemp(), 'demo.db')
os.environ.update(TINYWMS_DB='sqlite', TINYWMS_SQLITE_PATH=db,
                  PICK_WORK_QUEUE_URL='fake-queue', EVENT_BUS_NAME='fake-bus')

from data.init_db import init_db                       # noqa: E402
from src.db_adapter import open_connection             # noqa: E402
from src.lambda_inventory import (InventoryError, OrderLine, OrderRequest,  # noqa: E402
                                  place_order)

init_db()
queue, bus = FakeSQS(), FakeEventBridge()


def stock():
    with sqlite3.connect(db) as c:
        return dict(c.execute('SELECT sku, quantity FROM inventory ORDER BY sku'))


def try_order(order_id, *lines):
    order = OrderRequest(order_id, [OrderLine(sku, qty, None) for sku, qty in lines])
    try:
        with open_connection() as conn:
            result = place_order(conn, order, sqs_client=queue, eventbridge_client=bus)
        print(f'{order_id}: ACCEPTED {result}')
    except InventoryError as exc:
        print(f'{order_id}: REJECTED  {exc}')
    print('   stock now:', stock())


print('stock at start:', stock())
try_order('ORD-1', ('SKU-1001', 2), ('SKU-2001', 1))     # multi-line, succeeds
try_order('ORD-2', ('SKU-1002', 1), ('SKU-2001', 999))   # 2nd line fails -> 1st line must roll back
try_order('ORD-3', ('NOPE', 1))                          # unknown SKU
with sqlite3.connect(db) as c:
    show('orders table', c.execute('SELECT * FROM orders').fetchall())
    show('order_lines table', c.execute('SELECT * FROM order_lines').fetchall())
show('messages that would be in SQS', [m['Body'] for m in queue.messages])
show('events that would be on the bus', bus.entries)
