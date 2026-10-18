# Session 21 — Synchronous vs asynchronous work: SQS

**Stage:** `13-sqs` · **Repo support:** Yes (offline stand-in verified; real SQS steps not run) · **Run from:** `20-final-walkthrough/`

**Concept (20 min):** synchronous vs asynchronous work; producer, queue, consumer; delivery, retry, buffering.
**Demo (20 min):** the order Lambda sends a simple order JSON to SQS; inspect the message separately.

## Run sheet

**Step 1: see what an accepted order puts on the queue (verified, offline).**
```bash
PYTHONPATH=.:../lessons/support python3 ../lessons/support/order_demo.py
```
Look at the section "messages that would be in SQS". An order with two lines produces **two** messages, one per line:
```json
{"command_id": "pick-work:ORD-1:SKU-1001:2:A1-01", "order_id": "ORD-1", "sku": "SKU-1001",
 "description": "Blue widget", "quantity": 2, "bin": "A1-01"}
```
The contract is documented in `data/pick-work.json` and `docs/data-contracts.md`. The message is a **command**: it tells the worker what to do (go to bin A1-01 for 2 units), nothing about why.

**Step 2: show where in the code the send happens.** `place_order` in `src/lambda_inventory.py`: commit first, then `sqs.send_message(QueueUrl=..., MessageBody=json.dumps(command))` for each line. The HTTP response goes back as soon as that returns; nobody waits for a picker.

**Step 3: the real queue (needs AWS; not run for this plan).** `deploy/sqs/README.md` deploys `infra/sqs.yaml`. Place an order, then look at the message separately from the producer:
```bash
aws sqs receive-message --queue-url "$QUEUE_URL" --attribute-names All --message-attribute-names All
aws sqs get-queue-attributes --queue-url "$QUEUE_URL" --attribute-names All     # ApproximateNumberOfMessages etc.
```
Receiving does not delete: the message reappears after the visibility timeout. That sets up session 23.

**Step 4: the consumer helper.** Read `src/sqs_consumer.py` (about 60 lines): `receive_message` with long polling → for each message print its metadata → `json.loads(body)` → call your callback → `delete_message`. The delete after success is the acknowledgement.

## Talking points
- Synchronous: caller waits for the answer; failure and slowness are shared. Asynchronous: caller hands off work and moves on; the work happens later, somewhere else.
- A queue is a buffer between a producer and a consumer that run at different speeds and at different times. The worker can be down for an hour and nothing is lost.
- Delivery is at least once. A message can arrive twice; this is the central fact of the next session but one.
- Callback to session 19/20: the send is after the commit, and nothing retries if the send fails.
