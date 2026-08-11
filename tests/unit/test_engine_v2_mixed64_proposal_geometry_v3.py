from __future__ import annotations

from dataclasses import replace
import hashlib
import inspect
import math

import pytest

import betelgeuze_engine_v2.docking.mixed64_proposal_geometry_v3 as geometry
from betelgeuze_engine_v2.docking.mixed64_allocation import (
    FEATURE_LIGAND_ACCEPTOR,
    FEATURE_LIGAND_AROMATIC_PLANE,
    FEATURE_LIGAND_DONOR,
    FEATURE_LIGAND_POSITIVE_SITE,
    FEATURE_LIGAND_SHAPE_AXIS,
    FEATURE_POCKET_SHAPE_AXIS,
    FEATURE_RECEPTOR_ACCEPTOR,
    FEATURE_RECEPTOR_AROMATIC_PLANE,
    FEATURE_RECEPTOR_DONOR,
    FEATURE_RECEPTOR_NEGATIVE_SITE,
    TRUE_CONFORMER_RANKS,
    Mixed64AtomicFeatureEvidence,
    Mixed64ConformerSourceEvidence,
    Mixed64FeatureEvidence,
    build_fixed_mixed64_allocation,
)
from betelgeuze_engine_v2.docking.mixed64_proposal_geometry_v3 import (
    ALLOCATION_SLOT_NOT_ELIGIBLE,
    DEGENERATE_AROMATIC_PLANE,
    DEGENERATE_LIGAND_DIRECTION,
    DEGENERATE_LOCAL_SURFACE_NORMAL,
    DEGENERATE_PRINCIPAL_AXIS,
    FEATURE_ATOM_INDEX_OUT_OF_RANGE,
    SOURCE_COORDINATE_IDENTITY_MISMATCH,
    SOURCE_PROPOSAL_IDENTITY_MISMATCH,
    SOURCE_RECEIPT_IDENTITY_MISMATCH,
    Mixed64ProposalGeometryError,
    coordinate_sha256,
    generate_indexed_so3_placement,
    generate_single_anchor_placement,
)


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode("ascii")).hexdigest()


LIGAND = (
    (0.0, 0.0, 0.0),  # donor
    (1.0, 0.0, 0.0),  # attached H
    (2.0, 0.0, 0.0),  # acceptor
    (0.0, 1.0, 0.0),  # positive site
    (0.0, -1.0, 0.5),
    (-1.0, -1.0, 0.0),  # aromatic plane
    (1.0, -1.0, 0.0),
    (0.0, 1.0, 0.0),
    (-2.0, 0.2, 0.1),  # shape-axis evidence
    (0.0, 0.0, 0.0),
    (3.0, -0.1, 0.2),
)
RECEPTOR = (
    (0.0, 0.0, 0.0),  # donor
    (0.0, 0.0, 1.0),  # attached H
    (0.2, 0.1, 0.0),  # acceptor
    (-0.2, 0.0, 0.0),  # negative site
    (0.0, 0.0, 0.0),
    (-1.0, -1.0, 0.0),  # aromatic plane
    (1.0, -1.0, 0.0),
    (0.0, 1.0, 0.0),
    (-3.0, 0.1, 0.0),  # pocket shape-axis evidence
    (0.0, 0.0, 0.0),
    (4.0, -0.2, 0.1),
)
POCKET_CENTER = (0.0, 0.0, 10.0)
SOURCE_RECEIPT = _digest("v11-source")
SOURCE_PROPOSAL = _digest("v11-source-proposal")


def _atomic_features(
    *,
    aromatic_degenerate: bool = False,
    shape_degenerate: bool = False,
    out_of_range: bool = False,
) -> tuple[Mixed64AtomicFeatureEvidence, ...]:
    ligand_aromatic = (0, 1, 2) if aromatic_degenerate else (5, 6, 7)
    ligand_shape = (9,) if shape_degenerate else (8, 9, 10)
    receptor_acceptor = (999,) if out_of_range else (2,)
    rows = (
        (FEATURE_LIGAND_ACCEPTOR, (2,)),
        (FEATURE_LIGAND_AROMATIC_PLANE, ligand_aromatic),
        (FEATURE_LIGAND_DONOR, (0, 1)),
        (FEATURE_LIGAND_POSITIVE_SITE, (3,)),
        (FEATURE_LIGAND_SHAPE_AXIS, ligand_shape),
        (FEATURE_POCKET_SHAPE_AXIS, (8, 9, 10)),
        (FEATURE_RECEPTOR_ACCEPTOR, receptor_acceptor),
        (FEATURE_RECEPTOR_AROMATIC_PLANE, (5, 6, 7)),
        (FEATURE_RECEPTOR_DONOR, (0, 1)),
        (FEATURE_RECEPTOR_NEGATIVE_SITE, (3,)),
    )
    return tuple(
        sorted(
            (
                Mixed64AtomicFeatureEvidence(
                    kind=kind,
                    atom_indices=indices,
                    source_receipt_sha256=_digest(f"feature-source-{kind}"),
                    geometry_receipt_sha256=_digest(f"feature-geometry-{kind}"),
                )
                for kind, indices in rows
            ),
            key=lambda value: (value.kind, value.receipt_sha256),
        )
    )


def _allocation(
    *,
    ligand: tuple[tuple[float, float, float], ...] = LIGAND,
    conformers: bool = False,
    aromatic_degenerate: bool = False,
    shape_degenerate: bool = False,
    out_of_range: bool = False,
):
    conformer_sources = (
        tuple(
            Mixed64ConformerSourceEvidence(
                rank=rank,
                proposal_sha256=_digest(f"conformer-proposal-{rank}"),
                coordinate_sha256=coordinate_sha256(ligand),
                source_receipt_sha256=_digest(f"conformer-receipt-{rank}"),
            )
            for rank in TRUE_CONFORMER_RANKS
        )
        if conformers
        else ()
    )
    features = Mixed64FeatureEvidence(
        exact_v11_source_receipt_sha256=SOURCE_RECEIPT,
        prepared_ligand_topology_sha256=_digest("ligand-topology"),
        prepared_receptor_topology_sha256=_digest("receptor-topology"),
        feature_extractor_policy_sha256=_digest("feature-policy"),
        atomic_features=_atomic_features(
            aromatic_degenerate=aromatic_degenerate,
            shape_degenerate=shape_degenerate,
            out_of_range=out_of_range,
        ),
        v7_control_sources=(),
        conformer_sources=conformer_sources,
        retained_sources=(),
    )
    return build_fixed_mixed64_allocation(features)


def _so3(allocation, *, slot_index: int = 24, ligand=LIGAND, **overrides):
    arguments = {
        "slot_index": slot_index,
        "source_proposal_sha256": SOURCE_PROPOSAL,
        "source_coordinate_sha256": coordinate_sha256(ligand),
        "source_receipt_sha256": SOURCE_RECEIPT,
        "source_coordinates": ligand,
        "pocket_center": POCKET_CENTER,
        "pocket_normal": (0.0, 0.0, 1.0),
    }
    arguments.update(overrides)
    return generate_indexed_so3_placement(allocation, **arguments)


def _anchor(
    allocation,
    *,
    slot_index: int,
    ligand=LIGAND,
    receptor=RECEPTOR,
    ligand_radii=None,
    receptor_radii=None,
    **overrides,
):
    arguments = {
        "slot_index": slot_index,
        "source_proposal_sha256": SOURCE_PROPOSAL,
        "source_coordinate_sha256": coordinate_sha256(ligand),
        "source_receipt_sha256": SOURCE_RECEIPT,
        "ligand_coordinates": ligand,
        "ligand_vdw_radii": ligand_radii or (1.2,) * len(ligand),
        "ligand_heavy_atom_mask": (True,) * len(ligand),
        "receptor_coordinate_sha256": coordinate_sha256(receptor),
        "receptor_coordinates": receptor,
        "receptor_vdw_radii": receptor_radii or (1.2,) * len(receptor),
        "pocket_center": POCKET_CENTER,
        "pocket_radius": 20.0,
    }
    arguments.update(overrides)
    return generate_single_anchor_placement(allocation, **arguments)


def _distance(left, right) -> float:
    return math.sqrt(sum((left[index] - right[index]) ** 2 for index in range(3)))


def _unit(value) -> tuple[float, float, float]:
    length = math.sqrt(sum(component * component for component in value))
    return tuple(component / length for component in value)


class _BoundedEndlessRows:
    def __init__(self, permitted_reads: int) -> None:
        self.permitted_reads = permitted_reads
        self.read_count = 0

    def __iter__(self):
        return self

    def __next__(self):
        self.read_count += 1
        if self.read_count > self.permitted_reads:
            raise AssertionError("coordinate iterable was consumed past its bound")
        return (0.0, 0.0, 0.0)


def test_indexed_so3_is_deterministic_source_bound_and_index_stable() -> None:
    allocation = _allocation()
    first = _so3(allocation, slot_index=24)
    second = _so3(allocation, slot_index=24)
    next_slot = _so3(allocation, slot_index=25)

    assert first.receipt_sha256 == second.receipt_sha256
    assert first.accepted_sequence_index == 0
    assert next_slot.accepted_sequence_index == 1
    assert first.source_seed_sha256 == next_slot.source_seed_sha256
    assert first.quaternion != next_slot.quaternion
    assert first.output_coordinate_sha256 != next_slot.output_coordinate_sha256
    assert tuple(
        sum(point[axis] for point in first.output_coordinates)
        / len(first.output_coordinates)
        for axis in range(3)
    ) == pytest.approx(POCKET_CENTER)


def test_indexed_so3_seed_changes_with_exact_source_payload() -> None:
    allocation = _allocation()
    changed = (*LIGAND[:-1], (3.25, -0.1, 0.2))
    baseline = _so3(allocation)
    other = _so3(allocation, ligand=changed)

    assert baseline.source_seed_sha256 != other.source_seed_sha256
    assert baseline.output_coordinate_sha256 != other.output_coordinate_sha256


def test_public_generators_bound_coordinate_iterables_before_materializing() -> None:
    so3_rows = _BoundedEndlessRows(geometry.MAX_LIGAND_ATOMS + 1)
    with pytest.raises(Mixed64ProposalGeometryError) as captured:
        _so3(_allocation(), source_coordinates=so3_rows)
    assert captured.value.code == geometry.GEOMETRIC_PRECHECK_INPUT_INVALID
    assert so3_rows.read_count == geometry.MAX_LIGAND_ATOMS + 1

    ligand_rows = _BoundedEndlessRows(geometry.MAX_LIGAND_ATOMS + 1)
    with pytest.raises(Mixed64ProposalGeometryError) as captured:
        _anchor(
            _allocation(),
            slot_index=44,
            ligand_coordinates=ligand_rows,
        )
    assert captured.value.code == geometry.GEOMETRIC_PRECHECK_INPUT_INVALID
    assert ligand_rows.read_count == geometry.MAX_LIGAND_ATOMS + 1

    receptor_rows = _BoundedEndlessRows(geometry.MAX_RECEPTOR_ATOMS + 1)
    with pytest.raises(Mixed64ProposalGeometryError) as captured:
        _anchor(
            _allocation(),
            slot_index=44,
            receptor_coordinates=receptor_rows,
        )
    assert captured.value.code == geometry.GEOMETRIC_PRECHECK_INPUT_INVALID
    assert receptor_rows.read_count == geometry.MAX_RECEPTOR_ATOMS + 1


@pytest.mark.parametrize(
    ("override", "code"),
    [
        ({"source_receipt_sha256": _digest("wrong-source")}, SOURCE_RECEIPT_IDENTITY_MISMATCH),
        ({"source_coordinate_sha256": _digest("wrong-coordinate")}, SOURCE_COORDINATE_IDENTITY_MISMATCH),
    ],
)
def test_indexed_so3_rejects_source_cross_wiring(override, code: str) -> None:
    with pytest.raises(Mixed64ProposalGeometryError) as captured:
        _so3(_allocation(), **override)
    assert captured.value.code == code


def test_true_conformer_so3_requires_exact_allocation_parent() -> None:
    allocation = _allocation(conformers=True)
    slot = allocation.slots[36]
    receipt = _so3(
        allocation,
        slot_index=36,
        source_proposal_sha256=slot.selected_generation_parent_proposal_sha256,
        source_receipt_sha256=slot.selected_source_receipt_sha256s[0],
    )
    assert receipt.accepted_sequence_index == 0

    with pytest.raises(Mixed64ProposalGeometryError) as captured:
        _so3(allocation, slot_index=36)
    assert captured.value.code == SOURCE_PROPOSAL_IDENTITY_MISMATCH


def test_unavailable_true_conformer_slot_fails_before_geometry() -> None:
    with pytest.raises(Mixed64ProposalGeometryError) as captured:
        _so3(_allocation(), slot_index=36)
    assert captured.value.code == ALLOCATION_SLOT_NOT_ELIGIBLE


def test_donor_acceptor_anchor_hits_frozen_distance_and_direction() -> None:
    receipt = _anchor(_allocation(), slot_index=44)
    transformed_donor = receipt.output_coordinates[0]
    transformed_hydrogen = receipt.output_coordinates[1]

    assert _distance(transformed_donor, receipt.receptor_anchor_point) == pytest.approx(2.9)
    assert _unit(
        tuple(
            transformed_hydrogen[index] - transformed_donor[index]
            for index in range(3)
        )
    ) == pytest.approx(receipt.approach_vector)
    assert receipt.geometric_metrics.exact_pair_count == len(LIGAND) * len(RECEPTOR)
    assert receipt.geometric_metrics.ligand_atom_count == len(LIGAND)
    assert receipt.geometric_metrics.receptor_atom_count == len(RECEPTOR)


@pytest.mark.parametrize(
    ("slot_index", "distance"),
    [(44, 2.9), (48, 2.9), (52, 3.5), (56, 3.8), (58, 3.0)],
)
def test_every_single_anchor_lane_records_complete_frozen_geometry(
    slot_index: int,
    distance: float,
) -> None:
    receipt = _anchor(_allocation(), slot_index=slot_index)
    document = receipt.to_dict()

    assert receipt.target_distance_angstrom == distance
    assert _distance(receipt.target_anchor_point, receipt.receptor_anchor_point) == pytest.approx(
        distance
    )
    assert math.sqrt(sum(value * value for value in receipt.local_surface_normal)) == pytest.approx(1.0)
    assert receipt.approach_vector == tuple(-value for value in receipt.local_surface_normal)
    assert document["single_anchor_count"] == 1
    assert len(document["geometry_policy_sha256"]) == 64
    assert document["multi_anchor_consumed"] is False
    assert document["exact_pair_count_preserved"] is True
    assert document["slot_reallocation_allowed"] is False
    assert document["molecular_execution_authorized"] is False
    assert document["public_or_scientific_claim_authorized"] is False


@pytest.mark.parametrize("start", [44, 48, 52, 56, 58])
def test_lane_twists_are_predeclared_and_do_not_reallocate(start: int) -> None:
    width = 2 if start in {56, 58} else 4
    receipts = tuple(_anchor(_allocation(), slot_index=start + offset) for offset in range(width))

    assert tuple(receipt.twist_angle_radians for receipt in receipts) == pytest.approx(
        tuple(2.0 * math.pi * offset / width for offset in range(width))
    )
    assert len({receipt.quaternion for receipt in receipts}) == width
    assert len({receipt.output_coordinate_sha256 for receipt in receipts}) == width


def test_aromatic_normal_tangent_to_pocket_direction_fails_closed() -> None:
    with pytest.raises(Mixed64ProposalGeometryError) as captured:
        _anchor(
            _allocation(),
            slot_index=56,
            pocket_center=(10.0, 0.0, 0.0),
        )
    assert captured.value.code == DEGENERATE_LOCAL_SURFACE_NORMAL


def test_principal_axis_solver_finds_off_diagonal_dominant_mode() -> None:
    dominant = _unit((1.0, 1.0, 0.0))
    dominant_scale = math.sqrt(1.1 / 2.0)
    secondary_scale = math.sqrt(1.0 / 2.0)
    coordinates = (
        tuple(dominant_scale * value for value in dominant),
        tuple(-dominant_scale * value for value in dominant),
        (0.0, 0.0, secondary_scale),
        (0.0, 0.0, -secondary_scale),
    )

    observed = geometry._principal_axis(coordinates, role="test")

    assert abs(sum(left * right for left, right in zip(observed, dominant))) == (
        pytest.approx(1.0)
    )


def test_severe_penetration_is_preserved_as_precheck_evidence() -> None:
    receipt = _anchor(
        _allocation(),
        slot_index=44,
        ligand_radii=(10.0,) * len(LIGAND),
        receptor_radii=(10.0,) * len(RECEPTOR),
    )
    document = receipt.to_dict()

    assert receipt.steric_precheck_passed is False
    assert document["severe_penetration_preserved_for_typed_admission"] is True
    assert receipt.output_coordinates
    assert receipt.geometric_metrics.penetration_pair_count > 0


@pytest.mark.parametrize(
    ("allocation", "slot_index", "code", "ligand"),
    [
        (
            _allocation(),
            44,
            DEGENERATE_LIGAND_DIRECTION,
            ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0), *LIGAND[2:]),
        ),
        (_allocation(aromatic_degenerate=True), 56, DEGENERATE_AROMATIC_PLANE, LIGAND),
        (_allocation(shape_degenerate=True), 58, DEGENERATE_PRINCIPAL_AXIS, LIGAND),
        (_allocation(out_of_range=True), 44, FEATURE_ATOM_INDEX_OUT_OF_RANGE, LIGAND),
    ],
)
def test_anchor_degeneracy_has_typed_failure_codes(
    allocation,
    slot_index: int,
    code: str,
    ligand,
) -> None:
    with pytest.raises(Mixed64ProposalGeometryError) as captured:
        _anchor(allocation, slot_index=slot_index, ligand=ligand)
    assert captured.value.code == code


def test_receipts_rederive_and_reject_tampering() -> None:
    so3 = _so3(_allocation())
    anchor = _anchor(_allocation(), slot_index=44)

    with pytest.raises(Mixed64ProposalGeometryError) as captured:
        replace(so3, source_coordinate_sha256=_digest("tampered"))
    assert captured.value.code == SOURCE_COORDINATE_IDENTITY_MISMATCH
    with pytest.raises(Mixed64ProposalGeometryError) as captured:
        replace(anchor, receptor_coordinate_sha256=_digest("tampered"))
    assert captured.value.code == "receptor_coordinate_identity_mismatch"


def test_public_generators_cannot_consume_result_or_authority_inputs() -> None:
    forbidden = {
        "score",
        "rank",
        "rmsd",
        "native_pose",
        "benchmark_outcome",
        "reservation",
        "authority",
        "fresh",
    }
    for function in (
        generate_indexed_so3_placement,
        generate_single_anchor_placement,
    ):
        parameters = set(inspect.signature(function).parameters)
        assert not parameters & forbidden
