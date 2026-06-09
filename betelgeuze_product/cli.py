from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from betelgeuze_product.runtime_paths import repo_root

ROOT = repo_root()

ARTIFACTS = {
    "capabilities": "runs/product_capability_surface_contract_current.json",
    "architecture": "runs/product_architecture_contract_current.json",
    "service-boundary": "runs/product_service_boundary_contract_current.json",
    "api-contract": "runs/product_api_contract_current.json",
    "operational-quality": "runs/product_operational_quality_contract_current.json",
    "operations": "runs/product_release_operations_dossier_current.json",
    "public-benchmark": "runs/product_public_benchmark_work_order_current.json",
    "external-metrics": "runs/external_metric_scorecard_current.json",
    "ai-decision-graph": "runs/product_ai_decision_graph_contract_current.json",
    "ai-report-ux": "runs/product_ai_report_ux_contract_current.json",
    "cameo-live-validation": "runs/cameo_validation_operations_dossier_current.json",
    "commercial-independence": "runs/product_commercial_independence_gate_current.json",
    "license-decision": "runs/product_license_decision_gate_current.json",
    "license-options": "runs/product_license_decision_packet_current.json",
    "license-file-work-order": "runs/product_license_file_creation_work_order_current.json",
    "release-readiness": "runs/product_release_operations_dossier_current.json",
    "production-ai-checkpoint-readiness": "runs/product_production_ai_checkpoint_readiness_current.json",
    "production-ai-gpu-return-intake": "runs/product_production_ai_gpu_return_intake_current.json",
    "production-ai-promotion-workbench": "runs/product_production_ai_promotion_workbench_current.json",
    "scope-claim-guard": "runs/product_scope_breadth_closure_checklist_current.json",
    "scope-evidence-priority": "runs/product_scope_breadth_evidence_priority_packet_current.json",
    "scope-evidence-intake-readiness": "runs/product_scope_breadth_evidence_intake_readiness_current.json",
    "transporter-manual-review-intake": "runs/transporter_manual_review_intake_template_current.json",
    "pxr-exact-review-intake": "runs/pxr_exact_evidence_review_intake_template_current.json",
    "goal-completion-audit": "runs/product_goal_completion_audit_current.json",
}

CLAIM_BOUNDARY = (
    "Betelgeuze product CLI only; it reads local product readiness artifacts and prints status JSON. "
    "It does not run docking, write a license file, assemble bundles, submit CAMEO/CASP predictions, "
    "send email, delete data, upload, or mutate external state."
)

# Optional lanes tracked by the CLI but not required for restricted local product delivery readiness.
OPTIONAL_NON_BLOCKING_COMMANDS = frozenset(
    {
        "cameo-live-validation",
        "production-ai-gpu-return-intake",
        "production-ai-promotion-workbench",
        "goal-completion-audit",
    }
)


def _resolve(root: str | Path, path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else Path(root).resolve() / path


def _read_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    return [row for row in packet.get("rows", []) or [] if isinstance(row, dict)]


def _blockers(packet: dict[str, Any]) -> list[dict[str, Any]]:
    return [row for row in packet.get("blockers", []) or [] if isinstance(row, dict)]


def _approval_tokens_from_value(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(token).strip() for token in value if str(token).strip()]
    return [token.strip() for token in str(value or "").split(";") if token.strip()]


def _approval_tokens_from_status(payload: dict[str, Any]) -> set[str]:
    tokens: set[str] = set()
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    for key in ("approval_tokens_required", "approval_token_required"):
        tokens.update(_approval_tokens_from_value(summary.get(key)))
    for row in summary.get("rows", []) if isinstance(summary.get("rows"), list) else []:
        if isinstance(row, dict):
            tokens.update(_approval_tokens_from_value(row.get("approval_token_required")))
    return tokens


def _int_value(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _bool_value(value: Any) -> bool:
    return bool(value is True)


def build_cli_status(command: str, *, root: str | Path = ROOT) -> dict[str, Any]:
    artifact_rel = ARTIFACTS[command]
    artifact = _resolve(root, artifact_rel)
    packet = _read_json_object(artifact)
    summary = _summary(packet)
    if not summary:
        return {
            "packet_type": "product_cli_status",
            "command": command,
            "status": f"missing_{command.replace('-', '_')}_artifact",
            "artifact_path": artifact_rel,
            "artifact_present": artifact.exists(),
            "row_count": 0,
            "blocker_count": 1,
            "summary": {},
            "execution_enabled": False,
            "docking_results_emitted": False,
            "license_file_written": False,
            "bundle_assembled": False,
            "external_state_mutated": False,
            "claim_boundary": CLAIM_BOUNDARY,
        }
    return {
        "packet_type": "product_cli_status",
        "command": command,
        "status": str(summary.get("status") or "unknown"),
        "artifact_path": artifact_rel,
        "artifact_present": True,
        "row_count": len(_rows(packet)),
        "blocker_count": int(summary.get("blocker_count") or len(_blockers(packet))),
        "summary": summary,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "license_file_written": False,
        "bundle_assembled": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
    }


def _is_blocked_or_missing_status(status: str) -> bool:
    return str(status or "").startswith(("blocked_", "missing_"))


def build_all_status(*, root: str | Path = ROOT) -> dict[str, Any]:
    statuses = {command: build_cli_status(command, root=root) for command in ARTIFACTS}
    blocked_or_missing = [
        command
        for command, payload in statuses.items()
        if _is_blocked_or_missing_status(str(payload.get("status", "")))
    ]
    core_blocked_or_missing = [
        command for command in blocked_or_missing if command not in OPTIONAL_NON_BLOCKING_COMMANDS
    ]
    optional_blocked_or_missing = [
        command for command in blocked_or_missing if command in OPTIONAL_NON_BLOCKING_COMMANDS
    ]
    release_statuses = {
        command: payload
        for command, payload in statuses.items()
        if command not in OPTIONAL_NON_BLOCKING_COMMANDS
    }
    approval_tokens = sorted({token for payload in release_statuses.values() for token in _approval_tokens_from_status(payload)})
    cameo_live_summary = statuses.get("cameo-live-validation", {}).get("summary", {})
    if not isinstance(cameo_live_summary, dict):
        cameo_live_summary = {}
    cameo_live_approval_tokens = sorted(
        _approval_tokens_from_status(statuses.get("cameo-live-validation", {}))
    )
    operations_summary = statuses.get("operations", {}).get("summary", {})
    if not isinstance(operations_summary, dict):
        operations_summary = {}
    public_benchmark_summary = statuses.get("public-benchmark", {}).get("summary", {})
    if not isinstance(public_benchmark_summary, dict):
        public_benchmark_summary = {}
    goal_completion_summary = statuses.get("goal-completion-audit", {}).get("summary", {})
    if not isinstance(goal_completion_summary, dict):
        goal_completion_summary = {}
    core_ready = not core_blocked_or_missing
    return {
        "packet_type": "product_cli_status_set",
        "status": "product_cli_status_set_ready" if core_ready else "blocked_product_cli_status_set",
        "core_product_cli_status_set_ready": core_ready,
        "command_count": len(statuses),
        "blocked_or_missing_command_count": len(blocked_or_missing),
        "blocked_or_missing_commands": blocked_or_missing,
        "core_blocked_or_missing_command_count": len(core_blocked_or_missing),
        "core_blocked_or_missing_commands": core_blocked_or_missing,
        "optional_blocked_or_missing_command_count": len(optional_blocked_or_missing),
        "optional_blocked_or_missing_commands": optional_blocked_or_missing,
        "approval_token_count": len(approval_tokens),
        "approval_tokens_required": approval_tokens,
        "operations_stage_count": _int_value(operations_summary.get("stage_count")),
        "operations_blocked_stage_count": _int_value(operations_summary.get("blocked_stage_count")),
        "operations_approval_required_stage_count": _int_value(operations_summary.get("approval_required_stage_count")),
        "capability_surface_ready": _bool_value(operations_summary.get("capability_surface_ready")),
        "structure_analysis_capability_ready": _bool_value(operations_summary.get("structure_analysis_capability_ready")),
        "ligand_docking_capability_ready": _bool_value(operations_summary.get("ligand_docking_capability_ready")),
        "product_api_surface_ready": _bool_value(operations_summary.get("product_api_surface_ready")),
        "operational_quality_ready": _bool_value(operations_summary.get("operational_quality_ready")),
        "architecture_release_ready": _bool_value(operations_summary.get("architecture_release_ready")),
        "cameo_architecture_validation_ready": _bool_value(operations_summary.get("cameo_architecture_validation_ready")),
        "cleanup_postcheck_contract_ready": _bool_value(operations_summary.get("cleanup_postcheck_contract_ready")),
        "commercial_independence_ready": _bool_value(operations_summary.get("commercial_independence_ready")),
        "public_benchmark_work_order_status": statuses.get("public-benchmark", {}).get("status", ""),
        "public_benchmark_validation_ready": _bool_value(public_benchmark_summary.get("public_benchmark_validation_ready")),
        "public_benchmark_open_suite_count": _int_value(public_benchmark_summary.get("open_suite_count")),
        "public_benchmark_materialization_required_suite_count": _int_value(
            public_benchmark_summary.get("materialization_required_suite_count")
        ),
        "public_benchmark_scorecard_required_suite_count": _int_value(
            public_benchmark_summary.get("scorecard_required_suite_count")
        ),
        "public_benchmark_continuous_validation_command_count": _int_value(
            public_benchmark_summary.get("continuous_validation_command_count")
        ),
        "public_benchmark_suite_run_command_count": _int_value(public_benchmark_summary.get("suite_run_command_count")),
        "public_benchmark_suite_materialization_run_command_count": _int_value(
            public_benchmark_summary.get("suite_materialization_run_command_count")
        ),
        "public_benchmark_suite_scorecard_command_count": _int_value(
            public_benchmark_summary.get("suite_scorecard_command_count")
        ),
        "public_benchmark_suite_result_provenance_command_count": _int_value(
            public_benchmark_summary.get("suite_result_provenance_command_count")
        ),
        "public_benchmark_suite_result_provenance_present_count": _int_value(
            public_benchmark_summary.get("suite_result_provenance_present_count")
        ),
        "public_benchmark_suite_threshold_count": _int_value(public_benchmark_summary.get("suite_threshold_count")),
        "public_benchmark_suite_blocker_count": _int_value(public_benchmark_summary.get("suite_blocker_count")),
        "public_benchmark_suite_materialization_manifest_count": _int_value(
            public_benchmark_summary.get("suite_materialization_manifest_count")
        ),
        "public_benchmark_suite_scorecard_row_csv_count": _int_value(
            public_benchmark_summary.get("suite_scorecard_row_csv_count")
        ),
        "public_benchmark_suite_required_output_count": _int_value(
            public_benchmark_summary.get("suite_required_output_count")
        ),
        "public_benchmark_suite_no_external_dependency_count": _int_value(
            public_benchmark_summary.get("suite_no_external_dependency_count")
        ),
        "public_benchmark_local_artifact_preflight_ready_suite_count": _int_value(
            public_benchmark_summary.get("local_artifact_preflight_ready_suite_count")
        ),
        "public_benchmark_local_artifact_preflight_blocked_suite_count": _int_value(
            public_benchmark_summary.get("local_artifact_preflight_blocked_suite_count")
        ),
        "public_benchmark_missing_local_input_artifact_count": _int_value(
            public_benchmark_summary.get("missing_local_input_artifact_count")
        ),
        "public_benchmark_missing_local_output_artifact_count": _int_value(
            public_benchmark_summary.get("missing_local_output_artifact_count")
        ),
        "goal_completion_audit_status": statuses.get("goal-completion-audit", {}).get("status", ""),
        "goal_complete": _bool_value(goal_completion_summary.get("goal_complete")),
        "goal_completion_pass_count": _int_value(goal_completion_summary.get("pass_count")),
        "goal_completion_fail_count": _int_value(goal_completion_summary.get("fail_count")),
        "goal_completion_primary_bottleneck_phase": str(
            goal_completion_summary.get("primary_bottleneck_phase") or ""
        ),
        "goal_completion_next_command": str(goal_completion_summary.get("next_command") or ""),
        "goal_completion_next_command_candidate_count": _int_value(
            goal_completion_summary.get("next_command_candidate_count")
        ),
        "goal_completion_next_command_candidates": goal_completion_summary.get("next_command_candidates") or [],
        "cameo_live_validation_status": statuses.get("cameo-live-validation", {}).get("status", ""),
        "cameo_live_validation_ready": _bool_value(cameo_live_summary.get("validation_ready")),
        "cameo_live_official_results_intake_ready": _bool_value(
            cameo_live_summary.get("official_results_intake_ready")
        ),
        "cameo_live_official_result_required": _bool_value(cameo_live_summary.get("official_result_required")),
        "cameo_live_public_registration_allowed": _bool_value(cameo_live_summary.get("public_registration_allowed")),
        "cameo_live_approval_token_count": len(cameo_live_approval_tokens),
        "cameo_live_approval_tokens_required": cameo_live_approval_tokens,
        "license_present": _bool_value(operations_summary.get("license_present")),
        "license_authorized_for_file_creation_review": _bool_value(
            operations_summary.get("license_authorized_for_file_creation_review")
        ),
        "license_decision_packet_ready": _bool_value(operations_summary.get("license_decision_packet_ready")),
        "license_decision_option_count": _int_value(operations_summary.get("license_decision_option_count")),
        "license_file_creation_review_ready": _bool_value(operations_summary.get("license_file_creation_review_ready")),
        "authorized_for_execution": _bool_value(operations_summary.get("authorized_for_execution")),
        "bundle_assembled": _bool_value(operations_summary.get("bundle_assembled")),
        "bundle_validation_passed": _bool_value(operations_summary.get("bundle_validation_passed")),
        "delivery_ready_claim_allowed": _bool_value(operations_summary.get("delivery_ready_claim_allowed")),
        "pilot_delivery_ready": _bool_value(operations_summary.get("pilot_delivery_ready")),
        "restricted_delivery_complete": _bool_value(goal_completion_summary.get("restricted_delivery_complete")),
        "goal_complete": _bool_value(goal_completion_summary.get("goal_complete")),
        "product_ai_optional_lane_ready": _bool_value(goal_completion_summary.get("product_ai_optional_lane_ready")),
        "statuses": statuses,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "license_file_written": False,
        "bundle_assembled": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read local Betelgeuze product status artifacts as JSON.")
    parser.add_argument(
        "command",
        choices=[*ARTIFACTS.keys(), "all"],
        help="Product status surface to read.",
    )
    parser.add_argument("--root", default=str(ROOT), help="Repository root containing the runs/ artifacts.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_all_status(root=args.root) if args.command == "all" else build_cli_status(args.command, root=args.root)
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
