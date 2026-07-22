"""Claim-closed bridge-torsion docking diagnostic for the frozen four cases.

This path reuses the rigid diagnostic's failure-complete candidate evaluation,
but materializes a bounded molecular torsion tree before proposal generation.
Torsions are sampled uniformly, a fixed element-radius ligand self-overlap term
is scored, and only the initially selected Top-K receives geometry-only rigid
refinement.  It is not conformer science, force-field refinement, calibrated
docking, or a public holdout result.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Mapping

from betelgeuze_engine_v2.contracts import failure_receipt
from betelgeuze_engine_v2.docking import (
    FlexibleGeometryDiagnosticScoreConfig,
    MolecularTorsionSearchConfig,
)

from .public_protocol import FrozenPublicBenchmarkProtocol
from .public_rigid_diagnostic import (
    PublicRigidDockingCaseRow,
    PublicRigidDockingDiagnosticConfig,
    _failure_case,
    _run_case,
    _wilson_interval,
)
from .public_suite_materialization import (
    PublicBenchmarkSuiteMaterializationReceipt,
    materialize_public_benchmark_input_suite,
)


PUBLIC_FLEXIBLE_DOCKING_DIAGNOSTIC_SCHEMA_ID = (
    "betelgeuze.engine_v2_public_flexible_docking_diagnostic/1.2.0"
)
PUBLIC_FLEXIBLE_DOCKING_DIAGNOSTIC_ALGORITHM_ID = (
    "bridge_uniform_torsion_self_overlap_validity_gate_topk_rigid_refinement/1.2.0"
)
MAX_PUBLIC_FLEXIBLE_DOCKING_DIAGNOSTIC_RECEIPT_BYTES = 64 * 1024 * 1024
PUBLIC_FLEXIBLE_DOCKING_DIAGNOSTIC_BLOCKERS = (
    "four_case_contract_cohort_not_statistically_representative",
    "native_reference_coordinates_used_to_define_redocking_pocket",
    "seed_conformer_geometry_retained_as_zero_torsion_baseline",
    "bridge_only_torsion_perception_not_full_chemistry",
    "uniform_independent_torsions_not_validated_conformer_generation",
    "ring_macrocycle_and_torsion_closure_sampling_missing",
    "torsion_energy_and_bonded_internal_strain_scoring_missing",
    "supported_force_field_pose_refinement_missing",
    "topk_refinement_is_rigid_geometry_only",
    "geometry_only_score_not_force_field_energy",
    "geometry_score_weights_not_fitted_or_calibrated",
    "formal_and_partial_charge_scoring_missing",
    "aromatic_stereo_hbond_and_metal_chemistry_missing",
    "public_probability_calibration_missing",
    "same_input_vina_gnina_smina_receipts_missing",
    "independent_external_rerun_missing",
    "scientific_review_missing",
    "posebusters_benchmark_equivalence_not_established",
    "product_integration_not_qualified",
    "oracle_best_generation_metrics_not_pose_selection_metrics",
)


class PublicFlexibleDockingDiagnosticError(ValueError):
    """Flexible public diagnostic input, execution, or receipt is invalid."""


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise PublicFlexibleDockingDiagnosticError(
            "public flexible diagnostic value is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _digest(value: object, *, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise PublicFlexibleDockingDiagnosticError(
            f"{name} must be a lowercase SHA-256"
        )
    return value


@dataclass(frozen=True, slots=True)
class PublicFlexibleDockingDiagnosticConfig:
    search_and_refinement: PublicRigidDockingDiagnosticConfig = field(
        default_factory=PublicRigidDockingDiagnosticConfig
    )
    torsion_search: MolecularTorsionSearchConfig = field(
        default_factory=MolecularTorsionSearchConfig
    )
    flexible_geometry: FlexibleGeometryDiagnosticScoreConfig | None = None

    def __post_init__(self) -> None:
        if not isinstance(
            self.search_and_refinement,
            PublicRigidDockingDiagnosticConfig,
        ):
            raise PublicFlexibleDockingDiagnosticError(
                "search_and_refinement must be PublicRigidDockingDiagnosticConfig"
            )
        if not isinstance(self.torsion_search, MolecularTorsionSearchConfig):
            raise PublicFlexibleDockingDiagnosticError(
                "torsion_search must be MolecularTorsionSearchConfig"
            )
        flexible_geometry = self.flexible_geometry
        if flexible_geometry is None:
            flexible_geometry = FlexibleGeometryDiagnosticScoreConfig(
                base_geometry=self.search_and_refinement.geometry_score
            )
        if not isinstance(
            flexible_geometry,
            FlexibleGeometryDiagnosticScoreConfig,
        ):
            raise PublicFlexibleDockingDiagnosticError(
                "flexible_geometry must be FlexibleGeometryDiagnosticScoreConfig"
            )
        if (
            flexible_geometry.base_geometry
            != self.search_and_refinement.geometry_score
        ):
            raise PublicFlexibleDockingDiagnosticError(
                "flexible and search geometry-score configurations disagree"
            )
        object.__setattr__(self, "flexible_geometry", flexible_geometry)

    def to_dict(self) -> dict[str, object]:
        assert self.flexible_geometry is not None
        base = self.search_and_refinement.to_dict()
        base.update(
            {
                "diagnostic_mode": (
                    "bridge_torsion_generation_with_topk_rigid_geometry_refinement"
                ),
                "max_torsions": self.torsion_search.max_rotatable_bonds,
                "torsion_budget_policy": (
                    "all_perceived_variables_up_to_configured_maximum"
                ),
                "torsion_search": self.torsion_search.to_dict(),
                "flexible_geometry_score": self.flexible_geometry.to_dict(),
                "final_selection_policy": (
                    "score_order_after_excluding_invalid_poses_then_direct_rmsd_diversity"
                ),
                "torsion_refinement_performed": False,
                "flexible_internal_self_overlap_scored": True,
                "force_field_internal_strain_scored": False,
            }
        )
        return base

    @property
    def fingerprint_sha256(self) -> str:
        return _sha256(self.to_dict())


@dataclass(frozen=True, slots=True)
class PublicFlexibleDockingDiagnosticReport:
    protocol_sha256: str
    input_suite_receipt_sha256: str
    config: PublicFlexibleDockingDiagnosticConfig
    case_rows: tuple[PublicRigidDockingCaseRow, ...]
    scientific_blockers: tuple[str, ...] = (
        PUBLIC_FLEXIBLE_DOCKING_DIAGNOSTIC_BLOCKERS
    )
    schema_id: str = PUBLIC_FLEXIBLE_DOCKING_DIAGNOSTIC_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != PUBLIC_FLEXIBLE_DOCKING_DIAGNOSTIC_SCHEMA_ID:
            raise PublicFlexibleDockingDiagnosticError(
                "unsupported public flexible diagnostic schema"
            )
        _digest(self.protocol_sha256, name="protocol_sha256")
        _digest(
            self.input_suite_receipt_sha256,
            name="input_suite_receipt_sha256",
        )
        if not isinstance(self.config, PublicFlexibleDockingDiagnosticConfig):
            raise PublicFlexibleDockingDiagnosticError(
                "config must be PublicFlexibleDockingDiagnosticConfig"
            )
        rows = tuple(self.case_rows)
        case_ids = tuple(row.case_id for row in rows)
        if len(rows) != 4 or case_ids != tuple(sorted(set(case_ids))):
            raise PublicFlexibleDockingDiagnosticError(
                "public flexible report must retain four uniquely sorted cases"
            )
        if (
            tuple(self.scientific_blockers)
            != PUBLIC_FLEXIBLE_DOCKING_DIAGNOSTIC_BLOCKERS
        ):
            raise PublicFlexibleDockingDiagnosticError(
                "public flexible scientific blockers cannot be promoted"
            )
        object.__setattr__(self, "case_rows", rows)

    @property
    def executed_case_count(self) -> int:
        return sum(row.status != "failure" for row in self.case_rows)

    @property
    def successful_case_count(self) -> int:
        return sum(row.status == "success" for row in self.case_rows)

    @property
    def candidate_count(self) -> int:
        return sum(len(row.candidate_rows) for row in self.case_rows)

    @property
    def evaluated_candidate_count(self) -> int:
        return sum(
            candidate.status == "evaluated"
            for row in self.case_rows
            for candidate in row.candidate_rows
        )

    @property
    def valid_candidate_count(self) -> int:
        return sum(
            candidate.valid
            for row in self.case_rows
            for candidate in row.candidate_rows
        )

    @property
    def top1_success_count(self) -> int:
        return sum(row.summary.get("top1_success") is True for row in self.case_rows)

    @property
    def top5_success_count(self) -> int:
        return sum(row.summary.get("top5_success") is True for row in self.case_rows)

    @property
    def generated_primary_hit_case_count(self) -> int:
        return sum(
            int(row.summary.get("generated_primary_hit_count", 0)) > 0
            for row in self.case_rows
        )

    @property
    def torsion_sampling_case_count(self) -> int:
        return sum(
            row.summary.get("torsion_sampling_performed") is True
            for row in self.case_rows
        )

    @property
    def torsion_variable_count_total(self) -> int:
        return sum(
            int(row.summary.get("torsion_variable_count", 0))
            for row in self.case_rows
        )

    @property
    def refinement_candidate_count(self) -> int:
        return sum(
            int(row.summary.get("refinement_candidate_count", 0))
            for row in self.case_rows
        )

    @property
    def refinement_success_count(self) -> int:
        return sum(
            int(row.summary.get("refinement_success_count", 0))
            for row in self.case_rows
        )

    @property
    def refinement_failure_count(self) -> int:
        return sum(
            int(row.summary.get("refinement_failure_count", 0))
            for row in self.case_rows
        )

    @property
    def claim_safe(self) -> bool:
        return False

    def _payload(self) -> dict[str, object]:
        case_count = len(self.case_rows)
        top1_interval = _wilson_interval(self.top1_success_count, case_count)
        top5_interval = _wilson_interval(self.top5_success_count, case_count)
        valid_pose_rate = (
            self.valid_candidate_count / self.candidate_count
            if self.candidate_count
            else 0.0
        )
        return {
            "schema_id": self.schema_id,
            "algorithm_id": PUBLIC_FLEXIBLE_DOCKING_DIAGNOSTIC_ALGORITHM_ID,
            "protocol_sha256": self.protocol_sha256,
            "input_suite_receipt_sha256": self.input_suite_receipt_sha256,
            "config": self.config.to_dict(),
            "config_sha256": self.config.fingerprint_sha256,
            "case_rows": [row.to_dict() for row in self.case_rows],
            "case_count": case_count,
            "executed_case_count": self.executed_case_count,
            "successful_case_count": self.successful_case_count,
            "candidate_count": self.candidate_count,
            "evaluated_candidate_count": self.evaluated_candidate_count,
            "valid_candidate_count": self.valid_candidate_count,
            "valid_pose_rate_all_generated": valid_pose_rate,
            "torsion_sampling_case_count": self.torsion_sampling_case_count,
            "torsion_variable_count_total": self.torsion_variable_count_total,
            "flexible_pose_generation_performed": (
                self.torsion_sampling_case_count > 0
            ),
            "torsion_refinement_performed": False,
            "flexible_internal_self_overlap_scored": True,
            "force_field_internal_strain_scored": False,
            "validity_gated_final_selection": True,
            "refinement_candidate_count": self.refinement_candidate_count,
            "refinement_success_count": self.refinement_success_count,
            "refinement_failure_count": self.refinement_failure_count,
            "rigid_refinement_performed": self.refinement_success_count > 0,
            "top1_success_count": self.top1_success_count,
            "top1_success_rate_all_cases": self.top1_success_count / case_count,
            "top1_success_rate_wilson95": list(top1_interval),
            "top5_success_count": self.top5_success_count,
            "top5_success_rate_all_cases": self.top5_success_count / case_count,
            "top5_success_rate_wilson95": list(top5_interval),
            "generated_primary_hit_case_count": (
                self.generated_primary_hit_case_count
            ),
            "generated_primary_hit_case_rate_all_cases": (
                self.generated_primary_hit_case_count / case_count
            ),
            "failure_rows_retained": True,
            "case_denominator": "all_four_protocol_cases",
            "candidate_denominator": "all_generated_candidates",
            "diagnostic_execution_performed": self.executed_case_count > 0,
            "docking_predictions_present": self.evaluated_candidate_count > 0,
            "pose_validity_evaluated": self.evaluated_candidate_count > 0,
            "public_benchmark_executed": False,
            "public_holdout_result_established": False,
            "probability_calibrated": False,
            "scientifically_validated": False,
            "benchmark_validated": False,
            "customer_execution_enabled": False,
            "scientific_blockers": list(self.scientific_blockers),
            "claim_safe": False,
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _sha256(self._payload())

    def to_dict(self) -> dict[str, object]:
        return {**self._payload(), "report_sha256": self.fingerprint_sha256}

    def to_json_bytes(self) -> bytes:
        result = _canonical_bytes(self.to_dict()) + b"\n"
        if len(result) > MAX_PUBLIC_FLEXIBLE_DOCKING_DIAGNOSTIC_RECEIPT_BYTES:
            raise PublicFlexibleDockingDiagnosticError(
                "public flexible diagnostic receipt exceeds its size bound"
            )
        return result

    def require_protocol(
        self,
        protocol: FrozenPublicBenchmarkProtocol,
        suite: PublicBenchmarkSuiteMaterializationReceipt,
    ) -> "PublicFlexibleDockingDiagnosticReport":
        suite.require_protocol(protocol)
        if (
            self.protocol_sha256 != protocol.protocol_sha256
            or self.input_suite_receipt_sha256 != suite.fingerprint_sha256
            or tuple(row.case_id for row in self.case_rows)
            != tuple(case.case_id for case in protocol.cases)
            or any(
                row.case_input_sha256 != case.input_sha256
                for row, case in zip(self.case_rows, protocol.cases, strict=True)
            )
        ):
            raise PublicFlexibleDockingDiagnosticError(
                "public flexible diagnostic report disagrees with its protocol inputs"
            )
        return self


def run_public_flexible_docking_diagnostic(
    protocol: FrozenPublicBenchmarkProtocol,
    artifacts_by_relative_path: Mapping[str, bytes],
    *,
    config: PublicFlexibleDockingDiagnosticConfig | None = None,
) -> PublicFlexibleDockingDiagnosticReport:
    """Execute bridge-torsion generation with all case/candidate failures."""

    if not isinstance(protocol, FrozenPublicBenchmarkProtocol):
        raise PublicFlexibleDockingDiagnosticError(
            "protocol must be FrozenPublicBenchmarkProtocol"
        )
    active = PublicFlexibleDockingDiagnosticConfig() if config is None else config
    if not isinstance(active, PublicFlexibleDockingDiagnosticConfig):
        raise PublicFlexibleDockingDiagnosticError(
            "config must be PublicFlexibleDockingDiagnosticConfig"
        )
    suite = materialize_public_benchmark_input_suite(
        protocol,
        artifacts_by_relative_path,
    )
    rows: list[PublicRigidDockingCaseRow] = []
    assert active.flexible_geometry is not None
    for index, case in enumerate(protocol.cases):
        try:
            rows.append(
                _run_case(
                    case,
                    suite,
                    artifacts_by_relative_path,
                    active.search_and_refinement,
                    case_index=index,
                    torsion_search_config=active.torsion_search,
                    flexible_geometry_score_config=active.flexible_geometry,
                    validity_gated_selection=True,
                )
            )
        except Exception as exc:
            failure = failure_receipt(
                exc,
                public_message="public flexible case execution failed",
            )
            rows.append(
                _failure_case(
                    case,
                    error_code=failure.public_error_code,
                    private_error_sha256=failure.private_error_sha256,
                )
            )
    report = PublicFlexibleDockingDiagnosticReport(
        protocol_sha256=protocol.protocol_sha256,
        input_suite_receipt_sha256=suite.fingerprint_sha256,
        config=active,
        case_rows=tuple(rows),
    )
    return report.require_protocol(protocol, suite)


def write_public_flexible_docking_diagnostic_report(
    report: PublicFlexibleDockingDiagnosticReport,
    output_path: str | os.PathLike[str],
) -> Path:
    """Write a private report and refuse to replace an existing path."""

    if not isinstance(report, PublicFlexibleDockingDiagnosticReport):
        raise PublicFlexibleDockingDiagnosticError(
            "report must be PublicFlexibleDockingDiagnosticReport"
        )
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output.name}.",
        suffix=".tmp",
        dir=str(output.parent),
    )
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(report.to_json_bytes())
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary_name, output, follow_symlinks=False)
        except FileExistsError as exc:
            raise PublicFlexibleDockingDiagnosticError(
                "public flexible diagnostic output already exists"
            ) from exc
    finally:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
    return output


__all__ = [
    "MAX_PUBLIC_FLEXIBLE_DOCKING_DIAGNOSTIC_RECEIPT_BYTES",
    "PUBLIC_FLEXIBLE_DOCKING_DIAGNOSTIC_ALGORITHM_ID",
    "PUBLIC_FLEXIBLE_DOCKING_DIAGNOSTIC_BLOCKERS",
    "PUBLIC_FLEXIBLE_DOCKING_DIAGNOSTIC_SCHEMA_ID",
    "PublicFlexibleDockingDiagnosticConfig",
    "PublicFlexibleDockingDiagnosticError",
    "PublicFlexibleDockingDiagnosticReport",
    "run_public_flexible_docking_diagnostic",
    "write_public_flexible_docking_diagnostic_report",
]
