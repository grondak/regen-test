# TinyWMS end-to-end walkthrough

This walkthrough traces one warehouse order through the assembled TinyWMS system using only connections that are backed by source code, tests, infrastructure, or runnable commands in this repository.

## The order we will trace
We will trace a single example order:

```json
{
  "order_id": "ORD-1001",
  "lines": [
    {"sku": "SKU-1001", "quantity": 1}
  ]
}
```

## Component-by-component walk-through

### 1. Browser inventory and order page
- **Executing code:** `src/web/index.html` and `src/web/app.js`
- **Compute environment:** a desktop browser or other browser with JavaScript enabled
- **Input JSON:** the page loads inventory JSON from `GET /inventory` and prepares order JSON in the text area
- **Output JSON:** visible inventory JSON, visible order JSON, and visible error text when something fails
- **Network boundary:** same-origin `fetch()` calls to the HTTP server
- **Persistent state:** none in the browser itself
- **Possible failure:** invalid JSON, network failure, or a rejected order response
- **Responsible operator/provider:** the student or browser operator

### 2. Local HTTP walkthrough server
- **Executing code:** `src/http_server.py`
- **Compute environment:** a local Python process listening on `127.0.0.1`
- **Input JSON:** `GET /inventory` and `POST /orders`
- **Output JSON:** inventory JSON on GET, accepted-order JSON on POST, or error JSON on failure
- **Network boundary:** browser-to-server HTTP over localhost
- **Persistent state:** the mutable inventory file selected by `TINYWMS_INVENTORY_FILE`
- **Possible failure:** malformed JSON, unknown SKU, or insufficient inventory
- **Responsible operator/provider:** the student running the local walkthrough server

### 3. Lambda order handler
- **Executing code:** `src/lambda_inventory.py`
- **Compute environment:** AWS Lambda
- **Input JSON:** API Gateway proxy events for `GET /inventory` and `POST /orders`
- **Output JSON:** HTTP-style response objects with JSON bodies and status codes
- **Network boundary:** API Gateway invoke boundary
- **Persistent state:** the database-backed inventory, orders, and order lines
- **Possible failure:** validation failure, database failure, or publish failure
- **Responsible operator/provider:** the course operator configuring the function and AWS permissions

### 4. Relational database transaction
- **Executing code:** SQL constants and transaction logic in `src/lambda_inventory.py`
- **Compute environment:** PostgreSQL on Amazon RDS or a compatible test double in unit tests
- **Input JSON:** the order request body before it is mapped to SQL parameters
- **Output JSON:** no direct JSON; the handler emits HTTP-style JSON only after commit or error handling
- **Network boundary:** database connection over TCP
- **Persistent state:** inventory rows, orders, and order_lines rows
- **Possible failure:** shortage, deadlock, or connectivity failure
- **Responsible operator/provider:** AWS for the managed database; the course operator for schema and credentials

### 5. SQS pick-work command
- **Executing code:** the post-commit publish path in `src/lambda_inventory.py`
- **Compute environment:** AWS Lambda publishing to AWS SQS
- **Input JSON:** a pick-work command built from the committed order and inventory row
- **Output JSON:** queue message JSON containing `command_id`, `order_id`, `sku`, `description`, `quantity`, and `bin`
- **Network boundary:** Lambda-to-SQS service API
- **Persistent state:** the SQS queue stores the message until a worker consumes it
- **Possible failure:** permission failure or publish failure
- **Responsible operator/provider:** AWS for the queue service; the operator for queue configuration

### 6. EventBridge OrderPlaced event
- **Executing code:** the post-commit event publish path in `src/lambda_inventory.py`
- **Compute environment:** AWS Lambda publishing to AWS EventBridge
- **Input JSON:** a versioned `OrderPlaced` event detail payload
- **Output JSON:** an EventBridge entry with `Source`, `DetailType`, `Detail`, and `EventBusName`
- **Network boundary:** Lambda-to-EventBridge service API
- **Persistent state:** EventBridge routing and any configured consumers or archives
- **Possible failure:** publish failure or rule-matching failure
- **Responsible operator/provider:** AWS for the service; the operator for bus and rule configuration

### 7. Pick-ticket worker
- **Executing code:** `src/pick_ticket_worker.py`
- **Compute environment:** a Linux process or container on Linux
- **Input JSON:** the pick-work message body from the queue
- **Output JSON:** none; the worker writes a readable ticket line and updates worker state
- **Network boundary:** queue consumer boundary between SQS and the worker process
- **Persistent state:** `pick-tickets.txt` and the optional worker state file
- **Possible failure:** malformed queue message, missing file permissions, or process interruption
- **Responsible operator/provider:** the student or operator running the worker

### 8. Pick ticket file
- **Executing code:** the local filesystem on the worker host
- **Compute environment:** Linux filesystem
- **Input JSON:** none directly; the worker has already converted the queue message into text
- **Output JSON:** none
- **Network boundary:** none; this is a local storage boundary
- **Persistent state:** `pick-tickets.txt`
- **Possible failure:** disk full or accidental deletion
- **Responsible operator/provider:** the host operator

## What the tests prove
The repository includes focused tests that keep the walkthrough truthful:
- `tests/test_callback_integration.py` exercises the local HTTP server, the Lambda order handler, the SQS publish payload, the EventBridge publish payload, and the pick-ticket worker output path.
- `tests/test_http_order_flow.py` proves the local HTTP server accepts an order and refreshes inventory with the new quantity.
- `tests/test_lambda_inventory.py` proves the Lambda order path still produces the established inventory, order, command, and event contracts.
- `tests/test_pick_ticket_worker.py` proves durable ticket writing, idempotency, restart behavior, and acknowledgement boundaries.
- `tests/test_sqs_consumer.py` proves the shared queue helper receives, decodes, and acknowledges each message only after successful callback completion.
- `tests/test_event_consumers.py` proves the two EventBridge consumers can independently receive and decode delivered event JSON.
- `infra/template.yaml` defines the deployed Lambda environment, queue, bus, rules, targets, and permissions that the later cloud lessons reuse.

## Runnable commands
From the repository root, the visible commands are:

### Local walkthrough server
```bash
python3 src/http_server.py
```

### Local integration proof
```bash
PYTHONPATH=src python3 -m unittest tests.test_callback_integration -v
```

### HTTP order flow proof
```bash
PYTHONPATH=src python3 -m unittest tests.test_http_order_flow -v
```

### Deployment wiring proof
```bash
PYTHONPATH=src python3 -m unittest tests.test_deployment_wiring -v
```

### Worker against a queue URL
```bash
python3 src/pick_ticket_worker.py <queue-url> pick-tickets.txt --once
```

### Full repository tests
```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

## What this walkthrough intentionally does not claim
This walkthrough does not invent extra services or hidden implementation details. It only describes connections that are visible in the source tree, verified by tests, or declared in the CloudFormation template and runnable commands above.
