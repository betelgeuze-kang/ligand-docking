#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from betelgeuze_product.architecture import build_product_architecture_contract
from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PRODUCT_CAPABILITY_JSON = "runs/product_capability_surface_contract_current.json"
DEFAULT_PRODUCT_RELEASE_JSON = "runs/product_release_operations_dossier_current.json"
DEFAULT_COMMERCIAL_INDEPENDENCE_JSON = "runs/product_commercial_independence_gate_current.json"
DEFAULT_PRODUCT_SERVICE_BOUNDARY_JSON = "runs/product_service_boundary_contract_current.json"
DEFAULT_PRODUCT_API_CONTRACT_JSON = "runs/product_api_contract_current.json"
DEFAULT_PRODUCT_EXECUTION_PREFLIGHT_JSON = "runs/product_execution_preflight_current.json"
DEFAULT_PUBLIC_BENCHMARK_JSON = "runs/product_public_benchmark_contract_current.json"
DEFAULT_CAMEO_CAPABILITY_JSON = "runs/cameo_capability_preflight_current.json"
DEFAULT_CAMEO_ARCHITECTURE_VALIDATION_JSON = "runs/cameo_architecture_validation_contract_current.json"
DEFAULT_CLEANUP_OPERATIONS_JSON = "runs/cleanup_operations_surface_contract_current.json"
DEFAULT_CLEANUP_APPROVAL_JSON = "runs/cleanup_execution_approval_gate_current.json"
DEFAULT_CLEANUP_POSTCHECK_JSON = "runs/cleanup_postcheck_contract_current.json"
DEFAULT_CLEANUP_COMPLETION_JSON = "runs/cleanup_completion_gate_current.json"
DEFAULT_LIGAND_CLEANUP_WORK_ORDER_JSON = "runs/ligand_heavy_cleanup_work_order_current.json"
DEFAULT_LIGAND_CLEANUP_PREFLIGHT_JSON = "runs/ligand_heavy_cleanup_execution_preflight_current.json"
DEFAULT_CASP17_TRANSITION_JSON = "casp17/casp17_transition_surface_contract_current.json"
DEFAULT_OUT_JSON = "runs/product_architecture_contract_current.json"
DEFAULT_OUT_CSV = "runs/product_architecture_contract_current.csv"
DEFAULT_OUT_MD = "runs/product_architecture_contract_current.md"


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_json_if_present(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Product Architecture Contract",
        "",
        f"- status: `{s['status']}`",
        f"- local_architecture_surface_ready: `{s['local_architecture_surface_ready']}`",
        f"- architecture_release_ready: `{s['architecture_release_ready']}`",
        f"- release_claim_allowed: `{s['release_claim_allowed']}`",
        f"- product_execution_authorized: `{s['product_execution_authorized']}`",
        f"- delivery_ready_claim_allowed: `{s['delivery_ready_claim_allowed']}`",
        f"- lane_count: `{s['lane_count']}`",
        f"- ready_lane_count: `{s['ready_lane_count']}`",
        f"- blocked_lane_count: `{s['blocked_lane_count']}`",
        f"- approval_required_lane_count: `{s['approval_required_lane_count']}`",
        f"- canonical_architecture_lanes_required: `{';'.join(s['canonical_architecture_lanes_required'])}`",
        f"- canonical_architecture_required_lanes_present: `{s['canonical_architecture_required_lanes_present']}`",
        f"- canonical_architecture_ready_lane_count: `{s['canonical_architecture_ready_lane_count']}`",
        f"- canonical_architecture_blocked_lane_count: `{s['canonical_architecture_blocked_lane_count']}`",
        f"- canonical_architecture_blocked_lanes: `{';'.join(s['canonical_architecture_blocked_lanes'])}`",
        f"- structure_analysis_product_surface_ready: `{s['structure_analysis_product_surface_ready']}`",
        f"- ligand_docking_execution_contract_ready: `{s['ligand_docking_execution_contract_ready']}`",
        f"- scoring_ranking_contract_ready: `{s['scoring_ranking_contract_ready']}`",
        f"- scoring_ranking_eval_unique_keys: `{s['scoring_ranking_eval_unique_keys']}`",
        f"- scoring_ranking_gate_min_eval_unique_keys: `{s['scoring_ranking_gate_min_eval_unique_keys']}`",
        f"- scoring_ranking_gate_ef1_min: `{s['scoring_ranking_gate_ef1_min']}`",
        f"- local_delivery_bundle_validation_ready: `{s['local_delivery_bundle_validation_ready']}`",
        f"- result_bundle_generation_contract_ready: `{s['result_bundle_generation_contract_ready']}`",
        f"- result_bundle_expected_dir: `{s['result_bundle_expected_dir']}`",
        f"- result_bundle_artifact_count: `{s['result_bundle_artifact_count']}`",
        f"- result_bundle_planned_artifact_paths: `{';'.join(s['result_bundle_planned_artifact_paths'])}`",
        f"- result_bundle_validation_command_matches: `{s['result_bundle_validation_command_matches']}`",
        f"- result_bundle_rerun_command_present: `{s['result_bundle_rerun_command_present']}`",
        f"- local_delivery_bundle_assembled: `{s['local_delivery_bundle_assembled']}`",
        f"- local_delivery_bundle_validation_passed: `{s['local_delivery_bundle_validation_passed']}`",
        f"- local_delivery_pilot_delivery_ready: `{s['local_delivery_pilot_delivery_ready']}`",
        f"- product_service_boundary_ready: `{s['product_service_boundary_ready']}`",
        f"- product_api_contract_ready: `{s['product_api_contract_ready']}`",
        f"- public_benchmark_validation_ready: `{s['public_benchmark_validation_ready']}`",
        f"- public_benchmark_status: `{s['public_benchmark_status']}`",
        f"- public_benchmark_required_suite_count: `{s['public_benchmark_required_suite_count']}`",
        f"- public_benchmark_ready_required_suite_count: `{s['public_benchmark_ready_required_suite_count']}`",
        f"- public_benchmark_blocked_suite_count: `{s['public_benchmark_blocked_suite_count']}`",
        f"- public_benchmark_requires_24h_server: `{s['public_benchmark_requires_24h_server']}`",
        f"- public_benchmark_requires_competition_season: `{s['public_benchmark_requires_competition_season']}`",
        f"- public_benchmark_requires_paid_vps: `{s['public_benchmark_requires_paid_vps']}`",
        f"- commercial_independence_ready: `{s['commercial_independence_ready']}`",
        f"- commercial_dependency_provenance_manifest_present: `{s['commercial_dependency_provenance_manifest_present']}`",
        f"- commercial_requirements_lock_artifacts_present: `{s['commercial_requirements_lock_artifacts_present']}`",
        f"- commercial_reproducible_install_manifest_ready: `{s['commercial_reproducible_install_manifest_ready']}`",
        f"- commercial_dependency_provenance_git_short_commit: `{s['commercial_dependency_provenance_git_short_commit']}`",
        f"- commercial_dependency_provenance_requirements_lock_txt_sha256: `{s['commercial_dependency_provenance_requirements_lock_txt_sha256']}`",
        f"- cameo_local_surface_ready: `{s['cameo_local_surface_ready']}`",
        f"- cameo_service_boundary_ready: `{s['cameo_service_boundary_ready']}`",
        f"- cameo_service_boundary_status: `{s['cameo_service_boundary_status']}`",
        f"- cameo_api_contract_ready: `{s['cameo_api_contract_ready']}`",
        f"- cameo_api_contract_status: `{s['cameo_api_contract_status']}`",
        f"- cameo_architecture_validation_protocol_ready: `{s['cameo_architecture_validation_protocol_ready']}`",
        f"- cameo_architecture_validation_ready: `{s['cameo_architecture_validation_ready']}`",
        f"- cameo_official_validation_evidence_ready: `{s['cameo_official_validation_evidence_ready']}`",
        f"- cameo_official_results_status: `{s['cameo_official_results_status']}`",
        f"- cameo_accepted_official_result_count: `{s['cameo_accepted_official_result_count']}`",
        f"- cameo_model1_official_result_ready: `{s['cameo_model1_official_result_ready']}`",
        f"- cameo_operator_intake_csv: `{s['cameo_operator_intake_csv']}`",
        f"- cameo_public_registration_status: `{s['cameo_public_registration_status']}`",
        f"- cameo_public_registration_authorized: `{s['cameo_public_registration_authorized']}`",
        f"- cameo_receiver_smoke_ready: `{s['cameo_receiver_smoke_ready']}`",
        f"- cameo_receiver_smoke_status: `{s['cameo_receiver_smoke_status']}`",
        f"- cameo_api_dependency_ready: `{s['cameo_api_dependency_ready']}`",
        f"- cameo_api_dependency_status: `{s['cameo_api_dependency_status']}`",
        f"- cameo_public_registration_allowed: `{s['cameo_public_registration_allowed']}`",
        f"- cameo_public_registration_blocker_count: `{s['cameo_public_registration_blocker_count']}`",
        f"- cameo_registration_approval_token_count: `{s['cameo_registration_approval_token_count']}`",
        f"- cameo_registration_approval_tokens_required: `{';'.join(s['cameo_registration_approval_tokens_required'])}`",
        f"- cleanup_control_surface_ready: `{s['cleanup_control_surface_ready']}`",
        f"- cleanup_postcheck_contract_ready: `{s['cleanup_postcheck_contract_ready']}`",
        f"- cleanup_postcheck_row_count: `{s['cleanup_postcheck_row_count']}`",
        f"- cleanup_postcheck_blocked_row_count: `{s['cleanup_postcheck_blocked_row_count']}`",
        f"- cleanup_postcheck_global_refresh_command_count: `{s['cleanup_postcheck_global_refresh_command_count']}`",
        f"- cleanup_completion_ready: `{s['cleanup_completion_ready']}`",
        f"- ligand_heavy_cleanup_preflight_ready: `{s['ligand_heavy_cleanup_preflight_ready']}`",
        f"- casp17_transition_surface_ready: `{s['casp17_transition_surface_ready']}`",
        f"- cleanup_execution_approved: `{s['cleanup_execution_approved']}`",
        f"- cleanup_reclaim_size_gb: `{s['cleanup_reclaim_size_gb']}`",
        f"- release_allowed: `{s['release_allowed']}`",
        f"- execution_enabled: `{s['execution_enabled']}`",
        f"- docking_results_emitted: `{s['docking_results_emitted']}`",
        f"- cameo_submission_executed: `{s['cameo_submission_executed']}`",
        f"- casp_submission_executed: `{s['casp_submission_executed']}`",
        f"- cleanup_executed: `{s['cleanup_executed']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Lanes",
        "",
        "| lane | canonical | domain | status | observed | required | approval token | artifact | reason |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['lane_id']}` | `{row['canonical_lane']}` | `{row['domain']}` | `{row['status']}` | "
            f"`{row['observed']}` | `{row['required']}` | `{row['approval_token_required']}` | "
            f"`{row['artifact_path']}` | {row['reason']} |"
        )
    lines.extend(["", "## Blockers", ""])
    if payload["blockers"]:
        lines.extend(f"- `{blocker['code']}`: {blocker['reason']}" for blocker in payload["blockers"])
    else:
        lines.append("- none")
    lines.extend(["", "## Approval Required", ""])
    if payload["approval_required"]:
        lines.extend(
            f"- `{row['lane_id']}`: {row['reason']} Required token: `{row['approval_token_required']}`"
            for row in payload["approval_required"]
        )
    else:
        lines.append("- none")
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a product architecture contract from local evidence artifacts.")
    parser.add_argument("--product-capability-json", default=DEFAULT_PRODUCT_CAPABILITY_JSON)
    parser.add_argument("--product-release-json", default=DEFAULT_PRODUCT_RELEASE_JSON)
    parser.add_argument("--commercial-independence-json", default=DEFAULT_COMMERCIAL_INDEPENDENCE_JSON)
    parser.add_argument("--product-service-boundary-json", default=DEFAULT_PRODUCT_SERVICE_BOUNDARY_JSON)
    parser.add_argument("--product-api-contract-json", default=DEFAULT_PRODUCT_API_CONTRACT_JSON)
    parser.add_argument("--product-execution-preflight-json", default=DEFAULT_PRODUCT_EXECUTION_PREFLIGHT_JSON)
    parser.add_argument("--public-benchmark-json", default=DEFAULT_PUBLIC_BENCHMARK_JSON)
    parser.add_argument("--cameo-capability-json", default=DEFAULT_CAMEO_CAPABILITY_JSON)
    parser.add_argument("--cameo-architecture-validation-json", default=DEFAULT_CAMEO_ARCHITECTURE_VALIDATION_JSON)
    parser.add_argument("--cleanup-operations-json", default=DEFAULT_CLEANUP_OPERATIONS_JSON)
    parser.add_argument("--cleanup-approval-json", default=DEFAULT_CLEANUP_APPROVAL_JSON)
    parser.add_argument("--cleanup-postcheck-json", default=DEFAULT_CLEANUP_POSTCHECK_JSON)
    parser.add_argument("--cleanup-completion-json", default=DEFAULT_CLEANUP_COMPLETION_JSON)
    parser.add_argument("--ligand-cleanup-work-order-json", default=DEFAULT_LIGAND_CLEANUP_WORK_ORDER_JSON)
    parser.add_argument("--ligand-cleanup-preflight-json", default=DEFAULT_LIGAND_CLEANUP_PREFLIGHT_JSON)
    parser.add_argument("--casp17-transition-json", default=DEFAULT_CASP17_TRANSITION_JSON)
    parser.add_argument("--root", default=".")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_product_architecture_contract(
        product_capability_packet=_read_json_if_present(args.product_capability_json),
        product_release_packet=_read_json_if_present(args.product_release_json),
        commercial_independence_packet=_read_json_if_present(args.commercial_independence_json),
        product_service_boundary_packet=_read_json_if_present(args.product_service_boundary_json),
        product_api_contract_packet=_read_json_if_present(args.product_api_contract_json),
        product_execution_preflight_packet=_read_json_if_present(args.product_execution_preflight_json),
        public_benchmark_packet=_read_json_if_present(args.public_benchmark_json),
        cameo_capability_packet=_read_json_if_present(args.cameo_capability_json),
        cameo_architecture_validation_packet=_read_json_if_present(args.cameo_architecture_validation_json),
        cleanup_operations_packet=_read_json_if_present(args.cleanup_operations_json),
        cleanup_approval_packet=_read_json_if_present(args.cleanup_approval_json),
        cleanup_postcheck_packet=_read_json_if_present(args.cleanup_postcheck_json),
        cleanup_completion_packet=_read_json_if_present(args.cleanup_completion_json),
        ligand_cleanup_work_order_packet=_read_json_if_present(args.ligand_cleanup_work_order_json),
        ligand_cleanup_preflight_packet=_read_json_if_present(args.ligand_cleanup_preflight_json),
        casp17_transition_packet=_read_json_if_present(args.casp17_transition_json),
        root=args.root,
        product_capability_path=args.product_capability_json,
        product_release_path=args.product_release_json,
        commercial_independence_path=args.commercial_independence_json,
        product_service_boundary_path=args.product_service_boundary_json,
        product_api_contract_path=args.product_api_contract_json,
        product_execution_preflight_path=args.product_execution_preflight_json,
        public_benchmark_path=args.public_benchmark_json,
        cameo_capability_path=args.cameo_capability_json,
        cameo_architecture_validation_path=args.cameo_architecture_validation_json,
        cleanup_operations_path=args.cleanup_operations_json,
        cleanup_approval_path=args.cleanup_approval_json,
        cleanup_postcheck_path=args.cleanup_postcheck_json,
        cleanup_completion_path=args.cleanup_completion_json,
        ligand_cleanup_work_order_path=args.ligand_cleanup_work_order_json,
        ligand_cleanup_preflight_path=args.ligand_cleanup_preflight_json,
        casp17_transition_path=args.casp17_transition_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
