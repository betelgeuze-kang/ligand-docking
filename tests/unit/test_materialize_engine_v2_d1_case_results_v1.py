from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "d1_materializer",
    ROOT / "tools/materialize_engine_v2_d1_case_results_v1.py",
)
assert SPEC is not None and SPEC.loader is not None
MATERIALIZER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MATERIALIZER)


def _source(case_id: str) -> dict:
    reference = [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
    candidates = []
    for slot in range(64):
        candidates.append(
            {
                "slot_index": slot,
                "lane": "uniform",
                "status": "scored",
                "failure_code": None,
                "score": float(slot),
                "proposal_coordinates": reference,
                "final_coordinates": reference,
                "proposal_valid": True,
                "pose_valid": True,
            }
        )
    return {
        "schema_id": MATERIALIZER.ADAPTER_SOURCE,
        "case_id": case_id,
        "preparation_status": "success",
        "preparation_failure_code": None,
        "ligand_atom_count": 3,
        "reference_heavy_atom_coordinates": reference,
        "symmetry_permutations": [[0, 1, 2]],
        "candidates": candidates,
    }


def _build(tmp_path: Path) -> tuple[Path, Path, Path]:
    source_root = tmp_path / "sources"
    source_root.mkdir()
    rows = []
    for index in range(32):
        case_id = f"D1_CASE_{index:03d}"
        name = f"{case_id}.json"
        (source_root / name).write_text(
            json.dumps(_source(case_id)), encoding="utf-8"
        )
        rows.append({"case_id": case_id, "source_path": name})
    manifest = tmp_path / "adapter.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_id": MATERIALIZER.ADAPTER_MANIFEST,
                "profile_id": MATERIALIZER.PROFILE_ID,
                "cases": rows,
            }
        ),
        encoding="utf-8",
    )
    fresh = tmp_path / "fresh.json"
    fresh.write_text(
        json.dumps(
            {
                "schema_id": MATERIALIZER.FRESH_SCHEMA,
                "case_ids": [f"FRESH_{index:03d}" for index in range(128)],
            }
        ),
        encoding="utf-8",
    )
    return source_root, manifest, fresh


def test_kabsch_removes_rigid_rotation_and_translation() -> None:
    reference = np.array(
        [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
    )
    rotation = np.array(
        [[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]]
    )
    candidate = reference @ rotation + np.array([5.0, -2.0, 3.0])
    assert MATERIALIZER.aligned_rmsd(candidate, reference) < 1.0e-12


def test_materializes_exact_32_by_64(tmp_path: Path) -> None:
    source_root, manifest, fresh = _build(tmp_path)
    receipt = MATERIALIZER.materialize(
        manifest, source_root, fresh, tmp_path / "out"
    )
    assert receipt["case_count"] == 32
    result = json.loads(
        (tmp_path / "out/D1_CASE_000.json").read_text(encoding="ascii")
    )
    assert result["candidate_denominator"] == 64
    assert result["candidates"][0]["final_rmsd_angstrom"] < 1.0e-12
    assert receipt["authority"]["fresh_128_execution_authorized"] is False


def test_fresh_overlap_is_rejected(tmp_path: Path) -> None:
    source_root, manifest, fresh = _build(tmp_path)
    value = json.loads(fresh.read_text(encoding="utf-8"))
    value["case_ids"][0] = "D1_CASE_000"
    fresh.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(MATERIALIZER.MaterializationError, match="overlaps"):
        MATERIALIZER.materialize(manifest, source_root, fresh, tmp_path / "out")


def test_missing_candidate_is_rejected(tmp_path: Path) -> None:
    source_root, manifest, fresh = _build(tmp_path)
    path = source_root / "D1_CASE_000.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    value["candidates"].pop()
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(MATERIALIZER.MaterializationError, match="64 candidate"):
        MATERIALIZER.materialize(manifest, source_root, fresh, tmp_path / "out")


def test_failed_candidate_cannot_carry_coordinates(tmp_path: Path) -> None:
    source_root, manifest, fresh = _build(tmp_path)
    path = source_root / "D1_CASE_000.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    value["candidates"][0].update(
        {"status": "typed_failure", "failure_code": "source_missing"}
    )
    with pytest.raises(
        MATERIALIZER.MaterializationError, match="failed candidate contains"
    ):
        MATERIALIZER._materialize_case(
            _write_temporary(path, value), "D1_CASE_000"
        )


def _write_temporary(path: Path, value: dict) -> Path:
    path.write_text(json.dumps(value), encoding="utf-8")
    return path
