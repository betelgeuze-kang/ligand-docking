#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import datetime as dt
import glob
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd


DEFAULT_METRIC_PRIORITY: List[str] = [
    "energy",
    "Rg",
    "compactness",
    "sasa",
    "cluster_max",
    "is_llps",
    "is_folded",
    "rmsd",
    "ionic_strength",
    "ptm_count",
    "force_scale",
    "cooling_rate",
    "hydro_strength",
    "k_angle",
    "theta0",
    "k_dihedral",
    "phi0_alpha",
    "violations",
    "ai_correction_active",
]

DEFAULT_X_CANDIDATES: List[str] = [
    "step",
    "steps",
    "frame",
    "sample",
    "sample_idx",
    "index",
]

COLORS: List[str] = [
    "#0b84f3",
    "#f39c12",
    "#27ae60",
    "#e74c3c",
    "#8e44ad",
    "#16a085",
    "#2c3e50",
    "#7f8c8d",
]


@dataclass
class RunSeries:
    label: str
    csv_path: str
    metrics: Dict[str, Dict[str, List[float]]]
    rows: int


def _safe_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except Exception:
        pass
    try:
        return float(v)
    except Exception:
        return None


def _parse_threshold_pairs(items: Sequence[str]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for item in items:
        token = str(item).strip()
        if (not token) or ("=" not in token):
            continue
        k, v = token.split("=", 1)
        key = str(k).strip()
        val = _safe_float(v)
        if key and (val is not None):
            out[key] = float(val)
    return out


def _extract_gate_thresholds(path: str) -> Dict[str, float]:
    src = str(path).strip()
    if (not src) or (not os.path.exists(src)):
        return {}
    try:
        payload = json.loads(open(src, "r", encoding="utf-8").read())
    except Exception:
        return {}
    out: Dict[str, float] = {}
    if isinstance(payload, dict):
        summary = payload.get("summary", {})
        if isinstance(summary, dict):
            th = summary.get("thresholds", {})
            if isinstance(th, dict):
                for k, v in th.items():
                    fv = _safe_float(v)
                    if fv is not None:
                        out[str(k)] = float(fv)
        gates = payload.get("gates", {})
        if isinstance(gates, dict):
            for gk, gv in gates.items():
                if not isinstance(gv, dict):
                    continue
                tv = _safe_float(gv.get("threshold"))
                if tv is not None:
                    out[str(gk)] = float(tv)
    return out


def _choose_x_col(df: pd.DataFrame, x_col: str) -> Tuple[str, np.ndarray]:
    forced = str(x_col).strip()
    if forced and (forced in df.columns):
        arr = pd.to_numeric(df[forced], errors="coerce").to_numpy(dtype=np.float64, copy=False)
        if np.isfinite(arr).any():
            return forced, np.nan_to_num(arr, nan=0.0)
    for col in DEFAULT_X_CANDIDATES:
        if col not in df.columns:
            continue
        arr = pd.to_numeric(df[col], errors="coerce").to_numpy(dtype=np.float64, copy=False)
        if np.isfinite(arr).any():
            return col, np.nan_to_num(arr, nan=0.0)
    return "index", np.arange(df.shape[0], dtype=np.float64)


def _select_metrics(df: pd.DataFrame, metric_spec: str, max_metrics: int) -> List[str]:
    numeric_cols: List[str] = []
    for col in df.columns:
        vals = pd.to_numeric(df[col], errors="coerce")
        if vals.notna().sum() <= 0:
            continue
        numeric_cols.append(str(col))

    if str(metric_spec).strip().lower() not in ("", "auto"):
        picked: List[str] = []
        for token in str(metric_spec).split(","):
            c = str(token).strip()
            if c and (c in df.columns):
                vals = pd.to_numeric(df[c], errors="coerce")
                if vals.notna().sum() > 0:
                    picked.append(c)
        uniq: List[str] = []
        seen = set()
        for c in picked:
            if c in seen:
                continue
            seen.add(c)
            uniq.append(c)
        return uniq[: max(1, int(max_metrics))]

    out: List[str] = []
    seen = set()
    for col in DEFAULT_METRIC_PRIORITY:
        if col in numeric_cols and col not in seen:
            out.append(col)
            seen.add(col)
    for col in numeric_cols:
        if col in seen:
            continue
        out.append(col)
        seen.add(col)
    return out[: max(1, int(max_metrics))]


def _downsample(x: np.ndarray, y: np.ndarray, max_rows: int) -> Tuple[np.ndarray, np.ndarray]:
    n = int(len(x))
    lim = int(max_rows)
    if lim <= 0 or n <= lim:
        return x, y
    stride = int(np.ceil(float(n) / float(lim)))
    return x[::stride], y[::stride]


def _load_run_series(
    csv_path: str,
    *,
    label: str,
    x_col: str,
    metrics: List[str],
    max_rows: int,
    targets: Sequence[str],
    target_col: str,
) -> RunSeries:
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"csv not found: {csv_path}")
    df = pd.read_csv(csv_path)
    if df.empty:
        raise ValueError(f"csv has no rows: {csv_path}")
    wanted = [str(t).strip() for t in targets if str(t).strip()]
    if wanted:
        col = str(target_col).strip() or "target"
        if col not in df.columns:
            raise ValueError(f"target filter requested but column not found: {col} in {csv_path}")
        mask = df[col].astype(str).str.strip().isin(wanted)
        df = df.loc[mask].copy()
        if df.empty:
            raise ValueError(f"csv has no rows after target filter: {csv_path}")
    x_name, x_vals = _choose_x_col(df, x_col=x_col)
    _ = x_name  # kept for debugging if needed later
    out_metrics: Dict[str, Dict[str, List[float]]] = {}
    for m in metrics:
        if m not in df.columns:
            continue
        y = pd.to_numeric(df[m], errors="coerce").to_numpy(dtype=np.float64, copy=False)
        mask = np.isfinite(x_vals) & np.isfinite(y)
        if int(mask.sum()) <= 0:
            continue
        xx, yy = _downsample(x_vals[mask], y[mask], max_rows=max_rows)
        out_metrics[m] = {
            "x": xx.astype(np.float64).tolist(),
            "y": yy.astype(np.float64).tolist(),
        }
    if not out_metrics:
        raise ValueError(f"no numeric metrics found in csv: {csv_path}")
    return RunSeries(
        label=str(label),
        csv_path=str(csv_path),
        metrics=out_metrics,
        rows=int(df.shape[0]),
    )


def _collect_pdb_entries(pdb_files: Sequence[str], pdb_glob: Sequence[str], max_pdb: int) -> List[Dict[str, str]]:
    def _infer_source(path: str) -> str:
        p = str(path).replace("\\", "/").lower()
        b = os.path.basename(p)
        if ("internal_structures_refined/" in p) or ("visual_post_" in b):
            return "internal_visual_refined"
        # Stage2/Stage3 internal outputs may not use legacy naming but are still
        # coarse-grained internal structures and need CA-visible styling.
        if ("_visual_live_stage2_pdb/" in p) or ("_stage2_visual_live_pdb/" in p):
            return "internal_postprocessed"
        if ("/stage3_delivery/" in p) and b.startswith("backmapped_"):
            return "internal_postprocessed"
        if ("internal_structures/" in p) or ("internal_post_" in b):
            return "internal_postprocessed"
        if ("/public_structures/" in p) or ("_afdb_" in b) or ("_pdb_" in b):
            return "external_public"
        if "/data/native/" in p:
            return "native_reference"
        return "other"

    files: List[str] = []
    for p in pdb_files:
        src = str(p).strip()
        if src:
            files.append(src)
    for pat in pdb_glob:
        token = str(pat).strip()
        if not token:
            continue
        files.extend(sorted(glob.glob(token)))
    uniq: List[str] = []
    seen = set()
    for p in files:
        ap = os.path.abspath(str(p))
        if ap in seen:
            continue
        seen.add(ap)
        if os.path.isfile(ap):
            uniq.append(ap)
    records: List[Dict[str, str]] = []
    for p in uniq:
        try:
            content = open(p, "r", encoding="utf-8", errors="ignore").read()
        except Exception:
            continue
        records.append(
            {
                "name": os.path.basename(p),
                "path": p,
                "content": content,
                "source": _infer_source(p),
            }
        )

    lim = max(0, int(max_pdb))
    if lim <= 0 or len(records) <= lim:
        return records

    source_order: List[str] = []
    grouped: Dict[str, List[Dict[str, str]]] = {}
    for rec in records:
        s = str(rec.get("source", "other"))
        if s not in grouped:
            grouped[s] = []
            source_order.append(s)
        grouped[s].append(rec)

    if len(source_order) <= 1:
        return records[:lim]

    per_source = max(1, lim // len(source_order))
    selected: List[Dict[str, str]] = []
    used_paths = set()

    for s in source_order:
        chunk = grouped.get(s, [])
        take = chunk[:per_source]
        for rec in take:
            ap = str(rec.get("path", ""))
            if ap in used_paths:
                continue
            selected.append(rec)
            used_paths.add(ap)
            if len(selected) >= lim:
                return selected[:lim]

    if len(selected) < lim:
        for rec in records:
            ap = str(rec.get("path", ""))
            if ap in used_paths:
                continue
            selected.append(rec)
            used_paths.add(ap)
            if len(selected) >= lim:
                break
    return selected[:lim]


def _as_bool(v: Any) -> bool:
    if isinstance(v, bool):
        return bool(v)
    tok = str(v).strip().lower()
    return tok in {"1", "true", "yes", "y", "on"}


def _collect_movie_entries(
    movie_json_paths: Sequence[str],
    movie_csv_paths: Sequence[str],
) -> List[Dict[str, Any]]:
    def _norm_path(path: Any) -> str:
        tok = str(path).strip()
        if not tok:
            return ""
        try:
            return os.path.abspath(tok)
        except Exception:
            return tok

    rows: List[Dict[str, Any]] = []
    seen = set()

    def _push(raw: Dict[str, Any], source_path: str) -> None:
        pdb_raw = str(raw.get("pdb_path", "")).strip()
        if not pdb_raw:
            return
        mp4_raw = str(raw.get("mp4_path", "")).strip()
        script_raw = str(raw.get("script_path", "")).strip()
        pdb_path = _norm_path(pdb_raw) or pdb_raw
        mp4_path = _norm_path(mp4_raw) if mp4_raw else ""
        script_path = _norm_path(script_raw) if script_raw else ""
        key = (str(pdb_path), str(mp4_path))
        if key in seen:
            return
        seen.add(key)
        rows.append(
            {
                "pdb_path": str(pdb_path),
                "pdb_name": os.path.basename(str(pdb_path)),
                "mp4_path": str(mp4_path),
                "script_path": str(script_path),
                "ok": bool(_as_bool(raw.get("ok", True))),
                "executed": bool(_as_bool(raw.get("executed", False))),
                "has_mp4": bool(mp4_path and os.path.exists(mp4_path)),
                "source_path": str(source_path),
            }
        )

    for src in movie_json_paths:
        p = str(src).strip()
        if (not p) or (not os.path.isfile(p)):
            continue
        try:
            payload = json.loads(open(p, "r", encoding="utf-8").read())
        except Exception:
            continue
        if isinstance(payload, dict) and isinstance(payload.get("rows"), list):
            for row in payload.get("rows", []):
                if isinstance(row, dict):
                    _push(row, p)
        elif isinstance(payload, list):
            for row in payload:
                if isinstance(row, dict):
                    _push(row, p)

    for src in movie_csv_paths:
        p = str(src).strip()
        if (not p) or (not os.path.isfile(p)):
            continue
        try:
            with open(p, "r", encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if isinstance(row, dict):
                        _push(row, p)
        except Exception:
            continue

    rows = sorted(rows, key=lambda r: (str(r.get("pdb_name", "")), str(r.get("pdb_path", ""))))
    return rows


def _last_valid_metric_value(df: pd.DataFrame, metric: str, x_col: str) -> Optional[float]:
    if (df is None) or df.empty or (metric not in df.columns):
        return None
    _, x_vals = _choose_x_col(df, x_col=x_col)
    y_vals = pd.to_numeric(df[metric], errors="coerce").to_numpy(dtype=np.float64, copy=False)
    mask = np.isfinite(x_vals) & np.isfinite(y_vals)
    if int(mask.sum()) <= 0:
        return None
    xv = x_vals[mask]
    yv = y_vals[mask]
    idx = int(np.argmax(xv))
    return float(yv[idx])


def _build_decision_board(
    *,
    csv_inputs: Sequence[str],
    labels: Sequence[str],
    metrics: Sequence[str],
    x_col: str,
    target_col: str,
    target_filters: Sequence[str],
    thresholds: Dict[str, float],
    topk_targets: int,
) -> Dict[str, Any]:
    if len(csv_inputs) < 2:
        return {
            "available": False,
            "reason": "compare_csv_not_provided",
            "metric_compare_rows": [],
            "target_regression_rows": [],
        }

    try:
        base_df = pd.read_csv(str(csv_inputs[0]))
        cand_df = pd.read_csv(str(csv_inputs[1]))
    except Exception as exc:
        return {
            "available": False,
            "reason": f"compare_csv_read_failed: {exc}",
            "metric_compare_rows": [],
            "target_regression_rows": [],
        }

    tcol = str(target_col).strip() or "target"
    wanted = [str(x).strip() for x in target_filters if str(x).strip()]
    if wanted and (tcol in base_df.columns):
        base_df = base_df.loc[base_df[tcol].astype(str).str.strip().isin(wanted)].copy()
    if wanted and (tcol in cand_df.columns):
        cand_df = cand_df.loc[cand_df[tcol].astype(str).str.strip().isin(wanted)].copy()

    metric_rows: List[Dict[str, Any]] = []
    for m in metrics:
        b = _last_valid_metric_value(base_df, m, x_col=x_col)
        c = _last_valid_metric_value(cand_df, m, x_col=x_col)
        if (b is None) or (c is None):
            continue
        delta = float(c - b)
        threshold = _safe_float(thresholds.get(m))
        gate_fail = bool((threshold is not None) and (float(c) > float(threshold)))
        regression = bool(delta > 0.0)
        metric_rows.append(
            {
                "metric": str(m),
                "baseline_latest": float(b),
                "candidate_latest": float(c),
                "delta_candidate_minus_baseline": float(delta),
                "regression": bool(regression),
                "gate_threshold": threshold,
                "gate_fail": bool(gate_fail),
            }
        )

    key_metric = ""
    for m in ("rmsd", "Rg", "sasa", "energy"):
        if any(str(r.get("metric")) == m for r in metric_rows):
            key_metric = m
            break
    if (not key_metric) and metric_rows:
        key_metric = str(metric_rows[0].get("metric", ""))

    target_rows: List[Dict[str, Any]] = []
    if key_metric and (tcol in base_df.columns) and (tcol in cand_df.columns):
        bt = set(base_df[tcol].astype(str).str.strip().tolist())
        ct = set(cand_df[tcol].astype(str).str.strip().tolist())
        common = sorted(x for x in (bt & ct) if x)
        for t in common:
            b_sub = base_df.loc[base_df[tcol].astype(str).str.strip() == t].copy()
            c_sub = cand_df.loc[cand_df[tcol].astype(str).str.strip() == t].copy()
            b = _last_valid_metric_value(b_sub, key_metric, x_col=x_col)
            c = _last_valid_metric_value(c_sub, key_metric, x_col=x_col)
            if (b is None) or (c is None):
                continue
            d = float(c - b)
            target_rows.append(
                {
                    "target": str(t),
                    "metric": key_metric,
                    "baseline_latest": float(b),
                    "candidate_latest": float(c),
                    "delta_candidate_minus_baseline": float(d),
                    "regression": bool(d > 0.0),
                }
            )
        target_rows = sorted(target_rows, key=lambda r: float(r.get("delta_candidate_minus_baseline", 0.0)), reverse=True)[
            : max(1, int(topk_targets))
        ]

    return {
        "available": True,
        "baseline_label": str(labels[0]) if labels else "baseline",
        "candidate_label": str(labels[1]) if len(labels) > 1 else "candidate",
        "metric_compare_rows": metric_rows,
        "target_regression_rows": target_rows,
        "key_metric": key_metric or None,
        "metric_regression_count": int(sum(1 for r in metric_rows if bool(r.get("regression", False)))),
        "gate_fail_count": int(sum(1 for r in metric_rows if bool(r.get("gate_fail", False)))),
    }


def _build_payload(
    runs: List[RunSeries],
    metrics: List[str],
    thresholds: Dict[str, float],
    pdb_entries: List[Dict[str, str]],
    movie_entries: Sequence[Dict[str, Any]],
    target_filters: Sequence[str],
    title: str,
    viewer_engine: str,
) -> Dict[str, Any]:
    metric_cards: List[Dict[str, Any]] = []
    gate_check_total = 0
    gate_pass_count = 0
    total_rows = 0

    run_items: List[Dict[str, Any]] = []
    for idx, run in enumerate(runs):
        color = COLORS[idx % len(COLORS)]
        total_rows += int(run.rows)
        run_items.append(
            {
                "label": run.label,
                "csv_path": run.csv_path,
                "rows": run.rows,
                "color": color,
                "metrics": run.metrics,
            }
        )

    for metric in metrics:
        th = _safe_float(thresholds.get(metric))
        latest_by_run: Dict[str, float] = {}
        mean_by_run: Dict[str, float] = {}
        std_by_run: Dict[str, float] = {}
        pass_count = 0
        fail_count = 0
        for run in runs:
            series = run.metrics.get(metric, {})
            ys = np.asarray(series.get("y", []), dtype=np.float64)
            ys = ys[np.isfinite(ys)]
            if ys.size <= 0:
                continue
            latest_v = float(ys[-1])
            latest_by_run[run.label] = latest_v
            mean_by_run[run.label] = float(np.mean(ys))
            std_by_run[run.label] = float(np.std(ys))
            if th is not None:
                gate_check_total += 1
                if latest_v <= float(th):
                    gate_pass_count += 1
                    pass_count += 1
                else:
                    fail_count += 1
        if latest_by_run:
            metric_cards.append(
                {
                    "metric": metric,
                    "threshold": th,
                    "latest_by_run": latest_by_run,
                    "mean_by_run": mean_by_run,
                    "std_by_run": std_by_run,
                    "pass_count": int(pass_count),
                    "fail_count": int(fail_count),
                }
            )

    gate_pass_rate = None
    if gate_check_total > 0:
        gate_pass_rate = float(gate_pass_count) / float(gate_check_total)

    summary = {
        "run_count": int(len(runs)),
        "metric_count": int(len(metrics)),
        "pdb_count": int(len(pdb_entries)),
        "movie_count": int(len(movie_entries)),
        "movie_ready_count": int(sum(1 for x in movie_entries if bool(x.get("has_mp4", False)))),
        "threshold_count": int(len(thresholds)),
        "total_rows": int(total_rows),
        "gate_check_total": int(gate_check_total),
        "gate_pass_count": int(gate_pass_count),
        "gate_pass_rate": gate_pass_rate,
        "metric_cards": metric_cards,
    }
    return {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "title": str(title),
        "viewer_engine": str(viewer_engine).strip().lower() or "auto",
        "metrics": metrics,
        "thresholds": thresholds,
        "target_filters": [str(t).strip() for t in target_filters if str(t).strip()],
        "runs": run_items,
        "pdb_entries": pdb_entries,
        "movie_entries": list(movie_entries),
        "summary": summary,
    }


def _render_html(payload: Dict[str, Any]) -> str:
    pj = json.dumps(payload, ensure_ascii=False)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{payload.get("title","Experiment Dashboard")}</title>
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/molstar/build/viewer/molstar.css"/>
  <script src="https://cdn.jsdelivr.net/npm/molstar/build/viewer/molstar.js"></script>
  <script src="https://3Dmol.org/build/3Dmol-min.js"></script>
  <style>
    :root {{
      --bg: #f4f6f8;
      --fg: #0f172a;
      --card: #ffffff;
      --line: #d0d7de;
      --accent: #0b84f3;
      --muted: #5b6675;
    }}
    body {{
      margin: 0;
      font-family: "Segoe UI", "Noto Sans KR", "Arial", sans-serif;
      background: linear-gradient(180deg, #f8fbff 0%, #f3f6f8 100%);
      color: var(--fg);
    }}
    .wrap {{
      max-width: 1400px;
      margin: 0 auto;
      padding: 16px;
    }}
    .card {{
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 12px;
      margin-bottom: 12px;
      box-shadow: 0 3px 12px rgba(0,0,0,0.04);
    }}
    .title {{
      font-size: 20px;
      font-weight: 700;
      margin: 0 0 6px 0;
    }}
    .meta {{
      color: var(--muted);
      font-size: 13px;
      margin: 0;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(380px, 1fr));
      gap: 12px;
    }}
    .plot {{
      height: 300px;
      border: 1px solid var(--line);
      border-radius: 10px;
    }}
    .viewer-wrap {{
      display: grid;
      grid-template-columns: 280px 1fr;
      gap: 12px;
      align-items: start;
    }}
    .viewer {{
      height: 520px;
      border: 1px solid var(--line);
      border-radius: 10px;
      overflow: hidden;
      position: relative;
      background: #ffffff;
      isolation: isolate;
      contain: layout paint size;
    }}
    #molViewer {{
      position: relative;
      width: 100%;
      height: 100%;
      overflow: hidden;
      background: #ffffff;
    }}
    #molViewer > div {{
      position: absolute;
      inset: 0;
      overflow: hidden;
      max-width: 100%;
      max-height: 100%;
    }}
    .viewer *,
    .viewer canvas,
    .viewer img {{
      max-width: 100% !important;
      max-height: 100% !important;
      box-sizing: border-box;
    }}
    #molViewer canvas,
    #molViewer img {{
      position: absolute !important;
      inset: 0;
      width: 100% !important;
      height: 100% !important;
      display: block;
      object-fit: contain;
      overflow: hidden;
      background: transparent !important;
    }}
    .small {{
      font-size: 12px;
      color: var(--muted);
    }}
    img {{
      max-width: 100%;
      height: auto;
      display: block;
    }}
    select {{
      width: 100%;
      padding: 8px;
      border-radius: 8px;
      border: 1px solid var(--line);
      background: #fff;
    }}
    .legend-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 8px;
    }}
    .chip {{
      border: 1px solid var(--line);
      padding: 4px 8px;
      border-radius: 999px;
      font-size: 12px;
      background: #fff;
    }}
    .kpi-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
      gap: 10px;
    }}
    .kpi {{
      background: #fff;
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 10px;
    }}
    .kpi .k {{
      font-size: 11px;
      color: var(--muted);
      margin-bottom: 4px;
    }}
    .kpi .v {{
      font-size: 20px;
      font-weight: 700;
    }}
    .kpi.good {{
      border-color: #b7ebc0;
      background: #f5fff7;
    }}
    .kpi.warn {{
      border-color: #ffe08a;
      background: #fffdf6;
    }}
    .kpi.bad {{
      border-color: #ffb2b2;
      background: #fff8f8;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 12px;
    }}
    th, td {{
      border-bottom: 1px solid var(--line);
      text-align: left;
      padding: 7px 6px;
      vertical-align: top;
    }}
    th {{
      color: #334155;
      background: #f8fafc;
    }}
    tr.row-fail {{
      background: #fff3f3;
    }}
    tr.row-regression {{
      background: #fffaf0;
    }}
    .decision-meta {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 8px;
      margin-bottom: 10px;
    }}
    .decision-chip {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 6px 8px;
      font-size: 12px;
      background: #fff;
    }}
    .btn {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 8px 10px;
      background: #fff;
      color: var(--fg);
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
    }}
    .btn:hover {{
      border-color: #9bb6d1;
      background: #f8fbff;
    }}
    .btn.primary {{
      border-color: #0b84f3;
      background: #0b84f3;
      color: #fff;
    }}
    .btn.ghost {{
      background: #fff;
      color: #334155;
    }}
    .movie-box {{
      margin-top: 10px;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 8px;
      background: #fbfdff;
    }}
    .movie-links {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin-top: 6px;
    }}
    .movie-link {{
      display: inline-block;
      padding: 5px 8px;
      border-radius: 7px;
      border: 1px solid #bfd3ea;
      color: #0b3d74;
      background: #eef6ff;
      text-decoration: none;
      font-size: 12px;
      font-weight: 600;
    }}
    .movie-link:hover {{
      background: #e4f0ff;
      border-color: #8fb4de;
    }}
    .movie-path {{
      margin-top: 6px;
      font-size: 11px;
      color: #64748b;
      word-break: break-all;
    }}
    .modal {{
      display: none;
      position: fixed;
      inset: 0;
      z-index: 9999;
      background: rgba(8, 15, 28, 0.58);
      backdrop-filter: blur(2px);
      align-items: center;
      justify-content: center;
      padding: 14px;
    }}
    .modal.open {{
      display: flex;
    }}
    .modal-panel {{
      width: min(96vw, 1600px);
      height: min(94vh, 980px);
      background: #fff;
      border-radius: 14px;
      border: 1px solid #d7e1ea;
      box-shadow: 0 18px 60px rgba(0,0,0,0.25);
      display: grid;
      grid-template-rows: auto 1fr;
      gap: 10px;
      padding: 12px;
    }}
    .modal-header {{
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 12px;
      align-items: end;
    }}
    .modal-actions {{
      display: flex;
      gap: 8px;
      align-items: center;
      justify-content: flex-end;
    }}
    .modal-select {{
      min-width: 320px;
      max-width: 520px;
    }}
    .viewer.viewer-modal {{
      height: auto;
      min-height: 0;
      width: 100%;
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <h1 class="title">{payload.get("title","Experiment Dashboard")}</h1>
      <p class="meta">Generated: {payload.get("generated_at_local","")}</p>
      <p class="meta">Target Filter: {", ".join(payload.get("target_filters", [])) if payload.get("target_filters") else "all"}</p>
      <div id="runMeta" class="legend-row"></div>
    </div>

    <div class="card">
      <h2 class="title" style="font-size:17px;">Executive KPI</h2>
      <div id="kpiGrid" class="kpi-grid"></div>
    </div>

    <div class="card">
      <h2 class="title" style="font-size:17px;">Decision Board</h2>
      <div id="decisionMeta" class="decision-meta"></div>
      <p class="small">Baseline vs candidate regression and gate-fail highlights.</p>
      <div style="overflow:auto; max-height: 280px; margin-bottom: 10px;">
        <table>
          <thead>
            <tr>
              <th>Metric</th>
              <th>Baseline</th>
              <th>Candidate</th>
              <th>Delta (cand-base)</th>
              <th>Gate</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody id="decisionMetricRows"></tbody>
        </table>
      </div>
      <div style="overflow:auto; max-height: 240px;">
        <table>
          <thead>
            <tr>
              <th>Top Regression Target</th>
              <th>Metric</th>
              <th>Baseline</th>
              <th>Candidate</th>
              <th>Delta</th>
            </tr>
          </thead>
          <tbody id="decisionTargetRows"></tbody>
        </table>
      </div>
    </div>

    <div class="card">
      <h2 class="title" style="font-size:17px;">Metric Summary Table</h2>
      <p class="small">Latest/mean/std are computed from currently plotted rows after target filter/downsampling.</p>
      <div style="overflow:auto; max-height: 360px;">
        <table>
          <thead>
            <tr>
              <th>Metric</th>
              <th>Threshold</th>
              <th>Latest (by run)</th>
              <th>Mean ± Std (by run)</th>
              <th>Gate pass/fail</th>
            </tr>
          </thead>
          <tbody id="metricSummaryRows"></tbody>
        </table>
      </div>
    </div>

    <div class="card">
      <h2 class="title" style="font-size:17px;">CSV Time-Series + Gate Overlay</h2>
      <p class="small">Selected metrics are auto-detected or user-defined. Horizontal dashed line = threshold if provided.</p>
      <div id="plots" class="grid"></div>
    </div>

    <div class="card">
      <h2 class="title" style="font-size:17px;">PDB 3D Viewer</h2>
      <div class="viewer-wrap">
        <div>
          <label class="small" for="pdbSelect">Structure</label>
          <select id="pdbSelect"></select>
          <p id="pdbInfo" class="small"></p>
          <button id="openViewerModalBtn" class="btn primary" type="button">Detail Modal Viewer</button>
          <div id="movieBox" class="movie-box">
            <div id="movieStatus" class="small">Movie: not linked</div>
            <div id="movieLinks" class="movie-links"></div>
          </div>
        </div>
        <div id="molViewer" class="viewer"></div>
      </div>
    </div>
  </div>

  <div id="viewerModal" class="modal" role="dialog" aria-modal="true" aria-labelledby="viewerModalTitle">
    <div class="modal-panel">
      <div class="modal-header">
        <div>
          <h2 id="viewerModalTitle" class="title" style="font-size:18px; margin-bottom:4px;">PDB Detail Viewer</h2>
          <p id="pdbModalInfo" class="small" style="margin:0;"></p>
        </div>
        <div class="modal-actions">
          <select id="pdbSelectModal" class="modal-select"></select>
          <button id="openMovieBtn" class="btn ghost" type="button">Open Movie</button>
          <button id="resetViewerModalBtn" class="btn ghost" type="button">Reset Zoom</button>
          <button id="closeViewerModalBtn" class="btn" type="button">Close</button>
        </div>
      </div>
      <div id="molViewerModal" class="viewer viewer-modal"></div>
    </div>
  </div>

  <script>
    const payload = {pj};
    const summary = payload.summary || {{}};
    const runMeta = document.getElementById("runMeta");
    (payload.runs || []).forEach((r) => {{
      const chip = document.createElement("div");
      chip.className = "chip";
      chip.style.borderColor = r.color || "#ccc";
      chip.innerText = `${{r.label}} | rows=${{r.rows}}`;
      runMeta.appendChild(chip);
    }});

    function fnum(v, d=3) {{
      if (typeof v !== "number" || !isFinite(v)) return "-";
      return Number(v).toFixed(d);
    }}

    function renderKpi() {{
      const host = document.getElementById("kpiGrid");
      const cards = [
        {{k: "Runs", v: summary.run_count ?? (payload.runs || []).length}},
        {{k: "Metrics", v: summary.metric_count ?? (payload.metrics || []).length}},
        {{k: "PDB", v: summary.pdb_count ?? (payload.pdb_entries || []).length}},
        {{k: "Movies", v: summary.movie_count ?? (payload.movie_entries || []).length}},
        {{k: "Rows", v: summary.total_rows ?? "-"}},
        {{k: "Thresholds", v: summary.threshold_count ?? Object.keys(payload.thresholds || {{}}).length}},
      ];
      const gateRate = summary.gate_pass_rate;
      const gateCard = {{
        k: "Gate pass rate",
        v: (typeof gateRate === "number" && isFinite(gateRate)) ? `${{(gateRate*100).toFixed(1)}}%` : "N/A",
        cls: (typeof gateRate === "number" && isFinite(gateRate))
          ? (gateRate >= 0.95 ? "good" : (gateRate >= 0.80 ? "warn" : "bad"))
          : "warn",
      }};
      cards.push(gateCard);

      cards.forEach((item) => {{
        const div = document.createElement("div");
        div.className = `kpi ${{item.cls || ""}}`.trim();
        div.innerHTML = `<div class="k">${{item.k}}</div><div class="v">${{item.v}}</div>`;
        host.appendChild(div);
      }});
    }}

    function renderMetricSummaryTable() {{
      const body = document.getElementById("metricSummaryRows");
      const cards = Array.isArray(summary.metric_cards) ? summary.metric_cards : [];
      cards.forEach((row) => {{
        const tr = document.createElement("tr");
        const latest = Object.entries(row.latest_by_run || {{}})
          .map(([k, v]) => `${{k}}: ${{fnum(v, 4)}}`)
          .join("<br/>") || "-";
        const meanStd = Object.keys(row.mean_by_run || {{}})
          .map((k) => `${{k}}: ${{fnum((row.mean_by_run||{{}})[k],4)}} ± ${{fnum((row.std_by_run||{{}})[k],4)}}`)
          .join("<br/>") || "-";
        const gate = (typeof row.threshold === "number" && isFinite(row.threshold))
          ? `${{row.pass_count||0}} / ${{(row.pass_count||0)+(row.fail_count||0)}}`
          : "N/A";
        if ((row.fail_count || 0) > 0) {{
          tr.className = "row-fail";
        }}
        tr.innerHTML = `
          <td><b>${{row.metric || "-"}}</b></td>
          <td>${{(typeof row.threshold === "number" && isFinite(row.threshold)) ? fnum(row.threshold,4) : "-"}}</td>
          <td>${{latest}}</td>
          <td>${{meanStd}}</td>
          <td>${{gate}}</td>
        `;
        body.appendChild(tr);
      }});
      if (!cards.length) {{
        const tr = document.createElement("tr");
        tr.innerHTML = "<td colspan='5'>No summary rows.</td>";
        body.appendChild(tr);
      }}
    }}

    function renderDecisionBoard() {{
      const meta = document.getElementById("decisionMeta");
      const mbody = document.getElementById("decisionMetricRows");
      const tbody = document.getElementById("decisionTargetRows");
      const db = (summary && summary.decision_board) ? summary.decision_board : null;
      if (!db || !db.available) {{
        const chip = document.createElement("div");
        chip.className = "decision-chip";
        chip.innerText = "compare_csv not provided or unavailable";
        meta.appendChild(chip);
        const tr1 = document.createElement("tr");
        tr1.innerHTML = "<td colspan='6'>No compare-run decision rows.</td>";
        mbody.appendChild(tr1);
        const tr2 = document.createElement("tr");
        tr2.innerHTML = "<td colspan='5'>No target regression rows.</td>";
        tbody.appendChild(tr2);
        return;
      }}

      const chips = [
        `baseline: ${{db.baseline_label || '-'}}`,
        `candidate: ${{db.candidate_label || '-'}}`,
        `metric regressions: ${{db.metric_regression_count || 0}}`,
        `gate fails: ${{db.gate_fail_count || 0}}`,
        `key metric: ${{db.key_metric || '-'}}`,
      ];
      chips.forEach((txt) => {{
        const c = document.createElement("div");
        c.className = "decision-chip";
        c.innerText = txt;
        meta.appendChild(c);
      }});

      const mrows = Array.isArray(db.metric_compare_rows) ? db.metric_compare_rows : [];
      if (!mrows.length) {{
        const tr = document.createElement("tr");
        tr.innerHTML = "<td colspan='6'>No metric compare rows.</td>";
        mbody.appendChild(tr);
      }} else {{
        mrows.forEach((r) => {{
          const tr = document.createElement("tr");
          if (r.gate_fail) {{
            tr.className = "row-fail";
          }} else if (r.regression) {{
            tr.className = "row-regression";
          }}
          const gateText = (typeof r.gate_threshold === "number" && isFinite(r.gate_threshold))
            ? `${{fnum(r.gate_threshold, 4)}}${{r.gate_fail ? " (FAIL)" : " (PASS)"}}`
            : "-";
          const status = r.gate_fail ? "gate_fail" : (r.regression ? "regression" : "ok");
          tr.innerHTML = `
            <td><b>${{r.metric || "-"}}</b></td>
            <td>${{fnum(r.baseline_latest,4)}}</td>
            <td>${{fnum(r.candidate_latest,4)}}</td>
            <td>${{fnum(r.delta_candidate_minus_baseline,4)}}</td>
            <td>${{gateText}}</td>
            <td>${{status}}</td>
          `;
          mbody.appendChild(tr);
        }});
      }}

      const trows = Array.isArray(db.target_regression_rows) ? db.target_regression_rows : [];
      if (!trows.length) {{
        const tr = document.createElement("tr");
        tr.innerHTML = "<td colspan='5'>No target regression rows.</td>";
        tbody.appendChild(tr);
      }} else {{
        trows.forEach((r) => {{
          const tr = document.createElement("tr");
          if (r.regression) tr.className = "row-regression";
          tr.innerHTML = `
            <td><b>${{r.target || "-"}}</b></td>
            <td>${{r.metric || "-"}}</td>
            <td>${{fnum(r.baseline_latest,4)}}</td>
            <td>${{fnum(r.candidate_latest,4)}}</td>
            <td>${{fnum(r.delta_candidate_minus_baseline,4)}}</td>
          `;
          tbody.appendChild(tr);
        }});
      }}
    }}

    function buildPlots() {{
      const plots = document.getElementById("plots");
      const metrics = payload.metrics || [];
      metrics.forEach((m, idx) => {{
        const div = document.createElement("div");
        div.className = "plot";
        div.id = `plot_${{idx}}`;
        plots.appendChild(div);

        const traces = [];
        (payload.runs || []).forEach((r) => {{
          const metricSeries = (r.metrics || {{}})[m];
          const y = Array.isArray(metricSeries) ? metricSeries : ((metricSeries || {{}}).y || []);
          const x = Array.isArray(metricSeries) ? [] : ((metricSeries || {{}}).x || []);
          if (!y || y.length === 0) return;
          traces.push({{
            x: (x && x.length) ? x.slice(0, y.length) : [...Array(y.length).keys()],
            y: y,
            mode: "lines",
            name: r.label,
            line: {{ width: 2, color: r.color || "#0b84f3" }},
          }});
        }});
        const shapes = [];
        const th = (payload.thresholds || {{}})[m];
        if (typeof th === "number" && isFinite(th)) {{
          shapes.push({{
            type: "line",
            xref: "paper",
            x0: 0,
            x1: 1,
            y0: th,
            y1: th,
            line: {{ color: "#e74c3c", width: 1.5, dash: "dash" }},
          }});
        }}
        const layout = {{
          title: {{ text: m, font: {{ size: 14 }} }},
          margin: {{ l: 52, r: 14, t: 38, b: 44 }},
          paper_bgcolor: "#ffffff",
          plot_bgcolor: "#ffffff",
          xaxis: {{ title: "x", gridcolor: "#eef2f6" }},
          yaxis: {{ title: m, gridcolor: "#eef2f6" }},
          legend: {{ orientation: "h" }},
          shapes: shapes,
        }};
        Plotly.newPlot(div.id, traces, layout, {{displaylogo: false, responsive: true}});
      }});
    }}

    function buildPdbViewer() {{
      const pdbs = payload.pdb_entries || [];
      const movies = payload.movie_entries || [];
      const select = document.getElementById("pdbSelect");
      const info = document.getElementById("pdbInfo");
      const viewerHost = document.getElementById("molViewer");
      const movieStatus = document.getElementById("movieStatus");
      const movieLinks = document.getElementById("movieLinks");
      const openModalBtn = document.getElementById("openViewerModalBtn");
      const modal = document.getElementById("viewerModal");
      const modalHost = document.getElementById("molViewerModal");
      const modalInfo = document.getElementById("pdbModalInfo");
      const modalSelect = document.getElementById("pdbSelectModal");
      const openMovieBtn = document.getElementById("openMovieBtn");
      const closeModalBtn = document.getElementById("closeViewerModalBtn");
      const resetModalBtn = document.getElementById("resetViewerModalBtn");
      let currentIdx = 0;
      let viewer = null;
      let modalViewer = null;
      let loadEpoch = 0;

      const pref = String(payload.viewer_engine || "auto").toLowerCase();
      const canMolstar = !!(window.molstar && typeof window.molstar.Viewer === "function");
      let activeEngine = (pref === "molstar" || (pref === "auto" && canMolstar)) ? "molstar" : "3dmol";

      const setInfo = (item) => {{
        const src = item.source || "other";
        const txt = `[${{src}}] ${{item.name}} | ${{item.path}} | engine=${{activeEngine}}`;
        info.innerText = txt;
        modalInfo.innerText = txt;
      }};

      const _normPath = (p) => String(p || "").replace(/\\\\/g, "/").trim().toLowerCase();
      const _baseName = (p) => {{
        const tok = String(p || "").replace(/\\\\/g, "/");
        const idx = tok.lastIndexOf("/");
        return idx >= 0 ? tok.slice(idx + 1) : tok;
      }};
      const _toFileHref = (p) => {{
        const raw = String(p || "").trim();
        if (!raw) return "";
        if (/^[a-z]+:\\/\\//i.test(raw)) return raw;
        const posix = raw.replace(/\\\\/g, "/");
        if (posix.startsWith("/")) {{
          return "file://" + encodeURI(posix);
        }}
        return encodeURI(posix);
      }};

      const movieByExact = new Map();
      const movieByName = new Map();
      (Array.isArray(movies) ? movies : []).forEach((m) => {{
        if (!m || typeof m !== "object") return;
        const exact = _normPath(m.pdb_path || "");
        const name = _baseName(m.pdb_path || "");
        if (exact && !movieByExact.has(exact)) movieByExact.set(exact, m);
        if (name && !movieByName.has(name)) movieByName.set(name, m);
      }});

      const _resolveMovie = (item) => {{
        if (!item) return null;
        const exact = _normPath(item.path || "");
        if (exact && movieByExact.has(exact)) return movieByExact.get(exact);
        const name = _baseName(item.path || "");
        if (name && movieByName.has(name)) return movieByName.get(name);
        return null;
      }};

      let currentMovie = null;
      const _renderMovieLinks = (item) => {{
        currentMovie = _resolveMovie(item);
        if (!movieStatus || !movieLinks) return;
        movieLinks.innerHTML = "";
        if (!currentMovie) {{
          movieStatus.innerText = "Movie: not available for this structure.";
          if (openMovieBtn) openMovieBtn.disabled = true;
          return;
        }}
        const mp4 = String(currentMovie.mp4_path || "").trim();
        const script = String(currentMovie.script_path || "").trim();
        const ok = !!currentMovie.ok;
        const executed = !!currentMovie.executed;
        const hasMp4 = !!currentMovie.has_mp4 || !!mp4;
        movieStatus.innerText = `Movie: ${{hasMp4 ? "available" : "script-only"}} | ok=${{ok}} | executed=${{executed}}`;
        if (openMovieBtn) openMovieBtn.disabled = !hasMp4;

        if (hasMp4) {{
          const a = document.createElement("a");
          a.className = "movie-link";
          a.href = _toFileHref(mp4);
          a.target = "_blank";
          a.rel = "noopener";
          a.innerText = "Open MP4";
          movieLinks.appendChild(a);
          const p = document.createElement("div");
          p.className = "movie-path";
          p.innerText = mp4;
          movieLinks.appendChild(p);
        }}
        if (script) {{
          const a = document.createElement("a");
          a.className = "movie-link";
          a.href = _toFileHref(script);
          a.target = "_blank";
          a.rel = "noopener";
          a.innerText = "Open CXC";
          movieLinks.appendChild(a);
        }}
      }};

      const _parsePdbStats = (pdbText) => {{
        const lines = String(pdbText || "").split(/\\r?\\n/);
        let atomCount = 0;
        let caCount = 0;
        let nCount = 0;
        let cCount = 0;
        let oCount = 0;
        for (const ln of lines) {{
          if (!(ln.startsWith("ATOM") || ln.startsWith("HETATM"))) continue;
          atomCount += 1;
          const atomName = ln.slice(12, 16).trim().toUpperCase();
          if (atomName === "CA") caCount += 1;
          if (atomName === "N") nCount += 1;
          if (atomName === "C") cCount += 1;
          if (atomName === "O") oCount += 1;
        }}
        return {{
          atomCount,
          caCount,
          nCount,
          cCount,
          oCount,
          caOnly: atomCount > 0 && atomCount === caCount,
          hasBackbone: (caCount > 0) && (nCount > 0) && (cCount > 0),
        }};
      }};

      const _mixHex = (h1, h2, t) => {{
        const a = parseInt(String(h1 || "000000").replace("#", ""), 16);
        const b = parseInt(String(h2 || "000000").replace("#", ""), 16);
        const ar = (a >> 16) & 255;
        const ag = (a >> 8) & 255;
        const ab = a & 255;
        const br = (b >> 16) & 255;
        const bg = (b >> 8) & 255;
        const bb = b & 255;
        const cl = (x) => Math.max(0, Math.min(255, Math.round(x)));
        const r = cl(ar + (br - ar) * t);
        const g = cl(ag + (bg - ag) * t);
        const z = cl(ab + (bb - ab) * t);
        return (r << 16) | (g << 8) | z;
      }};

      const _afLikeColorFromB = (bval) => {{
        const b = Number.isFinite(bval) ? bval : 50.0;
        const t = Math.max(0.0, Math.min(1.0, b / 100.0));
        if (t <= 0.33) return _mixHex("#0053D6", "#65CBF3", t / 0.33);
        if (t <= 0.66) return _mixHex("#65CBF3", "#FFDB13", (t - 0.33) / 0.33);
        return _mixHex("#FFDB13", "#FF7D45", (t - 0.66) / 0.34);
      }};
      const _afLikeColorFunc = (atom) => _afLikeColorFromB((atom && Number.isFinite(atom.b)) ? atom.b : 50.0);

      const _create3Dmol = (host) => {{
        host.innerHTML = "";
        return $3Dmol.createViewer(host, {{ backgroundColor: "white" }});
      }};

      const _load3Dmol = (targetViewer, item, withZoom) => {{
        if (!targetViewer || !item) return;
        const src = item.source || "other";
        const stats = _parsePdbStats(item.content || "");
        if (typeof targetViewer.removeAllSurfaces === "function") {{
          try {{
            targetViewer.removeAllSurfaces();
          }} catch (_e) {{}}
        }}
        targetViewer.clear();
        targetViewer.addModel(item.content, "pdb");
        if (src === "internal_postprocessed" || src === "internal_visual_refined") {{
          if (stats.hasBackbone) {{
            targetViewer.addStyle({{}}, {{
              cartoon: {{
                opacity: 0.98,
                thickness: 0.90,
                colorfunc: _afLikeColorFunc,
              }},
            }});
            targetViewer.addStyle({{ atom: "CA" }}, {{
              sphere: {{
                radius: 0.22,
                opacity: 0.32,
                colorfunc: _afLikeColorFunc,
              }},
            }});
          }} else {{
            targetViewer.addStyle({{}}, {{
              line: {{
                linewidth: 2.0,
                colorfunc: _afLikeColorFunc,
              }},
            }});
          }}
          targetViewer.addStyle({{ atom: "CA" }}, {{
            sphere: {{
              radius: stats.caOnly ? 0.40 : 0.26,
              opacity: stats.caOnly ? 0.92 : 0.65,
              colorfunc: _afLikeColorFunc,
            }},
          }});
        }} else {{
          targetViewer.addStyle({{}}, {{
            cartoon: {{ color: "spectrum", opacity: 0.98, thickness: 0.36 }},
          }});
          targetViewer.addStyle({{ hetero: true }}, {{
            stick: {{ radius: 0.16, opacity: 0.92 }},
          }});
          // For CA-only / no-backbone inputs, force visible CA geometry.
          if (stats.caOnly || (!stats.hasBackbone)) {{
            targetViewer.addStyle({{ atom: "CA" }}, {{
              sphere: {{
                radius: 0.42,
                opacity: 0.95,
                color: "#1f78ff",
              }},
            }});
            targetViewer.addStyle({{ atom: "CA" }}, {{
              line: {{
                linewidth: 2.2,
                color: "#1456a0",
              }},
            }});
          }}
        }}
        if (withZoom) {{
          targetViewer.zoomTo();
        }}
        targetViewer.render();
      }};

      const _createMolstar = (host) => {{
        host.innerHTML = "";
        return new window.molstar.Viewer(host, {{
          layoutIsExpanded: false,
          layoutShowControls: false,
          viewportShowExpand: false,
          collapseLeftPanel: true,
          showImportControls: false,
          showSessionControls: false,
          showMembraneOrientationPreset: false,
          pdbProvider: "rcsb",
          emdbProvider: "rcsb",
        }});
      }};

      const _loadMolstar = async (targetViewer, item, withZoom, epochToken) => {{
        if (!targetViewer || !item) return;
        if (typeof targetViewer.clear === "function") {{
          try {{
            await targetViewer.clear();
          }} catch (_e) {{}}
        }}
        try {{
          await targetViewer.loadStructureFromData(item.content, "pdb", false);
        }} catch (_e) {{
          await targetViewer.loadStructureFromData(item.content, "pdb");
        }}
        if (epochToken !== loadEpoch) return;
        if (withZoom) {{
          try {{
            const cam = targetViewer.plugin && targetViewer.plugin.managers && targetViewer.plugin.managers.camera;
            if (cam && typeof cam.reset === "function") {{
              cam.reset();
            }}
          }} catch (_e) {{}}
        }}
      }};

      const _switchTo3DmolFallback = () => {{
        activeEngine = "3dmol";
        viewer = _create3Dmol(viewerHost);
        if (modal.classList.contains("open")) {{
          modalViewer = _create3Dmol(modalHost);
        }} else {{
          modalViewer = null;
          modalHost.innerHTML = "";
        }}
      }};

      const _load = (targetViewer, item, withZoom) => {{
        if (!targetViewer || !item) return;
        if (activeEngine === "molstar") {{
          const token = ++loadEpoch;
          _loadMolstar(targetViewer, item, withZoom, token).catch((_err) => {{
            _switchTo3DmolFallback();
            setInfo(item);
            _load3Dmol(viewer, item, withZoom);
            if (modalViewer) _load3Dmol(modalViewer, item, withZoom);
          }});
          return;
        }}
        _load3Dmol(targetViewer, item, withZoom);
      }};

      const syncIndex = (i, withZoom=true) => {{
        if (!pdbs.length) return;
        const next = Math.max(0, Math.min(pdbs.length - 1, Number(i) || 0));
        currentIdx = next;
        if (String(select.value) !== String(next)) {{
          select.value = String(next);
        }}
        if (String(modalSelect.value) !== String(next)) {{
          modalSelect.value = String(next);
        }}
        const item = pdbs[next];
        setInfo(item);
        _renderMovieLinks(item);
        _load(viewer, item, withZoom);
        if (modalViewer) {{
          _load(modalViewer, item, withZoom);
        }}
      }};

      const ensureModalViewer = () => {{
        if (!modalViewer) {{
          if (activeEngine === "molstar") {{
            try {{
              modalViewer = _createMolstar(modalHost);
            }} catch (_e) {{
              _switchTo3DmolFallback();
            }}
          }}
          if (!modalViewer) {{
            modalViewer = _create3Dmol(modalHost);
          }}
        }}
        return modalViewer;
      }};

      const openModal = () => {{
        if (!pdbs.length) return;
        modal.classList.add("open");
        ensureModalViewer();
        syncIndex(currentIdx, true);
        setTimeout(() => {{
          if (activeEngine === "3dmol" && modalViewer && modalHost) {{
            modalViewer.resize();
            modalViewer.render();
          }}
        }}, 0);
      }};

      const closeModal = () => {{
        modal.classList.remove("open");
      }};

      if (!pdbs.length) {{
        select.disabled = true;
        modalSelect.disabled = true;
        openModalBtn.disabled = true;
        if (openMovieBtn) openMovieBtn.disabled = true;
        info.innerText = "No PDB files provided.";
        modalInfo.innerText = "No PDB files provided.";
        if (movieStatus) movieStatus.innerText = "Movie: no structure loaded.";
        if (movieLinks) movieLinks.innerHTML = "";
        viewerHost.innerHTML = "<div style='padding:12px;color:#5b6675'>No structure loaded.</div>";
        modalHost.innerHTML = "<div style='padding:12px;color:#5b6675'>No structure loaded.</div>";
        return;
      }}
      pdbs.forEach((p, i) => {{
        const src = p.source || "other";
        const opt = document.createElement("option");
        opt.value = String(i);
        opt.text = `[${{src}}] ${{p.name}}`;
        select.appendChild(opt);
        const opt2 = document.createElement("option");
        opt2.value = String(i);
        opt2.text = `[${{src}}] ${{p.name}}`;
        modalSelect.appendChild(opt2);
      }});

      if (activeEngine === "molstar") {{
        try {{
          viewer = _createMolstar(viewerHost);
        }} catch (_e) {{
          _switchTo3DmolFallback();
        }}
      }}
      if (!viewer) {{
        viewer = _create3Dmol(viewerHost);
      }}
      if (openMovieBtn) openMovieBtn.disabled = true;
      if (movieStatus && (!Array.isArray(movies) || movies.length === 0)) {{
        movieStatus.innerText = "Movie: no render manifest loaded.";
      }}

      select.addEventListener("change", () => syncIndex(parseInt(select.value, 10) || 0));
      modalSelect.addEventListener("change", () => syncIndex(parseInt(modalSelect.value, 10) || 0));
      openModalBtn.addEventListener("click", () => openModal());
      if (openMovieBtn) {{
        openMovieBtn.addEventListener("click", () => {{
          if (!currentMovie) return;
          const mp4 = String(currentMovie.mp4_path || "").trim();
          if (!mp4) return;
          const href = _toFileHref(mp4);
          if (href) window.open(href, "_blank", "noopener");
        }});
      }}
      closeModalBtn.addEventListener("click", () => closeModal());
      resetModalBtn.addEventListener("click", () => syncIndex(currentIdx, true));
      modal.addEventListener("click", (e) => {{
        if (e.target === modal) closeModal();
      }});
      window.addEventListener("keydown", (e) => {{
        if (e.key === "Escape" && modal.classList.contains("open")) {{
          closeModal();
        }}
      }});
      window.addEventListener("resize", () => {{
        if (activeEngine === "3dmol" && modalViewer && modal.classList.contains("open")) {{
          modalViewer.resize();
          modalViewer.render();
        }}
      }});

      const firstInternalIdx = pdbs.findIndex((x) => {{
        const src = (x && x.source) ? String(x.source) : "";
        return src === "internal_visual_refined" || src === "internal_postprocessed";
      }});
      const initialIdx = firstInternalIdx >= 0 ? firstInternalIdx : 0;
      syncIndex(initialIdx, true);
    }}

    renderKpi();
    renderDecisionBoard();
    renderMetricSummaryTable();
    buildPlots();
    buildPdbViewer();
  </script>
</body>
</html>
"""


def build_dashboard(args: argparse.Namespace) -> Dict[str, Any]:
    from_json_path = str(getattr(args, "from_json", "")).strip()
    if from_json_path:
        if not os.path.exists(from_json_path):
            raise FileNotFoundError(f"from-json not found: {from_json_path}")
        payload_raw = json.loads(open(from_json_path, "r", encoding="utf-8").read())
        if not isinstance(payload_raw, dict):
            raise ValueError(f"invalid dashboard payload JSON: {from_json_path}")
        payload: Dict[str, Any] = dict(payload_raw)
        title_override = str(getattr(args, "title", "")).strip()
        if title_override:
            payload["title"] = title_override
        viewer_engine_override = str(getattr(args, "viewer_engine", "")).strip().lower()
        if viewer_engine_override in {"auto", "3dmol", "molstar"}:
            payload["viewer_engine"] = viewer_engine_override
        if (args.movie_json or []) or (args.movie_csv or []):
            payload["movie_entries"] = _collect_movie_entries(
                movie_json_paths=args.movie_json or [],
                movie_csv_paths=args.movie_csv or [],
            )
            summary_i = payload.get("summary", {})
            if isinstance(summary_i, dict):
                movie_arr = payload.get("movie_entries", []) if isinstance(payload.get("movie_entries"), list) else []
                summary_i["movie_count"] = int(len(movie_arr))
                summary_i["movie_ready_count"] = int(sum(1 for x in movie_arr if bool(x.get("has_mp4", False))))

        out_html = str(getattr(args, "out_html", "")).strip() or f"{os.path.splitext(from_json_path)[0]}.html"
        os.makedirs(os.path.dirname(out_html) or ".", exist_ok=True)
        with open(out_html, "w", encoding="utf-8") as f:
            f.write(_render_html(payload))

        out_json = str(getattr(args, "out_json", "")).strip()
        if out_json:
            os.makedirs(os.path.dirname(out_json) or ".", exist_ok=True)
            with open(out_json, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)

        runs_arr = payload.get("runs", []) if isinstance(payload.get("runs"), list) else []
        metrics_arr = payload.get("metrics", []) if isinstance(payload.get("metrics"), list) else []
        pdb_arr = payload.get("pdb_entries", []) if isinstance(payload.get("pdb_entries"), list) else []
        movie_arr = payload.get("movie_entries", []) if isinstance(payload.get("movie_entries"), list) else []
        thresholds_map = payload.get("thresholds", {}) if isinstance(payload.get("thresholds"), dict) else {}
        return {
            "out_html": out_html,
            "out_json": out_json if out_json else None,
            "runs": int(len(runs_arr)),
            "metrics": metrics_arr,
            "pdb_entries": int(len(pdb_arr)),
            "movie_entries": int(len(movie_arr)),
            "thresholds": thresholds_map,
            "summary": payload.get("summary", {}),
            "from_json": from_json_path,
        }

    csv_inputs: List[str] = []
    for c in args.csv:
        token = str(c).strip()
        if token:
            csv_inputs.append(token)
    if str(args.compare_csv).strip():
        csv_inputs.append(str(args.compare_csv).strip())
    if not csv_inputs:
        raise ValueError("at least one --csv is required")

    labels: List[str] = []
    if args.labels:
        labels = [str(x).strip() for x in args.labels if str(x).strip()]
    while len(labels) < len(csv_inputs):
        labels.append(f"run_{len(labels)+1}")

    first_df = pd.read_csv(csv_inputs[0])
    metrics = _select_metrics(
        first_df,
        metric_spec=str(args.metrics),
        max_metrics=int(args.max_metrics),
    )
    if not metrics:
        raise ValueError(f"no usable numeric metrics found in {csv_inputs[0]}")

    run_series: List[RunSeries] = []
    target_filters: List[str] = [str(t).strip() for t in (args.target or []) if str(t).strip()]
    for idx, csv_path in enumerate(csv_inputs):
        run_series.append(
            _load_run_series(
                csv_path=csv_path,
                label=labels[idx],
                x_col=str(args.x_col),
                metrics=metrics,
                max_rows=int(args.max_rows),
                targets=target_filters,
                target_col=str(args.target_col),
            )
        )

    thresholds = _extract_gate_thresholds(str(args.gate_json))
    thresholds.update(_parse_threshold_pairs(args.threshold or []))
    movie_entries = _collect_movie_entries(
        movie_json_paths=args.movie_json or [],
        movie_csv_paths=args.movie_csv or [],
    )
    pdb_entries = _collect_pdb_entries(
        pdb_files=args.pdb or [],
        pdb_glob=args.pdb_glob or [],
        max_pdb=int(args.max_pdb),
    )
    payload = _build_payload(
        runs=run_series,
        metrics=metrics,
        thresholds=thresholds,
        pdb_entries=pdb_entries,
        movie_entries=movie_entries,
        target_filters=target_filters,
        title=str(args.title),
        viewer_engine=str(getattr(args, "viewer_engine", "auto")),
    )
    decision_board = _build_decision_board(
        csv_inputs=csv_inputs,
        labels=labels,
        metrics=metrics,
        x_col=str(args.x_col),
        target_col=str(args.target_col),
        target_filters=target_filters,
        thresholds=thresholds,
        topk_targets=int(args.decision_topk_targets),
    )
    summary_i = payload.get("summary", {})
    if isinstance(summary_i, dict):
        summary_i["decision_board"] = decision_board
    else:
        payload["summary"] = {"decision_board": decision_board}

    out_html = str(args.out_html).strip() or f"runs/experiment_dashboard_{dt.date.today().isoformat()}.html"
    os.makedirs(os.path.dirname(out_html) or ".", exist_ok=True)
    with open(out_html, "w", encoding="utf-8") as f:
        f.write(_render_html(payload))

    out_json = str(args.out_json).strip() or f"runs/experiment_dashboard_{dt.date.today().isoformat()}.json"
    if out_json:
        os.makedirs(os.path.dirname(out_json) or ".", exist_ok=True)
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

    return {
        "out_html": out_html,
        "out_json": out_json if out_json else None,
        "runs": len(run_series),
        "metrics": metrics,
        "pdb_entries": len(pdb_entries),
        "movie_entries": len(movie_entries),
        "thresholds": thresholds,
        "summary": payload.get("summary", {}),
    }


def build_parser() -> argparse.ArgumentParser:
    stamp = dt.date.today().isoformat()
    p = argparse.ArgumentParser(
        description="Generate a local HTML dashboard for experiment CSV metrics and PDB structures."
    )
    p.add_argument("--from-json", type=str, default="", help="Rebuild dashboard HTML from an existing payload JSON.")
    p.add_argument("--csv", action="append", default=[], help="Primary CSV(s). Use multiple times for multi-run compare.")
    p.add_argument("--compare-csv", type=str, default="", help="Optional second run CSV.")
    p.add_argument("--labels", action="append", default=[], help="Label for each run in order of --csv.")
    p.add_argument("--pdb", action="append", default=[], help="PDB file(s) to render in 3D viewer.")
    p.add_argument("--pdb-glob", action="append", default=[], help="Glob pattern(s) for PDB files.")
    p.add_argument("--movie-json", action="append", default=[], help="Optional ChimeraX render summary JSON(s).")
    p.add_argument("--movie-csv", action="append", default=[], help="Optional ChimeraX render report CSV(s).")
    p.add_argument("--metrics", type=str, default="auto", help="Comma-separated metrics or auto.")
    p.add_argument("--x-col", type=str, default="auto", help="X-axis column (auto picks step/frame/index).")
    p.add_argument(
        "--target",
        action="append",
        default=[],
        help="Optional target filter (repeatable). Requires target column in CSV.",
    )
    p.add_argument("--target-col", type=str, default="target", help="Target column name for --target filter.")
    p.add_argument("--max-metrics", type=int, default=12)
    p.add_argument("--max-rows", type=int, default=2000)
    p.add_argument("--max-pdb", type=int, default=12)
    p.add_argument(
        "--viewer-engine",
        type=str,
        default="auto",
        choices=["auto", "3dmol", "molstar"],
        help="3D viewer engine for PDB panel. auto tries Mol* first and falls back to 3Dmol.",
    )
    p.add_argument("--gate-json", type=str, default="", help="Gate summary JSON to auto-load thresholds.")
    p.add_argument("--threshold", action="append", default=[], help="Manual threshold: metric=value")
    p.add_argument("--decision-topk-targets", type=int, default=8)
    p.add_argument("--title", type=str, default="MD Experiment Dashboard")
    p.add_argument(
        "--out-html",
        type=str,
        default="",
        help=f"Output HTML path (default: runs/experiment_dashboard_{stamp}.html or from-json basename).",
    )
    p.add_argument(
        "--out-json",
        type=str,
        default="",
        help=f"Optional output JSON path (default: runs/experiment_dashboard_{stamp}.json in CSV mode).",
    )
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    payload = build_dashboard(args)
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
