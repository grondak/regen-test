#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path


def hello_world_generation(prompt_path: Path) -> tuple[str, str, str]:
    app_code = '''def main():
    print("Hello, World!")


if __name__ == "__main__":
    main()
'''

    test_code = '''import contextlib
import io
import unittest

import app


class AppTests(unittest.TestCase):
    def test_main_prints_hello_world(self):
        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            app.main()
        self.assertEqual(stdout.getvalue(), "Hello, World!\\n")
'''

    readme = f'''# Generated app from prompt

Prompt: {prompt_path.name}

This app was generated from a prompt and reproduces a minimal Hello, World implementation.
'''

    return app_code, test_code, readme


def detect_prompt_kind(prompt_text: str, prompt_path: Path) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", (prompt_path.stem + " " + prompt_text).lower()).strip("-")
    if "hello-world" in normalized or "hello world" in normalized:
        return "hello-world"
    raise ValueError(f"Unsupported prompt type: {prompt_path}")


def generate_app(prompt_path: Path, output_dir: Path) -> Path:
    prompt_text = prompt_path.read_text(encoding="utf-8")
    kind = detect_prompt_kind(prompt_text, prompt_path)

    if kind == "hello-world":
        app_code, test_code, readme = hello_world_generation(prompt_path)
    else:
        raise ValueError(f"No generator configured for: {kind}")

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "app.py").write_text(app_code, encoding="utf-8")
    (output_dir / "test_app.py").write_text(test_code, encoding="utf-8")
    (output_dir / "README.md").write_text(readme, encoding="utf-8")
    return output_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate code from a stored prompt.")
    parser.add_argument("prompt", type=Path, help="Path to the prompt markdown file.")
    parser.add_argument("--output", type=Path, default=Path("generated"), help="Directory to write generated files to.")
    args = parser.parse_args()

    if not args.prompt.exists():
        raise FileNotFoundError(f"Prompt not found: {args.prompt}")

    target = generate_app(args.prompt, args.output)
    print(f"Generated app into: {target}")


if __name__ == "__main__":
    main()
