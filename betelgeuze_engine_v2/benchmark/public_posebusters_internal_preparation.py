"""Failure-inclusive canonical preparation for internal PoseBusters redocking.

The exact PoseBusters intake and corpus-audit receipts are reverified before any
case is touched.  Eligible cases produce strict canonical receptor JSON and an
RDKit/OpenFF-preparation-bound canonical ligand JSON.  Every corpus row remains
in the denominator; this module does not dock, score, evaluate a native pose, or
make a benchmark claim.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path, PurePosixPath
import platform
import re
import tempfile
from typing import Any, Protocol, Sequence
import zipfile

import torch

from betelgeuze_engine_v2 import DISTRIBUTION_VERSION
from betelgeuze_engine_v2.io import PDBParseError, SDFParseError, parse_pdb, parse_sdf_v2000
from betelgeuze_engine_v2.molecular import (
    AllAtomSystem,
    RdkitOpenffPreparationConfig,
    RdkitOpenffPreparationError,
    canonical_system_json_bytes,
    canonical_system_sha256,
    prepare_ligand_with_rdkit_openff,
    verify_rdkit_openff_prepared_system,
)

from .public_posebusters_corpus_audit import (
    PoseBustersCorpusAuditError,
    PoseBustersCorpusAuditReceipt,
    _canonical_bytes,
    _canonical_sha256,
    _read_member,
    _source_file_sha256,
    verify_posebusters_corpus_audit_receipt,
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
    PoseBustersArchiveIntakeError,
    _hash_descriptor,
    _read_exact_regular_file,
    _regular_file_descriptor,
    verify_posebusters_archive_intake_receipt,
)


POSEBUSTERS_INTERNAL_PREPARATION_CONFIG_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_internal_preparation_config/1.0.0"
)
POSEBUSTERS_INTERNAL_PREPARATION_RUNTIME_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_internal_preparation_runtime/1.0.0"
)
POSEBUSTERS_INTERNAL_PREPARATION_ARTIFACT_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_internal_preparation_artifact/1.0.0"
)
POSEBUSTERS_INTERNAL_PREPARATION_CASE_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_internal_preparation_case/1.0.0"
)
POSEBUSTERS_INTERNAL_PREPARATION_METRIC_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_internal_preparation_metric/1.0.0"
)
POSEBUSTERS_INTERNAL_PREPARATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_internal_preparation/1.0.0"
)

POSEBUSTERS_INTERNAL_PREPARATION_MAX_RECEIPT_BYTES = 64 * 1024 * 1024
POSEBUSTERS_INTERNAL_PREPARATION_MAX_ARTIFACT_BYTES = (
    POSEBUSTERS_EXTERNAL_PREPARATION_MAX_ARTIFACT_BYTES
)
POSEBUSTERS_INTERNAL_PREPARATION_SCOPE_STATUS = (
    "blocked_parameters_and_partial_charges_missing"
)
POSEBUSTERS_INTERNAL_PREPARATION_BLOCKERS = (
    "canonical_preparation_not_scientifically_validated",
    "receptor_protonation_hydrogen_and_bond_inference_missing",
    "ligand_protonation_tautomer_and_openff_parameterization_not_validated",
    "native_reference_used_only_for_pocket_center",
    "fixed_spherical_pocket_radius_not_benchmark_validated",
    "internal_redocking_batch_execution_missing",
    "target_family_and_chemistry_stratified_result_receipt_missing",
    "runtime_binary_and_dependency_payload_identity_incomplete",
    "independent_external_rerun_missing",
    "scientific_review_missing",
)

_ARTIFACT_ROLES = (
    "canonical_ligand_json",
    "canonical_receptor_json",
)
_CASE_STATUSES = {
    "abstain_chemistry_scope",
    "prepared",
    "preparation_failure",
    "upstream_failure",
}
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class PoseBustersInternalPreparationError(ValueError):
    """Canonical preparation input, artifact, or receipt is invalid."""


def _digest(value: object, *, name: str, allow_empty: bool = False) -> str:
    text = str(value or "").strip().lower()
    if allow_empty and not text:
        return ""
    if _SHA256_RE.fullmatch(text) is None:
        raise PoseBustersInternalPreparationError(
            f"{name} must be a lowercase SHA-256"
        )
    return text


def _text(value: object, *, name: str, allow_empty: bool = False) -> str:
    text = str(value or "").strip()
    if (not text and not allow_empty) or len(text) > 512 or "\x00" in text:
        raise PoseBustersInternalPreparationError(f"{name} is outside its text bound")
    return text


def _positive_int(
    value: object,
    *,
    name: str,
    allow_zero: bool = False,
    maximum: int = 2**63 - 1,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise PoseBustersInternalPreparationError(f"{name} must be an integer")
    minimum = 0 if allow_zero else 1
    if not minimum <= value <= maximum:
        raise PoseBustersInternalPreparationError(
            f"{name} must be in [{minimum}, {maximum}]"
        )
    return value


def _finite_hex(value: object, *, name: str, positive: bool = False) -> str:
    if not isinstance(value, str):
        raise PoseBustersInternalPreparationError(
            f"{name} must be canonical finite binary64"
        )
    try:
        number = float.fromhex(value)
    except ValueError as exc:
        raise PoseBustersInternalPreparationError(
            f"{name} must be canonical finite binary64"
        ) from exc
    if not math.isfinite(number) or number.hex() != value or (positive and number <= 0.0):
        raise PoseBustersInternalPreparationError(
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
            raise PoseBustersInternalPreparationError(
                f"duplicate JSON key: {key}"
            )
        result[key] = value
    return result


def _reject_json_constant(value: str) -> object:
    raise PoseBustersInternalPreparationError(
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
class PoseBustersInternalPreparationConfig:
    pocket_radius_angstrom: float = 10.0
    translation_radius_angstrom: float = 4.0
    ligand_preparation: RdkitOpenffPreparationConfig = field(
        default_factory=RdkitOpenffPreparationConfig
    )
    schema_id: str = POSEBUSTERS_INTERNAL_PREPARATION_CONFIG_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_INTERNAL_PREPARATION_CONFIG_SCHEMA_ID:
            raise PoseBustersInternalPreparationError(
                "unsupported internal-preparation config schema"
            )
        pocket = float(self.pocket_radius_angstrom)
        translation = float(self.translation_radius_angstrom)
        if (
            not math.isfinite(pocket)
            or pocket <= 0.0
            or not math.isfinite(translation)
            or translation < 0.0
            or translation > pocket
        ):
            raise PoseBustersInternalPreparationError(
                "internal-preparation pocket/translation radii are invalid"
            )
        if not isinstance(self.ligand_preparation, RdkitOpenffPreparationConfig):
            raise TypeError(
                "ligand_preparation must be RdkitOpenffPreparationConfig"
            )
        object.__setattr__(self, "pocket_radius_angstrom", pocket)
        object.__setattr__(self, "translation_radius_angstrom", translation)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "pocket_radius_angstrom_hex": self.pocket_radius_angstrom.hex(),
            "translation_radius_angstrom_hex": (
                self.translation_radius_angstrom.hex()
            ),
            "pocket_center_policy": (
                "native_reference_heavy_atom_centroid_in_raw_receptor_frame"
            ),
            "receptor_policy": (
                "strict_pdb_single_model_record_cryst1_without_materialization"
            ),
            "ligand_policy": "rdkit_openff_preparation_adapter",
            "ligand_preparation": self.ligand_preparation.to_dict(),
            "ligand_preparation_config_sha256": (
                self.ligand_preparation.fingerprint_sha256
            ),
            "scope_admission_status": POSEBUSTERS_INTERNAL_PREPARATION_SCOPE_STATUS,
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())


@dataclass(frozen=True, slots=True)
class PoseBustersInternalPreparationRuntime:
    python_implementation: str
    python_version: str
    torch_version: str
    rdkit_version: str
    engine_version: str
    schema_id: str = POSEBUSTERS_INTERNAL_PREPARATION_RUNTIME_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_INTERNAL_PREPARATION_RUNTIME_SCHEMA_ID:
            raise PoseBustersInternalPreparationError(
                "unsupported internal-preparation runtime schema"
            )
        for name in (
            "python_implementation",
            "python_version",
            "torch_version",
            "engine_version",
        ):
            object.__setattr__(self, name, _text(getattr(self, name), name=name))
        object.__setattr__(
            self,
            "rdkit_version",
            _text(self.rdkit_version, name="rdkit_version", allow_empty=True),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "python_implementation": self.python_implementation,
            "python_version": self.python_version,
            "torch_version": self.torch_version,
            "rdkit_distribution_version": self.rdkit_version or None,
            "rdkit_available": bool(self.rdkit_version),
            "engine_distribution_version": self.engine_version,
            "cpu_only": True,
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())


@dataclass(frozen=True, slots=True)
class PoseBustersInternalPreparedArtifact:
    role: str
    relative_path: str
    sha256: str
    size_bytes: int
    system_sha256: str
    source_role: str
    source_sha256: str
    ligand_preparation_receipt_sha256: str = ""
    schema_id: str = POSEBUSTERS_INTERNAL_PREPARATION_ARTIFACT_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_INTERNAL_PREPARATION_ARTIFACT_SCHEMA_ID:
            raise PoseBustersInternalPreparationError(
                "unsupported internal-preparation artifact schema"
            )
        role = _text(self.role, name="prepared artifact role")
        if role not in _ARTIFACT_ROLES:
            raise PoseBustersInternalPreparationError(
                "internal-preparation artifact role is invalid"
            )
        relative = _text(self.relative_path, name="prepared artifact path")
        path = PurePosixPath(relative)
        if path.is_absolute() or ".." in path.parts or "\\" in relative:
            raise PoseBustersInternalPreparationError(
                "internal-preparation artifact path is unsafe"
            )
        expected_source_role = {
            "canonical_ligand_json": "ligand_start_conformer_sdf",
            "canonical_receptor_json": "receptor_pdb",
        }[role]
        receipt = _digest(
            self.ligand_preparation_receipt_sha256,
            name="ligand_preparation_receipt_sha256",
            allow_empty=True,
        )
        if self.source_role != expected_source_role or bool(receipt) != (
            role == "canonical_ligand_json"
        ):
            raise PoseBustersInternalPreparationError(
                "prepared artifact source or ligand receipt is inconsistent"
            )
        object.__setattr__(self, "role", role)
        object.__setattr__(self, "relative_path", relative)
        object.__setattr__(self, "sha256", _digest(self.sha256, name="artifact SHA-256"))
        object.__setattr__(
            self,
            "system_sha256",
            _digest(self.system_sha256, name="artifact system SHA-256"),
        )
        object.__setattr__(
            self,
            "source_sha256",
            _digest(self.source_sha256, name="artifact source SHA-256"),
        )
        object.__setattr__(self, "ligand_preparation_receipt_sha256", receipt)
        object.__setattr__(
            self,
            "size_bytes",
            _positive_int(
                self.size_bytes,
                name="prepared artifact size",
                maximum=POSEBUSTERS_INTERNAL_PREPARATION_MAX_ARTIFACT_BYTES,
            ),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "role": self.role,
            "relative_path": self.relative_path,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "system_sha256": self.system_sha256,
            "source_role": self.source_role,
            "source_sha256": self.source_sha256,
            "ligand_preparation_receipt_sha256": (
                self.ligand_preparation_receipt_sha256 or None
            ),
        }


@dataclass(frozen=True, slots=True)
class PoseBustersInternalPreparationCase:
    case_id: str
    status: str
    disposition_code: str
    reference_scorer_scope_status: str
    reference_scorer_scope_blockers: tuple[str, ...]
    preparation_attempted: bool = False
    pocket_center_binary64_hex: tuple[str, ...] = ()
    artifacts: tuple[PoseBustersInternalPreparedArtifact, ...] = ()
    error_code: str = ""
    private_error_sha256: str = ""
    private_error_byte_length: int = 0
    schema_id: str = POSEBUSTERS_INTERNAL_PREPARATION_CASE_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_INTERNAL_PREPARATION_CASE_SCHEMA_ID:
            raise PoseBustersInternalPreparationError(
                "unsupported internal-preparation case schema"
            )
        case_id = _text(self.case_id, name="case ID")
        if case_id.upper() != case_id or len(case_id.split("_")) != 2:
            raise PoseBustersInternalPreparationError(
                "internal-preparation case ID is invalid"
            )
        status = _text(self.status, name="preparation status")
        if status not in _CASE_STATUSES:
            raise PoseBustersInternalPreparationError(
                "internal-preparation case status is invalid"
            )
        disposition = _text(self.disposition_code, name="preparation disposition")
        if not isinstance(self.preparation_attempted, bool):
            raise PoseBustersInternalPreparationError(
                "preparation_attempted must be boolean"
            )
        expected_disposition = {
            "prepared": "canonical_internal_redocking_input_pair",
            "preparation_failure": "internal_canonical_preparation_failed",
            "abstain_chemistry_scope": (
                "reference_scorer_chemistry_scope_abstention"
            ),
            "upstream_failure": "upstream_input_contract_failure",
        }[status]
        if disposition != expected_disposition:
            raise PoseBustersInternalPreparationError(
                "internal-preparation disposition disagrees with status"
            )
        scope_status = _text(
            self.reference_scorer_scope_status,
            name="reference scorer scope status",
            allow_empty=status == "upstream_failure",
        )
        scope_blockers = tuple(
            sorted(
                set(
                    _text(value, name="scope blocker")
                    for value in self.reference_scorer_scope_blockers
                )
            )
        )
        center = tuple(self.pocket_center_binary64_hex)
        if center:
            if len(center) != 3:
                raise PoseBustersInternalPreparationError(
                    "pocket center must contain three values"
                )
            center = tuple(
                _finite_hex(value, name="pocket center") for value in center
            )
        artifacts = tuple(self.artifacts)
        if (
            any(not isinstance(row, PoseBustersInternalPreparedArtifact) for row in artifacts)
            or tuple(row.role for row in artifacts) != tuple(
                sorted(row.role for row in artifacts)
            )
            or len({row.role for row in artifacts}) != len(artifacts)
        ):
            raise PoseBustersInternalPreparationError(
                "prepared artifacts must be canonical unique roles"
            )
        error_code = _text(
            self.error_code,
            name="preparation error code",
            allow_empty=status in {"prepared", "abstain_chemistry_scope"},
        )
        private_digest = _digest(
            self.private_error_sha256,
            name="private_error_sha256",
            allow_empty=True,
        )
        private_size = _positive_int(
            self.private_error_byte_length,
            name="private error byte length",
            allow_zero=True,
            maximum=16_384,
        )
        valid = {
            "prepared": (
                self.preparation_attempted
                and len(center) == 3
                and tuple(row.role for row in artifacts) == _ARTIFACT_ROLES
                and not error_code
                and not private_digest
                and private_size == 0
            ),
            "preparation_failure": (
                self.preparation_attempted
                and len(center) == 3
                and not artifacts
                and error_code == "internal_canonical_preparation_failed"
                and bool(private_digest and private_size)
            ),
            "abstain_chemistry_scope": (
                not self.preparation_attempted
                and not center
                and not artifacts
                and not error_code
                and not private_digest
                and private_size == 0
            ),
            "upstream_failure": (
                not self.preparation_attempted
                and not center
                and not artifacts
                and bool(error_code)
                and not private_digest
                and private_size == 0
            ),
        }[status]
        if not valid:
            raise PoseBustersInternalPreparationError(
                "internal-preparation case fields disagree with status"
            )
        object.__setattr__(self, "case_id", case_id)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "disposition_code", disposition)
        object.__setattr__(self, "reference_scorer_scope_status", scope_status)
        object.__setattr__(self, "reference_scorer_scope_blockers", scope_blockers)
        object.__setattr__(self, "pocket_center_binary64_hex", center)
        object.__setattr__(self, "artifacts", artifacts)
        object.__setattr__(self, "error_code", error_code)
        object.__setattr__(self, "private_error_sha256", private_digest)
        object.__setattr__(self, "private_error_byte_length", private_size)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "case_id": self.case_id,
            "status": self.status,
            "disposition_code": self.disposition_code,
            "reference_scorer_scope_status": self.reference_scorer_scope_status,
            "reference_scorer_scope_blockers": list(
                self.reference_scorer_scope_blockers
            ),
            "preparation_attempted": self.preparation_attempted,
            "pocket_center_binary64_hex": list(self.pocket_center_binary64_hex),
            "artifacts": [row.to_dict() for row in self.artifacts],
            "error_code": self.error_code,
            "public_error_message": (
                "internal canonical preparation failed"
                if self.status == "preparation_failure"
                else ""
            ),
            "private_error_sha256": self.private_error_sha256,
            "private_error_byte_length": self.private_error_byte_length,
        }


@dataclass(frozen=True, slots=True)
class PoseBustersInternalPreparationMetric:
    metric_id: str
    numerator: int
    denominator: int
    schema_id: str = POSEBUSTERS_INTERNAL_PREPARATION_METRIC_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_INTERNAL_PREPARATION_METRIC_SCHEMA_ID:
            raise PoseBustersInternalPreparationError(
                "unsupported internal-preparation metric schema"
            )
        metric_id = _text(self.metric_id, name="metric ID")
        numerator = _positive_int(
            self.numerator,
            name="metric numerator",
            allow_zero=True,
        )
        denominator = _positive_int(self.denominator, name="metric denominator")
        if numerator > denominator:
            raise PoseBustersInternalPreparationError(
                "metric numerator exceeds denominator"
            )
        object.__setattr__(self, "metric_id", metric_id)
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
    rows: Sequence[PoseBustersInternalPreparationCase],
) -> tuple[PoseBustersInternalPreparationMetric, ...]:
    denominator = len(rows)
    predicates = (
        ("scope_admission_rate", lambda row: row.reference_scorer_scope_status == POSEBUSTERS_INTERNAL_PREPARATION_SCOPE_STATUS),
        ("preparation_attempt_rate", lambda row: row.preparation_attempted),
        ("canonical_preparation_success_rate", lambda row: row.status == "prepared"),
        ("preparation_failure_rate", lambda row: row.status == "preparation_failure"),
    )
    return tuple(
        PoseBustersInternalPreparationMetric(
            metric_id=metric_id,
            numerator=sum(bool(predicate(row)) for row in rows),
            denominator=denominator,
        )
        for metric_id, predicate in predicates
    )


def _artifact_set_sha256(
    rows: Sequence[PoseBustersInternalPreparationCase],
) -> str:
    return _canonical_sha256(
        {
            f"{row.case_id}/{artifact.role}": artifact.to_dict()
            for row in rows
            for artifact in row.artifacts
        }
    )


@dataclass(frozen=True, slots=True)
class PoseBustersInternalPreparationReceipt:
    corpus_audit_receipt_sha256: str
    archive_intake_receipt_sha256: str
    archive_contract_sha256: str
    configuration: PoseBustersInternalPreparationConfig
    runtime_identity: PoseBustersInternalPreparationRuntime
    implementation_source_sha256: str
    implementation_source_members: tuple[tuple[str, str], ...]
    case_rows: tuple[PoseBustersInternalPreparationCase, ...]
    metrics: tuple[PoseBustersInternalPreparationMetric, ...]
    artifact_set_sha256: str
    schema_id: str = POSEBUSTERS_INTERNAL_PREPARATION_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_INTERNAL_PREPARATION_SCHEMA_ID:
            raise PoseBustersInternalPreparationError(
                "unsupported internal-preparation receipt schema"
            )
        if not isinstance(self.configuration, PoseBustersInternalPreparationConfig):
            raise TypeError("configuration has the wrong type")
        if not isinstance(self.runtime_identity, PoseBustersInternalPreparationRuntime):
            raise TypeError("runtime_identity has the wrong type")
        for name in (
            "corpus_audit_receipt_sha256",
            "archive_intake_receipt_sha256",
            "archive_contract_sha256",
            "implementation_source_sha256",
            "artifact_set_sha256",
        ):
            object.__setattr__(self, name, _digest(getattr(self, name), name=name))
        source_members = tuple(
            (
                _text(role, name="implementation source role"),
                _digest(digest, name="implementation source digest"),
            )
            for role, digest in self.implementation_source_members
        )
        if (
            tuple(role for role, _digest_value in source_members)
            != tuple(sorted(role for role, _digest_value in source_members))
            or len({role for role, _digest_value in source_members}) != len(source_members)
            or self.implementation_source_sha256
            != _canonical_sha256(dict(source_members))
        ):
            raise PoseBustersInternalPreparationError(
                "implementation source identity is inconsistent"
            )
        rows = tuple(self.case_rows)
        if (
            not rows
            or any(
                not isinstance(row, PoseBustersInternalPreparationCase)
                for row in rows
            )
            or tuple(row.case_id for row in rows)
            != tuple(sorted(row.case_id for row in rows))
            or len({row.case_id for row in rows}) != len(rows)
        ):
            raise PoseBustersInternalPreparationError(
                "internal-preparation rows must be canonical unique cases"
            )
        if any(
            not isinstance(row, PoseBustersInternalPreparationMetric)
            for row in self.metrics
        ):
            raise PoseBustersInternalPreparationError(
                "internal-preparation metrics have the wrong type"
            )
        metrics = _summary_metrics(rows)
        if tuple(row.to_dict() for row in self.metrics) != tuple(
            row.to_dict() for row in metrics
        ):
            raise PoseBustersInternalPreparationError(
                "internal-preparation metrics disagree with rows"
            )
        if self.artifact_set_sha256 != _artifact_set_sha256(rows):
            raise PoseBustersInternalPreparationError(
                "internal-preparation artifact-set identity is inconsistent"
            )
        object.__setattr__(self, "implementation_source_members", source_members)
        object.__setattr__(self, "case_rows", rows)
        object.__setattr__(self, "metrics", metrics)

    @property
    def prepared_case_count(self) -> int:
        return sum(row.status == "prepared" for row in self.case_rows)

    def _payload(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "corpus_audit_receipt_sha256": self.corpus_audit_receipt_sha256,
            "archive_intake_receipt_sha256": self.archive_intake_receipt_sha256,
            "archive_contract_sha256": self.archive_contract_sha256,
            "configuration": self.configuration.to_dict(),
            "configuration_sha256": self.configuration.fingerprint_sha256,
            "runtime_identity": self.runtime_identity.to_dict(),
            "runtime_identity_sha256": self.runtime_identity.fingerprint_sha256,
            "implementation_source_sha256": self.implementation_source_sha256,
            "implementation_source_members": dict(self.implementation_source_members),
            "artifact_set_sha256": self.artifact_set_sha256,
            "all_case_denominator": len(self.case_rows),
            "prepared_case_count": self.prepared_case_count,
            "failed_or_abstained_case_count": (
                len(self.case_rows) - self.prepared_case_count
            ),
            "case_rows": [row.to_dict() for row in self.case_rows],
            "metrics": [row.to_dict() for row in self.metrics],
            "native_reference_used_for_pocket_center_only": True,
            "native_reference_coordinates_used_for_ligand_preparation": False,
            "redocking_executed": False,
            "benchmark_executed": False,
            "scientific_blockers": list(POSEBUSTERS_INTERNAL_PREPARATION_BLOCKERS),
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
                raise PoseBustersInternalPreparationError(
                    "internal-preparation receipt output already exists"
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


class _PreparationRuntime(Protocol):
    identity: PoseBustersInternalPreparationRuntime

    def prepare(
        self,
        receptor_pdb: bytes,
        ligand_start_sdf: bytes,
        *,
        case_id: str,
    ) -> tuple[AllAtomSystem, AllAtomSystem, str]:
        ...


class _LocalPreparationRuntime:
    def __init__(self, config: PoseBustersInternalPreparationConfig) -> None:
        self.config = config
        try:
            rdkit_version = importlib.metadata.version("rdkit")
        except importlib.metadata.PackageNotFoundError:
            rdkit_version = ""
        self.identity = PoseBustersInternalPreparationRuntime(
            python_implementation=platform.python_implementation(),
            python_version=platform.python_version(),
            torch_version=str(torch.__version__),
            rdkit_version=rdkit_version,
            engine_version=DISTRIBUTION_VERSION,
        )

    def prepare(
        self,
        receptor_pdb: bytes,
        ligand_start_sdf: bytes,
        *,
        case_id: str,
    ) -> tuple[AllAtomSystem, AllAtomSystem, str]:
        receptor = parse_pdb(
            receptor_pdb,
            source_id=f"{case_id}:receptor",
            dtype=torch.float64,
            device="cpu",
            crystallographic_cell_policy="record_only",
        )
        ligand = prepare_ligand_with_rdkit_openff(
            ligand_start_sdf,
            source_format="sdf_v2000",
            source_id=f"{case_id}:ligand_start",
            config=self.config.ligand_preparation,
        )
        receipt = verify_rdkit_openff_prepared_system(ligand)
        readiness = receipt.get("readiness")
        if (
            receipt.get("status") != "prepared_diagnostic"
            or not isinstance(readiness, dict)
            or readiness.get("diagnostic_redocking_ready") is not True
        ):
            raise PoseBustersInternalPreparationError(
                "prepared ligand did not satisfy the diagnostic redocking gate"
            )
        receipt_sha256 = _digest(
            receipt.get("receipt_sha256"),
            name="ligand preparation receipt SHA-256",
        )
        source_receipt = receipt.get("source")
        if (
            not isinstance(source_receipt, dict)
            or source_receipt.get("source_sha256")
            != hashlib.sha256(ligand_start_sdf).hexdigest()
        ):
            raise PoseBustersInternalPreparationError(
                "ligand preparation receipt is cross-wired to another source"
            )
        if receptor.cell is not None or ligand.cell is not None:
            raise PoseBustersInternalPreparationError(
                "internal redocking preparation requires nonperiodic systems"
            )
        return receptor, ligand, receipt_sha256


def _load_runtime(
    config: PoseBustersInternalPreparationConfig,
) -> _PreparationRuntime:
    return _LocalPreparationRuntime(config)


def _native_heavy_centroid(
    source: bytes,
    *,
    case_id: str,
) -> tuple[str, str, str]:
    ligand = parse_sdf_v2000(
        source,
        source_id=f"{case_id}:native_pocket_center",
        dtype=torch.float64,
        device="cpu",
    )
    heavy_indices = tuple(
        atom.index for atom in ligand.atoms if atom.atomic_number != 1
    )
    if not heavy_indices or ligand.model_count != 1:
        raise PoseBustersInternalPreparationError(
            "native reference has no bounded heavy-atom coordinate model"
        )
    center = tuple(
        math.fsum(
            float(ligand.coordinates[0, atom_index, axis].item())
            for atom_index in heavy_indices
        )
        / len(heavy_indices)
        for axis in range(3)
    )
    return (center[0].hex(), center[1].hex(), center[2].hex())


def _source_artifacts(intake_row: Any) -> dict[str, Any]:
    return {artifact.role: artifact for artifact in intake_row.artifacts}


def _prepared_artifact(
    *,
    case_id: str,
    role: str,
    source_artifact: Any,
    payload: bytes,
    system: AllAtomSystem,
    ligand_preparation_receipt_sha256: str = "",
) -> PoseBustersInternalPreparedArtifact:
    filename = {
        "canonical_ligand_json": "ligand.canonical.json",
        "canonical_receptor_json": "receptor.canonical.json",
    }[role]
    return PoseBustersInternalPreparedArtifact(
        role=role,
        relative_path=f"{case_id}/{filename}",
        sha256=hashlib.sha256(payload).hexdigest(),
        size_bytes=len(payload),
        system_sha256=canonical_system_sha256(system),
        source_role=source_artifact.role,
        source_sha256=source_artifact.sha256,
        ligand_preparation_receipt_sha256=(
            ligand_preparation_receipt_sha256
        ),
    )


def _upstream_failure_row(
    corpus_row: Any,
    *,
    error_code: str,
) -> PoseBustersInternalPreparationCase:
    return PoseBustersInternalPreparationCase(
        case_id=corpus_row.case_id,
        status="upstream_failure",
        disposition_code="upstream_input_contract_failure",
        reference_scorer_scope_status=corpus_row.reference_scorer_scope_status,
        reference_scorer_scope_blockers=(
            corpus_row.reference_scorer_scope_blockers
        ),
        error_code=error_code,
    )


def _prepare_case(
    archive: zipfile.ZipFile,
    intake_row: Any,
    corpus_row: Any,
    runtime: _PreparationRuntime,
) -> tuple[PoseBustersInternalPreparationCase, dict[str, bytes]]:
    if corpus_row.status != "audited" or intake_row.status != "ready":
        return _upstream_failure_row(
            corpus_row,
            error_code="upstream_intake_or_corpus_case_failed",
        ), {}
    if (
        corpus_row.reference_scorer_scope_status
        != POSEBUSTERS_INTERNAL_PREPARATION_SCOPE_STATUS
    ):
        return PoseBustersInternalPreparationCase(
            case_id=corpus_row.case_id,
            status="abstain_chemistry_scope",
            disposition_code="reference_scorer_chemistry_scope_abstention",
            reference_scorer_scope_status=(
                corpus_row.reference_scorer_scope_status
            ),
            reference_scorer_scope_blockers=(
                corpus_row.reference_scorer_scope_blockers
            ),
        ), {}
    source_artifacts = _source_artifacts(intake_row)
    sources: dict[str, bytes] = {}
    for role in (
        "receptor_pdb",
        "reference_ligand_sdf",
        "ligand_start_conformer_sdf",
    ):
        artifact = source_artifacts.get(role)
        if artifact is None:
            return _upstream_failure_row(
                corpus_row,
                error_code=f"{role}_artifact_identity_missing",
            ), {}
        try:
            sources[role] = _read_member(
                archive,
                artifact.member_path,
                expected_sha256=artifact.sha256,
                expected_size=artifact.size_bytes,
            )
        except PoseBustersCorpusAuditError:
            return _upstream_failure_row(
                corpus_row,
                error_code=f"{role}_artifact_identity_verification_failed",
            ), {}
    try:
        center = _native_heavy_centroid(
            sources["reference_ligand_sdf"],
            case_id=corpus_row.case_id,
        )
    except (PoseBustersInternalPreparationError, SDFParseError):
        return _upstream_failure_row(
            corpus_row,
            error_code="native_reference_pocket_center_failed",
        ), {}
    try:
        receptor, ligand, ligand_receipt_sha256 = runtime.prepare(
            sources["receptor_pdb"],
            sources["ligand_start_conformer_sdf"],
            case_id=corpus_row.case_id,
        )
        ligand_receipt = verify_rdkit_openff_prepared_system(ligand)
        ligand_source_receipt = ligand_receipt.get("source")
        if (
            ligand_receipt.get("receipt_sha256") != ligand_receipt_sha256
            or not isinstance(ligand_source_receipt, dict)
            or ligand_source_receipt.get("source_sha256")
            != source_artifacts["ligand_start_conformer_sdf"].sha256
            or receptor.provenance.source_sha256
            != source_artifacts["receptor_pdb"].sha256
        ):
            raise PoseBustersInternalPreparationError(
                "canonical preparation runtime returned cross-wired systems"
            )
        receptor_payload = canonical_system_json_bytes(receptor)
        ligand_payload = canonical_system_json_bytes(ligand)
    except (
        OSError,
        PDBParseError,
        RdkitOpenffPreparationError,
        PoseBustersInternalPreparationError,
        TypeError,
        ValueError,
    ) as exc:
        private_sha256, private_size = _normalized_error(exc)
        return PoseBustersInternalPreparationCase(
            case_id=corpus_row.case_id,
            status="preparation_failure",
            disposition_code="internal_canonical_preparation_failed",
            reference_scorer_scope_status=(
                corpus_row.reference_scorer_scope_status
            ),
            reference_scorer_scope_blockers=(
                corpus_row.reference_scorer_scope_blockers
            ),
            preparation_attempted=True,
            pocket_center_binary64_hex=center,
            error_code="internal_canonical_preparation_failed",
            private_error_sha256=private_sha256,
            private_error_byte_length=private_size,
        ), {}
    artifacts = tuple(
        sorted(
            (
                _prepared_artifact(
                    case_id=corpus_row.case_id,
                    role="canonical_ligand_json",
                    source_artifact=source_artifacts[
                        "ligand_start_conformer_sdf"
                    ],
                    payload=ligand_payload,
                    system=ligand,
                    ligand_preparation_receipt_sha256=(
                        ligand_receipt_sha256
                    ),
                ),
                _prepared_artifact(
                    case_id=corpus_row.case_id,
                    role="canonical_receptor_json",
                    source_artifact=source_artifacts["receptor_pdb"],
                    payload=receptor_payload,
                    system=receptor,
                ),
            ),
            key=lambda row: row.role,
        )
    )
    payloads = {
        artifact.relative_path: (
            ligand_payload
            if artifact.role == "canonical_ligand_json"
            else receptor_payload
        )
        for artifact in artifacts
    }
    return PoseBustersInternalPreparationCase(
        case_id=corpus_row.case_id,
        status="prepared",
        disposition_code="canonical_internal_redocking_input_pair",
        reference_scorer_scope_status=corpus_row.reference_scorer_scope_status,
        reference_scorer_scope_blockers=(
            corpus_row.reference_scorer_scope_blockers
        ),
        preparation_attempted=True,
        pocket_center_binary64_hex=center,
        artifacts=artifacts,
    ), payloads


def _implementation_source_members(
    corpus: PoseBustersCorpusAuditReceipt,
) -> tuple[tuple[str, str], ...]:
    members = dict(corpus.implementation_source_members)
    members.update(
        {
            "internal_preparation": _source_file_sha256(__file__),
            "pdb_parser": _source_file_sha256(
                Path(__file__).parents[1] / "io" / "pdb.py"
            ),
            "rdkit_openff_preparation": _source_file_sha256(
                Path(__file__).parents[1]
                / "molecular"
                / "rdkit_openff_preparation.py"
            ),
            "canonical_serialization": _source_file_sha256(
                Path(__file__).parents[1] / "molecular" / "serialization.py"
            ),
        }
    )
    return tuple(sorted(members.items()))


def _build_preparation(
    archive_path: str | os.PathLike[str],
    selection_path: str | os.PathLike[str],
    intake_receipt_path: str | os.PathLike[str],
    corpus_audit_receipt_path: str | os.PathLike[str],
    *,
    contract: PoseBustersArchiveContract,
    configuration: PoseBustersInternalPreparationConfig,
) -> tuple[PoseBustersInternalPreparationReceipt, dict[str, bytes]]:
    try:
        corpus = verify_posebusters_corpus_audit_receipt(
            corpus_audit_receipt_path,
            archive_path,
            selection_path,
            intake_receipt_path,
            contract=contract,
        )
        intake = verify_posebusters_archive_intake_receipt(
            intake_receipt_path,
            archive_path,
            selection_path,
            contract=contract,
        )
    except (PoseBustersCorpusAuditError, PoseBustersArchiveIntakeError) as exc:
        raise PoseBustersInternalPreparationError(
            "internal preparation requires exact verified corpus and intake receipts"
        ) from exc
    if tuple(row.case_id for row in corpus.case_rows) != tuple(
        row.case_id for row in intake.case_rows
    ):
        raise PoseBustersInternalPreparationError(
            "corpus and intake case identities disagree"
        )
    runtime = _load_runtime(configuration)
    corpus_rows = {row.case_id: row for row in corpus.case_rows}
    descriptor, size = _regular_file_descriptor(
        archive_path,
        maximum_bytes=contract.archive_size_bytes,
    )
    payloads: dict[str, bytes] = {}
    try:
        if (
            size != contract.archive_size_bytes
            or _hash_descriptor(descriptor, size) != contract.archive_sha256
        ):
            raise PoseBustersInternalPreparationError(
                "internal-preparation archive changed after verification"
            )
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            try:
                with zipfile.ZipFile(handle, "r") as archive:
                    rows_list: list[PoseBustersInternalPreparationCase] = []
                    for intake_row in intake.case_rows:
                        row, case_payloads = _prepare_case(
                            archive,
                            intake_row,
                            corpus_rows[intake_row.case_id],
                            runtime,
                        )
                        rows_list.append(row)
                        overlap = set(payloads).intersection(case_payloads)
                        if overlap:
                            raise PoseBustersInternalPreparationError(
                                "internal-preparation artifact paths are duplicated"
                            )
                        payloads.update(case_payloads)
                    rows = tuple(rows_list)
            except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
                raise PoseBustersInternalPreparationError(
                    "internal preparation failed bounded ZIP access"
                ) from exc
    finally:
        os.close(descriptor)
    source_members = _implementation_source_members(corpus)
    receipt = PoseBustersInternalPreparationReceipt(
        corpus_audit_receipt_sha256=corpus.fingerprint_sha256,
        archive_intake_receipt_sha256=intake.fingerprint_sha256,
        archive_contract_sha256=contract.fingerprint_sha256,
        configuration=configuration,
        runtime_identity=runtime.identity,
        implementation_source_sha256=_canonical_sha256(dict(source_members)),
        implementation_source_members=source_members,
        case_rows=rows,
        metrics=_summary_metrics(rows),
        artifact_set_sha256=_artifact_set_sha256(rows),
    )
    expected_paths = {
        artifact.relative_path
        for row in rows
        for artifact in row.artifacts
    }
    if set(payloads) != expected_paths:
        raise PoseBustersInternalPreparationError(
            "internal-preparation artifact payload set is incomplete"
        )
    return receipt, payloads


def materialize_posebusters_internal_preparation(
    archive_path: str | os.PathLike[str],
    selection_path: str | os.PathLike[str],
    intake_receipt_path: str | os.PathLike[str],
    corpus_audit_receipt_path: str | os.PathLike[str],
    artifact_root: str | os.PathLike[str],
    *,
    contract: PoseBustersArchiveContract = OFFICIAL_POSEBUSTERS_ARCHIVE_CONTRACT,
    configuration: PoseBustersInternalPreparationConfig | None = None,
) -> PoseBustersInternalPreparationReceipt:
    """Prepare canonical artifacts and retain every corpus disposition."""

    active = (
        PoseBustersInternalPreparationConfig()
        if configuration is None
        else configuration
    )
    if not isinstance(active, PoseBustersInternalPreparationConfig):
        raise TypeError("configuration has the wrong type")
    receipt, payloads = _build_preparation(
        archive_path,
        selection_path,
        intake_receipt_path,
        corpus_audit_receipt_path,
        contract=contract,
        configuration=active,
    )
    try:
        _write_artifact_tree(Path(artifact_root), payloads)
    except PoseBustersExternalPreparationError as exc:
        raise PoseBustersInternalPreparationError(
            "internal-preparation artifact tree could not be materialized"
        ) from exc
    return receipt


def verify_posebusters_internal_preparation_receipt(
    preparation_receipt_path: str | os.PathLike[str],
    artifact_root: str | os.PathLike[str],
    archive_path: str | os.PathLike[str],
    selection_path: str | os.PathLike[str],
    intake_receipt_path: str | os.PathLike[str],
    corpus_audit_receipt_path: str | os.PathLike[str],
    *,
    contract: PoseBustersArchiveContract = OFFICIAL_POSEBUSTERS_ARCHIVE_CONTRACT,
    configuration: PoseBustersInternalPreparationConfig | None = None,
) -> PoseBustersInternalPreparationReceipt:
    """Reexecute preparation and verify receipt plus exact artifact tree."""

    active = (
        PoseBustersInternalPreparationConfig()
        if configuration is None
        else configuration
    )
    source = _read_exact_regular_file(
        preparation_receipt_path,
        maximum_bytes=POSEBUSTERS_INTERNAL_PREPARATION_MAX_RECEIPT_BYTES,
    )
    try:
        raw = json.loads(
            source.decode("ascii"),
            object_pairs_hook=_json_object_pairs,
            parse_constant=_reject_json_constant,
        )
    except PoseBustersInternalPreparationError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PoseBustersInternalPreparationError(
            "internal-preparation receipt must be ASCII JSON"
        ) from exc
    if (
        not isinstance(raw, dict)
        or raw.get("schema_id") != POSEBUSTERS_INTERNAL_PREPARATION_SCHEMA_ID
        or source != _canonical_bytes(raw) + b"\n"
        or raw.get("receipt_sha256")
        != _canonical_sha256(
            {key: value for key, value in raw.items() if key != "receipt_sha256"}
        )
    ):
        raise PoseBustersInternalPreparationError(
            "internal-preparation receipt is not canonical or self-authenticating"
        )
    expected, payloads = _build_preparation(
        archive_path,
        selection_path,
        intake_receipt_path,
        corpus_audit_receipt_path,
        contract=contract,
        configuration=active,
    )
    if source != _canonical_bytes(expected.to_dict()) + b"\n":
        raise PoseBustersInternalPreparationError(
            "internal-preparation receipt failed exact source-tree reexecution"
        )
    try:
        _verify_artifact_tree(Path(artifact_root), payloads)
    except PoseBustersExternalPreparationError as exc:
        raise PoseBustersInternalPreparationError(
            "internal-preparation artifact tree failed exact verification"
        ) from exc
    return expected


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="betelgeuze-engine-v2-posebusters-internal-preparation",
        description=(
            "Prepare canonical internal redocking inputs with all-case rows."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("materialize", "verify"):
        command = subparsers.add_parser(name)
        command.add_argument("--archive", required=True)
        command.add_argument("--selection", required=True)
        command.add_argument("--intake-receipt", required=True)
        command.add_argument("--corpus-audit-receipt", required=True)
        command.add_argument("--artifact-root", required=True)
        command.add_argument("--receipt", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "materialize":
        if Path(args.receipt).exists():
            raise PoseBustersInternalPreparationError(
                "internal-preparation receipt output already exists"
            )
        receipt = materialize_posebusters_internal_preparation(
            args.archive,
            args.selection,
            args.intake_receipt,
            args.corpus_audit_receipt,
            args.artifact_root,
        )
        receipt.write_json(args.receipt)
    else:
        receipt = verify_posebusters_internal_preparation_receipt(
            args.receipt,
            args.artifact_root,
            args.archive,
            args.selection,
            args.intake_receipt,
            args.corpus_audit_receipt,
        )
    print(
        json.dumps(
            {
                "receipt_sha256": receipt.fingerprint_sha256,
                "all_case_denominator": len(receipt.case_rows),
                "prepared_case_count": receipt.prepared_case_count,
                "redocking_executed": False,
                "claim_safe": False,
            },
            sort_keys=True,
        )
    )
    return 0


__all__ = [
    "POSEBUSTERS_INTERNAL_PREPARATION_ARTIFACT_SCHEMA_ID",
    "POSEBUSTERS_INTERNAL_PREPARATION_BLOCKERS",
    "POSEBUSTERS_INTERNAL_PREPARATION_CASE_SCHEMA_ID",
    "POSEBUSTERS_INTERNAL_PREPARATION_CONFIG_SCHEMA_ID",
    "POSEBUSTERS_INTERNAL_PREPARATION_MAX_ARTIFACT_BYTES",
    "POSEBUSTERS_INTERNAL_PREPARATION_MAX_RECEIPT_BYTES",
    "POSEBUSTERS_INTERNAL_PREPARATION_METRIC_SCHEMA_ID",
    "POSEBUSTERS_INTERNAL_PREPARATION_RUNTIME_SCHEMA_ID",
    "POSEBUSTERS_INTERNAL_PREPARATION_SCHEMA_ID",
    "POSEBUSTERS_INTERNAL_PREPARATION_SCOPE_STATUS",
    "PoseBustersInternalPreparationCase",
    "PoseBustersInternalPreparationConfig",
    "PoseBustersInternalPreparationError",
    "PoseBustersInternalPreparationMetric",
    "PoseBustersInternalPreparationReceipt",
    "PoseBustersInternalPreparationRuntime",
    "PoseBustersInternalPreparedArtifact",
    "main",
    "materialize_posebusters_internal_preparation",
    "verify_posebusters_internal_preparation_receipt",
]


if __name__ == "__main__":
    raise SystemExit(main())
