from __future__ import annotations

import inspect
import math

import pytest

from betelgeuze_engine_v2.docking.global_orientation import (
    GlobalOrientationConfig,
    GlobalOrientationError,
    generate_global_orientation_batch,
    rotate_vector,
)


LIGAND = ((-2.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 1.0, 0.0))


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


def test_first_orientation_aligns_ligand_long_axis_to_pocket_normal() -> None:
    batch = generate_global_orientation_batch(
        LIGAND,
        pocket_center=(0.0, 0.0, 0.0),
        pocket_normal=(0.0, 0.0, 1.0),
        config=_config(),
    )
    first = batch.slots[0]
    rotated_axis = rotate_vector((1.0, 0.0, 0.0), first.quaternion)

    assert rotated_axis[2] > 0.999999999
    assert abs(rotated_axis[0]) < 1.0e-9
    assert abs(rotated_axis[1]) < 1.0e-9


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
    assert len({slot.receipt_sha256 for slot in batch.slots}) == len(batch.slots)


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
        slot.accepted or slot.rejection_code == "receptor_clash"
        for slot in batch.slots
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
