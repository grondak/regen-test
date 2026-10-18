from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / 'src' / 'http_server.py'


class HttpOrderFlowTests(unittest.TestCase):
    def test_post_order_updates_inventory_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            inventory_file = Path(tmpdir) / 'inventory.json'
            inventory_file.write_text(
                json.dumps(
                    [
                        {
                            'sku': 'SKU-1001',
                            'description': 'Blue widget',
                            'bin_location': 'A1-01',
                            'quantity': 3,
                            'unit': 'each',
                        }
                    ],
                    indent=2,
                )
                + '\n',
                encoding='utf-8',
            )
            env = os.environ.copy()
            env['TINYWMS_PORT'] = '0'
            env['TINYWMS_INVENTORY_FILE'] = str(inventory_file)
            proc = subprocess.Popen(
                [sys.executable, str(SERVER)],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            try:
                assert proc.stdout is not None
                line = proc.stdout.readline().strip()
                self.assertIn('listening on', line)
                port = int(line.rsplit(' ', 1)[-1])
                print(port, flush=True)
                order = {'order_id': 'ORD-1', 'lines': [{'sku': 'SKU-1001', 'quantity': 1}]}
                request = urllib.request.Request(
                    f'http://127.0.0.1:{port}/orders',
                    data=json.dumps(order).encode('utf-8'),
                    headers={'Content-Type': 'application/json'},
                    method='POST',
                )
                with urllib.request.urlopen(request) as response:
                    self.assertEqual(response.status, 201)
                    payload = json.loads(response.read().decode('utf-8'))
                    self.assertEqual(payload['status'], 'accepted')
                with urllib.request.urlopen(f'http://127.0.0.1:{port}/inventory') as response:
                    inventory = json.loads(response.read().decode('utf-8'))
                    self.assertEqual(inventory[0]['quantity'], 2)
                on_disk = json.loads(inventory_file.read_text(encoding='utf-8'))
                self.assertEqual(on_disk[0]['quantity'], 2)
            finally:
                proc.terminate()
                proc.wait(timeout=5)


if __name__ == '__main__':
    unittest.main()
