#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_EVAL_CONFIG_JSON = "runs/idp_3bead_holdout_v7_literature_anchor_kfshadow_r1_fold_inputs/fold6_tau_k18_eval.json"
DEFAULT_BASELINE_GATE_JSON = "runs/idp_3bead_holdout_v7_literature_anchor_kfshadow_r1_fold6_tau_k18_gate_baseline_summary.json"
DEFAULT_OUT_PREFIX = "runs/idp_tau_k18_baseline_shadow_replay_current"


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _run(cmd: list[str]) -> dict[str, Any]:
    p = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
    return {
        "cmd": cmd,
        "rc": int(p.returncode),
        "stdout_tail": "\n".join((p.stdout or "").splitlines()[-20:]),
        "stderr_tail": "\n".join((p.stderr or "").splitlines()[-20:]),
    }


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Run a tau_k18 baseline-only Kalman shadow replay.")
    p.add_argument("--eval-config-json", default=DEFAULT_EVAL_CONFIG_JSON)
    p.add_argument("--baseline-gate-json", default=DEFAULT_BASELINE_GATE_JSON)
    p.add_argument("--out-prefix", default=DEFAULT_OUT_PREFIX)
    p.add_argument("--device", default="cuda")
    p.add_argument("--kalman-shadow-enable", type=int, default=1)
    p.add_argument("--kalman-shadow-mode", default="feature_state_v1")
    p.add_argument("--kalman-shadow-family-token", default="idp")
    p.add_argument("--kalman-shadow-obs-noise-scale", type=float, default=0.15)
    p.add_argument("--kalman-shadow-process-noise-scale", type=float, default=0.03)
    p.add_argument("--kalman-shadow-delta-cap-frac", type=float, default=0.25)
    p.add_argument("--kalman-shadow-feature-mask", default="ensemble_only")
    return p


def main() -> int:
    args = build_parser().parse_args()
    out_prefix = str(_resolve(args.out_prefix))
    eval_prefix = f"{out_prefix}_eval_baseline"
    eval_json = f"{eval_prefix}_summary.json"
    gate_json = f"{out_prefix}_gate_baseline_summary.json"
    gate_md = f"{out_prefix}_gate_baseline_summary.md"
    summary_json = f"{out_prefix}_summary.json"
    summary_md = f"{out_prefix}_summary.md"

    eval_cmd = [
        sys.executable, str(ROOT / "tools" / "run_idp_3bead_evaluator.py"),
        "--config-json", str(_resolve(args.eval_config_json)),
        "--device", str(args.device),
        "--date-tag", "tau-k18-baseline-shadow-replay",
        "--out-prefix", eval_prefix,
        "--kalman-shadow-enable", str(args.kalman_shadow_enable),
        "--kalman-shadow-mode", str(args.kalman_shadow_mode),
        "--kalman-shadow-family-token", str(args.kalman_shadow_family_token),
        "--kalman-shadow-obs-noise-scale", str(args.kalman_shadow_obs_noise_scale),
        "--kalman-shadow-process-noise-scale", str(args.kalman_shadow_process_noise_scale),
        "--kalman-shadow-delta-cap-frac", str(args.kalman_shadow_delta_cap_frac),
        "--kalman-shadow-feature-mask", str(args.kalman_shadow_feature_mask),
    ]
    eval_status = _run(eval_cmd)
    if eval_status["rc"] != 0:
        Path(summary_json).write_text(json.dumps({"pass": False, "stage": "eval", "status": eval_status}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return int(eval_status["rc"])

    gate_cmd = [
        sys.executable, str(ROOT / "tools" / "run_idp_3bead_benchmark_gate.py"),
        "--config-json", str(_resolve(args.eval_config_json)),
        "--eval-json", eval_json,
        "--out-json", gate_json,
        "--out-md", gate_md,
    ]
    gate_status = _run(gate_cmd)

    baseline_gate = _read_json(_resolve(args.baseline_gate_json))
    replay_gate = _read_json(Path(gate_json))
    eval_payload = _read_json(Path(eval_json))
    kalman = dict(eval_payload.get("kalman_shadow", {}) or {})

    summary = {
        "pass": bool(replay_gate.get("pass", False)),
        "eval_status": eval_status,
        "gate_status": gate_status,
        "feature_mask": str(args.kalman_shadow_feature_mask),
        "baseline_gate_pass": baseline_gate.get("pass"),
        "replay_gate_pass": replay_gate.get("pass"),
        "baseline_dominant_state_accuracy": (baseline_gate.get("classification_metrics", {}) or {}).get("dominant_state_accuracy"),
        "replay_dominant_state_accuracy": (replay_gate.get("classification_metrics", {}) or {}).get("dominant_state_accuracy"),
        "kalman_shadow": kalman,
        "eval_json": eval_json,
        "gate_json": gate_json,
    }
    Path(summary_json).write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    Path(summary_md).write_text(
        "\n".join(
            [
                "# Tau K18 Baseline Shadow Replay",
                "",
                f"- pass: `{summary['pass']}`",
                f"- feature_mask: `{summary['feature_mask']}`",
                f"- baseline_gate_pass: `{summary['baseline_gate_pass']}`",
                f"- replay_gate_pass: `{summary['replay_gate_pass']}`",
                f"- baseline_dominant_state_accuracy: `{summary['baseline_dominant_state_accuracy']}`",
                f"- replay_dominant_state_accuracy: `{summary['replay_dominant_state_accuracy']}`",
                f"- would_change_state_count: `{kalman.get('would_change_state_count')}`",
                f"- would_change_gate_count: `{kalman.get('would_change_gate_count')}`",
                f"- eval_json: `{summary['eval_json']}`",
                f"- gate_json: `{summary['gate_json']}`",
            ]
        ) + "\n",
        encoding="utf-8",
    )
    return int(gate_status["rc"])


if __name__ == "__main__":
    raise SystemExit(main())
