from __future__ import annotations

from dataclasses import replace
import hashlib

import pytest


pytest.importorskip("torch")

from betelgeuze_engine_v2.docking import (  # noqa: E402
    POSE_RANKING_EVALUATION_SCHEMA_ID,
    POSE_RANKING_LEGACY_EVALUATION_SCHEMA_ID_V1,
    DockingScoreBreakdown,
    DockingScoreDescriptor,
    DockingScoreTerm,
    PoseRankingCalibrationConfig,
    PoseRankingCalibrationError,
    PoseRankingCalibrationPartition,
    PoseRankingCalibrationRow,
    PoseRankingEvaluationConfig,
    PoseRankingLeakagePolicy,
    ScoreDirection,
    TrainingFitPoseRankingScorer,
    audit_pose_ranking_leakage,
    evaluate_pose_ranking_calibration,
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
        suite_id="synthetic-contract-suite",
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


def _fit_partition(*, include_failure: bool = False) -> PoseRankingCalibrationPartition:
    rows = [
        _row("fit", "fit-case-1", "native", "target-a", "kinase", 0.0, 0.0, True),
        _row("fit", "fit-case-1", "decoy", "target-a", "kinase", 2.0, 1.0, False),
        _row("fit", "fit-case-2", "native", "target-b", "gpcr", 0.2, 0.0, True),
        _row("fit", "fit-case-2", "decoy", "target-b", "gpcr", 3.0, 1.5, False),
    ]
    if include_failure:
        rows.append(
            _row(
                "fit",
                "fit-case-2",
                "failed",
                "target-b",
                "gpcr",
                None,
                None,
                None,
                status="failure",
            )
        )
    return PoseRankingCalibrationPartition(
        dataset_id="synthetic-ranking",
        dataset_version="1.0.0",
        split_role="fit",
        rows=tuple(rows),
    )


def _evaluation_partition() -> PoseRankingCalibrationPartition:
    return PoseRankingCalibrationPartition(
        dataset_id="synthetic-ranking",
        dataset_version="1.0.0",
        split_role="test",
        rows=(
            _row(
                "test",
                "test-case-1",
                "native",
                "target-c",
                "kinase",
                0.1,
                0.0,
                True,
            ),
            _row(
                "test",
                "test-case-1",
                "decoy",
                "target-c",
                "kinase",
                2.5,
                1.0,
                False,
            ),
            _row(
                "test",
                "test-case-2",
                "failed-1",
                "target-d",
                "gpcr",
                None,
                None,
                None,
                status="failure",
            ),
            _row(
                "test",
                "test-case-2",
                "failed-2",
                "target-d",
                "gpcr",
                None,
                None,
                None,
                status="failure",
            ),
        ),
    )


def _config() -> PoseRankingCalibrationConfig:
    return PoseRankingCalibrationConfig(
        term_ids=("physics", "clash"),
        learning_rate=0.05,
        l2_penalty=1.0e-3,
        iterations=300,
        trace_interval=20,
        max_training_pairs=100,
    )


def test_deterministic_pairwise_fit_consumes_only_bound_fit_partition() -> None:
    fit = _fit_partition()
    evaluation = _evaluation_partition()
    audit = audit_pose_ranking_leakage(fit, evaluation)

    assert audit.passed
    assert audit.overlaps["target_family"] == ("gpcr", "kinase")
    assert "target_family_overlap" not in audit.blockers
    first = fit_pose_ranking_calibration(fit, audit, _config())
    second = fit_pose_ranking_calibration(fit, audit, _config())

    assert first.fingerprint_sha256 == second.fingerprint_sha256
    assert first.coefficients == pytest.approx(second.coefficients, abs=0.0)
    assert first.loss_trace[-1][1] < first.loss_trace[0][1]
    assert first.training_case_count == 2
    assert first.training_pair_count == 2
    assert first.score_terms({"physics": 0.0, "clash": 0.0}) < first.score_terms(
        {"physics": 3.0, "clash": 1.0}
    )
    assert not first.claim_safe
    assert first.to_dict()["holdout_validated"] is False


def test_training_fit_scorer_reweights_complete_terms_without_promotion() -> None:
    fit = _fit_partition()
    evaluation = _evaluation_partition()
    audit = audit_pose_ranking_leakage(fit, evaluation)
    model = fit_pose_ranking_calibration(fit, audit, _config())

    class _BaseScorer:
        scorer_id = "unit-base-scorer"
        scorer_version = "1.0.0"
        validated_for_docking_ranking = False
        config_fingerprint_sha256 = "a" * 64
        score_descriptor = DockingScoreDescriptor(
            score_id="unit_base_score",
            direction=ScoreDirection.MINIMIZE,
            unit="kcal/mol",
            semantics="unit_test_two_term_score",
            calibrated=False,
        )

        def score(self, proposal):
            del proposal
            return DockingScoreBreakdown(
                terms=(
                    DockingScoreTerm(
                        term_id="physics",
                        raw_value=0.25,
                        weight=1.0,
                        unit="kcal/mol",
                        semantics="unit_test_physics",
                        parameter_source_sha256="b" * 64,
                    ),
                    DockingScoreTerm(
                        term_id="clash",
                        raw_value=0.1,
                        weight=1.0,
                        unit="kcal/mol",
                        semantics="unit_test_clash",
                        parameter_source_sha256="c" * 64,
                    ),
                ),
                blockers=("base_uncalibrated",),
            )

    scorer = TrainingFitPoseRankingScorer(_BaseScorer(), model)
    breakdown = scorer.score(object())
    assert breakdown.total_score == pytest.approx(
        model.score_terms({"physics": 0.25, "clash": 0.1})
    )
    assert {term.unit for term in breakdown.terms} == {None}
    assert "training_fit_only_not_holdout_validated" in breakdown.blockers
    assert scorer.score_descriptor.calibrated is False
    assert scorer.validated_for_docking_ranking is False
    assert len(scorer.config_fingerprint_sha256) == 64


def test_required_identity_overlap_blocks_fit_and_family_policy_is_explicit() -> None:
    fit = _fit_partition()
    evaluation = _evaluation_partition()
    leaked_rows = list(evaluation.rows)
    leaked_rows[0] = replace(leaked_rows[0], target_id="target-a")
    leaked_rows[1] = replace(leaked_rows[1], target_id="target-a")
    leaked = replace(evaluation, rows=tuple(leaked_rows))
    audit = audit_pose_ranking_leakage(fit, leaked)
    assert not audit.passed
    assert "target_id_overlap" in audit.blockers
    with pytest.raises(PoseRankingCalibrationError, match="passing leakage"):
        fit_pose_ranking_calibration(fit, audit, _config())

    family_strict = audit_pose_ranking_leakage(
        fit,
        evaluation,
        policy=PoseRankingLeakagePolicy(require_family_disjoint=True),
    )
    assert not family_strict.passed
    assert family_strict.blockers == ("target_family_overlap",)

    mismatched_profile = replace(
        evaluation,
        rows=tuple(
            replace(row, preparation_profile_sha256=_sha("different-preparation"))
            for row in evaluation.rows
        ),
    )
    profile_audit = audit_pose_ranking_leakage(fit, mismatched_profile)
    assert not profile_audit.passed
    assert "preparation_profile_mismatch" in profile_audit.blockers


def test_evaluation_retains_failed_poses_in_all_case_and_family_denominators() -> None:
    fit = _fit_partition()
    evaluation = _evaluation_partition()
    audit = audit_pose_ranking_leakage(fit, evaluation)
    model = fit_pose_ranking_calibration(fit, audit, _config())
    evaluation_config = PoseRankingEvaluationConfig(
        confidence_level=0.95,
        bootstrap_samples=200,
        seed=17,
    )
    first = evaluate_pose_ranking_calibration(
        model,
        evaluation,
        audit,
        config=evaluation_config,
    )
    second = evaluate_pose_ranking_calibration(
        model,
        evaluation,
        audit,
        config=evaluation_config,
    )

    assert first.fingerprint_sha256 == second.fingerprint_sha256
    assert first.schema_id == POSE_RANKING_EVALUATION_SCHEMA_ID
    assert first.schema_id.endswith("/2.0.0")
    assert POSE_RANKING_LEGACY_EVALUATION_SCHEMA_ID_V1.endswith("/1.0.0")
    assert first.all_case_denominator == 2
    assert first.all_pose_denominator == 4
    by_metric = {metric.metric_id: metric for metric in first.overall_metrics}
    assert by_metric["top1_native_like_rate"].value == pytest.approx(0.5)
    assert by_metric["top5_native_like_rate"].value == pytest.approx(0.5)
    assert by_metric["scored_case_coverage"].value == pytest.approx(0.5)
    assert all(metric.all_case_denominator == 2 for metric in first.overall_metrics)
    assert len(first.overall_pose_metrics) == 1
    pose_metric = first.overall_pose_metrics[0]
    assert pose_metric.metric_id == "average_precision_pr_auc"
    assert pose_metric.value == pytest.approx(1.0)
    assert pose_metric.confidence_interval_low == pytest.approx(1.0)
    assert pose_metric.confidence_interval_high == pytest.approx(1.0)
    assert pose_metric.total_case_denominator == 2
    assert pose_metric.all_pose_denominator == 4
    assert pose_metric.successful_labeled_pose_count == 2
    assert pose_metric.positive_pose_count == 1
    assert pose_metric.negative_pose_count == 1
    assert pose_metric.failed_pose_count == 2
    assert pose_metric.successful_pose_coverage == pytest.approx(0.5)
    assert 0 < pose_metric.bootstrap_valid_sample_count <= 200
    assert "case_cluster_bootstrap_dropped_single_class_replicates" in (
        pose_metric.blockers
    )
    failed_case = next(case for case in first.cases if case.case_id == "test-case-2")
    assert failed_case.total_pose_count == 2
    assert failed_case.successful_pose_count == 0
    assert failed_case.failed_pose_count == 2
    assert failed_case.failed_pose_ids == ("failed-1", "failed-2")
    assert failed_case.failed_pose_error_codes == (
        "synthetic_scoring_failure",
        "synthetic_scoring_failure",
    )
    scored_case = next(case for case in first.cases if case.case_id == "test-case-1")
    assert scored_case.ranked_native_like == (True, False)
    assert len(scored_case.ranked_scores) == 2
    assert scored_case.ranked_scores[0] < scored_case.ranked_scores[1]
    with pytest.raises(PoseRankingCalibrationError, match="canonical order"):
        replace(scored_case, ranked_scores=tuple(reversed(scored_case.ranked_scores)))
    with pytest.raises(PoseRankingCalibrationError, match="Top-1"):
        replace(scored_case, top1_native_like=False)
    families = {row.target_family: row for row in first.family_metrics}
    assert families["kinase"].case_count == 1
    assert families["gpcr"].case_count == 1
    gpcr_top1 = next(
        metric
        for metric in families["gpcr"].metrics
        if metric.metric_id == "top1_native_like_rate"
    )
    assert gpcr_top1.value == 0.0
    assert gpcr_top1.all_case_denominator == 1
    kinase_pr_auc = families["kinase"].pose_metrics[0]
    assert kinase_pr_auc.value == pytest.approx(1.0)
    assert kinase_pr_auc.bootstrap_valid_sample_count == 200
    gpcr_pr_auc = families["gpcr"].pose_metrics[0]
    assert gpcr_pr_auc.value is None
    assert gpcr_pr_auc.confidence_interval_low is None
    assert gpcr_pr_auc.confidence_interval_high is None
    assert gpcr_pr_auc.all_pose_denominator == 2
    assert gpcr_pr_auc.failed_pose_count == 2
    assert gpcr_pr_auc.successful_pose_coverage == 0.0
    assert gpcr_pr_auc.blockers == (
        "positive_successful_pose_class_missing",
        "negative_successful_pose_class_missing",
    )
    serialized = first.to_dict()
    assert serialized["all_pose_denominator"] == 4
    assert serialized["overall_pose_metrics"][0]["available"] is True
    gpcr_serialized = next(
        row for row in serialized["family_metrics"] if row["target_family"] == "gpcr"
    )
    assert gpcr_serialized["pose_metrics"][0]["available"] is False
    assert "pose_ranking_confidence_calibration_missing" in serialized["blockers"]
    with pytest.raises(PoseRankingCalibrationError, match="unsupported.*schema"):
        replace(first, schema_id=POSE_RANKING_LEGACY_EVALUATION_SCHEMA_ID_V1)
    with pytest.raises(PoseRankingCalibrationError, match="case metrics disagree"):
        replace(first, overall_metrics=families["kinase"].metrics)
    with pytest.raises(PoseRankingCalibrationError, match="pose-level metric counts"):
        replace(
            first,
            overall_pose_metrics=(
                replace(pose_metric, total_case_denominator=1),
            ),
        )
    with pytest.raises(PoseRankingCalibrationError, match="dropped-replicate"):
        replace(
            pose_metric,
            bootstrap_valid_sample_count=pose_metric.bootstrap_requested_sample_count,
        )
    with pytest.raises(PoseRankingCalibrationError, match="internally inconsistent"):
        replace(gpcr_pr_auc, bootstrap_valid_sample_count=1)
    assert not first.claim_safe


def test_pose_pr_auc_is_tie_invariant_and_uses_case_cluster_bootstrap() -> None:
    fit = _fit_partition()
    values: list[float] = []
    fingerprints: list[str] = []
    for first_label, second_label in ((True, False), (False, True)):
        evaluation = PoseRankingCalibrationPartition(
            dataset_id="synthetic-ranking",
            dataset_version="1.0.0",
            split_role="test",
            rows=(
                _row(
                    "test",
                    "tie-case",
                    "pose-a",
                    "target-tie",
                    "kinase",
                    1.0,
                    0.5,
                    first_label,
                ),
                _row(
                    "test",
                    "tie-case",
                    "pose-b",
                    "target-tie",
                    "kinase",
                    1.0,
                    0.5,
                    second_label,
                ),
            ),
        )
        audit = audit_pose_ranking_leakage(fit, evaluation)
        model = fit_pose_ranking_calibration(fit, audit, _config())
        report = evaluate_pose_ranking_calibration(
            model,
            evaluation,
            audit,
            config=PoseRankingEvaluationConfig(
                confidence_level=0.95,
                bootstrap_samples=100,
                seed=29,
            ),
        )
        metric = report.overall_pose_metrics[0]
        assert metric.value == pytest.approx(0.5)
        assert metric.confidence_interval_low == pytest.approx(0.5)
        assert metric.confidence_interval_high == pytest.approx(0.5)
        assert metric.bootstrap_unit == "case"
        assert metric.bootstrap_valid_sample_count == 100
        assert metric.blockers == ()
        values.append(metric.value)
        fingerprints.append(report.fingerprint_sha256)

    assert values == pytest.approx([0.5, 0.5])
    assert fingerprints[0] != fingerprints[1]


def test_partition_tamper_and_retained_fit_failures_block_use() -> None:
    fit = _fit_partition()
    evaluation = _evaluation_partition()
    audit = audit_pose_ranking_leakage(fit, evaluation)
    model = fit_pose_ranking_calibration(fit, audit, _config())

    tampered_rows = list(evaluation.rows)
    tampered_rows[0] = replace(
        tampered_rows[0],
        term_values={"physics": 99.0, "clash": 0.0},
    )
    tampered = replace(evaluation, rows=tuple(tampered_rows))
    with pytest.raises(PoseRankingCalibrationError, match="does not bind"):
        evaluate_pose_ranking_calibration(model, tampered, audit)

    fit_with_failure = _fit_partition(include_failure=True)
    failure_audit = audit_pose_ranking_leakage(fit_with_failure, evaluation)
    assert failure_audit.passed
    with pytest.raises(PoseRankingCalibrationError, match="failure rows"):
        fit_pose_ranking_calibration(fit_with_failure, failure_audit, _config())


def test_rows_and_partitions_reject_ambiguous_labels_and_term_schemas() -> None:
    with pytest.raises(PoseRankingCalibrationError, match="boolean native_like"):
        _row("fit", "case", "pose", "target", "family", 1.0, 1.0, None)

    first = _row("fit", "case", "one", "target", "family", 1.0, 1.0, True)
    second = replace(
        _row("fit", "case", "two", "target", "family", 2.0, 2.0, False),
        term_values={"physics": 2.0, "different": 2.0},
    )
    with pytest.raises(PoseRankingCalibrationError, match="exact term schema"):
        PoseRankingCalibrationPartition(
            dataset_id="dataset",
            dataset_version="1",
            split_role="fit",
            rows=(first, second),
        )
