from pathlib import Path
import unittest


class DemoRunbookTests(unittest.TestCase):
    def test_has_26_sessions_and_stable_artifacts(self):
        text = Path('docs/demo-runbook.md').read_text(encoding='utf-8')
        for i in range(1, 27):
            self.assertIn(f'## Session {i}', text)
        self.assertNotIn('## Session 27', text)
        self.assertIn('Session 1', text)
        self.assertIn('Session 26', text)

        required_links = [
            'src/web/index.html',
            'tests/test_http_order_flow.py',
            'src/http_server.py',
            'tests/test_web_app.js',
            'docs/data-contracts.md',
            'tests/test_concurrency.py',
            'data/schema.sql',
            'data/seed.sql',
            'tests/test_sql_export.py',
            'tests/test_lambda_inventory.py',
            'tests/test_sqs_consumer.py',
            'tests/test_event_consumers.py',
            'tests/test_pick_ticket_worker.py',
            'docs/end-to-end.md',
            'deploy/container-worker/README.md',
            'deploy/pick-ticket-worker/README.md',
            'deploy/aws/README.md',
            'tests/test_deployment_wiring.py',
            'infra/template.yaml',
            'tests/test_aws_deployment_files.py',
            'docs/git-history.md',
        ]
        for path in required_links:
            self.assertIn(path, text)

    def test_includes_required_command_forms(self):
        text = Path('docs/demo-runbook.md').read_text(encoding='utf-8')
        self.assertIn('TINYWMS_DB=sqlite TINYWMS_SQLITE_PATH=data/tinywms.db python3 -m data.init_db', text)
        self.assertIn('systemctl --user status tinywms-pick-ticket-worker', text)
        self.assertIn('journalctl --user', text)
        self.assertIn('tail -f', text)
        self.assertIn('docker run', text)
        self.assertIn('PICK_WORK_QUEUE_URL', text)

    def test_sessions_mark_manual_or_partly_manual(self):
        text = Path('docs/demo-runbook.md').read_text(encoding='utf-8')
        session_blocks = [block for block in text.split('## Session ')[1:] if block.strip()]
        self.assertEqual(26, len(session_blocks))
        for block in session_blocks:
            self.assertRegex(block, r'\*\*Work type:\*\* (Manual only|Partly manual)')
