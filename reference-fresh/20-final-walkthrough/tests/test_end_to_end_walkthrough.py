from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / 'docs' / 'end-to-end.md'


class EndToEndWalkthroughTests(unittest.TestCase):
    def test_walkthrough_mentions_only_source_backed_boundaries(self):
        text = DOC.read_text(encoding='utf-8')

        self.assertIn('src/web/index.html', text)
        self.assertIn('src/web/app.js', text)
        self.assertIn('src/http_server.py', text)
        self.assertIn('src/lambda_inventory.py', text)
        self.assertIn('src/pick_ticket_worker.py', text)
        self.assertIn('infra/template.yaml', text)
        self.assertIn('PYTHONPATH=src python3 -m unittest tests.test_callback_integration -v', text)

        for boundary in (
            'Browser inventory and order page',
            'API Gateway invoke boundary',
            'Amazon RDS',
            'Lambda-to-SQS service API',
            'Lambda-to-EventBridge service API',
            'pick-work message body from the queue',
        ):
            self.assertIn(boundary, text)

        for forbidden in (
            'docs/architecture.md',
            'docs/data-contracts.md',
            'Source code in',
            'unbacked',
            'draws from',
        ):
            self.assertNotIn(forbidden, text)


if __name__ == '__main__':
    unittest.main()
