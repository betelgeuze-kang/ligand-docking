#!/usr/bin/env python3

from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime as dt
import hashlib
import json
import math
import multiprocessing as mp
import os
import time
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

# Ensure repo-root imports work when running `python tools/...py` directly.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import numpy as np
import pandas as pd
import torch

from core.config import config
from core.definitions import StrategyType
from core.forcefield import ForceField
from core.integrator import LangevinIntegrator
from core.topology import TopologyFactory
from tools.pdb_loader import load_native_structure


TRAJECTORY_NPZ_RESERVED_KEYS: Dict[str, str] = {
    "protein_ca": "Required. Shape [P, 3] CA/protein anchor coordinates used for ligand distance screening.",
    "ligand_frames": "Required. Shape [T, L, 3] ligand coordinates for each sampled frame.",
    "frame_indices": "Optional. Shape [T]. Source frame indices for each stored ligand frame.",
    "protein_residue_rmsf": "Optional vNext. Shape [P]. Residue-level RMSF aligned to protein_ca order.",
    "protein_residue_bfactor_equivalent": "Optional vNext. Shape [P]. Precomputed B-factor-like values aligned to protein_ca order.",
    "protein_residue_centroids": "Optional vNext. Shape [T, P, 3]. Frame-wise residue centroids aligned to protein_ca order.",
    "protein_residue_schema_version": "Optional vNext. Scalar numeric contract version for residue-level overlays.",
    "protein_atom_frames": "Optional vNext. Shape [T, A, 3]. Full protein atom coordinates for frame-wise in-place protein motion, aligned to viewer proteinTemplateAtoms order.",
    "protein_atom_template_index": "Optional vNext. Shape [A]. Integer mapping from stored protein_atom_frames atom order to viewer proteinTemplateAtoms order when direct order cannot be guaranteed.",
    "protein_atom_schema_version": "Optional vNext. Scalar numeric contract version for atom-level frame mutation.",
}


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        if v is None:
            return float(default)
        s = str(v).strip()
        if (not s) or (s.lower() == "nan"):
            return float(default)
        return float(s)
    except Exception:
        return float(default)


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(float(v))
    except Exception:
        return int(default)


def _safe_bool(v: Any, default: bool = False) -> bool:
    if isinstance(v, bool):
        return bool(v)
    if v is None:
        return bool(default)
    s = str(v).strip().lower()
    if s in {"1", "true", "t", "yes", "y", "on"}:
        return True
    if s in {"0", "false", "f", "no", "n", "off"}:
        return False
    return bool(default)


def _coerce_float32_xyz_array(value: Any) -> np.ndarray:
    try:
        arr = np.asarray(value, dtype=np.float32)
    except Exception:
        return np.zeros((0, 3), dtype=np.float32)
    if arr.ndim != 2 or arr.shape[0] <= 0 or arr.shape[1] != 3:
        return np.zeros((0, 3), dtype=np.float32)
    return arr.astype(np.float32, copy=False)


def _normalize_protein_atom_template(template: Any) -> Dict[str, Any]:
    source_type = type(template).__name__ if template is not None else "none"
    out: Dict[str, Any] = {
        "coords": np.zeros((0, 3), dtype=np.float32),
        "atom_count": 0,
        "schema_version": 0,
        "ready": False,
        "source_type": str(source_type),
        "source_path": "",
        "normalization_warning": "",
    }
    if template is None:
        out["normalization_warning"] = "missing_template"
        return out
    if isinstance(template, dict):
        out["source_path"] = str(template.get("source_path", "")).strip()
        out["ready"] = bool(template.get("ready", False))
        coords = _coerce_float32_xyz_array(template.get("template_coords"))
        if bool(out["ready"]) and coords.shape[0] > 0:
            out["coords"] = coords
            out["atom_count"] = int(coords.shape[0])
            out["schema_version"] = 1
            return out
        out["normalization_warning"] = (
            "template_dict_missing_valid_template_coords"
            if bool(out["ready"])
            else "template_dict_not_ready"
        )
        return out
    coords = _coerce_float32_xyz_array(template)
    if coords.shape[0] > 0:
        out["coords"] = coords
        out["atom_count"] = int(coords.shape[0])
        out["schema_version"] = 1
        out["ready"] = True
        return out
    out["normalization_warning"] = f"unsupported_template_type:{source_type}"
    return out


def _expected_written_frames(frames: int, stride: int) -> Tuple[int, int]:
    f = int(max(frames, 1))
    s = int(max(stride, 1))
    last_idx = int(((f - 1) // s) * s)
    n = int(1 + ((f - 1) // s))
    return n, last_idx


def _parse_prod_frame_budget_tiers(spec: str) -> List[Tuple[float, float]]:
    tiers: List[Tuple[float, float]] = []
    for item in str(spec or "").split(","):
        tok = str(item).strip()
        if not tok or ":" not in tok:
            continue
        left, right = tok.split(":", 1)
        try:
            threshold = float(left)
            fraction = float(right)
        except Exception:
            continue
        tiers.append((float(max(0.0, min(1.0, threshold))), float(max(0.10, min(1.0, fraction)))))
    if not tiers:
        tiers = [
            (0.90, 1.00),
            (0.75, 0.85),
            (0.60, 0.70),
            (0.00, 0.55),
        ]
    return sorted(tiers, key=lambda x: float(x[0]), reverse=True)


def _slug(text: str) -> str:
    out: List[str] = []
    prev_us = False
    for ch in str(text).strip().lower():
        if ch.isalnum():
            out.append(ch)
            prev_us = False
            continue
        if not prev_us:
            out.append("_")
            prev_us = True
    s = "".join(out).strip("_")
    return s or "target"


def _parse_csv_set(spec: str) -> set[str]:
    out: set[str] = set()
    for item in str(spec).split(","):
        t = str(item).strip()
        if not t:
            continue
        out.add(t)
    return out


def _stable_ratio_key(value: str) -> float:
    key = str(value).encode("utf-8", errors="ignore")
    h = hashlib.md5(key).hexdigest()
    # Deterministic ratio in [0,1).
    return float(int(h[:8], 16)) / float(16**8)


def _should_retry_core_after_error(exc: Exception) -> bool:
    msg = f"{type(exc).__name__}: {exc}".strip().lower()
    signals = (
        "out of memory",
        "memory fault",
        "hiperroroutofmemory",
        "hip error",
        "cuda out of memory",
        "allocation failed",
        "abort",
        "segmentation fault",
    )
    return any(s in msg for s in signals)


def _estimate_adress_radius_A(
    *,
    affinity_hint: float,
    ligand_mw: float,
    base_radius_A: float,
    affinity_radius_scale: float,
    mw_radius_scale: float,
) -> float:
    aff = min(max(float(affinity_hint), 0.0), 1.0)
    mw_n = min(max((float(ligand_mw) - 120.0) / 500.0, 0.0), 1.0)
    return float(base_radius_A + affinity_radius_scale * aff + mw_radius_scale * mw_n)


def _estimate_atom_ratio_within_radius(
    protein_coords: np.ndarray,
    pocket_xyz: np.ndarray,
    radius_A: float,
) -> float:
    p = np.asarray(protein_coords, dtype=np.float32)
    if p.ndim != 2 or p.shape[0] <= 0 or p.shape[1] != 3:
        return 0.0
    ctr = np.asarray(pocket_xyz, dtype=np.float32).reshape(3)
    d = np.linalg.norm(p - ctr[None, :], axis=1)
    if d.size <= 0:
        return 0.0
    inside = float(np.mean(d <= float(max(radius_A, 1e-6))))
    return float(min(max(inside, 0.0), 1.0))


def _resolve_strategy_type(
    *,
    row: Dict[str, Any],
    protein_coords: np.ndarray,
    pocket_xyz: np.ndarray,
    affinity_hint: float,
    mode: str,
    dynamic_adress_min_affinity: float,
    dynamic_adress_max_protein_residues: int,
    dynamic_adress_min_ligand_mw: float,
    dynamic_adress_fraction: float,
    dynamic_adress_force_targets: set[str],
    dynamic_adress_base_radius_A: float,
    dynamic_adress_affinity_radius_scale: float,
    dynamic_adress_mw_radius_scale: float,
    dynamic_adress_max_all_atom_radius_A: float,
    dynamic_adress_max_atom_ratio: float,
    dynamic_adress_cap_force_core_on_radius: bool,
) -> Tuple[str, str, float, float]:
    m = str(mode).strip().lower()
    if m == "adress_only":
        return StrategyType.ADRESS, "mode_adress_only", 0.0, 0.0
    if m == "core_only":
        return StrategyType.DIRECT_PERTURBATION_NO_MIN, "mode_core_only", 0.0, 0.0

    target = str(row.get("target", "")).strip()
    queue_id = str(row.get("queue_id", "")).strip()
    ligand_id = str(row.get("ligand_id", "")).strip()
    ligand_mw = _safe_float(row.get("ligand_mw", 0.0))
    protein_res_count = int(protein_coords.shape[0]) if isinstance(protein_coords, np.ndarray) else 0

    if _safe_bool(row.get("force_core_only", False)):
        return StrategyType.DIRECT_PERTURBATION_NO_MIN, "row_force_core_only", 0.0, 0.0
    if target in dynamic_adress_force_targets:
        candidate = StrategyType.ADRESS
        reason = "force_target"
    elif _safe_bool(row.get("prefer_adress", False)):
        candidate = StrategyType.ADRESS
        reason = "row_prefer_adress"
    elif int(protein_res_count) > int(dynamic_adress_max_protein_residues):
        return StrategyType.DIRECT_PERTURBATION_NO_MIN, "protein_too_large", 0.0, 0.0
    elif float(affinity_hint) < float(dynamic_adress_min_affinity):
        return StrategyType.DIRECT_PERTURBATION_NO_MIN, "affinity_low", 0.0, 0.0
    elif float(ligand_mw) < float(dynamic_adress_min_ligand_mw):
        return StrategyType.DIRECT_PERTURBATION_NO_MIN, "ligand_mw_low", 0.0, 0.0
    else:
        frac = min(max(float(dynamic_adress_fraction), 0.0), 1.0)
        if frac <= 0.0:
            return StrategyType.DIRECT_PERTURBATION_NO_MIN, "dynamic_fraction_zero", 0.0, 0.0
        if frac < 1.0:
            ratio_key = queue_id or f"{target}|{ligand_id}"
            if _stable_ratio_key(ratio_key) >= frac:
                return StrategyType.DIRECT_PERTURBATION_NO_MIN, "dynamic_fraction_skip", 0.0, 0.0
        candidate = StrategyType.ADRESS
        reason = "dynamic_eligible"

    if str(candidate) != str(StrategyType.ADRESS):
        return str(candidate), str(reason), 0.0, 0.0

    raw_radius_A = _estimate_adress_radius_A(
        affinity_hint=float(affinity_hint),
        ligand_mw=float(ligand_mw),
        base_radius_A=float(dynamic_adress_base_radius_A),
        affinity_radius_scale=float(dynamic_adress_affinity_radius_scale),
        mw_radius_scale=float(dynamic_adress_mw_radius_scale),
    )
    max_radius_A = float(max(dynamic_adress_max_all_atom_radius_A, 1e-6))
    capped_radius_A = float(min(raw_radius_A, max_radius_A))
    if bool(dynamic_adress_cap_force_core_on_radius) and (raw_radius_A > max_radius_A):
        return (
            StrategyType.DIRECT_PERTURBATION_NO_MIN,
            f"{reason}+hard_cap_radius",
            float(capped_radius_A),
            0.0,
        )
    atom_ratio = _estimate_atom_ratio_within_radius(
        protein_coords=protein_coords,
        pocket_xyz=pocket_xyz,
        radius_A=float(capped_radius_A),
    )
    if float(atom_ratio) > float(dynamic_adress_max_atom_ratio):
        return (
            StrategyType.DIRECT_PERTURBATION_NO_MIN,
            f"{reason}+hard_cap_atom_ratio",
            float(capped_radius_A),
            float(atom_ratio),
        )
    if raw_radius_A > max_radius_A:
        reason = f"{reason}+radius_clamped"
    return str(candidate), str(reason), float(capped_radius_A), float(atom_ratio)


def _parse_pdb_ca_or_atom_coords(path: str) -> np.ndarray:
    src = str(path).strip()
    if (not src) or (not os.path.exists(src)):
        return np.zeros((0, 3), dtype=np.float32)
    ca: List[List[float]] = []
    xyz: List[List[float]] = []
    with open(src, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if not (line.startswith("ATOM") or line.startswith("HETATM")):
                continue
            try:
                x = float(line[30:38])
                y = float(line[38:46])
                z = float(line[46:54])
            except Exception:
                continue
            atom = str(line[12:16]).strip().upper()
            xyz.append([x, y, z])
            if atom == "CA":
                ca.append([x, y, z])
    use = ca if len(ca) > 0 else xyz
    if len(use) <= 0:
        return np.zeros((0, 3), dtype=np.float32)
    return np.asarray(use, dtype=np.float32)


def _candidate_native_structure_paths(target: str, native_path: str) -> List[str]:
    paths: List[str] = []
    explicit = str(native_path).strip()
    if explicit and os.path.exists(explicit):
        paths.append(explicit)
    fallback = os.path.join("data", "native", f"{str(target).strip().lower()}.pdb")
    if fallback and os.path.exists(fallback) and fallback not in paths:
        paths.append(fallback)
    return paths


def _parse_pdb_all_atom_coords(path: str) -> np.ndarray:
    src = str(path).strip()
    if (not src) or (not os.path.exists(src)):
        return np.zeros((0, 3), dtype=np.float32)
    xyz: List[List[float]] = []
    with open(src, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if not line.startswith("ATOM"):
                continue
            try:
                x = float(line[30:38])
                y = float(line[38:46])
                z = float(line[46:54])
            except Exception:
                continue
            xyz.append([x, y, z])
    if len(xyz) <= 0:
        return np.zeros((0, 3), dtype=np.float32)
    return np.asarray(xyz, dtype=np.float32)


def _load_protein_coords(target: str, native_path: str) -> np.ndarray:
    for candidate in _candidate_native_structure_paths(target=target, native_path=native_path):
        arr = _parse_pdb_ca_or_atom_coords(candidate)
        if arr.shape[0] > 0:
            return arr
    c, _ = load_native_structure(str(target))
    if c is None:
        return np.zeros((0, 3), dtype=np.float32)
    arr = c.detach().cpu().numpy()
    if arr.ndim != 2 or arr.shape[1] != 3:
        return np.zeros((0, 3), dtype=np.float32)
    return arr.astype(np.float32, copy=False)


def _load_protein_atom_template(target: str, native_path: str) -> Dict[str, Any]:
    for candidate in _candidate_native_structure_paths(target=target, native_path=native_path):
        src = str(candidate).strip()
        if (not src) or (not os.path.exists(src)):
            continue
        atom_records: List[Dict[str, Any]] = []
        residue_first_seen: List[Tuple[str, str, str]] = []
        residue_first_seen_set: set[Tuple[str, str, str]] = set()
        residue_anchor_by_key: Dict[Tuple[str, str, str], np.ndarray] = {}
        residue_ca_by_key: Dict[Tuple[str, str, str], np.ndarray] = {}
        with open(src, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if not line.startswith("ATOM"):
                    continue
                try:
                    x = float(line[30:38])
                    y = float(line[38:46])
                    z = float(line[46:54])
                except Exception:
                    continue
                atom_name = str(line[12:16]).strip().upper()
                residue_name = str(line[17:20]).strip() or "PRT"
                chain_id = str(line[21:22]).strip() or "_"
                residue_seq = str(line[22:26]).strip()
                insertion_code = str(line[26:27]).strip()
                element = str(line[76:78]).strip() or atom_name[:2] or "C"
                key = (chain_id, residue_seq, insertion_code)
                coord = np.asarray([x, y, z], dtype=np.float32)
                if key not in residue_first_seen_set:
                    residue_first_seen_set.add(key)
                    residue_first_seen.append(key)
                    residue_anchor_by_key[key] = coord
                if atom_name == "CA" and key not in residue_ca_by_key:
                    residue_ca_by_key[key] = coord
                atom_records.append(
                    {
                        "atomName": atom_name[:4] or "C",
                        "residueName": residue_name[:3] or "PRT",
                        "chainId": chain_id[:1] or "_",
                        "residueSeq": residue_seq,
                        "insertionCode": insertion_code[:1],
                        "element": element[:2] or "C",
                        "coord": coord,
                        "residueKey": key,
                    }
                )

        if not atom_records:
            continue
        if residue_ca_by_key:
            residue_order = [key for key in residue_first_seen if key in residue_ca_by_key]
            anchor_by_key = residue_ca_by_key
        else:
            residue_order = list(residue_first_seen)
            anchor_by_key = residue_anchor_by_key
        residue_index_by_key = {key: idx for idx, key in enumerate(residue_order)}
        template_atoms: List[Dict[str, Any]] = []
        atom_residue_index: List[int] = []
        template_coords: List[np.ndarray] = []
        for atom in atom_records:
            residue_index = residue_index_by_key.get(atom["residueKey"])
            if residue_index is None:
                continue
            template_atoms.append(atom)
            atom_residue_index.append(int(residue_index))
            template_coords.append(np.asarray(atom["coord"], dtype=np.float32))
        template_coords_np = np.asarray(template_coords, dtype=np.float32)
        atom_residue_index_np = np.asarray(atom_residue_index, dtype=np.int32)
        native_anchor_coords = np.asarray(
            [np.asarray(anchor_by_key[key], dtype=np.float32) for key in residue_order if key in anchor_by_key],
            dtype=np.float32,
        )
        ready = bool(
            template_coords_np.ndim == 2
            and template_coords_np.shape[0] > 0
            and template_coords_np.shape[1] == 3
            and atom_residue_index_np.shape[0] == template_coords_np.shape[0]
            and native_anchor_coords.ndim == 2
            and native_anchor_coords.shape[0] > 0
            and native_anchor_coords.shape[1] == 3
        )
        if not ready:
            continue
        return {
            "ready": True,
            "source_path": src,
            "template_atoms": template_atoms,
            "template_coords": template_coords_np,
            "atom_residue_index": atom_residue_index_np,
            "native_anchor_coords": native_anchor_coords,
            "residue_count": int(native_anchor_coords.shape[0]),
            "atom_count": int(template_coords_np.shape[0]),
        }
    return {
        "ready": False,
        "source_path": "",
        "template_atoms": [],
        "template_coords": np.zeros((0, 3), dtype=np.float32),
        "atom_residue_index": np.zeros((0,), dtype=np.int32),
        "native_anchor_coords": np.zeros((0, 3), dtype=np.float32),
        "residue_count": 0,
        "atom_count": 0,
    }


def _expand_protein_atom_frames(protein_frames: np.ndarray, template: Dict[str, Any]) -> Optional[np.ndarray]:
    frames = np.asarray(protein_frames, dtype=np.float32)
    if frames.ndim != 3 or frames.shape[0] <= 0 or frames.shape[2] != 3:
        return None
    template_coords = np.asarray(template.get("template_coords", np.zeros((0, 3), dtype=np.float32)), dtype=np.float32)
    native_anchor_coords = np.asarray(template.get("native_anchor_coords", np.zeros((0, 3), dtype=np.float32)), dtype=np.float32)
    atom_residue_index = np.asarray(template.get("atom_residue_index", np.zeros((0,), dtype=np.int32)), dtype=np.int32)
    if (
        template_coords.ndim != 2
        or template_coords.shape[0] <= 0
        or template_coords.shape[1] != 3
        or native_anchor_coords.ndim != 2
        or native_anchor_coords.shape[0] <= 0
        or native_anchor_coords.shape[1] != 3
        or atom_residue_index.ndim != 1
        or atom_residue_index.shape[0] != template_coords.shape[0]
    ):
        return None
    if frames.shape[1] != native_anchor_coords.shape[0]:
        return None
    shifted = frames - native_anchor_coords[None, :, :]
    protein_atom_frames = template_coords[None, :, :] + shifted[:, atom_residue_index, :]
    return np.asarray(protein_atom_frames, dtype=np.float32)


def _compose_ligand_xyz(row: Dict[str, Any]) -> np.ndarray:
    px = _safe_float(row.get("pocket_x", 0.0))
    py = _safe_float(row.get("pocket_y", 0.0))
    pz = _safe_float(row.get("pocket_z", 0.0))
    b0 = np.asarray(
        [
            _safe_float(row.get("ligand_bead0_x", -0.8)),
            _safe_float(row.get("ligand_bead0_y", 0.0)),
            _safe_float(row.get("ligand_bead0_z", 0.0)),
        ],
        dtype=np.float32,
    )
    b1 = np.asarray(
        [
            _safe_float(row.get("ligand_bead1_x", 0.8)),
            _safe_float(row.get("ligand_bead1_y", 0.0)),
            _safe_float(row.get("ligand_bead1_z", 0.0)),
        ],
        dtype=np.float32,
    )
    ctr = np.asarray([px, py, pz], dtype=np.float32)
    return np.stack([ctr + b0, ctr + b1], axis=0)


def _ligand_affinity_hint(row: Dict[str, Any]) -> float:
    mw = _safe_float(row.get("ligand_mw", 200.0))
    logp = _safe_float(row.get("ligand_logp", 1.0))
    rot = _safe_float(row.get("ligand_rot_bonds", 2.0))
    h_d = _safe_float(row.get("ligand_h_donors", 0.0))
    h_a = _safe_float(row.get("ligand_h_acceptors", 0.0))

    mw_n = min(max((mw - 120.0) / 500.0, 0.0), 1.0)
    logp_n = min(max((logp + 1.5) / 6.5, 0.0), 1.0)
    rot_n = min(max(rot / 12.0, 0.0), 1.0)
    polar_n = min(max((h_d + h_a) / 14.0, 0.0), 1.0)
    return float(0.35 * mw_n + 0.35 * logp_n + 0.15 * rot_n + 0.15 * polar_n)


def _batch_strategy_bucket_from_row(
    row: Dict[str, Any],
    *,
    mode: str,
    dynamic_adress_min_affinity: float,
    dynamic_adress_min_ligand_mw: float,
    dynamic_adress_force_targets: set[str],
) -> int:
    m = str(mode).strip().lower()
    if m == "adress_only":
        return 2
    if m == "core_only":
        return 0
    target = str(row.get("target", "")).strip()
    if target in dynamic_adress_force_targets:
        return 2
    if _safe_bool(row.get("force_core_only", False)):
        return 0
    if _safe_bool(row.get("prefer_adress", False)):
        return 2
    affinity = _ligand_affinity_hint(row)
    ligand_mw = _safe_float(row.get("ligand_mw", 0.0))
    if affinity >= float(dynamic_adress_min_affinity) and ligand_mw >= float(dynamic_adress_min_ligand_mw):
        return 2
    return 0


def _prod_frame_budget_score(
    *,
    affinity_hint: float,
    ligand_mw: float,
    strategy_type: str,
) -> float:
    aff = min(max(float(affinity_hint), 0.0), 1.0)
    mw_n = min(max((float(ligand_mw) - 120.0) / 500.0, 0.0), 1.0)
    score = 0.75 * aff + 0.25 * mw_n
    if str(strategy_type) == str(StrategyType.ADRESS):
        score = min(1.0, score + 0.05)
    return float(min(max(score, 0.0), 1.0))


def _resolve_prod_effective_frames(
    *,
    requested_frames: int,
    affinity_hint: float,
    ligand_mw: float,
    strategy_type: str,
    prod_mode: bool,
    adaptive_budget_enabled: bool,
    prod_min_frames: int,
    prod_frame_budget_tiers: Sequence[Tuple[float, float]],
) -> Tuple[int, float, bool]:
    requested = int(max(1, int(requested_frames)))
    minimum = int(max(1, min(int(prod_min_frames), requested)))
    score = _prod_frame_budget_score(
        affinity_hint=float(affinity_hint),
        ligand_mw=float(ligand_mw),
        strategy_type=str(strategy_type),
    )
    if (not bool(prod_mode)) or (not bool(adaptive_budget_enabled)):
        return requested, float(score), False
    fraction = 1.0
    for threshold, candidate_fraction in prod_frame_budget_tiers:
        if score >= float(threshold):
            fraction = float(candidate_fraction)
            break
    effective = int(max(minimum, min(requested, int(round(requested * fraction)))))
    return int(effective), float(score), bool(effective < requested)


def _window_drift(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    arr = np.asarray(values, dtype=np.float64)
    return float(np.max(arr) - np.min(arr))


def _prod_window_is_stable(
    *,
    min_distance_history: Sequence[float],
    contact_fraction_history: Sequence[float],
    min_distance_drift_A: float,
    contact_fraction_drift: float,
    max_mean_min_distance_A: float,
) -> bool:
    if not min_distance_history or not contact_fraction_history:
        return False
    mean_min_distance = float(np.mean(np.asarray(min_distance_history, dtype=np.float64)))
    if mean_min_distance > float(max_mean_min_distance_A):
        return False
    return (
        _window_drift(min_distance_history) <= float(max(0.0, min_distance_drift_A))
        and _window_drift(contact_fraction_history) <= float(max(0.0, contact_fraction_drift))
    )


def _resolve_prod_artifact_light_settings(
    *,
    prod_mode: bool,
    prod_light_artifacts: bool,
    manifest_chunk_size: int,
    progress_every_jobs: int,
    prod_light_progress_every_jobs: int,
) -> Dict[str, Any]:
    enabled = bool(prod_mode and prod_light_artifacts)
    effective_manifest_chunk_size = int(max(0, int(manifest_chunk_size)))
    effective_progress_every_jobs = int(max(1, int(progress_every_jobs)))
    if enabled:
        effective_manifest_chunk_size = 0
        effective_progress_every_jobs = int(
            max(effective_progress_every_jobs, max(1, int(prod_light_progress_every_jobs)))
        )
    return {
        "enabled": bool(enabled),
        "manifest_chunk_size": int(effective_manifest_chunk_size),
        "progress_every_jobs": int(effective_progress_every_jobs),
        "target_tail_disabled": bool(enabled),
        "summary_md_disabled": bool(enabled),
        "manifest_chunks_disabled": bool(enabled),
    }


def _to_atom_line(
    serial: int,
    atom_name: str,
    res_name: str,
    chain_id: str,
    res_seq: int,
    xyz: Sequence[float],
    element: str,
    hetatm: bool = False,
) -> str:
    rec = "HETATM" if bool(hetatm) else "ATOM  "
    x, y, z = float(xyz[0]), float(xyz[1]), float(xyz[2])
    return (
        f"{rec}{serial:5d} {atom_name:<4s}{res_name:>3s} {chain_id:1s}{res_seq:4d}    "
        f"{x:8.3f}{y:8.3f}{z:8.3f}{1.00:6.2f}{30.0:6.2f}          {element:>2s}"
    )


def _write_frame_pdb(path: str, protein_ca: np.ndarray, ligand_xyz: np.ndarray, frame_idx: int) -> None:
    lines: List[str] = [f"REMARK LIGAND_TRAJECTORY_FRAME {int(frame_idx)}"]
    serial = 1
    for i in range(int(protein_ca.shape[0])):
        lines.append(_to_atom_line(serial, "CA", "GLY", "A", i + 1, protein_ca[i], "C", hetatm=False))
        serial += 1
    lines.append("TER")
    for i in range(int(ligand_xyz.shape[0])):
        lines.append(_to_atom_line(serial, f"C{i+1}", "LIG", "L", 1, ligand_xyz[i], "C", hetatm=True))
        serial += 1
    lines.append("END")
    _ensure_dir(os.path.dirname(path) or ".")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def _write_npz_bundle(
    path: str,
    protein_ca: np.ndarray,
    ligand_frames: np.ndarray,
    frame_indices: np.ndarray,
    compression: str = "store",
    extra_arrays: Optional[Dict[str, Any]] = None,
) -> None:
    _ensure_dir(os.path.dirname(path) or ".")
    mode = str(compression or "store").strip().lower()
    writer = np.savez_compressed if mode == "compressed" else np.savez
    payload: Dict[str, Any] = dict(
        protein_ca=np.asarray(protein_ca, dtype=np.float32),
        ligand_frames=np.asarray(ligand_frames, dtype=np.float32),
        frame_indices=np.asarray(frame_indices, dtype=np.int32),
    )
    if extra_arrays:
        for key, value in extra_arrays.items():
            if key not in TRAJECTORY_NPZ_RESERVED_KEYS:
                continue
            if value is None:
                continue
            payload[str(key)] = np.asarray(value)
    writer(path, **payload)


def _selected_frame_indices(frames: int, stride: int) -> np.ndarray:
    f = int(max(frames, 1))
    s = int(max(stride, 1))
    idx = np.arange(0, f, s, dtype=np.int32)
    if idx.size <= 0:
        idx = np.asarray([0], dtype=np.int32)
    return idx


def _batched_min_distance_contact_fraction(
    protein_xyz: Any,
    ligand_xyz_batch: Any,
    *,
    contact_cutoff_A: float = 6.0,
) -> Tuple[np.ndarray, np.ndarray, str]:
    try:
        if isinstance(ligand_xyz_batch, torch.Tensor):
            lig_t = ligand_xyz_batch.to(dtype=torch.float32)
            device = lig_t.device
        else:
            lig_t = torch.as_tensor(ligand_xyz_batch, dtype=torch.float32)
            device = lig_t.device
        if lig_t.ndim == 2:
            lig_t = lig_t.unsqueeze(0)
        if lig_t.ndim != 3 or lig_t.shape[0] <= 0 or lig_t.shape[1] <= 0 or lig_t.shape[2] != 3:
            raise ValueError("ligand_xyz_batch must have shape [B, L, 3]")
        if isinstance(protein_xyz, torch.Tensor):
            prot_t = protein_xyz.to(device=device, dtype=torch.float32)
        else:
            prot_t = torch.as_tensor(protein_xyz, dtype=torch.float32, device=device)
        if prot_t.ndim != 2 or prot_t.shape[0] <= 0 or prot_t.shape[1] != 3:
            raise ValueError("protein_xyz must have shape [P, 3]")
        dist = torch.cdist(prot_t.unsqueeze(0).expand(int(lig_t.shape[0]), -1, -1), lig_t, p=2.0)
        min_distance = dist.amin(dim=(1, 2)).detach().cpu().numpy().astype(np.float32, copy=False)
        contact_fraction = (
            (dist < float(contact_cutoff_A)).to(dtype=torch.float32).mean(dim=(1, 2)).detach().cpu().numpy().astype(np.float32, copy=False)
        )
        return min_distance, contact_fraction, "torch_batch"
    except Exception:
        prot = np.asarray(protein_xyz, dtype=np.float32)
        lig = np.asarray(ligand_xyz_batch, dtype=np.float32)
        if lig.ndim == 2:
            lig = lig[None, :, :]
        min_distance_rows: List[float] = []
        contact_fraction_rows: List[float] = []
        for frame in lig:
            ff = _inline_frame_mmpbsa_proxy(
                prot,
                frame,
                affinity_hint=0.0,
                onsps_norm=0.0,
                contact_cutoff_A=float(contact_cutoff_A),
            )
            min_distance_rows.append(float(ff["min_distance_A"]))
            contact_fraction_rows.append(float(ff["contact_fraction"]))
        return (
            np.asarray(min_distance_rows, dtype=np.float32),
            np.asarray(contact_fraction_rows, dtype=np.float32),
            "cpu_per_row_fallback",
        )


def _inline_frame_mmpbsa_proxy(
    protein_xyz: np.ndarray,
    ligand_xyz: np.ndarray,
    *,
    affinity_hint: float,
    onsps_norm: float,
    contact_cutoff_A: float = 6.0,
) -> Dict[str, float]:
    prot = np.asarray(protein_xyz, dtype=np.float32)
    lig = np.asarray(ligand_xyz, dtype=np.float32)
    if prot.ndim != 2 or lig.ndim != 2 or prot.shape[0] <= 0 or lig.shape[0] <= 0:
        return {
            "min_distance_A": 999.0,
            "contact_fraction": 0.0,
            "deltaG_mmpbsa_proxy_kcal_mol": 5.0,
            "e_vdw": 0.0,
            "e_polar": 0.0,
            "e_nonpolar": 0.0,
            "e_solvation": 5.0,
        }
    diff = prot[:, None, :] - lig[None, :, :]
    d = np.linalg.norm(diff, axis=2)
    min_d = float(np.min(d))
    contacts = float(np.sum(d < float(contact_cutoff_A)))
    close_contacts = float(np.sum(d < 4.5))
    hb_contacts = float(np.sum(d < 3.6))
    clashes = float(np.sum(d < 2.1))
    denom = float(max(int(d.size), 1))
    contact_fraction = float(contacts / denom)
    affinity = float(max(0.0, min(1.0, affinity_hint)))
    onsps = float(max(0.0, min(1.0, onsps_norm)))
    e_vdw = (
        -(0.015 + 0.05 * affinity) * contacts
        -(0.03 + 0.07 * affinity) * close_contacts
        + (0.22 + 0.05 * (1.0 - affinity)) * clashes
    )
    e_polar = -(0.02 + 0.04 * onsps) * hb_contacts
    e_nonpolar = -(0.01 + 0.05 * affinity) * contacts
    e_solv = 0.12 * max(0.0, min_d - 4.0) + 0.35 * max(0.0, 0.20 - contact_fraction)
    delta_g = float(e_vdw + e_polar + e_nonpolar + e_solv)
    return {
        "min_distance_A": float(min_d),
        "contact_fraction": float(contact_fraction),
        "deltaG_mmpbsa_proxy_kcal_mol": float(delta_g),
        "e_vdw": float(e_vdw),
        "e_polar": float(e_polar),
        "e_nonpolar": float(e_nonpolar),
        "e_solvation": float(e_solv),
    }


def _compute_inline_aux_features(
    *,
    protein_ca: np.ndarray,
    ligand_frames: np.ndarray,
    frame_indices: np.ndarray,
    affinity_hint: float,
    onsps_norm: float,
    sim_fps: float,
) -> Dict[str, float]:
    prot = np.asarray(protein_ca, dtype=np.float32)
    lig = np.asarray(ligand_frames, dtype=np.float32)
    idx = np.asarray(frame_indices, dtype=np.int32)
    if prot.ndim != 2 or lig.ndim != 3 or lig.shape[0] <= 0:
        return {
            "inline_aux_available": False,
            "trajectory_frame_count": int(lig.shape[0]) if lig.ndim >= 1 else 0,
            "frame_index_start": int(idx[0]) if idx.size else 0,
            "frame_index_end": int(idx[-1]) if idx.size else 0,
        }
    min_dists: List[float] = []
    contact_fracs: List[float] = []
    energies: List[float] = []
    e_vdw_rows: List[float] = []
    e_polar_rows: List[float] = []
    e_nonpolar_rows: List[float] = []
    e_solv_rows: List[float] = []
    centroids = lig.mean(axis=1, dtype=np.float32)
    for frame in lig:
        ff = _inline_frame_mmpbsa_proxy(
            prot,
            frame,
            affinity_hint=float(affinity_hint),
            onsps_norm=float(onsps_norm),
        )
        min_dists.append(float(ff["min_distance_A"]))
        contact_fracs.append(float(ff["contact_fraction"]))
        energies.append(float(ff["deltaG_mmpbsa_proxy_kcal_mol"]))
        e_vdw_rows.append(float(ff["e_vdw"]))
        e_polar_rows.append(float(ff["e_polar"]))
        e_nonpolar_rows.append(float(ff["e_nonpolar"]))
        e_solv_rows.append(float(ff["e_solvation"]))
    min_arr = np.asarray(min_dists, dtype=np.float64)
    c_arr = np.asarray(contact_fracs, dtype=np.float64)
    e_arr = np.asarray(energies, dtype=np.float64)
    if centroids.shape[0] > 1:
        step = np.linalg.norm(centroids[1:] - centroids[:-1], axis=1)
        final_shift = float(np.linalg.norm(centroids[-1] - centroids[0]))
    else:
        step = np.zeros((0,), dtype=np.float32)
        final_shift = 0.0
    center_mean = centroids.mean(axis=0) if centroids.size else np.zeros((3,), dtype=np.float32)
    dispersion = np.linalg.norm(centroids - center_mean[None, :], axis=1) if centroids.size else np.zeros((0,), dtype=np.float32)
    std_min_distance = float(np.std(min_arr)) if min_arr.size else 0.0
    contact_fraction = float(np.mean(c_arr)) if c_arr.size else 0.0
    stability_score = float(contact_fraction / (1.0 + std_min_distance))
    quality_score = float(np.mean(min_arr <= 6.0)) if min_arr.size else 0.0
    return {
        "inline_aux_available": True,
        "trajectory_frame_count": int(lig.shape[0]),
        "frame_index_start": int(idx[0]) if idx.size else 0,
        "frame_index_end": int(idx[-1]) if idx.size else 0,
        "mean_min_distance_A": float(np.mean(min_arr)) if min_arr.size else 0.0,
        "min_min_distance_A": float(np.min(min_arr)) if min_arr.size else 0.0,
        "final_min_distance_A": float(min_arr[-1]) if min_arr.size else 0.0,
        "std_min_distance_A": float(std_min_distance),
        "contact_fraction": float(contact_fraction),
        "contact_fraction_4p5A": float(np.mean(min_arr <= 4.5)) if min_arr.size else 0.0,
        "contact_fraction_6A": float(np.mean(min_arr <= 6.0)) if min_arr.size else 0.0,
        "contact_fraction_8A": float(np.mean(min_arr <= 8.0)) if min_arr.size else 0.0,
        "centroid_path_A": float(step.sum()) if step.size else 0.0,
        "mean_step_A": float(step.mean()) if step.size else 0.0,
        "max_step_A": float(step.max()) if step.size else 0.0,
        "centroid_dispersion_A": float(dispersion.mean()) if dispersion.size else 0.0,
        "final_shift_A": float(final_shift),
        "binding_energy_proxy": float(np.mean(e_arr)) if e_arr.size else 0.0,
        "binding_energy_mmpbsa_kcal_mol_proxy": float(np.mean(e_arr)) if e_arr.size else 0.0,
        "binding_energy_mmpbsa_std": float(np.std(e_arr)) if e_arr.size else 0.0,
        "mean_e_vdw": float(np.mean(e_vdw_rows)) if e_vdw_rows else 0.0,
        "mean_e_polar": float(np.mean(e_polar_rows)) if e_polar_rows else 0.0,
        "mean_e_nonpolar": float(np.mean(e_nonpolar_rows)) if e_nonpolar_rows else 0.0,
        "mean_e_solvation": float(np.mean(e_solv_rows)) if e_solv_rows else 0.0,
        "stability_score": float(stability_score),
        "quality_score": float(quality_score),
        "sim_fps_inline": float(sim_fps),
    }


def _write_trajectory_artifact(
    *,
    protein_ca: np.ndarray,
    ligand_frames: np.ndarray,
    frame_indices: np.ndarray,
    frame_output_format: str,
    npz_path: str,
    tdir: str,
    npz_compression: str,
    protein_atom_template: Optional[np.ndarray] = None,
    npz_extra_arrays: Optional[Dict[str, Any]] = None,
) -> int:
    if str(frame_output_format) == "manifest_only":
        arr = np.asarray(ligand_frames)
        return int(arr.shape[0]) if arr.ndim >= 1 else 0
    if str(frame_output_format) == "npz_bundle":
        resolved_extra_arrays: Dict[str, Any] = dict(npz_extra_arrays or {})
        protein_atom_template_meta = _normalize_protein_atom_template(protein_atom_template)
        protein_atom_template_np = np.asarray(protein_atom_template_meta["coords"], dtype=np.float32)
        ligand_frames_np = np.asarray(ligand_frames, dtype=np.float32)
        if (
            protein_atom_template_np.ndim == 2
            and protein_atom_template_np.shape[0] > 0
            and protein_atom_template_np.shape[1] == 3
            and ligand_frames_np.ndim == 3
            and ligand_frames_np.shape[0] > 0
        ):
            frame_count = int(ligand_frames_np.shape[0])
            atom_count = int(protein_atom_template_np.shape[0])
            resolved_extra_arrays.setdefault(
                "protein_atom_frames",
                np.broadcast_to(protein_atom_template_np[None, :, :], (frame_count, atom_count, 3)).astype(np.float32, copy=False),
            )
            resolved_extra_arrays.setdefault("protein_atom_template_index", np.arange(atom_count, dtype=np.int32))
            resolved_extra_arrays.setdefault("protein_atom_schema_version", np.asarray(1, dtype=np.int32))
        _write_npz_bundle(
            npz_path,
            protein_ca=np.asarray(protein_ca, dtype=np.float32),
            ligand_frames=np.asarray(ligand_frames, dtype=np.float32),
            frame_indices=np.asarray(frame_indices, dtype=np.int32),
            compression=str(npz_compression),
            extra_arrays=resolved_extra_arrays,
        )
        arr = np.asarray(ligand_frames)
        return int(arr.shape[0]) if arr.ndim >= 1 else 0

    written = 0
    lig = np.asarray(ligand_frames, dtype=np.float32)
    idx = np.asarray(frame_indices, dtype=np.int32)
    for frame_idx, xyz in zip(idx.tolist(), lig, strict=False):
        out_path = os.path.join(tdir, f"frame_{int(frame_idx):05d}.pdb")
        _write_frame_pdb(out_path, protein_ca=np.asarray(protein_ca, dtype=np.float32), ligand_xyz=xyz, frame_idx=int(frame_idx))
        written += 1
    return int(written)


def _drain_writer_futures(
    futures: List[cf.Future],
    *,
    wait_all: bool = False,
    keep_max_pending: int = 0,
) -> None:
    if not futures:
        return
    if wait_all:
        done, pending = cf.wait(futures, return_when=cf.ALL_COMPLETED)
        for fut in done:
            fut.result()
        futures[:] = list(pending)
        return

    limit = int(max(0, int(keep_max_pending)))
    while len(futures) > limit:
        done, pending = cf.wait(futures, return_when=cf.FIRST_COMPLETED)
        for fut in done:
            fut.result()
        futures[:] = list(pending)


def _writer_process_main(task_queue: Any, result_queue: Any) -> None:
    while True:
        task = task_queue.get()
        if task is None:
            task_queue.task_done()
            break
        try:
            _write_trajectory_artifact(
                protein_ca=task["protein_ca"],
                ligand_frames=task["ligand_frames"],
                frame_indices=task["frame_indices"],
                frame_output_format=task["frame_output_format"],
                npz_path=task["npz_path"],
                tdir=task["tdir"],
                npz_compression=task["npz_compression"],
                protein_atom_template=task.get("protein_atom_template"),
                npz_extra_arrays=task.get("npz_extra_arrays"),
            )
            result_queue.put({"ok": True})
        except Exception as exc:
            result_queue.put(
                {
                    "ok": False,
                    "error": f"{type(exc).__name__}: {exc}",
                    "queue_id": str(task.get("queue_id", "")),
                    "target": str(task.get("target", "")),
                    "ligand_id": str(task.get("ligand_id", "")),
                    "trajectory_npz": str(task.get("npz_path", "")),
                    "protein_atom_template_source_type": str(task.get("protein_atom_template_source_type", "")),
                }
            )
        finally:
            task_queue.task_done()


def _drain_writer_process_results(
    result_queue: Any,
    *,
    expected_min: int = 0,
) -> int:
    drained = 0
    while drained < int(max(0, expected_min)):
        item = result_queue.get()
        drained += 1
        if not bool(item.get("ok", False)):
            context = " ".join(
                part
                for part in [
                    f"queue_id={item.get('queue_id', '')}" if item.get("queue_id") else "",
                    f"target={item.get('target', '')}" if item.get("target") else "",
                    f"ligand_id={item.get('ligand_id', '')}" if item.get("ligand_id") else "",
                    (
                        f"template_source_type={item.get('protein_atom_template_source_type', '')}"
                        if item.get("protein_atom_template_source_type")
                        else ""
                    ),
                    f"trajectory_npz={item.get('trajectory_npz', '')}" if item.get("trajectory_npz") else "",
                ]
                if part
            )
            detail = str(item.get("error", "unknown"))
            if context:
                raise RuntimeError(f"writer_process_failed {context}: {detail}")
            raise RuntimeError(f"writer_process_failed: {detail}")
    while True:
        try:
            item = result_queue.get_nowait()
        except Exception:
            break
        drained += 1
        if not bool(item.get("ok", False)):
            context = " ".join(
                part
                for part in [
                    f"queue_id={item.get('queue_id', '')}" if item.get("queue_id") else "",
                    f"target={item.get('target', '')}" if item.get("target") else "",
                    f"ligand_id={item.get('ligand_id', '')}" if item.get("ligand_id") else "",
                    (
                        f"template_source_type={item.get('protein_atom_template_source_type', '')}"
                        if item.get("protein_atom_template_source_type")
                        else ""
                    ),
                    f"trajectory_npz={item.get('trajectory_npz', '')}" if item.get("trajectory_npz") else "",
                ]
                if part
            )
            detail = str(item.get("error", "unknown"))
            if context:
                raise RuntimeError(f"writer_process_failed {context}: {detail}")
            raise RuntimeError(f"writer_process_failed: {detail}")
    return int(drained)


def _row_batch_signature(
    *,
    protein_key: Tuple[str, str],
    protein_shape: Tuple[int, int],
    ligand_shape: Tuple[int, int],
    strategy_type: str,
    effective_frames_requested: int,
) -> Tuple[Any, ...]:
    return (
        str(protein_key[0]),
        str(protein_key[1]),
        tuple(int(x) for x in protein_shape),
        tuple(int(x) for x in ligand_shape),
        str(strategy_type),
        int(effective_frames_requested),
    )


def _register_batch_limit_derate(
    *,
    batch_limit_by_sig: Dict[Tuple[Any, ...], int],
    sig: Tuple[Any, ...],
    attempted_size: int,
    reason: str,
    events: Optional[List[Dict[str, Any]]] = None,
    event_limit: int = 64,
) -> Tuple[int, bool]:
    attempted = int(max(1, int(attempted_size)))
    previous = int(max(1, int(batch_limit_by_sig.get(sig, attempted))))
    next_limit = int(max(1, min(previous, attempted // 2 if attempted > 1 else 1)))
    batch_limit_by_sig[sig] = int(next_limit)
    changed = bool(next_limit < previous)
    if changed and events is not None and len(events) < int(max(0, int(event_limit))):
        events.append(
            {
                "signature": str(sig),
                "attempted_batch_size": int(attempted),
                "previous_batch_limit": int(previous),
                "new_batch_limit": int(next_limit),
                "reason": str(reason),
            }
        )
    return int(next_limit), bool(changed)


def _parse_int_csv(spec: str, *, default: Sequence[int]) -> List[int]:
    vals: List[int] = []
    for item in str(spec or "").split(","):
        tok = str(item).strip()
        if not tok:
            continue
        try:
            v = int(tok)
        except Exception:
            continue
        if v > 0:
            vals.append(v)
    if not vals:
        vals = [int(x) for x in default if int(x) > 0]
    vals = sorted(set(vals))
    return vals


def _build_trajectory_paths(
    *,
    out_root: str,
    queue_id: str,
    frame_output_format: str,
    npz_layout: str,
    npz_shard_size: int,
    row_index: int,
) -> Tuple[str, str, str]:
    if str(frame_output_format) != "npz_bundle":
        tdir = os.path.join(out_root, queue_id)
        return tdir, os.path.join(tdir, "trajectory_ligand.npz"), "job_dir"

    layout = str(npz_layout or "flat_shard").strip().lower()
    if layout == "job_dir":
        tdir = os.path.join(out_root, queue_id)
        return tdir, os.path.join(tdir, "trajectory_ligand.npz"), layout
    if layout == "flat_root":
        return out_root, os.path.join(out_root, f"{queue_id}.npz"), layout

    shard_size = int(max(1, int(npz_shard_size)))
    shard_idx = int(max(0, int(row_index)) // shard_size)
    shard_dir = os.path.join(out_root, f"shard_{shard_idx:05d}")
    return shard_dir, os.path.join(shard_dir, f"{queue_id}.npz"), "flat_shard"


def _cached_npz_is_valid(path: str, min_frames: int) -> bool:
    src = str(path).strip()
    if (not src) or (not os.path.isfile(src)):
        return False
    try:
        with np.load(src, allow_pickle=False) as bundle:
            lig = np.asarray(bundle.get("ligand_frames", np.zeros((0, 0, 3), dtype=np.float32)), dtype=np.float32)
        n = 0
        if lig.ndim == 2 and lig.shape[1] == 3:
            n = 1
        elif lig.ndim == 3 and lig.shape[2] == 3:
            n = int(lig.shape[0])
        return int(n) >= int(max(1, int(min_frames)))
    except Exception:
        return False


def _engine_cache_key(
    *,
    n_total: int,
    strategy_type: str,
    box_size_A: float,
    ff_sigma: float,
    ff_eps_solv: float,
    force_backend: str,
    require_rust_hip: bool,
    dt_fs: float,
    friction: float,
    kT: float,
) -> Tuple[Any, ...]:
    return (
        int(n_total),
        str(strategy_type),
        float(box_size_A),
        float(ff_sigma),
        float(ff_eps_solv),
        str(force_backend),
        bool(require_rust_hip),
        float(dt_fs),
        float(friction),
        float(kT),
        str(config.DEVICE),
    )


def _get_engine_resources(
    *,
    n_total: int,
    strategy_type: str,
    box_size_A: float,
    ff_sigma: float,
    ff_eps_solv: float,
    force_backend: str,
    require_rust_hip: bool,
    dt_fs: float,
    friction: float,
    kT: float,
    engine_cache: Optional[Dict[Tuple[Any, ...], Dict[str, Any]]],
    engine_cache_max_entries: int,
) -> Dict[str, Any]:
    key = _engine_cache_key(
        n_total=n_total,
        strategy_type=strategy_type,
        box_size_A=box_size_A,
        ff_sigma=ff_sigma,
        ff_eps_solv=ff_eps_solv,
        force_backend=force_backend,
        require_rust_hip=require_rust_hip,
        dt_fs=dt_fs,
        friction=friction,
        kT=kT,
    )
    cache_enabled = engine_cache is not None and int(engine_cache_max_entries) > 0
    if cache_enabled and key in engine_cache:
        return engine_cache[key]

    device = config.DEVICE
    top = TopologyFactory(
        n_res=int(n_total),
        t_type="protein",
        box_size=[float(box_size_A), float(box_size_A), float(box_size_A)],
        device=device,
        target_name="ligand_htvs",
        strategy_type=str(strategy_type),
    )
    ff = ForceField(
        top,
        params={
            "d_e": 20.0,
            "eps_solv": float(ff_eps_solv),
            "sigma": float(ff_sigma),
            "r0": 4.2,
            "box_size": float(box_size_A),
        },
        force_backend=str(force_backend),
    ).to(device)
    if bool(require_rust_hip) and str(getattr(ff, "physics_backend", "")).lower() != "rust_hip":
        raise RuntimeError("Rust HIP backend required but unavailable for trajectory generation")
    integrator = LangevinIntegrator(
        dt=float(dt_fs),
        friction=float(friction),
        kT=float(kT),
        adaptive_dt=False,
    ).to(device)
    payload = {"top": top, "ff": ff, "integrator": integrator}
    if cache_enabled:
        engine_cache[key] = payload
        max_entries = int(max(1, int(engine_cache_max_entries)))
        while len(engine_cache) > max_entries:
            try:
                oldest_key = next(iter(engine_cache))
            except StopIteration:
                break
            if oldest_key == key:
                break
            engine_cache.pop(oldest_key, None)
    return payload


def _compute_ligand_extra_force(
    c: torch.Tensor,
    n_protein: int,
    pocket: torch.Tensor,
    *,
    pocket_attract: Any,
    protein_repulse: Any,
    bond_k: float,
    bond_ref: Any,
    repulse_cutoff_A: float,
) -> torch.Tensor:
    lig = c[:, n_protein:, :]  # [B, L, 3]
    b, l, _ = lig.shape
    f_lig = torch.zeros_like(lig)
    if l <= 0:
        return f_lig

    if isinstance(pocket_attract, torch.Tensor):
        pocket_attr_t = pocket_attract.to(device=lig.device, dtype=lig.dtype).reshape(b, 1, 1)
    else:
        pocket_attr_t = torch.full((b, 1, 1), float(pocket_attract), dtype=lig.dtype, device=lig.device)
    if isinstance(protein_repulse, torch.Tensor):
        protein_repulse_t = protein_repulse.to(device=lig.device, dtype=lig.dtype).reshape(b, 1, 1)
    else:
        protein_repulse_t = torch.full((b, 1, 1), float(protein_repulse), dtype=lig.dtype, device=lig.device)

    # Pocket attraction toward pocket center.
    center = lig.mean(dim=1, keepdim=True)  # [B,1,3]
    f_lig += -(center - pocket) * pocket_attr_t

    # Soft repulsion from nearby protein beads.
    if n_protein > 0:
        prot = c[:, :n_protein, :]  # [B,P,3]
        diff = lig.unsqueeze(2) - prot.unsqueeze(1)  # [B,L,P,3]
        dist = torch.linalg.norm(diff, dim=-1).clamp_min(1e-6)  # [B,L,P]
        cutoff = float(repulse_cutoff_A)
        mask = dist < cutoff
        if bool(mask.any().item()):
            unit = diff / dist.unsqueeze(-1)
            mag = protein_repulse_t * (cutoff - dist).clamp_min(0.0) / max(cutoff, 1e-6)
            weighted = unit * mag.unsqueeze(-1) * mask.unsqueeze(-1).to(unit.dtype)
            denom = mask.sum(dim=2, keepdim=True).clamp_min(1).to(unit.dtype)
            f_lig += weighted.sum(dim=2) / denom

    # 2-bead harmonic bond.
    if l >= 2:
        vec = lig[:, 0, :] - lig[:, 1, :]
        d = torch.linalg.norm(vec, dim=-1).clamp_min(1e-6)
        if isinstance(bond_ref, torch.Tensor):
            bond_ref_t = bond_ref.to(device=lig.device, dtype=lig.dtype).reshape(-1)
        else:
            bond_ref_t = torch.full((b,), float(bond_ref), dtype=lig.dtype, device=lig.device)
        fb = -float(bond_k) * (d - bond_ref_t).unsqueeze(-1) * (vec / d.unsqueeze(-1))
        f_lig[:, 0, :] += fb
        f_lig[:, 1, :] -= fb

    return f_lig


def _apply_pocket_radius_clip(
    c: torch.Tensor,
    n_protein: int,
    pocket: torch.Tensor,
    max_pocket_radius_A: float,
) -> torch.Tensor:
    lig = c[:, n_protein:, :]
    if lig.numel() <= 0:
        return c
    center = lig.mean(dim=1, keepdim=True)
    delta = center - pocket
    radial = torch.linalg.norm(delta, dim=-1, keepdim=True).clamp_min(1e-6)
    max_r = float(max_pocket_radius_A)
    over = radial > max_r
    if bool(over.any().item()):
        pull = (radial - max_r).clamp_min(0.0) / radial
        shift = delta * pull
        lig = lig - shift
        c = c.clone()
        c[:, n_protein:, :] = lig
    return c


def _simulate_with_engine_batch(
    protein: np.ndarray,
    ligand0_batch: np.ndarray,
    pocket_batch: np.ndarray,
    *,
    strategy_type: str,
    frames: int,
    write_every: int,
    dt_fs: float,
    friction: float,
    kT: float,
    pocket_attract_batch: np.ndarray,
    protein_repulse_batch: np.ndarray,
    bond_k: float,
    repulse_cutoff_A: float,
    max_pocket_radius_A: float,
    force_clip: float,
    box_size_A: float,
    ff_sigma: float,
    ff_eps_solv: float,
    force_backend: str,
    require_rust_hip: bool,
    seed: int,
    affinity_hint_batch: Optional[np.ndarray] = None,
    onsps_norm_batch: Optional[np.ndarray] = None,
    prod_early_stop_enabled: bool = False,
    prod_early_stop_min_frames: int = 0,
    prod_early_stop_window: int = 0,
    prod_early_stop_min_distance_drift_A: float = 0.0,
    prod_early_stop_contact_drift: float = 0.0,
    prod_early_stop_max_mean_min_distance_A: float = 0.0,
    engine_cache: Optional[Dict[Tuple[Any, ...], Dict[str, Any]]] = None,
    engine_cache_max_entries: int = 16,
) -> Tuple[np.ndarray, np.ndarray, str, int, bool, int, Dict[str, Any]]:
    if protein.shape[0] <= 0:
        protein = np.zeros((1, 3), dtype=np.float32)
    lig0 = np.asarray(ligand0_batch, dtype=np.float32)
    if lig0.ndim == 2:
        lig0 = lig0[None, :, :]
    if lig0.ndim != 3 or lig0.shape[1] <= 0 or lig0.shape[2] != 3:
        raise ValueError("ligand0_batch must have shape [B, L, 3]")
    pockets = np.asarray(pocket_batch, dtype=np.float32)
    if pockets.ndim == 1:
        pockets = pockets[None, :]
    if pockets.ndim != 2 or pockets.shape[0] != lig0.shape[0] or pockets.shape[1] != 3:
        raise ValueError("pocket_batch must have shape [B, 3]")
    pocket_attr = np.asarray(pocket_attract_batch, dtype=np.float32).reshape(-1)
    protein_rep = np.asarray(protein_repulse_batch, dtype=np.float32).reshape(-1)
    affinity_hint_arr = np.asarray(affinity_hint_batch if affinity_hint_batch is not None else np.zeros((lig0.shape[0],), dtype=np.float32), dtype=np.float32).reshape(-1)
    onsps_norm_arr = np.asarray(onsps_norm_batch if onsps_norm_batch is not None else np.zeros((lig0.shape[0],), dtype=np.float32), dtype=np.float32).reshape(-1)
    if pocket_attr.shape[0] != lig0.shape[0]:
        raise ValueError("pocket_attract_batch length must match batch size")
    if protein_rep.shape[0] != lig0.shape[0]:
        raise ValueError("protein_repulse_batch length must match batch size")
    if affinity_hint_arr.shape[0] != lig0.shape[0]:
        raise ValueError("affinity_hint_batch length must match batch size")
    if onsps_norm_arr.shape[0] != lig0.shape[0]:
        raise ValueError("onsps_norm_batch length must match batch size")
    torch.manual_seed(int(seed))
    np.random.seed(int(seed) % (2**32 - 1))

    device = config.DEVICE
    protein_t = torch.as_tensor(protein, dtype=torch.float32, device=device)
    ligand_t = torch.as_tensor(lig0, dtype=torch.float32, device=device)
    bsz = int(ligand_t.shape[0])
    pocket_t = torch.as_tensor(pockets, dtype=torch.float32, device=device).view(bsz, 1, 3)
    pocket_attr_t = torch.as_tensor(pocket_attr, dtype=torch.float32, device=device)
    protein_rep_t = torch.as_tensor(protein_rep, dtype=torch.float32, device=device)
    protein_batch = protein_t.unsqueeze(0).expand(bsz, -1, -1)
    c = torch.cat([protein_batch, ligand_t], dim=1)  # [B,N,3]
    v = torch.zeros_like(c)

    n_total = int(c.shape[1])
    n_protein = int(protein_t.shape[0])
    n_lig = int(ligand_t.shape[1])
    if n_lig <= 0:
        raise ValueError("ligand bead count must be > 0")

    engine = _get_engine_resources(
        n_total=n_total,
        strategy_type=str(strategy_type),
        box_size_A=float(box_size_A),
        ff_sigma=float(ff_sigma),
        ff_eps_solv=float(ff_eps_solv),
        force_backend=str(force_backend),
        require_rust_hip=bool(require_rust_hip),
        dt_fs=float(dt_fs),
        friction=float(friction),
        kT=float(kT),
        engine_cache=engine_cache,
        engine_cache_max_entries=int(engine_cache_max_entries),
    )
    ff = engine["ff"]
    integrator = engine["integrator"]

    keep_idx = _selected_frame_indices(int(frames), int(write_every))
    n_keep = int(len(keep_idx))
    protein_frame_capture_meta = {
        "protein_frame_capture_supported": False,
        "protein_frame_capture_mode": "not_simulated_in_engine",
        "protein_frame_capture_reason": "ligand_only_dynamics__protein_coordinates_are_static_in_engine_state",
    }
    if n_lig >= 2:
        bond_ref_t = torch.linalg.norm(ligand_t[:, 0, :] - ligand_t[:, 1, :], dim=-1).clamp_min(1e-6)
    else:
        bond_ref_t = torch.zeros((bsz,), dtype=torch.float32, device=device)
    rollout_noise_bank = None
    if (not bool(getattr(integrator, "adaptive_dt", False))) and float(kT) > 0.0:
        gamma_t = integrator.gamma.to(device=device, dtype=v.dtype)
        dt_t = integrator.dt.to(device=device, dtype=v.dtype)
        kT_half_t = integrator.kT_half.to(device=device, dtype=v.dtype)
        noise_std = torch.sqrt(2.0 * gamma_t * kT_half_t * dt_t)
        rollout_noise_bank = torch.randn(
            (int(max(frames, 1)),) + tuple(v.shape),
            dtype=v.dtype,
            device=device,
        ) * noise_std

    prod_early_stop_active = bool(prod_early_stop_enabled) and int(max(prod_early_stop_min_frames, 0)) > 0 and int(max(prod_early_stop_window, 0)) >= 2
    early_stop_metric_backend_counts: Dict[str, int] = {}
    early_stop_eval_keep_count = 0
    early_stop_eval_row_count = 0
    native_rollout_ok = (
        str(strategy_type) == str(StrategyType.DIRECT_PERTURBATION_NO_MIN)
        and str(getattr(ff, "physics_backend", "")).lower() == "rust_hip"
        and getattr(ff, "rust_backend", None) is not None
        and bool(ff.rust_backend.supports_direct_rollout())
        and (not prod_early_stop_active)
    )
    if native_rollout_ok:
        try:
            selected_gpu = torch.empty((bsz, n_keep, n_lig, 3), dtype=torch.float32, device=device)
            ff.rust_backend.rollout_ligand_direct(
                c,
                v,
                selected_gpu,
                pocket_t.view(bsz, 3),
                pocket_attr_t,
                protein_rep_t,
                bond_ref_t,
                keep_idx,
                {
                    "sigma": float(ff_sigma),
                    "eps_solv": float(ff_eps_solv),
                    "box_size": float(box_size_A),
                    "repulse_cutoff": float(repulse_cutoff_A),
                    "max_pocket_radius": float(max_pocket_radius_A),
                    "force_clip": float(force_clip),
                    "dt": float(dt_fs),
                    "friction": float(friction),
                    "bond_k": float(bond_k),
                },
                n_protein=n_protein,
                n_ligand=n_lig,
                frames=int(max(frames, 1)),
                noise_bank=rollout_noise_bank,
            )
            selected_cpu = selected_gpu.detach().cpu().numpy().astype(np.float32, copy=False)
            return (
                selected_cpu,
                keep_idx,
                "rust_hip_rollout",
                int(max(frames, 1)),
                False,
                int(max(frames, 1)),
                {
                    **protein_frame_capture_meta,
                    "prod_early_stop_metric_backend_counts": {},
                    "prod_early_stop_eval_keep_count": 0,
                    "prod_early_stop_eval_row_count": 0,
                },
            )
        except Exception:
            pass

    keep_pos = 0
    selected_gpu = torch.empty((bsz, n_keep, n_lig, 3), dtype=torch.float32, device=device)
    noise_bank = rollout_noise_bank
    with torch.inference_mode():
        max_frames = int(max(frames, 1))
        apply_clip = float(force_clip) > 0.0
        history_min_distance: List[List[float]] = [[] for _ in range(bsz)]
        history_contact_fraction: List[List[float]] = [[] for _ in range(bsz)]
        early_stop_triggered = False
        early_stop_frame = int(max_frames)
        for step in range(max_frames):
            f_core, _ = ff.compute(c, None)
            f_extra_lig = _compute_ligand_extra_force(
                c,
                n_protein=n_protein,
                pocket=pocket_t,
                pocket_attract=pocket_attr_t,
                protein_repulse=protein_rep_t,
                bond_k=float(bond_k),
                bond_ref=bond_ref_t if n_lig >= 2 else 0.0,
                repulse_cutoff_A=float(repulse_cutoff_A),
            )
            f_total = f_core
            f_total[:, n_protein:, :].add_(f_extra_lig)
            if apply_clip:
                f_total.clamp_(min=-float(force_clip), max=float(force_clip))
            noise_t = noise_bank[step] if isinstance(noise_bank, torch.Tensor) else None
            v, c = integrator.step(c, v, f_total, noise=noise_t)
            c = _apply_pocket_radius_clip(
                c,
                n_protein=n_protein,
                pocket=pocket_t,
                max_pocket_radius_A=float(max_pocket_radius_A),
            )
            if keep_pos < n_keep and step == int(keep_idx[keep_pos]):
                ligand_frame_gpu = c[:, n_protein:, :].to(dtype=torch.float32)
                selected_gpu[:, keep_pos, :, :] = ligand_frame_gpu
                keep_pos += 1
                if prod_early_stop_active:
                    min_distance_arr, contact_fraction_arr, metric_backend = _batched_min_distance_contact_fraction(
                        protein_t,
                        ligand_frame_gpu,
                    )
                    early_stop_metric_backend_counts[str(metric_backend)] = int(
                        early_stop_metric_backend_counts.get(str(metric_backend), 0) + 1
                    )
                    early_stop_eval_keep_count += 1
                    early_stop_eval_row_count += int(bsz)
                    for batch_idx in range(bsz):
                        history_min_distance[batch_idx].append(float(min_distance_arr[batch_idx]))
                        history_contact_fraction[batch_idx].append(float(contact_fraction_arr[batch_idx]))
                        if len(history_min_distance[batch_idx]) > int(prod_early_stop_window):
                            history_min_distance[batch_idx] = history_min_distance[batch_idx][-int(prod_early_stop_window) :]
                            history_contact_fraction[batch_idx] = history_contact_fraction[batch_idx][-int(prod_early_stop_window) :]
                    simulated_frames = int(step + 1)
                    if simulated_frames >= int(prod_early_stop_min_frames):
                        stable_for_all = True
                        for batch_idx in range(bsz):
                            if len(history_min_distance[batch_idx]) < int(prod_early_stop_window):
                                stable_for_all = False
                                break
                            if not _prod_window_is_stable(
                                min_distance_history=history_min_distance[batch_idx],
                                contact_fraction_history=history_contact_fraction[batch_idx],
                                min_distance_drift_A=float(prod_early_stop_min_distance_drift_A),
                                contact_fraction_drift=float(prod_early_stop_contact_drift),
                                max_mean_min_distance_A=float(prod_early_stop_max_mean_min_distance_A),
                            ):
                                stable_for_all = False
                                break
                        if stable_for_all:
                            early_stop_triggered = True
                            early_stop_frame = int(simulated_frames)
                            break
    selected_cpu = selected_gpu[:, :keep_pos, :, :].detach().cpu().numpy().astype(np.float32, copy=False)
    effective_keep_idx = keep_idx[:keep_pos]
    simulated_frames_final = int(early_stop_frame if prod_early_stop_active and early_stop_triggered else max(frames, 1))
    return (
        selected_cpu,
        effective_keep_idx,
        str(getattr(ff, "physics_backend", "unknown")),
        simulated_frames_final,
        bool(early_stop_triggered),
        int(early_stop_frame),
        {
            **protein_frame_capture_meta,
            "prod_early_stop_metric_backend_counts": early_stop_metric_backend_counts,
            "prod_early_stop_eval_keep_count": int(early_stop_eval_keep_count),
            "prod_early_stop_eval_row_count": int(early_stop_eval_row_count),
        },
    )


def run_batch(args: argparse.Namespace) -> Dict[str, Any]:
    queue_csv = str(args.queue_csv).strip()
    if (not queue_csv) or (not os.path.exists(queue_csv)):
        raise FileNotFoundError(f"queue csv not found: {queue_csv}")
    df = pd.read_csv(queue_csv)
    if df.empty:
        raise ValueError(f"queue csv is empty: {queue_csv}")

    max_jobs = int(args.max_jobs)
    if max_jobs > 0:
        df = df.head(max_jobs).copy()

    forced_adress_targets = _parse_csv_set(str(args.dynamic_adress_force_targets))
    if bool(getattr(args, "group_by_signature_sort", True)):
        native_col = str(getattr(args, "native_path_col", "native_pdb_path"))
        sort_df = df.copy()
        if native_col not in sort_df.columns:
            sort_df[native_col] = ""
        sort_df["_batch_affinity_hint"] = sort_df.apply(_ligand_affinity_hint, axis=1)
        sort_df["_batch_strategy_bucket"] = sort_df.apply(
            lambda row: _batch_strategy_bucket_from_row(
                row.to_dict(),
                mode=str(args.strategy_mode),
                dynamic_adress_min_affinity=float(args.dynamic_adress_min_affinity),
                dynamic_adress_min_ligand_mw=float(args.dynamic_adress_min_ligand_mw),
                dynamic_adress_force_targets=forced_adress_targets,
            ),
            axis=1,
        )
        sort_cols = ["target", native_col, "_batch_strategy_bucket", "ligand_mw", "_batch_affinity_hint", "queue_id"]
        asc = [True, True, False, False, False, True]
        df = (
            sort_df.sort_values(sort_cols, ascending=asc, kind="stable")
            .drop(columns=["_batch_affinity_hint", "_batch_strategy_bucket"], errors="ignore")
            .reset_index(drop=True)
        )

    out_root = str(args.out_root).strip() or f"runs/ligand_traj_engine_{dt.date.today().isoformat()}"
    _ensure_dir(out_root)
    out_progress_json = str(args.out_progress_json).strip()
    if not out_progress_json:
        out_progress_json = f"{out_root}_progress.json"
    progress_every_jobs = int(max(1, int(args.progress_every_jobs)))
    frame_output_format = str(args.frame_output_format).strip().lower()
    if frame_output_format not in {"pdb_files", "npz_bundle", "manifest_only"}:
        raise ValueError("--frame-output-format must be pdb_files|npz_bundle|manifest_only")

    total_rows = int(len(df))
    processed_rows = 0
    ok_rows = 0
    failed_rows = 0
    protein_cache: Dict[Tuple[str, str], np.ndarray] = {}
    protein_atom_template_cache: Dict[Tuple[str, str], Dict[str, Any]] = {}
    engine_cache: Dict[Tuple[Any, ...], Dict[str, Any]] = {}
    stride = int(max(1, int(args.write_every)))
    expected_frames_written, expected_last_frame_idx = _expected_written_frames(int(args.frames), stride)
    prod_mode = bool(getattr(args, "prod_mode", False))
    prod_adaptive_frame_budget = bool(getattr(args, "prod_adaptive_frame_budget", False))
    prod_frame_budget_tiers = _parse_prod_frame_budget_tiers(str(getattr(args, "prod_frame_budget_tiers", "")))
    prod_min_frames = int(max(1, int(getattr(args, "prod_min_frames", max(1, min(int(args.frames), 60))))))
    prod_early_stop = bool(getattr(args, "prod_early_stop", False))
    prod_early_stop_min_frames = int(max(1, int(getattr(args, "prod_early_stop_min_frames", prod_min_frames))))
    prod_early_stop_window = int(max(2, int(getattr(args, "prod_early_stop_window", 12))))
    prod_early_stop_min_distance_drift_A = float(max(0.0, float(getattr(args, "prod_early_stop_min_distance_drift_A", 0.12))))
    prod_early_stop_contact_drift = float(max(0.0, float(getattr(args, "prod_early_stop_contact_drift", 0.015))))
    prod_early_stop_max_mean_min_distance_A = float(max(0.0, float(getattr(args, "prod_early_stop_max_mean_min_distance_A", 6.0))))
    job_batch_derate_count = 0
    job_batch_derate_events: List[Dict[str, Any]] = []
    batch_limit_by_sig: Dict[Tuple[Any, ...], int] = {}
    writer_mode = "sync"
    writer_futures: List[cf.Future] = []
    writer_inflight = 0
    writer_pending_peak = 0
    writer_backpressure_count = 0
    prod_artifact_light = _resolve_prod_artifact_light_settings(
        prod_mode=bool(prod_mode),
        prod_light_artifacts=bool(getattr(args, "prod_light_artifacts", False)),
        manifest_chunk_size=int(getattr(args, "manifest_chunk_size", 1000)),
        progress_every_jobs=int(progress_every_jobs),
        prod_light_progress_every_jobs=int(getattr(args, "prod_light_progress_every_jobs", 250)),
    )
    prod_light_artifacts = bool(prod_artifact_light["enabled"])
    progress_every_jobs = int(prod_artifact_light["progress_every_jobs"])

    def _write_progress(
        *,
        status: str,
        current_queue_id: str = "",
        current_target: str = "",
        current_ligand_id: str = "",
        last_error: str = "",
    ) -> None:
        ratio = float(processed_rows / total_rows) if total_rows > 0 else 0.0
        payload = {
            "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
            "status": str(status),
            "queue_rows_total": int(total_rows),
            "processed_rows": int(processed_rows),
            "ok_rows": int(ok_rows),
            "failed_rows": int(failed_rows),
            "progress_ratio": float(max(0.0, min(1.0, ratio))),
            "current_queue_id": str(current_queue_id),
            "current_target": str(current_target),
            "current_ligand_id": str(current_ligand_id),
            "last_error": str(last_error),
            "job_batch_size_resolved_count": int(len(batch_limit_by_sig)),
            "job_batch_derate_count": int(job_batch_derate_count),
            "writer_pending_peak": int(writer_pending_peak),
            "writer_backpressure_count": int(writer_backpressure_count),
            "prod_early_stop_eval_keep_count": int(prod_early_stop_eval_keep_count),
            "prod_early_stop_eval_row_count": int(prod_early_stop_eval_row_count),
            "prod_early_stop_metric_backend_counts": prod_early_stop_metric_backend_counts,
        }
        _ensure_dir(os.path.dirname(out_progress_json) or ".")
        with open(out_progress_json, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

    rows: List[Dict[str, Any]] = []
    rows_flushed = 0
    failed = 0
    ok_backend_counts: Dict[str, int] = {}
    strategy_requested_counts: Dict[str, int] = {}
    strategy_final_counts: Dict[str, int] = {}
    strategy_fallback_count = 0
    prod_frame_budget_applied_count = 0
    prod_early_stop_batch_count = 0
    prod_early_stop_row_count = 0
    prod_early_stop_eval_keep_count = 0
    prod_early_stop_eval_row_count = 0
    prod_early_stop_metric_backend_counts: Dict[str, int] = {}
    aborted_early = False
    abort_reason = ""
    _write_progress(status="running")
    batch_job_size = int(getattr(args, "job_batch_size", 0))
    batch_autotune_candidates = _parse_int_csv(
        str(getattr(args, "job_batch_autotune_candidates", "1,2,4,8")),
        default=(1, 2, 4, 8),
    )
    batch_autotune_prefill = int(max(batch_autotune_candidates)) if batch_autotune_candidates else 1
    batch_autotune_frames = int(max(4, int(getattr(args, "job_batch_autotune_frames", 12))))
    batch_autotune_rows: List[Dict[str, Any]] = []
    writer_workers = int(max(0, int(getattr(args, "writer_workers", 0))))
    writer_max_pending = int(max(1, int(getattr(args, "writer_max_pending", 32))))
    writer_mode = str(getattr(args, "writer_mode", "thread")).strip().lower()
    if writer_mode not in {"sync", "thread", "process"}:
        writer_mode = "thread"
    if writer_workers <= 0:
        writer_mode = "sync"
    writer_pool: Optional[cf.Executor] = None
    writer_task_queue = None
    writer_result_queue = None
    writer_processes: List[mp.Process] = []
    manifest_chunk_size = int(prod_artifact_light["manifest_chunk_size"])
    out_manifest_csv = str(args.out_manifest_csv).strip() or f"{out_root}_manifest.csv"
    manifest_chunks_dir = ""
    if manifest_chunk_size > 0:
        manifest_chunks_dir = f"{os.path.splitext(out_manifest_csv)[0]}_chunks"
        _ensure_dir(manifest_chunks_dir)
    if writer_mode == "thread" and writer_workers > 0:
        writer_pool = cf.ThreadPoolExecutor(max_workers=writer_workers, thread_name_prefix="traj_writer")
    elif writer_mode == "process" and writer_workers > 0:
        ctx = mp.get_context("spawn")
        writer_task_queue = ctx.JoinableQueue(maxsize=writer_max_pending)
        writer_result_queue = ctx.Queue()
        for idx in range(writer_workers):
            proc = ctx.Process(
                target=_writer_process_main,
                args=(writer_task_queue, writer_result_queue),
                name=f"traj_writer_proc_{idx}",
                daemon=True,
            )
            proc.start()
            writer_processes.append(proc)

    pending_batch: List[Dict[str, Any]] = []
    pending_sig: Optional[Tuple[Any, ...]] = None

    def _flush_manifest_chunk(force: bool = False) -> None:
        nonlocal rows_flushed
        pending = int(len(rows) - rows_flushed)
        if pending <= 0:
            return
        if (not force) and pending < manifest_chunk_size:
            return
        if manifest_chunks_dir:
            chunk = rows[rows_flushed:]
            chunk_idx = int(rows_flushed // max(1, manifest_chunk_size))
            chunk_csv = os.path.join(manifest_chunks_dir, f"chunk_{chunk_idx:05d}.csv")
            pd.DataFrame(chunk).to_csv(chunk_csv, index=False)
        rows_flushed = int(len(rows))

    def _resolve_batch_limit(sig: Tuple[Any, ...], batch: List[Dict[str, Any]]) -> int:
        if sig in batch_limit_by_sig:
            return int(batch_limit_by_sig[sig])
        if int(batch_job_size) > 0:
            resolved = int(max(1, batch_job_size))
            batch_limit_by_sig[sig] = resolved
            return resolved
        if len(batch) <= 1:
            return 1
        sample = batch[: min(len(batch), batch_autotune_prefill)]
        best_limit = 1
        best_rows_per_sec = -1.0
        for cand in batch_autotune_candidates:
            if cand > len(sample):
                continue
            probe = sample[:cand]
            lig_batch = np.stack([x["ligand0"] for x in probe], axis=0).astype(np.float32, copy=False)
            pocket_batch = np.stack([x["pocket"] for x in probe], axis=0).astype(np.float32, copy=False)
            pocket_attr_batch = np.asarray([x["k_attr"] for x in probe], dtype=np.float32)
            protein_rep_batch = np.asarray([x["k_rep"] for x in probe], dtype=np.float32)
            t0_probe = time.perf_counter()
            try:
                _simulate_with_engine_batch(
                    protein=probe[0]["protein"],
                    ligand0_batch=lig_batch,
                    pocket_batch=pocket_batch,
                    strategy_type=str(probe[0]["strategy_requested"]),
                    frames=min(int(args.frames), batch_autotune_frames),
                    write_every=max(1, int(args.write_every)),
                    dt_fs=float(args.dt_fs),
                    friction=float(args.friction),
                    kT=float(args.kT),
                    pocket_attract_batch=pocket_attr_batch,
                    protein_repulse_batch=protein_rep_batch,
                    affinity_hint_batch=np.asarray([x["affinity"] for x in probe], dtype=np.float32),
                    onsps_norm_batch=np.asarray([x.get("onsps_norm", 0.0) for x in probe], dtype=np.float32),
                    bond_k=float(args.bond_k),
                    repulse_cutoff_A=float(args.repulse_cutoff_A),
                    max_pocket_radius_A=float(args.max_pocket_radius_A),
                    force_clip=float(args.force_clip),
                    box_size_A=float(args.box_size_A),
                    ff_sigma=float(args.ff_sigma),
                    ff_eps_solv=float(args.ff_eps_solv),
                    force_backend=str(args.force_backend),
                    require_rust_hip=bool(args.require_rust_hip),
                    seed=int(min(x["seed_i"] for x in probe)),
                    prod_early_stop_enabled=False,
                    engine_cache=engine_cache,
                    engine_cache_max_entries=int(args.engine_cache_max_entries),
                )
                elapsed_probe = float(max(1e-8, time.perf_counter() - t0_probe))
                rows_per_sec = float(cand / elapsed_probe)
                batch_autotune_rows.append(
                    {
                        "signature": str(sig),
                        "candidate_batch_size": int(cand),
                        "elapsed_sec": float(elapsed_probe),
                        "rows_per_sec": float(rows_per_sec),
                    }
                )
                if rows_per_sec > best_rows_per_sec:
                    best_rows_per_sec = rows_per_sec
                    best_limit = int(cand)
            except Exception as exc:
                batch_autotune_rows.append(
                    {
                        "signature": str(sig),
                        "candidate_batch_size": int(cand),
                        "elapsed_sec": None,
                        "rows_per_sec": None,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
        batch_limit_by_sig[sig] = int(max(1, best_limit))
        return int(batch_limit_by_sig[sig])

    def _record_progress(
        *,
        queue_id: str = "",
        target: str = "",
        ligand_id: str = "",
        last_error: str = "",
        status: str = "running",
    ) -> None:
        if (processed_rows % progress_every_jobs) == 0 or status != "running":
            _write_progress(
                status=status,
                current_queue_id=queue_id,
                current_target=target,
                current_ligand_id=ligand_id,
                last_error=last_error,
            )

    def _enqueue_write(entry: Dict[str, Any], ligand_frames_np: np.ndarray, frame_indices_np: np.ndarray) -> None:
        nonlocal writer_inflight, writer_pending_peak, writer_backpressure_count
        if writer_mode == "sync":
            _write_trajectory_artifact(
                protein_ca=entry["protein"],
                ligand_frames=ligand_frames_np,
                frame_indices=frame_indices_np,
                frame_output_format=frame_output_format,
                npz_path=entry["npz_path"],
                tdir=entry["tdir"],
                npz_compression=str(args.npz_compression),
                protein_atom_template=entry.get("protein_atom_template"),
            )
            return
        if writer_mode == "process":
            assert writer_task_queue is not None
            assert writer_result_queue is not None
            writer_task_queue.put(
                {
                    "queue_id": entry["queue_id"],
                    "target": entry["target"],
                    "ligand_id": entry["ligand_id"],
                    "protein_ca": entry["protein"],
                    "ligand_frames": ligand_frames_np,
                    "frame_indices": frame_indices_np,
                    "frame_output_format": frame_output_format,
                    "npz_path": entry["npz_path"],
                    "tdir": entry["tdir"],
                    "npz_compression": str(args.npz_compression),
                    "protein_atom_template": entry.get("protein_atom_template"),
                    "npz_extra_arrays": entry.get("npz_extra_arrays"),
                    "protein_atom_template_source_type": entry.get("protein_atom_template_source_type", ""),
                }
            )
            writer_inflight += 1
            writer_pending_peak = max(writer_pending_peak, int(writer_inflight))
            if writer_inflight >= writer_max_pending:
                writer_backpressure_count += 1
                drained = _drain_writer_process_results(
                    writer_result_queue,
                    expected_min=max(1, writer_inflight // 2),
                )
                writer_inflight = max(0, writer_inflight - int(drained))
            return
        writer_futures.append(
            writer_pool.submit(
                _write_trajectory_artifact,
                protein_ca=entry["protein"],
                ligand_frames=ligand_frames_np,
                frame_indices=frame_indices_np,
                frame_output_format=frame_output_format,
                npz_path=entry["npz_path"],
                tdir=entry["tdir"],
                npz_compression=str(args.npz_compression),
                protein_atom_template=entry.get("protein_atom_template"),
                npz_extra_arrays=entry.get("npz_extra_arrays"),
            )
        )
        writer_pending_peak = max(writer_pending_peak, int(len(writer_futures)))
        if len(writer_futures) > writer_max_pending:
            writer_backpressure_count += 1
        _drain_writer_futures(writer_futures, keep_max_pending=writer_max_pending)

    def _flush_pending_chunks() -> None:
        nonlocal pending_batch, pending_sig
        if not pending_batch or pending_sig is None:
            return
        limit = _resolve_batch_limit(pending_sig, pending_batch)
        while pending_batch and len(pending_batch) >= limit and not bool(aborted_early):
            chunk = pending_batch[:limit]
            pending_batch = pending_batch[limit:]
            _flush_batch(chunk)
        if not pending_batch:
            pending_sig = None

    def _append_ok_cached(entry: Dict[str, Any]) -> None:
        nonlocal processed_rows, ok_rows
        rows.append(
            {
                "queue_id": entry["queue_id"],
                "target": entry["target"],
                "ligand_id": entry["ligand_id"],
                "status": "ok_cached",
                "frames_written": int(entry.get("expected_frames_written", expected_frames_written)),
                "trajectory_dir": entry["tdir"],
                "trajectory_npz": entry["npz_path"] if bool(entry["cached_is_npz"]) else "",
                "frame_output_format": "npz_bundle" if bool(entry["cached_is_npz"]) else "pdb_files",
                "npz_layout": str(entry["npz_layout_effective"]),
                "backend": "cached",
                "affinity_hint": float(entry["affinity"]),
                "k_attr": float(entry["k_attr"]),
                "protein_repulse": float(entry["k_rep"]),
                "seed": int(entry["seed_i"]),
                "strategy_requested": str(entry["strategy_requested"]),
                "strategy_final": str(entry["strategy_requested"]),
                "strategy_reason": f"{entry['strategy_reason']}+resume_existing",
                "strategy_fallback_used": False,
                "adress_radius_A": float(entry["adress_radius_A"]),
                "estimated_atom_ratio": float(entry["estimated_atom_ratio"]),
                "protein_atom_frames_available": False,
                "protein_atom_template_ready": bool(entry.get("protein_atom_template_ready", False)),
                "protein_atom_template_source_type": str(entry.get("protein_atom_template_source_type", "")),
                "protein_atom_template_source_path": str(entry.get("protein_atom_template_source_path", "")),
                "protein_atom_template_warning": str(entry.get("protein_atom_template_warning", "")),
                "protein_atom_template_count": int(entry.get("protein_atom_template_count", 0)),
                "protein_atom_schema_version": int(entry.get("protein_atom_schema_version", 0)),
                "protein_atom_motion_mode": "unknown_resume_existing" if bool(entry.get("cached_is_npz", False)) else "not_available",
                "protein_frame_capture_supported": False,
                "protein_frame_capture_mode": "resume_existing_not_revalidated",
                "protein_frame_capture_reason": "cached_artifact_reused__true_protein_frame_capture_not_revalidated",
                "protein_res_count": int(entry["protein"].shape[0]),
                "elapsed_sec": 0.0,
                "frames_requested": int(max(int(args.frames), 1)),
                "frames_effective_cap": int(entry.get("effective_frames_requested", max(int(args.frames), 1))),
                "prod_frame_budget_score": float(entry.get("prod_frame_budget_score", 0.0)),
                "prod_frame_budget_applied": bool(entry.get("prod_frame_budget_applied", False)),
                "prod_early_stop_enabled": bool(prod_mode and prod_early_stop),
                "prod_early_stop_triggered": False,
                "prod_early_stop_frame": int(entry.get("effective_frames_requested", max(int(args.frames), 1))),
                "sim_frames_count": int(entry.get("effective_frames_requested", max(int(args.frames), 1))),
                "sim_fps": 0.0,
                "error": "",
                "inline_aux_available": False,
            }
        )
        ok_rows += 1
        processed_rows += 1
        _flush_manifest_chunk(force=False)
        _record_progress(queue_id=entry["queue_id"], target=entry["target"], ligand_id=entry["ligand_id"])

    def _append_failed(entry: Dict[str, Any], *, exc: Exception, elapsed_sec: float, strategy_final: str, strategy_fallback_used: bool) -> None:
        nonlocal processed_rows, failed_rows, failed, aborted_early, abort_reason
        failed += 1
        failed_rows += 1
        rows.append(
            {
                "queue_id": entry["queue_id"],
                "target": entry["target"],
                "ligand_id": entry["ligand_id"],
                "status": "failed_runtime",
                "frames_written": 0,
                "trajectory_dir": "",
                "trajectory_npz": "",
                "frame_output_format": frame_output_format,
                "npz_layout": str(entry["npz_layout_effective"]),
                "backend": "unknown",
                "strategy_requested": str(entry["strategy_requested"]),
                "strategy_final": str(strategy_final),
                "strategy_reason": str(entry["strategy_reason"]),
                "strategy_fallback_used": bool(strategy_fallback_used),
                "adress_radius_A": float(entry["adress_radius_A"]),
                "estimated_atom_ratio": float(entry["estimated_atom_ratio"]),
                "protein_atom_template_ready": bool(entry.get("protein_atom_template_ready", False)),
                "protein_atom_template_source_type": str(entry.get("protein_atom_template_source_type", "")),
                "protein_atom_template_source_path": str(entry.get("protein_atom_template_source_path", "")),
                "protein_atom_template_warning": str(entry.get("protein_atom_template_warning", "")),
                "protein_atom_frames_available": bool(entry.get("protein_atom_template_count", 0) > 0 and frame_output_format == "npz_bundle"),
                "protein_atom_template_count": int(entry.get("protein_atom_template_count", 0)),
                "protein_atom_schema_version": int(entry.get("protein_atom_schema_version", 0)),
                "protein_atom_motion_mode": "static_native_template_repeated"
                if int(entry.get("protein_atom_template_count", 0)) > 0 and frame_output_format == "npz_bundle"
                else "not_available",
                "protein_frame_capture_supported": False,
                "protein_frame_capture_mode": "simulation_failed_before_true_protein_frame_capture",
                "protein_frame_capture_reason": "simulation_failed__engine_only_integrates_ligand_coordinates",
                "protein_res_count": int(entry["protein"].shape[0]),
                "elapsed_sec": float(elapsed_sec),
                "frames_requested": int(max(int(args.frames), 1)),
                "frames_effective_cap": int(entry.get("effective_frames_requested", max(int(args.frames), 1))),
                "prod_frame_budget_score": float(entry.get("prod_frame_budget_score", 0.0)),
                "prod_frame_budget_applied": bool(entry.get("prod_frame_budget_applied", False)),
                "prod_early_stop_enabled": bool(prod_mode and prod_early_stop),
                "prod_early_stop_triggered": False,
                "prod_early_stop_frame": 0,
                "sim_frames_count": 0,
                "sim_fps": 0.0,
                "error": f"{type(exc).__name__}: {exc}",
                "inline_aux_available": False,
            }
        )
        processed_rows += 1
        _flush_manifest_chunk(force=False)
        if bool(args.abort_on_runtime_error):
            aborted_early = True
            abort_reason = f"{type(exc).__name__}: {exc}"
            _record_progress(
                queue_id=entry["queue_id"],
                target=entry["target"],
                ligand_id=entry["ligand_id"],
                last_error=abort_reason,
                status="aborted",
            )
        else:
            _record_progress(
                queue_id=entry["queue_id"],
                target=entry["target"],
                ligand_id=entry["ligand_id"],
                last_error=f"{type(exc).__name__}: {exc}",
            )

    def _flush_batch(batch: List[Dict[str, Any]], *, strategy_override: Optional[str] = None, strategy_fallback_used: bool = False) -> None:
        nonlocal processed_rows, ok_rows, failed_rows, failed, aborted_early, abort_reason, strategy_fallback_count
        nonlocal prod_early_stop_batch_count, prod_early_stop_row_count, job_batch_derate_count
        nonlocal prod_early_stop_eval_keep_count, prod_early_stop_eval_row_count, prod_early_stop_metric_backend_counts
        if not batch or bool(aborted_early):
            return
        strategy_final = str(strategy_override or batch[0]["strategy_requested"])
        batch_sig = batch[0].get("batch_sig")
        effective_frames_requested = int(batch[0].get("effective_frames_requested", max(int(args.frames), 1)))
        lig_batch = np.stack([x["ligand0"] for x in batch], axis=0).astype(np.float32, copy=False)
        pocket_batch = np.stack([x["pocket"] for x in batch], axis=0).astype(np.float32, copy=False)
        pocket_attr_batch = np.asarray([x["k_attr"] for x in batch], dtype=np.float32)
        protein_rep_batch = np.asarray([x["k_rep"] for x in batch], dtype=np.float32)
        affinity_hint_batch = np.asarray([x["affinity"] for x in batch], dtype=np.float32)
        onsps_norm_batch = np.asarray([x.get("onsps_norm", 0.0) for x in batch], dtype=np.float32)
        batch_seed = int(min(x["seed_i"] for x in batch))
        t0 = time.perf_counter()
        try:
            selected_cpu, frame_indices_np, backend, simulated_frames_count, early_stop_triggered, early_stop_frame, sim_telemetry = _simulate_with_engine_batch(
                protein=batch[0]["protein"],
                ligand0_batch=lig_batch,
                pocket_batch=pocket_batch,
                strategy_type=strategy_final,
                frames=int(effective_frames_requested),
                write_every=int(args.write_every),
                dt_fs=float(args.dt_fs),
                friction=float(args.friction),
                kT=float(args.kT),
                pocket_attract_batch=pocket_attr_batch,
                protein_repulse_batch=protein_rep_batch,
                affinity_hint_batch=affinity_hint_batch,
                onsps_norm_batch=onsps_norm_batch,
                bond_k=float(args.bond_k),
                repulse_cutoff_A=float(args.repulse_cutoff_A),
                max_pocket_radius_A=float(args.max_pocket_radius_A),
                force_clip=float(args.force_clip),
                box_size_A=float(args.box_size_A),
                ff_sigma=float(args.ff_sigma),
                ff_eps_solv=float(args.ff_eps_solv),
                force_backend=str(args.force_backend),
                require_rust_hip=bool(args.require_rust_hip),
                seed=batch_seed,
                prod_early_stop_enabled=bool(prod_mode and prod_early_stop),
                prod_early_stop_min_frames=int(prod_early_stop_min_frames),
                prod_early_stop_window=int(prod_early_stop_window),
                prod_early_stop_min_distance_drift_A=float(prod_early_stop_min_distance_drift_A),
                prod_early_stop_contact_drift=float(prod_early_stop_contact_drift),
                prod_early_stop_max_mean_min_distance_A=float(prod_early_stop_max_mean_min_distance_A),
                engine_cache=engine_cache,
                engine_cache_max_entries=int(args.engine_cache_max_entries),
            )
            prod_early_stop_eval_keep_count += int(sim_telemetry.get("prod_early_stop_eval_keep_count", 0))
            prod_early_stop_eval_row_count += int(sim_telemetry.get("prod_early_stop_eval_row_count", 0))
            for backend_key, backend_count in dict(sim_telemetry.get("prod_early_stop_metric_backend_counts", {})).items():
                prod_early_stop_metric_backend_counts[str(backend_key)] = int(
                    prod_early_stop_metric_backend_counts.get(str(backend_key), 0) + int(backend_count)
                )
        except Exception as sim_exc:
            if (
                bool(args.dynamic_core_fallback_on_oom)
                and str(strategy_final) == str(StrategyType.ADRESS)
                and (not bool(strategy_fallback_used))
                and _should_retry_core_after_error(sim_exc)
            ):
                strategy_fallback_count += int(len(batch))
                _flush_batch(
                    batch,
                    strategy_override=str(StrategyType.DIRECT_PERTURBATION_NO_MIN),
                    strategy_fallback_used=True,
                )
                return
            if len(batch) > 1:
                if isinstance(batch_sig, tuple):
                    _, changed = _register_batch_limit_derate(
                        batch_limit_by_sig=batch_limit_by_sig,
                        sig=batch_sig,
                        attempted_size=len(batch),
                        reason=f"runtime_error:{type(sim_exc).__name__}",
                        events=job_batch_derate_events,
                    )
                    if bool(changed):
                        job_batch_derate_count += 1
                mid = int(len(batch) // 2)
                _flush_batch(batch[:mid], strategy_override=strategy_final, strategy_fallback_used=strategy_fallback_used)
                _flush_batch(batch[mid:], strategy_override=strategy_final, strategy_fallback_used=strategy_fallback_used)
                return
            _append_failed(
                batch[0],
                exc=sim_exc,
                elapsed_sec=float(max(0.0, time.perf_counter() - float(t0))),
                strategy_final=str(strategy_final),
                strategy_fallback_used=bool(strategy_fallback_used),
            )
            return

        elapsed_sec = float(max(0.0, time.perf_counter() - float(t0)))
        backend_name = str(backend).strip().lower()
        if bool(args.abort_on_cpu_backend) and (not backend_name.startswith("rust_hip")):
            cpu_exc = RuntimeError(f"cpu_fallback_detected backend={backend}")
            if len(batch) > 1:
                if isinstance(batch_sig, tuple):
                    _, changed = _register_batch_limit_derate(
                        batch_limit_by_sig=batch_limit_by_sig,
                        sig=batch_sig,
                        attempted_size=len(batch),
                        reason="cpu_backend_abort",
                        events=job_batch_derate_events,
                    )
                    if bool(changed):
                        job_batch_derate_count += 1
                mid = int(len(batch) // 2)
                _flush_batch(batch[:mid], strategy_override=strategy_final, strategy_fallback_used=strategy_fallback_used)
                _flush_batch(batch[mid:], strategy_override=strategy_final, strategy_fallback_used=strategy_fallback_used)
                return
            _append_failed(
                batch[0],
                exc=cpu_exc,
                elapsed_sec=elapsed_sec,
                strategy_final=str(strategy_final),
                strategy_fallback_used=bool(strategy_fallback_used),
            )
            return

        ok_backend_counts[str(backend)] = int(ok_backend_counts.get(str(backend), 0) + len(batch))
        strategy_final_counts[str(strategy_final)] = int(strategy_final_counts.get(str(strategy_final), 0) + len(batch))
        sim_frames_count = int(max(int(simulated_frames_count), 1))
        sim_fps = float(sim_frames_count / max(elapsed_sec, 1e-8))
        written = int(len(frame_indices_np))
        if bool(early_stop_triggered):
            prod_early_stop_batch_count += 1
            prod_early_stop_row_count += int(len(batch))
        for idx, entry in enumerate(batch):
            _enqueue_write(entry, selected_cpu[idx], frame_indices_np)
            inline_aux = _compute_inline_aux_features(
                protein_ca=entry["protein"],
                ligand_frames=selected_cpu[idx],
                frame_indices=frame_indices_np,
                affinity_hint=float(entry["affinity"]),
                onsps_norm=float(entry.get("onsps_norm", 0.0)),
                sim_fps=float(sim_fps),
            )
            rows.append(
                {
                    "protein_frame_capture_supported": bool(sim_telemetry.get("protein_frame_capture_supported", False)),
                    "protein_frame_capture_mode": str(sim_telemetry.get("protein_frame_capture_mode", "not_simulated_in_engine")),
                    "protein_frame_capture_reason": str(
                        sim_telemetry.get(
                            "protein_frame_capture_reason",
                            "ligand_only_dynamics__protein_coordinates_are_static_in_engine_state",
                        )
                    ),
                    "queue_id": entry["queue_id"],
                    "target": entry["target"],
                    "ligand_id": entry["ligand_id"],
                    "status": "ok",
                    "frames_written": int(written),
                    "trajectory_dir": entry["tdir"],
                    "trajectory_npz": entry["npz_path"] if frame_output_format == "npz_bundle" else "",
                    "frame_output_format": frame_output_format,
                    "npz_layout": str(entry["npz_layout_effective"]),
                    "backend": str(backend),
                    "affinity_hint": float(entry["affinity"]),
                    "k_attr": float(entry["k_attr"]),
                    "protein_repulse": float(entry["k_rep"]),
                    "seed": int(entry["seed_i"]),
                    "strategy_requested": str(entry["strategy_requested"]),
                    "strategy_final": str(strategy_final),
                    "strategy_reason": str(entry["strategy_reason"]),
                    "strategy_fallback_used": bool(strategy_fallback_used),
                    "adress_radius_A": float(entry["adress_radius_A"]),
                    "estimated_atom_ratio": float(entry["estimated_atom_ratio"]),
                    "protein_atom_template_ready": bool(entry.get("protein_atom_template_ready", False)),
                    "protein_atom_template_source_type": str(entry.get("protein_atom_template_source_type", "")),
                    "protein_atom_template_source_path": str(entry.get("protein_atom_template_source_path", "")),
                    "protein_atom_template_warning": str(entry.get("protein_atom_template_warning", "")),
                    "protein_atom_frames_available": bool(entry.get("protein_atom_template_count", 0) > 0 and frame_output_format == "npz_bundle"),
                    "protein_atom_template_count": int(entry.get("protein_atom_template_count", 0)),
                    "protein_atom_schema_version": int(entry.get("protein_atom_schema_version", 0)),
                    "protein_atom_motion_mode": (
                        "engine_true_protein_frames"
                        if bool(sim_telemetry.get("protein_frame_capture_supported", False))
                        else (
                            "static_native_template_repeated"
                            if int(entry.get("protein_atom_template_count", 0)) > 0 and frame_output_format == "npz_bundle"
                            else "not_available"
                        )
                    ),
                    "protein_res_count": int(entry["protein"].shape[0]),
                    "elapsed_sec": float(elapsed_sec),
                    "frames_requested": int(max(int(args.frames), 1)),
                    "frames_effective_cap": int(entry.get("effective_frames_requested", sim_frames_count)),
                    "prod_frame_budget_score": float(entry.get("prod_frame_budget_score", 0.0)),
                    "prod_frame_budget_applied": bool(entry.get("prod_frame_budget_applied", False)),
                    "prod_early_stop_enabled": bool(prod_mode and prod_early_stop),
                    "prod_early_stop_triggered": bool(early_stop_triggered),
                    "prod_early_stop_frame": int(early_stop_frame if bool(early_stop_triggered) else sim_frames_count),
                    "sim_frames_count": int(sim_frames_count),
                    "sim_fps": float(sim_fps),
                    "error": "",
                    **inline_aux,
                }
            )
            ok_rows += 1
            processed_rows += 1
            _flush_manifest_chunk(force=False)
            _record_progress(queue_id=entry["queue_id"], target=entry["target"], ligand_id=entry["ligand_id"])

    try:
        for row_index, row in enumerate(df.to_dict(orient="records")):
            if bool(aborted_early):
                break
            queue_id = str(row.get("queue_id", "")).strip()
            if not queue_id:
                queue_id = f"{_slug(str(row.get('target','target')))}__rep{_safe_int(row.get('replica_idx', 0)):04d}"
            target = str(row.get("target", "unknown")).strip()
            ligand_id = str(row.get("ligand_id", "ligand")).strip()
            native_path = str(row.get(str(args.native_path_col), "")).strip()
            protein_key = (str(target), str(native_path))
            protein = protein_cache.get(protein_key)
            if protein is None:
                protein = _load_protein_coords(target=target, native_path=native_path)
                protein_cache[protein_key] = protein
            protein_atom_template = protein_atom_template_cache.get(protein_key)
            if protein_atom_template is None:
                protein_atom_template = _load_protein_atom_template(target=target, native_path=native_path)
                protein_atom_template_cache[protein_key] = protein_atom_template
            protein_atom_template_meta = _normalize_protein_atom_template(protein_atom_template)
            if protein.shape[0] <= 0 and bool(args.fail_on_missing_native):
                failed += 1
                failed_rows += 1
                rows.append(
                    {
                        "queue_id": queue_id,
                        "target": target,
                        "ligand_id": ligand_id,
                        "status": "failed_missing_native",
                        "frames_written": 0,
                        "trajectory_dir": "",
                        "backend": "none",
                        "error": "native_structure_not_found",
                    }
                )
                processed_rows += 1
                _record_progress(
                    queue_id=queue_id,
                    target=target,
                    ligand_id=ligand_id,
                    last_error="native_structure_not_found",
                )
                continue
            if protein.shape[0] <= 0:
                protein = np.zeros((1, 3), dtype=np.float32)

            ligand0 = _compose_ligand_xyz(row)
            pocket = np.asarray(
                [
                    _safe_float(row.get("pocket_x", 0.0)),
                    _safe_float(row.get("pocket_y", 0.0)),
                    _safe_float(row.get("pocket_z", 0.0)),
                ],
                dtype=np.float32,
            )
            affinity = _ligand_affinity_hint(row)
            onsps_norm = _safe_float(
                row.get("ligand_onsps_norm", row.get("onsps_norm", row.get("onsps_count_norm", 0.0))),
                0.0,
            )
            k_attr = float(args.pocket_attract_base) * (0.60 + 1.40 * affinity)
            k_rep = float(args.protein_repulse) * (1.00 + 0.30 * max(0.0, 1.0 - affinity))
            seed_i = int(args.seed) + abs(hash(queue_id)) % 1000003
            strategy_requested, strategy_reason, adress_radius_A, estimated_atom_ratio = _resolve_strategy_type(
                row=row,
                protein_coords=protein,
                pocket_xyz=pocket,
                affinity_hint=float(affinity),
                mode=str(args.strategy_mode),
                dynamic_adress_min_affinity=float(args.dynamic_adress_min_affinity),
                dynamic_adress_max_protein_residues=int(args.dynamic_adress_max_protein_residues),
                dynamic_adress_min_ligand_mw=float(args.dynamic_adress_min_ligand_mw),
                dynamic_adress_fraction=float(args.dynamic_adress_fraction),
                dynamic_adress_force_targets=forced_adress_targets,
                dynamic_adress_base_radius_A=float(args.dynamic_adress_base_radius_A),
                dynamic_adress_affinity_radius_scale=float(args.dynamic_adress_affinity_radius_scale),
                dynamic_adress_mw_radius_scale=float(args.dynamic_adress_mw_radius_scale),
                dynamic_adress_max_all_atom_radius_A=float(args.dynamic_adress_max_all_atom_radius_A),
                dynamic_adress_max_atom_ratio=float(args.dynamic_adress_max_atom_ratio),
                dynamic_adress_cap_force_core_on_radius=bool(args.dynamic_adress_cap_force_core_on_radius),
            )
            strategy_requested_counts[str(strategy_requested)] = int(strategy_requested_counts.get(str(strategy_requested), 0) + 1)
            tdir, npz_path, npz_layout_effective = _build_trajectory_paths(
                out_root=out_root,
                queue_id=queue_id,
                frame_output_format=frame_output_format,
                npz_layout=str(args.npz_layout),
                npz_shard_size=int(args.npz_shard_size),
                row_index=int(row_index),
            )

            entry = {
                "row_index": int(row_index),
                "queue_id": queue_id,
                "target": target,
                "ligand_id": ligand_id,
                "protein_key": protein_key,
                "protein": protein,
                "ligand0": ligand0,
                "pocket": pocket,
                "affinity": float(affinity),
                "onsps_norm": float(onsps_norm),
                "k_attr": float(k_attr),
                "k_rep": float(k_rep),
                "seed_i": int(seed_i),
                "strategy_requested": str(strategy_requested),
                "strategy_reason": str(strategy_reason),
                "adress_radius_A": float(adress_radius_A),
                "estimated_atom_ratio": float(estimated_atom_ratio),
                "protein_atom_template": protein_atom_template_meta["coords"],
                "protein_atom_template_ready": bool(protein_atom_template_meta["ready"]),
                "protein_atom_template_source_type": str(protein_atom_template_meta["source_type"]),
                "protein_atom_template_source_path": str(protein_atom_template_meta["source_path"]),
                "protein_atom_template_warning": str(protein_atom_template_meta["normalization_warning"]),
                "protein_atom_template_count": int(protein_atom_template_meta["atom_count"]),
                "protein_atom_schema_version": int(protein_atom_template_meta["schema_version"]),
                "tdir": tdir,
                "npz_path": npz_path,
                "npz_layout_effective": str(npz_layout_effective),
                "cached_is_npz": False,
            }
            effective_frames_requested, prod_frame_budget_score, prod_frame_budget_applied = _resolve_prod_effective_frames(
                requested_frames=int(args.frames),
                affinity_hint=float(affinity),
                ligand_mw=_safe_float(row.get("ligand_mw", 0.0)),
                strategy_type=str(strategy_requested),
                prod_mode=bool(prod_mode),
                adaptive_budget_enabled=bool(prod_adaptive_frame_budget),
                prod_min_frames=int(prod_min_frames),
                prod_frame_budget_tiers=prod_frame_budget_tiers,
            )
            expected_frames_written_row, expected_last_frame_idx_row = _expected_written_frames(
                int(effective_frames_requested),
                stride,
            )
            entry["effective_frames_requested"] = int(effective_frames_requested)
            entry["expected_frames_written"] = int(expected_frames_written_row)
            entry["expected_last_frame_idx"] = int(expected_last_frame_idx_row)
            entry["prod_frame_budget_score"] = float(prod_frame_budget_score)
            entry["prod_frame_budget_applied"] = bool(prod_frame_budget_applied)
            if bool(prod_frame_budget_applied):
                prod_frame_budget_applied_count += 1
            if bool(args.resume_existing):
                expected_last_frame = os.path.join(tdir, f"frame_{int(expected_last_frame_idx_row):05d}.pdb")
                cached_is_npz = False
                cached_ok = False
                if os.path.isfile(npz_path):
                    cached_is_npz = True
                    cached_ok = _cached_npz_is_valid(npz_path, min_frames=int(expected_frames_written_row))
                    if not cached_ok:
                        try:
                            os.remove(npz_path)
                        except Exception:
                            pass
                elif os.path.isfile(expected_last_frame):
                    cached_ok = True
                entry["cached_is_npz"] = bool(cached_is_npz)
                if cached_ok:
                    if pending_batch:
                        _flush_batch(pending_batch)
                        pending_batch = []
                        pending_sig = None
                        if bool(aborted_early):
                            break
                    _append_ok_cached(entry)
                    continue

            sig = _row_batch_signature(
                protein_key=protein_key,
                protein_shape=tuple(protein.shape),
                ligand_shape=tuple(ligand0.shape),
                strategy_type=str(strategy_requested),
                effective_frames_requested=int(effective_frames_requested),
            )
            entry["batch_sig"] = sig
            if pending_batch and sig != pending_sig:
                _flush_pending_chunks()
                if pending_batch and pending_sig is not None:
                    _flush_batch(pending_batch)
                    pending_batch = []
                    pending_sig = None
                if bool(aborted_early):
                    break
            if not pending_batch:
                pending_sig = sig
            pending_batch.append(entry)
            if pending_sig is not None:
                limit_known = batch_limit_by_sig.get(pending_sig)
                if limit_known is None and len(pending_batch) >= batch_autotune_prefill:
                    _flush_pending_chunks()
                elif limit_known is not None and len(pending_batch) >= int(limit_known):
                    _flush_pending_chunks()

        if pending_batch and not bool(aborted_early):
            _flush_pending_chunks()
            if pending_batch:
                _flush_batch(pending_batch)
                pending_batch = []
                pending_sig = None
        if writer_mode == "process":
            if writer_task_queue is not None:
                writer_task_queue.join()
            if writer_result_queue is not None and writer_inflight > 0:
                drained = _drain_writer_process_results(writer_result_queue, expected_min=writer_inflight)
                writer_inflight = max(0, writer_inflight - int(drained))
        else:
            _drain_writer_futures(writer_futures, wait_all=True)
    except Exception as exc:
        aborted_early = True
        abort_reason = f"{type(exc).__name__}: {exc}"
        _write_progress(status="aborted", last_error=abort_reason)
    finally:
        if writer_mode == "process":
            if writer_task_queue is not None:
                for _ in writer_processes:
                    writer_task_queue.put(None)
                writer_task_queue.join()
            for proc in writer_processes:
                proc.join(timeout=5.0)
            if writer_result_queue is not None:
                try:
                    _drain_writer_process_results(writer_result_queue)
                except Exception as exc:
                    if not abort_reason:
                        abort_reason = f"{type(exc).__name__}: {exc}"
                        aborted_early = True
        elif writer_pool is not None:
            writer_pool.shutdown(wait=True, cancel_futures=False)

    out_df = pd.DataFrame(rows)
    out_summary_json = str(args.out_summary_json).strip() or f"{out_root}_summary.json"
    out_summary_md = str(args.out_summary_md).strip() or f"{out_root}_summary.md"
    _ensure_dir(os.path.dirname(out_manifest_csv) or ".")
    _flush_manifest_chunk(force=True)
    out_df.to_csv(out_manifest_csv, index=False)

    ok_df = (
        out_df[out_df["status"].astype(str).str.startswith("ok")].copy()
        if (not out_df.empty and "status" in out_df.columns)
        else pd.DataFrame()
    )
    tail_summary: Dict[str, Any] = {}
    target_tail_rows: List[Dict[str, Any]] = []
    target_tail_csv = str(args.out_target_tail_csv).strip() or f"{out_root}_target_tail.csv"
    if (not bool(prod_light_artifacts)) and (not ok_df.empty) and ("target" in ok_df.columns):
        ok_df["sim_fps"] = pd.to_numeric(ok_df.get("sim_fps", np.nan), errors="coerce")
        ok_df["elapsed_sec"] = pd.to_numeric(ok_df.get("elapsed_sec", np.nan), errors="coerce")
        fps_all = ok_df["sim_fps"].dropna()
        if not fps_all.empty:
            tail_summary["fps_p05"] = float(np.quantile(fps_all.to_numpy(dtype=np.float64), 0.05))
            tail_summary["fps_worst"] = float(np.min(fps_all.to_numpy(dtype=np.float64)))
        for target, sub in ok_df.groupby("target"):
            fps = pd.to_numeric(sub["sim_fps"], errors="coerce").dropna()
            elapsed = pd.to_numeric(sub["elapsed_sec"], errors="coerce").dropna()
            ratio = pd.to_numeric(sub.get("estimated_atom_ratio", np.nan), errors="coerce").dropna()
            rec = {
                "target": str(target),
                "jobs": int(sub.shape[0]),
                "fps_mean": float(fps.mean()) if not fps.empty else None,
                "fps_p05": float(np.quantile(fps.to_numpy(dtype=np.float64), 0.05)) if not fps.empty else None,
                "fps_min": float(fps.min()) if not fps.empty else None,
                "elapsed_mean_sec": float(elapsed.mean()) if not elapsed.empty else None,
                "elapsed_p95_sec": float(np.quantile(elapsed.to_numpy(dtype=np.float64), 0.95)) if not elapsed.empty else None,
                "elapsed_worst_sec": float(elapsed.max()) if not elapsed.empty else None,
                "estimated_atom_ratio_mean": float(ratio.mean()) if not ratio.empty else None,
                "estimated_atom_ratio_p95": float(np.quantile(ratio.to_numpy(dtype=np.float64), 0.95))
                if not ratio.empty
                else None,
            }
            target_tail_rows.append(rec)
        target_tail_rows = sorted(
            target_tail_rows,
            key=lambda r: (
                float(r["fps_min"]) if isinstance(r.get("fps_min"), (int, float)) and r.get("fps_min") is not None else 1e12
            ),
        )
        if len(target_tail_rows) > 0:
            tail_summary["worst_targets_by_fps"] = target_tail_rows[: min(len(target_tail_rows), 10)]
        pd.DataFrame(target_tail_rows).to_csv(target_tail_csv, index=False)
    summary = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "queue_rows": int(len(df)),
        "processed_rows": int(len(out_df)),
        "ok_rows": int(len(ok_df)),
        "failed_rows": int(failed),
        "prod_mode": bool(prod_mode),
        "prod_light_artifacts": bool(prod_light_artifacts),
        "prod_adaptive_frame_budget": bool(prod_mode and prod_adaptive_frame_budget),
        "prod_early_stop": bool(prod_mode and prod_early_stop),
        "prod_frame_budget_applied_count": int(prod_frame_budget_applied_count),
        "prod_early_stop_batch_count": int(prod_early_stop_batch_count),
        "prod_early_stop_row_count": int(prod_early_stop_row_count),
        "prod_early_stop_eval_keep_count": int(prod_early_stop_eval_keep_count),
        "prod_early_stop_eval_row_count": int(prod_early_stop_eval_row_count),
        "prod_early_stop_metric_backend_counts": prod_early_stop_metric_backend_counts,
        "frames_requested": int(args.frames),
        "min_frames_written": int(ok_df["frames_written"].min()) if (not ok_df.empty) else 0,
        "mean_frames_written": float(ok_df["frames_written"].mean()) if (not ok_df.empty) else 0.0,
        "mean_sim_frames_count": float(ok_df["sim_frames_count"].mean()) if (not ok_df.empty and "sim_frames_count" in ok_df.columns) else 0.0,
        "mean_frames_effective_cap": float(ok_df["frames_effective_cap"].mean()) if (not ok_df.empty and "frames_effective_cap" in ok_df.columns) else float(max(int(args.frames), 1)),
        "backend_counts": ok_backend_counts,
        "strategy_mode": str(args.strategy_mode),
        "strategy_requested_counts": strategy_requested_counts,
        "strategy_final_counts": strategy_final_counts,
        "strategy_fallback_count": int(strategy_fallback_count),
        "aborted_early": bool(aborted_early),
        "abort_reason": str(abort_reason),
        "dynamic_adress_force_targets": sorted(list(forced_adress_targets)),
        "dynamic_adress_hard_caps": {
            "max_atom_ratio": float(args.dynamic_adress_max_atom_ratio),
            "max_all_atom_radius_A": float(args.dynamic_adress_max_all_atom_radius_A),
            "cap_force_core_on_radius": bool(args.dynamic_adress_cap_force_core_on_radius),
        },
        "tail_perf": tail_summary,
        "force_backend_requested": str(args.force_backend),
        "require_rust_hip": bool(args.require_rust_hip),
        "out_root": os.path.abspath(out_root),
        "frame_output_format": frame_output_format,
        "npz_layout": str(args.npz_layout),
        "npz_shard_size": int(args.npz_shard_size),
        "npz_compression": str(args.npz_compression),
        "group_by_signature_sort": bool(getattr(args, "group_by_signature_sort", True)),
        "job_batch_size": int(batch_job_size),
        "job_batch_size_resolved": {str(k): int(v) for k, v in batch_limit_by_sig.items()},
        "job_batch_derate_count": int(job_batch_derate_count),
        "job_batch_derate_events": job_batch_derate_events,
        "job_batch_autotune_rows": batch_autotune_rows,
        "job_batch_autotune_candidates": batch_autotune_candidates,
        "writer_workers": int(writer_workers),
        "writer_mode": str(writer_mode),
        "writer_max_pending": int(writer_max_pending),
        "writer_pending_peak": int(writer_pending_peak),
        "writer_backpressure_count": int(writer_backpressure_count),
        "progress_every_jobs": int(progress_every_jobs),
        "protein_cache_entries": int(len(protein_cache)),
        "protein_atom_template_cache_entries": int(len(protein_atom_template_cache)),
        "protein_atom_template_ready_row_count": int(ok_df["protein_atom_template_ready"].fillna(False).astype(bool).sum())
        if (not ok_df.empty and "protein_atom_template_ready" in ok_df.columns)
        else 0,
        "protein_atom_template_source_type_counts": (
            ok_df["protein_atom_template_source_type"].astype(str).value_counts(dropna=False).to_dict()
            if (not ok_df.empty and "protein_atom_template_source_type" in ok_df.columns)
            else {}
        ),
        "protein_atom_npz_row_count": int(ok_df["protein_atom_frames_available"].fillna(False).astype(bool).sum())
        if (not ok_df.empty and "protein_atom_frames_available" in ok_df.columns)
        else 0,
        "protein_frame_capture_supported_row_count": int(ok_df["protein_frame_capture_supported"].fillna(False).astype(bool).sum())
        if (not ok_df.empty and "protein_frame_capture_supported" in ok_df.columns)
        else 0,
        "protein_frame_capture_static_template_row_count": int(
            ok_df["protein_atom_motion_mode"].astype(str).eq("static_native_template_repeated").sum()
        )
        if (not ok_df.empty and "protein_atom_motion_mode" in ok_df.columns)
        else 0,
        "protein_frame_capture_mode_counts": (
            ok_df["protein_frame_capture_mode"].astype(str).value_counts(dropna=False).to_dict()
            if (not ok_df.empty and "protein_frame_capture_mode" in ok_df.columns)
            else {}
        ),
        "protein_frame_capture_reason_counts": (
            ok_df["protein_frame_capture_reason"].astype(str).value_counts(dropna=False).to_dict()
            if (not ok_df.empty and "protein_frame_capture_reason" in ok_df.columns)
            else {}
        ),
        "engine_cache_entries": int(len(engine_cache)),
        "artifacts": {
            "manifest_csv": out_manifest_csv,
            "manifest_chunks_dir": manifest_chunks_dir,
            "target_tail_csv": target_tail_csv if len(target_tail_rows) > 0 else "",
            "summary_json": out_summary_json,
            "summary_md": "" if bool(prod_light_artifacts) else out_summary_md,
            "progress_json": out_progress_json,
        },
        "prod_light_effects": {
            "manifest_chunks_disabled": bool(prod_artifact_light["manifest_chunks_disabled"]),
            "target_tail_disabled": bool(prod_artifact_light["target_tail_disabled"]),
            "summary_md_disabled": bool(prod_artifact_light["summary_md_disabled"]),
            "progress_every_jobs_effective": int(prod_artifact_light["progress_every_jobs"]),
        },
    }
    _write_progress(
        status="done" if not aborted_early else "aborted",
        last_error=str(abort_reason) if aborted_early else "",
    )
    with open(out_summary_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    if not bool(prod_light_artifacts):
        lines = [
            "# Ligand Trajectory Engine Batch",
            "",
            f"- generated_at_local: {summary['generated_at_local']}",
            f"- queue_rows: {summary['queue_rows']}",
            f"- processed_rows: {summary['processed_rows']}",
            f"- ok_rows: {summary['ok_rows']}",
            f"- failed_rows: {summary['failed_rows']}",
            f"- prod_mode: {summary['prod_mode']}",
            f"- prod_light_artifacts: {summary['prod_light_artifacts']}",
            f"- prod_adaptive_frame_budget: {summary['prod_adaptive_frame_budget']}",
            f"- prod_early_stop: {summary['prod_early_stop']}",
            f"- prod_frame_budget_applied_count: {summary['prod_frame_budget_applied_count']}",
            f"- prod_early_stop_batch_count: {summary['prod_early_stop_batch_count']}",
            f"- prod_early_stop_row_count: {summary['prod_early_stop_row_count']}",
            f"- prod_early_stop_eval_keep_count: {summary['prod_early_stop_eval_keep_count']}",
            f"- prod_early_stop_eval_row_count: {summary['prod_early_stop_eval_row_count']}",
            f"- frames_requested: {summary['frames_requested']}",
            f"- min_frames_written: {summary['min_frames_written']}",
            f"- mean_frames_written: {summary['mean_frames_written']}",
            f"- mean_sim_frames_count: {summary['mean_sim_frames_count']}",
            f"- mean_frames_effective_cap: {summary['mean_frames_effective_cap']}",
            f"- backend_counts: {summary['backend_counts']}",
            f"- tail_fps_p05: {summary['tail_perf'].get('fps_p05') if isinstance(summary.get('tail_perf'), dict) else None}",
            f"- tail_fps_worst: {summary['tail_perf'].get('fps_worst') if isinstance(summary.get('tail_perf'), dict) else None}",
            f"- job_batch_size: {summary['job_batch_size']}",
            f"- job_batch_derate_count: {summary['job_batch_derate_count']}",
            f"- writer_workers: {summary['writer_workers']}",
            f"- writer_max_pending: {summary['writer_max_pending']}",
            f"- writer_pending_peak: {summary['writer_pending_peak']}",
            f"- writer_backpressure_count: {summary['writer_backpressure_count']}",
            f"- out_root: `{out_root}`",
            f"- manifest_csv: `{out_manifest_csv}`",
            f"- manifest_chunks_dir: `{manifest_chunks_dir}`",
            f"- target_tail_csv: `{summary['artifacts'].get('target_tail_csv', '')}`",
        ]
        with open(out_summary_md, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    return summary


def build_parser() -> argparse.ArgumentParser:
    stamp = dt.date.today().isoformat()
    p = argparse.ArgumentParser(
        description=(
            "Generate ligand trajectory frames using core MD engine (Rust HIP when available) "
            "for each queue job."
        )
    )
    p.add_argument("--queue-csv", type=str, required=True)
    p.add_argument("--out-root", type=str, default=f"runs/ligand_traj_engine_{stamp}")
    p.add_argument("--frames", type=int, default=120)
    p.add_argument("--write-every", type=int, default=1)
    p.add_argument(
        "--frame-output-format",
        type=str,
        default="pdb_files",
        choices=["pdb_files", "npz_bundle", "manifest_only"],
    )
    p.add_argument("--npz-compression", type=str, default="store", choices=["store", "compressed"])
    p.add_argument("--npz-layout", type=str, default="flat_shard", choices=["job_dir", "flat_root", "flat_shard"])
    p.add_argument("--npz-shard-size", type=int, default=512)
    p.add_argument("--max-jobs", type=int, default=0)
    p.add_argument("--seed", type=int, default=7)
    # Compatibility with proxy generator CLI.
    p.add_argument("--step-size", type=float, default=0.0)
    p.add_argument("--noise-scale", type=float, default=0.0)
    p.add_argument("--dt-fs", type=float, default=0.002)
    p.add_argument("--friction", type=float, default=1.0)
    p.add_argument("--kT", type=float, default=(0.001987 * 300.0))
    p.add_argument("--force-clip", type=float, default=200.0)
    p.add_argument("--pocket-attract-base", type=float, default=0.16)
    p.add_argument("--protein-repulse", type=float, default=0.22)
    p.add_argument("--bond-k", type=float, default=0.25)
    p.add_argument("--repulse-cutoff-A", type=float, default=4.5)
    p.add_argument("--max-pocket-radius-A", type=float, default=12.0)
    p.add_argument("--box-size-A", type=float, default=120.0)
    p.add_argument("--ff-sigma", type=float, default=3.8)
    p.add_argument("--ff-eps-solv", type=float, default=25.0)
    p.add_argument("--force-backend", type=str, default="auto", choices=["auto", "pytorch"])
    p.add_argument("--require-rust-hip", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument(
        "--strategy-mode",
        type=str,
        default="dynamic",
        choices=["dynamic", "core_only", "adress_only"],
        help="Topology strategy selection for trajectory engine.",
    )
    p.add_argument("--dynamic-adress-min-affinity", type=float, default=0.78)
    p.add_argument("--dynamic-adress-max-protein-residues", type=int, default=200)
    p.add_argument("--dynamic-adress-min-ligand-mw", type=float, default=250.0)
    p.add_argument("--dynamic-adress-fraction", type=float, default=0.15)
    p.add_argument("--dynamic-adress-base-radius-A", type=float, default=6.0)
    p.add_argument("--dynamic-adress-affinity-radius-scale", type=float, default=3.0)
    p.add_argument("--dynamic-adress-mw-radius-scale", type=float, default=2.5)
    p.add_argument("--dynamic-adress-max-all-atom-radius-A", type=float, default=8.0)
    p.add_argument("--dynamic-adress-max-atom-ratio", type=float, default=0.10)
    p.add_argument(
        "--dynamic-adress-cap-force-core-on-radius",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="If estimated AA radius exceeds cap, force core-only instead of clamping silently.",
    )
    p.add_argument(
        "--dynamic-adress-force-targets",
        type=str,
        default="",
        help="Comma-separated targets always forced to ADRESS in dynamic mode.",
    )
    p.add_argument(
        "--dynamic-core-fallback-on-oom",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="If ADRESS run hits memory fault/OOM, retry once with core-only strategy.",
    )
    p.add_argument(
        "--abort-on-runtime-error",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Abort batch immediately on first runtime failure; keep partial outputs.",
    )
    p.add_argument(
        "--abort-on-cpu-backend",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Abort if backend is not rust_hip (prevents slow CPU fallback runs).",
    )
    p.add_argument("--native-path-col", type=str, default="native_pdb_path")
    p.add_argument("--fail-on-missing-native", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--out-manifest-csv", type=str, default="")
    p.add_argument("--out-target-tail-csv", type=str, default="")
    p.add_argument("--out-summary-json", type=str, default="")
    p.add_argument("--out-summary-md", type=str, default="")
    p.add_argument("--out-progress-json", type=str, default="")
    p.add_argument("--progress-every-jobs", type=int, default=25)
    p.add_argument("--resume-existing", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--group-by-signature-sort", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--engine-cache-max-entries", type=int, default=16)
    p.add_argument("--job-batch-size", type=int, default=0, help="0 means autotune per signature.")
    p.add_argument("--job-batch-autotune-candidates", type=str, default="1,2,4,8")
    p.add_argument("--job-batch-autotune-frames", type=int, default=12)
    p.add_argument("--writer-workers", type=int, default=1)
    p.add_argument("--writer-mode", type=str, default="process", choices=["sync", "thread", "process"])
    p.add_argument("--writer-max-pending", type=int, default=64)
    p.add_argument("--manifest-chunk-size", type=int, default=1000)
    p.add_argument("--prod-mode", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--prod-adaptive-frame-budget", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument(
        "--prod-frame-budget-tiers",
        type=str,
        default="0.90:1.00,0.75:0.85,0.60:0.70,0.00:0.55",
        help="Comma-separated score:fraction tiers used when prod adaptive frame budgeting is enabled.",
    )
    p.add_argument("--prod-min-frames", type=int, default=60)
    p.add_argument("--prod-early-stop", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--prod-early-stop-min-frames", type=int, default=72)
    p.add_argument("--prod-early-stop-window", type=int, default=12)
    p.add_argument("--prod-early-stop-min-distance-drift-A", type=float, default=0.12)
    p.add_argument("--prod-early-stop-contact-drift", type=float, default=0.015)
    p.add_argument("--prod-early-stop-max-mean-min-distance-A", type=float, default=6.0)
    p.add_argument("--prod-light-artifacts", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--prod-light-progress-every-jobs", type=int, default=250)
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    payload = run_batch(args)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    if bool(getattr(args, "abort_on_runtime_error", False)) and bool(payload.get("aborted_early", False)):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
