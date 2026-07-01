#!/usr/bin/env python3
"""Collect bounded PocketMD Lite atomized local-min/H-bond/clash metrics.

This builder consumes ligand atom-frame recovery outputs that already contain
both ligand atom frames and protein atom frames. It runs a small, bounded
OpenMM custom-force local minimization over sampled top-k frames and writes a
separate metric NPZ per ready row. The output is intentionally provenance-rich:
it records the bounded/custom-force scope and never mutates the canonical
PocketMD Lite candidate CSV.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import re
from pathlib import Path
from typing import Any

import numpy as np

from betelgeuze_product.pocketmd_lite_contract import LOCAL_MIN_SURVIVAL_RMSD_A
from tools.gpcr_replay import build_gpcr_drd2_local_minimization_survival as survival_mod

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_INPUT_CSV = "runs/pocketmd_lite_metric_collection_input_pack_current.csv"
DEFAULT_RECOVERY_JSON = "runs/pocketmd_lite_ligand_atom_frame_recovery_current.json"
DEFAULT_OUT_ROOT = "runs/pocketmd_lite_bounded_metric_collector_current"
DEFAULT_OUT_JSON = "runs/pocketmd_lite_bounded_metric_collector_current.json"
DEFAULT_OUT_MD = "runs/pocketmd_lite_bounded_metric_collector_current.md"
DEFAULT_OUT_CSV = "runs/pocketmd_lite_bounded_metric_collector_current.csv"

PACKET_TYPE = "pocketmd_lite_bounded_metric_collector"
SCHEMA_VERSION = "pocketmd_lite_bounded_metric_collector_v1"
METRIC_SOURCE = "openmm_custom_bounded_atomized_candidate"

DEFAULT_MAX_FRAMES_PER_ROW = 8
DEFAULT_OPENMM_MAX_ITERATIONS = 50
DEFAULT_CONTACT_CUTOFF_A = 6.0
DEFAULT_HBOND_DISTANCE_CUTOFF_A = 3.6
DEFAULT_CLASH_CUTOFF_A = 2.1

CLAIM_BOUNDARY = (
    "PocketMD Lite bounded metric collector only. It computes local-min RMSD, contact persistence, "
    "distance-only H-bond persistence, and clash relief from recovered atomized top-k inputs using the repo's "
    "bounded OpenMM custom-force path. It does not claim a fully parameterized protein-ligand force field, does "
    "not mutate the canonical candidate CSV, does not promote broad/commercial hard gates, and does not mutate "
    "external state."
)

LOCAL_FLAGS = {
    "execution_enabled": True,
    "external_state_mutated": False,
    "refinement_execution_enabled": True,
    "candidate_csv_update_allowed": False,
    "claim_promotion_allowed": False,
    "full_forcefield_parameterization_claimed": False,
}

CSV_COLUMNS = [
    "entry_id",
    "target",
    "ligand_id",
    "status",
    "source_npz",
    "metric_npz",
    "frame_count",
    "sampled_frame_count",
    "minimized_frame_count",
    "ligand_atom_count",
    "protein_atom_count",
    "local_min_ligand_rmsd_a",
    "local_min_survival_fraction",
    "contact_persistence",
    "hbond_persistence",
    "initial_clash_count",
    "clash_count",
    "clash_relief_count",
    "claim_grade_metric_ready",
    "metric_source",
    "blockers",
    "recommended_next_local_action",
    "execution_enabled",
    "external_state_mutated",
    "refinement_execution_enabled",
    "candidate_csv_update_allowed",
    "claim_promotion_allowed",
    "full_forcefield_parameterization_claimed",
]


def _resolve(path_like: str | Path) -> Path:
    path = Path(str(path_like)).expanduser()
    return path if path.is_absolute() else ROOT / path


def _display(path_like: str | Path) -> str:
    text = _text(path_like)
    if not text:
        return ""
    path = Path(text)
    if path.is_absolute():
        try:
            return str(path.relative_to(ROOT))
        except ValueError:
            return str(path)
    return text


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).lower() in {"1", "true", "yes", "y", "on"}


def _read_csv(path_like: str | Path) -> list[dict[str, Any]]:
    path = _resolve(path_like)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _recovery_rows_by_entry(path_like: str | Path) -> dict[str, dict[str, Any]]:
    payload = _read_json(path_like)
    rows = payload.get("rows")
    if not isinstance(rows, list):
        return {}
    return {_text(row.get("entry_id")): row for row in rows if isinstance(row, dict) and _text(row.get("entry_id"))}


def _load_npz_arrays(path_like: str | Path) -> tuple[dict[str, np.ndarray] | None, str]:
    path = _resolve(path_like)
    if not _text(path_like) or not path.exists():
        return None, "source_npz_missing"
    try:
        with np.load(str(path), allow_pickle=False) as payload:
            return {key: np.asarray(payload[key]) for key in payload.files}, "ok"
    except Exception as exc:
        return None, f"source_npz_unreadable:{type(exc).__name__}"


def _frames(arrays: dict[str, np.ndarray], *keys: str) -> np.ndarray:
    for key in keys:
        value = np.asarray(arrays.get(key, np.zeros((0, 0, 3), dtype=np.float32)), dtype=np.float32)
        if value.ndim == 3 and value.shape[0] > 0 and value.shape[1] > 0 and value.shape[2] == 3:
            return value
    return np.zeros((0, 0, 3), dtype=np.float32)


def _safe_name(entry_id: str, target: str, ligand_id: str) -> str:
    base = entry_id or f"{target}:{ligand_id}"
    base = base.replace(":", "__")
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", base).strip("_") or "pocketmd_lite_entry"


def _pair_distances(ligand_coords: np.ndarray, protein_coords: np.ndarray) -> np.ndarray:
    ligand = np.asarray(ligand_coords, dtype=np.float64)
    protein = np.asarray(protein_coords, dtype=np.float64)
    if ligand.size == 0 or protein.size == 0:
        return np.zeros((0, 0), dtype=np.float64)
    return np.linalg.norm(ligand[:, None, :] - protein[None, :, :], axis=2)


def _count_pairs_under(ligand_coords: np.ndarray, protein_coords: np.ndarray, cutoff_a: float) -> int:
    distances = _pair_distances(ligand_coords, protein_coords)
    return int(np.sum(distances < float(cutoff_a))) if distances.size else 0


def _min_distance(ligand_coords: np.ndarray, protein_coords: np.ndarray) -> float | None:
    distances = _pair_distances(ligand_coords, protein_coords)
    return float(np.min(distances)) if distances.size else None


def _hbond_distance_hit(
    ligand_coords: np.ndarray,
    protein_coords: np.ndarray,
    ligand_atomic_numbers: list[int],
    cutoff_a: float,
) -> bool:
    hetero_indices = [
        idx
        for idx, atomic_number in enumerate(ligand_atomic_numbers)
        if int(atomic_number) in {7, 8, 15, 16}
    ]
    if not hetero_indices:
        return False
    ligand_hetero = np.asarray(ligand_coords, dtype=np.float64)[hetero_indices]
    min_distance = _min_distance(ligand_hetero, protein_coords)
    return bool(min_distance is not None and min_distance <= float(cutoff_a))


def _normal_p90(values: list[float]) -> float | None:
    if not values:
        return None
    return float(np.percentile(np.asarray(values, dtype=np.float64), 90))


def _base_row(source_row: dict[str, Any], recovery_row: dict[str, Any] | None, out_root: Path) -> dict[str, Any]:
    entry_id = _text(source_row.get("entry_id"))
    target = _text(source_row.get("target"))
    ligand_id = _text(source_row.get("ligand_id"))
    metric_npz = out_root / f"{_safe_name(entry_id, target, ligand_id)}__bounded_metrics.npz"
    return {
        "entry_id": entry_id,
        "target": target,
        "ligand_id": ligand_id,
        "status": "blocked_pocketmd_lite_bounded_metric_collector",
        "source_npz": _display(recovery_row.get("out_npz")) if recovery_row else "",
        "metric_npz": _display(metric_npz),
        "frame_count": 0,
        "sampled_frame_count": 0,
        "minimized_frame_count": 0,
        "ligand_atom_count": 0,
        "protein_atom_count": 0,
        "local_min_ligand_rmsd_a": None,
        "local_min_survival_fraction": None,
        "contact_persistence": None,
        "hbond_persistence": None,
        "initial_clash_count": None,
        "clash_count": None,
        "clash_relief_count": None,
        "claim_grade_metric_ready": False,
        "metric_source": "",
        "blockers": [],
        "recommended_next_local_action": "run_ligand_atom_frame_recovery_for_collection_ready_input",
        **LOCAL_FLAGS,
    }


def _collect_row(
    source_row: dict[str, Any],
    recovery_row: dict[str, Any] | None,
    *,
    out_root: Path,
    max_frames_per_row: int,
    openmm_max_iterations: int,
    contact_cutoff_a: float,
    hbond_distance_cutoff_a: float,
    clash_cutoff_a: float,
) -> dict[str, Any]:
    base = _base_row(source_row, recovery_row, out_root)
    if recovery_row is None:
        return {**base, "blockers": ["ligand_atom_frame_recovery_row_missing"]}
    if recovery_row.get("collection_input_candidate_ready") is not True:
        blockers = list(recovery_row.get("blockers") or ["recovered_collection_input_not_ready"])
        return {
            **base,
            "source_npz": _display(recovery_row.get("out_npz")),
            "blockers": blockers,
            "recommended_next_local_action": "recover_or_generate_protein_atom_frames_then_rerun_bounded_metric_collector",
        }
    arrays, reason = _load_npz_arrays(recovery_row.get("out_npz", ""))
    if arrays is None:
        return {**base, "blockers": [reason], "recommended_next_local_action": "restore_recovered_atomized_npz"}

    ligand_atom_frames = _frames(arrays, "ligand_atom_frames", "ligand_heavy_atom_frames", "atomized_ligand_frames")
    protein_atom_frames = _frames(arrays, "protein_atom_frames")
    ligand_frames = _frames(arrays, "ligand_frames")
    blockers: list[str] = []
    if ligand_atom_frames.shape[1] <= 2:
        blockers.append("ligand_atom_frames_missing_or_not_atomized")
    if protein_atom_frames.shape[1] <= 0:
        blockers.append("protein_atom_frames_missing")
    if ligand_frames.shape[0] <= 0:
        blockers.append("ligand_frames_missing")
    if blockers:
        return {**base, "blockers": blockers}
    if survival_mod.mm is None:
        return {**base, "blockers": ["openmm_unavailable"]}

    frame_count = int(min(ligand_atom_frames.shape[0], protein_atom_frames.shape[0], ligand_frames.shape[0]))
    if frame_count <= 0:
        return {**base, "blockers": ["atomized_frame_count_zero"]}
    if frame_count < int(ligand_atom_frames.shape[0]):
        blockers.append("frame_count_truncated_to_common_atomized_frames")

    ligand_atom_count = int(ligand_atom_frames.shape[1])
    protein_atom_count = int(protein_atom_frames.shape[1])
    smiles = _text(source_row.get("ligand_smiles") or source_row.get("smiles"))
    ligand_atomic_numbers, ligand_type_blockers = survival_mod._ligand_atomic_numbers(
        arrays,
        smiles,
        ligand_atom_count,
    )
    protein_atomic_numbers, protein_type_blockers = survival_mod._protein_atomic_numbers(
        arrays,
        protein_atom_count,
    )
    blockers.extend(ligand_type_blockers)
    blockers.extend(protein_type_blockers)
    blockers.extend(
        [
            "full_protein_ligand_forcefield_parameterization_unavailable",
            "custom_force_minimizer_not_equivalent_to_full_protein_ligand_forcefield",
            "protein_coordinates_restrained_to_input_frame",
            "hbond_persistence_distance_only_no_angle_or_donor_acceptor_typing",
        ]
    )

    sampled_indices = survival_mod._frame_indices(frame_count, int(max_frames_per_row))
    rmsds: list[float] = []
    contact_hits: list[bool] = []
    hbond_hits: list[bool] = []
    initial_clashes: list[int] = []
    final_clashes: list[int] = []
    energy_before_values: list[float] = []
    energy_after_values: list[float] = []
    minimized_frames: list[np.ndarray] = []
    frame_failures: list[dict[str, Any]] = []

    for frame_idx in sampled_indices:
        ligand_coords = np.asarray(ligand_atom_frames[frame_idx], dtype=np.float64)
        protein_coords = np.asarray(protein_atom_frames[frame_idx], dtype=np.float64)
        if not np.isfinite(ligand_coords).all():
            frame_failures.append({"frame_index": int(frame_idx), "reason": "ligand_atom_frame_nonfinite"})
            continue
        if not np.isfinite(protein_coords).all():
            frame_failures.append({"frame_index": int(frame_idx), "reason": "protein_atom_frame_nonfinite"})
            continue
        result = survival_mod._openmm_minimize_frame(
            ligand_coords_A=ligand_coords,
            protein_coords_A=protein_coords,
            ligand_atomic_numbers=ligand_atomic_numbers,
            protein_atomic_numbers=protein_atomic_numbers,
            basic_indices=[],
            anchor_indices=[],
            max_iterations=int(openmm_max_iterations),
            tolerance_kj_mol_nm=10.0,
            ligand_pose_restraint_k_kj_mol_nm2=survival_mod.DEFAULT_LIGAND_POSE_RESTRAINT_K_KJ_MOL_NM2,
            ligand_internal_k_kj_mol_nm2=2500.0,
            protein_restraint_k_kj_mol_nm2=50000.0,
            salt_bridge_k_kj_mol_nm2=0.0,
            salt_bridge_distance_A=3.2,
            vdw_epsilon_kj_mol=0.05,
            vdw_cutoff_nm=1.2,
            softcore_nm=0.02,
        )
        if not result.get("ok"):
            frame_failures.append(
                {"frame_index": int(frame_idx), "reason": str(result.get("reason") or "openmm_minimization_failed")}
            )
            continue
        minimized = np.asarray(result.get("minimized_ligand_coords_A"), dtype=np.float64)
        if minimized.shape != ligand_coords.shape or not np.isfinite(minimized).all():
            frame_failures.append({"frame_index": int(frame_idx), "reason": "minimized_ligand_frame_invalid"})
            continue
        initial_clashes.append(_count_pairs_under(ligand_coords, protein_coords, clash_cutoff_a))
        final_clashes.append(_count_pairs_under(minimized, protein_coords, clash_cutoff_a))
        min_distance = _min_distance(minimized, protein_coords)
        contact_hits.append(bool(min_distance is not None and min_distance <= float(contact_cutoff_a)))
        hbond_hits.append(
            _hbond_distance_hit(
                minimized,
                protein_coords,
                ligand_atomic_numbers,
                hbond_distance_cutoff_a,
            )
        )
        rmsds.append(float(survival_mod._absolute_rmsd_A(ligand_coords, minimized)))
        energy_before = survival_mod._float(result.get("energy_before_kj_mol"))
        energy_after = survival_mod._float(result.get("energy_after_kj_mol"))
        if energy_before is not None:
            energy_before_values.append(float(energy_before))
        if energy_after is not None:
            energy_after_values.append(float(energy_after))
        minimized_frames.append(minimized.astype(np.float32, copy=False))

    attempted = int(len(sampled_indices))
    minimized_count = int(len(rmsds))
    if frame_failures:
        blockers.append("one_or_more_frame_minimizations_failed")
    if minimized_count <= 0:
        return {
            **base,
            "frame_count": frame_count,
            "sampled_frame_count": attempted,
            "ligand_atom_count": ligand_atom_count,
            "protein_atom_count": protein_atom_count,
            "blockers": sorted(set(blockers + ["local_minimization_unmeasured"])),
            "recommended_next_local_action": "inspect_openmm_failures_or_reduce_sampled_frames_then_rerun_collector",
        }

    local_min_rmsd = _normal_p90(rmsds)
    survival_fraction = float(sum(value <= LOCAL_MIN_SURVIVAL_RMSD_A for value in rmsds) / attempted) if attempted else None
    contact_persistence = float(np.mean(contact_hits)) if contact_hits else None
    hbond_persistence = float(np.mean(hbond_hits)) if hbond_hits else None
    initial_clash_count = int(max(initial_clashes)) if initial_clashes else None
    clash_count = int(max(final_clashes)) if final_clashes else None
    clash_relief_count = (
        None
        if initial_clash_count is None or clash_count is None
        else int(max(initial_clash_count - clash_count, 0))
    )
    metric_ready = bool(attempted > 0 and minimized_count == attempted and local_min_rmsd is not None)
    metric_npz = _resolve(base["metric_npz"])
    metric_npz.parent.mkdir(parents=True, exist_ok=True)

    output_arrays: dict[str, Any] = dict(arrays)
    output_arrays.update(
        {
            "pocketmd_lite_bounded_metric_collector_schema_version": np.asarray(SCHEMA_VERSION),
            "pocketmd_lite_metric_source": np.asarray(METRIC_SOURCE),
            "pocketmd_lite_metric_source_claim_boundary": np.asarray(CLAIM_BOUNDARY),
            "pocketmd_lite_bounded_metric_collector_frame_indices": np.asarray(sampled_indices, dtype=np.int32),
            "pocketmd_lite_bounded_metric_collector_minimized_ligand_atom_frames": np.asarray(
                minimized_frames,
                dtype=np.float32,
            ),
            "local_min_survival_fraction": np.asarray(survival_fraction, dtype=np.float32),
            "pocketmd_lite_bounded_local_min_ligand_rmsd_a": np.asarray(local_min_rmsd, dtype=np.float32),
            "pocketmd_lite_bounded_contact_persistence": np.asarray(contact_persistence, dtype=np.float32),
            "pocketmd_lite_bounded_hbond_persistence": np.asarray(hbond_persistence, dtype=np.float32),
            "pocketmd_lite_bounded_initial_clash_count": np.asarray(initial_clash_count, dtype=np.int32),
            "pocketmd_lite_bounded_clash_count": np.asarray(clash_count, dtype=np.int32),
            "pocketmd_lite_bounded_clash_relief_count": np.asarray(clash_relief_count, dtype=np.int32),
            "pocketmd_lite_bounded_metric_ready": np.asarray(metric_ready),
            "full_forcefield_parameterization_claimed": np.asarray(False),
            "hbond_persistence_distance_only": np.asarray(True),
            "frame_minimization_failure_count": np.asarray(len(frame_failures), dtype=np.int32),
            "energy_before_kj_mol_median": np.asarray(
                np.median(energy_before_values) if energy_before_values else np.nan,
                dtype=np.float32,
            ),
            "energy_after_kj_mol_median": np.asarray(
                np.median(energy_after_values) if energy_after_values else np.nan,
                dtype=np.float32,
            ),
        }
    )
    if metric_ready:
        output_arrays.update(
            {
                "local_min_ligand_rmsd_a": np.asarray(local_min_rmsd, dtype=np.float32),
                "contact_persistence": np.asarray(contact_persistence, dtype=np.float32),
                "hbond_persistence": np.asarray(hbond_persistence, dtype=np.float32),
                "initial_clash_count": np.asarray(initial_clash_count, dtype=np.int32),
                "pre_refine_clash_count": np.asarray(initial_clash_count, dtype=np.int32),
                "clash_count": np.asarray(clash_count, dtype=np.int32),
                "clash_relief_count": np.asarray(clash_relief_count, dtype=np.int32),
            }
        )
    np.savez(metric_npz, **output_arrays)

    return {
        **base,
        "status": (
            "pocketmd_lite_bounded_metric_collector_metric_ready"
            if metric_ready
            else "blocked_pocketmd_lite_bounded_metric_collector_partial_minimization"
        ),
        "frame_count": frame_count,
        "sampled_frame_count": attempted,
        "minimized_frame_count": minimized_count,
        "ligand_atom_count": ligand_atom_count,
        "protein_atom_count": protein_atom_count,
        "local_min_ligand_rmsd_a": local_min_rmsd,
        "local_min_survival_fraction": survival_fraction,
        "contact_persistence": contact_persistence,
        "hbond_persistence": hbond_persistence,
        "initial_clash_count": initial_clash_count,
        "clash_count": clash_count,
        "clash_relief_count": clash_relief_count,
        "claim_grade_metric_ready": metric_ready,
        "metric_source": METRIC_SOURCE,
        "blockers": sorted(set(blockers)),
        "frame_failures": frame_failures,
        "recommended_next_local_action": (
            "extract_bounded_exact_metric_fields_into_probe_and_candidate_fill_preview"
            if metric_ready
            else "inspect_openmm_failures_or_reduce_sampled_frames_then_rerun_collector"
        ),
    }


def build_pocketmd_lite_bounded_metric_collector(
    *,
    input_csv: str | Path = DEFAULT_INPUT_CSV,
    recovery_json: str | Path = DEFAULT_RECOVERY_JSON,
    out_root: str | Path = DEFAULT_OUT_ROOT,
    max_frames_per_row: int = DEFAULT_MAX_FRAMES_PER_ROW,
    openmm_max_iterations: int = DEFAULT_OPENMM_MAX_ITERATIONS,
    contact_cutoff_a: float = DEFAULT_CONTACT_CUTOFF_A,
    hbond_distance_cutoff_a: float = DEFAULT_HBOND_DISTANCE_CUTOFF_A,
    clash_cutoff_a: float = DEFAULT_CLASH_CUTOFF_A,
) -> dict[str, Any]:
    input_path = _resolve(input_csv)
    recovery_path = _resolve(recovery_json)
    out_root_path = _resolve(out_root)
    source_rows = [row for row in _read_csv(input_path) if _bool(row.get("collection_input_ready"))]
    recovery_rows = _recovery_rows_by_entry(recovery_path)
    rows = [
        _collect_row(
            row,
            recovery_rows.get(_text(row.get("entry_id"))),
            out_root=out_root_path,
            max_frames_per_row=max_frames_per_row,
            openmm_max_iterations=openmm_max_iterations,
            contact_cutoff_a=contact_cutoff_a,
            hbond_distance_cutoff_a=hbond_distance_cutoff_a,
            clash_cutoff_a=clash_cutoff_a,
        )
        for row in source_rows
    ]

    collection_input_candidate_count = sum(
        1 for row in source_rows if recovery_rows.get(_text(row.get("entry_id")), {}).get("collection_input_candidate_ready") is True
    )
    measured_count = sum(1 for row in rows if row.get("claim_grade_metric_ready") is True)
    blocked_count = len(rows) - measured_count
    if rows and measured_count == len(rows):
        status = "pocketmd_lite_bounded_metric_collector_ready"
    elif measured_count:
        status = "pocketmd_lite_bounded_metric_collector_partial_ready"
    elif rows:
        status = "blocked_pocketmd_lite_bounded_metric_collector"
    else:
        status = "blocked_pocketmd_lite_bounded_metric_collector_no_inputs"

    summary = {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": status,
        "input_csv": _display(input_path),
        "recovery_json": _display(recovery_path),
        "out_root": _display(out_root_path),
        "candidate_count": len(rows),
        "collection_input_candidate_ready_count": collection_input_candidate_count,
        "measured_metric_row_count": measured_count,
        "blocked_metric_row_count": blocked_count,
        "exact_metric_npz_count": measured_count,
        "openmm_available": survival_mod.mm is not None,
        "metric_source": METRIC_SOURCE,
        "max_frames_per_row": int(max_frames_per_row),
        "openmm_max_iterations": int(openmm_max_iterations),
        "contact_cutoff_a": float(contact_cutoff_a),
        "hbond_distance_cutoff_a": float(hbond_distance_cutoff_a),
        "clash_cutoff_a": float(clash_cutoff_a),
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Run the metric collection probe, candidate fill preview, and PocketMD Lite report against the preview CSV."
            if rows and measured_count == len(rows)
            else "Run the probe/fill preview for measured rows and recover protein atom frames for remaining top-k rows."
            if measured_count
            else "Recover atomized ligand/protein frame inputs, then rerun the bounded metric collector."
        ),
        **LOCAL_FLAGS,
    }
    return {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "summary": summary,
        "rows": rows,
        "claim_boundary": CLAIM_BOUNDARY,
    }


def _jsonable(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return _jsonable(value.tolist())
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _fmt(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, float):
        return f"{value:.6g}"
    if isinstance(value, list):
        return ";".join(str(item) for item in value)
    return str(value)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_jsonable(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: _fmt(row.get(column)) for column in CSV_COLUMNS})


def _render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# PocketMD Lite Bounded Metric Collector",
        "",
        f"- status: `{summary['status']}`",
        f"- candidate_count: `{summary['candidate_count']}`",
        f"- collection_input_candidate_ready_count: `{summary['collection_input_candidate_ready_count']}`",
        f"- measured_metric_row_count: `{summary['measured_metric_row_count']}`",
        f"- blocked_metric_row_count: `{summary['blocked_metric_row_count']}`",
        f"- metric_source: `{summary['metric_source']}`",
        "",
        "| entry | status | frames | local-min p90 A | contact | hbond | clash relief | action |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            "| `{entry}` | `{status}` | {frames} | `{rmsd}` | `{contact}` | `{hbond}` | `{relief}` | `{action}` |".format(
                entry=row["entry_id"],
                status=row["status"],
                frames=row["sampled_frame_count"],
                rmsd=_fmt(row["local_min_ligand_rmsd_a"]),
                contact=_fmt(row["contact_persistence"]),
                hbond=_fmt(row["hbond_persistence"]),
                relief=_fmt(row["clash_relief_count"]),
                action=row["recommended_next_local_action"],
            )
        )
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-csv", default=DEFAULT_INPUT_CSV)
    parser.add_argument("--recovery-json", default=DEFAULT_RECOVERY_JSON)
    parser.add_argument("--out-root", default=DEFAULT_OUT_ROOT)
    parser.add_argument("--max-frames-per-row", type=int, default=DEFAULT_MAX_FRAMES_PER_ROW)
    parser.add_argument("--openmm-max-iterations", type=int, default=DEFAULT_OPENMM_MAX_ITERATIONS)
    parser.add_argument("--contact-cutoff-a", type=float, default=DEFAULT_CONTACT_CUTOFF_A)
    parser.add_argument("--hbond-distance-cutoff-a", type=float, default=DEFAULT_HBOND_DISTANCE_CUTOFF_A)
    parser.add_argument("--clash-cutoff-a", type=float, default=DEFAULT_CLASH_CUTOFF_A)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    args = parser.parse_args(argv)

    payload = build_pocketmd_lite_bounded_metric_collector(
        input_csv=args.input_csv,
        recovery_json=args.recovery_json,
        out_root=args.out_root,
        max_frames_per_row=args.max_frames_per_row,
        openmm_max_iterations=args.openmm_max_iterations,
        contact_cutoff_a=args.contact_cutoff_a,
        hbond_distance_cutoff_a=args.hbond_distance_cutoff_a,
        clash_cutoff_a=args.clash_cutoff_a,
    )
    out_json = _resolve(args.out_json)
    out_md = _resolve(args.out_md)
    out_csv = _resolve(args.out_csv)
    _write_json(out_json, payload)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(_render_markdown(payload), encoding="utf-8")
    _write_csv(out_csv, payload["rows"])
    print(json.dumps(_jsonable(payload["summary"]), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
