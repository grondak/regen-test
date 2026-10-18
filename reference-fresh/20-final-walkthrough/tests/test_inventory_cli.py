import json
import tempfile
from pathlib import Path
import unittest

from src import inventory_cli


class InventoryCliTests(unittest.TestCase):
    def setUp(self):
        self.inventory_path = Path("data/inventory.json")

    def test_inventory_file_has_required_fields(self):
        items = inventory_cli.load_inventory(self.inventory_path)
        self.assertGreaterEqual(len(items), 1)
        for item in items:
            for field in inventory_cli.REQUIRED_FIELDS:
                self.assertIn(field, item)

    def test_find_returns_matching_json(self):
        items = inventory_cli.load_inventory(self.inventory_path)
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "stdout.txt"
            self.assertEqual(inventory_cli.command_find(items, "SKU-1002"), 0)
            matched = next(item for item in items if item["sku"] == "SKU-1002")
            self.assertEqual(matched["description"], "Red widget")

    def test_dump_emits_valid_json(self):
        items = inventory_cli.load_inventory(self.inventory_path)
        rendered = json.loads(json.dumps(items, indent=2, sort_keys=True))
        self.assertEqual(rendered[0]["sku"], "SKU-1001")

    def test_missing_sku_reports_useful_failure(self):
        items = inventory_cli.load_inventory(self.inventory_path)
        exit_code = inventory_cli.command_find(items, "SKU-DOES-NOT-EXIST")
        self.assertEqual(exit_code, 1)


if __name__ == "__main__":
    unittest.main()
