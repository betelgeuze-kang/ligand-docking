#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from tools.build_gpcr_drd2_hard_decoy_slice_packet import _candidate_pressures
from tools.build_gpcr_drd2_hard_decoy_slice_packet import _weak_base_rescue_support
from tools.repair_gpcr_drd2_pseudo_allatom_backmapping import (
    _anchor_indices,
    _backmap_frames,
    _rdkit_conformer,
)

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_INPUT_CSV = (
    "runs/external_validation_2026-05-03_family_balanced_frozen_r2_set1_core_blind_gpcr_core_full_"
    "p0_n100000_r1_stage3_scores.csv"
)
DEFAULT_NON_ADRB2_NATIVE_SOURCE_CSV = "config/gpcr_non_adrb2_native_sources_v1.csv"
DEFAULT_ADRB2_NATIVE_SOURCE_CSV = "config/real_drug_targets_blind_gpcr_adrb2_v1.csv"
DEFAULT_OUT_CSV = "runs/gpcr_cationic_pose_distortion_frozen_feature_cache_current.csv"
DEFAULT_OUT_JSON = "runs/gpcr_cationic_pose_distortion_frozen_feature_cache_current.json"
DEFAULT_OUT_MD = "runs/gpcr_cationic_pose_distortion_frozen_feature_cache_current.md"

_CONFORMER_CACHE: dict[str, dict[str, Any]] = {}


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else (ROOT / path).resolve()


def _text(value: Any) -> str:
    return str(value or "").strip()


def _float(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if np.isfinite(parsed) else default


def _clip01(value: float) -> float:
    return float(np.clip(_float(value), 0.0, 1.0))


def _read_csv(path_like: str | Path) -> list[dict[str, str]]:
    path = _resolve(path_like)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _row_key(row: dict[str, Any]) -> tuple[str, str]:
    return (_text(row.get("target")), _text(row.get("ligand_id")))


def _cached_conformer(smiles: str) -> dict[str, Any]:
    key = _text(smiles)
    if key not in _CONFORMER_CACHE:
        _CONFORMER_CACHE[key] = _rdkit_conformer(key)
    return _CONFORMER_CACHE[key]


def _native_path_from_pdb_id(pdb_id: str) -> str:
    pdb = _text(pdb_id).lower()
    if not pdb:
        return ""
    candidate = ROOT / "runs/gpcr_frozen_candidate_profile_support_current/native_pdb" / f"{pdb}.pdb"
    return str(candidate) if candidate.exists() else ""


def _native_path_lookup(
    *,
    non_adrb2_native_source_csv: str | Path = DEFAULT_NON_ADRB2_NATIVE_SOURCE_CSV,
    adrb2_native_source_csv: str | Path = DEFAULT_ADRB2_NATIVE_SOURCE_CSV,
) -> dict[str, str]:
    out: dict[str, str] = {}
    for row in _read_csv(adrb2_native_source_csv):
        target = _text(row.get("target"))
        native = _text(row.get("native_pdb_path"))
        if target and native:
            out[target] = str(_resolve(native))
    for row in _read_csv(non_adrb2_native_source_csv):
        target = _text(row.get("target"))
        native = _text(row.get("native_pdb_path")) or _native_path_from_pdb_id(_text(row.get("pdb_id")))
        if target and native:
            out[target] = str(_resolve(native))
    return out


def _target_filter_set(value: str) -> set[str]:
    return {item.strip() for item in str(value or "").split(",") if item.strip()}


def _score(row: dict[str, str]) -> float:
    for col in (
        "binding_score_composite_v7",
        # Residual-active columns can be stale when a stage CSV is reused after
        # shadow experiments. Feature caches must anchor to the immutable v7
        # base score unless only a generic score column exists.
        "binding_score_composite_v7_residual_active",
        "score",
    ):
        if _text(row.get(col)):
            return _float(row.get(col), 0.0)
    return 0.0


def _v12_anchor_terms(
    *,
    anchor_mode: str,
    support_pressure: float,
    weak_base_support_pressure: float,
    basic_amine_count: int,
    pose_rmsd_A: float,
) -> dict[str, float]:
    all_basic_anchor = 1.0 if str(anchor_mode or "").strip().lower() == "all_basic" and basic_amine_count > 0 else 0.0
    saturated = all_basic_anchor * _clip01((support_pressure - 0.90) / 0.08)
    plausible_window = _clip01((support_pressure - 0.35) / 0.25) * _clip01((0.86 - support_pressure) / 0.20)
    multi_basic = _clip01((float(basic_amine_count) - 1.0) / 1.0)
    pose_preserved = _clip01((1.35 - pose_rmsd_A) / 0.60)
    moderate_multi_support = weak_base_support_pressure * plausible_window * multi_basic * pose_preserved
    return {
        "v12_synthetic_anchor_saturation_pressure": saturated,
        "v12_moderate_multi_basic_weakbase_support_pressure": moderate_multi_support,
        "v12_plausible_anchor_window_support": plausible_window,
        "v12_multi_basic_support_gate": multi_basic,
        "v12_pose_preservation_gate": pose_preserved,
    }


def _v14_anchor_occupancy_terms(
    *,
    distance_features: dict[str, Any],
    basic_amine_count: int,
    pose_preservation_support: float,
) -> dict[str, float]:
    cationic_available = _clip01(distance_features.get("cationic_center_available"))
    cationic_window = _clip01(distance_features.get("cationic_center_contact_fraction_2p8_4p2A"))
    cationic_too_close = _clip01(distance_features.get("cationic_center_contact_fraction_le_2p8A"))
    basic_gate = _clip01(float(basic_amine_count))
    pose_gate = _clip01(pose_preservation_support)
    occupancy_support = cationic_available * basic_gate * cationic_window * (1.0 - cationic_too_close) * pose_gate
    overclose_artifact = cationic_available * cationic_too_close * (1.0 - occupancy_support) * (1.0 - pose_gate)
    return {
        "v14_cationic_anchor_occupancy_support": occupancy_support,
        "v14_cationic_anchor_window_gate": cationic_available * basic_gate * cationic_window,
        "v14_cationic_overclose_artifact_pressure": overclose_artifact,
        "v14_pose_preservation_support_gate": pose_gate,
    }


def _distance_features(
    *,
    ligand_frames: np.ndarray,
    protein_atom_frames: np.ndarray,
    anchor_indices: list[int],
    basic_indices: list[int],
) -> dict[str, Any]:
    frame_count = min(int(ligand_frames.shape[0]), int(protein_atom_frames.shape[0]))
    base = {
        "atom_anchor_available": 0,
        "atom_anchor_min_distance_A": "",
        "atom_anchor_p10_distance_A": "",
        "atom_anchor_mean_distance_A": "",
        "atom_contact_fraction_le_2p8A": 0.0,
        "atom_contact_fraction_2p8_4p2A": 0.0,
        "cationic_center_available": 0,
        "cationic_center_basic_atom_count": len(basic_indices),
        "cationic_center_min_distance_A": "",
        "cationic_center_p10_distance_A": "",
        "cationic_center_mean_distance_A": "",
        "cationic_center_contact_fraction_le_2p8A": 0.0,
        "cationic_center_contact_fraction_2p8_4p2A": 0.0,
        "cationic_center_contact_fraction_ge_4p2A": 0.0,
    }
    if frame_count <= 0 or not anchor_indices:
        return base
    ligand = ligand_frames[:frame_count]
    protein = protein_atom_frames[:frame_count]
    anchor_frames = protein[:, anchor_indices, :]
    atom_distances = np.linalg.norm(ligand[:, :, None, :] - anchor_frames[:, None, :, :], axis=3).min(axis=(1, 2))
    base.update(
        {
            "atom_anchor_available": 1,
            "atom_anchor_min_distance_A": float(np.min(atom_distances)),
            "atom_anchor_p10_distance_A": float(np.percentile(atom_distances, 10)),
            "atom_anchor_mean_distance_A": float(np.mean(atom_distances)),
            "atom_contact_fraction_le_2p8A": float(np.mean(atom_distances <= 2.8)),
            "atom_contact_fraction_2p8_4p2A": float(np.mean((atom_distances >= 2.8) & (atom_distances <= 4.2))),
        }
    )
    valid_basic = [idx for idx in basic_indices if 0 <= idx < ligand.shape[1]]
    if valid_basic:
        anchor_center = np.mean(anchor_frames, axis=1)
        basic_xyz = ligand[:, valid_basic, :]
        cationic_distances = np.linalg.norm(basic_xyz - anchor_center[:, None, :], axis=2).min(axis=1)
        base.update(
            {
                "cationic_center_available": 1,
                "cationic_center_basic_atom_count": len(valid_basic),
                "cationic_center_min_distance_A": float(np.min(cationic_distances)),
                "cationic_center_p10_distance_A": float(np.percentile(cationic_distances, 10)),
                "cationic_center_mean_distance_A": float(np.mean(cationic_distances)),
                "cationic_center_contact_fraction_le_2p8A": float(np.mean(cationic_distances <= 2.8)),
                "cationic_center_contact_fraction_2p8_4p2A": float(
                    np.mean((cationic_distances >= 2.8) & (cationic_distances <= 4.2))
                ),
                "cationic_center_contact_fraction_ge_4p2A": float(np.mean(cationic_distances >= 4.2)),
            }
        )
    return base


def _cache_row(
    row: dict[str, str],
    *,
    native_lookup: dict[str, str],
    anchor_mode: str,
) -> dict[str, Any]:
    target = _text(row.get("target"))
    ligand_id = _text(row.get("ligand_id"))
    native_pdb = _text(row.get("protein_structure_source_path")) or native_lookup.get(target, "")
    trajectory_npz = _text(row.get("trajectory_npz"))
    out: dict[str, Any] = {
        "target": target,
        "ligand_id": ligand_id,
        "base_score": _score(row),
        "feature_cache_status": "not_started",
        "feature_cache_reason": "",
        "native_pdb": native_pdb,
        "trajectory_npz": trajectory_npz,
        "label_free_anchor_mode": str(anchor_mode),
        "source_ligand_frame_atom_count": "",
        "repaired_ligand_frame_atom_count": "",
        "allatom_backmapping_coverage_ratio": "",
        "basic_amine_count": 0,
        "coarse_centroid_preservation_rmsd_A_mean": 0.0,
        "atom_anchor_available": 0,
        "cationic_center_available": 0,
        "label_free_penalty_pressure": 0.0,
        "label_free_support_pressure": 0.0,
    }
    if not native_pdb:
        return {**out, "feature_cache_status": "failed", "feature_cache_reason": "native_pdb_missing"}
    npz_path = _resolve(trajectory_npz) if trajectory_npz else None
    if npz_path is None or not npz_path.exists():
        return {**out, "feature_cache_status": "failed", "feature_cache_reason": "trajectory_npz_missing"}
    conformer = _cached_conformer(_text(row.get("ligand_smiles") or row.get("smiles")))
    if not conformer.get("available"):
        return {
            **out,
            "feature_cache_status": "failed",
            "feature_cache_reason": f"conformer_unavailable:{conformer.get('reason', '')}",
        }
    try:
        with np.load(str(npz_path), allow_pickle=False) as npz:
            ligand_frames = np.asarray(npz["ligand_frames"], dtype=np.float32)
            protein_atom_frames = np.asarray(npz["protein_atom_frames"], dtype=np.float32)
    except Exception as exc:
        return {**out, "feature_cache_status": "failed", "feature_cache_reason": f"trajectory_npz_unreadable:{type(exc).__name__}"}
    if ligand_frames.ndim != 3 or protein_atom_frames.ndim != 3:
        return {**out, "feature_cache_status": "failed", "feature_cache_reason": "trajectory_frames_invalid"}
    anchor_indices = _anchor_indices(native_pdb, int(protein_atom_frames.shape[1]))
    if not anchor_indices:
        return {**out, "feature_cache_status": "failed", "feature_cache_reason": "acidic_anchor_missing"}
    basic_indices = [int(idx) for idx in conformer.get("basic_amine_atom_indices", [])]
    heavy_atoms = max(len(conformer.get("atomic_numbers", [])), 1)
    anchor_mode_norm = str(anchor_mode or "none").strip().lower()

    def _evaluate_backmap(force_anchor: bool) -> dict[str, Any] | None:
        repaired, metrics = _backmap_frames(
            ligand_frames=ligand_frames,
            protein_atom_frames=protein_atom_frames,
            anchor_indices=anchor_indices,
            conformer_coords=np.asarray(conformer["coords"], dtype=float),
            basic_indices=basic_indices,
            salt_bridge_distance_A=3.2,
            force_anchor=bool(force_anchor),
        )
        if repaired.size <= 0:
            return None
        distance_features = _distance_features(
            ligand_frames=np.asarray(repaired, dtype=float),
            protein_atom_frames=np.asarray(protein_atom_frames, dtype=float),
            anchor_indices=anchor_indices,
            basic_indices=basic_indices,
        )
        pose_rmsd = _float(metrics.get("coarse_centroid_preservation_rmsd_A_mean"), 0.0)
        pressure_input = {
            **distance_features,
            "basic_amine_count": len(basic_indices),
            "ligand_h_donors": _float(row.get("ligand_h_donors"), 0.0),
            "ligand_h_acceptors": _float(row.get("ligand_h_acceptors"), 0.0),
            "ligand_rot_bonds": _float(row.get("ligand_rot_bonds"), 0.0),
            "ligand_logp": _float(row.get("ligand_logp"), 0.0),
            "coarse_centroid_preservation_rmsd_A_mean": pose_rmsd,
        }
        return {
            "repaired": repaired,
            "metrics": metrics,
            "distance_features": distance_features,
            "pressures": _candidate_pressures(pressure_input),
            "pose_rmsd": pose_rmsd,
            "force_anchor": bool(force_anchor),
        }

    adaptive_probe: dict[str, Any] = {
        "requested_label_free_anchor_mode": str(anchor_mode),
        "effective_label_free_anchor_mode": anchor_mode_norm,
        "adaptive_none_pose_rmsd_A": "",
        "adaptive_all_basic_pose_rmsd_A": "",
        "adaptive_none_support_pressure": "",
        "adaptive_all_basic_support_pressure": "",
        "adaptive_selection_reason": "",
    }
    if anchor_mode_norm == "adaptive_pose_preserving":
        none_eval = _evaluate_backmap(False)
        forced_eval = _evaluate_backmap(True) if basic_indices else None
        if none_eval is None and forced_eval is None:
            return {**out, "feature_cache_status": "failed", "feature_cache_reason": "pseudo_allatom_backmapping_failed"}
        if none_eval is None:
            selected = forced_eval
            selected_mode = "all_basic"
            adaptive_probe["adaptive_selection_reason"] = "none_backmapping_failed"
        elif forced_eval is None:
            selected = none_eval
            selected_mode = "none"
            adaptive_probe["adaptive_selection_reason"] = (
                "no_basic_amine_for_all_basic_anchor" if not basic_indices else "all_basic_backmapping_failed"
            )
        else:
            none_pose = float(none_eval["pose_rmsd"])
            forced_pose = float(forced_eval["pose_rmsd"])
            none_support = float(none_eval["pressures"].get("label_free_support_pressure") or 0.0)
            forced_support = float(forced_eval["pressures"].get("label_free_support_pressure") or 0.0)
            none_cationic = _float(
                none_eval["distance_features"].get("cationic_center_contact_fraction_2p8_4p2A"),
                0.0,
            )
            forced_cationic = _float(
                forced_eval["distance_features"].get("cationic_center_contact_fraction_2p8_4p2A"),
                0.0,
            )
            forced_pose_support = float(forced_eval["pressures"].get("pose_preservation_support") or 0.0)
            forced_pose_collapse = forced_pose_support < 0.20 or forced_pose > max(6.0, none_pose + 6.0)
            anchor_gain = forced_support > none_support + 0.05 or forced_cationic > none_cationic + 0.25
            if anchor_gain and not forced_pose_collapse:
                selected = forced_eval
                selected_mode = "all_basic"
                adaptive_probe["adaptive_selection_reason"] = "all_basic_anchor_gain_pose_preserved"
            else:
                selected = none_eval
                selected_mode = "none"
                adaptive_probe["adaptive_selection_reason"] = (
                    "all_basic_pose_collapse_rejected" if forced_pose_collapse else "no_all_basic_anchor_gain"
                )
            adaptive_probe.update(
                {
                    "adaptive_none_pose_rmsd_A": none_pose,
                    "adaptive_all_basic_pose_rmsd_A": forced_pose,
                    "adaptive_none_support_pressure": none_support,
                    "adaptive_all_basic_support_pressure": forced_support,
                }
            )
    else:
        selected_mode = "all_basic" if anchor_mode_norm == "all_basic" and basic_indices else "none"
        selected = _evaluate_backmap(anchor_mode_norm == "all_basic" and bool(basic_indices))
        if selected is None:
            return {**out, "feature_cache_status": "failed", "feature_cache_reason": "pseudo_allatom_backmapping_failed"}
        adaptive_probe["adaptive_selection_reason"] = "fixed_anchor_mode"
    adaptive_probe["effective_label_free_anchor_mode"] = selected_mode
    repaired = selected["repaired"]
    metrics = selected["metrics"]
    distance_features = selected["distance_features"]
    pressures = selected["pressures"]
    weak_gate, weak_support = _weak_base_rescue_support(
        _score(row),
        float(pressures.get("label_free_support_pressure") or 0.0),
    )
    pose_rmsd = _float(metrics.get("coarse_centroid_preservation_rmsd_A_mean"), 0.0)
    v12_terms = _v12_anchor_terms(
        anchor_mode=str(selected_mode),
        support_pressure=float(pressures.get("label_free_support_pressure") or 0.0),
        weak_base_support_pressure=float(weak_support),
        basic_amine_count=len(basic_indices),
        pose_rmsd_A=pose_rmsd,
    )
    v14_terms = _v14_anchor_occupancy_terms(
        distance_features=distance_features,
        basic_amine_count=len(basic_indices),
        pose_preservation_support=float(pressures.get("pose_preservation_support") or 0.0),
    )
    out.update(distance_features)
    out.update(pressures)
    out.update(v12_terms)
    out.update(v14_terms)
    out.update(adaptive_probe)
    out.update(
        {
            "feature_cache_status": "ok",
            "feature_cache_reason": "label_free_pseudo_allatom_feature_cache_ready",
            "label_free_anchor_mode": str(selected_mode),
            "source_ligand_frame_atom_count": int(ligand_frames.shape[1]),
            "repaired_ligand_frame_atom_count": int(repaired.shape[1]),
            "allatom_backmapping_coverage_ratio": float(repaired.shape[1] / heavy_atoms),
            "basic_amine_count": len(basic_indices),
            "coarse_centroid_preservation_rmsd_A_mean": pose_rmsd,
            "weak_base_rescue_gate": weak_gate,
            "weak_base_rescue_support_pressure": weak_support,
        }
    )
    return out


def build_cache(
    *,
    input_csv: str | Path = DEFAULT_INPUT_CSV,
    non_adrb2_native_source_csv: str | Path = DEFAULT_NON_ADRB2_NATIVE_SOURCE_CSV,
    adrb2_native_source_csv: str | Path = DEFAULT_ADRB2_NATIVE_SOURCE_CSV,
    target_filter: str = "",
    ligand_filter: str = "",
    row_limit: int = 0,
    row_offset: int = 0,
    existing_keys: set[tuple[str, str]] | None = None,
    anchor_mode: str = "none",
    generated_at_local: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    native_lookup = _native_path_lookup(
        non_adrb2_native_source_csv=non_adrb2_native_source_csv,
        adrb2_native_source_csv=adrb2_native_source_csv,
    )
    source_rows = _read_csv(input_csv)
    targets = _target_filter_set(target_filter)
    ligands = _target_filter_set(ligand_filter)
    eligible = [
        row
        for row in source_rows
        if (not targets or _text(row.get("target")) in targets)
        and (not ligands or _text(row.get("ligand_id")) in ligands)
    ]
    start = max(0, int(row_offset or 0))
    if int(row_limit or 0) > 0:
        stop = min(len(eligible), start + int(row_limit))
        limited = eligible[start:stop]
    else:
        stop = len(eligible)
        limited = eligible[start:]
    seen = existing_keys or set()
    skipped_existing_rows = [row for row in limited if _row_key(row) in seen]
    rows_to_process = [row for row in limited if _row_key(row) not in seen]
    rows = [
        _cache_row(row, native_lookup=native_lookup, anchor_mode=str(anchor_mode))
        for row in rows_to_process
    ]
    ok_rows = [row for row in rows if row.get("feature_cache_status") == "ok"]
    reason_counts = Counter(_text(row.get("feature_cache_reason")) for row in rows if row.get("feature_cache_status") != "ok")
    target_counts = Counter(_text(row.get("target")) for row in ok_rows)
    partial = stop < len(eligible)
    status = "partial_feature_cache_ready_claim_locked" if partial else "feature_cache_ready_for_shadow_replay_claim_locked"
    if not ok_rows and not skipped_existing_rows:
        status = "blocked_no_feature_rows"
    summary = {
        "generated_at_local": generated_at_local or dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": status,
        "input_csv": str(_resolve(input_csv)),
        "input_row_count": len(source_rows),
        "eligible_row_count": len(eligible),
        "row_offset": start,
        "row_window_end": stop,
        "window_row_count": len(limited),
        "processed_row_count": len(rows),
        "skipped_existing_row_count": len(skipped_existing_rows),
        "feature_row_count": len(ok_rows),
        "failed_row_count": len(rows) - len(ok_rows),
        "partial_due_to_row_limit": bool(partial),
        "row_limit": int(row_limit or 0),
        "target_filter": sorted(targets),
        "ligand_filter": sorted(ligands),
        "target_feature_row_counts": dict(sorted(target_counts.items())),
        "failure_reason_counts": dict(sorted(reason_counts.items())),
        "label_free_anchor_mode": str(anchor_mode),
        "claim_promotion_allowed": False,
        "scorer_apply_allowed": False,
        "router_claim_allowed": False,
        "platform_claim_allowed": False,
        "broad_gpcr_claim_allowed": False,
        "next_required_step": (
            "Replay v11 with this feature cache only as claim-locked shadow evidence. Full claim review remains "
            "blocked until complete frozen-row coverage, leakage audit, family-held-out scorecard, CI-low, and top20 gates are green."
        ),
    }
    return rows, summary


def _render_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# GPCR Cationic Pose-Distortion Frozen Feature Cache",
        "",
        f"- status: `{summary['status']}`",
        f"- input_row_count: `{summary['input_row_count']}`",
        f"- eligible_row_count: `{summary['eligible_row_count']}`",
        f"- row_offset: `{summary['row_offset']}`",
        f"- row_window_end: `{summary['row_window_end']}`",
        f"- processed_row_count: `{summary['processed_row_count']}`",
        f"- skipped_existing_row_count: `{summary['skipped_existing_row_count']}`",
        f"- feature_row_count: `{summary['feature_row_count']}`",
        f"- failed_row_count: `{summary['failed_row_count']}`",
        f"- partial_due_to_row_limit: `{str(summary['partial_due_to_row_limit']).lower()}`",
        f"- label_free_anchor_mode: `{summary['label_free_anchor_mode']}`",
        "- claim_promotion_allowed: `false`",
        "- scorer_apply_allowed: `false`",
        "",
        "## Next Required Step",
        "",
        f"- {summary['next_required_step']}",
        "",
    ]
    if summary["failure_reason_counts"]:
        lines.extend(["## Failure Reasons", ""])
        for reason, count in summary["failure_reason_counts"].items():
            lines.append(f"- `{reason}`: `{count}`")
        lines.append("")
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a label-free v10 feature cache for frozen GPCR rows.")
    parser.add_argument("--input-csv", default=DEFAULT_INPUT_CSV)
    parser.add_argument("--non-adrb2-native-source-csv", default=DEFAULT_NON_ADRB2_NATIVE_SOURCE_CSV)
    parser.add_argument("--adrb2-native-source-csv", default=DEFAULT_ADRB2_NATIVE_SOURCE_CSV)
    parser.add_argument("--target-filter", default="")
    parser.add_argument("--ligand-filter", default="")
    parser.add_argument("--row-limit", type=int, default=0)
    parser.add_argument("--row-offset", type=int, default=0)
    parser.add_argument("--resume-existing", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--anchor-mode", choices=["none", "all_basic", "adaptive_pose_preserving"], default="none")
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    out_csv = _resolve(args.out_csv)
    existing_rows = _read_csv(out_csv) if bool(args.resume_existing) and out_csv.exists() else []
    existing_keys = {_row_key(row) for row in existing_rows}
    rows, summary = build_cache(
        input_csv=args.input_csv,
        non_adrb2_native_source_csv=args.non_adrb2_native_source_csv,
        adrb2_native_source_csv=args.adrb2_native_source_csv,
        target_filter=args.target_filter,
        ligand_filter=args.ligand_filter,
        row_limit=int(args.row_limit),
        row_offset=int(args.row_offset),
        existing_keys=existing_keys,
        anchor_mode=str(args.anchor_mode),
    )
    output_rows = [*existing_rows, *rows] if bool(args.resume_existing) else rows
    summary["existing_row_count"] = len(existing_rows)
    summary["total_output_row_count"] = len(output_rows)
    _write_csv(args.out_csv, output_rows)
    summary["out_csv"] = str(out_csv)
    payload = {
        "packet_type": "gpcr_cationic_pose_distortion_frozen_feature_cache",
        "summary": summary,
        "claim_boundary": {
            "claim_promotion_allowed": False,
            "scorer_apply_allowed": False,
            "selected_slice_green_is_not_claim_evidence": True,
            "threshold_relaxation_allowed": False,
            "fake_pass_allowed": False,
        },
    }
    _write_json(args.out_json, payload)
    out_md = _resolve(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(_render_markdown(summary), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
