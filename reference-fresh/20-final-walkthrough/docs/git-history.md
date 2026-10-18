# TinyWMS git history guide

TinyWMS uses a teaching repository history that is meant to be read alongside the source tree, not as if each lesson lived in a separate long-lived branch. In this published repository, stage directories and lesson artifacts coexist in one revision so students can inspect the current checkpoint while still seeing the earlier materials that remain part of the course.

## How to compare stages honestly
Use `git diff --no-index` when you want to compare two lesson artifacts or two stage directories that both exist in the same checkout. That keeps the comparison grounded in real files that are already present in the repository.

Examples:

```bash
git diff --no-index docs/architecture.md docs/end-to-end.md
```

```bash
git diff --no-index deploy/pick-ticket-worker/README.md deploy/container-worker/README.md
```

## What not to invent
Do not invent stage tags that do not exist in the repository history. The lesson materials already name the published stages and the corresponding files that are currently present. If you want to study a prior checkpoint, use the actual repository history and the files that exist in this checkout.

## Why this matters in the course
The course compares real files, real commands, and real outputs:
- stage guides live in the repository together
- stage-specific files remain available for comparison
- history comparisons should use actual paths and actual diffs
- the checkout you have is the teaching artifact

This keeps the history lesson honest and avoids implying that students must rely on imaginary tags or unpublished stage names.
