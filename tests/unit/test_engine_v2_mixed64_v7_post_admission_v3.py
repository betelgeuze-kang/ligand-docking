from __future__ import annotations

from dataclasses import replace
import hashlib
import inspect
import json
from pathlib import Path

import pytest
import torch

from betelgeuze_engine_v2 import (
    AllAtomSystem,
    Atom,
    Bond,
    Chain,
    Residue,
    StructureProvenance,
)
import betelgeuze_engine_v2.docking.torsion_contact_refinement as refinement_module
import betelgeuze_engine_v2.docking.mixed64_v7_post_admission_v3 as v7_module
from betelgeuze_engine_v2.docking import (
    DockingScope,
    PocketDefinition,
    build_element_aware_authenticated_known_pocket_docking_problem,
)
from betelgeuze_engine_v2.docking.geometric_admission_v3 import GeometricAdmissionV3
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
    coordinate_sha256,
)
from betelgeuze_engine_v2.docking.mixed64_operational_proposal_v3 import (
    MATERIALIZED_STATUS,
    materialize_mixed64_operational_proposals,
)
from betelgeuze_engine_v2.docking.mixed64_proposal_producer_v3 import (
    SOURCE_KIND_EXACT_V11_BASE,
    SOURCE_KIND_RETAINED_CONTROL,
    SOURCE_KIND_TRUE_CONFORMER,
    SOURCE_KIND_V7_CONTROL,
    Mixed64CoordinateSourcePayloadV1,
    Mixed64ProposalSourceBundleV1,
    produce_fixed_mixed64_proposals,
)
from betelgeuze_engine_v2.docking.mixed64_v7_post_admission_v3 import (
    POST_REFINEMENT_ACCEPTED_STATUS,
    POST_REFINEMENT_REJECTED_STATUS,
    TYPED_V7_REFINEMENT_FAILURE_STATUS,
    UPSTREAM_NOT_REFINED_STATUS,
    Mixed64V7PostAdmissionRecordV1,
    Mixed64V7PostAdmissionV3Error,
    execute_synthetic_mixed64_v7_post_admission,
)
from betelgeuze_engine_v2.docking.mixed64_v7_post_admission_policy_v3 import (
    MIXED64_V7_POST_ADMISSION_POLICY_SHA256,
    V7_REFINEMENT_MAX_STEPS,
    V7_TORSION_ELIGIBLE_SLOT_INDICES,
    frozen_mixed64_v7_post_admission_policy,
)
from betelgeuze_engine_v2.docking.proposals import bind_docking_proposal_state
from betelgeuze_engine_v2.docking.torsion_contact_refinement import (
    InteractionAwareTorsionContactEnsembleRefinerV7,
    TorsionContactRefinementError,
)


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode("ascii")).hexdigest()


def _provenance(name: str, digest: str) -> StructureProvenance:
    return StructureProvenance(
        source_format="unit",
        source_id=name,
        source_sha256=digest,
        parser_name="mixed64-v7-fixture",
        parser_version="1.0.0",
    )


def _ligand() -> AllAtomSystem:
    elements = ("C", "N", "C", "O")
    atomic_numbers = {"C": 6, "N": 7, "O": 8}
    return AllAtomSystem(
        system_id="mixed64-v7-ligand",
        atoms=tuple(
            Atom(
                index=index,
                name=f"L{index}",
                element=element,
                atomic_number=atomic_numbers[element],
                residue_index=0,
            )
            for index, element in enumerate(elements)
        ),
        bonds=(
            Bond(index=0, atom_i=0, atom_j=1, order=1.0),
            Bond(index=1, atom_i=1, atom_j=2, order=1.0),
            Bond(index=2, atom_i=2, atom_j=3, order=1.0),
        ),
        residues=(
            Residue(
                index=0,
                name="LIG",
                chain_index=0,
                sequence_number=1,
                atom_indices=(0, 1, 2, 3),
            ),
        ),
        chains=(Chain(index=0, chain_id="L", residue_indices=(0,)),),
        coordinates=torch.tensor(
            [
                [
                    [0.0, 0.0, 0.0],
                    [1.4, 0.0, 0.0],
                    [2.8, 0.3, 0.0],
                    [4.1, 1.0, 0.2],
                ]
            ],
            dtype=torch.float64,
        ),
        provenance=_provenance("mixed64-v7-ligand-source", "a" * 64),
    )


def _receptor() -> AllAtomSystem:
    coordinates = [
        [float(x), float(y), float(z)]
        for x in range(-8, 9, 4)
        for y in range(-8, 9, 4)
        for z in (-6, 0, 6)
    ]
    atoms = tuple(
        Atom(
            index=index,
            name=f"R{index}",
            element="C",
            atomic_number=6,
            residue_index=0,
        )
        for index in range(len(coordinates))
    )
    return AllAtomSystem(
        system_id="mixed64-v7-receptor",
        atoms=atoms,
        bonds=(),
        residues=(
            Residue(
                index=0,
                name="REC",
                chain_index=0,
                sequence_number=1,
                atom_indices=tuple(range(len(atoms))),
            ),
        ),
        chains=(Chain(index=0, chain_id="A", residue_indices=(0,)),),
        coordinates=torch.tensor([coordinates], dtype=torch.float64),
        provenance=_provenance("mixed64-v7-receptor-source", "b" * 64),
    )


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _receipt(label: str) -> bytes:
    projection = {
        "schema_id": "betelgeuze.synthetic_v7_source/1.0.0",
        "label": label,
        "authority_granted": False,
    }
    return _canonical(
        {
            **projection,
            "receipt_sha256": hashlib.sha256(_canonical(projection)).hexdigest(),
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


def _source(
    authority,
    *,
    kind: str,
    ordinal: int | None,
    coordinates: tuple[tuple[float, float, float], ...],
    legacy_identity: bool = False,
) -> Mixed64CoordinateSourcePayloadV1:
    proposal_index = 0 if ordinal is None else ordinal
    if legacy_identity:
        identity = {
            "schema_id": "betelgeuze.synthetic_legacy_proposal/1.0.0",
            "ordinal": ordinal,
        }
    else:
        proposal = bind_docking_proposal_state(
            coordinates=torch.tensor(coordinates, dtype=torch.float64),
            torsion_angles=torch.zeros(len(coordinates), dtype=torch.float64),
            rotation=torch.eye(3, dtype=torch.float64),
            translation=torch.zeros(3, dtype=torch.float64),
            proposal_index=proposal_index,
            seed=10_000 + proposal_index,
            problem_fingerprint_sha256=authority.problem.fingerprint_sha256,
            search_space_fingerprint_sha256=authority.search_space.fingerprint_sha256,
        )
        identity = proposal.identity_payload()
    return Mixed64CoordinateSourcePayloadV1(
        source_kind=kind,
        source_ordinal=ordinal,
        proposal_identity_payload_canonical_json=_canonical(identity),
        source_receipt_canonical_json=_receipt(f"{kind}-{ordinal}"),
        coordinates=coordinates,
        proposal_lineage_canonical_json=(
            _lineage(int(ordinal)) if kind == SOURCE_KIND_V7_CONTROL else None
        ),
    )


def _feature_evidence() -> tuple[Mixed64AtomicFeatureEvidence, ...]:
    rows = (
        (FEATURE_LIGAND_ACCEPTOR, (3,)),
        (FEATURE_LIGAND_AROMATIC_PLANE, (0, 1, 2)),
        (FEATURE_LIGAND_DONOR, (1, 0)),
        (FEATURE_LIGAND_POSITIVE_SITE, (1,)),
        (FEATURE_LIGAND_SHAPE_AXIS, (0, 1, 3)),
        (FEATURE_POCKET_SHAPE_AXIS, (0, 1, 2)),
        (FEATURE_RECEPTOR_ACCEPTOR, (0,)),
        (FEATURE_RECEPTOR_AROMATIC_PLANE, (0, 1, 2)),
        (FEATURE_RECEPTOR_DONOR, (1, 0)),
        (FEATURE_RECEPTOR_NEGATIVE_SITE, (2,)),
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


def _fixture(*, legacy_exact_identity: bool = False):
    ligand = _ligand()
    receptor = _receptor()
    shifted_receptor = receptor.coordinates.clone()
    shifted_receptor[..., 0] += 30.0
    receptor = replace(receptor, coordinates=shifted_receptor)
    pocket = PocketDefinition(
        scope=DockingScope.KNOWN_POCKET,
        method_id="mixed64-v7-test-sphere",
        method_version="1.0.0",
        coordinate_frame_id="prepared-receptor-frame-v1",
        center=torch.tensor([0.0, 0.0, 0.0], dtype=torch.float64),
        radius_angstrom=100.0,
        source_artifact_sha256="c" * 64,
        implementation_source_sha256="d" * 64,
    )
    authority = build_element_aware_authenticated_known_pocket_docking_problem(
        receptor,
        ligand,
        pocket,
    )
    ligand_coordinates = tuple(
        tuple(float(component) for component in point)
        for point in ligand.coordinates[0].tolist()
    )
    exact = _source(
        authority,
        kind=SOURCE_KIND_EXACT_V11_BASE,
        ordinal=None,
        coordinates=ligand_coordinates,
        legacy_identity=legacy_exact_identity,
    )
    controls = tuple(
        _source(
            authority,
            kind=SOURCE_KIND_V7_CONTROL,
            ordinal=index,
            coordinates=ligand_coordinates,
        )
        for index in V7_CONTROL_SOURCE_INDICES
    )
    conformers = tuple(
        _source(
            authority,
            kind=SOURCE_KIND_TRUE_CONFORMER,
            ordinal=rank,
            coordinates=ligand_coordinates,
        )
        for rank in TRUE_CONFORMER_RANKS
    )
    retained = tuple(
        _source(
            authority,
            kind=SOURCE_KIND_RETAINED_CONTROL,
            ordinal=index,
            coordinates=ligand_coordinates,
        )
        for index in RETAINED_SOURCE_INDICES
    )
    receptor_coordinates = tuple(
        tuple(float(component) for component in point)
        for point in receptor.coordinates[0].tolist()
    )
    prepared_ligand_topology_sha256 = _digest("ligand-topology")
    prepared_receptor_topology_sha256 = _digest("receptor-topology")
    exact_source_evidence = Mixed64ExactV11SourceEvidence(
        source_receipt_sha256=exact.source_receipt_sha256,
        proposal_sha256=exact.proposal_sha256,
        ligand_coordinate_sha256=exact.coordinate_sha256,
        receptor_coordinate_sha256=coordinate_sha256(receptor_coordinates),
        prepared_ligand_topology_sha256=prepared_ligand_topology_sha256,
        prepared_receptor_topology_sha256=prepared_receptor_topology_sha256,
    )
    features = Mixed64FeatureEvidence(
        exact_v11_source_receipt_sha256=exact.source_receipt_sha256,
        prepared_ligand_topology_sha256=prepared_ligand_topology_sha256,
        prepared_receptor_topology_sha256=prepared_receptor_topology_sha256,
        exact_v11_source=exact_source_evidence,
        feature_extractor_policy_sha256=_digest("feature-policy"),
        atomic_features=_feature_evidence(),
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
        conformer_sources=tuple(
            Mixed64ConformerSourceEvidence(
                rank=int(source.source_ordinal),
                proposal_sha256=source.proposal_sha256,
                coordinate_sha256=source.coordinate_sha256,
                source_receipt_sha256=source.source_receipt_sha256,
            )
            for source in conformers
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
    policy = authority.validity_context.contact_policy
    bundle = Mixed64ProposalSourceBundleV1(
        allocation=allocation,
        exact_v11_source=exact,
        v7_control_sources=controls,
        conformer_sources=conformers,
        retained_sources=retained,
        ligand_vdw_radii=tuple(policy.radius(atom.element) for atom in ligand.atoms),
        ligand_heavy_atom_mask=tuple(atom.element != "H" for atom in ligand.atoms),
        receptor_coordinates=receptor_coordinates,
        receptor_vdw_radii=tuple(
            policy.radius(atom.element) for atom in receptor.atoms
        ),
        receptor_source_receipt_canonical_json=exact.source_receipt_canonical_json,
        pocket_center=tuple(float(value) for value in pocket.center.tolist()),
        pocket_normal=(0.0, 0.0, 1.0),
        pocket_radius=pocket.radius_angstrom,
    )
    producer = produce_fixed_mixed64_proposals(allocation, source_bundle=bundle)
    admission = GeometricAdmissionV3().admit_producer_batch(producer)
    operational = materialize_mixed64_operational_proposals(admission)
    return authority, receptor, ligand, operational


def _refiner(authority, receptor, ligand, *, indices=V7_TORSION_ELIGIBLE_SLOT_INDICES):
    source_sha256 = hashlib.sha256(
        Path(refinement_module.__file__).read_bytes()
    ).hexdigest()
    return InteractionAwareTorsionContactEnsembleRefinerV7(
        authority,
        receptor,
        ligand,
        implementation_source_sha256=source_sha256,
        v3_proposal_indices=indices,
    )


def test_exact_operational_batch_runs_v7_and_post_admission_once() -> None:
    authority, receptor, ligand, operational = _fixture()
    result = execute_synthetic_mixed64_v7_post_admission(
        operational,
        refiner=_refiner(authority, receptor, ligand),
    )

    assert len(result.records) == 64
    assert (
        result.post_refinement_accepted_count
        + result.post_refinement_rejected_count
        + result.typed_refinement_failure_count
        + result.upstream_not_refined_count
        == 64
    )
    assert result.typed_refinement_failure_count == 0
    assert (
        result.post_refinement_accepted_count + result.post_refinement_rejected_count
        == operational.materialized_count
    )
    assert result.exact_pair_evaluation_count == (
        operational.materialized_count
        * len(operational.admission_batch.producer_batch.source_bundle.ligand_vdw_radii)
        * len(
            operational.admission_batch.producer_batch.source_bundle.receptor_coordinates
        )
    )


def test_success_records_bind_v7_lineage_metrics_and_rank_eligibility() -> None:
    authority, receptor, ligand, operational = _fixture()
    result = execute_synthetic_mixed64_v7_post_admission(
        operational,
        refiner=_refiner(authority, receptor, ligand),
    )

    for source, record in zip(operational.records, result.records, strict=True):
        if source.status != MATERIALIZED_STATUS:
            assert record.status == UPSTREAM_NOT_REFINED_STATUS
            assert record.result_proposal is None
            continue
        assert record.result_proposal is not None
        assert record.result_proposal.parent_proposal_fingerprint_sha256 == (
            source.operational_proposal.fingerprint_sha256
        )
        assert record.refinement_receipt["receipt_sha256"] == (
            record.result_proposal.refinement_receipt_sha256
        )
        assert record.post_refinement_metrics is not None
        assert record.rank_eligible is (
            record.status == POST_REFINEMENT_ACCEPTED_STATUS
        )
        assert record.status in {
            POST_REFINEMENT_ACCEPTED_STATUS,
            POST_REFINEMENT_REJECTED_STATUS,
        }

    target = next(
        value for value in result.records if value.result_proposal is not None
    )
    target.result_proposal.coordinates[0, 0] += 1.0
    with pytest.raises(
        Mixed64V7PostAdmissionV3Error,
        match="record live integrity failed",
    ):
        result.assert_live_integrity()


def test_result_refiner_identity_must_match_exact_v7(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority, receptor, ligand, operational = _fixture()
    refiner = _refiner(authority, receptor, ligand)
    original = InteractionAwareTorsionContactEnsembleRefinerV7.refine
    replaced = False

    def refine(self, proposal, *, max_steps):
        nonlocal replaced
        result = original(self, proposal, max_steps=max_steps)
        if replaced:
            return result
        replaced = True
        return bind_docking_proposal_state(
            coordinates=result.coordinates,
            torsion_angles=result.torsion_angles,
            rotation=result.rotation,
            translation=result.translation,
            proposal_index=result.proposal_index,
            seed=result.seed,
            problem_fingerprint_sha256=result.problem_fingerprint_sha256,
            search_space_fingerprint_sha256=(result.search_space_fingerprint_sha256),
            parent_proposal_fingerprint_sha256=(
                result.parent_proposal_fingerprint_sha256
            ),
            refiner_id="wrong-v7-refiner",
            refiner_version=result.refiner_version,
            refinement_receipt_sha256=result.refinement_receipt_sha256,
        )

    monkeypatch.setattr(
        InteractionAwareTorsionContactEnsembleRefinerV7,
        "refine",
        refine,
    )
    with pytest.raises(
        Mixed64V7PostAdmissionV3Error,
        match="result proposal lineage is cross-wired",
    ):
        execute_synthetic_mixed64_v7_post_admission(
            operational,
            refiner=refiner,
        )


def test_nonoperational_upstream_slots_are_never_sent_to_v7() -> None:
    authority, receptor, ligand, operational = _fixture(legacy_exact_identity=True)
    materialized_count = operational.materialized_count
    result = execute_synthetic_mixed64_v7_post_admission(
        operational,
        refiner=_refiner(authority, receptor, ligand),
    )

    assert result.upstream_not_refined_count == 64 - materialized_count
    assert all(
        record.result_proposal is None
        for record in result.records
        if record.status == UPSTREAM_NOT_REFINED_STATUS
    )


def test_one_declared_refinement_error_is_typed_without_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority, receptor, ligand, operational = _fixture()
    refiner = _refiner(authority, receptor, ligand)
    original = InteractionAwareTorsionContactEnsembleRefinerV7.refine
    first_slot = next(
        value.slot_index for value in operational.records if value.materialized
    )
    attempts: list[int] = []

    def refine(self, proposal, *, max_steps):
        attempts.append(proposal.proposal_index)
        if proposal.proposal_index == first_slot:
            raise TorsionContactRefinementError("synthetic numerical failure")
        return original(self, proposal, max_steps=max_steps)

    monkeypatch.setattr(
        InteractionAwareTorsionContactEnsembleRefinerV7, "refine", refine
    )
    result = execute_synthetic_mixed64_v7_post_admission(
        operational,
        refiner=refiner,
    )

    failed = tuple(
        value
        for value in result.records
        if value.status == TYPED_V7_REFINEMENT_FAILURE_STATUS
    )
    assert len(failed) == 1
    assert attempts.count(first_slot) == 1
    assert failed[0].result_proposal is None
    assert failed[0].post_refinement_metrics is None
    assert failed[0].failure_reason == "synthetic numerical failure"
    assert (
        failed[0].to_dict()["failure_reason_sha256"]
        == hashlib.sha256(b"synthetic numerical failure").hexdigest()
    )


def test_unexpected_refinement_runtime_error_aborts_instead_of_becoming_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority, receptor, ligand, operational = _fixture()
    refiner = _refiner(authority, receptor, ligand)
    attempts = 0

    def refine(self, proposal, *, max_steps):
        nonlocal attempts
        attempts += 1
        raise RuntimeError("unexpected refiner implementation failure")

    monkeypatch.setattr(
        InteractionAwareTorsionContactEnsembleRefinerV7,
        "refine",
        refine,
    )
    with pytest.raises(
        RuntimeError,
        match="unexpected refiner implementation failure",
    ):
        execute_synthetic_mixed64_v7_post_admission(
            operational,
            refiner=refiner,
        )
    assert attempts == 1


def test_oversized_typed_failure_reason_aborts_instead_of_truncating_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import betelgeuze_engine_v2.docking.mixed64_v7_post_admission_v3 as module

    authority, receptor, ligand, operational = _fixture()
    refiner = _refiner(authority, receptor, ligand)

    def refine(self, proposal, *, max_steps):
        raise TorsionContactRefinementError(
            "x" * (module.MAX_TYPED_V7_FAILURE_REASON_UTF8_BYTES + 1)
        )

    monkeypatch.setattr(
        InteractionAwareTorsionContactEnsembleRefinerV7,
        "refine",
        refine,
    )
    with pytest.raises(
        Mixed64V7PostAdmissionV3Error,
        match="failure reason exceeds the byte bound",
    ):
        execute_synthetic_mixed64_v7_post_admission(
            operational,
            refiner=refiner,
        )


def test_operational_live_mutation_fails_before_any_refinement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority, receptor, ligand, operational = _fixture()
    refiner = _refiner(authority, receptor, ligand)
    target = next(value for value in operational.records if value.materialized)
    assert target.operational_proposal is not None
    target.operational_proposal.coordinates[0, 0] += 1.0
    attempts = 0

    def refine(self, proposal, *, max_steps):
        nonlocal attempts
        attempts += 1
        raise AssertionError("refinement must not start")

    monkeypatch.setattr(
        InteractionAwareTorsionContactEnsembleRefinerV7,
        "refine",
        refine,
    )
    with pytest.raises(
        Mixed64V7PostAdmissionV3Error,
        match="live integrity preflight",
    ):
        execute_synthetic_mixed64_v7_post_admission(
            operational,
            refiner=refiner,
        )
    assert attempts == 0


def test_pair_bound_is_checked_before_any_refinement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import betelgeuze_engine_v2.docking.mixed64_v7_post_admission_v3 as module

    authority, receptor, ligand, operational = _fixture()
    refiner = _refiner(authority, receptor, ligand)
    attempts = 0

    def refine(self, proposal, *, max_steps):
        nonlocal attempts
        attempts += 1
        raise AssertionError("must not run")

    monkeypatch.setattr(
        module,
        "POST_REFINEMENT_MAX_BATCH_EXACT_PAIR_EVALUATIONS",
        1,
    )
    monkeypatch.setattr(
        InteractionAwareTorsionContactEnsembleRefinerV7, "refine", refine
    )
    with pytest.raises(Mixed64V7PostAdmissionV3Error, match="pair work"):
        execute_synthetic_mixed64_v7_post_admission(
            operational,
            refiner=refiner,
        )
    assert attempts == 0


def test_crosswired_geometric_context_fails_before_any_refinement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority, receptor, ligand, operational = _fixture()
    refiner = _refiner(authority, receptor, ligand)
    refiner._receptor_coordinates[0, 0] += 1.0
    attempts = 0

    def refine(self, proposal, *, max_steps):
        nonlocal attempts
        attempts += 1
        raise AssertionError("must not run")

    monkeypatch.setattr(
        InteractionAwareTorsionContactEnsembleRefinerV7,
        "refine",
        refine,
    )
    with pytest.raises(
        Mixed64V7PostAdmissionV3Error,
        match="geometric-admission context",
    ):
        execute_synthetic_mixed64_v7_post_admission(
            operational,
            refiner=refiner,
        )
    assert attempts == 0


def test_wrong_v7_profile_source_or_preexisting_receipt_fails_closed() -> None:
    authority, receptor, ligand, operational = _fixture()
    with pytest.raises(Mixed64V7PostAdmissionV3Error, match="slot profile"):
        execute_synthetic_mixed64_v7_post_admission(
            operational,
            refiner=_refiner(authority, receptor, ligand, indices=(24,)),
        )

    wrong_source = InteractionAwareTorsionContactEnsembleRefinerV7(
        authority,
        receptor,
        ligand,
        implementation_source_sha256="b" * 64,
        v3_proposal_indices=V7_TORSION_ELIGIBLE_SLOT_INDICES,
    )
    with pytest.raises(Mixed64V7PostAdmissionV3Error, match="source identity"):
        execute_synthetic_mixed64_v7_post_admission(
            operational,
            refiner=wrong_source,
        )


def test_record_factory_policy_signature_and_authority_are_frozen() -> None:
    authority, receptor, ligand, operational = _fixture()
    with pytest.raises(Mixed64V7PostAdmissionV3Error, match="bounded factory"):
        Mixed64V7PostAdmissionRecordV1(
            materialization_record=operational.records[0],
            result_proposal=None,
            refinement_receipt=None,
            post_refinement_metrics=None,
            status=UPSTREAM_NOT_REFINED_STATUS,
            failure_code=None,
            failure_reason=None,
            rejection_code=None,
        )
    policy = frozen_mixed64_v7_post_admission_policy()
    assert len(MIXED64_V7_POST_ADMISSION_POLICY_SHA256) == 64
    assert policy["refinement"]["max_steps"] == V7_REFINEMENT_MAX_STEPS == 24
    assert policy["refinement"]["torsion_eligible_slot_indices"] == list(range(24, 44))
    assert policy["failure_semantics"]["unexpected_runtime_failure_typed"] is False
    assert all(value is False for value in policy["authority"].values())
    parameters = set(
        inspect.signature(execute_synthetic_mixed64_v7_post_admission).parameters
    )
    assert parameters == {"operational_batch", "refiner"}
    assert not parameters & {
        "coordinates",
        "max_steps",
        "score",
        "validity",
        "rank",
        "reservation",
        "authority",
    }


def test_implementation_source_snapshot_rejects_symlink(tmp_path: Path) -> None:
    target = tmp_path / "refiner.py"
    target.write_text("pass\n", encoding="ascii")
    link = tmp_path / "refiner-link.py"
    link.symlink_to(target)
    with pytest.raises(
        Mixed64V7PostAdmissionV3Error,
        match="source is unavailable",
    ):
        v7_module._stable_source_sha256(link)


def test_implementation_source_snapshot_enforces_byte_bound(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "refiner.py"
    source.write_bytes(b"12345")
    monkeypatch.setattr(v7_module, "MAX_V7_IMPLEMENTATION_SOURCE_BYTES", 4)
    with pytest.raises(
        Mixed64V7PostAdmissionV3Error,
        match="source is unavailable",
    ):
        v7_module._stable_source_sha256(source)
