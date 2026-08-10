from __future__ import annotations

from dataclasses import replace

import pytest

from betelgeuze_engine_v2.docking.global_orientation import (
    GlobalOrientationConfig,
    GlobalOrientationError,
)
from betelgeuze_engine_v2.docking.global_orientation_evidence import (
    GlobalOrientationEvidence,
    build_global_orientation_evidence,
)


LIGAND = ((-2.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 1.0, 0.0))
SOURCE_RECEIPT_SHA256 = "a" * 64
PROFILE_ID = "engine-v2-independent-so3-synthetic-v2"


def _evidence() -> GlobalOrientationEvidence:
    return build_global_orientation_evidence(
        LIGAND,
        pocket_center=(0.0, 0.0, 0.0),
        pocket_normal=(0.0, 0.0, 1.0),
        receptor_surface_points=((0.0, 0.0, -5.0),),
        config=GlobalOrientationConfig(
            orientation_count=4,
            translation_shell_radii=(2.0,),
            translation_points_per_shell=3,
            minimum_receptor_distance=1.0,
        ),
        source_receipt_sha256=SOURCE_RECEIPT_SHA256,
        profile_id=PROFILE_ID,
    )


def test_evidence_rederives_the_complete_batch_from_source_geometry() -> None:
    first = _evidence()
    second = _evidence()

    assert first.receipt_sha256 == second.receipt_sha256
    assert first.to_dict()["source_rederivation_verified"] is True
    assert first.to_dict()["native_pose_input_consumed"] is False
    assert first.to_dict()["source_receipt_sha256"] == SOURCE_RECEIPT_SHA256
    assert first.to_dict()["profile_id"] == PROFILE_ID


def test_evidence_preserves_complete_orientation_sequence_and_coverage() -> None:
    payload = _evidence().to_dict()
    sequence = payload["orientation_sequence"]
    coverage = payload["orientation_coverage_statistics"]

    assert [row["orientation_index"] for row in sequence] == list(range(4))
    assert [row["accepted_sequence_index"] for row in sequence] == list(range(4))
    assert sequence[0]["raw_sequence_index"] == 0
    assert all(
        len(row["canonical_quaternion_binary64_hex"]) == 4 for row in sequence
    )
    assert coverage["requested_orientation_count"] == 4
    assert coverage["accepted_sequence_count"] == 4
    assert coverage["raw_sequence_count"] >= 4
    assert coverage["duplicate_orientation_count"] == (
        coverage["raw_sequence_count"] - coverage["accepted_sequence_count"]
    )
    assert coverage[
        "geodesic_duplicate_tolerance_radians_binary64_hex"
    ] == (1.0e-10).hex()


def test_evidence_does_not_create_molecular_or_promotion_authority() -> None:
    payload = _evidence().to_dict()

    for key in (
        "historical_ab_execution_authorized",
        "fresh_holdout_execution_authorized",
        "stage0_admission_authority",
        "profile_promotion_authority",
        "molecular_execution_authorized",
        "product_execution_authorized",
        "customer_pose_emission_authorized",
        "public_or_scientific_claim_authorized",
    ):
        assert payload[key] is False


def test_resealed_slot_coordinate_substitution_is_rejected() -> None:
    evidence = _evidence()
    first_slot = evidence.batch.slots[0]
    changed_coordinates = tuple(
        (point[0] + 0.25, point[1], point[2])
        for point in first_slot.transformed_coordinates
    )
    changed_slot = replace(
        first_slot,
        transformed_coordinates=changed_coordinates,
    )
    changed_batch = replace(
        evidence.batch,
        slots=(changed_slot, *evidence.batch.slots[1:]),
    )

    with pytest.raises(GlobalOrientationError, match="source rederivation"):
        GlobalOrientationEvidence(
            ligand_coordinates=evidence.ligand_coordinates,
            pocket_center=evidence.pocket_center,
            pocket_normal=evidence.pocket_normal,
            receptor_surface_points=evidence.receptor_surface_points,
            config=evidence.config,
            batch=changed_batch,
            source_receipt_sha256=evidence.source_receipt_sha256,
            profile_id=evidence.profile_id,
        )


def test_resealed_translation_substitution_is_rejected() -> None:
    evidence = _evidence()
    first_slot = evidence.batch.slots[0]
    changed_slot = replace(
        first_slot,
        translation=(0.5, 0.0, 0.0),
    )
    changed_batch = replace(
        evidence.batch,
        slots=(changed_slot, *evidence.batch.slots[1:]),
    )

    with pytest.raises(GlobalOrientationError, match="source rederivation"):
        replace(evidence, batch=changed_batch)


def test_receptor_surface_substitution_is_rejected() -> None:
    evidence = _evidence()

    with pytest.raises(GlobalOrientationError, match="source rederivation"):
        replace(
            evidence,
            receptor_surface_points=((0.0, 0.0, 0.0),),
        )


def test_source_receipt_or_profile_cross_wiring_is_rejected() -> None:
    evidence = _evidence()

    with pytest.raises(GlobalOrientationError, match="source rederivation"):
        replace(evidence, source_receipt_sha256="b" * 64)
    with pytest.raises(GlobalOrientationError, match="source rederivation"):
        replace(evidence, profile_id="cross-wired-profile")


@pytest.mark.parametrize(
    ("field_name", "changed_value"),
    (
        ("raw_sequence_index", 1),
        ("accepted_sequence_index", 1),
    ),
)
def test_resealed_sequence_index_substitution_is_rejected(
    field_name: str,
    changed_value: int,
) -> None:
    evidence = _evidence()
    first_slot = evidence.batch.slots[0]
    changed_slot = replace(first_slot, **{field_name: changed_value})

    with pytest.raises(
        GlobalOrientationError,
        match="orientation sequence|raw orientation",
    ):
        replace(
            evidence.batch,
            slots=(changed_slot, *evidence.batch.slots[1:]),
        )


def test_resealed_canonical_quaternion_substitution_fails_closed() -> None:
    evidence = _evidence()
    first_slot = evidence.batch.slots[0]
    changed_quaternion = (
        (0.0, 0.0, 0.0, 1.0)
        if first_slot.quaternion != (0.0, 0.0, 0.0, 1.0)
        else (1.0, 0.0, 0.0, 0.0)
    )
    changed_slot = replace(
        first_slot,
        quaternion=changed_quaternion,
    )
    with pytest.raises(GlobalOrientationError, match="orientation sequence"):
        replace(
            evidence.batch,
            slots=(changed_slot, *evidence.batch.slots[1:]),
        )


def test_quaternion_sign_equivalence_is_canonicalized_in_receipt() -> None:
    evidence = _evidence()
    first_slot = evidence.batch.slots[0]
    sign_flipped = replace(
        first_slot,
        quaternion=tuple(-component for component in first_slot.quaternion),
    )

    assert sign_flipped.quaternion == first_slot.quaternion
    assert sign_flipped.receipt_sha256 == first_slot.receipt_sha256


def test_in_memory_source_seed_tamper_fails_closed() -> None:
    evidence = _evidence()
    object.__setattr__(evidence.batch, "source_seed_sha256", "b" * 64)

    with pytest.raises(GlobalOrientationError, match="batch changed"):
        evidence.to_dict()
