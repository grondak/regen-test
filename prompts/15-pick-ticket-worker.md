# Stage 15: Build the pick-ticket worker

Evolve the Python queue consumer into a pick-ticket worker. Given an order/pick-work JSON message, produce
a human-readable warehouse pick ticket containing command ID, order ID, SKU, description, quantity and
bin location. Append tickets to `pick-tickets.txt`.

Make the worker a real long-running SQS process/service. Prefer explicit reuse of the Stage 13
`sqs_consumer.consume_messages(...)` boundary instead of duplicating its receive/delete logic. Repeatedly
long-poll, process all returned messages, append output, and delete each queue message only after its
ticket operation succeeds. Its callback accepts the already-decoded command JSON produced by
`consume_messages(...)`; do not read a `Body` field or call `json.loads` on that callback value again.
Provide a bounded `--once` mode for deterministic local tests and classroom exercises. Handle SIGINT/SIGTERM with
a visible orderly shutdown. Preserve stdout/stderr logging so students can inspect it with ordinary Linux
tools.

Add concrete operations artifacts under `deploy/pick-ticket-worker/`: a readable systemd user-service
template, an installer that resolves the current stage directory into the installed unit, an environment
example, and a README with exact install/start/status/log/stop/disable commands. The installed service must
run long-lived mode (never `--once`), restart on failure, load the queue URL visibly, and leave ticket and
idempotency state in documented durable paths. Include `journalctl --user` and `tail -f` demonstrations.

Use the stable `command_id` to prevent a redelivered command from appending a duplicate ticket. Keep the
idempotency state durable across process restarts and explicit/inspectable rather than hiding it behind a
framework. Include the command ID in the ticket. Document the crash boundary between ticket output,
idempotency recording, and SQS acknowledgement. An empty receive must continue polling in service mode;
only `--once` or an orderly SIGINT/SIGTERM may stop the loop. Tests must cover multiple messages,
duplicate delivery in one process, duplicate delivery after a simulated restart, processing failure
without acknowledgement, acknowledgement after output, an empty poll in service mode, and bounded
execution. Give these proofs descriptive `test_...` names that include the behavior terms (multiple,
duplicate, restart, failure, delete/acknowledgement, empty, and once/bounded). Add concrete foreground and
systemd service instructions that invoke the long-running mode.

Update `docs/architecture.md` "Component Assembly Map" to show the consumer-to-worker evolution and the new output artifact component (`pick-tickets.txt`) as part of the system.

The stage README must include purpose, worker file map, start/stop/test commands, exercises, cleanup
notes, continuity note, and a "Component assembly update" section. Placeholder README output is not acceptable.
