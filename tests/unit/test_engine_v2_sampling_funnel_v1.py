from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "funnel", ROOT / "tools/run_engine_v2_sampling_funnel_v1.py"
)
assert SPEC is not None and SPEC.loader is not None
F = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(F)
PROFILE = ROOT / "config/engine_v2_sampling_funnel_v1.json"


def pool() -> dict:
    lanes = ["uniform_so3", "pocket_surface", "single_anchor", "multi_anchor"]
    rows = []
    for i in range(512):
        lane = lanes[i % 4]
        rows.append({
            "pool_index": i, "lane": lane, "status": "generated",
            "failure_code": None, "source_sha256": f"{i + 1:064x}",
            "proposal_sha256": f"{i + 513:064x}",
            "coordinate_sha256": f"{i + 1025:064x}",
            "minimum_vdw_ratio": 0.8, "pocket_escape_angstrom": 1.0,
            "shape_penalty": float(i % 17), "anchor_penalty": float(i % 11),
            "embedding": [float((i * (j + 3)) % 19) for j in range(7)],
        })
    return {
        "schema_id": F.INPUT_SCHEMA,
        "profile_id": "engine_v2_deterministic_512_to_64_funnel_v1",
        "candidates": rows,
    }


def save(tmp_path: Path, value: dict) -> Path:
    path = tmp_path / "input.json"
    path.write_text(json.dumps(value))
    return path


def test_exact_deterministic_512_to_64(tmp_path: Path) -> None:
    path = save(tmp_path, pool())
    first = F.run(PROFILE, path)
    second = F.run(PROFILE, path)
    assert len(first["observations"]) == 512
    assert len(first["selected_rows"]) == 64
    assert first["receipt_sha256"] == second["receipt_sha256"]
    assert first["authority"]["scientific_claim_authorized"] is False


def test_lane_shortfall_stays_in_output_denominator(tmp_path: Path) -> None:
    value = pool()
    for row in value["candidates"]:
        if row["lane"] == "multi_anchor":
            row.update({
                "status": "typed_failure", "failure_code": "feature_missing",
                "source_sha256": None, "proposal_sha256": None,
                "coordinate_sha256": None, "minimum_vdw_ratio": None,
                "pocket_escape_angstrom": None, "shape_penalty": None,
                "anchor_penalty": None, "embedding": None,
            })
    result = F.run(PROFILE, save(tmp_path, value))
    failed = [row for row in result["selected_rows"] if row["status"] == "typed_failure"]
    assert len(result["selected_rows"]) == 64
    assert len(failed) == 8
    assert {row["failure_code"] for row in failed} == {"lane_quota_unfilled"}


def test_hard_rejects_are_not_selected(tmp_path: Path) -> None:
    value = pool()
    value["candidates"][0]["minimum_vdw_ratio"] = 0.1
    result = F.run(PROFILE, save(tmp_path, value))
    assert result["observations"][0]["decision"] == "hard_reject_vdw"
    assert all(row["source_pool_index"] != 0 for row in result["selected_rows"])


def test_result_dependent_field_is_rejected(tmp_path: Path) -> None:
    value = pool()
    value["candidates"][0]["native_pose_rmsd"] = 0.0
    with pytest.raises(F.FunnelError, match="field set"):
        F.run(PROFILE, save(tmp_path, value))
