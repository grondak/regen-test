from pathlib import Path
import ast
import json
import unittest

ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = ROOT / 'src' / 'Dockerfile'
README = ROOT / 'deploy' / 'container-worker' / 'README.md'
WORKER = ROOT / 'src' / 'pick_ticket_worker.py'


class ContainerWorkerTests(unittest.TestCase):
    def test_dockerfile_uses_real_worker_entrypoint_and_defaults(self):
        text = DOCKERFILE.read_text(encoding='utf-8')
        self.assertIn('FROM python:3.11-slim', text)
        self.assertIn('COPY pick_ticket_worker.py /app/pick_ticket_worker.py', text)
        self.assertIn('COPY sqs_consumer.py /app/sqs_consumer.py', text)
        self.assertIn('ENTRYPOINT ["python3", "/app/pick_ticket_worker.py"]', text)
        self.assertIn('CMD ["pick-work-queue-url", "pick-tickets.txt", "--state-file", "pick-ticket-worker-state.json"]', text)

    def test_readme_shows_build_run_env_mounts_and_once_command(self):
        text = README.read_text(encoding='utf-8')
        self.assertIn('docker build -f src/Dockerfile -t tinywms-pick-ticket-worker .', text)
        self.assertIn('PICK_WORK_QUEUE_URL', text)
        self.assertIn('pick-tickets.txt:/app/pick-tickets.txt', text)
        self.assertIn('pick-ticket-worker-state.json:/app/pick-ticket-worker-state.json', text)
        self.assertIn('--once', text)
        self.assertIn('bounded classroom run', text)

    def test_worker_module_still_exposes_long_running_queue_contract(self):
        source = WORKER.read_text(encoding='utf-8')
        tree = ast.parse(source)
        self.assertTrue(any(isinstance(node, ast.FunctionDef) and node.name == 'main' for node in tree.body))
        self.assertIn('--once', source)
        self.assertIn('consume_messages', source)
        self.assertIn('signal.signal(signal.SIGTERM, request_stop)', source)
        self.assertIn('signal.signal(signal.SIGINT, request_stop)', source)

    def test_readme_example_mentions_host_backed_mounts_and_queue_url_variable(self):
        text = README.read_text(encoding='utf-8')
        self.assertIn('host-backed mounts', text)
        self.assertIn('queue URL supplied through `PICK_WORK_QUEUE_URL`', text)
        self.assertIn('processed-command state file', text)


if __name__ == '__main__':
    unittest.main()
