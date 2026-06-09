#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from betelgeuze_product.docking_request import _production_ai_posture_from_registry
from betelgeuze_product.residual_mode_policy import (
    customer_ranking_mutation_allowed_at_runtime,
    production_ai_inference_subject_active,
    residual_active_score_column,
    residual_runtime_status,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/residual_mode_inference_wiring_smoke_current.json"

CLAIM_BOUNDARY = (
    "Residual mode inference wiring smoke only; verifies shadow/assist/production_guarded registry postures "
    "against docking-request policy and ranking-mutation guards. It does not run docking or mutate rankings."
)

MODE_FIXTURES: dict[str, dict[str, Any]] = {
    "shadow": {
        "default_residual_mode": "shadow",
        "production_promotion_allowed": False,
        "customer_facing_auto_correction_allowed": False,
        "customer_facing_score_mutation_allowed": False,
        "customer_facing_ranking_mutation_allowed": False,
        "trained_model_checkpoint_count": 1,
    },
    "assist": {
        "default_residual_mode": "assist",
        "production_promotion_allowed": True,
        "customer_facing_auto_correction_allowed": True,
        "customer_facing_score_mutation_allowed": True,
        "customer_facing_ranking_mutation_allowed": False,
        "trained_model_checkpoint_count": 1,
    },
    "production_guarded": {
        "default_residual_mode": "production_guarded",
        "production_promotion_allowed": True,
        "customer_facing_auto_correction_allowed": True,
        "customer_facing_score_mutation_allowed": True,
        "customer_facing_ranking_mutation_allowed": True,
        "trained_model_checkpoint_count": 1,
    },
}


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def run_smoke() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for mode_name, registry in MODE_FIXTURES.items():
        posture = _production_ai_posture_from_registry(registry)
        ranking_guard_locked = customer_ranking_mutation_allowed_at_runtime(registry, shadow_only_active_locked=True)
        ranking_guard_unlocked = customer_ranking_mutation_allowed_at_runtime(registry, shadow_only_active_locked=False)
        active_col_locked = residual_active_score_column(
            assist_mode=_text(registry.get("default_residual_mode")),
            shadow_only_active_locked=True,
        )
        active_col_unlocked = residual_active_score_column(
            assist_mode=_text(registry.get("default_residual_mode")),
            shadow_only_active_locked=False,
        )
        runtime_status_unlocked = residual_runtime_status(
            assist_mode=_text(registry.get("default_residual_mode")),
            shadow_only_active_locked=False,
        )
        expected_inference_active = mode_name == "production_guarded"
        expected_ranking_unlocked = mode_name == "production_guarded"
        row = {
            "mode_fixture": mode_name,
            "default_residual_mode": registry.get("default_residual_mode"),
            "production_ai_inference_subject_active": posture.get("production_ai_inference_subject_active"),
            "production_ai_ranking_mutation_allowed_flag": posture.get(
                "production_ai_customer_facing_ranking_mutation_allowed"
            ),
            "ranking_mutation_guard_locked": ranking_guard_locked,
            "ranking_mutation_guard_unlocked": ranking_guard_unlocked,
            "active_score_column_locked": active_col_locked,
            "active_score_column_unlocked": active_col_unlocked,
            "runtime_status_unlocked": runtime_status_unlocked,
            "policy_locked_inference_matches_expectation": posture.get("production_ai_inference_subject_active")
            is expected_inference_active,
            "ranking_guard_unlocked_matches_expectation": ranking_guard_unlocked is expected_ranking_unlocked,
            "pass": (
                posture.get("production_ai_inference_subject_active") is expected_inference_active
                and ranking_guard_unlocked is expected_ranking_unlocked
                and (mode_name != "production_guarded" or active_col_unlocked == "binding_score_composite_v7_residual_active")
                and (mode_name == "shadow" or runtime_status_unlocked == "residual_assist_ready")
            ),
        }
        rows.append(row)
    pass_count = sum(1 for row in rows if row["pass"])
    summary = {
        "packet_type": "residual_mode_inference_wiring_smoke",
        "status": "residual_mode_inference_wiring_smoke_ready" if pass_count == len(rows) else "blocked_residual_mode_inference_wiring_smoke",
        "claim_boundary": CLAIM_BOUNDARY,
        "mode_fixture_count": len(rows),
        "pass_mode_count": pass_count,
        "fail_mode_count": len(rows) - pass_count,
        "execution_enabled": False,
        "benchmark_executed": True,
        "external_state_mutated": False,
        "next_required_step": (
            "Residual mode policy wiring is consistent across shadow, assist, and production_guarded fixtures."
            if pass_count == len(rows)
            else "Repair registry-to-runtime policy wiring for failing residual mode fixtures."
        ),
    }
    return {"summary": summary, "rows": rows}


def _text(value: Any) -> str:
    return str(value or "").strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke-test residual mode registry-to-runtime policy wiring.")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = run_smoke()
    path = _resolve(args.out_json)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
