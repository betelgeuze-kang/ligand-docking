from __future__ import annotations

# Torch is optional for collection; engine imports intentionally follow this guard.
# ruff: noqa: E402

from dataclasses import replace
import hashlib
from pathlib import Path
import runpy

import pytest

torch = pytest.importorskip("torch")

from betelgeuze_engine_v2 import canonical_topology_sha256
import betelgeuze_engine_v2.benchmark.global_orientation_development_decision as decision_module
import betelgeuze_engine_v2.benchmark.source_paired_clearance_activation as activation_module
from betelgeuze_engine_v2.benchmark.global_orientation_development_contracts import (
    GLOBAL_ORIENTATION_DEVELOPMENT_SCORED_CASE_IDS,
    GLOBAL_ORIENTATION_EXPECTED_EVALUATION_PIPELINE_SHA256,
    GlobalOrientationDevelopmentArmLineageReceiptV1,
    GlobalOrientationDevelopmentArmObservationsV1,
    GlobalOrientationDevelopmentCaseSourceReceiptV1,
    GlobalOrientationDevelopmentHistoricalFailureAuthorityV1,
    GlobalOrientationDevelopmentLineageSlotV1,
    GlobalOrientationDevelopmentPreparationFailureReceiptV1,
    derive_global_orientation_pose_validity_config_fingerprint,
    derive_global_orientation_pocket_declaration_sha256,
    derive_global_orientation_scorer_implementation_manifest_sha256,
    derive_global_orientation_source_coordinates_sha256,
)
from betelgeuze_engine_v2.benchmark.global_orientation_development_decision import (
    GLOBAL_ORIENTATION_DEVELOPMENT_COHORT_DECISION_SCHEMA_ID,
    GLOBAL_ORIENTATION_DEVELOPMENT_SCORED_CASE_COMPARISON_SCHEMA_ID,
    GlobalOrientationDevelopmentCohortDecisionV1,
    GlobalOrientationDevelopmentDecisionError,
    GlobalOrientationDevelopmentScoredCaseComparisonV1,
)
from betelgeuze_engine_v2.benchmark.global_orientation_development_metrics import (
    GlobalOrientationDevelopmentArmMetricsV1,
)
from betelgeuze_engine_v2.benchmark.source_paired_clearance_activation import (
    SourcePairedClearanceCaseSourceReceiptV1,
)
from betelgeuze_engine_v2.docking import (
    ScorerBackend,
    ScorerBackendOptions,
    ScorerBackendReceipt,
    build_element_aware_authenticated_known_pocket_docking_problem,
    derive_scorer_v1_context,
)


_ACTIVATION_FIXTURES = runpy.run_path(
    str(Path(__file__).with_name("test_source_paired_clearance_activation.py"))
)
_ACTIVATION_EVIDENCE_FIXTURES = runpy.run_path(
    str(
        Path(__file__).with_name(
            "test_source_paired_clearance_activation_evidence.py"
        )
    )
)
_GLOBAL_ORIENTATION_FIXTURES = runpy.run_path(
    str(
        Path(__file__).with_name(
            "test_engine_v2_global_orientation_development_contracts.py"
        )
    )
)
_experimental_lineage = _GLOBAL_ORIENTATION_FIXTURES["_lineage"]
_observation = _GLOBAL_ORIENTATION_FIXTURES["_observation"]


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode("ascii")).hexdigest()


def _with_zero_charges(system):
    return replace(
        system,
        atoms=tuple(replace(atom, partial_charge_e=0.0) for atom in system.atoms),
    )


@pytest.fixture(scope="module")
def exact_comparison() -> GlobalOrientationDevelopmentScoredCaseComparisonV1:
    fixture = _ACTIVATION_FIXTURES["_fixture"]
    original_receptor = _ACTIVATION_FIXTURES["_receptor"]
    original_ligand = _ACTIVATION_FIXTURES["_ligand"]
    fixture.__globals__["_receptor"] = lambda *, separated=False: _with_zero_charges(
        original_receptor(separated=separated)
    )
    fixture.__globals__["_ligand"] = lambda: _with_zero_charges(original_ligand())
    proposals, currents, snapshots, proposal_receipt = fixture(
        permissive_selection_window=True,
        return_all=True,
    )
    current_v7_lineage = _ACTIVATION_EVIDENCE_FIXTURES[
        "_current_v7_lineage"
    ](proposal_receipt, proposals, currents, snapshots)
    receptor = fixture.__globals__["_receptor"](separated=True)
    ligand = fixture.__globals__["_ligand"]()
    authenticated = build_element_aware_authenticated_known_pocket_docking_problem(
        receptor,
        ligand,
        _ACTIVATION_FIXTURES["_pocket"](),
    )
    case_id = "5SD5_HWI"
    authority = {
        "allocation_receipt_sha256": proposal_receipt.allocation.allocation_sha256,
        "authenticated_input_receipt_sha256": authenticated.input_receipt_sha256,
        "current_v7_candidate_lineage_sha256": (
            current_v7_lineage.lineage_identity_sha256
        ),
        "input_artifact_set_sha256": _digest("decision-input-set"),
        "native_pose_artifact_sha256": _digest("decision-native"),
        "receptor_artifact_sha256": _digest("decision-receptor"),
        "source_case_member_path": f"receipts/engine_v2/{case_id}.json",
        "source_case_member_receipt_sha256": _digest("decision-member-receipt"),
        "source_case_member_sha256": _digest("decision-member"),
        "source_proposal_receipt_sha256": proposal_receipt.receipt_sha256,
    }
    old_authority = activation_module._FROZEN_CASE_SOURCE_AUTHORITY_BY_CASE
    old_lookup = activation_module._frozen_case_source_authority
    activation_module._FROZEN_CASE_SOURCE_AUTHORITY_BY_CASE = {case_id: authority}
    activation_module._frozen_case_source_authority = {case_id: authority}.get
    try:
        historical = SourcePairedClearanceCaseSourceReceiptV1(
            case_id=case_id,
            problem_fingerprint_sha256=authenticated.problem.fingerprint_sha256,
            **authority,
        )
        receptor_coordinates = tuple(
            tuple(float(value) for value in row)
            for row in receptor.coordinates[0].tolist()
        )
        ligand_coordinates = tuple(
            tuple(float(value) for value in row)
            for row in ligand.coordinates[0].tolist()
        )
        pocket_center = tuple(
            float(value)
            for value in authenticated.pocket.center.detach().cpu().tolist()
        )
        pocket_normal = (0.0, 0.0, 1.0)
        pocket_radius = authenticated.pocket.radius_angstrom
        scorer_context = derive_scorer_v1_context(authenticated, receptor, ligand)
        extension = _digest("decision-extension")
        backend_options = ScorerBackendOptions(thread_count=1, max_batch_size=64)
        backend = ScorerBackendReceipt(
            backend=ScorerBackend.RUST_CPU_REQUIRED,
            backend_version="decision-unit-native-v1",
            implementation_source_sha256=(
                derive_global_orientation_scorer_implementation_manifest_sha256()
            ),
            options_fingerprint_sha256=backend_options.fingerprint_sha256,
            extension_sha256=extension,
            cargo_lock_sha256=_digest("decision-cargo-lock"),
            rustc_version="rustc decision unit",
            target_triple="decision-unit-target",
        )
        source = GlobalOrientationDevelopmentCaseSourceReceiptV1(
            case_id=case_id,
            historical_case_source=historical,
            authenticated_problem=authenticated,
            receptor_system=receptor,
            ligand_system=ligand,
            scorer_context=scorer_context,
            source_case_member_receipt_sha256=(
                historical.source_case_member_receipt_sha256
            ),
            authenticated_input_receipt_sha256=(
                historical.authenticated_input_receipt_sha256
            ),
            receptor_coordinates=receptor_coordinates,
            receptor_coordinate_sha256=(
                derive_global_orientation_source_coordinates_sha256(
                    receptor_coordinates
                )
            ),
            ligand_coordinates=ligand_coordinates,
            ligand_coordinate_sha256=(
                derive_global_orientation_source_coordinates_sha256(
                    ligand_coordinates
                )
            ),
            ligand_topology_sha256=canonical_topology_sha256(ligand),
            pocket_declaration_sha256=(
                derive_global_orientation_pocket_declaration_sha256(
                    case_id=case_id,
                    historical_case_source_receipt_sha256=historical.receipt_sha256,
                    pocket_center=pocket_center,
                    pocket_normal=pocket_normal,
                    pocket_radius_angstrom=pocket_radius,
                )
            ),
            pocket_center=pocket_center,
            pocket_normal=pocket_normal,
            pocket_radius_angstrom=pocket_radius,
            pose_validity_config_fingerprint_sha256=(
                derive_global_orientation_pose_validity_config_fingerprint(
                    pocket_radius
                )
            ),
            preparation_policy_sha256=authenticated.authority_policy_sha256,
            evaluation_pipeline_sha256=(
                GLOBAL_ORIENTATION_EXPECTED_EVALUATION_PIPELINE_SHA256
            ),
            scorer_backend_receipt=backend,
            scorer_native_extension_sha256=extension,
            scorer_backend_receipt_sha256=backend.receipt_sha256,
            receptor_surface_atom_indices=authenticated.receptor_atom_indices,
        )
        source_receipt_sha256 = source.receipt_sha256
        baseline_slots = tuple(
            GlobalOrientationDevelopmentLineageSlotV1(
                case_source_receipt_sha256=source_receipt_sha256,
                arm_id="baseline_current_v7",
                proposal_index=proposal.proposal_index,
                candidate_id=proposal.candidate_id,
                generation_status="generated",
                proposal_fingerprint_sha256=proposal.fingerprint_sha256,
                coordinate_sha256=proposal.coordinate_fingerprint_sha256,
                generation_receipt_sha256=current_v7_lineage.receipt_sha256,
                failure_code=None,
            )
            for proposal in current_v7_lineage.current_v7_proposals
        )
        baseline_lineage = GlobalOrientationDevelopmentArmLineageReceiptV1(
            case_source=source,
            arm_id="baseline_current_v7",
            arm_authority_sha256=current_v7_lineage.lineage_identity_sha256,
            arm_authority_receipt=current_v7_lineage,
            slots=baseline_slots,
        )
        experimental_lineage = _experimental_lineage(source)

        def metrics(lineage) -> GlobalOrientationDevelopmentArmMetricsV1:
            observations = []
            for slot in lineage.slots:
                observation = _observation(slot, source)
                evidence = observation.candidate_evidence
                if evidence is not None and lineage.arm_id == "baseline_current_v7":
                    evidence = replace(
                        evidence,
                        source_proposal_fingerprint_sha256=(
                            lineage.arm_authority_receipt.source_proposal_fingerprint_sha256(
                                observation.proposal_index
                            )
                        ),
                    )
                    observation = replace(observation, candidate_evidence=evidence)
                observations.append(observation)
            return GlobalOrientationDevelopmentArmMetricsV1(
                GlobalOrientationDevelopmentArmObservationsV1(
                    lineage=lineage,
                    observations=tuple(observations),
                )
            )

        return GlobalOrientationDevelopmentScoredCaseComparisonV1(
            baseline_metrics=metrics(baseline_lineage),
            experimental_metrics=metrics(experimental_lineage),
        )
    finally:
        activation_module._FROZEN_CASE_SOURCE_AUTHORITY_BY_CASE = old_authority
        activation_module._frozen_case_source_authority = old_lookup


def _decision_rows(
    *,
    recovered=("5SD5_HWI", "5SIS_JSM"),
    incomplete: str | None = None,
    regression: bool = False,
    baseline_invalid=GLOBAL_ORIENTATION_DEVELOPMENT_SCORED_CASE_IDS[:-1],
    experimental_invalid=(
        "6M2B_EZO",
        "6TW5_9M2",
        "6TW7_NZB",
        "6VTA_AKN",
        "6WTN_RXT",
    ),
) -> dict[str, dict[str, object]]:
    rows = {}
    for case_id in GLOBAL_ORIENTATION_DEVELOPMENT_SCORED_CASE_IDS:
        complete = case_id != incomplete
        baseline_recovered = case_id == "6T88_MWQ"
        experimental_recovered = baseline_recovered or case_id in recovered
        experimental_success = experimental_recovered and not (
            regression and case_id == "6T88_MWQ"
        )
        rows[case_id] = {
            "decision_evidence_complete": complete,
            "baseline_valid_proposal_oracle_success": (
                baseline_recovered if complete else None
            ),
            "experimental_valid_proposal_oracle_success": (
                experimental_recovered if complete else None
            ),
            "new_valid_proposal_oracle_recovery": bool(
                complete and not baseline_recovered and experimental_recovered
            ),
            "baseline_selected_top1_valid": (
                case_id not in baseline_invalid if complete else None
            ),
            "experimental_selected_top1_valid": (
                case_id not in experimental_invalid if complete else None
            ),
            "baseline_selected_top1_invalid_or_absent": bool(
                complete and case_id in baseline_invalid
            ),
            "experimental_selected_top1_invalid_or_absent": bool(
                complete and case_id in experimental_invalid
            ),
            "baseline_selected_top1_success": (
                baseline_recovered if complete else None
            ),
            "experimental_selected_top1_success": (
                experimental_success if complete else None
            ),
        }
    return rows


def _evaluate(rows):
    return decision_module._evaluate_decision_rows(
        rows,
        complete_source_or_preparation_failure_receipts=True,
        identical_denominators=True,
        common_sources=True,
    )


def test_exact_case_comparison_owns_both_full_arm_receipts(exact_comparison) -> None:
    document = exact_comparison.to_dict()

    assert document["schema_id"] == (
        GLOBAL_ORIENTATION_DEVELOPMENT_SCORED_CASE_COMPARISON_SCHEMA_ID
    )
    assert document["case_id"] == "5SD5_HWI"
    assert document["baseline_metrics"]["arm_observations"]
    assert document["experimental_metrics"]["arm_observations"]
    assert document["decision_inputs_rederived_from_exact_arm_receipts"] is True
    assert document["go_receipt_emission_authorized"] is False
    assert document["product_execution_authorized"] is False
    assert document["public_or_scientific_claim_authorized"] is False
    assert len(exact_comparison.receipt_sha256) == 64


def test_cohort_wrapper_rejects_partial_roster_and_summary_substitutes(
    exact_comparison,
) -> None:
    failure = GlobalOrientationDevelopmentPreparationFailureReceiptV1(
        historical_authority=GlobalOrientationDevelopmentHistoricalFailureAuthorityV1(),
        failure_code="unsupported_large_ring_system",
    )
    with pytest.raises(
        GlobalOrientationDevelopmentDecisionError,
        match="exact ordered eight scored cases",
    ):
        GlobalOrientationDevelopmentCohortDecisionV1(
            scored_case_comparisons=(exact_comparison,),
            preparation_failure=failure,
        )
    with pytest.raises(TypeError, match="exact per-arm metrics"):
        GlobalOrientationDevelopmentScoredCaseComparisonV1(
            baseline_metrics=exact_comparison.baseline_metrics.to_dict(),
            experimental_metrics=exact_comparison.experimental_metrics,
        )


def test_cohort_wrapper_retains_no_authority_even_when_structurally_complete(
    exact_comparison,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        decision_module,
        "GLOBAL_ORIENTATION_DEVELOPMENT_SCORED_CASE_IDS",
        ("5SD5_HWI",),
    )
    monkeypatch.setattr(
        decision_module,
        "GLOBAL_ORIENTATION_DEVELOPMENT_BASELINE_RECOVERED_CASE_ID",
        "5SD5_HWI",
    )
    monkeypatch.setattr(
        decision_module,
        "GLOBAL_ORIENTATION_DEVELOPMENT_PREVIOUSLY_UNCOVERED_CASE_IDS",
        (),
    )
    receipt = GlobalOrientationDevelopmentCohortDecisionV1(
        scored_case_comparisons=(exact_comparison,),
        preparation_failure=GlobalOrientationDevelopmentPreparationFailureReceiptV1(
            historical_authority=(
                GlobalOrientationDevelopmentHistoricalFailureAuthorityV1()
            ),
            failure_code="unsupported_large_ring_system",
        ),
    )
    document = receipt.to_dict()

    assert document["schema_id"] == (
        GLOBAL_ORIENTATION_DEVELOPMENT_COHORT_DECISION_SCHEMA_ID
    )
    assert document["decision_evaluator_implemented"] is True
    assert document["go_receipt_emission_authorized"] is False
    assert document["historical_development_execution_authorized"] is False
    assert document["fresh_holdout_execution_authorized"] is False
    assert document["stage0_admission_authority"] is False
    assert document["profile_promotion_authority"] is False
    assert document["product_execution_authorized"] is False
    assert document["customer_pose_emission_authorized"] is False
    assert document["public_or_scientific_claim_authorized"] is False


def test_exact_derived_rows_produce_only_protocol_go() -> None:
    decision = _evaluate(_decision_rows())

    assert decision["verdict"] == (
        "go_permit_separate_development_followup_review"
    )
    assert decision["new_valid_proposal_oracle_recovery_case_ids"] == [
        "5SD5_HWI",
        "5SIS_JSM",
    ]
    assert all(decision["invariants"].values())
    assert all(decision["go_criteria"].values())
    assert not any(decision["hard_no_go"].values())
    assert decision["go_effect"] == (
        "permit_separate_review_of_global_orientation_development_followup_only"
    )


def test_zero_recovery_incomplete_evidence_and_regression_fail_closed() -> None:
    zero = _evaluate(_decision_rows(recovered=()))
    assert zero["hard_no_go"][
        "zero_new_previously_uncovered_valid_proposal_recoveries"
    ] is True
    assert zero["verdict"] == "no_go_retain_synthetic_only_global_orientation"

    incomplete = _evaluate(_decision_rows(incomplete="5SD5_HWI"))
    assert incomplete["hard_no_go"][
        "evaluator_or_required_private_evidence_absent"
    ] is True
    assert incomplete["invariants"][
        "complete_source_and_observation_rederivation"
    ] is False

    regression = _evaluate(_decision_rows(regression=True))
    assert regression["hard_no_go"]["baseline_recovered_case_regression"] is True
    assert regression["invariants"][
        "no_baseline_recovered_case_regression"
    ] is False


def test_invalid_selected_top1_increase_and_row_drift_fail_closed() -> None:
    decision = _evaluate(
        _decision_rows(
            baseline_invalid=(),
            experimental_invalid=("5SD5_HWI",),
        )
    )
    assert decision["go_criteria"][
        "no_increase_in_invalid_selected_top1_count"
    ] is False
    assert decision["verdict"] == "no_go_retain_synthetic_only_global_orientation"

    missing_failure_source = decision_module._evaluate_decision_rows(
        _decision_rows(),
        complete_source_or_preparation_failure_receipts=False,
        identical_denominators=True,
        common_sources=True,
    )
    assert missing_failure_source["invariants"][
        "complete_source_or_preparation_failure_receipts_for_all_nine_cases"
    ] is False
    assert missing_failure_source["hard_no_go"]["required_invariant_failed"] is True

    drifted = _decision_rows()
    drifted["5SD5_HWI"]["decision_evidence_complete"] = 1
    with pytest.raises(
        GlobalOrientationDevelopmentDecisionError,
        match="must be a boolean",
    ):
        _evaluate(drifted)
