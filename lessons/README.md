# TinyWMS lesson notes

One file per session, in the order of the syllabus. Each file has the 20-minute concept, the 20-minute demo, and either a **run sheet** built from the repo's stages (where the repo supports the session) or **10 bullets** to work from (where it does not).

Run sheets use the `tinywms-course` repo (branch `course-rewrite` or later). Commands marked *verified* were executed while writing these notes; AWS, Postgres, Docker and systemd steps were **not** executed (the machine used had none of them) and are labelled as such.

## Running the demos

The lessons live in this repo; the code they run lives in `tinywms-course`. Tell your shell where each is, once per terminal:
```bash
export TINYWMS=~/devtools/tinywms-course          # the course repo (stages 00-20)
export LESSONS=~/devtools/regen-test/lessons      # this folder (holds support/)
```
Then:
1. **The whole system on one machine, no AWS** (the stage-20 demo; most sessions build on it):
   ```bash
   cd "$TINYWMS/20-final-walkthrough"
   bash deploy/local/run_local.sh --reset      # page + order API + SQLite + queue + event bus + worker
   # browser: http://127.0.0.1:8000/     second terminal: tail -F pick-tickets.txt
   ```
   Ctrl+C stops it. `--reset` clears `local-aws/` and `pick-tickets.txt`. Every stage from 10 to 20 has its own `deploy/local/run_local.sh` with just the parts that exist at that stage.
2. **A piece at a time**: start only the server with `export TINYWMS_LOCAL=1; python3 src/http_server.py` (no worker, so queue messages stay visible), and run the worker or the event consumers by hand, with the queue given as a folder path (`local-aws/pick-work`, `local-aws/event-consumer-a`).
3. **Offline scripts** in `$LESSONS/support/`, run from `20-final-walkthrough/` with the `PYTHONPATH` shown in each session.
4. **Stage by stage**: each session says which stage folder it runs from. `python3 src/http_server.py` inside a stage is the original file-backed server and is the right one for sessions 6 and 9.

What local mode stands in for: the SQLite file is RDS, each folder under `local-aws/` is an SQS queue (one JSON file per message) or an EventBridge subscriber queue, and `TINYWMS_LOCAL=1` is the only switch. It has no visibility timeout and never delivers duplicates by itself, so sessions 17 (row locks) and 23 (redelivery) show how to create those by hand.

### Cheat sheet

| Session | Run | You should see |
|---|---|---|
| 1 | `bash deploy/local/run_local.sh --reset` in `20-final-walkthrough` | order in the page; ticket lines in `pick-tickets.txt` |
| 4 | `python3 src/inventory_watcher.py data/inventory.json /tmp/w.log &` in `02-linux-visible`, then `tail -f /tmp/w.log` | a snapshot line every 2 seconds |
| 6 | `python3 src/http_server.py` in `03-pi-http-server`, then `curl -i localhost:8000/inventory` | 200, JSON headers, 3 items |
| 9 | same in `04-browser`, browser at `localhost:8000/` | the inventory table |
| 11 | `PYTHONPATH=. python3 -c "..."` in `06-lambda` (see the session) | `statusCode` 200 and a JSON string body |
| 13, 14 | `TINYWMS_DB=sqlite TINYWMS_SQLITE_PATH=data/tinywms.db python3 -m data.init_db` in `08-relational-persistence`, then `sqlite3` | an `inventory` table |
| 16 | `PYTHONPATH=. python3 "$LESSONS/support/inventory_query_demo.py"` in `20-final-walkthrough` (after `init_db`, see the session) | the handler returns rows from SQL |
| 17 | `python3 "$LESSONS/support/race_demo.py"` | naive: 2 of 1 accepted; conditional: 1 of 1 |
| 18, 19 | `run_local.sh`, then the `curl` commands in the session, then `sqlite3 local-aws/tinywms.db "select * from orders"` | 201 / 400 / 409 and the tables |
| 20 | local mode plus `chmod a-w local-aws/pick-work` (partial failure) | order stored, HTTP 500, no pick message |
| 21 | `TINYWMS_LOCAL=1 python3 src/http_server.py`, order, `ls local-aws/pick-work` | message files waiting |
| 22 | `ls local-aws/event-consumer-a`, then `python3 src/event_consumer_a.py local-aws/event-consumer-a` (with `TINYWMS_LOCAL=1`) | `consumer-a received OrderPlaced for ...` |
| 23 | the `cp` of a message file, then `pick_ticket_worker.py ... --once` | 2 messages, 1 ticket |
| 24 | `python3 src/pick_ticket_worker.py local-aws/pick-work pick-tickets.txt --once` | tickets appended |
| 25 | the systemd steps (Linux only), with `TINYWMS_LOCAL=1` in the env file | `journalctl -f` and the ticket file move together |
| 26 | `docker build`, then `docker run ... -v "$PWD/local-aws:/state"` | ticket written by the container, kept on the host |

| # | Topic | Stage | Repo support |
|---|---|---|---|
| 01 | What the course is about; the finished journey | 20 | Yes (`run_local.sh`) |
| 02 | Computer anatomy | none | 10 bullets |
| 03 | Filesystem, permissions, sudo | none | 10 bullets |
| 04 | Processes, streams, signals | 02 | Yes |
| 05 | Python and JSON | 01 | Yes |
| 06 | HTTP client/server | 03 | Yes |
| 07 | Virtual machines, EC2 | 05 | Partly |
| 08 | Networking; break/fix EC2 | none | 10 bullets |
| 09 | HTML, DOM, fetch() | 04 | Yes |
| 10 | AuthN/AuthZ, IAM | none | 10 bullets |
| 11 | Lambda | 06 | Yes (deploy needs a check) |
| 12 | HTTP API / API Gateway | 07 | Yes (AWS, not run) |
| 13 | Why files hurt; tables and keys | 08 | Yes |
| 14 | SQL; a database server on a port | 08 + manual | Partly |
| 15 | RDS | 09 | Yes (AWS, not run) |
| 16 | App/data boundary | 10 | Yes |
| 17 | State and concurrency | 12 | Yes |
| 18 | GET vs POST; order form | 11 | Yes |
| 19 | Multi-table transaction | 11 / 20 | Yes |
| 20 | Failure modes | 20 (local mode) | 10 bullets plus local break exercises |
| 21 | Queues; sync vs async | 13 | Yes (local queue folder) |
| 22 | Commands vs events | 14 | Yes (local event folders) |
| 23 | Consumers and idempotency | 15 | Yes (local duplicate demo) |
| 24 | Long-running workers | 15 | Yes (local queue) |
| 25 | Services and logs | 15 | Yes (Linux only; can use the local queue) |
| 26 | Containers; final architecture | 17 | Yes (Dockerfile fixed; image not built here) |
| 27 | Student demos 1 | none | 10 bullets |
| 28 | Student demos 2 and synthesis | 20 | 10 bullets |

## Helper scripts (`support/`)
Run from `20-final-walkthrough/` with `export LESSONS=...` set (see Running the demos). They run the repo's real order and worker code against SQLite and an in-memory fake queue and event bus, so the order → queue → event → ticket path can be shown with no AWS and without starting the server.

| Script | Used in | What it shows |
|---|---|---|
| `order_demo.py` | 1, 19, 21 | three orders: accepted, rolled back mid-order, unknown SKU; resulting tables, queue messages, event |
| `race_demo.py` | 17 | oversell with naive read-then-update vs a conditional UPDATE (needs no repo code) |
| `events_demo.py` | 22 | command vs event, plus fan-out to subscribers |
| `worker_demo.py` | 1, 23, 24 | the real worker, a duplicate delivery, tickets and state file |
| `inventory_query_demo.py` | 16 | `GET /inventory` through the Lambda handler reading SQL rows |
| `fake_aws.py` | all of the above | the fake queue and event bus |

Local mode (`run_local.sh`) now covers most of what these scripts show with the real server; keep the scripts for showing one thing in isolation, or as a fallback if a browser or port is a problem.

## Status of the problems found while preparing (original list, updated)
1. **Container (session 26): fixed in code, image not built.** The worker import failed in the flat `/app` layout, and the Dockerfile's `COPY` paths did not match the documented build context. Both are fixed in stages 17–20, and the image now carries the local queue module. Docker was not available to build it, so rehearse the first build.
2. **Lambda `GET /inventory` (sessions 11, 16): fixed in stages 10–20.** The handler's default connection crashed. Still open: **stage 6's inline Lambda** reads a data file that is not in the package, so the stage-6 live deploy needs a check.
3. **Event consumers (session 22): fixed.** They now read EventBridge's `detail-type` (and still accept `DetailType`). Not tested against a real EventBridge rule.
4. **Local order server (sessions 1, 18): changed.** The plain `python3 src/http_server.py` is unchanged (file-backed, rewrites `data/inventory.json`, 409 for everything). **Local mode** answers through the Lambda handler against SQLite: 400 for a bad request, 409 for a shortage, unknown SKU or repeated order ID, no file rewriting.
5. **Docs (session 24): still open.** `deploy/aws/README.md` step 6 passes a JSON file as the queue URL, and its curl example uses `SKU-001`, which is not seeded.
6. **Orders and notifications (sessions 19, 20): still true by design.** Commit and queue send are not atomic and there is no retry or outbox; session 20 now reproduces it locally.
7. **Stage 6/7 name mismatch: still open.** The Lambda function is `tinywms-lambda-inventory`, the API Gateway notes expect `tinywms-inventory-lesson`.
8. **`init_db`** is still not repeatable (fails if the table exists); local mode avoids it by creating the database only when missing.
9. **Syllabus mapping:** I treated the blank rows in the first paste as nothing, the repeated "Whole 90 minutes" row as a duplicate of session 1, and the last two rows as sessions 27 and 28.
