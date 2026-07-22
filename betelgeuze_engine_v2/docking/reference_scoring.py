"""Uncalibrated, explicitly parameterized receptor--ligand score decomposition.

This module deliberately does not ship fitted atom types or docking weights.
Callers must bind canonical all-atom systems to explicit reference force-field
parameters.  The resulting score is useful for deterministic diagnostics and
future calibration, but it is not validated for pose ranking or affinity.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from numbers import Real

import torch

from betelgeuze_engine_v2.geometry import RadiusGraphConfig, build_compact_radius_graph
from betelgeuze_engine_v2.molecular import (
    AllAtomSystem,
    canonical_system_sha256,
    canonical_topology_sha256,
    element_for_atomic_number,
    require_valid_all_atom_system,
)
from betelgeuze_engine_v2.physics import (
    COULOMB_KCAL_ANGSTROM_PER_MOL_E2,
    ReferenceForceFieldParameters,
    evaluate_reference_force_field,
)

from .identity import DockingProblemIdentity
from .proposals import DockingProposal
from .scoring import (
    DockingScoreBreakdown,
    DockingScoreDescriptor,
    DockingScoreTerm,
    ScoreDirection,
)


REFERENCE_DOCKING_SCORER_SCHEMA_ID = (
    "betelgeuze.engine_v2_uncalibrated_reference_docking_scorer/1.0.0"
)
DEFAULT_SUPPORTED_DOCKING_ATOMIC_NUMBERS = (1, 6, 7, 8, 9, 15, 16, 17, 35, 53)
_UNSPECIFIED_STEREO = {"", "NONE", "UNKNOWN", "UNSPECIFIED"}


class ReferenceDockingScoringError(ValueError):
    """Inputs exceed the bounded, explicit reference docking score contract."""


def _finite_float(
    value: object,
    *,
    name: str,
    positive: bool = False,
    nonnegative: bool = False,
) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ReferenceDockingScoringError(f"{name} must be a finite real number")
    number = float(value)
    if not math.isfinite(number):
        raise ReferenceDockingScoringError(f"{name} must be finite")
    if positive and number <= 0.0:
        raise ReferenceDockingScoringError(f"{name} must be positive")
    if nonnegative and number < 0.0:
        raise ReferenceDockingScoringError(f"{name} must be non-negative")
    return number


def _exact_int(value: object, *, name: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ReferenceDockingScoringError(f"{name} must be an integer")
    integer = int(value)
    if integer < minimum:
        raise ReferenceDockingScoringError(f"{name} must be at least {minimum}")
    return integer


def _canonical_sha256(payload: object) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class ReferenceDockingChemistryScope:
    """Frozen admission scope for the first diagnostic scorer profile."""

    supported_atomic_numbers: tuple[int, ...] = DEFAULT_SUPPORTED_DOCKING_ATOMIC_NUMBERS
    maximum_absolute_formal_charge: int = 4
    require_partial_charge_parameter_match: bool = True
    allow_receptor_nonpolymer_residues: bool = False
    aromatic_policy: str = "parameterized_atoms_without_aromatic_specific_term"
    stereo_policy: str = "topology_identity_only_external_pose_validity_required"
    metal_policy: str = "abstain"
    cofactor_policy: str = "abstain"

    def __post_init__(self) -> None:
        numbers = tuple(
            _exact_int(value, name="supported atomic number", minimum=1)
            for value in self.supported_atomic_numbers
        )
        if not numbers or tuple(sorted(set(numbers))) != numbers or numbers[-1] > 118:
            raise ReferenceDockingScoringError(
                "supported_atomic_numbers must be a sorted unique subset of [1,118]"
            )
        maximum_charge = _exact_int(
            self.maximum_absolute_formal_charge,
            name="maximum_absolute_formal_charge",
        )
        if not isinstance(self.require_partial_charge_parameter_match, bool):
            raise ReferenceDockingScoringError(
                "require_partial_charge_parameter_match must be boolean"
            )
        if not isinstance(self.allow_receptor_nonpolymer_residues, bool):
            raise ReferenceDockingScoringError(
                "allow_receptor_nonpolymer_residues must be boolean"
            )
        expected_policies = {
            "aromatic_policy": "parameterized_atoms_without_aromatic_specific_term",
            "stereo_policy": "topology_identity_only_external_pose_validity_required",
            "metal_policy": "abstain",
            "cofactor_policy": "abstain",
        }
        for name, expected in expected_policies.items():
            if getattr(self, name) != expected:
                raise ReferenceDockingScoringError(
                    f"{name} must remain frozen as {expected!r} in this scorer version"
                )
        object.__setattr__(self, "supported_atomic_numbers", numbers)
        object.__setattr__(self, "maximum_absolute_formal_charge", maximum_charge)

    def to_dict(self) -> dict[str, object]:
        return {
            "supported_atomic_numbers": list(self.supported_atomic_numbers),
            "supported_elements": [
                element_for_atomic_number(value)
                for value in self.supported_atomic_numbers
            ],
            "maximum_absolute_formal_charge": self.maximum_absolute_formal_charge,
            "require_partial_charge_parameter_match": (
                self.require_partial_charge_parameter_match
            ),
            "allow_receptor_nonpolymer_residues": (
                self.allow_receptor_nonpolymer_residues
            ),
            "aromatic_policy": self.aromatic_policy,
            "stereo_policy": self.stereo_policy,
            "metal_policy": self.metal_policy,
            "cofactor_policy": self.cofactor_policy,
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())


@dataclass(frozen=True)
class ReferenceDockingScoreConfig:
    """Numerical policy for an explicitly uncalibrated diagnostic score."""

    cutoff_angstrom: float = 8.0
    switch_start_angstrom: float = 6.0
    dielectric: float = 4.0
    screening_kappa_per_angstrom: float = 0.0
    softcore_distance_angstrom: float = 0.35
    clash_contact_scale: float = 0.75
    clash_force_constant_kcal_per_mol_angstrom2: float = 10.0
    lennard_jones_weight: float = 1.0
    electrostatic_weight: float = 1.0
    ligand_strain_weight: float = 1.0
    clash_weight: float = 1.0
    max_cross_pairs: int = 1_000_000
    max_ligand_atoms: int = 256
    chemistry_scope: ReferenceDockingChemistryScope = ReferenceDockingChemistryScope()

    def __post_init__(self) -> None:
        cutoff = _finite_float(
            self.cutoff_angstrom,
            name="cutoff_angstrom",
            positive=True,
        )
        switch = _finite_float(
            self.switch_start_angstrom,
            name="switch_start_angstrom",
            nonnegative=True,
        )
        if switch >= cutoff:
            raise ReferenceDockingScoringError(
                "switch_start_angstrom must be less than cutoff_angstrom"
            )
        object.__setattr__(self, "cutoff_angstrom", cutoff)
        object.__setattr__(self, "switch_start_angstrom", switch)
        for name in (
            "dielectric",
            "softcore_distance_angstrom",
            "clash_contact_scale",
            "clash_force_constant_kcal_per_mol_angstrom2",
        ):
            object.__setattr__(
                self,
                name,
                _finite_float(getattr(self, name), name=name, positive=True),
            )
        object.__setattr__(
            self,
            "screening_kappa_per_angstrom",
            _finite_float(
                self.screening_kappa_per_angstrom,
                name="screening_kappa_per_angstrom",
                nonnegative=True,
            ),
        )
        for name in (
            "lennard_jones_weight",
            "electrostatic_weight",
            "ligand_strain_weight",
            "clash_weight",
        ):
            object.__setattr__(
                self,
                name,
                _finite_float(getattr(self, name), name=name, nonnegative=True),
            )
        object.__setattr__(
            self,
            "max_cross_pairs",
            _exact_int(self.max_cross_pairs, name="max_cross_pairs", minimum=1),
        )
        max_ligand_atoms = _exact_int(
            self.max_ligand_atoms,
            name="max_ligand_atoms",
            minimum=1,
        )
        if max_ligand_atoms > 256:
            raise ReferenceDockingScoringError(
                "max_ligand_atoms exceeds the compact-neighbor hard limit 256"
            )
        object.__setattr__(self, "max_ligand_atoms", max_ligand_atoms)
        if not isinstance(self.chemistry_scope, ReferenceDockingChemistryScope):
            raise ReferenceDockingScoringError(
                "chemistry_scope must be ReferenceDockingChemistryScope"
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": REFERENCE_DOCKING_SCORER_SCHEMA_ID,
            "cutoff_angstrom": self.cutoff_angstrom,
            "switch_start_angstrom": self.switch_start_angstrom,
            "dielectric": self.dielectric,
            "screening_kappa_per_angstrom": self.screening_kappa_per_angstrom,
            "softcore_distance_angstrom": self.softcore_distance_angstrom,
            "clash_contact_scale": self.clash_contact_scale,
            "clash_force_constant_kcal_per_mol_angstrom2": (
                self.clash_force_constant_kcal_per_mol_angstrom2
            ),
            "lennard_jones_weight": self.lennard_jones_weight,
            "electrostatic_weight": self.electrostatic_weight,
            "ligand_strain_weight": self.ligand_strain_weight,
            "clash_weight": self.clash_weight,
            "max_cross_pairs": self.max_cross_pairs,
            "max_ligand_atoms": self.max_ligand_atoms,
            "chemistry_scope": self.chemistry_scope.to_dict(),
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())


def _parameter_map(parameters: ReferenceForceFieldParameters, atom_count: int):
    mapping = parameters.atom_parameter_map
    if set(mapping) != set(range(atom_count)):
        raise ReferenceDockingScoringError(
            "nonbonded parameters must cover every canonical atom exactly once"
        )
    return mapping


def _require_system_scope(
    system: AllAtomSystem,
    parameters: ReferenceForceFieldParameters,
    *,
    role: str,
    config: ReferenceDockingScoreConfig,
) -> None:
    require_valid_all_atom_system(system)
    if system.model_count != 1:
        raise ReferenceDockingScoringError(f"{role} must contain exactly one model")
    if system.coordinates.dtype != torch.float64 or system.coordinates.device.type != "cpu":
        raise ReferenceDockingScoringError(f"{role} must use CPU float64 coordinates")
    if system.cell is not None:
        raise ReferenceDockingScoringError(
            f"{role} periodic cells are outside the docking scorer scope"
        )
    if role == "ligand" and system.atom_count > config.max_ligand_atoms:
        raise ReferenceDockingScoringError("ligand atom count exceeds scorer capacity")
    if parameters.topology_sha256 != canonical_topology_sha256(system):
        raise ReferenceDockingScoringError(
            f"{role} parameter topology does not match the canonical system"
        )
    mapping = _parameter_map(parameters, system.atom_count)
    scope = config.chemistry_scope
    for atom in system.atoms:
        if atom.atomic_number not in scope.supported_atomic_numbers:
            raise ReferenceDockingScoringError(
                f"{role} atom {atom.index} element {atom.element} is outside the supported scope"
            )
        if abs(atom.formal_charge) > scope.maximum_absolute_formal_charge:
            raise ReferenceDockingScoringError(
                f"{role} atom {atom.index} formal charge is outside the supported scope"
            )
        if scope.require_partial_charge_parameter_match:
            if atom.partial_charge_e is None:
                raise ReferenceDockingScoringError(
                    f"{role} atom {atom.index} is missing an explicit partial charge"
                )
            if not math.isclose(
                float(atom.partial_charge_e),
                mapping[atom.index].charge_e,
                rel_tol=0.0,
                abs_tol=1.0e-12,
            ):
                raise ReferenceDockingScoringError(
                    f"{role} atom {atom.index} partial charge does not match its parameter"
                )
    if role == "receptor" and not scope.allow_receptor_nonpolymer_residues:
        nonpolymer = [
            residue.index
            for residue in system.residues
            if residue.entity_type.strip().lower() != "polymer"
        ]
        if nonpolymer:
            raise ReferenceDockingScoringError(
                "receptor nonpolymer residues are outside the cofactor-abstention scope"
            )


def _ligand_energy(
    system: AllAtomSystem,
    parameters: ReferenceForceFieldParameters,
) -> float:
    maximum = max(1, system.atom_count)
    neighbors = build_compact_radius_graph(
        system.coordinates,
        RadiusGraphConfig(
            cutoff_angstrom=parameters.cutoff_angstrom,
            max_neighbors=max(1, system.atom_count - 1),
            max_atoms_per_cell=maximum,
        ),
    )
    evaluation = evaluate_reference_force_field(system, neighbors, parameters)
    energy = float(evaluation.term.energy.detach().cpu().reshape(-1)[0].item())
    if not math.isfinite(energy):
        raise ReferenceDockingScoringError("ligand reference energy is not finite")
    return energy


def _switch(distance: torch.Tensor, start: float, cutoff: float) -> torch.Tensor:
    fraction = ((distance - start) / (cutoff - start)).clamp(0.0, 1.0)
    smooth = (
        1.0
        - 10.0 * fraction.pow(3)
        + 15.0 * fraction.pow(4)
        - 6.0 * fraction.pow(5)
    )
    return torch.where(
        distance <= start,
        torch.ones_like(distance),
        torch.where(distance < cutoff, smooth, torch.zeros_like(distance)),
    )


class UncalibratedReferenceDockingScorer:
    """CPU float64 interaction-plus-strain scorer with four explicit terms."""

    scorer_id = "uncalibrated-reference-interaction-strain"
    scorer_version = "1.0.0"
    validated_for_docking_ranking = False

    def __init__(
        self,
        receptor_system: AllAtomSystem,
        ligand_system: AllAtomSystem,
        receptor_parameters: ReferenceForceFieldParameters,
        ligand_parameters: ReferenceForceFieldParameters,
        problem: DockingProblemIdentity,
        *,
        config: ReferenceDockingScoreConfig | None = None,
    ) -> None:
        self.config = config or ReferenceDockingScoreConfig()
        self.receptor_system = receptor_system
        self.ligand_system = ligand_system
        self.receptor_parameters = receptor_parameters
        self.ligand_parameters = ligand_parameters
        self.problem = problem
        if not problem.bound:
            raise ReferenceDockingScoringError("docking problem identity must be bound")
        receptor_sha256 = canonical_system_sha256(receptor_system)
        ligand_sha256 = canonical_system_sha256(ligand_system)
        if problem.receptor_system_sha256 != receptor_sha256:
            raise ReferenceDockingScoringError(
                "problem receptor identity does not match the scorer receptor"
            )
        if problem.ligand_system_sha256 != ligand_sha256:
            raise ReferenceDockingScoringError(
                "problem ligand identity does not match the scorer ligand"
            )
        _require_system_scope(
            receptor_system,
            receptor_parameters,
            role="receptor",
            config=self.config,
        )
        _require_system_scope(
            ligand_system,
            ligand_parameters,
            role="ligand",
            config=self.config,
        )
        if self.config.cutoff_angstrom > min(
            receptor_parameters.cutoff_angstrom,
            ligand_parameters.cutoff_angstrom,
        ):
            raise ReferenceDockingScoringError(
                "docking cutoff exceeds a bound parameter-set cutoff"
            )
        pair_capacity = receptor_system.atom_count * ligand_system.atom_count
        if pair_capacity > self.config.max_cross_pairs:
            raise ReferenceDockingScoringError(
                "receptor-ligand cross-pair capacity exceeded"
            )
        self._receptor_parameter_map = receptor_parameters.atom_parameter_map
        self._ligand_parameter_map = ligand_parameters.atom_parameter_map
        self._ligand_reference_energy = _ligand_energy(
            ligand_system,
            ligand_parameters,
        )
        self.parameter_source_sha256 = _canonical_sha256(
            {
                "receptor_parameter_sha256": receptor_parameters.fingerprint_sha256,
                "ligand_parameter_sha256": ligand_parameters.fingerprint_sha256,
            }
        )
        self.config_fingerprint_sha256 = _canonical_sha256(
            {
                "schema_id": REFERENCE_DOCKING_SCORER_SCHEMA_ID,
                "config_sha256": self.config.fingerprint_sha256,
                "problem_sha256": problem.fingerprint_sha256,
                "parameter_source_sha256": self.parameter_source_sha256,
            }
        )
        self.score_descriptor = DockingScoreDescriptor(
            score_id="uncalibrated_reference_interaction_plus_strain",
            direction=ScoreDirection.MINIMIZE,
            unit="kcal/mol",
            semantics=(
                "weighted_sum_of_cross_lj_cross_screened_coulomb_signed_ligand_"
                "internal_energy_delta_and_vdw_overlap_penalty"
            ),
            calibrated=False,
            applicability_domain_id=self.config.chemistry_scope.fingerprint_sha256,
        )
        has_aromatic = any(
            atom.aromatic for atom in (*receptor_system.atoms, *ligand_system.atoms)
        ) or any(
            bond.aromatic for bond in (*receptor_system.bonds, *ligand_system.bonds)
        )
        has_declared_stereo = any(
            atom.stereo.strip().upper() not in _UNSPECIFIED_STEREO
            for atom in ligand_system.atoms
        ) or any(
            bond.stereo.strip().upper() not in _UNSPECIFIED_STEREO
            for bond in ligand_system.bonds
        )
        blockers = [
            "reference_docking_score_uncalibrated",
            "public_pose_ranking_calibration_fit_missing",
            "public_docking_benchmark_missing",
            "metals_and_cofactors_outside_scope",
        ]
        if has_aromatic:
            blockers.append("aromatic_specific_interaction_term_missing")
        if has_declared_stereo:
            blockers.append("stereo_validity_is_external_to_scorer")
        self._blockers = tuple(blockers)

    @property
    def chemistry_scope(self) -> dict[str, object]:
        return self.config.chemistry_scope.to_dict()

    def _cross_terms(self, ligand_coordinates: torch.Tensor) -> tuple[float, float, float]:
        receptor_coordinates = self.receptor_system.coordinates[0]
        delta = receptor_coordinates[:, None, :] - ligand_coordinates[None, :, :]
        distance = torch.linalg.vector_norm(delta, dim=-1)
        selected = distance < self.config.cutoff_angstrom
        if not bool(selected.any().item()):
            return 0.0, 0.0, 0.0
        receptor_indices, ligand_indices = torch.nonzero(selected, as_tuple=True)
        raw_distance = distance[receptor_indices, ligand_indices]
        effective_distance = torch.sqrt(
            raw_distance.square() + self.config.softcore_distance_angstrom**2
        )
        receptor_rows = [
            self._receptor_parameter_map[int(index)]
            for index in receptor_indices.detach().cpu().tolist()
        ]
        ligand_rows = [
            self._ligand_parameter_map[int(index)]
            for index in ligand_indices.detach().cpu().tolist()
        ]
        sigma = torch.tensor(
            [
                0.5 * (receptor.sigma_angstrom + ligand.sigma_angstrom)
                for receptor, ligand in zip(receptor_rows, ligand_rows)
            ],
            dtype=torch.float64,
        )
        epsilon = torch.tensor(
            [
                math.sqrt(
                    receptor.epsilon_kcal_per_mol
                    * ligand.epsilon_kcal_per_mol
                )
                for receptor, ligand in zip(receptor_rows, ligand_rows)
            ],
            dtype=torch.float64,
        )
        charge_product = torch.tensor(
            [
                receptor.charge_e * ligand.charge_e
                for receptor, ligand in zip(receptor_rows, ligand_rows)
            ],
            dtype=torch.float64,
        )
        switching = _switch(
            raw_distance,
            self.config.switch_start_angstrom,
            self.config.cutoff_angstrom,
        )
        ratio6 = (sigma / effective_distance).pow(6)
        lennard_jones = (
            4.0 * epsilon * (ratio6.pow(2) - ratio6) * switching
        ).sum()
        electrostatic = (
            COULOMB_KCAL_ANGSTROM_PER_MOL_E2
            * charge_product
            * torch.exp(
                -self.config.screening_kappa_per_angstrom * raw_distance
            )
            / (self.config.dielectric * effective_distance)
            * switching
        ).sum()
        contact_distance = (
            self.config.clash_contact_scale
            * (2.0 ** (1.0 / 6.0))
            * sigma
        )
        overlap = torch.clamp(contact_distance - raw_distance, min=0.0)
        clash = (
            self.config.clash_force_constant_kcal_per_mol_angstrom2
            * overlap.square()
        ).sum()
        return (
            float(lennard_jones.item()),
            float(electrostatic.item()),
            float(clash.item()),
        )

    def score(self, proposal: DockingProposal) -> DockingScoreBreakdown:
        if proposal.problem_fingerprint_sha256 != self.problem.fingerprint_sha256:
            raise ReferenceDockingScoringError(
                "proposal problem identity does not match the scorer"
            )
        if proposal.coordinates.shape != (self.ligand_system.atom_count, 3):
            raise ReferenceDockingScoringError(
                "proposal atom count does not match the scorer ligand"
            )
        if (
            proposal.coordinates.dtype != torch.float64
            or proposal.coordinates.device.type != "cpu"
        ):
            raise ReferenceDockingScoringError(
                "proposal coordinates must use CPU float64"
            )
        candidate_system = self.ligand_system.with_coordinates(
            proposal.coordinates.unsqueeze(0),
            operation=f"uncalibrated_docking_score:{proposal.candidate_id}",
        )
        candidate_energy = _ligand_energy(
            candidate_system,
            self.ligand_parameters,
        )
        strain_delta = candidate_energy - self._ligand_reference_energy
        lennard_jones, electrostatic, clash = self._cross_terms(
            proposal.coordinates
        )
        return DockingScoreBreakdown(
            terms=(
                DockingScoreTerm(
                    term_id="receptor_ligand_lennard_jones",
                    raw_value=lennard_jones,
                    weight=self.config.lennard_jones_weight,
                    unit="kcal/mol",
                    semantics=(
                        "softcore_switched_cross_lennard_jones_with_lorentz_"
                        "berthelot_combining"
                    ),
                    parameter_source_sha256=self.parameter_source_sha256,
                ),
                DockingScoreTerm(
                    term_id="receptor_ligand_screened_coulomb",
                    raw_value=electrostatic,
                    weight=self.config.electrostatic_weight,
                    unit="kcal/mol",
                    semantics=(
                        "softcore_switched_cross_coulomb_from_explicit_partial_charges"
                    ),
                    parameter_source_sha256=self.parameter_source_sha256,
                ),
                DockingScoreTerm(
                    term_id="ligand_internal_strain_delta",
                    raw_value=strain_delta,
                    weight=self.config.ligand_strain_weight,
                    unit="kcal/mol",
                    semantics=(
                        "signed_reference_force_field_internal_energy_delta_from_"
                        "the_bound_input_conformer"
                    ),
                    parameter_source_sha256=self.ligand_parameters.fingerprint_sha256,
                ),
                DockingScoreTerm(
                    term_id="vdw_overlap_penalty",
                    raw_value=clash,
                    weight=self.config.clash_weight,
                    unit="kcal/mol",
                    semantics=(
                        "quadratic_overlap_below_scaled_lj_minimum_contact_distance"
                    ),
                    parameter_source_sha256=self.parameter_source_sha256,
                ),
            ),
            blockers=self._blockers,
        )


__all__ = [
    "DEFAULT_SUPPORTED_DOCKING_ATOMIC_NUMBERS",
    "REFERENCE_DOCKING_SCORER_SCHEMA_ID",
    "ReferenceDockingChemistryScope",
    "ReferenceDockingScoreConfig",
    "ReferenceDockingScoringError",
    "UncalibratedReferenceDockingScorer",
]
