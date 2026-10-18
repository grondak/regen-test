# Session 18 — GET vs POST, request bodies, validation

**Stage:** `11-orders` · **Repo support:** Yes · **Run from:** `11-orders/`

**Concept (20 min):** GET vs POST; the form/request body; JSON payload; validation; HTTP success and error responses.
**Demo (20 min):** build the order form; inspect the browser request; POST order JSON with `curl` first, then from HTML.

## Run sheet

Two ways to start the server; the curl commands below work against either.

**A. The stage-11 server (file-backed).** Use a copy of the inventory, because **this server rewrites its inventory file on every accepted order**:
```bash
cd "$TINYWMS/11-orders"
cp data/inventory.json /tmp/inventory-demo.json
TINYWMS_INVENTORY_FILE=/tmp/inventory-demo.json python3 src/http_server.py
```

**B. Local mode (database-backed, the better demo).** The same page and the same `POST /orders`, but answered by the Lambda handler against SQLite, with proper status codes and no file rewriting. Stage 11 has it too:
```bash
cd "$TINYWMS/11-orders"            # or any stage up to 20-final-walkthrough
bash deploy/local/run_local.sh --reset
```
Afterwards look at what the order did: `sqlite3 -header -column local-aws/tinywms.db "select * from orders; select * from order_lines;"`.

**Step 1: curl first** (all verified):
```bash
curl -s -w ' [%{http_code}]\n' -H 'Content-Type: application/json' \
  -d '{"order_id":"ORD-DEMO","lines":[{"sku":"SKU-1001","quantity":1}]}' http://127.0.0.1:8000/orders
# {"order_id": "ORD-DEMO", "status": "accepted"} [201]
curl -s http://127.0.0.1:8000/inventory          # SKU-1001 is now 23
curl -s -w ' [%{http_code}]\n' -d '{"order_id":"X","lines":[{"sku":"SKU-1001","quantity":999}]}' http://127.0.0.1:8000/orders
# {"error": "insufficient inventory for SKU-1001"} [409]
curl -s -w ' [%{http_code}]\n' -d '{"order_id":"X","lines":[]}' http://127.0.0.1:8000/orders
# {"error": "lines must be a non-empty array"} [409]      (local mode: same message, [400])
curl -s -w ' [%{http_code}]\n' -d 'not json' http://127.0.0.1:8000/orders
# {"error": "Expecting value: ..."} [409]      (local mode: {"error": "request body must be JSON"} [400])
```
Contrast with session 6: GET asks for something and changes nothing, POST sends a body and causes a change.

**Step 2: the browser.** Open `http://127.0.0.1:8000/`. The page (`src/web/index.html`, `src/web/app.js`) shows the inventory table and a textarea with the order JSON. Open DevTools → Network, click **Submit order**, and open the `orders` request: method POST, request headers, request payload, `201` response. Then submit an impossible quantity and show the error.

**Step 3: read the validation** in `do_POST` (`src/http_server.py`): is the body JSON, is it an object, is `order_id` a non-empty string, is `lines` a non-empty array, is each `quantity` a positive integer? Everything is checked *before* inventory is touched.

## Talking points
- The request body is data you did not write; never trust it. Validate shape first, then business rules.
- Status codes carry meaning: 2xx worked, 4xx the client's request was wrong, 5xx the server broke.

## Caveats
- **Option A** uses **409** for every failure, including malformed JSON and a missing field; those should be 400. The `except json.JSONDecodeError` branch in `do_POST` is never reached because `JSONDecodeError` is a subclass of `ValueError`, which is caught first. Present it as a "find the bug" exercise. **Option B** returns 400 for a malformed or invalid request and 409 for a shortage, an unknown SKU or a repeated `order_id`.
- Option A does not check order IDs: posting the same order twice decrements twice. In option B the second post is rejected with 409 `order already exists`. This foreshadows idempotency in session 23.
- Option A edits the JSON file; option B edits the database (session 19 looks inside the transaction).
- The curl lines above call the order `ORD-DEMO` each time; with option B, either change the `order_id` or use `--reset` between runs.
