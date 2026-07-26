"""Interpretable, uncalibrated pose scorer v0 for canonical molecular inputs.

The scorer composes the existing element-geometry diagnostic with five
independently inspectable terms: reference-relative bond and angle strain,
reference-relative rotatable-bond torsion displacement, directional
``D-H...A`` hydrogen bonds, and hydrophobic contacts.  Chemistry features are
derived deterministically from explicit canonical topology.  The rules and
weights are implementation heuristics, not a force field or calibrated
docking model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
from numbers import Integral, Real
from typing import Mapping

import torch

from betelgeuze_engine_v2.molecular import (
    AllAtomSystem,
    Bond,
    canonical_system_sha256,
    require_valid_all_atom_system,
)

from .geometric_scoring import (
    GEOMETRY_DIAGNOSTIC_RADII_ANGSTROM,
    ElementGeometryDiagnosticScoreConfig,
    ElementGeometryDiagnosticScorer,
)
from .identity import DockingProblemIdentity, coordinate_fingerprint
from .proposals import DockingProposal
from .scoring import (
    DockingScoreBreakdown,
    DockingScoreDescriptor,
    DockingScoreTerm,
    ScoreDirection,
)


INTERPRETABLE_POSE_SCORER_V0_SCHEMA_ID = (
    "betelgeuze.engine_v2_interpretable_pose_scorer_v0/1.0.0"
)
INTERPRETABLE_POSE_FEATURE_RECEIPT_SCHEMA_ID = (
    "betelgeuze.engine_v2_interpretable_pose_features/1.0.0"
)
INTERPRETABLE_POSE_DIAGNOSTICS_SCHEMA_ID = (
    "betelgeuze.engine_v2_interpretable_pose_score_diagnostics/1.0.0"
)
INTERPRETABLE_POSE_FEATURE_PROFILE_ID = (
    "engine_v2_topology_heuristic_pose_features/1.0.0"
)
INTERPRETABLE_POSE_SUPPORTED_ATOMIC_NUMBERS = tuple(
    sorted(GEOMETRY_DIAGNOSTIC_RADII_ANGSTROM)
)
INTERPRETABLE_POSE_SCORER_V0_BLOCKERS = (
    "interpretable_pose_scorer_v0_uncalibrated",
    "element_geometry_component_not_force_field_energy",
    "scoring_weights_not_fitted",
    "chemistry_feature_rules_heuristic_not_independently_validated",
    "directional_hbond_acceptor_lone_pair_geometry_not_modeled",
    "hydrophobic_element_rules_not_fitted",
    "torsion_displacement_reference_relative_not_force_field_energy",
    "partial_charge_electrostatics_and_solvation_missing",
    "aromatic_pi_cation_pi_and_halogen_bond_terms_missing",
    "metal_coordination_and_covalent_ligands_unsupported",
    "public_pose_ranking_validation_missing",
    "independent_scientific_review_missing",
)


class InterpretablePoseScoringError(ValueError):
    """Canonical systems or score inputs exceed the bounded v0 contract."""


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
        raise InterpretablePoseScoringError(
            "interpretable score value is not canonical JSON"
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
        raise InterpretablePoseScoringError(f"{name} must be a real number")
    result = float(value)
    if not math.isfinite(result):
        raise InterpretablePoseScoringError(f"{name} must be finite")
    if positive and result <= 0.0:
        raise InterpretablePoseScoringError(f"{name} must be positive")
    if nonnegative and result < 0.0:
        raise InterpretablePoseScoringError(f"{name} must be non-negative")
    return result


def _exact_int(
    value: object,
    *,
    name: str,
    minimum: int = 0,
    maximum: int | None = None,
) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise InterpretablePoseScoringError(f"{name} must be an integer")
    result = int(value)
    if result < minimum or (maximum is not None and result > maximum):
        raise InterpretablePoseScoringError(f"{name} is outside its integer bound")
    return result


def _digest(value: object, *, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise InterpretablePoseScoringError(f"{name} must be a lowercase SHA-256")
    return value


def _coordinates(
    value: torch.Tensor,
    *,
    name: str,
    atom_count: int,
) -> torch.Tensor:
    if (
        not isinstance(value, torch.Tensor)
        or value.shape != (atom_count, 3)
        or value.dtype != torch.float64
        or value.device.type != "cpu"
        or not bool(torch.isfinite(value).all().item())
    ):
        raise InterpretablePoseScoringError(
            f"{name} must be CPU float64 with shape [{atom_count},3]"
        )
    return value.detach()


def interpretable_pose_feature_profile_document() -> dict[str, object]:
    return {
        "profile_id": INTERPRETABLE_POSE_FEATURE_PROFILE_ID,
        "supported_atomic_numbers": list(INTERPRETABLE_POSE_SUPPORTED_ATOMIC_NUMBERS),
        "donor_rule": (
            "explicit_H_bonded_to_neutral_or_positive_N_O_S_with_"
            "valence_based_missing_H_diagnostic"
        ),
        "acceptor_rule": (
            "nonpositive_unprotonated_O_or_S_or_nonpositive_nonamide_N_"
            "excluding_aromatic_N_H"
        ),
        "hydrophobic_rule": "neutral_C_S_or_F_Cl_Br_I",
        "rotatable_rule": (
            "nonring_nonaromatic_single_heavy_bond_with_heavy_neighbor_on_both_sides_"
            "excluding_amide_CN"
        ),
        "ring_membership_source": (
            "required_boolean_canonical_bond_metadata_is_in_ring"
        ),
        "hbond_geometry": "D_H_A_angle_and_H_A_D_A_distance",
        "acceptor_lone_pair_geometry_modeled": False,
        "physical_parameter_claimed": False,
        "calibrated": False,
    }


INTERPRETABLE_POSE_FEATURE_PROFILE_SHA256 = _canonical_sha256(
    interpretable_pose_feature_profile_document()
)


@dataclass(frozen=True, slots=True)
class InterpretablePoseScoreConfig:
    """Frozen v0 weights, geometry, and capacity policy."""

    base_geometry: ElementGeometryDiagnosticScoreConfig = field(
        default_factory=ElementGeometryDiagnosticScoreConfig
    )
    bond_strain_scale_angstrom: float = 0.10
    angle_strain_scale_radians: float = 0.35
    bond_strain_weight: float = 0.50
    angle_strain_weight: float = 0.25
    torsion_displacement_weight: float = 0.50
    hbond_h_a_center_angstrom: float = 1.90
    hbond_h_a_width_angstrom: float = 0.35
    hbond_h_a_minimum_angstrom: float = 1.20
    hbond_h_a_cutoff_angstrom: float = 2.80
    hbond_d_a_cutoff_angstrom: float = 3.60
    hbond_minimum_angle_degrees: float = 120.0
    hbond_weight: float = 2.00
    hydrophobic_contact_offset_angstrom: float = 0.25
    hydrophobic_contact_width_angstrom: float = 0.75
    hydrophobic_contact_cutoff_angstrom: float = 6.0
    hydrophobic_minimum_contact_scale: float = 0.82
    hydrophobic_weight: float = 0.50
    active_feature_threshold: float = 0.10
    max_bonds: int = 8_192
    max_angles: int = 32_768
    max_rotatable_bonds: int = 64
    max_hbond_pairs: int = 200_000
    max_hydrophobic_pairs: int = 500_000

    def __post_init__(self) -> None:
        if not isinstance(self.base_geometry, ElementGeometryDiagnosticScoreConfig):
            raise InterpretablePoseScoringError(
                "base_geometry must be ElementGeometryDiagnosticScoreConfig"
            )
        for name in (
            "bond_strain_scale_angstrom",
            "angle_strain_scale_radians",
            "hbond_h_a_center_angstrom",
            "hbond_h_a_width_angstrom",
            "hbond_h_a_minimum_angstrom",
            "hbond_h_a_cutoff_angstrom",
            "hbond_d_a_cutoff_angstrom",
            "hydrophobic_contact_width_angstrom",
            "hydrophobic_contact_cutoff_angstrom",
        ):
            object.__setattr__(
                self,
                name,
                _finite(getattr(self, name), name=name, positive=True),
            )
        if self.hbond_h_a_minimum_angstrom >= self.hbond_h_a_cutoff_angstrom:
            raise InterpretablePoseScoringError(
                "hbond H-A minimum must be less than its cutoff"
            )
        if not (
            self.hbond_h_a_minimum_angstrom
            <= self.hbond_h_a_center_angstrom
            <= self.hbond_h_a_cutoff_angstrom
        ):
            raise InterpretablePoseScoringError(
                "hbond H-A center must be inside the admitted distance interval"
            )
        object.__setattr__(
            self,
            "hbond_minimum_angle_degrees",
            _finite(
                self.hbond_minimum_angle_degrees,
                name="hbond_minimum_angle_degrees",
                positive=True,
            ),
        )
        if not 90.0 <= self.hbond_minimum_angle_degrees < 180.0:
            raise InterpretablePoseScoringError(
                "hbond minimum angle must be in [90,180) degrees"
            )
        for name in (
            "bond_strain_weight",
            "angle_strain_weight",
            "torsion_displacement_weight",
            "hbond_weight",
            "hydrophobic_contact_offset_angstrom",
            "hydrophobic_weight",
            "active_feature_threshold",
        ):
            object.__setattr__(
                self,
                name,
                _finite(getattr(self, name), name=name, nonnegative=True),
            )
        scale = _finite(
            self.hydrophobic_minimum_contact_scale,
            name="hydrophobic_minimum_contact_scale",
            positive=True,
        )
        if scale >= 1.0:
            raise InterpretablePoseScoringError(
                "hydrophobic minimum contact scale must be less than one"
            )
        object.__setattr__(self, "hydrophobic_minimum_contact_scale", scale)
        if self.active_feature_threshold > 1.0:
            raise InterpretablePoseScoringError(
                "active feature threshold must not exceed one"
            )
        for name, maximum in (
            ("max_bonds", 100_000),
            ("max_angles", 500_000),
            ("max_rotatable_bonds", 256),
            ("max_hbond_pairs", 1_000_000),
            ("max_hydrophobic_pairs", 1_000_000),
        ):
            object.__setattr__(
                self,
                name,
                _exact_int(
                    getattr(self, name),
                    name=name,
                    minimum=1,
                    maximum=maximum,
                ),
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": INTERPRETABLE_POSE_SCORER_V0_SCHEMA_ID,
            "base_geometry": self.base_geometry.to_dict(),
            "bond_strain_scale_angstrom": self.bond_strain_scale_angstrom,
            "angle_strain_scale_radians": self.angle_strain_scale_radians,
            "bond_strain_weight": self.bond_strain_weight,
            "angle_strain_weight": self.angle_strain_weight,
            "torsion_displacement_weight": self.torsion_displacement_weight,
            "hbond_h_a_center_angstrom": self.hbond_h_a_center_angstrom,
            "hbond_h_a_width_angstrom": self.hbond_h_a_width_angstrom,
            "hbond_h_a_minimum_angstrom": self.hbond_h_a_minimum_angstrom,
            "hbond_h_a_cutoff_angstrom": self.hbond_h_a_cutoff_angstrom,
            "hbond_d_a_cutoff_angstrom": self.hbond_d_a_cutoff_angstrom,
            "hbond_minimum_angle_degrees": self.hbond_minimum_angle_degrees,
            "hbond_weight": self.hbond_weight,
            "hydrophobic_contact_offset_angstrom": (
                self.hydrophobic_contact_offset_angstrom
            ),
            "hydrophobic_contact_width_angstrom": (
                self.hydrophobic_contact_width_angstrom
            ),
            "hydrophobic_contact_cutoff_angstrom": (
                self.hydrophobic_contact_cutoff_angstrom
            ),
            "hydrophobic_minimum_contact_scale": (
                self.hydrophobic_minimum_contact_scale
            ),
            "hydrophobic_weight": self.hydrophobic_weight,
            "active_feature_threshold": self.active_feature_threshold,
            "max_bonds": self.max_bonds,
            "max_angles": self.max_angles,
            "max_rotatable_bonds": self.max_rotatable_bonds,
            "max_hbond_pairs": self.max_hbond_pairs,
            "max_hydrophobic_pairs": self.max_hydrophobic_pairs,
            "feature_profile_sha256": INTERPRETABLE_POSE_FEATURE_PROFILE_SHA256,
            "score_direction": "minimize",
            "calibrated": False,
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())


@dataclass(frozen=True, slots=True)
class InterpretablePoseFeatureReceipt:
    role: str
    system_sha256: str
    donor_hydrogen_pairs: tuple[tuple[int, int], ...]
    acceptor_atom_indices: tuple[int, ...]
    hydrophobic_atom_indices: tuple[int, ...]
    aromatic_atom_indices: tuple[int, ...]
    declared_stereo_atom_indices: tuple[int, ...]
    declared_stereo_bond_indices: tuple[int, ...]
    potential_donor_atom_count: int
    donor_direction_missing_atom_count: int
    schema_id: str = INTERPRETABLE_POSE_FEATURE_RECEIPT_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != INTERPRETABLE_POSE_FEATURE_RECEIPT_SCHEMA_ID:
            raise InterpretablePoseScoringError("unsupported feature receipt schema")
        if self.role not in {"receptor", "ligand"}:
            raise InterpretablePoseScoringError(
                "feature role must be receptor or ligand"
            )
        object.__setattr__(
            self,
            "system_sha256",
            _digest(self.system_sha256, name="feature system SHA-256"),
        )
        for name in (
            "acceptor_atom_indices",
            "hydrophobic_atom_indices",
            "aromatic_atom_indices",
            "declared_stereo_atom_indices",
            "declared_stereo_bond_indices",
        ):
            values = tuple(int(value) for value in getattr(self, name))
            if values != tuple(sorted(set(values))) or any(
                value < 0 for value in values
            ):
                raise InterpretablePoseScoringError(
                    f"{name} must be unique sorted non-negative indices"
                )
            object.__setattr__(self, name, values)
        donor_pairs = tuple(
            (int(first), int(second)) for first, second in self.donor_hydrogen_pairs
        )
        if donor_pairs != tuple(sorted(set(donor_pairs))) or any(
            first < 0 or second < 0 or first == second for first, second in donor_pairs
        ):
            raise InterpretablePoseScoringError(
                "donor hydrogen pairs must be unique sorted non-self indices"
            )
        object.__setattr__(self, "donor_hydrogen_pairs", donor_pairs)
        for name in (
            "potential_donor_atom_count",
            "donor_direction_missing_atom_count",
        ):
            object.__setattr__(
                self,
                name,
                _exact_int(getattr(self, name), name=name),
            )
        if self.donor_direction_missing_atom_count > self.potential_donor_atom_count:
            raise InterpretablePoseScoringError(
                "missing donor directions exceed potential donors"
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "role": self.role,
            "system_sha256": self.system_sha256,
            "feature_profile_sha256": INTERPRETABLE_POSE_FEATURE_PROFILE_SHA256,
            "donor_hydrogen_pairs": [list(pair) for pair in self.donor_hydrogen_pairs],
            "acceptor_atom_indices": list(self.acceptor_atom_indices),
            "hydrophobic_atom_indices": list(self.hydrophobic_atom_indices),
            "aromatic_atom_indices": list(self.aromatic_atom_indices),
            "declared_stereo_atom_indices": list(self.declared_stereo_atom_indices),
            "declared_stereo_bond_indices": list(self.declared_stereo_bond_indices),
            "potential_donor_atom_count": self.potential_donor_atom_count,
            "donor_direction_missing_atom_count": (
                self.donor_direction_missing_atom_count
            ),
            "partial_charge_used": False,
            "scientifically_validated": False,
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())


@dataclass(frozen=True, slots=True)
class InterpretableHydrogenBondObservation:
    """One directional interaction with molecule-local atom indices."""

    direction: str
    donor_atom_index: int
    hydrogen_atom_index: int
    acceptor_atom_index: int
    h_a_distance_angstrom: float
    d_a_distance_angstrom: float
    d_h_a_angle_degrees: float
    feature_value: float

    def __post_init__(self) -> None:
        if self.direction not in {
            "ligand_donor_to_receptor_acceptor",
            "receptor_donor_to_ligand_acceptor",
        }:
            raise InterpretablePoseScoringError("unsupported hydrogen-bond direction")
        for name in (
            "donor_atom_index",
            "hydrogen_atom_index",
            "acceptor_atom_index",
        ):
            object.__setattr__(
                self,
                name,
                _exact_int(getattr(self, name), name=name),
            )
        if self.donor_atom_index == self.hydrogen_atom_index:
            raise InterpretablePoseScoringError(
                "hydrogen-bond donor and hydrogen indices must be distinct"
            )
        for name in (
            "h_a_distance_angstrom",
            "d_a_distance_angstrom",
            "d_h_a_angle_degrees",
            "feature_value",
        ):
            object.__setattr__(
                self,
                name,
                _finite(getattr(self, name), name=name, nonnegative=True),
            )
        if self.d_h_a_angle_degrees > 180.0:
            raise InterpretablePoseScoringError(
                "hydrogen-bond angle must not exceed 180 degrees"
            )
        if self.feature_value > 1.0:
            raise InterpretablePoseScoringError(
                "hydrogen-bond feature must not exceed one"
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "direction": self.direction,
            "donor_atom_index": self.donor_atom_index,
            "hydrogen_atom_index": self.hydrogen_atom_index,
            "acceptor_atom_index": self.acceptor_atom_index,
            "h_a_distance_angstrom": self.h_a_distance_angstrom,
            "d_a_distance_angstrom": self.d_a_distance_angstrom,
            "d_h_a_angle_degrees": self.d_h_a_angle_degrees,
            "feature_value": self.feature_value,
        }


@dataclass(frozen=True, slots=True)
class InterpretablePoseScoreDiagnostics:
    candidate_id: str
    coordinate_sha256: str
    scorer_fingerprint_sha256: str
    feature_binding_sha256: str
    bond_count: int
    angle_count: int
    rotatable_bond_count: int
    hbond_candidate_count: int
    hbond_active_count: int
    hydrophobic_pair_count: int
    hydrophobic_active_count: int
    term_raw_values: tuple[tuple[str, float], ...]
    strongest_hbond: InterpretableHydrogenBondObservation | None
    schema_id: str = INTERPRETABLE_POSE_DIAGNOSTICS_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != INTERPRETABLE_POSE_DIAGNOSTICS_SCHEMA_ID:
            raise InterpretablePoseScoringError("unsupported score diagnostics schema")
        if not str(self.candidate_id or "").strip():
            raise InterpretablePoseScoringError("diagnostic candidate_id is empty")
        for name in (
            "coordinate_sha256",
            "scorer_fingerprint_sha256",
            "feature_binding_sha256",
        ):
            object.__setattr__(self, name, _digest(getattr(self, name), name=name))
        for name in (
            "bond_count",
            "angle_count",
            "rotatable_bond_count",
            "hbond_candidate_count",
            "hbond_active_count",
            "hydrophobic_pair_count",
            "hydrophobic_active_count",
        ):
            object.__setattr__(
                self,
                name,
                _exact_int(getattr(self, name), name=name),
            )
        if self.hbond_active_count > self.hbond_candidate_count:
            raise InterpretablePoseScoringError("active H-bonds exceed candidates")
        if self.hydrophobic_active_count > self.hydrophobic_pair_count:
            raise InterpretablePoseScoringError(
                "active hydrophobic contacts exceed candidates"
            )
        rows = tuple(
            (str(name), _finite(value, name=str(name)))
            for name, value in self.term_raw_values
        )
        if not rows or len({name for name, _value in rows}) != len(rows):
            raise InterpretablePoseScoringError(
                "diagnostic term rows must be non-empty and unique"
            )
        object.__setattr__(self, "term_raw_values", rows)
        if self.strongest_hbond is not None and not isinstance(
            self.strongest_hbond,
            InterpretableHydrogenBondObservation,
        ):
            raise InterpretablePoseScoringError(
                "strongest_hbond must be a hydrogen-bond observation"
            )

    def to_dict(self) -> dict[str, object]:
        payload = {
            "schema_id": self.schema_id,
            "candidate_id": self.candidate_id,
            "coordinate_sha256": self.coordinate_sha256,
            "scorer_fingerprint_sha256": self.scorer_fingerprint_sha256,
            "feature_binding_sha256": self.feature_binding_sha256,
            "bond_count": self.bond_count,
            "angle_count": self.angle_count,
            "rotatable_bond_count": self.rotatable_bond_count,
            "hbond_candidate_count": self.hbond_candidate_count,
            "hbond_active_count": self.hbond_active_count,
            "hydrophobic_pair_count": self.hydrophobic_pair_count,
            "hydrophobic_active_count": self.hydrophobic_active_count,
            "term_raw_values": {name: value for name, value in self.term_raw_values},
            "strongest_hbond": (
                None if self.strongest_hbond is None else self.strongest_hbond.to_dict()
            ),
            "claim_safe": False,
            "scientifically_validated": False,
        }
        payload["diagnostics_sha256"] = _canonical_sha256(payload)
        return payload

    @property
    def fingerprint_sha256(self) -> str:
        return str(self.to_dict()["diagnostics_sha256"])


def _adjacency(system: AllAtomSystem) -> tuple[tuple[int, ...], ...]:
    rows: list[set[int]] = [set() for _ in range(system.atom_count)]
    for bond in system.bonds:
        rows[bond.atom_i].add(bond.atom_j)
        rows[bond.atom_j].add(bond.atom_i)
    return tuple(tuple(sorted(row)) for row in rows)


def _bond_by_pair(system: AllAtomSystem) -> dict[tuple[int, int], Bond]:
    return {(bond.atom_i, bond.atom_j): bond for bond in system.bonds}


def _is_carbonyl_carbon(
    atom_index: int,
    system: AllAtomSystem,
    adjacency: tuple[tuple[int, ...], ...],
    bonds: Mapping[tuple[int, int], Bond],
) -> bool:
    atom = system.atoms[atom_index]
    if atom.atomic_number != 6:
        return False
    for neighbor in adjacency[atom_index]:
        neighbor_atom = system.atoms[neighbor]
        pair = (min(atom_index, neighbor), max(atom_index, neighbor))
        bond = bonds[pair]
        if neighbor_atom.atomic_number in {7, 8, 16} and math.isclose(
            bond.order, 2.0, abs_tol=1.0e-6
        ):
            return True
    return False


def _is_amide_nitrogen(
    atom_index: int,
    system: AllAtomSystem,
    adjacency: tuple[tuple[int, ...], ...],
    bonds: Mapping[tuple[int, int], Bond],
) -> bool:
    atom = system.atoms[atom_index]
    if atom.atomic_number != 7:
        return False
    return any(
        _is_carbonyl_carbon(neighbor, system, adjacency, bonds)
        for neighbor in adjacency[atom_index]
    )


def _could_be_hbond_donor(
    atom_index: int,
    system: AllAtomSystem,
    adjacency: tuple[tuple[int, ...], ...],
    bonds: Mapping[tuple[int, int], Bond],
) -> bool:
    atom = system.atoms[atom_index]
    if atom.atomic_number not in {7, 8, 16} or atom.formal_charge not in {0, 1}:
        return False
    if any(
        system.atoms[neighbor].atomic_number == 1 for neighbor in adjacency[atom_index]
    ):
        return True
    bond_order_sum = sum(
        bonds[(min(atom_index, neighbor), max(atom_index, neighbor))].order
        for neighbor in adjacency[atom_index]
    )
    target_valence = 4.0 if atom.atomic_number == 7 and atom.formal_charge == 1 else 3.0
    if atom.atomic_number in {8, 16}:
        target_valence = 3.0 if atom.formal_charge == 1 else 2.0
    return bond_order_sum < target_valence - 1.0e-6


def _feature_receipt(
    system: AllAtomSystem,
    *,
    role: str,
    allowed_atom_indices: frozenset[int] | None = None,
) -> InterpretablePoseFeatureReceipt:
    adjacency = _adjacency(system)
    bonds = _bond_by_pair(system)
    allowed = (
        frozenset(range(system.atom_count))
        if allowed_atom_indices is None
        else allowed_atom_indices
    )
    donor_pairs: list[tuple[int, int]] = []
    acceptors: list[int] = []
    hydrophobic: list[int] = []
    potential_donors = 0
    missing_directions = 0
    for atom in system.atoms:
        if atom.index not in allowed:
            continue
        neighbor_indices = adjacency[atom.index]
        hydrogens = tuple(
            neighbor
            for neighbor in neighbor_indices
            if neighbor in allowed and system.atoms[neighbor].atomic_number == 1
        )
        if _could_be_hbond_donor(atom.index, system, adjacency, bonds):
            potential_donors += 1
            if hydrogens:
                donor_pairs.extend((atom.index, hydrogen) for hydrogen in hydrogens)
            else:
                missing_directions += 1
        aromatic_hydrogenated_nitrogen = bool(
            atom.atomic_number == 7 and atom.aromatic and hydrogens
        )
        acceptor = False
        if (
            atom.atomic_number in {8, 16}
            and atom.formal_charge <= 0
            and (not hydrogens or atom.formal_charge < 0)
        ):
            acceptor = True
        elif (
            atom.atomic_number == 7
            and atom.formal_charge <= 0
            and not aromatic_hydrogenated_nitrogen
            and not _is_amide_nitrogen(atom.index, system, adjacency, bonds)
        ):
            acceptor = True
        if acceptor:
            acceptors.append(atom.index)
        if atom.formal_charge == 0 and atom.atomic_number in {6, 9, 16, 17, 35, 53}:
            hydrophobic.append(atom.index)
    declared_atom_stereo = tuple(
        atom.index
        for atom in system.atoms
        if atom.index in allowed and str(atom.stereo).strip().upper() in {"R", "S"}
    )
    declared_bond_stereo = tuple(
        bond.index
        for bond in system.bonds
        if bond.atom_i in allowed
        and bond.atom_j in allowed
        and str(bond.stereo).strip().upper() in {"E", "Z", "CIS", "TRANS"}
    )
    return InterpretablePoseFeatureReceipt(
        role=role,
        system_sha256=canonical_system_sha256(system),
        donor_hydrogen_pairs=tuple(sorted(donor_pairs)),
        acceptor_atom_indices=tuple(sorted(acceptors)),
        hydrophobic_atom_indices=tuple(sorted(hydrophobic)),
        aromatic_atom_indices=tuple(
            atom.index
            for atom in system.atoms
            if atom.index in allowed and atom.aromatic
        ),
        declared_stereo_atom_indices=declared_atom_stereo,
        declared_stereo_bond_indices=declared_bond_stereo,
        potential_donor_atom_count=potential_donors,
        donor_direction_missing_atom_count=missing_directions,
    )


def _angle_triplets(
    adjacency: tuple[tuple[int, ...], ...],
) -> tuple[tuple[int, int, int], ...]:
    rows: list[tuple[int, int, int]] = []
    for center, neighbors in enumerate(adjacency):
        for first_position, first in enumerate(neighbors):
            for second in neighbors[first_position + 1 :]:
                rows.append((first, center, second))
    return tuple(rows)


def _rotatable_torsions(
    system: AllAtomSystem,
    adjacency: tuple[tuple[int, ...], ...],
) -> tuple[tuple[int, int, int, int], ...]:
    bonds = _bond_by_pair(system)
    rows: list[tuple[int, int, int, int]] = []
    for bond in system.bonds:
        if (
            bond.aromatic
            or not math.isclose(float(bond.order), 1.0, abs_tol=1.0e-6)
            or bool(bond.metadata.get("is_in_ring", False))
        ):
            continue
        first = bond.atom_i
        second = bond.atom_j
        if (
            system.atoms[first].atomic_number == 1
            or system.atoms[second].atomic_number == 1
        ):
            continue
        if (
            _is_amide_nitrogen(first, system, adjacency, bonds)
            and _is_carbonyl_carbon(second, system, adjacency, bonds)
        ) or (
            _is_amide_nitrogen(second, system, adjacency, bonds)
            and _is_carbonyl_carbon(first, system, adjacency, bonds)
        ):
            continue
        first_neighbors = tuple(
            index
            for index in adjacency[first]
            if index != second and system.atoms[index].atomic_number != 1
        )
        second_neighbors = tuple(
            index
            for index in adjacency[second]
            if index != first and system.atoms[index].atomic_number != 1
        )
        if not first_neighbors or not second_neighbors:
            continue
        rows.append((min(first_neighbors), first, second, min(second_neighbors)))
    return tuple(rows)


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
    first_norm = torch.linalg.vector_norm(first_vector, dim=1)
    second_norm = torch.linalg.vector_norm(second_vector, dim=1)
    if bool((first_norm <= 1.0e-12).any().item()) or bool(
        (second_norm <= 1.0e-12).any().item()
    ):
        raise InterpretablePoseScoringError("angle contains a collapsed bond")
    cosine = torch.sum(first_vector * second_vector, dim=1) / (first_norm * second_norm)
    return torch.acos(torch.clamp(cosine, min=-1.0, max=1.0))


def _dihedrals(
    coordinates: torch.Tensor,
    torsions: torch.Tensor,
) -> torch.Tensor:
    if torsions.numel() == 0:
        return torch.empty(0, dtype=torch.float64)
    p0 = coordinates.index_select(0, torsions[:, 0])
    p1 = coordinates.index_select(0, torsions[:, 1])
    p2 = coordinates.index_select(0, torsions[:, 2])
    p3 = coordinates.index_select(0, torsions[:, 3])
    b0 = p0 - p1
    b1 = p2 - p1
    b2 = p3 - p2
    b1_norm = torch.linalg.vector_norm(b1, dim=1)
    if bool((b1_norm <= 1.0e-12).any().item()):
        raise InterpretablePoseScoringError("torsion contains a collapsed central bond")
    axis = b1 / b1_norm[:, None]
    v = b0 - torch.sum(b0 * axis, dim=1)[:, None] * axis
    w = b2 - torch.sum(b2 * axis, dim=1)[:, None] * axis
    v_norm = torch.linalg.vector_norm(v, dim=1)
    w_norm = torch.linalg.vector_norm(w, dim=1)
    if bool((v_norm <= 1.0e-12).any().item()) or bool((w_norm <= 1.0e-12).any().item()):
        raise InterpretablePoseScoringError(
            "torsion terminal vectors are collinear with the central bond"
        )
    v = v / v_norm[:, None]
    w = w / w_norm[:, None]
    x = torch.sum(v * w, dim=1)
    y = torch.sum(torch.cross(axis, v, dim=1) * w, dim=1)
    return torch.atan2(y, x)


class InterpretablePoseScorerV0:
    """Nine-term, claim-closed scorer for one authenticated docking problem."""

    scorer_id = "interpretable-pose-scorer-v0"
    scorer_version = "1.0.0"
    validated_for_docking_ranking = False

    def __init__(
        self,
        receptor: AllAtomSystem,
        ligand: AllAtomSystem,
        problem: DockingProblemIdentity,
        *,
        config: InterpretablePoseScoreConfig | None = None,
    ) -> None:
        active = InterpretablePoseScoreConfig() if config is None else config
        if not isinstance(active, InterpretablePoseScoreConfig):
            raise InterpretablePoseScoringError(
                "config must be InterpretablePoseScoreConfig"
            )
        if not isinstance(problem, DockingProblemIdentity) or not problem.bound:
            raise InterpretablePoseScoringError(
                "a bound docking problem identity is required"
            )
        for system, role in ((receptor, "receptor"), (ligand, "ligand")):
            if not isinstance(system, AllAtomSystem):
                raise TypeError(f"{role} must be AllAtomSystem")
            require_valid_all_atom_system(system)
            if system.model_count != 1 or system.coordinate_unit != "angstrom":
                raise InterpretablePoseScoringError(
                    f"{role} must contain one Angstrom coordinate model"
                )
            _coordinates(
                system.coordinates[0],
                name=f"{role} coordinates",
                atom_count=system.atom_count,
            )
            unsupported = sorted(
                {
                    atom.atomic_number
                    for atom in system.atoms
                    if atom.atomic_number
                    not in INTERPRETABLE_POSE_SUPPORTED_ATOMIC_NUMBERS
                }
            )
            if unsupported:
                raise InterpretablePoseScoringError(
                    f"{role} contains unsupported atomic numbers {unsupported}"
                )
        receptor_sha256 = canonical_system_sha256(receptor)
        ligand_sha256 = canonical_system_sha256(ligand)
        if (
            problem.receptor_system_sha256 != receptor_sha256
            or problem.ligand_system_sha256 != ligand_sha256
        ):
            raise InterpretablePoseScoringError(
                "scorer systems do not match the docking problem identity"
            )
        self.config = active
        self.problem = problem
        self.receptor = receptor
        self.ligand = ligand
        self.receptor_coordinates = receptor.coordinates[0]
        self.reference_ligand_coordinates = ligand.coordinates[0]
        if len(ligand.bonds) > active.max_bonds:
            raise InterpretablePoseScoringError("ligand bond capacity exceeded")
        if any(
            not isinstance(bond.metadata.get("is_in_ring"), bool)
            for bond in ligand.bonds
        ):
            raise InterpretablePoseScoringError(
                "ligand bonds must declare boolean is_in_ring metadata"
            )
        self.base_scorer = ElementGeometryDiagnosticScorer(
            self.receptor_coordinates,
            tuple(atom.atomic_number for atom in receptor.atoms),
            tuple(atom.atomic_number for atom in ligand.atoms),
            problem,
            config=active.base_geometry,
        )
        shell_mask = (
            torch.linalg.vector_norm(
                self.receptor_coordinates,
                dim=1,
            )
            <= active.base_geometry.receptor_shell_radius_angstrom
        )
        shell_indices = tuple(
            int(value)
            for value in torch.nonzero(shell_mask, as_tuple=False).reshape(-1).tolist()
        )
        shell_set = frozenset(shell_indices)
        self.receptor_features = _feature_receipt(
            receptor,
            role="receptor",
            allowed_atom_indices=shell_set,
        )
        self.ligand_features = _feature_receipt(ligand, role="ligand")
        adjacency = _adjacency(ligand)
        bond_pairs = tuple((bond.atom_i, bond.atom_j) for bond in ligand.bonds)
        angle_count = sum(
            len(neighbors) * (len(neighbors) - 1) // 2 for neighbors in adjacency
        )
        if angle_count > active.max_angles:
            raise InterpretablePoseScoringError("ligand angle capacity exceeded")
        angle_rows = _angle_triplets(adjacency)
        torsion_rows = _rotatable_torsions(ligand, adjacency)
        if len(angle_rows) != angle_count:
            raise InterpretablePoseScoringError(
                "ligand angle materialization count is inconsistent"
            )
        if len(torsion_rows) > active.max_rotatable_bonds:
            raise InterpretablePoseScoringError(
                "ligand rotatable-bond capacity exceeded"
            )
        self.bond_pairs = bond_pairs
        self.angle_triplets = angle_rows
        self.rotatable_torsions = torsion_rows
        self._bond_indices = torch.tensor(bond_pairs, dtype=torch.long).reshape(-1, 2)
        self._angle_indices = torch.tensor(angle_rows, dtype=torch.long).reshape(-1, 3)
        self._torsion_indices = torch.tensor(torsion_rows, dtype=torch.long).reshape(
            -1, 4
        )
        self._reference_bond_lengths = _bond_lengths(
            self.reference_ligand_coordinates,
            self._bond_indices,
        )
        self._reference_angles = _angles(
            self.reference_ligand_coordinates,
            self._angle_indices,
        )
        self._reference_torsions = _dihedrals(
            self.reference_ligand_coordinates,
            self._torsion_indices,
        )
        hbond_pair_count = len(self.ligand_features.donor_hydrogen_pairs) * len(
            self.receptor_features.acceptor_atom_indices
        ) + len(self.receptor_features.donor_hydrogen_pairs) * len(
            self.ligand_features.acceptor_atom_indices
        )
        if hbond_pair_count > active.max_hbond_pairs:
            raise InterpretablePoseScoringError("hydrogen-bond pair capacity exceeded")
        ligand_donor_pairs = tuple(
            (donor, hydrogen, acceptor)
            for donor, hydrogen in self.ligand_features.donor_hydrogen_pairs
            for acceptor in self.receptor_features.acceptor_atom_indices
        )
        receptor_donor_pairs = tuple(
            (donor, hydrogen, acceptor)
            for donor, hydrogen in self.receptor_features.donor_hydrogen_pairs
            for acceptor in self.ligand_features.acceptor_atom_indices
        )
        if len(ligand_donor_pairs) + len(receptor_donor_pairs) != hbond_pair_count:
            raise InterpretablePoseScoringError(
                "hydrogen-bond pair materialization count is inconsistent"
            )
        self._ligand_donor_pairs = torch.tensor(
            ligand_donor_pairs,
            dtype=torch.long,
        ).reshape(-1, 3)
        self._receptor_donor_pairs = torch.tensor(
            receptor_donor_pairs,
            dtype=torch.long,
        ).reshape(-1, 3)
        hydrophobic_pair_count = len(
            self.receptor_features.hydrophobic_atom_indices
        ) * len(self.ligand_features.hydrophobic_atom_indices)
        if hydrophobic_pair_count > active.max_hydrophobic_pairs:
            raise InterpretablePoseScoringError("hydrophobic pair capacity exceeded")
        hydrophobic_pairs = tuple(
            (receptor_atom, ligand_atom)
            for receptor_atom in self.receptor_features.hydrophobic_atom_indices
            for ligand_atom in self.ligand_features.hydrophobic_atom_indices
        )
        if len(hydrophobic_pairs) != hydrophobic_pair_count:
            raise InterpretablePoseScoringError(
                "hydrophobic pair materialization count is inconsistent"
            )
        self._hydrophobic_pairs = torch.tensor(
            hydrophobic_pairs,
            dtype=torch.long,
        ).reshape(-1, 2)
        if self._hydrophobic_pairs.numel():
            self._hydrophobic_radius_sums = torch.tensor(
                [
                    GEOMETRY_DIAGNOSTIC_RADII_ANGSTROM[
                        receptor.atoms[int(pair[0])].atomic_number
                    ]
                    + GEOMETRY_DIAGNOSTIC_RADII_ANGSTROM[
                        ligand.atoms[int(pair[1])].atomic_number
                    ]
                    for pair in hydrophobic_pairs
                ],
                dtype=torch.float64,
            )
        else:
            self._hydrophobic_radius_sums = torch.empty(0, dtype=torch.float64)
        self.feature_binding_sha256 = _canonical_sha256(
            {
                "schema_id": INTERPRETABLE_POSE_FEATURE_RECEIPT_SCHEMA_ID,
                "feature_profile_sha256": INTERPRETABLE_POSE_FEATURE_PROFILE_SHA256,
                "receptor": self.receptor_features.to_dict(),
                "ligand": self.ligand_features.to_dict(),
                "ligand_bond_pairs": [list(pair) for pair in self.bond_pairs],
                "ligand_angle_triplets": [list(row) for row in self.angle_triplets],
                "ligand_rotatable_torsions": [
                    list(row) for row in self.rotatable_torsions
                ],
            }
        )
        blockers: list[str] = list(INTERPRETABLE_POSE_SCORER_V0_BLOCKERS)
        if self.receptor_features.donor_direction_missing_atom_count:
            blockers.append("receptor_explicit_hydrogen_donor_directions_incomplete")
        if self.ligand_features.donor_direction_missing_atom_count:
            blockers.append("ligand_explicit_hydrogen_donor_directions_incomplete")
        if (
            self.receptor_features.declared_stereo_atom_indices
            or self.receptor_features.declared_stereo_bond_indices
            or self.ligand_features.declared_stereo_atom_indices
            or self.ligand_features.declared_stereo_bond_indices
        ):
            blockers.append("declared_stereo_geometry_validity_external_to_scorer")
        if not ligand_donor_pairs and not receptor_donor_pairs:
            blockers.append("directional_hydrogen_bond_pair_set_empty")
        if not hydrophobic_pairs:
            blockers.append("hydrophobic_contact_pair_set_empty")
        self._blockers = tuple(dict.fromkeys(blockers))
        self.parameter_source_sha256 = _canonical_sha256(
            {
                "feature_profile_sha256": INTERPRETABLE_POSE_FEATURE_PROFILE_SHA256,
                "geometry_radius_profile_sha256": self.base_scorer.parameter_source_sha256,
            }
        )
        self.config_fingerprint_sha256 = _canonical_sha256(
            {
                "schema_id": INTERPRETABLE_POSE_SCORER_V0_SCHEMA_ID,
                "config_sha256": active.fingerprint_sha256,
                "problem_sha256": problem.fingerprint_sha256,
                "receptor_system_sha256": receptor_sha256,
                "ligand_system_sha256": ligand_sha256,
                "reference_ligand_coordinate_sha256": coordinate_fingerprint(
                    self.reference_ligand_coordinates
                ),
                "feature_binding_sha256": self.feature_binding_sha256,
            }
        )
        self.score_descriptor = DockingScoreDescriptor(
            score_id="interpretable_pose_scorer_v0",
            direction=ScoreDirection.MINIMIZE,
            unit="dimensionless",
            semantics=(
                "element_geometry_plus_reference_relative_internal_strain_"
                "directional_hbond_and_hydrophobic_contact"
            ),
            calibrated=False,
            applicability_domain_id=self.feature_binding_sha256,
        )

    @property
    def problem_fingerprint_sha256(self) -> str:
        return self.problem.fingerprint_sha256

    @property
    def blockers(self) -> tuple[str, ...]:
        return self._blockers

    @property
    def receptor_shell_atom_count(self) -> int:
        return self.base_scorer.receptor_shell_atom_count

    @property
    def chemistry_scope(self) -> dict[str, object]:
        return {
            "feature_profile_sha256": INTERPRETABLE_POSE_FEATURE_PROFILE_SHA256,
            "problem_sha256": self.problem.fingerprint_sha256,
            "reference_ligand_system_sha256": canonical_system_sha256(self.ligand),
            "reference_ligand_coordinate_sha256": coordinate_fingerprint(
                self.reference_ligand_coordinates
            ),
            "supported_atomic_numbers": list(
                INTERPRETABLE_POSE_SUPPORTED_ATOMIC_NUMBERS
            ),
            "receptor_features": self.receptor_features.to_dict(),
            "ligand_features": self.ligand_features.to_dict(),
            "reference_relative_bond_strain_evaluated": True,
            "reference_relative_angle_strain_evaluated": True,
            "reference_relative_torsion_displacement_evaluated": True,
            "directional_d_h_a_hbond_evaluated": True,
            "hydrophobic_contact_evaluated": True,
            "formal_charge_used_for_feature_classification": True,
            "bond_order_used_for_feature_classification": True,
            "aromaticity_used_for_feature_classification": True,
            "ring_membership_used_for_rotatable_classification": True,
            "stereo_geometry_scored": False,
            "partial_charge_used": False,
            "acceptor_lone_pair_direction_used": False,
            "metal_coordination_supported": False,
            "calibrated": False,
        }

    def _internal_terms(self, coordinates: torch.Tensor) -> tuple[float, float, float]:
        bond_lengths = _bond_lengths(coordinates, self._bond_indices)
        angles = _angles(coordinates, self._angle_indices)
        torsions = _dihedrals(coordinates, self._torsion_indices)
        bond_raw = float(
            (
                (
                    (bond_lengths - self._reference_bond_lengths)
                    / self.config.bond_strain_scale_angstrom
                ).square()
            )
            .sum()
            .item()
        )
        angle_raw = float(
            (
                (
                    (angles - self._reference_angles)
                    / self.config.angle_strain_scale_radians
                ).square()
            )
            .sum()
            .item()
        )
        torsion_raw = float(
            (1.0 - torch.cos(torsions - self._reference_torsions)).sum().item()
        )
        return bond_raw, angle_raw, torsion_raw

    def _hbond_group(
        self,
        pairs: torch.Tensor,
        ligand_coordinates: torch.Tensor,
        *,
        ligand_donor: bool,
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        if pairs.numel() == 0:
            empty = torch.empty(0, dtype=torch.float64)
            return empty, empty, empty, empty
        if ligand_donor:
            donor = ligand_coordinates.index_select(0, pairs[:, 0])
            hydrogen = ligand_coordinates.index_select(0, pairs[:, 1])
            acceptor = self.receptor_coordinates.index_select(0, pairs[:, 2])
        else:
            donor = self.receptor_coordinates.index_select(0, pairs[:, 0])
            hydrogen = self.receptor_coordinates.index_select(0, pairs[:, 1])
            acceptor = ligand_coordinates.index_select(0, pairs[:, 2])
        h_a = torch.linalg.vector_norm(hydrogen - acceptor, dim=1)
        d_a = torch.linalg.vector_norm(donor - acceptor, dim=1)
        h_to_d = donor - hydrogen
        h_to_a = acceptor - hydrogen
        denominator = torch.linalg.vector_norm(
            h_to_d, dim=1
        ) * torch.linalg.vector_norm(h_to_a, dim=1)
        if bool((denominator <= 1.0e-12).any().item()):
            raise InterpretablePoseScoringError(
                "hydrogen-bond geometry contains collapsed atoms"
            )
        cosine = torch.clamp(
            torch.sum(h_to_d * h_to_a, dim=1) / denominator,
            min=-1.0,
            max=1.0,
        )
        angle = torch.acos(cosine)
        minimum = math.radians(self.config.hbond_minimum_angle_degrees)
        angular = torch.clamp(
            (angle - minimum) / (math.pi - minimum),
            min=0.0,
            max=1.0,
        ).square()
        radial = torch.exp(
            -0.5
            * (
                (h_a - self.config.hbond_h_a_center_angstrom)
                / self.config.hbond_h_a_width_angstrom
            ).square()
        )
        mask = (
            (h_a >= self.config.hbond_h_a_minimum_angstrom)
            & (h_a <= self.config.hbond_h_a_cutoff_angstrom)
            & (d_a <= self.config.hbond_d_a_cutoff_angstrom)
        )
        feature = torch.where(mask, radial * angular, torch.zeros_like(radial))
        return feature, h_a, d_a, torch.rad2deg(angle)

    def _hbond_terms(
        self,
        coordinates: torch.Tensor,
    ) -> tuple[float, int, InterpretableHydrogenBondObservation | None]:
        ligand_values = self._hbond_group(
            self._ligand_donor_pairs,
            coordinates,
            ligand_donor=True,
        )
        receptor_values = self._hbond_group(
            self._receptor_donor_pairs,
            coordinates,
            ligand_donor=False,
        )
        feature = torch.cat((ligand_values[0], receptor_values[0]))
        active = int((feature >= self.config.active_feature_threshold).sum().item())
        if not feature.numel() or float(feature.max().item()) <= 0.0:
            return -float(feature.sum().item()), active, None
        strongest_index = int(torch.argmax(feature).item())
        ligand_count = int(ligand_values[0].numel())
        if strongest_index < ligand_count:
            row = self._ligand_donor_pairs[strongest_index]
            local_index = strongest_index
            values = ligand_values
            direction = "ligand_donor_to_receptor_acceptor"
        else:
            local_index = strongest_index - ligand_count
            row = self._receptor_donor_pairs[local_index]
            values = receptor_values
            direction = "receptor_donor_to_ligand_acceptor"
        observation = InterpretableHydrogenBondObservation(
            direction=direction,
            donor_atom_index=int(row[0]),
            hydrogen_atom_index=int(row[1]),
            acceptor_atom_index=int(row[2]),
            h_a_distance_angstrom=float(values[1][local_index].item()),
            d_a_distance_angstrom=float(values[2][local_index].item()),
            d_h_a_angle_degrees=float(values[3][local_index].item()),
            feature_value=float(values[0][local_index].item()),
        )
        return -float(feature.sum().item()), active, observation

    def _hydrophobic_term(self, coordinates: torch.Tensor) -> tuple[float, int]:
        if self._hydrophobic_pairs.numel() == 0:
            return 0.0, 0
        receptor = self.receptor_coordinates.index_select(
            0,
            self._hydrophobic_pairs[:, 0],
        )
        ligand = coordinates.index_select(0, self._hydrophobic_pairs[:, 1])
        distance = torch.linalg.vector_norm(receptor - ligand, dim=1)
        center = (
            self._hydrophobic_radius_sums
            + self.config.hydrophobic_contact_offset_angstrom
        )
        feature = torch.exp(
            -0.5
            * (
                (distance - center) / self.config.hydrophobic_contact_width_angstrom
            ).square()
        )
        selected = (distance <= self.config.hydrophobic_contact_cutoff_angstrom) & (
            distance
            >= self.config.hydrophobic_minimum_contact_scale
            * self._hydrophobic_radius_sums
        )
        feature = torch.where(selected, feature, torch.zeros_like(feature))
        active = int((feature >= self.config.active_feature_threshold).sum().item())
        return -float(feature.sum().item()), active

    def _evaluate(
        self,
        coordinates: torch.Tensor,
    ) -> tuple[
        DockingScoreBreakdown,
        int,
        int,
        InterpretableHydrogenBondObservation | None,
    ]:
        ligand_coordinates = _coordinates(
            coordinates,
            name="ligand coordinates",
            atom_count=self.ligand.atom_count,
        )
        base = self.base_scorer.score_coordinates(ligand_coordinates)
        base_terms = tuple(
            term
            for term in base.terms
            if term.term_id != "rigid_ligand_internal_strain"
        )
        bond_raw, angle_raw, torsion_raw = self._internal_terms(ligand_coordinates)
        hbond_raw, hbond_active, strongest_hbond = self._hbond_terms(ligand_coordinates)
        hydrophobic_raw, hydrophobic_active = self._hydrophobic_term(ligand_coordinates)
        terms = (
            *base_terms,
            DockingScoreTerm(
                term_id="ligand_bond_length_strain",
                raw_value=bond_raw,
                weight=self.config.bond_strain_weight,
                unit="dimensionless",
                semantics="sum_squared_reference_relative_bond_displacement_over_scale",
                parameter_source_sha256=self.config_fingerprint_sha256,
            ),
            DockingScoreTerm(
                term_id="ligand_angle_strain",
                raw_value=angle_raw,
                weight=self.config.angle_strain_weight,
                unit="dimensionless",
                semantics="sum_squared_reference_relative_angle_displacement_over_scale",
                parameter_source_sha256=self.config_fingerprint_sha256,
            ),
            DockingScoreTerm(
                term_id="ligand_torsion_displacement",
                raw_value=torsion_raw,
                weight=self.config.torsion_displacement_weight,
                unit="dimensionless",
                semantics="sum_one_minus_cosine_of_reference_relative_rotatable_dihedral",
                parameter_source_sha256=self.config_fingerprint_sha256,
            ),
            DockingScoreTerm(
                term_id="directional_hydrogen_bond_reward",
                raw_value=hbond_raw,
                weight=self.config.hbond_weight,
                unit="dimensionless",
                semantics="negative_sum_D_H_A_angular_and_H_A_radial_features",
                parameter_source_sha256=self.config_fingerprint_sha256,
            ),
            DockingScoreTerm(
                term_id="hydrophobic_contact_reward",
                raw_value=hydrophobic_raw,
                weight=self.config.hydrophobic_weight,
                unit="dimensionless",
                semantics="negative_gaussian_neutral_hydrophobic_element_contact_count",
                parameter_source_sha256=self.config_fingerprint_sha256,
            ),
        )
        breakdown = DockingScoreBreakdown(
            terms=terms,
            blockers=self.blockers,
        )
        return breakdown, hbond_active, hydrophobic_active, strongest_hbond

    def score_coordinates(self, coordinates: torch.Tensor) -> DockingScoreBreakdown:
        return self._evaluate(coordinates)[0]

    def score_with_diagnostics(
        self,
        proposal: DockingProposal,
    ) -> tuple[DockingScoreBreakdown, InterpretablePoseScoreDiagnostics]:
        if not isinstance(proposal, DockingProposal):
            raise InterpretablePoseScoringError("proposal must be DockingProposal")
        if proposal.problem_fingerprint_sha256 != self.problem.fingerprint_sha256:
            raise InterpretablePoseScoringError(
                "proposal problem identity does not match the scorer"
            )
        (
            breakdown,
            hbond_active,
            hydrophobic_active,
            strongest_hbond,
        ) = self._evaluate(proposal.coordinates)
        diagnostics = InterpretablePoseScoreDiagnostics(
            candidate_id=proposal.candidate_id,
            coordinate_sha256=proposal.coordinate_fingerprint_sha256,
            scorer_fingerprint_sha256=self.config_fingerprint_sha256,
            feature_binding_sha256=self.feature_binding_sha256,
            bond_count=len(self.bond_pairs),
            angle_count=len(self.angle_triplets),
            rotatable_bond_count=len(self.rotatable_torsions),
            hbond_candidate_count=(
                int(self._ligand_donor_pairs.shape[0])
                + int(self._receptor_donor_pairs.shape[0])
            ),
            hbond_active_count=hbond_active,
            hydrophobic_pair_count=int(self._hydrophobic_pairs.shape[0]),
            hydrophobic_active_count=hydrophobic_active,
            term_raw_values=tuple(
                (term.term_id, term.raw_value) for term in breakdown.terms
            ),
            strongest_hbond=strongest_hbond,
        )
        return breakdown, diagnostics

    def score(self, proposal: DockingProposal) -> DockingScoreBreakdown:
        if not isinstance(proposal, DockingProposal):
            raise InterpretablePoseScoringError("proposal must be DockingProposal")
        if proposal.problem_fingerprint_sha256 != self.problem.fingerprint_sha256:
            raise InterpretablePoseScoringError(
                "proposal problem identity does not match the scorer"
            )
        return self.score_coordinates(proposal.coordinates)


__all__ = [
    "INTERPRETABLE_POSE_DIAGNOSTICS_SCHEMA_ID",
    "INTERPRETABLE_POSE_FEATURE_PROFILE_ID",
    "INTERPRETABLE_POSE_FEATURE_PROFILE_SHA256",
    "INTERPRETABLE_POSE_FEATURE_RECEIPT_SCHEMA_ID",
    "INTERPRETABLE_POSE_SCORER_V0_BLOCKERS",
    "INTERPRETABLE_POSE_SCORER_V0_SCHEMA_ID",
    "INTERPRETABLE_POSE_SUPPORTED_ATOMIC_NUMBERS",
    "InterpretableHydrogenBondObservation",
    "InterpretablePoseFeatureReceipt",
    "InterpretablePoseScoreConfig",
    "InterpretablePoseScoreDiagnostics",
    "InterpretablePoseScorerV0",
    "InterpretablePoseScoringError",
    "interpretable_pose_feature_profile_document",
]
