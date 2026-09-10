"""Explicit rigid ligand candidates through existing prepared-state V2 physics.

Preparation reuse is local to one request. Source bytes and canonical mutation
guards remain checked; every accepted candidate receives a fresh calculation.
"""

from __future__ import annotations

from collections import Counter
import copy
from dataclasses import replace
import hashlib
import math
from pathlib import Path
import time

import torch

from betelgeuze_engine.product.prepared_gromacs_input import (
    _read_source,
    load_prepared_gromacs_components,
)
from betelgeuze_engine.product.v2_cross_interaction import (
    evaluate_prepared_cross_interaction,
)
from betelgeuze_engine_v2.molecular import AllAtomSystem, canonical_system_sha256

SCHEMA = "prepared_rigid_pose_cross_request_v1"
MAX_POSES = 32
ROTATION_TOLERANCE = 1e-10
EVALUATION_FIELDS = {
    "pocket_center_angstrom",
    "pocket_radius_angstrom",
    "cutoff_angstrom",
    "switch_start_angstrom",
    "dielectric",
    "screening_kappa_per_angstrom",
}


def _number(value):
    if type(value) not in (float, int):
        raise ValueError("pose transform requires finite numeric values, not booleans")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("pose transform requires finite numeric values")
    return value


def _transform(pose):
    if (
        type(pose) is not dict
        or set(pose) != {"pose_id", "rotation_matrix", "translation_angstrom"}
        or type(pose["pose_id"]) is not str
        or not pose["pose_id"].strip()
    ):
        raise ValueError(
            "explicit pose_id, rotation_matrix and translation_angstrom required"
        )
    matrix, shift = pose["rotation_matrix"], pose["translation_angstrom"]
    if (
        type(matrix) is not list
        or len(matrix) != 3
        or any(type(row) is not list or len(row) != 3 for row in matrix)
        or type(shift) is not list
        or len(shift) != 3
    ):
        raise ValueError(
            "pose transform requires a 3x3 matrix and a three-coordinate translation"
        )
    rotation = torch.tensor(
        [[_number(v) for v in row] for row in matrix], dtype=torch.float64
    )
    translation = torch.tensor([_number(v) for v in shift], dtype=torch.float64)
    if (
        not torch.isfinite(rotation.T @ rotation).all()
        or (rotation.T @ rotation - torch.eye(3, dtype=torch.float64)).abs().max()
        > ROTATION_TOLERANCE
        or abs(float(torch.linalg.det(rotation)) - 1.0) > ROTATION_TOLERANCE
    ):
        raise ValueError(
            "proper orthonormal rotation required; reflection, scale and shear unsupported"
        )
    return rotation, translation


def _verify_sources(provenance):
    # Reuse the original loader's exact byte limits/hash/regular-file policy.
    for label, ref in provenance["sources"].items():
        _read_source(ref, label, {})


def _unavailable_geometry(reason, origin=None):
    return {
        "schema_version": "prepared_source_geometry_observation_v1",
        "status": "unavailable",
        "reason": reason,
        "groups": None,
        "coordinate_origin": origin,
        "physical_validity_assessed": False,
        "affects_score_or_admission": False,
    }


def _geometry(receptor, ligand, provenance, origin):
    started, cpu = time.perf_counter(), time.process_time()
    try:
        from betelgeuze_engine.product.prepared_source_geometry import (
            observe_prepared_source_geometry,
        )

        observation = observe_prepared_source_geometry(receptor, ligand, provenance)
        observation["coordinate_origin"] = origin
        return observation
    except Exception as exc:
        observation = _unavailable_geometry(
            "source_geometry_observation_failed", origin
        )
        observation.update(error_type=type(exc).__name__, detail=str(exc))
        observation["cost"] = {
            "wall_seconds": time.perf_counter() - started,
            "cpu_seconds": time.process_time() - cpu,
            "scope": "failed geometry observation attempt",
        }
        return observation


def evaluate_rigid_pose_request(request: dict) -> dict:
    """Retain one ledger row per pose; no docking search or active ranking."""
    if (
        type(request) is not dict
        or set(request)
        != {"schema_version", "prepared_input", "evaluation", "execution", "poses"}
        or request["schema_version"] != SCHEMA
        or type(request["poses"]) is not list
        or not 1 <= len(request["poses"]) <= MAX_POSES
    ):
        raise ValueError(
            "expected 1..32 poses under the explicit prepared rigid pose contract"
        )
    request = copy.deepcopy(request)
    rows, shared, cached = [], None, None
    preparation_attempts, preparations, reuse_hits, rechecks = 0, 0, 0, 0
    preparation_wall = 0.0
    execution_declaration = None
    ids = Counter(
        p.get("pose_id")
        for p in request["poses"]
        if type(p) is dict and type(p.get("pose_id")) is str
    )
    for index, pose in enumerate(request["poses"]):
        started, cpu = time.perf_counter(), time.process_time()
        pose_id = (
            pose.get("pose_id")
            if type(pose) is dict and type(pose.get("pose_id")) is str
            else None
        )
        row = {
            "request_index": index,
            "case_id": pose_id,
            "status": "failed",
            "evaluated_ligand_coordinates_angstrom": None,
            "evaluation_completed": False,
            "pose_geometry_observation": _unavailable_geometry("pose_not_constructed"),
        }
        try:
            rotation, translation = _transform(pose)
            if ids[pose_id] != 1:
                raise ValueError(
                    "duplicate pose_id; no duplicate is selected as authoritative"
                )
            execution = request["execution"]
            if (
                type(execution) is not dict
                or set(execution) != {"projection_partition", "preparation_reuse"}
                or execution["projection_partition"]
                not in ("source_order_v1", "spatial_median_v1")
                or execution["preparation_reuse"] not in ("request", "none")
            ):
                raise ValueError(
                    "explicit supported projection_partition and preparation_reuse required"
                )
            execution_declaration = dict(execution)
            if (
                type(request["evaluation"]) is not dict
                or set(request["evaluation"]) != EVALUATION_FIELDS
            ):
                raise ValueError(
                    "all cross-model and pocket parameters must be explicit"
                )
            if cached is None or execution["preparation_reuse"] == "none":
                preparation_attempts += 1
                load_started = time.perf_counter()
                try:
                    state = load_prepared_gromacs_components(request["prepared_input"])
                finally:
                    preparation_wall += time.perf_counter() - load_started
                preparations += 1
                if execution["preparation_reuse"] == "request":
                    cached = state
            else:
                state = cached
                reuse_hits += 1
            receptor, ligand, rp, lp, provenance = state
            _verify_sources(provenance)
            rechecks += 1
            AllAtomSystem.assert_integrity(receptor)
            AllAtomSystem.assert_integrity(ligand)
            parent = canonical_system_sha256(ligand)
            if shared is None:
                shared = {
                    "preparation_provenance": provenance,
                    "receptor_system_sha256": canonical_system_sha256(receptor),
                    "ligand_system_sha256": parent,
                    "source_receptor_coordinates_angstrom": receptor.coordinates[
                        0
                    ].tolist(),
                    "source_ligand_coordinates_angstrom": ligand.coordinates[
                        0
                    ].tolist(),
                    "source_geometry_observation": _geometry(
                        receptor, ligand, provenance, "supplied_preparation_unchanged"
                    ),
                }
            AllAtomSystem.assert_integrity(receptor)
            AllAtomSystem.assert_integrity(ligand)
            center = ligand.coordinates.mean(dim=1, keepdim=True)
            if torch.equal(rotation, torch.eye(3, dtype=torch.float64)):
                coordinates = ligand.coordinates + translation
            else:
                coordinates = (
                    (ligand.coordinates - center) @ rotation.T + center + translation
                )
            if not torch.isfinite(coordinates).all():
                raise ValueError("pose transform produced nonfinite coordinates")
            row["evaluated_ligand_coordinates_angstrom"] = coordinates[0].tolist()
            derivation = {
                "pose_id": pose_id,
                "rotation_matrix": rotation.tolist(),
                "translation_angstrom": translation.tolist(),
                "pivot_angstrom": center[0, 0].tolist(),
                "pivot_policy": "supplied_ligand_all_atom_centroid",
                "coordinate_origin": "computed_rigid_transform_of_supplied_preparation",
                "source_ligand_system_sha256": parent,
                "atom_order_and_chemical_state_unchanged": True,
                "hydrogen_positions_added": False,
            }
            row["pose_derivation"] = derivation
            candidate = replace(
                ligand,
                coordinates=coordinates,
                provenance=replace(
                    ligand.provenance,
                    operations=ligand.provenance.operations
                    + ("explicit_product_rigid_pose",),
                    parent_sha256=ligand.provenance.parent_sha256 + (parent,),
                    metadata={
                        **ligand.provenance.metadata,
                        "pose_derivation": derivation,
                    },
                ),
            )
            row["pose_geometry_observation"] = _geometry(
                receptor,
                candidate,
                provenance,
                "computed_rigid_transform_of_supplied_preparation",
            )
            AllAtomSystem.assert_integrity(receptor)
            AllAtomSystem.assert_integrity(ligand)
            AllAtomSystem.assert_integrity(candidate)
            declarations = dict(request["prepared_input"]["source_declarations"])
            declarations["prepared_state_id"] = (
                "derived-rigid-pose:" + pose_id + ":" + parent
            )
            result = evaluate_prepared_cross_interaction(
                receptor,
                candidate,
                copy.deepcopy(rp),
                copy.deepcopy(lp),
                source_declarations=declarations,
                **request["evaluation"],
                projection_partition=execution["projection_partition"],
            )
            row["evaluation_completed"] = True
            _verify_sources(provenance)
            rechecks += 1
            AllAtomSystem.assert_integrity(receptor)
            AllAtomSystem.assert_integrity(ligand)
            AllAtomSystem.assert_integrity(candidate)
            row.update(status="evaluated", result=result)
        except Exception as exc:
            row.update(error_type=type(exc).__name__, reason=str(exc))
        row["cost"] = {
            "wall_seconds": time.perf_counter() - started,
            "cpu_seconds": time.process_time() - cpu,
            "scope": "pose validation, any preparation, source checks, source and pose geometry observations, transform and fresh cross evaluation; output excluded",
        }
        rows.append(row)
    success = sum(r["status"] == "evaluated" for r in rows)
    return {
        "schema_version": "prepared_rigid_pose_cross_report_v1",
        "rows": rows,
        "pose_adapter_source_sha256": hashlib.sha256(
            Path(__file__).read_bytes()
        ).hexdigest(),
        "denominator": {
            "requested": len(rows),
            "evaluated": success,
            "failed": len(rows) - success,
            "skipped": 0,
        },
        "preparation": shared,
        "execution": execution_declaration,
        "preparation_observation": {
            "attempts": preparation_attempts,
            "successful_loads": preparations,
            "reuse_hits": reuse_hits,
            "successful_source_rechecks": rechecks,
            "load_wall_seconds": preparation_wall,
            "numerical_results_reused": False,
        },
        "score_semantics": "fixed-candidate cross potential only; no affinity, search, refinement or active ranking",
        "customer_execution": False,
        "scientifically_validated": False,
        "external_solver_called": False,
    }
