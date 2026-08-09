from __future__ import annotations

from dataclasses import replace
import inspect
import math

import pytest

from betelgeuze_engine_v2.docking.global_orientation import (
    GlobalOrientationConfig,
    GlobalOrientationError,
    _quaternion_geodesic_distance,
    generate_global_orientation_batch,
)


LIGAND = ((-2.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 1.0, 0.0))
SOURCE_RECEIPT = "1a" * 32


def _config() -> GlobalOrientationConfig:
    return GlobalOrientationConfig(
        orientation_count=6,
        translation_shell_radii=(2.0,),
        translation_points_per_shell=4,
        minimum_receptor_distance=1.1,
    )


def test_generator_is_deterministic_and_failure_complete() -> None:
    first = generate_global_orientation_batch(
        LIGAND,
        pocket_center=(1.0, 2.0, 3.0),
        pocket_normal=(0.0, 0.0, 1.0),
        config=_config(),
    )
    second = generate_global_orientation_batch(
        LIGAND,
        pocket_center=(1.0, 2.0, 3.0),
        pocket_normal=(0.0, 0.0, 1.0),
        config=_config(),
    )

    assert first.receipt_sha256 == second.receipt_sha256
    assert len(first.slots) == 6 * 5
    assert first.config.candidate_slot_count == 30
    assert first.accepted_count == 30
    assert first.rejected_count == 0
    assert tuple(slot.proposal_index for slot in first.slots) == tuple(range(30))


def test_low_discrepancy_orientation_prefix_is_independent_of_requested_count() -> None:
    short = generate_global_orientation_batch(
        LIGAND,
        pocket_center=(0.0, 0.0, 0.0),
        pocket_normal=(0.0, 0.0, 1.0),
        config=GlobalOrientationConfig(
            orientation_count=6,
            translation_shell_radii=(),
            translation_points_per_shell=1,
        ),
        source_receipt_sha256=SOURCE_RECEIPT,
        profile_id="mixed64-independent-so3-v1",
    )
    long = generate_global_orientation_batch(
        LIGAND,
        pocket_center=(0.0, 0.0, 0.0),
        pocket_normal=(0.0, 0.0, 1.0),
        config=GlobalOrientationConfig(
            orientation_count=12,
            translation_shell_radii=(),
            translation_points_per_shell=1,
        ),
        source_receipt_sha256=SOURCE_RECEIPT,
        profile_id="mixed64-independent-so3-v1",
    )

    assert short.source_seed_sha256 == long.source_seed_sha256
    assert tuple(slot.quaternion for slot in short.slots) == tuple(
        slot.quaternion for slot in long.slots[:6]
    )
    assert tuple(slot.raw_sequence_index for slot in short.slots) == tuple(
        slot.raw_sequence_index for slot in long.slots[:6]
    )
    assert tuple(slot.accepted_sequence_index for slot in short.slots) == tuple(
        range(6)
    )


def test_all_quaternions_are_normalized_and_slot_receipts_are_unique() -> None:
    batch = generate_global_orientation_batch(
        LIGAND,
        pocket_center=(0.0, 0.0, 0.0),
        pocket_normal=(0.0, 1.0, 1.0),
        config=_config(),
    )

    for slot in batch.slots:
        norm = math.sqrt(sum(component * component for component in slot.quaternion))
        assert norm == pytest.approx(1.0, abs=1.0e-12)
        first_nonzero_in_canonical_order = next(
            component for component in reversed(slot.quaternion) if component != 0.0
        )
        assert first_nonzero_in_canonical_order > 0.0
    assert len({slot.receipt_sha256 for slot in batch.slots}) == len(batch.slots)


def test_source_seed_binds_source_ligand_pocket_and_profile() -> None:
    common = {
        "pocket_center": (0.0, 0.0, 0.0),
        "pocket_normal": (0.0, 0.0, 1.0),
        "config": _config(),
        "source_receipt_sha256": SOURCE_RECEIPT,
        "profile_id": "mixed64-independent-so3-v1",
    }
    baseline = generate_global_orientation_batch(LIGAND, **common)
    changed_source = generate_global_orientation_batch(
        LIGAND,
        **{**common, "source_receipt_sha256": "2b" * 32},
    )
    changed_ligand = generate_global_orientation_batch(
        (*LIGAND[:-1], (0.0, 1.25, 0.0)),
        **common,
    )
    changed_pocket = generate_global_orientation_batch(
        LIGAND,
        **{**common, "pocket_center": (0.25, 0.0, 0.0)},
    )
    changed_profile = generate_global_orientation_batch(
        LIGAND,
        **{**common, "profile_id": "mixed64-independent-so3-v2"},
    )

    assert len(baseline.source_seed_sha256) == 64
    assert baseline.source_receipt_sha256 == SOURCE_RECEIPT
    assert (
        len(
            {
                baseline.source_seed_sha256,
                changed_source.source_seed_sha256,
                changed_ligand.source_seed_sha256,
                changed_pocket.source_seed_sha256,
                changed_profile.source_seed_sha256,
            }
        )
        == 5
    )


def test_supported_x86_64_libm_seed_has_frozen_quaternion_golden_vector() -> None:
    batch = generate_global_orientation_batch(
        LIGAND,
        pocket_center=(0.0, 0.0, 0.0),
        pocket_normal=(0.0, 0.0, 1.0),
        config=GlobalOrientationConfig(
            orientation_count=3,
            translation_shell_radii=(),
            translation_points_per_shell=1,
        ),
        source_receipt_sha256=SOURCE_RECEIPT,
        profile_id="mixed64-independent-so3-v1",
    )

    assert batch.source_seed_sha256 == (
        "49d902cad80846024dd3f126cac8492c6b55a784d639aded77921dea2fe403f8"
    )
    assert tuple(
        tuple(component.hex() for component in slot.quaternion)
        for slot in batch.slots
    ) == (
        (
            "-0x1.973fbb4c6279ep-1",
            "0x1.1f8e934a32954p-2",
            "-0x1.0b2574e1f8db8p-2",
            "0x1.e0bdfdf80aceap-2",
        ),
        (
            "0x1.65d54e9008dc7p-2",
            "0x1.3235311df0969p-2",
            "0x1.35b4fca7d2670p-1",
            "0x1.4cd3a45d273c1p-1",
        ),
        (
            "-0x1.fdb4295ab734cp-4",
            "0x1.55f2c14c7141cp-1",
            "-0x1.54acb66d16190p-1",
            "0x1.3cd6eae3c887cp-2",
        ),
    )


def test_receipt_exposes_sequence_lineage_and_geodesic_coverage() -> None:
    batch = generate_global_orientation_batch(
        LIGAND,
        pocket_center=(0.0, 0.0, 0.0),
        pocket_normal=(0.0, 0.0, 1.0),
        config=GlobalOrientationConfig(
            orientation_count=24,
            translation_shell_radii=(),
            translation_points_per_shell=1,
        ),
        source_receipt_sha256=SOURCE_RECEIPT,
    )
    payload = batch.to_dict()
    coverage = payload["orientation_coverage_statistics"]

    assert [slot.to_dict()["raw_sequence_index"] for slot in batch.slots] == [
        slot.raw_sequence_index for slot in batch.slots
    ]
    assert [slot.accepted_sequence_index for slot in batch.slots] == list(range(24))
    assert coverage["requested_orientation_count"] == 24
    assert coverage["accepted_sequence_count"] == 24
    assert coverage["raw_sequence_count"] >= 24
    assert coverage["duplicate_orientation_count"] == (
        coverage["raw_sequence_count"] - coverage["accepted_sequence_count"]
    )
    assert (
        float.fromhex(
            coverage["minimum_pairwise_geodesic_distance_radians_binary64_hex"]
        )
        > 1.0e-10
    )
    assert (
        float.fromhex(
            coverage["mean_nearest_neighbor_geodesic_distance_radians_binary64_hex"]
        )
        > 0.0
    )
    assert (
        float.fromhex(
            coverage["maximum_nearest_neighbor_geodesic_distance_radians_binary64_hex"]
        )
        > 0.0
    )


@pytest.mark.parametrize(
    ("factor", "expected_relation"),
    ((0.5, "below"), (1.0, "equal"), (2.0, "above")),
)
def test_geodesic_duplicate_threshold_is_numerically_stable(
    factor: float,
    expected_relation: str,
) -> None:
    threshold = 1.0e-10
    angle = factor * threshold
    candidate = (math.sin(angle / 2.0), 0.0, 0.0, math.cos(angle / 2.0))
    observed = _quaternion_geodesic_distance(
        (0.0, 0.0, 0.0, 1.0),
        candidate,
    )

    assert observed == pytest.approx(angle, rel=1.0e-12, abs=1.0e-24)
    if expected_relation == "below":
        assert observed < threshold
    elif expected_relation == "equal":
        assert observed == pytest.approx(threshold, rel=1.0e-12)
    else:
        assert observed > threshold


@pytest.mark.parametrize("component", (math.nan, math.inf, -math.inf))
def test_non_finite_quaternion_fails_closed(component: float) -> None:
    batch = generate_global_orientation_batch(
        LIGAND,
        pocket_center=(0.0, 0.0, 0.0),
        pocket_normal=(0.0, 0.0, 1.0),
        config=GlobalOrientationConfig(
            orientation_count=1,
            translation_shell_radii=(),
            translation_points_per_shell=1,
        ),
        source_receipt_sha256=SOURCE_RECEIPT,
    )

    with pytest.raises(GlobalOrientationError, match="quaternion"):
        replace(batch.slots[0], quaternion=(component, 0.0, 0.0, 1.0))


def test_clash_prefilter_retains_rejected_slots_in_denominator() -> None:
    batch = generate_global_orientation_batch(
        LIGAND,
        pocket_center=(0.0, 0.0, 0.0),
        pocket_normal=(0.0, 0.0, 1.0),
        receptor_surface_points=((0.0, 0.0, 0.0),),
        config=GlobalOrientationConfig(
            orientation_count=4,
            translation_shell_radii=(1.0,),
            translation_points_per_shell=3,
            minimum_receptor_distance=5.0,
        ),
    )

    assert len(batch.slots) == 16
    assert batch.rejected_count > 0
    assert batch.accepted_count + batch.rejected_count == 16
    assert all(
        slot.accepted or slot.rejection_code == "receptor_clash" for slot in batch.slots
    )


def test_generator_signature_cannot_consume_native_pose_or_scoring_feedback() -> None:
    parameters = set(inspect.signature(generate_global_orientation_batch).parameters)

    assert "native_pose" not in parameters
    assert "reference_pose" not in parameters
    assert "rmsd" not in parameters
    assert "score" not in parameters
    assert "benchmark_result" not in parameters
    assert "fresh_holdout" not in parameters


def test_invalid_geometry_fails_closed() -> None:
    with pytest.raises(GlobalOrientationError, match="distinct"):
        generate_global_orientation_batch(
            ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
            pocket_center=(0.0, 0.0, 0.0),
            pocket_normal=(0.0, 0.0, 1.0),
            config=_config(),
        )

    with pytest.raises(GlobalOrientationError, match="pocket_normal"):
        generate_global_orientation_batch(
            LIGAND,
            pocket_center=(0.0, 0.0, 0.0),
            pocket_normal=(0.0, 0.0, 0.0),
            config=_config(),
        )
