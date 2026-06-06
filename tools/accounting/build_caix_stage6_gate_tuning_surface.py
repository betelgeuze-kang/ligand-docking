#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab_target_render_utils import maybe_load_json, write_artifact

DEFAULT_RUNTIME_PROFILE_JSON = "runs/caix_broad_screen_runtime_profile_current.json"
DEFAULT_OUT_MD = "runs/caix_stage6_gate_tuning_surface_current.md"


def build_payload(runtime_profile_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    rows = runtime_profile_payload.get("rows", []) if runtime_profile_payload else []
    gate_row = next((row for row in rows if str(row.get("failed_stage", "")).strip() == "stage6_operational_gate"), {})
    observed = float(gate_row.get("mean_min_distance_A", 0.0) or 0.0)
    candidates = [
        {"candidate_id": "tight_keep", "gate_max_mean_min_distance_A": 2.5, "would_pass_observed_08": observed <= 2.5, "risk_band": "very_low", "recommendation": "keep as current reference"},
        {"candidate_id": "conservative_relax", "gate_max_mean_min_distance_A": 3.0, "would_pass_observed_08": observed <= 3.0, "risk_band": "low", "recommendation": "unlikely to change CA IX 08 outcome"},
        {"candidate_id": "moderate_relax", "gate_max_mean_min_distance_A": 4.0, "would_pass_observed_08": observed <= 4.0, "risk_band": "medium", "recommendation": "still likely fails 08; mostly useful as an intermediate sensitivity check"},
        {"candidate_id": "aggressive_relax", "gate_max_mean_min_distance_A": 5.5, "would_pass_observed_08": observed <= 5.5, "risk_band": "high", "recommendation": "would clear the observed 08 row, but changes the scientific bar materially"},
    ]
    recommended = next((row for row in candidates if row["candidate_id"] == "moderate_relax"), candidates[0])
    return {
        "summary": {
            "status": "caix_stage6_gate_tuning_surface_ready",
            "target_id": "CA IX",
            "observed_failed_stage": str(gate_row.get("failed_stage", "")).strip(),
            "observed_mean_min_distance_A": observed,
            "current_gate_threshold_A": 2.5,
            "candidate_count": len(candidates),
            "recommended_candidate_id": recommended["candidate_id"],
            "next_required_step": "Try the slow-shard preset first; use this surface only if you intentionally want to relax the stage6 operational distance gate.",
        },
        "structured": {
            "runtime_profile_artifact": "runs/caix_broad_screen_runtime_profile_current.md",
        },
        "rows": candidates,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CA IX stage6 gate tuning candidates from the current runtime profile.")
    parser.add_argument("--runtime-profile-json", default=DEFAULT_RUNTIME_PROFILE_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    write_artifact(
        args.out_md,
        "CA IX Stage6 Gate Tuning Surface",
        build_payload(maybe_load_json(args.runtime_profile_json)),
    )


if __name__ == "__main__":
    main()
