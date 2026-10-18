# Stage 19: Make Git tell the semester's story

Review the repository as a teaching artifact. The published course stores self-contained stage directories
in one repository revision; it does not contain one historical commit per lesson. Do not invent milestone
tags or give checkout commands for tags that do not exist, and do not rewrite history. Add
`docs/git-history.md` explaining the model and showing honest comparisons such as
`git diff --no-index ../11-orders ../12-concurrency` from a stage directory.

A student checking out an earlier milestone must see the simpler architecture that existed then. Do not rewrite the application into a final architecture shared by every historical stage.

For milestones that include AWS deployment capability, keep the corresponding deployment instructions and CloudFormation/IaC artifacts present in that milestone checkout so students can reproduce the stage behavior from that point in history.

Require `docs/architecture.md` to include a component-evolution timeline derived from the "Component Assembly Map" so students can see when each component first appeared and what it depended on.

Update stage README with purpose, milestone directory map, comparison/verification commands, student exercises,
continuity note, and a "Component assembly update" section. Placeholder README output is not acceptable.
