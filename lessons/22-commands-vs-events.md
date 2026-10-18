# Session 22 — Commands vs events

**Stage:** `14-domain-events` · **Repo support:** Yes (offline stand-in verified) · **Run from:** `20-final-walkthrough/`

**Concept (20 min):** command vs event; "do this" vs "this happened"; subscribers; loose coupling; fan-out.
**Demo (20 min):** contrast the pick-work command with the `OrderPlaced` event; add a second trivial subscriber or action.

## Run sheet (verified)
```bash
PYTHONPATH=.:../lessons/support python3 ../lessons/support/events_demo.py
```
It places one order and prints, side by side:
- the **command**: `command_id`, `order_id`, `sku`, `description`, `quantity`, `bin` — specific, addressed to one worker, says what to do;
- the **event**: `Source: tinywms.orders`, `DetailType: OrderPlaced`, and a `Detail` of `version`, `order_id`, `lines[sku, quantity]` — no bin, no instruction, just a fact about what happened;
- then two subscribers (an audit logger and a customer-email stub) each handling the same event, with **no change** to the order code.

**Make the second-subscriber point live.** Open `events_demo.py` and add a third function, e.g. one that prints "reserve packing materials when quantity > 5", and add it to the tuple at the bottom. The producer is untouched.

**Read the repo's wiring:**
- `src/lambda_inventory.py` → `_build_order_placed_event` and the `put_events` call after the SQS sends.
- `infra/events.yaml`: an event bus, two rules matching `detail-type: OrderPlaced`, and two SQS queues (one per subscriber), each with a queue policy allowing EventBridge to send.
- `src/event_consumer_a.py` and `src/event_consumer_b.py`: two independent consumers of their own queues.

**Real AWS (not run for this plan):** `deploy/events/README.md` deploys the stack; then `python3 src/event_consumer_a.py "$EVENT_CONSUMER_A_QUEUE_URL"`.

## Talking points
- Naming: a command is imperative (`CreatePickTicket`, `pick-work`), an event is past tense (`OrderPlaced`). Note the syllabus calls the command "CreatePickTicket"; in the repo it is the pick-work command.
- A command has one owner who must act. An event can have zero, one or ten listeners and the sender neither knows nor cares: fan-out.
- Coupling: to add a subscriber you add a rule and a queue, not a line to the order code. To change the command you must change the order code and the worker together.

## Caveat to check on AWS
- Both consumers print `event['DetailType']`, but a real EventBridge-to-SQS delivery names that field `detail-type` (lower case, hyphenated). The consumers decode `detail` correctly but may raise `KeyError` on the type. The offline demo uses the producer's own capitalised shape, so it hides this. Test on a real stack before relying on it.
