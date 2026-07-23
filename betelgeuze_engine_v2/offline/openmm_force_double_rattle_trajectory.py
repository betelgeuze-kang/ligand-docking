"""Failure-inclusive OpenMM-force/double-RATTLE trajectory successor.

The adapter keeps OpenMM Reference as the independently mapped force provider
while the stdlib-only oracle module performs a separate binary64 constrained
integration.  The resulting development receipt is claim-closed and does not
supersede either predecessor OpenMM trajectory receipt.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import dataclass, replace
import hashlib
import json
import math
import os
from pathlib import Path
import stat
from typing import Any, Mapping, Sequence

import torch

from betelgeuze_engine_v2.molecular import (
    AllAtomSystem,
    Atom,
    Chain,
    Residue,
    StructureProvenance,
    UnitCell,
    canonical_system_sha256,
    canonical_topology_sha256,
)
from betelgeuze_engine_v2.physics import (
    AtomNonbondedParameter,
    ReferenceEwaldConfig,
    ReferenceForceFieldParameters,
    ReferenceNVEConfig,
    ReferenceSHAKERATTLEConfig,
    run_reference_nve,
)
from betelgeuze_engine_v2.physics.reference_explicit_solvent import (
    REFERENCE_EXPLICIT_SOLVENT_ALGORITHM_ID,
    REFERENCE_EXPLICIT_SOLVENT_PROFILE_FINGERPRINT_SHA256,
    ReferenceExplicitSolventConfig,
    ReferenceExplicitSolventError,
    ReferenceExplicitSolventPreparation,
    prepare_reference_explicit_solvent,
    verify_reference_explicit_solvent_replay,
)
from betelgeuze_engine_v2.offline import (
    openmm_reference_nve_trajectory as _parent,
)
from betelgeuze_engine_v2.offline.openmm_force_double_rattle_oracle import (
    DoubleRattleDistanceConstraint,
    OPENMM_FORCE_DOUBLE_RATTLE_ALGORITHM_ID,
    OpenMMForceDoubleRattleConfig,
    OpenMMForceDoubleRattleError,
    resume_openmm_force_double_rattle,
    run_openmm_force_double_rattle,
)


OPENMM_FORCE_DOUBLE_RATTLE_TRAJECTORY_PROTOCOL_ID = (
    "betelgeuze.engine_v2_openmm_force_double_rattle_trajectory/1.0.0"
)
OPENMM_FORCE_DOUBLE_RATTLE_TRAJECTORY_CONFIG_SCHEMA_ID = (
    "betelgeuze.engine_v2_openmm_force_double_rattle_trajectory_config/1.0.0"
)
OPENMM_FORCE_DOUBLE_RATTLE_TRAJECTORY_OBSERVATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_openmm_force_double_rattle_trajectory_observation/1.0.0"
)
OPENMM_FORCE_DOUBLE_RATTLE_TRAJECTORY_CASE_SCHEMA_ID = (
    "betelgeuze.engine_v2_openmm_force_double_rattle_trajectory_case/1.0.0"
)

# Filled after the input-only development projection is reviewed.  This is not
# a confirmatory scientific preregistration.
FROZEN_OPENMM_FORCE_DOUBLE_RATTLE_TRAJECTORY_CONFIG_SHA256 = (
    "ba2c1e99183cc124bb664745dfd1b4cbabbd2d4328cc35754e9e4da044606007"
)

OPENMM_FORCE_DOUBLE_RATTLE_MAX_OBSERVATION_BYTES = 32 * 1024**2
OPENMM_FORCE_DOUBLE_RATTLE_CUTOFF_MARGIN_THRESHOLD_ANGSTROM = 0.25
OPENMM_FORCE_DOUBLE_RATTLE_ENERGY_ERROR_THRESHOLD_KCAL_PER_MOL = 1.0e-9
OPENMM_FORCE_DOUBLE_RATTLE_FORCE_MAX_THRESHOLD_KCAL_PER_MOL_ANGSTROM = 1.0e-7
OPENMM_FORCE_DOUBLE_RATTLE_FORCE_RMS_THRESHOLD_KCAL_PER_MOL_ANGSTROM = 1.0e-8
OPENMM_FORCE_DOUBLE_RATTLE_COORDINATE_THRESHOLD_ANGSTROM = 2.0e-7
OPENMM_FORCE_DOUBLE_RATTLE_VELOCITY_THRESHOLD_ANGSTROM_PER_PS = 2.0e-4
OPENMM_FORCE_DOUBLE_RATTLE_TOTAL_ENERGY_THRESHOLD_KCAL_PER_MOL = 2.0e-6
OPENMM_FORCE_DOUBLE_RATTLE_POSITION_RESIDUAL_THRESHOLD_ANGSTROM = 1.0e-9
OPENMM_FORCE_DOUBLE_RATTLE_VELOCITY_RESIDUAL_THRESHOLD_ANGSTROM_PER_PS = 1.0e-8
OPENMM_FORCE_DOUBLE_RATTLE_DRIFT_THRESHOLD_KCAL_PER_MOL = 1.0e-6

OPENMM_FORCE_DOUBLE_RATTLE_SCIENTIFIC_BLOCKERS = (
    "development thresholds follow exploratory implementation work and are not "
    "confirmatory scientific acceptance thresholds",
    "stdlib double-RATTLE is an internal independent implementation, not an "
    "independently maintained external integrator",
    "OpenMM Reference supplies static forces only in this successor",
    "four-water deterministic lattice is not an equilibrated liquid",
    "single local CPU host observation only",
    "no long-time drift, liquid/ion observable, PME, two-host, GPU, or "
    "independent-review evidence",
    "scientific validation, product readiness, and P2 completion remain false",
)


class OpenMMForceDoubleRattleTrajectoryError(RuntimeError):
    """The successor configuration, runtime, or receipt failed closed."""


@dataclass(frozen=True)
class _PreparedCase:
    case_id: str
    source_system: AllAtomSystem
    source_parameters: ReferenceForceFieldParameters
    preparation_config: ReferenceExplicitSolventConfig
    preparation: ReferenceExplicitSolventPreparation


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
        raise OpenMMForceDoubleRattleTrajectoryError(
            "double-RATTLE trajectory payload is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _require_sha256(value: object, *, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise OpenMMForceDoubleRattleTrajectoryError(
            f"{name} must be a lowercase SHA-256 digest"
        )
    return value


def _float_field(row: Mapping[str, object], field: str) -> float:
    value = row[field]
    if not isinstance(value, str):
        raise OpenMMForceDoubleRattleTrajectoryError(
            f"{field} must be canonical binary64 hex"
        )
    try:
        result = float.fromhex(value)
    except ValueError:
        raise OpenMMForceDoubleRattleTrajectoryError(
            f"{field} must be canonical binary64 hex"
        ) from None
    if not math.isfinite(result) or result.hex() != value:
        raise OpenMMForceDoubleRattleTrajectoryError(
            f"{field} must be canonical finite binary64 hex"
        )
    return result


def _source_system(
    *,
    case_id: str,
    charge_e: float,
    mass_da: float | None = 12.011,
    cell: UnitCell | None = None,
) -> AllAtomSystem:
    return AllAtomSystem(
        system_id=f"{case_id}:source",
        atoms=(
            Atom(
                index=0,
                name="C",
                element="C",
                atomic_number=6,
                residue_index=0,
                formal_charge=int(charge_e),
                partial_charge_e=charge_e,
                mass_da=mass_da,
            ),
        ),
        bonds=(),
        residues=(
            Residue(
                index=0,
                name="MOL",
                chain_index=0,
                sequence_number=1,
                atom_indices=(0,),
                entity_type="non-polymer",
                hetero=True,
            ),
        ),
        chains=(Chain(index=0, chain_id="A", residue_indices=(0,)),),
        coordinates=torch.tensor(
            ((((0.0, 0.0, 0.0)),),),
            dtype=torch.float64,
        ),
        provenance=StructureProvenance(
            source_format="frozen-openmm-force-double-rattle-development"
        ),
        cell=cell,
    )


def _source_parameters(
    system: AllAtomSystem,
    *,
    charge_e: float,
) -> ReferenceForceFieldParameters:
    return ReferenceForceFieldParameters(
        parameter_set_id=f"{system.system_id}:parameters",
        parameter_set_version="1.0.0",
        topology_sha256=canonical_topology_sha256(system),
        atom_parameters=(
            AtomNonbondedParameter(
                atom_index=0,
                sigma_angstrom=3.4,
                epsilon_kcal_per_mol=0.1,
                charge_e=charge_e,
            ),
        ),
        cutoff_angstrom=4.0,
        switch_start_angstrom=3.0,
    )


def _preparation_config(
    *,
    sodium_count: int,
    chloride_count: int,
) -> ReferenceExplicitSolventConfig:
    return ReferenceExplicitSolventConfig(
        box_lengths_angstrom=(13.5, 13.5, 13.5),
        water_count=4,
        sodium_count=sodium_count,
        chloride_count=chloride_count,
        lattice_spacing_angstrom=3.4,
        water_constraint_tolerance_angstrom=1.0e-10,
    )


def _prepare_case(
    *,
    case_id: str,
    charge_e: float,
    sodium_count: int,
    chloride_count: int,
) -> _PreparedCase:
    source = _source_system(case_id=case_id, charge_e=charge_e)
    parameters = _source_parameters(source, charge_e=charge_e)
    config = _preparation_config(
        sodium_count=sodium_count,
        chloride_count=chloride_count,
    )
    preparation = prepare_reference_explicit_solvent(
        source,
        parameters,
        config,
    )
    return _PreparedCase(
        case_id=case_id,
        source_system=source,
        source_parameters=parameters,
        preparation_config=config,
        preparation=preparation,
    )


def _materialize_cases() -> tuple[_PreparedCase, ...]:
    return (
        _prepare_case(
            case_id="neutral_solute_four_waters",
            charge_e=0.0,
            sodium_count=0,
            chloride_count=0,
        ),
        _prepare_case(
            case_id="neutral_solute_four_waters_na_cl",
            charge_e=0.0,
            sodium_count=1,
            chloride_count=1,
        ),
        _prepare_case(
            case_id="positive_solute_four_waters_cl",
            charge_e=1.0,
            sodium_count=0,
            chloride_count=1,
        ),
    )


def _velocities(atom_count: int) -> torch.Tensor:
    rows = [
        (
            ((index % 3) - 1) * 0.002,
            (((2 * index) % 5) - 2) * 0.0015,
            (((3 * index) % 7) - 3) * 0.001,
        )
        for index in range(atom_count)
    ]
    return torch.tensor((rows,), dtype=torch.float64)


def _trajectory_case(prepared: _PreparedCase) -> _parent._TrajectoryCase:
    preparation = prepared.preparation
    return _parent._TrajectoryCase(
        case_id=prepared.case_id,
        system=preparation.system,
        parameters=preparation.parameters,
        velocities=_velocities(preparation.system.atom_count),
        nve_config=ReferenceNVEConfig(
            timestep_ps=1.0e-4,
            trajectory_stride=1,
            max_neighbors=32,
            max_atoms_per_cell=32,
            ewald_config=ReferenceEwaldConfig(
                alpha_per_angstrom=0.35,
                reciprocal_max_indices=(2, 2, 2),
            ),
        ),
        constraint_config=preparation.constraint_config,
        steps=16,
        restart_step=7,
    )


def _oracle_config(case: _parent._TrajectoryCase) -> OpenMMForceDoubleRattleConfig:
    if case.system.cell is None:
        raise OpenMMForceDoubleRattleTrajectoryError(
            "oracle config requires a periodic cell"
        )
    lengths = tuple(
        float(item)
        for item in case.system.cell.orthorhombic_lengths().tolist()
    )
    return OpenMMForceDoubleRattleConfig(
        timestep_ps=case.nve_config.timestep_ps,
        box_lengths_angstrom=lengths,  # type: ignore[arg-type]
        position_tolerance_angstrom=1.0e-12,
        velocity_tolerance_angstrom_per_ps=1.0e-12,
        max_position_sweeps=500,
        max_velocity_sweeps=500,
        max_pair_position_correction_angstrom=0.1,
    )


def _oracle_constraints(
    case: _parent._TrajectoryCase,
) -> tuple[DoubleRattleDistanceConstraint, ...]:
    rows = tuple(
        DoubleRattleDistanceConstraint(
            atom_i=row.atom_i,
            atom_j=row.atom_j,
            target_distance_angstrom=row.target_distance_angstrom,
        )
        for row in case.constraint_config.constraints
    )
    return tuple(sorted(rows, key=lambda row: (row.atom_i, row.atom_j)))


def _force_configuration_document(
    case: _parent._TrajectoryCase,
) -> dict[str, object]:
    projection = {
        "parent_protocol_id": _parent.OPENMM_REFERENCE_NVE_TRAJECTORY_PROTOCOL_ID,
        "parent_configuration_sha256": (
            _parent.FROZEN_OPENMM_REFERENCE_NVE_TRAJECTORY_CONFIG_SHA256
        ),
        "system_sha256": canonical_system_sha256(case.system),
        "parameter_fingerprint_sha256": (
            case.parameters.fingerprint_sha256
        ),
        "ewald_config": case.nve_config.ewald_config.to_dict()
        if case.nve_config.ewald_config is not None
        else None,
        "openmm_platform": _parent.OPENMM_REFERENCE_REQUIRED_PLATFORM,
        "lj_expression_sha256": hashlib.sha256(
            _parent._OPENMM_LJ_EXPRESSION.encode("ascii")
        ).hexdigest(),
        "ewald_real_pair_expression_sha256": hashlib.sha256(
            _parent._OPENMM_EWAL_REAL_AND_PAIR_CORRECTION_EXPRESSION.encode(
                "ascii"
            )
        ).hexdigest(),
    }
    return {**projection, "force_configuration_sha256": _sha256(projection)}


def _active_pair_rows(
    case: _parent._TrajectoryCase,
    coordinates: Sequence[Sequence[float]],
) -> list[dict[str, object]]:
    if case.system.cell is None:
        raise OpenMMForceDoubleRattleTrajectoryError(
            "cutoff audit requires a periodic cell"
        )
    lengths = tuple(
        float(item)
        for item in case.system.cell.orthorhombic_lengths().tolist()
    )
    atom_map = case.parameters.atom_parameter_map
    excluded = set(case.parameters.excluded_pairs)
    scaling = case.parameters.pair_scaling_map
    rows = []
    for atom_i in range(case.system.atom_count):
        for atom_j in range(atom_i + 1, case.system.atom_count):
            pair = (atom_i, atom_j)
            if pair in excluded:
                continue
            first = atom_map[atom_i]
            second = atom_map[atom_j]
            electrostatic_scale = (
                scaling[pair].electrostatic_scale
                if pair in scaling
                else 1.0
            )
            lj_scale = scaling[pair].lj_scale if pair in scaling else 1.0
            charge_product = (
                first.charge_e
                * second.charge_e
                * electrostatic_scale
            )
            epsilon = (
                math.sqrt(
                    first.epsilon_kcal_per_mol
                    * second.epsilon_kcal_per_mol
                )
                * lj_scale
            )
            if charge_product == 0.0 and epsilon == 0.0:
                continue
            displacement = tuple(
                (
                    float(coordinates[atom_i][axis])
                    - float(coordinates[atom_j][axis])
                )
                - round(
                    (
                        float(coordinates[atom_i][axis])
                        - float(coordinates[atom_j][axis])
                    )
                    / lengths[axis]
                )
                * lengths[axis]
                for axis in range(3)
            )
            distance = math.sqrt(
                math.fsum(item * item for item in displacement)
            )
            margin = abs(distance - case.parameters.cutoff_angstrom)
            rows.append(
                {
                    "atom_i": atom_i,
                    "atom_j": atom_j,
                    "distance_angstrom_hex": distance.hex(),
                    "cutoff_margin_angstrom_hex": margin.hex(),
                    "scaled_charge_product_e2_hex": charge_product.hex(),
                    "mixed_epsilon_kcal_per_mol_hex": epsilon.hex(),
                }
            )
    return rows


def _minimum_cutoff_margin(
    case: _parent._TrajectoryCase,
    coordinates: Sequence[Sequence[float]],
) -> float:
    rows = _active_pair_rows(case, coordinates)
    if not rows:
        raise OpenMMForceDoubleRattleTrajectoryError(
            "cutoff audit found no force-active pairs"
        )
    return min(
        _float_field(row, "cutoff_margin_angstrom_hex")
        for row in rows
    )


def _require_cutoff_margin(
    case: _parent._TrajectoryCase,
    coordinates: Sequence[Sequence[float]],
) -> float:
    margin = _minimum_cutoff_margin(case, coordinates)
    if margin < OPENMM_FORCE_DOUBLE_RATTLE_CUTOFF_MARGIN_THRESHOLD_ANGSTROM:
        raise OpenMMForceDoubleRattleTrajectoryError(
            "force-active pair violates the cutoff-margin requirement"
        )
    return margin


def _configuration_projection() -> dict[str, object]:
    prepared_cases = _materialize_cases()
    cases = [_trajectory_case(row) for row in prepared_cases]
    return {
        "schema_id": OPENMM_FORCE_DOUBLE_RATTLE_TRAJECTORY_CONFIG_SCHEMA_ID,
        "protocol_id": OPENMM_FORCE_DOUBLE_RATTLE_TRAJECTORY_PROTOCOL_ID,
        "evidence_status": {
            "development_successor": True,
            "confirmatory_scientific_protocol": False,
            "thresholds_selected_after_exploratory_implementation": True,
            "future_fresh_holdout_required": True,
        },
        "predecessor_configuration_sha256": (
            "e40902895938a4d7848e5207d0fe29de1ecaa43ae600c9c9ed8f7b7d0ac6c1b5"
        ),
        "superseded_development_result": {
            "configuration_sha256": (
                "332e675b2c45a6fffca102559ddd4bca2a11e24e592d0daaca6807417af36682"
            ),
            "observation_sha256": (
                "478745074eb22318fad3cdd7427c0cdb77511bb299cd7413770eaee5ec71fab8"
            ),
            "receipt_file_sha256": (
                "c1cadc22ffe8b55e8ac810097868d617ba4517bfc7ab8df26474b69181009ede"
            ),
            "reason": (
                "current-vector nonlinear position projection exceeded the "
                "unchanged energy-drift gate for the +1 solute/Cl case"
            ),
        },
        "operational_algorithms": {
            "explicit_solvent": REFERENCE_EXPLICIT_SOLVENT_ALGORITHM_ID,
            "oracle_integrator": OPENMM_FORCE_DOUBLE_RATTLE_ALGORITHM_ID,
            "engine_nve": _parent.REFERENCE_NVE_ALGORITHM_ID,
            "engine_shake_rattle": (
                _parent.REFERENCE_SHAKE_RATTLE_ALGORITHM_ID
            ),
            "direct_ewald": _parent.REFERENCE_EWALD_ALGORITHM_ID,
        },
        "materializer_profile_fingerprint_sha256": (
            REFERENCE_EXPLICIT_SOLVENT_PROFILE_FINGERPRINT_SHA256
        ),
        "case_order": [row.case_id for row in prepared_cases],
        "cases": [
            {
                "case_id": prepared.case_id,
                "source_system_sha256": canonical_system_sha256(
                    prepared.source_system
                ),
                "source_parameters": prepared.source_parameters.to_dict(),
                "preparation_config": (
                    prepared.preparation_config.to_dict()
                ),
                "preparation_receipt": prepared.preparation.receipt.to_dict(),
                "trajectory_input": _parent._case_input_document(case),
                "oracle_config": _oracle_config(case).to_dict(),
                "oracle_constraints": [
                    row.to_dict() for row in _oracle_constraints(case)
                ],
                "force_configuration": _force_configuration_document(case),
                "initial_minimum_cutoff_margin_angstrom_hex": (
                    _require_cutoff_margin(
                        case,
                        case.system.coordinates[0].tolist(),
                    ).hex()
                ),
            }
            for prepared, case in zip(prepared_cases, cases)
        ],
        "trajectory": {
            "timestep_ps_hex": (1.0e-4).hex(),
            "steps": 16,
            "restart_step": 7,
            "initial_velocity_policy": (
                "index_derived_nonzero_binary64_v1"
            ),
            "reciprocal_max_indices": [2, 2, 2],
        },
        "thresholds": {
            "cutoff_margin_minimum_angstrom_hex": (
                OPENMM_FORCE_DOUBLE_RATTLE_CUTOFF_MARGIN_THRESHOLD_ANGSTROM.hex()
            ),
            "same_coordinate_energy_max_abs_kcal_per_mol_hex": (
                OPENMM_FORCE_DOUBLE_RATTLE_ENERGY_ERROR_THRESHOLD_KCAL_PER_MOL.hex()
            ),
            "same_coordinate_force_max_abs_kcal_per_mol_angstrom_hex": (
                OPENMM_FORCE_DOUBLE_RATTLE_FORCE_MAX_THRESHOLD_KCAL_PER_MOL_ANGSTROM.hex()
            ),
            "same_coordinate_force_rms_kcal_per_mol_angstrom_hex": (
                OPENMM_FORCE_DOUBLE_RATTLE_FORCE_RMS_THRESHOLD_KCAL_PER_MOL_ANGSTROM.hex()
            ),
            "trajectory_coordinate_max_abs_angstrom_hex": (
                OPENMM_FORCE_DOUBLE_RATTLE_COORDINATE_THRESHOLD_ANGSTROM.hex()
            ),
            "trajectory_velocity_max_abs_angstrom_per_ps_hex": (
                OPENMM_FORCE_DOUBLE_RATTLE_VELOCITY_THRESHOLD_ANGSTROM_PER_PS.hex()
            ),
            "trajectory_total_energy_max_abs_kcal_per_mol_hex": (
                OPENMM_FORCE_DOUBLE_RATTLE_TOTAL_ENERGY_THRESHOLD_KCAL_PER_MOL.hex()
            ),
            "position_constraint_max_abs_angstrom_hex": (
                OPENMM_FORCE_DOUBLE_RATTLE_POSITION_RESIDUAL_THRESHOLD_ANGSTROM.hex()
            ),
            "velocity_constraint_max_abs_angstrom_per_ps_hex": (
                OPENMM_FORCE_DOUBLE_RATTLE_VELOCITY_RESIDUAL_THRESHOLD_ANGSTROM_PER_PS.hex()
            ),
            "per_implementation_energy_drift_max_abs_kcal_per_mol_hex": (
                OPENMM_FORCE_DOUBLE_RATTLE_DRIFT_THRESHOLD_KCAL_PER_MOL.hex()
            ),
        },
        "failure_rows": [
            {
                "case_id": "cutoff_margin_violation",
                "expected_code": "cutoff_margin_required",
            },
            {
                "case_id": "non_neutral_direct_ewald",
                "expected_code": "neutrality_required",
            },
            {
                "case_id": "missing_explicit_mass",
                "expected_code": "explicit_mass_required",
            },
            {
                "case_id": "oracle_atom_capacity",
                "expected_code": "oracle_atom_capacity_exceeded",
            },
            {
                "case_id": "position_projection_budget",
                "expected_code": "position_projection_budget_exhausted",
            },
            {
                "case_id": "tampered_oracle_checkpoint",
                "expected_code": "checkpoint_digest_mismatch",
            },
        ],
        "claim_gates": {
            "scientifically_validated": False,
            "production_eligible": False,
            "p2_complete": False,
            "claim_safe": False,
        },
    }


def openmm_force_double_rattle_configuration_document() -> dict[str, object]:
    """Return the frozen input-only development configuration."""

    projection = _configuration_projection()
    digest = _sha256(projection)
    if digest != FROZEN_OPENMM_FORCE_DOUBLE_RATTLE_TRAJECTORY_CONFIG_SHA256:
        raise OpenMMForceDoubleRattleTrajectoryError(
            "OpenMM-force double-RATTLE configuration digest drifted"
        )
    return {**projection, "configuration_sha256": digest}


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _source_identity_document() -> dict[str, object]:
    root = _repository_root()
    relative_paths = (
        "betelgeuze_engine_v2/offline/openmm_force_double_rattle_trajectory.py",
        "betelgeuze_engine_v2/offline/openmm_force_double_rattle_oracle.py",
        "betelgeuze_engine_v2/offline/openmm_reference_nve_trajectory.py",
        "betelgeuze_engine_v2/physics/reference_explicit_solvent.py",
        "betelgeuze_engine_v2/physics/reference_nve.py",
        "betelgeuze_engine_v2/physics/reference_ewald.py",
        "betelgeuze_engine_v2/physics/reference_shake_rattle.py",
        "betelgeuze_engine_v2/physics/reference_parameters.py",
    )
    source_rows = [
        {
            "path": relative,
            **_parent._hash_regular_file(root / relative),
        }
        for relative in relative_paths
    ]
    parent_identity = _parent._source_identity_document()
    projection = {
        "source_files": source_rows,
        "source_manifest_sha256": _sha256(source_rows),
        "runtime_dependencies": parent_identity["dependencies"],
        "runtime_dependency_identity_sha256": parent_identity[
            "dependency_identity_sha256"
        ],
        "oracle_import_boundary": {
            "stdlib_only_source": True,
            "engine_nve_imported": False,
            "engine_shake_rattle_imported": False,
            "torch_imported": False,
            "openmm_imported": False,
        },
        "absolute_paths_disclosed": False,
    }
    return {**projection, "source_identity_sha256": _sha256(projection)}


def _masses(case: _parent._TrajectoryCase) -> tuple[float, ...]:
    rows = []
    for atom in case.system.atoms:
        if atom.mass_da is None or atom.mass_da <= 0.0:
            raise OpenMMForceDoubleRattleTrajectoryError(
                "trajectory requires positive explicit masses"
            )
        rows.append(float(atom.mass_da))
    return tuple(rows)


def _oracle_restart(
    *,
    case: _parent._TrajectoryCase,
    force_configuration_sha256: str,
    evaluator: Any,
    full_result: Any,
) -> dict[str, object]:
    oracle_config = _oracle_config(case)
    constraints = _oracle_constraints(case)
    common = {
        "system_sha256": canonical_system_sha256(case.system),
        "force_configuration_sha256": force_configuration_sha256,
        "masses_da": _masses(case),
        "constraints": constraints,
        "config": oracle_config,
        "evaluator": evaluator.evaluate,
    }
    paused = run_openmm_force_double_rattle(
        **common,
        coordinates=case.system.coordinates[0].tolist(),
        velocities_angstrom_per_ps=case.velocities[0].tolist(),
        steps=case.restart_step,
    )
    resumed = resume_openmm_force_double_rattle(
        **common,
        checkpoint=paused.checkpoint.to_dict(),
        additional_steps=case.steps - case.restart_step,
    )
    full_checkpoint = full_result.checkpoint
    resumed_checkpoint = resumed.checkpoint
    projection = {
        "restart_step": case.restart_step,
        "paused_checkpoint": paused.checkpoint.to_dict(),
        "full_checkpoint_sha256": full_checkpoint.checkpoint_sha256,
        "resumed_checkpoint_sha256": resumed_checkpoint.checkpoint_sha256,
        "coordinates_bit_exact": (
            full_checkpoint.coordinates == resumed_checkpoint.coordinates
        ),
        "velocities_bit_exact": (
            full_checkpoint.velocities == resumed_checkpoint.velocities
        ),
        "forces_bit_exact": (
            full_checkpoint.forces == resumed_checkpoint.forces
        ),
        "potential_energy_bit_exact": (
            full_checkpoint.potential_energy_kcal_per_mol.hex()
            == resumed_checkpoint.potential_energy_kcal_per_mol.hex()
        ),
        "checkpoint_bit_exact": (
            full_checkpoint.to_dict() == resumed_checkpoint.to_dict()
        ),
        "trajectory_head_bit_exact": (
            full_checkpoint.trajectory_head_sha256
            == resumed_checkpoint.trajectory_head_sha256
        ),
        "projection_counts_bit_exact": (
            full_checkpoint.cumulative_position_sweeps
            == resumed_checkpoint.cumulative_position_sweeps
            and full_checkpoint.cumulative_velocity_sweeps
            == resumed_checkpoint.cumulative_velocity_sweeps
        ),
        "resumed_final_frame": resumed.frames[-1],
    }
    checks = {
        name: projection[name]
        for name in (
            "coordinates_bit_exact",
            "velocities_bit_exact",
            "forces_bit_exact",
            "potential_energy_bit_exact",
            "checkpoint_bit_exact",
            "trajectory_head_bit_exact",
            "projection_counts_bit_exact",
        )
    }
    return {
        **projection,
        "metric_checks": checks,
        "metric_pass": all(checks.values()),
        "restart_sha256": _sha256(projection),
    }


def _case_row(
    prepared: _PreparedCase,
    *,
    openmm: Any,
    unit: Any,
    reference: Any,
) -> dict[str, object]:
    replay = verify_reference_explicit_solvent_replay(
        prepared.source_system,
        prepared.source_parameters,
        prepared.preparation_config,
        prepared.preparation,
    )
    case = _trajectory_case(prepared)
    _parent._require_case_domain(case)
    initial_margin = _require_cutoff_margin(
        case,
        case.system.coordinates[0].tolist(),
    )
    openmm_system, mapping = _parent._build_openmm_system(
        case,
        openmm=openmm,
    )
    force_configuration = _force_configuration_document(case)
    force_configuration_sha256 = force_configuration[
        "force_configuration_sha256"
    ]
    if not isinstance(force_configuration_sha256, str):
        raise OpenMMForceDoubleRattleTrajectoryError(
            "force configuration digest is invalid"
        )
    engine_result = run_reference_nve(
        case.system,
        case.parameters,
        case.velocities,
        steps=case.steps,
        config=case.nve_config,
        constraint_config=case.constraint_config,
    )
    engine_states = tuple(
        _parent._engine_state(case, frame)
        for frame in engine_result.frames
    )
    oracle_config = _oracle_config(case)
    constraints = _oracle_constraints(case)
    with _parent._OpenMMStaticEvaluator(
        openmm=openmm,
        unit=unit,
        reference=reference,
        openmm_system=openmm_system,
        atom_count=case.system.atom_count,
    ) as evaluator:
        oracle_result = run_openmm_force_double_rattle(
            system_sha256=canonical_system_sha256(case.system),
            force_configuration_sha256=force_configuration_sha256,
            coordinates=case.system.coordinates[0].tolist(),
            velocities_angstrom_per_ps=case.velocities[0].tolist(),
            masses_da=_masses(case),
            constraints=constraints,
            config=oracle_config,
            steps=case.steps,
            evaluator=evaluator.evaluate,
        )
        oracle_states = oracle_result.frames
        comparisons = tuple(
            _parent._comparison_row(
                case=case,
                engine_state=engine_state,
                openmm_state=oracle_state,
                static_openmm=evaluator,
            )
            for engine_state, oracle_state in zip(
                engine_states,
                oracle_states,
            )
        )
        oracle_restart = _oracle_restart(
            case=case,
            force_configuration_sha256=force_configuration_sha256,
            evaluator=evaluator,
            full_result=oracle_result,
        )
    engine_restart = _parent._engine_restart(case, engine_result)
    energy_errors = []
    force_max_errors = []
    force_rms_errors = []
    coordinate_errors = []
    velocity_errors = []
    total_energy_errors = []
    for row in comparisons:
        for side in (
            "engine_at_engine_coordinates",
            "engine_at_openmm_coordinates",
        ):
            comparison = row[side]
            if not isinstance(comparison, Mapping):
                raise OpenMMForceDoubleRattleTrajectoryError(
                    "same-coordinate comparison is invalid"
                )
            energy_errors.append(
                _float_field(
                    comparison,
                    "energy_max_abs_error_kcal_per_mol_hex",
                )
            )
            force_max_errors.append(
                _float_field(
                    comparison,
                    "force_max_abs_error_kcal_per_mol_angstrom_hex",
                )
            )
            force_rms_errors.append(
                _float_field(
                    comparison,
                    "force_rms_error_kcal_per_mol_angstrom_hex",
                )
            )
        coordinate_errors.append(
            _float_field(
                row,
                "trajectory_coordinate_max_abs_error_angstrom_hex",
            )
        )
        velocity_errors.append(
            _float_field(
                row,
                "trajectory_velocity_max_abs_error_angstrom_per_ps_hex",
            )
        )
        total_energy_errors.append(
            _float_field(
                row,
                "trajectory_total_energy_max_abs_error_kcal_per_mol_hex",
            )
        )
    position_residuals = [
        _float_field(
            state,
            "position_constraint_residual_angstrom_hex",
        )
        for state in (*engine_states, *oracle_states)
    ]
    velocity_residuals = [
        _float_field(
            state,
            "velocity_constraint_residual_angstrom_per_ps_hex",
        )
        for state in (*engine_states, *oracle_states)
    ]
    engine_totals = [
        _float_field(state, "total_energy_kcal_per_mol_hex")
        for state in engine_states
    ]
    oracle_totals = [
        _float_field(state, "total_energy_kcal_per_mol_hex")
        for state in oracle_states
    ]
    engine_drift = max(
        abs(item - engine_totals[0]) for item in engine_totals
    )
    oracle_drift = max(
        abs(item - oracle_totals[0]) for item in oracle_totals
    )
    cutoff_margins = []
    for state in (*engine_states, *oracle_states):
        coordinates = _parent._rows_from_hex(
            state["coordinates_angstrom_hex"],
            atom_count=case.system.atom_count,
            name="trajectory cutoff audit coordinates",
        )
        cutoff_margins.append(_minimum_cutoff_margin(case, coordinates))
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
        "oracle_energy_drift_max_abs_kcal_per_mol_hex": oracle_drift.hex(),
        "minimum_trajectory_cutoff_margin_angstrom_hex": min(
            cutoff_margins
        ).hex(),
    }
    metric_checks = {
        "same_coordinate_energy_metric_pass": (
            max(energy_errors)
            <= OPENMM_FORCE_DOUBLE_RATTLE_ENERGY_ERROR_THRESHOLD_KCAL_PER_MOL
        ),
        "same_coordinate_force_max_metric_pass": (
            max(force_max_errors)
            <= OPENMM_FORCE_DOUBLE_RATTLE_FORCE_MAX_THRESHOLD_KCAL_PER_MOL_ANGSTROM
        ),
        "same_coordinate_force_rms_metric_pass": (
            max(force_rms_errors)
            <= OPENMM_FORCE_DOUBLE_RATTLE_FORCE_RMS_THRESHOLD_KCAL_PER_MOL_ANGSTROM
        ),
        "trajectory_coordinate_metric_pass": (
            max(coordinate_errors)
            <= OPENMM_FORCE_DOUBLE_RATTLE_COORDINATE_THRESHOLD_ANGSTROM
        ),
        "trajectory_velocity_metric_pass": (
            max(velocity_errors)
            <= OPENMM_FORCE_DOUBLE_RATTLE_VELOCITY_THRESHOLD_ANGSTROM_PER_PS
        ),
        "trajectory_total_energy_metric_pass": (
            max(total_energy_errors)
            <= OPENMM_FORCE_DOUBLE_RATTLE_TOTAL_ENERGY_THRESHOLD_KCAL_PER_MOL
        ),
        "position_constraint_metric_pass": (
            max(position_residuals)
            <= OPENMM_FORCE_DOUBLE_RATTLE_POSITION_RESIDUAL_THRESHOLD_ANGSTROM
        ),
        "velocity_constraint_metric_pass": (
            max(velocity_residuals)
            <= OPENMM_FORCE_DOUBLE_RATTLE_VELOCITY_RESIDUAL_THRESHOLD_ANGSTROM_PER_PS
        ),
        "engine_energy_drift_metric_pass": (
            engine_drift
            <= OPENMM_FORCE_DOUBLE_RATTLE_DRIFT_THRESHOLD_KCAL_PER_MOL
        ),
        "oracle_energy_drift_metric_pass": (
            oracle_drift
            <= OPENMM_FORCE_DOUBLE_RATTLE_DRIFT_THRESHOLD_KCAL_PER_MOL
        ),
        "trajectory_cutoff_margin_metric_pass": (
            min(cutoff_margins)
            >= OPENMM_FORCE_DOUBLE_RATTLE_CUTOFF_MARGIN_THRESHOLD_ANGSTROM
        ),
        "engine_restart_metric_pass": bool(engine_restart["metric_pass"]),
        "oracle_restart_metric_pass": bool(oracle_restart["metric_pass"]),
    }
    projection = {
        "schema_id": OPENMM_FORCE_DOUBLE_RATTLE_TRAJECTORY_CASE_SCHEMA_ID,
        "case_id": prepared.case_id,
        "status": "completed",
        "preparation_replay_pass": replay is prepared.preparation,
        "preparation_receipt": prepared.preparation.receipt.to_dict(),
        "initial_minimum_cutoff_margin_angstrom_hex": initial_margin.hex(),
        "force_configuration": force_configuration,
        "openmm_mapping": mapping,
        "engine_trace": list(engine_states),
        "oracle_trace": list(oracle_states),
        "same_step_comparisons": list(comparisons),
        "engine_restart": engine_restart,
        "oracle_restart": oracle_restart,
        "engine_projection_counts": {
            "cumulative_position_sweeps": (
                engine_result.cumulative_shake_iteration_count
            ),
            "cumulative_velocity_sweeps": (
                engine_result.cumulative_rattle_iteration_count
            ),
        },
        "oracle_projection_counts": {
            "cumulative_position_sweeps": (
                oracle_result.checkpoint.cumulative_position_sweeps
            ),
            "cumulative_velocity_sweeps": (
                oracle_result.checkpoint.cumulative_velocity_sweeps
            ),
        },
        "maxima": maxima,
        "metric_checks": metric_checks,
        "metric_pass": all(metric_checks.values()),
        "scientifically_validated": False,
        "claim_safe": False,
    }
    return {**projection, "case_sha256": _sha256(projection)}


def _cutoff_failure() -> dict[str, object]:
    prepared = _materialize_cases()[0]
    case = _trajectory_case(prepared)
    rows = _active_pair_rows(
        case,
        case.system.coordinates[0].tolist(),
    )
    selected = min(
        rows,
        key=lambda row: _float_field(
            row,
            "cutoff_margin_angstrom_hex",
        ),
    )
    cutoff = _float_field(selected, "distance_angstrom_hex")
    parameters = replace(
        case.parameters,
        cutoff_angstrom=cutoff,
        switch_start_angstrom=min(3.0, 0.75 * cutoff),
    )
    variant = replace(case, parameters=parameters)
    observed = "unexpected_success"
    message = ""
    try:
        _require_cutoff_margin(
            variant,
            variant.system.coordinates[0].tolist(),
        )
    except OpenMMForceDoubleRattleTrajectoryError as exc:
        message = str(exc)
        if "cutoff-margin" in message:
            observed = "cutoff_margin_required"
        else:
            observed = "unexpected_cutoff_error"
    projection = {
        "case_id": "cutoff_margin_violation",
        "status": "expected_fail_closed",
        "expected_code": "cutoff_margin_required",
        "observed_code": observed,
        "message": message,
        "metric_pass": observed == "cutoff_margin_required",
    }
    return {**projection, "failure_sha256": _sha256(projection)}


def _materializer_failure(case_id: str) -> dict[str, object]:
    if case_id == "non_neutral_direct_ewald":
        source = _source_system(case_id=case_id, charge_e=0.0)
        parameters = _source_parameters(source, charge_e=0.0)
        config = ReferenceExplicitSolventConfig(
            box_lengths_angstrom=(13.5, 13.5, 13.5),
            water_count=4,
            sodium_count=1,
            chloride_count=0,
            lattice_spacing_angstrom=3.4,
            water_constraint_tolerance_angstrom=1.0e-10,
        )
        expected = "neutrality_required"
    elif case_id == "missing_explicit_mass":
        source = _source_system(
            case_id=case_id,
            charge_e=0.0,
            mass_da=None,
        )
        parameters = _source_parameters(source, charge_e=0.0)
        config = _preparation_config(sodium_count=0, chloride_count=0)
        expected = "explicit_mass_required"
    else:
        raise OpenMMForceDoubleRattleTrajectoryError(
            "unknown materializer failure case"
        )
    observed = "unexpected_success"
    message = ""
    try:
        prepare_reference_explicit_solvent(source, parameters, config)
    except ReferenceExplicitSolventError as exc:
        message = str(exc)
        if "neutral system" in message:
            observed = "neutrality_required"
        elif "missing mass_da" in message:
            observed = "explicit_mass_required"
        else:
            observed = "unexpected_materializer_error"
    projection = {
        "case_id": case_id,
        "status": "expected_fail_closed",
        "expected_code": expected,
        "observed_code": observed,
        "message": message,
        "metric_pass": observed == expected,
    }
    return {**projection, "failure_sha256": _sha256(projection)}


def _capacity_failure() -> dict[str, object]:
    atom_count = _parent.OPENMM_REFERENCE_NVE_MAX_ATOMS + 1
    atoms = tuple(
        Atom(
            index=index,
            name=f"C{index + 1}",
            element="C",
            atomic_number=6,
            residue_index=0,
            partial_charge_e=0.0,
            mass_da=12.011,
        )
        for index in range(atom_count)
    )
    system = AllAtomSystem(
        system_id="double-rattle-oracle-capacity",
        atoms=atoms,
        bonds=(),
        residues=(
            Residue(
                index=0,
                name="MOL",
                chain_index=0,
                sequence_number=1,
                atom_indices=tuple(range(atom_count)),
                entity_type="non-polymer",
                hetero=True,
            ),
        ),
        chains=(Chain(index=0, chain_id="A", residue_indices=(0,)),),
        coordinates=torch.tensor(
            (
                tuple(
                    (
                        1.0 + (index % 4) * 2.0,
                        1.0 + ((index // 4) % 4) * 2.0,
                        1.0 + (index // 16) * 2.0,
                    )
                    for index in range(atom_count)
                ),
            ),
            dtype=torch.float64,
        ),
        provenance=StructureProvenance(source_format="frozen-failure-row"),
        cell=UnitCell.orthorhombic(
            (13.5, 13.5, 13.5),
            dtype=torch.float64,
        ),
    )
    parameters = ReferenceForceFieldParameters(
        parameter_set_id="double-rattle-oracle-capacity",
        parameter_set_version="1.0.0",
        topology_sha256=canonical_topology_sha256(system),
        atom_parameters=tuple(
            AtomNonbondedParameter(index, 3.4, 0.1, 0.0)
            for index in range(atom_count)
        ),
        cutoff_angstrom=4.0,
        switch_start_angstrom=3.0,
    )
    case = _parent._TrajectoryCase(
        case_id="oracle_atom_capacity",
        system=system,
        parameters=parameters,
        velocities=torch.zeros((1, atom_count, 3), dtype=torch.float64),
        nve_config=ReferenceNVEConfig(
            timestep_ps=1.0e-4,
            ewald_config=ReferenceEwaldConfig(
                alpha_per_angstrom=0.35,
                reciprocal_max_indices=(2, 2, 2),
            ),
        ),
        constraint_config=ReferenceSHAKERATTLEConfig(),
        steps=1,
        restart_step=0,
    )
    observed = "unexpected_success"
    message = ""
    try:
        _parent._require_case_domain(case)
    except _parent.OpenMMReferenceNVETrajectoryError as exc:
        message = str(exc)
        if "bounded coordinate model" in message:
            observed = "oracle_atom_capacity_exceeded"
        else:
            observed = "unexpected_oracle_error"
    projection = {
        "case_id": "oracle_atom_capacity",
        "status": "expected_fail_closed",
        "expected_code": "oracle_atom_capacity_exceeded",
        "observed_code": observed,
        "message": message,
        "atom_count": atom_count,
        "maximum_atom_count": _parent.OPENMM_REFERENCE_NVE_MAX_ATOMS,
        "metric_pass": observed == "oracle_atom_capacity_exceeded",
    }
    return {**projection, "failure_sha256": _sha256(projection)}


def _zero_evaluator(
    coordinates: Sequence[Sequence[float]],
) -> tuple[float, tuple[tuple[float, float, float], ...]]:
    return 0.0, tuple((0.0, 0.0, 0.0) for _ in coordinates)


def _projection_failure() -> dict[str, object]:
    digest = hashlib.sha256(b"projection-failure").hexdigest()
    constraints = (
        DoubleRattleDistanceConstraint(0, 1, 1.0),
        DoubleRattleDistanceConstraint(0, 2, 1.0),
        DoubleRattleDistanceConstraint(1, 2, 1.0),
    )
    observed = "unexpected_success"
    message = ""
    try:
        run_openmm_force_double_rattle(
            system_sha256=digest,
            force_configuration_sha256=digest,
            coordinates=(
                (1.0, 1.0, 1.0),
                (2.01, 1.0, 1.0),
                (1.5, 1.87, 1.0),
            ),
            velocities_angstrom_per_ps=((0.0, 0.0, 0.0),) * 3,
            masses_da=(1.0, 1.0, 1.0),
            constraints=constraints,
            config=OpenMMForceDoubleRattleConfig(
                timestep_ps=1.0e-4,
                box_lengths_angstrom=(13.5, 13.5, 13.5),
                position_tolerance_angstrom=1.0e-14,
                velocity_tolerance_angstrom_per_ps=1.0e-12,
                max_position_sweeps=1,
                max_velocity_sweeps=500,
            ),
            steps=0,
            evaluator=_zero_evaluator,
        )
    except OpenMMForceDoubleRattleError as exc:
        message = str(exc)
        if "position projection exhausted" in message:
            observed = "position_projection_budget_exhausted"
        else:
            observed = "unexpected_projection_error"
    projection = {
        "case_id": "position_projection_budget",
        "status": "expected_fail_closed",
        "expected_code": "position_projection_budget_exhausted",
        "observed_code": observed,
        "message": message,
        "metric_pass": observed == "position_projection_budget_exhausted",
    }
    return {**projection, "failure_sha256": _sha256(projection)}


def _checkpoint_failure() -> dict[str, object]:
    digest = hashlib.sha256(b"checkpoint-failure").hexdigest()
    constraint = (DoubleRattleDistanceConstraint(0, 1, 1.0),)
    config = OpenMMForceDoubleRattleConfig(
        timestep_ps=1.0e-4,
        box_lengths_angstrom=(13.5, 13.5, 13.5),
    )
    common = {
        "system_sha256": digest,
        "force_configuration_sha256": digest,
        "masses_da": (1.0, 1.0),
        "constraints": constraint,
        "config": config,
        "evaluator": _zero_evaluator,
    }
    result = run_openmm_force_double_rattle(
        **common,
        coordinates=((1.0, 1.0, 1.0), (2.0, 1.0, 1.0)),
        velocities_angstrom_per_ps=((0.0, 0.1, 0.0), (0.0, -0.1, 0.0)),
        steps=1,
    )
    payload = deepcopy(result.checkpoint.to_dict())
    payload["step"] = 0
    observed = "unexpected_success"
    message = ""
    try:
        resume_openmm_force_double_rattle(
            **common,
            checkpoint=payload,
            additional_steps=1,
        )
    except OpenMMForceDoubleRattleError as exc:
        message = str(exc)
        if "checkpoint digest mismatch" in message:
            observed = "checkpoint_digest_mismatch"
        else:
            observed = "unexpected_checkpoint_error"
    projection = {
        "case_id": "tampered_oracle_checkpoint",
        "status": "expected_fail_closed",
        "expected_code": "checkpoint_digest_mismatch",
        "observed_code": observed,
        "message": message,
        "metric_pass": observed == "checkpoint_digest_mismatch",
    }
    return {**projection, "failure_sha256": _sha256(projection)}


def _failure_rows() -> list[dict[str, object]]:
    return [
        _cutoff_failure(),
        _materializer_failure("non_neutral_direct_ewald"),
        _materializer_failure("missing_explicit_mass"),
        _capacity_failure(),
        _projection_failure(),
        _checkpoint_failure(),
    ]


def _observation_projection() -> dict[str, object]:
    configuration = openmm_force_double_rattle_configuration_document()
    runtime_identity, openmm, unit, reference = _parent._openmm_modules()
    case_rows = [
        _case_row(
            prepared,
            openmm=openmm,
            unit=unit,
            reference=reference,
        )
        for prepared in _materialize_cases()
    ]
    failure_rows = _failure_rows()
    all_metrics_pass = all(
        bool(row["metric_pass"]) for row in (*case_rows, *failure_rows)
    )
    return {
        "schema_id": (
            OPENMM_FORCE_DOUBLE_RATTLE_TRAJECTORY_OBSERVATION_SCHEMA_ID
        ),
        "protocol_id": OPENMM_FORCE_DOUBLE_RATTLE_TRAJECTORY_PROTOCOL_ID,
        "configuration_sha256": configuration["configuration_sha256"],
        "configuration": configuration,
        "source_identity": _source_identity_document(),
        "runtime_identity": runtime_identity,
        "case_rows": case_rows,
        "failure_rows": failure_rows,
        "summary": {
            "physical_case_count": len(case_rows),
            "physical_case_metric_pass_count": sum(
                bool(row["metric_pass"]) for row in case_rows
            ),
            "failure_case_count": len(failure_rows),
            "failure_case_metric_pass_count": sum(
                bool(row["metric_pass"]) for row in failure_rows
            ),
            "all_development_metrics_pass": all_metrics_pass,
            "confirmatory_scientific_protocol": False,
            "host_count": 1,
            "independent_reviewer_approved": False,
            "production_eligible": False,
            "p2_complete": False,
        },
        "scientific_blockers": list(
            OPENMM_FORCE_DOUBLE_RATTLE_SCIENTIFIC_BLOCKERS
        ),
        "scientifically_validated": False,
        "claim_safe": False,
    }


def build_openmm_force_double_rattle_observation() -> dict[str, object]:
    """Execute the frozen development successor."""

    projection = _observation_projection()
    return {**projection, "observation_sha256": _sha256(projection)}


def require_openmm_force_double_rattle_observation(
    value: Mapping[str, object],
) -> dict[str, object]:
    """Reexecute all cases, failures, identities, and numeric metrics."""

    if not isinstance(value, Mapping):
        raise OpenMMForceDoubleRattleTrajectoryError(
            "double-RATTLE trajectory observation must be a mapping"
        )
    observed = json.loads(_canonical_bytes(dict(value)).decode("ascii"))
    expected = {
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
    if set(observed) != expected:
        raise OpenMMForceDoubleRattleTrajectoryError(
            "double-RATTLE trajectory observation fields are invalid"
        )
    digest = _require_sha256(
        observed.get("observation_sha256"),
        name="observation_sha256",
    )
    projection = {
        key: item
        for key, item in observed.items()
        if key != "observation_sha256"
    }
    if digest != _sha256(projection):
        raise OpenMMForceDoubleRattleTrajectoryError(
            "double-RATTLE trajectory observation digest mismatch"
        )
    if (
        observed.get("schema_id")
        != OPENMM_FORCE_DOUBLE_RATTLE_TRAJECTORY_OBSERVATION_SCHEMA_ID
        or observed.get("protocol_id")
        != OPENMM_FORCE_DOUBLE_RATTLE_TRAJECTORY_PROTOCOL_ID
        or observed.get("scientifically_validated") is not False
        or observed.get("claim_safe") is not False
    ):
        raise OpenMMForceDoubleRattleTrajectoryError(
            "double-RATTLE trajectory observation overstates its claim"
        )
    current = _observation_projection()
    if projection != current:
        raise OpenMMForceDoubleRattleTrajectoryError(
            "double-RATTLE trajectory observation does not reproduce current "
            "source, runtime, traces, failures, or metrics"
        )
    return observed


def write_openmm_force_double_rattle_observation(
    path: Path | str,
    observation: Mapping[str, object],
) -> Path:
    """Write one verified private receipt without replacing other evidence."""

    verified = require_openmm_force_double_rattle_observation(observation)
    payload = json.dumps(
        verified,
        allow_nan=False,
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
    ) + "\n"
    encoded_size = len(payload.encode("utf-8"))
    if encoded_size > OPENMM_FORCE_DOUBLE_RATTLE_MAX_OBSERVATION_BYTES:
        raise OpenMMForceDoubleRattleTrajectoryError(
            "double-RATTLE observation exceeds its bounded size"
        )
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_symlink():
        raise OpenMMForceDoubleRattleTrajectoryError(
            "double-RATTLE observation path must not be a symlink"
        )
    if destination.exists():
        metadata = destination.lstat()
        if not stat.S_ISREG(metadata.st_mode):
            raise OpenMMForceDoubleRattleTrajectoryError(
                "double-RATTLE observation path must be a regular file"
            )
        if metadata.st_size > OPENMM_FORCE_DOUBLE_RATTLE_MAX_OBSERVATION_BYTES:
            raise OpenMMForceDoubleRattleTrajectoryError(
                "existing double-RATTLE observation exceeds its bound"
            )
        if destination.read_text(encoding="utf-8") != payload:
            raise OpenMMForceDoubleRattleTrajectoryError(
                "refusing to overwrite a different double-RATTLE observation"
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
            raise OpenMMForceDoubleRattleTrajectoryError(
                "double-RATTLE observation path appeared during creation"
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


def read_openmm_force_double_rattle_observation(
    path: Path | str,
) -> dict[str, object]:
    """Read one private receipt and reproduce it completely."""

    source = Path(path)
    metadata = source.lstat()
    if not stat.S_ISREG(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
        raise OpenMMForceDoubleRattleTrajectoryError(
            "double-RATTLE observation must be a regular non-symlink file"
        )
    if metadata.st_mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise OpenMMForceDoubleRattleTrajectoryError(
            "double-RATTLE observation must not be group/world accessible"
        )
    if metadata.st_size > OPENMM_FORCE_DOUBLE_RATTLE_MAX_OBSERVATION_BYTES:
        raise OpenMMForceDoubleRattleTrajectoryError(
            "double-RATTLE observation exceeds its bounded size"
        )
    try:
        with source.open("rb") as handle:
            raw = handle.read(
                OPENMM_FORCE_DOUBLE_RATTLE_MAX_OBSERVATION_BYTES + 1
            )
        if len(raw) > OPENMM_FORCE_DOUBLE_RATTLE_MAX_OBSERVATION_BYTES:
            raise OpenMMForceDoubleRattleTrajectoryError(
                "double-RATTLE observation exceeds its bounded size"
            )
        value = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise OpenMMForceDoubleRattleTrajectoryError(
            "double-RATTLE observation is not readable JSON"
        ) from exc
    return require_openmm_force_double_rattle_observation(value)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build or verify the claim-closed OpenMM-force double-RATTLE "
            "development trajectory observation"
        )
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--output", type=Path)
    action.add_argument("--verify", type=Path)
    arguments = parser.parse_args(argv)
    if arguments.output is not None:
        observation = build_openmm_force_double_rattle_observation()
        destination = write_openmm_force_double_rattle_observation(
            arguments.output,
            observation,
        )
        print(
            json.dumps(
                {
                    "observation_sha256": observation["observation_sha256"],
                    "path": str(destination),
                    "status": (
                        "openmm_force_double_rattle_observation_written"
                    ),
                },
                allow_nan=False,
                ensure_ascii=True,
                sort_keys=True,
            )
        )
        return 0
    verified = read_openmm_force_double_rattle_observation(
        arguments.verify
    )
    print(
        json.dumps(
            {
                "observation_sha256": verified["observation_sha256"],
                "path": str(arguments.verify),
                "status": (
                    "openmm_force_double_rattle_observation_verified"
                ),
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
    "FROZEN_OPENMM_FORCE_DOUBLE_RATTLE_TRAJECTORY_CONFIG_SHA256",
    "OPENMM_FORCE_DOUBLE_RATTLE_MAX_OBSERVATION_BYTES",
    "OPENMM_FORCE_DOUBLE_RATTLE_SCIENTIFIC_BLOCKERS",
    "OPENMM_FORCE_DOUBLE_RATTLE_TRAJECTORY_CONFIG_SCHEMA_ID",
    "OPENMM_FORCE_DOUBLE_RATTLE_TRAJECTORY_OBSERVATION_SCHEMA_ID",
    "OPENMM_FORCE_DOUBLE_RATTLE_TRAJECTORY_PROTOCOL_ID",
    "OpenMMForceDoubleRattleTrajectoryError",
    "build_openmm_force_double_rattle_observation",
    "main",
    "openmm_force_double_rattle_configuration_document",
    "read_openmm_force_double_rattle_observation",
    "require_openmm_force_double_rattle_observation",
    "write_openmm_force_double_rattle_observation",
]
