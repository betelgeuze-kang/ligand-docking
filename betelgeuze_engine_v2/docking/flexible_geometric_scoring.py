"""Element-geometry scoring with a bounded flexible-ligand self-overlap term.

The scorer composes the rigid element-geometry diagnostic and adds one
topology-aware nonbonded intraligand overlap penalty.  Covalent 1-2 and angular
1-3 pairs are excluded.  No torsion potential, bonded force field, charge model,
or calibrated docking weights are implied.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
from numbers import Integral, Real
from typing import Sequence

import torch

from .geometric_scoring import (
    GEOMETRY_DIAGNOSTIC_RADII_ANGSTROM,
    GEOMETRY_DIAGNOSTIC_RADIUS_PROFILE_SHA256,
    ElementGeometryDiagnosticScoreConfig,
    ElementGeometryDiagnosticScorer,
)
from .identity import DockingProblemIdentity
from .proposals import DockingProposal
from .scoring import (
    DockingScoreBreakdown,
    DockingScoreDescriptor,
    DockingScoreTerm,
    ScoreDirection,
)


FLEXIBLE_GEOMETRY_DIAGNOSTIC_SCORER_SCHEMA_ID = (
    "betelgeuze.engine_v2_flexible_geometry_diagnostic_scorer/1.0.0"
)
FLEXIBLE_GEOMETRY_DIAGNOSTIC_BLOCKERS = (
    "flexible_geometry_score_is_not_force_field_energy",
    "intraligand_self_overlap_is_not_a_torsion_energy_model",
    "bonded_angle_torsion_and_improper_energy_missing",
    "formal_and_partial_charge_scoring_missing",
    "aromatic_stereo_hbond_and_metal_chemistry_missing",
    "score_weights_not_fitted_or_calibrated",
    "public_flexible_pose_ranking_validation_missing",
)


class FlexibleGeometryDiagnosticScoringError(ValueError):
    """Flexible geometry score inputs exceed the bounded contract."""


def _canonical_sha256(value: object) -> str:
    try:
        encoded = json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise FlexibleGeometryDiagnosticScoringError(
            "flexible geometry value is not canonical JSON"
        ) from exc
    return hashlib.sha256(encoded).hexdigest()


def _finite(
    value: object,
    *,
    name: str,
    positive: bool = False,
    nonnegative: bool = False,
) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise FlexibleGeometryDiagnosticScoringError(f"{name} must be a real number")
    result = float(value)
    if not math.isfinite(result):
        raise FlexibleGeometryDiagnosticScoringError(f"{name} must be finite")
    if positive and result <= 0.0:
        raise FlexibleGeometryDiagnosticScoringError(f"{name} must be positive")
    if nonnegative and result < 0.0:
        raise FlexibleGeometryDiagnosticScoringError(
            f"{name} must be non-negative"
        )
    return result


def _exact_int(value: object, *, name: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise FlexibleGeometryDiagnosticScoringError(f"{name} must be an integer")
    result = int(value)
    if result < minimum:
        raise FlexibleGeometryDiagnosticScoringError(
            f"{name} must be at least {minimum}"
        )
    return result


@dataclass(frozen=True, slots=True)
class FlexibleGeometryDiagnosticScoreConfig:
    base_geometry: ElementGeometryDiagnosticScoreConfig = field(
        default_factory=ElementGeometryDiagnosticScoreConfig
    )
    ligand_self_overlap_scale: float = 0.75
    ligand_self_overlap_weight: float = 25.0
    max_ligand_nonbonded_pairs: int = 32_640

    def __post_init__(self) -> None:
        if not isinstance(self.base_geometry, ElementGeometryDiagnosticScoreConfig):
            raise FlexibleGeometryDiagnosticScoringError(
                "base_geometry must be ElementGeometryDiagnosticScoreConfig"
            )
        scale = _finite(
            self.ligand_self_overlap_scale,
            name="ligand_self_overlap_scale",
            positive=True,
        )
        if scale > 1.5:
            raise FlexibleGeometryDiagnosticScoringError(
                "ligand_self_overlap_scale must not exceed 1.5"
            )
        weight = _finite(
            self.ligand_self_overlap_weight,
            name="ligand_self_overlap_weight",
            nonnegative=True,
        )
        maximum = _exact_int(
            self.max_ligand_nonbonded_pairs,
            name="max_ligand_nonbonded_pairs",
            minimum=1,
        )
        if maximum > 1_000_000:
            raise FlexibleGeometryDiagnosticScoringError(
                "max_ligand_nonbonded_pairs must not exceed 1000000"
            )
        object.__setattr__(self, "ligand_self_overlap_scale", scale)
        object.__setattr__(self, "ligand_self_overlap_weight", weight)
        object.__setattr__(self, "max_ligand_nonbonded_pairs", maximum)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": FLEXIBLE_GEOMETRY_DIAGNOSTIC_SCORER_SCHEMA_ID,
            "base_geometry": self.base_geometry.to_dict(),
            "ligand_self_overlap_scale": self.ligand_self_overlap_scale,
            "ligand_self_overlap_weight": self.ligand_self_overlap_weight,
            "max_ligand_nonbonded_pairs": self.max_ligand_nonbonded_pairs,
            "pair_exclusion_policy": "exclude_covalent_1_2_and_angular_1_3_pairs",
            "torsion_energy_evaluated": False,
            "bonded_force_field_evaluated": False,
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())


def _canonical_bond_pairs(
    bond_pairs: Sequence[tuple[int, int]],
    *,
    atom_count: int,
) -> tuple[tuple[int, int], ...]:
    rows: list[tuple[int, int]] = []
    for pair in bond_pairs:
        if not isinstance(pair, (tuple, list)) or len(pair) != 2:
            raise FlexibleGeometryDiagnosticScoringError(
                "ligand bond pairs must contain two atom indices"
            )
        first = _exact_int(pair[0], name="ligand bond atom index")
        second = _exact_int(pair[1], name="ligand bond atom index")
        if first >= atom_count or second >= atom_count or first == second:
            raise FlexibleGeometryDiagnosticScoringError(
                "ligand bond pair is out of bounds or self-referential"
            )
        rows.append(tuple(sorted((first, second))))
    canonical = tuple(sorted(set(rows)))
    if len(canonical) != len(rows):
        raise FlexibleGeometryDiagnosticScoringError(
            "ligand bond pairs must be unique"
        )
    return canonical


def _nonbonded_pair_indices(
    atom_count: int,
    bond_pairs: tuple[tuple[int, int], ...],
) -> tuple[tuple[int, int], ...]:
    adjacency: list[set[int]] = [set() for _ in range(atom_count)]
    excluded = set(bond_pairs)
    for first, second in bond_pairs:
        adjacency[first].add(second)
        adjacency[second].add(first)
    for center in range(atom_count):
        neighbors = sorted(adjacency[center])
        for first_index, first in enumerate(neighbors):
            for second in neighbors[first_index + 1 :]:
                excluded.add(tuple(sorted((first, second))))
    return tuple(
        (first, second)
        for first in range(atom_count)
        for second in range(first + 1, atom_count)
        if (first, second) not in excluded
    )


class ElementFlexibleGeometryDiagnosticScorer:
    """Geometry-only interaction score plus element-aware ligand self-overlap."""

    scorer_id = "element-flexible-geometry-diagnostic"
    scorer_version = "1.0.0"
    validated_for_docking_ranking = False

    def __init__(
        self,
        receptor_coordinates: torch.Tensor,
        receptor_atomic_numbers: Sequence[int],
        ligand_atomic_numbers: Sequence[int],
        ligand_bond_pairs: Sequence[tuple[int, int]],
        problem: DockingProblemIdentity,
        *,
        config: FlexibleGeometryDiagnosticScoreConfig | None = None,
    ) -> None:
        active = (
            FlexibleGeometryDiagnosticScoreConfig() if config is None else config
        )
        if not isinstance(active, FlexibleGeometryDiagnosticScoreConfig):
            raise FlexibleGeometryDiagnosticScoringError(
                "config must be FlexibleGeometryDiagnosticScoreConfig"
            )
        self.base_scorer = ElementGeometryDiagnosticScorer(
            receptor_coordinates,
            receptor_atomic_numbers,
            ligand_atomic_numbers,
            problem,
            config=active.base_geometry,
        )
        self.config = active
        self.problem = problem
        self.ligand_atomic_numbers = tuple(int(value) for value in ligand_atomic_numbers)
        self.ligand_bond_pairs = _canonical_bond_pairs(
            ligand_bond_pairs,
            atom_count=len(self.ligand_atomic_numbers),
        )
        self.ligand_nonbonded_pairs = _nonbonded_pair_indices(
            len(self.ligand_atomic_numbers),
            self.ligand_bond_pairs,
        )
        if len(self.ligand_nonbonded_pairs) > active.max_ligand_nonbonded_pairs:
            raise FlexibleGeometryDiagnosticScoringError(
                "ligand nonbonded-pair count exceeds the configured capacity"
            )
        self._pair_indices = torch.tensor(
            self.ligand_nonbonded_pairs,
            dtype=torch.long,
        ).reshape(-1, 2)
        ligand_radii = torch.tensor(
            [
                GEOMETRY_DIAGNOSTIC_RADII_ANGSTROM[value]
                for value in self.ligand_atomic_numbers
            ],
            dtype=torch.float64,
        )
        self._ligand_radius_sums = (
            ligand_radii.index_select(0, self._pair_indices[:, 0])
            + ligand_radii.index_select(0, self._pair_indices[:, 1])
            if self._pair_indices.numel()
            else torch.empty(0, dtype=torch.float64)
        )
        self.parameter_source_sha256 = GEOMETRY_DIAGNOSTIC_RADIUS_PROFILE_SHA256
        self.config_fingerprint_sha256 = _canonical_sha256(
            {
                "schema_id": FLEXIBLE_GEOMETRY_DIAGNOSTIC_SCORER_SCHEMA_ID,
                "config_sha256": active.fingerprint_sha256,
                "base_scorer_config_sha256": (
                    self.base_scorer.config_fingerprint_sha256
                ),
                "problem_sha256": problem.fingerprint_sha256,
                "ligand_bond_pairs": [list(pair) for pair in self.ligand_bond_pairs],
                "ligand_nonbonded_pairs": [
                    list(pair) for pair in self.ligand_nonbonded_pairs
                ],
            }
        )
        self.score_descriptor = DockingScoreDescriptor(
            score_id="element_flexible_geometry_diagnostic_score",
            direction=ScoreDirection.MINIMIZE,
            unit="dimensionless",
            semantics=(
                "fixed_radius_receptor_ligand_geometry_plus_topology_excluded_"
                "ligand_nonbonded_self_overlap"
            ),
            calibrated=False,
            applicability_domain_id=GEOMETRY_DIAGNOSTIC_RADIUS_PROFILE_SHA256,
        )

    @property
    def receptor_shell_atom_count(self) -> int:
        return self.base_scorer.receptor_shell_atom_count

    @property
    def problem_fingerprint_sha256(self) -> str:
        return self.problem.fingerprint_sha256

    @property
    def chemistry_scope(self) -> dict[str, object]:
        scope = self.base_scorer.chemistry_scope
        scope.update(
            {
                "ligand_self_overlap_evaluated": True,
                "torsion_energy_evaluated": False,
                "bonded_force_field_evaluated": False,
            }
        )
        return scope

    @property
    def blockers(self) -> tuple[str, ...]:
        return FLEXIBLE_GEOMETRY_DIAGNOSTIC_BLOCKERS

    def _ligand_self_overlap(self, coordinates: torch.Tensor) -> float:
        if coordinates.shape != (len(self.ligand_atomic_numbers), 3):
            raise FlexibleGeometryDiagnosticScoringError(
                "ligand coordinates disagree with the flexible scorer topology"
            )
        if not bool(torch.isfinite(coordinates).all().item()):
            raise FlexibleGeometryDiagnosticScoringError(
                "ligand coordinates must be finite"
            )
        if not self._pair_indices.numel():
            return 0.0
        work = coordinates.detach().to(dtype=torch.float64, device="cpu")
        distance = torch.linalg.vector_norm(
            work.index_select(0, self._pair_indices[:, 0])
            - work.index_select(0, self._pair_indices[:, 1]),
            dim=1,
        )
        normalized = torch.clamp(
            (
                self.config.ligand_self_overlap_scale * self._ligand_radius_sums
                - distance
            )
            / self._ligand_radius_sums,
            min=0.0,
        )
        return float(normalized.square().sum().item())

    def score_coordinates(self, coordinates: torch.Tensor) -> DockingScoreBreakdown:
        base = self.base_scorer.score_coordinates(coordinates)
        retained_terms = tuple(
            term
            for term in base.terms
            if term.term_id != "rigid_ligand_internal_strain"
        )
        return DockingScoreBreakdown(
            terms=(
                *retained_terms,
                DockingScoreTerm(
                    term_id="ligand_nonbonded_self_overlap_penalty",
                    raw_value=self._ligand_self_overlap(coordinates),
                    weight=self.config.ligand_self_overlap_weight,
                    unit="dimensionless",
                    semantics=(
                        "squared_normalized_element_radius_overlap_excluding_1_2_1_3"
                    ),
                    parameter_source_sha256=self.parameter_source_sha256,
                ),
                DockingScoreTerm(
                    term_id="ligand_torsion_internal_energy",
                    raw_value=0.0,
                    weight=0.0,
                    unit="dimensionless",
                    semantics="not_evaluated_flexible_geometry_diagnostic_placeholder",
                    parameter_source_sha256="",
                ),
            ),
            blockers=FLEXIBLE_GEOMETRY_DIAGNOSTIC_BLOCKERS,
        )

    def score(self, proposal: DockingProposal) -> DockingScoreBreakdown:
        if not isinstance(proposal, DockingProposal):
            raise FlexibleGeometryDiagnosticScoringError(
                "proposal must be DockingProposal"
            )
        if proposal.problem_fingerprint_sha256 != self.problem.fingerprint_sha256:
            raise FlexibleGeometryDiagnosticScoringError(
                "proposal problem identity does not match the flexible scorer"
            )
        return self.score_coordinates(proposal.coordinates)


__all__ = [
    "FLEXIBLE_GEOMETRY_DIAGNOSTIC_BLOCKERS",
    "FLEXIBLE_GEOMETRY_DIAGNOSTIC_SCORER_SCHEMA_ID",
    "ElementFlexibleGeometryDiagnosticScorer",
    "FlexibleGeometryDiagnosticScoreConfig",
    "FlexibleGeometryDiagnosticScoringError",
]
