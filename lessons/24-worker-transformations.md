# Session 24 — Long-running workers and output

**Stage:** `15-pick-ticket-worker` · **Repo support:** Yes · **Run from:** `20-final-walkthrough/`

**Concept (20 min):** transformations, long-running workers, file output, stdout/stderr, operational separation from the web request.
**Demo (20 min):** consume an order → look up or receive the bin → format a pick ticket → append to a file.

## Run sheet

**Step 1: the transformation in isolation (verified).**
```bash
PYTHONPATH=. python3 -c "
import json
from src.pick_ticket_worker import format_ticket
work = json.load(open('data/pick-work.json'))
print(json.dumps(work, indent=2))
print(format_ticket(work))
"
```
The input is the command JSON; the output is one line: `command_id=... order_id=... sku=... description=... quantity=... bin=...`. Edit `format_ticket` to change the layout (for example put `bin` first, since the picker walks to the bin first) and rerun.

**Step 2: the whole worker, offline (verified).**
```bash
PYTHONPATH=.:../lessons/support python3 ../lessons/support/worker_demo.py
```
In a second terminal while it runs, or after it finishes: `cat` the ticket file it prints the path of. On the real worker use `tail -f pick-tickets.txt`.

**Step 3: the real worker against a real queue (needs AWS credentials; not run for this plan).**
```bash
PYTHONPATH=. python3 -m src.pick_ticket_worker "$PICK_WORK_QUEUE_URL" pick-tickets.txt --state-file pick-ticket-worker-state.json
tail -f pick-tickets.txt          # second terminal
# place an order from the page or with curl (session 18/19) and watch tickets appear
```
Use `--once` to poll one batch and exit; Ctrl+C or SIGTERM stops it between batches.

## Talking points
- The "bin lookup" is already done upstream: the command carries the bin, copied from the locked inventory row at order time. The worker does no database access, so it can run anywhere that can reach the queue.
- Separation: the web request ends when the order commits and messages are queued; picking happens on a different machine, at a different pace. If the worker is slow the user doesn't notice.
- Streams: stdout shows what the worker is doing (it prints each ticket and each message's metadata), the ticket file is the durable output, stderr is for failures. Students saw this split in session 4.
- Signals: the worker catches SIGINT and SIGTERM and finishes its current batch, which is what makes `systemctl stop` safe.

## Caveats
- Run the worker with `-m src.pick_ticket_worker` or with `PYTHONPATH=.`. Running `python3 src/pick_ticket_worker.py` directly fails with `ModuleNotFoundError: No module named 'src'`, because the file imports `src.sqs_consumer`. The stage-20 runbook shows the failing form.
- `deploy/aws/README.md` step 6 (`python3 src/pick_ticket_worker.py data/pick-work.json pick-tickets.txt`) passes a JSON file where the queue URL goes; do not use it.
- The sample command in `data/pick-work.json` uses `SKU-001`, which is not a seeded SKU (the seed has `SKU-1001`, `SKU-1002`, `SKU-2001`). An order for `SKU-001`, as in `deploy/aws/README.md`'s curl example, will be rejected as an unknown SKU.
