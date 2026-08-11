from __future__ import annotations

import hashlib
import inspect
import json
import math

import pytest
import torch

from betelgeuze_engine_v2.docking.geometric_admission_v3 import GeometricAdmissionV3
from betelgeuze_engine_v2.docking.mixed64_allocation import (
    Mixed64ConformerSourceEvidence,
    Mixed64ExactV11SourceEvidence,
    Mixed64FeatureEvidence,
    Mixed64RetainedSourceEvidence,
    Mixed64V7ControlSourceEvidence,
    build_fixed_mixed64_allocation,
)
from betelgeuze_engine_v2.docking.mixed64_operational_proposal_v3 import (
    MATERIALIZED_STATUS,
    MIXED64_OPERATIONAL_PROPOSAL_POLICY_SHA256,
    SOURCE_PROPOSAL_IDENTITY_NOT_OPERATIONAL,
    TYPED_MATERIALIZATION_FAILURE_STATUS,
    UPSTREAM_NOT_MATERIALIZED_STATUS,
    Mixed64OperationalProposalRecordV1,
    Mixed64OperationalProposalV3Error,
    frozen_mixed64_operational_proposal_policy,
    materialize_mixed64_operational_proposals,
)
from betelgeuze_engine_v2.docking.mixed64_proposal_geometry_v3 import (
    IndexedSO3PlacementReceiptV1,
    coordinate_sha256,
)
from betelgeuze_engine_v2.docking.mixed64_proposal_producer_v3 import (
    Mixed64CoordinateSourcePayloadV1,
    Mixed64ProposalSourceBundleV1,
    produce_fixed_mixed64_proposals,
)
from betelgeuze_engine_v2.docking.proposals import bind_docking_proposal_state
from tests.unit.test_engine_v2_mixed64_proposal_producer_v3 import _fixture


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode("ascii")).hexdigest()


def _canonical(document: object) -> bytes:
    return json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _operational_source(
    source: Mixed64CoordinateSourcePayloadV1,
    *,
    coordinate_identity_override: str | None = None,
    problem_label: str = "problem",
    nonidentity_transform: bool = False,
) -> Mixed64CoordinateSourcePayloadV1:
    coordinates = torch.tensor(source.coordinates, dtype=torch.float64)
    proposal_index = 0 if source.source_ordinal is None else source.source_ordinal
    rotation = (
        torch.tensor(
            ((0.0, -1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
            dtype=torch.float64,
        )
        if nonidentity_transform
        else torch.eye(3, dtype=torch.float64)
    )
    translation = (
        torch.tensor((2.0, -3.0, 5.0), dtype=torch.float64)
        if nonidentity_transform
        else torch.zeros(3, dtype=torch.float64)
    )
    proposal = bind_docking_proposal_state(
        coordinates=coordinates,
        torsion_angles=torch.zeros(len(source.coordinates), dtype=torch.float64),
        rotation=rotation,
        translation=translation,
        proposal_index=proposal_index,
        seed=1000 + proposal_index,
        problem_fingerprint_sha256=_digest(problem_label),
        search_space_fingerprint_sha256=_digest("search-space"),
    )
    identity = proposal.identity_payload()
    if coordinate_identity_override is not None:
        identity["coordinate_fingerprint_sha256"] = coordinate_identity_override
    return Mixed64CoordinateSourcePayloadV1(
        source_kind=source.source_kind,
        source_ordinal=source.source_ordinal,
        proposal_identity_payload_canonical_json=_canonical(identity),
        source_receipt_canonical_json=source.source_receipt_canonical_json,
        coordinates=source.coordinates,
        proposal_lineage_canonical_json=source.proposal_lineage_canonical_json,
    )


def _operational_fixture(
    *,
    corrupt_exact_coordinate_identity: bool = False,
    crosswire_control_problem: bool = False,
    nonidentity_source_transform: bool = False,
):
    original_allocation, original_bundle, exact, controls, conformers, retained = (
        _fixture()
    )
    operational_exact = _operational_source(
        exact,
        coordinate_identity_override=(
            _digest("wrong-coordinate") if corrupt_exact_coordinate_identity else None
        ),
        nonidentity_transform=nonidentity_source_transform,
    )
    operational_controls = tuple(
        _operational_source(
            value,
            problem_label=(
                "wrong-problem"
                if crosswire_control_problem and value.source_ordinal == 0
                else "problem"
            ),
            nonidentity_transform=nonidentity_source_transform,
        )
        for value in controls
    )
    operational_conformers = tuple(
        _operational_source(
            value,
            nonidentity_transform=nonidentity_source_transform,
        )
        for value in conformers
    )
    operational_retained = tuple(
        _operational_source(
            value,
            nonidentity_transform=nonidentity_source_transform,
        )
        for value in retained
    )
    original_features = original_allocation.features
    distant_receptor = tuple(
        (point[0], point[1], point[2] + 1_000.0)
        for point in original_bundle.receptor_coordinates
    )
    exact_source = Mixed64ExactV11SourceEvidence(
        source_receipt_sha256=operational_exact.source_receipt_sha256,
        proposal_sha256=operational_exact.proposal_sha256,
        ligand_coordinate_sha256=operational_exact.coordinate_sha256,
        receptor_coordinate_sha256=coordinate_sha256(distant_receptor),
        prepared_ligand_topology_sha256=(
            original_features.prepared_ligand_topology_sha256
        ),
        prepared_receptor_topology_sha256=(
            original_features.prepared_receptor_topology_sha256
        ),
    )
    features = Mixed64FeatureEvidence(
        exact_v11_source_receipt_sha256=operational_exact.source_receipt_sha256,
        prepared_ligand_topology_sha256=(
            original_features.prepared_ligand_topology_sha256
        ),
        prepared_receptor_topology_sha256=(
            original_features.prepared_receptor_topology_sha256
        ),
        exact_v11_source=exact_source,
        feature_extractor_policy_sha256=(
            original_features.feature_extractor_policy_sha256
        ),
        atomic_features=original_features.atomic_features,
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
            for source in operational_controls
        ),
        conformer_sources=tuple(
            Mixed64ConformerSourceEvidence(
                rank=int(source.source_ordinal),
                proposal_sha256=source.proposal_sha256,
                coordinate_sha256=source.coordinate_sha256,
                source_receipt_sha256=source.source_receipt_sha256,
            )
            for source in operational_conformers
        ),
        retained_sources=tuple(
            Mixed64RetainedSourceEvidence(
                source_index=int(source.source_ordinal),
                proposal_sha256=source.proposal_sha256,
                coordinate_sha256=source.coordinate_sha256,
                source_receipt_sha256=source.source_receipt_sha256,
            )
            for source in operational_retained
        ),
    )
    allocation = build_fixed_mixed64_allocation(features)
    bundle = Mixed64ProposalSourceBundleV1(
        allocation=allocation,
        exact_v11_source=operational_exact,
        v7_control_sources=operational_controls,
        conformer_sources=operational_conformers,
        retained_sources=operational_retained,
        ligand_vdw_radii=original_bundle.ligand_vdw_radii,
        ligand_heavy_atom_mask=original_bundle.ligand_heavy_atom_mask,
        receptor_coordinates=distant_receptor,
        receptor_vdw_radii=original_bundle.receptor_vdw_radii,
        receptor_source_receipt_canonical_json=(
            original_bundle.receptor_source_receipt_canonical_json
        ),
        pocket_center=(0.0, 0.0, 100.0),
        pocket_normal=original_bundle.pocket_normal,
        pocket_radius=200.0,
    )
    producer = produce_fixed_mixed64_proposals(allocation, source_bundle=bundle)
    admission = GeometricAdmissionV3().admit_producer_batch(producer)
    return allocation, bundle, producer, admission


def test_exact_operational_sources_materialize_all_admitted_slots_repeatably() -> None:
    _allocation, _bundle, producer, admission = _operational_fixture()
    first = materialize_mixed64_operational_proposals(admission)
    second = materialize_mixed64_operational_proposals(admission)

    assert first.receipt_sha256 == second.receipt_sha256
    assert len(first.records) == 64
    assert first.materialized_count == admission.accepted_count
    assert first.typed_materialization_failure_count == 0
    assert first.upstream_not_materialized_count == admission.nonaccepted_count
    for producer_record, admission_decision, record in zip(
        producer.records,
        admission.decisions,
        first.records,
        strict=True,
    ):
        assert record.admission_decision.receipt_sha256 == (
            admission_decision.receipt_sha256
        )
        if record.status == MATERIALIZED_STATUS:
            assert record.operational_proposal is not None
            assert (
                tuple(
                    tuple(float(component) for component in point)
                    for point in record.operational_proposal.coordinates.tolist()
                )
                == producer_record.output_coordinates
            )
            assert record.operational_proposal.proposal_index == record.slot_index


def test_passthrough_preserves_source_separately_and_binds_fixed64_slot_identity() -> (
    None
):
    _allocation, _bundle, producer, admission = _operational_fixture()
    batch = materialize_mixed64_operational_proposals(admission)

    passthrough = next(
        value for value in batch.records if value.materialized and value.slot_index < 24
    )
    transformed = next(
        value
        for value in batch.records
        if value.materialized and 24 <= value.slot_index < 60
    )
    assert passthrough.source_operational_proposal.fingerprint_sha256 == (
        producer.records[passthrough.slot_index].source_proposal_sha256
    )
    assert passthrough.operational_proposal.proposal_index == passthrough.slot_index
    assert transformed.operational_proposal.fingerprint_sha256 != (
        producer.records[transformed.slot_index].source_proposal_sha256
    )
    assert transformed.source_operational_proposal.torsion_angles.tolist() == (
        transformed.operational_proposal.torsion_angles.tolist()
    )
    assert transformed.source_operational_proposal.problem_fingerprint_sha256 == (
        transformed.operational_proposal.problem_fingerprint_sha256
    )

    retained = batch.records[60]
    assert retained.source_operational_proposal.proposal_index == 36
    assert retained.operational_proposal.proposal_index == 60
    assert retained.source_operational_proposal.fingerprint_sha256 != (
        retained.operational_proposal.fingerprint_sha256
    )


def test_transformed_lane_composes_source_then_placement_rigid_transform() -> None:
    _allocation, _bundle, _producer, admission = _operational_fixture(
        nonidentity_source_transform=True
    )
    batch = materialize_mixed64_operational_proposals(admission)
    passthrough = next(value for value in batch.records[:24] if value.materialized)
    assert torch.equal(
        passthrough.operational_proposal.rotation,
        passthrough.source_operational_proposal.rotation,
    )
    assert torch.equal(
        passthrough.operational_proposal.translation,
        passthrough.source_operational_proposal.translation,
    )
    record = next(value for value in batch.records[24:60] if value.materialized)
    source = record.source_operational_proposal
    operational = record.operational_proposal
    placement = record.admission_decision.producer_record.placement_receipt
    assert source is not None and operational is not None and placement is not None
    x, y, z, w = placement.quaternion
    norm = math.sqrt(x * x + y * y + z * z + w * w)
    x, y, z, w = (value / norm for value in (x, y, z, w))
    placement_rotation = torch.tensor(
        (
            (1.0 - 2.0 * (y * y + z * z), 2.0 * (x * y - z * w), 2.0 * (x * z + y * w)),
            (2.0 * (x * y + z * w), 1.0 - 2.0 * (x * x + z * z), 2.0 * (y * z - x * w)),
            (2.0 * (x * z - y * w), 2.0 * (y * z + x * w), 1.0 - 2.0 * (x * x + y * y)),
        ),
        dtype=torch.float64,
    )
    placement_translation = torch.tensor(
        placement.translation,
        dtype=torch.float64,
    )
    if type(placement) is IndexedSO3PlacementReceiptV1:
        source_centroid = torch.tensor(
            tuple(
                sum(point[axis] for point in placement.source_coordinates)
                / len(placement.source_coordinates)
                for axis in range(3)
            ),
            dtype=torch.float64,
        )
        placement_translation = (
            placement_translation - source_centroid @ placement_rotation.T
        )

    assert torch.equal(
        operational.rotation,
        placement_rotation @ source.rotation,
    )
    assert torch.equal(
        operational.translation,
        source.translation @ placement_rotation.T + placement_translation,
    )
    assert not torch.equal(operational.rotation, placement_rotation)


def test_all_admitted_indexed_so3_slots_rederive_their_affine_transform() -> None:
    _allocation, _bundle, producer, admission = _operational_fixture()
    batch = materialize_mixed64_operational_proposals(admission)
    admitted_so3 = [
        decision.slot_index
        for decision in admission.decisions
        if decision.status == "accepted"
        and type(decision.producer_record.placement_receipt)
        is IndexedSO3PlacementReceiptV1
    ]

    assert admitted_so3 == list(range(24, 44))
    for slot_index in admitted_so3:
        record = batch.records[slot_index]
        assert record.status == MATERIALIZED_STATUS
        assert record.failure_code is None
        assert record.operational_proposal is not None
        assert (
            tuple(
                tuple(float(component) for component in point)
                for point in record.operational_proposal.coordinates.tolist()
            )
            == producer.records[slot_index].output_coordinates
        )


def test_unexpected_runtime_failure_is_not_relabeled_as_typed_slot_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import betelgeuze_engine_v2.docking.mixed64_operational_proposal_v3 as module

    _allocation, _bundle, _producer, admission = _operational_fixture()

    def unexpected_runtime_failure(**_kwargs):
        raise RuntimeError("unexpected materialization failure")

    monkeypatch.setattr(
        module,
        "bind_docking_proposal_state",
        unexpected_runtime_failure,
    )
    with pytest.raises(RuntimeError, match="unexpected materialization failure"):
        materialize_mixed64_operational_proposals(admission)


def test_binary64_overflow_is_a_declared_identity_failure() -> None:
    import betelgeuze_engine_v2.docking.mixed64_operational_proposal_v3 as module

    with pytest.raises(Mixed64OperationalProposalV3Error) as captured:
        module._float_vector(
            {
                "dtype": "float64",
                "shape": [1],
                "values_binary64_hex": ["0x1p+999999999"],
            },
            name="overflow",
            expected_shape=(1,),
        )
    assert captured.value.code == SOURCE_PROPOSAL_IDENTITY_NOT_OPERATIONAL


def test_receipt_capacity_is_distinct_from_source_identity_capacity() -> None:
    import betelgeuze_engine_v2.docking.mixed64_operational_proposal_v3 as module

    payload, receipt_sha256 = module._seal_projection(
        {"payload": "x" * (4 * 1024 * 1024 + 1)}
    )
    assert len(payload) > 4 * 1024 * 1024
    assert hashlib.sha256(payload).hexdigest() == receipt_sha256


def test_admission_live_mutation_fails_before_operational_materialization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import betelgeuze_engine_v2.docking.mixed64_operational_proposal_v3 as module

    _allocation, _bundle, _producer, admission = _operational_fixture()
    object.__setattr__(admission.decisions[0], "status", "tampered")

    def unexpected_materialization(**_kwargs):
        raise AssertionError("proposal materialization must not start")

    monkeypatch.setattr(
        module,
        "bind_docking_proposal_state",
        unexpected_materialization,
    )
    with pytest.raises(
        Mixed64OperationalProposalV3Error,
        match="live integrity preflight",
    ):
        materialize_mixed64_operational_proposals(admission)


def test_operational_batch_detects_live_proposal_tensor_mutation() -> None:
    _allocation, _bundle, _producer, admission = _operational_fixture()
    batch = materialize_mixed64_operational_proposals(admission)
    record = next(value for value in batch.records if value.materialized)
    assert record.operational_proposal is not None
    record.operational_proposal.coordinates[0, 0] += 1.0

    with pytest.raises(
        Mixed64OperationalProposalV3Error,
        match="record live integrity failed",
    ):
        batch.assert_live_integrity()


def test_historical_nonoperational_source_identity_is_typed_not_guessed() -> None:
    allocation, bundle, *_ = _fixture()
    producer = produce_fixed_mixed64_proposals(allocation, source_bundle=bundle)
    admission = GeometricAdmissionV3().admit_producer_batch(producer)
    batch = materialize_mixed64_operational_proposals(admission)

    assert batch.typed_materialization_failure_count == admission.accepted_count
    assert all(
        record.failure_code == SOURCE_PROPOSAL_IDENTITY_NOT_OPERATIONAL
        for record in batch.records
        if record.status == TYPED_MATERIALIZATION_FAILURE_STATUS
    )
    assert all(
        record.operational_proposal is None
        for record in batch.records
        if record.status != MATERIALIZED_STATUS
    )


def test_source_coordinate_identity_cross_wiring_is_typed_per_dependent_slot() -> None:
    _allocation, _bundle, _producer, admission = _operational_fixture(
        corrupt_exact_coordinate_identity=True
    )
    batch = materialize_mixed64_operational_proposals(admission)

    failed = tuple(
        value
        for value in batch.records
        if value.status == TYPED_MATERIALIZATION_FAILURE_STATUS
    )
    assert failed
    assert all(value.operational_proposal is None for value in failed)
    assert all(
        value.failure_code == SOURCE_PROPOSAL_IDENTITY_NOT_OPERATIONAL
        for value in failed
    )


def test_upstream_rejections_never_materialize_proposal_state() -> None:
    _allocation, _bundle, _producer, admission = _operational_fixture()
    batch = materialize_mixed64_operational_proposals(admission)

    for decision, record in zip(admission.decisions, batch.records, strict=True):
        if not decision.accepted:
            assert record.status == UPSTREAM_NOT_MATERIALIZED_STATUS
            assert record.source_payload is None
            assert record.operational_proposal is None


def test_cross_wired_problem_identity_fails_the_whole_batch() -> None:
    _allocation, _bundle, _producer, admission = _operational_fixture(
        crosswire_control_problem=True
    )

    with pytest.raises(Mixed64OperationalProposalV3Error, match="problem identity"):
        materialize_mixed64_operational_proposals(admission)


def test_public_proposal_factory_rederives_identity_without_fingerprint_input() -> None:
    coordinates = torch.tensor(((1.0, 2.0, 3.0),), dtype=torch.float64)
    proposal = bind_docking_proposal_state(
        coordinates=coordinates,
        torsion_angles=torch.zeros(1, dtype=torch.float64),
        rotation=torch.eye(3, dtype=torch.float64),
        translation=torch.zeros(3, dtype=torch.float64),
        proposal_index=7,
        seed=11,
        problem_fingerprint_sha256=_digest("problem-factory"),
        search_space_fingerprint_sha256=_digest("search-factory"),
    )

    assert hashlib.sha256(_canonical(proposal.identity_payload())).hexdigest() == (
        proposal.fingerprint_sha256
    )
    assert (
        "fingerprint_sha256"
        not in inspect.signature(bind_docking_proposal_state).parameters
    )


def test_record_cannot_be_forged_without_factory() -> None:
    _allocation, _bundle, _producer, admission = _operational_fixture()
    with pytest.raises(Mixed64OperationalProposalV3Error, match="bounded factory"):
        Mixed64OperationalProposalRecordV1(
            admission_decision=admission.decisions[0],
            source_payload=None,
            source_operational_proposal=None,
            operational_proposal=None,
            status=UPSTREAM_NOT_MATERIALIZED_STATUS,
            failure_code=None,
        )


def test_policy_and_output_keep_all_authority_false() -> None:
    _allocation, _bundle, _producer, admission = _operational_fixture()
    policy = frozen_mixed64_operational_proposal_policy()
    batch = materialize_mixed64_operational_proposals(admission)
    document = batch.to_dict()

    assert len(MIXED64_OPERATIONAL_PROPOSAL_POLICY_SHA256) == 64
    assert policy["candidate_denominator"] == 64
    assert (
        policy["transformed_identity"]["operational_proposal_index_is_fixed64_slot"]
        is True
    )
    assert policy["failure_semantics"]["unexpected_runtime_failure_typed"] is False
    assert all(value is False for value in policy["authority"].values())
    assert document["producer_attested"] is False
    assert document["admission_batch"]["receipt_sha256"] == (admission.receipt_sha256)
    assert document["activation_evidence_eligible"] is False
    assert document["refinement_scoring_validity_executed"] is False
    assert document["molecular_execution_authorized"] is False
    assert document["reservation_allowed"] is False


def test_materializer_accepts_no_caller_coordinates_results_or_authority() -> None:
    parameters = set(
        inspect.signature(materialize_mixed64_operational_proposals).parameters
    )
    assert parameters == {"admission_batch"}
    assert not parameters & {
        "coordinates",
        "score",
        "rank",
        "validity",
        "refinement_result",
        "authority",
        "reservation",
    }
