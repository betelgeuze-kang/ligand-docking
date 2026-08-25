from __future__ import annotations

# Torch is optional for collection; engine imports intentionally follow this guard.
# ruff: noqa: E402

from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest

torch = pytest.importorskip("torch")

from betelgeuze_engine_v2 import (  # noqa: E402
    AllAtomSystem,
    Atom,
    Bond,
    Chain,
    Residue,
    StructureProvenance,
    canonical_topology_sha256,
)
from betelgeuze_engine_v2.benchmark.global_orientation_development_contracts import (
    GLOBAL_ORIENTATION_DEVELOPMENT_CANDIDATE_DENOMINATOR,
    GlobalOrientationDevelopmentArmLineageReceiptV1,
    GlobalOrientationDevelopmentArmObservationsV1,
    GlobalOrientationDevelopmentCaseSourceReceiptV1,
    GlobalOrientationDevelopmentContractError,
    GlobalOrientationDevelopmentHistoricalFailureAuthorityV1,
    GlobalOrientationDevelopmentLineageSlotV1,
    GlobalOrientationDevelopmentObservationSlotV1,
    GlobalOrientationDevelopmentPartialCandidateEvidenceV1,
    GlobalOrientationDevelopmentPreparationFailureReceiptV1,
    derive_global_orientation_generator_source_receipt_sha256,
    derive_global_orientation_pose_validity_config_fingerprint,
    derive_global_orientation_pocket_declaration_sha256,
    derive_global_orientation_source_coordinates_sha256,
    materialize_global_orientation_docking_proposals,
)
from betelgeuze_engine_v2.benchmark.source_paired_clearance_activation import (
    INTERNAL_VALIDITY_REQUIRED_CHECK_NAMES,
    POSEBUSTERS_REQUIRED_CHECK_NAMES,
    SourcePairedClearanceCandidateEvidenceV1,
    SourcePairedClearanceCaseSourceReceiptV1,
    SourcePairedClearanceInternalValidityEvidenceV1,
    SourcePairedClearancePoseBustersEvidenceV1,
    SourcePairedClearanceRmsdEvidenceV1,
)
from betelgeuze_engine_v2.docking import (
    DockingScope,
    PocketDefinition,
    PoseValidityConfig,
    PoseValidityResult,
    ScorerBackend,
    ScorerBackendOptions,
    ScorerBackendReceipt,
    ScorerV1Terms,
    build_element_aware_authenticated_known_pocket_docking_problem,
    derive_scorer_v1_context,
)
from betelgeuze_engine_v2.docking.global_orientation import (
    GlobalOrientationConfig,
    generate_global_orientation_batch,
)
from betelgeuze_engine_v2.benchmark.global_orientation_development_contracts import (
    GLOBAL_ORIENTATION_EXPECTED_EVALUATION_PIPELINE_SHA256,
    GLOBAL_ORIENTATION_INTERNAL_VALIDITY_IMPLEMENTATION_SHA256,
    GLOBAL_ORIENTATION_POSEBUSTERS_CONFIG_SHA256,
    GLOBAL_ORIENTATION_POSEBUSTERS_IMPLEMENTATION_SHA256,
    GLOBAL_ORIENTATION_RMSD_ATOM_MAPPING_SHA256,
    GLOBAL_ORIENTATION_RMSD_SYMMETRY_POLICY_SHA256,
    GLOBAL_ORIENTATION_SCORER_CONFIG_SHA256,
)


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode("ascii")).hexdigest()


def _system(*, receptor: bool) -> AllAtomSystem:
    if receptor:
        elements = ("C", "C", "C")
        coordinates = (((1.0, 4.0, 0.0), (4.0, 4.0, 0.0), (7.0, 0.0, 0.0)),)
        bonds = ()
        name = "REC"
    else:
        elements = ("C", "N", "C", "O")
        coordinates = (
            ((0.0, 0.0, 0.0), (1.4, 0.0, 0.0), (2.8, 0.3, 0.0), (4.1, 1.0, 0.2)),
        )
        bonds = (
            Bond(index=0, atom_i=0, atom_j=1, order=1.0),
            Bond(index=1, atom_i=1, atom_j=2, order=1.0),
            Bond(index=2, atom_i=2, atom_j=3, order=1.0),
        )
        name = "LIG"
    atoms = tuple(
        Atom(
            index=index,
            name=f"A{index}",
            element=element,
            atomic_number={"C": 6, "N": 7, "O": 8}[element],
            residue_index=0,
            partial_charge_e=0.0,
        )
        for index, element in enumerate(elements)
    )
    return AllAtomSystem(
        system_id=f"orientation-{name.lower()}",
        atoms=atoms,
        bonds=bonds,
        residues=(
            Residue(
                index=0,
                name=name,
                chain_index=0,
                sequence_number=1,
                atom_indices=tuple(range(len(atoms))),
            ),
        ),
        chains=(Chain(index=0, chain_id="A", residue_indices=(0,)),),
        coordinates=torch.tensor(coordinates, dtype=torch.float64),
        provenance=StructureProvenance(
            source_format="unit",
            source_id=f"orientation-{name.lower()}-source",
            source_sha256=_digest(f"{name}-source"),
            parser_name="orientation-contract-fixture",
            parser_version="1.0.0",
        ),
    )


def _source() -> GlobalOrientationDevelopmentCaseSourceReceiptV1:
    receptor_system = _system(receptor=True)
    ligand_system = _system(receptor=False)
    center = (2.5, 0.5, 0.0)
    normal = (0.0, 0.0, 1.0)
    radius = 10.0
    authenticated = build_element_aware_authenticated_known_pocket_docking_problem(
        receptor_system,
        ligand_system,
        PocketDefinition(
            scope=DockingScope.KNOWN_POCKET,
            method_id="manual-reviewed-sphere",
            method_version="1.0.0",
            coordinate_frame_id="prepared-receptor-frame-v1",
            center=torch.tensor(center, dtype=torch.float64),
            radius_angstrom=radius,
            source_artifact_sha256=_digest("pocket-source"),
            implementation_source_sha256=_digest("pocket-implementation"),
        ),
    )
    receptor = tuple(tuple(row) for row in receptor_system.coordinates[0].tolist())
    ligand = tuple(tuple(row) for row in ligand_system.coordinates[0].tolist())
    historical = SourcePairedClearanceCaseSourceReceiptV1(
        case_id="5SD5_HWI",
        source_case_member_path=(
            ".betelgeuze/stage0-development/v7-clearance-v11-6a749540-rescue-nine/receipts/engine_v2/5SD5_HWI.json"
        ),
        source_case_member_sha256=(
            "231b3267c8a77983383a54dac2ab255d839347025ac705868c275a78c45a2b60"
        ),
        source_case_member_receipt_sha256=(
            "367131fa76af6c1a3c579176c621f72631fe859464d8883218da0ebab6f16bfe"
        ),
        authenticated_input_receipt_sha256=(
            "129286d9f9bf96ba482b6744197b330a6dd489033e3533f9f9542b2c3e39f730"
        ),
        problem_fingerprint_sha256=authenticated.problem.fingerprint_sha256,
        source_proposal_receipt_sha256=(
            "f2a100e35c8951f5ce954a963091ee04cf6d86eb15d6c47e8cc1e8a2d6ab67ba"
        ),
        allocation_receipt_sha256=(
            "44fdb41049d49b6ea5198f39e94772ad62065b1ba47e3c0191e00e535aa10f64"
        ),
        native_pose_artifact_sha256=(
            "5cb7355e18c0af38af55ab49824e34c8f97540ab0a6866d97dbc45c1dfc59fb3"
        ),
        receptor_artifact_sha256=(
            "30a1ca38d5f047209fc65752e9a7e4a643d929be7f8d5c06eae303371e266ac6"
        ),
        input_artifact_set_sha256=(
            "4e52f80c435c05f690d23beece4b035eb3688cf1de9c60d57e46268d77cdaf74"
        ),
        current_v7_candidate_lineage_sha256=(
            "0133959300cee30971f55e3b3a7b043f06008d58e0abd38346c6972a4c038b52"
        ),
    )
    object.__setattr__(
        historical,
        "authenticated_input_receipt_sha256",
        authenticated.input_receipt_sha256,
    )
    object.__setattr__(
        historical,
        "_receipt_sha256",
        hashlib.sha256(
            json.dumps(
                historical._projection(),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
                allow_nan=False,
            ).encode("ascii")
        ).hexdigest(),
    )
    scorer_context = derive_scorer_v1_context(
        authenticated,
        receptor_system,
        ligand_system,
    )
    native_extension = _digest("native-extension")
    backend_options = ScorerBackendOptions(thread_count=1, max_batch_size=64)
    backend_receipt = ScorerBackendReceipt(
        backend=ScorerBackend.RUST_CPU_REQUIRED,
        backend_version="unit-native-v1",
        implementation_source_sha256=(
            "138484e4e3f5473c582485316ed8482fc770d0df2aa9f8397e4c91be22d81b75"
        ),
        options_fingerprint_sha256=backend_options.fingerprint_sha256,
        extension_sha256=native_extension,
        cargo_lock_sha256=_digest("cargo-lock"),
        rustc_version="rustc unit",
        target_triple="unit-target",
    )
    return GlobalOrientationDevelopmentCaseSourceReceiptV1(
        case_id="5SD5_HWI",
        historical_case_source=historical,
        authenticated_problem=authenticated,
        receptor_system=receptor_system,
        ligand_system=ligand_system,
        scorer_context=scorer_context,
        source_case_member_receipt_sha256=(
            historical.source_case_member_receipt_sha256
        ),
        authenticated_input_receipt_sha256=(
            historical.authenticated_input_receipt_sha256
        ),
        receptor_coordinates=receptor,
        receptor_coordinate_sha256=(
            derive_global_orientation_source_coordinates_sha256(receptor)
        ),
        ligand_coordinates=ligand,
        ligand_coordinate_sha256=(
            derive_global_orientation_source_coordinates_sha256(ligand)
        ),
        ligand_topology_sha256=canonical_topology_sha256(ligand_system),
        pocket_declaration_sha256=derive_global_orientation_pocket_declaration_sha256(
            case_id=historical.case_id,
            historical_case_source_receipt_sha256=historical.receipt_sha256,
            pocket_center=center,
            pocket_normal=normal,
            pocket_radius_angstrom=radius,
        ),
        pocket_center=center,
        pocket_normal=normal,
        pocket_radius_angstrom=radius,
        pose_validity_config_fingerprint_sha256=(
            derive_global_orientation_pose_validity_config_fingerprint(radius)
        ),
        preparation_policy_sha256=authenticated.authority_policy_sha256,
        evaluation_pipeline_sha256=(
            GLOBAL_ORIENTATION_EXPECTED_EVALUATION_PIPELINE_SHA256
        ),
        scorer_backend_receipt=backend_receipt,
        scorer_native_extension_sha256=native_extension,
        scorer_backend_receipt_sha256=backend_receipt.receipt_sha256,
        receptor_surface_atom_indices=authenticated.receptor_atom_indices,
    )


def _lineage(
    source: GlobalOrientationDevelopmentCaseSourceReceiptV1,
    *,
    arm_id: str = "experimental_global_orientation_v1",
    profile_id: str = "deterministic_surface_aware_rigid_v2",
) -> GlobalOrientationDevelopmentArmLineageReceiptV1:
    if arm_id != "experimental_global_orientation_v1":
        raise AssertionError("test helper currently constructs the experimental arm")
    batch = generate_global_orientation_batch(
        source.ligand_coordinates,
        pocket_center=source.pocket_center,
        pocket_normal=source.pocket_normal,
        receptor_surface_points=source.receptor_surface_points,
        config=GlobalOrientationConfig(
            orientation_count=8,
            translation_shell_radii=(1.5,),
            translation_points_per_shell=7,
            minimum_receptor_distance=1.1,
        ),
        source_receipt_sha256=source.generator_source_receipt_sha256,
        profile_id=profile_id,
    )
    return _lineage_from_batch(source, batch)


def _lineage_from_batch(
    source: GlobalOrientationDevelopmentCaseSourceReceiptV1,
    batch,
) -> GlobalOrientationDevelopmentArmLineageReceiptV1:
    arm_id = "experimental_global_orientation_v1"
    proposals = materialize_global_orientation_docking_proposals(source, batch)
    slots = tuple(
        GlobalOrientationDevelopmentLineageSlotV1(
            case_source_receipt_sha256=source.receipt_sha256,
            arm_id=arm_id,
            proposal_index=index,
            candidate_id=(
                proposals[index].candidate_id
                if proposals[index] is not None
                else f"{source.case_id}:{arm_id}:{index:02d}"
            ),
            generation_status="generated" if batch.slots[index].accepted else "failed",
            proposal_fingerprint_sha256=(
                proposals[index].fingerprint_sha256
                if proposals[index] is not None
                else None
            ),
            coordinate_sha256=(
                proposals[index].coordinate_fingerprint_sha256
                if proposals[index] is not None
                else None
            ),
            generation_receipt_sha256=(
                batch.slots[index].receipt_sha256
                if batch.slots[index].accepted
                else None
            ),
            failure_code=(
                None
                if batch.slots[index].accepted
                else batch.slots[index].rejection_code
            ),
        )
        for index in range(GLOBAL_ORIENTATION_DEVELOPMENT_CANDIDATE_DENOMINATOR)
    )
    return GlobalOrientationDevelopmentArmLineageReceiptV1(
        case_source=source,
        arm_id=arm_id,
        arm_authority_sha256=batch.receipt_sha256,
        arm_authority_receipt=batch,
        slots=slots,
    )


def _candidate_evidence(
    slot: GlobalOrientationDevelopmentLineageSlotV1,
    source: GlobalOrientationDevelopmentCaseSourceReceiptV1 | None = None,
    raw_rank: int | None = None,
) -> SourcePairedClearanceCandidateEvidenceV1:
    source = _source() if source is None else source
    if raw_rank is None:
        raw_rank = 1 + sum(
            value.generation_status == "generated"
            for value in _lineage(source).slots[: slot.proposal_index]
        )
    assert slot.proposal_fingerprint_sha256 is not None
    assert slot.coordinate_sha256 is not None
    proposal = slot.proposal_fingerprint_sha256
    coordinate = slot.coordinate_sha256
    pose = _digest(f"pose-{slot.candidate_id}")
    report = _digest(f"report-{slot.candidate_id}")
    native_pose = source.historical_case_source.native_pose_artifact_sha256
    receptor = source.historical_case_source.receptor_artifact_sha256
    score = float(slot.proposal_index)
    scorer_terms = ScorerV1Terms(
        proposal_fingerprint_sha256=proposal,
        authority_input_receipt_sha256=(
            source.historical_case_source.authenticated_input_receipt_sha256
        ),
        context_fingerprint_sha256=source.scorer_context.fingerprint_sha256,
        config_fingerprint_sha256=GLOBAL_ORIENTATION_SCORER_CONFIG_SHA256,
        backend_receipt_sha256=source.scorer_backend_receipt_sha256,
        typed_vdw=score,
        electrostatics=0.0,
        directional_hbond=0.0,
        hydrophobic_contact=0.0,
        desolvation_proxy=0.0,
        torsion_energy=0.0,
        ligand_strain=0.0,
        weak_pocket_prior=0.0,
        total_score=score,
        receptor_candidate_pair_count=10,
        ligand_pair_count=2,
        hbond_count=1,
        hydrophobic_contact_count=1,
        buried_polar_count=0,
    )
    checks = {name: True for name in INTERNAL_VALIDITY_REQUIRED_CHECK_NAMES}
    internal = SourcePairedClearanceInternalValidityEvidenceV1(
        proposal_fingerprint_sha256=proposal,
        coordinate_sha256=coordinate,
        pose_artifact_sha256=pose,
        authority_input_receipt_sha256=(
            source.historical_case_source.authenticated_input_receipt_sha256
        ),
        problem_fingerprint_sha256=(
            source.historical_case_source.problem_fingerprint_sha256
        ),
        context_fingerprint_sha256=(
            source.authenticated_problem.validity_context.fingerprint_sha256
        ),
        config_fingerprint_sha256=(source.pose_validity_config_fingerprint_sha256),
        evaluator_implementation_sha256=(
            GLOBAL_ORIENTATION_INTERNAL_VALIDITY_IMPLEMENTATION_SHA256
        ),
        result=PoseValidityResult(
            checks=checks,
            evaluated_checks={name: True for name in checks},
            complete=True,
            valid_within_evaluated_scope=True,
            measurements={"minimum_receptor_ligand_distance_angstrom": 2.5},
            blockers=(),
            not_evaluated_reasons={},
        ),
    )
    posebusters = SourcePairedClearancePoseBustersEvidenceV1(
        implementation_sha256=GLOBAL_ORIENTATION_POSEBUSTERS_IMPLEMENTATION_SHA256,
        config_sha256=GLOBAL_ORIENTATION_POSEBUSTERS_CONFIG_SHA256,
        proposal_fingerprint_sha256=proposal,
        coordinate_sha256=coordinate,
        pose_artifact_sha256=pose,
        native_pose_artifact_sha256=native_pose,
        receptor_artifact_sha256=receptor,
        report_artifact_sha256=report,
        check_results={name: True for name in POSEBUSTERS_REQUIRED_CHECK_NAMES},
    )
    rmsd = SourcePairedClearanceRmsdEvidenceV1(
        implementation_sha256=posebusters.implementation_sha256,
        config_sha256=posebusters.config_sha256,
        proposal_fingerprint_sha256=proposal,
        coordinate_sha256=coordinate,
        pose_artifact_sha256=pose,
        native_pose_artifact_sha256=native_pose,
        receptor_artifact_sha256=receptor,
        atom_mapping_sha256=GLOBAL_ORIENTATION_RMSD_ATOM_MAPPING_SHA256,
        symmetry_policy_sha256=GLOBAL_ORIENTATION_RMSD_SYMMETRY_POLICY_SHA256,
        report_artifact_sha256=report,
        rmsd_angstrom=float(slot.proposal_index) / 10.0,
    )
    return SourcePairedClearanceCandidateEvidenceV1(
        candidate_id=slot.candidate_id,
        proposal_index=slot.proposal_index,
        candidate_proposal_fingerprint_sha256=proposal,
        source_proposal_fingerprint_sha256=proposal,
        coordinate_sha256=coordinate,
        pose_artifact_sha256=pose,
        scorer_terms=scorer_terms,
        internal_validity=internal,
        posebusters=posebusters,
        rmsd=rmsd,
        raw_score_rank=raw_rank,
    )


def _observation(
    slot: GlobalOrientationDevelopmentLineageSlotV1,
    source: GlobalOrientationDevelopmentCaseSourceReceiptV1 | None = None,
) -> GlobalOrientationDevelopmentObservationSlotV1:
    failed = slot.generation_status == "failed"
    return GlobalOrientationDevelopmentObservationSlotV1(
        lineage_slot_receipt_sha256=slot.receipt_sha256,
        case_source_receipt_sha256=slot.case_source_receipt_sha256,
        arm_id=slot.arm_id,
        proposal_index=slot.proposal_index,
        candidate_id=slot.candidate_id,
        generation_status=slot.generation_status,
        proposal_fingerprint_sha256=slot.proposal_fingerprint_sha256,
        coordinate_sha256=slot.coordinate_sha256,
        score_status="unscored" if failed else "scored",
        validity_status="not_evaluated" if failed else "evaluated",
        rmsd_status="not_evaluated" if failed else "evaluated",
        candidate_evidence=None if failed else _candidate_evidence(slot, source),
        failure_code=slot.failure_code,
    )


def test_case_source_rederives_coordinates_surface_validity_and_runtime() -> None:
    source = _source()
    protocol = json.loads(
        Path(
            "config/engine_v2_global_orientation_contaminated_development.json"
        ).read_text(encoding="utf-8")
    )
    bindings = protocol["source_bindings"]

    assert source.receptor_surface_points == (
        source.receptor_coordinates[0],
        source.receptor_coordinates[1],
        source.receptor_coordinates[2],
    )
    assert source.schema_id == bindings["case_source_receipt_schema_id"]
    assert set(bindings["source_receipt_required_fields"]) <= set(source.to_dict())
    assert source.to_dict()["receptor_surface_points_rederived"] is True
    assert source.to_dict()["historical_development_execution_authorized"] is False
    expected = PoseValidityConfig(
        policy_id=("betelgeuze.engine_v2_pose_validity_policy/public-redocking/1.0.0"),
        pocket_radius_angstrom=10.0,
    ).fingerprint_sha256
    assert source.pose_validity_config_fingerprint_sha256 == expected


def test_case_source_rejects_crosswired_radius_chemistry_and_surface() -> None:
    source = _source()

    with pytest.raises(
        GlobalOrientationDevelopmentContractError,
        match="pocket geometry",
    ):
        replace(source, pocket_radius_angstrom=11.0)
    with pytest.raises(
        GlobalOrientationDevelopmentContractError,
        match="scorer context",
    ):
        replace(
            source,
            scorer_context=replace(
                source.scorer_context,
                ligand_partial_charges_e=(0.1, -0.1, 0.0, 0.0),
            ),
        )
    with pytest.raises(
        GlobalOrientationDevelopmentContractError,
        match="receptor surface indices",
    ):
        replace(source, receptor_surface_atom_indices=(2, 0))
    with pytest.raises(
        GlobalOrientationDevelopmentContractError,
        match="authenticated receptor subset",
    ):
        replace(source, receptor_surface_atom_indices=(0, 2))


def test_preparation_failure_retains_ninth_case_without_candidate_rows() -> None:
    receipt = GlobalOrientationDevelopmentPreparationFailureReceiptV1(
        historical_authority=(
            GlobalOrientationDevelopmentHistoricalFailureAuthorityV1()
        ),
        failure_code="unsupported_large_ring_system",
    )

    assert receipt.to_dict()["candidate_denominator"] == 0
    assert receipt.to_dict()["preparation_status"] == "failed"
    assert receipt.to_dict()["stage0_admission_authority"] is False
    with pytest.raises(
        GlobalOrientationDevelopmentContractError,
        match="pinned historical member",
    ):
        replace(
            receipt.historical_authority,
            historical_engine_receipt_sha256=_digest("fabricated-failure"),
        )
    with pytest.raises(
        GlobalOrientationDevelopmentContractError,
        match="frozen historical failure code",
    ):
        replace(receipt, failure_code="parser_failed")


def test_arm_lineage_and_observations_bind_exact_failure_complete_64_slots() -> None:
    lineage = _lineage(_source())
    evidence = GlobalOrientationDevelopmentArmObservationsV1(
        lineage=lineage,
        observations=tuple(_observation(slot) for slot in lineage.slots),
    )

    document = evidence.to_dict()
    protocol = json.loads(
        Path(
            "config/engine_v2_global_orientation_contaminated_development.json"
        ).read_text(encoding="utf-8")
    )
    bindings = protocol["source_bindings"]
    assert lineage.schema_id == bindings["arm_lineage_receipt_schema_id"]
    assert evidence.schema_id == bindings["arm_observations_receipt_schema_id"]
    assert document["candidate_denominator"] == 64
    generated_count = sum(
        slot.generation_status == "generated" for slot in lineage.slots
    )
    assert document["generated_candidate_count"] == generated_count
    assert document["scored_candidate_count"] == generated_count
    assert document["unscored_candidate_count"] == 64 - generated_count
    assert document["failure_complete_observation_denominator"] is True
    assert document["observations"][0]["candidate_evidence"]["scorer_v1_terms"]
    generated_index = next(
        slot.proposal_index
        for slot in lineage.slots
        if slot.generation_status == "generated"
    )
    generated_slot = lineage.slots[generated_index]
    docking_proposal = lineage.experimental_docking_proposals[generated_index]
    assert docking_proposal is not None
    assert (
        generated_slot.proposal_fingerprint_sha256
        == docking_proposal.fingerprint_sha256
    )
    assert (
        generated_slot.coordinate_sha256
        == docking_proposal.coordinate_fingerprint_sha256
    )
    assert (
        generated_slot.generation_receipt_sha256
        == lineage.arm_authority_receipt.slots[generated_index].receipt_sha256
    )
    assert (
        generated_slot.proposal_fingerprint_sha256
        != generated_slot.generation_receipt_sha256
    )
    assert (
        document["observations"][generated_index]["candidate_evidence"][
            "scorer_v1_terms"
        ]["proposal_fingerprint_sha256"]
        == docking_proposal.fingerprint_sha256
    )
    failed_index = next(
        slot.proposal_index
        for slot in lineage.slots
        if slot.generation_status == "failed"
    )
    assert document["observations"][failed_index]["candidate_evidence"] is None
    assert document["observations"][failed_index]["explicit_unscored_state"] is True
    assert document["decision_evaluator_implemented"] is False
    assert document["go_receipt_emission_authorized"] is False


def test_arm_lineage_rejects_short_duplicate_and_crosswired_slots() -> None:
    lineage = _lineage(_source())

    with pytest.raises(
        GlobalOrientationDevelopmentContractError,
        match="exact ordered 64-slot",
    ):
        replace(lineage, slots=lineage.slots[:-1])
    duplicate = (*lineage.slots[:-1], lineage.slots[-2])
    with pytest.raises(
        GlobalOrientationDevelopmentContractError,
        match="exact ordered 64-slot",
    ):
        replace(lineage, slots=duplicate)
    crosswired = replace(
        lineage.slots[0],
        case_source_receipt_sha256=_digest("another-case-source"),
    )
    with pytest.raises(
        GlobalOrientationDevelopmentContractError,
        match="exact ordered 64-slot",
    ):
        replace(lineage, slots=(crosswired, *lineage.slots[1:]))


def test_observations_reject_fabricated_or_crosswired_failure_states() -> None:
    lineage = _lineage(_source())
    failed = next(slot for slot in lineage.slots if slot.generation_status == "failed")

    with pytest.raises(
        GlobalOrientationDevelopmentContractError,
        match="cross-wired",
    ):
        replace(
            _observation(failed),
            candidate_evidence=_candidate_evidence(lineage.slots[0]),
        )

    observations = tuple(_observation(slot) for slot in lineage.slots)
    crosswired = replace(
        observations[0],
        lineage_slot_receipt_sha256=lineage.slots[1].receipt_sha256,
    )
    with pytest.raises(
        GlobalOrientationDevelopmentContractError,
        match="cross-wired",
    ):
        GlobalOrientationDevelopmentArmObservationsV1(
            lineage=lineage,
            observations=(crosswired, *observations[1:]),
        )


def test_generated_unscored_slot_requires_explicit_failure() -> None:
    slot = _lineage(_source()).slots[0]

    partial = GlobalOrientationDevelopmentObservationSlotV1(
        lineage_slot_receipt_sha256=slot.receipt_sha256,
        case_source_receipt_sha256=slot.case_source_receipt_sha256,
        arm_id=slot.arm_id,
        proposal_index=slot.proposal_index,
        candidate_id=slot.candidate_id,
        generation_status="generated",
        proposal_fingerprint_sha256=slot.proposal_fingerprint_sha256,
        coordinate_sha256=slot.coordinate_sha256,
        score_status="unscored",
        validity_status="not_evaluated",
        rmsd_status="not_evaluated",
        candidate_evidence=None,
        failure_code="scorer_failed",
    )

    assert partial.to_dict()["explicit_unscored_state"] is True
    with pytest.raises(
        GlobalOrientationDevelopmentContractError,
        match="success/failure state",
    ):
        replace(partial, failure_code=None)


def test_case_source_authenticates_archive_pocket_and_evaluation_authority() -> None:
    source = _source()

    with pytest.raises(
        GlobalOrientationDevelopmentContractError,
        match="authenticated historical member",
    ):
        replace(source, source_case_member_receipt_sha256=_digest("other-member"))
    with pytest.raises(
        GlobalOrientationDevelopmentContractError,
        match="pocket geometry",
    ):
        replace(source, pocket_center=(2.0, 1.0, 1.0))
    with pytest.raises(
        GlobalOrientationDevelopmentContractError,
        match="evaluation pipeline",
    ):
        replace(source, evaluation_pipeline_sha256=_digest("other-evaluator"))
    with pytest.raises(
        GlobalOrientationDevelopmentContractError,
        match="native extension identity",
    ):
        replace(
            source,
            scorer_native_extension_sha256=_digest("crosswired-extension"),
        )
    with pytest.raises(
        GlobalOrientationDevelopmentContractError,
        match="backend profile",
    ):
        wrong_backend = replace(
            source.scorer_backend_receipt,
            backend=ScorerBackend.CPP_HIP_REQUIRED,
        )
        replace(
            source,
            scorer_backend_receipt=wrong_backend,
            scorer_backend_receipt_sha256=wrong_backend.receipt_sha256,
        )
    for changed_field in (
        {"implementation_source_sha256": _digest("other-scorer-module")},
        {"options_fingerprint_sha256": _digest("other-backend-options")},
    ):
        with pytest.raises(
            GlobalOrientationDevelopmentContractError,
            match="backend profile",
        ):
            wrong_profile = replace(
                source.scorer_backend_receipt,
                **changed_field,
            )
            replace(
                source,
                scorer_backend_receipt=wrong_profile,
                scorer_backend_receipt_sha256=wrong_profile.receipt_sha256,
            )
    with pytest.raises(
        GlobalOrientationDevelopmentContractError,
        match="preparation policy",
    ):
        replace(source, preparation_policy_sha256=_digest("other-preparation"))


def test_generator_seed_uses_only_permitted_pre_result_projection() -> None:
    source = _source()
    assert source.generator_source_receipt_sha256 == (
        derive_global_orientation_generator_source_receipt_sha256(
            authenticated_input_receipt_sha256=source.authenticated_input_receipt_sha256,
            ligand_coordinate_sha256=source.ligand_coordinate_sha256,
            ligand_topology_sha256=source.ligand_topology_sha256,
            pocket_center=source.pocket_center,
            pocket_normal=source.pocket_normal,
            pocket_radius_angstrom=source.pocket_radius_angstrom,
            receptor_surface_points=source.receptor_surface_points,
        )
    )
    batch = _lineage(source).arm_authority_receipt
    assert batch.source_receipt_sha256 == source.generator_source_receipt_sha256
    assert batch.source_receipt_sha256 != source.receipt_sha256
    assert source.historical_case_source.native_pose_artifact_sha256 not in json.dumps(
        batch.to_dict(), sort_keys=True
    )


def test_arm_authority_and_slots_must_rederive_from_generator_batch() -> None:
    lineage = _lineage(_source())

    with pytest.raises(
        GlobalOrientationDevelopmentContractError,
        match="concrete generator batch",
    ):
        replace(lineage, arm_authority_sha256=_digest("fabricated-authority"))
    generated_index = next(
        slot.proposal_index
        for slot in lineage.slots
        if slot.generation_status == "generated"
    )
    fabricated = replace(
        lineage.slots[generated_index],
        coordinate_sha256=_digest("fabricated-coordinate"),
    )
    with pytest.raises(
        GlobalOrientationDevelopmentContractError,
        match="concrete generator batch",
    ):
        replace(
            lineage,
            slots=(
                *lineage.slots[:generated_index],
                fabricated,
                *lineage.slots[generated_index + 1 :],
            ),
        )
    with pytest.raises(
        GlobalOrientationDevelopmentContractError,
        match="concrete generator batch",
    ):
        _lineage(_source(), profile_id="unfrozen-profile")

    batch = lineage.arm_authority_receipt
    forged_coordinates = tuple(
        (x + 0.25, y, z)
        for x, y, z in batch.slots[generated_index].transformed_coordinates
    )
    forged_slot = replace(
        batch.slots[generated_index],
        transformed_coordinates=forged_coordinates,
    )
    forged_batch = replace(
        batch,
        slots=(
            *batch.slots[:generated_index],
            forged_slot,
            *batch.slots[generated_index + 1 :],
        ),
    )
    with pytest.raises(
        GlobalOrientationDevelopmentContractError,
        match="concrete generator batch",
    ):
        _lineage_from_batch(lineage.case_source, forged_batch)


def test_candidate_authority_and_score_ranks_are_rederived_at_arm_level() -> None:
    source = _source()
    lineage = _lineage(source)
    observations = tuple(_observation(slot, source) for slot in lineage.slots)
    generated = [
        slot.proposal_index
        for slot in lineage.slots
        if slot.generation_status == "generated"
    ]
    target = generated[1]
    evidence = observations[target].candidate_evidence
    assert evidence is not None

    wrong_terms = replace(
        evidence.scorer_terms,
        backend_receipt_sha256=_digest("crosswired-backend"),
    )
    wrong_authority = replace(
        observations[target],
        candidate_evidence=replace(evidence, scorer_terms=wrong_terms),
    )
    with pytest.raises(
        GlobalOrientationDevelopmentContractError,
        match="case/scorer authority",
    ):
        GlobalOrientationDevelopmentArmObservationsV1(
            lineage=lineage,
            observations=(
                *observations[:target],
                wrong_authority,
                *observations[target + 1 :],
            ),
        )

    wrong_validity = replace(
        evidence.internal_validity,
        context_fingerprint_sha256=_digest("crosswired-validity-context"),
    )
    wrong_validity_context = replace(
        observations[target],
        candidate_evidence=replace(evidence, internal_validity=wrong_validity),
    )
    with pytest.raises(
        GlobalOrientationDevelopmentContractError,
        match="internal-validity evidence",
    ):
        GlobalOrientationDevelopmentArmObservationsV1(
            lineage=lineage,
            observations=(
                *observations[:target],
                wrong_validity_context,
                *observations[target + 1 :],
            ),
        )

    wrong_context_terms = replace(
        evidence.scorer_terms,
        context_fingerprint_sha256=_digest("crosswired-context"),
    )
    wrong_context = replace(
        observations[target],
        candidate_evidence=replace(evidence, scorer_terms=wrong_context_terms),
    )
    with pytest.raises(
        GlobalOrientationDevelopmentContractError,
        match="case/scorer authority",
    ):
        GlobalOrientationDevelopmentArmObservationsV1(
            lineage=lineage,
            observations=(
                *observations[:target],
                wrong_context,
                *observations[target + 1 :],
            ),
        )

    wrong_rank = replace(
        observations[target],
        candidate_evidence=replace(evidence, raw_score_rank=1),
    )
    with pytest.raises(
        GlobalOrientationDevelopmentContractError,
        match="score ranks",
    ):
        GlobalOrientationDevelopmentArmObservationsV1(
            lineage=lineage,
            observations=(
                *observations[:target],
                wrong_rank,
                *observations[target + 1 :],
            ),
        )


def test_partial_evidence_preserves_score_when_later_evaluation_fails() -> None:
    source = _source()
    lineage = _lineage(source)
    observations = tuple(_observation(slot, source) for slot in lineage.slots)
    target = next(
        slot.proposal_index
        for slot in lineage.slots
        if slot.generation_status == "generated"
    )
    complete = observations[target].candidate_evidence
    assert complete is not None
    partial_evidence = GlobalOrientationDevelopmentPartialCandidateEvidenceV1(
        candidate_id=complete.candidate_id,
        proposal_index=complete.proposal_index,
        proposal_fingerprint_sha256=(complete.candidate_proposal_fingerprint_sha256),
        coordinate_sha256=complete.coordinate_sha256,
        scorer_terms=complete.scorer_terms,
        internal_validity=None,
        posebusters=None,
        rmsd=None,
        raw_score_rank=complete.raw_score_rank,
    )
    partial_observation = replace(
        observations[target],
        candidate_evidence=None,
        partial_evidence=partial_evidence,
        score_status="scored",
        validity_status="not_evaluated",
        rmsd_status="not_evaluated",
        failure_code="validity_evaluator_failed",
    )
    receipt = GlobalOrientationDevelopmentArmObservationsV1(
        lineage=lineage,
        observations=(
            *observations[:target],
            partial_observation,
            *observations[target + 1 :],
        ),
    )

    row = receipt.to_dict()["observations"][target]
    assert row["score_status"] == "scored"
    assert row["score_binary64_hex"] == complete.scorer_terms.total_score.hex()
    assert row["partial_evidence"]["scorer_terms"]
    assert row["candidate_evidence"] is None


def test_partial_evidence_requires_one_pose_and_stops_before_rmsd() -> None:
    source = _source()
    lineage = _lineage(source)
    slot = next(
        value for value in lineage.slots if value.generation_status == "generated"
    )
    complete = _candidate_evidence(slot, source)

    with pytest.raises(
        GlobalOrientationDevelopmentContractError,
        match="one pose artifact",
    ):
        GlobalOrientationDevelopmentPartialCandidateEvidenceV1(
            candidate_id=complete.candidate_id,
            proposal_index=complete.proposal_index,
            proposal_fingerprint_sha256=(
                complete.candidate_proposal_fingerprint_sha256
            ),
            coordinate_sha256=complete.coordinate_sha256,
            scorer_terms=complete.scorer_terms,
            internal_validity=replace(
                complete.internal_validity,
                pose_artifact_sha256=_digest("other-pose"),
            ),
            posebusters=complete.posebusters,
            rmsd=None,
            raw_score_rank=complete.raw_score_rank,
        )
    with pytest.raises(
        GlobalOrientationDevelopmentContractError,
        match="full candidate evidence",
    ):
        GlobalOrientationDevelopmentPartialCandidateEvidenceV1(
            candidate_id=complete.candidate_id,
            proposal_index=complete.proposal_index,
            proposal_fingerprint_sha256=(
                complete.candidate_proposal_fingerprint_sha256
            ),
            coordinate_sha256=complete.coordinate_sha256,
            scorer_terms=complete.scorer_terms,
            internal_validity=complete.internal_validity,
            posebusters=complete.posebusters,
            rmsd=complete.rmsd,
            raw_score_rank=complete.raw_score_rank,
        )


def test_case_source_coordinates_and_topology_match_authenticated_systems() -> None:
    source = _source()
    changed_receptor = (
        (99.0, 99.0, 99.0),
        *source.receptor_coordinates[1:],
    )
    with pytest.raises(
        GlobalOrientationDevelopmentContractError,
        match="retained coordinates",
    ):
        replace(
            source,
            receptor_coordinates=changed_receptor,
            receptor_coordinate_sha256=(
                derive_global_orientation_source_coordinates_sha256(changed_receptor)
            ),
        )
    with pytest.raises(
        GlobalOrientationDevelopmentContractError,
        match="ligand topology",
    ):
        replace(source, ligand_topology_sha256=_digest("other-topology"))
