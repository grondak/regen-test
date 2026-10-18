from __future__ import annotations
import json
import os
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator

class InventoryError(Exception):
    pass

class OrderValidationError(InventoryError):
    pass

class InventoryShortageError(InventoryError):
    pass
InventoryLookupError = InventoryShortageError

@dataclass(frozen=True)
class OrderLine:
    sku: str
    quantity: int
    description: str | None = None

@dataclass(frozen=True)
class OrderRequest:
    order_id: str
    lines: list[OrderLine]
INVENTORY_QUERY_SQL = 'SELECT sku, description, bin_location, quantity, unit FROM inventory ORDER BY sku'
INVENTORY_FOR_UPDATE_SQL = 'SELECT sku, description, bin_location, quantity, unit FROM inventory WHERE sku = %s FOR UPDATE'
DECREMENT_INVENTORY_SQL = 'UPDATE inventory SET quantity = quantity - %s WHERE sku = %s AND quantity >= %s'
INSERT_ORDER_SQL = 'INSERT INTO orders (order_id, status) VALUES (%s, %s)'
INSERT_ORDER_LINE_SQL = 'INSERT INTO order_lines (order_id, sku, quantity) VALUES (%s, %s, %s)'
PICK_WORK_QUEUE_URL_ENV = 'PICK_WORK_QUEUE_URL'
EVENT_BUS_NAME_ENV = 'EVENT_BUS_NAME'
ROOT = Path(__file__).resolve().parents[1]
INVENTORY_FILE = ROOT / 'data' / 'inventory.json'
DB_DSN_ENV = 'DATABASE_URL'

def _cursor_for_connection(connection):
    cursor = connection.cursor()
    if connection.__class__.__module__ == 'sqlite3':
        from src.db_adapter import SQLiteCursorAdapter
        return SQLiteCursorAdapter(cursor)
    return cursor

def _load_inventory() -> list[dict[str, Any]]:
    return json.loads(INVENTORY_FILE.read_text(encoding='utf-8'))

def _map_inventory_row(row: Any) -> dict[str, Any]:
    if isinstance(row, dict):
        return {'sku': row['sku'], 'description': row['description'], 'bin_location': row.get('bin_location', row.get('bin')), 'quantity': row['quantity'], 'unit': row['unit']}
    return {'sku': row[0], 'description': row[1], 'bin_location': row[2], 'quantity': row[3], 'unit': row[4]}

def _parse_body(event: dict[str, Any]) -> dict[str, Any]:
    body = event.get('body') or '{}'
    if isinstance(body, str):
        return json.loads(body)
    if isinstance(body, dict):
        return body
    raise OrderValidationError('request body must be JSON')

def parse_order_request(event: dict[str, Any]) -> OrderRequest:
    body = _parse_body(event)
    if 'order_id' not in body or 'lines' not in body:
        raise OrderValidationError('invalid order')
    if not isinstance(body['order_id'], str) or not body['order_id']:
        raise OrderValidationError('order_id must be a non-empty string')
    if not isinstance(body['lines'], list) or not body['lines']:
        raise OrderValidationError('lines must be a non-empty array')
    lines: list[OrderLine] = []
    for item in body['lines']:
        if not isinstance(item, dict):
            raise OrderValidationError('each order line must be an object')
        sku = item.get('sku')
        quantity = item.get('quantity')
        description = item.get('description')
        if not isinstance(sku, str) or not sku:
            raise OrderValidationError('line sku must be a non-empty string')
        if not isinstance(quantity, int) or quantity < 1:
            raise OrderValidationError('line quantity must be a positive integer')
        if description is not None and (not isinstance(description, str)):
            raise OrderValidationError('line description must be a string when present')
        lines.append(OrderLine(sku=sku, quantity=quantity, description=description))
    return OrderRequest(order_id=body['order_id'], lines=lines)

def _fetch_inventory_row(cursor, sku: str):
    cursor.execute(INVENTORY_FOR_UPDATE_SQL, (sku,))
    return cursor.fetchone()

def _command_id(order_id: str, sku: str, quantity: int, bin_location: str) -> str:
    return f'pick-work:{order_id}:{sku}:{quantity}:{bin_location}'

def _build_pick_work_commands(order: OrderRequest, locked_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    commands: list[dict[str, Any]] = []
    for line, row in zip(order.lines, locked_rows):
        bin_location = row['bin_location']
        commands.append({'command_id': _command_id(order.order_id, line.sku, line.quantity, bin_location), 'order_id': order.order_id, 'sku': line.sku, 'description': row['description'], 'quantity': line.quantity, 'bin': bin_location})
    return commands

def _build_order_placed_event(order: OrderRequest) -> dict[str, Any]:
    return {'Source': 'tinywms.orders', 'DetailType': 'OrderPlaced', 'Detail': json.dumps({'version': 1, 'order_id': order.order_id, 'lines': [{'sku': line.sku, 'quantity': line.quantity} for line in order.lines]})}

def _sqs_client(sqs_client=None):
    if sqs_client is not None:
        return sqs_client
    import boto3
    return boto3.client('sqs')

def _eventbridge_client(eventbridge_client=None):
    if eventbridge_client is not None:
        return eventbridge_client
    import boto3
    return boto3.client('events')

def _psycopg2_connect(dsn: str):
    try:
        import psycopg2
    except ModuleNotFoundError as exc:
        raise RuntimeError('PostgreSQL driver is required for deployed connections') from exc
    return psycopg2.connect(dsn)

@contextmanager
def open_connection(dsn: str | None=None) -> Iterator[Any]:
    connection = _psycopg2_connect(dsn or os.environ[DB_DSN_ENV])
    try:
        yield connection
    finally:
        connection.close()

def place_order(connection, order: OrderRequest, sqs_client=None, eventbridge_client=None) -> dict[str, Any]:
    locked_rows: list[dict[str, Any]] = []
    cursor = _cursor_for_connection(connection)
    try:
        for line in order.lines:
            row = _fetch_inventory_row(cursor, line.sku)
            if row is None:
                raise InventoryShortageError(f'unknown sku: {line.sku}')
            if isinstance(row, tuple):
                row = {'sku': row[0], 'description': row[1], 'bin_location': row[2], 'quantity': row[3], 'unit': row[4]}
            available = row['quantity']
            if available < line.quantity:
                raise InventoryShortageError(f'insufficient inventory for {line.sku}')
            cursor.execute(DECREMENT_INVENTORY_SQL, (line.quantity, line.sku, line.quantity))
            if cursor.rowcount != 1:
                raise InventoryShortageError(f'insufficient inventory for {line.sku}')
            locked_rows.append(row)
        cursor.execute(INSERT_ORDER_SQL, (order.order_id, 'accepted'))
        for line in order.lines:
            cursor.execute(INSERT_ORDER_LINE_SQL, (order.order_id, line.sku, line.quantity))
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
    queue_url = os.environ.get(PICK_WORK_QUEUE_URL_ENV, '')
    if sqs_client is not None or queue_url:
        sqs = _sqs_client(sqs_client)
        for command in _build_pick_work_commands(order, locked_rows):
            sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps(command))
    bus_name = os.environ.get(EVENT_BUS_NAME_ENV, '')
    if eventbridge_client is not None or bus_name:
        eventbridge = _eventbridge_client(eventbridge_client)
        eventbridge.put_events(Entries=[{**_build_order_placed_event(order), 'EventBusName': bus_name}])
    return {'order_id': order.order_id, 'status': 'accepted'}

def _inventory_payload(connection_factory: Callable[[], Any]) -> list[dict[str, Any]]:
    connection = connection_factory()
    try:
        cursor = _cursor_for_connection(connection)
        try:
            cursor.execute(INVENTORY_QUERY_SQL)
            rows = cursor.fetchall()
            return [_map_inventory_row(row) for row in rows]
        finally:
            cursor.close()
    finally:
        connection.close()

def handler(event, context, connection_factory: Callable[[], Any] | None=None, sqs_client=None, eventbridge_client=None):
    event = event or {}
    method = event.get('httpMethod', 'GET')
    if method == 'POST':
        try:
            order = parse_order_request(event)
            connection = connection_factory() if connection_factory is not None else open_connection().__enter__()
            try:
                result = place_order(connection, order, sqs_client=sqs_client, eventbridge_client=eventbridge_client)
            finally:
                if connection_factory is not None:
                    connection.close()
            return {'statusCode': 201, 'headers': {'Content-Type': 'application/json'}, 'body': json.dumps(result)}
        except OrderValidationError as exc:
            return {'statusCode': 400, 'headers': {'Content-Type': 'application/json'}, 'body': json.dumps({'error': str(exc)})}
        except InventoryShortageError as exc:
            return {'statusCode': 409, 'headers': {'Content-Type': 'application/json'}, 'body': json.dumps({'error': str(exc)})}
    query_string = event.get('queryStringParameters') or {}
    if query_string.get('demo') == 'local-json':
        return {'statusCode': 200, 'headers': {'Content-Type': 'application/json'}, 'body': json.dumps(_load_inventory())}
    factory = connection_factory or open_connection
    payload = _inventory_payload(factory)
    return {'statusCode': 200, 'headers': {'Content-Type': 'application/json'}, 'body': json.dumps(payload)}
