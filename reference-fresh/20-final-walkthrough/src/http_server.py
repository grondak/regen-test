#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = ROOT / 'src' / 'web'
DEFAULT_INVENTORY = ROOT / 'data' / 'inventory.json'
PORT = int(os.environ.get('TINYWMS_PORT', '8000'))
INVENTORY_FILE = Path(os.environ.get('TINYWMS_INVENTORY_FILE', str(DEFAULT_INVENTORY)))


@dataclass
class InventoryStore:
    path: Path

    def load(self) -> list[dict[str, Any]]:
        return json.loads(self.path.read_text(encoding='utf-8'))

    def save(self, items: list[dict[str, Any]]) -> None:
        self.path.write_text(json.dumps(items, indent=2) + '\n', encoding='utf-8')

    def _index(self, items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        return {item['sku']: item for item in items}

    def apply_order(self, order: dict[str, Any]) -> dict[str, Any]:
        items = self.load()
        index = self._index(items)
        for line in order['lines']:
            sku = line['sku']
            quantity = line['quantity']
            item = index.get(sku)
            if item is None:
                raise ValueError(f'unknown sku: {sku}')
            if item['quantity'] < quantity:
                raise ValueError(f'insufficient inventory for {sku}')
        for line in order['lines']:
            index[line['sku']]['quantity'] -= line['quantity']
        self.save(items)
        return {'order_id': order['order_id'], 'status': 'accepted'}


STORE = InventoryStore(INVENTORY_FILE)


def _content_type(path: str) -> str:
    if path.endswith('.html'):
        return 'text/html; charset=utf-8'
    if path.endswith('.js'):
        return 'application/javascript; charset=utf-8'
    if path.endswith('.css'):
        return 'text/css; charset=utf-8'
    return 'application/octet-stream'


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, payload: Any) -> None:
        body = json.dumps(payload).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path) -> None:
        body = path.read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', _content_type(path.name))
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == '/':
            return self._send_file(WEB_DIR / 'index.html')
        if parsed.path == '/index.html':
            return self._send_file(WEB_DIR / 'index.html')
        if parsed.path == '/app.js':
            return self._send_file(WEB_DIR / 'app.js')
        if parsed.path == '/style.css':
            return self._send_file(WEB_DIR / 'style.css')
        if parsed.path == '/inventory':
            return self._send_json(200, STORE.load())
        self._send_json(404, {'error': 'not found'})

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != '/orders':
            return self._send_json(404, {'error': 'not found'})
        try:
            length = int(self.headers.get('Content-Length', '0'))
            body = self.rfile.read(length).decode('utf-8')
            order = json.loads(body or '{}')
            if not isinstance(order, dict):
                raise ValueError('order must be an object')
            if not isinstance(order.get('order_id'), str) or not order['order_id']:
                raise ValueError('order_id must be a non-empty string')
            lines = order.get('lines')
            if not isinstance(lines, list) or not lines:
                raise ValueError('lines must be a non-empty array')
            for line in lines:
                if not isinstance(line, dict):
                    raise ValueError('each order line must be an object')
                if not isinstance(line.get('sku'), str) or not line['sku']:
                    raise ValueError('line sku must be a non-empty string')
                if not isinstance(line.get('quantity'), int) or line['quantity'] < 1:
                    raise ValueError('line quantity must be a positive integer')
            result = STORE.apply_order(order)
            self._send_json(201, result)
        except ValueError as exc:
            self._send_json(409, {'error': str(exc)})
        except json.JSONDecodeError:
            self._send_json(400, {'error': 'request body must be JSON'})

    def log_message(self, format, *args):
        print(self.address_string(), format % args)


def main() -> int:
    server = ThreadingHTTPServer(('0.0.0.0', PORT), Handler)
    print(f'listening on {server.server_address[1]}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
