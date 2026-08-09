from __future__ import annotations

from dataclasses import replace
import hashlib
import inspect
from itertools import repeat
import math

import pytest

from betelgeuze_engine_v2.docking.geometric_admission_v2 import (
    HARD_REJECTION_MINIMUM_VDW_RATIO,
    PAIR_TRAVERSAL_ORDER,
    POCKET_ESCAPE_DEFINITION,
    SEVERE_PENETRATION_REJECTION_CODE,
    SPHERE_OVERLAP_PROXY_DEFINITION,
    TYPED_GENERATION_FAILURE_STATUS,
    TYPED_MISSING_FEATURE_REJECTION_CODE,
    GeometricAdmissionV2,
    GeometricAdmissionV2Error,
    evaluate_geometric_admission_metrics_one_python,
)
import betelgeuze_engine_v2.docking.geometric_admission_v2 as geometric_module
from betelgeuze_engine_v2.docking.mixed64_allocation import (
    RETAINED_SOURCE_INDICES,
    TRUE_CONFORMER_RANKS,
    V7_CONTROL_SOURCE_INDICES,
    Mixed64AtomicFeatureEvidence,
    Mixed64ConformerSourceEvidence,
    Mixed64FeatureEvidence,
    Mixed64RetainedSourceEvidence,
    Mixed64V7ControlSourceEvidence,
    build_fixed_mixed64_allocation,
)


def _fixed64(
    coordinates: tuple[tuple[float, float, float], ...],
) -> tuple[tuple[tuple[float, float, float], ...], ...]:
    return (coordinates,) * 64


def _allocation(*, all_available: bool = True):
    def digest(label: str) -> str:
        return hashlib.sha256(label.encode("ascii")).hexdigest()

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
    return build_fixed_mixed64_allocation(
        Mixed64FeatureEvidence(
            exact_v11_source_receipt_sha256=digest("v11-source"),
            prepared_ligand_topology_sha256=digest("ligand-topology"),
            prepared_receptor_topology_sha256=digest("receptor-topology"),
            feature_extractor_policy_sha256=digest("feature-policy"),
            v7_control_sources=(
                tuple(
                    Mixed64V7ControlSourceEvidence(
                        source_index=index,
                        proposal_mode=(
                            "pocket_centered_control"
                            if index < 8
                            else "uniform_source_control"
                        ),
                        proposal_sha256=digest(f"v7-proposal-{index}"),
                        coordinate_sha256=digest(f"v7-coordinate-{index}"),
                        proposal_lineage_sha256=digest(f"v7-lineage-{index}"),
                        source_receipt_sha256=digest(f"v7-receipt-{index}"),
                    )
                    for index in V7_CONTROL_SOURCE_INDICES
                )
                if all_available
                else ()
            ),
            atomic_features=(
                tuple(
                    Mixed64AtomicFeatureEvidence(
                        kind=kind,
                        atom_indices=indices,
                        source_receipt_sha256=digest(f"feature-source-{kind}"),
                        geometry_receipt_sha256=digest(f"feature-geometry-{kind}"),
                    )
                    for kind, indices in feature_rows
                )
                if all_available
                else ()
            ),
            conformer_sources=(
                tuple(
                    Mixed64ConformerSourceEvidence(
                        rank=rank,
                        proposal_sha256=digest(f"conformer-proposal-{rank}"),
                        coordinate_sha256=digest(f"conformer-coordinate-{rank}"),
                        source_receipt_sha256=digest(f"conformer-receipt-{rank}"),
                    )
                    for rank in TRUE_CONFORMER_RANKS
                )
                if all_available
                else ()
            ),
            retained_sources=(
                tuple(
                    Mixed64RetainedSourceEvidence(
                        source_index=index,
                        proposal_sha256=digest(f"retained-proposal-{index}"),
                        coordinate_sha256=digest(f"retained-coordinate-{index}"),
                        source_receipt_sha256=digest(f"retained-receipt-{index}"),
                    )
                    for index in RETAINED_SOURCE_INDICES
                )
                if all_available
                else ()
            ),
        )
    )


def test_exact_full_pair_metrics_overlap_proxy_and_pocket_escape_receipt() -> None:
    candidates = _fixed64(((0.0, 0.0, 0.0), (4.0, 0.0, 0.0)))
    batch = GeometricAdmissionV2().admit_fixed64(
        candidates,
        allocation=_allocation(),
        ligand_vdw_radii=(1.0, 1.0),
        ligand_heavy_atom_mask=(True, False),
        receptor_coordinates=((1.0, 0.0, 0.0), (10.0, 0.0, 0.0)),
        receptor_vdw_radii=(1.0, 1.0),
        pocket_center=(0.0, 0.0, 0.0),
        pocket_radius=2.0,
    )
    metrics = batch.decisions[0].metrics

    assert metrics.ligand_atom_count == 2
    assert metrics.receptor_atom_count == 2
    assert metrics.exact_pair_count == 4
    assert metrics.raw_minimum_distance_angstrom == pytest.approx(1.0)
    assert metrics.minimum_vdw_surface_gap_angstrom == pytest.approx(-1.0)
    assert metrics.minimum_vdw_ratio == pytest.approx(0.5)
    assert metrics.penetration_pair_count == 1
    assert metrics.unique_ligand_penetration_atom_count == 1
    assert metrics.unique_ligand_heavy_atom_penetration_count == 1
    assert metrics.sphere_overlap_proxy_angstrom3 == pytest.approx(5.0 * math.pi / 12.0)
    # Atom center at x=4 with radius 1 extends 3 A beyond a radius-2 pocket.
    assert metrics.pocket_escape_angstrom == pytest.approx(3.0)
    document = metrics.to_dict()
    assert document["pair_traversal_order"] == PAIR_TRAVERSAL_ORDER
    assert (
        document["sphere_overlap_proxy_definition"] == SPHERE_OVERLAP_PROXY_DEFINITION
    )
    assert document["pocket_escape_definition"] == POCKET_ESCAPE_DEFINITION


def test_only_ratio_below_point55_rejects_and_all_slots_are_preserved() -> None:
    candidates = (
        (((0.0, 0.0, 0.0),),)
        + (((2.0 * HARD_REJECTION_MINIMUM_VDW_RATIO, 0.0, 0.0),),)
        + (((1.5, 0.0, 0.0),),) * 62
    )
    batch = GeometricAdmissionV2().admit_fixed64(
        candidates,
        allocation=_allocation(),
        ligand_vdw_radii=(1.0,),
        ligand_heavy_atom_mask=(True,),
        receptor_coordinates=((0.0, 0.0, 0.0),),
        receptor_vdw_radii=(1.0,),
        pocket_center=(0.0, 0.0, 0.0),
        pocket_radius=0.5,
    )

    assert len(batch.decisions) == 64
    assert tuple(decision.slot_index for decision in batch.decisions) == tuple(
        range(64)
    )
    assert batch.nonaccepted_count == 1
    assert batch.geometric_rejected_count == 1
    assert batch.typed_generation_failure_count == 0
    assert batch.accepted_count == 63
    assert batch.decisions[0].rejection_code == (SEVERE_PENETRATION_REJECTION_CODE)
    assert batch.decisions[0].rank_eligible is False
    boundary = batch.decisions[1]
    assert boundary.metrics.minimum_vdw_ratio == (HARD_REJECTION_MINIMUM_VDW_RATIO)
    assert boundary.accepted is True
    assert boundary.rank_eligible is True
    # Slots 2..63 still penetrate and escape the pocket, but neither diagnostic
    # is a second hard rejection rule.
    assert all(
        decision.metrics.penetration_pair_count == 1
        and decision.metrics.sphere_overlap_proxy_angstrom3 > 0.0
        and decision.metrics.pocket_escape_angstrom > 0.0
        and decision.accepted
        and decision.rank_eligible
        for decision in batch.decisions[2:]
    )
    receipt = batch.to_dict()
    assert receipt["candidate_denominator"] == 64
    assert receipt["exact_inputs"]["candidate_coordinates_binary64_hex"][1] == [
        [
            (2.0 * HARD_REJECTION_MINIMUM_VDW_RATIO).hex(),
            "0x0.0p+0",
            "0x0.0p+0",
        ]
    ]
    assert receipt["exact_inputs"]["ligand_heavy_atom_mask"] == [True]
    assert receipt["rejected_slots_preserved"] is True
    assert receipt["rejected_slots_rank_ineligible"] is True
    assert receipt["molecular_execution_authorized"] is False


def test_sphere_containment_uses_smaller_sphere_volume_in_overlap_proxy() -> None:
    batch = GeometricAdmissionV2().admit_fixed64(
        _fixed64(((0.0, 0.0, 0.0),)),
        allocation=_allocation(),
        ligand_vdw_radii=(1.0,),
        ligand_heavy_atom_mask=(True,),
        receptor_coordinates=((0.0, 0.0, 0.0),),
        receptor_vdw_radii=(2.0,),
        pocket_center=(0.0, 0.0, 0.0),
        pocket_radius=10.0,
    )

    assert batch.decisions[0].metrics.sphere_overlap_proxy_angstrom3 == (
        pytest.approx((4.0 / 3.0) * math.pi)
    )


def test_admission_is_deterministic_and_has_no_score_or_result_inputs() -> None:
    kwargs = {
        "allocation": _allocation(),
        "ligand_vdw_radii": (1.0,),
        "ligand_heavy_atom_mask": (True,),
        "receptor_coordinates": ((5.0, 0.0, 0.0),),
        "receptor_vdw_radii": (1.0,),
        "pocket_center": (0.0, 0.0, 0.0),
        "pocket_radius": 3.0,
    }
    candidates = _fixed64(((0.0, 0.0, 0.0),))
    first = GeometricAdmissionV2().admit_fixed64(candidates, **kwargs)
    second = GeometricAdmissionV2().admit_fixed64(candidates, **kwargs)

    assert first.receipt_sha256 == second.receipt_sha256
    parameters = set(inspect.signature(GeometricAdmissionV2.admit_fixed64).parameters)
    forbidden = {
        "score",
        "rank",
        "native_pose",
        "reference_pose",
        "rmsd",
        "benchmark_outcome",
        "fresh_holdout",
    }
    assert forbidden.isdisjoint(parameters)
    # The current pipeline's count-only statuses API is intentionally not
    # emulated: this component requires exact candidate geometry evidence.
    assert not hasattr(GeometricAdmissionV2(), "statuses")


def test_non_fixed_denominator_and_cross_wired_atom_counts_fail_closed() -> None:
    admission = GeometricAdmissionV2()
    kwargs = {
        "allocation": _allocation(),
        "ligand_vdw_radii": (1.0,),
        "ligand_heavy_atom_mask": (True,),
        "receptor_coordinates": ((5.0, 0.0, 0.0),),
        "receptor_vdw_radii": (1.0,),
        "pocket_center": (0.0, 0.0, 0.0),
        "pocket_radius": 3.0,
    }
    with pytest.raises(GeometricAdmissionV2Error, match="exactly 64"):
        admission.admit_fixed64(
            _fixed64(((0.0, 0.0, 0.0),))[:-1],
            **kwargs,
        )

    cross_wired = list(_fixed64(((0.0, 0.0, 0.0),)))
    cross_wired[63] = ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0))
    with pytest.raises(GeometricAdmissionV2Error, match="atom denominator"):
        admission.admit_fixed64(tuple(cross_wired), **kwargs)


def test_missing_feature_slots_preserve_denominator_without_geometry() -> None:
    allocation = _allocation(all_available=False)
    coordinates = tuple(
        ((2.0, 0.0, 0.0),) if slot.generation_eligible else None
        for slot in allocation.slots
    )
    batch = GeometricAdmissionV2().admit_fixed64(
        coordinates,
        allocation=allocation,
        ligand_vdw_radii=(1.0,),
        ligand_heavy_atom_mask=(True,),
        receptor_coordinates=((5.0, 0.0, 0.0),),
        receptor_vdw_radii=(1.0,),
        pocket_center=(0.0, 0.0, 0.0),
        pocket_radius=3.0,
    )

    assert len(batch.decisions) == 64
    assert batch.typed_generation_failure_count == 52
    assert batch.geometric_rejected_count == 0
    assert batch.nonaccepted_count == 52
    assert batch.accepted_count == 12
    for slot, decision in zip(allocation.slots, batch.decisions, strict=True):
        assert decision.allocation_slot_receipt_sha256 == slot.receipt_sha256
        assert decision.lane == slot.lane
        if slot.generation_eligible:
            assert decision.metrics is not None
            assert decision.candidate_coordinate_sha256 is not None
        else:
            assert decision.status == TYPED_GENERATION_FAILURE_STATUS
            assert decision.rejection_code == TYPED_MISSING_FEATURE_REJECTION_CODE
            assert decision.metrics is None
            assert decision.candidate_coordinate_sha256 is None
            assert decision.rank_eligible is False

    fabricated = list(coordinates)
    fabricated[44] = ((2.0, 0.0, 0.0),)
    with pytest.raises(GeometricAdmissionV2Error, match="fabricated coordinates"):
        GeometricAdmissionV2().admit_fixed64(
            tuple(fabricated),
            allocation=allocation,
            ligand_vdw_radii=(1.0,),
            ligand_heavy_atom_mask=(True,),
            receptor_coordinates=((5.0, 0.0, 0.0),),
            receptor_vdw_radii=(1.0,),
            pocket_center=(0.0, 0.0, 0.0),
            pocket_radius=3.0,
        )

    missing_ready = list(coordinates)
    first_ready_slot = next(
        slot.slot_index for slot in allocation.slots if slot.generation_eligible
    )
    missing_ready[first_ready_slot] = None
    with pytest.raises(GeometricAdmissionV2Error, match="missing candidate"):
        GeometricAdmissionV2().admit_fixed64(
            tuple(missing_ready),
            allocation=allocation,
            ligand_vdw_radii=(1.0,),
            ligand_heavy_atom_mask=(True,),
            receptor_coordinates=((5.0, 0.0, 0.0),),
            receptor_vdw_radii=(1.0,),
            pocket_center=(0.0, 0.0, 0.0),
            pocket_radius=3.0,
        )


def test_heavy_atom_penetration_count_uses_exact_bound_mask() -> None:
    batch = GeometricAdmissionV2().admit_fixed64(
        _fixed64(((0.0, 0.0, 0.0), (4.0, 0.0, 0.0))),
        allocation=_allocation(),
        ligand_vdw_radii=(1.0, 1.0),
        ligand_heavy_atom_mask=(False, True),
        receptor_coordinates=((1.0, 0.0, 0.0),),
        receptor_vdw_radii=(1.0,),
        pocket_center=(0.0, 0.0, 0.0),
        pocket_radius=10.0,
    )

    metrics = batch.decisions[0].metrics
    assert metrics is not None
    assert metrics.unique_ligand_penetration_atom_count == 1
    assert metrics.unique_ligand_heavy_atom_penetration_count == 0
    assert len(batch.ligand_heavy_atom_mask_sha256) == 64

    list_mask_batch = GeometricAdmissionV2().admit_fixed64(
        _fixed64(((0.0, 0.0, 0.0), (4.0, 0.0, 0.0))),
        allocation=_allocation(),
        ligand_vdw_radii=(1.0, 1.0),
        ligand_heavy_atom_mask=iter((False, True)),
        receptor_coordinates=((1.0, 0.0, 0.0),),
        receptor_vdw_radii=(1.0,),
        pocket_center=(0.0, 0.0, 0.0),
        pocket_radius=10.0,
    )
    assert list_mask_batch.ligand_heavy_atom_mask_sha256 == (
        batch.ligand_heavy_atom_mask_sha256
    )

    with pytest.raises(GeometricAdmissionV2Error, match="exact booleans"):
        GeometricAdmissionV2().admit_fixed64(
            _fixed64(((0.0, 0.0, 0.0), (4.0, 0.0, 0.0))),
            allocation=_allocation(),
            ligand_vdw_radii=(1.0, 1.0),
            ligand_heavy_atom_mask=(False, 1),
            receptor_coordinates=((1.0, 0.0, 0.0),),
            receptor_vdw_radii=(1.0,),
            pocket_center=(0.0, 0.0, 0.0),
            pocket_radius=10.0,
        )


def test_resealed_metrics_and_allocation_cross_wires_fail_closed() -> None:
    batch = GeometricAdmissionV2().admit_fixed64(
        _fixed64(((0.0, 0.0, 0.0),)),
        allocation=_allocation(),
        ligand_vdw_radii=(1.0,),
        ligand_heavy_atom_mask=(True,),
        receptor_coordinates=((0.0, 0.0, 0.0),),
        receptor_vdw_radii=(1.0,),
        pocket_center=(0.0, 0.0, 0.0),
        pocket_radius=1.0,
    )
    decision = batch.decisions[0]
    assert decision.metrics is not None
    forged_metrics = replace(
        decision.metrics,
        minimum_vdw_ratio=1.0,
        penetration_pair_count=0,
        unique_ligand_penetration_atom_count=0,
        unique_ligand_heavy_atom_penetration_count=0,
        sphere_overlap_proxy_angstrom3=0.0,
    )
    forged_decision = replace(
        decision,
        metrics=forged_metrics,
        status="accepted",
        rejection_code=None,
        rank_eligible=True,
    )
    with pytest.raises(
        GeometricAdmissionV2Error,
        match="must use the bounded evaluator factory",
    ):
        replace(
            batch,
            decisions=(forged_decision, *batch.decisions[1:]),
        )

    with pytest.raises(
        GeometricAdmissionV2Error,
        match="must use the bounded evaluator factory",
    ):
        replace(batch, allocation=_allocation(all_available=False))


def test_exact_input_coordinate_permutation_and_mask_tamper_fail_closed() -> None:
    coordinates = (
        (((2.0, 0.0, 0.0),),) + (((3.0, 0.0, 0.0),),) + (((4.0, 0.0, 0.0),),) * 62
    )
    batch = GeometricAdmissionV2().admit_fixed64(
        coordinates,
        allocation=_allocation(),
        ligand_vdw_radii=(1.0,),
        ligand_heavy_atom_mask=(True,),
        receptor_coordinates=((0.0, 0.0, 0.0),),
        receptor_vdw_radii=(1.0,),
        pocket_center=(0.0, 0.0, 0.0),
        pocket_radius=5.0,
    )
    exact_inputs = batch._exact_inputs
    permuted = replace(
        exact_inputs,
        candidate_coordinates=(
            exact_inputs.candidate_coordinates[1],
            exact_inputs.candidate_coordinates[0],
            *exact_inputs.candidate_coordinates[2:],
        ),
    )
    with pytest.raises(
        GeometricAdmissionV2Error,
        match="must use the bounded evaluator factory",
    ):
        replace(batch, _exact_inputs=permuted)

    object.__setattr__(
        exact_inputs,
        "ligand_heavy_atom_mask",
        (False,),
    )
    with pytest.raises(GeometricAdmissionV2Error, match="exact inputs changed"):
        batch.to_dict()


def test_all_external_iterables_are_bounded_before_materialization() -> None:
    admission = GeometricAdmissionV2()
    common = {
        "allocation": _allocation(),
        "ligand_vdw_radii": (1.0,),
        "ligand_heavy_atom_mask": (True,),
        "receptor_coordinates": ((5.0, 0.0, 0.0),),
        "receptor_vdw_radii": (1.0,),
        "pocket_center": (0.0, 0.0, 0.0),
        "pocket_radius": 3.0,
    }
    candidates = _fixed64(((0.0, 0.0, 0.0),))

    with pytest.raises(GeometricAdmissionV2Error, match="maximum count 64"):
        admission.admit_fixed64(repeat(((0.0, 0.0, 0.0),)), **common)
    with pytest.raises(GeometricAdmissionV2Error, match="maximum count 512"):
        admission.admit_fixed64(
            candidates,
            **{**common, "ligand_vdw_radii": repeat(1.0)},
        )
    with pytest.raises(GeometricAdmissionV2Error, match="maximum count 512"):
        admission.admit_fixed64(
            candidates,
            **{**common, "ligand_heavy_atom_mask": repeat(True)},
        )
    with pytest.raises(GeometricAdmissionV2Error, match="maximum count 4096"):
        admission.admit_fixed64(
            candidates,
            **{
                **common,
                "receptor_coordinates": repeat((5.0, 0.0, 0.0)),
            },
        )
    with pytest.raises(GeometricAdmissionV2Error, match="maximum count 4096"):
        admission.admit_fixed64(
            candidates,
            **{**common, "receptor_vdw_radii": repeat(1.0)},
        )
    with pytest.raises(GeometricAdmissionV2Error, match="maximum count 3"):
        admission.admit_fixed64(
            candidates,
            **{**common, "pocket_center": repeat(0.0)},
        )
    with pytest.raises(GeometricAdmissionV2Error, match="maximum count 512"):
        admission.admit_fixed64(
            (repeat((0.0, 0.0, 0.0)),) + candidates[1:],
            **common,
        )


def test_over_capacity_counts_and_pair_work_fail_before_traversal() -> None:
    admission = GeometricAdmissionV2()
    common = {
        "allocation": _allocation(),
        "ligand_vdw_radii": (1.0,),
        "ligand_heavy_atom_mask": (True,),
        "receptor_coordinates": ((5.0, 0.0, 0.0),),
        "receptor_vdw_radii": (1.0,),
        "pocket_center": (0.0, 0.0, 0.0),
        "pocket_radius": 3.0,
    }
    with pytest.raises(GeometricAdmissionV2Error, match="maximum count 64"):
        admission.admit_fixed64(
            _fixed64(((0.0, 0.0, 0.0),)) + (((0.0, 0.0, 0.0),),),
            **common,
        )
    with pytest.raises(GeometricAdmissionV2Error, match="maximum count 512"):
        admission.admit_fixed64(
            _fixed64(((0.0, 0.0, 0.0),) * 513),
            **common,
        )
    with pytest.raises(GeometricAdmissionV2Error, match="maximum count 4096"):
        admission.admit_fixed64(
            _fixed64(((0.0, 0.0, 0.0),)),
            **{
                **common,
                "receptor_coordinates": ((5.0, 0.0, 0.0),) * 4097,
            },
        )

    # 64 * 65 * 4096 = 17,039,360, above the explicit 16,777,216 cap.
    with pytest.raises(GeometricAdmissionV2Error, match="pair work exceeds"):
        admission.admit_fixed64(
            _fixed64(((0.0, 0.0, 0.0),) * 65),
            allocation=_allocation(),
            ligand_vdw_radii=(1.0,) * 65,
            ligand_heavy_atom_mask=(True,) * 65,
            receptor_coordinates=((5.0, 0.0, 0.0),) * 4096,
            receptor_vdw_radii=(1.0,) * 4096,
            pocket_center=(0.0, 0.0, 0.0),
            pocket_radius=3.0,
        )


@pytest.mark.parametrize(
    ("replacement", "message"),
    (
        ({"candidate_coordinates": _fixed64(((1e308, 0.0, 0.0),))}, "coordinate"),
        ({"ligand_vdw_radii": (1e308,)}, "vdW radius"),
        ({"receptor_coordinates": ((1e308, 0.0, 0.0),)}, "coordinate"),
        ({"receptor_vdw_radii": (1e308,)}, "vdW radius"),
        ({"pocket_center": (1e308, 0.0, 0.0)}, "coordinate"),
        ({"pocket_radius": 1e308}, "pocket safety envelope"),
    ),
)
def test_extreme_finite_geometry_fails_closed_without_overflow(
    replacement: dict[str, object],
    message: str,
) -> None:
    arguments: dict[str, object] = {
        "candidate_coordinates": _fixed64(((0.0, 0.0, 0.0),)),
        "allocation": _allocation(),
        "ligand_vdw_radii": (1.0,),
        "ligand_heavy_atom_mask": (True,),
        "receptor_coordinates": ((5.0, 0.0, 0.0),),
        "receptor_vdw_radii": (1.0,),
        "pocket_center": (0.0, 0.0, 0.0),
        "pocket_radius": 3.0,
    }
    arguments.update(replacement)
    with pytest.raises(GeometricAdmissionV2Error, match=message):
        GeometricAdmissionV2().admit_fixed64(**arguments)  # type: ignore[arg-type]


def test_batch_persists_allocation_and_does_not_recompute_cartesian_metrics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    allocation = _allocation()
    original_evaluate_metrics = geometric_module._evaluate_metrics
    evaluation_count = 0

    def counted_evaluation(*args: object, **kwargs: object):
        nonlocal evaluation_count
        evaluation_count += 1
        return original_evaluate_metrics(*args, **kwargs)

    monkeypatch.setattr(
        geometric_module,
        "_evaluate_metrics",
        counted_evaluation,
    )
    batch = GeometricAdmissionV2().admit_fixed64(
        _fixed64(((0.0, 0.0, 0.0),)),
        allocation=allocation,
        ligand_vdw_radii=(1.0,),
        ligand_heavy_atom_mask=(True,),
        receptor_coordinates=((5.0, 0.0, 0.0),),
        receptor_vdw_radii=(1.0,),
        pocket_center=(0.0, 0.0, 0.0),
        pocket_radius=3.0,
    )
    assert evaluation_count == 64

    def forbidden_recomputation(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("Cartesian metrics were recomputed")

    monkeypatch.setattr(
        geometric_module,
        "_derive_decisions",
        forbidden_recomputation,
    )
    document = batch.to_dict()
    assert batch.receipt_sha256 == document["receipt_sha256"]
    assert document["allocation"] == allocation.to_dict()
    assert (
        document["allocation"]["receipt_sha256"]
        == (document["allocation_receipt_sha256"])
    )


def test_duplicate_decision_and_post_init_tamper_fail_closed() -> None:
    batch = GeometricAdmissionV2().admit_fixed64(
        _fixed64(((0.0, 0.0, 0.0),)),
        allocation=_allocation(),
        ligand_vdw_radii=(1.0,),
        ligand_heavy_atom_mask=(True,),
        receptor_coordinates=((5.0, 0.0, 0.0),),
        receptor_vdw_radii=(1.0,),
        pocket_center=(0.0, 0.0, 0.0),
        pocket_radius=3.0,
    )
    duplicated = (batch.decisions[0], batch.decisions[0], *batch.decisions[2:])
    with pytest.raises(GeometricAdmissionV2Error, match="bounded evaluator factory"):
        replace(batch, decisions=duplicated)

    object.__setattr__(batch, "decisions", duplicated)
    with pytest.raises(GeometricAdmissionV2Error, match="decisions changed"):
        batch.to_dict()


def test_public_one_candidate_reference_is_the_fixed64_kernel() -> None:
    ligand = ((0.0, 0.0, 0.0), (3.0, 0.0, 0.0))
    ligand_radii = (1.0, 1.2)
    heavy_mask = (True, False)
    receptor = ((1.0, 0.0, 0.0), (10.0, 0.0, 0.0))
    receptor_radii = (1.0, 1.5)
    center = (0.0, 0.0, 0.0)
    radius = 4.0
    direct = evaluate_geometric_admission_metrics_one_python(
        ligand,
        ligand_vdw_radii=ligand_radii,
        ligand_heavy_atom_mask=heavy_mask,
        receptor_coordinates=receptor,
        receptor_vdw_radii=receptor_radii,
        pocket_center=center,
        pocket_radius=radius,
    )
    batch = GeometricAdmissionV2().admit_fixed64(
        _fixed64(ligand),
        allocation=_allocation(),
        ligand_vdw_radii=ligand_radii,
        ligand_heavy_atom_mask=heavy_mask,
        receptor_coordinates=receptor,
        receptor_vdw_radii=receptor_radii,
        pocket_center=center,
        pocket_radius=radius,
    )

    assert batch.decisions[0].metrics is not None
    assert direct.to_dict() == batch.decisions[0].metrics.to_dict()
