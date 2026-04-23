#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Any, Dict, List, Tuple

import numpy as np


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FIXTURE_DIR = os.path.join(REPO_ROOT, "runs", "synthetic_protein_atom_frames_fixture_current")
BUNDLE_JSON = os.path.join(FIXTURE_DIR, "synthetic_protein_atom_fixture_bundle.json")
SMOKE_JSON = os.path.join(FIXTURE_DIR, "synthetic_protein_atom_fixture_smoke_current.json")


def _web_to_abs(path: str) -> str:
    text = str(path or "").strip()
    if not text:
        return ""
    if text.startswith("/"):
        return os.path.join(REPO_ROOT, text.lstrip("/"))
    return os.path.abspath(os.path.join(REPO_ROOT, text))


def _count_protein_atoms_in_pdb(path: str) -> int:
    count = 0
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if not line.startswith("ATOM"):
                continue
            count += 1
    return count


def _check(condition: bool, name: str, details: str, failures: List[Dict[str, str]]) -> None:
    if condition:
        return
    failures.append({"check": name, "details": details})


def main() -> int:
    build = subprocess.run(
        [sys.executable, os.path.join(REPO_ROOT, "tools", "build_synthetic_protein_atom_frames_fixture.py")],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    build_info = json.loads(build.stdout)

    with open(BUNDLE_JSON, "r", encoding="utf-8") as f:
        bundle = json.load(f)
    summary = bundle.get("summary", {})
    rows = bundle.get("rows", [])

    failures: List[Dict[str, str]] = []
    _check(bool(rows), "bundle_rows_present", "bundle rows is empty", failures)
    _check(len(rows) == 1, "bundle_single_row", f"expected 1 row, got {len(rows)}", failures)
    row = rows[0] if rows else {}

    trajectory_abs = _web_to_abs(row.get("trajectory_npz") or summary.get("primary_trajectory_npz"))
    structure_abs = _web_to_abs(
        row.get("protein_reference_aligned_viewer_path")
        or summary.get("primary_protein_reference_aligned_viewer_path")
    )

    _check(os.path.isfile(trajectory_abs), "trajectory_npz_exists", trajectory_abs, failures)
    _check(os.path.isfile(structure_abs), "protein_reference_pdb_exists", structure_abs, failures)

    protein_atom_count = _count_protein_atoms_in_pdb(structure_abs) if os.path.isfile(structure_abs) else 0
    npz = np.load(trajectory_abs) if os.path.isfile(trajectory_abs) else None

    frame_count = 0
    ligand_frame_count = 0
    atom_shape: Tuple[int, ...] = tuple()
    template_index_len = 0
    atom_schema_version = None
    if npz is not None:
        required_keys = {
            "protein_ca",
            "ligand_frames",
            "frame_indices",
            "protein_atom_frames",
            "protein_atom_template_index",
            "protein_atom_schema_version",
        }
        for key in sorted(required_keys):
            _check(key in npz.files, f"npz_key_{key}", f"missing key: {key}", failures)
        if "protein_atom_frames" in npz.files:
            atom_shape = tuple(int(v) for v in np.asarray(npz["protein_atom_frames"]).shape)
            _check(len(atom_shape) == 3 and atom_shape[2] == 3, "protein_atom_frames_shape", str(atom_shape), failures)
            frame_count = int(atom_shape[0]) if len(atom_shape) >= 1 else 0
        if "ligand_frames" in npz.files:
            ligand_shape = tuple(int(v) for v in np.asarray(npz["ligand_frames"]).shape)
            ligand_frame_count = int(ligand_shape[0]) if len(ligand_shape) >= 1 else 0
            _check(len(ligand_shape) == 3 and ligand_shape[2] == 3, "ligand_frames_shape", str(ligand_shape), failures)
        if "frame_indices" in npz.files:
            index_shape = tuple(int(v) for v in np.asarray(npz["frame_indices"]).shape)
            _check(len(index_shape) == 1, "frame_indices_shape", str(index_shape), failures)
            if frame_count:
                _check(index_shape[0] == frame_count, "frame_indices_match_frames", f"{index_shape[0]} vs {frame_count}", failures)
        if "protein_atom_template_index" in npz.files:
            template_index = np.asarray(npz["protein_atom_template_index"])
            template_index_len = int(template_index.shape[0]) if template_index.ndim == 1 else 0
            _check(template_index.ndim == 1, "protein_atom_template_index_shape", str(template_index.shape), failures)
            if frame_count and len(atom_shape) >= 2:
                _check(template_index_len == atom_shape[1], "template_index_match_atom_count", f"{template_index_len} vs {atom_shape[1]}", failures)
                expected = np.arange(template_index_len, dtype=np.int32)
                _check(np.array_equal(template_index.astype(np.int32, copy=False), expected), "template_index_identity_map", "template index is not 0..A-1", failures)
        if "protein_atom_schema_version" in npz.files:
            atom_schema_version = int(np.asarray(npz["protein_atom_schema_version"]).reshape(-1)[0])
            _check(atom_schema_version == 1, "protein_atom_schema_version_is_1", str(atom_schema_version), failures)

    if frame_count:
        _check(frame_count == ligand_frame_count, "protein_frames_match_ligand_frames", f"{frame_count} vs {ligand_frame_count}", failures)
    if len(atom_shape) >= 2:
        _check(atom_shape[1] == protein_atom_count, "pdb_atom_count_match_npz", f"{protein_atom_count} vs {atom_shape[1]}", failures)

    report: Dict[str, Any] = {
        "status": "pass" if not failures else "fail",
        "build_info": build_info,
        "bundle_json": BUNDLE_JSON,
        "trajectory_npz": trajectory_abs,
        "protein_reference_pdb": structure_abs,
        "protein_atom_count_from_pdb": int(protein_atom_count),
        "protein_atom_frames_shape": list(atom_shape),
        "ligand_frame_count": int(ligand_frame_count),
        "template_index_len": int(template_index_len),
        "protein_atom_schema_version": atom_schema_version,
        "viewer_manual_smoke": {
            "viewer_url": "http://127.0.0.1:8765/viewer/index.html",
            "bundle_url": build_info.get("viewer_bundle_url", ""),
            "expected_ui_signal": "Protein Trajectory should show full motion ready and not schema missing.",
        },
        "failure_count": len(failures),
        "failures": failures,
    }
    os.makedirs(FIXTURE_DIR, exist_ok=True)
    with open(SMOKE_JSON, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
