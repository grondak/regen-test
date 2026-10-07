# regen-test

This repository stores the prompts, not the generated implementation code.

The workflow is intentionally simple:
- keep the prompt specification in version control
- regenerate the implementation on demand
- validate the generated result with tests that are part of the prompt contract

## Current prompt

The first prompt is `prompts/hello-world.md`.

It describes a tiny Python app that prints `Hello, World!` and includes a corresponding test.

## Toolchain

Generate the app from the prompt:

```bash
python3 toolchain/regen.py prompts/hello-world.md --output generated/hello-world
```

Run the generated test suite:

```bash
python3 -m pytest generated/hello-world/test_app.py -q
```

Generated output is intentionally not committed to source control.
