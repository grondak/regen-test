"""In-memory stand-ins for SQS and EventBridge so the AWS-shaped demos run offline.

Only the calls TinyWMS makes are implemented. Messages are kept in plain lists so
students can print them and see exactly what crossed the boundary.
"""
import itertools
import json


class FakeSQS:
    def __init__(self):
        self.messages = []          # [{'MessageId', 'ReceiptHandle', 'Body'}]
        self._ids = itertools.count(1)

    def send_message(self, QueueUrl, MessageBody, **_):
        n = next(self._ids)
        self.messages.append({'MessageId': f'm-{n}', 'ReceiptHandle': f'rh-{n}', 'Body': MessageBody})
        return {'MessageId': f'm-{n}'}

    def receive_message(self, QueueUrl, MaxNumberOfMessages=10, **_):
        return {'Messages': [dict(m) for m in self.messages[:MaxNumberOfMessages]]}

    def delete_message(self, QueueUrl, ReceiptHandle):
        self.messages = [m for m in self.messages if m['ReceiptHandle'] != ReceiptHandle]

    def redeliver(self, index=0):
        """Simulate SQS at-least-once delivery: the same body arrives again."""
        body = self.messages[index]['Body'] if self.messages else None
        if body is not None:
            self.send_message('fake', body)


class FakeEventBridge:
    def __init__(self):
        self.entries = []

    def put_events(self, Entries):
        self.entries.extend(Entries)
        return {'FailedEntryCount': 0}


def show(label, obj):
    print(f'--- {label}')
    print(json.dumps(obj, indent=2, sort_keys=True) if not isinstance(obj, str) else obj)
