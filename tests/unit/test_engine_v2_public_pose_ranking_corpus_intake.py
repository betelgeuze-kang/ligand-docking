from __future__ import annotations

from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path

import pytest

from betelgeuze_engine_v2.benchmark.public_pose_ranking_corpus_intake import (
    FROZEN_PUBLIC_POSE_RANKING_CORPUS_POLICY,
    PUBLIC_POSE_RANKING_CORPUS_INTAKE_CONFIGURATION_SHA256,
    PublicPoseRankingCorpusIntakeError,
    PublicPoseRankingCorpusPolicy,
    audit_public_pose_ranking_corpus,
    load_public_docking_split_manifest_file,
    materialize_public_pose_ranking_corpus_intake,
    verify_public_pose_ranking_corpus_intake_receipt,
)
from betelgeuze_engine_v2.benchmark.public_split_provenance import (
    CASF_2016_DATASET_ID,
    PDBBIND_V2020_DATASET_ID,
    POSEBUSTERS_2023_308_DATASET_ID,
    POSEBUSTERS_2023_308_SELECTION_SHA256,
    POSEBUSTERS_2023_ARCHIVE_SHA256,
    POSEBUSTERS_2023_ARCHIVE_SIZE_BYTES,
    PublicDockingDatasetSource,
    PublicDockingSequenceIdentityMethod,
    PublicDockingSequenceIdentityReceipt,
    PublicDockingSequenceIdentityRow,
    PublicDockingSplitCase,
    PublicDockingSplitManifest,
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


def _method(salt: str = "shared") -> PublicDockingSequenceIdentityMethod:
    return PublicDockingSequenceIdentityMethod(
        tool_id="reviewed-smith-waterman",
        tool_version="1.0.0",
        executable_sha256=_sha(f"{salt}:executable"),
        configuration_sha256=_sha(f"{salt}:configuration"),
    )


def _sequence_receipt(
    reference: PublicDockingSplitManifest,
    evaluation: PublicDockingSplitManifest,
    *,
    identities: tuple[float, ...] = (0.20, 0.50),
    method_salt: str = "shared",
) -> PublicDockingSequenceIdentityReceipt:
    return PublicDockingSequenceIdentityReceipt(
        fit_manifest_sha256=reference.fingerprint_sha256,
        evaluation_manifest_sha256=evaluation.fingerprint_sha256,
        method=_method(method_salt),
        rows=tuple(
            PublicDockingSequenceIdentityRow(
                evaluation_case_id=case.case_id,
                closest_fit_case_id=(
                    reference.cases[index % len(reference.cases)].case_id
                ),
                maximum_sequence_identity=identities[index],
                fit_case_count=len(reference.cases),
                comparison_evidence_sha256=_sha(
                    f"{reference.source.dataset_id}:{case.case_id}:sequence"
                ),
            )
            for index, case in enumerate(evaluation.cases)
        ),
    )


def _development_policy() -> PublicPoseRankingCorpusPolicy:
    return PublicPoseRankingCorpusPolicy(
        maximum_fit_validation_sequence_identity=0.90,
        maximum_fit_test_sequence_identity=0.90,
        maximum_validation_test_sequence_identity=0.90,
        require_complete_official_validation=False,
        require_complete_official_test=False,
        require_fit_test_temporal_order=True,
        require_validation_test_temporal_order=True,
    )


def _write_canonical(path: Path, payload: object) -> tuple[str, int]:
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
    return hashlib.sha256(data).hexdigest(), len(data)


def _materialization_inputs(tmp_path: Path) -> dict[str, object]:
    fit, validation, test = _manifests()
    fit_validation = _sequence_receipt(fit, validation)
    fit_test = _sequence_receipt(fit, test)
    validation_test = _sequence_receipt(validation, test)
    payloads = {
        "fit_manifest": fit,
        "validation_manifest": validation,
        "test_manifest": test,
        "fit_validation_sequence": fit_validation,
        "fit_test_sequence": fit_test,
        "validation_test_sequence": validation_test,
    }
    arguments: dict[str, object] = {}
    for role, payload in payloads.items():
        path = tmp_path / f"{role}.json"
        file_sha256, _ = _write_canonical(path, payload.to_dict())
        if role.endswith("_manifest"):
            arguments[f"{role}_path"] = path
            arguments[f"expected_{role}_file_sha256"] = file_sha256
            arguments[f"expected_{role}_sha256"] = (
                payload.fingerprint_sha256
            )
        else:
            arguments[f"{role}_receipt_path"] = path
            arguments[f"expected_{role}_file_sha256"] = file_sha256
            arguments[f"expected_{role}_receipt_sha256"] = (
                payload.fingerprint_sha256
            )
    return arguments


def test_three_way_audit_can_pass_without_labels_under_development_policy() -> None:
    fit, validation, test = _manifests()
    audit = audit_public_pose_ranking_corpus(
        fit,
        validation,
        test,
        _sequence_receipt(fit, validation),
        _sequence_receipt(fit, test),
        _sequence_receipt(validation, test),
        policy=_development_policy(),
    )

    assert audit.passed
    assert audit.fit_case_count == 2
    assert audit.validation_case_count == 2
    assert audit.test_case_count == 2
    assert audit.validation_test_overlaps == {
        field: ()
        for field in (
            "case_id",
            "ligand_sha256",
            "pdb_id",
            "receptor_sha256",
            "scaffold_sha256",
            "target_id",
            "target_sequence_set_sha256",
        )
    }
    assert audit.to_dict()["test_labels_used"] is False
    assert audit.to_dict()["fit_performed"] is False


def test_three_way_audit_exposes_exact_temporal_sequence_and_method_leaks() -> None:
    fit, validation, test = _manifests()
    leaked_case = replace(
        test.cases[0],
        release_date="2016-01-01",
        scaffold_sha256=validation.cases[0].scaffold_sha256,
    )
    leaked_test = replace(test, cases=(leaked_case, test.cases[1]))
    audit = audit_public_pose_ranking_corpus(
        fit,
        validation,
        leaked_test,
        _sequence_receipt(fit, validation),
        _sequence_receipt(fit, leaked_test),
        _sequence_receipt(
            validation,
            leaked_test,
            identities=(0.95, 0.50),
            method_salt="different",
        ),
        policy=_development_policy(),
    )

    assert not audit.passed
    assert "validation_test_scaffold_sha256_overlap" in audit.blockers
    assert "validation_test_release_order_violation" in audit.blockers
    assert (
        "validation_test_sequence_identity_threshold_exceeded"
        in audit.blockers
    )
    assert "sequence_method_identity_mismatch" in audit.blockers
    assert audit.validation_test_temporal_violation_case_ids == ("t001",)
    assert audit.validation_test_sequence_violation_case_ids == ("t001",)


def test_frozen_intake_is_blocked_without_complete_official_case_sets(
    tmp_path: Path,
) -> None:
    receipt = materialize_public_pose_ranking_corpus_intake(
        **_materialization_inputs(tmp_path)
    )

    assert not receipt.audit.passed
    assert (
        "fit_validation_complete_official_evaluation_case_set_missing"
        in receipt.audit.blockers
    )
    assert (
        "fit_test_complete_official_evaluation_case_set_missing"
        in receipt.audit.blockers
    )
    assert receipt.to_dict()["test_labels_present"] is False
    assert receipt.to_dict()["fit_or_model_selection_performed"] is False
    assert "native_like" not in json.dumps(receipt.to_dict(), sort_keys=True)
    assert (
        receipt.to_dict()["configuration_sha256"]
        == PUBLIC_POSE_RANKING_CORPUS_INTAKE_CONFIGURATION_SHA256
    )
    assert (
        receipt.audit.policy.fingerprint_sha256
        == FROZEN_PUBLIC_POSE_RANKING_CORPUS_POLICY.fingerprint_sha256
    )


def test_receipt_write_is_mode_0600_no_overwrite_and_exactly_verifiable(
    tmp_path: Path,
) -> None:
    arguments = _materialization_inputs(tmp_path)
    receipt = materialize_public_pose_ranking_corpus_intake(**arguments)
    output = tmp_path / "corpus-intake.json"
    receipt.write_json(output)

    assert stat_mode(output) == 0o600
    verified = verify_public_pose_ranking_corpus_intake_receipt(
        corpus_receipt_path=output,
        **arguments,
    )
    assert verified.receipt_sha256 == receipt.receipt_sha256
    with pytest.raises(PublicPoseRankingCorpusIntakeError, match="exists"):
        receipt.write_json(output)


def stat_mode(path: Path) -> int:
    return os.stat(path, follow_symlinks=False).st_mode & 0o777


def test_manifest_loader_rejects_label_fields_and_noncanonical_json(
    tmp_path: Path,
) -> None:
    fit, _, _ = _manifests()
    labeled = fit.to_dict()
    labeled["cases"][0]["native_like"] = True
    labeled_path = tmp_path / "labeled.json"
    labeled_sha256, _ = _write_canonical(labeled_path, labeled)
    with pytest.raises(PublicPoseRankingCorpusIntakeError, match="keys differ"):
        load_public_docking_split_manifest_file(
            labeled_path,
            expected_file_sha256=labeled_sha256,
            expected_manifest_sha256=fit.fingerprint_sha256,
        )

    pretty_path = tmp_path / "pretty.json"
    pretty_data = json.dumps(fit.to_dict(), indent=2).encode("ascii") + b"\n"
    pretty_path.write_bytes(pretty_data)
    with pytest.raises(PublicPoseRankingCorpusIntakeError, match="canonical"):
        load_public_docking_split_manifest_file(
            pretty_path,
            expected_file_sha256=hashlib.sha256(pretty_data).hexdigest(),
            expected_manifest_sha256=fit.fingerprint_sha256,
        )


def test_manifest_loader_rejects_duplicate_keys_and_symlinks(
    tmp_path: Path,
) -> None:
    duplicate = tmp_path / "duplicate.json"
    duplicate_data = b'{"schema_id":"one","schema_id":"two"}\n'
    duplicate.write_bytes(duplicate_data)
    with pytest.raises(PublicPoseRankingCorpusIntakeError, match="duplicate"):
        load_public_docking_split_manifest_file(
            duplicate,
            expected_file_sha256=hashlib.sha256(duplicate_data).hexdigest(),
            expected_manifest_sha256=_sha("not-reached"),
        )

    fit, _, _ = _manifests()
    target = tmp_path / "target.json"
    target_sha256, _ = _write_canonical(target, fit.to_dict())
    link = tmp_path / "link.json"
    link.symlink_to(target)
    with pytest.raises(PublicPoseRankingCorpusIntakeError, match="non-symlink"):
        load_public_docking_split_manifest_file(
            link,
            expected_file_sha256=target_sha256,
            expected_manifest_sha256=fit.fingerprint_sha256,
        )


def test_crosswired_sequence_receipt_fails_before_audit() -> None:
    fit, validation, test = _manifests()
    with pytest.raises(
        PublicPoseRankingCorpusIntakeError,
        match="fit/evaluation leakage receipt",
    ):
        audit_public_pose_ranking_corpus(
            fit,
            validation,
            test,
            _sequence_receipt(fit, validation),
            _sequence_receipt(validation, test),
            _sequence_receipt(validation, test),
            policy=_development_policy(),
        )


def test_audit_rejects_forged_blockers() -> None:
    fit, validation, test = _manifests()
    audit = audit_public_pose_ranking_corpus(
        fit,
        validation,
        test,
        _sequence_receipt(fit, validation),
        _sequence_receipt(fit, test),
        _sequence_receipt(validation, test),
        policy=_development_policy(),
    )

    with pytest.raises(
        PublicPoseRankingCorpusIntakeError,
        match="blockers do not match",
    ):
        replace(audit, blockers=("forged_readiness",))
    with pytest.raises(
        PublicPoseRankingCorpusIntakeError,
        match="fit-validation audit is not bound",
    ):
        replace(
            audit,
            validation_manifest_sha256=_sha("crosswired-validation"),
        )


def test_receipt_rejects_crosswired_input_payload_roots(
    tmp_path: Path,
) -> None:
    receipt = materialize_public_pose_ranking_corpus_intake(
        **_materialization_inputs(tmp_path)
    )
    identities = list(receipt.input_identities)
    identities[0] = replace(
        identities[0],
        payload_sha256=identities[1].payload_sha256,
    )

    with pytest.raises(
        PublicPoseRankingCorpusIntakeError,
        match="payloads are not bound",
    ):
        replace(receipt, input_identities=tuple(identities))

    identities = list(receipt.input_identities)
    identities[0] = replace(
        identities[0],
        row_count=identities[0].row_count + 1,
    )
    with pytest.raises(
        PublicPoseRankingCorpusIntakeError,
        match="row counts are not bound",
    ):
        replace(receipt, input_identities=tuple(identities))

    with pytest.raises(
        PublicPoseRankingCorpusIntakeError,
        match="input row count is outside bounds",
    ):
        replace(receipt.input_identities[0], row_count=25_001)
