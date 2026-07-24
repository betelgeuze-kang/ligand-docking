"""Element-aware, geometry-only diagnostic score for bounded docking probes.

The score is deliberately not a force field.  It uses a fixed implementation
radius table, smooth contact reward, overlap/penetration penalties, and a pocket
centroid restraint.  Formal/partial charge, aromaticity, hydrogen bonding,
stereo, metal coordination, solvation, and fitted ranking weights are absent.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from numbers import Integral, Real
from typing import Sequence

import torch

from betelgeuze_engine_v2.molecular import element_for_atomic_number

from .identity import DockingProblemIdentity, coordinate_fingerprint
from .proposals import DockingProposal
from .scoring import (
    DockingScoreBreakdown,
    DockingScoreDescriptor,
    DockingScoreTerm,
    ScoreDirection,
)


GEOMETRY_DIAGNOSTIC_SCORER_SCHEMA_ID = (
    "betelgeuze.engine_v2_element_geometry_diagnostic_scorer/1.0.0"
)
GEOMETRY_DIAGNOSTIC_RADIUS_PROFILE_ID = (
    "engine_v2_fixed_unvalidated_diagnostic_radii/1.0.0"
)

# Hand-fixed implementation heuristics in angstrom.  They are intentionally not
# labeled as Bondi, force-field, or calibrated docking radii.
GEOMETRY_DIAGNOSTIC_RADII_ANGSTROM = {
    1: 1.20,
    6: 1.70,
    7: 1.55,
    8: 1.52,
    9: 1.47,
    15: 1.80,
    16: 1.80,
    17: 1.75,
    35: 1.85,
    53: 1.98,
}

GEOMETRY_DIAGNOSTIC_BLOCKERS = (
    "geometry_diagnostic_not_force_field_energy",
    "geometry_diagnostic_weights_not_fitted",
    "formal_and_partial_charge_terms_missing",
    "hydrogen_bond_and_directional_interactions_missing",
    "aromatic_specific_interactions_missing",
    "stereo_validity_external_to_scorer",
    "metal_and_cofactor_chemistry_unsupported",
    "ligand_internal_strain_not_evaluated_for_rigid_proposals",
    "public_pose_ranking_validation_missing",
)


class ElementGeometryDiagnosticScoringError(ValueError):
    """Geometry diagnostic inputs exceed the explicit bounded scope."""


def _canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def _finite(
    value: object,
    *,
    name: str,
    positive: bool = False,
    nonnegative: bool = False,
) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ElementGeometryDiagnosticScoringError(f"{name} must be a real number")
    result = float(value)
    if not math.isfinite(result):
        raise ElementGeometryDiagnosticScoringError(f"{name} must be finite")
    if positive and result <= 0.0:
        raise ElementGeometryDiagnosticScoringError(f"{name} must be positive")
    if nonnegative and result < 0.0:
        raise ElementGeometryDiagnosticScoringError(f"{name} must be non-negative")
    return result


def _exact_int(value: object, *, name: str, minimum: int = 1) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise ElementGeometryDiagnosticScoringError(f"{name} must be an integer")
    result = int(value)
    if result < minimum:
        raise ElementGeometryDiagnosticScoringError(
            f"{name} must be at least {minimum}"
        )
    return result


def _coordinates(value: torch.Tensor, *, name: str) -> torch.Tensor:
    if (
        not isinstance(value, torch.Tensor)
        or value.ndim != 2
        or value.shape[1] != 3
        or not value.is_floating_point()
        or not bool(torch.isfinite(value).all().item())
    ):
        raise ElementGeometryDiagnosticScoringError(
            f"{name} must contain finite floating coordinates with shape [N,3]"
        )
    if value.device.type != "cpu" or value.dtype != torch.float64:
        raise ElementGeometryDiagnosticScoringError(
            f"{name} must use CPU float64"
        )
    return value.detach()


def _atomic_numbers(
    values: Sequence[int],
    *,
    name: str,
) -> tuple[int, ...]:
    if isinstance(values, (str, bytes)):
        raise ElementGeometryDiagnosticScoringError(f"{name} must be a sequence")
    result = tuple(_exact_int(value, name=name) for value in values)
    if not result:
        raise ElementGeometryDiagnosticScoringError(f"{name} cannot be empty")
    unsupported = sorted(set(result) - set(GEOMETRY_DIAGNOSTIC_RADII_ANGSTROM))
    if unsupported:
        elements = [element_for_atomic_number(value) or str(value) for value in unsupported]
        raise ElementGeometryDiagnosticScoringError(
            f"{name} contains unsupported elements: {', '.join(elements)}"
        )
    return result


def geometry_diagnostic_radius_profile_document() -> dict[str, object]:
    return {
        "profile_id": GEOMETRY_DIAGNOSTIC_RADIUS_PROFILE_ID,
        "values_angstrom": {
            str(number): GEOMETRY_DIAGNOSTIC_RADII_ANGSTROM[number]
            for number in sorted(GEOMETRY_DIAGNOSTIC_RADII_ANGSTROM)
        },
        "source_kind": "hand_fixed_unvalidated_implementation_heuristic",
        "physical_parameter_claimed": False,
        "calibrated": False,
    }


GEOMETRY_DIAGNOSTIC_RADIUS_PROFILE_SHA256 = _canonical_sha256(
    geometry_diagnostic_radius_profile_document()
)


@dataclass(frozen=True, slots=True)
class ElementGeometryDiagnosticScoreConfig:
    interaction_cutoff_angstrom: float = 8.0
    receptor_shell_radius_angstrom: float = 18.0
    pocket_radius_angstrom: float = 10.0
    contact_width_angstrom: float = 0.75
    overlap_contact_scale: float = 0.82
    deep_penetration_scale: float = 0.58
    contact_weight: float = 1.0
    overlap_weight: float = 25.0
    deep_penetration_weight: float = 100.0
    pocket_centroid_weight: float = 0.25
    max_receptor_shell_atoms: int = 8_192
    max_cross_pairs: int = 500_000

    def __post_init__(self) -> None:
        for name in (
            "interaction_cutoff_angstrom",
            "receptor_shell_radius_angstrom",
            "pocket_radius_angstrom",
            "contact_width_angstrom",
        ):
            object.__setattr__(
                self,
                name,
                _finite(getattr(self, name), name=name, positive=True),
            )
        if self.receptor_shell_radius_angstrom <= self.pocket_radius_angstrom:
            raise ElementGeometryDiagnosticScoringError(
                "receptor shell radius must exceed the pocket radius"
            )
        for name in ("overlap_contact_scale", "deep_penetration_scale"):
            value = _finite(getattr(self, name), name=name, positive=True)
            if value >= 1.0:
                raise ElementGeometryDiagnosticScoringError(
                    f"{name} must be less than one"
                )
            object.__setattr__(self, name, value)
        if self.deep_penetration_scale >= self.overlap_contact_scale:
            raise ElementGeometryDiagnosticScoringError(
                "deep penetration scale must be smaller than overlap scale"
            )
        for name in (
            "contact_weight",
            "overlap_weight",
            "deep_penetration_weight",
            "pocket_centroid_weight",
        ):
            object.__setattr__(
                self,
                name,
                _finite(getattr(self, name), name=name, nonnegative=True),
            )
        object.__setattr__(
            self,
            "max_receptor_shell_atoms",
            _exact_int(
                self.max_receptor_shell_atoms,
                name="max_receptor_shell_atoms",
            ),
        )
        object.__setattr__(
            self,
            "max_cross_pairs",
            _exact_int(self.max_cross_pairs, name="max_cross_pairs"),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": GEOMETRY_DIAGNOSTIC_SCORER_SCHEMA_ID,
            "interaction_cutoff_angstrom": self.interaction_cutoff_angstrom,
            "receptor_shell_radius_angstrom": self.receptor_shell_radius_angstrom,
            "pocket_radius_angstrom": self.pocket_radius_angstrom,
            "contact_width_angstrom": self.contact_width_angstrom,
            "overlap_contact_scale": self.overlap_contact_scale,
            "deep_penetration_scale": self.deep_penetration_scale,
            "contact_weight": self.contact_weight,
            "overlap_weight": self.overlap_weight,
            "deep_penetration_weight": self.deep_penetration_weight,
            "pocket_centroid_weight": self.pocket_centroid_weight,
            "max_receptor_shell_atoms": self.max_receptor_shell_atoms,
            "max_cross_pairs": self.max_cross_pairs,
            "radius_profile_sha256": GEOMETRY_DIAGNOSTIC_RADIUS_PROFILE_SHA256,
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())


class ElementGeometryDiagnosticScorer:
    """Bounded element-radius scorer for rigid public-workflow diagnostics."""

    scorer_id = "element-geometry-diagnostic"
    scorer_version = "1.0.0"
    validated_for_docking_ranking = False

    def __init__(
        self,
        receptor_coordinates: torch.Tensor,
        receptor_atomic_numbers: Sequence[int],
        ligand_atomic_numbers: Sequence[int],
        problem: DockingProblemIdentity,
        *,
        config: ElementGeometryDiagnosticScoreConfig | None = None,
    ) -> None:
        active = ElementGeometryDiagnosticScoreConfig() if config is None else config
        if not isinstance(active, ElementGeometryDiagnosticScoreConfig):
            raise ElementGeometryDiagnosticScoringError(
                "config must be ElementGeometryDiagnosticScoreConfig"
            )
        if not isinstance(problem, DockingProblemIdentity) or not problem.bound:
            raise ElementGeometryDiagnosticScoringError(
                "a bound docking problem identity is required"
            )
        receptor = _coordinates(
            receptor_coordinates,
            name="receptor_coordinates",
        )
        receptor_numbers = _atomic_numbers(
            receptor_atomic_numbers,
            name="receptor_atomic_numbers",
        )
        ligand_numbers = _atomic_numbers(
            ligand_atomic_numbers,
            name="ligand_atomic_numbers",
        )
        if len(receptor_numbers) != int(receptor.shape[0]):
            raise ElementGeometryDiagnosticScoringError(
                "receptor atom identities and coordinates disagree"
            )
        shell_mask = torch.linalg.vector_norm(receptor, dim=1) <= (
            active.receptor_shell_radius_angstrom
        )
        shell_indices = torch.nonzero(shell_mask, as_tuple=False).reshape(-1)
        shell_count = int(shell_indices.numel())
        if shell_count < 1:
            raise ElementGeometryDiagnosticScoringError(
                "receptor shell contains no supported atoms"
            )
        if shell_count > active.max_receptor_shell_atoms:
            raise ElementGeometryDiagnosticScoringError(
                "receptor shell exceeds the atom capacity"
            )
        if shell_count * len(ligand_numbers) > active.max_cross_pairs:
            raise ElementGeometryDiagnosticScoringError(
                "receptor-ligand shell pair capacity exceeded"
            )
        shell_number_values = tuple(
            receptor_numbers[int(index)] for index in shell_indices.tolist()
        )
        self.config = active
        self.problem = problem
        self.receptor_coordinates = receptor.index_select(0, shell_indices)
        self.receptor_atomic_numbers = shell_number_values
        self.ligand_atomic_numbers = ligand_numbers
        self.receptor_radii = torch.tensor(
            [GEOMETRY_DIAGNOSTIC_RADII_ANGSTROM[value] for value in shell_number_values],
            dtype=torch.float64,
        )
        self.ligand_radii = torch.tensor(
            [GEOMETRY_DIAGNOSTIC_RADII_ANGSTROM[value] for value in ligand_numbers],
            dtype=torch.float64,
        )
        self.parameter_source_sha256 = GEOMETRY_DIAGNOSTIC_RADIUS_PROFILE_SHA256
        self.config_fingerprint_sha256 = _canonical_sha256(
            {
                "schema_id": GEOMETRY_DIAGNOSTIC_SCORER_SCHEMA_ID,
                "config_sha256": active.fingerprint_sha256,
                "problem_sha256": problem.fingerprint_sha256,
                "receptor_shell_coordinate_sha256": coordinate_fingerprint(
                    self.receptor_coordinates
                ),
                "receptor_shell_atomic_numbers": list(shell_number_values),
                "ligand_atomic_numbers": list(ligand_numbers),
            }
        )
        self.score_descriptor = DockingScoreDescriptor(
            score_id="element_geometry_diagnostic_score",
            direction=ScoreDirection.MINIMIZE,
            unit="dimensionless",
            semantics=(
                "fixed_radius_contact_reward_plus_overlap_penetration_and_"
                "pocket_centroid_penalties"
            ),
            calibrated=False,
            applicability_domain_id=self.parameter_source_sha256,
        )

    @property
    def receptor_shell_atom_count(self) -> int:
        return int(self.receptor_coordinates.shape[0])

    @property
    def problem_fingerprint_sha256(self) -> str:
        return self.problem.fingerprint_sha256

    @property
    def blockers(self) -> tuple[str, ...]:
        return GEOMETRY_DIAGNOSTIC_BLOCKERS

    @property
    def chemistry_scope(self) -> dict[str, object]:
        return {
            "supported_atomic_numbers": sorted(GEOMETRY_DIAGNOSTIC_RADII_ANGSTROM),
            "supported_elements": [
                element_for_atomic_number(value)
                for value in sorted(GEOMETRY_DIAGNOSTIC_RADII_ANGSTROM)
            ],
            "formal_charge_used": False,
            "partial_charge_used": False,
            "aromaticity_used": False,
            "stereo_used": False,
            "metal_coordination_supported": False,
            "cofactor_chemistry_supported": False,
        }

    def _raw_terms(self, coordinates: torch.Tensor) -> tuple[float, float, float, float]:
        ligand = _coordinates(coordinates, name="ligand_coordinates")
        if int(ligand.shape[0]) != len(self.ligand_atomic_numbers):
            raise ElementGeometryDiagnosticScoringError(
                "ligand atom identities and coordinates disagree"
            )
        delta = self.receptor_coordinates[:, None, :] - ligand[None, :, :]
        distance = torch.linalg.vector_norm(delta, dim=-1)
        radius_sum = self.receptor_radii[:, None] + self.ligand_radii[None, :]
        selected = distance <= self.config.interaction_cutoff_angstrom
        contact = torch.where(
            selected,
            torch.exp(
                -0.5
                * ((distance - radius_sum) / self.config.contact_width_angstrom).square()
            ),
            torch.zeros_like(distance),
        ).sum()
        normalized_overlap = torch.clamp(
            (self.config.overlap_contact_scale * radius_sum - distance) / radius_sum,
            min=0.0,
        )
        overlap = normalized_overlap.square().sum()
        normalized_penetration = torch.clamp(
            (self.config.deep_penetration_scale * radius_sum - distance) / radius_sum,
            min=0.0,
        )
        penetration = normalized_penetration.square().sum()
        centroid_distance = torch.linalg.vector_norm(ligand.mean(dim=0))
        centroid_penalty = (
            centroid_distance / self.config.pocket_radius_angstrom
        ).square()
        return (
            -float(contact.item()),
            float(overlap.item()),
            float(penetration.item()),
            float(centroid_penalty.item()),
        )

    def score_coordinates(self, coordinates: torch.Tensor) -> DockingScoreBreakdown:
        contact, overlap, penetration, centroid = self._raw_terms(coordinates)
        return DockingScoreBreakdown(
            terms=(
                DockingScoreTerm(
                    term_id="element_radius_contact_reward",
                    raw_value=contact,
                    weight=self.config.contact_weight,
                    unit="dimensionless",
                    semantics=(
                        "negative_gaussian_contact_count_around_fixed_radius_sum"
                    ),
                    parameter_source_sha256=self.parameter_source_sha256,
                ),
                DockingScoreTerm(
                    term_id="element_radius_overlap_penalty",
                    raw_value=overlap,
                    weight=self.config.overlap_weight,
                    unit="dimensionless",
                    semantics="squared_normalized_overlap_below_fixed_contact_scale",
                    parameter_source_sha256=self.parameter_source_sha256,
                ),
                DockingScoreTerm(
                    term_id="element_radius_deep_penetration_penalty",
                    raw_value=penetration,
                    weight=self.config.deep_penetration_weight,
                    unit="dimensionless",
                    semantics="squared_normalized_deep_interpenetration",
                    parameter_source_sha256=self.parameter_source_sha256,
                ),
                DockingScoreTerm(
                    term_id="pocket_centroid_restraint",
                    raw_value=centroid,
                    weight=self.config.pocket_centroid_weight,
                    unit="dimensionless",
                    semantics="squared_ligand_centroid_distance_over_pocket_radius",
                    parameter_source_sha256=self.config.fingerprint_sha256,
                ),
                DockingScoreTerm(
                    term_id="rigid_ligand_internal_strain",
                    raw_value=0.0,
                    weight=0.0,
                    unit="dimensionless",
                    semantics="not_evaluated_rigid_body_diagnostic_placeholder",
                    parameter_source_sha256="",
                ),
            ),
            blockers=GEOMETRY_DIAGNOSTIC_BLOCKERS,
        )

    def score(self, proposal: DockingProposal) -> DockingScoreBreakdown:
        if not isinstance(proposal, DockingProposal):
            raise ElementGeometryDiagnosticScoringError(
                "proposal must be DockingProposal"
            )
        if proposal.problem_fingerprint_sha256 != self.problem.fingerprint_sha256:
            raise ElementGeometryDiagnosticScoringError(
                "proposal problem identity does not match the scorer"
            )
        return self.score_coordinates(proposal.coordinates)


__all__ = [
    "GEOMETRY_DIAGNOSTIC_BLOCKERS",
    "GEOMETRY_DIAGNOSTIC_RADII_ANGSTROM",
    "GEOMETRY_DIAGNOSTIC_RADIUS_PROFILE_ID",
    "GEOMETRY_DIAGNOSTIC_RADIUS_PROFILE_SHA256",
    "GEOMETRY_DIAGNOSTIC_SCORER_SCHEMA_ID",
    "ElementGeometryDiagnosticScoreConfig",
    "ElementGeometryDiagnosticScorer",
    "ElementGeometryDiagnosticScoringError",
    "geometry_diagnostic_radius_profile_document",
]
