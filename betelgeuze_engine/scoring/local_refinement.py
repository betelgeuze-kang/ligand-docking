"""Energy-based bounded local refinement with a full evidence row (P1-6).

The existing rigid-body minimizer optimized a coarse contact score and reported
only whether it improved. That is not enough to trust a refined pose: a
reviewer cannot tell how far the ligand moved, whether the run converged, which
parameters produced it, or whether a "refined" pose is actually a different
binding mode that drifted out of the pocket.

This refinement:

- minimizes the V2 scalar energy (Scorer v1 total), not a proxy contact count;
- is bounded: every step and the total displacement are capped, so refinement
  cannot silently relocate the ligand;
- records pre/post coordinates, the score delta, maximum displacement,
  convergence, a failure row, and the exact parameter identity.

A failed or non-converged refinement is reported, never dropped: the caller must
be able to count refinement failures in a benchmark denominator.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, field
from typing import Any, Sequence

import numpy as np

from betelgeuze_engine.scoring.scorer_v1 import score_pose_v1

LOCAL_REFINEMENT_SCHEMA_VERSION = "energy_based_local_refinement_v1"

METHOD = "bounded_finite_difference_rigid_body_scorer_v1_energy"

DEFAULT_MAX_STEPS = 24
DEFAULT_TRANSLATION_STEP_A = 0.20
DEFAULT_ROTATION_STEP_RAD = 0.05
DEFAULT_MAX_DISPLACEMENT_A = 1.5
DEFAULT_CONVERGENCE_DELTA = 1e-4
DEFAULT_GRADIENT_TOLERANCE = 1e-8

STATUS_CONVERGED = "local_refinement_converged"
STATUS_MAX_STEPS = "local_refinement_step_budget_exhausted"
STATUS_NO_IMPROVEMENT = "local_refinement_no_improvement"
STATUS_DISPLACEMENT_BOUND = "local_refinement_displacement_bound_reached"
STATUS_FAILED = "local_refinement_failed"

TERMINAL_STATUSES = (
    STATUS_CONVERGED,
    STATUS_MAX_STEPS,
    STATUS_NO_IMPROVEMENT,
    STATUS_DISPLACEMENT_BOUND,
    STATUS_FAILED,
)

CLAIM_BOUNDARY = (
    "Bounded local refinement of an internal uncalibrated Scorer v1 energy only. It reports pre/post "
    "coordinates, score delta, displacement, and convergence as evidence; it is not an energy minimization "
    "claim, a calibrated binding energy, or a benchmarked pose-accuracy claim."
)


@dataclass(frozen=True)
class RefinementParameters:
    """Exact parameter identity, so a refinement can be replayed."""

    max_steps: int = DEFAULT_MAX_STEPS
    translation_step_a: float = DEFAULT_TRANSLATION_STEP_A
    rotation_step_rad: float = DEFAULT_ROTATION_STEP_RAD
    max_displacement_a: float = DEFAULT_MAX_DISPLACEMENT_A
    convergence_delta: float = DEFAULT_CONVERGENCE_DELTA
    gradient_tolerance: float = DEFAULT_GRADIENT_TOLERANCE

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["method"] = METHOD
        return payload

    @property
    def parameter_digest(self) -> str:
        return hashlib.sha256(
            json.dumps(self.as_dict(), sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()


@dataclass(frozen=True)
class RefinementResult:
    """Refinement evidence row."""

    status: str
    parameters: RefinementParameters
    pre_coordinates: tuple[tuple[float, float, float], ...]
    post_coordinates: tuple[tuple[float, float, float], ...]
    pre_score: float
    post_score: float
    steps_taken: int
    line_search_backtracks: int
    max_atom_displacement_a: float
    centroid_displacement_a: float
    converged: bool
    failure_reason: str = ""
    blockers: tuple[str, ...] = field(default_factory=tuple)

    @property
    def score_delta(self) -> float:
        """Negative means the refinement improved the pose."""

        return float(self.post_score - self.pre_score)

    @property
    def improved(self) -> bool:
        return self.score_delta < -float(self.parameters.convergence_delta)

    @property
    def failed(self) -> bool:
        return self.status == STATUS_FAILED

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": LOCAL_REFINEMENT_SCHEMA_VERSION,
            "status": self.status,
            "method": METHOD,
            "converged": bool(self.converged),
            "improved": bool(self.improved),
            "failed": bool(self.failed),
            "failure_reason": self.failure_reason,
            "pre_score": float(self.pre_score),
            "post_score": float(self.post_score),
            "score_delta": self.score_delta,
            "steps_taken": int(self.steps_taken),
            "line_search_backtracks": int(self.line_search_backtracks),
            "max_atom_displacement_a": float(self.max_atom_displacement_a),
            "centroid_displacement_a": float(self.centroid_displacement_a),
            "max_displacement_bound_a": float(self.parameters.max_displacement_a),
            "displacement_within_bound": bool(
                self.max_atom_displacement_a <= float(self.parameters.max_displacement_a) + 1e-6
            ),
            "pre_coordinates": [list(row) for row in self.pre_coordinates],
            "post_coordinates": [list(row) for row in self.post_coordinates],
            "parameters": self.parameters.as_dict(),
            "parameter_digest": self.parameters.parameter_digest,
            "blockers": list(self.blockers),
            "claim_boundary": CLAIM_BOUNDARY,
        }


def _rotation_matrix(rotation_rad: np.ndarray) -> np.ndarray:
    rx, ry, rz = (float(rotation_rad[0]), float(rotation_rad[1]), float(rotation_rad[2]))
    cx, sx = math.cos(rx), math.sin(rx)
    cy, sy = math.cos(ry), math.sin(ry)
    cz, sz = math.cos(rz), math.sin(rz)
    mx = np.asarray([[1, 0, 0], [0, cx, -sx], [0, sx, cx]], dtype=np.float64)
    my = np.asarray([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]], dtype=np.float64)
    mz = np.asarray([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]], dtype=np.float64)
    return mz @ my @ mx


def _apply_delta(coords: np.ndarray, translation: np.ndarray, rotation: np.ndarray) -> np.ndarray:
    centroid = coords.mean(axis=0)
    rotated = (coords - centroid) @ _rotation_matrix(rotation).T + centroid
    return rotated + np.asarray(translation, dtype=np.float64).reshape(1, 3)


def _tuples(coords: np.ndarray) -> tuple[tuple[float, float, float], ...]:
    return tuple(
        (round(float(row[0]), 4), round(float(row[1]), 4), round(float(row[2]), 4))
        for row in coords
    )


def refine_pose_locally(
    protein_xyz: Any,
    ligand_xyz: Any,
    *,
    protein_elements: Sequence[str] | None = None,
    ligand_elements: Sequence[str] | None = None,
    protein_charges: Sequence[float] | None = None,
    ligand_charges: Sequence[float] | None = None,
    ligand_smiles: str = "",
    pocket_center: Any = None,
    pocket_radius_a: float = 8.0,
    parameters: RefinementParameters | None = None,
) -> RefinementResult:
    """Bounded local refinement of a pose against the Scorer v1 energy."""

    params = parameters or RefinementParameters()
    protein = np.asarray(protein_xyz, dtype=np.float64).reshape(-1, 3)
    original = np.asarray(ligand_xyz, dtype=np.float64).reshape(-1, 3)

    def _energy(coords: np.ndarray) -> float:
        result = score_pose_v1(
            protein,
            coords,
            protein_elements=protein_elements,
            ligand_elements=ligand_elements,
            protein_charges=protein_charges,
            ligand_charges=ligand_charges,
            ligand_smiles=ligand_smiles,
            pocket_center=pocket_center,
            pocket_radius_a=pocket_radius_a,
        )
        if not result.ready:
            return float("inf")
        return float(result.total_score)

    if protein.shape[0] == 0 or original.shape[0] == 0:
        return RefinementResult(
            status=STATUS_FAILED,
            parameters=params,
            pre_coordinates=_tuples(original),
            post_coordinates=_tuples(original),
            pre_score=float("inf"),
            post_score=float("inf"),
            steps_taken=0,
            line_search_backtracks=0,
            max_atom_displacement_a=0.0,
            centroid_displacement_a=0.0,
            converged=False,
            failure_reason="refinement_requires_protein_and_ligand_coordinates",
            blockers=("refinement_requires_protein_and_ligand_coordinates",),
        )

    pre_score = _energy(original)
    if not math.isfinite(pre_score):
        return RefinementResult(
            status=STATUS_FAILED,
            parameters=params,
            pre_coordinates=_tuples(original),
            post_coordinates=_tuples(original),
            pre_score=pre_score,
            post_score=pre_score,
            steps_taken=0,
            line_search_backtracks=0,
            max_atom_displacement_a=0.0,
            centroid_displacement_a=0.0,
            converged=False,
            failure_reason="initial_pose_energy_not_finite",
            blockers=("initial_pose_energy_not_finite",),
        )

    coords = original.copy()
    current = pre_score
    steps = 0
    backtracks = 0
    status = STATUS_MAX_STEPS
    step_scale = np.asarray(
        [
            params.translation_step_a,
            params.translation_step_a,
            params.translation_step_a,
            params.rotation_step_rad,
            params.rotation_step_rad,
            params.rotation_step_rad,
        ],
        dtype=np.float64,
    )
    probe = step_scale * 0.25

    for _iteration in range(int(max(params.max_steps, 0))):
        gradient = np.zeros(6, dtype=np.float64)
        for axis in range(6):
            plus = np.zeros(6, dtype=np.float64)
            minus = np.zeros(6, dtype=np.float64)
            plus[axis] = probe[axis]
            minus[axis] = -probe[axis]
            forward = _energy(_apply_delta(coords, plus[:3], plus[3:]))
            backward = _energy(_apply_delta(coords, minus[:3], minus[3:]))
            if not (math.isfinite(forward) and math.isfinite(backward)):
                continue
            gradient[axis] = (forward - backward) / (2.0 * probe[axis]) * step_scale[axis]
        norm = float(np.linalg.norm(gradient))
        if not math.isfinite(norm) or norm < float(params.gradient_tolerance):
            status = STATUS_CONVERGED
            break

        direction = -gradient / norm
        accepted = False
        scale = 1.0
        for _backtrack in range(8):
            delta = direction * step_scale * scale
            candidate = _apply_delta(coords, delta[:3], delta[3:])
            # Bounded: reject any step that moves an atom past the cap, measured
            # against the ORIGINAL pose so steps cannot accumulate past it.
            displacement = float(np.max(np.linalg.norm(candidate - original, axis=1)))
            if displacement > float(params.max_displacement_a):
                scale *= 0.5
                backtracks += 1
                continue
            candidate_score = _energy(candidate)
            if math.isfinite(candidate_score) and candidate_score < current - float(
                params.convergence_delta
            ):
                coords = candidate
                current = candidate_score
                steps += 1
                accepted = True
                break
            scale *= 0.5
            backtracks += 1
        if not accepted:
            max_now = float(np.max(np.linalg.norm(coords - original, axis=1)))
            if max_now >= float(params.max_displacement_a) - 1e-6:
                status = STATUS_DISPLACEMENT_BOUND
            elif steps == 0:
                status = STATUS_NO_IMPROVEMENT
            else:
                status = STATUS_CONVERGED
            break

    max_displacement = float(np.max(np.linalg.norm(coords - original, axis=1)))
    centroid_displacement = float(
        np.linalg.norm(coords.mean(axis=0) - original.mean(axis=0))
    )
    converged = status == STATUS_CONVERGED
    return RefinementResult(
        status=status,
        parameters=params,
        pre_coordinates=_tuples(original),
        post_coordinates=_tuples(coords),
        pre_score=float(pre_score),
        post_score=float(current),
        steps_taken=int(steps),
        line_search_backtracks=int(backtracks),
        max_atom_displacement_a=max_displacement,
        centroid_displacement_a=centroid_displacement,
        converged=converged,
    )


__all__ = [
    "CLAIM_BOUNDARY",
    "DEFAULT_MAX_DISPLACEMENT_A",
    "DEFAULT_MAX_STEPS",
    "LOCAL_REFINEMENT_SCHEMA_VERSION",
    "METHOD",
    "RefinementParameters",
    "RefinementResult",
    "STATUS_CONVERGED",
    "STATUS_DISPLACEMENT_BOUND",
    "STATUS_FAILED",
    "STATUS_MAX_STEPS",
    "STATUS_NO_IMPROVEMENT",
    "TERMINAL_STATUSES",
    "refine_pose_locally",
]
