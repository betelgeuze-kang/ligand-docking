from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest

from betelgeuze_engine_v2.benchmark.global_orientation_development_contracts import (
    GLOBAL_ORIENTATION_DEVELOPMENT_CANDIDATE_DENOMINATOR,
    GlobalOrientationDevelopmentArmLineageReceiptV1,
    GlobalOrientationDevelopmentArmObservationsV1,
    GlobalOrientationDevelopmentCaseSourceReceiptV1,
    GlobalOrientationDevelopmentContractError,
    GlobalOrientationDevelopmentLineageSlotV1,
    GlobalOrientationDevelopmentObservationSlotV1,
    GlobalOrientationDevelopmentPreparationFailureReceiptV1,
    derive_global_orientation_generator_runtime_fingerprint,
    derive_global_orientation_pose_validity_config_fingerprint,
    derive_global_orientation_source_coordinates_sha256,
)
from betelgeuze_engine_v2.benchmark.source_paired_clearance_activation import (
    INTERNAL_VALIDITY_REQUIRED_CHECK_NAMES,
    POSEBUSTERS_REQUIRED_CHECK_NAMES,
    SourcePairedClearanceCandidateEvidenceV1,
    SourcePairedClearanceInternalValidityEvidenceV1,
    SourcePairedClearancePoseBustersEvidenceV1,
    SourcePairedClearanceRmsdEvidenceV1,
)
from betelgeuze_engine_v2.docking import (
    PoseValidityConfig,
    PoseValidityResult,
    ScorerV1Terms,
)


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode("ascii")).hexdigest()


def _source() -> GlobalOrientationDevelopmentCaseSourceReceiptV1:
    receptor = ((0.0, 0.0, 0.0), (1.0, 2.0, 3.0), (4.0, 5.0, 6.0))
    ligand = ((0.0, 0.0, 0.0), (0.5, 0.0, 0.0))
    python = _digest("python")
    shared = _digest("libpython")
    libm = _digest("libm")
    radius = 10.0
    return GlobalOrientationDevelopmentCaseSourceReceiptV1(
        case_id="5SD5_HWI",
        source_case_member_receipt_sha256=_digest("archive-member"),
        authenticated_input_receipt_sha256=_digest("authenticated-input"),
        receptor_coordinates=receptor,
        receptor_coordinate_sha256=(
            derive_global_orientation_source_coordinates_sha256(receptor)
        ),
        ligand_coordinates=ligand,
        ligand_coordinate_sha256=(
            derive_global_orientation_source_coordinates_sha256(ligand)
        ),
        ligand_topology_sha256=_digest("ligand-topology"),
        pocket_declaration_sha256=_digest("pocket"),
        pocket_center=(1.0, 1.0, 1.0),
        pocket_normal=(0.0, 0.0, 1.0),
        pocket_radius_angstrom=radius,
        pose_validity_config_fingerprint_sha256=(
            derive_global_orientation_pose_validity_config_fingerprint(radius)
        ),
        preparation_policy_sha256=_digest("preparation"),
        evaluation_pipeline_sha256=_digest("evaluation-pipeline"),
        scorer_native_extension_sha256=_digest("native-extension"),
        scorer_backend_receipt_sha256=_digest("backend-receipt"),
        generator_python_executable_sha256=python,
        generator_python_shared_library_sha256=shared,
        generator_libm_sha256=libm,
        generator_runtime_fingerprint_sha256=(
            derive_global_orientation_generator_runtime_fingerprint(
                python_executable_sha256=python,
                python_shared_library_sha256=shared,
                libm_sha256=libm,
            )
        ),
        receptor_surface_atom_indices=(0, 2),
    )


def _lineage(
    source: GlobalOrientationDevelopmentCaseSourceReceiptV1,
    *,
    arm_id: str = "experimental_global_orientation_v1",
) -> GlobalOrientationDevelopmentArmLineageReceiptV1:
    slots = tuple(
        GlobalOrientationDevelopmentLineageSlotV1(
            case_source_receipt_sha256=source.receipt_sha256,
            arm_id=arm_id,
            proposal_index=index,
            candidate_id=f"{source.case_id}:{arm_id}:{index:02d}",
            generation_status="failed" if index == 7 else "generated",
            proposal_fingerprint_sha256=(
                None if index == 7 else _digest(f"proposal-{arm_id}-{index}")
            ),
            coordinate_sha256=(
                None if index == 7 else _digest(f"coordinate-{arm_id}-{index}")
            ),
            generation_receipt_sha256=(
                None if index == 7 else _digest(f"generation-{arm_id}-{index}")
            ),
            failure_code="receptor_clash" if index == 7 else None,
        )
        for index in range(GLOBAL_ORIENTATION_DEVELOPMENT_CANDIDATE_DENOMINATOR)
    )
    return GlobalOrientationDevelopmentArmLineageReceiptV1(
        case_source=source,
        arm_id=arm_id,
        arm_authority_sha256=_digest(f"authority-{arm_id}"),
        slots=slots,
    )


def _candidate_evidence(
    slot: GlobalOrientationDevelopmentLineageSlotV1,
) -> SourcePairedClearanceCandidateEvidenceV1:
    assert slot.proposal_fingerprint_sha256 is not None
    assert slot.coordinate_sha256 is not None
    proposal = slot.proposal_fingerprint_sha256
    coordinate = slot.coordinate_sha256
    pose = _digest(f"pose-{slot.candidate_id}")
    report = _digest(f"report-{slot.candidate_id}")
    native_pose = _digest("native-pose")
    receptor = _digest("receptor-artifact")
    score = -float(slot.proposal_index)
    scorer_terms = ScorerV1Terms(
        proposal_fingerprint_sha256=proposal,
        authority_input_receipt_sha256=_digest("scorer-authority"),
        context_fingerprint_sha256=_digest("scorer-context"),
        config_fingerprint_sha256=_digest("scorer-config"),
        backend_receipt_sha256=_digest("scorer-backend"),
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
        authority_input_receipt_sha256=_digest("validity-authority"),
        problem_fingerprint_sha256=_digest("problem"),
        context_fingerprint_sha256=_digest("validity-context"),
        config_fingerprint_sha256=_digest("validity-config"),
        evaluator_implementation_sha256=_digest("validity-implementation"),
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
        implementation_sha256=_digest("posebusters-implementation"),
        config_sha256=_digest("posebusters-config"),
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
        atom_mapping_sha256=_digest("atom-mapping"),
        symmetry_policy_sha256=_digest("symmetry-policy"),
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
        raw_score_rank=slot.proposal_index + 1,
    )


def _observation(
    slot: GlobalOrientationDevelopmentLineageSlotV1,
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
        candidate_evidence=None if failed else _candidate_evidence(slot),
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


def test_case_source_rejects_crosswired_radius_runtime_and_surface() -> None:
    source = _source()

    with pytest.raises(
        GlobalOrientationDevelopmentContractError,
        match="pose-validity config identity",
    ):
        replace(source, pocket_radius_angstrom=11.0)
    with pytest.raises(
        GlobalOrientationDevelopmentContractError,
        match="generator runtime identity",
    ):
        replace(source, generator_libm_sha256=_digest("other-libm"))
    with pytest.raises(
        GlobalOrientationDevelopmentContractError,
        match="surface indices",
    ):
        replace(source, receptor_surface_atom_indices=(2, 0))


def test_preparation_failure_retains_ninth_case_without_candidate_rows() -> None:
    receipt = GlobalOrientationDevelopmentPreparationFailureReceiptV1(
        case_id="6M73_FNR",
        source_case_member_receipt_sha256=_digest("failure-archive"),
        authenticated_input_receipt_sha256=_digest("failure-input"),
        preparation_policy_sha256=_digest("failure-policy"),
        failure_code="ligand_preparation_failed",
    )

    assert receipt.to_dict()["candidate_denominator"] == 0
    assert receipt.to_dict()["preparation_status"] == "failed"
    assert receipt.to_dict()["stage0_admission_authority"] is False


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
    assert document["generated_candidate_count"] == 63
    assert document["scored_candidate_count"] == 63
    assert document["unscored_candidate_count"] == 1
    assert document["failure_complete_observation_denominator"] is True
    assert document["observations"][0]["candidate_evidence"]["scorer_v1_terms"]
    assert document["observations"][7]["candidate_evidence"] is None
    assert document["observations"][7]["explicit_unscored_state"] is True
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
    failed = lineage.slots[7]

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
