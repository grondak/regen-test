#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from typing import Any


def _queue_client(queue_client=None):
    if queue_client is not None:
        return queue_client
    try:
        import boto3  # type: ignore
    except ModuleNotFoundError as exc:
        raise RuntimeError('boto3 is required when a queue client is not injected') from exc
    return boto3.client('sqs')


def _decode_event(body: str) -> dict[str, Any]:
    message = json.loads(body)
    detail = message.get('Detail') or message.get('detail')
    if isinstance(detail, str):
        message['detail'] = json.loads(detail)
    elif isinstance(detail, dict):
        message['detail'] = detail
    return message


def process_once(queue_url: str, queue_client=None) -> list[dict[str, Any]]:
    client = _queue_client(queue_client)
    response = client.receive_message(QueueUrl=queue_url, MaxNumberOfMessages=10, WaitTimeSeconds=0)
    messages = response.get('Messages', [])
    decoded: list[dict[str, Any]] = []
    for message in messages:
        body = message['Body']
        decoded.append(_decode_event(body))
        client.delete_message(QueueUrl=queue_url, ReceiptHandle=message['ReceiptHandle'])
    return decoded


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print('Usage: event_consumer_b.py <queue-url>')
        return 2
    for event in process_once(argv[1]):
        print(f"consumer-b received {event['DetailType']} for {event['detail']['order_id']}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
