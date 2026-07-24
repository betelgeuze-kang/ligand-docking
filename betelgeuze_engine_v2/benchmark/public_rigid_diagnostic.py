"""Failure-inclusive rigid-body redocking diagnostic for the frozen four cases.

This is an executable bridge from verified public inputs to generated poses,
geometric validity rows, and receptor-frame symmetry-aware RMSD.  It is not a
calibrated docking engine: native references define the redocking pocket,
ligands remain rigid, the score and top-k rigid refinement are geometry-only
diagnostics, and supported-force-field refinement, charge-aware physics,
torsion sampling, external baselines, and independent review are absent.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
import hashlib
import json
import math
from numbers import Integral, Real
import os
from pathlib import Path
import tempfile
from typing import Mapping

import torch

from betelgeuze_engine_v2.ai import axis_angle_matrix
from betelgeuze_engine_v2.contracts import failure_receipt
from betelgeuze_engine_v2.docking import (
    DockingBudget,
    DockingProposal,
    DockingProblemIdentity,
    DockingScoreBreakdown,
    ElementFlexibleGeometryDiagnosticScorer,
    ElementGeometryDiagnosticScoreConfig,
    ElementGeometryDiagnosticScorer,
    FlexibleGeometryDiagnosticScoreConfig,
    GeometricRigidBodyRefiner,
    GeometricRigidRefinementConfig,
    GeometricRigidRefinementReceipt,
    MolecularTorsionSearchConfig,
    PoseValidityConfig,
    PoseValidityContext,
    TorsionSearchSpace,
    direct_rmsd,
    build_molecular_torsion_search_space,
    run_bounded_docking_search,
)
from betelgeuze_engine_v2.io import parse_pdb, parse_sdf_v2000
from betelgeuze_engine_v2.molecular import canonical_system_sha256

from .public_materialization import minimum_public_reference_rmsd
from .public_protocol import (
    PRIMARY_RMSD_THRESHOLD_ANGSTROM,
    FrozenPublicBenchmarkProtocol,
    PublicBenchmarkCaseDefinition,
    require_public_benchmark_case_metrics,
)
from .public_suite_materialization import (
    PublicBenchmarkSuiteMaterializationReceipt,
    materialize_public_benchmark_input_suite,
)


PUBLIC_RIGID_DOCKING_DIAGNOSTIC_SCHEMA_ID = (
    "betelgeuze.engine_v2_public_rigid_docking_diagnostic/1.3.0"
)
PUBLIC_RIGID_DOCKING_DIAGNOSTIC_ALGORITHM_ID = (
    "first_native_record_rigid_geometry_search_and_topk_refinement/1.2.0"
)
MAX_PUBLIC_RIGID_DOCKING_DIAGNOSTIC_RECEIPT_BYTES = 64 * 1024 * 1024

PUBLIC_RIGID_DOCKING_DIAGNOSTIC_BLOCKERS = (
    "four_case_contract_cohort_not_statistically_representative",
    "native_reference_coordinates_used_to_define_redocking_pocket",
    "seed_conformer_geometry_used_after_fixed_rigid_deleak_rotation",
    "rigid_body_only_torsion_sampling_missing",
    "supported_force_field_pose_refinement_missing",
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

_FIXED_DELEAK_ROTATION_AXIS = (1.0, 2.0, 3.0)
_FIXED_DELEAK_ROTATION_ANGLE_RADIANS = 1.23456789


class PublicRigidDockingDiagnosticError(ValueError):
    """Public rigid diagnostic input, execution, or receipt is invalid."""


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
        raise PublicRigidDockingDiagnosticError(
            "public rigid diagnostic value is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _digest(value: object, *, name: str, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise PublicRigidDockingDiagnosticError(f"{name} must be a SHA-256")
    result = value.strip().lower()
    if allow_empty and not result:
        return ""
    if len(result) != 64 or any(character not in "0123456789abcdef" for character in result):
        raise PublicRigidDockingDiagnosticError(
            f"{name} must be a lowercase SHA-256"
        )
    return result


def _exact_int(value: object, *, name: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise PublicRigidDockingDiagnosticError(f"{name} must be an integer")
    result = int(value)
    if result < minimum:
        raise PublicRigidDockingDiagnosticError(
            f"{name} must be at least {minimum}"
        )
    return result


def _finite(value: object, *, name: str, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise PublicRigidDockingDiagnosticError(f"{name} must be a real number")
    result = float(value)
    if not math.isfinite(result) or (positive and result <= 0.0):
        condition = "positive and finite" if positive else "finite"
        raise PublicRigidDockingDiagnosticError(f"{name} must be {condition}")
    return result


def _float_vector(value: torch.Tensor) -> tuple[float, float, float]:
    row = value.detach().to(dtype=torch.float64, device="cpu").reshape(3).tolist()
    return (float(row[0]), float(row[1]), float(row[2]))


def _wilson_interval(successes: int, total: int) -> tuple[float, float]:
    if total < 1:
        return (0.0, 1.0)
    z = 1.959963984540054
    proportion = successes / total
    denominator = 1.0 + z * z / total
    center = (proportion + z * z / (2.0 * total)) / denominator
    radius = (
        z
        * math.sqrt(
            proportion * (1.0 - proportion) / total
            + z * z / (4.0 * total * total)
        )
        / denominator
    )
    return (max(0.0, center - radius), min(1.0, center + radius))


@dataclass(frozen=True, slots=True)
class PublicRigidDockingDiagnosticConfig:
    candidate_count: int = 256
    top_k: int = 5
    translation_radius_angstrom: float = 4.5
    diversity_rmsd_angstrom: float = 0.5
    seed: int = 23_017
    refinement_steps: int = 8
    geometry_score: ElementGeometryDiagnosticScoreConfig = field(
        default_factory=ElementGeometryDiagnosticScoreConfig
    )
    rigid_refinement: GeometricRigidRefinementConfig = field(
        default_factory=GeometricRigidRefinementConfig
    )

    def __post_init__(self) -> None:
        candidate_count = _exact_int(
            self.candidate_count,
            name="candidate_count",
            minimum=1,
        )
        top_k = _exact_int(self.top_k, name="top_k", minimum=1)
        if top_k > candidate_count or top_k > 128:
            raise PublicRigidDockingDiagnosticError(
                "top_k must not exceed candidate_count or 128"
            )
        translation = _finite(
            self.translation_radius_angstrom,
            name="translation_radius_angstrom",
            positive=True,
        )
        diversity = _finite(
            self.diversity_rmsd_angstrom,
            name="diversity_rmsd_angstrom",
        )
        if diversity < 0.0:
            raise PublicRigidDockingDiagnosticError(
                "diversity_rmsd_angstrom must be non-negative"
            )
        if not isinstance(self.geometry_score, ElementGeometryDiagnosticScoreConfig):
            raise PublicRigidDockingDiagnosticError(
                "geometry_score must be ElementGeometryDiagnosticScoreConfig"
            )
        refinement_steps = _exact_int(
            self.refinement_steps,
            name="refinement_steps",
            minimum=1,
        )
        if not isinstance(self.rigid_refinement, GeometricRigidRefinementConfig):
            raise PublicRigidDockingDiagnosticError(
                "rigid_refinement must be GeometricRigidRefinementConfig"
            )
        if refinement_steps > self.rigid_refinement.maximum_steps:
            raise PublicRigidDockingDiagnosticError(
                "refinement_steps exceeds the rigid-refinement bound"
            )
        if translation >= self.geometry_score.pocket_radius_angstrom:
            raise PublicRigidDockingDiagnosticError(
                "translation radius must remain inside the declared pocket radius"
            )
        object.__setattr__(self, "candidate_count", candidate_count)
        object.__setattr__(self, "top_k", top_k)
        object.__setattr__(self, "translation_radius_angstrom", translation)
        object.__setattr__(self, "diversity_rmsd_angstrom", diversity)
        object.__setattr__(self, "seed", int(self.seed))
        object.__setattr__(self, "refinement_steps", refinement_steps)

    def to_dict(self) -> dict[str, object]:
        return {
            "candidate_count": self.candidate_count,
            "top_k": self.top_k,
            "translation_radius_angstrom": self.translation_radius_angstrom,
            "diversity_rmsd_angstrom": self.diversity_rmsd_angstrom,
            "seed": self.seed,
            "max_torsions": 0,
            "max_refinement_steps": self.refinement_steps,
            "refinement_candidate_policy": "initial_diverse_score_top_k_only",
            "geometry_score": self.geometry_score.to_dict(),
            "rigid_refinement": self.rigid_refinement.to_dict(),
            "fixed_deleak_rotation_axis": list(_FIXED_DELEAK_ROTATION_AXIS),
            "fixed_deleak_rotation_angle_radians": (
                _FIXED_DELEAK_ROTATION_ANGLE_RADIANS
            ),
            "pocket_center_policy": (
                "centroid_of_lowest_record_index_graph_matched_native_reference"
            ),
            "seed_coordinate_policy": (
                "center_seed_heavy_centroid_then_apply_fixed_non_identity_rotation"
            ),
            "receptor_cell_policy": "discard_cryst1_for_nonperiodic_diagnostic",
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _sha256(self.to_dict())


@dataclass(frozen=True, slots=True)
class PublicRigidDockingCandidateRow:
    candidate_id: str
    proposal_index: int
    status: str
    selected_rank: int
    score_rank: int
    score: float | None
    proposal_fingerprint_sha256: str
    result_proposal_fingerprint_sha256: str
    score_breakdown: Mapping[str, object] | None
    refined: bool
    refinement_receipt_sha256: str
    refinement_receipt: Mapping[str, object] | None
    validity: Mapping[str, object] | None
    rmsd: Mapping[str, object] | None
    primary_success: bool
    error_code: str = ""
    private_error_sha256: str = ""

    def __post_init__(self) -> None:
        if self.status not in {
            "evaluated",
            "search_failure",
            "refinement_failure",
            "evaluation_failure",
        }:
            raise PublicRigidDockingDiagnosticError(
                "public rigid candidate status is invalid"
            )
        _exact_int(self.proposal_index, name="proposal_index")
        _exact_int(self.selected_rank, name="selected_rank")
        _exact_int(self.score_rank, name="score_rank")
        _digest(
            self.proposal_fingerprint_sha256,
            name="proposal_fingerprint_sha256",
        )
        _digest(
            self.result_proposal_fingerprint_sha256,
            name="result_proposal_fingerprint_sha256",
            allow_empty=self.status != "evaluated",
        )
        _digest(
            self.private_error_sha256,
            name="private_error_sha256",
            allow_empty=self.status == "evaluated",
        )
        if not isinstance(self.refined, bool):
            raise PublicRigidDockingDiagnosticError(
                "public rigid candidate refined flag must be boolean"
            )
        refinement_digest = _digest(
            self.refinement_receipt_sha256,
            name="refinement_receipt_sha256",
            allow_empty=not self.refined,
        )
        if self.refined != (self.refinement_receipt is not None):
            raise PublicRigidDockingDiagnosticError(
                "public rigid refinement flag and receipt disagree"
            )
        if not self.refined and refinement_digest:
            raise PublicRigidDockingDiagnosticError(
                "unrefined public rigid candidate cannot name a refinement receipt"
            )
        if self.refined and (
            not refinement_digest
            or self.refinement_receipt.get("receipt_sha256") != refinement_digest
        ):
            raise PublicRigidDockingDiagnosticError(
                "public rigid refinement receipt identity is inconsistent"
            )
        if self.status == "refinement_failure" and self.refined:
            raise PublicRigidDockingDiagnosticError(
                "failed public rigid refinement cannot produce a refined candidate"
            )
        if self.status == "evaluated":
            if (
                self.score is None
                or not math.isfinite(float(self.score))
                or self.score_breakdown is None
                or self.validity is None
                or self.rmsd is None
                or self.error_code
                or self.private_error_sha256
            ):
                raise PublicRigidDockingDiagnosticError(
                    "evaluated public rigid candidate is incomplete"
                )
        elif (
            not self.error_code
            or self.primary_success
            or self.validity is not None
            or self.rmsd is not None
        ):
            raise PublicRigidDockingDiagnosticError(
                "failed public rigid candidate row is inconsistent"
            )

    @property
    def valid(self) -> bool:
        return bool(self.validity is not None and self.validity.get("valid") is True)

    @property
    def rmsd_angstrom(self) -> float | None:
        if self.rmsd is None:
            return None
        return float(self.rmsd["rmsd_angstrom"])

    def to_dict(self) -> dict[str, object]:
        return {
            "candidate_id": self.candidate_id,
            "proposal_index": self.proposal_index,
            "status": self.status,
            "selected_rank": self.selected_rank,
            "score_rank": self.score_rank,
            "score": self.score,
            "proposal_fingerprint_sha256": self.proposal_fingerprint_sha256,
            "result_proposal_fingerprint_sha256": (
                self.result_proposal_fingerprint_sha256
            ),
            "score_breakdown": (
                None if self.score_breakdown is None else dict(self.score_breakdown)
            ),
            "refined": self.refined,
            "refinement_receipt_sha256": self.refinement_receipt_sha256,
            "refinement_receipt": (
                None
                if self.refinement_receipt is None
                else dict(self.refinement_receipt)
            ),
            "validity": None if self.validity is None else dict(self.validity),
            "rmsd": None if self.rmsd is None else dict(self.rmsd),
            "valid": self.valid,
            "primary_success": self.primary_success,
            "error_code": self.error_code,
            "private_error_sha256": self.private_error_sha256,
        }


@dataclass(frozen=True, slots=True)
class PublicRigidDockingCaseRow:
    case_id: str
    pdb_id: str
    case_input_sha256: str
    status: str
    pocket_definition_sha256: str
    pocket_center_receptor_frame_angstrom: tuple[float, float, float]
    discarded_cryst1_record_count: int
    receptor_atom_count: int
    receptor_shell_atom_count: int
    validity_receptor_atom_count: int
    ligand_atom_count: int
    ligand_heavy_atom_count: int
    candidate_rows: tuple[PublicRigidDockingCandidateRow, ...]
    summary: Mapping[str, object]
    error_code: str = ""
    private_error_sha256: str = ""

    def __post_init__(self) -> None:
        if self.status not in {"success", "partial_failure", "failure"}:
            raise PublicRigidDockingDiagnosticError(
                "public rigid case status is invalid"
            )
        _digest(self.case_input_sha256, name="case_input_sha256")
        _digest(
            self.pocket_definition_sha256,
            name="pocket_definition_sha256",
            allow_empty=self.status == "failure",
        )
        center = tuple(
            _finite(value, name="pocket center")
            for value in self.pocket_center_receptor_frame_angstrom
        )
        if len(center) != 3:
            raise PublicRigidDockingDiagnosticError(
                "pocket center must contain three values"
            )
        for name in (
            "discarded_cryst1_record_count",
            "receptor_atom_count",
            "receptor_shell_atom_count",
            "validity_receptor_atom_count",
            "ligand_atom_count",
            "ligand_heavy_atom_count",
        ):
            _exact_int(getattr(self, name), name=name)
        rows = tuple(self.candidate_rows)
        if rows and tuple(row.proposal_index for row in rows) != tuple(range(len(rows))):
            raise PublicRigidDockingDiagnosticError(
                "public rigid candidate rows must retain proposal order"
            )
        ranks = sorted(row.selected_rank for row in rows if row.selected_rank > 0)
        if ranks != list(range(1, len(ranks) + 1)):
            raise PublicRigidDockingDiagnosticError(
                "public rigid selected ranks must be contiguous"
            )
        if self.status == "failure" and (rows or not self.error_code):
            raise PublicRigidDockingDiagnosticError(
                "failed public rigid case must have no candidate rows and an error"
            )
        if self.status != "failure" and (not rows or self.error_code):
            raise PublicRigidDockingDiagnosticError(
                "executed public rigid case row is inconsistent"
            )
        object.__setattr__(
            self,
            "pocket_center_receptor_frame_angstrom",
            center,
        )
        object.__setattr__(self, "candidate_rows", rows)
        object.__setattr__(self, "summary", dict(self.summary))

    @property
    def execution_succeeded(self) -> bool:
        return self.status == "success"

    def to_dict(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "pdb_id": self.pdb_id,
            "case_input_sha256": self.case_input_sha256,
            "status": self.status,
            "execution_succeeded": self.execution_succeeded,
            "pocket_definition_sha256": self.pocket_definition_sha256,
            "pocket_center_receptor_frame_angstrom": list(
                self.pocket_center_receptor_frame_angstrom
            ),
            "discarded_cryst1_record_count": self.discarded_cryst1_record_count,
            "receptor_atom_count": self.receptor_atom_count,
            "receptor_shell_atom_count": self.receptor_shell_atom_count,
            "validity_receptor_atom_count": self.validity_receptor_atom_count,
            "ligand_atom_count": self.ligand_atom_count,
            "ligand_heavy_atom_count": self.ligand_heavy_atom_count,
            "candidate_rows": [row.to_dict() for row in self.candidate_rows],
            "summary": dict(self.summary),
            "error_code": self.error_code,
            "private_error_sha256": self.private_error_sha256,
        }


@dataclass(frozen=True, slots=True)
class PublicRigidDockingDiagnosticReport:
    protocol_sha256: str
    input_suite_receipt_sha256: str
    config: PublicRigidDockingDiagnosticConfig
    case_rows: tuple[PublicRigidDockingCaseRow, ...]
    scientific_blockers: tuple[str, ...] = PUBLIC_RIGID_DOCKING_DIAGNOSTIC_BLOCKERS
    schema_id: str = PUBLIC_RIGID_DOCKING_DIAGNOSTIC_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != PUBLIC_RIGID_DOCKING_DIAGNOSTIC_SCHEMA_ID:
            raise PublicRigidDockingDiagnosticError(
                "unsupported public rigid diagnostic schema"
            )
        _digest(self.protocol_sha256, name="protocol_sha256")
        _digest(
            self.input_suite_receipt_sha256,
            name="input_suite_receipt_sha256",
        )
        if not isinstance(self.config, PublicRigidDockingDiagnosticConfig):
            raise PublicRigidDockingDiagnosticError(
                "config must be PublicRigidDockingDiagnosticConfig"
            )
        rows = tuple(self.case_rows)
        case_ids = tuple(row.case_id for row in rows)
        if len(rows) != 4 or case_ids != tuple(sorted(set(case_ids))):
            raise PublicRigidDockingDiagnosticError(
                "public rigid report must retain four uniquely sorted cases"
            )
        if tuple(self.scientific_blockers) != PUBLIC_RIGID_DOCKING_DIAGNOSTIC_BLOCKERS:
            raise PublicRigidDockingDiagnosticError(
                "public rigid scientific blockers cannot be promoted"
            )
        object.__setattr__(self, "case_rows", rows)

    @property
    def executed_case_count(self) -> int:
        return sum(row.status != "failure" for row in self.case_rows)

    @property
    def successful_case_count(self) -> int:
        return sum(row.execution_succeeded for row in self.case_rows)

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
            "algorithm_id": PUBLIC_RIGID_DOCKING_DIAGNOSTIC_ALGORITHM_ID,
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
            "refinement_candidate_count": self.refinement_candidate_count,
            "refinement_success_count": self.refinement_success_count,
            "refinement_failure_count": self.refinement_failure_count,
            "rigid_refinement_performed": self.refinement_success_count > 0,
            "rigid_refinement_failure_rows_retained": True,
            "valid_pose_rate_all_generated": valid_pose_rate,
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
        if len(result) > MAX_PUBLIC_RIGID_DOCKING_DIAGNOSTIC_RECEIPT_BYTES:
            raise PublicRigidDockingDiagnosticError(
                "public rigid diagnostic receipt exceeds its size bound"
            )
        return result

    def require_protocol(
        self,
        protocol: FrozenPublicBenchmarkProtocol,
        suite: PublicBenchmarkSuiteMaterializationReceipt,
    ) -> "PublicRigidDockingDiagnosticReport":
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
            raise PublicRigidDockingDiagnosticError(
                "public rigid diagnostic report disagrees with its protocol inputs"
            )
        return self


def _discard_cryst1(source: bytes) -> tuple[bytes, int]:
    lines = source.splitlines(keepends=True)
    retained: list[bytes] = []
    count = 0
    for line in lines:
        if line[:6].strip().upper() == b"CRYST1":
            count += 1
        else:
            retained.append(line)
    return b"".join(retained), count


def _fixed_deleak_rotation(dtype: torch.dtype) -> torch.Tensor:
    axis = torch.tensor([_FIXED_DELEAK_ROTATION_AXIS], dtype=dtype)
    angle = torch.tensor([_FIXED_DELEAK_ROTATION_ANGLE_RADIANS], dtype=dtype)
    return axis_angle_matrix(axis, angle)[0]


def _pocket_center(materialization) -> torch.Tensor:
    first = min(materialization.reference_poses, key=lambda pose: pose.record_index)
    return first.reference_coordinates_seed_heavy_order.mean(dim=0).to(
        dtype=torch.float64,
        device="cpu",
    )


def _pocket_definition_sha256(
    case: PublicBenchmarkCaseDefinition,
    materialization_sha256: str,
    center: torch.Tensor,
) -> str:
    return _sha256(
        {
            "case_input_sha256": case.input_sha256,
            "materialization_sha256": materialization_sha256,
            "center_policy": (
                "centroid_of_lowest_record_index_graph_matched_native_reference"
            ),
            "center_binary64_hex": [float(value).hex() for value in center.tolist()],
            "coordinate_frame": "raw_receptor_input_frame",
        }
    )


def _rigid_search_space(coordinates: torch.Tensor) -> TorsionSearchSpace:
    atom_count = int(coordinates.shape[0])
    return TorsionSearchSpace(
        local_offsets=torch.zeros_like(coordinates),
        parent=torch.full((atom_count,), -1, dtype=torch.long),
        local_axes=torch.tensor(
            [[0.0, 0.0, 1.0]] * atom_count,
            dtype=coordinates.dtype,
        ),
        rotatable_mask=torch.zeros(atom_count, dtype=torch.bool),
        root_positions=coordinates,
    )


def _failure_case(
    case: PublicBenchmarkCaseDefinition,
    *,
    error_code: str,
    private_error_sha256: str = "",
) -> PublicRigidDockingCaseRow:
    return PublicRigidDockingCaseRow(
        case_id=case.case_id,
        pdb_id=case.pdb_id,
        case_input_sha256=case.input_sha256,
        status="failure",
        pocket_definition_sha256="",
        pocket_center_receptor_frame_angstrom=(0.0, 0.0, 0.0),
        discarded_cryst1_record_count=0,
        receptor_atom_count=0,
        receptor_shell_atom_count=0,
        validity_receptor_atom_count=0,
        ligand_atom_count=0,
        ligand_heavy_atom_count=0,
        candidate_rows=(),
        summary={
            "top1_success": False,
            "top5_success": False,
            "metric_available": False,
        },
        error_code=error_code,
        private_error_sha256=private_error_sha256,
    )


def _run_case(
    case: PublicBenchmarkCaseDefinition,
    suite: PublicBenchmarkSuiteMaterializationReceipt,
    artifacts: Mapping[str, bytes],
    config: PublicRigidDockingDiagnosticConfig,
    *,
    case_index: int,
    torsion_search_config: MolecularTorsionSearchConfig | None = None,
    flexible_geometry_score_config: FlexibleGeometryDiagnosticScoreConfig
    | None = None,
    validity_gated_selection: bool = False,
) -> PublicRigidDockingCaseRow:
    suite_row = suite.case_rows[case_index]
    if not suite_row.ready_for_rmsd or suite_row.materialization is None:
        return _failure_case(
            case,
            error_code="public_input_reference_materialization_not_ready",
        )
    materialization = suite_row.materialization
    receptor_source, discarded_cryst1 = _discard_cryst1(
        artifacts[case.receptor.relative_path]
    )
    receptor = parse_pdb(
        receptor_source,
        source_id=f"{case.case_id}:nonperiodic-receptor",
        dtype=torch.float64,
        device="cpu",
    )
    ligand = parse_sdf_v2000(
        artifacts[case.ligand_identity_seed.relative_path],
        source_id=f"{case.case_id}:identity-seed",
        dtype=torch.float64,
        device="cpu",
    )
    if (
        ligand.atom_count != materialization.seed_atom_count
        or tuple(
            atom.index for atom in ligand.atoms if atom.atomic_number != 1
        )
        != materialization.seed_heavy_atom_indices
    ):
        raise PublicRigidDockingDiagnosticError(
            "parsed ligand atom identity disagrees with reference materialization"
        )
    center = _pocket_center(materialization)
    pocket_digest = _pocket_definition_sha256(
        case,
        materialization.fingerprint_sha256,
        center,
    )
    receptor_coordinates = receptor.coordinates[0] - center
    receptor_prepared = receptor.with_coordinates(
        receptor_coordinates.unsqueeze(0),
        operation="public_rigid_diagnostic_pocket_center_shift",
        operation_evidence_sha256=pocket_digest,
    )
    seed_coordinates = ligand.coordinates[0]
    heavy = torch.tensor(
        materialization.seed_heavy_atom_indices,
        dtype=torch.long,
    )
    seed_center = seed_coordinates.index_select(0, heavy).mean(dim=0)
    prepared_coordinates = (seed_coordinates - seed_center) @ _fixed_deleak_rotation(
        torch.float64
    ).T
    ligand_prepared = ligand.with_coordinates(
        prepared_coordinates.unsqueeze(0),
        operation="public_rigid_diagnostic_fixed_deleak_rotation",
        operation_evidence_sha256=config.fingerprint_sha256,
    )
    problem_metadata: dict[str, object] = {
        "case_id": case.case_id,
        "raw_receptor_sha256": case.receptor.sha256,
        "reference_materialization_sha256": materialization.fingerprint_sha256,
        "cryst1_records_discarded": discarded_cryst1,
        "native_reference_used_for_pocket_center_only": True,
        "native_reference_coordinates_used_for_proposals": False,
        "seed_coordinates_fixed_rigid_deleak_rotated": True,
    }
    if torsion_search_config is not None:
        problem_metadata.update(
            {
                "bridge_only_torsion_sampling_requested": True,
                "torsion_search_config_sha256": (
                    torsion_search_config.fingerprint_sha256
                ),
            }
        )
    problem = DockingProblemIdentity(
        receptor_system_sha256=canonical_system_sha256(receptor_prepared),
        ligand_system_sha256=canonical_system_sha256(ligand_prepared),
        pocket_definition_sha256=pocket_digest,
        coordinate_frame_id="native_reference_pocket_centered_receptor_frame",
        metadata=problem_metadata,
    )
    if flexible_geometry_score_config is None:
        scorer = ElementGeometryDiagnosticScorer(
            receptor_coordinates,
            tuple(atom.atomic_number for atom in receptor.atoms),
            tuple(atom.atomic_number for atom in ligand.atoms),
            problem,
            config=config.geometry_score,
        )
    else:
        scorer = ElementFlexibleGeometryDiagnosticScorer(
            receptor_coordinates,
            tuple(atom.atomic_number for atom in receptor.atoms),
            tuple(atom.atomic_number for atom in ligand.atoms),
            tuple((bond.atom_i, bond.atom_j) for bond in ligand.bonds),
            problem,
            config=flexible_geometry_score_config,
        )
    torsion_receipt = None
    if torsion_search_config is None:
        search_space = _rigid_search_space(prepared_coordinates)
    else:
        search_space, torsion_receipt = build_molecular_torsion_search_space(
            ligand_prepared,
            config=torsion_search_config,
        )
    validity_radius = (
        config.geometry_score.pocket_radius_angstrom
        + PoseValidityConfig().receptor_ligand_clash_angstrom
    )
    validity_mask = (
        torch.linalg.vector_norm(receptor_coordinates, dim=1) <= validity_radius
    )
    validity_receptor = receptor_coordinates[validity_mask]
    validity_config = PoseValidityConfig(
        pocket_radius_angstrom=config.geometry_score.pocket_radius_angstrom,
        max_cross_checks=max(
            1_000_000,
            int(validity_receptor.shape[0]) * ligand.atom_count,
        ),
    )
    bond_pairs = tuple((bond.atom_i, bond.atom_j) for bond in ligand.bonds)
    validity_context = PoseValidityContext(
        problem_fingerprint_sha256=problem.fingerprint_sha256,
        reference_coordinates=prepared_coordinates,
        bond_pairs=bond_pairs,
        excluded_nonbonded_pairs=bond_pairs,
        receptor_coordinates=validity_receptor,
        pocket_center=torch.zeros(3, dtype=torch.float64),
        chirality_centers=(),
        config=validity_config,
    )
    budget = DockingBudget(
        candidate_count=config.candidate_count,
        top_k=config.top_k,
        max_torsions=search_space.torsion_count,
        max_refinement_steps=0,
        translation_radius_angstrom=config.translation_radius_angstrom,
        seed=config.seed + case_index,
    )
    search = run_bounded_docking_search(
        search_space,
        budget,
        scorer,
        diversity_rmsd_angstrom=config.diversity_rmsd_angstrom,
        diversity_metric="direct_rmsd",
        validity_context=validity_context,
        problem=problem,
    )
    final_proposals: dict[str, DockingProposal] = {}
    final_scores: dict[str, float] = {}
    final_breakdowns: dict[str, DockingScoreBreakdown] = {}
    refinement_receipts: dict[str, GeometricRigidRefinementReceipt] = {}
    refinement_failures: dict[str, tuple[str, str]] = {}
    for search_row in search.rows:
        if not search_row.succeeded or search_row.proposal is None:
            continue
        if search_row.score_breakdown is None:
            raise PublicRigidDockingDiagnosticError(
                "successful geometric search row is missing term decomposition"
            )
        final_proposals[search_row.candidate_id] = search_row.proposal
        final_scores[search_row.candidate_id] = float(search_row.score)
        final_breakdowns[search_row.candidate_id] = search_row.score_breakdown

    refiner = GeometricRigidBodyRefiner(
        scorer,
        config=config.rigid_refinement,
    )
    for search_row in search.top_rows:
        assert search_row.proposal is not None
        try:
            refined, receipt = refiner.refine_with_receipt(
                search_row.proposal,
                max_steps=config.refinement_steps,
            )
            breakdown = scorer.score(refined)
            if breakdown.total_score > float(search_row.score):
                raise PublicRigidDockingDiagnosticError(
                    "rigid refinement increased the diagnostic score"
                )
            final_proposals[search_row.candidate_id] = refined
            final_scores[search_row.candidate_id] = breakdown.total_score
            final_breakdowns[search_row.candidate_id] = breakdown
            refinement_receipts[search_row.candidate_id] = receipt
        except Exception as exc:
            failure = failure_receipt(
                exc,
                public_message="public rigid candidate refinement failed",
            )
            refinement_failures[search_row.candidate_id] = (
                failure.public_error_code,
                failure.private_error_sha256,
            )
            final_proposals.pop(search_row.candidate_id, None)
            final_scores.pop(search_row.candidate_id, None)
            final_breakdowns.pop(search_row.candidate_id, None)

    ranked_candidate_ids = sorted(
        final_proposals,
        key=lambda candidate_id: (
            final_scores[candidate_id],
            final_proposals[candidate_id].proposal_index,
            candidate_id,
        ),
    )
    score_ranks = {
        candidate_id: rank
        for rank, candidate_id in enumerate(ranked_candidate_ids, start=1)
    }
    selected_candidate_ids: list[str] = []
    for candidate_id in ranked_candidate_ids:
        if all(
            direct_rmsd(
                final_proposals[candidate_id].coordinates,
                final_proposals[selected_id].coordinates,
            )
            >= config.diversity_rmsd_angstrom
            for selected_id in selected_candidate_ids
        ):
            selected_candidate_ids.append(candidate_id)
        if len(selected_candidate_ids) >= config.top_k:
            break
    selected_ranks = {
        candidate_id: rank
        for rank, candidate_id in enumerate(selected_candidate_ids, start=1)
    }
    final_ranking_fingerprint_sha256 = _sha256(
        {
            "score_direction": "minimize",
            "candidate_rows": [
                {
                    "candidate_id": candidate_id,
                    "score_binary64_hex": final_scores[candidate_id].hex(),
                    "result_proposal_fingerprint_sha256": (
                        final_proposals[candidate_id].fingerprint_sha256
                    ),
                }
                for candidate_id in ranked_candidate_ids
            ],
            "selected_candidate_ids": selected_candidate_ids,
        }
    )
    candidate_rows: list[PublicRigidDockingCandidateRow] = []
    for search_row in search.rows:
        selected_rank = selected_ranks.get(search_row.candidate_id, 0)
        score_rank = score_ranks.get(search_row.candidate_id, 0)
        if not search_row.succeeded or search_row.proposal is None:
            candidate_rows.append(
                PublicRigidDockingCandidateRow(
                    candidate_id=search_row.candidate_id,
                    proposal_index=search_row.proposal_index,
                    status="search_failure",
                    selected_rank=selected_rank,
                    score_rank=score_rank,
                    score=None,
                    proposal_fingerprint_sha256=(
                        search_row.proposal_fingerprint_sha256
                    ),
                    result_proposal_fingerprint_sha256="",
                    score_breakdown=None,
                    refined=False,
                    refinement_receipt_sha256="",
                    refinement_receipt=None,
                    validity=None,
                    rmsd=None,
                    primary_success=False,
                    error_code=search_row.error_code or "docking_search_failure",
                    private_error_sha256=search_row.private_error_sha256,
                )
            )
            continue
        if search_row.candidate_id in refinement_failures:
            error_code, private_error_sha256 = refinement_failures[
                search_row.candidate_id
            ]
            candidate_rows.append(
                PublicRigidDockingCandidateRow(
                    candidate_id=search_row.candidate_id,
                    proposal_index=search_row.proposal_index,
                    status="refinement_failure",
                    selected_rank=0,
                    score_rank=0,
                    score=float(search_row.score),
                    proposal_fingerprint_sha256=(
                        search_row.proposal_fingerprint_sha256
                    ),
                    result_proposal_fingerprint_sha256="",
                    score_breakdown=(
                        None
                        if search_row.score_breakdown is None
                        else search_row.score_breakdown.to_dict()
                    ),
                    refined=False,
                    refinement_receipt_sha256="",
                    refinement_receipt=None,
                    validity=None,
                    rmsd=None,
                    primary_success=False,
                    error_code=error_code,
                    private_error_sha256=private_error_sha256,
                )
            )
            continue
        final_proposal = final_proposals[search_row.candidate_id]
        final_breakdown = final_breakdowns[search_row.candidate_id]
        refinement_receipt = refinement_receipts.get(search_row.candidate_id)
        refinement_receipt_payload = (
            None if refinement_receipt is None else refinement_receipt.to_dict()
        )
        refinement_receipt_sha256 = (
            ""
            if refinement_receipt is None
            else refinement_receipt.fingerprint_sha256
        )
        try:
            validity = validity_context.evaluate(final_proposal)
            candidate_receptor_frame = (
                final_proposal.coordinates.index_select(0, heavy) + center
            )
            rmsd = minimum_public_reference_rmsd(
                materialization,
                candidate_receptor_frame,
            )
            primary_success = bool(
                validity.valid
                and rmsd.rmsd_angstrom <= PRIMARY_RMSD_THRESHOLD_ANGSTROM
            )
            candidate_rows.append(
                PublicRigidDockingCandidateRow(
                    candidate_id=search_row.candidate_id,
                    proposal_index=search_row.proposal_index,
                    status="evaluated",
                    selected_rank=selected_rank,
                    score_rank=score_rank,
                    score=final_scores[search_row.candidate_id],
                    proposal_fingerprint_sha256=(
                        search_row.proposal_fingerprint_sha256
                    ),
                    result_proposal_fingerprint_sha256=(
                        final_proposal.fingerprint_sha256
                    ),
                    score_breakdown=final_breakdown.to_dict(),
                    refined=refinement_receipt is not None,
                    refinement_receipt_sha256=refinement_receipt_sha256,
                    refinement_receipt=refinement_receipt_payload,
                    validity=validity.to_dict(),
                    rmsd=rmsd.to_dict(),
                    primary_success=primary_success,
                )
            )
        except Exception as exc:
            failure = failure_receipt(
                exc,
                public_message="public rigid candidate evaluation failed",
            )
            candidate_rows.append(
                PublicRigidDockingCandidateRow(
                    candidate_id=search_row.candidate_id,
                    proposal_index=search_row.proposal_index,
                    status="evaluation_failure",
                    selected_rank=selected_rank,
                    score_rank=score_rank,
                    score=final_scores[search_row.candidate_id],
                    proposal_fingerprint_sha256=(
                        search_row.proposal_fingerprint_sha256
                    ),
                    result_proposal_fingerprint_sha256=(
                        final_proposal.fingerprint_sha256
                    ),
                    score_breakdown=final_breakdown.to_dict(),
                    refined=refinement_receipt is not None,
                    refinement_receipt_sha256=refinement_receipt_sha256,
                    refinement_receipt=refinement_receipt_payload,
                    validity=None,
                    rmsd=None,
                    primary_success=False,
                    error_code=failure.public_error_code,
                    private_error_sha256=failure.private_error_sha256,
                )
            )
    if validity_gated_selection:
        valid_candidate_ids = {
            row.candidate_id
            for row in candidate_rows
            if row.status == "evaluated" and row.valid
        }
        selected_candidate_ids = []
        for candidate_id in ranked_candidate_ids:
            if candidate_id not in valid_candidate_ids:
                continue
            if all(
                direct_rmsd(
                    final_proposals[candidate_id].coordinates,
                    final_proposals[selected_id].coordinates,
                )
                >= config.diversity_rmsd_angstrom
                for selected_id in selected_candidate_ids
            ):
                selected_candidate_ids.append(candidate_id)
            if len(selected_candidate_ids) >= config.top_k:
                break
        selected_ranks = {
            candidate_id: rank
            for rank, candidate_id in enumerate(selected_candidate_ids, start=1)
        }
        candidate_rows = [
            replace(
                row,
                selected_rank=selected_ranks.get(row.candidate_id, 0),
            )
            for row in candidate_rows
        ]
        final_ranking_fingerprint_sha256 = _sha256(
            {
                "score_direction": "minimize",
                "validity_gated_selection": True,
                "candidate_rows": [
                    {
                        "candidate_id": candidate_id,
                        "score_binary64_hex": final_scores[candidate_id].hex(),
                        "result_proposal_fingerprint_sha256": (
                            final_proposals[candidate_id].fingerprint_sha256
                        ),
                    }
                    for candidate_id in ranked_candidate_ids
                ],
                "selected_candidate_ids": selected_candidate_ids,
            }
        )
    ranked = sorted(
        (row for row in candidate_rows if row.selected_rank > 0),
        key=lambda row: row.selected_rank,
    )
    evaluated_ranked = [row for row in ranked if row.status == "evaluated"]
    top1 = ranked[0] if ranked else None
    top1_evaluated = top1 if top1 is not None and top1.status == "evaluated" else None
    top5 = ranked[: min(5, len(ranked))]
    top5_evaluated = [row for row in top5 if row.status == "evaluated"]
    top1_rmsd = None if top1_evaluated is None else top1_evaluated.rmsd_angstrom
    top5_rmsd = min(
        (row.rmsd_angstrom for row in top5_evaluated if row.rmsd_angstrom is not None),
        default=None,
    )
    top1_valid = bool(top1_evaluated is not None and top1_evaluated.valid)
    top1_success = bool(top1_evaluated is not None and top1_evaluated.primary_success)
    top5_success = any(row.primary_success for row in top5_evaluated)
    evaluated_count = sum(row.status == "evaluated" for row in candidate_rows)
    valid_count = sum(row.valid for row in candidate_rows)
    clash_failure_count = sum(
        row.validity is not None
        and (
            row.validity["checks"].get("ligand_self_clash_free") is False
            or row.validity["checks"].get("receptor_ligand_clash_free") is False
        )
        for row in candidate_rows
    )
    evaluated_rows = [row for row in candidate_rows if row.status == "evaluated"]
    valid_rows = [row for row in evaluated_rows if row.valid]
    generated_hits = [row for row in evaluated_rows if row.primary_success]
    oracle_best_all = min(
        evaluated_rows,
        key=lambda row: float(row.rmsd_angstrom),
        default=None,
    )
    oracle_best_valid = min(
        valid_rows,
        key=lambda row: float(row.rmsd_angstrom),
        default=None,
    )
    metric_available = top1_rmsd is not None
    protocol_metrics = None
    if metric_available:
        protocol_metrics = require_public_benchmark_case_metrics(
            {
                "top1_symmetry_aware_heavy_atom_rmsd_angstrom": top1_rmsd,
                "bounded_pose_valid": 1.0 if top1_valid else 0.0,
                "primary_pose_success": 1.0 if top1_success else 0.0,
            }
        )
    partial_failure = (
        evaluated_count != len(candidate_rows)
        or len(ranked) < config.top_k
        or len(evaluated_ranked) != len(ranked)
    )
    summary = {
        "generated_candidate_count": len(candidate_rows),
        "evaluated_candidate_count": evaluated_count,
        "candidate_failure_count": len(candidate_rows) - evaluated_count,
        "valid_candidate_count": valid_count,
        "valid_pose_rate_all_generated": valid_count / len(candidate_rows),
        "clash_failure_count": clash_failure_count,
        "oracle_best_all_rmsd_angstrom": (
            None if oracle_best_all is None else oracle_best_all.rmsd_angstrom
        ),
        "oracle_best_all_score_rank": (
            None if oracle_best_all is None else oracle_best_all.score_rank
        ),
        "oracle_best_all_valid": (
            False if oracle_best_all is None else oracle_best_all.valid
        ),
        "oracle_best_valid_rmsd_angstrom": (
            None if oracle_best_valid is None else oracle_best_valid.rmsd_angstrom
        ),
        "oracle_best_valid_score_rank": (
            None if oracle_best_valid is None else oracle_best_valid.score_rank
        ),
        "generated_primary_hit_count": len(generated_hits),
        "best_generated_primary_hit_score_rank": (
            None if not generated_hits else min(row.score_rank for row in generated_hits)
        ),
        "selected_pose_count": len(ranked),
        "metric_available": metric_available,
        "top1_rmsd_angstrom": top1_rmsd,
        "top5_min_rmsd_angstrom": top5_rmsd,
        "top1_valid": top1_valid,
        "top1_success": top1_success,
        "top5_success": top5_success,
        "protocol_primary_metrics": protocol_metrics,
        "search_fingerprint_sha256": search.search_fingerprint_sha256,
        "scorer_contract_fingerprint_sha256": (
            search.scorer_contract_fingerprint_sha256
        ),
        "search_blockers": list(search.blockers),
        "final_ranking_fingerprint_sha256": final_ranking_fingerprint_sha256,
        "initial_refinement_candidate_ids": [
            row.candidate_id for row in search.top_rows
        ],
        "final_selected_candidate_ids": selected_candidate_ids,
        "refinement_attempted": bool(search.top_rows),
        "refinement_performed": bool(refinement_receipts),
        "refinement_candidate_count": len(search.top_rows),
        "refinement_success_count": len(refinement_receipts),
        "refinement_failure_count": len(refinement_failures),
        "refinement_improved_count": sum(
            receipt.improved for receipt in refinement_receipts.values()
        ),
        "refinement_executed_step_count": sum(
            len(receipt.steps) for receipt in refinement_receipts.values()
        ),
        "refinement_accepted_step_count": sum(
            receipt.accepted_step_count for receipt in refinement_receipts.values()
        ),
        "refinement_rejected_step_count": sum(
            receipt.rejected_step_count for receipt in refinement_receipts.values()
        ),
        "refinement_receipt_sha256s": {
            candidate_id: refinement_receipts[candidate_id].fingerprint_sha256
            for candidate_id in sorted(refinement_receipts)
        },
        "rigid_refiner_contract_fingerprint_sha256": (
            refiner.config_fingerprint_sha256
        ),
        "torsion_sampling_performed": False,
    }
    if torsion_receipt is not None:
        summary.update(
            {
                "torsion_sampling_performed": search_space.torsion_count > 0,
                "torsion_variable_count": search_space.torsion_count,
                "torsion_search_space_sha256": search_space.fingerprint_sha256,
                "torsion_search_receipt_sha256": (
                    torsion_receipt.fingerprint_sha256
                ),
                "torsion_search_receipt": torsion_receipt.to_dict(),
                "torsion_sampling_distribution": (
                    "candidate_zero_zero_angle_then_independent_uniform_minus_pi_pi"
                ),
            }
        )
    if validity_gated_selection:
        summary.update(
            {
                "validity_gated_selection": True,
                "valid_candidate_pool_count": sum(
                    row.status == "evaluated" and row.valid
                    for row in candidate_rows
                ),
                "invalid_candidates_excluded_from_selection": True,
            }
        )
    return PublicRigidDockingCaseRow(
        case_id=case.case_id,
        pdb_id=case.pdb_id,
        case_input_sha256=case.input_sha256,
        status="partial_failure" if partial_failure else "success",
        pocket_definition_sha256=pocket_digest,
        pocket_center_receptor_frame_angstrom=_float_vector(center),
        discarded_cryst1_record_count=discarded_cryst1,
        receptor_atom_count=receptor.atom_count,
        receptor_shell_atom_count=scorer.receptor_shell_atom_count,
        validity_receptor_atom_count=int(validity_receptor.shape[0]),
        ligand_atom_count=ligand.atom_count,
        ligand_heavy_atom_count=len(materialization.seed_heavy_atom_indices),
        candidate_rows=tuple(candidate_rows),
        summary=summary,
    )


def run_public_rigid_docking_diagnostic(
    protocol: FrozenPublicBenchmarkProtocol,
    artifacts_by_relative_path: Mapping[str, bytes],
    *,
    config: PublicRigidDockingDiagnosticConfig | None = None,
) -> PublicRigidDockingDiagnosticReport:
    """Execute a claim-closed rigid diagnostic with all case/candidate failures."""

    if not isinstance(protocol, FrozenPublicBenchmarkProtocol):
        raise PublicRigidDockingDiagnosticError(
            "protocol must be FrozenPublicBenchmarkProtocol"
        )
    active = PublicRigidDockingDiagnosticConfig() if config is None else config
    if not isinstance(active, PublicRigidDockingDiagnosticConfig):
        raise PublicRigidDockingDiagnosticError(
            "config must be PublicRigidDockingDiagnosticConfig"
        )
    suite = materialize_public_benchmark_input_suite(
        protocol,
        artifacts_by_relative_path,
    )
    rows: list[PublicRigidDockingCaseRow] = []
    for index, case in enumerate(protocol.cases):
        try:
            rows.append(
                _run_case(
                    case,
                    suite,
                    artifacts_by_relative_path,
                    active,
                    case_index=index,
                )
            )
        except Exception as exc:
            failure = failure_receipt(
                exc,
                public_message="public rigid case execution failed",
            )
            rows.append(
                _failure_case(
                    case,
                    error_code=failure.public_error_code,
                    private_error_sha256=failure.private_error_sha256,
                )
            )
    report = PublicRigidDockingDiagnosticReport(
        protocol_sha256=protocol.protocol_sha256,
        input_suite_receipt_sha256=suite.fingerprint_sha256,
        config=active,
        case_rows=tuple(rows),
    )
    return report.require_protocol(protocol, suite)


def write_public_rigid_docking_diagnostic_report(
    report: PublicRigidDockingDiagnosticReport,
    output_path: str | os.PathLike[str],
) -> Path:
    """Write a private report and refuse to replace an existing path."""

    if not isinstance(report, PublicRigidDockingDiagnosticReport):
        raise PublicRigidDockingDiagnosticError(
            "report must be PublicRigidDockingDiagnosticReport"
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
            raise PublicRigidDockingDiagnosticError(
                "public rigid diagnostic output already exists"
            ) from exc
    finally:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
    return output


__all__ = [
    "MAX_PUBLIC_RIGID_DOCKING_DIAGNOSTIC_RECEIPT_BYTES",
    "PUBLIC_RIGID_DOCKING_DIAGNOSTIC_ALGORITHM_ID",
    "PUBLIC_RIGID_DOCKING_DIAGNOSTIC_BLOCKERS",
    "PUBLIC_RIGID_DOCKING_DIAGNOSTIC_SCHEMA_ID",
    "PublicRigidDockingCandidateRow",
    "PublicRigidDockingCaseRow",
    "PublicRigidDockingDiagnosticConfig",
    "PublicRigidDockingDiagnosticError",
    "PublicRigidDockingDiagnosticReport",
    "run_public_rigid_docking_diagnostic",
    "write_public_rigid_docking_diagnostic_report",
]
