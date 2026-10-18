from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class AwsDeploymentFileTests(unittest.TestCase):
    def test_required_files_exist(self):
        for rel in ['infra/template.yaml', 'deploy/aws/README.md', 'deploy/aws/package_lambda.sh']:
            self.assertTrue((ROOT / rel).exists(), rel)

    def test_template_has_packaged_lambda(self):
        text = (ROOT / 'infra' / 'template.yaml').read_text(encoding='utf-8')
        self.assertIn('AWS::ApiGateway::Method', text)
        self.assertIn('AWS::Lambda::Function', text)
        self.assertIn('AWS::SQS::Queue', text)
        self.assertIn('S3Bucket', text)
        self.assertIn('S3Key', text)
        self.assertIn('PICK_WORK_QUEUE_URL: !Ref PickWorkQueue', text)
        self.assertIn('EVENT_BUS_NAME: !Ref OrderEventsBus', text)
        self.assertIn('Handler: lambda_inventory.handler', text)
        self.assertNotIn('ZipFile:', text)

    def test_packaging_script_uploads_zip(self):
        text = (ROOT / 'deploy' / 'aws' / 'package_lambda.sh').read_text(encoding='utf-8')
        self.assertIn('python3 -m pip install -r requirements.txt -t', text)
        self.assertIn('aws s3 cp', text)
        self.assertIn('lambda_inventory.zip', text)
        self.assertIn('cp src/db_adapter.py', text)


if __name__ == '__main__':
    unittest.main()
