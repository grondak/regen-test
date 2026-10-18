"""Feed the REAL pick-ticket worker from an in-memory queue, including a duplicate delivery.

Run from 20-final-walkthrough:
    PYTHONPATH=.:../lessons/support python3 ../lessons/support/worker_demo.py
Then compare the ticket file with the state file.
"""
import json
import os
import tempfile

from fake_aws import FakeEventBridge, FakeSQS

work = tempfile.mkdtemp()
db = os.path.join(work, 'demo.db')
os.environ.update(TINYWMS_DB='sqlite', TINYWMS_SQLITE_PATH=db,
                  PICK_WORK_QUEUE_URL='fake-queue', EVENT_BUS_NAME='fake-bus')

import src.sqs_consumer as sqs_consumer                 # noqa: E402
from data.init_db import init_db                        # noqa: E402
from src.db_adapter import open_connection              # noqa: E402
from src.lambda_inventory import OrderLine, OrderRequest, place_order   # noqa: E402
from src.pick_ticket_worker import main as run_worker   # noqa: E402

init_db()
queue, bus = FakeSQS(), FakeEventBridge()
with open_connection() as conn:                          # a real order produces real pick-work commands
    place_order(conn, OrderRequest('ORD-77', [OrderLine('SKU-1001', 2, None), OrderLine('SKU-2001', 1, None)]),
                sqs_client=queue, eventbridge_client=bus)
queue.redeliver(0)                                       # SQS is at-least-once: line 1 arrives twice
print(f'queue holds {len(queue.messages)} messages (one is a duplicate)\n')

sqs_consumer._default_sqs_client = lambda: queue         # point the worker at the fake queue
tickets, state = os.path.join(work, 'pick-tickets.txt'), os.path.join(work, 'state.json')
run_worker(['worker', 'fake-queue', tickets, '--state-file', state, '--once'])

print('\n=== pick-tickets.txt (note: only 2 tickets, not 3)')
print(open(tickets).read())
print('=== state file')
print(open(state).read())
print('queue now holds', len(queue.messages), 'messages')
