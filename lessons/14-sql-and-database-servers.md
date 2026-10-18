# Session 14 — SQL, and a database is a process listening on a port

**Stage:** `08-relational-persistence` for SQL; the server half is manual · **Repo support:** Partly (SQL against SQLite works; there is nothing in the repo that installs or starts MariaDB/Postgres) · **Run from:** `08-relational-persistence/`

**Concept (20 min):** CREATE, INSERT, SELECT, UPDATE, DELETE; DB server vs client; a DB is a process listening on a port.
**Demo (20 min):** start MariaDB/Postgres on the Pi or EC2; `ps`/`ss`; create a table; load and query inventory.

## Run sheet

**Part A: the five statements, with SQLite (verified).**
```bash
TINYWMS_DB=sqlite TINYWMS_SQLITE_PATH=data/tinywms.db python3 -m data.init_db      # delete data/tinywms.db first if it exists
sqlite3 -header -column data/tinywms.db
```
```sql
SELECT * FROM inventory;
SELECT sku, quantity FROM inventory WHERE quantity < 10 ORDER BY quantity;
UPDATE inventory SET quantity = quantity - 1 WHERE sku = 'SKU-2001';
INSERT INTO inventory VALUES ('SKU-3000', 'Hammer', 'C1-01', 5, 'each');
DELETE FROM inventory WHERE sku = 'SKU-3000';
INSERT INTO inventory VALUES ('SKU-9', 'Bad', 'Z9', -1, 'each');     -- CHECK constraint failed
```
Do the same through Python (`import sqlite3`), then from the repo's own code path: `src/db_adapter.py` with `TINYWMS_DB=sqlite`.

**Part B: the server (manual, on the Pi or EC2).**
```bash
sudo apt install postgresql         # Raspberry Pi OS; on Amazon Linux: sudo dnf install postgresql15-server, then initdb
sudo systemctl status postgresql
ps aux | grep postgres              # a handful of processes, not one
ss -ltnp | grep 5432                # listening on 127.0.0.1:5432
sudo -u postgres psql               # the client, a different process, talks to the server over a socket
```
```sql
CREATE DATABASE tinywms;   \c tinywms
-- paste data/schema.sql, then data/seed.sql (or: \i data/schema.sql  \i data/seed.sql)
SELECT * FROM inventory;
```
Then repeat Part A's statements. The SQL is the same; the difference is that you are now talking to a process over a connection.
Postgres is the engine the app code targets (`psycopg2`, `FOR UPDATE`), so use Postgres rather than MariaDB. The Postgres steps above were not run for this plan.

## Talking points
- Client and server are separate programs. `sqlite3` opens a file inside your own process; Postgres is a server that many clients connect to, which is also what makes locking and concurrency (session 17) matter.
- Show the symmetry with HTTP: a port, a listening process, a client, a protocol. Re-use the `ss -ltnp` you taught in session 8.
- SQL statements: C-R-U-D, and what each returns (rows, or a row count).

## Caveats
- `init_db` fails on a second run (`table already exists`); remove the database file between runs.
- By default Postgres listens only on localhost; reaching it from another machine needs configuration plus a firewall rule, which sets up session 15's RDS networking.
