# Session 24 — Long-running workers and output

**Stage:** `15-pick-ticket-worker` · **Repo support:** Yes · **Run from:** `20-final-walkthrough/`

**Concept (20 min):** transformations, long-running workers, file output, stdout/stderr, operational separation from the web request.
**Demo (20 min):** consume an order → look up or receive the bin → format a pick ticket → append to a file.

## Run sheet
*Demo scripts: set `TINYWMS` and `LESSONS` first (see README → Running the demos).*

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
PYTHONPATH=.:"$LESSONS/support" python3 "$LESSONS/support/worker_demo.py"
```
In a second terminal while it runs, or after it finishes: `cat` the ticket file it prints the path of. On the real worker use `tail -f pick-tickets.txt`.

**Step 2b: the real worker against the local queue, the whole path (verified).**
```bash
cd "$TINYWMS/20-final-walkthrough"
bash deploy/local/run_local.sh --reset         # starts the server AND the worker
# second terminal, same folder:
tail -F pick-tickets.txt
# submit an order in the page at http://127.0.0.1:8000/ and watch the ticket lines appear
```
To run the worker on its own, in a third terminal (start the server without the worker first, e.g. `TINYWMS_LOCAL=1 python3 src/http_server.py`):
```bash
export TINYWMS_LOCAL=1
python3 src/pick_ticket_worker.py local-aws/pick-work pick-tickets.txt --state-file local-aws/pick-ticket-worker-state.json --wait-time-seconds 2
```
`TINYWMS_LOCAL=1` is the only thing that changes where the queue is; the queue URL argument becomes a folder path.

**Step 3: the real worker against a real queue (needs AWS credentials; not run for this plan).**
```bash
PYTHONPATH=. python3 -m src.pick_ticket_worker "$PICK_WORK_QUEUE_URL" pick-tickets.txt --state-file pick-ticket-worker-state.json
tail -F pick-tickets.txt          # second terminal
# place an order from the page or with curl (session 18/19) and watch tickets appear
```
Use `--once` to poll one batch and exit; Ctrl+C or SIGTERM stops it between batches.

## Talking points
- The "bin lookup" is already done upstream: the command carries the bin, copied from the locked inventory row at order time. The worker does no database access, so it can run anywhere that can reach the queue.
- Separation: the web request ends when the order commits and messages are queued; picking happens on a different machine, at a different pace. If the worker is slow the user doesn't notice.
- Streams: stdout shows what the worker is doing (it prints each ticket and each message's metadata), the ticket file is the durable output, stderr is for failures. Students saw this split in session 4.
- Signals: the worker catches SIGINT and SIGTERM and finishes its current batch, which is what makes `systemctl stop` safe.

## Caveats
- Both `python3 src/pick_ticket_worker.py ...` and `python3 -m src.pick_ticket_worker ...` work now (stages 15–20). The first draft of this lesson warned that the script form failed with `ModuleNotFoundError: No module named 'src'`; the import now falls back to the flat layout, which is also what the container uses.
- `deploy/aws/README.md` step 6 (`python3 src/pick_ticket_worker.py data/pick-work.json pick-tickets.txt`) passes a JSON file where the queue URL goes; do not use it.
- The sample command in `data/pick-work.json` uses `SKU-001`, which is not a seeded SKU (the seed has `SKU-1001`, `SKU-1002`, `SKU-2001`). An order for `SKU-001`, as in `deploy/aws/README.md`'s curl example, will be rejected as an unknown SKU.
