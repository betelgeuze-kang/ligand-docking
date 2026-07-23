"""Identity-bound applicability and abstention for reference docking.

The existing reference scorer remains an exception-based low-level API.  This
module provides a failure-inclusive boundary that inventories every detectable
input, chemistry, parameter, and execution blocker before constructing that
scorer.  Admission means only that the bounded uncalibrated diagnostic can run;
it is not a scientific chemical-applicability or docking-validity claim.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
import math
from typing import Any

import torch

from betelgeuze_engine_v2.geometry import NeighborOverflowError
from betelgeuze_engine_v2.molecular import (
    AllAtomSystem,
    canonical_system_sha256,
    canonical_topology_sha256,
    element_for_atomic_number,
    validate_all_atom_system,
)
from betelgeuze_engine_v2.physics import (
    ReferenceForceFieldParameters,
    ReferencePhysicsApplicabilityError,
)

from .identity import DockingProblemIdentity
from .reference_scoring import (
    ReferenceDockingScoreConfig,
    ReferenceDockingScoringError,
    UncalibratedReferenceDockingScorer,
)


REFERENCE_DOCKING_APPLICABILITY_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_docking_applicability/1.0.0"
)
REFERENCE_DOCKING_APPLICABILITY_PROFILE_ID = (
    "uncalibrated_explicit_parameter_reference_docking_admission/1.0.0"
)

REFERENCE_DOCKING_APPLICABILITY_DISPOSITIONS = (
    "admitted_diagnostic",
    "invalid_input",
    "abstain_chemistry_scope",
    "abstain_parameter_scope",
    "abstain_execution_scope",
)

# Frozen operational policy shared with the public PoseBusters chemistry audit.
# This is an applicability set, not a claim about disputed periodic-table
# classifications.
REFERENCE_DOCKING_METAL_ATOMIC_NUMBERS = tuple(
    sorted(
        {
            3,
            4,
            11,
            12,
            13,
            19,
            20,
            *range(21, 32),
            37,
            38,
            *range(39, 51),
            55,
            56,
            *range(57, 84),
            87,
            88,
            *range(89, 113),
        }
    )
)
_METAL_ATOMIC_NUMBERS = frozenset(REFERENCE_DOCKING_METAL_ATOMIC_NUMBERS)
_UNSPECIFIED_STEREO = {"", "NONE", "UNKNOWN", "UNSPECIFIED"}

REFERENCE_DOCKING_APPLICABILITY_SCIENTIFIC_BLOCKERS = (
    "reference_docking_score_uncalibrated",
    "caller_supplied_parameter_values_not_independently_validated",
    "scientific_chemical_applicability_domain_not_established",
    "public_docking_benchmark_missing",
    "independent_external_rerun_missing",
)


def _canonical_sha256(payload: object) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _unique(values: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def _safe_system_sha256(system: AllAtomSystem) -> str | None:
    try:
        return canonical_system_sha256(system)
    except (TypeError, ValueError, RuntimeError):
        return None


def _safe_topology_sha256(system: AllAtomSystem) -> str | None:
    try:
        return canonical_topology_sha256(system)
    except (TypeError, ValueError, RuntimeError):
        return None


def _bonded_topology_paths(
    atom_count: int,
    bond_pairs: tuple[tuple[int, int], ...],
) -> tuple[set[tuple[int, int, int]], set[tuple[int, int, int, int]]]:
    adjacency = {index: set() for index in range(atom_count)}
    for atom_i, atom_j in bond_pairs:
        adjacency[atom_i].add(atom_j)
        adjacency[atom_j].add(atom_i)

    angles: set[tuple[int, int, int]] = set()
    for center, neighbors in adjacency.items():
        ordered = sorted(neighbors)
        for offset, atom_i in enumerate(ordered):
            for atom_k in ordered[offset + 1 :]:
                angles.add((atom_i, center, atom_k))

    torsions: set[tuple[int, int, int, int]] = set()
    for atom_j, atom_k in sorted(set(bond_pairs)):
        for atom_i in adjacency[atom_j] - {atom_k}:
            for atom_l in adjacency[atom_k] - {atom_j}:
                forward = (atom_i, atom_j, atom_k, atom_l)
                if len(set(forward)) == 4:
                    torsions.add(min(forward, tuple(reversed(forward))))
    return angles, torsions


def _ligand_parameter_topology_blockers(
    system: AllAtomSystem,
    parameters: ReferenceForceFieldParameters,
) -> tuple[str, ...]:
    role = "ligand"
    atom_count = system.atom_count
    blockers: list[str] = []

    for label, rows in (
        ("bond", ((row.atom_i, row.atom_j) for row in parameters.bonds)),
        (
            "angle",
            ((row.atom_i, row.atom_j, row.atom_k) for row in parameters.angles),
        ),
        (
            "torsion",
            (
                (row.atom_i, row.atom_j, row.atom_k, row.atom_l)
                for row in parameters.torsions
            ),
        ),
        ("excluded_pair", parameters.excluded_pairs),
        (
            "scaled_pair",
            ((row.atom_i, row.atom_j) for row in parameters.scaled_pairs),
        ),
    ):
        if any(any(index < 0 or index >= atom_count for index in row) for row in rows):
            blockers.append(f"{role}_{label}_parameter_index_out_of_range")

    system_bonds = tuple(
        tuple(sorted((int(row.atom_i), int(row.atom_j)))) for row in system.bonds
    )
    if all(
        0 <= atom_i < atom_count and 0 <= atom_j < atom_count and atom_i != atom_j
        for atom_i, atom_j in system_bonds
    ):
        parameter_bonds = {(row.atom_i, row.atom_j) for row in parameters.bonds}
        if set(system_bonds) != parameter_bonds:
            blockers.append("ligand_bond_parameter_coverage_mismatch")
        else:
            expected_angles, expected_torsions = _bonded_topology_paths(
                atom_count,
                system_bonds,
            )
            parameter_angles = {
                (
                    min(row.atom_i, row.atom_k),
                    row.atom_j,
                    max(row.atom_i, row.atom_k),
                )
                for row in parameters.angles
            }
            parameter_torsions = {
                min(
                    (row.atom_i, row.atom_j, row.atom_k, row.atom_l),
                    (row.atom_l, row.atom_k, row.atom_j, row.atom_i),
                )
                for row in parameters.torsions
            }
            if parameter_angles != expected_angles:
                blockers.append("ligand_angle_parameter_coverage_mismatch")
            if parameter_torsions != expected_torsions:
                blockers.append("ligand_torsion_parameter_coverage_mismatch")

    domain = parameters.applicability_domain
    for code, count, maximum in (
        ("atom", atom_count, domain.max_atoms),
        ("bond", len(parameters.bonds), domain.max_bonds),
        ("angle", len(parameters.angles), domain.max_angles),
        ("torsion", len(parameters.torsions), domain.max_torsions),
    ):
        if count > maximum:
            blockers.append(f"ligand_{code}_count_outside_parameter_domain")
    return _unique(blockers)


@dataclass(frozen=True, slots=True)
class ReferenceDockingNonpolymerResidue:
    residue_index: int
    residue_name: str
    entity_type: str

    def to_dict(self) -> dict[str, object]:
        return {
            "residue_index": self.residue_index,
            "residue_name": self.residue_name,
            "entity_type": self.entity_type,
        }


@dataclass(frozen=True, slots=True)
class ReferenceDockingSystemApplicability:
    """Complete role-specific inventory used by the admission decision."""

    role: str
    system_sha256: str | None
    topology_sha256: str | None
    parameter_fingerprint_sha256: str | None
    atom_count: int
    model_count: int
    coordinate_dtype: str
    coordinate_device: str
    periodic_cell_present: bool
    validation_error_codes: tuple[str, ...]
    unsupported_atom_indices: tuple[int, ...]
    unsupported_atomic_numbers: tuple[int, ...]
    unsupported_elements: tuple[str, ...]
    metal_atom_indices: tuple[int, ...]
    metal_atomic_numbers: tuple[int, ...]
    formal_charge_outlier_atom_indices: tuple[int, ...]
    missing_partial_charge_atom_indices: tuple[int, ...]
    mismatched_partial_charge_atom_indices: tuple[int, ...]
    missing_parameter_atom_indices: tuple[int, ...]
    extra_parameter_atom_indices: tuple[int, ...]
    receptor_nonpolymer_residues: tuple[ReferenceDockingNonpolymerResidue, ...]
    aromatic_atom_indices: tuple[int, ...]
    aromatic_bond_indices: tuple[int, ...]
    declared_atom_stereo_indices: tuple[int, ...]
    declared_bond_stereo_indices: tuple[int, ...]
    invalid_input_blockers: tuple[str, ...]
    chemistry_scope_blockers: tuple[str, ...]
    parameter_scope_blockers: tuple[str, ...]
    execution_scope_blockers: tuple[str, ...]
    interaction_coverage_blockers: tuple[str, ...]

    @property
    def admission_blockers(self) -> tuple[str, ...]:
        return _unique(
            [
                *self.invalid_input_blockers,
                *self.chemistry_scope_blockers,
                *self.parameter_scope_blockers,
                *self.execution_scope_blockers,
            ]
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "role": self.role,
            "system_sha256": self.system_sha256,
            "topology_sha256": self.topology_sha256,
            "parameter_fingerprint_sha256": self.parameter_fingerprint_sha256,
            "atom_count": self.atom_count,
            "model_count": self.model_count,
            "coordinate_dtype": self.coordinate_dtype,
            "coordinate_device": self.coordinate_device,
            "periodic_cell_present": self.periodic_cell_present,
            "validation_error_codes": list(self.validation_error_codes),
            "unsupported_atom_indices": list(self.unsupported_atom_indices),
            "unsupported_atomic_numbers": list(self.unsupported_atomic_numbers),
            "unsupported_elements": list(self.unsupported_elements),
            "metal_atom_indices": list(self.metal_atom_indices),
            "metal_atomic_numbers": list(self.metal_atomic_numbers),
            "formal_charge_outlier_atom_indices": list(
                self.formal_charge_outlier_atom_indices
            ),
            "missing_partial_charge_atom_indices": list(
                self.missing_partial_charge_atom_indices
            ),
            "mismatched_partial_charge_atom_indices": list(
                self.mismatched_partial_charge_atom_indices
            ),
            "missing_parameter_atom_indices": list(self.missing_parameter_atom_indices),
            "extra_parameter_atom_indices": list(self.extra_parameter_atom_indices),
            "receptor_nonpolymer_residues": [
                row.to_dict() for row in self.receptor_nonpolymer_residues
            ],
            "aromatic_atom_indices": list(self.aromatic_atom_indices),
            "aromatic_bond_indices": list(self.aromatic_bond_indices),
            "declared_atom_stereo_indices": list(self.declared_atom_stereo_indices),
            "declared_bond_stereo_indices": list(self.declared_bond_stereo_indices),
            "invalid_input_blockers": list(self.invalid_input_blockers),
            "chemistry_scope_blockers": list(self.chemistry_scope_blockers),
            "parameter_scope_blockers": list(self.parameter_scope_blockers),
            "execution_scope_blockers": list(self.execution_scope_blockers),
            "interaction_coverage_blockers": list(self.interaction_coverage_blockers),
            "admission_blockers": list(self.admission_blockers),
        }


@dataclass(frozen=True, slots=True)
class ReferenceDockingApplicabilityAssessment:
    """Immutable disposition for one exact receptor/ligand/parameter problem."""

    disposition: str
    problem_fingerprint_sha256: str
    config_fingerprint_sha256: str
    parameter_source_sha256: str | None
    receptor: ReferenceDockingSystemApplicability
    ligand: ReferenceDockingSystemApplicability
    invalid_input_blockers: tuple[str, ...]
    chemistry_scope_blockers: tuple[str, ...]
    parameter_scope_blockers: tuple[str, ...]
    execution_scope_blockers: tuple[str, ...]
    interaction_coverage_blockers: tuple[str, ...]
    diagnostic_scorer_admitted: bool
    interaction_coverage_complete: bool
    ood_detected: bool
    scientifically_validated: bool = False
    claim_safe: bool = False
    schema_id: str = REFERENCE_DOCKING_APPLICABILITY_SCHEMA_ID
    profile_id: str = REFERENCE_DOCKING_APPLICABILITY_PROFILE_ID

    def __post_init__(self) -> None:
        if self.disposition not in REFERENCE_DOCKING_APPLICABILITY_DISPOSITIONS:
            raise ValueError("unsupported reference docking applicability disposition")
        expected_disposition = _disposition(
            invalid=self.invalid_input_blockers,
            chemistry=self.chemistry_scope_blockers,
            parameter=self.parameter_scope_blockers,
            execution=self.execution_scope_blockers,
        )
        if self.disposition != expected_disposition:
            raise ValueError("applicability disposition/blocker mismatch")
        expected_admission = self.disposition == "admitted_diagnostic"
        if self.diagnostic_scorer_admitted != expected_admission:
            raise ValueError("applicability disposition/admission mismatch")
        if self.interaction_coverage_complete != (
            not self.chemistry_scope_blockers and not self.interaction_coverage_blockers
        ):
            raise ValueError("interaction coverage flag/scope mismatch")
        if self.ood_detected != bool(
            self.chemistry_scope_blockers or self.interaction_coverage_blockers
        ):
            raise ValueError("OOD flag/blocker mismatch")
        if self.scientifically_validated or self.claim_safe:
            raise ValueError("reference docking applicability cannot promote claims")

    @property
    def admission_blockers(self) -> tuple[str, ...]:
        return _unique(
            [
                *self.invalid_input_blockers,
                *self.chemistry_scope_blockers,
                *self.parameter_scope_blockers,
                *self.execution_scope_blockers,
            ]
        )

    @property
    def all_blockers(self) -> tuple[str, ...]:
        return _unique(
            [
                *self.admission_blockers,
                *self.interaction_coverage_blockers,
                *REFERENCE_DOCKING_APPLICABILITY_SCIENTIFIC_BLOCKERS,
            ]
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "profile_id": self.profile_id,
            "disposition": self.disposition,
            "problem_fingerprint_sha256": self.problem_fingerprint_sha256,
            "config_fingerprint_sha256": self.config_fingerprint_sha256,
            "parameter_source_sha256": self.parameter_source_sha256,
            "receptor": self.receptor.to_dict(),
            "ligand": self.ligand.to_dict(),
            "invalid_input_blockers": list(self.invalid_input_blockers),
            "chemistry_scope_blockers": list(self.chemistry_scope_blockers),
            "parameter_scope_blockers": list(self.parameter_scope_blockers),
            "execution_scope_blockers": list(self.execution_scope_blockers),
            "admission_blockers": list(self.admission_blockers),
            "interaction_coverage_blockers": list(self.interaction_coverage_blockers),
            "interaction_coverage_complete": self.interaction_coverage_complete,
            "ood_detected": self.ood_detected,
            "diagnostic_scorer_admitted": self.diagnostic_scorer_admitted,
            "scientific_blockers": list(
                REFERENCE_DOCKING_APPLICABILITY_SCIENTIFIC_BLOCKERS
            ),
            "all_blockers": list(self.all_blockers),
            "scientifically_validated": False,
            "validated_refinement_allowed": False,
            "claim_safe": False,
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())


@dataclass(frozen=True, slots=True)
class ReferenceDockingScorerAdmission:
    """Assessment plus the scorer only when diagnostic execution is admitted."""

    assessment: ReferenceDockingApplicabilityAssessment
    scorer: UncalibratedReferenceDockingScorer | None

    def __post_init__(self) -> None:
        if (self.scorer is not None) != self.assessment.diagnostic_scorer_admitted:
            raise ValueError(
                "scorer presence must exactly match applicability admission"
            )

    @property
    def admitted(self) -> bool:
        return self.scorer is not None


def _role_assessment(
    system: AllAtomSystem,
    parameters: ReferenceForceFieldParameters | None,
    *,
    role: str,
    config: ReferenceDockingScoreConfig,
) -> ReferenceDockingSystemApplicability:
    system_sha256 = _safe_system_sha256(system)
    topology_sha256 = _safe_topology_sha256(system)
    validation = validate_all_atom_system(system)
    validation_error_codes = _unique([row.code for row in validation.errors])

    invalid = [f"{role}_system_validation_{code}" for code in validation_error_codes]
    if system_sha256 is None:
        invalid.append(f"{role}_system_identity_unavailable")
    if topology_sha256 is None:
        invalid.append(f"{role}_topology_identity_unavailable")

    chemistry_scope = config.chemistry_scope
    unsupported_atoms = tuple(
        atom.index
        for atom in system.atoms
        if atom.atomic_number not in chemistry_scope.supported_atomic_numbers
    )
    unsupported_numbers = tuple(
        sorted(
            {
                atom.atomic_number
                for atom in system.atoms
                if atom.atomic_number not in chemistry_scope.supported_atomic_numbers
            }
        )
    )
    unsupported_elements = tuple(
        sorted(
            {
                (
                    element_for_atomic_number(number)
                    if 1 <= number <= 118
                    else next(
                        atom.element
                        for atom in system.atoms
                        if atom.atomic_number == number
                    )
                )
                for number in unsupported_numbers
            }
        )
    )
    metal_atoms = tuple(
        atom.index
        for atom in system.atoms
        if atom.atomic_number in _METAL_ATOMIC_NUMBERS
    )
    metal_numbers = tuple(
        sorted(
            {
                atom.atomic_number
                for atom in system.atoms
                if atom.atomic_number in _METAL_ATOMIC_NUMBERS
            }
        )
    )
    formal_charge_outliers = tuple(
        atom.index
        for atom in system.atoms
        if abs(atom.formal_charge) > chemistry_scope.maximum_absolute_formal_charge
    )
    nonpolymer = (
        tuple(
            ReferenceDockingNonpolymerResidue(
                residue_index=row.index,
                residue_name=row.name,
                entity_type=row.entity_type,
            )
            for row in system.residues
            if row.entity_type.strip().lower() != "polymer"
        )
        if role == "receptor"
        else ()
    )

    chemistry: list[str] = []
    if metal_atoms:
        chemistry.append(f"{role}_metal_coordination_unsupported")
    if unsupported_atoms:
        chemistry.append(f"{role}_unsupported_atomic_numbers")
    if formal_charge_outliers:
        chemistry.append(f"{role}_formal_charge_outside_scope")
    if (
        role == "receptor"
        and nonpolymer
        and not chemistry_scope.allow_receptor_nonpolymer_residues
    ):
        chemistry.append("receptor_nonpolymer_cofactor_outside_scope")

    parameter_fingerprint = (
        None if parameters is None else parameters.fingerprint_sha256
    )
    missing_partial = tuple(
        atom.index for atom in system.atoms if atom.partial_charge_e is None
    )
    parameter_map = {} if parameters is None else parameters.atom_parameter_map
    expected_indices = set(range(system.atom_count))
    parameter_indices = set(parameter_map)
    missing_parameters = tuple(sorted(expected_indices - parameter_indices))
    extra_parameters = tuple(sorted(parameter_indices - expected_indices))
    mismatched_partial = tuple(
        atom.index
        for atom in system.atoms
        if atom.partial_charge_e is not None
        and atom.index in parameter_map
        and not math.isclose(
            float(atom.partial_charge_e),
            parameter_map[atom.index].charge_e,
            rel_tol=0.0,
            abs_tol=1.0e-12,
        )
    )

    parameter_blockers: list[str] = []
    if parameters is None:
        parameter_blockers.append(f"{role}_parameters_missing")
    else:
        if (
            topology_sha256 is not None
            and parameters.topology_sha256 != topology_sha256
        ):
            parameter_blockers.append(f"{role}_parameter_topology_identity_mismatch")
        if missing_parameters:
            parameter_blockers.append(f"{role}_nonbonded_parameter_coverage_missing")
        if extra_parameters:
            parameter_blockers.append(f"{role}_nonbonded_parameter_coverage_extra")
        if config.cutoff_angstrom > parameters.cutoff_angstrom:
            parameter_blockers.append(
                f"{role}_parameter_cutoff_shorter_than_docking_cutoff"
            )
        if role == "ligand":
            parameter_blockers.extend(
                _ligand_parameter_topology_blockers(system, parameters)
            )
    if chemistry_scope.require_partial_charge_parameter_match:
        if missing_partial:
            parameter_blockers.append(f"{role}_partial_charge_missing")
        if mismatched_partial:
            parameter_blockers.append(f"{role}_partial_charge_parameter_mismatch")

    execution: list[str] = []
    if system.model_count != 1:
        execution.append(f"{role}_model_count_not_one")
    if (
        system.coordinates.dtype != torch.float64
        or system.coordinates.device.type != "cpu"
    ):
        execution.append(f"{role}_coordinates_not_cpu_float64")
    if system.cell is not None:
        execution.append(f"{role}_periodic_cell_outside_scope")
    if role == "ligand" and system.atom_count > config.max_ligand_atoms:
        execution.append("ligand_atom_capacity_exceeded")

    aromatic_atoms = tuple(atom.index for atom in system.atoms if atom.aromatic)
    aromatic_bonds = tuple(bond.index for bond in system.bonds if bond.aromatic)
    declared_atom_stereo = tuple(
        atom.index
        for atom in system.atoms
        if atom.stereo.strip().upper() not in _UNSPECIFIED_STEREO
    )
    declared_bond_stereo = tuple(
        bond.index
        for bond in system.bonds
        if bond.stereo.strip().upper() not in _UNSPECIFIED_STEREO
    )
    coverage: list[str] = []
    if aromatic_atoms or aromatic_bonds:
        coverage.append(f"{role}_aromatic_specific_interactions_missing")
    if declared_atom_stereo or declared_bond_stereo:
        coverage.append(f"{role}_stereochemistry_geometry_not_verified")

    return ReferenceDockingSystemApplicability(
        role=role,
        system_sha256=system_sha256,
        topology_sha256=topology_sha256,
        parameter_fingerprint_sha256=parameter_fingerprint,
        atom_count=system.atom_count,
        model_count=system.model_count,
        coordinate_dtype=str(system.coordinates.dtype).removeprefix("torch."),
        coordinate_device=system.coordinates.device.type,
        periodic_cell_present=system.cell is not None,
        validation_error_codes=validation_error_codes,
        unsupported_atom_indices=unsupported_atoms,
        unsupported_atomic_numbers=unsupported_numbers,
        unsupported_elements=unsupported_elements,
        metal_atom_indices=metal_atoms,
        metal_atomic_numbers=metal_numbers,
        formal_charge_outlier_atom_indices=formal_charge_outliers,
        missing_partial_charge_atom_indices=missing_partial,
        mismatched_partial_charge_atom_indices=mismatched_partial,
        missing_parameter_atom_indices=missing_parameters,
        extra_parameter_atom_indices=extra_parameters,
        receptor_nonpolymer_residues=nonpolymer,
        aromatic_atom_indices=aromatic_atoms,
        aromatic_bond_indices=aromatic_bonds,
        declared_atom_stereo_indices=declared_atom_stereo,
        declared_bond_stereo_indices=declared_bond_stereo,
        invalid_input_blockers=_unique(invalid),
        chemistry_scope_blockers=_unique(chemistry),
        parameter_scope_blockers=_unique(parameter_blockers),
        execution_scope_blockers=_unique(execution),
        interaction_coverage_blockers=_unique(coverage),
    )


def _disposition(
    *,
    invalid: tuple[str, ...],
    chemistry: tuple[str, ...],
    parameter: tuple[str, ...],
    execution: tuple[str, ...],
) -> str:
    if invalid:
        return "invalid_input"
    if chemistry:
        return "abstain_chemistry_scope"
    if parameter:
        return "abstain_parameter_scope"
    if execution:
        return "abstain_execution_scope"
    return "admitted_diagnostic"


def _static_assessment(
    receptor_system: AllAtomSystem,
    ligand_system: AllAtomSystem,
    receptor_parameters: ReferenceForceFieldParameters | None,
    ligand_parameters: ReferenceForceFieldParameters | None,
    problem: DockingProblemIdentity,
    config: ReferenceDockingScoreConfig,
) -> ReferenceDockingApplicabilityAssessment:
    receptor = _role_assessment(
        receptor_system,
        receptor_parameters,
        role="receptor",
        config=config,
    )
    ligand = _role_assessment(
        ligand_system,
        ligand_parameters,
        role="ligand",
        config=config,
    )

    invalid = [
        *receptor.invalid_input_blockers,
        *ligand.invalid_input_blockers,
    ]
    if not problem.bound:
        invalid.append("docking_problem_identity_unbound")
    if (
        receptor.system_sha256 is not None
        and problem.receptor_system_sha256 != receptor.system_sha256
    ):
        invalid.append("docking_problem_receptor_identity_mismatch")
    if (
        ligand.system_sha256 is not None
        and problem.ligand_system_sha256 != ligand.system_sha256
    ):
        invalid.append("docking_problem_ligand_identity_mismatch")

    chemistry = _unique(
        [
            *receptor.chemistry_scope_blockers,
            *ligand.chemistry_scope_blockers,
        ]
    )
    parameter = _unique(
        [
            *receptor.parameter_scope_blockers,
            *ligand.parameter_scope_blockers,
        ]
    )
    execution = [
        *receptor.execution_scope_blockers,
        *ligand.execution_scope_blockers,
    ]
    cross_pair_count = receptor_system.atom_count * ligand_system.atom_count
    if cross_pair_count > config.max_cross_pairs:
        execution.append("receptor_ligand_cross_pair_capacity_exceeded")
    execution_rows = _unique(execution)
    invalid_rows = _unique(invalid)
    coverage = _unique(
        [
            *receptor.interaction_coverage_blockers,
            *ligand.interaction_coverage_blockers,
        ]
    )

    parameter_source_sha256 = None
    if receptor_parameters is not None and ligand_parameters is not None:
        parameter_source_sha256 = _canonical_sha256(
            {
                "receptor_parameter_sha256": (receptor_parameters.fingerprint_sha256),
                "ligand_parameter_sha256": ligand_parameters.fingerprint_sha256,
            }
        )

    disposition = _disposition(
        invalid=invalid_rows,
        chemistry=chemistry,
        parameter=parameter,
        execution=execution_rows,
    )
    return ReferenceDockingApplicabilityAssessment(
        disposition=disposition,
        problem_fingerprint_sha256=problem.fingerprint_sha256,
        config_fingerprint_sha256=config.fingerprint_sha256,
        parameter_source_sha256=parameter_source_sha256,
        receptor=receptor,
        ligand=ligand,
        invalid_input_blockers=invalid_rows,
        chemistry_scope_blockers=chemistry,
        parameter_scope_blockers=parameter,
        execution_scope_blockers=execution_rows,
        interaction_coverage_blockers=coverage,
        diagnostic_scorer_admitted=disposition == "admitted_diagnostic",
        interaction_coverage_complete=not chemistry and not coverage,
        ood_detected=bool(chemistry or coverage),
    )


def admit_reference_docking_scorer(
    receptor_system: AllAtomSystem,
    ligand_system: AllAtomSystem,
    receptor_parameters: ReferenceForceFieldParameters | None,
    ligand_parameters: ReferenceForceFieldParameters | None,
    problem: DockingProblemIdentity,
    *,
    config: ReferenceDockingScoreConfig | None = None,
) -> ReferenceDockingScorerAdmission:
    """Assess all blockers and construct the scorer only for admitted inputs."""

    resolved_config = config or ReferenceDockingScoreConfig()
    assessment = _static_assessment(
        receptor_system,
        ligand_system,
        receptor_parameters,
        ligand_parameters,
        problem,
        resolved_config,
    )
    if not assessment.diagnostic_scorer_admitted:
        return ReferenceDockingScorerAdmission(assessment=assessment, scorer=None)

    if receptor_parameters is None or ligand_parameters is None:
        raise AssertionError("admitted inputs must have both parameter sets")
    try:
        scorer = UncalibratedReferenceDockingScorer(
            receptor_system,
            ligand_system,
            receptor_parameters,
            ligand_parameters,
            problem,
            config=resolved_config,
        )
    except (
        ReferenceDockingScoringError,
        ReferencePhysicsApplicabilityError,
        NeighborOverflowError,
        FloatingPointError,
    ):
        execution = _unique(
            [
                *assessment.execution_scope_blockers,
                "reference_scorer_construction_failed",
            ]
        )
        assessment = replace(
            assessment,
            disposition="abstain_execution_scope",
            execution_scope_blockers=execution,
            diagnostic_scorer_admitted=False,
        )
        return ReferenceDockingScorerAdmission(assessment=assessment, scorer=None)
    return ReferenceDockingScorerAdmission(assessment=assessment, scorer=scorer)


def assess_reference_docking_applicability(
    receptor_system: AllAtomSystem,
    ligand_system: AllAtomSystem,
    receptor_parameters: ReferenceForceFieldParameters | None,
    ligand_parameters: ReferenceForceFieldParameters | None,
    problem: DockingProblemIdentity,
    *,
    config: ReferenceDockingScoreConfig | None = None,
) -> ReferenceDockingApplicabilityAssessment:
    """Return the exact failure-inclusive assessment without leaking an error."""

    return admit_reference_docking_scorer(
        receptor_system,
        ligand_system,
        receptor_parameters,
        ligand_parameters,
        problem,
        config=config,
    ).assessment


__all__ = [
    "REFERENCE_DOCKING_APPLICABILITY_DISPOSITIONS",
    "REFERENCE_DOCKING_APPLICABILITY_PROFILE_ID",
    "REFERENCE_DOCKING_APPLICABILITY_SCHEMA_ID",
    "REFERENCE_DOCKING_APPLICABILITY_SCIENTIFIC_BLOCKERS",
    "REFERENCE_DOCKING_METAL_ATOMIC_NUMBERS",
    "ReferenceDockingApplicabilityAssessment",
    "ReferenceDockingNonpolymerResidue",
    "ReferenceDockingScorerAdmission",
    "ReferenceDockingSystemApplicability",
    "admit_reference_docking_scorer",
    "assess_reference_docking_applicability",
]
