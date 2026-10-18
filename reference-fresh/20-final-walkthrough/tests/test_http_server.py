from pathlib import Path
import json
import os
import subprocess
import sys
import time
import urllib.request
import unittest

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / 'src' / 'http_server.py'


class HttpServerTests(unittest.TestCase):
    def test_inventory_endpoint_returns_json(self):
        env = os.environ.copy()
        env['TINYWMS_PORT'] = '0'
        proc = subprocess.Popen([sys.executable, str(SERVER)], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            assert proc.stdout is not None
            readiness = proc.stdout.readline().strip()
            self.assertIn('listening on', readiness)
            port = int(readiness.rsplit(' ', 1)[-1])
            with urllib.request.urlopen(f'http://127.0.0.1:{port}/inventory') as response:
                self.assertEqual(response.status, 200)
                payload = json.loads(response.read().decode('utf-8'))
                self.assertEqual(payload[0]['sku'], 'SKU-1001')
        finally:
            proc.terminate()
            proc.wait(timeout=5)


if __name__ == '__main__':
    unittest.main()
