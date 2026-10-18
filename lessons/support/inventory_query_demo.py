"""GET /inventory through the real Lambda handler, reading rows from SQLite.

Run from 20-final-walkthrough:
    TINYWMS_DB=sqlite TINYWMS_SQLITE_PATH=/tmp/tinywms.db python3 -m data.init_db
    PYTHONPATH=. python3 ../lessons/support/inventory_query_demo.py
"""
import json
import os
import sqlite3

from src.db_adapter import SQLiteConnectionAdapter
from src.lambda_inventory import handler

DB = os.environ.get('TINYWMS_SQLITE_PATH', '/tmp/tinywms.db')


def factory():      # the handler wants an object with .cursor() and .close()
    return SQLiteConnectionAdapter(sqlite3.connect(DB))


response = handler({}, None, connection_factory=factory)
print('statusCode:', response['statusCode'])
print('body is a', type(response['body']).__name__, '->', response['body'][:70], '...')
for item in json.loads(response['body']):
    print(' ', item)
