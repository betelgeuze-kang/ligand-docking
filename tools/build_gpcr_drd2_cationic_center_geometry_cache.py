#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any

import numpy as np

from tools.build_gpcr_atom_window_anchor_feature_cache import _parse_pdb_anchor_template

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_INPUT_CSV = "runs/gpcr_drd2_pseudo_allatom_repair_rows_current.csv"
DEFAULT_OUT_CSV = "runs/gpcr_drd2_cationic_center_geometry_cache_current.csv"
DEFAULT_OUT_JSON = "runs/gpcr_drd2_cationic_center_geometry_cache_current.json"
DEFAULT_OUT_MD = "runs/gpcr_drd2_cationic_center_geometry_cache_current.md"


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _text(value: Any) -> str:
    return str(value or "").strip()


def _read_csv(path_like: str | Path) -> list[dict[str, str]]:
    path = _resolve(path_like)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _base_row(row: dict[str, Any], reason: str = "") -> dict[str, Any]:
    return {
        "target": _text(row.get("target")),
        "ligand_id": _text(row.get("ligand_id")),
        "class_a_cationic_center_available": 0,
        "class_a_cationic_center_reason": reason,
        "class_a_cationic_center_basis": "",
        "class_a_cationic_center_frame_count": 0,
        "class_a_cationic_center_basic_atom_count": 0,
        "class_a_cationic_center_anchor_atom_count": 0,
        "class_a_cationic_center_min_distance_A": "",
        "class_a_cationic_center_p10_distance_A": "",
        "class_a_cationic_center_mean_distance_A": "",
        "class_a_cationic_center_contact_fraction_le_2p8A": "",
        "class_a_cationic_center_contact_fraction_2p8_4p2A": "",
        "class_a_cationic_center_contact_fraction_ge_4p2A": "",
        "class_a_cationic_center_contact_fraction_le_6A": "",
        "class_a_cationic_center_trajectory_npz": _text(row.get("trajectory_npz")),
        "class_a_cationic_center_native_pdb": _text(row.get("protein_structure_source_path")),
    }


def _anchor_indices(native_pdb: str, protein_atom_count: int) -> list[int]:
    if not _text(native_pdb):
        return []
    template = _parse_pdb_anchor_template(native_pdb)
    if not template.get("available"):
        return []
    return [
        int(idx)
        for idx in template.get("anchor_atom_indices", [])
        if 0 <= int(idx) < int(max(protein_atom_count, 0))
    ]


def _pdb_protein_atom_coords(native_pdb: str) -> np.ndarray:
    if not _text(native_pdb):
        return np.zeros((0, 3), dtype=np.float32)
    pdb_path = _resolve(native_pdb)
    if not pdb_path.exists():
        return np.zeros((0, 3), dtype=np.float32)
    coords: list[list[float]] = []
    with pdb_path.open("r", encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            if not line.startswith("ATOM"):
                continue
            try:
                coords.append([float(line[30:38]), float(line[38:46]), float(line[46:54])])
            except Exception:
                continue
    return np.asarray(coords, dtype=np.float32) if coords else np.zeros((0, 3), dtype=np.float32)


def _static_anchor_coords(native_pdb: str) -> np.ndarray:
    template = _parse_pdb_anchor_template(native_pdb) if _text(native_pdb) else {}
    raw_indices = [int(idx) for idx in template.get("anchor_atom_indices", [])] if template.get("available") else []
    protein_coords = _pdb_protein_atom_coords(native_pdb)
    if not raw_indices or protein_coords.size <= 0:
        return np.zeros((0, 3), dtype=np.float32)
    valid = [idx for idx in raw_indices if 0 <= idx < int(protein_coords.shape[0])]
    return np.asarray(protein_coords[valid, :], dtype=np.float32) if valid else np.zeros((0, 3), dtype=np.float32)


def _cache_row(row: dict[str, Any]) -> dict[str, Any]:
    out = _base_row(row)
    trajectory_npz = _text(row.get("trajectory_npz"))
    native_pdb = _text(row.get("protein_structure_source_path"))
    if not trajectory_npz:
        return {**out, "class_a_cationic_center_reason": "trajectory_npz_missing"}
    npz_path = _resolve(trajectory_npz)
    if not npz_path.exists():
        return {**out, "class_a_cationic_center_reason": "trajectory_npz_missing"}
    try:
        with np.load(str(npz_path), allow_pickle=False) as npz:
            ligand_frames = np.asarray(npz["ligand_frames"], dtype=float)
            protein_atom_frames = (
                np.asarray(npz["protein_atom_frames"], dtype=float)
                if "protein_atom_frames" in npz.files
                else np.zeros((0, 0, 3), dtype=float)
            )
            static_anchor = (
                np.asarray(npz["ligand_backmapping_static_anchor_coords"], dtype=float)
                if "ligand_backmapping_static_anchor_coords" in npz.files
                else _static_anchor_coords(native_pdb)
            )
            basic_indices = np.asarray(npz["ligand_basic_amine_atom_indices"], dtype=int)
    except Exception as exc:
        return {**out, "class_a_cationic_center_reason": f"trajectory_npz_unreadable:{type(exc).__name__}"}
    if ligand_frames.ndim != 3 or ligand_frames.shape[0] <= 0 or ligand_frames.shape[2] != 3:
        return {**out, "class_a_cationic_center_reason": "ligand_frames_invalid"}
    valid_basic = [int(idx) for idx in basic_indices.tolist() if 0 <= int(idx) < ligand_frames.shape[1]]
    if not valid_basic:
        return {**out, "class_a_cationic_center_reason": "basic_amine_center_missing"}
    anchors = _anchor_indices(native_pdb, int(protein_atom_frames.shape[1])) if protein_atom_frames.ndim == 3 else []
    if anchors and protein_atom_frames.ndim == 3 and protein_atom_frames.shape[0] > 0 and protein_atom_frames.shape[2] == 3:
        frame_count = min(int(ligand_frames.shape[0]), int(protein_atom_frames.shape[0]))
        anchor_center = np.mean(protein_atom_frames[:frame_count, anchors, :], axis=1)
        anchor_count = int(len(anchors))
    elif static_anchor.ndim == 2 and static_anchor.shape[0] > 0 and static_anchor.shape[1] == 3:
        frame_count = int(ligand_frames.shape[0])
        anchor_center = np.repeat(np.mean(static_anchor, axis=0)[None, :], frame_count, axis=0)
        anchor_count = int(static_anchor.shape[0])
    else:
        return {**out, "class_a_cationic_center_reason": "acidic_anchor_missing"}
    basic_xyz = ligand_frames[:frame_count, valid_basic, :]
    distances_by_basic = np.linalg.norm(basic_xyz - anchor_center[:, None, :], axis=2)
    distances = np.min(distances_by_basic, axis=1)
    return {
        **out,
        "class_a_cationic_center_available": 1,
        "class_a_cationic_center_reason": "ok",
        "class_a_cationic_center_basis": "closest_basic_amine_atom_to_acidic_anchor_center",
        "class_a_cationic_center_frame_count": int(frame_count),
        "class_a_cationic_center_basic_atom_count": int(len(valid_basic)),
        "class_a_cationic_center_anchor_atom_count": int(anchor_count),
        "class_a_cationic_center_min_distance_A": float(np.min(distances)),
        "class_a_cationic_center_p10_distance_A": float(np.percentile(distances, 10)),
        "class_a_cationic_center_mean_distance_A": float(np.mean(distances)),
        "class_a_cationic_center_contact_fraction_le_2p8A": float(np.mean(distances <= 2.8)),
        "class_a_cationic_center_contact_fraction_2p8_4p2A": float(
            np.mean((distances >= 2.8) & (distances <= 4.2))
        ),
        "class_a_cationic_center_contact_fraction_ge_4p2A": float(np.mean(distances >= 4.2)),
        "class_a_cationic_center_contact_fraction_le_6A": float(np.mean(distances <= 6.0)),
    }


def build_cache(
    *,
    input_csv: str | Path = DEFAULT_INPUT_CSV,
    generated_at_local: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source_rows = _read_csv(input_csv)
    rows = [_cache_row(row) for row in source_rows]
    available = [row for row in rows if int(row.get("class_a_cationic_center_available") or 0) == 1]
    positive = next((row for row in rows if row.get("ligand_id") == "CHEMBL301265"), {})
    summary = {
        "generated_at_local": generated_at_local or dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "input_csv": str(_resolve(input_csv)),
        "input_row_count": len(source_rows),
        "row_count": len(rows),
        "available_feature_count": len(available),
        "missing_feature_count": len(rows) - len(available),
        "positive_available": bool(int(positive.get("class_a_cationic_center_available") or 0) == 1),
        "positive_mean_distance_A": positive.get("class_a_cationic_center_mean_distance_A"),
        "positive_window_fraction_2p8_4p2A": positive.get("class_a_cationic_center_contact_fraction_2p8_4p2A"),
        "claim_promotion_allowed": False,
        "scorer_apply_allowed": False,
        "interpretation": (
            "Cationic-center-to-acidic-anchor geometry cache for claim-locked DRD2 diagnostics. "
            "Rows without basic amine are missing geometry, not failures."
        ),
    }
    return rows, summary


def _render_markdown(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# GPCR DRD2 Cationic-Center Geometry Cache",
            "",
            f"- input_row_count: `{summary['input_row_count']}`",
            f"- available_feature_count: `{summary['available_feature_count']}`",
            f"- missing_feature_count: `{summary['missing_feature_count']}`",
            f"- positive_available: `{str(summary['positive_available']).lower()}`",
            f"- positive_mean_distance_A: `{summary['positive_mean_distance_A']}`",
            f"- positive_window_fraction_2p8_4p2A: `{summary['positive_window_fraction_2p8_4p2A']}`",
            "- claim_promotion_allowed: `false`",
            "- scorer_apply_allowed: `false`",
            "",
        ]
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build DRD2 cationic-center geometry cache from repaired GPCR rows.")
    parser.add_argument("--input-csv", default=DEFAULT_INPUT_CSV)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows, summary = build_cache(input_csv=args.input_csv)
    _write_csv(args.out_csv, rows)
    summary["out_csv"] = str(_resolve(args.out_csv))
    _write_json(args.out_json, {"packet_type": "gpcr_drd2_cationic_center_geometry_cache", "summary": summary})
    out_md = _resolve(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(_render_markdown(summary), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
