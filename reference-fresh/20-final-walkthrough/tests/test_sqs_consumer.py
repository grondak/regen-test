import json
import unittest

from src.sqs_consumer import consume_messages


class FakeSqsClient:
    def __init__(self, messages=None):
        self.messages = messages or []
        self.received = []
        self.deleted = []

    def receive_message(self, **kwargs):
        self.received.append(kwargs)
        return {'Messages': self.messages}

    def delete_message(self, **kwargs):
        self.deleted.append(kwargs)
        return {}


class ConsumerTests(unittest.TestCase):
    def test_success_deletes_message(self):
        client = FakeSqsClient([
            {
                'MessageId': 'm-1',
                'ReceiptHandle': 'rh-1',
                'Body': json.dumps({'command_id': 'pick-work:1', 'sku': 'SKU-001'}),
                'Attributes': {'ApproximateReceiveCount': '1'},
            }
        ])
        seen = []

        def callback(payload, message):
            seen.append((payload, message.message_id, message.receipt_handle))

        processed = consume_messages('queue-url', callback, sqs_client=client, wait_time_seconds=1)

        self.assertEqual(processed, 1)
        self.assertEqual(len(client.received), 1)
        self.assertEqual(client.deleted[0]['ReceiptHandle'], 'rh-1')
        self.assertEqual(seen[0][0]['sku'], 'SKU-001')

    def test_callback_failure_does_not_delete(self):
        client = FakeSqsClient([
            {
                'MessageId': 'm-1',
                'ReceiptHandle': 'rh-1',
                'Body': json.dumps({'command_id': 'pick-work:1', 'sku': 'SKU-001'}),
                'Attributes': {'ApproximateReceiveCount': '2'},
            }
        ])

        def callback(payload, message):
            raise RuntimeError('boom')

        with self.assertRaises(RuntimeError):
            consume_messages('queue-url', callback, sqs_client=client, wait_time_seconds=1)

        self.assertEqual(len(client.received), 1)
        self.assertEqual(client.deleted, [])

    def test_processes_each_message(self):
        client = FakeSqsClient([
            {
                'MessageId': 'm-1',
                'ReceiptHandle': 'rh-1',
                'Body': json.dumps({'command_id': 'pick-work:1', 'sku': 'SKU-001'}),
            },
            {
                'MessageId': 'm-2',
                'ReceiptHandle': 'rh-2',
                'Body': json.dumps({'command_id': 'pick-work:2', 'sku': 'SKU-002'}),
            },
        ])
        seen = []

        processed = consume_messages('queue-url', lambda payload, message: seen.append(payload['command_id']), sqs_client=client, wait_time_seconds=1)

        self.assertEqual(processed, 2)
        self.assertEqual(seen, ['pick-work:1', 'pick-work:2'])
        self.assertEqual(len(client.deleted), 2)


if __name__ == '__main__':
    unittest.main()
