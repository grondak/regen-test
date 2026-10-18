#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print('Usage: sql_export.py <inventory.json>', file=sys.stderr)
        return 2
    items = json.loads(Path(argv[1]).read_text(encoding='utf-8'))
    if not isinstance(items, list):
        print('error: inventory JSON must be an array', file=sys.stderr)
        return 1
    print('INSERT INTO inventory (sku, description, bin_location, quantity, unit) VALUES')
    rows = []
    for item in items:
        rows.append(
            "  ('{sku}', '{description}', '{bin_location}', {quantity}, '{unit}')".format(**item)
        )
    print(',\n'.join(rows) + ';')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
