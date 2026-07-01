#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import pickle
import time
import tracemalloc
from pathlib import Path
from typing import Any

import numpy as np

try:
    from rdkit import Chem
except Exception:  # noqa: BLE001 - optional dependency for lightweight CI import safety.
    Chem = None

from betelgeuze_engine.benchmark.docking_gold import DockingGoldRow, evaluate_docking_gold_slice
from betelgeuze_engine.biodiscovery.pose import (
    generate_conformers,
    ligand_symmetry_mappings,
    symmetry_aware_pose_rmsd,
)

ROOT = Path(__file__).resolve().parents[2]

_REPLAY_ROW_SOURCE = "replay"
_GENERATED_POSE_ROW_SOURCE = "generated_pose_smoke"
_GENERATED_POSE_GENERATION_SOURCE = "rdkit_etkdgv3_local"
_POSEBUSTERS_CHECK_SCHEMA_VERSION = "posebusters_style_ligand_validity_v1"
_COMPARISON_ADAPTER_SCHEMA_VERSION = "vina_gnina_comparison_adapter_v1"
_COMPARISON_ENGINE_IDS = ("vina", "gnina")
_COMPARISON_SCORE_COLUMNS = {
    "vina": (
        "vina_score",
        "vina_affinity_score",
        "vina_affinity_kcal_mol",
        "autodock_vina_score",
        "autodock_vina_affinity_kcal_mol",
    ),
    "gnina": (
        "gnina_score",
        "gnina_affinity_score",
        "gnina_affinity_kcal_mol",
        "gnina_cnn_affinity",
        "gnina_docking_score",
    ),
}
_POSEBUSTERS_CLAIM_BOUNDARY = (
    "PoseBusters-style ligand pose validity checks only: finite heavy-atom coordinates, reference heavy-atom "
    "identity, duplicate-coordinate guard, and RDKit-backed nonbonded ligand internal-clash screening when a bond "
    "graph is available. This is not an official PoseBusters run and does not assess receptor-ligand geometry."
)
_GENERATED_POSE_CLAIM_BOUNDARY = (
    "Restricted local generated-pose smoke only; rows are produced from deterministic RDKit conformer "
    "generation against local reference ligands. This path does not run docking, download data, claim "
    "official CASF/PDBbind parity, or substitute replay benchmark evidence."
)
_REPLAY_CLAIM_BOUNDARY = (
    "PDBbind/CASF pose-affinity adapter only; it reads local RDKit-pickled CASF ligand/reference pose pairs "
    "and computes symmetry-aware heavy-atom RMSD in the receptor frame without ligand superposition. The "
    "primary pose_success_rate is aggregated "
    "per complex by best available pose, while pose_row_success_rate remains reported as a diagnostic. It does "
    "not run docking, train affinity models, use external SaaS, download data, or claim official CASF "
    "scoring/ranking performance."
)
_COMPARISON_ADAPTER_CLAIM_BOUNDARY = (
    "Vina/GNINA comparison adapter only: it reads operator-provided comparator scores for the same local "
    "PDBbind/CASF replay pose rows and evaluates them with the same local gold-slice metrics. It does not run "
    "Vina, GNINA, docking, downloads, or external services, and it does not claim official CASF/PDBbind rank."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _float_or_none(value: Any) -> float | None:
    text = _text(value)
    if not text:
        return None
    try:
        number = float(text)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _bool_or_none(value: Any) -> bool | None:
    text = _text(value).lower()
    if text in {"1", "true", "yes", "active"}:
        return True
    if text in {"0", "false", "no", "decoy"}:
        return False
    return None


def _load_gold_metadata(path_like: str | Path) -> dict[str, dict[str, Any]]:
    path = _resolve(path_like)
    if not path.is_file():
        return {}
    metadata: dict[str, dict[str, Any]] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            payload = dict(row)
            pose_id = _text(payload.get("pose_id"))
            complex_id = _text(payload.get("complex_id"))
            if pose_id:
                metadata[pose_id] = payload
            if complex_id:
                metadata.setdefault(complex_id, payload)
    return metadata


def _load_pose_id_allowlist(path_like: str | Path) -> set[str]:
    path = _resolve(path_like)
    if not path.is_file():
        return set()
    pose_ids: set[str] = set()
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames:
            for row in reader:
                pose_id = _text(row.get("pose_id"))
                if pose_id:
                    pose_ids.add(pose_id)
        else:
            handle.seek(0)
            for line in handle:
                pose_id = _text(line)
                if pose_id:
                    pose_ids.add(pose_id)
    return pose_ids


def _load_comparison_scores(path_like: str | Path) -> dict[str, dict[str, Any]]:
    path = _resolve(path_like)
    if not path.is_file():
        return {}
    scores: dict[str, dict[str, Any]] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            payload = dict(row)
            pose_id = _text(payload.get("pose_id"))
            complex_id = _text(payload.get("complex_id"))
            if pose_id:
                scores[pose_id] = payload
            elif complex_id:
                scores.setdefault(complex_id, payload)
    return scores


def _comparison_metadata(
    comparison_scores: dict[str, dict[str, Any]],
    *,
    pose_id: str,
    complex_id: str,
) -> dict[str, Any]:
    return comparison_scores.get(pose_id) or comparison_scores.get(complex_id) or {}


def _comparison_score(metadata: dict[str, Any], engine_id: str) -> float | None:
    for field in _COMPARISON_SCORE_COLUMNS.get(engine_id, ()):
        score = _float_or_none(metadata.get(field))
        if score is not None:
            return score
    return None


def _sha256_file(path: Path | None) -> str:
    if path is None or not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _subset_identity(
    *,
    dataset: Path,
    data_dir: Path,
    pose_files: list[Path],
    reference_paths: list[Path],
    gold_metadata_csv: str,
    max_poses: int,
) -> dict[str, Any]:
    artifact_rows = [
        {
            "role": "pose",
            "name": path.name,
            "relative_path": str(path.relative_to(dataset)) if path.is_relative_to(dataset) else str(path),
            "sha256": _sha256_file(path),
        }
        for path in pose_files
    ]
    artifact_rows.extend(
        {
            "role": "reference",
            "name": path.name,
            "relative_path": str(path.relative_to(dataset)) if path.is_relative_to(dataset) else str(path),
            "sha256": _sha256_file(path),
        }
        for path in reference_paths
    )
    metadata_path = _resolve(gold_metadata_csv) if _text(gold_metadata_csv) else None
    payload = {
        "schema_version": "pdbbind_casf_subset_identity_v1",
        "dataset_artifact": str(dataset),
        "data_5_sdf_dir": str(data_dir),
        "max_poses": int(max_poses),
        "pose_file_names": [path.name for path in pose_files],
        "reference_file_names": [path.name for path in reference_paths],
        "artifact_rows": sorted(artifact_rows, key=lambda row: (row["role"], row["name"], row["relative_path"])),
        "gold_metadata_csv": str(metadata_path or ""),
        "gold_metadata_sha256": _sha256_file(metadata_path),
    }
    identity_payload = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    payload["subset_identity_sha256"] = hashlib.sha256(identity_payload.encode("utf-8")).hexdigest()
    return payload


def _coords(mol: Any) -> list[tuple[float, float, float]]:
    conformer = mol.GetConformer()
    coords: list[tuple[float, float, float]] = []
    for atom in mol.GetAtoms():
        if atom.GetAtomicNum() == 1:
            continue
        point = conformer.GetAtomPosition(atom.GetIdx())
        coords.append((float(point.x), float(point.y), float(point.z)))
    return coords


def _heavy_atom_elements(mol: Any) -> list[str]:
    return [str(atom.GetSymbol()) for atom in mol.GetAtoms() if atom.GetAtomicNum() != 1]


def _direct_rmsd(a: list[tuple[float, float, float]], b: list[tuple[float, float, float]]) -> float | None:
    if not a or len(a) != len(b):
        return None
    total = 0.0
    for (ax, ay, az), (bx, by, bz) in zip(a, b):
        if not all(math.isfinite(value) for value in (ax, ay, az, bx, by, bz)):
            return None
        total += (ax - bx) ** 2 + (ay - by) ** 2 + (az - bz) ** 2
    value = math.sqrt(total / len(a))
    return value if math.isfinite(value) else None


def _pairwise_min_distance(
    coords: list[tuple[float, float, float]],
    *,
    excluded_pairs: set[tuple[int, int]] | None = None,
) -> tuple[float | None, int]:
    excluded = excluded_pairs or set()
    min_distance: float | None = None
    close_duplicate_count = 0
    for i, (ax, ay, az) in enumerate(coords):
        for j in range(i + 1, len(coords)):
            if (i, j) in excluded:
                continue
            bx, by, bz = coords[j]
            distance = math.sqrt((ax - bx) ** 2 + (ay - by) ** 2 + (az - bz) ** 2)
            if min_distance is None or distance < min_distance:
                min_distance = distance
            if distance < 1.0e-4:
                close_duplicate_count += 1
    return min_distance, close_duplicate_count


def _pair_count_below_distance(
    coords: list[tuple[float, float, float]],
    *,
    threshold: float,
    excluded_pairs: set[tuple[int, int]] | None = None,
) -> int:
    excluded = excluded_pairs or set()
    count = 0
    for i, (ax, ay, az) in enumerate(coords):
        for j in range(i + 1, len(coords)):
            if (i, j) in excluded:
                continue
            bx, by, bz = coords[j]
            distance = math.sqrt((ax - bx) ** 2 + (ay - by) ** 2 + (az - bz) ** 2)
            if distance < threshold:
                count += 1
    return count


def _rdkit_excluded_heavy_pairs(mol: Any) -> tuple[set[tuple[int, int]], bool]:
    if not hasattr(mol, "GetBonds"):
        return set(), False
    try:
        heavy_atom_indices = [atom.GetIdx() for atom in mol.GetAtoms() if atom.GetAtomicNum() != 1]
        heavy_position = {atom_idx: pos for pos, atom_idx in enumerate(heavy_atom_indices)}
        adjacency: dict[int, set[int]] = {atom_idx: set() for atom_idx in heavy_atom_indices}
        for bond in mol.GetBonds():
            begin = int(bond.GetBeginAtomIdx())
            end = int(bond.GetEndAtomIdx())
            if begin not in adjacency or end not in adjacency:
                continue
            adjacency[begin].add(end)
            adjacency[end].add(begin)
        excluded: set[tuple[int, int]] = set()
        for i, atom_i in enumerate(heavy_atom_indices):
            for j, atom_j in enumerate(heavy_atom_indices[i + 1 :], start=i + 1):
                if atom_j in adjacency.get(atom_i, set()):
                    excluded.add((heavy_position[atom_i], heavy_position[atom_j]))
                    continue
                if adjacency.get(atom_i, set()).intersection(adjacency.get(atom_j, set())):
                    excluded.add((heavy_position[atom_i], heavy_position[atom_j]))
        return excluded, True
    except Exception:  # noqa: BLE001 - validity diagnostics should fail closed at the row level.
        return set(), False


def _posebusters_style_validity_from_coords(
    *,
    reference_coords: list[tuple[float, float, float]],
    pose_coords: list[tuple[float, float, float]],
    reference_elements: list[str],
    pose_elements: list[str],
    excluded_pairs: set[tuple[int, int]] | None = None,
    bond_graph_available: bool = False,
) -> tuple[bool, dict[str, Any], list[str]]:
    blockers: list[str] = []
    diagnostics: dict[str, Any] = {
        "schema_version": _POSEBUSTERS_CHECK_SCHEMA_VERSION,
        "claim_boundary": _POSEBUSTERS_CLAIM_BOUNDARY,
        "reference_heavy_atom_count": len(reference_coords),
        "pose_heavy_atom_count": len(pose_coords),
        "heavy_atom_count_match": len(reference_coords) == len(pose_coords) and len(pose_coords) > 0,
        "heavy_atom_elements_match": reference_elements == pose_elements and bool(pose_elements),
        "finite_heavy_atom_coordinates": True,
        "duplicate_heavy_atom_coordinate_pair_count": 0,
        "bond_graph_available": bool(bond_graph_available),
        "nonbonded_ligand_internal_clash_assessed": bool(bond_graph_available),
        "nonbonded_ligand_internal_clash_count": 0,
        "min_nonbonded_heavy_atom_distance_A": None,
        "nonbonded_clash_distance_threshold_A": 0.75,
        "official_posebusters_run": False,
    }
    if not diagnostics["heavy_atom_count_match"]:
        blockers.append("posebusters_heavy_atom_count_mismatch")
    if not diagnostics["heavy_atom_elements_match"]:
        blockers.append("posebusters_heavy_atom_element_mismatch")
    all_coords = list(reference_coords) + list(pose_coords)
    finite_coords = all(
        math.isfinite(value)
        for coord in all_coords
        for value in coord
    )
    diagnostics["finite_heavy_atom_coordinates"] = bool(finite_coords)
    if not finite_coords:
        blockers.append("posebusters_nonfinite_coordinates")

    if finite_coords and pose_coords:
        duplicate_min, duplicate_count = _pairwise_min_distance(pose_coords)
        diagnostics["duplicate_heavy_atom_coordinate_pair_count"] = int(duplicate_count)
        diagnostics["min_heavy_atom_distance_A"] = duplicate_min
        if duplicate_count > 0:
            blockers.append("posebusters_duplicate_heavy_atom_coordinates")
        nonbonded_min, _duplicate_count_in_nonbonded_set = _pairwise_min_distance(
            pose_coords,
            excluded_pairs=excluded_pairs,
        )
        diagnostics["min_nonbonded_heavy_atom_distance_A"] = nonbonded_min
        if bond_graph_available and nonbonded_min is not None and nonbonded_min < 0.75:
            diagnostics["nonbonded_ligand_internal_clash_count"] = _pair_count_below_distance(
                pose_coords,
                threshold=0.75,
                excluded_pairs=excluded_pairs,
            )
            blockers.append("posebusters_ligand_internal_clash")
    diagnostics["status"] = "posebusters_style_valid" if not blockers else "blocked_posebusters_style_validity"
    return not blockers, diagnostics, blockers


def _posebusters_style_validity(ref_mol: Any, pose_mol: Any) -> tuple[bool, dict[str, Any], list[str]]:
    excluded_pairs, bond_graph_available = _rdkit_excluded_heavy_pairs(pose_mol)
    return _posebusters_style_validity_from_coords(
        reference_coords=_coords(ref_mol),
        pose_coords=_coords(pose_mol),
        reference_elements=_heavy_atom_elements(ref_mol),
        pose_elements=_heavy_atom_elements(pose_mol),
        excluded_pairs=excluded_pairs,
        bond_graph_available=bond_graph_available,
    )


def _symmetry_aware_heavy_atom_rmsd(ref_mol: Any, pose_mol: Any) -> tuple[float | None, dict[str, Any]]:
    ref_coords = _coords(ref_mol)
    pose_coords = _coords(pose_mol)
    ref_elements = _heavy_atom_elements(ref_mol)
    pose_elements = _heavy_atom_elements(pose_mol)
    diagnostics: dict[str, Any] = {
        "method": "rdkit_self_substructure_automorphism_no_ligand_alignment",
        "reference_heavy_atom_count": len(ref_coords),
        "pose_heavy_atom_count": len(pose_coords),
        "symmetry_mapping_count": 0,
        "atom_identity_checked": True,
        "ligand_alignment_applied": False,
    }
    if not ref_coords or len(ref_coords) != len(pose_coords):
        diagnostics["status"] = "heavy_atom_count_mismatch"
        return None, diagnostics
    if ref_elements != pose_elements:
        diagnostics["status"] = "heavy_atom_element_order_mismatch"
        return None, diagnostics
    try:
        if Chem is None:
            raise RuntimeError("rdkit_unavailable")
        ref_heavy = Chem.RemoveHs(ref_mol)
        mappings = ref_heavy.GetSubstructMatches(ref_heavy, uniquify=False, maxMatches=512)
    except Exception:
        mappings = ()
    candidates = [tuple(range(len(ref_coords)))]
    for mapping in mappings:
        if len(mapping) == len(ref_coords):
            candidates.append(tuple(int(idx) for idx in mapping))
    seen: set[tuple[int, ...]] = set()
    best: float | None = None
    for mapping in candidates:
        if mapping in seen:
            continue
        seen.add(mapping)
        if any(ref_elements[int(ref_idx)] != pose_elements[pose_idx] for pose_idx, ref_idx in enumerate(mapping)):
            continue
        mapped_ref = [ref_coords[int(ref_idx)] for ref_idx in mapping]
        value = _direct_rmsd(mapped_ref, pose_coords)
        if value is not None and (best is None or value < best):
            best = value
    diagnostics["symmetry_mapping_count"] = len(seen)
    diagnostics["status"] = "symmetry_aware_rmsd_computed" if best is not None else "symmetry_mapping_failed"
    return best, diagnostics


def _load_ligand(path: Path) -> Any:
    payload = pickle.loads(path.read_bytes())
    if isinstance(payload, tuple) and payload:
        return payload[0]
    return payload


def _reference_path(data_dir: Path, complex_id: str) -> Path | None:
    for candidate in [data_dir / complex_id, data_dir / f"{complex_id}_ligand"]:
        if candidate.exists():
            return candidate
    return None


def _is_pose_file(path: Path) -> bool:
    name = path.name
    if name.endswith("_ligand"):
        return False
    if "_" not in name:
        return False
    suffix = name.rsplit("_", 1)[-1]
    return suffix.isdigit()


def _pose_rank(path: Path) -> int:
    try:
        return int(path.name.rsplit("_", 1)[-1])
    except (IndexError, ValueError):
        return 10**9


def _mol_smiles(mol: Any) -> str:
    if Chem is None:
        raise RuntimeError("rdkit_unavailable")
    heavy = Chem.RemoveHs(mol)
    return Chem.MolToSmiles(heavy, isomericSmiles=True)


def _reference_coords_array(mol: Any) -> list[tuple[float, float, float]]:
    return _coords(mol)


def _generated_pose_reference_comparison_status(
    *,
    rmsd: float | None,
    rmsd_diagnostics: dict[str, Any],
    generated_pose_count: int,
) -> str:
    if generated_pose_count <= 0:
        return "generated_pose_count_zero"
    if rmsd is None:
        return str(rmsd_diagnostics.get("status") or "generated_pose_rmsd_not_computable")
    return "generated_pose_reference_rmsd_computed"


def _build_generated_pose_smoke_rows(
    *,
    complex_ids: list[str],
    data_dir: Path,
    threshold: float,
    generation_seed: int,
    generated_pose_count: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for complex_id in complex_ids:
        reference = _reference_path(data_dir, complex_id)
        blockers: list[str] = []
        rmsd: float | None = None
        ref_atom_count = 0
        pose_atom_count = 0
        rmsd_diagnostics: dict[str, Any] = {}
        posebusters_valid = False
        posebusters_blockers: list[str] = []
        posebusters_diagnostics: dict[str, Any] = {
            "schema_version": _POSEBUSTERS_CHECK_SCHEMA_VERSION,
            "status": "posebusters_style_not_assessed",
            "claim_boundary": _POSEBUSTERS_CLAIM_BOUNDARY,
            "official_posebusters_run": False,
        }
        actual_generated_pose_count = 0
        row_start = time.perf_counter()
        tracemalloc.start()
        comparison_status = ""
        if Chem is None:
            blockers.append("rdkit_unavailable")
            rmsd_diagnostics = {
                "method": "",
                "status": "rdkit_unavailable",
                "generation_source": _GENERATED_POSE_GENERATION_SOURCE,
                "generation_seed": int(generation_seed),
                "generated_pose_count": 0,
            }
            comparison_status = "rdkit_unavailable"
        elif reference is None:
            blockers.append("reference_ligand_missing")
        else:
            try:
                ref_mol = _load_ligand(reference)
                smiles = _mol_smiles(ref_mol)
                ref_coords = np.asarray(_reference_coords_array(ref_mol), dtype=np.float64)
                ref_atom_count = len(ref_coords)
                reference_elements = _heavy_atom_elements(ref_mol)
                generated = generate_conformers(smiles, generated_pose_count, generation_seed)
                if generated is None or int(getattr(generated, "shape", [0])[0] or 0) <= 0:
                    blockers.append("generated_pose_conformer_embedding_failed")
                else:
                    actual_generated_pose_count = int(generated.shape[0])
                    pose_coords = generated[0]
                    pose_atom_count = int(pose_coords.shape[0])
                    symmetry_mappings = ligand_symmetry_mappings(smiles)
                    rmsd_value = symmetry_aware_pose_rmsd(
                        pose_coords,
                        ref_coords,
                        symmetry_mappings,
                    )
                    rmsd = rmsd_value if math.isfinite(rmsd_value) else None
                    rmsd_diagnostics = {
                        "method": "rdkit_etkdgv3_symmetry_aware_heavy_atom_rmsd",
                        "reference_heavy_atom_count": ref_atom_count,
                        "pose_heavy_atom_count": pose_atom_count,
                        "symmetry_mapping_count": len(symmetry_mappings),
                        "atom_identity_checked": True,
                        "ligand_alignment_applied": False,
                        "generation_source": _GENERATED_POSE_GENERATION_SOURCE,
                        "generation_seed": int(generation_seed),
                        "generated_pose_count": actual_generated_pose_count,
                        "status": (
                            "generated_pose_reference_rmsd_computed"
                            if rmsd is not None
                            else "generated_pose_rmsd_not_computable"
                        ),
                    }
                    if rmsd is None:
                        blockers.append(str(rmsd_diagnostics.get("status") or "generated_pose_rmsd_not_computable"))
                    posebusters_valid, posebusters_diagnostics, posebusters_blockers = (
                        _posebusters_style_validity_from_coords(
                            reference_coords=[
                                (float(x), float(y), float(z))
                                for x, y, z in ref_coords.tolist()
                            ],
                            pose_coords=[
                                (float(x), float(y), float(z))
                                for x, y, z in pose_coords.tolist()
                            ],
                            reference_elements=reference_elements,
                            pose_elements=reference_elements[:pose_atom_count],
                        )
                    )
                    blockers.extend(posebusters_blockers)
            except Exception as exc:  # noqa: BLE001 - smoke rows should report concrete row-level failure.
                blockers.append(f"generated_pose_smoke_failed:{type(exc).__name__}")
        _current_bytes, peak_bytes = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        runtime_ms = max((time.perf_counter() - row_start) * 1000.0, 0.001)
        peak_memory_mb = max(float(peak_bytes) / (1024.0 * 1024.0), 0.001)
        if not comparison_status:
            comparison_status = _generated_pose_reference_comparison_status(
                rmsd=rmsd,
                rmsd_diagnostics=rmsd_diagnostics,
                generated_pose_count=actual_generated_pose_count,
            )
        success = rmsd is not None and rmsd <= threshold and not blockers
        rows.append(
            {
                "suite_id": "pdbbind_casf_pose_affinity",
                "complex_id": complex_id,
                "pose_id": f"{complex_id}_generated_smoke_0",
                "pose_success": int(success),
                "pose_rmsd_A": rmsd if rmsd is not None else "",
                "pose_success_rmsd_threshold_A": threshold,
                "reference_ligand": str(reference or ""),
                "pose_artifact": "",
                "reference_heavy_atom_count": ref_atom_count,
                "pose_heavy_atom_count": pose_atom_count,
                "pose_rmsd_method": str(rmsd_diagnostics.get("method", "")),
                "pose_rmsd_diagnostics": json.dumps(rmsd_diagnostics, sort_keys=True),
                "posebusters_valid": int(posebusters_valid),
                "posebusters_blocker_count": len(posebusters_blockers),
                "posebusters_blockers": ";".join(posebusters_blockers),
                "posebusters_checks": json.dumps(posebusters_diagnostics, sort_keys=True),
                "blocker_count": len(blockers),
                "blockers": ";".join(blockers),
                "active_label": "",
                "affinity_label": "",
                "score": "",
                "baseline_score": "",
                "vina_score": "",
                "gnina_score": "",
                "comparison_score_source": "",
                "split_id": "generated_pose_smoke",
                "abstained": "",
                "abstention_reasons": "",
                "chirality_failure": "",
                "tautomer_failure": "",
                "protonation_failure": "",
                "chemistry_evidence_present": 0,
                "runtime_ms": f"{runtime_ms:.6f}",
                "peak_memory_mb": f"{peak_memory_mb:.6f}",
                "runtime_metric_source": "builder_wall_clock_perf_counter",
                "peak_memory_metric_source": "builder_tracemalloc_peak",
                "row_source": _GENERATED_POSE_ROW_SOURCE,
                "pose_generation_source": _GENERATED_POSE_GENERATION_SOURCE,
                "pose_generation_seed": int(generation_seed),
                "generated_pose_count": actual_generated_pose_count,
                "generated_pose_reference_comparison_status": comparison_status,
                "generated_pose_claim_boundary": _GENERATED_POSE_CLAIM_BOUNDARY,
            }
        )
    return rows


def _chemistry_failures_from_metadata(metadata: dict[str, Any]) -> tuple[tuple[str, ...], bool]:
    fields = {
        "chirality_failure": "chirality_failure",
        "tautomer_failure": "tautomer_failure",
        "protonation_failure": "protonation_failure",
    }
    evidence_present = all(_text(metadata.get(field)) for field in fields)
    failures = [
        token
        for field, token in fields.items()
        if _bool_or_none(metadata.get(field)) is True
    ]
    return tuple(failures), evidence_present


def _gold_row_from_result_row(
    row: dict[str, Any],
    *,
    score: float | None = None,
    baseline_score: float | None = None,
) -> DockingGoldRow:
    return DockingGoldRow(
        complex_id=_text(row.get("complex_id")),
        pose_id=_text(row.get("pose_id")),
        pose_rank=_pose_rank(Path(_text(row.get("pose_id")))),
        pose_rmsd_a=float(row["pose_rmsd_A"]) if _text(row.get("pose_rmsd_A")) else None,
        score=_float_or_none(row.get("score")) if score is None else score,
        baseline_score=_float_or_none(row.get("baseline_score")) if baseline_score is None else baseline_score,
        affinity_label=_float_or_none(row.get("affinity_label")),
        active_label=_bool_or_none(row.get("active_label")),
        split_id=_text(row.get("split_id") or "heldout"),
        abstained=bool(_bool_or_none(row.get("abstained")) is True),
        chemistry_failures=tuple(
            failure
            for failure in [
                "chirality_failure" if _bool_or_none(row.get("chirality_failure")) is True else "",
                "tautomer_failure" if _bool_or_none(row.get("tautomer_failure")) is True else "",
                "protonation_failure" if _bool_or_none(row.get("protonation_failure")) is True else "",
            ]
            if failure
        ),
        chemistry_evidence_present=bool(int(row.get("chemistry_evidence_present") or 0)),
        abstention_reasons=tuple(
            reason for reason in _text(row.get("abstention_reasons")).split(";") if reason
        ),
        runtime_ms=_float_or_none(row.get("runtime_ms")),
        peak_memory_mb=_float_or_none(row.get("peak_memory_mb")),
    )


def _comparison_metrics(
    replay_rows: list[dict[str, Any]],
    *,
    engine_id: str,
    threshold: float,
) -> tuple[dict[str, Any], list[str]]:
    score_field = f"{engine_id}_score"
    scored_rows = [
        _gold_row_from_result_row(row, score=_float_or_none(row.get(score_field)), baseline_score=None)
        for row in replay_rows
        if _float_or_none(row.get(score_field)) is not None
    ]
    missing_count = len(replay_rows) - len(scored_rows)
    blockers: list[str] = []
    if not replay_rows:
        blockers.append("comparison_replay_rows_missing")
    if missing_count:
        blockers.append(f"{engine_id}_comparison_score_incomplete")
    metrics = evaluate_docking_gold_slice(
        scored_rows,
        pose_success_rmsd_a=threshold,
        top_k=5,
        require_baseline=False,
    )
    blockers.extend(str(blocker) for blocker in metrics.blockers)
    status = f"{engine_id}_comparison_adapter_ready" if not blockers else f"blocked_{engine_id}_comparison_adapter"
    payload = {
        "engine_id": engine_id,
        "status": status,
        "score_count": len(scored_rows),
        "missing_score_count": missing_count,
        "same_input_row_count_match": len(scored_rows) == len(replay_rows) and bool(replay_rows),
        "ranking_spearman": metrics.ranking_spearman,
        "pr_auc": metrics.pr_auc,
        "topk_hit_rate": metrics.topk_hit_rate,
        "decoy_rejection_rate": metrics.decoy_rejection_rate,
        "top1_pose_success_rate": metrics.top1_pose_success_rate,
        "top5_pose_success_rate": metrics.top5_pose_success_rate,
        "top1_mean_rmsd_A": metrics.top1_mean_rmsd_a,
        "top5_best_mean_rmsd_A": metrics.top5_best_mean_rmsd_a,
        "blockers": sorted(set(blockers)),
        "gold_metric_blockers": list(metrics.blockers),
    }
    return payload, sorted(set(blockers))


def build_results(args: argparse.Namespace) -> dict[str, Any]:
    dataset = _resolve(args.dataset_artifact)
    data_dir = dataset / "data_5_sdf"
    pose_files = sorted(path for path in data_dir.iterdir() if path.is_file() and _is_pose_file(path)) if data_dir.exists() else []
    pose_id_allowlist = (
        _load_pose_id_allowlist(args.pose_id_allowlist_csv)
        if _text(getattr(args, "pose_id_allowlist_csv", ""))
        else set()
    )
    if pose_id_allowlist:
        pose_files = [path for path in pose_files if path.name in pose_id_allowlist]
    if int(args.max_poses) > 0:
        pose_files = pose_files[: int(args.max_poses)]
    rows: list[dict[str, Any]] = []
    threshold = float(args.pose_success_rmsd_a)
    gold_metadata = _load_gold_metadata(args.gold_metadata_csv) if _text(getattr(args, "gold_metadata_csv", "")) else {}
    comparison_scores_csv = _text(getattr(args, "comparison_scores_csv", "")) or _text(
        getattr(args, "vina_gnina_comparison_csv", "")
    )
    comparison_scores = _load_comparison_scores(comparison_scores_csv) if comparison_scores_csv else {}
    comparison_adapter_enabled = bool(comparison_scores_csv)
    reference_paths = sorted(
        {
            reference
            for complex_id in {path.name.split("_", 1)[0] for path in pose_files}
            for reference in [_reference_path(data_dir, complex_id)]
            if reference is not None
        },
        key=lambda path: path.name,
    )
    subset_identity = _subset_identity(
        dataset=dataset,
        data_dir=data_dir,
        pose_files=pose_files,
        reference_paths=reference_paths,
        gold_metadata_csv=str(getattr(args, "gold_metadata_csv", "")),
        max_poses=int(args.max_poses),
    )

    for pose_path in pose_files:
        complex_id = pose_path.name.split("_", 1)[0]
        metadata = gold_metadata.get(pose_path.name, gold_metadata.get(complex_id, {}))
        comparator_metadata = _comparison_metadata(
            comparison_scores,
            pose_id=pose_path.name,
            complex_id=complex_id,
        )
        vina_score = _comparison_score(comparator_metadata, "vina")
        gnina_score = _comparison_score(comparator_metadata, "gnina")
        reference = _reference_path(data_dir, complex_id)
        blockers: list[str] = []
        rmsd: float | None = None
        ref_atom_count = 0
        pose_atom_count = 0
        rmsd_diagnostics: dict[str, Any] = {}
        posebusters_valid = False
        posebusters_blockers: list[str] = []
        posebusters_diagnostics: dict[str, Any] = {
            "schema_version": _POSEBUSTERS_CHECK_SCHEMA_VERSION,
            "status": "posebusters_style_not_assessed",
            "claim_boundary": _POSEBUSTERS_CLAIM_BOUNDARY,
            "official_posebusters_run": False,
        }
        row_start = time.perf_counter()
        tracemalloc.start()
        if reference is None:
            blockers.append("reference_ligand_missing")
        else:
            try:
                ref_mol = _load_ligand(reference)
                pose_mol = _load_ligand(pose_path)
                rmsd, rmsd_diagnostics = _symmetry_aware_heavy_atom_rmsd(ref_mol, pose_mol)
                posebusters_valid, posebusters_diagnostics, posebusters_blockers = _posebusters_style_validity(
                    ref_mol,
                    pose_mol,
                )
                ref_atom_count = int(rmsd_diagnostics.get("reference_heavy_atom_count") or 0)
                pose_atom_count = int(rmsd_diagnostics.get("pose_heavy_atom_count") or 0)
                if rmsd is None:
                    blockers.append(str(rmsd_diagnostics.get("status") or "pose_rmsd_not_computable"))
                blockers.extend(posebusters_blockers)
            except Exception as exc:  # noqa: BLE001 - artifact parser should report concrete row-level failure.
                blockers.append(f"rdkit_pickle_parse_failed:{type(exc).__name__}")
        _current_bytes, peak_bytes = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        runtime_ms = max((time.perf_counter() - row_start) * 1000.0, 0.001)
        peak_memory_mb = max(float(peak_bytes) / (1024.0 * 1024.0), 0.001)
        chemistry_failures, chemistry_evidence_present = _chemistry_failures_from_metadata(metadata)
        if not chemistry_evidence_present:
            blockers.append("chemistry_failure_evidence_missing")
        success = rmsd is not None and rmsd <= threshold and not blockers
        rows.append(
            {
                "suite_id": "pdbbind_casf_pose_affinity",
                "complex_id": complex_id,
                "pose_id": pose_path.name,
                "pose_success": int(success),
                "pose_rmsd_A": rmsd if rmsd is not None else "",
                "pose_success_rmsd_threshold_A": threshold,
                "reference_ligand": str(reference or ""),
                "pose_artifact": str(pose_path),
                "reference_heavy_atom_count": ref_atom_count,
                "pose_heavy_atom_count": pose_atom_count,
                "pose_rmsd_method": str(rmsd_diagnostics.get("method", "")),
                "pose_rmsd_diagnostics": json.dumps(rmsd_diagnostics, sort_keys=True),
                "posebusters_valid": int(posebusters_valid),
                "posebusters_blocker_count": len(posebusters_blockers),
                "posebusters_blockers": ";".join(posebusters_blockers),
                "posebusters_checks": json.dumps(posebusters_diagnostics, sort_keys=True),
                "blocker_count": len(blockers),
                "blockers": ";".join(blockers),
                "active_label": _text(metadata.get("active_label")),
                "affinity_label": _text(metadata.get("affinity_label")),
                "score": _text(metadata.get("score")),
                "baseline_score": _text(metadata.get("baseline_score")),
                "vina_score": vina_score if vina_score is not None else "",
                "gnina_score": gnina_score if gnina_score is not None else "",
                "comparison_score_source": _text(
                    comparator_metadata.get("score_source")
                    or comparator_metadata.get("source")
                    or comparator_metadata.get("engine_score_source")
                ),
                "split_id": _text(metadata.get("split_id") or "heldout"),
                "abstained": _text(metadata.get("abstained")),
                "abstention_reasons": _text(metadata.get("abstention_reasons")),
                "chirality_failure": _text(metadata.get("chirality_failure")),
                "tautomer_failure": _text(metadata.get("tautomer_failure")),
                "protonation_failure": _text(metadata.get("protonation_failure")),
                "chemistry_evidence_present": int(chemistry_evidence_present),
                "runtime_ms": f"{runtime_ms:.6f}",
                "peak_memory_mb": f"{peak_memory_mb:.6f}",
                "runtime_metric_source": "builder_wall_clock_perf_counter",
                "peak_memory_metric_source": "builder_tracemalloc_peak",
                "row_source": _REPLAY_ROW_SOURCE,
                "pose_generation_source": "",
                "pose_generation_seed": "",
                "generated_pose_count": "",
                "generated_pose_reference_comparison_status": "",
                "generated_pose_claim_boundary": "",
            }
        )

    generate_poses = bool(getattr(args, "generate_poses", False))
    generation_seed = int(getattr(args, "generate_poses_seed", 42) or 42)
    generated_pose_count = max(int(getattr(args, "generate_poses_count", 1) or 1), 1)
    generate_poses_max_complexes = max(int(getattr(args, "generate_poses_max_complexes", 2) or 2), 1)
    if generate_poses:
        smoke_complex_ids = sorted({path.name.split("_", 1)[0] for path in pose_files})[:generate_poses_max_complexes]
        rows.extend(
            _build_generated_pose_smoke_rows(
                complex_ids=smoke_complex_ids,
                data_dir=data_dir,
                threshold=threshold,
                generation_seed=generation_seed,
                generated_pose_count=generated_pose_count,
            )
        )

    replay_rows = [row for row in rows if _text(row.get("row_source")) == _REPLAY_ROW_SOURCE]
    generated_pose_rows = [row for row in rows if _text(row.get("row_source")) == _GENERATED_POSE_ROW_SOURCE]
    scored_rows = [row for row in replay_rows if _text(row.get("pose_rmsd_A"))]
    posebusters_assessed_rows = [row for row in replay_rows if _text(row.get("posebusters_valid"))]
    posebusters_valid_count = sum(1 for row in posebusters_assessed_rows if int(row.get("posebusters_valid") or 0) == 1)
    posebusters_valid_rate = (
        posebusters_valid_count / len(posebusters_assessed_rows)
        if posebusters_assessed_rows
        else 0.0
    )
    pose_success_count = sum(1 for row in replay_rows if int(row.get("pose_success") or 0) == 1)
    pose_success_rate = pose_success_count / len(replay_rows) if replay_rows else 0.0
    by_complex: dict[str, list[float]] = {}
    for row in scored_rows:
        try:
            rmsd = float(row["pose_rmsd_A"])
        except (TypeError, ValueError):
            continue
        by_complex.setdefault(_text(row.get("complex_id")), []).append(rmsd)
    complex_success_count = sum(1 for values in by_complex.values() if min(values) <= threshold)
    complex_success_rate = complex_success_count / len(by_complex) if by_complex else 0.0
    gold_metrics = evaluate_docking_gold_slice(
        [_gold_row_from_result_row(row) for row in replay_rows],
        pose_success_rmsd_a=threshold,
        top_k=5,
    )
    comparison_metric_payloads: dict[str, dict[str, Any]] = {}
    comparison_blockers: list[str] = []
    if comparison_adapter_enabled:
        for engine_id in _COMPARISON_ENGINE_IDS:
            engine_payload, engine_blockers = _comparison_metrics(
                replay_rows,
                engine_id=engine_id,
                threshold=threshold,
            )
            comparison_metric_payloads[engine_id] = engine_payload
            comparison_blockers.extend(f"{engine_id}:{blocker}" for blocker in engine_blockers)
    comparison_adapter_status = (
        "vina_gnina_comparison_adapter_not_requested"
        if not comparison_adapter_enabled
        else (
            "vina_gnina_comparison_adapter_ready"
            if not comparison_blockers
            else "blocked_vina_gnina_comparison_adapter"
        )
    )
    primary_threshold = float(args.threshold)
    blockers: list[str] = []
    if not dataset.exists():
        blockers.append("dataset_artifact_missing")
    if not data_dir.exists():
        blockers.append("data_5_sdf_dir_missing")
    if not replay_rows:
        blockers.append("pose_files_missing")
    if any(int(row.get("blocker_count") or 0) > 0 for row in replay_rows):
        blockers.append("row_level_benchmark_blockers_present")
    if complex_success_rate + 1e-12 < primary_threshold:
        blockers.append("pose_success_rate_below_threshold")
    if gold_metrics.status != "pass":
        blockers.append("gold_metrics_blocked")
    if comparison_adapter_enabled and comparison_blockers:
        blockers.append("vina_gnina_comparison_adapter_blocked")

    out_csv = _resolve(args.out_csv)
    out_json = _resolve(args.out_json)
    out_md = _resolve(args.out_md)
    fields = [
        "suite_id",
        "complex_id",
        "pose_id",
        "pose_success",
        "pose_rmsd_A",
        "pose_success_rmsd_threshold_A",
        "reference_ligand",
        "pose_artifact",
        "reference_heavy_atom_count",
        "pose_heavy_atom_count",
        "pose_rmsd_method",
        "pose_rmsd_diagnostics",
        "posebusters_valid",
        "posebusters_blocker_count",
        "posebusters_blockers",
        "posebusters_checks",
        "blocker_count",
        "blockers",
        "active_label",
        "affinity_label",
        "score",
        "baseline_score",
        "vina_score",
        "gnina_score",
        "comparison_score_source",
        "split_id",
        "abstained",
        "abstention_reasons",
        "chirality_failure",
        "tautomer_failure",
        "protonation_failure",
        "chemistry_evidence_present",
        "runtime_ms",
        "peak_memory_mb",
        "runtime_metric_source",
        "peak_memory_metric_source",
        "row_source",
        "pose_generation_source",
        "pose_generation_seed",
        "generated_pose_count",
        "generated_pose_reference_comparison_status",
        "generated_pose_claim_boundary",
    ]
    symmetry_aware_ligand_rmsd_coverage = len(scored_rows) / len(replay_rows) if replay_rows else 0.0
    symmetry_aware_ligand_rmsd_ready = bool(replay_rows) and len(scored_rows) == len(replay_rows)
    posebusters_style_validity_checks_ready = (
        bool(replay_rows)
        and len(posebusters_assessed_rows) == len(replay_rows)
        and bool(_POSEBUSTERS_CHECK_SCHEMA_VERSION)
    )
    vina_gnina_comparison_adapter_contract_ready = (
        _COMPARISON_ADAPTER_SCHEMA_VERSION == "vina_gnina_comparison_adapter_v1"
        and tuple(_COMPARISON_ENGINE_IDS) == ("vina", "gnina")
        and all(column in fields for column in ("vina_score", "gnina_score", "comparison_score_source"))
        and bool(_COMPARISON_ADAPTER_CLAIM_BOUNDARY)
    )
    vina_gnina_comparison_adapter_score_evidence_ready = (
        comparison_adapter_status == "vina_gnina_comparison_adapter_ready"
        and all(
            bool(comparison_metric_payloads.get(engine_id, {}).get("same_input_row_count_match"))
            for engine_id in _COMPARISON_ENGINE_IDS
        )
    )
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})

    summary = {
        "packet_type": "pdbbind_casf_pose_affinity_results",
        "suite_id": "pdbbind_casf_pose_affinity",
        "status": "pdbbind_casf_pose_affinity_results_ready" if not blockers else "blocked_pdbbind_casf_pose_affinity_results",
        "pass": not blockers,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "dataset_artifact": str(dataset),
        "data_5_sdf_dir": str(data_dir),
        "pose_count": len(rows),
        "replay_pose_count": len(replay_rows),
        "generated_pose_smoke_row_count": len(generated_pose_rows),
        "scored_pose_count": len(scored_rows),
        "posebusters_check_schema_version": _POSEBUSTERS_CHECK_SCHEMA_VERSION,
        "posebusters_claim_boundary": _POSEBUSTERS_CLAIM_BOUNDARY,
        "posebusters_assessed_pose_count": len(posebusters_assessed_rows),
        "posebusters_valid_count": posebusters_valid_count,
        "posebusters_valid_rate": posebusters_valid_rate,
        "posebusters_style_validity_checks_ready": posebusters_style_validity_checks_ready,
        "pose_success_count": pose_success_count,
        "pose_success_rate": complex_success_rate,
        "pose_row_success_rate": pose_success_rate,
        "symmetry_aware_ligand_rmsd_ready": symmetry_aware_ligand_rmsd_ready,
        "symmetry_aware_ligand_rmsd_coverage": symmetry_aware_ligand_rmsd_coverage,
        "symmetry_aware_ligand_rmsd_method": "rdkit_self_substructure_automorphism_no_ligand_alignment",
        "top1_mean_rmsd_A": gold_metrics.top1_mean_rmsd_a,
        "top5_best_mean_rmsd_A": gold_metrics.top5_best_mean_rmsd_a,
        "top1_pose_success_rate": gold_metrics.top1_pose_success_rate,
        "top5_pose_success_rate": gold_metrics.top5_pose_success_rate,
        "ranking_spearman": gold_metrics.ranking_spearman,
        "pr_auc": gold_metrics.pr_auc,
        "topk_hit_rate": gold_metrics.topk_hit_rate,
        "decoy_rejection_rate": gold_metrics.decoy_rejection_rate,
        "baseline_ranking_spearman": gold_metrics.baseline_ranking_spearman,
        "refine_ranking_spearman_delta": gold_metrics.refine_ranking_spearman_delta,
        "refine_improvement_observed": gold_metrics.refine_improvement_observed,
        "heldout_complex_count": gold_metrics.heldout_complex_count,
        "chirality_failure_rate": gold_metrics.chirality_failure_rate,
        "tautomer_failure_rate": gold_metrics.tautomer_failure_rate,
        "protonation_failure_rate": gold_metrics.protonation_failure_rate,
        "chemistry_evidence_coverage": gold_metrics.chemistry_evidence_coverage,
        "abstention_precision": gold_metrics.abstention_precision,
        "mean_runtime_ms": gold_metrics.mean_runtime_ms,
        "peak_memory_mb": gold_metrics.peak_memory_mb,
        "gold_metric_schema_version": gold_metrics.schema_version,
        "gold_metric_status": gold_metrics.status,
        "gold_metric_blockers": list(gold_metrics.blockers),
        "comparison_adapter_schema_version": _COMPARISON_ADAPTER_SCHEMA_VERSION,
        "comparison_adapter_claim_boundary": _COMPARISON_ADAPTER_CLAIM_BOUNDARY,
        "vina_gnina_comparison_adapter_contract_ready": vina_gnina_comparison_adapter_contract_ready,
        "vina_gnina_comparison_adapter_score_evidence_ready": vina_gnina_comparison_adapter_score_evidence_ready,
        "vina_gnina_comparison_adapter_enabled": comparison_adapter_enabled,
        "vina_gnina_comparison_adapter_status": comparison_adapter_status,
        "vina_gnina_comparison_adapter_ready": comparison_adapter_status == "vina_gnina_comparison_adapter_ready",
        "vina_gnina_comparison_adapter_blockers": sorted(set(comparison_blockers)),
        "comparison_scores_csv": str(_resolve(comparison_scores_csv)) if comparison_scores_csv else "",
        "comparison_scores_sha256": _sha256_file(_resolve(comparison_scores_csv)) if comparison_scores_csv else "",
        "comparison_adapter_engine_ids": list(_COMPARISON_ENGINE_IDS),
        "comparison_adapter_same_input_row_count_match": (
            all(
                bool(comparison_metric_payloads.get(engine_id, {}).get("same_input_row_count_match"))
                for engine_id in _COMPARISON_ENGINE_IDS
            )
            if comparison_adapter_enabled
            else False
        ),
        "comparison_adapter_metrics": comparison_metric_payloads,
        "vina_comparison_status": comparison_metric_payloads.get("vina", {}).get(
            "status",
            "vina_comparison_adapter_not_requested",
        ),
        "vina_comparison_score_count": int(comparison_metric_payloads.get("vina", {}).get("score_count") or 0),
        "vina_comparison_missing_score_count": int(
            comparison_metric_payloads.get("vina", {}).get("missing_score_count") or 0
        ),
        "vina_comparison_ranking_spearman": comparison_metric_payloads.get("vina", {}).get("ranking_spearman"),
        "vina_comparison_pr_auc": comparison_metric_payloads.get("vina", {}).get("pr_auc"),
        "vina_comparison_topk_hit_rate": comparison_metric_payloads.get("vina", {}).get("topk_hit_rate"),
        "vina_comparison_decoy_rejection_rate": comparison_metric_payloads.get("vina", {}).get("decoy_rejection_rate"),
        "vina_comparison_blockers": comparison_metric_payloads.get("vina", {}).get("blockers", []),
        "gnina_comparison_status": comparison_metric_payloads.get("gnina", {}).get(
            "status",
            "gnina_comparison_adapter_not_requested",
        ),
        "gnina_comparison_score_count": int(comparison_metric_payloads.get("gnina", {}).get("score_count") or 0),
        "gnina_comparison_missing_score_count": int(
            comparison_metric_payloads.get("gnina", {}).get("missing_score_count") or 0
        ),
        "gnina_comparison_ranking_spearman": comparison_metric_payloads.get("gnina", {}).get("ranking_spearman"),
        "gnina_comparison_pr_auc": comparison_metric_payloads.get("gnina", {}).get("pr_auc"),
        "gnina_comparison_topk_hit_rate": comparison_metric_payloads.get("gnina", {}).get("topk_hit_rate"),
        "gnina_comparison_decoy_rejection_rate": comparison_metric_payloads.get("gnina", {}).get("decoy_rejection_rate"),
        "gnina_comparison_blockers": comparison_metric_payloads.get("gnina", {}).get("blockers", []),
        "gold_metadata_csv": str(_resolve(args.gold_metadata_csv)) if _text(getattr(args, "gold_metadata_csv", "")) else "",
        "pose_id_allowlist_csv": (
            str(_resolve(args.pose_id_allowlist_csv))
            if _text(getattr(args, "pose_id_allowlist_csv", ""))
            else ""
        ),
        "pose_id_allowlist_count": len(pose_id_allowlist),
        "subset_identity": subset_identity,
        "subset_identity_schema_version": subset_identity["schema_version"],
        "subset_identity_sha256": subset_identity["subset_identity_sha256"],
        "subset_pose_file_names": list(subset_identity["pose_file_names"]),
        "subset_reference_file_names": list(subset_identity["reference_file_names"]),
        "subset_gold_metadata_sha256": subset_identity["gold_metadata_sha256"],
        "pose_rmsd_method": "rdkit_self_substructure_automorphism_no_ligand_alignment",
        "runtime_metric_source": "builder_wall_clock_perf_counter",
        "peak_memory_metric_source": "builder_tracemalloc_peak",
        "complex_count": len(by_complex),
        "complex_pose_success_count": complex_success_count,
        "complex_pose_success_rate": complex_success_rate,
        "primary_metric": "pose_success_rate",
        "primary_metric_value": complex_success_rate,
        "primary_metric_threshold": primary_threshold,
        "pose_success_rmsd_threshold_A": threshold,
        "out_csv": str(out_csv),
        "external_state_mutated": False,
        "download_executed": False,
        "prediction_generation_enabled": generate_poses,
        "generated_pose_smoke_enabled": generate_poses,
        "generated_pose_generation_source": _GENERATED_POSE_GENERATION_SOURCE if generate_poses else "",
        "generated_pose_generation_seed": generation_seed if generate_poses else "",
        "generated_pose_count_per_complex": generated_pose_count if generate_poses else "",
        "generated_pose_claim_boundary": _GENERATED_POSE_CLAIM_BOUNDARY if generate_poses else "",
        "claim_boundary": (
            _GENERATED_POSE_CLAIM_BOUNDARY
            if generate_poses
            else _REPLAY_CLAIM_BOUNDARY
        ),
        "next_required_step": (
            "Fingerprint this result CSV, build the suite scorecard, then refresh public benchmark gates."
            if rows
            else "Repair local CASF pose files, then rebuild these results."
        ),
    }
    payload = {"summary": summary, "rows": rows[:20]}
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(
        "\n".join(
            [
                "# PDBbind/CASF Pose Affinity Results",
                "",
                f"- status: `{summary['status']}`",
                f"- pose_count: `{summary['pose_count']}`",
                f"- pose_success_rate: `{summary['pose_success_rate']}`",
                f"- threshold: `{summary['primary_metric_threshold']}`",
                f"- vina_gnina_comparison_adapter_status: `{summary['vina_gnina_comparison_adapter_status']}`",
                f"- out_csv: `{out_csv}`",
                "",
                "## Claim Boundary",
                "",
                summary["claim_boundary"],
                "",
            ]
        ),
        encoding="utf-8",
    )
    return payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build PDBbind/CASF local pose RMSD proxy results from RDKit pickle files.")
    parser.add_argument("--dataset-artifact", default="data/public_benchmarks/pdbbind_casf_pose_affinity")
    parser.add_argument("--max-poses", type=int, default=0)
    parser.add_argument("--threshold", type=float, default=0.35)
    parser.add_argument("--pose-success-rmsd-a", type=float, default=2.0)
    parser.add_argument("--gold-metadata-csv", default="")
    parser.add_argument("--pose-id-allowlist-csv", default="")
    parser.add_argument("--comparison-scores-csv", default="")
    parser.add_argument("--vina-gnina-comparison-csv", default="")
    parser.add_argument("--out-csv", default="runs/pdbbind_casf_pose_affinity_benchmark_results_current.csv")
    parser.add_argument("--out-json", default="runs/pdbbind_casf_pose_affinity_results_current.json")
    parser.add_argument("--out-md", default="runs/pdbbind_casf_pose_affinity_results_current.md")
    parser.add_argument("--generate-poses", action="store_true")
    parser.add_argument("--generate-poses-seed", type=int, default=42)
    parser.add_argument("--generate-poses-count", type=int, default=1)
    parser.add_argument("--generate-poses-max-complexes", type=int, default=2)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    build_results(parse_args(argv))


if __name__ == "__main__":
    main()
