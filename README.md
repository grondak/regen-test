# regen-test

This repository stores prompt definitions rather than generated implementation code.

The workflow is intentionally simple:
- keep the app requirement in a prompt
- keep the implementation details in a matching `*-implementation.md` prompt file
- regenerate code on demand from those prompt definitions
- validate the generated app with tests
- include a language-appropriate runtime manifest in the generated output

## Prompt discovery

The generator scans the `prompts/` directory and finds prompt files automatically. Each app prompt has a matching implementation prompt, e.g.:

- `prompts/hello-world.md`
- `prompts/hello-world-implementation.md`

## Runtime manifests

The generator adds a manifest for the runtime automatically:
- Python outputs receive a `requirements.txt`
- Node outputs receive a `package.json`

This keeps the generated project buildable even when the prompt code itself is only stored as text in the repo.

## Toolchain

Generate the app from a discovered prompt:

```bash
python3 toolchain/regen.py prompts/hello-world.md --output generated/hello-world
```

Or let the generator discover prompts and then choose one explicitly:

```bash
python3 toolchain/regen.py --prompt-dir prompts
```

Then run the generated test suite:

```bash
python3 -m unittest discover -s generated/hello-world -p 'test_app.py' -q
```

Generated output is intentionally not committed to source control.
