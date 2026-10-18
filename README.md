# TinyWMS prompt-driven course

This repository stores an ordered set of teaching prompts. The regeneration tool sends the entire
course outline to an LLM, asks for the requested stage or stages, and writes inspectable source files
under `generated/`.

## Core teaching thesis

TinyWMS is contract-first. Stable contracts are what make the system rebuildable, resumable, and safe to
re-implement with a different technology.

The main learning goal is continuity of behavior across changing implementations. A stage can switch
runtime, hosting model, or language, but it should preserve explicit data contracts unless the lesson
explicitly teaches a contract evolution.

Non-goal: preserving one "perfect" long-lived implementation through maintenance-only updates.
Goal: preserving the contract while rebuilding implementations in visible, testable steps.

The important unit is a progression, not 21 unrelated code-generation contests. The preferred workflow
first generates a separate final-system reference and a visible JSON course blueprint, then generates
the actual lessons forward from Stage 0. The final reference supplies stable contracts and component
destinations; it is not copied backward into simpler lessons. Each accepted stage becomes the frozen
baseline for the next stage, while complete snapshots remain easy for students to compare.

## Cross-stage interoperability expectation

Treat the course as cumulative assembly.

If stage `m` introduces a working feature or artifact, stage `m+n` should reuse
as much of it as practical and only change what integration requires. Later
stages should prefer extension over replacement and should keep earlier
contracts demonstrably runnable unless contract evolution is explicitly the
lesson goal.

When reviewing generated stages, reject outputs that:
- re-implement prior features without clear need;
- drop earlier runnable behavior without migration notes;
- change contract behavior without calling it out as the lesson objective.

## Requirements

- Python 3.10 or newer
- an OpenAI API key with access to the configured model
- network access to the OpenAI Responses API

No Python packages are required. The tool uses the standard library so the HTTP and JSON boundaries
remain visible.

Set the API key in your shell. Do not put it in this repository:

In zsh, read it without placing the value in shell history:

```bash
read -s "OPENAI_API_KEY?OpenAI API key: "; echo
export OPENAI_API_KEY
```

The default model is `gpt-5.4-mini`. Override it with `OPENAI_MODEL` or `--model`:

```bash
export OPENAI_MODEL="gpt-5.4-mini"
```

API use incurs normal model charges. The final-first workflow uses one request for the reference and then
one or more requests per generated stage. The older `--all` workflow remains available for comparison and
uses one initial request, plus bounded repair requests when validation fails. Delete generated files
locally when finished; this does not delete any cloud resource or API usage record.

The standard-library HTTP client automatically retries transient connection failures and HTTP 408, 409,
429, and 5xx responses up to two times using `Retry-After` or short exponential backoff. It does not retry
authentication, billing, credit, or spend-limit failures.

Validation retries receive both the exact validator error and the rejected structured stage plan. This lets
the model edit a dangling blueprint ID or defective file directly instead of blindly recreating the same
invalid candidate.

## Generate the course final-first

First generate a standalone final system in a separate, ignored reference directory:

```bash
python3 toolchain/regen.py --prompt-dir prompts \
  --build-reference \
  --reference-output reference/20-final-walkthrough \
  --validation-retries 2
```

The reference is accepted only when it contains a valid `course-blueprint.json` whose components,
contracts, stage names, dependencies, concrete paths, and continuity checks are internally consistent;
whose final paths exist; and whose cumulative behaviors are present. The behavior audit checks the real
RDS query, transactional order writes and rollback, concurrent inventory guard, SQS command,
EventBridge event, and packaged Lambda deployment rather than accepting path-only placeholders. It also
requires the integrated inventory/order browser, local HTTP order proof, real SQS receive/delete behavior,
two observable EventBridge targets, a long-running idempotent pick-ticket worker, a local callback
integration proof, and source/IaC/package wiring agreement. Review
the reference and run its documented local tests before using it as the architectural oracle.

The model declares component and contract lifetimes plus meaningful `evolved_components` choices. Before
validation, the toolchain deterministically derives each stage’s added and reused component sets and its
introduced and inherited contract sets. This removes repetitive 21-stage bookkeeping without weakening
the component, contract, path, dependency, or continuity validators.

When the Stage 19 seed is missing cumulative final behavior, reference construction repairs it through
focused model passes before requesting the final blueprint and walkthrough. The concerns are the
integrated browser/local HTTP path, database transactions and concurrency, database-derived SQS commands
and acknowledgement, EventBridge fan-out, worker lifecycle/idempotency, the executable callback proof,
consolidated deployment wiring, and the final truthful walkthrough. Each pass receives only its relevant
files, may change only an explicit path allowlist, and must pass its concern-specific audit before the next
pass begins. This prevents a broad retry from dropping fixes made by an earlier candidate.

If `generated/19-git-history/.regen.json` exists, reference generation borrows that verified file snapshot
as a read-only frozen seed and asks only for the Stage 20/reference delta. This preserves the semester’s
earlier runnable components and avoids recreating the entire course in one response. Use
`--reference-seed-root <path>` when the checkpoint chain is under another output root. The seed stage is
never modified. If the final-stage validators detect a defect in an inherited deployment file, the request
lists all detected defects together and requires corrected replacement content in the Stage 20 delta. For
the small set of mechanically unambiguous inherited defects audited by the toolchain—such as an inline
Lambda handler mismatch or empty RDS deployment parameters—the builder also applies a deterministic repair
overlay to the Stage 20 plan. These files are recorded as Stage 20 changes; Stage 19 remains untouched.

Then generate the student course forward into a fresh output root:

```bash
python3 toolchain/regen.py --prompt-dir prompts \
  --forward-all \
  --reference-output reference/20-final-walkthrough \
  --output generated-forward \
  --validation-retries 2
```

Forward generation makes one stage request at a time. Each request receives the previous frozen snapshot,
the relevant blueprint slice, and mature reference implementations for components introduced or evolved
in that lesson. Those excerpts are evidence to adapt, not permission to leak later behavior backward.
The validator requires current component and contract paths, rejects paths reserved for future lessons,
checks cumulative runtime behavior, and rejects tests coupled to obsolete root READMEs. If an older
manifest predates stronger validation, generation resumes from the latest checkpoint that still passes
the current contract and regenerates only the invalid suffix.

The blueprint is generator planning metadata. It remains in `reference/` and is not copied into student
stage snapshots or the published course.

### Legacy one-request generation

The original full-plan workflow remains available for side-by-side evaluation:

```bash
python3 toolchain/regen.py --prompt-dir prompts --output generated --all
```

Generate an early cumulative slice of the course with the same inheritance behavior:

```bash
python3 toolchain/regen.py --prompt-dir prompts --output generated \
  --through 01-json-backbone
```

### Resume in reviewable batches

After reviewing a batch, freeze it and generate only the next batch:

```bash
# Existing generated stages: 00 and 01
python3 toolchain/regen.py --prompt-dir prompts --output generated \
  --resume-through 03-pi-http-server

# After reviewing Stages 02 and 03, continue without regenerating 00-03
python3 toolchain/regen.py --prompt-dir prompts --output generated \
  --resume-through 07-api-gateway
```

Resume mode finds the latest valid contiguous `.regen.json` manifest, loads that stage's complete file
snapshot as a frozen baseline, and asks the model only for subsequent deltas. The baseline is included so
the model understands the current application, not so it can rewrite it. The request says explicitly:
“I'm only using this to avoid regeneration of perfectly good code.”

If any file recorded in the baseline manifest is missing, or the manifest names the wrong stage or source
prompt, generation stops instead of silently reconstructing the earlier work.

For the legacy one-request and batch modes, the tool:

1. discovers the ordered `*.md` course prompts;
2. includes `AGENTS.md` and every course prompt in one model request;
3. requests strict JSON describing an ordered sequence of file deltas;
4. validates stage names and prevents absolute paths or `..` traversal;
5. applies the deltas in memory and writes a complete directory for every stage.

Each stage also receives `.regen.json`. This manifest makes the transition visible: it records the model,
source prompt, inherited stage, changed files, deleted files, and complete generated file list.

Each stage also receives `handoff/regen-notes.json`. The toolchain writes this automatically by extracting
continuity and component-assembly signals from the materialized stage. Notes accumulate stage by stage and
a compact recent window is injected into resume requests as explicit continuity context. When stored notes
approach the 24 KB budget, older entries are reduced to stage identity and continuity summaries while recent
entries remain detailed; no stage is dropped from the history.

## Publish the generated course repository

After the complete course has been generated, reviewed, and tested, publish the stage snapshots to the
sibling `tinywms-course` repository:

```bash
python3 toolchain/publish_generated.py --dry-run
python3 toolchain/publish_generated.py
```

The publisher requires every prompt-defined stage and a valid contiguous `.regen.json` checkpoint chain.
It refuses to write when the sibling Git repository contains uncommitted or untracked changes, preventing
an export from silently overwriting unrelated work.

The published repository receives its own course-facing `README.md` and `.gitignore`. Prompt files,
toolchain code, Python caches, and `.regen.json` generator metadata are not copied. The publisher updates
only the stage directories and those two managed root files; unrelated clean root files such as a license
remain in place.

Publication never commits, pushes, configures a remote, or deploys AWS resources. Review and commit the
sibling repository separately.

Inspect or save the exact API request without using the network or spending tokens:

```bash
python3 toolchain/regen.py --prompt-dir prompts --all --dry-run > request.json
```

Preview the final-reference request, including the blueprint contract:

```bash
python3 toolchain/regen.py --prompt-dir prompts --build-reference --dry-run > reference-request.json
```

The same preview works for a resumed batch and includes the frozen baseline:

```bash
python3 toolchain/regen.py --prompt-dir prompts --output generated \
  --resume-through 03-pi-http-server --dry-run > request.json
```

The preview contains the instructions, course context, model name, and response schema. It never contains
`OPENAI_API_KEY`, because that credential is sent separately in an HTTP header during a live request.

## Generate one stage

A single stage still sees the entire course catalog, but it is requested as a complete standalone
snapshot because there is no preceding generated state to inherit:

```bash
python3 toolchain/regen.py prompts/08-relational-persistence.md \
  --prompt-dir prompts \
  --output generated/08-relational-persistence
```

## Course prompts

- `00-establish-repository.md`: empty teaching-repository structure
- `01-json-backbone.md`: inventory JSON contracts and CLI
- `02-linux-visible.md`: stdin, stdout, stderr, processes, and files
- `03-pi-http-server.md`: transparent Python inventory HTTP service
- `04-browser.md`: plain browser inventory client
- `05-ec2-deployment.md`: unchanged application deployed to EC2
- `06-lambda.md`: parallel Lambda execution path
- `07-api-gateway.md`: HTTP routing to Lambda
- `08-relational-persistence.md`: observable Linux relational database
- `09-rds.md`: the same database moved to managed RDS
- `10-lambda-rds.md`: Lambda reads inventory from RDS
- `11-orders.md`: transactional order placement
- `12-concurrency.md`: race condition and overselling prevention
- `13-sqs.md`: asynchronous pick-work command
- `14-domain-events.md`: versioned `OrderPlaced` event and consumers
- `15-pick-ticket-worker.md`: long-running Linux worker
- `16-callback-demo.md`: complete browser-to-Pi teaching demonstration
- `17-container-worker.md`: containerize only the worker
- `18-aws-deployment.md`: reproducible, inexpensive cloud infrastructure
- `19-git-history.md`: semester milestones and architectural history
- `20-final-walkthrough.md`: end-to-end architecture documentation

### Prompt authoring requirement for lesson READMEs

Every stage prompt is expected to produce a student-usable stage `README.md`, not placeholder text.
During review, reject generated stage READMEs that only identify the source prompt without executable
lesson guidance.

Minimum required README content for runnable stages:

1. stage purpose;
2. key file map;
3. run commands;
4. test commands;
5. student exercises;
6. cleanup notes when applicable;
7. continuity note (inherited contract and changed boundary);
8. component assembly update (what components were added, reused unchanged, or replaced/evolved).

Use this heading order for consistency across stages:

`Stage purpose` → `Files in this lesson` → `Run the lesson` → `Run tests` →
`Student exercises` → `Continuity note` → `Component assembly update` → `Cleanup`

### Prompt authoring requirement for deploy/ops artifacts

Do not accept placeholder deploy/ops artifacts in runnable stages.

Reject outputs such as:
- empty IaC templates (for example `Resources: {}`)
- deploy guidance that omits exact commands
- verify/cleanup sections that do not identify concrete resources

Deployment-oriented stages must provide concrete, inspectable artifacts:
1. non-empty templates defining resources used in the lesson;
2. outputs/identifiers students can use in later stages;
3. exact deploy, verify, and teardown commands consistent with repository files;
4. at least one continuity proof command showing preserved contracts.

## Tests

The toolchain tests use fake model responses and temporary Git repositories and never call the network:

```bash
python3 -m unittest discover -s toolchain -p 'test_*.py' -v
```

Generated application tests are stage-specific. Read each generated stage's `README.md` for its run and
test commands.

When reviewing a generated stage, verify continuity first:

1. Which prior contract(s) are preserved?
2. Which boundary changed in this stage?
3. How can a student restart from this checkpoint after a failure or pause?
4. Which test or command proves compatibility at this boundary?

Then verify component assembly clarity:

5. Which components were introduced, reused unchanged, or replaced in this stage?
6. Are component dependencies and JSON contracts explicit and consistent with prior stages?

Then verify deploy/ops quality when applicable:

7. Are IaC templates non-empty and aligned with the stage purpose?
8. Do deploy/verify/cleanup commands reference real resources and runnable files?
9. Can a student identify the exact resource outputs needed by later stages?

Then verify cross-stage interoperability:

10. Which concrete prior components/features were reused unchanged in this stage?
11. What integration-only changes were made, and were they minimal?
12. Which command/test in this stage proves reused features still work?

See [the architecture notes](docs/architecture.md) and [the JSON contracts](docs/data-contracts.md) for
the details of the request, response, inheritance, failure behavior, and operator responsibilities.
