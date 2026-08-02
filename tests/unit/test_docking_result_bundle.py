"""Common DockingResult bundle tests (roadmap §17 result schema)."""

from __future__ import annotations

import pytest

from betelgeuze_product.docking_result_bundle import (
    DOCKING_RESULT_BUNDLE_SCHEMA_VERSION,
    REQUIRED_BUNDLE_SECTIONS,
    STATUS_BLOCKED,
    STATUS_READY,
    DockingResultBundle,
    DockingResultBundleError,
    FailureDenominator,
    PoseRecord,
    compare_bundles,
    validate_bundle_payload,
)
from betelgeuze_product.preparation_packet import (
    ENGINE_SURFACE_ENGINE_V2,
    ENGINE_SURFACE_EXTERNAL_ORACLE,
    ENGINE_SURFACE_LEGACY_PRODUCT,
)


def _denominator() -> FailureDenominator:
    return FailureDenominator(
        attempted_case_count=10,
        scored_case_count=8,
        failed_case_count=1,
        abstained_case_count=1,
    )


def _pose(score: float = -5.0, *, rank: int = 1) -> PoseRecord:
    return PoseRecord(
        pose_id=f"pose_{rank}",
        rank=rank,
        conformer_id="conf_1",
        cluster_id=0,
        total_score=score,
        per_term_score={"typed_steric_vdw": -2.0, "directional_hbond": -1.5},
        geometric_valid=True,
        chemistry_valid=True,
    )


def _bundle(surface: str = ENGINE_SURFACE_LEGACY_PRODUCT, **overrides) -> DockingResultBundle:
    kwargs = {
        "engine_surface": surface,
        "engine_version": "1.0.0",
        "prepared_input_hash": "prepared_hash",
        "receptor_input_hash": "receptor_hash",
        "ligand_input_hash": "ligand_hash",
        "pocket_identity": {"center": [0.0, 0.0, 0.0], "radius_a": 6.0},
        "poses": (_pose(),),
        "failure_denominator": _denominator(),
        "runtime_seconds": 1.5,
        "candidate_budget": 100,
        "benchmark_profile": "frozen_profile_v1",
        "claim_scope": "restricted_internal",
    }
    kwargs.update(overrides)
    return DockingResultBundle(**kwargs)


def test_bundle_payload_contains_every_required_section() -> None:
    payload = _bundle().to_dict()

    assert payload["schema_version"] == DOCKING_RESULT_BUNDLE_SCHEMA_VERSION
    assert payload["status"] == STATUS_READY
    assert validate_bundle_payload(payload) == []
    for section in REQUIRED_BUNDLE_SECTIONS:
        assert section in payload


def test_engine_surface_must_be_one_of_the_three_declared_surfaces() -> None:
    for surface in (
        ENGINE_SURFACE_LEGACY_PRODUCT,
        ENGINE_SURFACE_ENGINE_V2,
        ENGINE_SURFACE_EXTERNAL_ORACLE,
    ):
        assert _bundle(surface).engine_surface == surface

    with pytest.raises(DockingResultBundleError) as excinfo:
        _bundle("some_other_engine")
    assert "unsupported_engine_surface" in str(excinfo.value)


@pytest.mark.parametrize(
    "field_name", ["engine_version", "prepared_input_hash", "benchmark_profile", "claim_scope"]
)
def test_missing_required_field_fails_closed(field_name: str) -> None:
    with pytest.raises(DockingResultBundleError) as excinfo:
        _bundle(**{field_name: "  "})

    assert str(excinfo.value) == f"missing_required_field:{field_name}"


def test_failure_denominator_must_account_for_every_attempted_case() -> None:
    assert _denominator().accounted is True

    with pytest.raises(DockingResultBundleError) as excinfo:
        _bundle(failure_denominator=FailureDenominator(10, 5, 1, 1))

    assert str(excinfo.value) == "failure_denominator_not_accounted"


def test_per_term_score_is_reported_per_pose() -> None:
    payload = _bundle().to_dict()

    assert payload["per_term_score"]["pose_1"]["typed_steric_vdw"] == -2.0
    assert payload["per_term_score"]["pose_1"]["directional_hbond"] == -1.5


def test_validity_counts_split_geometric_and_chemistry() -> None:
    bad_pose = PoseRecord(
        pose_id="pose_2",
        rank=2,
        conformer_id="conf_2",
        cluster_id=1,
        total_score=-1.0,
        per_term_score={},
        geometric_valid=False,
        chemistry_valid=True,
    )
    payload = _bundle(poses=(_pose(), bad_pose)).to_dict()

    assert payload["geometric_validity"] == {"valid_pose_count": 1, "invalid_pose_count": 1}
    assert payload["chemistry_validity"] == {"valid_pose_count": 2, "invalid_pose_count": 0}


def test_abstention_is_reported_through_uncertainty() -> None:
    abstained = _bundle(uncertainty={"abstained": True, "reason": "low_confidence"})

    assert abstained.abstained is True
    assert _bundle().abstained is False


def test_runtime_and_candidate_budget_are_reported() -> None:
    payload = _bundle().to_dict()

    assert payload["runtime_budget"]["runtime_seconds"] == 1.5
    assert payload["runtime_budget"]["candidate_budget"] == 100


def test_blockers_mark_the_bundle_blocked() -> None:
    blocked = _bundle(blockers=("pose_generation_failed",))

    assert blocked.status == STATUS_BLOCKED
    assert blocked.to_dict()["blockers"] == ["pose_generation_failed"]


def test_top_pose_is_the_best_ranked_pose() -> None:
    second = PoseRecord(
        pose_id="pose_2",
        rank=2,
        conformer_id="conf_2",
        cluster_id=1,
        total_score=-9.0,
        per_term_score={},
        geometric_valid=True,
        chemistry_valid=True,
    )
    bundle = _bundle(poses=(second, _pose()))

    assert bundle.top_pose is not None
    assert bundle.top_pose.pose_id == "pose_1"


def test_bundles_sharing_prepared_input_are_comparable() -> None:
    legacy = _bundle(ENGINE_SURFACE_LEGACY_PRODUCT, poses=(_pose(-5.0),))
    v2 = _bundle(ENGINE_SURFACE_ENGINE_V2, poses=(_pose(-6.0),))

    comparison = compare_bundles([legacy, v2])

    assert comparison["comparable"] is True
    assert comparison["invalid_reasons"] == []
    assert comparison["pairwise_deltas"][0]["top_score_delta"] == -1.0


def test_three_surface_comparison_produces_every_pair() -> None:
    comparison = compare_bundles(
        [
            _bundle(ENGINE_SURFACE_LEGACY_PRODUCT),
            _bundle(ENGINE_SURFACE_ENGINE_V2),
            _bundle(ENGINE_SURFACE_EXTERNAL_ORACLE),
        ]
    )

    assert comparison["comparable"] is True
    assert len(comparison["pairwise_deltas"]) == 3


def test_mismatched_prepared_input_blocks_the_comparison() -> None:
    comparison = compare_bundles(
        [
            _bundle(ENGINE_SURFACE_LEGACY_PRODUCT),
            _bundle(ENGINE_SURFACE_ENGINE_V2, prepared_input_hash="different_hash"),
        ]
    )

    assert comparison["comparable"] is False
    assert "mismatched_prepared_input_hash" in comparison["invalid_reasons"]
    assert comparison["pairwise_deltas"] == []


def test_mismatched_pocket_blocks_the_comparison() -> None:
    comparison = compare_bundles(
        [
            _bundle(ENGINE_SURFACE_LEGACY_PRODUCT),
            _bundle(
                ENGINE_SURFACE_ENGINE_V2,
                pocket_identity={"center": [9.0, 9.0, 9.0], "radius_a": 6.0},
            ),
        ]
    )

    assert comparison["comparable"] is False
    assert "mismatched_pocket_identity" in comparison["invalid_reasons"]


def test_mismatched_candidate_budget_blocks_the_comparison() -> None:
    comparison = compare_bundles(
        [
            _bundle(ENGINE_SURFACE_LEGACY_PRODUCT),
            _bundle(ENGINE_SURFACE_ENGINE_V2, candidate_budget=5000),
        ]
    )

    assert comparison["comparable"] is False
    assert "mismatched_candidate_budget" in comparison["invalid_reasons"]


def test_single_surface_is_not_a_comparison() -> None:
    comparison = compare_bundles([_bundle()])

    assert comparison["comparable"] is False
    assert "need_at_least_two_engine_surfaces" in comparison["invalid_reasons"]


def test_duplicate_surface_blocks_the_comparison() -> None:
    comparison = compare_bundles([_bundle(), _bundle()])

    assert comparison["comparable"] is False
    assert "duplicate_engine_surface" in comparison["invalid_reasons"]


def test_bundle_hash_is_deterministic_and_input_sensitive() -> None:
    assert _bundle().bundle_hash == _bundle().bundle_hash
    assert _bundle().bundle_hash != _bundle(poses=(_pose(-9.0),)).bundle_hash


def test_incomplete_payload_is_detected() -> None:
    payload = _bundle().to_dict()
    payload.pop("failure_denominator")

    assert validate_bundle_payload(payload) == ["failure_denominator"]


def test_payload_states_no_claim_promotion() -> None:
    payload = _bundle().to_dict()

    assert "does not itself dock, score, or promote a claim" in payload["claim_boundary"]
