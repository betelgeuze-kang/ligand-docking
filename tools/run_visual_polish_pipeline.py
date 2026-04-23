#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from typing import Any, Dict, List, Optional, Sequence


def _run_cmd(cmd: List[str]) -> Dict[str, Any]:
    proc = subprocess.run(cmd, text=True, capture_output=True)
    return {
        "cmd": cmd,
        "cmd_str": " ".join(cmd),
        "ok": bool(proc.returncode == 0),
        "returncode": int(proc.returncode),
        "stdout_tail": "\n".join((proc.stdout or "").splitlines()[-40:]),
        "stderr_tail": "\n".join((proc.stderr or "").splitlines()[-40:]),
    }


def run(args: argparse.Namespace) -> Dict[str, Any]:
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs(os.path.dirname(args.out_summary_json) or ".", exist_ok=True)

    refined_csv = str(args.refined_report_csv).strip() or f"runs/visual_refined_report_{ts}.csv"
    refined_json = str(args.refined_summary_json).strip() or f"runs/visual_refined_summary_{ts}.json"
    chimerax_csv = str(args.chimerax_report_csv).strip() or f"runs/chimerax_render_report_{ts}.csv"
    chimerax_json = str(args.chimerax_summary_json).strip() or f"runs/chimerax_render_summary_{ts}.json"

    post_cmd: List[str] = [
        sys.executable,
        "tools/postprocess_structure_visuals.py",
        "--out-dir",
        str(args.processed_internal_dir),
        "--out-csv",
        refined_csv,
        "--out-json",
        refined_json,
        "--smooth-window",
        str(int(args.smooth_window)),
        "--secondary-structure-mode",
        str(args.secondary_structure_mode),
        "--visual-residual-lambda",
        str(float(args.visual_residual_lambda)),
        "--visual-residual-iters",
        str(int(args.visual_residual_iters)),
        "--target-ca-distance",
        str(float(args.target_ca_distance)),
        "--residual-bfactor-weight",
        str(float(args.residual_bfactor_weight)),
        "--ss-vote-min-fraction",
        str(float(args.ss_vote_min_fraction)),
        "--ss-vote-min-frames",
        str(int(args.ss_vote_min_frames)),
        "--align" if bool(args.align) else "--no-align",
        "--pseudo-backbone" if bool(args.pseudo_backbone) else "--no-pseudo-backbone",
        "--ss-temporal-vote" if bool(args.ss_temporal_vote) else "--no-ss-temporal-vote",
    ]
    for p in args.internal_pdb:
        post_cmd.extend(["--in-pdb", str(p)])
    for g in args.internal_pdb_glob:
        post_cmd.extend(["--in-glob", str(g)])
    post_rec = _run_cmd(post_cmd)
    if not bool(post_rec.get("ok", False)):
        summary = {
            "ok": False,
            "failed_stage": "postprocess_structure_visuals",
            "stages": {"postprocess": post_rec},
        }
        with open(args.out_summary_json, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        return summary

    chimerax_rec: Dict[str, Any] = {
        "requested": bool(args.run_chimerax),
        "ok": True,
        "returncode": 0,
    }
    if bool(args.run_chimerax):
        c_cmd: List[str] = [
            sys.executable,
            "tools/render_chimerax_movies.py",
            "--pdb-glob",
            os.path.join(str(args.processed_internal_dir), "*.pdb"),
            "--out-dir",
            str(args.chimerax_out_dir),
            "--out-csv",
            chimerax_csv,
            "--out-json",
            chimerax_json,
            "--fps",
            str(int(args.chimerax_fps)),
            "--turn-steps",
            str(int(args.chimerax_turn_steps)),
            "--chimerax-bin",
            str(args.chimerax_bin),
            "--execute" if bool(args.chimerax_execute) else "--no-execute",
            "--fail-on-missing" if bool(args.chimerax_fail_on_missing) else "--no-fail-on-missing",
        ]
        chimerax_rec = _run_cmd(c_cmd)
        if not bool(chimerax_rec.get("ok", False)):
            summary = {
                "ok": False,
                "failed_stage": "chimerax_render",
                "stages": {
                    "postprocess": post_rec,
                    "chimerax": chimerax_rec,
                },
                "artifacts": {
                    "refined_report_csv": refined_csv,
                    "refined_summary_json": refined_json,
                    "chimerax_report_csv": chimerax_csv,
                    "chimerax_summary_json": chimerax_json,
                },
            }
            with open(args.out_summary_json, "w", encoding="utf-8") as f:
                json.dump(summary, f, indent=2, ensure_ascii=False)
            return summary

    movie_json_inputs: List[str] = []
    movie_csv_inputs: List[str] = []
    for x in getattr(args, "dashboard_movie_json", []) or []:
        tok = str(x).strip()
        if tok:
            movie_json_inputs.append(tok)
    for x in getattr(args, "dashboard_movie_csv", []) or []:
        tok = str(x).strip()
        if tok:
            movie_csv_inputs.append(tok)
    if bool(args.run_chimerax):
        if os.path.exists(chimerax_json):
            movie_json_inputs.append(chimerax_json)
        if os.path.exists(chimerax_csv):
            movie_csv_inputs.append(chimerax_csv)

    uniq_movie_json: List[str] = []
    seen_json = set()
    for p in movie_json_inputs:
        ap = os.path.abspath(str(p))
        if ap in seen_json:
            continue
        seen_json.add(ap)
        if os.path.isfile(ap):
            uniq_movie_json.append(ap)

    uniq_movie_csv: List[str] = []
    seen_csv = set()
    for p in movie_csv_inputs:
        ap = os.path.abspath(str(p))
        if ap in seen_csv:
            continue
        seen_csv.add(ap)
        if os.path.isfile(ap):
            uniq_movie_csv.append(ap)

    dash_cmd: List[str] = [
        sys.executable,
        "tools/visualize_experiment_dashboard.py",
        "--csv",
        str(args.feature_csv),
        "--metrics",
        str(args.dashboard_metrics),
        "--max-metrics",
        str(int(args.dashboard_max_metrics)),
        "--max-rows",
        str(int(args.dashboard_max_rows)),
        "--max-pdb",
        str(int(args.dashboard_max_pdb)),
        "--viewer-engine",
        str(args.viewer_engine),
        "--target-col",
        str(args.dashboard_target_col),
        "--title",
        str(args.dashboard_title),
        "--out-html",
        str(args.dashboard_html),
        "--out-json",
        str(args.dashboard_json),
        "--pdb-glob",
        os.path.join(str(args.processed_internal_dir), "*.pdb"),
    ]
    if str(args.gate_json).strip():
        dash_cmd.extend(["--gate-json", str(args.gate_json)])
    for g in args.external_pdb_glob:
        dash_cmd.extend(["--pdb-glob", str(g)])
    for p in args.external_pdb:
        dash_cmd.extend(["--pdb", str(p)])
    for p in uniq_movie_json:
        dash_cmd.extend(["--movie-json", str(p)])
    for p in uniq_movie_csv:
        dash_cmd.extend(["--movie-csv", str(p)])

    dash_rec = _run_cmd(dash_cmd)
    if not bool(dash_rec.get("ok", False)):
        summary = {
            "ok": False,
            "failed_stage": "visualize_experiment_dashboard",
            "stages": {
                "postprocess": post_rec,
                "dashboard": dash_rec,
                "chimerax": chimerax_rec,
            },
        }
        with open(args.out_summary_json, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        return summary

    ok = bool(post_rec.get("ok", False) and dash_rec.get("ok", False) and chimerax_rec.get("ok", True))
    summary = {
        "ok": ok,
        "failed_stage": None if ok else (
            "chimerax_render" if not bool(chimerax_rec.get("ok", True)) else None
        ),
        "stages": {
            "postprocess": post_rec,
            "dashboard": dash_rec,
            "chimerax": chimerax_rec,
        },
        "artifacts": {
            "refined_report_csv": refined_csv,
            "refined_summary_json": refined_json,
            "dashboard_html": str(args.dashboard_html),
            "dashboard_json": str(args.dashboard_json),
            "chimerax_report_csv": chimerax_csv if bool(args.run_chimerax) else "",
            "chimerax_summary_json": chimerax_json if bool(args.run_chimerax) else "",
            "dashboard_movie_json": uniq_movie_json,
            "dashboard_movie_csv": uniq_movie_csv,
        },
    }
    with open(args.out_summary_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    return summary


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Apply visual polish pipeline: refine PDB -> Mol* dashboard -> ChimeraX render.")
    p.add_argument("--feature-csv", type=str, required=True)
    p.add_argument("--gate-json", type=str, default="")
    p.add_argument("--internal-pdb", action="append", default=[])
    p.add_argument("--internal-pdb-glob", action="append", default=[])
    p.add_argument("--external-pdb", action="append", default=[])
    p.add_argument("--external-pdb-glob", action="append", default=[])
    p.add_argument("--processed-internal-dir", type=str, required=True)
    p.add_argument("--smooth-window", type=int, default=3)
    p.add_argument(
        "--secondary-structure-mode",
        type=str,
        choices=["auto", "dssp", "heuristic"],
        default="auto",
    )
    p.add_argument("--visual-residual-lambda", type=float, default=0.12)
    p.add_argument("--visual-residual-iters", type=int, default=2)
    p.add_argument("--target-ca-distance", type=float, default=3.8)
    p.add_argument("--residual-bfactor-weight", type=float, default=0.25)
    p.add_argument("--pseudo-backbone", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--ss-temporal-vote", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--ss-vote-min-fraction", type=float, default=0.60)
    p.add_argument("--ss-vote-min-frames", type=int, default=3)
    p.add_argument("--align", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--dashboard-html", type=str, required=True)
    p.add_argument("--dashboard-json", type=str, required=True)
    p.add_argument("--dashboard-title", type=str, default="MD Experiment Dashboard")
    p.add_argument("--dashboard-target-col", type=str, default="target")
    p.add_argument("--dashboard-metrics", type=str, default="auto")
    p.add_argument("--dashboard-max-metrics", type=int, default=12)
    p.add_argument("--dashboard-max-rows", type=int, default=2000)
    p.add_argument("--dashboard-max-pdb", type=int, default=24)
    p.add_argument("--dashboard-movie-json", action="append", default=[])
    p.add_argument("--dashboard-movie-csv", action="append", default=[])
    p.add_argument("--viewer-engine", type=str, choices=["auto", "3dmol", "molstar"], default="3dmol")
    p.add_argument("--run-chimerax", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--chimerax-out-dir", type=str, default="runs/chimerax_movies")
    p.add_argument("--chimerax-bin", type=str, default="chimerax")
    p.add_argument("--chimerax-fps", type=int, default=30)
    p.add_argument("--chimerax-turn-steps", type=int, default=360)
    p.add_argument("--chimerax-execute", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--chimerax-fail-on-missing", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--refined-report-csv", type=str, default="")
    p.add_argument("--refined-summary-json", type=str, default="")
    p.add_argument("--chimerax-report-csv", type=str, default="")
    p.add_argument("--chimerax-summary-json", type=str, default="")
    p.add_argument("--out-summary-json", type=str, default="runs/visual_polish_pipeline_summary.json")
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    summary = run(args)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    if not bool(summary.get("ok", False)):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
