"""Fixed cross-distance ranking screen for serialized prepared pose reports.

The one-angstrom threshold is a ranking rule. It does not change the numeric
cross calculation or establish physical validity of a supplied pose.
"""

from __future__ import annotations

import math

import numpy as np

from .prepared_cross_numeric_reference import _component

HARD_OVERLAP_DISTANCE_ANGSTROM = 1.0


def _points(value):
    if (type(value) is not list or not value
            or any(type(row) is not list or len(row) != 3
                   or any(type(coordinate) not in (int, float) for coordinate in row)
                   for row in value)):
        return None
    try:
        array = np.asarray(value, dtype=np.float64)
    except (TypeError, ValueError, OverflowError):
        return None
    return array if np.isfinite(array).all() else None


def minimum_cross_distance_angstrom(receptor, ligand):
    """Use one all-source-atom distance calculation for preflight and ranking."""
    if (not isinstance(receptor, np.ndarray) or not isinstance(ligand, np.ndarray)
            or receptor.ndim != 2 or ligand.ndim != 2
            or receptor.shape[1] != 3 or ligand.shape[1] != 3
            or not len(receptor) or not len(ligand)
            or not np.isfinite(receptor).all() or not np.isfinite(ligand).all()):
        return None
    minimum = math.inf
    for start in range(0, len(receptor), 64):
        with np.errstate(over="ignore", invalid="ignore"):
            delta = receptor[start:start + 64, None, :] - ligand[None, :, :]
            distances = np.hypot(
                np.hypot(delta[:, :, 0], delta[:, :, 1]), delta[:, :, 2]
            )
        if not np.isfinite(distances).all():
            return None
        minimum = min(minimum, float(distances.min()))
    return minimum if math.isfinite(minimum) else None


def hard_overlap_screen(report):
    """Exhaust all receptor-ligand pairs and fail closed on absent coordinates."""
    preparation = report.get("preparation")
    receptor = (_points(preparation.get("source_receptor_coordinates_angstrom"))
                if type(preparation) is dict else None)
    rows = []
    for index, row in enumerate(report["rows"]):
        ligand = (_points(row.get("evaluated_ligand_coordinates_angstrom"))
                  if type(row) is dict else None)
        distance = (minimum_cross_distance_angstrom(receptor, ligand)
                    if receptor is not None and ligand is not None else None)
        status = ("unavailable" if distance is None else
                  "hard_overlap" if distance < HARD_OVERLAP_DISTANCE_ANGSTROM
                  else "eligible")
        rows.append({
            "request_index": index,
            "pose_id": row.get("case_id") if type(row) is dict else None,
            "minimum_cross_distance_angstrom": distance,
            "status": status,
        })
    return {
        "schema_version": "prepared_rigid_hard_overlap_screen_v1",
        "minimum_cross_distance_angstrom": HARD_OVERLAP_DISTANCE_ANGSTROM,
        "poses": rows,
        "eligible_pose_count": sum(row["status"] == "eligible" for row in rows),
        "scope": "fixed noncovalent cross-distance ranking screen; not physical validation",
    }


def screened_pose_selection(report, screen):
    eligible = [index for index, row in enumerate(screen["poses"])
                if row["status"] == "eligible"]
    if not eligible:
        return None

    def score(index):
        value = report["rows"][index]["result"]["quantities"]["cross_total_kcal_per_mol"]
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError("invalid_comparison_number")
        return float(value)

    index = min(eligible, key=score)
    return {
        "request_index": index,
        "pose_id": report["rows"][index]["case_id"],
        "score": score(index),
    }


def require_report_geometry_source_binding(report):
    """Tie display coordinates to numeric inputs in a portable pose report."""
    shared = report.get("preparation")
    if type(shared) is not dict or type(report.get("rows")) is not list:
        raise ValueError("pose_report_source_geometry_mismatch")
    receptor_coordinates = shared.get("source_receptor_coordinates_angstrom")
    for row in report["rows"]:
        if type(row) is not dict or row.get("status") != "evaluated":
            raise ValueError("pose_report_source_geometry_mismatch")
        try:
            sources = row["result"]["sources"]
            canonical_receptor, _ = _component(sources["receptor"])
            canonical_ligand, _ = _component(sources["ligand"])
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise ValueError("pose_report_source_geometry_mismatch") from exc
        if (receptor_coordinates != canonical_receptor
                or row.get("evaluated_ligand_coordinates_angstrom") != canonical_ligand):
            raise ValueError("pose_report_source_geometry_mismatch")
