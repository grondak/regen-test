# Session 16 — The application/data boundary

**Stage:** `10-lambda-rds` (runs against SQLite locally; Postgres/RDS in the cloud) · **Repo support:** Yes · **Run from:** `20-final-walkthrough/` (same code as stage 10, plus the SQLite switch)

**Concept (20 min):** connections, queries, result sets, mapping rows → objects → JSON.
**Demo (20 min):** replace the Lambda's hard-coded JSON with a SQL query and serialize the result.

## Run sheet

**Step 1: read the code that crosses the boundary** in `src/lambda_inventory.py`:
- `INVENTORY_QUERY_SQL = 'SELECT sku, description, bin_location, quantity, unit FROM inventory ORDER BY sku'`
- `_open_default_connection()` in `lambda_inventory.py` chooses SQLite (`connect_sqlite()` in `src/db_adapter.py`) or Postgres from `TINYWMS_DB`
- `_map_inventory_row` turns a row (a tuple) into a dict, `json.dumps` turns that into the response body.

**Step 2: run the whole path locally against SQLite** (verified):
*Demo scripts: set `TINYWMS` and `LESSONS` first (see README → Running the demos).*
```bash
cd "$TINYWMS/20-final-walkthrough"
export TINYWMS_DB=sqlite TINYWMS_SQLITE_PATH=/tmp/tinywms.db
rm -f /tmp/tinywms.db
python3 -m data.init_db
PYTHONPATH=. python3 "$LESSONS/support/inventory_query_demo.py"        # statusCode 200, body is a JSON *string*, one dict per row
sqlite3 -header -column /tmp/tinywms.db "UPDATE inventory SET quantity = 99 WHERE sku='SKU-1001'"
PYTHONPATH=. python3 "$LESSONS/support/inventory_query_demo.py"        # same function, new data, no code change
```
Compare the response with session 11's: same envelope, same fields. Only the source changed.

**Or see it through the web page.** `bash deploy/local/run_local.sh --reset` serves the page and `GET /inventory` through the same handler against SQLite. Change a quantity with `sqlite3 local-aws/tinywms.db "UPDATE inventory SET quantity = 99 WHERE sku='SKU-1001'"` and press Refresh in the browser.

**Step 3: the same code against Postgres/RDS.** Set `TINYWMS_DB=postgres` and a `DATABASE_URL`, install `psycopg2-binary` (`requirements.txt`) and repeat. Not run for this plan (needs Postgres).

**What changed since the first draft of this lesson.** Calling `handler({}, None)` with no injected connection used to crash (`'_GeneratorContextManager' object has no attribute 'cursor'`) because the default factory was a context manager. It now uses a plain `_open_default_connection()`: SQLite when `TINYWMS_DB=sqlite`, otherwise Postgres from `DATABASE_URL`. This is fixed in stages 10–20, and `GET /inventory` on a deployed Lambda goes through the same path. The Postgres side is covered by the tests only through fakes, so try it once against a real database before class.

## Talking points
- Three representations, three boundaries: a database row (tuple) → a Python dict → a JSON string. Name the code line at each arrow.
- Parameters, not string pasting: `WHERE sku = %s` with a separate values tuple, never `f"... '{sku}'"`.
- Connection lifecycle: open, use, commit or roll back, close. Lambda creates one per invocation here.
- SQLite vs Postgres differences are hidden by the small adapter in `src/db_adapter.py` (placeholder style, `FOR UPDATE`), but the adapter is a teaching shortcut, not how production code would work.
