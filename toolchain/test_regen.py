import ast
import json
import re
import tempfile
import unittest
from http.client import RemoteDisconnected
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from toolchain.regen import (
    HANDOFF_NOTES_PATH,
    MANIFEST_NAME,
    MAX_HANDOFF_NOTES_BYTES,
    REQUIRED_AWS_ARTIFACTS_BY_STAGE,
    _apply_stage_file_overlay,
    _adapt_order_handler_for_sqlite,
    _callback_invokes_worker_consumption,
    _consolidated_deployment_wiring_issues,
    _cached_stage_delta_plan,
    _deployability_audit_issues,
    _execute_snapshot_tests,
    _forward_behavior_generation_contract,
    _forward_reference_context_exclusions,
    _forward_continuity_overlay,
    _forward_reference_overlay,
    _forward_reference_snapshot,
    _project_reference_lambda_handler,
    _project_prepublisher_concurrency_test,
    _project_stage13_lambda_handler,
    _validate_focused_reference_group,
    _deployment_test_literal_issues,
    _has_behavioral_boto_client_tests,
    _browser_refreshes_inventory_after_order,
    _has_integrated_order_form,
    _has_send_message_inside_loop,
    _has_sqlite_persistence_proof,
    _has_worker_behavior_tests,
    _worker_has_durable_idempotency_state,
    _handler_normalizes_tuple_inventory_row,
    _handler_reads_dict_bin_location,
    _local_http_body_expects_lambda_envelope,
    _normalize_student_exercise_section,
    _normalize_deployment_wiring_test,
    _normalize_unittest_discovery_source,
    _normalize_forward_teaching_continuity,
    _repair_stable_reference_artifacts,
    _validate_forward_checkpoint,
    _validate_cross_stage_test_continuity,
    _validate_python_syntax,
    _reference_generation_context,
    _scratch_reference_missing_aws_overlay,
    _load_scratch_reference_cache,
    _save_scratch_reference_cache,
    _repair_reference_behavior_groups,
    _preserve_inherited_stage_files,
    _preserve_inherited_paths_from_deletion,
    _publisher_injection_issues,
    _relational_teaching_issues,
    _reference_seed_repair_overlay,
    _response_text,
    _serialize_handoff_notes,
    _sqs_publish_follows_transaction,
    _unittest_case_methods,
    _validate_behavior_continuity,
    _validate_concurrency_demo,
    _validate_test_portability,
    _validate_operations_teaching,
    _validate_student_exercises,
    _validate_web_node_test,
    _worker_uses_sqs_receive_delete,
    build_generation_input,
    build_output_schema,
    discover_prompt_files,
    find_resume_index,
    generate_app,
    generate_all_apps,
    generate_course_forward,
    generate_projects,
    load_generated_snapshot,
    request_plan,
    validate_plan,
)

ROOT = Path(__file__).resolve().parent.parent


class RegenTests(unittest.TestCase):
    def stage_readme(self, stage_name: str, files: list[str]) -> str:
        file_lines = "\n".join(f"- `{path}` - referenced by this stage." for path in files)
        return (
            f"# TinyWMS lesson: {stage_name}\n\n"
            "## Stage purpose\n"
            "Teach one small concept.\n\n"
            "## Files in this lesson\n"
            f"{file_lines}\n\n"
            "## Run the lesson\n"
            "```bash\n"
            "echo run\n"
            "```\n\n"
            "## Run tests\n"
            "```bash\n"
            "python3 -m unittest discover -s tests -v\n"
            "```\n\n"
            "## Student exercises\n"
            "1. Edit one file.\n"
            "2. Rerun tests.\n\n"
            "## Continuity note\n"
            "- Inherited contract: unchanged.\n"
            "- Boundary changed in this stage: one added behavior.\n\n"
            "## Component assembly update\n"
            "- Added: one file.\n"
            "- Reused unchanged: previous files.\n"
            "- Replaced/evolved: none.\n\n"
            "## Cleanup\n"
            "No external resources are created in this stage.\n"
        )

    def valid_behavior_snapshot(self) -> dict[str, str]:
        """Small source-shaped fixture satisfying the cumulative Stage 20 behavior audit."""
        return {
            "README.md": (
                "# TinyWMS lesson: 20-final-walkthrough\n\n"
                "## Run tests\n```bash\nnode --test tests/test_web_app.js\n```\n\n"
                "## Student exercises\n"
                "1. Submit an order and inspect the returned JSON.\n"
                "2. Change a quantity and inspect the refreshed inventory table.\n"
            ),
            "src/lambda_inventory.py": (
                "import json\nimport os\nimport psycopg\nimport boto3\n"
                "from src.db_adapter import open_connection\n"
                "DB_BACKEND = os.getenv('TINYWMS_DB', 'postgres')\n"
                "DB_PATH = os.getenv('TINYWMS_SQLITE_PATH', 'data/tinywms.db')\n"
                "SELECT_INVENTORY = 'SELECT sku, description, bin_location, quantity, unit FROM inventory FOR UPDATE'\n"
                "INSERT_ORDER = 'INSERT INTO orders VALUES (1)'\n"
                "INSERT_LINES = 'INSERT INTO order_lines VALUES (1)'\n"
                "ATOMIC = 'UPDATE inventory SET quantity = quantity - 1 WHERE quantity >= 1'\n"
                "def place_order(connection, order, rows, sqs_client=None, events_client=None):\n"
                "    if sqs_client is None: sqs_client = boto3.client('sqs')\n"
                "    if events_client is None: events_client = boto3.client('events')\n"
                "    connection.commit()\n"
                "    for line in order.lines:\n"
                "        row = rows[line.sku]\n"
                "        bin_location = row.get('bin_location') if hasattr(row, 'get') else row[2]\n"
                "        command = {'command_id': order.order_id + ':' + line.sku, "
                "'description': row['description'], 'bin': bin_location}\n"
                "        sqs_client.send_message(QueueUrl='resolved', MessageBody=json.dumps(command))\n"
                "    events_client.put_events(Entries=[{'DetailType': 'OrderPlaced'}])\n"
                "    connection.rollback()\n"
            ),
            "src/web/index.html": "<form id='order-form'></form><table id='inventory'></table>\n",
            "src/web/app.js": (
                "const apiBase = window.TINYWMS_API_BASE || '';\n"
                "function loadInventory() { return fetch(`${apiBase}/inventory`); }\n"
                "async function submitOrder() {\n"
                "  await fetch(`${apiBase}/orders`, {method: 'POST'});\n"
                "  return loadInventory();\n"
                "}\n"
                "loadInventory();\n"
            ),
            "src/http_server.py": (
                "TINYWMS_PORT = 0\nprint('listening', flush=True)\n"
                "class Handler:\n"
                "    def do_GET(self):\n"
                "        path = '/inventory'; assets = ('index.html', 'app.js')\n"
                "    def do_POST(self):\n"
                "        path = '/orders'\n"
            ),
            "tests/test_http_order_flow.py": "# GET /inventory POST /orders quantity\n",
            "tests/test_web_app.js": (
                "const test = require('node:test');\n"
                "const fs = require('node:fs');\n"
                "test('app.js keeps the order flow visible', () => {\n"
                "  const source = fs.readFileSync('src/web/app.js', 'utf8');\n"
                "  if (!source.includes('/orders')) throw new Error('missing order path');\n"
                "});\n"
            ),
            "data/schema.sql": (
                "CREATE TABLE inventory (\n"
                "  sku TEXT PRIMARY KEY, description TEXT NOT NULL,\n"
                "  bin_location TEXT NOT NULL, quantity INTEGER NOT NULL CHECK (quantity >= 0),\n"
                "  unit TEXT NOT NULL\n"
                ");\n"
                "CREATE TABLE orders (order_id TEXT PRIMARY KEY, status TEXT NOT NULL);\n"
                "CREATE TABLE order_lines (\n"
                "  order_id TEXT NOT NULL REFERENCES orders(order_id),\n"
                "  sku TEXT NOT NULL REFERENCES inventory(sku),\n"
                "  quantity INTEGER NOT NULL CHECK (quantity > 0)\n"
                ");\n"
            ),
            "data/seed.sql": (
                "INSERT INTO inventory (sku, description, bin_location, quantity, unit) "
                "VALUES ('WIDGET', 'Widget', 'A1-01', 5, 'each');\n"
            ),
            "src/db_adapter.py": (
                "import os\nimport sqlite3\n"
                "def adapt_sql(sql):\n"
                "    return sql.replace(' FOR UPDATE', '').replace('%s', '?')\n"
                "def open_connection():\n"
                "    backend = os.getenv('TINYWMS_DB', 'postgres')\n"
                "    if backend == 'sqlite':\n"
                "        connection = sqlite3.connect(os.getenv('TINYWMS_SQLITE_PATH', 'data/tinywms.db'))\n"
                "        connection.execute('PRAGMA foreign_keys = ON')\n"
                "        return connection\n"
                "    import psycopg\n"
                "    return psycopg.connect(os.environ['DATABASE_URL'])\n"
            ),
            "data/init_db.py": (
                "# Initialize schema.sql and seed.sql for sqlite or postgres.\n"
                "from pathlib import Path\n"
                "from src.db_adapter import open_connection\n"
                "def init_db():\n"
                "    connection = open_connection()\n"
                "    schema = Path('data/schema.sql').read_text()\n"
                "    seed = Path('data/seed.sql').read_text()\n"
                "    connection.executescript(schema + seed)\n"
                "    connection.commit()\n"
                "def main(): init_db()\n"
            ),
            "tests/test_sqlite_orders.py": (
                "import sqlite3\nimport tempfile\nimport unittest\nfrom pathlib import Path\n"
                "from data.init_db import init_db\n"
                "from src.db_adapter import open_connection\n"
                "from src.lambda_inventory import place_order\n"
                "TINYWMS_DB = 'sqlite'\nTINYWMS_SQLITE_PATH = 'temporary'\n"
                "SCHEMA = Path('data/schema.sql').read_text()\n"
                "QUERY = 'SELECT * FROM orders JOIN inventory ON 1 = 1'\n"
                "class SQLiteOrderTests(unittest.TestCase):\n"
                "    def test_accepted_order_persists_rows(self): self.assertTrue(SCHEMA and QUERY and init_db and open_connection)\n"
                "    def test_insufficient_inventory_rolls_back(self): self.assertTrue(sqlite3 and tempfile)\n"
                "    def test_unknown_sku_rolls_back(self): self.assertTrue(place_order)\n"
            ),
            "tests/test_concurrency.py": "from threading import Thread, Barrier\nBarrier(2)\n",
            "src/sqs_consumer.py": (
                "def consume_messages(client, queue, callback):\n"
                "    response = client.receive_message(QueueUrl=queue, WaitTimeSeconds=20)\n"
                "    for message in response['Messages']:\n"
                "        callback(message)\n"
                "        client.delete_message(QueueUrl=queue, ReceiptHandle=message['ReceiptHandle'])\n"
            ),
            "tests/test_sqs_consumer.py": (
                "class FakeClient:\n"
                "    def receive_message(self): pass\n"
                "    def delete_message(self): pass\n"
                "def test_success_deletes_message(): pass\n"
                "def test_callback_failure_does_not_delete(): pass\n"
                "def test_processes_each_message(): pass\n"
            ),
            "infra/events.yaml": (
                "AQueue:\n  Type: AWS::SQS::Queue\n"
                "BQueue:\n  Type: AWS::SQS::Queue\n"
                "ARule:\n  Type: AWS::Events::Rule\n  Targets:\n    - Arn: a\n"
                "BRule:\n  Type: AWS::Events::Rule\n  Targets:\n    - Arn: b\n"
                "Policy:\n  Type: AWS::SQS::QueuePolicy\n"
            ),
            "src/event_consumer_a.py": (
                "import json\ndef consume(client):\n"
                "    return json.loads(client.receive_message(QueueUrl='a')['Messages'][0]['Body'])\n"
            ),
            "src/event_consumer_b.py": (
                "import json\ndef consume(client):\n"
                "    return json.loads(client.receive_message(QueueUrl='b')['Messages'][0]['Body'])\n"
            ),
            "tests/test_event_consumers.py": "# consumer_a consumer_b receive_message\n",
            "src/pick_ticket_worker.py": (
                "import signal\nimport sqlite3\nsignal.signal(signal.SIGTERM, lambda *_: None)\n"
                "def run(client, idempotency_path, once=False):\n"
                "    state = sqlite3.connect(idempotency_path)\n"
                "    state.execute('CREATE TABLE IF NOT EXISTS processed_commands (command_id TEXT PRIMARY KEY)')\n"
                "    while True:\n"
                "        response = client.receive_message(WaitTimeSeconds=20)\n"
                "        for message in response['Messages']:\n"
                "            command_id = message['command_id']\n"
                "            seen = state.execute('SELECT command_id FROM processed_commands WHERE command_id = ?', (command_id,)).fetchone()\n"
                "            if not seen: state.execute('INSERT INTO processed_commands(command_id) VALUES (?)', (command_id,))\n"
                "            state.commit()\n"
                "            client.delete_message(ReceiptHandle=message['ReceiptHandle'])\n"
                "        if once: break\n"
                "# --once\n"
            ),
            "tests/test_pick_ticket_worker.py": (
                "def test_multiple_messages_are_acknowledged(): pass\n"
                "def test_duplicate_delivery_is_suppressed(): pass\n"
                "def test_duplicate_after_restart_is_suppressed(): pass\n"
                "def test_failure_does_not_delete(): pass\n"
                "def test_empty_poll_continues():\n"
                "    stop_flag = {'stop': False}\n"
                "    def run_worker(_config, *, stop_flag): stop_flag['stop'] = True\n"
                "    run_worker(None, stop_flag=stop_flag)\n"
                "    assert stop_flag['stop']\n"
                "def test_once_is_bounded(): pass\n"
            ),
            "deploy/pick-ticket-worker/tinywms-pick-ticket-worker.service.in": (
                "[Unit]\nDescription=TinyWMS pick-ticket worker\n"
                "[Service]\nEnvironmentFile=%h/.config/tinywms/worker.env\n"
                "ExecStart=python3 src/pick_ticket_worker.py\nRestart=on-failure\n"
                "[Install]\nWantedBy=default.target\n"
            ),
            "deploy/pick-ticket-worker/install_user_service.sh": (
                "#!/usr/bin/env bash\nsystemctl --user daemon-reload\n"
                "systemctl --user enable tinywms-pick-ticket-worker\n"
            ),
            "deploy/pick-ticket-worker/environment.example": "PICK_WORK_QUEUE_URL=https://queue.example\n",
            "deploy/pick-ticket-worker/README.md": (
                "systemctl --user start tinywms-pick-ticket-worker\n"
                "journalctl --user -u tinywms-pick-ticket-worker -f\n"
                "tail -f data/pick-tickets.txt\n"
            ),
            "tests/test_callback_integration.py": (
                "from src.sqs_consumer import consume_messages\n"
                "# urlopen patch inventory /inventory /orders quantity command_id pick-tickets lambda_inventory\n"
                "def test_callback():\n"
                "    if False: consume_messages(None, None)\n"
            ),
            "tests/test_end_to_end_walkthrough.py": (
                "from pathlib import Path\n"
                "text = Path('docs/end-to-end.md').read_text()\n"
                "for boundary in ('browser', 'API Gateway', 'Lambda', 'RDS', 'SQS', 'EventBridge', 'pick-ticket'):\n"
                "    assert boundary in text\n"
            ),
            "src/Dockerfile": (
                "FROM python:3.12-slim\nENTRYPOINT [\"python3\", \"pick_ticket_worker.py\"]\n"
            ),
            "deploy/container-worker/README.md": (
                "docker run --mount type=bind,src=$PWD/data/pick-tickets.txt,dst=/data/pick-tickets.txt "
                "--mount type=bind,src=$PWD/data/processed,dst=/data/processed "
                "-e PICK_WORK_QUEUE_URL tinywms-worker\n"
                "docker run -e PICK_WORK_QUEUE_URL tinywms-worker --once\n"
            ),
            "infra/template.yaml": (
                "Resources:\n"
                "  Function:\n    Type: AWS::Lambda::Function\n    Properties:\n"
                "      Handler: lambda_inventory.handler\n"
                "      Role: !GetAtt FunctionRole.Arn\n"
                "      Environment:\n        Variables:\n"
                "          DATABASE_URL: value\n          PICK_WORK_QUEUE_URL: !Ref PickWorkQueue\n"
                "          EVENT_BUS_NAME: !Ref EventBus\n"
                "      Code:\n        S3Bucket: bucket\n        S3Key: key\n"
                "  FunctionRole:\n    Type: AWS::IAM::Role\n    Properties:\n"
                "      AssumeRolePolicyDocument: {}\n"
                "      Policies:\n        - PolicyName: publish\n          PolicyDocument:\n"
                "            Statement:\n              - Action: [sqs:SendMessage, events:PutEvents]\n"
                "  PickWorkQueue:\n    Type: AWS::SQS::Queue\n"
                "  ConsumerAQueue:\n    Type: AWS::SQS::Queue\n"
                "  ConsumerBQueue:\n    Type: AWS::SQS::Queue\n"
                "  EventBus:\n    Type: AWS::Events::EventBus\n"
                "  RuleA:\n    Type: AWS::Events::Rule\n    Properties:\n"
                "      EventPattern:\n        detail-type: [OrderPlaced]\n"
                "      Targets:\n        - Arn: a\n"
                "  RuleB:\n    Type: AWS::Events::Rule\n    Properties:\n"
                "      EventPattern:\n        detail-type: [OrderPlaced]\n"
                "      Targets:\n        - Arn: b\n"
                "  PolicyA:\n    Type: AWS::SQS::QueuePolicy\n"
                "  PolicyB:\n    Type: AWS::SQS::QueuePolicy\n"
                "  Database:\n    Type: AWS::RDS::DBInstance\n    Properties:\n      Engine: postgres\n"
            ),
            "deploy/aws/README.md": (
                "aws s3 cp lambda.zip s3://$BUCKET/lambda.zip\n"
                "aws cloudformation deploy --capabilities CAPABILITY_IAM\n"
            ),
            "deploy/aws/package_lambda.sh": (
                'cp src/lambda_inventory.py "$BUILD_DIR/"\n'
                'cp src/db_adapter.py "$BUILD_DIR/"\n'
            ),
            "docs/end-to-end.md": "browser API Gateway Lambda RDS SQS EventBridge pick-ticket\n",
            "docs/architecture.md": (
                "SQLite is the local adapter. PostgreSQL demonstrates concurrency with FOR UPDATE row locks; "
                "SQLite cannot demonstrate that row-lock behavior.\n"
            ),
            "docs/data-contracts.md": "Inventory uses bin_location in SQL and bin in pick-work JSON.\n",
            "docs/git-history.md": "Compare adjacent stage directories with git diff --no-index.\n",
            "docs/demo-runbook.md": (
                "\n".join(f"## Session {number}\nStage {number - 1}." for number in range(1, 27))
                + "\nManual only\nPartly manual\nTINYWMS_DB=sqlite\n"
                "systemctl --user status tinywms-pick-ticket-worker\n"
                "docker run tinywms-worker --once\npick-ticket\n"
            ),
            "tests/test_demo_runbook.py": (
                "from pathlib import Path\n"
                "text = Path('docs/demo-runbook.md').read_text()\n"
                "for number in range(1, 27):\n"
                "    assert f'## Session {number}' in text\n"
            ),
            "tests/test_deployment_wiring.py": (
                "# DATABASE_URL PICK_WORK_QUEUE_URL EVENT_BUS_NAME "
                "sqs:SendMessage events:PutEvents\n"
                "# patch boto3 _sqs_client _eventbridge_client fake.calls assert_called\n"
            ),
        }

    def make_course(self, root: Path) -> Path:
        prompt_dir = root / "prompts"
        prompt_dir.mkdir()
        (root / "AGENTS.md").write_text("Teach with visible JSON.\n", encoding="utf-8")
        (prompt_dir / "00-repository.md").write_text("Establish the repository.\n", encoding="utf-8")
        (prompt_dir / "01-json.md").write_text("Add the JSON backbone.\n", encoding="utf-8")
        (prompt_dir / "00-repository-implementation.md").write_text(
            "This archived contract must not be discovered.\n", encoding="utf-8"
        )
        return prompt_dir

    def test_stage10_forward_contract_requires_a_real_rds_lambda_delta(self):
        contract = _forward_behavior_generation_contract("10-lambda-rds")

        self.assertIn("src/lambda_inventory.py", contract)
        self.assertIn("tests/test_lambda_inventory.py", contract)
        self.assertIn("execute SELECT against inventory", contract)
        self.assertIn("omit the order, SQS, and EventBridge behavior", contract)

    def test_stage13_forward_contract_requires_the_queue_publisher_delta(self):
        contract = _forward_behavior_generation_contract("13-sqs")

        self.assertIn("Mandatory delta paths are src/lambda_inventory.py", contract)
        self.assertIn("place_order(connection, order, sqs_client=None)", contract)
        self.assertIn("After the transaction context has exited and committed", contract)
        self.assertIn("do not add EventBridge until Stage 14", contract)
        self.assertIn("Stage 13 projection", contract)

    def test_stage13_reference_context_withholds_mature_publisher_tests(self):
        excluded = _forward_reference_context_exclusions("13-sqs")

        self.assertNotIn("src/lambda_inventory.py", excluded)
        self.assertNotIn("tests/test_lambda_inventory.py", excluded)
        self.assertIn("tests/test_orders.py", excluded)
        self.assertNotIn("tests/test_concurrency.py", excluded)
        self.assertNotIn("src/sqs_consumer.py", excluded)

    def test_stage13_reference_handler_is_projected_without_eventbridge(self):
        source = (
            "EVENT_BUS_NAME_ENV = 'EVENT_BUS_NAME'\n"
            "class InventoryShortageError(Exception): pass\n"
            "def _build_order_placed_event(order): return {}\n"
            "def _sqs_client(client=None): return client\n"
            "def _eventbridge_client(client=None): return client\n"
            "def place_order(connection, order, sqs_client=None, eventbridge_client=None):\n"
            "    connection.commit()\n"
            "    sqs = _sqs_client(sqs_client)\n"
            "    eventbridge = _eventbridge_client(eventbridge_client)\n"
            "    queue_url = ''\n"
            "    bus_name = 'course'\n"
            "    for command in order.lines:\n"
            "        sqs.send_message(MessageBody=str(command))\n"
            "    eventbridge.put_events(Entries=[_build_order_placed_event(order)])\n"
            "def handler(event, context, eventbridge_client=None):\n"
            "    return place_order(None, event, eventbridge_client=eventbridge_client)\n"
        )

        projected = _project_stage13_lambda_handler(source)
        snapshot = _forward_reference_snapshot(
            "13-sqs",
            {
                "src/lambda_inventory.py": source,
                "tests/test_lambda_inventory.py": "def test_ok(): pass\n",
                "tests/test_concurrency.py": "def test_ok(): pass\n",
                "tests/test_sqlite_orders.py": "def test_ok(): pass\n",
            },
        )

        ast.parse(projected)
        self.assertIn("send_message", projected)
        self.assertIn("InventoryLookupError = InventoryShortageError", projected)
        self.assertIn("def _cursor_for_connection(connection):", projected)
        self.assertIn("if sqs_client is not None or queue_url:", projected)
        self.assertNotIn("eventbridge", projected.lower())
        self.assertNotIn("EVENT_BUS_NAME", projected)
        self.assertEqual(snapshot["src/lambda_inventory.py"], projected)

    def test_stage14_reference_handler_keeps_eventbridge_behind_visible_configuration(self):
        source = (
            "EVENT_BUS_NAME_ENV = 'EVENT_BUS_NAME'\n"
            "class InventoryShortageError(Exception): pass\n"
            "def _sqs_client(client=None): return client\n"
            "def _eventbridge_client(client=None): return client\n"
            "def _build_order_placed_event(order): return {}\n"
            "def place_order(connection, order, sqs_client=None, eventbridge_client=None):\n"
            "    connection.commit()\n"
            "    sqs = _sqs_client(sqs_client)\n"
            "    eventbridge = _eventbridge_client(eventbridge_client)\n"
            "    queue_url = ''\n"
            "    bus_name = ''\n"
            "    for command in order.lines:\n"
            "        sqs.send_message(MessageBody=str(command))\n"
            "    eventbridge.put_events(Entries=[_build_order_placed_event(order)])\n"
        )

        projected = _project_reference_lambda_handler(source, include_eventbridge=True)

        ast.parse(projected)
        self.assertIn("if sqs_client is not None or queue_url:", projected)
        self.assertIn("if eventbridge_client is not None or bus_name:", projected)
        self.assertIn("put_events", projected)

    def test_relational_teaching_contract_is_stage_aware(self):
        snapshot = self.valid_behavior_snapshot()

        self.assertEqual(_relational_teaching_issues("20-final-walkthrough", snapshot), [])
        early_snapshot = dict(snapshot)
        early_snapshot["data/schema.sql"] = early_snapshot["data/schema.sql"].split(
            "CREATE TABLE orders", 1
        )[0]
        self.assertFalse(
            any("orders" in issue for issue in _relational_teaching_issues("08-relational-persistence", early_snapshot))
        )
        with_orders = _relational_teaching_issues("08-relational-persistence", snapshot)
        self.assertIn("order tables appear before the Stage 11 orders lesson", with_orders)

        name_drift = dict(snapshot)
        for path in ("data/schema.sql", "data/seed.sql", "src/lambda_inventory.py"):
            name_drift[path] = name_drift[path].replace("description", "name")
        drift_issues = _relational_teaching_issues("20-final-walkthrough", name_drift)
        self.assertTrue(any("inventory.description" in issue for issue in drift_issues))
        self.assertTrue(any("canonical inventory fields" in issue for issue in drift_issues))

    def test_inventory_row_normalization_accepts_helpers_and_non_row_variable_names(self):
        helper_source = (
            "def field(record, name, index):\n"
            "    if hasattr(record, 'keys'):\n"
            "        return record[name]\n"
            "    return record[index]\n"
            "bin_location = field(record, 'bin_location', 2)\n"
        )
        indexed_source = (
            "bin_location = inventory_record['bin_location']\n"
            "tuple_bin = inventory_record[2]\n"
        )

        self.assertTrue(_handler_reads_dict_bin_location(helper_source))
        self.assertTrue(_handler_normalizes_tuple_inventory_row(helper_source))
        self.assertTrue(_handler_reads_dict_bin_location(indexed_source))
        self.assertTrue(_handler_normalizes_tuple_inventory_row(indexed_source))

    def test_unittest_discovery_requires_testcase_methods_not_top_level_functions(self):
        pytest_style = "def test_accepted_order_persists_rows():\n    assert True\n"
        unittest_style = (
            "import unittest\n"
            "class SQLiteOrderTests(unittest.TestCase):\n"
            "    def test_accepted_order_persists_rows(self):\n"
            "        self.assertTrue(True)\n"
        )

        self.assertEqual(_unittest_case_methods(pytest_style), set())
        self.assertEqual(
            _unittest_case_methods(unittest_style),
            {"test_accepted_order_persists_rows"},
        )

    def test_top_level_generated_tests_are_normalized_for_unittest_discovery(self):
        source = (
            "HELPER = 3\n"
            "def test_first_behavior():\n"
            "    assert HELPER == 3\n"
            "def helper():\n"
            "    return 'kept at module scope'\n"
            "def test_second_behavior():\n"
            "    assert helper()\n"
        )

        normalized = _normalize_unittest_discovery_source(source)

        self.assertEqual(
            _unittest_case_methods(normalized),
            {"test_first_behavior", "test_second_behavior"},
        )
        self.assertIn("def helper():", normalized)
        self.assertEqual(_normalize_unittest_discovery_source(normalized), normalized)

    def test_relational_focused_repairs_have_independent_implementation_and_proof_gates(self):
        snapshot = self.valid_behavior_snapshot()

        _validate_focused_reference_group(
            "portable relational schema and row normalization",
            snapshot,
        )
        _validate_focused_reference_group(
            "real SQLite order persistence and rollback proof",
            snapshot,
        )

        broken_test = dict(snapshot)
        broken_test["tests/test_sqlite_orders.py"] = "def test_placeholder(): pass\n"
        _validate_focused_reference_group(
            "portable relational schema and row normalization",
            broken_test,
        )
        with self.assertRaisesRegex(ValueError, "tests/test_sqlite_orders.py"):
            _validate_focused_reference_group(
                "real SQLite order persistence and rollback proof",
                broken_test,
            )

    def test_web_and_operations_teaching_contracts_accept_the_final_fixture(self):
        snapshot = self.valid_behavior_snapshot()

        _validate_web_node_test("20-final-walkthrough", snapshot)
        _validate_student_exercises("20-final-walkthrough", snapshot)
        _validate_operations_teaching("20-final-walkthrough", snapshot)

    def test_walkthrough_proof_accepts_pathlib_path_assembly(self):
        snapshot = self.valid_behavior_snapshot()
        snapshot["tests/test_end_to_end_walkthrough.py"] = snapshot[
            "tests/test_end_to_end_walkthrough.py"
        ].replace(
            "Path('docs/end-to-end.md')",
            "(Path(__file__).parents[1] / 'docs' / 'end-to-end.md')",
        )

        _validate_focused_reference_group("final executable walkthrough proof", snapshot)

    def test_student_exercises_must_observe_behavior_before_tests(self):
        snapshot = self.valid_behavior_snapshot()
        snapshot["README.md"] = snapshot["README.md"].replace(
            "1. Submit an order and inspect the returned JSON.",
            "1. Change the handler and rerun tests.",
        )

        with self.assertRaisesRegex(ValueError, "visible behavior"):
            _validate_student_exercises("20-final-walkthrough", snapshot)

    def test_student_exercises_may_name_tests_as_an_optional_check(self):
        snapshot = self.valid_behavior_snapshot()
        snapshot["README.md"] = snapshot["README.md"].replace(
            "1. Submit an order and inspect the returned JSON.",
            "1. Submit an order, inspect the returned JSON, then optionally run tests.",
        )

        _validate_student_exercises("20-final-walkthrough", snapshot)

    def test_student_exercise_normalizer_repairs_only_test_first_wording(self):
        readme = (
            "# Lesson\n\n"
            "## Student exercises\n"
            "1. Change the queue delay, then rerun the tests.\n"
            "2. Submit a message, inspect the JSON, then optionally run tests.\n\n"
            "## Continuity note\n"
            "The JSON contract is unchanged.\n"
        )

        normalized = _normalize_student_exercise_section(readme)

        self.assertIn(
            "1. Change the queue delay, then observe the changed behavior through the lesson's "
            "visible interface, then optionally run the tests.",
            normalized,
        )
        self.assertIn(
            "2. Submit a message, inspect the JSON, then optionally run tests.",
            normalized,
        )
        self.assertTrue(normalized.endswith("The JSON contract is unchanged.\n"))

    def test_forward_teaching_normalizer_preserves_inherited_commands_and_boundary(self):
        plan = {
            "stages": [
                {
                    "name": "13-sqs",
                    "files": [
                        {"path": "README.md", "content": "## Run tests\npython3 -m unittest\n"},
                        {"path": "docs/architecture.md", "content": "# Architecture\n"},
                    ],
                }
            ]
        }

        normalized = _normalize_forward_teaching_continuity(plan, "13-sqs")
        files = {item["path"]: item["content"] for item in normalized["stages"][0]["files"]}

        self.assertIn("node --test tests/test_web_app.js", files["README.md"])
        self.assertIn(
            "SQLite cannot demonstrate the PostgreSQL row-lock lesson",
            files["docs/architecture.md"],
        )

    def test_stage11_handler_projection_uses_sqlite_adapter_without_later_publishers(self):
        source = (
            "def place_order(connection):\n"
            "    cursor = connection.cursor()\n"
            "    cursor.execute('INSERT INTO orders VALUES (%s)', ('ORD-1',))\n"
        )

        projected = _adapt_order_handler_for_sqlite(source)

        ast.parse(projected)
        self.assertIn("def _cursor_for_connection(connection):", projected)
        self.assertIn("cursor = _cursor_for_connection(connection)", projected)
        self.assertIn("SQLiteCursorAdapter", projected)
        self.assertNotIn("send_message", projected)
        self.assertNotIn("put_events", projected)

    def test_stage12_concurrency_projection_removes_future_publishers(self):
        source = (
            "class FakeSqsClient: pass\n"
            "class FakeEventBridgeClient: pass\n"
            "def test_overlap():\n"
            "    sqs = FakeSqsClient()\n"
            "    events = FakeEventBridgeClient()\n"
            "    result = place_order(connection, order, sqs_client=sqs, eventbridge_client=events)\n"
            "    assert len(sqs.calls) == 1\n"
            "    assert len(events.calls) == 1\n"
        )

        projected = _project_prepublisher_concurrency_test(source)

        ast.parse(projected)
        self.assertIn("place_order(connection, order)", projected)
        self.assertNotIn("FakeSqsClient", projected)
        self.assertNotIn("eventbridge_client", projected)

    def test_forward_continuity_overlay_evolves_inherited_stage_tests(self):
        rds = (
            "self.assertIn('self-managed Linux database operations', text)\n"
            "self.assertIn('Self-managed Linux database versus managed RDS', text)\n"
            "self.assertIn('SQLite remains the inspectable classroom path', text)\n"
            "self.assertIn('PostgreSQL remains the branch used for the managed database lesson', text)\n"
        )
        relational = (
            "def test_schema_uses_bin_location(self):\n"
            "        self.assertNotIn('orders (', schema.lower())\n"
            "        self.assertNotIn('order_lines', schema.lower())\n"
        )

        stage10 = _forward_continuity_overlay(
            "10-lambda-rds", {"tests/test_rds_deployment.py": rds}
        )
        stage11 = _forward_continuity_overlay(
            "11-orders", {"tests/test_relational_persistence.py": relational}
        )

        self.assertNotIn("self-managed Linux database operations", stage10["tests/test_rds_deployment.py"])
        evolved = stage11["tests/test_relational_persistence.py"]
        self.assertIn("test_schema_adds_order_tables", evolved)
        self.assertIn("assertIn('create table orders ('", evolved)
        self.assertNotIn("assertNotIn('orders ('", evolved)

    def test_cross_stage_continuity_rejects_stale_inherited_proofs(self):
        snapshot = {
            "tests/test_rds_deployment.py": "self-managed Linux database operations\n",
            "tests/test_relational_persistence.py": "assertNotIn('orders (', schema.lower())\n",
            "src/lambda_inventory.py": "def place_order(connection): connection.cursor()\n",
            "docs/data-contracts.md": "`bin_location` maps to the SQL `bin` column in the lesson schema.\n",
        }

        with self.assertRaisesRegex(ValueError, "cross-stage continuity") as raised:
            _validate_cross_stage_test_continuity("11-orders", snapshot)

        message = str(raised.exception)
        self.assertIn("RDS proof", message)
        self.assertIn("order tables", message)
        self.assertIn("placeholder adapter", message)
        self.assertIn("obsolete SQL bin", message)

    def test_reference_repairs_strengthen_browser_proof_and_behavior_led_runbook(self):
        repaired = _repair_stable_reference_artifacts(
            {
                "tests/test_web_app.js": "test('one check', () => {});\n",
                "docs/demo-runbook.md": "old runbook\n",
            }
        )

        web_test = repaired["tests/test_web_app.js"]
        self.assertEqual(web_test.count("test('"), 3)
        self.assertIn("await loadInventory", web_test)
        runbook = repaired["docs/demo-runbook.md"]
        self.assertEqual(len(re.findall(r"^## Session ", runbook, flags=re.M)), 26)
        self.assertIn("curl -s -H 'Content-Type: application/json'", runbook)
        self.assertNotIn("python3 -m unittest", runbook)

    def test_cached_stage_reuses_only_manifest_delta_not_stale_snapshot(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_root = Path(tmpdir)
            prompt = output_root / "13-sqs.md"
            prompt.write_text("# Stage 13\n", encoding="utf-8")
            stage_dir = output_root / "13-sqs"
            stage_dir.mkdir()
            (stage_dir / "README.md").write_text("# Queue lesson\n", encoding="utf-8")
            (stage_dir / MANIFEST_NAME).write_text(
                json.dumps(
                    {
                        "stage": "13-sqs",
                        "summary": "Queue delta",
                        "changed_files": ["README.md"],
                        "deleted_files": ["src/obsolete.py"],
                        "generated_files": ["README.md"],
                    }
                ),
                encoding="utf-8",
            )

            plan = _cached_stage_delta_plan(output_root, prompt)

        stage = plan["stages"][0]
        self.assertEqual(stage["files"], [{"path": "README.md", "content": "# Queue lesson\n"}])
        self.assertEqual(stage["delete_files"], ["src/obsolete.py"])

    def test_stage12_concurrency_demo_is_a_visible_non_test_entrypoint(self):
        snapshot = {
            "README.md": "python3 src/concurrency_demo.py\n",
            "src/concurrency_demo.py": (
                "from threading import Thread, Barrier\n"
                "from src.lambda_inventory import place_order\n"
                "gate = Barrier(2)\n"
                "print(place_order, Thread, gate)\n"
            ),
        }

        _validate_concurrency_demo("12-concurrency", snapshot)

    def test_stage18_borrows_the_deployable_reference_artifacts_exactly(self):
        reference = {
            "infra/template.yaml": "S3Bucket: lesson-bucket\nS3Key: lambda.zip\n",
            "deploy/aws/README.md": (
                "## 3) Deploy the stack\naws cloudformation deploy\n"
                "## 4) Resolve outputs\naws cloudformation describe-stacks\n"
                "## 5) Verify the API contract\ncurl /inventory\n"
                "## 7) Destroy the stack\naws cloudformation delete-stack\n"
            ),
            "deploy/aws/package_lambda.sh": "#!/usr/bin/env bash\n",
            "requirements.txt": "psycopg2-binary\n",
            "tests/test_aws_deployment_files.py": "import unittest\n",
            "tests/test_deployment_wiring.py": "import unittest\n",
            "src/lambda_inventory.py": "must not be copied by this overlay\n",
        }

        overlay = _forward_reference_overlay("18-aws-deployment", reference)

        self.assertEqual(
            set(overlay),
            {
                "infra/template.yaml",
                "deploy/aws/README.md",
                "deploy/aws/package_lambda.sh",
                "requirements.txt",
                "tests/test_aws_deployment_files.py",
                "tests/test_deployment_wiring.py",
            },
        )
        self.assertNotIn("src/lambda_inventory.py", overlay)
        deploy_guide = overlay["deploy/aws/README.md"]
        self.assertIn("## Deploy", deploy_guide)
        self.assertIn("## Resolve outputs", deploy_guide)
        self.assertIn("## Verify contracts", deploy_guide)
        self.assertIn("## Destroy", deploy_guide)
        self.assertNotIn("## 3) Deploy", deploy_guide)

    def test_stage13_borrows_the_stable_consumer_and_its_behavior_tests(self):
        reference = {
            "src/lambda_inventory.py": "projected handler\n",
            "src/sqs_consumer.py": "def consume_messages(): pass\n",
            "tests/test_lambda_inventory.py": "def test_publish(): pass\n",
            "tests/test_concurrency.py": "def test_concurrent(): pass\n",
            "tests/test_sqlite_orders.py": "def test_sqlite(): pass\n",
            "tests/test_sqs_consumer.py": "def test_receive_and_delete(): pass\n",
            "infra/sqs.yaml": "Resources: {Queue: {Type: AWS::SQS::Queue}}\n",
            "deploy/sqs/README.md": "# Deploy SQS\n",
            "src/event_consumer_a.py": "must not be borrowed yet\n",
        }

        overlay = _forward_reference_overlay("13-sqs", reference)

        self.assertEqual(
            set(overlay),
            {
                "src/lambda_inventory.py",
                "src/sqs_consumer.py",
                "tests/test_lambda_inventory.py",
                "tests/test_concurrency.py",
                "tests/test_sqlite_orders.py",
                "tests/test_sqs_consumer.py",
                "infra/sqs.yaml",
                "deploy/sqs/README.md",
            },
        )
        self.assertNotIn("src/event_consumer_a.py", overlay)

    def test_stage11_borrows_the_reference_order_form_as_a_comparison_artifact(self):
        reference = {
            "src/order_form.html": (
                "<form id='legacy-order-form'>"
                "<p>Compare this standalone request with the integrated inventory page.</p>"
                "</form>\n"
            ),
            "src/web/index.html": "<form id='order-form'></form>\n",
            "src/web/app.js": "fetch('/orders', {method: 'POST'}).then(loadInventory);\n",
            "src/web/style.css": "form { display: block; }\n",
            "src/http_server.py": "class Handler:\n    def do_POST(self): pass\n",
            "tests/test_http_order_flow.py": "# POST /orders then GET /inventory quantity\n",
            "tests/test_sqlite_orders.py": "# real SQLite order proof\n",
        }

        overlay = _forward_reference_overlay("11-orders", reference)

        self.assertEqual(overlay, reference)

    def test_stage18_preserves_prior_service_deployment_artifacts(self):
        plan = {
            "stages": [
                {
                    "name": "18-aws-deployment",
                    "summary": "consolidate deployment",
                    "files": [
                        {"path": "infra/lambda.yaml", "content": "replacement"},
                        {"path": "README.md", "content": "lesson"},
                    ],
                    "delete_files": ["deploy/lambda/README.md", "src/obsolete.py"],
                }
            ]
        }

        result = _preserve_inherited_stage_files(
            plan,
            "18-aws-deployment",
            {"infra/lambda.yaml", "deploy/lambda/README.md"},
        )

        stage = result["stages"][0]
        self.assertEqual(stage["files"], [{"path": "README.md", "content": "lesson"}])
        self.assertEqual(stage["delete_files"], ["src/obsolete.py"])

    def test_later_stage_cannot_delete_inherited_aws_artifacts_but_may_edit_them(self):
        plan = {
            "stages": [
                {
                    "name": "11-orders",
                    "summary": "add orders",
                    "files": [
                        {"path": "infra/lambda.yaml", "content": "integrated order route"},
                    ],
                    "delete_files": [
                        "infra/lambda.yaml",
                        "deploy/rds/README.md",
                        "src/obsolete.py",
                    ],
                }
            ]
        }

        result = _preserve_inherited_paths_from_deletion(
            plan,
            "11-orders",
            {"infra/lambda.yaml", "deploy/rds/README.md"},
        )

        stage = result["stages"][0]
        self.assertEqual(
            stage["files"],
            [{"path": "infra/lambda.yaml", "content": "integrated order route"}],
        )
        self.assertEqual(stage["delete_files"], ["src/obsolete.py"])

    def test_forward_checkpoint_scan_applies_test_portability(self):
        snapshot = {
            "README.md": self.stage_readme(
                "02-linux", ["README.md", "src/process_demo.py", "tests/test_process_demo.py"]
            ),
            "src/process_demo.py": "VALUE = 1\n",
            "tests/test_process_demo.py": "import process_demo\n",
            HANDOFF_NOTES_PATH: json.dumps(
                {
                    "current_stage": "02-linux",
                    "notes": [
                        {
                            "stage": "02-linux",
                            "summary": "Linux process lesson",
                            "inherited_contract": "JSON remains stable.",
                            "boundary_change": "Add a process.",
                            "components": {},
                            "continuity_checks": [],
                        }
                    ],
                }
            ),
        }

        with patch("toolchain.regen.validate_snapshot_against_blueprint"):
            with self.assertRaisesRegex(ValueError, "PYTHONPATH=src"):
                _validate_forward_checkpoint("02-linux", snapshot, {}, ["02-linux"])

    def test_forward_generation_fully_audits_the_reference_before_reuse(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prompt_dir = self.make_course(root)
            final_prompt = prompt_dir / "01-json.md"
            reference_dir = root / "reference" / "01-json"
            reference_dir.mkdir(parents=True)
            (reference_dir / "README.md").write_text("# reference\n", encoding="utf-8")
            (reference_dir / MANIFEST_NAME).write_text(
                json.dumps(
                    {
                        "stage": "01-json",
                        "source_prompt": final_prompt.name,
                        "generated_files": ["README.md"],
                    }
                ),
                encoding="utf-8",
            )

            with patch(
                "toolchain.regen._validate_materialized_stage",
                side_effect=ValueError("full reference audit"),
            ) as audit:
                with self.assertRaisesRegex(ValueError, "full reference audit"):
                    generate_course_forward(
                        prompt_dir,
                        root / "generated",
                        reference_dir,
                        api_key="test-key",
                    )

            audit.assert_called_once()

    def test_all_stages_use_one_request_and_inherit_unchanged_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prompt_dir = self.make_course(root)
            calls = []

            def fake_requester(generation_input, schema, model, api_key, base_url):
                calls.append((generation_input, schema, model, api_key, base_url))
                return {
                    "stages": [
                        {
                            "name": "00-repository",
                            "summary": "Empty teaching repository",
                            "files": [
                                {"path": "README.md", "content": "# Foundation\n"},
                                {"path": "data/.gitkeep", "content": ""},
                                {"path": "tests/.gitkeep", "content": ""},
                            ],
                            "delete_files": [],
                        },
                        {
                            "name": "01-json",
                            "summary": "Add the inventory JSON backbone",
                            "files": [
                                {"path": "src/inventory.py", "content": "import json\nprint('{}')\n"},
                                {"path": "tests/.gitkeep", "content": ""},
                                {
                                    "path": "README.md",
                                    "content": self.stage_readme(
                                        "01-json", ["README.md", "src/inventory.py", "tests/.gitkeep"]
                                    ),
                                },
                            ],
                            "delete_files": [],
                        },
                    ]
                }

            output_root = root / "generated"
            generated = generate_all_apps(
                prompt_dir,
                output_root,
                model="test-model",
                api_key="test-key",
                requester=fake_requester,
            )

            self.assertEqual(len(calls), 1)
            self.assertEqual(len(generated), 2)
            generation_input = calls[0][0]
            self.assertIn("Establish the repository.", generation_input)
            self.assertIn("Add the JSON backbone.", generation_input)
            self.assertIn("Teach with visible JSON.", generation_input)
            self.assertNotIn("archived contract", generation_input)

            second = output_root / "01-json"
            self.assertTrue((second / "tests" / ".gitkeep").exists())
            self.assertIn("import json", (second / "src" / "inventory.py").read_text(encoding="utf-8"))
            manifest = json.loads((second / MANIFEST_NAME).read_text(encoding="utf-8"))
            self.assertEqual(manifest["inherits_from"], "00-repository")
            self.assertEqual(
                manifest["changed_files"],
                ["src/inventory.py", "tests/.gitkeep", "README.md", HANDOFF_NOTES_PATH],
            )
            notes = json.loads((second / HANDOFF_NOTES_PATH).read_text(encoding="utf-8"))
            self.assertEqual(notes["current_stage"], "01-json")
            self.assertEqual(len(notes["notes"]), 2)
            self.assertEqual(notes["notes"][-1]["stage"], "01-json")

    def test_discovery_uses_only_course_prompts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            prompt_dir = self.make_course(Path(tmpdir))
            self.assertEqual(
                [path.name for path in discover_prompt_files(prompt_dir)],
                ["00-repository.md", "01-json.md"],
            )

    def test_test_portability_requires_visible_src_import_path(self):
        snapshot = {
            "README.md": "python3 -m unittest discover -s tests -v\n",
            "src/inventory.py": "def load(): return []\n",
            "tests/test_inventory.py": "import inventory\n",
        }
        with self.assertRaisesRegex(ValueError, "must set PYTHONPATH=src"):
            _validate_test_portability("01-json", snapshot)

        snapshot["README.md"] = "PYTHONPATH=src python3 -m unittest discover -s tests -v\n"
        _validate_test_portability("01-json", snapshot)

    def test_test_portability_rejects_optional_runtime_dependencies(self):
        snapshot = {
            "README.md": "python3 -m unittest discover -s tests -v\n",
            "tests/test_deployment.py": "import yaml\n",
        }

        with self.assertRaisesRegex(ValueError, r"optional runtime dependencies \['yaml'\]"):
            _validate_test_portability("18-aws-deployment", snapshot)

    def test_test_portability_rejects_imports_missing_from_generated_source(self):
        snapshot = {
            "README.md": "python3 -m unittest discover -s tests -v\n",
            "src/lambda_inventory.py": "def place_order(connection, order): return order\n",
            "tests/test_concurrency.py": (
                "from src.lambda_inventory import OrderRequest, place_order\n"
            ),
        }

        with self.assertRaisesRegex(ValueError, r"imports names \['OrderRequest'\].*does not export"):
            _validate_test_portability("12-concurrency", snapshot)

    def test_test_portability_rejects_invented_exception_prose(self):
        snapshot = {
            "README.md": "python3 -m unittest discover -s tests -v\n",
            "src/lambda_inventory.py": (
                "def parse_order(order):\n"
                "    raise ValueError('order_id must be a non-empty string')\n"
            ),
            "tests/test_lambda_inventory.py": (
                "from src.lambda_inventory import parse_order\n"
                "self.assertRaisesRegex(ValueError, 'invalid order')\n"
            ),
        }

        with self.assertRaisesRegex(ValueError, "cannot match any emitted error"):
            _validate_test_portability("11-orders", snapshot)

    def test_python_syntax_validation_reports_the_generated_path(self):
        with self.assertRaisesRegex(ValueError, r"src/broken\.py \(line 1"):
            _validate_python_syntax(
                "11-orders",
                {
                    "src/valid.py": "VALUE = 1\n",
                    "src/broken.py": "@dataclass = None\n",
                },
            )

    def test_test_portability_rejects_obsolete_root_readme_assertions(self):
        snapshot = {
            "README.md": "PYTHONPATH=src python3 -m unittest discover -s tests -v\n",
            "tests/test_history.py": (
                "from pathlib import Path\n"
                "text = Path('README.md').read_text(encoding='utf-8')\n"
            ),
        }
        with self.assertRaisesRegex(ValueError, "changing root README"):
            _validate_test_portability("20-final", snapshot)

        snapshot["tests/test_history.py"] = (
            "from pathlib import Path\n"
            "ROOT = Path(__file__).resolve().parents[1]\n"
            "README = ROOT / 'README.md'\n"
            "text = README.read_text(encoding='utf-8')\n"
        )
        with self.assertRaisesRegex(ValueError, "changing root README"):
            _validate_test_portability("17-container-worker", snapshot)

        snapshot["tests/test_history.py"] = (
            "from pathlib import Path\n"
            "ROOT = Path(__file__).resolve().parents[1]\n"
            "text = (ROOT / 'deploy' / 'aws' / 'README.md').read_text(encoding='utf-8')\n"
        )
        _validate_test_portability("20-final-walkthrough", snapshot)

    def test_test_portability_allows_tests_that_reject_placeholder_values(self):
        snapshot = {
            "tests/test_relational_persistence.py": (
                "def test_schema_has_no_placeholder_values():\n"
                "    schema = 'CREATE TABLE inventory'\n"
                "    assert 'placeholder' not in schema\n"
            ),
        }

        _validate_test_portability("08-relational-persistence", snapshot)

    def test_behavior_audit_preserves_stage10_inventory_contract_details(self):
        snapshot = {
            "src/lambda_inventory.py": (
                "import psycopg\n"
                "QUERY = 'SELECT sku, description, bin, quantity, unit FROM inventory'\n"
            ),
            "tests/test_lambda_inventory.py": (
                "payload[0]['bin_location']\n"
                "event = {'queryStringParameters': {'demo': 'local-json'}}\n"
            ),
        }

        with self.assertRaises(ValueError) as raised:
            _validate_behavior_continuity("10-lambda-rds", snapshot)
        message = str(raised.exception)
        self.assertIn("bin_location field", message)
        self.assertIn("local-json demonstration path", message)

    def test_behavior_audit_accepts_postgres_driver_delegated_to_adapter(self):
        snapshot = {
            "src/lambda_inventory.py": (
                "from src.db_adapter import open_connection\n"
                "QUERY = 'SELECT sku, description, bin_location, quantity FROM inventory'\n"
                "def handler(event, context):\n"
                "    connection = open_connection()\n"
                "    return connection.execute(QUERY).fetchall()\n"
            ),
            "src/db_adapter.py": (
                "def open_connection():\n"
                "    import psycopg\n"
                "    return psycopg.connect('postgresql://configured-at-runtime')\n"
            ),
            "tests/test_lambda_inventory.py": "",
        }

        _validate_behavior_continuity("10-lambda-rds", snapshot)

    def test_behavior_audit_rejects_opening_database_for_invalid_order(self):
        snapshot = {
            "src/lambda_inventory.py": (
                "import psycopg\n"
                "SQL = 'SELECT sku FROM inventory; INSERT INTO orders VALUES (1); "
                "INSERT INTO order_lines VALUES (1)'\n"
                "def save(connection):\n"
                "    connection.commit()\n"
                "    connection.rollback()\n"
            ),
            "tests/test_orders.py": (
                "class Tests:\n"
                "    def test_rejects_invalid_order(self):\n"
                "        self.assertTrue(connection.closed)\n"
                "\n"
                "    def test_accepts_order(self):\n"
                "        pass\n"
            ),
        }

        with self.assertRaisesRegex(ValueError, "validation must happen before"):
            _validate_behavior_continuity("11-orders", snapshot)

    def test_behavior_audit_rejects_async_publishers_before_their_lessons(self):
        snapshot = {
            "src/lambda_inventory.py": (
                "import psycopg\n"
                "SQL = 'SELECT inventory; INSERT INTO orders; INSERT INTO order_lines'\n"
                "def place(connection, sqs, events):\n"
                "    connection.commit()\n"
                "    connection.rollback()\n"
                "    sqs.send_message(MessageBody='{}')\n"
                "    events.put_events(Entries=[])\n"
            ),
        }

        with self.assertRaises(ValueError) as raised:
            _validate_behavior_continuity("11-orders", snapshot)
        message = str(raised.exception)
        self.assertIn("before the Stage 13 queue lesson", message)
        self.assertIn("before the Stage 14 domain-events lesson", message)

    def test_behavior_audit_reports_multiple_missing_cumulative_lessons(self):
        snapshot = {
            "src/lambda_inventory.py": "def lambda_handler(event, context): return {}\n",
            "tests/test_concurrency.py": "def test_insufficient_stock(): pass\n",
            "infra/template.yaml": "Code:\n  ZipFile: package the lesson code later\n",
            "deploy/aws/README.md": "## Deploy\naws cloudformation deploy\n",
            "docs/end-to-end.md": "browser to Lambda\n",
        }
        with self.assertRaises(ValueError) as raised:
            _validate_behavior_continuity("20-final-walkthrough", snapshot)
        message = str(raised.exception)
        self.assertIn("PostgreSQL driver", message)
        self.assertIn("does not run concurrent attempts", message)
        self.assertIn("put_events", message)
        self.assertIn("placeholder Lambda code", message)
        self.assertIn("does not cover the RDS boundary", message)

    def test_behavior_audit_rejects_disconnected_end_to_end_components(self):
        cases = [
            (
                "hard-coded final browser origin",
                "11-orders",
                "src/web/app.js",
                lambda text: text.replace("const apiBase = window.TINYWMS_API_BASE || '';", "const apiBase = 'http://127.0.0.1:8000';"),
                "hard-codes a local API origin",
            ),
            (
                "missing local order route",
                "11-orders",
                "src/http_server.py",
                lambda text: text.replace("def do_POST", "def post_disabled"),
                "does not implement the local POST /orders path",
            ),
            (
                "order page does not refresh inventory",
                "11-orders",
                "src/web/app.js",
                lambda text: "fetch('/orders', {method: 'POST'});\n",
                "does not refresh inventory",
            ),
            (
                "fake SQS receive",
                "13-sqs",
                "src/sqs_consumer.py",
                lambda text: text.replace(".receive_message(", ".read_local_file("),
                "does not call receive_message",
            ),
            (
                "SQS never acknowledges",
                "13-sqs",
                "src/sqs_consumer.py",
                lambda text: text.replace(".delete_message(", ".print_message("),
                "does not acknowledge success",
            ),
            (
                "first-line-only command",
                "13-sqs",
                "src/lambda_inventory.py",
                lambda text: text.replace("for line in order.lines:", "line = order.lines[0]"),
                "does not publish one pick-work command per order line",
            ),
            (
                "literal pick bin",
                "13-sqs",
                "src/lambda_inventory.py",
                lambda text: text.replace("'bin': bin_location", "'bin': 'A1-01'"),
                "hard-codes a bin",
            ),
            (
                "one EventBridge rule",
                "14-domain-events",
                "infra/events.yaml",
                lambda text: text.replace("BRule:\n  Type: AWS::Events::Rule", "BRule:\n  Type: Custom::MissingRule"),
                "does not define two independent EventBridge rules",
            ),
            (
                "event print stub",
                "14-domain-events",
                "src/event_consumer_a.py",
                lambda text: "def main(): print('bus')\n",
                "does not receive and decode delivered event JSON",
            ),
            (
                "one-shot worker",
                "15-pick-ticket-worker",
                "src/pick_ticket_worker.py",
                lambda text: text.replace("while True:", "if True:").replace("# --once", ""),
                "not a long-running worker with bounded --once mode",
            ),
            (
                "worker without idempotency",
                "15-pick-ticket-worker",
                "src/pick_ticket_worker.py",
                lambda text: text.replace("processed_command_ids", "seen").replace("command_id", "work_key"),
                "does not visibly suppress duplicate command_id",
            ),
            (
                "missing local callback proof",
                "16-callback-demo",
                "tests/test_callback_integration.py",
                lambda text: "def test_docs_only(): pass\n",
                "does not prove inventory -> order -> command -> pick-ticket",
            ),
            (
                "deployment environment mismatch",
                "18-aws-deployment",
                "infra/template.yaml",
                lambda text: text.replace("PICK_WORK_QUEUE_URL", "QUEUE_URL"),
                "does not wire the Lambda PICK_WORK_QUEUE_URL",
            ),
            (
                "missing publish permission",
                "18-aws-deployment",
                "infra/template.yaml",
                lambda text: text.replace("sqs:SendMessage", "sqs:GetQueueUrl"),
                "does not grant the Lambda sqs:SendMessage",
            ),
            (
                "Lambda package handler mismatch",
                "18-aws-deployment",
                "infra/template.yaml",
                lambda text: text.replace("Handler: lambda_inventory.handler", "Handler: src.lambda_inventory.handler"),
                "does not match the ZIP's root lambda_inventory.py",
            ),
            (
                "walkthrough invents a connection",
                "20-final-walkthrough",
                "docs/end-to-end.md",
                lambda text: text.replace("EventBridge", "event service"),
                "does not cover the EventBridge boundary",
            ),
        ]

        for label, stage, path, mutate, expected in cases:
            with self.subTest(label=label):
                snapshot = self.valid_behavior_snapshot()
                snapshot[path] = mutate(snapshot[path])
                if stage == "13-sqs":
                    snapshot["src/lambda_inventory.py"] = snapshot["src/lambda_inventory.py"].replace(
                        "    events_client.put_events(Entries=[{'DetailType': 'OrderPlaced'}])\n",
                        "",
                    )
                with self.assertRaisesRegex(ValueError, expected):
                    _validate_behavior_continuity(stage, snapshot)

    def test_behavior_audit_accepts_explicit_stdout_flush_for_server_readiness(self):
        snapshot = self.valid_behavior_snapshot()
        snapshot["src/http_server.py"] = snapshot["src/http_server.py"].replace(
            "print('listening', flush=True)",
            "print('listening')\nsys.stdout.flush()",
        )

        _validate_behavior_continuity("20-final-walkthrough", snapshot)

    def test_integrated_order_form_is_detected_by_behavior_not_dom_id(self):
        index = "<form id='placeOrder'><button>Order</button></form>"
        app = (
            "const form = document.querySelector('#placeOrder');\n"
            "form.addEventListener('submit', async event => {\n"
            "  await fetch('/orders', {method: 'POST'});\n"
            "});\n"
        )

        self.assertTrue(_has_integrated_order_form(index, app))
        self.assertFalse(_has_integrated_order_form("<main>No form</main>", app))

    def test_browser_refresh_accepts_a_named_refresh_function_after_order(self):
        app = (
            "async function refreshInventoryTable() {\n"
            "  return fetch('/inventory');\n"
            "}\n"
            "async function submitOrder() {\n"
            "  const response = await fetch('/orders', {method: 'POST'});\n"
            "  if (response.ok) await refreshInventoryTable();\n"
            "}\n"
            "refreshInventoryTable();\n"
        )

        self.assertTrue(_browser_refreshes_inventory_after_order(app))
        self.assertFalse(
            _browser_refreshes_inventory_after_order(
                "fetch('/inventory'); fetch('/orders', {method: 'POST'});\n"
            )
        )

    def test_behavior_audit_accepts_behavioral_sqs_test_names(self):
        snapshot = self.valid_behavior_snapshot()
        snapshot["tests/test_sqs_consumer.py"] = (
            "class FakeClient:\n"
            "    def receive_message(self): pass\n"
            "    def delete_message(self): pass\n"
            "def test_success_deletes_message(): pass\n"
            "def test_callback_raises_does_not_delete(): pass\n"
            "def test_processes_each_message(): pass\n"
        )

        _validate_behavior_continuity("20-final-walkthrough", snapshot)

    def test_worker_may_reuse_the_existing_sqs_consumer_boundary(self):
        worker = "from sqs_consumer import consume_messages\nconsume_messages(client, callback)\n"
        consumer = (
            "def consume_messages(client, callback):\n"
            "    client.receive_message()\n"
            "    client.delete_message()\n"
        )

        self.assertTrue(_worker_uses_sqs_receive_delete(worker, consumer))

    def test_callback_may_invoke_consumption_through_the_real_worker(self):
        callback_test = (
            "from src.pick_ticket_worker import run_worker as execute_worker\n"
            "def test_callback(): execute_worker(config)\n"
        )
        worker = (
            "from src.sqs_consumer import consume_messages\n"
            "def run_worker(config): consume_messages(config.queue_url, callback)\n"
        )
        consumer = (
            "def consume_messages(queue_url, callback):\n"
            "    client.receive_message()\n"
            "    client.delete_message()\n"
        )

        self.assertTrue(_callback_invokes_worker_consumption(callback_test, worker, consumer))
        self.assertFalse(
            _callback_invokes_worker_consumption(
                "# run_worker consume_messages\n",
                worker,
                consumer,
            )
        )

    def test_worker_durability_is_detected_from_sqlite_behavior_not_path_variable_name(self):
        sqlite_worker = (
            "import sqlite3\n"
            "def remember(db_path, command_id):\n"
            "    connection = sqlite3.connect(db_path)\n"
            "    connection.execute('SELECT command_id FROM processed_commands WHERE command_id = ?', (command_id,))\n"
            "    connection.execute('INSERT OR IGNORE INTO processed_commands(command_id) VALUES (?)', (command_id,))\n"
            "    connection.commit()\n"
        )
        memory_only_worker = (
            "processed_commands = set()\n"
            "def remember(command_id): processed_commands.add(command_id)\n"
        )
        sqlite_memory_worker = sqlite_worker.replace("sqlite3.connect(db_path)", "sqlite3.connect(':memory:')")

        self.assertTrue(_worker_has_durable_idempotency_state(sqlite_worker))
        self.assertFalse(_worker_has_durable_idempotency_state(memory_only_worker))
        self.assertFalse(_worker_has_durable_idempotency_state(sqlite_memory_worker))

    def test_worker_behavior_proof_rejects_a_service_test_that_starts_stopped(self):
        source = (
            "def test_multiple_messages_are_acknowledged(): pass\n"
            "def test_duplicate_after_restart_is_suppressed(): pass\n"
            "def test_failure_does_not_delete(): pass\n"
            "def test_empty_service_poll_continues():\n"
            "    run_worker(config, stop_flag={'stop': True})\n"
            "def test_once_is_bounded(): pass\n"
        )

        self.assertFalse(_has_worker_behavior_tests(source))
        bounded_source = source.replace(
            "    run_worker(config, stop_flag={'stop': True})",
            "    stop_flag = {'stop': False}\n"
            "    stop_flag['stop'] = True\n"
            "    run_worker(config, stop_flag=stop_flag)",
        )
        self.assertTrue(_has_worker_behavior_tests(bounded_source))

    def test_deployment_test_normalizer_uses_cloudformation_event_pattern_spelling(self):
        source = (
            "class DeploymentTest(unittest.TestCase):\n"
            "    def test_template(self):\n"
            "        self.assertIn('DetailType: \"order.placed.v1\"', template)\n"
        )
        template = "EventPattern:\n  detail-type:\n    - order.placed.v1\n"

        repaired = _normalize_deployment_wiring_test(source, template)

        self.assertNotIn("DetailType:", repaired)
        self.assertIn("self.assertIn('detail-type:', template)", repaired)
        self.assertIn("self.assertIn('order.placed.v1', template)", repaired)

    def test_snapshot_test_timeout_becomes_focused_repair_feedback(self):
        snapshot = {
            "tests/test_pick_ticket_worker.py": (
                "import time\nimport unittest\n"
                "class WorkerTests(unittest.TestCase):\n"
                "    def test_service_loop(self):\n"
                "        time.sleep(10)\n"
            )
        }

        with self.assertRaisesRegex(ValueError, "timed out.*bounded shutdown"):
            _execute_snapshot_tests(
                "15-pick-ticket-worker",
                snapshot,
                python_pattern="test_pick_ticket_worker.py",
                run_web_test=False,
                python_timeout_seconds=0.05,
            )

    def test_sqs_publish_order_check_requires_send_after_transaction(self):
        valid = (
            "def place_order(connection, order, sqs_client=None):\n"
            "    with transaction(connection):\n"
            "        save(order)\n"
            "    sqs_client.send_message(MessageBody='{}')\n"
        )
        invalid = (
            "def place_order(connection, order, sqs_client=None):\n"
            "    with transaction(connection):\n"
            "        save(order)\n"
            "        sqs_client.send_message(MessageBody='{}')\n"
        )

        self.assertTrue(_sqs_publish_follows_transaction(valid))
        self.assertFalse(_sqs_publish_follows_transaction(invalid))

    def test_per_line_publish_accepts_zip_and_enumerate_loops(self):
        source = (
            "def publish(client, lines, locked_rows):\n"
            "    for number, (line, row) in enumerate(zip(lines, locked_rows), start=1):\n"
            "        command = {'command_id': str(number), 'sku': line.sku}\n"
            "        client.send_message(MessageBody=str(command))\n"
        )

        self.assertTrue(_has_send_message_inside_loop(source))
        self.assertFalse(
            _has_send_message_inside_loop(
                "def publish(client, command):\n    client.send_message(MessageBody=str(command))\n"
            )
        )

    def test_publisher_injection_check_ignores_get_handler_calls(self):
        source = (
            "result = handler({}, None, connection_factory=lambda: connection)\n"
            "event = {'httpMethod': 'POST', 'body': '{}'}\n"
            "posted = handler(event, None, connection_factory=lambda: connection)\n"
        )

        issues = _publisher_injection_issues(source, "tests/test_lambda.py", {"sqs_client"})

        self.assertEqual(len(issues), 1)
        self.assertIn("without injected sqs_client", issues[0])

    def test_callback_envelope_check_distinguishes_local_http_from_lambda(self):
        broken = (
            "response = self._request_json('POST', '/orders')\n"
            "self.assertEqual(response['statusCode'], 201)\n"
        )
        valid = (
            "status, body = self._request_json('POST', '/orders')\n"
            "self.assertEqual(status, 201)\n"
            "lambda_response = lambda_inventory.handler(event, None)\n"
            "self.assertEqual(lambda_response['statusCode'], 201)\n"
        )

        self.assertTrue(_local_http_body_expects_lambda_envelope(broken))
        self.assertFalse(_local_http_body_expects_lambda_envelope(valid))

    def test_behavioral_boto_client_check_accepts_standard_mock_assertions(self):
        source = (
            "from unittest.mock import patch, Mock\n"
            "from src import lambda_inventory\n"
            "fake_boto3 = Mock()\n"
            "with patch.dict('sys.modules', {'boto3': fake_boto3}):\n"
            "    lambda_inventory._sqs_client()\n"
            "    lambda_inventory._eventbridge_client()\n"
            "fake_boto3.client.assert_any_call('sqs')\n"
            "fake_boto3.client.assert_any_call('events')\n"
        )

        self.assertTrue(_has_behavioral_boto_client_tests(source))

    def test_deployment_test_literals_must_match_the_template(self):
        template = "PICK_WORK_QUEUE_URL: !Ref PickWorkQueue\n"
        test_source = (
            "template = INFRA.read_text()\n"
            "self.assertIn('QueueUrl: !Ref PickWorkQueue', template)\n"
        )

        issues = _deployment_test_literal_issues(test_source, template)

        self.assertEqual(len(issues), 1)
        self.assertIn("QueueUrl: !Ref PickWorkQueue", issues[0])

    def test_deployment_test_literals_follow_the_artifact_loaded_as_text(self):
        source = (
            "template_text = (ROOT / 'infra' / 'template.yaml').read_text()\n"
            "self.assertIn('DATABASE_URL: real-value', template_text)\n"
            "text = (ROOT / 'deploy' / 'aws' / 'README.md').read_text()\n"
            "self.assertIn('GET /inventory', text)\n"
        )

        issues = _deployment_test_literal_issues(
            source,
            "DATABASE_URL: parameterized-value\n",
            'curl "$API_BASE_URL/inventory"\n',
        )

        self.assertEqual(len(issues), 2)
        self.assertIn("infra/template.yaml", issues[0])
        self.assertIn("deploy/aws/README.md", issues[1])

    def test_reference_behavior_repairs_are_split_into_focused_passes(self):
        baseline = self.valid_behavior_snapshot()
        baseline["tests/test_concurrency.py"] = "def test_serial_only(): pass\n"
        baseline["src/pick_ticket_worker.py"] = "def run_one_file(): return 0\n"
        baseline["infra/template.yaml"] = "Code:\n  ZipFile: upload code separately\n"
        valid = self.valid_behavior_snapshot()
        calls = []

        def requester(generation_input, schema, model, api_key, base_url):
            calls.append(generation_input)
            common = {
                "name": "20-final-walkthrough",
                "summary": "focused repair",
                "delete_files": [],
            }
            if "database transactions and concurrency" in generation_input:
                files = [
                    {
                        "path": "tests/test_concurrency.py",
                        "content": valid["tests/test_concurrency.py"],
                    },
                ]
            elif "long-running idempotent pick-ticket worker" in generation_input:
                files = [
                    {"path": "src/pick_ticket_worker.py", "content": valid["src/pick_ticket_worker.py"]},
                    {
                        "path": "tests/test_pick_ticket_worker.py",
                        "content": valid["tests/test_pick_ticket_worker.py"],
                    },
                ]
            else:
                files = [
                    {
                        "path": "infra/template.yaml",
                        "content": valid["infra/template.yaml"],
                    },
                    {
                        "path": "deploy/aws/README.md",
                        "content": valid["deploy/aws/README.md"],
                    },
                ]
            return {"stages": [{**common, "files": files}]}

        repaired, overlay = _repair_reference_behavior_groups(
            baseline,
            "20-final-walkthrough",
            model="test-model",
            api_token="test-key",
            base_url="https://example.test/v1",
            requester=requester,
        )

        self.assertEqual(len(calls), 3)
        self.assertIn("Barrier", repaired["tests/test_concurrency.py"])
        self.assertIn("--once", repaired["src/pick_ticket_worker.py"])
        self.assertIn("S3Bucket:", repaired["infra/template.yaml"])
        self.assertIn("infra/template.yaml", overlay)

    def test_focused_reference_repair_retries_the_rejected_candidate(self):
        baseline = self.valid_behavior_snapshot()
        baseline["src/lambda_inventory.py"] = baseline["src/lambda_inventory.py"].replace(
            "    connection.rollback()\n", ""
        )
        common_source = baseline["src/lambda_inventory.py"]
        calls = []

        def requester(generation_input, schema, model, api_key, base_url):
            calls.append(generation_input)
            source = common_source
            if len(calls) == 2:
                self.assertIn("PREVIOUS REJECTED STRUCTURED PLAN", generation_input)
                self.assertIn("rollback is missing", generation_input)
                source += "    connection.rollback()\n"
            return {
                "stages": [
                    {
                        "name": "20-final-walkthrough",
                        "summary": "focused database repair",
                        "files": [
                            {"path": "src/lambda_inventory.py", "content": source},
                        ],
                        "delete_files": [],
                    }
                ]
            }

        repaired, _ = _repair_reference_behavior_groups(
            baseline,
            "20-final-walkthrough",
            model="test-model",
            api_token="test-key",
            base_url="https://example.test/v1",
            requester=requester,
            max_validation_retries=1,
        )

        self.assertEqual(len(calls), 2)
        self.assertIn("rollback", repaired["src/lambda_inventory.py"])

    def test_course_operations_repair_requires_all_teaching_artifacts(self):
        baseline = self.valid_behavior_snapshot()
        baseline["README.md"] = baseline["README.md"].replace(
            "1. Submit an order and inspect the returned JSON.",
            "1. Change the handler and rerun tests.",
        )
        fixed_readme = self.valid_behavior_snapshot()["README.md"]
        calls = []

        def requester(generation_input, schema, model, api_key, base_url):
            calls.append(generation_input)
            files = [{"path": "README.md", "content": fixed_readme}]
            if len(calls) == 2:
                self.assertIn("must emit complete replacements", generation_input)
                valid = self.valid_behavior_snapshot()
                files.extend(
                    {"path": path, "content": valid[path]}
                    for path in (
                        "docs/git-history.md",
                        "docs/demo-runbook.md",
                        "tests/test_demo_runbook.py",
                    )
                )
            return {
                "stages": [
                    {
                        "name": "20-final-walkthrough",
                        "summary": "repair final teaching guides",
                        "files": files,
                        "delete_files": [],
                    }
                ]
            }

        repaired, _ = _repair_reference_behavior_groups(
            baseline,
            "20-final-walkthrough",
            model="test-model",
            api_token="test-key",
            base_url="https://example.test/v1",
            requester=requester,
            max_validation_retries=1,
        )

        self.assertEqual(len(calls), 2)
        self.assertIn("Submit an order", repaired["README.md"])

    def test_focused_reference_repair_rejects_nonportable_cached_tests(self):
        baseline = self.valid_behavior_snapshot()
        baseline["tests/test_deployment_wiring.py"] = (
            "import yaml\n"
            "# DATABASE_URL PICK_WORK_QUEUE_URL EVENT_BUS_NAME sqs:SendMessage events:PutEvents\n"
            "# patch boto3 _sqs_client _eventbridge_client fake.calls assert_called\n"
        )
        calls = []
        fixed_test = (
            "from unittest import mock\n"
            "from src import lambda_inventory\n"
            "# DATABASE_URL PICK_WORK_QUEUE_URL EVENT_BUS_NAME sqs:SendMessage events:PutEvents\n"
            "fake_boto3 = mock.Mock()\n"
            "with mock.patch.dict('sys.modules', {'boto3': fake_boto3}):\n"
            "    lambda_inventory._sqs_client()\n"
            "    lambda_inventory._eventbridge_client()\n"
            "fake_boto3.client.assert_any_call('sqs')\n"
            "fake_boto3.client.assert_any_call('events')\n"
        )

        def requester(generation_input, schema, model, api_key, base_url):
            calls.append(generation_input)
            return {
                "stages": [
                    {
                        "name": "20-final-walkthrough",
                        "summary": "portable deployment test",
                        "files": [
                            {"path": "tests/test_deployment_wiring.py", "content": fixed_test},
                        ],
                        "delete_files": [],
                    }
                ]
            }

        repaired, _ = _repair_reference_behavior_groups(
            baseline,
            "20-final-walkthrough",
            model="test-model",
            api_token="test-key",
            base_url="https://example.test/v1",
            requester=requester,
        )

        self.assertEqual(len(calls), 1)
        self.assertNotIn("import yaml", repaired["tests/test_deployment_wiring.py"])

    def test_repository_contains_the_complete_21_stage_course(self):
        prompts = discover_prompt_files(ROOT / "prompts")
        self.assertEqual(len(prompts), 21)
        self.assertEqual(prompts[0].name, "00-establish-repository.md")
        self.assertEqual(prompts[-1].name, "20-final-walkthrough.md")

    def test_single_stage_writes_to_the_exact_requested_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prompt_dir = self.make_course(root)
            target = root / "somewhere" / "custom-name"

            def fake_requester(generation_input, schema, model, api_key, base_url):
                self.assertIn("00-repository.md [CURRENT TARGET]", generation_input)
                self.assertIn("01-json.md [COURSE CONTEXT]", generation_input)
                return {
                    "stages": [
                        {
                            "name": "00-repository",
                            "summary": "standalone",
                            "files": [{"path": "README.md", "content": "# Standalone\n"}],
                            "delete_files": [],
                        }
                    ]
                }

            generated = generate_app(
                prompt_dir / "00-repository.md",
                target,
                prompt_dir=prompt_dir,
                api_key="test-key",
                requester=fake_requester,
            )
            self.assertEqual(generated, target)
            self.assertTrue((target / "README.md").exists())

    def test_resume_uses_frozen_snapshot_without_regenerating_earlier_stages(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prompt_dir = self.make_course(root)
            (prompt_dir / "02-linux.md").write_text("Make Linux visible.\n", encoding="utf-8")
            catalog = discover_prompt_files(prompt_dir)
            output_root = root / "generated"

            initial_plan = {
                "stages": [
                    {
                        "name": "00-repository",
                        "summary": "repository",
                        "files": [{"path": "README.md", "content": "# Repository\n"}],
                        "delete_files": [],
                    },
                    {
                        "name": "01-json",
                        "summary": "json",
                        "files": [
                            {"path": "src/inventory.py", "content": "print('inventory')\n"},
                            {"path": "tests/.gitkeep", "content": ""},
                            {
                                "path": "README.md",
                                "content": self.stage_readme(
                                    "01-json", ["README.md", "src/inventory.py", "tests/.gitkeep"]
                                ),
                            },
                        ],
                        "delete_files": [],
                    },
                ]
            }
            generate_projects(
                catalog[:2],
                catalog,
                output_root,
                api_key="test-key",
                requester=lambda *args: initial_plan,
            )
            frozen_readme = (output_root / "01-json" / "README.md").read_text(encoding="utf-8")
            baseline = load_generated_snapshot(output_root, catalog[1])
            self.assertEqual(find_resume_index(output_root, catalog, 2), 1)

            def resume_requester(generation_input, schema, model, api_key, base_url):
                self.assertIn("I'm only using this to avoid regeneration of perfectly good code.", generation_input)
                self.assertIn("FROZEN BASELINE SNAPSHOT: 01-json", generation_input)
                self.assertIn("print('inventory')", generation_input)
                return {
                    "stages": [
                        {
                            "name": "02-linux",
                            "summary": "linux",
                            "files": [
                                {"path": "src/process_demo.py", "content": "print('running')\n"},
                                {
                                    "path": "README.md",
                                    "content": self.stage_readme(
                                        "02-linux",
                                        [
                                            "README.md",
                                            "src/inventory.py",
                                            "src/process_demo.py",
                                            "tests/.gitkeep",
                                        ],
                                    ),
                                },
                            ],
                            "delete_files": [],
                        }
                    ]
                }

            generate_projects(
                [catalog[2]],
                catalog,
                output_root,
                api_key="test-key",
                requester=resume_requester,
                baseline_stage="01-json",
                baseline_files=baseline,
            )

            self.assertEqual(
                (output_root / "01-json" / "README.md").read_text(encoding="utf-8"),
                frozen_readme,
            )
            self.assertTrue((output_root / "02-linux" / "src" / "inventory.py").exists())
            stage_two_notes = json.loads(
                (output_root / "02-linux" / HANDOFF_NOTES_PATH).read_text(encoding="utf-8")
            )
            self.assertEqual(stage_two_notes["current_stage"], "02-linux")
            self.assertEqual([note["stage"] for note in stage_two_notes["notes"]], ["00-repository", "01-json", "02-linux"])
            manifest = json.loads((output_root / "02-linux" / MANIFEST_NAME).read_text(encoding="utf-8"))
            self.assertEqual(manifest["inherits_from"], "01-json")

    def test_build_generation_input_includes_handoff_notes_context_for_resumes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prompt_dir = self.make_course(root)
            prompts = discover_prompt_files(prompt_dir)
            baseline_files = {
                "README.md": "# TinyWMS lesson: 01-json\n",
                HANDOFF_NOTES_PATH: json.dumps(
                    {
                        "current_stage": "01-json",
                        "notes": [
                            {
                                "stage": "00-repository",
                                "summary": "repo",
                                "inherited_contract": "none",
                                "boundary_change": "bootstrap",
                                "components": {},
                                "continuity_checks": [],
                            },
                            {
                                "stage": "01-json",
                                "summary": "json",
                                "inherited_contract": "json payload shape",
                                "boundary_change": "added JSON file contract",
                                "components": {},
                                "continuity_checks": ["check readme map"],
                            },
                        ],
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
            }
            generation_input = build_generation_input(
                prompts,
                [prompts[1]],
                "Teach with visible JSON.",
                baseline_stage="01-json",
                baseline_files=baseline_files,
            )
            self.assertIn("ACCUMULATED HANDOFF NOTES", generation_input)
            self.assertIn('"stage": "01-json"', generation_input)

    def test_handoff_storage_compacts_history_without_dropping_stage_identity(self):
        notes = []
        for index in range(21):
            notes.append(
                {
                    "stage": f"{index:02d}-stage",
                    "summary": "summary " + ("s" * 1200),
                    "inherited_contract": "contract " + ("c" * 1200),
                    "boundary_change": "boundary " + ("b" * 1200),
                    "components": {
                        "added": "added " + ("a" * 800),
                        "reused_unchanged": "reused " + ("r" * 1800),
                        "replaced_or_evolved": "evolved " + ("e" * 800),
                    },
                    "continuity_checks": ["check inherited behavior"],
                }
            )

        text = _serialize_handoff_notes("20-stage", notes)
        payload = json.loads(text)

        self.assertLessEqual(len(text.encode("utf-8")), MAX_HANDOFF_NOTES_BYTES)
        self.assertEqual(len(payload["notes"]), 21)
        self.assertEqual(
            [note["stage"] for note in payload["notes"]],
            [f"{index:02d}-stage" for index in range(21)],
        )
        self.assertTrue(any(note.get("compacted") for note in payload["notes"][:-1]))
        self.assertEqual(payload["notes"][-1]["stage"], "20-stage")
        self.assertIn("continuity_checks", payload["notes"][-1])

    def test_rejects_unsafe_model_paths(self):
        plan = {
            "stages": [
                {
                    "name": "00-repository",
                    "summary": "bad path",
                    "files": [{"path": "../outside.py", "content": "bad"}],
                    "delete_files": [],
                }
            ]
        }
        with self.assertRaisesRegex(ValueError, "Unsafe generated path"):
            validate_plan(plan, ["00-repository"])

    def test_extracts_text_from_responses_api_message(self):
        payload = {
            "output": [
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": '{"stages": []}'}],
                }
            ]
        }
        self.assertEqual(_response_text(payload), '{"stages": []}')

    def test_output_schema_requires_exactly_the_requested_stage_count(self):
        schema = build_output_schema(["00-repository", "01-json"])
        stages_schema = schema["properties"]["stages"]
        self.assertEqual(stages_schema["minItems"], 2)
        self.assertEqual(stages_schema["maxItems"], 2)

    def test_request_plan_reports_incomplete_response_reason(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_value, traceback):
                return False

            def read(self):
                return json.dumps(
                    {
                        "status": "incomplete",
                        "incomplete_details": {"reason": "max_output_tokens"},
                        "output": [],
                    }
                ).encode("utf-8")

        with patch("toolchain.regen.urlopen", return_value=FakeResponse()):
            with self.assertRaisesRegex(RuntimeError, "incomplete: max_output_tokens"):
                request_plan(
                    "input",
                    build_output_schema(["00-repository"]),
                    "model",
                    "key",
                    "https://example.invalid/v1",
                )

    def test_request_plan_retries_transient_gateway_error(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_value, traceback):
                return False

            def read(self):
                return json.dumps({"output_text": '{"stages": []}'}).encode("utf-8")

        gateway_error = HTTPError(
            "https://example.invalid/v1/responses",
            502,
            "Bad Gateway",
            {},
            BytesIO(b"error code: 502"),
        )
        with (
            patch("toolchain.regen.urlopen", side_effect=[gateway_error, FakeResponse()]) as mocked_urlopen,
            patch("toolchain.regen.time.sleep") as mocked_sleep,
            patch("toolchain.regen.random.uniform", return_value=0),
        ):
            plan = request_plan(
                "input",
                build_output_schema(["00-repository"]),
                "model",
                "key",
                "https://example.invalid/v1",
            )

        self.assertEqual(plan, {"stages": []})
        self.assertEqual(mocked_urlopen.call_count, 2)
        mocked_sleep.assert_called_once_with(1)

    def test_request_plan_retries_dropped_connection(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_value, traceback):
                return False

            def read(self):
                return json.dumps({"output_text": '{"stages": []}'}).encode("utf-8")

        disconnected = RemoteDisconnected("remote end closed connection without response")
        with (
            patch("toolchain.regen.urlopen", side_effect=[disconnected, FakeResponse()]) as mocked_urlopen,
            patch("toolchain.regen.time.sleep") as mocked_sleep,
            patch("toolchain.regen.random.uniform", return_value=0),
        ):
            plan = request_plan(
                "input",
                build_output_schema(["00-repository"]),
                "model",
                "key",
                "https://example.invalid/v1",
            )

        self.assertEqual(plan, {"stages": []})
        self.assertEqual(mocked_urlopen.call_count, 2)
        mocked_sleep.assert_called_once_with(1)

    def test_normalizes_duplicate_writes_by_keeping_last_entry(self):
        plan = {
            "stages": [
                {
                    "name": "00-repository",
                    "summary": "duplicate write normalization",
                    "files": [
                        {"path": "README.md", "content": "first\n"},
                        {"path": "README.md", "content": "second\n"},
                    ],
                    "delete_files": [],
                }
            ]
        }
        stages = validate_plan(plan, ["00-repository"])
        files = stages[0]["files"]
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0]["path"], "README.md")
        self.assertEqual(files[0]["content"], "second\n")

    def test_normalizes_write_delete_conflict_by_keeping_the_written_file(self):
        plan = {
            "stages": [
                {
                    "name": "00-repository",
                    "summary": "write wins",
                    "files": [{"path": "tests/test_flow.py", "content": "VALUE = 1\n"}],
                    "delete_files": ["tests/test_flow.py", "src/obsolete.py"],
                }
            ]
        }

        stages = validate_plan(plan, ["00-repository"])

        self.assertEqual(stages[0]["delete_files"], ["src/obsolete.py"])
        self.assertEqual(stages[0]["files"][0]["path"], "tests/test_flow.py")

    def test_retries_once_after_validation_failure_and_succeeds(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prompt_dir = self.make_course(root)
            calls = []

            def fake_requester(generation_input, schema, model, api_key, base_url):
                calls.append(generation_input)
                if len(calls) == 1:
                    return {
                        "stages": [
                            {
                                "name": "00-repository",
                                "summary": "repo",
                                "files": [{"path": "README.md", "content": "# Setup\n"}],
                                "delete_files": [],
                            },
                            {
                                "name": "01-json",
                                "summary": "json",
                                "files": [
                                    {"path": "../outside.py", "content": "bad\n"}
                                ],
                                "delete_files": [],
                            },
                        ]
                    }
                return {
                    "stages": [
                        {
                            "name": "00-repository",
                            "summary": "repo",
                            "files": [{"path": "README.md", "content": "# Setup\n"}],
                            "delete_files": [],
                        },
                        {
                            "name": "01-json",
                            "summary": "json",
                            "files": [
                                {"path": "src/inventory.py", "content": "print('ok')\n"},
                                {"path": "tests/.gitkeep", "content": ""},
                                {
                                    "path": "README.md",
                                    "content": self.stage_readme(
                                        "01-json", ["README.md", "src/inventory.py", "tests/.gitkeep"]
                                    ),
                                },
                            ],
                            "delete_files": [],
                        },
                    ]
                }

            output_root = root / "generated"
            generated = generate_all_apps(
                prompt_dir,
                output_root,
                api_key="test-key",
                requester=fake_requester,
                max_validation_retries=1,
            )
            self.assertEqual(len(generated), 2)
            self.assertEqual(len(calls), 2)
            self.assertIn("VALIDATION FAILURE FROM PREVIOUS ATTEMPT", calls[1])
            self.assertIn("PREVIOUS REJECTED STRUCTURED PLAN", calls[1])
            self.assertIn("../outside.py", calls[1])
            self.assertTrue((output_root / "01-json" / "src" / "inventory.py").exists())

    def test_materialized_stage_retry_preserves_valid_prefix_and_regenerates_suffix(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prompt_dir = self.make_course(root)
            (prompt_dir / "02-linux.md").write_text("Make Linux visible.\n", encoding="utf-8")
            (prompt_dir / "03-http.md").write_text("Add HTTP.\n", encoding="utf-8")
            catalog = discover_prompt_files(prompt_dir)
            calls = []

            def fake_requester(generation_input, schema, model, api_key, base_url):
                calls.append((generation_input, schema))
                if len(calls) == 1:
                    bad_readme = self.stage_readme(
                        "02-linux",
                        ["README.md", "src/inventory.py", "src/process_demo.py", "tests/.gitkeep"],
                    ).replace("# TinyWMS lesson:", "# Wrong title:", 1)
                    return {
                        "stages": [
                            {
                                "name": "00-repository",
                                "summary": "repository",
                                "files": [{"path": "README.md", "content": "# Repository\n"}],
                                "delete_files": [],
                            },
                            {
                                "name": "01-json",
                                "summary": "json",
                                "files": [
                                    {"path": "src/inventory.py", "content": "print('inventory')\n"},
                                    {"path": "tests/.gitkeep", "content": ""},
                                    {
                                        "path": "README.md",
                                        "content": self.stage_readme(
                                            "01-json", ["README.md", "src/inventory.py", "tests/.gitkeep"]
                                        ),
                                    },
                                ],
                                "delete_files": [],
                            },
                            {
                                "name": "02-linux",
                                "summary": "linux",
                                "files": [
                                    {"path": "src/process_demo.py", "content": "print('running')\n"},
                                    {"path": "README.md", "content": bad_readme},
                                ],
                                "delete_files": [],
                            },
                            {
                                "name": "03-http",
                                "summary": "not reached before the Stage 02 failure",
                                "files": [],
                                "delete_files": [],
                            },
                        ]
                    }

                if len(calls) == 2:
                    self.assertIn("FROZEN BASELINE SNAPSHOT: 01-json", generation_input)
                    self.assertIn("README title must start", generation_input)
                    self.assertIn("print('inventory')", generation_input)
                    self.assertEqual(
                        schema["properties"]["stages"]["items"]["properties"]["name"]["enum"],
                        ["02-linux", "03-http"],
                    )
                    bad_http_readme = self.stage_readme(
                        "03-http",
                        ["README.md", "src/inventory.py", "src/process_demo.py", "src/server.py", "tests/.gitkeep"],
                    ).replace("# TinyWMS lesson:", "# Wrong title:", 1)
                    return {
                        "stages": [
                            {
                                "name": "02-linux",
                                "summary": "linux repaired",
                                "files": [
                                    {"path": "src/process_demo.py", "content": "print('running')\n"},
                                    {
                                        "path": "README.md",
                                        "content": self.stage_readme(
                                            "02-linux",
                                            [
                                                "README.md",
                                                "src/inventory.py",
                                                "src/process_demo.py",
                                                "tests/.gitkeep",
                                            ],
                                        ),
                                    },
                                ],
                                "delete_files": [],
                            },
                            {
                                "name": "03-http",
                                "summary": "http",
                                "files": [
                                    {"path": "src/server.py", "content": "print('server')\n"},
                                    {"path": "README.md", "content": bad_http_readme},
                                ],
                                "delete_files": [],
                            },
                        ]
                    }

                self.assertIn("FROZEN BASELINE SNAPSHOT: 02-linux", generation_input)
                self.assertIn("print('running')", generation_input)
                self.assertEqual(
                    schema["properties"]["stages"]["items"]["properties"]["name"]["enum"],
                    ["03-http"],
                )
                return {
                    "stages": [
                        {
                            "name": "03-http",
                            "summary": "http repaired",
                            "files": [
                                {"path": "src/server.py", "content": "print('server')\n"},
                                {
                                    "path": "README.md",
                                    "content": self.stage_readme(
                                        "03-http",
                                        [
                                            "README.md",
                                            "src/inventory.py",
                                            "src/process_demo.py",
                                            "src/server.py",
                                            "tests/.gitkeep",
                                        ],
                                    ),
                                },
                            ],
                            "delete_files": [],
                        }
                    ]
                }

            generated = generate_all_apps(
                prompt_dir,
                root / "generated",
                api_key="test-key",
                requester=fake_requester,
                max_validation_retries=2,
            )

            self.assertEqual(len(calls), 3)
            self.assertEqual(len(generated), 4)
            self.assertTrue((root / "generated" / "01-json" / "src" / "inventory.py").exists())
            self.assertTrue((root / "generated" / "02-linux" / "src" / "process_demo.py").exists())
            self.assertTrue((root / "generated" / "03-http" / "src" / "server.py").exists())

    def test_stops_after_retry_budget_exhausted(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prompt_dir = self.make_course(root)

            def fake_requester(generation_input, schema, model, api_key, base_url):
                return {
                    "stages": [
                        {
                            "name": "00-repository",
                            "summary": "repo",
                            "files": [{"path": "README.md", "content": "# Setup\n"}],
                            "delete_files": [],
                        },
                        {
                            "name": "01-json",
                            "summary": "json",
                            "files": [
                                {"path": "../outside.py", "content": "bad\n"}
                            ],
                            "delete_files": [],
                        },
                    ]
                }

            with self.assertRaisesRegex(ValueError, "Unsafe generated path"):
                generate_all_apps(
                    prompt_dir,
                    root / "generated",
                    api_key="test-key",
                    requester=fake_requester,
                    max_validation_retries=0,
                )

    def test_rejects_malformed_readme_file_map_paths(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prompt_dir = self.make_course(root)

            def fake_requester(generation_input, schema, model, api_key, base_url):
                return {
                    "stages": [
                        {
                            "name": "00-repository",
                            "summary": "repo",
                            "files": [{"path": "README.md", "content": "# Setup\n"}],
                            "delete_files": [],
                        },
                        {
                            "name": "01-json",
                            "summary": "json",
                            "files": [
                                {
                                    "path": "README.md",
                                    "content": self.stage_readme("01-json", ["README.md", "src\\missing.py"]),
                                }
                            ],
                            "delete_files": [],
                        },
                    ]
                }

            with self.assertRaisesRegex(ValueError, "Unsafe generated path"):
                generate_all_apps(
                    prompt_dir,
                    root / "generated",
                    api_key="test-key",
                    requester=fake_requester,
                    max_validation_retries=0,
                )

    def test_allows_missing_test_file_entries_in_readme_file_map(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prompt_dir = self.make_course(root)

            def fake_requester(generation_input, schema, model, api_key, base_url):
                return {
                    "stages": [
                        {
                            "name": "00-repository",
                            "summary": "repo",
                            "files": [{"path": "README.md", "content": "# Setup\n"}],
                            "delete_files": [],
                        },
                        {
                            "name": "01-json",
                            "summary": "json",
                            "files": [
                                {"path": "src/inventory.py", "content": "print('ok')\n"},
                                {"path": "tests/.gitkeep", "content": ""},
                                {
                                    "path": "README.md",
                                    "content": self.stage_readme(
                                        "01-json",
                                        ["README.md", "src/inventory.py", "tests/missing_test_file.py"],
                                    ),
                                },
                            ],
                            "delete_files": [],
                        },
                    ]
                }

            generated = generate_all_apps(
                prompt_dir,
                root / "generated",
                api_key="test-key",
                requester=fake_requester,
            )
            self.assertEqual(len(generated), 2)

    def test_prunes_missing_non_test_readme_file_map_entries(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prompt_dir = self.make_course(root)

            def fake_requester(generation_input, schema, model, api_key, base_url):
                return {
                    "stages": [
                        {
                            "name": "00-repository",
                            "summary": "repo",
                            "files": [{"path": "README.md", "content": "# Setup\n"}],
                            "delete_files": [],
                        },
                        {
                            "name": "01-json",
                            "summary": "json",
                            "files": [
                                {"path": "src/inventory.py", "content": "print('ok')\n"},
                                {"path": "tests/.gitkeep", "content": ""},
                                {
                                    "path": "README.md",
                                    "content": self.stage_readme(
                                        "01-json",
                                        ["README.md", "src/inventory.py", "src/missing_runtime.py"],
                                    ),
                                },
                            ],
                            "delete_files": [],
                        },
                    ]
                }

            generate_all_apps(
                prompt_dir,
                root / "generated",
                api_key="test-key",
                requester=fake_requester,
            )
            readme = (root / "generated" / "01-json" / "README.md").read_text(encoding="utf-8")
            self.assertIn("src/inventory.py", readme)
            self.assertNotIn("src/missing_runtime.py", readme)

    def test_prunes_runtime_artifacts_from_readme_file_map(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prompt_dir = self.make_course(root)

            def fake_requester(generation_input, schema, model, api_key, base_url):
                return {
                    "stages": [
                        {
                            "name": "00-repository",
                            "summary": "repo",
                            "files": [{"path": "README.md", "content": "# Setup\n"}],
                            "delete_files": [],
                        },
                        {
                            "name": "01-json",
                            "summary": "json",
                            "files": [
                                {"path": "src/inventory.py", "content": "print('ok')\n"},
                                {"path": "tests/.gitkeep", "content": ""},
                                {"path": "pick-tickets.txt", "content": "ticket\n"},
                                {
                                    "path": "README.md",
                                    "content": self.stage_readme(
                                        "01-json",
                                        ["README.md", "src/inventory.py", "pick-tickets.txt"],
                                    ),
                                },
                            ],
                            "delete_files": [],
                        },
                    ]
                }

            generate_all_apps(
                prompt_dir,
                root / "generated",
                api_key="test-key",
                requester=fake_requester,
            )
            readme = (root / "generated" / "01-json" / "README.md").read_text(encoding="utf-8")
            self.assertIn("src/inventory.py", readme)
            self.assertNotIn("pick-tickets.txt", readme)

    def test_accepts_readme_directory_entries_with_trailing_slash(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prompt_dir = self.make_course(root)

            def fake_requester(generation_input, schema, model, api_key, base_url):
                return {
                    "stages": [
                        {
                            "name": "00-repository",
                            "summary": "repo",
                            "files": [{"path": "README.md", "content": "# Setup\n"}],
                            "delete_files": [],
                        },
                        {
                            "name": "01-json",
                            "summary": "json",
                            "files": [
                                {"path": "src/inventory.py", "content": "print('ok')\n"},
                                {"path": "tests/.gitkeep", "content": ""},
                                {
                                    "path": "README.md",
                                    "content": self.stage_readme(
                                        "01-json", ["README.md", "src/", "tests/"]
                                    ),
                                },
                            ],
                            "delete_files": [],
                        },
                    ]
                }

            generated = generate_all_apps(
                prompt_dir,
                root / "generated",
                api_key="test-key",
                requester=fake_requester,
            )
            self.assertEqual(len(generated), 2)

    def test_rejects_stage18_missing_required_deploy_artifacts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prompt_dir = root / "prompts"
            prompt_dir.mkdir()
            (root / "AGENTS.md").write_text("Teach with visible JSON.\n", encoding="utf-8")
            (prompt_dir / "18-aws-deployment.md").write_text("Deploy stage.\n", encoding="utf-8")

            def fake_requester(generation_input, schema, model, api_key, base_url):
                return {
                    "stages": [
                        {
                            "name": "18-aws-deployment",
                            "summary": "deploy",
                            "files": [
                                {
                                    "path": "README.md",
                                    "content": self.stage_readme(
                                        "18-aws-deployment", ["README.md", "infra/template.yaml"]
                                    ),
                                }
                            ],
                            "delete_files": [],
                        }
                    ]
                }

            with self.assertRaisesRegex(ValueError, "missing required AWS deployment artifacts"):
                generate_all_apps(prompt_dir, root / "generated", api_key="test-key", requester=fake_requester)

    def test_rejects_stage18_without_callable_api_gateway_resources(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prompt_dir = root / "prompts"
            prompt_dir.mkdir()
            (root / "AGENTS.md").write_text("Teach with visible JSON.\n", encoding="utf-8")
            (prompt_dir / "18-aws-deployment.md").write_text("Deploy stage.\n", encoding="utf-8")

            def fake_requester(generation_input, schema, model, api_key, base_url):
                return {
                    "stages": [
                        {
                            "name": "18-aws-deployment",
                            "summary": "deploy",
                            "files": [
                                {
                                    "path": "README.md",
                                    "content": self.stage_readme(
                                        "18-aws-deployment",
                                        [
                                            "README.md",
                                            "deploy/ec2/run_inventory_server.sh",
                                            "deploy/ec2/environment.example",
                                            "infra/lambda.yaml",
                                            "deploy/lambda/README.md",
                                            "infra/api-gateway.yaml",
                                            "deploy/api-gateway/README.md",
                                            "infra/rds.yaml",
                                            "deploy/rds/README.md",
                                            "infra/sqs.yaml",
                                            "deploy/sqs/README.md",
                                            "infra/events.yaml",
                                            "deploy/events/README.md",
                                            "infra/template.yaml",
                                            "deploy/aws/README.md",
                                        ],
                                    ),
                                },
                                {"path": "deploy/ec2/run_inventory_server.sh", "content": "#!/usr/bin/env bash\n"},
                                {"path": "deploy/ec2/environment.example", "content": "PORT=8000\n"},
                                {"path": "infra/lambda.yaml", "content": "Resources: {}\n"},
                                {"path": "deploy/lambda/README.md", "content": "deploy lambda\n"},
                                {"path": "infra/api-gateway.yaml", "content": "Resources: {}\n"},
                                {"path": "deploy/api-gateway/README.md", "content": "deploy api-gateway\n"},
                                {"path": "infra/rds.yaml", "content": "Resources: {}\n"},
                                {"path": "deploy/rds/README.md", "content": "deploy rds\n"},
                                {"path": "infra/sqs.yaml", "content": "Resources: {}\n"},
                                {"path": "deploy/sqs/README.md", "content": "deploy sqs\n"},
                                {"path": "infra/events.yaml", "content": "Resources: {}\n"},
                                {"path": "deploy/events/README.md", "content": "deploy events\n"},
                                {
                                    "path": "deploy/aws/README.md",
                                    "content": (
                                        "## Deploy\nx\n## Resolve outputs\nx\n## Verify contracts\nx\n## Destroy\nx\n"
                                    ),
                                },
                                {
                                    "path": "infra/template.yaml",
                                    "content": (
                                        "Resources:\n"
                                        "  InventoryApi:\n"
                                        "    Type: AWS::ApiGateway::RestApi\n"
                                        "  InventoryFunction:\n"
                                        "    Type: AWS::Lambda::Function\n"
                                        "  InventoryRole:\n"
                                        "    Type: AWS::IAM::Role\n"
                                        "  Queue:\n"
                                        "    Type: AWS::SQS::Queue\n"
                                        "  Events:\n"
                                        "    Type: AWS::Events::EventBus\n"
                                        "  Logs:\n"
                                        "    Type: AWS::Logs::LogGroup\n"
                                        "Outputs:\n"
                                        "  ApiBaseUrl:\n"
                                        "    Value: !Sub 'https://${InventoryApi}.execute-api.${AWS::Region}.amazonaws.com/prod'\n"
                                    ),
                                },
                            ],
                            "delete_files": [],
                        }
                    ]
                }

            with self.assertRaisesRegex(ValueError, "missing API methods"):
                generate_all_apps(prompt_dir, root / "generated", api_key="test-key", requester=fake_requester)

    def test_deployability_audit_requires_iam_capabilities_in_deploy_docs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prompt_dir = root / "prompts"
            prompt_dir.mkdir()
            (root / "AGENTS.md").write_text("Teach with visible JSON.\n", encoding="utf-8")
            (prompt_dir / "18-aws-deployment.md").write_text("Deploy stage.\n", encoding="utf-8")

            def fake_requester(generation_input, schema, model, api_key, base_url):
                return {
                    "stages": [
                        {
                            "name": "18-aws-deployment",
                            "summary": "deploy",
                            "files": [
                                {
                                    "path": "README.md",
                                    "content": self.stage_readme(
                                        "18-aws-deployment",
                                        [
                                            "README.md",
                                            "deploy/ec2/run_inventory_server.sh",
                                            "deploy/ec2/environment.example",
                                            "infra/lambda.yaml",
                                            "deploy/lambda/README.md",
                                            "infra/api-gateway.yaml",
                                            "deploy/api-gateway/README.md",
                                            "infra/rds.yaml",
                                            "deploy/rds/README.md",
                                            "infra/sqs.yaml",
                                            "deploy/sqs/README.md",
                                            "infra/events.yaml",
                                            "deploy/events/README.md",
                                            "infra/template.yaml",
                                            "deploy/aws/README.md",
                                        ],
                                    ),
                                },
                                {"path": "deploy/ec2/run_inventory_server.sh", "content": "#!/usr/bin/env bash\n"},
                                {"path": "deploy/ec2/environment.example", "content": "PORT=8000\n"},
                                {"path": "infra/lambda.yaml", "content": "AWSTemplateFormatVersion: '2010-09-09'\nResources: {}\n"},
                                {"path": "deploy/lambda/README.md", "content": "deploy lambda\n"},
                                {"path": "infra/api-gateway.yaml", "content": "AWSTemplateFormatVersion: '2010-09-09'\nResources: {}\n"},
                                {"path": "deploy/api-gateway/README.md", "content": "deploy api-gateway\n"},
                                {"path": "infra/rds.yaml", "content": "AWSTemplateFormatVersion: '2010-09-09'\nResources: {}\n"},
                                {"path": "deploy/rds/README.md", "content": "deploy rds\n"},
                                {"path": "infra/sqs.yaml", "content": "AWSTemplateFormatVersion: '2010-09-09'\nResources: {}\n"},
                                {"path": "deploy/sqs/README.md", "content": "deploy sqs\n"},
                                {"path": "infra/events.yaml", "content": "AWSTemplateFormatVersion: '2010-09-09'\nResources: {}\n"},
                                {"path": "deploy/events/README.md", "content": "deploy events\n"},
                                {
                                    "path": "deploy/aws/README.md",
                                    "content": (
                                        "## Deploy\n"
                                        "```bash\n"
                                        "aws cloudformation deploy --stack-name tinywms --template-file infra/template.yaml\n"
                                        "```\n"
                                        "## Resolve outputs\nx\n## Verify contracts\nx\n## Destroy\nx\n"
                                    ),
                                },
                                {
                                    "path": "infra/template.yaml",
                                    "content": (
                                        "AWSTemplateFormatVersion: '2010-09-09'\n"
                                        "Resources:\n"
                                        "  Api:\n"
                                        "    Type: AWS::ApiGateway::RestApi\n"
                                        "  InventoryPath:\n"
                                        "    Type: AWS::ApiGateway::Resource\n"
                                        "    Properties:\n"
                                        "      PathPart: inventory\n"
                                        "  GetMethod:\n"
                                        "    Type: AWS::ApiGateway::Method\n"
                                        "  Deploy:\n"
                                        "    Type: AWS::ApiGateway::Deployment\n"
                                        "  Fn:\n"
                                        "    Type: AWS::Lambda::Function\n"
                                        "  Role:\n"
                                        "    Type: AWS::IAM::Role\n"
                                        "  Queue:\n"
                                        "    Type: AWS::SQS::Queue\n"
                                        "  Bus:\n"
                                        "    Type: AWS::Events::EventBus\n"
                                        "  Logs:\n"
                                        "    Type: AWS::Logs::LogGroup\n"
                                        "  Permission:\n"
                                        "    Type: AWS::Lambda::Permission\n"
                                        "Outputs:\n"
                                        "  ApiBaseUrl:\n"
                                        "    Value: !Sub 'https://${Api}.execute-api.${AWS::Region}.amazonaws.com/prod'\n"
                                    ),
                                },
                            ],
                            "delete_files": [],
                        }
                    ]
                }

            with self.assertRaisesRegex(ValueError, "deployability audit failed: deploy docs must include --capabilities"):
                generate_all_apps(prompt_dir, root / "generated", api_key="test-key", requester=fake_requester)

    def test_deployability_audit_rejects_inline_zipfile_with_src_handler(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prompt_dir = root / "prompts"
            prompt_dir.mkdir()
            (root / "AGENTS.md").write_text("Teach with visible JSON.\n", encoding="utf-8")
            (prompt_dir / "18-aws-deployment.md").write_text("Deploy stage.\n", encoding="utf-8")

            def fake_requester(generation_input, schema, model, api_key, base_url):
                return {
                    "stages": [
                        {
                            "name": "18-aws-deployment",
                            "summary": "deploy",
                            "files": [
                                {
                                    "path": "README.md",
                                    "content": self.stage_readme(
                                        "18-aws-deployment",
                                        [
                                            "README.md",
                                            "deploy/ec2/run_inventory_server.sh",
                                            "deploy/ec2/environment.example",
                                            "infra/lambda.yaml",
                                            "deploy/lambda/README.md",
                                            "infra/api-gateway.yaml",
                                            "deploy/api-gateway/README.md",
                                            "infra/rds.yaml",
                                            "deploy/rds/README.md",
                                            "infra/sqs.yaml",
                                            "deploy/sqs/README.md",
                                            "infra/events.yaml",
                                            "deploy/events/README.md",
                                            "infra/template.yaml",
                                            "deploy/aws/README.md",
                                        ],
                                    ),
                                },
                                {"path": "deploy/ec2/run_inventory_server.sh", "content": "#!/usr/bin/env bash\n"},
                                {"path": "deploy/ec2/environment.example", "content": "PORT=8000\n"},
                                {"path": "infra/lambda.yaml", "content": "AWSTemplateFormatVersion: '2010-09-09'\nResources: {}\n"},
                                {"path": "deploy/lambda/README.md", "content": "deploy lambda\n"},
                                {"path": "infra/api-gateway.yaml", "content": "AWSTemplateFormatVersion: '2010-09-09'\nResources: {}\n"},
                                {"path": "deploy/api-gateway/README.md", "content": "deploy api-gateway\n"},
                                {"path": "infra/rds.yaml", "content": "AWSTemplateFormatVersion: '2010-09-09'\nResources: {}\n"},
                                {"path": "deploy/rds/README.md", "content": "deploy rds\n"},
                                {"path": "infra/sqs.yaml", "content": "AWSTemplateFormatVersion: '2010-09-09'\nResources: {}\n"},
                                {"path": "deploy/sqs/README.md", "content": "deploy sqs\n"},
                                {"path": "infra/events.yaml", "content": "AWSTemplateFormatVersion: '2010-09-09'\nResources: {}\n"},
                                {"path": "deploy/events/README.md", "content": "deploy events\n"},
                                {
                                    "path": "deploy/aws/README.md",
                                    "content": (
                                        "## Deploy\n"
                                        "```bash\n"
                                        "aws cloudformation deploy --stack-name tinywms --template-file infra/template.yaml --capabilities CAPABILITY_NAMED_IAM\n"
                                        "```\n"
                                        "## Resolve outputs\nx\n## Verify contracts\nx\n## Destroy\nx\n"
                                    ),
                                },
                                {
                                    "path": "infra/template.yaml",
                                    "content": (
                                        "AWSTemplateFormatVersion: '2010-09-09'\n"
                                        "Resources:\n"
                                        "  Api:\n"
                                        "    Type: AWS::ApiGateway::RestApi\n"
                                        "  InventoryPath:\n"
                                        "    Type: AWS::ApiGateway::Resource\n"
                                        "    Properties:\n"
                                        "      PathPart: inventory\n"
                                        "  GetMethod:\n"
                                        "    Type: AWS::ApiGateway::Method\n"
                                        "  Deploy:\n"
                                        "    Type: AWS::ApiGateway::Deployment\n"
                                        "  Fn:\n"
                                        "    Type: AWS::Lambda::Function\n"
                                        "    Properties:\n"
                                        "      Handler: src.lambda_inventory.handler\n"
                                        "      Code:\n"
                                        "        ZipFile: |\n"
                                        "          def handler(event, context):\n"
                                        "            return {'statusCode': 200}\n"
                                        "  Role:\n"
                                        "    Type: AWS::IAM::Role\n"
                                        "  Queue:\n"
                                        "    Type: AWS::SQS::Queue\n"
                                        "  Bus:\n"
                                        "    Type: AWS::Events::EventBus\n"
                                        "  Logs:\n"
                                        "    Type: AWS::Logs::LogGroup\n"
                                        "  Permission:\n"
                                        "    Type: AWS::Lambda::Permission\n"
                                        "Outputs:\n"
                                        "  ApiBaseUrl:\n"
                                        "    Value: !Sub 'https://${Api}.execute-api.${AWS::Region}.amazonaws.com/prod'\n"
                                    ),
                                },
                            ],
                            "delete_files": [],
                        }
                    ]
                }

            with self.assertRaisesRegex(ValueError, "inline ZipFile Lambda"):
                generate_all_apps(prompt_dir, root / "generated", api_key="test-key", requester=fake_requester)

    def test_reference_context_reports_all_inherited_deployment_defects_together(self):
        snapshot = {
            "infra/rds.yaml": (
                "AWSTemplateFormatVersion: '2010-09-09'\n"
                "Resources:\n"
                "  Subnets:\n"
                "    Type: AWS::RDS::DBSubnetGroup\n"
                "    Properties:\n"
                "      SubnetIds: []\n"
                "  Database:\n"
                "    Type: AWS::RDS::DBInstance\n"
                "    Properties:\n"
                "      MasterUserPassword: change-me-in-a-real-deployment\n"
            )
        }

        issues = _deployability_audit_issues(snapshot)
        self.assertEqual(len(issues), 2)
        self.assertIn("empty DBSubnetGroup SubnetIds", issues[0])
        self.assertIn("placeholder credentials", issues[1])

        context = _reference_generation_context(
            ["19-git-history", "20-final-walkthrough"],
            snapshot,
        )
        self.assertIn("REFERENCE SEED REPAIR REQUIREMENTS", context)
        self.assertIn("fixing all listed issues in the same response", context)
        self.assertIn("empty DBSubnetGroup SubnetIds", context)
        self.assertIn("placeholder credentials", context)

    def test_scratch_reference_context_requires_every_cumulative_aws_artifact(self):
        context = _reference_generation_context(
            ["00-establish-repository", "20-final-walkthrough"],
            None,
        )

        self.assertIn("SCRATCH FINAL REFERENCE COMPLETENESS CONTRACT", context)
        for _, paths in REQUIRED_AWS_ARTIFACTS_BY_STAGE:
            for path in paths:
                self.assertIn(path, context)

    def test_scratch_reference_requests_and_returns_only_missing_aws_artifacts(self):
        stage_name = "20-final-walkthrough"
        required = [
            path
            for _, paths in REQUIRED_AWS_ARTIFACTS_BY_STAGE
            for path in paths
        ]
        present_path = required[0]
        missing_paths = required[1:]
        plan = {
            "stages": [
                {
                    "name": stage_name,
                    "summary": "scratch candidate",
                    "files": [
                        {"path": present_path, "content": "already here\n"},
                        {
                            "path": "src/lambda_inventory.py",
                            "content": "def handler(event, context):\n    return {}\n",
                        },
                    ],
                    "delete_files": [],
                }
            ]
        }
        calls = []

        def requester(generation_input, schema, model, api_key, base_url):
            calls.append(generation_input)
            return {
                "stages": [
                    {
                        "name": stage_name,
                        "summary": "complete missing deployment artifacts",
                        "files": [
                            {"path": path, "content": f"content for {path}\n"}
                            for path in missing_paths
                        ]
                        + [{"path": "README.md", "content": "must be ignored\n"}],
                        "delete_files": [],
                    }
                ]
            }

        overlay = _scratch_reference_missing_aws_overlay(
            plan,
            stage_name,
            model="test-model",
            api_key="test-key",
            base_url="https://example.invalid",
            requester=requester,
        )

        self.assertEqual(set(overlay), set(missing_paths))
        self.assertNotIn(present_path, overlay)
        self.assertNotIn("README.md", overlay)
        self.assertEqual(len(calls), 1)
        self.assertIn("MISSING PATHS", calls[0])
        self.assertIn("src/lambda_inventory.py", calls[0])

    def test_scratch_reference_progress_cache_is_digest_scoped(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / ".reference.scratch.json"
            snapshot = {
                "src/lambda_inventory.py": "def handler(event, context): return {}\n",
                "tests/test_sqlite_orders.py": "def test_order(): assert True\n",
            }

            _save_scratch_reference_cache(cache_path, "prompt-digest", snapshot)

            loaded = _load_scratch_reference_cache(cache_path, "prompt-digest")
            self.assertEqual(
                loaded["src/lambda_inventory.py"],
                snapshot["src/lambda_inventory.py"],
            )
            self.assertEqual(
                _unittest_case_methods(loaded["tests/test_sqlite_orders.py"]),
                {"test_order"},
            )
            self.assertEqual(
                _load_scratch_reference_cache(cache_path, "different-prompts"),
                {},
            )

    def test_failed_focused_repair_exposes_partial_candidate_for_scratch_resume(self):
        baseline = self.valid_behavior_snapshot()
        broken_app = baseline["src/web/app.js"].replace(
            "  return loadInventory();",
            "  return Promise.resolve();",
        )
        baseline["src/web/app.js"] = broken_app
        progress = []

        def requester(generation_input, schema, model, api_key, base_url):
            return {
                "stages": [
                    {
                        "name": "20-final-walkthrough",
                        "summary": "partial browser repair",
                        "files": [{"path": "src/web/app.js", "content": broken_app}],
                        "delete_files": [],
                    }
                ]
            }

        with self.assertRaisesRegex(ValueError, "browser does not refresh"):
            _repair_reference_behavior_groups(
                baseline,
                "20-final-walkthrough",
                model="test-model",
                api_token="test-key",
                base_url="https://example.invalid",
                requester=requester,
                max_validation_retries=0,
                on_group_progress=lambda snapshot, overlay: progress.append((snapshot, overlay)),
            )

        self.assertEqual(len(progress), 1)
        self.assertIn("src/web/app.js", progress[0][1])

    def test_deployability_audit_rejects_generic_placeholder_values(self):
        issues = _deployability_audit_issues(
            {
                "infra/template.yaml": (
                    "AWSTemplateFormatVersion: '2010-09-09'\n"
                    "Resources:\n"
                    "  Function:\n"
                    "    Type: AWS::Lambda::Function\n"
                    "    Properties:\n"
                    "      Environment:\n"
                    "        Variables:\n"
                    "          DATABASE_URL: postgresql://placeholder:5432/placeholder-db-endpoint\n"
                )
            }
        )

        self.assertEqual(len(issues), 1)
        self.assertIn("placeholder values", issues[0])

    def test_reference_seed_repair_overlay_is_recorded_as_a_stage_delta(self):
        baseline = {
            "infra/lambda.yaml": (
                "AWSTemplateFormatVersion: '2010-09-09'\n"
                "Resources:\n"
                "  Function:\n"
                "    Type: AWS::Lambda::Function\n"
                "    Properties:\n"
                "      Handler: src.lambda_inventory.handler\n"
                "      Code:\n"
                "        ZipFile: |\n"
                "          def handler(event, context): return {}\n"
            ),
            "infra/rds.yaml": (
                "AWSTemplateFormatVersion: '2010-09-09'\n"
                "Parameters:\n"
                "  DatabaseName:\n"
                "    Type: String\n"
                "Resources:\n"
                "  SecurityGroup:\n"
                "    Type: AWS::EC2::SecurityGroup\n"
                "    Properties:\n"
                "      GroupDescription: lesson\n"
                "      SecurityGroupIngress: []\n"
                "  Subnets:\n"
                "    Type: AWS::RDS::DBSubnetGroup\n"
                "    Properties:\n"
                "      SubnetIds: []\n"
                "  Database:\n"
                "    Type: AWS::RDS::DBInstance\n"
                "    Properties:\n"
                "      MasterUsername: tinywms\n"
                "      MasterUserPassword: change-me-in-a-real-deployment\n"
            ),
            "deploy/rds/README.md": "old instructions\n",
        }
        original = dict(baseline)

        overlay = _reference_seed_repair_overlay(baseline)
        repaired = {**baseline, **overlay}

        self.assertEqual(baseline, original)
        self.assertEqual(_deployability_audit_issues(repaired), [])
        self.assertEqual(_reference_seed_repair_overlay(repaired), {})
        self.assertIn("Handler: index.handler", overlay["infra/lambda.yaml"])
        self.assertIn("SubnetIds: !Ref DatabaseSubnetIds", overlay["infra/rds.yaml"])
        self.assertIn("NoEcho: true", overlay["infra/rds.yaml"])
        self.assertIn('DatabaseSubnetIds="$SUBNET_IDS"', overlay["deploy/rds/README.md"])

        plan = {
            "stages": [
                {
                    "name": "20-final-walkthrough",
                    "summary": "model delta",
                    "files": [
                        {"path": "docs/end-to-end.md", "content": "walkthrough\n"},
                        {"path": "infra/rds.yaml", "content": "model left it broken\n"},
                    ],
                    "delete_files": ["infra/rds.yaml"],
                }
            ]
        }
        _apply_stage_file_overlay(plan, "20-final-walkthrough", overlay)
        stage_files = {item["path"]: item["content"] for item in plan["stages"][0]["files"]}
        self.assertEqual(stage_files["infra/rds.yaml"], overlay["infra/rds.yaml"])
        self.assertEqual(stage_files["docs/end-to-end.md"], "walkthrough\n")
        self.assertNotIn("infra/rds.yaml", plan["stages"][0]["delete_files"])

    def test_rejects_missing_required_aws_artifacts_for_stage_progression(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prompt_dir = root / "prompts"
            prompt_dir.mkdir()
            (root / "AGENTS.md").write_text("Teach with visible JSON.\n", encoding="utf-8")
            (prompt_dir / "07-api-gateway.md").write_text("API gateway stage.\n", encoding="utf-8")

            def fake_requester(generation_input, schema, model, api_key, base_url):
                return {
                    "stages": [
                        {
                            "name": "07-api-gateway",
                            "summary": "api gateway",
                            "files": [
                                {
                                    "path": "README.md",
                                    "content": self.stage_readme(
                                        "07-api-gateway",
                                        [
                                            "README.md",
                                            "deploy/ec2/run_inventory_server.sh",
                                            "deploy/ec2/environment.example",
                                            "infra/lambda.yaml",
                                            "deploy/lambda/README.md",
                                        ],
                                    ),
                                },
                                {"path": "deploy/ec2/run_inventory_server.sh", "content": "#!/usr/bin/env bash\n"},
                                {"path": "deploy/ec2/environment.example", "content": "PORT=8000\n"},
                                {"path": "infra/lambda.yaml", "content": "Resources: {}\n"},
                                {"path": "deploy/lambda/README.md", "content": "deploy lambda\n"},
                            ],
                            "delete_files": [],
                        }
                    ]
                }

            with self.assertRaisesRegex(ValueError, "missing required AWS deployment artifacts"):
                generate_all_apps(prompt_dir, root / "generated", api_key="test-key", requester=fake_requester)

    def test_regeneration_prunes_empty_directories_left_by_removed_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prompt_dir = root / "prompts"
            prompt_dir.mkdir()
            (root / "AGENTS.md").write_text("Teach with visible JSON.\n", encoding="utf-8")
            prompt_path = prompt_dir / "00-repository.md"
            prompt_path.write_text("Establish the repository.\n", encoding="utf-8")
            output_root = root / "generated"

            def first_requester(generation_input, schema, model, api_key, base_url):
                return {
                    "stages": [
                        {
                            "name": "00-repository",
                            "summary": "first",
                            "files": [
                                {"path": "README.md", "content": "# Setup\n"},
                                {"path": "orphan/only.txt", "content": "temp\n"},
                            ],
                            "delete_files": [],
                        }
                    ]
                }

            def second_requester(generation_input, schema, model, api_key, base_url):
                return {
                    "stages": [
                        {
                            "name": "00-repository",
                            "summary": "second",
                            "files": [{"path": "README.md", "content": "# Setup v2\n"}],
                            "delete_files": [],
                        }
                    ]
                }

            generate_projects(
                [prompt_path],
                [prompt_path],
                output_root,
                api_key="test-key",
                requester=first_requester,
            )
            self.assertTrue((output_root / "00-repository" / "orphan" / "only.txt").exists())

            generate_projects(
                [prompt_path],
                [prompt_path],
                output_root,
                api_key="test-key",
                requester=second_requester,
            )

            self.assertFalse((output_root / "00-repository" / "orphan").exists())


if __name__ == "__main__":
    unittest.main()
