# Session 23 — Consumer lifecycle, duplicates and idempotency

**Stage:** `15-pick-ticket-worker` · **Repo support:** Yes (offline duplicate-delivery demo verified) · **Run from:** `20-final-walkthrough/`

**Concept (20 min):** consumer lifecycle, acknowledgement, retries, duplicates, ordering, idempotency; streaming as continuing data.
**Demo (20 min):** a Python consumer reads messages; deliberately process a duplicate; introduce the event/order ID as the fix.

## Run sheet (verified)
*Demo scripts: set `TINYWMS` and `LESSONS` first (see README → Running the demos).*

**Option 1: the script.** This runs the **real** worker code (`src/pick_ticket_worker.py` and `src/sqs_consumer.py`) against an in-memory queue, after a real order has produced real messages, and then redelivers one message:
```bash
PYTHONPATH=.:"$LESSONS/support" python3 "$LESSONS/support/worker_demo.py"
```
You will see:
1. `queue holds 3 messages (one is a duplicate)`: the order had 2 lines, and SQS "delivered" the first again.
2. For each delivered message, the consumer's printed metadata (message ID, receipt handle) and then the ticket line.
3. `pick-tickets.txt` containing **two** tickets, not three, and a state file listing the two processed `command_id`s.
4. `queue now holds 0 messages`: every message was acknowledged (deleted), including the duplicate.

**Option 2: make a real duplicate in local mode (verified).** The file queue never redelivers by itself, so create the duplicate by hand. Start the server alone (no worker), place a one-line order, then copy its message file:
```bash
cd "$TINYWMS/20-final-walkthrough"
rm -rf local-aws pick-tickets.txt && export TINYWMS_LOCAL=1
python3 src/http_server.py &                                  # or in another terminal
sleep 1
curl -s -d '{"order_id":"DUP-1","lines":[{"sku":"SKU-1002","quantity":1}]}' localhost:8000/orders
cp "$(ls local-aws/pick-work/*.json | head -1)" local-aws/pick-work/99999999999999999999-copy.json    # the "redelivery"
ls local-aws/pick-work                                         # two files, identical Body, same command_id
python3 src/pick_ticket_worker.py local-aws/pick-work pick-tickets.txt \
  --state-file local-aws/pick-ticket-worker-state.json --once --wait-time-seconds 1
wc -l pick-tickets.txt                                         # 1 ticket, not 2
cat local-aws/pick-ticket-worker-state.json                    # the command_id the worker remembered
```
Stop the background server afterwards (`kill %1`). Now delete the state file, copy the message again and rerun the worker: you get the duplicate ticket back. That is the lesson in one line: **the state file is the memory that makes a retry safe.**

**Prove that the ID is doing the work.** Edit `src/pick_ticket_worker.py` on a copy: remove the `if command_id in processed: return` check inside `handle_message`, rerun, and see three tickets, one of them a duplicate pick. Restore it.

**The lifecycle, in code order:**
1. `receive_message` (long poll, up to 20 s): messages become invisible to others for the visibility timeout.
2. Process: parse JSON, check `command_id` against the set loaded from the state file.
3. Side effect: append the ticket to the file.
4. Remember: add the ID to the state file.
5. Acknowledge: `delete_message`. If the worker dies before this, SQS makes the message visible again and delivers it again.

## Talking points
- At-least-once delivery is the contract. Exactly-once is something you build: make the work idempotent so a second run changes nothing. The key is a stable ID derived from the order, here `pick-work:<order>:<sku>:<qty>:<bin>`.
- Ordering is not guaranteed on a standard queue. The ticket for line 2 can come before line 1; the design tolerates that.
- Streaming idea: a queue consumer is a loop over a never-ending stream of small messages.
- Crash window: the ticket is written, then the ID is saved. If the worker dies between the two, a restart writes the ticket twice. Perfect idempotency would need both in one atomic step. Say this out loud; it is a good question for students.
