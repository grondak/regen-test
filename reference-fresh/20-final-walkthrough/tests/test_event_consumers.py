import json
import unittest

from src.event_consumer_a import process_once as process_once_a
from src.event_consumer_b import process_once as process_once_b


class FakeQueueClient:
    def __init__(self, body):
        self.body = body
        self.received = []
        self.deleted = []

    def receive_message(self, **kwargs):
        self.received.append(kwargs)
        return {
            'Messages': [
                {
                    'MessageId': 'm-1',
                    'ReceiptHandle': 'rh-1',
                    'Body': self.body,
                    'Attributes': {'ApproximateReceiveCount': '1'},
                }
            ]
        }

    def delete_message(self, **kwargs):
        self.deleted.append(kwargs)
        return {}


class EventConsumerTests(unittest.TestCase):
    def _event_body(self, order_id='ORD-1'):
        return json.dumps(
            {
                'Source': 'tinywms.orders',
                'DetailType': 'OrderPlaced',
                'Detail': json.dumps({'version': 1, 'order_id': order_id, 'lines': [{'sku': 'SKU-001', 'quantity': 1}]}),
            }
        )

    def test_consumer_a_receives_and_decodes_event(self):
        client = FakeQueueClient(self._event_body('ORD-A'))
        events = process_once_a('queue-url-a', queue_client=client)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['DetailType'], 'OrderPlaced')
        self.assertEqual(events[0]['detail']['order_id'], 'ORD-A')
        self.assertEqual(client.deleted[0]['ReceiptHandle'], 'rh-1')

    def test_consumer_b_receives_and_decodes_event(self):
        client = FakeQueueClient(self._event_body('ORD-B'))
        events = process_once_b('queue-url-b', queue_client=client)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['DetailType'], 'OrderPlaced')
        self.assertEqual(events[0]['detail']['order_id'], 'ORD-B')
        self.assertEqual(client.deleted[0]['ReceiptHandle'], 'rh-1')

    def test_consumers_use_independent_queue_clients(self):
        client_a = FakeQueueClient(self._event_body('ORD-A'))
        client_b = FakeQueueClient(self._event_body('ORD-B'))
        events_a = process_once_a('queue-url-a', queue_client=client_a)
        events_b = process_once_b('queue-url-b', queue_client=client_b)
        self.assertEqual(events_a[0]['detail']['order_id'], 'ORD-A')
        self.assertEqual(events_b[0]['detail']['order_id'], 'ORD-B')
        self.assertEqual(len(client_a.received), 1)
        self.assertEqual(len(client_b.received), 1)


if __name__ == '__main__':
    unittest.main()
