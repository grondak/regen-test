"""Contrast the CreatePickTicket command with the OrderPlaced event, and add a second subscriber.

Run from 20-final-walkthrough:
    PYTHONPATH=.:../lessons/support python3 ../lessons/support/events_demo.py
"""
import json
import os
import tempfile

from fake_aws import FakeEventBridge, FakeSQS

db = os.path.join(tempfile.mkdtemp(), 'demo.db')
os.environ.update(TINYWMS_DB='sqlite', TINYWMS_SQLITE_PATH=db,
                  PICK_WORK_QUEUE_URL='fake-queue', EVENT_BUS_NAME='fake-bus')

from data.init_db import init_db                        # noqa: E402
from src.db_adapter import open_connection              # noqa: E402
from src.lambda_inventory import OrderLine, OrderRequest, place_order   # noqa: E402

init_db()
commands, bus = FakeSQS(), FakeEventBridge()
with open_connection() as conn:
    place_order(conn, OrderRequest('ORD-88', [OrderLine('SKU-1002', 3, None)]),
                sqs_client=commands, eventbridge_client=bus)

print('COMMAND  ("do this", one addressee, names the bin and quantity to pick):')
print(json.dumps(json.loads(commands.messages[0]['Body']), indent=2))
print('\nEVENT  ("this happened", no addressee, says nothing about what anyone should do):')
event = bus.entries[0]
print(json.dumps({'Source': event['Source'], 'DetailType': event['DetailType'],
                  'Detail': json.loads(event['Detail'])}, indent=2))

# Fan-out: EventBridge copies the event to every subscriber. Two trivial subscribers, no change to the order code.
def audit_subscriber(evt):
    print('  [audit]    logged', evt['DetailType'], json.loads(evt['Detail'])['order_id'])

def email_subscriber(evt):
    d = json.loads(evt['Detail'])
    print(f"  [customer] would email: order {d['order_id']} has {len(d['lines'])} line(s)")

print('\nFan-out to subscribers:')
for subscriber in (audit_subscriber, email_subscriber):
    subscriber(event)
