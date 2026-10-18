# Session 1 — What is this course actually about?

**Format:** whole 90 minutes · **Repo support:** Partly (the local half of the journey runs; the event and pick-ticket half needs AWS or the offline stand-ins)

**Concept:** Pi → Linux → network → cloud → data → distributed system. Introduce TinyWMS and the no-tests / build-things model.
**Demo:** the finished warehouse journey: inventory page → submit order → inventory changes → event → pick ticket appears. Show the Pi and AWS architecture without explaining all of it.

## Run sheet: the journey, in three acts

Prepare once, from the repo root:
```bash
cp 11-orders/data/inventory.json /tmp/inventory-demo.json      # the server rewrites its inventory file on every order
```

**Act 1: inventory page and an order (real, local, about 5 min).**
```bash
cd 11-orders
TINYWMS_INVENTORY_FILE=/tmp/inventory-demo.json python3 src/http_server.py
# browser: http://127.0.0.1:8000/  -> table of 3 SKUs, textarea with order JSON, "Submit order"
# submit it, watch the quantity drop; repeat in a terminal:
curl -s localhost:8000/inventory
```

**Act 2: what the order really does in the cloud design (offline stand-ins, about 5 min).** The local server only edits a JSON file. The real design commits to a database, sends one SQS command per line, and publishes one event. This script runs the real order code against SQLite plus in-memory queue/bus:
```bash
cd 20-final-walkthrough
PYTHONPATH=.:../lessons/support python3 ../lessons/support/order_demo.py
```
Point at the tail of the output: the rows in `orders` / `order_lines`, the pick-work messages, the `OrderPlaced` event.

**Act 3: the pick ticket appears (offline, about 3 min).**
```bash
PYTHONPATH=.:../lessons/support python3 ../lessons/support/worker_demo.py
```
That feeds the real worker and prints `pick-tickets.txt`. If you have the AWS stack deployed (`20-final-walkthrough/deploy/aws/README.md`), do this part for real with `tail -f pick-tickets.txt`.

## Talking points (10 bullets for the rest of the 90 minutes)
1. The arc of the semester: a Raspberry Pi on the desk → Linux → HTTP → EC2 → serverless → SQL → orders → queues and events → a container. One small app, moved one boundary at a time.
2. Every session asks the same four questions: where does the code run, where is its data, how did the data get there, what representation crosses each boundary?
3. The domain: a warehouse has SKUs, bins and quantities. An order removes stock and tells a picker where to walk.
4. The contract that never changes shape: inventory JSON (`sku`, `description`, `bin_location`, `quantity`, `unit`). Show it once; it reappears every session.
5. The build-things model: you type commands, break things, fix them. The tests in the repo exist so the instructor knows the demo works; students are never asked to run them.
6. Show the architecture picture (`20-final-walkthrough/docs/end-to-end.md`, Mermaid diagram) without explaining it: browser → API → function → database → queue → worker → file.
7. Tools students will touch: terminal and SSH, Python, curl, a browser, `sqlite3`/`psql`, the AWS console, Docker.
8. What is deliberately absent: frameworks, ORMs, front-end tooling. Plain HTTP, JSON and SQL so every hop is visible.
9. Logistics: what to bring, accounts to create (AWS), cost control (terminate instances, delete stacks), where the repo and lesson notes live.
10. Close by promising the final session: students demonstrate their own working system and walk the final architecture beside this opening picture.

## Caveats found while preparing this
- The local server (stages 03–20) never talks to a database, queue or event bus. Act 1 is honest about a file-backed demo; Acts 2 and 3 are what the cloud path does.
- The server **rewrites its inventory file** on every accepted order, which is why the run sheet points it at a copy.
