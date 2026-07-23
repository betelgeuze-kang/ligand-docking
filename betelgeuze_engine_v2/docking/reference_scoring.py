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

from .identity import DockingProblemIdentity, coordinate_fingerprint
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
REFERENCE_DOCKING_INTERACTION_DIAGNOSTICS_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_docking_interaction_diagnostics/1.0.0"
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


def _required_sha256(value: object, *, name: str) -> str:
    if not isinstance(value, str):
        raise ReferenceDockingScoringError(f"{name} must be a lowercase SHA-256")
    digest = value.strip().lower()
    if len(digest) != 64 or any(
        character not in "0123456789abcdef" for character in digest
    ):
        raise ReferenceDockingScoringError(f"{name} must be a lowercase SHA-256")
    return digest


def _diagnostic_pair(
    value: tuple[int, int] | None,
    *,
    name: str,
    required: bool,
) -> tuple[int, int] | None:
    if value is None:
        if required:
            raise ReferenceDockingScoringError(f"{name} is required")
        return None
    if not isinstance(value, tuple) or len(value) != 2:
        raise ReferenceDockingScoringError(f"{name} must be a pair of atom indices")
    return (
        _exact_int(value[0], name=f"{name}[0]"),
        _exact_int(value[1], name=f"{name}[1]"),
    )


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


@dataclass(frozen=True)
class ReferenceDockingContactDiagnostics:
    """Pairwise steric-contact diagnostics under the scorer's LJ parameters."""

    scope: str
    total_pair_count: int
    evaluated_pair_count: int
    excluded_pair_count: int
    clashing_pair_count: int
    minimum_distance_angstrom: float | None
    minimum_contact_ratio: float | None
    minimum_contact_ratio_pair: tuple[int, int] | None
    maximum_overlap_angstrom: float
    maximum_overlap_pair: tuple[int, int] | None

    def __post_init__(self) -> None:
        if self.scope not in {"receptor_ligand", "ligand_internal_nonbonded"}:
            raise ReferenceDockingScoringError("unsupported contact diagnostic scope")
        total = _exact_int(self.total_pair_count, name="total_pair_count")
        evaluated = _exact_int(self.evaluated_pair_count, name="evaluated_pair_count")
        excluded = _exact_int(self.excluded_pair_count, name="excluded_pair_count")
        clashing = _exact_int(self.clashing_pair_count, name="clashing_pair_count")
        if evaluated + excluded != total:
            raise ReferenceDockingScoringError(
                "evaluated and excluded contact pairs must equal total pairs"
            )
        if clashing > evaluated:
            raise ReferenceDockingScoringError(
                "clashing_pair_count cannot exceed evaluated_pair_count"
            )
        maximum_overlap = _finite_float(
            self.maximum_overlap_angstrom,
            name="maximum_overlap_angstrom",
            nonnegative=True,
        )
        if evaluated == 0:
            if (
                self.minimum_distance_angstrom is not None
                or self.minimum_contact_ratio is not None
                or self.minimum_contact_ratio_pair is not None
                or self.maximum_overlap_pair is not None
                or clashing != 0
                or maximum_overlap != 0.0
            ):
                raise ReferenceDockingScoringError(
                    "empty contact diagnostics cannot contain pair measurements"
                )
        else:
            minimum_distance = _finite_float(
                self.minimum_distance_angstrom,
                name="minimum_distance_angstrom",
                nonnegative=True,
            )
            minimum_ratio = _finite_float(
                self.minimum_contact_ratio,
                name="minimum_contact_ratio",
                nonnegative=True,
            )
            minimum_pair = _diagnostic_pair(
                self.minimum_contact_ratio_pair,
                name="minimum_contact_ratio_pair",
                required=True,
            )
            maximum_pair = _diagnostic_pair(
                self.maximum_overlap_pair,
                name="maximum_overlap_pair",
                required=maximum_overlap > 0.0,
            )
            if maximum_overlap == 0.0 and maximum_pair is not None:
                raise ReferenceDockingScoringError(
                    "zero maximum overlap cannot identify an overlap pair"
                )
            object.__setattr__(self, "minimum_distance_angstrom", minimum_distance)
            object.__setattr__(self, "minimum_contact_ratio", minimum_ratio)
            object.__setattr__(self, "minimum_contact_ratio_pair", minimum_pair)
            object.__setattr__(self, "maximum_overlap_pair", maximum_pair)
        object.__setattr__(self, "total_pair_count", total)
        object.__setattr__(self, "evaluated_pair_count", evaluated)
        object.__setattr__(self, "excluded_pair_count", excluded)
        object.__setattr__(self, "clashing_pair_count", clashing)
        object.__setattr__(self, "maximum_overlap_angstrom", maximum_overlap)

    def to_dict(self) -> dict[str, object]:
        return {
            "scope": self.scope,
            "total_pair_count": self.total_pair_count,
            "evaluated_pair_count": self.evaluated_pair_count,
            "excluded_pair_count": self.excluded_pair_count,
            "clashing_pair_count": self.clashing_pair_count,
            "minimum_distance_angstrom": self.minimum_distance_angstrom,
            "minimum_contact_ratio": self.minimum_contact_ratio,
            "minimum_contact_ratio_pair": (
                None
                if self.minimum_contact_ratio_pair is None
                else list(self.minimum_contact_ratio_pair)
            ),
            "maximum_overlap_angstrom": self.maximum_overlap_angstrom,
            "maximum_overlap_pair": (
                None
                if self.maximum_overlap_pair is None
                else list(self.maximum_overlap_pair)
            ),
        }


@dataclass(frozen=True)
class ReferenceDockingChargeDiagnostics:
    """Signed screened-Coulomb decomposition for cross pairs inside the cutoff."""

    evaluated_pair_count: int
    like_charge_pair_count: int
    opposite_charge_pair_count: int
    neutral_charge_pair_count: int
    signed_screened_coulomb_kcal_per_mol: float
    attractive_screened_coulomb_kcal_per_mol: float
    repulsive_screened_coulomb_kcal_per_mol: float
    maximum_repulsive_pair_kcal_per_mol: float
    maximum_repulsive_pair: tuple[int, int] | None

    def __post_init__(self) -> None:
        evaluated = _exact_int(self.evaluated_pair_count, name="evaluated_pair_count")
        like = _exact_int(self.like_charge_pair_count, name="like_charge_pair_count")
        opposite = _exact_int(
            self.opposite_charge_pair_count,
            name="opposite_charge_pair_count",
        )
        neutral = _exact_int(
            self.neutral_charge_pair_count,
            name="neutral_charge_pair_count",
        )
        if like + opposite + neutral != evaluated:
            raise ReferenceDockingScoringError(
                "charge-sign pair counts must equal evaluated_pair_count"
            )
        signed = _finite_float(
            self.signed_screened_coulomb_kcal_per_mol,
            name="signed_screened_coulomb_kcal_per_mol",
        )
        attractive = _finite_float(
            self.attractive_screened_coulomb_kcal_per_mol,
            name="attractive_screened_coulomb_kcal_per_mol",
        )
        repulsive = _finite_float(
            self.repulsive_screened_coulomb_kcal_per_mol,
            name="repulsive_screened_coulomb_kcal_per_mol",
            nonnegative=True,
        )
        maximum_repulsive = _finite_float(
            self.maximum_repulsive_pair_kcal_per_mol,
            name="maximum_repulsive_pair_kcal_per_mol",
            nonnegative=True,
        )
        if attractive > 0.0:
            raise ReferenceDockingScoringError(
                "attractive screened Coulomb contribution must be non-positive"
            )
        decomposition_error = abs(signed - (attractive + repulsive))
        decomposition_tolerance = 1.0e-12 * max(
            1.0,
            abs(attractive),
            abs(repulsive),
        )
        if decomposition_error > decomposition_tolerance:
            raise ReferenceDockingScoringError(
                "signed screened Coulomb must equal attractive plus repulsive"
            )
        maximum_pair = _diagnostic_pair(
            self.maximum_repulsive_pair,
            name="maximum_repulsive_pair",
            required=maximum_repulsive > 0.0,
        )
        if maximum_repulsive == 0.0 and maximum_pair is not None:
            raise ReferenceDockingScoringError(
                "zero maximum repulsion cannot identify a repulsive pair"
            )
        if maximum_repulsive > repulsive + 1.0e-12:
            raise ReferenceDockingScoringError(
                "maximum pair repulsion cannot exceed aggregate repulsion"
            )
        object.__setattr__(self, "evaluated_pair_count", evaluated)
        object.__setattr__(self, "like_charge_pair_count", like)
        object.__setattr__(self, "opposite_charge_pair_count", opposite)
        object.__setattr__(self, "neutral_charge_pair_count", neutral)
        object.__setattr__(
            self,
            "signed_screened_coulomb_kcal_per_mol",
            signed,
        )
        object.__setattr__(
            self,
            "attractive_screened_coulomb_kcal_per_mol",
            attractive,
        )
        object.__setattr__(
            self,
            "repulsive_screened_coulomb_kcal_per_mol",
            repulsive,
        )
        object.__setattr__(
            self,
            "maximum_repulsive_pair_kcal_per_mol",
            maximum_repulsive,
        )
        object.__setattr__(self, "maximum_repulsive_pair", maximum_pair)

    def to_dict(self) -> dict[str, object]:
        return {
            "evaluated_pair_count": self.evaluated_pair_count,
            "like_charge_pair_count": self.like_charge_pair_count,
            "opposite_charge_pair_count": self.opposite_charge_pair_count,
            "neutral_charge_pair_count": self.neutral_charge_pair_count,
            "signed_screened_coulomb_kcal_per_mol": (
                self.signed_screened_coulomb_kcal_per_mol
            ),
            "attractive_screened_coulomb_kcal_per_mol": (
                self.attractive_screened_coulomb_kcal_per_mol
            ),
            "repulsive_screened_coulomb_kcal_per_mol": (
                self.repulsive_screened_coulomb_kcal_per_mol
            ),
            "maximum_repulsive_pair_kcal_per_mol": (
                self.maximum_repulsive_pair_kcal_per_mol
            ),
            "maximum_repulsive_pair": (
                None
                if self.maximum_repulsive_pair is None
                else list(self.maximum_repulsive_pair)
            ),
        }


@dataclass(frozen=True)
class ReferenceDockingInteractionDiagnostics:
    """Identity-bound steric and charge observations used by pose validity."""

    candidate_id: str
    proposal_fingerprint_sha256: str
    pose_coordinate_sha256: str
    problem_fingerprint_sha256: str
    parameter_source_sha256: str
    config_fingerprint_sha256: str
    receptor_net_formal_charge_e: int
    ligand_net_formal_charge_e: int
    receptor_net_partial_charge_e: float
    ligand_net_partial_charge_e: float
    receptor_ligand_contacts: ReferenceDockingContactDiagnostics
    ligand_internal_contacts: ReferenceDockingContactDiagnostics
    receptor_ligand_charges: ReferenceDockingChargeDiagnostics
    receptor_ligand_vdw_overlap_penalty_kcal_per_mol: float
    schema_id: str = REFERENCE_DOCKING_INTERACTION_DIAGNOSTICS_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != REFERENCE_DOCKING_INTERACTION_DIAGNOSTICS_SCHEMA_ID:
            raise ReferenceDockingScoringError(
                "unsupported reference docking interaction diagnostics schema"
            )
        candidate_id = str(self.candidate_id or "").strip()
        if not candidate_id:
            raise ReferenceDockingScoringError("candidate_id must be non-empty")
        for name in (
            "proposal_fingerprint_sha256",
            "pose_coordinate_sha256",
            "problem_fingerprint_sha256",
            "parameter_source_sha256",
            "config_fingerprint_sha256",
        ):
            object.__setattr__(
                self,
                name,
                _required_sha256(getattr(self, name), name=name),
            )
        if (
            not isinstance(
                self.receptor_ligand_contacts,
                ReferenceDockingContactDiagnostics,
            )
            or self.receptor_ligand_contacts.scope != "receptor_ligand"
        ):
            raise ReferenceDockingScoringError(
                "receptor_ligand_contacts has the wrong scope"
            )
        if (
            not isinstance(
                self.ligand_internal_contacts,
                ReferenceDockingContactDiagnostics,
            )
            or self.ligand_internal_contacts.scope != "ligand_internal_nonbonded"
        ):
            raise ReferenceDockingScoringError(
                "ligand_internal_contacts has the wrong scope"
            )
        if not isinstance(
            self.receptor_ligand_charges,
            ReferenceDockingChargeDiagnostics,
        ):
            raise ReferenceDockingScoringError(
                "receptor_ligand_charges must be charge diagnostics"
            )
        object.__setattr__(
            self,
            "receptor_net_formal_charge_e",
            int(self.receptor_net_formal_charge_e),
        )
        object.__setattr__(
            self,
            "ligand_net_formal_charge_e",
            int(self.ligand_net_formal_charge_e),
        )
        object.__setattr__(
            self,
            "receptor_net_partial_charge_e",
            _finite_float(
                self.receptor_net_partial_charge_e,
                name="receptor_net_partial_charge_e",
            ),
        )
        object.__setattr__(
            self,
            "ligand_net_partial_charge_e",
            _finite_float(
                self.ligand_net_partial_charge_e,
                name="ligand_net_partial_charge_e",
            ),
        )
        overlap_penalty = _finite_float(
            self.receptor_ligand_vdw_overlap_penalty_kcal_per_mol,
            name="receptor_ligand_vdw_overlap_penalty_kcal_per_mol",
            nonnegative=True,
        )
        if (
            self.receptor_ligand_contacts.clashing_pair_count == 0
            and overlap_penalty != 0.0
        ):
            raise ReferenceDockingScoringError(
                "cross overlap penalty requires at least one clashing pair"
            )
        object.__setattr__(self, "candidate_id", candidate_id)
        object.__setattr__(
            self,
            "receptor_ligand_vdw_overlap_penalty_kcal_per_mol",
            overlap_penalty,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "candidate_id": self.candidate_id,
            "proposal_fingerprint_sha256": self.proposal_fingerprint_sha256,
            "pose_coordinate_sha256": self.pose_coordinate_sha256,
            "problem_fingerprint_sha256": self.problem_fingerprint_sha256,
            "parameter_source_sha256": self.parameter_source_sha256,
            "config_fingerprint_sha256": self.config_fingerprint_sha256,
            "receptor_net_formal_charge_e": self.receptor_net_formal_charge_e,
            "ligand_net_formal_charge_e": self.ligand_net_formal_charge_e,
            "receptor_net_partial_charge_e": self.receptor_net_partial_charge_e,
            "ligand_net_partial_charge_e": self.ligand_net_partial_charge_e,
            "receptor_ligand_contacts": self.receptor_ligand_contacts.to_dict(),
            "ligand_internal_contacts": self.ligand_internal_contacts.to_dict(),
            "receptor_ligand_charges": self.receptor_ligand_charges.to_dict(),
            "receptor_ligand_vdw_overlap_penalty_kcal_per_mol": (
                self.receptor_ligand_vdw_overlap_penalty_kcal_per_mol
            ),
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
    if (
        system.coordinates.dtype != torch.float64
        or system.coordinates.device.type != "cpu"
    ):
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
        1.0 - 10.0 * fraction.pow(3) + 15.0 * fraction.pow(4) - 6.0 * fraction.pow(5)
    )
    return torch.where(
        distance <= start,
        torch.ones_like(distance),
        torch.where(distance < cutoff, smooth, torch.zeros_like(distance)),
    )


def _contact_diagnostics(
    *,
    scope: str,
    pairs: tuple[tuple[int, int], ...],
    distance: torch.Tensor,
    contact_distance: torch.Tensor,
    total_pair_count: int,
    excluded_pair_count: int,
) -> ReferenceDockingContactDiagnostics:
    evaluated_pair_count = len(pairs)
    if distance.shape != (evaluated_pair_count,) or contact_distance.shape != (
        evaluated_pair_count,
    ):
        raise ReferenceDockingScoringError(
            "contact diagnostic vectors do not match evaluated pairs"
        )
    if evaluated_pair_count == 0:
        return ReferenceDockingContactDiagnostics(
            scope=scope,
            total_pair_count=total_pair_count,
            evaluated_pair_count=0,
            excluded_pair_count=excluded_pair_count,
            clashing_pair_count=0,
            minimum_distance_angstrom=None,
            minimum_contact_ratio=None,
            minimum_contact_ratio_pair=None,
            maximum_overlap_angstrom=0.0,
            maximum_overlap_pair=None,
        )
    overlap = torch.clamp(contact_distance - distance, min=0.0)
    ratios = distance / contact_distance
    minimum_ratio_index = int(torch.argmin(ratios).item())
    maximum_overlap_index = int(torch.argmax(overlap).item())
    maximum_overlap = float(overlap[maximum_overlap_index].item())
    return ReferenceDockingContactDiagnostics(
        scope=scope,
        total_pair_count=total_pair_count,
        evaluated_pair_count=evaluated_pair_count,
        excluded_pair_count=excluded_pair_count,
        clashing_pair_count=int((overlap > 0.0).sum().item()),
        minimum_distance_angstrom=float(torch.min(distance).item()),
        minimum_contact_ratio=float(ratios[minimum_ratio_index].item()),
        minimum_contact_ratio_pair=pairs[minimum_ratio_index],
        maximum_overlap_angstrom=maximum_overlap,
        maximum_overlap_pair=(
            pairs[maximum_overlap_index] if maximum_overlap > 0.0 else None
        ),
    )


@dataclass(frozen=True)
class _CrossTermEvaluation:
    lennard_jones_kcal_per_mol: float
    screened_coulomb_kcal_per_mol: float
    vdw_overlap_penalty_kcal_per_mol: float
    full_distance: torch.Tensor
    receptor_indices: torch.Tensor
    ligand_indices: torch.Tensor
    raw_distance: torch.Tensor
    sigma: torch.Tensor
    charge_product: torch.Tensor
    pair_electrostatic: torch.Tensor


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

    def _evaluate_cross_terms(
        self,
        ligand_coordinates: torch.Tensor,
    ) -> _CrossTermEvaluation:
        receptor_coordinates = self.receptor_system.coordinates[0]
        delta = receptor_coordinates[:, None, :] - ligand_coordinates[None, :, :]
        full_distance = torch.linalg.vector_norm(delta, dim=-1)
        selected = full_distance < self.config.cutoff_angstrom
        receptor_indices, ligand_indices = torch.nonzero(selected, as_tuple=True)
        raw_distance = full_distance[receptor_indices, ligand_indices]
        if int(raw_distance.numel()) == 0:
            empty_float = torch.empty((0,), dtype=torch.float64)
            return _CrossTermEvaluation(
                lennard_jones_kcal_per_mol=0.0,
                screened_coulomb_kcal_per_mol=0.0,
                vdw_overlap_penalty_kcal_per_mol=0.0,
                full_distance=full_distance,
                receptor_indices=receptor_indices,
                ligand_indices=ligand_indices,
                raw_distance=raw_distance,
                sigma=empty_float,
                charge_product=empty_float,
                pair_electrostatic=empty_float,
            )
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
                math.sqrt(receptor.epsilon_kcal_per_mol * ligand.epsilon_kcal_per_mol)
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
        pair_lennard_jones = 4.0 * epsilon * (ratio6.pow(2) - ratio6) * switching
        pair_electrostatic = (
            COULOMB_KCAL_ANGSTROM_PER_MOL_E2
            * charge_product
            * torch.exp(-self.config.screening_kappa_per_angstrom * raw_distance)
            / (self.config.dielectric * effective_distance)
            * switching
        )
        contact_distance = (
            self.config.clash_contact_scale * (2.0 ** (1.0 / 6.0)) * sigma
        )
        overlap = torch.clamp(contact_distance - raw_distance, min=0.0)
        clash = (
            self.config.clash_force_constant_kcal_per_mol_angstrom2 * overlap.square()
        ).sum()
        return _CrossTermEvaluation(
            lennard_jones_kcal_per_mol=float(pair_lennard_jones.sum().item()),
            screened_coulomb_kcal_per_mol=float(pair_electrostatic.sum().item()),
            vdw_overlap_penalty_kcal_per_mol=float(clash.item()),
            full_distance=full_distance,
            receptor_indices=receptor_indices,
            ligand_indices=ligand_indices,
            raw_distance=raw_distance,
            sigma=sigma,
            charge_product=charge_product,
            pair_electrostatic=pair_electrostatic,
        )

    def _cross_contact_diagnostics(
        self,
        evaluation: _CrossTermEvaluation,
    ) -> ReferenceDockingContactDiagnostics:
        receptor_count = self.receptor_system.atom_count
        ligand_count = self.ligand_system.atom_count
        receptor_indices = torch.arange(
            receptor_count,
            dtype=torch.long,
        ).repeat_interleave(ligand_count)
        ligand_indices = torch.arange(
            ligand_count,
            dtype=torch.long,
        ).repeat(receptor_count)
        receptor_rows = [
            self._receptor_parameter_map[int(index)]
            for index in receptor_indices.tolist()
        ]
        ligand_rows = [
            self._ligand_parameter_map[int(index)] for index in ligand_indices.tolist()
        ]
        sigma = torch.tensor(
            [
                0.5 * (receptor.sigma_angstrom + ligand.sigma_angstrom)
                for receptor, ligand in zip(receptor_rows, ligand_rows)
            ],
            dtype=torch.float64,
        )
        contact_distance = (
            self.config.clash_contact_scale * (2.0 ** (1.0 / 6.0)) * sigma
        )
        pairs = tuple(
            (int(receptor), int(ligand))
            for receptor, ligand in zip(
                receptor_indices.tolist(),
                ligand_indices.tolist(),
            )
        )
        return _contact_diagnostics(
            scope="receptor_ligand",
            pairs=pairs,
            distance=evaluation.full_distance.reshape(-1),
            contact_distance=contact_distance,
            total_pair_count=receptor_count * ligand_count,
            excluded_pair_count=0,
        )

    def _cross_charge_diagnostics(
        self,
        evaluation: _CrossTermEvaluation,
    ) -> ReferenceDockingChargeDiagnostics:
        repulsive_values = evaluation.pair_electrostatic[
            evaluation.pair_electrostatic > 0.0
        ]
        attractive_values = evaluation.pair_electrostatic[
            evaluation.pair_electrostatic < 0.0
        ]
        maximum_repulsive = (
            float(torch.max(repulsive_values).item())
            if int(repulsive_values.numel()) > 0
            else 0.0
        )
        maximum_repulsive_pair: tuple[int, int] | None = None
        if maximum_repulsive > 0.0:
            pair_index = int(torch.argmax(evaluation.pair_electrostatic).item())
            maximum_repulsive_pair = (
                int(evaluation.receptor_indices[pair_index].item()),
                int(evaluation.ligand_indices[pair_index].item()),
            )
        return ReferenceDockingChargeDiagnostics(
            evaluated_pair_count=int(evaluation.raw_distance.numel()),
            like_charge_pair_count=int((evaluation.charge_product > 0.0).sum().item()),
            opposite_charge_pair_count=int(
                (evaluation.charge_product < 0.0).sum().item()
            ),
            neutral_charge_pair_count=int(
                (evaluation.charge_product == 0.0).sum().item()
            ),
            signed_screened_coulomb_kcal_per_mol=(
                evaluation.screened_coulomb_kcal_per_mol
            ),
            attractive_screened_coulomb_kcal_per_mol=float(
                attractive_values.sum().item()
            ),
            repulsive_screened_coulomb_kcal_per_mol=float(
                repulsive_values.sum().item()
            ),
            maximum_repulsive_pair_kcal_per_mol=maximum_repulsive,
            maximum_repulsive_pair=maximum_repulsive_pair,
        )

    def _ligand_internal_contacts(
        self,
        ligand_coordinates: torch.Tensor,
    ) -> ReferenceDockingContactDiagnostics:
        atom_count = self.ligand_system.atom_count
        total_pair_count = atom_count * (atom_count - 1) // 2
        excluded = set(self.ligand_parameters.excluded_pairs)
        pairs = tuple(
            (first, second)
            for first in range(atom_count)
            for second in range(first + 1, atom_count)
            if (first, second) not in excluded
        )
        if not pairs:
            empty = torch.empty((0,), dtype=torch.float64)
            return _contact_diagnostics(
                scope="ligand_internal_nonbonded",
                pairs=(),
                distance=empty,
                contact_distance=empty,
                total_pair_count=total_pair_count,
                excluded_pair_count=total_pair_count,
            )
        first_indices = torch.tensor(
            [pair[0] for pair in pairs],
            dtype=torch.long,
        )
        second_indices = torch.tensor(
            [pair[1] for pair in pairs],
            dtype=torch.long,
        )
        distance = torch.linalg.vector_norm(
            ligand_coordinates.index_select(0, first_indices)
            - ligand_coordinates.index_select(0, second_indices),
            dim=1,
        )
        sigma = torch.tensor(
            [
                0.5
                * (
                    self._ligand_parameter_map[first].sigma_angstrom
                    + self._ligand_parameter_map[second].sigma_angstrom
                )
                for first, second in pairs
            ],
            dtype=torch.float64,
        )
        contact_distance = (
            self.config.clash_contact_scale * (2.0 ** (1.0 / 6.0)) * sigma
        )
        return _contact_diagnostics(
            scope="ligand_internal_nonbonded",
            pairs=pairs,
            distance=distance,
            contact_distance=contact_distance,
            total_pair_count=total_pair_count,
            excluded_pair_count=total_pair_count - len(pairs),
        )

    def _validate_proposal(self, proposal: DockingProposal) -> None:
        if not isinstance(proposal, DockingProposal):
            raise ReferenceDockingScoringError("proposal must be a DockingProposal")
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

    def _score_components(
        self,
        proposal: DockingProposal,
    ) -> tuple[DockingScoreBreakdown, _CrossTermEvaluation]:
        self._validate_proposal(proposal)
        candidate_system = self.ligand_system.with_coordinates(
            proposal.coordinates.unsqueeze(0),
            operation=f"uncalibrated_docking_score:{proposal.candidate_id}",
        )
        candidate_energy = _ligand_energy(
            candidate_system,
            self.ligand_parameters,
        )
        strain_delta = candidate_energy - self._ligand_reference_energy
        cross_evaluation = self._evaluate_cross_terms(proposal.coordinates)
        breakdown = DockingScoreBreakdown(
            terms=(
                DockingScoreTerm(
                    term_id="receptor_ligand_lennard_jones",
                    raw_value=cross_evaluation.lennard_jones_kcal_per_mol,
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
                    raw_value=cross_evaluation.screened_coulomb_kcal_per_mol,
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
                    raw_value=cross_evaluation.vdw_overlap_penalty_kcal_per_mol,
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
        return breakdown, cross_evaluation

    def score_with_diagnostics(
        self,
        proposal: DockingProposal,
    ) -> tuple[DockingScoreBreakdown, ReferenceDockingInteractionDiagnostics]:
        """Return one atomic score/interaction observation for an exact proposal."""

        breakdown, cross_evaluation = self._score_components(proposal)
        cross_contacts = self._cross_contact_diagnostics(cross_evaluation)
        charge_diagnostics = self._cross_charge_diagnostics(cross_evaluation)
        ligand_contacts = self._ligand_internal_contacts(proposal.coordinates)
        diagnostics = ReferenceDockingInteractionDiagnostics(
            candidate_id=proposal.candidate_id,
            proposal_fingerprint_sha256=proposal.fingerprint_sha256,
            pose_coordinate_sha256=coordinate_fingerprint(proposal.coordinates),
            problem_fingerprint_sha256=self.problem.fingerprint_sha256,
            parameter_source_sha256=self.parameter_source_sha256,
            config_fingerprint_sha256=self.config_fingerprint_sha256,
            receptor_net_formal_charge_e=sum(
                atom.formal_charge for atom in self.receptor_system.atoms
            ),
            ligand_net_formal_charge_e=sum(
                atom.formal_charge for atom in self.ligand_system.atoms
            ),
            receptor_net_partial_charge_e=math.fsum(
                row.charge_e for row in self._receptor_parameter_map.values()
            ),
            ligand_net_partial_charge_e=math.fsum(
                row.charge_e for row in self._ligand_parameter_map.values()
            ),
            receptor_ligand_contacts=cross_contacts,
            ligand_internal_contacts=ligand_contacts,
            receptor_ligand_charges=charge_diagnostics,
            receptor_ligand_vdw_overlap_penalty_kcal_per_mol=(
                cross_evaluation.vdw_overlap_penalty_kcal_per_mol
            ),
        )
        return breakdown, diagnostics

    def interaction_diagnostics(
        self,
        proposal: DockingProposal,
    ) -> ReferenceDockingInteractionDiagnostics:
        return self.score_with_diagnostics(proposal)[1]

    def score(self, proposal: DockingProposal) -> DockingScoreBreakdown:
        return self._score_components(proposal)[0]


__all__ = [
    "DEFAULT_SUPPORTED_DOCKING_ATOMIC_NUMBERS",
    "REFERENCE_DOCKING_INTERACTION_DIAGNOSTICS_SCHEMA_ID",
    "REFERENCE_DOCKING_SCORER_SCHEMA_ID",
    "ReferenceDockingChargeDiagnostics",
    "ReferenceDockingChemistryScope",
    "ReferenceDockingContactDiagnostics",
    "ReferenceDockingInteractionDiagnostics",
    "ReferenceDockingScoreConfig",
    "ReferenceDockingScoringError",
    "UncalibratedReferenceDockingScorer",
]
