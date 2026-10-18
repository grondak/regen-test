#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import time
from pathlib import Path


def snapshot(inventory_path: Path) -> str:
    data = json.loads(inventory_path.read_text(encoding='utf-8'))
    return json.dumps({'count': len(data), 'skus': [item['sku'] for item in data]}, sort_keys=True)


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print('Usage: inventory_watcher.py <inventory.json> <log-file>', file=sys.stderr)
        return 2
    inventory_path = Path(argv[1])
    log_path = Path(argv[2])
    with log_path.open('a', encoding='utf-8') as log:
        print(f'watching {inventory_path}', file=log, flush=True)
        while True:
            print(snapshot(inventory_path), file=log, flush=True)
            time.sleep(2)


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
