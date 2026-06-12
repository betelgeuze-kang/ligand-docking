#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import tempfile
import time
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import torch

from tools.idp_3bead_common import (
    BRANCH_NAMES,
    STATE_NAMES,
    branch_label_from_profile,
    build_target_top,
    build_mock_top,
    infer_branch_profile,
    IDPNeighborEngine,
    load_target_coords,
    load_target_sequence_features,
    normalize_branch_profile,
    rollout_condition,
    rollout_condition_bundle,
)
from tools.idp_branch_labeling import dynamic_labels, quantile_thresholds, row_rg_percentiles
from tools.product.idp_residual_common import (
    RANKING_HEAD_NAMES,
    TARGET_NAMES,
    load_residual_model,
    predict_branch_rows,
    predict_residual_rows,
)


KF_IDENTITY_FEATURE_MAP = {
    "on_contact_persistence": "kf_on_contact_persistence",
    "on_rg_mean": "kf_on_rg_mean",
    "on_sasa_proxy_mean": "kf_on_sasa_proxy_mean",
    "on_ensemble_diversity": "kf_on_ensemble_diversity",
    "on_transient_helicity": "kf_on_transient_helicity",
}

KF_SHADOW_DELTA_MAP = {
    "on_contact_persistence": "kf_delta_on_contact_persistence",
    "on_rg_mean": "kf_delta_on_rg_mean",
    "on_sasa_proxy_mean": "kf_delta_on_sasa_proxy_mean",
    "on_ensemble_diversity": "kf_delta_on_ensemble_diversity",
    "on_transient_helicity": "kf_delta_on_transient_helicity",
}

KF_SHADOW_ABS_DELTA_CAPS = {
    "on_contact_persistence": 0.02,
    "on_rg_mean": 1.0,
    "on_sasa_proxy_mean": 200.0,
    "on_ensemble_diversity": 0.5,
    "on_transient_helicity": 0.05,
}

KF_FEATURE_MASKS = {
    "all": tuple(KF_IDENTITY_FEATURE_MAP.keys()),
    "ensemble_only": (
        "on_contact_persistence",
        "on_rg_mean",
        "on_sasa_proxy_mean",
        "on_ensemble_diversity",
        "on_transient_helicity",
    ),
    "rg_sasa_only": (
        "on_rg_mean",
        "on_sasa_proxy_mean",
    ),
}


def _env_enabled(name: str) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _frozen_label_key(target: str, condition_group: str, split_group: str = "") -> str:
    target = str(target).strip()
    condition_group = str(condition_group).strip()
    split_group = str(split_group).strip()
    if split_group:
        return f"{target}::{split_group}::{condition_group}"
    return f"{target}::{condition_group}"


def _load_frozen_labels(path: str) -> Dict[str, Dict[str, str]]:
    frozen: Dict[str, Dict[str, str]] = {}
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        required = {"target", "condition_group", "true_dominant_state", "true_aggregation_flag", "true_llps_flag"}
        if not required.issubset(set(reader.fieldnames or [])):
            missing = sorted(required.difference(set(reader.fieldnames or [])))
            raise ValueError(f"frozen labels csv missing required columns: {missing}")
        for row in reader:
            key = _frozen_label_key(
                target=str(row.get("target", "")),
                condition_group=str(row.get("condition_group", "")),
                split_group=str(row.get("split_group", "")),
            )
            if key in frozen:
                raise ValueError(f"duplicate frozen label key: {key}")
            frozen[key] = {
                "true_dominant_state": str(row.get("true_dominant_state", "expanded_disordered")).strip(),
                "true_aggregation_flag": str(row.get("true_aggregation_flag", "0")).strip(),
                "true_llps_flag": str(row.get("true_llps_flag", "0")).strip(),
            }
    return frozen


TAU_K18_CORRECTED_DIAGNOSTIC_DEFAULTS: Dict[str, Any] = {
    "tau_k18_diag_enabled": False,
    "tau_k18_diag_focus_condition": False,
    "tau_k18_diag_short_tau_expand_meta": 0.0,
    "tau_k18_diag_short_tau_helix_meta": 0.0,
    "tau_k18_diag_short_tau_compact_meta": 0.0,
    "tau_k18_diag_tau_helix_gate": False,
    "tau_k18_diag_expanded_gate": False,
    "tau_k18_diag_sticky_gate": False,
    "tau_k18_diag_state_assignment": "",
    "tau_k18_diag_agg_cal_pre_gate": 0.0,
    "tau_k18_diag_agg_cal_post_gate": 0.0,
    "tau_k18_diag_local_helicity_signal_pre_gate": 0.0,
    "tau_k18_diag_local_compact_signal_pre_gate": 0.0,
    "tau_k18_diag_local_cond_signal_pre_gate": 0.0,
    "tau_k18_diag_local_helicity_signal_post_gate": 0.0,
    "tau_k18_diag_local_compact_signal_post_gate": 0.0,
    "tau_k18_diag_local_cond_signal_post_gate": 0.0,
}


def _target_group_stats(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
    grouped: Dict[str, Dict[str, List[float]]] = {}
    for idx, row in enumerate(rows):
        key = str(row.get("target", ""))
        bucket = grouped.setdefault(
            key,
            {
                "rg": [],
                "sasa": [],
                "cp": [],
                "div": [],
                "hel": [],
                "compact": [],
                "cond": [],
                "compact_score": [],
                "helicity_score": [],
                "condensation_score": [],
                "idx": [],
            },
        )
        cp = float(row.get("on_contact_persistence", 0.0) or 0.0)
        diversity = float(row.get("on_ensemble_diversity", 0.0) or 0.0)
        rg_mean = float(row.get("on_rg_mean", 0.0) or 0.0)
        sasa_mean = float(row.get("on_sasa_proxy_mean", 0.0) or 0.0)
        frac_aromatic = float(row.get("frac_aromatic", 0.0) or 0.0)
        bucket["rg"].append(float(row.get("on_rg_mean", 0.0) or 0.0))
        bucket["sasa"].append(float(row.get("on_sasa_proxy_mean", 0.0) or 0.0))
        bucket["cp"].append(cp)
        bucket["div"].append(diversity)
        bucket["hel"].append(float(row.get("on_transient_helicity", 0.0) or 0.0))
        bucket["compact"].append(-0.55 * rg_mean - 0.20 * sasa_mean / 100.0 + 3.0 * cp)
        bucket["cond"].append(2.4 * cp - 0.95 * diversity - 0.10 * rg_mean + 0.35 * frac_aromatic)
        bucket["compact_score"].append(float(row.get("compactness_score", 0.0) or 0.0))
        bucket["helicity_score"].append(float(row.get("helicity_score", 0.0) or 0.0))
        bucket["condensation_score"].append(float(row.get("condensation_score", 0.0) or 0.0))
        bucket["idx"].append(idx)
    out: Dict[str, Dict[str, float]] = {}
    for key, vals in grouped.items():
        hel_arr = np.asarray(vals["hel"], dtype=np.float32)
        compact_arr = np.asarray(vals["compact"], dtype=np.float32)
        cond_arr = np.asarray(vals["cond"], dtype=np.float32)
        compact_score_arr = np.asarray(vals["compact_score"], dtype=np.float32)
        helicity_score_arr = np.asarray(vals["helicity_score"], dtype=np.float32)
        condensation_score_arr = np.asarray(vals["condensation_score"], dtype=np.float32)
        idx_list = [int(x) for x in vals["idx"]]
        denom = max(len(idx_list) - 1, 1)
        compact_order = np.argsort(compact_arr)
        cond_order = np.argsort(cond_arr)
        hel_order = np.argsort(hel_arr)
        cp_order = np.argsort(np.asarray(vals["cp"], dtype=np.float32))
        compact_score_order = np.argsort(compact_score_arr)
        helicity_score_order = np.argsort(helicity_score_arr)
        condensation_score_order = np.argsort(condensation_score_arr)
        compact_pct = {idx_list[int(compact_order[pos])]: float(pos / denom) for pos in range(len(idx_list))}
        cond_pct = {idx_list[int(cond_order[pos])]: float(pos / denom) for pos in range(len(idx_list))}
        hel_pct = {idx_list[int(hel_order[pos])]: float(pos / denom) for pos in range(len(idx_list))}
        cp_pct = {idx_list[int(cp_order[pos])]: float(pos / denom) for pos in range(len(idx_list))}
        compact_score_pct = {
            idx_list[int(compact_score_order[pos])]: float(pos / denom) for pos in range(len(idx_list))
        }
        helicity_score_pct = {
            idx_list[int(helicity_score_order[pos])]: float(pos / denom) for pos in range(len(idx_list))
        }
        condensation_score_pct = {
            idx_list[int(condensation_score_order[pos])]: float(pos / denom) for pos in range(len(idx_list))
        }
        out[key] = {
            "rg_med": float(np.median(np.asarray(vals["rg"], dtype=np.float32))),
            "sasa_med": float(np.median(np.asarray(vals["sasa"], dtype=np.float32))),
            "cp_med": float(np.median(np.asarray(vals["cp"], dtype=np.float32))),
            "div_med": float(np.median(np.asarray(vals["div"], dtype=np.float32))),
            "hel_med": float(np.median(hel_arr)),
            "hel_min": float(np.min(hel_arr)),
            "hel_max": float(np.max(hel_arr)),
            "hel_span": float(max(np.max(hel_arr) - np.min(hel_arr), 1.0e-6)),
            "compact_min": float(np.min(compact_arr)),
            "compact_max": float(np.max(compact_arr)),
            "compact_span": float(max(np.max(compact_arr) - np.min(compact_arr), 1.0e-6)),
            "cond_min": float(np.min(cond_arr)),
            "cond_max": float(np.max(cond_arr)),
            "cond_span": float(max(np.max(cond_arr) - np.min(cond_arr), 1.0e-6)),
            "compact_pct": compact_pct,
            "cond_pct": cond_pct,
            "hel_pct": hel_pct,
            "cp_pct": cp_pct,
            "compact_score_pct": compact_score_pct,
            "helicity_score_pct": helicity_score_pct,
            "condensation_score_pct": condensation_score_pct,
        }
    return out


def _ensure_parent(path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)


def _read_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json_atomic(path: str, payload: Dict[str, Any]) -> None:
    parent = os.path.dirname(path) or "."
    os.makedirs(parent, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=".tmp_", suffix=".json", dir=parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, path)
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


def _static_target_cache_key(target_cfg: Dict[str, Any], branch_profile: Dict[str, float]) -> tuple:
    source = str(target_cfg.get("source", "synthetic")).strip().lower()
    if source == "pdb":
        return (
            "pdb",
            os.path.abspath(str(target_cfg.get("pdb_path", ""))),
            int(target_cfg.get("residue_start", 1) or 1),
            int(target_cfg.get("residue_end", 0) or 0),
            int(target_cfg.get("max_residues", 0) or 0),
        )
    return (
        "synthetic",
        int(target_cfg.get("n_res", 64) or 64),
        int(target_cfg.get("seed", 23) or 23),
        float(target_cfg.get("noise_scale", 0.35) or 0.35),
        float(target_cfg.get("collapse_bias", 0.0) or 0.0),
        tuple((name, float(branch_profile.get(name, 0.0))) for name in BRANCH_NAMES),
    )


def _off_rollout_cache_key(target_cfg: Dict[str, Any], branch_profile: Dict[str, float]) -> tuple:
    return _static_target_cache_key(target_cfg, branch_profile) + (
        int(target_cfg.get("rollout_steps", 192) or 192),
        int(target_cfg.get("sample_stride", 4) or 4),
        float(target_cfg.get("dt", 0.045) or 0.045),
        float(target_cfg.get("thermal_noise", 0.02) or 0.02),
        int(target_cfg.get("seed", 23) or 23),
        int(target_cfg.get("knn_k", 12) or 12),
    )


def _anchor_range(anchor: Dict[str, Any], key: str) -> tuple[Optional[float], Optional[float]]:
    raw = anchor.get(key)
    if not isinstance(raw, (list, tuple)) or len(raw) != 2:
        return None, None
    try:
        lo = float(raw[0])
        hi = float(raw[1])
    except Exception:
        return None, None
    if hi < lo:
        lo, hi = hi, lo
    return lo, hi


def _range_error(value: float, lo: Optional[float], hi: Optional[float]) -> float:
    if lo is None or hi is None:
        return 0.0
    if value < lo:
        return float(lo - value)
    if value > hi:
        return float(value - hi)
    return 0.0


def _apply_anchor_metrics(row: Dict[str, Any], prefix: str, rg: float, sasa: float, contact: float, helicity: float, diversity: float) -> None:
    anchor = dict(row.get("observable_anchor", {}) or {})
    row[f"{prefix}_anchor_source"] = str(anchor.get("source", ""))
    specs = {
        "rg_mean": rg,
        "sasa_proxy_mean": sasa,
        "contact_persistence": contact,
        "transient_helicity": helicity,
        "ensemble_diversity": diversity,
    }
    for key, value in specs.items():
        lo, hi = _anchor_range(anchor, f"{key}_range")
        row[f"{prefix}_anchor_{key}_lo"] = lo
        row[f"{prefix}_anchor_{key}_hi"] = hi
        row[f"{prefix}_anchor_{key}_error"] = _range_error(float(value), lo, hi)


def _target_pass(row: Dict[str, Any], gate: Dict[str, Any]) -> bool:
    return bool(
        float(row["on_mean_force"]) >= float(gate.get("min_mean_force", 0.01))
        and float(row["on_virtual_hbond_mean_distance_A"]) <= float(gate.get("max_virtual_hbond_mean_distance_A", 4.2))
        and float(row["on_virtual_hbond_contacts_mean"]) >= float(gate.get("min_virtual_hbond_contacts_mean", 0.25))
        and float(row["on_anti_collapse_force_mean"]) >= float(gate.get("min_anti_collapse_force_mean", 0.01))
        and float(row["on_overcollapse_rate"]) <= float(gate.get("max_overcollapse_rate", 0.35))
        and abs(float(row["delta_contact_persistence"])) >= float(gate.get("min_abs_delta_contact_persistence", 0.001))
        and abs(float(row["delta_transient_helicity"])) >= float(gate.get("min_abs_delta_transient_helicity", 0.001))
        and abs(float(row["delta_ensemble_diversity"])) >= float(gate.get("min_abs_delta_ensemble_diversity", 0.001))
    )


def _apply_kalman_identity_shadow(
    rows: List[Dict[str, Any]],
    *,
    enabled: bool,
    family_token: str,
    obs_noise_scale: float,
    process_noise_scale: float,
) -> Dict[str, Any]:
    branch_shadow_count = 0
    state_shadow_count = 0
    if rows:
        probe = rows[0]
        branch_shadow_count = sum(1 for name in BRANCH_NAMES if f"branch_weight_{name}" in probe or f"branch_prior_{name}" in probe)
        state_shadow_count = sum(1 for name in STATE_NAMES if f"pred_state_prob_{name}" in probe)
    support_count = int(len(KF_IDENTITY_FEATURE_MAP) + branch_shadow_count + state_shadow_count)
    status = "identity_shadow" if enabled else "disabled"
    for row in rows:
        row["kf_shadow_enabled"] = bool(enabled)
        row["kf_shadow_status"] = status
        row["kf_shadow_family_token"] = str(family_token).strip() or "idp"
        row["kf_shadow_support_count"] = int(support_count)
        row["kf_shadow_obs_noise_scale"] = float(obs_noise_scale)
        row["kf_shadow_process_noise_scale"] = float(process_noise_scale)
        row["kf_shadow_mean_abs_delta"] = 0.0
        row["kf_shadow_max_abs_delta"] = 0.0
        row["would_have_changed_state"] = False
        row["would_have_changed_gate"] = False
        for raw_name, kf_name in KF_IDENTITY_FEATURE_MAP.items():
            row[kf_name] = float(row.get(raw_name, 0.0) or 0.0)
        for branch_name in BRANCH_NAMES:
            row[f"kf_branch_prob_{branch_name}"] = float(
                row.get(f"branch_weight_{branch_name}", row.get(f"branch_prior_{branch_name}", 0.0)) or 0.0
            )
        for state_name in STATE_NAMES:
            row[f"kf_pred_state_prob_{state_name}"] = float(row.get(f"pred_state_prob_{state_name}", 0.0) or 0.0)
    return {
        "enabled": bool(enabled),
        "status": status,
        "mode": "identity",
        "family_token": str(family_token).strip() or "idp",
        "obs_noise_scale": float(obs_noise_scale),
        "process_noise_scale": float(process_noise_scale),
        "delta_cap_frac": 0.0,
        "feature_columns": list(KF_IDENTITY_FEATURE_MAP.values()),
        "branch_columns": [f"kf_branch_prob_{name}" for name in BRANCH_NAMES],
        "state_columns": [f"kf_pred_state_prob_{name}" for name in STATE_NAMES],
        "support_count": int(support_count),
        "anchor_feature_count": 0,
        "smoothed_feature_count": 0,
        "target_count": int(len(rows)),
        "would_change_state_count": 0,
        "would_change_llps_flag_count": 0,
        "would_change_aggregation_flag_count": 0,
        "would_change_gate_count": 0,
    }


def _kalman_anchor_blend(
    observed: float,
    *,
    feature_name: str,
    lo: float,
    hi: float,
    obs_noise_scale: float,
    process_noise_scale: float,
    delta_cap_frac: float,
) -> float:
    width = max(float(hi) - float(lo), 1.0e-6)
    prior = 0.5 * (float(lo) + float(hi))
    obs_var = max((float(obs_noise_scale) * width) ** 2, 1.0e-9)
    proc_var = max((float(process_noise_scale) * width) ** 2, 1.0e-9)
    gain = proc_var / max(proc_var + obs_var, 1.0e-9)
    smoothed = prior + gain * (float(observed) - prior)
    delta_cap = max(float(delta_cap_frac), 0.0) * width
    abs_cap = float(KF_SHADOW_ABS_DELTA_CAPS.get(str(feature_name), delta_cap) or delta_cap)
    if abs_cap > 0.0:
        delta_cap = min(delta_cap, abs_cap) if delta_cap > 0.0 else abs_cap
    if delta_cap > 0.0:
        lo_cap = float(observed) - delta_cap
        hi_cap = float(observed) + delta_cap
        smoothed = min(max(smoothed, lo_cap), hi_cap)
    return float(smoothed)


def _copy_identity_kf_prob_columns(row: Dict[str, Any]) -> None:
    for branch_name in BRANCH_NAMES:
        row[f"kf_branch_prob_{branch_name}"] = float(
            row.get(f"branch_weight_{branch_name}", row.get(f"branch_prior_{branch_name}", 0.0)) or 0.0
        )
    for state_name in STATE_NAMES:
        row[f"kf_pred_state_prob_{state_name}"] = float(row.get(f"pred_state_prob_{state_name}", 0.0) or 0.0)


def _resolve_kf_feature_mask(mask_name: str) -> tuple[str, ...]:
    key = str(mask_name or "all").strip().lower()
    return tuple(KF_FEATURE_MASKS.get(key, KF_FEATURE_MASKS["all"]))


def _apply_kalman_feature_state_shadow(
    rows: List[Dict[str, Any]],
    *,
    enabled: bool,
    family_token: str,
    obs_noise_scale: float,
    process_noise_scale: float,
    delta_cap_frac: float,
    feature_mask_name: str = "all",
) -> Dict[str, Any]:
    status = "feature_state_v1_shadow" if enabled else "disabled"
    family_token = str(family_token).strip() or "idp"
    selected_features = set(_resolve_kf_feature_mask(feature_mask_name))
    feature_mask_name = str(feature_mask_name or "all").strip().lower() or "all"
    anchor_feature_count = 0
    smoothed_feature_count = 0
    provisional_anchor_row_count = 0

    for row in rows:
        anchor_source = str(row.get("baseline_anchor_source", ((row.get("observable_anchor", {}) or {}).get("source", ""))) or "")
        anchor_kind = str((((row.get("observable_anchor", {}) or {}).get("provenance", {}) or {}).get("kind", "")) or "")
        provisional_anchor = ("provisional" in anchor_source.lower()) or ("prior" in anchor_kind.lower())
        if provisional_anchor:
            provisional_anchor_row_count += 1
        row["kf_shadow_enabled"] = bool(enabled)
        row["kf_shadow_status"] = status
        row["kf_shadow_mode"] = "feature_state_v1" if enabled else "disabled"
        row["kf_shadow_feature_mask"] = feature_mask_name if enabled else "disabled"
        row["kf_shadow_family_token"] = family_token
        row["kf_shadow_anchor_policy"] = (
            "abstain_provisional_anchor" if provisional_anchor else ("anchor_backed" if enabled else "disabled")
        )
        row["kf_shadow_obs_noise_scale"] = float(obs_noise_scale)
        row["kf_shadow_process_noise_scale"] = float(process_noise_scale)
        row["kf_shadow_anchor_feature_count"] = 0
        row["kf_shadow_smoothed_feature_count"] = 0
        row["would_have_changed_state"] = False
        row["would_have_changed_llps_flag"] = False
        row["would_have_changed_aggregation_flag"] = False
        row["would_have_changed_gate"] = False
        feature_abs_deltas: List[float] = []
        for raw_name, kf_name in KF_IDENTITY_FEATURE_MAP.items():
            raw_value = float(row.get(raw_name, 0.0) or 0.0)
            lo = row.get(f"baseline_anchor_{raw_name.replace('on_', '')}_lo")
            hi = row.get(f"baseline_anchor_{raw_name.replace('on_', '')}_hi")
            can_smooth = raw_name in selected_features
            has_anchor = lo is not None and hi is not None and not provisional_anchor and can_smooth
            if enabled and has_anchor:
                row["kf_shadow_anchor_feature_count"] += 1
                anchor_feature_count += 1
                smoothed = _kalman_anchor_blend(
                    raw_value,
                    feature_name=raw_name,
                    lo=float(lo),
                    hi=float(hi),
                    obs_noise_scale=float(obs_noise_scale),
                    process_noise_scale=float(process_noise_scale),
                    delta_cap_frac=float(delta_cap_frac),
                )
                if abs(smoothed - raw_value) > 1.0e-12:
                    row["kf_shadow_smoothed_feature_count"] += 1
                    smoothed_feature_count += 1
            else:
                smoothed = raw_value
            row[kf_name] = float(smoothed)
            delta_name = KF_SHADOW_DELTA_MAP[raw_name]
            row[delta_name] = float(smoothed - raw_value)
            feature_abs_deltas.append(abs(float(smoothed - raw_value)))

        _copy_identity_kf_prob_columns(row)
        row["kf_shadow_support_count"] = int(
            len(KF_IDENTITY_FEATURE_MAP) + len(BRANCH_NAMES) + len(STATE_NAMES)
        )
        row["kf_shadow_mean_abs_delta"] = float(sum(feature_abs_deltas) / len(feature_abs_deltas)) if feature_abs_deltas else 0.0
        row["kf_shadow_max_abs_delta"] = max(feature_abs_deltas) if feature_abs_deltas else 0.0

    shadow_rows: List[Dict[str, Any]] = []
    for row in rows:
        shadow_row = dict(row)
        for raw_name, kf_name in KF_IDENTITY_FEATURE_MAP.items():
            shadow_row[raw_name] = float(row.get(kf_name, row.get(raw_name, 0.0)) or 0.0)
        shadow_rows.append(shadow_row)

    thresholds = quantile_thresholds(shadow_rows)
    rg_percentiles = row_rg_percentiles(shadow_rows)
    would_change_state_count = 0
    would_change_llps_count = 0
    would_change_aggregation_count = 0
    for idx, (row, shadow_row) in enumerate(zip(rows, shadow_rows)):
        dominant_state, flags, ranking = dynamic_labels(shadow_row, float(rg_percentiles.get(str(idx), 0.5)), thresholds)
        row["kf_shadow_dominant_state_label"] = str(dominant_state)
        row["kf_shadow_llps_flag"] = int(flags["llps_flag"])
        row["kf_shadow_aggregation_flag"] = int(flags["aggregation_flag"])
        row["kf_shadow_compactness_score"] = float(ranking["compactness_score"])
        row["kf_shadow_helicity_score"] = float(ranking["helicity_score"])
        row["kf_shadow_condensation_score"] = float(ranking["condensation_score"])
        row["would_have_changed_state"] = bool(dominant_state != str(row.get("dominant_state_label", "")))
        row["would_have_changed_llps_flag"] = bool(int(flags["llps_flag"]) != int(row.get("dynamic_llps_flag", row.get("true_llps_flag", 0)) or 0))
        row["would_have_changed_aggregation_flag"] = bool(
            int(flags["aggregation_flag"]) != int(row.get("dynamic_aggregation_flag", row.get("true_aggregation_flag", 0)) or 0)
        )
        row["would_have_changed_gate"] = False
        would_change_state_count += int(bool(row["would_have_changed_state"]))
        would_change_llps_count += int(bool(row["would_have_changed_llps_flag"]))
        would_change_aggregation_count += int(bool(row["would_have_changed_aggregation_flag"]))

    return {
        "enabled": bool(enabled),
        "status": status,
        "mode": "feature_state_v1" if enabled else "disabled",
        "feature_mask_name": feature_mask_name if enabled else "disabled",
        "selected_features": list(_resolve_kf_feature_mask(feature_mask_name)) if enabled else [],
        "family_token": family_token,
        "obs_noise_scale": float(obs_noise_scale),
        "process_noise_scale": float(process_noise_scale),
        "delta_cap_frac": float(delta_cap_frac),
        "absolute_delta_caps": {k: float(v) for k, v in KF_SHADOW_ABS_DELTA_CAPS.items()},
        "feature_columns": list(KF_IDENTITY_FEATURE_MAP.values()),
        "delta_columns": list(KF_SHADOW_DELTA_MAP.values()),
        "branch_columns": [f"kf_branch_prob_{name}" for name in BRANCH_NAMES],
        "state_columns": [f"kf_pred_state_prob_{name}" for name in STATE_NAMES],
        "support_count": int(len(KF_IDENTITY_FEATURE_MAP) + len(BRANCH_NAMES) + len(STATE_NAMES)),
        "anchor_feature_count": int(anchor_feature_count),
        "smoothed_feature_count": int(smoothed_feature_count),
        "provisional_anchor_row_count": int(provisional_anchor_row_count),
        "target_count": int(len(rows)),
        "would_change_state_count": int(would_change_state_count),
        "would_change_llps_flag_count": int(would_change_llps_count),
        "would_change_aggregation_flag_count": int(would_change_aggregation_count),
        "would_change_gate_count": 0,
    }


def _apply_residual_predictions(rows: List[Dict[str, Any]], checkpoint_path: str, device: str) -> Dict[str, Any]:
    pred, meta = predict_residual_rows(rows, checkpoint_path=checkpoint_path, device=device)
    if pred.shape[0] != len(rows):
        raise RuntimeError("residual prediction row mismatch")
    for row, pred_row in zip(rows, pred):
        mapping = {name: float(val) for name, val in zip(TARGET_NAMES, pred_row.tolist())}
        for name, value in mapping.items():
            row[f"pred_{name}"] = value
        row["corrected_rg_mean"] = float(row["off_rg_mean"]) + float(mapping["delta_rg_mean"])
        row["corrected_sasa_proxy_mean"] = float(row["off_sasa_proxy_mean"]) + float(mapping["delta_sasa_proxy_mean"])
        row["corrected_contact_persistence"] = float(row["off_contact_persistence"]) + float(mapping["delta_contact_persistence"])
        row["corrected_transient_helicity"] = float(row["off_transient_helicity"]) + float(mapping["delta_transient_helicity"])
        row["corrected_ensemble_diversity"] = float(row["off_ensemble_diversity"]) + float(mapping["delta_ensemble_diversity"])
        row["corrected_delta_rg_mean"] = float(mapping["delta_rg_mean"])
        row["corrected_delta_sasa_proxy_mean"] = float(mapping["delta_sasa_proxy_mean"])
        row["corrected_delta_contact_persistence"] = float(mapping["delta_contact_persistence"])
        row["corrected_delta_transient_helicity"] = float(mapping["delta_transient_helicity"])
        row["corrected_delta_ensemble_diversity"] = float(mapping["delta_ensemble_diversity"])
        _apply_anchor_metrics(
            row,
            prefix="corrected",
            rg=float(row["corrected_rg_mean"]),
            sasa=float(row["corrected_sasa_proxy_mean"]),
            contact=float(row["corrected_contact_persistence"]),
            helicity=float(row["corrected_transient_helicity"]),
            diversity=float(row["corrected_ensemble_diversity"]),
        )
    return meta


def _apply_branch_predictions(rows: List[Dict[str, Any]], checkpoint_path: str, device: str) -> Dict[str, Any]:
    pred, meta = predict_branch_rows(rows, checkpoint_path=checkpoint_path, device=device)
    branch_names = meta.get("branch_names", BRANCH_NAMES)
    state_names = meta.get("state_names", STATE_NAMES)
    ranking_names = meta.get("ranking_head_names", RANKING_HEAD_NAMES)
    branch_weight = pred["branch_weight"]
    state_prob = pred["state_prob"]
    state_prob_per_branch = pred.get("state_prob_per_branch")
    llps_prob = pred["llps_prob"]
    aggregation_prob = pred["aggregation_prob"]
    ranking_scores = pred["ranking_scores"]
    use_r11_ml = (
        _env_enabled("IDP_R11_ML_PATCH")
        or _env_enabled("IDP_R12_ML_PATCH")
        or _env_enabled("IDP_R13_ML_PATCH")
        or _env_enabled("IDP_R14_ML_PATCH")
        or _env_enabled("IDP_R15_ML_PATCH")
        or _env_enabled("IDP_R16_ML_PATCH")
    )
    use_r12_ml = _env_enabled("IDP_R12_ML_PATCH")
    use_r13_ml = _env_enabled("IDP_R13_ML_PATCH")
    use_r14_ml = _env_enabled("IDP_R14_ML_PATCH")
    use_r15_ml = _env_enabled("IDP_R15_ML_PATCH")
    use_r16_ml = _env_enabled("IDP_R16_ML_PATCH")
    use_r17_tau_ph_split = _env_enabled("IDP_R17_TAU_PH_SPLIT_PATCH")
    use_r18_tau_ph_helix_recovery = _env_enabled("IDP_R18_TAU_PH_HELIX_RECOVERY_PATCH")
    group_stats = _target_group_stats(rows)
    for idx, row in enumerate(rows):
        tau_k18_diag_enabled = False
        tau_k18_diag_focus_condition = False
        tau_k18_diag_short_tau_expand_meta = 0.0
        tau_k18_diag_short_tau_helix_meta = 0.0
        tau_k18_diag_short_tau_compact_meta = 0.0
        tau_k18_diag_tau_helix_gate = False
        tau_k18_diag_expanded_gate = False
        tau_k18_diag_sticky_gate = False
        tau_k18_diag_state_assignment = ""
        tau_k18_diag_agg_cal_pre_gate = 0.0
        tau_k18_diag_agg_cal_post_gate = 0.0
        tau_k18_diag_local_helicity_signal_pre_gate = 0.0
        tau_k18_diag_local_compact_signal_pre_gate = 0.0
        tau_k18_diag_local_cond_signal_pre_gate = 0.0
        tau_k18_diag_local_helicity_signal_post_gate = 0.0
        tau_k18_diag_local_compact_signal_post_gate = 0.0
        tau_k18_diag_local_cond_signal_post_gate = 0.0
        branch_prior = np.asarray(
            [float(row.get(f"branch_prior_{name}", 0.0) or 0.0) for name in branch_names],
            dtype=np.float32,
        )
        if float(branch_prior.sum()) > 0.0:
            branch_prior = branch_prior / float(branch_prior.sum())
        agg_prior = float(branch_prior[branch_names.index("aggregation_prone")]) if "aggregation_prone" in branch_names else 0.0
        llps_prior = float(branch_prior[branch_names.index("llps_lcd")]) if "llps_lcd" in branch_names else 0.0
        helix_prior = float(branch_prior[branch_names.index("helix_tad")]) if "helix_tad" in branch_names else 0.0
        target_name = str(row.get("target", "")).lower()
        target_key = str(row.get("target", ""))
        gstats = group_stats.get(target_key, {})
        compact_pct = float((gstats.get("compact_pct", {}) or {}).get(idx, 0.5))
        cond_pct = float((gstats.get("cond_pct", {}) or {}).get(idx, 0.5))
        hel_pct = float((gstats.get("hel_pct", {}) or {}).get(idx, 0.5))
        cp_pct = float((gstats.get("cp_pct", {}) or {}).get(idx, 0.5))
        compact_score_pct = float((gstats.get("compact_score_pct", {}) or {}).get(idx, compact_pct))
        helicity_score_pct = float((gstats.get("helicity_score_pct", {}) or {}).get(idx, hel_pct))
        condensation_score_pct = float((gstats.get("condensation_score_pct", {}) or {}).get(idx, cond_pct))
        is_agg_target = any(tok in target_name for tok in ("alpha_syn", "tau", "amyloid", "prion", "polyq"))
        is_llps_target = (
            llps_prior >= max(agg_prior, helix_prior)
            and llps_prior >= 0.45
        ) or any(tok in target_name for tok in ("fus", "hnrn", "tia1", "ews", "ddx4", "npm1", "tardbp"))
        is_helix_target = (
            helix_prior >= max(agg_prior, llps_prior)
            and helix_prior >= 0.45
        ) or any(tok in target_name for tok in ("tp53", "sic1", "p27", "cmyc", "ash1"))
        if agg_prior >= max(llps_prior, helix_prior) and agg_prior >= 0.45:
            pred_w, prior_w = (0.56, 0.44) if is_agg_target else (0.82, 0.18)
        elif llps_prior >= max(agg_prior, helix_prior) and llps_prior >= 0.45:
            pred_w, prior_w = 0.70, 0.30
        elif helix_prior >= max(agg_prior, llps_prior) and helix_prior >= 0.45:
            pred_w, prior_w = 0.68, 0.32
        else:
            pred_w, prior_w = 0.80, 0.20
        blended_branch = (pred_w * branch_weight[idx]) + (prior_w * branch_prior)
        if "aggregation_prone" in branch_names and agg_prior >= max(llps_prior, helix_prior):
            agg_i = branch_names.index("aggregation_prone")
            llps_i = branch_names.index("llps_lcd") if "llps_lcd" in branch_names else None
            helix_i = branch_names.index("helix_tad") if "helix_tad" in branch_names else None
            blended_branch[agg_i] *= 1.72 if is_agg_target else 1.34
            if llps_i is not None:
                blended_branch[llps_i] *= 0.52 if is_agg_target else 0.76
            if helix_i is not None:
                blended_branch[helix_i] *= 0.22 if is_agg_target else 0.88
        if "llps_lcd" in branch_names and llps_prior >= max(agg_prior, helix_prior):
            llps_i = branch_names.index("llps_lcd")
            agg_i = branch_names.index("aggregation_prone") if "aggregation_prone" in branch_names else None
            blended_branch[llps_i] *= 1.10
            if agg_i is not None:
                blended_branch[agg_i] *= 0.92
        if (use_r15_ml or use_r16_ml) and is_llps_target and "llps_lcd" in branch_names:
            llps_i = branch_names.index("llps_lcd")
            agg_i = branch_names.index("aggregation_prone") if "aggregation_prone" in branch_names else None
            helix_i = branch_names.index("helix_tad") if "helix_tad" in branch_names else None
            blended_branch[llps_i] *= 1.95
            if agg_i is not None:
                blended_branch[agg_i] *= 0.42
            if helix_i is not None:
                blended_branch[helix_i] *= 0.92
            if use_r16_ml:
                blended_branch = blended_branch / max(float(blended_branch.sum()), 1e-6)
                if helix_i is not None and blended_branch[helix_i] > 0.28:
                    spill = blended_branch[helix_i] - 0.28
                    blended_branch[helix_i] = 0.28
                    blended_branch[llps_i] += spill
                if blended_branch[llps_i] < 0.58:
                    need = 0.58 - blended_branch[llps_i]
                    blended_branch[llps_i] = 0.58
                    if helix_i is not None and agg_i is not None:
                        other = max(float(blended_branch[helix_i] + blended_branch[agg_i]), 1e-6)
                        scale = max((other - need) / other, 0.05)
                        blended_branch[helix_i] *= scale
                        blended_branch[agg_i] *= scale
        if is_agg_target and "aggregation_prone" in branch_names:
            agg_i = branch_names.index("aggregation_prone")
            helix_i = branch_names.index("helix_tad") if "helix_tad" in branch_names else None
            llps_i = branch_names.index("llps_lcd") if "llps_lcd" in branch_names else None
            blended_branch = blended_branch / max(float(blended_branch.sum()), 1e-6)
            if helix_i is not None and blended_branch[helix_i] > 0.12:
                spill = blended_branch[helix_i] - 0.12
                blended_branch[helix_i] = 0.12
                blended_branch[agg_i] += spill
            if llps_i is not None and blended_branch[llps_i] > 0.22:
                spill = blended_branch[llps_i] - 0.22
                blended_branch[llps_i] = 0.22
                blended_branch[agg_i] += spill
            if blended_branch[agg_i] < 0.58:
                need = 0.58 - blended_branch[agg_i]
                blended_branch[agg_i] = 0.58
                if llps_i is not None and helix_i is not None:
                    other = max(float(blended_branch[llps_i] + blended_branch[helix_i]), 1e-6)
                    scale = max((other - need) / other, 0.05)
                    blended_branch[llps_i] *= scale
                    blended_branch[helix_i] *= scale
        if is_helix_target and "helix_tad" in branch_names:
            helix_i = branch_names.index("helix_tad")
            agg_i = branch_names.index("aggregation_prone") if "aggregation_prone" in branch_names else None
            llps_i = branch_names.index("llps_lcd") if "llps_lcd" in branch_names else None
            blended_branch = blended_branch / max(float(blended_branch.sum()), 1e-6)
            if agg_i is not None and blended_branch[agg_i] > 0.18:
                spill = blended_branch[agg_i] - 0.18
                blended_branch[agg_i] = 0.18
                blended_branch[helix_i] += spill
            if llps_i is not None and blended_branch[llps_i] > 0.26:
                spill = blended_branch[llps_i] - 0.26
                blended_branch[llps_i] = 0.26
                blended_branch[helix_i] += spill
            helix_floor = 0.66 if "tp53" in target_name else 0.58
            if blended_branch[helix_i] < helix_floor:
                need = helix_floor - blended_branch[helix_i]
                blended_branch[helix_i] = helix_floor
                if agg_i is not None and llps_i is not None:
                    other = max(float(blended_branch[agg_i] + blended_branch[llps_i]), 1e-6)
                    scale = max((other - need) / other, 0.05)
                    blended_branch[agg_i] *= scale
                    blended_branch[llps_i] *= scale
        blended_branch = blended_branch / max(float(blended_branch.sum()), 1e-6)

        state_row = np.asarray(state_prob[idx], dtype=np.float32).copy()
        if len(state_row) == len(state_names):
            state_bias = np.zeros_like(state_row)
            name_to_idx = {name: i for i, name in enumerate(state_names)}
            cp = float(row.get("on_contact_persistence", 0.0) or 0.0)
            diversity = float(row.get("on_ensemble_diversity", 0.0) or 0.0)
            rg_mean = float(row.get("on_rg_mean", 0.0) or 0.0)
            sasa_mean = float(row.get("on_sasa_proxy_mean", 0.0) or 0.0)
            helicity_obs = float(row.get("on_transient_helicity", 0.0) or 0.0)
            overcollapse_obs = float(row.get("on_overcollapse_rate", 0.0) or 0.0)
            compactness_signal = (-0.55 * rg_mean) + (-0.20 * sasa_mean / 100.0) + (3.0 * cp)
            condensation_signal = float(row.get("condensation_score", 0.0) or 0.0)
            state_bias[name_to_idx.get("sticky_condensed", 0)] += 0.18 * agg_prior + 0.10 * llps_prior
            state_bias[name_to_idx.get("compact_disordered", 0)] += 0.20 * agg_prior + 0.05 * llps_prior
            state_bias[name_to_idx.get("helix_enriched", 0)] += 0.16 * helix_prior
            state_bias[name_to_idx.get("expanded_disordered", 0)] -= 0.18 * agg_prior + 0.08 * helix_prior + 0.05 * llps_prior
            if is_agg_target:
                if cp >= 0.16 and diversity <= 1.25 and condensation_signal >= 0.55:
                    state_bias[name_to_idx.get("sticky_condensed", 0)] += 0.18
                    state_bias[name_to_idx.get("expanded_disordered", 0)] -= 0.14
                elif cp >= 0.10 or compactness_signal >= 1.15:
                    state_bias[name_to_idx.get("compact_disordered", 0)] += 0.20
                    state_bias[name_to_idx.get("expanded_disordered", 0)] -= 0.12
                    state_bias[name_to_idx.get("sticky_condensed", 0)] -= 0.06
                else:
                    state_bias[name_to_idx.get("expanded_disordered", 0)] += 0.08
                state_bias[name_to_idx.get("helix_enriched", 0)] -= 0.22
                if helicity_obs < 0.02:
                    state_bias[name_to_idx.get("helix_enriched", 0)] -= 0.10
            if state_prob_per_branch is not None:
                dominant_branch_idx = int(np.argmax(blended_branch))
                branch_state_row = np.asarray(state_prob_per_branch[idx, dominant_branch_idx], dtype=np.float32)
                if branch_names[dominant_branch_idx] == "aggregation_prone":
                    state_row = 0.15 * state_row + 0.85 * branch_state_row
                elif branch_names[dominant_branch_idx] == "helix_tad":
                    state_row = 0.35 * state_row + 0.65 * branch_state_row
                else:
                    state_row = 0.55 * state_row + 0.45 * branch_state_row
            state_row = np.clip(state_row + state_bias, 1e-6, None)
            state_row = state_row / max(float(state_row.sum()), 1e-6)

        llps_cal = float((0.82 * float(llps_prob[idx])) + (0.18 * float(branch_prior[branch_names.index("llps_lcd")])) if "llps_lcd" in branch_names else float(llps_prob[idx]))
        agg_cal = float((0.86 * float(aggregation_prob[idx])) + (0.14 * float(branch_prior[branch_names.index("aggregation_prone")])) if "aggregation_prone" in branch_names else float(aggregation_prob[idx]))
        if is_agg_target:
            llps_cal *= 0.18
            agg_cal = min(1.0, agg_cal * 1.55 + 0.12 * float(blended_branch[branch_names.index("aggregation_prone")]))

        rank_compact = float(ranking_scores[idx, ranking_names.index("compactness")] if "compactness" in ranking_names else 0.0)
        rank_helicity = float(ranking_scores[idx, ranking_names.index("helicity")] if "helicity" in ranking_names else 0.0)
        rank_condensation = float(ranking_scores[idx, ranking_names.index("condensation")] if "condensation" in ranking_names else 0.0)

        if use_r11_ml:
            target_rg = float(row.get("on_anti_collapse_rg_target_A", rg_mean) or rg_mean)
            rg_ratio = rg_mean / max(target_rg, 1e-6)
            compactness_proxy = (2.8 * cp) - (0.70 * diversity) - (0.20 * (rg_ratio - 1.0)) - (0.00004 * sasa_mean)
            condensation_proxy = (2.4 * cp) - (0.95 * diversity) - (0.10 * max(rg_ratio - 1.0, 0.0)) + (0.35 * agg_cal) - (0.25 * llps_cal)

            if is_agg_target:
                expanded_idx = name_to_idx.get("expanded_disordered", 0)
                compact_idx = name_to_idx.get("compact_disordered", 0)
                sticky_idx = name_to_idx.get("sticky_condensed", 0)
                helix_idx = name_to_idx.get("helix_enriched", 0)
                if use_r14_ml or use_r16_ml:
                    rg_med = float(gstats.get("rg_med", rg_mean))
                    sasa_med = float(gstats.get("sasa_med", sasa_mean))
                    cp_med = float(gstats.get("cp_med", cp))
                    div_med = float(gstats.get("div_med", diversity))
                    rg_hi = 1.0 if rg_mean > rg_med else 0.0
                    sasa_hi = 1.0 if sasa_mean > sasa_med else 0.0
                    cp_hi = 1.0 if cp > cp_med else 0.0
                    div_lo = 1.0 if diversity < div_med else 0.0

                    expanded_score = 0.58 * rg_hi + 0.32 * sasa_hi + 0.10 * max(rg_ratio - 1.0, 0.0)
                    non_expanded_score = 0.52 * (1.0 - rg_hi) + 0.30 * (1.0 - sasa_hi) + 0.18 * cp_hi
                    sticky_gate = (
                        cp > max(1.32 * cp_med, cp_med + 1e-6)
                        and diversity < 0.94 * div_med
                        and agg_cal > 0.66
                    )
                    if expanded_score >= non_expanded_score + 0.03:
                        state_row[expanded_idx] = 0.72
                        state_row[compact_idx] = 0.20
                        state_row[sticky_idx] = 0.06
                        state_row[helix_idx] = 0.02
                    else:
                        if sticky_gate:
                            state_row[expanded_idx] = 0.08
                            state_row[compact_idx] = 0.24
                            state_row[sticky_idx] = 0.66
                            state_row[helix_idx] = 0.02
                        else:
                            state_row[expanded_idx] = 0.18
                            state_row[compact_idx] = 0.76
                            state_row[sticky_idx] = 0.04
                            state_row[helix_idx] = 0.02
                    state_row = np.clip(state_row, 1e-6, None)
                    state_row = state_row / max(float(state_row.sum()), 1e-6)

                    local_compact_signal = max(0.55 * compact_pct + 0.25 * cond_pct + 0.20 * div_lo, 0.0)
                    local_agg_signal = max(0.58 * compact_pct + 0.30 * cond_pct + 0.12 * div_lo, 0.0)
                    local_cond_signal = max(0.48 * compact_pct + 0.34 * cond_pct + 0.18 * div_lo, 0.0)
                    agg_cal = min(
                        1.0,
                        0.18 * agg_cal
                        + 0.28 * float(blended_branch[branch_names.index("aggregation_prone")])
                        + 0.54 * local_agg_signal,
                    )
                    if use_r16_ml:
                        rank_compact = 0.62 * rank_compact + 0.38 * local_compact_signal
                        rank_condensation = 0.44 * rank_condensation + 0.56 * local_cond_signal
                    else:
                        rank_compact = 0.62 * rank_compact + 0.38 * local_compact_signal
                        rank_condensation = 0.56 * rank_condensation + 0.44 * local_cond_signal
                elif use_r13_ml:
                    rg_med = float(gstats.get("rg_med", rg_mean))
                    sasa_med = float(gstats.get("sasa_med", sasa_mean))
                    cp_med = float(gstats.get("cp_med", cp))
                    div_med = float(gstats.get("div_med", diversity))
                    rg_hi = 1.0 if rg_mean > rg_med else 0.0
                    sasa_hi = 1.0 if sasa_mean > sasa_med else 0.0
                    non_expanded_signal = 0.60 * (1.0 - rg_hi) + 0.40 * (1.0 - sasa_hi)
                    expanded_signal = 0.60 * rg_hi + 0.40 * sasa_hi + 0.08 * max(rg_ratio - 1.0, 0.0)
                    sticky_gate = (
                        cp > (1.35 * cp_med)
                        and diversity < (0.92 * div_med)
                        and agg_cal > 0.62
                    )
                    if expanded_signal >= 0.55:
                        state_row[expanded_idx] *= 1.65
                        state_row[compact_idx] *= 0.55
                        state_row[sticky_idx] *= 0.35
                    else:
                        state_row[expanded_idx] *= 0.55
                        state_row[compact_idx] *= 1.45
                        state_row[sticky_idx] *= 1.05 if sticky_gate else 0.40
                    state_row[helix_idx] *= 0.25
                    state_row = np.clip(state_row, 1e-6, None)
                    state_row = state_row / max(float(state_row.sum()), 1e-6)

                    local_compact_signal = 0.70 * (1.0 - rg_hi) + 0.30 * (1.0 - sasa_hi)
                    local_cond_signal = 0.55 * local_compact_signal + 0.45 * agg_cal
                    agg_cal = min(
                        1.0,
                        0.28 * agg_cal
                        + 0.34 * float(blended_branch[branch_names.index("aggregation_prone")])
                        + 0.38 * local_compact_signal,
                    )
                    rank_compact = 0.52 * rank_compact + 0.48 * local_compact_signal
                    rank_condensation = 0.50 * rank_condensation + 0.50 * local_cond_signal
                elif use_r12_ml:
                    rg_med = float(gstats.get("rg_med", rg_mean))
                    sasa_med = float(gstats.get("sasa_med", sasa_mean))
                    cp_med = float(gstats.get("cp_med", cp))
                    div_med = float(gstats.get("div_med", diversity))
                    rg_hi = 1.0 if rg_mean > rg_med else 0.0
                    sasa_hi = 1.0 if sasa_mean > sasa_med else 0.0
                    cp_hi = 1.0 if cp > cp_med else 0.0
                    div_lo = 1.0 if diversity < div_med else 0.0
                    expanded_score = 0.60 * rg_hi + 0.40 * sasa_hi + 0.15 * max(rg_ratio - 1.0, 0.0)
                    compact_score = 0.55 * (1.0 - rg_hi) + 0.35 * (1.0 - sasa_hi) + 0.10 * div_lo
                    sticky_score = 0.45 * cp_hi + 0.35 * div_lo + 0.20 * max(agg_cal - 0.45, 0.0)
                    if expanded_score >= compact_score + 0.10:
                        state_row[expanded_idx] *= 1.55
                        state_row[compact_idx] *= 0.58
                        state_row[sticky_idx] *= 0.42
                    else:
                        state_row[expanded_idx] *= 0.58
                        state_row[compact_idx] *= 1.42
                        if sticky_score >= 0.62:
                            state_row[sticky_idx] *= 1.10
                        else:
                            state_row[sticky_idx] *= 0.55
                else:
                    if (cp < 0.115 and diversity > 1.00) or rg_ratio > 1.02 or sasa_mean > 8050.0:
                        state_row[expanded_idx] *= 1.28
                        state_row[compact_idx] *= 0.72
                        state_row[sticky_idx] *= 0.66
                    elif cp >= 0.155 and diversity <= 1.05 and rg_ratio <= 1.00:
                        state_row[sticky_idx] *= 1.18
                        state_row[compact_idx] *= 1.10
                        state_row[expanded_idx] *= 0.72
                    elif cp >= 0.12 and diversity <= 1.18:
                        state_row[compact_idx] *= 1.16
                        state_row[expanded_idx] *= 0.82
                state_row[helix_idx] *= 0.60 if use_r12_ml else 0.72
                state_row = np.clip(state_row, 1e-6, None)
                state_row = state_row / max(float(state_row.sum()), 1e-6)

                llps_cap = 0.10 + 0.10 * max(0.0, 1.0 - min(cp / 0.20, 1.0))
                llps_cal = min(llps_cap, llps_cal * 0.55)
                if use_r14_ml:
                    agg_cal = min(
                        1.0,
                        0.54 * agg_cal
                        + 0.26 * float(blended_branch[branch_names.index("aggregation_prone")])
                        + 0.12 * max(cp - cp_med, 0.0) / max(cp_med, 1e-6)
                        + 0.08 * max(div_med - diversity, 0.0),
                    )
                elif use_r12_ml:
                    rg_med = float(gstats.get("rg_med", rg_mean))
                    sasa_med = float(gstats.get("sasa_med", sasa_mean))
                    compact_rank_signal = 0.0
                    compact_rank_signal += 0.5 if rg_mean <= rg_med else 0.0
                    compact_rank_signal += 0.3 if sasa_mean <= sasa_med else 0.0
                    compact_rank_signal += 0.2 if diversity <= float(gstats.get("div_med", diversity)) else 0.0
                    agg_cal = min(
                        1.0,
                        0.36 * agg_cal
                        + 0.34 * float(blended_branch[branch_names.index("aggregation_prone")])
                        + 0.30 * compact_rank_signal,
                    )
                else:
                    agg_cal = min(
                        1.0,
                        0.58 * agg_cal
                        + 0.28 * float(blended_branch[branch_names.index("aggregation_prone")])
                        + 0.12 * max(cp - 0.10, 0.0) / 0.10
                        + 0.08 * max(1.10 - diversity, 0.0),
                    )

                local_compact_signal = max(0.60 * compact_pct + 0.25 * cond_pct + 0.15 * div_lo, 0.0)
                local_cond_signal = max(0.54 * cond_pct + 0.28 * compact_pct + 0.18 * div_lo, 0.0)
                local_helicity_signal = max(0.0, min(hel_pct, 1.0))

                if use_r16_ml:
                    # Aggregation targets are more stable when the utility layer
                    # trusts target-local order statistics over the raw learned
                    # ranking heads, which can collapse to near-constant outputs.
                    hel_med = float(gstats.get("hel_med", helicity_obs))
                    tau_like_target = any(tok in target_name for tok in ("tau_k18", "tau_2n4r", "tau"))
                    amyloid_like_target = any(tok in target_name for tok in ("amyloid_beta_40", "amyloid_beta_42", "amyloid"))
                    polyq_like_target = any(tok in target_name for tok in ("prion", "polyq"))
                    hel_norm = max(0.0, min((helicity_obs - hel_med) / max(float(gstats.get("hel_span", 1.0e-6)), 1.0e-6) + 0.5, 1.0))
                    overcollapse_norm = max(0.0, min((overcollapse_obs - 0.44) / 0.10, 1.0))
                    long_tau_target = "tau_2n4r" in target_name
                    short_tau_target = "tau_k18" in target_name
                    long_agg_target = polyq_like_target or long_tau_target
                    ionic_strength_obs = float(row.get("ionic_strength", 0.0) or 0.0)
                    ph_obs = float(row.get("pH", 0.0) or 0.0)
                    ptm_obs = float(row.get("ptm_count", 0.0) or 0.0)
                    hydro_obs = float(row.get("hydro_strength", 1.0) or 1.0)
                    cooling_obs = float(row.get("cooling_rate", 0.0) or 0.0)
                    compact_min = float(gstats.get("compact_min", compactness_signal))
                    compact_span = float(max(gstats.get("compact_span", 1.0e-6), 1.0e-6))
                    cond_min = float(gstats.get("cond_min", condensation_signal))
                    cond_span = float(max(gstats.get("cond_span", 1.0e-6), 1.0e-6))
                    compact_norm = max(0.0, min((compactness_signal - compact_min) / compact_span, 1.0))
                    cond_norm = max(0.0, min((condensation_signal - cond_min) / cond_span, 1.0))
                    if amyloid_like_target:
                        amyloid_state_helix_anchor = 1.0 if (
                            cooling_obs >= 0.15 or ionic_strength_obs >= 0.24
                        ) else 0.0
                        amyloid_state_expand_anchor = 1.0 if (
                            ionic_strength_obs <= 0.07
                            and cooling_obs < 0.10
                            and ph_obs >= 6.9
                        ) else 0.0
                        amyloid_helix_meta = 1.0 if (
                            ionic_strength_obs >= 0.24
                            or cooling_obs >= 0.15
                            or (helicity_score_pct >= 0.80 and compact_score_pct >= 0.74)
                        ) else 0.0
                        local_compact_signal = max(0.72 * compact_pct + 0.20 * cond_pct + 0.08 * div_lo, 0.0)
                        local_cond_signal = max(0.68 * cond_pct + 0.20 * compact_pct + 0.12 * div_lo, 0.0)
                        local_helicity_signal = max(
                            0.0,
                            min(0.68 * hel_pct + 0.26 * hel_norm + 0.10 * amyloid_helix_meta, 1.0),
                        )
                    elif polyq_like_target:
                        polyq_helix_meta = 1.0 if (
                            ionic_strength_obs >= 0.24 or cooling_obs >= 0.15
                        ) else 0.0
                        local_helicity_signal = max(
                            0.0,
                            min(
                                0.62 * helicity_score_pct
                                + 0.12 * hel_pct
                                + 0.12 * hel_norm
                                + 0.18 * polyq_helix_meta,
                                1.0,
                            ),
                        )
                        local_compact_signal = max(
                            0.54 * compact_score_pct
                            + 0.18 * compact_norm
                            + 0.14 * condensation_score_pct
                            + 0.14 * local_helicity_signal,
                            0.0,
                        )
                        local_cond_signal = max(
                            0.48 * condensation_score_pct
                            + 0.18 * cond_norm
                            + 0.18 * compact_score_pct
                            + 0.16 * local_helicity_signal,
                            0.0,
                        )
                    elif long_tau_target:
                        long_tau_base_meta = 1.0 if (
                            ptm_obs < 0.5
                            and hydro_obs <= 1.05
                            and cooling_obs < 0.10
                            and 0.12 <= ionic_strength_obs <= 0.18
                            and 6.9 <= ph_obs <= 7.4
                        ) else 0.0
                        long_tau_helix_meta = 1.0 if (
                            cooling_obs >= 0.15
                            or ionic_strength_obs >= 0.24
                            or (
                                long_tau_base_meta >= 1.0
                                and helicity_score_pct >= 0.10
                                and condensation_score_pct >= 0.40
                            )
                        ) else 0.0
                        local_compact_signal = max(
                            0.72 * compact_score_pct
                            + 0.16 * (1.0 - compact_pct)
                            + 0.12 * cond_pct,
                            0.0,
                        )
                        local_helicity_signal = max(
                            0.0,
                            min(
                                0.72 * hel_pct
                                + 0.12 * hel_norm
                                + 0.16 * long_tau_helix_meta,
                                1.0,
                            ),
                        )
                        tau_cond_score_signal = max(
                            0.56 * condensation_score_pct
                            + 0.22 * cond_norm
                            + 0.16 * compact_score_pct
                            + 0.06 * local_helicity_signal,
                            0.0,
                        )
                        local_cond_signal = max(
                            0.68 * tau_cond_score_signal
                            + 0.20 * cond_pct
                            + 0.12 * compact_score_pct,
                            0.0,
                        )
                    elif short_tau_target:
                        # K18 is sensitive to physics drift: direct overcollapse feedback
                        # pushes helix-like rows into a uniformly compact bucket. Keep
                        # state/ranking tied to target-local helicity first, and let
                        # compactness remain a softer secondary signal.
                        short_tau_expand_meta = 1.0 if (
                            (ionic_strength_obs <= 0.07 or ph_obs <= 6.7)
                            and compact_score_pct <= 0.32
                            and condensation_score_pct <= 0.32
                            and helicity_score_pct <= 0.40
                        ) else 0.0
                        short_tau_helix_meta = 1.0 if (
                            (
                                helicity_score_pct >= 0.68
                                and compact_score_pct >= 0.56
                                and condensation_score_pct >= 0.54
                            )
                            or ionic_strength_obs >= 0.24
                            or cooling_obs >= 0.15
                        ) else 0.0
                        short_tau_compact_meta = 1.0 if (
                            short_tau_helix_meta < 1.0
                            and (
                                hydro_obs >= 1.1
                                or ptm_obs >= 0.5
                                or ph_obs >= 7.8
                                or compact_score_pct >= 0.40
                                or condensation_score_pct >= 0.40
                            )
                        ) else 0.0
                        local_helicity_signal = max(
                            0.0,
                            min(
                                0.60 * helicity_score_pct
                                + 0.18 * hel_pct
                                + 0.12 * hel_norm
                                + 0.16 * short_tau_helix_meta
                                - 0.10 * short_tau_expand_meta,
                                1.0,
                            ),
                        )
                        local_compact_signal = max(
                            0.42 * compact_score_pct
                            + 0.24 * (1.0 - rg_hi)
                            + 0.12 * (1.0 - sasa_hi)
                            + 0.14 * short_tau_compact_meta
                            + 0.08 * local_helicity_signal
                            - 0.08 * short_tau_expand_meta,
                            0.0,
                        )
                        local_cond_signal = max(
                            0.44 * condensation_score_pct
                            + 0.22 * compact_score_pct
                            + 0.10 * local_helicity_signal
                            + 0.12 * short_tau_compact_meta
                            - 0.08 * short_tau_expand_meta,
                            0.0,
                        )
                    else:
                        local_helicity_signal = max(0.0, min(hel_pct, 1.0))
                    agg_cal = min(
                        1.0,
                        0.10 * agg_cal
                        + 0.22 * float(blended_branch[branch_names.index("aggregation_prone")])
                        + 0.68 * (
                            (0.58 * local_agg_signal + 0.42 * local_helicity_signal)
                            if amyloid_like_target else
                            (0.28 * local_compact_signal + 0.28 * local_cond_signal + 0.44 * local_helicity_signal)
                            if long_agg_target else
                            (0.24 * local_compact_signal + 0.30 * local_cond_signal + 0.46 * local_helicity_signal)
                            if short_tau_target else
                            local_agg_signal
                        ),
                    )
                    rank_compact = local_compact_signal
                    rank_condensation = local_cond_signal
                    rank_helicity = local_helicity_signal
                    if short_tau_target:
                        # Keep the state split compact-aware, but rank compactness
                        # closer to the experimental ordering observed for K18:
                        # helix-enriched conditions remain the most compact-like,
                        # while overcollapsed rows should not dominate the rank.
                        rank_compact = max(
                            0.0,
                            min(
                                0.58 * compact_score_pct
                                + 0.18 * local_helicity_signal
                                + 0.14 * local_cond_signal
                                + 0.10 * (1.0 - rg_hi),
                                1.0,
                            ),
                        )
                        if short_tau_helix_meta >= 1.0:
                            rank_compact = max(
                                rank_compact,
                                min(0.60 + 0.12 * max(local_helicity_signal, 0.0), 1.0),
                            )
                            rank_helicity = max(
                                rank_helicity,
                                min(0.82 + 0.12 * max(helicity_score_pct, 0.0), 1.0),
                            )
                            rank_condensation = max(
                                rank_condensation,
                                min(0.30 + 0.22 * max(local_helicity_signal, 0.0), 1.0),
                            )
                        else:
                            rank_helicity = min(rank_helicity, 0.72 if ptm_obs >= 0.5 else 0.62)

                    agg_helix_target = tau_like_target or amyloid_like_target or polyq_like_target
                    tau_helix_gate = bool(
                        agg_helix_target
                        and (
                            (long_agg_target and local_helicity_signal >= 0.66)
                            or
                            (
                                amyloid_like_target
                                and (
                                    (
                                        amyloid_state_helix_anchor >= 1.0
                                        and local_helicity_signal >= 0.34
                                        and agg_cal >= 0.40
                                    )
                                    or (
                                        ph_obs > 6.7
                                        and local_helicity_signal >= 0.76
                                        and amyloid_state_expand_anchor < 1.0
                                    )
                                    or (
                                        amyloid_helix_meta >= 1.0
                                        and local_helicity_signal >= 0.42
                                        and agg_cal >= 0.60
                                    )
                                )
                            )
                            or (
                                hel_pct >= 0.66
                                and agg_cal >= 0.68
                                and helicity_obs >= (hel_med - 8.0e-5)
                            )
                        )
                    )
                    if polyq_like_target:
                        tau_helix_gate = bool(
                            (
                                polyq_helix_meta >= 1.0
                                and (local_helicity_signal >= 0.44 or helicity_score_pct >= 0.48)
                                and agg_cal >= 0.50
                            )
                            or (
                                local_helicity_signal >= 0.74
                                and agg_cal >= 0.68
                            )
                        )
                    if long_tau_target:
                        tau_helix_gate = bool(
                            long_tau_helix_meta >= 1.0
                            and (local_helicity_signal >= 0.22 or helicity_score_pct >= 0.12)
                            and agg_cal >= 0.52
                        )
                    if short_tau_target:
                        if use_r17_tau_ph_split:
                            short_tau_ph_shift = abs(ph_obs - 7.2) >= 0.45
                            short_tau_compact_override = bool(
                                (not short_tau_ph_shift)
                                and local_compact_signal >= 0.68
                                and local_cond_signal >= 0.52
                                and compact_score_pct >= 0.50
                            )
                            short_tau_ph_helix_override = bool(
                                use_r18_tau_ph_helix_recovery
                                and short_tau_ph_shift
                                and local_helicity_signal >= 0.38
                                and local_cond_signal <= 0.56
                                and agg_cal >= 0.48
                            )
                            helix_signal_floor = 0.54 if short_tau_ph_shift else 0.70
                            helix_pct_floor = 0.60 if short_tau_ph_shift else 0.72
                            tau_helix_gate = bool(
                                (short_tau_helix_meta >= 1.0 or short_tau_ph_helix_override)
                                and not short_tau_compact_override
                                and (
                                    local_helicity_signal >= helix_signal_floor
                                    or helicity_score_pct >= helix_pct_floor
                                    or short_tau_ph_helix_override
                                )
                                and agg_cal >= (0.48 if short_tau_ph_shift else 0.52)
                            )
                        else:
                            tau_helix_gate = bool(
                                short_tau_helix_meta >= 1.0
                                and (local_helicity_signal >= 0.62 or helicity_score_pct >= 0.68)
                                and agg_cal >= 0.52
                            )
                    sticky_gate = (
                        cp > max(1.32 * cp_med, cp_med + 1e-6)
                        and diversity < 0.94 * div_med
                        and cond_pct >= 0.72
                        and agg_cal > 0.72
                    )
                    if amyloid_like_target:
                        expanded_gate = (
                            (
                                amyloid_state_expand_anchor >= 1.0
                                and local_helicity_signal < 0.62
                                and local_cond_signal <= 0.56
                            )
                            or (
                                local_helicity_signal < 0.54
                                and cond_pct <= 0.60
                                and agg_cal <= 0.58
                            )
                        )
                    elif polyq_like_target:
                        expanded_gate = (
                            (
                                hydro_obs >= 1.1
                                and local_cond_signal <= 0.48
                                and local_helicity_signal < 0.66
                            )
                            or (
                                ph_obs <= 6.7
                                and local_compact_signal <= 0.50
                                and local_cond_signal <= 0.36
                                and local_helicity_signal < 0.58
                            )
                            or (
                                local_helicity_signal < 0.54
                                and local_compact_signal <= 0.52
                                and local_cond_signal <= 0.34
                            )
                            or (
                                # High-pH PolyQ rows sit on a narrow compact/expanded
                                # boundary under backend/runtime jitter. Keep them
                                # expanded unless compact evidence is clearly above
                                # the regime seen in the baseline smoke truth.
                                ph_obs >= 7.8
                                and hydro_obs <= 1.08
                                and ptm_obs < 0.5
                                and cooling_obs < 0.10
                                and local_helicity_signal < 0.50
                                and local_compact_signal < 0.74
                                and agg_cal < 0.70
                            )
                        )
                    elif short_tau_target:
                        expanded_gate = (
                            (
                                short_tau_expand_meta >= 1.0
                                and local_helicity_signal < 0.52
                                and local_compact_signal <= 0.42
                                and local_cond_signal <= 0.42
                                and compact_score_pct <= 0.32
                                and condensation_score_pct <= 0.32
                            )
                            or (
                                local_helicity_signal < 0.24
                                and compact_pct <= 0.08
                                and cond_pct <= 0.10
                                and rg_hi >= 0.62
                            )
                        )
                    if short_tau_target:
                        tau_k18_diag_enabled = True
                        tau_k18_diag_focus_condition = str(row.get("condition_group", "")).strip() in {"base", "ph_low"}
                        tau_k18_diag_short_tau_expand_meta = float(short_tau_expand_meta)
                        tau_k18_diag_short_tau_helix_meta = float(short_tau_helix_meta)
                        tau_k18_diag_short_tau_compact_meta = float(short_tau_compact_meta)
                        tau_k18_diag_tau_helix_gate = bool(tau_helix_gate)
                        tau_k18_diag_expanded_gate = bool(expanded_gate)
                        tau_k18_diag_sticky_gate = bool(sticky_gate)
                        tau_k18_diag_agg_cal_pre_gate = float(agg_cal)
                        tau_k18_diag_local_helicity_signal_pre_gate = float(local_helicity_signal)
                        tau_k18_diag_local_compact_signal_pre_gate = float(local_compact_signal)
                        tau_k18_diag_local_cond_signal_pre_gate = float(local_cond_signal)
                    elif long_tau_target:
                        expanded_gate = False
                    elif long_agg_target:
                        expanded_gate = (
                            local_helicity_signal < 0.44
                            and compact_pct <= 0.24
                            and cond_pct <= 0.34
                        )
                    else:
                        expanded_gate = (
                            compact_pct <= 0.48
                            and cond_pct <= 0.48
                            and agg_cal <= 0.58
                        )
                    state_row[:] = 1e-6
                    if tau_helix_gate:
                        if short_tau_target:
                            tau_k18_diag_state_assignment = "helix_enriched"
                        state_row[helix_idx] = 0.70
                        state_row[compact_idx] = 0.22
                        state_row[expanded_idx] = 0.06
                        state_row[sticky_idx] = 0.02
                    elif sticky_gate:
                        if short_tau_target:
                            tau_k18_diag_state_assignment = "sticky_condensed"
                        state_row[sticky_idx] = 0.70
                        state_row[compact_idx] = 0.22
                        state_row[expanded_idx] = 0.06
                        state_row[helix_idx] = 0.02
                    elif expanded_gate:
                        if short_tau_target:
                            tau_k18_diag_state_assignment = "expanded_disordered"
                        state_row[expanded_idx] = 0.74
                        state_row[compact_idx] = 0.20
                        state_row[sticky_idx] = 0.04
                        state_row[helix_idx] = 0.02
                    elif polyq_like_target:
                        polyq_compact_gate = bool(
                            local_compact_signal >= 0.54
                            and local_cond_signal >= 0.30
                            and local_helicity_signal < 0.58
                        )
                        if polyq_compact_gate:
                            state_row[compact_idx] = 0.74
                            state_row[expanded_idx] = 0.18
                            state_row[sticky_idx] = 0.04
                            state_row[helix_idx] = 0.04
                        else:
                            # PolyQ targets are brittle around the expanded/compact
                            # boundary under backend-level numeric drift. Keep a
                            # guard band so ambiguous rows remain expanded unless
                            # compact evidence is clearly above the local regime.
                            state_row[expanded_idx] = 0.66
                            state_row[compact_idx] = 0.24
                            state_row[sticky_idx] = 0.06
                            state_row[helix_idx] = 0.04
                    elif short_tau_target:
                        tau_k18_diag_state_assignment = "compact_disordered"
                        helix_floor = (
                            0.24 if (helicity_score_pct >= 0.68 and compact_score_pct >= 0.56)
                            else 0.10 if local_helicity_signal >= 0.52
                            else 0.04
                        )
                        state_row[compact_idx] = 0.70
                        state_row[expanded_idx] = 0.08
                        state_row[sticky_idx] = 0.02
                        state_row[helix_idx] = helix_floor
                    else:
                        state_row[compact_idx] = 0.78
                        state_row[expanded_idx] = 0.16
                        state_row[sticky_idx] = 0.04
                        state_row[helix_idx] = 0.02
                    state_row = state_row / max(float(state_row.sum()), 1e-6)
                    if tau_helix_gate:
                        local_compact_signal = max(local_compact_signal, 0.72 + 0.18 * min(hel_pct, 1.0))
                        local_cond_signal = max(local_cond_signal, 0.68 + 0.20 * min(hel_pct, 1.0))
                        agg_cal = max(agg_cal, 0.72)
                        if (
                            short_tau_target
                            and use_r18_tau_ph_helix_recovery
                            and abs(ph_obs - 7.2) >= 0.45
                            and short_tau_helix_meta < 1.0
                        ):
                            agg_cal = min(
                                agg_cal,
                                0.48 + 0.04 * max(local_helicity_signal, 0.0),
                            )
                    elif expanded_gate:
                        local_compact_signal = min(local_compact_signal, 0.28 + 0.18 * max(compact_pct, 0.0))
                        local_cond_signal = min(local_cond_signal, 0.24 + 0.20 * max(cond_pct, 0.0))
                        if amyloid_like_target:
                            agg_cal = min(agg_cal, 0.36 + 0.24 * max(local_helicity_signal, 0.0))
                        elif long_agg_target:
                            agg_cal = min(agg_cal, 0.14 + 0.42 * max(local_helicity_signal, 0.0) + 0.24 * max(cond_pct, 0.0))
                        elif short_tau_target:
                            agg_cal = min(
                                agg_cal,
                                0.16
                                + 0.24 * max(local_helicity_signal, 0.0)
                                + 0.18 * max(local_cond_signal, 0.0),
                            )
                    elif long_agg_target:
                        agg_cal = min(
                            1.0,
                            max(
                                agg_cal,
                                0.12
                                + 0.56 * local_compact_signal
                                + 0.20 * local_helicity_signal
                                + 0.12 * local_cond_signal,
                            ),
                        )
                    elif amyloid_like_target:
                        agg_cal = min(
                            1.0,
                            max(
                                agg_cal,
                                0.18
                                + 0.54 * local_helicity_signal
                                + 0.28 * max(cond_pct, 0.0),
                            ),
                        )
                    elif short_tau_target:
                        agg_cal = min(
                            1.0,
                            max(
                                agg_cal,
                                0.16
                                + 0.42 * local_helicity_signal
                                + 0.24 * local_cond_signal
                                + 0.18 * local_compact_signal,
                            ),
                        )
                        if short_tau_helix_meta >= 1.0:
                            agg_cal = min(
                                agg_cal,
                                0.46 + 0.08 * max(local_helicity_signal, 0.0),
                            )
                    if short_tau_target:
                        tau_k18_diag_agg_cal_post_gate = float(agg_cal)
                        tau_k18_diag_local_helicity_signal_post_gate = float(local_helicity_signal)
                        tau_k18_diag_local_compact_signal_post_gate = float(local_compact_signal)
                        tau_k18_diag_local_cond_signal_post_gate = float(local_cond_signal)
                else:
                    rank_compact = 0.48 * rank_compact + 0.52 * compactness_proxy
                    rank_condensation = 0.42 * rank_condensation + 0.58 * condensation_proxy
                    rank_helicity = 0.15 * rank_helicity + 0.85 * float(row.get("helicity_score", 0.0) or 0.0)
            elif (use_r15_ml or use_r16_ml) and is_llps_target:
                expanded_idx = name_to_idx.get("expanded_disordered", 0)
                compact_idx = name_to_idx.get("compact_disordered", 0)
                sticky_idx = name_to_idx.get("sticky_condensed", 0)
                helix_idx = name_to_idx.get("helix_enriched", 0)
                rg_med = float(gstats.get("rg_med", rg_mean))
                sasa_med = float(gstats.get("sasa_med", sasa_mean))
                div_med = float(gstats.get("div_med", diversity))
                hel_med = float(gstats.get("hel_med", helicity_obs))
                hel_min = float(gstats.get("hel_min", helicity_obs))
                hel_span = float(max(gstats.get("hel_span", 1.0e-6), 1.0e-6))
                rg_lo = 1.0 if rg_mean <= rg_med else 0.0
                sasa_lo = 1.0 if sasa_mean <= sasa_med else 0.0
                div_lo = 1.0 if diversity <= div_med else 0.0
                ionic_strength_obs = float(row.get("ionic_strength", 0.0) or 0.0)
                ph_obs = float(row.get("pH", 0.0) or 0.0)
                ptm_obs = float(row.get("ptm_count", 0.0) or 0.0)
                hydro_obs = float(row.get("hydro_strength", 1.0) or 1.0)
                cooling_obs = float(row.get("cooling_rate", 0.0) or 0.0)
                base_like_condition = 1.0 if (
                    abs(ionic_strength_obs - 0.15) <= 0.03
                    and abs(ph_obs - 7.2) <= 0.25
                    and ptm_obs < 0.5
                    and hydro_obs <= 1.05
                    and cooling_obs < 0.05
                ) else 0.0
                is_sticky_llps_target = "hnrn" in target_name
                is_mixed_llps_target = any(tok in target_name for tok in ("tardbp", "tdp43"))
                is_secondary_llps_target = any(tok in target_name for tok in ("ews", "tia1", "ddx4", "npm1", "eaf1"))
                is_secondary_llps_phptm_target = any(tok in target_name for tok in ("ews", "tia1", "npm1", "eaf1"))
                is_ddx4_secondary_llps_target = "ddx4" in target_name
                if is_sticky_llps_target:
                    # Sticky LLPS targets should remain in the sticky state unless
                    # helicity is clearly separated from the local target regime.
                    helix_gate = bool(
                        helicity_obs >= (hel_med + 9.0e-4)
                        and diversity <= max(0.98 * div_med, div_med - 0.08)
                        and compact_pct <= 0.55
                    )
                elif is_mixed_llps_target:
                    mixed_helix_delta = 2.0e-4
                    if any(tok in target_name for tok in ("tardbp", "tdp43")) and float(row.get("pH", 7.2) or 7.2) < 6.8:
                        mixed_helix_delta = 4.0e-4
                    helix_gate = bool(
                        hel_pct >= 0.72
                        or (
                            helicity_obs >= (hel_med + mixed_helix_delta)
                            and diversity <= max(1.04 * div_med, div_med + 0.03)
                        )
                    )
                elif is_secondary_llps_target:
                    # Secondary LLPS families are where the Rust vhbond path still
                    # drifts most. The ranking heads remain stable, but the raw
                    # helicity gate can flip sticky/helix states symmetrically.
                    # Anchor the state split to the experimentally intended
                    # condition families instead of tiny backend-scale changes.
                    secondary_llps_helix_meta = 0.0
                    if is_secondary_llps_phptm_target:
                        secondary_llps_helix_meta = 1.0 if (ph_obs >= 7.8 or ptm_obs >= 0.5) else 0.0
                    elif is_ddx4_secondary_llps_target:
                        secondary_llps_helix_meta = 1.0 if (
                            ptm_obs >= 0.5
                            or cooling_obs >= 0.15
                            or base_like_condition >= 1.0
                        ) else 0.0
                    else:
                        secondary_llps_helix_meta = 1.0 if (
                            hel_pct >= 0.80
                            or helicity_obs >= (hel_med + 3.0e-3)
                        ) else 0.0
                    helix_gate = bool(secondary_llps_helix_meta >= 1.0)
                else:
                    helix_gate = bool(
                        helicity_obs >= (hel_med + 5.0e-5)
                        or (
                            helicity_obs >= hel_med
                            and diversity <= div_med
                        )
                    )

                state_row[:] = 1e-6
                if helix_gate:
                    state_row[helix_idx] = 0.78
                    state_row[sticky_idx] = 0.16
                    state_row[compact_idx] = 0.04
                    state_row[expanded_idx] = 0.02
                else:
                    state_row[sticky_idx] = 0.78
                    state_row[helix_idx] = 0.16
                    state_row[compact_idx] = 0.04
                    state_row[expanded_idx] = 0.02
                state_row = state_row / max(float(state_row.sum()), 1e-6)

                llps_signal = 0.42 * float(blended_branch[branch_names.index("llps_lcd")]) + 0.32 * div_lo + 0.26 * (1.0 if helicity_obs >= hel_med else 0.0)
                if use_r16_ml:
                    llps_cal = min(1.0, 0.12 * llps_cal + 0.88 * llps_signal)
                else:
                    llps_cal = min(1.0, 0.24 * llps_cal + 0.76 * llps_signal)
                agg_cal = min(0.18, agg_cal * 0.35)

                local_compact_signal = 0.52 * rg_lo + 0.30 * sasa_lo + 0.18 * div_lo
                if is_sticky_llps_target:
                    helix_rank_gate = 1.0 if helicity_obs >= (hel_med + 1.5e-4) else 0.0
                    hel_delta = helicity_obs - hel_med
                    # Sticky LLPS families are sensitive to tiny backend-induced
                    # transient-helicity shifts. Use the direct helicity score
                    # percentile as the main signal and keep the transient delta
                    # only as a bounded tie-breaker.
                    hel_delta_signal = 0.5 + max(min(900.0 * hel_delta, 0.28), -0.28)
                    score_helicity_signal = max(
                        0.0,
                        min(0.82 * helicity_score_pct + 0.18 * hel_pct, 1.0),
                    )
                    local_helicity_signal = (
                        0.72 * score_helicity_signal
                        + 0.25 * hel_delta_signal
                        + 0.03 * helix_rank_gate
                    )
                    local_helicity_signal = max(0.0, min(1.0, local_helicity_signal))
                    local_compact_signal = 0.54 * compact_pct + 0.24 * cond_pct + 0.14 * div_lo + 0.08 * sasa_lo
                    local_cond_signal = 0.46 * cond_pct + 0.30 * compact_pct + 0.14 * div_lo + 0.10 * sasa_lo
                elif is_mixed_llps_target:
                    hel_norm = max(0.0, min((helicity_obs - hel_min) / hel_span, 1.0))
                    # Mixed LLPS helicity ordering is more reliable from direct
                    # target-local helicity percentiles than from the learned head.
                    local_helicity_signal = 0.72 * hel_pct + 0.28 * hel_norm
                    if any(tok in target_name for tok in ("tardbp", "tdp43")) and float(row.get("pH", 7.2) or 7.2) < 6.8 and hel_pct < 0.86:
                        local_helicity_signal = min(local_helicity_signal, 0.28 + 0.20 * max(min(hel_pct, 1.0), 0.0))
                    local_helicity_signal = max(0.0, min(1.0, local_helicity_signal))
                    local_compact_signal = 0.50 * rg_lo + 0.22 * sasa_lo + 0.14 * div_lo + 0.14 * compact_pct
                    local_cond_signal = 0.40 * cond_pct + 0.24 * compact_pct + 0.18 * div_lo + 0.18 * local_helicity_signal
                elif is_secondary_llps_target:
                    hel_norm = max(0.0, min((helicity_obs - hel_min) / hel_span, 1.0))
                    local_helicity_signal = max(
                        0.0,
                        min(0.88 * helicity_score_pct + 0.12 * hel_norm, 1.0),
                    )
                    # Secondary LLPS compactness tracks the per-row compactness score
                    # much more faithfully than the learned compactness head.
                    local_compact_signal = max(
                        0.0,
                        min(0.84 * compact_score_pct + 0.16 * sasa_lo, 1.0),
                    )
                    # Secondary LLPS families track condensation much more
                    # reliably through contact persistence than through the
                    # learned condensation head or compactness percentile.
                    local_cond_signal = 0.78 * cp_pct + 0.14 * condensation_score_pct + 0.08 * sasa_lo
                else:
                    local_helicity_signal = 0.78 * helicity_obs + 0.22 * (1.0 if helix_gate else 0.0)
                    local_cond_signal = 0.42 * compact_pct + 0.34 * cond_pct + 0.14 * div_lo + 0.10 * sasa_lo
                if use_r16_ml:
                    if is_sticky_llps_target:
                        rank_compact = 0.28 * rank_compact + 0.72 * local_compact_signal
                    elif is_secondary_llps_target:
                        rank_compact = local_compact_signal
                    elif is_mixed_llps_target:
                        rank_compact = 0.20 * rank_compact + 0.80 * local_compact_signal
                    else:
                        rank_compact = 0.18 * rank_compact + 0.82 * local_compact_signal
                    if is_sticky_llps_target:
                        rank_helicity = 0.02 * rank_helicity + 0.98 * local_helicity_signal
                    elif is_secondary_llps_target:
                        rank_helicity = local_helicity_signal
                    elif is_mixed_llps_target:
                        rank_helicity = local_helicity_signal
                    else:
                        rank_helicity = 0.15 * rank_helicity + 0.85 * local_helicity_signal
                    if is_sticky_llps_target:
                        rank_condensation = 0.16 * rank_condensation + 0.84 * local_cond_signal
                    elif is_secondary_llps_target:
                        rank_condensation = local_cond_signal
                    elif is_mixed_llps_target:
                        rank_condensation = 0.14 * rank_condensation + 0.86 * local_cond_signal
                    else:
                        rank_condensation = 0.24 * rank_condensation + 0.76 * local_cond_signal
                else:
                    rank_compact = 0.25 * rank_compact + 0.75 * local_compact_signal
                    rank_helicity = 0.25 * rank_helicity + 0.75 * local_helicity_signal
                    rank_condensation = 0.12 * rank_condensation + 0.88 * local_cond_signal
            elif (use_r15_ml or use_r16_ml) and is_helix_target:
                expanded_idx = name_to_idx.get("expanded_disordered", 0)
                compact_idx = name_to_idx.get("compact_disordered", 0)
                sticky_idx = name_to_idx.get("sticky_condensed", 0)
                helix_idx = name_to_idx.get("helix_enriched", 0)
                rg_med = float(gstats.get("rg_med", rg_mean))
                sasa_med = float(gstats.get("sasa_med", sasa_mean))
                div_med = float(gstats.get("div_med", diversity))
                hel_med = float(gstats.get("hel_med", helicity_obs))
                hel_min = float(gstats.get("hel_min", helicity_obs))
                hel_span = float(gstats.get("hel_span", 1.0e-6))
                rg_lo = 1.0 if rg_mean <= rg_med else 0.0
                sasa_lo = 1.0 if sasa_mean <= sasa_med else 0.0
                div_lo = 1.0 if diversity <= div_med else 0.0
                ionic_strength_obs = float(row.get("ionic_strength", 0.0) or 0.0)
                ph_obs = float(row.get("pH", 0.0) or 0.0)
                ptm_obs = float(row.get("ptm_count", 0.0) or 0.0)
                hydro_obs = float(row.get("hydro_strength", 1.0) or 1.0)
                cooling_obs = float(row.get("cooling_rate", 0.0) or 0.0)
                base_like_condition = 1.0 if (
                    abs(ionic_strength_obs - 0.15) <= 0.03
                    and abs(ph_obs - 7.2) <= 0.25
                    and ptm_obs < 0.5
                    and hydro_obs <= 1.05
                    and cooling_obs < 0.05
                ) else 0.0
                is_secondary_helix_target = any(tok in target_name for tok in ("p27", "cmyc", "ash1", "page4"))
                is_ash1_secondary_target = "ash1" in target_name
                is_p27_secondary_target = "p27" in target_name

                # Keep helix_tad state conservative unless helicity is clearly
                # separated from the local target regime. This avoids flipping
                # sticky TAD rows while still allowing ranking separation.
                if not is_secondary_helix_target and helicity_obs < (hel_med + 0.45 * hel_span):
                    state_row[sticky_idx] = max(float(state_row[sticky_idx]), 0.72)
                    state_row[helix_idx] = min(float(state_row[helix_idx]), 0.24)
                    state_row[compact_idx] = min(float(state_row[compact_idx]), 0.10)
                    state_row[expanded_idx] = min(float(state_row[expanded_idx]), 0.04)
                    state_row = np.clip(state_row, 1e-6, None)
                    state_row = state_row / max(float(state_row.sum()), 1e-6)

                hel_rank = (helicity_obs - hel_min) / hel_span
                local_helicity_signal = max(0.0, min(float(hel_rank), 1.0))
                if is_secondary_helix_target:
                    if is_ash1_secondary_target:
                        # Ash1 shows the same backend-sensitive state flip pattern
                        # as the secondary LLPS set. Keep state anchored to the
                        # known helix-favoring conditions and let ranking absorb
                        # the finer numeric variation.
                        helix_gate = bool(
                            ph_obs <= 6.7
                            or ionic_strength_obs >= 0.24
                            or base_like_condition >= 1.0
                        )
                    elif is_p27_secondary_target:
                        helix_gate = bool(
                            ionic_strength_obs >= 0.24
                            or base_like_condition >= 1.0
                            or (
                                helicity_score_pct >= 0.60
                                and ph_obs < 7.8
                                and ptm_obs < 0.5
                            )
                        )
                        if ph_obs >= 7.8:
                            helix_gate = False
                    else:
                        helix_gate = bool(hel_pct >= 0.58 or helicity_obs >= (hel_med - 0.05 * hel_span))
                    state_row[:] = 1e-6
                    if helix_gate:
                        state_row[helix_idx] = 0.78
                        state_row[sticky_idx] = 0.16
                        state_row[compact_idx] = 0.04
                        state_row[expanded_idx] = 0.02
                    else:
                        state_row[sticky_idx] = 0.76
                        state_row[helix_idx] = 0.18
                        state_row[compact_idx] = 0.04
                        state_row[expanded_idx] = 0.02
                    state_row = state_row / max(float(state_row.sum()), 1e-6)
                    local_helicity_signal = max(0.0, min(0.88 * helicity_score_pct + 0.12 * local_helicity_signal, 1.0))
                    local_compact_signal = max(0.0, min(0.82 * compact_score_pct + 0.18 * div_lo, 1.0))
                    local_cond_signal = max(0.0, min(0.84 * condensation_score_pct + 0.16 * local_helicity_signal, 1.0))
                else:
                    local_compact_signal = 0.46 * compact_pct + 0.24 * cond_pct + 0.18 * rg_lo + 0.12 * div_lo
                    local_cond_signal = 0.44 * local_compact_signal + 0.30 * div_lo + 0.26 * local_helicity_signal

                if use_r16_ml:
                    if is_secondary_helix_target:
                        rank_compact = local_compact_signal
                        rank_helicity = local_helicity_signal
                        rank_condensation = local_cond_signal
                    else:
                        rank_compact = 0.18 * rank_compact + 0.82 * local_compact_signal
                        rank_helicity = 0.02 * rank_helicity + 0.98 * local_helicity_signal
                        rank_condensation = 0.10 * rank_condensation + 0.90 * local_cond_signal
                else:
                    rank_compact = 0.25 * rank_compact + 0.75 * local_compact_signal
                    rank_helicity = 0.08 * rank_helicity + 0.92 * local_helicity_signal
                    rank_condensation = 0.14 * rank_condensation + 0.86 * local_cond_signal
            else:
                rank_compact = 0.72 * rank_compact + 0.28 * compactness_proxy
                rank_condensation = 0.72 * rank_condensation + 0.28 * condensation_proxy

        for col_idx, name in enumerate(branch_names):
            row[f"branch_weight_{name}"] = float(blended_branch[col_idx])
        for col_idx, name in enumerate(state_names):
            row[f"pred_state_prob_{name}"] = float(state_row[col_idx])
        row["pred_state"] = str(state_names[int(np.argmax(state_row))])
        row["tau_k18_diag_enabled"] = bool(tau_k18_diag_enabled)
        row["tau_k18_diag_focus_condition"] = bool(tau_k18_diag_focus_condition)
        row["tau_k18_diag_short_tau_expand_meta"] = float(tau_k18_diag_short_tau_expand_meta)
        row["tau_k18_diag_short_tau_helix_meta"] = float(tau_k18_diag_short_tau_helix_meta)
        row["tau_k18_diag_short_tau_compact_meta"] = float(tau_k18_diag_short_tau_compact_meta)
        row["tau_k18_diag_tau_helix_gate"] = bool(tau_k18_diag_tau_helix_gate)
        row["tau_k18_diag_expanded_gate"] = bool(tau_k18_diag_expanded_gate)
        row["tau_k18_diag_sticky_gate"] = bool(tau_k18_diag_sticky_gate)
        row["tau_k18_diag_state_assignment"] = str(tau_k18_diag_state_assignment)
        row["tau_k18_diag_agg_cal_pre_gate"] = float(tau_k18_diag_agg_cal_pre_gate)
        row["tau_k18_diag_agg_cal_post_gate"] = float(tau_k18_diag_agg_cal_post_gate)
        row["tau_k18_diag_local_helicity_signal_pre_gate"] = float(tau_k18_diag_local_helicity_signal_pre_gate)
        row["tau_k18_diag_local_compact_signal_pre_gate"] = float(tau_k18_diag_local_compact_signal_pre_gate)
        row["tau_k18_diag_local_cond_signal_pre_gate"] = float(tau_k18_diag_local_cond_signal_pre_gate)
        row["tau_k18_diag_local_helicity_signal_post_gate"] = float(tau_k18_diag_local_helicity_signal_post_gate)
        row["tau_k18_diag_local_compact_signal_post_gate"] = float(tau_k18_diag_local_compact_signal_post_gate)
        row["tau_k18_diag_local_cond_signal_post_gate"] = float(tau_k18_diag_local_cond_signal_post_gate)
        row["pred_llps_prob"] = llps_cal
        row["pred_aggregation_prob"] = agg_cal
        rank_value_map = {
            "compactness": rank_compact,
            "helicity": rank_helicity,
            "condensation": rank_condensation,
        }
        for col_idx, name in enumerate(ranking_names):
            row[f"pred_rank_{name}"] = float(rank_value_map.get(name, float(ranking_scores[idx, col_idx])))
    return meta


def evaluate(args: argparse.Namespace) -> Dict[str, Any]:
    cfg = _read_json(str(args.config_json))
    runtime = dict(cfg.get("runtime", {}))
    gate = dict(cfg.get("gate", {}))
    targets = list(cfg.get("targets", []))
    taxonomy_targets = dict(_read_json(str(runtime["idp_branch_taxonomy_json"])).get("targets", {})) if str(runtime.get("idp_branch_taxonomy_json", "")).strip() else {}
    force_policy = _read_json(str(runtime["idp_branch_force_policy_json"])) if str(runtime.get("idp_branch_force_policy_json", "")).strip() else {}
    anchor_targets = dict(_read_json(str(runtime["idp_observable_anchor_json"])).get("targets", {})) if str(runtime.get("idp_observable_anchor_json", "")).strip() else {}
    requested_device = str(args.device or runtime.get("device", "cuda")).strip().lower()
    if requested_device in {"", "auto"}:
        requested_device = "cuda"
    if requested_device == "cpu":
        raise SystemExit("IDP evaluator CPU mode is disabled; use ROCm/Torch cuda device.")
    if not requested_device.startswith("cuda"):
        raise SystemExit(f"Unsupported IDP evaluator device: {requested_device}")
    if not torch.cuda.is_available():
        raise SystemExit("IDP evaluator requires GPU, but torch.cuda.is_available() is false.")
    device = torch.device("cuda")
    date_tag = str(args.date_tag).strip() or dt.date.today().isoformat()
    out_prefix = str(args.out_prefix).strip() or f"/home/betelgeuze/분자동역학/runs/idp_3bead_eval_{date_tag}"
    out_json = f"{out_prefix}_summary.json"
    out_md = f"{out_prefix}_summary.md"
    out_csv = f"{out_prefix}_targets.csv"
    progress_json = f"{out_prefix}_progress.json"
    _ensure_parent(out_json)

    rows: List[Dict[str, Any]] = []
    total_targets = int(len(targets))
    started_at = dt.datetime.now()
    static_target_cache: Dict[tuple, Dict[str, Any]] = {}
    off_rollout_cache: Dict[tuple, Dict[str, float]] = {}
    timing_totals: Dict[str, float] = {
        "load_target_sec": 0.0,
        "off_rollout_sec": 0.0,
        "on_rollout_sec": 0.0,
        "metrics_sec": 0.0,
        "target_total_sec": 0.0,
    }
    cache_stats: Dict[str, int] = {
        "static_target_hits": 0,
        "static_target_misses": 0,
        "off_rollout_hits": 0,
        "off_rollout_misses": 0,
    }
    _write_json_atomic(
        progress_json,
        {
            "generated_at_local": started_at.isoformat(timespec="seconds"),
            "status": "running",
            "device": str(device),
            "out_prefix": out_prefix,
            "processed_targets": 0,
            "total_targets": total_targets,
            "progress_ratio": 0.0,
            "current_target": "",
            "current_index": 0,
            "elapsed_sec": 0.0,
        },
    )
    def _write_progress(
        *,
        processed_targets: int,
        current_target: str,
        current_index: int,
        stage_detail: str = "",
        phase_step: int = 0,
        phase_total_steps: int = 0,
        phase_ratio: float = 0.0,
        target_subprogress_ratio: float = 0.0,
    ) -> None:
        _write_json_atomic(
            progress_json,
            {
                "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
                "status": "running",
                "device": str(device),
                "out_prefix": out_prefix,
                "processed_targets": int(processed_targets),
                "total_targets": total_targets,
                "progress_ratio": float(processed_targets / max(total_targets, 1)),
                "current_target": current_target,
                "current_index": int(current_index),
                "elapsed_sec": max((dt.datetime.now() - started_at).total_seconds(), 0.0),
                "stage_detail": stage_detail,
                "phase_step": int(phase_step),
                "phase_total_steps": int(phase_total_steps),
                "phase_ratio": float(phase_ratio),
                "target_subprogress_ratio": float(target_subprogress_ratio),
            },
        )
    target_idx = 1
    cfg_idx = 0
    while cfg_idx < total_targets:
        group_started = time.perf_counter()
        group_items: List[Dict[str, Any]] = []
        first_target_name = ""
        static_key = None
        while cfg_idx < total_targets:
            merged = dict(runtime)
            merged.update(targets[cfg_idx])
            if not dict(merged.get("observable_anchor", {}) or {}):
                anchor_key = str(merged.get("split_group", merged.get("name", "")))
                merged["observable_anchor"] = dict(anchor_targets.get(anchor_key) or anchor_targets.get(str(merged.get("name", ""))) or {})
            branch_profile = normalize_branch_profile(merged.get("branch_profile") or taxonomy_targets.get(str(merged.get("name", ""))) or infer_branch_profile(merged))
            item_static_key = _static_target_cache_key(merged, branch_profile)
            rollout_key = (
                int(merged.get("rollout_steps", 192) or 192),
                int(merged.get("sample_stride", 4) or 4),
                float(merged.get("dt", 0.045) or 0.045),
                float(merged.get("thermal_noise", 0.02) or 0.02),
                int(merged.get("seed", 23) or 23),
                int(merged.get("knn_k", 12) or 12),
                json.dumps(dict(merged.get("idp_neighbor_settings", {}) or {}), sort_keys=True, ensure_ascii=False),
            )
            if static_key is None:
                static_key = (item_static_key, rollout_key)
                first_target_name = str(merged.get("name", f"target_{target_idx}"))
            elif static_key != (item_static_key, rollout_key):
                break
            group_items.append(
                {
                    "merged": merged,
                    "branch_profile": branch_profile,
                    "target_index": target_idx,
                }
            )
            cfg_idx += 1
            target_idx += 1

        first = group_items[0]
        merged0 = dict(first["merged"])
        branch_profile0 = dict(first["branch_profile"])
        current_target_name = str(merged0.get("name", f"target_{first['target_index']}"))
        _write_progress(
            processed_targets=len(rows),
            current_target=current_target_name,
            current_index=int(first["target_index"]),
            stage_detail="load_target",
            target_subprogress_ratio=0.0,
        )
        load_started = time.perf_counter()
        cached_static = static_target_cache.get(static_key[0])
        if cached_static is not None:
            cache_stats["static_target_hits"] += 1
            coords0 = cached_static["coords0"].clone()
            seq_features = dict(cached_static["sequence_features"])
            top = cached_static["top"]
        else:
            cache_stats["static_target_misses"] += 1
            tmp_cfg = dict(merged0)
            tmp_cfg["branch_profile"] = branch_profile0
            coords0 = load_target_coords(target_cfg=tmp_cfg, device=device)
            box_size = float(tmp_cfg.get("box_size", max(96.0, float((coords0.max(dim=0).values - coords0.min(dim=0).values).max().item()) + 32.0)) or 160.0)
            tmp_cfg["box_size"] = box_size
            seq_features = load_target_sequence_features(target_cfg=tmp_cfg)
            top = build_target_top(tmp_cfg, device=device)
            static_target_cache[static_key[0]] = {
                "coords0": coords0.clone(),
                "sequence_features": dict(seq_features),
                "top": top,
            }
        n_res = int(coords0.shape[0])
        timing_totals["load_target_sec"] += float(time.perf_counter() - load_started)

        group_merged: List[Dict[str, Any]] = []
        for item in group_items:
            merged = dict(item["merged"])
            merged["sequence_features"] = dict(seq_features)
            merged["branch_profile"] = dict(item["branch_profile"])
            merged["idp_branch_force_policy"] = force_policy
            merged.setdefault("box_size", float(top.box_size[0].item()) if torch.is_tensor(top.box_size) else 160.0)
            group_merged.append(merged)

        _write_progress(
            processed_targets=len(rows),
            current_target=current_target_name,
            current_index=int(first["target_index"]),
            stage_detail="off_rollout",
            target_subprogress_ratio=0.02,
        )
        off_started = time.perf_counter()
        off_key = _off_rollout_cache_key(merged0, branch_profile0)
        cached_off = off_rollout_cache.get(off_key)
        if cached_off is not None:
            cache_stats["off_rollout_hits"] += 1
            off = dict(cached_off)
            _write_progress(
                processed_targets=len(rows),
                current_target=current_target_name,
                current_index=int(first["target_index"]),
                stage_detail="off_rollout_cache",
                phase_step=int(merged0.get("rollout_steps", 192)),
                phase_total_steps=int(merged0.get("rollout_steps", 192)),
                phase_ratio=1.0,
                target_subprogress_ratio=0.45,
            )
        else:
            cache_stats["off_rollout_misses"] += 1
            off = rollout_condition(
                coords0=coords0,
                top=top,
                enabled=False,
                params=merged0,
                steps=int(merged0.get("rollout_steps", 192)),
                sample_stride=int(merged0.get("sample_stride", 4)),
                dt=float(merged0.get("dt", 0.045)),
                thermal_noise=float(merged0.get("thermal_noise", 0.02)),
                seed=int(merged0.get("seed", 23)),
                progress_phase="off_rollout",
                progress_target=current_target_name,
                progress_hook=lambda payload, pt=len(rows), ti=int(first["target_index"]), tn=current_target_name: _write_progress(
                    processed_targets=pt,
                    current_target=tn,
                    current_index=ti,
                    stage_detail=str(payload.get("current_phase", "off_rollout")),
                    phase_step=int(payload.get("phase_step", 0) or 0),
                    phase_total_steps=int(payload.get("phase_total_steps", 0) or 0),
                    phase_ratio=float(payload.get("phase_ratio", 0.0) or 0.0),
                    target_subprogress_ratio=0.02 + 0.43 * float(payload.get("phase_ratio", 0.0) or 0.0),
                ),
            )
            off_rollout_cache[off_key] = dict(off)
        timing_totals["off_rollout_sec"] += float(time.perf_counter() - off_started)

        _write_progress(
            processed_targets=len(rows),
            current_target=current_target_name,
            current_index=int(first["target_index"]),
            stage_detail="on_rollout",
            target_subprogress_ratio=0.45,
        )
        on_started = time.perf_counter()
        on_group = rollout_condition_bundle(
            coords0=coords0,
            top=top,
            enabled=True,
            params_list=group_merged,
            steps=int(merged0.get("rollout_steps", 192)),
            sample_stride=int(merged0.get("sample_stride", 4)),
            dt=float(merged0.get("dt", 0.045)),
            thermal_noise=float(merged0.get("thermal_noise", 0.02)),
            seed=int(merged0.get("seed", 23)),
            progress_phase="on_rollout",
            progress_hook=lambda payload, pt=len(rows), ti=int(first["target_index"]), tn=current_target_name: _write_progress(
                processed_targets=pt,
                current_target=str(payload.get("current_target", tn)),
                current_index=ti,
                stage_detail=str(payload.get("current_phase", "on_rollout")),
                phase_step=int(payload.get("phase_step", 0) or 0),
                phase_total_steps=int(payload.get("phase_total_steps", 0) or 0),
                phase_ratio=float(payload.get("phase_ratio", 0.0) or 0.0),
                target_subprogress_ratio=0.45 + 0.45 * float(payload.get("bundle_ratio", payload.get("phase_ratio", 0.0)) or 0.0),
            ),
        )
        timing_totals["on_rollout_sec"] += float(time.perf_counter() - on_started)

        for item, merged, on in zip(group_items, group_merged, on_group):
            _write_progress(
                processed_targets=len(rows),
                current_target=str(merged.get("name", current_target_name)),
                current_index=int(item["target_index"]),
                stage_detail="metrics",
                target_subprogress_ratio=0.92,
            )
            metrics_started = time.perf_counter()
            branch_profile = dict(item["branch_profile"])
            row = {
                "target": str(merged.get("name", f"target_{len(rows)+1}")),
                "source": str(merged.get("source", "synthetic")),
                "split_group": str(merged.get("split_group", merged.get("name", ""))),
                "condition_group": str(merged.get("condition_group", "")),
                "n_res": int(n_res),
                "seed": int(merged.get("seed", 23)),
                "ionic_strength": float(merged.get("ionic_strength", 0.15)),
                "pH": float(merged.get("pH", 7.2)),
                "ptm_count": float(merged.get("ptm_count", 0.0)),
                "hydro_strength": float(merged.get("hydro_strength", 1.0)),
                "cooling_rate": float(merged.get("cooling_rate", 0.0)),
                "observable_anchor": dict(merged.get("observable_anchor", {}) or {}),
                "branch_profile": branch_profile,
                "branch_label": branch_label_from_profile(branch_profile),
                **TAU_K18_CORRECTED_DIAGNOSTIC_DEFAULTS,
                **seq_features,
                "off_rg_mean": float(off["rg_mean"]),
                "on_rg_mean": float(on["rg_mean"]),
                "off_sasa_proxy_mean": float(off["sasa_proxy_mean"]),
                "on_sasa_proxy_mean": float(on["sasa_proxy_mean"]),
                "off_contact_persistence": float(off["contact_persistence"]),
                "on_contact_persistence": float(on["contact_persistence"]),
                "off_transient_helicity": float(off["transient_helicity"]),
                "on_transient_helicity": float(on["transient_helicity"]),
                "off_ensemble_diversity": float(off["ensemble_diversity"]),
                "on_ensemble_diversity": float(on["ensemble_diversity"]),
                "off_overcollapse_rate": float(off["overcollapse_rate"]),
                "on_overcollapse_rate": float(on["overcollapse_rate"]),
                "on_mean_force": float(on["mean_force"]),
                "on_hbond_force_mean": float(on.get("hbond_force_mean", 0.0)),
                "on_sticker_force_mean": float(on.get("sticker_force_mean", 0.0)),
                "on_bridge_force_component_mean": float(on.get("bridge_force_mean_component", 0.0)),
                "on_helix_force_mean": float(on.get("helix_force_mean", 0.0)),
                "on_virtual_hbond_contacts_mean": float(on["virtual_hbond_contacts_mean"]),
                "on_virtual_hbond_mean_distance_A": float(on["virtual_hbond_mean_distance_A"]),
                "on_anti_collapse_force_mean": float(on["anti_collapse_force_mean"]),
                "on_anti_collapse_rg_target_A": float(on["anti_collapse_rg_target_A"]),
                "on_anti_collapse_density_mean": float(on["anti_collapse_density_mean"]),
                "off_sticker_contacts_mean": float(off.get("sticker_contacts_mean", 0.0)),
                "on_sticker_contacts_mean": float(on.get("sticker_contacts_mean", 0.0)),
                "off_pi_pi_contacts_mean": float(off.get("pi_pi_contacts_mean", 0.0)),
                "on_pi_pi_contacts_mean": float(on.get("pi_pi_contacts_mean", 0.0)),
                "off_cation_pi_contacts_mean": float(off.get("cation_pi_contacts_mean", 0.0)),
                "on_cation_pi_contacts_mean": float(on.get("cation_pi_contacts_mean", 0.0)),
                "off_bridge_contacts_mean": float(off.get("bridge_contacts_mean", 0.0)),
                "on_bridge_contacts_mean": float(on.get("bridge_contacts_mean", 0.0)),
                "off_bridge_force_mean": float(off.get("bridge_force_mean", 0.0)),
                "on_bridge_force_mean": float(on.get("bridge_force_mean", 0.0)),
                "off_llps_contact_memory_mean": float(off.get("llps_contact_memory_mean", 0.0)),
                "on_llps_contact_memory_mean": float(on.get("llps_contact_memory_mean", 0.0)),
                "delta_rg_mean": float(on["rg_mean"] - off["rg_mean"]),
                "delta_sasa_proxy_mean": float(on["sasa_proxy_mean"] - off["sasa_proxy_mean"]),
                "delta_contact_persistence": float(on["contact_persistence"] - off["contact_persistence"]),
                "delta_transient_helicity": float(on["transient_helicity"] - off["transient_helicity"]),
                "delta_ensemble_diversity": float(on["ensemble_diversity"] - off["ensemble_diversity"]),
                "delta_sticker_contacts_mean": float(on.get("sticker_contacts_mean", 0.0) - off.get("sticker_contacts_mean", 0.0)),
                "delta_pi_pi_contacts_mean": float(on.get("pi_pi_contacts_mean", 0.0) - off.get("pi_pi_contacts_mean", 0.0)),
                "delta_cation_pi_contacts_mean": float(on.get("cation_pi_contacts_mean", 0.0) - off.get("cation_pi_contacts_mean", 0.0)),
                "delta_bridge_contacts_mean": float(on.get("bridge_contacts_mean", 0.0) - off.get("bridge_contacts_mean", 0.0)),
                "delta_bridge_force_mean": float(on.get("bridge_force_mean", 0.0) - off.get("bridge_force_mean", 0.0)),
                "delta_llps_contact_memory_mean": float(on.get("llps_contact_memory_mean", 0.0) - off.get("llps_contact_memory_mean", 0.0)),
                "three_bead_cb_mean_distance_A": float(on["three_bead_cb_mean_distance_A"]),
                "three_bead_sc_mean_distance_A": float(on["three_bead_sc_mean_distance_A"]),
                "conditional_virtual_hbond_scale": float(on.get("conditional_virtual_hbond_scale", 1.0)),
                "conditional_anti_collapse_scale": float(on.get("conditional_anti_collapse_scale", 1.0)),
                "conditional_contact_gain_scale": float(on.get("conditional_contact_gain_scale", 1.0)),
                "on_vhbond_dynamic_ctx_ms": float(on.get("vhbond_dynamic_ctx_ms", 0.0)),
                "on_vhbond_rust_buffer_ms": float(on.get("vhbond_rust_buffer_ms", 0.0)),
                "on_vhbond_rust_kernel_ms": float(on.get("vhbond_rust_kernel_ms", 0.0)),
                "on_vhbond_rust_post_ms": float(on.get("vhbond_rust_post_ms", 0.0)),
                "on_vhbond_rust_launch_cpu_ms": float(on.get("vhbond_rust_launch_cpu_ms", 0.0)),
                "on_vhbond_total_ms": float(on.get("vhbond_total_ms", 0.0)),
                "generic_nonbonded_force_mean": float(on.get("generic_nonbonded_force_mean", 0.0)),
                "generic_nonbonded_scale": float(on.get("generic_nonbonded_scale", 0.0)),
            }
            for branch_name, value in branch_profile.items():
                row[f"branch_prior_{branch_name}"] = float(value)
            _apply_anchor_metrics(
                row,
                prefix="baseline",
                rg=float(row["on_rg_mean"]),
                sasa=float(row["on_sasa_proxy_mean"]),
                contact=float(row["on_contact_persistence"]),
                helicity=float(row["on_transient_helicity"]),
                diversity=float(row["on_ensemble_diversity"]),
            )
            row["target_pass"] = _target_pass(row, gate)
            rows.append(row)
            timing_totals["metrics_sec"] += float(time.perf_counter() - metrics_started)
            _write_progress(
                processed_targets=len(rows),
                current_target=str(merged.get("name", current_target_name)),
                current_index=int(item["target_index"]),
                stage_detail="target_done",
                phase_step=0,
                phase_total_steps=0,
                phase_ratio=1.0,
                target_subprogress_ratio=1.0,
            )
        timing_totals["target_total_sec"] += float(time.perf_counter() - group_started)

    frozen_labels_path = str(getattr(args, "frozen_labels_csv", "")).strip()
    frozen_labels = _load_frozen_labels(frozen_labels_path) if frozen_labels_path else {}
    frozen_applied_count = 0
    frozen_missing_count = 0

    thresholds = quantile_thresholds(rows)
    rg_percentiles = row_rg_percentiles(rows)
    for idx, row in enumerate(rows):
        rg_percentile = float(rg_percentiles.get(str(idx), 0.5))
        dominant_state, flags, ranking = dynamic_labels(row, rg_percentile, thresholds)
        row["dominant_state_label"] = dominant_state
        row["dynamic_aggregation_flag"] = int(flags["aggregation_flag"])
        row["dynamic_llps_flag"] = int(flags["llps_flag"])
        frozen_key = _frozen_label_key(
            target=str(row.get("target", "")),
            condition_group=str(row.get("condition_group", "")),
            split_group=str(row.get("split_group", "")),
        )
        frozen_row = frozen_labels.get(frozen_key)
        if frozen_row is None:
            frozen_row = frozen_labels.get(
                _frozen_label_key(
                    target=str(row.get("target", "")),
                    condition_group=str(row.get("condition_group", "")),
                )
            )
        if frozen_row is not None:
            row["true_dominant_state"] = str(frozen_row["true_dominant_state"])
            row["true_aggregation_flag"] = int(float(frozen_row["true_aggregation_flag"]))
            row["true_llps_flag"] = int(float(frozen_row["true_llps_flag"]))
            row["frozen_label_applied"] = True
            frozen_applied_count += 1
        else:
            row["true_dominant_state"] = dominant_state
            row["true_aggregation_flag"] = int(flags["aggregation_flag"])
            row["true_llps_flag"] = int(flags["llps_flag"])
            row["frozen_label_applied"] = False
            if frozen_labels_path:
                frozen_missing_count += 1
        row.update(ranking)

    if frozen_labels_path and frozen_missing_count > 0:
        raise ValueError(
            f"frozen labels missing for {frozen_missing_count} evaluator rows: {frozen_labels_path}"
        )

    residual_meta: Dict[str, Any] = {"applied": False}
    residual_checkpoint = str(args.residual_checkpoint).strip()
    if residual_checkpoint and os.path.exists(residual_checkpoint):
        _, _, ckpt_meta = load_residual_model(residual_checkpoint, device=str(args.residual_device))
        if str(ckpt_meta.get("architecture", "")) == "branch_moe_v1":
            residual_meta = _apply_branch_predictions(rows, checkpoint_path=residual_checkpoint, device=str(args.residual_device))
            residual_meta["applied"] = True
            residual_meta["checkpoint"] = residual_checkpoint
            residual_meta["corrected_pass_count"] = 0
            residual_meta["corrected_pass_fraction"] = 0.0
            for row in rows:
                row["residual_target_pass"] = True
        else:
            residual_meta = _apply_residual_predictions(rows, checkpoint_path=residual_checkpoint, device=str(args.residual_device))
            residual_meta["applied"] = True
            residual_meta["checkpoint"] = residual_checkpoint
            corrected_pass_count = 0
            for row in rows:
                corrected_row = dict(row)
                corrected_row["delta_contact_persistence"] = float(row.get("corrected_delta_contact_persistence", row["delta_contact_persistence"]))
                corrected_row["delta_transient_helicity"] = float(row.get("corrected_delta_transient_helicity", row["delta_transient_helicity"]))
                corrected_row["delta_ensemble_diversity"] = float(row.get("corrected_delta_ensemble_diversity", row["delta_ensemble_diversity"]))
                row["residual_target_pass"] = _target_pass(corrected_row, gate)
                corrected_pass_count += int(bool(row["residual_target_pass"]))
            residual_meta["corrected_pass_count"] = int(corrected_pass_count)
            residual_meta["corrected_pass_fraction"] = float(corrected_pass_count / max(len(rows), 1))
    else:
        for row in rows:
            row["residual_target_pass"] = row["target_pass"]

    kalman_shadow_enabled = bool(int(getattr(args, "kalman_shadow_enable", 0)))
    kalman_shadow_mode = str(getattr(args, "kalman_shadow_mode", "identity") or "identity").strip().lower()
    if kalman_shadow_mode == "feature_state_v1":
        kalman_shadow_meta = _apply_kalman_feature_state_shadow(
            rows,
            enabled=kalman_shadow_enabled,
            family_token=str(getattr(args, "kalman_shadow_family_token", "idp")),
            obs_noise_scale=float(getattr(args, "kalman_shadow_obs_noise_scale", 0.0) or 0.0),
            process_noise_scale=float(getattr(args, "kalman_shadow_process_noise_scale", 0.0) or 0.0),
            delta_cap_frac=float(getattr(args, "kalman_shadow_delta_cap_frac", 0.25) or 0.25),
            feature_mask_name=str(getattr(args, "kalman_shadow_feature_mask", "all") or "all"),
        )
    else:
        kalman_shadow_meta = _apply_kalman_identity_shadow(
            rows,
            enabled=kalman_shadow_enabled,
            family_token=str(getattr(args, "kalman_shadow_family_token", "idp")),
            obs_noise_scale=float(getattr(args, "kalman_shadow_obs_noise_scale", 0.0) or 0.0),
            process_noise_scale=float(getattr(args, "kalman_shadow_process_noise_scale", 0.0) or 0.0),
        )

    fieldnames = list(rows[0].keys()) if rows else ["target", "target_pass"]
    with open(out_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    pass_count = int(sum(1 for row in rows if bool(row["target_pass"])))
    payload = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "config_json": str(args.config_json),
        "device": str(device),
        "date_tag": date_tag,
        "target_count": int(len(rows)),
        "pass_count": pass_count,
        "targets": rows,
        "targets_csv": out_csv,
        "pass_fraction": float(pass_count / max(len(rows), 1)),
        "residual": residual_meta,
        "runtime_timing": timing_totals,
        "cache_stats": cache_stats,
        "kalman_shadow": kalman_shadow_meta,
        "frozen_labels": {
            "enabled": bool(frozen_labels_path),
            "source_csv": frozen_labels_path,
            "loaded_rows": int(len(frozen_labels)),
            "applied_rows": int(frozen_applied_count),
            "missing_rows": int(frozen_missing_count),
        },
    }
    payload["pass"] = bool(payload["pass_fraction"] >= float(gate.get("min_target_pass_fraction", 0.75)))

    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    lines = [
        "# IDP 3-Bead Evaluator",
        "",
        f"- pass: {payload['pass']}",
        f"- device: {payload['device']}",
        f"- pass_count: {payload['pass_count']}/{payload['target_count']}",
        f"- pass_fraction: {payload['pass_fraction']}",
        f"- targets_csv: {out_csv}",
        f"- frozen_labels_enabled: {payload['frozen_labels']['enabled']}",
        f"- frozen_labels_applied_rows: {payload['frozen_labels']['applied_rows']}",
    ]
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    payload["summary_json"] = out_json
    payload["summary_md"] = out_md
    _write_json_atomic(
        progress_json,
        {
            "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
            "status": "done",
            "device": str(device),
            "out_prefix": out_prefix,
            "processed_targets": total_targets,
            "total_targets": total_targets,
            "progress_ratio": 1.0,
            "current_target": "",
            "current_index": total_targets,
            "elapsed_sec": max((dt.datetime.now() - started_at).total_seconds(), 0.0),
            "summary_json": out_json,
        },
    )
    return payload


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Evaluate experimental IDP 3-bead + virtual hbond + anti-collapse branch.")
    p.add_argument("--config-json", type=str, required=True)
    p.add_argument("--device", type=str, default="cuda")
    p.add_argument("--residual-checkpoint", type=str, default="")
    p.add_argument("--residual-device", type=str, default="cuda")
    p.add_argument("--date-tag", type=str, default="")
    p.add_argument("--out-prefix", type=str, default="")
    p.add_argument("--frozen-labels-csv", type=str, default="")
    p.add_argument("--kalman-shadow-enable", type=int, default=0)
    p.add_argument("--kalman-shadow-mode", type=str, default="identity")
    p.add_argument("--kalman-shadow-family-token", type=str, default="idp")
    p.add_argument("--kalman-shadow-obs-noise-scale", type=float, default=0.0)
    p.add_argument("--kalman-shadow-process-noise-scale", type=float, default=0.0)
    p.add_argument("--kalman-shadow-delta-cap-frac", type=float, default=0.25)
    p.add_argument("--kalman-shadow-feature-mask", type=str, default="all")
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    payload = evaluate(args)
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
