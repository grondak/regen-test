#!/usr/bin/env python3
"""Publish the complete generated TinyWMS course to its sibling repository."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE = ROOT / "generated"
DEFAULT_PROMPTS = ROOT / "prompts"
DEFAULT_DESTINATION = ROOT.parent / "tinywms-course"
DEFAULT_TEMPLATES = ROOT / "toolchain" / "publish"
MANIFEST_NAME = ".regen.json"
STAGE_NAME = re.compile(r"^[0-9]{2}-[a-z0-9][a-z0-9-]*$")
MANAGED_ROOT_FILES = ("README.md", ".gitignore")


def expected_stage_names(prompt_dir: Path) -> list[str]:
    prompts = sorted(
        path
        for path in prompt_dir.iterdir()
        if path.is_file()
        and path.suffix.lower() == ".md"
        and not path.name.endswith("-implementation.md")
    )
    names = [path.stem for path in prompts]
    if not names or any(not STAGE_NAME.fullmatch(name) for name in names):
        raise RuntimeError(f"No valid ordered stage prompts found in {prompt_dir}.")
    return names


def safe_relative_path(value: str) -> bool:
    path = PurePosixPath(value)
    return bool(value) and not path.is_absolute() and ".." not in path.parts


def validate_complete_generation(source: Path, prompt_dir: Path) -> list[str]:
    if not source.is_dir():
        raise RuntimeError(f"Generated source directory does not exist: {source}")
    if not prompt_dir.is_dir():
        raise RuntimeError(f"Prompt directory does not exist: {prompt_dir}")

    expected = expected_stage_names(prompt_dir)
    actual = sorted(
        path.name
        for path in source.iterdir()
        if path.is_dir() and STAGE_NAME.fullmatch(path.name)
    )
    if actual != expected:
        raise RuntimeError(
            "Publication requires the complete prompt-defined stage sequence.\n"
            f"Expected: {expected}\nActual:   {actual}"
        )

    previous: str | None = None
    for stage_name in expected:
        stage_dir = source / stage_name
        manifest_path = stage_dir / MANIFEST_NAME
        if not manifest_path.is_file():
            raise RuntimeError(f"Missing publication checkpoint: {manifest_path}")
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Invalid publication checkpoint: {manifest_path}: {exc}") from exc

        if manifest.get("stage") != stage_name:
            raise RuntimeError(f"Manifest stage mismatch in {manifest_path}.")
        if manifest.get("source_prompt") != f"{stage_name}.md":
            raise RuntimeError(f"Manifest prompt mismatch in {manifest_path}.")
        if manifest.get("inherits_from") != previous:
            raise RuntimeError(
                f"Non-contiguous manifest {manifest_path}: expected inherits_from={previous!r}."
            )

        generated_files = manifest.get("generated_files")
        if not isinstance(generated_files, list):
            raise RuntimeError(f"Manifest has no generated_files list: {manifest_path}")
        for relative in generated_files:
            if not isinstance(relative, str) or not safe_relative_path(relative):
                raise RuntimeError(f"Unsafe generated path {relative!r} in {manifest_path}.")
            if not (stage_dir / relative).is_file():
                raise RuntimeError(f"Manifest file is missing: {stage_dir / relative}")

        for path in stage_dir.rglob("*"):
            if path.is_symlink():
                raise RuntimeError(f"Publication refuses generated symlinks: {path}")
        previous = stage_name

    return expected


def git_status(destination: Path) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(destination), "status", "--porcelain", "--untracked-files=all"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"Cannot inspect destination Git status: {detail}")
    return [line for line in result.stdout.splitlines() if line]


def validate_destination(destination: Path, source: Path, *, require_clean: bool) -> None:
    destination = destination.resolve()
    source = source.resolve()
    forbidden = {Path("/").resolve(), Path.home().resolve(), ROOT.resolve(), source}
    if destination in forbidden:
        raise RuntimeError(f"Refusing unsafe publication destination: {destination}")
    if not destination.is_dir() or not (destination / ".git").exists():
        raise RuntimeError(f"Destination must already be a Git repository: {destination}")
    for forbidden_name in ("prompts", "toolchain", "AGENTS.md"):
        if (destination / forbidden_name).exists():
            raise RuntimeError(
                f"Generated repository unexpectedly contains {forbidden_name}; remove it deliberately first."
            )
    if require_clean:
        dirty = git_status(destination)
        if dirty:
            preview = "\n".join(f"  {line}" for line in dirty[:20])
            if len(dirty) > 20:
                preview += f"\n  ... and {len(dirty) - 20} more"
            raise RuntimeError(
                "Destination has uncommitted or untracked changes. Commit, stash, or remove them "
                "before publishing:\n" + preview
            )


def copy_stage(source: Path, destination: Path) -> None:
    def ignored(_directory: str, names: list[str]) -> set[str]:
        return {
            name
            for name in names
            if name == MANIFEST_NAME
            or name == "__pycache__"
            or name.endswith((".pyc", ".pyo"))
        }

    shutil.copytree(source, destination, ignore=ignored)
    _prune_empty_directories(destination)


def _prune_empty_directories(root: Path) -> None:
    for path in sorted(root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        if not path.is_dir():
            continue
        try:
            next(path.iterdir())
        except StopIteration:
            path.rmdir()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tree_files(root: Path) -> dict[str, str]:
    if not root.exists():
        return {}
    return {
        path.relative_to(root).as_posix(): sha256(path)
        for path in root.rglob("*")
        if path.is_file() and not path.is_symlink()
    }


def prepare_export(
    staging: Path,
    source: Path,
    stage_names: list[str],
    templates: Path,
) -> None:
    readme_template = templates / "README.generated.md"
    ignore_template = templates / "gitignore.generated"
    if not readme_template.is_file() or not ignore_template.is_file():
        raise RuntimeError(f"Publication templates are incomplete in {templates}.")

    for stage_name in stage_names:
        copy_stage(source / stage_name, staging / stage_name)
    shutil.copy2(readme_template, staging / "README.md")
    shutil.copy2(ignore_template, staging / ".gitignore")


def describe_changes(staging: Path, destination: Path, stage_names: list[str]) -> list[str]:
    changes: list[str] = []
    for managed_name in [*stage_names, *MANAGED_ROOT_FILES]:
        wanted = staging / managed_name
        current = destination / managed_name
        wanted_files = tree_files(wanted) if wanted.is_dir() else ({managed_name: sha256(wanted)} if wanted.exists() else {})
        current_files = tree_files(current) if current.is_dir() else ({managed_name: sha256(current)} if current.exists() else {})
        for relative in sorted(wanted_files.keys() - current_files.keys()):
            changes.append(f"add {managed_name}/{relative}" if wanted.is_dir() else f"add {managed_name}")
        for relative in sorted(current_files.keys() - wanted_files.keys()):
            changes.append(f"delete {managed_name}/{relative}" if current.is_dir() else f"delete {managed_name}")
        for relative in sorted(wanted_files.keys() & current_files.keys()):
            if wanted_files[relative] != current_files[relative]:
                changes.append(f"update {managed_name}/{relative}" if wanted.is_dir() else f"update {managed_name}")

    expected = set(stage_names)
    for path in destination.iterdir():
        if path.is_dir() and STAGE_NAME.fullmatch(path.name) and path.name not in expected:
            changes.append(f"delete stale stage {path.name}/")
    return changes


def install_export(staging: Path, destination: Path, stage_names: list[str]) -> None:
    expected = set(stage_names)
    for path in destination.iterdir():
        if path.is_dir() and STAGE_NAME.fullmatch(path.name) and path.name not in expected:
            shutil.rmtree(path)

    for managed_name in [*stage_names, *MANAGED_ROOT_FILES]:
        target = destination / managed_name
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()
        shutil.move(str(staging / managed_name), str(target))


def publish_course(
    source: Path,
    prompt_dir: Path,
    destination: Path,
    templates: Path,
    *,
    dry_run: bool = False,
) -> list[str]:
    source = source.resolve()
    prompt_dir = prompt_dir.resolve()
    destination = destination.resolve()
    templates = templates.resolve()
    stage_names = validate_complete_generation(source, prompt_dir)
    validate_destination(destination, source, require_clean=not dry_run)

    with tempfile.TemporaryDirectory(prefix="tinywms-publish-") as tmpdir:
        staging = Path(tmpdir)
        prepare_export(staging, source, stage_names, templates)
        changes = describe_changes(staging, destination, stage_names)
        if not dry_run and changes:
            install_export(staging, destination, stage_names)

    return changes


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Publish a validated complete TinyWMS course to a clean sibling Git repository."
    )
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--prompt-dir", type=Path, default=DEFAULT_PROMPTS)
    parser.add_argument("--destination", type=Path, default=DEFAULT_DESTINATION)
    parser.add_argument("--templates", type=Path, default=DEFAULT_TEMPLATES)
    parser.add_argument("--dry-run", action="store_true", help="Show managed changes without writing them.")
    args = parser.parse_args()

    changes = publish_course(
        args.source,
        args.prompt_dir,
        args.destination,
        args.templates,
        dry_run=args.dry_run,
    )
    action = "Would publish" if args.dry_run else "Published"
    print(f"{action} {len(changes)} managed file changes to {args.destination.resolve()}.")
    for change in changes[:40]:
        print(f"- {change}")
    if len(changes) > 40:
        print(f"- ... and {len(changes) - 40} more")
    if not changes:
        print("Generated course repository is already current.")
    elif not args.dry_run:
        print("Review and commit the destination repository separately; this script never commits or pushes.")


if __name__ == "__main__":
    main()
