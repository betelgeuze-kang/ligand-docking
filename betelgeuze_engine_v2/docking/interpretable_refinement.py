"""Deterministic rigid-plus-torsion local refinement for scorer v0.

The refiner performs bounded coordinate descent over rigid translations,
rigid rotations, and graph-admitted rotatable-bond moves.  It optimizes the
uncalibrated :class:`InterpretablePoseScorerV0` objective and emits a complete
score, rejection, constraint-residual, and coordinate-identity trace.  It is
not force-field minimization and does not expose forces or physical energies.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from numbers import Integral, Real

import torch

from betelgeuze_engine_v2.ai import axis_angle_matrix
from betelgeuze_engine_v2.molecular import (
    canonical_system_sha256,
    canonical_topology_sha256,
)

from .identity import coordinate_fingerprint
from .interpretable_scoring import InterpretablePoseScorerV0
from .molecular_torsion import (
    MOLECULAR_TORSION_SEARCH_BLOCKERS,
    MolecularTorsionSearchConfig,
    MolecularTorsionSearchReceipt,
    build_molecular_torsion_search_space,
)
from .proposals import DockingProposal
from .scoring import DockingScoreBreakdown


INTERPRETABLE_LOCAL_REFINER_V0_SCHEMA_ID = (
    "betelgeuze.engine_v2_interpretable_local_pose_refiner_v0/1.0.0"
)
INTERPRETABLE_LOCAL_REFINEMENT_V0_RECEIPT_SCHEMA_ID = (
    "betelgeuze.engine_v2_interpretable_local_pose_refinement_v0_receipt/1.0.0"
)
INTERPRETABLE_LOCAL_REFINEMENT_V0_BLOCKERS = tuple(
    dict.fromkeys(
        (
            "bounded_coordinate_descent_not_force_field_minimization",
            "optimized_score_is_not_physical_energy",
            "analytic_forces_and_tangent_force_residual_missing",
            "coordinate_descent_steps_not_calibrated",
            "local_basin_search_not_global_pose_generation",
            "ring_and_macrocycle_internal_refinement_missing",
            "stereo_constraints_evaluated_after_not_during_refinement",
            "public_pose_refinement_validation_missing",
            "independent_scientific_review_missing",
            *MOLECULAR_TORSION_SEARCH_BLOCKERS,
        )
    )
)


class InterpretableLocalRefinementError(ValueError):
    """A local-refinement input, configuration, or trace is invalid."""


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
        raise InterpretableLocalRefinementError(
            "interpretable local-refinement value is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _digest(value: object, *, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise InterpretableLocalRefinementError(
            f"{name} must be a lowercase SHA-256"
        )
    return value


def _exact_int(
    value: object,
    *,
    name: str,
    minimum: int = 0,
    maximum: int | None = None,
) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise InterpretableLocalRefinementError(f"{name} must be an integer")
    result = int(value)
    if result < minimum or (maximum is not None and result > maximum):
        raise InterpretableLocalRefinementError(
            f"{name} is outside its integer bound"
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
        raise InterpretableLocalRefinementError(f"{name} must be a real number")
    result = float(value)
    if not math.isfinite(result):
        raise InterpretableLocalRefinementError(f"{name} must be finite")
    if positive and result <= 0.0:
        raise InterpretableLocalRefinementError(f"{name} must be positive")
    if nonnegative and result < 0.0:
        raise InterpretableLocalRefinementError(
            f"{name} must be non-negative"
        )
    return result


def _bond_lengths(
    coordinates: torch.Tensor,
    pairs: torch.Tensor,
) -> torch.Tensor:
    if pairs.numel() == 0:
        return torch.empty(0, dtype=torch.float64)
    return torch.linalg.vector_norm(
        coordinates.index_select(0, pairs[:, 0])
        - coordinates.index_select(0, pairs[:, 1]),
        dim=1,
    )


def _angles(
    coordinates: torch.Tensor,
    triplets: torch.Tensor,
) -> torch.Tensor:
    if triplets.numel() == 0:
        return torch.empty(0, dtype=torch.float64)
    first = coordinates.index_select(0, triplets[:, 0])
    center = coordinates.index_select(0, triplets[:, 1])
    second = coordinates.index_select(0, triplets[:, 2])
    first_vector = first - center
    second_vector = second - center
    denominator = torch.linalg.vector_norm(
        first_vector,
        dim=1,
    ) * torch.linalg.vector_norm(second_vector, dim=1)
    if bool((denominator <= 1.0e-12).any().item()):
        raise InterpretableLocalRefinementError(
            "local-refinement angle contains a collapsed bond"
        )
    cosine = torch.sum(first_vector * second_vector, dim=1) / denominator
    return torch.acos(torch.clamp(cosine, min=-1.0, max=1.0))


@dataclass(frozen=True, slots=True)
class InterpretableLocalRefinementConfig:
    """Capacity, move schedule, and convergence policy for one refiner."""

    maximum_steps: int = 8
    initial_translation_step_angstrom: float = 0.20
    initial_rotation_step_radians: float = 0.08
    initial_torsion_step_radians: float = 0.20
    minimum_translation_step_angstrom: float = 0.0125
    minimum_rotation_step_radians: float = 0.005
    minimum_torsion_step_radians: float = 0.0125
    step_reduction_factor: float = 0.5
    minimum_score_improvement: float = 1.0e-12
    constraint_residual_tolerance: float = 1.0e-8
    max_atoms: int = 4_096
    max_bonds: int = 16_384
    max_rotatable_bonds: int = 64

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "maximum_steps",
            _exact_int(
                self.maximum_steps,
                name="maximum_steps",
                minimum=1,
                maximum=32,
            ),
        )
        step_pairs = (
            (
                "initial_translation_step_angstrom",
                "minimum_translation_step_angstrom",
            ),
            ("initial_rotation_step_radians", "minimum_rotation_step_radians"),
            ("initial_torsion_step_radians", "minimum_torsion_step_radians"),
        )
        for initial_name, minimum_name in step_pairs:
            initial = _finite(
                getattr(self, initial_name),
                name=initial_name,
                positive=True,
            )
            minimum = _finite(
                getattr(self, minimum_name),
                name=minimum_name,
                positive=True,
            )
            if minimum > initial:
                raise InterpretableLocalRefinementError(
                    "minimum local-refinement steps cannot exceed initial steps"
                )
            object.__setattr__(self, initial_name, initial)
            object.__setattr__(self, minimum_name, minimum)
        reduction = _finite(
            self.step_reduction_factor,
            name="step_reduction_factor",
            positive=True,
        )
        if reduction >= 1.0:
            raise InterpretableLocalRefinementError(
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
        object.__setattr__(
            self,
            "constraint_residual_tolerance",
            _finite(
                self.constraint_residual_tolerance,
                name="constraint_residual_tolerance",
                positive=True,
            ),
        )
        object.__setattr__(
            self,
            "max_atoms",
            _exact_int(
                self.max_atoms,
                name="max_atoms",
                minimum=1,
                maximum=4_096,
            ),
        )
        object.__setattr__(
            self,
            "max_bonds",
            _exact_int(
                self.max_bonds,
                name="max_bonds",
                minimum=0,
                maximum=16_384,
            ),
        )
        object.__setattr__(
            self,
            "max_rotatable_bonds",
            _exact_int(
                self.max_rotatable_bonds,
                name="max_rotatable_bonds",
                minimum=0,
                maximum=64,
            ),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": INTERPRETABLE_LOCAL_REFINER_V0_SCHEMA_ID,
            "maximum_steps": self.maximum_steps,
            "initial_translation_step_angstrom": (
                self.initial_translation_step_angstrom
            ),
            "initial_rotation_step_radians": self.initial_rotation_step_radians,
            "initial_torsion_step_radians": self.initial_torsion_step_radians,
            "minimum_translation_step_angstrom": (
                self.minimum_translation_step_angstrom
            ),
            "minimum_rotation_step_radians": self.minimum_rotation_step_radians,
            "minimum_torsion_step_radians": self.minimum_torsion_step_radians,
            "step_reduction_factor": self.step_reduction_factor,
            "minimum_score_improvement": self.minimum_score_improvement,
            "constraint_residual_tolerance": self.constraint_residual_tolerance,
            "max_atoms": self.max_atoms,
            "max_bonds": self.max_bonds,
            "max_rotatable_bonds": self.max_rotatable_bonds,
            "move_policy": (
                "axis_aligned_rigid_translation_rotation_plus_signed_"
                "bridge_torsion_coordinate_descent"
            ),
            "tie_break_policy": "score_then_canonical_move_order",
            "gradient_used": False,
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _sha256(self.to_dict())


@dataclass(frozen=True, slots=True)
class InterpretableLocalRefinementTermDelta:
    term_id: str
    initial_raw_value: float
    initial_contribution: float
    final_raw_value: float
    final_contribution: float

    def __post_init__(self) -> None:
        term_id = str(self.term_id or "").strip()
        if not term_id:
            raise InterpretableLocalRefinementError("term_id must be non-empty")
        object.__setattr__(self, "term_id", term_id)
        for name in (
            "initial_raw_value",
            "initial_contribution",
            "final_raw_value",
            "final_contribution",
        ):
            object.__setattr__(
                self,
                name,
                _finite(getattr(self, name), name=name),
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "term_id": self.term_id,
            "initial_raw_value": self.initial_raw_value,
            "initial_contribution": self.initial_contribution,
            "final_raw_value": self.final_raw_value,
            "final_contribution": self.final_contribution,
            "contribution_delta": (
                self.final_contribution - self.initial_contribution
            ),
        }


@dataclass(frozen=True, slots=True)
class InterpretableLocalRefinementStep:
    iteration: int
    outcome: str
    move_id: str
    score_before: float
    score_after: float
    translation_step_angstrom: float
    rotation_step_radians: float
    torsion_step_radians: float
    evaluated_move_count: int
    rejected_move_count: int
    coordinate_sha256: str
    maximum_bond_length_residual_angstrom: float
    maximum_angle_residual_radians: float

    def __post_init__(self) -> None:
        _exact_int(self.iteration, name="iteration", minimum=1)
        if self.outcome not in {"accepted", "rejected_reduce_steps"}:
            raise InterpretableLocalRefinementError(
                "local-refinement step outcome is invalid"
            )
        if self.outcome == "accepted" and not self.move_id:
            raise InterpretableLocalRefinementError(
                "accepted local-refinement step requires a move ID"
            )
        if self.outcome != "accepted" and self.move_id:
            raise InterpretableLocalRefinementError(
                "rejected local-refinement step cannot name a move"
            )
        before = _finite(self.score_before, name="score_before")
        after = _finite(self.score_after, name="score_after")
        if after > before:
            raise InterpretableLocalRefinementError(
                "local-refinement score trace must be non-increasing"
            )
        if self.outcome == "rejected_reduce_steps" and after != before:
            raise InterpretableLocalRefinementError(
                "rejected local-refinement step must preserve the score"
            )
        for name in (
            "translation_step_angstrom",
            "rotation_step_radians",
            "torsion_step_radians",
        ):
            _finite(getattr(self, name), name=name, positive=True)
        evaluated = _exact_int(
            self.evaluated_move_count,
            name="evaluated_move_count",
            minimum=12,
        )
        rejected = _exact_int(
            self.rejected_move_count,
            name="rejected_move_count",
            minimum=0,
        )
        expected_rejected = evaluated - (1 if self.outcome == "accepted" else 0)
        if rejected != expected_rejected:
            raise InterpretableLocalRefinementError(
                "local-refinement rejected move count is inconsistent"
            )
        _digest(self.coordinate_sha256, name="coordinate_sha256")
        for name in (
            "maximum_bond_length_residual_angstrom",
            "maximum_angle_residual_radians",
        ):
            _finite(getattr(self, name), name=name, nonnegative=True)

    def to_dict(self) -> dict[str, object]:
        return {
            "iteration": self.iteration,
            "outcome": self.outcome,
            "move_id": self.move_id,
            "score_before": self.score_before,
            "score_after": self.score_after,
            "translation_step_angstrom": self.translation_step_angstrom,
            "rotation_step_radians": self.rotation_step_radians,
            "torsion_step_radians": self.torsion_step_radians,
            "evaluated_move_count": self.evaluated_move_count,
            "rejected_move_count": self.rejected_move_count,
            "coordinate_sha256": self.coordinate_sha256,
            "maximum_bond_length_residual_angstrom": (
                self.maximum_bond_length_residual_angstrom
            ),
            "maximum_angle_residual_radians": (
                self.maximum_angle_residual_radians
            ),
        }


@dataclass(frozen=True, slots=True)
class InterpretableLocalRefinementReceipt:
    parent_proposal_fingerprint_sha256: str
    problem_fingerprint_sha256: str
    ligand_system_sha256: str
    ligand_topology_sha256: str
    scorer_config_fingerprint_sha256: str
    feature_binding_sha256: str
    refiner_config_fingerprint_sha256: str
    torsion_search_space_sha256: str
    torsion_search_receipt: MolecularTorsionSearchReceipt
    requested_steps: int
    initial_coordinate_sha256: str
    final_coordinate_sha256: str
    initial_score: float
    final_score: float
    term_deltas: tuple[InterpretableLocalRefinementTermDelta, ...]
    steps: tuple[InterpretableLocalRefinementStep, ...]
    constraint_residual_tolerance: float
    blockers: tuple[str, ...] = INTERPRETABLE_LOCAL_REFINEMENT_V0_BLOCKERS
    schema_id: str = INTERPRETABLE_LOCAL_REFINEMENT_V0_RECEIPT_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != INTERPRETABLE_LOCAL_REFINEMENT_V0_RECEIPT_SCHEMA_ID:
            raise InterpretableLocalRefinementError(
                "unsupported interpretable local-refinement receipt schema"
            )
        for name in (
            "parent_proposal_fingerprint_sha256",
            "problem_fingerprint_sha256",
            "ligand_system_sha256",
            "ligand_topology_sha256",
            "scorer_config_fingerprint_sha256",
            "feature_binding_sha256",
            "refiner_config_fingerprint_sha256",
            "torsion_search_space_sha256",
            "initial_coordinate_sha256",
            "final_coordinate_sha256",
        ):
            _digest(getattr(self, name), name=name)
        if not isinstance(
            self.torsion_search_receipt,
            MolecularTorsionSearchReceipt,
        ):
            raise InterpretableLocalRefinementError(
                "torsion_search_receipt must be MolecularTorsionSearchReceipt"
            )
        if (
            self.torsion_search_receipt.search_space_sha256
            != self.torsion_search_space_sha256
            or self.torsion_search_receipt.system_sha256
            != self.ligand_system_sha256
            or self.torsion_search_receipt.topology_sha256
            != self.ligand_topology_sha256
        ):
            raise InterpretableLocalRefinementError(
                "local-refinement torsion receipt is cross-wired"
            )
        requested = _exact_int(
            self.requested_steps,
            name="requested_steps",
            minimum=1,
            maximum=32,
        )
        steps = tuple(self.steps)
        if len(steps) > requested or tuple(step.iteration for step in steps) != tuple(
            range(1, len(steps) + 1)
        ):
            raise InterpretableLocalRefinementError(
                "local-refinement steps exceed or reorder the requested budget"
            )
        initial = _finite(self.initial_score, name="initial_score")
        final = _finite(self.final_score, name="final_score")
        if final > initial:
            raise InterpretableLocalRefinementError(
                "local-refinement final score must not increase"
            )
        term_deltas = tuple(self.term_deltas)
        if not term_deltas or len({row.term_id for row in term_deltas}) != len(
            term_deltas
        ):
            raise InterpretableLocalRefinementError(
                "local-refinement term deltas must be non-empty and unique"
            )
        if math.fsum(row.initial_contribution for row in term_deltas) != initial:
            raise InterpretableLocalRefinementError(
                "initial term contributions do not reproduce the initial score"
            )
        if math.fsum(row.final_contribution for row in term_deltas) != final:
            raise InterpretableLocalRefinementError(
                "final term contributions do not reproduce the final score"
            )
        tolerance = _finite(
            self.constraint_residual_tolerance,
            name="constraint_residual_tolerance",
            positive=True,
        )
        if steps:
            if steps[0].score_before != initial or steps[-1].score_after != final:
                raise InterpretableLocalRefinementError(
                    "local-refinement receipt scores disagree with its trace"
                )
            for first, second in zip(steps, steps[1:]):
                if first.score_after != second.score_before:
                    raise InterpretableLocalRefinementError(
                        "local-refinement score trace is discontinuous"
                    )
            if steps[-1].coordinate_sha256 != self.final_coordinate_sha256:
                raise InterpretableLocalRefinementError(
                    "local-refinement final coordinate identity disagrees with trace"
                )
            if any(
                max(
                    step.maximum_bond_length_residual_angstrom,
                    step.maximum_angle_residual_radians,
                )
                > tolerance
                for step in steps
            ):
                raise InterpretableLocalRefinementError(
                    "local-refinement constraint residual exceeds tolerance"
                )
        elif (
            initial != final
            or self.initial_coordinate_sha256 != self.final_coordinate_sha256
        ):
            raise InterpretableLocalRefinementError(
                "empty local-refinement trace must preserve score and coordinates"
            )
        if tuple(self.blockers) != INTERPRETABLE_LOCAL_REFINEMENT_V0_BLOCKERS:
            raise InterpretableLocalRefinementError(
                "interpretable local-refinement blockers cannot be promoted"
            )
        object.__setattr__(self, "requested_steps", requested)
        object.__setattr__(self, "term_deltas", term_deltas)
        object.__setattr__(self, "steps", steps)
        object.__setattr__(self, "constraint_residual_tolerance", tolerance)

    @property
    def accepted_step_count(self) -> int:
        return sum(step.outcome == "accepted" for step in self.steps)

    @property
    def rejected_step_count(self) -> int:
        return len(self.steps) - self.accepted_step_count

    @property
    def evaluated_move_count(self) -> int:
        return sum(step.evaluated_move_count for step in self.steps)

    @property
    def rejected_move_count(self) -> int:
        return sum(step.rejected_move_count for step in self.steps)

    @property
    def improved(self) -> bool:
        return self.final_score < self.initial_score

    @property
    def maximum_bond_length_residual_angstrom(self) -> float:
        return max(
            (
                step.maximum_bond_length_residual_angstrom
                for step in self.steps
            ),
            default=0.0,
        )

    @property
    def maximum_angle_residual_radians(self) -> float:
        return max(
            (step.maximum_angle_residual_radians for step in self.steps),
            default=0.0,
        )

    def _payload(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "parent_proposal_fingerprint_sha256": (
                self.parent_proposal_fingerprint_sha256
            ),
            "problem_fingerprint_sha256": self.problem_fingerprint_sha256,
            "ligand_system_sha256": self.ligand_system_sha256,
            "ligand_topology_sha256": self.ligand_topology_sha256,
            "scorer_config_fingerprint_sha256": (
                self.scorer_config_fingerprint_sha256
            ),
            "feature_binding_sha256": self.feature_binding_sha256,
            "refiner_config_fingerprint_sha256": (
                self.refiner_config_fingerprint_sha256
            ),
            "torsion_search_space_sha256": self.torsion_search_space_sha256,
            "torsion_search_receipt_sha256": (
                self.torsion_search_receipt.fingerprint_sha256
            ),
            "rotatable_bond_count": (
                self.torsion_search_receipt.rotatable_bond_count
            ),
            "requested_steps": self.requested_steps,
            "executed_step_count": len(self.steps),
            "accepted_step_count": self.accepted_step_count,
            "rejected_step_count": self.rejected_step_count,
            "evaluated_move_count": self.evaluated_move_count,
            "rejected_move_count": self.rejected_move_count,
            "initial_coordinate_sha256": self.initial_coordinate_sha256,
            "final_coordinate_sha256": self.final_coordinate_sha256,
            "coordinate_sha256_trace": [
                self.initial_coordinate_sha256,
                *(step.coordinate_sha256 for step in self.steps),
            ],
            "initial_score": self.initial_score,
            "final_score": self.final_score,
            "score_trace": [
                self.initial_score,
                *(step.score_after for step in self.steps),
            ],
            "improved": self.improved,
            "term_deltas": [row.to_dict() for row in self.term_deltas],
            "constraint_residual_tolerance": self.constraint_residual_tolerance,
            "maximum_bond_length_residual_angstrom": (
                self.maximum_bond_length_residual_angstrom
            ),
            "maximum_angle_residual_radians": (
                self.maximum_angle_residual_radians
            ),
            "steps": [step.to_dict() for step in self.steps],
            "objective_is_force_field_energy": False,
            "analytic_forces_available": False,
            "tangent_force_residual_available": False,
            "scientifically_validated": False,
            "claim_safe": False,
            "blockers": list(self.blockers),
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _sha256(self._payload())

    def to_dict(self) -> dict[str, object]:
        return {**self._payload(), "receipt_sha256": self.fingerprint_sha256}


@dataclass(frozen=True, slots=True)
class _TorsionMove:
    bond_index: int
    parent_atom_index: int
    child_atom_index: int
    downstream_atom_indices: torch.Tensor


class InterpretableLocalPoseRefinerV0:
    """Bounded deterministic rigid-plus-torsion coordinate descent."""

    refiner_id = "interpretable-local-pose-coordinate-descent-v0"
    refiner_version = "1.0.0"

    def __init__(
        self,
        scorer: InterpretablePoseScorerV0,
        *,
        config: InterpretableLocalRefinementConfig | None = None,
    ) -> None:
        if not isinstance(scorer, InterpretablePoseScorerV0):
            raise InterpretableLocalRefinementError(
                "scorer must be InterpretablePoseScorerV0"
            )
        active = InterpretableLocalRefinementConfig() if config is None else config
        if not isinstance(active, InterpretableLocalRefinementConfig):
            raise InterpretableLocalRefinementError(
                "config must be InterpretableLocalRefinementConfig"
            )
        torsion_config = MolecularTorsionSearchConfig(
            max_atoms=active.max_atoms,
            max_bonds=active.max_bonds,
            max_rotatable_bonds=active.max_rotatable_bonds,
            reconstruction_tolerance_angstrom=min(
                active.constraint_residual_tolerance,
                1.0e-10,
            ),
        )
        torsion_space, torsion_receipt = build_molecular_torsion_search_space(
            scorer.ligand,
            config=torsion_config,
        )
        parent = tuple(int(value) for value in torsion_space.parent.tolist())
        selected_rows = tuple(
            row for row in torsion_receipt.bond_rows if row.status == "selected"
        )
        torsion_moves: list[_TorsionMove] = []
        for row in selected_rows:
            descendants = tuple(
                atom_index
                for atom_index in range(len(parent))
                if self._is_descendant(
                    atom_index,
                    row.child_atom_index,
                    parent,
                )
            )
            if row.child_atom_index not in descendants:
                raise InterpretableLocalRefinementError(
                    "selected torsion child is missing from its downstream side"
                )
            torsion_moves.append(
                _TorsionMove(
                    bond_index=row.bond_index,
                    parent_atom_index=row.parent_atom_index,
                    child_atom_index=row.child_atom_index,
                    downstream_atom_indices=torch.tensor(
                        descendants,
                        dtype=torch.long,
                    ),
                )
            )
        bond_pairs = tuple((bond.atom_i, bond.atom_j) for bond in scorer.ligand.bonds)
        angle_triplets = tuple(scorer.angle_triplets)
        self._bond_indices = torch.tensor(bond_pairs, dtype=torch.long).reshape(-1, 2)
        self._angle_indices = torch.tensor(
            angle_triplets,
            dtype=torch.long,
        ).reshape(-1, 3)
        self._reference_bond_lengths = _bond_lengths(
            scorer.reference_ligand_coordinates,
            self._bond_indices,
        )
        self._reference_angles = _angles(
            scorer.reference_ligand_coordinates,
            self._angle_indices,
        )
        self.scorer = scorer
        self.config = active
        self.torsion_search_receipt = torsion_receipt
        self.torsion_search_space_sha256 = torsion_space.fingerprint_sha256
        self._torsion_moves = tuple(torsion_moves)
        self.config_fingerprint_sha256 = _sha256(
            {
                "schema_id": INTERPRETABLE_LOCAL_REFINER_V0_SCHEMA_ID,
                "config_sha256": active.fingerprint_sha256,
                "problem_fingerprint_sha256": scorer.problem.fingerprint_sha256,
                "scorer_config_fingerprint_sha256": (
                    scorer.config_fingerprint_sha256
                ),
                "feature_binding_sha256": scorer.feature_binding_sha256,
                "ligand_system_sha256": canonical_system_sha256(scorer.ligand),
                "ligand_topology_sha256": canonical_topology_sha256(
                    scorer.ligand
                ),
                "torsion_search_space_sha256": (
                    self.torsion_search_space_sha256
                ),
                "torsion_search_receipt_sha256": (
                    torsion_receipt.fingerprint_sha256
                ),
            }
        )

    @property
    def problem_fingerprint_sha256(self) -> str:
        return self.scorer.problem.fingerprint_sha256

    @property
    def blockers(self) -> tuple[str, ...]:
        return INTERPRETABLE_LOCAL_REFINEMENT_V0_BLOCKERS

    @property
    def rotatable_bond_count(self) -> int:
        return len(self._torsion_moves)

    @staticmethod
    def _is_descendant(
        atom_index: int,
        ancestor: int,
        parent: tuple[int, ...],
    ) -> bool:
        current = atom_index
        while current >= 0:
            if current == ancestor:
                return True
            current = parent[current]
        return False

    def _constraint_residuals(
        self,
        coordinates: torch.Tensor,
    ) -> tuple[float, float]:
        observed_bonds = _bond_lengths(coordinates, self._bond_indices)
        observed_angles = _angles(coordinates, self._angle_indices)
        bond_residual = (
            0.0
            if observed_bonds.numel() == 0
            else float(
                (observed_bonds - self._reference_bond_lengths).abs().max().item()
            )
        )
        angle_residual = (
            0.0
            if observed_angles.numel() == 0
            else float((observed_angles - self._reference_angles).abs().max().item())
        )
        return bond_residual, angle_residual

    @staticmethod
    def _rigid_moves(
        coordinates: torch.Tensor,
        *,
        translation_step: float,
        rotation_step: float,
    ) -> tuple[tuple[str, torch.Tensor], ...]:
        axes = torch.eye(3, dtype=coordinates.dtype)
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
                angle = torch.tensor(
                    [sign * rotation_step],
                    dtype=coordinates.dtype,
                )
                rotation = axis_angle_matrix(axis, angle)[0]
                moves.append(
                    (
                        f"rotate_{'xyz'[axis_index]}_{label}",
                        centered @ rotation.T + centroid,
                    )
                )
        return tuple(moves)

    def _moves(
        self,
        coordinates: torch.Tensor,
        *,
        translation_step: float,
        rotation_step: float,
        torsion_step: float,
    ) -> tuple[tuple[str, torch.Tensor], ...]:
        moves = list(
            self._rigid_moves(
                coordinates,
                translation_step=translation_step,
                rotation_step=rotation_step,
            )
        )
        for torsion in self._torsion_moves:
            origin = coordinates[torsion.parent_atom_index]
            axis = coordinates[torsion.child_atom_index] - origin
            axis_norm = torch.linalg.vector_norm(axis)
            if float(axis_norm.item()) <= 1.0e-12:
                raise InterpretableLocalRefinementError(
                    "torsion move contains a collapsed central bond"
                )
            unit_axis = (axis / axis_norm).reshape(1, 3)
            for sign, label in ((-1.0, "minus"), (1.0, "plus")):
                angle = torch.tensor(
                    [sign * torsion_step],
                    dtype=coordinates.dtype,
                )
                rotation = axis_angle_matrix(unit_axis, angle)[0]
                candidate = coordinates.clone()
                selected = candidate.index_select(
                    0,
                    torsion.downstream_atom_indices,
                )
                candidate[torsion.downstream_atom_indices] = (
                    (selected - origin) @ rotation.T + origin
                )
                moves.append(
                    (
                        f"torsion_bond_{torsion.bond_index:05d}_{label}",
                        candidate,
                    )
                )
        return tuple(moves)

    @staticmethod
    def _term_deltas(
        initial: DockingScoreBreakdown,
        final: DockingScoreBreakdown,
    ) -> tuple[InterpretableLocalRefinementTermDelta, ...]:
        if tuple(term.term_id for term in initial.terms) != tuple(
            term.term_id for term in final.terms
        ):
            raise InterpretableLocalRefinementError(
                "local-refinement score term order changed"
            )
        return tuple(
            InterpretableLocalRefinementTermDelta(
                term_id=initial_term.term_id,
                initial_raw_value=initial_term.raw_value,
                initial_contribution=initial_term.contribution,
                final_raw_value=final_term.raw_value,
                final_contribution=final_term.contribution,
            )
            for initial_term, final_term in zip(
                initial.terms,
                final.terms,
                strict=True,
            )
        )

    def refine_with_receipt(
        self,
        proposal: DockingProposal,
        *,
        max_steps: int,
    ) -> tuple[DockingProposal, InterpretableLocalRefinementReceipt]:
        if not isinstance(proposal, DockingProposal):
            raise InterpretableLocalRefinementError(
                "proposal must be DockingProposal"
            )
        requested = _exact_int(
            max_steps,
            name="max_steps",
            minimum=1,
            maximum=32,
        )
        if requested > self.config.maximum_steps:
            raise InterpretableLocalRefinementError(
                "requested local refinement exceeds the configured bound"
            )
        proposal.assert_integrity()
        if proposal.problem_fingerprint_sha256 != self.problem_fingerprint_sha256:
            raise InterpretableLocalRefinementError(
                "proposal problem identity does not match the local refiner"
            )
        coordinates = proposal.coordinates.detach().clone()
        if (
            coordinates.dtype != torch.float64
            or coordinates.device.type != "cpu"
            or coordinates.shape != (self.scorer.ligand.atom_count, 3)
        ):
            raise InterpretableLocalRefinementError(
                "local refinement requires CPU float64 ligand coordinates"
            )
        initial_coordinate_sha256 = coordinate_fingerprint(coordinates)
        initial_breakdown = self.scorer.score_coordinates(coordinates)
        score = initial_breakdown.total_score
        initial_score = score
        initial_bond_residual, initial_angle_residual = self._constraint_residuals(
            coordinates
        )
        if max(initial_bond_residual, initial_angle_residual) > (
            self.config.constraint_residual_tolerance
        ):
            raise InterpretableLocalRefinementError(
                "proposal violates the local-refinement bond or angle constraint"
            )
        translation_step = self.config.initial_translation_step_angstrom
        rotation_step = self.config.initial_rotation_step_radians
        torsion_step = self.config.initial_torsion_step_radians
        rows: list[InterpretableLocalRefinementStep] = []
        final_breakdown = initial_breakdown
        for iteration in range(1, requested + 1):
            before = score
            used_translation_step = translation_step
            used_rotation_step = rotation_step
            used_torsion_step = torsion_step
            candidates: list[
                tuple[
                    float,
                    int,
                    str,
                    torch.Tensor,
                    DockingScoreBreakdown,
                    float,
                    float,
                ]
            ] = []
            for move_index, (move_id, candidate) in enumerate(
                self._moves(
                    coordinates,
                    translation_step=translation_step,
                    rotation_step=rotation_step,
                    torsion_step=torsion_step,
                )
            ):
                bond_residual, angle_residual = self._constraint_residuals(candidate)
                if max(bond_residual, angle_residual) > (
                    self.config.constraint_residual_tolerance
                ):
                    raise InterpretableLocalRefinementError(
                        "candidate move violates the bond or angle constraint"
                    )
                breakdown = self.scorer.score_coordinates(candidate)
                candidates.append(
                    (
                        breakdown.total_score,
                        move_index,
                        move_id,
                        candidate,
                        breakdown,
                        bond_residual,
                        angle_residual,
                    )
                )
            (
                best_score,
                _move_index,
                move_id,
                best_coordinates,
                best_breakdown,
                best_bond_residual,
                best_angle_residual,
            ) = min(candidates, key=lambda row: (row[0], row[1]))
            if best_score < before - self.config.minimum_score_improvement:
                coordinates = best_coordinates
                score = best_score
                final_breakdown = best_breakdown
                bond_residual = best_bond_residual
                angle_residual = best_angle_residual
                outcome = "accepted"
            else:
                move_id = ""
                score = before
                bond_residual, angle_residual = self._constraint_residuals(
                    coordinates
                )
                outcome = "rejected_reduce_steps"
                translation_step *= self.config.step_reduction_factor
                rotation_step *= self.config.step_reduction_factor
                torsion_step *= self.config.step_reduction_factor
            rows.append(
                InterpretableLocalRefinementStep(
                    iteration=iteration,
                    outcome=outcome,
                    move_id=move_id,
                    score_before=before,
                    score_after=score,
                    translation_step_angstrom=used_translation_step,
                    rotation_step_radians=used_rotation_step,
                    torsion_step_radians=used_torsion_step,
                    evaluated_move_count=len(candidates),
                    rejected_move_count=(
                        len(candidates) - (1 if outcome == "accepted" else 0)
                    ),
                    coordinate_sha256=coordinate_fingerprint(coordinates),
                    maximum_bond_length_residual_angstrom=bond_residual,
                    maximum_angle_residual_radians=angle_residual,
                )
            )
            if (
                translation_step < self.config.minimum_translation_step_angstrom
                and rotation_step < self.config.minimum_rotation_step_radians
                and (
                    not self._torsion_moves
                    or torsion_step < self.config.minimum_torsion_step_radians
                )
            ):
                break
        receipt = InterpretableLocalRefinementReceipt(
            parent_proposal_fingerprint_sha256=proposal.fingerprint_sha256,
            problem_fingerprint_sha256=self.problem_fingerprint_sha256,
            ligand_system_sha256=canonical_system_sha256(self.scorer.ligand),
            ligand_topology_sha256=canonical_topology_sha256(self.scorer.ligand),
            scorer_config_fingerprint_sha256=(
                self.scorer.config_fingerprint_sha256
            ),
            feature_binding_sha256=self.scorer.feature_binding_sha256,
            refiner_config_fingerprint_sha256=self.config_fingerprint_sha256,
            torsion_search_space_sha256=self.torsion_search_space_sha256,
            torsion_search_receipt=self.torsion_search_receipt,
            requested_steps=requested,
            initial_coordinate_sha256=initial_coordinate_sha256,
            final_coordinate_sha256=coordinate_fingerprint(coordinates),
            initial_score=initial_score,
            final_score=score,
            term_deltas=self._term_deltas(initial_breakdown, final_breakdown),
            steps=tuple(rows),
            constraint_residual_tolerance=(
                self.config.constraint_residual_tolerance
            ),
        )
        refined = proposal.with_refined_coordinates(
            coordinates,
            refiner_id=self.refiner_id,
            refiner_version=self.refiner_version,
            refinement_receipt_sha256=receipt.fingerprint_sha256,
        )
        return refined, receipt

    def refine(self, proposal: DockingProposal, *, max_steps: int) -> DockingProposal:
        refined, _receipt = self.refine_with_receipt(
            proposal,
            max_steps=max_steps,
        )
        return refined


__all__ = [
    "INTERPRETABLE_LOCAL_REFINEMENT_V0_BLOCKERS",
    "INTERPRETABLE_LOCAL_REFINEMENT_V0_RECEIPT_SCHEMA_ID",
    "INTERPRETABLE_LOCAL_REFINER_V0_SCHEMA_ID",
    "InterpretableLocalPoseRefinerV0",
    "InterpretableLocalRefinementConfig",
    "InterpretableLocalRefinementError",
    "InterpretableLocalRefinementReceipt",
    "InterpretableLocalRefinementStep",
    "InterpretableLocalRefinementTermDelta",
]
