# Stage 13: Add asynchronous work with SQS

After a successful committed order, publish versioned JSON pick-work commands to Amazon SQS. Emit one
command for every order line; do not silently drop later lines. Each command must contain a stable
`command_id`, `order_id`, `sku`, `quantity`, and the bin obtained from the locked inventory row. A
hard-coded bin is invalid. Include the locked row's description so the downstream ticket does not invent
or lose the item description. Define and document that message contract. The HTTP request must not perform
pick-ticket generation synchronously.

Tests must prove ordering: no SQS publish occurs when the database transaction rolls back, and `send_message` occurs only after a successful commit. Inject the SQS client and database connection so this proof stays local and does not call AWS.

This stage requires complete implementation deltas for `src/lambda_inventory.py`,
`tests/test_lambda_inventory.py`, `tests/test_concurrency.py`, `src/sqs_consumer.py`, and
`tests/test_sqs_consumer.py`; infrastructure or documentation changes alone are invalid. Start from the
working Stage 12 order transaction and adapt the mature final-reference queue code as follows:

1. Evolve `place_order(connection, order)` to `place_order(connection, order, sqs_client=None)`.
2. Retain each normalized locked inventory row while the transaction is open.
3. Exit the transaction context so commit has completed.
4. Resolve the injected-or-boto3 SQS client and queue URL only after that boundary.
5. Build and send one command for every order line using the matching locked row.

Carry forward the final reference's `_command_id`, `_build_pick_work_commands`, and `_sqs_client` shapes,
but omit `_eventbridge_client`, `put_events(...)`, and all EventBridge behavior until Stage 14. Update the
inherited Lambda and concurrency tests so every order-path call passes a fake SQS client and so the tests
prove commit-before-send and rollback-without-send.

Add a small Python consumer with a stable `consume_messages(...)` function. Each call must make exactly
one injected-or-boto3 SQS `receive_message` long poll, process every message in that returned batch, pass
the decoded JSON body (not the raw SQS envelope) to its callback, and then return the processed count.
The consumer function must not own an unbounded drain/service loop; Stage 15 will own the process
lifetime and call it again. Make the AWS message ID, receipt handle, approximate
receive count, acknowledgement, and retry/redelivery behavior visible in the code. Call
`delete_message` only after the processing callback succeeds. On processing failure, leave the message
undeleted so SQS can redeliver it.

Document that a standard SQS queue provides at-least-once delivery and best-effort ordering; do not imply
exactly-once processing or strict ordering. Tests must use a fake injected SQS client and prove receive,
success/delete, failure/no-delete, and multiple-message behavior without calling AWS. Use descriptive
test names such as `test_success_deletes_message`, `test_callback_failure_does_not_delete`, and
`test_processes_each_message` so those distinct proofs remain visible. The single-message success test
must prove that one `consume_messages(...)` call makes one `receive_message(...)` call. A consumer that
reads only stdin or a local JSON file and prints a fabricated acknowledgement is a placeholder.

If the locked inventory query evolves to return bin/description columns, update every inherited fake
cursor and concurrency test in the same stage so its row shape still matches the real query.

Queue publish/consume instructions must use real queue identifiers resolved from deployment outputs or CLI queries. Do not present fabricated queue URLs as if they are runnable.

Required deployment artifacts for this stage:
- `infra/sqs.yaml` (or equivalent CloudFormation template) defining queue resources and any wiring required by the order path.
- `deploy/sqs/README.md` containing exact deploy/update, output-resolution (queue URL/ARN), publish/consume verify, and destroy commands.
- if this stage modifies Lambda publish behavior, update the corresponding Lambda/API deployment artifacts in the same stage so queue integration is redeployable.

Update `docs/architecture.md` "Component Assembly Map" to add asynchronous command components (publisher, queue, consumer) and their dependencies on committed order state.

The stage README must include purpose, queue/message file map, publish/consume/test commands, exercises,
cleanup/destruction notes, continuity note, and a "Component assembly update" section. Placeholder README output is not acceptable.
