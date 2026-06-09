#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import numpy as np

from tools.run_ligand_backmapping_scoring import _frame_mmpbsa_proxy, _frame_mmpbsa_proxy_batch

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/backmapping_scoring_batch_smoke_benchmark_current.json"
DEFAULT_OUT_MD = "runs/backmapping_scoring_batch_smoke_benchmark_current.md"

CLAIM_BOUNDARY = (
    "Backmapping scoring batch smoke benchmark only; measures local batch vectorization throughput on a small "
    "synthetic fixture. It does not rerun docking, mutate rankings, or claim production SLA."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def run_smoke_benchmark(*, frame_count: int = 32, repeats: int = 5) -> dict[str, Any]:
    rng = np.random.default_rng(0)
    protein_xyz = rng.normal(size=(48, 3)).astype(np.float32)
    ligand_frames_xyz = rng.normal(size=(frame_count, 2, 3)).astype(np.float32)
    props = {"affinity_hint": 0.6, "polar_norm": 0.4, "logp_norm": 0.3, "onsps_norm": 0.2}
    loop_seconds = 0.0
    for _ in range(repeats):
        start = time.perf_counter()
        for frame in ligand_frames_xyz:
            _frame_mmpbsa_proxy(
                protein_xyz=protein_xyz,
                ligand_xyz=frame,
                props=props,
                contact_cutoff_A=8.0,
                ligand_model="2bead",
            )
        loop_seconds += time.perf_counter() - start
    batch_seconds = 0.0
    for _ in range(repeats):
        start = time.perf_counter()
        _frame_mmpbsa_proxy_batch(
            protein_xyz=protein_xyz,
            ligand_frames_xyz=ligand_frames_xyz,
            props=props,
            contact_cutoff_A=8.0,
            ligand_model="2bead",
        )
        batch_seconds += time.perf_counter() - start
    loop_frames_per_sec = float(frame_count * repeats / max(loop_seconds, 1e-9))
    batch_frames_per_sec = float(frame_count * repeats / max(batch_seconds, 1e-9))
    speedup_ratio = float(batch_frames_per_sec / max(loop_frames_per_sec, 1e-9))
    ready = batch_frames_per_sec > 0.0 and speedup_ratio >= 1.0
    summary = {
        "packet_type": "backmapping_scoring_batch_smoke_benchmark",
        "status": "backmapping_scoring_batch_smoke_benchmark_ready" if ready else "blocked_backmapping_scoring_batch_smoke_benchmark",
        "claim_boundary": CLAIM_BOUNDARY,
        "frame_count": frame_count,
        "repeat_count": repeats,
        "loop_frames_per_sec": loop_frames_per_sec,
        "batch_frames_per_sec": batch_frames_per_sec,
        "speedup_ratio": speedup_ratio,
        "benchmark_ready": ready,
        "execution_enabled": True,
        "benchmark_executed": True,
        "external_state_mutated": False,
        "next_required_step": (
            "Attach this smoke benchmark to the ROCm end-to-end benchmark summary as a vectorization guard."
            if ready
            else "Investigate backmapping batch vectorization regression on the synthetic fixture."
        ),
    }
    return {"summary": summary}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a small backmapping batch vectorization smoke benchmark.")
    parser.add_argument("--frame-count", type=int, default=32)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = run_smoke_benchmark(frame_count=args.frame_count, repeats=args.repeats)
    _write_json(args.out_json, payload)
    summary = payload["summary"]
    _resolve(args.out_md).write_text(
        "\n".join(
            [
                "# Backmapping Scoring Batch Smoke Benchmark",
                "",
                f"- status: `{summary['status']}`",
                f"- batch_frames_per_sec: `{summary['batch_frames_per_sec']:.3f}`",
                f"- loop_frames_per_sec: `{summary['loop_frames_per_sec']:.3f}`",
                f"- speedup_ratio: `{summary['speedup_ratio']:.3f}`",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
