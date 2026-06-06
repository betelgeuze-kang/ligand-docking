#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_ROWS_CSV = (
    "runs/external_validation_2026-05-03_family_balanced_frozen_r2_set1_core_blind_gpcr_core_full_"
    "p0_n100000_r1_stage5_ranking_rows.csv"
)
DEFAULT_STAGE3_CSV = (
    "runs/external_validation_2026-05-03_family_balanced_frozen_r2_set1_core_blind_gpcr_core_full_"
    "p0_n100000_r1_stage3_scores.csv"
)
DEFAULT_CI_JSON = (
    "runs/external_validation_2026-05-03_family_balanced_frozen_r2_set1_core_blind_gpcr_core_full_"
    "p0_n100000_r1_stage5_ranking_summary.json"
)
DEFAULT_READINESS_JSON = ""
DEFAULT_OUT_JSON = "runs/gpcr_guarded_100k_rank_failure_diagnostics_current.json"
DEFAULT_OUT_MD = "runs/gpcr_guarded_100k_rank_failure_diagnostics_current.md"
DEFAULT_V4_REPLAY_EVAL_JSON = "runs/gpcr_acidic_anchor_v4_shadow_replay_eval_current.json"
DEFAULT_V4_REPLAY_SUMMARY_JSON = "runs/gpcr_acidic_anchor_v4_shadow_replay_summary_current.json"
DEFAULT_V5_REPLAY_EVAL_JSON = "runs/gpcr_fixed_reference_live_v5_shadow_replay_eval_current.json"
DEFAULT_V5_REPLAY_SUMMARY_JSON = "runs/gpcr_fixed_reference_live_v5_shadow_replay_summary_current.json"
DEFAULT_V6_SPEC_JSON = "runs/gpcr_residual_prototype_spec_class_a_motif_shadow_v6.json"
DEFAULT_V6_REPLAY_EVAL_JSON = "runs/gpcr_class_a_motif_v6_shadow_replay_eval_current.json"
DEFAULT_V6_REPLAY_SUMMARY_JSON = "runs/gpcr_class_a_motif_v6_shadow_replay_summary_current.json"
DEFAULT_V7_SPEC_JSON = "runs/gpcr_residual_prototype_spec_class_a_anchor_geometry_shadow_v7.json"
DEFAULT_V7_REPLAY_EVAL_JSON = "runs/gpcr_class_a_anchor_geometry_v7_shadow_replay_eval_current.json"
DEFAULT_V7_REPLAY_SUMMARY_JSON = "runs/gpcr_class_a_anchor_geometry_v7_shadow_replay_summary_current.json"
DEFAULT_V8_SPEC_JSON = "runs/gpcr_residual_prototype_spec_direct_atom_anchor_window_shadow_v8.json"
DEFAULT_V8_REPLAY_EVAL_JSON = "runs/gpcr_direct_atom_anchor_window_v8_shadow_replay_eval_current.json"
DEFAULT_V8_REPLAY_SUMMARY_JSON = "runs/gpcr_direct_atom_anchor_window_v8_shadow_replay_summary_current.json"
DEFAULT_V9_SPEC_JSON = "runs/gpcr_residual_prototype_spec_atom_window_excess_polar_shadow_v9.json"
DEFAULT_V9_REPLAY_EVAL_JSON = "runs/gpcr_atom_window_excess_polar_v9_v2preserve_shadow_replay_eval_current.json"
DEFAULT_V9_REPLAY_SUMMARY_JSON = "runs/gpcr_atom_window_excess_polar_v9_v2preserve_shadow_replay_summary_current.json"

SCORE_COL = "binding_score_composite_v7"
SCORE_COL_CANDIDATES = (
    "binding_score_composite_v7_residual_active",
    "binding_score_composite_v7",
)
TOP20_THRESHOLD = 0.20
CI_LOW_THRESHOLD = 0.45
FROZEN_R2_V2_SHADOW_PR_AUC_BASELINE = 0.4326129361306714
FROZEN_R2_V2_SHADOW_PR_AUC_CI_LOW_BASELINE = 0.12342803469357462
FROZEN_R2_V2_SHADOW_TOP20_HIT_RATE_BASELINE = 0.25
NON_ADRB2_MARKERS = ("DRD", "HTR", "OPRM", "OPRD", "OPRK", "CHEMBL217", "CHEMBL224", "CHEMBL233")
DRD2_MARKERS = ("DRD2", "CHEMBL217")
FEATURE_COLUMNS = [
    "ligand_affinity_hint",
    "ligand_onsps_norm",
    "ligand_mw",
    "ligand_logp",
    "ligand_rot_bonds",
    "ligand_h_donors",
    "ligand_h_acceptors",
    "binding_energy_mmpbsa_kcal_mol_proxy",
    "mean_min_distance_A",
    "contact_fraction",
    "stability_score",
]
ANCHOR_PROXY_SOURCE_COLUMNS = [
    "contact_fraction",
    "mean_min_distance_A",
    "binding_energy_mmpbsa_kcal_mol_proxy",
    "stability_score",
    "ligand_affinity_hint",
    "ligand_onsps_norm",
    "residual_shadow_prior_pressure",
]
SMILES_COLUMNS = ("ligand_smiles", "smiles", "canonical_smiles", "isomeric_smiles")
POSE_PRESERVATION_RMSD_COLUMNS = (
    "pose_preservation_rmsd_A",
    "pose_preservation_rmsd",
    "ligand_pose_preservation_rmsd_A",
    "ligand_pose_rmsd_A",
    "local_pose_rmsd_A",
    "commercial_pose_preservation_rmsd_A_v2",
)
LOCAL_MINIMIZATION_SURVIVAL_COLUMNS = (
    "local_minimization_survival_fraction",
    "minimization_survival_fraction",
    "local_minimization_survival",
    "minimized_pose_survival_fraction",
    "commercial_local_minimization_survival_fraction_v2",
)
TRAJECTORY_SURVIVAL_SOURCE_COLUMNS = (
    "trajectory_ligand_presence_fraction",
    "frame_contact_presence_fraction",
    "clash_frame_fraction",
)
DRD2_LABEL_FREE_MOTIF_SUBLANE = "class_a_aminergic_opioid_orthosteric_motif_diagnostic"
ACIDIC_OVERANCHOR_PROXY_THRESHOLD = 0.75
ACIDIC_OVERANCHOR_ATOM_CONTACT_THRESHOLD = 0.5
LIGAND_PRIOR_HIGH_THRESHOLD = 1.0
PRIOR_OVERREWARD_HIGH_THRESHOLD = 0.5
EXCLUDED_NATIVE_LIGAND_RESN = {
    "HOH",
    "WAT",
    "DOD",
    "PEG",
    "OLA",
    "OLC",
    "CLR",
    "CHL",
    "NA",
    "CL",
    "K",
    "MG",
    "CA",
    "ZN",
}
ACID_SIDECHAIN_ATOMS = {"ASP": {"OD1", "OD2"}, "GLU": {"OE1", "OE2"}}


def _resolve(path_like: str | Path | None) -> Path | None:
    if path_like is None or str(path_like).strip() == "":
        return None
    path = Path(path_like)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _read_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_csv(path: Path | None) -> list[dict[str, str]]:
    if path is None or not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _float(value: Any) -> float | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _is_positive(row: dict[str, Any]) -> bool:
    return _text(row.get("is_binder")).lower() in {"1", "true", "t", "yes", "y"}


def _is_non_adrb2(target: str) -> bool:
    upper = target.upper()
    return "ADRB2" not in upper and any(marker in upper for marker in NON_ADRB2_MARKERS)


def _is_drd2_target(target: str) -> bool:
    upper = target.upper()
    return any(marker in upper for marker in DRD2_MARKERS)


def _score_col(rows: list[dict[str, Any]]) -> str:
    observed = {key for row in rows for key in row}
    for col in SCORE_COL_CANDIDATES:
        if col in observed and any(_float(row.get(col)) is not None for row in rows):
            return col
    return SCORE_COL


def _rank_maps(rows: list[dict[str, Any]], score_col: str) -> tuple[dict[tuple[str, str], int], dict[tuple[str, str], int]]:
    scored = [
        (idx, row, _float(row.get(score_col)))
        for idx, row in enumerate(rows)
        if _float(row.get(score_col)) is not None
    ]
    scored.sort(key=lambda item: (item[2], _text(item[1].get("target")), _text(item[1].get("ligand_id"))))
    global_ranks = {
        (_text(row.get("target")), _text(row.get("ligand_id"))): rank
        for rank, (_idx, row, _score) in enumerate(scored, start=1)
    }
    within_ranks: dict[tuple[str, str], int] = {}
    by_target: dict[str, list[tuple[int, dict[str, Any], float | None]]] = {}
    for item in scored:
        by_target.setdefault(_text(item[1].get("target")), []).append(item)
    for target, target_rows in by_target.items():
        for rank, (_idx, row, _score) in enumerate(target_rows, start=1):
            within_ranks[(target, _text(row.get("ligand_id")))] = rank
    return global_ranks, within_ranks


def _stage3_feature_lookup(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, Any]]:
    lookup: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        key = (_text(row.get("target")), _text(row.get("ligand_id")))
        if key not in lookup:
            lookup[key] = row
    return lookup


def _feature_snapshot(row: dict[str, Any]) -> dict[str, float | None]:
    return {col: _float(row.get(col)) for col in FEATURE_COLUMNS if col in row}


def _clamp01(value: float | None) -> float | None:
    if value is None:
        return None
    return float(max(0.0, min(1.0, value)))


def _mean_present(values: list[float | None]) -> float | None:
    present = [value for value in values if value is not None]
    if not present:
        return None
    return float(sum(present) / len(present))


def _proxy_diagnostics(row: dict[str, Any]) -> dict[str, float | None]:
    contact = _float(row.get("contact_fraction"))
    distance = _float(row.get("mean_min_distance_A"))
    energy = _float(row.get("binding_energy_mmpbsa_kcal_mol_proxy"))
    stability = _float(row.get("stability_score"))
    affinity_hint = _float(row.get("ligand_affinity_hint"))
    prior_pressure = _float(row.get("residual_shadow_prior_pressure"))

    contact_support = _clamp01((contact or 0.0) / 0.006) if contact is not None else None
    distance_support = _clamp01((6.0 - distance) / 2.0) if distance is not None else None
    conserved_anchor_proxy = _mean_present([contact_support, distance_support])

    energy_support = _clamp01((-(energy or 0.0)) / 0.55) if energy is not None else None
    stability_support = _clamp01((stability or 0.0) / 0.006) if stability is not None else None
    pose_physics_support = _mean_present([conserved_anchor_proxy, energy_support, stability_support])

    prior_signal = prior_pressure if prior_pressure is not None else affinity_hint
    prior_overreward_without_anchor = None
    if prior_signal is not None and conserved_anchor_proxy is not None:
        prior_overreward_without_anchor = _clamp01(prior_signal * (1.0 - conserved_anchor_proxy))

    return {
        "conserved_anchor_proxy": conserved_anchor_proxy,
        "pose_physics_support": pose_physics_support,
        "prior_overreward_without_anchor": prior_overreward_without_anchor,
    }


def _first_present(row: dict[str, Any], columns: tuple[str, ...]) -> tuple[str, Any] | tuple[None, None]:
    for col in columns:
        value = row.get(col)
        if _text(value):
            return col, value
    return None, None


def _numeric_proxy_from_columns(
    row: dict[str, Any],
    columns: tuple[str, ...],
    *,
    lower_is_better: bool,
    good_at: float,
    bad_at: float,
) -> dict[str, Any]:
    col, value = _first_present(row, columns)
    numeric = _float(value)
    support = None
    if numeric is not None:
        if lower_is_better:
            support = _clamp01((bad_at - numeric) / (bad_at - good_at))
        else:
            support = _clamp01((numeric - bad_at) / (good_at - bad_at))
    return {
        "available": numeric is not None,
        "source_column": col,
        "value": numeric,
        "support_proxy": support,
    }


def _local_minimization_survival_proxy(row: dict[str, Any]) -> dict[str, Any]:
    col, value = _first_present(row, LOCAL_MINIMIZATION_SURVIVAL_COLUMNS)
    numeric = _float(value)
    if numeric is not None:
        support = _clamp01(numeric if numeric <= 1.0 else numeric / 100.0)
        return {
            "available": True,
            "source_column": col,
            "value": numeric,
            "support_proxy": support,
        }
    text = _text(value).lower()
    if text:
        passed = text in {"1", "true", "t", "yes", "y", "pass", "passed", "survived"}
        failed = text in {"0", "false", "f", "no", "n", "fail", "failed", "not_survived"}
        if passed or failed:
            return {
                "available": True,
                "source_column": col,
                "value": text,
                "support_proxy": 1.0 if passed else 0.0,
            }
    return {"available": False, "source_column": col, "value": None, "support_proxy": None}


def _trajectory_pose_preservation_proxy(row: dict[str, Any]) -> dict[str, Any]:
    npz_path = _resolve(_text(row.get("trajectory_npz")))
    if npz_path is None or not npz_path.exists():
        return {
            "available": False,
            "basis": "trajectory_ligand_frames_first_frame_rmsd",
            "trajectory_npz": _text(row.get("trajectory_npz")),
            "reason": "trajectory_npz_missing",
        }
    try:
        with np.load(str(npz_path), allow_pickle=False) as npz:
            ligand_frames = np.asarray(npz["ligand_frames"], dtype=float)
    except Exception as exc:
        return {
            "available": False,
            "basis": "trajectory_ligand_frames_first_frame_rmsd",
            "trajectory_npz": str(npz_path),
            "reason": f"trajectory_npz_unreadable:{type(exc).__name__}",
        }
    if ligand_frames.ndim != 3 or ligand_frames.shape[0] == 0 or ligand_frames.shape[1] == 0:
        return {
            "available": False,
            "basis": "trajectory_ligand_frames_first_frame_rmsd",
            "trajectory_npz": str(npz_path),
            "reason": "ligand_frames_missing",
        }
    deltas = ligand_frames - ligand_frames[:1, :, :]
    frame_rmsd = np.sqrt(np.mean(np.sum(deltas * deltas, axis=2), axis=1))
    centroid = np.mean(ligand_frames, axis=1)
    centroid_delta = centroid - centroid[:1, :]
    centroid_drift = np.sqrt(np.sum(centroid_delta * centroid_delta, axis=1))
    p90_rmsd = float(np.percentile(frame_rmsd, 90))
    return {
        "available": True,
        "basis": "trajectory_ligand_frames_first_frame_rmsd",
        "trajectory_npz": str(npz_path),
        "frame_count": int(ligand_frames.shape[0]),
        "ligand_bead_count": int(ligand_frames.shape[1]),
        "mean_frame_rmsd_A": float(np.mean(frame_rmsd)),
        "p90_frame_rmsd_A": p90_rmsd,
        "max_frame_rmsd_A": float(np.max(frame_rmsd)),
        "mean_centroid_drift_A": float(np.mean(centroid_drift)),
        "p90_centroid_drift_A": float(np.percentile(centroid_drift, 90)),
        "support_proxy": _clamp01((4.0 - p90_rmsd) / 4.0),
        "interpretation": (
            "Trajectory-only pose-preservation proxy relative to the first ligand frame; "
            "diagnostic-only and not a substitute for atom-resolved pose RMSD."
        ),
    }


def _trajectory_survival_proxy(row: dict[str, Any]) -> dict[str, Any]:
    ligand_presence = _float(row.get("trajectory_ligand_presence_fraction"))
    contact_presence = _float(row.get("frame_contact_presence_fraction"))
    clash_fraction = _float(row.get("clash_frame_fraction"))
    components = [
        ligand_presence,
        contact_presence,
        1.0 - clash_fraction if clash_fraction is not None else None,
    ]
    support = _mean_present([_clamp01(value) for value in components if value is not None])
    return {
        "available": support is not None,
        "basis": "trajectory_ligand_presence_contact_presence_clash_absence",
        "source_columns": [col for col in TRAJECTORY_SURVIVAL_SOURCE_COLUMNS if col in row],
        "trajectory_ligand_presence_fraction": ligand_presence,
        "frame_contact_presence_fraction": contact_presence,
        "clash_frame_fraction": clash_fraction,
        "support_proxy": support,
        "interpretation": (
            "Trajectory survival proxy only; actual local-minimization survival remains a required follow-up if absent."
        ),
    }


def _smiles_chemistry_heuristics(row: dict[str, Any]) -> dict[str, Any]:
    col, value = _first_present(row, SMILES_COLUMNS)
    smiles = _text(value)
    h_donors = _float(row.get("ligand_h_donors"))
    h_acceptors = _float(row.get("ligand_h_acceptors"))
    rot_bonds = _float(row.get("ligand_rot_bonds"))
    upper = smiles.upper()
    aliphatic_n_count = upper.count("N") - upper.count("[NH") - upper.count("[N+")
    aromatic_n_count = smiles.count("n")
    explicit_cationic_n = "[N+]" in upper or "[NH+]" in upper or "[NH2+]" in upper or "[NH3+]" in upper
    neutral_aliphatic_amine = bool(smiles and ("N" in smiles or "CN" in smiles or "NC" in smiles))
    amide_like = "C(=O)N" in upper or "NC(=O)" in upper or "N=C=O" in upper
    sulfonamide_like = "S(=O)(=O)N" in upper or "NS(=O)(=O)" in upper
    acid_like = "C(=O)O" in upper or "C(=O)[O-]" in upper or "[O-]" in upper
    imine_or_amidine_like = "N=C" in upper or "C(=N" in upper or "NC(=N" in upper
    tautomer_risk = bool("[nH]" in smiles or imine_or_amidine_like or "N=C(O)" in upper)
    basic_amine_like = bool((explicit_cationic_n or neutral_aliphatic_amine) and not (amide_like and aliphatic_n_count <= 1))
    amine_anchor_support = None
    if smiles:
        amine_anchor_support = 1.0 if basic_amine_like and not acid_like else 0.5 if basic_amine_like else 0.0
    column_polar_anchor_possible = (
        h_donors is not None
        and h_acceptors is not None
        and h_donors >= 1.0
        and h_acceptors >= 1.0
    )
    return {
        "available": bool(smiles),
        "source_column": col,
        "smiles": smiles,
        "column_proxy_available": any(value is not None for value in (h_donors, h_acceptors, rot_bonds)),
        "ligand_h_donors": h_donors,
        "ligand_h_acceptors": h_acceptors,
        "ligand_rot_bonds": rot_bonds,
        "polar_anchor_possible_from_columns": bool(column_polar_anchor_possible),
        "basic_amine_like": basic_amine_like,
        "explicit_cationic_n": explicit_cationic_n,
        "aliphatic_n_count_proxy": max(0, aliphatic_n_count),
        "aromatic_n_count_proxy": aromatic_n_count,
        "amide_or_sulfonamide_like": bool(amide_like or sulfonamide_like),
        "acid_or_zwitterion_risk": acid_like,
        "tautomer_or_protonation_review_flag": tautomer_risk or (bool(smiles) and not basic_amine_like),
        "amine_anchor_support_proxy": amine_anchor_support,
        "interpretation": (
            "Local string heuristic only; use to prioritize protonation/tautomer review, not as claim or live scorer evidence."
        ),
    }


def _pose_physics_rescue_proxies(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "pose_preservation_rmsd_proxy": _numeric_proxy_from_columns(
            row,
            POSE_PRESERVATION_RMSD_COLUMNS,
            lower_is_better=True,
            good_at=2.0,
            bad_at=6.0,
        ),
        "local_minimization_survival_proxy": _local_minimization_survival_proxy(row),
        "trajectory_pose_preservation_proxy": _trajectory_pose_preservation_proxy(row),
        "trajectory_survival_proxy": _trajectory_survival_proxy(row),
        "chemistry_heuristics": _smiles_chemistry_heuristics(row),
    }


def _compact_drd2_row(
    row: dict[str, Any],
    stage3: dict[str, Any],
    *,
    rank: int | None,
    within_target_rank: int | None,
    score_col: str,
) -> dict[str, Any]:
    merged = {**row, **stage3}
    return {
        "target": _text(row.get("target")),
        "ligand_id": _text(row.get("ligand_id")),
        "is_binder": _is_positive(row),
        "rank": rank,
        "within_target_rank": within_target_rank,
        "score": _float(row.get(score_col)),
        "diagnostics": _proxy_diagnostics(merged),
        "pose_physics_rescue_proxies": _pose_physics_rescue_proxies(merged),
        "source_features": {col: _float(merged.get(col)) for col in ANCHOR_PROXY_SOURCE_COLUMNS if col in merged},
    }


def _mean_diagnostics(rows: list[dict[str, Any]]) -> dict[str, float | None]:
    diagnostics = [row.get("diagnostics") for row in rows if isinstance(row.get("diagnostics"), dict)]
    return {
        key: _mean_present([diag.get(key) for diag in diagnostics])
        for key in ("conserved_anchor_proxy", "pose_physics_support", "prior_overreward_without_anchor")
    }


def _mean_atom_anchor_diagnostics(rows: list[dict[str, Any]]) -> dict[str, float | None]:
    diagnostics = [
        row.get("atom_anchor_diagnostics")
        for row in rows
        if isinstance(row.get("atom_anchor_diagnostics"), dict) and row.get("atom_anchor_diagnostics", {}).get("available")
    ]
    return {
        key: _mean_present([diag.get(key) for diag in diagnostics])
        for key in (
            "anchor_mean_distance_A",
            "anchor_min_distance_A",
            "anchor_p10_distance_A",
            "anchor_contact_fraction_le_4A",
            "anchor_contact_fraction_le_6A",
        )
    }


def _mean_rescue_proxy_diagnostics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    proxies = [
        row.get("pose_physics_rescue_proxies")
        for row in rows
        if isinstance(row.get("pose_physics_rescue_proxies"), dict)
    ]
    chemistry = [
        proxy.get("chemistry_heuristics")
        for proxy in proxies
        if isinstance(proxy.get("chemistry_heuristics"), dict)
    ]
    rmsd = [
        proxy.get("pose_preservation_rmsd_proxy")
        for proxy in proxies
        if isinstance(proxy.get("pose_preservation_rmsd_proxy"), dict)
    ]
    survival = [
        proxy.get("local_minimization_survival_proxy")
        for proxy in proxies
        if isinstance(proxy.get("local_minimization_survival_proxy"), dict)
    ]
    trajectory_pose = [
        proxy.get("trajectory_pose_preservation_proxy")
        for proxy in proxies
        if isinstance(proxy.get("trajectory_pose_preservation_proxy"), dict)
    ]
    trajectory_survival = [
        proxy.get("trajectory_survival_proxy")
        for proxy in proxies
        if isinstance(proxy.get("trajectory_survival_proxy"), dict)
    ]
    return {
        "pose_preservation_rmsd_available_count": sum(1 for item in rmsd if item.get("available")),
        "pose_preservation_rmsd_mean_A": _mean_present([item.get("value") for item in rmsd]),
        "pose_preservation_support_mean": _mean_present([item.get("support_proxy") for item in rmsd]),
        "local_minimization_survival_available_count": sum(1 for item in survival if item.get("available")),
        "local_minimization_survival_support_mean": _mean_present(
            [item.get("support_proxy") for item in survival]
        ),
        "trajectory_pose_preservation_available_count": sum(
            1 for item in trajectory_pose if item.get("available")
        ),
        "trajectory_pose_p90_frame_rmsd_mean_A": _mean_present(
            [item.get("p90_frame_rmsd_A") for item in trajectory_pose]
        ),
        "trajectory_pose_support_mean": _mean_present(
            [item.get("support_proxy") for item in trajectory_pose]
        ),
        "trajectory_survival_available_count": sum(
            1 for item in trajectory_survival if item.get("available")
        ),
        "trajectory_survival_support_mean": _mean_present(
            [item.get("support_proxy") for item in trajectory_survival]
        ),
        "smiles_available_count": sum(1 for item in chemistry if item.get("available")),
        "basic_amine_like_count": sum(1 for item in chemistry if item.get("basic_amine_like")),
        "tautomer_or_protonation_review_count": sum(
            1 for item in chemistry if item.get("tautomer_or_protonation_review_flag")
        ),
        "amine_anchor_support_mean": _mean_present(
            [item.get("amine_anchor_support_proxy") for item in chemistry]
        ),
    }


def _decoy_margin_summary(
    decoys: list[dict[str, Any]],
    positive_score: float | None,
    score_col: str,
    limit: int,
) -> dict[str, Any]:
    selected = decoys[:limit]
    margins = [
        (_float(row.get(score_col)) or 0.0) - positive_score
        for row in selected
        if positive_score is not None and _float(row.get(score_col)) is not None
    ]
    best_decoy = selected[0] if selected else {}
    return {
        "selection": f"top{limit}_lowest_score_drd2_decoys",
        "decoy_count": len(selected),
        "best_decoy_ligand_id": _text(best_decoy.get("ligand_id")),
        "best_decoy_score": _float(best_decoy.get(score_col)),
        "best_margin": margins[0] if margins else None,
        "mean_margin": _mean_present(margins),
    }


def _top_decoy_cluster_anchor_overanchoring_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    overanchored_rows = [
        row
        for row in rows
        if (
            isinstance(row.get("diagnostics"), dict)
            and (row.get("diagnostics", {}).get("conserved_anchor_proxy") or 0.0) >= 0.75
        )
        or (
            isinstance(row.get("atom_anchor_diagnostics"), dict)
            and row.get("atom_anchor_diagnostics", {}).get("available")
            and (row.get("atom_anchor_diagnostics", {}).get("anchor_contact_fraction_le_4A") or 0.0) >= 0.5
        )
    ]
    overanchored_without_amine = [
        row
        for row in overanchored_rows
        if not (
            isinstance(row.get("pose_physics_rescue_proxies"), dict)
            and isinstance(row.get("pose_physics_rescue_proxies", {}).get("chemistry_heuristics"), dict)
            and row.get("pose_physics_rescue_proxies", {})
            .get("chemistry_heuristics", {})
            .get("basic_amine_like")
        )
    ]
    return {
        "cluster_size": len(rows),
        "overanchored_decoy_count": len(overanchored_rows),
        "overanchored_without_basic_amine_count": len(overanchored_without_amine),
        "overanchoring_rule": (
            "conserved_anchor_proxy >= 0.75 or atom_anchor_contact_fraction_le_4A >= 0.5"
        ),
        "overanchored_ligand_ids": [row.get("ligand_id") for row in overanchored_rows],
        "overanchored_without_basic_amine_ligand_ids": [
            row.get("ligand_id") for row in overanchored_without_amine
        ],
        "atom_anchor_available_count": sum(
            1
            for row in rows
            if isinstance(row.get("atom_anchor_diagnostics"), dict)
            and row.get("atom_anchor_diagnostics", {}).get("available")
        ),
        "mean_atom_anchor_diagnostics": _mean_atom_anchor_diagnostics(rows),
        "mean_conserved_anchor_proxy": _mean_present(
            [
                row.get("diagnostics", {}).get("conserved_anchor_proxy")
                for row in rows
                if isinstance(row.get("diagnostics"), dict)
            ]
        ),
        "mean_prior_overreward_without_anchor": _mean_present(
            [
                row.get("diagnostics", {}).get("prior_overreward_without_anchor")
                for row in rows
                if isinstance(row.get("diagnostics"), dict)
            ]
        ),
        "mean_rescue_proxy_diagnostics": _mean_rescue_proxy_diagnostics(rows),
    }


def _chemistry_heuristics_from_compact(row: dict[str, Any]) -> dict[str, Any]:
    proxies = (
        row.get("pose_physics_rescue_proxies")
        if isinstance(row.get("pose_physics_rescue_proxies"), dict)
        else {}
    )
    chemistry = (
        proxies.get("chemistry_heuristics")
        if isinstance(proxies.get("chemistry_heuristics"), dict)
        else {}
    )
    return chemistry


def _trajectory_pose_from_compact(row: dict[str, Any]) -> dict[str, Any]:
    proxies = (
        row.get("pose_physics_rescue_proxies")
        if isinstance(row.get("pose_physics_rescue_proxies"), dict)
        else {}
    )
    trajectory_pose = (
        proxies.get("trajectory_pose_preservation_proxy")
        if isinstance(proxies.get("trajectory_pose_preservation_proxy"), dict)
        else {}
    )
    return trajectory_pose


def _trajectory_survival_from_compact(row: dict[str, Any]) -> dict[str, Any]:
    proxies = (
        row.get("pose_physics_rescue_proxies")
        if isinstance(row.get("pose_physics_rescue_proxies"), dict)
        else {}
    )
    trajectory_survival = (
        proxies.get("trajectory_survival_proxy")
        if isinstance(proxies.get("trajectory_survival_proxy"), dict)
        else {}
    )
    return trajectory_survival


def _row_acidic_overanchor_validity(
    row: dict[str, Any],
    chemistry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    diagnostics = row.get("diagnostics") if isinstance(row.get("diagnostics"), dict) else {}
    atom_anchor = (
        row.get("atom_anchor_diagnostics")
        if isinstance(row.get("atom_anchor_diagnostics"), dict)
        else {}
    )
    chemistry = chemistry if isinstance(chemistry, dict) else _chemistry_heuristics_from_compact(row)
    basic_amine_like = bool(chemistry.get("basic_amine_like"))
    conserved_anchor_proxy = _float(diagnostics.get("conserved_anchor_proxy"))
    atom_contact_le_4 = _float(atom_anchor.get("anchor_contact_fraction_le_4A"))
    atom_min_distance = _float(atom_anchor.get("anchor_min_distance_A"))
    proxy_overanchor = (
        conserved_anchor_proxy is not None
        and conserved_anchor_proxy >= ACIDIC_OVERANCHOR_PROXY_THRESHOLD
    )
    atom_overanchor = (
        bool(atom_anchor.get("available"))
        and atom_contact_le_4 is not None
        and atom_contact_le_4 >= ACIDIC_OVERANCHOR_ATOM_CONTACT_THRESHOLD
    )
    acidic_contact_pressure = bool(proxy_overanchor or atom_overanchor)
    invalid_overanchor_without_basic_amine = bool(acidic_contact_pressure and not basic_amine_like)
    return {
        "conserved_anchor_proxy": conserved_anchor_proxy,
        "atom_anchor_available": bool(atom_anchor.get("available")),
        "anchor_min_distance_A": atom_min_distance,
        "anchor_contact_fraction_le_4A": atom_contact_le_4,
        "acidic_anchor_window_valid": (
            atom_min_distance is not None and 2.0 <= atom_min_distance <= 6.0
        )
        if atom_anchor.get("available")
        else None,
        "acidic_overanchor_proxy_flag": bool(proxy_overanchor),
        "acidic_overanchor_atom_flag": bool(atom_overanchor),
        "raw_acidic_contact_pressure_flag": acidic_contact_pressure,
        "charge_complemented_anchor_flag": bool(acidic_contact_pressure and basic_amine_like),
        "acidic_overanchor_flag": invalid_overanchor_without_basic_amine,
        "invalid_overanchor_without_basic_amine": invalid_overanchor_without_basic_amine,
        "overanchor_rule": (
            "invalid overanchor requires acidic contact pressure without basic/cationic amine support; "
            f"contact pressure is conserved_anchor_proxy >= {ACIDIC_OVERANCHOR_PROXY_THRESHOLD} or "
            f"atom_anchor_contact_fraction_le_4A >= {ACIDIC_OVERANCHOR_ATOM_CONTACT_THRESHOLD}"
        ),
    }


def _row_prior_pressure(row: dict[str, Any]) -> dict[str, Any]:
    diagnostics = row.get("diagnostics") if isinstance(row.get("diagnostics"), dict) else {}
    source_features = row.get("source_features") if isinstance(row.get("source_features"), dict) else {}
    prior_pressure = _float(source_features.get("residual_shadow_prior_pressure"))
    prior_overreward = _float(diagnostics.get("prior_overreward_without_anchor"))
    ligand_affinity_hint = _float(source_features.get("ligand_affinity_hint"))
    ligand_onsps_norm = _float(source_features.get("ligand_onsps_norm"))
    return {
        "residual_shadow_prior_pressure": prior_pressure,
        "prior_overreward_without_anchor": prior_overreward,
        "ligand_affinity_hint": ligand_affinity_hint,
        "ligand_onsps_norm": ligand_onsps_norm,
        "prior_high_flag": bool(
            (prior_pressure is not None and prior_pressure >= LIGAND_PRIOR_HIGH_THRESHOLD)
            or (
                prior_overreward is not None
                and prior_overreward >= PRIOR_OVERREWARD_HIGH_THRESHOLD
            )
        ),
        "prior_high_rule": (
            f"residual_shadow_prior_pressure >= {LIGAND_PRIOR_HIGH_THRESHOLD} or "
            f"prior_overreward_without_anchor >= {PRIOR_OVERREWARD_HIGH_THRESHOLD}"
        ),
    }


def _motif_row_summary(row: dict[str, Any]) -> dict[str, Any]:
    chemistry = _chemistry_heuristics_from_compact(row)
    trajectory_pose = _trajectory_pose_from_compact(row)
    trajectory_survival = _trajectory_survival_from_compact(row)
    acidic = _row_acidic_overanchor_validity(row, chemistry)
    prior = _row_prior_pressure(row)
    return {
        "ligand_id": row.get("ligand_id", ""),
        "cationic_basic_amine_support": {
            "available": bool(chemistry.get("available")),
            "basic_amine_like": bool(chemistry.get("basic_amine_like")),
            "explicit_cationic_n": bool(chemistry.get("explicit_cationic_n")),
            "amine_anchor_support_proxy": _float(chemistry.get("amine_anchor_support_proxy")),
            "tautomer_or_protonation_review_flag": bool(
                chemistry.get("tautomer_or_protonation_review_flag")
            ),
        },
        "acidic_anchor_window_overanchor_validity": acidic,
        "trajectory_pose_survival_proxy": {
            "pose_available": bool(trajectory_pose.get("available")),
            "pose_p90_frame_rmsd_A": _float(trajectory_pose.get("p90_frame_rmsd_A")),
            "pose_support_proxy": _float(trajectory_pose.get("support_proxy")),
            "survival_available": bool(trajectory_survival.get("available")),
            "survival_support_proxy": _float(trajectory_survival.get("support_proxy")),
        },
        "ligand_prior_pressure": prior,
    }


def _motif_cluster_component_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    row_summaries = [_motif_row_summary(row) for row in rows]
    chemistry = [row["cationic_basic_amine_support"] for row in row_summaries]
    acidic = [row["acidic_anchor_window_overanchor_validity"] for row in row_summaries]
    trajectory = [row["trajectory_pose_survival_proxy"] for row in row_summaries]
    prior = [row["ligand_prior_pressure"] for row in row_summaries]
    hard_decoys = [
        row
        for row, chem, acid, prior_row in zip(rows, chemistry, acidic, prior)
        if (
            not chem.get("basic_amine_like")
            and acid.get("acidic_overanchor_flag")
            and prior_row.get("prior_high_flag")
        )
    ]
    return {
        "size": len(rows),
        "cationic_basic_amine_support": {
            "smiles_available_count": sum(1 for item in chemistry if item.get("available")),
            "basic_amine_like_count": sum(1 for item in chemistry if item.get("basic_amine_like")),
            "amine_anchor_support_mean": _mean_present(
                [item.get("amine_anchor_support_proxy") for item in chemistry]
            ),
        },
        "acidic_anchor_window_overanchor_validity": {
            "acidic_overanchor_count": sum(1 for item in acidic if item.get("acidic_overanchor_flag")),
            "acidic_overanchor_fraction": (
                sum(1 for item in acidic if item.get("acidic_overanchor_flag")) / len(rows)
                if rows
                else None
            ),
            "acidic_anchor_window_valid_count": sum(
                1 for item in acidic if item.get("acidic_anchor_window_valid") is True
            ),
            "conserved_anchor_proxy_mean": _mean_present(
                [item.get("conserved_anchor_proxy") for item in acidic]
            ),
            "anchor_contact_fraction_le_4A_mean": _mean_present(
                [item.get("anchor_contact_fraction_le_4A") for item in acidic]
            ),
        },
        "trajectory_pose_survival_proxy": {
            "pose_available_count": sum(1 for item in trajectory if item.get("pose_available")),
            "pose_support_mean": _mean_present([item.get("pose_support_proxy") for item in trajectory]),
            "pose_p90_frame_rmsd_mean_A": _mean_present(
                [item.get("pose_p90_frame_rmsd_A") for item in trajectory]
            ),
            "survival_available_count": sum(1 for item in trajectory if item.get("survival_available")),
            "survival_support_mean": _mean_present(
                [item.get("survival_support_proxy") for item in trajectory]
            ),
        },
        "ligand_prior_pressure": {
            "prior_high_count": sum(1 for item in prior if item.get("prior_high_flag")),
            "prior_high_fraction": (
                sum(1 for item in prior if item.get("prior_high_flag")) / len(rows)
                if rows
                else None
            ),
            "residual_shadow_prior_pressure_mean": _mean_present(
                [item.get("residual_shadow_prior_pressure") for item in prior]
            ),
            "prior_overreward_without_anchor_mean": _mean_present(
                [item.get("prior_overreward_without_anchor") for item in prior]
            ),
        },
        "basic_amine_absent_acidic_overanchor_prior_high_cluster": {
            "count": len(hard_decoys),
            "ligand_ids": [row.get("ligand_id") for row in hard_decoys],
            "coverage": (len(hard_decoys) / len(rows)) if rows else None,
            "rule": (
                "basic_amine_like is false and acidic_overanchor_flag is true and prior_high_flag is true"
            ),
        },
        "rows": row_summaries,
    }


def _drd2_label_free_motif_aware_diagnostic(
    drd2_pose: dict[str, Any],
    pairwise: dict[str, Any],
) -> dict[str, Any]:
    positive = drd2_pose.get("positive") if isinstance(drd2_pose.get("positive"), dict) else {}
    cluster = (
        drd2_pose.get("top_decoy_cluster")
        if isinstance(drd2_pose.get("top_decoy_cluster"), dict)
        else {}
    )
    cluster_rows = cluster.get("rows") if isinstance(cluster.get("rows"), list) else []
    positive_summary = _motif_row_summary(positive) if positive else {}
    cluster_summary = _motif_cluster_component_summary(
        [row for row in cluster_rows if isinstance(row, dict)]
    )
    hard_cluster = cluster_summary.get(
        "basic_amine_absent_acidic_overanchor_prior_high_cluster", {}
    )
    return {
        "packet_name": DRD2_LABEL_FREE_MOTIF_SUBLANE,
        "sublane": DRD2_LABEL_FREE_MOTIF_SUBLANE,
        "diagnostic_only": True,
        "label_free": True,
        "claim_promotion_allowed": False,
        "scorer_apply_allowed": False,
        "router_claim_allowed": False,
        "platform_claim_allowed": False,
        "threshold_relaxation_allowed": False,
        "target_identity_feature_allowed": False,
        "metadata": {
            "diagnostic_only": True,
            "label_free": True,
            "sublane": DRD2_LABEL_FREE_MOTIF_SUBLANE,
            "claim_promotion_allowed": False,
            "scorer_apply_allowed": False,
            "router_claim_allowed": False,
            "platform_claim_allowed": False,
            "forbidden_live_features": [
                "target",
                "is_binder",
                "rank",
                "within_target_rank",
                "ligand_id",
                "reference_binding",
                "reference_binding_kcal_mol",
            ],
            "allowed_basis": [
                "existing_stage3_pose_physics_proxy_columns",
                "existing_smiles_basic_amine_heuristic",
                "existing_trajectory_npz_pose_proxy_if_present",
                "existing_trajectory_survival_proxy_columns_if_present",
            ],
            "source_pairwise_slice": pairwise.get("slice", ""),
            "comparison": "positive_vs_top_decoy_cluster",
        },
        "positive_vs_top_decoy_cluster": {
            "positive": positive_summary,
            "top_decoy_cluster": cluster_summary,
            "basic_amine_absent_acidic_overanchor_prior_high_cluster_count": hard_cluster.get("count", 0),
            "basic_amine_absent_acidic_overanchor_prior_high_cluster_ligand_ids": hard_cluster.get(
                "ligand_ids", []
            ),
            "basic_amine_absent_acidic_overanchor_prior_high_cluster_coverage": hard_cluster.get(
                "coverage"
            ),
        },
        "interpretation": (
            "Label-free DRD2-local motif diagnostic for the class A aminergic/opioid orthosteric sublane. "
            "It separates basic/cationic amine support, acidic-anchor overanchor validity, trajectory pose/survival, "
            "and ligand-prior pressure, and compares the positive with the top decoy cluster without authorizing claims."
        ),
    }


def _acidic_anchor_overcontact_probe(
    decoys: list[dict[str, Any]],
    stage3_lookup: dict[tuple[str, str], dict[str, Any]],
    *,
    limit: int = 50,
) -> dict[str, Any]:
    selected = decoys[:limit]
    diagnostics: list[dict[str, Any]] = []
    for row in selected:
        key = (_text(row.get("target")), _text(row.get("ligand_id")))
        atom_diag = _atom_anchor_diagnostics({**row, **stage3_lookup.get(key, {})})
        if isinstance(atom_diag, dict) and atom_diag.get("available"):
            diagnostics.append(atom_diag)
    min_lt_3 = [
        diag
        for diag in diagnostics
        if (_float(diag.get("anchor_min_distance_A")) is not None)
        and (_float(diag.get("anchor_min_distance_A")) or 999.0) < 3.0
    ]
    p10_lt_3 = [
        diag
        for diag in diagnostics
        if (_float(diag.get("anchor_p10_distance_A")) is not None)
        and (_float(diag.get("anchor_p10_distance_A")) or 999.0) < 3.0
    ]
    mean_contact_le_4 = _mean_present(
        [_float(diag.get("anchor_contact_fraction_le_4A")) for diag in diagnostics]
    )
    return {
        "diagnostic_only": True,
        "probe_name": "acidic_anchor_overcontact_pressure_probe",
        "selection": f"top{limit}_lowest_score_drd2_decoys",
        "selected_decoy_count": len(selected),
        "atom_anchor_available_count": len(diagnostics),
        "anchor_min_distance_lt_3A_count": len(min_lt_3),
        "anchor_p10_distance_lt_3A_count": len(p10_lt_3),
        "anchor_min_distance_lt_3A_fraction": (len(min_lt_3) / len(diagnostics)) if diagnostics else None,
        "anchor_p10_distance_lt_3A_fraction": (len(p10_lt_3) / len(diagnostics)) if diagnostics else None,
        "mean_anchor_contact_fraction_le_4A": mean_contact_le_4,
        "claim_promotion_allowed": False,
        "scorer_apply_allowed": False,
        "interpretation": (
            "Use only as a target-agnostic acidic-anchor overcontact diagnostic. A future scorer term must be "
            "shadow/replay reviewed and must not use target identity, labels, ranks, ligand IDs, or reference values."
        ),
    }


def _parse_pdb_anchor_template(path: str | Path | None) -> dict[str, Any]:
    pdb_path = _resolve(path)
    if pdb_path is None or not pdb_path.exists():
        return {"available": False, "reason": "native_pdb_missing", "anchor_atom_indices": []}
    protein_atoms: list[dict[str, Any]] = []
    acid_atoms: list[dict[str, Any]] = []
    het_groups: dict[tuple[str, str, str], list[list[float]]] = {}
    with pdb_path.open("r", encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            if line.startswith("ATOM"):
                atom_index = len(protein_atoms)
                atom_name = _text(line[12:16]).upper()
                resn = _text(line[17:20]).upper()
                chain = _text(line[21:22])
                resi = _text(line[22:26])
                try:
                    xyz = [float(line[30:38]), float(line[38:46]), float(line[46:54])]
                except Exception:
                    continue
                atom = {
                    "atom_index": atom_index,
                    "atom_name": atom_name,
                    "resn": resn,
                    "chain": chain,
                    "resi": resi,
                    "xyz": xyz,
                }
                protein_atoms.append(atom)
                if atom_name in ACID_SIDECHAIN_ATOMS.get(resn, set()):
                    acid_atoms.append(atom)
            elif line.startswith("HETATM"):
                resn = _text(line[17:20]).upper()
                if resn in EXCLUDED_NATIVE_LIGAND_RESN:
                    continue
                chain = _text(line[21:22])
                resi = _text(line[22:26])
                try:
                    xyz = [float(line[30:38]), float(line[38:46]), float(line[46:54])]
                except Exception:
                    continue
                het_groups.setdefault((resn, chain, resi), []).append(xyz)
    if not acid_atoms or not het_groups:
        return {"available": False, "reason": "acid_or_native_ligand_missing", "anchor_atom_indices": []}
    acid_xyz = np.asarray([atom["xyz"] for atom in acid_atoms], dtype=float)
    best: tuple[float, tuple[str, str, str], list[list[float]]] | None = None
    for group_key, coords in het_groups.items():
        if len(coords) < 5:
            continue
        lig_xyz = np.asarray(coords, dtype=float)
        min_dist = float(np.linalg.norm(acid_xyz[:, None, :] - lig_xyz[None, :, :], axis=2).min())
        if best is None or min_dist < best[0]:
            best = (min_dist, group_key, coords)
    if best is None:
        return {"available": False, "reason": "native_ligand_group_not_selected", "anchor_atom_indices": []}
    native_min_dist, native_ligand_key, native_ligand_coords = best
    native_ligand_xyz = np.asarray(native_ligand_coords, dtype=float)
    ranked_acids = sorted(
        [
            (
                float(np.linalg.norm(native_ligand_xyz - np.asarray(atom["xyz"], dtype=float), axis=1).min()),
                atom,
            )
            for atom in acid_atoms
        ],
        key=lambda item: (
            item[0],
            item[1]["resn"],
            item[1]["chain"],
            item[1]["resi"],
            item[1]["atom_name"],
        ),
    )
    anchor_residue = ranked_acids[0][1]
    anchor_atoms = [
        atom
        for atom in acid_atoms
        if atom["resn"] == anchor_residue["resn"]
        and atom["chain"] == anchor_residue["chain"]
        and atom["resi"] == anchor_residue["resi"]
    ]
    return {
        "available": True,
        "native_pdb": str(pdb_path),
        "native_ligand_resn": native_ligand_key[0],
        "native_ligand_chain": native_ligand_key[1],
        "native_ligand_resi": native_ligand_key[2],
        "native_ligand_min_acid_distance_A": native_min_dist,
        "anchor_resn": anchor_residue["resn"],
        "anchor_chain": anchor_residue["chain"],
        "anchor_resi": anchor_residue["resi"],
        "anchor_atom_names": [atom["atom_name"] for atom in anchor_atoms],
        "anchor_atom_indices": [int(atom["atom_index"]) for atom in anchor_atoms],
    }


def _atom_anchor_diagnostics(row: dict[str, Any]) -> dict[str, Any]:
    trajectory_npz = _text(row.get("trajectory_npz"))
    native_pdb = _text(row.get("protein_structure_source_path"))
    template = _parse_pdb_anchor_template(native_pdb)
    if not template.get("available"):
        return {
            "available": False,
            "reason": template.get("reason", "anchor_template_unavailable"),
            "native_pdb": native_pdb,
            "trajectory_npz": trajectory_npz,
        }
    npz_path = _resolve(trajectory_npz)
    if npz_path is None or not npz_path.exists():
        return {
            "available": False,
            "reason": "trajectory_npz_missing",
            "native_pdb": native_pdb,
            "trajectory_npz": trajectory_npz,
            "anchor_template": template,
        }
    try:
        with np.load(str(npz_path), allow_pickle=False) as npz:
            ligand_frames = np.asarray(npz["ligand_frames"], dtype=float)
            protein_atom_frames = np.asarray(npz["protein_atom_frames"], dtype=float)
    except Exception as exc:
        return {
            "available": False,
            "reason": f"trajectory_npz_unreadable:{type(exc).__name__}",
            "native_pdb": native_pdb,
            "trajectory_npz": trajectory_npz,
            "anchor_template": template,
        }
    anchor_indices = [idx for idx in template.get("anchor_atom_indices", []) if 0 <= int(idx) < protein_atom_frames.shape[1]]
    if ligand_frames.size == 0 or protein_atom_frames.size == 0 or not anchor_indices:
        return {
            "available": False,
            "reason": "ligand_or_anchor_frames_missing",
            "native_pdb": native_pdb,
            "trajectory_npz": trajectory_npz,
            "anchor_template": template,
        }
    anchor_frames = protein_atom_frames[:, anchor_indices, :]
    distances = np.linalg.norm(
        ligand_frames[:, :, None, :] - anchor_frames[:, None, :, :],
        axis=3,
    ).min(axis=(1, 2))
    return {
        "available": True,
        "basis": "native_pdb_acidic_anchor_plus_trajectory_npz",
        "native_pdb": native_pdb,
        "trajectory_npz": trajectory_npz,
        "anchor_template": template,
        "frame_count": int(len(distances)),
        "anchor_min_distance_A": float(np.min(distances)),
        "anchor_mean_distance_A": float(np.mean(distances)),
        "anchor_p10_distance_A": float(np.percentile(distances, 10)),
        "anchor_contact_fraction_le_4A": float(np.mean(distances <= 4.0)),
        "anchor_contact_fraction_le_6A": float(np.mean(distances <= 6.0)),
    }


def _drd2_pose_physics_diagnostics(
    rows: list[dict[str, Any]],
    stage3_lookup: dict[tuple[str, str], dict[str, Any]],
    global_ranks: dict[tuple[str, str], int],
    within_ranks: dict[tuple[str, str], int],
    score_col: str,
) -> dict[str, Any]:
    drd2_rows = [row for row in rows if _is_drd2_target(_text(row.get("target")))]
    positives = [row for row in drd2_rows if _is_positive(row)]
    decoys = [row for row in drd2_rows if not _is_positive(row) and _float(row.get(score_col)) is not None]
    positives.sort(
        key=lambda row: (
            global_ranks.get((_text(row.get("target")), _text(row.get("ligand_id"))), 10**12),
            _text(row.get("ligand_id")),
        )
    )
    decoys.sort(key=lambda row: (_float(row.get(score_col)) or 0.0, _text(row.get("ligand_id"))))

    positive = positives[0] if positives else {}
    positive_key = (_text(positive.get("target")), _text(positive.get("ligand_id"))) if positive else ("", "")
    cluster_rows = []
    for row in decoys[:12]:
        key = (_text(row.get("target")), _text(row.get("ligand_id")))
        cluster_rows.append(
            _compact_drd2_row(
                row,
                stage3_lookup.get(key, {}),
                rank=global_ranks.get(key),
                within_target_rank=within_ranks.get(key),
                score_col=score_col,
            )
        )

    positive_payload = (
        _compact_drd2_row(
            positive,
            stage3_lookup.get(positive_key, {}),
            rank=global_ranks.get(positive_key),
            within_target_rank=within_ranks.get(positive_key),
            score_col=score_col,
        )
        if positive
        else {}
    )
    if positive_payload:
        positive_payload["atom_anchor_diagnostics"] = _atom_anchor_diagnostics(
            {**positive, **stage3_lookup.get(positive_key, {})}
        )
    for row in cluster_rows:
        key = (_text(row.get("target")), _text(row.get("ligand_id")))
        row["atom_anchor_diagnostics"] = _atom_anchor_diagnostics(
            {**row, **stage3_lookup.get(key, {})}
        )

    return {
        "slice": "DRD2_pose_physics_conserved_anchor_proxy",
        "metadata": {
            "diagnostic_only": True,
            "claim_promotion_allowed": False,
            "scorer_apply_allowed": False,
            "feature_basis": "stage3_csv_proxy_not_atom_anchor",
            "proxy_note": (
                "No atom-resolved conserved GPCR anchor annotations are available in this packet; "
                "conserved_anchor_proxy, pose_physics_support, and prior_overreward_without_anchor are "
                "computed only from shared stage3 CSV pose/physics/prior columns."
            ),
            "proxy_source_columns": ANCHOR_PROXY_SOURCE_COLUMNS,
            "score_column": score_col,
        },
        "positive": positive_payload,
        "top_decoy_cluster": {
            "selection": "lowest_score_drd2_decoys_from_latest_ranking_rows",
            "size": len(cluster_rows),
            "rows": cluster_rows,
            "mean_diagnostics": _mean_diagnostics(cluster_rows),
            "mean_atom_anchor_diagnostics": _mean_atom_anchor_diagnostics(cluster_rows),
            "mean_rescue_proxy_diagnostics": _mean_rescue_proxy_diagnostics(cluster_rows),
        },
    }


def _drd2_target_internal_pairwise_diagnostic(
    rows: list[dict[str, Any]],
    stage3_lookup: dict[tuple[str, str], dict[str, Any]],
    global_ranks: dict[tuple[str, str], int],
    within_ranks: dict[tuple[str, str], int],
    score_col: str,
) -> dict[str, Any]:
    drd2_rows = [row for row in rows if _is_drd2_target(_text(row.get("target")))]
    positives = [row for row in drd2_rows if _is_positive(row) and _float(row.get(score_col)) is not None]
    decoys = [row for row in drd2_rows if not _is_positive(row) and _float(row.get(score_col)) is not None]
    positives.sort(
        key=lambda row: (
            within_ranks.get((_text(row.get("target")), _text(row.get("ligand_id"))), 10**12),
            _text(row.get("ligand_id")),
        )
    )
    decoys.sort(key=lambda row: (_float(row.get(score_col)) or 0.0, _text(row.get("ligand_id"))))

    positive = positives[0] if positives else {}
    positive_key = (_text(positive.get("target")), _text(positive.get("ligand_id"))) if positive else ("", "")
    positive_score = _float(positive.get(score_col)) if positive else None
    decoys_above_positive = [
        row
        for row in decoys
        if positive_score is not None and (_float(row.get(score_col)) or 0.0) < positive_score
    ]
    pairwise_wins = [
        row
        for row in decoys
        if positive_score is not None and (_float(row.get(score_col)) or 0.0) > positive_score
    ]

    cluster_rows: list[dict[str, Any]] = []
    for row in decoys[:12]:
        key = (_text(row.get("target")), _text(row.get("ligand_id")))
        cluster_row = _compact_drd2_row(
            row,
            stage3_lookup.get(key, {}),
            rank=global_ranks.get(key),
            within_target_rank=within_ranks.get(key),
            score_col=score_col,
        )
        cluster_row["atom_anchor_diagnostics"] = _atom_anchor_diagnostics({**row, **stage3_lookup.get(key, {})})
        cluster_rows.append(cluster_row)

    positive_payload = (
        _compact_drd2_row(
            positive,
            stage3_lookup.get(positive_key, {}),
            rank=global_ranks.get(positive_key),
            within_target_rank=within_ranks.get(positive_key),
            score_col=score_col,
        )
        if positive
        else {}
    )

    return {
        "slice": "DRD2_target_internal_pairwise_rank_failure",
        "metadata": {
            "diagnostic_only": True,
            "replay_only": True,
            "claim_promotion_allowed": False,
            "scorer_apply_allowed": False,
            "score_column": score_col,
            "score_order": "lower_score_ranks_higher",
            "forbidden_live_features": [
                "target",
                "is_binder",
                "rank",
                "within_target_rank",
                "ligand_id",
                "reference_binding",
                "reference_binding_kcal_mol",
            ],
        },
        "positive": positive_payload,
        "decoy_count": len(decoys),
        "decoys_above_positive_count": len(decoys_above_positive),
        "decoys_above_positive_fraction": (len(decoys_above_positive) / len(decoys)) if decoys else None,
        "decoys_above_positive_ligand_ids": [_text(row.get("ligand_id")) for row in decoys_above_positive],
        "top12_decoy_margin_vs_positive": _decoy_margin_summary(decoys, positive_score, score_col, 12),
        "top50_decoy_margin_vs_positive": _decoy_margin_summary(decoys, positive_score, score_col, 50),
        "pairwise_win_rate": (len(pairwise_wins) / len(decoys)) if decoys else None,
        "pairwise_win_count": len(pairwise_wins),
        "top_decoy_cluster_anchor_overanchoring_summary": _top_decoy_cluster_anchor_overanchoring_summary(
            cluster_rows
        ),
        "acidic_anchor_overcontact_probe": _acidic_anchor_overcontact_probe(
            decoys,
            stage3_lookup,
            limit=50,
        ),
        "shadow_replay_snapshot": {
            "not_claim_evidence": True,
            "ci_low_computed": True,
            "base_r2_pr_auc": 0.5186945103743427,
            "base_r2_pr_auc_ci_low": 0.1485815545422209,
            "base_r2_top20_hit_rate": 0.25,
            "family_anchor_v2_shadow_pr_auc": 0.5767474245351905,
            "family_anchor_v2_shadow_pr_auc_ci_low": 0.21066694653866244,
            "family_anchor_v2_shadow_pr_auc_ci_low_threshold": 0.45,
            "family_anchor_v2_shadow_top20_hit_rate": 0.25,
            "family_anchor_v2_shadow_drd2_global_rank": 8562,
            "family_anchor_v2_shadow_drd2_target_rank": 2435,
            "family_anchor_v2_shadow_drd2_decoys_above_positive_count": 2434,
            "family_anchor_v2_shadow_drd2_pairwise_win_rate": 0.7565756575657565,
            "family_anchor_v2_shadow_mean_mismatch_pressure_positive": 0.0,
            "family_anchor_v2_shadow_mean_mismatch_pressure_decoy": 0.8541410783206624,
            "family_anchor_v2_shadow_claim_review_status": "blocked_ci_low_below_threshold",
        },
        "guarded_validation_prep": {
            "ready_for_guarded_apply": False,
            "blockers": [
                "diagnostic_only_replay_packet",
                "shadow_replay_pr_auc_ci_low_below_threshold",
                "full_guarded_validation_missing",
            ],
            "required_next_evidence": [
                "target_internal_pairwise_replay_review",
                "guarded_apply_candidate_review",
                "full_100k_ci_low_top20_claim_review_green",
            ],
            "threshold_relaxation_allowed": False,
            "fake_pass_allowed": False,
            "full_100k_rerun_allowed_in_this_task": False,
        },
    }


def _ci_summary(ci_payload: dict[str, Any]) -> dict[str, Any]:
    summary = ci_payload.get("summary") if isinstance(ci_payload.get("summary"), dict) else {}
    stage6 = (
        ci_payload.get("stages", {}).get("stage6_operational_gate", {})
        if isinstance(ci_payload.get("stages"), dict)
        else {}
    )
    metrics_unique = ci_payload.get("metrics_unique") if isinstance(ci_payload.get("metrics_unique"), dict) else {}
    metrics_ci_unique = ci_payload.get("metrics_ci_unique") if isinstance(ci_payload.get("metrics_ci_unique"), dict) else {}
    topk_unique = ci_payload.get("topk_unique") if isinstance(ci_payload.get("topk_unique"), list) else []
    top20_hit_rate = None
    for row in topk_unique:
        if isinstance(row, dict) and int(_float(row.get("k")) or 0) == 20:
            top20_hit_rate = _float(row.get("hit_rate"))
            break
    ci_low_from_stage5 = None
    if isinstance(metrics_ci_unique.get("pr_auc"), dict):
        ci_low_from_stage5 = _float(metrics_ci_unique.get("pr_auc", {}).get("low"))
    return {
        "ranking_pr_auc": (
            _float(summary.get("ranking_pr_auc"))
            if _float(summary.get("ranking_pr_auc")) is not None
            else _float(stage6.get("ranking_pr_auc"))
            if _float(stage6.get("ranking_pr_auc")) is not None
            else _float(metrics_unique.get("pr_auc"))
        ),
        "ranking_pr_auc_ci_low": (
            _float(summary.get("ranking_pr_auc_ci_low"))
            if _float(summary.get("ranking_pr_auc_ci_low")) is not None
            else _float(stage6.get("ranking_pr_auc_ci_low"))
            if _float(stage6.get("ranking_pr_auc_ci_low")) is not None
            else ci_low_from_stage5
        ),
        "ranking_topk_hit_rate": (
            _float(summary.get("ranking_topk_hit_rate"))
            if _float(summary.get("ranking_topk_hit_rate")) is not None
            else _float(stage6.get("ranking_topk_hit_rate"))
            if _float(stage6.get("ranking_topk_hit_rate")) is not None
            else top20_hit_rate
        ),
        "ranking_positive_count": (
            _float(summary.get("ranking_positive_count"))
            if _float(summary.get("ranking_positive_count")) is not None
            else _float(stage6.get("ranking_positive_count"))
            if _float(stage6.get("ranking_positive_count")) is not None
            else _float(metrics_unique.get("positive_count"))
        ),
        "ci_low_threshold": _float(summary.get("threshold")) or CI_LOW_THRESHOLD,
        "top20_threshold": TOP20_THRESHOLD,
    }


def _ci_low_stability_metadata(ci: dict[str, Any]) -> dict[str, Any]:
    base_pr_auc = _float(ci.get("ranking_pr_auc"))
    base_ci_low = _float(ci.get("ranking_pr_auc_ci_low"))
    threshold = _float(ci.get("ci_low_threshold")) or CI_LOW_THRESHOLD
    v2_shadow_pr_auc = 0.5767474245351905
    v2_shadow_ci_low = 0.21066694653866244
    v2_shadow_top20_hit_rate = 0.25
    v2_shadow_drd2_decoys_above_positive_count = 2434
    v2_shadow_drd2_pairwise_win_rate = 0.7565756575657565
    ci_low_computed = base_ci_low is not None
    base_gap = (threshold - base_ci_low) if ci_low_computed else None
    v2_shadow_gap = threshold - v2_shadow_ci_low
    blocked = (not ci_low_computed) or (base_ci_low < threshold) or (v2_shadow_ci_low < threshold)
    blockers: list[str] = []
    if not ci_low_computed:
        blockers.append("bootstrap_pr_auc_ci_low_missing")
    if base_ci_low is None or base_ci_low < threshold:
        blockers.append("base_bootstrap_pr_auc_ci_low_below_threshold")
    if v2_shadow_ci_low < threshold:
        blockers.append("v2_shadow_bootstrap_pr_auc_ci_low_below_threshold")
    if blockers:
        blockers.append("do_not_promote_from_point_pr_auc")
    return {
        "diagnostic_only": True,
        "ci_low_computed": ci_low_computed,
        "claim_promotion_allowed": False,
        "scorer_apply_allowed": False,
        "threshold_relaxation_allowed": False,
        "base_pr_auc": base_pr_auc,
        "base_pr_auc_ci_low": base_ci_low,
        "base_ci_low_gap_to_threshold": base_gap if base_ci_low is None or base_ci_low < threshold else 0.0,
        "v2_shadow_pr_auc": v2_shadow_pr_auc,
        "v2_shadow_pr_auc_ci_low": v2_shadow_ci_low,
        "v2_shadow_top20_hit_rate": v2_shadow_top20_hit_rate,
        "v2_shadow_ci_low_gap_to_threshold": v2_shadow_gap,
        "v2_shadow_drd2_decoys_above_positive_count": v2_shadow_drd2_decoys_above_positive_count,
        "v2_shadow_drd2_pairwise_win_rate": v2_shadow_drd2_pairwise_win_rate,
        "ci_low_threshold": threshold,
        "ci_low_gap_to_threshold": max(
            value
            for value in [
                base_gap if base_gap is not None else threshold,
                v2_shadow_gap,
                0.0,
            ]
        )
        if blocked
        else 0.0,
        "ci_low_status": "blocked_below_threshold" if blocked else "green",
        "recommended_next_action": "gpcr_core_family_anchor_ci_stability_v3_diagnostic_only",
        "blockers": sorted(set(blockers)),
        "stability_hypotheses": [
            "bootstrap_positive_support_instability",
            "point_pr_auc_improvement_not_enough_for_claim",
            "target_agnostic_v2_terms_need_ci_low_replay_review",
        ],
    }


def _latest_v4_replay_review() -> dict[str, Any]:
    eval_path = _resolve(DEFAULT_V4_REPLAY_EVAL_JSON)
    summary_path = _resolve(DEFAULT_V4_REPLAY_SUMMARY_JSON)
    if eval_path is None or not eval_path.exists():
        return {"available": False}
    eval_payload = _read_json(eval_path)
    summary_payload = _read_json(summary_path) if summary_path and summary_path.exists() else {}
    metrics = eval_payload.get("metrics_unique") if isinstance(eval_payload.get("metrics_unique"), dict) else {}
    ci = eval_payload.get("metrics_ci_unique") if isinstance(eval_payload.get("metrics_ci_unique"), dict) else {}
    pr_auc_ci = ci.get("pr_auc") if isinstance(ci.get("pr_auc"), dict) else {}
    top20 = None
    for row in eval_payload.get("topk_unique", []):
        if isinstance(row, dict) and int(row.get("k") or 0) == 20:
            top20 = _float(row.get("hit_rate"))
            break
    residual = (
        summary_payload.get("residual_prototype")
        if isinstance(summary_payload.get("residual_prototype"), dict)
        else {}
    )
    pr_auc = _float(metrics.get("pr_auc"))
    pr_auc_ci_low = _float(pr_auc_ci.get("low"))
    status = "reject_evidence"
    if (
        pr_auc is not None
        and pr_auc > 0.5767474245351905
        and pr_auc_ci_low is not None
        and pr_auc_ci_low > 0.21066694653866244
        and top20 is not None
        and top20 >= 0.25
    ):
        status = "shadow_replay_improved_needs_guarded_review"
    return {
        "available": True,
        "status": status,
        "eval_json": str(eval_path),
        "summary_json": str(summary_path) if summary_path else "",
        "pr_auc": pr_auc,
        "pr_auc_ci_low": pr_auc_ci_low,
        "top20_hit_rate": top20,
        "gate_activation_count": int(residual.get("positive_delta_count") or 0),
        "shadow_only_active_locked": bool(residual.get("shadow_only_active_locked", False)),
        "score_scaling_mode": summary_payload.get("score_reference_scaling", {}).get("mode")
        if isinstance(summary_payload.get("score_reference_scaling"), dict)
        else "",
        "score_reference_stats_hash": summary_payload.get("score_reference_scaling", {}).get("stats_hash")
        if isinstance(summary_payload.get("score_reference_scaling"), dict)
        else "",
    }


def _latest_v5_replay_review() -> dict[str, Any]:
    eval_path = _resolve(DEFAULT_V5_REPLAY_EVAL_JSON)
    summary_path = _resolve(DEFAULT_V5_REPLAY_SUMMARY_JSON)
    if eval_path is None or not eval_path.exists():
        return {"available": False}
    eval_payload = _read_json(eval_path)
    summary_payload = _read_json(summary_path) if summary_path and summary_path.exists() else {}
    metrics = eval_payload.get("metrics_unique") if isinstance(eval_payload.get("metrics_unique"), dict) else {}
    ci = eval_payload.get("metrics_ci_unique") if isinstance(eval_payload.get("metrics_ci_unique"), dict) else {}
    pr_auc_ci = ci.get("pr_auc") if isinstance(ci.get("pr_auc"), dict) else {}
    top20 = None
    for row in eval_payload.get("topk_unique", []):
        if isinstance(row, dict) and int(row.get("k") or 0) == 20:
            top20 = _float(row.get("hit_rate"))
            break
    residual = (
        summary_payload.get("residual_prototype")
        if isinstance(summary_payload.get("residual_prototype"), dict)
        else {}
    )
    feature_counts = (
        residual.get("fixed_reference_feature_nonzero_counts")
        if isinstance(residual.get("fixed_reference_feature_nonzero_counts"), dict)
        else {}
    )
    if (
        "fixed_reference_prior_weakness_pressure" not in feature_counts
        and "target_internal_pairwise_pressure" in feature_counts
    ):
        feature_counts = {
            **feature_counts,
            "fixed_reference_prior_weakness_pressure": feature_counts.get("target_internal_pairwise_pressure"),
        }
    pr_auc = _float(metrics.get("pr_auc"))
    pr_auc_ci_low = _float(pr_auc_ci.get("low"))
    beats_v2 = (
        pr_auc is not None
        and pr_auc > 0.5767474245351905
        and pr_auc_ci_low is not None
        and pr_auc_ci_low > 0.21066694653866244
        and top20 is not None
        and top20 >= 0.25
    )
    status = "shadow_replay_improved_needs_guarded_review" if beats_v2 else "reject_evidence"
    return {
        "available": True,
        "status": status,
        "eval_json": str(eval_path),
        "summary_json": str(summary_path) if summary_path else "",
        "pr_auc": pr_auc,
        "pr_auc_ci_low": pr_auc_ci_low,
        "top20_hit_rate": top20,
        "beats_v2_shadow_baseline": bool(beats_v2),
        "v2_pr_auc_baseline": 0.5767474245351905,
        "v2_pr_auc_ci_low_baseline": 0.21066694653866244,
        "v2_top20_hit_rate_baseline": 0.25,
        "fixed_reference_live_positive_pressure_count": int(
            residual.get("fixed_reference_live_positive_pressure_count") or 0
        ),
        "shadow_only_active_locked": bool(residual.get("shadow_only_active_locked", False)),
        "score_scaling_mode": summary_payload.get("score_reference_scaling", {}).get("mode")
        if isinstance(summary_payload.get("score_reference_scaling"), dict)
        else "",
        "score_reference_stats_hash": summary_payload.get("score_reference_scaling", {}).get("stats_hash")
        if isinstance(summary_payload.get("score_reference_scaling"), dict)
        else "",
        "fixed_reference_feature_nonzero_counts": feature_counts,
    }


def _latest_v6_spec_review(spec_json: str | Path = DEFAULT_V6_SPEC_JSON) -> dict[str, Any]:
    path = _resolve(spec_json)
    spec = _read_json(path)
    if not spec:
        return {
            "available": False,
            "status": "missing",
            "spec_json": str(path) if path else "",
            "next_action": "build_class_a_motif_shadow_v6_spec",
        }
    prototype = spec.get("prototype") if isinstance(spec.get("prototype"), dict) else {}
    constraints = prototype.get("constraints") if isinstance(prototype.get("constraints"), dict) else {}
    tuning = prototype.get("tuning") if isinstance(prototype.get("tuning"), dict) else {}
    linear = prototype.get("linear_rescore") if isinstance(prototype.get("linear_rescore"), dict) else {}
    terms = linear.get("terms") if isinstance(linear.get("terms"), list) else []
    variant_ok = str(tuning.get("variant", "")).strip() == "gpcr_core_class_a_motif_shadow_v6"
    scope_ok = str(tuning.get("scope", "")).strip() == "class_a_aminergic_opioid_like_orthosteric_sublane"
    active_locked = bool(constraints.get("active_score_locked_to_base"))
    shadow_only = bool(constraints.get("shadow_only_candidate"))
    claim_locked = bool(constraints.get("claim_locked_candidate"))
    scorer_apply_allowed = bool(constraints.get("scorer_apply_allowed", True))
    broad_gpcr_claim_allowed = bool(constraints.get("broad_gpcr_claim_allowed", True))
    forbidden_feature_flags_green = not any(
        bool(constraints.get(key, True))
        for key in (
            "target_identity_feature_allowed",
            "label_feature_allowed",
            "rank_feature_allowed",
            "ligand_id_feature_allowed",
            "reference_binding_value_allowed",
        )
    )
    expected_terms = {
        "binding_score_composite_v7_prior_active",
        "class_a_orthosteric_motif_support_proxy",
        "class_a_prior_overreward_invalid_overanchor_pressure",
    }
    term_features = {
        str(term.get("feature", "")).strip()
        for term in terms
        if isinstance(term, dict) and str(term.get("feature", "")).strip()
    }
    ready = (
        variant_ok
        and scope_ok
        and active_locked
        and shadow_only
        and claim_locked
        and not scorer_apply_allowed
        and not broad_gpcr_claim_allowed
        and forbidden_feature_flags_green
        and term_features == expected_terms
    )
    return {
        "available": True,
        "status": "ready_for_score_only_shadow_replay" if ready else "blocked_spec_contract",
        "spec_json": str(path) if path else "",
        "prototype_variant": str(tuning.get("variant", "")),
        "scope": str(tuning.get("scope", "")),
        "active_score_locked_to_base": active_locked,
        "shadow_only_candidate": shadow_only,
        "claim_locked_candidate": claim_locked,
        "scorer_apply_allowed": scorer_apply_allowed,
        "broad_gpcr_claim_allowed": broad_gpcr_claim_allowed,
        "forbidden_feature_flags_green": forbidden_feature_flags_green,
        "linear_term_features": sorted(term_features),
        "next_action": (
            "run_score_only_shadow_replay_class_a_motif_shadow_v6"
            if ready
            else "repair_class_a_motif_shadow_v6_spec_contract"
        ),
    }


def _latest_v6_replay_review() -> dict[str, Any]:
    eval_path = _resolve(DEFAULT_V6_REPLAY_EVAL_JSON)
    summary_path = _resolve(DEFAULT_V6_REPLAY_SUMMARY_JSON)
    if eval_path is None or not eval_path.exists():
        return {"available": False, "status": "missing"}
    eval_payload = _read_json(eval_path)
    summary_payload = _read_json(summary_path) if summary_path and summary_path.exists() else {}
    metrics = eval_payload.get("metrics_unique") if isinstance(eval_payload.get("metrics_unique"), dict) else {}
    ci = eval_payload.get("metrics_ci_unique") if isinstance(eval_payload.get("metrics_ci_unique"), dict) else {}
    pr_auc_ci = ci.get("pr_auc") if isinstance(ci.get("pr_auc"), dict) else {}
    top20 = None
    for row in eval_payload.get("topk_unique", []):
        if isinstance(row, dict) and int(row.get("k") or 0) == 20:
            top20 = _float(row.get("hit_rate"))
            break
    residual = (
        summary_payload.get("residual_prototype")
        if isinstance(summary_payload.get("residual_prototype"), dict)
        else {}
    )
    replay_summary = summary_payload.get("summary") if isinstance(summary_payload.get("summary"), dict) else {}
    pr_auc = _float(metrics.get("pr_auc"))
    pr_auc_ci_low = _float(pr_auc_ci.get("low"))
    beats_v2 = (
        pr_auc is not None
        and pr_auc > FROZEN_R2_V2_SHADOW_PR_AUC_BASELINE
        and pr_auc_ci_low is not None
        and pr_auc_ci_low > FROZEN_R2_V2_SHADOW_PR_AUC_CI_LOW_BASELINE
        and top20 is not None
        and top20 >= FROZEN_R2_V2_SHADOW_TOP20_HIT_RATE_BASELINE
    )
    return {
        "available": True,
        "status": "shadow_replay_improved_needs_guarded_review" if beats_v2 else "reject_evidence",
        "eval_json": str(eval_path),
        "summary_json": str(summary_path) if summary_path else "",
        "pr_auc": pr_auc,
        "pr_auc_ci_low": pr_auc_ci_low,
        "top20_hit_rate": top20,
        "beats_v2_shadow_baseline": bool(beats_v2),
        "v2_pr_auc_baseline": FROZEN_R2_V2_SHADOW_PR_AUC_BASELINE,
        "v2_pr_auc_ci_low_baseline": FROZEN_R2_V2_SHADOW_PR_AUC_CI_LOW_BASELINE,
        "v2_top20_hit_rate_baseline": FROZEN_R2_V2_SHADOW_TOP20_HIT_RATE_BASELINE,
        "v2_baseline_label_basis": "frozen_r2_matching_labels",
        "active_score_locked_to_base": bool(replay_summary.get("active_score_locked_to_base", False)),
        "active_delta_max_abs": _float(replay_summary.get("active_delta_max_abs")),
        "shadow_only_active_locked": bool(residual.get("shadow_only_active_locked", False)),
        "class_a_motif_support_positive_count": int(residual.get("class_a_motif_support_positive_count") or 0),
        "class_a_prior_overreward_invalid_overanchor_positive_count": int(
            residual.get("class_a_prior_overreward_invalid_overanchor_positive_count") or 0
        ),
        "next_action": (
            "guarded_review_class_a_motif_shadow_v6"
            if beats_v2
            else "rework_class_a_motif_shadow_v6_after_replay_reject"
        ),
    }


def _latest_v7_spec_review(spec_json: str | Path = DEFAULT_V7_SPEC_JSON) -> dict[str, Any]:
    path = _resolve(spec_json)
    spec = _read_json(path)
    if not spec:
        return {
            "available": False,
            "status": "missing",
            "spec_json": str(path) if path else "",
            "next_action": "build_class_a_anchor_geometry_shadow_v7_spec",
        }
    prototype = spec.get("prototype") if isinstance(spec.get("prototype"), dict) else {}
    constraints = prototype.get("constraints") if isinstance(prototype.get("constraints"), dict) else {}
    tuning = prototype.get("tuning") if isinstance(prototype.get("tuning"), dict) else {}
    linear = prototype.get("linear_rescore") if isinstance(prototype.get("linear_rescore"), dict) else {}
    terms = linear.get("terms") if isinstance(linear.get("terms"), list) else []
    variant_ok = str(tuning.get("variant", "")).strip() == "gpcr_core_class_a_anchor_geometry_shadow_v7"
    scope_ok = str(tuning.get("scope", "")).strip() == "class_a_aminergic_opioid_like_orthosteric_sublane"
    active_locked = bool(constraints.get("active_score_locked_to_base"))
    shadow_only = bool(constraints.get("shadow_only_candidate"))
    claim_locked = bool(constraints.get("claim_locked_candidate"))
    scorer_apply_allowed = bool(constraints.get("scorer_apply_allowed", True))
    broad_gpcr_claim_allowed = bool(constraints.get("broad_gpcr_claim_allowed", True))
    forbidden_feature_flags_green = not any(
        bool(constraints.get(key, True))
        for key in (
            "target_identity_feature_allowed",
            "label_feature_allowed",
            "rank_feature_allowed",
            "ligand_id_feature_allowed",
            "reference_binding_value_allowed",
        )
    )
    expected_terms = {
        "binding_score_composite_v7_prior_active",
        "class_a_charge_complemented_anchor_geometry_proxy",
        "class_a_orthosteric_occupancy_proxy",
        "class_a_pose_survival_support_proxy",
        "class_a_invalid_anchor_prior_pressure_v7",
    }
    term_features = {
        str(term.get("feature", "")).strip()
        for term in terms
        if isinstance(term, dict) and str(term.get("feature", "")).strip()
    }
    ready = (
        variant_ok
        and scope_ok
        and active_locked
        and shadow_only
        and claim_locked
        and not scorer_apply_allowed
        and not broad_gpcr_claim_allowed
        and forbidden_feature_flags_green
        and term_features == expected_terms
    )
    return {
        "available": True,
        "status": "ready_for_score_only_shadow_replay" if ready else "blocked_spec_contract",
        "spec_json": str(path) if path else "",
        "prototype_variant": str(tuning.get("variant", "")),
        "scope": str(tuning.get("scope", "")),
        "active_score_locked_to_base": active_locked,
        "shadow_only_candidate": shadow_only,
        "claim_locked_candidate": claim_locked,
        "scorer_apply_allowed": scorer_apply_allowed,
        "broad_gpcr_claim_allowed": broad_gpcr_claim_allowed,
        "forbidden_feature_flags_green": forbidden_feature_flags_green,
        "linear_term_features": sorted(term_features),
        "next_action": (
            "run_score_only_shadow_replay_class_a_anchor_geometry_shadow_v7"
            if ready
            else "repair_class_a_anchor_geometry_shadow_v7_spec_contract"
        ),
    }


def _latest_v7_replay_review() -> dict[str, Any]:
    eval_path = _resolve(DEFAULT_V7_REPLAY_EVAL_JSON)
    summary_path = _resolve(DEFAULT_V7_REPLAY_SUMMARY_JSON)
    if eval_path is None or not eval_path.exists():
        return {"available": False, "status": "missing"}
    eval_payload = _read_json(eval_path)
    summary_payload = _read_json(summary_path) if summary_path and summary_path.exists() else {}
    metrics = eval_payload.get("metrics_unique") if isinstance(eval_payload.get("metrics_unique"), dict) else {}
    ci = eval_payload.get("metrics_ci_unique") if isinstance(eval_payload.get("metrics_ci_unique"), dict) else {}
    pr_auc_ci = ci.get("pr_auc") if isinstance(ci.get("pr_auc"), dict) else {}
    top20 = None
    for row in eval_payload.get("topk_unique", []):
        if isinstance(row, dict) and int(row.get("k") or 0) == 20:
            top20 = _float(row.get("hit_rate"))
            break
    residual = (
        summary_payload.get("residual_prototype")
        if isinstance(summary_payload.get("residual_prototype"), dict)
        else {}
    )
    replay_summary = summary_payload.get("summary") if isinstance(summary_payload.get("summary"), dict) else {}
    pr_auc = _float(metrics.get("pr_auc"))
    pr_auc_ci_low = _float(pr_auc_ci.get("low"))
    beats_v2 = (
        pr_auc is not None
        and pr_auc > FROZEN_R2_V2_SHADOW_PR_AUC_BASELINE
        and pr_auc_ci_low is not None
        and pr_auc_ci_low > FROZEN_R2_V2_SHADOW_PR_AUC_CI_LOW_BASELINE
        and top20 is not None
        and top20 >= FROZEN_R2_V2_SHADOW_TOP20_HIT_RATE_BASELINE
    )
    return {
        "available": True,
        "status": "shadow_replay_improved_needs_guarded_review" if beats_v2 else "reject_evidence",
        "eval_json": str(eval_path),
        "summary_json": str(summary_path) if summary_path else "",
        "pr_auc": pr_auc,
        "pr_auc_ci_low": pr_auc_ci_low,
        "top20_hit_rate": top20,
        "beats_v2_shadow_baseline": bool(beats_v2),
        "v2_pr_auc_baseline": FROZEN_R2_V2_SHADOW_PR_AUC_BASELINE,
        "v2_pr_auc_ci_low_baseline": FROZEN_R2_V2_SHADOW_PR_AUC_CI_LOW_BASELINE,
        "v2_top20_hit_rate_baseline": FROZEN_R2_V2_SHADOW_TOP20_HIT_RATE_BASELINE,
        "v2_baseline_label_basis": "frozen_r2_matching_labels",
        "active_score_locked_to_base": bool(replay_summary.get("active_score_locked_to_base", False)),
        "active_delta_max_abs": _float(replay_summary.get("active_delta_max_abs")),
        "shadow_only_active_locked": bool(residual.get("shadow_only_active_locked", False)),
        "charge_complemented_anchor_positive_count": int(
            residual.get("class_a_charge_complemented_anchor_geometry_positive_count") or 0
        ),
        "orthosteric_occupancy_positive_count": int(
            residual.get("class_a_orthosteric_occupancy_positive_count") or 0
        ),
        "pose_survival_support_positive_count": int(
            residual.get("class_a_pose_survival_support_positive_count") or 0
        ),
        "invalid_anchor_prior_pressure_positive_count": int(
            residual.get("class_a_invalid_anchor_prior_pressure_v7_positive_count") or 0
        ),
        "next_action": (
            "guarded_review_class_a_anchor_geometry_shadow_v7"
            if beats_v2
            else "rework_class_a_anchor_geometry_shadow_v7_after_replay_reject"
        ),
    }


def _latest_v8_spec_review(spec_json: str | Path = DEFAULT_V8_SPEC_JSON) -> dict[str, Any]:
    path = _resolve(spec_json)
    spec = _read_json(path)
    if not spec:
        return {
            "available": False,
            "status": "missing",
            "spec_json": str(path) if path else "",
            "next_action": "build_direct_atom_anchor_window_shadow_v8_spec",
        }
    prototype = spec.get("prototype") if isinstance(spec.get("prototype"), dict) else {}
    constraints = prototype.get("constraints") if isinstance(prototype.get("constraints"), dict) else {}
    tuning = prototype.get("tuning") if isinstance(prototype.get("tuning"), dict) else {}
    linear = prototype.get("linear_rescore") if isinstance(prototype.get("linear_rescore"), dict) else {}
    terms = linear.get("terms") if isinstance(linear.get("terms"), list) else []
    variant_ok = str(tuning.get("variant", "")).strip() == "gpcr_core_direct_atom_anchor_window_shadow_v8"
    scope_ok = str(tuning.get("scope", "")).strip() == "class_a_aminergic_opioid_like_orthosteric_sublane"
    active_locked = bool(constraints.get("active_score_locked_to_base"))
    shadow_only = bool(constraints.get("shadow_only_candidate"))
    claim_locked = bool(constraints.get("claim_locked_candidate"))
    scorer_apply_allowed = bool(constraints.get("scorer_apply_allowed", True))
    broad_gpcr_claim_allowed = bool(constraints.get("broad_gpcr_claim_allowed", True))
    requires_cache = bool(constraints.get("requires_precomputed_atom_window_features"))
    forbidden_feature_flags_green = not any(
        bool(constraints.get(key, True))
        for key in (
            "target_identity_feature_allowed",
            "label_feature_allowed",
            "rank_feature_allowed",
            "ligand_id_feature_allowed",
            "reference_binding_value_allowed",
        )
    )
    expected_terms = {
        "binding_score_composite_v7_prior_active",
        "class_a_direct_atom_window_anchor_geometry_proxy",
        "class_a_atom_window_pose_survival_proxy",
        "class_a_hydrophobic_overcontact_pressure_v8",
    }
    term_features = {
        str(term.get("feature", "")).strip()
        for term in terms
        if isinstance(term, dict) and str(term.get("feature", "")).strip()
    }
    ready = (
        variant_ok
        and scope_ok
        and active_locked
        and shadow_only
        and claim_locked
        and not scorer_apply_allowed
        and not broad_gpcr_claim_allowed
        and requires_cache
        and forbidden_feature_flags_green
        and term_features == expected_terms
    )
    return {
        "available": True,
        "status": "ready_for_feature_cache_and_score_only_shadow_replay" if ready else "blocked_spec_contract",
        "spec_json": str(path) if path else "",
        "prototype_variant": str(tuning.get("variant", "")),
        "scope": str(tuning.get("scope", "")),
        "active_score_locked_to_base": active_locked,
        "shadow_only_candidate": shadow_only,
        "claim_locked_candidate": claim_locked,
        "requires_precomputed_atom_window_features": requires_cache,
        "scorer_apply_allowed": scorer_apply_allowed,
        "broad_gpcr_claim_allowed": broad_gpcr_claim_allowed,
        "forbidden_feature_flags_green": forbidden_feature_flags_green,
        "linear_term_features": sorted(term_features),
        "next_action": (
            "build_atom_window_cache_then_run_direct_atom_anchor_window_shadow_v8"
            if ready
            else "repair_direct_atom_anchor_window_shadow_v8_spec_contract"
        ),
    }


def _latest_v8_replay_review() -> dict[str, Any]:
    eval_path = _resolve(DEFAULT_V8_REPLAY_EVAL_JSON)
    summary_path = _resolve(DEFAULT_V8_REPLAY_SUMMARY_JSON)
    if eval_path is None or not eval_path.exists():
        return {"available": False, "status": "missing"}
    eval_payload = _read_json(eval_path)
    summary_payload = _read_json(summary_path) if summary_path and summary_path.exists() else {}
    metrics = eval_payload.get("metrics_unique") if isinstance(eval_payload.get("metrics_unique"), dict) else {}
    ci = eval_payload.get("metrics_ci_unique") if isinstance(eval_payload.get("metrics_ci_unique"), dict) else {}
    pr_auc_ci = ci.get("pr_auc") if isinstance(ci.get("pr_auc"), dict) else {}
    top20 = None
    for row in eval_payload.get("topk_unique", []):
        if isinstance(row, dict) and int(row.get("k") or 0) == 20:
            top20 = _float(row.get("hit_rate"))
            break
    residual = (
        summary_payload.get("residual_prototype")
        if isinstance(summary_payload.get("residual_prototype"), dict)
        else {}
    )
    replay_summary = summary_payload.get("summary") if isinstance(summary_payload.get("summary"), dict) else {}
    pr_auc = _float(metrics.get("pr_auc"))
    pr_auc_ci_low = _float(pr_auc_ci.get("low"))
    beats_v2 = (
        pr_auc is not None
        and pr_auc > FROZEN_R2_V2_SHADOW_PR_AUC_BASELINE
        and pr_auc_ci_low is not None
        and pr_auc_ci_low > FROZEN_R2_V2_SHADOW_PR_AUC_CI_LOW_BASELINE
        and top20 is not None
        and top20 >= FROZEN_R2_V2_SHADOW_TOP20_HIT_RATE_BASELINE
    )
    return {
        "available": True,
        "status": "shadow_replay_improved_needs_guarded_review" if beats_v2 else "reject_evidence",
        "eval_json": str(eval_path),
        "summary_json": str(summary_path) if summary_path else "",
        "pr_auc": pr_auc,
        "pr_auc_ci_low": pr_auc_ci_low,
        "top20_hit_rate": top20,
        "beats_v2_shadow_baseline": bool(beats_v2),
        "v2_pr_auc_baseline": FROZEN_R2_V2_SHADOW_PR_AUC_BASELINE,
        "v2_pr_auc_ci_low_baseline": FROZEN_R2_V2_SHADOW_PR_AUC_CI_LOW_BASELINE,
        "v2_top20_hit_rate_baseline": FROZEN_R2_V2_SHADOW_TOP20_HIT_RATE_BASELINE,
        "v2_baseline_label_basis": "frozen_r2_matching_labels",
        "active_score_locked_to_base": bool(replay_summary.get("active_score_locked_to_base", False)),
        "active_delta_max_abs": _float(replay_summary.get("active_delta_max_abs")),
        "feature_cache_matched_row_count": int(replay_summary.get("feature_cache_matched_row_count") or 0),
        "shadow_only_active_locked": bool(residual.get("shadow_only_active_locked", False)),
        "atom_anchor_feature_available_count": int(
            residual.get("class_a_atom_anchor_feature_available_count") or 0
        ),
        "direct_atom_window_anchor_geometry_positive_count": int(
            residual.get("class_a_direct_atom_window_anchor_geometry_positive_count") or 0
        ),
        "hydrophobic_overcontact_pressure_positive_count": int(
            residual.get("class_a_hydrophobic_overcontact_pressure_v8_positive_count") or 0
        ),
        "next_action": (
            "guarded_review_direct_atom_anchor_window_shadow_v8"
            if beats_v2
            else "rework_direct_atom_anchor_window_shadow_v8_after_replay_reject"
        ),
    }


def _latest_v9_spec_review(spec_json: str | Path = DEFAULT_V9_SPEC_JSON) -> dict[str, Any]:
    path = _resolve(spec_json)
    spec = _read_json(path)
    if not spec:
        return {
            "available": False,
            "status": "missing",
            "spec_json": str(path) if path else "",
            "next_action": "build_atom_window_excess_polar_shadow_v9_spec",
        }
    prototype = spec.get("prototype") if isinstance(spec.get("prototype"), dict) else {}
    constraints = prototype.get("constraints") if isinstance(prototype.get("constraints"), dict) else {}
    tuning = prototype.get("tuning") if isinstance(prototype.get("tuning"), dict) else {}
    linear = prototype.get("linear_rescore") if isinstance(prototype.get("linear_rescore"), dict) else {}
    terms = linear.get("terms") if isinstance(linear.get("terms"), list) else []
    term_features = {
        str(term.get("feature", "")).strip()
        for term in terms
        if isinstance(term, dict) and str(term.get("feature", "")).strip()
    }
    expected_terms = {
        "binding_score_composite_v7_prior_active",
        "class_a_direct_atom_window_anchor_geometry_proxy",
        "class_a_atom_window_pose_survival_proxy",
        "class_a_compact_amine_window_support_v9",
        "class_a_hydrophobic_overcontact_pressure_v8",
        "class_a_excess_polar_anchor_pressure_v9",
    }
    forbidden_feature_flags_green = not any(
        bool(constraints.get(key, True))
        for key in (
            "target_identity_feature_allowed",
            "label_feature_allowed",
            "rank_feature_allowed",
            "ligand_id_feature_allowed",
            "reference_binding_value_allowed",
        )
    )
    ready = (
        str(tuning.get("variant", "")).strip() == "gpcr_core_atom_window_excess_polar_shadow_v9"
        and str(tuning.get("scope", "")).strip() == "class_a_aminergic_opioid_like_orthosteric_sublane"
        and bool(constraints.get("active_score_locked_to_base"))
        and bool(constraints.get("shadow_only_candidate"))
        and bool(constraints.get("claim_locked_candidate"))
        and bool(constraints.get("requires_precomputed_atom_window_features"))
        and not bool(constraints.get("scorer_apply_allowed", True))
        and not bool(constraints.get("broad_gpcr_claim_allowed", True))
        and forbidden_feature_flags_green
        and term_features == expected_terms
    )
    return {
        "available": True,
        "status": "ready_for_v2_preserved_score_only_shadow_replay" if ready else "blocked_spec_contract",
        "spec_json": str(path) if path else "",
        "prototype_variant": str(tuning.get("variant", "")),
        "scope": str(tuning.get("scope", "")),
        "active_score_locked_to_base": bool(constraints.get("active_score_locked_to_base")),
        "shadow_only_candidate": bool(constraints.get("shadow_only_candidate")),
        "claim_locked_candidate": bool(constraints.get("claim_locked_candidate")),
        "requires_precomputed_atom_window_features": bool(
            constraints.get("requires_precomputed_atom_window_features")
        ),
        "scorer_apply_allowed": bool(constraints.get("scorer_apply_allowed", True)),
        "broad_gpcr_claim_allowed": bool(constraints.get("broad_gpcr_claim_allowed", True)),
        "forbidden_feature_flags_green": forbidden_feature_flags_green,
        "linear_term_features": sorted(term_features),
        "next_action": (
            "run_v2_preserved_score_only_shadow_replay_atom_window_excess_polar_v9"
            if ready
            else "repair_atom_window_excess_polar_shadow_v9_spec_contract"
        ),
    }


def _latest_v9_replay_review() -> dict[str, Any]:
    eval_path = _resolve(DEFAULT_V9_REPLAY_EVAL_JSON)
    summary_path = _resolve(DEFAULT_V9_REPLAY_SUMMARY_JSON)
    if eval_path is None or not eval_path.exists():
        return {"available": False, "status": "missing"}
    eval_payload = _read_json(eval_path)
    summary_payload = _read_json(summary_path) if summary_path and summary_path.exists() else {}
    metrics = eval_payload.get("metrics_unique") if isinstance(eval_payload.get("metrics_unique"), dict) else {}
    ci = eval_payload.get("metrics_ci_unique") if isinstance(eval_payload.get("metrics_ci_unique"), dict) else {}
    pr_auc_ci = ci.get("pr_auc") if isinstance(ci.get("pr_auc"), dict) else {}
    top20 = None
    for row in eval_payload.get("topk_unique", []):
        if isinstance(row, dict) and int(row.get("k") or 0) == 20:
            top20 = _float(row.get("hit_rate"))
            break
    residual = (
        summary_payload.get("residual_prototype")
        if isinstance(summary_payload.get("residual_prototype"), dict)
        else {}
    )
    replay_summary = summary_payload.get("summary") if isinstance(summary_payload.get("summary"), dict) else {}
    pr_auc = _float(metrics.get("pr_auc"))
    pr_auc_ci_low = _float(pr_auc_ci.get("low"))
    beats_v2 = (
        pr_auc is not None
        and pr_auc > FROZEN_R2_V2_SHADOW_PR_AUC_BASELINE
        and pr_auc_ci_low is not None
        and pr_auc_ci_low > FROZEN_R2_V2_SHADOW_PR_AUC_CI_LOW_BASELINE
        and top20 is not None
        and top20 >= FROZEN_R2_V2_SHADOW_TOP20_HIT_RATE_BASELINE
    )
    return {
        "available": True,
        "status": "shadow_replay_improved_needs_guarded_review" if beats_v2 else "reject_evidence",
        "eval_json": str(eval_path),
        "summary_json": str(summary_path) if summary_path else "",
        "pr_auc": pr_auc,
        "pr_auc_ci_low": pr_auc_ci_low,
        "top20_hit_rate": top20,
        "beats_v2_shadow_baseline": bool(beats_v2),
        "v2_pr_auc_baseline": FROZEN_R2_V2_SHADOW_PR_AUC_BASELINE,
        "v2_pr_auc_ci_low_baseline": FROZEN_R2_V2_SHADOW_PR_AUC_CI_LOW_BASELINE,
        "v2_top20_hit_rate_baseline": FROZEN_R2_V2_SHADOW_TOP20_HIT_RATE_BASELINE,
        "v2_baseline_label_basis": "frozen_r2_matching_labels",
        "active_score_locked_to_base": bool(replay_summary.get("active_score_locked_to_base", False)),
        "active_delta_max_abs": _float(replay_summary.get("active_delta_max_abs")),
        "feature_cache_matched_row_count": int(replay_summary.get("feature_cache_matched_row_count") or 0),
        "reset_prior_active_to_base": bool(replay_summary.get("reset_prior_active_to_base", False)),
        "shadow_only_active_locked": bool(residual.get("shadow_only_active_locked", False)),
        "atom_anchor_feature_available_count": int(
            residual.get("class_a_atom_anchor_feature_available_count") or 0
        ),
        "excess_polar_anchor_pressure_positive_count": int(
            residual.get("class_a_excess_polar_anchor_pressure_v9_positive_count") or 0
        ),
        "compact_amine_window_support_positive_count": int(
            residual.get("class_a_compact_amine_window_support_v9_positive_count") or 0
        ),
        "next_action": (
            "guarded_review_atom_window_excess_polar_shadow_v9"
            if beats_v2
            else "reject_atom_window_excess_polar_shadow_v9_keep_v2_baseline"
        ),
    }


def _post_v3_acidic_anchor_review(
    pairwise: dict[str, Any],
    ci: dict[str, Any],
) -> dict[str, Any]:
    acidic_probe = (
        pairwise.get("acidic_anchor_overcontact_probe")
        if isinstance(pairwise.get("acidic_anchor_overcontact_probe"), dict)
        else {}
    )
    selected_count = int(acidic_probe.get("selected_decoy_count") or 0)
    available_count = int(acidic_probe.get("atom_anchor_available_count") or 0)
    min_lt_3_count = int(acidic_probe.get("anchor_min_distance_lt_3A_count") or 0)
    p10_lt_3_count = int(acidic_probe.get("anchor_p10_distance_lt_3A_count") or 0)
    v4_replay = _latest_v4_replay_review()
    return {
        "diagnostic_only": True,
        "candidate_variant": "gpcr_core_acidic_anchor_overcontact_prior_gate_v4",
        "candidate_role": "shadow_only_guarded_comparison_direction",
        "claim_promotion_allowed": False,
        "scorer_apply_allowed": False,
        "threshold_relaxation_allowed": False,
        "target_identity_feature_allowed": False,
        "label_rank_ligand_id_or_reference_binding_feature_allowed": False,
        "required_scaling_mode": "fixed_family_reference",
        "source_probe": "drd2_target_internal_pairwise_diagnostic.acidic_anchor_overcontact_probe",
        "selected_decoy_count": selected_count,
        "atom_anchor_available_count": available_count,
        "anchor_min_distance_lt_3A_count": min_lt_3_count,
        "anchor_p10_distance_lt_3A_count": p10_lt_3_count,
        "anchor_min_distance_lt_3A_fraction": (
            min_lt_3_count / available_count if available_count else None
        ),
        "anchor_p10_distance_lt_3A_fraction": (
            p10_lt_3_count / available_count if available_count else None
        ),
        "overcontact_signal_present": bool(available_count and min_lt_3_count > 0),
        "current_ci_low": ci.get("ranking_pr_auc_ci_low"),
        "ci_low_threshold": ci.get("ci_low_threshold"),
        "short_replay_acceptance": {
            "pr_auc_must_exceed": 0.5767474245351905,
            "pr_auc_ci_low_must_exceed": 0.21066694653866244,
            "top20_hit_rate_min": 0.25,
            "drd2_decoys_above_positive_must_be_below": 2434,
            "drd2_pairwise_win_rate_must_exceed": 0.7565756575657565,
        },
        "blocked_until": [
            "shadow_replay_beats_v2_without_metric_regression",
            "leakage_review_no_target_label_rank_ligand_id_reference_inputs",
            "full_100k_ci_low_top20_claim_review_green",
        ],
        "latest_v4_replay": v4_replay,
        "interpretation": (
            "Post-v3 evidence supports a shadow-only proxy gate for overcontact/prior-overreward review. "
            "It is not atom-resolved scorer evidence and cannot authorize delivery, router, or platform claims."
        ),
    }


def _post_v4_fixed_reference_redesign(v4_replay: dict[str, Any], v5_replay: dict[str, Any]) -> dict[str, Any]:
    return {
        "diagnostic_only": True,
        "candidate_variant": "gpcr_core_fixed_reference_live_shadow_v5",
        "candidate_role": "claim_locked_fixed_reference_live_shadow",
        "claim_promotion_allowed": False,
        "scorer_apply_allowed": False,
        "threshold_relaxation_allowed": False,
        "fake_pass_allowed": False,
        "target_identity_feature_allowed": False,
        "label_rank_ligand_id_or_reference_binding_feature_allowed": False,
        "required_scaling_mode": "fixed_family_reference",
        "rejected_predecessor_variant": "gpcr_core_acidic_anchor_overcontact_prior_gate_v4",
        "best_baseline_variant": "gpcr_core_family_anchor_rescore_v2",
        "fixed_reference_replay_feature_collapse": {
            "rows": 40000,
            "gpcr_conserved_anchor_proxy_nonzero": 1,
            "pose_physics_support_nonzero": 1,
            "gpcr_acidic_anchor_overcontact_prior_gate_nonzero": 0,
            "target_internal_pairwise_pressure_nonzero": 17768,
            "fixed_reference_prior_weakness_pressure_nonzero": 17768,
            "gpcr_pose_chemistry_hard_decoy_pressure_nonzero": 4164,
        },
        "fixed_reference_v2_formula_replay": {
            "pr_auc_approx": 0.0076,
            "top20_hit_rate": 0.0,
            "safe_to_port_v2_or_v4_weights": False,
        },
        "live_feature_policy": {
            "allowed_live_shadow_features": [
                "gpcr_pose_chemistry_hard_decoy_pressure",
                "fixed_reference_prior_weakness_pressure",
                "prior_overreward_without_anchor",
            ],
            "collapsed_features_must_be_telemetry_only": [
                "gpcr_conserved_anchor_proxy",
                "pose_physics_support",
                "gpcr_acidic_anchor_overcontact_prior_gate",
            ],
        },
        "latest_v4_replay": v4_replay,
        "latest_v5_replay": v5_replay,
        "blocked_until": [
            "score_only_shadow_replay_beats_v2_without_metric_regression",
            "leakage_review_no_target_label_rank_ligand_id_reference_inputs",
            "full_100k_ci_low_top20_claim_review_green",
        ],
    }


def _drd2_pose_physics_rescue_after_v5_packet(
    drd2_pose: dict[str, Any],
    pairwise: dict[str, Any],
    v5_replay: dict[str, Any],
) -> dict[str, Any]:
    positive = drd2_pose.get("positive") if isinstance(drd2_pose.get("positive"), dict) else {}
    cluster = (
        drd2_pose.get("top_decoy_cluster")
        if isinstance(drd2_pose.get("top_decoy_cluster"), dict)
        else {}
    )
    positive_proxies = (
        positive.get("pose_physics_rescue_proxies")
        if isinstance(positive.get("pose_physics_rescue_proxies"), dict)
        else {}
    )
    positive_chem = (
        positive_proxies.get("chemistry_heuristics")
        if isinstance(positive_proxies.get("chemistry_heuristics"), dict)
        else {}
    )
    positive_trajectory_pose = (
        positive_proxies.get("trajectory_pose_preservation_proxy")
        if isinstance(positive_proxies.get("trajectory_pose_preservation_proxy"), dict)
        else {}
    )
    positive_trajectory_survival = (
        positive_proxies.get("trajectory_survival_proxy")
        if isinstance(positive_proxies.get("trajectory_survival_proxy"), dict)
        else {}
    )
    cluster_proxy_summary = (
        cluster.get("mean_rescue_proxy_diagnostics")
        if isinstance(cluster.get("mean_rescue_proxy_diagnostics"), dict)
        else {}
    )
    overanchor = (
        pairwise.get("top_decoy_cluster_anchor_overanchoring_summary")
        if isinstance(pairwise.get("top_decoy_cluster_anchor_overanchoring_summary"), dict)
        else {}
    )
    positive_anchor_support = _float(positive_chem.get("amine_anchor_support_proxy"))
    decoy_anchor_support = _float(cluster_proxy_summary.get("amine_anchor_support_mean"))
    positive_trajectory_pose_support = _float(positive_trajectory_pose.get("support_proxy"))
    decoy_trajectory_pose_support = _float(cluster_proxy_summary.get("trajectory_pose_support_mean"))
    positive_trajectory_survival_support = _float(positive_trajectory_survival.get("support_proxy"))
    decoy_trajectory_survival_support = _float(cluster_proxy_summary.get("trajectory_survival_support_mean"))
    positive_trajectory_pose_p90 = _float(positive_trajectory_pose.get("p90_frame_rmsd_A"))
    decoy_trajectory_pose_p90 = _float(cluster_proxy_summary.get("trajectory_pose_p90_frame_rmsd_mean_A"))
    return {
        "packet_name": "drd2_pose_physics_rescue_after_v5_reject",
        "next_action": "return_to_drd2_pose_physics_rescue_after_v5_reject",
        "diagnostic_only": True,
        "local_only": True,
        "bounded_no_full_100k": True,
        "claim_promotion_allowed": False,
        "scorer_apply_allowed": False,
        "threshold_relaxation_allowed": False,
        "target_identity_feature_allowed": False,
        "v5_replay_status": v5_replay.get("status", "unavailable"),
        "positive_vs_top_decoy_cluster": {
            "positive_ligand_id": positive.get("ligand_id", ""),
            "positive_rank": positive.get("rank"),
            "positive_within_target_rank": positive.get("within_target_rank"),
            "top_decoy_cluster_size": cluster.get("size", 0),
            "positive_pose_preservation_rmsd_proxy": positive_proxies.get("pose_preservation_rmsd_proxy", {}),
            "positive_local_minimization_survival_proxy": positive_proxies.get(
                "local_minimization_survival_proxy", {}
            ),
            "positive_trajectory_pose_preservation_proxy": positive_trajectory_pose,
            "positive_trajectory_survival_proxy": positive_trajectory_survival,
            "positive_chemistry_heuristics": positive_chem,
            "top_decoy_cluster_rescue_proxy_summary": cluster_proxy_summary,
            "overanchored_without_basic_amine_count": overanchor.get(
                "overanchored_without_basic_amine_count", 0
            ),
            "overanchored_without_basic_amine_ligand_ids": overanchor.get(
                "overanchored_without_basic_amine_ligand_ids", []
            ),
            "amine_anchor_support_separation_positive_minus_decoy_mean": (
                positive_anchor_support - decoy_anchor_support
                if positive_anchor_support is not None and decoy_anchor_support is not None
                else None
            ),
            "trajectory_pose_support_separation_positive_minus_decoy_mean": (
                positive_trajectory_pose_support - decoy_trajectory_pose_support
                if positive_trajectory_pose_support is not None and decoy_trajectory_pose_support is not None
                else None
            ),
            "trajectory_survival_support_separation_positive_minus_decoy_mean": (
                positive_trajectory_survival_support - decoy_trajectory_survival_support
                if positive_trajectory_survival_support is not None
                and decoy_trajectory_survival_support is not None
                else None
            ),
            "trajectory_pose_p90_frame_rmsd_decoy_mean_minus_positive_A": (
                decoy_trajectory_pose_p90 - positive_trajectory_pose_p90
                if positive_trajectory_pose_p90 is not None and decoy_trajectory_pose_p90 is not None
                else None
            ),
        },
        "safe_local_measurements": [
            "pose_preservation_rmsd_proxy_from_existing_columns_if_present",
            "local_minimization_survival_proxy_from_existing_columns_if_present",
            "trajectory_pose_preservation_proxy_from_existing_npz",
            "trajectory_survival_proxy_from_existing_stage3_columns",
            "protonation_tautomer_basic_amine_anchor_heuristics_from_existing_smiles_or_columns",
            "decoy_overanchoring_separation_from_existing_anchor_proxy_or_atom_trajectory_if_present",
        ],
        "forbidden_actions": [
            "full_100k_rerun",
            "claim_promotion",
            "scorer_apply",
            "threshold_relaxation",
            "target_identity_scorer_feature",
            "label_rank_ligand_id_or_reference_binding_live_feature",
        ],
        "interpretation": (
            "This packet only diagnoses whether the DRD2 positive has pose preservation, minimization survival, "
            "and basic-amine anchor chemistry support that top decoys lack. It is not claim evidence."
        ),
    }


def build_packet(
    *,
    rows_csv: str | Path | None = DEFAULT_ROWS_CSV,
    stage3_csv: str | Path | None = DEFAULT_STAGE3_CSV,
    ci_json: str | Path | None = DEFAULT_CI_JSON,
    readiness_json: str | Path | None = DEFAULT_READINESS_JSON,
    generated_at_local: str | None = None,
) -> dict[str, Any]:
    rows_path = _resolve(rows_csv)
    stage3_path = _resolve(stage3_csv)
    ci_path = _resolve(ci_json)
    readiness_path = _resolve(readiness_json)
    rows = _read_csv(rows_path)
    stage3_rows = _read_csv(stage3_path)
    ci_payload = _read_json(ci_path)
    readiness_payload = _read_json(readiness_path)
    stage3_lookup = _stage3_feature_lookup(stage3_rows)
    score_col = _score_col(rows)
    global_ranks, within_ranks = _rank_maps(rows, score_col)

    positives: list[dict[str, Any]] = []
    for row in rows:
        if not _is_positive(row):
            continue
        target = _text(row.get("target"))
        ligand_id = _text(row.get("ligand_id"))
        key = (target, ligand_id)
        stage3 = stage3_lookup.get(key, {})
        positives.append(
            {
                "target": target,
                "ligand_id": ligand_id,
                "non_adrb2": _is_non_adrb2(target),
                "global_rank": global_ranks.get(key),
                "within_target_rank": within_ranks.get(key),
                "score": _float(row.get(score_col)),
                "mean_min_distance_A": _float(row.get("mean_min_distance_A")),
                "reference_binding_kcal_mol": _float(row.get("reference_binding_kcal_mol")),
                "features": _feature_snapshot(stage3),
            }
        )
    positives.sort(key=lambda row: (row.get("global_rank") or 10**12, row["target"], row["ligand_id"]))

    top_intrusions: list[dict[str, Any]] = []
    sorted_rows = sorted(
        [row for row in rows if _float(row.get(score_col)) is not None],
        key=lambda row: (_float(row.get(score_col)) or 0.0, _text(row.get("target")), _text(row.get("ligand_id"))),
    )
    for rank, row in enumerate(sorted_rows, start=1):
        if _is_positive(row):
            continue
        top_intrusions.append(
            {
                "rank": rank,
                "target": _text(row.get("target")),
                "ligand_id": _text(row.get("ligand_id")),
                "score": _float(row.get(score_col)),
                "mean_min_distance_A": _float(row.get("mean_min_distance_A")),
                "reference_binding_kcal_mol": _float(row.get("reference_binding_kcal_mol")),
            }
        )
        if len(top_intrusions) >= 12:
            break

    ci = _ci_summary(ci_payload)
    readiness_summary = readiness_payload.get("summary") if isinstance(readiness_payload.get("summary"), dict) else {}
    non_adrb2_tail = [
        row
        for row in positives
        if row["non_adrb2"] and ((row.get("global_rank") or 10**12) > 20 or (row.get("within_target_rank") or 10**12) > 20)
    ]
    blockers: list[str] = []
    if not rows:
        blockers.append("ranking_rows_missing")
    if ci["ranking_pr_auc_ci_low"] is None or ci["ranking_pr_auc_ci_low"] < ci["ci_low_threshold"]:
        blockers.append("ci_low_below_threshold")
    if ci["ranking_topk_hit_rate"] is None or ci["ranking_topk_hit_rate"] < ci["top20_threshold"]:
        blockers.append("top20_stability_not_green")
    if non_adrb2_tail:
        blockers.append("non_adrb2_positive_tail_rank")
    if top_intrusions:
        blockers.append("target_internal_decoy_intrusion")

    v4_replay = _latest_v4_replay_review()
    v5_replay = _latest_v5_replay_review()
    v6_spec = _latest_v6_spec_review()
    v6_replay = _latest_v6_replay_review()
    v7_spec = _latest_v7_spec_review()
    v7_replay = _latest_v7_replay_review()
    v8_spec = _latest_v8_spec_review()
    v8_replay = _latest_v8_replay_review()
    v9_spec = _latest_v9_spec_review()
    v9_replay = _latest_v9_replay_review()
    next_action = "shadow_replay_acidic_anchor_overcontact_prior_gate_v4"
    next_required_step = (
        "Do not relaunch the same packet as claim evidence. "
        "Use the post-v3 acidic-anchor overcontact review to run a fixed-family-reference, shadow-only "
        "v4 shadow replay before any guarded apply or fresh full 100k claim review."
    )
    if v4_replay.get("available") and v4_replay.get("status") == "reject_evidence":
        next_action = "build_claim_locked_fixed_reference_live_gpcr_v5_shadow_after_v4_reject"
        next_required_step = (
            "Do not relaunch v4 unchanged as claim evidence. The fixed-family-reference v4 shadow replay is reject "
            "evidence, so build a claim-locked v5 fixed-reference-live shadow diagnostic that records feature "
            "collapse and uses only live target-agnostic pressures before any guarded apply or fresh full 100k claim review."
        )
    if v5_replay.get("available") and v5_replay.get("status") == "reject_evidence":
        next_action = "return_to_drd2_pose_physics_rescue_after_v5_reject"
        next_required_step = (
            "Do not relaunch v5 unchanged as claim evidence. The v5 fixed-reference-live shadow replay is reject "
            "evidence and does not beat the v2 shadow baseline. "
            "Keep v2 as the current best comparison signal, keep claim promotion locked, and move the next hard work "
            "back to DRD2 pose/physics rescue: ligand protonation/tautomer checks, local minimization survival, "
            "pose-preservation RMSD, and decoy over-anchoring separation before any guarded apply or fresh full 100k claim review."
        )
    if v6_spec.get("available") and v6_spec.get("status") == "ready_for_score_only_shadow_replay":
        next_action = "run_score_only_shadow_replay_class_a_motif_shadow_v6"
        next_required_step = (
            "Do not relaunch v4 or v5 unchanged as claim evidence. Run the class A aminergic/opioid-like "
            "orthosteric motif v6 candidate only as a score-only, shadow-only, active-locked replay against "
            "the v2 donor/baseline. Do not run a fresh full 100k claim review, do not relax thresholds, and "
            "keep router/platform/broad GPCR claim promotion locked before any guarded apply."
        )
    if v6_replay.get("available") and v6_replay.get("status") == "reject_evidence":
        next_action = "rework_class_a_motif_shadow_v6_after_replay_reject"
        next_required_step = (
            "Do not relaunch or promote v6 as claim evidence. The class A motif shadow replay stayed active-locked "
            "but failed the v2 comparison gate, so keep it as reject evidence and rework the motif gate around "
            "charge-complemented anchor geometry, aromatic-cage/orthosteric occupancy, and DRD2 hard-decoy "
            "separation before any guarded apply or fresh full 100k claim review."
        )
    if v7_spec.get("available") and v7_spec.get("status") == "ready_for_score_only_shadow_replay":
        next_action = "run_score_only_shadow_replay_class_a_anchor_geometry_shadow_v7"
        next_required_step = (
            "Run the class A anchor-geometry v7 candidate only as a score-only, shadow-only, active-locked replay "
            "against the v2 donor/baseline. Do not run a fresh full 100k claim review, do not relax thresholds, "
            "and keep router/platform/broad GPCR claim promotion locked before any guarded apply."
        )
    if v7_replay.get("available") and v7_replay.get("status") == "reject_evidence":
        next_action = "rework_class_a_anchor_geometry_shadow_v7_after_replay_reject"
        next_required_step = (
            "Do not relaunch or promote v7 as claim evidence. The class A anchor-geometry replay stayed "
            "active-locked but failed the frozen-r2 v2 matching-label comparison gate, so keep it as reject "
            "evidence and move the next contract to direct atom-window anchor geometry plus hydrophobic-overcontact "
            "diagnostics before any guarded apply or fresh full 100k claim review."
        )
    if v7_replay.get("available") and v7_replay.get("status") == "shadow_replay_improved_needs_guarded_review":
        next_action = "guarded_review_class_a_anchor_geometry_shadow_v7"
        next_required_step = (
            "v7 beat the v2 shadow comparison gate, but it is still not claim evidence. Review leakage and "
            "active-lock invariants, then prepare a guarded-apply packet; only a later full 100k claim review can "
            "unlock router/platform/broad GPCR wording."
        )
    if v8_spec.get("available") and v8_spec.get("status") == "ready_for_feature_cache_and_score_only_shadow_replay":
        next_action = "build_atom_window_cache_then_run_direct_atom_anchor_window_shadow_v8"
        next_required_step = (
            "Build the direct atom-window anchor feature cache, then run v8 only as a score-only, shadow-only, "
            "active-locked replay against the frozen-r2 v2 matching-label comparator. Missing atom-window rows are "
            "telemetry, not negative evidence. Do not launch guarded apply or broad GPCR claims."
        )
    if v8_replay.get("available") and v8_replay.get("status") == "reject_evidence":
        next_action = "rework_direct_atom_anchor_window_shadow_v8_after_replay_reject"
        next_required_step = (
            "Do not relaunch or promote v8 as claim evidence. The direct atom-window replay failed the frozen-r2 "
            "v2 matching-label comparison gate, so keep it as reject evidence and inspect atom-window coverage, "
            "hydrophobic-overcontact pressure, and DRD2 hard-decoy separation before any guarded apply."
        )
    if v8_replay.get("available") and v8_replay.get("status") == "shadow_replay_improved_needs_guarded_review":
        next_action = "guarded_review_direct_atom_anchor_window_shadow_v8"
        next_required_step = (
            "v8 beat the frozen-r2 v2 comparison gate, but it is still not claim evidence. Review leakage, cache "
            "coverage, and active-lock invariants before preparing any guarded-apply packet."
        )
    if v9_spec.get("available") and v9_spec.get("status") == "ready_for_v2_preserved_score_only_shadow_replay":
        next_action = "run_v2_preserved_score_only_shadow_replay_atom_window_excess_polar_v9"
        next_required_step = (
            "Run v9 only as a v2-preserved, score-only, active-locked shadow replay. It must beat the frozen-r2 "
            "v2 PR-AUC, CI-low, and Top20 comparator before any guarded apply or broad GPCR claim wording."
        )
    if v9_replay.get("available") and v9_replay.get("status") == "reject_evidence":
        next_action = "reject_atom_window_excess_polar_shadow_v9_return_to_pose_generation_and_decoy_design"
        next_required_step = (
            "Do not relaunch or promote v9 as claim evidence. It preserves Top20 but still fails the v2 comparison "
            "gate, so the blocker is no longer just scorer weighting: return to DRD2 pose generation/backmapping, "
            "larger non-leaky positive coverage, and hard-decoy construction before any guarded apply or full 100k "
            "claim review."
        )
    if v9_replay.get("available") and v9_replay.get("status") == "shadow_replay_improved_needs_guarded_review":
        next_action = "guarded_review_atom_window_excess_polar_shadow_v9"
        next_required_step = (
            "v9 beat the frozen-r2 v2 comparison gate, but it is still not claim evidence. Review leakage, "
            "active-lock, cache coverage, and family-held-out behavior before preparing a guarded-apply packet."
        )

    drd2_pose_physics = _drd2_pose_physics_diagnostics(
        rows,
        stage3_lookup,
        global_ranks,
        within_ranks,
        score_col,
    )
    drd2_pairwise = _drd2_target_internal_pairwise_diagnostic(
        rows,
        stage3_lookup,
        global_ranks,
        within_ranks,
        score_col,
    )
    drd2_rescue_after_v5 = _drd2_pose_physics_rescue_after_v5_packet(
        drd2_pose_physics,
        drd2_pairwise,
        v5_replay,
    )
    drd2_label_free_motif = _drd2_label_free_motif_aware_diagnostic(
        drd2_pose_physics,
        drd2_pairwise,
    )

    return {
        "packet_type": "gpcr_guarded_100k_rank_failure_diagnostics",
        "generated_at_local": generated_at_local or dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "input_artifacts": {
            "rows_csv": str(rows_path) if rows_path else None,
            "stage3_csv": str(stage3_path) if stage3_path else None,
            "ci_json": str(ci_path) if ci_path else None,
            "readiness_json": str(readiness_path) if readiness_path else None,
        },
        "summary": {
            "status": "blocked_ranking_quality" if blockers else "diagnostic_green",
            "claim_promotion_allowed": False,
            "scorer_apply_allowed": False,
            "router_claim_allowed": False,
            "platform_claim_allowed": False,
            "next_action": next_action,
            "positive_count": len(positives),
            "non_adrb2_positive_count": sum(1 for row in positives if row["non_adrb2"]),
            "non_adrb2_tail_positive_count": len(non_adrb2_tail),
            "worst_positive_global_rank": max((row.get("global_rank") or 0 for row in positives), default=None),
            "worst_positive_within_target_rank": max((row.get("within_target_rank") or 0 for row in positives), default=None),
            "ranking_pr_auc": ci["ranking_pr_auc"],
            "ranking_pr_auc_ci_low": ci["ranking_pr_auc_ci_low"],
            "ranking_topk_hit_rate": ci["ranking_topk_hit_rate"],
            "blocker_count": len(blockers),
            "blockers": blockers,
            "readiness_blockers": readiness_summary.get("blockers", []),
            "next_action": next_action,
            "next_required_step": next_required_step,
        },
        "positive_rank_diagnostics": positives,
        "top_decoy_intrusions": top_intrusions,
        "ci_low_stability_metadata": _ci_low_stability_metadata(ci),
        "drd2_pose_physics_diagnostics": drd2_pose_physics,
        "drd2_target_internal_pairwise_diagnostic": drd2_pairwise,
        "drd2_pose_physics_rescue_after_v5_reject_packet": drd2_rescue_after_v5,
        DRD2_LABEL_FREE_MOTIF_SUBLANE: drd2_label_free_motif,
        "post_v3_acidic_anchor_review": _post_v3_acidic_anchor_review(drd2_pairwise, ci),
        "post_v4_fixed_reference_redesign": _post_v4_fixed_reference_redesign(v4_replay, v5_replay),
        "class_a_motif_shadow_v6_candidate": v6_spec,
        "class_a_motif_shadow_v6_replay": v6_replay,
        "class_a_anchor_geometry_shadow_v7_candidate": v7_spec,
        "class_a_anchor_geometry_shadow_v7_replay": v7_replay,
        "direct_atom_anchor_window_shadow_v8_candidate": v8_spec,
        "direct_atom_anchor_window_shadow_v8_replay": v8_replay,
        "atom_window_excess_polar_shadow_v9_candidate": v9_spec,
        "atom_window_excess_polar_shadow_v9_replay": v9_replay,
        "claim_boundary": {
            "diagnostic_only_not_claim_authorizing": True,
            "claim_promotion_allowed": False,
            "scorer_apply_allowed": False,
            "threshold_relaxation_allowed": False,
            "fake_pass_allowed": False,
        },
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# GPCR Guarded 100k Rank Failure Diagnostics",
        "",
        "## Summary",
        f"- status: `{summary['status']}`",
        f"- claim_promotion_allowed: `{str(summary['claim_promotion_allowed']).lower()}`",
        f"- scorer_apply_allowed: `{str(summary['scorer_apply_allowed']).lower()}`",
        f"- next_action: `{summary['next_action']}`",
        f"- positive_count: `{summary['positive_count']}`",
        f"- non_adrb2_positive_count: `{summary['non_adrb2_positive_count']}`",
        f"- non_adrb2_tail_positive_count: `{summary['non_adrb2_tail_positive_count']}`",
        f"- ranking_pr_auc_ci_low: `{summary['ranking_pr_auc_ci_low']}`",
        f"- ranking_topk_hit_rate: `{summary['ranking_topk_hit_rate']}`",
        f"- blockers: `{', '.join(summary['blockers'])}`",
        "",
        "## Positive Ranks",
        "",
        "| global_rank | within_target_rank | target | ligand_id | score | mean_min_distance_A |",
        "| ---: | ---: | --- | --- | ---: | ---: |",
    ]
    for row in payload.get("positive_rank_diagnostics", []):
        lines.append(
            "| {global_rank} | {within_target_rank} | `{target}` | `{ligand_id}` | {score} | {distance} |".format(
                global_rank=row.get("global_rank"),
                within_target_rank=row.get("within_target_rank"),
                target=row.get("target"),
                ligand_id=row.get("ligand_id"),
                score=row.get("score"),
                distance=row.get("mean_min_distance_A"),
            )
        )
    lines.extend(
        [
            "",
            "## Top Decoy Intrusions",
            "",
            "| rank | target | ligand_id | score | mean_min_distance_A |",
            "| ---: | --- | --- | ---: | ---: |",
        ]
    )
    for row in payload.get("top_decoy_intrusions", []):
        lines.append(
            "| {rank} | `{target}` | `{ligand_id}` | {score} | {distance} |".format(
                rank=row.get("rank"),
                target=row.get("target"),
                ligand_id=row.get("ligand_id"),
                score=row.get("score"),
                distance=row.get("mean_min_distance_A"),
            )
        )
    ci_meta = (
        payload.get("ci_low_stability_metadata")
        if isinstance(payload.get("ci_low_stability_metadata"), dict)
        else {}
    )
    lines.extend(
        [
            "",
            "## CI-Low Stability Metadata",
            "",
            f"- diagnostic_only: `{str(ci_meta.get('diagnostic_only', False)).lower()}`",
            f"- ci_low_computed: `{str(ci_meta.get('ci_low_computed', False)).lower()}`",
            f"- base_pr_auc: `{ci_meta.get('base_pr_auc', '')}`",
            f"- base_pr_auc_ci_low: `{ci_meta.get('base_pr_auc_ci_low', '')}`",
            f"- v2_shadow_pr_auc: `{ci_meta.get('v2_shadow_pr_auc', '')}`",
            f"- v2_shadow_pr_auc_ci_low: `{ci_meta.get('v2_shadow_pr_auc_ci_low', '')}`",
            f"- v2_shadow_top20_hit_rate: `{ci_meta.get('v2_shadow_top20_hit_rate', '')}`",
            f"- v2_shadow_drd2_decoys_above_positive_count: `{ci_meta.get('v2_shadow_drd2_decoys_above_positive_count', '')}`",
            f"- v2_shadow_drd2_pairwise_win_rate: `{ci_meta.get('v2_shadow_drd2_pairwise_win_rate', '')}`",
            f"- ci_low_threshold: `{ci_meta.get('ci_low_threshold', '')}`",
            f"- ci_low_gap_to_threshold: `{ci_meta.get('ci_low_gap_to_threshold', '')}`",
            f"- ci_low_status: `{ci_meta.get('ci_low_status', '')}`",
            f"- recommended_next_action: `{ci_meta.get('recommended_next_action', '')}`",
        ]
    )
    drd2 = payload.get("drd2_pose_physics_diagnostics") if isinstance(payload.get("drd2_pose_physics_diagnostics"), dict) else {}
    drd2_meta = drd2.get("metadata") if isinstance(drd2.get("metadata"), dict) else {}
    drd2_positive = drd2.get("positive") if isinstance(drd2.get("positive"), dict) else {}
    drd2_cluster = drd2.get("top_decoy_cluster") if isinstance(drd2.get("top_decoy_cluster"), dict) else {}
    positive_atom_anchor = (
        drd2_positive.get("atom_anchor_diagnostics")
        if isinstance(drd2_positive.get("atom_anchor_diagnostics"), dict)
        else {}
    )
    positive_rescue = (
        drd2_positive.get("pose_physics_rescue_proxies")
        if isinstance(drd2_positive.get("pose_physics_rescue_proxies"), dict)
        else {}
    )
    positive_chem = (
        positive_rescue.get("chemistry_heuristics")
        if isinstance(positive_rescue.get("chemistry_heuristics"), dict)
        else {}
    )
    positive_trajectory_pose = (
        positive_rescue.get("trajectory_pose_preservation_proxy")
        if isinstance(positive_rescue.get("trajectory_pose_preservation_proxy"), dict)
        else {}
    )
    positive_trajectory_survival = (
        positive_rescue.get("trajectory_survival_proxy")
        if isinstance(positive_rescue.get("trajectory_survival_proxy"), dict)
        else {}
    )
    cluster_atom_anchor = (
        drd2_cluster.get("mean_atom_anchor_diagnostics")
        if isinstance(drd2_cluster.get("mean_atom_anchor_diagnostics"), dict)
        else {}
    )
    cluster_rescue = (
        drd2_cluster.get("mean_rescue_proxy_diagnostics")
        if isinstance(drd2_cluster.get("mean_rescue_proxy_diagnostics"), dict)
        else {}
    )
    lines.extend(
        [
            "",
            "## DRD2 Pose/Physics Anchor Proxy",
            "",
            f"- feature_basis: `{drd2_meta.get('feature_basis', '')}`",
            f"- proxy_source_columns: `{', '.join(drd2_meta.get('proxy_source_columns', []))}`",
            f"- positive_ligand_id: `{drd2_positive.get('ligand_id', '')}`",
            f"- top_decoy_cluster_size: `{drd2_cluster.get('size', 0)}`",
            f"- positive_atom_anchor_mean_distance_A: `{positive_atom_anchor.get('anchor_mean_distance_A', '')}`",
            f"- decoy_cluster_atom_anchor_mean_distance_A: `{cluster_atom_anchor.get('anchor_mean_distance_A', '')}`",
            f"- positive_basic_amine_like: `{str(positive_chem.get('basic_amine_like', False)).lower()}`",
            f"- positive_tautomer_or_protonation_review_flag: `{str(positive_chem.get('tautomer_or_protonation_review_flag', False)).lower()}`",
            f"- positive_pose_preservation_rmsd_A: `{positive_rescue.get('pose_preservation_rmsd_proxy', {}).get('value', '')}`",
            f"- positive_local_minimization_survival_support: `{positive_rescue.get('local_minimization_survival_proxy', {}).get('support_proxy', '')}`",
            f"- positive_trajectory_pose_p90_frame_rmsd_A: `{positive_trajectory_pose.get('p90_frame_rmsd_A', '')}`",
            f"- positive_trajectory_pose_support: `{positive_trajectory_pose.get('support_proxy', '')}`",
            f"- positive_trajectory_survival_support: `{positive_trajectory_survival.get('support_proxy', '')}`",
            f"- decoy_cluster_basic_amine_like_count: `{cluster_rescue.get('basic_amine_like_count', '')}`",
            f"- decoy_cluster_pose_preservation_rmsd_available_count: `{cluster_rescue.get('pose_preservation_rmsd_available_count', '')}`",
            f"- decoy_cluster_local_minimization_survival_available_count: `{cluster_rescue.get('local_minimization_survival_available_count', '')}`",
            f"- decoy_cluster_trajectory_pose_p90_frame_rmsd_mean_A: `{cluster_rescue.get('trajectory_pose_p90_frame_rmsd_mean_A', '')}`",
            f"- decoy_cluster_trajectory_pose_support_mean: `{cluster_rescue.get('trajectory_pose_support_mean', '')}`",
            f"- decoy_cluster_trajectory_survival_support_mean: `{cluster_rescue.get('trajectory_survival_support_mean', '')}`",
        ]
    )
    pairwise = (
        payload.get("drd2_target_internal_pairwise_diagnostic")
        if isinstance(payload.get("drd2_target_internal_pairwise_diagnostic"), dict)
        else {}
    )
    pairwise_positive = pairwise.get("positive") if isinstance(pairwise.get("positive"), dict) else {}
    overanchor = (
        pairwise.get("top_decoy_cluster_anchor_overanchoring_summary")
        if isinstance(pairwise.get("top_decoy_cluster_anchor_overanchoring_summary"), dict)
        else {}
    )
    acidic_probe = (
        pairwise.get("acidic_anchor_overcontact_probe")
        if isinstance(pairwise.get("acidic_anchor_overcontact_probe"), dict)
        else {}
    )
    post_v3_review = (
        payload.get("post_v3_acidic_anchor_review")
        if isinstance(payload.get("post_v3_acidic_anchor_review"), dict)
        else {}
    )
    post_v4_review = (
        payload.get("post_v4_fixed_reference_redesign")
        if isinstance(payload.get("post_v4_fixed_reference_redesign"), dict)
        else {}
    )
    collapse = (
        post_v4_review.get("fixed_reference_replay_feature_collapse")
        if isinstance(post_v4_review.get("fixed_reference_replay_feature_collapse"), dict)
        else {}
    )
    v2_fixed = (
        post_v4_review.get("fixed_reference_v2_formula_replay")
        if isinstance(post_v4_review.get("fixed_reference_v2_formula_replay"), dict)
        else {}
    )
    v5_replay = (
        post_v4_review.get("latest_v5_replay")
        if isinstance(post_v4_review.get("latest_v5_replay"), dict)
        else {}
    )
    shadow = pairwise.get("shadow_replay_snapshot") if isinstance(pairwise.get("shadow_replay_snapshot"), dict) else {}
    guarded = pairwise.get("guarded_validation_prep") if isinstance(pairwise.get("guarded_validation_prep"), dict) else {}
    rescue_after_v5 = (
        payload.get("drd2_pose_physics_rescue_after_v5_reject_packet")
        if isinstance(payload.get("drd2_pose_physics_rescue_after_v5_reject_packet"), dict)
        else {}
    )
    rescue_compare = (
        rescue_after_v5.get("positive_vs_top_decoy_cluster")
        if isinstance(rescue_after_v5.get("positive_vs_top_decoy_cluster"), dict)
        else {}
    )
    motif = (
        payload.get(DRD2_LABEL_FREE_MOTIF_SUBLANE)
        if isinstance(payload.get(DRD2_LABEL_FREE_MOTIF_SUBLANE), dict)
        else {}
    )
    motif_compare = (
        motif.get("positive_vs_top_decoy_cluster")
        if isinstance(motif.get("positive_vs_top_decoy_cluster"), dict)
        else {}
    )
    motif_positive = (
        motif_compare.get("positive") if isinstance(motif_compare.get("positive"), dict) else {}
    )
    motif_positive_amine = (
        motif_positive.get("cationic_basic_amine_support")
        if isinstance(motif_positive.get("cationic_basic_amine_support"), dict)
        else {}
    )
    motif_positive_acidic = (
        motif_positive.get("acidic_anchor_window_overanchor_validity")
        if isinstance(motif_positive.get("acidic_anchor_window_overanchor_validity"), dict)
        else {}
    )
    motif_positive_traj = (
        motif_positive.get("trajectory_pose_survival_proxy")
        if isinstance(motif_positive.get("trajectory_pose_survival_proxy"), dict)
        else {}
    )
    motif_positive_prior = (
        motif_positive.get("ligand_prior_pressure")
        if isinstance(motif_positive.get("ligand_prior_pressure"), dict)
        else {}
    )
    motif_cluster = (
        motif_compare.get("top_decoy_cluster")
        if isinstance(motif_compare.get("top_decoy_cluster"), dict)
        else {}
    )
    motif_cluster_amine = (
        motif_cluster.get("cationic_basic_amine_support")
        if isinstance(motif_cluster.get("cationic_basic_amine_support"), dict)
        else {}
    )
    motif_cluster_acidic = (
        motif_cluster.get("acidic_anchor_window_overanchor_validity")
        if isinstance(motif_cluster.get("acidic_anchor_window_overanchor_validity"), dict)
        else {}
    )
    motif_cluster_traj = (
        motif_cluster.get("trajectory_pose_survival_proxy")
        if isinstance(motif_cluster.get("trajectory_pose_survival_proxy"), dict)
        else {}
    )
    motif_cluster_prior = (
        motif_cluster.get("ligand_prior_pressure")
        if isinstance(motif_cluster.get("ligand_prior_pressure"), dict)
        else {}
    )
    v6_candidate = (
        payload.get("class_a_motif_shadow_v6_candidate")
        if isinstance(payload.get("class_a_motif_shadow_v6_candidate"), dict)
        else {}
    )
    v6_replay = (
        payload.get("class_a_motif_shadow_v6_replay")
        if isinstance(payload.get("class_a_motif_shadow_v6_replay"), dict)
        else {}
    )
    v7_candidate = (
        payload.get("class_a_anchor_geometry_shadow_v7_candidate")
        if isinstance(payload.get("class_a_anchor_geometry_shadow_v7_candidate"), dict)
        else {}
    )
    v7_replay = (
        payload.get("class_a_anchor_geometry_shadow_v7_replay")
        if isinstance(payload.get("class_a_anchor_geometry_shadow_v7_replay"), dict)
        else {}
    )
    v8_candidate = (
        payload.get("direct_atom_anchor_window_shadow_v8_candidate")
        if isinstance(payload.get("direct_atom_anchor_window_shadow_v8_candidate"), dict)
        else {}
    )
    v8_replay = (
        payload.get("direct_atom_anchor_window_shadow_v8_replay")
        if isinstance(payload.get("direct_atom_anchor_window_shadow_v8_replay"), dict)
        else {}
    )
    v9_candidate = (
        payload.get("atom_window_excess_polar_shadow_v9_candidate")
        if isinstance(payload.get("atom_window_excess_polar_shadow_v9_candidate"), dict)
        else {}
    )
    v9_replay = (
        payload.get("atom_window_excess_polar_shadow_v9_replay")
        if isinstance(payload.get("atom_window_excess_polar_shadow_v9_replay"), dict)
        else {}
    )
    lines.extend(
        [
            "",
            "## DRD2 Target-Internal Pairwise Diagnostic",
            "",
            f"- diagnostic_only: `{str(pairwise.get('metadata', {}).get('diagnostic_only', False)).lower()}`",
            f"- replay_only: `{str(pairwise.get('metadata', {}).get('replay_only', False)).lower()}`",
            f"- positive_ligand_id: `{pairwise_positive.get('ligand_id', '')}`",
            f"- positive_within_target_rank: `{pairwise_positive.get('within_target_rank', '')}`",
            f"- decoys_above_positive_count: `{pairwise.get('decoys_above_positive_count', '')}`",
            f"- decoys_above_positive_fraction: `{pairwise.get('decoys_above_positive_fraction', '')}`",
            f"- pairwise_win_rate: `{pairwise.get('pairwise_win_rate', '')}`",
            f"- pairwise_win_count: `{pairwise.get('pairwise_win_count', '')}`",
            f"- top12_best_margin_vs_positive: `{pairwise.get('top12_decoy_margin_vs_positive', {}).get('best_margin', '')}`",
            f"- top50_mean_margin_vs_positive: `{pairwise.get('top50_decoy_margin_vs_positive', {}).get('mean_margin', '')}`",
            f"- overanchored_decoy_count: `{overanchor.get('overanchored_decoy_count', '')}`",
            f"- overanchored_without_basic_amine_count: `{overanchor.get('overanchored_without_basic_amine_count', '')}`",
            f"- acidic_anchor_probe_available_count: `{acidic_probe.get('atom_anchor_available_count', '')}`",
            f"- acidic_anchor_min_lt_3A_count: `{acidic_probe.get('anchor_min_distance_lt_3A_count', '')}`",
            f"- acidic_anchor_p10_lt_3A_count: `{acidic_probe.get('anchor_p10_distance_lt_3A_count', '')}`",
            f"- post_v3_candidate_variant: `{post_v3_review.get('candidate_variant', '')}`",
            f"- post_v3_required_scaling_mode: `{post_v3_review.get('required_scaling_mode', '')}`",
            f"- post_v3_overcontact_signal_present: `{str(post_v3_review.get('overcontact_signal_present', False)).lower()}`",
            f"- post_v4_candidate_variant: `{post_v4_review.get('candidate_variant', '')}`",
            f"- post_v4_required_scaling_mode: `{post_v4_review.get('required_scaling_mode', '')}`",
            f"- post_v4_best_baseline_variant: `{post_v4_review.get('best_baseline_variant', '')}`",
            f"- fixed_reference_v2_formula_pr_auc_approx: `{v2_fixed.get('pr_auc_approx', '')}`",
            f"- fixed_reference_v2_formula_top20_hit_rate: `{v2_fixed.get('top20_hit_rate', '')}`",
            f"- fixed_reference_safe_to_port_v2_or_v4_weights: `{str(v2_fixed.get('safe_to_port_v2_or_v4_weights', False)).lower()}`",
            f"- fixed_reference_conserved_anchor_nonzero: `{collapse.get('gpcr_conserved_anchor_proxy_nonzero', '')}`",
            f"- fixed_reference_pose_physics_nonzero: `{collapse.get('pose_physics_support_nonzero', '')}`",
            f"- fixed_reference_acidic_gate_nonzero: `{collapse.get('gpcr_acidic_anchor_overcontact_prior_gate_nonzero', '')}`",
            f"- fixed_reference_pose_chemistry_pressure_nonzero: `{collapse.get('gpcr_pose_chemistry_hard_decoy_pressure_nonzero', '')}`",
            f"- v5_replay_status: `{v5_replay.get('status', '')}`",
            f"- v5_replay_pr_auc: `{v5_replay.get('pr_auc', '')}`",
            f"- v5_replay_pr_auc_ci_low: `{v5_replay.get('pr_auc_ci_low', '')}`",
            f"- v5_replay_top20_hit_rate: `{v5_replay.get('top20_hit_rate', '')}`",
            f"- v5_replay_beats_v2_shadow_baseline: `{str(v5_replay.get('beats_v2_shadow_baseline', False)).lower()}`",
            f"- v5_fixed_reference_live_positive_pressure_count: `{v5_replay.get('fixed_reference_live_positive_pressure_count', '')}`",
            f"- shadow_replay_pr_auc: `{shadow.get('family_anchor_v2_shadow_pr_auc', '')}`",
            f"- shadow_replay_pr_auc_ci_low: `{shadow.get('family_anchor_v2_shadow_pr_auc_ci_low', '')}`",
            f"- shadow_replay_drd2_global_rank: `{shadow.get('family_anchor_v2_shadow_drd2_global_rank', '')}`",
            f"- shadow_replay_drd2_decoys_above_positive_count: `{shadow.get('family_anchor_v2_shadow_drd2_decoys_above_positive_count', '')}`",
            f"- shadow_replay_drd2_pairwise_win_rate: `{shadow.get('family_anchor_v2_shadow_drd2_pairwise_win_rate', '')}`",
            f"- shadow_replay_ci_low_computed: `{str(shadow.get('ci_low_computed', False)).lower()}`",
            f"- shadow_replay_claim_review_status: `{shadow.get('family_anchor_v2_shadow_claim_review_status', '')}`",
            f"- v6_candidate_status: `{v6_candidate.get('status', '')}`",
            f"- v6_candidate_next_action: `{v6_candidate.get('next_action', '')}`",
            f"- v6_active_score_locked_to_base: `{str(v6_candidate.get('active_score_locked_to_base', False)).lower()}`",
            f"- v6_scorer_apply_allowed: `{str(v6_candidate.get('scorer_apply_allowed', True)).lower()}`",
            f"- v6_broad_gpcr_claim_allowed: `{str(v6_candidate.get('broad_gpcr_claim_allowed', True)).lower()}`",
            f"- v6_replay_status: `{v6_replay.get('status', '')}`",
            f"- v6_replay_pr_auc: `{v6_replay.get('pr_auc', '')}`",
            f"- v6_replay_pr_auc_ci_low: `{v6_replay.get('pr_auc_ci_low', '')}`",
            f"- v6_replay_top20_hit_rate: `{v6_replay.get('top20_hit_rate', '')}`",
            f"- v6_v2_baseline_label_basis: `{v6_replay.get('v2_baseline_label_basis', '')}`",
            f"- v6_v2_pr_auc_baseline: `{v6_replay.get('v2_pr_auc_baseline', '')}`",
            f"- v6_v2_pr_auc_ci_low_baseline: `{v6_replay.get('v2_pr_auc_ci_low_baseline', '')}`",
            f"- v6_replay_beats_v2_shadow_baseline: `{str(v6_replay.get('beats_v2_shadow_baseline', False)).lower()}`",
            f"- v7_candidate_status: `{v7_candidate.get('status', '')}`",
            f"- v7_candidate_next_action: `{v7_candidate.get('next_action', '')}`",
            f"- v7_active_score_locked_to_base: `{str(v7_candidate.get('active_score_locked_to_base', False)).lower()}`",
            f"- v7_scorer_apply_allowed: `{str(v7_candidate.get('scorer_apply_allowed', True)).lower()}`",
            f"- v7_broad_gpcr_claim_allowed: `{str(v7_candidate.get('broad_gpcr_claim_allowed', True)).lower()}`",
            f"- v7_replay_status: `{v7_replay.get('status', '')}`",
            f"- v7_replay_pr_auc: `{v7_replay.get('pr_auc', '')}`",
            f"- v7_replay_pr_auc_ci_low: `{v7_replay.get('pr_auc_ci_low', '')}`",
            f"- v7_replay_top20_hit_rate: `{v7_replay.get('top20_hit_rate', '')}`",
            f"- v7_v2_baseline_label_basis: `{v7_replay.get('v2_baseline_label_basis', '')}`",
            f"- v7_v2_pr_auc_baseline: `{v7_replay.get('v2_pr_auc_baseline', '')}`",
            f"- v7_v2_pr_auc_ci_low_baseline: `{v7_replay.get('v2_pr_auc_ci_low_baseline', '')}`",
            f"- v7_replay_beats_v2_shadow_baseline: `{str(v7_replay.get('beats_v2_shadow_baseline', False)).lower()}`",
            f"- v8_candidate_status: `{v8_candidate.get('status', '')}`",
            f"- v8_candidate_next_action: `{v8_candidate.get('next_action', '')}`",
            f"- v8_active_score_locked_to_base: `{str(v8_candidate.get('active_score_locked_to_base', False)).lower()}`",
            f"- v8_requires_precomputed_atom_window_features: `{str(v8_candidate.get('requires_precomputed_atom_window_features', False)).lower()}`",
            f"- v8_scorer_apply_allowed: `{str(v8_candidate.get('scorer_apply_allowed', True)).lower()}`",
            f"- v8_broad_gpcr_claim_allowed: `{str(v8_candidate.get('broad_gpcr_claim_allowed', True)).lower()}`",
            f"- v8_replay_status: `{v8_replay.get('status', '')}`",
            f"- v8_replay_pr_auc: `{v8_replay.get('pr_auc', '')}`",
            f"- v8_replay_pr_auc_ci_low: `{v8_replay.get('pr_auc_ci_low', '')}`",
            f"- v8_replay_top20_hit_rate: `{v8_replay.get('top20_hit_rate', '')}`",
            f"- v8_feature_cache_matched_row_count: `{v8_replay.get('feature_cache_matched_row_count', '')}`",
            f"- v8_atom_anchor_feature_available_count: `{v8_replay.get('atom_anchor_feature_available_count', '')}`",
            f"- v8_direct_atom_window_anchor_geometry_positive_count: `{v8_replay.get('direct_atom_window_anchor_geometry_positive_count', '')}`",
            f"- v8_hydrophobic_overcontact_pressure_positive_count: `{v8_replay.get('hydrophobic_overcontact_pressure_positive_count', '')}`",
            f"- v8_v2_baseline_label_basis: `{v8_replay.get('v2_baseline_label_basis', '')}`",
            f"- v8_replay_beats_v2_shadow_baseline: `{str(v8_replay.get('beats_v2_shadow_baseline', False)).lower()}`",
            f"- v9_candidate_status: `{v9_candidate.get('status', '')}`",
            f"- v9_candidate_next_action: `{v9_candidate.get('next_action', '')}`",
            f"- v9_active_score_locked_to_base: `{str(v9_candidate.get('active_score_locked_to_base', False)).lower()}`",
            f"- v9_requires_precomputed_atom_window_features: `{str(v9_candidate.get('requires_precomputed_atom_window_features', False)).lower()}`",
            f"- v9_scorer_apply_allowed: `{str(v9_candidate.get('scorer_apply_allowed', True)).lower()}`",
            f"- v9_broad_gpcr_claim_allowed: `{str(v9_candidate.get('broad_gpcr_claim_allowed', True)).lower()}`",
            f"- v9_replay_status: `{v9_replay.get('status', '')}`",
            f"- v9_replay_pr_auc: `{v9_replay.get('pr_auc', '')}`",
            f"- v9_replay_pr_auc_ci_low: `{v9_replay.get('pr_auc_ci_low', '')}`",
            f"- v9_replay_top20_hit_rate: `{v9_replay.get('top20_hit_rate', '')}`",
            f"- v9_reset_prior_active_to_base: `{str(v9_replay.get('reset_prior_active_to_base', False)).lower()}`",
            f"- v9_feature_cache_matched_row_count: `{v9_replay.get('feature_cache_matched_row_count', '')}`",
            f"- v9_atom_anchor_feature_available_count: `{v9_replay.get('atom_anchor_feature_available_count', '')}`",
            f"- v9_excess_polar_anchor_pressure_positive_count: `{v9_replay.get('excess_polar_anchor_pressure_positive_count', '')}`",
            f"- v9_compact_amine_window_support_positive_count: `{v9_replay.get('compact_amine_window_support_positive_count', '')}`",
            f"- v9_v2_baseline_label_basis: `{v9_replay.get('v2_baseline_label_basis', '')}`",
            f"- v9_replay_beats_v2_shadow_baseline: `{str(v9_replay.get('beats_v2_shadow_baseline', False)).lower()}`",
            f"- ready_for_guarded_apply: `{str(guarded.get('ready_for_guarded_apply', False)).lower()}`",
            "",
            "## DRD2 Pose/Physics Rescue After V5 Reject",
            "",
            f"- diagnostic_only: `{str(rescue_after_v5.get('diagnostic_only', False)).lower()}`",
            f"- local_only: `{str(rescue_after_v5.get('local_only', False)).lower()}`",
            f"- bounded_no_full_100k: `{str(rescue_after_v5.get('bounded_no_full_100k', False)).lower()}`",
            f"- claim_promotion_allowed: `{str(rescue_after_v5.get('claim_promotion_allowed', True)).lower()}`",
            f"- scorer_apply_allowed: `{str(rescue_after_v5.get('scorer_apply_allowed', True)).lower()}`",
            f"- threshold_relaxation_allowed: `{str(rescue_after_v5.get('threshold_relaxation_allowed', True)).lower()}`",
            f"- target_identity_feature_allowed: `{str(rescue_after_v5.get('target_identity_feature_allowed', True)).lower()}`",
            f"- amine_anchor_support_separation_positive_minus_decoy_mean: `{rescue_compare.get('amine_anchor_support_separation_positive_minus_decoy_mean', '')}`",
            f"- trajectory_pose_support_separation_positive_minus_decoy_mean: `{rescue_compare.get('trajectory_pose_support_separation_positive_minus_decoy_mean', '')}`",
            f"- trajectory_survival_support_separation_positive_minus_decoy_mean: `{rescue_compare.get('trajectory_survival_support_separation_positive_minus_decoy_mean', '')}`",
            f"- trajectory_pose_p90_frame_rmsd_decoy_mean_minus_positive_A: `{rescue_compare.get('trajectory_pose_p90_frame_rmsd_decoy_mean_minus_positive_A', '')}`",
            f"- overanchored_without_basic_amine_count: `{rescue_compare.get('overanchored_without_basic_amine_count', '')}`",
            "",
            "## DRD2 Label-Free Motif-Aware Diagnostic",
            "",
            f"- sublane: `{motif.get('sublane', '')}`",
            f"- diagnostic_only: `{str(motif.get('diagnostic_only', False)).lower()}`",
            f"- claim_promotion_allowed: `{str(motif.get('claim_promotion_allowed', True)).lower()}`",
            f"- scorer_apply_allowed: `{str(motif.get('scorer_apply_allowed', True)).lower()}`",
            f"- router_claim_allowed: `{str(motif.get('router_claim_allowed', True)).lower()}`",
            f"- platform_claim_allowed: `{str(motif.get('platform_claim_allowed', True)).lower()}`",
            f"- positive_basic_amine_like: `{str(motif_positive_amine.get('basic_amine_like', False)).lower()}`",
            f"- positive_amine_anchor_support_proxy: `{motif_positive_amine.get('amine_anchor_support_proxy', '')}`",
            f"- positive_acidic_overanchor_flag: `{str(motif_positive_acidic.get('acidic_overanchor_flag', False)).lower()}`",
            f"- positive_trajectory_pose_support: `{motif_positive_traj.get('pose_support_proxy', '')}`",
            f"- positive_trajectory_survival_support: `{motif_positive_traj.get('survival_support_proxy', '')}`",
            f"- positive_prior_high_flag: `{str(motif_positive_prior.get('prior_high_flag', False)).lower()}`",
            f"- decoy_cluster_basic_amine_like_count: `{motif_cluster_amine.get('basic_amine_like_count', '')}`",
            f"- decoy_cluster_acidic_overanchor_count: `{motif_cluster_acidic.get('acidic_overanchor_count', '')}`",
            f"- decoy_cluster_trajectory_pose_support_mean: `{motif_cluster_traj.get('pose_support_mean', '')}`",
            f"- decoy_cluster_trajectory_survival_support_mean: `{motif_cluster_traj.get('survival_support_mean', '')}`",
            f"- decoy_cluster_prior_high_count: `{motif_cluster_prior.get('prior_high_count', '')}`",
            f"- basic_amine_absent_acidic_overanchor_prior_high_cluster_count: `{motif_compare.get('basic_amine_absent_acidic_overanchor_prior_high_cluster_count', '')}`",
            f"- basic_amine_absent_acidic_overanchor_prior_high_cluster_coverage: `{motif_compare.get('basic_amine_absent_acidic_overanchor_prior_high_cluster_coverage', '')}`",
        ]
    )
    lines.extend(["", "## Next Step", "", f"- {summary['next_required_step']}", ""])
    return "\n".join(lines)


def write_outputs(
    *,
    rows_csv: str | Path | None,
    stage3_csv: str | Path | None,
    ci_json: str | Path | None,
    readiness_json: str | Path | None,
    out_json: str | Path,
    out_md: str | Path,
) -> dict[str, Any]:
    payload = build_packet(
        rows_csv=rows_csv,
        stage3_csv=stage3_csv,
        ci_json=ci_json,
        readiness_json=readiness_json,
    )
    out_json_path = _resolve(out_json)
    out_md_path = _resolve(out_md)
    assert out_json_path is not None
    assert out_md_path is not None
    _write_json(out_json_path, payload)
    out_md_path.parent.mkdir(parents=True, exist_ok=True)
    out_md_path.write_text(render_markdown(payload), encoding="utf-8")
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build diagnostic packet for GPCR guarded 100k rank failure.")
    parser.add_argument("--rows-csv", default=DEFAULT_ROWS_CSV)
    parser.add_argument("--stage3-csv", default=DEFAULT_STAGE3_CSV)
    parser.add_argument("--ci-json", default=DEFAULT_CI_JSON)
    parser.add_argument("--readiness-json", default=DEFAULT_READINESS_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    write_outputs(
        rows_csv=args.rows_csv,
        stage3_csv=args.stage3_csv,
        ci_json=args.ci_json,
        readiness_json=args.readiness_json,
        out_json=args.out_json,
        out_md=args.out_md,
    )


if __name__ == "__main__":
    main()
