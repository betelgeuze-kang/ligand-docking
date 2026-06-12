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
    SALT_MAX_A,
    SALT_MIN_A,
    _add,
    _artifact,
    _distance_sq,
    _interaction_counts,
    _nearby_indices,
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
    _write_source,
)
from tools.build_casp17_sidechain_scaffold_packet import BACKBONE_ATOMS


DEFAULT_WATCHLIST_JSON = "runs/casp17_target_watchlist_current.json"
DEFAULT_SOURCE_DIR = "runs/casp17_predictions_rotamer_minimized_current"
DEFAULT_SEQUENCE_DIR = "runs/casp17_sequences_current"
DEFAULT_OUT_DIR = "runs/casp17_predictions_polar_refined_current"
DEFAULT_OUT_JSON = "runs/casp17_polar_refinement_packet_current.json"
DEFAULT_OUT_CSV = "runs/casp17_polar_refinement_packet_current.csv"
DEFAULT_OUT_MD = "runs/casp17_polar_refinement_packet_current.md"

CELL_SIZE_A = 5.4
SOFT_DISTANCE_A = 1.10
SEVERE_DISTANCE_A = 0.80
NEAR_DISTANCE_A = 1.55
MAX_SIDECHAIN_SHIFT_A = 0.14
POLAR_SEARCH_A = 4.8


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


def _grid(atoms: list[dict[str, Any]]) -> dict[tuple[int, int, int], list[int]]:
    grid: dict[tuple[int, int, int], list[int]] = defaultdict(list)
    for index, atom in enumerate(atoms):
        coord = atom["coord"]
        grid[tuple(math.floor(axis / CELL_SIZE_A) for axis in coord)].append(index)
    return grid


def _norm(vec: tuple[float, float, float]) -> float:
    return math.sqrt(max(0.0, vec[0] * vec[0] + vec[1] * vec[1] + vec[2] * vec[2]))


def _clip(vec: tuple[float, float, float], max_norm: float) -> tuple[float, float, float]:
    value = _norm(vec)
    if value <= max_norm or value < 1e-9:
        return vec
    return _scale(vec, max_norm / value)


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


def _candidate_shift(
    residue_atoms: list[dict[str, Any]],
    all_atoms: list[dict[str, Any]],
    spatial_grid: dict[tuple[int, int, int], list[int]],
    current_coords: dict[int, tuple[float, float, float]],
) -> tuple[float, float, float]:
    residue_line_ids = {int(atom["line_index"]) for atom in residue_atoms}
    force = (0.0, 0.0, 0.0)
    for atom in residue_atoms:
        coord = current_coords.get(int(atom["line_index"]), atom["coord"])
        for other_index in _nearby_indices(spatial_grid, coord):
            other = all_atoms[other_index]
            if int(other["line_index"]) in residue_line_ids:
                continue
            other_coord = current_coords.get(int(other["line_index"]), other["coord"])
            delta = _sub(other_coord, coord)
            dist = math.sqrt(_distance_sq(coord, other_coord))
            if dist < 1e-6 or dist > POLAR_SEARCH_A:
                continue
            direction = _unit(delta, (0.0, 0.0, 0.0))
            if dist < SOFT_DISTANCE_A:
                force = _add(force, _scale(direction, -0.18 * (SOFT_DISTANCE_A - dist)))
                continue
            if _is_salt_pair(atom, other):
                target = (SALT_MIN_A + SALT_MAX_A) / 2.0
                force = _add(force, _scale(direction, 0.045 * (dist - target)))
            elif _is_polar_atom(atom) and _is_polar_atom(other):
                target = (HBOND_MIN_A + HBOND_MAX_A) / 2.0
                force = _add(force, _scale(direction, 0.025 * (dist - target)))
    return _clip(force, MAX_SIDECHAIN_SHIFT_A)


def _candidate_score(
    residue_atoms: list[dict[str, Any]],
    shift: tuple[float, float, float],
    all_atoms: list[dict[str, Any]],
    spatial_grid: dict[tuple[int, int, int], list[int]],
    current_coords: dict[int, tuple[float, float, float]],
) -> float:
    severe_sq = SEVERE_DISTANCE_A * SEVERE_DISTANCE_A
    soft_sq = SOFT_DISTANCE_A * SOFT_DISTANCE_A
    near_sq = NEAR_DISTANCE_A * NEAR_DISTANCE_A
    residue_line_ids = {int(atom["line_index"]) for atom in residue_atoms}
    score = _norm(shift) * 3.5
    for atom in residue_atoms:
        coord = _add(current_coords.get(int(atom["line_index"]), atom["coord"]), shift)
        for other_index in _nearby_indices(spatial_grid, coord):
            other = all_atoms[other_index]
            if int(other["line_index"]) in residue_line_ids:
                continue
            other_coord = current_coords.get(int(other["line_index"]), other["coord"])
            dist_sq = _distance_sq(coord, other_coord)
            if dist_sq < severe_sq:
                score += 24000.0 + (severe_sq - dist_sq) * 36000.0
            elif dist_sq < soft_sq:
                score += 850.0 + (soft_sq - dist_sq) * 1000.0
            elif dist_sq < near_sq:
                score += (near_sq - dist_sq) * 20.0
            dist = math.sqrt(dist_sq)
            if _is_salt_pair(atom, other) and SALT_MIN_A <= dist <= SALT_MAX_A:
                score -= 18.0
            elif _is_polar_atom(atom) and _is_polar_atom(other) and HBOND_MIN_A <= dist <= HBOND_MAX_A:
                score -= 5.0
    return score


def _refine_atoms(atoms: list[dict[str, Any]]) -> tuple[dict[int, tuple[float, float, float]], dict[str, Any]]:
    by_residue: dict[tuple[str, int, str], list[dict[str, Any]]] = defaultdict(list)
    for atom in atoms:
        by_residue[_residue_key(atom)].append(atom)
    spatial_grid = _grid(atoms)
    current_coords = {int(atom["line_index"]): atom["coord"] for atom in atoms}
    updates: dict[int, tuple[float, float, float]] = {}
    refined_residue_count = 0
    improved_residue_count = 0
    candidate_count = 0
    total_score_delta = 0.0
    total_shift = 0.0

    for residue_key, residue_atoms_all in sorted(by_residue.items(), key=lambda item: item[0]):
        sidechain_atoms = [atom for atom in residue_atoms_all if atom["atom_name"] not in BACKBONE_ATOMS]
        if not sidechain_atoms:
            continue
        refined_residue_count += 1
        proposed = _candidate_shift(sidechain_atoms, atoms, spatial_grid, current_coords)
        candidates = [
            (0.0, 0.0, 0.0),
            proposed,
            _scale(proposed, 0.5),
            _scale(proposed, -0.35),
        ]
        scored = [
            (_candidate_score(sidechain_atoms, shift, atoms, spatial_grid, current_coords), shift)
            for shift in candidates
        ]
        candidate_count += len(scored)
        scored.sort(key=lambda item: item[0])
        original_score = _candidate_score(sidechain_atoms, (0.0, 0.0, 0.0), atoms, spatial_grid, current_coords)
        best_score, best_shift = scored[0]
        if _norm(best_shift) > 1e-6 and best_score < original_score - 1e-6:
            improved_residue_count += 1
            total_score_delta += original_score - best_score
            total_shift += _norm(best_shift)
            for atom in sidechain_atoms:
                line_index = int(atom["line_index"])
                new_coord = _add(current_coords[line_index], best_shift)
                current_coords[line_index] = new_coord
                updates[line_index] = new_coord
    return updates, {
        "refined_residue_count": refined_residue_count,
        "improved_residue_count": improved_residue_count,
        "polar_candidate_count": candidate_count,
        "mean_score_delta": round(total_score_delta / improved_residue_count, 6) if improved_residue_count else 0.0,
        "mean_sidechain_shift_A": round(total_shift / improved_residue_count, 6) if improved_residue_count else 0.0,
    }


def _insert_remark(lines: list[str]) -> list[str]:
    remark = "REMARK CASP17 POLAR_REFINEMENT internal sidechain-only hbond/salt/steric fine tuning; not native-calibrated refinement"
    if any(line.startswith("REMARK CASP17 POLAR_REFINEMENT") for line in lines):
        return lines
    out = lines[:]
    insert_index = next((index + 1 for index, line in enumerate(out) if _record(line) in {"SCORE", "QSCORE", "STOICH"}), None)
    if insert_index is None:
        insert_index = next((index + 1 for index, line in enumerate(out) if _record(line) == "MODEL"), 0)
    out.insert(insert_index, remark)
    return out


def _write_refined(source: Path, out_pdb: Path, updates: dict[int, tuple[float, float, float]]) -> None:
    lines, _atoms = _parse_source(source)
    tmp = out_pdb.with_suffix(".tmp.pdb")
    _write_source(source, tmp, updates)
    refined_lines = _insert_remark(tmp.read_text(encoding="utf-8").splitlines())
    out_pdb.parent.mkdir(parents=True, exist_ok=True)
    out_pdb.write_text("\n".join(refined_lines) + "\n", encoding="utf-8")
    tmp.unlink(missing_ok=True)


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
        "refined_residue_count": 0,
        "improved_residue_count": 0,
        "polar_candidate_count": 0,
        "coordinate_update_count": 0,
        "mean_score_delta": 0.0,
        "mean_sidechain_shift_A": 0.0,
        "soft_clash_count_before": 0,
        "soft_clash_count_after": 0,
        "severe_clash_count_before": 0,
        "severe_clash_count_after": 0,
        "hbond_like_contact_count_before": 0,
        "hbond_like_contact_count_after": 0,
        "salt_bridge_like_contact_count_before": 0,
        "salt_bridge_like_contact_count_after": 0,
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
            updates, refinement = _refine_atoms(atoms)
            _write_refined(source, out_pdb, updates)
            after = _quality(out_pdb)
            polar_before = int(before["hbond_like_contact_count"]) + int(before["salt_bridge_like_contact_count"])
            polar_after = int(after["hbond_like_contact_count"]) + int(after["salt_bridge_like_contact_count"])
            if (
                int(after["soft_clash_count"]) > int(before["soft_clash_count"])
                or int(after["severe_clash_count"]) > int(before["severe_clash_count"])
                or polar_after < polar_before
            ):
                _write_refined(source, out_pdb, {})
                after = before
                updates = {}
                refinement = {**refinement, "reverted_not_worse_guard": True}
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
                blockers.append("severe_clash_after_refinement")
            if int(after["soft_clash_count"]) > int(before["soft_clash_count"]):
                blockers.append("soft_clash_regression")
            metrics = {
                "atom_count": int(after["atom_count"]),
                **refinement,
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
                "polar_contact_delta": (
                    int(after["hbond_like_contact_count"])
                    + int(after["salt_bridge_like_contact_count"])
                    - int(before["hbond_like_contact_count"])
                    - int(before["salt_bridge_like_contact_count"])
                ),
                "revert_guard_triggered": bool(refinement.get("reverted_not_worse_guard")),
            }
    return {
        "target_id": target_id,
        "polar_refinement_status": "pass" if not blockers else "blocked",
        "source_pdb": _artifact(source),
        "out_pdb": _artifact(out_pdb),
        **metrics,
        **validation,
        "blockers": ",".join(sorted(set(blockers))),
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    rows = [_build_one(target_id, args) for target_id in _target_ids(args)]
    pass_count = sum(1 for row in rows if row["polar_refinement_status"] == "pass")
    total_before = sum(int(row.get("soft_clash_count_before", 0) or 0) for row in rows)
    total_after = sum(int(row.get("soft_clash_count_after", 0) or 0) for row in rows)
    summary = {
        "packet_type": "casp17_polar_refinement_packet",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "target_count": len(rows),
        "pass_count": pass_count,
        "blocked_count": len(rows) - pass_count,
        "polar_refinement_status": "pass" if rows and pass_count == len(rows) else "blocked",
        "source_dir": _artifact(args.source_dir),
        "out_dir": _artifact(args.out_dir),
        "selection_mode": "sidechain_only_hbond_salt_steric_fine_tune_not_worse",
        "total_soft_clash_count_before": total_before,
        "total_soft_clash_count_after": total_after,
        "total_soft_clash_delta": total_before - total_after,
        "total_coordinate_update_count": sum(int(row.get("coordinate_update_count", 0) or 0) for row in rows),
        "total_refined_residue_count": sum(int(row.get("refined_residue_count", 0) or 0) for row in rows),
        "total_improved_residue_count": sum(int(row.get("improved_residue_count", 0) or 0) for row in rows),
        "total_polar_candidate_count": sum(int(row.get("polar_candidate_count", 0) or 0) for row in rows),
        "revert_guard_count": sum(int(bool(row.get("revert_guard_triggered"))) for row in rows),
        "total_hbond_like_contact_count_before": sum(int(row.get("hbond_like_contact_count_before", 0) or 0) for row in rows),
        "total_hbond_like_contact_count_after": sum(int(row.get("hbond_like_contact_count_after", 0) or 0) for row in rows),
        "total_salt_bridge_like_contact_count_before": sum(int(row.get("salt_bridge_like_contact_count_before", 0) or 0) for row in rows),
        "total_salt_bridge_like_contact_count_after": sum(int(row.get("salt_bridge_like_contact_count_after", 0) or 0) for row in rows),
        "total_polar_contact_delta": sum(int(row.get("polar_contact_delta", 0) or 0) for row in rows),
        "claim_boundary": "Internal sidechain-only hydrogen-bond/salt/steric fine tuning over generated CASP17 coordinates only; not official MolProbity, not native accuracy evidence, not forcefield minimization, and not portal submission.",
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Polar Refinement Packet",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- source_dir: `{summary['source_dir']}`",
        f"- out_dir: `{summary['out_dir']}`",
        f"- status: `{summary['polar_refinement_status']}`",
        f"- pass/blocked: `{summary['pass_count']}/{summary['blocked_count']}`",
        f"- selection_mode: `{summary['selection_mode']}`",
        f"- soft clashes before/after/delta: `{summary['total_soft_clash_count_before']}/{summary['total_soft_clash_count_after']}/{summary['total_soft_clash_delta']}`",
        f"- hbond-like contacts before/after: `{summary['total_hbond_like_contact_count_before']}/{summary['total_hbond_like_contact_count_after']}`",
        f"- salt-bridge-like contacts before/after: `{summary['total_salt_bridge_like_contact_count_before']}/{summary['total_salt_bridge_like_contact_count_after']}`",
        f"- total polar contact delta: `{summary['total_polar_contact_delta']}`",
        "",
        "| target | status | residues | improved | candidates | updates | guard | soft before | soft after | hbond before/after | salt before/after | polar delta | format | geometry | confidence | blockers |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- | ---: | ---: | --- | --- | ---: | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['polar_refinement_status']}` | {row['refined_residue_count']} | "
            f"{row['improved_residue_count']} | {row['polar_candidate_count']} | {row['coordinate_update_count']} | "
            f"`{row.get('revert_guard_triggered', False)}` | {row['soft_clash_count_before']} | {row['soft_clash_count_after']} | "
            f"{row['hbond_like_contact_count_before']}/{row['hbond_like_contact_count_after']} | "
            f"{row['salt_bridge_like_contact_count_before']}/{row['salt_bridge_like_contact_count_after']} | "
            f"{row.get('polar_contact_delta', 0)} | `{row['format_check_status']}` | `{row['geometry_sanity_status']}` | "
            f"`{row['confidence_calibration_status']}` | {row['blockers'] or '-'} |"
        )
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build internal sidechain-only polar fine-tuning packet for CASP17 generated TS predictions.")
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
