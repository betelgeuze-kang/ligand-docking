#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import re
import statistics
from typing import Any, Dict, List, Optional, Sequence

import pandas as pd


RUN_RE = re.compile(r"(.+?)(?:_p(\d+))?_n(\d+)_r(\d+)_summary\.json$")


def _ensure_parent(path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)


def _read_json(path: str) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _parse_int_list(spec: str) -> List[int]:
    out: List[int] = []
    for tok in str(spec).split(","):
        tok = tok.strip()
        if not tok:
            continue
        try:
            out.append(int(tok))
        except Exception:
            continue
    return sorted(set(out))


def _discover_positive_counts(prefix: str) -> List[int]:
    out: List[int] = []
    for path in glob.glob(f"{prefix}_p*_n*_r*_summary.json"):
        m = RUN_RE.match(path)
        if not m:
            continue
        try:
            pos = int(m.group(2) or "0")
        except Exception:
            pos = 0
        out.append(pos)
    return sorted(set(out)) if out else [0]


def _to_float(v: Any) -> Optional[float]:
    try:
        x = float(v)
        return None if x != x else x
    except Exception:
        return None


def run_report(args: argparse.Namespace) -> Dict[str, Any]:
    prefix = str(args.prefix).strip()
    sizes = _parse_int_list(str(args.sizes))
    pos_counts = (
        _parse_int_list(str(args.positive_counts))
        if str(args.positive_counts).strip()
        else _discover_positive_counts(prefix)
    )
    repeats = int(max(args.repeats, 1))
    if not prefix:
        raise ValueError("--prefix is required")
    if not sizes:
        raise ValueError("--sizes is required")

    rows: List[Dict[str, Any]] = []
    expected = [(p, s, r) for p in pos_counts for s in sizes for r in range(1, repeats + 1)]
    for pos, size, rep in expected:
        path = f"{prefix}_p{pos}_n{size}_r{rep}_summary.json" if int(pos) > 0 else f"{prefix}_n{size}_r{rep}_summary.json"
        exists = os.path.exists(path)
        rec: Dict[str, Any] = {
            "positive_count_target": int(pos),
            "ligand_size": int(size),
            "repeat": int(rep),
            "summary_json": path,
            "exists": bool(exists),
            "pass": None,
            "failed_stage": "",
            "failed_metrics_count": None,
            "failed_metrics": "",
            "ranking_unique_auc": None,
            "ranking_ood_unique_auc": None,
            "ranking_row_auc_aux": None,
            "ranking_pr_auc": None,
            "ranking_ef1": None,
            "ranking_bedroc": None,
            "ranking_brier": None,
            "ranking_ece": None,
            "ranking_topk_hit_rate": None,
            "ranking_roc_auc_ci_low": None,
            "ranking_pr_auc_ci_low": None,
            "ranking_ef1_ci_low": None,
            "generated_at_local": "",
        }
        if exists:
            payload = _read_json(path)
            stage6 = ((payload.get("stages") or {}).get("stage6_operational_gate") or {})
            failed_metrics = stage6.get("failed_metrics") or []
            rec.update(
                {
                    "pass": bool(payload.get("pass", False)),
                    "failed_stage": str(payload.get("failed_stage", "")),
                    "failed_metrics_count": int(len(failed_metrics)) if isinstance(failed_metrics, list) else None,
                    "failed_metrics": json.dumps(failed_metrics, ensure_ascii=False) if isinstance(failed_metrics, list) else "",
                    "ranking_unique_auc": _to_float(stage6.get("ranking_unique_auc")),
                    "ranking_ood_unique_auc": _to_float(stage6.get("ranking_ood_unique_auc")),
                    "ranking_row_auc_aux": _to_float(stage6.get("ranking_row_auc_aux")),
                    "ranking_pr_auc": _to_float(stage6.get("ranking_pr_auc")),
                    "ranking_ef1": _to_float(stage6.get("ranking_ef1")),
                    "ranking_bedroc": _to_float(stage6.get("ranking_bedroc")),
                    "ranking_brier": _to_float(stage6.get("ranking_brier")),
                    "ranking_ece": _to_float(stage6.get("ranking_ece")),
                    "ranking_topk_hit_rate": _to_float(stage6.get("ranking_topk_hit_rate")),
                    "ranking_roc_auc_ci_low": _to_float(stage6.get("ranking_roc_auc_ci_low")),
                    "ranking_pr_auc_ci_low": _to_float(stage6.get("ranking_pr_auc_ci_low")),
                    "ranking_ef1_ci_low": _to_float(stage6.get("ranking_ef1_ci_low")),
                    "generated_at_local": str(payload.get("generated_at_local", "")),
                }
            )
        rows.append(rec)

    df = pd.DataFrame(rows).sort_values(["positive_count_target", "ligand_size", "repeat"]).reset_index(drop=True)
    done_df = df[df["exists"] == True].copy()  # noqa: E712

    size_summary_rows: List[Dict[str, Any]] = []
    for (pos, size), g in df.groupby(["positive_count_target", "ligand_size"]):
        row: Dict[str, Any] = {
            "positive_count_target": int(pos),
            "ligand_size": int(size),
            "completed_runs": int(g["exists"].sum()),
            "expected_runs": int(len(g)),
            "pass_runs": int(((g["pass"] == True) & (g["exists"] == True)).sum()),  # noqa: E712
            "fail_runs": int(((g["pass"] == False) & (g["exists"] == True)).sum()),  # noqa: E712
        }
        for col in [
            "ranking_unique_auc",
            "ranking_ood_unique_auc",
            "ranking_pr_auc",
            "ranking_ef1",
            "ranking_bedroc",
            "ranking_brier",
            "ranking_ece",
            "ranking_topk_hit_rate",
            "ranking_roc_auc_ci_low",
            "ranking_pr_auc_ci_low",
            "ranking_ef1_ci_low",
        ]:
            vals = [float(x) for x in g[col].dropna().tolist()]
            if vals:
                row[f"{col}_mean"] = float(statistics.mean(vals))
                row[f"{col}_min"] = float(min(vals))
                row[f"{col}_max"] = float(max(vals))
        size_summary_rows.append(row)

    size_df = pd.DataFrame(size_summary_rows).sort_values(["positive_count_target", "ligand_size"]).reset_index(drop=True)

    total_expected = int(len(expected))
    total_done = int(done_df.shape[0])
    total_pass = int(((done_df["pass"] == True)).sum()) if not done_df.empty else 0  # noqa: E712
    total_fail = int(((done_df["pass"] == False)).sum()) if not done_df.empty else 0  # noqa: E712
    progress_ratio = float(total_done / total_expected) if total_expected > 0 else 0.0

    final_summary_json = f"{prefix}_summary.json"
    final_summary_exists = os.path.exists(final_summary_json)
    final_summary = _read_json(final_summary_json) if final_summary_exists else {}

    report = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "prefix": prefix,
        "sizes": sizes,
        "positive_counts": pos_counts,
        "repeats": int(repeats),
        "progress": {
            "expected_runs": total_expected,
            "completed_runs": total_done,
            "pending_runs": int(max(0, total_expected - total_done)),
            "progress_ratio": progress_ratio,
            "pass_runs": total_pass,
            "fail_runs": total_fail,
        },
        "final_summary": {
            "exists": bool(final_summary_exists),
            "path": final_summary_json,
            "pass": final_summary.get("pass", None) if final_summary_exists else None,
            "failures": len(final_summary.get("failures", [])) if final_summary_exists else None,
        },
        "artifacts": {
            "runs_csv": str(args.out_runs_csv),
            "size_csv": str(args.out_size_csv),
            "summary_json": str(args.out_json),
            "summary_md": str(args.out_md),
        },
    }

    _ensure_parent(str(args.out_runs_csv))
    df.to_csv(str(args.out_runs_csv), index=False)
    _ensure_parent(str(args.out_size_csv))
    size_df.to_csv(str(args.out_size_csv), index=False)
    _ensure_parent(str(args.out_json))
    with open(str(args.out_json), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    md_lines: List[str] = [
        "# Ligand Stress Post Report",
        "",
        f"- generated_at_local: {report['generated_at_local']}",
        f"- prefix: `{prefix}`",
        f"- progress: {report['progress']}",
        f"- final_summary: {report['final_summary']}",
        "",
        "## Size Summary",
    ]
    if size_df.empty:
        md_lines.append("- no completed runs yet")
    else:
        for _, r in size_df.iterrows():
            md_lines.append(
                f"- p={int(r['positive_count_target'])} n={int(r['ligand_size'])}: "
                f"completed={int(r['completed_runs'])}/{int(r['expected_runs'])}, "
                f"pass={int(r['pass_runs'])}, fail={int(r['fail_runs'])}, "
                f"AUC={r.get('ranking_unique_auc_mean', None)}, "
                f"OOD_AUC={r.get('ranking_ood_unique_auc_mean', None)}, "
                f"ECE={r.get('ranking_ece_mean', None)}"
            )
    md_lines.extend(
        [
            "",
            f"- runs_csv: `{args.out_runs_csv}`",
            f"- size_csv: `{args.out_size_csv}`",
            f"- summary_json: `{args.out_json}`",
        ]
    )
    _ensure_parent(str(args.out_md))
    with open(str(args.out_md), "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines) + "\n")

    print(json.dumps(report, indent=2, ensure_ascii=False))
    return report


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Build post-run summary report from ligand stress run artifacts.")
    p.add_argument("--prefix", type=str, default="runs/ligand_stress_commercial_full")
    p.add_argument("--sizes", type=str, default="64,1000,5000,10000")
    p.add_argument("--positive-counts", type=str, default="")
    p.add_argument("--repeats", type=int, default=3)
    p.add_argument("--out-runs-csv", type=str, default="runs/ligand_stress_commercial_full_post_runs.csv")
    p.add_argument("--out-size-csv", type=str, default="runs/ligand_stress_commercial_full_post_sizes.csv")
    p.add_argument("--out-json", type=str, default="runs/ligand_stress_commercial_full_post_summary.json")
    p.add_argument("--out-md", type=str, default="runs/ligand_stress_commercial_full_post_summary.md")
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    run_report(args)


if __name__ == "__main__":
    main()
