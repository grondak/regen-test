from __future__ import annotations

import json
import os
import tempfile
import threading
import time
import urllib.request
from pathlib import Path
from http.server import ThreadingHTTPServer
import unittest
from unittest.mock import patch

import src.http_server as http_server
import src.lambda_inventory as lambda_inventory
import src.pick_ticket_worker as pick_ticket_worker


class FakeCursor:
    def __init__(self, inventory: dict[str, dict[str, object]]):
        self.inventory = inventory
        self.rowcount = 0
        self._last = None

    def execute(self, sql: str, params=None):
        if sql.startswith("SELECT sku, description, bin_location, quantity, unit FROM inventory WHERE sku = %s FOR UPDATE"):
            sku = params[0]
            row = self.inventory.get(sku)
            self._last = None if row is None else (
                row["sku"],
                row["description"],
                row["bin_location"],
                row["quantity"],
                row["unit"],
            )
        elif sql.startswith("UPDATE inventory SET quantity = quantity - %s WHERE sku = %s AND quantity >= %s"):
            amount, sku, threshold = params
            if self.inventory[sku]["quantity"] >= threshold:
                self.inventory[sku]["quantity"] -= amount
                self.rowcount = 1
            else:
                self.rowcount = 0
        elif sql.startswith("INSERT INTO orders") or sql.startswith("INSERT INTO order_lines"):
            self.rowcount = 1
        else:
            raise AssertionError(sql)

    def fetchone(self):
        return self._last

    def close(self):
        pass


class FakeConnection:
    def __init__(self, inventory: dict[str, dict[str, object]]):
        self.inventory = inventory
        self.committed = False
        self.rolled_back = False
        self.closed = False
        self.cursors: list[FakeCursor] = []

    def cursor(self):
        cursor = FakeCursor(self.inventory)
        self.cursors.append(cursor)
        return cursor

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


class FakeSqsClient:
    def __init__(self):
        self.calls = []

    def send_message(self, **kwargs):
        self.calls.append(kwargs)
        return {"MessageId": f"msg-{len(self.calls)}"}


class FakeEventBridgeClient:
    def __init__(self):
        self.calls = []

    def put_events(self, **kwargs):
        self.calls.append(kwargs)
        return {"FailedEntryCount": 0, "Entries": [{"EventId": "evt-1"}]}


class CallbackIntegrationTests(unittest.TestCase):
    def _wait_for_http_server(self, port: int) -> None:
        deadline = time.time() + 10
        last_error: Exception | None = None
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/inventory") as response:
                    if response.status == 200:
                        return
            except Exception as exc:  # pragma: no cover - retry loop
                last_error = exc
                time.sleep(0.1)
        raise AssertionError(f"server did not start: {last_error}")

    def test_local_http_callback_proof_through_worker_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            inventory_file = tmp / "inventory.json"
            ticket_file = tmp / "pick-tickets.txt"
            state_file = tmp / "worker-state.json"
            inventory_file.write_text(
                json.dumps(
                    [
                        {
                            "sku": "SKU-1001",
                            "description": "Blue widget",
                            "bin_location": "A1-01",
                            "quantity": 3,
                            "unit": "each",
                        }
                    ],
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            order = {"order_id": "ORD-LOCAL-1", "lines": [{"sku": "SKU-1001", "quantity": 2}]}

            original_store = http_server.STORE
            original_inventory_file = http_server.INVENTORY_FILE
            original_port = http_server.PORT
            original_lambda_inventory_file = lambda_inventory.INVENTORY_FILE
            try:
                http_server.STORE = http_server.InventoryStore(inventory_file)
                http_server.INVENTORY_FILE = inventory_file
                lambda_inventory.INVENTORY_FILE = inventory_file

                fake_connection = FakeConnection(
                    {
                        "SKU-1001": {
                            "sku": "SKU-1001",
                            "description": "Blue widget",
                            "bin_location": "A1-01",
                            "quantity": 3,
                            "unit": "each",
                        }
                    }
                )
                fake_sqs = FakeSqsClient()
                fake_events = FakeEventBridgeClient()
                os.environ[lambda_inventory.PICK_WORK_QUEUE_URL_ENV] = "https://sqs.invalid/queue"
                os.environ[lambda_inventory.EVENT_BUS_NAME_ENV] = "tinywms-local-bus"

                def connection_factory():
                    return fake_connection

                http_server.PORT = 0
                server = ThreadingHTTPServer(("127.0.0.1", 0), http_server.Handler)
                port = server.server_address[1]
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    self._wait_for_http_server(port)

                    with urllib.request.urlopen(f"http://127.0.0.1:{port}/inventory") as response:
                        self.assertEqual(response.status, 200)
                        inventory_before = json.loads(response.read().decode("utf-8"))
                    self.assertEqual(inventory_before[0]["quantity"], 3)

                    request = urllib.request.Request(
                        f"http://127.0.0.1:{port}/orders",
                        data=json.dumps(order).encode("utf-8"),
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    )
                    with urllib.request.urlopen(request) as response:
                        self.assertEqual(response.status, 201)
                        order_response = json.loads(response.read().decode("utf-8"))
                    self.assertEqual(order_response, {"order_id": "ORD-LOCAL-1", "status": "accepted"})

                    with urllib.request.urlopen(f"http://127.0.0.1:{port}/inventory") as response:
                        self.assertEqual(response.status, 200)
                        inventory_after = json.loads(response.read().decode("utf-8"))
                    self.assertEqual(inventory_after[0]["quantity"], 1)

                    lambda_response = lambda_inventory.handler(
                        {"httpMethod": "POST", "body": json.dumps(order)},
                        None,
                        connection_factory=connection_factory,
                        sqs_client=fake_sqs,
                        eventbridge_client=fake_events,
                    )
                    self.assertEqual(lambda_response["statusCode"], 201)
                    self.assertEqual(json.loads(lambda_response["body"]), {"order_id": "ORD-LOCAL-1", "status": "accepted"})

                    self.assertEqual(fake_connection.inventory["SKU-1001"]["quantity"], 1)
                    self.assertTrue(fake_connection.committed)
                    self.assertFalse(fake_connection.rolled_back)
                    self.assertTrue(fake_connection.closed)
                    self.assertEqual(len(fake_sqs.calls), 1)
                    self.assertEqual(len(fake_events.calls), 1)

                    command_payload = json.loads(fake_sqs.calls[0]["MessageBody"])
                    self.assertEqual(command_payload["command_id"], "pick-work:ORD-LOCAL-1:SKU-1001:2:A1-01")
                    self.assertEqual(command_payload["order_id"], "ORD-LOCAL-1")
                    self.assertEqual(command_payload["sku"], "SKU-1001")
                    self.assertEqual(command_payload["quantity"], 2)
                    self.assertEqual(command_payload["bin"], "A1-01")
                    self.assertEqual(command_payload["description"], "Blue widget")

                    self.assertEqual(fake_events.calls[0]["Entries"][0]["Source"], "tinywms.orders")
                    self.assertEqual(fake_events.calls[0]["Entries"][0]["DetailType"], "OrderPlaced")
                    self.assertEqual(
                        json.loads(fake_events.calls[0]["Entries"][0]["Detail"]),
                        {"version": 1, "order_id": "ORD-LOCAL-1", "lines": [{"sku": "SKU-1001", "quantity": 2}]},
                    )

                    work = json.loads(fake_sqs.calls[0]["MessageBody"])
                    with patch.object(
                        pick_ticket_worker,
                        "consume_messages",
                        side_effect=lambda queue_url, callback, **kwargs: callback(work, object()) or 1,
                    ):
                        exit_code = pick_ticket_worker.main(
                            [
                                "pick_ticket_worker.py",
                                "queue-url",
                                str(ticket_file),
                                "--state-file",
                                str(state_file),
                                "--once",
                            ]
                        )
                    self.assertEqual(exit_code, 0)
                    self.assertTrue(ticket_file.exists())
                    ticket_text = ticket_file.read_text(encoding="utf-8")
                    self.assertIn("command_id=pick-work:ORD-LOCAL-1:SKU-1001:2:A1-01", ticket_text)
                    self.assertIn("order_id=ORD-LOCAL-1", ticket_text)
                    self.assertIn("sku=SKU-1001", ticket_text)
                    self.assertIn("quantity=2", ticket_text)
                    self.assertIn("bin=A1-01", ticket_text)
                finally:
                    server.shutdown()
                    thread.join(timeout=5)
            finally:
                http_server.STORE = original_store
                http_server.INVENTORY_FILE = original_inventory_file
                http_server.PORT = original_port
                lambda_inventory.INVENTORY_FILE = original_lambda_inventory_file
                os.environ.pop(lambda_inventory.PICK_WORK_QUEUE_URL_ENV, None)
                os.environ.pop(lambda_inventory.EVENT_BUS_NAME_ENV, None)


if __name__ == "__main__":
    unittest.main()
