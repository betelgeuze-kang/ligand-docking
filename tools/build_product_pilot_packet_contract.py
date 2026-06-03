#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from betelgeuze_product.pilot_packet import build_product_pilot_packet_contract
from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PRODUCT_READINESS_JSON = "runs/product_readiness_gate_current.json"
DEFAULT_PRODUCT_PREFLIGHT_JSON = "runs/product_execution_preflight_current.json"
DEFAULT_PRODUCT_BUNDLE_CONTRACT_JSON = "runs/product_bundle_contract_current.json"
DEFAULT_PRODUCT_DELIVERY_EVIDENCE_JSON = "runs/product_delivery_evidence_contract_current.json"
DEFAULT_BUNDLE_VALIDATION_JSON = "runs/local_delivery/bundle_product_gpcr_adrb2/validation.json"
DEFAULT_OUT_JSON = "runs/product_pilot_packet_contract_current.json"
DEFAULT_OUT_CSV = "runs/product_pilot_packet_contract_current.csv"
DEFAULT_OUT_MD = "runs/product_pilot_packet_contract_current.md"


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


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
        "# Product Pilot Packet Contract",
        "",
        f"- status: `{s['status']}`",
        f"- target_id: `{s['target_id']}`",
        f"- family: `{s['family']}`",
        f"- ligand_count: `{s['ligand_count']}`",
        f"- blocker_count: `{s['blocker_count']}`",
        f"- warning_count: `{s['warning_count']}`",
        f"- expected_bundle_dir: `{s['expected_bundle_dir']}`",
        f"- bundle_dir_exists: `{s['bundle_dir_exists']}`",
        f"- bundle_assembled: `{s['bundle_assembled']}`",
        f"- bundle_validation_present: `{s['bundle_validation_present']}`",
        f"- bundle_validation_passed: `{s['bundle_validation_passed']}`",
        f"- delivery_ready_claim_allowed: `{s['delivery_ready_claim_allowed']}`",
        f"- pilot_delivery_ready: `{s['pilot_delivery_ready']}`",
        f"- operator_approval_required: `{s['operator_approval_required']}`",
        f"- approval_token_required: `{s['approval_token_required']}`",
        f"- execution_enabled: `{s['execution_enabled']}`",
        f"- docking_results_emitted: `{s['docking_results_emitted']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        f"- validated_without_execution: `{s['validated_without_execution']}`",
        "",
        "## Checks",
        "",
        "| check | status | observed | required | artifact |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['check']}` | `{row['status']}` | `{row['observed']}` | "
            f"`{row['required']}` | `{row['artifact_path']}` |"
        )

    lines.extend(["", "## Blockers", ""])
    blockers = payload.get("blockers") or []
    if blockers:
        lines.extend(f"- `{blocker['code']}`: {blocker['reason']}" for blocker in blockers)
    else:
        lines.append("- none")

    lines.extend(["", "## Warnings", ""])
    warnings = payload.get("warnings") or []
    if warnings:
        lines.extend(f"- `{warning['code']}`: {warning['reason']}" for warning in warnings)
    else:
        lines.append("- none")

    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a product pilot packet contract without execution or bundle assembly.")
    parser.add_argument("--product-readiness-json", default=DEFAULT_PRODUCT_READINESS_JSON)
    parser.add_argument("--product-preflight-json", default=DEFAULT_PRODUCT_PREFLIGHT_JSON)
    parser.add_argument("--product-bundle-contract-json", default=DEFAULT_PRODUCT_BUNDLE_CONTRACT_JSON)
    parser.add_argument("--product-delivery-evidence-json", default=DEFAULT_PRODUCT_DELIVERY_EVIDENCE_JSON)
    parser.add_argument("--bundle-validation-json", default=DEFAULT_BUNDLE_VALIDATION_JSON)
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_product_pilot_packet_contract(
        product_readiness_packet=_read_json(args.product_readiness_json),
        product_execution_preflight_packet=_read_json(args.product_preflight_json),
        product_bundle_contract_packet=_read_json(args.product_bundle_contract_json),
        product_delivery_evidence_packet=_read_json(args.product_delivery_evidence_json),
        bundle_validation_packet=_read_json_if_present(args.bundle_validation_json),
        root=args.root,
        product_readiness_path=args.product_readiness_json,
        product_execution_preflight_path=args.product_preflight_json,
        product_bundle_contract_path=args.product_bundle_contract_json,
        product_delivery_evidence_path=args.product_delivery_evidence_json,
        bundle_validation_path=args.bundle_validation_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
