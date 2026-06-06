#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_WATCHLIST_JSON = "runs/casp17_target_watchlist_current.json"
DEFAULT_PREDICTION_DIR = "runs/casp17_predictions_recursive_current"
DEFAULT_OUT_JSON = "runs/casp17_molecular_viewer_packet_current.json"
DEFAULT_OUT_CSV = "runs/casp17_molecular_viewer_packet_current.csv"
DEFAULT_OUT_MD = "runs/casp17_molecular_viewer_packet_current.md"
DEFAULT_OUT_HTML = "runs/casp17_molecular_viewer_current.html"
DEFAULT_RENDER_DIR = "runs/casp17_structure_renders_current"
DEFAULT_RENDER_JSON = "runs/casp17_structure_render_packet_current.json"
DEFAULT_REVIEW_QUEUE_JSON = "runs/casp17_structure_render_review_queue_current.json"
DEFAULT_ALL_ATOM_QUALITY_JSON = "runs/casp17_all_atom_quality_packet_current.json"
DEFAULT_SIDECHAIN_QUALITY_JSON = "runs/casp17_sidechain_quality_packet_current.json"

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
    "#ea580c",
    "#0284c7",
]

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


def _prediction_paths(prediction_dir: str | Path, target_ids: list[str]) -> list[tuple[str, Path]]:
    root = _resolve(prediction_dir)
    if target_ids:
        return [(target_id, root / f"{target_id}TS.pdb") for target_id in target_ids]
    return [(path.stem.replace("TS", "").upper(), path) for path in sorted(root.glob("*TS.pdb"))]


def _record(line: str) -> str:
    return line[:6].strip().upper()


def _sanitize_pdb_text(text: str, *, redact_author: bool) -> str:
    lines: list[str] = []
    for line in text.splitlines():
        if redact_author and _record(line) == "AUTHOR":
            lines.append("AUTHOR REDACTED_FOR_LOCAL_VIEWER")
        else:
            lines.append(line.rstrip("\n"))
    return "\n".join(lines) + "\n"


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
            resname = line[17:20].strip()
            chain_id = line[21].strip() or "_"
            resseq = int(line[22:26])
            insertion = line[26].strip()
            x = float(line[30:38])
            y = float(line[38:46])
            z = float(line[46:54])
            b_factor = float(line[60:66]) if len(line) >= 66 else 0.0
        except (ValueError, IndexError):
            continue
        atoms.append(
            {
                "atom_name": atom_name,
                "resname": resname,
                "chain_id": chain_id,
                "resseq": resseq,
                "insertion": insertion,
                "x": x,
                "y": y,
                "z": z,
                "b_factor": b_factor,
            }
        )
    return atoms


def _chain_stats(atoms: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_chain: dict[str, dict[str, Any]] = {}
    for atom in atoms:
        chain = atom["chain_id"]
        item = by_chain.setdefault(
            chain,
            {
                "chain_id": chain,
                "atom_count": 0,
                "ca_count": 0,
                "residues": set(),
                "x": [],
                "y": [],
                "z": [],
            },
        )
        item["atom_count"] += 1
        item["x"].append(atom["x"])
        item["y"].append(atom["y"])
        item["z"].append(atom["z"])
        item["residues"].add((atom["resseq"], atom["insertion"], atom["resname"]))
        if atom["atom_name"] == "CA":
            item["ca_count"] += 1

    rows: list[dict[str, Any]] = []
    for index, chain in enumerate(sorted(by_chain)):
        item = by_chain[chain]
        center = {
            "x": round(sum(item["x"]) / len(item["x"]), 3) if item["x"] else 0.0,
            "y": round(sum(item["y"]) / len(item["y"]), 3) if item["y"] else 0.0,
            "z": round(sum(item["z"]) / len(item["z"]), 3) if item["z"] else 0.0,
        }
        rows.append(
            {
                "chain_id": chain,
                "atom_count": item["atom_count"],
                "residue_count": len(item["residues"]),
                "ca_count": item["ca_count"],
                "color": CHAIN_COLORS[index % len(CHAIN_COLORS)],
                "center": center,
            }
        )
    return rows


def _span(atoms: list[dict[str, Any]]) -> dict[str, float]:
    if not atoms:
        return {"x": 0.0, "y": 0.0, "z": 0.0, "max": 0.0}
    xs = [atom["x"] for atom in atoms]
    ys = [atom["y"] for atom in atoms]
    zs = [atom["z"] for atom in atoms]
    spans = {"x": max(xs) - min(xs), "y": max(ys) - min(ys), "z": max(zs) - min(zs)}
    spans["max"] = max(spans.values())
    return {key: round(value, 3) for key, value in spans.items()}


def _b_factor_stats(atoms: list[dict[str, Any]]) -> dict[str, float]:
    values = [atom["b_factor"] for atom in atoms]
    if not values:
        return {"min": 0.0, "max": 0.0, "mean": 0.0}
    return {
        "min": round(min(values), 3),
        "max": round(max(values), 3),
        "mean": round(sum(values) / len(values), 3),
    }


def _residue_key(atom: dict[str, Any]) -> tuple[str, int, str, str]:
    return (atom["chain_id"], atom["resseq"], atom["insertion"], atom["resname"])


def _residue_class(resname: str) -> str:
    return RESIDUE_CLASS_BY_RESNAME.get(str(resname).upper(), "unknown")


def _residue_class_counts(atoms: list[dict[str, Any]]) -> dict[str, int]:
    residues = {_residue_key(atom) for atom in atoms}
    counts = {key: 0 for key in RESIDUE_CLASS_COLORS}
    for _chain, _resseq, _insertion, resname in residues:
        counts[_residue_class(resname)] += 1
    return counts


def _residue_table(atoms: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_residue: dict[tuple[str, int, str, str], list[dict[str, Any]]] = {}
    for atom in atoms:
        by_residue.setdefault(_residue_key(atom), []).append(atom)
    rows: list[dict[str, Any]] = []
    for chain_id, resseq, insertion, resname in sorted(by_residue, key=lambda key: (key[0], key[1], key[2], key[3])):
        residue_atoms = by_residue[(chain_id, resseq, insertion, resname)]
        confidences = [float(atom["b_factor"]) for atom in residue_atoms]
        ca_atoms = [atom for atom in residue_atoms if atom["atom_name"] == "CA"]
        confidence_mean = sum(confidences) / len(confidences) if confidences else 0.0
        center_atoms = ca_atoms or residue_atoms
        center = {
            "x": round(sum(atom["x"] for atom in center_atoms) / len(center_atoms), 3),
            "y": round(sum(atom["y"] for atom in center_atoms) / len(center_atoms), 3),
            "z": round(sum(atom["z"] for atom in center_atoms) / len(center_atoms), 3),
        }
        rows.append(
            {
                "chain_id": chain_id,
                "resseq": resseq,
                "insertion": insertion,
                "resname": resname,
                "residue_class": _residue_class(resname),
                "atom_count": len(residue_atoms),
                "has_ca": bool(ca_atoms),
                "confidence_mean": round(confidence_mean, 3),
                "low_confidence": confidence_mean < 50.0,
                "center": center,
            }
        )
    return rows


def _confidence_bins(residues: list[dict[str, Any]]) -> dict[str, int]:
    bins = {"very_high": 0, "confident": 0, "low": 0, "very_low": 0}
    for residue in residues:
        value = float(residue.get("confidence_mean") or 0.0)
        if value >= 90.0:
            bins["very_high"] += 1
        elif value >= 70.0:
            bins["confident"] += 1
        elif value >= 50.0:
            bins["low"] += 1
        else:
            bins["very_low"] += 1
    return bins


def _interface_summary(atoms: list[dict[str, Any]]) -> dict[str, Any]:
    ca_atoms = [atom for atom in atoms if atom["atom_name"] == "CA"]
    by_chain: dict[str, list[dict[str, Any]]] = {}
    for atom in ca_atoms:
        by_chain.setdefault(atom["chain_id"], []).append(atom)
    chain_ids = sorted(by_chain)
    pairs: list[dict[str, Any]] = []
    min_distance: float | None = None
    contact_12a_total = 0
    for left_index, left_chain in enumerate(chain_ids):
        for right_chain in chain_ids[left_index + 1 :]:
            distances: list[float] = []
            contact_8a = 0
            contact_12a = 0
            for left in by_chain[left_chain]:
                for right in by_chain[right_chain]:
                    distance = _distance(left, right)
                    distances.append(distance)
                    if distance <= 8.0:
                        contact_8a += 1
                    if distance <= 12.0:
                        contact_12a += 1
            if not distances:
                continue
            pair_min = min(distances)
            min_distance = pair_min if min_distance is None else min(min_distance, pair_min)
            contact_12a_total += contact_12a
            pairs.append(
                {
                    "chain_pair": f"{left_chain}:{right_chain}",
                    "min_ca_distance": round(pair_min, 3),
                    "ca_contacts_8a": contact_8a,
                    "ca_contacts_12a": contact_12a,
                }
            )
    return {
        "pair_count": len(pairs),
        "min_interchain_ca_distance": round(min_distance, 3) if min_distance is not None else 0.0,
        "ca_contacts_12a_total": contact_12a_total,
        "pairs": pairs,
    }


def _distance(a: dict[str, Any], b: dict[str, Any]) -> float:
    return math.sqrt((a["x"] - b["x"]) ** 2 + (a["y"] - b["y"]) ** 2 + (a["z"] - b["z"]) ** 2)


def _ca_geometry_scan(
    atoms: list[dict[str, Any]],
    *,
    min_continuity: float = 2.0,
    max_continuity: float = 8.0,
    clash_threshold: float = 2.0,
    marker_limit: int = 160,
) -> dict[str, Any]:
    ca_atoms = [atom for atom in atoms if atom["atom_name"] == "CA"]
    by_chain: dict[str, list[dict[str, Any]]] = {}
    for atom in ca_atoms:
        by_chain.setdefault(atom["chain_id"], []).append(atom)
    for chain_atoms in by_chain.values():
        chain_atoms.sort(key=lambda atom: (atom["resseq"], atom["insertion"]))

    markers: list[dict[str, Any]] = []
    continuity_distances: list[float] = []
    gap_count = 0
    for chain_id, chain_atoms in sorted(by_chain.items()):
        for previous, current in zip(chain_atoms, chain_atoms[1:]):
            distance = _distance(previous, current)
            continuity_distances.append(distance)
            if min_continuity <= distance <= max_continuity:
                continue
            gap_count += 1
            if len(markers) < marker_limit:
                markers.append(
                    {
                        "kind": "ca_continuity",
                        "chain_id": chain_id,
                        "label": f"CA gap {chain_id}:{previous['resseq']}-{current['resseq']} {distance:.2f}A",
                        "distance": round(distance, 3),
                        "center": {
                            "x": round((previous["x"] + current["x"]) / 2.0, 3),
                            "y": round((previous["y"] + current["y"]) / 2.0, 3),
                            "z": round((previous["z"] + current["z"]) / 2.0, 3),
                        },
                    }
                )

    clash_count = 0
    for i, left in enumerate(ca_atoms):
        for right in ca_atoms[i + 1 :]:
            if left["chain_id"] == right["chain_id"] and abs(left["resseq"] - right["resseq"]) <= 1:
                continue
            distance = _distance(left, right)
            if distance >= clash_threshold:
                continue
            clash_count += 1
            if len(markers) < marker_limit:
                markers.append(
                    {
                        "kind": "ca_clash",
                        "chain_id": f"{left['chain_id']},{right['chain_id']}",
                        "label": f"CA clash {left['chain_id']}:{left['resseq']} {right['chain_id']}:{right['resseq']} {distance:.2f}A",
                        "distance": round(distance, 3),
                        "center": {
                            "x": round((left["x"] + right["x"]) / 2.0, 3),
                            "y": round((left["y"] + right["y"]) / 2.0, 3),
                            "z": round((left["z"] + right["z"]) / 2.0, 3),
                        },
                    }
                )

    if continuity_distances:
        continuity = {
            "min": round(min(continuity_distances), 3),
            "max": round(max(continuity_distances), 3),
            "mean": round(sum(continuity_distances) / len(continuity_distances), 3),
        }
    else:
        continuity = {"min": 0.0, "max": 0.0, "mean": 0.0}
    return {
        "ca_gap_count": gap_count,
        "ca_clash_count": clash_count,
        "ca_continuity": continuity,
        "issue_markers": markers,
        "issue_marker_count": len(markers),
    }


def _fallback_preview_path(target_id: str, render_dir: str | Path) -> str:
    root = _resolve(render_dir)
    for suffix in (
        "_structure_presentation_plate.png",
        "_structure_molecular_plate.png",
        "_structure_pymol.png",
        "_structure_surface_pymol.png",
        "_structure_studio.png",
        "_structure.png",
    ):
        candidate = root / f"{target_id}{suffix}"
        if candidate.exists():
            return _artifact(candidate)
    return ""


def _rows_by_target(packet: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = packet.get("rows")
    if not isinstance(rows, list):
        return {}
    mapped: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        target_id = _text(row.get("target_id")).upper()
        if target_id:
            mapped[target_id] = row
    return mapped


def _truthy_flag(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "pass", "y"}


def _overlay_int(row: dict[str, Any], *keys: str) -> int:
    for key in keys:
        value = row.get(key)
        if value in (None, ""):
            continue
        try:
            return int(float(value))
        except (TypeError, ValueError):
            continue
    return 0


def _overlay_float(row: dict[str, Any], *keys: str) -> float:
    for key in keys:
        value = row.get(key)
        if value in (None, ""):
            continue
        try:
            return round(float(value), 3)
        except (TypeError, ValueError):
            continue
    return 0.0


def _overlay_path(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = _text(row.get(key))
        if value:
            return value
    return ""


def _qc_overlay_for_target(
    target_id: str,
    *,
    render_rows: dict[str, dict[str, Any]],
    review_rows: dict[str, dict[str, Any]],
    all_atom_rows: dict[str, dict[str, Any]],
    sidechain_rows: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    render = render_rows.get(target_id, {})
    review = review_rows.get(target_id, {})
    all_atom = all_atom_rows.get(target_id, {})
    sidechain = sidechain_rows.get(target_id, {})
    return {
        "raw_qc_hotspot_count": _overlay_int(review, "qc_hotspots_raw", "qc_hotspots")
        or _overlay_int(render, "pymol_qc_hotspot_raw_count", "pymol_qc_hotspot_count"),
        "rendered_qc_hotspot_count": _overlay_int(review, "qc_rendered_hotspots", "qc_hotspots")
        or _overlay_int(render, "pymol_qc_rendered_hotspot_count", "pymol_qc_display_hotspot_count"),
        "raw_low_confidence_hotspot_count": _overlay_int(review, "low_confidence_hotspots_raw", "low_confidence_hotspots")
        or _overlay_int(render, "pymol_qc_low_confidence_hotspot_raw_count", "pymol_qc_low_confidence_hotspot_count"),
        "rendered_low_confidence_hotspot_count": _overlay_int(
            review,
            "low_confidence_rendered_hotspots",
            "low_confidence_hotspots",
        )
        or _overlay_int(render, "pymol_qc_rendered_low_confidence_hotspot_count", "pymol_qc_display_low_confidence_hotspot_count"),
        "raw_soft_hotspot_count": _overlay_int(review, "soft_hotspots_raw", "soft_hotspots")
        or _overlay_int(render, "pymol_qc_soft_hotspot_raw_count", "pymol_qc_soft_hotspot_count"),
        "rendered_soft_hotspot_count": _overlay_int(review, "soft_rendered_hotspots", "soft_hotspots")
        or _overlay_int(render, "pymol_qc_rendered_soft_hotspot_count", "pymol_qc_display_soft_hotspot_count"),
        "qc_hotspot_truncated": _truthy_flag(review.get("qc_hotspot_truncated") or render.get("pymol_qc_hotspot_truncated")),
        "review_rank": _overlay_int(review, "review_rank"),
        "review_priority_score": _overlay_float(review, "review_priority_score"),
        "atlas_panel_png_path": _overlay_path(review, "atlas_panel_png_path") or _overlay_path(render, "atlas_panel_png_path"),
        "all_atom_severe_clash_count": _overlay_int(all_atom, "severe_clash_count"),
        "all_atom_soft_clash_count": _overlay_int(all_atom, "soft_clash_count"),
        "heavy_atom_completion_fraction": _overlay_float(all_atom, "heavy_atom_completion_fraction"),
        "sidechain_complete_fraction": _overlay_float(sidechain, "complete_sidechain_residue_fraction"),
        "rotamer_proxy_pass_fraction": _overlay_float(sidechain, "rotamer_proxy_pass_fraction"),
    }


def _build_target_row(
    target_id: str,
    pdb_path: Path,
    *,
    render_dir: str | Path,
    qc_overlay: dict[str, Any] | None = None,
) -> dict[str, Any]:
    qc_overlay = qc_overlay or {}
    row: dict[str, Any] = {
        "target_id": target_id,
        "prediction_file_path": _artifact(pdb_path),
        "viewer_status": "blocked",
        "atom_count": 0,
        "residue_count": 0,
        "ca_count": 0,
        "chain_count": 0,
        "chain_ids": "",
        "b_factor_min": 0.0,
        "b_factor_max": 0.0,
        "b_factor_mean": 0.0,
        "coordinate_span_max": 0.0,
        "ca_gap_count": 0,
        "ca_clash_count": 0,
        "issue_marker_count": 0,
        "residue_class_counts_json": "{}",
        "confidence_bins_json": "{}",
        "low_confidence_residue_count": 0,
        "very_low_confidence_residue_count": 0,
        "interface_pair_count": 0,
        "interface_contact_12a_total": 0,
        "min_interchain_ca_distance": 0.0,
        "raw_qc_hotspot_count": int(qc_overlay.get("raw_qc_hotspot_count") or 0),
        "rendered_qc_hotspot_count": int(qc_overlay.get("rendered_qc_hotspot_count") or 0),
        "raw_low_confidence_hotspot_count": int(qc_overlay.get("raw_low_confidence_hotspot_count") or 0),
        "rendered_low_confidence_hotspot_count": int(qc_overlay.get("rendered_low_confidence_hotspot_count") or 0),
        "raw_soft_hotspot_count": int(qc_overlay.get("raw_soft_hotspot_count") or 0),
        "rendered_soft_hotspot_count": int(qc_overlay.get("rendered_soft_hotspot_count") or 0),
        "qc_hotspot_truncated": bool(qc_overlay.get("qc_hotspot_truncated")),
        "review_rank": int(qc_overlay.get("review_rank") or 0),
        "review_priority_score": float(qc_overlay.get("review_priority_score") or 0.0),
        "all_atom_severe_clash_count": int(qc_overlay.get("all_atom_severe_clash_count") or 0),
        "all_atom_soft_clash_count": int(qc_overlay.get("all_atom_soft_clash_count") or 0),
        "heavy_atom_completion_fraction": float(qc_overlay.get("heavy_atom_completion_fraction") or 0.0),
        "sidechain_complete_fraction": float(qc_overlay.get("sidechain_complete_fraction") or 0.0),
        "rotamer_proxy_pass_fraction": float(qc_overlay.get("rotamer_proxy_pass_fraction") or 0.0),
        "atlas_panel_png_path": _text(qc_overlay.get("atlas_panel_png_path")),
        "fallback_preview_png_path": _fallback_preview_path(target_id, render_dir),
        "blockers": "",
    }
    if not pdb_path.exists():
        row["blockers"] = "prediction_file_missing"
        return row
    atoms = _parse_pdb_atoms(pdb_path)
    if not atoms:
        row["blockers"] = "atom_records_missing"
        return row
    chains = _chain_stats(atoms)
    if not chains:
        row["blockers"] = "chain_records_missing"
        return row
    residues = {(atom["chain_id"], atom["resseq"], atom["insertion"], atom["resname"]) for atom in atoms}
    b_stats = _b_factor_stats(atoms)
    span = _span(atoms)
    geometry = _ca_geometry_scan(atoms)
    residue_class_counts = _residue_class_counts(atoms)
    residues = _residue_table(atoms)
    confidence_bins = _confidence_bins(residues)
    interface = _interface_summary(atoms)
    row.update(
        {
            "viewer_status": "ready",
            "atom_count": len(atoms),
            "residue_count": len(residues),
            "ca_count": sum(1 for atom in atoms if atom["atom_name"] == "CA"),
            "chain_count": len(chains),
            "chain_ids": ",".join(chain["chain_id"] for chain in chains),
            "b_factor_min": b_stats["min"],
            "b_factor_max": b_stats["max"],
            "b_factor_mean": b_stats["mean"],
            "coordinate_span_max": span["max"],
            "ca_gap_count": geometry["ca_gap_count"],
            "ca_clash_count": geometry["ca_clash_count"],
            "issue_marker_count": geometry["issue_marker_count"],
            "residue_class_counts_json": json.dumps(residue_class_counts, sort_keys=True),
            "confidence_bins_json": json.dumps(confidence_bins, sort_keys=True),
            "low_confidence_residue_count": confidence_bins["low"] + confidence_bins["very_low"],
            "very_low_confidence_residue_count": confidence_bins["very_low"],
            "interface_pair_count": interface["pair_count"],
            "interface_contact_12a_total": interface["ca_contacts_12a_total"],
            "min_interchain_ca_distance": interface["min_interchain_ca_distance"],
            "blockers": "",
            "_chains": chains,
            "_coordinate_span": span,
            "_geometry": geometry,
            "_residue_class_counts": residue_class_counts,
            "_residues": residues,
            "_confidence_bins": confidence_bins,
            "_interface": interface,
            "_qc_overlay": qc_overlay,
        }
    )
    return row


def _viewer_items(rows: list[dict[str, Any]], *, redact_author: bool) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for row in rows:
        if row.get("viewer_status") != "ready":
            continue
        pdb_path = _resolve(row["prediction_file_path"])
        pdb_text = _sanitize_pdb_text(pdb_path.read_text(encoding="utf-8", errors="replace"), redact_author=redact_author)
        items.append(
            {
                "target_id": row["target_id"],
                "prediction_file_path": row["prediction_file_path"],
                "atom_count": row["atom_count"],
                "residue_count": row["residue_count"],
                "ca_count": row["ca_count"],
                "chain_count": row["chain_count"],
                "chain_ids": row["chain_ids"].split(",") if row["chain_ids"] else [],
                "chains": row.get("_chains", []),
                "b_factor": {
                    "min": row["b_factor_min"],
                    "max": row["b_factor_max"],
                    "mean": row["b_factor_mean"],
                },
                "coordinate_span": row.get("_coordinate_span", {}),
                "geometry": row.get("_geometry", {}),
                "residue_class_counts": row.get("_residue_class_counts", {}),
                "residues": row.get("_residues", []),
                "confidence_bins": row.get("_confidence_bins", {}),
                "interface": row.get("_interface", {}),
                "qc_overlay": row.get("_qc_overlay", {}),
                "fallback_preview_png_path": row.get("fallback_preview_png_path", ""),
                "atlas_panel_png_path": row.get("atlas_panel_png_path", ""),
                "pdb_text": pdb_text,
            }
        )
    return items


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Molecular Viewer Packet",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- prediction_dir: `{summary['prediction_dir']}`",
        f"- target_count: `{summary['target_count']}`",
        f"- viewer ready/blocked: `{summary['ready_count']}/{summary['blocked_count']}`",
        f"- viewer_html: `{summary['viewer_html_path'] or '-'}`",
        f"- embedded_viewer: `{summary['embedded_viewer']}`",
        f"- fallback_preview_dir: `{summary['fallback_preview_dir']}`",
        f"- molstar_deeplink: `{summary['molstar_deeplink']}`",
        f"- external_network_default: `{summary['external_network_default']}`",
        f"- webgl_runtime: `{summary['webgl_runtime']}`",
        f"- internal_canvas_runtime_enabled: `{summary['internal_canvas_runtime_enabled']}`",
        f"- static_preview_fallback_enabled: `{summary['static_preview_fallback_enabled']}`",
        f"- author_redacted_in_embedded_pdb: `{summary['author_redacted_in_embedded_pdb']}`",
        f"- residue_class_coloring: `{summary['residue_class_coloring']}`",
        f"- confidence_coloring: `{summary['confidence_coloring']}`",
        f"- qc_overlay_source: `{summary['qc_overlay_source']}`",
        "",
        "## Targets",
        "",
        "| target | status | chains | residues | atoms | CA | gaps | CA clashes | raw QC | raw low-conf | soft clashes | confidence bins | residue classes | interface 12A | span max | fallback preview | PDB | blockers |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | ---: | ---: | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['viewer_status']}` | {row['chain_count']} | {row['residue_count']} | "
            f"{row['atom_count']} | {row['ca_count']} | {row['ca_gap_count']} | {row['ca_clash_count']} | "
            f"{row.get('raw_qc_hotspot_count', 0)} | {row.get('raw_low_confidence_hotspot_count', 0)} | "
            f"{row.get('all_atom_soft_clash_count', 0)} | `{row.get('confidence_bins_json', '{}')}` | "
            f"`{row.get('residue_class_counts_json', '{}')}` | {row.get('interface_contact_12a_total', 0)} | {row['coordinate_span_max']} | "
            f"`{row.get('fallback_preview_png_path', '') or '-'}` | "
            f"`{row['prediction_file_path']}` | {row['blockers'] or '-'} |"
        )
    if not payload["rows"]:
        lines.append("| - | `no_targets` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | - | - |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _json_for_script(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True).replace("</", "<\\/")


def _local_viewer_script(path_like: str | Path | None) -> tuple[str, str]:
    if not path_like:
        return "", ""
    path = _resolve(path_like)
    if not path.exists() or not path.is_file():
        return "", ""
    text = path.read_text(encoding="utf-8", errors="replace")
    return f"<script>\n{text}\n</script>", _artifact(path)


def _write_html(
    path_like: str | Path,
    payload: dict[str, Any],
    *,
    viewer_items: list[dict[str, Any]],
    viewer_js_path: str | Path | None,
) -> tuple[str, str]:
    html_path = _resolve(path_like)
    viewer_script, viewer_runtime_path = _local_viewer_script(viewer_js_path)
    data = {
        "summary": payload["summary"],
        "targets": viewer_items,
        "chain_colors": CHAIN_COLORS,
        "residue_class_colors": RESIDUE_CLASS_COLORS,
        "residue_class_by_resname": RESIDUE_CLASS_BY_RESNAME,
    }
    data_json = _json_for_script(data)
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>CASP17 Internal Molecular Viewer</title>
  {viewer_script}
  <style>
    :root {{
      color-scheme: light;
      --bg: #eef2f7;
      --panel: #ffffff;
      --ink: #111827;
      --muted: #64748b;
      --line: #cbd5e1;
      --blue: #2563eb;
      --green: #059669;
      --red: #dc2626;
      --amber: #d97706;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      background: var(--bg);
      color: var(--ink);
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    header {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding: 18px 22px;
      border-bottom: 1px solid var(--line);
      background: #f8fafc;
    }}
    h1 {{
      margin: 0;
      font-size: 20px;
      font-weight: 720;
      letter-spacing: 0;
    }}
    .status {{
      color: var(--muted);
      font-size: 13px;
      white-space: nowrap;
    }}
    main {{
      display: grid;
      grid-template-columns: minmax(280px, 340px) minmax(0, 1fr);
      min-height: calc(100vh - 61px);
    }}
    aside {{
      border-right: 1px solid var(--line);
      background: var(--panel);
      padding: 14px;
      overflow: auto;
    }}
    .viewer-shell {{
      min-height: calc(100vh - 61px);
      display: grid;
      grid-template-rows: auto minmax(420px, 1fr) auto;
    }}
    .toolbar {{
      display: flex;
      align-items: center;
      flex-wrap: wrap;
      gap: 8px;
      padding: 12px 14px;
      border-bottom: 1px solid var(--line);
      background: #ffffff;
    }}
    .toolbar button, .toolbar a, select {{
      height: 34px;
      border: 1px solid var(--line);
      background: #ffffff;
      color: var(--ink);
      border-radius: 6px;
      padding: 0 10px;
      font: inherit;
      font-size: 13px;
      text-decoration: none;
    }}
    .toolbar button.active {{
      border-color: var(--blue);
      background: #eff6ff;
      color: #1d4ed8;
    }}
    .toolbar a.disabled {{
      pointer-events: none;
      color: #94a3b8;
      background: #f1f5f9;
    }}
    select {{
      width: 100%;
      margin-bottom: 12px;
    }}
    #viewer {{
      position: relative;
      min-height: 420px;
      background: #ffffff;
    }}
    #fallbackPreview {{
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
      object-fit: contain;
      background: #050b14;
      display: none;
      z-index: 1;
    }}
    #internalCanvas {{
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
      display: block;
      background: #ffffff;
      cursor: grab;
      touch-action: none;
    }}
    #internalCanvas.dragging {{
      cursor: grabbing;
    }}
    .metric-grid {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
      margin-top: 10px;
    }}
    .metric {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 8px;
      background: #f8fafc;
    }}
    .metric b {{
      display: block;
      font-size: 18px;
      line-height: 1.1;
    }}
    .metric span {{
      color: var(--muted);
      font-size: 12px;
    }}
    .chain-list {{
      display: grid;
      gap: 6px;
      margin-top: 14px;
    }}
    .chain-row, .class-row {{
      display: grid;
      grid-template-columns: 16px 1fr auto;
      gap: 8px;
      align-items: center;
      font-size: 13px;
      color: #334155;
    }}
    .class-section {{
      margin-top: 16px;
      padding-top: 12px;
      border-top: 1px solid var(--line);
    }}
    .qc-list, .residue-list, .interface-list {{
      display: grid;
      gap: 6px;
      font-size: 12px;
      color: #334155;
    }}
    .qc-row, .residue-row, .interface-row {{
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 8px;
      padding: 4px 0;
      border-bottom: 1px solid #e2e8f0;
    }}
    .qc-row:last-child, .residue-row:last-child, .interface-row:last-child {{
      border-bottom: 0;
    }}
    .section-label {{
      margin-bottom: 8px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
      text-transform: uppercase;
    }}
    .swatch {{
      width: 12px;
      height: 12px;
      border-radius: 50%;
      border: 1px solid rgba(15, 23, 42, 0.16);
    }}
    .path {{
      margin-top: 14px;
      padding-top: 12px;
      border-top: 1px solid var(--line);
      color: var(--muted);
      font-size: 12px;
      overflow-wrap: anywhere;
    }}
    .claim {{
      padding: 10px 14px;
      border-top: 1px solid var(--line);
      color: #475569;
      background: #f8fafc;
      font-size: 12px;
    }}
    #message {{
      position: absolute;
      left: 14px;
      top: 14px;
      z-index: 3;
      max-width: 460px;
      padding: 10px 12px;
      border: 1px solid #fecaca;
      border-radius: 8px;
      background: #fef2f2;
      color: #991b1b;
      font-size: 13px;
      display: none;
    }}
    @media (max-width: 860px) {{
      header {{ align-items: flex-start; flex-direction: column; gap: 4px; }}
      .status {{ white-space: normal; }}
      main {{ grid-template-columns: 1fr; }}
      aside {{ border-right: 0; border-bottom: 1px solid var(--line); }}
      .viewer-shell {{ min-height: 560px; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>CASP17 Internal Molecular Viewer</h1>
    <div class="status" id="summaryLine"></div>
  </header>
  <main>
    <aside>
      <select id="targetSelect" aria-label="CASP17 target selector"></select>
      <div class="metric-grid">
        <div class="metric"><b id="metricChains">0</b><span>chains</span></div>
        <div class="metric"><b id="metricResidues">0</b><span>residues</span></div>
        <div class="metric"><b id="metricAtoms">0</b><span>atoms</span></div>
        <div class="metric"><b id="metricB">0</b><span>B-factor mean</span></div>
        <div class="metric"><b id="metricGaps">0</b><span>CA gaps</span></div>
        <div class="metric"><b id="metricClashes">0</b><span>CA clashes</span></div>
      </div>
      <div class="class-section">
        <div class="section-label">Internal QC Overlay</div>
        <div class="qc-list" id="qcList"></div>
      </div>
      <div class="chain-list" id="chainList"></div>
      <div class="class-section">
        <div class="section-label">Residue Classes</div>
        <div class="chain-list" id="residueClassList"></div>
      </div>
      <div class="class-section">
        <div class="section-label">Confidence Bins</div>
        <div class="chain-list" id="confidenceBinList"></div>
      </div>
      <div class="class-section">
        <div class="section-label">Interface Contacts</div>
        <div class="interface-list" id="interfaceList"></div>
      </div>
      <div class="class-section">
        <div class="section-label">Low Confidence Residues</div>
        <div class="residue-list" id="residueList"></div>
      </div>
      <div class="path" id="pathLine"></div>
    </aside>
    <section class="viewer-shell">
      <div class="toolbar">
        <button type="button" data-repr="cartoon" class="active">Cartoon</button>
        <button type="button" data-repr="trace">Trace</button>
        <button type="button" data-repr="stick">Stick</button>
        <button type="button" data-repr="sphere">Sphere</button>
        <button type="button" data-color="chain" class="active">Chain</button>
        <button type="button" data-color="confidence">Confidence</button>
        <button type="button" data-color="residue">Residue Class</button>
        <button type="button" data-color="spectrum">Spectrum</button>
        <button type="button" id="surfaceButton">Surface</button>
        <button type="button" id="issuesButton">Issues</button>
        <button type="button" id="labelsButton">Labels</button>
        <button type="button" id="darkButton">Dark</button>
        <button type="button" id="spinButton">Spin</button>
        <button type="button" id="centerButton">Center</button>
        <a id="molstarLink" href="#" target="_blank" rel="noopener">Mol*</a>
      </div>
      <div id="viewer"><canvas id="internalCanvas" aria-label="internal canvas molecular viewer"></canvas><img id="fallbackPreview" alt="static molecular preview"><div id="message"></div></div>
      <div class="claim" id="claimLine"></div>
    </section>
  </main>
  <script type="application/json" id="viewerData">{data_json}</script>
  <script>
    const DATA = JSON.parse(document.getElementById("viewerData").textContent);
    const state = {{
      targetIndex: 0,
      repr: "cartoon",
      color: "chain",
      surface: false,
      issues: false,
      labels: true,
      dark: false,
      spin: false,
      viewer: null,
      model: null,
      surfaceHandle: null,
      internal: {{
        initialized: false,
        canvas: null,
        context: null,
        atoms: [],
        caChains: [],
        center: {{ x: 0, y: 0, z: 0 }},
        span: 1,
        zoom: 1,
        angleX: -0.42,
        angleY: 0.74,
        dragging: false,
        lastX: 0,
        lastY: 0,
        spinFrame: null
      }}
    }};

    const targetSelect = document.getElementById("targetSelect");
    const summaryLine = document.getElementById("summaryLine");
    const claimLine = document.getElementById("claimLine");
    const message = document.getElementById("message");
    const molstarLink = document.getElementById("molstarLink");

    function activeTarget() {{
      return DATA.targets[state.targetIndex];
    }}

    function showMessage(text) {{
      message.textContent = text;
      message.style.display = text ? "block" : "none";
    }}

    function showInternalCanvas(visible) {{
      const canvas = document.getElementById("internalCanvas");
      canvas.style.display = visible ? "block" : "none";
    }}

    function artifactUrl(path) {{
      if (!path) return "";
      if (/^(https?:|file:)/.test(path)) return path;
      if (path.startsWith("/")) return new URL(path, window.location.href).href;
      return new URL("../" + path, window.location.href).href;
    }}

    function showFallbackPreview(target, text) {{
      const preview = document.getElementById("fallbackPreview");
      showInternalCanvas(false);
      if (target && target.fallback_preview_png_path) {{
        preview.src = artifactUrl(target.fallback_preview_png_path);
        preview.style.display = "block";
      }} else {{
        preview.removeAttribute("src");
        preview.style.display = "none";
      }}
      showMessage(text || "");
    }}

    function hideFallbackPreview() {{
      const preview = document.getElementById("fallbackPreview");
      preview.style.display = "none";
      showInternalCanvas(true);
      showMessage("");
    }}

    function colorInt(hex) {{
      return parseInt(hex.replace("#", ""), 16);
    }}

    function chainColorHex(chainId, target) {{
      const chain = target.chains.find((item) => item.chain_id === chainId);
      return chain ? chain.color : "#64748b";
    }}

    function confidenceColorHex(value) {{
      const raw = Number(value || 0);
      if (raw >= 90) return "#2563eb";
      if (raw >= 70) return "#059669";
      if (raw >= 50) return "#d97706";
      return "#dc2626";
    }}

    function residueClassColorHex(resname) {{
      const residueClass = DATA.residue_class_by_resname[String(resname || "").toUpperCase()] || "unknown";
      return DATA.residue_class_colors[residueClass] || DATA.residue_class_colors.unknown || "#64748b";
    }}

    function spectrumColorHex(index, total) {{
      const hue = total > 1 ? Math.round((index / (total - 1)) * 270) : 205;
      return `hsl(${{hue}} 74% 48%)`;
    }}

    function atomColorHex(atom, target, index, total) {{
      if (state.color === "confidence") return confidenceColorHex(atom.b);
      if (state.color === "residue") return residueClassColorHex(atom.resname);
      if (state.color === "spectrum") return spectrumColorHex(index, total);
      return chainColorHex(atom.chain, target);
    }}

    function confidenceColor(atom, target) {{
      const raw = Number(atom.b || atom.bfactor || 0);
      return colorInt(confidenceColorHex(raw));
    }}

    function chainColor(atom, target) {{
      const chain = target.chains.find((item) => item.chain_id === atom.chain);
      return colorInt(chain ? chain.color : "#64748b");
    }}

    function residueClassForAtom(atom) {{
      const resn = String(atom.resn || atom.residue || "").toUpperCase();
      return DATA.residue_class_by_resname[resn] || "unknown";
    }}

    function residueClassColor(atom) {{
      const residueClass = residueClassForAtom(atom);
      return colorInt(DATA.residue_class_colors[residueClass] || DATA.residue_class_colors.unknown || "#64748b");
    }}

    function parsePdbAtoms(pdbText) {{
      const atoms = [];
      const lines = String(pdbText || "").split(/\\r?\\n/);
      let serialIndex = 0;
      for (const line of lines) {{
        if (!line.startsWith("ATOM")) continue;
        const atom = line.slice(12, 16).trim();
        const resname = line.slice(17, 20).trim();
        const chain = line.slice(21, 22).trim() || "_";
        const resseq = Number.parseInt(line.slice(22, 26).trim(), 10);
        const x = Number.parseFloat(line.slice(30, 38));
        const y = Number.parseFloat(line.slice(38, 46));
        const z = Number.parseFloat(line.slice(46, 54));
        const b = Number.parseFloat(line.slice(60, 66));
        if (!Number.isFinite(x) || !Number.isFinite(y) || !Number.isFinite(z)) continue;
        atoms.push({{
          atom,
          resname,
          chain,
          resseq: Number.isFinite(resseq) ? resseq : 0,
          x,
          y,
          z,
          b: Number.isFinite(b) ? b : 0,
          index: serialIndex++
        }});
      }}
      return atoms;
    }}

    function setupInternalScene(target) {{
      const atoms = parsePdbAtoms(target.pdb_text);
      const center = {{ x: 0, y: 0, z: 0 }};
      if (atoms.length) {{
        for (const atom of atoms) {{
          center.x += atom.x;
          center.y += atom.y;
          center.z += atom.z;
        }}
        center.x /= atoms.length;
        center.y /= atoms.length;
        center.z /= atoms.length;
      }}
      let span = 1;
      if (atoms.length) {{
        const xs = atoms.map((atom) => atom.x);
        const ys = atoms.map((atom) => atom.y);
        const zs = atoms.map((atom) => atom.z);
        span = Math.max(
          Math.max(...xs) - Math.min(...xs),
          Math.max(...ys) - Math.min(...ys),
          Math.max(...zs) - Math.min(...zs),
          1
        );
      }}
      const caByChain = new Map();
      for (const atom of atoms) {{
        if (atom.atom !== "CA") continue;
        if (!caByChain.has(atom.chain)) caByChain.set(atom.chain, []);
        caByChain.get(atom.chain).push(atom);
      }}
      const caChains = Array.from(caByChain.entries()).map(([chain, chainAtoms]) => {{
        chainAtoms.sort((a, b) => a.resseq - b.resseq || a.index - b.index);
        return {{ chain, atoms: chainAtoms }};
      }});
      state.internal.atoms = atoms;
      state.internal.caChains = caChains;
      state.internal.center = center;
      state.internal.span = span;
    }}

    function bindInternalCanvasEvents() {{
      if (state.internal.initialized) return;
      const canvas = document.getElementById("internalCanvas");
      state.internal.canvas = canvas;
      state.internal.context = canvas.getContext("2d");
      canvas.addEventListener("pointerdown", (event) => {{
        state.internal.dragging = true;
        state.internal.lastX = event.clientX;
        state.internal.lastY = event.clientY;
        canvas.classList.add("dragging");
        canvas.setPointerCapture(event.pointerId);
      }});
      canvas.addEventListener("pointermove", (event) => {{
        if (!state.internal.dragging) return;
        const dx = event.clientX - state.internal.lastX;
        const dy = event.clientY - state.internal.lastY;
        state.internal.lastX = event.clientX;
        state.internal.lastY = event.clientY;
        state.internal.angleY += dx * 0.01;
        state.internal.angleX += dy * 0.01;
        drawInternalScene(activeTarget());
      }});
      canvas.addEventListener("pointerup", (event) => {{
        state.internal.dragging = false;
        canvas.classList.remove("dragging");
        try {{ canvas.releasePointerCapture(event.pointerId); }} catch (_error) {{}}
      }});
      canvas.addEventListener("wheel", (event) => {{
        event.preventDefault();
        const factor = event.deltaY > 0 ? 0.9 : 1.1;
        state.internal.zoom = Math.max(0.25, Math.min(5, state.internal.zoom * factor));
        drawInternalScene(activeTarget());
      }}, {{ passive: false }});
      window.addEventListener("resize", () => drawInternalScene(activeTarget()));
      state.internal.initialized = true;
    }}

    function resetInternalView() {{
      state.internal.zoom = 1;
      state.internal.angleX = -0.42;
      state.internal.angleY = 0.74;
      drawInternalScene(activeTarget());
    }}

    function resizeInternalCanvas() {{
      const canvas = state.internal.canvas || document.getElementById("internalCanvas");
      const rect = canvas.getBoundingClientRect();
      const ratio = window.devicePixelRatio || 1;
      const width = Math.max(320, Math.floor(rect.width * ratio));
      const height = Math.max(320, Math.floor(rect.height * ratio));
      if (canvas.width !== width || canvas.height !== height) {{
        canvas.width = width;
        canvas.height = height;
      }}
      return {{ canvas, width, height, ratio }};
    }}

    function rotatePoint(atom) {{
      const center = state.internal.center;
      const x0 = atom.x - center.x;
      const y0 = atom.y - center.y;
      const z0 = atom.z - center.z;
      const cy = Math.cos(state.internal.angleY);
      const sy = Math.sin(state.internal.angleY);
      const cx = Math.cos(state.internal.angleX);
      const sx = Math.sin(state.internal.angleX);
      const x1 = x0 * cy + z0 * sy;
      const z1 = -x0 * sy + z0 * cy;
      const y1 = y0 * cx - z1 * sx;
      const z2 = y0 * sx + z1 * cx;
      return {{ x: x1, y: y1, z: z2 }};
    }}

    function projectAtom(atom, width, height) {{
      const rotated = rotatePoint(atom);
      const scale = (Math.min(width, height) / Math.max(state.internal.span, 1)) * 0.76 * state.internal.zoom;
      return {{
        x: width / 2 + rotated.x * scale,
        y: height / 2 - rotated.y * scale,
        z: rotated.z,
        scale
      }};
    }}

    function projectedRadius(base, z, zMin, zMax) {{
      const depth = zMax > zMin ? (z - zMin) / (zMax - zMin) : 0.5;
      return base * (0.72 + depth * 0.55);
    }}

    function drawCircle(ctx, item, radius, color, alpha = 1) {{
      ctx.save();
      ctx.globalAlpha = alpha;
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(item.x, item.y, radius, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
    }}

    function drawInternalScene(target, options = {{}}) {{
      if (!target) return;
      bindInternalCanvasEvents();
      const ctx = state.internal.context;
      const {{ width, height }} = resizeInternalCanvas();
      ctx.clearRect(0, 0, width, height);
      ctx.fillStyle = state.dark ? "#050b14" : "#ffffff";
      ctx.fillRect(0, 0, width, height);
      const atoms = state.internal.atoms || [];
      if (!atoms.length) {{
        showFallbackPreview(target, "Embedded PDB atom records could not be parsed. Showing the local static preview instead.");
        return;
      }}
      const projectedAtoms = atoms.map((atom, index) => {{
        const point = projectAtom(atom, width, height);
        return {{ atom, index, ...point }};
      }});
      const zValues = projectedAtoms.map((item) => item.z);
      const zMin = Math.min(...zValues);
      const zMax = Math.max(...zValues);
      hideFallbackPreview();

      if (state.surface) {{
        const surfaceAtoms = projectedAtoms
          .filter((item) => item.atom.atom === "CA" || item.atom.atom === "CB" || item.index % 4 === 0)
          .sort((a, b) => a.z - b.z);
        for (const item of surfaceAtoms) {{
          drawCircle(ctx, item, projectedRadius(10, item.z, zMin, zMax), atomColorHex(item.atom, target, item.index, atoms.length), state.dark ? 0.13 : 0.16);
        }}
      }}

      for (const chain of state.internal.caChains) {{
        const points = chain.atoms.map((atom) => ({{
          atom,
          ...projectAtom(atom, width, height)
        }}));
        if (points.length < 2) continue;
        ctx.save();
        ctx.lineCap = "round";
        ctx.lineJoin = "round";
        ctx.lineWidth = state.repr === "cartoon" ? 5.5 : state.repr === "trace" ? 2.4 : 1.4;
        ctx.strokeStyle = state.color === "chain" ? chainColorHex(chain.chain, target) : atomColorHex(points[0].atom, target, 0, atoms.length);
        ctx.globalAlpha = state.dark ? 0.95 : 0.9;
        ctx.beginPath();
        points.forEach((point, index) => {{
          if (index === 0) ctx.moveTo(point.x, point.y);
          else ctx.lineTo(point.x, point.y);
        }});
        ctx.stroke();
        ctx.restore();

        if (state.repr === "cartoon" || state.repr === "trace") {{
          for (const [index, point] of points.entries()) {{
            const radius = state.repr === "cartoon" ? 3.1 : 2.4;
            drawCircle(ctx, point, projectedRadius(radius, point.z, zMin, zMax), atomColorHex(point.atom, target, index, points.length), 0.96);
          }}
        }}
      }}

      if (state.repr === "stick" || state.repr === "sphere") {{
        const sampleStride = atoms.length > 9000 ? 3 : atoms.length > 4500 ? 2 : 1;
        const drawable = projectedAtoms
          .filter((item) => item.index % sampleStride === 0)
          .sort((a, b) => a.z - b.z);
        if (state.repr === "stick") {{
          const backbone = drawable.filter((item) => ["N", "CA", "C", "O", "CB"].includes(item.atom.atom));
          ctx.save();
          ctx.lineCap = "round";
          ctx.lineWidth = 1.15;
          ctx.globalAlpha = 0.62;
          for (let index = 1; index < backbone.length; index += 1) {{
            const left = backbone[index - 1];
            const right = backbone[index];
            if (left.atom.chain !== right.atom.chain || Math.abs(left.atom.resseq - right.atom.resseq) > 1) continue;
            ctx.strokeStyle = atomColorHex(right.atom, target, right.index, atoms.length);
            ctx.beginPath();
            ctx.moveTo(left.x, left.y);
            ctx.lineTo(right.x, right.y);
            ctx.stroke();
          }}
          ctx.restore();
        }}
        for (const item of drawable) {{
          const base = state.repr === "sphere" ? 2.9 : 1.75;
          drawCircle(ctx, item, projectedRadius(base, item.z, zMin, zMax), atomColorHex(item.atom, target, item.index, atoms.length), 0.92);
        }}
      }}

      if (state.issues) {{
        renderInternalIssues(ctx, target, width, height, zMin, zMax);
      }}
      if (state.labels) {{
        renderInternalLabels(ctx, target, width, height);
      }}
      updateToolbar();
      if (!options.skipSpinSync) syncInternalSpin();
    }}

    function renderInternalIssues(ctx, target, width, height, zMin, zMax) {{
      const markers = (target.geometry && target.geometry.issue_markers) || [];
      for (const marker of markers.slice(0, 160)) {{
        const point = projectAtom(marker.center, width, height);
        const color = marker.kind === "ca_clash" ? "#dc2626" : "#d97706";
        drawCircle(ctx, point, projectedRadius(7, point.z, zMin, zMax), color, 0.78);
      }}
    }}

    function renderInternalLabels(ctx, target, width, height) {{
      ctx.save();
      ctx.font = `${{Math.max(11, Math.round(width / 94))}}px ui-sans-serif, system-ui, sans-serif`;
      ctx.textBaseline = "middle";
      for (const chain of target.chains) {{
        const point = projectAtom(chain.center, width, height);
        const text = `Chain ${{chain.chain_id}}`;
        const padding = 5;
        const metrics = ctx.measureText(text);
        ctx.fillStyle = chain.color;
        ctx.globalAlpha = 0.86;
        ctx.fillRect(point.x - padding, point.y - 10, metrics.width + padding * 2, 20);
        ctx.globalAlpha = 1;
        ctx.fillStyle = "white";
        ctx.fillText(text, point.x, point.y);
      }}
      ctx.restore();
    }}

    function renderInternalCanvas(target, text) {{
      state.viewer = null;
      state.model = null;
      setupInternalScene(target);
      showMessage(text || "");
      drawInternalScene(target);
    }}

    function syncInternalSpin() {{
      if (state.viewer || !state.spin || state.internal.spinFrame) return;
      const animate = () => {{
        state.internal.spinFrame = null;
        if (state.viewer || !state.spin) return;
        state.internal.angleY += 0.012;
        drawInternalScene(activeTarget(), {{ skipSpinSync: true }});
        state.internal.spinFrame = window.requestAnimationFrame(animate);
      }};
      state.internal.spinFrame = window.requestAnimationFrame(animate);
    }}

    function stopInternalSpin() {{
      if (state.internal.spinFrame) {{
        window.cancelAnimationFrame(state.internal.spinFrame);
        state.internal.spinFrame = null;
      }}
    }}

    function styleForTarget(target) {{
      const base = {{}};
      if (state.color === "confidence") {{
        base.colorfunc = (atom) => confidenceColor(atom, target);
      }} else if (state.color === "residue") {{
        base.colorfunc = (atom) => residueClassColor(atom);
      }} else if (state.color === "spectrum") {{
        base.color = "spectrum";
      }} else {{
        base.colorfunc = (atom) => chainColor(atom, target);
      }}
      if (state.repr === "trace") {{
        return {{ line: {{ linewidth: 2, ...base }}, sphere: {{ radius: 0.28, ...base }} }};
      }}
      if (state.repr === "stick") {{
        return {{ stick: {{ radius: 0.14, ...base }} }};
      }}
      if (state.repr === "sphere") {{
        return {{ sphere: {{ radius: 0.55, ...base }} }};
      }}
      return {{ cartoon: {{ thickness: 0.42, arrows: true, ...base }} }};
    }}

    function loadTarget() {{
      const target = activeTarget();
      if (!target) {{
        showMessage("No ready CASP17 structures are embedded in this viewer packet.");
        return;
      }}
      updateSidePanel(target);
      if (!window.$3Dmol) {{
        renderInternalCanvas(target, "Internal canvas runtime active. No external network or local 3Dmol bundle is required.");
        return;
      }}
      const element = document.getElementById("viewer");
      stopInternalSpin();
      showInternalCanvas(false);
      element.querySelectorAll("canvas:not(#internalCanvas)").forEach((node) => node.remove());
      try {{
        state.viewer = $3Dmol.createViewer(element, {{ backgroundColor: state.dark ? "#050b14" : "white" }});
        state.model = state.viewer.addModel(target.pdb_text, "pdb");
        hideFallbackPreview();
        showInternalCanvas(false);
        applyStyle();
        state.viewer.zoomTo();
        state.viewer.render();
      }} catch (error) {{
        state.viewer = null;
        state.model = null;
        renderInternalCanvas(target, "3Dmol/WebGL rendering failed in this browser session. Using the internal canvas runtime.");
      }}
    }}

    function applyStyle() {{
      const target = activeTarget();
      if (!target) return;
      if (!state.viewer) {{
        drawInternalScene(target);
        updateToolbar();
        return;
      }}
      state.viewer.removeAllSurfaces();
      if (state.viewer.removeAllShapes) state.viewer.removeAllShapes();
      state.viewer.removeAllLabels();
      if (state.viewer.setBackgroundColor) state.viewer.setBackgroundColor(state.dark ? "#050b14" : "white");
      state.viewer.setStyle({{}}, {{}});
      const style = styleForTarget(target);
      if (state.repr === "trace") {{
        state.viewer.setStyle({{}}, {{ line: style.line }});
        state.viewer.addStyle({{ atom: "CA" }}, {{ sphere: style.sphere }});
      }} else {{
        state.viewer.setStyle({{}}, style);
      }}
      if (state.surface) {{
        state.viewer.addSurface($3Dmol.SurfaceType.VDW, {{ opacity: state.dark ? 0.16 : 0.22, color: state.dark ? "#dbeafe" : "white" }}, {{}});
      }}
      if (state.labels) {{
        for (const chain of target.chains) {{
          state.viewer.addLabel(`Chain ${{chain.chain_id}}`, {{
            position: chain.center,
            backgroundColor: chain.color,
            fontColor: "white",
            fontSize: 12,
            padding: 3,
            inFront: false
          }});
        }}
      }}
      if (state.issues) {{
        renderIssues(target);
      }}
      state.viewer.spin(state.spin);
      state.viewer.render();
      updateToolbar();
    }}

    function renderIssues(target) {{
      const markers = (target.geometry && target.geometry.issue_markers) || [];
      for (const marker of markers.slice(0, 120)) {{
        const isClash = marker.kind === "ca_clash";
        const color = isClash ? "#dc2626" : "#d97706";
        state.viewer.addSphere({{
          center: marker.center,
          radius: isClash ? 1.0 : 0.8,
          color,
          alpha: 0.78
        }});
        state.viewer.addLabel(marker.label, {{
          position: marker.center,
          backgroundColor: color,
          fontColor: "white",
          fontSize: 10,
          padding: 2,
          inFront: true
        }});
      }}
    }}

    function updateToolbar() {{
      document.querySelectorAll("[data-repr]").forEach((button) => {{
        button.classList.toggle("active", button.dataset.repr === state.repr);
      }});
      document.querySelectorAll("[data-color]").forEach((button) => {{
        button.classList.toggle("active", button.dataset.color === state.color);
      }});
      document.getElementById("surfaceButton").classList.toggle("active", state.surface);
      document.getElementById("issuesButton").classList.toggle("active", state.issues);
      document.getElementById("labelsButton").classList.toggle("active", state.labels);
      document.getElementById("darkButton").classList.toggle("active", state.dark);
      document.getElementById("spinButton").classList.toggle("active", state.spin);
    }}

    function updateMolstarLink(target) {{
      molstarLink.classList.remove("disabled");
      molstarLink.removeAttribute("aria-disabled");
      if (!DATA.summary.external_molstar_link_enabled || !DATA.summary.external_molstar_base_url) {{
        molstarLink.href = "#";
        molstarLink.classList.add("disabled");
        molstarLink.setAttribute("aria-disabled", "true");
        molstarLink.title = "External Mol* handoff is disabled by default for the internal-only CASP17 lane.";
        return;
      }}
      if (window.location.protocol === "file:") {{
        molstarLink.href = "#";
        molstarLink.classList.add("disabled");
        molstarLink.setAttribute("aria-disabled", "true");
        molstarLink.title = "Serve the repository over HTTP to open this target in Mol* by URL.";
        return;
      }}
      const pdbUrl = new URL(artifactUrl(target.prediction_file_path));
      const viewerUrl = new URL(DATA.summary.external_molstar_base_url);
      viewerUrl.searchParams.set("structure-url", pdbUrl.href);
      viewerUrl.searchParams.set("structure-url-format", "pdb");
      molstarLink.href = viewerUrl.href;
      molstarLink.title = "Open the current prediction in the explicitly enabled external Mol* handoff.";
    }}

    function updateSidePanel(target) {{
      summaryLine.textContent = `${{DATA.summary.ready_count}} of ${{DATA.summary.target_count}} targets ready | generated ${{DATA.summary.generated_at_local}}`;
      claimLine.textContent = DATA.summary.claim_boundary;
      document.getElementById("metricChains").textContent = target.chain_count;
      document.getElementById("metricResidues").textContent = target.residue_count;
      document.getElementById("metricAtoms").textContent = target.atom_count;
      document.getElementById("metricB").textContent = Number(target.b_factor.mean || 0).toFixed(1);
      const geometry = target.geometry || {{}};
      document.getElementById("metricGaps").textContent = geometry.ca_gap_count || 0;
      document.getElementById("metricClashes").textContent = geometry.ca_clash_count || 0;
      document.getElementById("pathLine").textContent = target.prediction_file_path;
      updateQcPanel(target);
      const chainList = document.getElementById("chainList");
      chainList.innerHTML = "";
      for (const chain of target.chains) {{
        const row = document.createElement("div");
        row.className = "chain-row";
        row.innerHTML = `<span class="swatch" style="background:${{chain.color}}"></span><span>Chain ${{chain.chain_id}}</span><span>${{chain.residue_count}} res</span>`;
        chainList.appendChild(row);
      }}
      const classList = document.getElementById("residueClassList");
      classList.innerHTML = "";
      const classLabels = {{
        hydrophobic: "Hydrophobic",
        polar: "Polar",
        positive: "Positive",
        negative: "Negative",
        aromatic: "Aromatic",
        special: "Special",
        unknown: "Unknown"
      }};
      const classCounts = target.residue_class_counts || {{}};
      for (const key of ["hydrophobic", "polar", "positive", "negative", "aromatic", "special", "unknown"]) {{
        const count = Number(classCounts[key] || 0);
        if (!count) continue;
        const row = document.createElement("div");
        row.className = "class-row";
        row.innerHTML = `<span class="swatch" style="background:${{DATA.residue_class_colors[key] || "#64748b"}}"></span><span>${{classLabels[key]}}</span><span>${{count}} res</span>`;
        classList.appendChild(row);
      }}
      updateMolstarLink(target);
    }}

    function updateQcPanel(target) {{
      const qc = target.qc_overlay || {{}};
      const rows = [
        ["Raw QC hotspots", qc.raw_qc_hotspot_count || 0],
        ["Rendered QC markers", qc.rendered_qc_hotspot_count || 0],
        ["Raw low-confidence hotspots", qc.raw_low_confidence_hotspot_count || 0],
        ["Raw soft hotspots", qc.raw_soft_hotspot_count || 0],
        ["Marker cap truncated", qc.qc_hotspot_truncated ? "yes" : "no"],
        ["All-atom soft clashes", qc.all_atom_soft_clash_count || 0],
        ["All-atom severe clashes", qc.all_atom_severe_clash_count || 0],
        ["Sidechain complete", `${{Number(qc.sidechain_complete_fraction || 0).toFixed(3)}}`],
        ["Rotamer proxy pass", `${{Number(qc.rotamer_proxy_pass_fraction || 0).toFixed(3)}}`]
      ];
      const qcList = document.getElementById("qcList");
      qcList.innerHTML = "";
      for (const [label, value] of rows) {{
        const row = document.createElement("div");
        row.className = "qc-row";
        row.innerHTML = `<span>${{label}}</span><b>${{value}}</b>`;
        qcList.appendChild(row);
      }}

      const confidenceList = document.getElementById("confidenceBinList");
      const binLabels = {{
        very_high: "Very high >=90",
        confident: "Confident 70-89",
        low: "Low 50-69",
        very_low: "Very low <50"
      }};
      const binColors = {{
        very_high: "#2563eb",
        confident: "#059669",
        low: "#d97706",
        very_low: "#dc2626"
      }};
      confidenceList.innerHTML = "";
      for (const key of ["very_high", "confident", "low", "very_low"]) {{
        const row = document.createElement("div");
        row.className = "class-row";
        row.innerHTML = `<span class="swatch" style="background:${{binColors[key]}}"></span><span>${{binLabels[key]}}</span><span>${{Number((target.confidence_bins || {{}})[key] || 0)}} res</span>`;
        confidenceList.appendChild(row);
      }}

      const interfaceList = document.getElementById("interfaceList");
      interfaceList.innerHTML = "";
      const interfaceInfo = target.interface || {{}};
      const pairs = interfaceInfo.pairs || [];
      if (!pairs.length) {{
        const row = document.createElement("div");
        row.className = "interface-row";
        row.innerHTML = "<span>Single-chain or no chain-pair CA contacts</span><b>-</b>";
        interfaceList.appendChild(row);
      }} else {{
        for (const pair of pairs.slice(0, 12)) {{
          const row = document.createElement("div");
          row.className = "interface-row";
          row.innerHTML = `<span>${{pair.chain_pair}} min ${{Number(pair.min_ca_distance || 0).toFixed(2)}}A</span><b>${{pair.ca_contacts_12a || 0}} <=12A</b>`;
          interfaceList.appendChild(row);
        }}
      }}

      const residueList = document.getElementById("residueList");
      residueList.innerHTML = "";
      const lowResidues = (target.residues || [])
        .filter((residue) => residue.low_confidence)
        .sort((a, b) => Number(a.confidence_mean || 0) - Number(b.confidence_mean || 0))
        .slice(0, 12);
      if (!lowResidues.length) {{
        const row = document.createElement("div");
        row.className = "residue-row";
        row.innerHTML = "<span>No residue below 50 B-factor confidence</span><b>-</b>";
        residueList.appendChild(row);
      }} else {{
        for (const residue of lowResidues) {{
          const row = document.createElement("div");
          row.className = "residue-row";
          row.innerHTML = `<span>${{residue.chain_id}}:${{residue.resname}}${{residue.resseq}}${{residue.insertion || ""}}</span><b>${{Number(residue.confidence_mean || 0).toFixed(1)}}</b>`;
          residueList.appendChild(row);
        }}
      }}
    }}

    function initialize() {{
      for (const [index, target] of DATA.targets.entries()) {{
        const option = document.createElement("option");
        option.value = String(index);
        option.textContent = `${{target.target_id}} - ${{target.chain_count}} chains, ${{target.residue_count}} residues`;
        targetSelect.appendChild(option);
      }}
      targetSelect.addEventListener("change", () => {{
        state.targetIndex = Number(targetSelect.value);
        loadTarget();
      }});
      document.querySelectorAll("[data-repr]").forEach((button) => {{
        button.addEventListener("click", () => {{
          state.repr = button.dataset.repr;
          applyStyle();
        }});
      }});
      document.querySelectorAll("[data-color]").forEach((button) => {{
        button.addEventListener("click", () => {{
          state.color = button.dataset.color;
          applyStyle();
        }});
      }});
      document.getElementById("surfaceButton").addEventListener("click", () => {{
        state.surface = !state.surface;
        applyStyle();
      }});
      document.getElementById("issuesButton").addEventListener("click", () => {{
        state.issues = !state.issues;
        applyStyle();
      }});
      document.getElementById("labelsButton").addEventListener("click", () => {{
        state.labels = !state.labels;
        applyStyle();
      }});
      document.getElementById("darkButton").addEventListener("click", () => {{
        state.dark = !state.dark;
        loadTarget();
      }});
      document.getElementById("spinButton").addEventListener("click", () => {{
        state.spin = !state.spin;
        if (state.viewer) state.viewer.spin(state.spin);
        else syncInternalSpin();
        updateToolbar();
      }});
      document.getElementById("centerButton").addEventListener("click", () => {{
        if (state.viewer) {{
          state.viewer.zoomTo();
          state.viewer.render();
        }} else {{
          resetInternalView();
        }}
      }});
      loadTarget();
    }}

    initialize();
  </script>
</body>
</html>
"""
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(html, encoding="utf-8")
    return _artifact(html_path), viewer_runtime_path


def _public_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    public: list[dict[str, Any]] = []
    for row in rows:
        public.append({key: value for key, value in row.items() if not key.startswith("_")})
    return public


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    watchlist = _read_json(args.target_watchlist_json)
    render_rows = _rows_by_target(_read_json(args.render_json))
    review_rows = _rows_by_target(_read_json(args.review_queue_json))
    all_atom_rows = _rows_by_target(_read_json(args.all_atom_quality_json))
    sidechain_rows = _rows_by_target(_read_json(args.sidechain_quality_json))
    target_ids = _current_open_targets(watchlist)
    if args.target_limit > 0:
        target_ids = target_ids[: args.target_limit]

    rows: list[dict[str, Any]] = []
    for target_id, pdb_path in _prediction_paths(args.prediction_dir, target_ids):
        qc_overlay = _qc_overlay_for_target(
            target_id,
            render_rows=render_rows,
            review_rows=review_rows,
            all_atom_rows=all_atom_rows,
            sidechain_rows=sidechain_rows,
        )
        rows.append(_build_target_row(target_id, pdb_path, render_dir=args.render_dir, qc_overlay=qc_overlay))

    ready_count = sum(1 for row in rows if row["viewer_status"] == "ready")
    local_viewer_js_exists = bool(args.viewer_js_path and _resolve(args.viewer_js_path).is_file())
    summary = {
        "packet_type": "casp17_molecular_viewer_packet",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "target_watchlist_json": _artifact(args.target_watchlist_json),
        "prediction_dir": _artifact(args.prediction_dir),
        "render_json": _artifact(args.render_json),
        "review_queue_json": _artifact(args.review_queue_json),
        "all_atom_quality_json": _artifact(args.all_atom_quality_json),
        "sidechain_quality_json": _artifact(args.sidechain_quality_json),
        "target_count": len(rows),
        "ready_count": ready_count,
        "blocked_count": len(rows) - ready_count,
        "viewer_html_path": _artifact(args.out_html),
        "embedded_viewer": "Local internal canvas molecular inspection packet with optional local 3Dmol WebGL runtime and static fallback",
        "webgl_runtime": "local_3dmol_bundle" if local_viewer_js_exists else "internal_canvas_runtime",
        "internal_canvas_runtime_enabled": True,
        "static_preview_fallback_enabled": True,
        "viewer_runtime_order": "local_3dmol_bundle,internal_canvas_runtime,static_preview_fallback",
        "local_viewer_js_path": _artifact(args.viewer_js_path) if local_viewer_js_exists else "",
        "external_network_default": "disabled",
        "fallback_preview_dir": _artifact(args.render_dir),
        "molstar_deeplink": "disabled by default for the internal-only CASP17 lane",
        "external_molstar_link_enabled": bool(args.enable_external_molstar_link),
        "external_molstar_base_url": "https://molstar.org/viewer/" if args.enable_external_molstar_link else "",
        "author_redacted_in_embedded_pdb": bool(args.redact_author),
        "residue_class_coloring": "hydrophobic,polar,positive,negative,aromatic,special,unknown",
        "confidence_coloring": "fixed B-factor confidence thresholds: >=90 very high, >=70 confident, >=50 low, <50 very low",
        "qc_overlay_source": "structure_render_review_queue + structure_render + all_atom_quality + sidechain_quality packets",
        "raw_qc_hotspot_count": sum(int(row.get("raw_qc_hotspot_count") or 0) for row in rows),
        "rendered_qc_hotspot_count": sum(int(row.get("rendered_qc_hotspot_count") or 0) for row in rows),
        "raw_low_confidence_hotspot_count": sum(int(row.get("raw_low_confidence_hotspot_count") or 0) for row in rows),
        "raw_soft_hotspot_count": sum(int(row.get("raw_soft_hotspot_count") or 0) for row in rows),
        "all_atom_soft_clash_count": sum(int(row.get("all_atom_soft_clash_count") or 0) for row in rows),
        "qc_hotspot_truncated_target_count": sum(1 for row in rows if row.get("qc_hotspot_truncated")),
        "claim_boundary": "Interactive visualization of internal CASP17 predicted coordinates only; not official CASP accuracy evidence or experimental structure.",
    }
    payload = {"summary": summary, "rows": _public_rows(rows)}
    viewer_items = _viewer_items(rows, redact_author=args.redact_author)
    summary["viewer_html_path"], summary["local_viewer_js_path"] = _write_html(
        args.out_html,
        payload,
        viewer_items=viewer_items,
        viewer_js_path=args.viewer_js_path,
    )
    summary["webgl_runtime"] = "local_3dmol_bundle" if summary["local_viewer_js_path"] else "internal_canvas_runtime"
    return payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a local interactive molecular viewer for CASP17 internal TS predictions.")
    parser.add_argument("--target-watchlist-json", default=DEFAULT_WATCHLIST_JSON)
    parser.add_argument("--prediction-dir", default=DEFAULT_PREDICTION_DIR)
    parser.add_argument("--target-limit", type=int, default=0)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--out-html", default=DEFAULT_OUT_HTML)
    parser.add_argument("--render-dir", default=DEFAULT_RENDER_DIR)
    parser.add_argument("--render-json", default=DEFAULT_RENDER_JSON)
    parser.add_argument("--review-queue-json", default=DEFAULT_REVIEW_QUEUE_JSON)
    parser.add_argument("--all-atom-quality-json", default=DEFAULT_ALL_ATOM_QUALITY_JSON)
    parser.add_argument("--sidechain-quality-json", default=DEFAULT_SIDECHAIN_QUALITY_JSON)
    parser.add_argument("--viewer-js-path", default="")
    parser.add_argument("--enable-external-molstar-link", action="store_true")
    parser.add_argument("--redact-author", action=argparse.BooleanOptionalAction, default=True)
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
