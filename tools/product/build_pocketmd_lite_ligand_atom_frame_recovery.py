#!/usr/bin/env python3
"""Recover PocketMD Lite ligand atom frame candidate NPZs from top-k inputs.

This is a local artifact builder, not a claim promoter. It uses RDKit ETKDG
heavy-atom conformers and a two-point Kabsch fit to map ligand heavy atoms onto
the existing PocketMD Lite two-bead trajectory frames. When a matching
trajectory already contains protein atom frames, or a local protein PDB can
provide static heavy-atom frames in the same source lane, the output NPZ becomes
a candidate input for the follow-on local-min/H-bond/clash metric collector.
The recovered frames are provenance-tagged and are not final claim-grade
metrics by themselves.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import re
from pathlib import Path
from typing import Any

import numpy as np

try:  # pragma: no cover - exercised in tests when RDKit is available.
    from rdkit import Chem  # type: ignore
    from rdkit.Chem import AllChem  # type: ignore
except Exception:  # pragma: no cover
    Chem = None  # type: ignore
    AllChem = None  # type: ignore

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_INPUT_CSV = "runs/pocketmd_lite_metric_collection_input_pack_current.csv"
DEFAULT_OUT_ROOT = "runs/pocketmd_lite_ligand_atom_frame_recovery_current"
DEFAULT_OUT_JSON = "runs/pocketmd_lite_ligand_atom_frame_recovery_current.json"
DEFAULT_OUT_MD = "runs/pocketmd_lite_ligand_atom_frame_recovery_current.md"
DEFAULT_OUT_CSV = "runs/pocketmd_lite_ligand_atom_frame_recovery_current.csv"
DEFAULT_SEARCH_ROOTS = (
    "runs/residual_force_trajectory_regeneration_current",
    "~/.local/share/Trash/files/trajectory_spill",
    "/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs",
)
MAX_CANDIDATE_PATHS_PER_ROW = 24

PACKET_TYPE = "pocketmd_lite_ligand_atom_frame_recovery"
SCHEMA_VERSION = "pocketmd_lite_ligand_atom_frame_recovery_v1"
FRAME_SOURCE = "rdkit_etkdg_heavy_atom_two_bead_kabsch_candidate"
PROTEIN_FRAME_SOURCE = "protein_structure_source_pdb_static_heavy_atom_frames"

CLAIM_BOUNDARY = (
    "PocketMD Lite ligand atom frame recovery builds local candidate NPZs from selected top-k two-bead "
    "trajectories, ligand SMILES, and available local protein PDB sources. The recovered ligand heavy-atom "
    "frames and static protein heavy-atom frames are provenance-tagged candidate inputs for the subsequent "
    "local-min/H-bond/clash collector; they are not final claim-grade refinement metrics, do not mutate the "
    "canonical candidate CSV, and do not promote PocketMD Lite claims."
)

LOCAL_FLAGS = {
    "external_state_mutated": False,
    "candidate_csv_update_allowed": False,
    "claim_promotion_allowed": False,
    "refinement_execution_enabled": False,
}

CSV_COLUMNS = [
    "entry_id",
    "target",
    "ligand_id",
    "status",
    "source_npz",
    "out_npz",
    "frame_count",
    "ligand_bead_count",
    "ligand_atom_count",
    "protein_atom_frame_count",
    "collection_input_candidate_ready",
    "ligand_atom_frame_source",
    "protein_atom_frame_source",
    "anchor_atom_indices",
    "blockers",
    "recommended_next_local_action",
    "external_state_mutated",
    "candidate_csv_update_allowed",
    "claim_promotion_allowed",
    "refinement_execution_enabled",
]

ELEMENT_TO_ATOMIC_NUMBER = {
    "H": 1,
    "C": 6,
    "N": 7,
    "O": 8,
    "F": 9,
    "P": 15,
    "S": 16,
    "CL": 17,
    "BR": 35,
    "I": 53,
}


def _resolve(path_like: str | Path) -> Path:
    path = Path(str(path_like)).expanduser()
    return path if path.is_absolute() else ROOT / path


def _display(path_like: str | Path) -> str:
    text = _text(path_like)
    if not text:
        return ""
    path = Path(text)
    if path.is_absolute():
        try:
            return str(path.relative_to(ROOT))
        except ValueError:
            return str(path)
    return text


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _bool(value: Any) -> bool:
    return _text(value).lower() in {"1", "true", "yes", "y", "on"}


def _read_csv(path_like: str | Path) -> list[dict[str, Any]]:
    path = _resolve(path_like)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _search_roots(values: list[str | Path] | tuple[str | Path, ...] | None) -> list[Path]:
    roots = values if values is not None else DEFAULT_SEARCH_ROOTS
    out: list[Path] = []
    for value in roots:
        text = _text(value)
        if not text:
            continue
        path = _resolve(text)
        if path not in out:
            out.append(path)
    return out


def _candidate_path_matches(path: Path, target: str, ligand_id: str) -> bool:
    text = str(path).lower()
    target_variants = {target.lower(), target.lower().replace("-", "_")}
    ligand_variants = {ligand_id.lower(), ligand_id.lower().replace("-", "_")}
    return any(part in text for part in target_variants) and any(part in text for part in ligand_variants)


def _find_matching_npzs(row: dict[str, Any], search_roots: list[Path]) -> list[str]:
    target = _text(row.get("target"))
    ligand_id = _text(row.get("ligand_id"))
    selected = _text(row.get("selected_trajectory_npz"))
    paths: list[str] = []
    if selected:
        paths.append(_display(selected))
    if not target or not ligand_id:
        return paths
    for root in search_roots:
        if not root.exists() or not root.is_dir():
            continue
        try:
            iterator = root.rglob("*.npz")
        except OSError:
            continue
        for path in iterator:
            try:
                if not path.is_file() or not _candidate_path_matches(path, target, ligand_id):
                    continue
            except OSError:
                continue
            display = _display(path)
            if display not in paths:
                paths.append(display)
            if len(paths) >= MAX_CANDIDATE_PATHS_PER_ROW:
                return paths
    return paths


def _load_npz(path_like: str | Path) -> tuple[dict[str, np.ndarray] | None, str]:
    path = _resolve(path_like)
    if not _text(path_like) or not path.exists():
        return None, "source_npz_missing"
    try:
        with np.load(str(path), allow_pickle=False) as payload:
            return {key: np.asarray(payload[key]) for key in payload.files}, "ok"
    except Exception as exc:
        return None, f"source_npz_unreadable:{type(exc).__name__}"


def _valid_ligand_frames(arrays: dict[str, np.ndarray]) -> np.ndarray | None:
    frames = np.asarray(arrays.get("ligand_frames", np.zeros((0, 0, 3), dtype=np.float32)), dtype=np.float32)
    if frames.ndim == 3 and frames.shape[0] > 0 and frames.shape[1] >= 2 and frames.shape[2] == 3:
        return frames
    return None


def _protein_atom_frame_count(arrays: dict[str, np.ndarray]) -> int:
    frames = np.asarray(arrays.get("protein_atom_frames", np.zeros((0, 0, 3), dtype=np.float32)))
    if frames.ndim == 3 and frames.shape[0] > 0 and frames.shape[1] > 0 and frames.shape[2] == 3:
        return int(frames.shape[1])
    return 0


def _pdb_element(line: str) -> str:
    element = line[76:78].strip().upper()
    if element:
        return element
    atom_name = "".join(part for part in line[12:16].strip().upper() if part.isalpha())
    if atom_name[:2] in {"CL", "BR"}:
        return atom_name[:2]
    if atom_name[:1] in {"C", "N", "O", "P", "S", "F", "I", "H"}:
        return atom_name[:1]
    return "C"


def _protein_atom_frames_from_pdb(
    path_like: str | Path,
    *,
    frame_count: int,
) -> tuple[dict[str, np.ndarray], list[str]]:
    path_text = _text(path_like)
    if not path_text:
        return {}, ["protein_structure_source_path_missing"]
    path = _resolve(path_text)
    if not path.exists():
        return {}, ["protein_structure_source_path_unavailable"]

    coords: list[list[float]] = []
    elements: list[str] = []
    atomic_numbers: list[int] = []
    model_seen = False
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError as exc:
        return {}, [f"protein_structure_source_path_unreadable:{type(exc).__name__}"]

    for line in lines:
        if line.startswith("MODEL"):
            if model_seen:
                break
            model_seen = True
            continue
        if line.startswith("ENDMDL"):
            break
        if not line.startswith("ATOM"):
            continue
        element = _pdb_element(line)
        if element == "H":
            continue
        try:
            coord = [float(line[30:38]), float(line[38:46]), float(line[46:54])]
        except ValueError:
            continue
        coords.append(coord)
        elements.append(element)
        atomic_numbers.append(ELEMENT_TO_ATOMIC_NUMBER.get(element, 6))

    if not coords:
        return {}, ["protein_structure_source_pdb_no_heavy_atoms"]
    base = np.asarray(coords, dtype=np.float32)
    frames = np.repeat(base.reshape(1, base.shape[0], 3), int(frame_count), axis=0)
    return (
        {
            "protein_atom_frames": frames.astype(np.float32, copy=False),
            "protein_atom_atomic_numbers": np.asarray(atomic_numbers, dtype=np.int16),
            "protein_atom_elements": np.asarray(elements, dtype="<U2"),
            "protein_atom_frame_source": np.asarray(PROTEIN_FRAME_SOURCE),
            "protein_atom_frame_static_pdb_source_path": np.asarray(_display(path)),
            "protein_atom_frame_claim_grade_metric_evidence": np.asarray(False),
        },
        [],
    )


def _rank_npz(path: str) -> tuple[int, int, int]:
    arrays, reason = _load_npz(path)
    if arrays is None:
        return (0, 0, 0)
    ligand = _valid_ligand_frames(arrays)
    if ligand is None:
        return (0, 0, 0)
    protein_atoms = _protein_atom_frame_count(arrays)
    ligand_atom_frames = np.asarray(arrays.get("ligand_atom_frames", np.zeros((0, 0, 3), dtype=np.float32)))
    ligand_atoms = (
        int(ligand_atom_frames.shape[1])
        if ligand_atom_frames.ndim == 3 and ligand_atom_frames.shape[1] > 2
        else 0
    )
    readable_rank = 2 if reason == "ok" else 1
    return (readable_rank + (4 if protein_atoms else 0) + (8 if ligand_atoms else 0), int(ligand.shape[0]), protein_atoms)


def _best_source_npz(row: dict[str, Any], search_roots: list[Path]) -> str:
    candidates = _find_matching_npzs(row, search_roots)
    return max(candidates, key=_rank_npz, default=_display(row.get("selected_trajectory_npz")))


def _safe_name(entry_id: str, target: str, ligand_id: str) -> str:
    base = entry_id or f"{target}:{ligand_id}"
    base = base.replace(":", "__")
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", base).strip("_") or "pocketmd_lite_entry"


def _heavy_conformer(smiles: str) -> tuple[np.ndarray | None, list[int], list[str], str]:
    if Chem is None or AllChem is None:
        return None, [], [], "rdkit_unavailable"
    mol = Chem.MolFromSmiles(_text(smiles))
    if mol is None:
        return None, [], [], "invalid_smiles"
    try:
        mol_h = Chem.AddHs(mol)
        params = AllChem.ETKDGv3()
        params.randomSeed = 0x504D44
        if AllChem.EmbedMolecule(mol_h, params) != 0:
            return None, [], [], "rdkit_embed_failed"
        try:
            AllChem.UFFOptimizeMolecule(mol_h, maxIters=200)
        except Exception:
            pass
        conf = mol_h.GetConformer()
        coords: list[list[float]] = []
        atomic_numbers: list[int] = []
        elements: list[str] = []
        for atom in mol_h.GetAtoms():
            atomic = int(atom.GetAtomicNum())
            if atomic <= 1:
                continue
            pos = conf.GetAtomPosition(int(atom.GetIdx()))
            coords.append([float(pos.x), float(pos.y), float(pos.z)])
            atomic_numbers.append(atomic)
            elements.append(str(atom.GetSymbol()))
        if len(coords) <= 2:
            return None, [], [], "ligand_heavy_atom_count_too_small"
        return np.asarray(coords, dtype=np.float32), atomic_numbers, elements, "ok"
    except Exception as exc:
        return None, [], [], f"rdkit_conformer_failed:{type(exc).__name__}"


def _anchor_indices(coords: np.ndarray) -> tuple[int, int]:
    d = np.linalg.norm(coords[:, None, :] - coords[None, :, :], axis=2)
    flat_index = int(np.argmax(d))
    i, j = np.unravel_index(flat_index, d.shape)
    if i == j:
        return 0, int(min(1, coords.shape[0] - 1))
    return int(i), int(j)


def _kabsch(mobile: np.ndarray, target: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mobile_c = mobile - mobile.mean(axis=0, keepdims=True)
    target_c = target - target.mean(axis=0, keepdims=True)
    h = mobile_c.T @ target_c
    u, _s, vt = np.linalg.svd(h)
    r = vt.T @ u.T
    if np.linalg.det(r) < 0:
        vt[-1, :] *= -1.0
        r = vt.T @ u.T
    t = target.mean(axis=0) - (r @ mobile.mean(axis=0))
    return r.astype(np.float32), t.astype(np.float32)


def _map_heavy_atoms_to_frames(coords: np.ndarray, ligand_frames: np.ndarray, anchors: tuple[int, int]) -> np.ndarray:
    mobile = coords[[anchors[0], anchors[1]], :]
    mapped: list[np.ndarray] = []
    for frame in ligand_frames:
        rot, trans = _kabsch(mobile, np.asarray(frame[:2], dtype=np.float32))
        mapped.append(((rot @ coords.T).T + trans).astype(np.float32, copy=False))
    return np.stack(mapped, axis=0).astype(np.float32, copy=False)


def _recover_row(row: dict[str, Any], *, out_root: Path, search_roots: list[Path]) -> dict[str, Any]:
    entry_id = _text(row.get("entry_id"))
    target = _text(row.get("target"))
    ligand_id = _text(row.get("ligand_id"))
    smiles = _text(row.get("ligand_smiles"))
    source_npz = _best_source_npz(row, search_roots)
    out_npz = out_root / f"{_safe_name(entry_id, target, ligand_id)}__ligand_atom_recovery.npz"
    base: dict[str, Any] = {
        "entry_id": entry_id,
        "target": target,
        "ligand_id": ligand_id,
        "status": "blocked_ligand_atom_frame_recovery",
        "source_npz": _display(source_npz),
        "out_npz": _display(out_npz),
        "frame_count": 0,
        "ligand_bead_count": 0,
        "ligand_atom_count": 0,
        "protein_atom_frame_count": 0,
        "collection_input_candidate_ready": False,
        "ligand_atom_frame_source": "",
        "protein_atom_frame_source": "",
        "anchor_atom_indices": [],
        "blockers": [],
        "recommended_next_local_action": "restore_or_regenerate_readable_two_bead_trajectory",
        **LOCAL_FLAGS,
    }
    arrays, reason = _load_npz(source_npz)
    if arrays is None:
        return {**base, "blockers": [reason]}
    ligand_frames = _valid_ligand_frames(arrays)
    if ligand_frames is None:
        return {**base, "blockers": ["ligand_frames_invalid_or_missing"]}
    base["frame_count"] = int(ligand_frames.shape[0])
    base["ligand_bead_count"] = int(ligand_frames.shape[1])
    base["protein_atom_frame_count"] = _protein_atom_frame_count(arrays)
    if not smiles:
        return {**base, "blockers": ["ligand_smiles_missing"]}

    coords, atomic_numbers, elements, conformer_status = _heavy_conformer(smiles)
    if coords is None:
        return {**base, "blockers": [conformer_status]}
    anchors = _anchor_indices(coords)
    ligand_atom_frames = _map_heavy_atoms_to_frames(coords, ligand_frames, anchors)
    if not np.isfinite(ligand_atom_frames).all():
        return {**base, "blockers": ["ligand_atom_frames_nonfinite"]}

    out_npz.parent.mkdir(parents=True, exist_ok=True)
    output_arrays: dict[str, Any] = dict(arrays)
    protein_frame_source = ""
    protein_frame_blockers: list[str] = []
    if _protein_atom_frame_count(output_arrays) <= 0:
        protein_frames, protein_frame_blockers = _protein_atom_frames_from_pdb(
            row.get("protein_structure_source_path"),
            frame_count=int(ligand_atom_frames.shape[0]),
        )
        if protein_frames:
            output_arrays.update(protein_frames)
            protein_frame_source = PROTEIN_FRAME_SOURCE
    else:
        protein_frame_source = _text(output_arrays.get("protein_atom_frame_source")) or "source_npz_protein_atom_frames"

    output_arrays.update(
        {
            "ligand_atom_frames": ligand_atom_frames,
            "ligand_heavy_atom_frames": ligand_atom_frames,
            "ligand_atom_atomic_numbers": np.asarray(atomic_numbers, dtype=np.int16),
            "ligand_atom_elements": np.asarray(elements, dtype="<U3"),
            "ligand_backmapping_anchor_atom_indices": np.asarray(anchors, dtype=np.int32),
            "ligand_atom_frame_source": np.asarray(FRAME_SOURCE),
            "ligand_atom_frame_claim_grade_metric_evidence": np.asarray(False),
            "pocketmd_lite_ligand_atom_frame_recovery_schema_version": np.asarray(SCHEMA_VERSION),
        }
    )
    np.savez(out_npz, **output_arrays)

    blockers: list[str] = []
    protein_atom_frame_count = _protein_atom_frame_count(output_arrays)
    if protein_atom_frame_count <= 0:
        blockers.extend(["protein_atom_frames_missing", *protein_frame_blockers])
    collection_ready = not blockers
    return {
        **base,
        "status": (
            "pocketmd_lite_ligand_atom_frame_recovery_collection_input_ready"
            if collection_ready
            else "pocketmd_lite_ligand_atom_frame_recovery_ligand_only_protein_atom_missing"
        ),
        "ligand_atom_count": int(ligand_atom_frames.shape[1]),
        "protein_atom_frame_count": int(protein_atom_frame_count),
        "collection_input_candidate_ready": collection_ready,
        "ligand_atom_frame_source": FRAME_SOURCE,
        "protein_atom_frame_source": protein_frame_source,
        "anchor_atom_indices": [int(anchors[0]), int(anchors[1])],
        "blockers": blockers,
        "recommended_next_local_action": (
            "run_claim_grade_metric_collector_for_recovered_atomized_input"
            if collection_ready
            else "recover_or_generate_protein_atom_frames_then_run_claim_grade_metric_collector"
        ),
    }


def build_pocketmd_lite_ligand_atom_frame_recovery(
    *,
    input_csv: str | Path = DEFAULT_INPUT_CSV,
    out_root: str | Path = DEFAULT_OUT_ROOT,
    search_roots: list[str | Path] | tuple[str | Path, ...] | None = None,
) -> dict[str, Any]:
    input_path = _resolve(input_csv)
    root = _resolve(out_root)
    roots = _search_roots(search_roots)
    source_rows = [row for row in _read_csv(input_path) if _bool(row.get("collection_input_ready"))]
    rows = [_recover_row(row, out_root=root, search_roots=roots) for row in source_rows]

    generated_count = sum(1 for row in rows if _text(row.get("ligand_atom_frame_source")) == FRAME_SOURCE)
    collection_ready_count = sum(1 for row in rows if row.get("collection_input_candidate_ready") is True)
    protein_missing_count = sum(1 for row in rows if "protein_atom_frames_missing" in row.get("blockers", []))
    if rows and collection_ready_count == len(rows):
        status = "pocketmd_lite_ligand_atom_frame_recovery_ready"
    elif generated_count:
        status = "pocketmd_lite_ligand_atom_frame_recovery_partial_ready"
    elif rows:
        status = "blocked_pocketmd_lite_ligand_atom_frame_recovery"
    else:
        status = "blocked_pocketmd_lite_ligand_atom_frame_recovery_no_inputs"

    summary = {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": status,
        "input_csv": _display(input_path),
        "out_root": _display(root),
        "candidate_count": len(rows),
        "ligand_atom_frame_generated_count": generated_count,
        "collection_input_candidate_ready_count": collection_ready_count,
        "protein_atom_frame_missing_count": protein_missing_count,
        "rdkit_available": Chem is not None and AllChem is not None,
        "ligand_atom_frame_source": FRAME_SOURCE,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Run the claim-grade metric collector for every recovered collection-ready top-k input."
            if rows and collection_ready_count == len(rows)
            else "Run the metric collector for recovered collection-ready rows and recover protein atom frames for the remaining top-k rows."
            if collection_ready_count
            else "Recover or generate protein atom frames and ligand atom frames for the selected top-k rows."
        ),
        **LOCAL_FLAGS,
    }
    return {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "summary": summary,
        "rows": rows,
        "claim_boundary": CLAIM_BOUNDARY,
    }


def _jsonable(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return _jsonable(value.tolist())
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _fmt(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, float):
        return f"{value:.6g}"
    if isinstance(value, list):
        return ";".join(str(item) for item in value)
    return str(value)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_jsonable(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: _fmt(row.get(column)) for column in CSV_COLUMNS})


def _render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# PocketMD Lite Ligand Atom Frame Recovery",
        "",
        f"- status: `{summary['status']}`",
        f"- candidate_count: `{summary['candidate_count']}`",
        f"- ligand_atom_frame_generated_count: `{summary['ligand_atom_frame_generated_count']}`",
        f"- collection_input_candidate_ready_count: `{summary['collection_input_candidate_ready_count']}`",
        f"- protein_atom_frame_missing_count: `{summary['protein_atom_frame_missing_count']}`",
        "",
        "| entry | status | ligand atoms | protein atom frames | collection ready | action |",
        "| --- | --- | ---: | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            "| `{entry}` | `{status}` | {ligand_atoms} | {protein_atoms} | `{ready}` | `{action}` |".format(
                entry=row["entry_id"],
                status=row["status"],
                ligand_atoms=row["ligand_atom_count"],
                protein_atoms=row["protein_atom_frame_count"],
                ready=row["collection_input_candidate_ready"],
                action=row["recommended_next_local_action"],
            )
        )
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-csv", default=DEFAULT_INPUT_CSV)
    parser.add_argument("--out-root", default=DEFAULT_OUT_ROOT)
    parser.add_argument("--search-root", action="append", default=None)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    args = parser.parse_args(argv)

    payload = build_pocketmd_lite_ligand_atom_frame_recovery(
        input_csv=args.input_csv,
        out_root=args.out_root,
        search_roots=args.search_root,
    )
    out_json = _resolve(args.out_json)
    out_md = _resolve(args.out_md)
    out_csv = _resolve(args.out_csv)
    _write_json(out_json, payload)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(_render_markdown(payload), encoding="utf-8")
    _write_csv(out_csv, payload["rows"])
    print(json.dumps(_jsonable(payload["summary"]), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
