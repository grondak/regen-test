# Stage 11: Introduce orders

Extend the JSON contracts with a minimal warehouse order representation. Evolve the existing plain HTML
inventory page into one integrated inventory-and-order page that submits an order as JSON through
`POST /orders`. The page must show the request JSON and response JSON, refresh `GET /inventory` after an
accepted order, and visibly show the changed quantity. Do not make a separate order-only page the primary
workflow.

Preserve `src/order_form.html` as a small historical/contract comparison artifact when the course blueprint
requires it, but make `src/web/index.html` plus `src/web/app.js` the documented and tested primary workflow.
The standalone form must not replace or bypass the integrated inventory → order → refreshed inventory path.

Use a same-origin API base by default with one explicit runtime override suitable for an output-resolved
API Gateway URL. The final browser code must not hard-code `localhost` or `127.0.0.1`.

Evolve the local Python HTTP application so it serves the browser assets and supports both
`GET /inventory` and `POST /orders` with the same visible JSON contracts. Keep this local teaching path
small and explicit. Add a local HTTP integration test that starts the server on an ephemeral port,
submits an order, and proves a later inventory response contains the decremented quantity.
When the server reports an OS-assigned port, its readiness `print(...)` call must include the literal
keyword argument `flush=True`; tests must not block on buffered subprocess output. Tests must redirect
the inventory path to a temporary file and must never
mutate the checked-in `data/inventory.json`.

Implement Lambda handling that validates the request, creates an order and order lines, and decrements
inventory transactionally.

Evolve `data/schema.sql` in this stage to add `orders(order_id, status)` and
`order_lines(order_id, sku, quantity)`. Require a primary key on `orders.order_id`, foreign keys from
order lines to both `orders` and `inventory`, and a positive-quantity `CHECK`. Update the initializer so
both SQLite and PostgreSQL create the complete schema.

Add `tests/test_sqlite_orders.py` using a real temporary SQLite database and the real `place_order` path.
It must prove accepted-order persistence and inventory decrement, insufficient-inventory rollback, and
unknown-SKU rollback without PostgreSQL, AWS, or network access. Preserve both tuple-row and mapping-row
support. Mapping rows use canonical `bin_location`; the later pick-work JSON contract may still expose
that value as `bin`.
Keep the Stage 8 module-form initializer command runnable after the schema evolves:
`TINYWMS_DB=sqlite TINYWMS_SQLITE_PATH=data/tinywms.db python3 -m data.init_db`.

Treat `src/lambda_inventory.py` and `tests/test_sqlite_orders.py` as one atomic API change. If the test
imports `OrderLine` or `OrderRequest` from `src.lambda_inventory`, define and export those dataclasses in
that module (using the final reference's simple `sku`/`quantity`/`description` line shape and
`order_id`/`lines` request shape). Otherwise, construct orders only through a function that the emitted
module actually exports. Before returning the plan, compare every `from src.lambda_inventory import ...`
name in all emitted tests against the module's top-level definitions and imports.

This stage stops at the synchronous order transaction. Do not copy later-stage SQS or EventBridge behavior
from the final reference: no `send_message(...)`, `put_events(...)`, queue URL, event bus, or boto3 client
factory belongs in this stage. Tests must call only names actually exported by the Stage 11 source. When a
test checks validation text, make the assertion agree with the emitted field-specific error instead of
inventing generic prose such as "invalid order".

Keep the SQL visible in the handler or a small adjacent module: the implementation must insert the order and order lines, guard/decrement inventory in the same database transaction, call commit only after all writes succeed, and call rollback on rejection or failure. Tests must exercise both commit and rollback with an injected/fake database connection; an in-memory calculation that never persists rows does not satisfy this lesson.

Reject insufficient inventory cleanly. Demonstrate rollback behavior. Keep `GET /inventory` compatible with everything already built.

Preserve every tested Stage 10 `GET /inventory` behavior verbatim, including `bin_location` in returned
JSON and the explicitly named `demo=local-json` teaching path. Validate a malformed order before opening
a database connection; tests should prove that no connection was acquired, not expect an unused injected
connection to be closed.

If this stage changes any AWS-deployed request path (API/Lambda/DB/queue-facing behavior), update the relevant CloudFormation template(s) and deployment README commands in the same stage so the cloud path remains runnable, not just locally testable.

Update `docs/architecture.md` "Component Assembly Map" to add order-entry/order-transaction components and show their dependencies on API Gateway/Lambda and relational persistence.

The stage README must include purpose, file map, run/test commands, order-validation exercises, cleanup
notes, continuity note, and a "Component assembly update" section. Do not emit placeholder README text.
