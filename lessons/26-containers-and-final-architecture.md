# Session 26 — Containers, then responsibility boundaries across the whole system

**Stage:** `17-container-worker` · **Repo support:** Yes (the Dockerfile bugs are fixed; the image has not been built here because Docker was unavailable) · **Run from:** `20-final-walkthrough/`

**Concept (20 min):** a container is a packaged process environment: image, container, filesystem, environment, port, volume; then responsibility boundaries.
**Demo (20 min):** containerize the pick worker, run it, feed it the same message, preserve its output; draw the final architecture beside the Session 1 version.

## Status of the Dockerfile (updated)
Two bugs were found in the first draft of this lesson, and both are fixed in the code (stages 17–20). **The image has still not been built or run**: the Docker daemon was not reachable when this was checked, so treat the first `docker build` as a rehearsal item.
- The worker's import (`from src.sqs_consumer import ...`) failed in the flat `/app` layout. It now falls back to `from sqs_consumer import ...`. I confirmed that by copying only the files the image contains into an empty folder and running the worker there.
- The `COPY` lines assumed the build context was `src/`, but the documented command (`docker build -f src/Dockerfile -t tinywms-pick-ticket-worker .`) uses the stage root. They now read `COPY src/...`, and the image also gets `local_aws.py`, which lets the container read the local queue folder.

## Run sheet
*Demo scripts: set `TINYWMS` and `LESSONS` first (see README → Running the demos).*

```bash
cd "$TINYWMS/20-final-walkthrough"
docker build -f src/Dockerfile -t tinywms-pick-ticket-worker .
```

**Offline version (no AWS): feed the container from the local queue folder.** The folder `local-aws/` is shared with the container as a volume, so the queue, the tickets and the idempotency state all live on the host:
```bash
rm -rf local-aws pick-tickets.txt && export TINYWMS_LOCAL=1
python3 src/http_server.py &                                   # server only; no worker
sleep 1
curl -s -d '{"order_id":"C-1","lines":[{"sku":"SKU-1001","quantity":2}]}' localhost:8000/orders
ls local-aws/pick-work                                          # the message waiting for a consumer
docker run --rm -e TINYWMS_LOCAL=1 -v "$PWD/local-aws:/state" tinywms-pick-ticket-worker \
  /state/pick-work /state/pick-tickets.txt --state-file /state/pick-ticket-worker-state.json --once --wait-time-seconds 1
cat local-aws/pick-tickets.txt                                  # the ticket, written inside the container, kept on the host
ls local-aws/pick-work                                          # empty: the container acknowledged the message
kill %1
```
Run the same `docker run` again after posting another order: the first ticket is still there, because the volume outlived the container. Remove the volume mount and the ticket vanishes with the container; that is the image/container/volume distinction in one demo. (Not run for this plan: Docker was unavailable.)

**Against real SQS.** Run it with the ticket ledger and the idempotency state on a volume, so they survive the container (the form from the stage-20 runbook, which is the better one because it mounts a directory):
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
