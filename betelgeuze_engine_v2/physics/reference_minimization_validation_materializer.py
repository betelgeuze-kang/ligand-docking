"""Exact runtime materializer for the frozen minimization protocol.

The materializer converts every frozen fixture and case into deterministic CPU
``float64`` Engine v2 runtime objects.  It does not run a minimizer, create a
checkpoint, evaluate energy or force, collect a metric, or authorize validation.
Synthetic values remain protocol inputs rather than fitted parameters.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import tempfile
from types import MappingProxyType
from typing import Any, Mapping

import torch

from betelgeuze_engine_v2.molecular import (
    AllAtomSystem,
    Atom,
    Bond,
    Chain,
    Residue,
    StructureProvenance,
    UnitCell,
    canonical_coordinates_sha256,
    canonical_system_sha256,
    canonical_topology_sha256,
)

from .reference_constrained_minimization import (
    ReferenceConstrainedMinimizationConfig,
)
from .reference_forcefield_v2 import (
    DistanceConstraintParameter,
    DistanceConstraintProjectionConfig,
    ReferenceForceFieldV2Parameters,
)
from .reference_minimization import ReferenceMinimizationConfig
from .reference_minimization_independent_oracle import (
    IndependentMinimizationOracleInput,
)
from .reference_minimization_validation_protocol import (
    FROZEN_CPU_MINIMIZATION_VALIDATION_PROTOCOL_SHA256,
    cpu_minimization_validation_protocol_document,
    require_cpu_minimization_validation_protocol_document,
)
from .reference_parameters import (
    AtomNonbondedParameter,
    HarmonicAngleParameter,
    HarmonicBondParameter,
    PairScalingParameter,
    PeriodicTorsionParameter,
    ReferenceApplicabilityDomain,
    ReferenceForceFieldParameters,
)
from .reference_solvation import (
    FixedBornAtomParameter,
    FixedBornPolarSolvationParameters,
)
from .reference_validation_oracle import IndependentAnalyticOracleInput


CPU_MINIMIZATION_VALIDATION_MATERIALIZER_SCHEMA_ID = (
    "betelgeuze.engine_v2_cpu_minimization_validation_materializer/1.0.0"
)
CPU_MINIMIZATION_VALIDATION_MATERIALIZER_ID = (
    "cpu_reference_minimization_exact_fixture_materializer/1.0.0"
)
CPU_MINIMIZATION_VALIDATION_MATERIALIZER_VERSION = "1.0.0"

MATERIALIZER_MAX_ATOMS = 16
MATERIALIZER_MAX_BONDS = 32
MATERIALIZER_MAX_ANGLES = 64
MATERIALIZER_MAX_TORSIONS = 128
MATERIALIZER_MAX_NONBONDED_PAIRS = 120
MATERIALIZER_MAX_NEIGHBORS = 16
MATERIALIZER_MAX_ATOMS_PER_CELL = 16
MATERIALIZER_MINIMUM_PAIR_DISTANCE_ANGSTROM = 0.1
MATERIALIZER_BACKTRACK_FACTOR = 0.5
MATERIALIZER_MAXIMUM_ATOM_DISPLACEMENT_ANGSTROM = 0.05
MATERIALIZER_FORCE_TOLERANCE_KCAL_PER_MOL_ANGSTROM = 1.0e-8
MATERIALIZER_CONSTRAINT_TOLERANCE_ANGSTROM = 1.0e-10
MATERIALIZER_MAX_CONSTRAINT_PROJECTION_ITERATIONS = 100
MATERIALIZER_MAX_PAIR_CORRECTION_ANGSTROM = 0.25
MATERIALIZER_FORCE_PROJECTION_MAX_SWEEPS = 100
MATERIALIZER_FORCE_PROJECTION_TOLERANCE = 1.0e-8

_ELEMENT_ATOMIC_NUMBERS = {
    "H": 1,
    "C": 6,
    "N": 7,
    "O": 8,
    "F": 9,
    "P": 15,
    "S": 16,
    "Cl": 17,
    "Br": 35,
    "I": 53,
}
_CROSSWIRE_KEYS = (
    "checkpoint_topology_sha256",
    "runtime_topology_sha256",
    "checkpoint_parameter_sha256",
    "runtime_parameter_sha256",
    "checkpoint_solvation_sha256",
    "runtime_solvation_sha256",
)


class CPUMinimizationValidationMaterializationError(ValueError):
    """A frozen minimization fixture could not be materialized exactly."""


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise CPUMinimizationValidationMaterializationError(
            "minimization materialization payload is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


def _freeze_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType(
        {
            str(key): (
                _freeze_mapping(item)
                if isinstance(item, Mapping)
                else tuple(
                    _freeze_mapping(child) if isinstance(child, Mapping) else child
                    for child in item
                )
                if isinstance(item, (list, tuple))
                else item
            )
            for key, item in sorted(value.items())
        }
    )


def cpu_minimization_validation_materializer_source_sha256() -> str:
    """Return the byte identity of this exact materializer source."""

    return hashlib.sha256(Path(__file__).resolve().read_bytes()).hexdigest()


def _protocol_document(
    value: Mapping[str, Any] | None,
) -> dict[str, Any]:
    document = (
        cpu_minimization_validation_protocol_document()
        if value is None
        else dict(value)
    )
    return require_cpu_minimization_validation_protocol_document(document)


def _fixture_map(document: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    rows = document["fixture_manifest"]["fixtures"]
    return {str(row["fixture_id"]): dict(row) for row in rows}


def _resolved_fixture(
    fixture_id: str,
    fixtures: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, Any], tuple[str, ...]]:
    try:
        row = fixtures[fixture_id]
    except KeyError as exc:
        raise CPUMinimizationValidationMaterializationError(
            f"unknown minimization fixture {fixture_id!r}"
        ) from exc
    payload = json.loads(json.dumps(row["payload"], allow_nan=False))
    base_id = payload.pop("base_fixture", None)
    if base_id is None:
        return payload, (fixture_id,)
    if not isinstance(base_id, str) or base_id == fixture_id:
        raise CPUMinimizationValidationMaterializationError(
            "fixture base identity must be a distinct string"
        )
    base, chain = _resolved_fixture(base_id, fixtures)
    if fixture_id in chain:
        raise CPUMinimizationValidationMaterializationError(
            "fixture base references must be acyclic"
        )
    return {**base, **payload}, (*chain, fixture_id)


def _coordinates(rows: object) -> torch.Tensor:
    try:
        tensor = torch.tensor(rows, dtype=torch.float64, device="cpu")
    except (TypeError, ValueError, RuntimeError) as exc:
        raise CPUMinimizationValidationMaterializationError(
            "fixture coordinates must be CPU float64 values"
        ) from exc
    if tensor.ndim != 2 or tensor.shape[1] != 3 or tensor.shape[0] == 0:
        raise CPUMinimizationValidationMaterializationError(
            "fixture coordinates must have non-empty [atom,3] shape"
        )
    if not bool(torch.isfinite(tensor).all().item()):
        raise CPUMinimizationValidationMaterializationError(
            "fixture coordinates must be finite"
        )
    return tensor.unsqueeze(0)


def _topology_bond_rows(payload: Mapping[str, Any]) -> tuple[tuple[int, int], ...]:
    rows: list[tuple[int, int]] = []
    for row in payload.get("bonds", ()):
        if not isinstance(row, list) or len(row) != 4:
            raise CPUMinimizationValidationMaterializationError(
                "bond rows must be [atom_i,atom_j,force_constant,equilibrium]"
            )
        rows.append(tuple(sorted((int(row[0]), int(row[1])))))
    if len(rows) != len(set(rows)):
        raise CPUMinimizationValidationMaterializationError(
            "fixture topology bonds must be unique"
        )
    return tuple(rows)


def _system(
    fixture_id: str,
    fixture_sha256: str,
    payload: Mapping[str, Any],
    resolution_chain: tuple[str, ...],
) -> AllAtomSystem:
    atom_rows = payload.get("atoms")
    if not isinstance(atom_rows, list) or not atom_rows:
        raise CPUMinimizationValidationMaterializationError(
            "fixture atom rows must be non-empty"
        )
    coordinates = _coordinates(payload.get("coordinates_angstrom"))
    if coordinates.shape[1] != len(atom_rows):
        raise CPUMinimizationValidationMaterializationError(
            "fixture atom and coordinate counts must match"
        )
    atoms: list[Atom] = []
    for index, row in enumerate(atom_rows):
        if not isinstance(row, Mapping):
            raise CPUMinimizationValidationMaterializationError(
                "fixture atom row must be an object"
            )
        element = str(row.get("element", ""))
        try:
            atomic_number = _ELEMENT_ATOMIC_NUMBERS[element]
        except KeyError as exc:
            raise CPUMinimizationValidationMaterializationError(
                f"unsupported fixture element {element!r}"
            ) from exc
        atoms.append(
            Atom(
                index=index,
                name=f"{element}{index + 1}",
                element=element,
                atomic_number=atomic_number,
                residue_index=0,
                formal_charge=int(row.get("formal_charge", 0)),
                mass_da=float(row["mass_dalton"]),
                metadata={
                    "synthetic_minimization_validation_fixture": True,
                    "scientifically_validated": False,
                },
            )
        )
    bond_pairs = _topology_bond_rows(payload)
    bonds = tuple(
        Bond(
            index=index,
            atom_i=pair[0],
            atom_j=pair[1],
            order=1.0,
            source="frozen_minimization_validation_protocol",
        )
        for index, pair in enumerate(bond_pairs)
    )
    cell = None
    if "orthorhombic_cell_angstrom" in payload:
        axes = payload.get("periodic_axes")
        if not isinstance(axes, list) or len(axes) != 3:
            raise CPUMinimizationValidationMaterializationError(
                "periodic fixture requires three periodic-axis flags"
            )
        cell = UnitCell.orthorhombic(
            payload["orthorhombic_cell_angstrom"],
            dtype=torch.float64,
            device="cpu",
            periodic=tuple(bool(item) for item in axes),
        )
    return AllAtomSystem(
        system_id=f"cpu-minimization-validation:{fixture_id}",
        atoms=tuple(atoms),
        bonds=bonds,
        residues=(
            Residue(
                index=0,
                name="SYN",
                chain_index=0,
                sequence_number=1,
                atom_indices=tuple(range(len(atoms))),
                entity_type="non_polymer",
                hetero=True,
                metadata={"synthetic_minimization_validation_fixture": True},
            ),
        ),
        chains=(
            Chain(
                index=0,
                chain_id="M",
                residue_indices=(0,),
                entity_id="synthetic-minimization-validation-fixture",
            ),
        ),
        coordinates=coordinates,
        cell=cell,
        coordinate_unit="angstrom",
        provenance=StructureProvenance(
            source_format="engine_v2_minimization_validation_fixture",
            source_id=fixture_id,
            source_sha256=fixture_sha256,
            parser_name=CPU_MINIMIZATION_VALIDATION_MATERIALIZER_ID,
            parser_version=CPU_MINIMIZATION_VALIDATION_MATERIALIZER_VERSION,
            operations=("exact_frozen_minimization_fixture_materialization",),
            source_digest_verified=True,
            transformation_chain_verified=True,
            chemistry_validated=False,
            scientifically_validated=False,
            product_qualified=False,
        ),
        metadata={
            "fixture_id": fixture_id,
            "fixture_sha256": fixture_sha256,
            "fixture_resolution_chain": list(resolution_chain),
            "parameter_origin": "synthetic_protocol_values_not_fit_data",
            "validation_result": False,
            "scientifically_validated": False,
            "claim_safe": False,
        },
    )


def _base_parameters(
    fixture_id: str,
    fixture_sha256: str,
    system: AllAtomSystem,
    payload: Mapping[str, Any],
) -> ReferenceForceFieldParameters:
    atom_rows = payload.get("atom_nonbonded")
    if atom_rows is None:
        atom_rows = [[0.0, 1.0, 0.0] for _ in range(system.atom_count)]
    if not isinstance(atom_rows, list) or len(atom_rows) != system.atom_count:
        raise CPUMinimizationValidationMaterializationError(
            "atom_nonbonded rows must cover every atom"
        )
    try:
        atoms = tuple(
            AtomNonbondedParameter(
                atom_index=index,
                charge_e=row[0],
                sigma_angstrom=row[1],
                epsilon_kcal_per_mol=row[2],
            )
            for index, row in enumerate(atom_rows)
        )
        bonds = tuple(
            HarmonicBondParameter(
                atom_i=row[0],
                atom_j=row[1],
                force_constant_kcal_per_mol_angstrom2=row[2],
                equilibrium_angstrom=row[3],
            )
            for row in payload.get("bonds", ())
        )
        angles = tuple(
            HarmonicAngleParameter(
                atom_i=row[0],
                atom_j=row[1],
                atom_k=row[2],
                force_constant_kcal_per_mol_radian2=row[3],
                equilibrium_radians=row[4],
            )
            for row in payload.get("angles", ())
        )
        torsions = tuple(
            PeriodicTorsionParameter(
                atom_i=row[0],
                atom_j=row[1],
                atom_k=row[2],
                atom_l=row[3],
                amplitude_kcal_per_mol=row[4],
                periodicity=row[5],
                phase_radians=row[6],
            )
            for row in payload.get("proper_torsions", ())
        )
        scaled = tuple(
            PairScalingParameter(
                atom_i=row[0],
                atom_j=row[1],
                lj_scale=row[2],
                electrostatic_scale=row[3],
            )
            for row in payload.get("pair_scaling", ())
        )
    except (IndexError, TypeError, ValueError) as exc:
        raise CPUMinimizationValidationMaterializationError(
            "fixture force-field rows cannot be materialized exactly"
        ) from exc
    scaled_pairs = {(row.atom_i, row.atom_j) for row in scaled}
    excluded = {(row.atom_i, row.atom_j) for row in bonds}
    excluded.update(tuple(sorted((row.atom_i, row.atom_k))) for row in angles)
    excluded.difference_update(scaled_pairs)
    nonbonded = payload.get("nonbonded", {})
    if not isinstance(nonbonded, Mapping):
        raise CPUMinimizationValidationMaterializationError(
            "fixture nonbonded settings must be an object"
        )
    return ReferenceForceFieldParameters(
        parameter_set_id=f"cpu-minimization-validation-{fixture_id}",
        parameter_set_version="1.0.0",
        topology_sha256=canonical_topology_sha256(system),
        atom_parameters=atoms,
        bonds=bonds,
        angles=angles,
        torsions=torsions,
        excluded_pairs=tuple(sorted(excluded)),
        scaled_pairs=scaled,
        cutoff_angstrom=nonbonded.get("cutoff_angstrom", 4.0),
        switch_start_angstrom=nonbonded.get("switch_distance_angstrom", 3.0),
        dielectric=nonbonded.get("dielectric", 1.0),
        screening_kappa_per_angstrom=nonbonded.get("screening_kappa_per_angstrom", 0.0),
        applicability_domain=ReferenceApplicabilityDomain(
            max_atoms=MATERIALIZER_MAX_ATOMS,
            max_bonds=MATERIALIZER_MAX_BONDS,
            max_angles=MATERIALIZER_MAX_ANGLES,
            max_torsions=MATERIALIZER_MAX_TORSIONS,
            max_nonbonded_pairs=MATERIALIZER_MAX_NONBONDED_PAIRS,
            periodic_orthorhombic_supported=True,
            minimum_pair_distance_angstrom=(
                MATERIALIZER_MINIMUM_PAIR_DISTANCE_ANGSTROM
            ),
        ),
        metadata={
            "fixture_id": fixture_id,
            "fixture_sha256": fixture_sha256,
            "parameter_origin": "synthetic_protocol_values_not_fit_data",
            "parameter_fitting_data": False,
            "scientifically_validated": False,
        },
    )


def _v2_parameters(
    base: ReferenceForceFieldParameters,
    payload: Mapping[str, Any],
) -> ReferenceForceFieldV2Parameters:
    constraints = tuple(
        DistanceConstraintParameter(
            atom_i=row[0],
            atom_j=row[1],
            target_distance_angstrom=row[2],
            tolerance_angstrom=MATERIALIZER_CONSTRAINT_TOLERANCE_ANGSTROM,
        )
        for row in payload.get("distance_constraints", ())
    )
    return ReferenceForceFieldV2Parameters(
        base_parameters=base,
        constraints=constraints,
        metadata={
            "scope": "synthetic_minimization_validation_fixture",
            "constraint_weighting": "equal_weight_without_atomic_masses",
            "scientifically_validated": False,
        },
    )


def _solvation_parameters(
    fixture_id: str,
    system: AllAtomSystem,
    parameters: ReferenceForceFieldV2Parameters,
    payload: Mapping[str, Any],
) -> FixedBornPolarSolvationParameters | None:
    fixed_born = payload.get("fixed_born")
    if fixed_born is None:
        return None
    if not isinstance(fixed_born, Mapping):
        raise CPUMinimizationValidationMaterializationError(
            "fixed_born settings must be an object"
        )
    radii = fixed_born.get("effective_radii_angstrom")
    if not isinstance(radii, list) or len(radii) != system.atom_count:
        raise CPUMinimizationValidationMaterializationError(
            "fixed Born radii must cover every atom"
        )
    return FixedBornPolarSolvationParameters(
        parameter_set_id=f"cpu-minimization-validation-born-{fixture_id}",
        parameter_set_version="1.0.0",
        parameter_source_sha256=str(fixed_born["radius_source_sha256"]),
        topology_sha256=canonical_topology_sha256(system),
        charge_parameter_fingerprint_sha256=parameters.fingerprint_sha256,
        atom_parameters=tuple(
            FixedBornAtomParameter(index, radius) for index, radius in enumerate(radii)
        ),
        solute_dielectric=fixed_born["solute_dielectric"],
        solvent_dielectric=fixed_born["solvent_dielectric"],
        minimum_pair_distance_angstrom=(MATERIALIZER_MINIMUM_PAIR_DISTANCE_ANGSTROM),
        max_atoms=MATERIALIZER_MAX_ATOMS,
        metadata={
            "fixture_id": fixture_id,
            "radius_origin": "synthetic_protocol_values_not_fit_data",
            "radius_estimation_performed": False,
            "scientifically_validated": False,
        },
    )


def _minimization_config(
    case_input: Mapping[str, Any],
    payload: Mapping[str, Any],
) -> ReferenceMinimizationConfig:
    def selected(name: str, fallback: object) -> object:
        return payload.get(name, case_input.get(name, fallback))

    return ReferenceMinimizationConfig(
        max_iterations=selected("maximum_iterations", 64),
        max_backtracks=selected("maximum_backtracks", 16),
        initial_step_size_angstrom2_mol_per_kcal=selected(
            "initial_step_angstrom_squared_mol_per_kcal", 1.0e-3
        ),
        backtrack_factor=MATERIALIZER_BACKTRACK_FACTOR,
        armijo_constant=selected("armijo_coefficient", 1.0e-4),
        maximum_atom_displacement_angstrom=(
            MATERIALIZER_MAXIMUM_ATOM_DISPLACEMENT_ANGSTROM
        ),
        force_tolerance_kcal_per_mol_angstrom=(
            MATERIALIZER_FORCE_TOLERANCE_KCAL_PER_MOL_ANGSTROM
        ),
        max_neighbors=MATERIALIZER_MAX_NEIGHBORS,
        max_atoms_per_cell=MATERIALIZER_MAX_ATOMS_PER_CELL,
    )


def _constrained_config(
    minimization: ReferenceMinimizationConfig,
    case_input: Mapping[str, Any],
    payload: Mapping[str, Any],
) -> ReferenceConstrainedMinimizationConfig:
    projection_iterations = payload.get(
        "maximum_constraint_projection_iterations",
        case_input.get(
            "maximum_constraint_projection_iterations",
            MATERIALIZER_MAX_CONSTRAINT_PROJECTION_ITERATIONS,
        ),
    )
    return ReferenceConstrainedMinimizationConfig(
        minimization=minimization,
        constraint_projection=DistanceConstraintProjectionConfig(
            max_iterations=projection_iterations,
            max_pair_correction_angstrom=(MATERIALIZER_MAX_PAIR_CORRECTION_ANGSTROM),
        ),
        force_projection_max_sweeps=MATERIALIZER_FORCE_PROJECTION_MAX_SWEEPS,
        force_projection_tolerance_kcal_per_mol_angstrom=(
            MATERIALIZER_FORCE_PROJECTION_TOLERANCE
        ),
    )


def _independent_oracle_input(
    *,
    case_id: str,
    case_input_sha256: str,
    expected_outcome: str,
    expected_error_code: str | None,
    system: AllAtomSystem,
    base_parameters: ReferenceForceFieldParameters,
    v2_parameters: ReferenceForceFieldV2Parameters | None,
    solvation_parameters: FixedBornPolarSolvationParameters | None,
    minimization_config: ReferenceMinimizationConfig,
    constrained_config: ReferenceConstrainedMinimizationConfig | None,
    pause_after_accepted_iterations: int | None,
    failure_injection: Mapping[str, Any],
) -> IndependentMinimizationOracleInput:
    coordinates = tuple(
        tuple(float(value) for value in row) for row in system.coordinates[0].tolist()
    )
    cell = system.cell
    orthorhombic_cell = (
        None
        if cell is None
        else tuple(float(cell.vectors[index, index].item()) for index in range(3))
    )
    periodic_axes = (False, False, False) if cell is None else cell.periodic
    energy_input = IndependentAnalyticOracleInput(
        coordinates_angstrom=coordinates,
        topology_bonds=tuple((row.atom_i, row.atom_j) for row in system.bonds),
        atom_nonbonded=tuple(
            (
                row.atom_index,
                row.sigma_angstrom,
                row.epsilon_kcal_per_mol,
                row.charge_e,
            )
            for row in base_parameters.atom_parameters
        ),
        bonds=tuple(
            (
                row.atom_i,
                row.atom_j,
                row.equilibrium_angstrom,
                row.force_constant_kcal_per_mol_angstrom2,
            )
            for row in base_parameters.bonds
        ),
        angles=tuple(
            (
                row.atom_i,
                row.atom_j,
                row.atom_k,
                row.equilibrium_radians,
                row.force_constant_kcal_per_mol_radian2,
            )
            for row in base_parameters.angles
        ),
        torsions=tuple(
            (
                row.atom_i,
                row.atom_j,
                row.atom_k,
                row.atom_l,
                row.periodicity,
                row.phase_radians,
                row.amplitude_kcal_per_mol,
            )
            for row in base_parameters.torsions
        ),
        excluded_pairs=base_parameters.excluded_pairs,
        scaled_pairs=tuple(
            (row.atom_i, row.atom_j, row.lj_scale, row.electrostatic_scale)
            for row in base_parameters.scaled_pairs
        ),
        cutoff_angstrom=base_parameters.cutoff_angstrom,
        switch_start_angstrom=base_parameters.switch_start_angstrom,
        dielectric=base_parameters.dielectric,
        screening_kappa_per_angstrom=(base_parameters.screening_kappa_per_angstrom),
        orthorhombic_cell_angstrom=orthorhombic_cell,
        periodic_axes=periodic_axes,
        minimum_pair_distance_angstrom=(
            base_parameters.applicability_domain.minimum_pair_distance_angstrom
        ),
    )
    constraints = (
        ()
        if v2_parameters is None
        else tuple(
            (
                row.atom_i,
                row.atom_j,
                row.target_distance_angstrom,
                row.tolerance_angstrom,
            )
            for row in v2_parameters.constraints
        )
    )
    radii = (
        None
        if solvation_parameters is None
        else tuple(
            row.effective_born_radius_angstrom
            for row in solvation_parameters.atom_parameters
        )
    )
    projection_config = (
        None if constrained_config is None else constrained_config.constraint_projection
    )
    return IndependentMinimizationOracleInput(
        case_id=case_id,
        case_input_sha256=case_input_sha256,
        expected_outcome=expected_outcome,
        expected_error_code=expected_error_code,
        energy_input=energy_input,
        constraints=constraints,
        fixed_born_radii_angstrom=radii,
        fixed_born_solute_dielectric=(
            1.0
            if solvation_parameters is None
            else solvation_parameters.solute_dielectric
        ),
        fixed_born_solvent_dielectric=(
            78.5
            if solvation_parameters is None
            else solvation_parameters.solvent_dielectric
        ),
        max_iterations=minimization_config.max_iterations,
        max_backtracks=minimization_config.max_backtracks,
        initial_step_size_angstrom2_mol_per_kcal=(
            minimization_config.initial_step_size_angstrom2_mol_per_kcal
        ),
        backtrack_factor=minimization_config.backtrack_factor,
        armijo_constant=minimization_config.armijo_constant,
        maximum_atom_displacement_angstrom=(
            minimization_config.maximum_atom_displacement_angstrom
        ),
        force_tolerance_kcal_per_mol_angstrom=(
            minimization_config.force_tolerance_kcal_per_mol_angstrom
        ),
        constraint_projection_max_iterations=(
            MATERIALIZER_MAX_CONSTRAINT_PROJECTION_ITERATIONS
            if projection_config is None
            else projection_config.max_iterations
        ),
        constraint_max_pair_correction_angstrom=(
            MATERIALIZER_MAX_PAIR_CORRECTION_ANGSTROM
            if projection_config is None
            else projection_config.max_pair_correction_angstrom
        ),
        force_projection_max_sweeps=(
            MATERIALIZER_FORCE_PROJECTION_MAX_SWEEPS
            if constrained_config is None
            else constrained_config.force_projection_max_sweeps
        ),
        force_projection_tolerance_kcal_per_mol_angstrom=(
            MATERIALIZER_FORCE_PROJECTION_TOLERANCE
            if constrained_config is None
            else constrained_config.force_projection_tolerance_kcal_per_mol_angstrom
        ),
        pause_after_accepted_iterations=pause_after_accepted_iterations,
        **{key: failure_injection.get(key) for key in _CROSSWIRE_KEYS},
    )


@dataclass(frozen=True, slots=True)
class MaterializedCPUMinimizationValidationCase:
    """One exact runtime plan without a minimization result."""

    case_id: str
    case_input_sha256: str
    fixture_id: str
    fixture_sha256: str
    fixture_resolution_chain: tuple[str, ...]
    lane: str
    evaluator_scope: str
    expected_outcome: str
    expected_error_code: str | None
    system: AllAtomSystem
    base_parameters: ReferenceForceFieldParameters
    v2_parameters: ReferenceForceFieldV2Parameters | None
    solvation_parameters: FixedBornPolarSolvationParameters | None
    minimization_config: ReferenceMinimizationConfig
    constrained_config: ReferenceConstrainedMinimizationConfig | None
    pause_after_accepted_iterations: int | None
    failure_injection: Mapping[str, Any]
    independent_oracle_input: IndependentMinimizationOracleInput

    def __post_init__(self) -> None:
        if self.system.coordinates.dtype != torch.float64:
            raise CPUMinimizationValidationMaterializationError(
                "materialized coordinates must use float64"
            )
        if self.system.coordinates.device.type != "cpu":
            raise CPUMinimizationValidationMaterializationError(
                "materialized coordinates must be CPU-resident"
            )
        if self.evaluator_scope == "reference_forcefield_v1":
            if self.v2_parameters is not None or self.constrained_config is not None:
                raise CPUMinimizationValidationMaterializationError(
                    "reference v1 cases cannot carry v2 runtime inputs"
                )
        elif self.v2_parameters is None or self.constrained_config is None:
            raise CPUMinimizationValidationMaterializationError(
                "v2 and fail-closed cases require bounded v2 runtime inputs"
            )
        if "fixed_born" in self.evaluator_scope:
            if self.solvation_parameters is None:
                raise CPUMinimizationValidationMaterializationError(
                    "fixed-Born cases require exact solvation inputs"
                )
        elif self.solvation_parameters is not None:
            raise CPUMinimizationValidationMaterializationError(
                "non-solvated cases cannot carry fixed-Born inputs"
            )
        object.__setattr__(
            self,
            "failure_injection",
            _freeze_mapping(dict(self.failure_injection)),
        )
        if self.independent_oracle_input.case_id != self.case_id:
            raise CPUMinimizationValidationMaterializationError(
                "independent oracle case identity does not match"
            )
        if self.independent_oracle_input.case_input_sha256 != self.case_input_sha256:
            raise CPUMinimizationValidationMaterializationError(
                "independent oracle input identity does not match"
            )

    def projection(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "case_input_sha256": self.case_input_sha256,
            "fixture_id": self.fixture_id,
            "fixture_sha256": self.fixture_sha256,
            "fixture_resolution_chain": list(self.fixture_resolution_chain),
            "lane": self.lane,
            "evaluator_scope": self.evaluator_scope,
            "expected_outcome": self.expected_outcome,
            "expected_error_code": self.expected_error_code,
            "system_sha256": canonical_system_sha256(self.system),
            "topology_sha256": canonical_topology_sha256(self.system),
            "coordinate_sha256": canonical_coordinates_sha256(self.system),
            "base_parameter_fingerprint_sha256": (
                self.base_parameters.fingerprint_sha256
            ),
            "v2_parameter_fingerprint_sha256": (
                None
                if self.v2_parameters is None
                else self.v2_parameters.fingerprint_sha256
            ),
            "solvation_parameter_fingerprint_sha256": (
                None
                if self.solvation_parameters is None
                else self.solvation_parameters.fingerprint_sha256
            ),
            "minimization_config_fingerprint_sha256": _sha256(
                self.minimization_config.to_dict()
            ),
            "constrained_config_fingerprint_sha256": (
                None
                if self.constrained_config is None
                else self.constrained_config.fingerprint_sha256
            ),
            "pause_after_accepted_iterations": (self.pause_after_accepted_iterations),
            "failure_injection": _thaw(self.failure_injection),
            "independent_oracle_input_sha256": (
                self.independent_oracle_input.input_sha256
            ),
            "coordinate_dtype": "float64",
            "device": "cpu",
            "minimization_executed": False,
            "checkpoint_created": False,
            "energy_or_force_evaluated": False,
            "metric_values_present": False,
            "validation_result_collected": False,
            "scientifically_validated": False,
            "claim_safe": False,
        }

    @property
    def runtime_input_sha256(self) -> str:
        return _sha256(self.projection())

    def to_dict(self) -> dict[str, Any]:
        return {**self.projection(), "runtime_input_sha256": self.runtime_input_sha256}


def materialize_frozen_cpu_minimization_validation_case(
    case_id: str,
    protocol_document: Mapping[str, Any] | None = None,
) -> MaterializedCPUMinimizationValidationCase:
    """Materialize one exact frozen case without evaluating physics."""

    document = _protocol_document(protocol_document)
    fixtures = _fixture_map(document)
    cases = {str(row["case_id"]): row for row in document["case_manifest"]["cases"]}
    try:
        case = cases[case_id]
    except KeyError as exc:
        raise CPUMinimizationValidationMaterializationError(
            f"unknown frozen minimization case {case_id!r}"
        ) from exc
    case_input = case["canonical_input"]
    fixture_id = str(case_input["fixture"])
    fixture = fixtures[fixture_id]
    fixture_sha256 = str(fixture["fixture_sha256"])
    if case_input["fixture_sha256"] != fixture_sha256:
        raise CPUMinimizationValidationMaterializationError(
            "case fixture identity does not match the frozen manifest"
        )
    payload, chain = _resolved_fixture(fixture_id, fixtures)
    system = _system(fixture_id, fixture_sha256, payload, chain)
    base = _base_parameters(fixture_id, fixture_sha256, system, payload)
    lane = str(case["lane"])
    evaluator_scope = str(case["evaluator_scope"])
    v2 = (
        None
        if evaluator_scope == "reference_forcefield_v1"
        else _v2_parameters(base, payload)
    )
    solvation = (
        None if v2 is None else _solvation_parameters(fixture_id, system, v2, payload)
    )
    minimization = _minimization_config(case_input, payload)
    constrained = (
        None if v2 is None else _constrained_config(minimization, case_input, payload)
    )
    if (
        "atom_count" in case_input
        and int(case_input["atom_count"]) != system.atom_count
    ):
        raise CPUMinimizationValidationMaterializationError(
            "case atom count does not match the materialized system"
        )
    if v2 is not None and "constraint_count" in case_input:
        if int(case_input["constraint_count"]) != len(v2.constraints):
            raise CPUMinimizationValidationMaterializationError(
                "case constraint count does not match materialized parameters"
            )
    pause = case_input.get("pause_after_iterations")
    if pause is not None:
        pause = int(pause)
    failure_injection = {key: payload[key] for key in _CROSSWIRE_KEYS if key in payload}
    independent_oracle_input = _independent_oracle_input(
        case_id=str(case["case_id"]),
        case_input_sha256=str(case["input_sha256"]),
        expected_outcome=str(case["expected_outcome"]),
        expected_error_code=case["expected_error_code"],
        system=system,
        base_parameters=base,
        v2_parameters=v2,
        solvation_parameters=solvation,
        minimization_config=minimization,
        constrained_config=constrained,
        pause_after_accepted_iterations=pause,
        failure_injection=failure_injection,
    )
    return MaterializedCPUMinimizationValidationCase(
        case_id=str(case["case_id"]),
        case_input_sha256=str(case["input_sha256"]),
        fixture_id=fixture_id,
        fixture_sha256=fixture_sha256,
        fixture_resolution_chain=chain,
        lane=lane,
        evaluator_scope=evaluator_scope,
        expected_outcome=str(case["expected_outcome"]),
        expected_error_code=case["expected_error_code"],
        system=system,
        base_parameters=base,
        v2_parameters=v2,
        solvation_parameters=solvation,
        minimization_config=minimization,
        constrained_config=constrained,
        pause_after_accepted_iterations=pause,
        failure_injection=failure_injection,
        independent_oracle_input=independent_oracle_input,
    )


def cpu_minimization_validation_materialization_manifest_document(
    protocol_document: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return all exact runtime identities without collecting results."""

    document = _protocol_document(protocol_document)
    cases = tuple(
        materialize_frozen_cpu_minimization_validation_case(
            str(row["case_id"]), document
        )
        for row in document["case_manifest"]["cases"]
    )
    projection = {
        "schema_id": CPU_MINIMIZATION_VALIDATION_MATERIALIZER_SCHEMA_ID,
        "materializer_id": CPU_MINIMIZATION_VALIDATION_MATERIALIZER_ID,
        "materializer_version": CPU_MINIMIZATION_VALIDATION_MATERIALIZER_VERSION,
        "materializer_source_sha256": (
            cpu_minimization_validation_materializer_source_sha256()
        ),
        "protocol_sha256": document["protocol_sha256"],
        "fixture_manifest_sha256": document["fixture_manifest"][
            "fixture_manifest_sha256"
        ],
        "case_manifest_sha256": document["case_manifest"]["case_manifest_sha256"],
        "materialization_policy": {
            "device": "cpu",
            "coordinate_dtype": "float64",
            "coordinate_unit": "angstrom",
            "synthetic_values_are_fit_data": False,
            "fixture_resolution_precedence": (
                "materializer_defaults_then_case_input_then_fixture_override"
            ),
            "missing_atom_nonbonded_default": [0.0, 1.0, 0.0],
            "max_neighbors": MATERIALIZER_MAX_NEIGHBORS,
            "max_atoms_per_cell": MATERIALIZER_MAX_ATOMS_PER_CELL,
            "backtrack_factor": MATERIALIZER_BACKTRACK_FACTOR,
            "maximum_atom_displacement_angstrom": (
                MATERIALIZER_MAXIMUM_ATOM_DISPLACEMENT_ANGSTROM
            ),
            "force_tolerance_kcal_per_mol_angstrom": (
                MATERIALIZER_FORCE_TOLERANCE_KCAL_PER_MOL_ANGSTROM
            ),
            "constraint_tolerance_angstrom": (
                MATERIALIZER_CONSTRAINT_TOLERANCE_ANGSTROM
            ),
            "case_order_matches_protocol": True,
            "all_failure_rows_retained": True,
            "skipped_cases_allowed": False,
        },
        "coverage": {
            "fixture_count": document["fixture_manifest"]["fixture_count"],
            "case_count": len(cases),
            "expected_pass_case_count": sum(
                row.expected_outcome == "pass" for row in cases
            ),
            "expected_fail_closed_case_count": sum(
                row.expected_outcome == "fail_closed" for row in cases
            ),
            "unconstrained_v1_case_count": sum(
                row.lane == "unconstrained_v1" for row in cases
            ),
            "v2_runtime_case_count": sum(
                row.v2_parameters is not None for row in cases
            ),
            "fixed_born_case_count": sum(
                row.solvation_parameters is not None for row in cases
            ),
        },
        "cases": [row.to_dict() for row in cases],
        "fixture_materializer_implemented": True,
        "independent_minimization_reference_implemented": True,
        "minimization_executed": False,
        "checkpoint_created": False,
        "energy_or_force_values_present": False,
        "metric_values_present": False,
        "validation_result_collected": False,
        "validation_execution_authorized": False,
        "parameter_fitting_authorized": False,
        "scientifically_validated": False,
        "product_qualified": False,
        "customer_execution_enabled": False,
        "claim_safe": False,
    }
    return {
        **projection,
        "materialization_manifest_sha256": _sha256(projection),
    }


def cpu_minimization_validation_materialization_manifest_json_bytes() -> bytes:
    """Return canonical ASCII JSON for the exact materialization manifest."""

    return (
        _canonical_bytes(
            cpu_minimization_validation_materialization_manifest_document()
        )
        + b"\n"
    )


def write_cpu_minimization_validation_materialization_manifest_json(
    path: str | os.PathLike[str],
) -> Path:
    """Atomically write the result-free materialization manifest."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_name = handle.name
            handle.write(
                cpu_minimization_validation_materialization_manifest_json_bytes()
            )
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary_name, 0o644)
        os.replace(temporary_name, destination)
        temporary_name = None
    finally:
        if temporary_name is not None:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
    return destination


__all__ = [
    "CPU_MINIMIZATION_VALIDATION_MATERIALIZER_ID",
    "CPU_MINIMIZATION_VALIDATION_MATERIALIZER_SCHEMA_ID",
    "CPU_MINIMIZATION_VALIDATION_MATERIALIZER_VERSION",
    "CPUMinimizationValidationMaterializationError",
    "FROZEN_CPU_MINIMIZATION_VALIDATION_PROTOCOL_SHA256",
    "MATERIALIZER_BACKTRACK_FACTOR",
    "MATERIALIZER_CONSTRAINT_TOLERANCE_ANGSTROM",
    "MATERIALIZER_FORCE_TOLERANCE_KCAL_PER_MOL_ANGSTROM",
    "MATERIALIZER_MAXIMUM_ATOM_DISPLACEMENT_ANGSTROM",
    "MaterializedCPUMinimizationValidationCase",
    "cpu_minimization_validation_materialization_manifest_document",
    "cpu_minimization_validation_materialization_manifest_json_bytes",
    "cpu_minimization_validation_materializer_source_sha256",
    "materialize_frozen_cpu_minimization_validation_case",
    "write_cpu_minimization_validation_materialization_manifest_json",
]
