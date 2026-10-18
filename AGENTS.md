# TinyWMS Teaching Repository

TinyWMS is a teaching system, not a production WMS.

The repository evolves during a semester as students learn computing concepts.
Do not prematurely introduce technologies or architectural patterns that belong
to later lessons.

## Primary design rule

Prefer the implementation that most clearly exposes the concept currently being
taught over the implementation that would be preferred in a production system.

## JSON rule

JSON is the canonical interchange format between components.

Whenever data crosses a meaningful boundary, make its JSON representation easy
for a student to see, print, save, inspect, curl, or discuss.

Do not hide JSON behind unnecessary framework abstractions.

## Contract-first continuity rule

Treat stable contracts as the primary mechanism for continuity.

A stage may replace implementation details (runtime, platform, storage engine, framework, or language)
when the lesson calls for it, but should preserve contract meaning at existing boundaries unless contract
evolution is itself the lesson objective.

Contract stability is what enables:
- restarting after failures
- resuming after pauses
- side-by-side comparison of old and new implementations
- reimplementation without hidden coupling to prior internals

## Evolution rule

Preserve the conceptual history of the system.

When adding a new implementation, do not automatically delete the old one.
Students should be able to compare:

Raspberry Pi Linux
-> EC2 Linux
-> Lambda

and:

JSON file
-> Linux database
-> RDS

and:

synchronous request
-> queue
-> event-driven processing.

## Component assembly rule

Teach TinyWMS as an assembled system of explicit components across stages, not
as isolated per-stage rewrites.

Maintain `docs/architecture.md` with a "Component Assembly Map" that records,
for each component:
- component name
- stage introduced
- runtime location
- inbound contract
- outbound contract
- dependencies

Each stage should clearly identify whether a component is:
- added
- reused unchanged
- replaced/evolved

When the runtime or infrastructure changes, preserve and document component
relationships and contract continuity.

## Cross-stage interoperability rule

Stages must interoperate by default.

If stage `m` introduces a working component, contract, script, or deployment
artifact, then stage `m+n` should reuse it unchanged whenever possible.
Integration updates are allowed, but unnecessary rewrites, silent replacement,
or dropped capabilities are not.

For each stage, explicitly identify:
- what was reused verbatim from earlier stages;
- what required integration changes and why;
- what was intentionally replaced/evolved and how compatibility is preserved.

Treat this as a cumulative build:
- each stage should inherit as much runnable behavior as practical;
- newer stages should remain able to demonstrate earlier contracts unless
  contract evolution is the lesson objective;
- if a prior artifact is superseded, keep a visible compatibility path or
  clearly documented migration in the same stage.

## Stage borrowing workflow (required)

For every stage after the repository-establishment stage:

1. Review prior stage artifacts first (at least stage `N-1`, plus older stages
   when relevant).
2. Build a borrowing inventory of concrete files/components to carry forward.
3. Mark each item as:
   - reused unchanged
   - reused with minimal integration edits
   - intentionally replaced/evolved
4. Prefer reusing existing names/paths over introducing new names for the same
   role.
5. If renaming/replacement is required, document old/new path mapping and the
   compatibility or migration note in that same stage.

The stage README should provide concrete borrowed paths in the component update,
not only high-level statements.

## Regeneration rule

Treat the latest contiguous generated stage with a valid `.regen.json` manifest
as a frozen checkpoint. When extending the course, use that checkpoint as input
and generate only the later stage deltas.

Do not regenerate or modify accepted earlier stages merely to seek a better
output. Regenerate an earlier stage only when explicitly requested. Resumable
batching exists to avoid regeneration of perfectly good code.

## Generated-repository publication rule

After a complete prompt-defined course build succeeds and its safe local tests
pass, publish it with:

```bash
python3 toolchain/publish_generated.py
```

Use this script instead of manually copying `generated/`. It validates the full
contiguous `.regen.json` checkpoint chain, installs the generated-repository
README and `.gitignore`, and excludes prompts, toolchain files, bytecode caches,
and generator-only manifests from the sibling course repository.

The sibling repository must have a clean Git worktree before publication. If
the publisher reports changes there, stop so they can be reviewed, committed,
stashed, or removed deliberately; do not bypass the clean-tree protection.

Publication does not authorize committing, pushing, configuring a remote, or
deploying AWS resources. Those actions require their own explicit request.

## Complexity rule

This course teaches systems, not framework mastery.

Prefer:
- Python standard library where reasonable
- small, obvious dependencies
- plain HTML
- plain JavaScript
- explicit SQL
- explicit JSON
- visible environment variables
- visible HTTP requests/responses
- readable AWS configuration

Avoid unless explicitly requested:
- frontend frameworks
- ORMs
- dependency-injection frameworks
- elaborate Python architecture
- unnecessary class hierarchies
- Kubernetes
- abstraction layers that conceal SQL, HTTP, JSON, Linux processes, or AWS behavior

## Teaching visibility

Students should be able to answer:

1. Where is this code running?
2. Where is its data?
3. How did the data get here?
4. In what representation is the data?
5. What happens if this component fails?
6. Who is responsible for operating this component?

Keep those answers visible in code and documentation.

## Stage continuity checklist

When creating or reviewing a stage, document all four:

1. Inherited contracts: which prior interfaces remain valid?
2. Boundary shift: what changed (process, host, protocol, storage, trigger)?
3. Failure/restart path: how does a student recover or resume from this checkpoint?
4. Continuity proof: what command, test, or script demonstrates compatibility?

Also verify interoperability:

5. Reuse proof: which concrete files/components from earlier stages are reused unchanged?
6. Integration delta: what minimal changes were made to connect reused components?
7. Compatibility proof: which command/test shows the reused feature still works in this stage?

## Stage README contract (required output quality)

For every runnable stage, the stage `README.md` must be a teaching guide, not placeholder text.

Do not emit generic boilerplate such as "Generated app from ...". Replace it with lesson-specific
instructions that a student can execute immediately.

Each runnable stage README must include:

1. Stage purpose in 1-3 sentences.
2. File map: what key files are and why they matter in this stage.
3. Exact run commands from the stage directory.
4. Exact test commands.
5. At least two student exercises that modify code and observe the result through the lesson's visible
   interface; tests may be offered as an optional follow-up check.
6. Cleanup notes when files/processes/resources are created.
7. Contract continuity note: what contract is inherited and what boundary changed.
8. Component assembly update: which components were added, reused, or replaced in this stage.

When `tests/test_web_app.js` is present, the exact test commands must also include:

```bash
node --test tests/test_web_app.js
```

Use this canonical structure:

~~~md
# TinyWMS lesson: <stage-name>

## Stage purpose
<1-3 sentence lesson objective and scope>

## Files in this lesson
- `<path>` - <what it does in this stage>
- `<path>` - <what it does in this stage>

## Run the lesson
From this folder:
```bash
<exact command(s)>
```

## Run tests
```bash
<exact test command(s)>
```

## Student exercises
1. <small code change exercise>
2. <small behavior/test exercise>

## Continuity note
- Inherited contract: <what remains compatible>
- Boundary changed in this stage: <what changed>

## Component assembly update
- Added: <new components introduced in this stage>
- Reused unchanged: <components carried forward unchanged>
- Replaced/evolved: <components whose internals or hosting changed>

## Cleanup
<commands or "No external resources are created in this stage.">
~~~

## Student exercise rule

Student exercises must lead with observable system behavior rather than the test suite. Ask students to
change or build something and then see it work through the CLI, JSON output, SQL query, browser, `curl`,
service log, queue message, container output, or `tail -f` as appropriate to the lesson. Tests remain a
required repository safety net and must retain an exact command under `Run tests`, but exercises should
describe them only as an optional follow-up check.

## Repository quality

Every stage must:
- contain useful README instructions
- avoid committed credentials and secrets
- expose useful errors
- use inexpensive AWS resources where practical
- document AWS resources that incur cost
- explain cleanup/destruction
- remain understandable to students encountering the technology for the first time
- avoid placeholder artifacts that look complete but are not operationally useful

## No-placeholder artifact rule

Do not emit placeholder infrastructure or operations artifacts in runnable
stages.

Examples to avoid:
- empty IaC templates such as `Resources: {}`
- README instructions that only say "follow docs" without concrete commands
- stub deploy/verify/teardown scripts that omit real resource names or checks

When a stage introduces deployment or operations content, require concrete and
inspectable artifacts:
- non-empty templates that declare the resources needed for the lesson
- explicit outputs/identifiers students use in later stages
- exact deploy/verify/cleanup commands that match the files in the stage
- at least one continuity check proving earlier contracts still work

Every stage containing runnable code must run and include appropriate tests.
Repository-establishment stages may intentionally contain no application code.

Generating AWS deployment artifacts does not authorize creating or changing AWS
resources. Live deployment and cloud integration tests require an explicit
request.

When changing architecture, update:
- README.md
- docs/architecture.md
- docs/data-contracts.md
- relevant deployment instructions

Do not make unrelated architectural improvements.
