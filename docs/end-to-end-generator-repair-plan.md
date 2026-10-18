# End-to-end generator repair plan

## Objective

Repair the TinyWMS browser, order, SQS, EventBridge, and pick-ticket path through the prompt-driven
generator. Do not hand-maintain fixes in `generated-forward/` or the published course repository.

The completed course must support one observable journey:

```text
inventory page
  -> POST /orders JSON
  -> committed inventory change
  -> one pick-work command per order line
  -> long-running SQS worker
  -> pick-tickets.txt
```

The same order also emits one versioned `OrderPlaced` event that reaches two independently observable
EventBridge targets. Every boundary must keep its JSON visible to students.

## Generator invariants

1. Prompts define lesson intent and stage ownership.
2. Forward behavior contracts turn the relevant prompt requirements into explicit generation acceptance
   conditions.
3. Deterministic validators reject convincing-looking stubs and disconnected components.
4. Focused reference repair groups may change only the files needed for one behavior cluster.
5. The final reference remains the architectural oracle for forward generation.
6. `--forward-all` revalidates existing checkpoints and regenerates only the invalid suffix.
7. Generated snapshots and the sibling course repository are outputs, never repair sources.
8. Local tests use fakes or local processes and never call live AWS.
9. Generating deployment artifacts does not authorize deploying AWS resources.

## Stage ownership

### Stage 11: integrated order journey

Update `prompts/11-orders.md` so the order lesson evolves the existing inventory page instead of adding
an isolated demonstration page.

Required generated behavior:

- `src/web/index.html` contains the inventory table, order form, request JSON, response JSON, and visible
  error state in one page.
- `src/web/app.js` uses a same-origin API base by default and permits one explicit runtime override. It
  must not contain a final hard-coded localhost URL.
- A successful order submission refreshes `GET /inventory` so the changed quantity is visible.
- The local HTTP application serves the browser assets and implements both `GET /inventory` and
  `POST /orders` through the same visible order contract.
- The Lambda/RDS path continues to use the transactional implementation introduced by this stage.
- Tests start the local server on an ephemeral port, submit an order, and prove that a later inventory
  response contains the decremented quantity.
- Keep a separate `src/order_form.html` only if it is explicitly documented as an earlier comparison
  artifact. It must not be the final browser workflow.

### Stage 13: real SQS receive and acknowledgement

Update `prompts/13-sqs.md` so “consumer” means a real queue consumer rather than a local JSON-file reader.

Required generated behavior:

- The publisher emits one versioned pick-work command per order line after the database commit.
- Each command contains a stable `command_id`, `order_id`, `sku`, `quantity`, and the bin obtained from
  the locked inventory row. No bin may be hard-coded.
- `src/sqs_consumer.py` calls an injected or boto3 SQS client's `receive_message` with long polling.
- It exposes the AWS message ID, receipt handle, receive count, and decoded JSON body.
- It calls `delete_message` only after the processing callback succeeds.
- On callback failure it leaves the message undeleted and reports that SQS can redeliver it.
- Documentation explains that a standard queue provides at-least-once delivery and best-effort ordering.
  It must not imply exactly-once delivery or strict ordering.
- Local tests use a fake SQS client to prove receive, success/delete, failure/no-delete, and multi-message
  behavior without contacting AWS.

### Stage 14: observable EventBridge fan-out

Update `prompts/14-domain-events.md` so the two independent consumers are backed by real EventBridge
routing targets.

Required generated behavior:

- Keep one versioned `OrderPlaced` event per accepted order, separate from pick-work commands.
- Define two EventBridge rules with the same `OrderPlaced` pattern and two independent targets.
- Prefer two SQS target queues for this teaching stage so delivery and payloads remain directly
  inspectable with AWS CLI and small Python consumers.
- Include the queue policies EventBridge needs to deliver to both targets.
- `event_consumer_a.py` and `event_consumer_b.py` receive and decode their own delivered event messages;
  passing a bus name and printing it is invalid.
- Tests inject independent fake queue clients and prove the same event reaches both consumers without
  coupling their behavior.
- Deployment documentation resolves all bus, rule, and target identifiers from stack outputs.

### Stage 15: long-running idempotent worker

Update `prompts/15-pick-ticket-worker.md` so the pick-ticket component is an actual service-shaped SQS
worker.

Required generated behavior:

- `src/pick_ticket_worker.py` repeatedly receives messages until interrupted.
- A bounded `--once` mode processes one receive batch and exits for local tests and classroom exercises.
- The worker appends one ticket per pick-work command and deletes the queue message only after the ticket
  operation succeeds.
- The ticket includes `command_id`, order ID, SKU, description, quantity, and database-derived bin.
- Duplicate `command_id` values do not append duplicate tickets. Keep the idempotency mechanism explicit
  and inspectable; document its crash boundary and limitations.
- SIGINT/SIGTERM produce a visible, orderly shutdown.
- Provide concrete foreground and systemd service instructions that invoke the long-running mode.
- Tests cover multiple messages, duplicate delivery, processing failure, acknowledgement ordering, and
  shutdown or bounded execution.

### Stage 16: executable callback demonstration

Update `prompts/16-callback-demo.md` so the instructor demonstration is an executable compatibility proof,
not only a narrative.

Required generated behavior:

- Add a local integration harness using the real HTTP application and worker logic with fake database,
  queue, and event clients.
- The proof loads inventory, submits an order, observes the changed quantity, consumes the emitted
  pick-work command, and observes the corresponding ticket line.
- Preserve request, response, command, event, and ticket representations in test output or fixtures.
- The browser and worker runbooks must use the same paths and commands exercised by tests.
- Cloud instructions remain output-resolution-first and must not fabricate endpoint, queue, or bus IDs.

### Stage 17: container continuity

Update `prompts/17-container-worker.md` only as needed to preserve the evolved worker contract.

Required generated behavior:

- The image runs the long-lived worker by default.
- `docker run` supplies the queue URL and mounts durable ticket/idempotency state.
- A bounded `--once` example remains available for a deterministic classroom demonstration.
- Container tests check the actual entry point and arguments rather than only searching for filenames.

### Stage 18: deployable assembly

Expand `prompts/18-aws-deployment.md` so the consolidated template wires the components it declares.

Required generated behavior:

- Lambda constructs real boto3 SQS and EventBridge clients when test doubles are not injected.
- Lambda receives `DATABASE_URL`, `PICK_WORK_QUEUE_URL`, and `EVENT_BUS_NAME` using names expected by the
  source code.
- The Lambda role grants narrowly scoped `sqs:SendMessage` and `events:PutEvents` permissions.
- EventBridge rules, two targets, and their resource policies are present.
- Queue URLs, bus name, and target identifiers are available as outputs.
- The Lambda ZIP layout matches its configured handler. If the ZIP contains `lambda_inventory.py` at its
  root, use `lambda_inventory.handler`; if it contains `src/lambda_inventory.py`, package `src` and use
  `src.lambda_inventory.handler`.
- Deployment verification exercises `GET /inventory`, `POST /orders`, both event targets, SQS worker
  delivery, and the ticket output in dependency order.
- Cleanup commands cover every resource created by the lesson.

### Stage 20: final truthfulness gate

Expand `prompts/20-final-walkthrough.md` so the final narrative may describe only executable connections.

Required generated behavior:

- The walkthrough's component sequence exactly matches deployed resources and runnable commands.
- A final local system test proves the browser/API/order/queue/worker path with fakes at AWS boundaries.
- Deployment-structure tests prove the corresponding cloud wiring exists.
- The final stage retains the earlier comparison artifacts while naming which implementation is the
  current assembled path.

## Deterministic generator changes

### Behavior audits

Extend `_validate_behavior_continuity` in `toolchain/regen.py` with stage-gated checks:

- Stage 11: reject final browser code containing literal `127.0.0.1` or `localhost`; require order submit,
  inventory refresh, local `do_POST`, and an HTTP integration test.
- Stage 13: require `receive_message`, long-poll configuration, `delete_message`, failure/no-delete tests,
  stable command IDs, all-line command production, and a nonliteral bin source.
- Stage 14: require two EventBridge rules, two targets, target permissions/policies, and consumers that
  decode delivered event JSON.
- Stage 15: require a receive loop, bounded test mode, duplicate handling, acknowledgement-after-output,
  and multi-message tests.
- Stage 16: require an integration test that observes quantity change and ticket output from one order.
- Stage 17: require the container entry point to run the service-shaped worker.
- Stage 18: require source/template agreement for environment names, IAM actions, clients, handler path,
  package layout, rules, and targets.
- Stage 20: require both the local system proof and deployment-wiring proof before accepting the
  walkthrough.

Prefer parsing Python with `ast`, JSON with `json`, and CloudFormation YAML with constrained structural
checks where the standard-library implementation is practical. Use narrow textual checks only for simple,
unambiguous invariants. Aggregate related failures so one repair request sees the complete defect set.

### Forward behavior acceptance contracts

Expand `_forward_behavior_generation_contract` for Stages 11, 13, 14, 15, 16, 17, 18, and 20. Each
contract must name the concrete files and tests the stage is expected to emit. The contract must say that
documentation-only deltas, print stubs, fabricated acknowledgements, and presence-only tests are invalid.

### Focused reference repair

Replace the broad messaging repair with independently validated groups:

1. `integrated browser and local order HTTP path`
2. `multi-line database-derived pick-work commands`
3. `real SQS receive, acknowledgement, and worker lifecycle`
4. `EventBridge fan-out and independent targets`
5. `consolidated deployment wiring and Lambda packaging`
6. `final local system proof and walkthrough`

Each group must define:

- a narrow objective;
- its validation stage;
- an explicit file allowlist;
- the smallest useful context set;
- tests that must pass before the next group runs.

Cache each accepted overlay through the existing reference-repair cache so a later failed group does not
spend tokens regenerating an earlier accepted repair.

### Blueprint requirements

Ensure `course-blueprint.json` models these components and contracts explicitly:

- integrated browser application;
- local HTTP order adapter;
- SQS command publisher;
- real SQS receiver;
- idempotent pick-ticket worker;
- pick-ticket output/idempotency state;
- EventBridge bus;
- fan-out rule A and target A;
- fan-out rule B and target B;
- consolidated deployed assembly;
- local end-to-end compatibility proof.

Component dependencies must name the command/event contracts they consume. Stage classifications should
show the Stage 4 browser and Stage 3 HTTP server being evolved at Stage 11, the Stage 13 consumer being
evolved into the Stage 15 worker, and the Stage 15 worker being reused by Stages 16-20.

## Toolchain regression tests

Add tests to `toolchain/test_regen.py` for every new rejection rule. Each test should start from the
smallest valid snapshot and introduce one defect, then assert the actionable validator message.

Minimum cases:

1. hard-coded final browser origin;
2. missing local `POST /orders`;
3. order submit without inventory refresh;
4. SQS consumer without `receive_message`;
5. unconditional or premature `delete_message`;
6. first-order-line-only command generation;
7. literal pick bin;
8. EventBridge bus without two rules/targets;
9. event print stub;
10. one-shot worker without bounded/service modes;
11. missing duplicate-command handling;
12. missing end-to-end local proof;
13. source/template environment-name mismatch;
14. missing SQS/EventBridge IAM actions;
15. Lambda ZIP/handler mismatch;
16. walkthrough naming an unimplemented connection.

Retain positive tests containing small accepted examples so validators do not force one incidental coding
style.

## Execution sequence

### 1. Implement prompt and toolchain changes

Change only prompts, generator logic, blueprint logic if required, toolchain tests, and generator
documentation. Do not edit generated snapshots as the implementation mechanism.

### 2. Run generator tests

```bash
python3 -m unittest discover -s toolchain -p 'test_*.py' -v
git diff --check
```

### 3. Rebuild and validate the reference

Use the existing Stage 19 checkpoint as a read-only seed:

```bash
python3 toolchain/regen.py \
  --prompt-dir prompts \
  --build-reference \
  --reference-seed-root generated-forward \
  --reference-output reference/20-final-walkthrough \
  --validation-retries 2
```

Run the reference's documented complete local test command. Do not perform live AWS tests unless they are
separately authorized.

### 4. Regenerate the invalid suffix

```bash
python3 toolchain/regen.py \
  --prompt-dir prompts \
  --forward-all \
  --reference-output reference/20-final-walkthrough \
  --output generated-forward \
  --validation-retries 2
```

`--forward-all` must validate existing checkpoints under the stronger rules. It should retain the latest
contiguous valid checkpoint and regenerate the first invalid stage plus all successors. Do not delete
accepted earlier checkpoints merely to force a clean run.

### 5. Run safe generated-course tests

- Run every runnable stage's documented local tests.
- Treat Stage 00 as intentionally having no application tests.
- Run the Stage 16 and Stage 20 local integration proofs explicitly.
- Confirm tests use fake AWS clients and create no cloud resources.
- Confirm no credentials, generated bytecode, or runtime ticket/idempotency files are publication inputs.

### 6. Review adjacent-stage continuity

Review diffs and handoff notes at these boundaries:

- Stage 10 -> 11: inventory-only browser becomes integrated order browser.
- Stage 12 -> 13: committed order gains real asynchronous command delivery.
- Stage 13 -> 14: command path remains intact while event fan-out is added.
- Stage 14 -> 15: receiver evolves into a long-running idempotent worker.
- Stage 15 -> 16: components are assembled without hidden replacement.
- Stage 16 -> 17: worker contract survives containerization.
- Stage 17 -> 18: local components receive deployable AWS wiring.
- Stage 19 -> 20: final documentation matches executable reality.

For every boundary, verify inherited contracts, boundary shift, failure/restart path, reuse proof,
integration delta, and compatibility command.

### 7. Publish through the guarded publisher

Before publication, the sibling `tinywms-course` repository must have a clean worktree. The current
publication must be reviewed and committed, stashed, or deliberately removed by the operator first; do
not bypass the clean-tree guard.

Then run:

```bash
python3 toolchain/publish_generated.py \
  --source generated-forward \
  --dry-run

python3 toolchain/publish_generated.py \
  --source generated-forward
```

Publication does not include committing, pushing, or deploying AWS resources.

## Completion criteria

The repair is complete only when all of the following are true:

- All toolchain tests pass.
- The final reference passes its complete local suite.
- Every runnable generated stage passes its documented local suite.
- Stage 11 demonstrates order submission and visible inventory change from one page.
- Stage 13 demonstrates real receive/delete semantics with fake-client tests.
- Stage 14 has two real, independently observable EventBridge targets.
- Stage 15 processes multiple queue messages, suppresses duplicate command IDs, and stays running until
  stopped unless `--once` is selected.
- Stage 16 proves the local browser/API/order/queue/worker/ticket chain.
- Stage 18 structurally wires every environment variable, permission, resource, target, handler, and
  package path required by the source.
- Stage 20 describes only connections proven by code, tests, and deployment artifacts.
- The regenerated suffix preserves earlier contracts and comparison artifacts.
- The guarded publisher accepts the complete checkpoint chain.

