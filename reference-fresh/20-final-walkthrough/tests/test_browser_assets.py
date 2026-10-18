from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'src' / 'web' / 'app.js'
INDEX = ROOT / 'src' / 'web' / 'index.html'
STYLE = ROOT / 'src' / 'web' / 'style.css'


class BrowserAssetTests(unittest.TestCase):
    def test_assets_reference_inventory_and_orders(self):
        app = APP.read_text(encoding='utf-8')
        index = INDEX.read_text(encoding='utf-8')
        style = STYLE.read_text(encoding='utf-8')
        self.assertIn('/inventory', app)
        self.assertIn('/orders', app)
        self.assertIn('window.TINYWMS_API_BASE_URL', app)
        self.assertIn('fetch(', app)
        self.assertIn('TinyWMS inventory and orders', index)
        self.assertIn('order-json', index)
        self.assertIn('response-json', index)
        self.assertIn('border-collapse', style)
        self.assertIn('#response-json', style)


if __name__ == '__main__':
    unittest.main()
