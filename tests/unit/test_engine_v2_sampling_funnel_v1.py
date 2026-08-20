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
EXPECTED_LANE_ORDER = [
    "uniform_so3",
    "pocket_surface",
    "single_anchor",
    "multi_anchor",
]
EXPECTED_SELECTED_POOL_INDICES = [
    int(value)
    for value in (
        ROOT
        / "rust/betelgeuze-docking-search/tests/fixtures/"
        "sampling_funnel_selected_indices_v1.txt"
    )
    .read_text(encoding="ascii")
    .split()
]
EXPECTED_PROFILE_CANONICAL_SHA256 = (
    "5f9a3f30ddb1cf76a64cb64dff678c191751e2ead368c8e9f73f08d44ec69a28"
)


def _pool() -> dict:
    lanes = EXPECTED_LANE_ORDER
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
    assert FUNNEL._digest(FUNNEL._profile(PROFILE)) == EXPECTED_PROFILE_CANONICAL_SHA256
    path = _save(tmp_path, _pool())
    first = FUNNEL.run(PROFILE, path)
    second = FUNNEL.run(PROFILE, path)
    assert len(first["observations"]) == 512
    assert len(first["selected_rows"]) == 64
    assert first["receipt_sha256"] == second["receipt_sha256"]
    assert first["lane_order"] == EXPECTED_LANE_ORDER
    assert [
        row["source_pool_index"] for row in first["selected_rows"]
    ] == EXPECTED_SELECTED_POOL_INDICES
    assert [
        row["lane"] for row in first["selected_rows"][:24]
    ] == ["uniform_so3"] * 24
    assert [
        row["lane"] for row in first["selected_rows"][-8:]
    ] == ["multi_anchor"] * 8
    assert first["authority"]["scientific_claim_authorized"] is False
    assert all(
        summary["generated_count"] == 128
        and summary["typed_failure_count"] == 0
        and summary["duplicate_count"] == 0
        and summary["filtered_count"] == 0
        for summary in first["lane_summary"].values()
    )


def test_global_coordinate_identity_duplicate_is_filtered(tmp_path: Path) -> None:
    value = _pool()
    value["candidates"][1]["coordinate_sha256"] = value["candidates"][0][
        "coordinate_sha256"
    ]
    result = FUNNEL.run(PROFILE, _save(tmp_path, value))
    assert result["observations"][0]["decision"] == "eligible"
    assert result["observations"][1]["decision"] == "duplicate_coordinate"
    assert result["lane_summary"]["pocket_surface"]["duplicate_count"] == 1
    assert result["lane_summary"]["pocket_surface"]["filtered_count"] == 1
    selected_coordinates = [
        row["coordinate_sha256"]
        for row in result["selected_rows"]
        if row["status"] == "selected"
    ]
    assert len(selected_coordinates) == len(set(selected_coordinates))


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
    assert all(row["lane"] == "multi_anchor" for row in failures)


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


def test_candidate_sha_must_not_be_zero(tmp_path: Path) -> None:
    value = _pool()
    value["candidates"][0]["coordinate_sha256"] = "0" * 64
    with pytest.raises(FUNNEL.FunnelError, match="coordinate_sha256"):
        FUNNEL.run(PROFILE, _save(tmp_path, value))


def test_lane_order_must_cover_quota_map(tmp_path: Path) -> None:
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    profile["lane_order"].pop()
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(profile), encoding="utf-8")
    with pytest.raises(FUNNEL.FunnelError, match="lane order"):
        FUNNEL._profile(path)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("hard_minimum_vdw_ratio", 0.9),
        ("maximum_pocket_escape_angstrom", 5.0),
        ("quality_prefilter_multiplier", 5),
        ("lane_order", list(reversed(EXPECTED_LANE_ORDER))),
    ],
)
def test_profile_must_match_frozen_native_constants(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    profile[field] = value
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(profile), encoding="utf-8")
    with pytest.raises(FUNNEL.FunnelError, match="profile differs"):
        FUNNEL._profile(path)


def test_profile_quota_must_match_frozen_native_constants(tmp_path: Path) -> None:
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    profile["lane_quotas"]["uniform_so3"] -= 1
    profile["lane_quotas"]["pocket_surface"] += 1
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(profile), encoding="utf-8")
    with pytest.raises(FUNNEL.FunnelError, match="profile differs"):
        FUNNEL._profile(path)


def test_profile_non_numeric_quota_is_a_typed_funnel_error(tmp_path: Path) -> None:
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    profile["lane_quotas"]["uniform_so3"] = "24"
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(profile), encoding="utf-8")
    with pytest.raises(FUNNEL.FunnelError, match="positive integers"):
        FUNNEL._profile(path)


def test_embedding_distance_overflow_is_a_typed_funnel_error() -> None:
    with pytest.raises(FUNNEL.FunnelError, match="embedding distance"):
        FUNNEL._distance((1e200,) * 7, (-1e200,) * 7)
