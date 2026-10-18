"""Two buyers want the last hammer. Naive read-then-update vs a conditional update.

Self-contained (SQLite, two threads, two connections). No repo code needed.
    python3 race_demo.py
"""
import os
import sqlite3
import tempfile
import threading
import time


def fresh_db():
    path = os.path.join(tempfile.mkdtemp(), 'race.db')
    c = sqlite3.connect(path)
    c.execute('CREATE TABLE inventory (sku TEXT PRIMARY KEY, quantity INTEGER NOT NULL CHECK (quantity >= 0))')
    c.execute("INSERT INTO inventory VALUES ('HAMMER', 1)")
    c.commit()
    c.close()
    return path


def naive(path, buyer, results):
    c = sqlite3.connect(path, timeout=10)
    (qty,) = c.execute("SELECT quantity FROM inventory WHERE sku='HAMMER'").fetchone()   # 1. read
    time.sleep(0.2)                                                                       # (both buyers read before either writes)
    if qty >= 1:                                                                          # 2. decide in Python
        c.execute("UPDATE inventory SET quantity=? WHERE sku='HAMMER'", (qty - 1,))       # 3. write a value computed from a stale read
        c.commit()
        results[buyer] = 'ACCEPTED'
    else:
        results[buyer] = 'rejected'


def conditional(path, buyer, results):
    c = sqlite3.connect(path, timeout=10)
    cur = c.execute("UPDATE inventory SET quantity = quantity - 1 WHERE sku='HAMMER' AND quantity >= 1")
    c.commit()
    results[buyer] = 'ACCEPTED' if cur.rowcount == 1 else 'rejected'                      # the database decides, atomically


def run(label, fn):
    path, results = fresh_db(), {}
    threads = [threading.Thread(target=fn, args=(path, b, results)) for b in ('buyer-A', 'buyer-B')]
    [t.start() for t in threads]
    [t.join() for t in threads]
    (final,) = sqlite3.connect(path).execute("SELECT quantity FROM inventory").fetchone()
    print(f'{label:<28} {results}  final stock={final}  accepted={list(results.values()).count("ACCEPTED")} of 1 hammer')


run('naive read-then-update', naive)
run('conditional UPDATE', conditional)
