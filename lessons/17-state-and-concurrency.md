# Session 17 — State, atomicity and concurrency

**Stage:** `12-concurrency` · **Repo support:** Yes (a runnable race demo is in `lessons/support/`, the repo's own demo only shows the protected path) · **Run from:** `20-final-walkthrough/`

**Concept (20 min):** state, atomicity, commit, rollback, concurrency. Two workers order the last hammer.
**Demo (20 min):** reproduce the naive read-then-update failure; demonstrate a transactional/conditional update.

## Run sheet

**Step 1: reproduce the bug (verified).** One hammer, two buyers, two threads with their own connections:
```bash
python3 ../lessons/support/race_demo.py
```
Expected output:
```
naive read-then-update       {... both 'ACCEPTED'}  final stock=0  accepted=2 of 1 hammer
conditional UPDATE           {... one 'ACCEPTED', one 'rejected'}  final stock=0  accepted=1 of 1 hammer
```
Read the file together. In the naive version each buyer reads `quantity=1`, decides in Python, and writes `quantity=0`; both succeed. In the conditional version the database applies `UPDATE ... SET quantity = quantity - 1 WHERE quantity >= 1` as a single atomic step and reports `rowcount` (1 = I got it, 0 = nothing left).

**Step 2: show that the real code uses the safe form.** In `src/lambda_inventory.py`:
```
SELECT ... FROM inventory WHERE sku = %s FOR UPDATE                                   # lock the row until commit (Postgres)
UPDATE inventory SET quantity = quantity - %s WHERE sku = %s AND quantity >= %s       # conditional decrement
if cursor.rowcount != 1: raise InventoryShortageError(...)
```

**Step 3: the repo's own demo (also verified).** It runs two real `place_order` calls against a *fake* cursor that holds both at the lock request and applies the guarded UPDATE, so the output always shows one accepted and one rejected:
```bash
PYTHONPATH=. python3 src/concurrency_demo.py
```
Walk the log it prints: both threads request the lock, one UPDATE succeeds, one commit, one rollback.

**Step 4 (needs Postgres):** run two `psql` sessions, `BEGIN; SELECT ... FOR UPDATE;` in the first, and watch the second block until the first commits. This shows the lock for real; SQLite cannot, it locks the whole file.

## Talking points
- Atomic: all of a transaction happens or none of it does. `COMMIT` makes it durable, `ROLLBACK` throws it away.
- The race is in the gap between *reading* and *writing*. Close the gap by moving the decision into the database (the `WHERE quantity >= 1` condition) or lock the row until you finish.
- The repo's `concurrency_demo.py` does not reproduce the bug; it demonstrates the fix. Use `race_demo.py` for the "before".
