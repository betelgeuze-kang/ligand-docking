#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from typing import Any, Dict, List, Optional, Sequence

import pandas as pd

TOPK_SELECTION_MODES = {"union", "global_only", "per_target_only"}


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _pick_score_col(df: pd.DataFrame, requested: str) -> Optional[str]:
    req = str(requested).strip()
    if req and req in df.columns:
        return req
    candidates = [
        "binding_score_composite_v3",
        "binding_score_composite_v2",
        "binding_energy_mmpbsa_kcal_mol_calibrated",
        "binding_energy_mmpbsa_kcal_mol_proxy",
        "binding_energy_proxy",
    ]
    for col in candidates:
        if col in df.columns:
            return col
    return None


def _normalize_selection_mode(value: Any) -> str:
    raw = str(value or "").strip().lower().replace("-", "_")
    aliases = {
        "": "union",
        "all": "union",
        "both": "union",
        "global": "global_only",
        "per_target": "per_target_only",
        "pertarget": "per_target_only",
    }
    mode = aliases.get(raw, raw)
    if mode not in TOPK_SELECTION_MODES:
        raise ValueError(f"unsupported top-k selection mode: {value}")
    return mode


def _per_target_head(work: pd.DataFrame, topk_per_target: int) -> pd.DataFrame:
    if int(topk_per_target) <= 0 or "target" not in work.columns:
        return work.head(0).copy()
    return (
        work.groupby("target", sort=False, group_keys=False)
        .head(int(topk_per_target))
        .reset_index(drop=True)
        .copy()
    )


def _dedupe_selected(selected: pd.DataFrame, score_col: str) -> pd.DataFrame:
    if selected.empty:
        return selected.copy()
    out = selected.copy()
    if "queue_id" in out.columns:
        out = out.drop_duplicates(subset=["queue_id"], keep="first")
    elif {"target", "ligand_id"}.issubset(out.columns):
        out = out.drop_duplicates(subset=["target", "ligand_id"], keep="first")
    else:
        out = out.drop_duplicates(keep="first")
    out = out.sort_values(score_col, ascending=True).reset_index(drop=True)
    out["delivery_rank"] = out.index + 1
    return out


def _select_topk(
    df: pd.DataFrame,
    score_col: str,
    topk_global: int,
    topk_per_target: int,
    selection_mode: str,
) -> tuple[pd.DataFrame, Dict[str, Any]]:
    mode = _normalize_selection_mode(selection_mode)
    work = df.copy()
    work[score_col] = pd.to_numeric(work[score_col], errors="coerce")
    work = work[work[score_col].notna()].copy()
    work = work.sort_values(score_col, ascending=True).reset_index(drop=True)
    if work.empty:
        return work, {
            "requested_mode": mode,
            "applied_mode": mode,
            "global_selected_rows": 0,
            "per_target_selected_rows": 0,
            "has_target_column": bool("target" in df.columns),
        }

    global_selected = work.head(int(topk_global)).copy() if int(topk_global) > 0 else work.head(0).copy()
    per_target_selected = _per_target_head(work, int(topk_per_target))
    if mode == "global_only":
        selected = global_selected.copy()
    elif mode == "per_target_only":
        selected = per_target_selected.copy()
    else:
        parts: List[pd.DataFrame] = []
        if not global_selected.empty:
            parts.append(global_selected)
        if not per_target_selected.empty:
            parts.append(per_target_selected)
        selected = pd.concat(parts, axis=0, ignore_index=True) if parts else work.head(0).copy()

    selected = _dedupe_selected(selected, score_col)
    return selected, {
        "requested_mode": mode,
        "applied_mode": mode,
        "global_selected_rows": int(len(global_selected)),
        "per_target_selected_rows": int(len(per_target_selected)),
        "has_target_column": bool("target" in work.columns),
    }


def _filter_queue(queue_df: pd.DataFrame, selected_df: pd.DataFrame) -> pd.DataFrame:
    if "queue_id" in queue_df.columns and "queue_id" in selected_df.columns:
        keys = set(selected_df["queue_id"].astype(str).tolist())
        out = queue_df[queue_df["queue_id"].astype(str).isin(keys)].copy()
        return out
    if {"target", "ligand_id"}.issubset(queue_df.columns) and {"target", "ligand_id"}.issubset(selected_df.columns):
        sel_keys = set(zip(selected_df["target"].astype(str), selected_df["ligand_id"].astype(str)))
        mask = [
            (str(t), str(l)) in sel_keys
            for t, l in zip(queue_df["target"].astype(str).tolist(), queue_df["ligand_id"].astype(str).tolist())
        ]
        return queue_df[pd.Series(mask, index=queue_df.index)].copy()
    raise ValueError("unable to match selected rows back to queue csv")


def _run(cmd: List[str]) -> Dict[str, Any]:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return {
        "ok": proc.returncode == 0,
        "returncode": int(proc.returncode),
        "cmd": cmd,
        "stdout_tail": "\n".join((proc.stdout or "").splitlines()[-20:]),
        "stderr_tail": "\n".join((proc.stderr or "").splitlines()[-40:]),
    }


def build_delivery(args: argparse.Namespace) -> Dict[str, Any]:
    scores_csv = str(args.scores_csv).strip()
    queue_csv = str(args.queue_csv).strip()
    if (not scores_csv) or (not os.path.exists(scores_csv)):
        raise FileNotFoundError(f"scores csv not found: {scores_csv}")
    if (not queue_csv) or (not os.path.exists(queue_csv)):
        raise FileNotFoundError(f"queue csv not found: {queue_csv}")

    out_prefix = str(args.out_prefix).strip() or "runs/ligand_topk_delivery"
    _ensure_dir(os.path.dirname(out_prefix) or ".")

    scores_df = pd.read_csv(scores_csv)
    queue_df = pd.read_csv(queue_csv)
    score_col = _pick_score_col(scores_df, str(args.score_col))
    if score_col is None:
        raise ValueError(f"no score column found in {scores_csv}")

    selected_scores, selection_meta = _select_topk(
        scores_df,
        score_col=score_col,
        topk_global=int(max(0, int(args.topk_global))),
        topk_per_target=int(max(0, int(args.topk_per_target))),
        selection_mode=str(args.selection_mode),
    )
    if selected_scores.empty:
        raise ValueError("top-k selection produced no rows")
    selected_queue = _filter_queue(queue_df, selected_scores)
    if selected_queue.empty:
        raise ValueError("filtered queue is empty after top-k selection")

    selected_scores_csv = f"{out_prefix}_selected_scores.csv"
    selected_queue_csv = f"{out_prefix}_selected_queue.csv"
    selected_scores.to_csv(selected_scores_csv, index=False)
    selected_queue.to_csv(selected_queue_csv, index=False)

    delivery_out_dir = f"{out_prefix}_delivery"
    cmd = [
        sys.executable,
        "tools/run_ligand_backmapping_scoring.py",
        "--queue-csv",
        selected_queue_csv,
        "--trajectory-root",
        str(args.trajectory_root),
        "--trajectory-glob",
        str(args.trajectory_glob),
        "--contact-cutoff-A",
        str(float(args.contact_cutoff_A)),
        "--min-frames",
        str(int(args.min_frames)),
        "--workers",
        str(int(max(0, int(args.workers)))),
        "--parallel-threshold",
        str(int(max(1, int(args.parallel_threshold)))),
        "--out-dir",
        delivery_out_dir,
        "--out-scores-csv",
        f"{out_prefix}_delivery_scores.csv",
        "--out-summary-json",
        f"{out_prefix}_delivery_summary.json",
        "--out-summary-md",
        f"{out_prefix}_delivery_summary.md",
        "--no-score-only",
        "--make-bundle-zip" if bool(args.make_bundle_zip) else "--no-make-bundle-zip",
    ]
    rec = _run(cmd)

    payload: Dict[str, Any] = {
        "ok": bool(rec["ok"]),
        "scores_csv": scores_csv,
        "queue_csv": queue_csv,
        "score_col": score_col,
        "topk_global": int(args.topk_global),
        "topk_per_target": int(args.topk_per_target),
        "selection_mode_requested": selection_meta.get("requested_mode"),
        "selection_mode_applied": selection_meta.get("applied_mode"),
        "selection_components": {
            "global_selected_rows": int(selection_meta.get("global_selected_rows", 0) or 0),
            "per_target_selected_rows": int(selection_meta.get("per_target_selected_rows", 0) or 0),
            "has_target_column": bool(selection_meta.get("has_target_column", False)),
        },
        "selected_rows": int(len(selected_scores)),
        "selected_targets": int(selected_scores["target"].nunique()) if "target" in selected_scores.columns else None,
        "selected_queue_csv": selected_queue_csv,
        "selected_scores_csv": selected_scores_csv,
        "delivery_cmd": cmd,
        "delivery_run": rec,
        "artifacts": {
            "delivery_out_dir": delivery_out_dir,
            "delivery_scores_csv": f"{out_prefix}_delivery_scores.csv",
            "delivery_summary_json": f"{out_prefix}_delivery_summary.json",
            "delivery_summary_md": f"{out_prefix}_delivery_summary.md",
        },
    }
    if bool(args.make_bundle_zip):
        payload["artifacts"]["delivery_bundle_zip"] = os.path.join(delivery_out_dir, "ligand_delivery_bundle.zip")

    out_json = f"{out_prefix}_summary.json"
    out_md = f"{out_prefix}_summary.md"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    lines = [
        "# Ligand Top-K Delivery",
        "",
        f"- ok: {bool(payload['ok'])}",
        f"- score_col: {score_col}",
        f"- selection_mode: {payload.get('selection_mode_applied')}",
        f"- selected_rows: {int(payload['selected_rows'])}",
        f"- selected_targets: {payload.get('selected_targets')}",
        f"- selected_queue_csv: `{selected_queue_csv}`",
        f"- selected_scores_csv: `{selected_scores_csv}`",
        f"- delivery_summary_json: `{payload['artifacts']['delivery_summary_json']}`",
    ]
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    payload["summary_json"] = out_json
    payload["summary_md"] = out_md
    return payload


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Build full delivery artifacts only for top-k ligand hits.")
    p.add_argument("--scores-csv", type=str, required=True)
    p.add_argument("--queue-csv", type=str, required=True)
    p.add_argument("--trajectory-root", type=str, required=True)
    p.add_argument("--trajectory-glob", type=str, default="")
    p.add_argument("--out-prefix", type=str, default="runs/ligand_topk_delivery")
    p.add_argument("--score-col", type=str, default="")
    p.add_argument("--topk-global", type=int, default=20)
    p.add_argument("--topk-per-target", type=int, default=8)
    p.add_argument("--selection-mode", type=str, default="union")
    p.add_argument("--contact-cutoff-A", type=float, default=6.0)
    p.add_argument("--min-frames", type=int, default=100)
    p.add_argument("--workers", type=int, default=0)
    p.add_argument("--parallel-threshold", type=int, default=2)
    p.add_argument("--make-bundle-zip", action=argparse.BooleanOptionalAction, default=True)
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    payload = build_delivery(args)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    if not bool(payload.get("ok", False)):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
