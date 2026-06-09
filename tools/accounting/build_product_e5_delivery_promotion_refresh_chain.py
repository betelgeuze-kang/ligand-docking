#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from tools.builder_json_utils import read_json, read_summary

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/product_e5_delivery_promotion_refresh_chain_current.json"

# command, optional extra argv
E5_STEPS: list[tuple[str, list[str]]] = [
    ("tools/build_residual_shadow_ab.py", []),
    ("tools/build_backmapping_scoring_batch_smoke_benchmark.py", []),
    ("tools/build_product_end_to_end_rocm_benchmark.py", []),
    ("tools/build_gpcr_hard_decoy_residual_proof.py", []),
    ("tools/build_public_benchmark_residual_regression_gate.py", []),
    (
        "tools/train_residual_production_score_model.py",
        [
            "--skip-if-unchanged",
            "--force-derivation-json",
            "runs/residual_force_derivation_validation_current.json",
        ],
    ),
    ("tools/build_residual_production_training_data_contract.py", []),
    ("tools/build_residual_production_checkpoint_sidecar.py", []),
    ("tools/build_residual_production_checkpoint_preflight.py", []),
    ("tools/build_residual_assist_promotion_gate.py", []),
    ("tools/build_residual_production_promotion_gate.py", []),
    ("tools/build_residual_model_registry.py", []),
    ("tools/build_commercial_gap_closure_status.py", []),
    ("tools/build_product_goal_completion_audit.py", []),
    ("tools/build_residual_mode_inference_wiring_smoke.py", []),
    ("tools/build_docking_ranking_mutation_e2e_smoke.py", []),
    ("tools/build_trajectory_engine_ranking_guard_smoke.py", []),
]


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _run_step(command: str, extra_args: list[str]) -> dict[str, Any]:
    proc = subprocess.run([sys.executable, command, *extra_args], cwd=ROOT, capture_output=True, text=True)
    return {
        "step_id": Path(command).stem,
        "command": command,
        "extra_args": extra_args,
        "returncode": proc.returncode,
        "ok": proc.returncode == 0,
        "stderr_tail": "\n".join(proc.stderr.splitlines()[-8:]),
    }


def build_payload(*, execute: bool) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    if execute:
        for command, extra_args in E5_STEPS:
            row = _run_step(command, extra_args)
            rows.append(row)
            if not row["ok"]:
                break
    else:
        for command, extra_args in E5_STEPS:
            rows.append(
                {
                    "step_id": Path(command).stem,
                    "command": command,
                    "extra_args": extra_args,
                    "execution_enabled": False,
                }
            )

    shadow = read_summary(read_json("runs/residual_shadow_ab_current.json", root=ROOT))
    assist = read_summary(read_json("runs/residual_assist_promotion_gate_current.json", root=ROOT))
    production = read_summary(read_json("runs/residual_production_promotion_gate_current.json", root=ROOT))
    registry = read_summary(read_json("runs/residual_model_registry_current.json", root=ROOT))
    e2e = read_summary(read_json("runs/product_end_to_end_rocm_benchmark_current.json", root=ROOT))
    goal = read_summary(read_json("runs/product_goal_completion_audit_current.json", root=ROOT))
    ready = (
        shadow.get("scaffold_ready") is True
        and assist.get("assist_promotion_allowed") is True
        and production.get("production_promotion_allowed") is True
        and registry.get("production_promotion_allowed") is True
        and e2e.get("benchmark_ready") is True
        and (not execute or all(row.get("ok") for row in rows))
    )
    summary = {
        "packet_type": "product_e5_delivery_promotion_refresh_chain",
        "status": "product_e5_delivery_promotion_refresh_chain_ready" if ready else "blocked_product_e5_delivery_promotion_refresh_chain",
        "generated_at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).isoformat(),
        "execution_enabled": execute,
        "shadow_scaffold_ready": shadow.get("scaffold_ready"),
        "assist_promotion_allowed": assist.get("assist_promotion_allowed"),
        "production_promotion_allowed": production.get("production_promotion_allowed"),
        "registry_production_promotion_allowed": registry.get("production_promotion_allowed"),
        "e2e_benchmark_ready": e2e.get("benchmark_ready"),
        "goal_complete": goal.get("goal_complete"),
        "residual_mode_promotion_path": "shadow -> assist -> production",
        "promotion_refresh_step_count": len(E5_STEPS),
        "next_required_step": (
            "E5 promotion refresh chain green; shadow, checkpoint, assist, production, and registry artifacts are aligned."
            if ready
            else "Repair failing E5 promotion refresh steps, then rerun with --execute."
        ),
    }
    return {"summary": summary, "rows": rows}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run full residual promotion refresh: shadow, checkpoint, assist, production, registry."
    )
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--execute", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(execute=bool(args.execute))
    _write_json(args.out_json, payload)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
