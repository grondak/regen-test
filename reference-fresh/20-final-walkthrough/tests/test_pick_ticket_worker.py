from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import src.pick_ticket_worker as worker


class FakeConsumer:
    def __init__(self, batches: list[list[dict[str, object]]]):
        self.batches = list(batches)
        self.calls = 0

    def __call__(self, queue_url, callback, *, wait_time_seconds, max_number_of_messages):
        if not self.batches:
            raise KeyboardInterrupt
        self.calls += 1
        batch = self.batches.pop(0)
        for message in batch:
            callback(message, object())
        return len(batch)


class PickTicketWorkerTests(unittest.TestCase):
    def message(self, command_id: str, order_id: str = 'ORD-1001') -> dict[str, object]:
        return {
            'command_id': command_id,
            'order_id': order_id,
            'sku': 'SKU-001',
            'description': 'Galvanized Shelf Bracket',
            'quantity': 1,
            'bin': 'A1-01',
        }

    def run_worker(self, ticket_file: Path, state_file: Path, fake: FakeConsumer, *, once: bool = True):
        argv = [
            'pick_ticket_worker.py',
            'queue-url',
            str(ticket_file),
            '--state-file',
            str(state_file),
        ]
        if once:
            argv.append('--once')
        with patch.object(worker, 'consume_messages', side_effect=fake):
            exit_code = worker.main(argv)
        return exit_code

    def test_multiple_messages_append_multiple_tickets(self):
        with tempfile.TemporaryDirectory() as tmp:
            ticket_file = Path(tmp) / 'pick-tickets.txt'
            state_file = Path(tmp) / 'state.json'
            fake = FakeConsumer([[self.message('pick-work:1'), self.message('pick-work:2', 'ORD-1002')]])
            exit_code = self.run_worker(ticket_file, state_file, fake)

            self.assertEqual(exit_code, 0)
            self.assertEqual(fake.calls, 1)
            contents = ticket_file.read_text(encoding='utf-8')
            self.assertIn('command_id=pick-work:1', contents)
            self.assertIn('command_id=pick-work:2', contents)

    def test_duplicate_delivery_after_restart_is_suppressed_by_state_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            ticket_file = Path(tmp) / 'pick-tickets.txt'
            state_file = Path(tmp) / 'state.json'
            state_file.write_text(json.dumps({'processed_command_ids': ['pick-work:dup']}), encoding='utf-8')
            fake = FakeConsumer([[self.message('pick-work:dup')]])
            exit_code = self.run_worker(ticket_file, state_file, fake)

            self.assertEqual(exit_code, 0)
            self.assertFalse(ticket_file.exists())
            self.assertIn('pick-work:dup', state_file.read_text(encoding='utf-8'))

    def test_service_continues_after_empty_poll(self):
        with tempfile.TemporaryDirectory() as tmp:
            ticket_file = Path(tmp) / 'pick-tickets.txt'
            state_file = Path(tmp) / 'state.json'
            stop_flag = {'stop': False}
            polls = [[], [self.message('pick-work:1')]]
            seen = []

            def fake_consume(queue_url, callback, *, wait_time_seconds, max_number_of_messages):
                batch = polls.pop(0)
                seen.append(len(batch))
                for message in batch:
                    callback(message, object())
                if not polls:
                    stop_flag['stop'] = True
                return len(batch)

            argv = ['pick_ticket_worker.py', 'queue-url', str(ticket_file), '--state-file', str(state_file)]
            with patch.object(worker, 'consume_messages', side_effect=fake_consume):
                exit_code = worker.main(argv, stop_flag=stop_flag)

            self.assertEqual(exit_code, 0)
            self.assertEqual(seen, [0, 1])
            self.assertIn('command_id=pick-work:1', ticket_file.read_text(encoding='utf-8'))

    def test_once_mode_is_bounded_to_one_poll(self):
        with tempfile.TemporaryDirectory() as tmp:
            ticket_file = Path(tmp) / 'pick-tickets.txt'
            state_file = Path(tmp) / 'state.json'
            fake = FakeConsumer([[self.message('pick-work:1')], [self.message('pick-work:2')]])
            exit_code = self.run_worker(ticket_file, state_file, fake, once=True)

            self.assertEqual(exit_code, 0)
            self.assertEqual(fake.calls, 1)
            contents = ticket_file.read_text(encoding='utf-8')
            self.assertIn('pick-work:1', contents)
            self.assertNotIn('pick-work:2', contents)

    def test_failure_does_not_append_or_acknowledge(self):
        with tempfile.TemporaryDirectory() as tmp:
            ticket_file = Path(tmp) / 'pick-tickets.txt'
            state_file = Path(tmp) / 'state.json'
            fake = FakeConsumer([[{'command_id': 'pick-work:bad'}]])
            with patch.object(worker, 'consume_messages', side_effect=fake):
                with self.assertRaises(KeyError):
                    worker.main([
                        'pick_ticket_worker.py',
                        'queue-url',
                        str(ticket_file),
                        '--state-file',
                        str(state_file),
                        '--once',
                    ])
            self.assertFalse(ticket_file.exists())
            self.assertFalse(state_file.exists())

    def test_acknowledgement_after_output_creates_ticket_before_state_update(self):
        with tempfile.TemporaryDirectory() as tmp:
            ticket_file = Path(tmp) / 'pick-tickets.txt'
            state_file = Path(tmp) / 'state.json'
            fake = FakeConsumer([[self.message('pick-work:1')]])
            exit_code = self.run_worker(ticket_file, state_file, fake)

            self.assertEqual(exit_code, 0)
            self.assertTrue(ticket_file.exists())
            ticket_text = ticket_file.read_text(encoding='utf-8')
            self.assertIn('command_id=pick-work:1', ticket_text)
            self.assertIn('pick-work:1', state_file.read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
