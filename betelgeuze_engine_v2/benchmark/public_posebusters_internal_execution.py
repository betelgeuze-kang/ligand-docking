"""Failure-inclusive internal redocking over canonical PoseBusters inputs.

This boundary re-verifies the exact internal-preparation receipt and artifact
tree, runs the claim-closed prepared redocking diagnostic for every prepared
case, and retains every upstream failure or chemistry abstention in the public
cohort denominator.  It materializes one authenticated diagnostic report per
completed case.  Native-pose RMSD and an external PoseBusters validity oracle
remain separate downstream gates, so this receipt cannot open a benchmark or
commercial docking claim.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import platform
import re
import tempfile
from typing import Any, Mapping, Protocol, Sequence

import torch

from betelgeuze_engine_v2 import DISTRIBUTION_VERSION
from betelgeuze_engine_v2.molecular import (
    MAX_CANONICAL_SYSTEM_JSON_BYTES,
    AllAtomSystem,
    all_atom_system_from_canonical_json,
    canonical_json_bytes,
    canonical_system_sha256,
)

from .public_posebusters_corpus_audit import (
    _canonical_bytes,
    _canonical_sha256,
    _source_file_sha256,
)
from .public_posebusters_external_preparation import (
    POSEBUSTERS_EXTERNAL_PREPARATION_MAX_ARTIFACT_BYTES,
    PoseBustersExternalPreparationError,
    _verify_artifact_tree,
    _write_artifact_tree,
)
from .public_posebusters_intake import (
    OFFICIAL_POSEBUSTERS_ARCHIVE_CONTRACT,
    PoseBustersArchiveContract,
    _read_exact_regular_file,
)
from .public_posebusters_internal_preparation import (
    POSEBUSTERS_INTERNAL_PREPARATION_MAX_ARTIFACT_BYTES,
    PoseBustersInternalPreparationCase,
    PoseBustersInternalPreparationConfig,
    PoseBustersInternalPreparationError,
    PoseBustersInternalPreparationReceipt,
    verify_posebusters_internal_preparation_receipt,
)
from .redocking_cli import (
    MAX_REDOCKING_DIAGNOSTIC_REPORT_BYTES,
    REDOCKING_DIAGNOSTIC_BLOCKERS,
    RedockingDiagnosticConfig,
    run_prepared_redocking_diagnostic,
    verify_redocking_diagnostic_report,
)


POSEBUSTERS_INTERNAL_EXECUTION_CONFIG_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_internal_execution_config/1.0.0"
)
POSEBUSTERS_INTERNAL_EXECUTION_RUNTIME_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_internal_execution_runtime/1.0.0"
)
POSEBUSTERS_INTERNAL_EXECUTION_ARTIFACT_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_internal_execution_artifact/1.0.0"
)
POSEBUSTERS_INTERNAL_EXECUTION_CASE_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_internal_execution_case/1.0.0"
)
POSEBUSTERS_INTERNAL_EXECUTION_METRIC_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_internal_execution_metric/1.0.0"
)
POSEBUSTERS_INTERNAL_EXECUTION_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_internal_execution/1.0.0"
)

POSEBUSTERS_INTERNAL_EXECUTION_MAX_RECEIPT_BYTES = 64 * 1024 * 1024
POSEBUSTERS_INTERNAL_EXECUTION_MAX_REPORT_BYTES = (
    min(
        MAX_REDOCKING_DIAGNOSTIC_REPORT_BYTES,
        POSEBUSTERS_EXTERNAL_PREPARATION_MAX_ARTIFACT_BYTES,
    )
)
POSEBUSTERS_INTERNAL_EXECUTION_BLOCKERS = tuple(
    dict.fromkeys(
        (
            *REDOCKING_DIAGNOSTIC_BLOCKERS,
            "internal_redocking_protocol_not_scientifically_validated",
            "native_pose_symmetry_aware_rmsd_evaluation_missing",
            "posebusters_external_validity_oracle_evaluation_missing",
            "target_family_and_chemistry_stratified_metrics_missing",
            "wall_clock_and_peak_memory_measurement_missing",
            "runtime_binary_and_dependency_payload_identity_incomplete",
            "second_cpu_host_exact_reproduction_missing",
            "independent_external_rerun_missing",
            "scientific_review_missing",
        )
    )
)

_CASE_STATUSES = {
    "abstain_chemistry_scope",
    "blocked_preparation_failure",
    "blocked_upstream_failure",
    "execution_failure",
    "success",
}
_PREPARATION_STATUS_TO_BLOCKED_STATUS = {
    "abstain_chemistry_scope": "abstain_chemistry_scope",
    "preparation_failure": "blocked_preparation_failure",
    "upstream_failure": "blocked_upstream_failure",
}
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class PoseBustersInternalExecutionError(ValueError):
    """Internal batch execution input, artifact, or receipt is invalid."""


def _digest(value: object, *, name: str, allow_empty: bool = False) -> str:
    text = str(value or "").strip().lower()
    if allow_empty and not text:
        return ""
    if _SHA256_RE.fullmatch(text) is None:
        raise PoseBustersInternalExecutionError(
            f"{name} must be a lowercase SHA-256"
        )
    return text


def _text(value: object, *, name: str, allow_empty: bool = False) -> str:
    text = str(value or "").strip()
    if (not text and not allow_empty) or len(text) > 512 or "\x00" in text:
        raise PoseBustersInternalExecutionError(
            f"{name} is outside its text bound"
        )
    return text


def _integer(
    value: object,
    *,
    name: str,
    minimum: int = 0,
    maximum: int = 2**63 - 1,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise PoseBustersInternalExecutionError(f"{name} must be an integer")
    if not minimum <= value <= maximum:
        raise PoseBustersInternalExecutionError(
            f"{name} must be in [{minimum}, {maximum}]"
        )
    return value


def _finite_hex(value: object, *, name: str) -> str:
    if not isinstance(value, str):
        raise PoseBustersInternalExecutionError(
            f"{name} must be canonical finite binary64"
        )
    try:
        number = float.fromhex(value)
    except ValueError as exc:
        raise PoseBustersInternalExecutionError(
            f"{name} must be canonical finite binary64"
        ) from exc
    if not math.isfinite(number) or number.hex() != value:
        raise PoseBustersInternalExecutionError(
            f"{name} must be canonical finite binary64"
        )
    return value


def _normalized_error(exc: BaseException) -> tuple[str, int]:
    raw = (
        f"{type(exc).__module__}.{type(exc).__qualname__}:"
        f"{' '.join(str(exc).split())[:4096]}"
    ).encode("utf-8", errors="backslashreplace")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def _json_object_pairs(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise PoseBustersInternalExecutionError(
                f"duplicate JSON key: {key}"
            )
        result[key] = value
    return result


def _reject_json_constant(value: str) -> object:
    raise PoseBustersInternalExecutionError(
        f"non-finite JSON constant is forbidden: {value}"
    )


def _wilson_interval(numerator: int, denominator: int) -> tuple[float, float]:
    z = 1.959963984540054
    fraction = numerator / denominator
    z2 = z * z
    scale = 1.0 + z2 / denominator
    center = (fraction + z2 / (2.0 * denominator)) / scale
    radius = (
        z
        * math.sqrt(
            fraction * (1.0 - fraction) / denominator
            + z2 / (4.0 * denominator * denominator)
        )
        / scale
    )
    return max(0.0, center - radius), min(1.0, center + radius)


@dataclass(frozen=True, slots=True)
class PoseBustersInternalExecutionConfig:
    candidate_count: int = 64
    top_k: int = 10
    max_torsions: int = 32
    translation_radius_angstrom: float = 4.0
    diversity_rmsd_angstrom: float = 0.5
    max_refinement_steps: int = 6
    base_seed: int = 7_301
    schema_id: str = POSEBUSTERS_INTERNAL_EXECUTION_CONFIG_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_INTERNAL_EXECUTION_CONFIG_SCHEMA_ID:
            raise PoseBustersInternalExecutionError(
                "unsupported internal-execution config schema"
            )
        probe = RedockingDiagnosticConfig(
            candidate_count=self.candidate_count,
            top_k=self.top_k,
            max_torsions=self.max_torsions,
            translation_radius_angstrom=self.translation_radius_angstrom,
            diversity_rmsd_angstrom=self.diversity_rmsd_angstrom,
            max_refinement_steps=self.max_refinement_steps,
            seed=self.base_seed,
        )
        object.__setattr__(self, "candidate_count", probe.candidate_count)
        object.__setattr__(self, "top_k", probe.top_k)
        object.__setattr__(self, "max_torsions", probe.max_torsions)
        object.__setattr__(
            self,
            "translation_radius_angstrom",
            probe.translation_radius_angstrom,
        )
        object.__setattr__(
            self,
            "diversity_rmsd_angstrom",
            probe.diversity_rmsd_angstrom,
        )
        object.__setattr__(
            self,
            "max_refinement_steps",
            probe.max_refinement_steps,
        )
        object.__setattr__(self, "base_seed", probe.seed)

    def case_seed(self, case_id: str) -> int:
        case = _text(case_id, name="case ID")
        source = f"{self.base_seed}:{case}".encode("ascii")
        return int.from_bytes(hashlib.sha256(source).digest()[:8], "big") % (
            2**63
        )

    def diagnostic_config(self, case_id: str) -> RedockingDiagnosticConfig:
        return RedockingDiagnosticConfig(
            candidate_count=self.candidate_count,
            top_k=self.top_k,
            max_torsions=self.max_torsions,
            translation_radius_angstrom=self.translation_radius_angstrom,
            diversity_rmsd_angstrom=self.diversity_rmsd_angstrom,
            max_refinement_steps=self.max_refinement_steps,
            seed=self.case_seed(case_id),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "candidate_count": self.candidate_count,
            "top_k": self.top_k,
            "max_torsions": self.max_torsions,
            "translation_radius_angstrom_binary64_hex": (
                self.translation_radius_angstrom.hex()
            ),
            "diversity_rmsd_angstrom_binary64_hex": (
                self.diversity_rmsd_angstrom.hex()
            ),
            "max_refinement_steps": self.max_refinement_steps,
            "base_seed": self.base_seed,
            "per_case_seed_policy": (
                "sha256_first_u64_big_endian_mod_2pow63_of_base_seed_colon_case_id"
            ),
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())


@dataclass(frozen=True, slots=True)
class PoseBustersInternalExecutionRuntime:
    python_implementation: str
    python_version: str
    torch_version: str
    engine_version: str
    schema_id: str = POSEBUSTERS_INTERNAL_EXECUTION_RUNTIME_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_INTERNAL_EXECUTION_RUNTIME_SCHEMA_ID:
            raise PoseBustersInternalExecutionError(
                "unsupported internal-execution runtime schema"
            )
        for name in (
            "python_implementation",
            "python_version",
            "torch_version",
            "engine_version",
        ):
            object.__setattr__(self, name, _text(getattr(self, name), name=name))

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "python_implementation": self.python_implementation,
            "python_version": self.python_version,
            "torch_version": self.torch_version,
            "engine_distribution_version": self.engine_version,
            "device": "cpu",
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())


@dataclass(frozen=True, slots=True)
class PoseBustersInternalExecutionArtifact:
    relative_path: str
    sha256: str
    size_bytes: int
    diagnostic_receipt_sha256: str
    diagnostic_config_sha256: str
    prepared_receptor_artifact_sha256: str
    prepared_ligand_artifact_sha256: str
    schema_id: str = POSEBUSTERS_INTERNAL_EXECUTION_ARTIFACT_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_INTERNAL_EXECUTION_ARTIFACT_SCHEMA_ID:
            raise PoseBustersInternalExecutionError(
                "unsupported internal-execution artifact schema"
            )
        relative = _text(self.relative_path, name="execution artifact path")
        path = PurePosixPath(relative)
        if (
            path.is_absolute()
            or len(path.parts) != 2
            or path.parts[1] != "redocking.report.json"
            or ".." in path.parts
            or "\\" in relative
        ):
            raise PoseBustersInternalExecutionError(
                "internal-execution artifact path is unsafe"
            )
        for name in (
            "sha256",
            "diagnostic_receipt_sha256",
            "diagnostic_config_sha256",
            "prepared_receptor_artifact_sha256",
            "prepared_ligand_artifact_sha256",
        ):
            object.__setattr__(self, name, _digest(getattr(self, name), name=name))
        size = _integer(
            self.size_bytes,
            name="execution artifact size",
            minimum=1,
            maximum=POSEBUSTERS_INTERNAL_EXECUTION_MAX_REPORT_BYTES,
        )
        object.__setattr__(self, "relative_path", relative)
        object.__setattr__(self, "size_bytes", size)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "role": "internal_redocking_diagnostic_report_json",
            "relative_path": self.relative_path,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "media_type": "application/json",
            "diagnostic_receipt_sha256": self.diagnostic_receipt_sha256,
            "diagnostic_config_sha256": self.diagnostic_config_sha256,
            "prepared_receptor_artifact_sha256": (
                self.prepared_receptor_artifact_sha256
            ),
            "prepared_ligand_artifact_sha256": (
                self.prepared_ligand_artifact_sha256
            ),
        }


@dataclass(frozen=True, slots=True)
class PoseBustersInternalExecutionCase:
    case_id: str
    status: str
    disposition_code: str
    preparation_status: str
    preparation_disposition_code: str
    preparation_error_code: str = ""
    execution_attempted: bool = False
    pocket_center_binary64_hex: tuple[str, ...] = ()
    case_seed: int = 0
    candidate_count: int = 0
    candidate_success_count: int = 0
    candidate_failure_count: int = 0
    selection_eligible_count: int = 0
    valid_pose_count: int = 0
    top_pose_count: int = 0
    artifact: PoseBustersInternalExecutionArtifact | None = None
    error_code: str = ""
    private_error_sha256: str = ""
    private_error_byte_length: int = 0
    schema_id: str = POSEBUSTERS_INTERNAL_EXECUTION_CASE_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_INTERNAL_EXECUTION_CASE_SCHEMA_ID:
            raise PoseBustersInternalExecutionError(
                "unsupported internal-execution case schema"
            )
        case = _text(self.case_id, name="case ID")
        if case.upper() != case or len(case.split("_")) != 2:
            raise PoseBustersInternalExecutionError(
                "internal-execution case ID is invalid"
            )
        status = _text(self.status, name="execution status")
        if status not in _CASE_STATUSES:
            raise PoseBustersInternalExecutionError(
                "internal-execution case status is invalid"
            )
        disposition = _text(
            self.disposition_code,
            name="execution disposition",
        )
        if not isinstance(self.execution_attempted, bool):
            raise PoseBustersInternalExecutionError(
                "execution_attempted must be boolean"
            )
        expected_disposition = {
            "success": (
                "claim_closed_internal_redocking_diagnostic_complete"
            ),
            "execution_failure": "internal_redocking_execution_failed",
            "abstain_chemistry_scope": (
                "chemistry_scope_abstention_retained"
            ),
            "blocked_preparation_failure": (
                "blocked_by_canonical_preparation_failure"
            ),
            "blocked_upstream_failure": (
                "blocked_by_upstream_intake_or_corpus_failure"
            ),
        }[status]
        if disposition != expected_disposition:
            raise PoseBustersInternalExecutionError(
                "internal-execution disposition disagrees with status"
            )
        preparation_status = _text(
            self.preparation_status,
            name="preparation status",
        )
        preparation_disposition = _text(
            self.preparation_disposition_code,
            name="preparation disposition",
        )
        preparation_error = _text(
            self.preparation_error_code,
            name="preparation error code",
            allow_empty=True,
        )
        center = tuple(
            _finite_hex(value, name="pocket center")
            for value in self.pocket_center_binary64_hex
        )
        seed = _integer(self.case_seed, name="case seed")
        counts = tuple(
            _integer(getattr(self, name), name=name)
            for name in (
                "candidate_count",
                "candidate_success_count",
                "candidate_failure_count",
                "selection_eligible_count",
                "valid_pose_count",
                "top_pose_count",
            )
        )
        (
            candidate_count,
            candidate_success,
            candidate_failure,
            eligible,
            valid_pose,
            top_pose,
        ) = counts
        error = _text(
            self.error_code,
            name="execution error code",
            allow_empty=status != "execution_failure",
        )
        private_digest = _digest(
            self.private_error_sha256,
            name="private execution error",
            allow_empty=True,
        )
        private_size = _integer(
            self.private_error_byte_length,
            name="private execution error size",
            maximum=16_384,
        )
        if status == "success":
            valid = (
                preparation_status == "prepared"
                and self.execution_attempted
                and len(center) == 3
                and candidate_count > 0
                and candidate_success + candidate_failure == candidate_count
                and eligible == valid_pose
                and eligible <= candidate_success
                and top_pose <= valid_pose
                and bool(top_pose) == bool(valid_pose)
                and isinstance(self.artifact, PoseBustersInternalExecutionArtifact)
                and PurePosixPath(self.artifact.relative_path).parts[0] == case
                and not preparation_error
                and not error
                and not private_digest
                and private_size == 0
            )
        elif status == "execution_failure":
            valid = (
                preparation_status == "prepared"
                and self.execution_attempted
                and len(center) == 3
                and counts == (0, 0, 0, 0, 0, 0)
                and self.artifact is None
                and not preparation_error
                and error == "internal_redocking_execution_failed"
                and bool(private_digest and private_size)
            )
        else:
            expected_preparation = {
                "abstain_chemistry_scope": "abstain_chemistry_scope",
                "blocked_preparation_failure": "preparation_failure",
                "blocked_upstream_failure": "upstream_failure",
            }[status]
            valid = (
                preparation_status == expected_preparation
                and not self.execution_attempted
                and not center
                and seed == 0
                and counts == (0, 0, 0, 0, 0, 0)
                and self.artifact is None
                and not error
                and not private_digest
                and private_size == 0
                and (
                    bool(preparation_error)
                    == (status != "abstain_chemistry_scope")
                )
            )
        if not valid:
            raise PoseBustersInternalExecutionError(
                "internal-execution case fields disagree with status"
            )
        object.__setattr__(self, "case_id", case)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "disposition_code", disposition)
        object.__setattr__(self, "preparation_status", preparation_status)
        object.__setattr__(
            self,
            "preparation_disposition_code",
            preparation_disposition,
        )
        object.__setattr__(self, "preparation_error_code", preparation_error)
        object.__setattr__(self, "pocket_center_binary64_hex", center)
        object.__setattr__(self, "case_seed", seed)
        object.__setattr__(self, "error_code", error)
        object.__setattr__(self, "private_error_sha256", private_digest)
        object.__setattr__(self, "private_error_byte_length", private_size)

    @property
    def has_any_valid_pose(self) -> bool:
        return self.status == "success" and self.valid_pose_count > 0

    @property
    def has_selected_valid_pose(self) -> bool:
        return self.status == "success" and self.top_pose_count > 0

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "case_id": self.case_id,
            "status": self.status,
            "disposition_code": self.disposition_code,
            "preparation_status": self.preparation_status,
            "preparation_disposition_code": self.preparation_disposition_code,
            "preparation_error_code": self.preparation_error_code,
            "execution_attempted": self.execution_attempted,
            "pocket_center_binary64_hex": list(
                self.pocket_center_binary64_hex
            ),
            "case_seed": self.case_seed if self.execution_attempted else None,
            "candidate_count": self.candidate_count,
            "candidate_success_count": self.candidate_success_count,
            "candidate_failure_count": self.candidate_failure_count,
            "selection_eligible_count": self.selection_eligible_count,
            "valid_pose_count": self.valid_pose_count,
            "top_pose_count": self.top_pose_count,
            "has_any_valid_pose": self.has_any_valid_pose,
            "has_selected_valid_pose": self.has_selected_valid_pose,
            "artifact": None if self.artifact is None else self.artifact.to_dict(),
            "error_code": self.error_code,
            "public_error_message": (
                "internal redocking execution failed"
                if self.status == "execution_failure"
                else ""
            ),
            "private_error_sha256": self.private_error_sha256,
            "private_error_byte_length": self.private_error_byte_length,
            "pose_validity_evaluated": self.candidate_success_count > 0,
            "symmetry_aware_native_rmsd_evaluated": False,
        }


@dataclass(frozen=True, slots=True)
class PoseBustersInternalExecutionMetric:
    metric_id: str
    numerator: int
    denominator: int
    schema_id: str = POSEBUSTERS_INTERNAL_EXECUTION_METRIC_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_INTERNAL_EXECUTION_METRIC_SCHEMA_ID:
            raise PoseBustersInternalExecutionError(
                "unsupported internal-execution metric schema"
            )
        metric = _text(self.metric_id, name="metric ID")
        numerator = _integer(self.numerator, name="metric numerator")
        denominator = _integer(
            self.denominator,
            name="metric denominator",
            minimum=1,
        )
        if numerator > denominator:
            raise PoseBustersInternalExecutionError(
                "metric numerator exceeds denominator"
            )
        object.__setattr__(self, "metric_id", metric)
        object.__setattr__(self, "numerator", numerator)
        object.__setattr__(self, "denominator", denominator)

    def to_dict(self) -> dict[str, object]:
        low, high = _wilson_interval(self.numerator, self.denominator)
        return {
            "schema_id": self.schema_id,
            "metric_id": self.metric_id,
            "numerator": self.numerator,
            "denominator": self.denominator,
            "rate_binary64_hex": (self.numerator / self.denominator).hex(),
            "confidence_level_binary64_hex": (0.95).hex(),
            "confidence_interval_method": "wilson_score_binomial",
            "confidence_interval_low_binary64_hex": low.hex(),
            "confidence_interval_high_binary64_hex": high.hex(),
            "denominator_scope": "all_cases",
        }


def _summary_metrics(
    rows: Sequence[PoseBustersInternalExecutionCase],
) -> tuple[PoseBustersInternalExecutionMetric, ...]:
    denominator = len(rows)
    predicates = (
        ("prepared_input_pair_rate", lambda row: row.preparation_status == "prepared"),
        ("internal_redocking_attempt_rate", lambda row: row.execution_attempted),
        (
            "internal_redocking_diagnostic_completion_rate",
            lambda row: row.status == "success",
        ),
        ("internal_redocking_failure_rate", lambda row: row.status == "execution_failure"),
        ("case_with_any_valid_pose_rate", lambda row: row.has_any_valid_pose),
        ("case_with_selected_valid_pose_rate", lambda row: row.has_selected_valid_pose),
    )
    return tuple(
        PoseBustersInternalExecutionMetric(
            metric_id=metric_id,
            numerator=sum(bool(predicate(row)) for row in rows),
            denominator=denominator,
        )
        for metric_id, predicate in predicates
    )


def _artifact_set_sha256(
    rows: Sequence[PoseBustersInternalExecutionCase],
) -> str:
    return _canonical_sha256(
        {
            row.case_id: row.artifact.to_dict()
            for row in rows
            if row.artifact is not None
        }
    )


@dataclass(frozen=True, slots=True)
class PoseBustersInternalExecutionReceipt:
    preparation_receipt_sha256: str
    preparation_receipt_file_sha256: str
    preparation_artifact_set_sha256: str
    preparation_runtime_identity_sha256: str
    preparation_case_projection_sha256: str
    configuration: PoseBustersInternalExecutionConfig
    runtime_identity: PoseBustersInternalExecutionRuntime
    implementation_source_sha256: str
    implementation_source_members: tuple[tuple[str, str], ...]
    case_rows: tuple[PoseBustersInternalExecutionCase, ...]
    metrics: tuple[PoseBustersInternalExecutionMetric, ...]
    artifact_set_sha256: str
    schema_id: str = POSEBUSTERS_INTERNAL_EXECUTION_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_INTERNAL_EXECUTION_SCHEMA_ID:
            raise PoseBustersInternalExecutionError(
                "unsupported internal-execution receipt schema"
            )
        if not isinstance(self.configuration, PoseBustersInternalExecutionConfig):
            raise TypeError("configuration has the wrong type")
        if not isinstance(self.runtime_identity, PoseBustersInternalExecutionRuntime):
            raise TypeError("runtime_identity has the wrong type")
        for name in (
            "preparation_receipt_sha256",
            "preparation_receipt_file_sha256",
            "preparation_artifact_set_sha256",
            "preparation_runtime_identity_sha256",
            "preparation_case_projection_sha256",
            "implementation_source_sha256",
            "artifact_set_sha256",
        ):
            object.__setattr__(self, name, _digest(getattr(self, name), name=name))
        members = tuple(
            (
                _text(role, name="implementation source role"),
                _digest(digest, name="implementation source digest"),
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
            raise PoseBustersInternalExecutionError(
                "implementation source identity is inconsistent"
            )
        rows = tuple(self.case_rows)
        if (
            not rows
            or any(
                not isinstance(row, PoseBustersInternalExecutionCase)
                for row in rows
            )
            or tuple(row.case_id for row in rows)
            != tuple(sorted(row.case_id for row in rows))
            or len({row.case_id for row in rows}) != len(rows)
        ):
            raise PoseBustersInternalExecutionError(
                "internal-execution rows must be canonical unique cases"
            )
        for row in rows:
            expected_seed = self.configuration.case_seed(row.case_id)
            if row.execution_attempted and row.case_seed != expected_seed:
                raise PoseBustersInternalExecutionError(
                    "case seed is not bound to configuration and case ID"
                )
            if row.status == "success":
                assert row.artifact is not None
                expected_config = self.configuration.diagnostic_config(row.case_id)
                if (
                    row.candidate_count != self.configuration.candidate_count
                    or row.top_pose_count > self.configuration.top_k
                    or row.artifact.diagnostic_config_sha256
                    != expected_config.fingerprint_sha256
                ):
                    raise PoseBustersInternalExecutionError(
                        "successful case disagrees with execution configuration"
                    )
        if any(
            not isinstance(row, PoseBustersInternalExecutionMetric)
            for row in self.metrics
        ):
            raise PoseBustersInternalExecutionError(
                "internal-execution metrics have the wrong type"
            )
        expected_metrics = _summary_metrics(rows)
        if tuple(row.to_dict() for row in self.metrics) != tuple(
            row.to_dict() for row in expected_metrics
        ):
            raise PoseBustersInternalExecutionError(
                "internal-execution metrics disagree with rows"
            )
        if self.artifact_set_sha256 != _artifact_set_sha256(rows):
            raise PoseBustersInternalExecutionError(
                "internal-execution artifact-set identity is inconsistent"
            )
        object.__setattr__(self, "implementation_source_members", members)
        object.__setattr__(self, "case_rows", rows)
        object.__setattr__(self, "metrics", expected_metrics)

    @property
    def attempted_case_count(self) -> int:
        return sum(row.execution_attempted for row in self.case_rows)

    @property
    def success_case_count(self) -> int:
        return sum(row.status == "success" for row in self.case_rows)

    @property
    def evaluated_candidate_count(self) -> int:
        return sum(row.candidate_success_count for row in self.case_rows)

    def _payload(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "preparation_receipt_sha256": self.preparation_receipt_sha256,
            "preparation_receipt_file_sha256": (
                self.preparation_receipt_file_sha256
            ),
            "preparation_artifact_set_sha256": (
                self.preparation_artifact_set_sha256
            ),
            "preparation_runtime_identity_sha256": (
                self.preparation_runtime_identity_sha256
            ),
            "preparation_case_projection_sha256": (
                self.preparation_case_projection_sha256
            ),
            "configuration": self.configuration.to_dict(),
            "configuration_sha256": self.configuration.fingerprint_sha256,
            "runtime_identity": self.runtime_identity.to_dict(),
            "runtime_identity_sha256": self.runtime_identity.fingerprint_sha256,
            "implementation_source_sha256": self.implementation_source_sha256,
            "implementation_source_members": dict(
                self.implementation_source_members
            ),
            "artifact_set_sha256": self.artifact_set_sha256,
            "all_case_denominator": len(self.case_rows),
            "attempted_case_count": self.attempted_case_count,
            "success_case_count": self.success_case_count,
            "evaluated_candidate_count": self.evaluated_candidate_count,
            "failed_or_abstained_case_count": (
                len(self.case_rows) - self.success_case_count
            ),
            "case_rows": [row.to_dict() for row in self.case_rows],
            "metrics": [row.to_dict() for row in self.metrics],
            "all_failure_rows_retained": True,
            "internal_redocking_diagnostic_batch_executed": (
                self.attempted_case_count > 0
            ),
            "generated_pose_validity_evaluated": (
                self.evaluated_candidate_count > 0
            ),
            "symmetry_aware_native_rmsd_evaluated": False,
            "posebusters_external_oracle_executed": False,
            "target_family_metrics_present": False,
            "wall_clock_runtime_metrics_present": False,
            "benchmark_executed": False,
            "scientific_blockers": list(
                POSEBUSTERS_INTERNAL_EXECUTION_BLOCKERS
            ),
            "scientifically_validated": False,
            "claim_safe": False,
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_sha256(self._payload())

    def to_dict(self) -> dict[str, object]:
        return {**self._payload(), "receipt_sha256": self.fingerprint_sha256}

    def write_json(self, output_path: str | os.PathLike[str]) -> Path:
        output = Path(output_path)
        output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        payload = _canonical_bytes(self.to_dict()) + b"\n"
        if len(payload) > POSEBUSTERS_INTERNAL_EXECUTION_MAX_RECEIPT_BYTES:
            raise PoseBustersInternalExecutionError(
                "internal-execution receipt exceeds its byte bound"
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
                raise PoseBustersInternalExecutionError(
                    "internal-execution receipt output already exists"
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


class _ExecutionRuntime(Protocol):
    identity: PoseBustersInternalExecutionRuntime

    def execute(
        self,
        receptor: AllAtomSystem,
        ligand: AllAtomSystem,
        *,
        receptor_artifact_sha256: str,
        ligand_artifact_sha256: str,
        pocket_center_angstrom: Sequence[float],
        pocket_radius_angstrom: float,
        config: RedockingDiagnosticConfig,
    ) -> Mapping[str, object]:
        ...


class _LocalExecutionRuntime:
    def __init__(self) -> None:
        self.identity = PoseBustersInternalExecutionRuntime(
            python_implementation=platform.python_implementation(),
            python_version=platform.python_version(),
            torch_version=str(torch.__version__),
            engine_version=DISTRIBUTION_VERSION,
        )

    def execute(
        self,
        receptor: AllAtomSystem,
        ligand: AllAtomSystem,
        *,
        receptor_artifact_sha256: str,
        ligand_artifact_sha256: str,
        pocket_center_angstrom: Sequence[float],
        pocket_radius_angstrom: float,
        config: RedockingDiagnosticConfig,
    ) -> Mapping[str, object]:
        return run_prepared_redocking_diagnostic(
            receptor,
            ligand,
            receptor_artifact_sha256=receptor_artifact_sha256,
            ligand_artifact_sha256=ligand_artifact_sha256,
            pocket_center_angstrom=pocket_center_angstrom,
            pocket_radius_angstrom=pocket_radius_angstrom,
            config=config,
        )


def _load_runtime() -> _ExecutionRuntime:
    return _LocalExecutionRuntime()


def _preparation_projection(
    preparation: PoseBustersInternalPreparationReceipt,
) -> dict[str, object]:
    return {
        row.case_id: {
            "status": row.status,
            "disposition_code": row.disposition_code,
            "error_code": row.error_code,
            "pocket_center_binary64_hex": list(
                row.pocket_center_binary64_hex
            ),
            "artifacts": [artifact.to_dict() for artifact in row.artifacts],
        }
        for row in preparation.case_rows
    }


def _blocked_row(
    row: PoseBustersInternalPreparationCase,
) -> PoseBustersInternalExecutionCase:
    status = _PREPARATION_STATUS_TO_BLOCKED_STATUS.get(row.status)
    if status is None:
        raise PoseBustersInternalExecutionError(
            "prepared row cannot be projected as a blocked execution"
        )
    return PoseBustersInternalExecutionCase(
        case_id=row.case_id,
        status=status,
        disposition_code={
            "abstain_chemistry_scope": "chemistry_scope_abstention_retained",
            "blocked_preparation_failure": "blocked_by_canonical_preparation_failure",
            "blocked_upstream_failure": "blocked_by_upstream_intake_or_corpus_failure",
        }[status],
        preparation_status=row.status,
        preparation_disposition_code=row.disposition_code,
        preparation_error_code=row.error_code,
    )


def _prepared_system(
    artifact_root: Path,
    artifact: Any,
) -> tuple[AllAtomSystem, bytes]:
    source = _read_exact_regular_file(
        artifact_root / PurePosixPath(artifact.relative_path),
        maximum_bytes=min(
            POSEBUSTERS_INTERNAL_PREPARATION_MAX_ARTIFACT_BYTES,
            MAX_CANONICAL_SYSTEM_JSON_BYTES,
        ),
    )
    if (
        len(source) != artifact.size_bytes
        or hashlib.sha256(source).hexdigest() != artifact.sha256
    ):
        raise PoseBustersInternalExecutionError(
            "prepared canonical artifact identity changed after verification"
        )
    system = all_atom_system_from_canonical_json(source, device="cpu")
    if canonical_system_sha256(system) != artifact.system_sha256:
        raise PoseBustersInternalExecutionError(
            "prepared canonical artifact system identity is inconsistent"
        )
    return system, source


def _report_counts(
    report: Mapping[str, object],
) -> tuple[int, int, int, int, int, int]:
    summary = report.get("summary")
    if not isinstance(summary, Mapping):
        raise PoseBustersInternalExecutionError(
            "redocking diagnostic summary is missing"
        )
    names = (
        "candidate_count",
        "success_count",
        "failure_count",
        "selection_eligible_count",
        "valid_pose_count",
        "top_pose_count",
    )
    values = tuple(
        _integer(summary.get(name), name=f"diagnostic {name}")
        for name in names
    )
    return (
        values[0],
        values[1],
        values[2],
        values[3],
        values[4],
        values[5],
    )


def _execute_case(
    row: PoseBustersInternalPreparationCase,
    preparation_artifact_root: Path,
    runtime: _ExecutionRuntime,
    configuration: PoseBustersInternalExecutionConfig,
    pocket_radius_angstrom: float,
) -> tuple[PoseBustersInternalExecutionCase, dict[str, bytes]]:
    if row.status != "prepared":
        return _blocked_row(row), {}
    center_hex = tuple(row.pocket_center_binary64_hex)
    center = tuple(float.fromhex(value) for value in center_hex)
    config = configuration.diagnostic_config(row.case_id)
    artifacts = {artifact.role: artifact for artifact in row.artifacts}
    try:
        receptor_artifact = artifacts["canonical_receptor_json"]
        ligand_artifact = artifacts["canonical_ligand_json"]
        receptor, _receptor_source = _prepared_system(
            preparation_artifact_root,
            receptor_artifact,
        )
        ligand, _ligand_source = _prepared_system(
            preparation_artifact_root,
            ligand_artifact,
        )
        report = dict(
            runtime.execute(
                receptor,
                ligand,
                receptor_artifact_sha256=receptor_artifact.sha256,
                ligand_artifact_sha256=ligand_artifact.sha256,
                pocket_center_angstrom=center,
                pocket_radius_angstrom=pocket_radius_angstrom,
                config=config,
            )
        )
        report_source = canonical_json_bytes(report)
        if len(report_source) > POSEBUSTERS_INTERNAL_EXECUTION_MAX_REPORT_BYTES:
            raise PoseBustersInternalExecutionError(
                "redocking diagnostic report exceeds its byte bound"
            )
        verified = verify_redocking_diagnostic_report(report_source)
        source_artifacts = verified.get("source_artifacts")
        config_report = verified.get("config")
        if (
            verified.get("status") != "diagnostic_complete"
            or not isinstance(source_artifacts, Mapping)
            or source_artifacts.get("receptor_canonical_json_sha256")
            != receptor_artifact.sha256
            or source_artifacts.get("ligand_canonical_json_sha256")
            != ligand_artifact.sha256
            or not isinstance(config_report, Mapping)
            or config_report.get("config_sha256") != config.fingerprint_sha256
        ):
            raise PoseBustersInternalExecutionError(
                "redocking report is cross-wired to another input or config"
            )
        counts = _report_counts(verified)
        report_receipt_sha256 = _digest(
            verified.get("receipt_sha256"),
            name="diagnostic receipt SHA-256",
        )
        artifact = PoseBustersInternalExecutionArtifact(
            relative_path=f"{row.case_id}/redocking.report.json",
            sha256=hashlib.sha256(report_source).hexdigest(),
            size_bytes=len(report_source),
            diagnostic_receipt_sha256=report_receipt_sha256,
            diagnostic_config_sha256=config.fingerprint_sha256,
            prepared_receptor_artifact_sha256=receptor_artifact.sha256,
            prepared_ligand_artifact_sha256=ligand_artifact.sha256,
        )
    except Exception as exc:
        private_sha256, private_size = _normalized_error(exc)
        return PoseBustersInternalExecutionCase(
            case_id=row.case_id,
            status="execution_failure",
            disposition_code="internal_redocking_execution_failed",
            preparation_status=row.status,
            preparation_disposition_code=row.disposition_code,
            preparation_error_code=row.error_code,
            execution_attempted=True,
            pocket_center_binary64_hex=center_hex,
            case_seed=config.seed,
            error_code="internal_redocking_execution_failed",
            private_error_sha256=private_sha256,
            private_error_byte_length=private_size,
        ), {}
    return PoseBustersInternalExecutionCase(
        case_id=row.case_id,
        status="success",
        disposition_code="claim_closed_internal_redocking_diagnostic_complete",
        preparation_status=row.status,
        preparation_disposition_code=row.disposition_code,
        preparation_error_code=row.error_code,
        execution_attempted=True,
        pocket_center_binary64_hex=center_hex,
        case_seed=config.seed,
        candidate_count=counts[0],
        candidate_success_count=counts[1],
        candidate_failure_count=counts[2],
        selection_eligible_count=counts[3],
        valid_pose_count=counts[4],
        top_pose_count=counts[5],
        artifact=artifact,
    ), {artifact.relative_path: report_source}


def _implementation_source_members(
    preparation: PoseBustersInternalPreparationReceipt,
) -> tuple[tuple[str, str], ...]:
    members = dict(preparation.implementation_source_members)
    root = Path(__file__).parents[1]
    members.update(
        {
            "internal_execution": _source_file_sha256(__file__),
            "redocking_cli": _source_file_sha256(
                root / "benchmark" / "redocking_cli.py"
            ),
            "docking_proposals": _source_file_sha256(
                root / "docking" / "proposals.py"
            ),
            "docking_search": _source_file_sha256(
                root / "docking" / "search.py"
            ),
            "docking_steric_field": _source_file_sha256(
                root / "docking" / "steric_field.py"
            ),
            "docking_interpretable_scoring": _source_file_sha256(
                root / "docking" / "interpretable_scoring.py"
            ),
            "docking_interpretable_refinement": _source_file_sha256(
                root / "docking" / "interpretable_refinement.py"
            ),
            "docking_chemistry_validity_v2": _source_file_sha256(
                root / "docking" / "chemistry_validity_v2.py"
            ),
        }
    )
    return tuple(sorted(members.items()))


def _build_execution(
    preparation_receipt_path: str | os.PathLike[str],
    preparation_artifact_root: str | os.PathLike[str],
    archive_path: str | os.PathLike[str],
    selection_path: str | os.PathLike[str],
    intake_receipt_path: str | os.PathLike[str],
    corpus_audit_receipt_path: str | os.PathLike[str],
    *,
    contract: PoseBustersArchiveContract,
    preparation_configuration: PoseBustersInternalPreparationConfig | None,
    configuration: PoseBustersInternalExecutionConfig,
) -> tuple[PoseBustersInternalExecutionReceipt, dict[str, bytes]]:
    try:
        preparation = verify_posebusters_internal_preparation_receipt(
            preparation_receipt_path,
            preparation_artifact_root,
            archive_path,
            selection_path,
            intake_receipt_path,
            corpus_audit_receipt_path,
            contract=contract,
            configuration=preparation_configuration,
        )
    except PoseBustersInternalPreparationError as exc:
        raise PoseBustersInternalExecutionError(
            "internal execution requires an exact verified preparation receipt"
        ) from exc
    preparation_source = _read_exact_regular_file(
        preparation_receipt_path,
        maximum_bytes=POSEBUSTERS_INTERNAL_EXECUTION_MAX_RECEIPT_BYTES,
    )
    if preparation_source != _canonical_bytes(preparation.to_dict()) + b"\n":
        raise PoseBustersInternalExecutionError(
            "preparation receipt changed after exact verification"
        )
    runtime = _load_runtime()
    payloads: dict[str, bytes] = {}
    rows_list: list[PoseBustersInternalExecutionCase] = []
    for preparation_row in preparation.case_rows:
        row, case_payloads = _execute_case(
            preparation_row,
            Path(preparation_artifact_root),
            runtime,
            configuration,
            preparation.configuration.pocket_radius_angstrom,
        )
        if set(payloads).intersection(case_payloads):
            raise PoseBustersInternalExecutionError(
                "internal-execution artifact paths are duplicated"
            )
        rows_list.append(row)
        payloads.update(case_payloads)
    rows = tuple(rows_list)
    members = _implementation_source_members(preparation)
    receipt = PoseBustersInternalExecutionReceipt(
        preparation_receipt_sha256=preparation.fingerprint_sha256,
        preparation_receipt_file_sha256=hashlib.sha256(
            preparation_source
        ).hexdigest(),
        preparation_artifact_set_sha256=preparation.artifact_set_sha256,
        preparation_runtime_identity_sha256=(
            preparation.runtime_identity.fingerprint_sha256
        ),
        preparation_case_projection_sha256=_canonical_sha256(
            _preparation_projection(preparation)
        ),
        configuration=configuration,
        runtime_identity=runtime.identity,
        implementation_source_sha256=_canonical_sha256(dict(members)),
        implementation_source_members=members,
        case_rows=rows,
        metrics=_summary_metrics(rows),
        artifact_set_sha256=_artifact_set_sha256(rows),
    )
    expected_paths = {
        row.artifact.relative_path
        for row in rows
        if row.artifact is not None
    }
    if set(payloads) != expected_paths:
        raise PoseBustersInternalExecutionError(
            "internal-execution artifact payload set is incomplete"
        )
    return receipt, payloads


def materialize_posebusters_internal_execution(
    preparation_receipt_path: str | os.PathLike[str],
    preparation_artifact_root: str | os.PathLike[str],
    archive_path: str | os.PathLike[str],
    selection_path: str | os.PathLike[str],
    intake_receipt_path: str | os.PathLike[str],
    corpus_audit_receipt_path: str | os.PathLike[str],
    output_artifact_root: str | os.PathLike[str],
    *,
    contract: PoseBustersArchiveContract = OFFICIAL_POSEBUSTERS_ARCHIVE_CONTRACT,
    preparation_configuration: PoseBustersInternalPreparationConfig | None = None,
    configuration: PoseBustersInternalExecutionConfig | None = None,
) -> PoseBustersInternalExecutionReceipt:
    """Execute all prepared cases and retain every cohort disposition."""

    active = (
        PoseBustersInternalExecutionConfig()
        if configuration is None
        else configuration
    )
    if not isinstance(active, PoseBustersInternalExecutionConfig):
        raise TypeError("configuration has the wrong type")
    receipt, payloads = _build_execution(
        preparation_receipt_path,
        preparation_artifact_root,
        archive_path,
        selection_path,
        intake_receipt_path,
        corpus_audit_receipt_path,
        contract=contract,
        preparation_configuration=preparation_configuration,
        configuration=active,
    )
    try:
        _write_artifact_tree(Path(output_artifact_root), payloads)
    except PoseBustersExternalPreparationError as exc:
        raise PoseBustersInternalExecutionError(
            "internal-execution artifact tree could not be materialized"
        ) from exc
    return receipt


def verify_posebusters_internal_execution_receipt(
    execution_receipt_path: str | os.PathLike[str],
    output_artifact_root: str | os.PathLike[str],
    preparation_receipt_path: str | os.PathLike[str],
    preparation_artifact_root: str | os.PathLike[str],
    archive_path: str | os.PathLike[str],
    selection_path: str | os.PathLike[str],
    intake_receipt_path: str | os.PathLike[str],
    corpus_audit_receipt_path: str | os.PathLike[str],
    *,
    contract: PoseBustersArchiveContract = OFFICIAL_POSEBUSTERS_ARCHIVE_CONTRACT,
    preparation_configuration: PoseBustersInternalPreparationConfig | None = None,
    configuration: PoseBustersInternalExecutionConfig | None = None,
) -> PoseBustersInternalExecutionReceipt:
    """Reexecute the complete batch and verify receipt plus artifact tree."""

    active = (
        PoseBustersInternalExecutionConfig()
        if configuration is None
        else configuration
    )
    if not isinstance(active, PoseBustersInternalExecutionConfig):
        raise TypeError("configuration has the wrong type")
    source = _read_exact_regular_file(
        execution_receipt_path,
        maximum_bytes=POSEBUSTERS_INTERNAL_EXECUTION_MAX_RECEIPT_BYTES,
    )
    try:
        raw = json.loads(
            source.decode("ascii"),
            object_pairs_hook=_json_object_pairs,
            parse_constant=_reject_json_constant,
        )
    except PoseBustersInternalExecutionError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PoseBustersInternalExecutionError(
            "internal-execution receipt must be ASCII JSON"
        ) from exc
    if (
        not isinstance(raw, dict)
        or raw.get("schema_id") != POSEBUSTERS_INTERNAL_EXECUTION_SCHEMA_ID
        or source != _canonical_bytes(raw) + b"\n"
        or raw.get("receipt_sha256")
        != _canonical_sha256(
            {key: value for key, value in raw.items() if key != "receipt_sha256"}
        )
    ):
        raise PoseBustersInternalExecutionError(
            "internal-execution receipt is not canonical or self-authenticating"
        )
    expected, payloads = _build_execution(
        preparation_receipt_path,
        preparation_artifact_root,
        archive_path,
        selection_path,
        intake_receipt_path,
        corpus_audit_receipt_path,
        contract=contract,
        preparation_configuration=preparation_configuration,
        configuration=active,
    )
    if source != _canonical_bytes(expected.to_dict()) + b"\n":
        raise PoseBustersInternalExecutionError(
            "internal-execution receipt failed exact source-tree reexecution"
        )
    try:
        _verify_artifact_tree(Path(output_artifact_root), payloads)
    except PoseBustersExternalPreparationError as exc:
        raise PoseBustersInternalExecutionError(
            "internal-execution artifact tree failed exact verification"
        ) from exc
    return expected


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="betelgeuze-engine-v2-posebusters-internal-execute",
        description=(
            "Run failure-inclusive internal redocking from canonical prepared inputs."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("materialize", "verify"):
        command = subparsers.add_parser(name)
        command.add_argument("--preparation-receipt", required=True)
        command.add_argument("--preparation-artifact-root", required=True)
        command.add_argument("--archive", required=True)
        command.add_argument("--selection", required=True)
        command.add_argument("--intake-receipt", required=True)
        command.add_argument("--corpus-audit-receipt", required=True)
        command.add_argument("--output-artifact-root", required=True)
        command.add_argument("--receipt", required=True)
        command.add_argument("--candidate-count", type=int, default=64)
        command.add_argument("--top-k", type=int, default=10)
        command.add_argument("--max-torsions", type=int, default=32)
        command.add_argument("--translation-radius", type=float, default=4.0)
        command.add_argument("--diversity-rmsd", type=float, default=0.5)
        command.add_argument("--max-refinement-steps", type=int, default=6)
        command.add_argument("--base-seed", type=int, default=7_301)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    configuration = PoseBustersInternalExecutionConfig(
        candidate_count=args.candidate_count,
        top_k=args.top_k,
        max_torsions=args.max_torsions,
        translation_radius_angstrom=args.translation_radius,
        diversity_rmsd_angstrom=args.diversity_rmsd,
        max_refinement_steps=args.max_refinement_steps,
        base_seed=args.base_seed,
    )
    common = {
        "preparation_receipt_path": args.preparation_receipt,
        "preparation_artifact_root": args.preparation_artifact_root,
        "archive_path": args.archive,
        "selection_path": args.selection,
        "intake_receipt_path": args.intake_receipt,
        "corpus_audit_receipt_path": args.corpus_audit_receipt,
        "configuration": configuration,
    }
    if args.command == "materialize":
        if Path(args.receipt).exists():
            raise PoseBustersInternalExecutionError(
                "internal-execution receipt output already exists"
            )
        receipt = materialize_posebusters_internal_execution(
            **common,
            output_artifact_root=args.output_artifact_root,
        )
        receipt.write_json(args.receipt)
    else:
        receipt = verify_posebusters_internal_execution_receipt(
            **common,
            execution_receipt_path=args.receipt,
            output_artifact_root=args.output_artifact_root,
        )
    print(
        json.dumps(
            {
                "receipt_sha256": receipt.fingerprint_sha256,
                "all_case_denominator": len(receipt.case_rows),
                "attempted_case_count": receipt.attempted_case_count,
                "success_case_count": receipt.success_case_count,
                "benchmark_executed": False,
                "claim_safe": False,
            },
            sort_keys=True,
        )
    )
    return 0


__all__ = [
    "POSEBUSTERS_INTERNAL_EXECUTION_ARTIFACT_SCHEMA_ID",
    "POSEBUSTERS_INTERNAL_EXECUTION_BLOCKERS",
    "POSEBUSTERS_INTERNAL_EXECUTION_CASE_SCHEMA_ID",
    "POSEBUSTERS_INTERNAL_EXECUTION_CONFIG_SCHEMA_ID",
    "POSEBUSTERS_INTERNAL_EXECUTION_MAX_RECEIPT_BYTES",
    "POSEBUSTERS_INTERNAL_EXECUTION_MAX_REPORT_BYTES",
    "POSEBUSTERS_INTERNAL_EXECUTION_METRIC_SCHEMA_ID",
    "POSEBUSTERS_INTERNAL_EXECUTION_RUNTIME_SCHEMA_ID",
    "POSEBUSTERS_INTERNAL_EXECUTION_SCHEMA_ID",
    "PoseBustersInternalExecutionArtifact",
    "PoseBustersInternalExecutionCase",
    "PoseBustersInternalExecutionConfig",
    "PoseBustersInternalExecutionError",
    "PoseBustersInternalExecutionMetric",
    "PoseBustersInternalExecutionReceipt",
    "PoseBustersInternalExecutionRuntime",
    "main",
    "materialize_posebusters_internal_execution",
    "verify_posebusters_internal_execution_receipt",
]


if __name__ == "__main__":
    raise SystemExit(main())
