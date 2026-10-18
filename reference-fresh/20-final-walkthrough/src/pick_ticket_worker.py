#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import signal
import sys
from pathlib import Path
from typing import Any

from src.sqs_consumer import consume_messages


DEFAULT_STATE_FILE = 'pick-ticket-worker-state.json'
DEFAULT_TICKET_FILE = 'pick-tickets.txt'


def load_state(path: Path) -> set[str]:
    if not path.exists():
        return set()
    payload = json.loads(path.read_text(encoding='utf-8'))
    return set(payload.get('processed_command_ids', []))


def save_state(path: Path, processed: set[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {'processed_command_ids': sorted(processed)}
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def format_ticket(work: dict[str, Any]) -> str:
    return (
        f"command_id={work['command_id']} "
        f"order_id={work['order_id']} "
        f"sku={work['sku']} "
        f"description={work.get('description', 'unknown item')} "
        f"quantity={work['quantity']} "
        f"bin={work['bin']}"
    )


def append_ticket(ticket_path: Path, line: str) -> None:
    ticket_path.parent.mkdir(parents=True, exist_ok=True)
    with ticket_path.open('a', encoding='utf-8') as handle:
        handle.write(line + '\n')


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Long-running pick-ticket worker')
    parser.add_argument('queue_url')
    parser.add_argument('ticket_file')
    parser.add_argument('--state-file', default=DEFAULT_STATE_FILE)
    parser.add_argument('--once', action='store_true', help='Poll once and exit after the batch is handled')
    parser.add_argument('--wait-time-seconds', type=int, default=20)
    parser.add_argument('--max-number-of-messages', type=int, default=10)
    return parser


def main(argv: list[str], stop_flag: dict[str, bool] | None = None) -> int:
    """Run the worker. stop_flag is a shared {'stop': bool} mapping so callers (and tests) can end service mode."""
    args = build_arg_parser().parse_args(argv[1:])
    ticket_path = Path(args.ticket_file)
    state_path = Path(args.state_file)
    processed = load_state(state_path)
    if stop_flag is None:
        stop_flag = {'stop': False}

    def request_stop(_signum, _frame):
        stop_flag['stop'] = True

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)

    def handle_message(work: dict[str, Any], _received: Any) -> None:
        command_id = work['command_id']
        if command_id in processed:
            return
        ticket = format_ticket(work)
        append_ticket(ticket_path, ticket)
        print(ticket)
        processed.add(command_id)
        save_state(state_path, processed)

    try:
        while True:
            consume_messages(
                args.queue_url,
                handle_message,
                wait_time_seconds=args.wait_time_seconds,
                max_number_of_messages=args.max_number_of_messages,
            )
            if args.once or stop_flag['stop']:
                break
    except KeyboardInterrupt:
        stop_flag['stop'] = True
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
