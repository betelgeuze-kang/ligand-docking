#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pandas as pd


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return int(default)


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        x = float(v)
        if x != x:
            return float(default)
        return x
    except Exception:
        return float(default)


def _read_json(path: str) -> Dict[str, Any]:
    if (not path) or (not os.path.isfile(path)):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _write_json(path: str, payload: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def _run_cmd(cmd: List[str]) -> Dict[str, Any]:
    proc = subprocess.run(cmd, text=True, capture_output=True)
    return {
        "cmd": cmd,
        "returncode": int(proc.returncode),
        "ok": bool(proc.returncode == 0),
        "stdout_tail": "\n".join((proc.stdout or "").splitlines()[-60:]),
        "stderr_tail": "\n".join((proc.stderr or "").splitlines()[-60:]),
    }


def _load_labels(path: str) -> Dict[Tuple[str, str], Dict[str, Any]]:
    out: Dict[Tuple[str, str], Dict[str, Any]] = {}
    src = str(path).strip()
    if (not src) or (not os.path.isfile(src)):
        return out
    try:
        with open(src, "r", encoding="utf-8", errors="ignore") as f:
            r = csv.DictReader(f)
            for row in r:
                if not isinstance(row, dict):
                    continue
                t = str(row.get("target", "")).strip()
                lid = str(row.get("ligand_id", "")).strip()
                if not t or not lid:
                    continue
                out[(t, lid)] = {
                    "is_binder": _safe_int(row.get("is_binder", 0), 0),
                    "split_role": str(row.get("split_role", "")).strip(),
                }
    except Exception:
        return {}
    return out


def _pick_score_col(df: pd.DataFrame) -> Optional[str]:
    candidates = [
        "binding_energy_mmpbsa_kcal_mol_proxy",
        "binding_energy_proxy",
        "mean_min_distance_A",
    ]
    for c in candidates:
        if c not in df.columns:
            continue
        vals = pd.to_numeric(df[c], errors="coerce")
        if vals.notna().sum() > 0:
            return c
    return None


def _build_stage2_snapshot(
    run_prefix: str,
    labels_csv: str,
    out_prefix: str,
    max_jobs: int,
    viewer_engine: str,
) -> Dict[str, Any]:
    cmd = [
        sys.executable,
        "tools/build_ligand_stage2_visual_snapshot.py",
        "--run-prefix",
        str(run_prefix),
        "--max-jobs",
        str(int(max_jobs)),
        "--viewer-engine",
        str(viewer_engine),
        "--out-prefix",
        str(out_prefix),
    ]
    if str(labels_csv).strip():
        cmd.extend(["--labels-csv", str(labels_csv)])
    rec = _run_cmd(cmd)
    summary_path = f"{out_prefix}_summary.json"
    summary = _read_json(summary_path)
    return {
        "cmd": cmd,
        "run": rec,
        "summary_path": summary_path,
        "summary": summary,
    }


def _build_stage3_topk(
    run_prefix: str,
    labels_csv: str,
    out_prefix: str,
    topk_global: int,
    topk_per_target: int,
    viewer_engine: str,
) -> Dict[str, Any]:
    stage3_csv = f"{run_prefix}_stage3_scores.csv"
    if not os.path.isfile(stage3_csv):
        return {
            "ok": False,
            "error": "missing_stage3_scores",
            "stage3_csv": stage3_csv,
        }

    df = pd.read_csv(stage3_csv)
    score_col = _pick_score_col(df)
    if (df.empty) or (score_col is None):
        return {
            "ok": False,
            "error": "no_score_column",
            "stage3_csv": stage3_csv,
            "columns": list(df.columns),
        }
    df[score_col] = pd.to_numeric(df[score_col], errors="coerce")
    df = df[df[score_col].notna()].copy()
    if df.empty:
        return {
            "ok": False,
            "error": "no_valid_scores",
            "stage3_csv": stage3_csv,
            "score_col": score_col,
        }

    labels = _load_labels(labels_csv)
    if labels and ("target" in df.columns) and ("ligand_id" in df.columns):
        binders: List[int] = []
        roles: List[str] = []
        for _, row in df.iterrows():
            key = (str(row.get("target", "")).strip(), str(row.get("ligand_id", "")).strip())
            info = labels.get(key, {})
            binders.append(int(info.get("is_binder", 0)))
            roles.append(str(info.get("split_role", "")))
        df["is_binder"] = binders
        df["split_role"] = roles
    elif "is_binder" not in df.columns:
        df["is_binder"] = 0

    df = df.sort_values(score_col, ascending=True).reset_index(drop=True)
    df["rank_global"] = df.index + 1

    top_global = df.head(max(1, int(topk_global))).copy()
    if "target" in df.columns:
        top_target = (
            df.groupby("target", as_index=False, group_keys=False)
            .apply(lambda g: g.head(max(1, int(topk_per_target))))
            .reset_index(drop=True)
        )
    else:
        top_target = pd.DataFrame(columns=df.columns)

    selected = pd.concat([top_global, top_target], axis=0, ignore_index=True)
    key_col = "queue_id" if "queue_id" in selected.columns else None
    if key_col:
        selected = selected.drop_duplicates(subset=[key_col], keep="first")
    else:
        selected = selected.drop_duplicates(keep="first")
    selected = selected.sort_values(score_col, ascending=True).reset_index(drop=True)

    out_rows_csv = f"{out_prefix}_rows.csv"
    out_html = f"{out_prefix}_dashboard.html"
    out_dash_json = f"{out_prefix}_dashboard.json"
    out_summary_json = f"{out_prefix}_summary.json"

    os.makedirs(os.path.dirname(out_rows_csv) or ".", exist_ok=True)
    selected.to_csv(out_rows_csv, index=False)

    pdb_list: List[str] = []
    if "backmapped_pdb" in selected.columns:
        for p in selected["backmapped_pdb"].dropna().astype(str).tolist():
            t = str(p).strip()
            if t and os.path.isfile(t):
                pdb_list.append(t)
    uniq_pdb: List[str] = []
    seen = set()
    for p in pdb_list:
        ap = os.path.abspath(p)
        if ap in seen:
            continue
        seen.add(ap)
        uniq_pdb.append(ap)

    metric_candidates = [
        score_col,
        "mean_min_distance_A",
        "stability_score",
        "contact_fraction",
        "trajectory_frames",
        "is_binder",
    ]
    metrics = ",".join([m for m in metric_candidates if m in selected.columns])

    dash_cmd: List[str] = [
        sys.executable,
        "tools/visualize_experiment_dashboard.py",
        "--csv",
        out_rows_csv,
        "--metrics",
        metrics or score_col,
        "--max-metrics",
        "8",
        "--max-rows",
        str(max(200, len(selected))),
        "--target-col",
        "target",
        "--title",
        f"Ligand Stage3 Top-K ({os.path.basename(run_prefix)})",
        "--out-html",
        out_html,
        "--out-json",
        out_dash_json,
        "--max-pdb",
        str(max(16, len(uniq_pdb))),
        "--viewer-engine",
        str(viewer_engine),
    ]
    for p in uniq_pdb:
        dash_cmd.extend(["--pdb", p])
    dash_rec = _run_cmd(dash_cmd)

    payload = {
        "ok": bool(dash_rec.get("ok", False)),
        "stage3_csv": stage3_csv,
        "score_col": score_col,
        "rows_total": int(len(df)),
        "rows_selected": int(len(selected)),
        "topk_global": int(topk_global),
        "topk_per_target": int(topk_per_target),
        "pdb_count": int(len(uniq_pdb)),
        "artifacts": {
            "rows_csv": out_rows_csv,
            "dashboard_html": out_html,
            "dashboard_json": out_dash_json,
            "summary_json": out_summary_json,
        },
        "dashboard": dash_rec,
    }
    _write_json(out_summary_json, payload)
    return payload


def run(args: argparse.Namespace) -> Dict[str, Any]:
    run_prefix = str(args.run_prefix).strip()
    if not run_prefix:
        raise ValueError("--run-prefix is required")

    out_prefix = str(args.out_prefix).strip() or f"{run_prefix}_visual_live"
    state_json = str(args.state_json).strip() or f"{out_prefix}_state.json"
    labels_csv = str(args.labels_csv).strip()
    poll_sec = max(1, int(args.poll_sec))
    refresh_min_rows = max(1, int(args.stage2_refresh_min_rows))

    state = _read_json(state_json)
    if not state:
        state = {
            "run_prefix": run_prefix,
            "created_at_local": dt.datetime.now().isoformat(timespec="seconds"),
            "last_stage2_rows": 0,
            "last_stage3_mtime": 0.0,
            "stage2_snapshot": {},
            "stage3_topk": {},
            "events": [],
        }

    stage2_progress_json = f"{run_prefix}_stage2_traj_progress.json"
    stage3_csv = f"{run_prefix}_stage3_scores.csv"
    final_summary_json = f"{run_prefix}_summary.json"

    while True:
        now = dt.datetime.now().isoformat(timespec="seconds")
        progress = _read_json(stage2_progress_json)
        processed_rows = _safe_int(progress.get("processed_rows", 0), 0)
        stage2_status = str(progress.get("status", "")).strip()

        last_rows = _safe_int(state.get("last_stage2_rows", 0), 0)
        if processed_rows > 0 and (processed_rows - last_rows >= refresh_min_rows or (last_rows == 0 and processed_rows > 0)):
            s2_out = f"{out_prefix}_stage2"
            s2 = _build_stage2_snapshot(
                run_prefix=run_prefix,
                labels_csv=labels_csv,
                out_prefix=s2_out,
                max_jobs=int(args.stage2_max_jobs),
                viewer_engine=str(args.viewer_engine),
            )
            state["last_stage2_rows"] = processed_rows
            state["stage2_snapshot"] = s2
            events = state.get("events", [])
            if isinstance(events, list):
                events.append({"at": now, "kind": "stage2_snapshot", "processed_rows": processed_rows})
                state["events"] = events[-64:]
            _write_json(state_json, state)

        if os.path.isfile(stage3_csv):
            cur_mtime = _safe_float(os.path.getmtime(stage3_csv), 0.0)
            last_mtime = _safe_float(state.get("last_stage3_mtime", 0.0), 0.0)
            if cur_mtime > last_mtime:
                s3_out = f"{out_prefix}_stage3_topk"
                s3 = _build_stage3_topk(
                    run_prefix=run_prefix,
                    labels_csv=labels_csv,
                    out_prefix=s3_out,
                    topk_global=int(args.stage3_topk_global),
                    topk_per_target=int(args.stage3_topk_per_target),
                    viewer_engine=str(args.viewer_engine),
                )
                state["last_stage3_mtime"] = cur_mtime
                state["stage3_topk"] = s3
                events = state.get("events", [])
                if isinstance(events, list):
                    events.append({"at": now, "kind": "stage3_topk", "rows_selected": int((s3.get("rows_selected") or 0))})
                    state["events"] = events[-64:]
                _write_json(state_json, state)

        state["last_seen_at_local"] = now
        state["stage2_status"] = stage2_status
        state["stage2_processed_rows"] = processed_rows
        state["final_summary_exists"] = bool(os.path.isfile(final_summary_json))
        _write_json(state_json, state)

        if not bool(args.loop):
            break
        if bool(args.stop_on_final) and os.path.isfile(final_summary_json):
            # One last refresh on stage3 if present.
            if os.path.isfile(stage3_csv):
                cur_mtime = _safe_float(os.path.getmtime(stage3_csv), 0.0)
                last_mtime = _safe_float(state.get("last_stage3_mtime", 0.0), 0.0)
                if cur_mtime > last_mtime:
                    s3_out = f"{out_prefix}_stage3_topk"
                    s3 = _build_stage3_topk(
                        run_prefix=run_prefix,
                        labels_csv=labels_csv,
                        out_prefix=s3_out,
                        topk_global=int(args.stage3_topk_global),
                        topk_per_target=int(args.stage3_topk_per_target),
                        viewer_engine=str(args.viewer_engine),
                    )
                    state["last_stage3_mtime"] = cur_mtime
                    state["stage3_topk"] = s3
                    _write_json(state_json, state)
            break
        time.sleep(poll_sec)

    print(json.dumps(state, indent=2, ensure_ascii=False))
    return state


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Live visual pipeline for ligand HTVS run (stage2 snapshot + stage3 top-k).")
    p.add_argument("--run-prefix", type=str, required=True)
    p.add_argument("--labels-csv", type=str, default="")
    p.add_argument("--out-prefix", type=str, default="")
    p.add_argument("--state-json", type=str, default="")
    p.add_argument("--poll-sec", type=int, default=15)
    p.add_argument("--loop", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--stop-on-final", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--stage2-max-jobs", type=int, default=24)
    p.add_argument("--stage2-refresh-min-rows", type=int, default=1000)
    p.add_argument("--stage3-topk-global", type=int, default=30)
    p.add_argument("--stage3-topk-per-target", type=int, default=12)
    p.add_argument("--viewer-engine", type=str, choices=["auto", "3dmol", "molstar"], default="molstar")
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    run(args)


if __name__ == "__main__":
    main()
