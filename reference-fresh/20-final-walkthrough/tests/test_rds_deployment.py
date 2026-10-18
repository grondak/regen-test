from __future__ import annotations

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / 'deploy' / 'rds' / 'README.md'
TEMPLATE = ROOT / 'infra' / 'rds.yaml'
ARCH = ROOT / 'docs' / 'architecture.md'
CONTRACTS = ROOT / 'docs' / 'data-contracts.md'


class RdsDeploymentTests(unittest.TestCase):
    def test_required_files_exist(self):
        for path in [README, TEMPLATE, ARCH, CONTRACTS]:
            self.assertTrue(path.exists(), path)

    def test_readme_has_required_command_flow(self):
        text = README.read_text(encoding='utf-8')
        for heading in ('## Deploy', '## Resolve outputs', '## Verify', '## Destroy'):
            self.assertIn(heading, text)
        self.assertLess(text.index('## Deploy'), text.index('## Resolve outputs'))
        self.assertLess(text.index('## Resolve outputs'), text.index('## Verify'))
        self.assertLess(text.index('## Verify'), text.index('## Destroy'))
        for token in ('aws cloudformation describe-stacks', 'DbEndpointAddress', 'DbEndpointPort', 'psql'):
            self.assertIn(token, text)

    def test_template_has_nonempty_rds_resources_and_outputs(self):
        text = TEMPLATE.read_text(encoding='utf-8')
        for token in (
            'Type: AWS::RDS::DBInstance', 'Type: AWS::RDS::DBSubnetGroup',
            'DbEndpointAddress', 'DbEndpointPort', 'SubnetIds: !Ref DbSubnetIds', 'NoEcho: true',
        ):
            self.assertIn(token, text)
        self.assertNotIn('example.invalid', text)
        self.assertNotIn('123456789012', text)

    def test_architecture_preserves_the_managed_rds_shift(self):
        text = ARCH.read_text(encoding='utf-8').lower()
        for token in ('rds', 'managed', 'deployment wrapper', 'sqlite'):
            self.assertIn(token, text)

    def test_data_contracts_preserve_the_hosting_and_column_contract(self):
        text = CONTRACTS.read_text(encoding='utf-8').lower()
        for token in ('self-managed', 'rds', 'bin_location'):
            self.assertIn(token, text)


if __name__ == '__main__':
    unittest.main()
