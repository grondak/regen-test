# Stage 17: Containerize only the worker

Add a Dockerfile for the pick-ticket worker. Keep it simple enough to explain in one 90-minute class. Demonstrate image, container, process, environment variables and persistent output volume.

Do not containerize everything merely for consistency. The purpose is to show that the same Linux process can run in a packaged execution environment.

Run the long-lived SQS worker by default. The documented `docker run` command must supply the queue URL
and mount durable ticket/idempotency state. Preserve a bounded `--once` example for a deterministic
classroom demonstration. Container tests must check the actual entrypoint and worker arguments, not only
the presence of filenames.

Container tests must assert stable artifacts such as `src/Dockerfile` and the Component Assembly Map in
`docs/architecture.md`. They must not read or assert lesson-specific text in the root `README.md`, because
that teaching guide is intentionally replaced by Stages 18–20.

Add a persistent guide at `deploy/container-worker/README.md`. Its exact `docker run` command must mount
host-backed durable paths for both `pick-tickets.txt` and the processed-command/idempotency ledger, pass
the queue URL through an environment variable, and include a bounded `--once` demonstration. Tests must
check the actual mounts, entrypoint, and arguments.

Update `docs/architecture.md` "Component Assembly Map" to represent containerized worker runtime as an alternate execution component for the same worker contract, not a contract change.

The stage README must include purpose, Docker/worker file map, build/run/test commands, exercises,
cleanup commands (images/containers/volumes), continuity note, and a "Component assembly update" section. No placeholder README text.
