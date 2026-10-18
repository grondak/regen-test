# Stage 14: Introduce domain events

Add an `OrderPlaced` JSON event distinct from the imperative pick-work message. Use an appropriate AWS event service and make the distinction between "do this" and "this happened" explicit in code and documentation.

The order path must call EventBridge `put_events` with the visible versioned event after commit, in addition to the separate SQS `send_message` command. Tests must inject both clients and assert the two payload shapes and semantics without calling AWS.

Update every inherited local order and concurrency test that calls the order path so it injects both a
fake/no-op SQS client and a fake/no-op EventBridge client. No local test may fall through to boto3 merely
because it is focused on concurrency or multi-line SQS behavior.

Demonstrate at least two independent consumers of the event without coupling them to the order Lambda.
Back the demonstration with two real EventBridge rules using the same `OrderPlaced` pattern and two
independently observable targets. Prefer one SQS queue per target so students can inspect delivery with
the AWS CLI and small Python consumers. Include the queue policies that authorize EventBridge delivery.
Keep the event schema small and versionable.

The two Python consumers must receive and decode delivered event JSON from their own target queues. A
script that accepts an event-bus name and only prints it is a placeholder. Tests must inject independent
fake queue clients and prove that both consumers process the same event shape without coupling their
behavior or calling AWS.

Event publishing commands must use real event-bus identifiers resolved from deployment outputs or explicit stage config variables. Do not use fabricated bus names/ARNs as runnable defaults.

Required deployment artifacts for this stage:
- `infra/events.yaml` (or equivalent CloudFormation template) defining the event bus, two rules, two
  targets, target queues, and delivery policies used in this lesson.
- `deploy/events/README.md` containing exact deploy/update, output-resolution (event bus name/ARN), publish/consume verify, and destroy commands.
- if this stage updates order Lambda event emission, update the related cloud deployment artifacts in the same stage so event flow remains deployable end-to-end.

Update `docs/architecture.md` "Component Assembly Map" to distinguish command components (SQS path) from event components (EventBridge + independent consumers), including what is shared and what is decoupled.

Update stage README with purpose, event-schema/file map, run/test commands for both consumers, exercises,
cleanup notes, continuity note, and a "Component assembly update" section. Do not emit placeholder README text.
