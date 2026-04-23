#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
from typing import Any, Dict, List, Optional, Sequence

import pandas as pd

from benchmark.performance_bench import benchmark_simulation
from core.definitions import ResearchConstants


VALID_RUNTIME_MODES = ("eager", "scripted", "compiled", "onnx")


def _parse_targets(raw: str) -> List[str]:
    token = str(raw or "").strip()
    if not token or token.lower() in ("all", "noncyclic"):
        return list(ResearchConstants.CHALLENGES.keys())
    return [x.strip() for x in token.split(",") if x.strip()]


def _parse_modes(raw: str) -> List[str]:
    token = str(raw or "").strip().lower()
    if not token:
        return ["eager", "scripted", "compiled", "onnx"]
    out: List[str] = []
    for item in token.split(","):
        m = str(item).strip().lower()
        if m in VALID_RUNTIME_MODES and m not in out:
            out.append(m)
    return out or ["eager", "scripted"]


def _safe_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except Exception:
        return None


def build_mode_summary(rows_df: pd.DataFrame) -> Dict[str, Any]:
    if rows_df.empty:
        return {
            "best_mode": None,
            "best_median_throughput_steps_per_sec": None,
            "modes": [],
        }

    modes_summary: List[Dict[str, Any]] = []
    for mode, sub in rows_df.groupby("runtime_mode"):
        throughputs = pd.to_numeric(sub["throughput_steps_per_sec"], errors="coerce")
        err_count = int(sub["runtime_error"].fillna("").astype(str).str.len().gt(0).sum())
        modes_summary.append(
            {
                "runtime_mode": str(mode),
                "rows": int(len(sub)),
                "median_throughput_steps_per_sec": _safe_float(throughputs.median()),
                "mean_throughput_steps_per_sec": _safe_float(throughputs.mean()),
                "runtime_error_rows": err_count,
                "all_rows_error_free": bool(err_count == 0),
            }
        )

    modes_summary.sort(
        key=lambda row: (
            0 if bool(row["all_rows_error_free"]) else 1,
            -float(row["median_throughput_steps_per_sec"] or 0.0),
        )
    )
    best = modes_summary[0] if modes_summary else None
    return {
        "best_mode": None if best is None else best["runtime_mode"],
        "best_median_throughput_steps_per_sec": None
        if best is None
        else best["median_throughput_steps_per_sec"],
        "modes": modes_summary,
    }


def run_profile(args: argparse.Namespace) -> Dict[str, Any]:
    targets = _parse_targets(args.targets)
    modes = _parse_modes(args.modes)
    ai_ckpt = str(getattr(args, "ai_router_checkpoint", "")).strip() or None
    rows: List[Dict[str, Any]] = []

    for target in targets:
        for mode in modes:
            result = benchmark_simulation(
                target=target,
                steps=int(args.steps),
                use_ai_router=True,
                num_runs=int(args.runs),
                warmup_steps=int(args.warmup_steps),
                batch_replicas=int(args.batch_replicas),
                ai_interval=int(args.ai_interval),
                ai_runtime_mode=str(mode),
                ai_disable_exploration=bool(args.ai_disable_exploration),
                ai_use_hip_graph=bool(args.ai_use_hip_graph),
                ai_graph_warmup_iters=int(args.ai_graph_warmup_iters),
                ai_router_checkpoint=ai_ckpt,
                ai_router_checkpoint_strict=bool(getattr(args, "ai_router_checkpoint_strict", False)),
                profile_components=bool(args.profile_components),
                sample_gpu_metrics=bool(args.sample_gpu_metrics),
                output_file="",
            )
            rows.append(
                {
                    "target": str(target),
                    "runtime_mode": str(mode),
                    "throughput_steps_per_sec": _safe_float(result.get("avg_throughput_steps_per_sec")),
                    "step_ms": _safe_float(result.get("avg_time_per_step_ms")),
                    "ai_calls_per_run": _safe_float(result.get("avg_ai_inference_calls_per_run")),
                    "ai_reuse_steps_per_run": _safe_float(result.get("avg_ai_reuse_steps_per_run")),
                    "runtime_error": str(result.get("ai_router_script_error") or "").strip(),
                }
            )

    df = pd.DataFrame(rows)
    summary = build_mode_summary(df)
    payload = {
        "summary": summary,
        "targets": targets,
        "modes": modes,
        "steps": int(args.steps),
        "runs": int(args.runs),
        "warmup_steps": int(args.warmup_steps),
        "batch_replicas": int(args.batch_replicas),
        "ai_interval": int(args.ai_interval),
    }

    out_csv = str(args.out_csv).strip()
    out_json = str(args.out_json).strip()
    os.makedirs(os.path.dirname(out_csv) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(out_json) or ".", exist_ok=True)
    df.to_csv(out_csv, index=False)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return {"summary": summary, "out_csv": out_csv, "out_json": out_json}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Profile AIRouter runtime modes and recommend release default mode.",
    )
    p.add_argument("--targets", type=str, default="noncyclic")
    p.add_argument("--modes", type=str, default="eager,scripted,compiled,onnx")
    p.add_argument("--steps", type=int, default=80)
    p.add_argument("--runs", type=int, default=1)
    p.add_argument("--warmup-steps", type=int, default=30)
    p.add_argument("--batch-replicas", type=int, default=1)
    p.add_argument("--ai-interval", type=int, default=4)
    p.add_argument("--ai-disable-exploration", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--ai-use-hip-graph", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--ai-graph-warmup-iters", type=int, default=2)
    p.add_argument("--profile-components", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--sample-gpu-metrics", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--ai-router-checkpoint", type=str, default="")
    p.add_argument(
        "--ai-router-checkpoint-strict",
        action=argparse.BooleanOptionalAction,
        default=False,
    )
    p.add_argument("--out-csv", type=str, default="runs/ai_runtime_mode_profile.csv")
    p.add_argument("--out-json", type=str, default="runs/ai_runtime_mode_profile.json")
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    out = run_profile(args)
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
