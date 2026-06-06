#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from betelgeuze_product.delivery_evidence import build_product_delivery_evidence_contract
from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PRODUCT_READINESS_JSON = "runs/product_readiness_gate_current.json"
DEFAULT_PRODUCT_PREFLIGHT_JSON = "runs/product_execution_preflight_current.json"
DEFAULT_PRODUCT_BUNDLE_CONTRACT_JSON = "runs/product_bundle_contract_current.json"
DEFAULT_LOCAL_DELIVERY_VERDICT_JSON = "runs/local_delivery_verdict_gate_current.json"
DEFAULT_LOCAL_DELIVERY_PREFLIGHT_JSON = "runs/local_delivery_preflight_current.json"
DEFAULT_ENVIRONMENT_MANIFEST_JSON = "runs/local_delivery_environment_manifest_current.json"
DEFAULT_REQUIREMENTS_LOCK_JSON = "runs/local_delivery_requirements_lock_current.json"
DEFAULT_ENGINE_PROVENANCE_JSON = "runs/local_delivery_engine_provenance_current.json"
DEFAULT_COMMERCIALIZATION_QUEUE_JSON = "runs/local_engine_commercialization_queue_current.json"
DEFAULT_NIGHTLY_GATE_JSON = "runs/nightly_gate_burndown_packet_current.json"
DEFAULT_WETLAB_GATE_JSON = "runs/wetlab_selected_allatom_gate_burndown_packet_current.json"
DEFAULT_OUT_JSON = "runs/product_delivery_evidence_contract_current.json"
DEFAULT_OUT_CSV = "runs/product_delivery_evidence_contract_current.csv"
DEFAULT_OUT_MD = "runs/product_delivery_evidence_contract_current.md"


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Product Delivery Evidence Contract",
        "",
        f"- status: `{s['status']}`",
        f"- target_id: `{s['target_id']}`",
        f"- family: `{s['family']}`",
        f"- ligand_count: `{s['ligand_count']}`",
        f"- blocker_count: `{s['blocker_count']}`",
        f"- warning_count: `{s['warning_count']}`",
        f"- evidence_pass_count: `{s['evidence_pass_count']}/{s['evidence_check_count']}`",
        f"- delivery_ready_claim_allowed: `{s['delivery_ready_claim_allowed']}`",
        f"- bundle_assembled: `{s['bundle_assembled']}`",
        f"- bundle_validation_passed: `{s['bundle_validation_passed']}`",
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
    parser = argparse.ArgumentParser(description="Build a product delivery evidence contract without executing or assembling anything.")
    parser.add_argument("--product-readiness-json", default=DEFAULT_PRODUCT_READINESS_JSON)
    parser.add_argument("--product-preflight-json", default=DEFAULT_PRODUCT_PREFLIGHT_JSON)
    parser.add_argument("--product-bundle-contract-json", default=DEFAULT_PRODUCT_BUNDLE_CONTRACT_JSON)
    parser.add_argument("--local-delivery-verdict-json", default=DEFAULT_LOCAL_DELIVERY_VERDICT_JSON)
    parser.add_argument("--local-delivery-preflight-json", default=DEFAULT_LOCAL_DELIVERY_PREFLIGHT_JSON)
    parser.add_argument("--environment-manifest-json", default=DEFAULT_ENVIRONMENT_MANIFEST_JSON)
    parser.add_argument("--requirements-lock-json", default=DEFAULT_REQUIREMENTS_LOCK_JSON)
    parser.add_argument("--engine-provenance-json", default=DEFAULT_ENGINE_PROVENANCE_JSON)
    parser.add_argument("--commercialization-queue-json", default=DEFAULT_COMMERCIALIZATION_QUEUE_JSON)
    parser.add_argument("--nightly-gate-json", default=DEFAULT_NIGHTLY_GATE_JSON)
    parser.add_argument("--wetlab-gate-json", default=DEFAULT_WETLAB_GATE_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_product_delivery_evidence_contract(
        product_readiness_packet=_read_json(args.product_readiness_json),
        product_execution_preflight_packet=_read_json(args.product_preflight_json),
        product_bundle_contract_packet=_read_json(args.product_bundle_contract_json),
        local_delivery_verdict_packet=_read_json(args.local_delivery_verdict_json),
        local_delivery_preflight_packet=_read_json(args.local_delivery_preflight_json),
        environment_manifest_packet=_read_json(args.environment_manifest_json),
        requirements_lock_packet=_read_json(args.requirements_lock_json),
        engine_provenance_packet=_read_json(args.engine_provenance_json),
        commercialization_queue_packet=_read_json(args.commercialization_queue_json),
        nightly_gate_packet=_read_json(args.nightly_gate_json),
        wetlab_gate_packet=_read_json(args.wetlab_gate_json),
        product_readiness_path=args.product_readiness_json,
        product_execution_preflight_path=args.product_preflight_json,
        product_bundle_contract_path=args.product_bundle_contract_json,
        local_delivery_verdict_path=args.local_delivery_verdict_json,
        local_delivery_preflight_path=args.local_delivery_preflight_json,
        environment_manifest_path=args.environment_manifest_json,
        requirements_lock_path=args.requirements_lock_json,
        engine_provenance_path=args.engine_provenance_json,
        commercialization_queue_path=args.commercialization_queue_json,
        nightly_gate_path=args.nightly_gate_json,
        wetlab_gate_path=args.wetlab_gate_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
