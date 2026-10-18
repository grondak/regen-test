# Stage 0: Establish the repository

Create a teaching repository named `tinywms`.

This is a semester-long warehouse-management teaching application for students learning Linux, Python, JSON, HTTP, AWS, SQL, distributed systems, events, and containers. JSON is the application's canonical interchange format. Use Python wherever server-side code is needed and plain HTML/CSS/JavaScript for the browser. Optimize for readability and teachability, not production sophistication. Do not introduce frameworks, abstractions, AWS services, databases, containers, queues, or infrastructure until explicitly requested.

Create `README.md`, `docs/`, `data/`, `src/`, and `tests/` directories, but do not implement the application yet. Create `docs/architecture.md` containing only the current empty architecture, a section titled "Architecture History," and a section titled "Component Assembly Map." The Component Assembly Map should start as an empty table that future stages fill in with: component name, stage introduced, runtime location, inbound contract, outbound contract, and dependencies. Create `docs/data-contracts.md`. Every future architectural change must update these documents.

Stage-0 README exception:
- Stage 0 is a repository-establishment stage and may use a setup-oriented README instead of the full runnable-stage template.
- It should still clearly state that no runnable application exists yet and what later stages will add.

Also define the stage README expectation for future stages: each runnable stage README must be a
lesson guide with purpose, file map, run/test commands, exercises, cleanup notes (when needed), and a
continuity note. Future stage READMEs must also include a short "Component assembly update" that states which components were added, reused unchanged, or replaced in that stage. Placeholder "generated app from ..." README text is not acceptable.

Global constraints for every later stage (apply cumulatively):
- Reuse-first: if an earlier stage introduced a working component or script, later stages must reuse it unless integration changes are required by the new lesson objective.
- Integration-only changes: when modifying prior components, keep deltas minimal and explain what changed and why.
- No silent capability drops: do not remove prior runnable behavior without an explicit compatibility path or migration note in the same stage README.
- No placeholder artifacts: do not emit empty infrastructure/templates, fake file maps, or command blocks that reference missing files.
- No fabricated runtime values: do not hardcode fake AWS account IDs, ARNs, execute-api URLs, queue URLs, database endpoints, or role names as if they were runnable outputs.
- Forbidden deploy-value literals in runnable artifacts: reject `example.invalid`, reject literal account IDs like `123456789012`, and reject fixed customer IAM role ARN strings in place of generated resource references. AWS-managed policy ARNs such as `arn:aws:iam::aws:policy/...` are valid and must not be rejected by an over-broad test.
- Forbidden deploy-value literals in runnable artifacts also include `example.com` when used as a live API or service endpoint.
- Runtime-value integrity: deploy/verify commands must obtain dynamic values from actual outputs (for example stack outputs, CLI queries, or generated files) rather than fixed example endpoints.
- File-map integrity: every file path listed in a stage README must exist in that stage directory.
- Continuity proof: each stage must include at least one command or test that demonstrates previously established behavior still works.
- Validation-first for deployment lessons: stages that introduce deploy/infrastructure artifacts must also include tests that assert artifact presence, basic consistency, and no forbidden placeholder runtime literals in runnable command paths.

README format strictness (apply to every runnable stage):
- Use this exact title format: `# TinyWMS lesson: <stage-name>`.
- Use these exact headings (same wording and order):
  1. `## Stage purpose`
  2. `## Files in this lesson`
  3. `## Run the lesson`
  4. `## Run tests`
  5. `## Student exercises`
  6. `## Continuity note`
  7. `## Component assembly update`
  8. `## Cleanup`
- Do not rename headings (for example, do not replace `Stage purpose` with `Repository purpose`).
- In `Files in this lesson`, every listed path must exist in that stage snapshot and use normalized relative paths (no doubled slashes like `..//`).
- `Files in this lesson` must list committed repository files/directories only. Do not list runtime-generated artifacts (for example `pick-tickets.txt`, temporary logs, or other outputs created while running commands) unless the stage intentionally commits that artifact file.
- Generated-snapshot consistency rule: a stage README may only list files that are actually generated in that same stage directory snapshot.
- No implied build-artifact listing: do not list build outputs (for example zip archives) in `Files in this lesson` unless the stage explicitly creates and commits those files.
- Deploy path normalization rule: only reference deploy subfolders that exist in that stage; do not invent new deploy paths unless they are also created in that stage.
- Preflight self-check rule: before finalizing a stage output, cross-check each `Files in this lesson` path against the generated stage file tree and remove/rename any non-existent references.
- Test commands in stage READMEs should prefer Python standard-library runners unless the stage explicitly introduces another test tool. When tests import modules directly from `src/`, use the visible command `PYTHONPATH=src python3 -m unittest discover -s tests -v`; otherwise default to `python3 -m unittest discover -s tests -v`.
- Tests inherited by later stages must assert stable component behavior, contracts, or lesson-specific guides. Do not make a persistent component test read the root `README.md` and assert the title, file map, or commands of the stage where that test originated, because the root README is intentionally rewritten by every later lesson.
- Every test must pass under the exact command printed in the stage README. Import `unittest.mock` explicitly when using it; do not rely on it being exposed as an attribute of `unittest`.

Mandatory borrowing pass for every stage after stage 0:
- Before generating stage `N`, review stage `N-1` (and earlier relevant stages) and create a borrowing inventory of concrete reusable artifacts (files, scripts, contracts, tests, deployment docs, and component names).
- For each borrowed artifact, classify it as one of:
  1. reused unchanged,
  2. reused with minimal integration edits,
  3. intentionally replaced/evolved.
- Prefer borrowing over renaming. Keep existing filenames and component names unless renaming is necessary for the lesson objective.
- If renaming/replacement is necessary, include both old and new paths in documentation and explain compatibility/migration in the same stage.
- Stage README `Component assembly update` must cite concrete borrowed paths (not generic prose) to prove reuse decisions.
