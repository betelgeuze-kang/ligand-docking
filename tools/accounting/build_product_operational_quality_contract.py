#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from betelgeuze_product.operational_quality import build_product_operational_quality_contract
from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_JSON = "runs/product_operational_quality_contract_current.json"
DEFAULT_OUT_CSV = "runs/product_operational_quality_contract_current.csv"
DEFAULT_OUT_MD = "runs/product_operational_quality_contract_current.md"


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _write_json(path_like: str | Path, payload: dict) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Product Operational Quality Contract",
        "",
        f"- status: `{s['status']}`",
        f"- operational_quality_ready: `{s['operational_quality_ready']}`",
        f"- check_count: `{s['check_count']}`",
        f"- pass_count: `{s['pass_count']}`",
        f"- blocker_count: `{s['blocker_count']}`",
        f"- fail_closed_docking_intake_ready: `{s['fail_closed_docking_intake_ready']}`",
        f"- production_ai_correction_fail_closed_ready: `{s['production_ai_correction_fail_closed_ready']}`",
        f"- sample_production_ai_inference_subject_active: `{s['sample_production_ai_inference_subject_active']}`",
        f"- sample_production_ai_correction_applied: `{s['sample_production_ai_correction_applied']}`",
        f"- sample_production_ai_abstention_enforced: `{s['sample_production_ai_abstention_enforced']}`",
        f"- sample_production_ai_default_residual_mode: `{s['sample_production_ai_default_residual_mode']}`",
        f"- sample_production_ai_customer_facing_auto_correction_allowed: `{s['sample_production_ai_customer_facing_auto_correction_allowed']}`",
        f"- sample_production_ai_customer_facing_score_mutation_allowed: `{s['sample_production_ai_customer_facing_score_mutation_allowed']}`",
        f"- sample_production_ai_customer_facing_ranking_mutation_allowed: `{s['sample_production_ai_customer_facing_ranking_mutation_allowed']}`",
        f"- ledger_payload_privacy_ready: `{s['ledger_payload_privacy_ready']}`",
        f"- request_traceability_ready: `{s['request_traceability_ready']}`",
        f"- scope_limit_enforcement_ready: `{s['scope_limit_enforcement_ready']}`",
        f"- heavy_artifact_policy_ready: `{s['heavy_artifact_policy_ready']}`",
        f"- input_payload_persisted: `{s['input_payload_persisted']}`",
        f"- execution_enabled: `{s['execution_enabled']}`",
        f"- docking_results_emitted: `{s['docking_results_emitted']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Checks",
        "",
        "| check | status | observed | required | reason |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['check']}` | `{row['status']}` | `{row['observed']}` | `{row['required']}` | {row['reason']} |"
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
    parser = argparse.ArgumentParser(description="Build the product operational quality contract.")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_product_operational_quality_contract()
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
