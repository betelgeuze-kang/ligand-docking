#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from betelgeuze_product.commercial_independence import build_product_commercial_independence_gate
from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/product_commercial_independence_gate_current.json"
DEFAULT_OUT_CSV = "runs/product_commercial_independence_gate_current.csv"
DEFAULT_OUT_MD = "runs/product_commercial_independence_gate_current.md"


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Product Commercial Independence Gate",
        "",
        f"- status: `{s['status']}`",
        f"- commercial_independent_product_claim_allowed: `{s['commercial_independent_product_claim_allowed']}`",
        f"- blocker_count: `{s['blocker_count']}`",
        f"- check_count: `{s['check_count']}`",
        f"- license_present: `{s['license_present']}`",
        f"- license_approval_token_required: `{s['license_approval_token_required']}`",
        f"- license_operator_required_input: `{s['license_operator_required_input']}`",
        f"- license_required_output: `{s['license_required_output']}`",
        f"- license_generation_command_template: `{s['license_generation_command_template']}`",
        f"- license_creation_executed: `{s['license_creation_executed']}`",
        f"- runtime_requirements_present: `{s['runtime_requirements_present']}`",
        f"- loose_runtime_dependency_count: `{s['loose_runtime_dependency_count']}`",
        f"- dependency_provenance_manifest_present: `{s['dependency_provenance_manifest_present']}`",
        f"- dependency_provenance_git_short_commit: `{s['dependency_provenance_git_short_commit']}`",
        f"- dependency_provenance_requirements_lock_txt_sha256: `{s['dependency_provenance_requirements_lock_txt_sha256']}`",
        f"- requirements_lock_artifacts_present: `{s['requirements_lock_artifacts_present']}`",
        f"- requirements_lock_complete: `{s['requirements_lock_complete']}`",
        f"- reproducible_install_manifest_ready: `{s['reproducible_install_manifest_ready']}`",
        f"- external_api_runtime_dependency_count: `{s['external_api_runtime_dependency_count']}`",
        f"- external_saas_runtime_dependency_count: `{s['external_saas_runtime_dependency_count']}`",
        f"- optional_profiles_separated: `{s['optional_profiles_separated']}`",
        f"- deployment_manifest_present: `{s['deployment_manifest_present']}`",
        f"- pyproject_packaging_metadata_present: `{s['pyproject_packaging_metadata_present']}`",
        f"- package_discovery_present: `{s['package_discovery_present']}`",
        f"- console_entrypoint_targets_present: `{s['console_entrypoint_targets_present']}`",
        f"- core_product_surface_present: `{s['core_product_surface_present']}`",
        f"- product_cli_surface_present: `{s['product_cli_surface_present']}`",
        f"- product_service_boundary_ready: `{s['product_service_boundary_ready']}`",
        f"- product_service_boundary_api_route_count: `{s['product_service_boundary_api_route_count']}`",
        f"- product_service_boundary_cli_command_count: `{s['product_service_boundary_cli_command_count']}`",
        f"- product_api_contract_ready: `{s['product_api_contract_ready']}`",
        f"- product_api_contract_missing_route_count: `{s['product_api_contract_missing_route_count']}`",
        f"- restricted_commercial_scope_claim_ready: `{s['restricted_commercial_scope_claim_ready']}`",
        f"- commercial_claim_scope_tier: `{s['commercial_claim_scope_tier']}`",
        f"- commercial_claim_scope_detail: `{s['commercial_claim_scope_detail']}`",
        f"- allowed_scope_families: `{','.join(s['allowed_scope_families'])}`",
        f"- blocked_claim_scopes: `{','.join(s['blocked_claim_scopes'])}`",
        f"- general_platform_claim_allowed: `{s['general_platform_claim_allowed']}`",
        f"- local_self_hosted_operation_ready: `{s['local_self_hosted_operation_ready']}`",
        f"- local_self_hosted_core_product_surface_present: `{s['local_self_hosted_core_product_surface_present']}`",
        f"- local_self_hosted_external_saas_free_runtime: `{s['local_self_hosted_external_saas_free_runtime']}`",
        f"- local_self_hosted_api_cli_ready: `{s['local_self_hosted_api_cli_ready']}`",
        f"- local_delivery_bundle_ready: `{s['local_delivery_bundle_ready']}`",
        f"- local_delivery_bundle_assembled: `{s['local_delivery_bundle_assembled']}`",
        f"- local_delivery_bundle_validation_passed: `{s['local_delivery_bundle_validation_passed']}`",
        f"- local_delivery_pilot_delivery_ready: `{s['local_delivery_pilot_delivery_ready']}`",
        f"- public_benchmark_evidence_ready: `{s['public_benchmark_evidence_ready']}`",
        f"- public_benchmark_status: `{s['public_benchmark_status']}`",
        f"- public_benchmark_ready_required_suite_count: `{s['public_benchmark_ready_required_suite_count']}`",
        f"- public_benchmark_required_suite_count: `{s['public_benchmark_required_suite_count']}`",
        f"- public_benchmark_blocked_suite_count: `{s['public_benchmark_blocked_suite_count']}`",
        f"- public_benchmark_suite_coverage_ready: `{s['public_benchmark_suite_coverage_ready']}`",
        f"- public_benchmark_suite_materialization_manifest_count: `{s['public_benchmark_suite_materialization_manifest_count']}`",
        f"- public_benchmark_suite_scorecard_row_csv_count: `{s['public_benchmark_suite_scorecard_row_csv_count']}`",
        f"- public_benchmark_suite_threshold_count: `{s['public_benchmark_suite_threshold_count']}`",
        f"- public_benchmark_suite_blocker_count: `{s['public_benchmark_suite_blocker_count']}`",
        f"- public_benchmark_suite_run_command_count: `{s['public_benchmark_suite_run_command_count']}`",
        f"- public_benchmark_suite_materialization_run_command_count: `{s['public_benchmark_suite_materialization_run_command_count']}`",
        f"- public_benchmark_suite_no_external_dependency_count: `{s['public_benchmark_suite_no_external_dependency_count']}`",
        f"- public_benchmark_work_order_status: `{s['public_benchmark_work_order_status']}`",
        f"- public_benchmark_work_order_local_artifact_preflight_ready: `{s['public_benchmark_work_order_local_artifact_preflight_ready']}`",
        f"- public_benchmark_work_order_local_artifact_preflight_ready_suite_count: `{s['public_benchmark_work_order_local_artifact_preflight_ready_suite_count']}`",
        f"- public_benchmark_work_order_local_artifact_preflight_blocked_suite_count: `{s['public_benchmark_work_order_local_artifact_preflight_blocked_suite_count']}`",
        f"- public_benchmark_work_order_missing_local_input_artifact_count: `{s['public_benchmark_work_order_missing_local_input_artifact_count']}`",
        f"- public_benchmark_work_order_missing_local_output_artifact_count: `{s['public_benchmark_work_order_missing_local_output_artifact_count']}`",
        f"- execution_enabled: `{s['execution_enabled']}`",
        f"- docking_results_emitted: `{s['docking_results_emitted']}`",
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
    blockers = payload.get("blockers") or []
    if blockers:
        lines.extend(f"- `{blocker['code']}`: {blocker['reason']}" for blocker in blockers)
    else:
        lines.append("- none")
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a commercial independent-product packaging gate without installing packages.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--environment-manifest-json", default="runs/local_delivery_environment_manifest_current.json")
    parser.add_argument("--requirements-lock-json", default="runs/local_delivery_requirements_lock_current.json")
    parser.add_argument("--requirements-lock-md", default="runs/local_delivery_requirements_lock_current.md")
    parser.add_argument("--requirements-lock-txt", default="runs/local_delivery_requirements_lock_current.txt")
    parser.add_argument("--product-service-boundary-json", default="runs/product_service_boundary_contract_current.json")
    parser.add_argument("--product-api-contract-json", default="runs/product_api_contract_current.json")
    parser.add_argument("--product-capability-json", default="runs/product_capability_surface_contract_current.json")
    parser.add_argument("--product-bundle-json", default="runs/product_bundle_contract_current.json")
    parser.add_argument("--product-delivery-evidence-json", default="runs/product_delivery_evidence_contract_current.json")
    parser.add_argument("--product-pilot-json", default="runs/product_pilot_packet_contract_current.json")
    parser.add_argument("--public-benchmark-json", default="runs/product_public_benchmark_contract_current.json")
    parser.add_argument("--public-benchmark-work-order-json", default="runs/product_public_benchmark_work_order_current.json")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    if not _resolve("runs/product_capability_surface_contract_current.json").exists():
        from tools.product.bootstrap_api_worker_contract_artifacts import materialize

        materialize()
    payload = build_product_commercial_independence_gate(
        root=args.root,
        environment_manifest_json=args.environment_manifest_json,
        requirements_lock_json=args.requirements_lock_json,
        requirements_lock_md=args.requirements_lock_md,
        requirements_lock_txt=args.requirements_lock_txt,
        product_service_boundary_json=args.product_service_boundary_json,
        product_api_contract_json=args.product_api_contract_json,
        product_capability_json=args.product_capability_json,
        product_bundle_json=args.product_bundle_json,
        product_delivery_evidence_json=args.product_delivery_evidence_json,
        product_pilot_json=args.product_pilot_json,
        public_benchmark_json=args.public_benchmark_json,
        public_benchmark_work_order_json=args.public_benchmark_work_order_json,
    )
    _write_json(args.out_json, payload)
    from tools.product.ci_contract_fixture_packets import write_license_decision_packets

    write_license_decision_packets(_resolve("runs"))
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
