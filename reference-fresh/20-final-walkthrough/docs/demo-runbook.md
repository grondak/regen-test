# TinyWMS demo runbook

Run each session from its named stage directory. Commands lead with visible behavior; the listed test is an optional safety check after the demonstration.

## Session 1
**Backing stage:** 01-json-backbone
**Work type:** Partly manual

Goal: Print and inspect the canonical inventory JSON.

```bash
python3 src/inventory_cli.py data/inventory.json list
python3 src/inventory_cli.py data/inventory.json dump
```

Observe the command output or interface before continuing. Optional safety check: `tests/test_inventory_cli.py`.

Artifact link:
- `data/inventory.json`

## Session 2
**Backing stage:** 02-linux-visible
**Work type:** Partly manual

Goal: Observe environment variables, stdin, stdout, and exit status.

```bash
python3 src/linux_visible.py env
TINYWMS_DEMO=visible python3 src/linux_visible.py env
printf 'hello from stdin\n' | python3 src/linux_visible.py echo
python3 src/linux_visible.py fail; echo "exit code: $?"
```

Observe the command output or interface before continuing. Optional safety check: `tests/test_linux_visible.py`.

Artifact link:
- `src/linux_visible.py`

## Session 3
**Backing stage:** 02-linux-visible
**Work type:** Partly manual

Goal: Run a long-lived process and watch its visible output file.

```bash
python3 src/inventory_watcher.py data/inventory.json /tmp/tinywms-watch.log
tail -f /tmp/tinywms-watch.log
```

Observe the command output or interface before continuing. Optional safety check: `tests/test_linux_visible.py`.

Artifact link:
- `src/inventory_watcher.py`

## Session 4
**Backing stage:** 03-pi-http-server
**Work type:** Partly manual

Goal: Cross the first HTTP boundary and inspect response headers and JSON.

```bash
PYTHONPATH=src python3 src/http_server.py
curl -i http://127.0.0.1:8000/inventory
```

Observe the command output or interface before continuing. Optional safety check: `tests/test_http_server.py`.

Artifact link:
- `src/http_server.py`

## Session 5
**Backing stage:** 04-browser
**Work type:** Partly manual

Goal: Render the inventory JSON in a plain browser page.

```bash
PYTHONPATH=src python3 -m http.server --directory src/web 8081
# Open http://127.0.0.1:8081/ in a browser.
```

Observe the command output or interface before continuing. Optional safety check: `tests/test_web_app.js`.

Artifact link:
- `src/web/index.html`

## Session 6
**Backing stage:** 05-ec2-deployment
**Work type:** Manual only

Goal: Identify what moves unchanged from Raspberry Pi Linux to EC2 Linux.

```bash
sed -n '1,220p' deploy/ec2/README.md
bash -n deploy/ec2/run_inventory_server.sh
```

Observe the command output or interface before continuing. Optional safety check: `tests/test_ec2_deployment_files.py`.

Artifact link:
- `deploy/ec2/README.md`

## Session 7
**Backing stage:** 06-lambda
**Work type:** Partly manual

Goal: Invoke the Lambda-shaped inventory boundary and inspect its JSON envelope.

```bash
PYTHONPATH=. python3 -c "import json; from src.lambda_inventory import handler; print(json.dumps(handler({'queryStringParameters': {'demo': 'local-json'}}, None), indent=2))"
```

Observe the command output or interface before continuing. Optional safety check: `tests/test_lambda_inventory.py`.

Artifact link:
- `src/lambda_inventory.py`

## Session 8
**Backing stage:** 07-api-gateway
**Work type:** Manual only

Goal: Trace the HTTP route from API Gateway to the Lambda handler.

```bash
sed -n '1,240p' infra/api-gateway.yaml
sed -n '1,220p' deploy/api-gateway/README.md
```

Observe the command output or interface before continuing. Optional safety check: `tests/test_api_gateway_files.py`.

Artifact link:
- `infra/api-gateway.yaml`

## Session 9
**Backing stage:** 08-relational-persistence
**Work type:** Partly manual

Goal: Create the SQLite classroom database from the visible schema and seed.

```bash
TINYWMS_DB=sqlite TINYWMS_SQLITE_PATH=data/tinywms.db python3 -m data.init_db
```

Observe the command output or interface before continuing. Optional safety check: `tests/test_relational_persistence.py`.

Artifact link:
- `data/schema.sql`

## Session 10
**Backing stage:** 08-relational-persistence
**Work type:** Partly manual

Goal: Query relational rows and compare them with the JSON records.

```bash
python3 -c "import sqlite3, json; print(json.dumps(sqlite3.connect('data/tinywms.db').execute('SELECT * FROM inventory ORDER BY sku').fetchall(), indent=2))"
```

Observe the command output or interface before continuing. Optional safety check: `tests/test_sql_export.py`.

Artifact link:
- `data/seed.sql`

## Session 11
**Backing stage:** 09-rds
**Work type:** Manual only

Goal: Compare self-managed database work with the managed RDS boundary.

```bash
sed -n '1,260p' deploy/rds/README.md
sed -n '1,260p' infra/rds.yaml
```

Observe the command output or interface before continuing. Optional safety check: `tests/test_rds_deployment.py`.

Artifact link:
- `deploy/rds/README.md`

## Session 12
**Backing stage:** 10-lambda-rds
**Work type:** Partly manual

Goal: Follow the Lambda inventory query from JSON response to PostgreSQL rows.

```bash
sed -n '1,260p' src/lambda_inventory.py
sed -n '1,220p' docs/data-contracts.md
```

Observe the command output or interface before continuing. Optional safety check: `tests/test_lambda_inventory.py`.

Artifact link:
- `tests/test_lambda_inventory.py`

## Session 13
**Backing stage:** 11-orders
**Work type:** Partly manual

Goal: Use one browser page to view inventory, submit an order, and see inventory refresh.

```bash
TINYWMS_DB=sqlite TINYWMS_SQLITE_PATH=data/tinywms.db python3 -m data.init_db
PYTHONPATH=src python3 src/http_server.py
# Open the server URL in a browser and submit the visible order JSON.
```

Observe the command output or interface before continuing. Optional safety check: `tests/test_http_order_flow.py`.

Artifact link:
- `src/web/index.html`

## Session 14
**Backing stage:** 11-orders
**Work type:** Partly manual

Goal: Submit visible order JSON with curl, then observe the changed inventory.

```bash
curl -s -H 'Content-Type: application/json' -d '{"order_id":"ORD-DEMO","lines":[{"sku":"SKU-1001","quantity":1}]}' http://127.0.0.1:8000/orders
curl -s http://127.0.0.1:8000/inventory
```

Observe the command output or interface before continuing. Optional safety check: `tests/test_http_order_flow.py`.

Artifact link:
- `src/http_server.py`

## Session 15
**Backing stage:** 12-concurrency
**Work type:** Partly manual

Goal: Run overlapping order attempts and compare SQLite with PostgreSQL row locking.

```bash
python3 src/concurrency_demo.py
```

Observe the command output or interface before continuing. Optional safety check: `tests/test_concurrency.py`.

Artifact link:
- `tests/test_concurrency.py`

## Session 16
**Backing stage:** 13-sqs
**Work type:** Partly manual

Goal: Inspect the per-line pick-work command JSON sent after commit.

```bash
python3 -m json.tool data/pick-work.json
sed -n '1,260p' src/sqs_consumer.py
```

Observe the command output or interface before continuing. Optional safety check: `tests/test_sqs_consumer.py`.

Artifact link:
- `tests/test_sqs_consumer.py`

## Session 17
**Backing stage:** 14-domain-events
**Work type:** Partly manual

Goal: Compare the imperative SQS command with the descriptive OrderPlaced event.

```bash
sed -n '1,280p' docs/data-contracts.md
sed -n '1,260p' infra/events.yaml
```

Observe the command output or interface before continuing. Optional safety check: `tests/test_event_consumers.py`.

Artifact link:
- `tests/test_event_consumers.py`

## Session 18
**Backing stage:** 15-pick-ticket-worker
**Work type:** Manual only

Goal: Run the long-lived worker against a configured queue and watch ticket output.

```bash
python3 src/pick_ticket_worker.py "$PICK_WORK_QUEUE_URL" pick-tickets.txt --state-file pick-ticket-worker-state.json
tail -f pick-tickets.txt
```

Observe the command output or interface before continuing. Optional safety check: `tests/test_pick_ticket_worker.py`.

Artifact link:
- `tests/test_pick_ticket_worker.py`

## Session 19
**Backing stage:** 15-pick-ticket-worker
**Work type:** Manual only

Goal: Operate the worker as a user service and inspect its logs.

```bash
systemctl --user status tinywms-pick-ticket-worker
journalctl --user -u tinywms-pick-ticket-worker.service -f
```

Observe the command output or interface before continuing. Optional safety check: `tests/test_pick_ticket_worker.py`.

Artifact link:
- `deploy/pick-ticket-worker/README.md`

## Session 20
**Backing stage:** 16-callback-demo
**Work type:** Partly manual

Goal: Follow one accepted order across HTTP, queue receipt, worker callback, and ticket file.

```bash
sed -n '1,260p' docs/end-to-end.md
tail -f pick-tickets.txt
```

Observe the command output or interface before continuing. Optional safety check: `tests/test_callback_integration.py`.

Artifact link:
- `docs/end-to-end.md`

## Session 21
**Backing stage:** 17-container-worker
**Work type:** Partly manual

Goal: Build the same worker code into a container image.

```bash
docker build -t tinywms-pick-ticket-worker -f src/Dockerfile .
```

Observe the command output or interface before continuing. Optional safety check: `tests/test_container_worker.py`.

Artifact link:
- `deploy/container-worker/README.md`

## Session 22
**Backing stage:** 17-container-worker
**Work type:** Manual only

Goal: Run the container with durable ticket and idempotency files mounted.

```bash
docker run --rm -e PICK_WORK_QUEUE_URL="$PICK_WORK_QUEUE_URL" -v "$PWD/data:/state" tinywms-pick-ticket-worker "$PICK_WORK_QUEUE_URL" /state/pick-tickets.txt --state-file /state/pick-ticket-worker-state.json --once
```

Observe the command output or interface before continuing. Optional safety check: `tests/test_container_worker.py`.

Artifact link:
- `deploy/container-worker/README.md`

## Session 23
**Backing stage:** 18-aws-deployment
**Work type:** Manual only

Goal: Inspect how Lambda, API Gateway, RDS, SQS, EventBridge, and IAM are assembled.

```bash
sed -n '1,320p' infra/template.yaml
sed -n '1,320p' deploy/aws/README.md
```

Observe the command output or interface before continuing. Optional safety check: `tests/test_deployment_wiring.py`.

Artifact link:
- `infra/template.yaml`

## Session 24
**Backing stage:** 18-aws-deployment
**Work type:** Manual only

Goal: Package, deploy, verify, and later destroy the real application stack using the documented commands.

```bash
sed -n '1,320p' deploy/aws/README.md
# Follow its package/deploy steps, then curl the resolved API URL.
```

Observe the command output or interface before continuing. Optional safety check: `tests/test_aws_deployment_files.py`.

Artifact link:
- `deploy/aws/README.md`

## Session 25
**Backing stage:** 19-git-history
**Work type:** Partly manual

Goal: Compare two stage directories without inventing repository tags.

```bash
git diff --no-index ../18-aws-deployment ../19-git-history || true
sed -n '1,260p' docs/git-history.md
```

Observe the command output or interface before continuing. Optional safety check: `tests/test_deployment_wiring.py`.

Artifact link:
- `docs/git-history.md`

## Session 26
**Backing stage:** 20-final-walkthrough
**Work type:** Partly manual

Goal: Repeat the complete local order journey, then use the boundary guide for cloud demonstrations.

```bash
PYTHONPATH=src python3 src/http_server.py
curl -s http://127.0.0.1:8000/inventory
node --test tests/test_web_app.js
```

Observe the command output or interface before continuing. Optional safety check: `tests/test_demo_runbook.py`.

Artifact link:
- `docs/end-to-end.md`
