# Data contracts

JSON is visible at both meaningful boundaries in regeneration.

Contract stability is the continuity mechanism for this repository. Implementations may be replaced, but
contract semantics should remain compatible unless a prompt explicitly introduces contract evolution.

## Responses API request

`toolchain/regen.py` sends a JSON object shaped like this:

```json
{
  "model": "gpt-5.4-mini",
  "instructions": "course evolution rules",
  "input": "AGENTS.md plus the ordered prompt catalog",
  "text": {
    "format": {
      "type": "json_schema",
      "name": "tinywms_stage_plan",
      "strict": true,
      "schema": {}
    }
  }
}
```

The actual schema is assembled from the discovered stage names. Its `stages` array sets `minItems` and
`maxItems` to the requested stage count, so strict structured output cannot silently stop after a valid
prefix of the course. The API key is carried in the HTTP `Authorization` header, not in this JSON.

For a resumed batch, the text `input` also contains a `FROZEN BASELINE SNAPSHOT` JSON object. Its keys are
relative file paths and its values are complete file contents. It is input context only; unchanged files
must not appear in the model's output delta.

When available, resumed requests also include an `ACCUMULATED HANDOFF NOTES` section distilled from
`handoff/regen-notes.json` so contract continuity constraints remain explicit.

Print this request contract without calling the API:

```bash
python3 toolchain/regen.py --prompt-dir prompts --all --dry-run
```

## Final-reference blueprint

The preferred workflow makes its architectural oracle visible as
`reference/20-final-walkthrough/course-blueprint.json`. Its top-level contract is:

```json
{
  "schema_version": 1,
  "reference_stage": "20-final-walkthrough",
  "contracts": [],
  "components": [],
  "stages": []
}
```

Each contract records its introduction stage, visible representation, schema/example paths, producers,
consumers, and exact compatibility commands. Each component records its introduction and optional
retirement stage, kind, runtime, concrete paths, boundary contracts, and dependencies on component or
contract IDs. The `stages` array
must exactly match the prompt catalog and exhaustively classifies active components as added, reused, or
evolved. It also separates newly introduced contracts from inherited contracts and records the boundary
shift, additional required paths, and continuity commands.

During final-reference generation, the declared `introduced_stage` and `retired_after_stage` values are
the source of truth for repetitive continuity bookkeeping. The toolchain derives `added_components`, fills
`reused_components` with active components not marked as evolved, and derives introduced/inherited contract
sets before applying the strict blueprint validator. Meaningful `evolved_components` choices remain
model-authored.

Stage `required_paths` also establish path availability. A path explicitly required by an earlier stage
may be inherited before a later component formally adopts that path; it is not treated as future leakage.
Paths with neither an active component/contract nor a current-or-earlier stage requirement remain rejected.

Before forward generation, `toolchain/blueprint.py` verifies all identifiers and paths, requires every
component to be added at its declared introduction stage, requires every active component to be classified
exactly once per stage, and proves that the final reference contains every active component and contract
path. During forward generation it requires all paths available at
the current stage and rejects paths belonging only to future components. This validates architectural
meaning without requiring predecessor source code to equal the final implementation.

## Model change plan

The structured model output is:

```json
{
  "stages": [
    {
      "name": "00-establish-repository",
      "summary": "Create the empty teaching repository.",
      "files": [
        {
          "path": "README.md",
          "content": "complete file contents"
        }
      ],
      "delete_files": []
    },
    {
      "name": "01-json-backbone",
      "summary": "Define inventory JSON and add the first CLI.",
      "files": [
        {
          "path": "src/inventory.py",
          "content": "complete replacement contents"
        }
      ],
      "delete_files": []
    }
  ]
}
```

For multi-stage generation, `files` contains only changed or added files. Each `content` value is still a
complete file body, rather than a hidden diff format. `delete_files` makes removal explicit. The first
stage must provide a complete project when no baseline exists. For a resumed batch, the first requested
stage is a delta against the frozen snapshot. A standalone single-stage request must also be complete.

## Generated manifest

Every materialized snapshot includes `.regen.json`:

```json
{
  "stage": "01-json-backbone",
  "source_prompt": "01-json-backbone.md",
  "model": "gpt-5.4-mini",
  "inherits_from": "00-establish-repository",
  "summary": "Define inventory JSON and add the first CLI.",
  "changed_files": ["src/inventory.py", "README.md"],
  "deleted_files": [],
  "generated_files": ["README.md", "data/inventory.json", "src/inventory.py"]
}
```

This is both an audit record and a teaching aid. A student can inspect exactly which stage supplied a
change while still opening ordinary files in the stage directory.

Every stage snapshot also includes `handoff/regen-notes.json`, generated by the toolchain from the
materialized stage content:

```json
{
  "current_stage": "01-json-backbone",
  "notes": [
    {
      "stage": "00-establish-repository",
      "summary": "Create the empty teaching repository.",
      "inherited_contract": "",
      "boundary_change": "Introduced repository scaffold",
      "components": {
        "added": "...",
        "reused_unchanged": "...",
        "replaced_or_evolved": "..."
      },
      "continuity_checks": [
        "README file-map paths must exist in the stage snapshot.",
        "Inherited contracts remain stable unless this stage prompt explicitly changes them."
      ]
    }
  ]
}
```

The `notes` array retains one entry per completed stage. To stay within its 24 KB storage contract, the
toolchain compacts older entries to their stage name and bounded continuity summary, while the newest entry
always retains the fields required for validation and recent entries remain detailed when space permits.

## Continuity checks across stages

Use these checks when evaluating regenerated output:

1. Contract compatibility
   - Existing boundary contracts keep field names, core meanings, and expected types unless a stage
     explicitly documents a planned breaking change.
2. Explicit evolution
   - When a contract changes, the stage documents old shape, new shape, migration notes, and updated
     examples.
3. Restartability
   - Stage documentation explains how to resume from this checkpoint after failure or pause.
4. Proof by runnable checks
   - At least one command or test demonstrates that boundary behavior still matches the documented
     contract.
