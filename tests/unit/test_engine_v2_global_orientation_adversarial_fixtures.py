from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path

import pytest

from betelgeuze_engine_v2.docking.global_orientation import (
    GlobalOrientationConfig,
    generate_global_orientation_batch,
)
from tools.verify_engine_v2_global_orientation_synthetic_contract import (
    load_fixture_suite,
    verify_fixture_suite,
)


_REPO_ROOT = Path(__file__).resolve().parents[2]
_FIXTURE_PATH = (
    _REPO_ROOT / "tests/fixtures/engine_v2_global_orientation_adversarial_v1.json"
)


def _centroid(coordinates: tuple[tuple[float, float, float], ...]) -> tuple[float, ...]:
    return tuple(
        sum(point[axis] for point in coordinates) / len(coordinates)
        for axis in range(3)
    )


def _distance_signature(
    coordinates: tuple[tuple[float, float, float], ...],
) -> tuple[float, ...]:
    return tuple(
        sorted(
            math.dist(left, right)
            for index, left in enumerate(coordinates[:-1])
            for right in coordinates[index + 1 :]
        )
    )


def _signed_tetrahedral_volume6(
    coordinates: tuple[tuple[float, float, float], ...],
) -> float:
    origin, first, second, third = coordinates
    left = tuple(first[index] - origin[index] for index in range(3))
    middle = tuple(second[index] - origin[index] for index in range(3))
    right = tuple(third[index] - origin[index] for index in range(3))
    return (
        left[0] * (middle[1] * right[2] - middle[2] * right[1])
        - left[1] * (middle[0] * right[2] - middle[2] * right[0])
        + left[2] * (middle[0] * right[1] - middle[1] * right[0])
    )


def _build(fixture: dict[str, object], suite: dict[str, object]):
    config = fixture["config"]
    return generate_global_orientation_batch(
        fixture["ligand_coordinates"],
        pocket_center=fixture["pocket_center"],
        pocket_normal=fixture["pocket_normal"],
        receptor_surface_points=fixture["receptor_surface_points"],
        config=GlobalOrientationConfig(
            orientation_count=config["orientation_count"],
            translation_shell_radii=tuple(config["translation_shell_radii"]),
            translation_points_per_shell=config["translation_points_per_shell"],
            minimum_receptor_distance=config["minimum_receptor_distance"],
        ),
        source_receipt_sha256=suite["source_receipt_sha256"],
        profile_id=suite["profile_id"],
    )


def _portable_observation_receipt(
    fixture: dict[str, object], suite: dict[str, object], batch
) -> str:
    payload = {
        "schema_id": suite["portable_observation_schema_id"],
        "fixture_id": fixture["fixture_id"],
        "generator_id": suite["generator_id"],
        "config_receipt_sha256": batch.config.receipt_sha256,
        "ligand_input_sha256": batch.ligand_input_sha256,
        "receptor_surface_input_sha256": batch.receptor_surface_input_sha256,
        "source_receipt_sha256": batch.source_receipt_sha256,
        "source_seed_sha256": batch.source_seed_sha256,
        "profile_id": batch.profile_id,
        "candidate_slot_count": len(batch.slots),
        "accepted_count": batch.accepted_count,
        "rejected_count": batch.rejected_count,
        "slot_outcomes": [
            {
                "proposal_index": slot.proposal_index,
                "orientation_index": slot.orientation_index,
                "raw_sequence_index": slot.raw_sequence_index,
                "accepted_sequence_index": slot.accepted_sequence_index,
                "translation_index": slot.translation_index,
                "accepted": slot.accepted,
                "rejection_code": slot.rejection_code,
            }
            for slot in batch.slots
        ],
    }

    def assert_no_runtime_float(value: object) -> None:
        assert type(value) is not float
        if isinstance(value, dict):
            for key, nested in value.items():
                assert_no_runtime_float(key)
                assert_no_runtime_float(nested)
        elif isinstance(value, (list, tuple)):
            for nested in value:
                assert_no_runtime_float(nested)

    assert_no_runtime_float(payload)
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    ).hexdigest()


def _derive_invariants(
    fixture: dict[str, object],
    batch,
) -> dict[str, bool]:
    fixture_id = fixture["fixture_id"]
    common = {
        "failure_complete_denominator": bool(
            len(batch.slots) == batch.config.candidate_slot_count
            and batch.accepted_count + batch.rejected_count == len(batch.slots)
        )
    }
    if fixture_id == "narrow_channel":
        return {
            **common,
            "mixed_acceptance_and_receptor_clash": bool(
                batch.accepted_count > 0
                and batch.rejected_count > 0
                and all(
                    slot.rejection_code == "receptor_clash"
                    for slot in batch.slots
                    if not slot.accepted
                )
            ),
            "accepted_slots_span_multiple_orientations": len(
                {slot.orientation_index for slot in batch.slots if slot.accepted}
            )
            > 1,
        }
    if fixture_id == "two_lobe_pocket":
        accepted_centroid_x = tuple(
            _centroid(slot.transformed_coordinates)[0]
            for slot in batch.slots
            if slot.accepted
        )
        return {
            **common,
            "mixed_acceptance_and_receptor_clash": bool(
                batch.accepted_count > 0
                and batch.rejected_count > 0
                and all(
                    slot.rejection_code == "receptor_clash"
                    for slot in batch.slots
                    if not slot.accepted
                )
            ),
            "accepted_centroids_occupy_both_lobes": bool(
                min(accepted_centroid_x) < -0.5 and max(accepted_centroid_x) > 0.5
            ),
        }
    if fixture_id == "symmetry_decoy":
        antipodal_pairs = ((0, 1), (2, 3), (4, 5))
        return {
            **common,
            "antipodal_symmetry_preserved": all(
                all(
                    first + second == pytest.approx(0.0, abs=1.0e-15)
                    for first, second in zip(
                        slot.transformed_coordinates[left],
                        slot.transformed_coordinates[right],
                    )
                )
                for slot in batch.slots
                for left, right in antipodal_pairs
            ),
            "distinct_orientation_receipts_for_symmetric_geometry": bool(
                len({slot.receipt_sha256 for slot in batch.slots}) == len(batch.slots)
                and len({slot.coordinate_sha256 for slot in batch.slots})
                == len(batch.slots)
            ),
        }
    if fixture_id == "mirror_decoy":
        source = tuple(tuple(row) for row in fixture["ligand_coordinates"])
        mirrored = tuple((-row[0], row[1], row[2]) for row in source)
        source_volume = _signed_tetrahedral_volume6(source)
        mirror_volume = _signed_tetrahedral_volume6(mirrored)
        return {
            **common,
            "proper_rotation_preserves_chirality": all(
                _signed_tetrahedral_volume6(slot.transformed_coordinates)
                == pytest.approx(source_volume, abs=1.0e-14)
                for slot in batch.slots
            ),
            "mirror_decoy_has_opposite_chirality": bool(
                source_volume > 0.0 and mirror_volume < 0.0
            ),
        }
    if fixture_id == "tangent_placement":
        normal_length = math.sqrt(sum(value * value for value in batch.pocket_normal))
        normal = tuple(value / normal_length for value in batch.pocket_normal)
        shell_displacements = tuple(
            tuple(
                slot.translation[axis] - batch.pocket_center[axis] for axis in range(3)
            )
            for slot in batch.slots[1:]
        )
        normal_projections = tuple(
            sum(value * axis for value, axis in zip(displacement, normal))
            for displacement in shell_displacements
        )
        tangent_norms = tuple(
            math.sqrt(
                max(
                    0.0,
                    sum(value * value for value in displacement)
                    - projection * projection,
                )
            )
            for displacement, projection in zip(shell_displacements, normal_projections)
        )
        return {
            **common,
            "shell_radius_preserved": all(
                math.sqrt(sum(value * value for value in displacement))
                == pytest.approx(2.0, abs=1.0e-14)
                for displacement in shell_displacements
            ),
            "tangent_component_present": all(value > 0.0 for value in tangent_norms),
            "normal_projection_spans_both_sides": bool(
                min(normal_projections) < 0.0 < max(normal_projections)
            ),
        }
    if fixture_id == "orientation_only":
        centroids = tuple(
            _centroid(slot.transformed_coordinates) for slot in batch.slots
        )
        return {
            **common,
            "single_translation_target": len({slot.translation for slot in batch.slots})
            == 1,
            "centroid_fixed_at_pocket_center": all(
                centroid == pytest.approx(batch.pocket_center, abs=1.0e-15)
                for centroid in centroids
            ),
            "orientations_change_coordinates": len(
                {slot.coordinate_sha256 for slot in batch.slots}
            )
            == len(batch.slots),
        }
    if fixture_id == "translation_only":
        signatures = tuple(
            _distance_signature(slot.transformed_coordinates) for slot in batch.slots
        )
        return {
            **common,
            "single_orientation_quaternion": len(
                {slot.quaternion for slot in batch.slots}
            )
            == 1,
            "translation_targets_are_distinct": len(
                {slot.translation for slot in batch.slots}
            )
            == len(batch.slots),
            "intramolecular_distances_preserved": all(
                observed == pytest.approx(signatures[0], abs=1.0e-14)
                for observed in signatures[1:]
            ),
        }
    raise AssertionError(f"unknown fixture_id: {fixture_id}")


def test_exact_adversarial_fixture_suite_rederives_portable_observations() -> None:
    suite = load_fixture_suite(_FIXTURE_PATH)
    assert verify_fixture_suite(suite) == suite["suite_sha256"]

    for fixture in suite["fixtures"]:
        batch = _build(fixture, suite)
        assert len(batch.receipt_sha256) == 64
        assert (
            _portable_observation_receipt(fixture, suite, batch)
            == (fixture["expected_portable_observation_receipt_sha256"])
        )
        assert len(batch.slots) == fixture["expected_candidate_slot_count"]
        assert batch.accepted_count == fixture["expected_accepted_count"]
        assert batch.rejected_count == fixture["expected_rejected_count"]
        invariants = _derive_invariants(fixture, batch)
        assert tuple(invariants) == tuple(fixture["required_invariants"])
        assert all(invariants.values())


def test_fixture_geometry_substitution_cannot_reproduce_the_golden_receipt() -> None:
    suite = load_fixture_suite(_FIXTURE_PATH)
    fixture = copy.deepcopy(suite["fixtures"][0])
    fixture["ligand_coordinates"][0][0] = -1.25

    batch = _build(fixture, suite)

    assert (
        _portable_observation_receipt(fixture, suite, batch)
        != (fixture["expected_portable_observation_receipt_sha256"])
    )


def test_fixture_corpus_contains_no_result_or_authority_input_fields() -> None:
    suite = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))
    serialized_keys = {key for fixture in suite["fixtures"] for key in fixture}
    assert serialized_keys.isdisjoint(
        {
            "native_pose",
            "reference_pose",
            "rmsd",
            "score",
            "benchmark_result",
            "fresh_holdout",
            "product_route",
        }
    )
    assert all(value is False for value in suite["authority"].values())
