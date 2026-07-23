"""PoseBusters evaluation of pinned GNINA or Smina generated poses.

This evaluator consumes the exact public PoseBusters source chain and a
failure-inclusive external-binary execution receipt.  It preserves every
engine score component, every PoseBusters full-report value, every failed or
blocked case, and both all-case and engine-success denominators.  It does not
promote the narrow prepared subset to a public docking or product claim.
"""

from __future__ import annotations

from dataclasses import dataclass
import argparse
import json
import os
from pathlib import Path, PurePosixPath
import stat
import tempfile
from typing import Any, Sequence
import zipfile

from .public_posebusters_corpus_audit import (
    _canonical_bytes,
    _canonical_sha256,
    _positive_int,
    _source_file_sha256,
    _token,
)
from .public_posebusters_external_binary_execution import (
    POSEBUSTERS_EXTERNAL_BINARY_ARTIFACT_SCHEMA_ID,
    POSEBUSTERS_EXTERNAL_BINARY_CASE_SCHEMA_ID,
    POSEBUSTERS_EXTERNAL_BINARY_CONFIGURATION_SHA256,
    POSEBUSTERS_EXTERNAL_BINARY_CONFIGURATIONS,
    POSEBUSTERS_EXTERNAL_BINARY_EXECUTION_SCHEMA_ID,
    POSEBUSTERS_EXTERNAL_BINARY_MAX_POSE_ARTIFACT_BYTES,
    POSEBUSTERS_EXTERNAL_BINARY_MAX_RECEIPT_BYTES,
    POSEBUSTERS_EXTERNAL_BINARY_SCORE_SCHEMA_ID,
    _ENGINE_SPECS,
)
from .public_posebusters_external_preparation import (
    PoseBustersExternalPreparationError,
    _verify_artifact_tree,
    verify_posebusters_external_preparation_receipt,
)
from .public_posebusters_generated_pose_evaluation import (
    POSEBUSTERS_GENERATED_POSE_CONFIGURATION,
    POSEBUSTERS_GENERATED_POSE_CONFIGURATION_SHA256,
    POSEBUSTERS_GENERATED_POSE_MAX_REPORT_VALUES,
    POSEBUSTERS_GENERATED_POSE_SELECTED_COLUMNS,
    PoseBustersGeneratedPoseCaseError,
    PoseBustersGeneratedPoseMetric,
    PoseBustersGeneratedPoseReportValue,
    PoseBustersGeneratedPoseRuntimeIdentity,
    _PoseBustersRuntimeProtocol,
    _RuntimePoseOutcome,
    _GEOMETRY_COLUMNS,
    _IDENTITY_COLUMNS,
    _INTERMOLECULAR_COLUMNS,
    _binary64_value,
    _boolean_value,
    _case_id,
    _digest,
    _hash_bytes,
    _identifier,
    _load_posebusters_runtime,
    _metric,
    _normalize_error,
    _read_archive_sources,
    _relative_path,
    _validate_hex,
)
from .public_posebusters_intake import (
    OFFICIAL_POSEBUSTERS_ARCHIVE_CONTRACT,
    PoseBustersArchiveContract,
    PoseBustersArchiveIntakeError,
    _hash_descriptor,
    _read_exact_regular_file,
    _regular_file_descriptor,
    verify_posebusters_archive_intake_receipt,
)


POSEBUSTERS_EXTERNAL_GENERATED_POSE_RESULT_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_external_generated_pose_result/1.0.0"
)
POSEBUSTERS_EXTERNAL_GENERATED_POSE_CASE_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_external_generated_pose_case/1.0.0"
)
POSEBUSTERS_EXTERNAL_GENERATED_POSE_EVALUATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_external_generated_pose_evaluation/1.0.0"
)
POSEBUSTERS_EXTERNAL_GENERATED_POSE_MAX_RECEIPT_BYTES = 64 * 1024 * 1024
POSEBUSTERS_EXTERNAL_GENERATED_POSE_ENGINES = ("gnina", "smina")
POSEBUSTERS_EXTERNAL_GENERATED_POSE_BLOCKERS = (
    "only_strictly_prepared_chemistry_subset_evaluated",
    "prepared_autodock_type_scope_not_closed",
    "target_family_and_leakage_receipts_missing",
    "independent_external_host_evaluation_rerun_missing",
    "independent_scientific_review_missing",
    "public_docking_benchmark_claim_not_authorized",
)

_EXECUTION_STATUSES = {
    "success",
    "engine_failure",
    "blocked_preparation_failure",
    "blocked_upstream_failure",
    "abstain_chemistry_scope",
}
_EVALUATION_CASE_STATUSES = {
    "evaluated",
    "partial_evaluation",
    "evaluation_failure",
    "blocked_engine_failure",
    "blocked_preparation_failure",
    "blocked_upstream_failure",
    "abstain_chemistry_scope",
}


class PoseBustersExternalGeneratedPoseEvaluationError(ValueError):
    """External execution input or generated-pose evaluation is invalid."""


def _engine_id(value: object) -> str:
    engine = _token(value, name="external generated-pose engine")
    if engine not in POSEBUSTERS_EXTERNAL_GENERATED_POSE_ENGINES:
        raise PoseBustersExternalGeneratedPoseEvaluationError(
            "external generated-pose engine must be gnina or smina"
        )
    return engine


@dataclass(frozen=True, slots=True)
class _ExternalArtifactView:
    relative_path: str
    sha256: str
    size_bytes: int
    raw: dict[str, Any]


@dataclass(frozen=True, slots=True)
class _ExternalCaseView:
    case_id: str
    status: str
    preparation_status: str
    pose_count: int
    score_components_binary64_hex: tuple[tuple[str, ...], ...]
    artifact: _ExternalArtifactView | None
    error_code: str


@dataclass(frozen=True, slots=True)
class _ExternalReceiptView:
    engine_id: str
    receipt_sha256: str
    receipt_file_sha256: str
    artifact_set_sha256: str
    preparation_receipt_sha256: str
    preparation_receipt_file_sha256: str
    preparation_artifact_set_sha256: str
    preparation_runtime_identity_sha256: str
    configuration_sha256: str
    score_component_order: tuple[str, ...]
    case_rows: tuple[_ExternalCaseView, ...]


def _load_external_execution_receipt(
    engine_id: str,
    receipt_path: str | os.PathLike[str],
    artifact_root: str | os.PathLike[str],
    *,
    expected_receipt_sha256: str,
    expected_preparation_receipt_sha256: str,
    expected_preparation_receipt_file_sha256: str,
    expected_preparation_artifact_set_sha256: str,
) -> tuple[_ExternalReceiptView, dict[str, bytes]]:
    engine = _engine_id(engine_id)
    expected_sha = _digest(
        expected_receipt_sha256,
        name="expected external execution receipt",
    )
    source = _read_exact_regular_file(
        receipt_path,
        maximum_bytes=POSEBUSTERS_EXTERNAL_BINARY_MAX_RECEIPT_BYTES,
    )
    try:
        metadata = Path(receipt_path).stat(follow_symlinks=False)
    except OSError as exc:
        raise PoseBustersExternalGeneratedPoseEvaluationError(
            "external execution receipt metadata is unavailable"
        ) from exc
    if stat.S_IMODE(metadata.st_mode) != 0o600:
        raise PoseBustersExternalGeneratedPoseEvaluationError(
            "external execution receipt must remain mode 0600"
        )
    try:
        raw = json.loads(source)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PoseBustersExternalGeneratedPoseEvaluationError(
            "external execution receipt is not canonical JSON"
        ) from exc
    if not isinstance(raw, dict) or source != _canonical_bytes(raw) + b"\n":
        raise PoseBustersExternalGeneratedPoseEvaluationError(
            "external execution receipt bytes are not canonical"
        )
    receipt_sha = raw.get("receipt_sha256")
    payload = dict(raw)
    payload.pop("receipt_sha256", None)
    source_members = raw.get("implementation_source_members")
    runtime_identity = raw.get("runtime_identity")
    spec = _ENGINE_SPECS[engine]
    expected_source_members = {
        "external_binary_execution": _source_file_sha256(
            Path(__file__).with_name(
                "public_posebusters_external_binary_execution.py"
            )
        ),
        "external_preparation_contract": _source_file_sha256(
            Path(__file__).with_name(
                "public_posebusters_external_preparation.py"
            )
        ),
        "preparation_receipt_loader": _source_file_sha256(
            Path(__file__).with_name("public_posebusters_vina_execution.py")
        ),
    }
    if (
        raw.get("schema_id") != POSEBUSTERS_EXTERNAL_BINARY_EXECUTION_SCHEMA_ID
        or raw.get("engine_id") != engine
        or not isinstance(receipt_sha, str)
        or _canonical_sha256(payload) != receipt_sha
        or receipt_sha != expected_sha
        or raw.get("configuration_sha256")
        != POSEBUSTERS_EXTERNAL_BINARY_CONFIGURATION_SHA256[engine]
        or raw.get("configuration")
        != POSEBUSTERS_EXTERNAL_BINARY_CONFIGURATIONS[engine]
        or raw.get("preparation_receipt_sha256")
        != expected_preparation_receipt_sha256
        or raw.get("preparation_receipt_file_sha256")
        != expected_preparation_receipt_file_sha256
        or raw.get("preparation_artifact_set_sha256")
        != expected_preparation_artifact_set_sha256
        or raw.get("benchmark_executed") is not False
        or raw.get("claim_safe") is not False
        or not isinstance(source_members, dict)
        or source_members != expected_source_members
        or _canonical_sha256(source_members)
        != raw.get("implementation_source_sha256")
        or not isinstance(runtime_identity, dict)
        or _canonical_sha256(runtime_identity)
        != raw.get("runtime_identity_sha256")
        or runtime_identity.get("engine_id") != engine
        or runtime_identity.get("engine_version") != spec["version"]
        or runtime_identity.get("executable_sha256")
        != spec["executable_sha256"]
        or runtime_identity.get("executable_size_bytes")
        != spec["executable_size_bytes"]
    ):
        raise PoseBustersExternalGeneratedPoseEvaluationError(
            "external execution receipt contract or runtime identity is invalid"
        )
    preparation_runtime_sha = raw.get("preparation_runtime_identity_sha256")
    if not isinstance(preparation_runtime_sha, str):
        raise PoseBustersExternalGeneratedPoseEvaluationError(
            "external execution preparation runtime identity is missing"
        )
    score_order = tuple(spec["score_components"])
    raw_rows = raw.get("case_rows")
    if (
        not isinstance(raw_rows, list)
        or not raw_rows
        or raw.get("all_case_denominator") != len(raw_rows)
    ):
        raise PoseBustersExternalGeneratedPoseEvaluationError(
            "external execution case denominator is invalid"
        )
    rows: list[_ExternalCaseView] = []
    payloads: dict[str, bytes] = {}
    artifact_projection: dict[str, dict[str, Any]] = {}
    for raw_row in raw_rows:
        if not isinstance(raw_row, dict):
            raise PoseBustersExternalGeneratedPoseEvaluationError(
                "external execution case row must be an object"
            )
        case = _case_id(raw_row.get("case_id"))
        status = str(raw_row.get("status", ""))
        preparation_status = str(raw_row.get("preparation_status", ""))
        if (
            raw_row.get("schema_id")
            != POSEBUSTERS_EXTERNAL_BINARY_CASE_SCHEMA_ID
            or raw_row.get("engine_id") != engine
            or status not in _EXECUTION_STATUSES
            or tuple(raw_row.get("score_component_order", ()))
            != score_order
            or raw_row.get("generated_pose_present")
            is not (status == "success")
            or raw_row.get("pose_validity_evaluated") is not False
            or raw_row.get("symmetry_aware_rmsd_evaluated") is not False
        ):
            raise PoseBustersExternalGeneratedPoseEvaluationError(
                "external execution case contract is invalid"
            )
        center = tuple(
            _validate_hex(
                value,
                name="external execution pocket center",
            )
            for value in raw_row.get("pocket_center_binary64_hex", ())
        )
        attempted = raw_row.get("engine_attempted")
        diagnostic_size = _positive_int(
            raw_row.get("diagnostic_size_bytes"),
            name="external execution diagnostic size",
            allow_zero=True,
        )
        pose_count = _positive_int(
            raw_row.get("pose_count"),
            name="external execution pose count",
            allow_zero=True,
        )
        raw_scores = raw_row.get("pose_scores")
        if not isinstance(raw_scores, list):
            raise PoseBustersExternalGeneratedPoseEvaluationError(
                "external execution score rows are invalid"
            )
        scores: list[tuple[str, ...]] = []
        for expected_rank, raw_score in enumerate(raw_scores, start=1):
            if (
                not isinstance(raw_score, dict)
                or raw_score.get("schema_id")
                != POSEBUSTERS_EXTERNAL_BINARY_SCORE_SCHEMA_ID
                or raw_score.get("pose_rank") != expected_rank
                or tuple(raw_score.get("score_component_order", ()))
                != score_order
            ):
                raise PoseBustersExternalGeneratedPoseEvaluationError(
                    "external execution score identity is invalid"
                )
            raw_components = raw_score.get("components_binary64_hex")
            if not isinstance(raw_components, list):
                raise PoseBustersExternalGeneratedPoseEvaluationError(
                    "external execution score components are invalid"
                )
            components = tuple(
                _validate_hex(value, name="external execution score")
                for value in raw_components
            )
            if len(components) != len(score_order):
                raise PoseBustersExternalGeneratedPoseEvaluationError(
                    "external execution score component count is invalid"
                )
            if raw_score.get("components") != dict(
                zip(score_order, components)
            ):
                raise PoseBustersExternalGeneratedPoseEvaluationError(
                    "external execution score component map is invalid"
                )
            scores.append(components)
        raw_artifact = raw_row.get("pose_artifact")
        artifact: _ExternalArtifactView | None = None
        if raw_artifact is not None:
            if (
                not isinstance(raw_artifact, dict)
                or raw_artifact.get("schema_id")
                != POSEBUSTERS_EXTERNAL_BINARY_ARTIFACT_SCHEMA_ID
                or raw_artifact.get("role")
                != f"{engine}_generated_poses_pdbqt"
                or raw_artifact.get("engine_id") != engine
                or raw_artifact.get("media_type") != "chemical/x-pdbqt"
            ):
                raise PoseBustersExternalGeneratedPoseEvaluationError(
                    "external execution pose artifact schema is invalid"
                )
            relative = _relative_path(raw_artifact.get("relative_path"))
            relative_parts = PurePosixPath(relative).parts
            if relative_parts != (case, "poses.pdbqt"):
                raise PoseBustersExternalGeneratedPoseEvaluationError(
                    "external execution pose artifact path is cross-wired"
                )
            for name in ("prepared_receptor_sha256", "prepared_ligand_sha256"):
                _digest(
                    raw_artifact.get(name),
                    name=f"external execution artifact {name}",
                )
            digest = _digest(
                raw_artifact.get("sha256"),
                name="external execution pose artifact",
            )
            size = _positive_int(
                raw_artifact.get("size_bytes"),
                name="external execution pose artifact size",
            )
            if size > POSEBUSTERS_EXTERNAL_BINARY_MAX_POSE_ARTIFACT_BYTES:
                raise PoseBustersExternalGeneratedPoseEvaluationError(
                    "external execution pose artifact exceeds its bound"
                )
            observed = _read_exact_regular_file(
                Path(artifact_root) / relative,
                maximum_bytes=POSEBUSTERS_EXTERNAL_BINARY_MAX_POSE_ARTIFACT_BYTES,
            )
            if len(observed) != size or _hash_bytes(observed) != digest:
                raise PoseBustersExternalGeneratedPoseEvaluationError(
                    "external execution pose artifact does not match its receipt"
                )
            if relative in payloads:
                raise PoseBustersExternalGeneratedPoseEvaluationError(
                    "external execution pose artifact path is duplicated"
                )
            payloads[relative] = observed
            artifact_projection[case] = dict(raw_artifact)
            artifact = _ExternalArtifactView(
                relative_path=relative,
                sha256=digest,
                size_bytes=size,
                raw=dict(raw_artifact),
            )
        expected_preparation_status = {
            "success": "prepared",
            "engine_failure": "prepared",
            "blocked_preparation_failure": "preparation_failure",
            "blocked_upstream_failure": "upstream_failure",
            "abstain_chemistry_scope": "abstain_chemistry_scope",
        }[status]
        valid = preparation_status == expected_preparation_status
        if status == "success":
            valid = (
                valid
                and attempted is True
                and len(center) == 3
                and pose_count > 0
                and len(scores) == pose_count
                and artifact is not None
                and not any(
                    raw_row.get(name)
                    for name in (
                        "error_stage",
                        "error_code",
                        "error_type",
                        "error_message_sha256",
                    )
                )
                and bool(raw_row.get("diagnostic_sha256"))
            )
        elif status == "engine_failure":
            valid = (
                valid
                and attempted is True
                and len(center) == 3
                and pose_count == 0
                and not scores
                and artifact is None
                and all(
                    raw_row.get(name)
                    for name in (
                        "error_stage",
                        "error_code",
                        "error_type",
                        "error_message_sha256",
                        "diagnostic_sha256",
                    )
                )
            )
        else:
            valid = (
                valid
                and attempted is False
                and not center
                and pose_count == 0
                and not scores
                and artifact is None
                and not any(
                    (
                        raw_row.get("error_stage"),
                        raw_row.get("error_type"),
                        raw_row.get("error_message_sha256"),
                        raw_row.get("diagnostic_sha256"),
                        diagnostic_size,
                    )
                )
            )
        if not valid:
            raise PoseBustersExternalGeneratedPoseEvaluationError(
                "external execution case disposition is inconsistent"
            )
        error_code = raw_row.get("error_code")
        if not isinstance(error_code, str):
            raise PoseBustersExternalGeneratedPoseEvaluationError(
                "external execution case error code must be text"
            )
        if raw_row.get("diagnostic_sha256"):
            _digest(
                raw_row.get("diagnostic_sha256"),
                name="external execution diagnostic",
            )
        rows.append(
            _ExternalCaseView(
                case_id=case,
                status=status,
                preparation_status=preparation_status,
                pose_count=pose_count,
                score_components_binary64_hex=tuple(scores),
                artifact=artifact,
                error_code=error_code,
            )
        )
    rows_tuple = tuple(rows)
    if (
        tuple(row.case_id for row in rows_tuple)
        != tuple(sorted(row.case_id for row in rows_tuple))
        or len({row.case_id for row in rows_tuple}) != len(rows_tuple)
        or raw.get("attempted_case_count")
        != sum(row.status in {"success", "engine_failure"} for row in rows_tuple)
        or raw.get("success_case_count")
        != sum(row.status == "success" for row in rows_tuple)
        or raw.get("engine_failure_case_count")
        != sum(row.status == "engine_failure" for row in rows_tuple)
        or raw.get("generated_pose_count")
        != sum(row.pose_count for row in rows_tuple)
        or _canonical_sha256(artifact_projection)
        != raw.get("artifact_set_sha256")
    ):
        raise PoseBustersExternalGeneratedPoseEvaluationError(
            "external execution rows or artifact-set identity are inconsistent"
        )
    try:
        _verify_artifact_tree(Path(artifact_root), payloads)
    except PoseBustersExternalPreparationError as exc:
        raise PoseBustersExternalGeneratedPoseEvaluationError(
            "external execution artifact tree failed exact verification"
        ) from exc
    return (
        _ExternalReceiptView(
            engine_id=engine,
            receipt_sha256=receipt_sha,
            receipt_file_sha256=_hash_bytes(source),
            artifact_set_sha256=_digest(
                raw.get("artifact_set_sha256"),
                name="external execution artifact set",
            ),
            preparation_receipt_sha256=expected_preparation_receipt_sha256,
            preparation_receipt_file_sha256=(
                expected_preparation_receipt_file_sha256
            ),
            preparation_artifact_set_sha256=(
                expected_preparation_artifact_set_sha256
            ),
            preparation_runtime_identity_sha256=_digest(
                preparation_runtime_sha,
                name="external execution preparation runtime identity",
            ),
            configuration_sha256=(
                POSEBUSTERS_EXTERNAL_BINARY_CONFIGURATION_SHA256[engine]
            ),
            score_component_order=score_order,
            case_rows=rows_tuple,
        ),
        payloads,
    )


@dataclass(frozen=True, slots=True)
class PoseBustersExternalGeneratedPoseResult:
    engine_id: str
    pose_rank: int
    score_components_binary64_hex: tuple[str, ...]
    status: str
    report_values: tuple[PoseBustersGeneratedPoseReportValue, ...] = ()
    all_non_rmsd_binary_tests_pass: bool = False
    identity_pass: bool = False
    intramolecular_geometry_pass: bool = False
    internal_energy_pass: bool = False
    intermolecular_distance_and_overlap_pass: bool = False
    rmsd_evaluated: bool = False
    rmsd_within_2_angstrom: bool = False
    direct_rmsd_angstrom_binary64_hex: str = ""
    kabsch_rmsd_angstrom_binary64_hex: str = ""
    centroid_distance_angstrom_binary64_hex: str = ""
    energy_ratio_binary64_hex: str = ""
    error_stage: str = ""
    error_code: str = ""
    error_type: str = ""
    error_message_sha256: str = ""
    diagnostic_sha256: str = ""
    diagnostic_size_bytes: int = 0
    schema_id: str = POSEBUSTERS_EXTERNAL_GENERATED_POSE_RESULT_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_EXTERNAL_GENERATED_POSE_RESULT_SCHEMA_ID:
            raise PoseBustersExternalGeneratedPoseEvaluationError(
                "unsupported external generated-pose result schema"
            )
        engine = _engine_id(self.engine_id)
        rank = _positive_int(
            self.pose_rank,
            name="external generated-pose rank",
        )
        if self.status not in {"evaluated", "evaluation_failure"}:
            raise PoseBustersExternalGeneratedPoseEvaluationError(
                "external generated-pose result status is invalid"
            )
        scores = tuple(
            _validate_hex(value, name="external generated-pose score")
            for value in self.score_components_binary64_hex
        )
        if len(scores) != len(_ENGINE_SPECS[engine]["score_components"]):
            raise PoseBustersExternalGeneratedPoseEvaluationError(
                "external generated-pose score component count is invalid"
            )
        report = tuple(self.report_values)
        if (
            len(report) > POSEBUSTERS_GENERATED_POSE_MAX_REPORT_VALUES
            or tuple(row.ordinal for row in report) != tuple(range(len(report)))
        ):
            raise PoseBustersExternalGeneratedPoseEvaluationError(
                "external PoseBusters report-value order is invalid"
            )
        diagnostics = _positive_int(
            self.diagnostic_size_bytes,
            name="external generated-pose diagnostic size",
            allow_zero=True,
        )
        numeric_fields = (
            "direct_rmsd_angstrom_binary64_hex",
            "kabsch_rmsd_angstrom_binary64_hex",
            "centroid_distance_angstrom_binary64_hex",
            "energy_ratio_binary64_hex",
        )
        boolean_fields = (
            "all_non_rmsd_binary_tests_pass",
            "identity_pass",
            "intramolecular_geometry_pass",
            "internal_energy_pass",
            "intermolecular_distance_and_overlap_pass",
            "rmsd_evaluated",
            "rmsd_within_2_angstrom",
        )
        if any(type(getattr(self, name)) is not bool for name in boolean_fields):
            raise PoseBustersExternalGeneratedPoseEvaluationError(
                "external generated-pose result flags must be boolean"
            )
        for name in numeric_fields:
            value = getattr(self, name)
            if value:
                object.__setattr__(
                    self,
                    name,
                    _validate_hex(value, name=name),
                )
        if self.status == "evaluated":
            valid = (
                bool(report)
                and bool(self.diagnostic_sha256)
                and not any(
                    (
                        self.error_stage,
                        self.error_code,
                        self.error_type,
                        self.error_message_sha256,
                    )
                )
            )
            selected = report[: len(POSEBUSTERS_GENERATED_POSE_SELECTED_COLUMNS)]
            if tuple(row.source_name for row in selected) != (
                POSEBUSTERS_GENERATED_POSE_SELECTED_COLUMNS
            ):
                valid = False
            expected_non_rmsd = all(
                row.value_type == "boolean" and row.value is True
                for row in selected[:-1]
            )
            expected_identity = all(
                _boolean_value(report, name) is True
                for name in _IDENTITY_COLUMNS
            )
            expected_geometry = all(
                _boolean_value(report, name) is True
                for name in _GEOMETRY_COLUMNS
            )
            expected_energy = _boolean_value(report, "internal_energy") is True
            expected_inter = all(
                _boolean_value(report, name) is True
                for name in _INTERMOLECULAR_COLUMNS
            )
            direct = _binary64_value(report, "rmsd")
            expected_rmsd_evaluated = bool(direct)
            expected_hit = (
                expected_rmsd_evaluated
                and float.fromhex(direct)
                <= POSEBUSTERS_GENERATED_POSE_CONFIGURATION[
                    "rmsd_threshold_angstrom"
                ]
            )
            selected_rmsd = _boolean_value(report, "rmsd_le_2_angstrom")
            valid = valid and (
                self.all_non_rmsd_binary_tests_pass == expected_non_rmsd
                and self.identity_pass == expected_identity
                and self.intramolecular_geometry_pass == expected_geometry
                and self.internal_energy_pass == expected_energy
                and self.intermolecular_distance_and_overlap_pass
                == expected_inter
                and self.rmsd_evaluated == expected_rmsd_evaluated
                and self.rmsd_within_2_angstrom == expected_hit
                and self.direct_rmsd_angstrom_binary64_hex == direct
                and self.kabsch_rmsd_angstrom_binary64_hex
                == _binary64_value(report, "kabsch_rmsd")
                and self.centroid_distance_angstrom_binary64_hex
                == _binary64_value(report, "centroid_distance")
                and self.energy_ratio_binary64_hex
                == _binary64_value(report, "energy_ratio")
                and (selected_rmsd is None or selected_rmsd == expected_hit)
            )
        else:
            valid = (
                not report
                and all(
                    (
                        self.error_stage,
                        self.error_code,
                        self.error_type,
                        self.error_message_sha256,
                        self.diagnostic_sha256,
                    )
                )
                and not any(
                    (
                        self.all_non_rmsd_binary_tests_pass,
                        self.identity_pass,
                        self.intramolecular_geometry_pass,
                        self.internal_energy_pass,
                        self.intermolecular_distance_and_overlap_pass,
                        self.rmsd_evaluated,
                        self.rmsd_within_2_angstrom,
                        *(bool(getattr(self, name)) for name in numeric_fields),
                    )
                )
            )
        if not valid:
            raise PoseBustersExternalGeneratedPoseEvaluationError(
                "external generated-pose result disposition is inconsistent"
            )
        if self.error_stage:
            object.__setattr__(
                self,
                "error_stage",
                _token(self.error_stage, name="external evaluation error stage"),
            )
            object.__setattr__(
                self,
                "error_code",
                _token(self.error_code, name="external evaluation error code"),
            )
            object.__setattr__(
                self,
                "error_type",
                _identifier(self.error_type, name="external evaluation error type"),
            )
            object.__setattr__(
                self,
                "error_message_sha256",
                _digest(
                    self.error_message_sha256,
                    name="external evaluation error message",
                ),
            )
        object.__setattr__(
            self,
            "diagnostic_sha256",
            _digest(
                self.diagnostic_sha256,
                name="external evaluation diagnostic",
            ),
        )
        object.__setattr__(self, "engine_id", engine)
        object.__setattr__(self, "pose_rank", rank)
        object.__setattr__(self, "score_components_binary64_hex", scores)
        object.__setattr__(self, "report_values", report)
        object.__setattr__(self, "diagnostic_size_bytes", diagnostics)

    @property
    def valid_and_rmsd_within_2_angstrom(self) -> bool:
        return (
            self.all_non_rmsd_binary_tests_pass
            and self.rmsd_within_2_angstrom
        )

    @property
    def report_sha256(self) -> str:
        return _canonical_sha256([row.to_dict() for row in self.report_values])

    def to_dict(self) -> dict[str, Any]:
        score_order = _ENGINE_SPECS[self.engine_id]["score_components"]
        return {
            "schema_id": self.schema_id,
            "engine_id": self.engine_id,
            "pose_rank": self.pose_rank,
            "status": self.status,
            "score_component_order": list(score_order),
            "score_components_binary64_hex": list(
                self.score_components_binary64_hex
            ),
            "score_components": {
                name: value
                for name, value in zip(
                    score_order,
                    self.score_components_binary64_hex,
                )
            },
            "report_values": [row.to_dict() for row in self.report_values],
            "report_sha256": self.report_sha256,
            "all_non_rmsd_binary_tests_pass": (
                self.all_non_rmsd_binary_tests_pass
            ),
            "identity_pass": self.identity_pass,
            "intramolecular_geometry_pass": self.intramolecular_geometry_pass,
            "internal_energy_pass": self.internal_energy_pass,
            "intermolecular_distance_and_overlap_pass": (
                self.intermolecular_distance_and_overlap_pass
            ),
            "rmsd_evaluated": self.rmsd_evaluated,
            "rmsd_within_2_angstrom": self.rmsd_within_2_angstrom,
            "valid_and_rmsd_within_2_angstrom": (
                self.valid_and_rmsd_within_2_angstrom
            ),
            "direct_rmsd_angstrom_binary64_hex": (
                self.direct_rmsd_angstrom_binary64_hex
            ),
            "kabsch_rmsd_angstrom_binary64_hex": (
                self.kabsch_rmsd_angstrom_binary64_hex
            ),
            "centroid_distance_angstrom_binary64_hex": (
                self.centroid_distance_angstrom_binary64_hex
            ),
            "energy_ratio_binary64_hex": self.energy_ratio_binary64_hex,
            "error_stage": self.error_stage,
            "error_code": self.error_code,
            "error_type": self.error_type,
            "error_message_sha256": self.error_message_sha256,
            "diagnostic_sha256": self.diagnostic_sha256,
            "diagnostic_size_bytes": self.diagnostic_size_bytes,
        }


@dataclass(frozen=True, slots=True)
class PoseBustersExternalGeneratedPoseCase:
    engine_id: str
    case_id: str
    status: str
    disposition_code: str
    execution_status: str
    execution_error_code: str
    execution_pose_count: int
    pose_results: tuple[PoseBustersExternalGeneratedPoseResult, ...] = ()
    error_stage: str = ""
    error_code: str = ""
    error_type: str = ""
    error_message_sha256: str = ""
    diagnostic_sha256: str = ""
    diagnostic_size_bytes: int = 0
    schema_id: str = POSEBUSTERS_EXTERNAL_GENERATED_POSE_CASE_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_EXTERNAL_GENERATED_POSE_CASE_SCHEMA_ID:
            raise PoseBustersExternalGeneratedPoseEvaluationError(
                "unsupported external generated-pose case schema"
            )
        engine = _engine_id(self.engine_id)
        case = _case_id(self.case_id)
        if (
            self.status not in _EVALUATION_CASE_STATUSES
            or self.execution_status not in _EXECUTION_STATUSES
        ):
            raise PoseBustersExternalGeneratedPoseEvaluationError(
                "external generated-pose case status is invalid"
            )
        disposition = _token(
            self.disposition_code,
            name="external generated-pose disposition",
        )
        pose_count = _positive_int(
            self.execution_pose_count,
            name="external generated-pose count",
            allow_zero=True,
        )
        poses = tuple(self.pose_results)
        if (
            tuple(row.pose_rank for row in poses)
            != tuple(range(1, len(poses) + 1))
            or any(row.engine_id != engine for row in poses)
        ):
            raise PoseBustersExternalGeneratedPoseEvaluationError(
                "external generated-pose ranks or engines are inconsistent"
            )
        diagnostics = _positive_int(
            self.diagnostic_size_bytes,
            name="external generated-pose case diagnostic size",
            allow_zero=True,
        )
        if self.execution_status == "success":
            evaluated = sum(row.status == "evaluated" for row in poses)
            expected_status = (
                "evaluated"
                if evaluated == pose_count
                else "evaluation_failure"
                if evaluated == 0
                else "partial_evaluation"
            )
            valid = (
                pose_count > 0
                and len(poses) == pose_count
                and self.status == expected_status
                and not self.execution_error_code
            )
            case_error_values = (
                self.error_stage,
                self.error_code,
                self.error_type,
                self.error_message_sha256,
                self.diagnostic_sha256,
            )
            if expected_status in {"evaluated", "partial_evaluation"}:
                valid = valid and not any((*case_error_values, diagnostics))
            elif any(case_error_values):
                valid = valid and all(case_error_values)
            else:
                valid = valid and diagnostics == 0
        else:
            expected_status = {
                "engine_failure": "blocked_engine_failure",
                "blocked_preparation_failure": "blocked_preparation_failure",
                "blocked_upstream_failure": "blocked_upstream_failure",
                "abstain_chemistry_scope": "abstain_chemistry_scope",
            }[self.execution_status]
            valid = (
                self.status == expected_status
                and pose_count == 0
                and not poses
                and not any(
                    (
                        self.error_stage,
                        self.error_code,
                        self.error_type,
                        self.error_message_sha256,
                        self.diagnostic_sha256,
                        diagnostics,
                    )
                )
            )
        if not valid:
            raise PoseBustersExternalGeneratedPoseEvaluationError(
                "external generated-pose case disposition is inconsistent"
            )
        if self.execution_error_code:
            object.__setattr__(
                self,
                "execution_error_code",
                _token(
                    self.execution_error_code,
                    name="external execution error code",
                ),
            )
        if self.error_stage:
            object.__setattr__(
                self,
                "error_stage",
                _token(self.error_stage, name="external case error stage"),
            )
            object.__setattr__(
                self,
                "error_code",
                _token(self.error_code, name="external case error code"),
            )
            object.__setattr__(
                self,
                "error_type",
                _identifier(self.error_type, name="external case error type"),
            )
            object.__setattr__(
                self,
                "error_message_sha256",
                _digest(
                    self.error_message_sha256,
                    name="external case error message",
                ),
            )
            object.__setattr__(
                self,
                "diagnostic_sha256",
                _digest(
                    self.diagnostic_sha256,
                    name="external case diagnostic",
                ),
            )
        object.__setattr__(self, "engine_id", engine)
        object.__setattr__(self, "case_id", case)
        object.__setattr__(self, "disposition_code", disposition)
        object.__setattr__(self, "execution_pose_count", pose_count)
        object.__setattr__(self, "pose_results", poses)
        object.__setattr__(self, "diagnostic_size_bytes", diagnostics)

    @property
    def evaluation_complete(self) -> bool:
        return self.status == "evaluated"

    @property
    def has_any_valid_pose(self) -> bool:
        return any(row.all_non_rmsd_binary_tests_pass for row in self.pose_results)

    @property
    def top_1_valid(self) -> bool:
        return bool(
            self.pose_results
            and self.pose_results[0].all_non_rmsd_binary_tests_pass
        )

    @property
    def top_5_valid(self) -> bool:
        return any(
            row.all_non_rmsd_binary_tests_pass for row in self.pose_results[:5]
        )

    @property
    def top_1_rmsd_hit(self) -> bool:
        return bool(
            self.pose_results and self.pose_results[0].rmsd_within_2_angstrom
        )

    @property
    def top_5_rmsd_hit(self) -> bool:
        return any(
            row.rmsd_within_2_angstrom for row in self.pose_results[:5]
        )

    @property
    def all_modes_rmsd_hit(self) -> bool:
        return any(row.rmsd_within_2_angstrom for row in self.pose_results)

    @property
    def top_1_valid_rmsd_hit(self) -> bool:
        return bool(
            self.pose_results
            and self.pose_results[0].valid_and_rmsd_within_2_angstrom
        )

    @property
    def top_5_valid_rmsd_hit(self) -> bool:
        return any(
            row.valid_and_rmsd_within_2_angstrom
            for row in self.pose_results[:5]
        )

    def _best_rmsd(self, top_k: int | None) -> str:
        rows = self.pose_results if top_k is None else self.pose_results[:top_k]
        values = [
            row.direct_rmsd_angstrom_binary64_hex
            for row in rows
            if row.rmsd_evaluated
        ]
        if not values:
            return ""
        return min(values, key=float.fromhex)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "engine_id": self.engine_id,
            "case_id": self.case_id,
            "status": self.status,
            "disposition_code": self.disposition_code,
            "execution_status": self.execution_status,
            "execution_error_code": self.execution_error_code,
            "execution_pose_count": self.execution_pose_count,
            "evaluated_pose_count": sum(
                row.status == "evaluated" for row in self.pose_results
            ),
            "failed_pose_count": sum(
                row.status == "evaluation_failure" for row in self.pose_results
            ),
            "physically_valid_pose_count": sum(
                row.all_non_rmsd_binary_tests_pass for row in self.pose_results
            ),
            "rmsd_evaluated_pose_count": sum(
                row.rmsd_evaluated for row in self.pose_results
            ),
            "rmsd_hit_pose_count": sum(
                row.rmsd_within_2_angstrom for row in self.pose_results
            ),
            "evaluation_complete": self.evaluation_complete,
            "has_any_valid_pose": self.has_any_valid_pose,
            "top_1_valid": self.top_1_valid,
            "top_5_valid": self.top_5_valid,
            "top_1_rmsd_within_2_angstrom": self.top_1_rmsd_hit,
            "top_5_rmsd_within_2_angstrom": self.top_5_rmsd_hit,
            "all_modes_rmsd_within_2_angstrom": self.all_modes_rmsd_hit,
            "top_1_valid_and_rmsd_within_2_angstrom": (
                self.top_1_valid_rmsd_hit
            ),
            "top_5_valid_and_rmsd_within_2_angstrom": (
                self.top_5_valid_rmsd_hit
            ),
            "top_1_direct_rmsd_angstrom_binary64_hex": self._best_rmsd(1),
            "top_5_best_direct_rmsd_angstrom_binary64_hex": self._best_rmsd(5),
            "all_modes_best_direct_rmsd_angstrom_binary64_hex": (
                self._best_rmsd(None)
            ),
            "pose_results": [row.to_dict() for row in self.pose_results],
            "error_stage": self.error_stage,
            "error_code": self.error_code,
            "error_type": self.error_type,
            "error_message_sha256": self.error_message_sha256,
            "diagnostic_sha256": self.diagnostic_sha256,
            "diagnostic_size_bytes": self.diagnostic_size_bytes,
        }


def _summary_metrics(
    engine_id: str,
    rows: Sequence[PoseBustersExternalGeneratedPoseCase],
) -> tuple[PoseBustersGeneratedPoseMetric, ...]:
    engine = _engine_id(engine_id)
    all_cases = tuple(rows)
    successes = tuple(
        row for row in rows if row.execution_status == "success"
    )
    poses = tuple(pose for row in successes for pose in row.pose_results)
    case_predicates = (
        (
            f"{engine}_generated_pose_case_rate",
            lambda row: row.execution_status == "success",
        ),
        (
            "posebusters_complete_case_evaluation_rate",
            lambda row: row.evaluation_complete,
        ),
        (
            "posebusters_case_evaluation_failure_rate",
            lambda row: row.status
            in {"partial_evaluation", "evaluation_failure"},
        ),
        (
            "case_with_any_physically_valid_pose_rate",
            lambda row: row.has_any_valid_pose,
        ),
        ("top_1_physically_valid_pose_rate", lambda row: row.top_1_valid),
        ("top_5_physically_valid_pose_rate", lambda row: row.top_5_valid),
        ("top_1_rmsd_le_2_angstrom_rate", lambda row: row.top_1_rmsd_hit),
        ("top_5_rmsd_le_2_angstrom_rate", lambda row: row.top_5_rmsd_hit),
        (
            "all_modes_rmsd_le_2_angstrom_rate",
            lambda row: row.all_modes_rmsd_hit,
        ),
        (
            "top_1_valid_and_rmsd_le_2_angstrom_rate",
            lambda row: row.top_1_valid_rmsd_hit,
        ),
        (
            "top_5_valid_and_rmsd_le_2_angstrom_rate",
            lambda row: row.top_5_valid_rmsd_hit,
        ),
    )
    conditional_predicates = case_predicates[4:]
    pose_predicates = (
        ("pose_evaluation_success_rate", lambda row: row.status == "evaluated"),
        (
            "physically_valid_pose_rate",
            lambda row: row.all_non_rmsd_binary_tests_pass,
        ),
        ("rmsd_evaluated_pose_rate", lambda row: row.rmsd_evaluated),
        (
            "rmsd_le_2_angstrom_pose_rate",
            lambda row: row.rmsd_within_2_angstrom,
        ),
        (
            "valid_and_rmsd_le_2_angstrom_pose_rate",
            lambda row: row.valid_and_rmsd_within_2_angstrom,
        ),
    )
    metrics = [
        _metric(
            name,
            "all_cases",
            sum(bool(predicate(row)) for row in all_cases),
            len(all_cases),
        )
        for name, predicate in case_predicates
    ]
    metrics.extend(
        _metric(
            name,
            f"{engine}_success_cases",
            sum(bool(predicate(row)) for row in successes),
            len(successes),
        )
        for name, predicate in conditional_predicates
    )
    metrics.extend(
        _metric(
            name,
            "generated_poses",
            sum(bool(predicate(row)) for row in poses),
            len(poses),
        )
        for name, predicate in pose_predicates
    )
    return tuple(metrics)


@dataclass(frozen=True, slots=True)
class PoseBustersExternalGeneratedPoseEvaluationReceipt:
    engine_id: str
    archive_intake_receipt_sha256: str
    corpus_audit_receipt_sha256: str
    preparation_receipt_sha256: str
    preparation_receipt_file_sha256: str
    preparation_artifact_set_sha256: str
    execution_receipt_sha256: str
    execution_receipt_file_sha256: str
    execution_artifact_set_sha256: str
    execution_configuration_sha256: str
    implementation_source_sha256: str
    implementation_source_members: tuple[tuple[str, str], ...]
    runtime_identity: PoseBustersGeneratedPoseRuntimeIdentity
    evaluation_configuration_sha256: str
    case_rows: tuple[PoseBustersExternalGeneratedPoseCase, ...]
    metrics: tuple[PoseBustersGeneratedPoseMetric, ...]
    schema_id: str = POSEBUSTERS_EXTERNAL_GENERATED_POSE_EVALUATION_SCHEMA_ID

    def __post_init__(self) -> None:
        if (
            self.schema_id
            != POSEBUSTERS_EXTERNAL_GENERATED_POSE_EVALUATION_SCHEMA_ID
        ):
            raise PoseBustersExternalGeneratedPoseEvaluationError(
                "unsupported external generated-pose evaluation schema"
            )
        engine = _engine_id(self.engine_id)
        for name in (
            "archive_intake_receipt_sha256",
            "corpus_audit_receipt_sha256",
            "preparation_receipt_sha256",
            "preparation_receipt_file_sha256",
            "preparation_artifact_set_sha256",
            "execution_receipt_sha256",
            "execution_receipt_file_sha256",
            "execution_artifact_set_sha256",
            "execution_configuration_sha256",
            "implementation_source_sha256",
            "evaluation_configuration_sha256",
        ):
            object.__setattr__(
                self,
                name,
                _digest(getattr(self, name), name=name),
            )
        if self.execution_configuration_sha256 != (
            POSEBUSTERS_EXTERNAL_BINARY_CONFIGURATION_SHA256[engine]
        ) or self.evaluation_configuration_sha256 != (
            POSEBUSTERS_GENERATED_POSE_CONFIGURATION_SHA256
        ):
            raise PoseBustersExternalGeneratedPoseEvaluationError(
                "external generated-pose configuration identity changed"
            )
        members = tuple(
            (
                _token(role, name="external evaluation source role"),
                _digest(digest, name="external evaluation source"),
            )
            for role, digest in self.implementation_source_members
        )
        if (
            not members
            or tuple(sorted(members)) != members
            or len({role for role, _digest_value in members}) != len(members)
            or self.implementation_source_sha256
            != _canonical_sha256(dict(members))
        ):
            raise PoseBustersExternalGeneratedPoseEvaluationError(
                "external evaluation source identity is invalid"
            )
        if not isinstance(
            self.runtime_identity,
            PoseBustersGeneratedPoseRuntimeIdentity,
        ):
            raise PoseBustersExternalGeneratedPoseEvaluationError(
                "external evaluation runtime identity is invalid"
            )
        rows = tuple(self.case_rows)
        if (
            not rows
            or tuple(row.case_id for row in rows)
            != tuple(sorted(row.case_id for row in rows))
            or len({row.case_id for row in rows}) != len(rows)
            or any(row.engine_id != engine for row in rows)
        ):
            raise PoseBustersExternalGeneratedPoseEvaluationError(
                "external evaluation rows must be canonical unique cases"
            )
        metrics = _summary_metrics(engine, rows)
        if tuple(row.to_dict() for row in self.metrics) != tuple(
            row.to_dict() for row in metrics
        ):
            raise PoseBustersExternalGeneratedPoseEvaluationError(
                "external evaluation metrics do not match case rows"
            )
        object.__setattr__(self, "engine_id", engine)
        object.__setattr__(self, "implementation_source_members", members)
        object.__setattr__(self, "case_rows", rows)
        object.__setattr__(self, "metrics", metrics)

    @property
    def generated_pose_count(self) -> int:
        return sum(row.execution_pose_count for row in self.case_rows)

    @property
    def evaluated_pose_count(self) -> int:
        return sum(
            pose.status == "evaluated"
            for row in self.case_rows
            for pose in row.pose_results
        )

    @property
    def physically_valid_pose_count(self) -> int:
        return sum(
            pose.all_non_rmsd_binary_tests_pass
            for row in self.case_rows
            for pose in row.pose_results
        )

    def _payload(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "engine_id": self.engine_id,
            "archive_intake_receipt_sha256": (
                self.archive_intake_receipt_sha256
            ),
            "corpus_audit_receipt_sha256": self.corpus_audit_receipt_sha256,
            "preparation_receipt_sha256": self.preparation_receipt_sha256,
            "preparation_receipt_file_sha256": (
                self.preparation_receipt_file_sha256
            ),
            "preparation_artifact_set_sha256": (
                self.preparation_artifact_set_sha256
            ),
            "execution_receipt_sha256": self.execution_receipt_sha256,
            "execution_receipt_file_sha256": (
                self.execution_receipt_file_sha256
            ),
            "execution_artifact_set_sha256": (
                self.execution_artifact_set_sha256
            ),
            "execution_configuration_sha256": (
                self.execution_configuration_sha256
            ),
            "implementation_source_sha256": self.implementation_source_sha256,
            "implementation_source_members": dict(
                self.implementation_source_members
            ),
            "runtime_identity": self.runtime_identity.to_dict(),
            "runtime_identity_sha256": (
                self.runtime_identity.fingerprint_sha256
            ),
            "evaluation_configuration": POSEBUSTERS_GENERATED_POSE_CONFIGURATION,
            "evaluation_configuration_sha256": (
                self.evaluation_configuration_sha256
            ),
            "score_component_order": list(
                _ENGINE_SPECS[self.engine_id]["score_components"]
            ),
            "all_case_denominator": len(self.case_rows),
            "execution_success_case_count": sum(
                row.execution_status == "success" for row in self.case_rows
            ),
            "execution_failure_case_count": sum(
                row.execution_status == "engine_failure"
                for row in self.case_rows
            ),
            "complete_evaluation_case_count": sum(
                row.evaluation_complete for row in self.case_rows
            ),
            "generated_pose_count": self.generated_pose_count,
            "evaluated_pose_count": self.evaluated_pose_count,
            "physically_valid_pose_count": self.physically_valid_pose_count,
            "case_rows": [row.to_dict() for row in self.case_rows],
            "metrics": [row.to_dict() for row in self.metrics],
            "posebusters_redock_oracle_executed": True,
            "physical_validity_and_rmsd_kept_separate": True,
            "full_report_values_retained": True,
            "target_family_metrics_present": False,
            "leakage_receipt_present": False,
            "independent_external_evaluation_rerun_present": False,
            "benchmark_executed": False,
            "scientific_blockers": list(
                POSEBUSTERS_EXTERNAL_GENERATED_POSE_BLOCKERS
            ),
            "scientifically_validated": False,
            "claim_safe": False,
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_sha256(self._payload())

    def to_dict(self) -> dict[str, Any]:
        return {**self._payload(), "receipt_sha256": self.fingerprint_sha256}

    def write_json(self, output_path: str | os.PathLike[str]) -> Path:
        output = Path(output_path)
        output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        payload = _canonical_bytes(self.to_dict()) + b"\n"
        if len(payload) > POSEBUSTERS_EXTERNAL_GENERATED_POSE_MAX_RECEIPT_BYTES:
            raise PoseBustersExternalGeneratedPoseEvaluationError(
                "external generated-pose evaluation receipt exceeds its bound"
            )
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{output.name}.",
            suffix=".tmp",
            dir=str(output.parent),
        )
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(temporary_name, output, follow_symlinks=False)
            except FileExistsError as exc:
                raise PoseBustersExternalGeneratedPoseEvaluationError(
                    "external generated-pose evaluation output already exists"
                ) from exc
        finally:
            try:
                os.close(descriptor)
            except OSError:
                pass
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
        return output


def _implementation_source_members() -> tuple[tuple[str, str], ...]:
    return tuple(
        sorted(
            {
                "external_generated_pose_evaluation": _source_file_sha256(
                    __file__
                ),
                "external_binary_execution_contract": _source_file_sha256(
                    Path(__file__).with_name(
                        "public_posebusters_external_binary_execution.py"
                    )
                ),
                "generated_pose_runtime": _source_file_sha256(
                    Path(__file__).with_name(
                        "public_posebusters_generated_pose_evaluation.py"
                    )
                ),
                "external_preparation_contract": _source_file_sha256(
                    Path(__file__).with_name(
                        "public_posebusters_external_preparation.py"
                    )
                ),
            }.items()
        )
    )


def _blocked_case(
    engine_id: str,
    execution: _ExternalCaseView,
) -> PoseBustersExternalGeneratedPoseCase:
    status = {
        "engine_failure": "blocked_engine_failure",
        "blocked_preparation_failure": "blocked_preparation_failure",
        "blocked_upstream_failure": "blocked_upstream_failure",
        "abstain_chemistry_scope": "abstain_chemistry_scope",
    }[execution.status]
    disposition = {
        "engine_failure": "blocked_by_external_engine_failure",
        "blocked_preparation_failure": "blocked_by_strict_preparation_failure",
        "blocked_upstream_failure": "blocked_by_upstream_input_failure",
        "abstain_chemistry_scope": "chemistry_scope_abstention",
    }[execution.status]
    return PoseBustersExternalGeneratedPoseCase(
        engine_id=engine_id,
        case_id=execution.case_id,
        status=status,
        disposition_code=disposition,
        execution_status=execution.status,
        execution_error_code=execution.error_code,
        execution_pose_count=0,
    )


def _failure_pose(
    engine_id: str,
    rank: int,
    score: tuple[str, ...],
    error: PoseBustersGeneratedPoseCaseError,
) -> PoseBustersExternalGeneratedPoseResult:
    return PoseBustersExternalGeneratedPoseResult(
        engine_id=engine_id,
        pose_rank=rank,
        score_components_binary64_hex=score,
        status="evaluation_failure",
        error_stage=error.stage,
        error_code=error.error_code,
        error_type=error.error_type,
        error_message_sha256=error.error_message_sha256,
        diagnostic_sha256=error.diagnostic_sha256,
        diagnostic_size_bytes=error.diagnostic_size_bytes,
    )


def _result_from_outcome(
    engine_id: str,
    rank: int,
    score: tuple[str, ...],
    outcome: _RuntimePoseOutcome,
) -> PoseBustersExternalGeneratedPoseResult:
    return PoseBustersExternalGeneratedPoseResult(
        engine_id=engine_id,
        pose_rank=rank,
        score_components_binary64_hex=score,
        status=outcome.status,
        report_values=outcome.report_values,
        all_non_rmsd_binary_tests_pass=(
            outcome.all_non_rmsd_binary_tests_pass
        ),
        identity_pass=outcome.identity_pass,
        intramolecular_geometry_pass=outcome.intramolecular_geometry_pass,
        internal_energy_pass=outcome.internal_energy_pass,
        intermolecular_distance_and_overlap_pass=(
            outcome.intermolecular_distance_and_overlap_pass
        ),
        rmsd_evaluated=outcome.rmsd_evaluated,
        rmsd_within_2_angstrom=outcome.rmsd_within_2_angstrom,
        direct_rmsd_angstrom_binary64_hex=(
            outcome.direct_rmsd_angstrom_binary64_hex
        ),
        kabsch_rmsd_angstrom_binary64_hex=(
            outcome.kabsch_rmsd_angstrom_binary64_hex
        ),
        centroid_distance_angstrom_binary64_hex=(
            outcome.centroid_distance_angstrom_binary64_hex
        ),
        energy_ratio_binary64_hex=outcome.energy_ratio_binary64_hex,
        error_stage=outcome.error_stage,
        error_code=outcome.error_code,
        error_type=outcome.error_type,
        error_message_sha256=outcome.error_message_sha256,
        diagnostic_sha256=outcome.diagnostic_sha256,
        diagnostic_size_bytes=outcome.diagnostic_size_bytes,
    )


def _evaluate_case(
    engine_id: str,
    execution: _ExternalCaseView,
    poses_pdbqt: bytes,
    receptor_pdb: bytes,
    reference_ligands_sdf: bytes,
    runtime: _PoseBustersRuntimeProtocol,
) -> PoseBustersExternalGeneratedPoseCase:
    engine = _engine_id(engine_id)
    if execution.status != "success" or execution.artifact is None:
        return _blocked_case(engine, execution)
    case_error: PoseBustersGeneratedPoseCaseError | None = None
    try:
        outcomes = runtime.evaluate_case(
            poses_pdbqt,
            receptor_pdb,
            reference_ligands_sdf,
            execution.pose_count,
        )
        if len(outcomes) != execution.pose_count:
            raise PoseBustersGeneratedPoseCaseError(
                stage="posebusters_runtime",
                error_code="posebusters_pose_count_mismatch",
                error_type="ValueError",
                error_message_sha256=_hash_bytes(b"pose count mismatch"),
                diagnostic_sha256=_hash_bytes(b""),
                diagnostic_size_bytes=0,
            )
    except PoseBustersGeneratedPoseCaseError as exc:
        case_error = exc
        outcomes = ()
    except Exception as exc:
        case_error = PoseBustersGeneratedPoseCaseError(
            stage="posebusters_runtime",
            error_code="unclassified_posebusters_case_failure",
            error_type=type(exc).__name__,
            error_message_sha256=_hash_bytes(_normalize_error(exc)),
            diagnostic_sha256=_hash_bytes(b""),
            diagnostic_size_bytes=0,
        )
        outcomes = ()
    if case_error is not None:
        pose_results = tuple(
            _failure_pose(engine, rank, score, case_error)
            for rank, score in enumerate(
                execution.score_components_binary64_hex,
                start=1,
            )
        )
        return PoseBustersExternalGeneratedPoseCase(
            engine_id=engine,
            case_id=execution.case_id,
            status="evaluation_failure",
            disposition_code=case_error.error_code,
            execution_status=execution.status,
            execution_error_code="",
            execution_pose_count=execution.pose_count,
            pose_results=pose_results,
            error_stage=case_error.stage,
            error_code=case_error.error_code,
            error_type=case_error.error_type,
            error_message_sha256=case_error.error_message_sha256,
            diagnostic_sha256=case_error.diagnostic_sha256,
            diagnostic_size_bytes=case_error.diagnostic_size_bytes,
        )
    pose_results = tuple(
        _result_from_outcome(engine, rank, score, outcome)
        for rank, (outcome, score) in enumerate(
            zip(outcomes, execution.score_components_binary64_hex),
            start=1,
        )
    )
    evaluated = sum(row.status == "evaluated" for row in pose_results)
    status = (
        "evaluated"
        if evaluated == execution.pose_count
        else "evaluation_failure"
        if evaluated == 0
        else "partial_evaluation"
    )
    return PoseBustersExternalGeneratedPoseCase(
        engine_id=engine,
        case_id=execution.case_id,
        status=status,
        disposition_code=(
            "posebusters_redock_evaluation_complete"
            if status == "evaluated"
            else "posebusters_redock_pose_failures_retained"
        ),
        execution_status=execution.status,
        execution_error_code="",
        execution_pose_count=execution.pose_count,
        pose_results=pose_results,
    )


def _build_evaluation(
    engine_id: str,
    archive_path: str | os.PathLike[str],
    selection_path: str | os.PathLike[str],
    intake_receipt_path: str | os.PathLike[str],
    corpus_audit_receipt_path: str | os.PathLike[str],
    preparation_receipt_path: str | os.PathLike[str],
    preparation_artifact_root: str | os.PathLike[str],
    execution_receipt_path: str | os.PathLike[str],
    execution_artifact_root: str | os.PathLike[str],
    posebusters_wheel_path: str | os.PathLike[str],
    scratch_root: str | os.PathLike[str],
    *,
    expected_preparation_receipt_sha256: str,
    expected_execution_receipt_sha256: str,
    contract: PoseBustersArchiveContract,
) -> PoseBustersExternalGeneratedPoseEvaluationReceipt:
    engine = _engine_id(engine_id)
    try:
        intake = verify_posebusters_archive_intake_receipt(
            intake_receipt_path,
            archive_path,
            selection_path,
            contract=contract,
        )
        preparation = verify_posebusters_external_preparation_receipt(
            preparation_receipt_path,
            archive_path,
            selection_path,
            intake_receipt_path,
            corpus_audit_receipt_path,
            preparation_artifact_root,
            contract=contract,
        )
    except (
        PoseBustersArchiveIntakeError,
        PoseBustersExternalPreparationError,
    ) as exc:
        raise PoseBustersExternalGeneratedPoseEvaluationError(
            "external generated-pose source chain did not verify"
        ) from exc
    expected_preparation_sha = _digest(
        expected_preparation_receipt_sha256,
        name="expected preparation receipt",
    )
    if preparation.fingerprint_sha256 != expected_preparation_sha:
        raise PoseBustersExternalGeneratedPoseEvaluationError(
            "verified preparation receipt differs from caller pin"
        )
    preparation_source = _read_exact_regular_file(
        preparation_receipt_path,
        maximum_bytes=POSEBUSTERS_EXTERNAL_GENERATED_POSE_MAX_RECEIPT_BYTES,
    )
    execution, execution_payloads = _load_external_execution_receipt(
        engine,
        execution_receipt_path,
        execution_artifact_root,
        expected_receipt_sha256=expected_execution_receipt_sha256,
        expected_preparation_receipt_sha256=(
            preparation.fingerprint_sha256
        ),
        expected_preparation_receipt_file_sha256=_hash_bytes(
            preparation_source
        ),
        expected_preparation_artifact_set_sha256=(
            preparation.artifact_set_sha256
        ),
    )
    intake_ids = tuple(row.case_id for row in intake.case_rows)
    preparation_ids = tuple(row.case_id for row in preparation.case_rows)
    execution_ids = tuple(row.case_id for row in execution.case_rows)
    if intake_ids != preparation_ids or intake_ids != execution_ids:
        raise PoseBustersExternalGeneratedPoseEvaluationError(
            "external evaluation source-chain case identities disagree"
        )
    try:
        runtime = _load_posebusters_runtime(
            Path(scratch_root),
            posebusters_wheel_path,
        )
    except Exception as exc:
        raise PoseBustersExternalGeneratedPoseEvaluationError(
            "external evaluation PoseBusters runtime did not load"
        ) from exc
    if (
        runtime.identity.preparation_runtime.to_dict()
        != preparation.runtime_identity.to_dict()
        or runtime.identity.preparation_runtime.fingerprint_sha256
        != execution.preparation_runtime_identity_sha256
    ):
        raise PoseBustersExternalGeneratedPoseEvaluationError(
            "PoseBusters runtime differs from preparation/execution runtime"
        )
    if (
        _canonical_sha256(POSEBUSTERS_GENERATED_POSE_CONFIGURATION)
        != POSEBUSTERS_GENERATED_POSE_CONFIGURATION_SHA256
    ):
        raise PoseBustersExternalGeneratedPoseEvaluationError(
            "external evaluation frozen configuration was mutated"
        )
    intake_rows = {row.case_id: row for row in intake.case_rows}
    source_payloads: dict[str, tuple[bytes, bytes]] = {}
    descriptor, size = _regular_file_descriptor(
        archive_path,
        maximum_bytes=contract.archive_size_bytes,
    )
    try:
        if (
            size != contract.archive_size_bytes
            or _hash_descriptor(descriptor, size) != contract.archive_sha256
        ):
            raise PoseBustersExternalGeneratedPoseEvaluationError(
                "PoseBusters archive changed after source-chain verification"
            )
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            with zipfile.ZipFile(handle, "r") as archive:
                for execution_row in execution.case_rows:
                    if execution_row.status == "success":
                        try:
                            source_payloads[execution_row.case_id] = (
                                _read_archive_sources(
                                    archive,
                                    intake_rows[execution_row.case_id],
                                )
                            )
                        except Exception as exc:
                            raise PoseBustersExternalGeneratedPoseEvaluationError(
                                "PoseBusters source members failed exact access"
                            ) from exc
    except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
        raise PoseBustersExternalGeneratedPoseEvaluationError(
            "PoseBusters archive failed bounded evaluation access"
        ) from exc
    finally:
        os.close(descriptor)
    rows: list[PoseBustersExternalGeneratedPoseCase] = []
    for execution_row in execution.case_rows:
        if execution_row.status == "success":
            assert execution_row.artifact is not None
            receptor, native = source_payloads[execution_row.case_id]
            rows.append(
                _evaluate_case(
                    engine,
                    execution_row,
                    execution_payloads[
                        execution_row.artifact.relative_path
                    ],
                    receptor,
                    native,
                    runtime,
                )
            )
        else:
            rows.append(_blocked_case(engine, execution_row))
    rows_tuple = tuple(rows)
    source_members = _implementation_source_members()
    corpus_source = _read_exact_regular_file(
        corpus_audit_receipt_path,
        maximum_bytes=POSEBUSTERS_EXTERNAL_GENERATED_POSE_MAX_RECEIPT_BYTES,
    )
    try:
        corpus_raw = json.loads(corpus_source)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PoseBustersExternalGeneratedPoseEvaluationError(
            "corpus receipt is not JSON"
        ) from exc
    corpus_sha = (
        corpus_raw.get("receipt_sha256")
        if isinstance(corpus_raw, dict)
        else None
    )
    if (
        not isinstance(corpus_sha, str)
        or corpus_sha != preparation.corpus_audit_receipt_sha256
    ):
        raise PoseBustersExternalGeneratedPoseEvaluationError(
            "corpus receipt fingerprint is missing or cross-wired"
        )
    return PoseBustersExternalGeneratedPoseEvaluationReceipt(
        engine_id=engine,
        archive_intake_receipt_sha256=intake.fingerprint_sha256,
        corpus_audit_receipt_sha256=corpus_sha,
        preparation_receipt_sha256=preparation.fingerprint_sha256,
        preparation_receipt_file_sha256=_hash_bytes(preparation_source),
        preparation_artifact_set_sha256=preparation.artifact_set_sha256,
        execution_receipt_sha256=execution.receipt_sha256,
        execution_receipt_file_sha256=execution.receipt_file_sha256,
        execution_artifact_set_sha256=execution.artifact_set_sha256,
        execution_configuration_sha256=execution.configuration_sha256,
        implementation_source_sha256=_canonical_sha256(dict(source_members)),
        implementation_source_members=source_members,
        runtime_identity=runtime.identity,
        evaluation_configuration_sha256=(
            POSEBUSTERS_GENERATED_POSE_CONFIGURATION_SHA256
        ),
        case_rows=rows_tuple,
        metrics=_summary_metrics(engine, rows_tuple),
    )


def materialize_posebusters_external_generated_pose_evaluation(
    engine_id: str,
    archive_path: str | os.PathLike[str],
    selection_path: str | os.PathLike[str],
    intake_receipt_path: str | os.PathLike[str],
    corpus_audit_receipt_path: str | os.PathLike[str],
    preparation_receipt_path: str | os.PathLike[str],
    preparation_artifact_root: str | os.PathLike[str],
    execution_receipt_path: str | os.PathLike[str],
    execution_artifact_root: str | os.PathLike[str],
    posebusters_wheel_path: str | os.PathLike[str],
    scratch_root: str | os.PathLike[str],
    *,
    expected_preparation_receipt_sha256: str,
    expected_execution_receipt_sha256: str,
    contract: PoseBustersArchiveContract = OFFICIAL_POSEBUSTERS_ARCHIVE_CONTRACT,
) -> PoseBustersExternalGeneratedPoseEvaluationReceipt:
    """Evaluate all generated GNINA or Smina poses and retain every case."""

    return _build_evaluation(
        engine_id,
        archive_path,
        selection_path,
        intake_receipt_path,
        corpus_audit_receipt_path,
        preparation_receipt_path,
        preparation_artifact_root,
        execution_receipt_path,
        execution_artifact_root,
        posebusters_wheel_path,
        scratch_root,
        expected_preparation_receipt_sha256=(
            expected_preparation_receipt_sha256
        ),
        expected_execution_receipt_sha256=expected_execution_receipt_sha256,
        contract=contract,
    )


def verify_posebusters_external_generated_pose_evaluation_receipt(
    evaluation_receipt_path: str | os.PathLike[str],
    engine_id: str,
    archive_path: str | os.PathLike[str],
    selection_path: str | os.PathLike[str],
    intake_receipt_path: str | os.PathLike[str],
    corpus_audit_receipt_path: str | os.PathLike[str],
    preparation_receipt_path: str | os.PathLike[str],
    preparation_artifact_root: str | os.PathLike[str],
    execution_receipt_path: str | os.PathLike[str],
    execution_artifact_root: str | os.PathLike[str],
    posebusters_wheel_path: str | os.PathLike[str],
    scratch_root: str | os.PathLike[str],
    *,
    expected_preparation_receipt_sha256: str,
    expected_execution_receipt_sha256: str,
    contract: PoseBustersArchiveContract = OFFICIAL_POSEBUSTERS_ARCHIVE_CONTRACT,
) -> PoseBustersExternalGeneratedPoseEvaluationReceipt:
    """Require exact PoseBusters reexecution and canonical receipt equality."""

    source = _read_exact_regular_file(
        evaluation_receipt_path,
        maximum_bytes=POSEBUSTERS_EXTERNAL_GENERATED_POSE_MAX_RECEIPT_BYTES,
    )
    expected = _build_evaluation(
        engine_id,
        archive_path,
        selection_path,
        intake_receipt_path,
        corpus_audit_receipt_path,
        preparation_receipt_path,
        preparation_artifact_root,
        execution_receipt_path,
        execution_artifact_root,
        posebusters_wheel_path,
        scratch_root,
        expected_preparation_receipt_sha256=(
            expected_preparation_receipt_sha256
        ),
        expected_execution_receipt_sha256=expected_execution_receipt_sha256,
        contract=contract,
    )
    if source != _canonical_bytes(expected.to_dict()) + b"\n":
        raise PoseBustersExternalGeneratedPoseEvaluationError(
            "external evaluation receipt does not match exact reexecution"
        )
    return expected


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="betelgeuze-engine-v2-posebusters-external-evaluate-generated",
        description="Evaluate GNINA or Smina poses with all-case rows.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("materialize", "verify"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument(
            "--engine",
            choices=POSEBUSTERS_EXTERNAL_GENERATED_POSE_ENGINES,
            required=True,
        )
        subparser.add_argument("--archive", required=True)
        subparser.add_argument("--selection", required=True)
        subparser.add_argument("--intake-receipt", required=True)
        subparser.add_argument("--corpus-audit-receipt", required=True)
        subparser.add_argument("--preparation-receipt", required=True)
        subparser.add_argument("--preparation-artifact-root", required=True)
        subparser.add_argument(
            "--expected-preparation-receipt-sha256",
            required=True,
        )
        subparser.add_argument("--execution-receipt", required=True)
        subparser.add_argument("--execution-artifact-root", required=True)
        subparser.add_argument(
            "--expected-execution-receipt-sha256",
            required=True,
        )
        subparser.add_argument("--posebusters-wheel", required=True)
        subparser.add_argument("--scratch-root", required=True)
    subparsers.choices["materialize"].add_argument("--output", required=True)
    subparsers.choices["verify"].add_argument(
        "--evaluation-receipt",
        required=True,
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    common = {
        "engine_id": args.engine,
        "archive_path": args.archive,
        "selection_path": args.selection,
        "intake_receipt_path": args.intake_receipt,
        "corpus_audit_receipt_path": args.corpus_audit_receipt,
        "preparation_receipt_path": args.preparation_receipt,
        "preparation_artifact_root": args.preparation_artifact_root,
        "execution_receipt_path": args.execution_receipt,
        "execution_artifact_root": args.execution_artifact_root,
        "posebusters_wheel_path": args.posebusters_wheel,
        "scratch_root": args.scratch_root,
        "expected_preparation_receipt_sha256": (
            args.expected_preparation_receipt_sha256
        ),
        "expected_execution_receipt_sha256": (
            args.expected_execution_receipt_sha256
        ),
    }
    if args.command == "materialize":
        receipt = materialize_posebusters_external_generated_pose_evaluation(
            **common
        )
        receipt.write_json(args.output)
    else:
        receipt = (
            verify_posebusters_external_generated_pose_evaluation_receipt(
                evaluation_receipt_path=args.evaluation_receipt,
                **common,
            )
        )
    conditional = {
        (metric.metric_id, metric.denominator_scope): metric
        for metric in receipt.metrics
    }
    engine_scope = f"{receipt.engine_id}_success_cases"
    print(
        json.dumps(
            {
                "engine_id": receipt.engine_id,
                "receipt_sha256": receipt.fingerprint_sha256,
                "all_case_denominator": len(receipt.case_rows),
                "execution_success_case_count": sum(
                    row.execution_status == "success"
                    for row in receipt.case_rows
                ),
                "generated_pose_count": receipt.generated_pose_count,
                "physically_valid_pose_count": (
                    receipt.physically_valid_pose_count
                ),
                "top_1_rmsd_hit_count_execution_success_cases": conditional[
                    ("top_1_rmsd_le_2_angstrom_rate", engine_scope)
                ].numerator,
                "top_5_rmsd_hit_count_execution_success_cases": conditional[
                    ("top_5_rmsd_le_2_angstrom_rate", engine_scope)
                ].numerator,
                "benchmark_executed": False,
                "claim_safe": False,
            },
            sort_keys=True,
        )
    )
    return 0


__all__ = [
    "POSEBUSTERS_EXTERNAL_GENERATED_POSE_BLOCKERS",
    "POSEBUSTERS_EXTERNAL_GENERATED_POSE_EVALUATION_SCHEMA_ID",
    "POSEBUSTERS_EXTERNAL_GENERATED_POSE_ENGINES",
    "PoseBustersExternalGeneratedPoseCase",
    "PoseBustersExternalGeneratedPoseEvaluationError",
    "PoseBustersExternalGeneratedPoseEvaluationReceipt",
    "PoseBustersExternalGeneratedPoseResult",
    "main",
    "materialize_posebusters_external_generated_pose_evaluation",
    "verify_posebusters_external_generated_pose_evaluation_receipt",
]


if __name__ == "__main__":
    raise SystemExit(main())
