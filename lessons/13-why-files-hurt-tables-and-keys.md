# Session 13 — Why files eventually hurt; tables, rows and keys

**Stage:** `08-relational-persistence` · **Repo support:** Yes · **Run from:** `08-relational-persistence/`

**Concept (20 min):** why files hurt; table/row/column/type; primary and foreign keys; entity relationships; normalization only enough to prevent obvious duplication.
**Demo (20 min):** start from `inventory.json`; derive product, inventory and warehouse/bin; then sketch order and order_line.

## Run sheet

**Step 1: make the pain visible with the file you already have.** Use `data/inventory.json` and the tools from sessions 5–6:
- Two writers: run two copies of the session-5 snippet that read, change, and write back; the second silently erases the first's change.
- No types or rules: change a quantity to `"lots"` or `-5`; the file accepts it, the server serves it, the page shows it.
- No relationships: the bin is just text (`"A1-01"`) repeated in every row that uses it; nothing says which bins exist.
- Finding things: "everything in aisle A under 10 units" means loading the whole file every time.

**Step 2: show the same data as a table.**
```bash
cat data/schema.sql          # one table: inventory(sku PRIMARY KEY, description, bin_location, quantity CHECK >= 0, unit)
cat data/seed.sql
TINYWMS_DB=sqlite TINYWMS_SQLITE_PATH=data/tinywms.db python3 -m data.init_db
sqlite3 -header -column data/tinywms.db "SELECT * FROM inventory"
sqlite3 data/tinywms.db "INSERT INTO inventory VALUES ('SKU-3000','Hammer','C1-01',-5,'each')"      # CHECK constraint failed: the database refuses it
```
Compare the JSON object with the row: key → column, array of objects → rows, text/number → column types. Note `TEXT`, `INTEGER`, `NOT NULL`, `PRIMARY KEY`, `CHECK` as the rules the file never had.

**Step 3: derive a better model on the whiteboard.** Product (sku, description, unit), Bin (bin_location), Inventory (sku → bin, quantity). The stage-8 schema keeps everything in one table on purpose; students see what repeats and what could be split. Then sketch `orders(order_id, status)` and `order_lines(order_id, sku, quantity)` with the foreign keys; the real versions are in `20-final-walkthrough/data/schema.sql` and are used in session 19.

**Step 4 (optional): the generator.** `python3 src/sql_export.py data/inventory.json` prints INSERT statements built from the JSON; it builds SQL by pasting strings, so a description containing an apostrophe would break it. Use that as a one-line SQL-injection warning.

## Caveats
- `python3 -m data.init_db` is not repeatable: a second run fails with `table inventory already exists`. `rm data/tinywms.db` first. (Local mode, `bash deploy/local/run_local.sh`, creates its database the first time it starts and `--reset` recreates it, so it avoids this.)
- The stage-8 schema is a single table; the product/bin/warehouse split is a whiteboard exercise, not code in the repo.
- Stage 8 gives you SQLite, a file. The "database is a server on a port" point is session 14.
