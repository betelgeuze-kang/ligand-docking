#!/usr/bin/env python3
"""Batch internal GB/SA physics refinement over local stage3 score CSVs."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

from tools.product.build_refine_tier_residual_training_dataset import _refine_output_path


def _resolve(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else ROOT / p


def batch_refine_stage3_scores(
    *,
    stage3_glob: str,
    backend: str = "internal_gb_sa_v1",
    refinement_mode: str = "implicit_gb_sa_v1",
    refined_energy_col: str = "internal_refine_proxy_score",
    topk_global: int = 128,
    skip_existing: bool = True,
) -> dict[str, Any]:
    inputs = sorted(ROOT.glob(stage3_glob))
    rows: list[dict[str, Any]] = []
    for src in inputs:
        if "_refine_scores" in src.name:
            continue
        out_csv = _refine_output_path(src)
        if skip_existing and out_csv.exists() and out_csv.stat().st_mtime >= src.stat().st_mtime:
            rows.append(
                {
                    "input_csv": str(src),
                    "out_csv": str(out_csv),
                    "status": "skipped_existing",
                }
            )
            continue
        cmd = [
            sys.executable,
            str(ROOT / "tools/run_ligand_physics_refinement.py"),
            "--scores-csv",
            str(src),
            "--backend",
            str(backend),
            "--refinement-mode",
            str(refinement_mode),
            "--refined-energy-col",
            str(refined_energy_col),
            "--topk-global",
            str(int(topk_global)),
            "--out-csv",
            str(out_csv),
            "--out-json",
            str(out_csv.with_suffix(".summary.json")),
        ]
        proc = subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)
        ok = proc.returncode == 0
        rows.append(
            {
                "input_csv": str(src),
                "out_csv": str(out_csv),
                "status": "refined" if ok else "failed",
                "returncode": int(proc.returncode),
                "stderr_tail": "\n".join((proc.stderr or "").splitlines()[-8:]),
            }
        )
    refined = sum(1 for row in rows if row.get("status") == "refined")
    skipped = sum(1 for row in rows if row.get("status") == "skipped_existing")
    failed = sum(1 for row in rows if row.get("status") == "failed")
    return {
        "status": "batch_refine_stage3_ready" if failed == 0 else "blocked_batch_refine_stage3",
        "stage3_glob": stage3_glob,
        "input_count": len(inputs),
        "refined_count": refined,
        "skipped_existing_count": skipped,
        "failed_count": failed,
        "rows": rows,
    }


def main() -> None:
    p = argparse.ArgumentParser(description="Batch refine stage3 score CSVs with internal GB/SA backend.")
    p.add_argument("--stage3-glob", default="runs/ligand_htvs_nightly_*_stage3_scores.csv")
    p.add_argument("--backend", default="internal_gb_sa_v1")
    p.add_argument("--refinement-mode", default="implicit_gb_sa_v1")
    p.add_argument("--refined-energy-col", default="internal_refine_proxy_score")
    p.add_argument("--topk-global", type=int, default=128)
    p.add_argument("--no-skip-existing", action="store_true")
    args = p.parse_args()
    summary = batch_refine_stage3_scores(
        stage3_glob=args.stage3_glob,
        backend=args.backend,
        refinement_mode=args.refinement_mode,
        refined_energy_col=args.refined_energy_col,
        topk_global=int(args.topk_global),
        skip_existing=not bool(args.no_skip_existing),
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    if summary.get("failed_count"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
