# Session 21 — Synchronous vs asynchronous work: SQS

**Stage:** `13-sqs` · **Repo support:** Yes (offline stand-in verified; real SQS steps not run) · **Run from:** `20-final-walkthrough/`

**Concept (20 min):** synchronous vs asynchronous work; producer, queue, consumer; delivery, retry, buffering.
**Demo (20 min):** the order Lambda sends a simple order JSON to SQS; inspect the message separately.

## Run sheet

*Demo scripts: set `TINYWMS` and `LESSONS` first (see README → Running the demos).*

**Step 0: watch a real queue fill up, in local mode (verified).** Start the server *without* the worker, so nothing consumes the messages:
```bash
cd "$TINYWMS/20-final-walkthrough"
rm -rf local-aws && export TINYWMS_LOCAL=1
python3 src/http_server.py                    # server only; open http://127.0.0.1:8000/ and submit an order
# second terminal, same folder:
ls local-aws/pick-work                         # one file per order line: the producer is done, the consumer has not started
cat local-aws/pick-work/*.json                 # {"MessageId": ..., "Body": "<the pick-work command as a JSON string>"}
```
Then start the consumer and watch the queue drain and the ticket appear:
```bash
export TINYWMS_LOCAL=1
python3 src/pick_ticket_worker.py local-aws/pick-work pick-tickets.txt --once --wait-time-seconds 1
ls local-aws/pick-work                         # empty: delete-after-success is the acknowledgement
cat pick-tickets.txt
```
The order finished before any ticket existed. That is the point of the lesson. (`bash deploy/local/run_local.sh` starts the worker for you, which hides this gap; use it for session 1, not here.)

**Step 1: see what an accepted order puts on the queue (verified, offline script).**
```bash
PYTHONPATH=.:"$LESSONS/support" python3 "$LESSONS/support/order_demo.py"
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
