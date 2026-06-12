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


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_WATCHLIST_JSON = "runs/casp17_target_watchlist_current.json"
DEFAULT_SOURCE_DIR = "runs/casp17_predictions_scored_current"
DEFAULT_SEQUENCE_DIR = "runs/casp17_sequences_current"
DEFAULT_OUT_DIR = "runs/casp17_predictions_sidechain_scaffold_current"
DEFAULT_OUT_JSON = "runs/casp17_sidechain_scaffold_packet_current.json"
DEFAULT_OUT_CSV = "runs/casp17_sidechain_scaffold_packet_current.csv"
DEFAULT_OUT_MD = "runs/casp17_sidechain_scaffold_packet_current.md"

BACKBONE_ATOMS = ("N", "CA", "C", "O")
SIDECHAIN_ATOMS: dict[str, tuple[str, ...]] = {
    "ALA": ("CB",),
    "ARG": ("CB", "CG", "CD", "NE", "CZ", "NH1", "NH2"),
    "ASN": ("CB", "CG", "OD1", "ND2"),
    "ASP": ("CB", "CG", "OD1", "OD2"),
    "CYS": ("CB", "SG"),
    "GLN": ("CB", "CG", "CD", "OE1", "NE2"),
    "GLU": ("CB", "CG", "CD", "OE1", "OE2"),
    "GLY": (),
    "HIS": ("CB", "CG", "ND1", "CD2", "CE1", "NE2"),
    "ILE": ("CB", "CG1", "CG2", "CD1"),
    "LEU": ("CB", "CG", "CD1", "CD2"),
    "LYS": ("CB", "CG", "CD", "CE", "NZ"),
    "MET": ("CB", "CG", "SD", "CE"),
    "PHE": ("CB", "CG", "CD1", "CD2", "CE1", "CE2", "CZ"),
    "PRO": ("CB", "CG", "CD"),
    "SER": ("CB", "OG"),
    "THR": ("CB", "OG1", "CG2"),
    "TRP": ("CB", "CG", "CD1", "CD2", "NE1", "CE2", "CE3", "CZ2", "CZ3", "CH2"),
    "TYR": ("CB", "CG", "CD1", "CD2", "CE1", "CE2", "CZ", "OH"),
    "VAL": ("CB", "CG1", "CG2"),
}
STANDARD_HEAVY_ATOMS = {resname: set(BACKBONE_ATOMS) | set(sidechain) for resname, sidechain in SIDECHAIN_ATOMS.items()}
HYDROPHOBIC_RESIDUES = {"ALA", "CYS", "ILE", "LEU", "MET", "PHE", "PRO", "TRP", "TYR", "VAL"}
CHARGED_OR_POLAR_RESIDUES = {"ARG", "ASN", "ASP", "GLN", "GLU", "HIS", "LYS", "SER", "THR", "TYR"}
ROTAMER_FRAME_ANGLES_DEG = (-140.0, -80.0, -20.0, 40.0, 100.0, 160.0)
ROTAMER_SPATIAL_CELL_SIZE = 1.7


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


def _record(line: str) -> str:
    return line[:6].strip().upper()


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
    return explicit or _current_open_targets(_read_json(args.target_watchlist_json))


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
    return chain, resseq, insertion, atom


def _parse_source(path_like: str | Path) -> tuple[list[str], list[str], dict[tuple[str, int, str], dict[str, Any]]]:
    path = _resolve(path_like)
    header: list[str] = []
    model_metadata: list[str] = []
    residues: dict[tuple[str, int, str], dict[str, Any]] = {}
    in_first_model = False
    seen_model = False
    model_metadata_open = False
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.rstrip("\r\n")
        rec = _record(line)
        if rec == "MODEL":
            if seen_model:
                break
            seen_model = True
            in_first_model = True
            model_metadata_open = True
            continue
        if not seen_model:
            if rec not in {"SCORE", "QSCORE"} and not line.startswith("REMARK CASP17 SIDECHAIN_SCAFFOLD"):
                header.append(line)
            continue
        if rec == "END" and in_first_model:
            break
        if not in_first_model:
            continue
        if rec in {"SCORE", "QSCORE", "STOICH"} and model_metadata_open:
            model_metadata.append(line)
            continue
        if rec in {"PARENT", "ATOM", "TER"}:
            model_metadata_open = False
        if rec != "ATOM":
            continue
        chain, resseq, insertion, atom_name = _atom_key(line)
        if atom_name != "CA":
            continue
        coord = (
            _pdb_float(line, 30, 38, 6),
            _pdb_float(line, 38, 46, 7),
            _pdb_float(line, 46, 54, 8),
        )
        if any(value is None for value in coord):
            continue
        key = (chain, resseq, insertion)
        residues[key] = {
            "chain_id": chain,
            "resseq": resseq,
            "insertion_code": insertion,
            "resname": line[17:20].strip().upper() if len(line) >= 20 else "UNK",
            "ca": (float(coord[0]), float(coord[1]), float(coord[2])),
            "b_factor": _pdb_float(line, 60, 66, 10) or 50.0,
        }
    return header, model_metadata, residues


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


def _frame(trace: list[dict[str, Any]], index: int) -> tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]:
    ca = trace[index]["ca"]
    if len(trace) == 1:
        tangent = (1.0, 0.0, 0.0)
    elif index == 0:
        tangent = _unit(_sub(trace[1]["ca"], ca), (1.0, 0.0, 0.0))
    elif index == len(trace) - 1:
        tangent = _unit(_sub(ca, trace[index - 1]["ca"]), (1.0, 0.0, 0.0))
    else:
        tangent = _unit(_sub(trace[index + 1]["ca"], trace[index - 1]["ca"]), (1.0, 0.0, 0.0))
    ref = (0.0, 0.0, 1.0)
    if _norm(_cross(tangent, ref)) < 1e-4:
        ref = (0.0, 1.0, 0.0)
    normal = _unit(_cross(ref, tangent), (0.0, 1.0, 0.0))
    binormal = _unit(_cross(tangent, normal), (0.0, 0.0, 1.0))
    return tangent, normal, binormal


def _coord(
    ca: tuple[float, float, float],
    tangent: tuple[float, float, float],
    normal: tuple[float, float, float],
    binormal: tuple[float, float, float],
    t: float,
    n: float,
    b: float,
) -> tuple[float, float, float]:
    return _add(_add(_add(ca, _scale(tangent, t)), _scale(normal, n)), _scale(binormal, b))


def _sidechain_coord(
    atom_name: str,
    ordinal: int,
    ca: tuple[float, float, float],
    tangent: tuple[float, float, float],
    normal: tuple[float, float, float],
    binormal: tuple[float, float, float],
) -> tuple[float, float, float]:
    if atom_name == "CB":
        return _coord(ca, tangent, normal, binormal, -0.22, 1.46, -0.48)
    level = 1 + max(0, ordinal - 1) // 2
    branch = -0.72 if ordinal % 2 else 0.72
    if atom_name[-1:].isdigit():
        branch *= 1.18 if int(atom_name[-1]) % 2 else -1.18
    if atom_name.startswith(("O", "N", "S")):
        branch *= 0.82
    if atom_name in {"CZ", "CE", "NE", "NZ", "OH", "SG", "SD", "CH2"}:
        level += 1
    return _coord(
        ca,
        tangent,
        normal,
        binormal,
        0.24 * ((ordinal % 3) - 1),
        1.45 + 1.02 * level,
        branch,
    )


def _rotate_frame_about_tangent(
    normal: tuple[float, float, float],
    binormal: tuple[float, float, float],
    degrees: float,
) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    radians = math.radians(float(degrees))
    cosine = math.cos(radians)
    sine = math.sin(radians)
    rotated_normal = _add(_scale(normal, cosine), _scale(binormal, sine))
    rotated_binormal = _add(_scale(normal, -sine), _scale(binormal, cosine))
    return _unit(rotated_normal, normal), _unit(rotated_binormal, binormal)


def _distance_sq(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2


def _sidechain_coords(
    sidechain: tuple[str, ...],
    ca: tuple[float, float, float],
    tangent: tuple[float, float, float],
    normal: tuple[float, float, float],
    binormal: tuple[float, float, float],
) -> list[tuple[str, tuple[float, float, float]]]:
    return [
        (atom_name, _sidechain_coord(atom_name, ordinal, ca, tangent, normal, binormal))
        for ordinal, atom_name in enumerate(sidechain)
    ]


def _rotamer_candidate_score(
    *,
    resname: str,
    chain_id: str,
    resseq: int,
    insertion: str,
    ca: tuple[float, float, float],
    candidate: list[tuple[str, tuple[float, float, float]]],
    placed_atoms: list[tuple[tuple[str, int, str, str], tuple[float, float, float]]],
    placed_grid: dict[tuple[int, int, int], list[int]],
    all_ca: list[tuple[str, int, str, tuple[float, float, float]]],
    ca_grid: dict[tuple[int, int, int], list[int]],
    chain_centroid: tuple[float, float, float],
) -> float:
    score = 0.0
    residue_identity = (chain_id, int(resseq), insertion, "_")
    for _atom_name, coord in candidate:
        for other_index in _nearby_grid_indices(placed_grid, coord, ROTAMER_SPATIAL_CELL_SIZE):
            other_identity, other_coord = placed_atoms[other_index]
            if _same_residue(residue_identity, other_identity):
                continue
            dist_sq = _distance_sq(coord, other_coord)
            if dist_sq < 0.82 * 0.82:
                score += 5000.0 + (0.82 * 0.82 - dist_sq) * 10000.0
            elif dist_sq < 1.35 * 1.35:
                score += (1.35 * 1.35 - dist_sq) * 90.0
        for other_index in _nearby_grid_indices(ca_grid, coord, ROTAMER_SPATIAL_CELL_SIZE):
            other_chain, other_resseq, other_insertion, other_ca = all_ca[other_index]
            if other_chain == chain_id and other_resseq == int(resseq) and other_insertion == insertion:
                continue
            dist_sq = _distance_sq(coord, other_ca)
            if dist_sq < 1.0 * 1.0:
                score += 2500.0 + (1.0 * 1.0 - dist_sq) * 4000.0
            elif dist_sq < 1.65 * 1.65:
                score += (1.65 * 1.65 - dist_sq) * 35.0
    if candidate:
        cb_vector = _unit(_sub(candidate[0][1], ca), (0.0, 1.0, 0.0))
        center_vector = _unit(_sub(chain_centroid, ca), (0.0, 1.0, 0.0))
        core_alignment = _dot(cb_vector, center_vector)
        if resname in HYDROPHOBIC_RESIDUES:
            score -= 0.20 * core_alignment
        elif resname in CHARGED_OR_POLAR_RESIDUES:
            score += 0.10 * core_alignment
    return float(score)


def _select_sidechain_candidate(
    *,
    resname: str,
    sidechain: tuple[str, ...],
    chain_id: str,
    resseq: int,
    insertion: str,
    ca: tuple[float, float, float],
    tangent: tuple[float, float, float],
    normal: tuple[float, float, float],
    binormal: tuple[float, float, float],
    placed_atoms: list[tuple[tuple[str, int, str, str], tuple[float, float, float]]],
    placed_grid: dict[tuple[int, int, int], list[int]],
    all_ca: list[tuple[str, int, str, tuple[float, float, float]]],
    ca_grid: dict[tuple[int, int, int], list[int]],
    chain_centroid: tuple[float, float, float],
) -> tuple[list[tuple[str, tuple[float, float, float]]], int, float]:
    if not sidechain:
        return [], 0, 0.0
    candidates: list[tuple[float, list[tuple[str, tuple[float, float, float]]]]] = []
    for angle in ROTAMER_FRAME_ANGLES_DEG:
        candidate_normal, candidate_binormal = _rotate_frame_about_tangent(normal, binormal, angle)
        candidate = _sidechain_coords(sidechain, ca, tangent, candidate_normal, candidate_binormal)
        candidates.append(
            (
                _rotamer_candidate_score(
                    resname=resname,
                    chain_id=chain_id,
                    resseq=resseq,
                    insertion=insertion,
                    ca=ca,
                    candidate=candidate,
                    placed_atoms=placed_atoms,
                    placed_grid=placed_grid,
                    all_ca=all_ca,
                    ca_grid=ca_grid,
                    chain_centroid=chain_centroid,
                ),
                candidate,
            )
        )
    best_score, best_candidate = min(candidates, key=lambda item: item[0])
    return best_candidate, len(candidates), float(best_score)


def _element(atom_name: str) -> str:
    stripped = atom_name.strip()
    if not stripped:
        return "C"
    if stripped[0].isdigit() and len(stripped) > 1:
        stripped = stripped[1:]
    if stripped.startswith(("CL", "BR")):
        return stripped[:2].title()
    return stripped[0].upper()


def _atom_line(
    serial: int,
    atom_name: str,
    resname: str,
    chain_id: str,
    resseq: int,
    coord: tuple[float, float, float],
    b_factor: float,
) -> str:
    x, y, z = coord
    return (
        f"ATOM  {serial:5d} {atom_name:<4} {resname:>3} {chain_id:1}{resseq:4d}    "
        f"{x:8.3f}{y:8.3f}{z:8.3f}{1.00:6.2f}{float(b_factor):6.2f}          {_element(atom_name):>2}  "
    )


def _line_coord(line: str) -> tuple[float, float, float] | None:
    coord = (_pdb_float(line, 30, 38, 6), _pdb_float(line, 38, 46, 7), _pdb_float(line, 46, 54, 8))
    if any(value is None for value in coord):
        return None
    return float(coord[0]), float(coord[1]), float(coord[2])


def _atom_identity(line: str) -> tuple[str, int, str, str]:
    chain, resseq, insertion, atom_name = _atom_key(line)
    return chain, int(resseq), insertion, atom_name


def _cell(coord: tuple[float, float, float], cell_size: float) -> tuple[int, int, int]:
    return tuple(math.floor(axis / cell_size) for axis in coord)


def _nearby_grid_indices(
    grid: dict[tuple[int, int, int], list[int]],
    coord: tuple[float, float, float],
    cell_size: float,
) -> list[int]:
    cell = _cell(coord, cell_size)
    indices: list[int] = []
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dz in (-1, 0, 1):
                indices.extend(grid.get((cell[0] + dx, cell[1] + dy, cell[2] + dz), []))
    return indices


def _same_residue(left: tuple[str, int, str, str], right: tuple[str, int, str, str]) -> bool:
    return left[:3] == right[:3]


def _is_backbone(identity: tuple[str, int, str, str]) -> bool:
    return identity[3] in BACKBONE_ATOMS


def _prune_severe_sidechain_clashes(lines: list[str], *, threshold: float = 0.82, max_iterations: int = 4) -> tuple[list[str], int]:
    current = lines[:]
    total_removed = 0
    threshold_sq = float(threshold) * float(threshold)
    for _iteration in range(max(1, int(max_iterations))):
        grid: dict[tuple[int, int, int], list[int]] = defaultdict(list)
        atoms: list[dict[str, Any]] = []
        removed: set[int] = set()
        for line_index, line in enumerate(current):
            if _record(line) != "ATOM":
                continue
            coord = _line_coord(line)
            if coord is None:
                continue
            identity = _atom_identity(line)
            atom_index = len(atoms)
            atoms.append({"line_index": line_index, "coord": coord, "identity": identity})
            cell = _cell(coord, threshold)
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for dz in (-1, 0, 1):
                        for other_index in grid.get((cell[0] + dx, cell[1] + dy, cell[2] + dz), []):
                            if other_index in removed or atom_index in removed:
                                continue
                            other = atoms[other_index]
                            if _same_residue(identity, other["identity"]):
                                continue
                            other_coord = other["coord"]
                            dist_sq = (
                                (coord[0] - other_coord[0]) ** 2
                                + (coord[1] - other_coord[1]) ** 2
                                + (coord[2] - other_coord[2]) ** 2
                            )
                            if dist_sq >= threshold_sq:
                                continue
                            current_is_backbone = _is_backbone(identity)
                            other_is_backbone = _is_backbone(other["identity"])
                            if current_is_backbone and other_is_backbone:
                                continue
                            if not current_is_backbone:
                                removed.add(atom_index)
                            elif not other_is_backbone:
                                removed.add(other_index)
            if atom_index not in removed:
                grid[cell].append(atom_index)
        if not removed:
            break
        removed_line_indices = {atoms[index]["line_index"] for index in removed}
        current = [line for index, line in enumerate(current) if index not in removed_line_indices]
        total_removed += len(removed)
    return current, total_removed


def _rebuild_atoms(residues: dict[tuple[str, int, str], dict[str, Any]]) -> tuple[list[str], dict[str, Any]]:
    by_chain: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for residue in residues.values():
        by_chain[str(residue["chain_id"])].append(residue)
    for chain in by_chain.values():
        chain.sort(key=lambda item: (int(item["resseq"]), str(item["insertion_code"])))
    all_ca = [
        (str(residue["chain_id"]), int(residue["resseq"]), str(residue["insertion_code"]), residue["ca"])
        for chain in by_chain.values()
        for residue in chain
    ]
    ca_grid: dict[tuple[int, int, int], list[int]] = defaultdict(list)
    for ca_index, (_chain_id, _resseq, _insertion, ca_coord) in enumerate(all_ca):
        ca_grid[_cell(ca_coord, ROTAMER_SPATIAL_CELL_SIZE)].append(ca_index)
    chain_centroids: dict[str, tuple[float, float, float]] = {}
    for chain_id, chain in by_chain.items():
        if not chain:
            chain_centroids[chain_id] = (0.0, 0.0, 0.0)
            continue
        chain_centroids[chain_id] = (
            sum(float(residue["ca"][0]) for residue in chain) / len(chain),
            sum(float(residue["ca"][1]) for residue in chain) / len(chain),
            sum(float(residue["ca"][2]) for residue in chain) / len(chain),
        )

    lines: list[str] = []
    placed_atoms: list[tuple[tuple[str, int, str, str], tuple[float, float, float]]] = []
    placed_grid: dict[tuple[int, int, int], list[int]] = defaultdict(list)
    serial = 1
    expected_atom_count = 0
    emitted_atom_count = 0
    unknown_residue_count = 0
    rotamer_candidate_count = 0
    rotamer_selected_residue_count = 0
    rotamer_score_sum = 0.0
    for chain_id in sorted(by_chain):
        trace = by_chain[chain_id]
        lines.append("PARENT N/A")
        for index, residue in enumerate(trace):
            resname = residue["resname"] if residue["resname"] in SIDECHAIN_ATOMS else "UNK"
            if resname == "UNK":
                unknown_residue_count += 1
            sidechain = SIDECHAIN_ATOMS.get(resname, ())
            expected_atom_count += len(BACKBONE_ATOMS) + len(sidechain)
            ca = residue["ca"]
            tangent, normal, binormal = _frame(trace, index)
            backbone_coords = {
                "N": _coord(ca, tangent, normal, binormal, -0.36, 0.16, 0.00),
                "CA": ca,
                "C": _coord(ca, tangent, normal, binormal, 0.36, 0.16, 0.00),
                "O": _coord(ca, tangent, normal, binormal, 0.48, 0.34, 0.12),
            }
            for atom_name in BACKBONE_ATOMS:
                coord = backbone_coords[atom_name]
                lines.append(
                    _atom_line(
                        serial,
                        atom_name,
                        resname,
                        chain_id,
                        int(residue["resseq"]),
                        coord,
                        float(residue["b_factor"]),
                    )
                )
                placed_index = len(placed_atoms)
                placed_atoms.append(((chain_id, int(residue["resseq"]), str(residue["insertion_code"]), atom_name), coord))
                placed_grid[_cell(coord, ROTAMER_SPATIAL_CELL_SIZE)].append(placed_index)
                serial += 1
                emitted_atom_count += 1
            selected_sidechain, candidate_count, rotamer_score = _select_sidechain_candidate(
                resname=resname,
                sidechain=sidechain,
                chain_id=chain_id,
                resseq=int(residue["resseq"]),
                insertion=str(residue["insertion_code"]),
                ca=ca,
                tangent=tangent,
                normal=normal,
                binormal=binormal,
                placed_atoms=placed_atoms,
                placed_grid=placed_grid,
                all_ca=all_ca,
                ca_grid=ca_grid,
                chain_centroid=chain_centroids[chain_id],
            )
            rotamer_candidate_count += candidate_count
            if selected_sidechain:
                rotamer_selected_residue_count += 1
                rotamer_score_sum += rotamer_score
            for atom_name, coord in selected_sidechain:
                lines.append(
                    _atom_line(
                        serial,
                        atom_name,
                        resname,
                        chain_id,
                        int(residue["resseq"]),
                        coord,
                        float(residue["b_factor"]),
                    )
                )
                placed_index = len(placed_atoms)
                placed_atoms.append(((chain_id, int(residue["resseq"]), str(residue["insertion_code"]), atom_name), coord))
                placed_grid[_cell(coord, ROTAMER_SPATIAL_CELL_SIZE)].append(placed_index)
                serial += 1
                emitted_atom_count += 1
        lines.append("TER")
    pruned_lines, pruned_atom_count = _prune_severe_sidechain_clashes(lines)
    emitted_after_prune = sum(1 for line in pruned_lines if _record(line) == "ATOM")
    return pruned_lines, {
        "chain_count": len(by_chain),
        "residue_count": len(residues),
        "expected_heavy_atom_count": expected_atom_count,
        "emitted_heavy_atom_count": emitted_after_prune,
        "pre_prune_heavy_atom_count": emitted_atom_count,
        "pruned_sidechain_atom_count": pruned_atom_count,
        "rotamer_candidate_count": rotamer_candidate_count,
        "rotamer_selected_residue_count": rotamer_selected_residue_count,
        "mean_rotamer_candidate_score": round(rotamer_score_sum / rotamer_selected_residue_count, 6) if rotamer_selected_residue_count else 0.0,
        "unknown_residue_count": unknown_residue_count,
        "heavy_atom_completion_fraction": round(emitted_after_prune / expected_atom_count if expected_atom_count else 0.0, 6),
    }


def _build_one(target_id: str, args: argparse.Namespace) -> dict[str, Any]:
    source = _resolve(args.source_dir) / f"{target_id}TS.pdb"
    sequence_path = _resolve(args.sequence_dir) / f"{target_id}.fasta"
    out_pdb = _resolve(args.out_dir) / f"{target_id}TS.pdb"
    blockers: list[str] = []
    if not source.exists():
        blockers.append("source_prediction_missing")
    if not sequence_path.exists():
        blockers.append("sequence_file_missing")
    metrics = {
        "chain_count": 0,
        "residue_count": 0,
        "expected_heavy_atom_count": 0,
        "emitted_heavy_atom_count": 0,
        "pre_prune_heavy_atom_count": 0,
        "pruned_sidechain_atom_count": 0,
        "rotamer_candidate_count": 0,
        "rotamer_selected_residue_count": 0,
        "mean_rotamer_candidate_score": 0.0,
        "unknown_residue_count": 0,
        "heavy_atom_completion_fraction": 0.0,
    }
    validation = {
        "format_check_status": "not_run",
        "geometry_sanity_status": "not_run",
        "confidence_calibration_status": "not_run",
    }
    if not blockers:
        header, model_metadata, residues = _parse_source(source)
        if not residues:
            blockers.append("ca_residues_missing")
        else:
            rebuilt, metrics = _rebuild_atoms(residues)
            lines = [
                *(line for line in header if _record(line) not in {"SCORE", "QSCORE"}),
                "MODEL 1",
                *model_metadata,
                "REMARK CASP17 SIDECHAIN_SCAFFOLD residue-specific heavy-atom scaffold with local frame-rotamer selection; not native-calibrated all-atom refinement",
                *rebuilt,
                "END",
                "",
            ]
            out_pdb.parent.mkdir(parents=True, exist_ok=True)
            out_pdb.write_text("\n".join(lines), encoding="utf-8")
            if bool(args.validate):
                format_payload = format_validator.validate_prediction(
                    target_id=target_id,
                    prediction_file=out_pdb,
                    sequence_path=sequence_path,
                )
                geometry_payload = geometry_validator.validate_geometry(target_id=target_id, prediction_file=out_pdb)
                confidence_payload = confidence_validator.validate_confidence(
                    target_id=target_id,
                    prediction_file=out_pdb,
                    sequence_path=sequence_path,
                )
                validation = {
                    "format_check_status": format_payload["summary"]["format_check_status"],
                    "geometry_sanity_status": geometry_payload["summary"]["geometry_sanity_status"],
                    "confidence_calibration_status": confidence_payload["summary"]["confidence_calibration_status"],
                }
                if validation["format_check_status"] != "pass":
                    blockers.append("format_check_failed")
                if validation["geometry_sanity_status"] != "pass":
                    blockers.append("geometry_sanity_failed")
                if validation["confidence_calibration_status"] != "pass":
                    blockers.append("confidence_calibration_failed")
    status = "pass" if not blockers else "blocked"
    return {
        "target_id": target_id,
        "sidechain_scaffold_status": status,
        "source_pdb": _artifact(source),
        "out_pdb": _artifact(out_pdb),
        **metrics,
        **validation,
        "blockers": ",".join(sorted(set(blockers))),
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    rows = [_build_one(target_id, args) for target_id in _target_ids(args)]
    pass_count = sum(1 for row in rows if row["sidechain_scaffold_status"] == "pass")
    validation_pass_count = sum(
        1
        for row in rows
        if row["format_check_status"] == row["geometry_sanity_status"] == row["confidence_calibration_status"] == "pass"
    )
    completion_values = [float(row["heavy_atom_completion_fraction"]) for row in rows if float(row.get("expected_heavy_atom_count", 0) or 0) > 0]
    summary = {
        "packet_type": "casp17_sidechain_scaffold_packet",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "target_count": len(rows),
        "pass_count": pass_count,
        "blocked_count": len(rows) - pass_count,
        "validation_pass_count": validation_pass_count,
        "min_heavy_atom_completion_fraction": round(min(completion_values), 6) if completion_values else 0.0,
        "mean_heavy_atom_completion_fraction": round(sum(completion_values) / len(completion_values), 6) if completion_values else 0.0,
        "total_emitted_heavy_atom_count": sum(int(row.get("emitted_heavy_atom_count", 0) or 0) for row in rows),
        "total_pruned_sidechain_atom_count": sum(int(row.get("pruned_sidechain_atom_count", 0) or 0) for row in rows),
        "total_rotamer_candidate_count": sum(int(row.get("rotamer_candidate_count", 0) or 0) for row in rows),
        "total_rotamer_selected_residue_count": sum(int(row.get("rotamer_selected_residue_count", 0) or 0) for row in rows),
        "source_dir": _artifact(args.source_dir),
        "out_dir": _artifact(args.out_dir),
        "sidechain_scaffold_status": "pass" if rows and pass_count == len(rows) else "blocked",
        "claim_boundary": "Residue-specific heavy-atom scaffold with local frame-rotamer candidate selection from internal CA traces only; not a statistical rotamer-library packer, energy-minimized, native-calibrated all-atom refinement, official CASP accuracy evidence, or portal submission.",
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Sidechain Scaffold Packet",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- source_dir: `{summary['source_dir']}`",
        f"- out_dir: `{summary['out_dir']}`",
        f"- pass/blocked: `{summary['pass_count']}/{summary['blocked_count']}`",
        f"- validation_pass_count: `{summary['validation_pass_count']}`",
        "",
        "| target | status | chains | residues | heavy atoms | completion | pruned | rotamers | format | geometry | confidence | output | blockers |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['sidechain_scaffold_status']}` | {row['chain_count']} | {row['residue_count']} | "
            f"{row['emitted_heavy_atom_count']} | {row['heavy_atom_completion_fraction']} | "
            f"{row.get('pruned_sidechain_atom_count', 0)} | "
            f"{row.get('rotamer_selected_residue_count', 0)}/{row.get('rotamer_candidate_count', 0)} | "
            f"`{row['format_check_status']}` | `{row['geometry_sanity_status']}` | `{row['confidence_calibration_status']}` | "
            f"`{row['out_pdb']}` | {row['blockers'] or '-'} |"
        )
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build residue-specific heavy-atom sidechain scaffold copies for CASP17 internal TS predictions.")
    parser.add_argument("--target-watchlist-json", default=DEFAULT_WATCHLIST_JSON)
    parser.add_argument("--target-ids", default="")
    parser.add_argument("--source-dir", default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--sequence-dir", default=DEFAULT_SEQUENCE_DIR)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--validate", action=argparse.BooleanOptionalAction, default=True)
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
