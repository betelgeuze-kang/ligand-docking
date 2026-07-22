"""Deterministic rigid-body coordinate descent for geometry diagnostics.

This refiner preserves every intraligand distance and only optimizes the
uncalibrated element-geometry diagnostic score.  It is not a molecular
minimizer, force-field refinement, or scientific docking validation.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from numbers import Integral, Real

import torch

from betelgeuze_engine_v2.ai import axis_angle_matrix

from .flexible_geometric_scoring import ElementFlexibleGeometryDiagnosticScorer
from .geometric_scoring import ElementGeometryDiagnosticScorer
from .identity import coordinate_fingerprint
from .proposals import DockingProposal


GEOMETRIC_RIGID_REFINER_SCHEMA_ID = (
    "betelgeuze.engine_v2_geometric_rigid_refiner/1.0.0"
)
GEOMETRIC_RIGID_REFINEMENT_RECEIPT_SCHEMA_ID = (
    "betelgeuze.engine_v2_geometric_rigid_refinement_receipt/1.0.0"
)
GEOMETRIC_RIGID_REFINEMENT_BLOCKERS = (
    "geometry_diagnostic_refinement_not_force_field_minimization",
    "refinement_objective_not_fitted_or_scientifically_validated",
    "torsion_and_internal_coordinate_refinement_missing",
    "charge_aromatic_stereo_hbond_and_metal_physics_missing",
    "public_pose_refinement_validation_missing",
)


class GeometricRigidRefinementError(ValueError):
    """Rigid geometry refinement input or trace is invalid."""


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
        raise GeometricRigidRefinementError(
            "geometric rigid refinement value is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _digest(value: object, *, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise GeometricRigidRefinementError(
            f"{name} must be a lowercase SHA-256"
        )
    return value


def _exact_int(value: object, *, name: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise GeometricRigidRefinementError(f"{name} must be an integer")
    result = int(value)
    if result < minimum:
        raise GeometricRigidRefinementError(
            f"{name} must be at least {minimum}"
        )
    return result


def _finite(
    value: object,
    *,
    name: str,
    positive: bool = False,
    nonnegative: bool = False,
) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise GeometricRigidRefinementError(f"{name} must be a real number")
    result = float(value)
    if not math.isfinite(result):
        raise GeometricRigidRefinementError(f"{name} must be finite")
    if positive and result <= 0.0:
        raise GeometricRigidRefinementError(f"{name} must be positive")
    if nonnegative and result < 0.0:
        raise GeometricRigidRefinementError(f"{name} must be non-negative")
    return result


@dataclass(frozen=True, slots=True)
class GeometricRigidRefinementConfig:
    maximum_steps: int = 12
    initial_translation_step_angstrom: float = 0.25
    initial_rotation_step_radians: float = 0.10
    minimum_translation_step_angstrom: float = 0.015625
    minimum_rotation_step_radians: float = 0.00625
    step_reduction_factor: float = 0.5
    minimum_score_improvement: float = 1.0e-12

    def __post_init__(self) -> None:
        maximum = _exact_int(self.maximum_steps, name="maximum_steps", minimum=1)
        if maximum > 64:
            raise GeometricRigidRefinementError(
                "maximum_steps must not exceed 64"
            )
        for name in (
            "initial_translation_step_angstrom",
            "initial_rotation_step_radians",
            "minimum_translation_step_angstrom",
            "minimum_rotation_step_radians",
        ):
            object.__setattr__(
                self,
                name,
                _finite(getattr(self, name), name=name, positive=True),
            )
        if (
            self.minimum_translation_step_angstrom
            > self.initial_translation_step_angstrom
            or self.minimum_rotation_step_radians
            > self.initial_rotation_step_radians
        ):
            raise GeometricRigidRefinementError(
                "minimum rigid steps cannot exceed their initial values"
            )
        reduction = _finite(
            self.step_reduction_factor,
            name="step_reduction_factor",
            positive=True,
        )
        if reduction >= 1.0:
            raise GeometricRigidRefinementError(
                "step_reduction_factor must be less than one"
            )
        object.__setattr__(self, "step_reduction_factor", reduction)
        object.__setattr__(
            self,
            "minimum_score_improvement",
            _finite(
                self.minimum_score_improvement,
                name="minimum_score_improvement",
                nonnegative=True,
            ),
        )
        object.__setattr__(self, "maximum_steps", maximum)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": GEOMETRIC_RIGID_REFINER_SCHEMA_ID,
            "maximum_steps": self.maximum_steps,
            "initial_translation_step_angstrom": (
                self.initial_translation_step_angstrom
            ),
            "initial_rotation_step_radians": self.initial_rotation_step_radians,
            "minimum_translation_step_angstrom": (
                self.minimum_translation_step_angstrom
            ),
            "minimum_rotation_step_radians": self.minimum_rotation_step_radians,
            "step_reduction_factor": self.step_reduction_factor,
            "minimum_score_improvement": self.minimum_score_improvement,
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _sha256(self.to_dict())


@dataclass(frozen=True, slots=True)
class GeometricRigidRefinementStep:
    iteration: int
    outcome: str
    move_id: str
    score_before: float
    score_after: float
    translation_step_angstrom: float
    rotation_step_radians: float
    coordinate_sha256: str

    def __post_init__(self) -> None:
        _exact_int(self.iteration, name="iteration", minimum=1)
        if self.outcome not in {"accepted", "rejected_reduce_steps"}:
            raise GeometricRigidRefinementError(
                "geometric rigid refinement outcome is invalid"
            )
        if self.outcome == "accepted" and not self.move_id:
            raise GeometricRigidRefinementError(
                "accepted rigid refinement step requires a move ID"
            )
        if self.outcome != "accepted" and self.move_id:
            raise GeometricRigidRefinementError(
                "rejected rigid refinement step cannot name a move"
            )
        before = _finite(self.score_before, name="score_before")
        after = _finite(self.score_after, name="score_after")
        if after > before:
            raise GeometricRigidRefinementError(
                "rigid refinement score trace must be non-increasing"
            )
        if self.outcome == "rejected_reduce_steps" and after != before:
            raise GeometricRigidRefinementError(
                "rejected rigid refinement step must preserve the score"
            )
        _finite(
            self.translation_step_angstrom,
            name="translation_step_angstrom",
            positive=True,
        )
        _finite(
            self.rotation_step_radians,
            name="rotation_step_radians",
            positive=True,
        )
        _digest(self.coordinate_sha256, name="coordinate_sha256")

    def to_dict(self) -> dict[str, object]:
        return {
            "iteration": self.iteration,
            "outcome": self.outcome,
            "move_id": self.move_id,
            "score_before": self.score_before,
            "score_after": self.score_after,
            "translation_step_angstrom": self.translation_step_angstrom,
            "rotation_step_radians": self.rotation_step_radians,
            "coordinate_sha256": self.coordinate_sha256,
        }


@dataclass(frozen=True, slots=True)
class GeometricRigidRefinementReceipt:
    parent_proposal_fingerprint_sha256: str
    scorer_config_fingerprint_sha256: str
    refiner_config_fingerprint_sha256: str
    requested_steps: int
    initial_coordinate_sha256: str
    final_coordinate_sha256: str
    initial_score: float
    final_score: float
    steps: tuple[GeometricRigidRefinementStep, ...]
    blockers: tuple[str, ...] = GEOMETRIC_RIGID_REFINEMENT_BLOCKERS
    schema_id: str = GEOMETRIC_RIGID_REFINEMENT_RECEIPT_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != GEOMETRIC_RIGID_REFINEMENT_RECEIPT_SCHEMA_ID:
            raise GeometricRigidRefinementError(
                "unsupported geometric rigid refinement receipt schema"
            )
        for name in (
            "parent_proposal_fingerprint_sha256",
            "scorer_config_fingerprint_sha256",
            "refiner_config_fingerprint_sha256",
            "initial_coordinate_sha256",
            "final_coordinate_sha256",
        ):
            _digest(getattr(self, name), name=name)
        requested = _exact_int(
            self.requested_steps,
            name="requested_steps",
            minimum=1,
        )
        steps = tuple(self.steps)
        if len(steps) > requested or tuple(step.iteration for step in steps) != tuple(
            range(1, len(steps) + 1)
        ):
            raise GeometricRigidRefinementError(
                "rigid refinement steps exceed or reorder the requested budget"
            )
        initial = _finite(self.initial_score, name="initial_score")
        final = _finite(self.final_score, name="final_score")
        if final > initial:
            raise GeometricRigidRefinementError(
                "rigid refinement final score must not increase"
            )
        if steps:
            if steps[0].score_before != initial or steps[-1].score_after != final:
                raise GeometricRigidRefinementError(
                    "rigid refinement receipt scores disagree with the trace"
                )
            for first, second in zip(steps, steps[1:]):
                if first.score_after != second.score_before:
                    raise GeometricRigidRefinementError(
                        "rigid refinement score trace is discontinuous"
                    )
            if steps[-1].coordinate_sha256 != self.final_coordinate_sha256:
                raise GeometricRigidRefinementError(
                    "rigid refinement final coordinate identity disagrees with the trace"
                )
        elif (
            initial != final
            or self.initial_coordinate_sha256 != self.final_coordinate_sha256
        ):
            raise GeometricRigidRefinementError(
                "empty rigid refinement trace must preserve score and coordinates"
            )
        if tuple(self.blockers) != GEOMETRIC_RIGID_REFINEMENT_BLOCKERS:
            raise GeometricRigidRefinementError(
                "geometric rigid refinement blockers cannot be promoted"
            )
        object.__setattr__(self, "requested_steps", requested)
        object.__setattr__(self, "steps", steps)

    @property
    def accepted_step_count(self) -> int:
        return sum(step.outcome == "accepted" for step in self.steps)

    @property
    def rejected_step_count(self) -> int:
        return len(self.steps) - self.accepted_step_count

    @property
    def improved(self) -> bool:
        return self.final_score < self.initial_score

    def _payload(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "parent_proposal_fingerprint_sha256": (
                self.parent_proposal_fingerprint_sha256
            ),
            "scorer_config_fingerprint_sha256": (
                self.scorer_config_fingerprint_sha256
            ),
            "refiner_config_fingerprint_sha256": (
                self.refiner_config_fingerprint_sha256
            ),
            "requested_steps": self.requested_steps,
            "executed_step_count": len(self.steps),
            "accepted_step_count": self.accepted_step_count,
            "rejected_step_count": self.rejected_step_count,
            "initial_coordinate_sha256": self.initial_coordinate_sha256,
            "final_coordinate_sha256": self.final_coordinate_sha256,
            "initial_score": self.initial_score,
            "final_score": self.final_score,
            "improved": self.improved,
            "rigid_body_only": True,
            "intraligand_distances_preserved": True,
            "steps": [step.to_dict() for step in self.steps],
            "blockers": list(self.blockers),
            "scientifically_validated": False,
            "claim_safe": False,
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _sha256(self._payload())

    def to_dict(self) -> dict[str, object]:
        return {**self._payload(), "receipt_sha256": self.fingerprint_sha256}


class GeometricRigidBodyRefiner:
    """Axis-aligned rigid coordinate descent over one geometry scorer."""

    refiner_id = "geometric-rigid-coordinate-descent"
    refiner_version = "1.0.0"

    def __init__(
        self,
        scorer: ElementGeometryDiagnosticScorer
        | ElementFlexibleGeometryDiagnosticScorer,
        *,
        config: GeometricRigidRefinementConfig | None = None,
    ) -> None:
        if not isinstance(
            scorer,
            (ElementGeometryDiagnosticScorer, ElementFlexibleGeometryDiagnosticScorer),
        ):
            raise GeometricRigidRefinementError(
                "scorer must be an element geometry diagnostic scorer"
            )
        active = GeometricRigidRefinementConfig() if config is None else config
        if not isinstance(active, GeometricRigidRefinementConfig):
            raise GeometricRigidRefinementError(
                "config must be GeometricRigidRefinementConfig"
            )
        self.scorer = scorer
        self.config = active
        self.config_fingerprint_sha256 = _sha256(
            {
                "schema_id": GEOMETRIC_RIGID_REFINER_SCHEMA_ID,
                "config_sha256": active.fingerprint_sha256,
                "scorer_config_sha256": scorer.config_fingerprint_sha256,
            }
        )

    @staticmethod
    def _moves(
        coordinates: torch.Tensor,
        translation_step: float,
        rotation_step: float,
    ) -> tuple[tuple[str, torch.Tensor], ...]:
        axes = torch.eye(3, dtype=torch.float64)
        centroid = coordinates.mean(dim=0)
        centered = coordinates - centroid
        moves: list[tuple[str, torch.Tensor]] = []
        for axis_index in range(3):
            for sign, label in ((-1.0, "minus"), (1.0, "plus")):
                delta = axes[axis_index] * sign * translation_step
                moves.append(
                    (f"translate_{'xyz'[axis_index]}_{label}", coordinates + delta)
                )
        for axis_index in range(3):
            axis = axes[axis_index].reshape(1, 3)
            for sign, label in ((-1.0, "minus"), (1.0, "plus")):
                angle = torch.tensor([sign * rotation_step], dtype=torch.float64)
                rotation = axis_angle_matrix(axis, angle)[0]
                moves.append(
                    (
                        f"rotate_{'xyz'[axis_index]}_{label}",
                        centered @ rotation.T + centroid,
                    )
                )
        return tuple(moves)

    def refine_with_receipt(
        self,
        proposal: DockingProposal,
        *,
        max_steps: int,
    ) -> tuple[DockingProposal, GeometricRigidRefinementReceipt]:
        if not isinstance(proposal, DockingProposal):
            raise GeometricRigidRefinementError(
                "proposal must be DockingProposal"
            )
        requested = _exact_int(max_steps, name="max_steps", minimum=1)
        if requested > self.config.maximum_steps:
            raise GeometricRigidRefinementError(
                "requested rigid refinement exceeds the configured bound"
            )
        if proposal.problem_fingerprint_sha256 != self.scorer.problem.fingerprint_sha256:
            raise GeometricRigidRefinementError(
                "proposal problem identity does not match the rigid refiner"
            )
        coordinates = proposal.coordinates.detach().clone()
        initial_coordinate_sha256 = coordinate_fingerprint(coordinates)
        score = self.scorer.score_coordinates(coordinates).total_score
        initial_score = score
        translation_step = self.config.initial_translation_step_angstrom
        rotation_step = self.config.initial_rotation_step_radians
        rows: list[GeometricRigidRefinementStep] = []
        for iteration in range(1, requested + 1):
            before = score
            candidates = []
            for move_index, (move_id, candidate) in enumerate(
                self._moves(coordinates, translation_step, rotation_step)
            ):
                candidate_score = self.scorer.score_coordinates(candidate).total_score
                candidates.append((candidate_score, move_index, move_id, candidate))
            best_score, _move_index, move_id, best_coordinates = min(candidates)
            if best_score < before - self.config.minimum_score_improvement:
                coordinates = best_coordinates
                score = best_score
                outcome = "accepted"
            else:
                move_id = ""
                score = before
                outcome = "rejected_reduce_steps"
                translation_step *= self.config.step_reduction_factor
                rotation_step *= self.config.step_reduction_factor
            rows.append(
                GeometricRigidRefinementStep(
                    iteration=iteration,
                    outcome=outcome,
                    move_id=move_id,
                    score_before=before,
                    score_after=score,
                    translation_step_angstrom=(
                        translation_step
                        if outcome == "accepted"
                        else translation_step / self.config.step_reduction_factor
                    ),
                    rotation_step_radians=(
                        rotation_step
                        if outcome == "accepted"
                        else rotation_step / self.config.step_reduction_factor
                    ),
                    coordinate_sha256=coordinate_fingerprint(coordinates),
                )
            )
            if (
                translation_step < self.config.minimum_translation_step_angstrom
                and rotation_step < self.config.minimum_rotation_step_radians
            ):
                break
        receipt = GeometricRigidRefinementReceipt(
            parent_proposal_fingerprint_sha256=proposal.fingerprint_sha256,
            scorer_config_fingerprint_sha256=(
                self.scorer.config_fingerprint_sha256
            ),
            refiner_config_fingerprint_sha256=self.config_fingerprint_sha256,
            requested_steps=requested,
            initial_coordinate_sha256=initial_coordinate_sha256,
            final_coordinate_sha256=coordinate_fingerprint(coordinates),
            initial_score=initial_score,
            final_score=score,
            steps=tuple(rows),
        )
        refined = proposal.with_refined_coordinates(
            coordinates,
            refiner_id=self.refiner_id,
            refiner_version=self.refiner_version,
            refinement_receipt_sha256=receipt.fingerprint_sha256,
        )
        return refined, receipt

    def refine(self, proposal: DockingProposal, *, max_steps: int) -> DockingProposal:
        refined, _receipt = self.refine_with_receipt(proposal, max_steps=max_steps)
        return refined


__all__ = [
    "GEOMETRIC_RIGID_REFINEMENT_BLOCKERS",
    "GEOMETRIC_RIGID_REFINEMENT_RECEIPT_SCHEMA_ID",
    "GEOMETRIC_RIGID_REFINER_SCHEMA_ID",
    "GeometricRigidBodyRefiner",
    "GeometricRigidRefinementConfig",
    "GeometricRigidRefinementError",
    "GeometricRigidRefinementReceipt",
    "GeometricRigidRefinementStep",
]
