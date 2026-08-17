from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "d1_materializer", ROOT / "tools/materialize_engine_v2_d1_case_results_v1.py"
)
assert SPEC is not None and SPEC.loader is not None
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


def source(case_id: str) -> dict:
    reference = [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
    candidates = []
    for slot in range(64):
        candidates.append({
            "slot_index": slot, "lane": "uniform", "status": "scored",
            "failure_code": None, "score": float(slot),
            "proposal_coordinates": reference, "final_coordinates": reference,
            "proposal_valid": True, "pose_valid": True,
        })
    return {
        "schema_id": M.ADAPTER_SOURCE, "case_id": case_id,
        "preparation_status": "success", "preparation_failure_code": None,
        "ligand_atom_count": 3,
        "reference_heavy_atom_coordinates": reference,
        "symmetry_permutations": [[0, 1, 2]],
        "candidates": candidates,
    }


def build(tmp_path: Path):
    root = tmp_path / "sources"
    root.mkdir()
    rows = []
    for i in range(32):
        case = f"D1_CASE_{i:03d}"
        name = f"{case}.json"
        (root / name).write_text(json.dumps(source(case)), encoding="utf-8")
        rows.append({"case_id": case, "source_path": name})
    manifest = tmp_path / "adapter.json"
    manifest.write_text(json.dumps({
        "schema_id": M.ADAPTER_MANIFEST, "profile_id": M.PROFILE_ID, "cases": rows,
    }), encoding="utf-8")
    fresh = tmp_path / "fresh.json"
    fresh.write_text(json.dumps({
        "schema_id": M.FRESH_SCHEMA,
        "case_ids": [f"FRESH_{i:03d}" for i in range(128)],
    }), encoding="utf-8")
    return root, manifest, fresh


def test_kabsch_rotation_and_translation() -> None:
    reference = np.array([[0., 0., 0.], [1., 0., 0.], [0., 1., 0.]])
    rotation = np.array([[0., -1., 0.], [1., 0., 0.], [0., 0., 1.]])
    candidate = reference @ rotation + np.array([5., -2., 3.])
    assert M.aligned_rmsd(candidate, reference) < 1e-12


def test_materializes_exact_32_by_64(tmp_path: Path) -> None:
    root, manifest, fresh = build(tmp_path)
    receipt = M.materialize(manifest, root, fresh, tmp_path / "out")
    assert receipt["case_count"] == 32
    result = json.loads((tmp_path / "out/D1_CASE_000.json").read_text())
    assert result["candidate_denominator"] == 64
    assert result["candidates"][0]["final_rmsd_angstrom"] < 1e-12
    assert receipt["authority"]["fresh_128_execution_authorized"] is False


def test_fresh_overlap_is_rejected(tmp_path: Path) -> None:
    root, manifest, fresh = build(tmp_path)
    value = json.loads(fresh.read_text())
    value["case_ids"][0] = "D1_CASE_000"
    fresh.write_text(json.dumps(value))
    with pytest.raises(M.MaterializationError, match="overlaps"):
        M.materialize(manifest, root, fresh, tmp_path / "out")


def test_missing_candidate_is_rejected(tmp_path: Path) -> None:
    root, manifest, fresh = build(tmp_path)
    path = root / "D1_CASE_000.json"
    value = json.loads(path.read_text())
    value["candidates"].pop()
    path.write_text(json.dumps(value))
    with pytest.raises(M.MaterializationError, match="64 candidate"):
        M.materialize(manifest, root, fresh, tmp_path / "out")
