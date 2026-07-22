from __future__ import annotations

from dataclasses import replace
import hashlib

import pytest


pytest.importorskip("torch")

from betelgeuze_engine_v2.benchmark.public_split_provenance import (  # noqa: E402
    CASF_2016_DATASET_ID,
    PDBBIND_V2020_DATASET_ID,
    POSEBUSTERS_2023_308_DATASET_ID,
    POSEBUSTERS_2023_308_SELECTION_SHA256,
    POSEBUSTERS_2023_ARCHIVE_SHA256,
    POSEBUSTERS_2023_ARCHIVE_SIZE_BYTES,
    PUBLIC_DOCKING_DATASET_SPECS,
    PublicDockingDatasetSource,
    PublicDockingLeakagePolicy,
    PublicDockingSequenceIdentityMethod,
    PublicDockingSequenceIdentityReceipt,
    PublicDockingSequenceIdentityRow,
    PublicDockingSplitCase,
    PublicDockingSplitError,
    PublicDockingSplitManifest,
    audit_public_docking_split_leakage,
    bind_pose_ranking_partition_to_public_split,
    bind_public_pose_ranking_result,
    link_public_pose_ranking_evaluation,
)
from betelgeuze_engine_v2.docking import (  # noqa: E402
    PoseRankingCalibrationConfig,
    PoseRankingCalibrationPartition,
    PoseRankingCalibrationRow,
    PoseRankingEvaluationConfig,
    audit_pose_ranking_leakage,
    evaluate_pose_ranking_calibration,
    fit_pose_ranking_calibration,
)


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _source(dataset_id: str, *, access: bool = True) -> PublicDockingDatasetSource:
    return PublicDockingDatasetSource(
        dataset_id=dataset_id,
        archive_sha256=(
            POSEBUSTERS_2023_ARCHIVE_SHA256
            if dataset_id == POSEBUSTERS_2023_308_DATASET_ID
            else _sha(f"{dataset_id}:archive")
        ),
        archive_size_bytes=(
            POSEBUSTERS_2023_ARCHIVE_SIZE_BYTES
            if dataset_id == POSEBUSTERS_2023_308_DATASET_ID
            else 1024
        ),
        selection_manifest_sha256=(
            POSEBUSTERS_2023_308_SELECTION_SHA256
            if dataset_id == POSEBUSTERS_2023_308_DATASET_ID
            else _sha(f"{dataset_id}:selection")
        ),
        license_terms_sha256=_sha(f"{dataset_id}:license"),
        access_authorization_receipt_sha256=(
            _sha(f"{dataset_id}:access")
            if access and dataset_id != POSEBUSTERS_2023_308_DATASET_ID
            else ""
        ),
        selection_review_receipt_sha256=(
            ""
            if dataset_id == POSEBUSTERS_2023_308_DATASET_ID
            else _sha(f"{dataset_id}:selection-review")
        ),
    )


def _case(
    dataset_id: str,
    split: str,
    case_id: str,
    target_id: str,
    family: str,
    release_date: str,
) -> PublicDockingSplitCase:
    return PublicDockingSplitCase(
        dataset_id=dataset_id,
        case_id=case_id,
        pdb_id=f"pdb-{case_id}",
        target_id=target_id,
        target_family=family,
        split_role=split,
        release_date=release_date,
        receptor_sha256=_sha(f"receptor:{case_id}"),
        ligand_sha256=_sha(f"ligand:{case_id}"),
        scaffold_sha256=_sha(f"scaffold:{case_id}"),
        target_sequence_set_sha256=_sha(f"sequence-set:{target_id}"),
        cofactor_category="inorganic" if case_id.endswith("b") else "none",
        chemistry_status="unsupported" if case_id.endswith("b") else "supported",
    )


def _manifests(
    *,
    fit_access: bool = True,
) -> tuple[PublicDockingSplitManifest, PublicDockingSplitManifest]:
    scoring = _sha("scoring-protocol:v1")
    preparation = _sha("preparation-profile:v1")
    fit = PublicDockingSplitManifest(
        source=_source(PDBBIND_V2020_DATASET_ID, access=fit_access),
        split_role="fit",
        partition_scope="calibration_fit",
        scoring_protocol_sha256=scoring,
        preparation_profile_sha256=preparation,
        cases=(
            _case(
                PDBBIND_V2020_DATASET_ID,
                "fit",
                "fit-a",
                "fit-target-a",
                "kinase",
                "2019-01-01",
            ),
            _case(
                PDBBIND_V2020_DATASET_ID,
                "fit",
                "fit-b",
                "fit-target-b",
                "gpcr",
                "2020-01-01",
            ),
        ),
    )
    evaluation = PublicDockingSplitManifest(
        source=_source(POSEBUSTERS_2023_308_DATASET_ID),
        split_role="test",
        partition_scope="development_subset",
        scoring_protocol_sha256=scoring,
        preparation_profile_sha256=preparation,
        cases=(
            _case(
                POSEBUSTERS_2023_308_DATASET_ID,
                "test",
                "eval-a",
                "eval-target-a",
                "kinase",
                "2021-06-01",
            ),
            _case(
                POSEBUSTERS_2023_308_DATASET_ID,
                "test",
                "eval-b",
                "eval-target-b",
                "gpcr",
                "2022-06-01",
            ),
        ),
    )
    return fit, evaluation


def _sequence_receipt(
    fit: PublicDockingSplitManifest,
    evaluation: PublicDockingSplitManifest,
    *,
    identities: tuple[float, ...] = (0.20, 0.50),
) -> PublicDockingSequenceIdentityReceipt:
    return PublicDockingSequenceIdentityReceipt(
        fit_manifest_sha256=fit.fingerprint_sha256,
        evaluation_manifest_sha256=evaluation.fingerprint_sha256,
        method=PublicDockingSequenceIdentityMethod(
            tool_id="reviewed-sequence-audit",
            tool_version="1.0.0",
            executable_sha256=_sha("sequence-tool"),
            configuration_sha256=_sha("sequence-config"),
        ),
        rows=tuple(
            PublicDockingSequenceIdentityRow(
                evaluation_case_id=case.case_id,
                closest_fit_case_id=fit.cases[index % len(fit.cases)].case_id,
                maximum_sequence_identity=identities[index],
                fit_case_count=len(fit.cases),
                comparison_evidence_sha256=_sha(
                    f"sequence-evidence:{case.case_id}"
                ),
            )
            for index, case in enumerate(evaluation.cases)
        ),
    )


def _ranking_row(
    manifest: PublicDockingSplitManifest,
    case: PublicDockingSplitCase,
    pose_id: str,
    physics: float | None,
    clash: float | None,
    native_like: bool | None,
    *,
    failure: bool = False,
) -> PoseRankingCalibrationRow:
    return PoseRankingCalibrationRow(
        suite_id=manifest.fingerprint_sha256,
        case_id=case.case_id,
        pose_id=pose_id,
        target_id=case.target_id,
        target_family=case.target_family,
        split_role=manifest.split_role,
        scoring_protocol_sha256=manifest.scoring_protocol_sha256,
        preparation_profile_sha256=manifest.preparation_profile_sha256,
        receptor_sha256=case.receptor_sha256,
        ligand_sha256=case.ligand_sha256,
        scaffold_sha256=case.scaffold_sha256,
        pose_sha256=_sha(f"pose:{case.case_id}:{pose_id}"),
        status="failure" if failure else "success",
        term_values=(
            {} if failure else {"physics": float(physics), "clash": float(clash)}
        ),
        native_like=None if failure else native_like,
        error_code="unsupported_chemistry" if failure else "",
    )


def _partitions(
    fit_manifest: PublicDockingSplitManifest,
    evaluation_manifest: PublicDockingSplitManifest,
) -> tuple[PoseRankingCalibrationPartition, PoseRankingCalibrationPartition]:
    fit_rows: list[PoseRankingCalibrationRow] = []
    for case in fit_manifest.cases:
        fit_rows.extend(
            (
                _ranking_row(fit_manifest, case, "native", 0.0, 0.0, True),
                _ranking_row(fit_manifest, case, "decoy", 2.0, 1.0, False),
            )
        )
    evaluation_rows = (
        _ranking_row(
            evaluation_manifest,
            evaluation_manifest.cases[0],
            "native",
            0.0,
            0.0,
            True,
        ),
        _ranking_row(
            evaluation_manifest,
            evaluation_manifest.cases[0],
            "decoy",
            2.0,
            1.0,
            False,
        ),
        _ranking_row(
            evaluation_manifest,
            evaluation_manifest.cases[1],
            "failed",
            None,
            None,
            None,
            failure=True,
        ),
        _ranking_row(
            evaluation_manifest,
            evaluation_manifest.cases[1],
            "native",
            0.5,
            0.2,
            True,
        ),
    )
    return (
        PoseRankingCalibrationPartition(
            dataset_id=fit_manifest.source.dataset_id,
            dataset_version=fit_manifest.source.spec.dataset_version,
            split_role="fit",
            rows=tuple(fit_rows),
        ),
        PoseRankingCalibrationPartition(
            dataset_id=evaluation_manifest.source.dataset_id,
            dataset_version=evaluation_manifest.source.spec.dataset_version,
            split_role="test",
            rows=evaluation_rows,
        ),
    )


def _successful_chain():
    fit_manifest, evaluation_manifest = _manifests()
    sequence = _sequence_receipt(fit_manifest, evaluation_manifest)
    public_audit = audit_public_docking_split_leakage(
        fit_manifest,
        evaluation_manifest,
        sequence,
        policy=PublicDockingLeakagePolicy(
            maximum_allowed_target_sequence_identity=0.60,
            require_temporal_order=True,
            require_complete_official_evaluation=False,
        ),
    )
    fit_partition, evaluation_partition = _partitions(
        fit_manifest,
        evaluation_manifest,
    )
    calibration_audit = audit_pose_ranking_leakage(
        fit_partition,
        evaluation_partition,
    )
    link = link_public_pose_ranking_evaluation(
        fit_partition,
        evaluation_partition,
        calibration_audit,
        fit_manifest,
        evaluation_manifest,
        sequence,
        public_audit,
    )
    model = fit_pose_ranking_calibration(
        fit_partition,
        calibration_audit,
        PoseRankingCalibrationConfig(
            term_ids=("physics", "clash"),
            learning_rate=0.05,
            l2_penalty=1.0e-3,
            iterations=100,
            trace_interval=10,
            max_training_pairs=100,
        ),
    )
    report = evaluate_pose_ranking_calibration(
        model,
        evaluation_partition,
        calibration_audit,
        config=PoseRankingEvaluationConfig(
            confidence_level=0.95,
            bootstrap_samples=20,
            seed=17,
        ),
    )
    return (
        fit_manifest,
        evaluation_manifest,
        sequence,
        public_audit,
        fit_partition,
        evaluation_partition,
        calibration_audit,
        link,
        report,
    )


def test_frozen_source_catalog_preserves_access_and_official_case_boundaries() -> None:
    assert PUBLIC_DOCKING_DATASET_SPECS[CASF_2016_DATASET_ID].official_evaluation_case_count == 285
    assert (
        PUBLIC_DOCKING_DATASET_SPECS[POSEBUSTERS_2023_308_DATASET_ID]
        .official_evaluation_case_count
        == 308
    )
    assert (
        PUBLIC_DOCKING_DATASET_SPECS[POSEBUSTERS_2023_308_DATASET_ID]
        .official_selection_manifest_sha256
        == POSEBUSTERS_2023_308_SELECTION_SHA256
    )
    assert not _source(PDBBIND_V2020_DATASET_ID, access=False).access_basis_present
    assert _source(
        POSEBUSTERS_2023_308_DATASET_ID,
        access=False,
    ).access_basis_present
    with pytest.raises(PublicDockingSplitError, match="frozen official identity"):
        replace(
            _source(POSEBUSTERS_2023_308_DATASET_ID),
            selection_manifest_sha256=_sha("wrong-posebusters-selection"),
        )

    fit, evaluation = _manifests()
    unreviewed_fit = replace(
        fit,
        source=replace(fit.source, selection_review_receipt_sha256=""),
    )
    assert "dataset_selection_review_evidence_missing" in unreviewed_fit.blockers
    with pytest.raises(PublicDockingSplitError, match="complete official"):
        replace(
            evaluation,
            partition_scope="full_benchmark",
            complete_official_case_set=True,
        )


def test_public_split_link_and_family_denominator_result_binding() -> None:
    (
        _,
        evaluation_manifest,
        sequence,
        public_audit,
        fit_partition,
        evaluation_partition,
        _,
        link,
        report,
    ) = _successful_chain()

    assert public_audit.passed
    assert public_audit.sequence_identity_stratum_counts == {
        "high_90_to_100_percent": 0,
        "low_0_to_30_percent": 1,
        "medium_above_30_below_90_percent": 1,
    }
    assert link.ready
    assert link.fit_partition_sha256 == fit_partition.fingerprint_sha256
    assert (
        link.evaluation_partition_sha256
        == evaluation_partition.fingerprint_sha256
    )
    assert sequence.to_dict()["case_count"] == 2

    binding = bind_public_pose_ranking_result(
        report,
        link,
        evaluation_manifest,
    )
    assert binding.passed
    assert binding.all_case_denominator == 2
    assert binding.target_family_case_denominators == {"gpcr": 1, "kinase": 1}
    assert binding.to_dict()["independent_rerun_complete"] is False
    assert binding.to_dict()["claim_safe"] is False


def test_exact_temporal_sequence_and_access_leaks_remain_explicit() -> None:
    fit, evaluation = _manifests(fit_access=False)
    leaked_first = replace(
        evaluation.cases[0],
        release_date="2019-01-01",
        scaffold_sha256=fit.cases[0].scaffold_sha256,
        target_sequence_set_sha256=fit.cases[0].target_sequence_set_sha256,
    )
    leaked_evaluation = replace(
        evaluation,
        cases=(leaked_first, evaluation.cases[1]),
    )
    sequence = _sequence_receipt(
        fit,
        leaked_evaluation,
        identities=(0.95, 0.50),
    )
    audit = audit_public_docking_split_leakage(
        fit,
        leaked_evaluation,
        sequence,
        policy=PublicDockingLeakagePolicy(
            maximum_allowed_target_sequence_identity=0.30,
            require_temporal_order=True,
        ),
    )

    assert not audit.passed
    assert "scaffold_sha256_overlap" in audit.blockers
    assert "target_sequence_set_sha256_overlap" in audit.blockers
    assert "dataset_access_basis_missing" in audit.blockers
    assert "complete_official_evaluation_case_set_missing" in audit.blockers
    assert "evaluation_release_not_after_fit_release" in audit.blockers
    assert "target_sequence_identity_threshold_exceeded" in audit.blockers
    assert audit.temporal_violation_case_ids == ("eval-a",)
    assert audit.sequence_identity_violation_case_ids == ("eval-a", "eval-b")


def test_sequence_receipt_and_partition_binding_fail_closed_on_crosswire() -> None:
    fit_manifest, evaluation_manifest = _manifests()
    sequence = _sequence_receipt(fit_manifest, evaluation_manifest)
    with pytest.raises(PublicDockingSplitError, match="cover every"):
        audit_public_docking_split_leakage(
            fit_manifest,
            evaluation_manifest,
            replace(sequence, rows=sequence.rows[:1]),
            policy=PublicDockingLeakagePolicy(
                require_complete_official_evaluation=False
            ),
        )

    fit_partition, _ = _partitions(fit_manifest, evaluation_manifest)
    cross_wired_rows = tuple(
        replace(row, suite_id=_sha("wrong-suite")) for row in fit_partition.rows
    )
    cross_wired_partition = replace(fit_partition, rows=cross_wired_rows)
    binding = bind_pose_ranking_partition_to_public_split(
        cross_wired_partition,
        fit_manifest,
    )
    assert not binding.passed
    assert binding.blockers == ("suite_manifest_identity_mismatch",)


def test_link_recomputes_audits_and_result_rejects_manifest_crosswire() -> None:
    (
        fit_manifest,
        evaluation_manifest,
        sequence,
        public_audit,
        fit_partition,
        evaluation_partition,
        calibration_audit,
        link,
        report,
    ) = _successful_chain()
    forged_public_audit = replace(
        public_audit,
        sequence_identity_stratum_counts={
            "low_0_to_30_percent": 0,
            "medium_above_30_below_90_percent": 0,
            "high_90_to_100_percent": 2,
        },
    )
    forged_link = link_public_pose_ranking_evaluation(
        fit_partition,
        evaluation_partition,
        calibration_audit,
        fit_manifest,
        evaluation_manifest,
        sequence,
        forged_public_audit,
    )
    assert not forged_link.ready
    assert forged_link.blockers == ("public_split_leakage_audit_failed",)

    cross_wired_case = replace(
        evaluation_manifest.cases[0],
        target_family="cross-wired-family",
    )
    cross_wired_manifest = replace(
        evaluation_manifest,
        cases=(cross_wired_case, evaluation_manifest.cases[1]),
    )
    binding = bind_public_pose_ranking_result(
        report,
        link,
        cross_wired_manifest,
    )
    assert not binding.passed
    assert "evaluation_manifest_link_mismatch" in binding.blockers
    assert "result_case_target_or_family_mismatch" in binding.blockers
    assert "result_target_family_denominator_mismatch" in binding.blockers
