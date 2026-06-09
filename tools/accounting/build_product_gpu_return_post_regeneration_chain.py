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
DEFAULT_OUT_JSON = "runs/product_gpu_return_post_regeneration_chain_current.json"
DEFAULT_OUT_MD = "runs/product_gpu_return_post_regeneration_chain_current.md"

POST_RETURN_STEPS: list[tuple[str, list[str]]] = [
    ("tools/build_rocm_environment_manifest.py", []),
    ("tools/build_residual_force_trajectory_regeneration_execution_probe.py", []),
    ("tools/build_residual_force_gpu_worker_return_manifest_finalize.py", []),
    ("tools/build_residual_force_gpu_worker_return_receipt.py", []),
    ("tools/build_residual_force_derivation_validation.py", []),
    ("tools/build_residual_energy_force_label_validation.py", []),
    ("tools/build_residual_energy_force_label_evidence_work_order.py", []),
    ("tools/build_residual_uncertainty_policy_evidence_contract.py", []),
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
    ("tools/build_residual_production_checkpoint_work_order.py", []),
    ("tools/build_residual_model_registry.py", []),
    ("tools/build_product_ai_architecture_execution_backlog.py", []),
    ("tools/build_product_ai_architecture_gap_closure.py", []),
    ("tools/build_goal_readiness_rollup.py", []),
    ("tools/build_goal_release_decision_gate.py", []),
    ("tools/build_product_goal_completion_audit.py", []),
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
    train_skipped = False
    if execute:
        for command, extra_args in POST_RETURN_STEPS:
            row = _run_step(command, extra_args)
            rows.append(row)
            if row["step_id"] == "train_residual_production_score_model" and row["ok"]:
                score = read_summary(read_json("runs/residual_production_score_model_current.json", root=ROOT))
                train_skipped = score.get("training_skipped") is True
            if not row["ok"]:
                break
    else:
        for command, extra_args in POST_RETURN_STEPS:
            rows.append(
                {
                    "step_id": Path(command).stem,
                    "command": command,
                    "extra_args": extra_args,
                    "execution_enabled": False,
                }
            )

    receipt = read_summary(read_json("runs/residual_force_gpu_worker_return_receipt_current.json", root=ROOT))
    registry = read_summary(read_json("runs/residual_model_registry_current.json", root=ROOT))
    goal = read_summary(read_json("runs/product_goal_completion_audit_current.json", root=ROOT))
    full = read_json("runs/residual_force_trajectory_regeneration_current_summary.json", root=ROOT)
    ok_rows = int(full.get("ok_rows") or 0)
    queue_rows = int(full.get("queue_rows") or 768)
    ready = (
        ok_rows >= queue_rows
        and receipt.get("gpu_worker_return_receipt_ready") is True
        and registry.get("checkpoint_preflight_ready") is True
        and (not execute or all(row.get("ok") for row in rows))
    )
    summary = {
        "packet_type": "product_gpu_return_post_regeneration_chain",
        "status": "product_gpu_return_post_regeneration_chain_ready" if ready else "blocked_product_gpu_return_post_regeneration_chain",
        "generated_at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).isoformat(),
        "execution_enabled": execute,
        "gpu_full_regeneration_ok_rows": ok_rows,
        "gpu_full_regeneration_queue_rows": queue_rows,
        "gpu_worker_return_receipt_ready": receipt.get("gpu_worker_return_receipt_ready"),
        "checkpoint_preflight_ready": registry.get("checkpoint_preflight_ready"),
        "score_model_training_skipped": train_skipped if execute else None,
        "goal_complete": goal.get("goal_complete"),
        "next_required_step": (
            "GPU return post-regeneration chain complete; run tools/build_product_e5_delivery_promotion_refresh_chain.py --execute."
            if ready
            else "Wait for full GPU regeneration (ok_rows=768), fill return manifest, then rerun with --execute."
        ),
    }
    return {"summary": summary, "rows": rows}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run GPU return post-regeneration validation and E4 checkpoint chain.")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--execute", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(execute=bool(args.execute))
    _write_json(args.out_json, payload)
    _resolve(args.out_md).write_text(
        f"# GPU Return Post-Regeneration Chain\n\n- status: `{payload['summary']['status']}`\n\n",
        encoding="utf-8",
    )
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
