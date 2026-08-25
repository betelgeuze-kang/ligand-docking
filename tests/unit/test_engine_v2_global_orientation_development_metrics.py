from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import runpy

import pytest

from betelgeuze_engine_v2.benchmark.global_orientation_development_contracts import (
    GlobalOrientationDevelopmentArmObservationsV1,
    GlobalOrientationDevelopmentPartialCandidateEvidenceV1,
)
from betelgeuze_engine_v2.benchmark.global_orientation_development_metrics import (
    GLOBAL_ORIENTATION_DEVELOPMENT_ARM_METRICS_SCHEMA_ID,
    GlobalOrientationDevelopmentArmMetricsV1,
    GlobalOrientationDevelopmentMetricsError,
)


_FIXTURES = runpy.run_path(
    str(
        Path(__file__).with_name(
            "test_engine_v2_global_orientation_development_contracts.py"
        )
    )
)
_source = _FIXTURES["_source"]
_lineage = _FIXTURES["_lineage"]
_observation = _FIXTURES["_observation"]


def _arm() -> GlobalOrientationDevelopmentArmObservationsV1:
    source = _source()
    lineage = _lineage(source)
    return GlobalOrientationDevelopmentArmObservationsV1(
        lineage=lineage,
        observations=tuple(_observation(slot, source) for slot in lineage.slots),
    )


def test_arm_metrics_rederive_every_declared_metric_from_exact_receipt() -> None:
    arm = _arm()
    metrics = GlobalOrientationDevelopmentArmMetricsV1(arm)
    document = metrics.to_dict()

    generated = tuple(
        row for row in arm.observations if row.generation_status == "generated"
    )
    expected_selected = min(
        generated,
        key=lambda row: (
            row.candidate_evidence.scorer_terms.total_score,
            row.proposal_index,
        ),
    )
    expected_oracle = min(
        row.candidate_evidence.rmsd.rmsd_angstrom for row in generated
    )

    assert document["schema_id"] == (
        GLOBAL_ORIENTATION_DEVELOPMENT_ARM_METRICS_SCHEMA_ID
    )
    assert document["candidate_denominator"] == 64
    assert document["generated_candidate_count"] == len(generated)
    assert document["accepted_candidate_count"] == len(generated)
    assert document["rejected_candidate_count"] == 64 - len(generated)
    assert document["scored_candidate_count"] == len(generated)
    assert document["score_coverage_complete"] is True
    assert document["validity_coverage_complete"] is True
    assert document["rmsd_coverage_complete"] is True
    assert document["metric_evidence_complete"] is True
    assert document["proposal_oracle_rmsd_angstrom_binary64_hex"] == (
        expected_oracle.hex()
    )
    assert document["valid_proposal_oracle_rmsd_angstrom_binary64_hex"] == (
        expected_oracle.hex()
    )
    assert document["selected_top1_index"] == expected_selected.proposal_index
    assert document["selected_top1_valid"] is True
    assert document["failure_class"] == "success"
    assert document["arm_observations"] == arm.to_dict()
    assert len(document["observation_receipt_sha256s"]) == 64
    assert document["metrics_rederived_from_exact_observations"] is True
    assert document["decision_evaluator_implemented"] is False
    assert document["go_receipt_emission_authorized"] is False
    assert document["fresh_holdout_execution_authorized"] is False
    assert document["product_execution_authorized"] is False
    assert len(metrics.receipt_sha256) == 64


def test_partial_stage_evidence_remains_visible_and_marks_metrics_incomplete() -> None:
    arm = _arm()
    target = min(
        (row for row in arm.observations if row.candidate_evidence is not None),
        key=lambda row: (
            row.candidate_evidence.scorer_terms.total_score,
            row.proposal_index,
        ),
    )
    complete = target.candidate_evidence
    assert complete is not None
    partial = GlobalOrientationDevelopmentPartialCandidateEvidenceV1(
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
    changed = replace(
        target,
        candidate_evidence=None,
        partial_evidence=partial,
        validity_status="not_evaluated",
        rmsd_status="not_evaluated",
        failure_code="validity_evaluator_failed",
    )
    observations = tuple(
        changed if row.proposal_index == changed.proposal_index else row
        for row in arm.observations
    )
    partial_arm = GlobalOrientationDevelopmentArmObservationsV1(
        lineage=arm.lineage,
        observations=observations,
    )

    document = GlobalOrientationDevelopmentArmMetricsV1(partial_arm).to_dict()

    assert document["metric_evidence_complete"] is False
    assert document["score_coverage_complete"] is True
    assert document["validity_coverage_complete"] is False
    assert document["rmsd_coverage_complete"] is False
    assert document["proposal_oracle_index"] is None
    assert document["proposal_oracle_rmsd_angstrom_binary64_hex"] is None
    assert document["proposal_oracle_success"] is None
    assert document["valid_proposal_oracle_index"] is None
    assert document["valid_proposal_oracle_rmsd_angstrom_binary64_hex"] is None
    assert document["valid_proposal_oracle_success"] is None
    assert all(
        row["proposal_oracle_rmsd_angstrom_binary64_hex"] is None
        and row["valid_proposal_oracle_rmsd_angstrom_binary64_hex"] is None
        for row in document["ranked_oracles"]
    )
    assert document["selected_top1_index"] == changed.proposal_index
    assert document["selected_top1_valid"] is None
    assert document["selected_top1_success"] is None
    assert document["failure_class"] is None
    assert document["scored_candidate_count"] == document["generated_candidate_count"]
    assert document["rmsd_evaluated_candidate_count"] == (
        document["generated_candidate_count"] - 1
    )
    assert document["failure_code_counts"] == {
        "receptor_clash": 3,
        "validity_evaluator_failed": 1,
    }
    assert (
        document["arm_observations"]["observations"][changed.proposal_index][
            "partial_evidence"
        ]
        is not None
    )


def test_missing_score_withholds_selection_and_all_oracle_metrics() -> None:
    arm = _arm()
    target = max(
        (row for row in arm.observations if row.candidate_evidence is not None),
        key=lambda row: row.candidate_evidence.raw_score_rank,
    )
    changed = replace(
        target,
        candidate_evidence=None,
        score_status="unscored",
        validity_status="not_evaluated",
        rmsd_status="not_evaluated",
        failure_code="scorer_failed",
    )
    partial_arm = GlobalOrientationDevelopmentArmObservationsV1(
        lineage=arm.lineage,
        observations=tuple(
            changed if row.proposal_index == changed.proposal_index else row
            for row in arm.observations
        ),
    )

    document = GlobalOrientationDevelopmentArmMetricsV1(partial_arm).to_dict()

    assert document["metric_evidence_complete"] is False
    assert document["score_coverage_complete"] is False
    assert document["validity_coverage_complete"] is False
    assert document["rmsd_coverage_complete"] is False
    for key in (
        "proposal_oracle_index",
        "proposal_oracle_rmsd_angstrom_binary64_hex",
        "proposal_oracle_success",
        "valid_proposal_oracle_index",
        "valid_proposal_oracle_rmsd_angstrom_binary64_hex",
        "valid_proposal_oracle_success",
        "selected_top1_index",
        "selected_top1_score_binary64_hex",
        "selected_top1_rmsd_angstrom_binary64_hex",
        "selected_top1_valid",
        "selected_top1_success",
        "selection_regret_angstrom_binary64_hex",
        "failure_class",
    ):
        assert document[key] is None
    assert all(
        row["proposal_oracle_rmsd_angstrom_binary64_hex"] is None
        and row["valid_proposal_oracle_rmsd_angstrom_binary64_hex"] is None
        for row in document["ranked_oracles"]
    )
    assert document["failure_code_counts"] == {
        "receptor_clash": 3,
        "scorer_failed": 1,
    }


def test_arm_metrics_reject_unfrozen_threshold_top_k_and_summary_substitutes() -> None:
    arm = _arm()
    with pytest.raises(
        GlobalOrientationDevelopmentMetricsError,
        match="RMSD threshold",
    ):
        GlobalOrientationDevelopmentArmMetricsV1(
            arm,
            rmsd_threshold_angstrom=2.5,
        )
    with pytest.raises(
        GlobalOrientationDevelopmentMetricsError,
        match="top_k",
    ):
        GlobalOrientationDevelopmentArmMetricsV1(arm, top_k=(1, 10))
    with pytest.raises(TypeError, match="exact arm receipt"):
        GlobalOrientationDevelopmentArmMetricsV1(arm.to_dict())  # type: ignore[arg-type]
