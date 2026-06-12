#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/goal_api_surface_contract_current.json"
DEFAULT_OUT_CSV = "runs/goal_api_surface_contract_current.csv"
DEFAULT_OUT_MD = "runs/goal_api_surface_contract_current.md"

CLAIM_BOUNDARY = (
    "Goal API surface contract only; it statically audits the read-only local goal API for commercial product, "
    "CAMEO validation, CASP17 transition, and cleanup status. It does not start a server, run docking, install "
    "packages, submit predictions, register servers, send email, delete, archive, externalize, upload, or mutate "
    "external state."
)

EXPECTED_ENDPOINTS = {
    "/status": "get_goal_status",
    "/readiness": "get_goal_readiness",
    "/actions": "get_goal_actions",
    "/operator-intake-kit": "get_goal_operator_intake_kit",
    "/release-decision": "get_goal_release_decision",
    "/burndown": "get_goal_burndown",
    "/bottlenecks": "get_goal_bottlenecks",
    "/api-contract": "get_goal_api_contract",
}

EXPECTED_ARTIFACT_CONSTANTS = {
    "GOAL_READINESS_ROLLUP_ARTIFACT",
    "GOAL_OPERATOR_ACTION_BOARD_ARTIFACT",
    "GOAL_OPERATOR_INTAKE_KIT_MANIFEST",
    "GOAL_RELEASE_DECISION_ARTIFACT",
    "GOAL_RELEASE_BURNDOWN_ARTIFACT",
    "GOAL_BOTTLENECK_BRIEFING_ARTIFACT",
    "GOAL_API_SURFACE_CONTRACT_ARTIFACT",
    "PRODUCT_COMMERCIAL_READINESS_HANDOFF_BUNDLE_ARTIFACT",
}

REQUIRED_FULL_COMMERCIAL_VISIBILITY_TOKENS = {
    "FULL_COMMERCIAL_RELEASE_BLOCKER_IDS",
    "R8_full_scope_claim_closure",
    "R9_engine_refinement_claim_promotion",
    "full_commercial_release_blocker_visibility_ready",
    "missing_full_commercial_release_blocker_ids",
}

REQUIRED_STATUS_KEYS = {
    "product_cli_status_set_status",
    "cameo_cli_status_set_status",
    "cleanup_cli_status_set_status",
    "approval_tokens",
    "approval_reclaim_size_gb",
    "protected_cleanup_payload_size_gb",
    "product_operational_quality_ready",
    "product_operational_quality_status",
    "product_operational_quality_blocker_count",
    "product_operational_quality_artifact",
    "cameo_evidence_integrity_ready",
    "cameo_evidence_integrity_status",
    "cameo_evidence_integrity_blocker_count",
    "cameo_evidence_integrity_artifact",
    "cameo_official_results_pending_honest",
    "cameo_no_local_native_accuracy_substitution",
    "release_allowed",
    "release_blocker_count",
    "bottleneck_count",
    "primary_bottleneck_kind",
    "primary_bottleneck_phase",
    "primary_bottleneck_root_cause_category",
    "primary_bottleneck_locally_closable_without_operator_return",
    "primary_bottleneck_required_external_return",
    "primary_bottleneck_post_return_acceptance_artifact",
    "completion_audit_release_blocker_bottleneck_count",
    "irreducible_external_return_bottleneck_count",
    "expected_full_commercial_release_blocker_ids",
    "full_commercial_release_blocker_ids",
    "full_commercial_release_blocker_count",
    "missing_full_commercial_release_blocker_ids",
    "full_commercial_release_blocker_visibility_ready",
    "commercial_readiness_handoff_bundle_status",
    "commercial_readiness_handoff_bundle_ready",
    "commercial_readiness_handoff_bundle_artifact_path",
    "commercial_readiness_handoff_bundle_artifact_reference_count",
    "commercial_readiness_handoff_bundle_local_missing_artifact_reference_count",
    "operator_action_count",
    "operator_intake_kit_status",
    "operator_intake_kit_release_burndown_linked_entry_count",
    "primary_action_id",
    "primary_action_status",
    "primary_action_required_input",
    "primary_action_command",
    "primary_action_recommended_action",
    "primary_action_artifact_path",
    "goal_api_surface_contract_status",
    "release_complete_vs_operator_pending_lane",
    "goal_completion_audit_goal_complete",
    "release_complete_lane_ready",
    "operator_pending_lane_ready",
}

REQUIRED_FAIL_CLOSED_FLAGS = {
    "execution_enabled",
    "action_executed",
    "delete_executed",
    "archive_executed",
    "externalize_executed",
    "upload_executed",
    "docking_results_emitted",
    "prediction_generation_enabled",
    "server_registration_mutated",
    "outbound_email_enabled",
    "external_state_mutated",
}


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _file_text(root: Path, path_like: str) -> str:
    path = root / path_like
    if not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _row(check: str, passed: bool, observed: str, required: str, artifact_path: str, reason: str) -> dict[str, Any]:
    return {
        "check": check,
        "status": "pass" if passed else "fail",
        "observed": observed,
        "required": required,
        "artifact_path": artifact_path,
        "reason": reason,
        "release_blocker": not passed,
        "execution_enabled": False,
        "action_executed": False,
        "delete_executed": False,
        "archive_executed": False,
        "externalize_executed": False,
        "upload_executed": False,
        "docking_results_emitted": False,
        "prediction_generation_enabled": False,
        "server_registration_mutated": False,
        "outbound_email_enabled": False,
        "external_state_mutated": False,
    }


def _missing_endpoint_tokens(api_text: str) -> list[str]:
    missing: list[str] = []
    for path, function_name in EXPECTED_ENDPOINTS.items():
        if f'"{path}"' not in api_text or function_name not in api_text:
            missing.append(f"GET {path}:{function_name}")
    return missing


def _missing_tokens(api_text: str, tokens: set[str]) -> list[str]:
    return sorted(token for token in tokens if token not in api_text)


def build_goal_api_surface_contract(*, root: str | Path = ".") -> dict[str, Any]:
    root_path = Path(root).resolve()
    api_text = _file_text(root_path, "api/goal.py")
    main_text = _file_text(root_path, "api/main.py")
    security_text = _file_text(root_path, "api/security.py")

    api_file_present = bool(api_text)
    router_registered = "goal_router" in main_text and "app.include_router(goal_router)" in main_text
    security_allowlist_permits_goal = "ALLOWED_PRODUCT_PREFIXES" in security_text and '"/goal"' in security_text
    missing_endpoints = _missing_endpoint_tokens(api_text)
    missing_artifact_constants = _missing_tokens(api_text, EXPECTED_ARTIFACT_CONSTANTS)
    missing_status_keys = _missing_tokens(api_text, REQUIRED_STATUS_KEYS)
    missing_full_commercial_visibility_tokens = _missing_tokens(
        api_text,
        REQUIRED_FULL_COMMERCIAL_VISIBILITY_TOKENS,
    )
    missing_fail_closed_flags = _missing_tokens(api_text, REQUIRED_FAIL_CLOSED_FLAGS)
    contract_endpoint_reads_contract = (
        "GOAL_API_SURFACE_CONTRACT_ARTIFACT" in api_text
        and "get_goal_api_contract" in api_text
        and "missing_goal_api_surface_contract" in api_text
    )

    rows = [
        _row(
            "goal_api_file_present",
            api_file_present,
            f"api/goal.py={api_file_present}",
            "api/goal.py exists",
            "api/goal.py",
            "The full objective needs a dedicated read-only API surface instead of scattered product, CAMEO, CASP17, and cleanup endpoints.",
        ),
        _row(
            "goal_router_registered",
            router_registered,
            f"goal_router_registered={router_registered}",
            "api.main imports and includes goal_router",
            "api/main.py",
            "The goal API must be mounted into the FastAPI app, not only defined as a detached module.",
        ),
        _row(
            "goal_security_allowlist_permits_goal_prefix",
            security_allowlist_permits_goal,
            f"security_allowlist_permits_goal={security_allowlist_permits_goal}",
            "api.security ALLOWED_PRODUCT_PREFIXES includes /goal",
            "api/security.py",
            "The goal API must remain reachable through the production security middleware once it is mounted.",
        ),
        _row(
            "goal_endpoints_present",
            not missing_endpoints,
            f"missing={','.join(missing_endpoints) or 'none'}",
            "all expected /goal read-only endpoints are present",
            "api/goal.py",
            "Operators need one API family for status, readiness, actions, release decision, burndown, and API contract inspection.",
        ),
        _row(
            "goal_local_artifact_sources_present",
            not missing_artifact_constants,
            f"missing={','.join(missing_artifact_constants) or 'none'}",
            "goal endpoints reference all current local goal artifacts",
            "api/goal.py",
            "The goal API must read existing local artifacts rather than infer, approve, or execute work.",
        ),
        _row(
            "goal_status_rollup_keys_present",
            not missing_status_keys,
            f"missing={','.join(missing_status_keys) or 'none'}",
            "/goal/status exposes release, operator, approval-token, protected cleanup, and product/CAMEO/cleanup CLI rollup keys",
            "api/goal.py",
            "The top-level API status needs the same commercial product, CAMEO validation, and cleanup blockers that the JSON/CLI surfaces expose.",
        ),
        _row(
            "goal_full_commercial_bottleneck_visibility_present",
            not missing_full_commercial_visibility_tokens,
            f"missing={','.join(missing_full_commercial_visibility_tokens) or 'none'}",
            "/goal/status exposes R8/R9 full-commercial release blockers and commercial-readiness handoff visibility",
            "api/goal.py",
            "The goal API must not let restricted release readiness hide full-scope transporter or engine-refinement claim blockers.",
        ),
        _row(
            "goal_fail_closed_flags_present",
            not missing_fail_closed_flags,
            f"missing={','.join(missing_fail_closed_flags) or 'none'}",
            "goal endpoint responses visibly preserve disabled execution, deletion, upload, email, registration, and external-mutation flags",
            "api/goal.py",
            "The goal API must be visibly read-only and must not imply docking, submission, cleanup execution, or external mutation happened.",
        ),
        _row(
            "goal_api_contract_endpoint_reads_contract",
            contract_endpoint_reads_contract,
            f"contract_endpoint_reads_contract={contract_endpoint_reads_contract}",
            "/goal/api-contract reads runs/goal_api_surface_contract_current.json and fails closed when missing",
            "api/goal.py",
            "The goal API contract should be inspectable through the same local status surface it validates.",
        ),
    ]
    blockers = [
        {
            "code": f"{row['check']}_not_ready",
            "severity": "hard",
            "check": row["check"],
            "reason": f"{row['reason']} Observed: {row['observed']}; required: {row['required']}.",
        }
        for row in rows
        if row["status"] != "pass"
    ]
    surface_ready = not blockers
    summary = {
        "packet_type": "goal_api_surface_contract",
        "status": "goal_api_surface_contract_ready" if surface_ready else "blocked_goal_api_surface_contract",
        "surface_ready": surface_ready,
        "check_count": len(rows),
        "pass_count": sum(1 for row in rows if row["status"] == "pass"),
        "blocker_count": len(blockers),
        "expected_endpoint_count": len(EXPECTED_ENDPOINTS),
        "missing_endpoint_count": len(missing_endpoints),
        "missing_artifact_source_count": len(missing_artifact_constants),
        "missing_status_key_count": len(missing_status_keys),
        "missing_full_commercial_visibility_token_count": len(
            missing_full_commercial_visibility_tokens
        ),
        "missing_fail_closed_flag_count": len(missing_fail_closed_flags),
        "goal_api_file_present": api_file_present,
        "goal_router_registered": router_registered,
        "goal_security_allowlist_permits_goal_prefix": security_allowlist_permits_goal,
        "goal_api_contract_endpoint_present": '"/api-contract"' in api_text,
        "goal_api_contract_endpoint_reads_contract": contract_endpoint_reads_contract,
        "server_started": False,
        "execution_enabled": False,
        "action_executed": False,
        "delete_executed": False,
        "archive_executed": False,
        "externalize_executed": False,
        "upload_executed": False,
        "docking_results_emitted": False,
        "prediction_generation_enabled": False,
        "server_registration_mutated": False,
        "outbound_email_enabled": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Goal API surface is ready; release still depends on product, CAMEO, cleanup, and operator approval gates."
            if surface_ready
            else "Repair failed goal API surface rows before treating the top-level API as operator-visible."
        ),
    }
    return {"summary": summary, "blockers": blockers, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Goal API Surface Contract",
        "",
        f"- status: `{s['status']}`",
        f"- surface_ready: `{s['surface_ready']}`",
        f"- check_count: `{s['check_count']}`",
        f"- pass_count: `{s['pass_count']}`",
        f"- blocker_count: `{s['blocker_count']}`",
        f"- expected_endpoint_count: `{s['expected_endpoint_count']}`",
        f"- missing_endpoint_count: `{s['missing_endpoint_count']}`",
        f"- missing_artifact_source_count: `{s['missing_artifact_source_count']}`",
        f"- missing_status_key_count: `{s['missing_status_key_count']}`",
        f"- missing_full_commercial_visibility_token_count: `{s['missing_full_commercial_visibility_token_count']}`",
        f"- missing_fail_closed_flag_count: `{s['missing_fail_closed_flag_count']}`",
        f"- goal_router_registered: `{s['goal_router_registered']}`",
        f"- goal_api_contract_endpoint_present: `{s['goal_api_contract_endpoint_present']}`",
        f"- goal_api_contract_endpoint_reads_contract: `{s['goal_api_contract_endpoint_reads_contract']}`",
        f"- execution_enabled: `{s['execution_enabled']}`",
        f"- delete_executed: `{s['delete_executed']}`",
        f"- outbound_email_enabled: `{s['outbound_email_enabled']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Checks",
        "",
        "| check | status | observed | required | artifact | reason |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['check']}` | `{row['status']}` | `{row['observed']}` | "
            f"`{row['required']}` | `{row['artifact_path']}` | {row['reason']} |"
        )
    lines.extend(["", "## Blockers", ""])
    if payload["blockers"]:
        lines.extend(f"- `{blocker['code']}`: {blocker['reason']}" for blocker in payload["blockers"])
    else:
        lines.append("- none")
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a goal API surface contract without starting the API server.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_goal_api_surface_contract(root=args.root)
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
