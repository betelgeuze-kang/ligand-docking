from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import runpy

import pytest

import betelgeuze_engine_v2.benchmark.source_paired_clearance_activation as activation_module
from betelgeuze_engine_v2.benchmark.source_paired_clearance_activation import (
    INTERNAL_VALIDITY_REQUIRED_CHECK_NAMES,
    POSEBUSTERS_REQUIRED_CHECK_NAMES,
    SOURCE_PAIRED_CLEARANCE_SCORED_CASE_IDS,
    SourcePairedClearanceArmRankingReceiptV1,
    SourcePairedClearanceCandidateEvidenceV1,
    SourcePairedClearanceCaseSourceReceiptV1,
    SourcePairedClearanceInternalValidityEvidenceV1,
    SourcePairedClearancePoseBustersEvidenceV1,
    SourcePairedClearanceRmsdEvidenceV1,
    SourcePairedClearanceSelectionActivationReceiptV1,
)
from betelgeuze_engine_v2.benchmark.source_paired_clearance_one_shot_ab import (
    OneShotABAuthorityError,
    sha256_payload,
)
from betelgeuze_engine_v2.benchmark.source_paired_clearance_one_shot_full_evidence import (
    build_external_evidence_envelope,
    build_full_evidence_bundle,
    verify_full_evidence_file,
)
from betelgeuze_engine_v2.docking.scorer_v1 import (
    ScorerBackend,
    ScorerBackendReceipt,
    ScorerV1Terms,
)
from betelgeuze_engine_v2.docking.source_paired_clearance_activation import (
    build_source_paired_clearance_activated_state_v1,
)
from betelgeuze_engine_v2.docking.validity import PoseValidityResult


_HELPERS = runpy.run_path(
    str(
        Path(__file__).with_name(
            "test_source_paired_clearance_activation_evidence.py"
        )
    )
)
_FIXTURE = _HELPERS["_ACTIVATION_FIXTURES"]["_fixture"]
_CURRENT_V7_LINEAGE = _HELPERS["_current_v7_lineage"]


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode("ascii")).hexdigest()


def _run_start() -> dict[str, object]:
    return {
        "receipt_sha256": "1" * 64,
        "source_commit_git_sha1": "2" * 40,
        "execution_environment_sha256": "3" * 64,
        "required_scorer_backend": "rust_cpu_required",
    }


def _backend() -> ScorerBackendReceipt:
    return ScorerBackendReceipt(
        backend=ScorerBackend.RUST_CPU_REQUIRED,
        backend_version="synthetic-test-v1",
        implementation_source_sha256=_digest("backend-implementation"),
        options_fingerprint_sha256=_digest("backend-options"),
        extension_sha256=_digest("backend-extension"),
        cargo_lock_sha256=_digest("backend-cargo-lock"),
        rustc_version="rustc 1.90.0 synthetic",
        target_triple="x86_64-unknown-linux-gnu",
        build_flags=("-Copt-level=3",),
    )


def _validity(*, receptor_clash: bool = False) -> PoseValidityResult:
    checks = {
        name: not (
            receptor_clash and name == "receptor_ligand_clash_free"
        )
        for name in INTERNAL_VALIDITY_REQUIRED_CHECK_NAMES
    }
    blockers = (
        ("receptor_ligand_clash_detected",) if receptor_clash else ()
    )
    return PoseValidityResult(
        checks=checks,
        evaluated_checks={name: True for name in checks},
        complete=True,
        valid_within_evaluated_scope=not receptor_clash,
        measurements={"minimum_receptor_ligand_distance_angstrom": 2.5},
        blockers=blockers,
        not_evaluated_reasons={},
    )


def _candidate(
    *,
    case_id: str,
    index: int,
    rank: int,
    candidate_id: str,
    source_proposal_sha256: str,
    proposal_sha256: str,
    coordinate_sha256: str,
    authority_sha256: str,
    problem_sha256: str,
    native_pose_sha256: str,
    receptor_sha256: str,
    backend_sha256: str,
    variant: str,
    rmsd: float,
) -> SourcePairedClearanceCandidateEvidenceV1:
    score = float(index)
    pose_sha256 = _digest(f"{case_id}:{variant}:pose:{index}")
    report_sha256 = _digest(f"{case_id}:{variant}:report:{index}")
    terms = ScorerV1Terms(
        proposal_fingerprint_sha256=proposal_sha256,
        authority_input_receipt_sha256=authority_sha256,
        context_fingerprint_sha256=_digest(f"{case_id}:scorer-context"),
        config_fingerprint_sha256=_digest("scorer-config"),
        backend_receipt_sha256=backend_sha256,
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
    internal = SourcePairedClearanceInternalValidityEvidenceV1(
        proposal_fingerprint_sha256=proposal_sha256,
        coordinate_sha256=coordinate_sha256,
        pose_artifact_sha256=pose_sha256,
        authority_input_receipt_sha256=authority_sha256,
        problem_fingerprint_sha256=problem_sha256,
        context_fingerprint_sha256=_digest(f"{case_id}:validity-context"),
        config_fingerprint_sha256=_digest("validity-config"),
        evaluator_implementation_sha256=_digest("validity-implementation"),
        result=_validity(),
    )
    posebusters = SourcePairedClearancePoseBustersEvidenceV1(
        implementation_sha256=_digest("posebusters-implementation"),
        config_sha256=_digest("posebusters-config"),
        proposal_fingerprint_sha256=proposal_sha256,
        coordinate_sha256=coordinate_sha256,
        pose_artifact_sha256=pose_sha256,
        native_pose_artifact_sha256=native_pose_sha256,
        receptor_artifact_sha256=receptor_sha256,
        report_artifact_sha256=report_sha256,
        check_results={name: True for name in POSEBUSTERS_REQUIRED_CHECK_NAMES},
    )
    rmsd_evidence = SourcePairedClearanceRmsdEvidenceV1(
        implementation_sha256=posebusters.implementation_sha256,
        config_sha256=posebusters.config_sha256,
        proposal_fingerprint_sha256=proposal_sha256,
        coordinate_sha256=coordinate_sha256,
        pose_artifact_sha256=pose_sha256,
        native_pose_artifact_sha256=native_pose_sha256,
        receptor_artifact_sha256=receptor_sha256,
        atom_mapping_sha256=_digest(f"{case_id}:atom-mapping"),
        symmetry_policy_sha256=_digest("symmetry-policy"),
        report_artifact_sha256=report_sha256,
        rmsd_angstrom=rmsd,
    )
    return SourcePairedClearanceCandidateEvidenceV1(
        candidate_id=candidate_id,
        proposal_index=index,
        candidate_proposal_fingerprint_sha256=proposal_sha256,
        source_proposal_fingerprint_sha256=source_proposal_sha256,
        coordinate_sha256=coordinate_sha256,
        pose_artifact_sha256=pose_sha256,
        scorer_terms=terms,
        internal_validity=internal,
        posebusters=posebusters,
        rmsd=rmsd_evidence,
        raw_score_rank=rank,
    )


def _case_source(
    *,
    case_id: str,
    proposal_receipt,
    problem_sha256: str,
    lineage,
    native_pose_sha256: str,
    receptor_sha256: str,
) -> SourcePairedClearanceCaseSourceReceiptV1:
    authority = {
        "allocation_receipt_sha256": (
            proposal_receipt.allocation.allocation_sha256
        ),
        "authenticated_input_receipt_sha256": (
            proposal_receipt.authenticated_input_receipt_sha256
        ),
        "current_v7_candidate_lineage_sha256": (
            lineage.lineage_identity_sha256
        ),
        "input_artifact_set_sha256": _digest(
            f"{case_id}:input-artifact-set"
        ),
        "native_pose_artifact_sha256": native_pose_sha256,
        "receptor_artifact_sha256": receptor_sha256,
        "source_case_member_path": f"receipts/engine_v2/{case_id}.json",
        "source_case_member_receipt_sha256": _digest(
            f"{case_id}:source-case-receipt"
        ),
        "source_case_member_sha256": _digest(
            f"{case_id}:source-case-member"
        ),
        "source_proposal_receipt_sha256": proposal_receipt.receipt_sha256,
    }
    activation_module._FROZEN_CASE_SOURCE_AUTHORITY_BY_CASE[case_id] = authority
    return SourcePairedClearanceCaseSourceReceiptV1(
        case_id=case_id,
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
        allocation_receipt_sha256=(
            proposal_receipt.allocation.allocation_sha256
        ),
        native_pose_artifact_sha256=native_pose_sha256,
        receptor_artifact_sha256=receptor_sha256,
        input_artifact_set_sha256=authority["input_artifact_set_sha256"],
        current_v7_candidate_lineage_sha256=(
            lineage.lineage_identity_sha256
        ),
    )


def _case_receipt(
    *,
    case_id: str,
    ordinal: int,
    backend: ScorerBackendReceipt,
    proposals,
    current_v7,
    snapshot,
    proposal_receipt,
    lineage,
    state,
) -> SourcePairedClearanceSelectionActivationReceiptV1:
    del proposals
    target = int(snapshot.to_dict()["proposal_index"])
    selected = state.selected_or_retained_proposal
    problem_sha256 = current_v7.problem_fingerprint_sha256
    native_pose_sha256 = _digest(f"{case_id}:native")
    receptor_sha256 = _digest(f"{case_id}:receptor")
    baseline_rows = []
    for index, proposal in enumerate(lineage.current_v7_proposals):
        rmsd = 1.5 if case_id == "6T88_MWQ" and index == 0 else 3.0
        baseline_rows.append(
            _candidate(
                case_id=case_id,
                index=index,
                rank=index + 1,
                candidate_id=proposal_receipt.candidate_ids[index],
                source_proposal_sha256=(
                    proposal_receipt.proposal_fingerprint_sha256s[index]
                ),
                proposal_sha256=proposal.fingerprint_sha256,
                coordinate_sha256=proposal.coordinate_fingerprint_sha256,
                authority_sha256=(
                    proposal_receipt.authenticated_input_receipt_sha256
                ),
                problem_sha256=problem_sha256,
                native_pose_sha256=native_pose_sha256,
                receptor_sha256=receptor_sha256,
                backend_sha256=backend.receipt_sha256,
                variant="baseline",
                rmsd=rmsd,
            )
        )
    experimental_rows = list(baseline_rows)
    experimental_rows[target] = _candidate(
        case_id=case_id,
        index=target,
        rank=target + 1,
        candidate_id=proposal_receipt.candidate_ids[target],
        source_proposal_sha256=(
            proposal_receipt.proposal_fingerprint_sha256s[target]
        ),
        proposal_sha256=selected.fingerprint_sha256,
        coordinate_sha256=selected.coordinate_fingerprint_sha256,
        authority_sha256=proposal_receipt.authenticated_input_receipt_sha256,
        problem_sha256=problem_sha256,
        native_pose_sha256=native_pose_sha256,
        receptor_sha256=receptor_sha256,
        backend_sha256=backend.receipt_sha256,
        variant="experimental",
        rmsd=(1.5 if ordinal < 2 else 3.0),
    )
    baseline = SourcePairedClearanceArmRankingReceiptV1(
        arm="baseline_current_v7",
        candidate_rows=baseline_rows,
    )
    experimental = SourcePairedClearanceArmRankingReceiptV1(
        arm="experimental_clearance_shadow",
        candidate_rows=experimental_rows,
    )
    case_source = _case_source(
        case_id=case_id,
        proposal_receipt=proposal_receipt,
        problem_sha256=problem_sha256,
        lineage=lineage,
        native_pose_sha256=native_pose_sha256,
        receptor_sha256=receptor_sha256,
    )
    return SourcePairedClearanceSelectionActivationReceiptV1(
        case_source=case_source,
        source_proposal_receipt=proposal_receipt,
        current_v7_lineage=lineage,
        source_snapshots=(snapshot,),
        activated_states=(state,),
        baseline_arm=baseline,
        experimental_arm=experimental,
    )


@pytest.fixture(scope="module")
def full_bundle():
    previous_authority = activation_module._FROZEN_CASE_SOURCE_AUTHORITY_BY_CASE
    previous_lookup = activation_module._frozen_case_source_authority
    synthetic_authority: dict[str, dict[str, str]] = {}
    activation_module._FROZEN_CASE_SOURCE_AUTHORITY_BY_CASE = synthetic_authority
    activation_module._frozen_case_source_authority = synthetic_authority.get
    try:
        proposals, current_v7, snapshot, proposal_receipt = _FIXTURE(
            permissive_selection_window=False
        )
        state = build_source_paired_clearance_activated_state_v1(
            snapshot, current_v7
        )
        lineage = _CURRENT_V7_LINEAGE(
            proposal_receipt,
            proposals,
            (current_v7,),
            (snapshot,),
        )
        backend = _backend()
        receipts = [
            _case_receipt(
                case_id=case_id,
                ordinal=ordinal,
                backend=backend,
                proposals=proposals,
                current_v7=current_v7,
                snapshot=snapshot,
                proposal_receipt=proposal_receipt,
                lineage=lineage,
                state=state,
            ).to_dict()
            for ordinal, case_id in enumerate(
                SOURCE_PAIRED_CLEARANCE_SCORED_CASE_IDS
            )
        ]
        yield (
            build_full_evidence_bundle(
                run_start=_run_start(),
                scorer_backend_receipt=backend.to_dict(),
                case_activation_receipts=receipts,
            ),
            backend,
        )
    finally:
        activation_module._FROZEN_CASE_SOURCE_AUTHORITY_BY_CASE = (
            previous_authority
        )
        activation_module._frozen_case_source_authority = previous_lookup


def _reseal(value: dict[str, object], field: str) -> None:
    value.pop(field, None)
    value[field] = sha256_payload(value)


def _write(path: Path, bundle: dict[str, object]) -> None:
    path.write_text(
        json.dumps(bundle, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def test_complete_8_by_64_two_arm_bundle_verifies(
    tmp_path: Path,
    full_bundle,
) -> None:
    bundle, _ = full_bundle
    path = tmp_path / "full-evidence.json"
    _write(path, bundle)

    verified = verify_full_evidence_file(path, run_start=_run_start())

    assert len(verified.case_receipt_sha256s) == 8
    assert len(verified.candidate_receipt_sha256s) == 1024
    assert verified.baseline_summary["candidate_count"] == 512
    assert verified.experimental_summary["candidate_count"] == 512
    assert verified.cross_arm["changed_slot_count"] == 8
    assert verified.cross_arm["shadow_eligible_candidate_count"] == 8


def test_hash_only_manifest_builder_is_rejected() -> None:
    with pytest.raises(OneShotABAuthorityError, match="hash-only"):
        build_external_evidence_envelope()


def test_missing_candidate_row_fails_closed(
    tmp_path: Path,
    full_bundle,
) -> None:
    bundle = copy.deepcopy(full_bundle[0])
    case_row = bundle["case_evidence_rows"][0]
    receipt = case_row["selection_activation_receipt"]
    ranking = receipt["baseline_arm_ranking"]
    ranking["candidate_rows_by_proposal_index"].pop()
    _reseal(receipt, "receipt_sha256")
    case_row["selection_activation_receipt_sha256"] = receipt[
        "receipt_sha256"
    ]
    _reseal(case_row, "receipt_sha256")
    _reseal(bundle, "receipt_sha256")
    path = tmp_path / "missing-row.json"
    _write(path, bundle)

    with pytest.raises(OneShotABAuthorityError, match="exactly 64"):
        verify_full_evidence_file(path, run_start=_run_start())


def test_nested_candidate_tamper_fails_even_after_outer_reseal(
    tmp_path: Path,
    full_bundle,
) -> None:
    bundle = copy.deepcopy(full_bundle[0])
    case_row = bundle["case_evidence_rows"][0]
    receipt = case_row["selection_activation_receipt"]
    candidate = receipt["baseline_arm_ranking"][
        "candidate_rows_by_proposal_index"
    ][0]
    candidate["scorer_v1_terms"]["typed_vdw_binary64_hex"] = (99.0).hex()
    _reseal(receipt, "receipt_sha256")
    case_row["selection_activation_receipt_sha256"] = receipt[
        "receipt_sha256"
    ]
    _reseal(case_row, "receipt_sha256")
    _reseal(bundle, "receipt_sha256")
    path = tmp_path / "candidate-tamper.json"
    _write(path, bundle)

    with pytest.raises(OneShotABAuthorityError):
        verify_full_evidence_file(path, run_start=_run_start())


def test_duplicate_case_or_role_substitution_fails_closed(
    tmp_path: Path,
    full_bundle,
) -> None:
    duplicate = copy.deepcopy(full_bundle[0])
    duplicate["case_evidence_rows"][1] = copy.deepcopy(
        duplicate["case_evidence_rows"][0]
    )
    _reseal(duplicate, "receipt_sha256")
    duplicate_path = tmp_path / "duplicate-case.json"
    _write(duplicate_path, duplicate)
    with pytest.raises(OneShotABAuthorityError, match="case order|coverage"):
        verify_full_evidence_file(duplicate_path, run_start=_run_start())

    swapped = copy.deepcopy(full_bundle[0])
    case_row = swapped["case_evidence_rows"][0]
    receipt = case_row["selection_activation_receipt"]
    receipt["baseline_arm_ranking"], receipt[
        "experimental_arm_ranking"
    ] = (
        receipt["experimental_arm_ranking"],
        receipt["baseline_arm_ranking"],
    )
    _reseal(receipt, "receipt_sha256")
    case_row["selection_activation_receipt_sha256"] = receipt[
        "receipt_sha256"
    ]
    _reseal(case_row, "receipt_sha256")
    _reseal(swapped, "receipt_sha256")
    swapped_path = tmp_path / "role-swap.json"
    _write(swapped_path, swapped)
    with pytest.raises(
        OneShotABAuthorityError, match="baseline_current_v7"
    ):
        verify_full_evidence_file(swapped_path, run_start=_run_start())


def test_summary_changed_slot_and_run_crosswires_fail_closed(
    tmp_path: Path,
    full_bundle,
) -> None:
    summary = copy.deepcopy(full_bundle[0])
    summary["baseline_arm_summary_projection"]["exact_valid_case_ids"] = []
    _reseal(summary, "receipt_sha256")
    summary_path = tmp_path / "summary-tamper.json"
    _write(summary_path, summary)
    with pytest.raises(
        OneShotABAuthorityError, match="independently rederive"
    ):
        verify_full_evidence_file(summary_path, run_start=_run_start())

    changed = copy.deepcopy(full_bundle[0])
    changed["cross_arm_projection"]["changed_slot_count"] = 0
    _reseal(changed, "receipt_sha256")
    changed_path = tmp_path / "changed-slot-tamper.json"
    _write(changed_path, changed)
    with pytest.raises(
        OneShotABAuthorityError, match="independently rederive"
    ):
        verify_full_evidence_file(changed_path, run_start=_run_start())

    cross_run = copy.deepcopy(full_bundle[0])
    cross_run["run_start_receipt_sha256"] = "9" * 64
    _reseal(cross_run, "receipt_sha256")
    cross_run_path = tmp_path / "cross-run.json"
    _write(cross_run_path, cross_run)
    with pytest.raises(OneShotABAuthorityError, match="run_start"):
        verify_full_evidence_file(cross_run_path, run_start=_run_start())


def test_authority_and_backend_substitution_fail_closed(
    tmp_path: Path,
    full_bundle,
) -> None:
    authority = copy.deepcopy(full_bundle[0])
    authority["authority"]["product_execution_authorized"] = True
    _reseal(authority, "receipt_sha256")
    authority_path = tmp_path / "authority.json"
    _write(authority_path, authority)
    with pytest.raises(OneShotABAuthorityError, match="authority"):
        verify_full_evidence_file(authority_path, run_start=_run_start())

    backend = copy.deepcopy(full_bundle[0])
    backend["scorer_backend_receipt"]["backend"] = "python_reference"
    _reseal(backend["scorer_backend_receipt"], "receipt_sha256")
    _reseal(backend, "receipt_sha256")
    backend_path = tmp_path / "backend.json"
    _write(backend_path, backend)
    with pytest.raises(OneShotABAuthorityError, match="Rust CPU|backend"):
        verify_full_evidence_file(backend_path, run_start=_run_start())
