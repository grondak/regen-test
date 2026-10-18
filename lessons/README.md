# TinyWMS lesson notes

One file per session, in the order of the syllabus. Each file has the 20-minute concept, the 20-minute demo, and either a **run sheet** built from the repo's stages (where the repo supports the session) or **10 bullets** to work from (where it does not).

Run sheets use the repo as it stands in the working tree. Commands marked *verified* were executed while writing these notes; AWS, Postgres, Docker and systemd steps were **not** executed (this machine has none of them) and are labelled as such.

| # | Topic | Stage | Repo support |
|---|---|---|---|
| 01 | What the course is about; the finished journey | 11 + 20 | Partly |
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
| 20 | Failure modes | none | 10 bullets |
| 21 | Queues; sync vs async | 13 | Yes |
| 22 | Commands vs events | 14 | Yes |
| 23 | Consumers and idempotency | 15 | Yes |
| 24 | Long-running workers | 15 | Yes |
| 25 | Services and logs | 15 | Yes (Linux only) |
| 26 | Containers; final architecture | 17 | Yes, but see the Dockerfile bug |
| 27 | Student demos 1 | none | 10 bullets |
| 28 | Student demos 2 and synthesis | 20 | 10 bullets |

## Helper scripts (`support/`)
Run from `20-final-walkthrough/`. They run the repo's real order and worker code against SQLite and an in-memory fake queue and event bus, so the order → queue → event → ticket path can be shown with no AWS.

| Script | Used in | What it shows |
|---|---|---|
| `order_demo.py` | 1, 19, 21 | three orders: accepted, rolled back mid-order, unknown SKU; resulting tables, queue messages, event |
| `race_demo.py` | 17 | oversell with naive read-then-update vs a conditional UPDATE |
| `events_demo.py` | 22 | command vs event, plus fan-out to subscribers |
| `worker_demo.py` | 1, 23, 24 | the real worker, a duplicate delivery, tickets and state file |
| `inventory_query_demo.py` | 16 | `GET /inventory` through the Lambda handler reading SQL rows |
| `fake_aws.py` | all of the above | the fake queue and event bus |

## Things to fix or check before teaching (found while preparing)
1. **Container (session 26):** the Docker image cannot start (`No module named 'src'`).
2. **Lambda GET /inventory (sessions 11, 16):** with no injected connection factory, the handler fails with an `AttributeError`; stage 6's inline Lambda reads a file that is not in the package.
3. **Event consumers (session 22):** they print `DetailType`, but EventBridge delivers `detail-type`.
4. **Local order server (sessions 1, 18):** rewrites its inventory file on every order; returns 409 for malformed input; accepts duplicate order IDs.
5. **Docs (session 24):** `deploy/aws/README.md` step 6 passes a JSON file as the queue URL; its curl example uses `SKU-001`, which is not seeded.
6. **Orders and notifications (sessions 19, 20):** commit and queue send are not atomic; there is no retry or outbox.
7. **Stage 6/7 name mismatch:** the Lambda function is `tinywms-lambda-inventory`, the API Gateway notes expect `tinywms-inventory-lesson`.
8. **init_db** is not repeatable (fails if the table exists).
9. **Syllabus mapping:** I treated the blank rows in the first paste as nothing, the repeated "Whole 90 minutes" row as a duplicate of session 1, and the last two rows as sessions 27 and 28.
