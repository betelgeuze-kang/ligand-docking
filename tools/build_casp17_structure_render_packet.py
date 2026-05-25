#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import os
import shutil
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_WATCHLIST_JSON = "runs/casp17_target_watchlist_current.json"
DEFAULT_PREDICTION_DIR = "runs/casp17_predictions_recursive_current"
DEFAULT_OUT_DIR = "runs/casp17_structure_renders_current"
DEFAULT_OUT_JSON = "runs/casp17_structure_render_packet_current.json"
DEFAULT_OUT_CSV = "runs/casp17_structure_render_packet_current.csv"
DEFAULT_OUT_MD = "runs/casp17_structure_render_packet_current.md"
DEFAULT_OUT_HTML = "runs/casp17_structure_render_gallery_current.html"
DEFAULT_CONTACT_SHEET = "runs/casp17_structure_render_contact_sheet_current.png"
DEFAULT_QC_CONTACT_SHEET = "runs/casp17_structure_render_qc_contact_sheet_current.png"
DEFAULT_SURFACE_CONTACT_SHEET = "runs/casp17_structure_render_surface_contact_sheet_current.png"
DEFAULT_CONFIDENCE_CONTACT_SHEET = "runs/casp17_structure_render_confidence_contact_sheet_current.png"
DEFAULT_RESIDUE_CLASS_CONTACT_SHEET = "runs/casp17_structure_render_residue_class_contact_sheet_current.png"
DEFAULT_INTERFACE_CONTACT_SHEET = "runs/casp17_structure_render_interface_contact_sheet_current.png"
DEFAULT_REVIEW_CONTACT_SHEET = "runs/casp17_structure_render_review_contact_sheet_current.png"
DEFAULT_ATLAS_CONTACT_SHEET = "runs/casp17_structure_render_atlas_contact_sheet_current.png"
DEFAULT_MOLECULAR_PLATE_CONTACT_SHEET = "runs/casp17_structure_render_molecular_plate_contact_sheet_current.png"
DEFAULT_PRESENTATION_PLATE_CONTACT_SHEET = "runs/casp17_structure_render_presentation_contact_sheet_current.png"
DEFAULT_STEREO_CONTACT_SHEET = "runs/casp17_structure_render_stereo_depth_contact_sheet_current.png"
DEFAULT_TURNTABLE_CONTACT_SHEET = "runs/casp17_structure_render_turntable_contact_sheet_current.png"
DEFAULT_PYMOL_EXECUTABLE = "auto"

SOFT_QC_DISTANCE_A = 1.10
LOW_CONFIDENCE_QC_FRACTION = 0.18
MAX_QC_HOTSPOTS = 36

CHAIN_COLORS = [
    "#2563eb",
    "#dc2626",
    "#059669",
    "#d97706",
    "#7c3aed",
    "#0891b2",
    "#be123c",
    "#4d7c0f",
    "#9333ea",
    "#0f766e",
]

ELEMENT_COLORS = {
    "C": (148, 163, 184),
    "N": (96, 165, 250),
    "O": (248, 113, 113),
    "S": (250, 204, 21),
    "P": (251, 146, 60),
}

RESIDUE_CLASS_COLORS = {
    "hydrophobic": "#16a34a",
    "polar": "#0891b2",
    "positive": "#2563eb",
    "negative": "#dc2626",
    "aromatic": "#7c3aed",
    "special": "#d97706",
    "unknown": "#64748b",
}
RESIDUE_CLASS_BY_RESNAME = {
    "ALA": "hydrophobic",
    "VAL": "hydrophobic",
    "LEU": "hydrophobic",
    "ILE": "hydrophobic",
    "MET": "hydrophobic",
    "PRO": "special",
    "GLY": "special",
    "SER": "polar",
    "THR": "polar",
    "CYS": "polar",
    "ASN": "polar",
    "GLN": "polar",
    "TYR": "aromatic",
    "TRP": "aromatic",
    "PHE": "aromatic",
    "HIS": "positive",
    "LYS": "positive",
    "ARG": "positive",
    "ASP": "negative",
    "GLU": "negative",
}

SECONDARY_PROXY_COLORS = {
    "helix_like": "#22c55e",
    "strand_like": "#f59e0b",
    "coil_or_turn": "#38bdf8",
}

CONFIDENCE_STOPS = [
    (0.00, (220, 38, 38)),
    (0.45, (217, 119, 6)),
    (0.70, (5, 150, 105)),
    (1.00, (37, 99, 235)),
]


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


def _font(size: int, *, bold: bool = False) -> ImageFont.ImageFont:
    names = ["DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf", "Arial.ttf"]
    for name in names:
        try:
            return ImageFont.truetype(name, int(size))
        except OSError:
            continue
    return ImageFont.load_default()


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
    targets = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        lane = _text(row.get("lane_recommendation"))
        target_id = _text(row.get("target_id")).upper()
        if target_id and row.get("human_open") is True and lane in {"organic_ligand_protein_complexes", "difficult_protein_complexes"}:
            targets.append(target_id)
    return targets


def _prediction_paths(prediction_dir: str | Path, target_ids: list[str]) -> list[tuple[str, Path]]:
    root = _resolve(prediction_dir)
    if target_ids:
        return [(target_id, root / f"{target_id}TS.pdb") for target_id in target_ids]
    return [(path.stem.replace("TS", "").upper(), path) for path in sorted(root.glob("*TS.pdb"))]


def _record(line: str) -> str:
    return line[:6].strip().upper()


def _parse_pdb_atoms(path_like: str | Path) -> list[dict[str, Any]]:
    path = _resolve(path_like)
    atoms: list[dict[str, Any]] = []
    in_first_model = False
    seen_model = False
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        rec = _record(line)
        if rec == "MODEL":
            if seen_model:
                break
            seen_model = True
            in_first_model = True
            continue
        if rec == "END" and in_first_model:
            break
        if rec != "ATOM":
            continue
        if seen_model and not in_first_model:
            continue
        try:
            atom_name = line[12:16].strip()
            chain_id = line[21].strip() or "_"
            resseq = int(line[22:26])
            x = float(line[30:38])
            y = float(line[38:46])
            z = float(line[46:54])
            b_factor = float(line[60:66]) if len(line) >= 66 else 0.0
        except (ValueError, IndexError):
            continue
        atoms.append(
            {
            "atom_name": atom_name,
            "chain_id": chain_id,
            "resseq": resseq,
            "resname": line[17:20].strip().upper() if len(line) >= 20 else "UNK",
            "x": x,
            "y": y,
                "z": z,
                "b_factor": b_factor,
            }
        )
    return atoms


def _pml_quote(value: str | Path) -> str:
    text = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{text}"'


def _safe_pymol_name(target_id: str) -> str:
    safe = "".join(char if char.isalnum() else "_" for char in target_id)
    return f"casp17_{safe or 'model'}"


def _safe_pymol_selection_name(prefix: str, index: int) -> str:
    safe = "".join(char if char.isalnum() else "_" for char in prefix)
    return f"{safe or 'qc'}_{index}"


def _find_pymol_executable(executable: str) -> str:
    executable = _text(executable)
    if not executable or executable.lower() in {"none", "disabled", "false"}:
        return ""
    if executable.lower() == "auto":
        return shutil.which("pymol") or ""
    return executable


def _ca_trace_by_chain(atoms: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    chains: dict[str, list[dict[str, Any]]] = {}
    for atom in atoms:
        if atom["atom_name"] != "CA":
            continue
        chains.setdefault(atom["chain_id"], []).append(atom)
    return chains


def _residue_class(resname: str) -> str:
    return RESIDUE_CLASS_BY_RESNAME.get(str(resname).upper(), "unknown")


def _residue_class_counts_from_atoms(atoms: list[dict[str, Any]]) -> dict[str, int]:
    residues = {
        (str(atom.get("chain_id") or "_"), int(atom.get("resseq") or 0), str(atom.get("resname") or "UNK").upper())
        for atom in atoms
    }
    counts = {key: 0 for key in RESIDUE_CLASS_COLORS}
    for _chain_id, _resseq, resname in residues:
        counts[_residue_class(resname)] += 1
    return counts


def _coord_distance(left: dict[str, Any], right: dict[str, Any]) -> float:
    return math.sqrt(_distance_sq(_atom_coord(left), _atom_coord(right)))


def _secondary_proxy_by_residue(chains: dict[str, list[dict[str, Any]]]) -> dict[tuple[str, int], str]:
    """Rule-based CA geometry proxy for visual triage; not DSSP or native SS evidence."""
    proxy: dict[tuple[str, int], str] = {}
    for chain_id, trace in chains.items():
        for index, atom in enumerate(trace):
            key = (str(chain_id), int(atom.get("resseq") or 0))
            label = "coil_or_turn"
            if index + 4 < len(trace):
                ca_i_i4 = _coord_distance(atom, trace[index + 4])
                if 4.8 <= ca_i_i4 <= 6.6:
                    label = "helix_like"
            if label == "coil_or_turn" and index + 2 < len(trace):
                ca_i_i2 = _coord_distance(atom, trace[index + 2])
                if ca_i_i2 >= 6.2:
                    label = "strand_like"
            proxy[key] = label
    return proxy


def _secondary_proxy_counts(proxy: dict[tuple[str, int], str]) -> dict[str, int]:
    counts = {key: 0 for key in SECONDARY_PROXY_COLORS}
    for label in proxy.values():
        counts[label if label in counts else "coil_or_turn"] += 1
    return counts


def _residue_key(atom: dict[str, Any]) -> tuple[str, int]:
    return str(atom.get("chain_id") or "_"), int(atom.get("resseq") or 0)


def _atom_coord(atom: dict[str, Any]) -> tuple[float, float, float]:
    return float(atom["x"]), float(atom["y"]), float(atom["z"])


def _grid_cell(coord: tuple[float, float, float], cell_size: float) -> tuple[int, int, int]:
    return tuple(math.floor(axis / cell_size) for axis in coord)


def _distance_sq(left: tuple[float, float, float], right: tuple[float, float, float]) -> float:
    return (left[0] - right[0]) ** 2 + (left[1] - right[1]) ** 2 + (left[2] - right[2]) ** 2


def _interface_contact_summary(chains: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    chain_ids = sorted(chains)
    pairs: list[dict[str, Any]] = []
    total_contacts_8a = 0
    total_contacts_12a = 0
    min_distance: float | None = None
    for left_index, left_chain in enumerate(chain_ids):
        for right_chain in chain_ids[left_index + 1 :]:
            left_atoms = chains.get(left_chain, [])
            right_atoms = chains.get(right_chain, [])
            if not left_atoms or not right_atoms:
                continue
            contacts_8a = 0
            contacts_12a = 0
            pair_min: float | None = None
            for left_atom in left_atoms:
                left_coord = _atom_coord(left_atom)
                for right_atom in right_atoms:
                    distance = math.sqrt(_distance_sq(left_coord, _atom_coord(right_atom)))
                    pair_min = distance if pair_min is None else min(pair_min, distance)
                    if distance <= 8.0:
                        contacts_8a += 1
                    if distance <= 12.0:
                        contacts_12a += 1
            if pair_min is None:
                continue
            min_distance = pair_min if min_distance is None else min(min_distance, pair_min)
            total_contacts_8a += contacts_8a
            total_contacts_12a += contacts_12a
            pairs.append(
                {
                    "chain_pair": f"{left_chain}:{right_chain}",
                    "left_chain_id": left_chain,
                    "right_chain_id": right_chain,
                    "left_ca_count": len(left_atoms),
                    "right_ca_count": len(right_atoms),
                    "min_ca_distance_A": round(pair_min, 3),
                    "ca_contacts_8a": contacts_8a,
                    "ca_contacts_12a": contacts_12a,
                }
            )
    pairs.sort(key=lambda row: (-int(row["ca_contacts_12a"]), float(row["min_ca_distance_A"]), str(row["chain_pair"])))
    return {
        "chain_count": len(chain_ids),
        "pair_count": len(pairs),
        "total_ca_contacts_8a": total_contacts_8a,
        "total_ca_contacts_12a": total_contacts_12a,
        "min_interchain_ca_distance_A": round(min_distance, 3) if min_distance is not None else 0.0,
        "pairs": pairs,
    }


def _qc_hotspot_analysis(atoms: list[dict[str, Any]]) -> dict[str, Any]:
    residues: dict[tuple[str, int], dict[str, Any]] = {}
    for atom in atoms:
        key = _residue_key(atom)
        residue = residues.setdefault(
            key,
            {
                "chain_id": key[0],
                "resseq": key[1],
                "resname": str(atom.get("resname") or "UNK"),
                "b_values": [],
                "atom_count": 0,
            },
        )
        residue["b_values"].append(float(atom.get("b_factor", 0.0)))
        residue["atom_count"] += 1

    if not residues:
        return {"hotspots": [], "low_confidence_cutoff": 0.0, "confidence_span": 0.0}

    mean_confidence: dict[tuple[str, int], float] = {
        key: sum(row["b_values"]) / max(1, len(row["b_values"])) for key, row in residues.items()
    }
    sorted_confidence = sorted(mean_confidence.values())
    cutoff_index = max(0, min(len(sorted_confidence) - 1, int(math.floor((len(sorted_confidence) - 1) * LOW_CONFIDENCE_QC_FRACTION))))
    low_confidence_cutoff = sorted_confidence[cutoff_index]
    confidence_span = sorted_confidence[-1] - sorted_confidence[0]

    contact_counts: dict[tuple[str, int], int] = defaultdict(int)
    closest_by_residue: dict[tuple[str, int], float] = {}
    closest_partner_by_residue: dict[tuple[str, int], dict[str, Any]] = {}
    grid: dict[tuple[int, int, int], list[int]] = defaultdict(list)
    soft_sq = SOFT_QC_DISTANCE_A * SOFT_QC_DISTANCE_A

    def record_closest(
        residue_key: tuple[str, int],
        atom: dict[str, Any],
        partner_key: tuple[str, int],
        partner_atom: dict[str, Any],
        dist_sq: float,
    ) -> None:
        previous = closest_by_residue.get(residue_key)
        if previous is not None and dist_sq >= previous:
            return
        closest_by_residue[residue_key] = dist_sq
        closest_partner_by_residue[residue_key] = {
            "closest_atom_name": str(atom.get("atom_name") or ""),
            "closest_partner_chain_id": partner_key[0],
            "closest_partner_resseq": partner_key[1],
            "closest_partner_atom_name": str(partner_atom.get("atom_name") or ""),
        }

    for atom_index, atom in enumerate(atoms):
        coord = _atom_coord(atom)
        cell = _grid_cell(coord, SOFT_QC_DISTANCE_A)
        key = _residue_key(atom)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for other_index in grid.get((cell[0] + dx, cell[1] + dy, cell[2] + dz), []):
                        other = atoms[other_index]
                        other_key = _residue_key(other)
                        if key == other_key:
                            continue
                        dist_sq = _distance_sq(coord, _atom_coord(other))
                        if dist_sq >= soft_sq:
                            continue
                        contact_counts[key] += 1
                        contact_counts[other_key] += 1
                        record_closest(key, atom, other_key, other, dist_sq)
                        record_closest(other_key, other, key, atom, dist_sq)
        grid[cell].append(atom_index)

    rows: list[dict[str, Any]] = []
    for key, residue in residues.items():
        soft_contacts = int(contact_counts.get(key, 0))
        mean_b = mean_confidence[key]
        low_confidence = confidence_span > 1e-6 and mean_b <= low_confidence_cutoff and len(residues) >= 4
        if not soft_contacts and not low_confidence:
            continue
        closest_sq = closest_by_residue.get(key)
        hotspot_type = "soft_contact"
        if soft_contacts and low_confidence:
            hotspot_type = "soft_contact_low_confidence"
        elif low_confidence:
            hotspot_type = "low_confidence"
        confidence_deficit = max(0.0, low_confidence_cutoff - mean_b)
        partner = closest_partner_by_residue.get(key, {})
        row = {
            "chain_id": residue["chain_id"],
            "resseq": residue["resseq"],
            "resname": residue["resname"],
            "soft_contact_count": soft_contacts,
            "mean_confidence": round(mean_b, 3),
            "low_confidence": bool(low_confidence),
            "closest_soft_contact_A": round(math.sqrt(closest_sq), 3) if closest_sq is not None else 0.0,
            "hotspot_type": hotspot_type,
            "score": soft_contacts * 1000.0 + confidence_deficit * 10.0 + (25.0 if low_confidence else 0.0),
            "closest_atom_name": str(partner.get("closest_atom_name") or ""),
            "closest_partner_chain_id": str(partner.get("closest_partner_chain_id") or ""),
            "closest_partner_resseq": int(partner.get("closest_partner_resseq") or 0),
            "closest_partner_atom_name": str(partner.get("closest_partner_atom_name") or ""),
        }
        rows.append(row)
    rows.sort(key=lambda row: (-float(row["score"]), str(row["chain_id"]), int(row["resseq"])))
    return {
        "hotspots": rows,
        "low_confidence_cutoff": round(float(low_confidence_cutoff), 3),
        "confidence_span": round(float(confidence_span), 3),
    }


def _qc_hotspot_residues(atoms: list[dict[str, Any]], *, max_hotspots: int | None = MAX_QC_HOTSPOTS) -> list[dict[str, Any]]:
    rows = list(_qc_hotspot_analysis(atoms)["hotspots"])
    if max_hotspots is None:
        return rows
    return rows[: max(0, int(max_hotspots))]


def _rgb(hex_color: str) -> tuple[int, int, int]:
    value = hex_color.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def _mix(left: tuple[int, int, int], right: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    t = max(0.0, min(1.0, t))
    return tuple(int(round(left[index] + (right[index] - left[index]) * t)) for index in range(3))


def _mix_rgba(
    left: tuple[int, int, int] | tuple[int, int, int, int],
    right: tuple[int, int, int] | tuple[int, int, int, int],
    t: float,
    *,
    alpha: int = 255,
) -> tuple[int, int, int, int]:
    mixed = _mix((left[0], left[1], left[2]), (right[0], right[1], right[2]), t)
    return mixed[0], mixed[1], mixed[2], alpha


def _confidence_rgb(value: float, min_value: float, max_value: float) -> tuple[int, int, int]:
    if max_value <= min_value:
        return CONFIDENCE_STOPS[-1][1]
    t = max(0.0, min(1.0, (value - min_value) / (max_value - min_value)))
    left = CONFIDENCE_STOPS[0]
    right = CONFIDENCE_STOPS[-1]
    for index in range(1, len(CONFIDENCE_STOPS)):
        if t <= CONFIDENCE_STOPS[index][0]:
            left = CONFIDENCE_STOPS[index - 1]
            right = CONFIDENCE_STOPS[index]
            break
    local = (t - left[0]) / max(1e-6, right[0] - left[0])
    return _mix(left[1], right[1], local)


def _confidence_stats(atoms: list[dict[str, Any]]) -> dict[str, Any]:
    values = sorted(float(atom.get("b_factor", 0.0)) for atom in atoms if math.isfinite(float(atom.get("b_factor", 0.0))))
    if not values:
        return {
            "confidence_b_factor_min": 0.0,
            "confidence_b_factor_median": 0.0,
            "confidence_b_factor_max": 0.0,
            "confidence_palette": "",
        }
    mid = len(values) // 2
    median = values[mid] if len(values) % 2 else (values[mid - 1] + values[mid]) / 2.0
    return {
        "confidence_b_factor_min": round(values[0], 3),
        "confidence_b_factor_median": round(median, 3),
        "confidence_b_factor_max": round(values[-1], 3),
        "confidence_palette": "red_amber_green_blue",
    }


def _confidence_legend(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], b_min: float, b_max: float) -> None:
    left, top, right, bottom = box
    width = max(1, right - left)
    for x in range(width):
        value = b_min + (b_max - b_min) * (x / max(1, width - 1))
        draw.line([(left + x, top), (left + x, bottom)], fill=(*_confidence_rgb(value, b_min, b_max), 255))
    draw.rounded_rectangle([left, top, right, bottom], radius=8, outline=(148, 163, 184, 180), width=2)


def _draw_shaded_sphere(
    draw: ImageDraw.ImageDraw,
    center: tuple[int, int],
    radius: int,
    base_color: tuple[int, int, int],
    *,
    alpha: int,
) -> None:
    if radius <= 0:
        return
    cx, cy = center
    draw.ellipse(
        [cx - radius + 3, cy - radius + 5, cx + radius + 3, cy + radius + 5],
        fill=(2, 6, 23, max(20, alpha // 3)),
    )
    for step in range(radius, 0, -1):
        t = 1.0 - step / max(radius, 1)
        shade = _mix((5, 10, 24), base_color, 0.50 + 0.42 * t)
        draw.ellipse(
            [cx - step, cy - step, cx + step, cy + step],
            fill=(shade[0], shade[1], shade[2], alpha),
        )
    highlight_r = max(2, radius // 3)
    hx = cx - max(1, radius // 3)
    hy = cy - max(1, radius // 3)
    draw.ellipse(
        [hx - highlight_r, hy - highlight_r, hx + highlight_r, hy + highlight_r],
        fill=(255, 255, 255, min(160, alpha)),
    )


def _rotate_project(
    point: tuple[float, float, float],
    center: tuple[float, float, float],
    *,
    elev: float,
    azim: float,
) -> tuple[float, float, float]:
    x = point[0] - center[0]
    y = point[1] - center[1]
    z = point[2] - center[2]
    az = math.radians(azim)
    el = math.radians(elev)
    x1 = math.cos(az) * x - math.sin(az) * y
    y1 = math.sin(az) * x + math.cos(az) * y
    z1 = z
    y2 = math.cos(el) * y1 - math.sin(el) * z1
    z2 = math.sin(el) * y1 + math.cos(el) * z1
    return x1, y2, z2


def _draw_gradient_background(draw: ImageDraw.ImageDraw, width: int, height: int, top: str, bottom: str) -> None:
    top_rgb = _rgb(top)
    bottom_rgb = _rgb(bottom)
    for y in range(height):
        color = _mix(top_rgb, bottom_rgb, y / max(1, height - 1))
        draw.line([(0, y), (width, y)], fill=color)


def _ca_bounds(chains: dict[str, list[dict[str, Any]]]) -> tuple[tuple[float, float, float], float]:
    points = [(atom["x"], atom["y"], atom["z"]) for trace in chains.values() for atom in trace]
    if not points:
        return (0.0, 0.0, 0.0), 1.0
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    zs = [point[2] for point in points]
    center = ((min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0, (min(zs) + max(zs)) / 2.0)
    span = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs), 1.0)
    return center, span


def _draw_projected_trace_panel(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    chains: dict[str, list[dict[str, Any]]],
    *,
    title: str,
    elev: float,
    azim: float,
    color_mode: str,
) -> None:
    left, top, right, bottom = box
    width = right - left
    height = bottom - top
    margin = max(46, min(width, height) // 11)
    draw.rounded_rectangle([left, top, right, bottom], radius=26, fill=(255, 255, 255), outline=(203, 213, 225), width=2)
    title_font = _font(max(18, min(width, height) // 24), bold=True)
    draw.text((left + 28, top + 20), title, fill=(15, 23, 42), font=title_font)

    center, span = _ca_bounds(chains)
    projected_by_chain: dict[str, list[tuple[float, float, float, float]]] = {}
    all_projected: list[tuple[float, float, float]] = []
    for chain_id, trace in chains.items():
        values: list[tuple[float, float, float, float]] = []
        for atom in trace:
            projected = _rotate_project((atom["x"], atom["y"], atom["z"]), center, elev=elev, azim=azim)
            values.append((projected[0], projected[1], projected[2], float(atom.get("b_factor", 0.0))))
            all_projected.append(projected)
        projected_by_chain[chain_id] = values
    if not all_projected:
        return
    xs = [point[0] for point in all_projected]
    ys = [point[1] for point in all_projected]
    zs = [point[2] for point in all_projected]
    x_mid = (min(xs) + max(xs)) / 2.0
    y_mid = (min(ys) + max(ys)) / 2.0
    xy_span = max(max(xs) - min(xs), max(ys) - min(ys), span * 0.15, 1.0)
    scale = min((width - margin * 2) / xy_span, (height - margin * 2 - 28) / xy_span)
    z_min = min(zs)
    z_max = max(zs)
    b_values = [atom["b_factor"] for trace in chains.values() for atom in trace]
    b_min = min(b_values) if b_values else 0.0
    b_max = max(b_values) if b_values else 1.0

    def screen(point: tuple[float, float, float, float]) -> tuple[int, int, float, float]:
        x, y, z, b_factor = point
        sx = int(round(left + width / 2.0 + (x - x_mid) * scale))
        sy = int(round(top + height / 2.0 - (y - y_mid) * scale + 16))
        depth = (z - z_min) / max(1e-6, z_max - z_min)
        return sx, sy, depth, b_factor

    segments: list[dict[str, Any]] = []
    for chain_index, chain_id in enumerate(sorted(projected_by_chain)):
        chain_color = _rgb(CHAIN_COLORS[chain_index % len(CHAIN_COLORS)])
        trace = projected_by_chain[chain_id]
        source_trace = chains.get(chain_id, [])
        for first_atom, first, second in zip(source_trace, trace, trace[1:]):
            s1 = screen(first)
            s2 = screen(second)
            depth = (s1[2] + s2[2]) / 2.0
            if color_mode == "confidence":
                color = _confidence_rgb((s1[3] + s2[3]) / 2.0, b_min, b_max)
            elif color_mode == "residue_class":
                residue_class = _residue_class(str(first_atom.get("resname") or "UNK"))
                color = _rgb(RESIDUE_CLASS_COLORS.get(residue_class, RESIDUE_CLASS_COLORS["unknown"]))
            else:
                color = chain_color
            segments.append(
                {
                    "depth": depth,
                    "points": [(s1[0], s1[1]), (s2[0], s2[1])],
                    "color": color,
                    "width": int(round(5 + depth * 7)),
                }
            )
    segments.sort(key=lambda item: item["depth"])
    for segment in segments:
        shadow = [(x + 5, y + 7) for x, y in segment["points"]]
        draw.line(shadow, fill=(15, 23, 42, 34), width=segment["width"] + 3)
    for segment in segments:
        color = _mix((210, 220, 232), segment["color"], 0.55 + segment["depth"] * 0.45)
        draw.line(segment["points"], fill=color, width=segment["width"])

    for chain_index, chain_id in enumerate(sorted(projected_by_chain)):
        chain_color = _rgb(CHAIN_COLORS[chain_index % len(CHAIN_COLORS)])
        trace = projected_by_chain[chain_id]
        source_trace = chains.get(chain_id, [])
        step = max(1, math.ceil(len(trace) / 110))
        for atom, point in zip(source_trace[::step], trace[::step]):
            sx, sy, depth, b_factor = screen(point)
            radius = int(round(3 + depth * 4))
            if color_mode == "confidence":
                color = _confidence_rgb(b_factor, b_min, b_max)
            elif color_mode == "residue_class":
                residue_class = _residue_class(str(atom.get("resname") or "UNK"))
                color = _rgb(RESIDUE_CLASS_COLORS.get(residue_class, RESIDUE_CLASS_COLORS["unknown"]))
            else:
                color = chain_color
            color = _mix((226, 232, 240), color, 0.55 + depth * 0.45)
            draw.ellipse([sx - radius, sy - radius, sx + radius, sy + radius], fill=color, outline=(255, 255, 255))


def _write_publication_render(
    target_id: str,
    chains: dict[str, list[dict[str, Any]]],
    out_dir: str | Path,
    *,
    width: int,
    height: int,
) -> str:
    out = _resolve(out_dir) / f"{target_id}_structure_publication.png"
    image = Image.new("RGB", (width, height), "#f8fafc")
    draw = ImageDraw.Draw(image, "RGBA")
    _draw_gradient_background(draw, width, height, "#f8fafc", "#e2e8f0")
    title_font = ImageFont.load_default()
    draw.text((34, 28), f"{target_id} internal physics model", fill=(15, 23, 42), font=title_font)
    draw.text((34, 50), "Two-view CA-anchored molecular trace: chain color and confidence color", fill=(71, 85, 105), font=title_font)
    gap = 22
    panel_top = 84
    panel_bottom = height - 42
    panel_width = (width - 68 - gap) // 2
    left_box = (34, panel_top, 34 + panel_width, panel_bottom)
    right_box = (34 + panel_width + gap, panel_top, width - 34, panel_bottom)
    _draw_projected_trace_panel(draw, left_box, chains, title="Chain-colored view", elev=20, azim=-58, color_mode="chain")
    _draw_projected_trace_panel(draw, right_box, chains, title="Confidence-colored view", elev=82, azim=32, color_mode="confidence")
    legend_y = height - 28
    draw.text((34, legend_y), "Red/amber = lower confidence, green/blue = higher confidence. Visualization only; not official CASP accuracy evidence.", fill=(71, 85, 105))
    out.parent.mkdir(parents=True, exist_ok=True)
    image.save(out)
    return _artifact(out)


def _write_stereo_depth_render(
    target_id: str,
    chains: dict[str, list[dict[str, Any]]],
    out_dir: str | Path,
    *,
    width: int = 3000,
    height: int = 1500,
) -> str:
    out = _resolve(out_dir) / f"{target_id}_structure_stereo_depth.png"
    image = Image.new("RGB", (width, height), "#07111f")
    draw = ImageDraw.Draw(image, "RGBA")
    _draw_gradient_background(draw, width, height, "#07111f", "#111827")
    title_font = _font(34, bold=True)
    body_font = _font(21)
    margin = 46
    header_h = 126
    footer_h = 82
    gap = 34
    panel_w = (width - margin * 2 - gap) // 2
    panel_h = height - header_h - footer_h
    left_box = (margin, header_h, margin + panel_w, header_h + panel_h)
    right_box = (margin + panel_w + gap, header_h, width - margin, header_h + panel_h)

    draw.text((margin, 30), f"{target_id} orthographic stereo depth review", fill=(226, 232, 240, 255), font=title_font)
    draw.text(
        (margin, 72),
        "Side-by-side CA trace views use a small azimuth offset for depth inspection from internal predicted coordinates.",
        fill=(148, 163, 184, 255),
        font=body_font,
    )
    draw.text(
        (margin, 102),
        "Use as local visual triage only; this is not native accuracy evidence or an experimental structure.",
        fill=(148, 163, 184, 255),
        font=body_font,
    )

    _draw_projected_trace_panel(draw, left_box, chains, title="Left-eye chain view", elev=28, azim=-51, color_mode="chain")
    _draw_projected_trace_panel(draw, right_box, chains, title="Right-eye chain view", elev=28, azim=-43, color_mode="chain")

    footer_y = height - footer_h + 24
    draw.text(
        (margin, footer_y),
        "Stereo pair is generated locally from the submitted TS PDB coordinates; no external predictor, template, or current-target native lookup is used.",
        fill=(148, 163, 184, 255),
        font=body_font,
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    image.save(out, quality=95)
    return _artifact(out)


def _write_turntable_render(
    target_id: str,
    chains: dict[str, list[dict[str, Any]]],
    out_dir: str | Path,
    *,
    width: int = 3600,
    height: int = 2200,
) -> str:
    out = _resolve(out_dir) / f"{target_id}_structure_turntable.png"
    image = Image.new("RGB", (width, height), "#07111f")
    draw = ImageDraw.Draw(image, "RGBA")
    _draw_gradient_background(draw, width, height, "#07111f", "#111827")
    title_font = _font(38, bold=True)
    body_font = _font(22)
    footer_font = _font(20)
    margin = 52
    header_h = 154
    footer_h = 96
    gap = 30
    columns = 4
    rows = 2
    panel_w = (width - margin * 2 - gap * (columns - 1)) // columns
    panel_h = (height - header_h - footer_h - gap * (rows - 1)) // rows

    draw.text((margin, 34), f"{target_id} molecular turntable review", fill=(226, 232, 240, 255), font=title_font)
    draw.text(
        (margin, 82),
        "Eight local orthographic projections expose silhouette, chain packing, confidence, and residue chemistry from the same TS coordinates.",
        fill=(148, 163, 184, 255),
        font=body_font,
    )
    draw.text(
        (margin, 116),
        "This is internal visual triage only; it does not imply native accuracy, template use, or experimental validation.",
        fill=(148, 163, 184, 255),
        font=body_font,
    )

    views = [
        ("front chain", 18, -60, "chain"),
        ("right chain", 18, 30, "chain"),
        ("back chain", 18, 120, "chain"),
        ("left chain", 18, 210, "chain"),
        ("top chain", 86, -60, "chain"),
        ("tilt confidence", 44, -18, "confidence"),
        ("tilt residue class", 44, 58, "residue_class"),
        ("low-angle packing", 8, 142, "chain"),
    ]
    for index, (label, elev, azim, color_mode) in enumerate(views):
        row_index = index // columns
        column_index = index % columns
        left = margin + column_index * (panel_w + gap)
        top = header_h + row_index * (panel_h + gap)
        box = (left, top, left + panel_w, top + panel_h)
        _draw_projected_trace_panel(draw, box, chains, title=label, elev=elev, azim=azim, color_mode=color_mode)

    footer_y = height - footer_h + 28
    draw.text(
        (margin, footer_y),
        "Generated locally from internal CASP17 TS PDB coordinates; no external predictor, template, current-target native lookup, or hosted viewer is used.",
        fill=(148, 163, 184, 255),
        font=footer_font,
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    image.save(out, quality=95)
    return _artifact(out)


def _project_chain_points(
    chains: dict[str, list[dict[str, Any]]],
    *,
    elev: float,
    azim: float,
) -> tuple[dict[str, list[tuple[float, float, float, float]]], tuple[float, float, float], float]:
    center, span = _ca_bounds(chains)
    projected_by_chain: dict[str, list[tuple[float, float, float, float]]] = {}
    for chain_id, trace in chains.items():
        values: list[tuple[float, float, float, float]] = []
        for atom in trace:
            projected = _rotate_project((atom["x"], atom["y"], atom["z"]), center, elev=elev, azim=azim)
            values.append((projected[0], projected[1], projected[2], float(atom.get("b_factor", 0.0))))
        projected_by_chain[chain_id] = values
    return projected_by_chain, center, span


def _write_studio_render(
    target_id: str,
    chains: dict[str, list[dict[str, Any]]],
    atoms: list[dict[str, Any]],
    out_dir: str | Path,
    *,
    width: int,
    height: int,
) -> str:
    out = _resolve(out_dir) / f"{target_id}_structure_studio.png"
    supersample = 2
    canvas_w = width * supersample
    canvas_h = height * supersample
    image = Image.new("RGB", (canvas_w, canvas_h), "#08111f")
    draw = ImageDraw.Draw(image, "RGBA")
    _draw_gradient_background(draw, canvas_w, canvas_h, "#08111f", "#101827")

    for ring in range(7):
        inset = (42 + ring * 34) * supersample
        alpha = max(10, 54 - ring * 6)
        draw.rounded_rectangle(
            [inset, inset, canvas_w - inset, canvas_h - inset],
            radius=42 * supersample,
            outline=(30, 41, 59, alpha),
            width=max(1, supersample),
        )

    projected_by_chain, center, span = _project_chain_points(chains, elev=28, azim=-46)
    all_projected = [point for trace in projected_by_chain.values() for point in trace]
    if not all_projected:
        image.save(out)
        return _artifact(out)

    xs = [point[0] for point in all_projected]
    ys = [point[1] for point in all_projected]
    zs = [point[2] for point in all_projected]
    x_mid = (min(xs) + max(xs)) / 2.0
    y_mid = (min(ys) + max(ys)) / 2.0
    xy_span = max(max(xs) - min(xs), max(ys) - min(ys), span * 0.12, 1.0)
    margin_x = 118 * supersample
    margin_top = 142 * supersample
    margin_bottom = 126 * supersample
    scale = min((canvas_w - margin_x * 2) / xy_span, (canvas_h - margin_top - margin_bottom) / xy_span)
    z_min = min(zs)
    z_max = max(zs)
    b_values = [point[3] for point in all_projected]
    b_min = min(b_values) if b_values else 0.0
    b_max = max(b_values) if b_values else 1.0

    def screen(point: tuple[float, float, float, float]) -> tuple[int, int, float, float]:
        x, y, z, b_factor = point
        sx = int(round(canvas_w / 2.0 + (x - x_mid) * scale))
        sy = int(round(margin_top + (canvas_h - margin_top - margin_bottom) / 2.0 - (y - y_mid) * scale))
        depth = (z - z_min) / max(1e-6, z_max - z_min)
        return sx, sy, depth, b_factor

    chain_points: dict[str, list[tuple[int, int, float, float]]] = {
        chain_id: [screen(point) for point in trace] for chain_id, trace in projected_by_chain.items()
    }
    sidechain_atoms = [atom for atom in atoms if atom.get("atom_name") != "CA"]
    atom_overlay_rows: list[tuple[float, tuple[int, int], int, tuple[int, int, int], int]] = []
    if sidechain_atoms:
        atom_step = max(1, math.ceil(len(sidechain_atoms) / 2600))
        for atom in sidechain_atoms[::atom_step]:
            projected = _rotate_project((atom["x"], atom["y"], atom["z"]), center, elev=28, azim=-46)
            sx, sy, depth, _b_factor = screen((projected[0], projected[1], projected[2], float(atom.get("b_factor", 0.0))))
            atom_name = str(atom.get("atom_name", "")).strip()
            element = atom_name[0].upper() if atom_name else "C"
            base = ELEMENT_COLORS.get(element, ELEMENT_COLORS["C"])
            radius = int(round((1.5 + depth * 2.5) * supersample))
            alpha = int(round(80 + depth * 95))
            atom_overlay_rows.append((depth, (sx, sy), radius, base, alpha))
    segments: list[dict[str, Any]] = []
    for chain_index, chain_id in enumerate(sorted(chain_points)):
        chain_color = _rgb(CHAIN_COLORS[chain_index % len(CHAIN_COLORS)])
        trace = chain_points[chain_id]
        for first, second in zip(trace, trace[1:]):
            depth = (first[2] + second[2]) / 2.0
            confidence_color = _confidence_rgb((first[3] + second[3]) / 2.0, b_min, b_max)
            color = _mix(chain_color, confidence_color, 0.20)
            segments.append(
                {
                    "depth": depth,
                    "points": [(first[0], first[1]), (second[0], second[1])],
                    "color": color,
                    "width": int(round((7.0 + depth * 9.0) * supersample)),
                }
            )
    segments.sort(key=lambda item: item["depth"])

    for segment in segments:
        points = segment["points"]
        width_px = segment["width"]
        offset = int(round((4.0 + 6.0 * segment["depth"]) * supersample))
        shadow_points = [(x + offset, y + offset) for x, y in points]
        draw.line(shadow_points, fill=(0, 0, 0, 80), width=width_px + 8 * supersample)
    for segment in segments:
        depth = float(segment["depth"])
        width_px = int(segment["width"])
        base = _mix((20, 28, 44), segment["color"], 0.52 + depth * 0.40)
        rim = _mix((255, 255, 255), base, 0.72)
        draw.line(segment["points"], fill=(*base, 235), width=width_px)
        draw.line(segment["points"], fill=(*rim, 90), width=max(1, width_px // 3))

    atom_overlay_rows.sort(key=lambda item: item[0])
    for _depth, center_xy, radius, color, alpha in atom_overlay_rows:
        _draw_shaded_sphere(draw, center_xy, max(1, radius), color, alpha=alpha)

    sphere_rows: list[tuple[float, tuple[int, int], int, tuple[int, int, int], int]] = []
    for chain_index, chain_id in enumerate(sorted(chain_points)):
        chain_color = _rgb(CHAIN_COLORS[chain_index % len(CHAIN_COLORS)])
        trace = chain_points[chain_id]
        step = max(1, math.ceil(len(trace) / 130))
        for point in trace[::step]:
            sx, sy, depth, b_factor = point
            confidence_color = _confidence_rgb(b_factor, b_min, b_max)
            color = _mix(chain_color, confidence_color, 0.38)
            radius = int(round((4.0 + depth * 5.5) * supersample))
            alpha = int(round(170 + depth * 70))
            sphere_rows.append((depth, (sx, sy), radius, color, alpha))
    sphere_rows.sort(key=lambda item: item[0])
    for _depth, center_xy, radius, color, alpha in sphere_rows:
        _draw_shaded_sphere(draw, center_xy, radius, color, alpha=alpha)

    font = ImageFont.load_default()
    title = f"{target_id} internal physics model"
    subtitle = (
        f"{len(chains)} chains | {sum(len(trace) for trace in chains.values())} CA trace points | "
        f"{len(sidechain_atoms)} non-CA atoms | shaded tube + atomic overlay"
    )
    draw.text((54 * supersample, 38 * supersample), title, fill=(226, 232, 240, 255), font=font)
    draw.text((54 * supersample, 62 * supersample), subtitle, fill=(148, 163, 184, 255), font=font)

    legend_x = canvas_w - 432 * supersample
    legend_y = 42 * supersample
    draw.text((legend_x, legend_y - 18 * supersample), "Confidence", fill=(203, 213, 225, 255), font=font)
    _confidence_legend(
        draw,
        (legend_x, legend_y, legend_x + 320 * supersample, legend_y + 16 * supersample),
        b_min,
        b_max,
    )
    draw.text((legend_x, legend_y + 24 * supersample), "lower", fill=(148, 163, 184, 255), font=font)
    draw.text((legend_x + 270 * supersample, legend_y + 24 * supersample), "higher", fill=(148, 163, 184, 255), font=font)

    label_y = canvas_h - 58 * supersample
    draw.text(
        (54 * supersample, label_y),
        "Visualization of internal predicted coordinates only; not official CASP accuracy evidence.",
        fill=(148, 163, 184, 255),
        font=font,
    )

    image = image.resize((width, height), Image.Resampling.LANCZOS)
    out.parent.mkdir(parents=True, exist_ok=True)
    image.save(out, quality=95)
    return _artifact(out)


def _write_residue_class_render(
    target_id: str,
    chains: dict[str, list[dict[str, Any]]],
    atoms: list[dict[str, Any]],
    out_dir: str | Path,
    *,
    width: int,
    height: int,
) -> str:
    out = _resolve(out_dir) / f"{target_id}_structure_residue_class.png"
    supersample = 2
    canvas_w = width * supersample
    canvas_h = height * supersample
    image = Image.new("RGB", (canvas_w, canvas_h), "#07111f")
    draw = ImageDraw.Draw(image, "RGBA")
    _draw_gradient_background(draw, canvas_w, canvas_h, "#07111f", "#101827")

    projected_by_chain, center, span = _project_chain_points(chains, elev=32, azim=-52)
    all_projected = [point for trace in projected_by_chain.values() for point in trace]
    if not all_projected:
        image.save(out)
        return _artifact(out)

    xs = [point[0] for point in all_projected]
    ys = [point[1] for point in all_projected]
    zs = [point[2] for point in all_projected]
    x_mid = (min(xs) + max(xs)) / 2.0
    y_mid = (min(ys) + max(ys)) / 2.0
    xy_span = max(max(xs) - min(xs), max(ys) - min(ys), span * 0.12, 1.0)
    margin_x = 124 * supersample
    margin_top = 150 * supersample
    margin_bottom = 170 * supersample
    scale = min((canvas_w - margin_x * 2) / xy_span, (canvas_h - margin_top - margin_bottom) / xy_span)
    z_min = min(zs)
    z_max = max(zs)

    def screen_from_projected(point: tuple[float, float, float, float]) -> tuple[int, int, float]:
        x, y, z, _b_factor = point
        sx = int(round(canvas_w / 2.0 + (x - x_mid) * scale))
        sy = int(round(margin_top + (canvas_h - margin_top - margin_bottom) / 2.0 - (y - y_mid) * scale))
        depth = (z - z_min) / max(1e-6, z_max - z_min)
        return sx, sy, depth

    ca_by_key: dict[tuple[str, int], dict[str, Any]] = {
        (str(atom.get("chain_id") or "_"), int(atom.get("resseq") or 0)): atom
        for atom in atoms
        if atom.get("atom_name") == "CA"
    }
    residue_counts = _residue_class_counts_from_atoms(atoms)
    segments: list[dict[str, Any]] = []
    ca_spheres: list[tuple[float, tuple[int, int], int, tuple[int, int, int], int]] = []
    for chain_id, trace in chains.items():
        projected = projected_by_chain.get(chain_id, [])
        for first_atom, second_atom, first_point, second_point in zip(trace, trace[1:], projected, projected[1:]):
            first = screen_from_projected(first_point)
            second = screen_from_projected(second_point)
            depth = (first[2] + second[2]) / 2.0
            residue_class = _residue_class(str(first_atom.get("resname") or "UNK"))
            color = _rgb(RESIDUE_CLASS_COLORS.get(residue_class, RESIDUE_CLASS_COLORS["unknown"]))
            segments.append(
                {
                    "depth": depth,
                    "points": [(first[0], first[1]), (second[0], second[1])],
                    "color": color,
                    "width": int(round((7.0 + depth * 10.0) * supersample)),
                }
            )
        step = max(1, math.ceil(len(trace) / 150))
        for atom, point in zip(trace[::step], projected[::step]):
            sx, sy, depth = screen_from_projected(point)
            residue_class = _residue_class(str(atom.get("resname") or "UNK"))
            color = _rgb(RESIDUE_CLASS_COLORS.get(residue_class, RESIDUE_CLASS_COLORS["unknown"]))
            ca_spheres.append((depth, (sx, sy), int(round((4.0 + depth * 5.5) * supersample)), color, int(round(170 + depth * 70))))

    atom_overlay_rows: list[tuple[float, tuple[int, int], int, tuple[int, int, int], int]] = []
    non_ca_atoms = [atom for atom in atoms if atom.get("atom_name") != "CA"]
    if non_ca_atoms:
        atom_step = max(1, math.ceil(len(non_ca_atoms) / 2400))
        for atom in non_ca_atoms[::atom_step]:
            key = (str(atom.get("chain_id") or "_"), int(atom.get("resseq") or 0))
            ca_atom = ca_by_key.get(key, atom)
            projected = _rotate_project((atom["x"], atom["y"], atom["z"]), center, elev=32, azim=-52)
            sx, sy, depth = screen_from_projected((projected[0], projected[1], projected[2], float(atom.get("b_factor", 0.0))))
            residue_class = _residue_class(str(ca_atom.get("resname") or atom.get("resname") or "UNK"))
            color = _rgb(RESIDUE_CLASS_COLORS.get(residue_class, RESIDUE_CLASS_COLORS["unknown"]))
            atom_overlay_rows.append((depth, (sx, sy), int(round((1.5 + depth * 2.4) * supersample)), color, int(round(70 + depth * 95))))

    for segment in sorted(segments, key=lambda item: item["depth"]):
        offset = int(round((4.0 + 6.0 * float(segment["depth"])) * supersample))
        shadow_points = [(x + offset, y + offset) for x, y in segment["points"]]
        draw.line(shadow_points, fill=(0, 0, 0, 86), width=int(segment["width"]) + 8 * supersample)
    for segment in sorted(segments, key=lambda item: item["depth"]):
        depth = float(segment["depth"])
        base = _mix((20, 28, 44), segment["color"], 0.50 + depth * 0.43)
        rim = _mix((255, 255, 255), base, 0.75)
        draw.line(segment["points"], fill=(*base, 236), width=int(segment["width"]))
        draw.line(segment["points"], fill=(*rim, 84), width=max(1, int(segment["width"]) // 3))
    for _depth, center_xy, radius, color, alpha in sorted(atom_overlay_rows, key=lambda item: item[0]):
        _draw_shaded_sphere(draw, center_xy, max(1, radius), color, alpha=alpha)
    for _depth, center_xy, radius, color, alpha in sorted(ca_spheres, key=lambda item: item[0]):
        _draw_shaded_sphere(draw, center_xy, radius, color, alpha=alpha)

    font = ImageFont.load_default()
    draw.text((54 * supersample, 38 * supersample), f"{target_id} residue-class molecular map", fill=(226, 232, 240, 255), font=font)
    draw.text(
        (54 * supersample, 62 * supersample),
        "Internal predicted coordinates colored by residue class; useful for hydrophobic/polar/charged visual triage.",
        fill=(148, 163, 184, 255),
        font=font,
    )

    legend_order = ["hydrophobic", "polar", "positive", "negative", "aromatic", "special", "unknown"]
    legend_y = canvas_h - 120 * supersample
    legend_x = 54 * supersample
    for index, key in enumerate(legend_order):
        x = legend_x + (index % 4) * 350 * supersample
        y = legend_y + (index // 4) * 38 * supersample
        color = _rgb(RESIDUE_CLASS_COLORS[key])
        draw.rounded_rectangle([x, y, x + 24 * supersample, y + 24 * supersample], radius=6 * supersample, fill=(*color, 255))
        draw.text(
            (x + 34 * supersample, y + 5 * supersample),
            f"{key} {int(residue_counts.get(key, 0))}",
            fill=(203, 213, 225, 255),
            font=font,
        )
    draw.text(
        (54 * supersample, canvas_h - 38 * supersample),
        "Visualization only; no template/native/external predictor evidence is implied.",
        fill=(148, 163, 184, 255),
        font=font,
    )
    image = image.resize((width, height), Image.Resampling.LANCZOS)
    out.parent.mkdir(parents=True, exist_ok=True)
    image.save(out, quality=95)
    return _artifact(out)


def _write_interface_contact_map(
    target_id: str,
    chains: dict[str, list[dict[str, Any]]],
    interface_summary: dict[str, Any],
    out_dir: str | Path,
    *,
    width: int,
    height: int,
) -> str:
    out = _resolve(out_dir) / f"{target_id}_structure_interface_map.png"
    image = Image.new("RGB", (width, height), "#07111f")
    draw = ImageDraw.Draw(image, "RGBA")
    _draw_gradient_background(draw, width, height, "#07111f", "#111827")
    font = ImageFont.load_default()

    margin = 54
    draw.text((margin, 34), f"{target_id} chain interface contact map", fill=(226, 232, 240, 255), font=font)
    draw.text(
        (margin, 60),
        "Internal CA-contact summary from predicted coordinates; no native/template evidence is implied.",
        fill=(148, 163, 184, 255),
        font=font,
    )

    chain_ids = sorted(chains)
    pair_rows = list(interface_summary.get("pairs") or [])
    if len(chain_ids) < 2 or not pair_rows:
        box = (margin, 130, width - margin, height - 138)
        draw.rounded_rectangle(box, radius=24, fill=(15, 23, 42, 210), outline=(71, 85, 105, 220), width=2)
        draw.text((box[0] + 28, box[1] + 30), "Single-chain target or no inter-chain CA contacts within 12 A.", fill=(203, 213, 225, 255), font=font)
        draw.text((box[0] + 28, box[1] + 58), f"chains={len(chain_ids)} | interface_pair_count=0", fill=(148, 163, 184, 255), font=font)
        out.parent.mkdir(parents=True, exist_ok=True)
        image.save(out, quality=95)
        return _artifact(out)

    contacts_by_pair = {
        (str(row["left_chain_id"]), str(row["right_chain_id"])): int(row.get("ca_contacts_12a") or 0)
        for row in pair_rows
    }
    min_by_pair = {
        (str(row["left_chain_id"]), str(row["right_chain_id"])): float(row.get("min_ca_distance_A") or 0.0)
        for row in pair_rows
    }
    max_contacts = max(1, max(contacts_by_pair.values()))
    matrix_size = min(760, max(280, height - 330))
    cell = max(22, matrix_size // max(1, len(chain_ids)))
    matrix_size = cell * len(chain_ids)
    matrix_left = margin
    matrix_top = 136

    draw.rounded_rectangle(
        (matrix_left - 18, matrix_top - 42, matrix_left + matrix_size + 34, matrix_top + matrix_size + 34),
        radius=24,
        fill=(15, 23, 42, 176),
        outline=(71, 85, 105, 210),
        width=2,
    )
    draw.text((matrix_left, matrix_top - 30), "CA contacts <=12 A", fill=(203, 213, 225, 255), font=font)
    for row_index, left_chain in enumerate(chain_ids):
        draw.text((matrix_left - 28, matrix_top + row_index * cell + cell // 2 - 5), left_chain, fill=(203, 213, 225, 255), font=font)
        draw.text((matrix_left + row_index * cell + cell // 2 - 4, matrix_top - 18), left_chain, fill=(203, 213, 225, 255), font=font)
        for column_index, right_chain in enumerate(chain_ids):
            x0 = matrix_left + column_index * cell
            y0 = matrix_top + row_index * cell
            if row_index == column_index:
                fill = (30, 41, 59, 210)
                label = "-"
            else:
                key = tuple(sorted((left_chain, right_chain)))
                contacts = contacts_by_pair.get(key, 0)
                t = contacts / max_contacts
                fill = _mix_rgba((15, 23, 42), (37, 99, 235), t, alpha=235)
                label = str(contacts) if contacts and cell >= 38 else ""
            draw.rectangle((x0, y0, x0 + cell - 2, y0 + cell - 2), fill=fill, outline=(51, 65, 85, 160))
            if label:
                draw.text((x0 + 6, y0 + cell // 2 - 5), label, fill=(241, 245, 249, 255), font=font)

    panel_left = matrix_left + matrix_size + 74
    panel_top = matrix_top - 42
    panel_right = width - margin
    panel_bottom = height - 116
    draw.rounded_rectangle((panel_left, panel_top, panel_right, panel_bottom), radius=24, fill=(15, 23, 42, 184), outline=(71, 85, 105, 210), width=2)
    metrics = [
        f"chains: {len(chain_ids)}",
        f"chain pairs: {interface_summary.get('pair_count', 0)}",
        f"contacts <=8A: {interface_summary.get('total_ca_contacts_8a', 0)}",
        f"contacts <=12A: {interface_summary.get('total_ca_contacts_12a', 0)}",
        f"min inter-chain CA: {float(interface_summary.get('min_interchain_ca_distance_A') or 0.0):.2f} A",
    ]
    y = panel_top + 26
    for metric in metrics:
        draw.text((panel_left + 24, y), metric, fill=(226, 232, 240, 255), font=font)
        y += 28
    y += 10
    draw.text((panel_left + 24, y), "Top chain-pair contacts", fill=(203, 213, 225, 255), font=font)
    y += 28
    for row in pair_rows[:12]:
        contacts = int(row.get("ca_contacts_12a") or 0)
        t = contacts / max_contacts
        bar_w = int((panel_right - panel_left - 210) * t)
        y_mid = y + 7
        draw.text((panel_left + 24, y), str(row.get("chain_pair") or ""), fill=(226, 232, 240, 255), font=font)
        draw.rounded_rectangle((panel_left + 96, y + 2, panel_left + 96 + bar_w, y + 18), radius=5, fill=(37, 99, 235, 220))
        draw.text(
            (panel_right - 96, y),
            f"{contacts} / {float(row.get('min_ca_distance_A') or 0.0):.2f}A",
            fill=(148, 163, 184, 255),
            font=font,
        )
        y = y_mid + 20
        if y > panel_bottom - 26:
            break

    draw.text(
        (margin, height - 70),
        "Interface map is a predicted-coordinate review aid. CASP assembly win-tier still requires no-leak native DockQ/interface benchmark evidence.",
        fill=(148, 163, 184, 255),
        font=font,
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    image.save(out, quality=95)
    return _artifact(out)


def _write_pymol_script(
    target_id: str,
    pdb_path: str | Path,
    out_dir: str | Path,
    chains: dict[str, list[dict[str, Any]]],
    *,
    width: int,
    height: int,
    dpi: int,
) -> tuple[str, str]:
    out_root = _resolve(out_dir)
    out_root.mkdir(parents=True, exist_ok=True)
    png_path = out_root / f"{target_id}_structure_pymol.png"
    pml_path = out_root / f"{target_id}_structure_pymol.pml"
    model = _safe_pymol_name(target_id)
    lines = [
        "reinitialize",
        "set quiet, 1",
        "set internal_gui, 0",
        f"viewport {int(width)}, {int(height)}",
        f"load {_pml_quote(_artifact(pdb_path))}, {model}",
        f"hide everything, {model}",
        f"remove {model} and elem H",
        "bg_color 0x08111f",
        "set ray_opaque_background, on",
        "set antialias, 2",
        "set ambient, 0.34",
        "set direct, 0.72",
        "set spec_reflect, 0.32",
        "set spec_power, 180",
        "set ray_shadow, 1",
        "set depth_cue, 1",
        "set fog_start, 0.38",
        "set fog_end, 1.0",
        "set cartoon_fancy_helices, 1",
        "set cartoon_smooth_loops, 1",
        "set cartoon_sampling, 14",
        "set cartoon_quality, 24",
        "set stick_quality, 18",
        "set sphere_quality, 2",
        "set stick_radius, 0.115",
        "set stick_ball, on",
        "set stick_ball_ratio, 1.25",
        "set sphere_scale, 0.22",
        f"show cartoon, {model}",
        f"show sticks, {model} and not name N+C+O+CA",
        f"show spheres, {model} and name CA",
    ]
    for chain_index, chain_id in enumerate(sorted(chains)):
        if chain_id == "_":
            continue
        color = _rgb(CHAIN_COLORS[chain_index % len(CHAIN_COLORS)])
        color_name = f"casp17_chain_{chain_index}"
        rgb_fraction = [round(channel / 255.0, 4) for channel in color]
        lines.extend(
            [
                f"set_color {color_name}, [{rgb_fraction[0]}, {rgb_fraction[1]}, {rgb_fraction[2]}]",
                f"color {color_name}, {model} and chain {chain_id}",
            ]
        )
    lines.extend(
        [
            f"orient {model}",
            f"zoom {model}, 1.10",
            "rotate x, 8",
            "rotate y, -10",
            f"ray {int(width)}, {int(height)}",
            f"png {_artifact(png_path)}, dpi={int(dpi)}",
            "quit",
            "",
        ]
    )
    pml_path.write_text("\n".join(lines), encoding="utf-8")
    return _artifact(pml_path), _artifact(png_path)


def _pymol_residue_selection(model: str, hotspot: dict[str, Any]) -> str:
    chain_id = str(hotspot.get("chain_id") or "_")
    resseq = int(hotspot.get("resseq") or 0)
    chain_clause = "" if chain_id == "_" else f" and chain {chain_id}"
    return f"({model}{chain_clause} and resi {resseq})"


def _write_pymol_qc_script(
    target_id: str,
    pdb_path: str | Path,
    out_dir: str | Path,
    chains: dict[str, list[dict[str, Any]]],
    hotspots: list[dict[str, Any]],
    *,
    width: int,
    height: int,
    dpi: int,
) -> tuple[str, str]:
    out_root = _resolve(out_dir)
    out_root.mkdir(parents=True, exist_ok=True)
    png_path = out_root / f"{target_id}_structure_qc_pymol.png"
    pml_path = out_root / f"{target_id}_structure_qc_pymol.pml"
    model = _safe_pymol_name(f"{target_id}_qc")
    lines = [
        "# CASP17 QC overlay: soft close-contact and low-confidence residue markers.",
        "# Visualization of internal predicted coordinates only; not official CASP accuracy evidence.",
        "reinitialize",
        "set quiet, 1",
        "set internal_gui, 0",
        f"viewport {int(width)}, {int(height)}",
        f"load {_pml_quote(_artifact(pdb_path))}, {model}",
        f"hide everything, {model}",
        f"remove {model} and elem H",
        "bg_color 0x08111f",
        "set ray_opaque_background, on",
        "set antialias, 2",
        "set ambient, 0.38",
        "set direct, 0.68",
        "set spec_reflect, 0.26",
        "set spec_power, 150",
        "set ray_shadow, 1",
        "set depth_cue, 1",
        "set fog_start, 0.34",
        "set fog_end, 1.0",
        "set cartoon_fancy_helices, 1",
        "set cartoon_smooth_loops, 1",
        "set cartoon_sampling, 14",
        "set cartoon_quality, 24",
        "set stick_quality, 20",
        "set sphere_quality, 3",
        "set stick_radius, 0.10",
        "set stick_ball, on",
        "set stick_ball_ratio, 1.22",
        "set sphere_scale, 0.24",
        f"show cartoon, {model}",
        f"show sticks, {model} and not name N+C+O+CA",
        f"show spheres, {model} and name CA",
        f"set cartoon_transparency, 0.22, {model}",
        f"set stick_transparency, 0.18, {model} and not name N+C+O+CA",
        "set_color casp17_qc_soft, [1.0, 0.20, 0.12]",
        "set_color casp17_qc_low, [1.0, 0.70, 0.12]",
        "set_color casp17_qc_dual, [0.82, 0.22, 1.0]",
        "set_color casp17_qc_base, [0.55, 0.65, 0.78]",
        f"color casp17_qc_base, {model}",
    ]
    for chain_index, chain_id in enumerate(sorted(chains)):
        if chain_id == "_":
            continue
        color = _rgb(CHAIN_COLORS[chain_index % len(CHAIN_COLORS)])
        mixed = _mix((148, 163, 184), color, 0.58)
        color_name = f"casp17_qc_chain_{chain_index}"
        rgb_fraction = [round(channel / 255.0, 4) for channel in mixed]
        lines.extend(
            [
                f"set_color {color_name}, [{rgb_fraction[0]}, {rgb_fraction[1]}, {rgb_fraction[2]}]",
                f"color {color_name}, {model} and chain {chain_id}",
            ]
        )
    for index, hotspot in enumerate(hotspots, start=1):
        selection_name = _safe_pymol_selection_name("qc_hotspot", index)
        selection = _pymol_residue_selection(model, hotspot)
        hotspot_type = str(hotspot.get("hotspot_type") or "")
        color_name = "casp17_qc_soft"
        if hotspot_type == "low_confidence":
            color_name = "casp17_qc_low"
        elif hotspot_type == "soft_contact_low_confidence":
            color_name = "casp17_qc_dual"
        lines.extend(
            [
                f"select {selection_name}, {selection}",
                f"color {color_name}, {selection_name}",
                f"show sticks, {selection_name}",
                f"show spheres, {selection_name} and name CA",
                f"set sphere_scale, 0.48, {selection_name} and name CA",
            ]
        )
        if index <= 10:
            label = f"{hotspot['chain_id']}:{hotspot['resseq']}"
            lines.append(f"label {selection_name} and name CA, {_pml_quote(label)}")
    lines.extend(
        [
            "set label_color, white",
            "set label_size, 14",
            f"orient {model}",
            f"zoom {model}, 1.08",
            "rotate x, 8",
            "rotate y, -10",
            f"ray {int(width)}, {int(height)}",
            f"png {_artifact(png_path)}, dpi={int(dpi)}",
            "quit",
            "",
        ]
    )
    pml_path.write_text("\n".join(lines), encoding="utf-8")
    return _artifact(pml_path), _artifact(png_path)


def _write_pymol_surface_script(
    target_id: str,
    pdb_path: str | Path,
    out_dir: str | Path,
    chains: dict[str, list[dict[str, Any]]],
    *,
    width: int,
    height: int,
    dpi: int,
) -> tuple[str, str]:
    out_root = _resolve(out_dir)
    out_root.mkdir(parents=True, exist_ok=True)
    png_path = out_root / f"{target_id}_structure_surface_pymol.png"
    pml_path = out_root / f"{target_id}_structure_surface_pymol.pml"
    model = _safe_pymol_name(f"{target_id}_surface")
    lines = [
        "# CASP17 molecular inspection render: transparent surface plus cartoon/CA context.",
        "# Visualization of internal predicted coordinates only; not official CASP accuracy evidence.",
        "reinitialize",
        "set quiet, 1",
        "set internal_gui, 0",
        f"viewport {int(width)}, {int(height)}",
        f"load {_pml_quote(_artifact(pdb_path))}, {model}",
        f"hide everything, {model}",
        f"remove {model} and elem H",
        "bg_color 0x06101f",
        "set ray_opaque_background, on",
        "set antialias, 2",
        "set ambient, 0.30",
        "set direct, 0.76",
        "set reflect, 0.28",
        "set spec_reflect, 0.22",
        "set spec_power, 160",
        "set ray_shadow, 1",
        "set depth_cue, 1",
        "set fog_start, 0.33",
        "set fog_end, 1.0",
        "set two_sided_lighting, on",
        "set cartoon_fancy_helices, 1",
        "set cartoon_smooth_loops, 1",
        "set cartoon_sampling, 16",
        "set cartoon_quality, 28",
        "set sphere_quality, 3",
        "set sphere_scale, 0.20",
        "set surface_quality, 0",
        f"show surface, {model}",
        f"show cartoon, {model}",
        f"show spheres, {model} and name CA",
        f"set transparency, 0.46, {model}",
        f"set cartoon_transparency, 0.08, {model}",
        "set_color casp17_surface_base, [0.60, 0.68, 0.80]",
        f"color casp17_surface_base, {model}",
    ]
    for chain_index, chain_id in enumerate(sorted(chains)):
        if chain_id == "_":
            continue
        color = _rgb(CHAIN_COLORS[chain_index % len(CHAIN_COLORS)])
        soft_color = _mix((226, 232, 240), color, 0.70)
        color_name = f"casp17_surface_chain_{chain_index}"
        rgb_fraction = [round(channel / 255.0, 4) for channel in soft_color]
        lines.extend(
            [
                f"set_color {color_name}, [{rgb_fraction[0]}, {rgb_fraction[1]}, {rgb_fraction[2]}]",
                f"color {color_name}, {model} and chain {chain_id}",
            ]
        )
    lines.extend(
        [
            f"orient {model}",
            f"zoom {model}, 1.06",
            "rotate x, 12",
            "rotate y, -18",
            f"ray {int(width)}, {int(height)}",
            f"png {_artifact(png_path)}, dpi={int(dpi)}",
            "quit",
            "",
        ]
    )
    pml_path.write_text("\n".join(lines), encoding="utf-8")
    return _artifact(pml_path), _artifact(png_path)


def _write_pymol_confidence_script(
    target_id: str,
    pdb_path: str | Path,
    out_dir: str | Path,
    chains: dict[str, list[dict[str, Any]]],
    atoms: list[dict[str, Any]],
    *,
    width: int,
    height: int,
    dpi: int,
) -> tuple[str, str]:
    out_root = _resolve(out_dir)
    out_root.mkdir(parents=True, exist_ok=True)
    png_path = out_root / f"{target_id}_structure_confidence_pymol.png"
    pml_path = out_root / f"{target_id}_structure_confidence_pymol.pml"
    model = _safe_pymol_name(f"{target_id}_confidence")
    stats = _confidence_stats(atoms)
    b_min = float(stats["confidence_b_factor_min"])
    b_max = float(stats["confidence_b_factor_max"])
    span = max(1e-6, b_max - b_min)
    bins = [
        ("casp17_conf_very_low", b_min - 0.001, b_min + span * 0.35, CONFIDENCE_STOPS[0][1]),
        ("casp17_conf_low", b_min + span * 0.35, b_min + span * 0.55, CONFIDENCE_STOPS[1][1]),
        ("casp17_conf_medium", b_min + span * 0.55, b_min + span * 0.78, CONFIDENCE_STOPS[2][1]),
        ("casp17_conf_high", b_min + span * 0.78, b_max + 0.001, CONFIDENCE_STOPS[3][1]),
    ]
    lines = [
        "# CASP17 confidence render: PDB B-factor/pLDDT-style confidence coloring.",
        "# Visualization of internal predicted coordinates only; not official CASP accuracy evidence.",
        "reinitialize",
        "set quiet, 1",
        "set internal_gui, 0",
        f"viewport {int(width)}, {int(height)}",
        f"load {_pml_quote(_artifact(pdb_path))}, {model}",
        f"hide everything, {model}",
        f"remove {model} and elem H",
        "bg_color 0x08111f",
        "set ray_opaque_background, on",
        "set antialias, 2",
        "set ambient, 0.36",
        "set direct, 0.70",
        "set spec_reflect, 0.30",
        "set spec_power, 170",
        "set ray_shadow, 1",
        "set depth_cue, 1",
        "set fog_start, 0.36",
        "set fog_end, 1.0",
        "set cartoon_fancy_helices, 1",
        "set cartoon_smooth_loops, 1",
        "set cartoon_sampling, 16",
        "set cartoon_quality, 28",
        "set stick_quality, 20",
        "set sphere_quality, 3",
        "set stick_radius, 0.11",
        "set sphere_scale, 0.22",
        f"show cartoon, {model}",
        f"show sticks, {model} and not name N+C+O+CA",
        f"show spheres, {model} and name CA",
    ]
    for color_name, low, high, color in bins:
        rgb_fraction = [round(channel / 255.0, 4) for channel in color]
        lines.append(f"set_color {color_name}, [{rgb_fraction[0]}, {rgb_fraction[1]}, {rgb_fraction[2]}]")
        lines.append(f"color {color_name}, {model} and b >= {low:.3f} and b < {high:.3f}")
    for chain_index, chain_id in enumerate(sorted(chains)):
        if chain_id == "_":
            continue
        lines.append(f"show cartoon, {model} and chain {chain_id}")
    lines.extend(
        [
            f"orient {model}",
            f"zoom {model}, 1.08",
            "rotate x, 8",
            "rotate y, -12",
            f"ray {int(width)}, {int(height)}",
            f"png {_artifact(png_path)}, dpi={int(dpi)}",
            "quit",
            "",
        ]
    )
    pml_path.write_text("\n".join(lines), encoding="utf-8")
    return _artifact(pml_path), _artifact(png_path)


def _write_pymol_render(
    target_id: str,
    pdb_path: str | Path,
    out_dir: str | Path,
    chains: dict[str, list[dict[str, Any]]],
    *,
    executable: str,
    reuse_existing: bool,
    width: int,
    height: int,
    dpi: int,
) -> dict[str, str]:
    resolved_executable = _find_pymol_executable(executable)
    pml_artifact, png_artifact = _write_pymol_script(target_id, pdb_path, out_dir, chains, width=width, height=height, dpi=dpi)
    if not resolved_executable:
        return {
            "pymol_render_status": "skipped",
            "pymol_png_path": "",
            "pymol_script_path": pml_artifact,
            "pymol_blockers": "pymol_executable_missing",
        }
    png_path = _resolve(png_artifact)
    if reuse_existing and png_path.exists() and png_path.stat().st_size > 0:
        return {
            "pymol_render_status": "rendered",
            "pymol_png_path": png_artifact,
            "pymol_script_path": pml_artifact,
            "pymol_blockers": "",
        }
    if png_path.exists():
        png_path.unlink()
    try:
        result = subprocess.run(
            [resolved_executable, "-cq", str(_resolve(pml_artifact))],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=300,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "pymol_render_status": "blocked",
            "pymol_png_path": "",
            "pymol_script_path": pml_artifact,
            "pymol_blockers": f"pymol_execution_failed:{type(exc).__name__}",
        }
    if result.returncode != 0 or not png_path.exists() or png_path.stat().st_size == 0:
        stderr_tail = " ".join((result.stderr or result.stdout or "").split())[-160:]
        return {
            "pymol_render_status": "blocked",
            "pymol_png_path": "",
            "pymol_script_path": pml_artifact,
            "pymol_blockers": f"pymol_render_failed:{stderr_tail}" if stderr_tail else "pymol_render_failed",
        }
    return {
        "pymol_render_status": "rendered",
        "pymol_png_path": png_artifact,
        "pymol_script_path": pml_artifact,
        "pymol_blockers": "",
    }


def _write_pymol_qc_render(
    target_id: str,
    pdb_path: str | Path,
    out_dir: str | Path,
    chains: dict[str, list[dict[str, Any]]],
    atoms: list[dict[str, Any]],
    *,
    executable: str,
    reuse_existing: bool,
    width: int,
    height: int,
    dpi: int,
) -> dict[str, Any]:
    qc_analysis = _qc_hotspot_analysis(atoms)
    hotspots = list(qc_analysis["hotspots"])
    display_hotspots = hotspots[:MAX_QC_HOTSPOTS]
    resolved_executable = _find_pymol_executable(executable)
    pml_artifact, png_artifact = _write_pymol_qc_script(
        target_id,
        pdb_path,
        out_dir,
        chains,
        display_hotspots,
        width=width,
        height=height,
        dpi=dpi,
    )
    soft_count = sum(1 for hotspot in hotspots if int(hotspot.get("soft_contact_count") or 0) > 0)
    low_count = sum(1 for hotspot in hotspots if bool(hotspot.get("low_confidence")))
    display_soft_count = sum(1 for hotspot in display_hotspots if int(hotspot.get("soft_contact_count") or 0) > 0)
    display_low_count = sum(1 for hotspot in display_hotspots if bool(hotspot.get("low_confidence")))
    base_result: dict[str, Any] = {
        "pymol_qc_png_path": "",
        "pymol_qc_script_path": pml_artifact,
        "pymol_qc_hotspot_count": len(display_hotspots),
        "pymol_qc_soft_hotspot_count": display_soft_count,
        "pymol_qc_low_confidence_hotspot_count": display_low_count,
        "pymol_qc_total_hotspot_count": len(hotspots),
        "pymol_qc_total_soft_hotspot_count": soft_count,
        "pymol_qc_total_low_confidence_hotspot_count": low_count,
        "pymol_qc_hotspot_raw_count": len(hotspots),
        "pymol_qc_soft_hotspot_raw_count": soft_count,
        "pymol_qc_low_confidence_hotspot_raw_count": low_count,
        "pymol_qc_display_hotspot_count": len(display_hotspots),
        "pymol_qc_display_soft_hotspot_count": display_soft_count,
        "pymol_qc_display_low_confidence_hotspot_count": display_low_count,
        "pymol_qc_rendered_hotspot_count": len(display_hotspots),
        "pymol_qc_rendered_soft_hotspot_count": display_soft_count,
        "pymol_qc_rendered_low_confidence_hotspot_count": display_low_count,
        "pymol_qc_display_hotspot_limit": MAX_QC_HOTSPOTS,
        "pymol_qc_hotspot_marker_cap": MAX_QC_HOTSPOTS,
        "pymol_qc_hotspot_truncated": len(hotspots) > len(display_hotspots),
        "pymol_qc_low_confidence_cutoff": qc_analysis["low_confidence_cutoff"],
        "pymol_qc_confidence_span": qc_analysis["confidence_span"],
        "pymol_qc_top_hotspots": hotspots[:10],
        "pymol_qc_hotspot_top_details": hotspots[:10],
    }
    if not resolved_executable:
        return {
            **base_result,
            "pymol_qc_render_status": "skipped",
            "pymol_qc_blockers": "pymol_executable_missing",
        }
    png_path = _resolve(png_artifact)
    if reuse_existing and png_path.exists() and png_path.stat().st_size > 0:
        return {
            **base_result,
            "pymol_qc_render_status": "rendered",
            "pymol_qc_png_path": png_artifact,
            "pymol_qc_blockers": "",
        }
    if png_path.exists():
        png_path.unlink()
    try:
        result = subprocess.run(
            [resolved_executable, "-cq", str(_resolve(pml_artifact))],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=300,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            **base_result,
            "pymol_qc_render_status": "blocked",
            "pymol_qc_blockers": f"pymol_qc_execution_failed:{type(exc).__name__}",
        }
    if result.returncode != 0 or not png_path.exists() or png_path.stat().st_size == 0:
        stderr_tail = " ".join((result.stderr or result.stdout or "").split())[-160:]
        return {
            **base_result,
            "pymol_qc_render_status": "blocked",
            "pymol_qc_blockers": f"pymol_qc_render_failed:{stderr_tail}" if stderr_tail else "pymol_qc_render_failed",
        }
    return {
        **base_result,
        "pymol_qc_render_status": "rendered",
        "pymol_qc_png_path": png_artifact,
        "pymol_qc_blockers": "",
    }


def _write_pymol_surface_render(
    target_id: str,
    pdb_path: str | Path,
    out_dir: str | Path,
    chains: dict[str, list[dict[str, Any]]],
    *,
    executable: str,
    reuse_existing: bool,
    width: int,
    height: int,
    dpi: int,
) -> dict[str, str]:
    resolved_executable = _find_pymol_executable(executable)
    pml_artifact, png_artifact = _write_pymol_surface_script(
        target_id,
        pdb_path,
        out_dir,
        chains,
        width=width,
        height=height,
        dpi=dpi,
    )
    if not resolved_executable:
        return {
            "pymol_surface_render_status": "skipped",
            "pymol_surface_png_path": "",
            "pymol_surface_script_path": pml_artifact,
            "pymol_surface_blockers": "pymol_executable_missing",
        }
    png_path = _resolve(png_artifact)
    if reuse_existing and png_path.exists() and png_path.stat().st_size > 0:
        return {
            "pymol_surface_render_status": "rendered",
            "pymol_surface_png_path": png_artifact,
            "pymol_surface_script_path": pml_artifact,
            "pymol_surface_blockers": "",
        }
    if png_path.exists():
        png_path.unlink()
    try:
        result = subprocess.run(
            [resolved_executable, "-cq", str(_resolve(pml_artifact))],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=300,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "pymol_surface_render_status": "blocked",
            "pymol_surface_png_path": "",
            "pymol_surface_script_path": pml_artifact,
            "pymol_surface_blockers": f"pymol_surface_execution_failed:{type(exc).__name__}",
        }
    if result.returncode != 0 or not png_path.exists() or png_path.stat().st_size == 0:
        stderr_tail = " ".join((result.stderr or result.stdout or "").split())[-160:]
        return {
            "pymol_surface_render_status": "blocked",
            "pymol_surface_png_path": "",
            "pymol_surface_script_path": pml_artifact,
            "pymol_surface_blockers": f"pymol_surface_render_failed:{stderr_tail}" if stderr_tail else "pymol_surface_render_failed",
        }
    return {
        "pymol_surface_render_status": "rendered",
        "pymol_surface_png_path": png_artifact,
        "pymol_surface_script_path": pml_artifact,
        "pymol_surface_blockers": "",
    }


def _write_pymol_confidence_render(
    target_id: str,
    pdb_path: str | Path,
    out_dir: str | Path,
    chains: dict[str, list[dict[str, Any]]],
    atoms: list[dict[str, Any]],
    *,
    executable: str,
    reuse_existing: bool,
    width: int,
    height: int,
    dpi: int,
) -> dict[str, Any]:
    resolved_executable = _find_pymol_executable(executable)
    pml_artifact, png_artifact = _write_pymol_confidence_script(
        target_id,
        pdb_path,
        out_dir,
        chains,
        atoms,
        width=width,
        height=height,
        dpi=dpi,
    )
    stats = _confidence_stats(atoms)
    base_result: dict[str, Any] = {
        "pymol_confidence_png_path": "",
        "pymol_confidence_script_path": pml_artifact,
        **stats,
    }
    if not resolved_executable:
        return {
            **base_result,
            "pymol_confidence_render_status": "skipped",
            "pymol_confidence_blockers": "pymol_executable_missing",
        }
    png_path = _resolve(png_artifact)
    if reuse_existing and png_path.exists() and png_path.stat().st_size > 0:
        return {
            **base_result,
            "pymol_confidence_render_status": "rendered",
            "pymol_confidence_png_path": png_artifact,
            "pymol_confidence_blockers": "",
        }
    if png_path.exists():
        png_path.unlink()
    try:
        result = subprocess.run(
            [resolved_executable, "-cq", str(_resolve(pml_artifact))],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=300,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            **base_result,
            "pymol_confidence_render_status": "blocked",
            "pymol_confidence_blockers": f"pymol_confidence_execution_failed:{type(exc).__name__}",
        }
    if result.returncode != 0 or not png_path.exists() or png_path.stat().st_size == 0:
        stderr_tail = " ".join((result.stderr or result.stdout or "").split())[-160:]
        return {
            **base_result,
            "pymol_confidence_render_status": "blocked",
            "pymol_confidence_blockers": f"pymol_confidence_render_failed:{stderr_tail}" if stderr_tail else "pymol_confidence_render_failed",
        }
    return {
        **base_result,
        "pymol_confidence_render_status": "rendered",
        "pymol_confidence_png_path": png_artifact,
        "pymol_confidence_blockers": "",
    }


def _cover_image(image: Image.Image, box: tuple[int, int]) -> Image.Image:
    width, height = box
    source = image.convert("RGB")
    scale = max(width / max(1, source.width), height / max(1, source.height))
    resized = source.resize((int(round(source.width * scale)), int(round(source.height * scale))), Image.Resampling.LANCZOS)
    left = max(0, (resized.width - width) // 2)
    top = max(0, (resized.height - height) // 2)
    return resized.crop((left, top, left + width, top + height))


def _write_review_panel(target_id: str, row: dict[str, Any], out_dir: str | Path, *, width: int = 3000, height: int = 1500) -> str:
    base_artifact = _text(row.get("pymol_png_path"))
    surface_artifact = _text(row.get("pymol_surface_png_path"))
    qc_artifact = _text(row.get("pymol_qc_png_path"))
    if not base_artifact or not qc_artifact:
        return ""
    base_path = _resolve(base_artifact)
    surface_path = _resolve(surface_artifact) if surface_artifact else None
    qc_path = _resolve(qc_artifact)
    if not base_path.exists() or not qc_path.exists():
        return ""
    if surface_path is not None and not surface_path.exists():
        surface_path = None

    out = _resolve(out_dir) / f"{target_id}_structure_review_panel.png"
    canvas = Image.new("RGB", (width, height), "#06101f")
    draw = ImageDraw.Draw(canvas, "RGBA")
    _draw_gradient_background(draw, width, height, "#06101f", "#111827")

    margin = 44
    title_h = 104
    footer_h = 86
    gap = 28
    panel_count = 3 if surface_path is not None else 2
    panel_w = (width - margin * 2 - gap * (panel_count - 1)) // panel_count
    panel_h = height - title_h - footer_h - margin
    boxes = [
        (
            margin + index * (panel_w + gap),
            title_h,
            margin + index * (panel_w + gap) + panel_w,
            title_h + panel_h,
        )
        for index in range(panel_count)
    ]

    image_paths = [base_path]
    labels = ["Structure"]
    if surface_path is not None:
        image_paths.append(surface_path)
        labels.append("Surface")
    image_paths.append(qc_path)
    labels.append("QC overlay")
    for box, image_path in zip(boxes, image_paths):
        with Image.open(image_path) as source:
            canvas.paste(_cover_image(source, (panel_w, panel_h)), box[:2])

    for box in boxes:
        draw.rounded_rectangle(box, radius=18, outline=(148, 163, 184, 190), width=3)
    font = ImageFont.load_default()
    draw.text((margin, 34), f"{target_id} internal physics model review", fill=(226, 232, 240, 255), font=font)
    draw.text(
        (margin, 58),
        "PyMOL molecular render, transparent surface inspection, and QC overlay for capped soft-contact / low-confidence markers.",
        fill=(148, 163, 184, 255),
        font=font,
    )
    for box, label in zip(boxes, labels):
        draw.rectangle([box[0], box[1] - 28, box[0] + 150, box[1] - 6], fill=(15, 23, 42, 220))
        draw.text((box[0] + 10, box[1] - 25), label, fill=(226, 232, 240, 255), font=font)

    legend_y = height - footer_h + 20
    legend_items = [
        ((255, 51, 31), "soft close contact"),
        ((255, 179, 31), "low confidence"),
        ((209, 56, 255), "both"),
    ]
    x = margin
    for color, label in legend_items:
        draw.rounded_rectangle([x, legend_y, x + 24, legend_y + 24], radius=5, fill=(*color, 255))
        draw.text((x + 34, legend_y + 5), label, fill=(203, 213, 225, 255), font=font)
        x += 210
    metrics = (
        f"chains={row.get('chain_count', 0)} | CA={row.get('ca_count', 0)} | atoms={row.get('atom_count', 0)} | "
        f"QC total/display={row.get('pymol_qc_total_hotspot_count', row.get('pymol_qc_hotspot_count', 0))}/{row.get('pymol_qc_display_hotspot_count', 0)} "
        f"(soft={row.get('pymol_qc_total_soft_hotspot_count', row.get('pymol_qc_soft_hotspot_count', 0))}, "
        f"low={row.get('pymol_qc_total_low_confidence_hotspot_count', row.get('pymol_qc_low_confidence_hotspot_count', 0))})"
    )
    draw.text((margin, legend_y + 38), metrics, fill=(148, 163, 184, 255), font=font)
    draw.text(
        (width - 640, legend_y + 38),
        "Visualization only; not official CASP accuracy evidence.",
        fill=(148, 163, 184, 255),
        font=font,
    )

    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out, quality=95)
    return _artifact(out)


def _first_existing_artifact(*artifacts: str) -> Path | None:
    for artifact in artifacts:
        text = _text(artifact)
        if not text:
            continue
        path = _resolve(text)
        if path.exists() and path.stat().st_size > 0:
            return path
    return None


def _paste_labeled_panel(
    canvas: Image.Image,
    draw: ImageDraw.ImageDraw,
    image_path: Path | None,
    box: tuple[int, int, int, int],
    *,
    label: str,
    font: ImageFont.ImageFont,
) -> None:
    left, top, right, bottom = box
    draw.rounded_rectangle(box, radius=24, fill=(15, 23, 42, 226), outline=(71, 85, 105, 220), width=2)
    if image_path is not None:
        with Image.open(image_path) as source:
            canvas.paste(_cover_image(source, (right - left, bottom - top)), (left, top))
    else:
        draw.text((left + 26, top + 32), "image not available", fill=(148, 163, 184, 255), font=font)
    draw.rounded_rectangle(box, radius=24, outline=(148, 163, 184, 210), width=3)
    label_box = (left + 18, top + 18, left + min(480, right - left - 18), top + 58)
    draw.rounded_rectangle(label_box, radius=12, fill=(2, 6, 23, 205))
    draw.text((label_box[0] + 14, label_box[1] + 9), label, fill=(226, 232, 240, 255), font=font)


def _draw_secondary_proxy_strip(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    chains: dict[str, list[dict[str, Any]]],
    proxy: dict[tuple[str, int], str],
    *,
    font: ImageFont.ImageFont,
    small_font: ImageFont.ImageFont,
) -> None:
    left, top, right, bottom = box
    draw.rounded_rectangle(box, radius=18, fill=(15, 23, 42, 235), outline=(71, 85, 105, 220), width=2)
    draw.text((left + 22, top + 18), "CA geometry secondary-structure proxy", fill=(226, 232, 240, 255), font=font)
    draw.text((left + 22, top + 48), "Internal rule-based helix/strand/coil visual triage, not DSSP/native evidence.", fill=(148, 163, 184, 255), font=small_font)
    chain_ids = sorted(chains)
    if not chain_ids:
        return
    strip_left = left + 80
    strip_right = right - 28
    strip_top = top + 86
    available_h = max(24, bottom - strip_top - 48)
    row_h = max(18, min(42, available_h // max(1, len(chain_ids))))
    for row_index, chain_id in enumerate(chain_ids):
        trace = chains[chain_id]
        y0 = strip_top + row_index * row_h
        y1 = y0 + max(8, row_h - 8)
        draw.text((left + 22, y0 + 1), chain_id, fill=(203, 213, 225, 255), font=small_font)
        if not trace:
            continue
        for residue_index, atom in enumerate(trace):
            x0 = strip_left + int((strip_right - strip_left) * residue_index / max(1, len(trace)))
            x1 = strip_left + int((strip_right - strip_left) * (residue_index + 1) / max(1, len(trace)))
            label = proxy.get((str(chain_id), int(atom.get("resseq") or 0)), "coil_or_turn")
            color = _rgb(SECONDARY_PROXY_COLORS.get(label, SECONDARY_PROXY_COLORS["coil_or_turn"]))
            draw.rectangle([x0, y0, max(x0 + 1, x1), y1], fill=(*color, 230))
    legend_y = bottom - 34
    x = left + 22
    for key, label in [("helix_like", "helix-like"), ("strand_like", "strand-like"), ("coil_or_turn", "coil/turn")]:
        color = _rgb(SECONDARY_PROXY_COLORS[key])
        draw.rounded_rectangle([x, legend_y, x + 20, legend_y + 20], radius=5, fill=(*color, 255))
        draw.text((x + 28, legend_y + 2), label, fill=(203, 213, 225, 255), font=small_font)
        x += 174


def _write_presentation_plate(
    target_id: str,
    chains: dict[str, list[dict[str, Any]]],
    atoms: list[dict[str, Any]],
    row: dict[str, Any],
    interface_summary: dict[str, Any],
    out_dir: str | Path,
    *,
    width: int = 3840,
    height: int = 2160,
) -> str:
    out = _resolve(out_dir) / f"{target_id}_structure_presentation_plate.png"
    canvas = Image.new("RGB", (width, height), "#06101f")
    draw = ImageDraw.Draw(canvas, "RGBA")
    _draw_gradient_background(draw, width, height, "#06101f", "#111827")
    title_font = _font(44, bold=True)
    subtitle_font = _font(24)
    panel_font = _font(22, bold=True)
    metric_font = _font(22)
    small_font = _font(18)

    margin = 66
    gap = 34
    draw.text((margin, 38), f"{target_id} molecular presentation plate", fill=(241, 245, 249, 255), font=title_font)
    draw.text(
        (margin, 92),
        "Internal CASP17 predicted coordinates: molecular context, confidence, surface, QC, interface and geometry-proxy review in one plate.",
        fill=(148, 163, 184, 255),
        font=subtitle_font,
    )
    draw.text(
        (margin, 124),
        "Visualization only; not official CASP accuracy evidence, not a public/template/native lookup, and not an experimental structure.",
        fill=(148, 163, 184, 255),
        font=small_font,
    )

    main_box = (margin, 172, 2468, 1458)
    main_path = _first_existing_artifact(
        _text(row.get("pymol_png_path")),
        _text(row.get("studio_png_path")),
        _text(row.get("turntable_png_path")),
        _text(row.get("stereo_depth_png_path")),
        _text(row.get("publication_png_path")),
        _text(row.get("png_path")),
    )
    _paste_labeled_panel(canvas, draw, main_path, main_box, label="Primary molecular structure", font=panel_font)

    right_left = main_box[2] + gap
    right_right = width - margin
    thumb_w = (right_right - right_left - gap) // 2
    thumb_h = 416
    thumb_boxes = [
        (right_left + (index % 2) * (thumb_w + gap), 172 + (index // 2) * (thumb_h + gap), right_left + (index % 2) * (thumb_w + gap) + thumb_w, 172 + (index // 2) * (thumb_h + gap) + thumb_h)
        for index in range(6)
    ]
    thumb_items = [
        ("Confidence coloring", _first_existing_artifact(_text(row.get("pymol_confidence_png_path")), _text(row.get("publication_png_path")))),
        ("Transparent surface", _first_existing_artifact(_text(row.get("pymol_surface_png_path")), _text(row.get("studio_png_path")))),
        ("QC overlay", _first_existing_artifact(_text(row.get("pymol_qc_png_path")), _text(row.get("review_panel_png_path")))),
        ("Residue chemistry", _first_existing_artifact(_text(row.get("residue_class_png_path")))),
        ("Interface map", _first_existing_artifact(_text(row.get("interface_map_png_path")))),
        ("Turntable views", _first_existing_artifact(_text(row.get("turntable_png_path")), _text(row.get("stereo_depth_png_path")))),
    ]
    for box, (label, image_path) in zip(thumb_boxes, thumb_items):
        _paste_labeled_panel(canvas, draw, image_path, box, label=label, font=small_font)

    bottom_top = 1510
    bottom_bottom = height - 76
    secondary_box = (margin, bottom_top, 1540, bottom_bottom)
    proxy = _secondary_proxy_by_residue(chains)
    _draw_secondary_proxy_strip(draw, secondary_box, chains, proxy, font=panel_font, small_font=small_font)

    metrics_left = secondary_box[2] + gap
    metrics_box = (metrics_left, bottom_top, 2570, bottom_bottom)
    draw.rounded_rectangle(metrics_box, radius=18, fill=(15, 23, 42, 235), outline=(71, 85, 105, 220), width=2)
    draw.text((metrics_left + 22, bottom_top + 18), "CASP local readiness evidence", fill=(226, 232, 240, 255), font=panel_font)
    metric_rows = [
        ("chains", str(row.get("chain_count", 0))),
        ("CA / atoms", f"{row.get('ca_count', 0)} / {row.get('atom_count', 0)}"),
        ("sidechain atoms", str(row.get("sidechain_atom_count", 0))),
        ("confidence min/median/max", f"{float(row.get('confidence_b_factor_min') or 0.0):.1f}/{float(row.get('confidence_b_factor_median') or 0.0):.1f}/{float(row.get('confidence_b_factor_max') or 0.0):.1f}"),
        ("QC hotspots total/display", f"{row.get('pymol_qc_total_hotspot_count', row.get('pymol_qc_hotspot_count', 0))}/{row.get('pymol_qc_display_hotspot_count', 0)}"),
        ("soft / low-confidence", f"{row.get('pymol_qc_total_soft_hotspot_count', 0)} / {row.get('pymol_qc_total_low_confidence_hotspot_count', 0)}"),
        ("interface pairs", str(interface_summary.get("pair_count", 0))),
        ("CA contacts <=12A", str(interface_summary.get("total_ca_contacts_12a", 0))),
        ("min interchain CA", f"{float(interface_summary.get('min_interchain_ca_distance_A') or 0.0):.2f} A"),
    ]
    y = bottom_top + 66
    for label, value in metric_rows:
        draw.text((metrics_left + 22, y), label, fill=(148, 163, 184, 255), font=small_font)
        draw.text((metrics_box[2] - 250, y), value, fill=(226, 232, 240, 255), font=metric_font)
        draw.line([(metrics_left + 22, y + 31), (metrics_box[2] - 22, y + 31)], fill=(51, 65, 85, 170), width=1)
        y += 46

    counts_box = (metrics_box[2] + gap, bottom_top, width - margin, bottom_bottom)
    draw.rounded_rectangle(counts_box, radius=18, fill=(15, 23, 42, 235), outline=(71, 85, 105, 220), width=2)
    draw.text((counts_box[0] + 22, bottom_top + 18), "Chemistry and proxy counts", fill=(226, 232, 240, 255), font=panel_font)
    residue_counts = _residue_class_counts_from_atoms(atoms)
    secondary_counts = _secondary_proxy_counts(proxy)
    y = bottom_top + 72
    for key in ["hydrophobic", "polar", "positive", "negative", "aromatic", "special"]:
        color = _rgb(RESIDUE_CLASS_COLORS[key])
        draw.rounded_rectangle([counts_box[0] + 24, y, counts_box[0] + 50, y + 26], radius=6, fill=(*color, 255))
        draw.text((counts_box[0] + 64, y + 1), key, fill=(203, 213, 225, 255), font=small_font)
        draw.text((counts_box[2] - 86, y + 1), str(int(residue_counts.get(key, 0))), fill=(226, 232, 240, 255), font=metric_font)
        y += 42
    y += 12
    for key, label in [("helix_like", "helix-like"), ("strand_like", "strand-like"), ("coil_or_turn", "coil/turn")]:
        color = _rgb(SECONDARY_PROXY_COLORS[key])
        draw.rounded_rectangle([counts_box[0] + 24, y, counts_box[0] + 50, y + 26], radius=6, fill=(*color, 255))
        draw.text((counts_box[0] + 64, y + 1), label, fill=(203, 213, 225, 255), font=small_font)
        draw.text((counts_box[2] - 86, y + 1), str(int(secondary_counts.get(key, 0))), fill=(226, 232, 240, 255), font=metric_font)
        y += 42

    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out, quality=96)
    return _artifact(out)


def _write_atlas_panel(target_id: str, row: dict[str, Any], out_dir: str | Path, *, width: int = 3200, height: int = 2200) -> str:
    image_items = [
        ("Presentation plate", _text(row.get("presentation_plate_png_path"))),
        ("Molecular plate", _text(row.get("molecular_plate_png_path"))),
        ("Turntable review", _text(row.get("turntable_png_path"))),
        ("Stereo depth pair", _text(row.get("stereo_depth_png_path"))),
        ("Studio shaded model", _text(row.get("studio_png_path"))),
        ("Residue-class map", _text(row.get("residue_class_png_path"))),
        ("Interface contact map", _text(row.get("interface_map_png_path"))),
        ("Confidence color", _text(row.get("pymol_confidence_png_path"))),
        ("Transparent surface", _text(row.get("pymol_surface_png_path"))),
        ("QC overlay", _text(row.get("pymol_qc_png_path"))),
        ("PyMOL structure", _text(row.get("pymol_png_path"))),
    ]
    existing: list[tuple[str, Path]] = []
    for label, artifact in image_items:
        if not artifact:
            continue
        path = _resolve(artifact)
        if path.exists():
            existing.append((label, path))
    if len(existing) < 2:
        fallback = _text(row.get("publication_png_path")) or _text(row.get("png_path"))
        fallback_path = _resolve(fallback) if fallback else None
        if fallback_path is not None and fallback_path.exists():
            existing.append(("Internal trace", fallback_path))
    if len(existing) < 2:
        return ""

    out = _resolve(out_dir) / f"{target_id}_structure_atlas_panel.png"
    canvas = Image.new("RGB", (width, height), "#07111f")
    draw = ImageDraw.Draw(canvas, "RGBA")
    _draw_gradient_background(draw, width, height, "#07111f", "#111827")
    font = ImageFont.load_default()

    margin = 52
    title_h = 142
    footer_h = 154
    gap = 34
    grid_top = title_h
    grid_h = height - title_h - footer_h
    columns = 3 if len(existing) >= 5 else 2
    rows_n = 2
    cell_w = (width - margin * 2 - gap * (columns - 1)) // columns
    cell_h = (grid_h - gap * (rows_n - 1)) // rows_n
    boxes = []
    for row_index in range(rows_n):
        for column_index in range(columns):
            left = margin + column_index * (cell_w + gap)
            top = grid_top + row_index * (cell_h + gap)
            boxes.append((left, top, left + cell_w, top + cell_h))

    for (label, image_path), box in zip(existing[: len(boxes)], boxes):
        with Image.open(image_path) as source:
            canvas.paste(_cover_image(source, (box[2] - box[0], box[3] - box[1])), box[:2])
        draw.rounded_rectangle(box, radius=20, outline=(148, 163, 184, 210), width=3)
        draw.rectangle([box[0], box[1] - 32, box[0] + min(360, box[2] - box[0]), box[1] - 6], fill=(15, 23, 42, 230))
        draw.text((box[0] + 12, box[1] - 28), label, fill=(226, 232, 240, 255), font=font)

    draw.text((margin, 34), f"{target_id} molecular inspection atlas", fill=(226, 232, 240, 255), font=font)
    draw.text(
        (margin, 62),
        "Internal predicted coordinates: shaded molecular context, ray-traced structure, surface, and QC overlay.",
        fill=(148, 163, 184, 255),
        font=font,
    )
    draw.text(
        (margin, 88),
        "Use this atlas for human review triage; it is not native accuracy evidence and does not replace CASP assessment.",
        fill=(148, 163, 184, 255),
        font=font,
    )

    footer_y = height - footer_h + 28
    metrics = [
        f"chains={row.get('chain_count', 0)}",
        f"CA={row.get('ca_count', 0)}",
        f"atoms={row.get('atom_count', 0)}",
        f"sidechain_atoms={row.get('sidechain_atom_count', 0)}",
        f"QC_total={row.get('pymol_qc_total_hotspot_count', row.get('pymol_qc_hotspot_count', 0))}",
        f"QC_display={row.get('pymol_qc_display_hotspot_count', 0)}",
        f"soft={row.get('pymol_qc_total_soft_hotspot_count', row.get('pymol_qc_soft_hotspot_count', 0))}",
        f"low_conf={row.get('pymol_qc_total_low_confidence_hotspot_count', row.get('pymol_qc_low_confidence_hotspot_count', 0))}",
    ]
    draw.text((margin, footer_y), " | ".join(metrics), fill=(203, 213, 225, 255), font=font)
    legend_y = footer_y + 42
    legend_items = [
        ((255, 51, 31), "soft close contact"),
        ((255, 179, 31), "low confidence"),
        ((209, 56, 255), "both"),
    ]
    x = margin
    for color, label in legend_items:
        draw.rounded_rectangle([x, legend_y, x + 24, legend_y + 24], radius=5, fill=(*color, 255))
        draw.text((x + 34, legend_y + 5), label, fill=(203, 213, 225, 255), font=font)
        x += 238
    draw.text(
        (margin, legend_y + 42),
        "Atlas combines internal structure outputs only; no external predictor, template, public native, or official CASP result is implied.",
        fill=(148, 163, 184, 255),
        font=font,
    )

    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out, quality=95)
    return _artifact(out)


def _confidence_bin_counts(values: list[float]) -> dict[str, int]:
    bins = {"very_high": 0, "confident": 0, "low": 0, "very_low": 0}
    for value in values:
        if value >= 90.0:
            bins["very_high"] += 1
        elif value >= 70.0:
            bins["confident"] += 1
        elif value >= 50.0:
            bins["low"] += 1
        else:
            bins["very_low"] += 1
    return bins


def _draw_metric_row(draw: ImageDraw.ImageDraw, x: int, y: int, label: str, value: str, *, width: int) -> int:
    font = ImageFont.load_default()
    draw.text((x, y), label, fill=(148, 163, 184, 255), font=font)
    draw.text((x + width - 180, y), value, fill=(226, 232, 240, 255), font=font)
    draw.line([(x, y + 23), (x + width, y + 23)], fill=(51, 65, 85, 170), width=1)
    return y + 32


def _write_molecular_plate(
    target_id: str,
    chains: dict[str, list[dict[str, Any]]],
    atoms: list[dict[str, Any]],
    row: dict[str, Any],
    interface_summary: dict[str, Any],
    out_dir: str | Path,
    *,
    width: int = 3600,
    height: int = 2200,
) -> str:
    out = _resolve(out_dir) / f"{target_id}_structure_molecular_plate.png"
    canvas = Image.new("RGB", (width, height), "#07111f")
    draw = ImageDraw.Draw(canvas, "RGBA")
    _draw_gradient_background(draw, width, height, "#07111f", "#111827")
    font = ImageFont.load_default()

    margin = 54
    gap = 34
    header_h = 150
    footer_h = 94
    panel_w = (width - margin * 2 - gap * 2) // 3
    panel_h = 1030
    panel_top = header_h
    boxes = [
        (margin + index * (panel_w + gap), panel_top, margin + index * (panel_w + gap) + panel_w, panel_top + panel_h)
        for index in range(3)
    ]

    _draw_projected_trace_panel(draw, boxes[0], chains, title="Chain front view", elev=18, azim=-58, color_mode="chain")
    _draw_projected_trace_panel(draw, boxes[1], chains, title="Confidence side view", elev=58, azim=18, color_mode="confidence")
    _draw_projected_trace_panel(draw, boxes[2], chains, title="Residue-class top view", elev=84, azim=36, color_mode="residue_class")

    draw.text((margin, 40), f"{target_id} high-resolution molecular inspection plate", fill=(226, 232, 240, 255), font=font)
    draw.text(
        (margin, 68),
        "Internal predicted coordinates: orthographic CA views, confidence, residue class, interface, and QC summary.",
        fill=(148, 163, 184, 255),
        font=font,
    )
    draw.text(
        (margin, 96),
        "Use for local visual triage only; not official CASP accuracy evidence or an experimental/native structure.",
        fill=(148, 163, 184, 255),
        font=font,
    )

    metrics_top = panel_top + panel_h + 42
    metrics_bottom = height - footer_h
    metrics_box = (margin, metrics_top, width - margin, metrics_bottom)
    draw.rounded_rectangle(metrics_box, radius=24, fill=(15, 23, 42, 215), outline=(71, 85, 105, 220), width=2)

    column_w = (metrics_box[2] - metrics_box[0] - gap * 2 - 52) // 3
    col1 = metrics_box[0] + 26
    col2 = col1 + column_w + gap
    col3 = col2 + column_w + gap
    y = metrics_top + 30
    draw.text((col1, y), "Model inventory", fill=(203, 213, 225, 255), font=font)
    y += 34
    y = _draw_metric_row(draw, col1, y, "chains", str(row.get("chain_count", 0)), width=column_w)
    y = _draw_metric_row(draw, col1, y, "CA trace points", str(row.get("ca_count", 0)), width=column_w)
    y = _draw_metric_row(draw, col1, y, "atoms", str(row.get("atom_count", 0)), width=column_w)
    y = _draw_metric_row(draw, col1, y, "non-CA atoms", str(row.get("sidechain_atom_count", 0)), width=column_w)
    y = _draw_metric_row(draw, col1, y, "interface pairs", str(interface_summary.get("pair_count", 0)), width=column_w)
    _draw_metric_row(draw, col1, y, "CA contacts <=12A", str(interface_summary.get("total_ca_contacts_12a", 0)), width=column_w)

    values = [float(atom.get("b_factor", 0.0)) for atom in atoms]
    b_min = min(values) if values else 0.0
    b_max = max(values) if values else 1.0
    bins = _confidence_bin_counts(values)
    y = metrics_top + 30
    draw.text((col2, y), "Confidence distribution", fill=(203, 213, 225, 255), font=font)
    y += 34
    _confidence_legend(draw, (col2, y, col2 + column_w, y + 20), b_min, b_max)
    draw.text((col2, y + 30), f"min {b_min:.1f}", fill=(148, 163, 184, 255), font=font)
    draw.text((col2 + column_w - 84, y + 30), f"max {b_max:.1f}", fill=(148, 163, 184, 255), font=font)
    y += 72
    bin_colors = {
        "very_high": "#2563eb",
        "confident": "#059669",
        "low": "#d97706",
        "very_low": "#dc2626",
    }
    max_bin = max(1, max(bins.values()))
    for key, label in [
        ("very_high", "very high >=90"),
        ("confident", "confident 70-89"),
        ("low", "low 50-69"),
        ("very_low", "very low <50"),
    ]:
        count = bins[key]
        bar_w = int((column_w - 176) * count / max_bin)
        color = _rgb(bin_colors[key])
        draw.text((col2, y), label, fill=(148, 163, 184, 255), font=font)
        draw.rounded_rectangle((col2 + 142, y + 2, col2 + 142 + bar_w, y + 18), radius=5, fill=(*color, 230))
        draw.text((col2 + column_w - 54, y), str(count), fill=(226, 232, 240, 255), font=font)
        y += 34

    y = metrics_top + 30
    draw.text((col3, y), "QC and chemistry triage", fill=(203, 213, 225, 255), font=font)
    y += 34
    y = _draw_metric_row(
        draw,
        col3,
        y,
        "QC hotspots total/display",
        f"{row.get('pymol_qc_total_hotspot_count', row.get('pymol_qc_hotspot_count', 0))}/{row.get('pymol_qc_display_hotspot_count', 0)}",
        width=column_w,
    )
    y = _draw_metric_row(draw, col3, y, "soft-contact hotspots", str(row.get("pymol_qc_total_soft_hotspot_count", 0)), width=column_w)
    y = _draw_metric_row(draw, col3, y, "low-confidence hotspots", str(row.get("pymol_qc_total_low_confidence_hotspot_count", 0)), width=column_w)
    y = _draw_metric_row(draw, col3, y, "min interchain CA", f"{float(interface_summary.get('min_interchain_ca_distance_A') or 0.0):.2f} A", width=column_w)
    residue_counts = _residue_class_counts_from_atoms(atoms)
    y += 8
    for key in ["hydrophobic", "polar", "positive", "negative", "aromatic", "special"]:
        color = _rgb(RESIDUE_CLASS_COLORS[key])
        draw.rounded_rectangle((col3, y, col3 + 20, y + 20), radius=5, fill=(*color, 255))
        draw.text((col3 + 30, y + 3), f"{key}: {int(residue_counts.get(key, 0))}", fill=(203, 213, 225, 255), font=font)
        y += 28

    footer_y = height - footer_h + 30
    draw.text(
        (margin, footer_y),
        "Molecular plate combines local internal renders only; no external predictor, template, public native, or official CASP result is implied.",
        fill=(148, 163, 184, 255),
        font=font,
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out, quality=95)
    return _artifact(out)


def _axis_bounds(points: list[tuple[float, float, float]]) -> tuple[tuple[float, float], tuple[float, float], tuple[float, float]]:
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    zs = [p[2] for p in points]
    center = ((min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0, (min(zs) + max(zs)) / 2.0)
    span = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs), 1.0) * 0.58
    return (
        (center[0] - span, center[0] + span),
        (center[1] - span, center[1] + span),
        (center[2] - span, center[2] + span),
    )


def _render_target(
    target_id: str,
    pdb_path: str | Path,
    out_dir: str | Path,
    *,
    elev: float,
    azim: float,
    dpi: int,
    pymol_render: bool,
    pymol_qc_render: bool,
    pymol_surface_render: bool,
    pymol_confidence_render: bool,
    pymol_executable: str,
    reuse_existing_pymol: bool,
    pymol_width: int,
    pymol_height: int,
    pymol_dpi: int,
) -> dict[str, Any]:
    atoms = _parse_pdb_atoms(pdb_path)
    chains = _ca_trace_by_chain(atoms)
    ca_count = sum(len(values) for values in chains.values())
    out_root = _resolve(out_dir)
    out_root.mkdir(parents=True, exist_ok=True)
    png_path = out_root / f"{target_id}_structure.png"
    svg_path = out_root / f"{target_id}_structure.svg"

    row: dict[str, Any] = {
        "target_id": target_id,
        "prediction_file_path": _artifact(pdb_path),
        "render_status": "blocked",
        "png_path": "",
        "svg_path": "",
        "publication_png_path": "",
        "studio_png_path": "",
        "residue_class_png_path": "",
        "interface_map_png_path": "",
        "stereo_depth_png_path": "",
        "turntable_png_path": "",
        "atlas_panel_png_path": "",
        "molecular_plate_png_path": "",
        "presentation_plate_png_path": "",
        "pymol_png_path": "",
        "pymol_script_path": "",
        "pymol_render_status": "disabled",
        "pymol_blockers": "",
        "pymol_qc_png_path": "",
        "pymol_qc_script_path": "",
        "pymol_qc_render_status": "disabled",
        "pymol_qc_blockers": "",
        "pymol_surface_png_path": "",
        "pymol_surface_script_path": "",
        "pymol_surface_render_status": "disabled",
        "pymol_surface_blockers": "",
        "pymol_confidence_png_path": "",
        "pymol_confidence_script_path": "",
        "pymol_confidence_render_status": "disabled",
        "pymol_confidence_blockers": "",
        "confidence_b_factor_min": 0.0,
        "confidence_b_factor_median": 0.0,
        "confidence_b_factor_max": 0.0,
        "confidence_palette": "",
        "pymol_qc_hotspot_count": 0,
        "pymol_qc_soft_hotspot_count": 0,
        "pymol_qc_low_confidence_hotspot_count": 0,
        "pymol_qc_total_hotspot_count": 0,
        "pymol_qc_total_soft_hotspot_count": 0,
        "pymol_qc_total_low_confidence_hotspot_count": 0,
        "pymol_qc_hotspot_raw_count": 0,
        "pymol_qc_soft_hotspot_raw_count": 0,
        "pymol_qc_low_confidence_hotspot_raw_count": 0,
        "pymol_qc_display_hotspot_count": 0,
        "pymol_qc_display_soft_hotspot_count": 0,
        "pymol_qc_display_low_confidence_hotspot_count": 0,
        "pymol_qc_rendered_hotspot_count": 0,
        "pymol_qc_rendered_soft_hotspot_count": 0,
        "pymol_qc_rendered_low_confidence_hotspot_count": 0,
        "pymol_qc_display_hotspot_limit": MAX_QC_HOTSPOTS,
        "pymol_qc_hotspot_marker_cap": MAX_QC_HOTSPOTS,
        "pymol_qc_hotspot_truncated": False,
        "pymol_qc_low_confidence_cutoff": 0.0,
        "pymol_qc_confidence_span": 0.0,
        "pymol_qc_top_hotspots": [],
        "pymol_qc_hotspot_top_details": [],
        "interface_pair_count": 0,
        "interface_contacts_8a_total": 0,
        "interface_contacts_12a_total": 0,
        "interface_min_ca_distance_A": 0.0,
        "interface_contact_summary_json": "{}",
        "review_panel_png_path": "",
        "atom_count": len(atoms),
        "ca_count": ca_count,
        "sidechain_atom_count": max(0, len(atoms) - ca_count),
        "chain_count": len(chains),
        "blockers": "",
    }
    if not atoms:
        row["blockers"] = "atom_records_missing"
        return row
    if not chains:
        row["blockers"] = "ca_trace_missing"
        return row
    interface_summary = _interface_contact_summary(chains)
    row.update(
        {
            "interface_pair_count": int(interface_summary.get("pair_count") or 0),
            "interface_contacts_8a_total": int(interface_summary.get("total_ca_contacts_8a") or 0),
            "interface_contacts_12a_total": int(interface_summary.get("total_ca_contacts_12a") or 0),
            "interface_min_ca_distance_A": float(interface_summary.get("min_interchain_ca_distance_A") or 0.0),
            "interface_contact_summary_json": json.dumps(interface_summary, sort_keys=True),
        }
    )

    fig = plt.figure(figsize=(8.0, 7.0), facecolor="#f8fafc")
    ax = fig.add_subplot(111, projection="3d", facecolor="#f8fafc")
    all_points: list[tuple[float, float, float]] = []
    sorted_chains = sorted(chains)
    for index, chain_id in enumerate(sorted_chains):
        trace = chains[chain_id]
        xs = [atom["x"] for atom in trace]
        ys = [atom["y"] for atom in trace]
        zs = [atom["z"] for atom in trace]
        all_points.extend(zip(xs, ys, zs))
        color = CHAIN_COLORS[index % len(CHAIN_COLORS)]
        line_width = 1.7 if len(trace) < 800 else 1.1
        ax.plot(xs, ys, zs, color=color, linewidth=line_width, alpha=0.88, label=f"Chain {chain_id}")
        step = max(1, math.ceil(len(trace) / 160))
        ax.scatter(xs[::step], ys[::step], zs[::step], color=color, s=9, alpha=0.75, depthshade=True)
    xlim, ylim, zlim = _axis_bounds(all_points)
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_zlim(*zlim)
    ax.set_box_aspect((1, 1, 1))
    ax.view_init(elev=elev, azim=azim)
    ax.set_axis_off()
    ax.set_title(
        f"{target_id} internal physics TS model\n{len(sorted_chains)} chains, {row['ca_count']} CA trace points",
        fontsize=13,
        color="#0f172a",
        pad=8,
    )
    if len(sorted_chains) <= 8:
        ax.legend(loc="upper left", fontsize=7, frameon=False)
    fig.tight_layout(pad=0.3)
    fig.savefig(png_path, dpi=dpi, facecolor=fig.get_facecolor(), bbox_inches="tight", pad_inches=0.05)
    fig.savefig(svg_path, facecolor=fig.get_facecolor(), bbox_inches="tight", pad_inches=0.05)
    plt.close(fig)

    row.update(
        {
            "render_status": "rendered",
            "png_path": _artifact(png_path),
            "svg_path": _artifact(svg_path),
            "publication_png_path": _write_publication_render(target_id, chains, out_dir, width=1800, height=1050),
            "studio_png_path": _write_studio_render(target_id, chains, atoms, out_dir, width=2200, height=1400),
            "residue_class_png_path": _write_residue_class_render(target_id, chains, atoms, out_dir, width=2200, height=1400),
            "interface_map_png_path": _write_interface_contact_map(target_id, chains, interface_summary, out_dir, width=2200, height=1400),
            "stereo_depth_png_path": _write_stereo_depth_render(target_id, chains, out_dir),
            "turntable_png_path": _write_turntable_render(target_id, chains, out_dir),
            "blockers": "",
        }
    )
    if pymol_render:
        row.update(
            _write_pymol_render(
                target_id,
                pdb_path,
                out_dir,
                chains,
                executable=pymol_executable,
                reuse_existing=reuse_existing_pymol,
                width=pymol_width,
                height=pymol_height,
                dpi=pymol_dpi,
            )
        )
    if pymol_qc_render:
        row.update(
            _write_pymol_qc_render(
                target_id,
                pdb_path,
                out_dir,
                chains,
                atoms,
                executable=pymol_executable,
                reuse_existing=reuse_existing_pymol,
                width=pymol_width,
                height=pymol_height,
                dpi=pymol_dpi,
            )
        )
    if pymol_surface_render:
        row.update(
            _write_pymol_surface_render(
                target_id,
                pdb_path,
                out_dir,
                chains,
                executable=pymol_executable,
                reuse_existing=reuse_existing_pymol,
                width=pymol_width,
                height=pymol_height,
                dpi=pymol_dpi,
            )
        )
    if pymol_confidence_render:
        row.update(
            _write_pymol_confidence_render(
                target_id,
                pdb_path,
                out_dir,
                chains,
                atoms,
                executable=pymol_executable,
                reuse_existing=reuse_existing_pymol,
                width=pymol_width,
                height=pymol_height,
                dpi=pymol_dpi,
            )
        )
    row["review_panel_png_path"] = _write_review_panel(target_id, row, out_dir) if row.get("pymol_png_path") and row.get("pymol_qc_png_path") else ""
    row["molecular_plate_png_path"] = _write_molecular_plate(target_id, chains, atoms, row, interface_summary, out_dir)
    row["presentation_plate_png_path"] = _write_presentation_plate(target_id, chains, atoms, row, interface_summary, out_dir)
    row["atlas_panel_png_path"] = _write_atlas_panel(target_id, row, out_dir)
    return row


def _write_contact_sheet(
    path_like: str | Path,
    rows: list[dict[str, Any]],
    *,
    columns: int = 4,
    image_keys: list[str] | None = None,
) -> str:
    keys = image_keys or [
        "presentation_plate_png_path",
        "molecular_plate_png_path",
        "pymol_png_path",
        "turntable_png_path",
        "stereo_depth_png_path",
        "studio_png_path",
        "residue_class_png_path",
        "publication_png_path",
        "png_path",
    ]
    rendered = [
        row
        for row in rows
        if row.get("render_status") == "rendered"
        and any(_text(row.get(key)) for key in keys)
    ]
    if not rendered:
        return ""
    thumb_w, thumb_h = 420, 286
    label_h = 44
    columns = max(1, int(columns))
    rows_n = math.ceil(len(rendered) / columns)
    sheet = Image.new("RGB", (columns * thumb_w, rows_n * (thumb_h + label_h)), "#0b1220")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for index, row in enumerate(rendered):
        image_artifact = next(_text(row.get(key)) for key in keys if _text(row.get(key)))
        png = _resolve(image_artifact)
        cell_x = (index % columns) * thumb_w
        cell_y = (index // columns) * (thumb_h + label_h)
        with Image.open(png) as im:
            im = im.convert("RGB")
            im.thumbnail((thumb_w, thumb_h), Image.Resampling.LANCZOS)
            x = cell_x + (thumb_w - im.width) // 2
            y = cell_y + 8
            sheet.paste(im, (x, y))
        label = f"{row['target_id']} | chains={row['chain_count']} | CA={row['ca_count']} | atom={row.get('atom_count', 0)}"
        total_count = int(row.get("pymol_qc_total_hotspot_count") or row.get("pymol_qc_hotspot_count") or 0)
        if total_count > 0:
            display_count = int(row.get("pymol_qc_display_hotspot_count") or row.get("pymol_qc_hotspot_count") or 0)
            label = f"{label} | QC={total_count}/{display_count}"
        draw.text((cell_x + 12, cell_y + thumb_h + 14), label, fill="#e2e8f0", font=font)
    out = _resolve(path_like)
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    return _artifact(out)


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Structure Render Packet",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- prediction_dir: `{summary['prediction_dir']}`",
        f"- target_count: `{summary['target_count']}`",
        f"- rendered/blocked: `{summary['rendered_count']}/{summary['blocked_count']}`",
        f"- contact_sheet: `{summary['contact_sheet_path'] or '-'}`",
        f"- qc_contact_sheet: `{summary.get('qc_contact_sheet_path') or '-'}`",
        f"- surface_contact_sheet: `{summary.get('surface_contact_sheet_path') or '-'}`",
        f"- confidence_contact_sheet: `{summary.get('confidence_contact_sheet_path') or '-'}`",
        f"- residue_class_contact_sheet: `{summary.get('residue_class_contact_sheet_path') or '-'}`",
        f"- interface_contact_sheet: `{summary.get('interface_contact_sheet_path') or '-'}`",
        f"- review_contact_sheet: `{summary.get('review_contact_sheet_path') or '-'}`",
        f"- atlas_contact_sheet: `{summary.get('atlas_contact_sheet_path') or '-'}`",
        f"- molecular_plate_contact_sheet: `{summary.get('molecular_plate_contact_sheet_path') or '-'}`",
        f"- presentation_plate_contact_sheet: `{summary.get('presentation_plate_contact_sheet_path') or '-'}`",
        f"- stereo_depth_contact_sheet: `{summary.get('stereo_depth_contact_sheet_path') or '-'}`",
        f"- turntable_contact_sheet: `{summary.get('turntable_contact_sheet_path') or '-'}`",
        f"- molecular_plate_count: `{summary.get('molecular_plate_count', 0)}`",
        f"- presentation_plate_count: `{summary.get('presentation_plate_count', 0)}`",
        f"- stereo_depth_count: `{summary.get('stereo_depth_count', 0)}`",
        f"- turntable_count: `{summary.get('turntable_count', 0)}`",
        f"- predicted CA interface contacts <=12A: `{summary.get('interface_contacts_12a_total', 0)}`",
        f"- total/display QC hotspots: `{summary.get('pymol_qc_total_hotspot_count', summary.get('pymol_qc_hotspot_count', 0))}/{summary.get('pymol_qc_display_hotspot_count', 0)}`",
        f"- gallery_html: `{summary['gallery_html_path'] or '-'}`",
        "",
        "## Renders",
        "",
        "| target | status | chains | CA points | atoms | PNG | publication PNG | studio PNG | residue-class PNG | interface map | stereo depth | turntable | molecular plate | presentation plate | atlas panel | PyMOL PNG | confidence PNG | PyMOL surface PNG | PyMOL QC PNG | review panel | predicted CA interface 12A | QC total/display | SVG | blockers |",
        "| --- | --- | ---: | ---: | ---: | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | ---: | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['render_status']}` | {row['chain_count']} | {row['ca_count']} | {row.get('atom_count', 0)} | "
            f"`{row['png_path'] or '-'}` | `{row.get('publication_png_path') or '-'}` | "
            f"`{row.get('studio_png_path') or '-'}` | `{row.get('residue_class_png_path') or '-'}` | "
            f"`{row.get('interface_map_png_path') or '-'}` | `{row.get('stereo_depth_png_path') or '-'}` | "
            f"`{row.get('turntable_png_path') or '-'}` | "
            f"`{row.get('molecular_plate_png_path') or '-'}` | "
            f"`{row.get('presentation_plate_png_path') or '-'}` | "
            f"`{row.get('atlas_panel_png_path') or '-'}` | "
            f"`{row.get('pymol_png_path') or '-'}` | "
            f"`{row.get('pymol_confidence_png_path') or '-'}` | "
            f"`{row.get('pymol_surface_png_path') or '-'}` | `{row.get('pymol_qc_png_path') or '-'}` | "
            f"`{row.get('review_panel_png_path') or '-'}` | {row.get('interface_contacts_12a_total', 0)} | "
            f"{row.get('pymol_qc_total_hotspot_count', row.get('pymol_qc_hotspot_count', 0))}/{row.get('pymol_qc_display_hotspot_count', 0)} | "
            f"`{row['svg_path'] or '-'}` | {row['blockers'] or row.get('pymol_blockers') or row.get('pymol_surface_blockers') or row.get('pymol_qc_blockers') or '-'} |"
    )
    if not payload["rows"]:
        lines.append("| - | `no_targets` | 0 | 0 | 0 | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | 0 | 0 | - | - |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_html(path_like: str | Path, payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    rendered = [row for row in payload["rows"] if row.get("render_status") == "rendered"]
    html_path = _resolve(path_like)

    def href(artifact: str) -> str:
        if not artifact:
            return ""
        return os.path.relpath(_resolve(artifact), start=html_path.parent).replace(os.sep, "/")

    cards = []
    for row in rendered:
        hero_image = row.get("presentation_plate_png_path") or row.get("molecular_plate_png_path") or row.get("turntable_png_path") or row.get("stereo_depth_png_path") or row.get("atlas_panel_png_path") or row.get("interface_map_png_path") or row.get("residue_class_png_path") or row.get("pymol_surface_png_path") or row.get("pymol_png_path") or row.get("studio_png_path") or row.get("publication_png_path") or row["png_path"]
        presentation_plate_link = f" | <a href=\"{href(row.get('presentation_plate_png_path'))}\">Presentation plate</a>" if row.get("presentation_plate_png_path") else ""
        molecular_plate_link = f" | <a href=\"{href(row.get('molecular_plate_png_path'))}\">Molecular plate</a>" if row.get("molecular_plate_png_path") else ""
        stereo_link = f" | <a href=\"{href(row.get('stereo_depth_png_path'))}\">Stereo depth</a>" if row.get("stereo_depth_png_path") else ""
        turntable_link = f" | <a href=\"{href(row.get('turntable_png_path'))}\">Turntable review</a>" if row.get("turntable_png_path") else ""
        atlas_link = f" | <a href=\"{href(row.get('atlas_panel_png_path'))}\">Atlas PNG</a>" if row.get("atlas_panel_png_path") else ""
        residue_link = f" | <a href=\"{href(row.get('residue_class_png_path'))}\">Residue Class PNG</a>" if row.get("residue_class_png_path") else ""
        interface_link = f" | <a href=\"{href(row.get('interface_map_png_path'))}\">Interface Map PNG</a>" if row.get("interface_map_png_path") else ""
        pymol_link = f" | <a href=\"{href(row.get('pymol_png_path'))}\">PyMOL PNG</a>" if row.get("pymol_png_path") else ""
        pml_link = f" | <a href=\"{href(row.get('pymol_script_path'))}\">PyMOL script</a>" if row.get("pymol_script_path") else ""
        confidence_link = f" | <a href=\"{href(row.get('pymol_confidence_png_path'))}\">Confidence PNG</a>" if row.get("pymol_confidence_png_path") else ""
        confidence_pml_link = f" | <a href=\"{href(row.get('pymol_confidence_script_path'))}\">Confidence script</a>" if row.get("pymol_confidence_script_path") else ""
        surface_link = f" | <a href=\"{href(row.get('pymol_surface_png_path'))}\">PyMOL surface PNG</a>" if row.get("pymol_surface_png_path") else ""
        surface_pml_link = f" | <a href=\"{href(row.get('pymol_surface_script_path'))}\">Surface script</a>" if row.get("pymol_surface_script_path") else ""
        qc_link = f" | <a href=\"{href(row.get('pymol_qc_png_path'))}\">PyMOL QC PNG</a>" if row.get("pymol_qc_png_path") else ""
        qc_pml_link = f" | <a href=\"{href(row.get('pymol_qc_script_path'))}\">QC script</a>" if row.get("pymol_qc_script_path") else ""
        review_panel_link = f" | <a href=\"{href(row.get('review_panel_png_path'))}\">Review panel</a>" if row.get("review_panel_png_path") else ""
        qc_note = (
            f"<p>QC overlay hotspots: {row.get('pymol_qc_total_hotspot_count', row.get('pymol_qc_hotspot_count', 0))} total / "
            f"{row.get('pymol_qc_display_hotspot_count', 0)} displayed "
            f"(soft={row.get('pymol_qc_total_soft_hotspot_count', row.get('pymol_qc_soft_hotspot_count', 0))}, "
            f"low-confidence={row.get('pymol_qc_total_low_confidence_hotspot_count', row.get('pymol_qc_low_confidence_hotspot_count', 0))})</p>"
            if row.get("pymol_qc_render_status") == "rendered"
            else ""
        )
        cards.append(
            "\n".join(
                [
                    "<article>",
                    f"<img src=\"{href(hero_image)}\" alt=\"{row['target_id']} structure render\">",
                    f"<h2>{row['target_id']}</h2>",
                    f"<p>{row['chain_count']} chains | {row['ca_count']} CA trace points | {row.get('atom_count', 0)} atoms | predicted CA interface contacts <=12A {row.get('interface_contacts_12a_total', 0)}</p>",
                    qc_note,
                    f"<p><a href=\"{href(row['png_path'])}\">Trace PNG</a> | <a href=\"{href(row.get('publication_png_path'))}\">Publication PNG</a> | <a href=\"{href(row.get('studio_png_path'))}\">Studio PNG</a>{residue_link}{interface_link}{stereo_link}{turntable_link}{presentation_plate_link}{molecular_plate_link}{atlas_link}{pymol_link}{pml_link}{confidence_link}{confidence_pml_link}{surface_link}{surface_pml_link}{qc_link}{qc_pml_link}{review_panel_link} | <a href=\"{href(row['svg_path'])}\">SVG</a> | <a href=\"{href(row['prediction_file_path'])}\">TS PDB</a></p>",
                    "</article>",
                ]
            )
        )
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>CASP17 Internal Structure Render Gallery</title>
  <style>
    body {{ margin: 0; font-family: system-ui, sans-serif; background: #f8fafc; color: #0f172a; }}
    header {{ padding: 24px 28px 10px; }}
    h1 {{ margin: 0 0 6px; font-size: 24px; }}
    .meta {{ color: #475569; font-size: 14px; }}
    main {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 14px; padding: 18px 24px 28px; }}
    article {{ background: white; border: 1px solid #dbe3ef; border-radius: 8px; padding: 10px; }}
    img {{ width: 100%; display: block; background: #f8fafc; border-radius: 6px; }}
    h2 {{ margin: 8px 2px 2px; font-size: 16px; }}
    p {{ margin: 4px 2px; color: #475569; font-size: 13px; }}
    a {{ color: #2563eb; }}
  </style>
</head>
<body>
  <header>
    <h1>CASP17 Internal Structure Render Gallery</h1>
    <div class="meta">Generated {summary['generated_at_local']} | rendered {summary['rendered_count']} of {summary['target_count']} current targets</div>
    <p class="meta">{summary['claim_boundary']}</p>
  </header>
  <main>
    {''.join(cards)}
  </main>
</body>
</html>
"""
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(html, encoding="utf-8")
    return _artifact(html_path)


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    watchlist = _read_json(args.target_watchlist_json)
    target_ids = _current_open_targets(watchlist)
    if args.target_limit > 0:
        target_ids = target_ids[: args.target_limit]
    rows: list[dict[str, Any]] = []
    for target_id, pdb_path in _prediction_paths(args.prediction_dir, target_ids):
        if not pdb_path.exists():
            rows.append(
                {
                    "target_id": target_id,
                    "prediction_file_path": _artifact(pdb_path),
                    "render_status": "blocked",
                    "png_path": "",
                    "svg_path": "",
                    "publication_png_path": "",
                    "studio_png_path": "",
                    "residue_class_png_path": "",
                    "interface_map_png_path": "",
                    "stereo_depth_png_path": "",
                    "turntable_png_path": "",
                    "atlas_panel_png_path": "",
                    "molecular_plate_png_path": "",
                    "presentation_plate_png_path": "",
                    "pymol_png_path": "",
                    "pymol_script_path": "",
                    "pymol_render_status": "disabled" if not args.pymol_render else "blocked",
                    "pymol_blockers": "" if not args.pymol_render else "prediction_file_missing",
                    "pymol_qc_png_path": "",
                    "pymol_qc_script_path": "",
                    "pymol_qc_render_status": "disabled" if not args.pymol_qc_render else "blocked",
                    "pymol_qc_blockers": "" if not args.pymol_qc_render else "prediction_file_missing",
                    "pymol_surface_png_path": "",
                    "pymol_surface_script_path": "",
                    "pymol_surface_render_status": "disabled" if not args.pymol_surface_render else "blocked",
                    "pymol_surface_blockers": "" if not args.pymol_surface_render else "prediction_file_missing",
                    "pymol_confidence_png_path": "",
                    "pymol_confidence_script_path": "",
                    "pymol_confidence_render_status": "disabled" if not args.pymol_confidence_render else "blocked",
                    "pymol_confidence_blockers": "" if not args.pymol_confidence_render else "prediction_file_missing",
                    "confidence_b_factor_min": 0.0,
                    "confidence_b_factor_median": 0.0,
                    "confidence_b_factor_max": 0.0,
                    "confidence_palette": "",
                    "pymol_qc_hotspot_count": 0,
                    "pymol_qc_soft_hotspot_count": 0,
                    "pymol_qc_low_confidence_hotspot_count": 0,
                    "pymol_qc_total_hotspot_count": 0,
                    "pymol_qc_total_soft_hotspot_count": 0,
                    "pymol_qc_total_low_confidence_hotspot_count": 0,
                    "pymol_qc_hotspot_raw_count": 0,
                    "pymol_qc_soft_hotspot_raw_count": 0,
                    "pymol_qc_low_confidence_hotspot_raw_count": 0,
                    "pymol_qc_display_hotspot_count": 0,
                    "pymol_qc_display_soft_hotspot_count": 0,
                    "pymol_qc_display_low_confidence_hotspot_count": 0,
                    "pymol_qc_rendered_hotspot_count": 0,
                    "pymol_qc_rendered_soft_hotspot_count": 0,
                    "pymol_qc_rendered_low_confidence_hotspot_count": 0,
                    "pymol_qc_display_hotspot_limit": MAX_QC_HOTSPOTS,
                    "pymol_qc_hotspot_marker_cap": MAX_QC_HOTSPOTS,
                    "pymol_qc_hotspot_truncated": False,
                    "pymol_qc_low_confidence_cutoff": 0.0,
                    "pymol_qc_confidence_span": 0.0,
                    "pymol_qc_top_hotspots": [],
                    "pymol_qc_hotspot_top_details": [],
                    "interface_pair_count": 0,
                    "interface_contacts_8a_total": 0,
                    "interface_contacts_12a_total": 0,
                    "interface_min_ca_distance_A": 0.0,
                    "interface_contact_summary_json": "{}",
                    "review_panel_png_path": "",
                    "atom_count": 0,
                    "ca_count": 0,
                    "sidechain_atom_count": 0,
                    "chain_count": 0,
                    "blockers": "prediction_file_missing",
                }
            )
            continue
        rows.append(
            _render_target(
                target_id,
                pdb_path,
                args.out_dir,
                elev=args.elev,
                azim=args.azim,
                dpi=args.dpi,
                pymol_render=args.pymol_render,
                pymol_qc_render=args.pymol_qc_render,
                pymol_surface_render=args.pymol_surface_render,
                pymol_confidence_render=args.pymol_confidence_render,
                pymol_executable=args.pymol_executable,
                reuse_existing_pymol=args.reuse_existing_pymol_renders,
                pymol_width=args.pymol_width,
                pymol_height=args.pymol_height,
                pymol_dpi=args.pymol_dpi,
            )
        )

    contact_sheet = _write_contact_sheet(args.contact_sheet, rows, columns=args.contact_sheet_columns)
    qc_contact_sheet = (
        _write_contact_sheet(
            args.qc_contact_sheet,
            rows,
            columns=args.contact_sheet_columns,
            image_keys=["pymol_qc_png_path"],
        )
        if args.pymol_qc_render
        else ""
    )
    surface_contact_sheet = (
        _write_contact_sheet(
            args.surface_contact_sheet,
            rows,
            columns=args.contact_sheet_columns,
            image_keys=["pymol_surface_png_path"],
        )
        if args.pymol_surface_render
        else ""
    )
    confidence_contact_sheet = (
        _write_contact_sheet(
            args.confidence_contact_sheet,
            rows,
            columns=args.contact_sheet_columns,
            image_keys=["pymol_confidence_png_path"],
        )
        if args.pymol_confidence_render
        else ""
    )
    residue_class_contact_sheet = _write_contact_sheet(
        args.residue_class_contact_sheet,
        rows,
        columns=args.contact_sheet_columns,
        image_keys=["residue_class_png_path"],
    )
    interface_contact_sheet = _write_contact_sheet(
        args.interface_contact_sheet,
        rows,
        columns=args.contact_sheet_columns,
        image_keys=["interface_map_png_path"],
    )
    review_contact_sheet = _write_contact_sheet(
        args.review_contact_sheet,
        rows,
        columns=args.contact_sheet_columns,
        image_keys=["review_panel_png_path"],
    )
    atlas_contact_sheet = _write_contact_sheet(
        args.atlas_contact_sheet,
        rows,
        columns=args.contact_sheet_columns,
        image_keys=["atlas_panel_png_path"],
    )
    molecular_plate_contact_sheet = _write_contact_sheet(
        args.molecular_plate_contact_sheet,
        rows,
        columns=args.contact_sheet_columns,
        image_keys=["molecular_plate_png_path"],
    )
    presentation_plate_contact_sheet = _write_contact_sheet(
        args.presentation_plate_contact_sheet,
        rows,
        columns=args.contact_sheet_columns,
        image_keys=["presentation_plate_png_path"],
    )
    stereo_depth_contact_sheet = _write_contact_sheet(
        args.stereo_contact_sheet,
        rows,
        columns=args.contact_sheet_columns,
        image_keys=["stereo_depth_png_path"],
    )
    turntable_contact_sheet = _write_contact_sheet(
        args.turntable_contact_sheet,
        rows,
        columns=args.contact_sheet_columns,
        image_keys=["turntable_png_path"],
    )
    rendered_count = sum(1 for row in rows if row["render_status"] == "rendered")
    summary = {
        "packet_type": "casp17_structure_render_packet",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "target_watchlist_json": _artifact(args.target_watchlist_json),
        "prediction_dir": _artifact(args.prediction_dir),
        "out_dir": _artifact(args.out_dir),
        "target_count": len(rows),
        "rendered_count": rendered_count,
        "blocked_count": len(rows) - rendered_count,
        "pymol_render_enabled": bool(args.pymol_render),
        "pymol_rendered_count": sum(1 for row in rows if row.get("pymol_render_status") == "rendered"),
        "pymol_skipped_count": sum(1 for row in rows if row.get("pymol_render_status") == "skipped"),
        "pymol_blocked_count": sum(1 for row in rows if row.get("pymol_render_status") == "blocked"),
        "pymol_qc_render_enabled": bool(args.pymol_qc_render),
        "pymol_qc_rendered_count": sum(1 for row in rows if row.get("pymol_qc_render_status") == "rendered"),
        "pymol_qc_skipped_count": sum(1 for row in rows if row.get("pymol_qc_render_status") == "skipped"),
        "pymol_qc_blocked_count": sum(1 for row in rows if row.get("pymol_qc_render_status") == "blocked"),
        "pymol_surface_render_enabled": bool(args.pymol_surface_render),
        "pymol_surface_rendered_count": sum(1 for row in rows if row.get("pymol_surface_render_status") == "rendered"),
        "pymol_surface_skipped_count": sum(1 for row in rows if row.get("pymol_surface_render_status") == "skipped"),
        "pymol_surface_blocked_count": sum(1 for row in rows if row.get("pymol_surface_render_status") == "blocked"),
        "pymol_confidence_render_enabled": bool(args.pymol_confidence_render),
        "pymol_confidence_rendered_count": sum(1 for row in rows if row.get("pymol_confidence_render_status") == "rendered"),
        "pymol_confidence_skipped_count": sum(1 for row in rows if row.get("pymol_confidence_render_status") == "skipped"),
        "pymol_confidence_blocked_count": sum(1 for row in rows if row.get("pymol_confidence_render_status") == "blocked"),
        "pymol_qc_hotspot_count": sum(int(row.get("pymol_qc_hotspot_count") or 0) for row in rows),
        "pymol_qc_soft_hotspot_count": sum(int(row.get("pymol_qc_soft_hotspot_count") or 0) for row in rows),
        "pymol_qc_low_confidence_hotspot_count": sum(int(row.get("pymol_qc_low_confidence_hotspot_count") or 0) for row in rows),
        "pymol_qc_total_hotspot_count": sum(int(row.get("pymol_qc_total_hotspot_count") or row.get("pymol_qc_hotspot_count") or 0) for row in rows),
        "pymol_qc_total_soft_hotspot_count": sum(int(row.get("pymol_qc_total_soft_hotspot_count") or row.get("pymol_qc_soft_hotspot_count") or 0) for row in rows),
        "pymol_qc_total_low_confidence_hotspot_count": sum(
            int(row.get("pymol_qc_total_low_confidence_hotspot_count") or row.get("pymol_qc_low_confidence_hotspot_count") or 0)
            for row in rows
        ),
        "pymol_qc_hotspot_raw_count": sum(int(row.get("pymol_qc_hotspot_raw_count") or row.get("pymol_qc_total_hotspot_count") or row.get("pymol_qc_hotspot_count") or 0) for row in rows),
        "pymol_qc_soft_hotspot_raw_count": sum(
            int(row.get("pymol_qc_soft_hotspot_raw_count") or row.get("pymol_qc_total_soft_hotspot_count") or row.get("pymol_qc_soft_hotspot_count") or 0)
            for row in rows
        ),
        "pymol_qc_low_confidence_hotspot_raw_count": sum(
            int(
                row.get("pymol_qc_low_confidence_hotspot_raw_count")
                or row.get("pymol_qc_total_low_confidence_hotspot_count")
                or row.get("pymol_qc_low_confidence_hotspot_count")
                or 0
            )
            for row in rows
        ),
        "pymol_qc_display_hotspot_count": sum(int(row.get("pymol_qc_display_hotspot_count") or 0) for row in rows),
        "pymol_qc_rendered_hotspot_count": sum(int(row.get("pymol_qc_rendered_hotspot_count") or row.get("pymol_qc_display_hotspot_count") or 0) for row in rows),
        "pymol_qc_display_hotspot_limit": MAX_QC_HOTSPOTS,
        "pymol_qc_hotspot_marker_cap": MAX_QC_HOTSPOTS,
        "pymol_qc_hotspot_truncated_target_count": sum(1 for row in rows if bool(row.get("pymol_qc_hotspot_truncated"))),
        "review_panel_count": sum(1 for row in rows if row.get("review_panel_png_path")),
        "residue_class_panel_count": sum(1 for row in rows if row.get("residue_class_png_path")),
        "interface_map_panel_count": sum(1 for row in rows if row.get("interface_map_png_path")),
        "interface_pair_count": sum(int(row.get("interface_pair_count") or 0) for row in rows),
        "interface_contacts_8a_total": sum(int(row.get("interface_contacts_8a_total") or 0) for row in rows),
        "interface_contacts_12a_total": sum(int(row.get("interface_contacts_12a_total") or 0) for row in rows),
        "contact_sheet_path": contact_sheet,
        "qc_contact_sheet_path": qc_contact_sheet,
        "surface_contact_sheet_path": surface_contact_sheet,
        "confidence_contact_sheet_path": confidence_contact_sheet,
        "residue_class_contact_sheet_path": residue_class_contact_sheet,
        "interface_contact_sheet_path": interface_contact_sheet,
        "review_contact_sheet_path": review_contact_sheet,
        "atlas_contact_sheet_path": atlas_contact_sheet,
        "molecular_plate_contact_sheet_path": molecular_plate_contact_sheet,
        "presentation_plate_contact_sheet_path": presentation_plate_contact_sheet,
        "stereo_depth_contact_sheet_path": stereo_depth_contact_sheet,
        "turntable_contact_sheet_path": turntable_contact_sheet,
        "gallery_html_path": "",
        "claim_boundary": "Visualization of internal CASP17 predicted coordinates only, including predicted CA interface contacts; not official CASP accuracy evidence or experimental structure.",
        "atlas_panel_count": sum(1 for row in rows if row.get("atlas_panel_png_path")),
        "molecular_plate_count": sum(1 for row in rows if row.get("molecular_plate_png_path")),
        "presentation_plate_count": sum(1 for row in rows if row.get("presentation_plate_png_path")),
        "stereo_depth_count": sum(1 for row in rows if row.get("stereo_depth_png_path")),
        "turntable_count": sum(1 for row in rows if row.get("turntable_png_path")),
    }
    payload = {"summary": summary, "rows": rows}
    summary["gallery_html_path"] = _write_html(args.out_html, payload)
    return payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render CASP17 internal TS predictions as local 3D structure images.")
    parser.add_argument("--target-watchlist-json", default=DEFAULT_WATCHLIST_JSON)
    parser.add_argument("--prediction-dir", default=DEFAULT_PREDICTION_DIR)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--target-limit", type=int, default=0)
    parser.add_argument("--elev", type=float, default=20.0)
    parser.add_argument("--azim", type=float, default=-58.0)
    parser.add_argument("--dpi", type=int, default=180)
    parser.add_argument("--contact-sheet", default=DEFAULT_CONTACT_SHEET)
    parser.add_argument("--qc-contact-sheet", default=DEFAULT_QC_CONTACT_SHEET)
    parser.add_argument("--surface-contact-sheet", default=DEFAULT_SURFACE_CONTACT_SHEET)
    parser.add_argument("--confidence-contact-sheet", default=DEFAULT_CONFIDENCE_CONTACT_SHEET)
    parser.add_argument("--residue-class-contact-sheet", default=DEFAULT_RESIDUE_CLASS_CONTACT_SHEET)
    parser.add_argument("--interface-contact-sheet", default=DEFAULT_INTERFACE_CONTACT_SHEET)
    parser.add_argument("--review-contact-sheet", default=DEFAULT_REVIEW_CONTACT_SHEET)
    parser.add_argument("--atlas-contact-sheet", default=DEFAULT_ATLAS_CONTACT_SHEET)
    parser.add_argument("--molecular-plate-contact-sheet", default=DEFAULT_MOLECULAR_PLATE_CONTACT_SHEET)
    parser.add_argument("--presentation-plate-contact-sheet", default=DEFAULT_PRESENTATION_PLATE_CONTACT_SHEET)
    parser.add_argument("--stereo-contact-sheet", default=DEFAULT_STEREO_CONTACT_SHEET)
    parser.add_argument("--turntable-contact-sheet", default=DEFAULT_TURNTABLE_CONTACT_SHEET)
    parser.add_argument("--contact-sheet-columns", type=int, default=4)
    parser.add_argument("--pymol-render", action="store_true", help="Also render PyMOL ray-traced PNGs when PyMOL is available.")
    parser.add_argument("--require-pymol-render", action="store_true", help="Exit nonzero if PyMOL rendering is requested but incomplete.")
    parser.add_argument("--pymol-qc-render", action="store_true", help="Also render PyMOL QC overlays for soft close-contact and low-confidence hotspots.")
    parser.add_argument("--require-pymol-qc-render", action="store_true", help="Exit nonzero if PyMOL QC rendering is requested but incomplete.")
    parser.add_argument("--pymol-surface-render", action="store_true", help="Also render PyMOL transparent molecular-surface inspection PNGs.")
    parser.add_argument("--require-pymol-surface-render", action="store_true", help="Exit nonzero if PyMOL surface rendering is requested but incomplete.")
    parser.add_argument("--pymol-confidence-render", action="store_true", help="Also render PyMOL B-factor confidence-colored inspection PNGs.")
    parser.add_argument("--require-pymol-confidence-render", action="store_true", help="Exit nonzero if PyMOL confidence rendering is requested but incomplete.")
    parser.add_argument("--pymol-executable", default=DEFAULT_PYMOL_EXECUTABLE)
    parser.add_argument("--reuse-existing-pymol-renders", action="store_true", help="Reuse existing nonempty PyMOL PNGs instead of ray-tracing them again.")
    parser.add_argument("--pymol-width", type=int, default=1800)
    parser.add_argument("--pymol-height", type=int, default=1200)
    parser.add_argument("--pymol-dpi", type=int, default=240)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--out-html", default=DEFAULT_OUT_HTML)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)
    if payload["summary"]["blocked_count"]:
        raise SystemExit(2)
    if args.require_pymol_render and payload["summary"]["pymol_rendered_count"] != payload["summary"]["rendered_count"]:
        raise SystemExit(2)
    if args.require_pymol_qc_render and payload["summary"]["pymol_qc_rendered_count"] != payload["summary"]["rendered_count"]:
        raise SystemExit(2)
    if args.require_pymol_surface_render and payload["summary"]["pymol_surface_rendered_count"] != payload["summary"]["rendered_count"]:
        raise SystemExit(2)
    if args.require_pymol_confidence_render and payload["summary"]["pymol_confidence_rendered_count"] != payload["summary"]["rendered_count"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
