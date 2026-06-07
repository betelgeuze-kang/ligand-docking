#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from core.definitions import ResearchConstants


ALL_PARAMS: List[str] = [
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

BINARY_PARAMS = {"is_llps", "is_folded", "ai_correction_active"}
DISCRETE_PARAMS = {"cluster_max", "ptm_count", "violations"}
CONTINUOUS_PARAMS = set(ALL_PARAMS) - BINARY_PARAMS - DISCRETE_PARAMS


def _to_float(v: Any) -> Optional[float]:
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


def _finite_range(values: List[Optional[float]]) -> Optional[List[float]]:
    clean = [float(v) for v in values if v is not None]
    if not clean:
        return None
    return [float(min(clean)), float(max(clean))]


def _read_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _read_csv(path: str) -> pd.DataFrame:
    return pd.read_csv(path)


def _resolve_optional_path(path: Optional[str]) -> Optional[str]:
    if not path:
        return path
    path_i = str(path)
    if os.path.exists(path_i):
        return path_i
    base = os.path.basename(path_i)
    if not base:
        return path_i
    candidates = sorted(glob.glob(f"runs/**/{base}", recursive=True))
    if len(candidates) > 0:
        return str(candidates[-1])
    return path_i


def _branch_capability_summary() -> Dict[str, Any]:
    branch_dir = Path("theory/branches")
    branch_modules: List[str] = []
    if branch_dir.exists():
        for fp in sorted(branch_dir.glob("*_logic.py")):
            name = fp.stem.replace("_logic", "")
            branch_modules.append(name)

    core_modules = [
        "salt",
        "hydrophobic",
        "aromatic",
        "hbond",
        "ct",
        "picat",
        "catpi",
        "halogen",
        "chalcogen",
        "stacking",
    ]
    return {
        "core_modules": core_modules,
        "branch_modules_detected": branch_modules,
        "counts": {
            "core": len(core_modules),
            "branch": len(branch_modules),
            "total_specialists": len(core_modules) + len(branch_modules),
        },
        "router_features": {
            "dynamic_branch_loading": True,
            "conditional_execution_with_active_mask": True,
            "exploration_weighting": True,
            "learnable_physics_ai_mixing": True,
            "fallback_at_least_one_active_module": True,
        },
        "source": {
            "orchestrator_file": "theory/strategy.py",
            "branch_dir": "theory/branches",
        },
    }


def _row_by_target(df: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    if df is None or df.empty:
        return out
    for _, row in df.iterrows():
        target = str(row.get("target", "")).strip()
        if target:
            out[target] = row.to_dict()
    return out


def _normalize_target_key(name: str) -> str:
    return "".join(ch for ch in str(name).lower() if ch.isalnum())


def _row_by_target_norm(df: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    if df is None or df.empty:
        return out
    for _, row in df.iterrows():
        target = str(row.get("target", "")).strip()
        if target:
            out[_normalize_target_key(target)] = row.to_dict()
    return out


def _rows_group_by_target_norm(df: pd.DataFrame) -> Dict[str, List[Dict[str, Any]]]:
    out: Dict[str, List[Dict[str, Any]]] = {}
    if df is None or df.empty:
        return out
    for _, row in df.iterrows():
        target = str(row.get("target", "")).strip()
        if not target:
            continue
        key = _normalize_target_key(target)
        out.setdefault(key, []).append(row.to_dict())
    return out


def _load_optional_csv(path: Optional[str], strict: bool, label: str) -> pd.DataFrame:
    path_i = _resolve_optional_path(path)
    if not path_i:
        return pd.DataFrame()
    if os.path.exists(path_i):
        return _read_csv(path_i)
    if strict:
        raise FileNotFoundError(f"{label} not found: {path_i}")
    return pd.DataFrame()


def _load_optional_json(path: Optional[str], strict: bool, label: str) -> Dict[str, Any]:
    path_i = _resolve_optional_path(path)
    if not path_i:
        return {}
    if os.path.exists(path_i):
        return _read_json(path_i)
    if strict:
        raise FileNotFoundError(f"{label} not found: {path_i}")
    return {}


def _summarize_strict_release(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not payload:
        return {"available": False}
    summary = payload.get("summary", {}) if isinstance(payload, dict) else {}
    gates = payload.get("gates", {}) if isinstance(payload, dict) else {}
    speed_gate = gates.get("speed", {}) if isinstance(gates, dict) else {}
    return {
        "available": True,
        "pass": bool(summary.get("pass", False)),
        "failed_gates": list(summary.get("failed_gates", [])),
        "failed_targets": list(summary.get("failed_targets", [])),
        "targets": _to_float(summary.get("targets")),
        "speed_gate_avg_speedup": _to_float(speed_gate.get("avg_speedup_on_vs_off")),
    }


def _summarize_nightly_batch(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not payload:
        return {"available": False}
    paths = payload.get("paths", {}) if isinstance(payload.get("paths"), dict) else {}
    return {
        "available": True,
        "pass": bool(payload.get("pass", False)),
        "failed_step_index": _to_float(payload.get("failed_step_index")),
        "total_steps": _to_float(payload.get("total_steps")),
        "executed_steps": _to_float(payload.get("executed_steps")),
        "claim_status": payload.get("claim_status"),
        "long_stability_status": payload.get("long_stability_status"),
        "dashboard_status": payload.get("dashboard_status"),
        "dashboard_json": paths.get("dashboard_json"),
        "dashboard_html": paths.get("dashboard_html"),
    }


def _summarize_dashboard(
    dashboard_payload: Dict[str, Any],
    nightly_payload: Dict[str, Any],
    *,
    dashboard_json_path: Optional[str],
    dashboard_html_path: Optional[str],
) -> Dict[str, Any]:
    nightly_status = (
        nightly_payload.get("dashboard_status", {})
        if isinstance(nightly_payload.get("dashboard_status"), dict)
        else {}
    )
    payload_metrics = dashboard_payload.get("metrics", []) if isinstance(dashboard_payload, dict) else []
    payload_runs = dashboard_payload.get("runs", []) if isinstance(dashboard_payload, dict) else []
    payload_pdb = dashboard_payload.get("pdb_entries", []) if isinstance(dashboard_payload, dict) else []
    payload_thresholds = dashboard_payload.get("thresholds", {}) if isinstance(dashboard_payload, dict) else {}
    payload_targets = (
        dashboard_payload.get("target_filters", []) if isinstance(dashboard_payload, dict) else []
    )

    metrics_count = (
        int(len(payload_metrics))
        if isinstance(payload_metrics, list)
        else int(_to_float(nightly_status.get("metrics_count")) or 0)
    )
    run_count = (
        int(len(payload_runs))
        if isinstance(payload_runs, list)
        else int(_to_float(nightly_status.get("run_count")) or 0)
    )
    pdb_count = (
        int(len(payload_pdb))
        if isinstance(payload_pdb, list)
        else int(_to_float(nightly_status.get("pdb_count")) or 0)
    )
    target_filters = payload_targets if isinstance(payload_targets, list) else nightly_status.get("target_filters")

    available = bool(dashboard_payload) or bool(nightly_status) or bool(dashboard_json_path) or bool(dashboard_html_path)
    return {
        "available": bool(available),
        "title": (
            dashboard_payload.get("title")
            if isinstance(dashboard_payload, dict)
            else nightly_status.get("title")
        ),
        "dashboard_json": dashboard_json_path,
        "dashboard_html": dashboard_html_path,
        "metrics_count": int(metrics_count),
        "run_count": int(run_count),
        "pdb_count": int(pdb_count),
        "target_filters": target_filters,
        "threshold_count": int(len(payload_thresholds)) if isinstance(payload_thresholds, dict) else 0,
    }


def _summarize_reproducibility(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not payload:
        return {"available": False}
    summary = payload.get("summary", {}) if isinstance(payload, dict) else {}
    return {
        "available": True,
        "pass": bool(summary.get("pass", False)),
        "replicates": _to_float(summary.get("replicates")),
        "all_claim_ready_for_allatom": bool(summary.get("all_claim_ready_for_allatom", False)),
        "all_long_stability_pass": bool(summary.get("all_long_stability_pass", False)),
        "avg_rmsd_vs_native_aligned_mean": _to_float(summary.get("avg_rmsd_vs_native_aligned_mean")),
        "avg_rmsd_vs_native_aligned_std": _to_float(summary.get("avg_rmsd_vs_native_aligned_std")),
        "max_std_rmsd_vs_native_aligned": _to_float(summary.get("max_std_rmsd_vs_native_aligned")),
        "std_gate_pass": bool(summary.get("std_gate_pass", False)),
    }


def _summarize_claim_correction(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not payload:
        return {"available": False}
    summary = payload.get("summary", {}) if isinstance(payload, dict) else {}
    return {
        "available": True,
        "initial_fail_count": _to_float(summary.get("initial_fail_count")),
        "best_fail_count": _to_float(summary.get("best_fail_count")),
        "claim_failed_metrics_after_runner": _to_float(
            summary.get("claim_failed_metrics_after_runner")
        ),
        "claim_ready_for_allatom": bool(summary.get("claim_ready_for_allatom", False)),
        "pass_core_gate": bool(summary.get("pass_core_gate", False)),
        "improved": bool(summary.get("improved", False)),
    }


def _summarize_baseline_config(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not payload:
        return {"available": False}
    paths = payload.get("paths", {}) if isinstance(payload, dict) else {}
    return {
        "available": True,
        "created_at": payload.get("meta", {}).get("created_at")
        if isinstance(payload.get("meta"), dict)
        else None,
        "strict_summary_json": paths.get("strict_summary_json") if isinstance(paths, dict) else None,
        "nightly_full_summary_json": paths.get("nightly_full_summary_json")
        if isinstance(paths, dict)
        else None,
        "repro_summary_json": paths.get("repro_summary_json") if isinstance(paths, dict) else None,
        "stability_profile_json": paths.get("stability_profile_json") if isinstance(paths, dict) else None,
        "claim_policy_json": paths.get("claim_policy_json") if isinstance(paths, dict) else None,
    }


def _summarize_quality_rows(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not rows:
        return {
            "available": False,
            "candidate_rows": 0,
            "included_rows": 0,
            "include_recommended": False,
            "mean_weight_included": None,
            "best_source_file": None,
            "best_quality_tier": None,
            "best_plddt_mean": None,
        }

    included = [r for r in rows if int(_to_float(r.get("include")) or 0) == 1]
    included_weights = [_to_float(r.get("sample_weight")) for r in included]
    included_weights = [w for w in included_weights if w is not None]

    best_row = None
    best_weight = float("-inf")
    for r in included:
        w = _to_float(r.get("sample_weight"))
        if w is None:
            continue
        if w > best_weight:
            best_weight = w
            best_row = r
    if best_row is None:
        best_row = rows[0]

    return {
        "available": True,
        "candidate_rows": int(len(rows)),
        "included_rows": int(len(included)),
        "include_recommended": bool(len(included) > 0),
        "mean_weight_included": (
            float(np.mean(np.asarray(included_weights, dtype=np.float32)))
            if included_weights
            else None
        ),
        "best_source_file": best_row.get("source_file"),
        "best_quality_tier": best_row.get("quality_tier"),
        "best_plddt_mean": _to_float(best_row.get("plddt_mean")),
        "best_sample_weight": _to_float(best_row.get("sample_weight")),
        "best_exclude_reason": best_row.get("exclude_reason"),
    }


def _base_param(name: str) -> Dict[str, Any]:
    return {
        "name": name,
        "status": "not_measured_yet",
        "value": None,
        "safe_range": None,
        "confidence": "low",
        "reason": "current report set does not log this variable for per-target optimization",
    }


def _build_golden_params(
    target: str,
    parity_row: Dict[str, Any],
    stage2_row: Dict[str, Any],
    fidelity_row: Dict[str, Any],
) -> Dict[str, Dict[str, Any]]:
    result: Dict[str, Dict[str, Any]] = {k: _base_param(k) for k in ALL_PARAMS}

    if fidelity_row:
        energy_proxy_range = _finite_range(
            [
                _to_float(fidelity_row.get("restrained_proxy_energy_drift_ratio")),
                _to_float(fidelity_row.get("unrestrained_proxy_energy_drift_ratio")),
            ]
        )
        energy_raw_range = _finite_range(
            [
                _to_float(fidelity_row.get("restrained_energy_drift_ratio")),
                _to_float(fidelity_row.get("unrestrained_energy_drift_ratio")),
            ]
        )
        result["energy"] = {
            "name": "energy",
            "status": "measured_proxy",
            "value": {
                "restrained_proxy_energy_drift_ratio": _to_float(
                    fidelity_row.get("restrained_proxy_energy_drift_ratio")
                ),
                "unrestrained_proxy_energy_drift_ratio": _to_float(
                    fidelity_row.get("unrestrained_proxy_energy_drift_ratio")
                ),
            },
            "safe_range": energy_proxy_range,
            "confidence": "medium",
            "metric_definition": "proxy_energy_drift_ratio",
            "aux_raw_energy_drift_range": energy_raw_range,
            "source": "runs/physics_fidelity_report.csv",
        }

        rg_range = _finite_range(
            [
                _to_float(fidelity_row.get("restrained_rg_delta")),
                _to_float(fidelity_row.get("unrestrained_rg_delta")),
            ]
        )
        result["Rg"] = {
            "name": "Rg",
            "status": "measured_delta_to_native",
            "value": {
                "restrained_rg_delta_A": _to_float(fidelity_row.get("restrained_rg_delta")),
                "unrestrained_rg_delta_A": _to_float(fidelity_row.get("unrestrained_rg_delta")),
            },
            "safe_range": rg_range,
            "confidence": "medium",
            "metric_definition": "abs(Rg_result - Rg_native) in Angstrom",
            "source": "runs/physics_fidelity_report.csv",
        }

        sasa_range = _finite_range(
            [
                _to_float(fidelity_row.get("restrained_sasa_delta")),
                _to_float(fidelity_row.get("unrestrained_sasa_delta")),
            ]
        )
        result["sasa"] = {
            "name": "sasa",
            "status": "measured_proxy_delta",
            "value": {
                "restrained_sasa_delta": _to_float(fidelity_row.get("restrained_sasa_delta")),
                "unrestrained_sasa_delta": _to_float(fidelity_row.get("unrestrained_sasa_delta")),
            },
            "safe_range": sasa_range,
            "confidence": "medium",
            "metric_definition": "abs(SASA_proxy_result - SASA_proxy_native)",
            "source": "runs/physics_fidelity_report.csv",
        }

        rmsd_range = _finite_range(
            [
                _to_float(fidelity_row.get("restrained_rmsd")),
                _to_float(fidelity_row.get("unrestrained_rmsd")),
            ]
        )
        result["rmsd"] = {
            "name": "rmsd",
            "status": "measured",
            "value": {
                "restrained_rmsd_A": _to_float(fidelity_row.get("restrained_rmsd")),
                "unrestrained_rmsd_A": _to_float(fidelity_row.get("unrestrained_rmsd")),
            },
            "safe_range": rmsd_range,
            "confidence": "high",
            "metric_definition": "RMSD to native in Angstrom",
            "source": "runs/physics_fidelity_report.csv",
        }

    result["ionic_strength"] = {
        "name": "ionic_strength",
        "status": "config_default_not_tuned",
        "value": 0.15,
        "safe_range": [0.15, 0.15],
        "confidence": "low",
        "reason": "default runtime condition is logged in code paths, but no target-specific sweep output yet",
        "source": "benchmark/performance_bench.py",
    }

    if parity_row:
        sat_count = int(_to_float(parity_row.get("rs_neighbor_saturated_samples")) or 0)
        overflow_count = int(_to_float(parity_row.get("rs_cell_overflow_samples")) or 0)
        result["violations"] = {
            "name": "violations",
            "status": "partially_measured",
            "value": {
                "rs_neighbor_saturated_samples": sat_count,
                "rs_cell_overflow_samples": overflow_count,
            },
            "safe_range": [0.0, 0.0],
            "confidence": "medium",
            "reason": "overflow/saturation violations are measured, but full physics-guard violation stream is not aggregated here",
            "source": "runs/accuracy_gate_parity_target.csv",
        }

    ai_mode_note = "stage2 reports include on/off throughput comparison using auto backend vs pytorch fallback"
    if stage2_row:
        result["ai_correction_active"] = {
            "name": "ai_correction_active",
            "status": "mode_dependent_not_optimized",
            "value": {
                "evaluation_mode": "paired_on_off_backend_benchmark",
                "recommended_for_strict_accuracy_gate": False,
            },
            "safe_range": [0.0, 1.0],
            "confidence": "low",
            "reason": ai_mode_note,
            "source": "runs/accuracy_gate_stage2.csv",
        }
    else:
        result["ai_correction_active"] = {
            "name": "ai_correction_active",
            "status": "not_measured_yet",
            "value": None,
            "safe_range": None,
            "confidence": "low",
            "reason": ai_mode_note,
        }

    return result


def _coerce_numeric_series(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _classify_param_type(name: str, values: pd.Series) -> str:
    if name in BINARY_PARAMS:
        return "binary"
    if name in DISCRETE_PARAMS:
        return "discrete"
    if name in CONTINUOUS_PARAMS:
        return "continuous"
    valid = values.dropna()
    if valid.empty:
        return "unknown"
    arr = valid.to_numpy(dtype=float)
    int_like = bool(np.all(np.isclose(arr, np.round(arr), atol=1e-8)))
    uniq = sorted(set(float(x) for x in np.unique(arr)))
    if int_like and set(uniq).issubset({0.0, 1.0}):
        return "binary"
    if int_like:
        return "discrete"
    return "continuous"


def _confidence_label(n_valid: int, n_total: int, min_obs: int) -> str:
    if n_total <= 0:
        return "low"
    coverage = float(n_valid) / float(max(n_total, 1))
    if n_valid < int(min_obs) or coverage < 0.50:
        return "low"
    if n_valid < int(min_obs * 3) or coverage < 0.85:
        return "medium"
    return "high"


def _build_param_from_feature_series(
    name: str,
    series: pd.Series,
    q_low: float,
    q_high: float,
    min_obs: int,
    source: str,
) -> Optional[Dict[str, Any]]:
    n_total = int(series.shape[0])
    values = _coerce_numeric_series(series)
    valid = values.dropna()
    n_valid = int(valid.shape[0])
    if n_valid < int(min_obs):
        return None

    ptype = _classify_param_type(name=name, values=valid)
    mean_v = float(valid.mean())
    median_v = float(valid.median())
    std_v = float(valid.std(ddof=0))
    min_v = float(valid.min())
    max_v = float(valid.max())
    low_v = float(valid.quantile(float(q_low)))
    high_v = float(valid.quantile(float(q_high)))
    if low_v > high_v:
        low_v, high_v = high_v, low_v

    uniq_count = int(valid.nunique(dropna=True))
    coverage = float(n_valid) / float(max(n_total, 1))
    confidence = _confidence_label(n_valid=n_valid, n_total=n_total, min_obs=min_obs)

    if ptype in ("binary", "discrete"):
        mean_v = float(round(mean_v, 6))
        median_v = float(round(median_v))
        std_v = float(round(std_v, 6))
        min_v = float(round(min_v))
        max_v = float(round(max_v))
        low_v = float(round(low_v))
        high_v = float(round(high_v))
        recommended = int(round(median_v))
    else:
        recommended = float(median_v)

    return {
        "name": name,
        "status": "measured_from_feature_matrix_v2",
        "param_type": ptype,
        "value": {
            "recommended": recommended,
            "median": float(median_v),
            "mean": float(mean_v),
            "std": float(std_v),
        },
        "safe_range": [float(low_v), float(high_v)],
        "hard_range": [float(min_v), float(max_v)],
        "coverage": float(coverage),
        "observations": int(n_valid),
        "total_rows_target": int(n_total),
        "unique_values": int(uniq_count),
        "confidence": confidence,
        "method": {
            "type": "quantile_band",
            "q_low": float(q_low),
            "q_high": float(q_high),
            "min_obs": int(min_obs),
        },
        "source": source,
    }


def _build_golden_params_v2(
    fallback_v1: Dict[str, Dict[str, Any]],
    feature_target_df: pd.DataFrame,
    feature_source: str,
    q_low: float,
    q_high: float,
    min_obs: int,
) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    has_feature = feature_target_df is not None and (not feature_target_df.empty)

    for name in ALL_PARAMS:
        v2_item: Optional[Dict[str, Any]] = None
        if has_feature and name in feature_target_df.columns:
            v2_item = _build_param_from_feature_series(
                name=name,
                series=feature_target_df[name],
                q_low=float(q_low),
                q_high=float(q_high),
                min_obs=int(min_obs),
                source=feature_source,
            )
        if v2_item is not None:
            out[name] = v2_item
        else:
            out[name] = fallback_v1.get(name, _base_param(name))
    return out


def _build_param_status_summary(proteins: List[Dict[str, Any]]) -> Dict[str, Any]:
    summary: Dict[str, Any] = {}
    for param_name in ALL_PARAMS:
        status_count: Dict[str, int] = {}
        for item in proteins:
            status = (
                item.get("golden_params", {})
                .get(param_name, {})
                .get("status", "unknown")
            )
            status_count[status] = status_count.get(status, 0) + 1
        summary[param_name] = {"status_counts": status_count}
    return summary


def _steps_per_day(steps_per_sec: Optional[float]) -> Optional[float]:
    if steps_per_sec is None:
        return None
    return float(steps_per_sec) * 86400.0


def build_packet(args: argparse.Namespace) -> Dict[str, Any]:
    packet_version = str(getattr(args, "packet_version", "v2")).strip().lower()
    if packet_version not in ("v1", "v2", "v3"):
        raise ValueError("packet_version must be one of: v1, v2, v3")

    gate_json_path = _resolve_optional_path(str(args.gate_json)) or str(args.gate_json)
    parity_target_csv_path = _resolve_optional_path(str(args.parity_target_csv)) or str(
        args.parity_target_csv
    )
    stage2_csv_path = _resolve_optional_path(str(args.stage2_csv)) or str(args.stage2_csv)
    fidelity_csv_path = _resolve_optional_path(str(args.fidelity_csv)) or str(args.fidelity_csv)

    gate = _read_json(gate_json_path)
    parity_df = _read_csv(parity_target_csv_path)
    stage2_df = _read_csv(stage2_csv_path)
    fidelity_df = _read_csv(fidelity_csv_path)
    feature_source = str(
        _resolve_optional_path(str(getattr(args, "feature_csv", "runs/feature_matrix_per_target.csv")))
        or str(getattr(args, "feature_csv", "runs/feature_matrix_per_target.csv"))
    )
    q_low = float(getattr(args, "q_low", 0.10))
    q_high = float(getattr(args, "q_high", 0.90))
    min_obs = int(getattr(args, "min_obs", 64))
    accuracy_external_source = getattr(args, "accuracy_external_csv", None)
    quality_curation_source = getattr(args, "quality_curation_csv", None)
    strict_release_summary_source = getattr(args, "strict_release_summary_json", None)
    nightly_summary_source = getattr(args, "nightly_summary_json", None)
    reproducibility_source = getattr(args, "reproducibility_json", None)
    baseline_config_source = getattr(args, "baseline_config_json", None)
    claim_correction_source = getattr(args, "claim_correction_summary_json", None)
    dashboard_json_source = getattr(args, "dashboard_json", None)
    dashboard_html_source = getattr(args, "dashboard_html", None)
    strict_optional_sources = bool(getattr(args, "strict_optional_sources", False))
    if q_low < 0.0 or q_high > 1.0 or q_low >= q_high:
        raise ValueError("q_low/q_high must satisfy 0.0 <= q_low < q_high <= 1.0")

    parity_by_target = _row_by_target(parity_df)
    stage2_by_target = _row_by_target(stage2_df)
    fidelity_by_target = _row_by_target(fidelity_df)
    feature_by_target: Dict[str, pd.DataFrame] = {}
    feature_df = pd.DataFrame()
    if packet_version in ("v2", "v3"):
        if not os.path.exists(feature_source):
            raise FileNotFoundError(
                f"feature csv not found for packet_version={packet_version}: {feature_source}"
            )
        feature_df = _read_csv(feature_source)
        if "target" not in feature_df.columns:
            raise ValueError("feature csv must include 'target' column")
        for target, sub_df in feature_df.groupby("target"):
            feature_by_target[str(target)] = sub_df.copy()

    external_df = _load_optional_csv(
        path=accuracy_external_source,
        strict=strict_optional_sources,
        label="accuracy_external_csv",
    )
    quality_df = _load_optional_csv(
        path=quality_curation_source,
        strict=strict_optional_sources,
        label="quality_curation_csv",
    )
    strict_release_summary = _load_optional_json(
        path=strict_release_summary_source,
        strict=strict_optional_sources,
        label="strict_release_summary_json",
    )
    nightly_summary = _load_optional_json(
        path=nightly_summary_source,
        strict=strict_optional_sources,
        label="nightly_summary_json",
    )
    nightly_paths = nightly_summary.get("paths", {}) if isinstance(nightly_summary.get("paths"), dict) else {}
    if not dashboard_json_source:
        dashboard_json_source = nightly_paths.get("dashboard_json")
    if not dashboard_html_source:
        dashboard_html_source = nightly_paths.get("dashboard_html")
    explicit_dashboard_json = str(getattr(args, "dashboard_json", "") or "").strip()
    dashboard_summary = _load_optional_json(
        path=dashboard_json_source,
        strict=bool(strict_optional_sources and bool(explicit_dashboard_json)),
        label="dashboard_json",
    )
    reproducibility_summary = _load_optional_json(
        path=reproducibility_source,
        strict=strict_optional_sources,
        label="reproducibility_json",
    )
    baseline_config = _load_optional_json(
        path=baseline_config_source,
        strict=strict_optional_sources,
        label="baseline_config_json",
    )
    claim_correction_summary = _load_optional_json(
        path=claim_correction_source,
        strict=strict_optional_sources,
        label="claim_correction_summary_json",
    )
    external_by_target = _row_by_target_norm(external_df)
    quality_by_target = _rows_group_by_target_norm(quality_df)
    dashboard_json_resolved = _resolve_optional_path(dashboard_json_source) if dashboard_json_source else None
    dashboard_html_resolved = _resolve_optional_path(dashboard_html_source) if dashboard_html_source else None

    protein_rows: List[Dict[str, Any]] = []
    for target, conf in ResearchConstants.CHALLENGES.items():
        parity_row = parity_by_target.get(target, {})
        stage2_row = stage2_by_target.get(target, {})
        fidelity_row = fidelity_by_target.get(target, {})
        feature_target_df = feature_by_target.get(target, pd.DataFrame())
        ext_row = external_by_target.get(_normalize_target_key(target), {})
        quality_rows = quality_by_target.get(_normalize_target_key(target), [])
        quality_summary = _summarize_quality_rows(quality_rows)
        pdb_path = f"data/native/{target.lower()}.pdb"
        golden_v1 = _build_golden_params(
            target=target,
            parity_row=parity_row,
            stage2_row=stage2_row,
            fidelity_row=fidelity_row,
        )
        if packet_version in ("v2", "v3"):
            golden = _build_golden_params_v2(
                fallback_v1=golden_v1,
                feature_target_df=feature_target_df,
                feature_source=feature_source,
                q_low=q_low,
                q_high=q_high,
                min_obs=min_obs,
            )
        else:
            golden = golden_v1

        protein_rows.append(
            {
                "target": target,
                "protein_meta": {
                    "n_res": int(conf["n_res"]),
                    "fold_class": conf.get("fold_class", "unknown"),
                    "pdb_path": pdb_path,
                    "pdb_exists": bool(os.path.exists(pdb_path)),
                },
                "accuracy": {
                    "neighbor_jaccard_mean": _to_float(parity_row.get("neighbor_jaccard_mean")),
                    "e2e_rmse_mean_raw": _to_float(parity_row.get("e2e_rmse_mean_raw")),
                    "e2e_rel_rmse_mean_clipped": _to_float(
                        parity_row.get("e2e_rel_rmse_mean_clipped")
                    ),
                    "force_rmse_mean_raw": _to_float(parity_row.get("force_rmse_mean_raw")),
                },
                "speed": {
                    "throughput_on_steps_per_sec": _to_float(stage2_row.get("throughput_on")),
                    "throughput_off_steps_per_sec": _to_float(stage2_row.get("throughput_off")),
                    "speedup_on_vs_off": _to_float(stage2_row.get("speedup_on_vs_off")),
                    "step_ms_on": _to_float(stage2_row.get("step_ms_on")),
                    "step_ms_off": _to_float(stage2_row.get("step_ms_off")),
                },
                "dynamics_fidelity": {
                    "restrained_rmsd_A": _to_float(fidelity_row.get("restrained_rmsd")),
                    "unrestrained_rmsd_A": _to_float(fidelity_row.get("unrestrained_rmsd")),
                    "restrained_rg_delta_A": _to_float(fidelity_row.get("restrained_rg_delta")),
                    "unrestrained_rg_delta_A": _to_float(
                        fidelity_row.get("unrestrained_rg_delta")
                    ),
                    "restrained_sasa_delta": _to_float(
                        fidelity_row.get("restrained_sasa_delta")
                    ),
                    "unrestrained_sasa_delta": _to_float(
                        fidelity_row.get("unrestrained_sasa_delta")
                    ),
                    "restrained_proxy_energy_drift_ratio": _to_float(
                        fidelity_row.get("restrained_proxy_energy_drift_ratio")
                    ),
                    "unrestrained_proxy_energy_drift_ratio": _to_float(
                        fidelity_row.get("unrestrained_proxy_energy_drift_ratio")
                    ),
                },
                "external_md_accuracy": {
                    "available": bool(ext_row),
                    "reference_source": ext_row.get("reference_source") if ext_row else None,
                    "reference_path": ext_row.get("reference_path") if ext_row else None,
                    "reference_engine": ext_row.get("reference_engine") if ext_row else None,
                    "reference_label": ext_row.get("reference_label") if ext_row else None,
                    "rmsd_vs_external_ref_A": _to_float(ext_row.get("avg_rmsd")),
                    "rmsd_vs_external_ref_raw_A": _to_float(
                        ext_row.get("avg_rmsd_raw", ext_row.get("avg_rmsd"))
                    ),
                    "rmsd_vs_external_ref_aligned_A": _to_float(ext_row.get("avg_rmsd_aligned")),
                    "rmsd_vs_native_A": _to_float(ext_row.get("avg_rmsd_vs_native")),
                    "rmsd_vs_native_raw_A": _to_float(
                        ext_row.get("avg_rmsd_vs_native_raw", ext_row.get("avg_rmsd_vs_native"))
                    ),
                    "rmsd_vs_native_aligned_A": _to_float(ext_row.get("avg_rmsd_vs_native_aligned")),
                    "reference_vs_native_rmsd_A": _to_float(ext_row.get("avg_reference_vs_native_rmsd")),
                    "reference_vs_native_rmsd_raw_A": _to_float(
                        ext_row.get("avg_reference_vs_native_rmsd_raw", ext_row.get("avg_reference_vs_native_rmsd"))
                    ),
                    "reference_vs_native_rmsd_aligned_A": _to_float(
                        ext_row.get("avg_reference_vs_native_rmsd_aligned")
                    ),
                    "rg_A": _to_float(ext_row.get("avg_rg")),
                },
                "structure_data_quality": quality_summary,
                "golden_params": golden,
                "feature_rows_target": (
                    int(feature_target_df.shape[0]) if packet_version in ("v2", "v3") else 0
                ),
            }
        )

    parity_summary = gate.get("parity_summary", {})
    perf_summary = gate.get("performance_summary", {})
    gate_summary = gate.get("summary", {})
    status_summary = _build_param_status_summary(protein_rows)
    measured_v2_entries = 0
    total_param_entries = len(protein_rows) * len(ALL_PARAMS)
    for p in protein_rows:
        for k in ALL_PARAMS:
            st = p.get("golden_params", {}).get(k, {}).get("status", "")
            if st == "measured_from_feature_matrix_v2":
                measured_v2_entries += 1

    external_rmsd_vals: List[float] = []
    external_rmsd_aligned_vals: List[float] = []
    external_ref_native_vals: List[float] = []
    external_ref_native_aligned_vals: List[float] = []
    external_targets = 0
    for p in protein_rows:
        ext_i = p.get("external_md_accuracy", {})
        if bool(ext_i.get("available")):
            external_targets += 1
            v_r = _to_float(ext_i.get("rmsd_vs_external_ref_A"))
            v_ra = _to_float(ext_i.get("rmsd_vs_external_ref_aligned_A"))
            v_ref = _to_float(ext_i.get("reference_vs_native_rmsd_A"))
            v_refa = _to_float(ext_i.get("reference_vs_native_rmsd_aligned_A"))
            if v_r is not None:
                external_rmsd_vals.append(float(v_r))
            if v_ra is not None:
                external_rmsd_aligned_vals.append(float(v_ra))
            if v_ref is not None:
                external_ref_native_vals.append(float(v_ref))
            if v_refa is not None:
                external_ref_native_aligned_vals.append(float(v_refa))

    quality_targets_with_rows = sum(
        1 for p in protein_rows if int(p.get("structure_data_quality", {}).get("candidate_rows", 0)) > 0
    )
    quality_targets_recommended = sum(
        1 for p in protein_rows if bool(p.get("structure_data_quality", {}).get("include_recommended", False))
    )

    quality_rows_total = int(len(quality_df)) if not quality_df.empty else 0
    quality_rows_included = 0
    quality_mean_weight_included: Optional[float] = None
    if not quality_df.empty and "include" in quality_df.columns:
        include_mask = pd.to_numeric(quality_df["include"], errors="coerce").fillna(0).astype(int) == 1
        quality_rows_included = int(include_mask.sum())
        if "sample_weight" in quality_df.columns:
            ws = pd.to_numeric(quality_df.loc[include_mask, "sample_weight"], errors="coerce").dropna()
            if not ws.empty:
                quality_mean_weight_included = float(ws.mean())

    packet = {
        "meta": {
            "packet_name": f"external_eval_packet_{packet_version}",
            "packet_version": packet_version,
            "generated_at_utc": dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
            "date_local": dt.datetime.now().strftime("%Y-%m-%d"),
            "scope": "single-file external evaluation summary",
        },
        "sources": {
            "gate_json": gate_json_path,
            "parity_target_csv": parity_target_csv_path,
            "stage2_csv": stage2_csv_path,
            "fidelity_csv": fidelity_csv_path,
            "feature_csv": feature_source if packet_version in ("v2", "v3") else None,
                "accuracy_external_csv": accuracy_external_source,
                "quality_curation_csv": quality_curation_source,
                "strict_release_summary_json": strict_release_summary_source,
                "nightly_summary_json": nightly_summary_source,
                "reproducibility_json": reproducibility_source,
                "baseline_config_json": baseline_config_source,
                "claim_correction_summary_json": claim_correction_source,
                "dashboard_json": dashboard_json_resolved,
                "dashboard_html": dashboard_html_resolved,
                "definitions": "core/definitions.py",
                "strategy": "theory/strategy.py",
        },
        "global_summary": {
            "gate_pass": bool(gate_summary.get("pass", False)),
            "targets": int(gate_summary.get("targets", len(protein_rows))),
            "samples_per_target": int(gate_summary.get("samples", 0)),
            "accuracy": {
                "avg_neighbor_jaccard": _to_float(parity_summary.get("avg_neighbor_jaccard")),
                "avg_force_rmse_raw": _to_float(parity_summary.get("avg_force_rmse_raw")),
                "avg_force_rel_rmse_clipped200": _to_float(
                    parity_summary.get("avg_force_rel_rmse_clipped200")
                ),
                "avg_e2e_rmse_raw": _to_float(parity_df["e2e_rmse_mean_raw"].mean())
                if "e2e_rmse_mean_raw" in parity_df
                else None,
                "avg_e2e_rel_rmse_mean_clipped": _to_float(
                    parity_df["e2e_rel_rmse_mean_clipped"].mean()
                )
                if "e2e_rel_rmse_mean_clipped" in parity_df
                else None,
                "overflow_events_count": len(gate.get("overflow_events", [])),
            },
            "speed": {
                "avg_throughput_on_steps_per_sec": _to_float(
                    perf_summary.get("avg_throughput_on")
                ),
                "avg_throughput_off_steps_per_sec": _to_float(
                    perf_summary.get("avg_throughput_off")
                ),
                "avg_speedup_on_vs_off": _to_float(perf_summary.get("avg_speedup_on_vs_off")),
                "avg_throughput_on_steps_per_day": _steps_per_day(
                    _to_float(perf_summary.get("avg_throughput_on"))
                ),
                "avg_throughput_off_steps_per_day": _steps_per_day(
                    _to_float(perf_summary.get("avg_throughput_off"))
                ),
                "speedup_reference": "internal baseline (pytorch fallback path), not external MD engine",
            },
            "external_md_accuracy": {
                "source_present": bool(not external_df.empty),
                "targets_with_external_reference": int(external_targets),
                "avg_rmsd_vs_external_ref_A": (
                    float(np.mean(np.asarray(external_rmsd_vals, dtype=np.float32)))
                    if external_rmsd_vals
                    else None
                ),
                "avg_rmsd_vs_external_ref_aligned_A": (
                    float(np.mean(np.asarray(external_rmsd_aligned_vals, dtype=np.float32)))
                    if external_rmsd_aligned_vals
                    else None
                ),
                "avg_reference_vs_native_rmsd_A": (
                    float(np.mean(np.asarray(external_ref_native_vals, dtype=np.float32)))
                    if external_ref_native_vals
                    else None
                ),
                "avg_reference_vs_native_rmsd_aligned_A": (
                    float(np.mean(np.asarray(external_ref_native_aligned_vals, dtype=np.float32)))
                    if external_ref_native_aligned_vals
                    else None
                ),
            },
            "structure_quality_curation": {
                "source_present": bool(not quality_df.empty),
                "total_rows": int(quality_rows_total),
                "included_rows": int(quality_rows_included),
                "mean_weight_included": quality_mean_weight_included,
                "targets_with_curated_rows": int(quality_targets_with_rows),
                "targets_with_include_recommended": int(quality_targets_recommended),
            },
            "dashboard": _summarize_dashboard(
                dashboard_payload=dashboard_summary,
                nightly_payload=nightly_summary,
                dashboard_json_path=dashboard_json_resolved,
                dashboard_html_path=dashboard_html_resolved,
            ),
            "thresholds": gate_summary.get("thresholds", {}),
            "golden_params": {
                "version": packet_version,
                "q_low": q_low if packet_version in ("v2", "v3") else None,
                "q_high": q_high if packet_version in ("v2", "v3") else None,
                "min_obs": min_obs if packet_version in ("v2", "v3") else None,
                "feature_matrix_rows": (
                    int(feature_df.shape[0]) if packet_version in ("v2", "v3") else None
                ),
                "measured_v2_entries": int(measured_v2_entries) if packet_version in ("v2", "v3") else 0,
                "total_entries": int(total_param_entries),
            },
            "validation_evidence_v3": (
                {
                    "strict_release": _summarize_strict_release(strict_release_summary),
                    "nightly_batch": _summarize_nightly_batch(nightly_summary),
                    "reproducibility": _summarize_reproducibility(reproducibility_summary),
                    "claim_correction_loop": _summarize_claim_correction(claim_correction_summary),
                    "baseline_config": _summarize_baseline_config(baseline_config),
                    "dashboard": _summarize_dashboard(
                        dashboard_payload=dashboard_summary,
                        nightly_payload=nightly_summary,
                        dashboard_json_path=dashboard_json_resolved,
                        dashboard_html_path=dashboard_html_resolved,
                    ),
                }
                if packet_version == "v3"
                else None
            ),
        },
        "branch_capabilities": _branch_capability_summary(),
        "proteins": protein_rows,
        "golden_param_status_summary": status_summary,
        "limitations": (
            [
                "golden parameters are v1 ranges based on currently logged metrics only",
                "variables without direct telemetry remain not_measured_yet",
                "speedup is reported vs internal fallback path, not direct GROMACS/AMBER benchmark",
                "Rg and sasa in this packet are delta/proxy-based metrics from current validation pipeline",
                "optional external_md_accuracy and structure_quality_curation sections are present only when source CSVs are provided",
            ]
            if packet_version == "v1"
            else (
                [
                    "golden parameters use quantile-band v2 estimator from feature_matrix_per_target",
                    "if observations are below min_obs for a parameter, v1 fallback status is kept",
                    "speedup is reported vs internal fallback path, not direct GROMACS/AMBER benchmark",
                    "v2 ranges are empirical and should be re-estimated for new simulation regimes",
                    "optional external_md_accuracy and structure_quality_curation sections are present only when source CSVs are provided",
                ]
                if packet_version == "v2"
                else [
                    "v3 extends v2 with strict/nightly/reproducibility/claim evidence summaries",
                    "v3 evidence blocks are optional and remain unavailable when source JSON is not provided",
                    "golden parameters still use quantile-band v2 estimator from feature_matrix_per_target",
                    "speedup is reported vs internal fallback path, not direct GROMACS/AMBER benchmark",
                    "v3 ranges are empirical and should be re-estimated for new simulation regimes",
                ]
            )
        ),
    }
    return packet


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build one-file external evaluation packet (accuracy/speed/features/golden-params)."
    )
    parser.add_argument(
        "--packet-version",
        type=str,
        choices=["v1", "v2", "v3"],
        default="v2",
    )
    parser.add_argument(
        "--gate-json",
        type=str,
        default="runs/accuracy_gate_rep4.json",
    )
    parser.add_argument(
        "--parity-target-csv",
        type=str,
        default="runs/accuracy_gate_parity_target.csv",
    )
    parser.add_argument(
        "--stage2-csv",
        type=str,
        default="runs/accuracy_gate_stage2.csv",
    )
    parser.add_argument(
        "--fidelity-csv",
        type=str,
        default="runs/physics_fidelity_report.csv",
    )
    parser.add_argument(
        "--feature-csv",
        type=str,
        default="runs/feature_matrix_per_target.csv",
    )
    parser.add_argument(
        "--q-low",
        type=float,
        default=0.10,
    )
    parser.add_argument(
        "--q-high",
        type=float,
        default=0.90,
    )
    parser.add_argument(
        "--min-obs",
        type=int,
        default=64,
    )
    parser.add_argument(
        "--out-json",
        type=str,
        default="runs/external_eval_packet_v2.json",
    )
    parser.add_argument(
        "--accuracy-external-csv",
        type=str,
        default=None,
    )
    parser.add_argument(
        "--quality-curation-csv",
        type=str,
        default=None,
    )
    parser.add_argument(
        "--strict-release-summary-json",
        type=str,
        default=None,
    )
    parser.add_argument(
        "--nightly-summary-json",
        type=str,
        default=None,
    )
    parser.add_argument(
        "--reproducibility-json",
        type=str,
        default=None,
    )
    parser.add_argument(
        "--baseline-config-json",
        type=str,
        default=None,
    )
    parser.add_argument(
        "--claim-correction-summary-json",
        type=str,
        default=None,
    )
    parser.add_argument(
        "--dashboard-json",
        type=str,
        default=None,
    )
    parser.add_argument(
        "--dashboard-html",
        type=str,
        default=None,
    )
    parser.add_argument(
        "--strict-optional-sources",
        action=argparse.BooleanOptionalAction,
        default=False,
    )
    return parser


def main(argv: Optional[List[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    packet = build_packet(args)
    os.makedirs(os.path.dirname(args.out_json) or ".", exist_ok=True)
    with open(args.out_json, "w", encoding="utf-8") as f:
        json.dump(packet, f, indent=2)
    print(f"Wrote: {args.out_json}")
    print(
        json.dumps(
            {
                "packet_version": packet["meta"]["packet_version"],
                "gate_pass": packet["global_summary"]["gate_pass"],
                "targets": packet["global_summary"]["targets"],
                "avg_speedup_on_vs_off": packet["global_summary"]["speed"][
                    "avg_speedup_on_vs_off"
                ],
                "avg_neighbor_jaccard": packet["global_summary"]["accuracy"][
                    "avg_neighbor_jaccard"
                ],
                "measured_v2_entries": packet["global_summary"]["golden_params"][
                    "measured_v2_entries"
                ],
                "external_targets": packet["global_summary"]["external_md_accuracy"][
                    "targets_with_external_reference"
                ],
                "quality_rows": packet["global_summary"]["structure_quality_curation"][
                    "total_rows"
                ],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
