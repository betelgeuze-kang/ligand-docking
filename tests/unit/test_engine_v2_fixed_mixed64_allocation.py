from __future__ import annotations

from collections import Counter
from dataclasses import replace
import hashlib
import inspect

import pytest

from betelgeuze_engine_v2.docking.mixed64_allocation import (
    FIXED_MIXED64_CANDIDATE_COUNT,
    FIXED_MIXED64_LANE_RANGES,
    FixedMixed64AllocationError,
    GENERATION_PARENT_EXACT_PASSTHROUGH,
    GENERATION_PARENT_GENERATOR_INPUT,
    LANE_AROMATIC_PLANE,
    LANE_COMPLEMENTARY_CHARGE,
    LANE_LIGAND_ACCEPTOR_TO_RECEPTOR_DONOR,
    LANE_LIGAND_DONOR_TO_RECEPTOR_ACCEPTOR,
    LANE_PAIRED_RETAINED_CONTROLS,
    LANE_PRINCIPAL_AXIS_SHAPE,
    LANE_TRUE_CONFORMER_INDEPENDENT_SO3,
    MISSING_FEATURE_STATUS,
    Mixed64AtomicFeatureEvidence,
    Mixed64ConformerSourceEvidence,
    Mixed64ExactV11SourceEvidence,
    Mixed64FeatureEvidence,
    Mixed64RetainedSourceEvidence,
    Mixed64V7ControlSourceEvidence,
    READY_STATUS,
    RETAINED_SOURCE_INDICES,
    TRUE_CONFORMER_RANKS,
    V7_CONTROL_SOURCE_INDICES,
    V7_CONTROL_SOURCE_NAMESPACE,
    build_fixed_mixed64_allocation,
)


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode("ascii")).hexdigest()


def _features(*, all_available: bool) -> Mixed64FeatureEvidence:
    ligand_topology_sha256 = _digest("ligand-topology")
    receptor_topology_sha256 = _digest("receptor-topology")
    exact_source = Mixed64ExactV11SourceEvidence(
        source_receipt_sha256=_digest("v11-source"),
        proposal_sha256=_digest("v11-proposal"),
        ligand_coordinate_sha256=_digest("v11-ligand-coordinate"),
        receptor_coordinate_sha256=_digest("v11-receptor-coordinate"),
        prepared_ligand_topology_sha256=ligand_topology_sha256,
        prepared_receptor_topology_sha256=receptor_topology_sha256,
        ligand_vdw_radii_sha256=_digest("ligand-vdw-radii"),
        ligand_heavy_atom_mask_sha256=_digest("ligand-heavy-atom-mask"),
        receptor_vdw_radii_sha256=_digest("receptor-vdw-radii"),
    )
    feature_rows = (
        ("ligand_acceptor", (2,)),
        ("ligand_aromatic_plane", (5, 6, 7)),
        ("ligand_donor", (0, 1)),
        ("ligand_positive_site", (3,)),
        ("ligand_shape_axis", (0, 2, 3)),
        ("pocket_shape_axis", (20, 21, 22)),
        ("receptor_acceptor", (12,)),
        ("receptor_aromatic_plane", (15, 16, 17)),
        ("receptor_donor", (10, 11)),
        ("receptor_negative_site", (13,)),
    )
    atomic = tuple(
        Mixed64AtomicFeatureEvidence(
            kind=kind,
            atom_indices=indices,
            source_receipt_sha256=_digest(f"feature-source-{kind}"),
            geometry_receipt_sha256=_digest(f"feature-geometry-{kind}"),
        )
        for kind, indices in feature_rows
    )
    conformers = tuple(
        Mixed64ConformerSourceEvidence(
            rank=rank,
            proposal_sha256=_digest(f"conformer-proposal-{rank}"),
            coordinate_sha256=_digest(f"conformer-coordinate-{rank}"),
            source_receipt_sha256=_digest(f"conformer-receipt-{rank}"),
        )
        for rank in TRUE_CONFORMER_RANKS
    )
    v7_controls = tuple(
        Mixed64V7ControlSourceEvidence(
            source_index=index,
            proposal_mode=(
                "pocket_centered_control"
                if index < 8
                else "uniform_source_control"
            ),
            proposal_sha256=_digest(f"v7-control-proposal-{index}"),
            coordinate_sha256=_digest(f"v7-control-coordinate-{index}"),
            proposal_lineage_sha256=_digest(f"v7-control-lineage-{index}"),
            source_receipt_sha256=_digest(f"v7-control-receipt-{index}"),
        )
        for index in V7_CONTROL_SOURCE_INDICES
    )
    retained = tuple(
        Mixed64RetainedSourceEvidence(
            source_index=index,
            proposal_sha256=_digest(f"retained-proposal-{index}"),
            coordinate_sha256=_digest(f"retained-coordinate-{index}"),
            source_receipt_sha256=_digest(f"retained-receipt-{index}"),
        )
        for index in RETAINED_SOURCE_INDICES
    )
    return Mixed64FeatureEvidence(
        exact_v11_source_receipt_sha256=exact_source.source_receipt_sha256,
        prepared_ligand_topology_sha256=ligand_topology_sha256,
        prepared_receptor_topology_sha256=receptor_topology_sha256,
        exact_v11_source=exact_source,
        feature_extractor_policy_sha256=_digest("feature-policy"),
        atomic_features=atomic if all_available else (),
        v7_control_sources=v7_controls if all_available else (),
        conformer_sources=conformers if all_available else (),
        retained_sources=retained if all_available else (),
    )


def test_exact_mixed64_ranges_counts_and_retained_sources_are_frozen() -> None:
    allocation = build_fixed_mixed64_allocation(_features(all_available=True))

    assert len(allocation.slots) == FIXED_MIXED64_CANDIDATE_COUNT == 64
    assert allocation.ready_count == 64
    assert allocation.typed_failure_count == 0
    assert tuple(slot.slot_index for slot in allocation.slots) == tuple(range(64))
    for lane, start, end in FIXED_MIXED64_LANE_RANGES:
        assert all(slot.lane == lane for slot in allocation.slots[start : end + 1])
        assert tuple(
            slot.lane_offset for slot in allocation.slots[start : end + 1]
        ) == tuple(range(end - start + 1))
    assert tuple(slot.retained_source_index for slot in allocation.slots[60:64]) == (
        36,
        45,
        54,
        63,
    )
    assert tuple(
        slot.v7_control_source_index for slot in allocation.slots[:24]
    ) == tuple(range(24))
    assert tuple(
        slot.selected_source_receipt_sha256s[0]
        for slot in allocation.slots[:24]
    ) == tuple(source.receipt_sha256 for source in allocation.features.v7_control_sources)
    assert tuple(slot.so3_sequence_index for slot in allocation.slots[24:36]) == tuple(
        range(12)
    )
    assert tuple(slot.so3_sequence_index for slot in allocation.slots[36:44]) == tuple(
        range(8)
    )
    assert tuple(slot.true_conformer_rank for slot in allocation.slots[36:44]) == (
        *TRUE_CONFORMER_RANKS,
        2,
    )
    assert allocation.slots[36].selected_source_receipt_sha256s == (
        allocation.slots[43].selected_source_receipt_sha256s
    )
    assert all(
        len(slot.selected_source_receipt_sha256s) == 2
        for slot in allocation.slots[44:60]
    )
    assert all(
        len(slot.selected_source_receipt_sha256s) == 1
        for slot in allocation.slots[60:64]
    )
    assert all(
        slot.generation_parent_role == GENERATION_PARENT_EXACT_PASSTHROUGH
        for slot in allocation.slots[:24] + allocation.slots[60:64]
    )
    assert all(
        slot.generation_parent_role == GENERATION_PARENT_GENERATOR_INPUT
        for slot in allocation.slots[36:44]
    )
    assert all(
        slot.selected_generation_parent_proposal_sha256 is not None
        and slot.selected_generation_parent_coordinate_sha256 is not None
        for slot in allocation.slots[:24]
        + allocation.slots[36:44]
        + allocation.slots[60:64]
    )
    assert Counter(slot.lane for slot in allocation.slots) == {
        lane: end - start + 1 for lane, start, end in FIXED_MIXED64_LANE_RANGES
    }


def test_missing_features_are_typed_without_fallback_or_reallocation() -> None:
    allocation = build_fixed_mixed64_allocation(_features(all_available=False))

    assert allocation.ready_count == 12
    assert allocation.typed_failure_count == 52
    assert all(
        slot.generation_status == MISSING_FEATURE_STATUS
        for slot in allocation.slots[:24]
    )
    assert all(
        slot.missing_feature_codes == (f"missing_v7_control_source:{slot.slot_index}",)
        and slot.selected_source_receipt_sha256s == ()
        and slot.selected_generation_parent_proposal_sha256 is None
        and slot.selected_generation_parent_coordinate_sha256 is None
        and slot.generation_parent_role is None
        for slot in allocation.slots[:24]
    )
    assert all(
        slot.generation_status == READY_STATUS for slot in allocation.slots[24:36]
    )
    assert all(
        slot.generation_status == MISSING_FEATURE_STATUS
        and not slot.generation_eligible
        and slot.to_dict()["fallback_lane"] is None
        and slot.to_dict()["fallback_allowed"] is False
        and slot.to_dict()["slot_preserved_on_failure"] is True
        for slot in allocation.slots[36:]
    )
    assert {
        slot.lane: slot.missing_feature_codes
        for slot in (
            allocation.slots[36],
            allocation.slots[44],
            allocation.slots[48],
            allocation.slots[52],
            allocation.slots[56],
            allocation.slots[58],
        )
    } == {
        LANE_TRUE_CONFORMER_INDEPENDENT_SO3: ("missing_true_conformer:2",),
        LANE_LIGAND_DONOR_TO_RECEPTOR_ACCEPTOR: (
            "missing_ligand_donor",
            "missing_receptor_acceptor",
        ),
        LANE_LIGAND_ACCEPTOR_TO_RECEPTOR_DONOR: (
            "missing_ligand_acceptor",
            "missing_receptor_donor",
        ),
        LANE_COMPLEMENTARY_CHARGE: ("missing_complementary_charge_anchor",),
        LANE_AROMATIC_PLANE: (
            "missing_ligand_aromatic_plane",
            "missing_receptor_aromatic_plane",
        ),
        LANE_PRINCIPAL_AXIS_SHAPE: (
            "missing_ligand_shape_axis",
            "missing_pocket_shape_axis",
        ),
    }
    assert tuple(slot.missing_feature_codes for slot in allocation.slots[60:64]) == (
        ("missing_retained_source:36",),
        ("missing_retained_source:45",),
        ("missing_retained_source:54",),
        ("missing_retained_source:63",),
    )
    assert all(
        slot.lane == LANE_PAIRED_RETAINED_CONTROLS for slot in allocation.slots[60:64]
    )


def test_every_anchor_lane_is_single_anchor_and_never_multi_anchor() -> None:
    allocation = build_fixed_mixed64_allocation(_features(all_available=True))
    anchored = allocation.slots[44:60]

    assert len(anchored) == 16
    assert all(slot.declared_anchor_count == 1 for slot in anchored)
    assert all(
        slot.to_dict()["multi_anchor_allowed"] is False for slot in allocation.slots
    )
    assert all(
        slot.declared_anchor_count == 0
        for slot in allocation.slots[:44] + allocation.slots[60:]
    )


def test_allocation_is_deterministic_and_has_no_result_feedback_inputs() -> None:
    features = _features(all_available=True)
    first = build_fixed_mixed64_allocation(features)
    second = build_fixed_mixed64_allocation(features)

    assert first.receipt_sha256 == second.receipt_sha256
    parameters = set(inspect.signature(build_fixed_mixed64_allocation).parameters)
    assert parameters == {"features"}
    forbidden = {
        "native_pose",
        "reference_pose",
        "rmsd",
        "score",
        "rank",
        "benchmark_outcome",
        "fresh_holdout",
    }
    assert forbidden.isdisjoint(parameters)
    receipt = first.to_dict()
    assert receipt["allocation_result_dependent"] is False
    assert receipt["molecular_execution_authorized"] is False


def test_resealed_feature_failure_or_slot_source_cross_wire_fails_closed() -> None:
    unavailable = build_fixed_mixed64_allocation(_features(all_available=False))
    donor_slot = unavailable.slots[44]
    forged_ready = replace(
        donor_slot,
        declared_anchor_kind=None,
        required_features=(),
        missing_feature_codes=(),
        generation_status=READY_STATUS,
        generation_eligible=True,
    )
    with pytest.raises(FixedMixed64AllocationError, match="do not rederive"):
        replace(
            unavailable,
            slots=(
                *unavailable.slots[:44],
                forged_ready,
                *unavailable.slots[45:],
            ),
        )

    available = build_fixed_mixed64_allocation(_features(all_available=True))
    wrong_source = replace(
        available.slots[0],
        v7_control_source_index=1,
    )
    with pytest.raises(FixedMixed64AllocationError, match="do not rederive"):
        replace(
            available,
            slots=(wrong_source, *available.slots[1:]),
        )


def test_true_conformer_and_so3_mapping_tamper_fails_closed() -> None:
    allocation = build_fixed_mixed64_allocation(_features(all_available=True))
    changed = replace(
        allocation.slots[43],
        true_conformer_rank=8,
        so3_sequence_index=7,
    )

    with pytest.raises(FixedMixed64AllocationError, match="do not rederive"):
        replace(
            allocation,
            slots=(*allocation.slots[:43], changed, *allocation.slots[44:]),
        )


def test_missing_conformer_rank_fails_only_its_frozen_slot() -> None:
    features = _features(all_available=True)
    partial = replace(
        features,
        conformer_sources=tuple(
            source for source in features.conformer_sources if source.rank != 4
        ),
    )
    allocation = build_fixed_mixed64_allocation(partial)

    failed = tuple(
        slot.slot_index
        for slot in allocation.slots
        if slot.generation_status == MISSING_FEATURE_STATUS
    )
    assert failed == (38,)
    assert allocation.slots[38].missing_feature_codes == ("missing_true_conformer:4",)
    assert allocation.slots[36].generation_eligible is True
    assert allocation.slots[43].generation_eligible is True


def test_missing_v7_control_source_fails_only_its_exact_passthrough_slot() -> None:
    features = _features(all_available=True)
    partial = replace(
        features,
        v7_control_sources=tuple(
            source for source in features.v7_control_sources if source.source_index != 9
        ),
    )
    allocation = build_fixed_mixed64_allocation(partial)

    failed = tuple(
        slot.slot_index
        for slot in allocation.slots
        if slot.generation_status == MISSING_FEATURE_STATUS
    )
    assert failed == (9,)
    assert allocation.slots[9].missing_feature_codes == (
        "missing_v7_control_source:9",
    )
    assert allocation.slots[9].selected_source_receipt_sha256s == ()
    assert allocation.slots[9].selected_generation_parent_proposal_sha256 is None
    assert allocation.slots[9].selected_generation_parent_coordinate_sha256 is None
    assert allocation.slots[9].generation_parent_role is None
    assert allocation.slots[8].generation_eligible is True
    assert allocation.slots[10].generation_eligible is True


def test_v7_control_evidence_and_parent_identity_are_exact_and_source_bound() -> None:
    features = _features(all_available=True)
    allocation = build_fixed_mixed64_allocation(features)

    source = features.v7_control_for_index(17)
    assert source is not None
    assert source.source_namespace == V7_CONTROL_SOURCE_NAMESPACE
    assert source.to_dict()["generation_parent_role"] == (
        GENERATION_PARENT_EXACT_PASSTHROUGH
    )
    slot = allocation.slots[17]
    assert slot.selected_source_receipt_sha256s == (source.receipt_sha256,)
    assert slot.selected_generation_parent_proposal_sha256 == source.proposal_sha256
    assert slot.selected_generation_parent_coordinate_sha256 == source.coordinate_sha256
    assert slot.generation_parent_role == GENERATION_PARENT_EXACT_PASSTHROUGH

    conformer = features.conformer_for_rank(4)
    assert conformer is not None
    conformer_slot = allocation.slots[38]
    assert conformer_slot.selected_generation_parent_proposal_sha256 == (
        conformer.proposal_sha256
    )
    assert conformer_slot.selected_generation_parent_coordinate_sha256 == (
        conformer.coordinate_sha256
    )
    assert conformer_slot.generation_parent_role == GENERATION_PARENT_GENERATOR_INPUT

    retained = features.retained_for_index(54)
    assert retained is not None
    retained_slot = allocation.slots[62]
    assert retained_slot.selected_generation_parent_proposal_sha256 == (
        retained.proposal_sha256
    )
    assert retained_slot.selected_generation_parent_coordinate_sha256 == (
        retained.coordinate_sha256
    )
    assert retained_slot.generation_parent_role == GENERATION_PARENT_EXACT_PASSTHROUGH

    exact = features.exact_v11_source
    exact_generated_slots = allocation.slots[24:36] + allocation.slots[44:60]
    assert all(
        slot.selected_generation_parent_proposal_sha256 == exact.proposal_sha256
        and slot.selected_generation_parent_coordinate_sha256
        == exact.ligand_coordinate_sha256
        and slot.generation_parent_role == GENERATION_PARENT_GENERATOR_INPUT
        for slot in exact_generated_slots
    )


def test_exact_v11_evidence_cross_wiring_and_live_tamper_fail_closed() -> None:
    features = _features(all_available=True)

    with pytest.raises(FixedMixed64AllocationError, match="cross-wired"):
        replace(
            features,
            exact_v11_source_receipt_sha256=_digest("other-source-receipt"),
        )
    with pytest.raises(FixedMixed64AllocationError, match="cross-wired"):
        replace(
            features,
            prepared_receptor_topology_sha256=_digest("other-receptor-topology"),
        )

    exact = features.exact_v11_source
    object.__setattr__(exact, "proposal_sha256", _digest("tampered-exact-proposal"))
    with pytest.raises(FixedMixed64AllocationError, match="source evidence changed"):
        features.to_dict()


def test_v7_control_source_and_generation_parent_cross_wires_fail_closed() -> None:
    with pytest.raises(FixedMixed64AllocationError, match="namespace changed"):
        Mixed64V7ControlSourceEvidence(
            source_index=0,
            proposal_mode="pocket_centered_control",
            proposal_sha256=_digest("proposal"),
            coordinate_sha256=_digest("coordinate"),
            proposal_lineage_sha256=_digest("lineage"),
            source_receipt_sha256=_digest("receipt"),
            source_namespace="caller_selected_control",
        )
    with pytest.raises(FixedMixed64AllocationError, match="index is not frozen"):
        Mixed64V7ControlSourceEvidence(
            source_index=24,
            proposal_mode="uniform_source_control",
            proposal_sha256=_digest("proposal"),
            coordinate_sha256=_digest("coordinate"),
            proposal_lineage_sha256=_digest("lineage"),
            source_receipt_sha256=_digest("receipt"),
        )
    with pytest.raises(FixedMixed64AllocationError, match="exact lowercase SHA-256"):
        Mixed64V7ControlSourceEvidence(
            source_index=0,
            proposal_mode="pocket_centered_control",
            proposal_sha256="not-a-digest",
            coordinate_sha256=_digest("coordinate"),
            proposal_lineage_sha256=_digest("lineage"),
            source_receipt_sha256=_digest("receipt"),
        )

    allocation = build_fixed_mixed64_allocation(_features(all_available=True))
    cross_wired = replace(
        allocation.slots[0],
        selected_generation_parent_proposal_sha256=(
            allocation.slots[1].selected_generation_parent_proposal_sha256
        ),
    )
    with pytest.raises(FixedMixed64AllocationError, match="do not rederive"):
        replace(allocation, slots=(cross_wired, *allocation.slots[1:]))

    forged_role = replace(
        allocation.slots[36],
        generation_parent_role=GENERATION_PARENT_EXACT_PASSTHROUGH,
    )
    with pytest.raises(FixedMixed64AllocationError, match="do not rederive"):
        replace(
            allocation,
            slots=(*allocation.slots[:36], forged_role, *allocation.slots[37:]),
        )


def test_v7_control_source_order_and_receipt_tamper_fail_closed() -> None:
    features = _features(all_available=True)
    with pytest.raises(FixedMixed64AllocationError, match="unique and sorted"):
        replace(
            features,
            v7_control_sources=(
                features.v7_control_sources[1],
                features.v7_control_sources[0],
                *features.v7_control_sources[2:],
            ),
        )

    source = features.v7_control_sources[0]
    object.__setattr__(source, "coordinate_sha256", _digest("tampered-coordinate"))
    with pytest.raises(FixedMixed64AllocationError, match="source evidence changed"):
        source.to_dict()

    allocation = build_fixed_mixed64_allocation(_features(all_available=True))
    slot = allocation.slots[5]
    object.__setattr__(
        slot,
        "selected_generation_parent_coordinate_sha256",
        _digest("tampered-parent-coordinate"),
    )
    with pytest.raises(FixedMixed64AllocationError, match="mixed64 slot changed"):
        slot.to_dict()


def test_v7_control_mode_and_atomic_feature_capacity_fail_closed() -> None:
    with pytest.raises(FixedMixed64AllocationError, match="proposal mode disagrees"):
        Mixed64V7ControlSourceEvidence(
            source_index=8,
            proposal_mode="pocket_centered_control",
            proposal_sha256=_digest("proposal"),
            coordinate_sha256=_digest("coordinate"),
            proposal_lineage_sha256=_digest("lineage"),
            source_receipt_sha256=_digest("receipt"),
        )

    with pytest.raises(FixedMixed64AllocationError, match="bounded non-negative"):
        Mixed64AtomicFeatureEvidence(
            kind="ligand_shape_axis",
            atom_indices=(1 << 53,),
            source_receipt_sha256=_digest("feature-source"),
            geometry_receipt_sha256=_digest("feature-geometry"),
        )

    indices = tuple(range(4096))
    rows = tuple(
        sorted(
            (
                Mixed64AtomicFeatureEvidence(
                    kind="ligand_shape_axis",
                    atom_indices=indices,
                    source_receipt_sha256=_digest(f"large-source-{index}"),
                    geometry_receipt_sha256=_digest(f"large-geometry-{index}"),
                )
                for index in range(17)
            ),
            key=lambda value: (value.kind, value.receipt_sha256),
        )
    )
    with pytest.raises(FixedMixed64AllocationError, match="total atomic feature"):
        replace(_features(all_available=True), atomic_features=rows)

    repeated = rows[0]
    with pytest.raises(FixedMixed64AllocationError, match="fixed evidence capacity"):
        replace(
            _features(all_available=True),
            atomic_features=(repeated,) * (12 * 256 + 1),
        )
