# Architecture

This repository optimizes for contract continuity across implementation changes. A stage may replace how
the system runs, but should keep boundary behavior inspectable and stable unless the lesson explicitly
teaches contract evolution.

## Components and locations

| Component | Runs in | Data |
| --- | --- | --- |
| `prompts/*.md` | nowhere; source input | ordered lesson requirements in Markdown |
| `AGENTS.md` | nowhere; source input | course-wide teaching constraints in Markdown |
| `toolchain/regen.py` | the operator's local Python process | prompt text, JSON request, JSON response, in-memory snapshots |
| `toolchain/blueprint.py` | the operator's local Python process | blueprint validation and stage-specific context slices |
| OpenAI Responses API | OpenAI-managed infrastructure | the supplied course context and generated change plan |
| `reference/20-final-walkthrough/` | the local filesystem | standalone final-system reference plus `course-blueprint.json` |
| `generated/<stage>/` | the local filesystem | complete source snapshot plus `.regen.json` and `handoff/regen-notes.json` |

The toolchain uses Python's `urllib.request` directly. There is no SDK or framework hiding the HTTP
request. `OPENAI_API_KEY` is read from the process environment and sent as a bearer token. It is never
written to generated output. `--dry-run` prints the request JSON without making a network call.

## Preferred final-first, forward-build workflow

```text
all prompts + AGENTS.md
          |
          v
standalone Stage 20 reference + course-blueprint.json
          |
          v
validate component IDs, contracts, paths, stages, and final completeness
          |
          v
Stage 00 --frozen snapshot--> Stage 01 --...--> Stage 20
   |                              |
   + reject future paths          + require inherited contracts/components
```

The final reference is an executable architectural specification, not a source tree to subtract from.
`course-blueprint.json` identifies when components and contracts first appear and which concrete paths and
compatibility checks belong to each lesson. Forward generation injects only the relevant blueprint slice,
uses the preceding accepted snapshot as the baseline, and rejects component paths introduced by later
lessons. The reference blueprint never enters ordinary stage snapshots.

Component and contract lifetime declarations are authoritative. Reference generation derives the
repetitive per-stage added/reused and introduced/inherited sets from those lifetimes, while preserving
valid model-authored evolved-component choices. The strict validator then checks the normalized blueprint.
Path availability is cumulative as well: an earlier stage requirement establishes a path for later stages,
even when a later component eventually takes ownership of that shared file.

When a valid Stage 19 manifest is available under the configured reference seed root, the reference build
borrows that exact snapshot and generates Stage 20 as a delta. This follows the normal stage-borrowing
workflow, preserves all earlier comparison artifacts, and leaves the seed checkpoint byte-for-byte
unchanged. "Frozen" protects the checkpoint directory; it does not require Stage 20 to perpetuate a broken
inherited artifact. Known deployment audit defects are collected before generation and supplied together
as mandatory Stage 20 repairs. A narrow deterministic overlay repairs mechanically unambiguous inline
Lambda handler and RDS parameter defects if the model leaves them behind. The overlay is applied to the
Stage 20 delta and therefore appears in its manifest; it never writes into Stage 19. Without a seed,
reference generation falls back to a complete standalone Stage 20 snapshot.

Behavior repair is split by component boundary. Browser/HTTP integration, database transactions, SQS
commands and acknowledgement, EventBridge fan-out, worker lifecycle/idempotency, callback integration,
and deployment wiring each have an explicit file allowlist and concern-specific validator. Accepted
repair overlays accumulate in order, so a later retry cannot silently discard an earlier component fix.
The complete cumulative validator still runs before the reference becomes the forward-generation oracle.

An existing forward checkpoint is validated against the blueprint before it can be reused. If it is
incompatible, generation stops rather than rewriting the accepted stage. Operators should review that
checkpoint or choose a fresh output root deliberately.

## Legacy full-course generation

```text
all prompts + AGENTS.md
          |
          v
one Responses API request ----failure----> stop without writing a stage
          |
          v
strict JSON stage deltas
          |
          v
validate names and paths ------failure----> stop without writing a stage
          |
          v
apply each delta to the prior in-memory snapshot
          |
          v
generated/00-...  generated/01-...  ...  generated/20-...
```

The legacy `--all` course is planned in one initial request. The model sees what came before and what
comes later, and its structured output represents only the transition at each stage. This reduces
repeated generation and prevents a later technology from appearing early merely because it would make
one isolated prompt easier to satisfy.

The filesystem output remains a set of complete snapshots. That small amount of local duplication is
intentional: students can run a stage on its own and compare adjacent stages without learning a patch
format first.

## Rebuildability and replacement

The course models "small-team rebuildability" by preserving visible contracts while changing internals.
For example, a team can replace one stage's Python implementation with a Go implementation in a later
stage if request/response shape, semantics, and operational instructions remain explicit and testable.

Continuity target: swap implementation, keep boundary promises.

## Single-stage generation

A single target is shown alongside every other course prompt, but the response must contain a complete
snapshot. It does not inherit whatever happens to be in `generated/`; that keeps regeneration independent
of stale local output.

## Resumable batches

`--resume-through` treats the latest contiguous generated stage as a frozen checkpoint. The tool validates
that stage's `.regen.json`, reads only the files listed there, and places their complete contents in the
next model request. The first requested delta inherits that snapshot; later deltas inherit one another.

```text
validated Stage 03 snapshot
          |
          v
one request for Stages 04-07 only
          |
          v
generated/04-... through generated/07-...
```

Previously generated directories are neither sent back as requested output nor rewritten. Batches are a
context and output-size control, not an invitation to search for a luckier version of accepted code.

## Failure behavior

- Missing prompts, API credentials, or network access produce visible errors.
- Temporary connection failures and HTTP 408, 409, 429, and 5xx responses receive up to two bounded
  retries with `Retry-After` or short exponential backoff. Billing/quota 429 responses are not retried.
- Final HTTP errors include the API response body.
- Refusals and missing response text are reported explicitly.
- Incomplete API responses report their reason and direct the operator to checkpoint batching.
- Invalid JSON, wrong stage ordering, duplicate writes, and unsafe paths stop generation.
- Model output cannot use absolute paths, `..`, backslashes, or overwrite `.regen.json`.
- Resume stops if a checkpoint manifest is invalid or any recorded baseline file is missing.
- Validation failures are retried with a bounded loop that appends the exact previous error to the next
  request together with the rejected structured plan, allowing the model to edit the failed candidate
  instead of recreating it without seeing its mistake. When a materialized stage fails, the valid generated prefix becomes an in-memory frozen
  checkpoint and only the failing stage plus its successors are requested again. Retry count is controlled
  by `--validation-retries`.

The tool validates the complete plan before writing any stage. Files from a previous model-authored
manifest that disappear from a regenerated snapshot are removed; unrelated untracked files are left
alone.

After each stage is materialized, the toolchain emits `handoff/regen-notes.json` and validates it. This
file accumulates continuity notes across stages so resumed batches carry forward explicit inherited
contracts and component-evolution cues. Storage compaction retains every stage name plus short historical
continuity summaries, while keeping as many recent full-detail entries as fit within the 24 KB limit.

## Operations, cost, and cleanup

The person running `regen.py` operates the local generator and is responsible for the selected model,
API account, generated source review, and any later deployment. OpenAI operates the model endpoint.

Every live generation uses paid API tokens. `--all` uses one request. No AWS resources are created by the
toolchain itself, even when a lesson asks the model to produce AWS examples. `--build-reference` uses one
initial request and `--forward-all` uses one initial request per missing stage; validation retries add
requests only for the failing target. A generated stage that adds
cloud resources must document its own costs and destruction steps before students use it.

Local cleanup is simply removal of the ignored `generated/` directory. It is safe to regenerate because
source prompts remain in version control.
