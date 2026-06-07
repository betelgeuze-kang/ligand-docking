#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from betelgeuze_product.capability_surface import build_product_capability_surface_contract
from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_READINESS_JSON = "runs/product_readiness_gate_current.json"
DEFAULT_WORK_ORDER_JSON = "runs/product_execution_work_order_current.json"
DEFAULT_PREFLIGHT_JSON = "runs/product_execution_preflight_current.json"
DEFAULT_STRUCTURE_REPORT_JSON = "runs/product_structure_analysis_report_current.json"
DEFAULT_BUNDLE_CONTRACT_JSON = "runs/product_bundle_contract_current.json"
DEFAULT_DELIVERY_EVIDENCE_JSON = "runs/product_delivery_evidence_contract_current.json"
DEFAULT_PILOT_PACKET_JSON = "runs/product_pilot_packet_contract_current.json"
DEFAULT_SCOPE_BREADTH_JSON = "runs/product_scope_breadth_contract_current.json"
DEFAULT_OUT_JSON = "runs/product_capability_surface_contract_current.json"
DEFAULT_OUT_CSV = "runs/product_capability_surface_contract_current.csv"
DEFAULT_OUT_MD = "runs/product_capability_surface_contract_current.md"


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
        "# Product Capability Surface Contract",
        "",
        f"- status: `{s['status']}`",
        f"- target_id: `{s['target_id']}`",
        f"- family: `{s['family']}`",
        f"- ligand_count: `{s['ligand_count']}`",
        f"- capability_count: `{s['capability_count']}`",
        f"- ready_capability_count: `{s['ready_capability_count']}`",
        f"- blocked_capability_count: `{s['blocked_capability_count']}`",
        f"- structure_analysis_capability_ready: `{s['structure_analysis_capability_ready']}`",
        f"- ligand_docking_capability_ready: `{s['ligand_docking_capability_ready']}`",
        f"- local_delivery_bundle_capability_ready: `{s['local_delivery_bundle_capability_ready']}`",
        f"- result_bundle_generation_contract_ready: `{s['result_bundle_generation_contract_ready']}`",
        f"- result_bundle_expected_dir: `{s['result_bundle_expected_dir']}`",
        f"- result_bundle_artifact_count: `{s['result_bundle_artifact_count']}`",
        f"- result_bundle_planned_artifact_paths: `{';'.join(s['result_bundle_planned_artifact_paths'])}`",
        f"- result_bundle_validation_command_matches: `{s['result_bundle_validation_command_matches']}`",
        f"- result_bundle_rerun_command_present: `{s['result_bundle_rerun_command_present']}`",
        f"- api_surface_ready: `{s['api_surface_ready']}`",
        f"- product_structure_analysis_endpoint_present: `{s['product_structure_analysis_endpoint_present']}`",
        f"- product_structure_analysis_report_ready: `{s['product_structure_analysis_report_ready']}`",
        f"- product_structure_analysis_atom_count: `{s['product_structure_analysis_atom_count']}`",
        f"- product_structure_analysis_ligand_like_residue_count: `{s['product_structure_analysis_ligand_like_residue_count']}`",
        f"- product_capability_endpoint_present: `{s['product_capability_endpoint_present']}`",
        f"- product_architecture_endpoint_present: `{s['product_architecture_endpoint_present']}`",
        f"- product_service_boundary_endpoint_present: `{s['product_service_boundary_endpoint_present']}`",
        f"- product_api_contract_endpoint_present: `{s['product_api_contract_endpoint_present']}`",
        f"- product_operations_endpoint_present: `{s['product_operations_endpoint_present']}`",
        f"- product_license_decision_endpoint_present: `{s['product_license_decision_endpoint_present']}`",
        f"- product_commercial_independence_endpoint_present: `{s['product_commercial_independence_endpoint_present']}`",
        f"- product_release_readiness_endpoint_present: `{s['product_release_readiness_endpoint_present']}`",
        f"- product_cli_surface_present: `{s['product_cli_surface_present']}`",
        f"- guarded_claims_ready: `{s['guarded_claims_ready']}`",
        f"- restricted_scope_claim_guard_ready: `{s['restricted_scope_claim_guard_ready']}`",
        f"- allowed_scope_families: `{','.join(s['allowed_scope_families'])}`",
        f"- blocked_claim_scopes: `{','.join(s['blocked_claim_scopes'])}`",
        f"- general_platform_claim_allowed: `{s['general_platform_claim_allowed']}`",
        f"- scope_claim_boundary_detail: `{s['scope_claim_boundary_detail']}`",
        f"- delivery_claim_backed_by_bundle_validation: `{s['delivery_claim_backed_by_bundle_validation']}`",
        f"- execution_enabled: `{s['execution_enabled']}`",
        f"- docking_results_emitted: `{s['docking_results_emitted']}`",
        f"- delivery_ready_claim_allowed: `{s['delivery_ready_claim_allowed']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Capabilities",
        "",
        "| capability | domain | status | observed | required | artifact | reason |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['capability_id']}` | `{row['domain']}` | `{row['status']}` | "
            f"`{row['observed']}` | `{row['required']}` | `{row['artifact_path']}` | {row['reason']} |"
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
    parser = argparse.ArgumentParser(description="Build a product capability surface contract from local artifacts.")
    parser.add_argument("--readiness-json", default=DEFAULT_READINESS_JSON)
    parser.add_argument("--work-order-json", default=DEFAULT_WORK_ORDER_JSON)
    parser.add_argument("--preflight-json", default=DEFAULT_PREFLIGHT_JSON)
    parser.add_argument("--structure-report-json", default=DEFAULT_STRUCTURE_REPORT_JSON)
    parser.add_argument("--bundle-contract-json", default=DEFAULT_BUNDLE_CONTRACT_JSON)
    parser.add_argument("--delivery-evidence-json", default=DEFAULT_DELIVERY_EVIDENCE_JSON)
    parser.add_argument("--pilot-packet-json", default=DEFAULT_PILOT_PACKET_JSON)
    parser.add_argument("--scope-breadth-json", default=DEFAULT_SCOPE_BREADTH_JSON)
    parser.add_argument("--root", default=".")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_product_capability_surface_contract(
        readiness_packet=_read_json_if_present(args.readiness_json),
        work_order_packet=_read_json_if_present(args.work_order_json),
        preflight_packet=_read_json_if_present(args.preflight_json),
        structure_report_packet=_read_json_if_present(args.structure_report_json),
        bundle_contract_packet=_read_json_if_present(args.bundle_contract_json),
        delivery_evidence_packet=_read_json_if_present(args.delivery_evidence_json),
        pilot_packet=_read_json_if_present(args.pilot_packet_json),
        scope_breadth_packet=_read_json_if_present(args.scope_breadth_json),
        root=args.root,
        readiness_path=args.readiness_json,
        work_order_path=args.work_order_json,
        preflight_path=args.preflight_json,
        structure_report_path=args.structure_report_json,
        bundle_contract_path=args.bundle_contract_json,
        delivery_evidence_path=args.delivery_evidence_json,
        pilot_packet_path=args.pilot_packet_json,
        scope_breadth_path=args.scope_breadth_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
