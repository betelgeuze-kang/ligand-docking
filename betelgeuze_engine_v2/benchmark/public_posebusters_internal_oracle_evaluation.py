"""Pinned PoseBusters oracle evaluation of internal selected poses.

The boundary exactly reexecutes the internal direct-RMSD chain, reconstructs
RDKit poses from the raw start-SDF topology plus source-bound prepared
coordinates, and applies the pinned PoseBusters 0.6.5 ``redock`` oracle.  Every
upstream, adapter, case, and pose failure remains in the all-case denominator.

The resulting receipt is external-oracle evidence for an unvalidated internal
diagnostic.  It is not a representative public benchmark, independent rerun,
or product claim.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Mapping, Protocol, Sequence
import zipfile

import torch

from betelgeuze_engine_v2.io import SDFParseError, parse_sdf_v2000
from betelgeuze_engine_v2.molecular import (
    MAX_CANONICAL_SYSTEM_JSON_BYTES,
    AllAtomSystem,
    all_atom_system_from_canonical_json,
    canonical_system_sha256,
)

from .public_posebusters_corpus_audit import (
    PoseBustersCorpusAuditError,
    _canonical_bytes,
    _canonical_sha256,
    _read_member,
    _source_file_sha256,
)
from .public_posebusters_generated_pose_evaluation import (
    POSEBUSTERS_GENERATED_POSE_MAX_RECEIPT_BYTES,
    PoseBustersGeneratedPoseCaseError,
    PoseBustersGeneratedPoseEvaluationError,
    PoseBustersGeneratedPoseMetric,
    PoseBustersGeneratedPoseReportValue,
    PoseBustersGeneratedPoseResult,
    PoseBustersGeneratedPoseRuntimeIdentity,
    _RuntimePoseOutcome,
    _case_id,
    _digest,
    _hash_bytes,
    _identifier,
    _load_posebusters_runtime,
    _metric,
    _normalize_error,
    _positive_int,
    _token,
    _validate_hex,
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
from .public_posebusters_internal_execution import (
    POSEBUSTERS_INTERNAL_EXECUTION_MAX_REPORT_BYTES,
    PoseBustersInternalExecutionConfig,
)
from .public_posebusters_internal_preparation import (
    POSEBUSTERS_INTERNAL_PREPARATION_MAX_ARTIFACT_BYTES,
    PoseBustersInternalPreparationConfig,
)
from .public_posebusters_internal_rmsd_evaluation import (
    POSEBUSTERS_INTERNAL_RMSD_MAX_RECEIPT_BYTES,
    PoseBustersInternalRMSDCase,
    PoseBustersInternalRMSDConfig,
    PoseBustersInternalRMSDEvaluationError,
    PoseBustersInternalRMSDEvaluationReceipt,
    _pose_coordinates,
    verify_posebusters_internal_rmsd_evaluation_receipt,
)
from .redocking_cli import RedockingDiagnosticError, verify_redocking_diagnostic_report


POSEBUSTERS_INTERNAL_ORACLE_POSE_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_internal_oracle_pose/1.0.0"
)
POSEBUSTERS_INTERNAL_ORACLE_CASE_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_internal_oracle_case/1.0.0"
)
POSEBUSTERS_INTERNAL_ORACLE_EVALUATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_internal_oracle_evaluation/1.0.0"
)
POSEBUSTERS_INTERNAL_ORACLE_MAX_RECEIPT_BYTES = (
    POSEBUSTERS_GENERATED_POSE_MAX_RECEIPT_BYTES
)

POSEBUSTERS_INTERNAL_ORACLE_CONFIGURATION = {
    "schema_id": (
        "betelgeuze.engine_v2_posebusters_internal_oracle_configuration/1.0.0"
    ),
    "oracle_id": "posebusters_0.6.5_redock_full_report",
    "pose_topology_source": "exact_raw_ligand_start_conformer_sdf",
    "pose_coordinate_source": (
        "internal_redocking_selected_pose_prepared_atom_coordinates"
    ),
    "atom_mapping_policy": (
        "complete_start_atom_to_prepared_atom_source_index_bijection"
    ),
    "batch_then_per_pose_fallback": True,
    "maximum_pose_count_per_case": 128,
    "rmsd_threshold_angstrom_binary64_hex": (2.0).hex(),
    "top_k": 5,
    "internal_oracle_rmsd_comparison_tolerance_angstrom_binary64_hex": (1.0e-6).hex(),
}
POSEBUSTERS_INTERNAL_ORACLE_CONFIGURATION_SHA256 = (
    "0e84a2d618ccac3545e63195a005854f20ceda663a745247bafcd4893588b7f5"
)

POSEBUSTERS_INTERNAL_ORACLE_BLOCKERS = (
    "internal_pose_generation_scoring_and_refinement_not_scientifically_validated",
    "internal_preparation_chemistry_profile_not_scientifically_validated",
    "supported_subset_selection_bias_not_resolved",
    "target_family_and_chemistry_stratified_metrics_missing",
    "wall_clock_and_peak_memory_measurement_missing",
    "same_input_vina_gnina_smina_comparison_bundle_missing",
    "independent_second_host_oracle_rerun_missing",
    "public_result_bundle_validator_missing",
    "scientific_review_missing",
)

_CASE_STATUSES = {
    "adapter_failure",
    "blocked_upstream",
    "evaluated",
    "evaluation_failure",
    "no_selected_pose",
    "partial_evaluation",
}


class PoseBustersInternalOracleEvaluationError(PoseBustersGeneratedPoseEvaluationError):
    """Internal PoseBusters-oracle input or receipt is invalid."""


@dataclass(frozen=True, slots=True)
class PoseBustersInternalOraclePoseResult:
    pose_rank: int
    candidate_id: str
    proposal_fingerprint_sha256: str
    coordinates_sha256: str
    internal_direct_rmsd_angstrom_binary64_hex: str
    status: str
    report_values: tuple[PoseBustersGeneratedPoseReportValue, ...] = ()
    all_non_rmsd_binary_tests_pass: bool = False
    identity_pass: bool = False
    intramolecular_geometry_pass: bool = False
    internal_energy_pass: bool = False
    intermolecular_distance_and_overlap_pass: bool = False
    rmsd_evaluated: bool = False
    rmsd_within_2_angstrom: bool = False
    oracle_direct_rmsd_angstrom_binary64_hex: str = ""
    oracle_kabsch_rmsd_angstrom_binary64_hex: str = ""
    oracle_centroid_distance_angstrom_binary64_hex: str = ""
    oracle_energy_ratio_binary64_hex: str = ""
    internal_oracle_direct_rmsd_delta_angstrom_binary64_hex: str = ""
    error_stage: str = ""
    error_code: str = ""
    error_type: str = ""
    error_message_sha256: str = ""
    diagnostic_sha256: str = ""
    diagnostic_size_bytes: int = 0
    schema_id: str = POSEBUSTERS_INTERNAL_ORACLE_POSE_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_INTERNAL_ORACLE_POSE_SCHEMA_ID:
            raise PoseBustersInternalOracleEvaluationError(
                "unsupported internal-oracle pose schema"
            )
        rank = _positive_int(self.pose_rank, name="internal-oracle pose rank")
        candidate = _token(self.candidate_id, name="internal-oracle candidate ID")
        proposal = _digest(
            self.proposal_fingerprint_sha256,
            name="internal-oracle proposal fingerprint",
        )
        coordinates = _digest(
            self.coordinates_sha256,
            name="internal-oracle coordinate identity",
        )
        internal_rmsd = _validate_hex(
            self.internal_direct_rmsd_angstrom_binary64_hex,
            name="internal direct RMSD",
        )
        if any(
            not isinstance(value, bool)
            for value in (
                self.all_non_rmsd_binary_tests_pass,
                self.identity_pass,
                self.intramolecular_geometry_pass,
                self.internal_energy_pass,
                self.intermolecular_distance_and_overlap_pass,
                self.rmsd_evaluated,
                self.rmsd_within_2_angstrom,
            )
        ):
            raise PoseBustersInternalOracleEvaluationError(
                "internal-oracle pose flags must be boolean"
            )
        validated = PoseBustersGeneratedPoseResult(
            pose_rank=rank,
            status=self.status,
            vina_energy_components_binary64_hex=((0.0).hex(),) * 5,
            report_values=self.report_values,
            all_non_rmsd_binary_tests_pass=(self.all_non_rmsd_binary_tests_pass),
            identity_pass=self.identity_pass,
            intramolecular_geometry_pass=self.intramolecular_geometry_pass,
            internal_energy_pass=self.internal_energy_pass,
            intermolecular_distance_and_overlap_pass=(
                self.intermolecular_distance_and_overlap_pass
            ),
            rmsd_evaluated=self.rmsd_evaluated,
            rmsd_within_2_angstrom=self.rmsd_within_2_angstrom,
            direct_rmsd_angstrom_binary64_hex=(
                self.oracle_direct_rmsd_angstrom_binary64_hex
            ),
            kabsch_rmsd_angstrom_binary64_hex=(
                self.oracle_kabsch_rmsd_angstrom_binary64_hex
            ),
            centroid_distance_angstrom_binary64_hex=(
                self.oracle_centroid_distance_angstrom_binary64_hex
            ),
            energy_ratio_binary64_hex=self.oracle_energy_ratio_binary64_hex,
            error_stage=self.error_stage,
            error_code=self.error_code,
            error_type=self.error_type,
            error_message_sha256=self.error_message_sha256,
            diagnostic_sha256=self.diagnostic_sha256,
            diagnostic_size_bytes=self.diagnostic_size_bytes,
        )
        delta = self.internal_oracle_direct_rmsd_delta_angstrom_binary64_hex
        if validated.rmsd_evaluated:
            expected_delta = abs(
                float.fromhex(internal_rmsd)
                - float.fromhex(validated.direct_rmsd_angstrom_binary64_hex)
            )
            delta = _validate_hex(delta, name="internal/oracle RMSD delta")
            if float.fromhex(delta).hex() != expected_delta.hex():
                raise PoseBustersInternalOracleEvaluationError(
                    "internal/oracle RMSD delta is inconsistent"
                )
        elif delta:
            raise PoseBustersInternalOracleEvaluationError(
                "unevaluated oracle RMSD cannot carry a comparison delta"
            )
        object.__setattr__(self, "pose_rank", rank)
        object.__setattr__(self, "candidate_id", candidate)
        object.__setattr__(self, "proposal_fingerprint_sha256", proposal)
        object.__setattr__(self, "coordinates_sha256", coordinates)
        object.__setattr__(
            self,
            "internal_direct_rmsd_angstrom_binary64_hex",
            internal_rmsd,
        )
        object.__setattr__(self, "status", validated.status)
        object.__setattr__(self, "report_values", validated.report_values)
        object.__setattr__(
            self,
            "oracle_direct_rmsd_angstrom_binary64_hex",
            validated.direct_rmsd_angstrom_binary64_hex,
        )
        object.__setattr__(
            self,
            "oracle_kabsch_rmsd_angstrom_binary64_hex",
            validated.kabsch_rmsd_angstrom_binary64_hex,
        )
        object.__setattr__(
            self,
            "oracle_centroid_distance_angstrom_binary64_hex",
            validated.centroid_distance_angstrom_binary64_hex,
        )
        object.__setattr__(
            self,
            "oracle_energy_ratio_binary64_hex",
            validated.energy_ratio_binary64_hex,
        )
        object.__setattr__(
            self,
            "internal_oracle_direct_rmsd_delta_angstrom_binary64_hex",
            delta,
        )
        object.__setattr__(self, "error_stage", validated.error_stage)
        object.__setattr__(self, "error_code", validated.error_code)
        object.__setattr__(self, "error_type", validated.error_type)
        object.__setattr__(
            self,
            "error_message_sha256",
            validated.error_message_sha256,
        )
        object.__setattr__(
            self,
            "diagnostic_sha256",
            validated.diagnostic_sha256,
        )
        object.__setattr__(
            self,
            "diagnostic_size_bytes",
            validated.diagnostic_size_bytes,
        )

    @property
    def valid_and_rmsd_within_2_angstrom(self) -> bool:
        return self.all_non_rmsd_binary_tests_pass and self.rmsd_within_2_angstrom

    @property
    def report_sha256(self) -> str:
        return _canonical_sha256([row.to_dict() for row in self.report_values])

    @property
    def rmsd_agrees_with_internal_tolerance(self) -> bool:
        return bool(
            self.rmsd_evaluated
            and float.fromhex(
                self.internal_oracle_direct_rmsd_delta_angstrom_binary64_hex
            )
            <= float.fromhex(
                str(
                    POSEBUSTERS_INTERNAL_ORACLE_CONFIGURATION[
                        "internal_oracle_rmsd_comparison_tolerance_angstrom_binary64_hex"
                    ]
                )
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "pose_rank": self.pose_rank,
            "candidate_id": self.candidate_id,
            "proposal_fingerprint_sha256": self.proposal_fingerprint_sha256,
            "coordinates_sha256": self.coordinates_sha256,
            "internal_direct_rmsd_angstrom_binary64_hex": (
                self.internal_direct_rmsd_angstrom_binary64_hex
            ),
            "status": self.status,
            "report_values": [row.to_dict() for row in self.report_values],
            "report_sha256": self.report_sha256,
            "all_non_rmsd_binary_tests_pass": (self.all_non_rmsd_binary_tests_pass),
            "identity_pass": self.identity_pass,
            "intramolecular_geometry_pass": self.intramolecular_geometry_pass,
            "internal_energy_pass": self.internal_energy_pass,
            "intermolecular_distance_and_overlap_pass": (
                self.intermolecular_distance_and_overlap_pass
            ),
            "rmsd_evaluated": self.rmsd_evaluated,
            "rmsd_within_2_angstrom": self.rmsd_within_2_angstrom,
            "valid_and_rmsd_within_2_angstrom": (self.valid_and_rmsd_within_2_angstrom),
            "oracle_direct_rmsd_angstrom_binary64_hex": (
                self.oracle_direct_rmsd_angstrom_binary64_hex
            ),
            "oracle_kabsch_rmsd_angstrom_binary64_hex": (
                self.oracle_kabsch_rmsd_angstrom_binary64_hex
            ),
            "oracle_centroid_distance_angstrom_binary64_hex": (
                self.oracle_centroid_distance_angstrom_binary64_hex
            ),
            "oracle_energy_ratio_binary64_hex": (self.oracle_energy_ratio_binary64_hex),
            "internal_oracle_direct_rmsd_delta_angstrom_binary64_hex": (
                self.internal_oracle_direct_rmsd_delta_angstrom_binary64_hex
            ),
            "rmsd_agrees_with_internal_tolerance": (
                self.rmsd_agrees_with_internal_tolerance
            ),
            "error_stage": self.error_stage,
            "error_code": self.error_code,
            "error_type": self.error_type,
            "error_message_sha256": self.error_message_sha256,
            "diagnostic_sha256": self.diagnostic_sha256,
            "diagnostic_size_bytes": self.diagnostic_size_bytes,
        }


@dataclass(frozen=True, slots=True)
class PoseBustersInternalOracleCase:
    case_id: str
    status: str
    disposition_code: str
    internal_rmsd_status: str
    selected_pose_count: int
    oracle_attempted: bool
    receptor_source_sha256: str = ""
    reference_ligands_source_sha256: str = ""
    start_ligand_source_sha256: str = ""
    prepared_ligand_artifact_sha256: str = ""
    prepared_ligand_system_sha256: str = ""
    diagnostic_report_receipt_sha256: str = ""
    source_to_prepared_atom_mapping_sha256: str = ""
    pose_results: tuple[PoseBustersInternalOraclePoseResult, ...] = ()
    error_stage: str = ""
    error_code: str = ""
    error_type: str = ""
    error_message_sha256: str = ""
    diagnostic_sha256: str = ""
    diagnostic_size_bytes: int = 0
    schema_id: str = POSEBUSTERS_INTERNAL_ORACLE_CASE_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_INTERNAL_ORACLE_CASE_SCHEMA_ID:
            raise PoseBustersInternalOracleEvaluationError(
                "unsupported internal-oracle case schema"
            )
        case = _case_id(self.case_id)
        if self.status not in _CASE_STATUSES:
            raise PoseBustersInternalOracleEvaluationError(
                "internal-oracle case status is invalid"
            )
        disposition = _token(
            self.disposition_code,
            name="internal-oracle case disposition",
        )
        expected_disposition = {
            "evaluated": "posebusters_internal_pose_oracle_complete",
            "partial_evaluation": "posebusters_internal_pose_failures_retained",
            "evaluation_failure": "posebusters_internal_pose_failures_retained",
            "adapter_failure": "internal_pose_oracle_adapter_failed",
            "no_selected_pose": "internal_redocking_selected_no_pose",
            "blocked_upstream": "blocked_by_internal_rmsd_disposition",
        }[self.status]
        if disposition != expected_disposition:
            raise PoseBustersInternalOracleEvaluationError(
                "internal-oracle disposition disagrees with status"
            )
        upstream = _token(
            self.internal_rmsd_status,
            name="internal RMSD status",
        )
        selected = _positive_int(
            self.selected_pose_count,
            name="internal selected pose count",
            allow_zero=True,
        )
        if not isinstance(self.oracle_attempted, bool):
            raise PoseBustersInternalOracleEvaluationError(
                "oracle_attempted must be boolean"
            )
        source_digests = tuple(
            (_digest(getattr(self, name), name=name) if getattr(self, name) else "")
            for name in (
                "receptor_source_sha256",
                "reference_ligands_source_sha256",
                "start_ligand_source_sha256",
                "prepared_ligand_artifact_sha256",
                "prepared_ligand_system_sha256",
                "diagnostic_report_receipt_sha256",
                "source_to_prepared_atom_mapping_sha256",
            )
        )
        poses = tuple(self.pose_results)
        if (
            any(
                not isinstance(row, PoseBustersInternalOraclePoseResult)
                for row in poses
            )
            or tuple(row.pose_rank for row in poses) != tuple(range(1, len(poses) + 1))
            or len({row.candidate_id for row in poses}) != len(poses)
        ):
            raise PoseBustersInternalOracleEvaluationError(
                "internal-oracle pose rows are not canonical"
            )
        diagnostics = _positive_int(
            self.diagnostic_size_bytes,
            name="internal-oracle case diagnostic size",
            allow_zero=True,
        )
        case_error_fields = (
            self.error_stage,
            self.error_code,
            self.error_type,
            self.error_message_sha256,
            self.diagnostic_sha256,
        )
        if self.status in {
            "evaluated",
            "partial_evaluation",
            "evaluation_failure",
        }:
            evaluated = sum(row.status == "evaluated" for row in poses)
            expected = (
                "evaluated"
                if evaluated == selected
                else "evaluation_failure"
                if evaluated == 0
                else "partial_evaluation"
            )
            valid = (
                upstream == "evaluated"
                and selected > 0
                and self.oracle_attempted
                and len(poses) == selected
                and self.status == expected
                and all(source_digests)
                and not any(case_error_fields)
                and diagnostics == 0
            )
        elif self.status == "adapter_failure":
            valid = (
                upstream == "evaluated"
                and selected > 0
                and not self.oracle_attempted
                and not any(source_digests)
                and not poses
                and all(case_error_fields)
            )
        elif self.status == "no_selected_pose":
            valid = (
                upstream == "evaluated"
                and selected == 0
                and not self.oracle_attempted
                and not any(source_digests)
                and not poses
                and not any(case_error_fields)
                and diagnostics == 0
            )
        else:
            valid = (
                upstream != "evaluated"
                and selected == 0
                and not self.oracle_attempted
                and not any(source_digests)
                and not poses
                and not any(case_error_fields)
                and diagnostics == 0
            )
        if not valid:
            raise PoseBustersInternalOracleEvaluationError(
                "internal-oracle case fields disagree with status"
            )
        if self.status == "adapter_failure":
            object.__setattr__(
                self,
                "error_stage",
                _token(self.error_stage, name="internal-oracle error stage"),
            )
            object.__setattr__(
                self,
                "error_code",
                _token(self.error_code, name="internal-oracle error code"),
            )
            object.__setattr__(
                self,
                "error_type",
                _identifier(self.error_type, name="internal-oracle error type"),
            )
            object.__setattr__(
                self,
                "error_message_sha256",
                _digest(
                    self.error_message_sha256,
                    name="internal-oracle error message",
                ),
            )
            object.__setattr__(
                self,
                "diagnostic_sha256",
                _digest(
                    self.diagnostic_sha256,
                    name="internal-oracle diagnostic",
                ),
            )
        for name, value in zip(
            (
                "receptor_source_sha256",
                "reference_ligands_source_sha256",
                "start_ligand_source_sha256",
                "prepared_ligand_artifact_sha256",
                "prepared_ligand_system_sha256",
                "diagnostic_report_receipt_sha256",
                "source_to_prepared_atom_mapping_sha256",
            ),
            source_digests,
            strict=True,
        ):
            object.__setattr__(self, name, value)
        object.__setattr__(self, "case_id", case)
        object.__setattr__(self, "disposition_code", disposition)
        object.__setattr__(self, "internal_rmsd_status", upstream)
        object.__setattr__(self, "selected_pose_count", selected)
        object.__setattr__(self, "pose_results", poses)
        object.__setattr__(self, "diagnostic_size_bytes", diagnostics)

    @property
    def evaluation_complete(self) -> bool:
        return self.status == "evaluated"

    @property
    def has_any_valid_pose(self) -> bool:
        return any(row.all_non_rmsd_binary_tests_pass for row in self.pose_results)

    def top_valid(self, top_k: int) -> bool:
        return any(
            row.all_non_rmsd_binary_tests_pass for row in self.pose_results[:top_k]
        )

    def top_rmsd_hit(self, top_k: int) -> bool:
        return any(row.rmsd_within_2_angstrom for row in self.pose_results[:top_k])

    def top_valid_rmsd_hit(self, top_k: int) -> bool:
        return any(
            row.valid_and_rmsd_within_2_angstrom for row in self.pose_results[:top_k]
        )

    def best_oracle_rmsd(self, top_k: int) -> str:
        values = [
            row.oracle_direct_rmsd_angstrom_binary64_hex
            for row in self.pose_results[:top_k]
            if row.rmsd_evaluated
        ]
        return "" if not values else min(values, key=float.fromhex)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "case_id": self.case_id,
            "status": self.status,
            "disposition_code": self.disposition_code,
            "internal_rmsd_status": self.internal_rmsd_status,
            "selected_pose_count": self.selected_pose_count,
            "oracle_attempted": self.oracle_attempted,
            "receptor_source_sha256": self.receptor_source_sha256,
            "reference_ligands_source_sha256": (self.reference_ligands_source_sha256),
            "start_ligand_source_sha256": self.start_ligand_source_sha256,
            "prepared_ligand_artifact_sha256": (self.prepared_ligand_artifact_sha256),
            "prepared_ligand_system_sha256": (self.prepared_ligand_system_sha256),
            "diagnostic_report_receipt_sha256": (self.diagnostic_report_receipt_sha256),
            "source_to_prepared_atom_mapping_sha256": (
                self.source_to_prepared_atom_mapping_sha256
            ),
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
            "rmsd_agreement_pose_count": sum(
                row.rmsd_agrees_with_internal_tolerance for row in self.pose_results
            ),
            "evaluation_complete": self.evaluation_complete,
            "has_any_valid_pose": self.has_any_valid_pose,
            "top_1_valid": self.top_valid(1),
            "top_5_valid": self.top_valid(5),
            "top_1_rmsd_within_2_angstrom": self.top_rmsd_hit(1),
            "top_5_rmsd_within_2_angstrom": self.top_rmsd_hit(5),
            "top_1_valid_and_rmsd_within_2_angstrom": (self.top_valid_rmsd_hit(1)),
            "top_5_valid_and_rmsd_within_2_angstrom": (self.top_valid_rmsd_hit(5)),
            "top_1_oracle_direct_rmsd_angstrom_binary64_hex": (
                self.best_oracle_rmsd(1)
            ),
            "top_5_best_oracle_direct_rmsd_angstrom_binary64_hex": (
                self.best_oracle_rmsd(5)
            ),
            "pose_results": [row.to_dict() for row in self.pose_results],
            "error_stage": self.error_stage,
            "error_code": self.error_code,
            "error_type": self.error_type,
            "error_message_sha256": self.error_message_sha256,
            "diagnostic_sha256": self.diagnostic_sha256,
            "diagnostic_size_bytes": self.diagnostic_size_bytes,
        }


class _InternalOracleCaseObserver(Protocol):
    def case_started(self, case_id: str) -> None: ...

    def case_finished(self, row: PoseBustersInternalOracleCase) -> None: ...

    def case_aborted(self, case_id: str) -> None: ...


def _summary_metrics(
    rows: Sequence[PoseBustersInternalOracleCase],
) -> tuple[PoseBustersGeneratedPoseMetric, ...]:
    all_cases = tuple(rows)
    selected_cases = tuple(row for row in rows if row.selected_pose_count > 0)
    selected_poses = tuple(pose for row in selected_cases for pose in row.pose_results)
    selected_pose_denominator = sum(
        row.selected_pose_count for row in selected_cases
    )
    case_predicates = (
        ("internal_selected_pose_case_rate", lambda row: row.selected_pose_count > 0),
        ("posebusters_oracle_attempt_rate", lambda row: row.oracle_attempted),
        (
            "posebusters_complete_case_evaluation_rate",
            lambda row: row.evaluation_complete,
        ),
        (
            "posebusters_case_failure_rate",
            lambda row: (
                row.status
                in {"adapter_failure", "partial_evaluation", "evaluation_failure"}
            ),
        ),
        (
            "case_with_any_physically_valid_pose_rate",
            lambda row: row.has_any_valid_pose,
        ),
        ("top_1_physically_valid_pose_rate", lambda row: row.top_valid(1)),
        ("top_5_physically_valid_pose_rate", lambda row: row.top_valid(5)),
        ("top_1_rmsd_le_2_angstrom_rate", lambda row: row.top_rmsd_hit(1)),
        ("top_5_rmsd_le_2_angstrom_rate", lambda row: row.top_rmsd_hit(5)),
        (
            "top_1_valid_and_rmsd_le_2_angstrom_rate",
            lambda row: row.top_valid_rmsd_hit(1),
        ),
        (
            "top_5_valid_and_rmsd_le_2_angstrom_rate",
            lambda row: row.top_valid_rmsd_hit(5),
        ),
    )
    conditional_predicates = case_predicates[4:]
    pose_predicates = (
        ("pose_evaluation_success_rate", lambda row: row.status == "evaluated"),
        ("physically_valid_pose_rate", lambda row: row.all_non_rmsd_binary_tests_pass),
        ("rmsd_evaluated_pose_rate", lambda row: row.rmsd_evaluated),
        ("rmsd_le_2_angstrom_pose_rate", lambda row: row.rmsd_within_2_angstrom),
        (
            "valid_and_rmsd_le_2_angstrom_pose_rate",
            lambda row: row.valid_and_rmsd_within_2_angstrom,
        ),
        (
            "internal_oracle_direct_rmsd_agreement_rate",
            lambda row: row.rmsd_agrees_with_internal_tolerance,
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
            "internal_selected_pose_cases",
            sum(bool(predicate(row)) for row in selected_cases),
            len(selected_cases),
        )
        for name, predicate in conditional_predicates
    )
    metrics.extend(
        _metric(
            name,
            "internal_selected_poses",
            sum(bool(predicate(row)) for row in selected_poses),
            selected_pose_denominator,
        )
        for name, predicate in pose_predicates
    )
    return tuple(metrics)


@dataclass(frozen=True, slots=True)
class PoseBustersInternalOracleEvaluationReceipt:
    archive_intake_receipt_sha256: str
    internal_rmsd_receipt_sha256: str
    internal_rmsd_receipt_file_sha256: str
    internal_execution_receipt_sha256: str
    implementation_source_sha256: str
    implementation_source_members: tuple[tuple[str, str], ...]
    runtime_identity: PoseBustersGeneratedPoseRuntimeIdentity
    configuration_sha256: str
    case_rows: tuple[PoseBustersInternalOracleCase, ...]
    metrics: tuple[PoseBustersGeneratedPoseMetric, ...]
    schema_id: str = POSEBUSTERS_INTERNAL_ORACLE_EVALUATION_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_INTERNAL_ORACLE_EVALUATION_SCHEMA_ID:
            raise PoseBustersInternalOracleEvaluationError(
                "unsupported internal-oracle evaluation schema"
            )
        for name in (
            "archive_intake_receipt_sha256",
            "internal_rmsd_receipt_sha256",
            "internal_rmsd_receipt_file_sha256",
            "internal_execution_receipt_sha256",
            "implementation_source_sha256",
            "configuration_sha256",
        ):
            object.__setattr__(
                self,
                name,
                _digest(getattr(self, name), name=name),
            )
        if self.configuration_sha256 != (
            POSEBUSTERS_INTERNAL_ORACLE_CONFIGURATION_SHA256
        ):
            raise PoseBustersInternalOracleEvaluationError(
                "internal-oracle configuration identity changed"
            )
        members = tuple(
            (
                _token(role, name="internal-oracle implementation role"),
                _digest(digest, name=f"{role} implementation source"),
            )
            for role, digest in self.implementation_source_members
        )
        if (
            not members
            or tuple(sorted(members)) != members
            or len({role for role, _digest_value in members}) != len(members)
            or self.implementation_source_sha256 != _canonical_sha256(dict(members))
        ):
            raise PoseBustersInternalOracleEvaluationError(
                "internal-oracle implementation-source identity is invalid"
            )
        if not isinstance(
            self.runtime_identity,
            PoseBustersGeneratedPoseRuntimeIdentity,
        ):
            raise PoseBustersInternalOracleEvaluationError(
                "internal-oracle runtime identity is missing"
            )
        rows = tuple(self.case_rows)
        if (
            not rows
            or any(not isinstance(row, PoseBustersInternalOracleCase) for row in rows)
            or tuple(row.case_id for row in rows)
            != tuple(sorted(row.case_id for row in rows))
            or len({row.case_id for row in rows}) != len(rows)
        ):
            raise PoseBustersInternalOracleEvaluationError(
                "internal-oracle rows must be canonical unique cases"
            )
        if any(
            not isinstance(row, PoseBustersGeneratedPoseMetric) for row in self.metrics
        ):
            raise PoseBustersInternalOracleEvaluationError(
                "internal-oracle metrics have the wrong type"
            )
        metrics = _summary_metrics(rows)
        if tuple(row.to_dict() for row in self.metrics) != tuple(
            row.to_dict() for row in metrics
        ):
            raise PoseBustersInternalOracleEvaluationError(
                "internal-oracle metrics disagree with case rows"
            )
        object.__setattr__(self, "implementation_source_members", members)
        object.__setattr__(self, "case_rows", rows)
        object.__setattr__(self, "metrics", metrics)

    @property
    def selected_pose_count(self) -> int:
        return sum(row.selected_pose_count for row in self.case_rows)

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
            "internal_rmsd_receipt_sha256": self.internal_rmsd_receipt_sha256,
            "internal_rmsd_receipt_file_sha256": (
                self.internal_rmsd_receipt_file_sha256
            ),
            "internal_execution_receipt_sha256": (
                self.internal_execution_receipt_sha256
            ),
            "implementation_source_sha256": self.implementation_source_sha256,
            "implementation_source_members": dict(self.implementation_source_members),
            "runtime_identity": self.runtime_identity.to_dict(),
            "runtime_identity_sha256": self.runtime_identity.fingerprint_sha256,
            "configuration": dict(POSEBUSTERS_INTERNAL_ORACLE_CONFIGURATION),
            "configuration_sha256": self.configuration_sha256,
            "all_case_denominator": len(self.case_rows),
            "selected_pose_count": self.selected_pose_count,
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
            "internal_direct_rmsd_comparison_present": any(
                pose.rmsd_evaluated
                for row in self.case_rows
                for pose in row.pose_results
            ),
            "target_family_metrics_present": False,
            "chemistry_stratified_metrics_present": False,
            "runtime_measurements_present": False,
            "independent_external_rerun_present": False,
            "public_result_bundle_validated": False,
            "benchmark_executed": False,
            "scientific_blockers": list(POSEBUSTERS_INTERNAL_ORACLE_BLOCKERS),
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
        if len(payload) > POSEBUSTERS_INTERNAL_ORACLE_MAX_RECEIPT_BYTES:
            raise PoseBustersInternalOracleEvaluationError(
                "internal-oracle receipt exceeds its byte bound"
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
                raise PoseBustersInternalOracleEvaluationError(
                    "internal-oracle receipt output already exists"
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
    row: PoseBustersInternalRMSDCase,
    artifact_root: Path,
) -> AllAtomSystem:
    source = _read_exact_regular_file(
        artifact_root / row.case_id / "ligand.canonical.json",
        maximum_bytes=min(
            POSEBUSTERS_INTERNAL_PREPARATION_MAX_ARTIFACT_BYTES,
            MAX_CANONICAL_SYSTEM_JSON_BYTES,
        ),
    )
    if hashlib.sha256(source).hexdigest() != row.prepared_ligand_artifact_sha256:
        raise PoseBustersInternalOracleEvaluationError(
            "prepared ligand artifact is cross-wired"
        )
    system = all_atom_system_from_canonical_json(source, device="cpu")
    if canonical_system_sha256(system) != row.prepared_ligand_system_sha256:
        raise PoseBustersInternalOracleEvaluationError(
            "prepared ligand system identity is cross-wired"
        )
    return system


def _read_report(
    row: PoseBustersInternalRMSDCase,
    artifact_root: Path,
) -> dict[str, object]:
    source = _read_exact_regular_file(
        artifact_root / row.case_id / "redocking.report.json",
        maximum_bytes=POSEBUSTERS_INTERNAL_EXECUTION_MAX_REPORT_BYTES,
    )
    report = verify_redocking_diagnostic_report(source)
    if report.get("receipt_sha256") != row.diagnostic_report_receipt_sha256:
        raise PoseBustersInternalOracleEvaluationError(
            "internal redocking report is cross-wired"
        )
    return report


def _source_to_prepared_mapping(
    start: AllAtomSystem,
    prepared: AllAtomSystem,
    *,
    start_source_sha256: str,
) -> tuple[tuple[int, ...], str]:
    mapping: dict[int, int] = {}
    for atom in prepared.atoms:
        source_index = atom.metadata.get("source_atom_index")
        if source_index is None:
            continue
        if (
            isinstance(source_index, bool)
            or not isinstance(source_index, int)
            or not 0 <= source_index < start.atom_count
            or source_index in mapping
            or atom.atomic_number != start.atoms[source_index].atomic_number
        ):
            raise PoseBustersInternalOracleEvaluationError(
                "prepared atom has an invalid source-start binding"
            )
        mapping[source_index] = atom.index
    if (
        set(mapping) != set(range(start.atom_count))
        or set(mapping.values()) != set(range(prepared.atom_count))
    ):
        raise PoseBustersInternalOracleEvaluationError(
            "raw start and prepared atoms do not form a complete source-bound bijection"
        )
    ordered = tuple(mapping[index] for index in range(start.atom_count))
    identity = _canonical_sha256(
        {
            "start_ligand_source_sha256": start_source_sha256,
            "prepared_ligand_system_sha256": canonical_system_sha256(prepared),
            "source_atom_to_prepared_atom": list(ordered),
        }
    )
    return ordered, identity


def _adapter_failure(
    row: PoseBustersInternalRMSDCase,
    exc: BaseException,
) -> PoseBustersInternalOracleCase:
    if isinstance(exc, PoseBustersGeneratedPoseCaseError):
        stage = exc.stage
        code = exc.error_code
        error_type = exc.error_type
        message_sha256 = exc.error_message_sha256
        diagnostic_sha256 = exc.diagnostic_sha256
        diagnostic_size = exc.diagnostic_size_bytes
    else:
        stage = "internal_pose_oracle_adapter"
        code = "internal_pose_oracle_adapter_failed"
        error_type = type(exc).__name__
        message_sha256 = _hash_bytes(_normalize_error(exc))
        diagnostic_sha256 = _hash_bytes(b"")
        diagnostic_size = 0
    return PoseBustersInternalOracleCase(
        case_id=row.case_id,
        status="adapter_failure",
        disposition_code="internal_pose_oracle_adapter_failed",
        internal_rmsd_status=row.status,
        selected_pose_count=len(row.pose_results),
        oracle_attempted=False,
        error_stage=stage,
        error_code=code,
        error_type=error_type,
        error_message_sha256=message_sha256,
        diagnostic_sha256=diagnostic_sha256,
        diagnostic_size_bytes=diagnostic_size,
    )


def _pose_result(
    source: Any,
    outcome: _RuntimePoseOutcome,
) -> PoseBustersInternalOraclePoseResult:
    delta = ""
    if outcome.rmsd_evaluated:
        delta = abs(
            float.fromhex(source.direct_rmsd_angstrom_binary64_hex)
            - float.fromhex(outcome.direct_rmsd_angstrom_binary64_hex)
        ).hex()
    return PoseBustersInternalOraclePoseResult(
        pose_rank=source.rank,
        candidate_id=source.candidate_id,
        proposal_fingerprint_sha256=source.proposal_fingerprint_sha256,
        coordinates_sha256=source.coordinates_sha256,
        internal_direct_rmsd_angstrom_binary64_hex=(
            source.direct_rmsd_angstrom_binary64_hex
        ),
        status=outcome.status,
        report_values=outcome.report_values,
        all_non_rmsd_binary_tests_pass=(outcome.all_non_rmsd_binary_tests_pass),
        identity_pass=outcome.identity_pass,
        intramolecular_geometry_pass=outcome.intramolecular_geometry_pass,
        internal_energy_pass=outcome.internal_energy_pass,
        intermolecular_distance_and_overlap_pass=(
            outcome.intermolecular_distance_and_overlap_pass
        ),
        rmsd_evaluated=outcome.rmsd_evaluated,
        rmsd_within_2_angstrom=outcome.rmsd_within_2_angstrom,
        oracle_direct_rmsd_angstrom_binary64_hex=(
            outcome.direct_rmsd_angstrom_binary64_hex
        ),
        oracle_kabsch_rmsd_angstrom_binary64_hex=(
            outcome.kabsch_rmsd_angstrom_binary64_hex
        ),
        oracle_centroid_distance_angstrom_binary64_hex=(
            outcome.centroid_distance_angstrom_binary64_hex
        ),
        oracle_energy_ratio_binary64_hex=outcome.energy_ratio_binary64_hex,
        internal_oracle_direct_rmsd_delta_angstrom_binary64_hex=delta,
        error_stage=outcome.error_stage,
        error_code=outcome.error_code,
        error_type=outcome.error_type,
        error_message_sha256=outcome.error_message_sha256,
        diagnostic_sha256=outcome.diagnostic_sha256,
        diagnostic_size_bytes=outcome.diagnostic_size_bytes,
    )


def _evaluate_case(
    archive: zipfile.ZipFile,
    intake_row: Any,
    row: PoseBustersInternalRMSDCase,
    preparation_artifact_root: Path,
    execution_artifact_root: Path,
    runtime: Any,
) -> PoseBustersInternalOracleCase:
    if row.status != "evaluated":
        return PoseBustersInternalOracleCase(
            case_id=row.case_id,
            status="blocked_upstream",
            disposition_code="blocked_by_internal_rmsd_disposition",
            internal_rmsd_status=row.status,
            selected_pose_count=0,
            oracle_attempted=False,
        )
    if not row.pose_results:
        return PoseBustersInternalOracleCase(
            case_id=row.case_id,
            status="no_selected_pose",
            disposition_code="internal_redocking_selected_no_pose",
            internal_rmsd_status=row.status,
            selected_pose_count=0,
            oracle_attempted=False,
        )
    try:
        artifacts = _source_artifacts(intake_row)
        receptor_artifact = artifacts["receptor_pdb"]
        native_artifact = artifacts["reference_ligands_sdf"]
        start_artifact = artifacts["ligand_start_conformer_sdf"]
        receptor_source = _read_member(
            archive,
            receptor_artifact.member_path,
            expected_sha256=receptor_artifact.sha256,
            expected_size=receptor_artifact.size_bytes,
        )
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
        start = parse_sdf_v2000(
            start_source,
            source_id=f"{row.case_id}:internal_oracle_start",
            dtype=torch.float64,
            device="cpu",
        )
        prepared = _read_prepared_ligand(row, preparation_artifact_root)
        mapping, mapping_sha256 = _source_to_prepared_mapping(
            start,
            prepared,
            start_source_sha256=start_artifact.sha256,
        )
        report = _read_report(row, execution_artifact_root)
        raw_poses = report.get("top_poses")
        if not isinstance(raw_poses, list) or len(raw_poses) != len(row.pose_results):
            raise PoseBustersInternalOracleEvaluationError(
                "internal report and RMSD selected-pose counts disagree"
            )
        coordinate_rows: list[list[list[float]]] = []
        for raw_pose, rmsd_pose in zip(
            raw_poses,
            row.pose_results,
            strict=True,
        ):
            if not isinstance(raw_pose, Mapping):
                raise PoseBustersInternalOracleEvaluationError(
                    "internal report selected pose is not an object"
                )
            coordinates, coordinates_sha256 = _pose_coordinates(
                raw_pose,
                atom_count=prepared.atom_count,
            )
            if (
                raw_pose.get("rank") != rmsd_pose.rank
                or raw_pose.get("candidate_id") != rmsd_pose.candidate_id
                or raw_pose.get("proposal_fingerprint_sha256")
                != rmsd_pose.proposal_fingerprint_sha256
                or coordinates_sha256 != rmsd_pose.coordinates_sha256
            ):
                raise PoseBustersInternalOracleEvaluationError(
                    "internal RMSD pose is cross-wired to another report row"
                )
            coordinate_rows.append(coordinates.tolist())
        outcomes = runtime.evaluate_prepared_coordinate_case(
            start_source,
            mapping,
            coordinate_rows,
            receptor_source,
            native_source,
        )
        if len(outcomes) != len(row.pose_results):
            raise PoseBustersInternalOracleEvaluationError(
                "PoseBusters oracle outcome count disagrees with selected poses"
            )
        pose_results = tuple(
            _pose_result(source, outcome)
            for source, outcome in zip(
                row.pose_results,
                outcomes,
                strict=True,
            )
        )
    except (
        KeyError,
        OSError,
        PoseBustersCorpusAuditError,
        PoseBustersGeneratedPoseCaseError,
        PoseBustersInternalOracleEvaluationError,
        RedockingDiagnosticError,
        SDFParseError,
        TypeError,
        ValueError,
    ) as exc:
        return _adapter_failure(row, exc)
    evaluated = sum(result.status == "evaluated" for result in pose_results)
    status = (
        "evaluated"
        if evaluated == len(pose_results)
        else "evaluation_failure"
        if evaluated == 0
        else "partial_evaluation"
    )
    return PoseBustersInternalOracleCase(
        case_id=row.case_id,
        status=status,
        disposition_code=(
            "posebusters_internal_pose_oracle_complete"
            if status == "evaluated"
            else "posebusters_internal_pose_failures_retained"
        ),
        internal_rmsd_status=row.status,
        selected_pose_count=len(row.pose_results),
        oracle_attempted=True,
        receptor_source_sha256=receptor_artifact.sha256,
        reference_ligands_source_sha256=native_artifact.sha256,
        start_ligand_source_sha256=start_artifact.sha256,
        prepared_ligand_artifact_sha256=row.prepared_ligand_artifact_sha256,
        prepared_ligand_system_sha256=row.prepared_ligand_system_sha256,
        diagnostic_report_receipt_sha256=(row.diagnostic_report_receipt_sha256),
        source_to_prepared_atom_mapping_sha256=mapping_sha256,
        pose_results=pose_results,
    )


def _implementation_source_members(
    rmsd: PoseBustersInternalRMSDEvaluationReceipt,
) -> tuple[tuple[str, str], ...]:
    members = dict(rmsd.implementation_source_members)
    members.update(
        {
            "internal_oracle_evaluation": _source_file_sha256(__file__),
            "posebusters_generated_pose_runtime": _source_file_sha256(
                Path(__file__).with_name(
                    "public_posebusters_generated_pose_evaluation.py"
                )
            ),
        }
    )
    return tuple(sorted(members.items()))


def _build_evaluation(
    internal_rmsd_receipt_path: str | os.PathLike[str],
    execution_receipt_path: str | os.PathLike[str],
    execution_artifact_root: str | os.PathLike[str],
    preparation_receipt_path: str | os.PathLike[str],
    preparation_artifact_root: str | os.PathLike[str],
    archive_path: str | os.PathLike[str],
    selection_path: str | os.PathLike[str],
    intake_receipt_path: str | os.PathLike[str],
    corpus_audit_receipt_path: str | os.PathLike[str],
    posebusters_wheel_path: str | os.PathLike[str],
    scratch_root: str | os.PathLike[str],
    *,
    expected_internal_rmsd_receipt_sha256: str,
    contract: PoseBustersArchiveContract,
    preparation_configuration: PoseBustersInternalPreparationConfig | None,
    execution_configuration: PoseBustersInternalExecutionConfig,
    rmsd_configuration: PoseBustersInternalRMSDConfig,
    case_observer: _InternalOracleCaseObserver | None = None,
) -> PoseBustersInternalOracleEvaluationReceipt:
    expected_rmsd_sha256 = _digest(
        expected_internal_rmsd_receipt_sha256,
        name="expected internal RMSD receipt",
    )
    if (
        _canonical_sha256(POSEBUSTERS_INTERNAL_ORACLE_CONFIGURATION)
        != POSEBUSTERS_INTERNAL_ORACLE_CONFIGURATION_SHA256
    ):
        raise PoseBustersInternalOracleEvaluationError(
            "internal-oracle frozen configuration was mutated"
        )
    try:
        rmsd = verify_posebusters_internal_rmsd_evaluation_receipt(
            internal_rmsd_receipt_path,
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
            execution_configuration=execution_configuration,
            configuration=rmsd_configuration,
        )
        intake = verify_posebusters_archive_intake_receipt(
            intake_receipt_path,
            archive_path,
            selection_path,
            contract=contract,
        )
    except (
        PoseBustersArchiveIntakeError,
        PoseBustersInternalRMSDEvaluationError,
    ) as exc:
        raise PoseBustersInternalOracleEvaluationError(
            "internal-oracle evaluation requires exact RMSD and intake receipts"
        ) from exc
    if rmsd.fingerprint_sha256 != expected_rmsd_sha256:
        raise PoseBustersInternalOracleEvaluationError(
            "internal RMSD receipt identity differs from the expected input"
        )
    rmsd_source = _read_exact_regular_file(
        internal_rmsd_receipt_path,
        maximum_bytes=POSEBUSTERS_INTERNAL_RMSD_MAX_RECEIPT_BYTES,
    )
    intake_source = _read_exact_regular_file(
        intake_receipt_path,
        maximum_bytes=POSEBUSTERS_ARCHIVE_MAX_RECEIPT_BYTES,
    )
    if (
        rmsd_source != _canonical_bytes(rmsd.to_dict()) + b"\n"
        or intake_source != _canonical_bytes(intake.to_dict()) + b"\n"
    ):
        raise PoseBustersInternalOracleEvaluationError(
            "upstream receipt changed after exact verification"
        )
    if tuple(row.case_id for row in rmsd.case_rows) != tuple(
        row.case_id for row in intake.case_rows
    ):
        raise PoseBustersInternalOracleEvaluationError(
            "internal RMSD and intake case identities disagree"
        )
    runtime = _load_posebusters_runtime(
        Path(scratch_root),
        posebusters_wheel_path,
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
            raise PoseBustersInternalOracleEvaluationError(
                "PoseBusters archive changed after source-chain verification"
            )
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            try:
                with zipfile.ZipFile(handle, "r") as archive:
                    observed_rows: list[PoseBustersInternalOracleCase] = []
                    for intake_row, rmsd_row in zip(
                        intake.case_rows,
                        rmsd.case_rows,
                        strict=True,
                    ):
                        if case_observer is not None:
                            case_observer.case_started(rmsd_row.case_id)
                        try:
                            observed = _evaluate_case(
                                archive,
                                intake_row,
                                rmsd_row,
                                Path(preparation_artifact_root),
                                Path(execution_artifact_root),
                                runtime,
                            )
                        except BaseException:
                            if case_observer is not None:
                                try:
                                    case_observer.case_aborted(rmsd_row.case_id)
                                except BaseException:
                                    pass
                            raise
                        if case_observer is not None:
                            case_observer.case_finished(observed)
                        observed_rows.append(observed)
                    rows = tuple(observed_rows)
            except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
                raise PoseBustersInternalOracleEvaluationError(
                    "internal-oracle evaluation failed bounded ZIP access"
                ) from exc
    finally:
        os.close(descriptor)
    members = _implementation_source_members(rmsd)
    return PoseBustersInternalOracleEvaluationReceipt(
        archive_intake_receipt_sha256=intake.fingerprint_sha256,
        internal_rmsd_receipt_sha256=rmsd.fingerprint_sha256,
        internal_rmsd_receipt_file_sha256=_hash_bytes(rmsd_source),
        internal_execution_receipt_sha256=rmsd.execution_receipt_sha256,
        implementation_source_sha256=_canonical_sha256(dict(members)),
        implementation_source_members=members,
        runtime_identity=runtime.identity,
        configuration_sha256=(POSEBUSTERS_INTERNAL_ORACLE_CONFIGURATION_SHA256),
        case_rows=rows,
        metrics=_summary_metrics(rows),
    )


def materialize_posebusters_internal_oracle_evaluation(
    internal_rmsd_receipt_path: str | os.PathLike[str],
    execution_receipt_path: str | os.PathLike[str],
    execution_artifact_root: str | os.PathLike[str],
    preparation_receipt_path: str | os.PathLike[str],
    preparation_artifact_root: str | os.PathLike[str],
    archive_path: str | os.PathLike[str],
    selection_path: str | os.PathLike[str],
    intake_receipt_path: str | os.PathLike[str],
    corpus_audit_receipt_path: str | os.PathLike[str],
    posebusters_wheel_path: str | os.PathLike[str],
    scratch_root: str | os.PathLike[str],
    *,
    expected_internal_rmsd_receipt_sha256: str,
    contract: PoseBustersArchiveContract = OFFICIAL_POSEBUSTERS_ARCHIVE_CONTRACT,
    preparation_configuration: PoseBustersInternalPreparationConfig | None = None,
    execution_configuration: PoseBustersInternalExecutionConfig | None = None,
    rmsd_configuration: PoseBustersInternalRMSDConfig | None = None,
) -> PoseBustersInternalOracleEvaluationReceipt:
    """Apply the pinned PoseBusters oracle to every internal selected pose."""

    execution_active = (
        PoseBustersInternalExecutionConfig()
        if execution_configuration is None
        else execution_configuration
    )
    rmsd_active = (
        PoseBustersInternalRMSDConfig()
        if rmsd_configuration is None
        else rmsd_configuration
    )
    if not isinstance(execution_active, PoseBustersInternalExecutionConfig):
        raise TypeError("execution_configuration has the wrong type")
    if not isinstance(rmsd_active, PoseBustersInternalRMSDConfig):
        raise TypeError("rmsd_configuration has the wrong type")
    return _build_evaluation(
        internal_rmsd_receipt_path,
        execution_receipt_path,
        execution_artifact_root,
        preparation_receipt_path,
        preparation_artifact_root,
        archive_path,
        selection_path,
        intake_receipt_path,
        corpus_audit_receipt_path,
        posebusters_wheel_path,
        scratch_root,
        expected_internal_rmsd_receipt_sha256=(expected_internal_rmsd_receipt_sha256),
        contract=contract,
        preparation_configuration=preparation_configuration,
        execution_configuration=execution_active,
        rmsd_configuration=rmsd_active,
    )


def _verify_posebusters_internal_oracle_evaluation_receipt(
    oracle_receipt_path: str | os.PathLike[str],
    internal_rmsd_receipt_path: str | os.PathLike[str],
    execution_receipt_path: str | os.PathLike[str],
    execution_artifact_root: str | os.PathLike[str],
    preparation_receipt_path: str | os.PathLike[str],
    preparation_artifact_root: str | os.PathLike[str],
    archive_path: str | os.PathLike[str],
    selection_path: str | os.PathLike[str],
    intake_receipt_path: str | os.PathLike[str],
    corpus_audit_receipt_path: str | os.PathLike[str],
    posebusters_wheel_path: str | os.PathLike[str],
    scratch_root: str | os.PathLike[str],
    *,
    expected_internal_rmsd_receipt_sha256: str,
    contract: PoseBustersArchiveContract = OFFICIAL_POSEBUSTERS_ARCHIVE_CONTRACT,
    preparation_configuration: PoseBustersInternalPreparationConfig | None = None,
    execution_configuration: PoseBustersInternalExecutionConfig | None = None,
    rmsd_configuration: PoseBustersInternalRMSDConfig | None = None,
    case_observer: _InternalOracleCaseObserver | None = None,
) -> PoseBustersInternalOracleEvaluationReceipt:
    """Internal exact verifier with an optional non-payload observer."""

    source = _read_exact_regular_file(
        oracle_receipt_path,
        maximum_bytes=POSEBUSTERS_INTERNAL_ORACLE_MAX_RECEIPT_BYTES,
    )
    execution_active = (
        PoseBustersInternalExecutionConfig()
        if execution_configuration is None
        else execution_configuration
    )
    rmsd_active = (
        PoseBustersInternalRMSDConfig()
        if rmsd_configuration is None
        else rmsd_configuration
    )
    if not isinstance(execution_active, PoseBustersInternalExecutionConfig):
        raise TypeError("execution_configuration has the wrong type")
    if not isinstance(rmsd_active, PoseBustersInternalRMSDConfig):
        raise TypeError("rmsd_configuration has the wrong type")
    expected = _build_evaluation(
        internal_rmsd_receipt_path,
        execution_receipt_path,
        execution_artifact_root,
        preparation_receipt_path,
        preparation_artifact_root,
        archive_path,
        selection_path,
        intake_receipt_path,
        corpus_audit_receipt_path,
        posebusters_wheel_path,
        scratch_root,
        expected_internal_rmsd_receipt_sha256=(expected_internal_rmsd_receipt_sha256),
        contract=contract,
        preparation_configuration=preparation_configuration,
        execution_configuration=execution_active,
        rmsd_configuration=rmsd_active,
        case_observer=case_observer,
    )
    if source != _canonical_bytes(expected.to_dict()) + b"\n":
        raise PoseBustersInternalOracleEvaluationError(
            "internal-oracle receipt does not match exact reexecution"
        )
    return expected


def verify_posebusters_internal_oracle_evaluation_receipt(
    oracle_receipt_path: str | os.PathLike[str],
    internal_rmsd_receipt_path: str | os.PathLike[str],
    execution_receipt_path: str | os.PathLike[str],
    execution_artifact_root: str | os.PathLike[str],
    preparation_receipt_path: str | os.PathLike[str],
    preparation_artifact_root: str | os.PathLike[str],
    archive_path: str | os.PathLike[str],
    selection_path: str | os.PathLike[str],
    intake_receipt_path: str | os.PathLike[str],
    corpus_audit_receipt_path: str | os.PathLike[str],
    posebusters_wheel_path: str | os.PathLike[str],
    scratch_root: str | os.PathLike[str],
    *,
    expected_internal_rmsd_receipt_sha256: str,
    contract: PoseBustersArchiveContract = OFFICIAL_POSEBUSTERS_ARCHIVE_CONTRACT,
    preparation_configuration: PoseBustersInternalPreparationConfig | None = None,
    execution_configuration: PoseBustersInternalExecutionConfig | None = None,
    rmsd_configuration: PoseBustersInternalRMSDConfig | None = None,
) -> PoseBustersInternalOracleEvaluationReceipt:
    """Require byte-exact internal-oracle reexecution and receipt equality."""

    return _verify_posebusters_internal_oracle_evaluation_receipt(
        oracle_receipt_path,
        internal_rmsd_receipt_path,
        execution_receipt_path,
        execution_artifact_root,
        preparation_receipt_path,
        preparation_artifact_root,
        archive_path,
        selection_path,
        intake_receipt_path,
        corpus_audit_receipt_path,
        posebusters_wheel_path,
        scratch_root,
        expected_internal_rmsd_receipt_sha256=(
            expected_internal_rmsd_receipt_sha256
        ),
        contract=contract,
        preparation_configuration=preparation_configuration,
        execution_configuration=execution_configuration,
        rmsd_configuration=rmsd_configuration,
        case_observer=None,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="betelgeuze-engine-v2-posebusters-internal-oracle",
        description=("Apply the pinned PoseBusters oracle to internal selected poses."),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("materialize", "verify"):
        command = subparsers.add_parser(name)
        command.add_argument("--internal-rmsd-receipt", required=True)
        command.add_argument("--execution-receipt", required=True)
        command.add_argument("--execution-artifact-root", required=True)
        command.add_argument("--preparation-receipt", required=True)
        command.add_argument("--preparation-artifact-root", required=True)
        command.add_argument("--archive", required=True)
        command.add_argument("--selection", required=True)
        command.add_argument("--intake-receipt", required=True)
        command.add_argument("--corpus-audit-receipt", required=True)
        command.add_argument("--posebusters-wheel", required=True)
        command.add_argument("--scratch-root", required=True)
        command.add_argument(
            "--expected-internal-rmsd-receipt-sha256",
            required=True,
        )
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
    rmsd_configuration = PoseBustersInternalRMSDConfig(
        rmsd_threshold_angstrom=args.rmsd_threshold,
        top_k=args.evaluation_top_k,
    )
    common = {
        "internal_rmsd_receipt_path": args.internal_rmsd_receipt,
        "execution_receipt_path": args.execution_receipt,
        "execution_artifact_root": args.execution_artifact_root,
        "preparation_receipt_path": args.preparation_receipt,
        "preparation_artifact_root": args.preparation_artifact_root,
        "archive_path": args.archive,
        "selection_path": args.selection,
        "intake_receipt_path": args.intake_receipt,
        "corpus_audit_receipt_path": args.corpus_audit_receipt,
        "posebusters_wheel_path": args.posebusters_wheel,
        "scratch_root": args.scratch_root,
        "expected_internal_rmsd_receipt_sha256": (
            args.expected_internal_rmsd_receipt_sha256
        ),
        "execution_configuration": execution_configuration,
        "rmsd_configuration": rmsd_configuration,
    }
    if args.command == "materialize":
        if Path(args.receipt).exists():
            raise PoseBustersInternalOracleEvaluationError(
                "internal-oracle receipt output already exists"
            )
        receipt = materialize_posebusters_internal_oracle_evaluation(**common)
        receipt.write_json(args.receipt)
    else:
        receipt = verify_posebusters_internal_oracle_evaluation_receipt(
            **common,
            oracle_receipt_path=args.receipt,
        )
    print(
        json.dumps(
            {
                "receipt_sha256": receipt.fingerprint_sha256,
                "all_case_denominator": len(receipt.case_rows),
                "selected_pose_count": receipt.selected_pose_count,
                "evaluated_pose_count": receipt.evaluated_pose_count,
                "physically_valid_pose_count": (receipt.physically_valid_pose_count),
                "benchmark_executed": False,
                "claim_safe": False,
            },
            sort_keys=True,
        )
    )
    return 0


__all__ = [
    "POSEBUSTERS_INTERNAL_ORACLE_BLOCKERS",
    "POSEBUSTERS_INTERNAL_ORACLE_CASE_SCHEMA_ID",
    "POSEBUSTERS_INTERNAL_ORACLE_CONFIGURATION",
    "POSEBUSTERS_INTERNAL_ORACLE_CONFIGURATION_SHA256",
    "POSEBUSTERS_INTERNAL_ORACLE_EVALUATION_SCHEMA_ID",
    "POSEBUSTERS_INTERNAL_ORACLE_MAX_RECEIPT_BYTES",
    "POSEBUSTERS_INTERNAL_ORACLE_POSE_SCHEMA_ID",
    "PoseBustersInternalOracleCase",
    "PoseBustersInternalOracleEvaluationError",
    "PoseBustersInternalOracleEvaluationReceipt",
    "PoseBustersInternalOraclePoseResult",
    "main",
    "materialize_posebusters_internal_oracle_evaluation",
    "verify_posebusters_internal_oracle_evaluation_receipt",
]


if __name__ == "__main__":
    raise SystemExit(main())
