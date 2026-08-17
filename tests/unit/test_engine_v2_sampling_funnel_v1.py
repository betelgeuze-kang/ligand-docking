from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "engine_v2_sampling_funnel_v1",
    ROOT / "tools/run_engine_v2_sampling_funnel_v1.py",
)
assert SPEC is not None and SPEC.loader is not None
FUNNEL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FUNNEL)
PROFILE = ROOT / "config/engine_v2_sampling_funnel_v1.json"


def _pool() -> dict:
    lanes = ["uniform_so3", "pocket_surface", "single_anchor", "multi_anchor"]
    rows = []
    for index in range(512):
        lane = lanes[index % len(lanes)]
        rows.append(
            {
                "pool_index": index,
                "lane": lane,
                "status": "generated",
                "failure_code": None,
                "source_sha256": f"{index + 1:064x}",
                "proposal_sha256": f"{index + 513:064x}",
                "coordinate_sha256": f"{index + 1025:064x}",
                "minimum_vdw_ratio": 0.8,
                "pocket_escape_angstrom": 1.0,
                "shape_penalty": float(index % 17),
                "anchor_penalty": float(index % 11),
                "embedding": [
                    float((index * (dimension + 3)) % 19)
                    for dimension in range(7)
                ],
            }
        )
    return {
        "schema_id": FUNNEL.INPUT_SCHEMA,
        "profile_id": "engine_v2_deterministic_512_to_64_funnel_v1",
        "candidates": rows,
    }


def _save(tmp_path: Path, value: dict) -> Path:
    path = tmp_path / "input.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_exact_deterministic_512_to_64(tmp_path: Path) -> None:
    path = _save(tmp_path, _pool())
    first = FUNNEL.run(PROFILE, path)
    second = FUNNEL.run(PROFILE, path)
    assert len(first["observations"]) == 512
    assert len(first["selected_rows"]) == 64
    assert first["receipt_sha256"] == second["receipt_sha256"]
    assert first["authority"]["scientific_claim_authorized"] is False


def test_lane_shortfall_stays_in_output_denominator(tmp_path: Path) -> None:
    value = _pool()
    for row in value["candidates"]:
        if row["lane"] == "multi_anchor":
            row.update(
                {
                    "status": "typed_failure",
                    "failure_code": "feature_missing",
                    "source_sha256": None,
                    "proposal_sha256": None,
                    "coordinate_sha256": None,
                    "minimum_vdw_ratio": None,
                    "pocket_escape_angstrom": None,
                    "shape_penalty": None,
                    "anchor_penalty": None,
                    "embedding": None,
                }
            )
    result = FUNNEL.run(PROFILE, _save(tmp_path, value))
    failures = [
        row for row in result["selected_rows"] if row["status"] == "typed_failure"
    ]
    assert len(result["selected_rows"]) == 64
    assert len(failures) == 8
    assert {row["failure_code"] for row in failures} == {"lane_quota_unfilled"}


def test_hard_rejects_are_not_selected(tmp_path: Path) -> None:
    value = _pool()
    value["candidates"][0]["minimum_vdw_ratio"] = 0.1
    result = FUNNEL.run(PROFILE, _save(tmp_path, value))
    assert result["observations"][0]["decision"] == "hard_reject_vdw"
    assert all(row["source_pool_index"] != 0 for row in result["selected_rows"])


def test_result_dependent_field_is_rejected(tmp_path: Path) -> None:
    value = _pool()
    value["candidates"][0]["native_pose_rmsd"] = 0.0
    with pytest.raises(FUNNEL.FunnelError, match="field set"):
        FUNNEL.run(PROFILE, _save(tmp_path, value))


def test_candidate_sha_must_be_lowercase_hex(tmp_path: Path) -> None:
    value = _pool()
    value["candidates"][0]["source_sha256"] = "Z" * 64
    with pytest.raises(FUNNEL.FunnelError, match="source_sha256"):
        FUNNEL.run(PROFILE, _save(tmp_path, value))
