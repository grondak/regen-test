#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from src.lambda_inventory import OrderLine, OrderRequest, place_order

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INVENTORY = ROOT / 'data' / 'inventory.json'


@dataclass
class DemoState:
    inventory: dict[str, dict[str, Any]]
    barrier: threading.Barrier
    commits: int = 0
    rollbacks: int = 0
    log: list[str] = None

    def __post_init__(self):
        if self.log is None:
            self.log = []


class DemoCursor:
    def __init__(self, state: DemoState):
        self.state = state
        self.rowcount = 0
        self._last_row = None

    def execute(self, sql, params=None):
        self.state.log.append(f'cursor.execute: {sql} {params!r}')
        if sql == 'SELECT sku, description, bin_location, quantity, unit FROM inventory WHERE sku = %s FOR UPDATE':
            sku = params[0]
            self.state.log.append(f'lock requested for {sku}')
            self.state.barrier.wait()
            self._last_row = self.state.inventory.get(sku)
            return
        if sql == 'UPDATE inventory SET quantity = quantity - %s WHERE sku = %s AND quantity >= %s':
            amount, sku, threshold = params
            item = self.state.inventory.get(sku)
            if item is not None and item['quantity'] >= threshold:
                item['quantity'] -= amount
                self.rowcount = 1
                self.state.log.append(f'updated {sku} to {item["quantity"]}')
            else:
                self.rowcount = 0
                self.state.log.append(f'update rejected for {sku}')
            return
        if sql == 'INSERT INTO orders (order_id, status) VALUES (%s, %s)':
            self.state.log.append(f'order inserted {params!r}')
            return
        if sql == 'INSERT INTO order_lines (order_id, sku, quantity) VALUES (%s, %s, %s)':
            self.state.log.append(f'order line inserted {params!r}')
            return
        if sql == 'BEGIN':
            self.state.log.append('transaction begin')
            return
        raise AssertionError(f'unexpected SQL: {sql}')

    def fetchone(self):
        return self._last_row

    def close(self):
        self.state.log.append('cursor closed')


class DemoConnection:
    def __init__(self, state: DemoState):
        self.state = state

    def cursor(self):
        return DemoCursor(self.state)

    def commit(self):
        self.state.commits += 1
        self.state.log.append('commit')

    def rollback(self):
        self.state.rollbacks += 1
        self.state.log.append('rollback')

    def close(self):
        self.state.log.append('connection closed')


def _load_demo_inventory() -> dict[str, dict[str, Any]]:
    data = json.loads(DEFAULT_INVENTORY.read_text(encoding='utf-8'))
    return {item['sku']: dict(item) for item in data}


def _run_attempt(state: DemoState, order_id: str, quantity: int) -> None:
    connection = DemoConnection(state)
    order = OrderRequest(order_id=order_id, lines=[OrderLine(sku='SKU-1001', quantity=quantity, description='Blue widget')])
    try:
        result = place_order(connection, order)
        print(f'{order_id}: accepted -> {result}')
    except Exception as exc:
        print(f'{order_id}: rejected -> {exc}')


def main() -> int:
    inventory = _load_demo_inventory()
    inventory['SKU-1001']['quantity'] = 1
    state = DemoState(inventory=inventory, barrier=threading.Barrier(2))
    print('starting concurrency demo with SKU-1001 quantity set to 1')
    print('database backend is controlled by TINYWMS_DB, TINYWMS_SQLITE_PATH, and DATABASE_URL')
    print('for the real row-lock lesson, use PostgreSQL as documented in deploy/rds/README.md')

    first = threading.Thread(target=_run_attempt, args=(state, 'ORD-A', 1))
    second = threading.Thread(target=_run_attempt, args=(state, 'ORD-B', 1))
    first.start()
    second.start()
    first.join()
    second.join()

    print(f'commits: {state.commits}')
    print(f'rollbacks: {state.rollbacks}')
    print(f'final inventory: {json.dumps(inventory["SKU-1001"], sort_keys=True)}')
    print('log:')
    for line in state.log:
        print(f'  {line}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
