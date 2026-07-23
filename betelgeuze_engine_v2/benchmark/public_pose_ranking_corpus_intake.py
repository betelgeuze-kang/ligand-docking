"""Installable, claim-closed public pose-ranking corpus intake.

The intake binds caller-provided PDBbind-v2020 fit, CASF-2016 validation, and
PoseBusters-308 test manifests plus source-bound sequence-identity receipts.
It recomputes provenance/leakage contracts before any calibration partition,
score, label, model, or benchmark result is admitted.

No dataset bytes, license acceptance, sequence alignment execution, fitted
model, benchmark result, independent review, or public docking claim is
provided by this module.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date
import hashlib
import json
import math
from numbers import Real
import os
from pathlib import Path
import stat
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from .public_split_provenance import (
    CASF_2016_DATASET_ID,
    PDBBIND_V2020_DATASET_ID,
    POSEBUSTERS_2023_308_DATASET_ID,
    PUBLIC_DOCKING_DATASET_SPECS,
    PUBLIC_DOCKING_MAX_CASES,
    PublicDockingDatasetSource,
    PublicDockingLeakageAudit,
    PublicDockingLeakagePolicy,
    PublicDockingSequenceIdentityMethod,
    PublicDockingSequenceIdentityReceipt,
    PublicDockingSequenceIdentityRow,
    PublicDockingSplitCase,
    PublicDockingSplitError,
    PublicDockingSplitManifest,
    audit_public_docking_split_leakage,
)


PUBLIC_POSE_RANKING_CORPUS_INPUT_IDENTITY_SCHEMA_ID = (
    "betelgeuze.engine_v2_public_pose_ranking_corpus_input_identity/1.0.0"
)
PUBLIC_POSE_RANKING_CORPUS_AUDIT_SCHEMA_ID = (
    "betelgeuze.engine_v2_public_pose_ranking_corpus_audit/1.0.0"
)
PUBLIC_POSE_RANKING_CORPUS_INTAKE_RECEIPT_SCHEMA_ID = (
    "betelgeuze.engine_v2_public_pose_ranking_corpus_intake/1.0.0"
)
PUBLIC_POSE_RANKING_CORPUS_MAX_INPUT_BYTES = 64 * 1024 * 1024
PUBLIC_POSE_RANKING_CORPUS_MAX_RECEIPT_BYTES = 32 * 1024 * 1024

_INPUT_ROLES = (
    "fit_manifest",
    "validation_manifest",
    "test_manifest",
    "fit_validation_sequence",
    "fit_test_sequence",
    "validation_test_sequence",
)
_CROSS_EVALUATION_FIELDS = (
    "case_id",
    "pdb_id",
    "target_id",
    "receptor_sha256",
    "ligand_sha256",
    "scaffold_sha256",
    "target_sequence_set_sha256",
)
_SCIENTIFIC_BLOCKERS = (
    "dataset_bytes_and_license_acceptance_are_caller_managed",
    "sequence_alignment_evidence_is_verified_not_reexecuted",
    "calibration_partitions_and_pose_scores_are_absent",
    "fit_validation_and_test_labels_are_absent",
    "scorer_fit_and_model_selection_are_not_performed",
    "benchmark_metrics_and_confidence_intervals_are_absent",
    "independent_external_rerun_is_absent",
    "independent_scientific_review_is_absent",
    "public_docking_product_claim_is_not_authorized",
)


class PublicPoseRankingCorpusIntakeError(ValueError):
    """Public corpus input, leakage, or canonical receipt validation failed."""


def _plain_json(value: object) -> object:
    if isinstance(value, Mapping):
        return {
            str(key): _plain_json(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_plain_json(item) for item in value]
    return value


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            _plain_json(value),
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise PublicPoseRankingCorpusIntakeError(
            "public corpus value is not canonical JSON"
        ) from exc


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _digest(value: object, *, name: str) -> str:
    if not isinstance(value, str):
        raise PublicPoseRankingCorpusIntakeError(
            f"{name} must be a lowercase SHA-256"
        )
    digest = value.strip().lower()
    if len(digest) != 64 or any(
        character not in "0123456789abcdef" for character in digest
    ):
        raise PublicPoseRankingCorpusIntakeError(
            f"{name} must be a lowercase SHA-256"
        )
    return digest


def _text(value: object, *, name: str, maximum: int = 256) -> str:
    if not isinstance(value, str):
        raise PublicPoseRankingCorpusIntakeError(f"{name} must be text")
    text = value.strip()
    if not text or len(text) > maximum:
        raise PublicPoseRankingCorpusIntakeError(
            f"{name} must contain 1..{maximum} characters"
        )
    return text


def _integer(
    value: object,
    *,
    name: str,
    minimum: int = 0,
    maximum: int | None = None,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise PublicPoseRankingCorpusIntakeError(f"{name} must be an integer")
    integer = int(value)
    if integer < minimum or (maximum is not None and integer > maximum):
        raise PublicPoseRankingCorpusIntakeError(f"{name} is outside bounds")
    return integer


def _ratio(value: object, *, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise PublicPoseRankingCorpusIntakeError(f"{name} must be a ratio")
    ratio = float(value)
    if not math.isfinite(ratio) or ratio < 0.0 or ratio > 1.0:
        raise PublicPoseRankingCorpusIntakeError(f"{name} must be in [0,1]")
    return ratio


def _object(value: object, *, name: str) -> dict[str, Any]:
    if not isinstance(value, dict) or any(
        not isinstance(key, str) for key in value
    ):
        raise PublicPoseRankingCorpusIntakeError(
            f"{name} must be a JSON object with text keys"
        )
    return dict(value)


def _array(value: object, *, name: str) -> list[Any]:
    if not isinstance(value, list):
        raise PublicPoseRankingCorpusIntakeError(f"{name} must be a JSON array")
    return list(value)


def _exact_keys(
    value: Mapping[str, object],
    expected: set[str],
    *,
    name: str,
) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise PublicPoseRankingCorpusIntakeError(
            f"{name} keys differ; missing={missing}, extra={extra}"
        )


def _json_object_pairs(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise PublicPoseRankingCorpusIntakeError(
                f"duplicate JSON key: {key}"
            )
        result[key] = value
    return result


def _reject_json_constant(value: str) -> object:
    raise PublicPoseRankingCorpusIntakeError(
        f"non-finite JSON constant is forbidden: {value}"
    )


def _decode_json_object(data: bytes, *, name: str) -> dict[str, Any]:
    try:
        text = data.decode("ascii")
    except UnicodeDecodeError as exc:
        raise PublicPoseRankingCorpusIntakeError(
            f"{name} must be canonical ASCII JSON"
        ) from exc
    try:
        value = json.loads(
            text,
            object_pairs_hook=_json_object_pairs,
            parse_constant=_reject_json_constant,
        )
    except PublicPoseRankingCorpusIntakeError:
        raise
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise PublicPoseRankingCorpusIntakeError(
            f"{name} is not valid JSON"
        ) from exc
    return _object(value, name=name)


def _read_regular_file(
    path: str | os.PathLike[str],
    *,
    name: str,
    maximum_bytes: int,
) -> tuple[bytes, str]:
    candidate = Path(path)
    try:
        path_metadata = os.lstat(candidate)
    except OSError as exc:
        raise PublicPoseRankingCorpusIntakeError(
            f"{name} cannot be opened as a regular non-symlink file"
        ) from exc
    if stat.S_ISLNK(path_metadata.st_mode):
        raise PublicPoseRankingCorpusIntakeError(
            f"{name} cannot be opened as a regular non-symlink file"
        )
    flags = os.O_RDONLY
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(candidate, flags)
    except OSError as exc:
        raise PublicPoseRankingCorpusIntakeError(
            f"{name} cannot be opened as a regular non-symlink file"
        ) from exc
    try:
        metadata = os.fstat(descriptor)
        if (
            metadata.st_dev != path_metadata.st_dev
            or metadata.st_ino != path_metadata.st_ino
        ):
            raise PublicPoseRankingCorpusIntakeError(
                f"{name} changed before read"
            )
        if not stat.S_ISREG(metadata.st_mode):
            raise PublicPoseRankingCorpusIntakeError(
                f"{name} must be a regular file"
            )
        if metadata.st_size < 1 or metadata.st_size > maximum_bytes:
            raise PublicPoseRankingCorpusIntakeError(
                f"{name} size is outside the frozen bound"
            )
        chunks: list[bytes] = []
        remaining = metadata.st_size
        while remaining:
            chunk = os.read(descriptor, min(remaining, 1024 * 1024))
            if not chunk:
                raise PublicPoseRankingCorpusIntakeError(
                    f"{name} changed during read"
                )
            chunks.append(chunk)
            remaining -= len(chunk)
        if os.read(descriptor, 1):
            raise PublicPoseRankingCorpusIntakeError(
                f"{name} changed during read"
            )
        data = b"".join(chunks)
    finally:
        os.close(descriptor)
    return data, hashlib.sha256(data).hexdigest()


_SOURCE_KEYS = {
    "schema_id",
    "dataset",
    "archive_sha256",
    "archive_size_bytes",
    "selection_manifest_sha256",
    "license_terms_sha256",
    "access_authorization_receipt_sha256",
    "selection_review_receipt_sha256",
    "access_basis_present",
    "selection_evidence_present",
    "dataset_bytes_bundled",
    "redistribution_authorized_by_this_receipt",
}
_CASE_KEYS = {
    "schema_id",
    "dataset_id",
    "case_id",
    "pdb_id",
    "target_id",
    "target_family",
    "split_role",
    "release_date",
    "receptor_sha256",
    "ligand_sha256",
    "scaffold_sha256",
    "target_sequence_set_sha256",
    "cofactor_category",
    "chemistry_status",
}
_MANIFEST_KEYS = {
    "schema_id",
    "source",
    "source_sha256",
    "split_role",
    "partition_scope",
    "scoring_protocol_sha256",
    "preparation_profile_sha256",
    "case_count",
    "official_evaluation_case_count",
    "complete_official_case_set",
    "cases",
    "input_ready",
    "blockers",
    "benchmark_executed",
    "claim_safe",
}
_SEQUENCE_METHOD_KEYS = {
    "schema_id",
    "method_id",
    "tool_id",
    "tool_version",
    "executable_sha256",
    "configuration_sha256",
    "alignment",
    "substitution_matrix",
    "gap_open_score",
    "gap_extension_score",
    "identity_denominator",
    "chain_pair_policy",
}
_SEQUENCE_ROW_KEYS = {
    "schema_id",
    "evaluation_case_id",
    "closest_fit_case_id",
    "maximum_sequence_identity",
    "similarity_stratum",
    "fit_case_count",
    "comparison_evidence_sha256",
}
_SEQUENCE_RECEIPT_KEYS = {
    "schema_id",
    "fit_manifest_sha256",
    "evaluation_manifest_sha256",
    "method",
    "method_sha256",
    "rows",
    "case_count",
    "stratum_counts",
}


def _parse_dataset_source(value: object) -> PublicDockingDatasetSource:
    payload = _object(value, name="dataset source")
    _exact_keys(payload, _SOURCE_KEYS, name="dataset source")
    dataset = _object(payload["dataset"], name="dataset specification")
    dataset_id = _text(dataset.get("dataset_id"), name="dataset_id")
    if dataset_id not in PUBLIC_DOCKING_DATASET_SPECS:
        raise PublicPoseRankingCorpusIntakeError(
            "dataset source uses an unsupported dataset"
        )
    if dataset != PUBLIC_DOCKING_DATASET_SPECS[dataset_id].to_dict():
        raise PublicPoseRankingCorpusIntakeError(
            "dataset specification differs from the frozen catalog"
        )
    try:
        source = PublicDockingDatasetSource(
            schema_id=payload["schema_id"],
            dataset_id=dataset_id,
            archive_sha256=payload["archive_sha256"],
            archive_size_bytes=payload["archive_size_bytes"],
            selection_manifest_sha256=payload["selection_manifest_sha256"],
            license_terms_sha256=payload["license_terms_sha256"],
            access_authorization_receipt_sha256=payload[
                "access_authorization_receipt_sha256"
            ],
            selection_review_receipt_sha256=payload[
                "selection_review_receipt_sha256"
            ],
        )
    except (PublicDockingSplitError, TypeError) as exc:
        raise PublicPoseRankingCorpusIntakeError(
            "dataset source failed reconstruction"
        ) from exc
    if source.to_dict() != payload:
        raise PublicPoseRankingCorpusIntakeError(
            "dataset source derived fields do not reconstruct exactly"
        )
    return source


def _parse_split_case(value: object) -> PublicDockingSplitCase:
    payload = _object(value, name="split case")
    _exact_keys(payload, _CASE_KEYS, name="split case")
    try:
        case = PublicDockingSplitCase(**payload)
    except (PublicDockingSplitError, TypeError) as exc:
        raise PublicPoseRankingCorpusIntakeError(
            "split case failed reconstruction"
        ) from exc
    if case.to_dict() != payload:
        raise PublicPoseRankingCorpusIntakeError(
            "split case does not reconstruct exactly"
        )
    return case


def _parse_split_manifest(value: object) -> PublicDockingSplitManifest:
    payload = _object(value, name="split manifest")
    _exact_keys(payload, _MANIFEST_KEYS, name="split manifest")
    source = _parse_dataset_source(payload["source"])
    cases = tuple(
        _parse_split_case(item)
        for item in _array(payload["cases"], name="split manifest cases")
    )
    try:
        manifest = PublicDockingSplitManifest(
            schema_id=payload["schema_id"],
            source=source,
            split_role=payload["split_role"],
            partition_scope=payload["partition_scope"],
            scoring_protocol_sha256=payload["scoring_protocol_sha256"],
            preparation_profile_sha256=payload["preparation_profile_sha256"],
            cases=cases,
            complete_official_case_set=payload["complete_official_case_set"],
        )
    except (PublicDockingSplitError, TypeError) as exc:
        raise PublicPoseRankingCorpusIntakeError(
            "split manifest failed reconstruction"
        ) from exc
    if manifest.to_dict() != payload:
        raise PublicPoseRankingCorpusIntakeError(
            "split manifest derived fields do not reconstruct exactly"
        )
    return manifest


def _parse_sequence_method(
    value: object,
) -> PublicDockingSequenceIdentityMethod:
    payload = _object(value, name="sequence method")
    _exact_keys(payload, _SEQUENCE_METHOD_KEYS, name="sequence method")
    try:
        method = PublicDockingSequenceIdentityMethod(
            schema_id=payload["schema_id"],
            method_id=payload["method_id"],
            tool_id=payload["tool_id"],
            tool_version=payload["tool_version"],
            executable_sha256=payload["executable_sha256"],
            configuration_sha256=payload["configuration_sha256"],
        )
    except (PublicDockingSplitError, TypeError) as exc:
        raise PublicPoseRankingCorpusIntakeError(
            "sequence method failed reconstruction"
        ) from exc
    if method.to_dict() != payload:
        raise PublicPoseRankingCorpusIntakeError(
            "sequence method derived fields do not reconstruct exactly"
        )
    return method


def _parse_sequence_row(value: object) -> PublicDockingSequenceIdentityRow:
    payload = _object(value, name="sequence row")
    _exact_keys(payload, _SEQUENCE_ROW_KEYS, name="sequence row")
    try:
        row = PublicDockingSequenceIdentityRow(
            schema_id=payload["schema_id"],
            evaluation_case_id=payload["evaluation_case_id"],
            closest_fit_case_id=payload["closest_fit_case_id"],
            maximum_sequence_identity=payload["maximum_sequence_identity"],
            fit_case_count=payload["fit_case_count"],
            comparison_evidence_sha256=payload[
                "comparison_evidence_sha256"
            ],
        )
    except (PublicDockingSplitError, TypeError) as exc:
        raise PublicPoseRankingCorpusIntakeError(
            "sequence row failed reconstruction"
        ) from exc
    if row.to_dict() != payload:
        raise PublicPoseRankingCorpusIntakeError(
            "sequence row derived fields do not reconstruct exactly"
        )
    return row


def _parse_sequence_receipt(
    value: object,
) -> PublicDockingSequenceIdentityReceipt:
    payload = _object(value, name="sequence receipt")
    _exact_keys(payload, _SEQUENCE_RECEIPT_KEYS, name="sequence receipt")
    method = _parse_sequence_method(payload["method"])
    rows = tuple(
        _parse_sequence_row(item)
        for item in _array(payload["rows"], name="sequence receipt rows")
    )
    try:
        receipt = PublicDockingSequenceIdentityReceipt(
            schema_id=payload["schema_id"],
            fit_manifest_sha256=payload["fit_manifest_sha256"],
            evaluation_manifest_sha256=payload[
                "evaluation_manifest_sha256"
            ],
            method=method,
            rows=rows,
        )
    except (PublicDockingSplitError, TypeError) as exc:
        raise PublicPoseRankingCorpusIntakeError(
            "sequence receipt failed reconstruction"
        ) from exc
    if receipt.to_dict() != payload:
        raise PublicPoseRankingCorpusIntakeError(
            "sequence receipt derived fields do not reconstruct exactly"
        )
    return receipt


def _load_manifest_file(
    path: str | os.PathLike[str],
    *,
    expected_file_sha256: str,
    expected_manifest_sha256: str,
    role: str,
) -> tuple[PublicDockingSplitManifest, "PublicPoseRankingCorpusInputIdentity"]:
    expected_file = _digest(
        expected_file_sha256,
        name=f"{role} expected file SHA-256",
    )
    expected_manifest = _digest(
        expected_manifest_sha256,
        name=f"{role} expected manifest SHA-256",
    )
    data, file_sha256 = _read_regular_file(
        path,
        name=role,
        maximum_bytes=PUBLIC_POSE_RANKING_CORPUS_MAX_INPUT_BYTES,
    )
    if file_sha256 != expected_file:
        raise PublicPoseRankingCorpusIntakeError(
            f"{role} file SHA-256 mismatch"
        )
    manifest = _parse_split_manifest(_decode_json_object(data, name=role))
    canonical = _canonical_bytes(manifest.to_dict()) + b"\n"
    if data != canonical:
        raise PublicPoseRankingCorpusIntakeError(
            f"{role} must use canonical JSON plus one newline"
        )
    if manifest.fingerprint_sha256 != expected_manifest:
        raise PublicPoseRankingCorpusIntakeError(
            f"{role} manifest SHA-256 mismatch"
        )
    return manifest, PublicPoseRankingCorpusInputIdentity(
        role=role,
        source_file_sha256=file_sha256,
        source_file_size_bytes=len(data),
        payload_schema_id=manifest.schema_id,
        payload_sha256=manifest.fingerprint_sha256,
        row_count=len(manifest.cases),
    )


def _load_sequence_file(
    path: str | os.PathLike[str],
    *,
    expected_file_sha256: str,
    expected_receipt_sha256: str,
    role: str,
) -> tuple[
    PublicDockingSequenceIdentityReceipt,
    "PublicPoseRankingCorpusInputIdentity",
]:
    expected_file = _digest(
        expected_file_sha256,
        name=f"{role} expected file SHA-256",
    )
    expected_receipt = _digest(
        expected_receipt_sha256,
        name=f"{role} expected receipt SHA-256",
    )
    data, file_sha256 = _read_regular_file(
        path,
        name=role,
        maximum_bytes=PUBLIC_POSE_RANKING_CORPUS_MAX_INPUT_BYTES,
    )
    if file_sha256 != expected_file:
        raise PublicPoseRankingCorpusIntakeError(
            f"{role} file SHA-256 mismatch"
        )
    receipt = _parse_sequence_receipt(_decode_json_object(data, name=role))
    canonical = _canonical_bytes(receipt.to_dict()) + b"\n"
    if data != canonical:
        raise PublicPoseRankingCorpusIntakeError(
            f"{role} must use canonical JSON plus one newline"
        )
    if receipt.fingerprint_sha256 != expected_receipt:
        raise PublicPoseRankingCorpusIntakeError(
            f"{role} receipt SHA-256 mismatch"
        )
    return receipt, PublicPoseRankingCorpusInputIdentity(
        role=role,
        source_file_sha256=file_sha256,
        source_file_size_bytes=len(data),
        payload_schema_id=receipt.schema_id,
        payload_sha256=receipt.fingerprint_sha256,
        row_count=len(receipt.rows),
    )


def load_public_docking_split_manifest_file(
    path: str | os.PathLike[str],
    *,
    expected_file_sha256: str,
    expected_manifest_sha256: str,
) -> PublicDockingSplitManifest:
    """Load an exact canonical public split manifest without dataset bytes."""

    manifest, _ = _load_manifest_file(
        path,
        expected_file_sha256=expected_file_sha256,
        expected_manifest_sha256=expected_manifest_sha256,
        role="public_split_manifest",
    )
    return manifest


def load_public_docking_sequence_identity_receipt_file(
    path: str | os.PathLike[str],
    *,
    expected_file_sha256: str,
    expected_receipt_sha256: str,
) -> PublicDockingSequenceIdentityReceipt:
    """Load an exact canonical sequence-identity receipt."""

    receipt, _ = _load_sequence_file(
        path,
        expected_file_sha256=expected_file_sha256,
        expected_receipt_sha256=expected_receipt_sha256,
        role="public_sequence_identity_receipt",
    )
    return receipt


@dataclass(frozen=True, slots=True)
class PublicPoseRankingCorpusPolicy:
    maximum_fit_validation_sequence_identity: float = 0.90
    maximum_fit_test_sequence_identity: float = 0.90
    maximum_validation_test_sequence_identity: float = 0.90
    require_complete_official_validation: bool = True
    require_complete_official_test: bool = True
    require_fit_test_temporal_order: bool = True
    require_validation_test_temporal_order: bool = True
    require_sequence_method_identity_match: bool = True

    def __post_init__(self) -> None:
        for name in (
            "maximum_fit_validation_sequence_identity",
            "maximum_fit_test_sequence_identity",
            "maximum_validation_test_sequence_identity",
        ):
            object.__setattr__(
                self,
                name,
                _ratio(getattr(self, name), name=name),
            )
        for name in (
            "require_complete_official_validation",
            "require_complete_official_test",
            "require_fit_test_temporal_order",
            "require_validation_test_temporal_order",
            "require_sequence_method_identity_match",
        ):
            if not isinstance(getattr(self, name), bool):
                raise PublicPoseRankingCorpusIntakeError(
                    f"{name} must be boolean"
                )

    def to_dict(self) -> dict[str, Any]:
        return {
            "fit_dataset_id": PDBBIND_V2020_DATASET_ID,
            "fit_split_role": "fit",
            "fit_partition_scope": "calibration_fit",
            "validation_dataset_id": CASF_2016_DATASET_ID,
            "validation_split_role": "validation",
            "validation_partition_scope": "full_benchmark",
            "test_dataset_id": POSEBUSTERS_2023_308_DATASET_ID,
            "test_split_role": "test",
            "test_partition_scope": "full_benchmark",
            "maximum_fit_validation_sequence_identity": (
                self.maximum_fit_validation_sequence_identity
            ),
            "maximum_fit_test_sequence_identity": (
                self.maximum_fit_test_sequence_identity
            ),
            "maximum_validation_test_sequence_identity": (
                self.maximum_validation_test_sequence_identity
            ),
            "require_complete_official_validation": (
                self.require_complete_official_validation
            ),
            "require_complete_official_test": (
                self.require_complete_official_test
            ),
            "require_fit_test_temporal_order": (
                self.require_fit_test_temporal_order
            ),
            "require_validation_test_temporal_order": (
                self.require_validation_test_temporal_order
            ),
            "require_sequence_method_identity_match": (
                self.require_sequence_method_identity_match
            ),
            "require_case_pdb_target_receptor_ligand_scaffold_and_sequence_disjoint": True,
            "target_family_overlap_allowed_for_stratified_metrics": True,
            "test_labels_allowed_in_intake": False,
            "fit_or_model_selection_allowed_in_intake": False,
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())

    def fit_validation_policy(self) -> PublicDockingLeakagePolicy:
        return PublicDockingLeakagePolicy(
            maximum_allowed_target_sequence_identity=(
                self.maximum_fit_validation_sequence_identity
            ),
            require_temporal_order=False,
            require_complete_official_evaluation=(
                self.require_complete_official_validation
            ),
        )

    def fit_test_policy(self) -> PublicDockingLeakagePolicy:
        return PublicDockingLeakagePolicy(
            maximum_allowed_target_sequence_identity=(
                self.maximum_fit_test_sequence_identity
            ),
            require_temporal_order=self.require_fit_test_temporal_order,
            require_complete_official_evaluation=(
                self.require_complete_official_test
            ),
        )


FROZEN_PUBLIC_POSE_RANKING_CORPUS_POLICY = PublicPoseRankingCorpusPolicy()
PUBLIC_POSE_RANKING_CORPUS_INTAKE_CONFIGURATION: Mapping[str, Any] = (
    MappingProxyType(
        {
            "schema_id": (
                "betelgeuze.engine_v2_public_pose_ranking_corpus_intake_configuration/1.0.0"
            ),
            "policy": MappingProxyType(
                FROZEN_PUBLIC_POSE_RANKING_CORPUS_POLICY.to_dict()
            ),
            "input_roles": _INPUT_ROLES,
            "cross_evaluation_overlap_fields": _CROSS_EVALUATION_FIELDS,
            "canonical_input_encoding": (
                "sorted_ascii_json_without_whitespace_plus_one_newline"
            ),
            "receipt_write_policy": "mode_0600_no_overwrite",
        }
    )
)
PUBLIC_POSE_RANKING_CORPUS_INTAKE_CONFIGURATION_SHA256 = _canonical_sha256(
    dict(PUBLIC_POSE_RANKING_CORPUS_INTAKE_CONFIGURATION)
)


@dataclass(frozen=True, slots=True)
class PublicPoseRankingCorpusInputIdentity:
    role: str
    source_file_sha256: str
    source_file_size_bytes: int
    payload_schema_id: str
    payload_sha256: str
    row_count: int
    schema_id: str = PUBLIC_POSE_RANKING_CORPUS_INPUT_IDENTITY_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != PUBLIC_POSE_RANKING_CORPUS_INPUT_IDENTITY_SCHEMA_ID:
            raise PublicPoseRankingCorpusIntakeError(
                "unsupported corpus input-identity schema"
            )
        role = _text(self.role, name="input role")
        if role not in _INPUT_ROLES and role not in {
            "public_split_manifest",
            "public_sequence_identity_receipt",
        }:
            raise PublicPoseRankingCorpusIntakeError(
                "unsupported corpus input role"
            )
        object.__setattr__(self, "role", role)
        for name in ("source_file_sha256", "payload_sha256"):
            object.__setattr__(
                self,
                name,
                _digest(getattr(self, name), name=name),
            )
        object.__setattr__(
            self,
            "source_file_size_bytes",
            _integer(
                self.source_file_size_bytes,
                name="source file size",
                minimum=1,
                maximum=PUBLIC_POSE_RANKING_CORPUS_MAX_INPUT_BYTES,
            ),
        )
        object.__setattr__(
            self,
            "payload_schema_id",
            _text(self.payload_schema_id, name="payload schema ID"),
        )
        object.__setattr__(
            self,
            "row_count",
            _integer(
                self.row_count,
                name="input row count",
                minimum=1,
                maximum=PUBLIC_DOCKING_MAX_CASES,
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "role": self.role,
            "source_file_sha256": self.source_file_sha256,
            "source_file_size_bytes": self.source_file_size_bytes,
            "payload_schema_id": self.payload_schema_id,
            "payload_sha256": self.payload_sha256,
            "row_count": self.row_count,
        }


def _case_values(
    manifest: PublicDockingSplitManifest,
    field_name: str,
) -> set[str]:
    return {str(getattr(case, field_name)) for case in manifest.cases}


def _validate_corpus_roles(
    fit: PublicDockingSplitManifest,
    validation: PublicDockingSplitManifest,
    test: PublicDockingSplitManifest,
) -> None:
    expected = (
        (
            fit,
            PDBBIND_V2020_DATASET_ID,
            "fit",
            "calibration_fit",
            "fit",
        ),
        (
            validation,
            CASF_2016_DATASET_ID,
            "validation",
            "full_benchmark",
            "validation",
        ),
        (
            test,
            POSEBUSTERS_2023_308_DATASET_ID,
            "test",
            "full_benchmark",
            "test",
        ),
    )
    for manifest, dataset_id, split_role, scope, name in expected:
        if (
            manifest.source.dataset_id != dataset_id
            or manifest.split_role != split_role
            or manifest.partition_scope != scope
        ):
            raise PublicPoseRankingCorpusIntakeError(
                f"{name} manifest dataset, role, or scope is cross-wired"
            )


def _validate_cross_sequence_receipt(
    reference: PublicDockingSplitManifest,
    evaluation: PublicDockingSplitManifest,
    receipt: PublicDockingSequenceIdentityReceipt,
) -> None:
    if (
        receipt.fit_manifest_sha256 != reference.fingerprint_sha256
        or receipt.evaluation_manifest_sha256
        != evaluation.fingerprint_sha256
    ):
        raise PublicPoseRankingCorpusIntakeError(
            "validation-test sequence receipt does not bind its manifests"
        )
    if tuple(row.evaluation_case_id for row in receipt.rows) != tuple(
        case.case_id for case in evaluation.cases
    ):
        raise PublicPoseRankingCorpusIntakeError(
            "validation-test sequence receipt does not cover every test case"
        )
    reference_case_ids = {case.case_id for case in reference.cases}
    if any(
        row.closest_fit_case_id not in reference_case_ids
        or row.fit_case_count != len(reference.cases)
        for row in receipt.rows
    ):
        raise PublicPoseRankingCorpusIntakeError(
            "validation-test sequence comparison count or closest case is invalid"
        )


@dataclass(frozen=True, slots=True)
class PublicPoseRankingCorpusAudit:
    policy: PublicPoseRankingCorpusPolicy
    fit_manifest_sha256: str
    validation_manifest_sha256: str
    test_manifest_sha256: str
    fit_case_count: int
    validation_case_count: int
    test_case_count: int
    fit_validation_audit: PublicDockingLeakageAudit
    fit_test_audit: PublicDockingLeakageAudit
    validation_test_sequence_receipt_sha256: str
    validation_test_overlaps: Mapping[str, tuple[str, ...]]
    validation_test_temporal_violation_case_ids: tuple[str, ...]
    validation_test_sequence_violation_case_ids: tuple[str, ...]
    validation_test_sequence_stratum_counts: Mapping[str, int]
    sequence_method_sha256s: tuple[str, ...]
    blockers: tuple[str, ...]
    schema_id: str = PUBLIC_POSE_RANKING_CORPUS_AUDIT_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != PUBLIC_POSE_RANKING_CORPUS_AUDIT_SCHEMA_ID:
            raise PublicPoseRankingCorpusIntakeError(
                "unsupported public corpus audit schema"
            )
        if not isinstance(self.policy, PublicPoseRankingCorpusPolicy):
            raise PublicPoseRankingCorpusIntakeError(
                "public corpus audit policy has the wrong type"
            )
        for name in (
            "fit_manifest_sha256",
            "validation_manifest_sha256",
            "test_manifest_sha256",
            "validation_test_sequence_receipt_sha256",
        ):
            object.__setattr__(
                self,
                name,
                _digest(getattr(self, name), name=name),
            )
        for name in (
            "fit_case_count",
            "validation_case_count",
            "test_case_count",
        ):
            object.__setattr__(
                self,
                name,
                _integer(getattr(self, name), name=name, minimum=1),
            )
        if not isinstance(self.fit_validation_audit, PublicDockingLeakageAudit):
            raise PublicPoseRankingCorpusIntakeError(
                "fit-validation audit has the wrong type"
            )
        if not isinstance(self.fit_test_audit, PublicDockingLeakageAudit):
            raise PublicPoseRankingCorpusIntakeError(
                "fit-test audit has the wrong type"
            )
        expected_fit_validation_policy = self.policy.fit_validation_policy()
        if (
            self.fit_validation_audit.fit_manifest_sha256
            != self.fit_manifest_sha256
            or self.fit_validation_audit.evaluation_manifest_sha256
            != self.validation_manifest_sha256
            or self.fit_validation_audit.evaluation_case_count
            != self.validation_case_count
            or self.fit_validation_audit.policy.to_dict()
            != expected_fit_validation_policy.to_dict()
        ):
            raise PublicPoseRankingCorpusIntakeError(
                "fit-validation audit is not bound to the corpus audit"
            )
        expected_fit_test_policy = self.policy.fit_test_policy()
        if (
            self.fit_test_audit.fit_manifest_sha256
            != self.fit_manifest_sha256
            or self.fit_test_audit.evaluation_manifest_sha256
            != self.test_manifest_sha256
            or self.fit_test_audit.evaluation_case_count
            != self.test_case_count
            or self.fit_test_audit.policy.to_dict()
            != expected_fit_test_policy.to_dict()
        ):
            raise PublicPoseRankingCorpusIntakeError(
                "fit-test audit is not bound to the corpus audit"
            )
        overlaps = {
            _text(key, name="cross-evaluation overlap field"): tuple(
                sorted(
                    _text(item, name="cross-evaluation overlap identity")
                    for item in values
                )
            )
            for key, values in self.validation_test_overlaps.items()
        }
        if set(overlaps) != set(_CROSS_EVALUATION_FIELDS) or any(
            len(values) != len(set(values)) for values in overlaps.values()
        ):
            raise PublicPoseRankingCorpusIntakeError(
                "cross-evaluation overlaps are incomplete or duplicated"
            )
        temporal = tuple(
            sorted(
                _text(item, name="cross-evaluation temporal violation")
                for item in self.validation_test_temporal_violation_case_ids
            )
        )
        sequence = tuple(
            sorted(
                _text(item, name="cross-evaluation sequence violation")
                for item in self.validation_test_sequence_violation_case_ids
            )
        )
        if len(temporal) != len(set(temporal)) or len(sequence) != len(
            set(sequence)
        ):
            raise PublicPoseRankingCorpusIntakeError(
                "cross-evaluation violations must be unique"
            )
        strata = {
            _text(key, name="cross-evaluation sequence stratum"): _integer(
                value,
                name="cross-evaluation sequence stratum count",
                minimum=0,
            )
            for key, value in self.validation_test_sequence_stratum_counts.items()
        }
        expected_strata = {
            "low_0_to_30_percent",
            "medium_above_30_below_90_percent",
            "high_90_to_100_percent",
        }
        if set(strata) != expected_strata or sum(
            strata.values()
        ) != self.test_case_count:
            raise PublicPoseRankingCorpusIntakeError(
                "cross-evaluation sequence strata do not cover test cases"
            )
        methods = tuple(
            _digest(item, name="sequence method SHA-256")
            for item in self.sequence_method_sha256s
        )
        if len(methods) != 3:
            raise PublicPoseRankingCorpusIntakeError(
                "exactly three sequence method identities are required"
            )
        blockers = tuple(
            _text(item, name="public corpus audit blocker")
            for item in self.blockers
        )
        if len(blockers) != len(set(blockers)):
            raise PublicPoseRankingCorpusIntakeError(
                "public corpus audit blockers must be unique"
            )
        expected_blockers: list[str] = []
        expected_blockers.extend(
            f"fit_validation_{item}"
            for item in self.fit_validation_audit.blockers
        )
        expected_blockers.extend(
            f"fit_test_{item}" for item in self.fit_test_audit.blockers
        )
        expected_blockers.extend(
            f"validation_test_{field_name}_overlap"
            for field_name in _CROSS_EVALUATION_FIELDS
            if overlaps[field_name]
        )
        if temporal:
            expected_blockers.append(
                "validation_test_release_order_violation"
            )
        if sequence:
            expected_blockers.append(
                "validation_test_sequence_identity_threshold_exceeded"
            )
        if (
            self.policy.require_sequence_method_identity_match
            and len(set(methods)) != 1
        ):
            expected_blockers.append("sequence_method_identity_mismatch")
        if blockers != tuple(dict.fromkeys(expected_blockers)):
            raise PublicPoseRankingCorpusIntakeError(
                "public corpus audit blockers do not match the evidence"
            )
        object.__setattr__(
            self,
            "validation_test_overlaps",
            MappingProxyType(dict(sorted(overlaps.items()))),
        )
        object.__setattr__(
            self,
            "validation_test_temporal_violation_case_ids",
            temporal,
        )
        object.__setattr__(
            self,
            "validation_test_sequence_violation_case_ids",
            sequence,
        )
        object.__setattr__(
            self,
            "validation_test_sequence_stratum_counts",
            MappingProxyType(dict(sorted(strata.items()))),
        )
        object.__setattr__(self, "sequence_method_sha256s", methods)
        object.__setattr__(self, "blockers", blockers)

    @property
    def passed(self) -> bool:
        return not self.blockers

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "policy": self.policy.to_dict(),
            "policy_sha256": self.policy.fingerprint_sha256,
            "fit_manifest_sha256": self.fit_manifest_sha256,
            "validation_manifest_sha256": self.validation_manifest_sha256,
            "test_manifest_sha256": self.test_manifest_sha256,
            "fit_case_count": self.fit_case_count,
            "validation_case_count": self.validation_case_count,
            "test_case_count": self.test_case_count,
            "fit_validation_audit": self.fit_validation_audit.to_dict(),
            "fit_test_audit": self.fit_test_audit.to_dict(),
            "validation_test_sequence_receipt_sha256": (
                self.validation_test_sequence_receipt_sha256
            ),
            "validation_test_overlaps": {
                key: list(values)
                for key, values in self.validation_test_overlaps.items()
            },
            "validation_test_temporal_violation_case_ids": list(
                self.validation_test_temporal_violation_case_ids
            ),
            "validation_test_sequence_violation_case_ids": list(
                self.validation_test_sequence_violation_case_ids
            ),
            "validation_test_sequence_stratum_counts": dict(
                self.validation_test_sequence_stratum_counts
            ),
            "sequence_method_sha256s": list(self.sequence_method_sha256s),
            "blockers": list(self.blockers),
            "passed": self.passed,
            "ready_for_partition_materialization": self.passed,
            "test_labels_used": False,
            "fit_performed": False,
            "claim_safe": False,
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())


def audit_public_pose_ranking_corpus(
    fit_manifest: PublicDockingSplitManifest,
    validation_manifest: PublicDockingSplitManifest,
    test_manifest: PublicDockingSplitManifest,
    fit_validation_sequence_receipt: PublicDockingSequenceIdentityReceipt,
    fit_test_sequence_receipt: PublicDockingSequenceIdentityReceipt,
    validation_test_sequence_receipt: PublicDockingSequenceIdentityReceipt,
    *,
    policy: PublicPoseRankingCorpusPolicy | None = None,
) -> PublicPoseRankingCorpusAudit:
    """Recompute three-way provenance, exact, temporal, and sequence leakage."""

    active = policy or FROZEN_PUBLIC_POSE_RANKING_CORPUS_POLICY
    _validate_corpus_roles(fit_manifest, validation_manifest, test_manifest)
    try:
        fit_validation_audit = audit_public_docking_split_leakage(
            fit_manifest,
            validation_manifest,
            fit_validation_sequence_receipt,
            policy=active.fit_validation_policy(),
        )
        fit_test_audit = audit_public_docking_split_leakage(
            fit_manifest,
            test_manifest,
            fit_test_sequence_receipt,
            policy=active.fit_test_policy(),
        )
    except PublicDockingSplitError as exc:
        raise PublicPoseRankingCorpusIntakeError(
            "fit/evaluation leakage receipt failed reconstruction"
        ) from exc
    _validate_cross_sequence_receipt(
        validation_manifest,
        test_manifest,
        validation_test_sequence_receipt,
    )
    overlaps = {
        field_name: tuple(
            sorted(
                _case_values(validation_manifest, field_name)
                & _case_values(test_manifest, field_name)
            )
        )
        for field_name in _CROSS_EVALUATION_FIELDS
    }
    temporal_violations: tuple[str, ...] = ()
    if active.require_validation_test_temporal_order:
        latest_validation = max(
            date.fromisoformat(case.release_date)
            for case in validation_manifest.cases
        )
        temporal_violations = tuple(
            case.case_id
            for case in test_manifest.cases
            if date.fromisoformat(case.release_date) <= latest_validation
        )
    sequence_violations = tuple(
        row.evaluation_case_id
        for row in validation_test_sequence_receipt.rows
        if row.maximum_sequence_identity
        > active.maximum_validation_test_sequence_identity
    )
    methods = (
        fit_validation_sequence_receipt.method.fingerprint_sha256,
        fit_test_sequence_receipt.method.fingerprint_sha256,
        validation_test_sequence_receipt.method.fingerprint_sha256,
    )
    blockers: list[str] = []
    blockers.extend(
        f"fit_validation_{item}" for item in fit_validation_audit.blockers
    )
    blockers.extend(f"fit_test_{item}" for item in fit_test_audit.blockers)
    blockers.extend(
        f"validation_test_{field_name}_overlap"
        for field_name, values in overlaps.items()
        if values
    )
    if temporal_violations:
        blockers.append("validation_test_release_order_violation")
    if sequence_violations:
        blockers.append("validation_test_sequence_identity_threshold_exceeded")
    if (
        active.require_sequence_method_identity_match
        and len(set(methods)) != 1
    ):
        blockers.append("sequence_method_identity_mismatch")
    return PublicPoseRankingCorpusAudit(
        policy=active,
        fit_manifest_sha256=fit_manifest.fingerprint_sha256,
        validation_manifest_sha256=validation_manifest.fingerprint_sha256,
        test_manifest_sha256=test_manifest.fingerprint_sha256,
        fit_case_count=len(fit_manifest.cases),
        validation_case_count=len(validation_manifest.cases),
        test_case_count=len(test_manifest.cases),
        fit_validation_audit=fit_validation_audit,
        fit_test_audit=fit_test_audit,
        validation_test_sequence_receipt_sha256=(
            validation_test_sequence_receipt.fingerprint_sha256
        ),
        validation_test_overlaps=overlaps,
        validation_test_temporal_violation_case_ids=temporal_violations,
        validation_test_sequence_violation_case_ids=sequence_violations,
        validation_test_sequence_stratum_counts=(
            validation_test_sequence_receipt.stratum_counts
        ),
        sequence_method_sha256s=methods,
        blockers=tuple(dict.fromkeys(blockers)),
    )


@dataclass(frozen=True, slots=True)
class PublicPoseRankingCorpusIntakeReceipt:
    input_identities: tuple[PublicPoseRankingCorpusInputIdentity, ...]
    audit: PublicPoseRankingCorpusAudit
    schema_id: str = PUBLIC_POSE_RANKING_CORPUS_INTAKE_RECEIPT_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != PUBLIC_POSE_RANKING_CORPUS_INTAKE_RECEIPT_SCHEMA_ID:
            raise PublicPoseRankingCorpusIntakeError(
                "unsupported public corpus intake receipt schema"
            )
        identities = tuple(self.input_identities)
        if (
            len(identities) != len(_INPUT_ROLES)
            or any(
                not isinstance(item, PublicPoseRankingCorpusInputIdentity)
                for item in identities
            )
            or tuple(item.role for item in identities) != _INPUT_ROLES
        ):
            raise PublicPoseRankingCorpusIntakeError(
                "public corpus receipt requires six canonically ordered inputs"
            )
        if not isinstance(self.audit, PublicPoseRankingCorpusAudit):
            raise PublicPoseRankingCorpusIntakeError(
                "public corpus receipt audit has the wrong type"
            )
        if (
            self.audit.policy.fingerprint_sha256
            != FROZEN_PUBLIC_POSE_RANKING_CORPUS_POLICY.fingerprint_sha256
        ):
            raise PublicPoseRankingCorpusIntakeError(
                "installable corpus receipt must use the frozen policy"
            )
        expected_payload_sha256s = (
            self.audit.fit_manifest_sha256,
            self.audit.validation_manifest_sha256,
            self.audit.test_manifest_sha256,
            self.audit.fit_validation_audit.sequence_receipt_sha256,
            self.audit.fit_test_audit.sequence_receipt_sha256,
            self.audit.validation_test_sequence_receipt_sha256,
        )
        if (
            tuple(item.payload_sha256 for item in identities)
            != expected_payload_sha256s
        ):
            raise PublicPoseRankingCorpusIntakeError(
                "public corpus input payloads are not bound to the audit"
            )
        expected_row_counts = (
            self.audit.fit_case_count,
            self.audit.validation_case_count,
            self.audit.test_case_count,
            self.audit.validation_case_count,
            self.audit.test_case_count,
            self.audit.test_case_count,
        )
        if (
            tuple(item.row_count for item in identities)
            != expected_row_counts
        ):
            raise PublicPoseRankingCorpusIntakeError(
                "public corpus input row counts are not bound to the audit"
            )
        object.__setattr__(self, "input_identities", identities)

    def _payload_without_receipt_sha256(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "configuration": _plain_json(
                PUBLIC_POSE_RANKING_CORPUS_INTAKE_CONFIGURATION
            ),
            "configuration_sha256": (
                PUBLIC_POSE_RANKING_CORPUS_INTAKE_CONFIGURATION_SHA256
            ),
            "input_identities": [
                item.to_dict() for item in self.input_identities
            ],
            "audit": self.audit.to_dict(),
            "audit_sha256": self.audit.fingerprint_sha256,
            "ready_for_partition_materialization": self.audit.passed,
            "calibration_partitions_present": False,
            "pose_score_rows_present": False,
            "fit_or_model_selection_performed": False,
            "validation_labels_used_for_fit": False,
            "test_labels_present": False,
            "test_labels_used_for_fit": False,
            "test_labels_used_for_model_selection": False,
            "benchmark_executed": False,
            "independent_external_rerun_present": False,
            "independent_scientific_review_present": False,
            "scientifically_validated": False,
            "public_docking_claim_authorized": False,
            "claim_safe": False,
            "scientific_blockers": list(_SCIENTIFIC_BLOCKERS),
        }

    @property
    def receipt_sha256(self) -> str:
        return _canonical_sha256(self._payload_without_receipt_sha256())

    def to_dict(self) -> dict[str, Any]:
        payload = self._payload_without_receipt_sha256()
        payload["receipt_sha256"] = self.receipt_sha256
        return payload

    def write_json(self, path: str | os.PathLike[str]) -> None:
        destination = Path(path)
        if not destination.parent.is_dir():
            raise PublicPoseRankingCorpusIntakeError(
                "receipt output parent must already exist"
            )
        payload = _canonical_bytes(self.to_dict()) + b"\n"
        if len(payload) > PUBLIC_POSE_RANKING_CORPUS_MAX_RECEIPT_BYTES:
            raise PublicPoseRankingCorpusIntakeError(
                "public corpus receipt exceeds the frozen size bound"
            )
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_CLOEXEC"):
            flags |= os.O_CLOEXEC
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            descriptor = os.open(destination, flags, 0o600)
        except OSError as exc:
            raise PublicPoseRankingCorpusIntakeError(
                "receipt output exists or cannot be created safely"
            ) from exc
        try:
            view = memoryview(payload)
            while view:
                written = os.write(descriptor, view)
                if written <= 0:
                    raise PublicPoseRankingCorpusIntakeError(
                        "receipt write did not make progress"
                    )
                view = view[written:]
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def materialize_public_pose_ranking_corpus_intake(
    *,
    fit_manifest_path: str | os.PathLike[str],
    validation_manifest_path: str | os.PathLike[str],
    test_manifest_path: str | os.PathLike[str],
    fit_validation_sequence_receipt_path: str | os.PathLike[str],
    fit_test_sequence_receipt_path: str | os.PathLike[str],
    validation_test_sequence_receipt_path: str | os.PathLike[str],
    expected_fit_manifest_file_sha256: str,
    expected_fit_manifest_sha256: str,
    expected_validation_manifest_file_sha256: str,
    expected_validation_manifest_sha256: str,
    expected_test_manifest_file_sha256: str,
    expected_test_manifest_sha256: str,
    expected_fit_validation_sequence_file_sha256: str,
    expected_fit_validation_sequence_receipt_sha256: str,
    expected_fit_test_sequence_file_sha256: str,
    expected_fit_test_sequence_receipt_sha256: str,
    expected_validation_test_sequence_file_sha256: str,
    expected_validation_test_sequence_receipt_sha256: str,
) -> PublicPoseRankingCorpusIntakeReceipt:
    """Load six exact inputs and materialize the frozen corpus-readiness audit."""

    fit, fit_identity = _load_manifest_file(
        fit_manifest_path,
        expected_file_sha256=expected_fit_manifest_file_sha256,
        expected_manifest_sha256=expected_fit_manifest_sha256,
        role="fit_manifest",
    )
    validation, validation_identity = _load_manifest_file(
        validation_manifest_path,
        expected_file_sha256=expected_validation_manifest_file_sha256,
        expected_manifest_sha256=expected_validation_manifest_sha256,
        role="validation_manifest",
    )
    test, test_identity = _load_manifest_file(
        test_manifest_path,
        expected_file_sha256=expected_test_manifest_file_sha256,
        expected_manifest_sha256=expected_test_manifest_sha256,
        role="test_manifest",
    )
    fit_validation_sequence, fit_validation_identity = _load_sequence_file(
        fit_validation_sequence_receipt_path,
        expected_file_sha256=(
            expected_fit_validation_sequence_file_sha256
        ),
        expected_receipt_sha256=(
            expected_fit_validation_sequence_receipt_sha256
        ),
        role="fit_validation_sequence",
    )
    fit_test_sequence, fit_test_identity = _load_sequence_file(
        fit_test_sequence_receipt_path,
        expected_file_sha256=expected_fit_test_sequence_file_sha256,
        expected_receipt_sha256=(
            expected_fit_test_sequence_receipt_sha256
        ),
        role="fit_test_sequence",
    )
    validation_test_sequence, validation_test_identity = _load_sequence_file(
        validation_test_sequence_receipt_path,
        expected_file_sha256=(
            expected_validation_test_sequence_file_sha256
        ),
        expected_receipt_sha256=(
            expected_validation_test_sequence_receipt_sha256
        ),
        role="validation_test_sequence",
    )
    audit = audit_public_pose_ranking_corpus(
        fit,
        validation,
        test,
        fit_validation_sequence,
        fit_test_sequence,
        validation_test_sequence,
        policy=FROZEN_PUBLIC_POSE_RANKING_CORPUS_POLICY,
    )
    return PublicPoseRankingCorpusIntakeReceipt(
        input_identities=(
            fit_identity,
            validation_identity,
            test_identity,
            fit_validation_identity,
            fit_test_identity,
            validation_test_identity,
        ),
        audit=audit,
    )


def verify_public_pose_ranking_corpus_intake_receipt(
    *,
    corpus_receipt_path: str | os.PathLike[str],
    **materialization_arguments: Any,
) -> PublicPoseRankingCorpusIntakeReceipt:
    """Reconstruct and byte-compare one canonical intake receipt."""

    expected = materialize_public_pose_ranking_corpus_intake(
        **materialization_arguments
    )
    data, _ = _read_regular_file(
        corpus_receipt_path,
        name="public corpus intake receipt",
        maximum_bytes=PUBLIC_POSE_RANKING_CORPUS_MAX_RECEIPT_BYTES,
    )
    metadata = os.stat(corpus_receipt_path, follow_symlinks=False)
    if stat.S_IMODE(metadata.st_mode) != 0o600:
        raise PublicPoseRankingCorpusIntakeError(
            "public corpus intake receipt mode must be 0600"
        )
    expected_bytes = _canonical_bytes(expected.to_dict()) + b"\n"
    if data != expected_bytes:
        raise PublicPoseRankingCorpusIntakeError(
            "public corpus intake receipt differs from reconstruction"
        )
    return expected


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="betelgeuze-engine-v2-public-ranking-corpus-intake",
        description=(
            "Bind PDBbind fit, CASF validation, and PoseBusters test manifests "
            "without fitting or reading test labels."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("materialize", "verify"):
        subparser = subparsers.add_parser(command)
        for role in ("fit", "validation", "test"):
            subparser.add_argument(f"--{role}-manifest", required=True)
            subparser.add_argument(
                f"--expected-{role}-manifest-file-sha256",
                required=True,
            )
            subparser.add_argument(
                f"--expected-{role}-manifest-sha256",
                required=True,
            )
        for role in (
            "fit-validation",
            "fit-test",
            "validation-test",
        ):
            subparser.add_argument(
                f"--{role}-sequence-receipt",
                required=True,
            )
            subparser.add_argument(
                f"--expected-{role}-sequence-file-sha256",
                required=True,
            )
            subparser.add_argument(
                f"--expected-{role}-sequence-receipt-sha256",
                required=True,
            )
    subparsers.choices["materialize"].add_argument("--output", required=True)
    subparsers.choices["verify"].add_argument(
        "--corpus-receipt",
        required=True,
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    common: dict[str, Any] = {
        "fit_manifest_path": args.fit_manifest,
        "validation_manifest_path": args.validation_manifest,
        "test_manifest_path": args.test_manifest,
        "fit_validation_sequence_receipt_path": (
            args.fit_validation_sequence_receipt
        ),
        "fit_test_sequence_receipt_path": args.fit_test_sequence_receipt,
        "validation_test_sequence_receipt_path": (
            args.validation_test_sequence_receipt
        ),
        "expected_fit_manifest_file_sha256": (
            args.expected_fit_manifest_file_sha256
        ),
        "expected_fit_manifest_sha256": args.expected_fit_manifest_sha256,
        "expected_validation_manifest_file_sha256": (
            args.expected_validation_manifest_file_sha256
        ),
        "expected_validation_manifest_sha256": (
            args.expected_validation_manifest_sha256
        ),
        "expected_test_manifest_file_sha256": (
            args.expected_test_manifest_file_sha256
        ),
        "expected_test_manifest_sha256": args.expected_test_manifest_sha256,
        "expected_fit_validation_sequence_file_sha256": (
            args.expected_fit_validation_sequence_file_sha256
        ),
        "expected_fit_validation_sequence_receipt_sha256": (
            args.expected_fit_validation_sequence_receipt_sha256
        ),
        "expected_fit_test_sequence_file_sha256": (
            args.expected_fit_test_sequence_file_sha256
        ),
        "expected_fit_test_sequence_receipt_sha256": (
            args.expected_fit_test_sequence_receipt_sha256
        ),
        "expected_validation_test_sequence_file_sha256": (
            args.expected_validation_test_sequence_file_sha256
        ),
        "expected_validation_test_sequence_receipt_sha256": (
            args.expected_validation_test_sequence_receipt_sha256
        ),
    }
    if args.command == "materialize":
        receipt = materialize_public_pose_ranking_corpus_intake(**common)
        receipt.write_json(args.output)
    else:
        receipt = verify_public_pose_ranking_corpus_intake_receipt(
            corpus_receipt_path=args.corpus_receipt,
            **common,
        )
    print(
        json.dumps(
            {
                "receipt_sha256": receipt.receipt_sha256,
                "ready_for_partition_materialization": receipt.audit.passed,
                "fit_case_count": receipt.audit.fit_case_count,
                "validation_case_count": receipt.audit.validation_case_count,
                "test_case_count": receipt.audit.test_case_count,
                "readiness_blockers": list(receipt.audit.blockers),
                "test_labels_present": False,
                "fit_or_model_selection_performed": False,
                "claim_safe": False,
            },
            sort_keys=True,
        )
    )
    return 0


__all__ = [
    "FROZEN_PUBLIC_POSE_RANKING_CORPUS_POLICY",
    "PUBLIC_POSE_RANKING_CORPUS_AUDIT_SCHEMA_ID",
    "PUBLIC_POSE_RANKING_CORPUS_INPUT_IDENTITY_SCHEMA_ID",
    "PUBLIC_POSE_RANKING_CORPUS_INTAKE_CONFIGURATION",
    "PUBLIC_POSE_RANKING_CORPUS_INTAKE_CONFIGURATION_SHA256",
    "PUBLIC_POSE_RANKING_CORPUS_INTAKE_RECEIPT_SCHEMA_ID",
    "PUBLIC_POSE_RANKING_CORPUS_MAX_INPUT_BYTES",
    "PUBLIC_POSE_RANKING_CORPUS_MAX_RECEIPT_BYTES",
    "PublicPoseRankingCorpusAudit",
    "PublicPoseRankingCorpusInputIdentity",
    "PublicPoseRankingCorpusIntakeError",
    "PublicPoseRankingCorpusIntakeReceipt",
    "PublicPoseRankingCorpusPolicy",
    "audit_public_pose_ranking_corpus",
    "load_public_docking_sequence_identity_receipt_file",
    "load_public_docking_split_manifest_file",
    "materialize_public_pose_ranking_corpus_intake",
    "verify_public_pose_ranking_corpus_intake_receipt",
    "main",
]


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
