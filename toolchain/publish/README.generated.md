# TinyWMS teaching repository

TinyWMS is a semester-long teaching system for learning how a small warehouse
application evolves across processes, hosts, protocols, storage systems, and
AWS services. It is deliberately straightforward: explicit JSON, SQL, HTTP,
environment variables, and deployment files are preferred over framework
abstractions.

This repository contains complete, self-contained snapshots. Start in an early
stage and move forward in order. Later stages preserve earlier implementations
where they are useful for comparison.

## Course stages

| Stage | Main lesson |
| --- | --- |
| `00-establish-repository` | Repository and documentation skeleton |
| `01-json-backbone` | Inventory JSON contract and command-line tools |
| `02-linux-visible` | Linux processes, streams, environment, and files |
| `03-pi-http-server` | Small Python HTTP server suitable for a Raspberry Pi |
| `04-browser` | Plain HTML and JavaScript inventory client |
| `05-ec2-deployment` | Move the Linux HTTP process to EC2 |
| `06-lambda` | Run the inventory handler in AWS Lambda |
| `07-api-gateway` | Put an HTTP API in front of Lambda |
| `08-relational-persistence` | Map inventory JSON to relational tables |
| `09-rds` | Move the same relational schema to Amazon RDS |
| `10-lambda-rds` | Read RDS rows through Lambda without changing the JSON contract |
| `11-orders` | Validate and commit transactional warehouse orders |
| `12-concurrency` | Reproduce and prevent overselling |
| `13-sqs` | Send asynchronous pick-work commands through SQS |
| `14-domain-events` | Publish `OrderPlaced` events for independent consumers |
| `15-pick-ticket-worker` | Run a Linux worker that writes pick tickets |
| `16-callback-demo` | Trace the complete asynchronous path |
| `17-container-worker` | Package the worker as a container |
| `18-aws-deployment` | Describe the current AWS system as deployment artifacts |
| `19-git-history` | Map architectural milestones to Git history |
| `20-final-walkthrough` | Walk through the complete system end to end |

## How to use a stage

Each stage directory has its own `README.md`, source, data, documentation, and
tests. Treat the directory as the repository root for that lesson:

```bash
cd 03-pi-http-server
python3 -m unittest discover -s tests -v
```

To run the complete local suite from the final stage:

```bash
cd 20-final-walkthrough
python3 -m unittest discover -s tests -v
node --test tests/test_web_app.js
```

Stage 00 intentionally contains no application. Later stages may require
additional tools for the lesson they introduce:

- Python 3 for the application and tests
- Node.js for the small browser JavaScript test
- PostgreSQL for hands-on relational database exercises
- Docker for the container lesson
- AWS CLI and an AWS account only for explicitly chosen cloud exercises

The automated local tests use temporary files, SQLite-compatible test
connections, and mocked cloud boundaries. They do not require an AWS account.

## Contracts and continuity

JSON is the canonical interchange format. When a stage changes where code runs
or where data is stored, it preserves the meaning of established contracts
unless changing the contract is the lesson itself.

For each stage, ask:

1. Where is the code running?
2. Where is its data?
3. How did the data get there?
4. What representation crosses each boundary?
5. What happens when a component fails?
6. Who operates that component?

Use `docs/architecture.md` and `docs/data-contracts.md` inside each stage to
compare the current design with earlier snapshots.

## AWS cost and cleanup

Generating or reading AWS deployment artifacts does not deploy anything.
Cloud exercises are optional and require an explicit deployment step.

Before deploying a cloud lesson, read that stage's cleanup section and identify
resources that may incur charges. When the lesson is finished, remove its
CloudFormation stacks, RDS instances and snapshots, queues, event rules,
functions, APIs, logs, images, and temporary artifacts as directed by the stage
README.

Never commit credentials, access keys, database passwords, populated `.env`
files, private keys, or account-specific parameter files.

