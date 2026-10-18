import importlib
import sys
import types
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src'


class DeploymentWiringTests(unittest.TestCase):
    def setUp(self):
        self._orig_path = list(sys.path)
        self._orig_modules = dict(sys.modules)
        sys.path.insert(0, str(SRC))

    def tearDown(self):
        sys.path[:] = self._orig_path
        for name in list(sys.modules):
            if name not in self._orig_modules:
                del sys.modules[name]
        sys.modules.update(self._orig_modules)

    def test_clients_are_created_from_boto3_when_not_injected(self):
        fake_boto3 = types.SimpleNamespace(calls=[])

        def client(service_name):
            fake_boto3.calls.append(service_name)
            return {'service_name': service_name}

        fake_boto3.client = client
        sys.modules['boto3'] = fake_boto3
        sys.modules.pop('lambda_inventory', None)
        module = importlib.import_module('lambda_inventory')

        sqs = module._sqs_client()
        events = module._eventbridge_client()

        self.assertEqual({'service_name': 'sqs'}, sqs)
        self.assertEqual({'service_name': 'events'}, events)
        self.assertEqual(['sqs', 'events'], fake_boto3.calls)

    def test_template_contains_wiring_markers(self):
        text = (ROOT / 'infra' / 'template.yaml').read_text(encoding='utf-8')
        self.assertIn('DATABASE_URL', text)
        self.assertIn('PICK_WORK_QUEUE_URL', text)
        self.assertIn('EVENT_BUS_NAME', text)
        self.assertIn('sqs:SendMessage', text)
        self.assertIn('events:PutEvents', text)
        self.assertIn('PICK_WORK_QUEUE_URL: !Ref PickWorkQueue', text)

    def test_readme_shows_packaging_and_verification_commands(self):
        text = (ROOT / 'deploy' / 'aws' / 'README.md').read_text(encoding='utf-8')
        self.assertIn('python3 -m pip install -r requirements.txt -t deploy/aws/build/lambda', text)
        self.assertIn('./deploy/aws/package_lambda.sh tinywms-lambda-bucket tinywms-cloud-inventory', text)
        self.assertIn('curl -i "$API_BASE_URL/inventory"', text)
        self.assertIn('curl -i -X POST "$API_BASE_URL/orders"', text)
        self.assertIn('aws cloudformation delete-stack --stack-name tinywms-cloud', text)


if __name__ == '__main__':
    unittest.main()
