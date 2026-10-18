"""Course-blueprint contract for final-first TinyWMS generation."""

from __future__ import annotations

import copy
import json
from pathlib import Path, PurePosixPath
from typing import Any


BLUEPRINT_NAME = "course-blueprint.json"
BLUEPRINT_SCHEMA_VERSION = 1


def _require_string(value: Any, location: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Course blueprint {location} must be a non-empty string.")
    return value


def _require_string_list(value: Any, location: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        raise ValueError(f"Course blueprint {location} must be an array of non-empty strings.")
    if len(value) != len(set(value)):
        raise ValueError(f"Course blueprint {location} contains duplicates.")
    return value


def _safe_blueprint_path(value: str, location: str) -> str:
    if not value or value.endswith("/") or "\\" in value:
        raise ValueError(f"Course blueprint {location} contains unsafe path {value!r}.")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != value:
        raise ValueError(f"Course blueprint {location} contains unsafe path {value!r}.")
    return value


def _records_by_id(records: Any, location: str) -> dict[str, dict[str, Any]]:
    if not isinstance(records, list):
        raise ValueError(f"Course blueprint {location} must be an array.")
    indexed: dict[str, dict[str, Any]] = {}
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise ValueError(f"Course blueprint {location}[{index}] must be an object.")
        record_id = _require_string(record.get("id"), f"{location}[{index}].id")
        if record_id in indexed:
            raise ValueError(f"Course blueprint {location} contains duplicate id {record_id!r}.")
        indexed[record_id] = record
    return indexed


def validate_blueprint(blueprint: dict[str, Any], stage_names: list[str]) -> dict[str, Any]:
    """Validate blueprint references, ordering, paths, and component continuity."""
    if not isinstance(blueprint, dict):
        raise ValueError("Course blueprint must be a JSON object.")
    if blueprint.get("schema_version") != BLUEPRINT_SCHEMA_VERSION:
        raise ValueError(
            f"Course blueprint schema_version must be {BLUEPRINT_SCHEMA_VERSION}."
        )
    if not stage_names:
        raise ValueError("Course blueprint validation requires at least one course stage.")
    if blueprint.get("reference_stage") != stage_names[-1]:
        raise ValueError(
            f"Course blueprint reference_stage must be {stage_names[-1]!r}."
        )

    stage_positions = {name: index for index, name in enumerate(stage_names)}
    components = _records_by_id(blueprint.get("components"), "components")
    contracts = _records_by_id(blueprint.get("contracts"), "contracts")
    if not components:
        raise ValueError("Course blueprint must define at least one component.")
    if not contracts:
        raise ValueError("Course blueprint must define at least one contract.")
    stage_records = blueprint.get("stages")
    if not isinstance(stage_records, list):
        raise ValueError("Course blueprint stages must be an array.")
    actual_stage_names = [
        record.get("name") for record in stage_records if isinstance(record, dict)
    ]
    if actual_stage_names != stage_names or len(stage_records) != len(stage_names):
        raise ValueError(
            f"Course blueprint stages must exactly match {stage_names!r}; "
            f"received {actual_stage_names!r}."
        )
    stages = {record["name"]: record for record in stage_records}

    component_kinds = {"application", "contract", "infrastructure", "operations"}
    for component_id, component in components.items():
        _require_string(component.get("name"), f"components[{component_id}].name")
        introduced = _require_string(
            component.get("introduced_stage"), f"components[{component_id}].introduced_stage"
        )
        if introduced not in stage_positions:
            raise ValueError(
                f"Course blueprint component {component_id!r} has unknown introduced_stage {introduced!r}."
            )
        kind = component.get("kind")
        if kind not in component_kinds:
            raise ValueError(
                f"Course blueprint component {component_id!r} kind must be one of {sorted(component_kinds)!r}."
            )
        _require_string(component.get("runtime"), f"components[{component_id}].runtime")
        paths = _require_string_list(component.get("paths"), f"components[{component_id}].paths")
        if not paths:
            raise ValueError(f"Course blueprint component {component_id!r} must name at least one path.")
        for path in paths:
            _safe_blueprint_path(path, f"components[{component_id}].paths")
        retired = component.get("retired_after_stage")
        if retired is not None:
            retired = _require_string(retired, f"components[{component_id}].retired_after_stage")
            if retired not in stage_positions or stage_positions[retired] < stage_positions[introduced]:
                raise ValueError(
                    f"Course blueprint component {component_id!r} has invalid retired_after_stage {retired!r}."
                )
        for field in ("inbound_contracts", "outbound_contracts"):
            for contract_id in _require_string_list(
                component.get(field), f"components[{component_id}].{field}"
            ):
                if contract_id not in contracts:
                    raise ValueError(
                        f"Course blueprint component {component_id!r} field {field!r} references "
                        f"unknown contract {contract_id!r}; declared contract IDs are "
                        f"{sorted(contracts)!r}. Add the missing contract record or replace the "
                        "reference with the intended declared ID."
                    )
        for dependency_id in _require_string_list(
            component.get("dependencies"), f"components[{component_id}].dependencies"
        ):
            if dependency_id not in components and dependency_id not in contracts:
                raise ValueError(
                    f"Course blueprint component {component_id!r} references unknown component or "
                    f"contract dependency {dependency_id!r}; declared component IDs are "
                    f"{sorted(components)!r} and declared contract IDs are {sorted(contracts)!r}."
                )

    unresolved_contract_components: list[tuple[str, str, str]] = []
    for contract_id, contract in contracts.items():
        _require_string(contract.get("name"), f"contracts[{contract_id}].name")
        introduced = _require_string(
            contract.get("introduced_stage"), f"contracts[{contract_id}].introduced_stage"
        )
        if introduced not in stage_positions:
            raise ValueError(
                f"Course blueprint contract {contract_id!r} has unknown introduced_stage {introduced!r}."
            )
        _require_string(contract.get("representation"), f"contracts[{contract_id}].representation")
        schema_paths = _require_string_list(
            contract.get("schema_paths"), f"contracts[{contract_id}].schema_paths"
        )
        for path in schema_paths:
            _safe_blueprint_path(path, f"contracts[{contract_id}].schema_paths")
        for field in ("producer_components", "consumer_components"):
            component_ids = _require_string_list(
                contract.get(field), f"contracts[{contract_id}].{field}"
            )
            if not component_ids:
                raise ValueError(
                    f"Course blueprint contract {contract_id!r} must name at least one {field}."
                )
            for component_id in component_ids:
                if component_id not in components:
                    unresolved_contract_components.append((contract_id, field, component_id))
        checks = _require_string_list(
            contract.get("compatibility_checks"), f"contracts[{contract_id}].compatibility_checks"
        )
        if not checks:
            raise ValueError(
                f"Course blueprint contract {contract_id!r} needs at least one compatibility check."
            )

    if unresolved_contract_components:
        details = "; ".join(
            f"contract {contract_id!r} {field} references unknown component {component_id!r}"
            for contract_id, field, component_id in unresolved_contract_components
        )
        raise ValueError(
            f"Course blueprint contract component references do not resolve: {details}; declared component "
            f"IDs are {sorted(components)!r}. Add each missing component record or replace each reference "
            "with the intended declared ID."
        )

    stage_component_fields = ("added_components", "reused_components", "evolved_components")
    for stage_name in stage_names:
        stage = stages[stage_name]
        _require_string(stage.get("purpose"), f"stages[{stage_name}].purpose")
        _require_string(stage.get("boundary_shift"), f"stages[{stage_name}].boundary_shift")
        referenced_components: set[str] = set()
        for field in stage_component_fields:
            values = _require_string_list(stage.get(field), f"stages[{stage_name}].{field}")
            for component_id in values:
                if component_id not in components:
                    raise ValueError(
                        f"Course blueprint stage {stage_name!r} references unknown component {component_id!r}."
                    )
                if component_id in referenced_components:
                    raise ValueError(
                        f"Course blueprint stage {stage_name!r} lists component {component_id!r} more than once."
                    )
                referenced_components.add(component_id)
                introduced = components[component_id]["introduced_stage"]
                if stage_positions[introduced] > stage_positions[stage_name]:
                    raise ValueError(
                        f"Course blueprint stage {stage_name!r} references future component {component_id!r}."
                    )
        stage_index = stage_positions[stage_name]
        active_components = {
            component_id
            for component_id, component in components.items()
            if _component_active(component, stage_index, stage_positions)
        }
        if referenced_components != active_components:
            missing = sorted(active_components - referenced_components)
            extra = sorted(referenced_components - active_components)
            raise ValueError(
                f"Course blueprint stage {stage_name!r} component classification is incomplete; "
                f"missing={missing}, inactive={extra}."
            )

        introduced_contracts = set(
            _require_string_list(
                stage.get("introduced_contracts"), f"stages[{stage_name}].introduced_contracts"
            )
        )
        inherited_contracts = set(
            _require_string_list(
                stage.get("inherited_contracts"), f"stages[{stage_name}].inherited_contracts"
            )
        )
        expected_introduced = {
            contract_id
            for contract_id, contract in contracts.items()
            if contract["introduced_stage"] == stage_name
        }
        expected_inherited = {
            contract_id
            for contract_id, contract in contracts.items()
            if stage_positions[contract["introduced_stage"]] < stage_index
        }
        if introduced_contracts != expected_introduced:
            raise ValueError(
                f"Course blueprint stage {stage_name!r} introduced_contracts must be "
                f"{sorted(expected_introduced)!r}."
            )
        if inherited_contracts != expected_inherited:
            raise ValueError(
                f"Course blueprint stage {stage_name!r} inherited_contracts must be "
                f"{sorted(expected_inherited)!r}."
            )
        for path in _require_string_list(
            stage.get("required_paths"), f"stages[{stage_name}].required_paths"
        ):
            _safe_blueprint_path(path, f"stages[{stage_name}].required_paths")
        checks = _require_string_list(
            stage.get("continuity_checks"), f"stages[{stage_name}].continuity_checks"
        )
        if stage_name != stage_names[0] and not checks:
            raise ValueError(
                f"Course blueprint stage {stage_name!r} needs at least one continuity check."
            )

    for component_id, component in components.items():
        introduced = component["introduced_stage"]
        if component_id not in stages[introduced]["added_components"]:
            raise ValueError(
                f"Course blueprint component {component_id!r} must be added in {introduced!r}."
            )

    assembly_paths = {
        "src/http_server.py": "03-pi-http-server",
        "src/web/app.js": "04-browser",
        "src/sqs_consumer.py": "13-sqs",
        "infra/events.yaml": "14-domain-events",
        "src/event_consumer_a.py": "14-domain-events",
        "src/event_consumer_b.py": "14-domain-events",
        "src/pick_ticket_worker.py": "15-pick-ticket-worker",
        "tests/test_callback_integration.py": "16-callback-demo",
        "src/Dockerfile": "17-container-worker",
        "tests/test_deployment_wiring.py": "18-aws-deployment",
    }
    if all(stage in stage_positions for stage in set(assembly_paths.values()) | {"11-orders"}):
        owners_by_path: dict[str, list[str]] = {}
        for component_id, component in components.items():
            for path in component["paths"]:
                owners_by_path.setdefault(path, []).append(component_id)
        for path, introduced_stage in assembly_paths.items():
            owners = owners_by_path.get(path, [])
            if not owners:
                raise ValueError(
                    f"Course blueprint must model assembled-system path {path!r} as a component."
                )
            if not any(components[owner]["introduced_stage"] == introduced_stage for owner in owners):
                raise ValueError(
                    f"Course blueprint path {path!r} must have a component introduced in "
                    f"{introduced_stage!r}."
                )
        for path in ("src/http_server.py", "src/web/app.js"):
            owners = owners_by_path[path]
            if not any(owner in stages["11-orders"]["evolved_components"] for owner in owners):
                raise ValueError(
                    f"Course blueprint Stage '11-orders' must evolve the component owning {path!r}."
                )

    return blueprint


def load_blueprint(path: Path, stage_names: list[str]) -> dict[str, Any]:
    """Load and validate the visible JSON course blueprint."""
    try:
        blueprint = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise FileNotFoundError(f"Course blueprint not found: {path}") from None
    except json.JSONDecodeError as error:
        raise ValueError(f"Course blueprint is not valid JSON: {path}") from error
    return validate_blueprint(normalize_blueprint_continuity(blueprint, stage_names), stage_names)


def _component_active(component: dict[str, Any], stage_index: int, positions: dict[str, int]) -> bool:
    if positions[component["introduced_stage"]] > stage_index:
        return False
    retired = component.get("retired_after_stage")
    return retired is None or stage_index <= positions[retired]


def normalize_blueprint_continuity(
    blueprint: dict[str, Any],
    stage_names: list[str],
) -> dict[str, Any]:
    """Derive exhaustive stage classifications from declared component and contract lifetimes."""
    normalized = copy.deepcopy(blueprint)
    components = normalized.get("components")
    contracts = normalized.get("contracts")
    stages = normalized.get("stages")
    if not isinstance(components, list) or not isinstance(contracts, list) or not isinstance(stages, list):
        return normalized

    positions = {name: index for index, name in enumerate(stage_names)}
    component_records: list[dict[str, Any]] = []
    component_ids: set[str] = set()
    for component in components:
        if not isinstance(component, dict):
            return normalized
        component_id = component.get("id")
        introduced = component.get("introduced_stage")
        retired = component.get("retired_after_stage")
        if (
            not isinstance(component_id, str)
            or component_id in component_ids
            or introduced not in positions
            or (retired is not None and retired not in positions)
        ):
            return normalized
        component_ids.add(component_id)
        component_records.append(component)

    contract_records: list[dict[str, Any]] = []
    contract_ids: set[str] = set()
    for contract in contracts:
        if not isinstance(contract, dict):
            return normalized
        contract_id = contract.get("id")
        introduced = contract.get("introduced_stage")
        if (
            not isinstance(contract_id, str)
            or contract_id in contract_ids
            or introduced not in positions
        ):
            return normalized
        contract_ids.add(contract_id)
        contract_records.append(contract)

    stage_records: dict[str, dict[str, Any]] = {}
    for stage in stages:
        if not isinstance(stage, dict) or stage.get("name") not in positions:
            return normalized
        stage_name = stage["name"]
        if stage_name in stage_records:
            return normalized
        if not isinstance(stage.get("evolved_components"), list):
            return normalized
        stage_records[stage_name] = stage
    if set(stage_records) != set(stage_names):
        return normalized

    required_paths_by_stage = {
        "07-api-gateway": ["tests/test_web_app.js"],
        "08-relational-persistence": [
            "data/schema.sql",
            "data/seed.sql",
            "data/init_db.py",
            "src/db_adapter.py",
        ],
        "11-orders": ["tests/test_http_order_flow.py", "tests/test_sqlite_orders.py"],
        "15-pick-ticket-worker": [
            "deploy/pick-ticket-worker/tinywms-pick-ticket-worker.service.in",
            "deploy/pick-ticket-worker/install_user_service.sh",
            "deploy/pick-ticket-worker/environment.example",
            "deploy/pick-ticket-worker/README.md",
        ],
        "17-container-worker": ["deploy/container-worker/README.md"],
        "19-git-history": ["docs/git-history.md"],
        "20-final-walkthrough": [
            "docs/demo-runbook.md",
            "tests/test_demo_runbook.py",
            "tests/test_end_to_end_walkthrough.py",
        ],
    }
    for stage_name, paths in required_paths_by_stage.items():
        if stage_name not in stage_records:
            continue
        required_paths = stage_records[stage_name].get("required_paths")
        if not isinstance(required_paths, list):
            continue
        for path in paths:
            if path not in required_paths:
                required_paths.append(path)

    for stage_name in stage_names:
        stage = stage_records[stage_name]
        stage_index = positions[stage_name]
        active_ids = [
            component["id"]
            for component in component_records
            if positions[component["introduced_stage"]] <= stage_index
            and (
                component.get("retired_after_stage") is None
                or stage_index <= positions[component["retired_after_stage"]]
            )
        ]
        added_ids = [
            component["id"]
            for component in component_records
            if component["introduced_stage"] == stage_name
        ]
        evolved_ids: list[str] = []
        for component_id in stage["evolved_components"]:
            if (
                isinstance(component_id, str)
                and component_id in active_ids
                and component_id not in added_ids
                and component_id not in evolved_ids
            ):
                evolved_ids.append(component_id)
        reused_ids = [
            component_id
            for component_id in active_ids
            if component_id not in added_ids and component_id not in evolved_ids
        ]
        stage["added_components"] = added_ids
        stage["evolved_components"] = evolved_ids
        stage["reused_components"] = reused_ids
        stage["introduced_contracts"] = [
            contract["id"]
            for contract in contract_records
            if contract["introduced_stage"] == stage_name
        ]
        stage["inherited_contracts"] = [
            contract["id"]
            for contract in contract_records
            if positions[contract["introduced_stage"]] < stage_index
        ]

    return normalized


def validate_snapshot_against_blueprint(
    stage_name: str,
    snapshot: dict[str, str],
    blueprint: dict[str, Any],
    stage_names: list[str],
) -> None:
    """Require current components and reject paths belonging only to future lessons."""
    positions = {name: index for index, name in enumerate(stage_names)}
    if stage_name not in positions:
        raise ValueError(f"Course blueprint has no stage named {stage_name!r}.")
    stage_index = positions[stage_name]
    stage = blueprint["stages"][stage_index]

    required_paths = set(stage["required_paths"])
    historically_required_paths = {
        path
        for earlier_stage in blueprint["stages"][: stage_index + 1]
        for path in earlier_stage["required_paths"]
    }
    active_paths: set[str] = set()
    future_paths: set[str] = set()
    for component in blueprint["components"]:
        component_paths = set(component["paths"])
        if _component_active(component, stage_index, positions):
            active_paths.update(component_paths)
        elif positions[component["introduced_stage"]] > stage_index:
            future_paths.update(component_paths)
    for contract in blueprint["contracts"]:
        contract_paths = set(contract["schema_paths"])
        if positions[contract["introduced_stage"]] <= stage_index:
            active_paths.update(contract_paths)
        else:
            future_paths.update(contract_paths)

    missing = sorted((required_paths | active_paths) - snapshot.keys())
    if missing:
        raise ValueError(
            f"Stage {stage_name} is missing blueprint-required paths: {missing}."
        )
    # A path explicitly required by this or an earlier stage is already available even if a component
    # formally adopts it later. Shared documentation such as README.md is established in Stage 0 and
    # inherited throughout the course; only paths never made available by this point are leakage.
    leaked = sorted(
        (future_paths - active_paths - historically_required_paths) & snapshot.keys()
    )
    if leaked:
        raise ValueError(
            f"Stage {stage_name} contains paths reserved for later blueprint stages: {leaked}."
        )


def validate_reference_snapshot(
    stage_name: str,
    snapshot: dict[str, str],
    stage_names: list[str],
) -> None:
    """Validate the reference's embedded blueprint against its complete file tree."""
    if stage_name != stage_names[-1]:
        raise ValueError(f"Final reference must target {stage_names[-1]!r}, not {stage_name!r}.")
    if BLUEPRINT_NAME not in snapshot:
        raise ValueError(f"Final reference must include {BLUEPRINT_NAME}.")
    try:
        blueprint = json.loads(snapshot[BLUEPRINT_NAME])
    except json.JSONDecodeError as error:
        raise ValueError(f"Final reference {BLUEPRINT_NAME} is not valid JSON.") from error
    blueprint = normalize_blueprint_continuity(blueprint, stage_names)
    validate_blueprint(blueprint, stage_names)
    validate_snapshot_against_blueprint(stage_name, snapshot, blueprint, stage_names)


def blueprint_context(
    blueprint: dict[str, Any],
    stage_names: list[str],
    requested_stage_names: list[str],
) -> str:
    """Return a focused JSON slice for forward generation without hiding future constraints."""
    positions = {name: index for index, name in enumerate(stage_names)}
    first_index = positions[requested_stage_names[0]]
    last_index = positions[requested_stage_names[-1]]
    components = blueprint["components"]
    contracts = blueprint["contracts"]
    context = {
        "reference_stage": blueprint["reference_stage"],
        "available_components_at_start": [
            component for component in components
            if positions[component["introduced_stage"]] < first_index
            and _component_active(component, first_index, positions)
        ],
        "target_stage_specs": blueprint["stages"][first_index : last_index + 1],
        "components_introduced_in_targets": [
            component for component in components
            if first_index <= positions[component["introduced_stage"]] <= last_index
        ],
        "contracts_available_through_targets": [
            contract for contract in contracts
            if positions[contract["introduced_stage"]] <= last_index
        ],
        "future_components_do_not_implement": [
            {
                "id": component["id"],
                "introduced_stage": component["introduced_stage"],
                "paths": component["paths"],
            }
            for component in components
            if positions[component["introduced_stage"]] > last_index
        ],
    }
    return json.dumps(context, indent=2, sort_keys=True)


def reference_implementation_context(
    blueprint: dict[str, Any],
    stage_names: list[str],
    stage_name: str,
    reference_snapshot: dict[str, str],
    excluded_paths: set[str] | None = None,
) -> str:
    """Expose final component examples relevant to one forward stage."""
    positions = {name: index for index, name in enumerate(stage_names)}
    stage = blueprint["stages"][positions[stage_name]]
    component_ids = set(stage["added_components"]) | set(stage["evolved_components"])
    contract_ids = set(stage["introduced_contracts"])
    paths = set(stage["required_paths"])
    evolved_paths: dict[str, list[str]] = {}

    for component in blueprint["components"]:
        if component["id"] in component_ids:
            paths.update(component["paths"])
        if component["id"] in stage["evolved_components"]:
            evolved_paths[component["id"]] = component["paths"]
    for contract in blueprint["contracts"]:
        if contract["id"] in contract_ids:
            paths.update(contract["schema_paths"])

    # Final shared narratives describe the whole semester and would leak later
    # lessons backward. Component code and tests are still useful concrete targets.
    excluded = {
        "README.md",
        "docs/architecture.md",
        "docs/data-contracts.md",
        BLUEPRINT_NAME,
        "handoff/regen-notes.json",
    }
    excluded.update(excluded_paths or set())
    files = {
        path: reference_snapshot[path]
        for path in sorted(paths - excluded)
        if path in reference_snapshot
    }
    if not files:
        return ""

    return "REFERENCE IMPLEMENTATION EXCERPTS\n" + json.dumps(
        {
            "stage": stage_name,
            "adaptation_rule": (
                "Use these mature final implementations as concrete design and contract evidence. "
                "Adapt only behavior introduced by the current stage; do not leak future-stage behavior. "
                "An evolved component requires a real implementation delta: emit complete replacements "
                "for the relevant evolved paths instead of changing documentation alone."
            ),
            "evolved_component_paths": evolved_paths,
            "reference_files": files,
        },
        indent=2,
        sort_keys=True,
    )


def blueprint_prompt_contract(stage_names: list[str]) -> str:
    """Describe the JSON artifact the final reference must expose."""
    return f"""FINAL-FIRST REFERENCE REQUIREMENT
Generate a complete standalone final TinyWMS repository for {stage_names[-1]} that visibly preserves
the useful earlier implementations. Also create `{BLUEPRINT_NAME}` as valid JSON with this shape:

{{
  "schema_version": 1,
  "reference_stage": "{stage_names[-1]}",
  "contracts": [{{
    "id": "stable-kebab-case-id",
    "name": "human name",
    "introduced_stage": "exact stage name",
    "representation": "visible JSON, HTTP, SQL, queue, or event representation",
    "schema_paths": ["concrete/path"],
    "producer_components": ["component-id"],
    "consumer_components": ["component-id"],
    "compatibility_checks": ["exact command from stage root"]
  }}],
  "components": [{{
    "id": "stable-kebab-case-id",
    "name": "human name",
    "introduced_stage": "exact stage name",
    "retired_after_stage": null,
    "kind": "application|contract|infrastructure|operations",
    "runtime": "where it runs",
    "paths": ["concrete/path"],
    "inbound_contracts": ["contract-id"],
    "outbound_contracts": ["contract-id"],
    "dependencies": ["component-id-or-contract-id"]
  }}],
  "stages": [{{
    "name": "exact stage name",
    "purpose": "lesson-specific purpose",
    "added_components": ["component-id"],
    "reused_components": ["component-id"],
    "evolved_components": ["component-id"],
    "introduced_contracts": ["contract-id"],
    "inherited_contracts": ["contract-id"],
    "boundary_shift": "what changes at this stage",
    "required_paths": ["additional concrete/path"],
    "continuity_checks": ["exact safe local command from stage root"]
  }}]
}}

The stages array must contain these exact names in this exact order:
{json.dumps(stage_names)}

Every component path and contract schema path must exist in the final reference. At each stage, classify
every active component exactly once as added, reused, or evolved. Split contracts exactly into those
introduced in this stage and those inherited from prior stages. A component must appear in added_components
at its introduced stage. A dependency may name either a component or a contract, and every referenced ID
must resolve. Build the component ID set first, then ensure every producer_components, consumer_components,
stage classification, and component dependency reference uses an ID from the appropriate declared set. Keep
predecessor-specific implementations visible in the final reference when the course evolution rules call
for comparison. The toolchain derives added_components from introduced_stage, derives introduced_contracts
and inherited_contracts from contract introduction stages, preserves valid evolved_components choices, and
fills reused_components with the remaining active components before validation. The blueprint is planning
metadata for the generator and must not be copied into ordinary generated course stages.

The assembled-system blueprint must explicitly model these concrete paths at their teaching stages:
- `src/http_server.py` at `03-pi-http-server`, evolved at `11-orders` for the integrated local order path;
- `src/web/app.js` at `04-browser`, evolved at `11-orders` for the integrated inventory/order page;
- `tests/test_http_order_flow.py` as a required path at `11-orders` for the local order round trip;
- `src/sqs_consumer.py` at `13-sqs` for real receive/delete semantics;
- `infra/events.yaml`, `src/event_consumer_a.py`, and `src/event_consumer_b.py` at `14-domain-events`;
- `src/pick_ticket_worker.py` at `15-pick-ticket-worker` for the long-running idempotent worker;
- `tests/test_callback_integration.py` at `16-callback-demo` as the local assembly proof;
- `src/Dockerfile` at `17-container-worker` for the unchanged worker contract in a container; and
- `tests/test_deployment_wiring.py` at `18-aws-deployment` as the cloud assembly proof.

Their component dependencies must name the command/event contracts they consume. The Stage 15 worker must
remain active and reused through Stages 16-20. Do not collapse the SQS command path and EventBridge event
path into one component or contract.
"""
