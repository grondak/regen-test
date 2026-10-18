# Session 18 — GET vs POST, request bodies, validation

**Stage:** `11-orders` · **Repo support:** Yes · **Run from:** `11-orders/`

**Concept (20 min):** GET vs POST; the form/request body; JSON payload; validation; HTTP success and error responses.
**Demo (20 min):** build the order form; inspect the browser request; POST order JSON with `curl` first, then from HTML.

## Run sheet

Use a copy of the inventory, because **the server rewrites its inventory file on every accepted order**:
```bash
cp data/inventory.json /tmp/inventory-demo.json
TINYWMS_INVENTORY_FILE=/tmp/inventory-demo.json python3 src/http_server.py
```

**Step 1: curl first** (all verified):
```bash
curl -s -w ' [%{http_code}]\n' -H 'Content-Type: application/json' \
  -d '{"order_id":"ORD-DEMO","lines":[{"sku":"SKU-1001","quantity":1}]}' http://127.0.0.1:8000/orders
# {"order_id": "ORD-DEMO", "status": "accepted"} [201]
curl -s http://127.0.0.1:8000/inventory          # SKU-1001 is now 23
curl -s -w ' [%{http_code}]\n' -d '{"order_id":"X","lines":[{"sku":"SKU-1001","quantity":999}]}' http://127.0.0.1:8000/orders
# {"error": "insufficient inventory for SKU-1001"} [409]
curl -s -w ' [%{http_code}]\n' -d '{"order_id":"X","lines":[]}' http://127.0.0.1:8000/orders
# {"error": "lines must be a non-empty array"} [409]
curl -s -w ' [%{http_code}]\n' -d 'not json' http://127.0.0.1:8000/orders
# {"error": "Expecting value: ..."} [409]
```
Contrast with session 6: GET asks for something and changes nothing, POST sends a body and causes a change.

**Step 2: the browser.** Open `http://127.0.0.1:8000/`. The page (`src/web/index.html`, `src/web/app.js`) shows the inventory table and a textarea with the order JSON. Open DevTools → Network, click **Submit order**, and open the `orders` request: method POST, request headers, request payload, `201` response. Then submit an impossible quantity and show the error.

**Step 3: read the validation** in `do_POST` (`src/http_server.py`): is the body JSON, is it an object, is `order_id` a non-empty string, is `lines` a non-empty array, is each `quantity` a positive integer? Everything is checked *before* inventory is touched.

## Talking points
- The request body is data you did not write; never trust it. Validate shape first, then business rules.
- Status codes carry meaning: 2xx worked, 4xx the client's request was wrong, 5xx the server broke.

## Caveats
- The server uses **409** for every failure, including malformed JSON and a missing field. Those should be 400. The `except json.JSONDecodeError` branch is never reached because `JSONDecodeError` is a subclass of `ValueError`, which is caught first. Present it as a "find the bug" exercise.
- Order IDs are not checked for duplicates here: posting the same order twice decrements twice. Foreshadows idempotency in session 23.
- This server still edits the JSON file, not a database. The database-backed order path is the Lambda (session 19).
