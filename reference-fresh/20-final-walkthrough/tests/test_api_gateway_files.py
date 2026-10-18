from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ApiGatewayFilesTests(unittest.TestCase):
    def test_required_files_exist(self):
        for rel in ['infra/api-gateway.yaml', 'deploy/api-gateway/README.md']:
            self.assertTrue((ROOT / rel).exists(), rel)


if __name__ == '__main__':
    unittest.main()
