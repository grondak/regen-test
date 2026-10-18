# Stage 18: Make the whole thing deployable

Create a reproducible AWS deployment for the current TinyWMS cloud architecture using a suitable infrastructure-as-code mechanism. Include API Gateway, Lambda, IAM, RDS connectivity, SQS/event resources and necessary observability.

This stage must not emit placeholder deploy artifacts. Require deployable, concrete infrastructure definitions and operator commands.

The consolidated template must deploy the actual `src/lambda_inventory.py` implementation through a visible packaging step (for example `aws cloudformation package` plus an S3-backed Lambda `Code` block, or SAM `CodeUri`). An inline function that only returns a message telling students to upload/package code later is a placeholder and must fail validation.

The packaged module layout and configured Lambda handler must agree. If the ZIP contains
`lambda_inventory.py` at its root, use `lambda_inventory.handler`; if the ZIP preserves
`src/lambda_inventory.py`, package `src` and use `src.lambda_inventory.handler`.
Package every local module imported by the handler, including `src/db_adapter.py`; a ZIP containing only
`lambda_inventory.py` is not deployable once the handler uses the explicit database adapter.

Wire the source code and infrastructure using the same visible environment names. The Lambda must receive
`DATABASE_URL`, `PICK_WORK_QUEUE_URL`, and `EVENT_BUS_NAME`, construct real boto3 SQS and EventBridge
clients when test doubles are not injected, and receive narrowly scoped `sqs:SendMessage` and
`events:PutEvents` permissions. Define the two EventBridge rules, targets, and target resource policies
introduced earlier; declaring only an event bus is incomplete.

Test production client construction behaviorally: import `lambda_inventory`, install or patch a fake
`boto3` module, call `_sqs_client()` and `_eventbridge_client()` without injected clients, and assert that
`client("sqs")` and `client("events")` were requested. Do not inspect source for exact optional-dependency
error-message prose; wording is not part of the contract.

All safe local tests must run with the Python standard library alone. Do not import PyYAML/`yaml`, boto3,
botocore, psycopg, or psycopg2 in tests. Inspect CloudFormation as text and inject fake modules/clients.
Every literal `assertIn`/`assertNotIn` against template text must agree with the actual
`infra/template.yaml`; assert the real environment wiring such as
`PICK_WORK_QUEUE_URL: !Ref PickWorkQueue`, not an invented `QueueUrl` property.
Apply the same rule to `deploy/aws/README.md`: assert literal text that is actually present in the guide.
For example, if the executable proof is `curl "$API_BASE_URL/inventory"`, do not invent a prose label such
as `GET /inventory` solely to make a test pass.

Do not place `placeholder`, `placeholder-db-endpoint`, dummy database users/passwords, or a fabricated
`DATABASE_URL` in the runnable template. Model environment-specific database connection inputs as required
deployment parameters, mark secret parameters `NoEcho`, and build the Lambda environment value from those
parameters without committed defaults.

Minimum infrastructure content requirements:
- define real resources for API entry, compute, database connectivity, queue/event path, IAM permissions, and logs/observability;
- include explicit resource names/identifiers and outputs that students can use in later stages (for example API base URL, queue URL/ARN, function name, database endpoint/port, and event bus name where applicable);
- include concrete parameter/input variables for region, stack/project name, and secret values without committing secrets;
- include explicit teardown instructions that remove all cost-incurring resources created by this stage.
- verify both EventBridge targets, SQS worker delivery, and pick-ticket output after the HTTP contract
  checks, using identifiers resolved from stack outputs.

Minimum file expectations for this stage:
- a real `infra/` directory that exists in this stage and contains non-empty infrastructure definitions;
- a deployment guide at `deploy/aws/README.md` with exact deploy, verify, and destroy commands (no "follow docs" placeholders);
- at least one verification command that proves a preserved contract (for example `GET /inventory` or `POST /orders`) against deployed infrastructure.

Hard artifact requirements for this stage:
- `infra/template.yaml` (or equivalent IaC entrypoint) must exist and define non-empty resources;
- infrastructure outputs must include values equivalent to:
  - API base URL,
  - queue URL (and/or ARN),
  - function name,
  - database endpoint/port (when RDS is part of the stage path);
- `README.md` and `deploy/aws/README.md` must only reference files that actually exist in this stage.

Hard command/output integrity requirements:
- runnable verify commands must resolve and use real deployed outputs (for example via `aws cloudformation describe-stacks ... --query ... --output text`) rather than fixed sample URLs;
- no fake ARNs/account IDs/role names/endpoints may appear as operational defaults in runnable commands or IaC resources;
- if example placeholder values are needed, keep them only in explicitly named example files (for example `parameters.example.json`) and never in "run this now" command blocks.

Forbidden patterns in deployable artifacts for this stage (must not appear in runnable IaC/commands):
- `example.invalid`
- `example.com` used as a deployed API base URL output or runnable verification target
- hardcoded account IDs such as `123456789012`
- fixed customer role ARN literals in Lambda resources (for example `arn:aws:iam::...:role/...`); AWS-managed policy ARNs under `arn:aws:iam::aws:policy/...` are allowed
- fixed execute-api URLs used as verification targets

Required patterns in deployable artifacts for this stage:
- Lambda resources must reference IAM roles created in the same template (for example `!GetAtt <Role>.Arn`) rather than fixed role ARN strings.
- Outputs must be derived from created resources (for example `!Ref`, `!GetAtt`, or `!Sub` over resource IDs), not fabricated literal endpoint strings.
- `deploy/aws/README.md` must include concrete commands that:
  1. deploy the stack,
  2. query stack outputs (for example `ApiBaseUrl`, queue identifier, function name),
  3. assign queried values to shell variables,
  4. verify `GET /inventory` and `POST /orders` using those variables,
  5. destroy the stack.

Required minimum resource coverage in `infra/template.yaml`:
- one API entry resource (API Gateway v1 or v2),
- one Lambda function for inventory/order path,
- one IAM role for Lambda referenced by `!GetAtt ... Arn`,
- one SQS queue,
- one EventBridge bus or rule resource for event path,
- one logs/observability resource (for example CloudWatch log group),
- RDS connectivity represented either as:
  - concrete RDS resources, or
  - explicit parameters/outputs/wiring fields for an existing RDS endpoint and port.

Required output derivation rules:
- `ApiBaseUrl` must be derived from created API resource identifiers using template expressions (for example `!Sub`), not literal URLs.
- Queue/function/event outputs must come from `!Ref`/`!GetAtt` of resources defined in this stage.

Interoperability requirements with prior stages:
- reuse existing stage components/scripts where possible instead of introducing alternate names for the same behavior;
- preserve compatibility with prior contracts by including verification for both `GET /inventory` and `POST /orders` against deployed infrastructure (unless the stage explicitly scopes one out);
- ensure stage 18 deploy outputs can be consumed by later/parallel operational steps (worker, queue consumer, event publisher) without manual rewriting of identifiers.

Self-consistency and validation requirements (mandatory):
- Add tests under `tests/` that fail if:
  1. required deploy files are missing (`infra/template.yaml`, `deploy/aws/README.md`, and any referenced parameter example file),
  2. stage README references file paths that do not exist,
  3. forbidden literals appear in runnable deploy artifacts (`example.invalid`, `123456789012`, fixed customer IAM role ARN strings); tests must not reject legitimate AWS-managed policy ARNs,
  4. deploy guide omits output-resolution commands before verify commands.
- Include at least one test that inspects `infra/template.yaml` and asserts there are non-empty resources for API entry and compute and async messaging.
- Include at least one test that checks deploy guide command flow order: deploy -> resolve outputs -> verify contracts -> destroy.

Required README command concreteness:
- `deploy/aws/README.md` must include concrete command blocks, not prose-only instructions.
- Verify commands must show both:
  - `GET /inventory` against an output-resolved API base URL variable.
  - `POST /orders` against the same output-resolved API base URL variable.
- `deploy/aws/README.md` must use these exact section headings in this order:
  1. `## Deploy`
  2. `## Resolve outputs`
  3. `## Verify contracts`
  4. `## Destroy`

Deploy guide path/cwd integrity:
- State the working directory explicitly before commands (for example, "From stage root:").
- Command paths must be valid from that working directory.
- Avoid inconsistent path references (for example, if commands run from stage root, use `infra/template.yaml` and `deploy/aws/parameters.example.json` directly).

Resource-scope requirement:
- Prefer lesson-scale, low-cost resources, but still model the real assembled path (API entry, compute, persistence boundary, async queue/event boundary, IAM, and logs/observability) with concrete artifacts and commands.

If the chosen IaC/tooling is unavailable in the student environment, provide an alternative path using standard AWS CLI commands while still keeping resources and outputs explicit and inspectable.

Keep the Raspberry Pi pick-ticket worker as a supported deployment target so the physical Pi can participate in the cloud system. Minimize AWS cost and document resources students must destroy after exercises. Never commit credentials or secrets.

Update `docs/architecture.md` "Component Assembly Map" to consolidate all cloud and Linux components into one deployable system view, explicitly marking which components are core application logic versus deployment/operations infrastructure.

Update stage README with purpose, deployment artifact map, deploy/verify/test commands, explicit
teardown commands, continuity note, and a "Component assembly update" section. Placeholder README output is not acceptable.
