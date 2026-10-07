# regen-test

This repository stores prompt definitions rather than generated implementation code.

The workflow is intentionally simple:
- keep the app requirement in a prompt
- keep the implementation details in a matching `*-implementation.md` prompt file as a structured generation contract
- regenerate code on demand from those prompt definitions
- validate the generated app with tests
- include a language-appropriate runtime manifest in the generated output

## Prompt discovery

The generator scans the `prompts/` directory and finds prompt files automatically. Each app prompt has a matching implementation prompt, e.g.:

- `prompts/hello-world.md`
- `prompts/hello-world-implementation.md`

## Declarative implementation prompts

The first implementation prompt is intentionally no longer a literal source-code dump. Instead, it is a JSON contract that describes:
- the runtime
- the file list
- the template for each file
- the variable substitutions used to assemble the final source text

This makes the repo behave more like a prompt-driven generator than a template repository.

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

Run the generated app to see the output manually without naming a specific generated project folder:

```bash
python3 - <<'PY'
from pathlib import Path
import subprocess
import sys

root = Path('generated')
candidates = sorted([p for p in root.iterdir() if p.is_dir()], key=lambda p: p.stat().st_mtime, reverse=True)
for project_dir in candidates:
    for preferred in ('app.py', 'main.py', 'index.js', 'server.js'):
        entrypoint = project_dir / preferred
        if entrypoint.exists():
            raise SystemExit(subprocess.call([sys.executable, str(entrypoint)]))
    py_files = sorted([p for p in project_dir.glob('*.py') if not p.name.startswith('test_') and not p.name.endswith('_test.py')])
    if py_files:
        raise SystemExit(subprocess.call([sys.executable, str(py_files[0])]))
raise SystemExit('No generated app found under generated/')
PY
```

Then run the generated test suite by discovering the most recently generated project:

```bash
python3 - <<'PY'
from pathlib import Path
import subprocess
import sys

root = Path('generated')
projects = sorted([p for p in root.iterdir() if p.is_dir()], key=lambda p: p.stat().st_mtime, reverse=True)
if not projects:
    raise SystemExit('No generated project found under generated/')
project = projects[0]
subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', str(project), '-p', 'test_app.py', '-q'], check=True)
PY
```

Generated output is intentionally not committed to source control.
