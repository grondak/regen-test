#!/usr/bin/env python3
from __future__ import annotations

import os
import sys


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print('Usage: linux_visible.py <env|echo|fail>', file=sys.stderr)
        return 2
    command = argv[1]
    if command == 'env':
        print(os.environ.get('TINYWMS_DEMO', 'unset'))
        return 0
    if command == 'echo':
        data = sys.stdin.read() if not sys.stdin.isatty() else ' '.join(argv[2:])
        print(data.rstrip('\n'))
        return 0
    if command == 'fail':
        print('intentional failure for exit-code practice', file=sys.stderr)
        return 3
    print(f'Unknown command: {command}', file=sys.stderr)
    return 2


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
