from __future__ import annotations

from dataclasses import replace
import hashlib
import inspect
import json
from pathlib import Path

import pytest

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
    RETAINED_SOURCE_INDICES,
    TRUE_CONFORMER_RANKS,
    V7_CONTROL_SOURCE_INDICES,
    Mixed64AtomicFeatureEvidence,
    Mixed64ConformerSourceEvidence,
    Mixed64ExactV11SourceEvidence,
    Mixed64FeatureEvidence,
    Mixed64RetainedSourceEvidence,
    Mixed64V7ControlSourceEvidence,
    build_fixed_mixed64_allocation,
)
from betelgeuze_engine_v2.docking.mixed64_proposal_geometry_v3 import (
    IndexedSO3PlacementReceiptV1,
    SingleAnchorPlacementReceiptV1,
    coordinate_sha256,
)
from betelgeuze_engine_v2.docking.mixed64_proposal_producer_v3 import (
    ALLOCATION_MISSING_FEATURE_FAILURE,
    GENERATION_STATUS_FAILURE,
    GENERATION_STATUS_SUCCESS,
    LIGAND_ATOM_DENOMINATOR_MISMATCH,
    MISSING_EXACT_V11_SOURCE_PAYLOAD,
    MISSING_V7_CONTROL_SOURCE_PAYLOAD,
    MIXED64_PRODUCER_POLICY_SHA256,
    ExactPassthroughPlacementReceiptV1,
    Mixed64CoordinateSourcePayloadV1,
    Mixed64ProposalProducerError,
    Mixed64ProposalSourceBundleV1,
    SOURCE_KIND_EXACT_V11_BASE,
    SOURCE_KIND_RETAINED_CONTROL,
    SOURCE_KIND_TRUE_CONFORMER,
    SOURCE_KIND_V7_CONTROL,
    SOURCE_PAYLOAD_CROSS_WIRING,
    SOURCE_PAYLOAD_NONCANONICAL,
    SOURCE_PAYLOAD_RECEIPT_INVALID,
    frozen_mixed64_producer_policy,
    produce_fixed_mixed64_proposals,
)


def _canonical(document: object) -> bytes:
    return json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _digest(document: object) -> str:
    return hashlib.sha256(_canonical(document)).hexdigest()


def _receipt(label: str) -> bytes:
    projection = {
        "schema_id": "betelgeuze.synthetic_source_receipt/1.0.0",
        "label": label,
        "authority_granted": False,
    }
    return _canonical({**projection, "receipt_sha256": _digest(projection)})


def _proposal(label: str) -> bytes:
    return _canonical(
        {
            "schema_id": "betelgeuze.synthetic_proposal_identity/1.0.0",
            "label": label,
        }
    )


def _lineage(index: int) -> bytes:
    return _canonical(
        {
            "schema_id": "betelgeuze.synthetic_v7_lineage/1.0.0",
            "source_index": index,
            "proposal_mode": (
                "pocket_centered_control" if index < 8 else "uniform_source_control"
            ),
        }
    )


LIGAND = (
    (0.0, 0.0, 0.0),
    (1.0, 0.0, 0.0),
    (2.0, 0.0, 0.0),
    (0.0, 1.0, 0.0),
    (0.0, -1.0, 0.5),
    (-1.0, -1.0, 0.0),
    (1.0, -1.0, 0.0),
    (0.0, 1.0, 0.0),
    (-2.0, 0.2, 0.1),
    (0.0, 0.0, 0.0),
    (3.0, -0.1, 0.2),
)
RECEPTOR = (
    (0.0, 0.0, 0.0),
    (0.0, 0.0, 1.0),
    (0.2, 0.1, 0.0),
    (-0.2, 0.0, 0.0),
    (0.0, 0.0, 0.0),
    (-1.0, -1.0, 0.0),
    (1.0, -1.0, 0.0),
    (0.0, 1.0, 0.0),
    (-3.0, 0.1, 0.0),
    (0.0, 0.0, 0.0),
    (4.0, -0.2, 0.1),
)


def _shifted(value, offset: float):
    return tuple(
        (point[0] + offset, point[1] - offset / 2.0, point[2] + offset / 3.0)
        for point in value
    )


def _source(
    kind: str,
    ordinal: int | None,
    *,
    coordinates=LIGAND,
    receipt_bytes: bytes | None = None,
) -> Mixed64CoordinateSourcePayloadV1:
    label = f"{kind}-{ordinal}"
    return Mixed64CoordinateSourcePayloadV1(
        source_kind=kind,
        source_ordinal=ordinal,
        proposal_identity_payload_canonical_json=_proposal(label),
        source_receipt_canonical_json=receipt_bytes or _receipt(f"receipt-{label}"),
        coordinates=coordinates,
        proposal_lineage_canonical_json=(
            _lineage(int(ordinal)) if kind == SOURCE_KIND_V7_CONTROL else None
        ),
    )


def _atomic_features(*, available: bool = True, out_of_range: bool = False):
    if not available:
        return ()
    rows = (
        (FEATURE_LIGAND_ACCEPTOR, (2,)),
        (FEATURE_LIGAND_AROMATIC_PLANE, (5, 6, 7)),
        (FEATURE_LIGAND_DONOR, (0, 1)),
        (FEATURE_LIGAND_POSITIVE_SITE, (3,)),
        (FEATURE_LIGAND_SHAPE_AXIS, (8, 9, 10)),
        (FEATURE_POCKET_SHAPE_AXIS, (8, 9, 10)),
        (FEATURE_RECEPTOR_ACCEPTOR, ((999,) if out_of_range else (2,))),
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
                    source_receipt_sha256=hashlib.sha256(
                        f"feature-source-{kind}".encode("ascii")
                    ).hexdigest(),
                    geometry_receipt_sha256=hashlib.sha256(
                        f"feature-geometry-{kind}".encode("ascii")
                    ).hexdigest(),
                )
                for kind, indices in rows
            ),
            key=lambda value: (value.kind, value.receipt_sha256),
        )
    )


def _fixture(
    *,
    feature_available: bool = True,
    conformer_available: bool = True,
    exact_coordinates=LIGAND,
    short_conformer_rank: int | None = None,
    out_of_range: bool = False,
):
    exact_receipt = _receipt("exact-v11")
    exact = _source(
        SOURCE_KIND_EXACT_V11_BASE,
        None,
        coordinates=exact_coordinates,
        receipt_bytes=exact_receipt,
    )
    controls = tuple(
        _source(
            SOURCE_KIND_V7_CONTROL,
            index,
            coordinates=_shifted(LIGAND, index / 100.0),
        )
        for index in V7_CONTROL_SOURCE_INDICES
    )
    conformers = tuple(
        _source(
            SOURCE_KIND_TRUE_CONFORMER,
            rank,
            coordinates=(
                _shifted(LIGAND[:-1], rank / 100.0)
                if rank == short_conformer_rank
                else _shifted(LIGAND, rank / 100.0)
            ),
        )
        for rank in TRUE_CONFORMER_RANKS
    )
    retained = tuple(
        _source(
            SOURCE_KIND_RETAINED_CONTROL,
            index,
            coordinates=_shifted(LIGAND, index / 1000.0),
        )
        for index in RETAINED_SOURCE_INDICES
    )
    ligand_topology_sha256 = hashlib.sha256(b"ligand-topology").hexdigest()
    receptor_topology_sha256 = hashlib.sha256(b"receptor-topology").hexdigest()
    exact_evidence = Mixed64ExactV11SourceEvidence(
        source_receipt_sha256=exact.source_receipt_sha256,
        proposal_sha256=exact.proposal_sha256,
        ligand_coordinate_sha256=exact.coordinate_sha256,
        receptor_coordinate_sha256=coordinate_sha256(RECEPTOR),
        prepared_ligand_topology_sha256=ligand_topology_sha256,
        prepared_receptor_topology_sha256=receptor_topology_sha256,
        ligand_vdw_radii_sha256=_digest([float(1.2).hex()] * len(LIGAND)),
        ligand_heavy_atom_mask_sha256=_digest([True] * len(LIGAND)),
        receptor_vdw_radii_sha256=_digest([float(1.2).hex()] * len(RECEPTOR)),
    )
    features = Mixed64FeatureEvidence(
        exact_v11_source_receipt_sha256=exact.source_receipt_sha256,
        prepared_ligand_topology_sha256=ligand_topology_sha256,
        prepared_receptor_topology_sha256=receptor_topology_sha256,
        exact_v11_source=exact_evidence,
        feature_extractor_policy_sha256=hashlib.sha256(b"feature-policy").hexdigest(),
        atomic_features=_atomic_features(
            available=feature_available,
            out_of_range=out_of_range,
        ),
        v7_control_sources=tuple(
            Mixed64V7ControlSourceEvidence(
                source_index=int(source.source_ordinal),
                proposal_mode=(
                    "pocket_centered_control"
                    if int(source.source_ordinal) < 8
                    else "uniform_source_control"
                ),
                proposal_sha256=source.proposal_sha256,
                coordinate_sha256=source.coordinate_sha256,
                proposal_lineage_sha256=str(source.proposal_lineage_sha256),
                source_receipt_sha256=source.source_receipt_sha256,
            )
            for source in controls
        ),
        conformer_sources=(
            tuple(
                Mixed64ConformerSourceEvidence(
                    rank=int(source.source_ordinal),
                    proposal_sha256=source.proposal_sha256,
                    coordinate_sha256=source.coordinate_sha256,
                    source_receipt_sha256=source.source_receipt_sha256,
                )
                for source in conformers
            )
            if conformer_available
            else ()
        ),
        retained_sources=tuple(
            Mixed64RetainedSourceEvidence(
                source_index=int(source.source_ordinal),
                proposal_sha256=source.proposal_sha256,
                coordinate_sha256=source.coordinate_sha256,
                source_receipt_sha256=source.source_receipt_sha256,
            )
            for source in retained
        ),
    )
    allocation = build_fixed_mixed64_allocation(features)
    bundle = Mixed64ProposalSourceBundleV1(
        allocation=allocation,
        exact_v11_source=exact,
        v7_control_sources=controls,
        conformer_sources=conformers if conformer_available else (),
        retained_sources=retained,
        ligand_vdw_radii=(1.2,) * len(LIGAND),
        ligand_heavy_atom_mask=(True,) * len(LIGAND),
        receptor_coordinates=RECEPTOR,
        receptor_vdw_radii=(1.2,) * len(RECEPTOR),
        receptor_source_receipt_canonical_json=exact_receipt,
        pocket_center=(0.0, 0.0, 10.0),
        pocket_normal=(0.0, 0.0, 1.0),
        pocket_radius=20.0,
    )
    return allocation, bundle, exact, controls, conformers, retained


def test_full_source_bundle_produces_exact64_repeatably() -> None:
    allocation, bundle, *_ = _fixture()
    first = produce_fixed_mixed64_proposals(allocation, source_bundle=bundle)
    second = produce_fixed_mixed64_proposals(allocation, source_bundle=bundle)

    assert first.receipt_sha256 == second.receipt_sha256
    assert len(first.records) == 64
    assert first.generated_count == 64
    assert first.typed_failure_count == 0
    assert len(first.candidate_coordinates) == 64
    assert all(value is not None for value in first.candidate_coordinates)
    assert tuple(record.slot_index for record in first.records) == tuple(range(64))
    assert all(record.status == GENERATION_STATUS_SUCCESS for record in first.records)


def test_lane_implementations_and_parent_semantics_are_exact() -> None:
    allocation, bundle, *_ = _fixture()
    batch = produce_fixed_mixed64_proposals(allocation, source_bundle=bundle)

    for index in (*range(24), *range(60, 64)):
        record = batch.records[index]
        assert type(record.placement_receipt) is ExactPassthroughPlacementReceiptV1
        assert record.source_proposal_sha256 == (
            allocation.slots[index].selected_generation_parent_proposal_sha256
        )
        assert record.source_coordinate_sha256 == (
            allocation.slots[index].selected_generation_parent_coordinate_sha256
        )
    for index in range(24, 44):
        record = batch.records[index]
        assert type(record.placement_receipt) is IndexedSO3PlacementReceiptV1
        if index >= 36:
            assert record.source_proposal_sha256 != (
                allocation.slots[index].selected_generation_parent_proposal_sha256
            )
            assert record.source_coordinate_sha256 != (
                allocation.slots[index].selected_generation_parent_coordinate_sha256
            )
    for index in range(44, 60):
        assert type(batch.records[index].placement_receipt) is SingleAnchorPlacementReceiptV1


def test_every_success_binds_the_existing_proposal_execution_contract() -> None:
    allocation, bundle, *_ = _fixture()
    batch = produce_fixed_mixed64_proposals(allocation, source_bundle=bundle)

    for slot, record in zip(allocation.slots, batch.records, strict=True):
        proposal = record.proposal_execution_receipt
        assert proposal is not None
        assert proposal.slot_index == slot.slot_index
        assert proposal.allocation_slot_receipt_sha256 == slot.receipt_sha256
        assert proposal.allocation_source_receipt_sha256s == (
            slot.selected_source_receipt_sha256s
        )
        assert proposal.source_proposal_sha256 == record.source_proposal_sha256
        assert proposal.source_coordinate_sha256 == record.source_coordinate_sha256
        assert proposal.generator_config_sha256 == MIXED64_PRODUCER_POLICY_SHA256
        assert proposal.to_dict()["producer_attested"] is False


def test_source_payloads_rederive_proposal_receipt_coordinate_and_lineage() -> None:
    _allocation, bundle, exact, controls, *_ = _fixture()
    document = bundle.to_dict()

    assert exact.proposal_sha256 == hashlib.sha256(
        exact.proposal_identity_payload_canonical_json
    ).hexdigest()
    assert controls[8].proposal_lineage_sha256 == hashlib.sha256(
        controls[8].proposal_lineage_canonical_json
    ).hexdigest()
    assert document["all_present_source_payload_identities_rederived"] is True
    assert document["v7_control_sources"][8]["proposal_lineage"]["source_index"] == 8


def test_allocation_missing_features_remain_in_their_slots() -> None:
    allocation, bundle, *_ = _fixture(
        feature_available=False,
        conformer_available=False,
    )
    batch = produce_fixed_mixed64_proposals(allocation, source_bundle=bundle)

    expected_failures = tuple(range(36, 60))
    assert tuple(
        record.slot_index for record in batch.records if not record.generated
    ) == expected_failures
    assert batch.generated_count == 40
    assert batch.typed_failure_count == 24
    for index in expected_failures:
        failure = batch.records[index].failure_receipt
        assert failure is not None
        assert failure.failure_code == ALLOCATION_MISSING_FEATURE_FAILURE
        assert failure.allocation_missing_feature_codes
        assert failure.to_dict()["slot_preserved_in_denominator"] is True


def test_missing_present_source_payload_is_one_typed_slot_failure() -> None:
    allocation, bundle, *_ = _fixture()
    incomplete = replace(
        bundle,
        v7_control_sources=tuple(
            value for value in bundle.v7_control_sources if value.source_ordinal != 8
        ),
    )
    batch = produce_fixed_mixed64_proposals(allocation, source_bundle=incomplete)

    assert batch.generated_count == 63
    assert batch.typed_failure_count == 1
    failed = batch.records[8]
    assert failed.status == GENERATION_STATUS_FAILURE
    assert failed.failure_receipt is not None
    assert failed.failure_receipt.failure_code == MISSING_V7_CONTROL_SOURCE_PAYLOAD
    assert failed.output_coordinates is None
    assert failed.proposal_execution_receipt is None


def test_missing_exact_base_preserves_all_dependent_slots() -> None:
    allocation, bundle, *_ = _fixture()
    incomplete = replace(bundle, exact_v11_source=None)
    batch = produce_fixed_mixed64_proposals(allocation, source_bundle=incomplete)

    failed_indices = tuple(
        record.slot_index for record in batch.records if not record.generated
    )
    assert failed_indices == (*range(24, 36), *range(44, 60))
    assert all(
        batch.records[index].failure_receipt.failure_code
        == MISSING_EXACT_V11_SOURCE_PAYLOAD
        for index in failed_indices
    )


def test_typed_geometry_failures_keep_the_full_denominator() -> None:
    degenerate = tuple((0.0, 0.0, 0.0) for _ in LIGAND)
    allocation, bundle, *_ = _fixture(exact_coordinates=degenerate)
    batch = produce_fixed_mixed64_proposals(allocation, source_bundle=bundle)

    assert len(batch.records) == 64
    assert all(
        batch.records[index].failure_receipt.failure_code
        == "degenerate_so3_source_geometry"
        for index in range(24, 36)
    )
    assert all(batch.records[index].output_coordinates is None for index in range(24, 36))
    assert batch.typed_failure_count >= 12


def test_feature_atom_out_of_range_becomes_typed_anchor_failure() -> None:
    allocation, bundle, *_ = _fixture(out_of_range=True)
    batch = produce_fixed_mixed64_proposals(allocation, source_bundle=bundle)
    assert all(
        batch.records[index].failure_receipt.failure_code
        == "feature_atom_index_out_of_range"
        for index in range(44, 48)
    )


def test_source_cross_wiring_fails_before_generation() -> None:
    allocation, bundle, *_ = _fixture()
    changed = replace(
        bundle.v7_control_sources[0],
        proposal_identity_payload_canonical_json=_proposal("wrong"),
    )
    with pytest.raises(Mixed64ProposalProducerError) as captured:
        replace(bundle, v7_control_sources=(changed, *bundle.v7_control_sources[1:]))
    assert captured.value.code == SOURCE_PAYLOAD_CROSS_WIRING


def test_exact_source_proposal_coordinate_and_receptor_cross_wires_fail_closed() -> None:
    _allocation, bundle, *_ = _fixture()
    exact = bundle.exact_v11_source
    assert exact is not None

    wrong_proposal = replace(
        exact,
        proposal_identity_payload_canonical_json=_proposal("cross-wired-exact"),
    )
    with pytest.raises(Mixed64ProposalProducerError) as captured:
        replace(bundle, exact_v11_source=wrong_proposal)
    assert captured.value.code == SOURCE_PAYLOAD_CROSS_WIRING

    wrong_coordinates = replace(
        exact,
        coordinates=_shifted(exact.coordinates, 0.125),
    )
    with pytest.raises(Mixed64ProposalProducerError) as captured:
        replace(bundle, exact_v11_source=wrong_coordinates)
    assert captured.value.code == SOURCE_PAYLOAD_CROSS_WIRING

    with pytest.raises(Mixed64ProposalProducerError) as captured:
        replace(bundle, receptor_coordinates=_shifted(RECEPTOR, 0.125))
    assert captured.value.code == SOURCE_PAYLOAD_CROSS_WIRING


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("ligand_vdw_radii", (1.3,) * len(LIGAND)),
        (
            "ligand_heavy_atom_mask",
            (False,) + (True,) * (len(LIGAND) - 1),
        ),
        ("receptor_vdw_radii", (1.3,) * len(RECEPTOR)),
    ),
)
def test_topology_derived_parameter_cross_wires_fail_closed(
    field: str,
    value: object,
) -> None:
    _allocation, bundle, *_ = _fixture()
    with pytest.raises(Mixed64ProposalProducerError) as captured:
        replace(bundle, **{field: value})
    assert captured.value.code == SOURCE_PAYLOAD_CROSS_WIRING


def test_noncanonical_and_invalid_receipt_payloads_fail_closed() -> None:
    with pytest.raises(Mixed64ProposalProducerError) as captured:
        Mixed64CoordinateSourcePayloadV1(
            source_kind=SOURCE_KIND_EXACT_V11_BASE,
            source_ordinal=None,
            proposal_identity_payload_canonical_json=b'{"z": 1}',
            source_receipt_canonical_json=_receipt("x"),
            coordinates=LIGAND,
        )
    assert captured.value.code == SOURCE_PAYLOAD_NONCANONICAL

    invalid_receipt = _canonical(
        {
            "schema_id": "broken",
            "receipt_sha256": "0" * 64,
        }
    )
    with pytest.raises(Mixed64ProposalProducerError) as captured:
        _source(
            SOURCE_KIND_EXACT_V11_BASE,
            None,
            receipt_bytes=invalid_receipt,
        )
    assert captured.value.code == SOURCE_PAYLOAD_RECEIPT_INVALID


def test_all_source_atom_denominators_must_match() -> None:
    with pytest.raises(Mixed64ProposalProducerError) as captured:
        _fixture(short_conformer_rank=2)
    assert captured.value.code == LIGAND_ATOM_DENOMINATOR_MISMATCH


def test_source_postflight_drift_discards_the_batch(monkeypatch: pytest.MonkeyPatch) -> None:
    import betelgeuze_engine_v2.docking.mixed64_proposal_producer_v3 as producer

    allocation, bundle, *_ = _fixture()
    observed = iter(("1" * 64, "2" * 64, "3" * 64))
    monkeypatch.setattr(producer, "_stable_source_sha256", lambda _path: next(observed))

    with pytest.raises(Mixed64ProposalProducerError) as captured:
        producer.produce_fixed_mixed64_proposals(allocation, source_bundle=bundle)
    assert captured.value.code == "producer_implementation_source_changed"


def test_generation_record_validates_exact_inputs_before_slot_lookup() -> None:
    import betelgeuze_engine_v2.docking.mixed64_proposal_producer_v3 as producer

    allocation, bundle, *_ = _fixture()
    record = produce_fixed_mixed64_proposals(
        allocation,
        source_bundle=bundle,
    ).records[0]

    with pytest.raises(Mixed64ProposalProducerError) as captured:
        replace(
            record,
            slot_index=64,
            _factory_seal=producer._RECORD_FACTORY_SEAL,
        )
    assert captured.value.code == SOURCE_PAYLOAD_CROSS_WIRING

    with pytest.raises(TypeError, match="allocation must be exact"):
        replace(
            record,
            allocation=object(),
            _factory_seal=producer._RECORD_FACTORY_SEAL,
        )


def test_stable_source_hash_rejects_empty_regular_data(tmp_path: Path) -> None:
    import betelgeuze_engine_v2.docking.mixed64_proposal_producer_v3 as producer

    empty = tmp_path / "empty.py"
    empty.write_bytes(b"")
    with pytest.raises(Mixed64ProposalProducerError) as captured:
        producer._stable_source_sha256(empty)
    assert captured.value.code == "producer_implementation_source_changed"


def test_producer_rejects_live_source_mutation_before_generation() -> None:
    allocation, bundle, *_ = _fixture()
    object.__setattr__(bundle, "pocket_center", (99.0, 99.0, 99.0))

    with pytest.raises(Mixed64ProposalProducerError) as captured:
        produce_fixed_mixed64_proposals(allocation, source_bundle=bundle)
    assert captured.value.code == SOURCE_PAYLOAD_CROSS_WIRING


def test_batch_authority_and_downstream_stages_remain_false() -> None:
    allocation, bundle, *_ = _fixture()
    document = produce_fixed_mixed64_proposals(
        allocation,
        source_bundle=bundle,
    ).to_dict()

    assert document["candidate_denominator"] == 64
    assert document["denominator_failure_complete"] is True
    assert document["generation_scope_source_payloads_rederived"] is True
    assert document["producer_attested"] is False
    assert document["activation_evidence_eligible"] is False
    assert document["post_refinement_admission_complete"] is False
    assert document["scorer_v1_reexecuted"] is False
    assert document["pose_validity_reexecuted"] is False
    assert document["reservation_allowed"] is False
    assert document["molecular_execution_authorized"] is False
    assert document["public_or_scientific_claim_authorized"] is False


def test_policy_is_fixed64_and_all_authority_false() -> None:
    policy = frozen_mixed64_producer_policy()
    assert policy["candidate_denominator"] == 64
    assert len(MIXED64_PRODUCER_POLICY_SHA256) == 64
    assert policy["failure_semantics"]["slot_reallocation_allowed"] is False
    assert all(value is False for value in policy["authority"].values())


def test_producer_signature_cannot_consume_results_or_authority() -> None:
    parameters = set(inspect.signature(produce_fixed_mixed64_proposals).parameters)
    assert not parameters & {
        "authority",
        "benchmark_outcome",
        "fresh",
        "native_pose",
        "rank",
        "reservation",
        "rmsd",
        "score",
        "validity_result",
    }
    assert Path(inspect.getsourcefile(produce_fixed_mixed64_proposals) or "").is_file()
