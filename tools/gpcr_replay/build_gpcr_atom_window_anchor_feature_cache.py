#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_INPUT_CSV = (
    "runs/external_validation_2026-05-03_family_balanced_frozen_r2_set1_core_blind_gpcr_core_full_"
    "p0_n100000_r1_stage3_scores.csv"
)
DEFAULT_OUT_CSV = "runs/gpcr_atom_window_anchor_feature_cache_current.csv"
DEFAULT_OUT_JSON = "runs/gpcr_atom_window_anchor_feature_cache_current.json"
DEFAULT_OUT_MD = "runs/gpcr_atom_window_anchor_feature_cache_current.md"

EXCLUDED_NATIVE_LIGAND_RESN = {
    "HOH",
    "WAT",
    "DOD",
    "PEG",
    "OLA",
    "OLC",
    "CLR",
    "CHL",
    "NA",
    "CL",
    "K",
    "MG",
    "CA",
    "ZN",
}
ACID_SIDECHAIN_ATOMS = {"ASP": {"OD1", "OD2"}, "GLU": {"OE1", "OE2"}}


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _text(value: Any) -> str:
    return str(value or "").strip()


def _float(value: Any) -> float | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if np.isfinite(out) else None


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _parse_pdb_anchor_template(path: str | Path) -> dict[str, Any]:
    pdb_path = _resolve(path)
    if not pdb_path.exists():
        return {"available": False, "reason": "native_pdb_missing", "anchor_atom_indices": []}
    protein_atoms: list[dict[str, Any]] = []
    acid_atoms: list[dict[str, Any]] = []
    het_groups: dict[tuple[str, str, str], list[list[float]]] = {}
    with pdb_path.open("r", encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            if line.startswith("ATOM"):
                atom_index = len(protein_atoms)
                atom_name = _text(line[12:16]).upper()
                resn = _text(line[17:20]).upper()
                chain = _text(line[21:22])
                resi = _text(line[22:26])
                try:
                    xyz = [float(line[30:38]), float(line[38:46]), float(line[46:54])]
                except Exception:
                    continue
                atom = {
                    "atom_index": atom_index,
                    "atom_name": atom_name,
                    "resn": resn,
                    "chain": chain,
                    "resi": resi,
                    "xyz": xyz,
                }
                protein_atoms.append(atom)
                if atom_name in ACID_SIDECHAIN_ATOMS.get(resn, set()):
                    acid_atoms.append(atom)
            elif line.startswith("HETATM"):
                resn = _text(line[17:20]).upper()
                if resn in EXCLUDED_NATIVE_LIGAND_RESN:
                    continue
                chain = _text(line[21:22])
                resi = _text(line[22:26])
                try:
                    xyz = [float(line[30:38]), float(line[38:46]), float(line[46:54])]
                except Exception:
                    continue
                het_groups.setdefault((resn, chain, resi), []).append(xyz)
    if not acid_atoms or not het_groups:
        return {"available": False, "reason": "acid_or_native_ligand_missing", "anchor_atom_indices": []}
    acid_xyz = np.asarray([atom["xyz"] for atom in acid_atoms], dtype=float)
    best: tuple[float, tuple[str, str, str], list[list[float]]] | None = None
    for group_key, coords in het_groups.items():
        if len(coords) < 5:
            continue
        lig_xyz = np.asarray(coords, dtype=float)
        min_dist = float(np.linalg.norm(acid_xyz[:, None, :] - lig_xyz[None, :, :], axis=2).min())
        if best is None or min_dist < best[0]:
            best = (min_dist, group_key, coords)
    if best is None:
        return {"available": False, "reason": "native_ligand_group_not_selected", "anchor_atom_indices": []}
    native_min_dist, native_ligand_key, native_ligand_coords = best
    native_ligand_xyz = np.asarray(native_ligand_coords, dtype=float)
    ranked_acids = sorted(
        [
            (
                float(np.linalg.norm(native_ligand_xyz - np.asarray(atom["xyz"], dtype=float), axis=1).min()),
                atom,
            )
            for atom in acid_atoms
        ],
        key=lambda item: (
            item[0],
            item[1]["resn"],
            item[1]["chain"],
            item[1]["resi"],
            item[1]["atom_name"],
        ),
    )
    anchor_residue = ranked_acids[0][1]
    anchor_atoms = [
        atom
        for atom in acid_atoms
        if atom["resn"] == anchor_residue["resn"]
        and atom["chain"] == anchor_residue["chain"]
        and atom["resi"] == anchor_residue["resi"]
    ]
    return {
        "available": True,
        "native_pdb": str(pdb_path),
        "native_ligand_resn": native_ligand_key[0],
        "native_ligand_chain": native_ligand_key[1],
        "native_ligand_resi": native_ligand_key[2],
        "native_ligand_min_acid_distance_A": native_min_dist,
        "anchor_resn": anchor_residue["resn"],
        "anchor_chain": anchor_residue["chain"],
        "anchor_resi": anchor_residue["resi"],
        "anchor_atom_names": [atom["atom_name"] for atom in anchor_atoms],
        "anchor_atom_indices": [int(atom["atom_index"]) for atom in anchor_atoms],
    }


def _pdb_static_anchor_coords(native_pdb: str | Path, template: dict[str, Any]) -> np.ndarray:
    pdb_path = _resolve(native_pdb)
    if not pdb_path.exists():
        return np.zeros((0, 3), dtype=np.float32)
    raw_indices = [int(idx) for idx in template.get("anchor_atom_indices", []) if int(idx) >= 0]
    if not raw_indices:
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
    if not coords:
        return np.zeros((0, 3), dtype=np.float32)
    arr = np.asarray(coords, dtype=np.float32)
    valid = [idx for idx in raw_indices if 0 <= idx < int(arr.shape[0])]
    return arr[valid, :] if valid else np.zeros((0, 3), dtype=np.float32)


def _atom_window_features(row: dict[str, Any], template_cache: dict[str, dict[str, Any]]) -> dict[str, Any]:
    target = _text(row.get("target"))
    ligand_id = _text(row.get("ligand_id"))
    native_pdb = _text(row.get("protein_structure_source_path"))
    trajectory_npz = _text(row.get("trajectory_npz"))
    base = {
        "target": target,
        "ligand_id": ligand_id,
        "class_a_atom_anchor_available": 0,
        "class_a_atom_anchor_reason": "",
        "class_a_atom_anchor_frame_count": 0,
        "class_a_atom_anchor_min_distance_A": "",
        "class_a_atom_anchor_p10_distance_A": "",
        "class_a_atom_anchor_mean_distance_A": "",
        "class_a_atom_anchor_contact_fraction_le_2p8A": "",
        "class_a_atom_anchor_contact_fraction_2p8_4p2A": "",
        "class_a_atom_anchor_contact_fraction_le_4A": "",
        "class_a_atom_anchor_contact_fraction_le_6A": "",
        "class_a_atom_anchor_template_residue": "",
        "class_a_atom_anchor_native_pdb": native_pdb,
        "class_a_atom_anchor_trajectory_npz": trajectory_npz,
    }
    if not native_pdb:
        return {**base, "class_a_atom_anchor_reason": "native_pdb_missing"}
    template = template_cache.get(native_pdb)
    if template is None:
        template = _parse_pdb_anchor_template(native_pdb)
        template_cache[native_pdb] = template
    if not template.get("available"):
        return {**base, "class_a_atom_anchor_reason": template.get("reason", "anchor_template_unavailable")}
    npz_path = _resolve(trajectory_npz) if trajectory_npz else None
    if npz_path is None or not npz_path.exists():
        return {**base, "class_a_atom_anchor_reason": "trajectory_npz_missing"}
    try:
        with np.load(str(npz_path), allow_pickle=False) as npz:
            ligand_frames = np.asarray(npz["ligand_frames"], dtype=float)
            protein_atom_frames = (
                np.asarray(npz["protein_atom_frames"], dtype=float)
                if "protein_atom_frames" in npz.files
                else np.zeros((0, 0, 3), dtype=float)
            )
            static_anchor_coords = (
                np.asarray(npz["ligand_backmapping_static_anchor_coords"], dtype=float)
                if "ligand_backmapping_static_anchor_coords" in npz.files
                else _pdb_static_anchor_coords(native_pdb, template).astype(float)
            )
    except Exception as exc:
        return {**base, "class_a_atom_anchor_reason": f"trajectory_npz_unreadable:{type(exc).__name__}"}
    anchor_indices = [
        int(idx)
        for idx in template.get("anchor_atom_indices", [])
        if protein_atom_frames.ndim == 3 and 0 <= int(idx) < protein_atom_frames.shape[1]
    ]
    if ligand_frames.size == 0:
        return {**base, "class_a_atom_anchor_reason": "ligand_or_anchor_frames_missing"}
    if protein_atom_frames.size and anchor_indices:
        anchor_frames = protein_atom_frames[:, anchor_indices, :]
        anchor_source = "protein_atom_frames"
    elif static_anchor_coords.size:
        anchor_static = np.asarray(static_anchor_coords, dtype=float)
        if anchor_static.ndim != 2 or anchor_static.shape[1] != 3:
            return {**base, "class_a_atom_anchor_reason": "ligand_or_anchor_frames_missing"}
        anchor_frames = np.repeat(anchor_static[None, :, :], int(ligand_frames.shape[0]), axis=0)
        anchor_source = "native_pdb_static_fallback"
    else:
        return {**base, "class_a_atom_anchor_reason": "ligand_or_anchor_frames_missing"}
    distances = np.linalg.norm(
        ligand_frames[:, :, None, :] - anchor_frames[:, None, :, :],
        axis=3,
    ).min(axis=(1, 2))
    return {
        **base,
        "class_a_atom_anchor_available": 1,
        "class_a_atom_anchor_reason": "ok",
        "class_a_atom_anchor_frame_count": int(len(distances)),
        "class_a_atom_anchor_min_distance_A": float(np.min(distances)),
        "class_a_atom_anchor_p10_distance_A": float(np.percentile(distances, 10)),
        "class_a_atom_anchor_mean_distance_A": float(np.mean(distances)),
        "class_a_atom_anchor_contact_fraction_le_2p8A": float(np.mean(distances <= 2.8)),
        "class_a_atom_anchor_contact_fraction_2p8_4p2A": float(
            np.mean((distances >= 2.8) & (distances <= 4.2))
        ),
        "class_a_atom_anchor_contact_fraction_le_4A": float(np.mean(distances <= 4.0)),
        "class_a_atom_anchor_contact_fraction_le_6A": float(np.mean(distances <= 6.0)),
        "class_a_atom_anchor_template_residue": (
            f"{template.get('anchor_resn', '')}{template.get('anchor_resi', '')}"
            f"{template.get('anchor_chain', '')}"
        ),
        "class_a_atom_anchor_source": anchor_source,
    }


def _positive_keys_from_labels(path_like: str | Path, *, target: str) -> set[tuple[str, str]]:
    path_text = _text(path_like)
    if not path_text:
        return set()
    path = _resolve(path_text)
    if not path.exists():
        raise FileNotFoundError(f"labels csv not found: {path}")
    keys: set[tuple[str, str]] = set()
    for row in _read_csv(path):
        if target and _text(row.get("target")) != target:
            continue
        is_binder = _text(row.get("is_binder")).lower() in {"1", "true", "t", "yes", "y"}
        if not is_binder:
            continue
        t = _text(row.get("target"))
        lig = _text(row.get("ligand_id"))
        if t and lig:
            keys.add((t, lig))
    return keys


def _selected_rows(
    rows: list[dict[str, str]],
    *,
    target: str,
    score_col: str,
    top_n: int,
    include_positives: bool,
    positive_keys: set[tuple[str, str]] | None = None,
) -> list[dict[str, str]]:
    positive_keys = positive_keys or set()
    filtered = [row for row in rows if not target or _text(row.get("target")) == target]
    if score_col:
        filtered = sorted(
            filtered,
            key=lambda row: (
                _float(row.get(score_col)) if _float(row.get(score_col)) is not None else float("inf"),
                _text(row.get("target")),
                _text(row.get("ligand_id")),
            ),
        )
    selected = filtered if top_n <= 0 else filtered[:top_n]
    if include_positives:
        seen = {(_text(row.get("target")), _text(row.get("ligand_id"))) for row in selected}
        for row in filtered:
            key = (_text(row.get("target")), _text(row.get("ligand_id")))
            row_is_binder = _text(row.get("is_binder")).lower() in {"1", "true", "t", "yes", "y"}
            if not (row_is_binder or key in positive_keys):
                continue
            if key in seen:
                continue
            selected.append(row)
            seen.add(key)
    return selected


def build_cache(
    *,
    input_csv: str | Path,
    labels_csv: str | Path = "",
    target: str = "",
    score_col: str = "binding_score_composite_v7",
    top_n: int = 64,
    include_positives: bool = True,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    input_path = _resolve(input_csv)
    rows = _read_csv(input_path)
    positive_keys = _positive_keys_from_labels(labels_csv, target=target) if labels_csv else set()
    selected = _selected_rows(
        rows,
        target=target,
        score_col=score_col,
        top_n=top_n,
        include_positives=include_positives,
        positive_keys=positive_keys,
    )
    template_cache: dict[str, dict[str, Any]] = {}
    out_rows = [_atom_window_features(row, template_cache) for row in selected]
    available = sum(1 for row in out_rows if int(row.get("class_a_atom_anchor_available") or 0) == 1)
    summary = {
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "input_csv": str(input_path),
        "labels_csv": str(_resolve(labels_csv)) if labels_csv else "",
        "target_filter": target,
        "score_col": score_col,
        "top_n": top_n,
        "include_positives": include_positives,
        "positive_label_key_count": len(positive_keys),
        "input_row_count": len(rows),
        "selected_row_count": len(selected),
        "available_feature_count": available,
        "missing_feature_count": len(out_rows) - available,
        "claim_promotion_allowed": False,
        "scorer_apply_allowed": False,
        "interpretation": (
            "Precomputed direct atom-window cache for claim-locked shadow replay only; "
            "missing rows are telemetry, not negative evidence."
        ),
    }
    return out_rows, summary


def _render_markdown(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# GPCR Atom-Window Anchor Feature Cache",
            "",
            f"- selected_row_count: `{summary['selected_row_count']}`",
            f"- available_feature_count: `{summary['available_feature_count']}`",
            f"- missing_feature_count: `{summary['missing_feature_count']}`",
            f"- positive_label_key_count: `{summary['positive_label_key_count']}`",
            f"- target_filter: `{summary['target_filter']}`",
            f"- claim_promotion_allowed: `{str(summary['claim_promotion_allowed']).lower()}`",
            f"- scorer_apply_allowed: `{str(summary['scorer_apply_allowed']).lower()}`",
            "",
            "This cache is for score-only shadow replay. It does not unlock GPCR router/platform claims.",
            "",
        ]
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a direct atom-window GPCR anchor feature cache.")
    parser.add_argument("--input-csv", default=DEFAULT_INPUT_CSV)
    parser.add_argument("--labels-csv", default="")
    parser.add_argument("--target", default="CHEMBL217_DRD2_HUMAN")
    parser.add_argument("--score-col", default="binding_score_composite_v7")
    parser.add_argument("--top-n", type=int, default=64)
    parser.add_argument("--include-positives", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows, summary = build_cache(
        input_csv=args.input_csv,
        labels_csv=args.labels_csv,
        target=args.target,
        score_col=args.score_col,
        top_n=int(args.top_n),
        include_positives=bool(args.include_positives),
    )
    out_csv = _resolve(args.out_csv)
    out_json = _resolve(args.out_json)
    out_md = _resolve(args.out_md)
    _write_csv(out_csv, rows)
    summary["out_csv"] = str(out_csv)
    _write_json(out_json, {"summary": summary, "rows": rows[:20]})
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(_render_markdown(summary), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
