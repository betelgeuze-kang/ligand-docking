#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from betelgeuze_product.operational_quality import build_product_operational_quality_contract

CLAIM_BOUNDARY = (
    "Product quality gate verifier only; it rebuilds the local operational quality contract in memory and checks "
    "fail-closed intake, production-AI correction guardrails, ledger privacy, traceability, scope limits, and heavy "
    "artifact policy. It does not run docking, persist jobs, emit results, upload, email, delete, commit, push, or "
    "mutate external state."
)


def _row(check: str, passed: bool, observed: str, required: str) -> dict[str, Any]:
    return {
        "check": check,
        "status": "pass" if passed else "fail",
        "observed": observed,
        "required": required,
        "release_blocker": not passed,
        "execution_enabled": False,
        "external_state_mutated": False,
    }


def build_quality_gate_verification() -> dict[str, Any]:
    contract = build_product_operational_quality_contract()
    summary = contract.get("summary", {})
    rows = [
        _row(
            "operational_quality_contract_ready",
            summary.get("status") == "product_operational_quality_contract_ready"
            and summary.get("operational_quality_ready") is True
            and int(summary.get("blocker_count") or 0) == 0,
            (
                f"status={summary.get('status')};ready={summary.get('operational_quality_ready')};"
                f"blocker_count={summary.get('blocker_count')};pass_count={summary.get('pass_count')};"
                f"check_count={summary.get('check_count')}"
            ),
            "product_operational_quality_contract_ready with zero blockers",
        ),
        _row(
            "fail_closed_execution_posture",
            summary.get("execution_enabled") is False
            and summary.get("docking_results_emitted") is False
            and summary.get("external_state_mutated") is False
            and summary.get("input_payload_persisted") is False,
            (
                f"execution_enabled={summary.get('execution_enabled')};"
                f"docking_results_emitted={summary.get('docking_results_emitted')};"
                f"external_state_mutated={summary.get('external_state_mutated')};"
                f"input_payload_persisted={summary.get('input_payload_persisted')}"
            ),
            "execution/results/external mutation/input payload persistence all false",
        ),
        _row(
            "production_ai_correction_guarded",
            summary.get("production_ai_correction_fail_closed_ready") is True
            and summary.get("sample_production_ai_correction_applied") is False
            and summary.get("sample_production_ai_abstention_enforced") is True
            and summary.get("sample_production_ai_customer_facing_auto_correction_allowed") is False
            and summary.get("sample_production_ai_customer_facing_score_mutation_allowed") is False
            and summary.get("sample_production_ai_customer_facing_ranking_mutation_allowed") is False,
            (
                f"correction_fail_closed={summary.get('production_ai_correction_fail_closed_ready')};"
                f"correction_applied={summary.get('sample_production_ai_correction_applied')};"
                f"abstention={summary.get('sample_production_ai_abstention_enforced')};"
                f"auto={summary.get('sample_production_ai_customer_facing_auto_correction_allowed')};"
                f"score={summary.get('sample_production_ai_customer_facing_score_mutation_allowed')};"
                f"ranking={summary.get('sample_production_ai_customer_facing_ranking_mutation_allowed')}"
            ),
            "production AI correction is fail-closed and customer-facing mutation flags are false",
        ),
        _row(
            "ledger_privacy_traceability_scope_policy_ready",
            summary.get("ledger_payload_privacy_ready") is True
            and summary.get("request_traceability_ready") is True
            and summary.get("scope_limit_enforcement_ready") is True
            and summary.get("heavy_artifact_policy_ready") is True,
            (
                f"ledger_privacy={summary.get('ledger_payload_privacy_ready')};"
                f"traceability={summary.get('request_traceability_ready')};"
                f"scope={summary.get('scope_limit_enforcement_ready')};"
                f"heavy_artifact={summary.get('heavy_artifact_policy_ready')}"
            ),
            "ledger privacy, traceability, scope limit, and heavy artifact policy are ready",
        ),
    ]
    blockers = [row["check"] for row in rows if row["status"] != "pass"]
    return {
        "summary": {
            "packet_type": "product_quality_gate_verification",
            "status": "product_quality_gate_verified" if not blockers else "blocked_product_quality_gate",
            "quality_gate_ready": not blockers,
            "check_count": len(rows),
            "pass_count": sum(1 for row in rows if row["status"] == "pass"),
            "blocker_count": len(blockers),
            "blocked_checks": blockers,
            "source_contract_status": summary.get("status"),
            "source_contract_check_count": summary.get("check_count"),
            "source_contract_pass_count": summary.get("pass_count"),
            "execution_enabled": False,
            "external_state_mutated": False,
            "claim_boundary": CLAIM_BOUNDARY,
            "next_required_step": (
                "Quality gate is verified; keep this script in the operator preflight chain."
                if not blockers
                else "Fix the failed quality checks before release handoff."
            ),
        },
        "rows": rows,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify the current product operational quality gate.")
    parser.add_argument("--out-json", default="", help="Optional path to write the verification payload.")
    parser.add_argument("--quiet", action="store_true", help="Do not print the JSON payload to stdout.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_quality_gate_verification()
    if args.out_json:
        path = Path(args.out_json)
        path = path if path.is_absolute() else ROOT / path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    if not args.quiet:
        print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if payload["summary"]["quality_gate_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
