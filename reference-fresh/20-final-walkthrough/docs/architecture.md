# TinyWMS Architecture

## Current architecture
Stage 19 keeps the Stage 18 cloud system intact and adds the teaching idea of repository history as a first-class lesson artifact. The application contracts are still the same, but students can now line up stages, tags, and checkouts to see how the system evolved over time.

## Architecture History
- Stage 0: repository scaffold only.
- Stage 1: inventory JSON contract and CLI backbone.
- Stage 2: Linux-visible command-line tools and watcher process.
- Stage 3: tiny HTTP inventory server on Raspberry Pi Linux / EC2 Linux.
- Stage 4: plain browser HTML/CSS/JavaScript page consuming the same inventory contract.
- Stage 5: EC2 deployment wrapper for the existing HTTP inventory server.
- Stage 6: Lambda inventory handler added in parallel with the Pi/EC2 HTTP path.
- Stage 7: API Gateway front door added in front of the Lambda path while preserving the earlier compute paths.
- Stage 8: relational persistence lesson adds SQL schema, seed, and export artifacts derived from the JSON inventory contract.
- Stage 9: managed RDS deployment wrapper shifts the database hosting/operations responsibility from self-managed Linux to AWS RDS while preserving the relational schema.
- Stage 10: Lambda inventory handler switches its deployed read path from static JSON to RDS while keeping the inventory JSON contract unchanged.
- Stage 11: order transaction workflow is added to the local HTTP server, browser page, and Lambda handler.
- Stage 12: concurrent order attempts are hardened so the order transaction cannot oversell inventory under overlap.
- Stage 13: committed orders now publish asynchronous pick-work commands to SQS, and a reusable consumer helper demonstrates the receive/delete contract.
- Stage 14: committed orders now also publish OrderPlaced domain events to EventBridge, and two independent consumers show decoupled event delivery.
- Stage 15: the SQS consumer becomes a durable pick-ticket worker that writes tickets to a file and remembers processed commands across restarts.
- Stage 16: the callback demo ties the browser, HTTP server, Lambda, queue, worker, and file output together in one local proof.
- Stage 17: the pick-ticket worker gains a Docker container runtime while keeping the same queue command and ticket output contract.
- Stage 18: the AWS deployment path is consolidated into one CloudFormation stack with explicit packaging, IAM, queue, event, API, and logging resources.
- Stage 19: Git tags and checkouts become a teaching boundary so students can compare the semester's simpler and more complex checkpoints side by side.
- Stage 20: the browser and local HTTP server are repaired so one plain page can render inventory, submit visible order JSON, show the response, and refresh inventory after acceptance while preserving the deployed Lambda/RDS transaction path and JSON contracts.

## Component Assembly Map

| component name | stage introduced | runtime location | inbound contract | outbound contract | dependencies |
| --- | --- | --- | --- | --- | --- |
| Inventory JSON file | 01-json-backbone | `data/inventory.json` on disk | inventory JSON contract | inventory JSON contract | none |
| Inventory CLI | 01-json-backbone | Python process on Linux | inventory JSON contract | visible JSON text / inventory listing | Inventory JSON file |
| Linux-visible demo CLI | 02-linux-visible | Python process on Linux | command name plus stdin/stdout/stderr/env/process contract | visible output, non-zero exit codes, environment echo | Python runtime, environment variables |
| Inventory watcher | 02-linux-visible | long-running Python process on Linux | inventory JSON contract and log-file path | appended log snapshots | Inventory JSON file |
| HTTP inventory server | 03-pi-http-server | Python process on a TCP port on Raspberry Pi Linux or EC2 Linux | HTTP `GET /inventory` | inventory JSON body with HTTP status and headers | Inventory JSON file, Python standard library HTTP server |
| Browser inventory page | 04-browser | browser DOM and JavaScript | HTTP `GET /inventory` response body | rendered table and visible error message | HTTP inventory server, Inventory JSON file |
| EC2 deployment wrapper | 05-ec2-deployment | EC2 Linux host process startup scripts | shell environment plus repository layout | launched HTTP inventory server process | HTTP inventory server, shell, copied environment file |
| Lambda inventory handler | 06-lambda | AWS Lambda | Lambda event for `GET /inventory` and an injected database/connection-like interface in tests | inventory JSON body with HTTP-style status, headers, and body | Inventory JSON file, AWS Lambda runtime, IAM role |
| API Gateway front door | 07-api-gateway | AWS API Gateway | HTTPS `GET /inventory` | proxied Lambda invocation and HTTP response | Lambda inventory handler, AWS Lambda invoke permission |
| Relational persistence | 08-relational-persistence | Linux database process | SQL schema and seed derived from the inventory JSON contract | inventory rows stored in tables and SQL INSERT output from the export script | Inventory JSON file, SQL schema, SQL export script |
| RDS deployment wrapper | 09-rds | AWS RDS | deployment parameters for database name, credentials, subnets, and security groups | running managed PostgreSQL instance with endpoint/port outputs | Relational persistence, AWS RDS, VPC subnet/security-group inputs |
| Lambda database-backed inventory handler | 10-lambda-rds | AWS Lambda | `GET /inventory` Lambda event plus PostgreSQL connection settings | inventory JSON body returned from database rows | Lambda inventory handler, relational persistence, RDS wrapper |
| local HTTP inventory/order server | 11-orders | Python process on Linux | HTTP `GET /inventory` and `POST /orders` | inventory JSON plus order acceptance/rejection JSON | HTTP inventory server, inventory JSON, order JSON |
| integrated inventory and order browser page | 11-orders | browser | inventory JSON plus order JSON via same-origin fetch | rendered inventory table, order request JSON, response JSON, and refresh behavior | browser inventory page, local HTTP inventory/order server |
| Lambda order handler | 11-orders | AWS Lambda | HTTP `GET /inventory` and `POST /orders` events plus PostgreSQL connection settings | inventory JSON, accepted-order JSON, and transaction rollback on rejection | Lambda database-backed inventory handler, relational persistence, order JSON |
| concurrent order hardening | 12-concurrency | database transaction boundary | overlapping order attempts using the same order JSON contract | committed inventory changes without overselling and visible rollback on rejection | Lambda order handler, relational persistence, order JSON |
| SQS consumer helper | 13-sqs | Python process on Linux | pick-work command JSON from a queue message body | decoded command JSON passed to a callback; delete-on-success queue acknowledgement | SQS client, pick-work command contract |
| pick-work SQS queue | 13-sqs | AWS SQS | pick-work command JSON | stored queue messages and delivery metadata | Lambda order handler, pick-work command contract |
| OrderPlaced event consumers | 14-domain-events | Python processes on Linux | EventBridge-delivered OrderPlaced event JSON from separate target queues | visible event inspection and acknowledgement after queue receive/delete | EventBridge rule targets, SQS queues, OrderPlaced event contract |
| EventBridge order bus and rules | 14-domain-events | AWS EventBridge | OrderPlaced event JSON | fan-out to two independent SQS target queues | Lambda order handler, SQS target queues, queue policies |
| pick-ticket worker | 15-pick-ticket-worker | Python process on Linux | pick-work command JSON from `src.sqs_consumer.consume_messages(...)` | durable `pick-tickets.txt` file entries and persisted command IDs | SQS consumer helper, pick-work command contract, filesystem |
| callback integration proof | 16-callback-demo | local test suite | browser request/response, Lambda order command/event emission, queue receipt, and worker callback JSON | end-to-end local proof and pick-ticket file output | HTTP server, Lambda handler, worker, SQS consumer helper |
| containerized pick-ticket worker | 17-container-worker | Docker container | pick-work command JSON from `src.sqs_consumer.consume_messages(...)` or the worker CLI entrypoint | the same durable `pick-tickets.txt` output and persisted command IDs as the bare process | pick-ticket worker, SQS consumer helper, mounted state volume |
| consolidated AWS deployment | 18-aws-deployment | AWS CloudFormation stack | inventory/order HTTP requests, Lambda env vars, pick-work queue path, OrderPlaced event path, and RDS connectivity inputs | API base URL, function name, queue URL/ARN, bus name/ARN, DB endpoint/port outputs | Lambda inventory handler, API Gateway front door, pick-work SQS queue, EventBridge order bus and rules, RDS connectivity, logs/observability |
| Git history milestones | 19-git-history | git tags and checkouts | the lesson repository state at each milestone | readable historical checkpoints and comparison points | current repository history, stage tags, deployment guides, and existing lesson artifacts |
| final browser and local order HTTP path | 20-final-walkthrough | browser DOM and Python standard-library HTTP server | same-origin or runtime-overridden `/inventory` and `/orders` requests plus local inventory file state | rendered table, visible order JSON, accepted/rejected JSON response, and refreshed inventory display | `src/web/index.html`, `src/web/app.js`, `src/web/style.css`, `src/http_server.py`, inventory file override, existing Lambda/RDS contracts |

## Component evolution notes
- The inventory JSON contract remains canonical and compatible with all earlier readers.
- Stage 11 introduces `order-json` as a new visible contract; it remains small and separate from the inventory schema.
- Stage 12 does not add a new top-level subsystem. It hardens the existing order/database path so the same contracts survive genuine overlap.
- Stage 13 adds a queue boundary after the commit. The new queue contract is separate from the existing inventory/order HTTP contracts.
- Stage 14 adds a domain event boundary after the same commit. The event contract says what happened, while the SQS command says what to do.
- Stage 15 reuses the Stage 13 consumer boundary rather than replacing it. The worker evolves the consumer into a durable process that writes file output and remembers processed command IDs.
- Stage 16 adds a local callback proof that traces the whole path without changing the contracts.
- Stage 17 does not change the queue or file contract. It adds an alternate container runtime for the same worker process.
- Stage 18 consolidates deployment artifacts. It does not change the application contract; it makes the assembled cloud path reproducible and inspectable from one stack.
- Stage 19 does not replace any application boundary. It adds Git milestones so students can compare earlier repository snapshots against the current architecture and deployment guides.
- Stage 20 repairs the local browser and HTTP server path without replacing the deployed Lambda/RDS order transaction path.
- `src/http_server.py` remains the local teaching server that serves browser files and implements `POST /orders`.
- `src/lambda_inventory.py` remains the order handler entry point. Its transaction strategy remains the lesson-visible boundary that publishes asynchronous queue commands and domain events after the commit.
- The queue consumer helper and the event consumers intentionally expose receive/delete behavior instead of hiding it behind a worker loop so later stages can evolve them into long-running services.
- `src/pick_ticket_worker.py` is the first component in TinyWMS that turns a queue message into a durable operational artifact on disk, and Stage 17 packages that same process in Docker without changing the behavior.
- `src/Dockerfile` is the containerized runtime wrapper for the worker, not a new business-logic component.
- `infra/template.yaml` is the stage 18 deployment assembly point; it groups the previously separate cloud operations into one stack without altering the business contracts.
- SQLite is useful for portable local exercises, but it cannot demonstrate the PostgreSQL row-lock lesson; Stage 12 concurrency remains a PostgreSQL-only proof of `FOR UPDATE` overlap behavior.

## Component evolution timeline
This timeline is derived from the Component Assembly Map above.

| stage introduced | components first appearing at that stage | dependency snapshot |
| --- | --- | --- |
| 01-json-backbone | Inventory JSON file, Inventory CLI | Inventory file stands alone and feeds the CLI. |
| 02-linux-visible | Linux-visible demo CLI, Inventory watcher | Linux process visibility depends on the inventory contract and the local filesystem. |
| 03-pi-http-server | HTTP inventory server | HTTP server depends on the inventory contract. |
| 04-browser | Browser inventory page | Browser depends on the HTTP inventory server and the same inventory contract. |
| 05-ec2-deployment | EC2 deployment wrapper | EC2 wrapper depends on the HTTP inventory server and Linux process startup. |
| 06-lambda | Lambda inventory handler | Lambda compute depends on the inventory contract and a database-like connection. |
| 07-api-gateway | API Gateway front door | API Gateway depends on Lambda invocation permissions and the Lambda inventory handler. |
| 08-relational-persistence | Relational persistence | SQL schema and export depend on the inventory JSON contract. |
| 09-rds | RDS deployment wrapper | RDS wrapper depends on the relational schema and AWS-managed database hosting. |
| 10-lambda-rds | Lambda database-backed inventory handler | Lambda read path changes from static JSON to the relational database boundary. |
| 11-orders | Local HTTP inventory/order server, integrated inventory and order browser page, Lambda order handler | Order workflow adds the order JSON contract while reusing the inventory contract. |
| 12-concurrency | Concurrent order hardening | Transaction boundary hardens the existing order/database path. |
| 13-sqs | SQS consumer helper, pick-work SQS queue | Queue command boundary is added after committed orders. |
| 14-domain-events | Event consumers, EventBridge order bus and rules | Event boundary is added alongside the queue boundary with independent consumers. |
| 15-pick-ticket-worker | Pick-ticket worker | Queue consumer evolves into a durable worker and adds a file output boundary. |
| 16-callback-demo | Callback integration proof | Local proof composes the browser, HTTP, Lambda, queue, worker, and file output paths. |
| 17-container-worker | Containerized pick-ticket worker | Docker packages the same worker contract as an alternate runtime. |
| 18-aws-deployment | Consolidated AWS deployment | One CloudFormation stack assembles the cloud resources around the same contracts. |
| 19-git-history | Git history milestones | Git tags/checkouts now expose the historical checkpoints of the existing components. |
| 20-final-walkthrough | final browser and local order HTTP path | Browser and HTTP server now share the same local order flow while preserving the deployed transaction path. |

## Component map continuity checks
- The inventory JSON contract remains the common root for the earliest CLI, HTTP, browser, and Lambda lessons.
- The order JSON contract remains the visible request shape for the HTTP and Lambda order paths.
- The queue command, event, and ticket output contracts remain separate so students can compare imperative commands, facts, and durable file artifacts.
- The deployment guides stay present so earlier milestones can still be checked out and reproduced at the appropriate checkpoint.

## SQLite concurrency boundary
SQLite cannot demonstrate the PostgreSQL row-lock lesson; use PostgreSQL and `SELECT ... FOR UPDATE` for the concurrency demonstration.
