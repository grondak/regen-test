# Stage 20: Produce the final architecture walkthrough

Create `docs/end-to-end.md` tracing one warehouse order through every component of the final system. At each hop identify: executing code, compute environment, input JSON, output JSON, network boundary, persistent state, possible failure and responsible operator/provider.

Include Mermaid diagrams suitable for GitHub rendering. Relate the final architecture back to Raspberry Pi/Linux concepts without turning the document into AWS marketing material.

Add `docs/demo-runbook.md` with exactly one clearly numbered section for each of the 26 syllabus sessions.
Each section must name the backing stage(s), give exact runnable commands when the repository supports the
demo, and label instructor-only work as `Manual only` or `Partly manual`. It must not pretend that AWS,
PostgreSQL, Docker, systemd, physical Pi hardware, DNS, or security-group behavior was locally verified.
The runbook must include the SQLite initialization/order proof, PostgreSQL-only concurrency boundary,
worker systemd operations, persistent Docker volume demonstration, and finished order-to-pick-ticket journey.
Use the exact supported command forms, including
`TINYWMS_DB=sqlite TINYWMS_SQLITE_PATH=data/tinywms.db python3 -m data.init_db`,
`systemctl --user status tinywms-pick-ticket-worker`, `journalctl --user`, `tail -f`, and the documented
durable-mount `docker run` command.

Use the completed "Component Assembly Map" as source material and ensure the walkthrough explicitly narrates how the final system is assembled from components introduced across stages.

The walkthrough may describe only executable connections backed by source, tests, infrastructure, and
runnable commands. Require a final local system test that proves the integrated inventory/order HTTP
path, database-backed quantity change, emitted pick-work command, worker consumption, duplicate-command
handling, and pick-ticket output with fake AWS clients. Require deployment-structure tests that prove the
corresponding SQS/EventBridge environment, IAM, rules, targets, Lambda handler, and package wiring.

The final browser must contain the order workflow and refresh inventory after acceptance without a
hard-coded local origin. The final SQS consumer and pick-ticket worker must use real receive/delete
semantics, and the final EventBridge consumers must process delivered JSON from two independent targets.
Documentation-only connections, print stubs, and presence-only tests are invalid.

The accumulated safe local tests must run with the Python standard library alone. Tests may inspect YAML
as text but must not import PyYAML/`yaml`, boto3, botocore, psycopg, or psycopg2; inject fakes at those
boundaries instead.

Final-stage cloud artifact continuity requirement:
- when the final walkthrough references AWS-deployed behavior, ensure corresponding deployment artifacts remain present and runnable (for example `infra/template.yaml` and `deploy/aws/README.md`);
- if walkthrough validation reveals broken API/Lambda/RDS/SQS/event deployment instructions, fix those source artifacts in this stage rather than describing the broken behavior;
- treat the Stage 19 checkpoint directory as read-only, but emit corrected Stage 20 replacements for inherited artifacts that fail validation;
- an RDS subnet group must receive real subnet IDs through an explicit deployment parameter rather than `SubnetIds: []`, and database credentials must use deploy-time parameters with secrets marked `NoEcho` rather than committed placeholder values;
- include explicit references to output-resolution-first verification commands for `GET /inventory` and `POST /orders` in the deploy guide path.

File-reference integrity requirements for this stage:
- Any file referenced in `README.md` under `Files in this lesson` must exist exactly as named.
- Do not generate malformed test filenames such as `*.md.py` unless such a file is intentionally created (normally it should not be).
- Prefer clear final-stage test names like `tests/test_end_to_end_walkthrough.py` and ensure the file exists.
- Run a final compatibility pass over every inherited test. Update tests that import `src/` modules so the documented test command works, and replace assertions tied to an obsolete earlier root README with assertions against stable component files, contracts, or lesson-specific deployment guides.
- The accumulated test suite must remain meaningful: repair broken tests rather than deleting them or weakening functional contract checks.

Update stage README with purpose, document map, generation/validation commands (if any), student review
tasks, continuity note, and a "Component assembly update" section. Placeholder README output is not acceptable.
Student exercises must produce visible output first. If they mention tests, phrase them only as an optional
follow-up after submitting, inspecting, observing, curling, viewing, comparing, or tailing real behavior.
