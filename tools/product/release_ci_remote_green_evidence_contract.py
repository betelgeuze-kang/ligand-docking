#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]

REPO = "betelgeuze-kang/ligand-docking"
DEFAULT_BRANCH = "main"
WORKFLOW_FILE = "product-image-smoke.yml"
CONTRACT_SCHEMA_VERSION = "release_ci_remote_green_evidence_contract_v1"
DEFAULT_MANIFEST_JSON = "runs/release_ci_remote_green_evidence_collect_manifest_current.json"
PLACEHOLDER_STATUS = "blocked_release_ci_remote_green_evidence_placeholder"

CLAIM_BOUNDARY = (
    "Release CI remote-green evidence collection contract is read-only. It emits exact gh api "
    "commands and validates supplied JSON shape only. It does not register runners, dispatch "
    "workflows, change branch protection, edit required checks, create tags, upload artifacts, "
    "deploy, publish, or mutate external state. The explicit --execute mode runs the same read-only "
    "GitHub API collection commands and writes only local evidence JSON files."
)


@dataclass(frozen=True)
class EvidenceInputSpec:
    input_id: str
    receipt_arg: str
    default_output_path: str
    gh_api_endpoint: str
    collect_command: str
    discovery_command: str
    required_top_level_keys: tuple[str, ...]
    description: str


def _workflow_runs_endpoint(*, event: str | None = None) -> str:
    base = f"repos/{REPO}/actions/workflows/{WORKFLOW_FILE}/runs"
    if event:
        return f"{base}?event={event}&per_page=30"
    return f"{base}?per_page=30"


EVIDENCE_INPUTS: tuple[EvidenceInputSpec, ...] = (
    EvidenceInputSpec(
        input_id="runner_inventory",
        receipt_arg="runner_inventory_json",
        default_output_path="runs/github_self_hosted_runner_inventory_current.json",
        gh_api_endpoint=f"repos/{REPO}/actions/runners",
        collect_command=(
            f"gh api repos/{REPO}/actions/runners --paginate > "
            "runs/github_self_hosted_runner_inventory_current.json"
        ),
        discovery_command="",
        required_top_level_keys=("runners",),
        description="Online self-hosted runner inventory with Linux and ROCm labels.",
    ),
    EvidenceInputSpec(
        input_id="main_branch",
        receipt_arg="branch_json",
        default_output_path="runs/release_ci_branch_main_current.json",
        gh_api_endpoint=f"repos/{REPO}/branches/{DEFAULT_BRANCH}",
        collect_command=(
            f"gh api repos/{REPO}/branches/{DEFAULT_BRANCH} > "
            "runs/release_ci_branch_main_current.json"
        ),
        discovery_command="",
        required_top_level_keys=("name", "protected"),
        description="main branch protection envelope including protected flag.",
    ),
    EvidenceInputSpec(
        input_id="main_required_checks",
        receipt_arg="required_checks_json",
        default_output_path="runs/release_ci_required_status_checks_main_current.json",
        gh_api_endpoint=f"repos/{REPO}/branches/{DEFAULT_BRANCH}/protection/required_status_checks",
        collect_command=(
            f"gh api repos/{REPO}/branches/{DEFAULT_BRANCH}/protection/required_status_checks > "
            "runs/release_ci_required_status_checks_main_current.json || "
            "printf '%s\\n' "
            "'{\"contexts\":[],\"checks\":[],\"collection_error\":\"required_status_checks_unavailable_or_branch_unprotected\",\"external_state_mutated\":false}' "
            "> runs/release_ci_required_status_checks_main_current.json"
        ),
        discovery_command="",
        required_top_level_keys=("contexts",),
        description="Required status check contexts configured for main branch protection.",
    ),
    EvidenceInputSpec(
        input_id="schedule_runs",
        receipt_arg="schedule_runs_json",
        default_output_path="runs/release_ci_product_image_smoke_schedule_runs_current.json",
        gh_api_endpoint=_workflow_runs_endpoint(event="schedule"),
        collect_command=(
            f"gh api '{_workflow_runs_endpoint(event='schedule')}' > "
            "runs/release_ci_product_image_smoke_schedule_runs_current.json"
        ),
        discovery_command="",
        required_top_level_keys=("workflow_runs",),
        description="Scheduled product-image-smoke workflow runs for weekly ROCm runtime evidence.",
    ),
    EvidenceInputSpec(
        input_id="failed_run_artifacts",
        receipt_arg="failed_run_artifacts_json",
        default_output_path="runs/release_ci_failed_run_artifacts_current.json",
        gh_api_endpoint=f"repos/{REPO}/actions/runs/{{failed_run_id}}/artifacts",
        collect_command=(
            "if [ -n \"${RELEASE_CI_FAILED_RUN_ID:-}\" ]; then "
            "gh api "
            f"repos/{REPO}/actions/runs/${{RELEASE_CI_FAILED_RUN_ID}}/artifacts > "
            "runs/release_ci_failed_run_artifacts_current.json; "
            "else "
            "printf '%s\\n' "
            "'{\"total_count\":0,\"artifacts\":[],\"collection_error\":\"no_failed_product_image_run_found\",\"external_state_mutated\":false}' "
            "> runs/release_ci_failed_run_artifacts_current.json; "
            "fi"
        ),
        discovery_command=(
            f"RELEASE_CI_FAILED_RUN_ID=$(gh api 'repos/{REPO}/actions/workflows/{WORKFLOW_FILE}/runs?status=failure&per_page=1' "
            "--jq '.workflow_runs[0].id // empty' 2>/dev/null || true)"
        ),
        required_top_level_keys=("artifacts",),
        description=(
            "Artifacts from the latest failed product-image-smoke run; must include active "
            "receipt/log artifact names."
        ),
    ),
    EvidenceInputSpec(
        input_id="release_tag_runs",
        receipt_arg="release_tag_runs_json",
        default_output_path="runs/release_ci_product_image_smoke_push_runs_current.json",
        gh_api_endpoint=_workflow_runs_endpoint(event="push"),
        collect_command=(
            f"gh api '{_workflow_runs_endpoint(event='push')}' > "
            "runs/release_ci_product_image_smoke_push_runs_current.json"
        ),
        discovery_command="",
        required_top_level_keys=("workflow_runs",),
        description=(
            "Push-triggered product-image-smoke runs; receipt filters v* and product-* tag refs."
        ),
    ),
)

EVIDENCE_INPUT_BY_ID = {spec.input_id: spec for spec in EVIDENCE_INPUTS}
EVIDENCE_INPUT_BY_RECEIPT_ARG = {spec.receipt_arg: spec for spec in EVIDENCE_INPUTS}


def _spec_row(spec: EvidenceInputSpec) -> dict[str, Any]:
    return {
        "input_id": spec.input_id,
        "receipt_arg": spec.receipt_arg,
        "default_output_path": spec.default_output_path,
        "gh_api_endpoint": spec.gh_api_endpoint,
        "collect_command": spec.collect_command,
        "discovery_command": spec.discovery_command,
        "required_top_level_keys": list(spec.required_top_level_keys),
        "description": spec.description,
        "external_state_mutated": False,
    }


def build_release_ci_remote_green_placeholder_payload(input_id: str) -> dict[str, Any]:
    spec = EVIDENCE_INPUT_BY_ID[input_id]
    placeholder = {
        "status": PLACEHOLDER_STATUS,
        "input_id": input_id,
        "description": spec.description,
        "reason": "read_only_github_evidence_not_collected",
        "collect_command": spec.collect_command,
        "external_state_mutated": False,
    }
    if input_id == "runner_inventory":
        return {"total_count": 0, "runners": [], "placeholder": placeholder}
    if input_id == "main_branch":
        return {
            "name": DEFAULT_BRANCH,
            "protected": False,
            "protection": {
                "enabled": False,
                "required_status_checks": {
                    "enforcement_level": "off",
                    "contexts": [],
                    "checks": [],
                },
            },
            "placeholder": placeholder,
        }
    if input_id == "main_required_checks":
        return {
            "contexts": [],
            "checks": [],
            "placeholder": placeholder,
        }
    if input_id in {"schedule_runs", "release_tag_runs"}:
        return {"total_count": 0, "workflow_runs": [], "placeholder": placeholder}
    if input_id == "failed_run_artifacts":
        return {"total_count": 0, "artifacts": [], "placeholder": placeholder}
    raise KeyError(input_id)


def emit_release_ci_remote_green_placeholder_evidence(
    *,
    root: str | Path = ROOT,
    paths: dict[str, str | Path] | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    root_path = Path(root)
    selected_paths = paths or {spec.input_id: spec.default_output_path for spec in EVIDENCE_INPUTS}
    rows = []
    for spec in EVIDENCE_INPUTS:
        path = Path(selected_paths.get(spec.input_id, spec.default_output_path))
        if not path.is_absolute():
            path = root_path / path
        existed_before = path.exists()
        wrote_placeholder = bool(overwrite or not existed_before)
        if wrote_placeholder:
            path.parent.mkdir(parents=True, exist_ok=True)
            payload = build_release_ci_remote_green_placeholder_payload(spec.input_id)
            path.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        rows.append(
            {
                "input_id": spec.input_id,
                "path": str(path),
                "existed_before": existed_before,
                "wrote_placeholder": wrote_placeholder,
                "overwrote_existing": bool(wrote_placeholder and existed_before),
                "external_state_mutated": False,
            }
        )
    return {
        "summary": {
            "packet_type": "release_ci_remote_green_placeholder_evidence",
            "schema_version": CONTRACT_SCHEMA_VERSION,
            "status": "release_ci_remote_green_placeholder_evidence_ready",
            "input_count": len(EVIDENCE_INPUTS),
            "placeholder_written_count": sum(1 for row in rows if row["wrote_placeholder"]),
            "existing_preserved_count": sum(1 for row in rows if not row["wrote_placeholder"]),
            "overwrite": bool(overwrite),
            "external_state_mutated": False,
            "claim_boundary": CLAIM_BOUNDARY,
        },
        "rows": rows,
    }


def build_release_ci_remote_green_evidence_contract() -> dict[str, Any]:
    return {
        "packet_type": "release_ci_remote_green_evidence_contract",
        "schema_version": CONTRACT_SCHEMA_VERSION,
        "repo": REPO,
        "branch": DEFAULT_BRANCH,
        "workflow_file": WORKFLOW_FILE,
        "claim_boundary": CLAIM_BOUNDARY,
        "external_state_mutated": False,
        "inputs": [_spec_row(spec) for spec in EVIDENCE_INPUTS],
        "placeholder_builder_command": (
            "python3 tools/product/release_ci_remote_green_evidence_contract.py --emit-placeholders"
        ),
        "receipt_builder_command": (
            "python3 tools/product/build_release_ci_remote_green_receipt.py "
            "--runner-inventory-json runs/github_self_hosted_runner_inventory_current.json "
            "--branch-json runs/release_ci_branch_main_current.json "
            "--required-checks-json runs/release_ci_required_status_checks_main_current.json "
            "--schedule-runs-json runs/release_ci_product_image_smoke_schedule_runs_current.json "
            "--failed-run-artifacts-json runs/release_ci_failed_run_artifacts_current.json "
            "--release-tag-runs-json runs/release_ci_product_image_smoke_push_runs_current.json"
        ),
    }


def emit_release_ci_remote_green_collect_commands(*, include_discovery: bool = True) -> list[str]:
    commands: list[str] = []
    for spec in EVIDENCE_INPUTS:
        if include_discovery and spec.discovery_command:
            commands.append(spec.discovery_command)
        commands.append(spec.collect_command)
    return commands


def emit_release_ci_remote_green_collect_shell_script() -> str:
    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "",
        "# Read-only GitHub API evidence collection for release CI remote-green receipt.",
        "# Requires gh auth and repo read access. Does not mutate GitHub settings.",
        "",
    ]
    lines.extend(emit_release_ci_remote_green_collect_commands())
    lines.append("")
    lines.append(build_release_ci_remote_green_evidence_contract()["receipt_builder_command"])
    lines.append("")
    return "\n".join(lines)


def validate_release_ci_remote_green_evidence_payload(
    input_id: str,
    payload: Any,
) -> dict[str, Any]:
    spec = EVIDENCE_INPUT_BY_ID.get(input_id)
    if spec is None:
        return {
            "input_id": input_id,
            "valid": False,
            "present": False,
            "error": "unknown_input_id",
        }
    if payload in (None, "", {}):
        return {
            "input_id": input_id,
            "receipt_arg": spec.receipt_arg,
            "valid": False,
            "present": False,
            "error": "missing_or_empty_payload",
            "required_top_level_keys": list(spec.required_top_level_keys),
        }
    if not isinstance(payload, dict):
        return {
            "input_id": input_id,
            "receipt_arg": spec.receipt_arg,
            "valid": False,
            "present": True,
            "error": "payload_not_object",
            "required_top_level_keys": list(spec.required_top_level_keys),
        }
    missing_keys = [key for key in spec.required_top_level_keys if key not in payload]
    if missing_keys:
        return {
            "input_id": input_id,
            "receipt_arg": spec.receipt_arg,
            "valid": False,
            "present": True,
            "error": "missing_required_keys",
            "missing_keys": missing_keys,
            "required_top_level_keys": list(spec.required_top_level_keys),
        }
    return {
        "input_id": input_id,
        "receipt_arg": spec.receipt_arg,
        "valid": True,
        "present": True,
        "required_top_level_keys": list(spec.required_top_level_keys),
    }


def _read_json_file(root: Path, path_like: str | Path) -> Any:
    path = Path(path_like)
    if not path.is_absolute():
        path = root / path
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def validate_release_ci_remote_green_evidence_files(
    *,
    root: str | Path = ROOT,
    paths: dict[str, str | Path] | None = None,
) -> dict[str, Any]:
    root_path = Path(root)
    selected_paths = paths or {spec.input_id: spec.default_output_path for spec in EVIDENCE_INPUTS}
    rows = []
    for spec in EVIDENCE_INPUTS:
        payload = _read_json_file(root_path, selected_paths.get(spec.input_id, spec.default_output_path))
        row = validate_release_ci_remote_green_evidence_payload(spec.input_id, payload)
        row["path"] = str(selected_paths.get(spec.input_id, spec.default_output_path))
        rows.append(row)
    invalid_count = sum(1 for row in rows if not row["valid"])
    return {
        "schema_version": CONTRACT_SCHEMA_VERSION,
        "valid": invalid_count == 0,
        "invalid_count": invalid_count,
        "rows": rows,
        "external_state_mutated": False,
    }


def build_release_ci_remote_green_evidence_collect_manifest(
    *,
    root: str | Path = ROOT,
    validate_paths: dict[str, str | Path] | None = None,
) -> dict[str, Any]:
    contract = build_release_ci_remote_green_evidence_contract()
    validation = validate_release_ci_remote_green_evidence_files(root=root, paths=validate_paths)
    return {
        "summary": {
            "packet_type": "release_ci_remote_green_evidence_collect_manifest",
            "schema_version": CONTRACT_SCHEMA_VERSION,
            "repo": REPO,
            "branch": DEFAULT_BRANCH,
            "workflow_file": WORKFLOW_FILE,
            "input_count": len(EVIDENCE_INPUTS),
            "collect_command_count": len(emit_release_ci_remote_green_collect_commands()),
            "validation_valid": validation["valid"],
            "validation_invalid_count": validation["invalid_count"],
            "external_state_mutated": False,
            "claim_boundary": CLAIM_BOUNDARY,
            "receipt_builder_command": contract["receipt_builder_command"],
        },
        "contract": contract,
        "collect_commands": emit_release_ci_remote_green_collect_commands(),
        "validation": validation,
    }


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = Path(path_like)
    if not path.is_absolute():
        path = ROOT / path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def execute_release_ci_remote_green_collect_commands(
    *,
    execute_fn: Callable[[str], int] | None = None,
) -> dict[str, Any]:
    runner = execute_fn or _default_execute
    rows = []
    for spec in EVIDENCE_INPUTS:
        commands = []
        if spec.discovery_command:
            commands.append(f"{spec.discovery_command}\n{spec.collect_command}")
        else:
            commands.append(spec.collect_command)
        exit_codes = [runner(command) for command in commands]
        rows.append(
            {
                "input_id": spec.input_id,
                "commands": commands,
                "exit_codes": exit_codes,
                "passed": all(code == 0 for code in exit_codes),
            }
        )
    return {
        "executed": True,
        "external_state_mutated": False,
        "rows": rows,
        "passed": all(row["passed"] for row in rows),
    }


def _default_execute(command: str) -> int:
    return subprocess.run(["bash", "-lc", command], check=False).returncode


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Emit or validate read-only release CI remote-green GitHub evidence contract.",
    )
    parser.add_argument("--emit-manifest", action="store_true", help="Write collect manifest JSON.")
    parser.add_argument(
        "--emit-placeholders",
        action="store_true",
        help="Write fail-closed placeholder JSON for missing evidence inputs.",
    )
    parser.add_argument(
        "--overwrite-placeholders",
        action="store_true",
        help="Allow --emit-placeholders to overwrite existing evidence JSON files.",
    )
    parser.add_argument("--emit-shell-script", action="store_true", help="Print bash collect script.")
    parser.add_argument("--print-commands", action="store_true", help="Print gh collect commands.")
    parser.add_argument("--validate", action="store_true", help="Validate default evidence JSON files.")
    parser.add_argument("--execute", action="store_true", help="Execute collect commands via bash.")
    parser.add_argument("--out-json", default=DEFAULT_MANIFEST_JSON)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.print_commands:
        for command in emit_release_ci_remote_green_collect_commands():
            print(command)
        return 0
    if args.emit_shell_script:
        print(emit_release_ci_remote_green_collect_shell_script(), end="")
        return 0
    if args.execute:
        result = execute_release_ci_remote_green_collect_commands()
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["passed"] else 2
    if args.emit_placeholders:
        result = emit_release_ci_remote_green_placeholder_evidence(
            overwrite=args.overwrite_placeholders,
        )
        print(json.dumps(result["summary"], indent=2, sort_keys=True))
        return 0
    manifest = build_release_ci_remote_green_evidence_collect_manifest()
    if args.validate:
        print(json.dumps(manifest["validation"], indent=2, sort_keys=True))
        return 0 if manifest["validation"]["valid"] else 2
    if args.emit_manifest:
        _write_json(args.out_json, manifest)
        print(json.dumps({"out_json": args.out_json, "validation_valid": manifest["validation"]["valid"]}, sort_keys=True))
        return 0 if manifest["validation"]["valid"] else 2
    print(json.dumps(build_release_ci_remote_green_evidence_contract(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
