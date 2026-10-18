# Session 23 — Consumer lifecycle, duplicates and idempotency

**Stage:** `15-pick-ticket-worker` · **Repo support:** Yes (offline duplicate-delivery demo verified) · **Run from:** `20-final-walkthrough/`

**Concept (20 min):** consumer lifecycle, acknowledgement, retries, duplicates, ordering, idempotency; streaming as continuing data.
**Demo (20 min):** a Python consumer reads messages; deliberately process a duplicate; introduce the event/order ID as the fix.

## Run sheet (verified)
This runs the **real** worker code (`src/pick_ticket_worker.py` and `src/sqs_consumer.py`) against an in-memory queue, after a real order has produced real messages, and then redelivers one message:
```bash
PYTHONPATH=.:../lessons/support python3 ../lessons/support/worker_demo.py
```
You will see:
1. `queue holds 3 messages (one is a duplicate)`: the order had 2 lines, and SQS "delivered" the first again.
2. For each delivered message, the consumer's printed metadata (message ID, receipt handle) and then the ticket line.
3. `pick-tickets.txt` containing **two** tickets, not three, and a state file listing the two processed `command_id`s.
4. `queue now holds 0 messages`: every message was acknowledged (deleted), including the duplicate.

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
