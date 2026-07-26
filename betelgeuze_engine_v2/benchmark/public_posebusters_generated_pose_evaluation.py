"""Failure-inclusive PoseBusters evaluation of generated Vina poses.

The evaluator consumes the exact public PoseBusters archive chain, strict
preparation receipt, and Vina execution receipt.  It reconstructs every Vina
PDBQT model through pinned Meeko, evaluates the official PoseBusters ``redock``
configuration, and preserves every report value and every blocked or failed
row.  Physical-validity and direct receptor-frame RMSD endpoints are kept
separate.  The supported 18-case execution subset is not promoted to a public
docking benchmark or product claim.
"""

from __future__ import annotations

from dataclasses import dataclass
import argparse
import contextlib
import hashlib
import importlib
import json
import math
from numbers import Real
import os
from pathlib import Path, PurePosixPath
import stat
import tempfile
from typing import Any, Protocol, Sequence, TextIO, cast
import zipfile

from .public_posebusters_corpus_audit import (
    _canonical_bytes,
    _canonical_sha256,
    _positive_int,
    _source_file_sha256,
    _token,
)
from .public_posebusters_external_preparation import (
    PoseBustersExternalPreparationDependency,
    PoseBustersExternalPreparationError,
    PoseBustersExternalPreparationRuntime,
    _dependency_payload,
    _DigestingTextSink,
    _hash_regular_file,
    _require_import_owned_by_distribution,
    _runtime_identity,
    _verify_artifact_tree,
    verify_posebusters_external_preparation_receipt,
)
from .public_posebusters_intake import (
    OFFICIAL_POSEBUSTERS_ARCHIVE_CONTRACT,
    POSEBUSTERS_ARCHIVE_MAX_RECEIPT_BYTES,
    PoseBustersArchiveContract,
    PoseBustersArchiveIntakeError,
    _hash_descriptor,
    _read_exact_regular_file,
    _regular_file_descriptor,
    verify_posebusters_archive_intake_receipt,
)
from .public_posebusters_vina_execution import (
    POSEBUSTERS_VINA_EXECUTION_ARTIFACT_SCHEMA_ID,
    POSEBUSTERS_VINA_EXECUTION_CONFIGURATION_SHA256,
    POSEBUSTERS_VINA_EXECUTION_MAX_POSE_ARTIFACT_BYTES,
    POSEBUSTERS_VINA_EXECUTION_MAX_RECEIPT_BYTES,
    POSEBUSTERS_VINA_EXECUTION_SCHEMA_ID,
)


POSEBUSTERS_GENERATED_POSE_REPORT_VALUE_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_generated_pose_report_value/1.0.0"
)
POSEBUSTERS_GENERATED_POSE_RESULT_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_generated_pose_result/1.0.0"
)
POSEBUSTERS_GENERATED_POSE_CASE_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_generated_pose_case/1.0.0"
)
POSEBUSTERS_GENERATED_POSE_METRIC_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_generated_pose_metric/1.0.0"
)
POSEBUSTERS_GENERATED_POSE_RUNTIME_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_generated_pose_runtime/1.0.0"
)
POSEBUSTERS_GENERATED_POSE_EVALUATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_generated_pose_evaluation/1.0.0"
)

POSEBUSTERS_GENERATED_POSE_MAX_RECEIPT_BYTES = 64 * 1024 * 1024
POSEBUSTERS_GENERATED_POSE_MAX_REPORT_VALUES = 512
POSEBUSTERS_GENERATED_POSE_MAX_TEXT_BYTES = 16 * 1024
POSEBUSTERS_GENERATED_POSE_CONFIDENCE_LEVEL = 0.95
POSEBUSTERS_GENERATED_POSE_Z = 1.959963984540054
POSEBUSTERS_GENERATED_POSE_VERSION = "0.6.5"
POSEBUSTERS_GENERATED_POSE_WHEEL_SHA256 = (
    "3e0cbca6481079d5ab7d1989a8a8f184dbba27366613c4b515658ea52fb95ea3"
)
POSEBUSTERS_GENERATED_POSE_WHEEL_SIZE_BYTES = 567_794
POSEBUSTERS_GENERATED_POSE_REDOCK_CONFIGURATION_SHA256 = (
    "4d551d898ff29a404f16e02ad5a7a2d4235e6b7b14e9a3e27f7c66b4d16b2da9"
)
POSEBUSTERS_GENERATED_POSE_DEPENDENCY_PINS = {
    "pandas": "2.3.3",
    "posebusters": POSEBUSTERS_GENERATED_POSE_VERSION,
    "pyyaml": "6.0.3",
}
POSEBUSTERS_GENERATED_POSE_CONFIGURATION = {
    "conformer_id_policy": "copy_single_conformer_and_assign_id_zero",
    "full_report": True,
    "meeko_keep_flexres": False,
    "meeko_only_cluster_leads": False,
    "meeko_skip_typing": True,
    "posebusters_config_name": "redock",
    "posebusters_config_sha256": (
        POSEBUSTERS_GENERATED_POSE_REDOCK_CONFIGURATION_SHA256
    ),
    "posebusters_max_workers": 0,
    "posebusters_version": POSEBUSTERS_GENERATED_POSE_VERSION,
    "rmsd_oracle": (
        "posebusters_0.6.5_robust_rmsd_direct_calcrms_heavy_only"
    ),
    "rmsd_threshold_angstrom": 2.0,
    "top_k": 5,
}
POSEBUSTERS_GENERATED_POSE_CONFIGURATION_SHA256 = (
    "3c02c32628e5974f23490652467517f26bd60242b680215dcdbae5d4d852ad74"
)
POSEBUSTERS_GENERATED_POSE_SELECTED_COLUMNS = (
    "mol_pred_loaded",
    "mol_true_loaded",
    "mol_cond_loaded",
    "sanitization",
    "inchi_convertible",
    "all_atoms_connected",
    "no_radicals",
    "molecular_formula",
    "molecular_bonds",
    "double_bond_stereochemistry",
    "tetrahedral_chirality",
    "bond_lengths",
    "bond_angles",
    "internal_steric_clash",
    "aromatic_ring_flatness",
    "non-aromatic_ring_non-flatness",
    "double_bond_flatness",
    "internal_energy",
    "protein-ligand_maximum_distance",
    "minimum_distance_to_protein",
    "minimum_distance_to_organic_cofactors",
    "minimum_distance_to_inorganic_cofactors",
    "minimum_distance_to_waters",
    "volume_overlap_with_protein",
    "volume_overlap_with_organic_cofactors",
    "volume_overlap_with_inorganic_cofactors",
    "volume_overlap_with_waters",
    "rmsd_≤_2å",
)
POSEBUSTERS_GENERATED_POSE_BLOCKERS = (
    "only_strictly_prepared_chemistry_subset_evaluated",
    "prepared_ad4_types_and_gasteiger_charges_not_independently_validated",
    "posebusters_identity_and_rmsd_fallback_semantics_remain_external",
    "gnina_and_smina_same_input_results_missing",
    "target_family_and_leakage_receipts_missing",
    "independent_external_host_rerun_missing",
    "independent_scientific_review_missing",
    "public_docking_benchmark_claim_not_authorized",
)

_VINA_CASE_STATUSES = {
    "success",
    "engine_failure",
    "blocked_preparation_failure",
    "blocked_upstream_failure",
    "abstain_chemistry_scope",
}
_CASE_STATUSES = {
    "evaluated",
    "partial_evaluation",
    "evaluation_failure",
    "blocked_vina_engine_failure",
    "blocked_preparation_failure",
    "blocked_upstream_failure",
    "abstain_chemistry_scope",
}
_POSE_STATUSES = {"evaluated", "evaluation_failure"}
_VALUE_TYPES = {"boolean", "integer", "binary64", "text", "missing"}
_MISSING_CODES = {"nan", "positive_infinity", "negative_infinity", "pandas_na"}
_SHA256_CHARACTERS = frozenset("0123456789abcdef")
_VINA_ENERGY_COMPONENT_COUNT = 5
_IDENTITY_COLUMNS = (
    "molecular_formula",
    "molecular_bonds",
    "double_bond_stereochemistry",
    "tetrahedral_chirality",
)
_GEOMETRY_COLUMNS = (
    "bond_lengths",
    "bond_angles",
    "internal_steric_clash",
    "aromatic_ring_flatness",
    "non_aromatic_ring_non_flatness",
    "double_bond_flatness",
)
_INTERMOLECULAR_COLUMNS = (
    "protein_ligand_maximum_distance",
    "minimum_distance_to_protein",
    "minimum_distance_to_organic_cofactors",
    "minimum_distance_to_inorganic_cofactors",
    "minimum_distance_to_waters",
    "volume_overlap_with_protein",
    "volume_overlap_with_organic_cofactors",
    "volume_overlap_with_inorganic_cofactors",
    "volume_overlap_with_waters",
)


class PoseBustersGeneratedPoseEvaluationError(ValueError):
    """Generated-pose input, runtime, report, or receipt is invalid."""


class PoseBustersGeneratedPoseCaseError(RuntimeError):
    """One generated-pose case failed before per-pose evaluation."""

    def __init__(
        self,
        *,
        stage: str,
        error_code: str,
        error_type: str,
        error_message_sha256: str,
        diagnostic_sha256: str,
        diagnostic_size_bytes: int,
    ) -> None:
        super().__init__(error_code)
        self.stage = _token(stage, name="generated-pose failure stage")
        self.error_code = _token(error_code, name="generated-pose error code")
        self.error_type = _identifier(error_type, name="generated-pose error type")
        self.error_message_sha256 = _digest(
            error_message_sha256,
            name="generated-pose error message",
        )
        self.diagnostic_sha256 = _digest(
            diagnostic_sha256,
            name="generated-pose diagnostic",
        )
        self.diagnostic_size_bytes = _positive_int(
            diagnostic_size_bytes,
            name="generated-pose diagnostic size",
            allow_zero=True,
        )


def _digest(value: object, *, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in _SHA256_CHARACTERS for character in value)
    ):
        raise PoseBustersGeneratedPoseEvaluationError(
            f"{name} must be a lowercase SHA-256"
        )
    return value


def _case_id(value: object) -> str:
    if not isinstance(value, str):
        raise PoseBustersGeneratedPoseEvaluationError("case ID must be text")
    result = value.strip()
    parts = result.split("_")
    if (
        len(parts) != 2
        or len(parts[0]) != 4
        or len(parts[1]) != 3
        or not all(
            part.isascii() and part.isalnum() and part.upper() == part
            for part in parts
        )
    ):
        raise PoseBustersGeneratedPoseEvaluationError(
            "case ID must use uppercase PDB4_CCD3 form"
        )
    return result


def _identifier(value: object, *, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise PoseBustersGeneratedPoseEvaluationError(
            f"{name} must be non-empty text"
        )
    if (
        not value.isascii()
        or not (value[0].isalpha() or value[0] == "_")
        or any(not (character.isalnum() or character == "_") for character in value)
    ):
        raise PoseBustersGeneratedPoseEvaluationError(
            f"{name} must be an identifier"
        )
    return value


def _bounded_text(value: object, *, name: str, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not value and not allow_empty):
        raise PoseBustersGeneratedPoseEvaluationError(
            f"{name} must be bounded text"
        )
    try:
        source = value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise PoseBustersGeneratedPoseEvaluationError(
            f"{name} must be UTF-8 text"
        ) from exc
    if len(source) > POSEBUSTERS_GENERATED_POSE_MAX_TEXT_BYTES or "\x00" in value:
        raise PoseBustersGeneratedPoseEvaluationError(
            f"{name} exceeds its text bound"
        )
    return value


def _relative_path(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise PoseBustersGeneratedPoseEvaluationError(
            "Vina pose artifact path must be non-empty text"
        )
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "." in path.parts:
        raise PoseBustersGeneratedPoseEvaluationError(
            "Vina pose artifact path must remain below artifact root"
        )
    result = path.as_posix()
    if not result.endswith("/poses.pdbqt"):
        raise PoseBustersGeneratedPoseEvaluationError(
            "Vina pose artifact path must end in poses.pdbqt"
        )
    return result


def _hash_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _normalize_error(error: BaseException) -> bytes:
    text = " ".join(str(error).split())
    if len(text) > 2048:
        text = text[:2048]
    return f"{type(error).__name__}:{text}".encode("utf-8", errors="replace")


def _finite_hex(value: float, *, name: str) -> str:
    number = float(value)
    if not math.isfinite(number):
        raise PoseBustersGeneratedPoseEvaluationError(f"{name} must be finite")
    return number.hex()


def _validate_hex(value: object, *, name: str) -> str:
    if not isinstance(value, str):
        raise PoseBustersGeneratedPoseEvaluationError(
            f"{name} must be canonical binary64"
        )
    try:
        number = float.fromhex(value)
    except ValueError as exc:
        raise PoseBustersGeneratedPoseEvaluationError(
            f"{name} must be canonical binary64"
        ) from exc
    if not math.isfinite(number) or number.hex() != value:
        raise PoseBustersGeneratedPoseEvaluationError(
            f"{name} must be canonical finite binary64"
        )
    return value


def _output_id(source_name: str) -> str:
    value = source_name
    if value == "rmsd_≤_2å":
        return "rmsd_le_2_angstrom"
    value = value.replace("-", "_")
    return _identifier(value, name="PoseBusters output ID")


@dataclass(frozen=True, slots=True)
class PoseBustersGeneratedPoseReportValue:
    ordinal: int
    source_name: str
    output_id: str
    occurrence: int
    value_type: str
    value: bool | int | str | None
    missing_code: str = ""
    schema_id: str = POSEBUSTERS_GENERATED_POSE_REPORT_VALUE_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_GENERATED_POSE_REPORT_VALUE_SCHEMA_ID:
            raise PoseBustersGeneratedPoseEvaluationError(
                "unsupported PoseBusters report-value schema"
            )
        ordinal = _positive_int(
            self.ordinal,
            name="PoseBusters report ordinal",
            allow_zero=True,
        )
        occurrence = _positive_int(
            self.occurrence,
            name="PoseBusters report occurrence",
            allow_zero=True,
        )
        source_name = _bounded_text(
            self.source_name,
            name="PoseBusters source column",
        )
        output_id = _identifier(self.output_id, name="PoseBusters output ID")
        if output_id != _output_id(source_name):
            raise PoseBustersGeneratedPoseEvaluationError(
                "PoseBusters source column and output ID disagree"
            )
        if self.value_type not in _VALUE_TYPES:
            raise PoseBustersGeneratedPoseEvaluationError(
                "unsupported PoseBusters report-value type"
            )
        value = self.value
        missing_code = self.missing_code
        if self.value_type == "boolean":
            valid = isinstance(value, bool) and not missing_code
        elif self.value_type == "integer":
            valid = isinstance(value, int) and not isinstance(value, bool) and not missing_code
        elif self.value_type == "binary64":
            valid = isinstance(value, str) and not missing_code
            if valid:
                value = _validate_hex(value, name="PoseBusters binary64 value")
        elif self.value_type == "text":
            valid = isinstance(value, str) and not missing_code
            if valid:
                value = _bounded_text(
                    value,
                    name="PoseBusters text value",
                    allow_empty=True,
                )
        else:
            valid = value is None and missing_code in _MISSING_CODES
        if not valid:
            raise PoseBustersGeneratedPoseEvaluationError(
                "PoseBusters report value is inconsistent"
            )
        object.__setattr__(self, "ordinal", ordinal)
        object.__setattr__(self, "source_name", source_name)
        object.__setattr__(self, "output_id", output_id)
        object.__setattr__(self, "occurrence", occurrence)
        object.__setattr__(self, "value", value)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "ordinal": self.ordinal,
            "source_name": self.source_name,
            "output_id": self.output_id,
            "occurrence": self.occurrence,
            "value_type": self.value_type,
            "value": self.value,
            "missing_code": self.missing_code,
        }


def _report_value(
    ordinal: int,
    source_name: str,
    occurrence: int,
    value: Any,
    *,
    numpy_module: Any,
    pandas_module: Any,
) -> PoseBustersGeneratedPoseReportValue:
    if value is pandas_module.NA:
        value_type = "missing"
        normalized: bool | int | str | None = None
        missing_code = "pandas_na"
    elif isinstance(value, (bool, numpy_module.bool_)):
        value_type = "boolean"
        normalized = bool(value)
        missing_code = ""
    elif isinstance(value, (int, numpy_module.integer)):
        value_type = "integer"
        normalized = int(value)
        missing_code = ""
    elif isinstance(value, (float, numpy_module.floating)):
        number = float(value)
        if math.isnan(number):
            value_type = "missing"
            normalized = None
            missing_code = "nan"
        elif math.isinf(number):
            value_type = "missing"
            normalized = None
            missing_code = (
                "positive_infinity" if number > 0.0 else "negative_infinity"
            )
        else:
            value_type = "binary64"
            normalized = number.hex()
            missing_code = ""
    elif isinstance(value, str):
        value_type = "text"
        normalized = value
        missing_code = ""
    else:
        try:
            missing = bool(pandas_module.isna(value))
        except (TypeError, ValueError):
            missing = False
        if not missing:
            raise PoseBustersGeneratedPoseEvaluationError(
                "PoseBusters report contains an unsupported value type"
            )
        value_type = "missing"
        normalized = None
        missing_code = "pandas_na"
    return PoseBustersGeneratedPoseReportValue(
        ordinal=ordinal,
        source_name=source_name,
        output_id=_output_id(source_name),
        occurrence=occurrence,
        value_type=value_type,
        value=normalized,
        missing_code=missing_code,
    )


def _boolean_value(
    values: Sequence[PoseBustersGeneratedPoseReportValue],
    output_id: str,
) -> bool | None:
    matches = [row for row in values if row.output_id == output_id]
    if len(matches) != 1 or matches[0].value_type != "boolean":
        return None
    return bool(matches[0].value)


def _binary64_value(
    values: Sequence[PoseBustersGeneratedPoseReportValue],
    output_id: str,
) -> str:
    matches = [row for row in values if row.output_id == output_id]
    if len(matches) != 1 or matches[0].value_type != "binary64":
        return ""
    assert isinstance(matches[0].value, str)
    return matches[0].value


@dataclass(frozen=True, slots=True)
class PoseBustersGeneratedPoseResult:
    pose_rank: int
    status: str
    vina_energy_components_binary64_hex: tuple[str, ...]
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
    schema_id: str = POSEBUSTERS_GENERATED_POSE_RESULT_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_GENERATED_POSE_RESULT_SCHEMA_ID:
            raise PoseBustersGeneratedPoseEvaluationError(
                "unsupported generated-pose result schema"
            )
        rank = _positive_int(self.pose_rank, name="generated-pose rank")
        if self.status not in _POSE_STATUSES:
            raise PoseBustersGeneratedPoseEvaluationError(
                "generated-pose result status is invalid"
            )
        energies = tuple(
            _validate_hex(value, name="Vina energy component")
            for value in self.vina_energy_components_binary64_hex
        )
        if len(energies) != _VINA_ENERGY_COMPONENT_COUNT:
            raise PoseBustersGeneratedPoseEvaluationError(
                "generated-pose result requires five Vina energy components"
            )
        report = tuple(self.report_values)
        if (
            len(report) > POSEBUSTERS_GENERATED_POSE_MAX_REPORT_VALUES
            or tuple(row.ordinal for row in report) != tuple(range(len(report)))
        ):
            raise PoseBustersGeneratedPoseEvaluationError(
                "PoseBusters report-value order is invalid"
            )
        diagnostics = _positive_int(
            self.diagnostic_size_bytes,
            name="generated-pose diagnostic size",
            allow_zero=True,
        )
        numeric_fields = (
            "direct_rmsd_angstrom_binary64_hex",
            "kabsch_rmsd_angstrom_binary64_hex",
            "centroid_distance_angstrom_binary64_hex",
            "energy_ratio_binary64_hex",
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
                and not any(
                    (
                        self.error_stage,
                        self.error_code,
                        self.error_type,
                        self.error_message_sha256,
                    )
                )
                and bool(self.diagnostic_sha256)
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
                _boolean_value(report, name) is True for name in _IDENTITY_COLUMNS
            )
            expected_geometry = all(
                _boolean_value(report, name) is True for name in _GEOMETRY_COLUMNS
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
                and self.intermolecular_distance_and_overlap_pass == expected_inter
                and self.rmsd_evaluated == expected_rmsd_evaluated
                and self.rmsd_within_2_angstrom == expected_hit
                and self.direct_rmsd_angstrom_binary64_hex == direct
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
                        *(
                            bool(getattr(self, name))
                            for name in numeric_fields
                        ),
                    )
                )
            )
        if not valid:
            raise PoseBustersGeneratedPoseEvaluationError(
                "generated-pose result disposition is inconsistent"
            )
        if self.error_stage:
            object.__setattr__(
                self,
                "error_stage",
                _token(self.error_stage, name="generated-pose error stage"),
            )
            object.__setattr__(
                self,
                "error_code",
                _token(self.error_code, name="generated-pose error code"),
            )
            object.__setattr__(
                self,
                "error_type",
                _identifier(self.error_type, name="generated-pose error type"),
            )
            object.__setattr__(
                self,
                "error_message_sha256",
                _digest(
                    self.error_message_sha256,
                    name="generated-pose error message",
                ),
            )
        object.__setattr__(
            self,
            "diagnostic_sha256",
            _digest(self.diagnostic_sha256, name="generated-pose diagnostic"),
        )
        object.__setattr__(self, "pose_rank", rank)
        object.__setattr__(self, "vina_energy_components_binary64_hex", energies)
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
        return {
            "schema_id": self.schema_id,
            "pose_rank": self.pose_rank,
            "status": self.status,
            "vina_energy_component_order": [
                "total",
                "inter",
                "intra",
                "torsions",
                "intra_best_pose",
            ],
            "vina_energy_components_binary64_hex": list(
                self.vina_energy_components_binary64_hex
            ),
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
class _RuntimePoseOutcome:
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


@dataclass(frozen=True, slots=True)
class PoseBustersGeneratedPoseRuntimeIdentity:
    preparation_runtime: PoseBustersExternalPreparationRuntime
    additional_dependencies: tuple[PoseBustersExternalPreparationDependency, ...]
    posebusters_wheel_sha256: str
    posebusters_wheel_size_bytes: int
    redock_configuration_sha256: str
    posebusters_api_source_sha256: str
    meeko_export_source_sha256: str
    schema_id: str = POSEBUSTERS_GENERATED_POSE_RUNTIME_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_GENERATED_POSE_RUNTIME_SCHEMA_ID:
            raise PoseBustersGeneratedPoseEvaluationError(
                "unsupported generated-pose runtime schema"
            )
        if not isinstance(
            self.preparation_runtime,
            PoseBustersExternalPreparationRuntime,
        ):
            raise PoseBustersGeneratedPoseEvaluationError(
                "generated-pose runtime requires preparation runtime identity"
            )
        dependencies = tuple(self.additional_dependencies)
        if (
            tuple(row.distribution_name for row in dependencies)
            != tuple(sorted(POSEBUSTERS_GENERATED_POSE_DEPENDENCY_PINS))
            or any(
                row.version
                != POSEBUSTERS_GENERATED_POSE_DEPENDENCY_PINS[
                    row.distribution_name
                ]
                for row in dependencies
            )
        ):
            raise PoseBustersGeneratedPoseEvaluationError(
                "generated-pose runtime dependencies are not pinned"
            )
        wheel_sha = _digest(
            self.posebusters_wheel_sha256,
            name="PoseBusters wheel",
        )
        wheel_size = _positive_int(
            self.posebusters_wheel_size_bytes,
            name="PoseBusters wheel size",
        )
        if (
            wheel_sha != POSEBUSTERS_GENERATED_POSE_WHEEL_SHA256
            or wheel_size != POSEBUSTERS_GENERATED_POSE_WHEEL_SIZE_BYTES
            or self.redock_configuration_sha256
            != POSEBUSTERS_GENERATED_POSE_REDOCK_CONFIGURATION_SHA256
        ):
            raise PoseBustersGeneratedPoseEvaluationError(
                "PoseBusters wheel or redock configuration identity changed"
            )
        object.__setattr__(self, "additional_dependencies", dependencies)
        object.__setattr__(self, "posebusters_wheel_sha256", wheel_sha)
        object.__setattr__(self, "posebusters_wheel_size_bytes", wheel_size)
        object.__setattr__(
            self,
            "redock_configuration_sha256",
            _digest(
                self.redock_configuration_sha256,
                name="PoseBusters redock configuration",
            ),
        )
        object.__setattr__(
            self,
            "posebusters_api_source_sha256",
            _digest(
                self.posebusters_api_source_sha256,
                name="PoseBusters API source",
            ),
        )
        object.__setattr__(
            self,
            "meeko_export_source_sha256",
            _digest(
                self.meeko_export_source_sha256,
                name="Meeko export source",
            ),
        )

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "preparation_runtime": self.preparation_runtime.to_dict(),
            "preparation_runtime_identity_sha256": (
                self.preparation_runtime.fingerprint_sha256
            ),
            "additional_dependencies": [
                row.to_dict() for row in self.additional_dependencies
            ],
            "posebusters_wheel_sha256": self.posebusters_wheel_sha256,
            "posebusters_wheel_size_bytes": self.posebusters_wheel_size_bytes,
            "redock_configuration_sha256": self.redock_configuration_sha256,
            "posebusters_api_source_sha256": self.posebusters_api_source_sha256,
            "meeko_export_source_sha256": self.meeko_export_source_sha256,
            "selected_binary_columns": list(
                POSEBUSTERS_GENERATED_POSE_SELECTED_COLUMNS
            ),
        }


class _PoseBustersRuntimeProtocol(Protocol):
    identity: PoseBustersGeneratedPoseRuntimeIdentity

    def evaluate_case(
        self,
        poses_pdbqt: bytes,
        receptor_pdb: bytes,
        reference_ligands_sdf: bytes,
        expected_pose_count: int,
    ) -> tuple[_RuntimePoseOutcome, ...]: ...

    def evaluate_prepared_coordinate_case(
        self,
        ligand_start_sdf: bytes,
        source_atom_to_prepared_atom: Sequence[int],
        pose_coordinates_angstrom: Sequence[Sequence[Sequence[float]]],
        receptor_pdb: bytes,
        reference_ligands_sdf: bytes,
    ) -> tuple[_RuntimePoseOutcome, ...]: ...


def _private_scratch_root(path: Path) -> Path:
    try:
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
        metadata = path.lstat()
    except OSError as exc:
        raise PoseBustersGeneratedPoseEvaluationError(
            "PoseBusters scratch root is unavailable"
        ) from exc
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or stat.S_ISLNK(metadata.st_mode)
        or stat.S_IMODE(metadata.st_mode) != 0o700
    ):
        raise PoseBustersGeneratedPoseEvaluationError(
            "PoseBusters scratch root must be a private real directory"
        )
    return path


def _write_private_file(path: Path, source: bytes) -> None:
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
        0o600,
    )
    try:
        observed = 0
        while observed < len(source):
            written = os.write(descriptor, source[observed:])
            if written < 1:
                raise OSError("private staging write made no progress")
            observed += written
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


class _PoseBustersRuntime:
    def __init__(
        self,
        *,
        PoseBusters: Any,
        PDBQTMolecule: Any,
        RDKitMolCreate: Any,
        Chem: Any,
        numpy_module: Any,
        pandas_module: Any,
        identity: PoseBustersGeneratedPoseRuntimeIdentity,
        scratch_root: Path,
    ) -> None:
        self._PoseBusters = PoseBusters
        self._PDBQTMolecule = PDBQTMolecule
        self._RDKitMolCreate = RDKitMolCreate
        self._Chem = Chem
        self._numpy = numpy_module
        self._pandas = pandas_module
        self.identity = identity
        self._scratch_root = _private_scratch_root(scratch_root)
        self._engine = PoseBusters(config="redock", max_workers=0)

    def _outcome_from_report(
        self,
        report: Any,
        row_index: int,
        sink: _DigestingTextSink,
    ) -> _RuntimePoseOutcome:
        row_count = tuple(report.shape)[0]
        if row_index < 0 or row_index >= row_count:
            raise ValueError("PoseBusters report row index is out of bounds")
        columns = tuple(str(value) for value in report.columns.tolist())
        if columns[: len(POSEBUSTERS_GENERATED_POSE_SELECTED_COLUMNS)] != (
            POSEBUSTERS_GENERATED_POSE_SELECTED_COLUMNS
        ):
            raise ValueError("PoseBusters selected report columns changed")
        values = report.iloc[row_index].tolist()
        if len(values) != len(columns):
            raise ValueError("PoseBusters report columns and values disagree")
        occurrences: dict[str, int] = {}
        normalized: list[PoseBustersGeneratedPoseReportValue] = []
        for ordinal, (column, value) in enumerate(zip(columns, values)):
            occurrence = occurrences.get(column, 0)
            occurrences[column] = occurrence + 1
            normalized.append(
                _report_value(
                    ordinal,
                    column,
                    occurrence,
                    value,
                    numpy_module=self._numpy,
                    pandas_module=self._pandas,
                )
            )
        rows = tuple(normalized)
        selected = rows[: len(POSEBUSTERS_GENERATED_POSE_SELECTED_COLUMNS)]
        non_rmsd = all(
            row.value_type == "boolean" and row.value is True
            for row in selected[:-1]
        )
        identity = all(
            _boolean_value(rows, name) is True for name in _IDENTITY_COLUMNS
        )
        geometry = all(
            _boolean_value(rows, name) is True for name in _GEOMETRY_COLUMNS
        )
        energy = _boolean_value(rows, "internal_energy") is True
        intermolecular = all(
            _boolean_value(rows, name) is True
            for name in _INTERMOLECULAR_COLUMNS
        )
        direct = _binary64_value(rows, "rmsd")
        rmsd_evaluated = bool(direct)
        rmsd_hit = (
            rmsd_evaluated
            and float.fromhex(direct)
            <= POSEBUSTERS_GENERATED_POSE_CONFIGURATION[
                "rmsd_threshold_angstrom"
            ]
        )
        return _RuntimePoseOutcome(
            status="evaluated",
            report_values=rows,
            all_non_rmsd_binary_tests_pass=non_rmsd,
            identity_pass=identity,
            intramolecular_geometry_pass=geometry,
            internal_energy_pass=energy,
            intermolecular_distance_and_overlap_pass=intermolecular,
            rmsd_evaluated=rmsd_evaluated,
            rmsd_within_2_angstrom=rmsd_hit,
            direct_rmsd_angstrom_binary64_hex=direct,
            kabsch_rmsd_angstrom_binary64_hex=_binary64_value(
                rows,
                "kabsch_rmsd",
            ),
            centroid_distance_angstrom_binary64_hex=_binary64_value(
                rows,
                "centroid_distance",
            ),
            energy_ratio_binary64_hex=_binary64_value(rows, "energy_ratio"),
            diagnostic_sha256=sink.sha256,
            diagnostic_size_bytes=sink.size_bytes,
        )

    def _one_report(
        self,
        pose: Any,
        native_path: Path,
        receptor_path: Path,
    ) -> _RuntimePoseOutcome:
        sink = _DigestingTextSink()
        try:
            with contextlib.redirect_stdout(
                cast(TextIO, sink)
            ), contextlib.redirect_stderr(cast(TextIO, sink)):
                report = self._engine.bust(
                    [pose],
                    mol_true=native_path,
                    mol_cond=receptor_path,
                    full_report=True,
                )
            if tuple(report.shape)[0] != 1:
                raise ValueError("PoseBusters did not return exactly one pose row")
            return self._outcome_from_report(report, 0, sink)
        except Exception as exc:
            return _RuntimePoseOutcome(
                status="evaluation_failure",
                error_stage="posebusters_redock",
                error_code="posebusters_pose_evaluation_failed",
                error_type=type(exc).__name__,
                error_message_sha256=_hash_bytes(_normalize_error(exc)),
                diagnostic_sha256=sink.sha256,
                diagnostic_size_bytes=sink.size_bytes,
            )

    def _evaluate_rdkit_poses(
        self,
        poses: Sequence[Any],
        receptor_pdb: bytes,
        reference_ligands_sdf: bytes,
    ) -> tuple[_RuntimePoseOutcome, ...]:
        expected_pose_count = len(poses)
        if expected_pose_count < 1 or expected_pose_count > 128:
            raise ValueError("PoseBusters pose count is outside its bound")
        with tempfile.TemporaryDirectory(
            prefix="posebusters-case-",
            dir=self._scratch_root,
        ) as temporary:
            root = Path(temporary)
            receptor_path = root / "receptor.pdb"
            native_path = root / "reference_ligands.sdf"
            _write_private_file(receptor_path, receptor_pdb)
            _write_private_file(native_path, reference_ligands_sdf)
            batch_sink = _DigestingTextSink()
            try:
                with (
                    contextlib.redirect_stdout(cast(TextIO, batch_sink)),
                    contextlib.redirect_stderr(cast(TextIO, batch_sink)),
                ):
                    report = self._engine.bust(
                        list(poses),
                        mol_true=native_path,
                        mol_cond=receptor_path,
                        full_report=True,
                    )
                if tuple(report.shape)[0] != expected_pose_count:
                    raise ValueError(
                        "PoseBusters report row count differs from pose input"
                    )
            except Exception:
                return tuple(
                    self._one_report(pose, native_path, receptor_path)
                    for pose in poses
                )
            outcomes: list[_RuntimePoseOutcome] = []
            for index, pose in enumerate(poses):
                try:
                    outcome = self._outcome_from_report(
                        report,
                        index,
                        batch_sink,
                    )
                except Exception:
                    outcome = self._one_report(
                        pose,
                        native_path,
                        receptor_path,
                    )
                outcomes.append(outcome)
            return tuple(outcomes)

    def evaluate_case(
        self,
        poses_pdbqt: bytes,
        receptor_pdb: bytes,
        reference_ligands_sdf: bytes,
        expected_pose_count: int,
    ) -> tuple[_RuntimePoseOutcome, ...]:
        sink = _DigestingTextSink()
        try:
            pdbqt_text = poses_pdbqt.decode("ascii")
            with contextlib.redirect_stdout(
                cast(TextIO, sink)
            ), contextlib.redirect_stderr(cast(TextIO, sink)):
                pdbqt_molecule = self._PDBQTMolecule(
                    pdbqt_text,
                    skip_typing=True,
                )
                created = self._RDKitMolCreate.from_pdbqt_mol(
                    pdbqt_molecule,
                    only_cluster_leads=False,
                    keep_flexres=False,
                )
            if len(created) != 1:
                raise ValueError("Meeko PDBQT export did not return one ligand")
            molecule = created[0]
            if molecule.GetNumConformers() != expected_pose_count:
                raise ValueError("Meeko conformer count differs from Vina receipt")
            poses = []
            for index in range(expected_pose_count):
                pose = self._Chem.Mol(molecule)
                conformer = self._Chem.Conformer(molecule.GetConformer(index))
                pose.RemoveAllConformers()
                identifier = pose.AddConformer(conformer, assignId=True)
                if identifier != 0 or pose.GetNumConformers() != 1:
                    raise ValueError("generated conformer ID was not normalized to zero")
                poses.append(pose)
            return self._evaluate_rdkit_poses(
                poses,
                receptor_pdb,
                reference_ligands_sdf,
            )
        except Exception as exc:
            raise PoseBustersGeneratedPoseCaseError(
                stage="pdbqt_reconstruction",
                error_code="generated_pose_reconstruction_failed",
                error_type=type(exc).__name__,
                error_message_sha256=_hash_bytes(_normalize_error(exc)),
                diagnostic_sha256=sink.sha256,
                diagnostic_size_bytes=sink.size_bytes,
            ) from exc

    def evaluate_prepared_coordinate_case(
        self,
        ligand_start_sdf: bytes,
        source_atom_to_prepared_atom: Sequence[int],
        pose_coordinates_angstrom: Sequence[Sequence[Sequence[float]]],
        receptor_pdb: bytes,
        reference_ligands_sdf: bytes,
    ) -> tuple[_RuntimePoseOutcome, ...]:
        sink = _DigestingTextSink()
        try:
            try:
                source_text = ligand_start_sdf.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ValueError("start ligand SDF must be UTF-8") from exc
            parts = source_text.split("$$$$")
            if len(parts) != 2 or parts[1].strip():
                raise ValueError("start ligand SDF must contain one record")
            with contextlib.redirect_stdout(
                cast(TextIO, sink)
            ), contextlib.redirect_stderr(cast(TextIO, sink)):
                molecule = self._Chem.MolFromMolBlock(
                    parts[0],
                    sanitize=True,
                    removeHs=False,
                    strictParsing=True,
                )
            if molecule is None:
                raise ValueError("RDKit could not parse the start ligand SDF")
            source_atom_count = int(molecule.GetNumAtoms())
            mapping = tuple(source_atom_to_prepared_atom)
            if (
                len(mapping) != source_atom_count
                or any(
                    isinstance(value, bool)
                    or not isinstance(value, int)
                    or value < 0
                    for value in mapping
                )
                or len(set(mapping)) != len(mapping)
            ):
                raise ValueError(
                    "source-to-prepared atom mapping is not a complete bijection"
                )
            pose_rows = tuple(pose_coordinates_angstrom)
            if not 1 <= len(pose_rows) <= 128:
                raise ValueError("prepared coordinate pose count is outside its bound")
            poses: list[Any] = []
            prepared_atom_count: int | None = None
            for pose_index, raw_coordinates in enumerate(pose_rows):
                coordinates = tuple(tuple(row) for row in raw_coordinates)
                if prepared_atom_count is None:
                    prepared_atom_count = len(coordinates)
                if (
                    len(coordinates) != prepared_atom_count
                    or prepared_atom_count != source_atom_count
                    or max(mapping) >= prepared_atom_count
                    or any(
                        len(row) != 3
                        or any(
                            isinstance(value, bool)
                            or not isinstance(value, Real)
                            or not math.isfinite(float(value))
                            for value in row
                        )
                        for row in coordinates
                    )
                ):
                    raise ValueError(
                        f"prepared pose {pose_index} coordinates are invalid"
                    )
                pose = self._Chem.Mol(molecule)
                pose.RemoveAllConformers()
                conformer = self._Chem.Conformer(source_atom_count)
                for source_index, prepared_index in enumerate(mapping):
                    x, y, z = coordinates[prepared_index]
                    conformer.SetAtomPosition(
                        source_index,
                        (float(x), float(y), float(z)),
                    )
                identifier = pose.AddConformer(conformer, assignId=True)
                if identifier != 0 or pose.GetNumConformers() != 1:
                    raise ValueError(
                        "prepared coordinate conformer ID was not normalized"
                    )
                poses.append(pose)
            return self._evaluate_rdkit_poses(
                poses,
                receptor_pdb,
                reference_ligands_sdf,
            )
        except PoseBustersGeneratedPoseCaseError:
            raise
        except Exception as exc:
            raise PoseBustersGeneratedPoseCaseError(
                stage="internal_coordinate_reconstruction",
                error_code="internal_pose_reconstruction_failed",
                error_type=type(exc).__name__,
                error_message_sha256=_hash_bytes(_normalize_error(exc)),
                diagnostic_sha256=sink.sha256,
                diagnostic_size_bytes=sink.size_bytes,
            ) from exc


def _selected_columns_from_configuration(configuration: dict[str, Any]) -> tuple[str, ...]:
    columns: list[str] = []
    modules = configuration.get("modules")
    if not isinstance(modules, list):
        raise PoseBustersGeneratedPoseEvaluationError(
            "PoseBusters redock configuration has no modules"
        )
    for module in modules:
        if not isinstance(module, dict):
            raise PoseBustersGeneratedPoseEvaluationError(
                "PoseBusters redock module is invalid"
            )
        suffix = str(module.get("rename_suffix", ""))
        renamed = module.get("rename_outputs", {})
        chosen = module.get("chosen_binary_test_output", [])
        if not isinstance(renamed, dict) or not isinstance(chosen, list):
            raise PoseBustersGeneratedPoseEvaluationError(
                "PoseBusters redock output mapping is invalid"
            )
        for value in chosen:
            name = str(renamed.get(value, f"{value}{suffix}"))
            columns.append(name.lower().replace(" ", "_"))
    return tuple(columns)


def _verify_posebusters_wheel(path: str | os.PathLike[str]) -> tuple[str, int]:
    wheel = Path(path)
    try:
        digest, size, _mode = _hash_regular_file(
            wheel,
            maximum_bytes=2 * 1024 * 1024,
        )
    except PoseBustersExternalPreparationError as exc:
        raise PoseBustersGeneratedPoseEvaluationError(
            "PoseBusters wheel is not a bounded regular file"
        ) from exc
    if (
        digest != POSEBUSTERS_GENERATED_POSE_WHEEL_SHA256
        or size != POSEBUSTERS_GENERATED_POSE_WHEEL_SIZE_BYTES
    ):
        raise PoseBustersGeneratedPoseEvaluationError(
            "PoseBusters wheel identity does not match the frozen artifact"
        )
    return digest, size


def _load_posebusters_runtime(
    scratch_root: Path,
    posebusters_wheel_path: str | os.PathLike[str],
) -> _PoseBustersRuntimeProtocol:
    wheel_sha, wheel_size = _verify_posebusters_wheel(posebusters_wheel_path)
    try:
        meeko = importlib.import_module("meeko")
        PDBQTMolecule = getattr(meeko, "PDBQTMolecule")
        RDKitMolCreate = getattr(meeko, "RDKitMolCreate")
        import numpy
        import pandas
        posebusters = importlib.import_module("posebusters")
        PoseBusters = getattr(posebusters, "PoseBusters")
        from rdkit import Chem
        import torch
        import yaml
    except (AttributeError, ImportError) as exc:
        raise PoseBustersGeneratedPoseEvaluationError(
            "generated-pose evaluation requires the pinned optional runtime"
        ) from exc
    for module, distribution in (
        (meeko, "meeko"),
        (numpy, "numpy"),
        (pandas, "pandas"),
        (posebusters, "posebusters"),
        (yaml, "pyyaml"),
    ):
        _require_import_owned_by_distribution(module, distribution)
    if getattr(posebusters, "__version__", "") != (
        POSEBUSTERS_GENERATED_POSE_VERSION
    ):
        raise PoseBustersGeneratedPoseEvaluationError(
            "PoseBusters module version is not pinned"
        )
    posebusters_file = getattr(posebusters, "__file__", None)
    if not isinstance(posebusters_file, str) or not posebusters_file:
        raise PoseBustersGeneratedPoseEvaluationError(
            "PoseBusters module source path is unavailable"
        )
    config_path = Path(posebusters_file).parent / "config" / "redock.yml"
    config_sha = _source_file_sha256(config_path)
    if config_sha != POSEBUSTERS_GENERATED_POSE_REDOCK_CONFIGURATION_SHA256:
        raise PoseBustersGeneratedPoseEvaluationError(
            "PoseBusters redock configuration bytes changed"
        )
    engine = PoseBusters(config="redock", max_workers=0)
    if _selected_columns_from_configuration(engine.config) != (
        POSEBUSTERS_GENERATED_POSE_SELECTED_COLUMNS
    ):
        raise PoseBustersGeneratedPoseEvaluationError(
            "PoseBusters selected output contract changed"
        )
    preparation_runtime = _runtime_identity(str(torch.__version__))
    dependencies = tuple(
        _dependency_payload(name, version)
        for name, version in sorted(
            POSEBUSTERS_GENERATED_POSE_DEPENDENCY_PINS.items()
        )
    )
    identity = PoseBustersGeneratedPoseRuntimeIdentity(
        preparation_runtime=preparation_runtime,
        additional_dependencies=dependencies,
        posebusters_wheel_sha256=wheel_sha,
        posebusters_wheel_size_bytes=wheel_size,
        redock_configuration_sha256=config_sha,
        posebusters_api_source_sha256=_source_file_sha256(
            PoseBusters.bust.__code__.co_filename
        ),
        meeko_export_source_sha256=_source_file_sha256(
            RDKitMolCreate.from_pdbqt_mol.__code__.co_filename
        ),
    )
    return _PoseBustersRuntime(
        PoseBusters=PoseBusters,
        PDBQTMolecule=PDBQTMolecule,
        RDKitMolCreate=RDKitMolCreate,
        Chem=Chem,
        numpy_module=numpy,
        pandas_module=pandas,
        identity=identity,
        scratch_root=scratch_root,
    )


@dataclass(frozen=True, slots=True)
class _VinaArtifactView:
    relative_path: str
    sha256: str
    size_bytes: int
    raw: dict[str, Any]


@dataclass(frozen=True, slots=True)
class _VinaCaseView:
    case_id: str
    status: str
    preparation_status: str
    pose_count: int
    energies_binary64_hex: tuple[tuple[str, ...], ...]
    artifact: _VinaArtifactView | None
    error_code: str


@dataclass(frozen=True, slots=True)
class _VinaReceiptView:
    receipt_sha256: str
    receipt_file_sha256: str
    artifact_set_sha256: str
    preparation_receipt_sha256: str
    preparation_receipt_file_sha256: str
    preparation_artifact_set_sha256: str
    preparation_runtime_identity_sha256: str
    case_rows: tuple[_VinaCaseView, ...]


def _load_vina_receipt(
    receipt_path: str | os.PathLike[str],
    artifact_root: str | os.PathLike[str],
    *,
    expected_receipt_sha256: str,
    expected_preparation_receipt_sha256: str,
    expected_preparation_receipt_file_sha256: str,
    expected_preparation_artifact_set_sha256: str,
) -> tuple[_VinaReceiptView, dict[str, bytes]]:
    expected_sha = _digest(expected_receipt_sha256, name="expected Vina receipt")
    source = _read_exact_regular_file(
        receipt_path,
        maximum_bytes=POSEBUSTERS_VINA_EXECUTION_MAX_RECEIPT_BYTES,
    )
    try:
        metadata = Path(receipt_path).stat(follow_symlinks=False)
    except OSError as exc:
        raise PoseBustersGeneratedPoseEvaluationError(
            "Vina receipt metadata is unavailable"
        ) from exc
    if stat.S_IMODE(metadata.st_mode) != 0o600:
        raise PoseBustersGeneratedPoseEvaluationError(
            "Vina receipt must remain mode 0600"
        )
    try:
        raw = json.loads(source)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PoseBustersGeneratedPoseEvaluationError(
            "Vina receipt is not canonical JSON"
        ) from exc
    if not isinstance(raw, dict) or source != _canonical_bytes(raw) + b"\n":
        raise PoseBustersGeneratedPoseEvaluationError(
            "Vina receipt bytes are not canonical"
        )
    receipt_sha = raw.get("receipt_sha256")
    payload = dict(raw)
    payload.pop("receipt_sha256", None)
    source_members = raw.get("implementation_source_members")
    engine_identity = raw.get("engine_identity")
    if (
        raw.get("schema_id") != POSEBUSTERS_VINA_EXECUTION_SCHEMA_ID
        or not isinstance(receipt_sha, str)
        or _canonical_sha256(payload) != receipt_sha
        or receipt_sha != expected_sha
        or raw.get("configuration_sha256")
        != POSEBUSTERS_VINA_EXECUTION_CONFIGURATION_SHA256
        or raw.get("preparation_receipt_sha256")
        != expected_preparation_receipt_sha256
        or raw.get("preparation_receipt_file_sha256")
        != expected_preparation_receipt_file_sha256
        or raw.get("preparation_artifact_set_sha256")
        != expected_preparation_artifact_set_sha256
        or raw.get("benchmark_executed") is not False
        or raw.get("claim_safe") is not False
        or not isinstance(source_members, dict)
        or source_members.get("vina_execution")
        != _source_file_sha256(
            Path(__file__).with_name("public_posebusters_vina_execution.py")
        )
        or not isinstance(engine_identity, dict)
        or _canonical_sha256(engine_identity) != raw.get("engine_identity_sha256")
        or engine_identity.get("engine_id") != "vina"
        or engine_identity.get("engine_version") != "1.2.7"
    ):
        raise PoseBustersGeneratedPoseEvaluationError(
            "Vina receipt contract or identity is invalid"
        )
    preparation_runtime_sha = engine_identity.get(
        "preparation_runtime_identity_sha256"
    )
    if not isinstance(preparation_runtime_sha, str):
        raise PoseBustersGeneratedPoseEvaluationError(
            "Vina preparation runtime identity is missing"
        )
    raw_rows = raw.get("case_rows")
    if (
        not isinstance(raw_rows, list)
        or not raw_rows
        or raw.get("all_case_denominator") != len(raw_rows)
    ):
        raise PoseBustersGeneratedPoseEvaluationError(
            "Vina case denominator is invalid"
        )
    rows: list[_VinaCaseView] = []
    payloads: dict[str, bytes] = {}
    artifact_projection: dict[str, dict[str, Any]] = {}
    for raw_row in raw_rows:
        if not isinstance(raw_row, dict):
            raise PoseBustersGeneratedPoseEvaluationError(
                "Vina case row must be an object"
            )
        case = _case_id(raw_row.get("case_id"))
        status = str(raw_row.get("status", ""))
        preparation_status = str(raw_row.get("preparation_status", ""))
        if status not in _VINA_CASE_STATUSES:
            raise PoseBustersGeneratedPoseEvaluationError(
                "Vina case status is invalid"
            )
        pose_count = _positive_int(
            raw_row.get("pose_count"),
            name="Vina pose count",
            allow_zero=True,
        )
        raw_energies = raw_row.get("energies_binary64_hex")
        if not isinstance(raw_energies, list):
            raise PoseBustersGeneratedPoseEvaluationError(
                "Vina energy rows are invalid"
            )
        energies = tuple(
            tuple(
                _validate_hex(value, name="Vina energy component")
                for value in energy_row
            )
            for energy_row in raw_energies
            if isinstance(energy_row, list)
        )
        if len(energies) != len(raw_energies) or any(
            len(row) != _VINA_ENERGY_COMPONENT_COUNT for row in energies
        ):
            raise PoseBustersGeneratedPoseEvaluationError(
                "Vina energy component rows are invalid"
            )
        raw_artifact = raw_row.get("pose_artifact")
        artifact: _VinaArtifactView | None = None
        if raw_artifact is not None:
            if (
                not isinstance(raw_artifact, dict)
                or raw_artifact.get("schema_id")
                != POSEBUSTERS_VINA_EXECUTION_ARTIFACT_SCHEMA_ID
                or raw_artifact.get("role") != "vina_generated_poses_pdbqt"
            ):
                raise PoseBustersGeneratedPoseEvaluationError(
                    "Vina pose artifact schema is invalid"
                )
            relative = _relative_path(raw_artifact.get("relative_path"))
            if PurePosixPath(relative).parts[0] != case:
                raise PoseBustersGeneratedPoseEvaluationError(
                    "Vina pose artifact path is cross-wired"
                )
            digest = _digest(raw_artifact.get("sha256"), name="Vina pose artifact")
            size = _positive_int(
                raw_artifact.get("size_bytes"),
                name="Vina pose artifact size",
            )
            if size > POSEBUSTERS_VINA_EXECUTION_MAX_POSE_ARTIFACT_BYTES:
                raise PoseBustersGeneratedPoseEvaluationError(
                    "Vina pose artifact exceeds its bound"
                )
            observed = _read_exact_regular_file(
                Path(artifact_root) / relative,
                maximum_bytes=POSEBUSTERS_VINA_EXECUTION_MAX_POSE_ARTIFACT_BYTES,
            )
            if len(observed) != size or _hash_bytes(observed) != digest:
                raise PoseBustersGeneratedPoseEvaluationError(
                    "Vina pose artifact does not match its receipt"
                )
            if relative in payloads:
                raise PoseBustersGeneratedPoseEvaluationError(
                    "Vina pose artifact path is duplicated"
                )
            payloads[relative] = observed
            artifact_projection[case] = dict(raw_artifact)
            artifact = _VinaArtifactView(
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
            valid = valid and pose_count > 0 and len(energies) == pose_count and artifact is not None
        else:
            valid = valid and pose_count == 0 and not energies and artifact is None
        if not valid:
            raise PoseBustersGeneratedPoseEvaluationError(
                "Vina case row disposition is inconsistent"
            )
        error_code = raw_row.get("error_code")
        if not isinstance(error_code, str):
            raise PoseBustersGeneratedPoseEvaluationError(
                "Vina case error code must be text"
            )
        rows.append(
            _VinaCaseView(
                case_id=case,
                status=status,
                preparation_status=preparation_status,
                pose_count=pose_count,
                energies_binary64_hex=energies,
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
        or _canonical_sha256(artifact_projection)
        != raw.get("artifact_set_sha256")
    ):
        raise PoseBustersGeneratedPoseEvaluationError(
            "Vina rows or artifact-set identity are inconsistent"
        )
    try:
        _verify_artifact_tree(Path(artifact_root), payloads)
    except PoseBustersExternalPreparationError as exc:
        raise PoseBustersGeneratedPoseEvaluationError(
            "Vina pose artifact tree failed exact verification"
        ) from exc
    return (
        _VinaReceiptView(
            receipt_sha256=receipt_sha,
            receipt_file_sha256=_hash_bytes(source),
            artifact_set_sha256=_digest(
                raw.get("artifact_set_sha256"),
                name="Vina artifact set",
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
                name="Vina preparation runtime identity",
            ),
            case_rows=rows_tuple,
        ),
        payloads,
    )


@dataclass(frozen=True, slots=True)
class PoseBustersGeneratedPoseCase:
    case_id: str
    status: str
    disposition_code: str
    vina_status: str
    vina_error_code: str
    vina_pose_count: int
    pose_results: tuple[PoseBustersGeneratedPoseResult, ...] = ()
    error_stage: str = ""
    error_code: str = ""
    error_type: str = ""
    error_message_sha256: str = ""
    diagnostic_sha256: str = ""
    diagnostic_size_bytes: int = 0
    schema_id: str = POSEBUSTERS_GENERATED_POSE_CASE_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_GENERATED_POSE_CASE_SCHEMA_ID:
            raise PoseBustersGeneratedPoseEvaluationError(
                "unsupported generated-pose case schema"
            )
        case = _case_id(self.case_id)
        if self.status not in _CASE_STATUSES or self.vina_status not in _VINA_CASE_STATUSES:
            raise PoseBustersGeneratedPoseEvaluationError(
                "generated-pose case status is invalid"
            )
        disposition = _token(
            self.disposition_code,
            name="generated-pose case disposition",
        )
        pose_count = _positive_int(
            self.vina_pose_count,
            name="generated-pose case Vina pose count",
            allow_zero=True,
        )
        poses = tuple(self.pose_results)
        if tuple(row.pose_rank for row in poses) != tuple(range(1, len(poses) + 1)):
            raise PoseBustersGeneratedPoseEvaluationError(
                "generated-pose case ranks are not contiguous"
            )
        diagnostics = _positive_int(
            self.diagnostic_size_bytes,
            name="generated-pose case diagnostic size",
            allow_zero=True,
        )
        if self.vina_status == "success":
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
                and not self.vina_error_code
            )
        else:
            expected_status = {
                "engine_failure": "blocked_vina_engine_failure",
                "blocked_preparation_failure": "blocked_preparation_failure",
                "blocked_upstream_failure": "blocked_upstream_failure",
                "abstain_chemistry_scope": "abstain_chemistry_scope",
            }[self.vina_status]
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
            raise PoseBustersGeneratedPoseEvaluationError(
                "generated-pose case disposition is inconsistent"
            )
        if self.error_stage:
            object.__setattr__(
                self,
                "error_stage",
                _token(self.error_stage, name="generated-pose case error stage"),
            )
            object.__setattr__(
                self,
                "error_code",
                _token(self.error_code, name="generated-pose case error code"),
            )
            object.__setattr__(
                self,
                "error_type",
                _identifier(self.error_type, name="generated-pose case error type"),
            )
            object.__setattr__(
                self,
                "error_message_sha256",
                _digest(
                    self.error_message_sha256,
                    name="generated-pose case error message",
                ),
            )
            object.__setattr__(
                self,
                "diagnostic_sha256",
                _digest(
                    self.diagnostic_sha256,
                    name="generated-pose case diagnostic",
                ),
            )
        object.__setattr__(self, "case_id", case)
        object.__setattr__(self, "disposition_code", disposition)
        object.__setattr__(self, "vina_pose_count", pose_count)
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
        return bool(self.pose_results and self.pose_results[0].rmsd_within_2_angstrom)

    @property
    def top_5_rmsd_hit(self) -> bool:
        return any(row.rmsd_within_2_angstrom for row in self.pose_results[:5])

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

    @property
    def top_1_rmsd_binary64_hex(self) -> str:
        return self._best_rmsd(1)

    @property
    def top_5_best_rmsd_binary64_hex(self) -> str:
        return self._best_rmsd(5)

    @property
    def all_modes_best_rmsd_binary64_hex(self) -> str:
        return self._best_rmsd(None)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "case_id": self.case_id,
            "status": self.status,
            "disposition_code": self.disposition_code,
            "vina_status": self.vina_status,
            "vina_error_code": self.vina_error_code,
            "vina_pose_count": self.vina_pose_count,
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
            "top_1_direct_rmsd_angstrom_binary64_hex": (
                self.top_1_rmsd_binary64_hex
            ),
            "top_5_best_direct_rmsd_angstrom_binary64_hex": (
                self.top_5_best_rmsd_binary64_hex
            ),
            "all_modes_best_direct_rmsd_angstrom_binary64_hex": (
                self.all_modes_best_rmsd_binary64_hex
            ),
            "pose_results": [row.to_dict() for row in self.pose_results],
            "error_stage": self.error_stage,
            "error_code": self.error_code,
            "error_type": self.error_type,
            "error_message_sha256": self.error_message_sha256,
            "diagnostic_sha256": self.diagnostic_sha256,
            "diagnostic_size_bytes": self.diagnostic_size_bytes,
        }


@dataclass(frozen=True, slots=True)
class PoseBustersGeneratedPoseMetric:
    metric_id: str
    denominator_scope: str
    numerator: int
    denominator: int
    estimate: float | None
    confidence_interval_low: float | None
    confidence_interval_high: float | None
    schema_id: str = POSEBUSTERS_GENERATED_POSE_METRIC_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_GENERATED_POSE_METRIC_SCHEMA_ID:
            raise PoseBustersGeneratedPoseEvaluationError(
                "unsupported generated-pose metric schema"
            )
        metric = _token(self.metric_id, name="generated-pose metric ID")
        scope = _token(self.denominator_scope, name="generated-pose metric scope")
        numerator = _positive_int(
            self.numerator,
            name="generated-pose metric numerator",
            allow_zero=True,
        )
        denominator = _positive_int(
            self.denominator,
            name="generated-pose metric denominator",
            allow_zero=True,
        )
        if numerator > denominator:
            raise PoseBustersGeneratedPoseEvaluationError(
                "generated-pose metric numerator exceeds denominator"
            )
        if denominator == 0:
            valid = (
                numerator == 0
                and self.estimate is None
                and self.confidence_interval_low is None
                and self.confidence_interval_high is None
            )
        else:
            values = (
                self.estimate,
                self.confidence_interval_low,
                self.confidence_interval_high,
            )
            valid = all(
                isinstance(value, float)
                and math.isfinite(value)
                and 0.0 <= value <= 1.0
                for value in values
            )
            if valid:
                estimate, low, high = cast(tuple[float, float, float], values)
                valid = (
                    low <= estimate <= high
                    and math.isclose(
                        estimate,
                        numerator / denominator,
                        abs_tol=1.0e-15,
                    )
                )
        if not valid:
            raise PoseBustersGeneratedPoseEvaluationError(
                "generated-pose metric is inconsistent"
            )
        object.__setattr__(self, "metric_id", metric)
        object.__setattr__(self, "denominator_scope", scope)
        object.__setattr__(self, "numerator", numerator)
        object.__setattr__(self, "denominator", denominator)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "metric_id": self.metric_id,
            "denominator_scope": self.denominator_scope,
            "numerator": self.numerator,
            "denominator": self.denominator,
            "estimate": self.estimate,
            "evaluable": self.denominator > 0,
            "confidence_level": POSEBUSTERS_GENERATED_POSE_CONFIDENCE_LEVEL,
            "confidence_interval_method": "wilson_score_binomial",
            "confidence_interval_low": self.confidence_interval_low,
            "confidence_interval_high": self.confidence_interval_high,
        }


def _metric(
    metric_id: str,
    scope: str,
    numerator: int,
    denominator: int,
) -> PoseBustersGeneratedPoseMetric:
    if denominator == 0:
        return PoseBustersGeneratedPoseMetric(
            metric_id=metric_id,
            denominator_scope=scope,
            numerator=numerator,
            denominator=denominator,
            estimate=None,
            confidence_interval_low=None,
            confidence_interval_high=None,
        )
    proportion = numerator / denominator
    z2 = POSEBUSTERS_GENERATED_POSE_Z**2
    scale = 1.0 + z2 / denominator
    center = (proportion + z2 / (2.0 * denominator)) / scale
    radius = (
        POSEBUSTERS_GENERATED_POSE_Z
        * math.sqrt(
            proportion * (1.0 - proportion) / denominator
            + z2 / (4.0 * denominator**2)
        )
        / scale
    )
    return PoseBustersGeneratedPoseMetric(
        metric_id=metric_id,
        denominator_scope=scope,
        numerator=numerator,
        denominator=denominator,
        estimate=proportion,
        confidence_interval_low=min(proportion, max(0.0, center - radius)),
        confidence_interval_high=max(proportion, min(1.0, center + radius)),
    )


def _summary_metrics(
    rows: Sequence[PoseBustersGeneratedPoseCase],
) -> tuple[PoseBustersGeneratedPoseMetric, ...]:
    all_case = tuple(rows)
    vina_success = tuple(row for row in rows if row.vina_status == "success")
    poses = tuple(pose for row in vina_success for pose in row.pose_results)
    case_predicates = (
        ("vina_generated_pose_case_rate", lambda row: row.vina_status == "success"),
        ("posebusters_complete_case_evaluation_rate", lambda row: row.evaluation_complete),
        (
            "posebusters_case_evaluation_failure_rate",
            lambda row: row.status in {"partial_evaluation", "evaluation_failure"},
        ),
        ("case_with_any_physically_valid_pose_rate", lambda row: row.has_any_valid_pose),
        ("top_1_physically_valid_pose_rate", lambda row: row.top_1_valid),
        ("top_5_physically_valid_pose_rate", lambda row: row.top_5_valid),
        ("top_1_rmsd_le_2_angstrom_rate", lambda row: row.top_1_rmsd_hit),
        ("top_5_rmsd_le_2_angstrom_rate", lambda row: row.top_5_rmsd_hit),
        ("all_modes_rmsd_le_2_angstrom_rate", lambda row: row.all_modes_rmsd_hit),
        (
            "top_1_valid_and_rmsd_le_2_angstrom_rate",
            lambda row: row.top_1_valid_rmsd_hit,
        ),
        (
            "top_5_valid_and_rmsd_le_2_angstrom_rate",
            lambda row: row.top_5_valid_rmsd_hit,
        ),
    )
    conditional_predicates = (
        ("top_1_physically_valid_pose_rate", lambda row: row.top_1_valid),
        ("top_5_physically_valid_pose_rate", lambda row: row.top_5_valid),
        ("top_1_rmsd_le_2_angstrom_rate", lambda row: row.top_1_rmsd_hit),
        ("top_5_rmsd_le_2_angstrom_rate", lambda row: row.top_5_rmsd_hit),
        ("all_modes_rmsd_le_2_angstrom_rate", lambda row: row.all_modes_rmsd_hit),
        (
            "top_1_valid_and_rmsd_le_2_angstrom_rate",
            lambda row: row.top_1_valid_rmsd_hit,
        ),
        (
            "top_5_valid_and_rmsd_le_2_angstrom_rate",
            lambda row: row.top_5_valid_rmsd_hit,
        ),
    )
    pose_predicates = (
        ("pose_evaluation_success_rate", lambda row: row.status == "evaluated"),
        (
            "physically_valid_pose_rate",
            lambda row: row.all_non_rmsd_binary_tests_pass,
        ),
        ("rmsd_evaluated_pose_rate", lambda row: row.rmsd_evaluated),
        ("rmsd_le_2_angstrom_pose_rate", lambda row: row.rmsd_within_2_angstrom),
        (
            "valid_and_rmsd_le_2_angstrom_pose_rate",
            lambda row: row.valid_and_rmsd_within_2_angstrom,
        ),
    )
    metrics = [
        _metric(name, "all_cases", sum(bool(fn(row)) for row in all_case), len(all_case))
        for name, fn in case_predicates
    ]
    metrics.extend(
        _metric(
            name,
            "vina_success_cases",
            sum(bool(fn(row)) for row in vina_success),
            len(vina_success),
        )
        for name, fn in conditional_predicates
    )
    metrics.extend(
        _metric(
            name,
            "generated_poses",
            sum(bool(fn(row)) for row in poses),
            len(poses),
        )
        for name, fn in pose_predicates
    )
    return tuple(metrics)


@dataclass(frozen=True, slots=True)
class PoseBustersGeneratedPoseEvaluationReceipt:
    archive_intake_receipt_sha256: str
    corpus_audit_receipt_sha256: str
    preparation_receipt_sha256: str
    preparation_receipt_file_sha256: str
    preparation_artifact_set_sha256: str
    vina_receipt_sha256: str
    vina_receipt_file_sha256: str
    vina_artifact_set_sha256: str
    implementation_source_sha256: str
    implementation_source_members: tuple[tuple[str, str], ...]
    runtime_identity: PoseBustersGeneratedPoseRuntimeIdentity
    configuration_sha256: str
    case_rows: tuple[PoseBustersGeneratedPoseCase, ...]
    metrics: tuple[PoseBustersGeneratedPoseMetric, ...]
    schema_id: str = POSEBUSTERS_GENERATED_POSE_EVALUATION_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_GENERATED_POSE_EVALUATION_SCHEMA_ID:
            raise PoseBustersGeneratedPoseEvaluationError(
                "unsupported generated-pose evaluation schema"
            )
        for name in (
            "archive_intake_receipt_sha256",
            "corpus_audit_receipt_sha256",
            "preparation_receipt_sha256",
            "preparation_receipt_file_sha256",
            "preparation_artifact_set_sha256",
            "vina_receipt_sha256",
            "vina_receipt_file_sha256",
            "vina_artifact_set_sha256",
            "implementation_source_sha256",
            "configuration_sha256",
        ):
            object.__setattr__(
                self,
                name,
                _digest(getattr(self, name), name=name),
            )
        if self.configuration_sha256 != (
            POSEBUSTERS_GENERATED_POSE_CONFIGURATION_SHA256
        ):
            raise PoseBustersGeneratedPoseEvaluationError(
                "generated-pose evaluation configuration identity changed"
            )
        members = tuple(
            (
                _token(role, name="generated-pose implementation role"),
                _digest(digest, name=f"{role} implementation source"),
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
            raise PoseBustersGeneratedPoseEvaluationError(
                "generated-pose implementation-source identity is invalid"
            )
        if not isinstance(
            self.runtime_identity,
            PoseBustersGeneratedPoseRuntimeIdentity,
        ):
            raise PoseBustersGeneratedPoseEvaluationError(
                "generated-pose runtime identity is missing"
            )
        rows = tuple(self.case_rows)
        if (
            not rows
            or tuple(row.case_id for row in rows)
            != tuple(sorted(row.case_id for row in rows))
            or len({row.case_id for row in rows}) != len(rows)
        ):
            raise PoseBustersGeneratedPoseEvaluationError(
                "generated-pose case rows must be canonical and unique"
            )
        metrics = _summary_metrics(rows)
        if tuple(row.to_dict() for row in self.metrics) != tuple(
            row.to_dict() for row in metrics
        ):
            raise PoseBustersGeneratedPoseEvaluationError(
                "generated-pose summary metrics do not match case rows"
            )
        object.__setattr__(self, "implementation_source_members", members)
        object.__setattr__(self, "case_rows", rows)
        object.__setattr__(self, "metrics", metrics)

    @property
    def generated_pose_count(self) -> int:
        return sum(row.vina_pose_count for row in self.case_rows)

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
            "archive_intake_receipt_sha256": self.archive_intake_receipt_sha256,
            "corpus_audit_receipt_sha256": self.corpus_audit_receipt_sha256,
            "preparation_receipt_sha256": self.preparation_receipt_sha256,
            "preparation_receipt_file_sha256": (
                self.preparation_receipt_file_sha256
            ),
            "preparation_artifact_set_sha256": (
                self.preparation_artifact_set_sha256
            ),
            "vina_receipt_sha256": self.vina_receipt_sha256,
            "vina_receipt_file_sha256": self.vina_receipt_file_sha256,
            "vina_artifact_set_sha256": self.vina_artifact_set_sha256,
            "implementation_source_sha256": self.implementation_source_sha256,
            "implementation_source_members": dict(
                self.implementation_source_members
            ),
            "runtime_identity": self.runtime_identity.to_dict(),
            "runtime_identity_sha256": self.runtime_identity.fingerprint_sha256,
            "configuration": POSEBUSTERS_GENERATED_POSE_CONFIGURATION,
            "configuration_sha256": self.configuration_sha256,
            "all_case_denominator": len(self.case_rows),
            "generated_pose_count": self.generated_pose_count,
            "evaluated_pose_count": self.evaluated_pose_count,
            "physically_valid_pose_count": self.physically_valid_pose_count,
            "case_rows": [row.to_dict() for row in self.case_rows],
            "metrics": [row.to_dict() for row in self.metrics],
            "pose_generation_performed_by_this_runner": False,
            "posebusters_redock_oracle_executed": self.evaluated_pose_count > 0,
            "generated_pose_validity_evaluated": self.evaluated_pose_count > 0,
            "symmetry_aware_direct_rmsd_evaluated": any(
                pose.rmsd_evaluated
                for row in self.case_rows
                for pose in row.pose_results
            ),
            "gnina_same_input_execution_performed": False,
            "smina_same_input_execution_performed": False,
            "target_family_metrics_present": False,
            "leakage_receipt_present": False,
            "independent_external_rerun_present": False,
            "benchmark_executed": False,
            "scientific_blockers": list(POSEBUSTERS_GENERATED_POSE_BLOCKERS),
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
        if len(payload) > POSEBUSTERS_GENERATED_POSE_MAX_RECEIPT_BYTES:
            raise PoseBustersGeneratedPoseEvaluationError(
                "generated-pose receipt exceeds its byte bound"
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
                raise PoseBustersGeneratedPoseEvaluationError(
                    "generated-pose evaluation output already exists"
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
                "generated_pose_evaluation": _source_file_sha256(__file__),
                "posebusters_external_preparation_contract": _source_file_sha256(
                    Path(__file__).with_name(
                        "public_posebusters_external_preparation.py"
                    )
                ),
                "vina_execution_contract": _source_file_sha256(
                    Path(__file__).with_name(
                        "public_posebusters_vina_execution.py"
                    )
                ),
            }.items()
        )
    )


def _blocked_case(vina: _VinaCaseView) -> PoseBustersGeneratedPoseCase:
    status = {
        "engine_failure": "blocked_vina_engine_failure",
        "blocked_preparation_failure": "blocked_preparation_failure",
        "blocked_upstream_failure": "blocked_upstream_failure",
        "abstain_chemistry_scope": "abstain_chemistry_scope",
    }[vina.status]
    disposition = {
        "engine_failure": "blocked_by_vina_engine_failure",
        "blocked_preparation_failure": "blocked_by_strict_preparation_failure",
        "blocked_upstream_failure": "blocked_by_upstream_input_failure",
        "abstain_chemistry_scope": "chemistry_scope_abstention",
    }[vina.status]
    return PoseBustersGeneratedPoseCase(
        case_id=vina.case_id,
        status=status,
        disposition_code=disposition,
        vina_status=vina.status,
        vina_error_code=vina.error_code,
        vina_pose_count=0,
    )


def _failure_pose(
    rank: int,
    energy: tuple[str, ...],
    error: PoseBustersGeneratedPoseCaseError,
) -> PoseBustersGeneratedPoseResult:
    return PoseBustersGeneratedPoseResult(
        pose_rank=rank,
        status="evaluation_failure",
        vina_energy_components_binary64_hex=energy,
        error_stage=error.stage,
        error_code=error.error_code,
        error_type=error.error_type,
        error_message_sha256=error.error_message_sha256,
        diagnostic_sha256=error.diagnostic_sha256,
        diagnostic_size_bytes=error.diagnostic_size_bytes,
    )


def _evaluate_case(
    vina: _VinaCaseView,
    poses_pdbqt: bytes,
    receptor_pdb: bytes,
    reference_ligands_sdf: bytes,
    runtime: _PoseBustersRuntimeProtocol,
) -> PoseBustersGeneratedPoseCase:
    if vina.status != "success" or vina.artifact is None:
        return _blocked_case(vina)
    case_error: PoseBustersGeneratedPoseCaseError | None = None
    try:
        outcomes = runtime.evaluate_case(
            poses_pdbqt,
            receptor_pdb,
            reference_ligands_sdf,
            vina.pose_count,
        )
        if len(outcomes) != vina.pose_count:
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
            _failure_pose(rank, energy, case_error)
            for rank, energy in enumerate(vina.energies_binary64_hex, start=1)
        )
        return PoseBustersGeneratedPoseCase(
            case_id=vina.case_id,
            status="evaluation_failure",
            disposition_code=case_error.error_code,
            vina_status=vina.status,
            vina_error_code="",
            vina_pose_count=vina.pose_count,
            pose_results=pose_results,
            error_stage=case_error.stage,
            error_code=case_error.error_code,
            error_type=case_error.error_type,
            error_message_sha256=case_error.error_message_sha256,
            diagnostic_sha256=case_error.diagnostic_sha256,
            diagnostic_size_bytes=case_error.diagnostic_size_bytes,
        )
    pose_results = tuple(
        PoseBustersGeneratedPoseResult(
            pose_rank=rank,
            status=outcome.status,
            vina_energy_components_binary64_hex=energy,
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
        for rank, (outcome, energy) in enumerate(
            zip(outcomes, vina.energies_binary64_hex),
            start=1,
        )
    )
    evaluated = sum(row.status == "evaluated" for row in pose_results)
    status = (
        "evaluated"
        if evaluated == vina.pose_count
        else "evaluation_failure"
        if evaluated == 0
        else "partial_evaluation"
    )
    return PoseBustersGeneratedPoseCase(
        case_id=vina.case_id,
        status=status,
        disposition_code=(
            "posebusters_redock_evaluation_complete"
            if status == "evaluated"
            else "posebusters_redock_pose_failures_retained"
        ),
        vina_status=vina.status,
        vina_error_code="",
        vina_pose_count=vina.pose_count,
        pose_results=pose_results,
    )


def _read_archive_sources(
    archive: zipfile.ZipFile,
    intake_row: Any,
) -> tuple[bytes, bytes]:
    artifacts = {row.role: row for row in intake_row.artifacts}
    sources: list[bytes] = []
    for role in ("receptor_pdb", "reference_ligands_sdf"):
        artifact = artifacts[role]
        try:
            info = archive.getinfo(artifact.member_path)
            source = archive.read(info)
        except (KeyError, OSError, RuntimeError, zipfile.BadZipFile) as exc:
            raise PoseBustersGeneratedPoseEvaluationError(
                f"PoseBusters archive member could not be read: {role}"
            ) from exc
        if len(source) != artifact.size_bytes or _hash_bytes(source) != artifact.sha256:
            raise PoseBustersGeneratedPoseEvaluationError(
                f"PoseBusters archive member changed after intake verification: {role}"
            )
        sources.append(source)
    return sources[0], sources[1]


def _build_evaluation(
    archive_path: str | os.PathLike[str],
    selection_path: str | os.PathLike[str],
    intake_receipt_path: str | os.PathLike[str],
    corpus_audit_receipt_path: str | os.PathLike[str],
    preparation_receipt_path: str | os.PathLike[str],
    preparation_artifact_root: str | os.PathLike[str],
    vina_receipt_path: str | os.PathLike[str],
    vina_artifact_root: str | os.PathLike[str],
    posebusters_wheel_path: str | os.PathLike[str],
    scratch_root: str | os.PathLike[str],
    *,
    expected_preparation_receipt_sha256: str,
    expected_vina_receipt_sha256: str,
    contract: PoseBustersArchiveContract,
) -> PoseBustersGeneratedPoseEvaluationReceipt:
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
        raise PoseBustersGeneratedPoseEvaluationError(
            "generated-pose evaluation source chain did not verify"
        ) from exc
    expected_preparation_sha = _digest(
        expected_preparation_receipt_sha256,
        name="expected preparation receipt",
    )
    if preparation.fingerprint_sha256 != expected_preparation_sha:
        raise PoseBustersGeneratedPoseEvaluationError(
            "verified preparation receipt differs from caller pin"
        )
    preparation_source = _read_exact_regular_file(
        preparation_receipt_path,
        maximum_bytes=POSEBUSTERS_ARCHIVE_MAX_RECEIPT_BYTES,
    )
    vina, vina_payloads = _load_vina_receipt(
        vina_receipt_path,
        vina_artifact_root,
        expected_receipt_sha256=expected_vina_receipt_sha256,
        expected_preparation_receipt_sha256=preparation.fingerprint_sha256,
        expected_preparation_receipt_file_sha256=_hash_bytes(preparation_source),
        expected_preparation_artifact_set_sha256=preparation.artifact_set_sha256,
    )
    if tuple(row.case_id for row in intake.case_rows) != tuple(
        row.case_id for row in vina.case_rows
    ) or tuple(row.case_id for row in preparation.case_rows) != tuple(
        row.case_id for row in vina.case_rows
    ):
        raise PoseBustersGeneratedPoseEvaluationError(
            "source-chain case identities disagree"
        )
    runtime = _load_posebusters_runtime(
        Path(scratch_root),
        posebusters_wheel_path,
    )
    if (
        runtime.identity.preparation_runtime.to_dict()
        != preparation.runtime_identity.to_dict()
        or runtime.identity.preparation_runtime.fingerprint_sha256
        != vina.preparation_runtime_identity_sha256
    ):
        raise PoseBustersGeneratedPoseEvaluationError(
            "PoseBusters runtime differs from preparation/Vina runtime"
        )
    if (
        _canonical_sha256(POSEBUSTERS_GENERATED_POSE_CONFIGURATION)
        != POSEBUSTERS_GENERATED_POSE_CONFIGURATION_SHA256
    ):
        raise PoseBustersGeneratedPoseEvaluationError(
            "generated-pose frozen configuration was mutated"
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
            raise PoseBustersGeneratedPoseEvaluationError(
                "PoseBusters archive changed after source-chain verification"
            )
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            with zipfile.ZipFile(handle, "r") as archive:
                for vina_row in vina.case_rows:
                    if vina_row.status == "success":
                        source_payloads[vina_row.case_id] = _read_archive_sources(
                            archive,
                            intake_rows[vina_row.case_id],
                        )
    except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
        raise PoseBustersGeneratedPoseEvaluationError(
            "PoseBusters archive failed bounded evaluation access"
        ) from exc
    finally:
        os.close(descriptor)
    rows: list[PoseBustersGeneratedPoseCase] = []
    for vina_row in vina.case_rows:
        if vina_row.status == "success":
            assert vina_row.artifact is not None
            receptor, native = source_payloads[vina_row.case_id]
            rows.append(
                _evaluate_case(
                    vina_row,
                    vina_payloads[vina_row.artifact.relative_path],
                    receptor,
                    native,
                    runtime,
                )
            )
        else:
            rows.append(_blocked_case(vina_row))
    rows_tuple = tuple(rows)
    source_members = _implementation_source_members()
    corpus_source = _read_exact_regular_file(
        corpus_audit_receipt_path,
        maximum_bytes=POSEBUSTERS_GENERATED_POSE_MAX_RECEIPT_BYTES,
    )
    try:
        corpus_raw = json.loads(corpus_source)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PoseBustersGeneratedPoseEvaluationError(
            "corpus receipt is not JSON"
        ) from exc
    corpus_sha = corpus_raw.get("receipt_sha256") if isinstance(corpus_raw, dict) else None
    if (
        not isinstance(corpus_sha, str)
        or corpus_sha != preparation.corpus_audit_receipt_sha256
    ):
        raise PoseBustersGeneratedPoseEvaluationError(
            "corpus receipt fingerprint is missing or cross-wired"
        )
    return PoseBustersGeneratedPoseEvaluationReceipt(
        archive_intake_receipt_sha256=intake.fingerprint_sha256,
        corpus_audit_receipt_sha256=corpus_sha,
        preparation_receipt_sha256=preparation.fingerprint_sha256,
        preparation_receipt_file_sha256=_hash_bytes(preparation_source),
        preparation_artifact_set_sha256=preparation.artifact_set_sha256,
        vina_receipt_sha256=vina.receipt_sha256,
        vina_receipt_file_sha256=vina.receipt_file_sha256,
        vina_artifact_set_sha256=vina.artifact_set_sha256,
        implementation_source_sha256=_canonical_sha256(dict(source_members)),
        implementation_source_members=source_members,
        runtime_identity=runtime.identity,
        configuration_sha256=POSEBUSTERS_GENERATED_POSE_CONFIGURATION_SHA256,
        case_rows=rows_tuple,
        metrics=_summary_metrics(rows_tuple),
    )


def materialize_posebusters_generated_pose_evaluation(
    archive_path: str | os.PathLike[str],
    selection_path: str | os.PathLike[str],
    intake_receipt_path: str | os.PathLike[str],
    corpus_audit_receipt_path: str | os.PathLike[str],
    preparation_receipt_path: str | os.PathLike[str],
    preparation_artifact_root: str | os.PathLike[str],
    vina_receipt_path: str | os.PathLike[str],
    vina_artifact_root: str | os.PathLike[str],
    posebusters_wheel_path: str | os.PathLike[str],
    scratch_root: str | os.PathLike[str],
    *,
    expected_preparation_receipt_sha256: str,
    expected_vina_receipt_sha256: str,
    contract: PoseBustersArchiveContract = OFFICIAL_POSEBUSTERS_ARCHIVE_CONTRACT,
) -> PoseBustersGeneratedPoseEvaluationReceipt:
    """Evaluate every generated Vina pose and retain all case dispositions."""

    return _build_evaluation(
        archive_path,
        selection_path,
        intake_receipt_path,
        corpus_audit_receipt_path,
        preparation_receipt_path,
        preparation_artifact_root,
        vina_receipt_path,
        vina_artifact_root,
        posebusters_wheel_path,
        scratch_root,
        expected_preparation_receipt_sha256=(
            expected_preparation_receipt_sha256
        ),
        expected_vina_receipt_sha256=expected_vina_receipt_sha256,
        contract=contract,
    )


def verify_posebusters_generated_pose_evaluation_receipt(
    evaluation_receipt_path: str | os.PathLike[str],
    archive_path: str | os.PathLike[str],
    selection_path: str | os.PathLike[str],
    intake_receipt_path: str | os.PathLike[str],
    corpus_audit_receipt_path: str | os.PathLike[str],
    preparation_receipt_path: str | os.PathLike[str],
    preparation_artifact_root: str | os.PathLike[str],
    vina_receipt_path: str | os.PathLike[str],
    vina_artifact_root: str | os.PathLike[str],
    posebusters_wheel_path: str | os.PathLike[str],
    scratch_root: str | os.PathLike[str],
    *,
    expected_preparation_receipt_sha256: str,
    expected_vina_receipt_sha256: str,
    contract: PoseBustersArchiveContract = OFFICIAL_POSEBUSTERS_ARCHIVE_CONTRACT,
) -> PoseBustersGeneratedPoseEvaluationReceipt:
    """Require byte-exact PoseBusters reexecution and receipt equality."""

    source = _read_exact_regular_file(
        evaluation_receipt_path,
        maximum_bytes=POSEBUSTERS_GENERATED_POSE_MAX_RECEIPT_BYTES,
    )
    expected = _build_evaluation(
        archive_path,
        selection_path,
        intake_receipt_path,
        corpus_audit_receipt_path,
        preparation_receipt_path,
        preparation_artifact_root,
        vina_receipt_path,
        vina_artifact_root,
        posebusters_wheel_path,
        scratch_root,
        expected_preparation_receipt_sha256=(
            expected_preparation_receipt_sha256
        ),
        expected_vina_receipt_sha256=expected_vina_receipt_sha256,
        contract=contract,
    )
    if source != _canonical_bytes(expected.to_dict()) + b"\n":
        raise PoseBustersGeneratedPoseEvaluationError(
            "generated-pose receipt does not match exact reexecution"
        )
    return expected


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="betelgeuze-engine-v2-posebusters-evaluate-generated",
        description=(
            "Evaluate Vina poses with pinned PoseBusters redock and all-case rows."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("materialize", "verify"):
        subparser = subparsers.add_parser(command)
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
        subparser.add_argument("--vina-receipt", required=True)
        subparser.add_argument("--vina-artifact-root", required=True)
        subparser.add_argument("--expected-vina-receipt-sha256", required=True)
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
        "archive_path": args.archive,
        "selection_path": args.selection,
        "intake_receipt_path": args.intake_receipt,
        "corpus_audit_receipt_path": args.corpus_audit_receipt,
        "preparation_receipt_path": args.preparation_receipt,
        "preparation_artifact_root": args.preparation_artifact_root,
        "vina_receipt_path": args.vina_receipt,
        "vina_artifact_root": args.vina_artifact_root,
        "posebusters_wheel_path": args.posebusters_wheel,
        "scratch_root": args.scratch_root,
        "expected_preparation_receipt_sha256": (
            args.expected_preparation_receipt_sha256
        ),
        "expected_vina_receipt_sha256": args.expected_vina_receipt_sha256,
    }
    if args.command == "materialize":
        if Path(args.output).exists():
            raise PoseBustersGeneratedPoseEvaluationError(
                "generated-pose evaluation output already exists"
            )
        receipt = materialize_posebusters_generated_pose_evaluation(**common)
        receipt.write_json(args.output)
    else:
        receipt = verify_posebusters_generated_pose_evaluation_receipt(
            evaluation_receipt_path=args.evaluation_receipt,
            **common,
        )
    conditional = {
        (metric.metric_id, metric.denominator_scope): metric
        for metric in receipt.metrics
    }
    print(
        json.dumps(
            {
                "receipt_sha256": receipt.fingerprint_sha256,
                "all_case_denominator": len(receipt.case_rows),
                "generated_pose_count": receipt.generated_pose_count,
                "evaluated_pose_count": receipt.evaluated_pose_count,
                "physically_valid_pose_count": (
                    receipt.physically_valid_pose_count
                ),
                "top_1_rmsd_hit_count_vina_success_cases": conditional[
                    ("top_1_rmsd_le_2_angstrom_rate", "vina_success_cases")
                ].numerator,
                "top_5_rmsd_hit_count_vina_success_cases": conditional[
                    ("top_5_rmsd_le_2_angstrom_rate", "vina_success_cases")
                ].numerator,
                "benchmark_executed": False,
                "claim_safe": False,
            },
            sort_keys=True,
        )
    )
    return 0


__all__ = [
    "POSEBUSTERS_GENERATED_POSE_CONFIGURATION",
    "POSEBUSTERS_GENERATED_POSE_CONFIGURATION_SHA256",
    "POSEBUSTERS_GENERATED_POSE_EVALUATION_SCHEMA_ID",
    "POSEBUSTERS_GENERATED_POSE_REDOCK_CONFIGURATION_SHA256",
    "POSEBUSTERS_GENERATED_POSE_SELECTED_COLUMNS",
    "POSEBUSTERS_GENERATED_POSE_VERSION",
    "POSEBUSTERS_GENERATED_POSE_WHEEL_SHA256",
    "PoseBustersGeneratedPoseCase",
    "PoseBustersGeneratedPoseEvaluationError",
    "PoseBustersGeneratedPoseEvaluationReceipt",
    "PoseBustersGeneratedPoseMetric",
    "PoseBustersGeneratedPoseReportValue",
    "PoseBustersGeneratedPoseResult",
    "PoseBustersGeneratedPoseRuntimeIdentity",
    "main",
    "materialize_posebusters_generated_pose_evaluation",
    "verify_posebusters_generated_pose_evaluation_receipt",
]


if __name__ == "__main__":
    raise SystemExit(main())
