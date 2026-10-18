from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'src' / 'sql_export.py'
DATA = ROOT / 'data' / 'inventory.json'
SCHEMA = ROOT / 'data' / 'schema.sql'
SEED = ROOT / 'data' / 'seed.sql'


class SqlExportTests(unittest.TestCase):
    def test_export_mentions_inventory(self):
        result = subprocess.run([sys.executable, str(SCRIPT), str(DATA)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn('INSERT INTO inventory', result.stdout)
        self.assertIn('SKU-1001', result.stdout)
        self.assertIn('bin_location', result.stdout)

    def test_schema_and_seed_exist(self):
        self.assertTrue(SCHEMA.exists())
        self.assertTrue(SEED.exists())
        self.assertIn('CREATE TABLE inventory', SCHEMA.read_text(encoding='utf-8'))
        self.assertIn('INSERT INTO inventory', SEED.read_text(encoding='utf-8'))
        self.assertIn('bin_location', SCHEMA.read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
