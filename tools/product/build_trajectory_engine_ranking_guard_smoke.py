#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from betelgeuze_product.residual_mode_policy import (
    customer_ligand_ranking_snapshot,
    customer_ranking_mutation_allowed_at_runtime,
    production_ai_inference_subject_active,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/trajectory_engine_ranking_guard_smoke_current.json"
DEFAULT_REGISTRY_JSON = "runs/residual_model_registry_current.json"

CLAIM_BOUNDARY = (
    "Trajectory-engine ranking-guard smoke only; requires production promotion green, runs "
    "generate_ligand_trajectory_engine on one queue row, then validates customer ranking order "
    "changes only when the runtime guard unlocks. It does not mutate production ledgers or claim "
    "broad platform SLA."
)

RANKING_SCORE_ROWS = [
    {
        "ligand_id": "lig_a",
        "binding_score_composite_v7": 1.0,
        "binding_score_composite_v7_residual_active": -5.0,
    },
    {
        "ligand_id": "lig_b",
        "binding_score_composite_v7": -5.0,
        "binding_score_composite_v7_residual_active": 1.0,
    },
]


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    if isinstance(summary, dict):
        return summary
    return packet if isinstance(packet, dict) else {}


def _ranking_scenarios(registry: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for shadow_only_active_locked, expected_mutation in (
        (True, False),
        (False, True),
    ):
        ranking_mutation_allowed = customer_ranking_mutation_allowed_at_runtime(
            registry,
            shadow_only_active_locked=shadow_only_active_locked,
        )
        ranking = customer_ligand_ranking_snapshot(
            RANKING_SCORE_ROWS,
            ranking_mutation_allowed=ranking_mutation_allowed,
        )
        rows.append(
            {
                "scenario": "shadow_locked" if shadow_only_active_locked else "shadow_unlocked",
                "shadow_only_active_locked": shadow_only_active_locked,
                "production_ai_inference_subject_active": production_ai_inference_subject_active(registry),
                "production_ai_customer_facing_ranking_mutation_allowed": ranking_mutation_allowed,
                "customer_score_column": ranking["customer_score_column"],
                "base_ranking_ligand_ids": ranking["base_ranking_ligand_ids"],
                "customer_ranking_ligand_ids": ranking["customer_ranking_ligand_ids"],
                "ranking_mutated": ranking["ranking_mutated"],
                "expected_ranking_mutated": expected_mutation,
                "pass": ranking["ranking_mutated"] is expected_mutation
                and ranking_mutation_allowed is (not shadow_only_active_locked),
            }
        )
    return rows


def _default_engine_runner(queue_csv: Path, out_root: Path) -> dict[str, Any]:
    from tools import generate_ligand_trajectory_engine as mod

    args = mod.build_parser().parse_args(
        [
            "--queue-csv",
            str(queue_csv),
            "--out-root",
            str(out_root),
            "--out-summary-json",
            str(out_root.parent / f"{out_root.name}_summary.json"),
            "--out-manifest-csv",
            str(out_root.parent / f"{out_root.name}_manifest.csv"),
            "--frame-output-format",
            "manifest_only",
            "--max-jobs",
            "1",
            "--frames",
            "2",
            "--write-every",
            "1",
            "--writer-workers",
            "0",
            "--no-fail-on-missing-native",
        ]
    )
    return mod.run_batch(args)


def run_smoke(
    *,
    registry_packet: dict[str, Any],
    engine_runner: Callable[[Path, Path], dict[str, Any]] | None = None,
    work_root: Path | None = None,
) -> dict[str, Any]:
    registry = _summary(registry_packet)
    promotion_green = production_ai_inference_subject_active(registry)
    ranking_rows = _ranking_scenarios(registry)
    ranking_pass_count = sum(1 for row in ranking_rows if row["pass"])

    engine_summary: dict[str, Any] = {}
    engine_error = ""
    engine_executed = False
    if promotion_green:
        work_root = work_root or (_resolve("runs") / "trajectory_engine_ranking_guard_smoke_work")
        work_root.mkdir(parents=True, exist_ok=True)
        queue_csv = work_root / "queue.csv"
        pd.DataFrame(
            [
                {
                    "queue_id": "traj_rank_smoke_q1",
                    "target": "ADRB2",
                    "ligand_id": "lig_a",
                    "ligand_mw": 180.0,
                }
            ]
        ).to_csv(queue_csv, index=False)
        out_root = work_root / "engine_out"
        runner = engine_runner or _default_engine_runner
        try:
            engine_summary = runner(queue_csv, out_root)
            engine_executed = True
        except Exception as exc:  # pragma: no cover - surfaced in smoke status
            engine_error = f"{type(exc).__name__}:{exc}"

    engine_ok_rows = int(engine_summary.get("ok_rows") or 0)
    engine_processed_rows = int(engine_summary.get("processed_rows") or 0)
    engine_pass = promotion_green and engine_executed and engine_ok_rows >= 1 and engine_processed_rows >= 1
    all_pass = promotion_green and engine_pass and ranking_pass_count == len(ranking_rows)
    blockers: list[str] = []
    if not promotion_green:
        blockers.append("production_promotion_not_green")
    if promotion_green and not engine_pass:
        blockers.append("trajectory_engine_single_queue_row_failed")
    if ranking_pass_count != len(ranking_rows):
        blockers.append("ranking_guard_scenario_failed")

    summary = {
        "packet_type": "trajectory_engine_ranking_guard_smoke",
        "status": "trajectory_engine_ranking_guard_smoke_ready"
        if all_pass
        else "blocked_trajectory_engine_ranking_guard_smoke",
        "claim_boundary": CLAIM_BOUNDARY,
        "production_promotion_green": promotion_green,
        "production_ai_default_residual_mode": registry.get("default_residual_mode", ""),
        "production_ai_promotion_allowed": registry.get("production_promotion_allowed"),
        "production_ai_customer_facing_ranking_mutation_allowed": registry.get(
            "customer_facing_ranking_mutation_allowed"
        ),
        "engine_executed": engine_executed,
        "engine_processed_rows": engine_processed_rows,
        "engine_ok_rows": engine_ok_rows,
        "engine_failed_rows": int(engine_summary.get("failed_rows") or 0),
        "engine_error": engine_error,
        "ranking_scenario_count": len(ranking_rows),
        "ranking_pass_scenario_count": ranking_pass_count,
        "ranking_fail_scenario_count": len(ranking_rows) - ranking_pass_count,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "execution_enabled": engine_executed,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "next_required_step": (
            "Post-promotion trajectory engine processed one queue row and ranking guard preserves base "
            "order when locked while reordering on residual-active scores when unlocked."
            if all_pass
            else "Repair production promotion registry, trajectory engine single-row execution, or ranking guard wiring."
        ),
    }
    return {"summary": summary, "ranking_rows": ranking_rows, "engine_summary": engine_summary}


def main() -> None:
    parser = argparse.ArgumentParser(description=CLAIM_BOUNDARY)
    parser.add_argument("--registry-json", default=DEFAULT_REGISTRY_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    args = parser.parse_args()
    registry_path = _resolve(args.registry_json)
    registry_packet = json.loads(registry_path.read_text(encoding="utf-8")) if registry_path.exists() else {}
    payload = run_smoke(registry_packet=registry_packet if isinstance(registry_packet, dict) else {})
    out_path = _resolve(args.out_json)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
