"""GET /inventory through the real Lambda handler, reading rows from SQLite.

Run from the stage-20 folder (any stage from 10 up works):
    export TINYWMS_DB=sqlite TINYWMS_SQLITE_PATH=/tmp/tinywms.db
    python3 -m data.init_db
    PYTHONPATH=. python3 "$LESSONS/support/inventory_query_demo.py"
"""
import json

from src.lambda_inventory import handler

response = handler({}, None)          # no demo=local-json flag, no injected connection: it queries the database
print('statusCode:', response['statusCode'])
print('body is a', type(response['body']).__name__, '->', response['body'][:70], '...')
for item in json.loads(response['body']):
    print(' ', item)
