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
    )


def test_evidence_rederives_the_complete_batch_from_source_geometry() -> None:
    first = _evidence()
    second = _evidence()

    assert first.receipt_sha256 == second.receipt_sha256
    assert first.to_dict()["source_rederivation_verified"] is True
    assert first.to_dict()["native_pose_input_consumed"] is False


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
