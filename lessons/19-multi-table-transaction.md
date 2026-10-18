# Session 19 — A multi-table transaction

**Stage:** `11-orders` (concept) · **Repo support:** Yes · **Run from:** `20-final-walkthrough/`

**Concept (20 min):** a multi-table transaction: order, order lines, inventory update; validation and rollback.
**Demo (20 min):** walk one order through validation → insert → decrement → commit; deliberately fail another.

## Run sheet (verified)
*Demo scripts: set `TINYWMS` and `LESSONS` first (see README → Running the demos).*

**Through the web page and curl (the transaction you can watch).** Start local mode, post orders, and read the tables:
```bash
cd "$TINYWMS/20-final-walkthrough"
bash deploy/local/run_local.sh --reset
# second terminal, same folder:
curl -s -w ' [%{http_code}]\n' -d '{"order_id":"ORD-1","lines":[{"sku":"SKU-1001","quantity":2},{"sku":"SKU-2001","quantity":1}]}' localhost:8000/orders
curl -s -w ' [%{http_code}]\n' -d '{"order_id":"ORD-2","lines":[{"sku":"SKU-1002","quantity":1},{"sku":"SKU-2001","quantity":999}]}' localhost:8000/orders
curl -s -w ' [%{http_code}]\n' -d '{"order_id":"ORD-1","lines":[{"sku":"SKU-1002","quantity":1}]}' localhost:8000/orders
sqlite3 -header -column local-aws/tinywms.db "select * from inventory; select * from orders; select * from order_lines;"
```
The first is accepted (201), the second is rejected on its second line (409) and leaves SKU-1002 untouched, the third repeats an `order_id` and is rejected (409 `order already exists`). The tables show exactly one order and two lines.

**The same thing as a script that prints the stock after each order.** The real `place_order()` against a throwaway SQLite database, with in-memory stand-ins for SQS and EventBridge:
```bash
PYTHONPATH=.:"$LESSONS/support" python3 "$LESSONS/support/order_demo.py"
```
It places three orders and prints the stock after each:
1. `ORD-1` buys SKU-1001 ×2 and SKU-2001 ×1. **Accepted**; both stock numbers drop; a row appears in `orders` and two in `order_lines`.
2. `ORD-2` buys SKU-1002 ×1 (fine) and SKU-2001 ×999 (too many). **Rejected on line 2**; stock for SKU-1002 is unchanged, which proves the first line's decrement was rolled back.
3. `ORD-3` uses an unknown SKU. **Rejected**.

Then it prints the `orders` and `order_lines` tables, the pick-work messages and the `OrderPlaced` event that only the accepted order produced.

**Walk the code** in `src/lambda_inventory.py` → `place_order`:
1. `with transaction(connection):` opens the unit of work.
2. For each line: fetch the row `FOR UPDATE`, check stock, run the conditional `UPDATE`, check `rowcount`.
3. Insert the `orders` row, then one `order_lines` row per line.
4. Leaving the `with` block commits; any exception rolls everything back.
5. Only *after* commit does it send SQS commands and the event.

The schema (`data/schema.sql`) shows why order_lines has a composite primary key and foreign keys to `orders` and `inventory`: the database itself rejects an order line for a SKU that does not exist.

## Talking points
- The invariant: stock decrements and the order record agree, or neither exists.
- Validation vs business rules: shape of the request (400) vs "not enough stock" (409).
- Order matters: messages leave **after** the commit so a rolled-back order never sends a pick request.

## Caveat (feeds session 20)
- The commit and the queue publish are two separate steps. If the database commits and then the SQS send fails (for instance a missing IAM permission), the order exists and nobody is told to pick it. The code has no retry or outbox for that. You can reproduce it on one machine; see session 20, bullet 6.
- A repeated `order_id` is now rejected with 409 by the database's primary key on `orders`; the rollback undoes the stock changes.
