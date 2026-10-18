#!/usr/bin/env python3
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

try:
    import boto3  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    boto3 = None


@dataclass(frozen=True)
class ReceivedMessage:
    message_id: str | None
    receipt_handle: str | None
    body: str
    attributes: dict[str, Any]
    message_attributes: dict[str, Any]
    md5_of_body: str | None = None


def _default_sqs_client():
    if boto3 is None:
        raise RuntimeError('boto3 is required only when no injected SQS client is provided')
    return boto3.client('sqs')


def _received_message(message: dict[str, Any]) -> ReceivedMessage:
    return ReceivedMessage(
        message_id=message.get('MessageId'),
        receipt_handle=message.get('ReceiptHandle'),
        body=message.get('Body', ''),
        attributes=message.get('Attributes', {}),
        message_attributes=message.get('MessageAttributes', {}),
        md5_of_body=message.get('MD5OfBody'),
    )


def consume_messages(
    queue_url: str,
    callback: Callable[[dict[str, Any], ReceivedMessage], Any],
    *,
    sqs_client=None,
    wait_time_seconds: int = 20,
    max_number_of_messages: int = 10,
) -> int:
    client = sqs_client or _default_sqs_client()
    response = client.receive_message(
        QueueUrl=queue_url,
        MaxNumberOfMessages=max_number_of_messages,
        WaitTimeSeconds=wait_time_seconds,
        AttributeNames=['All'],
        MessageAttributeNames=['All'],
    )
    messages = response.get('Messages', [])
    processed = 0
    for message in messages:
        received = _received_message(message)
        visible_metadata = {
            'message_id': received.message_id,
            'receipt_handle': received.receipt_handle,
            'attributes': received.attributes,
            'message_attributes': received.message_attributes,
            'md5_of_body': received.md5_of_body,
        }
        print(json.dumps(visible_metadata, indent=2, sort_keys=True))
        payload = json.loads(received.body)
        callback(payload, received)
        client.delete_message(QueueUrl=queue_url, ReceiptHandle=received.receipt_handle)
        processed += 1
    return processed


if __name__ == '__main__':  # pragma: no cover
    raise SystemExit('Use as an imported consumer helper in tests or a small wrapper script')
