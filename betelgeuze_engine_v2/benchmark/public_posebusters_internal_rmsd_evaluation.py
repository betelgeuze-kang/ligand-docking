"""Connectivity-symmetry direct RMSD for internal PoseBusters diagnostics.

The evaluator consumes an exactly reexecuted internal-redocking receipt.  It
maps the RDKit-prepared ligand back to the raw start-conformer atom order,
enumerates bounded native-to-start heavy-graph isomorphisms, and computes
direct receptor-frame RMSD for every selected internal pose without alignment.
Every execution failure and abstention remains in the cohort denominator.

This is a diagnostic connectivity-symmetry endpoint.  It does not replace the
pinned PoseBusters oracle, interpret atom stereochemistry completely, or open a
public benchmark claim.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import tempfile
from typing import Any, Mapping, Sequence
import zipfile

import torch

from betelgeuze_engine_v2.io import SDFParseError, parse_sdf_v2000
from betelgeuze_engine_v2.molecular import (
    MAX_CANONICAL_SYSTEM_JSON_BYTES,
    AllAtomSystem,
    all_atom_system_from_canonical_json,
    canonical_system_sha256,
)

from .public_ligand_graph_audit import _projected_labeled_graph
from .public_materialization import (
    MAX_PUBLIC_REFERENCE_GRAPH_SEARCH_STATES,
    MAX_PUBLIC_REFERENCE_SYMMETRY_PERMUTATIONS,
    PublicReferenceMaterializationError,
    _graph_isomorphisms,
)
from .public_posebusters_corpus_audit import (
    PoseBustersCorpusAuditError,
    _canonical_bytes,
    _canonical_sha256,
    _read_member,
    _source_file_sha256,
)
from .public_posebusters_intake import (
    OFFICIAL_POSEBUSTERS_ARCHIVE_CONTRACT,
    PoseBustersArchiveContract,
    PoseBustersArchiveIntakeError,
    POSEBUSTERS_ARCHIVE_MAX_RECEIPT_BYTES,
    _hash_descriptor,
    _read_exact_regular_file,
    _regular_file_descriptor,
    verify_posebusters_archive_intake_receipt,
)
from .public_posebusters_internal_execution import (
    POSEBUSTERS_INTERNAL_EXECUTION_MAX_RECEIPT_BYTES,
    POSEBUSTERS_INTERNAL_EXECUTION_MAX_REPORT_BYTES,
    PoseBustersInternalExecutionCase,
    PoseBustersInternalExecutionConfig,
    PoseBustersInternalExecutionError,
    PoseBustersInternalExecutionReceipt,
    verify_posebusters_internal_execution_receipt,
)
from .public_posebusters_internal_preparation import (
    POSEBUSTERS_INTERNAL_PREPARATION_MAX_ARTIFACT_BYTES,
    PoseBustersInternalPreparationConfig,
)
from .redocking_cli import verify_redocking_diagnostic_report


POSEBUSTERS_INTERNAL_RMSD_CONFIG_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_internal_rmsd_config/1.0.0"
)
POSEBUSTERS_INTERNAL_RMSD_POSE_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_internal_rmsd_pose/1.0.0"
)
POSEBUSTERS_INTERNAL_RMSD_CASE_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_internal_rmsd_case/1.0.0"
)
POSEBUSTERS_INTERNAL_RMSD_METRIC_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_internal_rmsd_metric/1.0.0"
)
POSEBUSTERS_INTERNAL_RMSD_EVALUATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_internal_rmsd_evaluation/1.0.0"
)

POSEBUSTERS_INTERNAL_RMSD_MAX_RECEIPT_BYTES = 64 * 1024 * 1024
POSEBUSTERS_INTERNAL_RMSD_BLOCKERS = (
    "connectivity_symmetry_does_not_interpret_complete_atom_stereochemistry",
    "pinned_posebusters_external_validity_and_rmsd_oracle_missing",
    "pose_generation_and_scoring_not_scientifically_validated",
    "validated_force_field_pose_minimization_missing",
    "target_family_and_chemistry_stratified_metrics_missing",
    "wall_clock_and_peak_memory_measurement_missing",
    "second_cpu_host_exact_reproduction_missing",
    "independent_external_rerun_missing",
    "scientific_review_missing",
    "evaluation_runtime_binary_and_dependency_payload_identity_incomplete",
)

_CASE_STATUSES = {
    "blocked_execution",
    "evaluated",
    "evaluation_failure",
}
_EXECUTION_STATUSES = {
    "abstain_chemistry_scope",
    "blocked_preparation_failure",
    "blocked_upstream_failure",
    "execution_failure",
    "success",
}
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class PoseBustersInternalRMSDEvaluationError(ValueError):
    """Internal RMSD evaluation input or receipt is invalid."""


def _digest(value: object, *, name: str, allow_empty: bool = False) -> str:
    text = str(value or "").strip().lower()
    if allow_empty and not text:
        return ""
    if _SHA256_RE.fullmatch(text) is None:
        raise PoseBustersInternalRMSDEvaluationError(
            f"{name} must be a lowercase SHA-256"
        )
    return text


def _text(value: object, *, name: str, allow_empty: bool = False) -> str:
    text = str(value or "").strip()
    if (not text and not allow_empty) or len(text) > 512 or "\x00" in text:
        raise PoseBustersInternalRMSDEvaluationError(
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
        raise PoseBustersInternalRMSDEvaluationError(
            f"{name} must be an integer"
        )
    if not minimum <= value <= maximum:
        raise PoseBustersInternalRMSDEvaluationError(
            f"{name} must be in [{minimum}, {maximum}]"
        )
    return value


def _finite_hex(
    value: object,
    *,
    name: str,
    nonnegative: bool = False,
) -> str:
    if not isinstance(value, str):
        raise PoseBustersInternalRMSDEvaluationError(
            f"{name} must be canonical finite binary64"
        )
    try:
        number = float.fromhex(value)
    except ValueError as exc:
        raise PoseBustersInternalRMSDEvaluationError(
            f"{name} must be canonical finite binary64"
        ) from exc
    if (
        not math.isfinite(number)
        or number.hex() != value
        or (nonnegative and number < 0.0)
    ):
        raise PoseBustersInternalRMSDEvaluationError(
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
            raise PoseBustersInternalRMSDEvaluationError(
                f"duplicate JSON key: {key}"
            )
        result[key] = value
    return result


def _reject_json_constant(value: str) -> object:
    raise PoseBustersInternalRMSDEvaluationError(
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
class PoseBustersInternalRMSDConfig:
    rmsd_threshold_angstrom: float = 2.0
    top_k: int = 5
    max_symmetry_permutations: int = (
        MAX_PUBLIC_REFERENCE_SYMMETRY_PERMUTATIONS
    )
    max_graph_search_states: int = MAX_PUBLIC_REFERENCE_GRAPH_SEARCH_STATES
    schema_id: str = POSEBUSTERS_INTERNAL_RMSD_CONFIG_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_INTERNAL_RMSD_CONFIG_SCHEMA_ID:
            raise PoseBustersInternalRMSDEvaluationError(
                "unsupported internal RMSD config schema"
            )
        threshold = float(self.rmsd_threshold_angstrom)
        if not math.isfinite(threshold) or threshold <= 0.0:
            raise PoseBustersInternalRMSDEvaluationError(
                "RMSD threshold must be positive and finite"
            )
        top_k = _integer(self.top_k, name="top_k", minimum=1, maximum=128)
        mappings = _integer(
            self.max_symmetry_permutations,
            name="max_symmetry_permutations",
            minimum=1,
            maximum=MAX_PUBLIC_REFERENCE_SYMMETRY_PERMUTATIONS,
        )
        states = _integer(
            self.max_graph_search_states,
            name="max_graph_search_states",
            minimum=1,
            maximum=MAX_PUBLIC_REFERENCE_GRAPH_SEARCH_STATES,
        )
        object.__setattr__(self, "rmsd_threshold_angstrom", threshold)
        object.__setattr__(self, "top_k", top_k)
        object.__setattr__(self, "max_symmetry_permutations", mappings)
        object.__setattr__(self, "max_graph_search_states", states)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "rmsd_threshold_angstrom_binary64_hex": (
                self.rmsd_threshold_angstrom.hex()
            ),
            "top_k": self.top_k,
            "max_symmetry_permutations": self.max_symmetry_permutations,
            "max_graph_search_states": self.max_graph_search_states,
            "alignment_policy": "direct_receptor_frame_no_ligand_alignment",
            "symmetry_policy": (
                "all_bounded_native_to_start_heavy_connectivity_isomorphisms_"
                "mapped_through_prepared_source_atom_indices"
            ),
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())


@dataclass(frozen=True, slots=True)
class PoseBustersInternalRMSDPose:
    rank: int
    candidate_id: str
    proposal_fingerprint_sha256: str
    pose_system_sha256: str
    coordinates_sha256: str
    internal_pose_valid: bool
    direct_rmsd_angstrom_binary64_hex: str
    symmetry_mapping_index: int
    symmetry_mapping_count: int
    schema_id: str = POSEBUSTERS_INTERNAL_RMSD_POSE_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_INTERNAL_RMSD_POSE_SCHEMA_ID:
            raise PoseBustersInternalRMSDEvaluationError(
                "unsupported internal RMSD pose schema"
            )
        rank = _integer(self.rank, name="pose rank", minimum=1, maximum=128)
        candidate = _text(self.candidate_id, name="candidate ID")
        if not isinstance(self.internal_pose_valid, bool):
            raise PoseBustersInternalRMSDEvaluationError(
                "internal_pose_valid must be boolean"
            )
        for name in (
            "proposal_fingerprint_sha256",
            "pose_system_sha256",
            "coordinates_sha256",
        ):
            object.__setattr__(self, name, _digest(getattr(self, name), name=name))
        rmsd = _finite_hex(
            self.direct_rmsd_angstrom_binary64_hex,
            name="direct RMSD",
            nonnegative=True,
        )
        mapping_count = _integer(
            self.symmetry_mapping_count,
            name="symmetry mapping count",
            minimum=1,
            maximum=MAX_PUBLIC_REFERENCE_SYMMETRY_PERMUTATIONS,
        )
        mapping_index = _integer(
            self.symmetry_mapping_index,
            name="symmetry mapping index",
            maximum=mapping_count - 1,
        )
        object.__setattr__(self, "rank", rank)
        object.__setattr__(self, "candidate_id", candidate)
        object.__setattr__(self, "direct_rmsd_angstrom_binary64_hex", rmsd)
        object.__setattr__(self, "symmetry_mapping_count", mapping_count)
        object.__setattr__(self, "symmetry_mapping_index", mapping_index)

    @property
    def direct_rmsd_angstrom(self) -> float:
        return float.fromhex(self.direct_rmsd_angstrom_binary64_hex)

    def to_dict(self, *, threshold_angstrom: float) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "rank": self.rank,
            "candidate_id": self.candidate_id,
            "proposal_fingerprint_sha256": self.proposal_fingerprint_sha256,
            "pose_system_sha256": self.pose_system_sha256,
            "coordinates_sha256": self.coordinates_sha256,
            "internal_pose_valid": self.internal_pose_valid,
            "direct_rmsd_angstrom_binary64_hex": (
                self.direct_rmsd_angstrom_binary64_hex
            ),
            "symmetry_mapping_index": self.symmetry_mapping_index,
            "symmetry_mapping_count": self.symmetry_mapping_count,
            "rmsd_within_threshold": (
                self.direct_rmsd_angstrom <= threshold_angstrom
            ),
            "valid_and_rmsd_within_threshold": (
                self.internal_pose_valid
                and self.direct_rmsd_angstrom <= threshold_angstrom
            ),
            "alignment_policy": "direct_receptor_frame_no_ligand_alignment",
        }


@dataclass(frozen=True, slots=True)
class PoseBustersInternalRMSDCase:
    case_id: str
    status: str
    disposition_code: str
    execution_status: str
    execution_disposition_code: str
    execution_error_code: str
    evaluation_attempted: bool = False
    native_ligand_source_sha256: str = ""
    start_ligand_source_sha256: str = ""
    prepared_ligand_artifact_sha256: str = ""
    prepared_ligand_system_sha256: str = ""
    diagnostic_report_receipt_sha256: str = ""
    native_to_start_symmetry_mapping_count: int = 0
    native_to_prepared_mapping_set_sha256: str = ""
    pose_results: tuple[PoseBustersInternalRMSDPose, ...] = ()
    error_code: str = ""
    private_error_sha256: str = ""
    private_error_byte_length: int = 0
    schema_id: str = POSEBUSTERS_INTERNAL_RMSD_CASE_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_INTERNAL_RMSD_CASE_SCHEMA_ID:
            raise PoseBustersInternalRMSDEvaluationError(
                "unsupported internal RMSD case schema"
            )
        case = _text(self.case_id, name="case ID")
        if case.upper() != case or len(case.split("_")) != 2:
            raise PoseBustersInternalRMSDEvaluationError(
                "internal RMSD case ID is invalid"
            )
        status = _text(self.status, name="RMSD evaluation status")
        if status not in _CASE_STATUSES:
            raise PoseBustersInternalRMSDEvaluationError(
                "internal RMSD case status is invalid"
            )
        disposition = _text(
            self.disposition_code,
            name="RMSD evaluation disposition",
        )
        expected_disposition = {
            "evaluated": "connectivity_symmetry_direct_rmsd_evaluated",
            "evaluation_failure": "internal_rmsd_evaluation_failed",
            "blocked_execution": "blocked_by_internal_execution_disposition",
        }[status]
        if disposition != expected_disposition:
            raise PoseBustersInternalRMSDEvaluationError(
                "internal RMSD disposition disagrees with status"
            )
        execution_status = _text(
            self.execution_status,
            name="execution status",
        )
        if execution_status not in _EXECUTION_STATUSES:
            raise PoseBustersInternalRMSDEvaluationError(
                "internal RMSD execution status is invalid"
            )
        if not isinstance(self.evaluation_attempted, bool):
            raise PoseBustersInternalRMSDEvaluationError(
                "evaluation_attempted must be boolean"
            )
        execution_disposition = _text(
            self.execution_disposition_code,
            name="execution disposition",
        )
        execution_error = _text(
            self.execution_error_code,
            name="execution error",
            allow_empty=True,
        )
        source_digests = tuple(
            _digest(
                getattr(self, name),
                name=name,
                allow_empty=True,
            )
            for name in (
                "native_ligand_source_sha256",
                "start_ligand_source_sha256",
                "prepared_ligand_artifact_sha256",
                "prepared_ligand_system_sha256",
                "diagnostic_report_receipt_sha256",
                "native_to_prepared_mapping_set_sha256",
            )
        )
        mapping_count = _integer(
            self.native_to_start_symmetry_mapping_count,
            name="native/start symmetry mapping count",
            maximum=MAX_PUBLIC_REFERENCE_SYMMETRY_PERMUTATIONS,
        )
        poses = tuple(self.pose_results)
        if (
            any(not isinstance(row, PoseBustersInternalRMSDPose) for row in poses)
            or tuple(row.rank for row in poses)
            != tuple(range(1, len(poses) + 1))
            or len({row.candidate_id for row in poses}) != len(poses)
            or any(row.symmetry_mapping_count != mapping_count for row in poses)
        ):
            raise PoseBustersInternalRMSDEvaluationError(
                "internal RMSD pose rows are not canonical"
            )
        error = _text(
            self.error_code,
            name="RMSD evaluation error",
            allow_empty=status != "evaluation_failure",
        )
        private_digest = _digest(
            self.private_error_sha256,
            name="private RMSD evaluation error",
            allow_empty=True,
        )
        private_size = _integer(
            self.private_error_byte_length,
            name="private RMSD evaluation error size",
            maximum=16_384,
        )
        if status == "evaluated":
            valid = (
                execution_status == "success"
                and self.evaluation_attempted
                and all(source_digests)
                and mapping_count > 0
                and not error
                and not private_digest
                and private_size == 0
            )
        elif status == "evaluation_failure":
            valid = (
                execution_status == "success"
                and self.evaluation_attempted
                and not any(source_digests)
                and mapping_count == 0
                and not poses
                and error == "internal_rmsd_evaluation_failed"
                and bool(private_digest and private_size)
            )
        else:
            valid = (
                execution_status != "success"
                and not self.evaluation_attempted
                and not any(source_digests)
                and mapping_count == 0
                and not poses
                and not error
                and not private_digest
                and private_size == 0
            )
        if not valid:
            raise PoseBustersInternalRMSDEvaluationError(
                "internal RMSD case fields disagree with status"
            )
        object.__setattr__(self, "case_id", case)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "disposition_code", disposition)
        object.__setattr__(self, "execution_status", execution_status)
        object.__setattr__(
            self,
            "execution_disposition_code",
            execution_disposition,
        )
        object.__setattr__(self, "execution_error_code", execution_error)
        for name, value in zip(
            (
                "native_ligand_source_sha256",
                "start_ligand_source_sha256",
                "prepared_ligand_artifact_sha256",
                "prepared_ligand_system_sha256",
                "diagnostic_report_receipt_sha256",
                "native_to_prepared_mapping_set_sha256",
            ),
            source_digests,
            strict=True,
        ):
            object.__setattr__(self, name, value)
        object.__setattr__(
            self,
            "native_to_start_symmetry_mapping_count",
            mapping_count,
        )
        object.__setattr__(self, "pose_results", poses)
        object.__setattr__(self, "error_code", error)
        object.__setattr__(self, "private_error_sha256", private_digest)
        object.__setattr__(self, "private_error_byte_length", private_size)

    def top_rmsd_hit(self, *, top_k: int, threshold_angstrom: float) -> bool:
        return any(
            row.direct_rmsd_angstrom <= threshold_angstrom
            for row in self.pose_results[:top_k]
        )

    def top_valid_rmsd_hit(
        self,
        *,
        top_k: int,
        threshold_angstrom: float,
    ) -> bool:
        return any(
            row.internal_pose_valid
            and row.direct_rmsd_angstrom <= threshold_angstrom
            for row in self.pose_results[:top_k]
        )

    def best_rmsd_hex(self, *, top_k: int) -> str:
        values = [
            row.direct_rmsd_angstrom for row in self.pose_results[:top_k]
        ]
        return "" if not values else min(values).hex()

    def to_dict(
        self,
        *,
        threshold_angstrom: float,
        top_k: int,
    ) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "case_id": self.case_id,
            "status": self.status,
            "disposition_code": self.disposition_code,
            "execution_status": self.execution_status,
            "execution_disposition_code": self.execution_disposition_code,
            "execution_error_code": self.execution_error_code,
            "evaluation_attempted": self.evaluation_attempted,
            "native_ligand_source_sha256": self.native_ligand_source_sha256,
            "start_ligand_source_sha256": self.start_ligand_source_sha256,
            "prepared_ligand_artifact_sha256": (
                self.prepared_ligand_artifact_sha256
            ),
            "prepared_ligand_system_sha256": (
                self.prepared_ligand_system_sha256
            ),
            "diagnostic_report_receipt_sha256": (
                self.diagnostic_report_receipt_sha256
            ),
            "native_to_start_symmetry_mapping_count": (
                self.native_to_start_symmetry_mapping_count
            ),
            "native_to_prepared_mapping_set_sha256": (
                self.native_to_prepared_mapping_set_sha256
            ),
            "evaluated_pose_count": len(self.pose_results),
            "pose_results": [
                row.to_dict(threshold_angstrom=threshold_angstrom)
                for row in self.pose_results
            ],
            "top_1_rmsd_within_threshold": self.top_rmsd_hit(
                top_k=1,
                threshold_angstrom=threshold_angstrom,
            ),
            "top_k_rmsd_within_threshold": self.top_rmsd_hit(
                top_k=top_k,
                threshold_angstrom=threshold_angstrom,
            ),
            "top_1_valid_and_rmsd_within_threshold": (
                self.top_valid_rmsd_hit(
                    top_k=1,
                    threshold_angstrom=threshold_angstrom,
                )
            ),
            "top_k_valid_and_rmsd_within_threshold": (
                self.top_valid_rmsd_hit(
                    top_k=top_k,
                    threshold_angstrom=threshold_angstrom,
                )
            ),
            "top_1_direct_rmsd_angstrom_binary64_hex": (
                self.best_rmsd_hex(top_k=1)
            ),
            "top_k_best_direct_rmsd_angstrom_binary64_hex": (
                self.best_rmsd_hex(top_k=top_k)
            ),
            "error_code": self.error_code,
            "public_error_message": (
                "internal RMSD evaluation failed"
                if self.status == "evaluation_failure"
                else ""
            ),
            "private_error_sha256": self.private_error_sha256,
            "private_error_byte_length": self.private_error_byte_length,
        }


@dataclass(frozen=True, slots=True)
class PoseBustersInternalRMSDMetric:
    metric_id: str
    numerator: int
    denominator: int
    schema_id: str = POSEBUSTERS_INTERNAL_RMSD_METRIC_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_INTERNAL_RMSD_METRIC_SCHEMA_ID:
            raise PoseBustersInternalRMSDEvaluationError(
                "unsupported internal RMSD metric schema"
            )
        metric = _text(self.metric_id, name="metric ID")
        numerator = _integer(self.numerator, name="metric numerator")
        denominator = _integer(
            self.denominator,
            name="metric denominator",
            minimum=1,
        )
        if numerator > denominator:
            raise PoseBustersInternalRMSDEvaluationError(
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
    rows: Sequence[PoseBustersInternalRMSDCase],
    configuration: PoseBustersInternalRMSDConfig,
) -> tuple[PoseBustersInternalRMSDMetric, ...]:
    denominator = len(rows)
    threshold = configuration.rmsd_threshold_angstrom
    top_k = configuration.top_k
    predicates = (
        ("internal_execution_completion_rate", lambda row: row.execution_status == "success"),
        ("direct_rmsd_evaluation_rate", lambda row: bool(row.pose_results)),
        ("direct_rmsd_evaluation_failure_rate", lambda row: row.status == "evaluation_failure"),
        ("top_1_rmsd_within_threshold_rate", lambda row: row.top_rmsd_hit(top_k=1, threshold_angstrom=threshold)),
        ("top_k_rmsd_within_threshold_rate", lambda row: row.top_rmsd_hit(top_k=top_k, threshold_angstrom=threshold)),
        ("top_1_valid_and_rmsd_within_threshold_rate", lambda row: row.top_valid_rmsd_hit(top_k=1, threshold_angstrom=threshold)),
        ("top_k_valid_and_rmsd_within_threshold_rate", lambda row: row.top_valid_rmsd_hit(top_k=top_k, threshold_angstrom=threshold)),
    )
    return tuple(
        PoseBustersInternalRMSDMetric(
            metric_id=metric_id,
            numerator=sum(bool(predicate(row)) for row in rows),
            denominator=denominator,
        )
        for metric_id, predicate in predicates
    )


@dataclass(frozen=True, slots=True)
class PoseBustersInternalRMSDEvaluationReceipt:
    execution_receipt_sha256: str
    execution_receipt_file_sha256: str
    execution_artifact_set_sha256: str
    execution_runtime_identity_sha256: str
    execution_configuration_sha256: str
    archive_intake_receipt_sha256: str
    archive_contract_sha256: str
    configuration: PoseBustersInternalRMSDConfig
    implementation_source_sha256: str
    implementation_source_members: tuple[tuple[str, str], ...]
    case_rows: tuple[PoseBustersInternalRMSDCase, ...]
    metrics: tuple[PoseBustersInternalRMSDMetric, ...]
    schema_id: str = POSEBUSTERS_INTERNAL_RMSD_EVALUATION_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_INTERNAL_RMSD_EVALUATION_SCHEMA_ID:
            raise PoseBustersInternalRMSDEvaluationError(
                "unsupported internal RMSD evaluation schema"
            )
        if not isinstance(self.configuration, PoseBustersInternalRMSDConfig):
            raise TypeError("configuration has the wrong type")
        for name in (
            "execution_receipt_sha256",
            "execution_receipt_file_sha256",
            "execution_artifact_set_sha256",
            "execution_runtime_identity_sha256",
            "execution_configuration_sha256",
            "archive_intake_receipt_sha256",
            "archive_contract_sha256",
            "implementation_source_sha256",
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
            raise PoseBustersInternalRMSDEvaluationError(
                "implementation source identity is inconsistent"
            )
        rows = tuple(self.case_rows)
        if (
            not rows
            or any(
                not isinstance(row, PoseBustersInternalRMSDCase)
                for row in rows
            )
            or tuple(row.case_id for row in rows)
            != tuple(sorted(row.case_id for row in rows))
            or len({row.case_id for row in rows}) != len(rows)
        ):
            raise PoseBustersInternalRMSDEvaluationError(
                "internal RMSD rows must be canonical unique cases"
            )
        if any(
            not isinstance(row, PoseBustersInternalRMSDMetric)
            for row in self.metrics
        ):
            raise PoseBustersInternalRMSDEvaluationError(
                "internal RMSD metrics have the wrong type"
            )
        expected = _summary_metrics(rows, self.configuration)
        if tuple(row.to_dict() for row in self.metrics) != tuple(
            row.to_dict() for row in expected
        ):
            raise PoseBustersInternalRMSDEvaluationError(
                "internal RMSD metrics disagree with rows"
            )
        object.__setattr__(self, "implementation_source_members", members)
        object.__setattr__(self, "case_rows", rows)
        object.__setattr__(self, "metrics", expected)

    @property
    def evaluated_case_count(self) -> int:
        return sum(row.status == "evaluated" for row in self.case_rows)

    @property
    def evaluated_pose_count(self) -> int:
        return sum(len(row.pose_results) for row in self.case_rows)

    def _payload(self) -> dict[str, object]:
        threshold = self.configuration.rmsd_threshold_angstrom
        top_k = self.configuration.top_k
        return {
            "schema_id": self.schema_id,
            "execution_receipt_sha256": self.execution_receipt_sha256,
            "execution_receipt_file_sha256": self.execution_receipt_file_sha256,
            "execution_artifact_set_sha256": self.execution_artifact_set_sha256,
            "execution_runtime_identity_sha256": (
                self.execution_runtime_identity_sha256
            ),
            "execution_configuration_sha256": (
                self.execution_configuration_sha256
            ),
            "archive_intake_receipt_sha256": self.archive_intake_receipt_sha256,
            "archive_contract_sha256": self.archive_contract_sha256,
            "configuration": self.configuration.to_dict(),
            "configuration_sha256": self.configuration.fingerprint_sha256,
            "implementation_source_sha256": self.implementation_source_sha256,
            "implementation_source_members": dict(
                self.implementation_source_members
            ),
            "all_case_denominator": len(self.case_rows),
            "evaluated_case_count": self.evaluated_case_count,
            "evaluated_pose_count": self.evaluated_pose_count,
            "case_rows": [
                row.to_dict(
                    threshold_angstrom=threshold,
                    top_k=top_k,
                )
                for row in self.case_rows
            ],
            "metrics": [row.to_dict() for row in self.metrics],
            "all_failure_rows_retained": True,
            "direct_receptor_frame_rmsd_evaluated": (
                self.evaluated_pose_count > 0
            ),
            "connectivity_symmetry_aware_rmsd_evaluated": (
                self.evaluated_pose_count > 0
            ),
            "complete_atom_stereo_symmetry_evaluated": False,
            "posebusters_external_oracle_executed": False,
            "target_family_metrics_present": False,
            "benchmark_executed": False,
            "scientific_blockers": list(POSEBUSTERS_INTERNAL_RMSD_BLOCKERS),
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
        if len(payload) > POSEBUSTERS_INTERNAL_RMSD_MAX_RECEIPT_BYTES:
            raise PoseBustersInternalRMSDEvaluationError(
                "internal RMSD receipt exceeds its byte bound"
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
                raise PoseBustersInternalRMSDEvaluationError(
                    "internal RMSD receipt output already exists"
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


def _source_artifacts(intake_row: Any) -> dict[str, Any]:
    return {artifact.role: artifact for artifact in intake_row.artifacts}


def _read_prepared_ligand(
    execution_row: PoseBustersInternalExecutionCase,
    preparation_artifact_root: Path,
) -> AllAtomSystem:
    if execution_row.artifact is None:
        raise PoseBustersInternalRMSDEvaluationError(
            "successful execution row has no diagnostic artifact"
        )
    source = _read_exact_regular_file(
        preparation_artifact_root
        / PurePosixPath(execution_row.case_id)
        / "ligand.canonical.json",
        maximum_bytes=min(
            POSEBUSTERS_INTERNAL_PREPARATION_MAX_ARTIFACT_BYTES,
            MAX_CANONICAL_SYSTEM_JSON_BYTES,
        ),
    )
    if (
        hashlib.sha256(source).hexdigest()
        != execution_row.artifact.prepared_ligand_artifact_sha256
    ):
        raise PoseBustersInternalRMSDEvaluationError(
            "prepared ligand artifact is cross-wired"
        )
    return all_atom_system_from_canonical_json(source, device="cpu")


def _read_execution_report(
    execution_row: PoseBustersInternalExecutionCase,
    execution_artifact_root: Path,
) -> dict[str, object]:
    if execution_row.artifact is None:
        raise PoseBustersInternalRMSDEvaluationError(
            "successful execution row has no diagnostic artifact"
        )
    source = _read_exact_regular_file(
        execution_artifact_root
        / PurePosixPath(execution_row.artifact.relative_path),
        maximum_bytes=POSEBUSTERS_INTERNAL_EXECUTION_MAX_REPORT_BYTES,
    )
    if (
        len(source) != execution_row.artifact.size_bytes
        or hashlib.sha256(source).hexdigest() != execution_row.artifact.sha256
    ):
        raise PoseBustersInternalRMSDEvaluationError(
            "execution report artifact is cross-wired"
        )
    report = verify_redocking_diagnostic_report(source)
    if (
        report.get("status") != "diagnostic_complete"
        or report.get("receipt_sha256")
        != execution_row.artifact.diagnostic_receipt_sha256
    ):
        raise PoseBustersInternalRMSDEvaluationError(
            "execution report receipt identity is inconsistent"
        )
    return report


def _prepared_index_by_start_heavy_atom(
    prepared: AllAtomSystem,
    start: AllAtomSystem,
) -> dict[int, int]:
    start_heavy = tuple(
        atom.index for atom in start.atoms if atom.atomic_number != 1
    )
    mapping: dict[int, int] = {}
    for atom in prepared.atoms:
        if atom.atomic_number == 1:
            continue
        source_index = atom.metadata.get("source_atom_index")
        if (
            isinstance(source_index, bool)
            or not isinstance(source_index, int)
            or source_index < 0
            or source_index >= start.atom_count
            or start.atoms[source_index].atomic_number != atom.atomic_number
            or source_index in mapping
        ):
            raise PoseBustersInternalRMSDEvaluationError(
                "prepared heavy atom lacks a unique source-start binding"
            )
        mapping[source_index] = atom.index
    if set(mapping) != set(start_heavy):
        raise PoseBustersInternalRMSDEvaluationError(
            "prepared heavy atoms do not cover the start heavy graph"
        )
    return mapping


def _native_to_prepared_mappings(
    native: AllAtomSystem,
    start: AllAtomSystem,
    prepared: AllAtomSystem,
    configuration: PoseBustersInternalRMSDConfig,
) -> tuple[tuple[tuple[int, ...], ...], str]:
    native_heavy = tuple(
        atom.index for atom in native.atoms if atom.atomic_number != 1
    )
    start_heavy = tuple(
        atom.index for atom in start.atoms if atom.atomic_number != 1
    )
    if not native_heavy or len(native_heavy) != len(start_heavy):
        raise PoseBustersInternalRMSDEvaluationError(
            "native and start heavy-atom counts disagree"
        )
    source_graph = _projected_labeled_graph(
        native,
        atom_indices=native_heavy,
        include_directional_stereo=False,
    )
    target_graph = _projected_labeled_graph(
        start,
        atom_indices=start_heavy,
        include_directional_stereo=False,
    )
    mappings = _graph_isomorphisms(
        source_graph,
        target_graph,
        max_mappings=configuration.max_symmetry_permutations,
        max_search_states=configuration.max_graph_search_states,
    )
    if not mappings:
        raise PoseBustersInternalRMSDEvaluationError(
            "native and start heavy connectivity graphs do not match"
        )
    prepared_by_start = _prepared_index_by_start_heavy_atom(prepared, start)
    prepared_mappings = tuple(
        tuple(
            prepared_by_start[start_heavy[target_position]]
            for target_position in mapping
        )
        for mapping in mappings
    )
    if len(set(prepared_mappings)) != len(prepared_mappings):
        raise PoseBustersInternalRMSDEvaluationError(
            "native-to-prepared symmetry mappings are duplicated"
        )
    identity = _canonical_sha256(
        {
            "native_heavy_atom_indices": list(native_heavy),
            "start_heavy_atom_indices": list(start_heavy),
            "native_to_start_heavy_position_mappings": [
                list(row) for row in mappings
            ],
            "native_to_prepared_atom_index_mappings": [
                list(row) for row in prepared_mappings
            ],
        }
    )
    return prepared_mappings, identity


def _pose_coordinates(
    raw_pose: Mapping[str, object],
    *,
    atom_count: int,
) -> tuple[torch.Tensor, str]:
    raw_rows = raw_pose.get("coordinates_angstrom_hex")
    if not isinstance(raw_rows, list) or len(raw_rows) != atom_count:
        raise PoseBustersInternalRMSDEvaluationError(
            "selected pose coordinate rows are incomplete"
        )
    rows: list[list[float]] = []
    canonical_rows: list[list[str]] = []
    for row_index, raw_row in enumerate(raw_rows):
        if not isinstance(raw_row, list) or len(raw_row) != 3:
            raise PoseBustersInternalRMSDEvaluationError(
                "selected pose coordinate row is invalid"
            )
        canonical = [
            _finite_hex(value, name=f"pose coordinate {row_index}")
            for value in raw_row
        ]
        canonical_rows.append(canonical)
        rows.append([float.fromhex(value) for value in canonical])
    return (
        torch.tensor(rows, dtype=torch.float64, device="cpu"),
        _canonical_sha256(canonical_rows),
    )


def _evaluate_pose(
    raw_pose: Mapping[str, object],
    *,
    prepared: AllAtomSystem,
    native_heavy_coordinates: torch.Tensor,
    prepared_mappings: tuple[tuple[int, ...], ...],
) -> PoseBustersInternalRMSDPose:
    coordinates, coordinates_sha256 = _pose_coordinates(
        raw_pose,
        atom_count=prepared.atom_count,
    )
    best: tuple[float, int] | None = None
    for mapping_index, mapping in enumerate(prepared_mappings):
        indices = torch.tensor(mapping, dtype=torch.long, device="cpu")
        candidate = coordinates.index_select(0, indices)
        rmsd = float(
            torch.sqrt(
                (native_heavy_coordinates - candidate)
                .square()
                .sum(dim=1)
                .mean()
            ).item()
        )
        result = (rmsd, mapping_index)
        if best is None or result < best:
            best = result
    if best is None:
        raise PoseBustersInternalRMSDEvaluationError(
            "selected pose had no symmetry mapping"
        )
    validity = raw_pose.get("pose_validity")
    if not isinstance(validity, Mapping) or not isinstance(
        validity.get("valid"),
        bool,
    ):
        raise PoseBustersInternalRMSDEvaluationError(
            "selected pose validity receipt is missing"
        )
    return PoseBustersInternalRMSDPose(
        rank=_integer(raw_pose.get("rank"), name="selected pose rank", minimum=1),
        candidate_id=_text(raw_pose.get("candidate_id"), name="candidate ID"),
        proposal_fingerprint_sha256=_digest(
            raw_pose.get("proposal_fingerprint_sha256"),
            name="proposal fingerprint",
        ),
        pose_system_sha256=_digest(
            raw_pose.get("pose_system_sha256"),
            name="pose system SHA-256",
        ),
        coordinates_sha256=coordinates_sha256,
        internal_pose_valid=bool(validity["valid"]),
        direct_rmsd_angstrom_binary64_hex=best[0].hex(),
        symmetry_mapping_index=best[1],
        symmetry_mapping_count=len(prepared_mappings),
    )


def _blocked_case(
    execution_row: PoseBustersInternalExecutionCase,
) -> PoseBustersInternalRMSDCase:
    return PoseBustersInternalRMSDCase(
        case_id=execution_row.case_id,
        status="blocked_execution",
        disposition_code="blocked_by_internal_execution_disposition",
        execution_status=execution_row.status,
        execution_disposition_code=execution_row.disposition_code,
        execution_error_code=execution_row.error_code,
    )


def _evaluate_case(
    archive: zipfile.ZipFile,
    intake_row: Any,
    execution_row: PoseBustersInternalExecutionCase,
    preparation_artifact_root: Path,
    execution_artifact_root: Path,
    configuration: PoseBustersInternalRMSDConfig,
) -> PoseBustersInternalRMSDCase:
    if execution_row.status != "success":
        return _blocked_case(execution_row)
    try:
        source_artifacts = _source_artifacts(intake_row)
        native_artifact = source_artifacts["reference_ligand_sdf"]
        start_artifact = source_artifacts["ligand_start_conformer_sdf"]
        native_source = _read_member(
            archive,
            native_artifact.member_path,
            expected_sha256=native_artifact.sha256,
            expected_size=native_artifact.size_bytes,
        )
        start_source = _read_member(
            archive,
            start_artifact.member_path,
            expected_sha256=start_artifact.sha256,
            expected_size=start_artifact.size_bytes,
        )
        native = parse_sdf_v2000(
            native_source,
            source_id=f"{execution_row.case_id}:native_rmsd",
            dtype=torch.float64,
            device="cpu",
        )
        start = parse_sdf_v2000(
            start_source,
            source_id=f"{execution_row.case_id}:start_rmsd",
            dtype=torch.float64,
            device="cpu",
        )
        prepared = _read_prepared_ligand(
            execution_row,
            preparation_artifact_root,
        )
        report = _read_execution_report(
            execution_row,
            execution_artifact_root,
        )
        prepared_mappings, mapping_set_sha256 = (
            _native_to_prepared_mappings(
                native,
                start,
                prepared,
                configuration,
            )
        )
        native_heavy_indices = tuple(
            atom.index for atom in native.atoms if atom.atomic_number != 1
        )
        native_heavy_coordinates = native.coordinates[0].index_select(
            0,
            torch.tensor(native_heavy_indices, dtype=torch.long, device="cpu"),
        )
        raw_top_poses = report.get("top_poses")
        if not isinstance(raw_top_poses, list):
            raise PoseBustersInternalRMSDEvaluationError(
                "execution report top poses are missing"
            )
        pose_results = tuple(
            _evaluate_pose(
                raw_pose,
                prepared=prepared,
                native_heavy_coordinates=native_heavy_coordinates,
                prepared_mappings=prepared_mappings,
            )
            for raw_pose in raw_top_poses
            if isinstance(raw_pose, Mapping)
        )
        if len(pose_results) != len(raw_top_poses):
            raise PoseBustersInternalRMSDEvaluationError(
                "execution report contains a non-object top pose"
            )
        if execution_row.artifact is None:
            raise PoseBustersInternalRMSDEvaluationError(
                "successful execution artifact disappeared"
            )
    except (
        KeyError,
        OSError,
        PoseBustersCorpusAuditError,
        PoseBustersInternalRMSDEvaluationError,
        PublicReferenceMaterializationError,
        SDFParseError,
        TypeError,
        ValueError,
    ) as exc:
        private_sha256, private_size = _normalized_error(exc)
        return PoseBustersInternalRMSDCase(
            case_id=execution_row.case_id,
            status="evaluation_failure",
            disposition_code="internal_rmsd_evaluation_failed",
            execution_status=execution_row.status,
            execution_disposition_code=execution_row.disposition_code,
            execution_error_code=execution_row.error_code,
            evaluation_attempted=True,
            error_code="internal_rmsd_evaluation_failed",
            private_error_sha256=private_sha256,
            private_error_byte_length=private_size,
        )
    return PoseBustersInternalRMSDCase(
        case_id=execution_row.case_id,
        status="evaluated",
        disposition_code="connectivity_symmetry_direct_rmsd_evaluated",
        execution_status=execution_row.status,
        execution_disposition_code=execution_row.disposition_code,
        execution_error_code=execution_row.error_code,
        evaluation_attempted=True,
        native_ligand_source_sha256=native_artifact.sha256,
        start_ligand_source_sha256=start_artifact.sha256,
        prepared_ligand_artifact_sha256=(
            execution_row.artifact.prepared_ligand_artifact_sha256
        ),
        prepared_ligand_system_sha256=canonical_system_sha256(prepared),
        diagnostic_report_receipt_sha256=(
            execution_row.artifact.diagnostic_receipt_sha256
        ),
        native_to_start_symmetry_mapping_count=len(prepared_mappings),
        native_to_prepared_mapping_set_sha256=mapping_set_sha256,
        pose_results=pose_results,
    )


def _implementation_source_members(
    execution: PoseBustersInternalExecutionReceipt,
) -> tuple[tuple[str, str], ...]:
    members = dict(execution.implementation_source_members)
    root = Path(__file__).parents[1]
    members.update(
        {
            "internal_rmsd_evaluation": _source_file_sha256(__file__),
            "public_ligand_graph_audit": _source_file_sha256(
                root / "benchmark" / "public_ligand_graph_audit.py"
            ),
            "public_reference_graph_search": _source_file_sha256(
                root / "benchmark" / "public_materialization.py"
            ),
        }
    )
    return tuple(sorted(members.items()))


def _build_evaluation(
    execution_receipt_path: str | os.PathLike[str],
    execution_artifact_root: str | os.PathLike[str],
    preparation_receipt_path: str | os.PathLike[str],
    preparation_artifact_root: str | os.PathLike[str],
    archive_path: str | os.PathLike[str],
    selection_path: str | os.PathLike[str],
    intake_receipt_path: str | os.PathLike[str],
    corpus_audit_receipt_path: str | os.PathLike[str],
    *,
    contract: PoseBustersArchiveContract,
    preparation_configuration: PoseBustersInternalPreparationConfig | None,
    execution_configuration: PoseBustersInternalExecutionConfig,
    configuration: PoseBustersInternalRMSDConfig,
) -> PoseBustersInternalRMSDEvaluationReceipt:
    try:
        execution = verify_posebusters_internal_execution_receipt(
            execution_receipt_path,
            execution_artifact_root,
            preparation_receipt_path,
            preparation_artifact_root,
            archive_path,
            selection_path,
            intake_receipt_path,
            corpus_audit_receipt_path,
            contract=contract,
            preparation_configuration=preparation_configuration,
            configuration=execution_configuration,
        )
        intake = verify_posebusters_archive_intake_receipt(
            intake_receipt_path,
            archive_path,
            selection_path,
            contract=contract,
        )
    except (
        PoseBustersArchiveIntakeError,
        PoseBustersInternalExecutionError,
    ) as exc:
        raise PoseBustersInternalRMSDEvaluationError(
            "internal RMSD evaluation requires exact execution and intake receipts"
        ) from exc
    execution_source = _read_exact_regular_file(
        execution_receipt_path,
        maximum_bytes=POSEBUSTERS_INTERNAL_EXECUTION_MAX_RECEIPT_BYTES,
    )
    if execution_source != _canonical_bytes(execution.to_dict()) + b"\n":
        raise PoseBustersInternalRMSDEvaluationError(
            "execution receipt changed after exact verification"
        )
    intake_source = _read_exact_regular_file(
        intake_receipt_path,
        maximum_bytes=POSEBUSTERS_ARCHIVE_MAX_RECEIPT_BYTES,
    )
    if intake_source != _canonical_bytes(intake.to_dict()) + b"\n":
        raise PoseBustersInternalRMSDEvaluationError(
            "intake receipt changed after exact verification"
        )
    if tuple(row.case_id for row in execution.case_rows) != tuple(
        row.case_id for row in intake.case_rows
    ):
        raise PoseBustersInternalRMSDEvaluationError(
            "execution and intake case identities disagree"
        )
    descriptor, size = _regular_file_descriptor(
        archive_path,
        maximum_bytes=contract.archive_size_bytes,
    )
    try:
        if (
            size != contract.archive_size_bytes
            or _hash_descriptor(descriptor, size) != contract.archive_sha256
        ):
            raise PoseBustersInternalRMSDEvaluationError(
                "PoseBusters archive changed after receipt verification"
            )
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            try:
                with zipfile.ZipFile(handle, "r") as archive:
                    rows = tuple(
                        _evaluate_case(
                            archive,
                            intake_row,
                            execution_row,
                            Path(preparation_artifact_root),
                            Path(execution_artifact_root),
                            configuration,
                        )
                        for intake_row, execution_row in zip(
                            intake.case_rows,
                            execution.case_rows,
                            strict=True,
                        )
                    )
            except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
                raise PoseBustersInternalRMSDEvaluationError(
                    "internal RMSD evaluation failed bounded ZIP access"
                ) from exc
    finally:
        os.close(descriptor)
    members = _implementation_source_members(execution)
    return PoseBustersInternalRMSDEvaluationReceipt(
        execution_receipt_sha256=execution.fingerprint_sha256,
        execution_receipt_file_sha256=hashlib.sha256(
            execution_source
        ).hexdigest(),
        execution_artifact_set_sha256=execution.artifact_set_sha256,
        execution_runtime_identity_sha256=(
            execution.runtime_identity.fingerprint_sha256
        ),
        execution_configuration_sha256=(
            execution.configuration.fingerprint_sha256
        ),
        archive_intake_receipt_sha256=intake.fingerprint_sha256,
        archive_contract_sha256=contract.fingerprint_sha256,
        configuration=configuration,
        implementation_source_sha256=_canonical_sha256(dict(members)),
        implementation_source_members=members,
        case_rows=rows,
        metrics=_summary_metrics(rows, configuration),
    )


def materialize_posebusters_internal_rmsd_evaluation(
    execution_receipt_path: str | os.PathLike[str],
    execution_artifact_root: str | os.PathLike[str],
    preparation_receipt_path: str | os.PathLike[str],
    preparation_artifact_root: str | os.PathLike[str],
    archive_path: str | os.PathLike[str],
    selection_path: str | os.PathLike[str],
    intake_receipt_path: str | os.PathLike[str],
    corpus_audit_receipt_path: str | os.PathLike[str],
    *,
    contract: PoseBustersArchiveContract = OFFICIAL_POSEBUSTERS_ARCHIVE_CONTRACT,
    preparation_configuration: PoseBustersInternalPreparationConfig | None = None,
    execution_configuration: PoseBustersInternalExecutionConfig | None = None,
    configuration: PoseBustersInternalRMSDConfig | None = None,
) -> PoseBustersInternalRMSDEvaluationReceipt:
    """Evaluate selected poses while retaining every execution disposition."""

    execution_active = (
        PoseBustersInternalExecutionConfig()
        if execution_configuration is None
        else execution_configuration
    )
    active = PoseBustersInternalRMSDConfig() if configuration is None else configuration
    if not isinstance(execution_active, PoseBustersInternalExecutionConfig):
        raise TypeError("execution_configuration has the wrong type")
    if not isinstance(active, PoseBustersInternalRMSDConfig):
        raise TypeError("configuration has the wrong type")
    return _build_evaluation(
        execution_receipt_path,
        execution_artifact_root,
        preparation_receipt_path,
        preparation_artifact_root,
        archive_path,
        selection_path,
        intake_receipt_path,
        corpus_audit_receipt_path,
        contract=contract,
        preparation_configuration=preparation_configuration,
        execution_configuration=execution_active,
        configuration=active,
    )


def verify_posebusters_internal_rmsd_evaluation_receipt(
    evaluation_receipt_path: str | os.PathLike[str],
    execution_receipt_path: str | os.PathLike[str],
    execution_artifact_root: str | os.PathLike[str],
    preparation_receipt_path: str | os.PathLike[str],
    preparation_artifact_root: str | os.PathLike[str],
    archive_path: str | os.PathLike[str],
    selection_path: str | os.PathLike[str],
    intake_receipt_path: str | os.PathLike[str],
    corpus_audit_receipt_path: str | os.PathLike[str],
    *,
    contract: PoseBustersArchiveContract = OFFICIAL_POSEBUSTERS_ARCHIVE_CONTRACT,
    preparation_configuration: PoseBustersInternalPreparationConfig | None = None,
    execution_configuration: PoseBustersInternalExecutionConfig | None = None,
    configuration: PoseBustersInternalRMSDConfig | None = None,
) -> PoseBustersInternalRMSDEvaluationReceipt:
    """Reexecute and exactly verify one internal RMSD evaluation receipt."""

    execution_active = (
        PoseBustersInternalExecutionConfig()
        if execution_configuration is None
        else execution_configuration
    )
    active = PoseBustersInternalRMSDConfig() if configuration is None else configuration
    if not isinstance(execution_active, PoseBustersInternalExecutionConfig):
        raise TypeError("execution_configuration has the wrong type")
    if not isinstance(active, PoseBustersInternalRMSDConfig):
        raise TypeError("configuration has the wrong type")
    source = _read_exact_regular_file(
        evaluation_receipt_path,
        maximum_bytes=POSEBUSTERS_INTERNAL_RMSD_MAX_RECEIPT_BYTES,
    )
    try:
        raw = json.loads(
            source.decode("ascii"),
            object_pairs_hook=_json_object_pairs,
            parse_constant=_reject_json_constant,
        )
    except PoseBustersInternalRMSDEvaluationError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PoseBustersInternalRMSDEvaluationError(
            "internal RMSD receipt must be ASCII JSON"
        ) from exc
    if (
        not isinstance(raw, dict)
        or raw.get("schema_id")
        != POSEBUSTERS_INTERNAL_RMSD_EVALUATION_SCHEMA_ID
        or source != _canonical_bytes(raw) + b"\n"
        or raw.get("receipt_sha256")
        != _canonical_sha256(
            {key: value for key, value in raw.items() if key != "receipt_sha256"}
        )
    ):
        raise PoseBustersInternalRMSDEvaluationError(
            "internal RMSD receipt is not canonical or self-authenticating"
        )
    expected = _build_evaluation(
        execution_receipt_path,
        execution_artifact_root,
        preparation_receipt_path,
        preparation_artifact_root,
        archive_path,
        selection_path,
        intake_receipt_path,
        corpus_audit_receipt_path,
        contract=contract,
        preparation_configuration=preparation_configuration,
        execution_configuration=execution_active,
        configuration=active,
    )
    if source != _canonical_bytes(expected.to_dict()) + b"\n":
        raise PoseBustersInternalRMSDEvaluationError(
            "internal RMSD receipt failed exact source-tree reexecution"
        )
    return expected


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="betelgeuze-engine-v2-posebusters-internal-rmsd",
        description=(
            "Evaluate failure-inclusive connectivity-symmetry direct RMSD."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("materialize", "verify"):
        command = subparsers.add_parser(name)
        command.add_argument("--execution-receipt", required=True)
        command.add_argument("--execution-artifact-root", required=True)
        command.add_argument("--preparation-receipt", required=True)
        command.add_argument("--preparation-artifact-root", required=True)
        command.add_argument("--archive", required=True)
        command.add_argument("--selection", required=True)
        command.add_argument("--intake-receipt", required=True)
        command.add_argument("--corpus-audit-receipt", required=True)
        command.add_argument("--receipt", required=True)
        command.add_argument("--candidate-count", type=int, default=64)
        command.add_argument("--search-top-k", type=int, default=10)
        command.add_argument("--max-torsions", type=int, default=32)
        command.add_argument("--translation-radius", type=float, default=4.0)
        command.add_argument("--diversity-rmsd", type=float, default=0.5)
        command.add_argument("--max-refinement-steps", type=int, default=6)
        command.add_argument("--base-seed", type=int, default=7_301)
        command.add_argument("--rmsd-threshold", type=float, default=2.0)
        command.add_argument("--evaluation-top-k", type=int, default=5)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    execution_configuration = PoseBustersInternalExecutionConfig(
        candidate_count=args.candidate_count,
        top_k=args.search_top_k,
        max_torsions=args.max_torsions,
        translation_radius_angstrom=args.translation_radius,
        diversity_rmsd_angstrom=args.diversity_rmsd,
        max_refinement_steps=args.max_refinement_steps,
        base_seed=args.base_seed,
    )
    configuration = PoseBustersInternalRMSDConfig(
        rmsd_threshold_angstrom=args.rmsd_threshold,
        top_k=args.evaluation_top_k,
    )
    common = {
        "execution_receipt_path": args.execution_receipt,
        "execution_artifact_root": args.execution_artifact_root,
        "preparation_receipt_path": args.preparation_receipt,
        "preparation_artifact_root": args.preparation_artifact_root,
        "archive_path": args.archive,
        "selection_path": args.selection,
        "intake_receipt_path": args.intake_receipt,
        "corpus_audit_receipt_path": args.corpus_audit_receipt,
        "execution_configuration": execution_configuration,
        "configuration": configuration,
    }
    if args.command == "materialize":
        if Path(args.receipt).exists():
            raise PoseBustersInternalRMSDEvaluationError(
                "internal RMSD receipt output already exists"
            )
        receipt = materialize_posebusters_internal_rmsd_evaluation(**common)
        receipt.write_json(args.receipt)
    else:
        receipt = verify_posebusters_internal_rmsd_evaluation_receipt(
            **common,
            evaluation_receipt_path=args.receipt,
        )
    print(
        json.dumps(
            {
                "receipt_sha256": receipt.fingerprint_sha256,
                "all_case_denominator": len(receipt.case_rows),
                "evaluated_case_count": receipt.evaluated_case_count,
                "evaluated_pose_count": receipt.evaluated_pose_count,
                "posebusters_external_oracle_executed": False,
                "benchmark_executed": False,
                "claim_safe": False,
            },
            sort_keys=True,
        )
    )
    return 0


__all__ = [
    "POSEBUSTERS_INTERNAL_RMSD_BLOCKERS",
    "POSEBUSTERS_INTERNAL_RMSD_CASE_SCHEMA_ID",
    "POSEBUSTERS_INTERNAL_RMSD_CONFIG_SCHEMA_ID",
    "POSEBUSTERS_INTERNAL_RMSD_EVALUATION_SCHEMA_ID",
    "POSEBUSTERS_INTERNAL_RMSD_MAX_RECEIPT_BYTES",
    "POSEBUSTERS_INTERNAL_RMSD_METRIC_SCHEMA_ID",
    "POSEBUSTERS_INTERNAL_RMSD_POSE_SCHEMA_ID",
    "PoseBustersInternalRMSDCase",
    "PoseBustersInternalRMSDConfig",
    "PoseBustersInternalRMSDEvaluationError",
    "PoseBustersInternalRMSDEvaluationReceipt",
    "PoseBustersInternalRMSDMetric",
    "PoseBustersInternalRMSDPose",
    "main",
    "materialize_posebusters_internal_rmsd_evaluation",
    "verify_posebusters_internal_rmsd_evaluation_receipt",
]


if __name__ == "__main__":
    raise SystemExit(main())
