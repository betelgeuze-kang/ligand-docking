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
from tools.build_casp17_forcefield_minimization_packet import _forcefield_energy
from tools.build_casp17_rotamer_minimization_packet import (
    ROTAMER_LIBRARY_DEG,
    _add,
    _angle_delta,
    _artifact,
    _candidate_score,
    _ca_tangent,
    _grid,
    _interaction_counts,
    _normal_frame,
    _parse_source,
    _pseudo_angle,
    _record,
    _residue_key,
    _resolve,
    _rotate_about_axis,
    _sub,
    _text,
    _write_json,
)
from tools.build_casp17_sidechain_scaffold_packet import BACKBONE_ATOMS


DEFAULT_WATCHLIST_JSON = "runs/casp17_target_watchlist_current.json"
DEFAULT_SOURCE_DIR = "runs/casp17_predictions_forcefield_minimized_current"
DEFAULT_SEQUENCE_DIR = "runs/casp17_sequences_current"
DEFAULT_OUT_DIR = "runs/casp17_predictions_statistical_rotamer_current"
DEFAULT_OUT_JSON = "runs/casp17_statistical_rotamer_packet_current.json"
DEFAULT_OUT_CSV = "runs/casp17_statistical_rotamer_packet_current.csv"
DEFAULT_OUT_MD = "runs/casp17_statistical_rotamer_packet_current.md"

PRIOR_WEIGHT = 1.15
ACCEPTANCE_EPSILON = 0.02

INTERNAL_STATISTICAL_ROTAMER_PRIOR: dict[str, tuple[tuple[float, float], ...]] = {
    "ALA": ((60.0, 0.34), (180.0, 0.33), (-60.0, 0.33)),
    "ARG": ((-60.0, 0.45), (180.0, 0.34), (60.0, 0.21)),
    "ASN": ((-60.0, 0.42), (180.0, 0.37), (60.0, 0.21)),
    "ASP": ((-60.0, 0.43), (180.0, 0.36), (60.0, 0.21)),
    "CYS": ((-60.0, 0.48), (60.0, 0.29), (180.0, 0.23)),
    "GLN": ((-60.0, 0.43), (180.0, 0.35), (60.0, 0.22)),
    "GLU": ((-60.0, 0.43), (180.0, 0.35), (60.0, 0.22)),
    "HIS": ((-60.0, 0.41), (60.0, 0.32), (180.0, 0.27)),
    "ILE": ((-60.0, 0.50), (180.0, 0.31), (60.0, 0.19)),
    "LEU": ((-60.0, 0.47), (180.0, 0.34), (60.0, 0.19)),
    "LYS": ((-60.0, 0.45), (180.0, 0.35), (60.0, 0.20)),
    "MET": ((-60.0, 0.43), (180.0, 0.34), (60.0, 0.23)),
    "PHE": ((-60.0, 0.40), (60.0, 0.35), (180.0, 0.25)),
    "PRO": ((30.0, 0.46), (-30.0, 0.34), (90.0, 0.12), (-90.0, 0.08)),
    "SER": ((-60.0, 0.38), (60.0, 0.36), (180.0, 0.26)),
    "THR": ((-60.0, 0.39), (60.0, 0.38), (180.0, 0.23)),
    "TRP": ((-60.0, 0.40), (60.0, 0.34), (180.0, 0.26)),
    "TYR": ((-60.0, 0.40), (60.0, 0.35), (180.0, 0.25)),
    "VAL": ((-60.0, 0.41), (60.0, 0.40), (180.0, 0.19)),
}


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


def _prior_options(resname: str) -> tuple[tuple[float, float], ...]:
    if resname in INTERNAL_STATISTICAL_ROTAMER_PRIOR:
        return INTERNAL_STATISTICAL_ROTAMER_PRIOR[resname]
    library = ROTAMER_LIBRARY_DEG.get(resname, ())
    if not library:
        return ()
    probability = 1.0 / len(library)
    return tuple((float(angle), probability) for angle in library)


def _prior_penalty(angle: float, options: tuple[tuple[float, float], ...]) -> float:
    if not options:
        return 0.0
    penalties = []
    for target_angle, probability in options:
        probability = max(float(probability), 0.01)
        angle_term = (_angle_delta(angle, target_angle) / 55.0) ** 2
        penalties.append(angle_term - math.log(probability))
    return float(min(penalties))


def _statistical_score(
    *,
    residue_atoms: list[dict[str, Any]],
    candidate_coords: dict[int, tuple[float, float, float]],
    all_atoms: list[dict[str, Any]],
    spatial_grid: dict[tuple[int, int, int], list[int]],
    current_coords: dict[int, tuple[float, float, float]],
    target_angle: float,
    selected_angle: float,
    probability: float,
) -> float:
    contact_score = _candidate_score(
        residue_atoms,
        candidate_coords,
        all_atoms,
        spatial_grid,
        current_coords,
        target_angle,
        selected_angle,
    )
    frequency_penalty = -math.log(max(float(probability), 0.01))
    return float(contact_score + PRIOR_WEIGHT * frequency_penalty)


def _pack_atoms(atoms: list[dict[str, Any]]) -> tuple[dict[int, tuple[float, float, float]], dict[str, Any]]:
    by_residue: dict[tuple[str, int, str], list[dict[str, Any]]] = defaultdict(list)
    ca_by_chain: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for atom in atoms:
        by_residue[_residue_key(atom)].append(atom)
        if atom["atom_name"] == "CA":
            ca_by_chain[str(atom["chain_id"])].append(atom)
    for trace in ca_by_chain.values():
        trace.sort(key=lambda item: (int(item["resseq"]), str(item["insertion_code"])))

    spatial_grid = _grid(atoms)
    current_coords = {int(atom["line_index"]): atom["coord"] for atom in atoms}
    updates: dict[int, tuple[float, float, float]] = {}
    evaluated_residue_count = 0
    packed_residue_count = 0
    improved_residue_count = 0
    candidate_count = 0
    total_score_delta = 0.0
    total_prior_before = 0.0
    total_prior_after = 0.0

    for residue_key, residue_atoms in sorted(by_residue.items(), key=lambda item: item[0]):
        ca_atoms = [atom for atom in residue_atoms if atom["atom_name"] == "CA"]
        cb_atoms = [atom for atom in residue_atoms if atom["atom_name"] == "CB"]
        sidechain_atoms = [atom for atom in residue_atoms if atom["atom_name"] not in BACKBONE_ATOMS]
        if not ca_atoms or not cb_atoms or not sidechain_atoms:
            continue
        resname = str(residue_atoms[0]["resname"])
        options = _prior_options(resname)
        if not options:
            continue
        ca = current_coords[int(ca_atoms[0]["line_index"])]
        tangent = _ca_tangent(residue_key, ca_by_chain)
        normal, binormal = _normal_frame(tangent)
        current_angle = _pseudo_angle(ca, current_coords[int(cb_atoms[0]["line_index"])], normal, binormal)
        original = {int(atom["line_index"]): current_coords[int(atom["line_index"])] for atom in sidechain_atoms}
        nearest_angle, nearest_probability = min(options, key=lambda item: _angle_delta(current_angle, item[0]))
        original_score = _statistical_score(
            residue_atoms=sidechain_atoms,
            candidate_coords=original,
            all_atoms=atoms,
            spatial_grid=spatial_grid,
            current_coords=current_coords,
            target_angle=nearest_angle,
            selected_angle=current_angle,
            probability=nearest_probability,
        )
        candidates: list[tuple[float, float, float, float, dict[int, tuple[float, float, float]]]] = [
            (original_score, nearest_angle, current_angle, nearest_probability, original)
        ]
        for target_angle, probability in options:
            base_delta = (target_angle - current_angle + 180.0) % 360.0 - 180.0
            selected_angle = current_angle + base_delta
            candidate: dict[int, tuple[float, float, float]] = {}
            for atom in sidechain_atoms:
                line_index = int(atom["line_index"])
                rel = _sub(current_coords[line_index], ca)
                rotated = _rotate_about_axis(rel, tangent, base_delta)
                candidate[line_index] = _add(ca, rotated)
            score = _statistical_score(
                residue_atoms=sidechain_atoms,
                candidate_coords=candidate,
                all_atoms=atoms,
                spatial_grid=spatial_grid,
                current_coords=current_coords,
                target_angle=target_angle,
                selected_angle=selected_angle,
                probability=probability,
            )
            candidates.append((score, target_angle, selected_angle, probability, candidate))
        candidates.sort(key=lambda item: item[0])
        best_score, _best_angle, best_selected_angle, _best_probability, best_candidate = candidates[0]
        evaluated_residue_count += 1
        candidate_count += len(candidates)
        total_prior_before += _prior_penalty(current_angle, options)
        if best_score < original_score - ACCEPTANCE_EPSILON:
            packed_residue_count += 1
            improved_residue_count += 1
            total_score_delta += original_score - best_score
            current_coords.update(best_candidate)
            updates.update(best_candidate)
            total_prior_after += _prior_penalty(best_selected_angle, options)
        else:
            total_prior_after += _prior_penalty(current_angle, options)

    return updates, {
        "evaluated_residue_count": evaluated_residue_count,
        "packed_residue_count": packed_residue_count,
        "improved_residue_count": improved_residue_count,
        "statistical_rotamer_candidate_count": candidate_count,
        "mean_frequency_prior_penalty_before": round(total_prior_before / evaluated_residue_count, 6) if evaluated_residue_count else 0.0,
        "mean_frequency_prior_penalty_after": round(total_prior_after / evaluated_residue_count, 6) if evaluated_residue_count else 0.0,
        "mean_statistical_score_delta": round(total_score_delta / improved_residue_count, 6) if improved_residue_count else 0.0,
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
    remark = "REMARK CASP17 STATISTICAL_ROTAMER internal residue-specific frequency-prior packing proxy; no external rotamer library or native template"
    if any(line.startswith("REMARK CASP17 STATISTICAL_ROTAMER") for line in lines):
        return lines
    out = lines[:]
    insert_index = next((index + 1 for index, line in enumerate(out) if _record(line) in {"SCORE", "QSCORE", "STOICH"}), None)
    if insert_index is None:
        insert_index = next((index + 1 for index, line in enumerate(out) if _record(line) == "MODEL"), 0)
    out.insert(insert_index, remark)
    return out


def _write_packed(source: Path, out_pdb: Path, updates: dict[int, tuple[float, float, float]]) -> None:
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


def _energy(path_like: str | Path) -> float:
    _lines, atoms = _parse_source(path_like)
    coords = {int(atom["line_index"]): atom["coord"] for atom in atoms}
    return _forcefield_energy(atoms, coords, coords)


def _build_one(target_id: str, args: argparse.Namespace) -> dict[str, Any]:
    source = _resolve(args.source_dir) / f"{target_id}TS.pdb"
    sequence_path = _resolve(args.sequence_dir) / f"{target_id}.fasta"
    out_pdb = _resolve(args.out_dir) / f"{target_id}TS.pdb"
    blockers: list[str] = []
    metrics: dict[str, Any] = {
        "atom_count": 0,
        "evaluated_residue_count": 0,
        "packed_residue_count": 0,
        "improved_residue_count": 0,
        "statistical_rotamer_candidate_count": 0,
        "coordinate_update_count": 0,
        "mean_frequency_prior_penalty_before": 0.0,
        "mean_frequency_prior_penalty_after": 0.0,
        "mean_statistical_score_delta": 0.0,
        "frequency_prior_penalty_delta": 0.0,
        "forcefield_energy_before": 0.0,
        "forcefield_energy_after": 0.0,
        "forcefield_energy_delta": 0.0,
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
            energy_before = _energy(source)
            updates, packing = _pack_atoms(atoms)
            _write_packed(source, out_pdb, updates)
            after = _quality(out_pdb)
            energy_after = _energy(out_pdb)
            reverted = False
            if (
                int(after["soft_clash_count"]) > int(before["soft_clash_count"])
                or int(after["severe_clash_count"]) > int(before["severe_clash_count"])
                or energy_after > energy_before + 1e-6
                or float(packing["mean_frequency_prior_penalty_after"])
                > float(packing["mean_frequency_prior_penalty_before"]) + 1e-6
            ):
                _write_packed(source, out_pdb, {})
                after = before
                energy_after = energy_before
                updates = {}
                packing = {
                    **packing,
                    "packed_residue_count": 0,
                    "improved_residue_count": 0,
                    "mean_frequency_prior_penalty_after": packing["mean_frequency_prior_penalty_before"],
                    "mean_statistical_score_delta": 0.0,
                }
                reverted = True
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
                blockers.append("severe_clash_after_statistical_rotamer")
            if int(after["soft_clash_count"]) > int(before["soft_clash_count"]):
                blockers.append("soft_clash_regression")
            if energy_after > energy_before + 1e-6:
                blockers.append("forcefield_energy_regression")
            if float(packing["mean_frequency_prior_penalty_after"]) > float(packing["mean_frequency_prior_penalty_before"]) + 1e-6:
                blockers.append("frequency_prior_regression")
            metrics = {
                "atom_count": int(after["atom_count"]),
                **packing,
                "coordinate_update_count": len(updates),
                "frequency_prior_penalty_delta": round(
                    float(packing["mean_frequency_prior_penalty_before"])
                    - float(packing["mean_frequency_prior_penalty_after"]),
                    6,
                ),
                "forcefield_energy_before": energy_before,
                "forcefield_energy_after": energy_after,
                "forcefield_energy_delta": round(energy_before - energy_after, 6),
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
                "revert_guard_triggered": reverted,
            }
    return {
        "target_id": target_id,
        "statistical_rotamer_status": "pass" if not blockers else "blocked",
        "source_pdb": _artifact(source),
        "out_pdb": _artifact(out_pdb),
        **metrics,
        **validation,
        "blockers": ",".join(sorted(set(blockers))),
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    rows = [_build_one(target_id, args) for target_id in _target_ids(args)]
    pass_count = sum(1 for row in rows if row["statistical_rotamer_status"] == "pass")
    total_before = sum(int(row.get("soft_clash_count_before", 0) or 0) for row in rows)
    total_after = sum(int(row.get("soft_clash_count_after", 0) or 0) for row in rows)
    summary = {
        "packet_type": "casp17_statistical_rotamer_packet",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "target_count": len(rows),
        "pass_count": pass_count,
        "blocked_count": len(rows) - pass_count,
        "statistical_rotamer_status": "pass" if rows and pass_count == len(rows) else "blocked",
        "source_dir": _artifact(args.source_dir),
        "out_dir": _artifact(args.out_dir),
        "selection_mode": "internal_residue_frequency_prior_sidechain_packing_not_worse",
        "total_soft_clash_count_before": total_before,
        "total_soft_clash_count_after": total_after,
        "total_soft_clash_delta": total_before - total_after,
        "total_coordinate_update_count": sum(int(row.get("coordinate_update_count", 0) or 0) for row in rows),
        "total_evaluated_residue_count": sum(int(row.get("evaluated_residue_count", 0) or 0) for row in rows),
        "total_packed_residue_count": sum(int(row.get("packed_residue_count", 0) or 0) for row in rows),
        "total_improved_residue_count": sum(int(row.get("improved_residue_count", 0) or 0) for row in rows),
        "total_statistical_rotamer_candidate_count": sum(int(row.get("statistical_rotamer_candidate_count", 0) or 0) for row in rows),
        "mean_frequency_prior_penalty_before": round(
            sum(float(row.get("mean_frequency_prior_penalty_before", 0.0) or 0.0) for row in rows) / len(rows),
            6,
        )
        if rows
        else 0.0,
        "mean_frequency_prior_penalty_after": round(
            sum(float(row.get("mean_frequency_prior_penalty_after", 0.0) or 0.0) for row in rows) / len(rows),
            6,
        )
        if rows
        else 0.0,
        "total_frequency_prior_penalty_delta": round(
            sum(float(row.get("frequency_prior_penalty_delta", 0.0) or 0.0) for row in rows),
            6,
        ),
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
        "claim_boundary": "Internal residue-specific frequency-prior rotamer packing proxy over generated CASP17 coordinates only; no external rotamer library, no public/template/native structures, not official MolProbity, and not portal submission.",
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Statistical Rotamer Packet",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- source_dir: `{summary['source_dir']}`",
        f"- out_dir: `{summary['out_dir']}`",
        f"- status: `{summary['statistical_rotamer_status']}`",
        f"- pass/blocked: `{summary['pass_count']}/{summary['blocked_count']}`",
        f"- selection_mode: `{summary['selection_mode']}`",
        f"- evaluated/packed/improved residues: `{summary['total_evaluated_residue_count']}/{summary['total_packed_residue_count']}/{summary['total_improved_residue_count']}`",
        f"- frequency prior penalty before/after/delta: `{summary['mean_frequency_prior_penalty_before']}/{summary['mean_frequency_prior_penalty_after']}/{summary['total_frequency_prior_penalty_delta']}`",
        f"- soft clashes before/after/delta: `{summary['total_soft_clash_count_before']}/{summary['total_soft_clash_count_after']}/{summary['total_soft_clash_delta']}`",
        f"- forcefield energy before/after/delta: `{summary['total_forcefield_energy_before']}/{summary['total_forcefield_energy_after']}/{summary['total_forcefield_energy_delta']}`",
        f"- hbond-like contacts before/after: `{summary['total_hbond_like_contact_count_before']}/{summary['total_hbond_like_contact_count_after']}`",
        f"- salt-bridge-like contacts before/after: `{summary['total_salt_bridge_like_contact_count_before']}/{summary['total_salt_bridge_like_contact_count_after']}`",
        f"- hydrophobic contacts before/after: `{summary['total_hydrophobic_contact_count_before']}/{summary['total_hydrophobic_contact_count_after']}`",
        "",
        "| target | status | evaluated | packed | updates | guard | prior before | prior after | energy before | energy after | soft before | soft after | hbond before/after | salt before/after | hydro before/after | format | geometry | confidence | blockers |",
        "| --- | --- | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['statistical_rotamer_status']}` | {row['evaluated_residue_count']} | "
            f"{row['packed_residue_count']} | {row['coordinate_update_count']} | `{row.get('revert_guard_triggered', False)}` | "
            f"{row['mean_frequency_prior_penalty_before']} | {row['mean_frequency_prior_penalty_after']} | "
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
    parser = argparse.ArgumentParser(description="Build an internal statistical-rotamer packing proxy packet for CASP17 generated TS predictions.")
    parser.add_argument("--target-watchlist-json", default=DEFAULT_WATCHLIST_JSON)
    parser.add_argument("--target-ids", default="")
    parser.add_argument("--source-dir", default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--sequence-dir", default=DEFAULT_SEQUENCE_DIR)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
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
