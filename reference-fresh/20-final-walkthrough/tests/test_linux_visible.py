from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
LINUX = ROOT / 'src' / 'linux_visible.py'
WATCHER = ROOT / 'src' / 'inventory_watcher.py'
DATA = ROOT / 'data' / 'inventory.json'


class LinuxVisibleTests(unittest.TestCase):
    def test_env_reads_environment(self):
        env = os.environ.copy()
        env['TINYWMS_DEMO'] = 'visible'
        result = subprocess.run([sys.executable, str(LINUX), 'env'], capture_output=True, text=True, env=env)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), 'visible')

    def test_fail_returns_nonzero(self):
        result = subprocess.run([sys.executable, str(LINUX), 'fail'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 3)
        self.assertIn('intentional failure', result.stderr)

    def test_watcher_writes_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / 'watch.log'
            proc = subprocess.Popen([sys.executable, str(WATCHER), str(DATA), str(log)])
            try:
                import time
                time.sleep(2.5)
                self.assertTrue(log.exists())
                self.assertIn('SKU-1001', log.read_text(encoding='utf-8'))
            finally:
                proc.terminate()
                proc.wait(timeout=5)


if __name__ == '__main__':
    unittest.main()
