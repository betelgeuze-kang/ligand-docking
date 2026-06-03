#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from betelgeuze_cameo.architecture_validation import build_cameo_architecture_validation_contract
from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PRODUCT_ARCHITECTURE_JSON = "runs/product_architecture_contract_current.json"
DEFAULT_VALIDATION_OPERATIONS_JSON = "runs/cameo_validation_operations_dossier_current.json"
DEFAULT_VALIDATION_READINESS_JSON = "runs/cameo_validation_readiness_gate_current.json"
DEFAULT_PERFORMANCE_THRESHOLD_POLICY_JSON = "runs/cameo_performance_threshold_policy_current.json"
DEFAULT_PERFORMANCE_SCORECARD_JSON = "runs/cameo_performance_scorecard_current.json"
DEFAULT_OFFICIAL_RESULTS_JSON = "runs/cameo_official_results_intake_gate_current.json"
DEFAULT_PUBLIC_REGISTRATION_JSON = "runs/cameo_public_registration_approval_gate_current.json"
DEFAULT_SERVICE_BOUNDARY_JSON = "runs/cameo_service_boundary_contract_current.json"
DEFAULT_API_CONTRACT_JSON = "runs/cameo_api_contract_current.json"
DEFAULT_OUT_JSON = "runs/cameo_architecture_validation_contract_current.json"
DEFAULT_OUT_CSV = "runs/cameo_architecture_validation_contract_current.csv"
DEFAULT_OUT_MD = "runs/cameo_architecture_validation_contract_current.md"


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
        "# CAMEO Architecture Validation Contract",
        "",
        f"- status: `{s['status']}`",
        f"- local_validation_protocol_ready: `{s['local_validation_protocol_ready']}`",
        f"- cameo_architecture_validation_ready: `{s['cameo_architecture_validation_ready']}`",
        f"- lane_count: `{s['lane_count']}`",
        f"- ready_lane_count: `{s['ready_lane_count']}`",
        f"- blocked_lane_count: `{s['blocked_lane_count']}`",
        f"- approval_required_lane_count: `{s['approval_required_lane_count']}`",
        f"- product_architecture_local_surface_ready: `{s['product_architecture_local_surface_ready']}`",
        f"- product_architecture_full_local_surface_ready: `{s['product_architecture_full_local_surface_ready']}`",
        f"- product_architecture_component_surface_ready: `{s['product_architecture_component_surface_ready']}`",
        f"- cameo_service_boundary_ready: `{s['cameo_service_boundary_ready']}`",
        f"- cameo_service_boundary_status: `{s['cameo_service_boundary_status']}`",
        f"- cameo_api_contract_ready: `{s['cameo_api_contract_ready']}`",
        f"- cameo_api_contract_status: `{s['cameo_api_contract_status']}`",
        f"- validation_operations_surface_ready: `{s['validation_operations_surface_ready']}`",
        f"- validation_evidence_ready: `{s['validation_evidence_ready']}`",
        f"- performance_threshold_policy_ready: `{s['performance_threshold_policy_ready']}`",
        f"- performance_threshold_profile_name: `{s['performance_threshold_profile_name']}`",
        f"- performance_scorecard_evidence_ready: `{s['performance_scorecard_evidence_ready']}`",
        f"- performance_scorecard_status: `{s['performance_scorecard_status']}`",
        f"- performance_model1_official_result_count: `{s['performance_model1_official_result_count']}`",
        f"- official_results_ready: `{s['official_results_ready']}`",
        f"- official_results_status: `{s['official_results_status']}`",
        f"- accepted_official_result_count: `{s['accepted_official_result_count']}`",
        f"- model1_official_result_ready: `{s['model1_official_result_ready']}`",
        f"- operator_intake_csv: `{s['operator_intake_csv']}`",
        f"- operator_template_csv: `{s['operator_template_csv']}`",
        f"- public_registration_authorized: `{s['public_registration_authorized']}`",
        f"- public_registration_status: `{s['public_registration_status']}`",
        f"- public_registration_prepared: `{s['public_registration_prepared']}`",
        f"- public_registration_blocker_count: `{s['public_registration_blocker_count']}`",
        f"- official_cameo_results_used: `{s['official_cameo_results_used']}`",
        f"- live_external_validation_channel: `{s['live_external_validation_channel']}`",
        f"- cameo_live_validation_required_for_product_release: `{s['cameo_live_validation_required_for_product_release']}`",
        f"- cameo_live_validation_evidence_ready: `{s['cameo_live_validation_evidence_ready']}`",
        f"- official_results_required_for_product_release: `{s['official_results_required_for_product_release']}`",
        f"- official_results_intake_artifact: `{s['official_results_intake_artifact']}`",
        f"- registration_required_for_product_release: `{s['registration_required_for_product_release']}`",
        f"- registration_evidence_artifact: `{s['registration_evidence_artifact']}`",
        f"- receiver_api_readiness_ready: `{s['receiver_api_readiness_ready']}`",
        f"- development_blocked_by_cameo_registration: `{s['development_blocked_by_cameo_registration']}`",
        f"- server_registration_mutated: `{s['server_registration_mutated']}`",
        f"- prediction_generation_enabled: `{s['prediction_generation_enabled']}`",
        f"- outbound_email_enabled: `{s['outbound_email_enabled']}`",
        f"- native_local_accuracy_used: `{s['native_local_accuracy_used']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Lanes",
        "",
        "| lane | status | live | product_release_blocker | observed | required | approval token | artifact | reason |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['lane_id']}` | `{row['status']}` | `{row['live_external_validation_channel']}` | "
            f"`{row['product_release_blocker']}` | `{row['observed']}` | `{row['required']}` | "
            f"`{row['approval_token_required']}` | `{row['artifact_path']}` | {row['reason']} |"
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
    parser = argparse.ArgumentParser(description="Build a CAMEO architecture validation contract from local evidence artifacts.")
    parser.add_argument("--product-architecture-json", default=DEFAULT_PRODUCT_ARCHITECTURE_JSON)
    parser.add_argument("--validation-operations-json", default=DEFAULT_VALIDATION_OPERATIONS_JSON)
    parser.add_argument("--validation-readiness-json", default=DEFAULT_VALIDATION_READINESS_JSON)
    parser.add_argument("--performance-threshold-policy-json", default=DEFAULT_PERFORMANCE_THRESHOLD_POLICY_JSON)
    parser.add_argument("--performance-scorecard-json", default=DEFAULT_PERFORMANCE_SCORECARD_JSON)
    parser.add_argument("--official-results-json", default=DEFAULT_OFFICIAL_RESULTS_JSON)
    parser.add_argument("--public-registration-json", default=DEFAULT_PUBLIC_REGISTRATION_JSON)
    parser.add_argument("--service-boundary-json", default=DEFAULT_SERVICE_BOUNDARY_JSON)
    parser.add_argument("--api-contract-json", default=DEFAULT_API_CONTRACT_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_cameo_architecture_validation_contract(
        product_architecture_packet=_read_json_if_present(args.product_architecture_json),
        validation_operations_packet=_read_json_if_present(args.validation_operations_json),
        validation_readiness_packet=_read_json_if_present(args.validation_readiness_json),
        performance_threshold_policy_packet=_read_json_if_present(args.performance_threshold_policy_json),
        performance_scorecard_packet=_read_json_if_present(args.performance_scorecard_json),
        official_results_packet=_read_json_if_present(args.official_results_json),
        public_registration_packet=_read_json_if_present(args.public_registration_json),
        service_boundary_packet=_read_json_if_present(args.service_boundary_json),
        api_contract_packet=_read_json_if_present(args.api_contract_json),
        product_architecture_path=args.product_architecture_json,
        validation_operations_path=args.validation_operations_json,
        validation_readiness_path=args.validation_readiness_json,
        performance_threshold_policy_path=args.performance_threshold_policy_json,
        performance_scorecard_path=args.performance_scorecard_json,
        official_results_path=args.official_results_json,
        public_registration_path=args.public_registration_json,
        service_boundary_path=args.service_boundary_json,
        api_contract_path=args.api_contract_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
