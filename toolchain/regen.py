#!/usr/bin/env python3
"""Generate the TinyWMS teaching stages with one context-aware LLM request."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path, PurePosixPath
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    from .blueprint import (
        BLUEPRINT_NAME,
        blueprint_context,
        blueprint_prompt_contract,
        load_blueprint,
        normalize_blueprint_continuity,
        reference_implementation_context,
        validate_reference_snapshot,
        validate_snapshot_against_blueprint,
    )
except ImportError:
    from blueprint import (  # type: ignore[no-redef]
        BLUEPRINT_NAME,
        blueprint_context,
        blueprint_prompt_contract,
        load_blueprint,
        normalize_blueprint_continuity,
        reference_implementation_context,
        validate_reference_snapshot,
        validate_snapshot_against_blueprint,
    )


PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"
DEFAULT_MODEL = "gpt-5.4-mini"
DEFAULT_BASE_URL = "https://api.openai.com/v1"
MANIFEST_NAME = ".regen.json"
HANDOFF_NOTES_PATH = "handoff/regen-notes.json"
MAX_HANDOFF_NOTES_BYTES = 24_000
MAX_HANDOFF_NOTES_CONTEXT_STAGES = 6
REFERENCE_REPAIR_CACHE_VERSION = 4
SCRATCH_REFERENCE_CACHE_VERSION = 1
REFERENCE_BEHAVIOR_CACHE_PATHS = {
    "README.md",
    "data/pick-work.json",
    "data/init_db.py",
    "data/schema.sql",
    "data/seed.sql",
    "deploy/container-worker/README.md",
    "deploy/pick-ticket-worker/README.md",
    "deploy/pick-ticket-worker/environment.example",
    "deploy/pick-ticket-worker/install_user_service.sh",
    "deploy/pick-ticket-worker/tinywms-pick-ticket-worker.service.in",
    "deploy/aws/README.md",
    "deploy/aws/package_lambda.sh",
    "deploy/events/README.md",
    "docs/architecture.md",
    "docs/data-contracts.md",
    "docs/end-to-end.md",
    "docs/demo-runbook.md",
    "docs/git-history.md",
    "infra/events.yaml",
    "infra/template.yaml",
    "requirements.txt",
    "src/event_consumer_a.py",
    "src/event_consumer_b.py",
    "src/Dockerfile",
    "src/http_server.py",
    "src/db_adapter.py",
    "src/lambda_inventory.py",
    "src/pick_ticket_worker.py",
    "src/sqs_consumer.py",
    "src/web/app.js",
    "src/web/index.html",
    "src/web/style.css",
    "tests/test_aws_deployment_files.py",
    "tests/test_browser_assets.py",
    "tests/test_callback_integration.py",
    "tests/test_concurrency.py",
    "tests/test_container_worker.py",
    "tests/test_deployment_wiring.py",
    "tests/test_demo_runbook.py",
    "tests/test_end_to_end_walkthrough.py",
    "tests/test_event_consumers.py",
    "tests/test_http_order_flow.py",
    "tests/test_http_server.py",
    "tests/test_lambda_inventory.py",
    "tests/test_orders.py",
    "tests/test_pick_ticket_worker.py",
    "tests/test_sqs_consumer.py",
    "tests/test_sqlite_orders.py",
    "tests/test_web_app.js",
}
RUNTIME_ARTIFACT_NAMES = {"pick-tickets.txt"}
README_OPTIONAL_FILEMAP_PREFIXES = ("tests/",)
REQUIRED_STAGE_README_HEADINGS = [
    "## Stage purpose",
    "## Files in this lesson",
    "## Run the lesson",
    "## Run tests",
    "## Student exercises",
    "## Continuity note",
    "## Component assembly update",
    "## Cleanup",
]
REQUIRED_AWS_ARTIFACTS_BY_STAGE: list[tuple[int, tuple[str, ...]]] = [
    (5, ("deploy/ec2/run_inventory_server.sh", "deploy/ec2/environment.example")),
    (6, ("infra/lambda.yaml", "deploy/lambda/README.md")),
    (7, ("infra/api-gateway.yaml", "deploy/api-gateway/README.md")),
    (9, ("infra/rds.yaml", "deploy/rds/README.md")),
    (13, ("infra/sqs.yaml", "deploy/sqs/README.md")),
    (14, ("infra/events.yaml", "deploy/events/README.md")),
    (18, ("infra/template.yaml", "deploy/aws/README.md")),
]
IAM_CAPABILITY_TOKENS = ("CAPABILITY_IAM", "CAPABILITY_NAMED_IAM")
MAX_API_ATTEMPTS = 3
MAX_RETRY_AFTER_SECONDS = 30.0
TRANSIENT_HTTP_STATUSES = {408, 409, 429}
NON_RETRYABLE_429_CODES = {
    "credit_balance_exhausted",
    "organization_spend_limit_exceeded",
    "project_spend_limit_exceeded",
    "organization_usage_limit_exceeded",
}

SYSTEM_PROMPT = """You are evolving TinyWMS, a small teaching repository, through an ordered course.

Return only the requested structured stage plan. Treat the prompts as a progression, not as unrelated
greenfield projects. When a frozen baseline snapshot is supplied, the first requested stage starts as an
exact copy of that snapshot. Otherwise, the first requested stage starts empty. Every later requested
stage starts as an exact copy of the preceding stage. Emit only files that must be added or changed and
explicitly list files that must be deleted. Do not rewrite an unchanged file merely to make the stage
look complete. The generator will carry unchanged files forward.

Keep JSON, HTTP, SQL, processes, environment variables, and AWS boundaries visible to students. Prefer
the Python standard library, plain HTML, plain JavaScript, explicit SQL, and small readable programs.
Do not introduce a technology before its course prompt calls for it. Preserve useful earlier examples
unless the current lesson explicitly replaces them. Follow each stage's scope literally: in particular,
do not implement the application in a repository-establishment stage that says not to. Every stage must
include a useful README; every stage with runnable code must run and include tests. Expose useful failures,
avoid credentials, and document setup, cost, and cleanup when cloud resources appear. Represent an
intentionally empty required directory with a `.gitkeep` file so it survives materialization.

When tests directly import modules from `src/`, the README test command must visibly set
`PYTHONPATH=src`. Persistent component tests must assert stable component files or lesson-specific guides,
not the changing root `README.md`, because later stages replace that teaching guide.

Each `files` entry is a complete replacement body for one changed file. Paths are relative POSIX paths.
For a single-stage request without a frozen baseline, emit every file in the complete project and leave
`delete_files` empty.

When accumulated handoff notes are provided, preserve their inherited contracts and continuity checks
unless the current stage prompt explicitly changes them.
"""


PlanRequester = Callable[[str, dict[str, Any], str, str, str], dict[str, Any]]
StageSnapshotValidator = Callable[[str, dict[str, str]], None]


class StageValidationError(ValueError):
    """Report which generated prefix remains valid after a stage snapshot fails."""

    def __init__(self, message: str, stage_index: int, baseline_files: dict[str, str]):
        super().__init__(message)
        self.stage_index = stage_index
        self.baseline_files = baseline_files


def discover_prompt_files(prompt_dir: Path | None = None) -> list[Path]:
    """Return ordered course prompts, excluding non-stage implementation files."""
    root = prompt_dir or PROMPT_DIR
    return sorted(
        path
        for path in root.iterdir()
        if path.is_file()
        and path.suffix.lower() == ".md"
        and not path.name.endswith("-implementation.md")
    )


def read_repository_rules(prompt_dir: Path) -> str:
    """Read the teaching rules next to the prompt directory when available."""
    rules_path = prompt_dir.parent / "AGENTS.md"
    if not rules_path.exists():
        return "No additional repository rules were supplied."
    return rules_path.read_text(encoding="utf-8")


def build_generation_input(
    prompt_paths: list[Path],
    requested_prompts: list[Path],
    repository_rules: str,
    baseline_stage: str | None = None,
    baseline_files: dict[str, str] | None = None,
    extra_context: str | None = None,
) -> str:
    """Put every course prompt around the requested work so the model can plan evolution."""
    requested = {path.resolve() for path in requested_prompts}
    catalog: list[str] = []

    for number, prompt_path in enumerate(prompt_paths, start=1):
        marker = "CURRENT TARGET" if prompt_path.resolve() in requested else "COURSE CONTEXT"
        text = prompt_path.read_text(encoding="utf-8").strip()
        catalog.append(
            f"--- PROMPT {number}: {prompt_path.name} [{marker}] ---\n{text}\n"
            f"--- END PROMPT {number} ---"
        )

    if baseline_stage is not None:
        mode = (
            f"Generate the target stages as an ordered delta sequence beginning with the frozen "
            f"{baseline_stage} snapshot supplied below. Preserve every unchanged baseline file byte-for-byte. "
            "Frozen means the source checkpoint on disk is read-only; the requested stage may emit a complete "
            "replacement for an inherited file when its lesson or validation requirements demand a change."
        )
    elif len(requested_prompts) > 1:
        mode = "Generate all target stages as an ordered delta sequence beginning with an empty repository."
    else:
        mode = "Generate the one target stage as a complete standalone snapshot."
    target_names = ", ".join(path.stem for path in requested_prompts)
    batching_intent = (
        "BATCHING INTENT\n"
        "I'm only using this to avoid regeneration of perfectly good code.\n\n"
        if baseline_stage is not None
        else ""
    )
    generation_input = (
        f"{mode}\n"
        f"Required stage names, in exact output order: {target_names}\n\n"
        f"{batching_intent}"
        "REPOSITORY TEACHING RULES\n"
        f"{repository_rules.strip()}\n\n"
        "ORDERED COURSE PROMPTS\n"
        + "\n\n".join(catalog)
    )
    if baseline_stage is not None:
        generation_input += (
            f"\n\nFROZEN BASELINE SNAPSHOT: {baseline_stage}\n"
            "This JSON object maps each relative path to its complete current contents. Do not emit these "
            "files unless the requested stage genuinely changes them.\n"
            + json.dumps(baseline_files or {}, indent=2, sort_keys=True)
        )
    handoff_notes = _load_handoff_notes_from_snapshot(baseline_files or {})
    if handoff_notes:
        compact_notes = _notes_tail_for_context(handoff_notes)
        generation_input += (
            "\n\nACCUMULATED HANDOFF NOTES\n"
            "Use these notes as continuity constraints and preserve them unless the current stage prompt "
            "explicitly changes behavior.\n"
            + json.dumps(compact_notes, indent=2, sort_keys=True)
        )
    if extra_context:
        generation_input += f"\n\n{extra_context.strip()}"
    return generation_input


def build_retry_generation_input(
    generation_input: str,
    error: str,
    attempt: int,
    max_attempts: int,
    previous_plan: dict[str, Any] | None = None,
) -> str:
    """Append validator feedback for a bounded regeneration retry."""
    rejected_plan = ""
    if previous_plan is not None:
        rejected_plan = (
            "\n\nPREVIOUS REJECTED STRUCTURED PLAN\n"
            "Edit this exact candidate to resolve the validation error. Return the complete requested "
            "stage set required by the response schema, not a prose explanation or a partial patch.\n"
            + json.dumps(previous_plan, indent=2, sort_keys=True)
        )
    return (
        f"{generation_input}\n\n"
        "VALIDATION FAILURE FROM PREVIOUS ATTEMPT\n"
        f"Attempt {attempt} of {max_attempts} failed validation with this exact error:\n"
        f"{error}"
        f"{rejected_plan}\n\n"
        "Retry by fixing only what is necessary to satisfy this validation error while preserving prior "
        "scope, reuse intent, and unchanged files. If the error names an inherited baseline file, that file "
        "is not unchanged: emit its complete corrected contents in the requested stage delta. This evolves "
        "the target snapshot without modifying the frozen checkpoint directory."
    )


def build_output_schema(stage_names: list[str]) -> dict[str, Any]:
    """Build a strict response schema for a sequence of filesystem deltas."""
    file_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "content": {"type": "string"},
        },
        "required": ["path", "content"],
        "additionalProperties": False,
    }
    stage_schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "enum": stage_names},
            "summary": {"type": "string"},
            "files": {"type": "array", "items": file_schema},
            "delete_files": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["name", "summary", "files", "delete_files"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "stages": {
                "type": "array",
                "items": stage_schema,
                "minItems": len(stage_names),
                "maxItems": len(stage_names),
            }
        },
        "required": ["stages"],
        "additionalProperties": False,
    }


def _response_text(response: dict[str, Any]) -> str:
    output_text = response.get("output_text")
    if isinstance(output_text, str) and output_text:
        return output_text

    for item in response.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "refusal":
                raise RuntimeError(f"The model refused the generation request: {content.get('refusal', '')}")
            if content.get("type") == "output_text" and isinstance(content.get("text"), str):
                return content["text"]
    raise RuntimeError("The OpenAI response did not contain text output.")


def build_api_payload(
    generation_input: str,
    schema: dict[str, Any],
    model: str,
) -> dict[str, Any]:
    """Return the exact JSON body sent to the Responses API."""
    return {
        "model": model,
        "instructions": SYSTEM_PROMPT,
        "input": generation_input,
        "text": {
            "format": {
                "type": "json_schema",
                "name": "tinywms_stage_plan",
                "strict": True,
                "schema": schema,
            }
        },
    }


def _api_error_code(detail: str) -> str | None:
    try:
        payload = json.loads(detail)
    except json.JSONDecodeError:
        return None
    error = payload.get("error") if isinstance(payload, dict) else None
    return error.get("code") if isinstance(error, dict) and isinstance(error.get("code"), str) else None


def _retry_delay_seconds(error: HTTPError | None, failed_attempt: int) -> float | None:
    retry_after = error.headers.get("Retry-After") if error is not None and error.headers else None
    if retry_after is not None:
        try:
            server_delay = float(retry_after)
        except ValueError:
            server_delay = -1
        if server_delay > MAX_RETRY_AFTER_SECONDS:
            return None
        if server_delay >= 0:
            return server_delay + random.uniform(0, 0.25)
    return min(2 ** (failed_attempt - 1), MAX_RETRY_AFTER_SECONDS) + random.uniform(0, 0.25)


def request_plan(
    generation_input: str,
    schema: dict[str, Any],
    model: str,
    api_key: str,
    base_url: str,
) -> dict[str, Any]:
    """Call the Responses API using only the Python standard library."""
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set. Set it before running the generator.")

    body = build_api_payload(generation_input, schema, model)
    request = Request(
        f"{base_url.rstrip('/')}/responses",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    payload: dict[str, Any] | None = None
    for attempt in range(1, MAX_API_ATTEMPTS + 1):
        try:
            with urlopen(request, timeout=300) as response:
                payload = json.loads(response.read().decode("utf-8"))
            break
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            error_code = _api_error_code(detail)
            transient = error.code in TRANSIENT_HTTP_STATUSES or error.code >= 500
            if error.code == 429 and error_code in NON_RETRYABLE_429_CODES:
                transient = False
            delay = _retry_delay_seconds(error, attempt) if transient else None
            if attempt == MAX_API_ATTEMPTS or delay is None:
                raise RuntimeError(
                    f"OpenAI API request failed with HTTP {error.code}: {detail}"
                ) from error
            time.sleep(delay)
        except (URLError, TimeoutError, ConnectionError) as error:
            delay = _retry_delay_seconds(None, attempt)
            if attempt == MAX_API_ATTEMPTS:
                reason = getattr(error, "reason", str(error))
                raise RuntimeError(f"Could not reach the OpenAI API: {reason}") from error
            time.sleep(delay)

    assert payload is not None

    if payload.get("status") == "incomplete":
        details = payload.get("incomplete_details")
        reason = details.get("reason") if isinstance(details, dict) else None
        explanation = f": {reason}" if reason else ""
        raise RuntimeError(
            f"The OpenAI response was incomplete{explanation}. "
            "Generate a smaller checkpoint with --through, then continue with --resume-through."
        )

    try:
        return json.loads(_response_text(payload))
    except json.JSONDecodeError as error:
        raise RuntimeError("The model response was not valid JSON.") from error


def _safe_path(relative_name: str) -> PurePosixPath:
    if not relative_name or relative_name == "." or relative_name.endswith("/") or "\\" in relative_name:
        raise ValueError(f"Unsafe generated path: {relative_name!r}")
    path = PurePosixPath(relative_name)
    if path.is_absolute() or ".." in path.parts or relative_name == MANIFEST_NAME:
        raise ValueError(f"Unsafe generated path: {relative_name!r}")
    return path


def _output_path(output_dir: Path, relative_name: str) -> Path:
    relative_path = _safe_path(relative_name)
    root = output_dir.resolve()
    target = output_dir.joinpath(*relative_path.parts)
    if not target.resolve().is_relative_to(root):
        raise ValueError(f"Generated path escapes through a symbolic link: {relative_name!r}")
    return target


def validate_plan(plan: dict[str, Any], stage_names: list[str]) -> list[dict[str, Any]]:
    """Validate ordering and paths even when the API schema is bypassed in tests."""
    stages = plan.get("stages")
    if not isinstance(stages, list):
        raise ValueError("Generation plan must contain a stages array.")

    actual_names = [stage.get("name") for stage in stages if isinstance(stage, dict)]
    if actual_names != stage_names or len(stages) != len(stage_names):
        raise ValueError(f"Expected stages {stage_names!r}, received {actual_names!r}.")

    for stage in stages:
        if not isinstance(stage.get("summary"), str):
            raise ValueError(f"Stage {stage['name']} has no summary.")
        if not isinstance(stage.get("files"), list) or not isinstance(stage.get("delete_files"), list):
            raise ValueError(f"Stage {stage['name']} has invalid file changes.")

        normalized_files: dict[str, str] = {}
        for item in stage["files"]:
            if (
                not isinstance(item, dict)
                or not isinstance(item.get("path"), str)
                or not isinstance(item.get("content"), str)
            ):
                raise ValueError(f"Stage {stage['name']} contains an invalid file entry.")
            normalized = _safe_path(item["path"]).as_posix()
            if normalized in normalized_files:
                del normalized_files[normalized]
            normalized_files[normalized] = item["content"]

        stage["files"] = [
            {"path": path, "content": content}
            for path, content in normalized_files.items()
        ]

        normalized_deletes: dict[str, None] = {}
        for relative_name in stage["delete_files"]:
            if not isinstance(relative_name, str):
                raise ValueError(f"Stage {stage['name']} contains an invalid deleted path.")
            normalized = _safe_path(relative_name).as_posix()
            if normalized in normalized_deletes:
                continue
            normalized_deletes[normalized] = None

        written_paths = set(normalized_files.keys())
        stage["delete_files"] = [
            path for path in normalized_deletes if path not in written_paths
        ]
    return stages


def _extract_files_in_lesson_paths(readme_text: str) -> list[str]:
    match = re.search(r"## Files in this lesson\n(.*?)(?:\n## |\Z)", readme_text, flags=re.S)
    if not match:
        return []
    paths: list[str] = []
    for raw_line in match.group(1).splitlines():
        line = raw_line.strip()
        if not line.startswith("- "):
            continue
        code = re.search(r"`([^`]+)`", line)
        if code:
            paths.append(code.group(1))
    return paths


def _prune_missing_readme_file_map_entries(snapshot: dict[str, str]) -> bool:
    readme = snapshot.get("README.md")
    if readme is None:
        return False
    match = re.search(r"(## Files in this lesson\n)(.*?)(\n## |\Z)", readme, flags=re.S)
    if not match:
        return False

    header, body, trailer = match.group(1), match.group(2), match.group(3)
    repaired = False
    retained_lines: list[str] = []

    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line.startswith("- "):
            retained_lines.append(raw_line)
            continue
        code = re.search(r"`([^`]+)`", line)
        if not code:
            retained_lines.append(raw_line)
            continue

        relative_name = code.group(1)
        candidate = relative_name[:-1] if relative_name.endswith("/") else relative_name
        try:
            normalized = _safe_path(candidate).as_posix()
        except ValueError:
            retained_lines.append(raw_line)
            continue

        if PurePosixPath(normalized).name in RUNTIME_ARTIFACT_NAMES:
            repaired = True
            continue

        exists = False
        if relative_name.endswith("/"):
            exists = any(path.startswith(normalized) for path in snapshot)
        else:
            exists = normalized in snapshot

        if exists or normalized.startswith(README_OPTIONAL_FILEMAP_PREFIXES):
            retained_lines.append(raw_line)
            continue

        repaired = True

    if not repaired:
        return False

    rebuilt_body = "\n".join(retained_lines)
    start, end = match.span()
    snapshot["README.md"] = readme[:start] + header + rebuilt_body + trailer + readme[end:]
    return True


def _extract_markdown_section(readme_text: str, heading: str) -> str:
    pattern = rf"{re.escape(heading)}\n(.*?)(?:\n## |\Z)"
    match = re.search(pattern, readme_text, flags=re.S)
    if not match:
        return ""
    return match.group(1).strip()


def _extract_note_value(section_text: str, label: str) -> str:
    pattern = rf"-\s+{re.escape(label)}:\s*(.+)"
    match = re.search(pattern, section_text)
    if not match:
        return ""
    return match.group(1).strip()


def _build_stage_handoff_note(stage: dict[str, Any], snapshot: dict[str, str]) -> dict[str, Any]:
    readme_text = snapshot.get("README.md", "")
    continuity = _extract_markdown_section(readme_text, "## Continuity note")
    components = _extract_markdown_section(readme_text, "## Component assembly update")
    inherited_contract = _extract_note_value(continuity, "Inherited contract")
    boundary_change = _extract_note_value(continuity, "Boundary changed in this stage")
    components_added = _extract_note_value(components, "Added")
    components_reused = _extract_note_value(components, "Reused unchanged")
    components_replaced = _extract_note_value(components, "Replaced/evolved")
    note = {
        "stage": stage["name"],
        "summary": stage["summary"],
        "inherited_contract": inherited_contract,
        "boundary_change": boundary_change,
        "components": {
            "added": components_added,
            "reused_unchanged": components_reused,
            "replaced_or_evolved": components_replaced,
        },
        "continuity_checks": [
            "README file-map paths must exist in the stage snapshot.",
            "Inherited contracts remain stable unless this stage prompt explicitly changes them.",
        ],
    }
    return note


def _load_handoff_notes_from_snapshot(snapshot: dict[str, str]) -> list[dict[str, Any]]:
    text = snapshot.get(HANDOFF_NOTES_PATH)
    if text is None:
        return []
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid handoff notes JSON at {HANDOFF_NOTES_PATH}.") from error
    if not isinstance(payload, dict) or not isinstance(payload.get("notes"), list):
        raise ValueError(f"Handoff notes at {HANDOFF_NOTES_PATH} must contain a notes array.")
    notes = payload["notes"]
    for note in notes:
        if not isinstance(note, dict):
            raise ValueError(f"Handoff notes at {HANDOFF_NOTES_PATH} contain a non-object entry.")
        if not isinstance(note.get("stage"), str):
            raise ValueError(f"Handoff notes at {HANDOFF_NOTES_PATH} contain an entry without stage.")
    return notes


def _merge_handoff_notes(
    existing_notes: list[dict[str, Any]],
    stage_note: dict[str, Any],
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    for note in existing_notes:
        if note.get("stage") == stage_note["stage"]:
            continue
        merged.append(note)
    merged.append(stage_note)
    return merged


def _truncate_handoff_text(value: Any, limit: int) -> str:
    text = value if isinstance(value, str) else ""
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _compact_historical_handoff_note(note: dict[str, Any]) -> dict[str, Any]:
    components = note.get("components")
    added = components.get("added", "") if isinstance(components, dict) else ""
    return {
        "stage": note.get("stage", ""),
        "summary": _truncate_handoff_text(note.get("summary"), 160),
        "inherited_contract": _truncate_handoff_text(note.get("inherited_contract"), 160),
        "boundary_change": _truncate_handoff_text(note.get("boundary_change"), 160),
        "components_added": _truncate_handoff_text(added, 120),
        "compacted": True,
    }


def _compact_current_handoff_note(note: dict[str, Any]) -> dict[str, Any]:
    components = note.get("components")
    compact_components: dict[str, str] = {}
    if isinstance(components, dict):
        for key in ("added", "reused_unchanged", "replaced_or_evolved"):
            compact_components[key] = _truncate_handoff_text(components.get(key), 512)
    checks = note.get("continuity_checks")
    return {
        "stage": note.get("stage", ""),
        "summary": _truncate_handoff_text(note.get("summary"), 512),
        "inherited_contract": _truncate_handoff_text(note.get("inherited_contract"), 512),
        "boundary_change": _truncate_handoff_text(note.get("boundary_change"), 512),
        "components": compact_components,
        "continuity_checks": checks if isinstance(checks, list) else [],
    }


def _serialize_handoff_notes(stage_name: str, notes: list[dict[str, Any]]) -> str:
    """Keep recent notes detailed and compact older history within the storage budget."""
    max_detailed = min(MAX_HANDOFF_NOTES_CONTEXT_STAGES, len(notes))
    for detailed_count in range(max_detailed, 0, -1):
        compact_count = len(notes) - detailed_count
        stored_notes = [
            _compact_historical_handoff_note(note)
            for note in notes[:compact_count]
        ] + notes[compact_count:]
        text = json.dumps(
            {"current_stage": stage_name, "notes": stored_notes},
            indent=2,
            sort_keys=True,
        ) + "\n"
        if len(text.encode("utf-8")) <= MAX_HANDOFF_NOTES_BYTES:
            return text

    if notes:
        stored_notes = [
            _compact_historical_handoff_note(note)
            for note in notes[:-1]
        ] + [_compact_current_handoff_note(notes[-1])]
        text = json.dumps(
            {"current_stage": stage_name, "notes": stored_notes},
            indent=2,
            sort_keys=True,
        ) + "\n"
        if len(text.encode("utf-8")) <= MAX_HANDOFF_NOTES_BYTES:
            return text

    raise ValueError(
        f"Stage {stage_name} handoff notes cannot fit within {MAX_HANDOFF_NOTES_BYTES} bytes after compaction."
    )


def _notes_tail_for_context(notes: list[dict[str, Any]]) -> dict[str, Any]:
    tail = notes[-MAX_HANDOFF_NOTES_CONTEXT_STAGES :]
    compact_tail: list[dict[str, Any]] = []
    for note in tail:
        compact_tail.append(
            {
                "stage": note.get("stage", ""),
                "summary": note.get("summary", ""),
                "inherited_contract": note.get("inherited_contract", ""),
                "boundary_change": note.get("boundary_change", ""),
                "components": note.get("components", {}),
            }
        )
    return {
        "notes_window": compact_tail,
        "notes_window_count": len(compact_tail),
        "total_notes_available": len(notes),
    }


def _validate_handoff_notes(stage_name: str, snapshot: dict[str, str]) -> None:
    notes_text = snapshot.get(HANDOFF_NOTES_PATH)
    if notes_text is None:
        raise ValueError(f"Stage {stage_name} did not produce {HANDOFF_NOTES_PATH}.")
    if len(notes_text.encode("utf-8")) > MAX_HANDOFF_NOTES_BYTES:
        raise ValueError(
            f"Stage {stage_name} produced oversized handoff notes ({HANDOFF_NOTES_PATH})."
        )
    notes = _load_handoff_notes_from_snapshot(snapshot)
    if not notes:
        raise ValueError(f"Stage {stage_name} produced empty handoff notes ({HANDOFF_NOTES_PATH}).")
    if notes[-1].get("stage") != stage_name:
        raise ValueError(
            f"Stage {stage_name} handoff notes must end with the current stage entry."
        )
    latest = notes[-1]
    required_latest = [
        "summary",
        "inherited_contract",
        "boundary_change",
        "components",
        "continuity_checks",
    ]
    for field in required_latest:
        if field not in latest:
            raise ValueError(
                f"Stage {stage_name} handoff note is missing required field: {field}."
            )
    if not isinstance(latest["components"], dict):
        raise ValueError(f"Stage {stage_name} handoff components field must be an object.")


def _validate_readme_contract(stage_name: str, snapshot: dict[str, str]) -> None:
    readme = snapshot.get("README.md")
    if readme is None:
        raise ValueError(f"Stage {stage_name} did not produce a README.md.")

    is_stage_zero = stage_name.startswith("00-")
    if not is_stage_zero:
        first_line = readme.splitlines()[0] if readme.splitlines() else ""
        if not first_line.startswith("# TinyWMS lesson: "):
            raise ValueError(
                f"Stage {stage_name} README title must start with '# TinyWMS lesson: '."
            )

        previous_index = -1
        for heading in REQUIRED_STAGE_README_HEADINGS:
            index = readme.find(heading)
            if index < 0:
                raise ValueError(f"Stage {stage_name} README is missing heading: {heading}")
            if index <= previous_index:
                raise ValueError(
                    f"Stage {stage_name} README headings are out of order near {heading}."
                )
            previous_index = index

    for relative_name in _extract_files_in_lesson_paths(readme):
        candidate = relative_name[:-1] if relative_name.endswith("/") else relative_name
        normalized = _safe_path(candidate).as_posix()
        if "//" in relative_name:
            raise ValueError(f"Stage {stage_name} README lists malformed path: {relative_name}")
        if relative_name.endswith("/"):
            if not any(path.startswith(normalized) for path in snapshot):
                raise ValueError(
                    f"Stage {stage_name} README references missing path: {relative_name}"
                )
            continue
        if normalized not in snapshot:
            if normalized.startswith(README_OPTIONAL_FILEMAP_PREFIXES):
                continue
            raise ValueError(f"Stage {stage_name} README references missing path: {relative_name}")
        if PurePosixPath(normalized).name in RUNTIME_ARTIFACT_NAMES:
            raise ValueError(
                f"Stage {stage_name} README must not list runtime artifact in files section: "
                f"{relative_name}"
            )


def _validate_stage18_constraints(stage_name: str, snapshot: dict[str, str]) -> None:
    if stage_name != "18-aws-deployment":
        return

    required = ["infra/template.yaml", "deploy/aws/README.md"]
    missing = [path for path in required if path not in snapshot]
    if missing:
        raise ValueError(f"Stage {stage_name} is missing required deploy artifacts: {missing}")

    deploy_readme = snapshot["deploy/aws/README.md"]
    sections = ["## Deploy", "## Resolve outputs", "## Verify contracts", "## Destroy"]
    section_positions = [deploy_readme.find(section) for section in sections]
    if not all(index >= 0 for index in section_positions) or section_positions != sorted(section_positions):
        raise ValueError(
            f"Stage {stage_name} deploy README must contain ordered sections: {sections}"
        )

    runtime_text = ""
    for path, content in snapshot.items():
        if path.startswith("tests/"):
            continue
        if PurePosixPath(path).suffix.lower() in {".md", ".yml", ".yaml", ".json", ".sh", ".py", ".tf"}:
            runtime_text += content + "\n"
    for forbidden in ("example.invalid", "example.com", "123456789012"):
        if forbidden in runtime_text:
            raise ValueError(f"Stage {stage_name} contains forbidden deploy literal: {forbidden}")

    infra = snapshot["infra/template.yaml"]
    required_tokens = [
        ("API entry", ("AWS::ApiGateway", "AWS::ApiGatewayV2")),
        ("API methods", ("AWS::ApiGateway::Method",)),
        ("API deployment stage", ("AWS::ApiGateway::Deployment",)),
        ("Lambda function", ("AWS::Lambda::Function",)),
        ("Lambda invoke permission", ("AWS::Lambda::Permission",)),
        ("IAM role", ("AWS::IAM::Role",)),
        ("SQS queue", ("AWS::SQS::Queue",)),
        ("Events resource", ("AWS::Events::",)),
        ("Logs resource", ("AWS::Logs::",)),
    ]
    for label, tokens in required_tokens:
        if not any(token in infra for token in tokens):
            raise ValueError(f"Stage {stage_name} infra template is missing {label}.")

    if re.search(r"ApiBaseUrl:\s*\n\s*Value:\s*['\"]?https?://", infra):
        raise ValueError(
            f"Stage {stage_name} ApiBaseUrl output must be derived from resources, not a literal URL."
        )
    if "PathPart: inventory" not in infra:
        raise ValueError(f"Stage {stage_name} infra template must define an inventory API route.")


def _stage_number(stage_name: str) -> int | None:
    prefix = stage_name.split("-", 1)[0]
    if not prefix.isdigit():
        return None
    return int(prefix)


def _validate_aws_artifact_continuity(stage_name: str, snapshot: dict[str, str]) -> None:
    required = _required_aws_artifact_paths(stage_name)
    missing = [path for path in required if path not in snapshot]
    if missing:
        raise ValueError(
            f"Stage {stage_name} is missing required AWS deployment artifacts: {missing}"
        )


def _required_aws_artifact_paths(stage_name: str) -> list[str]:
    """Return cumulative deployment paths introduced by or before a stage."""
    stage_num = _stage_number(stage_name)
    if stage_num is None:
        return []
    return [
        path
        for min_stage, files in REQUIRED_AWS_ARTIFACTS_BY_STAGE
        if stage_num >= min_stage
        for path in files
    ]


def _deployability_audit_issues(snapshot: dict[str, str]) -> list[str]:
    """Return every visible deployment defect so one retry can repair them together."""
    infra_templates = [
        path
        for path in snapshot
        if path.startswith("infra/") and path.endswith(".yaml")
    ]
    if not infra_templates:
        return []

    deploy_readmes = [
        path
        for path in snapshot
        if path.startswith("deploy/") and path.endswith("/README.md")
    ]
    readme_text = "\n".join(snapshot[path] for path in deploy_readmes)
    issues: list[str] = []

    for template_path in infra_templates:
        text = snapshot[template_path]
        if "AWSTemplateFormatVersion" not in text and "Type: AWS::" not in text:
            continue

        if "AWS::IAM::Role" in text and not any(token in readme_text for token in IAM_CAPABILITY_TOKENS):
            issues.append(
                f"deploy docs must include --capabilities for IAM resources in {template_path}"
            )

        if "Type: AWS::Lambda::Function" in text and "ZipFile:" in text:
            if re.search(r"^\s*Handler:\s*src\.", text, flags=re.M):
                issues.append(
                    f"inline ZipFile Lambda in {template_path} must use an inline handler such as index.handler"
                )

        if "AWS::RDS::DBSubnetGroup" in text and re.search(r"^\s*SubnetIds:\s*\[\s*\]\s*$", text, flags=re.M):
            issues.append(f"{template_path} has an empty DBSubnetGroup SubnetIds list")

        if "change-me-in-a-real-deployment" in text:
            issues.append(
                f"remove non-runnable placeholder credentials from {template_path}"
            )
        if re.search(r"\bplaceholder(?:-[A-Za-z0-9_-]+)?\b", text, flags=re.I):
            issues.append(
                f"remove non-runnable placeholder values from {template_path}; use required "
                "deploy-time parameters and NoEcho secret parameters"
            )

    return issues


def _consolidated_deployment_wiring_issues(template: str, handler: str) -> list[str]:
    """Check that the single-stack walkthrough preserves the proven component wiring."""
    issues: list[str] = []
    resource_pattern = r"(?m)^  ([A-Za-z][A-Za-z0-9]*):\n    Type:\s*{}\s*$"

    def resources(resource_type: str) -> list[str]:
        return re.findall(resource_pattern.format(re.escape(resource_type)), template)

    rules = resources("AWS::Events::Rule")
    queues = resources("AWS::SQS::Queue")
    queue_policies = resources("AWS::SQS::QueuePolicy")
    event_buses = set(resources("AWS::Events::EventBus"))
    if len(rules) < 2 or template.count("Targets:") < 2:
        issues.append(
            "infra/template.yaml itself must declare two AWS::Events::Rule resources with "
            "two Targets sections; the separate infra/events.yaml stack does not satisfy "
            "the consolidated deployment"
        )
    if len(queues) < 3:
        issues.append(
            "infra/template.yaml must declare the pick-work queue plus two independent "
            "EventBridge consumer queues"
        )
    if len(queue_policies) < 2:
        issues.append(
            "infra/template.yaml must declare delivery policies for both EventBridge consumer queues"
        )

    bus_reference = re.search(r"(?m)^\s*EVENT_BUS_NAME:\s*!Ref\s+([A-Za-z][A-Za-z0-9]*)\s*$", template)
    if not bus_reference or bus_reference.group(1) not in event_buses:
        issues.append("Lambda EVENT_BUS_NAME must reference an AWS::Events::EventBus resource, not a rule")

    published_detail_types = set(
        re.findall(r"['\"]DetailType['\"]\s*:\s*['\"]([^'\"]+)['\"]", handler)
    )
    missing_detail_types = sorted(value for value in published_detail_types if value not in template)
    if missing_detail_types:
        issues.append(
            "EventBridge rule patterns must match the Lambda's published DetailType values: "
            + ", ".join(missing_detail_types)
        )

    if any(token in handler.lower() for token in ("psycopg", "postgresql")):
        if not re.search(r"(?mi)^\s*Engine:\s*postgres\s*$", template):
            issues.append("the consolidated RDS resource must use PostgreSQL because the Lambda uses psycopg")
        if re.search(r"(?mi)^\s*Engine:\s*mysql\s*$", template):
            issues.append("the consolidated RDS resource cannot use MySQL with the PostgreSQL Lambda path")

    lambda_resources = resources("AWS::Lambda::Function")
    if lambda_resources:
        lambda_blocks: list[str] = []
        for resource_name in lambda_resources:
            match = re.search(
                rf"(?ms)^  {re.escape(resource_name)}:\n(?P<body>.*?)(?=^  [A-Za-z][A-Za-z0-9]*:\n|\Z)",
                template,
            )
            if match:
                lambda_blocks.append(match.group("body"))
        if any(re.search(r"(?m)^\s*Role:\s*arn:aws:iam::", block) for block in lambda_blocks):
            issues.append("the Lambda Role cannot be a hard-coded account ARN")
        if not resources("AWS::IAM::Role"):
            issues.append("a raw AWS::Lambda::Function needs a deployable AWS::IAM::Role resource")
        if any(re.search(r"(?m)^\s*Policies:\s*$", block) for block in lambda_blocks):
            issues.append(
                "Policies is not valid on raw AWS::Lambda::Function; attach policies to its AWS::IAM::Role"
            )

    return issues


def _validate_deployability_audit(stage_name: str, snapshot: dict[str, str]) -> None:
    stage_num = _stage_number(stage_name)
    if stage_num is None or stage_num < 6:
        return

    issues = _deployability_audit_issues(snapshot)
    if issues:
        raise ValueError(
            f"Stage {stage_name} deployability audit failed: " + "; ".join(issues) + "."
        )


def _handler_reads_dict_bin_location(handler: str) -> bool:
    """Accept direct or helper-based reads of the canonical dict-row field."""
    return bool(
        re.search(r"\b\w+\s*\.get\(\s*['\"]bin_location['\"]", handler)
        or re.search(r"\b\w+\s*\[\s*['\"]bin_location['\"]\s*\]", handler)
        or re.search(r"['\"]bin_location['\"]\s*,\s*2\b", handler)
    )


def _handler_normalizes_tuple_inventory_row(handler: str) -> bool:
    """Accept indexing, a named helper, column zipping, or visible tuple unpacking."""
    return bool(
        re.search(r"\b\w+\s*\[\s*2\s*\]", handler)
        or re.search(r"['\"]bin_location['\"]\s*,\s*2\b", handler)
        or ("zip(" in handler and "bin_location" in handler)
        or re.search(
            r"^[^=\n]*\bbin_location\b[^=\n]*=\s*\w+\s*$",
            handler,
            flags=re.M,
        )
    )


def _inventory_select_has_canonical_columns(handler: str) -> bool:
    """Require one visible inventory SELECT carrying the stable JSON fields."""
    required = {"sku", "description", "bin_location", "quantity", "unit"}
    for match in re.finditer(
        r"SELECT\s+(?P<columns>.*?)\s+FROM\s+inventory\b",
        handler,
        flags=re.I | re.S,
    ):
        identifiers = {
            identifier.lower()
            for identifier in re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", match.group("columns"))
        }
        if required <= identifiers:
            return True
    return False


def _has_sqlite_persistence_proof(source: str) -> bool:
    """Recognize a real temporary-database proof without requiring schema-loader internals."""
    lowered = source.lower()
    return (
        any(token in lowered for token in ("tempfile", "temporarydirectory", "namedtemporaryfile", "mkstemp"))
        and "tinywms_db" in lowered
        and "tinywms_sqlite_path" in lowered
        and "init_db" in lowered
        and "open_connection" in lowered
        and "place_order" in lowered
        and "select" in lowered
        and all(table in lowered for table in ("orders", "inventory"))
        and "assert" in lowered
    )


def _unittest_case_methods(source: str) -> set[str]:
    """Return methods discoverable by the repository's unittest command."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    methods: set[str] = set()
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        is_test_case = any(
            (isinstance(base, ast.Attribute) and base.attr == "TestCase")
            or (isinstance(base, ast.Name) and base.id == "TestCase")
            for base in node.bases
        )
        if not is_test_case:
            continue
        methods.update(
            item.name
            for item in node.body
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
            and item.name.startswith("test_")
        )
    return methods


def _relational_teaching_issues(stage_name: str, snapshot: dict[str, str]) -> list[str]:
    """Keep the local SQL path runnable without leaking later relational lessons backward."""
    stage_num = _stage_number(stage_name)
    if stage_num is None or stage_num < 8:
        return []

    issues: list[str] = []
    schema = snapshot.get("data/schema.sql", "")
    seed = snapshot.get("data/seed.sql", "")
    adapter = snapshot.get("src/db_adapter.py", "")
    initializer = snapshot.get("data/init_db.py", "")
    # Match through the statement terminator rather than the first closing
    # parenthesis. CHECK and REFERENCES clauses contain nested parentheses.
    inventory_table = re.search(
        r"CREATE\s+TABLE(?:\s+IF\s+NOT\s+EXISTS)?\s+inventory\s*\((?P<body>.*?);",
        schema,
        flags=re.I | re.S,
    )
    inventory_body = inventory_table.group("body") if inventory_table else ""
    if not inventory_table:
        issues.append("data/schema.sql does not create the inventory table")
    else:
        inventory_columns = inventory_body.lower()
        if "description" not in inventory_columns:
            issues.append("data/schema.sql must use canonical inventory.description, not inventory.name")
        if "bin_location" not in inventory_columns:
            issues.append("data/schema.sql must use canonical inventory.bin_location")
        if "unit" not in inventory_columns:
            issues.append("data/schema.sql must preserve canonical inventory.unit")
    if re.search(r"\bINSERT\s+INTO\s+inventory\s*\([^)]*\bbin\b", seed, flags=re.I):
        issues.append("data/seed.sql still inserts the obsolete inventory.bin column")
    if "bin_location" not in seed:
        issues.append("data/seed.sql does not load the canonical bin_location column")
    if "description" not in seed:
        issues.append("data/seed.sql does not load the canonical description column")
    if not re.search(r"\bunit\b", seed, flags=re.I):
        issues.append("data/seed.sql does not load the canonical unit column")

    for path in ("src/db_adapter.py", "data/init_db.py"):
        if path not in snapshot:
            issues.append(f"missing relational teaching artifact {path}")
    adapter_lower = adapter.lower()
    initializer_lower = initializer.lower()
    for token, message in (
        ("sqlite3", "src/db_adapter.py does not expose a SQLite backend"),
        ("postgres", "src/db_adapter.py does not expose a PostgreSQL backend"),
        ("foreign_keys", "src/db_adapter.py does not enable SQLite foreign keys"),
        ("for update", "src/db_adapter.py does not visibly adapt PostgreSQL row locking for SQLite"),
    ):
        if token not in adapter_lower:
            issues.append(message)
    if "%s" not in adapter or "?" not in adapter:
        issues.append("src/db_adapter.py does not visibly translate TinyWMS %s placeholders to SQLite ?")
    if not all(token in initializer_lower for token in ("schema.sql", "seed.sql", "sqlite", "postgres")):
        issues.append("data/init_db.py must initialize schema and seed data for SQLite or PostgreSQL")
    elif not (
        "open_connection" in initializer
        and any(token in initializer for token in ("read_text(", "open("))
        and any(token in initializer for token in ("executescript(", ".execute("))
        and ".commit(" in initializer
    ):
        issues.append("data/init_db.py does not execute and commit the visible schema and seed SQL")
    if not re.search(r"(?m)^def\s+init_db\s*\(", initializer):
        issues.append("data/init_db.py must export init_db() for the local SQLite teaching proof")

    has_order_tables = bool(
        re.search(r"CREATE\s+TABLE(?:\s+IF\s+NOT\s+EXISTS)?\s+orders\b", schema, flags=re.I)
        or re.search(r"CREATE\s+TABLE(?:\s+IF\s+NOT\s+EXISTS)?\s+order_lines\b", schema, flags=re.I)
    )
    if stage_num < 11 and has_order_tables:
        issues.append("order tables appear before the Stage 11 orders lesson")

    handler = snapshot.get("src/lambda_inventory.py", "")
    if stage_num >= 10:
        combined = handler + "\n" + adapter
        if "TINYWMS_DB" not in combined or "TINYWMS_SQLITE_PATH" not in combined:
            issues.append("the database path lacks explicit TINYWMS_DB and TINYWMS_SQLITE_PATH switches")
        if not re.search(r"TINYWMS_DB[^\n]{0,100}postgres", combined, flags=re.I):
            issues.append("PostgreSQL is not visibly the default TINYWMS_DB backend")
        if not _inventory_select_has_canonical_columns(handler):
            issues.append(
                "src/lambda_inventory.py must SELECT canonical inventory fields "
                "sku, description, bin_location, quantity, and unit"
            )

    if stage_num >= 11:
        orders_table = re.search(
            r"CREATE\s+TABLE(?:\s+IF\s+NOT\s+EXISTS)?\s+orders\s*\((?P<body>.*?);",
            schema,
            flags=re.I | re.S,
        )
        lines_table = re.search(
            r"CREATE\s+TABLE(?:\s+IF\s+NOT\s+EXISTS)?\s+order_lines\s*\((?P<body>.*?);",
            schema,
            flags=re.I | re.S,
        )
        orders_body = orders_table.group("body") if orders_table else ""
        lines_body = lines_table.group("body") if lines_table else ""
        if not orders_table:
            issues.append("data/schema.sql does not create orders")
        else:
            if not re.search(r"(?:order_id[^,\n]*PRIMARY\s+KEY|PRIMARY\s+KEY\s*\(\s*order_id\s*\))", orders_body, flags=re.I):
                issues.append("orders.order_id is not a primary key")
            if not re.search(r"\bstatus\b", orders_body, flags=re.I):
                issues.append("orders.status is missing")
        if not lines_table:
            issues.append("data/schema.sql does not create order_lines")
        else:
            if not re.search(r"REFERENCES\s+orders\s*\(\s*order_id\s*\)", lines_body, flags=re.I):
                issues.append("order_lines.order_id does not reference orders.order_id")
            if not re.search(r"REFERENCES\s+inventory\s*\(\s*sku\s*\)", lines_body, flags=re.I):
                issues.append("order_lines.sku does not reference inventory.sku")
            if not re.search(r"CHECK\s*\([^)]*quantity\s*>\s*0", lines_body, flags=re.I):
                issues.append("order_lines.quantity lacks a positive CHECK constraint")
        if not _handler_reads_dict_bin_location(handler):
            issues.append("dict-style inventory rows do not read canonical bin_location")
        if not _handler_normalizes_tuple_inventory_row(handler):
            issues.append("tuple-style inventory rows are not normalized")
        sqlite_test = snapshot.get("tests/test_sqlite_orders.py", "")
        sqlite_test_lower = sqlite_test.lower()
        if not any(token in sqlite_test for token in ("sqlite3", "TINYWMS_DB")) or "place_order" not in sqlite_test:
            issues.append("tests/test_sqlite_orders.py does not execute the real order path on SQLite")
        if "open_connection" not in sqlite_test or "init_db" not in sqlite_test:
            issues.append(
                "tests/test_sqlite_orders.py must use src.db_adapter.open_connection and "
                "data.init_db.init_db instead of a parallel raw-SQLite adapter"
            )
        if not _has_sqlite_persistence_proof(sqlite_test):
            issues.append(
                "tests/test_sqlite_orders.py must create a temporary schema and assert persisted database rows"
            )
        required_unittest_methods = {
            "test_accepted_order_persists_rows",
            "test_insufficient_inventory_rolls_back",
            "test_unknown_sku_rolls_back",
        }
        missing_unittest_methods = sorted(
            required_unittest_methods - _unittest_case_methods(sqlite_test)
        )
        if missing_unittest_methods:
            issues.append(
                "tests/test_sqlite_orders.py must expose discoverable unittest.TestCase methods: "
                + ", ".join(missing_unittest_methods)
            )
        for alternatives, label in (
            (("success", "accepted", "persists"), "accepted-order persistence"),
            (("insufficient", "shortage"), "insufficient-inventory rollback"),
            (("unknown", "missing_sku"), "unknown-SKU rollback"),
        ):
            if not any(token in sqlite_test_lower for token in alternatives):
                issues.append(f"tests/test_sqlite_orders.py lacks {label} coverage")

    if stage_num >= 12:
        architecture = snapshot.get("docs/architecture.md", "").lower()
        if not (
            "sqlite" in architecture
            and "postgres" in architecture
            and any(token in architecture for token in ("row lock", "for update", "concurrency"))
        ):
            issues.append(
                "docs/architecture.md must say SQLite cannot demonstrate the PostgreSQL row-lock lesson"
            )
    return issues


def _validate_relational_teaching(stage_name: str, snapshot: dict[str, str]) -> None:
    issues = _relational_teaching_issues(stage_name, snapshot)
    if issues:
        raise ValueError(
            f"Stage {stage_name} relational teaching audit failed: " + "; ".join(issues) + "."
        )


def _validate_student_exercises(stage_name: str, snapshot: dict[str, str]) -> None:
    stage_num = _stage_number(stage_name)
    if stage_num is None or stage_num < 7:
        return
    exercises = _extract_markdown_section(snapshot.get("README.md", ""), "## Student exercises")
    for line in exercises.splitlines():
        test_action = re.search(r"\b(?:re-?run|run)\b[^\n]{0,50}\btests?\b", line, flags=re.I)
        if not test_action:
            continue
        visible_action = re.search(
            r"\b(?:inspect|observe|open|curl|print|show|view|tail|query|submit|compare|read|watch)\b",
            line[: test_action.start()],
            flags=re.I,
        )
        optional_check = re.search(r"\boptional(?:ly)?\b", line, flags=re.I)
        if visible_action or optional_check:
            continue
        raise ValueError(
            f"Stage {stage_name} student exercises lead with tests; make visible behavior the result "
            "and mention tests only as an optional check."
        )


def _normalize_student_exercise_section(readme: str) -> str:
    """Repair only test-first exercise wording while preserving the model's lesson content."""
    section = re.search(
        r"(?P<header>## Student exercises\n)(?P<body>.*?)(?=\n## |\Z)",
        readme,
        flags=re.S,
    )
    if section is None:
        return readme

    test_action_pattern = re.compile(
        r"\b(?:re-?run|run)\b[^\n]{0,50}\b(?:the\s+)?tests?\b",
        flags=re.I,
    )
    visible_action_pattern = re.compile(
        r"\b(?:inspect|observe|open|curl|print|show|view|tail|query|submit|compare|read|watch)\b",
        flags=re.I,
    )
    normalized_lines: list[str] = []
    for line in section.group("body").splitlines():
        test_action = test_action_pattern.search(line)
        if (
            test_action is None
            or visible_action_pattern.search(line[: test_action.start()])
            or re.search(r"\boptional(?:ly)?\b", line, flags=re.I)
        ):
            normalized_lines.append(line)
            continue

        replacement = (
            "observe the changed behavior through the lesson's visible interface, "
            "then optionally run the tests"
        )
        prefix = line[: test_action.start()]
        if re.fullmatch(r"\s*(?:\d+[.)]|[-*+])?\s*", prefix):
            replacement = replacement[0].upper() + replacement[1:]
        normalized_lines.append(prefix + replacement + line[test_action.end() :])

    normalized_body = "\n".join(normalized_lines)
    return readme[: section.start("body")] + normalized_body + readme[section.end("body") :]


def _normalize_student_exercises_in_plan(plan: dict[str, Any]) -> dict[str, Any]:
    """Apply the README wording repair to generated stage plans before validation."""
    if not isinstance(plan, dict):
        return plan
    stages = plan.get("stages")
    if not isinstance(stages, list):
        return plan
    for stage in stages:
        if not isinstance(stage, dict):
            continue
        files = stage.get("files")
        if not isinstance(files, list):
            continue
        for item in files:
            if (
                isinstance(item, dict)
                and item.get("path") == "README.md"
                and isinstance(item.get("content"), str)
            ):
                item["content"] = _normalize_student_exercise_section(item["content"])
    return plan


def _normalize_unittest_discovery_source(source: str) -> str:
    """Move top-level test functions into a stdlib-unittest discoverable class."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source
    top_level_tests = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
    ]
    if not top_level_tests:
        return source

    for test in top_level_tests:
        test.args.args.insert(0, ast.arg(arg="self"))
    tree.body = [node for node in tree.body if node not in top_level_tests]

    alias = "_tinywms_unittest"
    import_node = ast.Import(names=[ast.alias(name="unittest", asname=alias)])
    import_index = 1 if tree.body and isinstance(tree.body[0], ast.Expr) and isinstance(
        tree.body[0].value, ast.Constant
    ) and isinstance(tree.body[0].value.value, str) else 0
    while import_index < len(tree.body) and isinstance(tree.body[import_index], ast.ImportFrom) and tree.body[
        import_index
    ].module == "__future__":
        import_index += 1
    tree.body.insert(import_index, import_node)

    existing_names = {
        node.name for node in tree.body if isinstance(node, ast.ClassDef)
    }
    class_name = "TinyWMSGeneratedTests"
    suffix = 2
    while class_name in existing_names:
        class_name = f"TinyWMSGeneratedTests{suffix}"
        suffix += 1
    base_name = "IsolatedAsyncioTestCase" if any(
        isinstance(node, ast.AsyncFunctionDef) for node in top_level_tests
    ) else "TestCase"
    test_class = ast.ClassDef(
        name=class_name,
        bases=[
            ast.Attribute(
                value=ast.Name(id=alias, ctx=ast.Load()),
                attr=base_name,
                ctx=ast.Load(),
            )
        ],
        keywords=[],
        body=top_level_tests,
        decorator_list=[],
    )
    main_guard_index = next(
        (
            index
            for index, node in enumerate(tree.body)
            if isinstance(node, ast.If)
            and isinstance(node.test, ast.Compare)
            and isinstance(node.test.left, ast.Name)
            and node.test.left.id == "__name__"
        ),
        len(tree.body),
    )
    tree.body.insert(main_guard_index, test_class)
    ast.fix_missing_locations(tree)
    return ast.unparse(tree) + "\n"


def _normalize_unittest_tests_in_plan(plan: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(plan, dict):
        return plan
    stages = plan.get("stages")
    if not isinstance(stages, list):
        return plan
    for stage in stages:
        if not isinstance(stage, dict) or not isinstance(stage.get("files"), list):
            continue
        for item in stage["files"]:
            if not isinstance(item, dict):
                continue
            path = item.get("path")
            content = item.get("content")
            if (
                isinstance(path, str)
                and path.startswith("tests/test_")
                and path.endswith(".py")
                and isinstance(content, str)
            ):
                item["content"] = _normalize_unittest_discovery_source(content)
    return plan


def _normalize_forward_teaching_continuity(
    plan: dict[str, Any],
    stage_name: str,
) -> dict[str, Any]:
    """Restore small cumulative teaching notes that must survive later README/doc rewrites."""
    stage_num = _stage_number(stage_name)
    if stage_num is None or not isinstance(plan, dict):
        return plan
    stages = plan.get("stages")
    if not isinstance(stages, list):
        return plan
    for stage in stages:
        if not isinstance(stage, dict) or stage.get("name") != stage_name:
            continue
        files = stage.get("files")
        if not isinstance(files, list):
            continue
        for item in files:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if not isinstance(content, str):
                continue
            if item.get("path") == "src/lambda_inventory.py" and stage_num in (11, 12):
                item["content"] = _adapt_order_handler_for_sqlite(content)
                content = item["content"]
            if item.get("path") == "tests/test_concurrency.py" and stage_num == 12:
                item["content"] = _project_prepublisher_concurrency_test(content)
                content = item["content"]
            if item.get("path") == "docs/data-contracts.md" and stage_num >= 11:
                item["content"] = content.replace(
                    "`bin_location` maps to the SQL `bin` column in the lesson schema.",
                    "`bin_location` maps to the SQL `bin_location` column in the lesson schema.",
                )
                content = item["content"]
            if stage_num < 12:
                continue
            if item.get("path") == "README.md" and "node --test tests/test_web_app.js" not in content:
                run_tests = "## Run tests\n"
                if run_tests in content:
                    content = content.replace(
                        run_tests,
                        run_tests + "```bash\nnode --test tests/test_web_app.js\n```\n\n",
                        1,
                    )
                    item["content"] = content
            if item.get("path") != "docs/architecture.md":
                continue
            required = "SQLite cannot demonstrate the PostgreSQL row-lock lesson"
            if required not in content:
                item["content"] = (
                    content.rstrip()
                    + "\n\n## SQLite concurrency boundary\n"
                    + required
                    + "; use PostgreSQL and `SELECT ... FOR UPDATE` for the concurrency demonstration.\n"
                )
    return plan


def _adapt_order_handler_for_sqlite(source: str) -> str:
    """Route Stage 11/12 cursors through the adapter without introducing later publishers."""
    tree = ast.parse(source, filename="src/lambda_inventory.py")
    if any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "_cursor_for_connection"
        for node in tree.body
    ):
        return source

    class CursorProjection(ast.NodeTransformer):
        def visit_Call(self, node: ast.Call) -> ast.AST:
            node = self.generic_visit(node)
            assert isinstance(node, ast.Call)
            if (
                isinstance(node.func, ast.Attribute)
                and node.func.attr == "cursor"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "connection"
            ):
                return ast.Call(
                    func=ast.Name(id="_cursor_for_connection", ctx=ast.Load()),
                    args=[ast.Name(id="connection", ctx=ast.Load())],
                    keywords=[],
                )
            return node

    projected = CursorProjection().visit(tree)
    assert isinstance(projected, ast.Module)
    helper = ast.parse(
        "def _cursor_for_connection(connection):\n"
        "    cursor = connection.cursor()\n"
        "    if connection.__class__.__module__ == 'sqlite3':\n"
        "        from src.db_adapter import SQLiteCursorAdapter\n"
        "        return SQLiteCursorAdapter(cursor)\n"
        "    return cursor\n"
    ).body[0]
    first_function = next(
        (
            index
            for index, node in enumerate(projected.body)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ),
        len(projected.body),
    )
    projected.body.insert(first_function, helper)
    ast.fix_missing_locations(projected)
    return ast.unparse(projected) + "\n"


def _project_prepublisher_concurrency_test(source: str) -> str:
    """Remove Stage 13/14 publisher fixtures from the Stage 12 concurrency proof."""
    tree = ast.parse(source, filename="tests/test_concurrency.py")

    def names(node: ast.AST) -> set[str]:
        return {item.id for item in ast.walk(node) if isinstance(item, ast.Name)}

    class PrePublisherProjection(ast.NodeTransformer):
        def visit_ClassDef(self, node: ast.ClassDef) -> ast.AST | None:
            if node.name in {"FakeSqsClient", "FakeEventBridgeClient"}:
                return None
            if node.name == "ZeroRowcountCursor":
                replacement = ast.parse(
                    "class ZeroRowcountCursor(FakeCursor):\n"
                    "    def execute(self, sql, params=None):\n"
                    "        if sql.startswith('UPDATE inventory SET quantity = quantity -'):\n"
                    "            self.state['sql'].append((sql, params))\n"
                    "            self.rowcount = 0\n"
                    "            return\n"
                    "        return super().execute(sql, params)\n"
                ).body[0]
                assert isinstance(replacement, ast.ClassDef)
                return replacement
            return self.generic_visit(node)

        def visit_Assign(self, node: ast.Assign) -> ast.AST | None:
            assigned = {
                target.id
                for target in node.targets
                if isinstance(target, ast.Name)
            }
            if assigned & {"sqs", "events"}:
                return None
            return self.generic_visit(node)

        def visit_Expr(self, node: ast.Expr) -> ast.AST | None:
            node = self.generic_visit(node)
            assert isinstance(node, ast.Expr)
            if names(node) & {"sqs", "events"}:
                return None
            return node

        def visit_Call(self, node: ast.Call) -> ast.AST:
            node = self.generic_visit(node)
            assert isinstance(node, ast.Call)
            node.keywords = [
                keyword
                for keyword in node.keywords
                if keyword.arg not in {"sqs_client", "eventbridge_client"}
            ]
            return node

        def visit_With(self, node: ast.With) -> ast.AST | list[ast.stmt] | None:
            node = self.generic_visit(node)
            assert isinstance(node, ast.With)
            obsolete_patch = any(
                isinstance(item.context_expr, ast.Call)
                and isinstance(item.context_expr.func, ast.Attribute)
                and item.context_expr.func.attr == "patch"
                and any(
                    isinstance(argument, ast.Constant)
                    and argument.value == "tests.test_concurrency.FakeConnection"
                    for argument in item.context_expr.args
                )
                for item in node.items
            )
            return node.body if obsolete_patch else node

    projected = PrePublisherProjection().visit(tree)
    assert isinstance(projected, ast.Module)
    ast.fix_missing_locations(projected)
    result = ast.unparse(projected) + "\n"
    forbidden = ("FakeSqsClient", "FakeEventBridgeClient", "sqs_client=", "eventbridge_client=")
    remaining = [token for token in forbidden if token in result]
    if remaining:
        raise ValueError(f"Could not project Stage 12 concurrency test before publishers: {remaining}.")
    return result


def _evolve_rds_continuity_test(source: str) -> str:
    """Keep the Stage 9 proof meaningful without freezing later documentation prose."""
    del source
    return """from __future__ import annotations

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / 'deploy' / 'rds' / 'README.md'
TEMPLATE = ROOT / 'infra' / 'rds.yaml'
ARCH = ROOT / 'docs' / 'architecture.md'
CONTRACTS = ROOT / 'docs' / 'data-contracts.md'


class RdsDeploymentTests(unittest.TestCase):
    def test_required_files_exist(self):
        for path in [README, TEMPLATE, ARCH, CONTRACTS]:
            self.assertTrue(path.exists(), path)

    def test_readme_has_required_command_flow(self):
        text = README.read_text(encoding='utf-8')
        for heading in ('## Deploy', '## Resolve outputs', '## Verify', '## Destroy'):
            self.assertIn(heading, text)
        self.assertLess(text.index('## Deploy'), text.index('## Resolve outputs'))
        self.assertLess(text.index('## Resolve outputs'), text.index('## Verify'))
        self.assertLess(text.index('## Verify'), text.index('## Destroy'))
        for token in ('aws cloudformation describe-stacks', 'DbEndpointAddress', 'DbEndpointPort', 'psql'):
            self.assertIn(token, text)

    def test_template_has_nonempty_rds_resources_and_outputs(self):
        text = TEMPLATE.read_text(encoding='utf-8')
        for token in (
            'Type: AWS::RDS::DBInstance', 'Type: AWS::RDS::DBSubnetGroup',
            'DbEndpointAddress', 'DbEndpointPort', 'SubnetIds: !Ref DbSubnetIds', 'NoEcho: true',
        ):
            self.assertIn(token, text)
        self.assertNotIn('example.invalid', text)
        self.assertNotIn('123456789012', text)

    def test_architecture_preserves_the_managed_rds_shift(self):
        text = ARCH.read_text(encoding='utf-8').lower()
        for token in ('rds', 'managed', 'deployment wrapper', 'sqlite'):
            self.assertIn(token, text)

    def test_data_contracts_preserve_the_hosting_and_column_contract(self):
        text = CONTRACTS.read_text(encoding='utf-8').lower()
        for token in ('self-managed', 'rds', 'bin_location'):
            self.assertIn(token, text)


if __name__ == '__main__':
    unittest.main()
"""


def _evolve_relational_test_for_orders(source: str) -> str:
    """At Stage 11, evolve the Stage 8 schema proof along with the schema."""
    source = source.replace(
        "def test_schema_uses_bin_location(self):",
        "def test_schema_adds_order_tables_without_renaming_inventory_bin(self):",
    )
    source = source.replace(
        "        self.assertNotIn('orders (', schema.lower())\n"
        "        self.assertNotIn('order_lines', schema.lower())\n",
        "        self.assertIn('create table orders (', schema.lower())\n"
        "        self.assertIn('create table order_lines (', schema.lower())\n",
    )
    # Any other phrasing of "no order tables yet" becomes the matching positive assertion.
    source = re.sub(
        r"self\.assertNotIn\((['\"])((?:create table\s+)?order(?:s|_lines)\b[^'\"]*)\1,\s*(schema(?:\.lower\(\))?)\)",
        lambda match: f"self.assertIn({match.group(1)}{match.group(2)}{match.group(1)}, {match.group(3)})",
        source,
        flags=re.IGNORECASE,
    )
    return source


def _forward_continuity_overlay(
    stage_name: str,
    baseline_files: dict[str, str] | None,
) -> dict[str, str]:
    """Evolve inherited proofs exactly where their lesson contract changes."""
    baseline = baseline_files or {}
    overlay: dict[str, str] = {}
    stage_num = _stage_number(stage_name)
    if stage_num is not None and stage_num >= 10 and "tests/test_rds_deployment.py" in baseline:
        evolved_rds = _evolve_rds_continuity_test(baseline["tests/test_rds_deployment.py"])
        if evolved_rds != baseline["tests/test_rds_deployment.py"]:
            overlay["tests/test_rds_deployment.py"] = evolved_rds
    if stage_num is not None and stage_num >= 11 and "tests/test_relational_persistence.py" in baseline:
        evolved_relational = _evolve_relational_test_for_orders(
            baseline["tests/test_relational_persistence.py"]
        )
        if evolved_relational != baseline["tests/test_relational_persistence.py"]:
            overlay["tests/test_relational_persistence.py"] = evolved_relational
    return overlay


def _course_demo_runbook() -> str:
    """Build the final runbook around observable course behavior, in lesson order."""
    sessions = [
        ("01-json-backbone", "Partly manual", "Print and inspect the canonical inventory JSON.",
         "python3 src/inventory_cli.py data/inventory.json list\npython3 src/inventory_cli.py data/inventory.json dump",
         "data/inventory.json", "tests/test_inventory_cli.py"),
        ("02-linux-visible", "Partly manual", "Observe environment variables, stdin, stdout, and exit status.",
         "python3 src/linux_visible.py env\nTINYWMS_DEMO=visible python3 src/linux_visible.py env\nprintf 'hello from stdin\\n' | python3 src/linux_visible.py echo\npython3 src/linux_visible.py fail; echo \"exit code: $?\"",
         "src/linux_visible.py", "tests/test_linux_visible.py"),
        ("02-linux-visible", "Partly manual", "Run a long-lived process and watch its visible output file.",
         "python3 src/inventory_watcher.py data/inventory.json /tmp/tinywms-watch.log\ntail -f /tmp/tinywms-watch.log",
         "src/inventory_watcher.py", "tests/test_linux_visible.py"),
        ("03-pi-http-server", "Partly manual", "Cross the first HTTP boundary and inspect response headers and JSON.",
         "PYTHONPATH=src python3 src/http_server.py\ncurl -i http://127.0.0.1:8000/inventory",
         "src/http_server.py", "tests/test_http_server.py"),
        ("04-browser", "Partly manual", "Render the inventory JSON in a plain browser page.",
         "PYTHONPATH=src python3 -m http.server --directory src/web 8081\n# Open http://127.0.0.1:8081/ in a browser.",
         "src/web/index.html", "tests/test_web_app.js"),
        ("05-ec2-deployment", "Manual only", "Identify what moves unchanged from Raspberry Pi Linux to EC2 Linux.",
         "sed -n '1,220p' deploy/ec2/README.md\nbash -n deploy/ec2/run_inventory_server.sh",
         "deploy/ec2/README.md", "tests/test_ec2_deployment_files.py"),
        ("06-lambda", "Partly manual", "Invoke the Lambda-shaped inventory boundary and inspect its JSON envelope.",
         "PYTHONPATH=. python3 -c \"import json; from src.lambda_inventory import handler; print(json.dumps(handler({'queryStringParameters': {'demo': 'local-json'}}, None), indent=2))\"",
         "src/lambda_inventory.py", "tests/test_lambda_inventory.py"),
        ("07-api-gateway", "Manual only", "Trace the HTTP route from API Gateway to the Lambda handler.",
         "sed -n '1,240p' infra/api-gateway.yaml\nsed -n '1,220p' deploy/api-gateway/README.md",
         "infra/api-gateway.yaml", "tests/test_api_gateway_files.py"),
        ("08-relational-persistence", "Partly manual", "Create the SQLite classroom database from the visible schema and seed.",
         "TINYWMS_DB=sqlite TINYWMS_SQLITE_PATH=data/tinywms.db python3 -m data.init_db",
         "data/schema.sql", "tests/test_relational_persistence.py"),
        ("08-relational-persistence", "Partly manual", "Query relational rows and compare them with the JSON records.",
         "python3 -c \"import sqlite3, json; print(json.dumps(sqlite3.connect('data/tinywms.db').execute('SELECT * FROM inventory ORDER BY sku').fetchall(), indent=2))\"",
         "data/seed.sql", "tests/test_sql_export.py"),
        ("09-rds", "Manual only", "Compare self-managed database work with the managed RDS boundary.",
         "sed -n '1,260p' deploy/rds/README.md\nsed -n '1,260p' infra/rds.yaml",
         "deploy/rds/README.md", "tests/test_rds_deployment.py"),
        ("10-lambda-rds", "Partly manual", "Follow the Lambda inventory query from JSON response to PostgreSQL rows.",
         "sed -n '1,260p' src/lambda_inventory.py\nsed -n '1,220p' docs/data-contracts.md",
         "tests/test_lambda_inventory.py", "tests/test_lambda_inventory.py"),
        ("11-orders", "Partly manual", "Use one browser page to view inventory, submit an order, and see inventory refresh.",
         "TINYWMS_DB=sqlite TINYWMS_SQLITE_PATH=data/tinywms.db python3 -m data.init_db\nPYTHONPATH=src python3 src/http_server.py\n# Open the server URL in a browser and submit the visible order JSON.",
         "src/web/index.html", "tests/test_http_order_flow.py"),
        ("11-orders", "Partly manual", "Submit visible order JSON with curl, then observe the changed inventory.",
         "curl -s -H 'Content-Type: application/json' -d '{\"order_id\":\"ORD-DEMO\",\"lines\":[{\"sku\":\"SKU-1001\",\"quantity\":1}]}' http://127.0.0.1:8000/orders\ncurl -s http://127.0.0.1:8000/inventory",
         "src/http_server.py", "tests/test_http_order_flow.py"),
        ("12-concurrency", "Partly manual", "Run overlapping order attempts and compare SQLite with PostgreSQL row locking.",
         "python3 src/concurrency_demo.py",
         "tests/test_concurrency.py", "tests/test_concurrency.py"),
        ("13-sqs", "Partly manual", "Inspect the per-line pick-work command JSON sent after commit.",
         "python3 -m json.tool data/pick-work.json\nsed -n '1,260p' src/sqs_consumer.py",
         "tests/test_sqs_consumer.py", "tests/test_sqs_consumer.py"),
        ("14-domain-events", "Partly manual", "Compare the imperative SQS command with the descriptive OrderPlaced event.",
         "sed -n '1,280p' docs/data-contracts.md\nsed -n '1,260p' infra/events.yaml",
         "tests/test_event_consumers.py", "tests/test_event_consumers.py"),
        ("15-pick-ticket-worker", "Manual only", "Run the long-lived worker against a configured queue and watch ticket output.",
         "python3 src/pick_ticket_worker.py \"$PICK_WORK_QUEUE_URL\" pick-tickets.txt --state-file pick-ticket-worker-state.json\ntail -f pick-tickets.txt",
         "tests/test_pick_ticket_worker.py", "tests/test_pick_ticket_worker.py"),
        ("15-pick-ticket-worker", "Manual only", "Operate the worker as a user service and inspect its logs.",
         "systemctl --user status tinywms-pick-ticket-worker\njournalctl --user -u tinywms-pick-ticket-worker.service -f",
         "deploy/pick-ticket-worker/README.md", "tests/test_pick_ticket_worker.py"),
        ("16-callback-demo", "Partly manual", "Follow one accepted order across HTTP, queue receipt, worker callback, and ticket file.",
         "sed -n '1,260p' docs/end-to-end.md\ntail -f pick-tickets.txt",
         "docs/end-to-end.md", "tests/test_callback_integration.py"),
        ("17-container-worker", "Partly manual", "Build the same worker code into a container image.",
         "docker build -t tinywms-pick-ticket-worker -f src/Dockerfile .",
         "deploy/container-worker/README.md", "tests/test_container_worker.py"),
        ("17-container-worker", "Manual only", "Run the container with durable ticket and idempotency files mounted.",
         "docker run --rm -e PICK_WORK_QUEUE_URL=\"$PICK_WORK_QUEUE_URL\" -v \"$PWD/data:/state\" tinywms-pick-ticket-worker \"$PICK_WORK_QUEUE_URL\" /state/pick-tickets.txt --state-file /state/pick-ticket-worker-state.json --once",
         "deploy/container-worker/README.md", "tests/test_container_worker.py"),
        ("18-aws-deployment", "Manual only", "Inspect how Lambda, API Gateway, RDS, SQS, EventBridge, and IAM are assembled.",
         "sed -n '1,320p' infra/template.yaml\nsed -n '1,320p' deploy/aws/README.md",
         "infra/template.yaml", "tests/test_deployment_wiring.py"),
        ("18-aws-deployment", "Manual only", "Package, deploy, verify, and later destroy the real application stack using the documented commands.",
         "sed -n '1,320p' deploy/aws/README.md\n# Follow its package/deploy steps, then curl the resolved API URL.",
         "deploy/aws/README.md", "tests/test_aws_deployment_files.py"),
        ("19-git-history", "Partly manual", "Compare two stage directories without inventing repository tags.",
         "git diff --no-index ../18-aws-deployment ../19-git-history || true\nsed -n '1,260p' docs/git-history.md",
         "docs/git-history.md", "tests/test_deployment_wiring.py"),
        ("20-final-walkthrough", "Partly manual", "Repeat the complete local order journey, then use the boundary guide for cloud demonstrations.",
         "PYTHONPATH=src python3 src/http_server.py\ncurl -s http://127.0.0.1:8000/inventory\nnode --test tests/test_web_app.js",
         "docs/end-to-end.md", "tests/test_demo_runbook.py"),
    ]
    blocks = [
        "# TinyWMS demo runbook\n\n"
        "Run each session from its named stage directory. Commands lead with visible behavior; "
        "the listed test is an optional safety check after the demonstration."
    ]
    for number, (stage, work_type, goal, commands, artifact, optional_test) in enumerate(sessions, 1):
        blocks.append(
            f"## Session {number}\n"
            f"**Backing stage:** {stage}\n"
            f"**Work type:** {work_type}\n\n"
            f"Goal: {goal}\n\n"
            f"```bash\n{commands}\n```\n\n"
            f"Observe the command output or interface before continuing. Optional safety check: "
            f"`{optional_test}`.\n\n"
            f"Artifact link:\n- `{artifact}`"
        )
    return "\n\n".join(blocks) + "\n"


def _validate_concurrency_demo(stage_name: str, snapshot: dict[str, str]) -> None:
    if stage_name != "12-concurrency":
        return
    demo = snapshot.get("src/concurrency_demo.py", "")
    demo_lower = demo.lower()
    issues: list[str] = []
    if not demo:
        issues.append("missing src/concurrency_demo.py")
    if not any(token in demo_lower for token in ("thread", "barrier", "concurrent.futures")):
        issues.append("concurrency demo does not launch overlapping attempts")
    if "print(" not in demo or not any(token in demo_lower for token in ("place_order", "handler")):
        issues.append("concurrency demo does not run the real order path and print outcomes")
    if "python3 src/concurrency_demo.py" not in snapshot.get("README.md", ""):
        issues.append("README does not document python3 src/concurrency_demo.py")
    if issues:
        raise ValueError(f"Stage {stage_name} concurrency demonstration audit failed: " + "; ".join(issues) + ".")


def _validate_web_node_test(stage_name: str, snapshot: dict[str, str]) -> None:
    stage_num = _stage_number(stage_name)
    if stage_num is None or stage_num < 7:
        return
    source = snapshot.get("tests/test_web_app.js", "")
    if not source:
        raise ValueError(f"Stage {stage_name} is missing tests/test_web_app.js.")
    if "node:test" not in source or "app.js" not in source:
        raise ValueError(
            f"Stage {stage_name} tests/test_web_app.js must use node:test against the plain web app."
        )
    if "node --test tests/test_web_app.js" not in snapshot.get("README.md", ""):
        raise ValueError(
            f"Stage {stage_name} README does not document node --test tests/test_web_app.js."
        )


def _validate_operations_teaching(stage_name: str, snapshot: dict[str, str]) -> None:
    stage_num = _stage_number(stage_name)
    if stage_num is None:
        return
    issues: list[str] = []
    if stage_num >= 15:
        service_paths = (
            "deploy/pick-ticket-worker/tinywms-pick-ticket-worker.service.in",
            "deploy/pick-ticket-worker/install_user_service.sh",
            "deploy/pick-ticket-worker/environment.example",
            "deploy/pick-ticket-worker/README.md",
        )
        issues.extend(f"missing {path}" for path in service_paths if path not in snapshot)
        unit = snapshot.get(service_paths[0], "")
        installer = snapshot.get(service_paths[1], "")
        guide = snapshot.get(service_paths[3], "")
        for token in ("[Unit]", "[Service]", "[Install]", "ExecStart=", "Restart=", "EnvironmentFile="):
            if token not in unit:
                issues.append(f"systemd worker template is missing {token}")
        if "--once" in unit:
            issues.append("systemd worker incorrectly runs bounded --once mode")
        if not all(token in installer for token in ("systemctl", "daemon-reload", "tinywms-pick-ticket-worker")):
            issues.append("worker service installer does not install/reload the user unit")
        for token in ("systemctl --user", "journalctl --user", "tail -f"):
            if token not in guide:
                issues.append(f"worker service guide is missing {token}")
    if stage_num >= 17:
        container_guide = snapshot.get("deploy/container-worker/README.md", "")
        if "docker run" not in container_guide:
            issues.append("container worker guide has no docker run command")
        if not any(token in container_guide for token in ("--mount", "-v ", "--volume")):
            issues.append("container worker guide does not mount durable host state")
        for token in ("pick-tickets", "processed", "PICK_WORK_QUEUE_URL", "--once"):
            if token not in container_guide:
                issues.append(f"container worker guide is missing {token}")
    if stage_num >= 19:
        history = snapshot.get("docs/git-history.md", "")
        if "git diff --no-index" not in history:
            issues.append("docs/git-history.md does not compare stage directories honestly")
        if re.search(r"git\s+(?:checkout|show|diff)\s+stage-", history):
            issues.append("docs/git-history.md assumes milestone tags that the published repository does not have")
    if stage_num >= 20:
        runbook = snapshot.get("docs/demo-runbook.md", "")
        session_numbers = re.findall(r"^##\s+Session\s+(\d+)\b", runbook, flags=re.M)
        missing_sessions = [
            str(number)
            for number in range(1, 27)
            if not re.search(rf"^##\s+Session\s+{number}\b", runbook, flags=re.M)
        ]
        if missing_sessions:
            issues.append("docs/demo-runbook.md is missing sessions " + ", ".join(missing_sessions))
        if session_numbers != [str(number) for number in range(1, 27)]:
            issues.append("docs/demo-runbook.md must contain exactly one ordered heading for Sessions 1-26")
        for token in ("Manual only", "Partly manual", "TINYWMS_DB=sqlite", "systemctl", "docker run", "pick-ticket"):
            if token not in runbook:
                issues.append(f"docs/demo-runbook.md is missing {token}")
        runbook_test = snapshot.get("tests/test_demo_runbook.py", "")
        if "demo-runbook.md" not in runbook_test or "range(1, 27)" not in runbook_test:
            issues.append("tests/test_demo_runbook.py does not enforce all 26 sessions")
    if issues:
        raise ValueError(
            f"Stage {stage_name} operations teaching audit failed: " + "; ".join(issues) + "."
        )


def _validate_test_portability(stage_name: str, snapshot: dict[str, str]) -> None:
    """Catch tests that work only in their originating lesson or interpreter."""
    readme = snapshot.get("README.md", "")
    source_modules = {
        PurePosixPath(path).stem
        for path in snapshot
        if path.startswith("src/") and path.endswith(".py")
    }
    bare_imports: list[str] = []
    forbidden_test_dependencies = {"boto3", "botocore", "psycopg", "psycopg2", "yaml"}
    for path, content in snapshot.items():
        if not path.startswith("tests/test_") or not path.endswith(".py"):
            continue
        final_readme_test = stage_name == "20-final-walkthrough" and path in {
            "tests/test_blueprint.py",
            "tests/test_end_to_end_walkthrough.py",
        }
        reads_root_readme = bool(
            re.search(r"\bPath\(\s*['\"]README\.md['\"]\s*\)", content)
            or re.search(r"\bROOT\s*/\s*['\"]README\.md['\"]", content)
            or re.search(r"\.parents\s*\[[^\]]+\]\s*/\s*['\"]README\.md['\"]", content)
        )
        if reads_root_readme and not final_readme_test:
            raise ValueError(
                f"Stage {stage_name} test {path} reads the changing root README.md; "
                "assert a stable component, contract, or lesson-specific guide instead."
            )
        if re.search(r"def\s+test_(?:placeholder|todo|stub)(?:_|\s*\()", content, flags=re.I):
            raise ValueError(
                f"Stage {stage_name} test {path} contains a placeholder test name; rename it for the "
                "behavior it proves (for example test_schema_uses_bin_location) and replace any pass or "
                "assert True body with assertions against the real artifact."
            )
        if "unittest.mock." in content and not re.search(
            r"^(?:from\s+unittest\s+import\s+mock|import\s+unittest\.mock)\b",
            content,
            flags=re.M,
        ):
            raise ValueError(
                f"Stage {stage_name} test {path} uses unittest.mock without importing it explicitly."
            )
        try:
            test_tree = ast.parse(content, filename=path)
        except SyntaxError:
            test_tree = None
        imported_dependencies: set[str] = set()
        if test_tree is not None:
            for node in ast.walk(test_tree):
                if isinstance(node, ast.Import):
                    imported_dependencies.update(alias.name.split(".", 1)[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported_dependencies.add(node.module.split(".", 1)[0])
                    if not node.module.startswith("src."):
                        continue
                    source_path = node.module.replace(".", "/") + ".py"
                    source = snapshot.get(source_path)
                    if source is None:
                        continue
                    try:
                        source_tree = ast.parse(source, filename=source_path)
                    except SyntaxError:
                        continue
                    exports: set[str] = set()
                    for statement in source_tree.body:
                        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                            exports.add(statement.name)
                        elif isinstance(statement, (ast.Assign, ast.AnnAssign)):
                            targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
                            for target in targets:
                                if isinstance(target, ast.Name):
                                    exports.add(target.id)
                        elif isinstance(statement, (ast.Import, ast.ImportFrom)):
                            for alias in statement.names:
                                exports.add(alias.asname or alias.name.split(".", 1)[0])
                    missing_exports = sorted(
                        alias.name for alias in node.names if alias.name != "*" and alias.name not in exports
                    )
                    if missing_exports:
                        raise ValueError(
                            f"Stage {stage_name} test {path} imports names {missing_exports} that "
                            f"{source_path} does not export."
                        )

            imported_source_paths = {
                node.module.replace(".", "/") + ".py"
                for node in ast.walk(test_tree)
                if isinstance(node, ast.ImportFrom)
                and node.module
                and node.module.startswith("src.")
                and node.module.replace(".", "/") + ".py" in snapshot
            }
            source_error_texts: list[str] = []
            for source_path in imported_source_paths:
                try:
                    source_tree = ast.parse(snapshot[source_path], filename=source_path)
                except SyntaxError:
                    continue
                source_error_texts.extend(
                    node.value
                    for node in ast.walk(source_tree)
                    if isinstance(node, ast.Constant) and isinstance(node.value, str)
                )
            for node in ast.walk(test_tree):
                if (
                    not isinstance(node, ast.Call)
                    or not isinstance(node.func, ast.Attribute)
                    or node.func.attr != "assertRaisesRegex"
                    or len(node.args) < 2
                    or not isinstance(node.args[1], ast.Constant)
                    or not isinstance(node.args[1].value, str)
                    or not source_error_texts
                ):
                    continue
                pattern = node.args[1].value
                try:
                    matches_source_error = any(re.search(pattern, text) for text in source_error_texts)
                except re.error:
                    continue
                if not matches_source_error:
                    raise ValueError(
                        f"Stage {stage_name} test {path} expects exception text {pattern!r}, but that "
                        "text cannot match any emitted error in its imported source module."
                    )
        forbidden_imports = sorted(imported_dependencies & forbidden_test_dependencies)
        if forbidden_imports:
            raise ValueError(
                f"Stage {stage_name} test {path} imports optional runtime dependencies {forbidden_imports}; "
                "safe local tests must use standard-library text inspection or injected fakes."
            )
        for module in source_modules:
            if re.search(
                rf"^(?:import\s+{re.escape(module)}\b|from\s+{re.escape(module)}\s+import\b)",
                content,
                flags=re.M,
            ):
                bare_imports.append(f"{path}:{module}")

    if bare_imports and "PYTHONPATH=src python3 -m unittest" not in readme:
        raise ValueError(
            f"Stage {stage_name} tests import modules directly from src ({bare_imports}); "
            "the README test command must set PYTHONPATH=src."
        )


def _validate_python_syntax(stage_name: str, snapshot: dict[str, str]) -> None:
    """Reject generated Python that cannot even be imported by the documented test suite."""
    errors: list[str] = []
    for path, content in snapshot.items():
        if not path.endswith(".py"):
            continue
        try:
            ast.parse(content, filename=path)
        except SyntaxError as error:
            location = f"line {error.lineno}" if error.lineno is not None else "unknown line"
            errors.append(f"{path} ({location}: {error.msg})")
    if errors:
        raise ValueError(
            f"Stage {stage_name} contains invalid Python syntax: " + "; ".join(errors) + "."
        )


def _has_flushed_readiness_output(source: str) -> bool:
    """Recognize explicit, readable readiness flushing in the teaching server."""
    return "flush=True" in source or bool(re.search(r"(?:sys\.)?stdout\.flush\s*\(", source))


def _has_sqs_fake_client_behavior_tests(source: str) -> bool:
    """Recognize behavior-focused SQS tests without prescribing exact test names."""
    lowered = source.lower()
    failure_proof = any(
        token in lowered
        for token in (
            "failure",
            "fail",
            "error",
            "raises",
            "exception",
            "does_not_delete",
            "does not delete",
            "without_delete",
        )
    )
    multiple_proof = any(
        token in lowered
        for token in (
            "multiple",
            "two_messages",
            "two messages",
            "each_message",
            "every_message",
            "all_messages",
            "several",
        )
    ) or lowered.count("receipthandle") >= 2
    return (
        "receive_message" in lowered
        and "delete_message" in lowered
        and failure_proof
        and multiple_proof
        and len(re.findall(r"\bdef\s+test_", lowered)) >= 3
    )


def _has_send_message_inside_loop(source: str) -> bool:
    """Recognize per-item publishing without prescribing collection or variable names."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False

    class SendInLoopVisitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.loop_depth = 0
            self.found = False

        def visit_For(self, node: ast.For) -> None:
            self.loop_depth += 1
            self.generic_visit(node)
            self.loop_depth -= 1

        def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
            self.loop_depth += 1
            self.generic_visit(node)
            self.loop_depth -= 1

        def visit_Call(self, node: ast.Call) -> None:
            if (
                self.loop_depth
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "send_message"
            ):
                self.found = True
            self.generic_visit(node)

    visitor = SendInLoopVisitor()
    visitor.visit(tree)
    return visitor.found


def _worker_uses_sqs_receive_delete(worker: str, consumer: str) -> bool:
    """Accept direct SQS calls or explicit reuse of the already-tested consumer component."""
    direct = ".receive_message(" in worker and ".delete_message(" in worker
    delegated = (
        "consume_messages(" in worker
        and re.search(r"def\s+consume_messages\s*\(", consumer) is not None
        and ".receive_message(" in consumer
        and ".delete_message(" in consumer
    )
    return direct or delegated


def _callback_invokes_worker_consumption(
    callback_test: str,
    worker: str,
    consumer: str,
) -> bool:
    """Recognize direct consumer use or invocation through the real worker entry point."""
    try:
        tree = ast.parse(callback_test)
    except SyntaxError:
        return False

    called_names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    called_attributes = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    consumer_names: set[str] = set()
    worker_names: set[str] = set()
    imported_consumer_modules: set[str] = set()
    imported_worker_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for imported in node.names:
                local_name = imported.asname or imported.name
                if module.endswith("sqs_consumer") and imported.name == "consume_messages":
                    consumer_names.add(local_name)
                if module.endswith("pick_ticket_worker") and imported.name in {"run_worker", "main"}:
                    worker_names.add(local_name)
        elif isinstance(node, ast.Import):
            for imported in node.names:
                local_name = imported.asname or imported.name.split(".")[-1]
                if imported.name.endswith("sqs_consumer"):
                    imported_consumer_modules.add(local_name)
                if imported.name.endswith("pick_ticket_worker"):
                    imported_worker_modules.add(local_name)

    direct_consumer_call = bool(consumer_names & called_names) or (
        bool(imported_consumer_modules) and "consume_messages" in called_attributes
    )
    if direct_consumer_call and re.search(r"def\s+consume_messages\s*\(", consumer):
        return True

    worker_call = bool(worker_names & called_names) or (
        bool(imported_worker_modules) and bool({"run_worker", "main"} & called_attributes)
    )
    return worker_call and _worker_uses_sqs_receive_delete(worker, consumer)


def _worker_has_durable_idempotency_state(source: str) -> bool:
    """Recognize persisted command IDs without prescribing a variable name."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False

    lowered = source.lower()
    if "command_id" not in lowered:
        return False

    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    string_literals = "\n".join(
        node.value.lower()
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    )

    sqlite_connections: list[ast.Call] = []
    for call in calls:
        if (
            isinstance(call.func, ast.Attribute)
            and call.func.attr == "connect"
            and isinstance(call.func.value, ast.Name)
            and call.func.value.id == "sqlite3"
        ):
            sqlite_connections.append(call)

    has_non_memory_sqlite = False
    for call in sqlite_connections:
        if not call.args:
            continue
        target = call.args[0]
        if isinstance(target, ast.Constant) and isinstance(target.value, str):
            has_non_memory_sqlite = target.value.strip().lower() != ":memory:"
        else:
            # A path/config expression is durable unless the source explicitly hard-codes
            # SQLite's in-memory sentinel as the connection target.
            has_non_memory_sqlite = True
        if has_non_memory_sqlite:
            break

    has_commit = any(
        isinstance(call.func, ast.Attribute) and call.func.attr == "commit"
        for call in calls
    )
    has_idempotency_read = bool(
        re.search(r"\bselect\b[^\n]*(?:command_id|processed|idemp)", string_literals)
    )
    has_idempotency_write = bool(
        re.search(r"\b(?:insert|replace|update)\b[^\n]*(?:command_id|processed|idemp)", string_literals)
    )
    if has_non_memory_sqlite and has_commit and has_idempotency_read and has_idempotency_write:
        return True

    # Also allow a deliberately simple file-backed ledger, which is useful in this
    # teaching repository. Require both a read and a write so a ticket output file
    # containing command_id is not mistaken for idempotency state.
    has_file_read = any(
        isinstance(call.func, ast.Attribute) and call.func.attr in {"read_text", "read_bytes"}
        for call in calls
    )
    has_file_write = any(
        isinstance(call.func, ast.Attribute) and call.func.attr in {"write_text", "write_bytes"}
        for call in calls
    )
    for call in calls:
        if not (
            (isinstance(call.func, ast.Name) and call.func.id == "open")
            or (isinstance(call.func, ast.Attribute) and call.func.attr == "open")
        ):
            continue
        mode: str | None = None
        if len(call.args) >= 2 and isinstance(call.args[1], ast.Constant):
            mode = call.args[1].value if isinstance(call.args[1].value, str) else None
        elif isinstance(call.func, ast.Attribute) and call.args and isinstance(call.args[0], ast.Constant):
            mode = call.args[0].value if isinstance(call.args[0].value, str) else None
        for keyword in call.keywords:
            if keyword.arg == "mode" and isinstance(keyword.value, ast.Constant):
                mode = keyword.value.value if isinstance(keyword.value.value, str) else mode
        if mode is None or "r" in mode or "+" in mode:
            has_file_read = True
        if mode and any(flag in mode for flag in "awx+"):
            has_file_write = True

    state_marker = any(token in lowered for token in ("processed", "idemp", "ledger", "state"))
    return state_marker and has_file_read and has_file_write


def _has_worker_behavior_tests(source: str) -> bool:
    """Recognize the worker's service, restart, failure, and bounded-run proofs."""
    lowered = source.lower()
    required_groups = (
        ("multiple", "two_messages", "each_message", "all_messages"),
        ("duplicate", "idempot"),
        ("restart", "new_process", "new_instance", "second_run"),
        ("failure", "fail", "error", "raises", "exception"),
        ("delete", "acknowledg"),
        ("empty", "no_messages"),
        ("once", "bounded"),
    )
    if len(re.findall(r"\bdef\s+test_", lowered)) < 5 or not all(
        any(token in lowered for token in group) for group in required_groups
    ):
        return False

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False
    service_proof_found = False
    for function in (
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
        and any(token in node.name.lower() for token in ("empty", "service"))
    ):
        initially_false: set[str] = set()
        transitioned_true: set[str] = set()
        for assignment in (node for node in ast.walk(function) if isinstance(node, ast.Assign)):
            if isinstance(assignment.value, ast.Dict):
                has_false_stop = any(
                    isinstance(key, ast.Constant)
                    and key.value == "stop"
                    and isinstance(value, ast.Constant)
                    and value.value is False
                    for key, value in zip(assignment.value.keys, assignment.value.values)
                )
                if has_false_stop:
                    initially_false.update(
                        target.id for target in assignment.targets if isinstance(target, ast.Name)
                    )
            if isinstance(assignment.value, ast.Constant) and assignment.value.value is True:
                for target in assignment.targets:
                    if (
                        isinstance(target, ast.Subscript)
                        and isinstance(target.value, ast.Name)
                        and isinstance(target.slice, ast.Constant)
                        and target.slice.value == "stop"
                    ):
                        transitioned_true.add(target.value.id)
        for call in (node for node in ast.walk(function) if isinstance(node, ast.Call)):
            for keyword in call.keywords:
                if keyword.arg != "stop_flag":
                    continue
                if isinstance(keyword.value, ast.Name):
                    flag_name = keyword.value.id
                    if flag_name in initially_false and flag_name in transitioned_true:
                        service_proof_found = True
                elif isinstance(keyword.value, ast.Dict):
                    # An inline mapping cannot be flipped later by the fake poller, and an
                    # already-true mapping prevents the service loop from running at all.
                    return False
    return service_proof_found


def _publisher_injection_issues(
    source: str,
    path: str,
    required_clients: set[str] | None = None,
) -> list[str]:
    """Find local order-path tests that would accidentally construct live AWS clients."""
    if not source:
        return []
    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError:
        return []

    assigned_values: dict[str, ast.AST] = {}
    for candidate in ast.walk(tree):
        if isinstance(candidate, ast.Assign):
            for target in candidate.targets:
                if isinstance(target, ast.Name):
                    assigned_values[target.id] = candidate.value
        elif isinstance(candidate, ast.AnnAssign) and isinstance(candidate.target, ast.Name):
            if candidate.value is not None:
                assigned_values[candidate.target.id] = candidate.value

    def handler_call_is_post(call: ast.Call) -> bool:
        event_expression: ast.AST | None = call.args[0] if call.args else None
        for keyword in call.keywords:
            if keyword.arg == "event":
                event_expression = keyword.value
                break
        if isinstance(event_expression, ast.Name):
            event_expression = assigned_values.get(event_expression.id, event_expression)
        if event_expression is None:
            return False
        rendered = ast.unparse(event_expression).lower()
        return "post" in rendered and any(
            token in rendered for token in ("httpmethod", "requestcontext", "routekey")
        )

    issues: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = ""
        if isinstance(node.func, ast.Name):
            name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            name = node.func.attr
        keyword_names = {keyword.arg for keyword in node.keywords if keyword.arg is not None}
        exercises_order_path = name == "place_order" or (
            name in {"handler", "lambda_handler"} and handler_call_is_post(node)
        )
        if not exercises_order_path:
            continue
        missing = (required_clients or {"sqs_client", "eventbridge_client"}) - keyword_names
        if missing:
            issues.append(
                f"{path} calls {name}(...) without injected {', '.join(sorted(missing))}; "
                "local tests must not construct boto3 clients"
            )
    return issues


def _sqs_publish_follows_transaction(source: str) -> bool:
    """Prove send_message is structurally after commit or the transaction context."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False
    place_order = next(
        (
            node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "place_order"
        ),
        None,
    )
    if place_order is None:
        return False
    send_lines = [
        node.lineno
        for node in ast.walk(place_order)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "send_message"
    ]
    transaction_boundaries = [
        node.end_lineno or node.lineno
        for node in ast.walk(place_order)
        if isinstance(node, (ast.With, ast.AsyncWith))
        and any(
            isinstance(item.context_expr, ast.Call)
            and (
                isinstance(item.context_expr.func, ast.Name)
                and item.context_expr.func.id == "transaction"
                or isinstance(item.context_expr.func, ast.Attribute)
                and item.context_expr.func.attr == "transaction"
            )
            for item in node.items
        )
    ]
    commit_lines = [
        node.lineno
        for node in ast.walk(place_order)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "commit"
    ]
    boundaries = transaction_boundaries or commit_lines
    return bool(send_lines and boundaries and min(send_lines) > max(boundaries))


def _local_http_body_expects_lambda_envelope(source: str) -> bool:
    """Detect statusCode access specifically on JSON returned by a local HTTP helper."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False

    def called_name(call: ast.Call) -> str:
        if isinstance(call.func, ast.Name):
            return call.func.id.lower()
        if isinstance(call.func, ast.Attribute):
            return call.func.attr.lower()
        return ""

    local_json_values: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        value = node.value
        if not isinstance(value, ast.Call) or "request_json" not in called_name(value):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            if isinstance(target, ast.Name):
                local_json_values.add(target.id)

    for node in ast.walk(tree):
        if not isinstance(node, ast.Subscript):
            continue
        key = node.slice.value if isinstance(node.slice, ast.Constant) else None
        if key != "statusCode":
            continue
        if isinstance(node.value, ast.Name) and node.value.id in local_json_values:
            return True
        if isinstance(node.value, ast.Call) and "request_json" in called_name(node.value):
            return True
    return False


def _has_integrated_order_form(index_html: str, app_js: str) -> bool:
    """Recognize an order form by its browser behavior, not one prescribed DOM id."""
    if not re.search(r"<form\b", index_html, re.I) or "/orders" not in app_js:
        return False
    return bool(
        re.search(r"addEventListener\s*\(\s*['\"]submit['\"]", app_js, re.I)
        or re.search(r"\.onsubmit\s*=", app_js, re.I)
        or re.search(r"\bsubmit[_A-Za-z]*order\s*\(", app_js, re.I)
    )


def _browser_refreshes_inventory_after_order(app_js: str) -> bool:
    """Recognize an initial inventory load reused after the POST /orders boundary."""
    if "/orders" not in app_js or "/inventory" not in app_js:
        return False
    order_position = app_js.find("/orders")
    after_order = app_js[order_position:]
    if re.search(r"fetch\s*\([^)]*/inventory", after_order, re.I | re.S):
        return True

    action_pattern = re.compile(
        r"\b((?:get|load|fetch|refresh|render|show|update)[A-Za-z0-9_$]*inventory[A-Za-z0-9_$]*)\s*\(",
        re.I,
    )
    action_names = action_pattern.findall(app_js)
    for name in set(action_names):
        # Definition/assignment plus an initial invocation and a post-order invocation.
        if len(re.findall(rf"\b{re.escape(name)}\s*\(", app_js, re.I)) < 3:
            continue
        if re.search(rf"\b{re.escape(name)}\s*\(", after_order, re.I):
            return True
    return False


def _has_behavioral_boto_client_tests(source: str) -> bool:
    """Require execution of client factories instead of assertions about source prose."""
    lowered = source.lower()
    return (
        "_sqs_client" in lowered
        and "_eventbridge_client" in lowered
        and "boto3" in lowered
        and any(token in lowered for token in ("patch", "sys.modules"))
        and any(
            token in lowered
            for token in (
                "assert_called",
                "assert_any_call",
                "assert_has_calls",
                "assertcall",
                "mock_calls",
                ".calls",
                "call_args",
                "assertin",
                "assertequal",
            )
        )
        and "assertin('boto3 is required" not in lowered.replace('"', "'")
    )


def _normalize_deployment_wiring_test(source: str, template: str) -> str:
    """Replace a publisher-shaped DetailType text assertion with template-shaped proof."""
    repaired_lines: list[str] = []
    pattern = re.compile(
        r"^(?P<indent>\s*)self\.assertIn\((?P<quote>['\"])(?P<literal>DetailType:\s*.*?)"
        r"(?P=quote),\s*template\)\s*$"
    )
    for line in source.splitlines():
        match = pattern.match(line)
        if not match or match.group("literal") in template:
            repaired_lines.append(line)
            continue
        detail_type = match.group("literal").split(":", 1)[1].strip().strip("'\"")
        if not detail_type or "detail-type:" not in template or detail_type not in template:
            repaired_lines.append(line)
            continue
        indent = match.group("indent")
        repaired_lines.append(f"{indent}self.assertIn('detail-type:', template)")
        repaired_lines.append(f"{indent}self.assertIn({detail_type!r}, template)")
    if not source:
        return source
    return "\n".join(repaired_lines) + ("\n" if source.endswith("\n") else "")


def _deployment_test_literal_issues(
    source: str,
    template: str,
    deploy_guide: str | None = None,
) -> list[str]:
    """Reject artifact-text assertions whose expected literal is not in the file read by the test."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    def artifact_from_expression(expression: ast.AST, known: dict[str, str]) -> str | None:
        if isinstance(expression, ast.Name) and expression.id in known:
            return known[expression.id]
        if isinstance(expression, ast.Name) and expression.id in {"template", "template_text"}:
            return "infra/template.yaml"
        rendered = ast.unparse(expression).lower()
        if "template.yaml" in rendered or "infra_template" in rendered:
            return "infra/template.yaml"
        if "readme.md" in rendered and ("deploy" in rendered or "aws" in rendered):
            return "deploy/aws/README.md"
        return None

    global_artifacts: dict[str, str] = {}
    for statement in tree.body:
        if not isinstance(statement, (ast.Assign, ast.AnnAssign)):
            continue
        value = statement.value
        if value is None:
            continue
        artifact = artifact_from_expression(value, global_artifacts)
        targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
        for target in targets:
            if isinstance(target, ast.Name):
                target_artifact = artifact
                if target_artifact is None and target.id in {"template", "template_text"}:
                    target_artifact = "infra/template.yaml"
                if target_artifact is not None:
                    global_artifacts[target.id] = target_artifact

    artifact_contents = {
        "infra/template.yaml": template,
        "deploy/aws/README.md": deploy_guide,
    }
    issues: list[str] = []
    scopes: list[ast.AST] = [
        node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    if not scopes:
        scopes = [tree]
    for scope in scopes:
        assignments: list[tuple[int, str, str]] = []
        for node in ast.walk(scope):
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                value = node.value
                if value is None:
                    continue
                artifact = artifact_from_expression(value, global_artifacts)
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    if isinstance(target, ast.Name):
                        target_artifact = artifact
                        if target_artifact is None and target.id in {"template", "template_text"}:
                            target_artifact = "infra/template.yaml"
                        if target_artifact is not None:
                            assignments.append((node.lineno, target.id, target_artifact))
        for node in ast.walk(scope):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr not in {"assertIn", "assertNotIn"} or len(node.args) < 2:
                continue
            expected = node.args[0]
            actual = node.args[1]
            if not isinstance(expected, ast.Constant) or not isinstance(expected.value, str):
                continue
            local_artifacts = dict(global_artifacts)
            for _, name, assigned_artifact in sorted(
                (assignment for assignment in assignments if assignment[0] < node.lineno),
                key=lambda assignment: assignment[0],
            ):
                local_artifacts[name] = assigned_artifact
            artifact = artifact_from_expression(actual, local_artifacts)
            artifact_content = artifact_contents.get(artifact or "")
            if artifact is None or artifact_content is None:
                continue
            present = expected.value in artifact_content
            contradicted = (node.func.attr == "assertIn" and not present) or (
                node.func.attr == "assertNotIn" and present
            )
            if contradicted:
                issue = (
                    f"tests/test_deployment_wiring.py {node.func.attr} literal "
                    f"{expected.value!r} contradicts {artifact}"
                )
                if issue not in issues:
                    issues.append(issue)
    return issues


def _validate_behavior_continuity(stage_name: str, snapshot: dict[str, str]) -> None:
    """Require the observable behaviors promised by cumulative lesson prompts."""
    stage_num = _stage_number(stage_name)
    if stage_num is None:
        return

    issues: list[str] = []
    handler = snapshot.get("src/lambda_inventory.py", "")
    handler_lower = handler.lower()
    db_adapter = snapshot.get("src/db_adapter.py", "")
    db_adapter_lower = db_adapter.lower()
    lambda_test = snapshot.get("tests/test_lambda_inventory.py", "")
    browser_app = snapshot.get("src/web/app.js", "")
    browser_index = snapshot.get("src/web/index.html", "")
    http_server = snapshot.get("src/http_server.py", "")

    if stage_num >= 10:
        handler_opens_postgres = any(
            driver in handler_lower for driver in ("psycopg", "pg8000")
        ) and ".connect(" in handler_lower
        handler_uses_adapter = "db_adapter" in handler_lower or "open_connection" in handler_lower
        adapter_opens_postgres = any(
            driver in db_adapter_lower for driver in ("psycopg", "pg8000")
        ) and ".connect(" in db_adapter_lower
        if not handler_opens_postgres and not (handler_uses_adapter and adapter_opens_postgres):
            issues.append(
                "the Lambda inventory path does not use a real PostgreSQL driver connection directly or through "
                "src/db_adapter.py"
            )
        if "select" not in handler_lower or "inventory" not in handler_lower:
            issues.append("src/lambda_inventory.py does not query inventory rows from the database")
        if "bin_location" in lambda_test and "bin_location" not in handler:
            issues.append(
                "src/lambda_inventory.py does not preserve the inventory JSON bin_location field"
            )
        if "local-json" in lambda_test and "local-json" not in handler:
            issues.append(
                "src/lambda_inventory.py dropped the inherited explicit local-json demonstration path"
            )

    if stage_num >= 11:
        for token, label in (
            ("insert into orders", "create an order row"),
            ("insert into order_lines", "create order-line rows"),
            ("commit", "commit the order transaction"),
            ("rollback", "roll back a rejected/failed order"),
        ):
            if token not in handler_lower:
                issues.append(f"src/lambda_inventory.py does not {label}")
        order_test = snapshot.get("tests/test_orders.py", "")
        invalid_order_test = re.search(
            r"def\s+test_rejects_invalid_order[^\n]*\(self\):(?P<body>.*?)(?=\n\s+def\s+test_|\nif\s+__name__|\Z)",
            order_test,
            flags=re.S,
        )
        if invalid_order_test and re.search(
            r"assertTrue\(\s*connection\.closed\s*\)",
            invalid_order_test.group("body"),
        ):
            issues.append(
                "tests/test_orders.py expects an invalid request to open/close a database connection; "
                "validation must happen before the database boundary"
            )
        if re.search(r"https?://(?:127\.0\.0\.1|localhost)(?::\d+)?", browser_app, re.I):
            issues.append("src/web/app.js hard-codes a local API origin instead of using same-origin/config")
        if not _has_integrated_order_form(browser_index, browser_app):
            issues.append("the inventory page does not contain the integrated POST /orders workflow")
        if not re.search(r"method\s*:\s*['\"]POST['\"]", browser_app, re.I):
            issues.append("src/web/app.js does not submit the order with HTTP POST")
        if not _browser_refreshes_inventory_after_order(browser_app):
            issues.append("src/web/app.js does not refresh inventory after an accepted order")
        if "def do_POST" not in http_server or "/orders" not in http_server:
            issues.append("src/http_server.py does not implement the local POST /orders path")
        if not all(token in http_server for token in ("index.html", "app.js")):
            issues.append("src/http_server.py does not serve the integrated browser assets")
        if "TINYWMS_PORT" in http_server and not _has_flushed_readiness_output(http_server):
            issues.append("src/http_server.py does not flush its ephemeral-port readiness line")
        http_order_test = snapshot.get("tests/test_http_order_flow.py", "")
        if not all(token in http_order_test for token in ("/inventory", "/orders", "quantity")):
            issues.append(
                "tests/test_http_order_flow.py does not prove order submission followed by changed inventory"
            )

    if 11 <= stage_num < 13 and re.search(r"\.send_message\s*\(", handler):
        issues.append(
            "src/lambda_inventory.py publishes SQS messages before the Stage 13 queue lesson"
        )

    premature_eventbridge = re.search(r"\.put_events\s*\(", handler) or any(
        token in handler
        for token in (
            "_eventbridge_client",
            "eventbridge_client",
            "EVENT_BUS_NAME",
            "_build_order_placed_event",
        )
    )
    if 11 <= stage_num < 14 and premature_eventbridge:
        issues.append(
            "src/lambda_inventory.py introduces EventBridge behavior before the Stage 14 domain-events lesson"
        )

    if stage_num >= 12:
        concurrency_test = snapshot.get("tests/test_concurrency.py", "").lower()
        if not any(token in handler_lower for token in ("for update", "quantity >=", "begin immediate")):
            issues.append("the order transaction has no visible row-lock or atomic quantity guard")
        if not any(token in concurrency_test for token in ("thread", "barrier", "concurrent.futures")):
            issues.append("tests/test_concurrency.py does not run concurrent attempts")
        if "placeholder" in concurrency_test:
            issues.append("tests/test_concurrency.py still contains placeholder coverage")

    if stage_num >= 13:
        if not re.search(r"\.send_message\s*\(", handler) or "sqs" not in handler_lower:
            issues.append(
                "src/lambda_inventory.py must call an injected or boto3 SQS client's "
                "send_message(...) after commit"
            )
        elif not _sqs_publish_follows_transaction(handler):
            issues.append(
                "src/lambda_inventory.py must place send_message(...) structurally after the committed "
                "transaction boundary"
            )
        if "command_id" not in handler:
            issues.append("the pick-work command does not contain a stable command_id")
        if "description" not in handler:
            issues.append("the pick-work command does not preserve the locked row description")
        if re.search(r"['\"]bin['\"]\s*:\s*['\"][A-Za-z]+\d+-\d+['\"]", handler):
            issues.append("the pick-work command hard-codes a bin instead of using the locked inventory row")
        publishes_all_lines = _has_send_message_inside_loop(handler)
        if not publishes_all_lines:
            issues.append("the committed order path does not publish one pick-work command per order line")
        concurrency_test = snapshot.get("tests/test_concurrency.py", "")
        if "SELECT sku, description, bin" in handler and "SELECT sku, quantity" in concurrency_test:
            issues.append("tests/test_concurrency.py still expects the obsolete compact locked-row query")
        consumer = snapshot.get("src/sqs_consumer.py", "")
        consumer_test = snapshot.get("tests/test_sqs_consumer.py", "").lower()
        if ".receive_message(" not in consumer:
            issues.append("src/sqs_consumer.py does not call receive_message(...) on an SQS client")
        if "WaitTimeSeconds" not in consumer:
            issues.append("src/sqs_consumer.py does not make SQS long polling visible")
        if ".delete_message(" not in consumer:
            issues.append("src/sqs_consumer.py does not acknowledge success with delete_message(...)")
        if not re.search(r"def\s+consume_messages\s*\(", consumer):
            issues.append("src/sqs_consumer.py does not expose the stable consume_messages(...) boundary")
        if re.search(r"while\s+True\s*:", consumer):
            issues.append(
                "src/sqs_consumer.py owns an unbounded drain loop; consume_messages(...) must perform "
                "one long poll so the worker owns service lifetime"
            )
        if not _has_sqs_fake_client_behavior_tests(consumer_test):
            issues.append(
                "tests/test_sqs_consumer.py does not cover receive, delete, failure/no-delete, and multiple messages"
            )
        for publisher_test_path in ("tests/test_lambda_inventory.py", "tests/test_concurrency.py"):
            issues.extend(
                _publisher_injection_issues(
                    snapshot.get(publisher_test_path, ""),
                    publisher_test_path,
                    {"sqs_client"},
                )
            )

    if stage_num >= 14:
        if not re.search(r"\.put_events\s*\(", handler) or "events" not in handler_lower:
            issues.append(
                "src/lambda_inventory.py must call an injected or boto3 EventBridge client's "
                "put_events(...) with OrderPlaced after commit"
            )
        events_template = snapshot.get("infra/events.yaml", "")
        if events_template.count("AWS::Events::Rule") < 2:
            issues.append("infra/events.yaml does not define two independent EventBridge rules")
        if events_template.count("AWS::SQS::Queue") < 2 or "AWS::SQS::QueuePolicy" not in events_template:
            issues.append("infra/events.yaml does not define two observable queue targets and delivery policy")
        for consumer_path in ("src/event_consumer_a.py", "src/event_consumer_b.py"):
            event_consumer = snapshot.get(consumer_path, "")
            if ".receive_message(" not in event_consumer or "json.loads" not in event_consumer:
                issues.append(f"{consumer_path} does not receive and decode delivered event JSON")
        event_test = snapshot.get("tests/test_event_consumers.py", "").lower()
        if not all(token in event_test for token in ("consumer_a", "consumer_b", "receive_message")):
            issues.append("tests/test_event_consumers.py does not prove two independent delivered-event consumers")
        for publisher_test_path in ("tests/test_orders.py", "tests/test_concurrency.py"):
            issues.extend(
                _publisher_injection_issues(
                    snapshot.get(publisher_test_path, ""),
                    publisher_test_path,
                )
            )

    if stage_num >= 15:
        worker = snapshot.get("src/pick_ticket_worker.py", "")
        worker_lower = worker.lower()
        worker_test = snapshot.get("tests/test_pick_ticket_worker.py", "")
        sqs_consumer = snapshot.get("src/sqs_consumer.py", "")
        if not _worker_uses_sqs_receive_delete(worker, sqs_consumer):
            issues.append("src/pick_ticket_worker.py is not connected to SQS receive/delete semantics")
        if "consume_messages(" in worker and re.search(
            r"json\.loads\s*\([^\n]*(?:\[['\"]Body['\"]\]|\.get\(['\"]Body['\"])",
            worker,
        ):
            issues.append(
                "src/pick_ticket_worker.py treats the decoded consume_messages callback value as a raw SQS envelope"
            )
        if not re.search(r"\bwhile\b", worker) or "--once" not in worker:
            issues.append("src/pick_ticket_worker.py is not a long-running worker with bounded --once mode")
        if "command_id" not in worker or not any(
            token in worker_lower for token in ("processed", "idemp", "duplicate")
        ):
            issues.append("src/pick_ticket_worker.py does not visibly suppress duplicate command_id delivery")
        if not _worker_has_durable_idempotency_state(worker):
            issues.append("src/pick_ticket_worker.py does not persist idempotency state across restarts")
        if re.search(r"if\s+once\s+or\s+not\s+messages", worker):
            issues.append("src/pick_ticket_worker.py exits service mode after an empty SQS receive")
        if "SIGTERM" not in worker or "signal.signal" not in worker:
            issues.append("src/pick_ticket_worker.py does not handle orderly SIGTERM shutdown")
        if not _has_worker_behavior_tests(worker_test):
            issues.append(
                "tests/test_pick_ticket_worker.py does not cover multiple messages, restart duplicates, "
                "failure/no-delete, empty service polls, and bounded --once execution"
            )

    if stage_num >= 16:
        callback_source = snapshot.get("tests/test_callback_integration.py", "")
        callback_test = callback_source.lower()
        callback_signals = {
            "inventory": ("/inventory", "inventory"),
            "order": ("/orders", "order"),
            "quantity": ("quantity",),
            "command ID": ("command_id",),
            "ticket output": ("pick-tickets", "pick_tickets", "ticket_path"),
        }
        missing_callback_signals = [
            label
            for label, alternatives in callback_signals.items()
            if not any(token in callback_test for token in alternatives)
        ]
        if missing_callback_signals:
            issues.append(
                "tests/test_callback_integration.py does not prove inventory -> order -> command -> "
                "pick-ticket; missing " + ", ".join(missing_callback_signals)
            )
        if not any(token in callback_test for token in ("urlopen", "httpconnection")):
            issues.append("tests/test_callback_integration.py bypasses the real local HTTP boundary")
        if "inventory" not in callback_test or not any(
            token in callback_test for token in ("patch", "tinywms_inventory_path")
        ):
            issues.append("tests/test_callback_integration.py does not isolate mutable inventory state")
        if not _callback_invokes_worker_consumption(
            callback_source,
            snapshot.get("src/pick_ticket_worker.py", ""),
            snapshot.get("src/sqs_consumer.py", ""),
        ):
            issues.append("tests/test_callback_integration.py does not invoke the real worker consumer")
        if _local_http_body_expects_lambda_envelope(callback_source):
            issues.append(
                "tests/test_callback_integration.py expects a Lambda statusCode envelope from the local HTTP server"
            )
        if "lambda_inventory" not in callback_test:
            issues.append(
                "tests/test_callback_integration.py fabricates the pick-work command instead of invoking the real order publisher"
            )

    if stage_num >= 17:
        dockerfile = snapshot.get("src/Dockerfile", "")
        if "pick_ticket_worker.py" not in dockerfile or "ENTRYPOINT" not in dockerfile:
            issues.append("src/Dockerfile does not start the pick-ticket worker")
        if "--once" in dockerfile:
            issues.append("src/Dockerfile makes bounded --once mode the default instead of long-running mode")

    if stage_num >= 18:
        template = snapshot.get("infra/template.yaml", "")
        deploy_guide = snapshot.get("deploy/aws/README.md", "")
        placeholder_phrases = (
            "package the lesson code",
            "upload code separately",
            "replace with your code",
        )
        if any(phrase in template.lower() for phrase in placeholder_phrases):
            issues.append("infra/template.yaml deploys placeholder Lambda code")
        packaged_code = (
            ("S3Bucket:" in template and "S3Key:" in template)
            or "CodeUri:" in template
        )
        packaging_command = any(
            token in deploy_guide
            for token in ("aws cloudformation package", "aws s3 cp", "sam build", "sam deploy")
        )
        if not packaged_code or not packaging_command:
            issues.append(
                "infra/template.yaml must use Lambda Code S3Bucket/S3Key (or SAM CodeUri), and "
                "deploy/aws/README.md must run aws cloudformation package, aws s3 cp, sam build, "
                "or sam deploy for the real Lambda source"
            )
        for name in ("DATABASE_URL", "PICK_WORK_QUEUE_URL", "EVENT_BUS_NAME"):
            if name not in template:
                issues.append(f"infra/template.yaml does not wire the Lambda {name} environment variable")
        for action in ("sqs:SendMessage", "events:PutEvents"):
            if action not in template:
                issues.append(f"infra/template.yaml does not grant the Lambda {action}")
        issues.extend(_consolidated_deployment_wiring_issues(template, handler))
        if not re.search(r"boto3\.client\(\s*['\"]sqs['\"]", handler):
            issues.append("src/lambda_inventory.py does not construct a production boto3 SQS client")
        if not re.search(r"boto3\.client\(\s*['\"](?:events|eventbridge)['\"]", handler):
            issues.append("src/lambda_inventory.py does not construct a production boto3 EventBridge client")
        package_script = snapshot.get("deploy/aws/package_lambda.sh", "")
        handler_match = re.search(r"^\s*Handler:\s*([^\s#]+)", template, re.M)
        if handler_match:
            configured_handler = handler_match.group(1)
            copies_module_to_root = bool(
                re.search(r"cp\s+[^\n]*src/lambda_inventory\.py\s+['\"]?\$\{?BUILD_DIR\}?/?['\"]?", package_script)
            )
            preserves_src_package = bool(
                re.search(r"(?:cp|mkdir)[^\n]*(?:\$\{?BUILD_DIR\}?/src|src/?['\"]?\s*$)", package_script, re.M)
            )
            if configured_handler.startswith("src.") and copies_module_to_root and not preserves_src_package:
                issues.append(
                    "Lambda handler src.lambda_inventory.handler does not match the ZIP's root lambda_inventory.py"
                )
            if configured_handler == "lambda_inventory.handler" and preserves_src_package and not copies_module_to_root:
                issues.append(
                    "Lambda handler lambda_inventory.handler does not match a ZIP that preserves src/lambda_inventory.py"
                )
        if "db_adapter" in handler and "src/db_adapter.py" not in package_script:
            issues.append("Lambda package script omits imported src/db_adapter.py")
        deployment_test = snapshot.get("tests/test_deployment_wiring.py", "")
        if not _has_behavioral_boto_client_tests(deployment_test):
            issues.append(
                "tests/test_deployment_wiring.py does not execute the SQS/EventBridge client factories "
                "with a fake boto3 module"
            )
        issues.extend(_deployment_test_literal_issues(deployment_test, template, deploy_guide))

    if stage_num >= 20:
        walkthrough = snapshot.get("docs/end-to-end.md", "")
        for token in (
            "browser",
            "API Gateway",
            "Lambda",
            "RDS",
            "SQS",
            "EventBridge",
            "pick-ticket",
        ):
            if token not in walkthrough:
                issues.append(f"docs/end-to-end.md does not cover the {token} boundary")
        deployment_test = snapshot.get("tests/test_deployment_wiring.py", "")
        if not all(
            token in deployment_test
            for token in (
                "DATABASE_URL",
                "PICK_WORK_QUEUE_URL",
                "EVENT_BUS_NAME",
                "sqs:SendMessage",
                "events:PutEvents",
            )
        ):
            issues.append("tests/test_deployment_wiring.py does not prove the final cloud component wiring")

    if issues:
        raise ValueError(
            f"Stage {stage_name} behavior continuity audit failed: " + "; ".join(issues) + "."
        )


def _forward_behavior_generation_contract(stage_name: str) -> str:
    """Put stage-specific executable acceptance conditions next to reference excerpts."""
    requirements = {
        "07-api-gateway": [
            "Add tests/test_web_app.js using only node:test and document node --test tests/test_web_app.js. "
            "The test must exercise or inspect the inherited plain JavaScript app without network access.",
            "tests/test_web_app.js may assert only what this stage's src/web/app.js and index.html actually contain "
            "(runtime API base override, new URL('/inventory', ...), fetch, inventory-body rendering). Do NOT copy "
            "the Stage 20 reference's order-form, POST /orders, response-json, or refresh-after-order assertions: "
            "the order form arrives in Stage 11 and its tests belong there.",
            "Student exercises must lead to visible browser/curl behavior; tests are an optional follow-up.",
        ],
        "08-relational-persistence": [
            "Emit data/schema.sql with only the inventory table at this stage, using canonical bin_location, "
            "plus matching data/seed.sql. Do not introduce orders/order_lines before Stage 11.",
            "Emit src/db_adapter.py and data/init_db.py with explicit TINYWMS_DB=sqlite|postgres selection, "
            "TINYWMS_SQLITE_PATH, lazy PostgreSQL imports, SQLite foreign keys, and a narrow visible adaptation "
            "of %s to ? plus removal of FOR UPDATE. PostgreSQL remains the default.",
            "Emit tests/test_relational_persistence.py with descriptive test names such as "
            "test_schema_uses_bin_location, test_seed_matches_inventory_schema, and "
            "test_sqlite_initializer_loads_inventory. Never emit test_placeholder names, pass-only tests, "
            "or assert True placeholders; exercise or inspect the real schema, seed, adapter, and initializer.",
        ],
        "09-rds": [
            "Preserve the Stage 08 SQLite/PostgreSQL adapter and initializer unchanged while adding RDS as "
            "the PostgreSQL hosting option; do not delete the runnable local SQLite path.",
        ],
        "10-lambda-rds": [
            "Emit complete replacements for src/lambda_inventory.py and tests/test_lambda_inventory.py; "
            "a documentation-only or infrastructure-only delta is invalid.",
            "The deployed GET /inventory path must import psycopg/psycopg2 or pg8000, open the RDS "
            "connection from visible environment configuration, execute SELECT against inventory, and "
            "map rows back to the established JSON fields.",
            "Borrow the final reference's PostgreSQL connection and inventory-query behavior, but omit "
            "the order, SQS, and EventBridge behavior introduced by later stages.",
            "Reuse src/db_adapter.py. TINYWMS_DB defaults to postgres; sqlite uses TINYWMS_SQLITE_PATH. "
            "Query SQL column bin_location and map it to the inherited inventory JSON field.",
            "The tests must inject a fake or mock DB connection and prove returned JSON came from DB rows.",
        ],
        "11-orders": [
            "Emit complete replacements for src/lambda_inventory.py and tests/test_sqlite_orders.py in the "
            "same response; they are one atomic public API change.",
            "If tests/test_sqlite_orders.py imports OrderLine or OrderRequest from src.lambda_inventory, "
            "src/lambda_inventory.py must define and export those dataclasses. OrderLine has visible sku, "
            "quantity, and description fields; OrderRequest has order_id and lines. Alternatively, the test "
            "must construct orders only through a function actually exported by that emitted module. Audit "
            "every `from src.lambda_inventory import ...` name against the complete handler before returning.",
            "Public API, matching the final reference: `@dataclass(frozen=True) class OrderLine: sku: str; quantity: int; "
            "description: str = ''`, `@dataclass(frozen=True) class OrderRequest: order_id: str; lines: list[OrderLine]`, "
            "and `place_order(connection, order: OrderRequest) -> dict` that reads order.order_id and order.lines directly "
            "(attribute access, not dict access); the HTTP/Lambda handler parses JSON into an OrderRequest before calling it, "
            "and the test constructs OrderRequest('ORD-1', [OrderLine('SKU-1001', 2, 'Blue widget')]). "
            "Within one visible transaction, insert the order row and order-line rows, decrement inventory, "
            "commit success, and roll back rejection/failure. Do not publish SQS or EventBridge messages yet.",
            "Evolve data/schema.sql here, not earlier: orders.order_id is a primary key and order_lines has "
            "foreign keys to orders and inventory plus CHECK(quantity > 0). Emit tests/test_sqlite_orders.py "
            "using a real temporary SQLite database for success, insufficient-stock rollback, and unknown SKU.",
            "tests/test_sqlite_orders.py is checked structurally: it must be a unittest.TestCase with methods "
            "named exactly test_accepted_order_persists_rows, test_insufficient_inventory_rolls_back, and "
            "test_unknown_sku_rolls_back. In setUp, patch.dict os.environ with TINYWMS_DB=sqlite and "
            "TINYWMS_SQLITE_PATH pointing into a tempfile.TemporaryDirectory, then call "
            "`from data.init_db import init_db; init_db()` (inherited unchanged from Stage 08) and obtain order "
            "connections with `from src.db_adapter import open_connection` used as "
            "`with open_connection() as connection:`. Assert persisted rows by SELECT COUNT(*) on orders and "
            "order_lines and the changed/unchanged inventory quantity. Never open sqlite3 directly in the test. Use `assertRaises(<exception class exported by src/lambda_inventory.py>)` with no assertRaisesRegex or message-text assertion.",
            "Normalize tuple and dict cursor rows using canonical bin_location; later queue JSON may map it to bin.",
            "Do not copy later-stage send_message(...), put_events(...), queue URL, event bus, or boto3 "
            "client-factory behavior into this stage. Tests must exercise only the APIs actually exported "
            "by the emitted src/lambda_inventory.py, and exception assertions must match its real errors.",
            "Evolve src/web/index.html and src/web/app.js into one inventory-and-order page. Use same-origin "
            "configuration, POST /orders, then refresh GET /inventory; never hard-code localhost.",
            "Evolve src/http_server.py to serve the browser assets and implement local POST /orders. Emit "
            "tests/test_http_order_flow.py proving order submission changes a later inventory response.",
            "Preserve src/order_form.html as a comparison artifact required by the course blueprint, but "
            "document and test src/web/index.html plus src/web/app.js as the primary integrated journey.",
        ],
        "12-concurrency": [
            "Emit the transaction/concurrency implementation delta, src/concurrency_demo.py, and "
            "tests/test_concurrency.py. `python3 src/concurrency_demo.py` must run two overlapping attempts "
            "and print their outcomes plus final inventory without invoking unittest.",
            "tests/test_concurrency.py must literally import `threading` and start at least two `threading.Thread` workers that "
            "wait on a shared `threading.Barrier(2)` before each calls place_order against the same SKU with a stock that "
            "covers only one order; assert exactly one succeeds, one raises the insufficient-stock error, and inventory never goes negative. "
            "Use a visible row lock or atomic quantity guard, and run genuinely overlapping attempts with "
            "threads, a barrier, or concurrent.futures; placeholder assertions are invalid.",
            "Keep the Stage 11 public order API unless source and tests are evolved together. Every name "
            "imported by tests/test_concurrency.py must actually be exported by src/lambda_inventory.py. "
            "Do not introduce Stage 13 SQS or Stage 14 EventBridge publishing early.",
            "Edit src/lambda_inventory.py incrementally: keep every module-level name that inherited tests reference "
            "(for example DEFAULT_QUERY, handler, OrderLine, OrderRequest, place_order and their exceptions) with "
            "unchanged meaning. Before returning, search tests/test_lambda_inventory.py, tests/test_orders.py and "
            "tests/test_sqlite_orders.py for `module.<name>` and `from src.lambda_inventory import` usages and confirm each exists.",
            "docs/architecture.md and docs/data-contracts.md must each contain, verbatim, the sentence \"SQLite cannot demonstrate the PostgreSQL row-lock lesson\". "
            "Keep SQLite as a transaction smoke-test backend, but document that the real row-lock/concurrency "
            "lesson requires PostgreSQL and SELECT ... FOR UPDATE.",
            "README student exercises must change a stock, delay, or transaction value, run "
            "python3 src/concurrency_demo.py, and ask students to observe or compare printed behavior. "
            "Mention the test suite only afterward as an explicitly optional check.",
        ],
        "13-sqs": [
            "Mandatory delta paths are src/lambda_inventory.py, tests/test_lambda_inventory.py, "
            "tests/test_concurrency.py, src/sqs_consumer.py, and tests/test_sqs_consumer.py. Emit complete "
            "replacements for them; infrastructure/documentation alone is invalid.",
            "Evolve Stage 12 place_order(connection, order) to place_order(connection, order, "
            "sqs_client=None). Retain every normalized locked inventory row while inside the transaction. "
            "After the transaction context has exited and committed, resolve the injected-or-boto3 SQS "
            "client and queue URL, then loop over every built command and call send_message(...). Never "
            "send inside the transaction or after rollback, and do not add EventBridge until Stage 14.",
            "Do not define or reference EVENT_BUS_NAME, _eventbridge_client, eventbridge_client, "
            "_build_order_placed_event, or put_events in src/lambda_inventory.py at Stage 13. The frozen "
            "Stage 12 handler is the implementation base. The supplied reference handler is a Stage 13 "
            "projection whose Stage 14 event publisher has been structurally removed.",
            "Emit one versioned command per order line with stable command_id and a bin obtained from the "
            "locked inventory row plus its description; a first-line-only command or literal bin is invalid. "
            "Copy/adapt the final reference's _command_id, _build_pick_work_commands, and _sqs_client shapes. "
            "Update inherited Lambda and concurrency tests to pass fake sqs_client objects and prove "
            "commit-before-send plus rollback-without-send.",
            "Implement src/sqs_consumer.py with receive_message long polling and delete_message only after "
            "successful processing. Fake-client tests must cover receive/delete, failure/no-delete, and multiple messages.",
        ],
        "14-domain-events": [
            "Emit the order-handler delta that calls an injected or boto3 EventBridge client's "
            "put_events(...) with OrderPlaced only after commit; preserve the distinct SQS command path.",
            "infra/events.yaml must define two EventBridge rules, two observable SQS targets, and delivery "
            "policies. Both Python consumers must receive/decode delivered JSON and use independent fake-client tests.",
        ],
        "15-pick-ticket-worker": [
            "Evolve the queue receiver into a long-running SQS worker with --once test mode, delete only "
            "after ticket output, durable command_id duplicate suppression across restarts, empty-poll "
            "continuation, and orderly SIGINT/SIGTERM shutdown.",
            "tests/test_pick_ticket_worker.py must cover multiple messages, restart duplicates, empty polls, "
            "failure/no-delete, and acknowledgement after output.",
            "Give main a signature `main(argv, stop_flag=None)` where stop_flag is a shared {'stop': False} dict; "
            "signal handlers set stop_flag['stop']=True and the loop ends on `args.once or stop_flag['stop']`. "
            "Write test_service_continues_after_empty_poll with `stop_flag = {'stop': False}`, a fake "
            "consume_messages whose second call delivers a message and then sets stop_flag['stop']=True, and "
            "`worker.main(argv, stop_flag=stop_flag)`. Also write test_once_mode_is_bounded_to_one_poll, "
            "test_multiple_messages_..., test_duplicate_after_restart_..., and test_failure_does_not_delete.",
            "Emit deploy/pick-ticket-worker/tinywms-pick-ticket-worker.service.in, install_user_service.sh, "
            "environment.example, and README.md. The user service runs long-lived mode, restarts on failure, "
            "and documents systemctl --user, journalctl --user, and tail -f.",
        ],
        "16-callback-demo": [
            "Emit tests/test_callback_integration.py as an executable local proof of GET inventory, POST order, "
            "changed quantity, emitted command, worker consumption, and pick-ticket output using fake AWS clients. "
            "Use a real local HTTP client and temporary isolated mutable paths; never edit checked-in data.",
        ],
        "17-container-worker": [
            "src/Dockerfile must run the long-lived worker by default while documentation retains a bounded "
            "--once classroom example and mounts ticket/idempotency state.",
            "Emit deploy/container-worker/README.md with exact docker run commands, PICK_WORK_QUEUE_URL, "
            "host-backed mounts for pick-tickets and processed-command state, and a bounded --once example.",
        ],
        "18-aws-deployment": [
            "infra/template.yaml and deploy/aws/README.md must package and deploy the real "
            "src/lambda_inventory.py source through S3Bucket/S3Key or SAM CodeUri and runnable package/deploy "
            "commands; an inline demonstration handler is not the consolidated deployment.",
            "Wire DATABASE_URL, PICK_WORK_QUEUE_URL, EVENT_BUS_NAME, sqs:SendMessage, events:PutEvents, two "
            "EventBridge rules/targets, and production boto3 clients. The configured handler must match the ZIP layout.",
            "If lambda_inventory imports db_adapter, deploy/aws/package_lambda.sh must copy src/db_adapter.py "
            "into the same importable ZIP layout.",
            "Deployment tests must run with the Python standard library alone: do not import yaml/PyYAML, "
            "boto3, botocore, or PostgreSQL drivers. Inspect template text and inject fake modules instead.",
            "Every literal assertion about infra/template.yaml or deploy/aws/README.md must occur verbatim "
            "in that artifact. Do not invent database URLs or prose labels such as GET /inventory when the "
            "guide demonstrates the route through curl commands.",
        ],
        "19-git-history": [
            "Emit docs/git-history.md explaining that the published course uses sibling stage directories in "
            "one repository revision. Use git diff --no-index comparisons and do not invent stage-* tags or "
            "rewrite history.",
        ],
        "20-final-walkthrough": [
            "Emit tests/test_callback_integration.py, tests/test_deployment_wiring.py, and "
            "tests/test_end_to_end_walkthrough.py. The walkthrough test must inspect docs/end-to-end.md "
            "using only the standard library and check browser, API Gateway, Lambda, RDS, SQS, EventBridge, "
            "and pick-ticket boundaries. Reject a walkthrough "
            "that names browser/order/SQS/EventBridge/worker connections not proven by those executable checks.",
            "Emit docs/demo-runbook.md with headings Session 1 through Session 26, exact supported commands, "
            "stage mappings, and honest Manual only/Partly manual labels. It must literally include "
            "TINYWMS_DB=sqlite, systemctl --user, journalctl --user, tail -f, and docker run. Emit "
            "tests/test_demo_runbook.py. Rewrite README exercises around visible behavior first; tests may "
            "appear only as an optional follow-up.",
        ],
    }.get(stage_name)
    if not requirements:
        return ""
    return (
        "FORWARD BEHAVIOR ACCEPTANCE CONTRACT\n"
        "These are executable acceptance conditions, not documentation suggestions. The stage is rejected "
        "unless its file delta implements them:\n- "
        + "\n- ".join(requirements)
    )


def _forward_reference_overlay(
    stage_name: str,
    reference_snapshot: dict[str, str],
) -> dict[str, str]:
    """Borrow final component files, applying only stage-contract presentation edits."""
    paths_by_stage = {
        "07-api-gateway": (
            "infra/api-gateway.yaml",
            "deploy/api-gateway/README.md",
        ),
        "12-concurrency": ("tests/test_sqlite_orders.py",),
        "11-orders": (
            "tests/test_sqlite_orders.py",
            "src/order_form.html",
            "src/web/index.html",
            "src/web/app.js",
            "src/web/style.css",
            "src/http_server.py",
            "tests/test_http_order_flow.py",
        ),
        "13-sqs": (
            "src/lambda_inventory.py",
            "src/sqs_consumer.py",
            "tests/test_lambda_inventory.py",
            "tests/test_concurrency.py",
            "tests/test_sqlite_orders.py",
            "tests/test_sqs_consumer.py",
            "infra/sqs.yaml",
            "deploy/sqs/README.md",
        ),
        "14-domain-events": (
            "src/lambda_inventory.py",
            "tests/test_lambda_inventory.py",
            "tests/test_orders.py",
            "tests/test_concurrency.py",
            "tests/test_sqlite_orders.py",
            "src/event_consumer_a.py",
            "src/event_consumer_b.py",
            "tests/test_event_consumers.py",
            "infra/events.yaml",
            "deploy/events/README.md",
        ),
        "15-pick-ticket-worker": (
            "src/pick_ticket_worker.py",
            "tests/test_pick_ticket_worker.py",
            "deploy/pick-ticket-worker/tinywms-pick-ticket-worker.service.in",
            "deploy/pick-ticket-worker/install_user_service.sh",
            "deploy/pick-ticket-worker/environment.example",
            "deploy/pick-ticket-worker/README.md",
        ),
        "16-callback-demo": (
            "tests/test_callback_integration.py",
        ),
        "17-container-worker": (
            "src/Dockerfile",
            "tests/test_container_worker.py",
            "deploy/container-worker/README.md",
        ),
        "18-aws-deployment": (
            "infra/template.yaml",
            "deploy/aws/README.md",
            "deploy/aws/package_lambda.sh",
            "requirements.txt",
            "tests/test_aws_deployment_files.py",
            "tests/test_deployment_wiring.py",
        ),
        "19-git-history": ("docs/git-history.md",),
    }
    if stage_name == "20-final-walkthrough":
        return dict(reference_snapshot)
    paths = paths_by_stage.get(stage_name, ())
    missing = [path for path in paths if path not in reference_snapshot]
    if missing:
        raise ValueError(
            f"Final reference cannot supply exact {stage_name} borrowing paths: {missing}."
        )
    overlay = {path: reference_snapshot[path] for path in paths}
    if stage_name == "18-aws-deployment":
        # The final walkthrough numbers operational steps around these sections. Stage 18's prompt
        # requires the four core headings literally, so normalize headings without rewriting commands.
        deploy_readme = overlay["deploy/aws/README.md"]
        heading_patterns = (
            (r"(?m)^##(?:\s+\d+\))?\s+Deploy(?: the stack)?\s*$", "## Deploy"),
            (r"(?m)^##(?:\s+\d+\))?\s+Resolve outputs\s*$", "## Resolve outputs"),
            (
                r"(?m)^##(?:\s+\d+\))?\s+Verify(?: the API contract| contracts)?\s*$",
                "## Verify contracts",
            ),
            (r"(?m)^##(?:\s+\d+\))?\s+Destroy(?: the stack)?\s*$", "## Destroy"),
        )
        for pattern, replacement in heading_patterns:
            deploy_readme = re.sub(pattern, replacement, deploy_readme)
        overlay["deploy/aws/README.md"] = deploy_readme
    return overlay


def _project_reference_lambda_handler(source: str, *, include_eventbridge: bool) -> str:
    """Preserve local contracts while projecting the final handler to a lesson boundary."""
    tree = ast.parse(source, filename="src/lambda_inventory.py")

    def drop_argument(arguments: ast.arguments, name: str) -> None:
        positional = [*arguments.posonlyargs, *arguments.args]
        index = next((index for index, argument in enumerate(positional) if argument.arg == name), None)
        if index is not None:
            default_start = len(positional) - len(arguments.defaults)
            if index >= default_start:
                del arguments.defaults[index - default_start]
            if index < len(arguments.posonlyargs):
                del arguments.posonlyargs[index]
            else:
                del arguments.args[index - len(arguments.posonlyargs)]
        for index, argument in enumerate(arguments.kwonlyargs):
            if argument.arg == name:
                del arguments.kwonlyargs[index]
                del arguments.kw_defaults[index]
                break
        if arguments.vararg is not None and arguments.vararg.arg == name:
            arguments.vararg = None
        if arguments.kwarg is not None and arguments.kwarg.arg == name:
            arguments.kwarg = None

    def target_names(target: ast.expr) -> set[str]:
        if isinstance(target, ast.Name):
            return {target.id}
        if isinstance(target, (ast.Tuple, ast.List)):
            return {name for item in target.elts for name in target_names(item)}
        return set()

    # Idempotence: a source that already routes cursors through the helper must not be rewritten again.
    has_cursor_helper = any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "_cursor_for_connection"
        for node in tree.body
    )

    eventbridge_assignments = {"EVENT_BUS_NAME_ENV", "eventbridge", "bus_name"}
    eventbridge_functions = {"_eventbridge_client", "_build_order_placed_event"}

    class LessonProjection(ast.NodeTransformer):
        def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST | None:
            if not include_eventbridge and node.name in eventbridge_functions:
                return None
            if not include_eventbridge:
                drop_argument(node.args, "eventbridge_client")
            return self.generic_visit(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST | None:
            if not include_eventbridge and node.name in eventbridge_functions:
                return None
            if not include_eventbridge:
                drop_argument(node.args, "eventbridge_client")
            return self.generic_visit(node)

        def visit_Assign(self, node: ast.Assign) -> ast.AST | None:
            if not include_eventbridge and any(
                target_names(target) & eventbridge_assignments for target in node.targets
            ):
                return None
            return self.generic_visit(node)

        def visit_AnnAssign(self, node: ast.AnnAssign) -> ast.AST | None:
            if not include_eventbridge and target_names(node.target) & eventbridge_assignments:
                return None
            return self.generic_visit(node)

        def visit_If(self, node: ast.If) -> ast.AST | None:
            condition_names = {
                item.id for item in ast.walk(node.test) if isinstance(item, ast.Name)
            }
            if not include_eventbridge and condition_names & (
                eventbridge_assignments | {"eventbridge_client"}
            ):
                return None
            return self.generic_visit(node)

        def visit_Expr(self, node: ast.Expr) -> ast.AST | None:
            if (
                not include_eventbridge
                and
                isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Attribute)
                and node.value.func.attr == "put_events"
            ):
                return None
            return self.generic_visit(node)

        def visit_Call(self, node: ast.Call) -> ast.AST:
            node = self.generic_visit(node)
            assert isinstance(node, ast.Call)
            if not include_eventbridge:
                node.keywords = [
                    keyword for keyword in node.keywords if keyword.arg != "eventbridge_client"
                ]
            if (
                not has_cursor_helper
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "cursor"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "connection"
            ):
                return ast.Call(
                    func=ast.Name(id="_cursor_for_connection", ctx=ast.Load()),
                    args=[ast.Name(id="connection", ctx=ast.Load())],
                    keywords=[],
                )
            return node

    projected = LessonProjection().visit(tree)
    assert isinstance(projected, ast.Module)

    shortage_index = next(
        (
            index
            for index, node in enumerate(projected.body)
            if isinstance(node, ast.ClassDef) and node.name == "InventoryShortageError"
        ),
        None,
    )
    defines_lookup_error = any(
        isinstance(node, ast.ClassDef) and node.name == "InventoryLookupError"
        for node in projected.body
    )
    if shortage_index is not None and not defines_lookup_error:
        projected.body.insert(
            shortage_index + 1,
            ast.Assign(
                targets=[ast.Name(id="InventoryLookupError", ctx=ast.Store())],
                value=ast.Name(id="InventoryShortageError", ctx=ast.Load()),
            ),
        )

    cursor_helper = ast.parse(
        "def _cursor_for_connection(connection):\n"
        "    cursor = connection.cursor()\n"
        "    if connection.__class__.__module__ == 'sqlite3':\n"
        "        from src.db_adapter import SQLiteCursorAdapter\n"
        "        return SQLiteCursorAdapter(cursor)\n"
        "    return cursor\n"
    ).body[0]
    first_function = next(
        (
            index
            for index, node in enumerate(projected.body)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ),
        len(projected.body),
    )
    if not has_cursor_helper:
        projected.body.insert(first_function, cursor_helper)

    place_order_node = next(
        (
            node
            for node in projected.body
            if isinstance(node, ast.FunctionDef) and node.name == "place_order"
        ),
        None,
    )
    if place_order_node is not None:
        sqs_assignment = next(
            (
                node
                for node in place_order_node.body
                if isinstance(node, ast.Assign)
                and any("sqs" in target_names(target) for target in node.targets)
            ),
            None,
        )
        queue_assignment = next(
            (
                node
                for node in place_order_node.body
                if isinstance(node, ast.Assign)
                and any("queue_url" in target_names(target) for target in node.targets)
            ),
            None,
        )
        publish_loop = next(
            (
                node
                for node in place_order_node.body
                if isinstance(node, (ast.For, ast.AsyncFor))
                and any(
                    isinstance(descendant, ast.Attribute) and descendant.attr == "send_message"
                    for descendant in ast.walk(node)
                )
            ),
            None,
        )
        if sqs_assignment is not None and queue_assignment is not None and publish_loop is not None:
            place_order_node.body = [
                node
                for node in place_order_node.body
                if node is not sqs_assignment and node is not publish_loop
            ]
            queue_index = place_order_node.body.index(queue_assignment)
            place_order_node.body.insert(
                queue_index + 1,
                ast.If(
                    test=ast.BoolOp(
                        op=ast.Or(),
                        values=[
                            ast.Compare(
                                left=ast.Name(id="sqs_client", ctx=ast.Load()),
                                ops=[ast.IsNot()],
                                comparators=[ast.Constant(value=None)],
                            ),
                            ast.Name(id="queue_url", ctx=ast.Load()),
                        ],
                    ),
                    body=[sqs_assignment, publish_loop],
                    orelse=[],
                ),
            )

        if include_eventbridge:
            eventbridge_assignment = next(
                (
                    node
                    for node in place_order_node.body
                    if isinstance(node, ast.Assign)
                    and any("eventbridge" in target_names(target) for target in node.targets)
                ),
                None,
            )
            bus_assignment = next(
                (
                    node
                    for node in place_order_node.body
                    if isinstance(node, ast.Assign)
                    and any("bus_name" in target_names(target) for target in node.targets)
                ),
                None,
            )
            event_publish = next(
                (
                    node
                    for node in place_order_node.body
                    if isinstance(node, ast.Expr)
                    and isinstance(node.value, ast.Call)
                    and isinstance(node.value.func, ast.Attribute)
                    and node.value.func.attr == "put_events"
                ),
                None,
            )
            if (
                eventbridge_assignment is not None
                and bus_assignment is not None
                and event_publish is not None
            ):
                place_order_node.body = [
                    node
                    for node in place_order_node.body
                    if node is not eventbridge_assignment and node is not event_publish
                ]
                bus_index = place_order_node.body.index(bus_assignment)
                place_order_node.body.insert(
                    bus_index + 1,
                    ast.If(
                        test=ast.BoolOp(
                            op=ast.Or(),
                            values=[
                                ast.Compare(
                                    left=ast.Name(id="eventbridge_client", ctx=ast.Load()),
                                    ops=[ast.IsNot()],
                                    comparators=[ast.Constant(value=None)],
                                ),
                                ast.Name(id="bus_name", ctx=ast.Load()),
                            ],
                        ),
                        body=[eventbridge_assignment, event_publish],
                        orelse=[],
                    ),
                )

    ast.fix_missing_locations(projected)
    result = ast.unparse(projected) + "\n"
    forbidden = (
        "EVENT_BUS_NAME",
        "_eventbridge_client",
        "eventbridge_client",
        "_build_order_placed_event",
        ".put_events",
    )
    remaining = [] if include_eventbridge else [token for token in forbidden if token in result]
    if remaining:
        raise ValueError(
            "Could not project the final Lambda handler back to Stage 13; "
            f"remaining EventBridge tokens: {remaining}."
        )
    required_continuity = (
        "InventoryLookupError = InventoryShortageError",
        "def _cursor_for_connection(connection):",
        "if sqs_client is not None or queue_url:",
    )
    if include_eventbridge:
        required_continuity += ("if eventbridge_client is not None or bus_name:",)
    missing_continuity = [token for token in required_continuity if token not in result]
    if missing_continuity:
        raise ValueError(
            "Could not preserve the Stage 12 handler contracts in the Stage 13 projection; "
            f"missing: {missing_continuity}."
        )
    return result


def _project_stage13_lambda_handler(source: str) -> str:
    """Remove Stage 14 EventBridge behavior from the proven final handler."""
    return _project_reference_lambda_handler(source, include_eventbridge=False)


def _project_stage11_sqlite_test(source: str) -> str:
    """Strip later-stage publisher fakes/keywords so the SQLite proof matches the Stage 11/12 order API."""
    tree = ast.parse(source, filename="tests/test_sqlite_orders.py")

    class PrePublisherProjection(ast.NodeTransformer):
        def visit_ClassDef(self, node: ast.ClassDef) -> ast.AST | None:
            if node.name in {"FakeSqsClient", "FakeEventBridgeClient"}:
                return None
            return self.generic_visit(node)

        def visit_Call(self, node: ast.Call) -> ast.AST:
            node = self.generic_visit(node)
            assert isinstance(node, ast.Call)
            node.keywords = [
                keyword for keyword in node.keywords
                if keyword.arg not in {"sqs_client", "eventbridge_client"}
            ]
            return node

    projected = PrePublisherProjection().visit(tree)
    ast.fix_missing_locations(projected)
    return ast.unparse(projected) + "\n"


def _project_stage13_test_source(source: str, path: str) -> str:
    """Remove Stage 14 fakes/assertions from final publisher tests without weakening SQS proofs."""
    tree = ast.parse(source, filename=path)

    def referenced_names(node: ast.AST) -> set[str]:
        return {item.id for item in ast.walk(node) if isinstance(item, ast.Name)}

    class Stage13TestProjection(ast.NodeTransformer):
        def visit_ClassDef(self, node: ast.ClassDef) -> ast.AST | None:
            if node.name == "FakeEventBridgeClient":
                return None
            return self.generic_visit(node)

        def visit_Assign(self, node: ast.Assign) -> ast.AST | None:
            assigned = {
                target.id
                for target in node.targets
                if isinstance(target, ast.Name)
            }
            if assigned & {"events", "event_entry"}:
                return None
            if (
                isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Name)
                and node.value.func.id == "FakeEventBridgeClient"
            ):
                return None
            return self.generic_visit(node)

        def visit_Expr(self, node: ast.Expr) -> ast.AST | None:
            node = self.generic_visit(node)
            assert isinstance(node, ast.Expr)
            if referenced_names(node) & {"events", "event_entry"}:
                return None
            return node

        def visit_Call(self, node: ast.Call) -> ast.AST:
            node = self.generic_visit(node)
            assert isinstance(node, ast.Call)
            node.keywords = [
                keyword for keyword in node.keywords if keyword.arg != "eventbridge_client"
            ]
            return node

        def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
            node = self.generic_visit(node)
            assert isinstance(node, ast.FunctionDef)
            node.name = node.name.replace("and_domain_event", "after_commit").replace(
                "_or_event", ""
            )
            if not node.body:
                node.body = [ast.Pass()]
            return node

    projected = Stage13TestProjection().visit(tree)
    assert isinstance(projected, ast.Module)
    ast.fix_missing_locations(projected)
    result = ast.unparse(projected) + "\n"
    if "eventbridge" in result.lower() or "put_events" in result:
        raise ValueError(f"Could not remove Stage 14 behavior from {path}.")
    return result


def _repair_stable_reference_artifacts(snapshot: dict[str, str]) -> dict[str, str]:
    """Apply deterministic corrections discovered by executable reference preflight."""
    repaired = dict(snapshot)
    fake_queue_url = "https://sqs.us-east-1.amazonaws.com/123456789012/pick-work"
    for path in ("deploy/container-worker/README.md", "docs/demo-runbook.md"):
        content = repaired.get(path)
        if content is not None:
            repaired[path] = content.replace(fake_queue_url, "$PICK_WORK_QUEUE_URL")
    worker_environment = repaired.get("deploy/pick-ticket-worker/environment.example")
    if worker_environment is not None:
        repaired["deploy/pick-ticket-worker/environment.example"] = re.sub(
            r"(?m)^TINYWMS_QUEUE_URL=.*$",
            "TINYWMS_QUEUE_URL=",
            worker_environment,
        )

    worker = repaired.get("src/pick_ticket_worker.py")
    if worker is not None:
        repaired["src/pick_ticket_worker.py"] = worker.replace(
            "return 130 if stop_requested and not args.once else 0",
            "return 0",
        )

    worker_test = repaired.get("tests/test_pick_ticket_worker.py")
    if worker_test is not None:
        worker_test = worker_test.replace(
            "if not self.batches:\n            return 0",
            "if not self.batches:\n            raise KeyboardInterrupt",
        )
        worker_test = worker_test.replace(
            "        self.calls += 1\n"
            "        if not self.batches:\n"
            "            raise KeyboardInterrupt",
            "        if not self.batches:\n"
            "            raise KeyboardInterrupt\n"
            "        self.calls += 1",
        )
        repaired["tests/test_pick_ticket_worker.py"] = worker_test

    runbook_test = repaired.get("tests/test_demo_runbook.py")
    if runbook_test is not None:
        repaired["tests/test_demo_runbook.py"] = runbook_test.replace(
            "[block for block in text.split('## Session ') if block.strip()]",
            "[block for block in text.split('## Session ')[1:] if block.strip()]",
        )

    if "docs/demo-runbook.md" in repaired:
        repaired["docs/demo-runbook.md"] = _course_demo_runbook()

    if "tests/test_web_app.js" in repaired:
        repaired["tests/test_web_app.js"] = r"""import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(fileURLToPath(new URL('..', import.meta.url)));
const app = readFileSync(resolve(root, 'src/web/app.js'), 'utf8');
const index = readFileSync(resolve(root, 'src/web/index.html'), 'utf8');
const style = readFileSync(resolve(root, 'src/web/style.css'), 'utf8');

test('browser inventory uses same-origin or a runtime override', () => {
  assert.match(app, /window\.TINYWMS_API_BASE_URL/);
  assert.match(app, /window\.location\.origin/);
  assert.match(app, /new URL\('\/inventory'/);
  assert.doesNotMatch(app, /127\.0\.0\.1:8000/);
});

test('inventory page submits visible order JSON with POST', () => {
  assert.match(app, /new URL\('\/orders'/);
  assert.match(app, /method:\s*'POST'/);
  assert.match(app, /JSON\.stringify\(payload\)/);
  assert.match(index, /order-json/);
  assert.match(index, /response-json/);
  assert.match(style, /#response-json/);
});

test('accepted order refreshes the rendered inventory', () => {
  assert.match(app, /responseJson\.textContent/);
  assert.match(app, /await loadInventory\(\)/);
  assert.match(app, /form\.addEventListener\('submit', submitOrder\)/);
  assert.match(app, /renderInventory/);
});
"""

    http_test = repaired.get("tests/test_http_server.py")
    if http_test is not None:
        http_test = http_test.replace("env['TINYWMS_PORT'] = '8123'", "env['TINYWMS_PORT'] = '0'")
        http_test = http_test.replace(
            "            time.sleep(1)\n"
            "            with urllib.request.urlopen('http://127.0.0.1:8123/inventory') as response:\n",
            "            assert proc.stdout is not None\n"
            "            readiness = proc.stdout.readline().strip()\n"
            "            self.assertIn('listening on', readiness)\n"
            "            port = int(readiness.rsplit(' ', 1)[-1])\n"
            "            with urllib.request.urlopen(f'http://127.0.0.1:{port}/inventory') as response:\n",
        )
        repaired["tests/test_http_server.py"] = http_test

    return repaired


def _forward_reference_snapshot(
    stage_name: str,
    reference_snapshot: dict[str, str],
) -> dict[str, str]:
    """Return the mature reference as it is allowed to appear in a given lesson."""
    projected = _repair_stable_reference_artifacts(reference_snapshot)
    stage_num = _stage_number(stage_name)
    if stage_num is not None and stage_num in (11, 12):
        sqlite_test = projected.get("tests/test_sqlite_orders.py")
        if sqlite_test is not None:
            projected["tests/test_sqlite_orders.py"] = _project_stage11_sqlite_test(sqlite_test)
    if stage_num is None or stage_num < 13:
        return projected
    handler = projected.get("src/lambda_inventory.py")
    if handler is None:
        raise ValueError("Final reference is missing src/lambda_inventory.py for forward projection.")
    projected["src/lambda_inventory.py"] = _project_reference_lambda_handler(
        handler,
        include_eventbridge=stage_num >= 14,
    )
    if stage_num == 13:
        for path in (
            "tests/test_lambda_inventory.py",
            "tests/test_concurrency.py",
            "tests/test_sqlite_orders.py",
        ):
            source = projected.get(path)
            if source is None:
                raise ValueError(f"Final reference is missing {path} for Stage 13 projection.")
            projected[path] = _project_stage13_test_source(source, path)
    return projected


def _forward_reference_context_exclusions(stage_name: str) -> set[str]:
    """Hide mature files whose later behavior would leak into an earlier lesson."""
    if stage_name == "11-orders":
        return {
            "src/lambda_inventory.py",
            "tests/test_lambda_inventory.py",
            "tests/test_orders.py",
            "tests/test_sqlite_orders.py",
            "tests/test_concurrency.py",
        }
    if stage_name == "13-sqs":
        return {"tests/test_orders.py"}
    return set()


def _snapshot_delta_plan(
    stage_name: str,
    baseline_files: dict[str, str] | None,
    candidate: dict[str, str],
    *,
    summary: str,
) -> dict[str, Any]:
    """Turn an existing stage snapshot into a deterministic plan against the current checkpoint."""
    baseline = baseline_files or {}
    return {
        "stages": [
            {
                "name": stage_name,
                "summary": summary,
                "files": [
                    {"path": path, "content": content}
                    for path, content in sorted(candidate.items())
                    if baseline.get(path) != content
                ],
                "delete_files": sorted(set(baseline) - set(candidate)),
            }
        ]
    }


def _cached_stage_delta_plan(output_root: Path, prompt_path: Path) -> dict[str, Any]:
    """Recover only the recorded delta from an older generated stage, never its stale baseline."""
    stage_dir = output_root / prompt_path.stem
    manifest = json.loads((stage_dir / MANIFEST_NAME).read_text(encoding="utf-8"))
    changed_files = manifest.get("changed_files")
    deleted_files = manifest.get("deleted_files")
    if not isinstance(changed_files, list) or not isinstance(deleted_files, list):
        raise ValueError(f"Cached stage {prompt_path.stem} has no reusable file delta.")
    files: list[dict[str, str]] = []
    for relative_name in changed_files:
        if not isinstance(relative_name, str):
            raise ValueError(f"Cached stage {prompt_path.stem} has an invalid changed path.")
        target = _output_path(stage_dir, relative_name)
        if not target.is_file():
            raise ValueError(
                f"Cached stage {prompt_path.stem} is missing changed file {relative_name}."
            )
        files.append({"path": relative_name, "content": target.read_text(encoding="utf-8")})
    summary = manifest.get("summary")
    if not isinstance(summary, str):
        summary = "Reuse the existing teaching delta with preflighted reference components."
    return {
        "stages": [
            {
                "name": prompt_path.stem,
                "summary": summary,
                "files": files,
                "delete_files": deleted_files,
            }
        ]
    }


def _execute_snapshot_tests(
    stage_name: str,
    snapshot: dict[str, str],
    *,
    python_pattern: str = "test_*.py",
    run_web_test: bool = True,
    python_timeout_seconds: float = 120,
) -> None:
    """Run a materialized stage's safe local Python and browser suites before acceptance."""
    with tempfile.TemporaryDirectory(prefix="tinywms-forward-preflight-") as tmpdir:
        root = Path(tmpdir)
        for relative_name, content in snapshot.items():
            target = _output_path(root, relative_name)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        has_python_tests = any(
            Path(path).match(f"tests/{python_pattern}") for path in snapshot
        )
        has_runnable_code = any(
            path.startswith("src/") and path.endswith((".py", ".js")) for path in snapshot
        )
        if has_runnable_code and not has_python_tests:
            raise ValueError(
                f"Stage {stage_name} contains runnable code under src/ but no tests/{python_pattern}; "
                "every runnable stage must carry its inherited Python tests (for example "
                "tests/test_inventory_cli.py, tests/test_linux_visible.py, tests/test_http_server.py) "
                "and add tests for what it introduces."
            )
        if has_python_tests:
            try:
                python_result = subprocess.run(
                    [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", python_pattern],
                    cwd=root,
                    env=environment,
                    text=True,
                    capture_output=True,
                    timeout=python_timeout_seconds,
                    check=False,
                )
            except subprocess.TimeoutExpired as error:
                stdout = error.stdout.decode(errors="replace") if isinstance(error.stdout, bytes) else error.stdout or ""
                stderr = error.stderr.decode(errors="replace") if isinstance(error.stderr, bytes) else error.stderr or ""
                detail = (stdout + stderr)[-4_000:]
                raise ValueError(
                    f"Stage {stage_name} safe local Python tests timed out after "
                    f"{python_timeout_seconds:g} seconds before checkpoint acceptance. "
                    "A service-loop test must arrange its own bounded shutdown: start the shared "
                    "stop flag false, make the first poll empty, deliver a later message, then set "
                    f"the flag true.\n{detail}"
                ) from error
            if python_result.returncode != 0:
                detail = (python_result.stdout + python_result.stderr)[-12_000:]
                raise ValueError(
                    f"Stage {stage_name} safe local Python tests failed before checkpoint acceptance.\n{detail}"
                )

        web_test = root / "tests" / "test_web_app.js"
        if run_web_test and web_test.exists():
            node = shutil.which("node")
            if node is None:
                raise ValueError(
                    f"Stage {stage_name} requires node for tests/test_web_app.js."
                )
            node_result = subprocess.run(
                [node, "--test", "tests/test_web_app.js"],
                cwd=root,
                env=environment,
                text=True,
                capture_output=True,
                timeout=30,
                check=False,
            )
            if node_result.returncode != 0:
                detail = (node_result.stdout + node_result.stderr)[-8_000:]
                raise ValueError(
                    f"Stage {stage_name} browser tests failed before checkpoint acceptance.\n" + detail
                )


def _preflight_forward_reference(reference_snapshot: dict[str, str]) -> None:
    """Execute the projected final local suite before any forward API request."""
    snapshot = _forward_reference_snapshot("20-final-walkthrough", reference_snapshot)
    _validate_python_syntax("20-final-walkthrough", snapshot)
    _validate_test_portability("20-final-walkthrough", snapshot)
    _validate_behavior_continuity("20-final-walkthrough", snapshot)
    _execute_snapshot_tests("20-final-walkthrough reference", snapshot)


def _validate_cross_stage_test_continuity(stage_name: str, snapshot: dict[str, str]) -> None:
    """Reject proofs or documentation that became false at a later lesson boundary."""
    stage_num = _stage_number(stage_name)
    if stage_num is None:
        return
    issues: list[str] = []
    rds_test = snapshot.get("tests/test_rds_deployment.py", "")
    if stage_num >= 10 and any(
        phrase in rds_test
        for phrase in (
            "self-managed Linux database operations",
            "Self-managed Linux database versus managed RDS",
            "SQLite remains the inspectable classroom path",
        )
    ):
        issues.append("the inherited RDS proof freezes exact Stage 9 documentation prose")
    if stage_num >= 10 and rds_test and not all(
        name in rds_test
        for name in (
            "test_architecture_preserves_the_managed_rds_shift",
            "test_data_contracts_preserve_the_hosting_and_column_contract",
        )
    ):
        issues.append("the inherited RDS proof does not separately preserve architecture and contract meaning")
    relational_test = snapshot.get("tests/test_relational_persistence.py", "")
    if stage_num >= 11 and any(
        phrase in relational_test
        for phrase in (
            "assertNotIn('orders ('",
            'assertNotIn("orders ("',
            "assertNotIn('order_lines'",
            'assertNotIn("order_lines"',
        )
    ):
        issues.append("the inherited relational proof still forbids Stage 11 order tables")
    if stage_num in (11, 12):
        handler = snapshot.get("src/lambda_inventory.py", "")
        if "def _cursor_for_connection(connection):" not in handler or "_cursor_for_connection(connection)" not in handler:
            issues.append("the order handler does not route SQLite cursors through the placeholder adapter")
    contracts = snapshot.get("docs/data-contracts.md", "")
    if stage_num >= 11 and "`bin_location` maps to the SQL `bin` column" in contracts:
        issues.append("docs/data-contracts.md maps bin_location to the obsolete SQL bin column")
    if issues:
        raise ValueError(f"Stage {stage_name} cross-stage continuity audit failed: " + "; ".join(issues) + ".")


def _validate_materialized_stage(stage_name: str, snapshot: dict[str, str]) -> None:
    _validate_readme_contract(stage_name, snapshot)
    _validate_python_syntax(stage_name, snapshot)
    _validate_aws_artifact_continuity(stage_name, snapshot)
    _validate_stage18_constraints(stage_name, snapshot)
    _validate_deployability_audit(stage_name, snapshot)
    _validate_relational_teaching(stage_name, snapshot)
    _validate_behavior_continuity(stage_name, snapshot)
    _validate_test_portability(stage_name, snapshot)
    _validate_web_node_test(stage_name, snapshot)
    _validate_concurrency_demo(stage_name, snapshot)
    _validate_student_exercises(stage_name, snapshot)
    _validate_operations_teaching(stage_name, snapshot)
    _validate_cross_stage_test_continuity(stage_name, snapshot)
    _validate_handoff_notes(stage_name, snapshot)


def _remove_stale_generated_files(output_dir: Path, current_files: set[str]) -> None:
    manifest_path = output_dir / MANIFEST_NAME
    if not manifest_path.exists():
        return
    try:
        old_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return

    for relative_name in old_manifest.get("generated_files", []):
        if not isinstance(relative_name, str) or relative_name in current_files:
            continue
        stale_path = _output_path(output_dir, relative_name)
        if stale_path.is_file():
            stale_path.unlink()


def _prune_empty_directories(root: Path) -> None:
    for path in sorted(root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        if not path.is_dir():
            continue
        try:
            next(path.iterdir())
        except StopIteration:
            path.rmdir()


def load_stage_snapshot(stage_dir: Path, prompt_path: Path) -> dict[str, str]:
    """Load and verify a stage snapshot from its exact directory."""
    manifest_path = stage_dir / MANIFEST_NAME
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Generated manifest not found: {manifest_path}")

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"Generated manifest is not valid JSON: {manifest_path}") from error

    if manifest.get("stage") != prompt_path.stem:
        raise ValueError(f"Generated manifest has the wrong stage: {manifest_path}")
    if manifest.get("source_prompt") != prompt_path.name:
        raise ValueError(f"Generated manifest has the wrong source prompt: {manifest_path}")
    generated_files = manifest.get("generated_files")
    if not isinstance(generated_files, list):
        raise ValueError(f"Generated manifest has no file list: {manifest_path}")

    snapshot: dict[str, str] = {}
    for relative_name in generated_files:
        if not isinstance(relative_name, str):
            raise ValueError(f"Generated manifest contains an invalid path: {manifest_path}")
        target = _output_path(stage_dir, relative_name)
        if not target.is_file():
            raise FileNotFoundError(f"Generated file recorded by the manifest is missing: {target}")
        snapshot[_safe_path(relative_name).as_posix()] = target.read_text(encoding="utf-8")
    return snapshot


def load_generated_snapshot(output_root: Path, prompt_path: Path) -> dict[str, str]:
    """Load a generated stage from its conventional directory under an output root."""
    return load_stage_snapshot(output_root / prompt_path.stem, prompt_path)


def find_resume_index(output_root: Path, prompt_paths: list[Path], target_index: int) -> int:
    """Return the latest valid contiguous stage at or before the requested target."""
    latest = -1
    for index, prompt_path in enumerate(prompt_paths[: target_index + 1]):
        manifest_path = output_root / prompt_path.stem / MANIFEST_NAME
        if not manifest_path.exists():
            break
        load_generated_snapshot(output_root, prompt_path)
        latest = index
    return latest


def materialize_plan(
    stages: list[dict[str, Any]],
    prompt_paths: list[Path],
    output_root: Path,
    model: str,
    output_dirs: list[Path] | None = None,
    baseline_stage: str | None = None,
    baseline_files: dict[str, str] | None = None,
    additional_stage_validator: StageSnapshotValidator | None = None,
) -> list[Path]:
    """Apply model deltas in memory and write a complete, comparable snapshot per stage."""
    snapshot: dict[str, str] = dict(baseline_files or {})
    snapshots: list[dict[str, str]] = []
    transitions: list[tuple[list[str], list[str]]] = []
    generated_dirs: list[Path] = []

    for stage_index, stage in enumerate(stages):
        stage_baseline = snapshot.copy()
        changed_files: list[str] = []
        deleted_files: list[str] = []

        for relative_name in stage["delete_files"]:
            normalized = _safe_path(relative_name).as_posix()
            snapshot.pop(normalized, None)
            deleted_files.append(normalized)
        for item in stage["files"]:
            normalized = _safe_path(item["path"]).as_posix()
            snapshot[normalized] = item["content"]
            changed_files.append(normalized)

        if _prune_missing_readme_file_map_entries(snapshot) and "README.md" not in changed_files:
            changed_files.append("README.md")

        existing_notes = _load_handoff_notes_from_snapshot(snapshot)
        stage_note = _build_stage_handoff_note(stage, snapshot)
        merged_notes = _merge_handoff_notes(existing_notes, stage_note)
        snapshot[HANDOFF_NOTES_PATH] = _serialize_handoff_notes(stage["name"], merged_notes)
        if HANDOFF_NOTES_PATH not in changed_files:
            changed_files.append(HANDOFF_NOTES_PATH)

        try:
            _validate_materialized_stage(stage["name"], snapshot)
            if additional_stage_validator is not None:
                additional_stage_validator(stage["name"], snapshot)
        except ValueError as error:
            raise StageValidationError(str(error), stage_index, stage_baseline) from error

        snapshots.append(snapshot.copy())
        transitions.append((changed_files, deleted_files))

    if output_dirs is not None and len(output_dirs) != len(stages):
        raise ValueError("The number of output directories must match the number of stages.")

    for index, (stage, prompt_path, stage_snapshot) in enumerate(
        zip(stages, prompt_paths, snapshots, strict=True)
    ):
        changed_files, deleted_files = transitions[index]
        output_dir = output_dirs[index] if output_dirs is not None else output_root / stage["name"]
        output_dir.mkdir(parents=True, exist_ok=True)
        _remove_stale_generated_files(output_dir, set(stage_snapshot))
        for relative_name, content in sorted(stage_snapshot.items()):
            target = _output_path(output_dir, relative_name)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

        _prune_empty_directories(output_dir)

        manifest = {
            "stage": stage["name"],
            "source_prompt": prompt_path.name,
            "model": model,
            "inherits_from": stages[index - 1]["name"] if index else baseline_stage,
            "summary": stage["summary"],
            "changed_files": changed_files,
            "deleted_files": deleted_files,
            "generated_files": sorted(stage_snapshot),
        }
        (output_dir / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        generated_dirs.append(output_dir)

    return generated_dirs


def generate_projects(
    prompt_paths: list[Path],
    all_prompt_paths: list[Path],
    output_root: Path,
    *,
    model: str = DEFAULT_MODEL,
    api_key: str | None = None,
    base_url: str = DEFAULT_BASE_URL,
    requester: PlanRequester = request_plan,
    output_dirs: list[Path] | None = None,
    baseline_stage: str | None = None,
    baseline_files: dict[str, str] | None = None,
    max_validation_retries: int = 1,
    course_blueprint: dict[str, Any] | None = None,
    extra_generation_context: str | None = None,
    additional_stage_validator: StageSnapshotValidator | None = None,
) -> list[Path]:
    """Plan requested stages, retrying only the suffix after a valid generated prefix."""
    if not prompt_paths:
        return []
    if max_validation_retries < 0:
        raise ValueError("max_validation_retries must be non-negative.")
    repository_rules = read_repository_rules(all_prompt_paths[0].parent)
    api_token = api_key if api_key is not None else os.getenv("OPENAI_API_KEY", "")
    attempts = max_validation_retries + 1
    last_error: ValueError | None = None
    retry_plan: dict[str, Any] | None = None
    accepted_stages: list[dict[str, Any]] = []
    remaining_prompt_paths = list(prompt_paths)
    retry_baseline_stage = baseline_stage
    retry_baseline_files = dict(baseline_files or {})
    all_stage_names = [path.stem for path in all_prompt_paths]

    def validate_stage(stage_name: str, snapshot: dict[str, str]) -> None:
        if course_blueprint is not None:
            validate_snapshot_against_blueprint(
                stage_name,
                snapshot,
                course_blueprint,
                all_stage_names,
            )
        if additional_stage_validator is not None:
            additional_stage_validator(stage_name, snapshot)

    for attempt in range(1, attempts + 1):
        stage_names = [path.stem for path in remaining_prompt_paths]
        context_sections: list[str] = []
        if course_blueprint is not None:
            context_sections.append(
                "COURSE BLUEPRINT SLICE\n"
                "Treat this JSON as the architectural destination and stage-scope contract. Reuse only "
                "components available at the current stage, do not copy future component implementations "
                "backward, and satisfy the listed concrete paths and continuity checks.\n"
                + blueprint_context(course_blueprint, all_stage_names, stage_names)
            )
        if extra_generation_context:
            context_sections.append(extra_generation_context)
        generation_input = build_generation_input(
            all_prompt_paths,
            remaining_prompt_paths,
            repository_rules,
            retry_baseline_stage,
            retry_baseline_files,
            "\n\n".join(context_sections),
        )
        schema = build_output_schema(stage_names)
        request_input = generation_input
        if last_error is not None:
            request_input = build_retry_generation_input(
                generation_input,
                str(last_error),
                attempt - 1,
                attempts,
                retry_plan,
            )
        plan = requester(
            request_input,
            schema,
            model,
            api_token,
            base_url,
        )
        plan = _normalize_student_exercises_in_plan(plan)
        plan = _normalize_unittest_tests_in_plan(plan)
        try:
            stages = validate_plan(plan, stage_names)
            complete_plan = [*accepted_stages, *stages]
            return materialize_plan(
                complete_plan,
                prompt_paths,
                output_root,
                model,
                output_dirs,
                baseline_stage,
                baseline_files,
                validate_stage if course_blueprint is not None or additional_stage_validator is not None else None,
            )
        except StageValidationError as error:
            suffix_error_index = error.stage_index - len(accepted_stages)
            if suffix_error_index < 0 or suffix_error_index >= len(stages):
                raise RuntimeError("Stage validation failed outside the current retry suffix.") from error
            if suffix_error_index:
                accepted_stages.extend(stages[:suffix_error_index])
                remaining_prompt_paths = remaining_prompt_paths[suffix_error_index:]
                retry_baseline_stage = accepted_stages[-1]["name"]
                retry_baseline_files = error.baseline_files
            retry_plan = {"stages": stages[suffix_error_index:]}
            last_error = error
            if attempt == attempts:
                raise
        except ValueError as error:
            retry_plan = plan
            last_error = error
            if attempt == attempts:
                raise
    assert last_error is not None
    raise last_error


def generate_app(
    prompt_path: Path,
    output_dir: Path,
    *,
    prompt_dir: Path | None = None,
    model: str = DEFAULT_MODEL,
    api_key: str | None = None,
    base_url: str = DEFAULT_BASE_URL,
    requester: PlanRequester = request_plan,
    max_validation_retries: int = 1,
) -> Path:
    """Generate one complete stage while giving the model the full course context."""
    catalog = discover_prompt_files(prompt_dir or prompt_path.parent)
    generated = generate_projects(
        [prompt_path],
        catalog,
        output_dir.parent,
        model=model,
        api_key=api_key,
        base_url=base_url,
        requester=requester,
        output_dirs=[output_dir],
        max_validation_retries=max_validation_retries,
    )[0]
    return generated


def generate_all_apps(
    prompt_dir: Path | None = None,
    output_root: Path = Path("generated"),
    *,
    model: str = DEFAULT_MODEL,
    api_key: str | None = None,
    base_url: str = DEFAULT_BASE_URL,
    requester: PlanRequester = request_plan,
    max_validation_retries: int = 1,
) -> list[Path]:
    """Generate every stage with one LLM request and cumulative file deltas."""
    catalog = discover_prompt_files(prompt_dir or PROMPT_DIR)
    return generate_projects(
        catalog,
        catalog,
        output_root,
        model=model,
        api_key=api_key,
        base_url=base_url,
        requester=requester,
        max_validation_retries=max_validation_retries,
    )


def _reference_generation_context(
    stage_names: list[str],
    baseline_files: dict[str, str] | None,
) -> str:
    sections = [blueprint_prompt_contract(stage_names)]
    if baseline_files is None:
        final_stage = stage_names[-1]
        required_aws_paths = _required_aws_artifact_paths(final_stage)
        if required_aws_paths:
            sections.append(
                "SCRATCH FINAL REFERENCE COMPLETENESS CONTRACT\n"
                "There is no predecessor snapshot. Build the cumulative final repository from an empty "
                "directory; do not assume that any file from an earlier lesson already exists. The response "
                "must include complete, runnable contents for every path below. Do not replace a required file "
                "with a prose promise, an empty template, or instructions to copy it from another stage.\n- "
                + "\n- ".join(required_aws_paths)
                + "\n\nThe individual deployment templates and guides remain visible teaching artifacts even "
                "when infra/template.yaml also provides the consolidated deployment. Keep resource names, "
                "parameters, outputs, deploy commands, verification commands, and cleanup commands consistent. "
                "Package the real src/lambda_inventory.py implementation; never substitute an inline demo handler."
            )
        return "\n\n".join(sections)

    inherited_issues = _deployability_audit_issues(baseline_files)
    if inherited_issues:
        sections.append(
            "REFERENCE SEED REPAIR REQUIREMENTS\n"
            "The checkpoint directory is read-only, but the final Stage 20 snapshot must not preserve "
            "known deployment defects. Emit complete corrected replacements for every inherited file "
            "named below in the Stage 20 delta, fixing all listed issues in the same response. Use "
            "deploy-time parameters for environment-specific subnet IDs and credentials; mark secret "
            "parameters NoEcho instead of hardcoding secrets.\n- "
            + "\n- ".join(inherited_issues)
        )
    try:
        _validate_behavior_continuity(stage_names[-1], baseline_files)
    except ValueError as error:
        sections.append(
            "REFERENCE BEHAVIOR REPAIR REQUIREMENTS\n"
            "The frozen predecessor is missing cumulative behaviors required by the final system. "
            "Replace the affected inherited source, tests, infrastructure, and guides in Stage 20 so "
            "the completed reference satisfies every item in this audit:\n"
            + str(error)
            + "\n\nREMAINING REPAIR SHAPE\n"
            "Keep these boundaries explicit in the corrected files:\n"
            "- In src/lambda_inventory.py, accept/inject SQS and EventBridge clients for local tests. "
            "After connection.commit(), call sqs_client.send_message(...) with the pick-work command "
            "and events_client.put_events(...) with a versioned OrderPlaced entry. Do neither after rollback.\n"
            "- In infra/template.yaml, point the Lambda Code block at deploy-time S3Bucket/S3Key "
            "parameters (or use SAM CodeUri); do not retain an instructional inline ZipFile stub.\n"
            "- In deploy/aws/README.md, include the exact zip/upload or CloudFormation/SAM packaging "
            "command before deployment, then resolve outputs before verification.\n"
            "- Add local injected-client tests proving commit-before-publish and no publish after rollback."
        )
    return "\n\n".join(sections)


def _scratch_reference_missing_aws_overlay(
    plan: dict[str, Any],
    stage_name: str,
    *,
    model: str,
    api_key: str,
    base_url: str,
    requester: PlanRequester,
) -> dict[str, str]:
    """Ask for only omitted cumulative AWS files in an otherwise scratch reference plan."""
    if not isinstance(plan, dict):
        return {}
    stages = plan.get("stages")
    if not isinstance(stages, list):
        return {}
    stage = next(
        (
            item
            for item in stages
            if isinstance(item, dict) and item.get("name") == stage_name
        ),
        None,
    )
    if stage is None or not isinstance(stage.get("files"), list):
        return {}

    candidate: dict[str, str] = {}
    for item in stage["files"]:
        if not isinstance(item, dict):
            continue
        path = item.get("path")
        content = item.get("content")
        if isinstance(path, str) and isinstance(content, str):
            try:
                candidate[_safe_path(path).as_posix()] = content
            except ValueError:
                continue

    required_paths = _required_aws_artifact_paths(stage_name)
    missing_paths = [path for path in required_paths if path not in candidate]
    if not missing_paths:
        return {}

    existing_paths = sorted(candidate)
    source_excerpt_sections: list[str] = []
    for path in ("src/lambda_inventory.py", "requirements.txt", "schema.sql"):
        content = candidate.get(path)
        if content is not None:
            source_excerpt_sections.append(f"--- {path} ---\n{content}")
    source_excerpts = "\n\n".join(source_excerpt_sections)
    completion_input = (
        SYSTEM_PROMPT
        + "\n\nFOCUSED SCRATCH REFERENCE COMPLETION\n"
        + f"The initial {stage_name} plan was generated from an empty directory and omitted the exact "
        "cumulative deployment files listed below. Return one stage delta named exactly "
        + repr(stage_name)
        + ". Emit complete contents for every listed path and no other paths. Do not delete anything. "
        "These are runnable teaching artifacts: use explicit parameters and outputs, exact deploy/verify/cleanup "
        "commands, inexpensive resources, and no credentials, empty Resources maps, or placeholder prose. "
        "The consolidated template must package the real Lambda source with S3Bucket/S3Key or SAM CodeUri.\n\n"
        "MISSING PATHS\n- "
        + "\n- ".join(missing_paths)
        + "\n\nFILES ALREADY PRESENT IN THE CANDIDATE (do not re-emit them)\n- "
        + "\n- ".join(existing_paths)
    )
    if source_excerpts:
        completion_input += (
            "\n\nIMPLEMENTATION EXCERPTS TO WIRE, NOT REPLACE\n" + source_excerpts
        )

    completion_plan = requester(
        completion_input,
        build_output_schema([stage_name]),
        model,
        api_key,
        base_url,
    )
    try:
        completion_stages = validate_plan(completion_plan, [stage_name])
    except (AttributeError, TypeError, ValueError):
        return {}

    requested = set(missing_paths)
    return {
        item["path"]: item["content"]
        for item in completion_stages[0]["files"]
        if item["path"] in requested
    }


def _scratch_reference_snapshot(plan: dict[str, Any], stage_name: str) -> dict[str, str]:
    """Materialize a scratch single-stage plan in memory for focused repair passes."""
    stages = validate_plan(plan, [stage_name])
    snapshot: dict[str, str] = {}
    for item in stages[0]["files"]:
        snapshot[item["path"]] = item["content"]
    for path in stages[0]["delete_files"]:
        snapshot.pop(path, None)
    return snapshot


def _reference_seed_repair_overlay(baseline_files: dict[str, str] | None) -> dict[str, str]:
    """Build narrow Stage 20 replacements for known mechanical defects in a frozen seed."""
    if baseline_files is None:
        return {}

    repairs: dict[str, str] = {}
    for template_path, template in baseline_files.items():
        if not template_path.startswith("infra/") or not template_path.endswith(".yaml"):
            continue
        if "Type: AWS::Lambda::Function" not in template or "ZipFile:" not in template:
            continue
        repaired_lambda = re.sub(
            r"^(\s*Handler:)\s*src\.[^\n]+$",
            r"\1 index.handler",
            template,
            flags=re.M,
        )
        if repaired_lambda != template:
            repairs[template_path] = repaired_lambda

    rds_path = "infra/rds.yaml"
    rds_template = baseline_files.get(rds_path)
    if rds_template is not None and (
        re.search(r"^\s*SubnetIds:\s*\[\s*\]\s*$", rds_template, flags=re.M)
        or "change-me-in-a-real-deployment" in rds_template
    ):
        parameter_block = (
            "  VpcId:\n"
            "    Type: AWS::EC2::VPC::Id\n"
            "    Description: VPC containing the database subnets.\n"
            "  DatabaseSubnetIds:\n"
            "    Type: List<AWS::EC2::Subnet::Id>\n"
            "    Description: At least two subnets in different Availability Zones.\n"
            "  DatabaseClientCidr:\n"
            "    Type: String\n"
            "    Description: CIDR allowed to connect to PostgreSQL for this lesson.\n"
            "  DatabaseMasterUsername:\n"
            "    Type: String\n"
            "    Default: tinywms\n"
            "  DatabaseMasterPassword:\n"
            "    Type: String\n"
            "    NoEcho: true\n"
            "    MinLength: 12\n"
            "    Description: Enter at deployment time; never commit this value.\n"
        )
        repaired_rds = rds_template
        if "  DatabaseSubnetIds:" not in repaired_rds:
            repaired_rds = repaired_rds.replace("Parameters:\n", "Parameters:\n" + parameter_block, 1)
        repaired_rds = re.sub(
            r"^(\s*)SecurityGroupIngress:\s*\[\s*\]\s*$",
            (
                r"\1VpcId: !Ref VpcId\n"
                r"\1SecurityGroupIngress:\n"
                r"\1  - IpProtocol: tcp\n"
                r"\1    FromPort: 5432\n"
                r"\1    ToPort: 5432\n"
                r"\1    CidrIp: !Ref DatabaseClientCidr"
            ),
            repaired_rds,
            flags=re.M,
        )
        repaired_rds = re.sub(
            r"^(\s*)SubnetIds:\s*\[\s*\]\s*$",
            r"\1SubnetIds: !Ref DatabaseSubnetIds",
            repaired_rds,
            flags=re.M,
        )
        repaired_rds = re.sub(
            r"^(\s*)MasterUsername:\s*[^\n]+$",
            r"\1MasterUsername: !Ref DatabaseMasterUsername",
            repaired_rds,
            flags=re.M,
        )
        repaired_rds = re.sub(
            r"^(\s*)MasterUserPassword:\s*[^\n]+$",
            r"\1MasterUserPassword: !Ref DatabaseMasterPassword",
            repaired_rds,
            flags=re.M,
        )
        repairs[rds_path] = repaired_rds
        repairs["deploy/rds/README.md"] = """# TinyWMS RDS deployment notes

From the stage root, resolve real values from the default VPC. The subnet query deliberately selects two
subnets; verify that they are in different Availability Zones before deploying.

## Resolve deployment inputs
```bash
VPC_ID="$(aws ec2 describe-vpcs --filters Name=isDefault,Values=true --query 'Vpcs[0].VpcId' --output text)"
SUBNET_IDS="$(aws ec2 describe-subnets --filters Name=vpc-id,Values="$VPC_ID" --query 'Subnets[:2].SubnetId' --output text | tr '\t' ',')"
CLIENT_CIDR="$(curl -fsS https://checkip.amazonaws.com)/32"
aws ec2 describe-subnets --filters Name=vpc-id,Values="$VPC_ID" --query 'Subnets[].{Subnet:SubnetId,AZ:AvailabilityZone}' --output table
printf 'Temporary TinyWMS database password: '
read -r -s DB_PASSWORD
printf '\n'
```

## Deploy
```bash
aws cloudformation deploy \
  --stack-name tinywms-rds \
  --template-file infra/rds.yaml \
  --parameter-overrides \
    VpcId="$VPC_ID" \
    DatabaseSubnetIds="$SUBNET_IDS" \
    DatabaseClientCidr="$CLIENT_CIDR" \
    DatabaseName=tinywms \
    DatabaseMasterUsername=tinywms \
    DatabaseMasterPassword="$DB_PASSWORD"
unset DB_PASSWORD
```

## Resolve outputs
```bash
DB_ENDPOINT_ADDRESS="$(aws cloudformation describe-stacks \
  --stack-name tinywms-rds \
  --query 'Stacks[0].Outputs[?OutputKey==`DbEndpointAddress`].OutputValue | [0]' \
  --output text)"
DB_ENDPOINT_PORT="$(aws cloudformation describe-stacks \
  --stack-name tinywms-rds \
  --query 'Stacks[0].Outputs[?OutputKey==`DbEndpointPort`].OutputValue | [0]' \
  --output text)"
```

## Verify
```bash
psql "host=${DB_ENDPOINT_ADDRESS} port=${DB_ENDPOINT_PORT} dbname=tinywms user=tinywms sslmode=require" -c '\\dt'
```

## Destroy
```bash
aws cloudformation delete-stack --stack-name tinywms-rds
aws cloudformation wait stack-delete-complete --stack-name tinywms-rds
```
"""

    return repairs


def _apply_stage_file_overlay(
    plan: dict[str, Any],
    stage_name: str,
    overlay: dict[str, str],
) -> dict[str, Any]:
    """Force deterministic changed files into a model plan while preserving its other deltas."""
    if not overlay or not isinstance(plan, dict):
        return plan
    stages = plan.get("stages")
    if not isinstance(stages, list):
        return plan
    for stage in stages:
        if not isinstance(stage, dict) or stage.get("name") != stage_name:
            continue
        files = stage.get("files")
        if not isinstance(files, list):
            return plan
        retained = [
            item
            for item in files
            if not isinstance(item, dict) or item.get("path") not in overlay
        ]
        retained.extend(
            {"path": path, "content": content}
            for path, content in sorted(overlay.items())
        )
        stage["files"] = retained
        delete_files = stage.get("delete_files")
        if isinstance(delete_files, list):
            stage["delete_files"] = [path for path in delete_files if path not in overlay]
        return plan
    return plan


def _preserve_inherited_stage_files(
    plan: dict[str, Any],
    stage_name: str,
    protected_paths: set[str],
) -> dict[str, Any]:
    """Discard model writes/deletions for paths a stage must reuse byte-for-byte."""
    if not protected_paths or not isinstance(plan, dict):
        return plan
    stages = plan.get("stages")
    if not isinstance(stages, list):
        return plan
    for stage in stages:
        if not isinstance(stage, dict) or stage.get("name") != stage_name:
            continue
        files = stage.get("files")
        if isinstance(files, list):
            stage["files"] = [
                item
                for item in files
                if not isinstance(item, dict) or item.get("path") not in protected_paths
            ]
        delete_files = stage.get("delete_files")
        if isinstance(delete_files, list):
            stage["delete_files"] = [
                path for path in delete_files if path not in protected_paths
            ]
        return plan
    return plan


def _preserve_inherited_paths_from_deletion(
    plan: dict[str, Any],
    stage_name: str,
    protected_paths: set[str],
) -> dict[str, Any]:
    """Keep cumulative artifacts present while still allowing explicit integration edits."""
    if not protected_paths or not isinstance(plan, dict):
        return plan
    stages = plan.get("stages")
    if not isinstance(stages, list):
        return plan
    for stage in stages:
        if not isinstance(stage, dict) or stage.get("name") != stage_name:
            continue
        delete_files = stage.get("delete_files")
        if isinstance(delete_files, list):
            stage["delete_files"] = [
                path for path in delete_files if path not in protected_paths
            ]
        return plan
    return plan


def _normalize_reference_blueprint_in_plan(
    plan: dict[str, Any],
    stage_name: str,
    stage_names: list[str],
) -> dict[str, Any]:
    """Normalize derived continuity sets in the last blueprint file emitted for the reference stage."""
    if not isinstance(plan, dict):
        return plan
    stages = plan.get("stages")
    if not isinstance(stages, list):
        return plan
    for stage in stages:
        if not isinstance(stage, dict) or stage.get("name") != stage_name:
            continue
        files = stage.get("files")
        if not isinstance(files, list):
            return plan
        for item in reversed(files):
            if not isinstance(item, dict) or item.get("path") != BLUEPRINT_NAME:
                continue
            content = item.get("content")
            if not isinstance(content, str):
                return plan
            try:
                blueprint = json.loads(content)
            except json.JSONDecodeError:
                return plan
            if not isinstance(blueprint, dict):
                return plan
            normalized = normalize_blueprint_continuity(blueprint, stage_names)
            item["content"] = json.dumps(normalized, indent=2) + "\n"
            return plan
        return plan
    return plan


def _apply_plan_stage_to_snapshot(
    snapshot: dict[str, str],
    stage: dict[str, Any],
    allowed_paths: set[str],
) -> tuple[dict[str, str], dict[str, str]]:
    """Apply one focused repair delta while preventing unrelated rewrites."""
    if stage["delete_files"]:
        raise ValueError("Focused reference repair passes may not delete inherited files.")
    candidate = dict(snapshot)
    overlay: dict[str, str] = {}
    for item in stage["files"]:
        path = _safe_path(item["path"]).as_posix()
        if path not in allowed_paths:
            raise ValueError(
                f"Focused reference repair emitted unrelated path {path!r}; allowed={sorted(allowed_paths)!r}."
            )
        candidate[path] = item["content"]
        overlay[path] = item["content"]
    if not overlay:
        raise ValueError("Focused reference repair emitted no changed files.")
    return candidate, overlay


def _focused_reference_repair_prompt(
    final_stage: str,
    label: str,
    objective: str,
    snapshot: dict[str, str],
    context_paths: set[str],
    allowed_paths: set[str],
) -> str:
    visible_files = {
        path: snapshot[path]
        for path in sorted(context_paths)
        if path in snapshot
    }
    return f"""FOCUSED FINAL-REFERENCE REPAIR: {label}

Return exactly one structured stage named {final_stage!r}. This is a narrow repair pass over a frozen
baseline before the final blueprint/documentation pass; unchanged repository files are inherited outside
this focused view, so the system rule for a standalone stage without a baseline does not apply. Preserve
the supplied contracts and working behavior. Emit complete replacement bodies only for files that
genuinely change, and emit no deletions.

OBJECTIVE
{objective}

ALLOWED CHANGED PATHS
{json.dumps(sorted(allowed_paths), indent=2)}

FOCUSED CURRENT SNAPSHOT
{json.dumps(visible_files, indent=2, sort_keys=True)}
"""


def _validate_focused_reference_group(label: str, snapshot: dict[str, str]) -> None:
    """Validate one repair concern without making it responsible for unrelated broken groups."""
    issues: list[str] = []
    handler = snapshot.get("src/lambda_inventory.py", "")
    handler_lower = handler.lower()

    if label == "integrated browser and local order HTTP path":
        app = snapshot.get("src/web/app.js", "")
        index = snapshot.get("src/web/index.html", "")
        server = snapshot.get("src/http_server.py", "")
        flow_test = snapshot.get("tests/test_http_order_flow.py", "")
        if re.search(r"https?://(?:127\.0\.0\.1|localhost)(?::\d+)?", app, re.I):
            issues.append("browser hard-codes a local API origin")
        if not _has_integrated_order_form(index, app):
            issues.append("inventory page lacks the integrated order form")
        if not _browser_refreshes_inventory_after_order(app):
            issues.append("browser does not refresh inventory after ordering")
        if "def do_POST" not in server or "/orders" not in server:
            issues.append("local HTTP server lacks POST /orders")
        if not all(token in server for token in ("index.html", "app.js")):
            issues.append("local HTTP server does not serve browser assets")
        if "TINYWMS_PORT" in server and not _has_flushed_readiness_output(server):
            issues.append(
                "local HTTP server does not flush its readiness line; make the readiness print use "
                "print(..., flush=True)"
            )
        if not all(token in flow_test for token in ("/inventory", "/orders", "quantity")):
            issues.append("local HTTP order-flow test is missing")
        web_test = snapshot.get("tests/test_web_app.js", "")
        if "node:test" not in web_test or "app.js" not in web_test:
            issues.append("Node web-app safety test is missing")

    elif label == "database transactions and concurrency":
        for token, message in (
            ("psycopg", "PostgreSQL driver is missing"),
            ("select", "inventory SELECT is missing"),
            ("insert into orders", "order INSERT is missing"),
            ("insert into order_lines", "order-line INSERT is missing"),
            ("commit", "commit is missing"),
            ("rollback", "rollback is missing"),
        ):
            if token not in handler_lower:
                issues.append(message)
        concurrency_test = snapshot.get("tests/test_concurrency.py", "").lower()
        if not any(token in handler_lower for token in ("for update", "quantity >=", "begin immediate")):
            issues.append("concurrency guard is missing")
        if not any(token in concurrency_test for token in ("thread", "barrier", "concurrent.futures")):
            issues.append("overlapping concurrency test is missing")

    elif label == "portable relational schema and row normalization":
        issues.extend(
            issue
            for issue in _relational_teaching_issues("20-final-walkthrough", snapshot)
            if not issue.startswith("tests/test_sqlite_orders.py")
        )

    elif label == "real SQLite order persistence and rollback proof":
        issues.extend(
            issue
            for issue in _relational_teaching_issues("20-final-walkthrough", snapshot)
            if issue.startswith("tests/test_sqlite_orders.py")
        )

    elif label == "database-derived pick-work commands and real SQS acknowledgement":
        consumer = snapshot.get("src/sqs_consumer.py", "")
        consumer_test = snapshot.get("tests/test_sqs_consumer.py", "").lower()
        if ".send_message(" not in handler or "command_id" not in handler:
            issues.append("versioned SQS command publishing is missing")
        if "description" not in handler:
            issues.append("pick-work description propagation is missing")
        if re.search(r"['\"]bin['\"]\s*:\s*['\"][A-Za-z]+\d+-\d+['\"]", handler):
            issues.append("pick-work bin is hard-coded")
        if not _has_send_message_inside_loop(handler):
            issues.append("one-command-per-line publishing is missing")
        concurrency_test = snapshot.get("tests/test_concurrency.py", "")
        if "SELECT sku, description, bin" in handler and "SELECT sku, quantity" in concurrency_test:
            issues.append("concurrency fake still expects the obsolete locked-row query")
        for token in (".receive_message(", "WaitTimeSeconds", ".delete_message("):
            if token not in consumer:
                issues.append(f"SQS consumer is missing {token}")
        if not re.search(r"def\s+consume_messages\s*\(", consumer):
            issues.append("SQS consumer must expose def consume_messages(...)")
        if re.search(r"while\s+True\s*:", consumer):
            issues.append(
                "consume_messages(...) must perform exactly one long poll; the Stage 15 worker owns the service loop"
            )
        if not _has_sqs_fake_client_behavior_tests(consumer_test):
            issues.append(
                "SQS fake-client behavior tests are incomplete; include at least three test_ methods "
                "covering receive_message/delete_message success, callback failure without delete, "
                "and processing each of multiple messages"
            )

    elif label == "EventBridge fan-out and independent delivered-event consumers":
        template = snapshot.get("infra/events.yaml", "")
        if ".put_events(" not in handler:
            issues.append("OrderPlaced put_events publishing is missing")
        if template.count("AWS::Events::Rule") < 2:
            issues.append("two EventBridge rules are missing")
        if template.count("AWS::SQS::Queue") < 2 or "AWS::SQS::QueuePolicy" not in template:
            issues.append("two observable targets and their policy are missing")
        for path in ("src/event_consumer_a.py", "src/event_consumer_b.py"):
            source = snapshot.get(path, "")
            if ".receive_message(" not in source or "json.loads" not in source:
                issues.append(f"{path} does not receive/decode events")
        event_test = snapshot.get("tests/test_event_consumers.py", "").lower()
        if not all(token in event_test for token in ("consumer_a", "consumer_b", "receive_message")):
            issues.append("independent event-consumer tests are missing")
        for publisher_test_path in ("tests/test_orders.py", "tests/test_concurrency.py"):
            issues.extend(
                _publisher_injection_issues(
                    snapshot.get(publisher_test_path, ""),
                    publisher_test_path,
                )
            )

    elif label == "long-running idempotent pick-ticket worker":
        worker = snapshot.get("src/pick_ticket_worker.py", "")
        worker_test = snapshot.get("tests/test_pick_ticket_worker.py", "")
        consumer = snapshot.get("src/sqs_consumer.py", "")
        if not _worker_uses_sqs_receive_delete(worker, consumer):
            issues.append(
                "pick-ticket worker must either call SQS receive/delete directly or reuse "
                "sqs_consumer.consume_messages(...)"
            )
        if "consume_messages(" in worker and re.search(
            r"json\.loads\s*\([^\n]*(?:\[['\"]Body['\"]\]|\.get\(['\"]Body['\"])",
            worker,
        ):
            issues.append(
                "consume_messages(...) passes decoded JSON to the worker callback; do not decode message['Body'] again"
            )
        for token in ("--once", "command_id"):
            if token not in worker:
                issues.append(f"pick-ticket worker is missing {token}")
        if not re.search(r"\bwhile\b", worker):
            issues.append("pick-ticket worker has no service loop")
        if not any(token in worker.lower() for token in ("processed", "idemp", "duplicate")):
            issues.append("pick-ticket worker has no visible idempotency state")
        if not _worker_has_durable_idempotency_state(worker):
            issues.append("pick-ticket worker idempotency state is not durable")
        if re.search(r"if\s+once\s+or\s+not\s+messages", worker):
            issues.append("pick-ticket worker exits service mode after an empty poll")
        if "SIGTERM" not in worker or "signal.signal" not in worker:
            issues.append("pick-ticket worker lacks orderly SIGTERM handling")
        if not _has_worker_behavior_tests(worker_test):
            issues.append(
                "pick-ticket worker tests are incomplete; use at least five descriptive test_ methods "
                "covering multiple messages, duplicate restart, failure/no-delete, empty service polls, "
                "and bounded --once execution; an empty-poll service test must start with stop_flag false "
                "and flip that same shared flag true after a later delivery"
            )
        try:
            _validate_operations_teaching("15-pick-ticket-worker", snapshot)
        except ValueError as error:
            issues.append(str(error))

    elif label == "executable local callback proof":
        callback_source = snapshot.get("tests/test_callback_integration.py", "")
        callback_test = callback_source.lower()
        callback_signals = {
            "inventory": ("/inventory", "inventory"),
            "order": ("/orders", "order"),
            "quantity": ("quantity",),
            "command ID": ("command_id",),
            "ticket output": ("pick-tickets", "pick_tickets", "ticket_path"),
        }
        missing = [
            name
            for name, alternatives in callback_signals.items()
            if not any(token in callback_test for token in alternatives)
        ]
        if missing:
            issues.append("local callback integration proof is incomplete; missing " + ", ".join(missing))
        if not any(token in callback_test for token in ("urlopen", "httpconnection")):
            issues.append("local callback proof bypasses HTTP")
        if not any(token in callback_test for token in ("patch", "tinywms_inventory_path")):
            issues.append("local callback proof does not isolate inventory state")
        if not _callback_invokes_worker_consumption(
            callback_source,
            snapshot.get("src/pick_ticket_worker.py", ""),
            snapshot.get("src/sqs_consumer.py", ""),
        ):
            issues.append("local callback proof does not invoke worker consumption")
        if _local_http_body_expects_lambda_envelope(callback_source):
            issues.append("local callback proof expects a Lambda statusCode envelope from the local HTTP response")
        if "lambda_inventory" not in callback_test:
            issues.append("local callback proof fabricates the command instead of invoking the real order publisher")

    elif label == "persistent container worker demonstration":
        try:
            _validate_operations_teaching("17-container-worker", snapshot)
        except ValueError as error:
            issues.append(str(error))

    elif label == "consolidated deployment wiring and Lambda packaging":
        template = snapshot.get("infra/template.yaml", "")
        deploy_guide = snapshot.get("deploy/aws/README.md", "")
        package_script = snapshot.get("deploy/aws/package_lambda.sh", "")
        issues.extend(
            _deployability_audit_issues(
                {
                    "infra/template.yaml": template,
                    "deploy/aws/README.md": deploy_guide,
                }
            )
        )
        for token in (
            "S3Bucket:",
            "S3Key:",
            "DATABASE_URL",
            "PICK_WORK_QUEUE_URL",
            "EVENT_BUS_NAME",
            "sqs:SendMessage",
            "events:PutEvents",
        ):
            if token not in template:
                issues.append(f"deployment template is missing {token}")
        issues.extend(_consolidated_deployment_wiring_issues(template, handler))
        if not re.search(r"boto3\.client\(\s*['\"]sqs['\"]", handler):
            issues.append("production SQS client construction is missing")
        if not re.search(r"boto3\.client\(\s*['\"](?:events|eventbridge)['\"]", handler):
            issues.append("production EventBridge client construction is missing")
        if not any(token in deploy_guide for token in ("aws s3 cp", "sam build", "sam deploy")):
            issues.append("real Lambda packaging command is missing")
        handler_match = re.search(r"^\s*Handler:\s*([^\s#]+)", template, re.M)
        if handler_match and handler_match.group(1).startswith("src."):
            if re.search(r"cp\s+[^\n]*src/lambda_inventory\.py\s+['\"]?\$\{?BUILD_DIR\}?/?['\"]?", package_script):
                issues.append("configured src handler does not match root-packaged module")
        if "db_adapter" in handler and "src/db_adapter.py" not in package_script:
            issues.append("Lambda package omits imported src/db_adapter.py")
        deployment_test = snapshot.get("tests/test_deployment_wiring.py", "")
        missing_test_markers = [
            token
            for token in (
                "DATABASE_URL",
                "PICK_WORK_QUEUE_URL",
                "EVENT_BUS_NAME",
                "sqs:SendMessage",
                "events:PutEvents",
            )
            if token not in deployment_test
        ]
        if missing_test_markers:
            issues.append(
                "deployment wiring tests must prove the template environment/IAM markers: "
                + ", ".join(missing_test_markers)
            )
        if not _has_behavioral_boto_client_tests(deployment_test):
            issues.append(
                "deployment wiring tests must import lambda_inventory, patch/fake boto3, call "
                "_sqs_client() and _eventbridge_client(), and assert client('sqs')/client('events') calls; "
                "do not assert optional exception-message prose in source text"
            )
        issues.extend(_deployment_test_literal_issues(deployment_test, template, deploy_guide))

    elif label == "final executable walkthrough proof":
        callback_test = snapshot.get("tests/test_callback_integration.py", "").lower()
        deployment_test = snapshot.get("tests/test_deployment_wiring.py", "")
        walkthrough_test = snapshot.get("tests/test_end_to_end_walkthrough.py", "")
        walkthrough_test_lower = walkthrough_test.lower()
        walkthrough = snapshot.get("docs/end-to-end.md", "")
        if not all(
            any(token in callback_test for token in alternatives)
            for alternatives in (
                ("/inventory", "inventory"),
                ("/orders", "order"),
                ("quantity",),
                ("command_id",),
                ("pick-tickets", "pick_tickets", "ticket_path"),
            )
        ):
            issues.append("final callback proof is incomplete")
        if not all(
            token in deployment_test
            for token in (
                "DATABASE_URL",
                "PICK_WORK_QUEUE_URL",
                "EVENT_BUS_NAME",
                "sqs:SendMessage",
                "events:PutEvents",
            )
        ):
            issues.append("final deployment-wiring proof is incomplete")
        reads_walkthrough = "end-to-end.md" in walkthrough_test_lower and "docs" in walkthrough_test_lower
        required_boundaries = (
            ("browser",),
            ("api gateway", "api-gateway", "apigateway"),
            ("lambda",),
            ("rds",),
            ("sqs",),
            ("eventbridge", "event bridge"),
            ("pick-ticket", "pick ticket", "pick_ticket"),
        )
        if not reads_walkthrough or not all(
            any(token in walkthrough_test_lower for token in alternatives)
            for alternatives in required_boundaries
        ):
            issues.append(
                "tests/test_end_to_end_walkthrough.py is missing or does not check every documented boundary"
            )
        for token in ("browser", "API Gateway", "Lambda", "RDS", "SQS", "EventBridge", "pick-ticket"):
            if token not in walkthrough:
                issues.append(f"walkthrough omits {token}")

    elif label == "honest course operations and 26-session demo runbook":
        try:
            _validate_operations_teaching("20-final-walkthrough", snapshot)
        except ValueError as error:
            issues.append(str(error))
        try:
            _validate_student_exercises("20-final-walkthrough", snapshot)
            _validate_web_node_test("20-final-walkthrough", snapshot)
        except ValueError as error:
            issues.append(str(error))

    if issues:
        raise ValueError("; ".join(issues))


def _repair_reference_behavior_groups(
    baseline_files: dict[str, str],
    final_stage: str,
    *,
    model: str,
    api_token: str,
    base_url: str,
    requester: PlanRequester,
    max_validation_retries: int = 1,
    on_group_complete: Callable[[dict[str, str], dict[str, str]], None] | None = None,
    on_group_progress: Callable[[dict[str, str], dict[str, str]], None] | None = None,
) -> tuple[dict[str, str], dict[str, str]]:
    """Repair the broad final seed through small, independently validated requests."""
    groups = [
        {
            "label": "integrated browser and local order HTTP path",
            "validation_stage": "11-orders",
            "objective": (
                "Evolve the inherited inventory browser into one plain HTML page that displays inventory. "
                "Put the order controls in a canonical <form id=\"order-form\">, register its submit "
                "behavior in app.js, submit visible JSON to POST /orders, display the response, and refresh GET /inventory "
                "after acceptance. Define one canonical async loadInventory() function, call it once at startup, "
                "and await loadInventory() again only after an accepted POST response. Use same-origin URLs "
                "with an explicit runtime override and no hard-coded "
                "localhost. Evolve the standard-library HTTP server to serve index.html/app.js/style.css and "
                "handle local GET /inventory plus POST /orders. Add tests/test_http_order_flow.py that starts "
                "the server on an ephemeral port, submits an order, and proves the subsequent inventory "
                "quantity changed. Print the reported OS-assigned port with the literal keyword argument "
                "flush=True (for example, print(..., flush=True)) and isolate mutable "
                "inventory in a temporary file. Add tests/test_web_app.js using Node's built-in node:test "
                "module with no packages or network. Preserve the deployed Lambda/RDS transaction path and JSON contracts."
            ),
            "allowed": {
                "src/web/index.html",
                "src/web/app.js",
                "src/web/style.css",
                "src/http_server.py",
                "tests/test_browser_assets.py",
                "tests/test_http_server.py",
                "tests/test_http_order_flow.py",
                "tests/test_web_app.js",
                "docs/architecture.md",
                "docs/data-contracts.md",
            },
            "context": {
                "src/web/index.html",
                "src/web/app.js",
                "src/web/style.css",
                "src/http_server.py",
                "src/lambda_inventory.py",
                "tests/test_browser_assets.py",
                "tests/test_http_server.py",
                "tests/test_web_app.js",
                "tests/test_orders.py",
                "data/inventory.json",
                "data/orders.schema.json",
                "docs/architecture.md",
                "docs/data-contracts.md",
            },
        },
        {
            "label": "database transactions and concurrency",
            "validation_stage": "12-concurrency",
            "objective": (
                "Implement a real PostgreSQL/RDS inventory query and transactional POST /orders path. "
                "Keep SQL visible: insert orders and order_lines, lock rows with SELECT ... FOR UPDATE "
                "or use an atomic guarded decrement, commit success, and rollback rejection/failure. "
                "Use an injected connection in local tests. tests/test_concurrency.py must launch "
                "overlapping attempts with threads and a barrier and prove inventory cannot be oversold. "
                "Declare the small PostgreSQL driver dependency in requirements.txt. Keep local imports "
                "and tests runnable without that package by importing the driver inside the real connection "
                "factory or handling its absence until a deployed connection is requested."
            ),
            "allowed": {
                "src/lambda_inventory.py",
                "tests/test_lambda_inventory.py",
                "tests/test_orders.py",
                "tests/test_concurrency.py",
                "requirements.txt",
            },
            "context": {
                "src/lambda_inventory.py",
                "src/inventory_cli.py",
                "tests/test_lambda_inventory.py",
                "tests/test_orders.py",
                "tests/test_concurrency.py",
                "data/inventory.json",
                "data/orders.schema.json",
                "data/schema.sql",
                "requirements.txt",
            },
        },
        {
            "label": "portable relational schema and row normalization",
            "validation_stage": "11-orders",
            "objective": (
                "Make the relational path executable locally and consistent with the inherited JSON contract. "
                "The canonical inventory fields are exactly sku, description, bin_location, quantity, and unit. "
                "Replace any SQL column, dataclass field, row mapping, or seed field named name with description; "
                "do not preserve name as an alias. Preserve unit in the schema, seed, SELECT list, and returned "
                "inventory JSON. Use bin_location in data/schema.sql, data/seed.sql, every query, and "
                "dict-row mapping; keep the pick-work command's external JSON field named bin. Add orders "
                "with primary-key order_id and order_lines with foreign keys to orders and inventory plus "
                "CHECK(quantity > 0). Add a small commented src/db_adapter.py and data/init_db.py with an "
                "explicit TINYWMS_DB=sqlite|postgres switch, PostgreSQL default, TINYWMS_SQLITE_PATH, lazy "
                "PostgreSQL imports, PRAGMA foreign_keys=ON, and a deliberately narrow SQLite cursor adapter "
                "that changes %s to ? and removes FOR UPDATE. Keep open_connection readable, and export a "
                "callable init_db() that applies and commits schema.sql plus seed.sql; the CLI main() should "
                "delegate to init_db(). data/init_db.py must define a module-level `def init_db(` "
                "(not nested, not only main), use open_connection, read the SQL files with "
                "Path.read_text(), obtain the connection with `with open_connection() as connection:` (open_connection is a "
                "@contextmanager that yields the connection; never call .cursor() or .close() on its raw return value), run them with executescript( or .execute(, call .commit(, and its "
                "module docstring must literally mention schema.sql, seed.sql, sqlite and postgres. "
                "Order SQL must be portable: for multi-SKU lookups build `IN (` + \",\".join([\"%s\"] * len(skus)) + `)` "
                "and pass the SKUs as a flat parameter sequence; never use `= ANY(%s)` or pass a list as one parameter. "
                "Support tuple "
                "and dict rows with a visible normalization helper: read dict/SQLite Row values by the literal "
                "key 'bin_location' and tuple values by the documented column index 2. Export one stable "
                "place_order(...) function that the local proof can call with an injected connection and fake "
                "AWS publishers. State clearly that SQLite cannot prove row locking and Stage 12 concurrency "
                "requires PostgreSQL. Update SQL export/tests and data-contract docs."
            ),
            "allowed": {
                "data/schema.sql",
                "data/seed.sql",
                "data/init_db.py",
                "src/db_adapter.py",
                "src/sql_export.py",
                "src/lambda_inventory.py",
                "tests/test_sql_export.py",
                "tests/test_lambda_inventory.py",
                "tests/test_orders.py",
                "tests/test_concurrency.py",
                "docs/architecture.md",
                "docs/data-contracts.md",
            },
            "required_changed": {
                "data/schema.sql",
                "data/seed.sql",
                "src/lambda_inventory.py",
            },
            "context": {
                "data/inventory.json",
                "data/inventory.schema.json",
                "data/schema.sql",
                "data/seed.sql",
                "src/lambda_inventory.py",
                "src/sql_export.py",
                "tests/test_lambda_inventory.py",
                "tests/test_orders.py",
                "tests/test_concurrency.py",
                "tests/test_sql_export.py",
                "docs/architecture.md",
                "docs/data-contracts.md",
            },
        },
        {
            "label": "real SQLite order persistence and rollback proof",
            "validation_stage": "11-orders",
            "objective": (
                "Write tests/test_sqlite_orders.py as an executable standard-library integration proof "
                "against the current src/lambda_inventory.py API; do not merely inspect source text. Use "
                "tempfile/TemporaryDirectory and the repository's real SQLite boundary: patch TINYWMS_DB=sqlite "
                "and TINYWMS_SQLITE_PATH to the temporary file, call data.init_db.init_db(), then obtain the "
                "order connection from src.db_adapter.open_connection(). Do not create a parallel wrapper "
                "around raw sqlite3, because it bypasses the adapter that translates %s and removes FOR UPDATE. "
                "Call the exported place_order(...) using its actual current signature; inject no-op or recording "
                "SQS/EventBridge clients only when that signature accepts them. The repository runs "
                "`python3 -m unittest discover`: "
                "import unittest, define a class such as SQLiteOrderTests(unittest.TestCase), and put all three "
                "scenarios inside that class as discoverable methods using self.assert* helpers. Top-level "
                "pytest-style test functions are invalid because unittest reports `Ran 0 tests`. Use these "
                "exact descriptive method names: "
                "test_accepted_order_persists_rows, test_insufficient_inventory_rolls_back, and "
                "test_unknown_sku_rolls_back. The accepted test must SELECT and assert persisted orders, "
                "order_lines, and changed inventory. Each rejected test must assert the expected rejection "
                "and then SELECT the database to prove no order/order-line mutation and unchanged inventory. "
                "Keep all setup and assertions in this test file and require no PostgreSQL, boto3, or network."
            ),
            "allowed": {
                "data/schema.sql",
                "data/seed.sql",
                "data/init_db.py",
                "src/db_adapter.py",
                "src/lambda_inventory.py",
                "tests/test_sqlite_orders.py",
            },
            "required_changed": {
                "tests/test_sqlite_orders.py",
            },
            "context": {
                "data/schema.sql",
                "data/seed.sql",
                "data/init_db.py",
                "src/db_adapter.py",
                "src/lambda_inventory.py",
                "tests/test_lambda_inventory.py",
                "tests/test_orders.py",
                "tests/test_sqlite_orders.py",
            },
        },
        {
            "label": "database-derived pick-work commands and real SQS acknowledgement",
            "validation_stage": "13-sqs",
            "objective": (
                "Preserve the repaired database transaction. After commit only, call an injected SQS "
                "client's send_message(...) once per order line. Each versioned command must have a stable "
                "command_id plus order_id, sku, quantity, and the bin obtained from that line's locked "
                "inventory row; include its description, never hard-code a bin, and never drop later lines. "
                "Concretely, src/lambda_inventory.py itself (not another module) must contain, after the "
                "commit, a `for` loop over the order lines whose body builds a command dict with the literal "
                "keys 'command_id', 'order_id', 'sku', 'quantity', 'bin', 'description' and calls "
                "`sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps(command))` directly in that loop. "
                "That loop must appear textually AFTER the `connection.commit()` statement in place_order (commit "
                "first, collect the command dicts in a list while inside the transaction, then publish them in "
                "the loop after commit and outside any try/with block that wraps the transaction). "
                "Every `place_order(` call in tests/test_lambda_inventory.py must also pass `sqs_client=` with a fake. "
                "Update the inherited concurrency fake for the evolved locked-row shape. Implement src/sqs_consumer.py "
                "with a stable consume_messages(...) function that performs exactly one injected-or-boto3 "
                "receive_message long poll per call, passes each decoded JSON body to the callback, exposes "
                "visible message metadata, and calls delete_message only after callback success. It must not "
                "own an unbounded drain/service loop; Stage 15 owns that loop. Fake-client tests must prove receive/delete, "
                "failure/no-delete, and multiple-message behavior without calling AWS. Use descriptive "
                "test names such as test_success_deletes_message, test_callback_failure_does_not_delete, "
                "and test_processes_each_message so each proof remains visible to students."
            ),
            "allowed": {
                "src/lambda_inventory.py",
                "src/sqs_consumer.py",
                "tests/test_orders.py",
                "tests/test_concurrency.py",
                "tests/test_sqs_consumer.py",
                "data/pick-work.json",
                "docs/data-contracts.md",
                "docs/architecture.md",
            },
            "context": {
                "src/lambda_inventory.py",
                "src/sqs_consumer.py",
                "tests/test_orders.py",
                "tests/test_concurrency.py",
                "tests/test_sqs_consumer.py",
                "data/pick-work.json",
                "docs/data-contracts.md",
                "docs/architecture.md",
            },
        },
        {
            "label": "EventBridge fan-out and independent delivered-event consumers",
            "validation_stage": "14-domain-events",
            "objective": (
                "Preserve the SQS command path and publish one versioned OrderPlaced event only after "
                "commit using an injected EventBridge client. Make fan-out executable: infra/events.yaml "
                "must define an event bus, two matching EventBridge rules, two independent SQS target "
                "queues, and queue policies authorizing EventBridge delivery. Both Python event consumers "
                "must receive and decode delivered event JSON from their own injected-or-boto3 queue "
                "clients. Add independent fake-client tests and output-resolution-first deploy guidance. "
                "Update every local order/concurrency test to inject both no-op/fake SQS and EventBridge "
                "clients so tests never attempt to import or call boto3. Literally: EVERY `handler(` call in "
                "tests/test_orders.py and tests/test_concurrency.py, including helper functions and each test "
                "method, must pass the keyword arguments `sqs_client=` and `eventbridge_client=` (a shared "
                "module-level fake class instance is fine); grep your output for `handler(` before answering "
                "and fix any call lacking both. Likewise every `place_order(` call in tests/test_lambda_inventory.py, tests/test_orders.py, tests/test_concurrency.py and tests/test_sqlite_orders.py must pass sqs_client= and eventbridge_client= fakes."
            ),
            "allowed": {
                "src/lambda_inventory.py",
                "src/event_consumer_a.py",
                "src/event_consumer_b.py",
                "tests/test_orders.py",
                "tests/test_concurrency.py",
                "tests/test_event_consumers.py",
                "infra/events.yaml",
                "deploy/events/README.md",
                "docs/data-contracts.md",
                "docs/architecture.md",
            },
            "context": {
                "src/lambda_inventory.py",
                "src/event_consumer_a.py",
                "src/event_consumer_b.py",
                "tests/test_orders.py",
                "tests/test_concurrency.py",
                "tests/test_event_consumers.py",
                "infra/events.yaml",
                "deploy/events/README.md",
                "docs/data-contracts.md",
                "docs/architecture.md",
            },
        },
        {
            "label": "long-running idempotent pick-ticket worker",
            "validation_stage": "15-pick-ticket-worker",
            "objective": (
                "Evolve the SQS receiver into a long-running pick-ticket worker. Prefer explicit reuse of "
                "src.sqs_consumer.consume_messages(...) rather than duplicating its receive/delete logic. "
                "That callback receives the already-decoded command JSON, not a raw SQS envelope, so do not "
                "read or decode a Body field again. Repeatedly long-poll, "
                "process all returned messages, suppress duplicate command_id values with explicit durable "
                "state across restarts, include command_id in tickets, append tickets, and delete messages "
                "only after output succeeds. Add bounded --once mode and orderly SIGINT/SIGTERM handling. "
                "Empty receives continue polling in service mode. Tests must prove multiple messages, restart "
                "duplicate suppression, empty-poll continuation, failure/no-delete, and acknowledgement after output without AWS."
                " For the empty-poll service proof, begin with stop_flag['stop'] false, return an empty first "
                "poll, deliver a message on a later poll, and set the shared flag true only after that delivery; "
                "passing an already-true stop flag does not exercise the loop."
                " Concretely, name that test test_service_continues_after_empty_poll and write it inside the one "
                "function body as: `stop_flag = {'stop': False}`; a fake client (nested class or closure defined in "
                "that same function) whose second receive_message sets `stop_flag['stop'] = True`; and the worker "
                "call passing `stop_flag=stop_flag` as a keyword argument. Also name tests with the words "
                "multiple_messages, duplicate_after_restart, failure_does_not_delete, and once."
                " Add deploy/pick-ticket-worker/tinywms-pick-ticket-worker.service.in, "
                "install_user_service.sh, environment.example, and README.md. The installer resolves the "
                "current stage path; the user service runs long-lived mode, restarts on failure, and the "
                "guide demonstrates systemctl --user, journalctl --user, and tail -f."
            ),
            "allowed": {
                "src/pick_ticket_worker.py",
                "tests/test_pick_ticket_worker.py",
                "deploy/pick-ticket-worker/tinywms-pick-ticket-worker.service.in",
                "deploy/pick-ticket-worker/install_user_service.sh",
                "deploy/pick-ticket-worker/environment.example",
                "deploy/pick-ticket-worker/README.md",
                "docs/data-contracts.md",
                "docs/architecture.md",
            },
            "context": {
                "src/sqs_consumer.py",
                "src/pick_ticket_worker.py",
                "tests/test_sqs_consumer.py",
                "tests/test_pick_ticket_worker.py",
                "deploy/pick-ticket-worker/tinywms-pick-ticket-worker.service.in",
                "deploy/pick-ticket-worker/install_user_service.sh",
                "deploy/pick-ticket-worker/environment.example",
                "deploy/pick-ticket-worker/README.md",
                "data/pick-work.json",
                "docs/data-contracts.md",
                "docs/architecture.md",
            },
        },
        {
            "label": "executable local callback proof",
            "validation_stage": "16-callback-demo",
            "objective": (
                "Add tests/test_callback_integration.py as a local executable compatibility proof using "
                "the real HTTP application and worker logic with fake AWS/database boundaries. It must "
                "GET /inventory, POST /orders, observe a changed quantity, then invoke the real "
                "lambda_inventory order publisher with injected fake database/SQS/EventBridge clients, "
                "inspect its emitted command_id, "
                "run worker processing, and observe pick-tickets.txt. Use an actual local HTTP client, patch "
                "all mutable inventory/ticket/idempotency paths into a temporary directory, and never mutate "
                "checked-in data. Assert the real local HTTP status separately from its decoded JSON body; "
                "the local response is not a Lambda statusCode/body envelope. Never construct a pick-work "
                "command literal inside the integration test. Keep every JSON boundary visible. To run worker "
                "processing, write `from src.sqs_consumer import consume_messages` at module level and call "
                "`consume_messages(...)` directly (with a fake SQS client holding the emitted command and a "
                "callback that appends the ticket), or import and call `main` from src.pick_ticket_worker; "
                "do not reimplement consumption inline."
            ),
            "allowed": {
                "tests/test_callback_integration.py",
                "docs/end-to-end.md",
                "docs/architecture.md",
                "docs/data-contracts.md",
            },
            "context": {
                "src/http_server.py",
                "src/lambda_inventory.py",
                "src/sqs_consumer.py",
                "src/pick_ticket_worker.py",
                "tests/test_http_order_flow.py",
                "tests/test_orders.py",
                "tests/test_pick_ticket_worker.py",
                "docs/end-to-end.md",
                "docs/architecture.md",
                "docs/data-contracts.md",
            },
        },
        {
            "label": "persistent container worker demonstration",
            "validation_stage": "17-container-worker",
            "objective": (
                "Keep the worker as the only containerized component. Make src/Dockerfile run long-lived "
                "worker mode by default. Add deploy/container-worker/README.md with exact build and docker "
                "run commands, PICK_WORK_QUEUE_URL, host-backed mounts for pick-tickets.txt and the durable "
                "processed-command ledger, plus a bounded --once classroom command. Update "
                "tests/test_container_worker.py to verify the real entrypoint, arguments, environment, and "
                "both mounts without Docker or network access."
            ),
            "allowed": {
                "src/Dockerfile",
                "deploy/container-worker/README.md",
                "tests/test_container_worker.py",
                "docs/architecture.md",
            },
            "context": {
                "src/Dockerfile",
                "src/pick_ticket_worker.py",
                "tests/test_container_worker.py",
                "deploy/pick-ticket-worker/README.md",
                "docs/architecture.md",
            },
        },
        {
            "label": "consolidated deployment wiring and Lambda packaging",
            "validation_stage": "18-aws-deployment",
            "objective": (
                "Replace the consolidated template's inline instructional Lambda stub with deployment "
                "of the real src/lambda_inventory.py package. Use CloudFormation Lambda Code "
                "S3Bucket/S3Key parameters or SAM CodeUri. The deploy guide must show exact dependency "
                "installation, zip/upload or cloudformation package/SAM commands before deployment, "
                "then output resolution, GET /inventory and POST /orders verification, and destroy. "
                "Construct production boto3 SQS/EventBridge clients when tests do not inject them. Wire "
                "DATABASE_URL, PICK_WORK_QUEUE_URL, EVENT_BUS_NAME, narrowly scoped sqs:SendMessage and "
                "events:PutEvents permissions. infra/template.yaml is a standalone consolidated stack: "
                "it must itself contain the pick-work queue plus two independent event-consumer queues, "
                "two AWS::Events::Rule resources with one Targets section each, and delivery policies for "
                "both event queues; do not rely on separately deploying infra/events.yaml. Point "
                "EVENT_BUS_NAME at the AWS::Events::EventBus, and make both rule patterns match the exact "
                "DetailType published by lambda_inventory.py. Use PostgreSQL RDS because the Lambda uses "
                "psycopg. For a raw AWS::Lambda::Function, create an AWS::IAM::Role, attach policies there, "
                "and reference its ARN; do not use a hard-coded role ARN or a Function-level Policies key. "
                "Preserve the established relational API and SQL contract when editing lambda_inventory.py: "
                "tests/test_sqlite_orders.py must still import its public names and pass against the real "
                "data/schema.sql through data.init_db.init_db() and src.db_adapter.open_connection(). "
                "Make the configured "
                "Lambda handler agree with the ZIP module layout. tests/test_deployment_wiring.py must "
                "behaviorally import lambda_inventory, install or patch a fake boto3 module, call "
                "_sqs_client() and _eventbridge_client(), and assert client('sqs') and client('events') "
                "were requested. It must also inspect template text and visibly assert the literal "
                "DATABASE_URL, PICK_WORK_QUEUE_URL, EVENT_BUS_NAME, sqs:SendMessage, and events:PutEvents "
                "markers. Do not assert exact optional-dependency error-message text in source. "
                "All tests must run with the standard library alone: do not import yaml/PyYAML, boto3, "
                "botocore, or PostgreSQL drivers; inspect template text and inject fake modules instead. "
                "Every literal assertIn/assertNotIn against the template text must match the actual "
                "infra/template.yaml content; assert PICK_WORK_QUEUE_URL: !Ref PickWorkQueue rather than "
                "inventing an unrelated QueueUrl property. Every literal assertion against the deployment "
                "README must likewise appear in that guide; assert its real curl commands rather than "
                "inventing prose such as GET /inventory. Do not use placeholder endpoints, users, passwords, "
                "or DATABASE_URL values in the runnable template. Require environment-specific values as "
                "deploy-time parameters and mark secrets NoEcho."
                " If src/lambda_inventory.py imports src/db_adapter.py, copy db_adapter.py into the same "
                "importable ZIP layout and test that package wiring."
            ),
            "allowed": {
                "src/lambda_inventory.py",
                "infra/template.yaml",
                "deploy/aws/README.md",
                "deploy/aws/package_lambda.sh",
                "tests/test_aws_deployment_files.py",
                "tests/test_deployment_wiring.py",
            },
            "context": {
                "src/lambda_inventory.py",
                "src/db_adapter.py",
                "data/init_db.py",
                "data/schema.sql",
                "data/seed.sql",
                "tests/test_sqlite_orders.py",
                "requirements.txt",
                "infra/template.yaml",
                "deploy/aws/README.md",
                "deploy/aws/package_lambda.sh",
                "tests/test_aws_deployment_files.py",
                "infra/events.yaml",
                "infra/sqs.yaml",
            },
        },
        {
            "label": "honest course operations and 26-session demo runbook",
            "validation_stage": "20-final-walkthrough",
            "objective": (
                "Align the final teaching guides with the published repository's real shape. Add "
                "docs/git-history.md explaining that stage directories coexist in one revision, using "
                "git diff --no-index and never invented stage tags. Add docs/demo-runbook.md with exactly "
                "Session 1 through Session 26 headings. Each session names its backing stage, gives exact "
                "commands where supported, and marks hardware/cloud/operator work Manual only or Partly "
                "manual. Cover the finished order-to-pick-ticket journey, SQLite initialization and real "
                "order proof, PostgreSQL-only concurrency, worker systemd operations, and Docker durable "
                "mounts. The runbook must contain these literal executable command forms in their relevant "
                "sessions: `TINYWMS_DB=sqlite TINYWMS_SQLITE_PATH=data/tinywms.db python3 -m data.init_db`, "
                "`systemctl --user status tinywms-pick-ticket-worker`, `journalctl --user`, `tail -f`, and "
                "a `docker run` command with durable mounts. Add tests/test_demo_runbook.py enforcing the 26 "
                "sections and stable artifact links. Rewrite README.md in this pass: every numbered student "
                "exercise must first ask the student to submit, inspect, observe, curl, view, compare, or tail "
                "visible behavior. If an exercise mentions running tests, say `optionally run the tests` only "
                "after that visible action. Include the inherited `node --test tests/test_web_app.js` command."
            ),
            "allowed": {
                "README.md",
                "docs/git-history.md",
                "docs/demo-runbook.md",
                "tests/test_demo_runbook.py",
            },
            "required_changed": {
                "README.md",
                "docs/git-history.md",
                "docs/demo-runbook.md",
                "tests/test_demo_runbook.py",
            },
            "context": {
                "README.md",
                "docs/end-to-end.md",
                "docs/architecture.md",
                "docs/data-contracts.md",
                "deploy/pick-ticket-worker/README.md",
                "deploy/container-worker/README.md",
                "tests/test_web_app.js",
            },
        },
        {
            "label": "final executable walkthrough proof",
            "validation_stage": "20-final-walkthrough",
            "objective": (
                "Make the final walkthrough truthful to the executable system. Preserve and, if needed, "
                "repair tests/test_callback_integration.py. The already validated standard-library-only "
                "tests/test_deployment_wiring.py is inherited read-only from the deployment repair; do not "
                "rewrite it or introduce yaml/PyYAML. Add tests/test_end_to_end_walkthrough.py using only "
                "the standard library to inspect docs/end-to-end.md and assert the browser, API Gateway, "
                "Lambda, RDS, SQS, EventBridge, and pick-ticket boundaries. Update docs/end-to-end.md so it "
                "describes only connections backed by source, tests, infrastructure, and runnable commands."
            ),
            "allowed": {
                "tests/test_callback_integration.py",
                "tests/test_end_to_end_walkthrough.py",
                "docs/end-to-end.md",
                "docs/architecture.md",
                "docs/data-contracts.md",
            },
            "context": {
                "src/web/index.html",
                "src/web/app.js",
                "src/http_server.py",
                "src/lambda_inventory.py",
                "src/sqs_consumer.py",
                "src/event_consumer_a.py",
                "src/event_consumer_b.py",
                "src/pick_ticket_worker.py",
                "tests/test_callback_integration.py",
                "tests/test_deployment_wiring.py",
                "tests/test_end_to_end_walkthrough.py",
                "infra/template.yaml",
                "deploy/aws/package_lambda.sh",
                "deploy/aws/README.md",
                "docs/end-to-end.md",
                "docs/architecture.md",
                "docs/data-contracts.md",
            },
        },
    ]

    snapshot = dict(baseline_files)
    combined_overlay: dict[str, str] = {}
    schema = build_output_schema([final_stage])
    for group in groups:
        if group["label"] == "consolidated deployment wiring and Lambda packaging":
            deployment_test_path = "tests/test_deployment_wiring.py"
            deployment_test = snapshot.get(deployment_test_path)
            template = snapshot.get("infra/template.yaml", "")
            if deployment_test is not None:
                normalized_test = _normalize_deployment_wiring_test(deployment_test, template)
                if normalized_test != deployment_test:
                    snapshot = dict(snapshot)
                    snapshot[deployment_test_path] = normalized_test
                    combined_overlay[deployment_test_path] = normalized_test

        def focused_quality_snapshot(candidate: dict[str, str]) -> dict[str, str]:
            paths = set(group["allowed"]) | {"README.md"}
            return {path: content for path, content in candidate.items() if path in paths}

        try:
            _validate_focused_reference_group(group["label"], snapshot)
            quality_snapshot = focused_quality_snapshot(snapshot)
            _validate_python_syntax(group["validation_stage"], quality_snapshot)
            _validate_test_portability(group["validation_stage"], quality_snapshot)
            if (
                group["label"] == "long-running idempotent pick-ticket worker"
                and _unittest_case_methods(snapshot.get("tests/test_pick_ticket_worker.py", ""))
            ):
                _execute_snapshot_tests(
                    group["validation_stage"],
                    snapshot,
                    python_pattern="test_pick_ticket_worker.py",
                    run_web_test=False,
                    python_timeout_seconds=10,
                )
            if (
                group["label"] == "consolidated deployment wiring and Lambda packaging"
                and _unittest_case_methods(snapshot.get("tests/test_deployment_wiring.py", ""))
            ):
                _execute_snapshot_tests(
                    group["validation_stage"],
                    snapshot,
                    python_pattern="test_deployment_wiring.py",
                    run_web_test=False,
                    python_timeout_seconds=20,
                )
                if _unittest_case_methods(snapshot.get("tests/test_sqlite_orders.py", "")):
                    _execute_snapshot_tests(
                        group["validation_stage"],
                        snapshot,
                        python_pattern="test_sqlite_orders.py",
                        run_web_test=False,
                        python_timeout_seconds=20,
                    )
            continue
        except ValueError:
            pass

        prompt = _focused_reference_repair_prompt(
            final_stage,
            group["label"],
            group["objective"]
            + " INVARIANT for every group that edits src/lambda_inventory.py: inside place_order, "
            "connection.commit() (or leaving the transaction() block) must come textually BEFORE any "
            "sqs.send_message(...) or eventbridge put_events(...) call; never publish inside the transaction or "
            "before commit, and rollback only in except paths. Every place_order( call in every test file passes "
            "sqs_client= (and eventbridge_client= from Stage 14 on) fakes.",
            snapshot,
            group["context"],
            group["allowed"],
        )
        attempts = max_validation_retries + 1
        rejected_plan: dict[str, Any] | None = None
        last_error: ValueError | None = None
        candidate: dict[str, str] | None = None
        overlay: dict[str, str] | None = None
        for attempt in range(1, attempts + 1):
            request_input = prompt
            if last_error is not None:
                request_input = build_retry_generation_input(
                    prompt,
                    str(last_error),
                    attempt - 1,
                    attempts,
                    rejected_plan,
                )
            plan = requester(request_input, schema, model, api_token, base_url)
            plan = _normalize_student_exercises_in_plan(plan)
            plan = _normalize_unittest_tests_in_plan(plan)
            try:
                stages = validate_plan(plan, [final_stage])
                candidate, overlay = _apply_plan_stage_to_snapshot(
                    snapshot,
                    stages[0],
                    group["allowed"],
                )
                if group["label"] == "consolidated deployment wiring and Lambda packaging":
                    deployment_test_path = "tests/test_deployment_wiring.py"
                    deployment_test = candidate.get(deployment_test_path)
                    if deployment_test is not None:
                        normalized_test = _normalize_deployment_wiring_test(
                            deployment_test,
                            candidate.get("infra/template.yaml", ""),
                        )
                        if normalized_test != deployment_test:
                            candidate[deployment_test_path] = normalized_test
                            overlay[deployment_test_path] = normalized_test
                required_changed = set(group.get("required_changed", ()))
                missing_changes = sorted(required_changed - set(overlay))
                if missing_changes:
                    raise ValueError(
                        f"Focused reference repair {group['label']!r} must emit complete replacements "
                        f"for these paths: {missing_changes}."
                    )
                _validate_focused_reference_group(group["label"], candidate)
                quality_snapshot = focused_quality_snapshot(candidate)
                _validate_python_syntax(final_stage, quality_snapshot)
                _validate_test_portability(final_stage, quality_snapshot)
                if group["label"] == "real SQLite order persistence and rollback proof":
                    _execute_snapshot_tests(
                        group["validation_stage"],
                        candidate,
                        python_pattern="test_sqlite_orders.py",
                        run_web_test=False,
                    )
                if group["label"] == "long-running idempotent pick-ticket worker":
                    _execute_snapshot_tests(
                        group["validation_stage"],
                        candidate,
                        python_pattern="test_pick_ticket_worker.py",
                        run_web_test=False,
                        python_timeout_seconds=10,
                    )
                if (
                    group["label"] == "consolidated deployment wiring and Lambda packaging"
                    and _unittest_case_methods(candidate.get("tests/test_deployment_wiring.py", ""))
                ):
                    _execute_snapshot_tests(
                        group["validation_stage"],
                        candidate,
                        python_pattern="test_deployment_wiring.py",
                        run_web_test=False,
                        python_timeout_seconds=20,
                    )
                    if _unittest_case_methods(candidate.get("tests/test_sqlite_orders.py", "")):
                        _execute_snapshot_tests(
                            group["validation_stage"],
                            candidate,
                            python_pattern="test_sqlite_orders.py",
                            run_web_test=False,
                            python_timeout_seconds=20,
                        )
                break
            except ValueError as error:
                if candidate is not None and overlay and on_group_progress is not None:
                    on_group_progress(candidate, overlay)
                rejected_plan = plan
                last_error = error
                if attempt == attempts:
                    raise ValueError(
                        f"Focused reference repair {group['label']!r} failed validation after "
                        f"{attempts} attempts: {error}"
                    ) from error
        assert candidate is not None and overlay is not None
        snapshot = candidate
        combined_overlay.update(overlay)
        if on_group_complete is not None:
            on_group_complete(snapshot, combined_overlay)

    return snapshot, combined_overlay


def _snapshot_digest(snapshot: dict[str, str]) -> str:
    digest = hashlib.sha256()
    for path, content in sorted(snapshot.items()):
        digest.update(path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(content.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def _load_reference_repair_cache(
    cache_path: Path,
    seed_digest: str,
) -> dict[str, str]:
    if not cache_path.is_file():
        return {}
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict) or payload.get("seed_digest") != seed_digest:
        return {}
    if payload.get("repair_contract_version", REFERENCE_REPAIR_CACHE_VERSION) != REFERENCE_REPAIR_CACHE_VERSION:
        return {}
    overlay = payload.get("overlay")
    if not isinstance(overlay, dict):
        return {}
    validated: dict[str, str] = {}
    for path, content in overlay.items():
        if not isinstance(path, str) or not isinstance(content, str):
            return {}
        validated[_safe_path(path).as_posix()] = content
    return validated


def _scratch_reference_contract_digest(catalog: list[Path]) -> str:
    digest = hashlib.sha256()
    digest.update(str(SCRATCH_REFERENCE_CACHE_VERSION).encode("ascii"))
    for prompt_path in catalog:
        digest.update(prompt_path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(prompt_path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _load_scratch_reference_cache(cache_path: Path, contract_digest: str) -> dict[str, str]:
    if not cache_path.is_file():
        return {}
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict) or payload.get("contract_digest") != contract_digest:
        return {}
    if payload.get("cache_version") != SCRATCH_REFERENCE_CACHE_VERSION:
        return {}
    snapshot = payload.get("snapshot")
    if not isinstance(snapshot, dict):
        return {}
    validated: dict[str, str] = {}
    for path, content in snapshot.items():
        if not isinstance(path, str) or not isinstance(content, str):
            return {}
        normalized_path = _safe_path(path).as_posix()
        if normalized_path.startswith("tests/test_") and normalized_path.endswith(".py"):
            content = _normalize_unittest_discovery_source(content)
        validated[normalized_path] = content
    return validated


def _save_scratch_reference_cache(
    cache_path: Path,
    contract_digest: str,
    snapshot: dict[str, str],
) -> None:
    normalized_snapshot = {
        path: (
            _normalize_unittest_discovery_source(content)
            if path.startswith("tests/test_") and path.endswith(".py")
            else content
        )
        for path, content in snapshot.items()
    }
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps(
            {
                "cache_version": SCRATCH_REFERENCE_CACHE_VERSION,
                "contract_digest": contract_digest,
                "snapshot": normalized_snapshot,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def generate_final_reference(
    prompt_dir: Path,
    reference_dir: Path,
    *,
    seed_output_root: Path | None = Path("generated"),
    model: str = DEFAULT_MODEL,
    api_key: str | None = None,
    base_url: str = DEFAULT_BASE_URL,
    requester: PlanRequester = request_plan,
    max_validation_retries: int = 1,
) -> Path:
    """Generate and validate the final system plus its course blueprint."""
    catalog = discover_prompt_files(prompt_dir)
    stage_names = [path.stem for path in catalog]
    stable_blueprint_overlay: dict[str, str] = {}
    existing_blueprint_path = reference_dir / BLUEPRINT_NAME
    if existing_blueprint_path.is_file():
        try:
            existing_blueprint = load_blueprint(existing_blueprint_path, stage_names)
        except (OSError, ValueError):
            pass
        else:
            stable_blueprint_overlay[BLUEPRINT_NAME] = (
                json.dumps(
                    normalize_blueprint_continuity(existing_blueprint, stage_names),
                    indent=2,
                )
                + "\n"
            )
    baseline_stage: str | None = None
    baseline_files: dict[str, str] | None = None
    if len(catalog) > 1 and seed_output_root is not None:
        predecessor = catalog[-2]
        seed_manifest = seed_output_root / predecessor.stem / MANIFEST_NAME
        if seed_manifest.is_file():
            baseline_stage = predecessor.stem
            baseline_files = load_generated_snapshot(seed_output_root, predecessor)
    api_token = api_key if api_key is not None else os.getenv("OPENAI_API_KEY", "")
    behavior_repair_overlay: dict[str, str] = {}
    repair_cache_path = reference_dir.parent / f".{reference_dir.name}.repair.json"
    scratch_cache_path = reference_dir.parent / f".{reference_dir.name}.scratch.json"
    scratch_contract_digest = _scratch_reference_contract_digest(catalog)
    scratch_resume_snapshot: dict[str, str] = {}
    scratch_resume_pending = False
    if baseline_files is None and catalog[-1].stem == "20-final-walkthrough":
        scratch_resume_snapshot = _load_scratch_reference_cache(
            scratch_cache_path,
            scratch_contract_digest,
        )
        scratch_resume_pending = bool(scratch_resume_snapshot)
    if baseline_files is not None and catalog[-1].stem == "20-final-walkthrough":
        seed_digest = _snapshot_digest(baseline_files)
        behavior_repair_overlay = _load_reference_repair_cache(repair_cache_path, seed_digest)
        if not behavior_repair_overlay and not repair_cache_path.is_file():
            try:
                prior_reference = load_stage_snapshot(reference_dir, catalog[-1])
            except (FileNotFoundError, OSError, ValueError):
                prior_reference = {}
            behavior_repair_overlay = {
                path: prior_reference[path]
                for path in REFERENCE_BEHAVIOR_CACHE_PATHS
                if path in prior_reference and prior_reference[path] != baseline_files.get(path)
            }
        baseline_files.update(behavior_repair_overlay)

        def save_repair_progress(
            repaired_snapshot: dict[str, str],
            new_overlay: dict[str, str],
        ) -> None:
            behavior_repair_overlay.update(new_overlay)
            repair_cache_path.parent.mkdir(parents=True, exist_ok=True)
            repair_cache_path.write_text(
                json.dumps(
                    {
                        "repair_contract_version": REFERENCE_REPAIR_CACHE_VERSION,
                        "seed_digest": seed_digest,
                        "overlay": behavior_repair_overlay,
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )

        baseline_files, new_behavior_overlay = _repair_reference_behavior_groups(
            baseline_files,
            catalog[-1].stem,
            model=model,
            api_token=api_token,
            base_url=base_url,
            requester=requester,
            max_validation_retries=max_validation_retries,
            on_group_complete=save_repair_progress,
        )
        behavior_repair_overlay.update(new_behavior_overlay)
    baseline_repair_overlay = _reference_seed_repair_overlay(baseline_files)

    def reference_requester(
        generation_input: str,
        schema: dict[str, Any],
        requested_model: str,
        requested_api_key: str,
        requested_base_url: str,
    ) -> dict[str, Any]:
        nonlocal scratch_resume_pending, scratch_resume_snapshot
        if baseline_files is None and scratch_resume_pending:
            scratch_resume_pending = False
            plan = _snapshot_delta_plan(
                catalog[-1].stem,
                None,
                scratch_resume_snapshot,
                summary="Resume the focused scratch final-reference repairs.",
            )
        else:
            plan = requester(
                generation_input,
                schema,
                requested_model,
                requested_api_key,
                requested_base_url,
            )
        if not isinstance(plan, dict):
            return plan
        if baseline_files is None:
            plan = _normalize_unittest_tests_in_plan(plan)
            plan = _normalize_reference_blueprint_in_plan(plan, catalog[-1].stem, stage_names)
            missing_aws_overlay = _scratch_reference_missing_aws_overlay(
                plan,
                catalog[-1].stem,
                model=requested_model,
                api_key=requested_api_key,
                base_url=requested_base_url,
                requester=requester,
            )
            plan = _apply_stage_file_overlay(
                plan,
                catalog[-1].stem,
                missing_aws_overlay,
            )
            if catalog[-1].stem == "20-final-walkthrough":
                scratch_snapshot = _scratch_reference_snapshot(
                    plan,
                    catalog[-1].stem,
                )

                def save_scratch_progress(
                    repaired_progress: dict[str, str],
                    _new_overlay: dict[str, str],
                ) -> None:
                    nonlocal scratch_resume_snapshot
                    scratch_resume_snapshot = dict(repaired_progress)
                    _save_scratch_reference_cache(
                        scratch_cache_path,
                        scratch_contract_digest,
                        scratch_resume_snapshot,
                    )

                save_scratch_progress(scratch_snapshot, {})
                repaired_snapshot, scratch_behavior_overlay = _repair_reference_behavior_groups(
                    scratch_snapshot,
                    catalog[-1].stem,
                    model=requested_model,
                    api_token=requested_api_key,
                    base_url=requested_base_url,
                    requester=requester,
                    max_validation_retries=max_validation_retries,
                    on_group_complete=save_scratch_progress,
                    on_group_progress=save_scratch_progress,
                )
                plan = _apply_stage_file_overlay(
                    plan,
                    catalog[-1].stem,
                    scratch_behavior_overlay,
                )
                mechanical_overlay = _reference_seed_repair_overlay(repaired_snapshot)
                plan = _apply_stage_file_overlay(
                    plan,
                    catalog[-1].stem,
                    mechanical_overlay,
                )
                repaired_snapshot.update(mechanical_overlay)
                save_scratch_progress(repaired_snapshot, mechanical_overlay)
            return _apply_stage_file_overlay(
                plan,
                catalog[-1].stem,
                stable_blueprint_overlay,
            )
        candidate_snapshot = dict(baseline_files)
        stages = plan.get("stages")
        if isinstance(stages, list):
            for stage in stages:
                if not isinstance(stage, dict) or stage.get("name") != catalog[-1].stem:
                    continue
                delete_files = stage.get("delete_files")
                if isinstance(delete_files, list):
                    for path in delete_files:
                        if isinstance(path, str):
                            candidate_snapshot.pop(path, None)
                files = stage.get("files")
                if isinstance(files, list):
                    for item in files:
                        if not isinstance(item, dict):
                            continue
                        path = item.get("path")
                        content = item.get("content")
                        if isinstance(path, str) and isinstance(content, str):
                            candidate_snapshot[path] = content
                break
        repair_overlay = _reference_seed_repair_overlay(candidate_snapshot)
        for path, content in baseline_repair_overlay.items():
            if path not in candidate_snapshot:
                repair_overlay[path] = content
        plan = _apply_stage_file_overlay(plan, catalog[-1].stem, repair_overlay)
        plan = _apply_stage_file_overlay(plan, catalog[-1].stem, behavior_repair_overlay)
        plan = _apply_stage_file_overlay(plan, catalog[-1].stem, stable_blueprint_overlay)
        return _normalize_reference_blueprint_in_plan(plan, catalog[-1].stem, stage_names)

    def validate_reference(stage_name: str, snapshot: dict[str, str]) -> None:
        validate_reference_snapshot(stage_name, snapshot, stage_names)

    generated_reference = generate_projects(
        [catalog[-1]],
        catalog,
        reference_dir.parent,
        model=model,
        api_key=api_key,
        base_url=base_url,
        requester=reference_requester,
        output_dirs=[reference_dir],
        baseline_stage=baseline_stage,
        baseline_files=baseline_files,
        max_validation_retries=max_validation_retries,
        extra_generation_context=_reference_generation_context(stage_names, baseline_files),
        additional_stage_validator=validate_reference,
    )[0]
    if baseline_files is None and scratch_cache_path.is_file():
        scratch_cache_path.unlink()
    return generated_reference


def _validate_forward_checkpoint(
    stage_name: str,
    snapshot: dict[str, str],
    blueprint: dict[str, Any],
    stage_names: list[str],
) -> None:
    """Apply every current validator before treating a prior checkpoint as frozen."""
    validate_snapshot_against_blueprint(stage_name, snapshot, blueprint, stage_names)
    _validate_materialized_stage(stage_name, snapshot)


def generate_course_forward(
    prompt_dir: Path,
    output_root: Path,
    reference_dir: Path,
    *,
    model: str = DEFAULT_MODEL,
    api_key: str | None = None,
    base_url: str = DEFAULT_BASE_URL,
    requester: PlanRequester = request_plan,
    max_validation_retries: int = 1,
) -> list[Path]:
    """Generate one stage at a time from a validated final-reference blueprint."""
    catalog = discover_prompt_files(prompt_dir)
    stage_names = [path.stem for path in catalog]
    final_prompt = catalog[-1]
    reference_snapshot = load_stage_snapshot(reference_dir, final_prompt)
    _validate_materialized_stage(final_prompt.stem, reference_snapshot)
    validate_reference_snapshot(final_prompt.stem, reference_snapshot, stage_names)
    blueprint = load_blueprint(reference_dir / BLUEPRINT_NAME, stage_names)
    if final_prompt.stem == "20-final-walkthrough":
        _preflight_forward_reference(reference_snapshot)

    latest = -1
    baseline_files: dict[str, str] | None = None
    for index, prompt_path in enumerate(catalog):
        manifest_path = output_root / prompt_path.stem / MANIFEST_NAME
        if not manifest_path.exists():
            break
        snapshot = load_generated_snapshot(output_root, prompt_path)
        try:
            _validate_forward_checkpoint(prompt_path.stem, snapshot, blueprint, stage_names)
        except ValueError:
            # A checkpoint accepted by an older validator is not frozen merely
            # because its manifest exists. Resume from the latest contiguous
            # checkpoint that still satisfies the current course contract.
            break
        latest = index
        baseline_files = snapshot

    generated: list[Path] = []
    baseline_stage = catalog[latest].stem if latest >= 0 else None
    for prompt_path in catalog[latest + 1 :]:
        # Mature final handlers/tests contain publishers from later lessons. Earlier stages evolve
        # their frozen checkpoint instead and borrow only reference components appropriate to the lesson.
        reference_context_exclusions = _forward_reference_context_exclusions(prompt_path.stem)
        stage_reference_snapshot = _forward_reference_snapshot(
            prompt_path.stem,
            reference_snapshot,
        )
        implementation_context = reference_implementation_context(
            blueprint,
            stage_names,
            prompt_path.stem,
            stage_reference_snapshot,
            excluded_paths=reference_context_exclusions,
        )
        behavior_contract = _forward_behavior_generation_contract(prompt_path.stem)
        extra_context = "\n\n".join(
            section for section in (implementation_context, behavior_contract) if section
        )
        reference_overlay = _forward_reference_overlay(
            prompt_path.stem,
            stage_reference_snapshot,
        )
        continuity_overlay = _forward_continuity_overlay(prompt_path.stem, baseline_files)
        cached_plan: dict[str, Any] | None = None
        cached_manifest = output_root / prompt_path.stem / MANIFEST_NAME
        if cached_manifest.exists():
            cached_plan = _cached_stage_delta_plan(output_root, prompt_path)
        cached_candidate_pending = cached_plan is not None

        def forward_requester(
            generation_input: str,
            schema: dict[str, Any],
            requested_model: str,
            requested_api_key: str,
            requested_base_url: str,
        ) -> dict[str, Any]:
            nonlocal cached_candidate_pending
            if prompt_path.stem == "20-final-walkthrough":
                final_candidate = dict(baseline_files or {})
                final_candidate.update(stage_reference_snapshot)
                plan = _snapshot_delta_plan(
                    prompt_path.stem,
                    baseline_files,
                    final_candidate,
                    summary="Install the preflighted final reference walkthrough.",
                )
            elif cached_candidate_pending and cached_plan is not None:
                cached_candidate_pending = False
                plan = cached_plan
            else:
                plan = requester(
                    generation_input,
                    schema,
                    requested_model,
                    requested_api_key,
                    requested_base_url,
                )
            if not isinstance(plan, dict):
                return plan
            stage_num = _stage_number(prompt_path.stem)
            if stage_num is not None:
                inherited_aws_paths = {
                    path
                    for introduced_stage, paths in REQUIRED_AWS_ARTIFACTS_BY_STAGE
                    if introduced_stage < stage_num
                    for path in paths
                }
                plan = _preserve_inherited_paths_from_deletion(
                    plan,
                    prompt_path.stem,
                    inherited_aws_paths,
                )
            if prompt_path.stem == "18-aws-deployment":
                inherited_aws_paths = {
                    path
                    for introduced_stage, paths in REQUIRED_AWS_ARTIFACTS_BY_STAGE
                    if introduced_stage < 18
                    for path in paths
                }
                plan = _preserve_inherited_stage_files(
                    plan,
                    prompt_path.stem,
                    inherited_aws_paths,
                )
            if reference_overlay:
                plan = _apply_stage_file_overlay(
                    plan,
                    prompt_path.stem,
                    reference_overlay,
                )
            if continuity_overlay:
                plan = _apply_stage_file_overlay(
                    plan,
                    prompt_path.stem,
                    continuity_overlay,
                )
            return _normalize_forward_teaching_continuity(plan, prompt_path.stem)

        stage_dir = generate_projects(
            [prompt_path],
            catalog,
            output_root,
            model=model,
            api_key=api_key,
            base_url=base_url,
            requester=forward_requester,
            baseline_stage=baseline_stage,
            baseline_files=baseline_files,
            max_validation_retries=max_validation_retries,
            course_blueprint=blueprint,
            extra_generation_context=extra_context,
            additional_stage_validator=_execute_snapshot_tests,
        )[0]
        generated.append(stage_dir)
        baseline_stage = prompt_path.stem
        baseline_files = load_generated_snapshot(output_root, prompt_path)

    return generated


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate staged teaching code with a context-aware LLM.")
    parser.add_argument("prompt", type=Path, nargs="?", help="Optional single prompt file to generate.")
    parser.add_argument("--prompt-dir", type=Path, default=PROMPT_DIR, help="Directory containing course prompts.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("generated"),
        help="Output root, or stage directory for one prompt.",
    )
    parser.add_argument("--all", action="store_true", help="Generate all stages with one model request.")
    parser.add_argument(
        "--build-reference",
        action="store_true",
        help="Generate a standalone final system and validated course-blueprint.json reference.",
    )
    parser.add_argument(
        "--forward-all",
        action="store_true",
        help="Generate missing stages forward from the validated final-reference blueprint.",
    )
    parser.add_argument(
        "--reference-output",
        type=Path,
        default=Path("reference/20-final-walkthrough"),
        help="Final-reference stage directory (default: reference/20-final-walkthrough).",
    )
    parser.add_argument(
        "--reference-seed-root",
        type=Path,
        default=Path("generated"),
        help="Output root containing an optional Stage 19 seed (default: generated).",
    )
    parser.add_argument(
        "--through",
        metavar="STAGE",
        help="Generate every stage through this prompt filename or stage name.",
    )
    parser.add_argument(
        "--resume-through",
        metavar="STAGE",
        help="Continue after the latest generated stage through this stage without regenerating earlier work.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the API request JSON without calling the model or writing output.",
    )
    parser.add_argument("--model", default=os.getenv("OPENAI_MODEL", DEFAULT_MODEL), help="OpenAI model ID.")
    parser.add_argument(
        "--base-url",
        default=os.getenv("OPENAI_BASE_URL", DEFAULT_BASE_URL),
        help="OpenAI-compatible API base URL.",
    )
    parser.add_argument(
        "--validation-retries",
        type=int,
        default=1,
        help="Number of bounded regeneration retries after validation failures (default: 1).",
    )
    args = parser.parse_args()

    if not args.prompt_dir.is_dir():
        raise FileNotFoundError(f"Prompt directory not found: {args.prompt_dir}")
    discovered = discover_prompt_files(args.prompt_dir)
    if not discovered:
        raise FileNotFoundError(f"No prompt files found in {args.prompt_dir}")
    selector_count = sum(
        value is not None
        for value in (args.prompt, args.through, args.resume_through)
    ) + int(args.all) + int(args.build_reference) + int(args.forward_all)
    if selector_count > 1:
        parser.error(
            "Choose only one of a positional prompt, --through, --resume-through, --all, "
            "--build-reference, or --forward-all."
        )

    def match_stage(stage_name: str) -> Path:
        matches = [path for path in discovered if stage_name in (path.name, path.stem)]
        if len(matches) != 1:
            names = ", ".join(path.stem for path in discovered)
            raise SystemExit(f"Unknown stage {stage_name!r}. Available stages: {names}")
        return matches[0]

    selected_prompt = args.prompt
    through_prompts: list[Path] | None = None
    resume_prompts: list[Path] | None = None
    baseline_stage: str | None = None
    baseline_files: dict[str, str] | None = None
    if args.through is not None:
        through_prompt = match_stage(args.through)
        through_prompts = discovered[: discovered.index(through_prompt) + 1]
    elif args.resume_through is not None:
        resume_target = match_stage(args.resume_through)
        target_index = discovered.index(resume_target)
        resume_index = find_resume_index(args.output, discovered, target_index)
        if resume_index == target_index:
            print(f"Nothing to generate: {resume_target.stem} is already present and contiguous.")
            return
        resume_prompts = discovered[resume_index + 1 : target_index + 1]
        if resume_index >= 0:
            baseline_prompt = discovered[resume_index]
            baseline_stage = baseline_prompt.stem
            baseline_files = load_generated_snapshot(args.output, baseline_prompt)
    elif not args.all and not args.build_reference and not args.forward_all and selected_prompt is None:
        if len(discovered) != 1:
            names = ", ".join(path.name for path in discovered)
            raise SystemExit(
                f"Multiple prompts found: {names}. Choose one explicitly, use --through, "
                "use --resume-through, or use --all."
            )
        selected_prompt = discovered[0]
    elif selected_prompt is not None and not selected_prompt.exists() and not selected_prompt.is_absolute():
        selected_prompt = args.prompt_dir / selected_prompt.name
    if selected_prompt is not None and not selected_prompt.exists():
        raise FileNotFoundError(f"Prompt not found: {selected_prompt}")

    if args.build_reference:
        reference_baseline_stage: str | None = None
        reference_baseline_files: dict[str, str] | None = None
        if len(discovered) > 1:
            predecessor = discovered[-2]
            seed_manifest = args.reference_seed_root / predecessor.stem / MANIFEST_NAME
            if seed_manifest.is_file():
                reference_baseline_stage = predecessor.stem
                reference_baseline_files = load_generated_snapshot(args.reference_seed_root, predecessor)
        if args.dry_run:
            generation_input = build_generation_input(
                discovered,
                [discovered[-1]],
                read_repository_rules(args.prompt_dir),
                reference_baseline_stage,
                reference_baseline_files,
                extra_context=_reference_generation_context(
                    [path.stem for path in discovered],
                    reference_baseline_files,
                ),
            )
            schema = build_output_schema([discovered[-1].stem])
            print(json.dumps(build_api_payload(generation_input, schema, args.model), indent=2))
            return
        reference = generate_final_reference(
            args.prompt_dir,
            args.reference_output,
            seed_output_root=args.reference_seed_root,
            model=args.model,
            base_url=args.base_url,
            max_validation_retries=args.validation_retries,
        )
        print(f"Generated and validated final reference in {reference}.")
        print(f"Blueprint: {reference / BLUEPRINT_NAME}")
        print(f"Model: {args.model}")
        return

    if args.forward_all:
        if args.dry_run:
            parser.error("--dry-run is not supported with --forward-all; preview --build-reference instead.")
        generated = generate_course_forward(
            args.prompt_dir,
            args.output,
            args.reference_output,
            model=args.model,
            base_url=args.base_url,
            max_validation_retries=args.validation_retries,
        )
        if generated:
            print(
                f"Generated {len(generated)} blueprint-guided stages forward under {args.output}; "
                f"latest stage: {generated[-1].name}."
            )
        else:
            print(f"Nothing to generate: all blueprint-guided checkpoints already exist under {args.output}.")
        print(f"Model: {args.model}")
        return

    requested_prompts = discovered if args.all else resume_prompts or through_prompts or [selected_prompt]
    if args.dry_run:
        generation_input = build_generation_input(
            discovered,
            requested_prompts,
            read_repository_rules(args.prompt_dir),
            baseline_stage,
            baseline_files,
        )
        schema = build_output_schema([path.stem for path in requested_prompts])
        print(json.dumps(build_api_payload(generation_input, schema, args.model), indent=2))
        return

    if args.all:
        generated = generate_all_apps(
            args.prompt_dir,
            args.output,
            model=args.model,
            base_url=args.base_url,
            max_validation_retries=args.validation_retries,
        )
        print(f"Generated {len(generated)} cumulative stages under {args.output} with one LLM request.")
        print(f"Model: {args.model}")
        return

    if resume_prompts is not None:
        generated = generate_projects(
            resume_prompts,
            discovered,
            args.output,
            model=args.model,
            base_url=args.base_url,
            baseline_stage=baseline_stage,
            baseline_files=baseline_files,
            max_validation_retries=args.validation_retries,
        )
        print(
            f"Generated {len(generated)} resumed stages under {args.output}; "
            f"preserved everything through {baseline_stage or 'the empty repository'}."
        )
        print(f"Model: {args.model}")
        return

    if through_prompts is not None:
        generated = generate_projects(
            through_prompts,
            discovered,
            args.output,
            model=args.model,
            base_url=args.base_url,
            max_validation_retries=args.validation_retries,
        )
        print(f"Generated {len(generated)} cumulative stages under {args.output} with one LLM request.")
        print(f"Model: {args.model}")
        return

    target = generate_app(
        selected_prompt,
        args.output,
        prompt_dir=args.prompt_dir,
        model=args.model,
        base_url=args.base_url,
        max_validation_retries=args.validation_retries,
    )
    print(f"Generated {selected_prompt.name} into {target} with one LLM request.")
    print(f"Model: {args.model}")


if __name__ == "__main__":
    main()
