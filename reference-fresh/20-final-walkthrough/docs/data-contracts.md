# TinyWMS Data Contracts

This document describes TinyWMS JSON, HTTP, SQL, event, queue, file, and worker contracts as the course progresses.

## Current state
Stage 1 introduces the first contract: a small inventory JSON file with clearly documented fields. Stage 4 reuses that same contract in the browser without changing the data model. Stage 5 keeps that contract unchanged while adding EC2 deployment instructions around the same HTTP server. Stage 6 adds a Lambda compute path that still returns the same inventory JSON shape. Stage 7 adds API Gateway as a front door in front of the Lambda path without changing the inventory JSON contract. Stage 8 adds a relational representation of the same inventory concepts so students can see how visible JSON fields map into SQL tables and seed statements. Stage 9 keeps the relational contract the same and changes only the database hosting boundary to Amazon RDS. Stage 10 changes the deployed Lambda read path to the database while keeping the inventory response shape identical. Stage 11 adds a separate, explicit order JSON contract and uses it in the HTTP server, browser page, and Lambda order handler. Stage 12 keeps the same order JSON contract but hardens the transaction boundary. Stage 13 adds a new pick-work command contract that is emitted after commit and received from SQS. Stage 14 adds an OrderPlaced domain event contract that is emitted after the same commit and delivered to separate consumers. Stage 15 turns the consumer into a durable pick-ticket worker that writes human-readable file output and persists processed command IDs. Stage 20 keeps those contracts intact while improving the local browser and HTTP path that demonstrates them.

## Inventory JSON contract
Each inventory item is a JSON object with these fields:
- `sku` - stable item identifier used for lookups and display
- `description` - human-readable product description
- `bin_location` - warehouse bin or shelf location
- `quantity` - on-hand quantity as a non-negative integer
- `unit` - unit of measure such as `each`, `case`, or `box`

The inventory file is a JSON array of these objects.

## Order JSON contract
Stage 11 introduces a minimal order request object:
- `order_id` - non-empty string chosen by the browser or client
- `lines` - non-empty array of order line objects

Each order line object contains:
- `sku` - non-empty string identifying the inventory item to reserve
- `quantity` - positive integer quantity to remove from inventory
- `description` - optional human-readable description echoed in the browser and visible code paths

The HTTP server and Lambda handler both validate the request before applying inventory changes. Successful requests return a small JSON object with the accepted `order_id` and `status` fields; rejections return JSON error objects with a visible message.

## JSON to relational mapping
Stage 8 introduced a minimal relational model derived from the same inventory records:
- `sku` maps to the table primary key.
- `description` maps to a required text column.
- `bin_location` maps to the SQL `bin_location` column in the lesson schema.
- `quantity` maps to a non-negative integer column.
- `unit` maps to a required text column.

The lesson keeps the mapping intentionally small so students can compare the same business data in two representations:
- JSON file rows in `data/inventory.json`
- SQL schema in `data/schema.sql`
- SQL seed rows in `data/seed.sql`
- SQL export output from `src/sql_export.py`

## RDS operational shift
Stage 9 does not change the data model. It changes where the database runs and who operates it:
- self-managed Linux database process: student installs, starts, patches, backs up, and monitors the database
- Amazon RDS: AWS operates the database instance, endpoint, storage, and much of the routine availability work; students still manage schema, credentials, connectivity, and application behavior

The same SQL schema and seed statements are the teaching artifacts in both cases.

## SQLite and PostgreSQL note
Stage 20 adds a local SQLite execution path for the order workflow and database schema tests. SQLite is useful for a portable teaching demo, but it cannot prove row locking behavior. Stage 12 concurrency remains a PostgreSQL lesson because only PostgreSQL can exercise the real `FOR UPDATE` overlap boundary used by the hardening tests.

## Pick-work command contract
Stage 13 adds a queue message that the order Lambda emits after commit. The message is JSON and must remain easy to inspect.

Required fields:
- `command_id` - stable identifier for the queue command, derived from order ID, SKU, quantity, and bin location
- `order_id` - original order identifier
- `sku` - SKU taken from the locked inventory row
- `description` - product description taken from the locked inventory row
- `quantity` - quantity to pick
- `bin` - bin location taken from the locked inventory row

The command is emitted once for every order line. The queue consumer receives the decoded JSON body, not the raw SQS envelope, and acknowledges only after successful processing.

## OrderPlaced domain event contract
Stage 14 adds a fact event that says what happened after the order commit completed.

Required fields:
- `version` - small integer schema version for the event detail
- `order_id` - original order identifier
- `lines` - array of order line objects containing the reserved `sku` and `quantity`

The event envelope is produced with these visible fields:
- `Source` - the TinyWMS order source string
- `DetailType` - `OrderPlaced`
- `Detail` - JSON detail payload encoded as a string for EventBridge delivery

This contract is separate from the SQS command contract:
- the SQS message is imperative and tells a worker to do a task
- the event message is descriptive and tells consumers that the order was placed

## Pick-ticket output contract
Stage 15 adds a durable file output contract created by the worker after successful command processing.

Required fields per line:
- `command_id` - copied from the decoded pick-work command
- `order_id` - original order identifier
- `sku` - SKU being picked
- `description` - human-readable item description from the command
- `quantity` - quantity being picked
- `bin` - bin location from the command

The worker appends one human-readable line per processed command to `pick-tickets.txt`. The worker also persists a separate idempotency record of processed `command_id` values so redelivered queue messages do not create duplicate tickets after a restart.

## Planned contract areas
- inventory JSON
- order JSON
- command-line interfaces
- HTTP requests and responses
- browser data rendering
- deployment and operator inputs
- Lambda event input and output
- relational mappings
- queue and event message formats
- worker output files
