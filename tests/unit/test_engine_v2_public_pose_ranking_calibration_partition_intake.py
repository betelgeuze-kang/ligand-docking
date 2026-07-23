from __future__ import annotations

from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path

import pytest

from betelgeuze_engine_v2.benchmark.public_pose_ranking_calibration_partition_intake import (
    PUBLIC_POSE_RANKING_CALIBRATION_PARTITION_INTAKE_CONFIGURATION_SHA256,
    PublicPoseRankingCalibrationPartitionIntakeError,
    audit_public_pose_ranking_calibration_partitions,
    load_public_pose_ranking_calibration_partition_file,
)
from betelgeuze_engine_v2.benchmark.public_pose_ranking_calibration_training_view import (
    PUBLIC_POSE_RANKING_CALIBRATION_TRAINING_VIEW_CONFIGURATION_SHA256,
    PublicPoseRankingCalibrationTrainingViewError,
    fit_public_pose_ranking_calibration_training_view,
    materialize_public_pose_ranking_calibration_training_view,
)
from betelgeuze_engine_v2.benchmark.public_pose_ranking_corpus_intake import (
    FROZEN_PUBLIC_POSE_RANKING_CORPUS_POLICY,
    PublicPoseRankingCorpusAudit,
    PublicPoseRankingCorpusInputIdentity,
    PublicPoseRankingCorpusIntakeReceipt,
)
from betelgeuze_engine_v2.benchmark.public_split_provenance import (
    CASF_2016_DATASET_ID,
    PDBBIND_V2020_DATASET_ID,
    POSEBUSTERS_2023_308_DATASET_ID,
    POSEBUSTERS_2023_308_SELECTION_SHA256,
    POSEBUSTERS_2023_ARCHIVE_SHA256,
    POSEBUSTERS_2023_ARCHIVE_SIZE_BYTES,
    PublicDockingDatasetSource,
    PublicDockingLeakageAudit,
    PublicDockingSequenceIdentityMethod,
    PublicDockingSequenceIdentityReceipt,
    PublicDockingSequenceIdentityRow,
    PublicDockingSplitCase,
    PublicDockingSplitManifest,
)
from betelgeuze_engine_v2.docking.calibration import (
    PoseRankingCalibrationConfig,
    PoseRankingCalibrationPartition,
    PoseRankingCalibrationRow,
)


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("ascii")).hexdigest()


def _source(dataset_id: str) -> PublicDockingDatasetSource:
    posebusters = dataset_id == POSEBUSTERS_2023_308_DATASET_ID
    return PublicDockingDatasetSource(
        dataset_id=dataset_id,
        archive_sha256=(
            POSEBUSTERS_2023_ARCHIVE_SHA256
            if posebusters
            else _sha(f"{dataset_id}:archive")
        ),
        archive_size_bytes=(
            POSEBUSTERS_2023_ARCHIVE_SIZE_BYTES if posebusters else 4096
        ),
        selection_manifest_sha256=(
            POSEBUSTERS_2023_308_SELECTION_SHA256
            if posebusters
            else _sha(f"{dataset_id}:selection")
        ),
        license_terms_sha256=_sha(f"{dataset_id}:license"),
        access_authorization_receipt_sha256=(
            "" if posebusters else _sha(f"{dataset_id}:access")
        ),
        selection_review_receipt_sha256=(
            "" if posebusters else _sha(f"{dataset_id}:selection-review")
        ),
    )


def _case(
    dataset_id: str,
    split_role: str,
    case_id: str,
    release_date: str,
) -> PublicDockingSplitCase:
    return PublicDockingSplitCase(
        dataset_id=dataset_id,
        case_id=case_id,
        pdb_id=f"pdb-{case_id}",
        target_id=f"target-{case_id}",
        target_family=f"family-{case_id[-1]}",
        split_role=split_role,
        release_date=release_date,
        receptor_sha256=_sha(f"receptor:{case_id}"),
        ligand_sha256=_sha(f"ligand:{case_id}"),
        scaffold_sha256=_sha(f"scaffold:{case_id}"),
        target_sequence_set_sha256=_sha(f"sequence:{case_id}"),
        cofactor_category="none",
        chemistry_status="supported",
    )


def _manifests() -> tuple[
    PublicDockingSplitManifest,
    PublicDockingSplitManifest,
    PublicDockingSplitManifest,
]:
    scoring = _sha("frozen-four-term-score:v1")
    preparation = _sha("frozen-preparation:v1")
    fit = PublicDockingSplitManifest(
        source=_source(PDBBIND_V2020_DATASET_ID),
        split_role="fit",
        partition_scope="calibration_fit",
        scoring_protocol_sha256=scoring,
        preparation_profile_sha256=preparation,
        cases=(
            _case(PDBBIND_V2020_DATASET_ID, "fit", "f001", "2018-01-01"),
            _case(PDBBIND_V2020_DATASET_ID, "fit", "f002", "2019-01-01"),
        ),
    )
    validation = PublicDockingSplitManifest(
        source=_source(CASF_2016_DATASET_ID),
        split_role="validation",
        partition_scope="full_benchmark",
        scoring_protocol_sha256=scoring,
        preparation_profile_sha256=preparation,
        cases=(
            _case(CASF_2016_DATASET_ID, "validation", "v001", "2016-01-01"),
            _case(CASF_2016_DATASET_ID, "validation", "v002", "2017-01-01"),
        ),
    )
    test = PublicDockingSplitManifest(
        source=_source(POSEBUSTERS_2023_308_DATASET_ID),
        split_role="test",
        partition_scope="full_benchmark",
        scoring_protocol_sha256=scoring,
        preparation_profile_sha256=preparation,
        cases=(
            _case(
                POSEBUSTERS_2023_308_DATASET_ID,
                "test",
                "t001",
                "2021-01-01",
            ),
            _case(
                POSEBUSTERS_2023_308_DATASET_ID,
                "test",
                "t002",
                "2022-01-01",
            ),
        ),
    )
    return fit, validation, test


def _method() -> PublicDockingSequenceIdentityMethod:
    return PublicDockingSequenceIdentityMethod(
        tool_id="reviewed-smith-waterman",
        tool_version="1.0.0",
        executable_sha256=_sha("sequence:executable"),
        configuration_sha256=_sha("sequence:configuration"),
    )


def _sequence_receipt(
    reference: PublicDockingSplitManifest,
    evaluation: PublicDockingSplitManifest,
) -> PublicDockingSequenceIdentityReceipt:
    return PublicDockingSequenceIdentityReceipt(
        fit_manifest_sha256=reference.fingerprint_sha256,
        evaluation_manifest_sha256=evaluation.fingerprint_sha256,
        method=_method(),
        rows=tuple(
            PublicDockingSequenceIdentityRow(
                evaluation_case_id=case.case_id,
                closest_fit_case_id=(
                    reference.cases[index % len(reference.cases)].case_id
                ),
                maximum_sequence_identity=0.20,
                fit_case_count=len(reference.cases),
                comparison_evidence_sha256=_sha(
                    f"{reference.source.dataset_id}:{case.case_id}:sequence"
                ),
            )
            for index, case in enumerate(evaluation.cases)
        ),
    )


def _empty_public_overlaps() -> dict[str, tuple[str, ...]]:
    return {
        field: ()
        for field in (
            "case_id",
            "pdb_id",
            "target_id",
            "receptor_sha256",
            "ligand_sha256",
            "scaffold_sha256",
            "target_sequence_set_sha256",
            "target_family",
        )
    }


def _passing_corpus_receipt(
    fit: PublicDockingSplitManifest,
    validation: PublicDockingSplitManifest,
    test: PublicDockingSplitManifest,
) -> PublicPoseRankingCorpusIntakeReceipt:
    fit_validation = _sequence_receipt(fit, validation)
    fit_test = _sequence_receipt(fit, test)
    validation_test = _sequence_receipt(validation, test)
    policy = FROZEN_PUBLIC_POSE_RANKING_CORPUS_POLICY
    fit_validation_audit = PublicDockingLeakageAudit(
        fit_manifest_sha256=fit.fingerprint_sha256,
        evaluation_manifest_sha256=validation.fingerprint_sha256,
        sequence_receipt_sha256=fit_validation.fingerprint_sha256,
        policy=policy.fit_validation_policy(),
        overlaps=_empty_public_overlaps(),
        temporal_violation_case_ids=(),
        sequence_identity_violation_case_ids=(),
        sequence_identity_stratum_counts=fit_validation.stratum_counts,
        evaluation_case_count=len(validation.cases),
        blockers=(),
    )
    fit_test_audit = PublicDockingLeakageAudit(
        fit_manifest_sha256=fit.fingerprint_sha256,
        evaluation_manifest_sha256=test.fingerprint_sha256,
        sequence_receipt_sha256=fit_test.fingerprint_sha256,
        policy=policy.fit_test_policy(),
        overlaps=_empty_public_overlaps(),
        temporal_violation_case_ids=(),
        sequence_identity_violation_case_ids=(),
        sequence_identity_stratum_counts=fit_test.stratum_counts,
        evaluation_case_count=len(test.cases),
        blockers=(),
    )
    audit = PublicPoseRankingCorpusAudit(
        policy=policy,
        fit_manifest_sha256=fit.fingerprint_sha256,
        validation_manifest_sha256=validation.fingerprint_sha256,
        test_manifest_sha256=test.fingerprint_sha256,
        fit_case_count=len(fit.cases),
        validation_case_count=len(validation.cases),
        test_case_count=len(test.cases),
        fit_validation_audit=fit_validation_audit,
        fit_test_audit=fit_test_audit,
        validation_test_sequence_receipt_sha256=(
            validation_test.fingerprint_sha256
        ),
        validation_test_overlaps={
            key: values
            for key, values in _empty_public_overlaps().items()
            if key != "target_family"
        },
        validation_test_temporal_violation_case_ids=(),
        validation_test_sequence_violation_case_ids=(),
        validation_test_sequence_stratum_counts=(
            validation_test.stratum_counts
        ),
        sequence_method_sha256s=(
            fit_validation.method.fingerprint_sha256,
            fit_test.method.fingerprint_sha256,
            validation_test.method.fingerprint_sha256,
        ),
        blockers=(),
    )
    roots = (
        ("fit_manifest", fit, len(fit.cases)),
        ("validation_manifest", validation, len(validation.cases)),
        ("test_manifest", test, len(test.cases)),
        (
            "fit_validation_sequence",
            fit_validation,
            len(validation.cases),
        ),
        ("fit_test_sequence", fit_test, len(test.cases)),
        (
            "validation_test_sequence",
            validation_test,
            len(test.cases),
        ),
    )
    return PublicPoseRankingCorpusIntakeReceipt(
        input_identities=tuple(
            PublicPoseRankingCorpusInputIdentity(
                role=role,
                source_file_sha256=_sha(f"{role}:file"),
                source_file_size_bytes=1000 + index,
                payload_schema_id=payload.schema_id,
                payload_sha256=payload.fingerprint_sha256,
                row_count=row_count,
            )
            for index, (role, payload, row_count) in enumerate(roots)
        ),
        audit=audit,
    )


def _ranking_row(
    manifest: PublicDockingSplitManifest,
    case: PublicDockingSplitCase,
    pose_id: str,
    *,
    native_like: bool | None,
    failure: bool = False,
    term_ids: tuple[str, ...] = ("clash", "physics"),
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
        pose_sha256=_sha(f"{manifest.split_role}:{case.case_id}:{pose_id}"),
        status="failure" if failure else "success",
        term_values=(
            {}
            if failure
            else {
                term_id: float(index + (0 if native_like else 2))
                for index, term_id in enumerate(term_ids)
            }
        ),
        native_like=None if failure else native_like,
        error_code="scoring_failure" if failure else "",
    )


def _partitions(
    fit: PublicDockingSplitManifest,
    validation: PublicDockingSplitManifest,
    *,
    fit_failure: bool = False,
    validation_term_ids: tuple[str, ...] = ("clash", "physics"),
) -> tuple[
    PoseRankingCalibrationPartition,
    PoseRankingCalibrationPartition,
]:
    fit_rows: list[PoseRankingCalibrationRow] = []
    for case in fit.cases:
        fit_rows.extend(
            (
                _ranking_row(
                    fit,
                    case,
                    "decoy",
                    native_like=False,
                ),
                _ranking_row(
                    fit,
                    case,
                    "native",
                    native_like=True,
                ),
            )
        )
    if fit_failure:
        fit_rows.append(
            _ranking_row(
                fit,
                fit.cases[1],
                "failed",
                native_like=None,
                failure=True,
            )
        )
    fit_rows.sort(key=lambda row: (row.case_id, row.pose_id))
    validation_rows = [
        _ranking_row(
            validation,
            validation.cases[0],
            "decoy",
            native_like=False,
            term_ids=validation_term_ids,
        ),
        _ranking_row(
            validation,
            validation.cases[0],
            "native",
            native_like=True,
            term_ids=validation_term_ids,
        ),
        _ranking_row(
            validation,
            validation.cases[1],
            "failed",
            native_like=None,
            failure=True,
            term_ids=validation_term_ids,
        ),
    ]
    return (
        PoseRankingCalibrationPartition(
            dataset_id=fit.source.dataset_id,
            dataset_version=fit.source.spec.dataset_version,
            split_role="fit",
            rows=tuple(fit_rows),
        ),
        PoseRankingCalibrationPartition(
            dataset_id=validation.source.dataset_id,
            dataset_version=validation.source.spec.dataset_version,
            split_role="validation",
            rows=tuple(validation_rows),
        ),
    )


def _audit(
    fit: PublicDockingSplitManifest,
    validation: PublicDockingSplitManifest,
    test: PublicDockingSplitManifest,
    fit_partition: PoseRankingCalibrationPartition,
    validation_partition: PoseRankingCalibrationPartition,
):
    return audit_public_pose_ranking_calibration_partitions(
        corpus_intake_receipt=_passing_corpus_receipt(
            fit,
            validation,
            test,
        ),
        corpus_receipt_source_file_sha256=_sha("corpus-receipt:file"),
        corpus_receipt_source_file_size_bytes=4096,
        fit_manifest=fit,
        validation_manifest=validation,
        fit_partition=fit_partition,
        fit_partition_source_file_sha256=_sha("fit-partition:file"),
        fit_partition_source_file_size_bytes=8192,
        validation_partition=validation_partition,
        validation_partition_source_file_sha256=_sha(
            "validation-partition:file"
        ),
        validation_partition_source_file_size_bytes=8192,
    )


def _write_canonical(path: Path, payload: object) -> str:
    data = (
        json.dumps(
            payload,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
        + b"\n"
    )
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def test_partition_intake_binds_fit_and_validation_without_test_access() -> None:
    fit, validation, test = _manifests()
    fit_partition, validation_partition = _partitions(fit, validation)
    receipt = _audit(
        fit,
        validation,
        test,
        fit_partition,
        validation_partition,
    )

    assert receipt.passed
    assert receipt.ready_for_direct_fit
    assert receipt.fit_partition.case_count == 2
    assert receipt.validation_partition.case_count == 2
    assert receipt.validation_partition.failure_row_count == 1
    assert receipt.validation_partition.pairwise_uninformative_case_ids == (
        "v002",
    )
    payload = receipt.to_dict()
    assert payload["validation_labels_used_for_fit"] is False
    assert payload["test_partition_present"] is False
    assert payload["test_labels_present"] is False
    assert payload["fit_or_model_selection_performed"] is False
    assert payload["claim_safe"] is False
    assert (
        payload["configuration_sha256"]
        == PUBLIC_POSE_RANKING_CALIBRATION_PARTITION_INTAKE_CONFIGURATION_SHA256
        == "c4b423063a36f38d7f6f098a38c7ea54b078c25f3cc04d060ae88638902ff8be"
    )


def test_fit_failures_are_retained_but_require_a_bound_training_view() -> None:
    fit, validation, test = _manifests()
    fit_partition, validation_partition = _partitions(
        fit,
        validation,
        fit_failure=True,
    )
    receipt = _audit(
        fit,
        validation,
        test,
        fit_partition,
        validation_partition,
    )

    assert receipt.passed
    assert receipt.fit_partition.failure_row_count == 1
    assert not receipt.ready_for_direct_fit
    assert receipt.to_dict()["direct_fit_blockers"] == [
        "fit_failure_rows_require_bound_success_training_view"
    ]


def test_term_schema_and_pose_identity_leakage_fail_closed() -> None:
    fit, validation, test = _manifests()
    fit_partition, mismatched_validation = _partitions(
        fit,
        validation,
        validation_term_ids=("clash", "solvation"),
    )
    mismatch = _audit(
        fit,
        validation,
        test,
        fit_partition,
        mismatched_validation,
    )
    assert not mismatch.passed
    assert "fit_validation_term_schema_mismatch" in mismatch.blockers

    _, validation_partition = _partitions(fit, validation)
    leaked_rows = list(validation_partition.rows)
    leaked_rows[0] = replace(
        leaked_rows[0],
        pose_sha256=fit_partition.rows[0].pose_sha256,
    )
    leaked = _audit(
        fit,
        validation,
        test,
        fit_partition,
        replace(validation_partition, rows=tuple(leaked_rows)),
    )
    assert not leaked.passed
    assert "fit_validation_pose_sha256_overlap" in leaked.blockers


def test_partition_loader_accepts_only_exact_canonical_fit_or_validation(
    tmp_path: Path,
) -> None:
    fit, validation, _ = _manifests()
    fit_partition, validation_partition = _partitions(fit, validation)
    fit_path = tmp_path / "fit.json"
    fit_file_sha256 = _write_canonical(fit_path, fit_partition.to_dict())

    loaded = load_public_pose_ranking_calibration_partition_file(
        fit_path,
        expected_file_sha256=fit_file_sha256,
        expected_partition_sha256=fit_partition.fingerprint_sha256,
        split_role="fit",
    )
    assert loaded.fingerprint_sha256 == fit_partition.fingerprint_sha256

    validation_path = tmp_path / "validation.json"
    validation_file_sha256 = _write_canonical(
        validation_path,
        validation_partition.to_dict(),
    )
    with pytest.raises(
        PublicPoseRankingCalibrationPartitionIntakeError,
        match="split_role=fit",
    ):
        load_public_pose_ranking_calibration_partition_file(
            validation_path,
            expected_file_sha256=validation_file_sha256,
            expected_partition_sha256=(
                validation_partition.fingerprint_sha256
            ),
            split_role="fit",
        )

    with pytest.raises(
        PublicPoseRankingCalibrationPartitionIntakeError,
        match="only fit or validation",
    ):
        load_public_pose_ranking_calibration_partition_file(
            fit_path,
            expected_file_sha256=fit_file_sha256,
            expected_partition_sha256=fit_partition.fingerprint_sha256,
            split_role="test",
        )


def test_partition_loader_rejects_labels_outside_schema_and_unsafe_files(
    tmp_path: Path,
) -> None:
    fit, validation, _ = _manifests()
    fit_partition, _ = _partitions(fit, validation)
    labeled = fit_partition.to_dict()
    labeled["rows"][0]["test_label_source"] = "forbidden"
    labeled_path = tmp_path / "labeled.json"
    labeled_sha256 = _write_canonical(labeled_path, labeled)
    with pytest.raises(
        PublicPoseRankingCalibrationPartitionIntakeError,
        match="keys differ",
    ):
        load_public_pose_ranking_calibration_partition_file(
            labeled_path,
            expected_file_sha256=labeled_sha256,
            expected_partition_sha256=fit_partition.fingerprint_sha256,
            split_role="fit",
        )

    pretty_path = tmp_path / "pretty.json"
    pretty_data = (
        json.dumps(fit_partition.to_dict(), indent=2).encode("ascii") + b"\n"
    )
    pretty_path.write_bytes(pretty_data)
    with pytest.raises(
        PublicPoseRankingCalibrationPartitionIntakeError,
        match="canonical",
    ):
        load_public_pose_ranking_calibration_partition_file(
            pretty_path,
            expected_file_sha256=hashlib.sha256(pretty_data).hexdigest(),
            expected_partition_sha256=fit_partition.fingerprint_sha256,
            split_role="fit",
        )

    duplicate_path = tmp_path / "duplicate.json"
    duplicate_data = b'{"schema_id":"one","schema_id":"two"}\n'
    duplicate_path.write_bytes(duplicate_data)
    with pytest.raises(
        PublicPoseRankingCalibrationPartitionIntakeError,
        match="duplicate",
    ):
        load_public_pose_ranking_calibration_partition_file(
            duplicate_path,
            expected_file_sha256=hashlib.sha256(duplicate_data).hexdigest(),
            expected_partition_sha256=fit_partition.fingerprint_sha256,
            split_role="fit",
        )

    target = tmp_path / "target.json"
    target_sha256 = _write_canonical(target, fit_partition.to_dict())
    link = tmp_path / "link.json"
    link.symlink_to(target)
    with pytest.raises(
        PublicPoseRankingCalibrationPartitionIntakeError,
        match="non-symlink",
    ):
        load_public_pose_ranking_calibration_partition_file(
            link,
            expected_file_sha256=target_sha256,
            expected_partition_sha256=fit_partition.fingerprint_sha256,
            split_role="fit",
        )


def test_receipt_rejects_forged_blockers_and_writes_mode_0600(
    tmp_path: Path,
) -> None:
    fit, validation, test = _manifests()
    fit_partition, validation_partition = _partitions(fit, validation)
    receipt = _audit(
        fit,
        validation,
        test,
        fit_partition,
        validation_partition,
    )

    with pytest.raises(
        PublicPoseRankingCalibrationPartitionIntakeError,
        match="blockers do not match",
    ):
        replace(receipt, blockers=("forged_readiness",))
    with pytest.raises(
        PublicPoseRankingCalibrationPartitionIntakeError,
        match="fit public binding is not bound",
    ):
        replace(receipt, fit_manifest_sha256=_sha("crosswired-manifest"))

    output = tmp_path / "partition-intake.json"
    receipt.write_json(output)
    assert os.stat(output, follow_symlinks=False).st_mode & 0o777 == 0o600
    assert output.read_bytes() == (
        json.dumps(
            receipt.to_dict(),
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
        + b"\n"
    )
    with pytest.raises(
        PublicPoseRankingCalibrationPartitionIntakeError,
        match="exists",
    ):
        receipt.write_json(output)


def test_blocked_corpus_cannot_admit_calibration_partitions() -> None:
    fit, validation, test = _manifests()
    corpus = _passing_corpus_receipt(fit, validation, test)
    blocked_fit_validation = replace(
        corpus.audit.fit_validation_audit,
        blockers=("dataset_access_basis_missing",),
    )
    blocked_audit = replace(
        corpus.audit,
        fit_validation_audit=blocked_fit_validation,
        blockers=("fit_validation_dataset_access_basis_missing",),
    )
    blocked_corpus = replace(corpus, audit=blocked_audit)
    fit_partition, validation_partition = _partitions(fit, validation)

    with pytest.raises(
        PublicPoseRankingCalibrationPartitionIntakeError,
        match="requires a passing corpus intake",
    ):
        audit_public_pose_ranking_calibration_partitions(
            corpus_intake_receipt=blocked_corpus,
            corpus_receipt_source_file_sha256=_sha("corpus-receipt:file"),
            corpus_receipt_source_file_size_bytes=4096,
            fit_manifest=fit,
            validation_manifest=validation,
            fit_partition=fit_partition,
            fit_partition_source_file_sha256=_sha("fit-partition:file"),
            fit_partition_source_file_size_bytes=8192,
            validation_partition=validation_partition,
            validation_partition_source_file_sha256=_sha(
                "validation-partition:file"
            ),
            validation_partition_source_file_size_bytes=8192,
        )


def _training_view(
    fit: PublicDockingSplitManifest,
    validation: PublicDockingSplitManifest,
    test: PublicDockingSplitManifest,
    fit_partition: PoseRankingCalibrationPartition,
    validation_partition: PoseRankingCalibrationPartition,
):
    partition_intake = _audit(
        fit,
        validation,
        test,
        fit_partition,
        validation_partition,
    )
    return materialize_public_pose_ranking_calibration_training_view(
        partition_intake_receipt=partition_intake,
        partition_intake_receipt_source_file_sha256=_sha(
            "partition-intake:file"
        ),
        partition_intake_receipt_source_file_size_bytes=16384,
        fit_partition=fit_partition,
        validation_partition=validation_partition,
    )


def test_training_view_retains_failure_disposition_and_fits_successes() -> None:
    fit, validation, test = _manifests()
    fit_partition, validation_partition = _partitions(
        fit,
        validation,
        fit_failure=True,
    )
    receipt = _training_view(
        fit,
        validation,
        test,
        fit_partition,
        validation_partition,
    )

    assert receipt.ready_for_fit
    assert len(receipt.row_dispositions) == 5
    assert len(receipt.training_partition.rows) == 4
    excluded = [
        item
        for item in receipt.row_dispositions
        if item.selection == "excluded"
    ]
    assert len(excluded) == 1
    assert excluded[0].source_status == "failure"
    assert excluded[0].source_error_code == "scoring_failure"
    payload = receipt.to_dict()
    assert payload["source_failure_rows_retained_as_dispositions"] is True
    assert payload["validation_labels_used_for_selection"] is False
    assert payload["validation_labels_used_for_fit"] is False
    assert payload["test_partition_present"] is False
    assert payload["fit_performed"] is False

    model = fit_public_pose_ranking_calibration_training_view(
        receipt,
        PoseRankingCalibrationConfig(
            term_ids=("clash", "physics"),
            learning_rate=0.05,
            l2_penalty=1.0e-3,
            iterations=50,
            trace_interval=10,
            max_training_pairs=100,
        ),
    )
    assert model.fit_partition_sha256 == (
        receipt.training_partition.fingerprint_sha256
    )
    assert model.evaluation_identity_sha256 == (
        receipt.validation_partition.partition_identity_sha256
    )
    assert model.training_case_count == 2
    assert model.training_pair_count == 2
    assert model.to_dict()["holdout_validated"] is False


def test_training_view_without_failures_preserves_every_source_row() -> None:
    fit, validation, test = _manifests()
    fit_partition, validation_partition = _partitions(fit, validation)
    receipt = _training_view(
        fit,
        validation,
        test,
        fit_partition,
        validation_partition,
    )

    assert receipt.ready_for_fit
    assert all(
        item.selection == "included"
        for item in receipt.row_dispositions
    )
    assert (
        receipt.training_partition.fingerprint_sha256
        == fit_partition.fingerprint_sha256
    )
    assert (
        receipt.to_dict()["configuration_sha256"]
        == PUBLIC_POSE_RANKING_CALIBRATION_TRAINING_VIEW_CONFIGURATION_SHA256
        == "e5e202d10420b5a557b1227aa0f7735433ebaeadc1656f6b981c14453aeb25b8"
    )


def test_training_view_rejects_source_tamper_and_blocked_intake() -> None:
    fit, validation, test = _manifests()
    fit_partition, validation_partition = _partitions(fit, validation)
    partition_intake = _audit(
        fit,
        validation,
        test,
        fit_partition,
        validation_partition,
    )
    tampered_rows = list(fit_partition.rows)
    tampered_rows[0] = replace(
        tampered_rows[0],
        term_values={"clash": 99.0, "physics": 3.0},
    )
    tampered_fit = replace(fit_partition, rows=tuple(tampered_rows))
    with pytest.raises(
        PublicPoseRankingCalibrationTrainingViewError,
        match="not bound",
    ):
        materialize_public_pose_ranking_calibration_training_view(
            partition_intake_receipt=partition_intake,
            partition_intake_receipt_source_file_sha256=_sha(
                "partition-intake:file"
            ),
            partition_intake_receipt_source_file_size_bytes=16384,
            fit_partition=tampered_fit,
            validation_partition=validation_partition,
        )

    _, mismatched_validation = _partitions(
        fit,
        validation,
        validation_term_ids=("clash", "solvation"),
    )
    blocked_intake = _audit(
        fit,
        validation,
        test,
        fit_partition,
        mismatched_validation,
    )
    assert not blocked_intake.passed
    with pytest.raises(
        PublicPoseRankingCalibrationTrainingViewError,
        match="requires a passing",
    ):
        materialize_public_pose_ranking_calibration_training_view(
            partition_intake_receipt=blocked_intake,
            partition_intake_receipt_source_file_sha256=_sha(
                "partition-intake:file"
            ),
            partition_intake_receipt_source_file_size_bytes=16384,
            fit_partition=fit_partition,
            validation_partition=mismatched_validation,
        )


def test_training_view_receipt_rejects_silent_row_omission_and_writes_0600(
    tmp_path: Path,
) -> None:
    fit, validation, test = _manifests()
    fit_partition, validation_partition = _partitions(
        fit,
        validation,
        fit_failure=True,
    )
    receipt = _training_view(
        fit,
        validation,
        test,
        fit_partition,
        validation_partition,
    )

    with pytest.raises(
        PublicPoseRankingCalibrationTrainingViewError,
        match="incomplete or duplicated",
    ):
        replace(receipt, row_dispositions=receipt.row_dispositions[:-1])
    with pytest.raises(
        PublicPoseRankingCalibrationTrainingViewError,
        match="does not preserve",
    ):
        replace(
            receipt,
            training_partition=replace(
                receipt.training_partition,
                rows=receipt.training_partition.rows[:-1],
            ),
        )
    with pytest.raises(
        PublicPoseRankingCalibrationTrainingViewError,
        match="blockers do not match",
    ):
        replace(receipt, blockers=("forged_training_ready",))

    output = tmp_path / "training-view.json"
    receipt.write_json(output)
    assert os.stat(output, follow_symlinks=False).st_mode & 0o777 == 0o600
    assert json.loads(output.read_text(encoding="ascii"))[
        "receipt_sha256"
    ] == receipt.receipt_sha256
    with pytest.raises(
        PublicPoseRankingCalibrationTrainingViewError,
        match="exists",
    ):
        receipt.write_json(output)


def test_training_view_fit_bridge_rejects_term_schema_mismatch() -> None:
    fit, validation, test = _manifests()
    fit_partition, validation_partition = _partitions(fit, validation)
    receipt = _training_view(
        fit,
        validation,
        test,
        fit_partition,
        validation_partition,
    )

    with pytest.raises(
        PublicPoseRankingCalibrationTrainingViewError,
        match="receipt-bound calibration fit failed",
    ):
        fit_public_pose_ranking_calibration_training_view(
            receipt,
            PoseRankingCalibrationConfig(
                term_ids=("clash", "solvation"),
                iterations=10,
                trace_interval=5,
            ),
        )
