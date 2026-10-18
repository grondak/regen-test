# TinyWMS containerized pick-ticket worker

This guide packages the pick-ticket worker as the only containerized component in the lesson.
It keeps the queue consumer and durable ticket ledger behavior unchanged while showing a simple
Docker runtime wrapper.

## What the container runs
The container launches `src/pick_ticket_worker.py` directly.
By default it stays in long-lived worker mode and expects the queue URL, ticket file, and state file
paths as arguments.

## Build the image
Run this from the repository root:

```bash
docker build -f src/Dockerfile -t tinywms-pick-ticket-worker .
```

## Run the worker with host-backed mounts
This example uses a queue URL supplied through `PICK_WORK_QUEUE_URL` and mounts the durable ticket
ledger plus the processed-command state file from the host.

```bash
docker run --rm \
  -e PICK_WORK_QUEUE_URL="$PICK_WORK_QUEUE_URL" \
  -v "$PWD/deploy/container-worker/pick-tickets.txt:/app/pick-tickets.txt" \
  -v "$PWD/deploy/container-worker/pick-ticket-worker-state.json:/app/pick-ticket-worker-state.json" \
  tinywms-pick-ticket-worker \
  "$PICK_WORK_QUEUE_URL" \
  /app/pick-tickets.txt \
  --state-file /app/pick-ticket-worker-state.json
```

### Notes
- `PICK_WORK_QUEUE_URL` keeps the queue endpoint visible as an environment variable.
- The first mount holds the durable `pick-tickets.txt` ledger on the host.
- The second mount holds the processed-command state file so restarts remember prior work.
- The container image does not talk to Docker or the network during tests; those contracts are checked by the
  repository tests instead.

## Bounded classroom command
Use `--once` for a short, bounded classroom run that handles one polling cycle and exits:

```bash
docker run --rm \
  -e PICK_WORK_QUEUE_URL="$PICK_WORK_QUEUE_URL" \
  -v "$PWD/deploy/container-worker/pick-tickets.txt:/app/pick-tickets.txt" \
  -v "$PWD/deploy/container-worker/pick-ticket-worker-state.json:/app/pick-ticket-worker-state.json" \
  tinywms-pick-ticket-worker \
  "$PICK_WORK_QUEUE_URL" \
  /app/pick-tickets.txt \
  --state-file /app/pick-ticket-worker-state.json \
  --once
```

## Cleanup
Remove the host-backed files when you are done with the exercise:

```bash
rm -f deploy/container-worker/pick-tickets.txt deploy/container-worker/pick-ticket-worker-state.json
```

## Reminder
The worker is the only containerized component in this stage. The rest of TinyWMS remains in the
standard Python and browser teaching path.
