# Session 26 — Containers, then responsibility boundaries across the whole system

**Stage:** `17-container-worker` · **Repo support:** Yes for the files; **the container as shipped does not start** (see the first caveat) · **Run from:** `20-final-walkthrough/`

**Concept (20 min):** a container is a packaged process environment: image, container, filesystem, environment, port, volume; then responsibility boundaries.
**Demo (20 min):** containerize the pick worker, run it, feed it the same message, preserve its output; draw the final architecture beside the Session 1 version.

## Check this first
`src/Dockerfile` copies `pick_ticket_worker.py` and `sqs_consumer.py` into a flat `/app` directory, but the worker begins with `from src.sqs_consumer import consume_messages`. Inside the image there is no `src` package, so the container exits at once with `ModuleNotFoundError: No module named 'src'`. I reproduced the same import error by copying just those two files into a clean directory; I did not run Docker. Two fixes; pick one before class:
- change the import to `from sqs_consumer import consume_messages` when running in the container, or
- keep the package layout: `COPY src/ /app/src/`, `WORKDIR /app`, `ENTRYPOINT ["python3", "-m", "src.pick_ticket_worker"]`.

## Run sheet (once the import is fixed)
```bash
docker build -f src/Dockerfile -t tinywms-pick-ticket-worker .
```
Run it with the ticket ledger and the idempotency state on a volume, so they survive the container (the form from the stage-20 runbook, which is the better one because it mounts a directory):
```bash
mkdir -p data
docker run --rm \
  -e PICK_WORK_QUEUE_URL="$PICK_WORK_QUEUE_URL" \
  -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_DEFAULT_REGION \
  -v "$PWD/data:/state" \
  tinywms-pick-ticket-worker "$PICK_WORK_QUEUE_URL" /state/pick-tickets.txt \
  --state-file /state/pick-ticket-worker-state.json --once
cat data/pick-tickets.txt
```
Then run it again with the same queue: the state file means no duplicate tickets. Delete `data/pick-tickets.txt` and `data/pick-ticket-worker-state.json` between runs.
Note the AWS credentials: inside a container nothing in `~/.aws` exists. Pass environment variables, mount the directory, or (on EC2) rely on the instance role. This is session 10 again.

Walk the Dockerfile: base image, `WORKDIR`, `COPY`, `ENTRYPOINT`/`CMD`. The README for this stage is `deploy/container-worker/README.md`; its example mounts single files into `/app`, which Docker creates as directories if the host file does not exist, so prefer the directory mount above.

## Final architecture exercise (the second half of the session)
1. Put the Session 1 picture back on screen (browser → Pi → JSON file) and have students draw today's system beside it: browser → API Gateway → Lambda → RDS; Lambda → SQS → worker (container or service) → ticket file; Lambda → EventBridge → subscriber queues.
2. For every box write who is responsible: AWS (API Gateway, Lambda runtime, RDS, SQS, EventBridge), you (schema, code, IAM policies, worker host or container, secrets).
3. For every arrow write the representation that crosses it (HTTP+JSON, SQL rows, queue message JSON, event JSON, file lines).
4. Mark the arrows that fail independently and recall session 20's table.
5. Use `20-final-walkthrough/docs/end-to-end.md` as an answer key.
