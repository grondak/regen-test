# Session 1 — What is this course actually about?

**Format:** whole 90 minutes · **Repo support:** Yes (the whole journey runs on one machine with `run_local.sh`; the AWS version is not run here)

**Concept:** Pi → Linux → network → cloud → data → distributed system. Introduce TinyWMS and the no-tests / build-things model.
**Demo:** the finished warehouse journey: inventory page → submit order → inventory changes → event → pick ticket appears. Show the Pi and AWS architecture without explaining all of it.

## Run sheet: the journey

*Demo scripts: set `TINYWMS` and `LESSONS` first (see README → Running the demos).*

**The whole journey, one command (about 8 min).** No AWS, no setup beyond a checkout:
```bash
cd "$TINYWMS/20-final-walkthrough"
bash deploy/local/run_local.sh --reset
# browser: http://127.0.0.1:8000/  -> table of 3 SKUs, textarea with order JSON, "Submit order"
# second terminal, before you submit:
cd "$TINYWMS/20-final-walkthrough" && tail -F pick-tickets.txt
```
Submit the order in the page. In this order the audience sees:
1. the inventory quantities drop (the page refreshes);
2. one pick ticket line per order line appear in `pick-tickets.txt`, written by the worker process that `run_local.sh` started.

That is the whole path: browser, order API (the same handler code Lambda runs), database, queue, worker, file. Ctrl+C in the first terminal stops everything.

**Show the seams (optional, 3 min).** In a third terminal, still in `20-final-walkthrough/`:
```bash
sqlite3 -header -column local-aws/tinywms.db "select * from orders; select * from order_lines;"
ls local-aws/event-consumer-a local-aws/event-consumer-b     # the OrderPlaced event, copied to both subscribers
export TINYWMS_LOCAL=1
python3 src/event_consumer_a.py local-aws/event-consumer-a   # consumer-a received OrderPlaced for <order>
```
In this local mode the SQLite file stands in for RDS and each folder under `local-aws/` stands in for an SQS queue or an EventBridge rule's target queue.

**If you want to see the same order without the web server** (what is inside it, as three orders in a row: accepted, rolled back, unknown SKU):
```bash
PYTHONPATH=.:"$LESSONS/support" python3 "$LESSONS/support/order_demo.py"
```

**The real cloud version.** If you have the stack deployed (`20-final-walkthrough/deploy/aws/README.md`), run the same order against the API URL and `tail -f` the ticket file on the worker host. Not run for this plan.

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
- `bash deploy/local/run_local.sh` (stages 10–20) runs the real order code against SQLite with directories standing in for SQS and EventBridge. Plain `python3 src/http_server.py` is still the older file-backed server: it never touches a database, queue or event bus, and it rewrites `data/inventory.json` on every accepted order. Use `run_local.sh` for the demo.
- The file queue is simpler than SQS: no visibility timeout and no duplicate deliveries.
- Each run leaves `local-aws/` and `pick-tickets.txt` behind; `--reset` clears them.
