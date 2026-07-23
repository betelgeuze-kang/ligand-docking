"""Claim-closed OpenMM Reference comparison for the bounded NVE path.

This module is an offline evidence adapter.  It does not alter or replace the
source-bound reference NVE, SHAKE/RATTLE, or direct-Ewald implementations.  The
OpenMM system uses independent force expressions and OpenMM's documented
velocity-Verlet/RATTLE ``CustomIntegrator`` sequence on the pinned Reference
platform.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
import hashlib
from importlib import import_module
import json
import math
import os
from pathlib import Path
import platform
import stat
import struct
from typing import Any, Mapping, Sequence

import torch

from betelgeuze_engine_v2.geometry import (
    RadiusGraphConfig,
    build_compact_radius_graph,
)
from betelgeuze_engine_v2.molecular import (
    AllAtomSystem,
    Atom,
    Bond,
    Chain,
    Residue,
    StructureProvenance,
    UnitCell,
    atomic_number_for_element,
    canonical_system_sha256,
    canonical_topology_sha256,
)
from betelgeuze_engine_v2.offline.openmm_reference_oracle import (
    OPENMM_REFERENCE_REQUIRED_PLATFORM,
    OPENMM_REFERENCE_REQUIRED_DISTRIBUTION_VERSION,
    OPENMM_REFERENCE_REQUIRED_FULL_VERSION,
    OPENMM_REFERENCE_REQUIRED_GIT_REVISION,
    observe_openmm_reference_runtime_identity,
    require_openmm_reference_runtime_identity_document,
)
from betelgeuze_engine_v2.physics import (
    COULOMB_KCAL_ANGSTROM_PER_MOL_E2,
    REFERENCE_EWALD_ALGORITHM_ID,
    REFERENCE_NVE_ALGORITHM_ID,
    REFERENCE_SHAKE_RATTLE_ALGORITHM_ID,
    AtomNonbondedParameter,
    HarmonicAngleParameter,
    HarmonicBondParameter,
    ReferenceEwaldConfig,
    ReferenceForceFieldParameters,
    ReferenceNVEConfig,
    ReferenceNVEError,
    ReferenceSHAKERATTLEConfig,
    ReferenceSHAKERATTLEDistanceConstraint,
    evaluate_reference_force_field_with_ewald,
    observe_reference_position_constraints,
    observe_reference_velocity_constraints,
    resume_reference_nve,
    run_reference_nve,
    validate_reference_shake_rattle_inputs,
)


OPENMM_REFERENCE_NVE_TRAJECTORY_PROTOCOL_ID = (
    "betelgeuze.engine_v2_openmm_reference_nve_trajectory/1.0.0"
)
OPENMM_REFERENCE_NVE_TRAJECTORY_CONFIG_SCHEMA_ID = (
    "betelgeuze.engine_v2_openmm_reference_nve_trajectory_config/1.0.0"
)
OPENMM_REFERENCE_NVE_TRAJECTORY_OBSERVATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_openmm_reference_nve_trajectory_observation/1.0.0"
)
OPENMM_REFERENCE_NVE_TRAJECTORY_STATE_SCHEMA_ID = (
    "betelgeuze.engine_v2_openmm_reference_nve_state/1.0.0"
)
OPENMM_REFERENCE_NVE_TRAJECTORY_CASE_SCHEMA_ID = (
    "betelgeuze.engine_v2_openmm_reference_nve_case/1.0.0"
)

# Filled after the input-only projection is reviewed.  It binds cases,
# algorithms, failure dispositions, metrics, thresholds, and claim gates.
FROZEN_OPENMM_REFERENCE_NVE_TRAJECTORY_CONFIG_SHA256 = (
    "2beca32683c0393666cc1c3b5a136bed3416f774b0db631133a04bb43928871e"
)

OPENMM_REFERENCE_NVE_ENERGY_ERROR_THRESHOLD_KCAL_PER_MOL = 1.0e-9
OPENMM_REFERENCE_NVE_FORCE_MAX_ERROR_THRESHOLD_KCAL_PER_MOL_ANGSTROM = 1.0e-7
OPENMM_REFERENCE_NVE_FORCE_RMS_ERROR_THRESHOLD_KCAL_PER_MOL_ANGSTROM = 1.0e-8
OPENMM_REFERENCE_NVE_COORDINATE_ERROR_THRESHOLD_ANGSTROM = 1.0e-7
OPENMM_REFERENCE_NVE_VELOCITY_ERROR_THRESHOLD_ANGSTROM_PER_PS = 1.0e-6
OPENMM_REFERENCE_NVE_POSITION_CONSTRAINT_THRESHOLD_ANGSTROM = 1.0e-9
OPENMM_REFERENCE_NVE_VELOCITY_CONSTRAINT_THRESHOLD_ANGSTROM_PER_PS = 1.0e-8
OPENMM_REFERENCE_NVE_DRIFT_THRESHOLD_KCAL_PER_MOL = 1.0e-6
OPENMM_REFERENCE_NVE_RESTART_COORDINATE_THRESHOLD_ANGSTROM = 1.0e-12
OPENMM_REFERENCE_NVE_RESTART_VELOCITY_THRESHOLD_ANGSTROM_PER_PS = 1.0e-11
OPENMM_REFERENCE_NVE_RESTART_ENERGY_THRESHOLD_KCAL_PER_MOL = 1.0e-12
OPENMM_REFERENCE_NVE_MAX_OBSERVATION_BYTES = 8 * 1024**2
OPENMM_REFERENCE_NVE_MAX_ATOMS = 16
OPENMM_REFERENCE_NVE_OPENMM_CONSTRAINT_TOLERANCE_RELATIVE = 1.0e-12

_KJ_PER_KCAL = 4.184
_NM_PER_ANGSTROM = 0.1
_KJ_PER_NM_TO_KCAL_PER_ANGSTROM = 41.84

_SWITCH_COORDINATE = "min(1,max(0,(r-rs)/(rc-rs)))"
_OPENMM_LJ_EXPRESSION = (
    "scale*4*epsilon*((sigma/r)^12-(sigma/r)^6)*"
    f"(1-10*({_SWITCH_COORDINATE})^3+15*({_SWITCH_COORDINATE})^4-"
    f"6*({_SWITCH_COORDINATE})^5)"
)
_OPENMM_EWAL_REAL_AND_PAIR_CORRECTION_EXPRESSION = (
    "coulomb*qprod*("
    "scale*step(rc-r)*(erfc(alpha*r)/r-erfc(alpha*rc)/rc)"
    "+(scale-1)*erf(alpha*r)/r)"
)
_OPENMM_VELOCITY_VERLET_RATTLE_SEQUENCE = (
    ("addPerDofVariable", "x1", "0"),
    ("addUpdateContextState",),
    ("addComputePerDof", "v", "v+0.5*dt*f/m"),
    ("addComputePerDof", "x", "x+dt*v"),
    ("addComputePerDof", "x1", "x"),
    ("addConstrainPositions",),
    ("addComputePerDof", "v", "v+0.5*dt*f/m+(x-x1)/dt"),
    ("addConstrainVelocities",),
)

OPENMM_REFERENCE_NVE_TRAJECTORY_SCIENTIFIC_BLOCKERS = (
    "single local CPU host observation only",
    "OpenMM Reference is an offline implementation comparison, not a production dependency",
    "finite direct-Ewald lattice only; PME is not implemented or validated",
    "require-neutral orthorhombic scope only; no background charge or triclinic cell",
    "OpenMM constraint-solver iteration counts are not exposed by the runtime",
    "no GPU parity, long-time drift study, ensemble validation, or independent review",
)


class OpenMMReferenceNVETrajectoryError(RuntimeError):
    """The frozen comparison contract or one observation is invalid."""


@dataclass(frozen=True)
class _TrajectoryCase:
    case_id: str
    system: AllAtomSystem
    parameters: ReferenceForceFieldParameters
    velocities: torch.Tensor
    nve_config: ReferenceNVEConfig
    constraint_config: ReferenceSHAKERATTLEConfig
    steps: int
    restart_step: int


def _canonical_bytes(value: object) -> bytes:
    try:
        return (
            json.dumps(
                value,
                allow_nan=False,
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise OpenMMReferenceNVETrajectoryError(
            "comparison payload is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _require_sha256(value: object, *, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise OpenMMReferenceNVETrajectoryError(
            f"{name} must be a lowercase SHA-256 digest"
        )
    return value


def _finite(value: object, *, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise OpenMMReferenceNVETrajectoryError(f"{name} must be a finite float")
    result = float(value)
    if not math.isfinite(result):
        raise OpenMMReferenceNVETrajectoryError(f"{name} must be a finite float")
    return result


def _hex_rows(value: torch.Tensor | Sequence[Sequence[object]]) -> list[list[str]]:
    rows = (
        value.detach().to(dtype=torch.float64, device="cpu").tolist()
        if isinstance(value, torch.Tensor)
        else value
    )
    result: list[list[str]] = []
    for row_index, row in enumerate(rows):
        if not isinstance(row, Sequence) or len(row) != 3:
            raise OpenMMReferenceNVETrajectoryError(
                f"three-vector row {row_index} is invalid"
            )
        result.append(
            [
                _finite(item, name=f"three-vector row {row_index}").hex()
                for item in row
            ]
        )
    return result


def _rows_from_hex(
    value: object,
    *,
    atom_count: int,
    name: str,
) -> tuple[tuple[float, float, float], ...]:
    if not isinstance(value, list) or len(value) != atom_count:
        raise OpenMMReferenceNVETrajectoryError(f"{name} atom count is invalid")
    result: list[tuple[float, float, float]] = []
    for row_index, row in enumerate(value):
        if not isinstance(row, list) or len(row) != 3:
            raise OpenMMReferenceNVETrajectoryError(
                f"{name}[{row_index}] must be a three-vector"
            )
        parsed: list[float] = []
        for column_index, item in enumerate(row):
            if not isinstance(item, str):
                raise OpenMMReferenceNVETrajectoryError(
                    f"{name}[{row_index}][{column_index}] is not hexadecimal"
                )
            try:
                number = float.fromhex(item)
            except ValueError:
                raise OpenMMReferenceNVETrajectoryError(
                    f"{name}[{row_index}][{column_index}] is not hexadecimal"
                ) from None
            if not math.isfinite(number) or number.hex() != item:
                raise OpenMMReferenceNVETrajectoryError(
                    f"{name}[{row_index}][{column_index}] is not canonical binary64"
                )
            parsed.append(number)
        result.append((parsed[0], parsed[1], parsed[2]))
    return tuple(result)


def _tensor_f64le_sha256(value: Sequence[Sequence[float]]) -> str:
    payload = bytearray(8 * 3 * len(value))
    offset = 0
    for row in value:
        for item in row:
            struct.pack_into("<d", payload, offset, float(item))
            offset += 8
    return hashlib.sha256(payload).hexdigest()


def _water_geometry() -> tuple[tuple[float, float, float], ...]:
    return (
        (5.0, 5.0, 5.0),
        (float.fromhex("0x1.7d42c3c9eecc0p+2"), 5.0, 5.0),
        (
            float.fromhex("0x1.30a40cb11b30fp+2"),
            float.fromhex("0x1.7b4ddc32dc3c7p+2"),
            5.0,
        ),
    )


def _system(
    *,
    system_id: str,
    names: tuple[str, ...],
    elements: tuple[str, ...],
    masses: tuple[float | None, ...],
    charges: tuple[float, ...],
    coordinates: tuple[tuple[float, float, float], ...],
    bonds: tuple[tuple[int, int], ...],
    cell: UnitCell | None,
) -> AllAtomSystem:
    atoms = tuple(
        Atom(
            index=index,
            name=names[index],
            element=elements[index],
            atomic_number=atomic_number_for_element(elements[index]),
            residue_index=0,
            partial_charge_e=charges[index],
            mass_da=masses[index],
        )
        for index in range(len(names))
    )
    return AllAtomSystem(
        system_id=system_id,
        atoms=atoms,
        bonds=tuple(
            Bond(index=index, atom_i=pair[0], atom_j=pair[1])
            for index, pair in enumerate(bonds)
        ),
        residues=(
            Residue(
                index=0,
                name="SYS",
                chain_index=0,
                sequence_number=1,
                atom_indices=tuple(range(len(atoms))),
                entity_type="non-polymer",
                hetero=True,
            ),
        ),
        chains=(Chain(index=0, chain_id="A", residue_indices=(0,)),),
        coordinates=torch.tensor((coordinates,), dtype=torch.float64),
        provenance=StructureProvenance(source_format="frozen-offline-protocol"),
        cell=cell,
    )


def _materialize_cases() -> tuple[_TrajectoryCase, ...]:
    cell = UnitCell.orthorhombic((12.0, 12.0, 12.0), dtype=torch.float64)
    ewald = ReferenceEwaldConfig(
        alpha_per_angstrom=0.35,
        reciprocal_max_indices=(2, 2, 2),
    )
    nve = ReferenceNVEConfig(
        timestep_ps=1.0e-4,
        trajectory_stride=1,
        ewald_config=ewald,
    )

    ion_charges = (0.25, -0.25)
    ion_system = _system(
        system_id="openmm-reference-nve-ion-pair",
        names=("NA", "CL"),
        elements=("Na", "Cl"),
        masses=(22.98976928, 35.45),
        charges=ion_charges,
        coordinates=((3.0, 6.0, 6.0), (7.0, 6.0, 6.0)),
        bonds=(),
        cell=cell,
    )
    ion_parameters = ReferenceForceFieldParameters(
        parameter_set_id="openmm-reference-nve-ion-pair",
        parameter_set_version="1.0.0",
        topology_sha256=canonical_topology_sha256(ion_system),
        atom_parameters=tuple(
            AtomNonbondedParameter(
                atom_index=index,
                sigma_angstrom=3.0,
                epsilon_kcal_per_mol=0.05,
                charge_e=charge,
            )
            for index, charge in enumerate(ion_charges)
        ),
        cutoff_angstrom=5.0,
        switch_start_angstrom=4.0,
    )

    water_coordinates = _water_geometry()
    water_charges = (-0.834, 0.417, 0.417)
    water_system = _system(
        system_id="openmm-reference-nve-constrained-water",
        names=("O", "H1", "H2"),
        elements=("O", "H", "H"),
        masses=(15.9994, 1.008, 1.008),
        charges=water_charges,
        coordinates=water_coordinates,
        bonds=((0, 1), (0, 2)),
        cell=cell,
    )
    water_parameters = ReferenceForceFieldParameters(
        parameter_set_id="openmm-reference-nve-constrained-water",
        parameter_set_version="1.0.0",
        topology_sha256=canonical_topology_sha256(water_system),
        atom_parameters=(
            AtomNonbondedParameter(0, 3.15061, 0.1521, water_charges[0]),
            AtomNonbondedParameter(1, 1.0, 0.0, water_charges[1]),
            AtomNonbondedParameter(2, 1.0, 0.0, water_charges[2]),
        ),
        bonds=(
            HarmonicBondParameter(0, 1, 0.9572, 450.0),
            HarmonicBondParameter(0, 2, 0.9572, 450.0),
        ),
        angles=(
            HarmonicAngleParameter(
                atom_i=1,
                atom_j=0,
                atom_k=2,
                equilibrium_radians=float.fromhex(
                    "0x1.d2fff5ab17aafp+0"
                ),
                force_constant_kcal_per_mol_radian2=50.0,
            ),
        ),
        excluded_pairs=((0, 1), (0, 2), (1, 2)),
        cutoff_angstrom=5.0,
        switch_start_angstrom=4.0,
    )
    water_constraints = ReferenceSHAKERATTLEConfig(
        constraints=(
            ReferenceSHAKERATTLEDistanceConstraint(
                0,
                1,
                0.9572,
                tolerance_angstrom=1.0e-10,
            ),
            ReferenceSHAKERATTLEDistanceConstraint(
                0,
                2,
                0.9572,
                tolerance_angstrom=1.0e-10,
            ),
        ),
        velocity_tolerance_angstrom_per_ps=1.0e-10,
    )
    return (
        _TrajectoryCase(
            case_id="neutral_ion_pair_unconstrained",
            system=ion_system,
            parameters=ion_parameters,
            velocities=torch.tensor(
                (((0.0, 0.02, 0.0), (0.0, -0.01, 0.0)),),
                dtype=torch.float64,
            ),
            nve_config=nve,
            constraint_config=ReferenceSHAKERATTLEConfig(),
            steps=16,
            restart_step=7,
        ),
        _TrajectoryCase(
            case_id="neutral_water_coupled_oh_constraints",
            system=water_system,
            parameters=water_parameters,
            velocities=torch.tensor(
                (
                    (
                        (0.001, -0.002, 0.003),
                        (0.001, -0.002, 0.023),
                        (0.001, -0.002, -0.012),
                    ),
                ),
                dtype=torch.float64,
            ),
            nve_config=nve,
            constraint_config=water_constraints,
            steps=16,
            restart_step=7,
        ),
    )


def _case_input_document(case: _TrajectoryCase) -> dict[str, object]:
    system = case.system
    return {
        "case_id": case.case_id,
        "source_system_sha256": canonical_system_sha256(system),
        "topology_sha256": canonical_topology_sha256(system),
        "atom_rows": [
            {
                "index": atom.index,
                "name": atom.name,
                "element": atom.element,
                "mass_da_hex": (
                    None if atom.mass_da is None else float(atom.mass_da).hex()
                ),
                "partial_charge_e_hex": (
                    None
                    if atom.partial_charge_e is None
                    else float(atom.partial_charge_e).hex()
                ),
            }
            for atom in system.atoms
        ],
        "bond_rows": [
            [bond.atom_i, bond.atom_j] for bond in system.bonds
        ],
        "coordinates_angstrom_hex": _hex_rows(system.coordinates[0]),
        "velocities_angstrom_per_ps_hex": _hex_rows(case.velocities[0]),
        "cell_vectors_angstrom_hex": (
            None if system.cell is None else _hex_rows(system.cell.vectors)
        ),
        "parameter_document": case.parameters.to_dict(),
        "nve_config": case.nve_config.to_dict(),
        "constraint_config": case.constraint_config.to_dict(),
        "steps": case.steps,
        "restart_step": case.restart_step,
    }


def _configuration_projection() -> dict[str, object]:
    thresholds = {
        "same_coordinate_energy_max_abs_kcal_per_mol": (
            OPENMM_REFERENCE_NVE_ENERGY_ERROR_THRESHOLD_KCAL_PER_MOL
        ),
        "same_coordinate_force_max_abs_kcal_per_mol_angstrom": (
            OPENMM_REFERENCE_NVE_FORCE_MAX_ERROR_THRESHOLD_KCAL_PER_MOL_ANGSTROM
        ),
        "same_coordinate_force_rms_kcal_per_mol_angstrom": (
            OPENMM_REFERENCE_NVE_FORCE_RMS_ERROR_THRESHOLD_KCAL_PER_MOL_ANGSTROM
        ),
        "trajectory_coordinate_max_abs_angstrom": (
            OPENMM_REFERENCE_NVE_COORDINATE_ERROR_THRESHOLD_ANGSTROM
        ),
        "trajectory_velocity_max_abs_angstrom_per_ps": (
            OPENMM_REFERENCE_NVE_VELOCITY_ERROR_THRESHOLD_ANGSTROM_PER_PS
        ),
        "position_constraint_max_abs_angstrom": (
            OPENMM_REFERENCE_NVE_POSITION_CONSTRAINT_THRESHOLD_ANGSTROM
        ),
        "velocity_constraint_max_abs_angstrom_per_ps": (
            OPENMM_REFERENCE_NVE_VELOCITY_CONSTRAINT_THRESHOLD_ANGSTROM_PER_PS
        ),
        "per_implementation_energy_drift_max_abs_kcal_per_mol": (
            OPENMM_REFERENCE_NVE_DRIFT_THRESHOLD_KCAL_PER_MOL
        ),
        "openmm_restart_coordinate_max_abs_angstrom": (
            OPENMM_REFERENCE_NVE_RESTART_COORDINATE_THRESHOLD_ANGSTROM
        ),
        "openmm_restart_velocity_max_abs_angstrom_per_ps": (
            OPENMM_REFERENCE_NVE_RESTART_VELOCITY_THRESHOLD_ANGSTROM_PER_PS
        ),
        "openmm_restart_total_energy_max_abs_kcal_per_mol": (
            OPENMM_REFERENCE_NVE_RESTART_ENERGY_THRESHOLD_KCAL_PER_MOL
        ),
    }
    return {
        "schema_id": OPENMM_REFERENCE_NVE_TRAJECTORY_CONFIG_SCHEMA_ID,
        "protocol_id": OPENMM_REFERENCE_NVE_TRAJECTORY_PROTOCOL_ID,
        "operational_algorithms": {
            "nve": REFERENCE_NVE_ALGORITHM_ID,
            "shake_rattle": REFERENCE_SHAKE_RATTLE_ALGORITHM_ID,
            "direct_ewald": REFERENCE_EWALD_ALGORITHM_ID,
        },
        "oracle": {
            "distribution_version": OPENMM_REFERENCE_REQUIRED_DISTRIBUTION_VERSION,
            "full_version": OPENMM_REFERENCE_REQUIRED_FULL_VERSION,
            "git_revision": OPENMM_REFERENCE_REQUIRED_GIT_REVISION,
            "platform": OPENMM_REFERENCE_REQUIRED_PLATFORM,
            "integrator": "OpenMM documented velocity-Verlet/RATTLE CustomIntegrator",
            "integrator_sequence": [list(row) for row in _OPENMM_VELOCITY_VERLET_RATTLE_SEQUENCE],
            "constraint_tolerance_relative_hex": (
                OPENMM_REFERENCE_NVE_OPENMM_CONSTRAINT_TOLERANCE_RELATIVE.hex()
            ),
            "electrostatics_mapping": (
                "independent shifted-real plus pair correction plus "
                "half-lattice cosine reciprocal decomposition plus self term"
            ),
            "lj_expression_sha256": hashlib.sha256(
                _OPENMM_LJ_EXPRESSION.encode("ascii")
            ).hexdigest(),
            "ewald_real_pair_expression_sha256": hashlib.sha256(
                _OPENMM_EWAL_REAL_AND_PAIR_CORRECTION_EXPRESSION.encode("ascii")
            ).hexdigest(),
        },
        "case_order": [
            "neutral_ion_pair_unconstrained",
            "neutral_water_coupled_oh_constraints",
        ],
        "cases": [_case_input_document(case) for case in _materialize_cases()],
        "failure_rows": [
            {
                "case_id": "nonperiodic_direct_ewald",
                "expected_engine_code": "fully_periodic_required",
                "expected_oracle_code": "fully_periodic_required",
            },
            {
                "case_id": "net_charged_direct_ewald",
                "expected_engine_code": "neutrality_required",
                "expected_oracle_code": "neutrality_required",
            },
            {
                "case_id": "triclinic_direct_ewald",
                "expected_engine_code": "orthorhombic_required",
                "expected_oracle_code": "orthorhombic_required",
            },
        ],
        "thresholds": {
            key: value.hex() for key, value in thresholds.items()
        },
        "required_evidence": [
            "term energy error",
            "force max and RMS error",
            "position and velocity constraint residual",
            "every-step energy, coordinate, velocity, and force trace",
            "operational exact checkpoint/restart equality",
            "OpenMM split-run restart comparison",
            "all failure rows",
            "source, binary, environment, and dependency identity",
        ],
        "claim_gates": {
            "single_host_can_validate": False,
            "scientifically_validated": False,
            "production_eligible": False,
            "claim_safe": False,
        },
    }


def openmm_reference_nve_trajectory_configuration_document() -> dict[str, object]:
    projection = _configuration_projection()
    digest = _sha256(projection)
    if digest != FROZEN_OPENMM_REFERENCE_NVE_TRAJECTORY_CONFIG_SHA256:
        raise OpenMMReferenceNVETrajectoryError(
            "OpenMM NVE trajectory configuration digest drifted"
        )
    return {**projection, "configuration_sha256": digest}


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _hash_regular_file(
    path: Path,
    *,
    maximum_bytes: int = 512 * 1024**2,
) -> dict[str, object]:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise OpenMMReferenceNVETrajectoryError(
            "source or dependency identity file is unavailable"
        ) from exc
    if not stat.S_ISREG(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
        raise OpenMMReferenceNVETrajectoryError(
            "source or dependency identity requires a regular non-symlink file"
        )
    if metadata.st_size < 0 or metadata.st_size > maximum_bytes:
        raise OpenMMReferenceNVETrajectoryError(
            "source or dependency identity file exceeds its bound"
        )
    digest = hashlib.sha256()
    observed = 0
    with path.open("rb") as handle:
        while True:
            block = handle.read(1024**2)
            if not block:
                break
            observed += len(block)
            if observed > maximum_bytes:
                raise OpenMMReferenceNVETrajectoryError(
                    "source or dependency identity file exceeded its bound"
                )
            digest.update(block)
    if observed != metadata.st_size:
        raise OpenMMReferenceNVETrajectoryError(
            "source or dependency identity changed while hashing"
        )
    return {"sha256": digest.hexdigest(), "size": observed}


def _source_identity_document() -> dict[str, object]:
    root = _repository_root()
    relative_paths = (
        "betelgeuze_engine_v2/offline/openmm_reference_nve_trajectory.py",
        "betelgeuze_engine_v2/offline/openmm_reference_oracle.py",
        "betelgeuze_engine_v2/physics/reference_nve.py",
        "betelgeuze_engine_v2/physics/reference_ewald.py",
        "betelgeuze_engine_v2/physics/reference_shake_rattle.py",
        "betelgeuze_engine_v2/physics/reference_parameters.py",
    )
    source_rows = []
    for relative in relative_paths:
        source_rows.append(
            {"path": relative, **_hash_regular_file(root / relative)}
        )
    torch_wrapper = Path(torch.__file__).resolve(strict=True)
    torch_native_module = import_module("torch._C")
    torch_native = Path(torch_native_module.__file__).resolve(strict=True)
    dependencies = {
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "torch_version": str(torch.__version__),
        "torch_wrapper": _hash_regular_file(torch_wrapper),
        "torch_native_extension": _hash_regular_file(torch_native),
    }
    projection = {
        "source_files": source_rows,
        "source_manifest_sha256": _sha256(source_rows),
        "dependencies": dependencies,
        "dependency_identity_sha256": _sha256(dependencies),
        "absolute_paths_disclosed": False,
    }
    return {**projection, "source_identity_sha256": _sha256(projection)}


def _require_case_domain(case: _TrajectoryCase) -> tuple[float, float, float]:
    system = case.system
    if system.model_count != 1 or system.atom_count > OPENMM_REFERENCE_NVE_MAX_ATOMS:
        raise OpenMMReferenceNVETrajectoryError(
            "oracle case requires one bounded coordinate model"
        )
    if system.cell is None or system.cell.periodic != (True, True, True):
        raise OpenMMReferenceNVETrajectoryError(
            "oracle direct Ewald requires a fully periodic cell"
        )
    try:
        lengths = system.cell.orthorhombic_lengths().tolist()
    except ValueError as exc:
        raise OpenMMReferenceNVETrajectoryError(
            "oracle direct Ewald requires an orthorhombic cell"
        ) from exc
    if case.nve_config.ewald_config is None:
        raise OpenMMReferenceNVETrajectoryError(
            "oracle comparison requires direct Ewald"
        )
    if case.parameters.screening_kappa_per_angstrom != 0.0:
        raise OpenMMReferenceNVETrajectoryError(
            "oracle direct Ewald requires zero screened-Coulomb kappa"
        )
    if case.parameters.cutoff_angstrom >= 0.5 * min(lengths):
        raise OpenMMReferenceNVETrajectoryError(
            "oracle direct Ewald cutoff exceeds the minimum-image bound"
        )
    atom_map = case.parameters.atom_parameter_map
    if set(atom_map) != set(range(system.atom_count)):
        raise OpenMMReferenceNVETrajectoryError(
            "oracle atom parameters do not cover the system"
        )
    if any(atom.mass_da is None or atom.mass_da <= 0.0 for atom in system.atoms):
        raise OpenMMReferenceNVETrajectoryError(
            "oracle dynamics requires positive explicit masses"
        )
    total_charge = math.fsum(
        atom_map[index].charge_e for index in range(system.atom_count)
    )
    if abs(total_charge) > case.nve_config.ewald_config.neutrality_tolerance_e:
        raise OpenMMReferenceNVETrajectoryError(
            "oracle direct Ewald requires a neutral system"
        )
    masses = torch.tensor(
        [float(atom.mass_da) for atom in system.atoms],
        dtype=torch.float64,
    )
    try:
        validate_reference_shake_rattle_inputs(
            system,
            masses,
            case.constraint_config,
        )
    except Exception as exc:
        raise OpenMMReferenceNVETrajectoryError(
            "oracle constraint applicability failed closed"
        ) from exc
    return float(lengths[0]), float(lengths[1]), float(lengths[2])


def _half_reciprocal_vectors(
    ewald: ReferenceEwaldConfig,
    lengths: tuple[float, float, float],
) -> tuple[tuple[tuple[float, float, float], float], ...]:
    limits = ewald.reciprocal_max_indices
    rows: list[tuple[tuple[float, float, float], float]] = []
    for first in range(-limits[0], limits[0] + 1):
        for second in range(-limits[1], limits[1] + 1):
            for third in range(-limits[2], limits[2] + 1):
                integers = (first, second, third)
                if integers == (0, 0, 0):
                    continue
                leading = next(value for value in integers if value != 0)
                if leading < 0:
                    continue
                vector = tuple(
                    2.0 * math.pi * integer / length
                    for integer, length in zip(integers, lengths)
                )
                norm2 = math.fsum(component * component for component in vector)
                weight = math.exp(
                    -norm2 / (4.0 * ewald.alpha_per_angstrom**2)
                ) / norm2
                rows.append((vector, weight))
    if 2 * len(rows) != ewald.reciprocal_vector_count:
        raise OpenMMReferenceNVETrajectoryError(
            "half reciprocal lattice does not cover the frozen full lattice"
        )
    return tuple(rows)


def _openmm_modules() -> tuple[dict[str, Any], Any, Any, Any]:
    runtime = observe_openmm_reference_runtime_identity()
    require_openmm_reference_runtime_identity_document(runtime)
    openmm = import_module("openmm")
    unit = import_module("openmm.unit")
    reference = openmm.Platform.getPlatformByName(
        OPENMM_REFERENCE_REQUIRED_PLATFORM
    )
    return runtime, openmm, unit, reference


def _build_openmm_system(
    case: _TrajectoryCase,
    *,
    openmm: Any,
) -> tuple[Any, dict[str, object]]:
    lengths = _require_case_domain(case)
    source = case.system
    parameters = case.parameters
    ewald = case.nve_config.ewald_config
    if ewald is None:
        raise OpenMMReferenceNVETrajectoryError(
            "oracle system construction requires direct Ewald"
        )
    result = openmm.System()
    for atom in source.atoms:
        result.addParticle(float(atom.mass_da))
    result.setDefaultPeriodicBoxVectors(
        openmm.Vec3(lengths[0] * _NM_PER_ANGSTROM, 0.0, 0.0),
        openmm.Vec3(0.0, lengths[1] * _NM_PER_ANGSTROM, 0.0),
        openmm.Vec3(0.0, 0.0, lengths[2] * _NM_PER_ANGSTROM),
    )

    bond_force = openmm.HarmonicBondForce()
    for row in parameters.bonds:
        bond_force.addBond(
            row.atom_i,
            row.atom_j,
            row.equilibrium_angstrom * _NM_PER_ANGSTROM,
            row.force_constant_kcal_per_mol_angstrom2
            * _KJ_PER_KCAL
            / (_NM_PER_ANGSTROM**2),
        )
    result.addForce(bond_force)

    angle_force = openmm.HarmonicAngleForce()
    for row in parameters.angles:
        angle_force.addAngle(
            row.atom_i,
            row.atom_j,
            row.atom_k,
            row.equilibrium_radians,
            row.force_constant_kcal_per_mol_radian2 * _KJ_PER_KCAL,
        )
    result.addForce(angle_force)

    torsion_force = openmm.PeriodicTorsionForce()
    for row in parameters.torsions:
        torsion_force.addTorsion(
            row.atom_i,
            row.atom_j,
            row.atom_k,
            row.atom_l,
            row.periodicity,
            row.phase_radians,
            row.amplitude_kcal_per_mol * _KJ_PER_KCAL,
        )
    result.addForce(torsion_force)

    lj_force = openmm.CustomBondForce(_OPENMM_LJ_EXPRESSION)
    for name in ("sigma", "epsilon", "scale"):
        lj_force.addPerBondParameter(name)
    lj_force.addGlobalParameter(
        "rs",
        parameters.switch_start_angstrom * _NM_PER_ANGSTROM,
    )
    lj_force.addGlobalParameter(
        "rc",
        parameters.cutoff_angstrom * _NM_PER_ANGSTROM,
    )
    lj_force.setUsesPeriodicBoundaryConditions(True)

    direct_force = openmm.CustomBondForce(
        _OPENMM_EWAL_REAL_AND_PAIR_CORRECTION_EXPRESSION
    )
    for name in ("qprod", "scale"):
        direct_force.addPerBondParameter(name)
    direct_force.addGlobalParameter(
        "coulomb",
        COULOMB_KCAL_ANGSTROM_PER_MOL_E2
        * _KJ_PER_KCAL
        * _NM_PER_ANGSTROM
        / parameters.dielectric,
    )
    direct_force.addGlobalParameter(
        "alpha",
        ewald.alpha_per_angstrom / _NM_PER_ANGSTROM,
    )
    direct_force.addGlobalParameter(
        "rc",
        parameters.cutoff_angstrom * _NM_PER_ANGSTROM,
    )
    direct_force.setUsesPeriodicBoundaryConditions(True)

    atom_map = parameters.atom_parameter_map
    scaling_map = parameters.pair_scaling_map
    excluded = set(parameters.excluded_pairs)
    pairs: list[tuple[int, int, float]] = []
    for atom_i in range(source.atom_count):
        for atom_j in range(atom_i + 1, source.atom_count):
            pair = (atom_i, atom_j)
            first = atom_map[atom_i]
            second = atom_map[atom_j]
            if pair in excluded:
                lj_scale, electrostatic_scale = 0.0, 0.0
            elif pair in scaling_map:
                scaling = scaling_map[pair]
                lj_scale = scaling.lj_scale
                electrostatic_scale = scaling.electrostatic_scale
            else:
                lj_scale, electrostatic_scale = 1.0, 1.0
            lj_force.addBond(
                atom_i,
                atom_j,
                [
                    0.5
                    * (first.sigma_angstrom + second.sigma_angstrom)
                    * _NM_PER_ANGSTROM,
                    math.sqrt(
                        first.epsilon_kcal_per_mol
                        * second.epsilon_kcal_per_mol
                    )
                    * _KJ_PER_KCAL,
                    lj_scale,
                ],
            )
            charge_product = first.charge_e * second.charge_e
            direct_force.addBond(
                atom_i,
                atom_j,
                [charge_product, electrostatic_scale],
            )
            pairs.append((atom_i, atom_j, charge_product))
    result.addForce(lj_force)
    result.addForce(direct_force)

    half_vectors = _half_reciprocal_vectors(ewald, lengths)
    volume = math.prod(lengths)
    reciprocal_terms: list[str] = []
    for vector, weight in half_vectors:
        wave_nm = tuple(
            component / _NM_PER_ANGSTROM for component in vector
        )
        coefficient = (
            COULOMB_KCAL_ANGSTROM_PER_MOL_E2
            / parameters.dielectric
            * (2.0 * math.pi / volume)
            * 4.0
            * weight
            * _KJ_PER_KCAL
        )
        reciprocal_terms.append(
            f"{coefficient:.17g}*cos("
            f"{wave_nm[0]:.17g}*(x1-x2)+"
            f"{wave_nm[1]:.17g}*(y1-y2)+"
            f"{wave_nm[2]:.17g}*(z1-z2))"
        )
    reciprocal_expression = "qprod*(" + "+".join(reciprocal_terms) + ")"
    reciprocal_force = openmm.CustomCompoundBondForce(
        2,
        reciprocal_expression,
    )
    reciprocal_force.addPerBondParameter("qprod")
    for atom_i, atom_j, charge_product in pairs:
        reciprocal_force.addBond(
            [atom_i, atom_j],
            [charge_product],
        )
    result.addForce(reciprocal_force)

    full_weight_sum = 2.0 * math.fsum(
        weight for _, weight in half_vectors
    )
    constant_coefficient = (
        COULOMB_KCAL_ANGSTROM_PER_MOL_E2
        / parameters.dielectric
        * (
            (2.0 * math.pi / volume) * full_weight_sum
            - ewald.alpha_per_angstrom / math.sqrt(math.pi)
        )
        * _KJ_PER_KCAL
    )
    constant_force = openmm.CustomExternalForce("coefficient*q2")
    constant_force.addGlobalParameter("coefficient", constant_coefficient)
    constant_force.addPerParticleParameter("q2")
    for atom_index in range(source.atom_count):
        charge = atom_map[atom_index].charge_e
        constant_force.addParticle(atom_index, [charge * charge])
    result.addForce(constant_force)

    for constraint in case.constraint_config.constraints:
        result.addConstraint(
            constraint.atom_i,
            constraint.atom_j,
            constraint.target_distance_angstrom * _NM_PER_ANGSTROM,
        )
    mapping = {
        "particle_count": result.getNumParticles(),
        "constraint_count": result.getNumConstraints(),
        "force_count": result.getNumForces(),
        "unique_pair_count": len(pairs),
        "full_reciprocal_vector_count": ewald.reciprocal_vector_count,
        "half_reciprocal_vector_count": len(half_vectors),
        "reciprocal_expression_sha256": hashlib.sha256(
            reciprocal_expression.encode("ascii")
        ).hexdigest(),
        "reciprocal_constant_kj_per_mol_e2_hex": constant_coefficient.hex(),
    }
    return result, mapping


def _openmm_integrator(openmm: Any, timestep_ps: float) -> Any:
    integrator = openmm.CustomIntegrator(timestep_ps)
    integrator.addPerDofVariable("x1", 0.0)
    integrator.addUpdateContextState()
    integrator.addComputePerDof("v", "v+0.5*dt*f/m")
    integrator.addComputePerDof("x", "x+dt*v")
    integrator.addComputePerDof("x1", "x")
    integrator.addConstrainPositions()
    integrator.addComputePerDof(
        "v",
        "v+0.5*dt*f/m+(x-x1)/dt",
    )
    integrator.addConstrainVelocities()
    integrator.setConstraintTolerance(
        OPENMM_REFERENCE_NVE_OPENMM_CONSTRAINT_TOLERANCE_RELATIVE
    )
    return integrator


def _constraint_residuals(
    case: _TrajectoryCase,
    coordinates: Sequence[Sequence[float]],
    velocities: Sequence[Sequence[float]],
) -> tuple[float, float]:
    coordinate_tensor = torch.tensor(
        (coordinates,),
        dtype=torch.float64,
    )
    velocity_tensor = torch.tensor(
        (velocities,),
        dtype=torch.float64,
    )
    position_rows = observe_reference_position_constraints(
        case.system,
        coordinate_tensor,
        case.constraint_config,
    )
    velocity_rows = observe_reference_velocity_constraints(
        case.system,
        coordinate_tensor,
        velocity_tensor,
        case.constraint_config,
    )
    return (
        max((abs(row.residual_angstrom) for row in position_rows), default=0.0),
        max(
            (
                abs(row.radial_relative_velocity_angstrom_per_ps)
                for row in velocity_rows
            ),
            default=0.0,
        ),
    )


def _openmm_state(
    *,
    context: Any,
    unit: Any,
    case: _TrajectoryCase,
    step: int,
) -> dict[str, object]:
    state = context.getState(
        getPositions=True,
        getVelocities=True,
        getForces=True,
        getEnergy=True,
    )
    positions_nm = state.getPositions().value_in_unit(unit.nanometer)
    velocities_nm_ps = state.getVelocities().value_in_unit(
        unit.nanometer / unit.picosecond
    )
    forces_kj_nm = state.getForces().value_in_unit(
        unit.kilojoule_per_mole / unit.nanometer
    )
    coordinates = tuple(
        tuple(float(value) / _NM_PER_ANGSTROM for value in row)
        for row in positions_nm
    )
    velocities = tuple(
        tuple(float(value) / _NM_PER_ANGSTROM for value in row)
        for row in velocities_nm_ps
    )
    forces = tuple(
        tuple(
            float(value) / _KJ_PER_NM_TO_KCAL_PER_ANGSTROM
            for value in row
        )
        for row in forces_kj_nm
    )
    potential = (
        float(
            state.getPotentialEnergy().value_in_unit(
                unit.kilojoule_per_mole
            )
        )
        / _KJ_PER_KCAL
    )
    kinetic = (
        float(
            state.getKineticEnergy().value_in_unit(
                unit.kilojoule_per_mole
            )
        )
        / _KJ_PER_KCAL
    )
    position_residual, velocity_residual = _constraint_residuals(
        case,
        coordinates,
        velocities,
    )
    projection = {
        "schema_id": OPENMM_REFERENCE_NVE_TRAJECTORY_STATE_SCHEMA_ID,
        "implementation": "openmm_reference",
        "step": step,
        "time_ps_hex": (step * case.nve_config.timestep_ps).hex(),
        "coordinates_angstrom_hex": _hex_rows(coordinates),
        "velocities_angstrom_per_ps_hex": _hex_rows(velocities),
        "potential_energy_kcal_per_mol_hex": potential.hex(),
        "kinetic_energy_kcal_per_mol_hex": kinetic.hex(),
        "total_energy_kcal_per_mol_hex": (potential + kinetic).hex(),
        "forces_kcal_per_mol_angstrom_hex": _hex_rows(forces),
        "position_constraint_residual_angstrom_hex": position_residual.hex(),
        "velocity_constraint_residual_angstrom_per_ps_hex": (
            velocity_residual.hex()
        ),
        "coordinate_f64le_sha256": _tensor_f64le_sha256(coordinates),
        "velocity_f64le_sha256": _tensor_f64le_sha256(velocities),
    }
    return {**projection, "state_sha256": _sha256(projection)}


class _OpenMMRunner:
    def __init__(
        self,
        *,
        openmm: Any,
        unit: Any,
        reference: Any,
        openmm_system: Any,
        case: _TrajectoryCase,
        coordinates: Sequence[Sequence[float]],
        velocities: Sequence[Sequence[float]],
        project_initial: bool,
    ) -> None:
        self._openmm = openmm
        self._unit = unit
        self._case = case
        self._integrator = _openmm_integrator(
            openmm,
            case.nve_config.timestep_ps,
        )
        self._context = openmm.Context(
            openmm_system,
            self._integrator,
            reference,
        )
        if (
            self._context.getPlatform().getName()
            != OPENMM_REFERENCE_REQUIRED_PLATFORM
        ):
            raise OpenMMReferenceNVETrajectoryError(
                "OpenMM trajectory context did not use the Reference platform"
            )
        self._context.setPositions(
            [
                openmm.Vec3(
                    row[0] * _NM_PER_ANGSTROM,
                    row[1] * _NM_PER_ANGSTROM,
                    row[2] * _NM_PER_ANGSTROM,
                )
                for row in coordinates
            ]
        )
        self._context.setVelocities(
            [
                openmm.Vec3(
                    row[0] * _NM_PER_ANGSTROM,
                    row[1] * _NM_PER_ANGSTROM,
                    row[2] * _NM_PER_ANGSTROM,
                )
                for row in velocities
            ]
        )
        if project_initial:
            self._context.applyConstraints(
                OPENMM_REFERENCE_NVE_OPENMM_CONSTRAINT_TOLERANCE_RELATIVE
            )
            self._context.applyVelocityConstraints(
                OPENMM_REFERENCE_NVE_OPENMM_CONSTRAINT_TOLERANCE_RELATIVE
            )
        self._step = 0

    def snapshot(self) -> dict[str, object]:
        return _openmm_state(
            context=self._context,
            unit=self._unit,
            case=self._case,
            step=self._step,
        )

    def step(self, count: int = 1) -> None:
        self._integrator.step(count)
        self._step += count

    def create_checkpoint(self) -> bytes:
        checkpoint = self._context.createCheckpoint()
        if not isinstance(checkpoint, bytes) or not checkpoint:
            raise OpenMMReferenceNVETrajectoryError(
                "OpenMM did not return a non-empty native checkpoint"
            )
        return checkpoint

    def load_checkpoint(self, checkpoint: bytes, *, step: int) -> None:
        if not isinstance(checkpoint, bytes) or not checkpoint:
            raise OpenMMReferenceNVETrajectoryError(
                "OpenMM native checkpoint transport is invalid"
            )
        self._context.loadCheckpoint(checkpoint)
        self._step = step

    def close(self) -> None:
        del self._context
        del self._integrator

    def __enter__(self) -> "_OpenMMRunner":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


class _OpenMMStaticEvaluator:
    def __init__(
        self,
        *,
        openmm: Any,
        unit: Any,
        reference: Any,
        openmm_system: Any,
        atom_count: int,
    ) -> None:
        self._openmm = openmm
        self._unit = unit
        self._atom_count = atom_count
        self._integrator = openmm.VerletIntegrator(0.0)
        self._context = openmm.Context(
            openmm_system,
            self._integrator,
            reference,
        )

    def evaluate(
        self,
        coordinates: Sequence[Sequence[float]],
    ) -> tuple[float, tuple[tuple[float, float, float], ...]]:
        if len(coordinates) != self._atom_count:
            raise OpenMMReferenceNVETrajectoryError(
                "static OpenMM coordinate atom count is invalid"
            )
        self._context.setPositions(
            [
                self._openmm.Vec3(
                    row[0] * _NM_PER_ANGSTROM,
                    row[1] * _NM_PER_ANGSTROM,
                    row[2] * _NM_PER_ANGSTROM,
                )
                for row in coordinates
            ]
        )
        state = self._context.getState(getEnergy=True, getForces=True)
        energy = (
            float(
                state.getPotentialEnergy().value_in_unit(
                    self._unit.kilojoule_per_mole
                )
            )
            / _KJ_PER_KCAL
        )
        values = state.getForces().value_in_unit(
            self._unit.kilojoule_per_mole / self._unit.nanometer
        )
        forces = tuple(
            tuple(
                float(item) / _KJ_PER_NM_TO_KCAL_PER_ANGSTROM
                for item in row
            )
            for row in values
        )
        return energy, forces

    def close(self) -> None:
        del self._context
        del self._integrator

    def __enter__(self) -> "_OpenMMStaticEvaluator":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def _engine_evaluate(
    case: _TrajectoryCase,
    coordinates: Sequence[Sequence[float]],
) -> tuple[float, tuple[tuple[float, float, float], ...]]:
    tensor = torch.tensor((coordinates,), dtype=torch.float64)
    current = replace(case.system, coordinates=tensor)
    neighbors = build_compact_radius_graph(
        tensor,
        RadiusGraphConfig(
            cutoff_angstrom=case.parameters.cutoff_angstrom,
            max_neighbors=case.nve_config.max_neighbors,
            max_atoms_per_cell=case.nve_config.max_atoms_per_cell,
        ),
        cell=current.cell,
    )
    ewald = case.nve_config.ewald_config
    if ewald is None:
        raise OpenMMReferenceNVETrajectoryError(
            "engine comparison requires direct Ewald"
        )
    evaluation = evaluate_reference_force_field_with_ewald(
        current,
        neighbors,
        case.parameters,
        ewald,
    )
    energy = float(evaluation.term.energy.reshape(-1)[0].item())
    forces = tuple(
        tuple(float(item) for item in row)
        for row in evaluation.term.forces[0].tolist()
    )
    return energy, forces


def _engine_state(
    case: _TrajectoryCase,
    frame: Any,
) -> dict[str, object]:
    coordinates = tuple(
        tuple(float(item) for item in row)
        for row in frame.coordinates[0].tolist()
    )
    velocities = tuple(
        tuple(float(item) for item in row)
        for row in frame.velocities_angstrom_per_ps[0].tolist()
    )
    energy, forces = _engine_evaluate(case, coordinates)
    if energy.hex() != frame.potential_energy_kcal_per_mol.hex():
        raise OpenMMReferenceNVETrajectoryError(
            "engine retained frame does not reproduce its potential energy"
        )
    position_residual, velocity_residual = _constraint_residuals(
        case,
        coordinates,
        velocities,
    )
    projection = {
        "schema_id": OPENMM_REFERENCE_NVE_TRAJECTORY_STATE_SCHEMA_ID,
        "implementation": "engine_reference",
        "step": frame.step,
        "time_ps_hex": frame.time_ps.hex(),
        "coordinates_angstrom_hex": _hex_rows(coordinates),
        "velocities_angstrom_per_ps_hex": _hex_rows(velocities),
        "potential_energy_kcal_per_mol_hex": energy.hex(),
        "kinetic_energy_kcal_per_mol_hex": (
            frame.kinetic_energy_kcal_per_mol.hex()
        ),
        "total_energy_kcal_per_mol_hex": (
            frame.total_energy_kcal_per_mol.hex()
        ),
        "forces_kcal_per_mol_angstrom_hex": _hex_rows(forces),
        "position_constraint_residual_angstrom_hex": position_residual.hex(),
        "velocity_constraint_residual_angstrom_per_ps_hex": (
            velocity_residual.hex()
        ),
        "coordinate_f64le_sha256": _tensor_f64le_sha256(coordinates),
        "velocity_f64le_sha256": _tensor_f64le_sha256(velocities),
    }
    return {**projection, "state_sha256": _sha256(projection)}


def _state_values(
    state: Mapping[str, object],
    *,
    atom_count: int,
) -> tuple[
    tuple[tuple[float, float, float], ...],
    tuple[tuple[float, float, float], ...],
    tuple[tuple[float, float, float], ...],
    float,
    float,
    float,
]:
    coordinates = _rows_from_hex(
        state["coordinates_angstrom_hex"],
        atom_count=atom_count,
        name="state coordinates",
    )
    velocities = _rows_from_hex(
        state["velocities_angstrom_per_ps_hex"],
        atom_count=atom_count,
        name="state velocities",
    )
    forces = _rows_from_hex(
        state["forces_kcal_per_mol_angstrom_hex"],
        atom_count=atom_count,
        name="state forces",
    )

    def number(field: str) -> float:
        value = state[field]
        if not isinstance(value, str):
            raise OpenMMReferenceNVETrajectoryError(
                f"state {field} is not hexadecimal"
            )
        try:
            result = float.fromhex(value)
        except ValueError:
            raise OpenMMReferenceNVETrajectoryError(
                f"state {field} is not hexadecimal"
            ) from None
        if not math.isfinite(result) or result.hex() != value:
            raise OpenMMReferenceNVETrajectoryError(
                f"state {field} is not canonical binary64"
            )
        return result

    return (
        coordinates,
        velocities,
        forces,
        number("potential_energy_kcal_per_mol_hex"),
        number("kinetic_energy_kcal_per_mol_hex"),
        number("total_energy_kcal_per_mol_hex"),
    )


def _vector_errors(
    first: Sequence[Sequence[float]],
    second: Sequence[Sequence[float]],
) -> tuple[float, float]:
    differences = [
        float(left) - float(right)
        for left_row, right_row in zip(first, second)
        for left, right in zip(left_row, right_row)
    ]
    if not differences:
        return 0.0, 0.0
    return (
        max(abs(value) for value in differences),
        math.sqrt(math.fsum(value * value for value in differences) / len(differences)),
    )


def _coordinate_error(
    first: Sequence[Sequence[float]],
    second: Sequence[Sequence[float]],
    lengths: tuple[float, float, float],
) -> float:
    values = []
    for first_row, second_row in zip(first, second):
        for axis, length in enumerate(lengths):
            difference = float(first_row[axis]) - float(second_row[axis])
            difference -= round(difference / length) * length
            values.append(abs(difference))
    return max(values, default=0.0)


def _comparison_row(
    *,
    case: _TrajectoryCase,
    engine_state: Mapping[str, object],
    openmm_state: Mapping[str, object],
    static_openmm: _OpenMMStaticEvaluator,
) -> dict[str, object]:
    atom_count = case.system.atom_count
    (
        engine_coordinates,
        engine_velocities,
        engine_forces,
        engine_potential,
        _,
        engine_total,
    ) = _state_values(engine_state, atom_count=atom_count)
    (
        openmm_coordinates,
        openmm_velocities,
        openmm_forces,
        openmm_potential,
        _,
        openmm_total,
    ) = _state_values(openmm_state, atom_count=atom_count)
    openmm_at_engine_energy, openmm_at_engine_forces = static_openmm.evaluate(
        engine_coordinates
    )
    engine_at_openmm_energy, engine_at_openmm_forces = _engine_evaluate(
        case,
        openmm_coordinates,
    )
    engine_coordinate_force_max, engine_coordinate_force_rms = _vector_errors(
        engine_forces,
        openmm_at_engine_forces,
    )
    openmm_coordinate_force_max, openmm_coordinate_force_rms = _vector_errors(
        engine_at_openmm_forces,
        openmm_forces,
    )
    lengths = tuple(
        float(value)
        for value in case.system.cell.orthorhombic_lengths().tolist()
    )
    coordinate_error = _coordinate_error(
        engine_coordinates,
        openmm_coordinates,
        lengths,
    )
    velocity_error, _ = _vector_errors(
        engine_velocities,
        openmm_velocities,
    )
    projection = {
        "step": int(engine_state["step"]),
        "engine_at_engine_coordinates": {
            "engine_energy_kcal_per_mol_hex": engine_potential.hex(),
            "openmm_energy_kcal_per_mol_hex": openmm_at_engine_energy.hex(),
            "energy_max_abs_error_kcal_per_mol_hex": abs(
                engine_potential - openmm_at_engine_energy
            ).hex(),
            "engine_forces_kcal_per_mol_angstrom_hex": _hex_rows(
                engine_forces
            ),
            "openmm_forces_kcal_per_mol_angstrom_hex": _hex_rows(
                openmm_at_engine_forces
            ),
            "force_max_abs_error_kcal_per_mol_angstrom_hex": (
                engine_coordinate_force_max.hex()
            ),
            "force_rms_error_kcal_per_mol_angstrom_hex": (
                engine_coordinate_force_rms.hex()
            ),
        },
        "engine_at_openmm_coordinates": {
            "engine_energy_kcal_per_mol_hex": engine_at_openmm_energy.hex(),
            "openmm_energy_kcal_per_mol_hex": openmm_potential.hex(),
            "energy_max_abs_error_kcal_per_mol_hex": abs(
                engine_at_openmm_energy - openmm_potential
            ).hex(),
            "engine_forces_kcal_per_mol_angstrom_hex": _hex_rows(
                engine_at_openmm_forces
            ),
            "openmm_forces_kcal_per_mol_angstrom_hex": _hex_rows(
                openmm_forces
            ),
            "force_max_abs_error_kcal_per_mol_angstrom_hex": (
                openmm_coordinate_force_max.hex()
            ),
            "force_rms_error_kcal_per_mol_angstrom_hex": (
                openmm_coordinate_force_rms.hex()
            ),
        },
        "trajectory_coordinate_max_abs_error_angstrom_hex": (
            coordinate_error.hex()
        ),
        "trajectory_velocity_max_abs_error_angstrom_per_ps_hex": (
            velocity_error.hex()
        ),
        "trajectory_total_energy_max_abs_error_kcal_per_mol_hex": abs(
            engine_total - openmm_total
        ).hex(),
    }
    return {**projection, "comparison_sha256": _sha256(projection)}


def _float_field(row: Mapping[str, object], field: str) -> float:
    value = row[field]
    if not isinstance(value, str):
        raise OpenMMReferenceNVETrajectoryError(
            f"{field} is not a hexadecimal float"
        )
    try:
        result = float.fromhex(value)
    except ValueError:
        raise OpenMMReferenceNVETrajectoryError(
            f"{field} is not a hexadecimal float"
        ) from None
    if not math.isfinite(result) or result.hex() != value:
        raise OpenMMReferenceNVETrajectoryError(
            f"{field} is not canonical binary64"
        )
    return result


def _openmm_trace(
    *,
    openmm: Any,
    unit: Any,
    reference: Any,
    openmm_system: Any,
    case: _TrajectoryCase,
) -> tuple[dict[str, object], ...]:
    coordinates = case.system.coordinates[0].tolist()
    velocities = case.velocities[0].tolist()
    with _OpenMMRunner(
        openmm=openmm,
        unit=unit,
        reference=reference,
        openmm_system=openmm_system,
        case=case,
        coordinates=coordinates,
        velocities=velocities,
        project_initial=True,
    ) as runner:
        rows = [runner.snapshot()]
        for _ in range(case.steps):
            runner.step()
            rows.append(runner.snapshot())
    return tuple(rows)


def _openmm_restart(
    *,
    openmm: Any,
    unit: Any,
    reference: Any,
    openmm_system: Any,
    case: _TrajectoryCase,
    full_trace: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    coordinates = case.system.coordinates[0].tolist()
    velocities = case.velocities[0].tolist()
    with _OpenMMRunner(
        openmm=openmm,
        unit=unit,
        reference=reference,
        openmm_system=openmm_system,
        case=case,
        coordinates=coordinates,
        velocities=velocities,
        project_initial=True,
    ) as first:
        first.step(case.restart_step)
        checkpoint = first.snapshot()
        checkpoint_transport = first.create_checkpoint()
    with _OpenMMRunner(
        openmm=openmm,
        unit=unit,
        reference=reference,
        openmm_system=openmm_system,
        case=case,
        coordinates=coordinates,
        velocities=velocities,
        project_initial=False,
    ) as resumed:
        resumed.load_checkpoint(
            checkpoint_transport,
            step=case.restart_step,
        )
        resumed.step(case.steps - case.restart_step)
        resumed_final = resumed.snapshot()
    full_final = full_trace[-1]
    full_coordinates, full_velocities, _, _, _, full_total = _state_values(
        full_final,
        atom_count=case.system.atom_count,
    )
    (
        resumed_coordinates,
        resumed_velocities,
        _,
        _,
        _,
        resumed_total,
    ) = _state_values(
        resumed_final,
        atom_count=case.system.atom_count,
    )
    lengths = tuple(
        float(value)
        for value in case.system.cell.orthorhombic_lengths().tolist()
    )
    coordinate_error = _coordinate_error(
        full_coordinates,
        resumed_coordinates,
        lengths,
    )
    velocity_error, _ = _vector_errors(
        full_velocities,
        resumed_velocities,
    )
    energy_error = abs(full_total - resumed_total)
    projection = {
        "restart_step": case.restart_step,
        "checkpoint_state": checkpoint,
        "checkpoint_transport": {
            "format": "OpenMM Context native checkpoint",
            "size": len(checkpoint_transport),
            "portable_across_runtime_or_hardware": False,
            "raw_bytes_persisted": False,
            "transport_digest_persisted": False,
            "digest_omission_reason": (
                "OpenMM native checkpoint contains a nondeterministic "
                "context header; semantic restart equality is recorded"
            ),
        },
        "full_final_state_sha256": full_final["state_sha256"],
        "resumed_final_state": resumed_final,
        "coordinate_max_abs_error_angstrom_hex": coordinate_error.hex(),
        "velocity_max_abs_error_angstrom_per_ps_hex": velocity_error.hex(),
        "total_energy_max_abs_error_kcal_per_mol_hex": energy_error.hex(),
        "coordinate_metric_pass": (
            coordinate_error
            <= OPENMM_REFERENCE_NVE_RESTART_COORDINATE_THRESHOLD_ANGSTROM
        ),
        "velocity_metric_pass": (
            velocity_error
            <= OPENMM_REFERENCE_NVE_RESTART_VELOCITY_THRESHOLD_ANGSTROM_PER_PS
        ),
        "energy_metric_pass": (
            energy_error
            <= OPENMM_REFERENCE_NVE_RESTART_ENERGY_THRESHOLD_KCAL_PER_MOL
        ),
    }
    return {
        **projection,
        "restart_sha256": _sha256(projection),
        "metric_pass": all(
            projection[field]
            for field in (
                "coordinate_metric_pass",
                "velocity_metric_pass",
                "energy_metric_pass",
            )
        ),
    }


def _engine_restart(case: _TrajectoryCase, full_result: Any) -> dict[str, object]:
    paused = run_reference_nve(
        case.system,
        case.parameters,
        case.velocities,
        steps=case.restart_step,
        config=case.nve_config,
        constraint_config=case.constraint_config,
    )
    resumed = resume_reference_nve(
        case.system,
        case.parameters,
        paused.checkpoint,
        additional_steps=case.steps - case.restart_step,
    )
    coordinates_equal = torch.equal(
        resumed.checkpoint.coordinates,
        full_result.checkpoint.coordinates,
    )
    velocities_equal = torch.equal(
        resumed.checkpoint.velocities_angstrom_per_ps,
        full_result.checkpoint.velocities_angstrom_per_ps,
    )
    projection = {
        "restart_step": case.restart_step,
        "paused_checkpoint_sha256": paused.checkpoint.checkpoint_sha256,
        "full_checkpoint_sha256": full_result.checkpoint.checkpoint_sha256,
        "resumed_checkpoint_sha256": resumed.checkpoint.checkpoint_sha256,
        "full_trajectory_head_sha256": (
            full_result.checkpoint.trajectory_head_sha256
        ),
        "resumed_trajectory_head_sha256": (
            resumed.checkpoint.trajectory_head_sha256
        ),
        "coordinates_bit_exact": coordinates_equal,
        "velocities_bit_exact": velocities_equal,
        "checkpoint_bit_exact": (
            resumed.checkpoint.checkpoint_sha256
            == full_result.checkpoint.checkpoint_sha256
        ),
        "trajectory_head_bit_exact": (
            resumed.checkpoint.trajectory_head_sha256
            == full_result.checkpoint.trajectory_head_sha256
        ),
    }
    return {
        **projection,
        "restart_sha256": _sha256(projection),
        "metric_pass": all(
            projection[field]
            for field in (
                "coordinates_bit_exact",
                "velocities_bit_exact",
                "checkpoint_bit_exact",
                "trajectory_head_bit_exact",
            )
        ),
    }


def _case_row(
    case: _TrajectoryCase,
    *,
    openmm: Any,
    unit: Any,
    reference: Any,
) -> dict[str, object]:
    full_result = run_reference_nve(
        case.system,
        case.parameters,
        case.velocities,
        steps=case.steps,
        config=case.nve_config,
        constraint_config=case.constraint_config,
    )
    engine_states = tuple(
        _engine_state(case, frame) for frame in full_result.frames
    )
    openmm_system, mapping = _build_openmm_system(case, openmm=openmm)
    openmm_states = _openmm_trace(
        openmm=openmm,
        unit=unit,
        reference=reference,
        openmm_system=openmm_system,
        case=case,
    )
    if len(engine_states) != len(openmm_states) or len(engine_states) != (
        case.steps + 1
    ):
        raise OpenMMReferenceNVETrajectoryError(
            "engine and OpenMM trace lengths are inconsistent"
        )
    with _OpenMMStaticEvaluator(
        openmm=openmm,
        unit=unit,
        reference=reference,
        openmm_system=openmm_system,
        atom_count=case.system.atom_count,
    ) as static_openmm:
        comparisons = tuple(
            _comparison_row(
                case=case,
                engine_state=engine_state,
                openmm_state=openmm_state,
                static_openmm=static_openmm,
            )
            for engine_state, openmm_state in zip(
                engine_states,
                openmm_states,
            )
        )
    engine_restart = _engine_restart(case, full_result)
    openmm_restart = _openmm_restart(
        openmm=openmm,
        unit=unit,
        reference=reference,
        openmm_system=openmm_system,
        case=case,
        full_trace=openmm_states,
    )

    energy_errors = []
    force_max_errors = []
    force_rms_errors = []
    coordinate_errors = []
    velocity_errors = []
    total_energy_errors = []
    for comparison in comparisons:
        for scope in (
            "engine_at_engine_coordinates",
            "engine_at_openmm_coordinates",
        ):
            row = comparison[scope]
            energy_errors.append(
                _float_field(
                    row,
                    "energy_max_abs_error_kcal_per_mol_hex",
                )
            )
            force_max_errors.append(
                _float_field(
                    row,
                    "force_max_abs_error_kcal_per_mol_angstrom_hex",
                )
            )
            force_rms_errors.append(
                _float_field(
                    row,
                    "force_rms_error_kcal_per_mol_angstrom_hex",
                )
            )
        coordinate_errors.append(
            _float_field(
                comparison,
                "trajectory_coordinate_max_abs_error_angstrom_hex",
            )
        )
        velocity_errors.append(
            _float_field(
                comparison,
                "trajectory_velocity_max_abs_error_angstrom_per_ps_hex",
            )
        )
        total_energy_errors.append(
            _float_field(
                comparison,
                "trajectory_total_energy_max_abs_error_kcal_per_mol_hex",
            )
        )
    position_residuals = []
    velocity_residuals = []
    for state in (*engine_states, *openmm_states):
        position_residuals.append(
            _float_field(
                state,
                "position_constraint_residual_angstrom_hex",
            )
        )
        velocity_residuals.append(
            _float_field(
                state,
                "velocity_constraint_residual_angstrom_per_ps_hex",
            )
        )
    engine_totals = [
        _float_field(state, "total_energy_kcal_per_mol_hex")
        for state in engine_states
    ]
    openmm_totals = [
        _float_field(state, "total_energy_kcal_per_mol_hex")
        for state in openmm_states
    ]
    engine_drift = max(
        abs(value - engine_totals[0]) for value in engine_totals
    )
    openmm_drift = max(
        abs(value - openmm_totals[0]) for value in openmm_totals
    )
    maxima = {
        "same_coordinate_energy_max_abs_kcal_per_mol_hex": max(
            energy_errors
        ).hex(),
        "same_coordinate_force_max_abs_kcal_per_mol_angstrom_hex": max(
            force_max_errors
        ).hex(),
        "same_coordinate_force_rms_kcal_per_mol_angstrom_hex": max(
            force_rms_errors
        ).hex(),
        "trajectory_coordinate_max_abs_angstrom_hex": max(
            coordinate_errors
        ).hex(),
        "trajectory_velocity_max_abs_angstrom_per_ps_hex": max(
            velocity_errors
        ).hex(),
        "trajectory_total_energy_max_abs_kcal_per_mol_hex": max(
            total_energy_errors
        ).hex(),
        "position_constraint_max_abs_angstrom_hex": max(
            position_residuals
        ).hex(),
        "velocity_constraint_max_abs_angstrom_per_ps_hex": max(
            velocity_residuals
        ).hex(),
        "engine_energy_drift_max_abs_kcal_per_mol_hex": engine_drift.hex(),
        "openmm_energy_drift_max_abs_kcal_per_mol_hex": openmm_drift.hex(),
    }
    metric_checks = {
        "same_coordinate_energy_metric_pass": (
            max(energy_errors)
            <= OPENMM_REFERENCE_NVE_ENERGY_ERROR_THRESHOLD_KCAL_PER_MOL
        ),
        "same_coordinate_force_max_metric_pass": (
            max(force_max_errors)
            <= OPENMM_REFERENCE_NVE_FORCE_MAX_ERROR_THRESHOLD_KCAL_PER_MOL_ANGSTROM
        ),
        "same_coordinate_force_rms_metric_pass": (
            max(force_rms_errors)
            <= OPENMM_REFERENCE_NVE_FORCE_RMS_ERROR_THRESHOLD_KCAL_PER_MOL_ANGSTROM
        ),
        "trajectory_coordinate_metric_pass": (
            max(coordinate_errors)
            <= OPENMM_REFERENCE_NVE_COORDINATE_ERROR_THRESHOLD_ANGSTROM
        ),
        "trajectory_velocity_metric_pass": (
            max(velocity_errors)
            <= OPENMM_REFERENCE_NVE_VELOCITY_ERROR_THRESHOLD_ANGSTROM_PER_PS
        ),
        "position_constraint_metric_pass": (
            max(position_residuals)
            <= OPENMM_REFERENCE_NVE_POSITION_CONSTRAINT_THRESHOLD_ANGSTROM
        ),
        "velocity_constraint_metric_pass": (
            max(velocity_residuals)
            <= OPENMM_REFERENCE_NVE_VELOCITY_CONSTRAINT_THRESHOLD_ANGSTROM_PER_PS
        ),
        "engine_energy_drift_metric_pass": (
            engine_drift <= OPENMM_REFERENCE_NVE_DRIFT_THRESHOLD_KCAL_PER_MOL
        ),
        "openmm_energy_drift_metric_pass": (
            openmm_drift <= OPENMM_REFERENCE_NVE_DRIFT_THRESHOLD_KCAL_PER_MOL
        ),
        "engine_restart_metric_pass": bool(engine_restart["metric_pass"]),
        "openmm_restart_metric_pass": bool(openmm_restart["metric_pass"]),
    }
    projection = {
        "schema_id": OPENMM_REFERENCE_NVE_TRAJECTORY_CASE_SCHEMA_ID,
        "case_id": case.case_id,
        "status": "completed",
        "input_identity": {
            "source_system_sha256": canonical_system_sha256(case.system),
            "topology_sha256": canonical_topology_sha256(case.system),
            "parameter_fingerprint_sha256": (
                case.parameters.fingerprint_sha256
            ),
            "nve_config_fingerprint_sha256": (
                case.nve_config.fingerprint_sha256
            ),
            "constraint_config_fingerprint_sha256": (
                case.constraint_config.fingerprint_sha256
            ),
        },
        "openmm_mapping": mapping,
        "engine_constraint_iteration_counts": {
            "cumulative_shake": (
                full_result.cumulative_shake_iteration_count
            ),
            "cumulative_rattle": (
                full_result.cumulative_rattle_iteration_count
            ),
        },
        "openmm_constraint_iteration_counts": {
            "status": "not_exposed_by_openmm",
            "count": None,
        },
        "engine_trace": list(engine_states),
        "openmm_trace": list(openmm_states),
        "same_step_comparisons": list(comparisons),
        "engine_restart": engine_restart,
        "openmm_restart": openmm_restart,
        "maxima": maxima,
        "metric_checks": metric_checks,
        "metric_pass": all(metric_checks.values()),
        "scientifically_validated": False,
        "claim_safe": False,
    }
    return {**projection, "case_sha256": _sha256(projection)}


def _failure_variant(
    case_id: str,
) -> _TrajectoryCase:
    base = _materialize_cases()[0]
    if case_id == "nonperiodic_direct_ewald":
        return replace(
            base,
            case_id=case_id,
            system=replace(base.system, cell=None),
        )
    if case_id == "net_charged_direct_ewald":
        parameters = replace(
            base.parameters,
            atom_parameters=(
                base.parameters.atom_parameters[0],
                replace(base.parameters.atom_parameters[1], charge_e=-0.20),
            ),
        )
        return replace(base, case_id=case_id, parameters=parameters)
    if case_id == "triclinic_direct_ewald":
        vectors = torch.tensor(
            (
                (12.0, 0.0, 0.0),
                (1.0, 12.0, 0.0),
                (0.0, 0.0, 12.0),
            ),
            dtype=torch.float64,
        )
        return replace(
            base,
            case_id=case_id,
            system=replace(base.system, cell=UnitCell(vectors=vectors)),
        )
    raise OpenMMReferenceNVETrajectoryError(
        "unknown frozen failure case"
    )


def _engine_failure_code(case: _TrajectoryCase) -> tuple[str, str]:
    try:
        run_reference_nve(
            case.system,
            case.parameters,
            case.velocities,
            steps=1,
            config=case.nve_config,
            constraint_config=case.constraint_config,
        )
    except ReferenceNVEError as exc:
        message = str(exc)
        if "fully periodic" in message:
            return "fully_periodic_required", message
        if "net charge" in message:
            return "neutrality_required", message
        if "orthorhombic" in message:
            return "orthorhombic_required", message
        return "unexpected_reference_nve_error", message
    return "unexpected_success", ""


def _oracle_failure_code(case: _TrajectoryCase) -> tuple[str, str]:
    try:
        _require_case_domain(case)
    except OpenMMReferenceNVETrajectoryError as exc:
        message = str(exc)
        if "fully periodic" in message:
            return "fully_periodic_required", message
        if "neutral" in message:
            return "neutrality_required", message
        if "orthorhombic" in message:
            return "orthorhombic_required", message
        return "unexpected_oracle_error", message
    return "unexpected_success", ""


def _failure_row(case_id: str) -> dict[str, object]:
    expected = {
        "nonperiodic_direct_ewald": (
            "fully_periodic_required",
            "fully_periodic_required",
        ),
        "net_charged_direct_ewald": (
            "neutrality_required",
            "neutrality_required",
        ),
        "triclinic_direct_ewald": (
            "orthorhombic_required",
            "orthorhombic_required",
        ),
    }[case_id]
    case = _failure_variant(case_id)
    engine_code, engine_message = _engine_failure_code(case)
    oracle_code, oracle_message = _oracle_failure_code(case)
    projection = {
        "case_id": case_id,
        "status": "expected_fail_closed",
        "expected_engine_code": expected[0],
        "observed_engine_code": engine_code,
        "engine_error_class": "ReferenceNVEError",
        "engine_message": engine_message,
        "expected_oracle_code": expected[1],
        "observed_oracle_code": oracle_code,
        "oracle_error_class": "OpenMMReferenceNVETrajectoryError",
        "oracle_message": oracle_message,
        "metric_pass": (
            engine_code == expected[0] and oracle_code == expected[1]
        ),
    }
    return {**projection, "failure_sha256": _sha256(projection)}


def _observation_projection() -> dict[str, object]:
    configuration = openmm_reference_nve_trajectory_configuration_document()
    runtime_identity, openmm, unit, reference = _openmm_modules()
    case_rows = [
        _case_row(
            case,
            openmm=openmm,
            unit=unit,
            reference=reference,
        )
        for case in _materialize_cases()
    ]
    failure_rows = [
        _failure_row(case_id)
        for case_id in (
            "nonperiodic_direct_ewald",
            "net_charged_direct_ewald",
            "triclinic_direct_ewald",
        )
    ]
    all_metrics_pass = all(
        bool(row["metric_pass"]) for row in (*case_rows, *failure_rows)
    )
    return {
        "schema_id": OPENMM_REFERENCE_NVE_TRAJECTORY_OBSERVATION_SCHEMA_ID,
        "protocol_id": OPENMM_REFERENCE_NVE_TRAJECTORY_PROTOCOL_ID,
        "configuration_sha256": configuration["configuration_sha256"],
        "configuration": configuration,
        "source_identity": _source_identity_document(),
        "runtime_identity": runtime_identity,
        "case_rows": case_rows,
        "failure_rows": failure_rows,
        "summary": {
            "pass_case_count": len(case_rows),
            "pass_case_metric_count": sum(
                bool(row["metric_pass"]) for row in case_rows
            ),
            "failure_case_count": len(failure_rows),
            "failure_case_metric_count": sum(
                bool(row["metric_pass"]) for row in failure_rows
            ),
            "all_preregistered_metrics_pass": all_metrics_pass,
            "host_count": 1,
            "independent_reviewer_approved": False,
            "production_eligible": False,
        },
        "scientific_blockers": list(
            OPENMM_REFERENCE_NVE_TRAJECTORY_SCIENTIFIC_BLOCKERS
        ),
        "scientifically_validated": False,
        "claim_safe": False,
    }


def build_openmm_reference_nve_trajectory_observation() -> dict[str, object]:
    """Execute the frozen local protocol and return one deterministic receipt."""

    projection = _observation_projection()
    return {**projection, "observation_sha256": _sha256(projection)}


def require_openmm_reference_nve_trajectory_observation(
    value: Mapping[str, object],
) -> dict[str, object]:
    """Verify hashes, active identities, dispositions, and every numeric result."""

    if not isinstance(value, Mapping):
        raise OpenMMReferenceNVETrajectoryError(
            "OpenMM NVE trajectory observation must be a mapping"
        )
    observed = json.loads(_canonical_bytes(dict(value)).decode("ascii"))
    expected_keys = {
        "schema_id",
        "protocol_id",
        "configuration_sha256",
        "configuration",
        "source_identity",
        "runtime_identity",
        "case_rows",
        "failure_rows",
        "summary",
        "scientific_blockers",
        "scientifically_validated",
        "claim_safe",
        "observation_sha256",
    }
    if set(observed) != expected_keys:
        raise OpenMMReferenceNVETrajectoryError(
            "OpenMM NVE trajectory observation fields are invalid"
        )
    digest = _require_sha256(
        observed.get("observation_sha256"),
        name="OpenMM NVE trajectory observation",
    )
    projection = {
        key: item
        for key, item in observed.items()
        if key != "observation_sha256"
    }
    if digest != _sha256(projection):
        raise OpenMMReferenceNVETrajectoryError(
            "OpenMM NVE trajectory observation digest mismatch"
        )
    if (
        observed.get("schema_id")
        != OPENMM_REFERENCE_NVE_TRAJECTORY_OBSERVATION_SCHEMA_ID
        or observed.get("protocol_id")
        != OPENMM_REFERENCE_NVE_TRAJECTORY_PROTOCOL_ID
        or observed.get("scientifically_validated") is not False
        or observed.get("claim_safe") is not False
    ):
        raise OpenMMReferenceNVETrajectoryError(
            "OpenMM NVE trajectory observation overstates its evidence claim"
        )
    current = _observation_projection()
    if projection != current:
        raise OpenMMReferenceNVETrajectoryError(
            "OpenMM NVE trajectory observation does not reproduce current "
            "source, runtime, failures, traces, or numeric metrics"
        )
    return observed


def write_openmm_reference_nve_trajectory_observation(
    path: Path | str,
    observation: Mapping[str, object],
) -> Path:
    """Write one verified private receipt without replacing different evidence."""

    verified = require_openmm_reference_nve_trajectory_observation(observation)
    payload = json.dumps(
        verified,
        allow_nan=False,
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
    ) + "\n"
    encoded_size = len(payload.encode("utf-8"))
    if encoded_size > OPENMM_REFERENCE_NVE_MAX_OBSERVATION_BYTES:
        raise OpenMMReferenceNVETrajectoryError(
            "OpenMM NVE trajectory observation exceeds its bounded size"
        )
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_symlink():
        raise OpenMMReferenceNVETrajectoryError(
            "OpenMM NVE trajectory observation path must not be a symlink"
        )
    if destination.exists():
        metadata = destination.lstat()
        if not stat.S_ISREG(metadata.st_mode):
            raise OpenMMReferenceNVETrajectoryError(
                "OpenMM NVE trajectory observation path must be a regular file"
            )
        if metadata.st_size > OPENMM_REFERENCE_NVE_MAX_OBSERVATION_BYTES:
            raise OpenMMReferenceNVETrajectoryError(
                "existing OpenMM NVE trajectory observation exceeds its bound"
            )
        if destination.read_text(encoding="utf-8") != payload:
            raise OpenMMReferenceNVETrajectoryError(
                "refusing to overwrite a different OpenMM NVE trajectory observation"
            )
        os.chmod(destination, 0o600)
        return destination
    temporary = destination.with_name(
        f".{destination.name}.tmp-{os.getpid()}"
    )
    created = False
    try:
        with temporary.open("x", encoding="utf-8") as handle:
            created = True
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        try:
            os.link(temporary, destination, follow_symlinks=False)
        except FileExistsError as exc:
            raise OpenMMReferenceNVETrajectoryError(
                "OpenMM NVE trajectory observation path appeared during creation"
            ) from exc
        temporary.unlink()
        directory_fd = os.open(
            destination.parent,
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
        )
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if created and temporary.exists():
            temporary.unlink()
    return destination


def read_openmm_reference_nve_trajectory_observation(
    path: Path | str,
) -> dict[str, object]:
    """Read one private bounded receipt and reproduce its complete observation."""

    source = Path(path)
    metadata = source.lstat()
    if not stat.S_ISREG(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
        raise OpenMMReferenceNVETrajectoryError(
            "OpenMM NVE trajectory observation must be a regular non-symlink file"
        )
    if metadata.st_mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise OpenMMReferenceNVETrajectoryError(
            "OpenMM NVE trajectory observation must not be group/world accessible"
        )
    if metadata.st_size > OPENMM_REFERENCE_NVE_MAX_OBSERVATION_BYTES:
        raise OpenMMReferenceNVETrajectoryError(
            "OpenMM NVE trajectory observation exceeds its bounded size"
        )
    try:
        with source.open("rb") as handle:
            raw = handle.read(OPENMM_REFERENCE_NVE_MAX_OBSERVATION_BYTES + 1)
        if len(raw) > OPENMM_REFERENCE_NVE_MAX_OBSERVATION_BYTES:
            raise OpenMMReferenceNVETrajectoryError(
                "OpenMM NVE trajectory observation exceeds its bounded size"
            )
        value = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise OpenMMReferenceNVETrajectoryError(
            "OpenMM NVE trajectory observation is not readable JSON"
        ) from exc
    return require_openmm_reference_nve_trajectory_observation(value)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build or verify the claim-closed OpenMM Reference NVE, "
            "SHAKE/RATTLE, and direct-Ewald trajectory observation"
        )
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--output", type=Path)
    action.add_argument("--verify", type=Path)
    arguments = parser.parse_args(argv)
    if arguments.output is not None:
        observation = build_openmm_reference_nve_trajectory_observation()
        destination = write_openmm_reference_nve_trajectory_observation(
            arguments.output,
            observation,
        )
        print(
            json.dumps(
                {
                    "observation_sha256": observation["observation_sha256"],
                    "path": str(destination),
                    "status": "openmm_reference_nve_trajectory_observation_written",
                },
                allow_nan=False,
                ensure_ascii=True,
                sort_keys=True,
            )
        )
        return 0
    verified = read_openmm_reference_nve_trajectory_observation(
        arguments.verify
    )
    print(
        json.dumps(
            {
                "observation_sha256": verified["observation_sha256"],
                "path": str(arguments.verify),
                "status": "openmm_reference_nve_trajectory_observation_verified",
            },
            allow_nan=False,
            ensure_ascii=True,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "FROZEN_OPENMM_REFERENCE_NVE_TRAJECTORY_CONFIG_SHA256",
    "OPENMM_REFERENCE_NVE_MAX_OBSERVATION_BYTES",
    "OPENMM_REFERENCE_NVE_TRAJECTORY_CONFIG_SCHEMA_ID",
    "OPENMM_REFERENCE_NVE_TRAJECTORY_OBSERVATION_SCHEMA_ID",
    "OPENMM_REFERENCE_NVE_TRAJECTORY_PROTOCOL_ID",
    "OPENMM_REFERENCE_NVE_TRAJECTORY_SCIENTIFIC_BLOCKERS",
    "OpenMMReferenceNVETrajectoryError",
    "build_openmm_reference_nve_trajectory_observation",
    "main",
    "openmm_reference_nve_trajectory_configuration_document",
    "read_openmm_reference_nve_trajectory_observation",
    "require_openmm_reference_nve_trajectory_observation",
    "write_openmm_reference_nve_trajectory_observation",
]
