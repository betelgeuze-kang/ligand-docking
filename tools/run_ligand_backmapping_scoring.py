#!/usr/bin/env python3

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import datetime as dt
import glob
import hashlib
import json
import math
import os
import re
import shlex
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

# Ensure repo-root imports work when running `python tools/...py` directly.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
import torch
import torch.nn as nn

from tools.native_target_registry import resolve_repo_native_entry
from tools.pdb_loader import load_native_structure

try:
    from rdkit import Chem  # type: ignore
except Exception:  # pragma: no cover
    Chem = None

ADRB2_BETA_BLOCKER_PHARMACOPHORE_SMARTS = "[a]-[OX2]-[CX4]-[CX4]([OX2H1])-[CX4]-[NX3]"
_ADRB2_BETA_BLOCKER_PHARMACOPHORE = (
    Chem.MolFromSmarts(ADRB2_BETA_BLOCKER_PHARMACOPHORE_SMARTS) if Chem is not None else None
)
GPCR_BASIC_AMINE_SMARTS = (
    "[NX3;H0,H1,H2;!$(NC=O);!$(NS=O);!$(N[S](=O)=O)]",
    "[NX4+]",
)
_GPCR_BASIC_AMINE_PATTERNS = (
    tuple(Chem.MolFromSmarts(s) for s in GPCR_BASIC_AMINE_SMARTS) if Chem is not None else tuple()
)


class _AuxMLP(nn.Module):
    def __init__(self, in_dim: int, hidden_dim: int = 64):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(in_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x).squeeze(-1)


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _read_json_if_exists(path: str) -> Dict[str, Any]:
    src = str(path or "").strip()
    if (not src) or (not os.path.exists(src)):
        return {}
    try:
        with open(src, "r", encoding="utf-8") as f:
            obj = json.load(f)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _safe_float(value: Any, default: float) -> float:
    try:
        if value is None or value == "":
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _safe_optional_float(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        out = float(value)
        return float(out) if np.isfinite(out) else None
    except (TypeError, ValueError):
        return None


def _adrb2_beta_blocker_pharmacophore_match(smiles: Any) -> bool:
    if Chem is None or _ADRB2_BETA_BLOCKER_PHARMACOPHORE is None:
        return False
    src = str(smiles or "").strip()
    if not src:
        return False
    mol = Chem.MolFromSmiles(src)
    return bool(mol is not None and mol.HasSubstructMatch(_ADRB2_BETA_BLOCKER_PHARMACOPHORE))


def _gpcr_basic_amine_proxy(smiles: Any) -> float:
    src = str(smiles or "").strip()
    if not src:
        return 0.0
    if Chem is None or not _GPCR_BASIC_AMINE_PATTERNS:
        return 1.0 if re.search(r"(N|\[NH[0-9+]?\]|\[N[H+]?\+?\])", src) else 0.0
    mol = Chem.MolFromSmiles(src)
    if mol is None:
        return 0.0
    return 1.0 if any(p is not None and mol.HasSubstructMatch(p) for p in _GPCR_BASIC_AMINE_PATTERNS) else 0.0


def _safe_optional_int(value: Any) -> Optional[int]:
    try:
        if value is None or value == "":
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _canonical_json_hash(payload: Dict[str, Any]) -> str:
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load_score_reference_scaling(*, mode: str, stats_json: str) -> Dict[str, Any]:
    requested_mode = str(mode or "run_local").strip().lower()
    stats_path = str(stats_json or "").strip()
    payload = _read_json_if_exists(stats_path) if stats_path else {}
    features = payload.get("features") if isinstance(payload.get("features"), dict) else {}
    if not features and isinstance(payload.get("columns"), dict):
        features = payload.get("columns", {})
    status = "run_local"
    if requested_mode in {"fixed_family_reference", "reference", "frozen"}:
        status = "loaded" if features else "missing_stats_fallback_run_local"
    return {
        "mode": requested_mode,
        "stats_json": stats_path,
        "status": status,
        "schema_version": str(payload.get("schema_version", "") or ""),
        "reference_scope": payload.get("reference_scope", {}) if isinstance(payload.get("reference_scope"), dict) else {},
        "stats_hash": _canonical_json_hash(payload) if payload else "",
        "features": features if isinstance(features, dict) else {},
        "applied_columns": [],
        "missing_columns": [],
        "fallback_columns": [],
        "invalid_columns": [],
    }


def _append_unique(values: list[str], value: str) -> None:
    if value and value not in values:
        values.append(value)


def _run_local_zscore(series: pd.Series) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce")
    mu = float(s.mean()) if len(s) > 0 else 0.0
    sd = float(s.std()) if len(s) > 0 else 1.0
    if (not np.isfinite(sd)) or sd <= 1e-12:
        sd = 1.0
    return (s - mu) / sd


def _zscore_with_reference(result_df: pd.DataFrame, col: str, scaling: Dict[str, Any]) -> pd.Series:
    s = pd.to_numeric(result_df[col], errors="coerce")
    mode = str(scaling.get("mode", "run_local") or "run_local").strip().lower()
    features = scaling.get("features") if isinstance(scaling.get("features"), dict) else {}
    if mode not in {"fixed_family_reference", "reference", "frozen"}:
        return _run_local_zscore(s)

    stats = features.get(col) if isinstance(features, dict) else None
    if not isinstance(stats, dict):
        _append_unique(scaling["missing_columns"], col)
        _append_unique(scaling["fallback_columns"], col)
        return _run_local_zscore(s)

    mu = _safe_optional_float(stats.get("mean"))
    sd = _safe_optional_float(stats.get("std", stats.get("sd")))
    if mu is None or sd is None or sd <= 1e-12:
        _append_unique(scaling["invalid_columns"], col)
        _append_unique(scaling["fallback_columns"], col)
        return _run_local_zscore(s)
    _append_unique(scaling["applied_columns"], col)
    return (s - float(mu)) / float(sd)


def _nan_percentile(values: np.ndarray, q: float) -> Optional[float]:
    arr = np.asarray(values, dtype=np.float64)
    if arr.size <= 0:
        return None
    try:
        out = float(np.nanpercentile(arr, q))
    except Exception:
        return None
    return out if np.isfinite(out) else None


def _safe_sem(std_value: Any, count: int) -> Optional[float]:
    sd = _safe_optional_float(std_value)
    n = int(max(count, 0))
    if sd is None or n <= 0:
        return None
    return float(sd / math.sqrt(float(n)))


def _clip_pos(values: pd.Series) -> np.ndarray:
    return np.clip(pd.to_numeric(values, errors="coerce").to_numpy(dtype=float), 0.0, None)


def _has_usable_numeric_score(df: pd.DataFrame, col: str) -> bool:
    name = str(col or "").strip()
    if (not name) or (name not in df.columns):
        return False
    values = pd.to_numeric(df[name], errors="coerce")
    return bool(values.notna().any())


def _composite_score_sort_key(col: str) -> Tuple[int, int, str]:
    match = re.match(r"^binding_score_composite_v(\d+)(.*)$", str(col or ""))
    if not match:
        return (10**9, 10**9, str(col or ""))
    version = int(match.group(1))
    suffix = str(match.group(2) or "")
    suffix_rank = 3
    if suffix == "_residual_active":
        suffix_rank = 0
    elif suffix == "":
        suffix_rank = 1
    elif suffix == "_residual_shadow":
        suffix_rank = 2
    return (-version, suffix_rank, str(col))


def _resolve_ranking_columns(
    result_df: pd.DataFrame,
    residual_shadow_meta: Dict[str, Any],
) -> Dict[str, Any]:
    ranking_candidates: List[str] = []
    residual_meta = residual_shadow_meta if isinstance(residual_shadow_meta, dict) else {}
    residual_active_col = str(residual_meta.get("active_score_col", "") or "").strip()
    if _has_usable_numeric_score(result_df, residual_active_col):
        ranking_candidates.append(residual_active_col)

    composite_candidates = sorted(
        [
            str(col)
            for col in result_df.columns
            if str(col).startswith("binding_score_composite_") and _has_usable_numeric_score(result_df, str(col))
        ],
        key=_composite_score_sort_key,
    )
    for col in composite_candidates:
        if col not in ranking_candidates:
            ranking_candidates.append(col)

    for fallback_col in ["binding_energy_mmpbsa_kcal_mol_proxy", "stability_score"]:
        if _has_usable_numeric_score(result_df, fallback_col) and fallback_col not in ranking_candidates:
            ranking_candidates.append(fallback_col)

    ranking_score_col = (
        ranking_candidates[0]
        if ranking_candidates
        else "binding_energy_mmpbsa_kcal_mol_proxy"
    )
    active_score_col = (
        residual_active_col
        if _has_usable_numeric_score(result_df, residual_active_col)
        else ranking_score_col
    )
    sort_columns: List[str] = []
    ascending: List[bool] = []
    for col, asc in [
        (ranking_score_col, True),
        ("binding_energy_mmpbsa_kcal_mol_proxy", True),
        ("stability_score", False),
    ]:
        if _has_usable_numeric_score(result_df, col) and col not in sort_columns:
            sort_columns.append(col)
            ascending.append(asc)

    if not sort_columns:
        sort_columns = ["binding_energy_mmpbsa_kcal_mol_proxy", "stability_score"]
        ascending = [True, False]

    return {
        "active_score_col": active_score_col,
        "ranking_score_col_used": ranking_score_col,
        "sort_columns": sort_columns,
        "ascending": ascending,
    }


def _residual_tuning(spec_payload: Dict[str, Any]) -> Dict[str, float | str]:
    proto = spec_payload.get("prototype", {}) if isinstance(spec_payload.get("prototype", {}), dict) else {}
    tuning = proto.get("tuning", {}) if isinstance(proto.get("tuning", {}), dict) else {}
    return {
        "variant": str(tuning.get("variant", "current") or "current"),
        "prior_weight_h_donors": _safe_float(tuning.get("prior_weight_h_donors"), 0.55),
        "prior_weight_h_acceptors": _safe_float(tuning.get("prior_weight_h_acceptors"), 0.45),
        "prior_weight_rot_bonds": _safe_float(tuning.get("prior_weight_rot_bonds"), 0.22),
        "prior_weight_neg_logp": _safe_float(tuning.get("prior_weight_neg_logp"), 0.18),
        "weakness_weight_distance": _safe_float(tuning.get("weakness_weight_distance"), 0.55),
        "weakness_weight_neg_contact": _safe_float(tuning.get("weakness_weight_neg_contact"), 0.40),
        "weakness_weight_neg_stability": _safe_float(tuning.get("weakness_weight_neg_stability"), 0.20),
        "weakness_weight_energy": _safe_float(tuning.get("weakness_weight_energy"), 0.20),
        "support_weight_neg_energy": _safe_float(tuning.get("support_weight_neg_energy"), 0.35),
        "support_weight_contact": _safe_float(tuning.get("support_weight_contact"), 0.25),
        "support_weight_stability": _safe_float(tuning.get("support_weight_stability"), 0.15),
        "support_weight_neg_distance": _safe_float(tuning.get("support_weight_neg_distance"), 0.25),
        "interaction_bias": _safe_float(tuning.get("interaction_bias"), 0.35),
        "affinity_mismatch_weight": _safe_float(tuning.get("affinity_mismatch_weight"), 0.30),
        "affinity_interaction_bias": _safe_float(tuning.get("affinity_interaction_bias"), 0.35),
        "support_penalty_weight": _safe_float(tuning.get("support_penalty_weight"), 0.20),
        "min_prior_pressure_for_delta": _safe_float(tuning.get("min_prior_pressure_for_delta"), 0.0),
        "min_structural_weakness_for_delta": _safe_float(tuning.get("min_structural_weakness_for_delta"), 0.0),
        "max_structural_support_for_delta": _safe_float(tuning.get("max_structural_support_for_delta"), 1.0e9),
        "min_raw_delta_for_activation": _safe_float(tuning.get("min_raw_delta_for_activation"), 0.0),
        "require_distance_above_z": _safe_float(tuning.get("require_distance_above_z"), -1.0e9),
        "require_contact_below_z": _safe_float(tuning.get("require_contact_below_z"), 1.0e9),
        "intrusion_weight_low_h_donors": _safe_float(tuning.get("intrusion_weight_low_h_donors"), 0.0),
        "intrusion_weight_low_h_acceptors": _safe_float(tuning.get("intrusion_weight_low_h_acceptors"), 0.0),
        "intrusion_weight_low_rot_bonds": _safe_float(tuning.get("intrusion_weight_low_rot_bonds"), 0.0),
        "intrusion_weight_high_logp": _safe_float(tuning.get("intrusion_weight_high_logp"), 0.0),
        "intrusion_weight_low_affinity": _safe_float(tuning.get("intrusion_weight_low_affinity"), 0.0),
        "intrusion_weight_contact": _safe_float(tuning.get("intrusion_weight_contact"), 0.0),
        "intrusion_weight_stability": _safe_float(tuning.get("intrusion_weight_stability"), 0.0),
        "intrusion_weight_neg_energy": _safe_float(tuning.get("intrusion_weight_neg_energy"), 0.0),
        "intrusion_weight_neg_distance": _safe_float(tuning.get("intrusion_weight_neg_distance"), 0.0),
        "intrusion_contact_bias": _safe_float(tuning.get("intrusion_contact_bias"), 0.0),
        "min_intrusion_prior_pressure_for_delta": _safe_float(
            tuning.get("min_intrusion_prior_pressure_for_delta"), 0.0
        ),
        "min_intrusion_contact_support_for_delta": _safe_float(
            tuning.get("min_intrusion_contact_support_for_delta"), 0.0
        ),
        "min_intrusion_raw_delta_for_activation": _safe_float(
            tuning.get("min_intrusion_raw_delta_for_activation"), 0.0
        ),
        "max_intrusion_affinity_z": _safe_float(tuning.get("max_intrusion_affinity_z"), 1.0e9),
        "require_intrusion_contact_above_z": _safe_float(
            tuning.get("require_intrusion_contact_above_z"), -1.0e9
        ),
        "require_intrusion_distance_below_z": _safe_float(
            tuning.get("require_intrusion_distance_below_z"), 1.0e9
        ),
        "affinity_md_support_mismatch_weight": _safe_float(
            tuning.get("affinity_md_support_mismatch_weight"), 0.0
        ),
        "min_contact_mismatch_z_for_delta": _safe_float(
            tuning.get("min_contact_mismatch_z_for_delta"), 0.0
        ),
        "max_md_support_for_affinity_hint_delta": _safe_float(
            tuning.get("max_md_support_for_affinity_hint_delta"), 1.0e9
        ),
        "pharmacophore_reward_score": _safe_float(tuning.get("pharmacophore_reward_score"), 0.0),
    }


def _apply_residual_prototype_shadow(
    result_df: pd.DataFrame,
    args: argparse.Namespace,
    *,
    z_e: pd.Series,
    z_d: pd.Series,
    z_s: pd.Series,
    z_c: pd.Series,
    z_aff: pd.Series,
    z_logp: pd.Series,
    z_rot: pd.Series,
    z_hd: pd.Series,
    z_ha: pd.Series,
    z_std: pd.Series | None = None,
) -> tuple[pd.DataFrame, Dict[str, Any]]:
    enabled = bool(getattr(args, "residual_prototype_enabled", False))
    mode = str(getattr(args, "residual_prototype_mode", "shadow_only") or "shadow_only").strip().lower()
    family = str(getattr(args, "residual_prototype_family", "") or "").strip().lower()
    spec_json = str(getattr(args, "residual_prototype_spec_json", "") or "").strip()
    runtime_hook_ready = bool(getattr(args, "residual_prototype_runtime_hook_ready", False))
    score_reference_scaling_mode = str(
        getattr(args, "score_reference_scaling_mode", "run_local") or "run_local"
    ).strip().lower()
    spec_payload = _read_json_if_exists(spec_json)
    constraints = (
        spec_payload.get("prototype", {}).get("constraints", {})
        if isinstance(spec_payload.get("prototype", {}), dict)
        else {}
    )
    max_abs_delta = _safe_float(
        getattr(args, "residual_prototype_max_abs_delta_score", None),
        _safe_float(constraints.get("max_abs_delta_score"), 1.5),
    )
    yellow_band = _safe_float(
        getattr(args, "residual_prototype_yellow_band_abs_delta_score", None),
        _safe_float(constraints.get("yellow_band_abs_delta_score"), 0.75),
    )
    summary: Dict[str, Any] = {
        "enabled": bool(enabled),
        "mode": mode,
        "family": family,
        "spec_json": spec_json,
        "runtime_hook_ready": bool(runtime_hook_ready),
        "score_reference_scaling_mode": score_reference_scaling_mode,
        "active_score_col": "binding_score_composite_v7",
        "shadow_score_col": "",
        "positive_delta_count": 0,
        "yellow_band_count": 0,
        "mean_delta": 0.0,
        "max_delta": 0.0,
        "status": "disabled",
    }
    if (not enabled) or result_df.empty:
        return result_df, summary
    if family in {"ion_channel", "kinase"} and mode == "shadow_only":
        base_score = pd.to_numeric(result_df["binding_score_composite_v7"], errors="coerce")
        zero_delta = np.zeros(len(result_df), dtype=float)
        result_df["residual_shadow_prior_pressure"] = zero_delta
        result_df["residual_shadow_structure_weakness"] = zero_delta
        result_df["residual_shadow_structure_support"] = zero_delta
        result_df["residual_shadow_delta_raw"] = zero_delta
        result_df["residual_shadow_delta"] = zero_delta
        result_df["residual_shadow_band"] = np.full(len(result_df), "none", dtype=object)
        result_df["binding_score_composite_v7_residual_shadow"] = base_score
        result_df["binding_score_composite_v7_residual_active"] = base_score
        result_df["residual_shadow_family"] = family
        result_df["residual_shadow_mode"] = mode
        result_df["residual_shadow_runtime_hook_ready"] = bool(runtime_hook_ready)
        summary.update(
            {
                "active_score_col": "binding_score_composite_v7",
                "shadow_score_col": "binding_score_composite_v7_residual_shadow",
                "positive_delta_count": 0,
                "gated_positive_delta_count": 0,
                "yellow_band_count": 0,
                "mean_delta": 0.0,
                "max_delta": 0.0,
                "status": "shadow_ready_noop_family",
                "top_shadow": [],
                "max_abs_delta_score": float(max_abs_delta),
                "yellow_band_abs_delta_score": float(yellow_band),
                "tuning_variant": "family_noop_shadow",
                "min_prior_pressure_for_delta": 0.0,
                "min_structural_weakness_for_delta": 0.0,
                "max_structural_support_for_delta": 0.0,
                "min_raw_delta_for_activation": 0.0,
            }
        )
        return result_df, summary
    if family != "gpcr":
        summary["status"] = "unsupported_family"
        return result_df, summary

    tuning = _residual_tuning(spec_payload)
    if z_std is None:
        z_std = pd.Series(np.zeros(len(result_df)), index=result_df.index, dtype=float)
    prior_pressure = (
        float(tuning["prior_weight_h_donors"]) * _clip_pos(z_hd)
        + float(tuning["prior_weight_h_acceptors"]) * _clip_pos(z_ha)
        + float(tuning["prior_weight_rot_bonds"]) * _clip_pos(z_rot)
        + float(tuning["prior_weight_neg_logp"]) * _clip_pos(-z_logp)
    )
    structural_weakness = (
        float(tuning["weakness_weight_distance"]) * _clip_pos(z_d)
        + float(tuning["weakness_weight_neg_contact"]) * _clip_pos(-z_c)
        + float(tuning["weakness_weight_neg_stability"]) * _clip_pos(-z_s)
        + float(tuning["weakness_weight_energy"]) * _clip_pos(z_e)
    )
    structural_support = (
        float(tuning["support_weight_neg_energy"]) * _clip_pos(-z_e)
        + float(tuning["support_weight_contact"]) * _clip_pos(z_c)
        + float(tuning["support_weight_stability"]) * _clip_pos(z_s)
        + float(tuning["support_weight_neg_distance"]) * _clip_pos(-z_d)
    )
    affinity_mismatch = float(tuning["affinity_mismatch_weight"]) * _clip_pos(z_aff) * (
        float(tuning["affinity_interaction_bias"]) + structural_weakness
    )
    base_raw_delta = (
        prior_pressure * (float(tuning["interaction_bias"]) + structural_weakness)
        + affinity_mismatch
        - float(tuning["support_penalty_weight"]) * structural_support
    )
    base_raw_delta = np.clip(base_raw_delta, 0.0, None)
    base_activation_mask = (
        (prior_pressure >= float(tuning["min_prior_pressure_for_delta"]))
        & (structural_weakness >= float(tuning["min_structural_weakness_for_delta"]))
        & (structural_support <= float(tuning["max_structural_support_for_delta"]))
        & (pd.to_numeric(z_d, errors="coerce").to_numpy(dtype=float) >= float(tuning["require_distance_above_z"]))
        & (pd.to_numeric(z_c, errors="coerce").to_numpy(dtype=float) <= float(tuning["require_contact_below_z"]))
        & (base_raw_delta >= float(tuning["min_raw_delta_for_activation"]))
    )
    if str(tuning["variant"]) == "gpcr_core_mismatch_contact_rescore_v1":
        base_activation_mask = np.zeros(len(result_df), dtype=bool)
    intrusion_pressure = np.zeros(len(result_df), dtype=float)
    intrusion_contact_support = np.zeros(len(result_df), dtype=float)
    intrusion_raw_delta = np.zeros(len(result_df), dtype=float)
    intrusion_activation_mask = np.zeros(len(result_df), dtype=bool)
    contact_mismatch = np.zeros(len(result_df), dtype=float)
    affinity_md_support = np.zeros(len(result_df), dtype=float)
    affinity_md_support_mismatch = np.zeros(len(result_df), dtype=float)
    mismatch_contact_raw_delta = np.zeros(len(result_df), dtype=float)
    mismatch_contact_activation_mask = np.zeros(len(result_df), dtype=bool)
    if str(tuning["variant"]) in {"gpcr_core_decoy_intrusion_v1", "core_decoy_intrusion_v1"}:
        intrusion_pressure = (
            float(tuning["intrusion_weight_low_h_donors"]) * _clip_pos(-z_hd)
            + float(tuning["intrusion_weight_low_h_acceptors"]) * _clip_pos(-z_ha)
            + float(tuning["intrusion_weight_low_rot_bonds"]) * _clip_pos(-z_rot)
            + float(tuning["intrusion_weight_high_logp"]) * _clip_pos(z_logp)
            + float(tuning["intrusion_weight_low_affinity"]) * _clip_pos(-z_aff)
        )
        intrusion_contact_support = (
            float(tuning["intrusion_weight_contact"]) * _clip_pos(z_c)
            + float(tuning["intrusion_weight_stability"]) * _clip_pos(z_s)
            + float(tuning["intrusion_weight_neg_energy"]) * _clip_pos(-z_e)
            + float(tuning["intrusion_weight_neg_distance"]) * _clip_pos(-z_d)
        )
        intrusion_raw_delta = np.clip(
            intrusion_pressure * (float(tuning["intrusion_contact_bias"]) + intrusion_contact_support),
            0.0,
            None,
        )
        intrusion_activation_mask = (
            (intrusion_pressure >= float(tuning["min_intrusion_prior_pressure_for_delta"]))
            & (intrusion_contact_support >= float(tuning["min_intrusion_contact_support_for_delta"]))
            & (intrusion_raw_delta >= float(tuning["min_intrusion_raw_delta_for_activation"]))
            & (pd.to_numeric(z_aff, errors="coerce").to_numpy(dtype=float) <= float(tuning["max_intrusion_affinity_z"]))
            & (
                pd.to_numeric(z_c, errors="coerce").to_numpy(dtype=float)
                >= float(tuning["require_intrusion_contact_above_z"])
            )
            & (
                pd.to_numeric(z_d, errors="coerce").to_numpy(dtype=float)
                <= float(tuning["require_intrusion_distance_below_z"])
            )
        )
    if str(tuning["variant"]) == "gpcr_core_mismatch_contact_rescore_v1":
        z_aff_arr = pd.to_numeric(z_aff, errors="coerce").to_numpy(dtype=float)
        contact_mismatch = (
            float(tuning["weakness_weight_neg_contact"]) * _clip_pos(-z_c)
            + float(tuning["weakness_weight_distance"]) * _clip_pos(z_d)
        )
        affinity_md_support = (
            float(tuning["support_weight_contact"]) * _clip_pos(z_c)
            + float(tuning["support_weight_stability"]) * _clip_pos(z_s)
            + float(tuning["support_weight_neg_energy"]) * _clip_pos(-z_e)
        )
        affinity_prior_pressure = float(tuning["affinity_md_support_mismatch_weight"]) * _clip_pos(z_aff)
        affinity_md_support_mismatch = _clip_pos(z_aff) * np.clip(
            float(tuning["max_md_support_for_affinity_hint_delta"]) - affinity_md_support,
            0.0,
            None,
        )
        mismatch_prior_pressure = prior_pressure + affinity_prior_pressure
        mismatch_contact_raw_delta = np.clip(
            mismatch_prior_pressure * (contact_mismatch + affinity_md_support_mismatch),
            0.0,
            None,
        )
        mismatch_contact_activation_mask = (
            (mismatch_prior_pressure >= float(tuning["min_prior_pressure_for_delta"]))
            & (contact_mismatch >= float(tuning["min_contact_mismatch_z_for_delta"]))
            & (affinity_md_support <= float(tuning["max_md_support_for_affinity_hint_delta"]))
            & (z_aff_arr > 0.0)
            & (mismatch_contact_raw_delta >= float(tuning["min_raw_delta_for_activation"]))
        )
    base_delta_candidate = np.where(base_activation_mask, base_raw_delta, 0.0)
    intrusion_delta_candidate = np.where(intrusion_activation_mask, intrusion_raw_delta, 0.0)
    mismatch_contact_delta_candidate = np.where(
        mismatch_contact_activation_mask,
        mismatch_contact_raw_delta,
        0.0,
    )
    raw_delta = np.maximum(np.maximum(base_delta_candidate, intrusion_delta_candidate), mismatch_contact_delta_candidate)
    activation_mask = raw_delta > 0.0
    delta = np.where(
        activation_mask,
        np.clip(raw_delta, 0.0, max(0.0, float(max_abs_delta))),
        0.0,
    )
    band = np.where(delta >= float(yellow_band), "yellow", np.where(delta > 0.0, "green", "none"))

    base_score = pd.to_numeric(result_df["binding_score_composite_v7"], errors="coerce")
    prior_active_score = (
        pd.to_numeric(result_df["binding_score_composite_v7_residual_active"], errors="coerce")
        if "binding_score_composite_v7_residual_active" in result_df.columns
        else base_score.copy()
    )
    prior_active_score = prior_active_score.fillna(base_score)
    shadow_score = base_score + delta
    pharmacophore_matches = np.zeros(len(result_df), dtype=np.int64)
    pharmacophore_reward = np.zeros(len(result_df), dtype=float)
    linear_rescore = (
        spec_payload.get("prototype", {}).get("linear_rescore", {})
        if isinstance(spec_payload.get("prototype", {}), dict)
        else {}
    )
    linear_rescore_enabled = bool(linear_rescore.get("enabled", False)) if isinstance(linear_rescore, dict) else False
    linear_rescore_status = "disabled"
    linear_rescore_term_count = 0
    if linear_rescore_enabled:
        terms = linear_rescore.get("terms", []) if isinstance(linear_rescore.get("terms", []), list) else []
        combine_mode = str(linear_rescore.get("combine_mode", "replace") or "replace").strip().lower()
        linear_score = np.full(len(result_df), _safe_float(linear_rescore.get("intercept"), 0.0), dtype=float)
        ligand_mw_series = pd.to_numeric(
            result_df["ligand_mw"] if "ligand_mw" in result_df.columns else pd.Series(np.zeros(len(result_df))),
            errors="coerce",
        ).fillna(0.0)
        ligand_mw_std = float(ligand_mw_series.std()) if len(ligand_mw_series) else 1.0
        if (not np.isfinite(ligand_mw_std)) or ligand_mw_std <= 1.0e-12:
            ligand_mw_std = 1.0
        z_ligand_mw = ((ligand_mw_series - float(ligand_mw_series.mean())) / ligand_mw_std).to_numpy(dtype=float)
        ligand_onsps_series = pd.to_numeric(
            result_df["ligand_onsps_norm"] if "ligand_onsps_norm" in result_df.columns else pd.Series(np.zeros(len(result_df))),
            errors="coerce",
        ).fillna(0.0)
        ligand_onsps_std = float(ligand_onsps_series.std()) if len(ligand_onsps_series) else 1.0
        if (not np.isfinite(ligand_onsps_std)) or ligand_onsps_std <= 1.0e-12:
            ligand_onsps_std = 1.0
        z_ligand_onsps = (
            (ligand_onsps_series - float(ligand_onsps_series.mean())) / ligand_onsps_std
        ).to_numpy(dtype=float)
        smiles_series = (
            result_df["ligand_smiles"]
            if "ligand_smiles" in result_df.columns
            else result_df["smiles"]
            if "smiles" in result_df.columns
            else pd.Series([""] * len(result_df), index=result_df.index)
        )
        gpcr_smiles_present_proxy = smiles_series.astype(str).str.strip().ne("").astype(float).to_numpy(dtype=float)
        gpcr_basic_amine_proxy = smiles_series.apply(_gpcr_basic_amine_proxy).astype(float).to_numpy(dtype=float)
        family_balanced_pose_energy_support = (
            _clip_pos(-z_e)
            + _clip_pos(z_c)
            + _clip_pos(z_s)
            + _clip_pos(-z_d)
        )
        # Shared GPCR anchor proxy only uses target-agnostic pose/physics and ligand-property signals.
        # It is a proxy for conserved aminergic-GPCR anchor behavior until atom-level motif checks are available.
        pose_physics_support = (
            _clip_pos(-z_e)
            + 0.75 * _clip_pos(z_c)
            + 0.50 * _clip_pos(z_s)
            + 0.50 * _clip_pos(-z_d)
        )
        anchor_chemistry_support = 1.0 + 0.25 * _clip_pos(z_hd) + 0.10 * _clip_pos(z_ha)
        gpcr_conserved_anchor_proxy = np.clip(
            pose_physics_support * anchor_chemistry_support - 0.50 * _clip_pos(z_d),
            0.0,
            None,
        )
        ligand_prior_pressure_v2 = (
            _clip_pos(z_aff)
            + 0.50 * _clip_pos(z_logp)
            + 0.40 * _clip_pos(z_rot)
            + 0.25 * _clip_pos(z_ha)
        )
        prior_overreward_without_anchor = np.clip(
            ligand_prior_pressure_v2 - gpcr_conserved_anchor_proxy,
            0.0,
            None,
        )
        target_internal_pairwise_pressure = prior_overreward_without_anchor * (
            0.50 + _clip_pos(z_d) + _clip_pos(-z_c) + _clip_pos(z_e)
        )
        over_anchor_without_basic_amine = np.maximum(
            gpcr_smiles_present_proxy * gpcr_conserved_anchor_proxy * (1.0 - gpcr_basic_amine_proxy),
            0.0,
        )
        z_hd_arr = pd.to_numeric(z_hd, errors="coerce").to_numpy(dtype=float)
        z_ha_arr = pd.to_numeric(z_ha, errors="coerce").to_numpy(dtype=float)
        raw_h_donors = pd.to_numeric(
            result_df["ligand_h_donors"] if "ligand_h_donors" in result_df.columns else pd.Series(np.zeros(len(result_df))),
            errors="coerce",
        ).fillna(0.0).to_numpy(dtype=float)
        raw_h_acceptors = pd.to_numeric(
            result_df["ligand_h_acceptors"]
            if "ligand_h_acceptors" in result_df.columns
            else pd.Series(np.zeros(len(result_df))),
            errors="coerce",
        ).fillna(0.0).to_numpy(dtype=float)
        raw_rot_bonds = pd.to_numeric(
            result_df["ligand_rot_bonds"] if "ligand_rot_bonds" in result_df.columns else pd.Series(np.zeros(len(result_df))),
            errors="coerce",
        ).fillna(0.0).to_numpy(dtype=float)
        anchor_chemistry_gap = np.clip(-(z_hd_arr + z_ha_arr) / 2.0, 0.0, None)
        anchor_prior_context = 0.25 + _clip_pos(z_aff) + 0.50 * _clip_pos(z_logp) + 0.30 * _clip_pos(z_rot)
        gpcr_anchor_chemistry_mismatch_pressure = np.clip(
            gpcr_smiles_present_proxy
            * (1.0 - gpcr_basic_amine_proxy)
            * (
                gpcr_conserved_anchor_proxy * anchor_prior_context
                + 0.50 * pose_physics_support * anchor_chemistry_gap
            ),
            0.0,
            None,
        )
        hydrophobic_low_polar_intrusion = (
            gpcr_basic_amine_proxy
            * _clip_pos(z_logp)
            * anchor_chemistry_gap
        )
        gpcr_pose_chemistry_hard_decoy_pressure = np.clip(
            hydrophobic_low_polar_intrusion
            + 0.05 * over_anchor_without_basic_amine
            + 0.25 * gpcr_anchor_chemistry_mismatch_pressure,
            0.0,
            None,
        )
        acidic_anchor_overcontact_excess = np.clip(
            gpcr_conserved_anchor_proxy - (1.0 + 0.75 * gpcr_basic_amine_proxy),
            0.0,
            None,
        )
        gpcr_acidic_anchor_overcontact_prior_gate = np.clip(
            gpcr_smiles_present_proxy
            * (1.0 - gpcr_basic_amine_proxy)
            * acidic_anchor_overcontact_excess
            * (0.25 + prior_overreward_without_anchor)
            * (0.50 + _clip_pos(z_c) + _clip_pos(-z_d)),
            0.0,
            None,
        )
        fixed_reference_scaling_enabled = score_reference_scaling_mode == "fixed_family_reference"
        fixed_reference_pose_prior_support = np.clip(
            gpcr_conserved_anchor_proxy
            + pose_physics_support
            + gpcr_basic_amine_proxy
            - prior_overreward_without_anchor,
            0.0,
            None,
        )
        fixed_reference_prior_weakness_pressure = target_internal_pairwise_pressure
        fixed_reference_live_overreward_pressure = np.clip(
            float(fixed_reference_scaling_enabled)
            * (
                prior_overreward_without_anchor
                + gpcr_pose_chemistry_hard_decoy_pressure
                + 0.15 * fixed_reference_prior_weakness_pressure
                - 0.10 * fixed_reference_pose_prior_support
            ),
            0.0,
            None,
        )
        class_a_orthosteric_motif_support_proxy = np.clip(
            gpcr_basic_amine_proxy
            * (
                pose_physics_support
                + 0.50 * _clip_pos(-z_e)
                + 0.25 * _clip_pos(z_s)
                + 0.25 * _clip_pos(z_c)
            ),
            0.0,
            None,
        )
        class_a_invalid_overanchor_pressure = np.clip(
            gpcr_smiles_present_proxy
            * (1.0 - gpcr_basic_amine_proxy)
            * gpcr_conserved_anchor_proxy
            * (0.50 + _clip_pos(z_c) + _clip_pos(-z_d)),
            0.0,
            None,
        )
        class_a_prior_overreward_invalid_overanchor_pressure = np.clip(
            prior_overreward_without_anchor
            + class_a_invalid_overanchor_pressure
            - 0.35 * class_a_orthosteric_motif_support_proxy,
            0.0,
            None,
        )
        class_a_orthosteric_occupancy_proxy = np.clip(
            0.35 * _clip_pos(z_c)
            + 0.25 * _clip_pos(-z_d)
            + 0.25 * _clip_pos(-z_e)
            + 0.15 * _clip_pos(z_s),
            0.0,
            None,
        )
        class_a_pose_survival_support_proxy = np.clip(
            0.45 * pose_physics_support
            + 0.35 * _clip_pos(z_s)
            + 0.20 * _clip_pos(-z_e),
            0.0,
            None,
        )
        class_a_charge_complemented_anchor_geometry_proxy = np.clip(
            gpcr_smiles_present_proxy
            * gpcr_basic_amine_proxy
            * (
                0.50 * gpcr_conserved_anchor_proxy
                + 0.35 * class_a_orthosteric_occupancy_proxy
                + 0.15 * class_a_pose_survival_support_proxy
            ),
            0.0,
            None,
        )
        class_a_anchorless_prior_pressure_v7 = np.clip(
            gpcr_smiles_present_proxy
            * prior_overreward_without_anchor
            * (1.0 - np.clip(class_a_orthosteric_occupancy_proxy, 0.0, 1.0)),
            0.0,
            None,
        )
        class_a_invalid_anchor_prior_pressure_v7 = np.clip(
            class_a_anchorless_prior_pressure_v7
            + class_a_invalid_overanchor_pressure
            + 0.35 * gpcr_anchor_chemistry_mismatch_pressure
            - 0.30 * class_a_charge_complemented_anchor_geometry_proxy
            - 0.20 * class_a_pose_survival_support_proxy,
            0.0,
            None,
        )
        def _optional_numeric_column(name: str) -> np.ndarray:
            if name not in result_df.columns:
                return np.full(len(result_df), np.nan, dtype=float)
            return pd.to_numeric(result_df[name], errors="coerce").to_numpy(dtype=float)

        atom_available = np.nan_to_num(
            _optional_numeric_column("class_a_atom_anchor_available"),
            nan=0.0,
            posinf=0.0,
            neginf=0.0,
        )
        atom_available = np.clip(atom_available, 0.0, 1.0)
        atom_min_distance = _optional_numeric_column("class_a_atom_anchor_min_distance_A")
        atom_p10_distance = _optional_numeric_column("class_a_atom_anchor_p10_distance_A")
        atom_mean_distance = _optional_numeric_column("class_a_atom_anchor_mean_distance_A")
        atom_window_fraction = np.nan_to_num(
            _optional_numeric_column("class_a_atom_anchor_contact_fraction_2p8_4p2A"),
            nan=0.0,
            posinf=0.0,
            neginf=0.0,
        )
        atom_too_close_fraction = np.nan_to_num(
            _optional_numeric_column("class_a_atom_anchor_contact_fraction_le_2p8A"),
            nan=0.0,
            posinf=0.0,
            neginf=0.0,
        )
        p10_for_window = np.nan_to_num(atom_p10_distance, nan=999.0, posinf=999.0, neginf=-999.0)
        mean_for_window = np.nan_to_num(atom_mean_distance, nan=999.0, posinf=999.0, neginf=-999.0)
        min_for_overcontact = np.nan_to_num(atom_min_distance, nan=999.0, posinf=999.0, neginf=-999.0)
        atom_window_lower_support = np.clip((p10_for_window - 2.4) / 0.4, 0.0, 1.0)
        atom_window_upper_support = np.clip((4.8 - mean_for_window) / 0.6, 0.0, 1.0)
        class_a_atom_anchor_feature_available_proxy = atom_available
        class_a_direct_atom_window_core_proxy = np.clip(
            atom_available
            * (
                0.50 * np.clip(atom_window_fraction, 0.0, 1.0)
                + 0.25 * atom_window_lower_support
                + 0.25 * atom_window_upper_support
            ),
            0.0,
            None,
        )
        class_a_direct_atom_window_anchor_geometry_proxy = np.clip(
            gpcr_basic_amine_proxy
            * class_a_direct_atom_window_core_proxy
            * (0.50 + 0.50 * np.clip(class_a_pose_survival_support_proxy, 0.0, 1.0)),
            0.0,
            None,
        )
        class_a_atom_window_pose_survival_proxy = np.clip(
            atom_available
            * class_a_direct_atom_window_core_proxy
            * np.clip(class_a_pose_survival_support_proxy, 0.0, None),
            0.0,
            None,
        )
        atom_too_close_pressure = np.clip(
            atom_available
            * (
                np.clip(atom_too_close_fraction, 0.0, 1.0)
                + np.clip((2.8 - p10_for_window) / 0.8, 0.0, None)
                + 0.50 * np.clip((2.6 - min_for_overcontact) / 0.6, 0.0, None)
            ),
            0.0,
            None,
        )
        hydrophobic_overcontact_context = np.clip(
            _clip_pos(z_logp)
            + 0.25 * _clip_pos(-z_hd)
            + 0.25 * _clip_pos(-z_ha)
            + 0.15 * _clip_pos(z_c)
            + 0.15 * gpcr_anchor_chemistry_mismatch_pressure,
            0.0,
            None,
        )
        class_a_hydrophobic_overcontact_pressure_v8 = np.clip(
            gpcr_smiles_present_proxy
            * atom_too_close_pressure
            * hydrophobic_overcontact_context
            * (1.0 - 0.50 * np.clip(class_a_direct_atom_window_core_proxy, 0.0, 1.0)),
            0.0,
            None,
        )
        class_a_excess_polar_anchor_pressure_v9 = np.clip(
            atom_available
            * gpcr_smiles_present_proxy
            * gpcr_basic_amine_proxy
            * class_a_direct_atom_window_core_proxy
            * (
                np.clip((raw_h_donors - 2.5) / 2.0, 0.0, None)
                + 0.75 * np.clip((raw_h_acceptors - 4.5) / 2.0, 0.0, None)
                + 0.35 * np.clip((raw_rot_bonds - 5.5) / 3.0, 0.0, None)
            ),
            0.0,
            None,
        )
        class_a_compact_amine_window_support_v9 = np.clip(
            atom_available
            * gpcr_smiles_present_proxy
            * gpcr_basic_amine_proxy
            * class_a_direct_atom_window_core_proxy
            * (1.0 - np.clip((raw_h_donors - 2.5) / 3.0, 0.0, 1.0))
            * (1.0 - np.clip((raw_h_acceptors - 4.5) / 3.0, 0.0, 1.0))
            * (1.0 - np.clip((raw_rot_bonds - 5.5) / 4.0, 0.0, 1.0)),
            0.0,
            None,
        )
        cache_anchor_mode = (
            result_df["label_free_anchor_mode"]
            if "label_free_anchor_mode" in result_df.columns
            else pd.Series([""] * len(result_df), index=result_df.index)
        )
        cache_all_basic_anchor = (
            cache_anchor_mode.astype(str).str.strip().str.lower().eq("all_basic").astype(float).to_numpy(dtype=float)
        )
        cache_support_pressure = np.nan_to_num(
            _optional_numeric_column("label_free_support_pressure"),
            nan=0.0,
            posinf=0.0,
            neginf=0.0,
        )
        cache_weakbase_support_pressure = np.nan_to_num(
            _optional_numeric_column("weak_base_rescue_support_pressure"),
            nan=0.0,
            posinf=0.0,
            neginf=0.0,
        )
        cache_basic_amine_count = np.nan_to_num(
            _optional_numeric_column("basic_amine_count"),
            nan=0.0,
            posinf=0.0,
            neginf=0.0,
        )
        cache_pose_rmsd = np.nan_to_num(
            _optional_numeric_column("coarse_centroid_preservation_rmsd_A_mean"),
            nan=999.0,
            posinf=999.0,
            neginf=999.0,
        )
        gpcr_synthetic_anchor_saturation_pressure_v12 = np.clip(
            cache_all_basic_anchor
            * np.clip(cache_basic_amine_count, 0.0, 1.0)
            * np.clip((cache_support_pressure - 0.90) / 0.08, 0.0, 1.0),
            0.0,
            None,
        )
        gpcr_plausible_anchor_window_support_v12 = np.clip(
            np.clip((cache_support_pressure - 0.35) / 0.25, 0.0, 1.0)
            * np.clip((0.86 - cache_support_pressure) / 0.20, 0.0, 1.0),
            0.0,
            1.0,
        )
        gpcr_moderate_multi_basic_weakbase_support_v12 = np.clip(
            cache_weakbase_support_pressure
            * gpcr_plausible_anchor_window_support_v12
            * np.clip((cache_basic_amine_count - 1.0) / 1.0, 0.0, 1.0)
            * np.clip((1.35 - cache_pose_rmsd) / 0.60, 0.0, 1.0),
            0.0,
            None,
        )
        gpcr_pose_support_signal_v13 = np.maximum.reduce(
            [
                np.clip(cache_support_pressure, 0.0, 1.0),
                np.clip(cache_weakbase_support_pressure, 0.0, 1.0),
                np.clip(gpcr_moderate_multi_basic_weakbase_support_v12, 0.0, 1.0),
            ]
        )
        gpcr_no_pose_support_gate_v13 = np.clip((0.30 - gpcr_pose_support_signal_v13) / 0.30, 0.0, 1.0)
        gpcr_strong_base_without_support_gate_v13 = np.clip(
            (-6.0 - base_score.to_numpy(dtype=float)) / 2.0,
            0.0,
            None,
        )
        cache_pose_preservation_support = np.nan_to_num(
            _optional_numeric_column("pose_preservation_support"),
            nan=0.0,
            posinf=1.0,
            neginf=0.0,
        )
        gpcr_pose_gap_gate_v13 = np.clip(
            (0.50 - np.clip(cache_pose_preservation_support, 0.0, 1.0)) / 0.50,
            0.0,
            1.0,
        )
        gpcr_unsupported_strong_base_pressure_v13 = np.clip(
            gpcr_strong_base_without_support_gate_v13 * gpcr_no_pose_support_gate_v13,
            0.0,
            None,
        )
        gpcr_pose_gap_strong_base_pressure_v13 = np.clip(
            gpcr_strong_base_without_support_gate_v13 * gpcr_pose_gap_gate_v13,
            0.0,
            None,
        )
        binding_base_score = base_score.to_numpy(dtype=float)
        cached_true_base_score = _optional_numeric_column("base_score")
        gpcr_true_base_score_for_gap_v14 = np.where(
            np.isfinite(cached_true_base_score),
            cached_true_base_score,
            binding_base_score,
        )
        cationic_center_available = np.clip(
            np.nan_to_num(
                _optional_numeric_column("cationic_center_available"),
                nan=0.0,
                posinf=0.0,
                neginf=0.0,
            ),
            0.0,
            1.0,
        )
        cationic_center_window_fraction = np.clip(
            np.nan_to_num(
                _optional_numeric_column("cationic_center_contact_fraction_2p8_4p2A"),
                nan=0.0,
                posinf=0.0,
                neginf=0.0,
            ),
            0.0,
            1.0,
        )
        cationic_center_too_close_fraction = np.clip(
            np.nan_to_num(
                _optional_numeric_column("cationic_center_contact_fraction_le_2p8A"),
                nan=0.0,
                posinf=0.0,
                neginf=0.0,
            ),
            0.0,
            1.0,
        )
        gpcr_cationic_anchor_occupancy_support_v14 = np.clip(
            cationic_center_available
            * np.clip(cache_basic_amine_count, 0.0, 1.0)
            * cationic_center_window_fraction
            * (1.0 - cationic_center_too_close_fraction)
            * np.clip(cache_pose_preservation_support, 0.0, 1.0),
            0.0,
            1.0,
        )
        gpcr_pose_support_signal_v14 = np.maximum(
            gpcr_pose_support_signal_v13,
            gpcr_cationic_anchor_occupancy_support_v14,
        )
        gpcr_no_pose_support_gate_v14 = np.clip((0.30 - gpcr_pose_support_signal_v14) / 0.30, 0.0, 1.0)
        gpcr_strong_truebase_gate_v14 = np.clip(
            (-6.0 - gpcr_true_base_score_for_gap_v14) / 2.0,
            0.0,
            None,
        )
        gpcr_truebase_unsupported_strong_base_pressure_v14 = np.clip(
            gpcr_strong_truebase_gate_v14 * gpcr_no_pose_support_gate_v14,
            0.0,
            None,
        )
        gpcr_truebase_pose_gap_pressure_v14 = np.clip(
            gpcr_strong_truebase_gate_v14 * gpcr_pose_gap_gate_v13,
            0.0,
            None,
        )
        gpcr_truebase_backmapping_collapse_pressure_v14 = np.clip(
            gpcr_strong_truebase_gate_v14
            * np.clip((0.20 - np.clip(cache_pose_preservation_support, 0.0, 1.0)) / 0.20, 0.0, 1.0)
            * (1.0 - gpcr_cationic_anchor_occupancy_support_v14),
            0.0,
            None,
        )
        gpcr_truebase_overclose_artifact_pressure_v14 = np.clip(
            gpcr_strong_truebase_gate_v14
            * cationic_center_available
            * cationic_center_too_close_fraction
            * (1.0 - gpcr_cationic_anchor_occupancy_support_v14)
            * gpcr_pose_gap_gate_v13,
            0.0,
            None,
        )
        gpcr_truebase_unsupported_strong_base_pressure_v15 = np.clip(
            gpcr_strong_truebase_gate_v14 * gpcr_no_pose_support_gate_v13,
            0.0,
            None,
        )
        gpcr_truebase_pose_gap_pressure_v15 = gpcr_truebase_pose_gap_pressure_v14
        gpcr_truebase_soft_intrusion_gate_v16 = np.clip(
            (-5.25 - gpcr_true_base_score_for_gap_v14) / 1.25,
            0.0,
            None,
        )
        gpcr_weak_support_missing_gate_v16 = np.clip(
            (0.05 - np.clip(cache_weakbase_support_pressure, 0.0, 1.0)) / 0.05,
            0.0,
            1.0,
        )
        gpcr_basic_count_decoy_like_gate_v16 = np.clip(
            (2.5 - cache_basic_amine_count) / 1.5,
            0.0,
            1.0,
        )
        gpcr_false_support_saturation_pressure_v16 = np.clip(
            np.clip((cache_support_pressure - 0.35) / 0.45, 0.0, 1.0)
            * gpcr_weak_support_missing_gate_v16
            * (1.0 - np.clip(gpcr_moderate_multi_basic_weakbase_support_v12, 0.0, 1.0))
            * gpcr_basic_count_decoy_like_gate_v16
            * gpcr_truebase_soft_intrusion_gate_v16,
            0.0,
            None,
        )
        gpcr_nonbasic_truebase_noanchor_pressure_v16 = np.clip(
            (1.0 - np.clip(cache_basic_amine_count, 0.0, 1.0))
            * gpcr_no_pose_support_gate_v13
            * np.clip((-4.30 - gpcr_true_base_score_for_gap_v14) / 1.30, 0.0, None),
            0.0,
            None,
        )
        gpcr_basic_collapse_truebase_noanchor_pressure_v16 = np.clip(
            np.clip(cache_basic_amine_count, 0.0, 1.0)
            * gpcr_no_pose_support_gate_v13
            * np.clip((0.20 - np.clip(cache_pose_preservation_support, 0.0, 1.0)) / 0.20, 0.0, 1.0)
            * np.clip((-5.00 - gpcr_true_base_score_for_gap_v14) / 1.20, 0.0, None),
            0.0,
            None,
        )
        fixed_reference_feature_collapse_probe = np.asarray(
            [
                np.mean(gpcr_conserved_anchor_proxy > 0.0),
                np.mean(pose_physics_support > 0.0),
                np.mean(gpcr_acidic_anchor_overcontact_prior_gate > 0.0),
            ],
            dtype=float,
        )
        target_internal_pairwise_replay_diagnostic = np.maximum(
            target_internal_pairwise_pressure,
            np.maximum(
                gpcr_pose_chemistry_hard_decoy_pressure,
                gpcr_acidic_anchor_overcontact_prior_gate,
            ),
        )
        donor_rich_decoy_intrusion_pressure = np.maximum(
            _clip_pos(z_hd) + 0.5 * _clip_pos(z_ha) - 0.5 * family_balanced_pose_energy_support,
            0.0,
        )
        computed_linear_features = {
            "z_binding_energy_mmpbsa_kcal_mol_proxy": pd.to_numeric(z_e, errors="coerce").to_numpy(dtype=float),
            "z_mean_min_distance_A": pd.to_numeric(z_d, errors="coerce").to_numpy(dtype=float),
            "z_stability_score": pd.to_numeric(z_s, errors="coerce").to_numpy(dtype=float),
            "z_contact_fraction": pd.to_numeric(z_c, errors="coerce").to_numpy(dtype=float),
            "z_binding_energy_mmpbsa_std": pd.to_numeric(z_std, errors="coerce").to_numpy(dtype=float),
            "z_ligand_affinity_hint": pd.to_numeric(z_aff, errors="coerce").to_numpy(dtype=float),
            "z_ligand_mw": z_ligand_mw,
            "z_ligand_onsps_norm": z_ligand_onsps,
            "z_ligand_logp": pd.to_numeric(z_logp, errors="coerce").to_numpy(dtype=float),
            "z_ligand_rot_bonds": pd.to_numeric(z_rot, errors="coerce").to_numpy(dtype=float),
            "z_ligand_h_donors": pd.to_numeric(z_hd, errors="coerce").to_numpy(dtype=float),
            "z_ligand_h_acceptors": pd.to_numeric(z_ha, errors="coerce").to_numpy(dtype=float),
            "binding_score_composite_v7_prior_active": prior_active_score.to_numpy(dtype=float),
            "gpcr_smiles_present_proxy": gpcr_smiles_present_proxy,
            "family_balanced_pose_energy_support": family_balanced_pose_energy_support,
            "gpcr_conserved_anchor_proxy": gpcr_conserved_anchor_proxy,
            "gpcr_basic_amine_proxy": gpcr_basic_amine_proxy,
            "pose_physics_support": pose_physics_support,
            "prior_overreward_without_anchor": prior_overreward_without_anchor,
            "target_internal_pairwise_pressure": target_internal_pairwise_pressure,
            "gpcr_pose_chemistry_hard_decoy_pressure": gpcr_pose_chemistry_hard_decoy_pressure,
            "gpcr_anchor_chemistry_mismatch_pressure": gpcr_anchor_chemistry_mismatch_pressure,
            "gpcr_acidic_anchor_overcontact_prior_gate": gpcr_acidic_anchor_overcontact_prior_gate,
            "fixed_reference_pose_prior_support": fixed_reference_pose_prior_support,
            "fixed_reference_prior_weakness_pressure": fixed_reference_prior_weakness_pressure,
            "fixed_reference_live_overreward_pressure": fixed_reference_live_overreward_pressure,
            "class_a_orthosteric_motif_support_proxy": class_a_orthosteric_motif_support_proxy,
            "class_a_prior_overreward_invalid_overanchor_pressure": (
                class_a_prior_overreward_invalid_overanchor_pressure
            ),
            "class_a_charge_complemented_anchor_geometry_proxy": (
                class_a_charge_complemented_anchor_geometry_proxy
            ),
            "class_a_orthosteric_occupancy_proxy": class_a_orthosteric_occupancy_proxy,
            "class_a_pose_survival_support_proxy": class_a_pose_survival_support_proxy,
            "class_a_invalid_anchor_prior_pressure_v7": class_a_invalid_anchor_prior_pressure_v7,
            "class_a_atom_anchor_feature_available_proxy": class_a_atom_anchor_feature_available_proxy,
            "class_a_direct_atom_window_anchor_geometry_proxy": (
                class_a_direct_atom_window_anchor_geometry_proxy
            ),
            "class_a_atom_window_pose_survival_proxy": class_a_atom_window_pose_survival_proxy,
            "class_a_hydrophobic_overcontact_pressure_v8": class_a_hydrophobic_overcontact_pressure_v8,
            "class_a_excess_polar_anchor_pressure_v9": class_a_excess_polar_anchor_pressure_v9,
            "class_a_compact_amine_window_support_v9": class_a_compact_amine_window_support_v9,
            "gpcr_synthetic_anchor_saturation_pressure_v12": gpcr_synthetic_anchor_saturation_pressure_v12,
            "gpcr_plausible_anchor_window_support_v12": gpcr_plausible_anchor_window_support_v12,
            "gpcr_moderate_multi_basic_weakbase_support_v12": gpcr_moderate_multi_basic_weakbase_support_v12,
            "gpcr_pose_support_signal_v13": gpcr_pose_support_signal_v13,
            "gpcr_unsupported_strong_base_pressure_v13": gpcr_unsupported_strong_base_pressure_v13,
            "gpcr_pose_gap_strong_base_pressure_v13": gpcr_pose_gap_strong_base_pressure_v13,
            "gpcr_true_base_score_for_gap_v14": gpcr_true_base_score_for_gap_v14,
            "gpcr_cationic_anchor_occupancy_support_v14": gpcr_cationic_anchor_occupancy_support_v14,
            "gpcr_pose_support_signal_v14": gpcr_pose_support_signal_v14,
            "gpcr_truebase_unsupported_strong_base_pressure_v14": (
                gpcr_truebase_unsupported_strong_base_pressure_v14
            ),
            "gpcr_truebase_pose_gap_pressure_v14": gpcr_truebase_pose_gap_pressure_v14,
            "gpcr_truebase_backmapping_collapse_pressure_v14": (
                gpcr_truebase_backmapping_collapse_pressure_v14
            ),
            "gpcr_truebase_overclose_artifact_pressure_v14": gpcr_truebase_overclose_artifact_pressure_v14,
            "gpcr_truebase_unsupported_strong_base_pressure_v15": (
                gpcr_truebase_unsupported_strong_base_pressure_v15
            ),
            "gpcr_truebase_pose_gap_pressure_v15": gpcr_truebase_pose_gap_pressure_v15,
            "gpcr_false_support_saturation_pressure_v16": gpcr_false_support_saturation_pressure_v16,
            "gpcr_nonbasic_truebase_noanchor_pressure_v16": gpcr_nonbasic_truebase_noanchor_pressure_v16,
            "gpcr_basic_collapse_truebase_noanchor_pressure_v16": (
                gpcr_basic_collapse_truebase_noanchor_pressure_v16
            ),
            "fixed_reference_feature_collapse_probe": np.full(
                len(result_df),
                float(np.max(fixed_reference_feature_collapse_probe))
                if fixed_reference_feature_collapse_probe.size
                else 0.0,
                dtype=float,
            ),
            "fixed_reference_scaling_enabled": np.full(
                len(result_df),
                1.0 if fixed_reference_scaling_enabled else 0.0,
                dtype=float,
            ),
            "target_internal_pairwise_replay_diagnostic": target_internal_pairwise_replay_diagnostic,
            "donor_rich_decoy_intrusion_pressure": donor_rich_decoy_intrusion_pressure,
            "residual_shadow_prior_pressure": prior_pressure,
            "residual_shadow_structure_weakness": structural_weakness,
            "residual_shadow_structure_support": structural_support,
            "residual_shadow_intrusion_pressure": intrusion_pressure,
            "residual_shadow_intrusion_contact_support": intrusion_contact_support,
            "residual_shadow_intrusion_delta_raw": intrusion_raw_delta,
            "residual_shadow_contact_mismatch": contact_mismatch,
            "residual_shadow_affinity_md_support": affinity_md_support,
            "residual_shadow_affinity_md_support_mismatch": affinity_md_support_mismatch,
            "residual_shadow_mismatch_contact_delta_raw": mismatch_contact_raw_delta,
            "residual_shadow_delta_raw": raw_delta,
            "residual_shadow_delta": delta,
        }
        missing_terms: list[str] = []
        for term in terms:
            if not isinstance(term, dict):
                continue
            feature = str(term.get("feature", "") or "").strip()
            if not feature:
                continue
            if feature in computed_linear_features:
                values = np.asarray(computed_linear_features[feature], dtype=float)
            elif feature in result_df.columns:
                values = pd.to_numeric(result_df[feature], errors="coerce").fillna(0.0).to_numpy(dtype=float)
            else:
                missing_terms.append(feature)
                continue
            linear_score += _safe_float(term.get("weight"), 0.0) * values
            linear_rescore_term_count += 1
        if linear_rescore_term_count <= 0:
            linear_rescore_status = "missing_terms"
        elif combine_mode == "replace":
            shadow_score = pd.Series(linear_score, index=result_df.index)
            delta = pd.to_numeric(shadow_score - base_score, errors="coerce").to_numpy(dtype=float)
            raw_delta = delta
            activation_mask = np.isfinite(delta) & (np.abs(delta) > 0.0)
            band = np.where(np.abs(delta) >= float(yellow_band), "yellow", np.where(np.abs(delta) > 0.0, "green", "none"))
            linear_rescore_status = "applied" if not missing_terms else "applied_with_missing_terms"
        elif combine_mode in {"add", "additive"}:
            shadow_score = shadow_score + linear_score
            delta = pd.to_numeric(shadow_score - base_score, errors="coerce").to_numpy(dtype=float)
            raw_delta = delta
            activation_mask = np.isfinite(delta) & (np.abs(delta) > 0.0)
            band = np.where(np.abs(delta) >= float(yellow_band), "yellow", np.where(np.abs(delta) > 0.0, "green", "none"))
            linear_rescore_status = "applied" if not missing_terms else "applied_with_missing_terms"
        else:
            linear_rescore_status = "unsupported_combine_mode"
    if str(tuning["variant"]) in {
        "gpcr_adrb2_beta_blocker_pharmacophore_v1",
        "gpcr_core_family_balanced_beta_blocker_rescue_v2",
    }:
        smiles_series = (
            result_df["ligand_smiles"]
            if "ligand_smiles" in result_df.columns
            else result_df["smiles"]
            if "smiles" in result_df.columns
            else pd.Series([""] * len(result_df), index=result_df.index)
        )
        pharmacophore_matches = smiles_series.apply(_adrb2_beta_blocker_pharmacophore_match).astype(int).to_numpy()
        pharmacophore_reward = pharmacophore_matches.astype(float) * float(tuning["pharmacophore_reward_score"])
        shadow_score = pd.to_numeric(shadow_score, errors="coerce") - pharmacophore_reward
        delta = pd.to_numeric(shadow_score - base_score, errors="coerce").to_numpy(dtype=float)
        raw_delta = delta
        activation_mask = pharmacophore_matches.astype(bool)
        band = np.where(
            np.abs(delta) >= float(yellow_band),
            "yellow",
            np.where(np.abs(delta) > 0.0, "green", "none"),
        )
    result_df["residual_shadow_prior_pressure"] = prior_pressure
    result_df["residual_shadow_structure_weakness"] = structural_weakness
    result_df["residual_shadow_structure_support"] = structural_support
    result_df["residual_shadow_intrusion_pressure"] = intrusion_pressure
    result_df["residual_shadow_intrusion_contact_support"] = intrusion_contact_support
    result_df["residual_shadow_intrusion_delta_raw"] = intrusion_raw_delta
    result_df["residual_shadow_contact_mismatch"] = contact_mismatch
    result_df["residual_shadow_affinity_md_support"] = affinity_md_support
    result_df["residual_shadow_affinity_md_support_mismatch"] = affinity_md_support_mismatch
    result_df["residual_shadow_mismatch_contact_delta_raw"] = mismatch_contact_raw_delta
    result_df["binding_score_composite_v7_prior_active"] = prior_active_score
    result_df["gpcr_smiles_present_proxy"] = (
        computed_linear_features.get("gpcr_smiles_present_proxy", np.zeros(len(result_df), dtype=float))
        if linear_rescore_enabled
        else np.zeros(len(result_df), dtype=float)
    )
    result_df["gpcr_conserved_anchor_proxy"] = (
        computed_linear_features.get("gpcr_conserved_anchor_proxy", np.zeros(len(result_df), dtype=float))
        if linear_rescore_enabled
        else np.zeros(len(result_df), dtype=float)
    )
    result_df["gpcr_basic_amine_proxy"] = (
        computed_linear_features.get("gpcr_basic_amine_proxy", np.zeros(len(result_df), dtype=float))
        if linear_rescore_enabled
        else np.zeros(len(result_df), dtype=float)
    )
    result_df["pose_physics_support"] = (
        computed_linear_features.get("pose_physics_support", np.zeros(len(result_df), dtype=float))
        if linear_rescore_enabled
        else np.zeros(len(result_df), dtype=float)
    )
    result_df["prior_overreward_without_anchor"] = (
        computed_linear_features.get("prior_overreward_without_anchor", np.zeros(len(result_df), dtype=float))
        if linear_rescore_enabled
        else np.zeros(len(result_df), dtype=float)
    )
    result_df["target_internal_pairwise_pressure"] = (
        computed_linear_features.get("target_internal_pairwise_pressure", np.zeros(len(result_df), dtype=float))
        if linear_rescore_enabled
        else np.zeros(len(result_df), dtype=float)
    )
    result_df["gpcr_pose_chemistry_hard_decoy_pressure"] = (
        computed_linear_features.get("gpcr_pose_chemistry_hard_decoy_pressure", np.zeros(len(result_df), dtype=float))
        if linear_rescore_enabled
        else np.zeros(len(result_df), dtype=float)
    )
    result_df["gpcr_anchor_chemistry_mismatch_pressure"] = (
        computed_linear_features.get("gpcr_anchor_chemistry_mismatch_pressure", np.zeros(len(result_df), dtype=float))
        if linear_rescore_enabled
        else np.zeros(len(result_df), dtype=float)
    )
    result_df["gpcr_acidic_anchor_overcontact_prior_gate"] = (
        computed_linear_features.get(
            "gpcr_acidic_anchor_overcontact_prior_gate",
            np.zeros(len(result_df), dtype=float),
        )
        if linear_rescore_enabled
        else np.zeros(len(result_df), dtype=float)
    )
    result_df["fixed_reference_pose_prior_support"] = (
        computed_linear_features.get("fixed_reference_pose_prior_support", np.zeros(len(result_df), dtype=float))
        if linear_rescore_enabled
        else np.zeros(len(result_df), dtype=float)
    )
    result_df["fixed_reference_prior_weakness_pressure"] = (
        computed_linear_features.get("fixed_reference_prior_weakness_pressure", np.zeros(len(result_df), dtype=float))
        if linear_rescore_enabled
        else np.zeros(len(result_df), dtype=float)
    )
    result_df["fixed_reference_live_overreward_pressure"] = (
        computed_linear_features.get("fixed_reference_live_overreward_pressure", np.zeros(len(result_df), dtype=float))
        if linear_rescore_enabled
        else np.zeros(len(result_df), dtype=float)
    )
    result_df["class_a_orthosteric_motif_support_proxy"] = (
        computed_linear_features.get("class_a_orthosteric_motif_support_proxy", np.zeros(len(result_df), dtype=float))
        if linear_rescore_enabled
        else np.zeros(len(result_df), dtype=float)
    )
    result_df["class_a_prior_overreward_invalid_overanchor_pressure"] = (
        computed_linear_features.get(
            "class_a_prior_overreward_invalid_overanchor_pressure",
            np.zeros(len(result_df), dtype=float),
        )
        if linear_rescore_enabled
        else np.zeros(len(result_df), dtype=float)
    )
    result_df["class_a_charge_complemented_anchor_geometry_proxy"] = (
        computed_linear_features.get(
            "class_a_charge_complemented_anchor_geometry_proxy",
            np.zeros(len(result_df), dtype=float),
        )
        if linear_rescore_enabled
        else np.zeros(len(result_df), dtype=float)
    )
    result_df["class_a_orthosteric_occupancy_proxy"] = (
        computed_linear_features.get("class_a_orthosteric_occupancy_proxy", np.zeros(len(result_df), dtype=float))
        if linear_rescore_enabled
        else np.zeros(len(result_df), dtype=float)
    )
    result_df["class_a_pose_survival_support_proxy"] = (
        computed_linear_features.get("class_a_pose_survival_support_proxy", np.zeros(len(result_df), dtype=float))
        if linear_rescore_enabled
        else np.zeros(len(result_df), dtype=float)
    )
    result_df["class_a_invalid_anchor_prior_pressure_v7"] = (
        computed_linear_features.get("class_a_invalid_anchor_prior_pressure_v7", np.zeros(len(result_df), dtype=float))
        if linear_rescore_enabled
        else np.zeros(len(result_df), dtype=float)
    )
    result_df["class_a_atom_anchor_feature_available_proxy"] = (
        computed_linear_features.get(
            "class_a_atom_anchor_feature_available_proxy",
            np.zeros(len(result_df), dtype=float),
        )
        if linear_rescore_enabled
        else np.zeros(len(result_df), dtype=float)
    )
    result_df["class_a_direct_atom_window_anchor_geometry_proxy"] = (
        computed_linear_features.get(
            "class_a_direct_atom_window_anchor_geometry_proxy",
            np.zeros(len(result_df), dtype=float),
        )
        if linear_rescore_enabled
        else np.zeros(len(result_df), dtype=float)
    )
    result_df["class_a_atom_window_pose_survival_proxy"] = (
        computed_linear_features.get(
            "class_a_atom_window_pose_survival_proxy",
            np.zeros(len(result_df), dtype=float),
        )
        if linear_rescore_enabled
        else np.zeros(len(result_df), dtype=float)
    )
    result_df["class_a_hydrophobic_overcontact_pressure_v8"] = (
        computed_linear_features.get(
            "class_a_hydrophobic_overcontact_pressure_v8",
            np.zeros(len(result_df), dtype=float),
        )
        if linear_rescore_enabled
        else np.zeros(len(result_df), dtype=float)
    )
    result_df["class_a_excess_polar_anchor_pressure_v9"] = (
        computed_linear_features.get(
            "class_a_excess_polar_anchor_pressure_v9",
            np.zeros(len(result_df), dtype=float),
        )
        if linear_rescore_enabled
        else np.zeros(len(result_df), dtype=float)
    )
    result_df["class_a_compact_amine_window_support_v9"] = (
        computed_linear_features.get(
            "class_a_compact_amine_window_support_v9",
            np.zeros(len(result_df), dtype=float),
        )
        if linear_rescore_enabled
        else np.zeros(len(result_df), dtype=float)
    )
    result_df["gpcr_synthetic_anchor_saturation_pressure_v12"] = (
        computed_linear_features.get(
            "gpcr_synthetic_anchor_saturation_pressure_v12",
            np.zeros(len(result_df), dtype=float),
        )
        if linear_rescore_enabled
        else np.zeros(len(result_df), dtype=float)
    )
    result_df["gpcr_plausible_anchor_window_support_v12"] = (
        computed_linear_features.get(
            "gpcr_plausible_anchor_window_support_v12",
            np.zeros(len(result_df), dtype=float),
        )
        if linear_rescore_enabled
        else np.zeros(len(result_df), dtype=float)
    )
    result_df["gpcr_moderate_multi_basic_weakbase_support_v12"] = (
        computed_linear_features.get(
            "gpcr_moderate_multi_basic_weakbase_support_v12",
            np.zeros(len(result_df), dtype=float),
        )
        if linear_rescore_enabled
        else np.zeros(len(result_df), dtype=float)
    )
    result_df["gpcr_pose_support_signal_v13"] = (
        computed_linear_features.get(
            "gpcr_pose_support_signal_v13",
            np.zeros(len(result_df), dtype=float),
        )
        if linear_rescore_enabled
        else np.zeros(len(result_df), dtype=float)
    )
    result_df["gpcr_unsupported_strong_base_pressure_v13"] = (
        computed_linear_features.get(
            "gpcr_unsupported_strong_base_pressure_v13",
            np.zeros(len(result_df), dtype=float),
        )
        if linear_rescore_enabled
        else np.zeros(len(result_df), dtype=float)
    )
    result_df["gpcr_pose_gap_strong_base_pressure_v13"] = (
        computed_linear_features.get(
            "gpcr_pose_gap_strong_base_pressure_v13",
            np.zeros(len(result_df), dtype=float),
        )
        if linear_rescore_enabled
        else np.zeros(len(result_df), dtype=float)
    )
    result_df["gpcr_true_base_score_for_gap_v14"] = (
        computed_linear_features.get(
            "gpcr_true_base_score_for_gap_v14",
            np.zeros(len(result_df), dtype=float),
        )
        if linear_rescore_enabled
        else np.zeros(len(result_df), dtype=float)
    )
    result_df["gpcr_cationic_anchor_occupancy_support_v14"] = (
        computed_linear_features.get(
            "gpcr_cationic_anchor_occupancy_support_v14",
            np.zeros(len(result_df), dtype=float),
        )
        if linear_rescore_enabled
        else np.zeros(len(result_df), dtype=float)
    )
    result_df["gpcr_pose_support_signal_v14"] = (
        computed_linear_features.get(
            "gpcr_pose_support_signal_v14",
            np.zeros(len(result_df), dtype=float),
        )
        if linear_rescore_enabled
        else np.zeros(len(result_df), dtype=float)
    )
    result_df["gpcr_truebase_unsupported_strong_base_pressure_v14"] = (
        computed_linear_features.get(
            "gpcr_truebase_unsupported_strong_base_pressure_v14",
            np.zeros(len(result_df), dtype=float),
        )
        if linear_rescore_enabled
        else np.zeros(len(result_df), dtype=float)
    )
    result_df["gpcr_truebase_pose_gap_pressure_v14"] = (
        computed_linear_features.get(
            "gpcr_truebase_pose_gap_pressure_v14",
            np.zeros(len(result_df), dtype=float),
        )
        if linear_rescore_enabled
        else np.zeros(len(result_df), dtype=float)
    )
    result_df["gpcr_truebase_backmapping_collapse_pressure_v14"] = (
        computed_linear_features.get(
            "gpcr_truebase_backmapping_collapse_pressure_v14",
            np.zeros(len(result_df), dtype=float),
        )
        if linear_rescore_enabled
        else np.zeros(len(result_df), dtype=float)
    )
    result_df["gpcr_truebase_overclose_artifact_pressure_v14"] = (
        computed_linear_features.get(
            "gpcr_truebase_overclose_artifact_pressure_v14",
            np.zeros(len(result_df), dtype=float),
        )
        if linear_rescore_enabled
        else np.zeros(len(result_df), dtype=float)
    )
    result_df["gpcr_truebase_unsupported_strong_base_pressure_v15"] = (
        computed_linear_features.get(
            "gpcr_truebase_unsupported_strong_base_pressure_v15",
            np.zeros(len(result_df), dtype=float),
        )
        if linear_rescore_enabled
        else np.zeros(len(result_df), dtype=float)
    )
    result_df["gpcr_truebase_pose_gap_pressure_v15"] = (
        computed_linear_features.get(
            "gpcr_truebase_pose_gap_pressure_v15",
            np.zeros(len(result_df), dtype=float),
        )
        if linear_rescore_enabled
        else np.zeros(len(result_df), dtype=float)
    )
    result_df["gpcr_false_support_saturation_pressure_v16"] = (
        computed_linear_features.get(
            "gpcr_false_support_saturation_pressure_v16",
            np.zeros(len(result_df), dtype=float),
        )
        if linear_rescore_enabled
        else np.zeros(len(result_df), dtype=float)
    )
    result_df["gpcr_nonbasic_truebase_noanchor_pressure_v16"] = (
        computed_linear_features.get(
            "gpcr_nonbasic_truebase_noanchor_pressure_v16",
            np.zeros(len(result_df), dtype=float),
        )
        if linear_rescore_enabled
        else np.zeros(len(result_df), dtype=float)
    )
    result_df["gpcr_basic_collapse_truebase_noanchor_pressure_v16"] = (
        computed_linear_features.get(
            "gpcr_basic_collapse_truebase_noanchor_pressure_v16",
            np.zeros(len(result_df), dtype=float),
        )
        if linear_rescore_enabled
        else np.zeros(len(result_df), dtype=float)
    )
    result_df["fixed_reference_feature_collapse_probe"] = (
        computed_linear_features.get("fixed_reference_feature_collapse_probe", np.zeros(len(result_df), dtype=float))
        if linear_rescore_enabled
        else np.zeros(len(result_df), dtype=float)
    )
    result_df["fixed_reference_scaling_enabled"] = (
        computed_linear_features.get("fixed_reference_scaling_enabled", np.zeros(len(result_df), dtype=float))
        if linear_rescore_enabled
        else np.zeros(len(result_df), dtype=float)
    )
    result_df["target_internal_pairwise_replay_diagnostic"] = (
        computed_linear_features.get("target_internal_pairwise_replay_diagnostic", np.zeros(len(result_df), dtype=float))
        if linear_rescore_enabled
        else np.zeros(len(result_df), dtype=float)
    )
    result_df["residual_shadow_delta_raw"] = raw_delta
    result_df["residual_shadow_delta"] = delta
    result_df["residual_shadow_band"] = band
    result_df["gpcr_adrb2_beta_blocker_pharmacophore_match"] = pharmacophore_matches
    result_df["gpcr_adrb2_beta_blocker_pharmacophore_reward"] = pharmacophore_reward
    result_df["binding_score_composite_v7_residual_shadow"] = shadow_score
    shadow_only_active_locked = str(tuning["variant"]) in {
        "gpcr_core_acidic_anchor_overcontact_prior_gate_v4",
        "gpcr_core_fixed_reference_live_shadow_v5",
        "gpcr_core_class_a_motif_shadow_v6",
        "gpcr_core_class_a_anchor_geometry_shadow_v7",
        "gpcr_core_direct_atom_anchor_window_shadow_v8",
        "gpcr_core_atom_window_excess_polar_shadow_v9",
        "gpcr_core_cationic_pose_distortion_shadow_v10",
        "gpcr_core_cationic_weakbase_rescue_shadow_v11",
        "gpcr_core_synthetic_anchor_penalty_shadow_v12",
        "gpcr_core_pose_support_gap_shadow_v13",
        "gpcr_core_truebase_anchor_occupancy_shadow_v14",
        "gpcr_core_truebase_gap_penalty_shadow_v15",
        "gpcr_core_false_support_discriminator_shadow_v16",
    }
    result_df["binding_score_composite_v7_residual_active"] = (
        shadow_score if mode in {"apply", "apply_ranking"} and not shadow_only_active_locked else base_score
    )
    result_df["residual_shadow_family"] = family
    result_df["residual_shadow_mode"] = mode
    result_df["residual_shadow_runtime_hook_ready"] = bool(runtime_hook_ready)

    top_shadow = (
        result_df.sort_values("binding_score_composite_v7_residual_shadow", ascending=True)
        .head(10)[
            [
                col
                for col in [
                    "ligand_id",
                    "binding_score_composite_v7",
                    "binding_score_composite_v7_residual_shadow",
                    "residual_shadow_delta",
                    "residual_shadow_band",
                ]
                if col in result_df.columns
            ]
        ]
        .to_dict(orient="records")
    )
    summary.update(
        {
            "active_score_col": (
                "binding_score_composite_v7_residual_active"
                if mode in {"apply", "apply_ranking"} and not shadow_only_active_locked
                else "binding_score_composite_v7"
            ),
            "shadow_score_col": "binding_score_composite_v7_residual_shadow",
            "positive_delta_count": int((delta > 0.0).sum()),
            "gated_positive_delta_count": int(activation_mask.sum()),
            "intrusion_positive_delta_count": int(((intrusion_raw_delta > 0.0) & intrusion_activation_mask).sum()),
            "mismatch_contact_positive_delta_count": int(
                ((mismatch_contact_raw_delta > 0.0) & mismatch_contact_activation_mask).sum()
            ),
            "affinity_md_support_mismatch_positive_count": int(
                ((affinity_md_support_mismatch > 0.0) & mismatch_contact_activation_mask).sum()
            ),
            "yellow_band_count": int((delta >= float(yellow_band)).sum()),
            "mean_delta": float(np.mean(delta)) if len(delta) > 0 else 0.0,
            "max_delta": float(np.max(delta)) if len(delta) > 0 else 0.0,
            "status": (
                "shadow_ready_claim_locked"
                if shadow_only_active_locked
                else "shadow_ready"
                if mode == "shadow_only"
                else "apply_ready"
            ),
            "top_shadow": top_shadow,
            "max_abs_delta_score": float(max_abs_delta),
            "yellow_band_abs_delta_score": float(yellow_band),
            "tuning_variant": str(tuning["variant"]),
            "min_prior_pressure_for_delta": float(tuning["min_prior_pressure_for_delta"]),
            "min_structural_weakness_for_delta": float(tuning["min_structural_weakness_for_delta"]),
            "max_structural_support_for_delta": float(tuning["max_structural_support_for_delta"]),
            "min_raw_delta_for_activation": float(tuning["min_raw_delta_for_activation"]),
            "min_intrusion_prior_pressure_for_delta": float(tuning["min_intrusion_prior_pressure_for_delta"]),
            "min_intrusion_contact_support_for_delta": float(
                tuning["min_intrusion_contact_support_for_delta"]
            ),
            "linear_rescore_enabled": bool(linear_rescore_enabled),
            "linear_rescore_status": linear_rescore_status,
            "linear_rescore_term_count": int(linear_rescore_term_count),
            "linear_rescore_missing_terms": list(missing_terms) if linear_rescore_enabled else [],
            "pharmacophore_positive_match_count": int(pharmacophore_matches.sum()),
            "pharmacophore_reward_score": float(tuning["pharmacophore_reward_score"]),
            "shadow_only_active_locked": bool(shadow_only_active_locked),
            "fixed_reference_scaling_enabled": bool(score_reference_scaling_mode == "fixed_family_reference"),
            "fixed_reference_live_positive_pressure_count": int(
                (pd.to_numeric(result_df["fixed_reference_live_overreward_pressure"], errors="coerce") > 0.0).sum()
            ),
            "class_a_motif_support_positive_count": int(
                (pd.to_numeric(result_df["class_a_orthosteric_motif_support_proxy"], errors="coerce") > 0.0).sum()
            ),
            "class_a_prior_overreward_invalid_overanchor_positive_count": int(
                (
                    pd.to_numeric(
                        result_df["class_a_prior_overreward_invalid_overanchor_pressure"],
                        errors="coerce",
                    )
                    > 0.0
                ).sum()
            ),
            "class_a_charge_complemented_anchor_geometry_positive_count": int(
                (
                    pd.to_numeric(
                        result_df["class_a_charge_complemented_anchor_geometry_proxy"],
                        errors="coerce",
                    )
                    > 0.0
                ).sum()
            ),
            "class_a_orthosteric_occupancy_positive_count": int(
                (pd.to_numeric(result_df["class_a_orthosteric_occupancy_proxy"], errors="coerce") > 0.0).sum()
            ),
            "class_a_pose_survival_support_positive_count": int(
                (
                    pd.to_numeric(
                        result_df["class_a_pose_survival_support_proxy"],
                        errors="coerce",
                    )
                    > 0.0
                ).sum()
            ),
            "class_a_invalid_anchor_prior_pressure_v7_positive_count": int(
                (
                    pd.to_numeric(
                        result_df["class_a_invalid_anchor_prior_pressure_v7"],
                        errors="coerce",
                    )
                    > 0.0
                ).sum()
            ),
            "class_a_atom_anchor_feature_available_count": int(
                (
                    pd.to_numeric(
                        result_df["class_a_atom_anchor_feature_available_proxy"],
                        errors="coerce",
                    )
                    > 0.0
                ).sum()
            ),
            "class_a_direct_atom_window_anchor_geometry_positive_count": int(
                (
                    pd.to_numeric(
                        result_df["class_a_direct_atom_window_anchor_geometry_proxy"],
                        errors="coerce",
                    )
                    > 0.0
                ).sum()
            ),
            "class_a_hydrophobic_overcontact_pressure_v8_positive_count": int(
                (
                    pd.to_numeric(
                        result_df["class_a_hydrophobic_overcontact_pressure_v8"],
                        errors="coerce",
                    )
                    > 0.0
                ).sum()
            ),
            "class_a_excess_polar_anchor_pressure_v9_positive_count": int(
                (
                    pd.to_numeric(
                        result_df["class_a_excess_polar_anchor_pressure_v9"],
                        errors="coerce",
                    )
                    > 0.0
                ).sum()
            ),
            "class_a_compact_amine_window_support_v9_positive_count": int(
                (
                    pd.to_numeric(
                        result_df["class_a_compact_amine_window_support_v9"],
                        errors="coerce",
                    )
                    > 0.0
                ).sum()
            ),
            "fixed_reference_live_mean_pressure": float(
                pd.to_numeric(result_df["fixed_reference_live_overreward_pressure"], errors="coerce").mean()
            )
            if len(result_df) > 0
            else 0.0,
            "fixed_reference_feature_nonzero_counts": {
                "gpcr_conserved_anchor_proxy": int(
                    (pd.to_numeric(result_df["gpcr_conserved_anchor_proxy"], errors="coerce") > 0.0).sum()
                ),
                "pose_physics_support": int(
                    (pd.to_numeric(result_df["pose_physics_support"], errors="coerce") > 0.0).sum()
                ),
                "gpcr_acidic_anchor_overcontact_prior_gate": int(
                    (
                        pd.to_numeric(
                            result_df["gpcr_acidic_anchor_overcontact_prior_gate"],
                            errors="coerce",
                        )
                        > 0.0
                    ).sum()
                ),
                "target_internal_pairwise_pressure": int(
                    (pd.to_numeric(result_df["target_internal_pairwise_pressure"], errors="coerce") > 0.0).sum()
                ),
                "fixed_reference_prior_weakness_pressure": int(
                    (
                        pd.to_numeric(
                            result_df["fixed_reference_prior_weakness_pressure"],
                            errors="coerce",
                        )
                        > 0.0
                    ).sum()
                ),
                "gpcr_pose_chemistry_hard_decoy_pressure": int(
                    (
                        pd.to_numeric(
                            result_df["gpcr_pose_chemistry_hard_decoy_pressure"],
                            errors="coerce",
                        )
                        > 0.0
                    ).sum()
                ),
                "fixed_reference_live_overreward_pressure": int(
                    (
                        pd.to_numeric(
                            result_df["fixed_reference_live_overreward_pressure"],
                            errors="coerce",
                        )
                        > 0.0
                    ).sum()
                ),
            },
        }
    )
    return result_df, summary


def _parse_pdb_coords(path: str) -> Tuple[np.ndarray, np.ndarray]:
    protein = []
    ligand = []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if not (line.startswith("ATOM") or line.startswith("HETATM")):
                continue
            try:
                x = float(line[30:38])
                y = float(line[38:46])
                z = float(line[46:54])
            except Exception:
                continue
            resn = str(line[17:20]).strip().upper()
            chain = str(line[21:22]).strip().upper()
            if resn == "LIG" or chain == "L":
                ligand.append([x, y, z])
            else:
                protein.append([x, y, z])
    return (
        np.asarray(protein, dtype=np.float32),
        np.asarray(ligand, dtype=np.float32),
    )


def _as_xyz_array(points: List[Sequence[float]]) -> np.ndarray:
    if not points:
        return np.zeros((0, 3), dtype=np.float32)
    return np.asarray(points, dtype=np.float32)


def _parse_pdb_protein_anchor(path: str) -> Dict[str, Any]:
    protein_all: List[List[float]] = []
    protein_ca: List[List[float]] = []
    ligand: List[List[float]] = []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if not (line.startswith("ATOM") or line.startswith("HETATM")):
                continue
            try:
                x = float(line[30:38])
                y = float(line[38:46])
                z = float(line[46:54])
            except Exception:
                continue
            atom_name = str(line[12:16]).strip().upper()
            resn = str(line[17:20]).strip().upper()
            chain = str(line[21:22]).strip().upper()
            xyz = [x, y, z]
            if resn == "LIG" or chain == "L" or line.startswith("HETATM"):
                ligand.append(xyz)
                continue
            protein_all.append(xyz)
            if atom_name == "CA":
                protein_ca.append(xyz)
    return {
        "protein_all": _as_xyz_array(protein_all),
        "protein_ca": _as_xyz_array(protein_ca),
        "ligand": _as_xyz_array(ligand),
    }


def _parse_mmcif_protein_anchor(path: str) -> Dict[str, Any]:
    protein_all: List[List[float]] = []
    protein_ca: List[List[float]] = []
    ligand: List[List[float]] = []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    headers: List[str] = []
    row_tokens: List[str] = []
    in_atom_site_loop = False
    i = 0
    while i < len(lines):
        raw_line = lines[i]
        stripped = raw_line.strip()
        i += 1
        if not stripped:
            continue
        if stripped == "loop_":
            headers = []
            row_tokens = []
            in_atom_site_loop = False
            continue
        if stripped.startswith("_atom_site."):
            headers.append(stripped)
            in_atom_site_loop = True
            continue
        if headers and stripped.startswith("_") and not stripped.startswith("_atom_site."):
            headers = []
            row_tokens = []
            in_atom_site_loop = False
            continue
        if not in_atom_site_loop or not headers:
            continue
        if stripped == "#":
            break
        row_tokens.extend(shlex.split(stripped, posix=True))
        if len(row_tokens) < len(headers):
            continue
        row = {headers[idx]: row_tokens[idx] for idx in range(len(headers))}
        row_tokens = row_tokens[len(headers) :]
        group = str(row.get("_atom_site.group_PDB", "")).strip().upper()
        atom_name = str(
            row.get("_atom_site.label_atom_id")
            or row.get("_atom_site.auth_atom_id")
            or ""
        ).strip().upper()
        resn = str(
            row.get("_atom_site.label_comp_id")
            or row.get("_atom_site.auth_comp_id")
            or ""
        ).strip().upper()
        chain = str(
            row.get("_atom_site.auth_asym_id")
            or row.get("_atom_site.label_asym_id")
            or ""
        ).strip().upper()
        try:
            x = float(row.get("_atom_site.Cartn_x", "nan"))
            y = float(row.get("_atom_site.Cartn_y", "nan"))
            z = float(row.get("_atom_site.Cartn_z", "nan"))
        except Exception:
            continue
        if not (np.isfinite(x) and np.isfinite(y) and np.isfinite(z)):
            continue
        xyz = [x, y, z]
        if group == "HETATM" or resn == "LIG" or chain == "L":
            ligand.append(xyz)
            continue
        protein_all.append(xyz)
        if atom_name == "CA":
            protein_ca.append(xyz)
    return {
        "protein_all": _as_xyz_array(protein_all),
        "protein_ca": _as_xyz_array(protein_ca),
        "ligand": _as_xyz_array(ligand),
    }


def _native_source_format(path: str) -> str:
    ext = os.path.splitext(str(path or "").strip())[1].lower()
    if ext == ".pdb":
        return "pdb"
    if ext in {".cif", ".mmcif"}:
        return "mmcif"
    return ""


def _empty_native_target_info(target: str, explicit_native_path: str = "", note: str = "") -> Dict[str, Any]:
    return {
        "coords": np.zeros((0, 3), dtype=np.float32),
        "source_lookup_target": str(target or "").strip(),
        "source_path": "",
        "source_kind": "missing",
        "source_format": "",
        "source_available": False,
        "source_explicit_native_path": str(explicit_native_path or "").strip(),
        "source_requested_explicit_native_path": bool(str(explicit_native_path or "").strip()),
        "source_used_explicit_native_path": False,
        "source_is_aligned_for_backmap": False,
        "source_residue_anchor_mode": "missing",
        "protein_atom_count": 0,
        "protein_ca_count": 0,
        "ligand_atom_count": 0,
        "notes": str(note or "").strip(),
    }


def _native_target_info_from_structure(
    *,
    target: str,
    source_path: str,
    source_kind: str,
    source_format: str,
    explicit_native_path: str,
    parse_result: Dict[str, Any],
    source_used_explicit_native_path: bool,
    note: str = "",
) -> Dict[str, Any]:
    protein_all = np.asarray(parse_result.get("protein_all"), dtype=np.float32)
    protein_ca = np.asarray(parse_result.get("protein_ca"), dtype=np.float32)
    ligand = np.asarray(parse_result.get("ligand"), dtype=np.float32)
    coords = protein_ca if protein_ca.shape[0] > 0 else protein_all
    residue_anchor_mode = "ca_only" if protein_ca.shape[0] > 0 else "all_atom_fallback"
    return {
        "coords": coords.astype(np.float32, copy=False),
        "source_lookup_target": str(target or "").strip(),
        "source_path": os.path.abspath(str(source_path)),
        "source_kind": str(source_kind),
        "source_format": str(source_format),
        "source_available": bool(coords.shape[0] > 0),
        "source_explicit_native_path": str(explicit_native_path or "").strip(),
        "source_requested_explicit_native_path": bool(str(explicit_native_path or "").strip()),
        "source_used_explicit_native_path": bool(source_used_explicit_native_path),
        "source_is_aligned_for_backmap": bool(coords.shape[0] > 0),
        "source_residue_anchor_mode": residue_anchor_mode,
        "protein_atom_count": int(protein_all.shape[0]),
        "protein_ca_count": int(protein_ca.shape[0]),
        "ligand_atom_count": int(ligand.shape[0]),
        "notes": str(note or "").strip(),
    }


def _compose_ligand_xyz(row: Dict[str, Any]) -> np.ndarray:
    px = float(row.get("pocket_x", 0.0))
    py = float(row.get("pocket_y", 0.0))
    pz = float(row.get("pocket_z", 0.0))
    b0 = np.asarray(
        [
            float(row.get("ligand_bead0_x", -0.8)),
            float(row.get("ligand_bead0_y", 0.0)),
            float(row.get("ligand_bead0_z", 0.0)),
        ],
        dtype=np.float32,
    )
    b1 = np.asarray(
        [
            float(row.get("ligand_bead1_x", 0.8)),
            float(row.get("ligand_bead1_y", 0.0)),
            float(row.get("ligand_bead1_z", 0.0)),
        ],
        dtype=np.float32,
    )
    center = np.asarray([px, py, pz], dtype=np.float32)
    out = [center + b0, center + b1]
    bead2_keys = ("ligand_bead2_x", "ligand_bead2_y", "ligand_bead2_z")
    if all(k in row for k in bead2_keys):
        b2 = np.asarray(
            [
                float(row.get("ligand_bead2_x", 0.0)),
                float(row.get("ligand_bead2_y", 0.7)),
                float(row.get("ligand_bead2_z", 0.0)),
            ],
            dtype=np.float32,
        )
        out.append(center + b2)
    return np.stack(out, axis=0)


def _onsps_from_smiles(smiles: str) -> Dict[str, int]:
    smi = str(smiles or "").strip()
    if (not smi) or (Chem is None):
        return {"o": 0, "n": 0, "p": 0, "s": 0}
    try:
        mol = Chem.MolFromSmiles(smi)
        if mol is None:
            return {"o": 0, "n": 0, "p": 0, "s": 0}
        out = {"o": 0, "n": 0, "p": 0, "s": 0}
        for atom in mol.GetAtoms():
            z = int(atom.GetAtomicNum())
            if z == 8:
                out["o"] += 1
            elif z == 7:
                out["n"] += 1
            elif z == 15:
                out["p"] += 1
            elif z == 16:
                out["s"] += 1
        return out
    except Exception:
        return {"o": 0, "n": 0, "p": 0, "s": 0}


def _find_frames(queue_id: str, trajectory_root: str, trajectory_glob: str) -> List[str]:
    root = str(trajectory_root).strip()
    if not root:
        return []
    g1 = os.path.join(root, str(queue_id), "*.pdb")
    g2 = os.path.join(root, f"{queue_id}_*.pdb")
    out = sorted(glob.glob(g1)) + sorted(glob.glob(g2))
    if trajectory_glob:
        pat = str(trajectory_glob).replace("{queue_id}", str(queue_id))
        out.extend(sorted(glob.glob(pat)))
    uniq = []
    seen = set()
    for p in out:
        ap = os.path.abspath(p)
        if ap in seen:
            continue
        seen.add(ap)
        if os.path.isfile(ap):
            uniq.append(ap)
    return uniq


def _find_npz_bundle(queue_id: str, trajectory_root: str) -> str:
    root = str(trajectory_root).strip()
    if not root:
        return ""
    candidates = [
        os.path.join(root, str(queue_id), "trajectory_ligand.npz"),
        os.path.join(root, f"{queue_id}.npz"),
    ]
    for p in candidates:
        if os.path.isfile(p):
            return os.path.abspath(p)
    sharded = sorted(glob.glob(os.path.join(root, "*", f"{queue_id}.npz")))
    for p in sharded:
        if os.path.isfile(p):
            return os.path.abspath(p)
    return ""


def _load_native_target_coords(target: str, native_path: str = "") -> Dict[str, Any]:
    explicit_path = str(native_path or "").strip()
    if explicit_path:
        explicit_format = _native_source_format(explicit_path)
        if os.path.isfile(explicit_path):
            try:
                if explicit_format == "pdb":
                    parse_result = _parse_pdb_protein_anchor(explicit_path)
                elif explicit_format == "mmcif":
                    parse_result = _parse_mmcif_protein_anchor(explicit_path)
                else:
                    parse_result = {"protein_all": np.zeros((0, 3), dtype=np.float32), "protein_ca": np.zeros((0, 3), dtype=np.float32), "ligand": np.zeros((0, 3), dtype=np.float32)}
                info = _native_target_info_from_structure(
                    target=target,
                    source_path=explicit_path,
                    source_kind=f"explicit_native_{explicit_format or 'structure'}",
                    source_format=explicit_format,
                    explicit_native_path=explicit_path,
                    parse_result=parse_result,
                    source_used_explicit_native_path=True,
                    note=(
                        "Explicit native structure path was used for protein anchor coordinates."
                        if explicit_format
                        else "Explicit native structure path was used, but the file extension is not recognized."
                    ),
                )
                if info["source_available"]:
                    return info
            except Exception as exc:
                explicit_note = f"Explicit native structure parse failed: {exc}"
            else:
                explicit_note = "Explicit native structure path exists but does not contain usable protein anchor coordinates."
        else:
            explicit_note = "Explicit native structure path is missing."
    else:
        explicit_note = ""

    registry_entry = resolve_repo_native_entry(target)
    registry_native_path = str(registry_entry.get("native_pdb_path", "") or "").strip()
    registry_native_format = _native_source_format(registry_native_path)
    if registry_native_path and os.path.isfile(registry_native_path):
        try:
            if registry_native_format == "pdb":
                parse_result = _parse_pdb_protein_anchor(registry_native_path)
            elif registry_native_format == "mmcif":
                parse_result = _parse_mmcif_protein_anchor(registry_native_path)
            else:
                parse_result = {"protein_all": np.zeros((0, 3), dtype=np.float32), "protein_ca": np.zeros((0, 3), dtype=np.float32), "ligand": np.zeros((0, 3), dtype=np.float32)}
            info = _native_target_info_from_structure(
                target=target,
                source_path=registry_native_path,
                source_kind=f"repo_registry_native_{registry_native_format or 'structure'}",
                source_format=registry_native_format,
                explicit_native_path=explicit_path,
                parse_result=parse_result,
                source_used_explicit_native_path=False,
                note="Repo-native registry supplied protein anchor coordinates.",
            )
            if info["source_available"]:
                return info
        except Exception as exc:
            explicit_note = (
                f"{explicit_note} Repo-native registry parse failed: {exc}".strip()
                if explicit_note
                else f"Repo-native registry parse failed: {exc}"
            )

    default_path = os.path.abspath(f"data/native/{str(target).lower()}.pdb")
    c, _ = load_native_structure(str(target))
    if c is not None:
        arr = c.detach().cpu().numpy()
        if arr.ndim == 2 and arr.shape[1] == 3 and arr.shape[0] > 0:
            note = "Repo-local loader fallback supplied protein anchor coordinates."
            if explicit_note:
                note = f"{explicit_note} {note}".strip()
            return {
                "coords": arr.astype(np.float32, copy=False),
                "source_lookup_target": str(target or "").strip(),
                "source_path": default_path if os.path.isfile(default_path) else "",
                "source_kind": "loader_fallback_native_pdb",
                "source_format": "pdb" if os.path.isfile(default_path) else "",
                "source_available": True,
                "source_explicit_native_path": explicit_path,
                "source_requested_explicit_native_path": bool(explicit_path),
                "source_used_explicit_native_path": False,
                "source_is_aligned_for_backmap": True,
                "source_residue_anchor_mode": "ca_only",
                "protein_atom_count": int(arr.shape[0]),
                "protein_ca_count": int(arr.shape[0]),
                "ligand_atom_count": 0,
                "notes": note,
            }

    missing_note = explicit_note or "No native protein structure was available."
    return _empty_native_target_info(target=target, explicit_native_path=explicit_path, note=missing_note)


def _ligand_props(row: Dict[str, Any]) -> Dict[str, float]:
    def _pick_float(*keys: str, default: float) -> float:
        for key in keys:
            raw = row.get(key, None)
            if raw is None:
                continue
            try:
                text = str(raw).strip()
                if not text:
                    continue
                val = float(text)
                if np.isfinite(val):
                    return float(val)
            except Exception:
                continue
        return float(default)

    mw = _pick_float("ligand_mw", "molecular_weight", default=200.0)
    logp = _pick_float("ligand_logp", "logp", default=1.0)
    rot = _pick_float("ligand_rot_bonds", "rot_bonds", default=2.0)
    h_d = _pick_float("ligand_h_donors", "h_donors", default=0.0)
    h_a = _pick_float("ligand_h_acceptors", "h_acceptors", default=0.0)
    o_cnt = int(float(row.get("ligand_o_count", 0) or 0))
    n_cnt = int(float(row.get("ligand_n_count", 0) or 0))
    p_cnt = int(float(row.get("ligand_p_count", 0) or 0))
    s_cnt = int(float(row.get("ligand_s_count", 0) or 0))
    if (o_cnt + n_cnt + p_cnt + s_cnt) <= 0:
        onsps = _onsps_from_smiles(str(row.get("ligand_smiles", "")))
        o_cnt = int(onsps["o"])
        n_cnt = int(onsps["n"])
        p_cnt = int(onsps["p"])
        s_cnt = int(onsps["s"])
    mw_n = min(max((mw - 120.0) / 500.0, 0.0), 1.0)
    logp_n = min(max((logp + 1.5) / 6.5, 0.0), 1.0)
    rot_n = min(max(rot / 12.0, 0.0), 1.0)
    polar_n = min(max((h_d + h_a) / 14.0, 0.0), 1.0)
    onsps_n = min(max((o_cnt + n_cnt + p_cnt + s_cnt) / 20.0, 0.0), 1.0)
    affinity_hint = float(0.35 * mw_n + 0.35 * logp_n + 0.15 * rot_n + 0.15 * polar_n)
    return {
        "mw": float(mw),
        "logp": float(logp),
        "rot_bonds": float(rot),
        "h_donors": float(h_d),
        "h_acceptors": float(h_a),
        "mw_norm": float(mw_n),
        "logp_norm": float(logp_n),
        "rot_norm": float(rot_n),
        "polar_norm": float(polar_n),
        "onsps_norm": float(onsps_n),
        "o_count": int(o_cnt),
        "n_count": int(n_cnt),
        "p_count": int(p_cnt),
        "s_count": int(s_cnt),
        "affinity_hint": float(affinity_hint),
    }


def _virtual_third_bead(ligand_xyz: np.ndarray) -> np.ndarray:
    lig = np.asarray(ligand_xyz, dtype=np.float32)
    if lig.ndim != 2 or lig.shape[1] != 3 or lig.shape[0] <= 0:
        return lig
    if lig.shape[0] >= 3:
        return lig
    if lig.shape[0] == 1:
        return np.concatenate([lig, lig + np.asarray([[0.7, 0.0, 0.0], [0.0, 0.7, 0.0]], dtype=np.float32)], axis=0)
    a = lig[0]
    b = lig[1]
    mid = 0.5 * (a + b)
    axis = b - a
    ax_n = float(np.linalg.norm(axis))
    if ax_n <= 1e-6:
        axis = np.asarray([1.0, 0.0, 0.0], dtype=np.float32)
        ax_n = 1.0
    axis = axis / ax_n
    perp = np.cross(axis, np.asarray([0.0, 0.0, 1.0], dtype=np.float32))
    pn = float(np.linalg.norm(perp))
    if pn <= 1e-6:
        perp = np.cross(axis, np.asarray([0.0, 1.0, 0.0], dtype=np.float32))
        pn = float(np.linalg.norm(perp))
    if pn <= 1e-6:
        perp = np.asarray([0.0, 1.0, 0.0], dtype=np.float32)
        pn = 1.0
    perp = perp / pn
    c = mid + 0.7 * perp
    return np.stack([a, b, c], axis=0)


def _frame_mmpbsa_proxy(
    protein_xyz: np.ndarray,
    ligand_xyz: np.ndarray,
    props: Dict[str, float],
    contact_cutoff_A: float,
    ligand_model: str = "2bead",
    hbond_onsps_weight: float = 1.0,
) -> Dict[str, float]:
    prot = np.asarray(protein_xyz, dtype=np.float32)
    lig = np.asarray(ligand_xyz, dtype=np.float32)
    model = str(ligand_model).strip().lower()
    if model == "3bead_implicit_hbond":
        lig = _virtual_third_bead(lig)
    if prot.size == 0 or lig.size == 0:
        return {
            "min_distance_A": 999.0,
            "contact_fraction": 0.0,
            "contact_count": 0.0,
            "close_contact_count": 0.0,
            "clash_count": 0.0,
            "deltaG_mmpbsa_proxy_kcal_mol": 5.0,
            "e_vdw": 0.0,
            "e_polar": 0.0,
            "e_nonpolar": 0.0,
            "e_solvation": 5.0,
        }

    d = np.linalg.norm(prot[:, None, :] - lig[None, :, :], axis=2)
    min_d = float(np.min(d))
    denom = float(max(int(d.size), 1))
    contacts = float(np.sum(d < float(contact_cutoff_A)))
    close_contacts = float(np.sum(d < 4.5))
    if model == "3bead_implicit_hbond":
        hb_core = np.exp(-((d - 2.9) / 0.45) ** 2)
        hb_contacts = float(np.sum(hb_core))
    else:
        hb_contacts = float(np.sum(d < 3.6))
    clashes = float(np.sum(d < 2.1))
    contact_fraction = float(contacts / denom)

    affinity = float(props.get("affinity_hint", 0.5))
    polar_n = float(props.get("polar_norm", 0.0))
    logp_n = float(props.get("logp_norm", 0.0))
    onsps_n = float(props.get("onsps_norm", 0.0))

    # MM/PBSA-like proxy:
    #   - e_vdw, e_nonpolar lower when stable hydrophobic packing persists
    #   - e_polar lower with donor/acceptor enriched close contacts
    #   - e_solvation penalizes solvent-exposed weak-contact states
    e_vdw = (
        -(0.015 + 0.05 * affinity) * contacts
        -(0.03 + 0.07 * affinity) * close_contacts
        + (0.22 + 0.05 * (1.0 - affinity)) * clashes
    )
    if model == "3bead_implicit_hbond":
        e_polar = -(0.02 + 0.05 * polar_n + float(hbond_onsps_weight) * 0.05 * onsps_n) * hb_contacts
    else:
        e_polar = -(0.02 + 0.04 * polar_n) * hb_contacts
    e_nonpolar = -(0.01 + 0.06 * logp_n) * contacts
    e_solv = 0.12 * max(0.0, min_d - 4.0) + 0.35 * max(0.0, 0.20 - contact_fraction)
    if model == "3bead_implicit_hbond":
        unsat = max(0.0, (0.25 + 0.35 * polar_n) - contact_fraction)
        e_solv += 0.25 * (1.0 + float(hbond_onsps_weight) * onsps_n) * unsat
    delta_g = float(e_vdw + e_polar + e_nonpolar + e_solv)
    return {
        "min_distance_A": float(min_d),
        "contact_fraction": float(contact_fraction),
        "contact_count": float(contacts),
        "close_contact_count": float(close_contacts),
        "clash_count": float(clashes),
        "deltaG_mmpbsa_proxy_kcal_mol": float(delta_g),
        "e_vdw": float(e_vdw),
        "e_polar": float(e_polar),
        "e_nonpolar": float(e_nonpolar),
        "e_solvation": float(e_solv),
    }


def _model_ligand_xyz(ligand_xyz: np.ndarray, ligand_model: str) -> np.ndarray:
    lig = np.asarray(ligand_xyz, dtype=np.float32)
    if str(ligand_model).strip().lower() == "3bead_implicit_hbond":
        return _virtual_third_bead(lig)
    return lig


def _closest_distance_pair(
    protein_xyz: np.ndarray,
    ligand_xyz: np.ndarray,
) -> tuple[float, np.ndarray, np.ndarray]:
    prot = np.asarray(protein_xyz, dtype=np.float32)
    lig = np.asarray(ligand_xyz, dtype=np.float32)
    if prot.size == 0 or lig.size == 0:
        zero = np.zeros(3, dtype=np.float32)
        return 999.0, zero, zero
    delta = lig[None, :, :] - prot[:, None, :]
    d = np.linalg.norm(delta, axis=2)
    flat_idx = int(np.argmin(d))
    prot_idx, lig_idx = np.unravel_index(flat_idx, d.shape)
    return float(d[prot_idx, lig_idx]), prot[prot_idx], lig[lig_idx]


def _relieve_ligand_clashes(
    protein_xyz: np.ndarray,
    ligand_xyz: np.ndarray,
    *,
    ligand_model: str,
    target_min_distance_A: float,
    max_translation_A: float,
    max_steps: int,
) -> tuple[np.ndarray, dict[str, Any]]:
    prot = np.asarray(protein_xyz, dtype=np.float32)
    lig = np.asarray(ligand_xyz, dtype=np.float32).copy()
    if prot.size == 0 or lig.size == 0:
        return lig, {
            "applied": False,
            "initial_min_distance_A": 999.0,
            "repaired_min_distance_A": 999.0,
            "translation_norm_A": 0.0,
            "step_count": 0,
        }

    target = float(max(0.0, target_min_distance_A))
    max_translation = float(max(0.0, max_translation_A))
    steps = int(max(0, max_steps))
    model_lig = _model_ligand_xyz(lig, ligand_model)
    initial_min, _, _ = _closest_distance_pair(prot, model_lig)
    total_shift = np.zeros(3, dtype=np.float32)
    step_count = 0

    for _ in range(steps):
        model_lig = _model_ligand_xyz(lig, ligand_model)
        min_d, prot_atom, lig_atom = _closest_distance_pair(prot, model_lig)
        if min_d >= target or max_translation <= 0.0:
            break
        direction = lig_atom - prot_atom
        norm = float(np.linalg.norm(direction))
        if norm <= 1e-6:
            direction = np.mean(lig, axis=0) - np.mean(prot, axis=0)
            norm = float(np.linalg.norm(direction))
        if norm <= 1e-6:
            direction = np.asarray([1.0, 0.0, 0.0], dtype=np.float32)
            norm = 1.0
        direction = direction / norm
        remaining = max(0.0, max_translation - float(np.linalg.norm(total_shift)))
        if remaining <= 1e-6:
            break
        # Move the entire ligand gently; this preserves internal geometry while
        # removing impossible close contacts before the same proxy is recomputed.
        step = min(max(target - min_d, 0.0), remaining, 0.35)
        if step <= 1e-6:
            break
        shift = (direction * float(step)).astype(np.float32)
        lig = lig + shift
        total_shift = total_shift + shift
        step_count += 1

    repaired_min, _, _ = _closest_distance_pair(prot, _model_ligand_xyz(lig, ligand_model))
    return lig, {
        "applied": bool(step_count > 0),
        "initial_min_distance_A": float(initial_min),
        "repaired_min_distance_A": float(repaired_min),
        "translation_norm_A": float(np.linalg.norm(total_shift)),
        "step_count": int(step_count),
    }


def _residue_name(i: int) -> str:
    names = [
        "GLY",
        "ALA",
        "VAL",
        "LEU",
        "SER",
        "THR",
        "ASN",
        "GLN",
        "LYS",
        "ARG",
    ]
    return names[i % len(names)]


def _to_pdb_atom(
    serial: int,
    atom_name: str,
    res_name: str,
    chain_id: str,
    res_seq: int,
    xyz: Sequence[float],
    element: str,
) -> str:
    x, y, z = float(xyz[0]), float(xyz[1]), float(xyz[2])
    return (
        f"ATOM  {serial:5d} {atom_name:<4s}{res_name:>3s} {chain_id:1s}{res_seq:4d}    "
        f"{x:8.3f}{y:8.3f}{z:8.3f}{1.00:6.2f}{30.0:6.2f}          {element:>2s}"
    )


def _pseudo_backmap(protein_ca: np.ndarray, ligand_xyz: np.ndarray, out_pdb: str) -> Dict[str, int]:
    protein = np.asarray(protein_ca, dtype=np.float32)
    ligand = np.asarray(ligand_xyz, dtype=np.float32)
    lines: List[str] = ["REMARK PSEUDO BACKMAPPED ALL-ATOM MODEL", "MODEL        1"]
    serial = 1
    n_res = int(protein.shape[0])
    for i in range(n_res):
        ca = protein[i]
        prev_ca = protein[i - 1] if i > 0 else ca + np.asarray([-1.2, 0.0, 0.0], dtype=np.float32)
        nxt_ca = protein[i + 1] if i + 1 < n_res else ca + np.asarray([1.2, 0.0, 0.0], dtype=np.float32)
        tangent = nxt_ca - prev_ca
        tnorm = float(np.linalg.norm(tangent))
        if tnorm <= 1e-6:
            tangent = np.asarray([1.0, 0.0, 0.0], dtype=np.float32)
            tnorm = 1.0
        tangent = tangent / tnorm
        normal = np.asarray([-tangent[1], tangent[0], 0.4], dtype=np.float32)
        nnorm = float(np.linalg.norm(normal))
        if nnorm <= 1e-6:
            normal = np.asarray([0.0, 1.0, 0.0], dtype=np.float32)
            nnorm = 1.0
        normal = normal / nnorm

        n_atom = ca - 1.22 * tangent
        c_atom = ca + 1.33 * tangent
        o_atom = c_atom + 0.98 * normal
        cb_atom = ca + 1.52 * normal
        resn = _residue_name(i)
        resi = i + 1
        for atom_name, xyz, element in (
            ("N", n_atom, "N"),
            ("CA", ca, "C"),
            ("C", c_atom, "C"),
            ("O", o_atom, "O"),
            ("CB", cb_atom, "C"),
        ):
            lines.append(_to_pdb_atom(serial, atom_name, resn, "A", resi, xyz, element))
            serial += 1

    lines.append("TER")
    for i in range(int(ligand.shape[0])):
        xyz = ligand[i]
        atom_name = f"C{i+1}"
        lines.append(_to_pdb_atom(serial, atom_name, "LIG", "L", 1, xyz, "C"))
        serial += 1
    lines.append("ENDMDL")
    lines.append("END")

    _ensure_dir(os.path.dirname(out_pdb) or ".")
    with open(out_pdb, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return {
        "protein_residues": int(n_res),
        "protein_atoms": int(n_res * 5),
        "ligand_atoms": int(ligand.shape[0]),
    }


def _score_frames(
    frame_paths: List[str],
    trajectory_npz_path: str,
    protein_default: np.ndarray,
    ligand_default: np.ndarray,
    contact_cutoff_A: float,
    row: Dict[str, Any],
    min_frames: int,
    ligand_model: str,
    hbond_onsps_weight: float,
    clash_relief_mode: str = "off",
    clash_relief_target_min_distance_A: float = 2.12,
    clash_relief_max_translation_A: float = 2.0,
    clash_relief_max_steps: int = 12,
) -> Dict[str, Any]:
    min_dists: List[float] = []
    contact_fracs: List[float] = []
    contact_counts: List[float] = []
    close_contact_counts: List[float] = []
    clash_counts: List[float] = []
    frame_energy: List[float] = []
    e_vdw: List[float] = []
    e_polar: List[float] = []
    e_nonpolar: List[float] = []
    e_solv: List[float] = []
    pre_repair_min_dists: List[float] = []
    pre_repair_frame_energy: List[float] = []
    pre_repair_clash_counts: List[float] = []
    pre_repair_e_vdw: List[float] = []
    clash_relief_translations: List[float] = []
    clash_relief_applied: List[bool] = []
    representative_ligand_xyz: np.ndarray | None = None
    frame_count = 0
    frame_with_ligand = 0
    props = _ligand_props(row)
    relief_mode = str(clash_relief_mode or "off").strip().lower()
    relief_enabled = relief_mode not in {"", "off", "none", "disabled", "false", "0"}

    def _score_one_frame(prot_xyz: np.ndarray, lig_xyz: np.ndarray) -> Dict[str, float]:
        nonlocal representative_ligand_xyz
        prot_arr = np.asarray(prot_xyz, dtype=np.float32)
        lig_arr = np.asarray(lig_xyz, dtype=np.float32)
        scored_lig = lig_arr
        if relief_enabled:
            pre_ff = _frame_mmpbsa_proxy(
                protein_xyz=prot_arr,
                ligand_xyz=lig_arr,
                props=props,
                contact_cutoff_A=float(contact_cutoff_A),
                ligand_model=str(ligand_model),
                hbond_onsps_weight=float(hbond_onsps_weight),
            )
            scored_lig, repair_meta = _relieve_ligand_clashes(
                protein_xyz=prot_arr,
                ligand_xyz=lig_arr,
                ligand_model=str(ligand_model),
                target_min_distance_A=float(clash_relief_target_min_distance_A),
                max_translation_A=float(clash_relief_max_translation_A),
                max_steps=int(clash_relief_max_steps),
            )
            pre_repair_min_dists.append(float(pre_ff["min_distance_A"]))
            pre_repair_frame_energy.append(float(pre_ff["deltaG_mmpbsa_proxy_kcal_mol"]))
            pre_repair_clash_counts.append(float(pre_ff["clash_count"]))
            pre_repair_e_vdw.append(float(pre_ff["e_vdw"]))
            clash_relief_translations.append(float(repair_meta.get("translation_norm_A", 0.0)))
            clash_relief_applied.append(bool(repair_meta.get("applied", False)))
        ff = _frame_mmpbsa_proxy(
            protein_xyz=prot_arr,
            ligand_xyz=scored_lig,
            props=props,
            contact_cutoff_A=float(contact_cutoff_A),
            ligand_model=str(ligand_model),
            hbond_onsps_weight=float(hbond_onsps_weight),
        )
        if representative_ligand_xyz is None or (relief_enabled and clash_relief_applied and clash_relief_applied[-1]):
            representative_ligand_xyz = np.asarray(scored_lig, dtype=np.float32)
        return ff

    npz_src = str(trajectory_npz_path).strip()
    if npz_src and os.path.exists(npz_src):
        try:
            with np.load(npz_src, allow_pickle=False) as bundle:
                lig_frames = np.asarray(bundle.get("ligand_frames", np.zeros((0, 0, 3), dtype=np.float32)), dtype=np.float32)
                prot_npz = np.asarray(bundle.get("protein_ca", np.zeros((0, 3), dtype=np.float32)), dtype=np.float32)
            if lig_frames.ndim == 2 and lig_frames.shape[1] == 3:
                lig_frames = lig_frames.reshape(1, lig_frames.shape[0], 3)
            if lig_frames.ndim == 3 and lig_frames.shape[2] == 3 and lig_frames.shape[0] > 0:
                prot = prot_npz if (prot_npz.ndim == 2 and prot_npz.shape[1] == 3 and prot_npz.shape[0] > 0) else protein_default
                for i in range(int(lig_frames.shape[0])):
                    lig = lig_frames[i]
                    frame_count += 1
                    if lig.size > 0:
                        frame_with_ligand += 1
                    ff = _score_one_frame(prot, lig)
                    min_dists.append(float(ff["min_distance_A"]))
                    contact_fracs.append(float(ff["contact_fraction"]))
                    contact_counts.append(float(ff["contact_count"]))
                    close_contact_counts.append(float(ff["close_contact_count"]))
                    clash_counts.append(float(ff["clash_count"]))
                    frame_energy.append(float(ff["deltaG_mmpbsa_proxy_kcal_mol"]))
                    e_vdw.append(float(ff["e_vdw"]))
                    e_polar.append(float(ff["e_polar"]))
                    e_nonpolar.append(float(ff["e_nonpolar"]))
                    e_solv.append(float(ff["e_solvation"]))
        except Exception:
            # Fall back to per-frame PDB parsing below.
            frame_count = 0
            frame_with_ligand = 0
            min_dists = []
            contact_fracs = []
            contact_counts = []
            close_contact_counts = []
            clash_counts = []
            frame_energy = []
            e_vdw = []
            e_polar = []
            e_nonpolar = []
            e_solv = []

    if frame_count <= 0:
        for fp in frame_paths:
            prot, lig = _parse_pdb_coords(fp)
            if prot.size == 0:
                prot = protein_default
            if lig.size == 0:
                lig = ligand_default
            frame_count += 1
            if lig.size > 0:
                frame_with_ligand += 1
            ff = _score_one_frame(prot, lig)
            min_dists.append(float(ff["min_distance_A"]))
            contact_fracs.append(float(ff["contact_fraction"]))
            contact_counts.append(float(ff["contact_count"]))
            close_contact_counts.append(float(ff["close_contact_count"]))
            clash_counts.append(float(ff["clash_count"]))
            frame_energy.append(float(ff["deltaG_mmpbsa_proxy_kcal_mol"]))
            e_vdw.append(float(ff["e_vdw"]))
            e_polar.append(float(ff["e_polar"]))
            e_nonpolar.append(float(ff["e_nonpolar"]))
            e_solv.append(float(ff["e_solvation"]))

    if frame_count <= 0:
        if protein_default.size > 0 and ligand_default.size > 0:
            ff = _score_one_frame(protein_default, ligand_default)
            min_d = float(ff["min_distance_A"])
            cfrac = float(ff["contact_fraction"])
            contact_cnt = float(ff["contact_count"])
            close_contact_cnt = float(ff["close_contact_count"])
            clash_cnt = float(ff["clash_count"])
            dG = float(ff["deltaG_mmpbsa_proxy_kcal_mol"])
            vv = float(ff["e_vdw"])
            pp = float(ff["e_polar"])
            nn = float(ff["e_nonpolar"])
            ss = float(ff["e_solvation"])
        else:
            min_d = 999.0
            cfrac = 0.0
            contact_cnt = 0.0
            close_contact_cnt = 0.0
            clash_cnt = 0.0
            dG = 5.0
            vv = 0.0
            pp = 0.0
            nn = 0.0
            ss = 5.0
        min_dists = [min_d]
        contact_fracs = [cfrac]
        contact_counts = [contact_cnt]
        close_contact_counts = [close_contact_cnt]
        clash_counts = [clash_cnt]
        frame_energy = [dG]
        e_vdw = [vv]
        e_polar = [pp]
        e_nonpolar = [nn]
        e_solv = [ss]
        frame_count = 1
        frame_with_ligand = 1 if ligand_default.size > 0 else 0

    if int(frame_count) < int(min_frames):
        raise ValueError(f"insufficient trajectory frames: {frame_count} < min_frames={int(min_frames)}")

    arr = np.asarray(min_dists, dtype=np.float64)
    c_arr = np.asarray(contact_fracs, dtype=np.float64)
    cc_arr = np.asarray(contact_counts, dtype=np.float64)
    close_arr = np.asarray(close_contact_counts, dtype=np.float64)
    clash_arr = np.asarray(clash_counts, dtype=np.float64)
    g_arr = np.asarray(frame_energy, dtype=np.float64)
    vv_arr = np.asarray(e_vdw, dtype=np.float64)
    pp_arr = np.asarray(e_polar, dtype=np.float64)
    nn_arr = np.asarray(e_nonpolar, dtype=np.float64)
    ss_arr = np.asarray(e_solv, dtype=np.float64)
    contact = arr < float(contact_cutoff_A)
    contact_fraction = float(np.mean(c_arr)) if c_arr.size > 0 else float(np.mean(contact))
    mean_min_distance = float(np.mean(arr))
    std_min_distance = float(np.std(arr))
    frame_contact_fraction_std = float(np.std(c_arr)) if c_arr.size > 0 else 0.0
    stability_score = float(contact_fraction / (1.0 + std_min_distance))
    dg_mean = float(np.mean(g_arr))
    dg_std = float(np.std(g_arr))
    mean_e_vdw = float(np.mean(vv_arr))
    mean_e_polar = float(np.mean(pp_arr))
    mean_e_nonpolar = float(np.mean(nn_arr))
    mean_e_solvation = float(np.mean(ss_arr))
    favorable_energy_proxy = float(-(mean_e_vdw + mean_e_polar + mean_e_nonpolar))
    solvation_penalty_proxy = float(max(mean_e_solvation, 0.0))
    vdw_nonpolar_support_proxy = float(-(mean_e_vdw + mean_e_nonpolar))
    polar_support_proxy = float(-mean_e_polar)
    physics_net_support_proxy = float(favorable_energy_proxy - solvation_penalty_proxy)
    physics_contact_stability_proxy = float(contact_fraction * stability_score)
    pre_arr = np.asarray(pre_repair_min_dists, dtype=np.float64)
    pre_g_arr = np.asarray(pre_repair_frame_energy, dtype=np.float64)
    pre_clash_arr = np.asarray(pre_repair_clash_counts, dtype=np.float64)
    pre_vdw_arr = np.asarray(pre_repair_e_vdw, dtype=np.float64)
    relief_translation_arr = np.asarray(clash_relief_translations, dtype=np.float64)
    relief_applied_arr = np.asarray(clash_relief_applied, dtype=bool)
    representative_ligand = (
        representative_ligand_xyz.astype(float).tolist()
        if isinstance(representative_ligand_xyz, np.ndarray) and representative_ligand_xyz.ndim == 2
        else np.asarray(ligand_default, dtype=np.float32).astype(float).tolist()
    )
    return {
        "frame_count": int(frame_count),
        "frame_with_ligand_count": int(frame_with_ligand),
        "trajectory_ligand_presence_fraction": float(frame_with_ligand / max(int(frame_count), 1)),
        "contact_fraction": contact_fraction,
        "frame_contact_fraction_std": frame_contact_fraction_std,
        "frame_contact_presence_fraction": float(np.mean(contact)) if contact.size > 0 else 0.0,
        "frame_close_contact_presence_fraction": float(np.mean(close_arr > 0.0)) if close_arr.size > 0 else 0.0,
        "clash_frame_fraction": float(np.mean(clash_arr > 0.0)) if clash_arr.size > 0 else 0.0,
        "contact_count_mean_per_frame": float(np.mean(cc_arr)) if cc_arr.size > 0 else 0.0,
        "close_contact_count_mean_per_frame": float(np.mean(close_arr)) if close_arr.size > 0 else 0.0,
        "clash_count_mean_per_frame": float(np.mean(clash_arr)) if clash_arr.size > 0 else 0.0,
        "mean_min_distance_A": mean_min_distance,
        "std_min_distance_A": std_min_distance,
        "distance_sem_A": _safe_sem(std_min_distance, int(frame_count)),
        "min_distance_p10_A": _nan_percentile(arr, 10.0),
        "min_distance_p50_A": _nan_percentile(arr, 50.0),
        "min_distance_p90_A": _nan_percentile(arr, 90.0),
        "stability_score": stability_score,
        "binding_energy_proxy": dg_mean,
        "binding_energy_mmpbsa_kcal_mol_proxy": dg_mean,
        "binding_energy_mmpbsa_std": dg_std,
        "binding_energy_mmpbsa_sem": _safe_sem(dg_std, int(frame_count)),
        "binding_energy_mmpbsa_p10_kcal_mol_proxy": _nan_percentile(g_arr, 10.0),
        "binding_energy_mmpbsa_p50_kcal_mol_proxy": _nan_percentile(g_arr, 50.0),
        "binding_energy_mmpbsa_p90_kcal_mol_proxy": _nan_percentile(g_arr, 90.0),
        "contact_fraction_p10": _nan_percentile(c_arr, 10.0),
        "contact_fraction_p50": _nan_percentile(c_arr, 50.0),
        "contact_fraction_p90": _nan_percentile(c_arr, 90.0),
        "mean_e_vdw": mean_e_vdw,
        "mean_e_polar": mean_e_polar,
        "mean_e_nonpolar": mean_e_nonpolar,
        "mean_e_solvation": mean_e_solvation,
        "physics_favorable_energy_proxy": favorable_energy_proxy,
        "physics_net_support_proxy": physics_net_support_proxy,
        "physics_contact_stability_proxy": physics_contact_stability_proxy,
        "vdw_nonpolar_support_proxy": vdw_nonpolar_support_proxy,
        "polar_support_proxy": polar_support_proxy,
        "solvation_penalty_proxy": solvation_penalty_proxy,
        "clash_relief_mode": relief_mode if relief_enabled else "off",
        "clash_relief_enabled": bool(relief_enabled),
        "clash_relief_target_min_distance_A": float(clash_relief_target_min_distance_A) if relief_enabled else None,
        "clash_relief_max_translation_A": float(clash_relief_max_translation_A) if relief_enabled else None,
        "clash_relief_max_steps": int(clash_relief_max_steps) if relief_enabled else None,
        "clash_relief_applied_frame_count": int(np.sum(relief_applied_arr)) if relief_enabled else 0,
        "clash_relief_frame_fraction": (
            float(np.mean(relief_applied_arr)) if relief_enabled and relief_applied_arr.size > 0 else 0.0
        ),
        "clash_relief_mean_translation_A": (
            float(np.mean(relief_translation_arr)) if relief_enabled and relief_translation_arr.size > 0 else 0.0
        ),
        "pre_repair_binding_energy_proxy": (
            float(np.mean(pre_g_arr)) if relief_enabled and pre_g_arr.size > 0 else None
        ),
        "pre_repair_mean_min_distance_A": (
            float(np.mean(pre_arr)) if relief_enabled and pre_arr.size > 0 else None
        ),
        "pre_repair_clash_frame_fraction": (
            float(np.mean(pre_clash_arr > 0.0)) if relief_enabled and pre_clash_arr.size > 0 else None
        ),
        "pre_repair_mean_e_vdw": (
            float(np.mean(pre_vdw_arr)) if relief_enabled and pre_vdw_arr.size > 0 else None
        ),
        "representative_ligand_xyz": representative_ligand,
        "min_distance_A": float(np.min(arr)),
        "max_distance_A": float(np.max(arr)),
        "ligand_affinity_hint": float(props.get("affinity_hint", 0.0)),
        "ligand_onsps_norm": float(props.get("onsps_norm", 0.0)),
        "ligand_mw": float(props.get("mw", 0.0)),
        "ligand_logp": float(props.get("logp", 0.0)),
        "ligand_rot_bonds": float(props.get("rot_bonds", 0.0)),
        "ligand_h_donors": float(props.get("h_donors", 0.0)),
        "ligand_h_acceptors": float(props.get("h_acceptors", 0.0)),
        "ligand_model": str(ligand_model),
    }


def _feature_vector_from_scores(df: pd.DataFrame, feature_names: Sequence[str]) -> np.ndarray:
    out_cols: List[np.ndarray] = []
    for name in feature_names:
        col = str(name)
        if col in df.columns:
            arr = pd.to_numeric(df[col], errors="coerce").fillna(0.0).to_numpy(dtype=np.float32, copy=False)
        else:
            arr = np.zeros((len(df),), dtype=np.float32)
        out_cols.append(arr.reshape(-1, 1))
    if not out_cols:
        return np.zeros((len(df), 0), dtype=np.float32)
    return np.concatenate(out_cols, axis=1).astype(np.float32, copy=False)


def _apply_aux_binding_model(
    df: pd.DataFrame,
    checkpoint_path: str,
    aux_score_weight: float,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    src = str(checkpoint_path).strip()
    if (not src) or (not os.path.exists(src)) or df.empty:
        return df, {"applied": False, "reason": "checkpoint_missing_or_empty"}
    payload = torch.load(src, map_location="cpu")
    state = payload.get("state_dict", payload)
    feature_names = [str(x) for x in payload.get("feature_names", [])]
    hidden_dim = int(payload.get("hidden_dim", 64) or 64)
    if not feature_names:
        return df, {"applied": False, "reason": "missing_feature_names"}
    model = _AuxMLP(in_dim=len(feature_names), hidden_dim=hidden_dim)
    model.load_state_dict(state, strict=False)
    model.eval()
    x = _feature_vector_from_scores(df, feature_names)
    with torch.no_grad():
        logits = model(torch.from_numpy(x)).detach().cpu().numpy().astype(np.float32, copy=False)
    probs = 1.0 / (1.0 + np.exp(-logits))
    df = df.copy()
    df["aux_binding_score_logit"] = logits
    df["aux_binding_score_prob"] = probs
    mu = float(np.mean(probs)) if len(probs) > 0 else 0.0
    sd = float(np.std(probs)) if len(probs) > 0 else 1.0
    if (not np.isfinite(sd)) or sd <= 1e-12:
        sd = 1.0
    z_aux = (probs - mu) / sd
    if "binding_score_composite_v4" in df.columns:
        df["binding_score_composite_v5"] = pd.to_numeric(df["binding_score_composite_v4"], errors="coerce").fillna(0.0) - float(aux_score_weight) * z_aux
    return df, {
        "applied": True,
        "checkpoint": os.path.abspath(src),
        "feature_dim": int(len(feature_names)),
        "hidden_dim": int(hidden_dim),
        "aux_score_weight": float(aux_score_weight),
        "prob_mean": float(mu),
        "prob_std": float(sd),
    }


def _balanced_sample_by_target(df: pd.DataFrame, max_jobs: int) -> pd.DataFrame:
    if int(max_jobs) <= 0 or len(df) <= int(max_jobs):
        return df
    if "target" not in df.columns:
        return df.head(int(max_jobs)).copy()
    groups = [g.copy() for _, g in df.groupby("target", sort=False)]
    if len(groups) <= 1:
        return df.head(int(max_jobs)).copy()
    base = int(max_jobs) // len(groups)
    rem = int(max_jobs) % len(groups)
    chunks: List[pd.DataFrame] = []
    for i, g in enumerate(groups):
        take = int(base + (1 if i < rem else 0))
        if take > 0:
            chunks.append(g.head(take))
    out = pd.concat(chunks, axis=0, ignore_index=True)
    if len(out) < int(max_jobs):
        # Fill remaining slots from tail while preserving order.
        used = set(out.get("queue_id", pd.Series(dtype=str)).astype(str).tolist())
        add_rows = []
        for _, row in df.iterrows():
            qid = str(row.get("queue_id", ""))
            if qid in used:
                continue
            add_rows.append(row)
            used.add(qid)
            if len(out) + len(add_rows) >= int(max_jobs):
                break
        if add_rows:
            out = pd.concat([out, pd.DataFrame(add_rows)], axis=0, ignore_index=True)
    return out.head(int(max_jobs)).copy()


def _parse_csv_list(text: str) -> List[str]:
    return [s.strip() for s in str(text or "").split(",") if s.strip()]


def _priority_sample_by_split(
    df: pd.DataFrame,
    max_jobs: int,
    split_csv: str,
    priority_roles: str,
    split_role_col: str,
    split_target_col: str,
    split_ligand_col: str,
    balance_targets_for_max_jobs: bool,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    stats: Dict[str, Any] = {
        "enabled": False,
        "applied": False,
        "split_csv": str(split_csv or ""),
        "priority_roles": _parse_csv_list(priority_roles),
        "priority_key_total": 0,
        "priority_rows_selected": 0,
        "priority_rows_in_queue": 0,
        "fallback_rows_selected": 0,
        "error": "",
    }
    if int(max_jobs) <= 0:
        return df, stats
    split_path = str(split_csv or "").strip()
    roles = stats["priority_roles"]
    if (not split_path) or (not os.path.exists(split_path)) or (not roles):
        return df, stats
    if ("target" not in df.columns) or ("ligand_id" not in df.columns):
        stats["error"] = "queue missing required columns(target, ligand_id)"
        return df, stats
    try:
        sdf = pd.read_csv(split_path)
    except Exception as e:
        stats["error"] = f"failed to read split csv: {e}"
        return df, stats
    for col in (split_role_col, split_target_col, split_ligand_col):
        if col not in sdf.columns:
            stats["error"] = f"split missing column: {col}"
            return df, stats

    stats["enabled"] = True
    sdf = sdf[sdf[split_role_col].astype(str).isin(roles)].copy()
    if sdf.empty:
        stats["error"] = "no split rows matched priority roles"
        return df, stats

    priority_keys = set(
        zip(
            sdf[split_target_col].astype(str).tolist(),
            sdf[split_ligand_col].astype(str).tolist(),
        )
    )
    stats["priority_key_total"] = int(len(priority_keys))
    queue_keys = list(zip(df["target"].astype(str).tolist(), df["ligand_id"].astype(str).tolist()))
    mask = pd.Series([k in priority_keys for k in queue_keys], index=df.index)

    priority_df = df[mask].copy()
    non_priority_df = df[~mask].copy()
    stats["priority_rows_in_queue"] = int(len(priority_df))
    if len(priority_df) >= int(max_jobs):
        if bool(balance_targets_for_max_jobs):
            out = _balanced_sample_by_target(priority_df, max_jobs=int(max_jobs))
        else:
            out = priority_df.head(int(max_jobs)).copy()
        stats["applied"] = True
        stats["priority_rows_selected"] = int(len(out))
        return out, stats

    remain = int(max_jobs) - int(len(priority_df))
    if bool(balance_targets_for_max_jobs):
        tail = _balanced_sample_by_target(non_priority_df, max_jobs=remain)
    else:
        tail = non_priority_df.head(remain).copy()
    out = pd.concat([priority_df, tail], axis=0, ignore_index=True).head(int(max_jobs)).copy()
    stats["applied"] = True
    stats["priority_rows_selected"] = int(len(priority_df))
    stats["fallback_rows_selected"] = int(max(0, len(out) - len(priority_df)))
    return out, stats


def _inline_score_from_row(row: Dict[str, Any], ligand_model: str) -> Optional[Dict[str, Any]]:
    if not bool(row.get("inline_aux_available", False)):
        return None
    required = (
        "binding_energy_proxy",
        "binding_energy_mmpbsa_kcal_mol_proxy",
        "binding_energy_mmpbsa_std",
        "stability_score",
        "contact_fraction",
        "mean_min_distance_A",
    )
    for key in required:
        if key not in row:
            return None
    frame_count = int(float(row.get("trajectory_frame_count", row.get("sim_frames_count", 0)) or 0))
    props = _ligand_props(row)
    frame_with_ligand = _safe_optional_int(
        row.get("frame_with_ligand_count", row.get("trajectory_frame_with_ligand_count", frame_count))
    )
    if frame_with_ligand is None:
        frame_with_ligand = int(max(frame_count, 0))
    trajectory_presence = _safe_optional_float(row.get("trajectory_ligand_presence_fraction"))
    if trajectory_presence is None and frame_count > 0:
        trajectory_presence = float(frame_with_ligand / max(frame_count, 1))
    return {
        "frame_count": int(max(frame_count, 0)),
        "frame_with_ligand_count": int(max(frame_with_ligand, 0)),
        "trajectory_ligand_presence_fraction": trajectory_presence,
        "contact_fraction": float(row.get("contact_fraction", 0.0) or 0.0),
        "frame_contact_fraction_std": _safe_optional_float(row.get("frame_contact_fraction_std")),
        "frame_contact_presence_fraction": _safe_optional_float(row.get("frame_contact_presence_fraction")),
        "frame_close_contact_presence_fraction": _safe_optional_float(row.get("frame_close_contact_presence_fraction")),
        "clash_frame_fraction": _safe_optional_float(row.get("clash_frame_fraction")),
        "contact_count_mean_per_frame": _safe_optional_float(row.get("contact_count_mean_per_frame")),
        "close_contact_count_mean_per_frame": _safe_optional_float(row.get("close_contact_count_mean_per_frame")),
        "clash_count_mean_per_frame": _safe_optional_float(row.get("clash_count_mean_per_frame")),
        "mean_min_distance_A": float(row.get("mean_min_distance_A", 0.0) or 0.0),
        "std_min_distance_A": float(row.get("std_min_distance_A", 0.0) or 0.0),
        "distance_sem_A": _safe_optional_float(row.get("distance_sem_A")),
        "min_distance_p10_A": _safe_optional_float(row.get("min_distance_p10_A")),
        "min_distance_p50_A": _safe_optional_float(row.get("min_distance_p50_A")),
        "min_distance_p90_A": _safe_optional_float(row.get("min_distance_p90_A")),
        "stability_score": float(row.get("stability_score", 0.0) or 0.0),
        "binding_energy_proxy": float(row.get("binding_energy_proxy", 0.0) or 0.0),
        "binding_energy_mmpbsa_kcal_mol_proxy": float(row.get("binding_energy_mmpbsa_kcal_mol_proxy", 0.0) or 0.0),
        "binding_energy_mmpbsa_std": float(row.get("binding_energy_mmpbsa_std", 0.0) or 0.0),
        "binding_energy_mmpbsa_sem": _safe_optional_float(row.get("binding_energy_mmpbsa_sem")),
        "binding_energy_mmpbsa_p10_kcal_mol_proxy": _safe_optional_float(
            row.get("binding_energy_mmpbsa_p10_kcal_mol_proxy")
        ),
        "binding_energy_mmpbsa_p50_kcal_mol_proxy": _safe_optional_float(
            row.get("binding_energy_mmpbsa_p50_kcal_mol_proxy")
        ),
        "binding_energy_mmpbsa_p90_kcal_mol_proxy": _safe_optional_float(
            row.get("binding_energy_mmpbsa_p90_kcal_mol_proxy")
        ),
        "contact_fraction_p10": _safe_optional_float(row.get("contact_fraction_p10")),
        "contact_fraction_p50": _safe_optional_float(row.get("contact_fraction_p50")),
        "contact_fraction_p90": _safe_optional_float(row.get("contact_fraction_p90")),
        "mean_e_vdw": float(row.get("mean_e_vdw", 0.0) or 0.0),
        "mean_e_polar": float(row.get("mean_e_polar", 0.0) or 0.0),
        "mean_e_nonpolar": float(row.get("mean_e_nonpolar", 0.0) or 0.0),
        "mean_e_solvation": float(row.get("mean_e_solvation", 0.0) or 0.0),
        "physics_favorable_energy_proxy": _safe_optional_float(row.get("physics_favorable_energy_proxy")),
        "physics_net_support_proxy": _safe_optional_float(row.get("physics_net_support_proxy")),
        "physics_contact_stability_proxy": _safe_optional_float(row.get("physics_contact_stability_proxy")),
        "vdw_nonpolar_support_proxy": _safe_optional_float(row.get("vdw_nonpolar_support_proxy")),
        "polar_support_proxy": _safe_optional_float(row.get("polar_support_proxy")),
        "solvation_penalty_proxy": _safe_optional_float(row.get("solvation_penalty_proxy")),
        "min_distance_A": float(row.get("min_min_distance_A", row.get("mean_min_distance_A", 0.0)) or 0.0),
        "max_distance_A": float(row.get("final_min_distance_A", row.get("mean_min_distance_A", 0.0)) or 0.0),
        "ligand_affinity_hint": float(row.get("affinity_hint", row.get("ligand_affinity_hint", 0.0)) or 0.0),
        "ligand_onsps_norm": float(row.get("ligand_onsps_norm", row.get("onsps_norm", 0.0)) or 0.0),
        "ligand_mw": float(props.get("mw", 0.0)),
        "ligand_logp": float(props.get("logp", 0.0)),
        "ligand_rot_bonds": float(props.get("rot_bonds", 0.0)),
        "ligand_h_donors": float(props.get("h_donors", 0.0)),
        "ligand_h_acceptors": float(props.get("h_acceptors", 0.0)),
        "ligand_model": str(row.get("ligand_model", ligand_model) or ligand_model),
    }


def _process_queue_row(row: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    queue_id = str(row.get("queue_id", "")).strip()
    if not queue_id:
        queue_id = f"{str(row.get('target','target')).lower()}__rep{int(row.get('replica_idx', 0)):04d}"
    target = str(row.get("target", "unknown")).strip()
    ligand_id = str(row.get("ligand_id", "ligand")).strip()
    replica_idx = _safe_optional_int(row.get("replica_idx", row.get("replicate_idx")))
    simulation_seed = row.get("simulation_seed", row.get("seed", row.get("random_seed", row.get("trajectory_seed"))))
    if simulation_seed in {"", None}:
        simulation_seed = None
    score_only = bool(cfg.get("score_only", False))
    job_dir = os.path.join(str(cfg["jobs_root"]), queue_id) if (not score_only) else ""
    if job_dir:
        _ensure_dir(job_dir)

    native_info = _load_native_target_coords(target, native_path=str(row.get("native_pdb_path", "")))
    native_ca = np.asarray(native_info.get("coords"), dtype=np.float32)
    ligand_default = _compose_ligand_xyz(row)
    frame_paths = _find_frames(
        queue_id=queue_id,
        trajectory_root=str(cfg["trajectory_root"]),
        trajectory_glob=str(cfg["trajectory_glob"]),
    )
    trajectory_npz = str(row.get("trajectory_npz", "")).strip() or _find_npz_bundle(
        queue_id=queue_id,
        trajectory_root=str(cfg["trajectory_root"]),
    )
    clash_relief_mode = str(cfg.get("clash_relief_mode", "off") or "off").strip().lower()
    clash_relief_enabled = clash_relief_mode not in {"", "off", "none", "disabled", "false", "0"}
    inline_score = None if clash_relief_enabled else _inline_score_from_row(row, ligand_model=str(cfg["ligand_model"]))
    if (inline_score is None) and (not frame_paths) and (not trajectory_npz) and (not bool(cfg["allow_missing_trajectory"])):
        raise FileNotFoundError(f"no frames found for queue_id={queue_id}")

    score = inline_score
    if score is None:
        score = _score_frames(
            frame_paths=frame_paths,
            trajectory_npz_path=trajectory_npz,
            protein_default=native_ca,
            ligand_default=ligand_default,
            contact_cutoff_A=float(cfg["contact_cutoff_A"]),
            row=row,
            min_frames=int(cfg["min_frames"]),
            ligand_model=str(cfg["ligand_model"]),
            hbond_onsps_weight=float(cfg["hbond_onsps_weight"]),
            clash_relief_mode=clash_relief_mode,
            clash_relief_target_min_distance_A=float(cfg.get("clash_relief_target_min_distance_A", 2.12)),
            clash_relief_max_translation_A=float(cfg.get("clash_relief_max_translation_A", 2.0)),
            clash_relief_max_steps=int(cfg.get("clash_relief_max_steps", 12)),
        )

    backmap_pdb = ""
    score_json = ""
    representative_ligand = np.asarray(score.get("representative_ligand_xyz", []), dtype=np.float32)
    if representative_ligand.ndim != 2 or representative_ligand.shape[1] != 3 or representative_ligand.shape[0] <= 0:
        representative_ligand = ligand_default
    backmap_stats: Dict[str, Any] = {
        "protein_residues": int(native_ca.shape[0]) if native_ca.ndim == 2 else 0,
        "protein_atoms": 0,
        "ligand_atoms": int(representative_ligand.shape[0]) if representative_ligand.ndim == 2 else 0,
    }
    if not score_only:
        backmap_pdb = os.path.join(job_dir, f"backmapped_{queue_id}.pdb")
        backmap_stats = _pseudo_backmap(
            protein_ca=native_ca,
            ligand_xyz=representative_ligand,
            out_pdb=backmap_pdb,
        )
        backmapped_contains_protein = bool(int(backmap_stats.get("protein_atoms", 0)) > 0)
        score_json = os.path.join(job_dir, f"score_{queue_id}.json")
        with open(score_json, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "queue_id": queue_id,
                    "target": target,
                    "ligand_id": ligand_id,
                    "score": score,
                    "protein_structure_provenance": {
                        key: value
                        for key, value in native_info.items()
                        if key != "coords"
                    },
                    "backmap_stats": backmap_stats,
                    "backmapped_contains_protein": backmapped_contains_protein,
                    "backmapped_structure_kind": (
                        "pseudo_backmapped_protein_ligand_pdb"
                        if backmapped_contains_protein
                        else "ligand_only_backmapped_pdb"
                    ),
                    "trajectory_frame_count": int(score.get("frame_count", len(frame_paths))),
                    "trajectory_npz": trajectory_npz,
                },
                f,
                indent=2,
                ensure_ascii=False,
            )
    else:
        backmapped_contains_protein = bool(native_ca.ndim == 2 and native_ca.shape[0] > 0)

    result = {
        "queue_id": queue_id,
        "target": target,
        "ligand_id": ligand_id,
        "ligand_smiles": str(row.get("ligand_smiles", row.get("smiles", "")) or ""),
        "replica_idx": replica_idx,
        "simulation_seed": simulation_seed,
        "binding_energy_proxy": float(score["binding_energy_proxy"]),
        "binding_energy_mmpbsa_kcal_mol_proxy": float(score["binding_energy_mmpbsa_kcal_mol_proxy"]),
        "binding_energy_mmpbsa_std": float(score["binding_energy_mmpbsa_std"]),
        "binding_energy_mmpbsa_sem": score.get("binding_energy_mmpbsa_sem"),
        "binding_energy_mmpbsa_p10_kcal_mol_proxy": score.get("binding_energy_mmpbsa_p10_kcal_mol_proxy"),
        "binding_energy_mmpbsa_p50_kcal_mol_proxy": score.get("binding_energy_mmpbsa_p50_kcal_mol_proxy"),
        "binding_energy_mmpbsa_p90_kcal_mol_proxy": score.get("binding_energy_mmpbsa_p90_kcal_mol_proxy"),
        "stability_score": float(score["stability_score"]),
        "contact_fraction": float(score["contact_fraction"]),
        "frame_contact_fraction_std": score.get("frame_contact_fraction_std"),
        "frame_contact_presence_fraction": score.get("frame_contact_presence_fraction"),
        "frame_close_contact_presence_fraction": score.get("frame_close_contact_presence_fraction"),
        "clash_frame_fraction": score.get("clash_frame_fraction"),
        "contact_count_mean_per_frame": score.get("contact_count_mean_per_frame"),
        "close_contact_count_mean_per_frame": score.get("close_contact_count_mean_per_frame"),
        "clash_count_mean_per_frame": score.get("clash_count_mean_per_frame"),
        "contact_fraction_p10": score.get("contact_fraction_p10"),
        "contact_fraction_p50": score.get("contact_fraction_p50"),
        "contact_fraction_p90": score.get("contact_fraction_p90"),
        "mean_min_distance_A": float(score["mean_min_distance_A"]),
        "distance_sem_A": score.get("distance_sem_A"),
        "min_distance_p10_A": score.get("min_distance_p10_A"),
        "min_distance_p50_A": score.get("min_distance_p50_A"),
        "min_distance_p90_A": score.get("min_distance_p90_A"),
        "trajectory_frames": int(score["frame_count"]),
        "trajectory_ligand_presence_fraction": score.get("trajectory_ligand_presence_fraction"),
        "trajectory_npz": trajectory_npz,
        "ligand_affinity_hint": float(score["ligand_affinity_hint"]),
        "ligand_onsps_norm": float(score.get("ligand_onsps_norm", 0.0)),
        "ligand_mw": float(score.get("ligand_mw", 0.0)),
        "ligand_logp": float(score.get("ligand_logp", 0.0)),
        "ligand_rot_bonds": float(score.get("ligand_rot_bonds", 0.0)),
        "ligand_h_donors": float(score.get("ligand_h_donors", 0.0)),
        "ligand_h_acceptors": float(score.get("ligand_h_acceptors", 0.0)),
        "ligand_model": str(score.get("ligand_model", str(cfg["ligand_model"]))),
        "mean_e_vdw": score.get("mean_e_vdw"),
        "mean_e_polar": score.get("mean_e_polar"),
        "mean_e_nonpolar": score.get("mean_e_nonpolar"),
        "mean_e_solvation": score.get("mean_e_solvation"),
        "physics_favorable_energy_proxy": score.get("physics_favorable_energy_proxy"),
        "physics_net_support_proxy": score.get("physics_net_support_proxy"),
        "physics_contact_stability_proxy": score.get("physics_contact_stability_proxy"),
        "vdw_nonpolar_support_proxy": score.get("vdw_nonpolar_support_proxy"),
        "polar_support_proxy": score.get("polar_support_proxy"),
        "solvation_penalty_proxy": score.get("solvation_penalty_proxy"),
        "clash_relief_mode": score.get("clash_relief_mode", "off"),
        "clash_relief_enabled": bool(score.get("clash_relief_enabled", False)),
        "clash_relief_target_min_distance_A": score.get("clash_relief_target_min_distance_A"),
        "clash_relief_max_translation_A": score.get("clash_relief_max_translation_A"),
        "clash_relief_max_steps": score.get("clash_relief_max_steps"),
        "clash_relief_applied_frame_count": score.get("clash_relief_applied_frame_count"),
        "clash_relief_frame_fraction": score.get("clash_relief_frame_fraction"),
        "clash_relief_mean_translation_A": score.get("clash_relief_mean_translation_A"),
        "pre_repair_binding_energy_proxy": score.get("pre_repair_binding_energy_proxy"),
        "pre_repair_mean_min_distance_A": score.get("pre_repair_mean_min_distance_A"),
        "pre_repair_clash_frame_fraction": score.get("pre_repair_clash_frame_fraction"),
        "pre_repair_mean_e_vdw": score.get("pre_repair_mean_e_vdw"),
        "backmapped_pdb": backmap_pdb,
        "score_json": score_json,
        "protein_structure_source_path": str(native_info.get("source_path", "") or ""),
        "protein_structure_source_kind": str(native_info.get("source_kind", "") or ""),
        "protein_structure_source_format": str(native_info.get("source_format", "") or ""),
        "protein_structure_source_available": bool(native_info.get("source_available", False)),
        "protein_structure_source_explicit_native_path": str(
            native_info.get("source_explicit_native_path", "") or ""
        ),
        "protein_structure_source_requested_explicit_native_path": bool(
            native_info.get("source_requested_explicit_native_path", False)
        ),
        "protein_structure_source_used_explicit_native_path": bool(
            native_info.get("source_used_explicit_native_path", False)
        ),
        "protein_structure_source_is_aligned_for_backmap": bool(
            native_info.get("source_is_aligned_for_backmap", False)
        ),
        "protein_structure_source_residue_anchor_mode": str(
            native_info.get("source_residue_anchor_mode", "") or ""
        ),
        "protein_structure_source_note": str(native_info.get("notes", "") or ""),
        "protein_structure_protein_atom_count": int(native_info.get("protein_atom_count", 0) or 0),
        "protein_structure_protein_ca_count": int(native_info.get("protein_ca_count", 0) or 0),
        "protein_structure_ligand_atom_count": int(native_info.get("ligand_atom_count", 0) or 0),
        "backmapped_contains_protein": bool(backmapped_contains_protein),
        "backmapped_structure_kind": (
            "pseudo_backmapped_protein_ligand_pdb"
            if backmapped_contains_protein
            else "ligand_only_backmapped_pdb"
        ),
        "backmapped_protein_atoms": int(backmap_stats.get("protein_atoms", 0) or 0),
        "backmapped_protein_residues": int(backmap_stats.get("protein_residues", 0) or 0),
        "backmapped_ligand_atoms": int(backmap_stats.get("ligand_atoms", 0) or 0),
    }
    return result


def _append_replicate_export_metrics(
    result_df: pd.DataFrame,
    ranking_meta: Dict[str, Any],
) -> pd.DataFrame:
    if result_df.empty:
        return result_df
    out = result_df.copy()
    active_score_col = str(
        ranking_meta.get("active_score_col")
        or ranking_meta.get("ranking_score_col_used")
        or ""
    ).strip()
    out["export_rank"] = np.arange(1, len(out) + 1, dtype=np.int64)

    group_cols = [col for col in ("target", "ligand_id") if col in out.columns]
    if len(group_cols) < 2:
        out["replicate_group_key"] = ""
        out["replicate_group_size"] = 1
        out["replicate_rank_within_group"] = 1
        out["replicate_global_rank_best"] = out["export_rank"]
        out["replicate_global_rank_worst"] = out["export_rank"]
        out["replicate_rank_spread"] = 0
        out["replicate_consistency_score"] = np.nan
        out["replicate_support_factor"] = np.nan
        out["replicate_observability_score"] = np.nan
        return out

    out["replicate_group_key"] = (
        out[group_cols[0]].fillna("").astype(str)
        + "::"
        + out[group_cols[1]].fillna("").astype(str)
    )
    grouped = out.groupby(group_cols, sort=False, dropna=False)
    out["replicate_group_size"] = grouped["queue_id"].transform("size").astype(np.int64)
    out["replicate_rank_within_group"] = grouped.cumcount() + 1
    out["replicate_global_rank_best"] = grouped["export_rank"].transform("min").astype(np.int64)
    out["replicate_global_rank_worst"] = grouped["export_rank"].transform("max").astype(np.int64)
    out["replicate_rank_spread"] = (
        out["replicate_global_rank_worst"] - out["replicate_global_rank_best"]
    ).astype(np.int64)

    metric_map = {
        "binding_energy_mmpbsa_kcal_mol_proxy": "binding_energy_mmpbsa_kcal_mol_proxy",
        "mean_min_distance_A": "mean_min_distance_A",
        "stability_score": "stability_score",
        "contact_fraction": "contact_fraction",
        "binding_energy_mmpbsa_std": "binding_energy_mmpbsa_std",
    }
    for src_col, metric_tag in metric_map.items():
        if src_col not in out.columns:
            continue
        num_col = f"__replicate_num__{metric_tag}"
        out[num_col] = pd.to_numeric(out[src_col], errors="coerce")
        metric_group = out.groupby(group_cols, sort=False, dropna=False)[num_col]
        out[f"replicate_mean_{metric_tag}"] = metric_group.transform("mean")
        out[f"replicate_std_{metric_tag}"] = metric_group.transform("std").fillna(0.0)
        out[f"replicate_min_{metric_tag}"] = metric_group.transform("min")
        out[f"replicate_max_{metric_tag}"] = metric_group.transform("max")

    if active_score_col and active_score_col in out.columns:
        active_num_col = "__replicate_num__active_score"
        out[active_num_col] = pd.to_numeric(out[active_score_col], errors="coerce")
        active_group = out.groupby(group_cols, sort=False, dropna=False)[active_num_col]
        out["replicate_active_score_col"] = active_score_col
        out["replicate_mean_active_score"] = active_group.transform("mean")
        out["replicate_std_active_score"] = active_group.transform("std").fillna(0.0)
        out["replicate_min_active_score"] = active_group.transform("min")
        out["replicate_max_active_score"] = active_group.transform("max")
    else:
        out["replicate_active_score_col"] = ""
        out["replicate_mean_active_score"] = np.nan
        out["replicate_std_active_score"] = np.nan
        out["replicate_min_active_score"] = np.nan
        out["replicate_max_active_score"] = np.nan

    distance_std = (
        pd.to_numeric(out["replicate_std_mean_min_distance_A"], errors="coerce")
        if "replicate_std_mean_min_distance_A" in out.columns
        else pd.Series(np.zeros(len(out), dtype=float), index=out.index)
    ).fillna(0.0)
    energy_std = (
        pd.to_numeric(out["replicate_std_binding_energy_mmpbsa_kcal_mol_proxy"], errors="coerce")
        if "replicate_std_binding_energy_mmpbsa_kcal_mol_proxy" in out.columns
        else pd.Series(np.zeros(len(out), dtype=float), index=out.index)
    ).fillna(0.0)
    stability_std = (
        pd.to_numeric(out["replicate_std_stability_score"], errors="coerce")
        if "replicate_std_stability_score" in out.columns
        else pd.Series(np.zeros(len(out), dtype=float), index=out.index)
    ).fillna(0.0)
    support_factor = np.clip(
        pd.to_numeric(out["replicate_group_size"], errors="coerce").fillna(1.0).to_numpy(dtype=float) / 3.0,
        0.0,
        1.0,
    )
    distance_consistency = 1.0 / (1.0 + np.clip(distance_std.to_numpy(dtype=float), 0.0, None) / 0.5)
    energy_consistency = 1.0 / (1.0 + np.clip(energy_std.to_numpy(dtype=float), 0.0, None) / 0.75)
    stability_consistency = 1.0 / (1.0 + np.clip(stability_std.to_numpy(dtype=float), 0.0, None) / 0.15)
    consistency = (
        0.45 * distance_consistency
        + 0.35 * energy_consistency
        + 0.20 * stability_consistency
    )
    out["replicate_support_factor"] = support_factor
    out["replicate_consistency_score"] = consistency
    out["replicate_observability_score"] = consistency * support_factor

    drop_cols = [col for col in out.columns if col.startswith("__replicate_num__")]
    if drop_cols:
        out.drop(columns=drop_cols, inplace=True, errors="ignore")
    return out


def run_pipeline(args: argparse.Namespace) -> Dict[str, Any]:
    queue_csv = str(args.queue_csv).strip()
    if (not queue_csv) or (not os.path.exists(queue_csv)):
        raise FileNotFoundError(f"queue csv not found: {queue_csv}")
    df = pd.read_csv(queue_csv)
    if df.empty:
        raise ValueError(f"queue csv is empty: {queue_csv}")
    manifest_csv = str(getattr(args, "stage2_manifest_csv", "") or "").strip()
    if manifest_csv and os.path.exists(manifest_csv):
        mdf = pd.read_csv(manifest_csv)
        if (not mdf.empty) and ("queue_id" in mdf.columns):
            manifest_cols = [
                "queue_id",
                "trajectory_npz",
                "trajectory_frame_count",
                "frame_with_ligand_count",
                "inline_aux_available",
                "binding_energy_proxy",
                "binding_energy_mmpbsa_kcal_mol_proxy",
                "binding_energy_mmpbsa_std",
                "binding_energy_mmpbsa_sem",
                "binding_energy_mmpbsa_p10_kcal_mol_proxy",
                "binding_energy_mmpbsa_p50_kcal_mol_proxy",
                "binding_energy_mmpbsa_p90_kcal_mol_proxy",
                "stability_score",
                "contact_fraction",
                "frame_contact_fraction_std",
                "frame_contact_presence_fraction",
                "frame_close_contact_presence_fraction",
                "clash_frame_fraction",
                "contact_count_mean_per_frame",
                "close_contact_count_mean_per_frame",
                "clash_count_mean_per_frame",
                "contact_fraction_p10",
                "contact_fraction_p50",
                "contact_fraction_p90",
                "mean_min_distance_A",
                "std_min_distance_A",
                "distance_sem_A",
                "min_distance_p10_A",
                "min_distance_p50_A",
                "min_distance_p90_A",
                "min_min_distance_A",
                "final_min_distance_A",
                "mean_e_vdw",
                "mean_e_polar",
                "mean_e_nonpolar",
                "mean_e_solvation",
                "trajectory_ligand_presence_fraction",
                "physics_favorable_energy_proxy",
                "physics_net_support_proxy",
                "physics_contact_stability_proxy",
                "vdw_nonpolar_support_proxy",
                "polar_support_proxy",
                "solvation_penalty_proxy",
                "affinity_hint",
                "onsps_norm",
                "ligand_onsps_norm",
            ]
            keep_cols = [c for c in manifest_cols if c in mdf.columns]
            if keep_cols:
                for c in keep_cols:
                    if c in df.columns and c != "queue_id":
                        df.drop(columns=[c], inplace=True, errors="ignore")
                df = df.merge(mdf[keep_cols], on="queue_id", how="left")

    max_jobs = int(args.max_jobs)
    queue_rows_total = int(len(df))
    priority_sampling: Dict[str, Any] = {}
    if max_jobs > 0:
        df_selected = df
        used_priority = False
        if str(args.priority_split_csv).strip() and str(args.priority_roles).strip():
            df_selected, priority_sampling = _priority_sample_by_split(
                df=df,
                max_jobs=max_jobs,
                split_csv=str(args.priority_split_csv),
                priority_roles=str(args.priority_roles),
                split_role_col=str(args.priority_split_role_col),
                split_target_col=str(args.priority_split_target_col),
                split_ligand_col=str(args.priority_split_ligand_col),
                balance_targets_for_max_jobs=bool(args.balance_targets_for_max_jobs),
            )
            used_priority = bool(priority_sampling.get("applied", False))
        if not used_priority:
            if bool(args.balance_targets_for_max_jobs):
                df_selected = _balanced_sample_by_target(df, max_jobs=max_jobs)
            else:
                df_selected = df.head(max_jobs).copy()
            if not priority_sampling:
                priority_sampling = {"enabled": False, "applied": False}
        df = df_selected

    out_root = str(args.out_dir).strip() or f"runs/ligand_screening_delivery_{dt.date.today().isoformat()}"
    _ensure_dir(out_root)
    jobs_root = os.path.join(out_root, "jobs")
    score_only = bool(getattr(args, "score_only", False))
    if not score_only:
        _ensure_dir(jobs_root)

    rows: List[Dict[str, Any]] = []
    cfg = {
        "jobs_root": jobs_root,
        "trajectory_root": str(args.trajectory_root),
        "trajectory_glob": str(args.trajectory_glob),
        "allow_missing_trajectory": bool(args.allow_missing_trajectory),
        "contact_cutoff_A": float(args.contact_cutoff_A),
        "min_frames": int(args.min_frames),
        "ligand_model": str(args.ligand_model),
        "hbond_onsps_weight": float(args.hbond_onsps_weight),
        "score_only": bool(score_only),
        "clash_relief_mode": str(args.clash_relief_mode),
        "clash_relief_target_min_distance_A": float(args.clash_relief_target_min_distance_A),
        "clash_relief_max_translation_A": float(args.clash_relief_max_translation_A),
        "clash_relief_max_steps": int(args.clash_relief_max_steps),
    }
    all_rows = df.to_dict(orient="records")
    workers_requested = int(max(0, int(args.workers)))
    workers_auto = max(1, min((os.cpu_count() or 2), 24))
    workers_used = int(workers_requested if workers_requested > 0 else workers_auto)
    parallel_threshold = int(max(1, int(args.parallel_threshold)))
    parallel_enabled = bool(workers_used > 1 and len(all_rows) >= parallel_threshold)
    error_rows: List[str] = []

    if parallel_enabled:
        with ProcessPoolExecutor(max_workers=workers_used) as ex:
            fut_map = {ex.submit(_process_queue_row, row, cfg): idx for idx, row in enumerate(all_rows)}
            for fut in as_completed(fut_map):
                idx = int(fut_map[fut])
                row_obj = all_rows[idx]
                try:
                    rows.append(fut.result())
                except Exception as e:
                    qid = str(row_obj.get("queue_id", "")).strip()
                    error_rows.append(f"{qid or idx}:{e}")
    else:
        workers_used = 1
        for row in all_rows:
            try:
                rows.append(_process_queue_row(row, cfg))
            except Exception as e:
                qid = str(row.get("queue_id", "")).strip()
                error_rows.append(f"{qid or '?'}:{e}")

    if error_rows:
        raise RuntimeError(
            "stage3 processing failed for one or more rows: "
            + "; ".join(error_rows[:5])
            + ("" if len(error_rows) <= 5 else f" ... ({len(error_rows)} total)")
        )

    result_df = pd.DataFrame(rows)
    # Composite ranking score tuned for Stage5 separation:
    # lower is better (energy + distance penalties; contact/stability rewards).
    # We keep the raw proxy columns and expose this as an additional score option.
    if not result_df.empty:
        for _c in [
            "binding_energy_mmpbsa_kcal_mol_proxy",
            "mean_min_distance_A",
            "stability_score",
            "contact_fraction",
            "binding_energy_mmpbsa_std",
            "ligand_affinity_hint",
            "ligand_onsps_norm",
            "ligand_mw",
            "ligand_logp",
            "ligand_rot_bonds",
            "ligand_h_donors",
            "ligand_h_acceptors",
            "binding_energy_mmpbsa_sem",
            "frame_contact_fraction_std",
            "trajectory_ligand_presence_fraction",
            "physics_favorable_energy_proxy",
            "physics_net_support_proxy",
            "physics_contact_stability_proxy",
            "vdw_nonpolar_support_proxy",
            "polar_support_proxy",
            "solvation_penalty_proxy",
            "clash_relief_frame_fraction",
            "clash_relief_mean_translation_A",
            "pre_repair_binding_energy_proxy",
            "pre_repair_mean_min_distance_A",
            "pre_repair_clash_frame_fraction",
            "pre_repair_mean_e_vdw",
        ]:
            if _c in result_df.columns:
                result_df[_c] = pd.to_numeric(result_df[_c], errors="coerce")

        score_reference_scaling = _load_score_reference_scaling(
            mode=str(args.score_reference_scaling_mode),
            stats_json=str(args.score_reference_stats_json),
        )

        def _z(col: str) -> pd.Series:
            return _zscore_with_reference(result_df, col, score_reference_scaling)

        z_e = _z("binding_energy_mmpbsa_kcal_mol_proxy")
        z_d = _z("mean_min_distance_A")
        z_s = _z("stability_score")
        z_c = _z("contact_fraction")
        z_std = _z("binding_energy_mmpbsa_std")
        z_mw = _z("ligand_mw")
        z_logp = _z("ligand_logp")
        z_rot = _z("ligand_rot_bonds")
        z_hd = _z("ligand_h_donors")
        z_ha = _z("ligand_h_acceptors")
        # Empirically selected on p50 reference to lift EF1/PR while preserving AUC floor.
        result_df["binding_score_composite_v2"] = (
            z_e + 0.75 * z_d - 0.05 * z_s - 0.85 * z_c + 0.15 * z_std
        )
        # v3: tighten top-1% discrimination (EF1/PR) while keeping gate-friendly
        # contact distance behavior.
        dist = pd.to_numeric(result_df["mean_min_distance_A"], errors="coerce")
        clash_thr = 2.22
        clash_scale = 0.25
        clash_penalty = np.where(
            np.isfinite(dist.to_numpy()) & (dist.to_numpy() < clash_thr),
            np.square((clash_thr - dist.to_numpy()) / clash_scale),
            0.0,
        )
        result_df["binding_score_composite_v3"] = (
            0.95 * z_e + 0.30 * z_d - 0.05 * z_s - 1.40 * z_c + 0.02 * z_std + 0.05 * clash_penalty
        )
        # v4: OOD/balanced-topk tuned variant.
        # Keep the same physics proxy core, but re-introduce ligand priors that are
        # already available in the metadata to reduce false-positive enrichment from
        # contact-heavy decoys in blind GPCR settings.
        z_aff = _z("ligand_affinity_hint")
        z_onsps = _z("ligand_onsps_norm")
        result_df["binding_score_composite_v4"] = (
            0.95 * z_e
            + 0.30 * z_d
            - 0.05 * z_s
            - 0.80 * z_c
            + 0.02 * z_std
            - 2.00 * z_aff
            - 1.00 * z_onsps
            + 0.05 * clash_penalty
        )
        # v6: GPCR blind scorefix2.
        # Preserve the v4 physics core, but add ligand priors that favor the
        # larger, more donor/acceptor-rich beta-blocker-like binders that remain
        # under-ranked against compact aromatic hard decoys in ADRB2 core blind runs.
        result_df["binding_score_composite_v6"] = (
            0.95 * z_e
            + 0.30 * z_d
            - 0.05 * z_s
            - 0.80 * z_c
            + 0.02 * z_std
            - 2.20 * z_aff
            - 1.00 * z_onsps
            - 0.18 * z_mw
            - 0.22 * z_hd
            - 0.14 * z_ha
            - 0.10 * z_rot
            + 0.05 * clash_penalty
        )
        # v7: GPCR core blind precision fix.
        # Remove the distance reward that was favoring compact aromatic decoys and
        # lean harder on donor/acceptor richness plus rotatable-bond flexibility so
        # beta-blocker-like binders recover into the top ranks in ADRB2 core blind.
        result_df["binding_score_composite_v7"] = (
            0.95 * z_e
            + 0.00 * z_d
            - 0.05 * z_s
            - 0.15 * z_c
            + 0.02 * z_std
            - 1.20 * z_aff
            - 1.00 * z_onsps
            - 0.00 * z_mw
            - 1.20 * z_hd
            - 1.00 * z_ha
            - 0.40 * z_rot
            + 0.24 * z_logp
            + 0.05 * clash_penalty
        )
        result_df, aux_meta = _apply_aux_binding_model(
            result_df,
            checkpoint_path=str(args.aux_model_checkpoint),
            aux_score_weight=float(args.aux_score_weight),
        )
        result_df, residual_shadow_meta = _apply_residual_prototype_shadow(
            result_df,
            args,
            z_e=z_e,
            z_d=z_d,
            z_s=z_s,
            z_c=z_c,
            z_aff=z_aff,
            z_logp=z_logp,
            z_rot=z_rot,
            z_hd=z_hd,
            z_ha=z_ha,
            z_std=z_std,
        )
        result_df["score_scaling_mode"] = str(score_reference_scaling.get("mode", "run_local"))
        result_df["score_reference_stats_hash"] = str(score_reference_scaling.get("stats_hash", ""))
    else:
        aux_meta = {"applied": False, "reason": "empty_scores"}
        residual_shadow_meta = {"enabled": False, "status": "empty_scores"}
        score_reference_scaling = _load_score_reference_scaling(
            mode=str(args.score_reference_scaling_mode),
            stats_json=str(args.score_reference_stats_json),
        )

    ranking_meta = _resolve_ranking_columns(result_df, residual_shadow_meta)
    result_df = result_df.sort_values(
        ranking_meta["sort_columns"],
        ascending=ranking_meta["ascending"],
        na_position="last",
    ).reset_index(drop=True)
    result_df = _append_replicate_export_metrics(result_df, ranking_meta)
    result_csv = str(args.out_scores_csv).strip() or os.path.join(out_root, "ligand_scores.csv")
    _ensure_dir(os.path.dirname(result_csv) or ".")
    result_df.to_csv(result_csv, index=False)

    topk = result_df.head(int(max(args.topk_report, 1))).to_dict(orient="records")
    replicate_group_count = (
        int(result_df["replicate_group_key"].nunique())
        if (not result_df.empty) and ("replicate_group_key" in result_df.columns)
        else 0
    )
    multi_replicate_group_count = (
        int(result_df.loc[result_df["replicate_group_size"] > 1, "replicate_group_key"].nunique())
        if (not result_df.empty) and {"replicate_group_key", "replicate_group_size"}.issubset(result_df.columns)
        else 0
    )
    unique_groups_df = (
        result_df.drop_duplicates(subset=["replicate_group_key"])
        if (not result_df.empty) and ("replicate_group_key" in result_df.columns)
        else pd.DataFrame()
    )
    summary = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "queue_rows": int(len(df)),
        "queue_rows_total": int(queue_rows_total),
        "processed_jobs": int(len(result_df)),
        "max_jobs": int(max_jobs),
        "balance_targets_for_max_jobs": bool(args.balance_targets_for_max_jobs),
        "priority_sampling": priority_sampling,
        "ligand_model": str(args.ligand_model),
        "hbond_onsps_weight": float(args.hbond_onsps_weight),
        "clash_relief_mode": str(args.clash_relief_mode),
        "clash_relief_target_min_distance_A": (
            float(args.clash_relief_target_min_distance_A)
            if str(args.clash_relief_mode).strip().lower() not in {"", "off", "none", "disabled", "false", "0"}
            else None
        ),
        "clash_relief_max_translation_A": (
            float(args.clash_relief_max_translation_A)
            if str(args.clash_relief_mode).strip().lower() not in {"", "off", "none", "disabled", "false", "0"}
            else None
        ),
        "clash_relief_max_steps": (
            int(args.clash_relief_max_steps)
            if str(args.clash_relief_mode).strip().lower() not in {"", "off", "none", "disabled", "false", "0"}
            else None
        ),
        "allow_missing_trajectory": bool(args.allow_missing_trajectory),
        "score_only": bool(score_only),
        "parallel_enabled": bool(parallel_enabled),
        "workers_requested": int(workers_requested),
        "workers_used": int(workers_used),
        "parallel_threshold": int(parallel_threshold),
        "contact_cutoff_A": float(args.contact_cutoff_A),
        "min_frames_required": int(args.min_frames),
        "replicate_export_schema_version": "backmapping_replicate_metrics_v1",
        "physics_export_schema_version": "backmapping_physics_support_v1",
        "score_reference_scaling": {
            key: value
            for key, value in score_reference_scaling.items()
            if key != "features"
        },
        "active_score_col": str(ranking_meta["active_score_col"]),
        "ranking_score_col_used": str(ranking_meta["ranking_score_col_used"]),
        "ranking_sort_columns": list(ranking_meta["sort_columns"]),
        "avg_binding_energy_proxy": float(result_df["binding_energy_proxy"].mean()) if not result_df.empty else None,
        "avg_binding_energy_mmpbsa_kcal_mol_proxy": (
            float(result_df["binding_energy_mmpbsa_kcal_mol_proxy"].mean()) if not result_df.empty else None
        ),
        "avg_stability_score": float(result_df["stability_score"].mean()) if not result_df.empty else None,
        "avg_binding_energy_mmpbsa_sem": (
            float(pd.to_numeric(result_df["binding_energy_mmpbsa_sem"], errors="coerce").mean())
            if (not result_df.empty) and ("binding_energy_mmpbsa_sem" in result_df.columns)
            else None
        ),
        "avg_frame_contact_presence_fraction": (
            float(pd.to_numeric(result_df["frame_contact_presence_fraction"], errors="coerce").mean())
            if (not result_df.empty) and ("frame_contact_presence_fraction" in result_df.columns)
            else None
        ),
        "avg_clash_frame_fraction": (
            float(pd.to_numeric(result_df["clash_frame_fraction"], errors="coerce").mean())
            if (not result_df.empty) and ("clash_frame_fraction" in result_df.columns)
            else None
        ),
        "avg_clash_relief_frame_fraction": (
            float(pd.to_numeric(result_df["clash_relief_frame_fraction"], errors="coerce").mean())
            if (not result_df.empty) and ("clash_relief_frame_fraction" in result_df.columns)
            else None
        ),
        "avg_clash_relief_mean_translation_A": (
            float(pd.to_numeric(result_df["clash_relief_mean_translation_A"], errors="coerce").mean())
            if (not result_df.empty) and ("clash_relief_mean_translation_A" in result_df.columns)
            else None
        ),
        "avg_pre_repair_binding_energy_proxy": (
            float(pd.to_numeric(result_df["pre_repair_binding_energy_proxy"], errors="coerce").mean())
            if (not result_df.empty) and ("pre_repair_binding_energy_proxy" in result_df.columns)
            else None
        ),
        "avg_pre_repair_mean_min_distance_A": (
            float(pd.to_numeric(result_df["pre_repair_mean_min_distance_A"], errors="coerce").mean())
            if (not result_df.empty) and ("pre_repair_mean_min_distance_A" in result_df.columns)
            else None
        ),
        "avg_trajectory_ligand_presence_fraction": (
            float(pd.to_numeric(result_df["trajectory_ligand_presence_fraction"], errors="coerce").mean())
            if (not result_df.empty) and ("trajectory_ligand_presence_fraction" in result_df.columns)
            else None
        ),
        "avg_physics_net_support_proxy": (
            float(pd.to_numeric(result_df["physics_net_support_proxy"], errors="coerce").mean())
            if (not result_df.empty) and ("physics_net_support_proxy" in result_df.columns)
            else None
        ),
        "replicate_group_count": replicate_group_count,
        "multi_replicate_group_count": multi_replicate_group_count,
        "avg_replicate_group_size": (
            float(pd.to_numeric(unique_groups_df["replicate_group_size"], errors="coerce").mean())
            if (not unique_groups_df.empty) and ("replicate_group_size" in unique_groups_df.columns)
            else None
        ),
        "avg_replicate_consistency_score": (
            float(pd.to_numeric(unique_groups_df["replicate_consistency_score"], errors="coerce").mean())
            if (not unique_groups_df.empty) and ("replicate_consistency_score" in unique_groups_df.columns)
            else None
        ),
        "avg_replicate_observability_score": (
            float(pd.to_numeric(unique_groups_df["replicate_observability_score"], errors="coerce").mean())
            if (not unique_groups_df.empty) and ("replicate_observability_score" in unique_groups_df.columns)
            else None
        ),
        "topk": topk,
        "artifacts": {
            "scores_csv": result_csv,
        },
        "aux_model": aux_meta,
        "residual_prototype": residual_shadow_meta,
    }
    if not score_only:
        summary["artifacts"]["jobs_dir"] = jobs_root
    out_json = str(args.out_summary_json).strip() or os.path.join(out_root, "summary.json")
    out_md = str(args.out_summary_md).strip() or os.path.join(out_root, "summary.md")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    lines = [
        "# Ligand Backmapping + Scoring",
        "",
        f"- generated_at_local: {summary['generated_at_local']}",
        f"- queue_rows: {summary['queue_rows']}",
        f"- processed_jobs: {summary['processed_jobs']}",
        f"- avg_binding_energy_proxy: {summary['avg_binding_energy_proxy']}",
        f"- avg_binding_energy_mmpbsa_kcal_mol_proxy: {summary['avg_binding_energy_mmpbsa_kcal_mol_proxy']}",
        f"- avg_stability_score: {summary['avg_stability_score']}",
        f"- avg_binding_energy_mmpbsa_sem: {summary['avg_binding_energy_mmpbsa_sem']}",
        f"- clash_relief_mode: {summary['clash_relief_mode']}",
        f"- avg_pre_repair_binding_energy_proxy: {summary['avg_pre_repair_binding_energy_proxy']}",
        f"- avg_clash_relief_frame_fraction: {summary['avg_clash_relief_frame_fraction']}",
        f"- avg_physics_net_support_proxy: {summary['avg_physics_net_support_proxy']}",
        f"- avg_replicate_consistency_score: {summary['avg_replicate_consistency_score']}",
        f"- ranking_score_col_used: {summary['ranking_score_col_used']}",
        f"- scores_csv: `{result_csv}`",
    ]
    residual_meta = summary.get("residual_prototype", {}) if isinstance(summary.get("residual_prototype"), dict) else {}
    if residual_meta:
        lines.extend(
            [
                f"- residual_prototype_enabled: {residual_meta.get('enabled')}",
                f"- residual_prototype_mode: {residual_meta.get('mode')}",
                f"- residual_prototype_status: {residual_meta.get('status')}",
                f"- residual_shadow_positive_delta_count: {residual_meta.get('positive_delta_count')}",
                f"- residual_shadow_mean_delta: {residual_meta.get('mean_delta')}",
                f"- residual_shadow_max_delta: {residual_meta.get('max_delta')}",
            ]
        )
    scaling_meta = summary.get("score_reference_scaling", {})
    if isinstance(scaling_meta, dict) and scaling_meta:
        lines.extend(
            [
                f"- score_reference_scaling_mode: {scaling_meta.get('mode')}",
                f"- score_reference_scaling_status: {scaling_meta.get('status')}",
                f"- score_reference_stats_hash: {scaling_meta.get('stats_hash')}",
                f"- score_reference_applied_columns: {scaling_meta.get('applied_columns')}",
                f"- score_reference_fallback_columns: {scaling_meta.get('fallback_columns')}",
            ]
        )
    if not score_only:
        lines.append(f"- jobs_dir: `{jobs_root}`")
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    bundle_zip = ""
    if bool(args.make_bundle_zip) and (not score_only):
        archive_base = str(args.bundle_base).strip() or os.path.join(out_root, "ligand_delivery_bundle")
        bundle_zip = shutil.make_archive(archive_base, "zip", root_dir=out_root)
        summary["artifacts"]["bundle_zip"] = bundle_zip
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

    return {
        "summary": summary,
        "scores_csv": result_csv,
        "summary_json": out_json,
        "summary_md": out_md,
        "bundle_zip": bundle_zip,
    }


def build_parser() -> argparse.ArgumentParser:
    stamp = dt.date.today().isoformat()
    p = argparse.ArgumentParser(
        description=(
            "Backmap queue jobs to pseudo all-atom PDB and compute binding proxy score table for delivery."
        )
    )
    p.add_argument("--queue-csv", type=str, required=True)
    p.add_argument("--stage2-manifest-csv", type=str, default="")
    p.add_argument("--trajectory-root", type=str, default="")
    p.add_argument("--trajectory-glob", type=str, default="")
    p.add_argument("--allow-missing-trajectory", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--min-frames", type=int, default=100)
    p.add_argument("--contact-cutoff-A", type=float, default=6.0)
    p.add_argument("--max-jobs", type=int, default=640)
    p.add_argument("--workers", type=int, default=0)
    p.add_argument("--parallel-threshold", type=int, default=2)
    p.add_argument("--balance-targets-for-max-jobs", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--priority-split-csv", type=str, default="")
    p.add_argument("--priority-roles", type=str, default="")
    p.add_argument("--priority-split-role-col", type=str, default="role")
    p.add_argument("--priority-split-target-col", type=str, default="target")
    p.add_argument("--priority-split-ligand-col", type=str, default="ligand_id")
    p.add_argument(
        "--ligand-model",
        type=str,
        default="2bead",
        choices=["2bead", "3bead_implicit_hbond"],
    )
    p.add_argument("--hbond-onsps-weight", type=float, default=1.0)
    p.add_argument(
        "--clash-relief-mode",
        type=str,
        default="off",
        choices=["off", "translate"],
        help="Optional deterministic ligand translation before scoring to relieve impossible steric clashes.",
    )
    p.add_argument("--clash-relief-target-min-distance-A", type=float, default=2.12)
    p.add_argument("--clash-relief-max-translation-A", type=float, default=2.0)
    p.add_argument("--clash-relief-max-steps", type=int, default=12)
    p.add_argument("--topk-report", type=int, default=20)
    p.add_argument("--out-dir", type=str, default=f"runs/ligand_screening_delivery_{stamp}")
    p.add_argument("--out-scores-csv", type=str, default="")
    p.add_argument("--out-summary-json", type=str, default="")
    p.add_argument("--out-summary-md", type=str, default="")
    p.add_argument("--aux-model-checkpoint", type=str, default="")
    p.add_argument("--aux-score-weight", type=float, default=0.35)
    p.add_argument("--residual-prototype-enabled", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--residual-prototype-mode", type=str, default="shadow_only")
    p.add_argument("--residual-prototype-family", type=str, default="")
    p.add_argument("--residual-prototype-spec-json", type=str, default="")
    p.add_argument("--residual-prototype-runtime-hook-ready", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--residual-prototype-max-abs-delta-score", type=float, default=None)
    p.add_argument("--residual-prototype-yellow-band-abs-delta-score", type=float, default=None)
    p.add_argument("--score-reference-scaling-mode", type=str, default="run_local")
    p.add_argument("--score-reference-stats-json", type=str, default="")
    p.add_argument("--score-only", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--make-bundle-zip", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--bundle-base", type=str, default="")
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    payload = run_pipeline(args)
    print(json.dumps(payload.get("summary", {}), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
