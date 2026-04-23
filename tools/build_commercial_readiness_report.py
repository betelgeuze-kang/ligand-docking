#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import datetime as dt
import glob
import json
import os
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd


def _safe_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except Exception:
        return None


def _read_json_if_exists(path: str) -> Dict[str, Any]:
    src = str(path).strip()
    if (not src) or (not os.path.exists(src)):
        return {}
    try:
        with open(src, "r", encoding="utf-8") as f:
            payload = json.load(f)
        if isinstance(payload, dict):
            return payload
    except Exception:
        return {}
    return {}


def _read_csv_if_exists(path: str) -> pd.DataFrame:
    src = str(path).strip()
    if (not src) or (not os.path.exists(src)):
        return pd.DataFrame()
    try:
        return pd.read_csv(src)
    except Exception:
        return pd.DataFrame()


def _latest_existing(patterns: Sequence[str]) -> Optional[str]:
    matches: List[str] = []
    for pat in patterns:
        matches.extend(glob.glob(str(pat)))
    matches = sorted(set(matches), key=lambda p: os.path.getmtime(p) if os.path.exists(p) else 0.0)
    return str(matches[-1]) if matches else None


def _all_existing(patterns: Sequence[str]) -> List[str]:
    matches: List[str] = []
    for pat in patterns:
        matches.extend(glob.glob(str(pat)))
    uniq = sorted(set(matches), key=lambda p: os.path.getmtime(p) if os.path.exists(p) else 0.0)
    return [str(x) for x in uniq if os.path.exists(str(x))]


def _resolve_or_latest(path: str, patterns: Sequence[str], *, auto_discovery: bool = True) -> Optional[str]:
    src = str(path).strip()
    if not auto_discovery:
        return src if (src and os.path.exists(src)) else None
    if src:
        if os.path.exists(src):
            return src
        base = os.path.basename(src)
        if base:
            found = _latest_existing([f"runs/**/{base}"])
            if found:
                return found
        return _latest_existing(patterns)
    return _latest_existing(patterns)


def _extract_strict_pass(strict_payload: Dict[str, Any]) -> Optional[bool]:
    if not strict_payload:
        return None
    summary = strict_payload.get("summary", {})
    if isinstance(summary, dict) and ("pass" in summary):
        return bool(summary.get("pass"))
    if "pass" in strict_payload:
        return bool(strict_payload.get("pass"))
    return None


def _extract_speedup(strict_payload: Dict[str, Any]) -> Optional[float]:
    if not strict_payload:
        return None
    gates = strict_payload.get("gates", {})
    if isinstance(gates, dict):
        speed = gates.get("speed", {})
        if isinstance(speed, dict):
            for key in ("avg_speedup_on_vs_off", "speedup", "value"):
                fv = _safe_float(speed.get(key))
                if fv is not None:
                    return float(fv)
    summary = strict_payload.get("summary", {})
    if isinstance(summary, dict):
        for key in ("avg_speedup_on_vs_off", "speedup"):
            fv = _safe_float(summary.get(key))
            if fv is not None:
                return float(fv)
    return None


def _extract_speed_enforced(strict_payload: Dict[str, Any]) -> Optional[bool]:
    if not strict_payload:
        return None
    gates = strict_payload.get("gates", {})
    if isinstance(gates, dict):
        speed = gates.get("speed", {})
        if isinstance(speed, dict) and ("enforced" in speed):
            return bool(speed.get("enforced"))
    return None


def _extract_strict_targets(strict_payload: Dict[str, Any]) -> Optional[int]:
    if not strict_payload:
        return None
    summary = strict_payload.get("summary", {})
    if isinstance(summary, dict):
        v = _safe_float(summary.get("targets"))
        if v is not None:
            return int(v)
    return None


def _is_smoke_path(path: str) -> bool:
    name = os.path.basename(str(path).strip()).lower()
    return ("smoke" in name) or ("_r1" in name and "full" not in name)


def _choose_strict_release_path(
    *,
    explicit_path: str,
    nightly_payload: Dict[str, Any],
    packet_payload: Dict[str, Any],
    auto_discovery: bool,
    strict_source_policy: str,
) -> Tuple[Optional[str], List[Dict[str, Any]]]:
    candidates: List[Dict[str, Any]] = []
    seen: set[str] = set()

    def _append(path: Optional[str], source: str) -> None:
        p = str(path or "").strip()
        if (not p) or (not os.path.exists(p)) or (p in seen):
            return
        seen.add(p)
        payload = _read_json_if_exists(p)
        rec = {
            "path": p,
            "source": str(source),
            "targets": _extract_strict_targets(payload),
            "pass": _extract_strict_pass(payload),
            "speed_enforced": _extract_speed_enforced(payload),
            "is_smoke_path": _is_smoke_path(p),
            "mtime": float(os.path.getmtime(p)),
        }
        candidates.append(rec)

    _append(explicit_path, "explicit")

    if isinstance(nightly_payload, dict):
        nightly_paths = nightly_payload.get("paths", {})
        if isinstance(nightly_paths, dict):
            _append(nightly_paths.get("strict_summary_json"), "nightly.paths.strict_summary_json")
    if isinstance(packet_payload, dict):
        src = packet_payload.get("sources", {})
        if isinstance(src, dict):
            _append(src.get("strict_release_summary_json"), "packet.sources.strict_release_summary_json")
    if bool(auto_discovery):
        for p in _all_existing(
            [
                "runs/openmm_2bead_strict_*_summary.json",
                "runs/external_eval_submission/**/openmm_2bead_strict_*_summary.json",
            ]
        ):
            _append(p, "auto_discovery")

    if len(candidates) <= 0:
        return None, []

    policy = str(strict_source_policy).strip().lower()

    def _rank(rec: Dict[str, Any]) -> Tuple[int, int, int, int, float]:
        targets = rec.get("targets")
        full_target = 1 if (isinstance(targets, int) and int(targets) >= 10) else 0
        not_smoke = 1 if (not bool(rec.get("is_smoke_path", False))) else 0
        pass_ok = 1 if rec.get("pass") is True else 0
        speed_enforced = 1 if rec.get("speed_enforced") is True else 0
        mtime = float(rec.get("mtime", 0.0) or 0.0)
        return (full_target, not_smoke, pass_ok, speed_enforced, mtime)

    chosen: Optional[Dict[str, Any]] = None
    if policy == "full_only":
        full_pool = [
            rec
            for rec in candidates
            if (isinstance(rec.get("targets"), int) and int(rec.get("targets")) >= 10)
            and (not bool(rec.get("is_smoke_path", False)))
        ]
        if len(full_pool) > 0:
            chosen = sorted(full_pool, key=_rank)[-1]
    elif policy == "prefer_full":
        chosen = sorted(candidates, key=_rank)[-1]
    else:
        chosen = sorted(candidates, key=lambda r: float(r.get("mtime", 0.0)))[-1]

    if chosen is None:
        # Fallback: keep behavior non-breaking if full-only has no match.
        chosen = sorted(candidates, key=lambda r: float(r.get("mtime", 0.0)))[-1]
    return str(chosen.get("path", "")), candidates


def _extract_accuracy_gate_pass(strict_payload: Dict[str, Any]) -> Optional[bool]:
    if not strict_payload:
        return None
    gates = strict_payload.get("gates", {})
    if isinstance(gates, dict):
        acc = gates.get("accuracy_gate", {})
        if isinstance(acc, dict) and ("pass" in acc):
            return bool(acc.get("pass"))
    summary = strict_payload.get("summary", {})
    if isinstance(summary, dict):
        failed = summary.get("failed_gates", [])
        if isinstance(failed, list):
            return "accuracy_gate" not in [str(x) for x in failed]
    return None


def _extract_dashboard_counts(dashboard_payload: Dict[str, Any]) -> Tuple[int, int, int]:
    if not dashboard_payload:
        return (0, 0, 0)
    summary = dashboard_payload.get("summary", {})
    if isinstance(summary, dict):
        metric_count = int(_safe_float(summary.get("metric_count")) or 0)
        run_count = int(_safe_float(summary.get("run_count")) or 0)
        pdb_count = int(_safe_float(summary.get("pdb_count")) or 0)
        if metric_count > 0 or run_count > 0 or pdb_count > 0:
            return (metric_count, run_count, pdb_count)
    metrics = dashboard_payload.get("metrics", [])
    runs = dashboard_payload.get("runs", [])
    pdb_entries = dashboard_payload.get("pdb_entries", [])
    return (
        int(len(metrics)) if isinstance(metrics, list) else 0,
        int(len(runs)) if isinstance(runs, list) else 0,
        int(len(pdb_entries)) if isinstance(pdb_entries, list) else 0,
    )


def _extract_external_targets(packet_payload: Dict[str, Any]) -> Optional[int]:
    if not packet_payload:
        return None
    gs = packet_payload.get("global_summary", {})
    if not isinstance(gs, dict):
        return None
    ext = gs.get("external_md_accuracy", {})
    if isinstance(ext, dict):
        for key in (
            "external_targets_with_reference",
            "targets_with_reference",
            "targets_with_external_reference",
        ):
            v = _safe_float(ext.get(key))
            if v is not None:
                return int(v)
    return None


def _extract_stage2_tail_stats(stage2_df: pd.DataFrame) -> Dict[str, Optional[float]]:
    out = {
        "speedup_p95": None,
        "speedup_worst": None,
    }
    if stage2_df is None or stage2_df.empty or ("speedup_on_vs_off" not in stage2_df.columns):
        return out
    s = pd.to_numeric(stage2_df["speedup_on_vs_off"], errors="coerce").dropna()
    if s.empty:
        return out
    vals = s.to_numpy(dtype=np.float64)
    out["speedup_p95"] = float(np.quantile(vals, 0.95))
    out["speedup_worst"] = float(np.min(vals))
    return out


def _summarize_stage2_candidate(path: str) -> Dict[str, Any]:
    rec: Dict[str, Any] = {
        "path": str(path),
        "rows": 0,
        "targets": 0,
        "speed_rows": 0,
        "is_smoke_path": _is_smoke_path(path),
        "mtime": float(os.path.getmtime(path)) if os.path.exists(path) else 0.0,
    }
    df = _read_csv_if_exists(path)
    if df.empty:
        return rec
    rec["rows"] = int(df.shape[0])
    if "target" in df.columns:
        rec["targets"] = int(df["target"].astype(str).nunique())
    if "speedup_on_vs_off" in df.columns:
        s = pd.to_numeric(df["speedup_on_vs_off"], errors="coerce").dropna()
        rec["speed_rows"] = int(s.shape[0])
    return rec


def _choose_stage2_csv_path(
    *,
    explicit_path: str,
    nightly_payload: Dict[str, Any],
    packet_payload: Dict[str, Any],
    auto_discovery: bool,
    strict_source_policy: str,
) -> Tuple[Optional[str], List[Dict[str, Any]]]:
    candidates: List[Dict[str, Any]] = []
    seen: set[str] = set()

    source_rank = {
        "explicit": 4,
        "nightly.paths.rebench_prefix": 3,
        "nightly.resolved_inputs.active_learning_stage2_csv": 3,
        "packet.sources.stage2_csv": 2,
        "auto_discovery": 1,
    }

    def _append(path: Optional[str], source: str) -> None:
        p = str(path or "").strip()
        if (not p) or (not os.path.exists(p)) or (p in seen):
            return
        seen.add(p)
        rec = _summarize_stage2_candidate(p)
        rec["source"] = str(source)
        rec["source_rank"] = int(source_rank.get(str(source), 0))
        candidates.append(rec)

    _append(explicit_path, "explicit")

    if isinstance(nightly_payload, dict):
        nightly_paths = nightly_payload.get("paths", {})
        if isinstance(nightly_paths, dict):
            rp = str(nightly_paths.get("rebench_prefix", "")).strip()
            if rp:
                _append(f"{rp}_stage2.csv", "nightly.paths.rebench_prefix")
        resolved = nightly_payload.get("resolved_inputs", {})
        if isinstance(resolved, dict):
            _append(
                resolved.get("active_learning_stage2_csv"),
                "nightly.resolved_inputs.active_learning_stage2_csv",
            )

    if isinstance(packet_payload, dict):
        src = packet_payload.get("sources", {})
        if isinstance(src, dict):
            _append(src.get("stage2_csv"), "packet.sources.stage2_csv")

    if bool(auto_discovery):
        for p in _all_existing(["runs/stage2_*.csv", "runs/*_stage2.csv", "runs/**/*_stage2.csv"]):
            _append(p, "auto_discovery")

    if len(candidates) <= 0:
        return None, []

    policy = str(strict_source_policy).strip().lower()

    def _rank(rec: Dict[str, Any]) -> Tuple[int, int, int, int, int, float]:
        targets = int(rec.get("targets", 0) or 0)
        speed_rows = int(rec.get("speed_rows", 0) or 0)
        full_target = 1 if targets >= 10 else 0
        not_smoke = 1 if (not bool(rec.get("is_smoke_path", False))) else 0
        has_speed = 1 if speed_rows > 0 else 0
        src = int(rec.get("source_rank", 0) or 0)
        mtime = float(rec.get("mtime", 0.0) or 0.0)
        return (full_target, not_smoke, has_speed, speed_rows, src, mtime)

    chosen: Optional[Dict[str, Any]] = None
    if policy == "full_only":
        full_pool = [c for c in candidates if int(c.get("targets", 0) or 0) >= 10]
        if full_pool:
            chosen = sorted(full_pool, key=_rank)[-1]
    elif policy == "prefer_full":
        chosen = sorted(candidates, key=_rank)[-1]
    else:
        chosen = sorted(candidates, key=lambda r: float(r.get("mtime", 0.0) or 0.0))[-1]

    if chosen is None:
        chosen = sorted(candidates, key=_rank)[-1]
    return str(chosen.get("path", "")), candidates


def _extract_trajectory_tail_stats(traj_tail_df: pd.DataFrame) -> Dict[str, Optional[float]]:
    out = {
        "fps_p05": None,
        "fps_worst": None,
    }
    if traj_tail_df is None or traj_tail_df.empty:
        return out
    fps_p05_col = "fps_p05" if "fps_p05" in traj_tail_df.columns else None
    fps_worst_col = "fps_min" if "fps_min" in traj_tail_df.columns else None
    if fps_p05_col is not None:
        s = pd.to_numeric(traj_tail_df[fps_p05_col], errors="coerce").dropna()
        if not s.empty:
            out["fps_p05"] = float(np.min(s.to_numpy(dtype=np.float64)))
    if fps_worst_col is not None:
        s = pd.to_numeric(traj_tail_df[fps_worst_col], errors="coerce").dropna()
        if not s.empty:
            out["fps_worst"] = float(np.min(s.to_numpy(dtype=np.float64)))
    return out


def _extract_accuracy_tail_stats(acc_df: pd.DataFrame) -> Dict[str, Optional[float]]:
    out = {
        "rmsd_p95": None,
        "rmsd_worst": None,
    }
    if acc_df is None or acc_df.empty:
        return out
    for c in ("avg_rmsd_aligned", "avg_rmsd", "rmsd"):
        if c in acc_df.columns:
            s = pd.to_numeric(acc_df[c], errors="coerce").dropna()
            if s.empty:
                continue
            vals = s.to_numpy(dtype=np.float64)
            out["rmsd_p95"] = float(np.quantile(vals, 0.95))
            out["rmsd_worst"] = float(np.max(vals))
            return out
    return out


def _extract_feature_quality(feature_df: pd.DataFrame) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "rows": 0,
        "targets": 0,
        "max_missing_rate": None,
        "variable_cols_count": 0,
        "constant_flag_cols_count": 0,
        "constant_flag_cols": [],
        "evaluated_cols": [],
    }
    if feature_df is None or feature_df.empty:
        return out
    out["rows"] = int(feature_df.shape[0])
    if "target" in feature_df.columns:
        out["targets"] = int(feature_df["target"].astype(str).nunique())
    control_cols_new = [
        "control_ionic_strength",
        "control_ptm_count",
        "control_cooling_rate",
        "control_hydro_strength",
        "control_force_scale_mult",
        "control_temperature_start",
        "control_temperature_end",
    ]
    control_flag_cols_new = [
        "control_ionic_strength",
        "control_ptm_count",
        "control_cooling_rate",
        "control_hydro_strength",
        "control_force_scale_mult",
        "control_temperature_end",
    ]
    control_cols_legacy = [
        "ionic_strength",
        "ptm_count",
        "cooling_rate",
        "hydro_strength",
    ]
    observed_cols = [
        "observed_is_llps",
        "observed_is_folded",
        "observed_rmsd",
        "observed_violations",
        "is_llps",
        "is_folded",
        "rmsd",
        "violations",
    ]
    eval_cols = [
        "energy",
        "Rg",
        "compactness",
        "sasa",
        "cluster_max",
        "rmsd",
        "force_scale",
        "k_angle",
        "theta0",
        "k_dihedral",
        "phi0_alpha",
        *observed_cols,
        *control_cols_new,
        *control_cols_legacy,
    ]
    eval_cols = [c for c in dict.fromkeys(eval_cols) if c in feature_df.columns]
    out["evaluated_cols"] = eval_cols
    if len(eval_cols) <= 0:
        return out
    miss_rates: List[float] = []
    variable_cols = 0
    flag_cols = [c for c in control_flag_cols_new if c in feature_df.columns]
    if not flag_cols:
        flag_cols = [c for c in control_cols_legacy if c in feature_df.columns]
    out["control_flag_cols_evaluated"] = flag_cols
    constant_flags: List[str] = []
    for c in eval_cols:
        s = feature_df[c]
        miss = float(s.isna().mean())
        miss_rates.append(miss)
        uniq = int(s.nunique(dropna=True))
        if uniq > 1:
            variable_cols += 1
        if c in flag_cols and uniq <= 1:
            constant_flags.append(c)
    out["max_missing_rate"] = float(max(miss_rates)) if miss_rates else None
    out["variable_cols_count"] = int(variable_cols)
    out["constant_flag_cols_count"] = int(len(constant_flags))
    out["constant_flag_cols"] = constant_flags
    return out


def _build_check(
    name: str,
    value: Any,
    threshold: Any,
    passed: Optional[bool],
    source: Optional[str],
    note: str = "",
) -> Dict[str, Any]:
    status = "na"
    if passed is True:
        status = "pass"
    elif passed is False:
        status = "fail"
    return {
        "check": str(name),
        "status": status,
        "pass": passed,
        "value": value,
        "threshold": threshold,
        "source": source,
        "note": str(note),
    }


def _tier(score: float, critical_pass: bool, considered: int) -> str:
    if considered <= 0:
        return "insufficient_evidence"
    if score >= 90.0 and critical_pass:
        return "commercial_candidate"
    if score >= 75.0:
        return "pilot_ready"
    if score >= 60.0:
        return "prototype_ready"
    return "research_only"


def build_report(args: argparse.Namespace) -> Dict[str, Any]:
    auto_discovery = not bool(getattr(args, "disable_auto_discovery", False))
    nightly_path = _resolve_or_latest(
        str(args.nightly_summary_json),
        patterns=["runs/nightly_screening_batch_*.json"],
        auto_discovery=auto_discovery,
    )
    dashboard_path = _resolve_or_latest(
        str(args.dashboard_json),
        patterns=["runs/experiment_dashboard_nightly_*.json", "runs/experiment_dashboard_*.json"],
        auto_discovery=auto_discovery,
    )
    packet_path = _resolve_or_latest(
        str(args.external_packet_json),
        patterns=["runs/external_eval_packet_v3_nightly_*.json", "runs/external_eval_packet_*.json"],
        auto_discovery=auto_discovery,
    )

    nightly = _read_json_if_exists(nightly_path or "")
    packet = _read_json_if_exists(packet_path or "")

    strict_path, strict_candidates = _choose_strict_release_path(
        explicit_path=str(args.strict_release_summary_json),
        nightly_payload=nightly,
        packet_payload=packet,
        auto_discovery=auto_discovery,
        strict_source_policy=str(args.strict_source_policy),
    )

    strict = _read_json_if_exists(strict_path or "")
    dashboard = _read_json_if_exists(dashboard_path or "")
    packet_sources = packet.get("sources", {}) if isinstance(packet.get("sources"), dict) else {}
    stage2_path, stage2_candidates = _choose_stage2_csv_path(
        explicit_path=str(args.stage2_csv),
        nightly_payload=nightly,
        packet_payload=packet,
        auto_discovery=auto_discovery,
        strict_source_policy=str(args.strict_source_policy),
    )
    accuracy_external_path = _resolve_or_latest(
        str(args.accuracy_external_csv),
        patterns=["runs/accuracy_external*.csv", "runs/*_accuracy_external.csv"],
        auto_discovery=auto_discovery,
    )
    if (not accuracy_external_path) and isinstance(packet_sources, dict):
        ap = str(packet_sources.get("accuracy_external_csv", "")).strip()
        if ap:
            accuracy_external_path = _resolve_or_latest(ap, patterns=[], auto_discovery=False)
    stage2_df = _read_csv_if_exists(stage2_path or "")
    accuracy_external_df = _read_csv_if_exists(accuracy_external_path or "")
    feature_path = _resolve_or_latest(
        str(args.feature_csv),
        patterns=["runs/feature_matrix_per_target_nightly_*.csv", "runs/feature_matrix_per_target*.csv"],
        auto_discovery=auto_discovery,
    )
    if (not feature_path) and isinstance(packet_sources, dict):
        fp = str(packet_sources.get("feature_csv", "")).strip()
        if fp:
            feature_path = _resolve_or_latest(fp, patterns=[], auto_discovery=False)
    feature_df = _read_csv_if_exists(feature_path or "")
    trajectory_tail_path = _resolve_or_latest(
        str(args.trajectory_target_tail_csv),
        patterns=[
            "runs/*_stage2_traj_frames_target_tail.csv",
            "runs/**/*_stage2_traj_frames_target_tail.csv",
            "runs/*target_tail.csv",
            "runs/**/*target_tail.csv",
        ],
        auto_discovery=auto_discovery,
    )
    trajectory_tail_df = _read_csv_if_exists(trajectory_tail_path or "")
    speedup_threshold = float(args.speedup_threshold)
    speedup_p95_threshold = (
        float(args.speedup_p95_threshold)
        if args.speedup_p95_threshold is not None
        else speedup_threshold
    )
    speedup_worst_threshold = (
        float(args.speedup_worst_threshold)
        if args.speedup_worst_threshold is not None
        else speedup_threshold
    )
    max_rmsd_p95_a = float(args.max_rmsd_p95_a)
    max_rmsd_worst_a = float(args.max_rmsd_worst_a)
    min_dashboard_metrics = int(args.min_dashboard_metrics)
    min_dashboard_runs = int(args.min_dashboard_runs)
    min_external_targets = int(args.min_external_targets)

    checks: List[Dict[str, Any]] = []

    nightly_pass = None
    if nightly:
        nightly_pass = bool(nightly.get("pass")) if "pass" in nightly else None
    checks.append(
        _build_check(
            "nightly_pass",
            nightly_pass,
            True,
            nightly_pass,
            nightly_path,
            "nightly 전체 파이프라인 통과 여부",
        )
    )

    strict_pass = _extract_strict_pass(strict)
    checks.append(
        _build_check(
            "strict_release_pass",
            strict_pass,
            True,
            strict_pass,
            strict_path,
            "엄격 릴리즈 게이트 통과 여부",
        )
    )

    speedup = _extract_speedup(strict)
    speed_pass = None if speedup is None else bool(speedup >= speedup_threshold)
    checks.append(
        _build_check(
            "speed_gate",
            speedup,
            speedup_threshold,
            speed_pass,
            strict_path,
            "상용화 최소 속도 하한",
        )
    )
    speed_enforced = _extract_speed_enforced(strict)
    checks.append(
        _build_check(
            "speed_gate_enforced",
            speed_enforced,
            True,
            speed_enforced,
            strict_path,
            "strict speed gate가 실제 enforce 모드로 측정되었는지",
        )
    )

    stage2_tail = _extract_stage2_tail_stats(stage2_df)
    speedup_p95 = stage2_tail.get("speedup_p95")
    speedup_worst = stage2_tail.get("speedup_worst")
    speedup_p95_pass = None if speedup_p95 is None else bool(float(speedup_p95) >= speedup_p95_threshold)
    speedup_worst_pass = (
        None if speedup_worst is None else bool(float(speedup_worst) >= speedup_worst_threshold)
    )
    checks.append(
        _build_check(
            "speed_tail_p95",
            speedup_p95,
            speedup_p95_threshold,
            speedup_p95_pass,
            stage2_path,
            "stage2 speedup_on_vs_off 분포 p95",
        )
    )
    checks.append(
        _build_check(
            "speed_tail_worst_target",
            speedup_worst,
            speedup_worst_threshold,
            speedup_worst_pass,
            stage2_path,
            "stage2 speedup_on_vs_off 최악 타깃",
        )
    )
    traj_tail = _extract_trajectory_tail_stats(trajectory_tail_df)
    traj_fps_p05 = traj_tail.get("fps_p05")
    traj_fps_worst = traj_tail.get("fps_worst")
    traj_fps_p05_threshold = (
        float(args.traj_fps_p05_threshold)
        if args.traj_fps_p05_threshold is not None
        else None
    )
    traj_fps_worst_threshold = (
        float(args.traj_fps_worst_threshold)
        if args.traj_fps_worst_threshold is not None
        else None
    )
    traj_fps_p05_pass = (
        None
        if (traj_fps_p05 is None or traj_fps_p05_threshold is None)
        else bool(float(traj_fps_p05) >= float(traj_fps_p05_threshold))
    )
    traj_fps_worst_pass = (
        None
        if (traj_fps_worst is None or traj_fps_worst_threshold is None)
        else bool(float(traj_fps_worst) >= float(traj_fps_worst_threshold))
    )
    checks.append(
        _build_check(
            "trajectory_tail_fps_p05",
            traj_fps_p05,
            traj_fps_p05_threshold,
            traj_fps_p05_pass,
            trajectory_tail_path,
            "trajectory target-tail CSV 기준 fps_p05 최저값",
        )
    )
    checks.append(
        _build_check(
            "trajectory_tail_fps_worst_target",
            traj_fps_worst,
            traj_fps_worst_threshold,
            traj_fps_worst_pass,
            trajectory_tail_path,
            "trajectory target-tail CSV 기준 fps_min 최저값",
        )
    )

    acc_pass = _extract_accuracy_gate_pass(strict)
    checks.append(
        _build_check(
            "accuracy_gate_pass",
            acc_pass,
            True,
            acc_pass,
            strict_path,
            "정확도 게이트 통과",
        )
    )

    long_stability = None
    long_status = nightly.get("long_stability_status", {}) if isinstance(nightly, dict) else {}
    if isinstance(long_status, dict) and ("pass" in long_status):
        long_stability = bool(long_status.get("pass"))
    checks.append(
        _build_check(
            "long_stability_pass",
            long_stability,
            True,
            long_stability,
            nightly_path,
            "장기 안정성 게이트",
        )
    )

    claim_ready = None
    claim_status = nightly.get("claim_status", {}) if isinstance(nightly, dict) else {}
    if isinstance(claim_status, dict):
        if "initial_claim_ready_for_allatom" in claim_status:
            claim_ready = bool(claim_status.get("initial_claim_ready_for_allatom"))
        elif "claim_ready_for_allatom" in claim_status:
            claim_ready = bool(claim_status.get("claim_ready_for_allatom"))
    checks.append(
        _build_check(
            "allatom_claim_ready",
            claim_ready,
            True,
            claim_ready,
            nightly_path,
            "all-atom 동등성 claim 준비도",
        )
    )

    special_case_pass = None
    special_case_status = nightly.get("special_case_status", {}) if isinstance(nightly, dict) else {}
    if isinstance(special_case_status, dict) and ("pass" in special_case_status):
        special_case_pass = bool(special_case_status.get("pass"))
    checks.append(
        _build_check(
            "special_case_pass",
            special_case_pass,
            True,
            special_case_pass,
            nightly_path,
            "metal/dna/membrane 특이케이스 게이트",
        )
    )

    ood_pass = None
    ood_status = nightly.get("ood_measured20_status", {}) if isinstance(nightly, dict) else {}
    if isinstance(ood_status, dict) and ("pass" in ood_status):
        ood_pass = bool(ood_status.get("pass"))
    checks.append(
        _build_check(
            "ood_measured20_pass",
            ood_pass,
            True,
            ood_pass,
            nightly_path,
            "실측 OOD 검증",
        )
    )

    metric_count, run_count, pdb_count = _extract_dashboard_counts(dashboard)
    dashboard_ready = bool(metric_count >= min_dashboard_metrics and run_count >= min_dashboard_runs)
    checks.append(
        _build_check(
            "dashboard_ready",
            {"metrics": metric_count, "runs": run_count, "pdb": pdb_count},
            {"min_metrics": min_dashboard_metrics, "min_runs": min_dashboard_runs},
            dashboard_ready if dashboard else None,
            dashboard_path,
            "외부 검토용 시각화 최소 기준",
        )
    )

    ext_targets = _extract_external_targets(packet)
    ext_ready = None if ext_targets is None else bool(ext_targets >= min_external_targets)
    checks.append(
        _build_check(
            "external_packet_targets",
            ext_targets,
            min_external_targets,
            ext_ready,
            packet_path,
            "외부 기준 비교 타깃 수",
        )
    )

    acc_tail = _extract_accuracy_tail_stats(accuracy_external_df)
    rmsd_p95 = acc_tail.get("rmsd_p95")
    rmsd_worst = acc_tail.get("rmsd_worst")
    rmsd_p95_pass = None if rmsd_p95 is None else bool(float(rmsd_p95) <= max_rmsd_p95_a)
    rmsd_worst_pass = None if rmsd_worst is None else bool(float(rmsd_worst) <= max_rmsd_worst_a)
    checks.append(
        _build_check(
            "accuracy_tail_rmsd_p95",
            rmsd_p95,
            max_rmsd_p95_a,
            rmsd_p95_pass,
            accuracy_external_path,
            "accuracy_external RMSD 분포 p95",
        )
    )
    checks.append(
        _build_check(
            "accuracy_tail_rmsd_worst_target",
            rmsd_worst,
            max_rmsd_worst_a,
            rmsd_worst_pass,
            accuracy_external_path,
            "accuracy_external RMSD 최악 타깃",
        )
    )

    feature_quality = _extract_feature_quality(feature_df)
    max_missing_rate = _safe_float(feature_quality.get("max_missing_rate"))
    checks.append(
        _build_check(
            "feature_matrix_targets",
            feature_quality.get("targets"),
            int(args.min_feature_targets),
            None
            if feature_quality.get("targets") is None
            else bool(int(feature_quality.get("targets", 0)) >= int(args.min_feature_targets)),
            feature_path,
            "상품 DB용 feature matrix 타깃 커버리지",
        )
    )
    checks.append(
        _build_check(
            "feature_matrix_missing_rate",
            max_missing_rate,
            float(args.feature_max_missing_rate),
            None
            if max_missing_rate is None
            else bool(float(max_missing_rate) <= float(args.feature_max_missing_rate)),
            feature_path,
            "핵심 feature 컬럼 결측률 상한",
        )
    )
    checks.append(
        _build_check(
            "feature_matrix_variable_cols",
            int(feature_quality.get("variable_cols_count", 0)),
            int(args.feature_min_variable_cols),
            bool(int(feature_quality.get("variable_cols_count", 0)) >= int(args.feature_min_variable_cols)),
            feature_path,
            "핵심 feature 컬럼 변별성(고정값 제외)",
        )
    )
    checks.append(
        _build_check(
            "feature_matrix_constant_flag_cols",
            int(feature_quality.get("constant_flag_cols_count", 0)),
            int(args.feature_max_constant_flag_cols),
            bool(int(feature_quality.get("constant_flag_cols_count", 0)) <= int(args.feature_max_constant_flag_cols)),
            feature_path,
            "플래그/조건 컬럼 상수화 허용 상한",
        )
    )

    considered = [c for c in checks if isinstance(c.get("pass"), bool)]
    passed = [c for c in considered if c.get("pass") is True]
    score = (100.0 * float(len(passed)) / float(len(considered))) if considered else 0.0

    critical_names = {
        "nightly_pass",
        "strict_release_pass",
        "speed_gate",
        "speed_gate_enforced",
        "speed_tail_worst_target",
        "trajectory_tail_fps_worst_target",
        "accuracy_gate_pass",
        "accuracy_tail_rmsd_worst_target",
        "allatom_claim_ready",
        "dashboard_ready",
    }
    critical_pass = True
    for c in checks:
        if c.get("check") in critical_names and c.get("pass") is False:
            critical_pass = False
            break

    readiness_tier = _tier(score=score, critical_pass=critical_pass, considered=len(considered))
    failed_checks = [c for c in checks if c.get("pass") is False]

    recommendations: List[str] = []
    for c in failed_checks:
        ck = str(c.get("check"))
        if ck == "speed_gate":
            recommendations.append("stage2 병목 리포트 기준으로 AI 추론 구간/입출력 경로 최적화 우선")
        elif ck == "accuracy_gate_pass":
            recommendations.append("정확도 게이트 실패 타깃 중심으로 claim correction loop 재학습")
        elif ck == "dashboard_ready":
            recommendations.append("대시보드에 비교 러닝/타깃 필터/PDB 샘플을 최소 기준 이상 채움")
        elif ck == "external_packet_targets":
            recommendations.append("실측 외부 레퍼런스 타깃 수 확대(최소 기준 충족)")
        elif ck == "allatom_claim_ready":
            recommendations.append("thermo/kinetics 지표 안정화 후 initial claim ready 고정")
        elif ck == "speed_gate_enforced":
            recommendations.append("strict speed 측정을 single-target smoke가 아닌 full-scope enforced 결과로 고정")
        elif ck == "special_case_pass":
            recommendations.append("특이케이스 도메인별 smoke/full 실패 원인 보정")
        elif ck == "ood_measured20_pass":
            recommendations.append("measured20 OOD 커버리지/품질 재수집")
        elif ck == "long_stability_pass":
            recommendations.append("타깃별 장기 안정성 튜닝 프로파일 재검증")
        elif ck == "feature_matrix_targets":
            recommendations.append("feature matrix 대상 타깃 수를 상업 기준(min targets) 이상으로 확장")
        elif ck == "feature_matrix_missing_rate":
            recommendations.append("k_angle/theta0/k_dihedral/phi0_alpha 결측 행을 보강하거나 생성 파이프 수정")
        elif ck == "feature_matrix_variable_cols":
            recommendations.append("변수 스윕(ionic_strength/ptm_count/cooling_rate 등)으로 feature 변별성 확보")
        elif ck == "feature_matrix_constant_flag_cols":
            recommendations.append("상수화된 플래그 변수를 실험 조건군으로 분해해 DB 상품성 개선")
        elif ck == "trajectory_tail_fps_p05":
            recommendations.append("trajectory target-tail 기준 p05 fps가 낮은 타깃의 AdResS 반경/원자비 캡을 축소")
        elif ck == "trajectory_tail_fps_worst_target":
            recommendations.append("trajectory 최악 타깃의 AdResS fallback 비율을 높여 fps 하한을 복구")

    out = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "summary": {
            "readiness_score": float(round(score, 2)),
            "readiness_tier": readiness_tier,
            "considered_checks": int(len(considered)),
            "passed_checks": int(len(passed)),
            "failed_checks": int(len(failed_checks)),
            "critical_checks_pass": bool(critical_pass),
        },
        "checks": checks,
        "sources": {
            "nightly_summary_json": nightly_path,
            "strict_release_summary_json": strict_path,
            "strict_release_candidates": strict_candidates,
            "dashboard_json": dashboard_path,
            "external_packet_json": packet_path,
            "stage2_csv": stage2_path,
            "stage2_candidates": stage2_candidates,
            "accuracy_external_csv": accuracy_external_path,
            "feature_csv": feature_path,
            "trajectory_target_tail_csv": trajectory_tail_path,
        },
        "feature_quality": feature_quality,
        "recommendations": recommendations,
    }
    return out


def _write_outputs(payload: Dict[str, Any], out_json: str, out_csv: str, out_md: str) -> None:
    os.makedirs(os.path.dirname(out_json) or ".", exist_ok=True)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    os.makedirs(os.path.dirname(out_csv) or ".", exist_ok=True)
    with open(out_csv, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["check", "status", "pass", "value", "threshold", "source", "note"],
        )
        w.writeheader()
        for row in payload.get("checks", []):
            row_i = dict(row)
            for k in ("value", "threshold"):
                if isinstance(row_i.get(k), (dict, list)):
                    row_i[k] = json.dumps(row_i[k], ensure_ascii=False)
            w.writerow(row_i)

    summary = payload.get("summary", {})
    checks = payload.get("checks", [])
    recs = payload.get("recommendations", [])
    lines = [
        "# Commercial Readiness Report",
        "",
        f"- generated_at_local: {payload.get('generated_at_local')}",
        f"- readiness_score: {summary.get('readiness_score')}",
        f"- readiness_tier: {summary.get('readiness_tier')}",
        f"- considered_checks: {summary.get('considered_checks')}",
        f"- passed_checks: {summary.get('passed_checks')}",
        f"- failed_checks: {summary.get('failed_checks')}",
        f"- critical_checks_pass: {summary.get('critical_checks_pass')}",
        "",
        "## Checks",
    ]
    for c in checks:
        lines.append(
            f"- {c.get('check')}: {c.get('status')} (value={c.get('value')}, threshold={c.get('threshold')})"
        )
    lines.append("")
    lines.append("## Recommendations")
    if recs:
        for r in recs:
            lines.append(f"- {r}")
    else:
        lines.append("- No blocking item detected.")

    os.makedirs(os.path.dirname(out_md) or ".", exist_ok=True)
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def build_parser() -> argparse.ArgumentParser:
    stamp = dt.date.today().isoformat()
    p = argparse.ArgumentParser(
        description="Build commercialization readiness report from nightly/strict/dashboard/packet artifacts."
    )
    p.add_argument("--nightly-summary-json", type=str, default="")
    p.add_argument("--strict-release-summary-json", type=str, default="")
    p.add_argument("--dashboard-json", type=str, default="")
    p.add_argument("--external-packet-json", type=str, default="")
    p.add_argument("--stage2-csv", type=str, default="")
    p.add_argument("--trajectory-target-tail-csv", type=str, default="")
    p.add_argument("--accuracy-external-csv", type=str, default="")
    p.add_argument("--feature-csv", type=str, default="")
    p.add_argument("--strict-source-policy", type=str, default="full_only", choices=["full_only", "prefer_full", "any"])
    p.add_argument("--speedup-threshold", type=float, default=12.0)
    p.add_argument("--speedup-p95-threshold", type=float, default=None)
    p.add_argument("--speedup-worst-threshold", type=float, default=None)
    p.add_argument("--traj-fps-p05-threshold", type=float, default=None)
    p.add_argument("--traj-fps-worst-threshold", type=float, default=None)
    p.add_argument("--max-rmsd-p95-a", type=float, default=8.0)
    p.add_argument("--max-rmsd-worst-a", type=float, default=12.0)
    p.add_argument("--min-dashboard-metrics", type=int, default=3)
    p.add_argument("--min-dashboard-runs", type=int, default=1)
    p.add_argument("--min-external-targets", type=int, default=5)
    p.add_argument("--min-feature-targets", type=int, default=8)
    p.add_argument("--feature-max-missing-rate", type=float, default=0.15)
    p.add_argument("--feature-min-variable-cols", type=int, default=8)
    p.add_argument("--feature-max-constant-flag-cols", type=int, default=8)
    p.add_argument(
        "--disable-auto-discovery",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Disable fallback lookup of latest artifacts when explicit paths are missing.",
    )
    p.add_argument("--out-json", type=str, default=f"runs/commercial_readiness_{stamp}.json")
    p.add_argument("--out-csv", type=str, default=f"runs/commercial_readiness_{stamp}.csv")
    p.add_argument("--out-md", type=str, default=f"runs/commercial_readiness_{stamp}.md")
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    payload = build_report(args)
    _write_outputs(payload, out_json=str(args.out_json), out_csv=str(args.out_csv), out_md=str(args.out_md))
    print(
        json.dumps(
            {
                "out_json": str(args.out_json),
                "out_csv": str(args.out_csv),
                "out_md": str(args.out_md),
                "summary": payload.get("summary", {}),
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
