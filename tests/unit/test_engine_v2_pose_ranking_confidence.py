from __future__ import annotations

from dataclasses import replace
import hashlib

import pytest


pytest.importorskip("torch")

from betelgeuze_engine_v2.docking import (  # noqa: E402
    POSE_RANKING_CONFIDENCE_EVALUATION_SCHEMA_ID,
    POSE_RANKING_MARGIN_CONFIDENCE_SIGNAL_ID,
    PoseRankingCalibrationConfig,
    PoseRankingCalibrationPartition,
    PoseRankingCalibrationRow,
    PoseRankingConfidenceError,
    PoseRankingConfidenceEvaluationConfig,
    PoseRankingEvaluationConfig,
    audit_pose_ranking_leakage,
    evaluate_pose_ranking_calibration,
    evaluate_pose_ranking_confidence,
    fit_pose_ranking_calibration,
)


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _row(
    split: str,
    case_id: str,
    pose_id: str,
    target_id: str,
    family: str,
    physics: float | None,
    clash: float | None,
    native_like: bool | None,
    *,
    status: str = "success",
) -> PoseRankingCalibrationRow:
    return PoseRankingCalibrationRow(
        suite_id="synthetic-confidence-contract-suite",
        case_id=case_id,
        pose_id=pose_id,
        target_id=target_id,
        target_family=family,
        split_role=split,
        scoring_protocol_sha256=_sha("scoring-protocol:v1"),
        preparation_profile_sha256=_sha("preparation-profile:v1"),
        receptor_sha256=_sha(f"receptor:{target_id}"),
        ligand_sha256=_sha(f"ligand:{case_id}"),
        scaffold_sha256=_sha(f"scaffold:{case_id}"),
        pose_sha256=_sha(f"pose:{case_id}:{pose_id}"),
        status=status,
        term_values=(
            {}
            if status == "failure"
            else {"physics": float(physics), "clash": float(clash)}
        ),
        native_like=None if status == "failure" else native_like,
        error_code="synthetic_scoring_failure" if status == "failure" else "",
    )


def _ranking_report():
    fit = PoseRankingCalibrationPartition(
        dataset_id="synthetic-confidence-fit",
        dataset_version="1.0.0",
        split_role="fit",
        rows=(
            _row("fit", "fit-a", "native", "fit-target-a", "kinase", 0.0, 0.0, True),
            _row("fit", "fit-a", "decoy", "fit-target-a", "kinase", 2.0, 1.0, False),
            _row("fit", "fit-b", "native", "fit-target-b", "gpcr", 0.0, 0.0, True),
            _row("fit", "fit-b", "decoy", "fit-target-b", "gpcr", 2.0, 1.0, False),
        ),
    )
    evaluation = PoseRankingCalibrationPartition(
        dataset_id="synthetic-confidence-holdout",
        dataset_version="1.0.0",
        split_role="test",
        rows=(
            _row("test", "case-a", "native", "target-a", "kinase", 0.0, 0.0, True),
            _row("test", "case-a", "decoy", "target-a", "kinase", 2.0, 1.0, False),
            _row("test", "case-b", "native", "target-b", "kinase", 2.0, 1.0, True),
            _row("test", "case-b", "decoy", "target-b", "kinase", 0.0, 0.0, False),
            _row("test", "case-c", "a-native", "target-c", "gpcr", 1.0, 0.5, True),
            _row("test", "case-c", "b-decoy", "target-c", "gpcr", 1.0, 0.5, False),
            _row(
                "test",
                "case-d",
                "failed-a",
                "target-d",
                "gpcr",
                None,
                None,
                None,
                status="failure",
            ),
            _row(
                "test",
                "case-d",
                "failed-b",
                "target-d",
                "gpcr",
                None,
                None,
                None,
                status="failure",
            ),
            _row("test", "case-e", "only", "target-e", "gpcr", 0.5, 0.2, True),
        ),
    )
    audit = audit_pose_ranking_leakage(fit, evaluation)
    model = fit_pose_ranking_calibration(
        fit,
        audit,
        PoseRankingCalibrationConfig(
            term_ids=("physics", "clash"),
            learning_rate=0.1,
            l2_penalty=0.0,
            iterations=200,
            trace_interval=20,
            max_training_pairs=100,
        ),
    )
    return evaluate_pose_ranking_calibration(
        model,
        evaluation,
        audit,
        config=PoseRankingEvaluationConfig(
            confidence_level=0.95,
            bootstrap_samples=50,
            seed=31,
        ),
    )


def test_confidence_evaluation_retains_failures_and_reports_selective_risk() -> None:
    ranking = _ranking_report()
    config = PoseRankingConfidenceEvaluationConfig(
        confidence_threshold=0.51,
        bin_count=5,
        selective_coverage_targets=(0.2, 0.4, 0.6, 0.8, 1.0),
        confidence_level=0.95,
        bootstrap_samples=100,
        seed=73,
    )
    first = evaluate_pose_ranking_confidence(ranking, config=config)
    second = evaluate_pose_ranking_confidence(ranking, config=config)

    assert first.fingerprint_sha256 == second.fingerprint_sha256
    assert first.schema_id == POSE_RANKING_CONFIDENCE_EVALUATION_SCHEMA_ID
    assert first.pose_ranking_evaluation_sha256 == ranking.fingerprint_sha256
    assert not first.probability_calibrated
    assert not first.claim_safe
    assert first.blockers == (
        "raw_pairwise_margin_is_not_disjoint_probability_calibrator",
        "confidence_acceptance_threshold_not_independently_reviewed",
        "public_dataset_result_not_established",
        "independent_external_rerun_missing",
        "scientific_review_missing",
    )

    cases = {case.case_id: case for case in first.cases}
    assert cases["case-a"].decision == "accepted"
    assert cases["case-b"].decision == "accepted"
    assert cases["case-a"].confidence == pytest.approx(cases["case-b"].confidence)
    assert cases["case-c"].confidence == pytest.approx(0.5)
    assert cases["case-c"].decision == "abstained"
    assert cases["case-c"].abstention_reason == "below_confidence_threshold"
    assert cases["case-d"].confidence is None
    assert cases["case-d"].failed_pose_count == 2
    assert cases["case-d"].abstention_reason == (
        "insufficient_successful_poses_for_margin"
    )
    assert cases["case-e"].confidence is None
    assert cases["case-e"].successful_pose_count == 1

    overall = first.overall
    assert overall.all_case_denominator == 5
    assert overall.all_pose_denominator == 9
    assert overall.failed_pose_count == 2
    assert overall.confidence_available_case_count == 3
    assert overall.confidence_unavailable_case_count == 2
    assert overall.accepted_case_count == 2
    assert overall.abstained_case_count == 3
    assert overall.positive_confidence_outcome_count == 2
    assert overall.negative_confidence_outcome_count == 1
    assert sum(row.row_count for row in overall.reliability_bins) == 3
    assert len(overall.reliability_bins) == 5

    metrics = {metric.metric_id: metric for metric in overall.metrics}
    assert metrics["brier_score"].available
    assert metrics["brier_score"].contributing_case_count == 3
    assert metrics["expected_calibration_error"].available
    assert metrics["confidence_available_case_coverage"].value == pytest.approx(0.6)
    assert metrics["threshold_accepted_case_coverage"].value == pytest.approx(0.4)
    assert metrics["threshold_selective_risk"].value == pytest.approx(0.5)
    assert metrics["threshold_selective_risk"].contributing_case_count == 2

    curve = {point.target_coverage: point for point in overall.selective_risk_curve}
    assert curve[0.2].achieved_coverage == pytest.approx(0.4)
    assert curve[0.2].selected_case_ids == ("case-a", "case-b")
    assert curve[0.2].risk.value == pytest.approx(0.5)
    assert curve[0.4].selected_case_ids == ("case-a", "case-b")
    assert curve[0.6].selected_case_ids == ("case-a", "case-b", "case-c")
    assert curve[0.6].risk.value == pytest.approx(1.0 / 3.0)
    assert curve[0.8].risk.value is None
    assert curve[1.0].risk.value is None
    assert "target_coverage_exceeds_confidence_available_coverage" in (
        curve[1.0].risk.blockers
    )
    assert "selective_risk_target_coverage_unavailable" in overall.blockers

    families = {scope.target_family: scope for scope in first.families}
    assert families["kinase"].all_case_denominator == 2
    assert families["kinase"].accepted_case_count == 2
    assert families["gpcr"].all_case_denominator == 3
    assert families["gpcr"].confidence_available_case_count == 1
    assert families["gpcr"].failed_pose_count == 2
    assert "negative_confidence_outcome_missing" in families["gpcr"].blockers

    document = first.to_dict()
    assert document["confidence_signal"]["signal_id"] == (
        POSE_RANKING_MARGIN_CONFIDENCE_SIGNAL_ID
    )
    assert document["confidence_signal"]["probability_calibrated"] is False
    assert document["public_benchmark_result_established"] is False
    assert document["overall"]["all_case_denominator"] == 5


def test_confidence_contract_rejects_threshold_and_report_tampering() -> None:
    ranking = _ranking_report()
    with pytest.raises(PoseRankingConfidenceError, match="confidence_threshold"):
        PoseRankingConfidenceEvaluationConfig(confidence_threshold=0.49)
    with pytest.raises(PoseRankingConfidenceError, match="coverage_targets"):
        PoseRankingConfidenceEvaluationConfig(
            selective_coverage_targets=(0.5, 0.25)
        )

    config = PoseRankingConfidenceEvaluationConfig(
        confidence_threshold=0.51,
        bin_count=5,
        selective_coverage_targets=(0.5, 1.0),
        bootstrap_samples=20,
        seed=17,
    )
    report = evaluate_pose_ranking_confidence(ranking, config=config)
    tie_case = next(case for case in report.cases if case.case_id == "case-c")
    tampered_case = replace(
        tie_case,
        decision="accepted",
        abstention_reason="",
    )
    tampered_cases = tuple(
        tampered_case if case.case_id == "case-c" else case
        for case in report.cases
    )
    with pytest.raises(PoseRankingConfidenceError, match="scope evidence disagrees"):
        replace(report, cases=tampered_cases)
    brier = report.overall.metrics[0]
    tampered_brier = replace(brier, value=0.123456789)
    tampered_overall = replace(
        report.overall,
        metrics=(tampered_brier, *report.overall.metrics[1:]),
    )
    with pytest.raises(PoseRankingConfidenceError, match="metric values disagree"):
        replace(report, overall=tampered_overall)
    with pytest.raises(PoseRankingConfidenceError, match="unsupported.*schema"):
        replace(report, schema_id="betelgeuze.invalid/1.0.0")
    with pytest.raises(PoseRankingConfidenceError, match="ranking_report"):
        evaluate_pose_ranking_confidence(object())  # type: ignore[arg-type]


def test_confidence_symbols_are_public_docking_exports() -> None:
    from betelgeuze_engine_v2 import docking
    from betelgeuze_engine_v2.docking.confidence import __all__ as exports

    assert set(exports) <= set(docking.__all__)
