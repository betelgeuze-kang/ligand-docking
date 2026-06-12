#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

from tools.casp17 import validate_casp17_confidence_calibration as confidence_validator
from tools.casp17 import validate_casp17_geometry_sanity as geometry_validator
from tools import validate_casp17_ts_prediction as format_validator
from tools.build_casp17_all_atom_quality_packet import _inter_residue_contact_counts, _parse_first_model
from tools.build_casp17_rotamer_minimization_packet import (
    ACIDIC_RESIDUES,
    BASIC_RESIDUES,
    HBOND_MAX_A,
    HBOND_MIN_A,
    HYDROPHOBIC_MAX_A,
    HYDROPHOBIC_MIN_A,
    HYDROPHOBIC_RESIDUES,
    SALT_MAX_A,
    SALT_MIN_A,
    _add,
    _artifact,
    _distance_sq,
    _interaction_counts,
    _parse_source,
    _record,
    _residue_key,
    _resolve,
    _same_residue,
    _scale,
    _sub,
    _text,
    _unit,
    _write_json,
)
from tools.build_casp17_sidechain_scaffold_packet import BACKBONE_ATOMS


DEFAULT_WATCHLIST_JSON = "runs/casp17_target_watchlist_current.json"
DEFAULT_SOURCE_DIR = "runs/casp17_predictions_polar_refined_current"
DEFAULT_SEQUENCE_DIR = "runs/casp17_sequences_current"
DEFAULT_OUT_DIR = "runs/casp17_predictions_forcefield_minimized_current"
DEFAULT_OUT_JSON = "runs/casp17_forcefield_minimization_packet_current.json"
DEFAULT_OUT_CSV = "runs/casp17_forcefield_minimization_packet_current.csv"
DEFAULT_OUT_MD = "runs/casp17_forcefield_minimization_packet_current.md"

CELL_SIZE_A = 5.4
SOFT_DISTANCE_A = 1.10
SEVERE_DISTANCE_A = 0.80
NEAR_DISTANCE_A = 1.55
PAIR_SEARCH_A = 5.6
ANCHOR_K = 0.18
REPULSION_K = 11.0
NEAR_K = 0.55
SALT_K = 0.32
HBOND_K = 0.15
HYDROPHOBIC_K = 0.045
MAX_ITER_SHIFT_A = 0.045
MAX_TOTAL_SHIFT_A = 0.28


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    if not fieldnames:
        fieldnames = ["target_id"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _current_open_targets(watchlist: dict[str, Any]) -> list[str]:
    rows = watchlist.get("rows")
    if not isinstance(rows, list):
        return []
    targets: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        lane = _text(row.get("lane_recommendation"))
        target_id = _text(row.get("target_id")).upper()
        if target_id and row.get("human_open") is True and lane in {"organic_ligand_protein_complexes", "difficult_protein_complexes"}:
            targets.append(target_id)
    return targets


def _target_ids(args: argparse.Namespace) -> list[str]:
    explicit = [item.strip().upper() for item in _text(args.target_ids).split(",") if item.strip()]
    if explicit:
        return explicit
    current = _current_open_targets(_read_json(args.target_watchlist_json))
    if current:
        return current
    root = _resolve(args.source_dir)
    return sorted(path.name[:-6].upper() for path in root.glob("*TS.pdb"))


def _norm(vec: tuple[float, float, float]) -> float:
    return math.sqrt(max(0.0, vec[0] * vec[0] + vec[1] * vec[1] + vec[2] * vec[2]))


def _clip(vec: tuple[float, float, float], max_norm: float) -> tuple[float, float, float]:
    value = _norm(vec)
    if value <= max_norm or value < 1e-9:
        return vec
    return _scale(vec, max_norm / value)


def _grid_for_coords(
    atoms: list[dict[str, Any]],
    coords: dict[int, tuple[float, float, float]],
) -> dict[tuple[int, int, int], list[int]]:
    grid: dict[tuple[int, int, int], list[int]] = defaultdict(list)
    for index, atom in enumerate(atoms):
        coord = coords[int(atom["line_index"])]
        grid[tuple(math.floor(axis / CELL_SIZE_A) for axis in coord)].append(index)
    return grid


def _nearby_indices(
    grid: dict[tuple[int, int, int], list[int]],
    coord: tuple[float, float, float],
) -> list[int]:
    cell = tuple(math.floor(axis / CELL_SIZE_A) for axis in coord)
    indices: list[int] = []
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dz in (-1, 0, 1):
                indices.extend(grid.get((cell[0] + dx, cell[1] + dy, cell[2] + dz), []))
    return indices


def _is_polar_atom(atom: dict[str, Any]) -> bool:
    return str(atom["atom_name"]).strip()[:1] in {"N", "O", "S"}


def _is_salt_pair(atom: dict[str, Any], other: dict[str, Any]) -> bool:
    left = str(atom["resname"])
    right = str(other["resname"])
    left_atom = str(atom["atom_name"]).strip()[:1]
    right_atom = str(other["atom_name"]).strip()[:1]
    return (
        (left in BASIC_RESIDUES and left_atom == "N" and right in ACIDIC_RESIDUES and right_atom == "O")
        or (right in BASIC_RESIDUES and right_atom == "N" and left in ACIDIC_RESIDUES and left_atom == "O")
    )


def _is_hydrophobic_pair(atom: dict[str, Any], other: dict[str, Any]) -> bool:
    return str(atom["resname"]) in HYDROPHOBIC_RESIDUES and str(other["resname"]) in HYDROPHOBIC_RESIDUES


def _atom_force(
    atom: dict[str, Any],
    atoms: list[dict[str, Any]],
    coords: dict[int, tuple[float, float, float]],
    anchors: dict[int, tuple[float, float, float]],
    spatial_grid: dict[tuple[int, int, int], list[int]],
) -> tuple[float, float, float]:
    line_index = int(atom["line_index"])
    coord = coords[line_index]
    force = _scale(_sub(anchors[line_index], coord), ANCHOR_K)
    for other_index in _nearby_indices(spatial_grid, coord):
        other = atoms[other_index]
        if int(other["line_index"]) == line_index or _same_residue(atom, other):
            continue
        other_coord = coords[int(other["line_index"])]
        delta = _sub(other_coord, coord)
        dist_sq = _distance_sq(coord, other_coord)
        if dist_sq < 1e-10:
            continue
        dist = math.sqrt(dist_sq)
        if dist > PAIR_SEARCH_A:
            continue
        direction = _unit(delta, (1.0, 0.0, 0.0))
        if dist < SOFT_DISTANCE_A:
            force = _add(force, _scale(direction, -REPULSION_K * (SOFT_DISTANCE_A - dist)))
        elif dist < NEAR_DISTANCE_A:
            force = _add(force, _scale(direction, -NEAR_K * (NEAR_DISTANCE_A - dist)))
        if _is_salt_pair(atom, other):
            target = (SALT_MIN_A + SALT_MAX_A) / 2.0
            force = _add(force, _scale(direction, SALT_K * (dist - target)))
        elif _is_polar_atom(atom) and _is_polar_atom(other):
            target = (HBOND_MIN_A + HBOND_MAX_A) / 2.0
            force = _add(force, _scale(direction, HBOND_K * (dist - target)))
        elif _is_hydrophobic_pair(atom, other):
            target = (HYDROPHOBIC_MIN_A + HYDROPHOBIC_MAX_A) / 2.0
            force = _add(force, _scale(direction, HYDROPHOBIC_K * (dist - target)))
    return force


def _forcefield_energy(
    atoms: list[dict[str, Any]],
    coords: dict[int, tuple[float, float, float]],
    anchors: dict[int, tuple[float, float, float]],
) -> float:
    spatial_grid = _grid_for_coords(atoms, coords)
    sidechain_ids = {int(atom["line_index"]) for atom in atoms if atom["atom_name"] not in BACKBONE_ATOMS}
    energy = 0.0
    for line_index in sidechain_ids:
        energy += _distance_sq(coords[line_index], anchors[line_index]) * 0.32
    seen: set[tuple[int, int]] = set()
    for index, atom in enumerate(atoms):
        coord = coords[int(atom["line_index"])]
        for other_index in _nearby_indices(spatial_grid, coord):
            if other_index <= index:
                continue
            pair = (index, other_index)
            if pair in seen:
                continue
            seen.add(pair)
            other = atoms[other_index]
            if _same_residue(atom, other):
                continue
            other_coord = coords[int(other["line_index"])]
            dist = math.sqrt(_distance_sq(coord, other_coord))
            if dist < SEVERE_DISTANCE_A:
                energy += 60000.0 + (SEVERE_DISTANCE_A - dist) * 80000.0
            elif dist < SOFT_DISTANCE_A:
                energy += 2400.0 + (SOFT_DISTANCE_A - dist) * 4200.0
            elif dist < NEAR_DISTANCE_A:
                energy += (NEAR_DISTANCE_A - dist) * 20.0
            if _is_salt_pair(atom, other) and dist <= PAIR_SEARCH_A:
                target = (SALT_MIN_A + SALT_MAX_A) / 2.0
                energy += min((dist - target) ** 2, 4.0) * 0.38
                if SALT_MIN_A <= dist <= SALT_MAX_A:
                    energy -= 10.0
            elif _is_polar_atom(atom) and _is_polar_atom(other) and dist <= PAIR_SEARCH_A:
                target = (HBOND_MIN_A + HBOND_MAX_A) / 2.0
                energy += min((dist - target) ** 2, 4.0) * 0.10
                if HBOND_MIN_A <= dist <= HBOND_MAX_A:
                    energy -= 2.8
            elif _is_hydrophobic_pair(atom, other) and dist <= PAIR_SEARCH_A:
                target = (HYDROPHOBIC_MIN_A + HYDROPHOBIC_MAX_A) / 2.0
                energy += min((dist - target) ** 2, 4.0) * 0.018
                if HYDROPHOBIC_MIN_A <= dist <= HYDROPHOBIC_MAX_A:
                    energy -= 0.35
    return round(float(energy), 6)


def _minimize_atoms(
    atoms: list[dict[str, Any]],
    *,
    iterations: int,
    step_size: float,
) -> tuple[dict[int, tuple[float, float, float]], dict[str, Any]]:
    coords = {int(atom["line_index"]): atom["coord"] for atom in atoms}
    anchors = dict(coords)
    movable = [atom for atom in atoms if atom["atom_name"] not in BACKBONE_ATOMS]
    energy_before = _forcefield_energy(atoms, coords, anchors)
    for _iteration in range(max(0, iterations)):
        spatial_grid = _grid_for_coords(atoms, coords)
        proposed: dict[int, tuple[float, float, float]] = {}
        for atom in movable:
            line_index = int(atom["line_index"])
            force = _atom_force(atom, atoms, coords, anchors, spatial_grid)
            shift = _clip(_scale(force, step_size), MAX_ITER_SHIFT_A)
            next_coord = _add(coords[line_index], shift)
            total_shift = _sub(next_coord, anchors[line_index])
            if _norm(total_shift) > MAX_TOTAL_SHIFT_A:
                next_coord = _add(anchors[line_index], _clip(total_shift, MAX_TOTAL_SHIFT_A))
            proposed[line_index] = next_coord
        coords.update(proposed)

    updates: dict[int, tuple[float, float, float]] = {}
    total_shift = 0.0
    max_shift = 0.0
    for atom in movable:
        line_index = int(atom["line_index"])
        shift = _norm(_sub(coords[line_index], anchors[line_index]))
        if shift > 0.001:
            updates[line_index] = coords[line_index]
            total_shift += shift
            max_shift = max(max_shift, shift)
    energy_after = _forcefield_energy(atoms, coords, anchors)
    return updates, {
        "sidechain_atom_count": len(movable),
        "iteration_count": max(0, iterations),
        "forcefield_energy_before": energy_before,
        "forcefield_energy_after": energy_after,
        "forcefield_energy_delta": round(energy_before - energy_after, 6),
        "mean_sidechain_shift_A": round(total_shift / len(updates), 6) if updates else 0.0,
        "max_sidechain_shift_A": round(max_shift, 6),
    }


def _update_atom_line(line: str, coord: tuple[float, float, float]) -> str:
    fields = line.split()
    try:
        serial = int(fields[1])
    except (IndexError, ValueError):
        serial = 0
    atom_name = line[12:16].strip() if len(line) >= 16 else ""
    if not atom_name and len(fields) > 2:
        atom_name = fields[2]
    resname = line[17:20].strip().upper() if len(line) >= 20 else ""
    if not resname and len(fields) > 3:
        resname = fields[3].upper()
    chain_id = line[21].strip() if len(line) > 21 else ""
    if not chain_id and len(fields) > 4:
        chain_id = fields[4][:1]
    try:
        resseq = int(line[22:26])
    except ValueError:
        try:
            resseq = int(fields[5])
        except (IndexError, ValueError):
            resseq = 0
    try:
        occupancy = float(fields[-3])
    except (IndexError, ValueError):
        occupancy = 1.0
    try:
        b_factor = float(fields[-2])
    except (IndexError, ValueError):
        b_factor = 0.0
    element = fields[-1] if fields and fields[-1].isalpha() and len(fields[-1]) <= 2 else (atom_name[:1] or "C")
    x, y, z = coord
    return (
        f"ATOM  {serial:5d} {atom_name:<4} {resname:>3} {chain_id:1}{resseq:4d}    "
        f"{x:8.3f}{y:8.3f}{z:8.3f}{occupancy:6.2f}{b_factor:6.2f}          {element:>2}  "
    )


def _insert_remark(lines: list[str]) -> list[str]:
    remark = "REMARK CASP17 FORCEFIELD_MINIMIZATION internal short sidechain-only forcefield-style minimization; not native-calibrated refinement"
    if any(line.startswith("REMARK CASP17 FORCEFIELD_MINIMIZATION") for line in lines):
        return lines
    out = lines[:]
    insert_index = next((index + 1 for index, line in enumerate(out) if _record(line) in {"SCORE", "QSCORE", "STOICH"}), None)
    if insert_index is None:
        insert_index = next((index + 1 for index, line in enumerate(out) if _record(line) == "MODEL"), 0)
    out.insert(insert_index, remark)
    return out


def _write_minimized(source: Path, out_pdb: Path, updates: dict[int, tuple[float, float, float]]) -> None:
    lines, _atoms = _parse_source(source)
    for line_index, coord in updates.items():
        if 0 <= line_index < len(lines) and _record(lines[line_index]) == "ATOM":
            lines[line_index] = _update_atom_line(lines[line_index], coord)
    lines = _insert_remark(lines)
    out_pdb.parent.mkdir(parents=True, exist_ok=True)
    out_pdb.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _quality(path_like: str | Path) -> dict[str, Any]:
    atoms = _parse_first_model(path_like)
    return {"atom_count": len(atoms), **_inter_residue_contact_counts(atoms), **_interaction_counts(atoms)}


def _build_one(target_id: str, args: argparse.Namespace) -> dict[str, Any]:
    source = _resolve(args.source_dir) / f"{target_id}TS.pdb"
    sequence_path = _resolve(args.sequence_dir) / f"{target_id}.fasta"
    out_pdb = _resolve(args.out_dir) / f"{target_id}TS.pdb"
    blockers: list[str] = []
    metrics: dict[str, Any] = {
        "atom_count": 0,
        "sidechain_atom_count": 0,
        "iteration_count": int(args.iterations),
        "coordinate_update_count": 0,
        "forcefield_energy_before": 0.0,
        "forcefield_energy_after": 0.0,
        "forcefield_energy_delta": 0.0,
        "mean_sidechain_shift_A": 0.0,
        "max_sidechain_shift_A": 0.0,
        "soft_clash_count_before": 0,
        "soft_clash_count_after": 0,
        "soft_clash_delta": 0,
        "severe_clash_count_before": 0,
        "severe_clash_count_after": 0,
        "hbond_like_contact_count_before": 0,
        "hbond_like_contact_count_after": 0,
        "salt_bridge_like_contact_count_before": 0,
        "salt_bridge_like_contact_count_after": 0,
        "hydrophobic_contact_count_before": 0,
        "hydrophobic_contact_count_after": 0,
        "revert_guard_triggered": False,
    }
    validation = {
        "format_check_status": "not_run",
        "geometry_sanity_status": "not_run",
        "confidence_calibration_status": "not_run",
    }
    if not source.exists():
        blockers.append("source_prediction_missing")
    if not sequence_path.exists():
        blockers.append("sequence_file_missing")
    if not blockers:
        _lines, atoms = _parse_source(source)
        if not atoms:
            blockers.append("atom_records_missing")
        else:
            before = _quality(source)
            updates, minimization = _minimize_atoms(atoms, iterations=int(args.iterations), step_size=float(args.step_size))
            _write_minimized(source, out_pdb, updates)
            after = _quality(out_pdb)
            if (
                int(after["soft_clash_count"]) > int(before["soft_clash_count"])
                or int(after["severe_clash_count"]) > int(before["severe_clash_count"])
                or float(minimization["forcefield_energy_after"]) > float(minimization["forcefield_energy_before"]) + 1e-6
            ):
                _write_minimized(source, out_pdb, {})
                after = before
                updates = {}
                minimization = {
                    **minimization,
                    "forcefield_energy_after": minimization["forcefield_energy_before"],
                    "forcefield_energy_delta": 0.0,
                    "mean_sidechain_shift_A": 0.0,
                    "max_sidechain_shift_A": 0.0,
                    "reverted_not_worse_guard": True,
                }
            validation_format = format_validator.validate_prediction(
                target_id=target_id,
                prediction_file=out_pdb,
                sequence_path=sequence_path,
            )
            validation_geometry = geometry_validator.validate_geometry(target_id=target_id, prediction_file=out_pdb)
            validation_confidence = confidence_validator.validate_confidence(
                target_id=target_id,
                prediction_file=out_pdb,
                sequence_path=sequence_path,
            )
            validation = {
                "format_check_status": validation_format["summary"]["format_check_status"],
                "geometry_sanity_status": validation_geometry["summary"]["geometry_sanity_status"],
                "confidence_calibration_status": validation_confidence["summary"]["confidence_calibration_status"],
            }
            if validation["format_check_status"] != "pass":
                blockers.append("format_check_failed")
            if validation["geometry_sanity_status"] != "pass":
                blockers.append("geometry_sanity_failed")
            if validation["confidence_calibration_status"] != "pass":
                blockers.append("confidence_calibration_failed")
            if int(after["severe_clash_count"]):
                blockers.append("severe_clash_after_minimization")
            if int(after["soft_clash_count"]) > int(before["soft_clash_count"]):
                blockers.append("soft_clash_regression")
            if float(minimization["forcefield_energy_after"]) > float(minimization["forcefield_energy_before"]) + 1e-6:
                blockers.append("forcefield_energy_regression")
            metrics = {
                "atom_count": int(after["atom_count"]),
                **minimization,
                "coordinate_update_count": len(updates),
                "soft_clash_count_before": int(before["soft_clash_count"]),
                "soft_clash_count_after": int(after["soft_clash_count"]),
                "soft_clash_delta": int(before["soft_clash_count"]) - int(after["soft_clash_count"]),
                "soft_clashscore_after": float(after["soft_clashscore_per_1000_atoms"]),
                "severe_clash_count_before": int(before["severe_clash_count"]),
                "severe_clash_count_after": int(after["severe_clash_count"]),
                "hbond_like_contact_count_before": int(before["hbond_like_contact_count"]),
                "hbond_like_contact_count_after": int(after["hbond_like_contact_count"]),
                "salt_bridge_like_contact_count_before": int(before["salt_bridge_like_contact_count"]),
                "salt_bridge_like_contact_count_after": int(after["salt_bridge_like_contact_count"]),
                "hydrophobic_contact_count_before": int(before["hydrophobic_contact_count"]),
                "hydrophobic_contact_count_after": int(after["hydrophobic_contact_count"]),
                "revert_guard_triggered": bool(minimization.get("reverted_not_worse_guard")),
            }
    return {
        "target_id": target_id,
        "forcefield_minimization_status": "pass" if not blockers else "blocked",
        "source_pdb": _artifact(source),
        "out_pdb": _artifact(out_pdb),
        **metrics,
        **validation,
        "blockers": ",".join(sorted(set(blockers))),
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    rows = [_build_one(target_id, args) for target_id in _target_ids(args)]
    pass_count = sum(1 for row in rows if row["forcefield_minimization_status"] == "pass")
    total_before = sum(int(row.get("soft_clash_count_before", 0) or 0) for row in rows)
    total_after = sum(int(row.get("soft_clash_count_after", 0) or 0) for row in rows)
    summary = {
        "packet_type": "casp17_forcefield_minimization_packet",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "target_count": len(rows),
        "pass_count": pass_count,
        "blocked_count": len(rows) - pass_count,
        "forcefield_minimization_status": "pass" if rows and pass_count == len(rows) else "blocked",
        "source_dir": _artifact(args.source_dir),
        "out_dir": _artifact(args.out_dir),
        "selection_mode": "short_sidechain_only_forcefield_style_minimization_not_worse",
        "iteration_count": int(args.iterations),
        "step_size": float(args.step_size),
        "total_soft_clash_count_before": total_before,
        "total_soft_clash_count_after": total_after,
        "total_soft_clash_delta": total_before - total_after,
        "total_coordinate_update_count": sum(int(row.get("coordinate_update_count", 0) or 0) for row in rows),
        "total_sidechain_atom_count": sum(int(row.get("sidechain_atom_count", 0) or 0) for row in rows),
        "total_forcefield_energy_before": round(sum(float(row.get("forcefield_energy_before", 0.0) or 0.0) for row in rows), 6),
        "total_forcefield_energy_after": round(sum(float(row.get("forcefield_energy_after", 0.0) or 0.0) for row in rows), 6),
        "total_forcefield_energy_delta": round(sum(float(row.get("forcefield_energy_delta", 0.0) or 0.0) for row in rows), 6),
        "revert_guard_count": sum(int(bool(row.get("revert_guard_triggered"))) for row in rows),
        "total_hbond_like_contact_count_before": sum(int(row.get("hbond_like_contact_count_before", 0) or 0) for row in rows),
        "total_hbond_like_contact_count_after": sum(int(row.get("hbond_like_contact_count_after", 0) or 0) for row in rows),
        "total_salt_bridge_like_contact_count_before": sum(int(row.get("salt_bridge_like_contact_count_before", 0) or 0) for row in rows),
        "total_salt_bridge_like_contact_count_after": sum(int(row.get("salt_bridge_like_contact_count_after", 0) or 0) for row in rows),
        "total_hydrophobic_contact_count_before": sum(int(row.get("hydrophobic_contact_count_before", 0) or 0) for row in rows),
        "total_hydrophobic_contact_count_after": sum(int(row.get("hydrophobic_contact_count_after", 0) or 0) for row in rows),
        "claim_boundary": "Internal short sidechain-only forcefield-style minimization over generated CASP17 coordinates only; not official MolProbity, not native accuracy evidence, not full all-atom forcefield refinement, and not portal submission.",
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Forcefield Minimization Packet",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- source_dir: `{summary['source_dir']}`",
        f"- out_dir: `{summary['out_dir']}`",
        f"- status: `{summary['forcefield_minimization_status']}`",
        f"- pass/blocked: `{summary['pass_count']}/{summary['blocked_count']}`",
        f"- selection_mode: `{summary['selection_mode']}`",
        f"- iterations/step_size: `{summary['iteration_count']}/{summary['step_size']}`",
        f"- soft clashes before/after/delta: `{summary['total_soft_clash_count_before']}/{summary['total_soft_clash_count_after']}/{summary['total_soft_clash_delta']}`",
        f"- forcefield energy before/after/delta: `{summary['total_forcefield_energy_before']}/{summary['total_forcefield_energy_after']}/{summary['total_forcefield_energy_delta']}`",
        f"- hbond-like contacts before/after: `{summary['total_hbond_like_contact_count_before']}/{summary['total_hbond_like_contact_count_after']}`",
        f"- salt-bridge-like contacts before/after: `{summary['total_salt_bridge_like_contact_count_before']}/{summary['total_salt_bridge_like_contact_count_after']}`",
        f"- hydrophobic contacts before/after: `{summary['total_hydrophobic_contact_count_before']}/{summary['total_hydrophobic_contact_count_after']}`",
        "",
        "| target | status | sidechain atoms | updates | guard | energy before | energy after | soft before | soft after | hbond before/after | salt before/after | hydro before/after | format | geometry | confidence | blockers |",
        "| --- | --- | ---: | ---: | --- | ---: | ---: | ---: | ---: | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['forcefield_minimization_status']}` | {row['sidechain_atom_count']} | "
            f"{row['coordinate_update_count']} | `{row.get('revert_guard_triggered', False)}` | "
            f"{row['forcefield_energy_before']} | {row['forcefield_energy_after']} | "
            f"{row['soft_clash_count_before']} | {row['soft_clash_count_after']} | "
            f"{row['hbond_like_contact_count_before']}/{row['hbond_like_contact_count_after']} | "
            f"{row['salt_bridge_like_contact_count_before']}/{row['salt_bridge_like_contact_count_after']} | "
            f"{row['hydrophobic_contact_count_before']}/{row['hydrophobic_contact_count_after']} | "
            f"`{row['format_check_status']}` | `{row['geometry_sanity_status']}` | "
            f"`{row['confidence_calibration_status']}` | {row['blockers'] or '-'} |"
        )
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build internal short forcefield-style minimization packet for CASP17 generated TS predictions.")
    parser.add_argument("--target-watchlist-json", default=DEFAULT_WATCHLIST_JSON)
    parser.add_argument("--target-ids", default="")
    parser.add_argument("--source-dir", default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--sequence-dir", default=DEFAULT_SEQUENCE_DIR)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--iterations", type=int, default=6)
    parser.add_argument("--step-size", type=float, default=0.006)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)
    if payload["summary"]["blocked_count"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
