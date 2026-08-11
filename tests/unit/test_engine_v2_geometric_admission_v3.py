from __future__ import annotations

from dataclasses import replace
import inspect

import pytest

from betelgeuze_engine_v2.docking.geometric_admission_v3 import (
    ACCEPTED_STATUS,
    GEOMETRIC_ADMISSION_V3_POLICY_SHA256,
    REJECTED_STATUS,
    TYPED_ALLOCATION_FAILURE_STATUS,
    TYPED_PROPOSAL_GENERATION_FAILURE_STATUS,
    GeometricAdmissionDecisionV3,
    GeometricAdmissionV3,
    GeometricAdmissionV3Error,
    frozen_geometric_admission_v3_policy,
)
from betelgeuze_engine_v2.docking.mixed64_proposal_producer_v3 import (
    MISSING_EXACT_V11_SOURCE_PAYLOAD,
    MISSING_V7_CONTROL_SOURCE_PAYLOAD,
    Mixed64ProposalProducerError,
    produce_fixed_mixed64_proposals,
)
from tests.unit.test_engine_v2_mixed64_proposal_producer_v3 import (
    LIGAND,
    RECEPTOR,
    _fixture,
)


def _admit(allocation, bundle):
    producer = produce_fixed_mixed64_proposals(
        allocation,
        source_bundle=bundle,
    )
    return producer, GeometricAdmissionV3().admit_producer_batch(producer)


def test_full_generated_batch_is_replayed_deterministically_in_exact64() -> None:
    allocation, bundle, *_ = _fixture()
    producer, first = _admit(allocation, bundle)
    second = GeometricAdmissionV3().admit_producer_batch(producer)

    assert first.receipt_sha256 == second.receipt_sha256
    assert len(first.decisions) == 64
    assert tuple(value.slot_index for value in first.decisions) == tuple(range(64))
    assert first.accepted_count + first.geometric_rejected_count == 64
    assert first.typed_allocation_failure_count == 0
    assert first.typed_proposal_generation_failure_count == 0
    assert first.nonaccepted_count == first.geometric_rejected_count
    assert first.exact_pair_evaluation_count == 64 * len(LIGAND) * len(RECEPTOR)
    assert all(value.metrics is not None for value in first.decisions)


def test_decisions_bind_exact_producer_records_and_coordinates() -> None:
    allocation, bundle, *_ = _fixture()
    producer, admission = _admit(allocation, bundle)

    for record, decision in zip(producer.records, admission.decisions, strict=True):
        assert decision.producer_record.receipt_sha256 == record.receipt_sha256
        assert decision.candidate_coordinate_sha256 == record.source_coordinate_sha256
        assert decision.metrics is not None
        assert decision.metrics.exact_pair_count == len(LIGAND) * len(RECEPTOR)
        assert decision.rank_eligible is (decision.status == ACCEPTED_STATUS)


def test_missing_declared_source_payload_is_failure_aware_not_fabricated() -> None:
    allocation, bundle, *_ = _fixture()
    incomplete = replace(
        bundle,
        v7_control_sources=tuple(
            value for value in bundle.v7_control_sources if value.source_ordinal != 8
        ),
    )
    producer, admission = _admit(allocation, incomplete)
    record = producer.records[8]
    decision = admission.decisions[8]

    assert record.failure_receipt is not None
    assert record.failure_receipt.failure_code == MISSING_V7_CONTROL_SOURCE_PAYLOAD
    assert decision.status == TYPED_PROPOSAL_GENERATION_FAILURE_STATUS
    assert decision.rejection_code == MISSING_V7_CONTROL_SOURCE_PAYLOAD
    assert decision.candidate_coordinate_sha256 is None
    assert decision.metrics is None
    assert decision.rank_eligible is False
    assert admission.typed_proposal_generation_failure_count == 1
    assert len(admission.decisions) == 64


def test_missing_exact_base_preserves_all_dependent_runtime_failures() -> None:
    allocation, bundle, *_ = _fixture()
    producer, admission = _admit(allocation, replace(bundle, exact_v11_source=None))
    expected = (*range(24, 36), *range(44, 60))

    assert tuple(
        value.slot_index
        for value in admission.decisions
        if value.status == TYPED_PROPOSAL_GENERATION_FAILURE_STATUS
    ) == expected
    assert all(
        producer.records[index].failure_receipt.failure_code
        == MISSING_EXACT_V11_SOURCE_PAYLOAD
        for index in expected
    )
    assert admission.typed_proposal_generation_failure_count == 28


def test_allocation_failures_remain_distinct_from_runtime_failures() -> None:
    allocation, bundle, *_ = _fixture(
        feature_available=False,
        conformer_available=False,
    )
    _producer, admission = _admit(allocation, bundle)

    assert admission.typed_allocation_failure_count == 24
    assert admission.typed_proposal_generation_failure_count == 0
    assert tuple(
        value.slot_index
        for value in admission.decisions
        if value.status == TYPED_ALLOCATION_FAILURE_STATUS
    ) == tuple(range(36, 60))


def test_typed_geometry_failures_are_carried_without_metrics() -> None:
    degenerate = tuple((0.0, 0.0, 0.0) for _ in LIGAND)
    allocation, bundle, *_ = _fixture(exact_coordinates=degenerate)
    _producer, admission = _admit(allocation, bundle)

    for index in range(24, 36):
        decision = admission.decisions[index]
        assert decision.status == TYPED_PROPOSAL_GENERATION_FAILURE_STATUS
        assert decision.rejection_code == "degenerate_so3_source_geometry"
        assert decision.metrics is None
        assert decision.candidate_coordinate_sha256 is None


def test_severe_penetration_is_typed_geometric_rejection_not_deletion() -> None:
    allocation, bundle, *_ = _fixture()
    penetrative = replace(
        bundle,
        ligand_vdw_radii=(10.0,) * len(LIGAND),
        receptor_vdw_radii=(10.0,) * len(RECEPTOR),
    )
    producer, admission = _admit(allocation, penetrative)

    rejected = tuple(
        value for value in admission.decisions if value.status == REJECTED_STATUS
    )
    assert rejected
    assert admission.geometric_rejected_count == len(rejected)
    assert all(value.rejection_code == "severe_receptor_penetration_min_vdw_ratio" for value in rejected)
    assert all(value.candidate_coordinate_sha256 is not None for value in rejected)
    assert len(producer.records) == len(admission.decisions) == 64


def test_single_anchor_precheck_is_identical_to_admission_replay() -> None:
    allocation, bundle, *_ = _fixture()
    producer, admission = _admit(allocation, bundle)

    for index in range(44, 60):
        placement = producer.records[index].placement_receipt
        decision = admission.decisions[index]
        assert placement is not None
        assert decision.metrics is not None
        assert placement.geometric_metrics.receipt_sha256 == (
            decision.metrics.receipt_sha256
        )


def test_batch_pair_limit_is_checked_before_metric_traversal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import betelgeuze_engine_v2.docking.geometric_admission_v3 as module

    allocation, bundle, *_ = _fixture()
    producer = produce_fixed_mixed64_proposals(allocation, source_bundle=bundle)
    monkeypatch.setattr(module, "MAX_BATCH_EXACT_PAIR_EVALUATIONS", 1)

    with pytest.raises(GeometricAdmissionV3Error, match="exceeds"):
        GeometricAdmissionV3().admit_producer_batch(producer)


def test_live_record_mutation_fails_before_metric_traversal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import betelgeuze_engine_v2.docking.geometric_admission_v3 as module

    allocation, bundle, *_ = _fixture()
    producer = produce_fixed_mixed64_proposals(allocation, source_bundle=bundle)
    record = producer.records[0]
    assert record.output_coordinates is not None
    object.__setattr__(
        record,
        "output_coordinates",
        tuple((x + 1.0, y, z) for x, y, z in record.output_coordinates),
    )

    def unexpected_metric_traversal(*_args, **_kwargs):
        raise AssertionError("metric traversal must not start")

    monkeypatch.setattr(
        module,
        "evaluate_geometric_admission_metrics_one_python",
        unexpected_metric_traversal,
    )

    with pytest.raises(GeometricAdmissionV3Error, match="integrity preflight"):
        GeometricAdmissionV3().admit_producer_batch(producer)


@pytest.mark.parametrize(
    "field_name,replacement",
    (
        ("receptor_coordinates", ((999.0, 999.0, 999.0),)),
        ("ligand_vdw_radii", (9.0,)),
        ("pocket_center", (9.0, 9.0, 9.0)),
    ),
)
def test_live_source_bundle_mutation_fails_closed(
    field_name: str,
    replacement: object,
) -> None:
    allocation, bundle, *_ = _fixture()
    producer = produce_fixed_mixed64_proposals(allocation, source_bundle=bundle)
    object.__setattr__(producer.source_bundle, field_name, replacement)

    with pytest.raises(GeometricAdmissionV3Error, match="integrity preflight"):
        GeometricAdmissionV3().admit_producer_batch(producer)


def test_nested_source_payload_live_mutation_is_checked_recursively() -> None:
    allocation, bundle, *_ = _fixture()
    producer = produce_fixed_mixed64_proposals(allocation, source_bundle=bundle)
    source = producer.source_bundle.v7_control_sources[0]
    object.__setattr__(source, "coordinates", ((999.0, 999.0, 999.0),))

    with pytest.raises(GeometricAdmissionV3Error, match="integrity preflight"):
        GeometricAdmissionV3().admit_producer_batch(producer)


def test_nested_placement_receipt_live_mutation_is_checked_recursively() -> None:
    allocation, bundle, *_ = _fixture()
    producer = produce_fixed_mixed64_proposals(allocation, source_bundle=bundle)
    placement = producer.records[44].placement_receipt
    assert placement is not None
    object.__setattr__(placement, "output_coordinates", ((999.0, 999.0, 999.0),))

    with pytest.raises(GeometricAdmissionV3Error, match="integrity preflight"):
        GeometricAdmissionV3().admit_producer_batch(producer)


def test_direct_record_integrity_normalizes_nested_geometry_failure() -> None:
    allocation, bundle, *_ = _fixture()
    producer = produce_fixed_mixed64_proposals(allocation, source_bundle=bundle)
    placement = producer.records[44].placement_receipt
    assert placement is not None
    object.__setattr__(placement, "output_coordinates", ((999.0, 999.0, 999.0),))

    with pytest.raises(
        Mixed64ProposalProducerError,
        match="generation record nested live projection changed",
    ):
        producer.records[44].assert_live_integrity()


def test_transient_live_record_mutation_cannot_change_sealed_kernel_inputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import betelgeuze_engine_v2.docking.geometric_admission_v3 as module

    allocation, bundle, *_ = _fixture()
    producer = produce_fixed_mixed64_proposals(allocation, source_bundle=bundle)
    baseline = GeometricAdmissionV3().admit_producer_batch(producer)
    target = producer.records[1]
    original_coordinates = target.output_coordinates
    assert original_coordinates is not None
    poisoned_coordinates = tuple(
        (x + 50.0, y - 50.0, z + 25.0) for x, y, z in original_coordinates
    )
    original_kernel = module.evaluate_geometric_admission_metrics_one_python
    call_count = 0

    def transient_mutation_kernel(*args, **kwargs):
        nonlocal call_count
        if call_count == 0:
            object.__setattr__(target, "output_coordinates", poisoned_coordinates)
        elif call_count == 1:
            object.__setattr__(target, "output_coordinates", original_coordinates)
        call_count += 1
        return original_kernel(*args, **kwargs)

    monkeypatch.setattr(
        module,
        "evaluate_geometric_admission_metrics_one_python",
        transient_mutation_kernel,
    )
    observed = GeometricAdmissionV3().admit_producer_batch(producer)

    assert call_count == 64
    assert target.output_coordinates == original_coordinates
    assert observed.receipt_sha256 == baseline.receipt_sha256


def test_decision_cannot_be_forged_without_factory() -> None:
    allocation, bundle, *_ = _fixture()
    producer, admission = _admit(allocation, bundle)
    source = admission.decisions[0]

    with pytest.raises(GeometricAdmissionV3Error, match="factory"):
        GeometricAdmissionDecisionV3(
            producer_record=producer.records[0],
            metrics=source.metrics,
            status=source.status,
            rejection_code=source.rejection_code,
            rank_eligible=source.rank_eligible,
        )


def test_policy_freezes_threshold_failure_semantics_and_zero_authority() -> None:
    policy = frozen_geometric_admission_v3_policy()
    assert len(GEOMETRIC_ADMISSION_V3_POLICY_SHA256) == 64
    assert policy["candidate_denominator"] == 64
    assert policy["hard_rejection"]["threshold_binary64_hex"] == (0.55).hex()
    assert policy["failure_semantics"]["slot_reallocation_allowed"] is False
    assert all(policy["producer_integrity"].values())
    assert all(value is False for value in policy["authority"].values())


def test_batch_output_keeps_activation_and_downstream_authority_false() -> None:
    allocation, bundle, *_ = _fixture()
    _producer, admission = _admit(allocation, bundle)
    document = admission.to_dict()

    assert document["denominator_failure_complete"] is True
    assert document["pre_refinement_geometric_admission_complete"] is True
    assert document["post_refinement_geometric_admission_complete"] is False
    assert document["activation_evidence_eligible"] is False
    assert document["score_or_validity_input_consumed"] is False
    assert document["reservation_allowed"] is False
    assert document["molecular_execution_authorized"] is False
    assert document["public_or_scientific_claim_authorized"] is False


def test_sealed_batch_projection_returns_independent_documents() -> None:
    allocation, bundle, *_ = _fixture()
    _producer, admission = _admit(allocation, bundle)
    receipt_sha256 = admission.receipt_sha256
    first = admission.to_dict()

    first["candidate_denominator"] = 0
    first["decisions"][0]["status"] = "tampered"
    second = admission.to_dict()

    assert second["candidate_denominator"] == 64
    assert second["decisions"][0]["status"] != "tampered"
    assert second["receipt_sha256"] == receipt_sha256


def test_sealed_batch_projection_corruption_fails_closed() -> None:
    allocation, bundle, *_ = _fixture()
    _producer, admission = _admit(allocation, bundle)
    object.__setattr__(admission, "_canonical_projection_bytes", b"{}")

    with pytest.raises(GeometricAdmissionV3Error, match="sealed projection changed"):
        _ = admission.receipt_sha256


def test_admission_decision_live_mutation_fails_integrity_check() -> None:
    allocation, bundle, *_ = _fixture()
    _producer, admission = _admit(allocation, bundle)
    decision = admission.decisions[0]
    object.__setattr__(
        decision,
        "status",
        REJECTED_STATUS if decision.status == ACCEPTED_STATUS else ACCEPTED_STATUS,
    )

    with pytest.raises(GeometricAdmissionV3Error, match="live projection changed"):
        admission.assert_live_integrity()


def test_admission_metric_live_mutation_fails_integrity_check() -> None:
    allocation, bundle, *_ = _fixture()
    _producer, admission = _admit(allocation, bundle)
    decision = admission.decisions[0]
    assert decision.metrics is not None
    object.__setattr__(
        decision.metrics,
        "raw_minimum_distance_angstrom",
        decision.metrics.raw_minimum_distance_angstrom + 1.0,
    )

    with pytest.raises(GeometricAdmissionV3Error, match="live integrity failed"):
        admission.assert_live_integrity()


def test_admission_batch_live_order_mutation_fails_integrity_check() -> None:
    allocation, bundle, *_ = _fixture()
    _producer, admission = _admit(allocation, bundle)
    object.__setattr__(admission, "decisions", tuple(reversed(admission.decisions)))

    with pytest.raises(GeometricAdmissionV3Error, match="live projection changed"):
        admission.assert_live_integrity()


def test_admission_signature_accepts_no_caller_coordinates_or_results() -> None:
    parameters = set(
        inspect.signature(GeometricAdmissionV3.admit_producer_batch).parameters
    )
    assert parameters == {"self", "producer_batch"}
    assert not parameters & {
        "candidate_coordinates",
        "score",
        "rank",
        "validity",
        "benchmark_outcome",
        "authority",
        "reservation",
    }
