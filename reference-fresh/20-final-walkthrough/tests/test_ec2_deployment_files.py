from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Ec2DeploymentFilesTests(unittest.TestCase):
    def test_required_files_exist(self):
        for rel in [
            'deploy/ec2/README.md',
            'deploy/ec2/environment.example',
            'deploy/ec2/run_inventory_server.sh',
        ]:
            self.assertTrue((ROOT / rel).exists(), rel)


if __name__ == '__main__':
    unittest.main()
