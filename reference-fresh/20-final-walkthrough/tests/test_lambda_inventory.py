import json
import unittest
from unittest import mock

from src.lambda_inventory import (
    INVENTORY_QUERY_SQL,
    OrderLine,
    OrderRequest,
    InventoryShortageError,
    handler,
    place_order,
)


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows
        self.executed = []
        self.closed = False
        self.rowcount = 0
        self.fetchone_calls = 0

    def execute(self, sql, params=None):
        self.executed.append((sql, params))
        if sql.startswith('UPDATE inventory SET quantity = quantity -'):
            self.rowcount = 1
        if sql.startswith('SELECT sku, description, bin_location, quantity, unit FROM inventory WHERE sku = %s FOR UPDATE'):
            self.fetchone_calls += 1

    def fetchall(self):
        return self.rows

    def fetchone(self):
        if not self.rows:
            return None
        value = self.rows[min(self.fetchone_calls - 1, len(self.rows) - 1)]
        return value

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, rows):
        self.rows = rows
        self.cursor_obj = FakeCursor(rows)
        self.closed = False
        self.commits = 0
        self.rollbacks = 0

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


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


class LambdaInventoryTests(unittest.TestCase):
    def test_handler_returns_inventory_json_from_injected_database_rows(self):
        rows = [
            ('SKU-001', 'Blue widget', 'A1-01', 24, 'each'),
            ('SKU-002', 'Red widget', 'A1-02', 12, 'each'),
        ]
        connection = FakeConnection(rows)

        result = handler({}, None, connection_factory=lambda: connection)

        self.assertEqual(result['statusCode'], 200)
        self.assertEqual(result['headers']['Content-Type'], 'application/json')
        payload = json.loads(result['body'])
        self.assertEqual(payload[0]['sku'], 'SKU-001')
        self.assertEqual(payload[0]['description'], 'Blue widget')
        self.assertEqual(payload[0]['bin_location'], 'A1-01')
        self.assertEqual(payload[1]['quantity'], 12)
        self.assertEqual(connection.cursor_obj.executed[0][0], INVENTORY_QUERY_SQL)
        self.assertTrue(connection.cursor_obj.closed)
        self.assertTrue(connection.closed)

    def test_local_demo_path_still_reads_json_explicitly(self):
        with mock.patch.dict('os.environ', {}, clear=True):
            result = handler({'queryStringParameters': {'demo': 'local-json'}}, None)
        payload = json.loads(result['body'])
        self.assertEqual(payload[0]['sku'], 'SKU-1001')
        self.assertEqual(result['statusCode'], 200)

    def test_place_order_sends_commands_and_domain_event_after_commit(self):
        rows = [
            ('SKU-001', 'Blue widget', 'A1-01', 2, 'each'),
            ('SKU-002', 'Red widget', 'A1-02', 3, 'each'),
        ]
        connection = FakeConnection(rows)
        sqs = FakeSqsClient()
        events = FakeEventBridgeClient()
        order = OrderRequest('ORD-2001', [OrderLine('SKU-001', 1, 'Blue widget'), OrderLine('SKU-002', 2, 'Red widget')])

        result = place_order(connection, order, sqs_client=sqs, eventbridge_client=events)

        self.assertEqual(result['status'], 'accepted')
        self.assertEqual(connection.commits, 1)
        self.assertEqual(connection.rollbacks, 0)
        self.assertEqual(len(sqs.calls), 2)
        self.assertTrue(all(call['QueueUrl'] == '' for call in sqs.calls))
        self.assertEqual(json.loads(sqs.calls[0]['MessageBody'])['sku'], 'SKU-001')
        self.assertEqual(json.loads(sqs.calls[1]['MessageBody'])['bin'], 'A1-02')
        self.assertEqual(len(events.calls), 1)
        event_entry = events.calls[0]['Entries'][0]
        self.assertEqual(event_entry['DetailType'], 'OrderPlaced')
        self.assertEqual(event_entry['Source'], 'tinywms.orders')
        self.assertEqual(json.loads(event_entry['Detail'])['order_id'], 'ORD-2001')
        self.assertTrue(connection.cursor_obj.closed)

    def test_place_order_rolls_back_without_sending_commands_or_event(self):
        rows = [('SKU-001', 'Blue widget', 'A1-01', 1, 'each')]
        connection = FakeConnection(rows)
        sqs = FakeSqsClient()
        events = FakeEventBridgeClient()
        order = OrderRequest('ORD-2002', [OrderLine('SKU-001', 2, 'Blue widget')])

        with self.assertRaises(InventoryShortageError):
            place_order(connection, order, sqs_client=sqs, eventbridge_client=events)

        self.assertEqual(connection.commits, 0)
        self.assertEqual(connection.rollbacks, 1)
        self.assertEqual(sqs.calls, [])
        self.assertEqual(events.calls, [])

    def test_validation_failure_happens_before_connection_factory(self):
        factory = mock.Mock(side_effect=AssertionError('connection should not be opened'))
        response = handler({'httpMethod': 'POST', 'body': json.dumps({'order_id': '', 'lines': []})}, None, connection_factory=factory, sqs_client=FakeSqsClient(), eventbridge_client=FakeEventBridgeClient())
        self.assertEqual(response['statusCode'], 400)
        factory.assert_not_called()


if __name__ == '__main__':
    unittest.main()
