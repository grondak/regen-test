import threading
import unittest

from src.lambda_inventory import OrderLine, OrderRequest, place_order


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


class FakeCursor:
    def __init__(self, state, barrier):
        self.state = state
        self.barrier = barrier
        self.rowcount = 0
        self._last = None

    def execute(self, sql, params=None):
        self.state['sql'].append((sql, params))
        if sql.startswith('SELECT sku, description, bin_location, quantity, unit FROM inventory WHERE sku = %s FOR UPDATE'):
            sku = params[0]
            self.barrier.wait()
            self.state['selects'] += 1
            self._last = self.state['inventory'][sku]
        elif sql.startswith('UPDATE inventory SET quantity = quantity -'):
            amount, sku, threshold = params
            if self.state['inventory'][sku]['quantity'] >= threshold:
                self.state['inventory'][sku]['quantity'] -= amount
                self.rowcount = 1
            else:
                self.rowcount = 0
        elif sql.startswith('INSERT INTO orders'):
            self.state['orders'].append(params)
        elif sql.startswith('INSERT INTO order_lines'):
            self.state['order_lines'].append(params)
        else:
            raise AssertionError(f'unexpected sql: {sql}')

    def fetchone(self):
        return self._last

    def close(self):
        self.state['closed_cursors'] += 1


class FakeConnection:
    def __init__(self, state, barrier):
        self.state = state
        self.barrier = barrier

    def cursor(self):
        return FakeCursor(self.state, self.barrier)

    def commit(self):
        self.state['commits'] += 1

    def rollback(self):
        self.state['rollbacks'] += 1

    def close(self):
        self.state['closed_connections'] += 1


class ConcurrencyTests(unittest.TestCase):
    def test_overlapping_orders_do_not_oversell_inventory(self):
        barrier = threading.Barrier(2)
        state = {
            'inventory': {'SKU-001': {'sku': 'SKU-001', 'description': 'Galvanized Shelf Bracket', 'bin_location': 'A1-01', 'quantity': 1, 'unit': 'each'}},
            'selects': 0,
            'orders': [],
            'order_lines': [],
            'commits': 0,
            'rollbacks': 0,
            'closed_cursors': 0,
            'closed_connections': 0,
            'sql': [],
        }

        def make_connection():
            return FakeConnection(state, barrier)

        sqs = FakeSqsClient()
        events = FakeEventBridgeClient()
        results = []
        errors = []

        def worker(order_id):
            try:
                result = place_order(
                    make_connection(),
                    OrderRequest(order_id=order_id, lines=[OrderLine('SKU-001', 1, 'Galvanized Shelf Bracket')]),
                    sqs_client=sqs,
                    eventbridge_client=events,
                )
                results.append(result)
            except Exception as exc:  # pragma: no cover - captured for assertions
                errors.append(exc)

        first = threading.Thread(target=worker, args=('ORD-1',))
        second = threading.Thread(target=worker, args=('ORD-2',))
        first.start()
        second.start()
        first.join()
        second.join()

        self.assertEqual(len(results), 1)
        self.assertEqual(len(errors), 1)
        self.assertEqual(state['inventory']['SKU-001']['quantity'], 0)
        self.assertEqual(state['commits'], 1)
        self.assertEqual(state['rollbacks'], 1)
        self.assertEqual(len(state['orders']), 1)
        self.assertEqual(len(state['order_lines']), 1)
        self.assertEqual(len(sqs.calls), 1)
        self.assertEqual(len(events.calls), 1)


if __name__ == '__main__':
    unittest.main()
