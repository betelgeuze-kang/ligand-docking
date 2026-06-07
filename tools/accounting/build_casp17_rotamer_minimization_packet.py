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

from tools import validate_casp17_confidence_calibration as confidence_validator
from tools import validate_casp17_geometry_sanity as geometry_validator
from tools import validate_casp17_ts_prediction as format_validator
from tools.build_casp17_all_atom_quality_packet import _inter_residue_contact_counts, _parse_first_model
from tools.build_casp17_sidechain_scaffold_packet import BACKBONE_ATOMS


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_WATCHLIST_JSON = "runs/casp17_target_watchlist_current.json"
DEFAULT_SOURCE_DIR = "runs/casp17_predictions_steric_relaxed_current"
DEFAULT_SEQUENCE_DIR = "runs/casp17_sequences_current"
DEFAULT_OUT_DIR = "runs/casp17_predictions_rotamer_minimized_current"
DEFAULT_OUT_JSON = "runs/casp17_rotamer_minimization_packet_current.json"
DEFAULT_OUT_CSV = "runs/casp17_rotamer_minimization_packet_current.csv"
DEFAULT_OUT_MD = "runs/casp17_rotamer_minimization_packet_current.md"

CELL_SIZE_A = 5.4
SOFT_DISTANCE_A = 1.10
SEVERE_DISTANCE_A = 0.80
NEAR_DISTANCE_A = 1.55
HBOND_MIN_A = 2.45
HBOND_MAX_A = 3.55
SALT_MIN_A = 2.6
SALT_MAX_A = 4.2
HYDROPHOBIC_MIN_A = 3.2
HYDROPHOBIC_MAX_A = 5.2
MAX_CANDIDATES_PER_RESIDUE = 8

ROTAMER_LIBRARY_DEG: dict[str, tuple[float, ...]] = {
    "ALA": (60.0, 180.0, -60.0),
    "ARG": (-60.0, 60.0, 180.0),
    "ASN": (-60.0, 180.0, 60.0),
    "ASP": (-60.0, 180.0, 60.0),
    "CYS": (-60.0, 60.0, 180.0),
    "GLN": (-60.0, 180.0, 60.0),
    "GLU": (-60.0, 180.0, 60.0),
    "HIS": (-60.0, 60.0, 180.0),
    "ILE": (-60.0, 180.0, 60.0),
    "LEU": (-60.0, 180.0, 60.0),
    "LYS": (-60.0, 180.0, 60.0),
    "MET": (-60.0, 180.0, 60.0),
    "PHE": (-60.0, 60.0, 180.0),
    "PRO": (30.0, -30.0, 90.0, -90.0),
    "SER": (-60.0, 60.0, 180.0),
    "THR": (-60.0, 60.0, 180.0),
    "TRP": (-60.0, 60.0, 180.0),
    "TYR": (-60.0, 60.0, 180.0),
    "VAL": (-60.0, 60.0, 180.0),
}

POLAR_RESIDUES = {"ARG", "ASN", "ASP", "GLN", "GLU", "HIS", "LYS", "SER", "THR", "TYR", "TRP", "CYS", "MET"}
ACIDIC_RESIDUES = {"ASP", "GLU"}
BASIC_RESIDUES = {"ARG", "HIS", "LYS"}
HYDROPHOBIC_RESIDUES = {"ALA", "CYS", "ILE", "LEU", "MET", "PHE", "PRO", "TRP", "TYR", "VAL"}


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _artifact(path_like: str | Path) -> str:
    path = _resolve(path_like).resolve()
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


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


def _record(line: str) -> str:
    return line[:6].strip().upper()


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


def _float_or_none(value: str) -> float | None:
    try:
        parsed = float(value.strip())
    except ValueError:
        return None
    return parsed if math.isfinite(parsed) else None


def _pdb_float(line: str, start: int, end: int, fallback_index: int) -> float | None:
    if len(line) >= end:
        parsed = _float_or_none(line[start:end])
        if parsed is not None:
            return parsed
    fields = line.split()
    if len(fields) > fallback_index:
        return _float_or_none(fields[fallback_index])
    return None


def _atom_key(line: str) -> tuple[str, int, str, str]:
    chain = line[21].strip() or "_" if len(line) > 21 else "_"
    try:
        resseq = int(line[22:26])
    except ValueError:
        fields = line.split()
        resseq = int(fields[5]) if len(fields) > 5 and fields[5].lstrip("-").isdigit() else 0
    insertion = line[26].strip() or "_" if len(line) > 26 else "_"
    atom = line[12:16].strip() if len(line) >= 16 else ""
    return chain, int(resseq), insertion, atom


def _parse_source(path_like: str | Path) -> tuple[list[str], list[dict[str, Any]]]:
    path = _resolve(path_like)
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    atoms: list[dict[str, Any]] = []
    seen_model = False
    in_first_model = False
    for line_index, line in enumerate(lines):
        rec = _record(line)
        if rec == "MODEL":
            if seen_model:
                break
            seen_model = True
            in_first_model = True
            continue
        if rec == "END" and in_first_model:
            break
        if rec != "ATOM" or (seen_model and not in_first_model):
            continue
        x = _pdb_float(line, 30, 38, 6)
        y = _pdb_float(line, 38, 46, 7)
        z = _pdb_float(line, 46, 54, 8)
        if x is None or y is None or z is None:
            continue
        chain, resseq, insertion, atom_name = _atom_key(line)
        atoms.append(
            {
                "line_index": line_index,
                "chain_id": chain,
                "resseq": int(resseq),
                "insertion_code": insertion,
                "atom_name": atom_name,
                "resname": line[17:20].strip().upper() if len(line) >= 20 else "UNK",
                "coord": (float(x), float(y), float(z)),
            }
        )
    return lines, atoms


def _sub(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return a[0] - b[0], a[1] - b[1], a[2] - b[2]


def _add(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return a[0] + b[0], a[1] + b[1], a[2] + b[2]


def _scale(a: tuple[float, float, float], scalar: float) -> tuple[float, float, float]:
    return a[0] * scalar, a[1] * scalar, a[2] * scalar


def _dot(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]


def _norm(a: tuple[float, float, float]) -> float:
    return math.sqrt(max(0.0, _dot(a, a)))


def _unit(a: tuple[float, float, float], fallback: tuple[float, float, float]) -> tuple[float, float, float]:
    value = _norm(a)
    if value < 1e-6:
        return fallback
    return a[0] / value, a[1] / value, a[2] / value


def _rotate_about_axis(
    vec: tuple[float, float, float],
    axis: tuple[float, float, float],
    degrees: float,
) -> tuple[float, float, float]:
    radians = math.radians(float(degrees))
    cosine = math.cos(radians)
    sine = math.sin(radians)
    axis = _unit(axis, (1.0, 0.0, 0.0))
    return _add(
        _add(_scale(vec, cosine), _scale(_cross(axis, vec), sine)),
        _scale(axis, _dot(axis, vec) * (1.0 - cosine)),
    )


def _angle_delta(left: float, right: float) -> float:
    return abs((left - right + 180.0) % 360.0 - 180.0)


def _cell(coord: tuple[float, float, float], cell_size: float = CELL_SIZE_A) -> tuple[int, int, int]:
    return tuple(math.floor(axis / cell_size) for axis in coord)


def _grid(atoms: list[dict[str, Any]]) -> dict[tuple[int, int, int], list[int]]:
    grid: dict[tuple[int, int, int], list[int]] = defaultdict(list)
    for index, atom in enumerate(atoms):
        grid[_cell(atom["coord"])].append(index)
    return grid


def _nearby_indices(grid: dict[tuple[int, int, int], list[int]], coord: tuple[float, float, float]) -> list[int]:
    cell = _cell(coord)
    indices: list[int] = []
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dz in (-1, 0, 1):
                indices.extend(grid.get((cell[0] + dx, cell[1] + dy, cell[2] + dz), []))
    return indices


def _distance_sq(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2


def _residue_key(atom: dict[str, Any]) -> tuple[str, int, str]:
    return str(atom["chain_id"]), int(atom["resseq"]), str(atom["insertion_code"])


def _same_residue(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return _residue_key(left) == _residue_key(right)


def _ca_tangent(residue_key: tuple[str, int, str], ca_by_chain: dict[str, list[dict[str, Any]]]) -> tuple[float, float, float]:
    chain_id, resseq, insertion = residue_key
    trace = ca_by_chain.get(chain_id, [])
    index = next(
        (idx for idx, atom in enumerate(trace) if int(atom["resseq"]) == int(resseq) and str(atom["insertion_code"]) == insertion),
        -1,
    )
    if index < 0 or not trace:
        return (1.0, 0.0, 0.0)
    ca = trace[index]["coord"]
    if len(trace) == 1:
        return (1.0, 0.0, 0.0)
    if index == 0:
        return _unit(_sub(trace[index + 1]["coord"], ca), (1.0, 0.0, 0.0))
    if index == len(trace) - 1:
        return _unit(_sub(ca, trace[index - 1]["coord"]), (1.0, 0.0, 0.0))
    return _unit(_sub(trace[index + 1]["coord"], trace[index - 1]["coord"]), (1.0, 0.0, 0.0))


def _normal_frame(tangent: tuple[float, float, float]) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    ref = (0.0, 0.0, 1.0)
    if _norm(_cross(tangent, ref)) < 1e-4:
        ref = (0.0, 1.0, 0.0)
    normal = _unit(_cross(ref, tangent), (0.0, 1.0, 0.0))
    binormal = _unit(_cross(tangent, normal), (0.0, 0.0, 1.0))
    return normal, binormal


def _pseudo_angle(
    ca: tuple[float, float, float],
    cb: tuple[float, float, float],
    normal: tuple[float, float, float],
    binormal: tuple[float, float, float],
) -> float:
    vec = _sub(cb, ca)
    return math.degrees(math.atan2(_dot(vec, binormal), _dot(vec, normal)))


def _is_polar_atom(atom: dict[str, Any]) -> bool:
    return str(atom["atom_name"]).strip()[:1] in {"N", "O", "S"} or str(atom["resname"]) in POLAR_RESIDUES


def _is_salt_pair(atom: dict[str, Any], other: dict[str, Any]) -> bool:
    left = str(atom["resname"])
    right = str(other["resname"])
    left_atom = str(atom["atom_name"])[:1]
    right_atom = str(other["atom_name"])[:1]
    return (
        (left in BASIC_RESIDUES and left_atom == "N" and right in ACIDIC_RESIDUES and right_atom == "O")
        or (right in BASIC_RESIDUES and right_atom == "N" and left in ACIDIC_RESIDUES and left_atom == "O")
    )


def _is_hydrophobic_pair(atom: dict[str, Any], other: dict[str, Any]) -> bool:
    return str(atom["resname"]) in HYDROPHOBIC_RESIDUES and str(other["resname"]) in HYDROPHOBIC_RESIDUES


def _interaction_counts(atoms: list[dict[str, Any]]) -> dict[str, int]:
    grid = _grid(atoms)
    hbond = 0
    salt = 0
    hydrophobic = 0
    seen: set[tuple[int, int]] = set()
    for index, atom in enumerate(atoms):
        coord = atom["coord"]
        for other_index in _nearby_indices(grid, coord):
            if other_index <= index or (index, other_index) in seen:
                continue
            other = atoms[other_index]
            if _same_residue(atom, other):
                continue
            seen.add((index, other_index))
            dist = math.sqrt(_distance_sq(coord, other["coord"]))
            if _is_salt_pair(atom, other) and SALT_MIN_A <= dist <= SALT_MAX_A:
                salt += 1
            if _is_polar_atom(atom) and _is_polar_atom(other) and HBOND_MIN_A <= dist <= HBOND_MAX_A:
                hbond += 1
            if _is_hydrophobic_pair(atom, other) and HYDROPHOBIC_MIN_A <= dist <= HYDROPHOBIC_MAX_A:
                hydrophobic += 1
    return {
        "hbond_like_contact_count": hbond,
        "salt_bridge_like_contact_count": salt,
        "hydrophobic_contact_count": hydrophobic,
    }


def _candidate_score(
    residue_atoms: list[dict[str, Any]],
    candidate_coords: dict[int, tuple[float, float, float]],
    all_atoms: list[dict[str, Any]],
    spatial_grid: dict[tuple[int, int, int], list[int]],
    current_coords: dict[int, tuple[float, float, float]],
    target_angle: float,
    selected_angle: float,
) -> float:
    severe_sq = SEVERE_DISTANCE_A * SEVERE_DISTANCE_A
    soft_sq = SOFT_DISTANCE_A * SOFT_DISTANCE_A
    near_sq = NEAR_DISTANCE_A * NEAR_DISTANCE_A
    residue_line_ids = {int(atom["line_index"]) for atom in residue_atoms}
    score = 0.0
    score += (_angle_delta(selected_angle, target_angle) / 60.0) ** 2 * 2.5
    for atom in residue_atoms:
        coord = candidate_coords[int(atom["line_index"])]
        for other_index in _nearby_indices(spatial_grid, coord):
            other = all_atoms[other_index]
            if int(other["line_index"]) in residue_line_ids:
                continue
            other_coord = current_coords.get(int(other["line_index"]), other["coord"])
            dist_sq = _distance_sq(coord, other_coord)
            if dist_sq < severe_sq:
                score += 16000.0 + (severe_sq - dist_sq) * 28000.0
            elif dist_sq < soft_sq:
                score += 450.0 + (soft_sq - dist_sq) * 700.0
            elif dist_sq < near_sq:
                score += (near_sq - dist_sq) * 16.0
            dist = math.sqrt(dist_sq)
            if _is_salt_pair(atom, other) and SALT_MIN_A <= dist <= SALT_MAX_A:
                score -= 12.0
            elif _is_polar_atom(atom) and _is_polar_atom(other) and HBOND_MIN_A <= dist <= HBOND_MAX_A:
                score -= 4.0
            elif _is_hydrophobic_pair(atom, other) and HYDROPHOBIC_MIN_A <= dist <= HYDROPHOBIC_MAX_A:
                score -= 0.5
        score += _distance_sq(coord, atom["coord"]) * 0.08
    return float(score)


def _minimize_atoms(atoms: list[dict[str, Any]]) -> tuple[dict[int, tuple[float, float, float]], dict[str, Any]]:
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
    minimized_residue_count = 0
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
        library = ROTAMER_LIBRARY_DEG.get(resname)
        if not library:
            continue
        ca = ca_atoms[0]["coord"]
        tangent = _ca_tangent(residue_key, ca_by_chain)
        normal, binormal = _normal_frame(tangent)
        current_angle = _pseudo_angle(ca, cb_atoms[0]["coord"], normal, binormal)
        nearest_prior = min(library, key=lambda angle: _angle_delta(current_angle, angle))
        prior_before = _angle_delta(current_angle, nearest_prior)
        total_prior_before += prior_before

        original = {int(atom["line_index"]): atom["coord"] for atom in sidechain_atoms}
        candidates: list[tuple[float, float, float, dict[int, tuple[float, float, float]]]] = []
        for target_angle in library:
            base_delta = (target_angle - current_angle + 180.0) % 360.0 - 180.0
            candidate: dict[int, tuple[float, float, float]] = {}
            selected_angle = current_angle + base_delta
            for atom in sidechain_atoms:
                rel = _sub(atom["coord"], ca)
                rotated = _rotate_about_axis(rel, tangent, base_delta)
                candidate[int(atom["line_index"])] = _add(ca, rotated)
            score = _candidate_score(
                sidechain_atoms,
                candidate,
                atoms,
                spatial_grid,
                current_coords,
                target_angle,
                selected_angle,
            )
            candidates.append((score, target_angle, selected_angle, candidate))
        original_score = _candidate_score(
            sidechain_atoms,
            original,
            atoms,
            spatial_grid,
            current_coords,
            nearest_prior,
            current_angle,
        )
        candidates.append((original_score, nearest_prior, current_angle, original))
        candidates.sort(key=lambda item: item[0])
        candidates = candidates[:MAX_CANDIDATES_PER_RESIDUE]
        best_score, best_prior, best_angle, best_candidate = candidates[0]
        candidate_count += len(candidates)
        minimized_residue_count += 1
        prior_after = _angle_delta(best_angle, best_prior)
        total_prior_after += prior_after
        if best_score < original_score - 1e-6:
            improved_residue_count += 1
            total_score_delta += original_score - best_score
        current_coords.update(best_candidate)
        updates.update(best_candidate)

    return updates, {
        "minimized_residue_count": minimized_residue_count,
        "improved_residue_count": improved_residue_count,
        "rotamer_candidate_count": candidate_count,
        "mean_energy_score_delta": round(total_score_delta / improved_residue_count, 6) if improved_residue_count else 0.0,
        "mean_rotamer_prior_deviation_before_deg": round(total_prior_before / minimized_residue_count, 3) if minimized_residue_count else 0.0,
        "mean_rotamer_prior_deviation_after_deg": round(total_prior_after / minimized_residue_count, 3) if minimized_residue_count else 0.0,
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
    remark = "REMARK CASP17 ROTAMER_MINIMIZATION internal residue-class rotamer-prior steric/polar minimization; not native-calibrated refinement"
    if any(line.startswith("REMARK CASP17 ROTAMER_MINIMIZATION") for line in lines):
        return lines
    out = lines[:]
    insert_index = next((index + 1 for index, line in enumerate(out) if _record(line) in {"SCORE", "QSCORE", "STOICH"}), None)
    if insert_index is None:
        insert_index = next((index + 1 for index, line in enumerate(out) if _record(line) == "MODEL"), 0)
    out.insert(insert_index, remark)
    return out


def _write_source(source: Path, out_pdb: Path, updates: dict[int, tuple[float, float, float]]) -> None:
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
        "minimized_residue_count": 0,
        "improved_residue_count": 0,
        "rotamer_candidate_count": 0,
        "coordinate_update_count": 0,
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
        "mean_rotamer_prior_deviation_before_deg": 0.0,
        "mean_rotamer_prior_deviation_after_deg": 0.0,
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
            updates, minimization = _minimize_atoms(atoms)
            _write_source(source, out_pdb, updates)
            after = _quality(out_pdb)
            if (
                int(after["soft_clash_count"]) > int(before["soft_clash_count"])
                or int(after["severe_clash_count"]) > int(before["severe_clash_count"])
            ):
                _write_source(source, out_pdb, {})
                after = before
                updates = {}
                minimization = {**minimization, "reverted_not_worse_guard": True}
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
        "rotamer_minimization_status": "pass" if not blockers else "blocked",
        "source_pdb": _artifact(source),
        "out_pdb": _artifact(out_pdb),
        **metrics,
        **validation,
        "blockers": ",".join(sorted(set(blockers))),
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    rows = [_build_one(target_id, args) for target_id in _target_ids(args)]
    pass_count = sum(1 for row in rows if row["rotamer_minimization_status"] == "pass")
    total_before = sum(int(row.get("soft_clash_count_before", 0) or 0) for row in rows)
    total_after = sum(int(row.get("soft_clash_count_after", 0) or 0) for row in rows)
    summary = {
        "packet_type": "casp17_rotamer_minimization_packet",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "target_count": len(rows),
        "pass_count": pass_count,
        "blocked_count": len(rows) - pass_count,
        "rotamer_minimization_status": "pass" if rows and pass_count == len(rows) else "blocked",
        "source_dir": _artifact(args.source_dir),
        "out_dir": _artifact(args.out_dir),
        "selection_mode": "residue_class_rotamer_prior_steric_polar_greedy",
        "total_soft_clash_count_before": total_before,
        "total_soft_clash_count_after": total_after,
        "total_soft_clash_delta": total_before - total_after,
        "total_coordinate_update_count": sum(int(row.get("coordinate_update_count", 0) or 0) for row in rows),
        "total_minimized_residue_count": sum(int(row.get("minimized_residue_count", 0) or 0) for row in rows),
        "total_improved_residue_count": sum(int(row.get("improved_residue_count", 0) or 0) for row in rows),
        "total_rotamer_candidate_count": sum(int(row.get("rotamer_candidate_count", 0) or 0) for row in rows),
        "revert_guard_count": sum(int(bool(row.get("revert_guard_triggered"))) for row in rows),
        "total_hbond_like_contact_count_before": sum(int(row.get("hbond_like_contact_count_before", 0) or 0) for row in rows),
        "total_hbond_like_contact_count_after": sum(int(row.get("hbond_like_contact_count_after", 0) or 0) for row in rows),
        "total_salt_bridge_like_contact_count_before": sum(int(row.get("salt_bridge_like_contact_count_before", 0) or 0) for row in rows),
        "total_salt_bridge_like_contact_count_after": sum(int(row.get("salt_bridge_like_contact_count_after", 0) or 0) for row in rows),
        "mean_rotamer_prior_deviation_before_deg": round(
            sum(float(row.get("mean_rotamer_prior_deviation_before_deg", 0.0) or 0.0) for row in rows) / len(rows), 3
        )
        if rows
        else 0.0,
        "mean_rotamer_prior_deviation_after_deg": round(
            sum(float(row.get("mean_rotamer_prior_deviation_after_deg", 0.0) or 0.0) for row in rows) / len(rows), 3
        )
        if rows
        else 0.0,
        "claim_boundary": "Internal residue-class rotamer-prior and steric/polar sidechain minimization over generated CASP17 coordinates only; not Dunbrack/Richardson library validation, not official MolProbity, not native accuracy evidence, and not portal submission.",
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Rotamer Minimization Packet",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- source_dir: `{summary['source_dir']}`",
        f"- out_dir: `{summary['out_dir']}`",
        f"- status: `{summary['rotamer_minimization_status']}`",
        f"- pass/blocked: `{summary['pass_count']}/{summary['blocked_count']}`",
        f"- selection_mode: `{summary['selection_mode']}`",
        f"- soft clashes before/after/delta: `{summary['total_soft_clash_count_before']}/{summary['total_soft_clash_count_after']}/{summary['total_soft_clash_delta']}`",
        f"- hbond-like contacts before/after: `{summary['total_hbond_like_contact_count_before']}/{summary['total_hbond_like_contact_count_after']}`",
        f"- salt-bridge-like contacts before/after: `{summary['total_salt_bridge_like_contact_count_before']}/{summary['total_salt_bridge_like_contact_count_after']}`",
        f"- rotamer prior deviation before/after: `{summary['mean_rotamer_prior_deviation_before_deg']}/{summary['mean_rotamer_prior_deviation_after_deg']}`",
        "",
        "| target | status | residues | improved | candidates | updates | guard | soft before | soft after | hbond before/after | salt before/after | prior before/after | format | geometry | confidence | blockers |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- | ---: | ---: | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['rotamer_minimization_status']}` | {row['minimized_residue_count']} | "
            f"{row['improved_residue_count']} | {row['rotamer_candidate_count']} | {row['coordinate_update_count']} | "
            f"`{row.get('revert_guard_triggered', False)}` | {row['soft_clash_count_before']} | {row['soft_clash_count_after']} | "
            f"{row['hbond_like_contact_count_before']}/{row['hbond_like_contact_count_after']} | "
            f"{row['salt_bridge_like_contact_count_before']}/{row['salt_bridge_like_contact_count_after']} | "
            f"{row['mean_rotamer_prior_deviation_before_deg']}/{row['mean_rotamer_prior_deviation_after_deg']} | "
            f"`{row['format_check_status']}` | `{row['geometry_sanity_status']}` | `{row['confidence_calibration_status']}` | {row['blockers'] or '-'} |"
        )
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build internal rotamer-prior steric/polar minimization packet for CASP17 generated TS predictions.")
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
