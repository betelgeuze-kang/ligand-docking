from __future__ import annotations

from dataclasses import fields, replace
import hashlib
import json
from pathlib import Path
import runpy

import pytest

import betelgeuze_engine_v2.benchmark.source_paired_clearance_activation as activation_evidence_module
import betelgeuze_engine_v2.docking.source_paired_clearance_activation as activation_state_module
from betelgeuze_engine_v2.benchmark.source_paired_clearance_activation import (
    INTERNAL_VALIDITY_REQUIRED_CHECK_NAMES,
    POSEBUSTERS_REQUIRED_CHECK_NAMES,
    SOURCE_PAIRED_CLEARANCE_CASE_SOURCE_AUTHORITY_SHA256,
    SOURCE_PAIRED_CLEARANCE_SCORED_CASE_IDS,
    SourcePairedClearanceActivationEvidenceError,
    SourcePairedClearanceArmRankingReceiptV1,
    SourcePairedClearanceCandidateEvidenceV1,
    SourcePairedClearanceCaseSourceReceiptV1,
    SourcePairedClearanceCurrentV7LineageReceiptV1,
    SourcePairedClearanceInternalValidityEvidenceV1,
    SourcePairedClearancePoseBustersEvidenceV1,
    SourcePairedClearanceRmsdEvidenceV1,
    SourcePairedClearanceSelectionActivationReceiptV1,
)
from betelgeuze_engine_v2.docking.source_paired_clearance_activation import (
    SourcePairedClearanceActivationError,
    build_source_paired_clearance_activated_state_v1,
)
from betelgeuze_engine_v2.docking.scorer_v1 import ScorerV1Terms
from betelgeuze_engine_v2.docking.proposals import DockingProposal
from betelgeuze_engine_v2.docking.torsion_contact_refinement import (
    SourcePairedTorsionRescueActivationSnapshotV1,
)
from betelgeuze_engine_v2.docking.validity import PoseValidityResult


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode("ascii")).hexdigest()


_ACTIVATION_FIXTURES = runpy.run_path(
    str(Path(__file__).with_name("test_source_paired_clearance_activation.py"))
)
_PRODUCTION_CASE_SOURCE_AUTHORITY = (
    activation_evidence_module._FROZEN_CASE_SOURCE_AUTHORITY_BY_CASE
)
_PRODUCTION_CASE_SOURCE_AUTHORITY_LOOKUP = (
    activation_evidence_module._frozen_case_source_authority
)
_PRODUCTION_CASE_SOURCE_AUTHORITY = (
    activation_evidence_module._FROZEN_CASE_SOURCE_AUTHORITY_BY_CASE
)


@pytest.fixture(autouse=True)
def _synthetic_case_source_authority(monkeypatch: pytest.MonkeyPatch) -> None:
    synthetic_authority: dict[str, dict[str, str]] = {}
    monkeypatch.setattr(
        activation_evidence_module,
        "_FROZEN_CASE_SOURCE_AUTHORITY_BY_CASE",
        synthetic_authority,
    )
    monkeypatch.setattr(
        activation_evidence_module,
        "_frozen_case_source_authority",
        synthetic_authority.get,
    )


def _reflection_copy(value):
    forged = object.__new__(type(value))
    for descriptor in fields(value):
        object.__setattr__(forged, descriptor.name, getattr(value, descriptor.name))
    return forged


def test_runtime_case_source_authority_matches_frozen_policy_identity() -> None:
    payload = {
        case_id: dict(authority)
        for case_id, authority in _PRODUCTION_CASE_SOURCE_AUTHORITY.items()
    }
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")

    assert tuple(payload) == SOURCE_PAIRED_CLEARANCE_SCORED_CASE_IDS
    assert hashlib.sha256(canonical).hexdigest() == (
        SOURCE_PAIRED_CLEARANCE_CASE_SOURCE_AUTHORITY_SHA256
    )
    assert SOURCE_PAIRED_CLEARANCE_CASE_SOURCE_AUTHORITY_SHA256 == (
        "4c083af473c369bf35fc34fdf4fe797ddbb2ef60b5474a78d6354415e3aa06bc"
    )
    for case_id, authority in _PRODUCTION_CASE_SOURCE_AUTHORITY.items():
        assert dict(_PRODUCTION_CASE_SOURCE_AUTHORITY_LOOKUP(case_id) or {}) == dict(
            authority
        )


def _validity(*, failed_check: str | None = None) -> PoseValidityResult:
    checks = {
        name: name != failed_check for name in INTERNAL_VALIDITY_REQUIRED_CHECK_NAMES
    }
    blocker_by_check = {
        "proper_rotation": "rigid_rotation_not_proper_orthogonal",
        "bond_lengths_preserved": "bond_length_preservation_failed",
        "ligand_self_clash_free": "ligand_self_clash_detected",
        "receptor_ligand_clash_free": "receptor_ligand_clash_detected",
        "declared_chirality_preserved": "declared_chirality_not_preserved",
        "inside_declared_pocket": "pose_outside_declared_pocket",
    }
    blockers = () if failed_check is None else (blocker_by_check[failed_check],)
    return PoseValidityResult(
        checks=checks,
        evaluated_checks={name: True for name in checks},
        complete=True,
        valid_within_evaluated_scope=failed_check is None,
        measurements={"minimum_receptor_ligand_distance_angstrom": 2.5},
        blockers=blockers,
        not_evaluated_reasons={},
    )


def _candidate(
    index: int,
    *,
    authority_sha256: str,
    problem_sha256: str,
    source_sha256: str,
    candidate_id: str,
    rank: int | None = None,
    variant: str = "baseline",
    score: float | None = None,
    proposal_sha256: str | None = None,
    coordinate_sha256: str | None = None,
    scorer_context_sha256: str | None = None,
    validity_coordinate_sha256: str | None = None,
    native_pose_sha256: str | None = None,
    receptor_sha256: str | None = None,
) -> SourcePairedClearanceCandidateEvidenceV1:
    observed_score = float(index if score is None else score)
    proposal_sha = proposal_sha256 or _digest(f"proposal:{variant}:{index}")
    coordinate_sha = coordinate_sha256 or _digest(f"coordinates:{variant}:{index}")
    pose_sha = _digest(f"pose:{variant}:{index}")
    native_sha = native_pose_sha256 or _digest("native-pose")
    receptor_artifact_sha = receptor_sha256 or _digest("receptor-artifact")
    report_sha = _digest(f"posebusters-report:{variant}:{index}")
    terms = ScorerV1Terms(
        proposal_fingerprint_sha256=proposal_sha,
        authority_input_receipt_sha256=authority_sha256,
        context_fingerprint_sha256=(scorer_context_sha256 or _digest("context")),
        config_fingerprint_sha256=_digest("scorer-config"),
        backend_receipt_sha256=_digest("backend"),
        typed_vdw=observed_score,
        electrostatics=0.0,
        directional_hbond=0.0,
        hydrophobic_contact=0.0,
        desolvation_proxy=0.0,
        torsion_energy=0.0,
        ligand_strain=0.0,
        weak_pocket_prior=0.0,
        total_score=observed_score,
        receptor_candidate_pair_count=10,
        ligand_pair_count=2,
        hbond_count=1,
        hydrophobic_contact_count=1,
        buried_polar_count=0,
    )
    internal = SourcePairedClearanceInternalValidityEvidenceV1(
        proposal_fingerprint_sha256=proposal_sha,
        coordinate_sha256=(validity_coordinate_sha256 or coordinate_sha),
        pose_artifact_sha256=pose_sha,
        authority_input_receipt_sha256=authority_sha256,
        problem_fingerprint_sha256=problem_sha256,
        context_fingerprint_sha256=_digest("validity-context"),
        config_fingerprint_sha256=_digest("validity-config"),
        evaluator_implementation_sha256=_digest("validity-implementation"),
        result=_validity(),
    )
    posebusters = SourcePairedClearancePoseBustersEvidenceV1(
        implementation_sha256=_digest("posebusters-implementation"),
        config_sha256=_digest("posebusters-config"),
        proposal_fingerprint_sha256=proposal_sha,
        coordinate_sha256=coordinate_sha,
        pose_artifact_sha256=pose_sha,
        native_pose_artifact_sha256=native_sha,
        receptor_artifact_sha256=receptor_artifact_sha,
        report_artifact_sha256=report_sha,
        check_results={name: True for name in POSEBUSTERS_REQUIRED_CHECK_NAMES},
    )
    rmsd = SourcePairedClearanceRmsdEvidenceV1(
        implementation_sha256=posebusters.implementation_sha256,
        config_sha256=posebusters.config_sha256,
        proposal_fingerprint_sha256=proposal_sha,
        coordinate_sha256=coordinate_sha,
        pose_artifact_sha256=pose_sha,
        native_pose_artifact_sha256=native_sha,
        receptor_artifact_sha256=receptor_artifact_sha,
        atom_mapping_sha256=_digest("atom-mapping"),
        symmetry_policy_sha256=_digest("symmetry-policy"),
        report_artifact_sha256=report_sha,
        rmsd_angstrom=1.5,
    )
    return SourcePairedClearanceCandidateEvidenceV1(
        candidate_id=candidate_id,
        proposal_index=index,
        candidate_proposal_fingerprint_sha256=proposal_sha,
        source_proposal_fingerprint_sha256=source_sha256,
        coordinate_sha256=coordinate_sha,
        pose_artifact_sha256=pose_sha,
        scorer_terms=terms,
        internal_validity=internal,
        posebusters=posebusters,
        rmsd=rmsd,
        raw_score_rank=index + 1 if rank is None else rank,
    )


def _current_v7_lineage(
    proposal_receipt,
    proposals,
    currents,
    snapshots,
):
    current_v7_proposals = list(proposals)
    source_v11_receipts = [None] * 64
    for current, snapshot in zip(currents, snapshots, strict=True):
        proposal_index = int(snapshot.to_dict()["proposal_index"])
        current_v7_proposals[proposal_index] = current
        source_v11_receipts[proposal_index] = snapshot.to_dict()[
            "source_v11_receipt_payload"
        ]
    return SourcePairedClearanceCurrentV7LineageReceiptV1(
        source_proposal_receipt=proposal_receipt,
        current_v7_proposals=current_v7_proposals,
        source_v11_receipts=source_v11_receipts,
    )


def _case_source(proposal_receipt, problem_sha256: str, lineage):
    authority = {
        "allocation_receipt_sha256": proposal_receipt.allocation.allocation_sha256,
        "authenticated_input_receipt_sha256": (
            proposal_receipt.authenticated_input_receipt_sha256
        ),
        "current_v7_candidate_lineage_sha256": lineage.lineage_identity_sha256,
        "input_artifact_set_sha256": _digest("input-artifact-set"),
        "native_pose_artifact_sha256": _digest("native-pose"),
        "receptor_artifact_sha256": _digest("receptor-artifact"),
        "source_case_member_path": "receipts/engine_v2/5SD5_HWI.json",
        "source_case_member_receipt_sha256": _digest("source-case-receipt"),
        "source_case_member_sha256": _digest("source-case-member"),
        "source_proposal_receipt_sha256": proposal_receipt.receipt_sha256,
    }
    activation_evidence_module._FROZEN_CASE_SOURCE_AUTHORITY_BY_CASE["5SD5_HWI"] = (
        authority
    )
    return SourcePairedClearanceCaseSourceReceiptV1(
        case_id="5SD5_HWI",
        source_case_member_path=authority["source_case_member_path"],
        source_case_member_sha256=authority["source_case_member_sha256"],
        source_case_member_receipt_sha256=authority[
            "source_case_member_receipt_sha256"
        ],
        authenticated_input_receipt_sha256=(
            proposal_receipt.authenticated_input_receipt_sha256
        ),
        problem_fingerprint_sha256=problem_sha256,
        source_proposal_receipt_sha256=proposal_receipt.receipt_sha256,
        allocation_receipt_sha256=proposal_receipt.allocation.allocation_sha256,
        native_pose_artifact_sha256=_digest("native-pose"),
        receptor_artifact_sha256=_digest("receptor-artifact"),
        input_artifact_set_sha256=_digest("input-artifact-set"),
        current_v7_candidate_lineage_sha256=lineage.lineage_identity_sha256,
    )


def _baseline_rows(proposal_receipt, problem_sha256: str):
    authority = proposal_receipt.authenticated_input_receipt_sha256
    return tuple(
        _candidate(
            index,
            authority_sha256=authority,
            problem_sha256=problem_sha256,
            source_sha256=proposal_receipt.proposal_fingerprint_sha256s[index],
            proposal_sha256=proposal_receipt.proposal_fingerprint_sha256s[index],
            coordinate_sha256=(
                proposal_receipt.proposal_coordinate_fingerprint_sha256s[index]
            ),
            candidate_id=proposal_receipt.candidate_ids[index],
        )
        for index in range(64)
    )


def _complete_activation_evidence(*, retained: bool = False):
    fixture = _ACTIVATION_FIXTURES["_fixture"]
    proposals, current_v7, snapshot, proposal_receipt = fixture(
        permissive_selection_window=retained
    )
    state = build_source_paired_clearance_activated_state_v1(snapshot, current_v7)
    lineage = _current_v7_lineage(
        proposal_receipt,
        proposals,
        (current_v7,),
        (snapshot,),
    )
    selected = state.selected_or_retained_proposal
    problem_sha = current_v7.problem_fingerprint_sha256
    target = int(snapshot.to_dict()["proposal_index"])
    source_sha = proposal_receipt.proposal_fingerprint_sha256s[target]
    baseline_rows = list(_baseline_rows(proposal_receipt, problem_sha))
    common = {
        "authority_sha256": proposal_receipt.authenticated_input_receipt_sha256,
        "problem_sha256": problem_sha,
        "source_sha256": source_sha,
        "candidate_id": proposal_receipt.candidate_ids[target],
    }
    baseline_rows[target] = _candidate(
        target,
        variant="real-current-v7",
        proposal_sha256=current_v7.fingerprint_sha256,
        coordinate_sha256=current_v7.coordinate_fingerprint_sha256,
        **common,
    )
    experimental_rows = list(baseline_rows)
    experimental_rows[target] = _candidate(
        target,
        variant=("real-current-v7" if retained else "real-clearance-activated"),
        proposal_sha256=selected.fingerprint_sha256,
        coordinate_sha256=selected.coordinate_fingerprint_sha256,
        **common,
    )
    baseline = SourcePairedClearanceArmRankingReceiptV1(
        arm="baseline_current_v7",
        candidate_rows=baseline_rows,
    )
    experimental = SourcePairedClearanceArmRankingReceiptV1(
        arm="experimental_clearance_shadow",
        candidate_rows=experimental_rows,
    )
    return {
        "proposals": proposals,
        "proposal_receipt": proposal_receipt,
        "case_source": _case_source(proposal_receipt, problem_sha, lineage),
        "current_v7_lineage": lineage,
        "target": target,
        "snapshot": snapshot,
        "state": state,
        "baseline": baseline,
        "experimental": experimental,
        "problem_sha": problem_sha,
    }


def _outer(
    evidence,
    *,
    case_source=None,
    current_v7_lineage=None,
    baseline=None,
    experimental=None,
    snapshots=None,
    states=None,
):
    return SourcePairedClearanceSelectionActivationReceiptV1(
        case_source=evidence["case_source"] if case_source is None else case_source,
        source_proposal_receipt=evidence["proposal_receipt"],
        current_v7_lineage=(
            evidence["current_v7_lineage"]
            if current_v7_lineage is None
            else current_v7_lineage
        ),
        source_snapshots=(evidence["snapshot"],) if snapshots is None else snapshots,
        activated_states=(evidence["state"],) if states is None else states,
        baseline_arm=evidence["baseline"] if baseline is None else baseline,
        experimental_arm=(
            evidence["experimental"] if experimental is None else experimental
        ),
    )


def test_full_arm_ranking_retains_terms_validity_and_exact_order() -> None:
    evidence = _complete_activation_evidence()
    payload = evidence["baseline"].to_dict()

    assert payload["candidate_denominator"] == 64
    assert len(payload["candidate_rows_by_proposal_index"]) == 64
    assert payload["raw_rank_order_proposal_indices"] == list(range(64))
    first = payload["candidate_rows_by_proposal_index"][0]
    assert first["scorer_v1_terms"]["receipt_sha256"]
    assert first["internal_pose_validity"]["receipt_sha256"]
    assert first["posebusters"]["receipt_sha256"]
    assert first["rmsd"]["receipt_sha256"]
    assert len(first["posebusters"]["check_results"]) == len(
        POSEBUSTERS_REQUIRED_CHECK_NAMES
    )


def test_arm_ranking_rejects_claimed_rank_drift() -> None:
    evidence = _complete_activation_evidence()
    rows = list(evidence["baseline"].candidate_rows)
    rows[0] = replace(rows[0], raw_score_rank=2)

    with pytest.raises(SourcePairedClearanceActivationEvidenceError, match="raw ranks"):
        SourcePairedClearanceArmRankingReceiptV1(
            arm="baseline_current_v7",
            candidate_rows=rows,
        )


def test_arm_ranking_rejects_scorer_authority_crosswire() -> None:
    evidence = _complete_activation_evidence()
    rows = list(evidence["baseline"].candidate_rows)
    row = rows[63]
    rows[63] = replace(
        row,
        scorer_terms=replace(
            row.scorer_terms,
            context_fingerprint_sha256=_digest("cross-wired-context"),
        ),
    )

    with pytest.raises(
        SourcePairedClearanceActivationEvidenceError,
        match="scorer authority",
    ):
        SourcePairedClearanceArmRankingReceiptV1(
            arm="baseline_current_v7",
            candidate_rows=rows,
        )


def test_activation_receipt_binds_all_targets_and_both_rankings() -> None:
    evidence = _complete_activation_evidence()
    receipt = _outer(evidence)
    payload = receipt.to_dict()

    assert payload["case_id"] == "5SD5_HWI"
    assert payload["activation_target_count"] == 1
    assert payload["activation_targets"][0]["proposal_index"] == evidence["target"]
    assert payload["selected_replacement_proposal_indices"] == [evidence["target"]]
    assert payload["full_source_proposal_lineage_verified"] is True
    assert payload["top1_top5_semantics_fully_rederivable"] is True
    assert payload["historical_ab_execution_authorized"] is False


def test_activation_receipt_represents_multiple_allocated_targets() -> None:
    fixture = _ACTIVATION_FIXTURES["_fixture"]
    proposals, currents, snapshots, proposal_receipt = fixture(
        permissive_selection_window=False,
        rescue_pairs=((1, 0), (3, 2)),
        return_all=True,
    )
    states = tuple(
        build_source_paired_clearance_activated_state_v1(snapshot, current)
        for snapshot, current in zip(snapshots, currents, strict=True)
    )
    problem_sha = currents[0].problem_fingerprint_sha256
    baseline_rows = list(_baseline_rows(proposal_receipt, problem_sha))
    experimental_rows = list(baseline_rows)
    for current, snapshot, state in zip(
        currents,
        snapshots,
        states,
        strict=True,
    ):
        target = int(snapshot.to_dict()["proposal_index"])
        selected = state.selected_or_retained_proposal
        common = {
            "authority_sha256": (proposal_receipt.authenticated_input_receipt_sha256),
            "problem_sha256": problem_sha,
            "source_sha256": (proposal_receipt.proposal_fingerprint_sha256s[target]),
            "candidate_id": proposal_receipt.candidate_ids[target],
        }
        baseline_rows[target] = _candidate(
            target,
            variant=f"multi-current-{target}",
            proposal_sha256=current.fingerprint_sha256,
            coordinate_sha256=current.coordinate_fingerprint_sha256,
            **common,
        )
        experimental_rows[target] = _candidate(
            target,
            variant=(
                f"multi-selected-{target}"
                if state.selection_applied
                else f"multi-current-{target}"
            ),
            proposal_sha256=selected.fingerprint_sha256,
            coordinate_sha256=selected.coordinate_fingerprint_sha256,
            **common,
        )
    baseline = SourcePairedClearanceArmRankingReceiptV1(
        arm="baseline_current_v7",
        candidate_rows=baseline_rows,
    )
    experimental = SourcePairedClearanceArmRankingReceiptV1(
        arm="experimental_clearance_shadow",
        candidate_rows=experimental_rows,
    )
    lineage = _current_v7_lineage(
        proposal_receipt,
        proposals,
        currents,
        snapshots,
    )
    receipt = SourcePairedClearanceSelectionActivationReceiptV1(
        case_source=_case_source(proposal_receipt, problem_sha, lineage),
        source_proposal_receipt=proposal_receipt,
        current_v7_lineage=lineage,
        source_snapshots=snapshots,
        activated_states=states,
        baseline_arm=baseline,
        experimental_arm=experimental,
    )

    payload = receipt.to_dict()
    assert payload["activation_target_count"] == 2
    assert [row["proposal_index"] for row in payload["activation_targets"]] == [1, 3]
    assert payload["selected_replacement_proposal_indices"] == [
        index
        for index, state in zip((1, 3), states, strict=True)
        if state.selection_applied
    ]


def test_activation_receipt_rejects_non_target_arm_change() -> None:
    evidence = _complete_activation_evidence()
    experimental_rows = list(evidence["experimental"].candidate_rows)
    source = experimental_rows[8]
    experimental_rows[8] = _candidate(
        8,
        authority_sha256=source.scorer_terms.authority_input_receipt_sha256,
        problem_sha256=source.internal_validity.problem_fingerprint_sha256,
        source_sha256=source.source_proposal_fingerprint_sha256,
        candidate_id=source.candidate_id,
        variant="illicit",
        score=source.scorer_terms.total_score,
    )
    experimental = SourcePairedClearanceArmRankingReceiptV1(
        arm="experimental_clearance_shadow",
        candidate_rows=experimental_rows,
    )

    with pytest.raises(
        SourcePairedClearanceActivationEvidenceError,
        match="non-target candidate",
    ):
        _outer(evidence, experimental=experimental)


def test_outer_rederives_pre_score_state_and_rejects_private_forgery() -> None:
    evidence = _complete_activation_evidence(retained=True)
    projection = evidence["state"].to_dict()
    projection.pop("state_sha256")
    projection["shadow_selection_eligible"] = True
    projection["selection_applied"] = True

    with pytest.raises(
        SourcePairedClearanceActivationError,
        match="snapshot-driven public builder",
    ):
        activation_state_module._build_activated_state(
            baseline_proposal=evidence["state"].baseline_proposal,
            selected_proposal=evidence["state"].selected_or_retained_proposal,
            projection=projection,
            _builder_token=object(),
        )

    forged = activation_state_module._build_activated_state(
        baseline_proposal=evidence["state"].baseline_proposal,
        selected_proposal=evidence["state"].selected_or_retained_proposal,
        projection=projection,
        _builder_token=activation_state_module._ACTIVATED_STATE_BUILDER_TOKEN,
    )
    with pytest.raises(
        SourcePairedClearanceActivationEvidenceError,
        match="does not rederive",
    ):
        _outer(evidence, states=(forged,))


def test_private_builder_rejects_hidden_selected_proposal_forgery() -> None:
    evidence = _complete_activation_evidence(retained=True)
    baseline = evidence["state"].baseline_proposal
    hidden_selected = baseline.with_refined_coordinates(
        baseline.coordinates + 1.0,
        refiner_id="hidden_selected_forgery",
        refiner_version="1.0.0",
        refinement_receipt_sha256=_digest("hidden selected forgery"),
        torsion_angles=baseline.torsion_angles,
    )
    projection = evidence["state"].to_dict()
    projection.pop("state_sha256")

    with pytest.raises(
        SourcePairedClearanceActivationError,
        match="proposal objects do not match",
    ):
        activation_state_module._build_activated_state(
            baseline_proposal=baseline,
            selected_proposal=hidden_selected,
            projection=projection,
            _builder_token=activation_state_module._ACTIVATED_STATE_BUILDER_TOKEN,
        )


def test_outer_rejects_reflection_hidden_selected_proposal_forgery() -> None:
    evidence = _complete_activation_evidence(retained=True)
    genuine = evidence["state"]
    baseline = genuine.baseline_proposal
    hidden_selected = baseline.with_refined_coordinates(
        baseline.coordinates + 1.0,
        refiner_id="reflection_hidden_selected_forgery",
        refiner_version="1.0.0",
        refinement_receipt_sha256=_digest("reflection hidden selected forgery"),
        torsion_angles=baseline.torsion_angles,
    )
    forged = object.__new__(
        activation_state_module.SourcePairedClearanceActivatedStateV1
    )
    object.__setattr__(forged, "_baseline_proposal", baseline)
    object.__setattr__(forged, "_selected_proposal", hidden_selected)
    object.__setattr__(forged, "_projection", genuine._projection)
    object.__setattr__(forged, "_state_sha256", genuine._state_sha256)

    with pytest.raises(
        SourcePairedClearanceActivationEvidenceError,
        match="does not rederive",
    ):
        _outer(evidence, states=(forged,))


def test_outer_revalidates_reflection_forged_case_source() -> None:
    evidence = _complete_activation_evidence(retained=True)
    forged = _reflection_copy(evidence["case_source"])
    object.__setattr__(
        forged,
        "source_case_member_sha256",
        _digest("reflection forged case member"),
    )
    object.__setattr__(
        forged,
        "_receipt_sha256",
        activation_evidence_module._sha256(forged._projection()),
    )

    with pytest.raises(
        SourcePairedClearanceActivationEvidenceError,
        match="frozen archive member authority",
    ):
        _outer(evidence, case_source=forged)


def test_outer_rederives_reflection_forged_current_v7_lineage() -> None:
    evidence = _complete_activation_evidence(retained=True)
    genuine = evidence["current_v7_lineage"]
    forged = _reflection_copy(genuine)
    proposals = list(genuine.current_v7_proposals)
    source = proposals[8]
    proposals[8] = source.with_refined_coordinates(
        source.coordinates + 1.0,
        refiner_id="reflection_hidden_lineage_forgery",
        refiner_version="1.0.0",
        refinement_receipt_sha256=_digest("reflection hidden lineage forgery"),
        torsion_angles=source.torsion_angles,
    )
    object.__setattr__(forged, "current_v7_proposals", tuple(proposals))

    with pytest.raises(
        SourcePairedClearanceActivationEvidenceError,
        match="current-V7",
    ):
        _outer(evidence, current_v7_lineage=forged)


def test_outer_rejects_current_v7_proposal_subclass_before_dispatch() -> None:
    evidence = _complete_activation_evidence()
    genuine_lineage = evidence["current_v7_lineage"]
    genuine = genuine_lineage.current_v7_proposals[2]

    class ForgedDockingProposal(DockingProposal):
        def __post_init__(self) -> None:
            pass

        def assert_integrity(self) -> None:
            pass

    forged_proposal = ForgedDockingProposal(
        candidate_id=genuine.candidate_id,
        coordinates=genuine.coordinates + 999.0,
        torsion_angles=genuine.torsion_angles,
        rotation=genuine.rotation,
        translation=genuine.translation,
        proposal_index=genuine.proposal_index,
        seed=genuine.seed,
        fingerprint_sha256=genuine.fingerprint_sha256,
        problem_fingerprint_sha256=genuine.problem_fingerprint_sha256,
        search_space_fingerprint_sha256=genuine.search_space_fingerprint_sha256,
        coordinate_fingerprint_sha256=genuine.coordinate_fingerprint_sha256,
        parent_proposal_fingerprint_sha256=(genuine.parent_proposal_fingerprint_sha256),
        refiner_id=genuine.refiner_id,
        refiner_version=genuine.refiner_version,
        refinement_receipt_sha256=genuine.refinement_receipt_sha256,
    )
    proposals = list(genuine_lineage.current_v7_proposals)
    proposals[2] = forged_proposal
    forged_lineage = _reflection_copy(genuine_lineage)
    object.__setattr__(
        forged_lineage,
        "current_v7_proposals",
        tuple(proposals),
    )

    with pytest.raises(TypeError, match="current_v7_proposals"):
        _outer(evidence, current_v7_lineage=forged_lineage)


def test_both_arms_cannot_share_one_forged_non_target_candidate() -> None:
    evidence = _complete_activation_evidence()
    index = 8
    source = evidence["baseline"].candidate_rows[index]
    forged = _candidate(
        index,
        authority_sha256=source.scorer_terms.authority_input_receipt_sha256,
        problem_sha256=source.internal_validity.problem_fingerprint_sha256,
        source_sha256=source.source_proposal_fingerprint_sha256,
        candidate_id=source.candidate_id,
        rank=source.raw_score_rank,
        variant="same-forged-non-target",
        score=source.scorer_terms.total_score,
        proposal_sha256=_digest("forged-non-target-proposal"),
        coordinate_sha256=_digest("forged-non-target-coordinate"),
    )
    baseline_rows = list(evidence["baseline"].candidate_rows)
    experimental_rows = list(evidence["experimental"].candidate_rows)
    baseline_rows[index] = forged
    experimental_rows[index] = forged
    baseline = SourcePairedClearanceArmRankingReceiptV1(
        arm="baseline_current_v7",
        candidate_rows=baseline_rows,
    )
    experimental = SourcePairedClearanceArmRankingReceiptV1(
        arm="experimental_clearance_shadow",
        candidate_rows=experimental_rows,
    )

    with pytest.raises(
        SourcePairedClearanceActivationEvidenceError,
        match="exact current-V7 lineage",
    ):
        _outer(evidence, baseline=baseline, experimental=experimental)


def test_case_source_cannot_be_relabelled_to_another_archive_member() -> None:
    evidence = _complete_activation_evidence()
    original_authority = dict(
        activation_evidence_module._FROZEN_CASE_SOURCE_AUTHORITY_BY_CASE["5SD5_HWI"]
    )
    other_authority = {
        **original_authority,
        "allocation_receipt_sha256": _digest("6WTN allocation"),
        "authenticated_input_receipt_sha256": _digest("6WTN input"),
        "current_v7_candidate_lineage_sha256": _digest("6WTN lineage"),
        "input_artifact_set_sha256": _digest("6WTN inputs"),
        "native_pose_artifact_sha256": _digest("6WTN native"),
        "receptor_artifact_sha256": _digest("6WTN receptor"),
        "source_case_member_path": "receipts/engine_v2/6WTN_RXT.json",
        "source_case_member_receipt_sha256": _digest("6WTN member receipt"),
        "source_case_member_sha256": _digest("6WTN member"),
        "source_proposal_receipt_sha256": _digest("6WTN proposal receipt"),
    }
    activation_evidence_module._FROZEN_CASE_SOURCE_AUTHORITY_BY_CASE["6WTN_RXT"] = (
        other_authority
    )

    with pytest.raises(
        SourcePairedClearanceActivationEvidenceError,
        match="frozen archive member authority",
    ):
        replace(
            evidence["case_source"],
            case_id="6WTN_RXT",
            source_case_member_path=other_authority["source_case_member_path"],
            source_case_member_sha256=other_authority["source_case_member_sha256"],
            source_case_member_receipt_sha256=other_authority[
                "source_case_member_receipt_sha256"
            ],
        )


def test_case_source_rejects_arbitrary_member_hash() -> None:
    evidence = _complete_activation_evidence()
    with pytest.raises(
        SourcePairedClearanceActivationEvidenceError,
        match="frozen archive member authority",
    ):
        replace(
            evidence["case_source"],
            source_case_member_sha256=_digest("arbitrary-member"),
        )


def test_activation_receipt_requires_every_allocated_target() -> None:
    evidence = _complete_activation_evidence()
    with pytest.raises(
        SourcePairedClearanceActivationEvidenceError,
        match="every allocated rescue target",
    ):
        _outer(evidence, snapshots=(), states=())


def test_retained_target_cannot_change_post_decision_evidence() -> None:
    evidence = _complete_activation_evidence(retained=True)
    assert evidence["state"].selection_applied is False
    target = evidence["target"]
    experimental_rows = list(evidence["experimental"].candidate_rows)
    baseline = evidence["baseline"].candidate_rows[target]
    experimental_rows[target] = _candidate(
        target,
        authority_sha256=baseline.scorer_terms.authority_input_receipt_sha256,
        problem_sha256=baseline.internal_validity.problem_fingerprint_sha256,
        source_sha256=baseline.source_proposal_fingerprint_sha256,
        candidate_id=baseline.candidate_id,
        proposal_sha256=baseline.candidate_proposal_fingerprint_sha256,
        coordinate_sha256=baseline.coordinate_sha256,
        variant="illicit-retained-evidence",
        score=baseline.scorer_terms.total_score,
    )
    experimental = SourcePairedClearanceArmRankingReceiptV1(
        arm="experimental_clearance_shadow",
        candidate_rows=experimental_rows,
    )

    with pytest.raises(
        SourcePairedClearanceActivationEvidenceError,
        match="retained target changed",
    ):
        _outer(evidence, experimental=experimental)


def test_candidate_rejects_validity_from_another_coordinate() -> None:
    evidence = _complete_activation_evidence()
    row = evidence["baseline"].candidate_rows[0]

    with pytest.raises(
        SourcePairedClearanceActivationEvidenceError,
        match="another candidate pose",
    ):
        replace(
            row,
            internal_validity=replace(
                row.internal_validity,
                coordinate_sha256=_digest("wrong-coordinate"),
            ),
        )


def test_internal_validity_rejects_incoherent_result() -> None:
    incoherent = PoseValidityResult(
        checks={name: False for name in INTERNAL_VALIDITY_REQUIRED_CHECK_NAMES},
        evaluated_checks={
            name: True for name in INTERNAL_VALIDITY_REQUIRED_CHECK_NAMES
        },
        complete=True,
        valid_within_evaluated_scope=True,
        measurements={},
        blockers=(),
        not_evaluated_reasons={},
    )
    with pytest.raises(
        SourcePairedClearanceActivationEvidenceError,
        match="incomplete",
    ):
        SourcePairedClearanceInternalValidityEvidenceV1(
            proposal_fingerprint_sha256=_digest("proposal"),
            coordinate_sha256=_digest("coordinate"),
            pose_artifact_sha256=_digest("pose"),
            authority_input_receipt_sha256=_digest("authority"),
            problem_fingerprint_sha256=_digest("problem"),
            context_fingerprint_sha256=_digest("context"),
            config_fingerprint_sha256=_digest("config"),
            evaluator_implementation_sha256=_digest("implementation"),
            result=incoherent,
        )


def test_posebusters_rejects_truncated_check_map() -> None:
    with pytest.raises(
        SourcePairedClearanceActivationEvidenceError,
        match="complete check set",
    ):
        SourcePairedClearancePoseBustersEvidenceV1(
            implementation_sha256=_digest("implementation"),
            config_sha256=_digest("config"),
            proposal_fingerprint_sha256=_digest("proposal"),
            coordinate_sha256=_digest("coordinate"),
            pose_artifact_sha256=_digest("pose"),
            native_pose_artifact_sha256=_digest("native"),
            receptor_artifact_sha256=_digest("receptor"),
            report_artifact_sha256=_digest("report"),
            check_results={"minimum_distance_to_protein": True},
        )


def test_outer_rejects_scorer_authority_not_bound_to_source_snapshot() -> None:
    evidence = _complete_activation_evidence()
    baseline_rows = [
        replace(
            row,
            scorer_terms=replace(
                row.scorer_terms,
                authority_input_receipt_sha256=_digest("other-authority"),
            ),
        )
        for row in evidence["baseline"].candidate_rows
    ]
    experimental_rows = [
        replace(
            row,
            scorer_terms=replace(
                row.scorer_terms,
                authority_input_receipt_sha256=_digest("other-authority"),
            ),
        )
        for row in evidence["experimental"].candidate_rows
    ]
    baseline = SourcePairedClearanceArmRankingReceiptV1(
        arm="baseline_current_v7",
        candidate_rows=baseline_rows,
    )
    experimental = SourcePairedClearanceArmRankingReceiptV1(
        arm="experimental_clearance_shadow",
        candidate_rows=experimental_rows,
    )

    with pytest.raises(
        SourcePairedClearanceActivationEvidenceError,
        match="source case",
    ):
        _outer(evidence, baseline=baseline, experimental=experimental)


def test_activation_receipt_requires_builder_produced_snapshots_and_states() -> None:
    evidence = _complete_activation_evidence()
    with pytest.raises(
        SourcePairedClearanceActivationEvidenceError,
        match="every allocated rescue target",
    ):
        _outer(
            evidence,
            snapshots=(evidence["snapshot"].to_dict(),),
        )


def test_activation_receipt_rejects_snapshot_subclass_dispatch() -> None:
    evidence = _complete_activation_evidence()
    genuine = evidence["snapshot"]

    class SnapshotSubclass(SourcePairedTorsionRescueActivationSnapshotV1):
        def __init__(self) -> None:
            pass

        @property
        def snapshot_sha256(self) -> str:
            return genuine.snapshot_sha256

        def to_dict(self) -> dict[str, object]:
            return genuine.to_dict()

    with pytest.raises(
        SourcePairedClearanceActivationEvidenceError,
        match="every allocated rescue target",
    ):
        _outer(evidence, snapshots=(SnapshotSubclass(),))
