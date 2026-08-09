from __future__ import annotations

from dataclasses import fields, replace
import hashlib
import inspect
import json

import pytest

from betelgeuze_engine_v2.docking.geometric_admission_v2 import (
    GeometricAdmissionV2,
)
from betelgeuze_engine_v2.docking.mixed64_allocation import (
    RETAINED_SOURCE_INDICES,
    TRUE_CONFORMER_RANKS,
    Mixed64AtomicFeatureEvidence,
    Mixed64ConformerSourceEvidence,
    Mixed64FeatureEvidence,
    Mixed64RetainedSourceEvidence,
    Mixed64V7ControlSourceEvidence,
    V7_CONTROL_SOURCE_INDICES,
    build_fixed_mixed64_allocation,
)
from betelgeuze_engine_v2.docking.pipeline_candidate_evidence_v2 import (
    ALLOCATION_FAILURE_STATUS,
    EXECUTION_FAILURE_STAGE_SCORING,
    EXECUTION_FAILURE_STAGE_VALIDITY,
    EXECUTION_FAILURE_STATUS,
    GEOMETRIC_REJECTION_STATUS,
    SCORED_SUCCESS_STATUS,
    PipelineCandidateEvidenceV2,
    PipelineCandidateEvidenceV2Error,
    PipelineCandidateRecordV2,
    PoseValidityReceiptV2,
    bind_pose_validity_receipt_v2,
    bind_proposal_execution_receipt_v2,
    bind_refinement_receipt_v2,
    bind_scorer_v1_evidence_v2,
    build_pipeline_candidate_evidence_v2,
)
from betelgeuze_engine_v2.docking.scorer_v1 import ScorerV1Error, ScorerV1Terms
from betelgeuze_engine_v2.docking.validity import PoseValidityResult


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode("ascii")).hexdigest()


def _receipt(document: dict[str, object]) -> dict[str, object]:
    observed = dict(document)
    observed["receipt_sha256"] = hashlib.sha256(
        json.dumps(
            document,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    ).hexdigest()
    return observed


def _coordinate_digest(x: float) -> str:
    return hashlib.sha256(
        json.dumps(
            [[float(x).hex(), 0.0.hex(), 0.0.hex()]],
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    ).hexdigest()


def _features(*, available: bool, slot_zero_coordinate: float = 5.0):
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
    return Mixed64FeatureEvidence(
        exact_v11_source_receipt_sha256=_digest("v11-source"),
        prepared_ligand_topology_sha256=_digest("ligand-topology"),
        prepared_receptor_topology_sha256=_digest("receptor-topology"),
        feature_extractor_policy_sha256=_digest("feature-policy"),
        atomic_features=(
            tuple(
                Mixed64AtomicFeatureEvidence(
                    kind=kind,
                    atom_indices=indices,
                    source_receipt_sha256=_digest(f"feature-source-{kind}"),
                    geometry_receipt_sha256=_digest(f"feature-geometry-{kind}"),
                )
                for kind, indices in feature_rows
            )
            if available
            else ()
        ),
        v7_control_sources=tuple(
            Mixed64V7ControlSourceEvidence(
                source_index=index,
                proposal_mode=(
                    "pocket_centered_control"
                    if index < 8
                    else "uniform_source_control"
                ),
                proposal_sha256=_digest(f"v7-control-proposal-{index}"),
                coordinate_sha256=_coordinate_digest(
                    slot_zero_coordinate if index == 0 else 5.0 + index / 10.0
                ),
                proposal_lineage_sha256=_digest(f"v7-control-lineage-{index}"),
                source_receipt_sha256=_digest(f"v7-control-receipt-{index}"),
            )
            for index in V7_CONTROL_SOURCE_INDICES
        ),
        conformer_sources=(
            tuple(
                Mixed64ConformerSourceEvidence(
                    rank=rank,
                    proposal_sha256=_digest(f"conformer-proposal-{rank}"),
                    coordinate_sha256=_digest(f"conformer-coordinate-{rank}"),
                    source_receipt_sha256=_digest(f"conformer-receipt-{rank}"),
                )
                for rank in TRUE_CONFORMER_RANKS
            )
            if available
            else ()
        ),
        retained_sources=(
            tuple(
                Mixed64RetainedSourceEvidence(
                    source_index=index,
                    proposal_sha256=_digest(f"retained-proposal-{index}"),
                    coordinate_sha256=_coordinate_digest(11.0 + position / 10.0),
                    source_receipt_sha256=_digest(f"retained-receipt-{index}"),
                )
                for position, index in enumerate(RETAINED_SOURCE_INDICES)
            )
            if available
            else ()
        ),
    )


def _geometric_batch(
    allocation,
    *,
    reject_slot_zero: bool = False,
    coordinate_bias: float = 0.0,
):
    coordinates = tuple(
        None
        if not slot.generation_eligible
        else (
            (
                coordinate_bias
                if reject_slot_zero and slot.slot_index == 0
                else 5.0 + coordinate_bias + slot.slot_index / 10.0,
                0.0,
                0.0,
            ),
        )
        for slot in allocation.slots
    )
    return GeometricAdmissionV2().admit_fixed64(
        allocation=allocation,
        candidate_coordinates=coordinates,
        ligand_vdw_radii=(1.0,),
        ligand_heavy_atom_mask=(True,),
        receptor_coordinates=((0.0, 0.0, 0.0),),
        receptor_vdw_radii=(1.0,),
        pocket_center=(0.0, 0.0, 0.0),
        pocket_radius=100.0,
    )


def _validity_receipt(
    *,
    result_sha256: str,
    coordinate_sha256: str,
    valid: bool,
    measurements: dict[str, float | int] | None = None,
    blockers: tuple[str, ...] | None = None,
) -> PoseValidityReceiptV2:
    checks = {
        "proper_rotation": valid,
        "bond_lengths_preserved": True,
        "ligand_self_clash_free": True,
        "receptor_ligand_clash_free": True,
        "declared_chirality_preserved": True,
        "inside_declared_pocket": True,
        "element_vdw_ligand_overlap_free": True,
        "element_vdw_receptor_overlap_free": True,
    }
    return bind_pose_validity_receipt_v2(
        result_proposal_sha256=result_sha256,
        coordinate_sha256=coordinate_sha256,
        validity_context_fingerprint_sha256=_digest("validity-context"),
        validity_config_fingerprint_sha256=_digest("validity-config"),
        evaluator_implementation_source_sha256=_digest("validity-source"),
        result=PoseValidityResult(
            checks=checks,
            evaluated_checks={name: True for name in checks},
            complete=True,
            valid_within_evaluated_scope=valid,
            measurements=(
                {"synthetic_measurement": 1.0}
                if measurements is None
                else measurements
            ),
            blockers=(
                (() if valid else ("synthetic_pose_invalid",))
                if blockers is None
                else blockers
            ),
            not_evaluated_reasons={},
        ),
    )


def _scorer_terms(
    *,
    result_sha256: str,
    score: float,
    receptor_candidate_pair_count: int = 1,
) -> ScorerV1Terms:
    return ScorerV1Terms(
        proposal_fingerprint_sha256=result_sha256,
        authority_input_receipt_sha256=_digest("authority"),
        context_fingerprint_sha256=_digest("context"),
        config_fingerprint_sha256=_digest("config"),
        backend_receipt_sha256=_digest("backend"),
        typed_vdw=score,
        electrostatics=0.0,
        directional_hbond=0.0,
        hydrophobic_contact=0.0,
        desolvation_proxy=0.0,
        torsion_energy=0.0,
        ligand_strain=0.0,
        weak_pocket_prior=0.0,
        total_score=score,
        receptor_candidate_pair_count=receptor_candidate_pair_count,
        ligand_pair_count=0,
        hbond_count=0,
        hydrophobic_contact_count=0,
        buried_polar_count=0,
    )


def _success_record(
    slot_index: int,
    source_coordinate_sha256: str,
    *,
    allocation_slot,
    score: float,
    valid: bool = True,
    generator_component_id: str = (
        "betelgeuze.engine_v2_fixed64_generator/1.0.0"
    ),
    refiner_config_sha256: str | None = None,
    refiner_implementation_source_sha256: str | None = None,
    refinement_source_schema_id: str = (
        "betelgeuze.engine_v2_interaction_aware_torsion_contact_receipt/7.0.0"
    ),
) -> PipelineCandidateRecordV2:
    source_sha256 = (
        allocation_slot.selected_generation_parent_proposal_sha256
        if allocation_slot.generation_parent_role == "exact_passthrough_parent"
        else _digest(f"source-{slot_index}")
    )
    result_sha256 = _digest(f"result-{slot_index}")
    scorer_terms = _scorer_terms(
        result_sha256=result_sha256,
        score=score,
    )
    result_coordinate_sha256 = _digest(f"result-coordinate-{slot_index}")
    if refiner_config_sha256 is None:
        refiner_config_sha256 = _digest("refiner-config")
    if refiner_implementation_source_sha256 is None:
        refiner_implementation_source_sha256 = _digest("refiner-source")
    refinement = bind_refinement_receipt_v2(
        source_proposal_sha256=source_sha256,
        result_proposal_sha256=result_sha256,
        source_coordinate_sha256=source_coordinate_sha256,
        result_coordinate_sha256=result_coordinate_sha256,
        refiner_config_sha256=refiner_config_sha256,
        refiner_implementation_source_sha256=(refiner_implementation_source_sha256),
        source_receipt=_receipt(
            {
                "schema_id": refinement_source_schema_id,
                "source_proposal_sha256": source_sha256,
                "config_sha256": refiner_config_sha256,
                "pre_coordinates_sha256": source_coordinate_sha256,
                "post_coordinates_sha256": result_coordinate_sha256,
                "accepted_steps": 0,
                "scientifically_validated": False,
            }
        ),
    )
    scorer_evidence = bind_scorer_v1_evidence_v2(
        terms=scorer_terms,
        search_row_sha256=_digest(f"search-row-{slot_index}"),
        search_term_row_receipt_sha256=_digest(f"term-row-{slot_index}"),
        source_search_result_receipt_sha256=_digest("search-result"),
        scorer_implementation_source_sha256=_digest("scorer-source"),
    )
    return PipelineCandidateRecordV2(
        slot_index=slot_index,
        source_proposal_sha256=source_sha256,
        result_proposal_sha256=result_sha256,
        proposal_execution_receipt=bind_proposal_execution_receipt_v2(
            slot_index=slot_index,
            allocation_slot_receipt_sha256=allocation_slot.receipt_sha256,
            allocation_source_receipt_sha256s=(
                allocation_slot.selected_source_receipt_sha256s
            ),
            generation_parent_proposal_sha256=(
                allocation_slot.selected_generation_parent_proposal_sha256
            ),
            generation_parent_coordinate_sha256=(
                allocation_slot.selected_generation_parent_coordinate_sha256
            ),
            source_proposal_sha256=source_sha256,
            source_coordinate_sha256=source_coordinate_sha256,
            generation_input_receipt_sha256=_digest("v11-source"),
            generator_config_sha256=_digest("generator-config"),
            generator_implementation_source_sha256=_digest("generator-source"),
            generator_component_id=generator_component_id,
        ),
        scorer_evidence=scorer_evidence,
        pose_validity_receipt=_validity_receipt(
            result_sha256=result_sha256,
            coordinate_sha256=result_coordinate_sha256,
            valid=valid,
        ),
        refinement_receipt=refinement,
    )


def test_exact64_success_rederives_stable_rank_top1_top5_and_authority_false() -> None:
    allocation = build_fixed_mixed64_allocation(_features(available=True))
    geometric = _geometric_batch(allocation)
    scores = tuple(
        0.0 if slot_index in {2, 5} else 10.0 + slot_index for slot_index in range(64)
    )
    records = tuple(
        _success_record(
            slot_index,
            geometric.decisions[slot_index].candidate_coordinate_sha256,
            allocation_slot=allocation.slots[slot_index],
            score=scores[slot_index],
        )
        for slot_index in range(64)
    )
    batch = build_pipeline_candidate_evidence_v2(
        allocation,
        geometric,
        records,
    )

    assert len(batch.candidates) == 64
    assert batch.scored_success_count == 64
    assert batch.typed_failure_count == 0
    assert batch.stable_ranking_slot_indices[:5] == (2, 5, 0, 1, 3)
    assert batch.top1_slot_index == 2
    assert batch.top5_slot_indices == (2, 5, 0, 1, 3)
    assert batch.geometric_admission_batch is geometric
    assert all(
        candidate.geometric_admission_batch_receipt_sha256 == geometric.receipt_sha256
        for candidate in batch.candidates
    )
    assert batch.candidates[2].stable_rank == 1
    assert batch.candidates[2].top1_member is True
    assert all(
        candidate.top5_member is (candidate.slot_index in {2, 5, 0, 1, 3})
        for candidate in batch.candidates
    )
    assert all(
        candidate.status == SCORED_SUCCESS_STATUS
        and candidate.evidence_complete
        and candidate.rank_eligible
        and candidate.scorer_terms is not None
        and candidate.pose_validity_receipt is not None
        and candidate.refinement_receipt is not None
        for candidate in batch.candidates
    )
    document = batch.to_dict()
    assert document["candidate_denominator"] == 64
    assert document["allocation"] == allocation.to_dict()
    assert document["denominator_failure_complete"] is True
    assert document["denominator_failure_completeness_scope"] == (
        "allocation_and_supported_post_proposal_structural_stages_only"
    )
    assert document["activation_evidence_eligible"] is False
    assert document["activation_evidence_blockers"] == [
        "uniform_source_control_lineage_not_rederived",
        "independent_so3_base_source_not_bound",
        "independent_so3_orientation_receipt_not_implemented",
        "single_anchor_placement_receipt_not_implemented",
        "proposal_generation_failure_receipt_not_implemented",
        "post_refinement_geometric_admission_not_implemented",
        "source_parent_payload_rederivation_not_implemented",
        "producer_attestation_not_implemented",
        "score_term_reexecution_not_implemented",
        "pose_validity_reexecution_not_implemented",
    ]
    for slot_index in (*range(24), *range(60, 64)):
        slot = allocation.slots[slot_index]
        candidate = batch.candidates[slot_index]
        assert candidate.source_proposal_sha256 == (
            slot.selected_generation_parent_proposal_sha256
        )
        assert candidate.source_coordinate_sha256 == (
            slot.selected_generation_parent_coordinate_sha256
        )
    for slot_index in range(36, 44):
        slot = allocation.slots[slot_index]
        candidate = batch.candidates[slot_index]
        assert candidate.proposal_execution_receipt is not None
        assert candidate.proposal_execution_receipt.generation_parent_proposal_sha256 == (
            slot.selected_generation_parent_proposal_sha256
        )
        assert candidate.proposal_execution_receipt.generation_parent_coordinate_sha256 == (
            slot.selected_generation_parent_coordinate_sha256
        )
        assert candidate.source_proposal_sha256 != (
            slot.selected_generation_parent_proposal_sha256
        )
        assert candidate.source_coordinate_sha256 != (
            slot.selected_generation_parent_coordinate_sha256
        )
    assert all(
        candidate["proposal_execution_receipt"]["producer_attested"] is False
        and candidate["scorer_v1_evidence"]["producer_attested"] is False
        and candidate["pose_validity_receipt"]["producer_attested"] is False
        and candidate["refinement_receipt"]["producer_attested"] is False
        for candidate in document["candidates"]
    )
    assert document["evidence_completion_flags_caller_supplied"] is False
    assert document["rank_eligibility_caller_supplied"] is False
    assert document["top_k_membership_caller_supplied"] is False
    for authority_name in (
        "historical_execution_authorized",
        "fresh_holdout_execution_authorized",
        "molecular_execution_authorized",
        "product_mutation_authorized",
        "existing_rank_auto_change_authorized",
        "customer_pose_emission_authorized",
        "public_benchmark_execution_authorized",
        "public_or_scientific_claim_authorized",
        "stage0_admission_authority",
    ):
        assert document[authority_name] is False


def test_complete_geometric_batch_and_allocation_binding_reject_cross_wiring() -> None:
    allocation = build_fixed_mixed64_allocation(_features(available=True))
    first_geometric = _geometric_batch(allocation)
    records = tuple(
        _success_record(
            slot_index,
            first_geometric.decisions[slot_index].candidate_coordinate_sha256,
            allocation_slot=allocation.slots[slot_index],
            score=float(slot_index),
        )
        for slot_index in range(64)
    )
    built = build_pipeline_candidate_evidence_v2(
        allocation,
        first_geometric,
        records,
    )

    second_geometric = _geometric_batch(allocation, coordinate_bias=1.0)
    with pytest.raises(
        PipelineCandidateEvidenceV2Error,
        match="geometric admission batch evidence is cross-wired",
    ):
        replace(built, geometric_admission_batch=second_geometric)

    different_allocation = build_fixed_mixed64_allocation(_features(available=False))
    different_geometric = _geometric_batch(different_allocation)
    with pytest.raises(
        PipelineCandidateEvidenceV2Error,
        match="batch allocation receipt is cross-wired",
    ):
        build_pipeline_candidate_evidence_v2(
            allocation,
            different_geometric,
            records,
        )

    document = built.to_dict()
    assert document["geometric_admission_batch_receipt_sha256"] == (
        first_geometric.receipt_sha256
    )
    assert document["geometric_admission_batch"] == first_geometric.to_dict()


def test_complete_but_invalid_pose_remains_primary_top1_and_is_reported() -> None:
    allocation = build_fixed_mixed64_allocation(_features(available=True))
    geometric = _geometric_batch(allocation)
    records = tuple(
        _success_record(
            slot_index,
            geometric.decisions[slot_index].candidate_coordinate_sha256,
            allocation_slot=allocation.slots[slot_index],
            score=float(slot_index),
            valid=slot_index != 0,
        )
        for slot_index in range(64)
    )
    batch = build_pipeline_candidate_evidence_v2(
        allocation,
        geometric,
        records,
    )
    invalid = batch.candidates[0]

    assert invalid.status == SCORED_SUCCESS_STATUS
    assert invalid.evidence_complete is True
    assert invalid.pose_validity_receipt is not None
    assert invalid.pose_validity_receipt.valid is False
    assert invalid.rank_eligible is True
    assert invalid.stable_rank == 1
    assert invalid.valid_rank_eligible is False
    assert invalid.selection_eligible is False
    assert invalid.stable_valid_rank is None
    assert batch.top1_slot_index == 0
    assert batch.top1_pose_valid is False
    assert batch.invalid_top1 is True
    assert batch.valid_top1_slot_index == 1
    assert batch.valid_top5_slot_indices == (1, 2, 3, 4, 5)


def test_validity_stage_failure_preserves_complete_score_and_primary_rank() -> None:
    allocation = build_fixed_mixed64_allocation(_features(available=True))
    geometric = _geometric_batch(allocation)
    complete = tuple(
        _success_record(
            slot_index,
            geometric.decisions[slot_index].candidate_coordinate_sha256,
            allocation_slot=allocation.slots[slot_index],
            score=float(slot_index),
        )
        for slot_index in range(64)
    )
    records = (
        replace(
            complete[0],
            pose_validity_receipt=None,
            execution_failure_stage=EXECUTION_FAILURE_STAGE_VALIDITY,
            execution_failure_code="typed_validity_evaluator_failure",
        ),
        *complete[1:],
    )
    batch = build_pipeline_candidate_evidence_v2(allocation, geometric, records)
    failed = batch.candidates[0]

    assert failed.source_coordinate_sha256 != failed.result_coordinate_sha256
    assert failed.status == EXECUTION_FAILURE_STATUS
    assert failed.evidence_complete is False
    assert failed.score_evidence_complete is True
    assert failed.rank_eligible is True
    assert failed.stable_rank == 1
    assert failed.valid_rank_eligible is False
    assert failed.stable_valid_rank is None
    assert batch.top1_slot_index == 0
    assert batch.top1_pose_valid is None
    assert batch.invalid_top1 is None
    assert batch.valid_top1_slot_index == 1
    assert batch.score_evidence_complete_count == 64
    assert batch.scored_success_count == 63


def test_allocation_failures_preserve_slots_without_fabricated_geometry() -> None:
    allocation = build_fixed_mixed64_allocation(_features(available=False))
    geometric = _geometric_batch(allocation)
    records = tuple(
        _success_record(
            slot_index,
            geometric.decisions[slot_index].candidate_coordinate_sha256,
            allocation_slot=allocation.slots[slot_index],
            score=float(slot_index),
        )
        if slot_index < 36
        else PipelineCandidateRecordV2(slot_index=slot_index)
        for slot_index in range(64)
    )
    batch = build_pipeline_candidate_evidence_v2(
        allocation,
        geometric,
        records,
    )

    assert len(batch.candidates) == 64
    assert batch.scored_success_count == 36
    assert batch.typed_failure_count == 28
    for candidate in batch.candidates[36:]:
        assert candidate.status == ALLOCATION_FAILURE_STATUS
        assert candidate.typed_failure_codes
        assert candidate.coordinate_sha256 is None
        assert candidate.geometric_decision.metrics is None
        assert candidate.geometric_decision.rank_eligible is False
        assert candidate.scorer_terms is None
        assert candidate.pose_validity_receipt is None
        assert candidate.refinement_receipt is None
        assert candidate.rank_eligible is False
        assert candidate.stable_rank is None
        assert candidate.valid_rank_eligible is False
        assert candidate.stable_valid_rank is None


def test_geometric_rejection_and_execution_failure_cannot_fabricate_evidence() -> None:
    allocation = build_fixed_mixed64_allocation(
        _features(available=True, slot_zero_coordinate=0.0)
    )
    geometric = _geometric_batch(allocation, reject_slot_zero=True)
    records = []
    for slot_index, decision in enumerate(geometric.decisions):
        if slot_index == 0:
            records.append(
                PipelineCandidateRecordV2(
                    slot_index=0,
                    source_proposal_sha256=(
                        allocation.slots[0].selected_generation_parent_proposal_sha256
                    ),
                    proposal_execution_receipt=bind_proposal_execution_receipt_v2(
                        slot_index=0,
                        allocation_slot_receipt_sha256=(
                            allocation.slots[0].receipt_sha256
                        ),
                        allocation_source_receipt_sha256s=(
                            allocation.slots[0].selected_source_receipt_sha256s
                        ),
                        generation_parent_proposal_sha256=(
                            allocation.slots[
                                0
                            ].selected_generation_parent_proposal_sha256
                        ),
                        generation_parent_coordinate_sha256=(
                            allocation.slots[
                                0
                            ].selected_generation_parent_coordinate_sha256
                        ),
                        source_proposal_sha256=(
                            allocation.slots[
                                0
                            ].selected_generation_parent_proposal_sha256
                        ),
                        source_coordinate_sha256=(decision.candidate_coordinate_sha256),
                        generation_input_receipt_sha256=_digest("v11-source"),
                        generator_config_sha256=_digest("generator-config"),
                        generator_implementation_source_sha256=_digest(
                            "generator-source"
                        ),
                        generator_component_id=(
                            "betelgeuze.engine_v2_fixed64_generator/1.0.0"
                        ),
                    ),
                )
            )
        elif slot_index == 1:
            complete = _success_record(
                slot_index,
                decision.candidate_coordinate_sha256,
                allocation_slot=allocation.slots[slot_index],
                score=float(slot_index),
            )
            records.append(
                replace(
                    complete,
                    scorer_evidence=None,
                    pose_validity_receipt=None,
                    execution_failure_stage=EXECUTION_FAILURE_STAGE_SCORING,
                    execution_failure_code="typed_scorer_failure",
                )
            )
        else:
            records.append(
                _success_record(
                    slot_index,
                    decision.candidate_coordinate_sha256,
                    allocation_slot=allocation.slots[slot_index],
                    score=float(slot_index),
                )
            )
    batch = build_pipeline_candidate_evidence_v2(
        allocation,
        geometric,
        tuple(records),
    )

    rejected = batch.candidates[0]
    failed = batch.candidates[1]
    assert rejected.status == GEOMETRIC_REJECTION_STATUS
    assert rejected.geometric_decision is not None
    assert rejected.geometric_decision.metrics.receipt_sha256
    assert rejected.rank_eligible is False
    assert rejected.scorer_terms is None
    assert rejected.pose_validity_receipt is None
    assert rejected.refinement_receipt is None
    assert failed.status == EXECUTION_FAILURE_STATUS
    assert failed.typed_failure_codes == ("typed_scorer_failure",)
    assert failed.rank_eligible is False
    assert failed.valid_rank_eligible is False
    assert failed.scorer_terms is None
    assert batch.typed_failure_count == 2
    assert len(batch.candidates) == 64


def test_cross_wired_scorer_validity_and_refinement_receipts_fail_closed() -> None:
    allocation = build_fixed_mixed64_allocation(_features(available=True))
    geometric = _geometric_batch(allocation)
    good = tuple(
        _success_record(
            slot_index,
            geometric.decisions[slot_index].candidate_coordinate_sha256,
            allocation_slot=allocation.slots[slot_index],
            score=float(slot_index),
        )
        for slot_index in range(64)
    )

    wrong_result = _digest("wrong-result")
    assert good[0].scorer_evidence is not None
    cross_terms = replace(
        good[0].scorer_evidence.terms,
        proposal_fingerprint_sha256=wrong_result,
    )
    cross_scorer = replace(
        good[0],
        scorer_evidence=bind_scorer_v1_evidence_v2(
            terms=cross_terms,
            search_row_sha256=_digest("cross-search-row"),
            search_term_row_receipt_sha256=_digest("cross-term-row"),
            source_search_result_receipt_sha256=_digest("search-result"),
            scorer_implementation_source_sha256=_digest("scorer-source"),
        ),
    )
    with pytest.raises(PipelineCandidateEvidenceV2Error, match="ScorerV1 evidence"):
        build_pipeline_candidate_evidence_v2(
            allocation,
            geometric,
            (cross_scorer,) + good[1:],
        )

    cross_proposal = replace(
        good[0],
        proposal_execution_receipt=bind_proposal_execution_receipt_v2(
            slot_index=0,
            allocation_slot_receipt_sha256=allocation.slots[0].receipt_sha256,
            allocation_source_receipt_sha256s=(
                allocation.slots[0].selected_source_receipt_sha256s
            ),
            generation_parent_proposal_sha256=(
                allocation.slots[0].selected_generation_parent_proposal_sha256
            ),
            generation_parent_coordinate_sha256=(
                allocation.slots[0].selected_generation_parent_coordinate_sha256
            ),
            source_proposal_sha256=str(good[0].source_proposal_sha256),
            source_coordinate_sha256=_digest("wrong-source-coordinate"),
            generation_input_receipt_sha256=_digest("v11-source"),
            generator_config_sha256=_digest("generator-config"),
            generator_implementation_source_sha256=_digest("generator-source"),
            generator_component_id="betelgeuze.engine_v2_fixed64_generator/1.0.0",
        ),
    )
    with pytest.raises(PipelineCandidateEvidenceV2Error, match="proposal execution"):
        build_pipeline_candidate_evidence_v2(
            allocation,
            geometric,
            (cross_proposal,) + good[1:],
        )

    cross_parent = replace(
        good[0],
        proposal_execution_receipt=bind_proposal_execution_receipt_v2(
            slot_index=0,
            allocation_slot_receipt_sha256=allocation.slots[0].receipt_sha256,
            allocation_source_receipt_sha256s=(
                allocation.slots[0].selected_source_receipt_sha256s
            ),
            generation_parent_proposal_sha256=_digest("wrong-parent-proposal"),
            generation_parent_coordinate_sha256=_digest("wrong-parent-coordinate"),
            source_proposal_sha256=str(good[0].source_proposal_sha256),
            source_coordinate_sha256=str(
                geometric.decisions[0].candidate_coordinate_sha256
            ),
            generation_input_receipt_sha256=_digest("v11-source"),
            generator_config_sha256=_digest("generator-config"),
            generator_implementation_source_sha256=_digest("generator-source"),
            generator_component_id="betelgeuze.engine_v2_fixed64_generator/1.0.0",
        ),
    )
    with pytest.raises(
        PipelineCandidateEvidenceV2Error,
        match="generation parent identity is cross-wired",
    ):
        build_pipeline_candidate_evidence_v2(
            allocation,
            geometric,
            (cross_parent,) + good[1:],
        )

    conformer_slot = allocation.slots[36]
    untransformed_conformer = PipelineCandidateRecordV2(
        slot_index=36,
        source_proposal_sha256=(
            conformer_slot.selected_generation_parent_proposal_sha256
        ),
        proposal_execution_receipt=bind_proposal_execution_receipt_v2(
            slot_index=36,
            allocation_slot_receipt_sha256=conformer_slot.receipt_sha256,
            allocation_source_receipt_sha256s=(
                conformer_slot.selected_source_receipt_sha256s
            ),
            generation_parent_proposal_sha256=(
                conformer_slot.selected_generation_parent_proposal_sha256
            ),
            generation_parent_coordinate_sha256=(
                conformer_slot.selected_generation_parent_coordinate_sha256
            ),
            source_proposal_sha256=str(
                conformer_slot.selected_generation_parent_proposal_sha256
            ),
            source_coordinate_sha256=str(
                geometric.decisions[36].candidate_coordinate_sha256
            ),
            generation_input_receipt_sha256=_digest("v11-source"),
            generator_config_sha256=_digest("generator-config"),
            generator_implementation_source_sha256=_digest("generator-source"),
            generator_component_id="betelgeuze.engine_v2_fixed64_generator/1.0.0",
        ),
        execution_failure_stage="refinement",
        execution_failure_code="typed_refinement_untransformed_parent",
    )
    records = (*good[:36], untransformed_conformer, *good[37:])
    with pytest.raises(
        PipelineCandidateEvidenceV2Error,
        match="did not preserve transformed semantics",
    ):
        build_pipeline_candidate_evidence_v2(allocation, geometric, records)

    assert good[0].pose_validity_receipt is not None
    cross_validity = replace(
        good[0],
        pose_validity_receipt=_validity_receipt(
            result_sha256=str(good[0].result_proposal_sha256),
            coordinate_sha256=_digest("wrong-coordinate"),
            valid=True,
        ),
    )
    with pytest.raises(PipelineCandidateEvidenceV2Error, match="validity"):
        build_pipeline_candidate_evidence_v2(
            allocation,
            geometric,
            (cross_validity,) + good[1:],
        )

    assert good[0].refinement_receipt is not None
    decision = geometric.decisions[0]
    assert decision is not None
    source_payload = good[0].refinement_receipt.to_dict()["source_receipt"]
    assert isinstance(source_payload, dict)
    source_payload["post_coordinates_sha256"] = _digest("tampered")
    with pytest.raises(PipelineCandidateEvidenceV2Error, match="does not rederive"):
        bind_refinement_receipt_v2(
            source_proposal_sha256=str(good[0].source_proposal_sha256),
            result_proposal_sha256=str(good[0].result_proposal_sha256),
            source_coordinate_sha256=(decision.candidate_coordinate_sha256),
            result_coordinate_sha256=(
                good[0].refinement_receipt.result_coordinate_sha256
            ),
            refiner_config_sha256=(good[0].refinement_receipt.refiner_config_sha256),
            refiner_implementation_source_sha256=(
                good[0].refinement_receipt.refiner_implementation_source_sha256
            ),
            source_receipt=source_payload,
        )


@pytest.mark.parametrize(
    ("drift_kwargs", "expected_identity"),
    (
        (
            {"generator_component_id": "betelgeuze.synthetic_other_generator/1.0.0"},
            "proposal generator component",
        ),
        (
            {"refiner_config_sha256": _digest("other-refiner-config")},
            "refiner config",
        ),
        (
            {
                "refiner_implementation_source_sha256": _digest(
                    "other-refiner-source"
                )
            },
            "refiner implementation",
        ),
        (
            {
                "refinement_source_schema_id": (
                    "betelgeuze.engine_v2_source_paired_torsion_rescue_receipt/1.1.0"
                )
            },
            "refinement source schema",
        ),
    ),
)
def test_batch_rejects_mixed_generator_and_refiner_identities(
    drift_kwargs: dict[str, object],
    expected_identity: str,
) -> None:
    allocation = build_fixed_mixed64_allocation(_features(available=True))
    geometric = _geometric_batch(allocation)
    records = tuple(
        _success_record(
            slot_index,
            geometric.decisions[slot_index].candidate_coordinate_sha256,
            allocation_slot=allocation.slots[slot_index],
            score=float(slot_index),
            **(drift_kwargs if slot_index == 0 else {}),
        )
        for slot_index in range(64)
    )

    with pytest.raises(
        PipelineCandidateEvidenceV2Error,
        match=rf"{expected_identity} is cross-wired across the batch",
    ):
        build_pipeline_candidate_evidence_v2(allocation, geometric, records)


@pytest.mark.parametrize(
    ("authority_key", "authority_value"),
    (
        ("profile_promotion_authority", True),
        ("activation_evidence_eligible", True),
        ("authority_granted", True),
    ),
)
def test_refinement_source_receipt_cannot_grant_nested_authority_or_eligibility(
    authority_key: str,
    authority_value: bool,
) -> None:
    allocation = build_fixed_mixed64_allocation(_features(available=True))
    geometric = _geometric_batch(allocation)
    record = _success_record(
        0,
        geometric.decisions[0].candidate_coordinate_sha256,
        allocation_slot=allocation.slots[0],
        score=0.0,
    )
    refinement = record.refinement_receipt
    assert refinement is not None
    source_receipt = refinement.to_dict()["source_receipt"]
    assert isinstance(source_receipt, dict)
    source_receipt.pop("receipt_sha256")
    source_receipt[authority_key] = authority_value
    source_receipt = _receipt(source_receipt)

    with pytest.raises(
        PipelineCandidateEvidenceV2Error,
        match="cannot grant nested authority or eligibility",
    ):
        bind_refinement_receipt_v2(
            source_proposal_sha256=refinement.source_proposal_sha256,
            result_proposal_sha256=refinement.result_proposal_sha256,
            source_coordinate_sha256=refinement.source_coordinate_sha256,
            result_coordinate_sha256=refinement.result_coordinate_sha256,
            refiner_config_sha256=refinement.refiner_config_sha256,
            refiner_implementation_source_sha256=(
                refinement.refiner_implementation_source_sha256
            ),
            source_receipt=source_receipt,
        )


def test_uninterpreted_refinement_source_extensions_are_not_embedded() -> None:
    source_proposal = _digest("opaque-refinement-source")
    result_proposal = _digest("opaque-refinement-result")
    source_coordinate = _digest("opaque-refinement-pre-coordinate")
    result_coordinate = _digest("opaque-refinement-post-coordinate")
    config = _digest("opaque-refinement-config")
    source_receipt = _receipt(
        {
            "schema_id": (
                "betelgeuze.engine_v2_interaction_aware_torsion_contact_receipt/"
                "7.0.0"
            ),
            "source_proposal_sha256": source_proposal,
            "config_sha256": config,
            "pre_coordinates_sha256": source_coordinate,
            "post_coordinates_sha256": result_coordinate,
            "authorityGranted": True,
            "scientifically_validated": False,
        }
    )

    binding = bind_refinement_receipt_v2(
        source_proposal_sha256=source_proposal,
        result_proposal_sha256=result_proposal,
        source_coordinate_sha256=source_coordinate,
        result_coordinate_sha256=result_coordinate,
        refiner_config_sha256=config,
        refiner_implementation_source_sha256=_digest("opaque-refinement-code"),
        source_receipt=source_receipt,
    )
    identity = binding.to_dict()["source_receipt"]

    assert isinstance(identity, dict)
    assert "authorityGranted" not in identity
    assert identity["original_source_receipt_sha256"] == source_receipt[
        "receipt_sha256"
    ]
    assert identity["source_payload_embedded"] is False
    assert identity["source_payload_rederived"] is False
    assert identity["producer_attested"] is False
    assert identity["claim_safe"] is False


@pytest.mark.parametrize(
    ("measurements", "expected_error"),
    (
        ({"too_large": 2.0e15}, "bounded finite numeric values"),
        (
            {f"measurement_{index}": float(index) for index in range(257)},
            "measurement capacity exceeded",
        ),
        ({"x" * 257: 1.0}, "bounded canonical strings"),
        ({"\ud800": 1.0}, "non-Unicode-scalar string"),
    ),
)
def test_pose_validity_binding_enforces_independent_verifier_measurement_bounds(
    measurements: dict[str, float],
    expected_error: str,
) -> None:
    with pytest.raises(PipelineCandidateEvidenceV2Error, match=expected_error):
        _validity_receipt(
            result_sha256=_digest("bounded-validity-result"),
            coordinate_sha256=_digest("bounded-validity-coordinate"),
            valid=True,
            measurements=measurements,
        )


def test_pose_validity_binding_enforces_independent_verifier_blocker_capacity(
) -> None:
    with pytest.raises(
        PipelineCandidateEvidenceV2Error,
        match="blocker capacity exceeded",
    ):
        _validity_receipt(
            result_sha256=_digest("bounded-blocker-result"),
            coordinate_sha256=_digest("bounded-blocker-coordinate"),
            valid=False,
            blockers=tuple(f"blocker_{index}" for index in range(257)),
        )


def test_scorer_binding_enforces_exact_integer_and_count_envelope() -> None:
    with pytest.raises(ScorerV1Error, match="must be an exact integer"):
        replace(
            _scorer_terms(
                result_sha256=_digest("noninteger-count-result"),
                score=0.0,
            ),
            receptor_candidate_pair_count=1.5,
        )

    terms = _scorer_terms(
        result_sha256=_digest("oversized-count-result"),
        score=0.0,
        receptor_candidate_pair_count=16_777_217,
    )
    with pytest.raises(
        PipelineCandidateEvidenceV2Error,
        match="exceeds the exact count envelope",
    ):
        bind_scorer_v1_evidence_v2(
            terms=terms,
            search_row_sha256=_digest("search-row"),
            search_term_row_receipt_sha256=_digest("term-row"),
            source_search_result_receipt_sha256=_digest("search-result"),
            scorer_implementation_source_sha256=_digest("scorer-source"),
        )


def test_refinement_source_receipt_enforces_exact_json_integer_envelope() -> None:
    source_proposal = _digest("bounded-refinement-source")
    result_proposal = _digest("bounded-refinement-result")
    source_coordinate = _digest("bounded-refinement-pre-coordinate")
    result_coordinate = _digest("bounded-refinement-post-coordinate")
    config = _digest("bounded-refinement-config")
    source_receipt = _receipt(
        {
            "schema_id": (
                "betelgeuze.engine_v2_interaction_aware_torsion_contact_receipt/"
                "7.0.0"
            ),
            "source_proposal_sha256": source_proposal,
            "config_sha256": config,
            "pre_coordinates_sha256": source_coordinate,
            "post_coordinates_sha256": result_coordinate,
            "accepted_steps": 1 << 53,
            "scientifically_validated": False,
        }
    )

    with pytest.raises(
        PipelineCandidateEvidenceV2Error,
        match="exact JSON integer envelope",
    ):
        bind_refinement_receipt_v2(
            source_proposal_sha256=source_proposal,
            result_proposal_sha256=result_proposal,
            source_coordinate_sha256=source_coordinate,
            result_coordinate_sha256=result_coordinate,
            refiner_config_sha256=config,
            refiner_implementation_source_sha256=_digest(
                "bounded-refinement-source-code"
            ),
            source_receipt=source_receipt,
        )


def test_incomplete_success_and_caller_rank_or_completion_inputs_are_rejected() -> None:
    allocation = build_fixed_mixed64_allocation(_features(available=True))
    geometric = _geometric_batch(allocation)
    good = tuple(
        _success_record(
            slot_index,
            geometric.decisions[slot_index].candidate_coordinate_sha256,
            allocation_slot=allocation.slots[slot_index],
            score=float(slot_index),
        )
        for slot_index in range(64)
    )
    incomplete = replace(good[0], scorer_evidence=None)
    with pytest.raises(PipelineCandidateEvidenceV2Error, match="score and validity"):
        build_pipeline_candidate_evidence_v2(
            allocation,
            geometric,
            (incomplete,) + good[1:],
        )

    assert good[0].pose_validity_receipt is not None
    decision = geometric.decisions[0]
    assert decision is not None
    with pytest.raises(PipelineCandidateEvidenceV2Error, match="must be complete"):
        bind_pose_validity_receipt_v2(
            result_proposal_sha256=str(good[0].result_proposal_sha256),
            coordinate_sha256=_digest("result-coordinate-0"),
            validity_context_fingerprint_sha256=_digest("validity-context"),
            validity_config_fingerprint_sha256=_digest("validity-config"),
            evaluator_implementation_source_sha256=_digest("validity-source"),
            result=PoseValidityResult(
                checks={
                    "proper_rotation": True,
                    "bond_lengths_preserved": True,
                    "ligand_self_clash_free": True,
                    "receptor_ligand_clash_free": True,
                    "declared_chirality_preserved": True,
                    "inside_declared_pocket": True,
                    "element_vdw_ligand_overlap_free": True,
                    "element_vdw_receptor_overlap_free": True,
                },
                evaluated_checks={
                    "proper_rotation": False,
                    "bond_lengths_preserved": True,
                    "ligand_self_clash_free": True,
                    "receptor_ligand_clash_free": True,
                    "declared_chirality_preserved": True,
                    "inside_declared_pocket": True,
                    "element_vdw_ligand_overlap_free": True,
                    "element_vdw_receptor_overlap_free": True,
                },
                complete=False,
                valid_within_evaluated_scope=False,
                measurements={},
                blockers=(),
                not_evaluated_reasons={"proper_rotation": "not run"},
            ),
        )

    record_fields = {item.name for item in fields(PipelineCandidateRecordV2)}
    assert "evidence_complete" not in record_fields
    assert "rank_eligible" not in record_fields
    assert "stable_rank" not in record_fields
    assert "top1_member" not in record_fields
    assert "top5_member" not in record_fields
    assert "geometric_decision" not in record_fields
    assert set(inspect.signature(build_pipeline_candidate_evidence_v2).parameters) == {
        "allocation",
        "geometric_admission_batch",
        "records",
    }
    with pytest.raises(PipelineCandidateEvidenceV2Error, match="exact builder"):
        PipelineCandidateEvidenceV2(
            allocation_receipt_sha256=allocation.receipt_sha256,
            geometric_admission_batch_receipt_sha256=(geometric.receipt_sha256),
            allocation_slot=allocation.slots[0],
            geometric_decision=decision,
            source_proposal_sha256=good[0].source_proposal_sha256,
            result_proposal_sha256=good[0].result_proposal_sha256,
            proposal_execution_receipt=good[0].proposal_execution_receipt,
            scorer_evidence=good[0].scorer_evidence,
            pose_validity_receipt=good[0].pose_validity_receipt,
            refinement_receipt=good[0].refinement_receipt,
            execution_failure_stage=None,
            execution_failure_code=None,
            stable_rank=1,
            stable_valid_rank=1,
        )
