"""Claim-closed OpenMM receipt for bounded explicit-solvent trajectories.

This successor composes the deterministic explicit-solvent materializer with
the frozen NVE/OpenMM comparison adapter.  It preserves every preregistered
threshold and records known failed rows without converting them into passes.
It is offline evidence only and does not alter the product runtime.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
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
    REFERENCE_EXPLICIT_SOLVENT_PROFILE_SOURCE_SHA256,
    ReferenceExplicitSolventConfig,
    ReferenceExplicitSolventError,
    ReferenceExplicitSolventPreparation,
    prepare_reference_explicit_solvent,
    verify_reference_explicit_solvent_replay,
)
from betelgeuze_engine_v2.offline import (
    openmm_reference_nve_trajectory as _parent,
)


OPENMM_REFERENCE_EXPLICIT_SOLVENT_PROTOCOL_ID = (
    "betelgeuze.engine_v2_openmm_reference_explicit_solvent_trajectory/1.0.0"
)
OPENMM_REFERENCE_EXPLICIT_SOLVENT_CONFIG_SCHEMA_ID = (
    "betelgeuze.engine_v2_openmm_reference_explicit_solvent_config/1.0.0"
)
OPENMM_REFERENCE_EXPLICIT_SOLVENT_OBSERVATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_openmm_reference_explicit_solvent_observation/1.0.0"
)
OPENMM_REFERENCE_EXPLICIT_SOLVENT_CASE_SCHEMA_ID = (
    "betelgeuze.engine_v2_openmm_reference_explicit_solvent_case/1.0.0"
)

# Filled only after reviewing the input-only projection.  It binds the three
# exact materialized cases, thresholds, convergence ladder, failure rows, and
# disposition policy, but not any observed result.
FROZEN_OPENMM_REFERENCE_EXPLICIT_SOLVENT_CONFIG_SHA256 = (
    "e40902895938a4d7848e5207d0fe29de1ecaa43ae600c9c9ed8f7b7d0ac6c1b5"
)

OPENMM_REFERENCE_EXPLICIT_SOLVENT_MAX_OBSERVATION_BYTES = 16 * 1024**2
OPENMM_REFERENCE_EXPLICIT_SOLVENT_TIMESTEP_COORDINATE_THRESHOLD_ANGSTROM = (
    2.5e-7
)
OPENMM_REFERENCE_EXPLICIT_SOLVENT_TIMESTEP_VELOCITY_THRESHOLD_ANGSTROM_PER_PS = (
    2.5e-5
)
OPENMM_REFERENCE_EXPLICIT_SOLVENT_EWALD_ENERGY_THRESHOLD_KCAL_PER_MOL = 5.0e-2
OPENMM_REFERENCE_EXPLICIT_SOLVENT_EWALD_FORCE_THRESHOLD_KCAL_PER_MOL_ANGSTROM = (
    5.0e-2
)

OPENMM_REFERENCE_CONSTRAINTS_SOURCE_URL = (
    "https://raw.githubusercontent.com/openmm/openmm/"
    f"{_parent.OPENMM_REFERENCE_REQUIRED_GIT_REVISION}/"
    "platforms/reference/src/SimTKReference/ReferenceConstraints.cpp"
)
OPENMM_REFERENCE_CONSTRAINTS_SOURCE_SHA256 = (
    "39b9b3b34c610757faa8d00e37820e406a40dfc0f8541ddefffa10e404555665"
)
OPENMM_REFERENCE_SETTLE_SOURCE_URL = (
    "https://raw.githubusercontent.com/openmm/openmm/"
    f"{_parent.OPENMM_REFERENCE_REQUIRED_GIT_REVISION}/"
    "platforms/reference/src/SimTKReference/ReferenceSETTLEAlgorithm.cpp"
)
OPENMM_REFERENCE_SETTLE_SOURCE_SHA256 = (
    "f248f20d5cabaeec4b943406c35f4d598e08e1ef12b464ceb864a374e58da5ae"
)

OPENMM_REFERENCE_EXPLICIT_SOLVENT_SCIENTIFIC_BLOCKERS = (
    "all three rigid-water rows exceed the preregistered 1e-9 Angstrom "
    "position-constraint threshold under OpenMM Reference SETTLE",
    "two rows contain an exact charged-pair cutoff boundary and fail the "
    "preregistered same-coordinate force and trajectory-velocity metrics",
    "the engine timestep ladder is non-monotone at its coordinate roundoff "
    "floor even though both compared errors are below the absolute threshold",
    "single local CPU host observation only",
    "deterministic lattice is not an equilibrated liquid",
    "finite direct-Ewald lattice only; PME is not implemented or validated",
    "no liquid-property, long-time drift, ensemble, GPU, or two-host evidence",
    "OpenMM Reference remains an offline oracle and is not a runtime dependency",
    "independent reviewer approval is missing",
)


class OpenMMReferenceExplicitSolventError(RuntimeError):
    """The frozen successor contract or one observation is invalid."""


@dataclass(frozen=True)
class _PreparedCase:
    case_id: str
    source_system: AllAtomSystem
    source_parameters: ReferenceForceFieldParameters
    config: ReferenceExplicitSolventConfig
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
        raise OpenMMReferenceExplicitSolventError(
            "explicit-solvent successor payload is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _require_sha256(value: object, *, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise OpenMMReferenceExplicitSolventError(
            f"{name} must be a lowercase SHA-256 digest"
        )
    return value


def _finite_hex(value: object, *, name: str) -> float:
    if not isinstance(value, str):
        raise OpenMMReferenceExplicitSolventError(
            f"{name} must be canonical binary64 hex"
        )
    try:
        result = float.fromhex(value)
    except ValueError:
        raise OpenMMReferenceExplicitSolventError(
            f"{name} must be canonical binary64 hex"
        ) from None
    if not math.isfinite(result) or result.hex() != value:
        raise OpenMMReferenceExplicitSolventError(
            f"{name} must be canonical finite binary64 hex"
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
            source_format="frozen-offline-explicit-solvent-protocol"
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
    water_count: int = 2,
) -> ReferenceExplicitSolventConfig:
    return ReferenceExplicitSolventConfig(
        box_lengths_angstrom=(12.0, 12.0, 12.0),
        water_count=water_count,
        sodium_count=sodium_count,
        chloride_count=chloride_count,
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
        config=config,
        preparation=preparation,
    )


def _materialize_cases() -> tuple[_PreparedCase, ...]:
    return (
        _prepare_case(
            case_id="neutral_solute_two_waters",
            charge_e=0.0,
            sodium_count=0,
            chloride_count=0,
        ),
        _prepare_case(
            case_id="neutral_solute_two_waters_na_cl",
            charge_e=0.0,
            sodium_count=1,
            chloride_count=1,
        ),
        _prepare_case(
            case_id="positive_solute_two_waters_cl",
            charge_e=1.0,
            sodium_count=0,
            chloride_count=1,
        ),
    )


def _trajectory_case(
    prepared: _PreparedCase,
    *,
    timestep_ps: float = 1.0e-6,
    steps: int = 4,
    reciprocal_bound: int = 2,
    restart_step: int = 2,
) -> _parent._TrajectoryCase:
    preparation = prepared.preparation
    return _parent._TrajectoryCase(
        case_id=prepared.case_id,
        system=preparation.system,
        parameters=preparation.parameters,
        velocities=torch.zeros(
            (1, preparation.system.atom_count, 3),
            dtype=torch.float64,
        ),
        nve_config=ReferenceNVEConfig(
            timestep_ps=timestep_ps,
            trajectory_stride=1,
            max_neighbors=32,
            max_atoms_per_cell=32,
            ewald_config=ReferenceEwaldConfig(
                alpha_per_angstrom=0.35,
                reciprocal_max_indices=(
                    reciprocal_bound,
                    reciprocal_bound,
                    reciprocal_bound,
                ),
            ),
        ),
        constraint_config=preparation.constraint_config,
        steps=steps,
        restart_step=restart_step,
    )


def _threshold_document() -> dict[str, str]:
    return {
        "same_coordinate_energy_max_abs_kcal_per_mol": (
            _parent.OPENMM_REFERENCE_NVE_ENERGY_ERROR_THRESHOLD_KCAL_PER_MOL.hex()
        ),
        "same_coordinate_force_max_abs_kcal_per_mol_angstrom": (
            _parent.OPENMM_REFERENCE_NVE_FORCE_MAX_ERROR_THRESHOLD_KCAL_PER_MOL_ANGSTROM.hex()
        ),
        "same_coordinate_force_rms_kcal_per_mol_angstrom": (
            _parent.OPENMM_REFERENCE_NVE_FORCE_RMS_ERROR_THRESHOLD_KCAL_PER_MOL_ANGSTROM.hex()
        ),
        "trajectory_coordinate_max_abs_angstrom": (
            _parent.OPENMM_REFERENCE_NVE_COORDINATE_ERROR_THRESHOLD_ANGSTROM.hex()
        ),
        "trajectory_velocity_max_abs_angstrom_per_ps": (
            _parent.OPENMM_REFERENCE_NVE_VELOCITY_ERROR_THRESHOLD_ANGSTROM_PER_PS.hex()
        ),
        "position_constraint_max_abs_angstrom": (
            _parent.OPENMM_REFERENCE_NVE_POSITION_CONSTRAINT_THRESHOLD_ANGSTROM.hex()
        ),
        "velocity_constraint_max_abs_angstrom_per_ps": (
            _parent.OPENMM_REFERENCE_NVE_VELOCITY_CONSTRAINT_THRESHOLD_ANGSTROM_PER_PS.hex()
        ),
        "per_implementation_energy_drift_max_abs_kcal_per_mol": (
            _parent.OPENMM_REFERENCE_NVE_DRIFT_THRESHOLD_KCAL_PER_MOL.hex()
        ),
        "timestep_medium_to_fine_coordinate_max_abs_angstrom": (
            OPENMM_REFERENCE_EXPLICIT_SOLVENT_TIMESTEP_COORDINATE_THRESHOLD_ANGSTROM.hex()
        ),
        "timestep_medium_to_fine_velocity_max_abs_angstrom_per_ps": (
            OPENMM_REFERENCE_EXPLICIT_SOLVENT_TIMESTEP_VELOCITY_THRESHOLD_ANGSTROM_PER_PS.hex()
        ),
        "ewald_bound3_to_bound4_energy_max_abs_kcal_per_mol": (
            OPENMM_REFERENCE_EXPLICIT_SOLVENT_EWALD_ENERGY_THRESHOLD_KCAL_PER_MOL.hex()
        ),
        "ewald_bound3_to_bound4_force_max_abs_kcal_per_mol_angstrom": (
            OPENMM_REFERENCE_EXPLICIT_SOLVENT_EWALD_FORCE_THRESHOLD_KCAL_PER_MOL_ANGSTROM.hex()
        ),
    }


def _configuration_projection() -> dict[str, object]:
    prepared_cases = _materialize_cases()
    cases = [_trajectory_case(row) for row in prepared_cases]
    return {
        "schema_id": OPENMM_REFERENCE_EXPLICIT_SOLVENT_CONFIG_SCHEMA_ID,
        "protocol_id": OPENMM_REFERENCE_EXPLICIT_SOLVENT_PROTOCOL_ID,
        "parent_protocol_id": _parent.OPENMM_REFERENCE_NVE_TRAJECTORY_PROTOCOL_ID,
        "parent_configuration_sha256": (
            _parent.FROZEN_OPENMM_REFERENCE_NVE_TRAJECTORY_CONFIG_SHA256
        ),
        "materializer": {
            "algorithm_id": REFERENCE_EXPLICIT_SOLVENT_ALGORITHM_ID,
            "profile_fingerprint_sha256": (
                REFERENCE_EXPLICIT_SOLVENT_PROFILE_FINGERPRINT_SHA256
            ),
            "profile_source_sha256": (
                REFERENCE_EXPLICIT_SOLVENT_PROFILE_SOURCE_SHA256
            ),
        },
        "openmm_constraint_source_audit": {
            "git_revision": _parent.OPENMM_REFERENCE_REQUIRED_GIT_REVISION,
            "reference_constraints_source_url": (
                OPENMM_REFERENCE_CONSTRAINTS_SOURCE_URL
            ),
            "reference_constraints_source_sha256": (
                OPENMM_REFERENCE_CONSTRAINTS_SOURCE_SHA256
            ),
            "reference_settle_source_url": OPENMM_REFERENCE_SETTLE_SOURCE_URL,
            "reference_settle_source_sha256": (
                OPENMM_REFERENCE_SETTLE_SOURCE_SHA256
            ),
            "selection_contract": (
                "closed three-atom constraint loops are automatically assigned "
                "to SETTLE and their distances are narrowed to float"
            ),
            "public_disable_path_observed": False,
        },
        "case_order": [row.case_id for row in prepared_cases],
        "cases": [
            {
                "case_id": prepared.case_id,
                "source_system_sha256": canonical_system_sha256(
                    prepared.source_system
                ),
                "source_parameter_document": (
                    prepared.source_parameters.to_dict()
                ),
                "preparation_config": prepared.config.to_dict(),
                "preparation_receipt": prepared.preparation.receipt.to_dict(),
                "trajectory_input": _parent._case_input_document(case),
            }
            for prepared, case in zip(prepared_cases, cases)
        ],
        "nominal_trajectory": {
            "timestep_ps_hex": (1.0e-6).hex(),
            "steps": 4,
            "restart_step": 2,
            "reciprocal_max_indices": [2, 2, 2],
            "initial_velocity_policy": "all_zero_binary64",
        },
        "timestep_convergence": {
            "case_id": "neutral_solute_two_waters_na_cl",
            "common_horizon_ps_hex": (8.0e-6).hex(),
            "ladder": [
                {"name": "coarse", "timestep_ps_hex": (4.0e-6).hex(), "steps": 2},
                {"name": "medium", "timestep_ps_hex": (2.0e-6).hex(), "steps": 4},
                {"name": "fine", "timestep_ps_hex": (1.0e-6).hex(), "steps": 8},
            ],
            "monotonic_policy": (
                "medium-to-fine max error must not exceed coarse-to-fine"
            ),
        },
        "ewald_convergence": {
            "case_id": "neutral_solute_two_waters_na_cl",
            "coordinate_policy": "identical_unprojected_materialized_coordinates",
            "reciprocal_bounds": [2, 3, 4],
            "monotonic_policy": (
                "bound3-to-bound4 gap must not exceed bound2-to-bound4"
            ),
        },
        "failure_rows": [
            {
                "case_id": "non_neutral_materialization",
                "expected_code": "neutrality_required",
            },
            {
                "case_id": "boxed_source_materialization",
                "expected_code": "unboxed_source_required",
            },
            {
                "case_id": "missing_mass_materialization",
                "expected_code": "explicit_mass_required",
            },
            {
                "case_id": "oracle_atom_capacity",
                "expected_code": "oracle_atom_capacity_exceeded",
            },
        ],
        "failure_disposition_policy": {
            "threshold_relaxation_allowed": False,
            "physical_input_modification_allowed": False,
            "accepted_as_metric_pass": False,
            "recognized_codes": [
                "openmm_reference_settle_float_distance_precision_limit",
                "exact_cutoff_boundary_inclusion_divergence",
                "engine_constraint_roundoff_nonmonotone_below_absolute_threshold",
            ],
        },
        "thresholds": _threshold_document(),
        "required_evidence": [
            "exact materializer replay",
            "term energy and force max/RMS error",
            "position and velocity constraint residual",
            "iteration counts and complete trajectory traces",
            "engine and OpenMM restart equality",
            "timestep convergence",
            "direct-Ewald reciprocal-bound convergence",
            "all failure rows and failed-metric dispositions",
            "source, binary, environment, and dependency identity",
        ],
        "claim_gates": {
            "single_host_can_validate": False,
            "scientifically_validated": False,
            "production_eligible": False,
            "claim_safe": False,
        },
    }


def openmm_reference_explicit_solvent_configuration_document() -> dict[str, object]:
    """Return the reviewed input-only successor configuration."""

    projection = _configuration_projection()
    digest = _sha256(projection)
    if digest != FROZEN_OPENMM_REFERENCE_EXPLICIT_SOLVENT_CONFIG_SHA256:
        raise OpenMMReferenceExplicitSolventError(
            "OpenMM explicit-solvent configuration digest drifted"
        )
    return {**projection, "configuration_sha256": digest}


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _source_identity_document() -> dict[str, object]:
    root = _repository_root()
    relative_paths = (
        "betelgeuze_engine_v2/offline/openmm_reference_explicit_solvent_trajectory.py",
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
        "parent_runtime_dependency_identity": parent_identity["dependencies"],
        "parent_runtime_dependency_identity_sha256": parent_identity[
            "dependency_identity_sha256"
        ],
        "absolute_paths_disclosed": False,
    }
    return {**projection, "source_identity_sha256": _sha256(projection)}


def _settle_triangle_count(case: _parent._TrajectoryCase) -> int:
    constraints = case.constraint_config.constraints
    adjacency: dict[int, set[int]] = {
        index: set() for index in range(case.system.atom_count)
    }
    distances: dict[tuple[int, int], float] = {}
    for row in constraints:
        pair = tuple(sorted((row.atom_i, row.atom_j)))
        adjacency[pair[0]].add(pair[1])
        adjacency[pair[1]].add(pair[0])
        distances[pair] = row.target_distance_angstrom
    clusters = 0
    for center in range(case.system.atom_count):
        partners = sorted(adjacency[center])
        if len(partners) != 2 or center > min(partners):
            continue
        first, second = partners
        if (
            len(adjacency[first]) == 2
            and len(adjacency[second]) == 2
            and second in adjacency[first]
        ):
            values = (
                distances[tuple(sorted((center, first)))],
                distances[tuple(sorted((center, second)))],
                distances[tuple(sorted((first, second)))],
            )
            narrowed = tuple(
                torch.tensor(value, dtype=torch.float32).item()
                for value in values
            )
            if (
                narrowed[0] == narrowed[1]
                or narrowed[0] == narrowed[2]
                or narrowed[1] == narrowed[2]
            ):
                clusters += 1
    return clusters


def _cutoff_boundary_pairs(
    case: _parent._TrajectoryCase,
) -> list[dict[str, object]]:
    if case.system.cell is None:
        return []
    lengths = tuple(
        float(value)
        for value in case.system.cell.orthorhombic_lengths().tolist()
    )
    coordinates = case.system.coordinates[0].tolist()
    atom_map = case.parameters.atom_parameter_map
    excluded = set(case.parameters.excluded_pairs)
    scaling = case.parameters.pair_scaling_map
    rows: list[dict[str, object]] = []
    for atom_i in range(case.system.atom_count):
        for atom_j in range(atom_i + 1, case.system.atom_count):
            pair = (atom_i, atom_j)
            differences = []
            for axis, length in enumerate(lengths):
                difference = (
                    float(coordinates[atom_i][axis])
                    - float(coordinates[atom_j][axis])
                )
                difference -= round(difference / length) * length
                differences.append(difference)
            distance = math.sqrt(
                math.fsum(value * value for value in differences)
            )
            if distance.hex() != case.parameters.cutoff_angstrom.hex():
                continue
            if pair in excluded:
                electrostatic_scale = 0.0
            elif pair in scaling:
                electrostatic_scale = scaling[pair].electrostatic_scale
            else:
                electrostatic_scale = 1.0
            charge_product = (
                atom_map[atom_i].charge_e
                * atom_map[atom_j].charge_e
                * electrostatic_scale
            )
            if charge_product == 0.0:
                continue
            rows.append(
                {
                    "atom_i": atom_i,
                    "atom_j": atom_j,
                    "distance_angstrom_hex": distance.hex(),
                    "cutoff_angstrom_hex": (
                        case.parameters.cutoff_angstrom.hex()
                    ),
                    "scaled_charge_product_e2_hex": charge_product.hex(),
                }
            )
    return rows


def _case_dispositions(
    *,
    case: _parent._TrajectoryCase,
    parent_row: Mapping[str, object],
) -> tuple[list[dict[str, object]], list[str]]:
    checks = parent_row["metric_checks"]
    if not isinstance(checks, Mapping):
        raise OpenMMReferenceExplicitSolventError(
            "parent trajectory metric checks are invalid"
        )
    failed = sorted(name for name, passed in checks.items() if passed is False)
    covered: set[str] = set()
    dispositions: list[dict[str, object]] = []
    if (
        "position_constraint_metric_pass" in failed
        and _settle_triangle_count(case) > 0
    ):
        covered.add("position_constraint_metric_pass")
        dispositions.append(
            {
                "code": (
                    "openmm_reference_settle_float_distance_precision_limit"
                ),
                "failed_metrics": ["position_constraint_metric_pass"],
                "settle_triangle_count": _settle_triangle_count(case),
                "source_sha256": OPENMM_REFERENCE_CONSTRAINTS_SOURCE_SHA256,
                "threshold_relaxed": False,
                "physical_input_modified": False,
                "accepted_as_metric_pass": False,
            }
        )
    boundary_pairs = _cutoff_boundary_pairs(case)
    boundary_metrics = {
        "same_coordinate_force_max_metric_pass",
        "same_coordinate_force_rms_metric_pass",
        "trajectory_velocity_metric_pass",
    }
    observed_boundary_failures = sorted(boundary_metrics.intersection(failed))
    if boundary_pairs and observed_boundary_failures:
        covered.update(observed_boundary_failures)
        dispositions.append(
            {
                "code": "exact_cutoff_boundary_inclusion_divergence",
                "failed_metrics": observed_boundary_failures,
                "charged_cutoff_boundary_pairs": boundary_pairs,
                "engine_policy": "compact_radius_graph_excludes_cutoff_equality",
                "openmm_policy": "CustomBond step(rc-r) evaluates equality as included",
                "threshold_relaxed": False,
                "physical_input_modified": False,
                "accepted_as_metric_pass": False,
            }
        )
    return dispositions, sorted(set(failed) - covered)


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
        prepared.config,
        prepared.preparation,
    )
    case = _trajectory_case(prepared)
    parent_row = _parent._case_row(
        case,
        openmm=openmm,
        unit=unit,
        reference=reference,
    )
    dispositions, unexpected = _case_dispositions(
        case=case,
        parent_row=parent_row,
    )
    metric_pass = bool(parent_row["metric_pass"])
    disposition_complete = metric_pass or not unexpected
    projection = {
        "schema_id": OPENMM_REFERENCE_EXPLICIT_SOLVENT_CASE_SCHEMA_ID,
        "case_id": prepared.case_id,
        "status": (
            "completed_pass"
            if metric_pass
            else (
                "completed_failed_disposition"
                if disposition_complete
                else "completed_unexpected_failure"
            )
        ),
        "preparation_replay_pass": replay is prepared.preparation,
        "preparation_receipt": prepared.preparation.receipt.to_dict(),
        "parent_trajectory_row": parent_row,
        "failed_metric_dispositions": dispositions,
        "unexpected_failed_metrics": unexpected,
        "metric_pass": metric_pass,
        "failure_disposition_complete": disposition_complete,
        "scientifically_validated": False,
        "claim_safe": False,
    }
    return {**projection, "case_sha256": _sha256(projection)}


def _final_state_for_engine(case: _parent._TrajectoryCase) -> dict[str, object]:
    result = run_reference_nve(
        case.system,
        case.parameters,
        case.velocities,
        steps=case.steps,
        config=case.nve_config,
        constraint_config=case.constraint_config,
    )
    return _parent._engine_state(case, result.frames[-1])


def _timestep_convergence_row(
    prepared: _PreparedCase,
    *,
    openmm: Any,
    unit: Any,
    reference: Any,
) -> dict[str, object]:
    ladder = (
        ("coarse", 4.0e-6, 2),
        ("medium", 2.0e-6, 4),
        ("fine", 1.0e-6, 8),
    )
    final_states: dict[str, dict[str, dict[str, object]]] = {
        "engine_reference": {},
        "openmm_reference": {},
    }
    case_fingerprints: dict[str, dict[str, object]] = {}
    for name, timestep, steps in ladder:
        case = _trajectory_case(
            prepared,
            timestep_ps=timestep,
            steps=steps,
            reciprocal_bound=2,
            restart_step=max(1, steps // 2),
        )
        case_fingerprints[name] = {
            "timestep_ps_hex": timestep.hex(),
            "steps": steps,
            "horizon_ps_hex": (timestep * steps).hex(),
            "nve_config_fingerprint_sha256": (
                case.nve_config.fingerprint_sha256
            ),
        }
        final_states["engine_reference"][name] = _final_state_for_engine(case)
        openmm_system, _ = _parent._build_openmm_system(
            case,
            openmm=openmm,
        )
        final_states["openmm_reference"][name] = _parent._openmm_trace(
            openmm=openmm,
            unit=unit,
            reference=reference,
            openmm_system=openmm_system,
            case=case,
        )[-1]
    implementation_rows = []
    lengths = (12.0, 12.0, 12.0)
    all_metric_checks: list[bool] = []
    all_dispositions_complete = True
    for implementation, states in final_states.items():
        values = {
            name: _parent._state_values(
                state,
                atom_count=prepared.preparation.system.atom_count,
            )
            for name, state in states.items()
        }
        errors: dict[str, dict[str, str]] = {}
        numeric_errors: dict[str, tuple[float, float]] = {}
        for name in ("coarse", "medium"):
            coordinate_error = _parent._coordinate_error(
                values[name][0],
                values["fine"][0],
                lengths,
            )
            velocity_error = _parent._vector_errors(
                values[name][1],
                values["fine"][1],
            )[0]
            numeric_errors[name] = (coordinate_error, velocity_error)
            errors[f"{name}_to_fine"] = {
                "coordinate_max_abs_angstrom_hex": coordinate_error.hex(),
                "velocity_max_abs_angstrom_per_ps_hex": velocity_error.hex(),
            }
        coarse_coordinate, coarse_velocity = numeric_errors["coarse"]
        medium_coordinate, medium_velocity = numeric_errors["medium"]
        checks = {
            "medium_coordinate_absolute_metric_pass": (
                medium_coordinate
                <= OPENMM_REFERENCE_EXPLICIT_SOLVENT_TIMESTEP_COORDINATE_THRESHOLD_ANGSTROM
            ),
            "medium_velocity_absolute_metric_pass": (
                medium_velocity
                <= OPENMM_REFERENCE_EXPLICIT_SOLVENT_TIMESTEP_VELOCITY_THRESHOLD_ANGSTROM_PER_PS
            ),
            "coordinate_monotonic_metric_pass": (
                medium_coordinate <= coarse_coordinate
            ),
            "velocity_monotonic_metric_pass": (
                medium_velocity <= coarse_velocity
            ),
        }
        failed = sorted(name for name, passed in checks.items() if not passed)
        dispositions: list[dict[str, object]] = []
        covered: set[str] = set()
        if (
            failed == ["coordinate_monotonic_metric_pass"]
            and medium_coordinate
            <= OPENMM_REFERENCE_EXPLICIT_SOLVENT_TIMESTEP_COORDINATE_THRESHOLD_ANGSTROM
            and coarse_coordinate
            <= OPENMM_REFERENCE_EXPLICIT_SOLVENT_TIMESTEP_COORDINATE_THRESHOLD_ANGSTROM
        ):
            covered.add("coordinate_monotonic_metric_pass")
            dispositions.append(
                {
                    "code": (
                        "engine_constraint_roundoff_nonmonotone_below_absolute_threshold"
                    ),
                    "failed_metrics": ["coordinate_monotonic_metric_pass"],
                    "threshold_relaxed": False,
                    "accepted_as_metric_pass": False,
                }
            )
        unexpected = sorted(set(failed) - covered)
        disposition_complete = not unexpected
        metric_pass = all(checks.values())
        all_metric_checks.extend(checks.values())
        all_dispositions_complete = (
            all_dispositions_complete and disposition_complete
        )
        implementation_rows.append(
            {
                "implementation": implementation,
                "final_states": states,
                "errors": errors,
                "metric_checks": checks,
                "metric_pass": metric_pass,
                "failed_metric_dispositions": dispositions,
                "unexpected_failed_metrics": unexpected,
                "failure_disposition_complete": disposition_complete,
            }
        )
    projection = {
        "case_id": prepared.case_id,
        "case_fingerprints": case_fingerprints,
        "implementation_rows": implementation_rows,
        "metric_pass": all(all_metric_checks),
        "failure_disposition_complete": all_dispositions_complete,
    }
    return {**projection, "convergence_sha256": _sha256(projection)}


def _ewald_convergence_row(
    prepared: _PreparedCase,
    *,
    openmm: Any,
    unit: Any,
    reference: Any,
) -> dict[str, object]:
    coordinates = prepared.preparation.system.coordinates[0].tolist()
    evaluations: dict[
        str,
        dict[int, tuple[float, tuple[tuple[float, float, float], ...]]],
    ] = {
        "engine_reference": {},
        "openmm_reference": {},
    }
    mappings: dict[str, object] = {}
    for bound in (2, 3, 4):
        case = _trajectory_case(
            prepared,
            reciprocal_bound=bound,
        )
        evaluations["engine_reference"][bound] = _parent._engine_evaluate(
            case,
            coordinates,
        )
        openmm_system, mapping = _parent._build_openmm_system(
            case,
            openmm=openmm,
        )
        mappings[str(bound)] = mapping
        with _parent._OpenMMStaticEvaluator(
            openmm=openmm,
            unit=unit,
            reference=reference,
            openmm_system=openmm_system,
            atom_count=case.system.atom_count,
        ) as evaluator:
            evaluations["openmm_reference"][bound] = evaluator.evaluate(
                coordinates
            )
    implementation_rows = []
    all_checks: list[bool] = []
    for implementation, values in evaluations.items():
        gaps: dict[str, dict[str, str]] = {}
        numeric: dict[int, tuple[float, float]] = {}
        for bound in (2, 3):
            energy_error = abs(values[bound][0] - values[4][0])
            force_error = _parent._vector_errors(
                values[bound][1],
                values[4][1],
            )[0]
            numeric[bound] = energy_error, force_error
            gaps[f"bound{bound}_to_bound4"] = {
                "energy_max_abs_kcal_per_mol_hex": energy_error.hex(),
                "force_max_abs_kcal_per_mol_angstrom_hex": (
                    force_error.hex()
                ),
            }
        checks = {
            "bound3_energy_absolute_metric_pass": (
                numeric[3][0]
                <= OPENMM_REFERENCE_EXPLICIT_SOLVENT_EWALD_ENERGY_THRESHOLD_KCAL_PER_MOL
            ),
            "bound3_force_absolute_metric_pass": (
                numeric[3][1]
                <= OPENMM_REFERENCE_EXPLICIT_SOLVENT_EWALD_FORCE_THRESHOLD_KCAL_PER_MOL_ANGSTROM
            ),
            "energy_monotonic_metric_pass": numeric[3][0] <= numeric[2][0],
            "force_monotonic_metric_pass": numeric[3][1] <= numeric[2][1],
        }
        all_checks.extend(checks.values())
        implementation_rows.append(
            {
                "implementation": implementation,
                "evaluations": {
                    str(bound): {
                        "energy_kcal_per_mol_hex": values[bound][0].hex(),
                        "forces_kcal_per_mol_angstrom_hex": (
                            _parent._hex_rows(values[bound][1])
                        ),
                    }
                    for bound in (2, 3, 4)
                },
                "gaps": gaps,
                "metric_checks": checks,
                "metric_pass": all(checks.values()),
            }
        )
    cross_implementation_rows = []
    for bound in (2, 3, 4):
        engine = evaluations["engine_reference"][bound]
        oracle = evaluations["openmm_reference"][bound]
        force_max, force_rms = _parent._vector_errors(
            engine[1],
            oracle[1],
        )
        cross_implementation_rows.append(
            {
                "reciprocal_bound": bound,
                "energy_max_abs_error_kcal_per_mol_hex": abs(
                    engine[0] - oracle[0]
                ).hex(),
                "force_max_abs_error_kcal_per_mol_angstrom_hex": (
                    force_max.hex()
                ),
                "force_rms_error_kcal_per_mol_angstrom_hex": (
                    force_rms.hex()
                ),
            }
        )
    projection = {
        "case_id": prepared.case_id,
        "coordinate_f64le_sha256": (
            _parent._tensor_f64le_sha256(coordinates)
        ),
        "openmm_mappings": mappings,
        "implementation_rows": implementation_rows,
        "cross_implementation_rows": cross_implementation_rows,
        "metric_pass": all(all_checks),
    }
    return {**projection, "convergence_sha256": _sha256(projection)}


def _materialization_failure(
    *,
    case_id: str,
    expected_code: str,
) -> dict[str, object]:
    if case_id == "non_neutral_materialization":
        source = _source_system(case_id=case_id, charge_e=0.0)
        parameters = _source_parameters(source, charge_e=0.0)
        config = _preparation_config(sodium_count=1, chloride_count=0)
    elif case_id == "boxed_source_materialization":
        source = _source_system(
            case_id=case_id,
            charge_e=0.0,
            cell=UnitCell.orthorhombic(
                (12.0, 12.0, 12.0),
                dtype=torch.float64,
            ),
        )
        parameters = _source_parameters(source, charge_e=0.0)
        config = _preparation_config(sodium_count=0, chloride_count=0)
    elif case_id == "missing_mass_materialization":
        source = _source_system(
            case_id=case_id,
            charge_e=0.0,
            mass_da=None,
        )
        parameters = _source_parameters(source, charge_e=0.0)
        config = _preparation_config(sodium_count=0, chloride_count=0)
    else:
        raise OpenMMReferenceExplicitSolventError(
            "unknown materialization failure case"
        )
    observed_code = "unexpected_success"
    message = ""
    try:
        prepare_reference_explicit_solvent(source, parameters, config)
    except ReferenceExplicitSolventError as exc:
        message = str(exc)
        if "neutral system" in message:
            observed_code = "neutrality_required"
        elif "unboxed source" in message:
            observed_code = "unboxed_source_required"
        elif "missing mass_da" in message:
            observed_code = "explicit_mass_required"
        else:
            observed_code = "unexpected_materialization_error"
    projection = {
        "case_id": case_id,
        "status": "expected_fail_closed",
        "expected_code": expected_code,
        "observed_code": observed_code,
        "error_class": "ReferenceExplicitSolventError",
        "message": message,
        "metric_pass": observed_code == expected_code,
    }
    return {**projection, "failure_sha256": _sha256(projection)}


def _oracle_capacity_failure() -> dict[str, object]:
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
        system_id="oracle-atom-capacity",
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
            (12.0, 12.0, 12.0),
            dtype=torch.float64,
        ),
    )
    parameters = ReferenceForceFieldParameters(
        parameter_set_id="oracle-atom-capacity",
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
            timestep_ps=1.0e-6,
            max_neighbors=32,
            max_atoms_per_cell=32,
            ewald_config=ReferenceEwaldConfig(
                alpha_per_angstrom=0.35,
                reciprocal_max_indices=(2, 2, 2),
            ),
        ),
        constraint_config=ReferenceSHAKERATTLEConfig(),
        steps=1,
        restart_step=0,
    )
    observed_code = "unexpected_success"
    message = ""
    try:
        _parent._require_case_domain(case)
    except _parent.OpenMMReferenceNVETrajectoryError as exc:
        message = str(exc)
        if "bounded coordinate model" in message:
            observed_code = "oracle_atom_capacity_exceeded"
        else:
            observed_code = "unexpected_oracle_error"
    projection = {
        "case_id": "oracle_atom_capacity",
        "status": "expected_fail_closed",
        "expected_code": "oracle_atom_capacity_exceeded",
        "observed_code": observed_code,
        "error_class": "OpenMMReferenceNVETrajectoryError",
        "message": message,
        "atom_count": atom_count,
        "maximum_atom_count": _parent.OPENMM_REFERENCE_NVE_MAX_ATOMS,
        "metric_pass": observed_code == "oracle_atom_capacity_exceeded",
    }
    return {**projection, "failure_sha256": _sha256(projection)}


def _failure_rows() -> list[dict[str, object]]:
    return [
        _materialization_failure(
            case_id="non_neutral_materialization",
            expected_code="neutrality_required",
        ),
        _materialization_failure(
            case_id="boxed_source_materialization",
            expected_code="unboxed_source_required",
        ),
        _materialization_failure(
            case_id="missing_mass_materialization",
            expected_code="explicit_mass_required",
        ),
        _oracle_capacity_failure(),
    ]


def _observation_projection() -> dict[str, object]:
    configuration = openmm_reference_explicit_solvent_configuration_document()
    runtime_identity, openmm, unit, reference = _parent._openmm_modules()
    prepared_cases = _materialize_cases()
    case_rows = [
        _case_row(
            prepared,
            openmm=openmm,
            unit=unit,
            reference=reference,
        )
        for prepared in prepared_cases
    ]
    salted = prepared_cases[1]
    timestep_convergence = _timestep_convergence_row(
        salted,
        openmm=openmm,
        unit=unit,
        reference=reference,
    )
    ewald_convergence = _ewald_convergence_row(
        salted,
        openmm=openmm,
        unit=unit,
        reference=reference,
    )
    failure_rows = _failure_rows()
    all_preregistered_metrics_pass = (
        all(bool(row["metric_pass"]) for row in case_rows)
        and bool(timestep_convergence["metric_pass"])
        and bool(ewald_convergence["metric_pass"])
        and all(bool(row["metric_pass"]) for row in failure_rows)
    )
    all_failure_dispositions_complete = (
        all(
            bool(row["metric_pass"])
            or bool(row["failure_disposition_complete"])
            for row in case_rows
        )
        and (
            bool(timestep_convergence["metric_pass"])
            or bool(timestep_convergence["failure_disposition_complete"])
        )
        and all(bool(row["metric_pass"]) for row in failure_rows)
    )
    return {
        "schema_id": OPENMM_REFERENCE_EXPLICIT_SOLVENT_OBSERVATION_SCHEMA_ID,
        "protocol_id": OPENMM_REFERENCE_EXPLICIT_SOLVENT_PROTOCOL_ID,
        "configuration_sha256": configuration["configuration_sha256"],
        "configuration": configuration,
        "source_identity": _source_identity_document(),
        "runtime_identity": runtime_identity,
        "case_rows": case_rows,
        "timestep_convergence": timestep_convergence,
        "ewald_convergence": ewald_convergence,
        "failure_rows": failure_rows,
        "summary": {
            "physical_case_count": len(case_rows),
            "physical_case_metric_pass_count": sum(
                bool(row["metric_pass"]) for row in case_rows
            ),
            "physical_case_disposition_count": sum(
                bool(row["failure_disposition_complete"])
                and not bool(row["metric_pass"])
                for row in case_rows
            ),
            "timestep_convergence_metric_pass": bool(
                timestep_convergence["metric_pass"]
            ),
            "ewald_convergence_metric_pass": bool(
                ewald_convergence["metric_pass"]
            ),
            "failure_case_count": len(failure_rows),
            "failure_case_metric_pass_count": sum(
                bool(row["metric_pass"]) for row in failure_rows
            ),
            "all_preregistered_metrics_pass": all_preregistered_metrics_pass,
            "all_failure_dispositions_complete": (
                all_failure_dispositions_complete
            ),
            "host_count": 1,
            "independent_reviewer_approved": False,
            "production_eligible": False,
        },
        "scientific_blockers": list(
            OPENMM_REFERENCE_EXPLICIT_SOLVENT_SCIENTIFIC_BLOCKERS
        ),
        "scientifically_validated": False,
        "claim_safe": False,
    }


def build_openmm_reference_explicit_solvent_observation() -> dict[str, object]:
    """Execute the frozen successor and return one deterministic receipt."""

    projection = _observation_projection()
    return {**projection, "observation_sha256": _sha256(projection)}


def require_openmm_reference_explicit_solvent_observation(
    value: Mapping[str, object],
) -> dict[str, object]:
    """Reproduce source, runtime, traces, failures, and all dispositions."""

    if not isinstance(value, Mapping):
        raise OpenMMReferenceExplicitSolventError(
            "OpenMM explicit-solvent observation must be a mapping"
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
        "timestep_convergence",
        "ewald_convergence",
        "failure_rows",
        "summary",
        "scientific_blockers",
        "scientifically_validated",
        "claim_safe",
        "observation_sha256",
    }
    if set(observed) != expected_keys:
        raise OpenMMReferenceExplicitSolventError(
            "OpenMM explicit-solvent observation fields are invalid"
        )
    digest = _require_sha256(
        observed.get("observation_sha256"),
        name="OpenMM explicit-solvent observation",
    )
    projection = {
        key: item
        for key, item in observed.items()
        if key != "observation_sha256"
    }
    if digest != _sha256(projection):
        raise OpenMMReferenceExplicitSolventError(
            "OpenMM explicit-solvent observation digest mismatch"
        )
    if (
        observed.get("schema_id")
        != OPENMM_REFERENCE_EXPLICIT_SOLVENT_OBSERVATION_SCHEMA_ID
        or observed.get("protocol_id")
        != OPENMM_REFERENCE_EXPLICIT_SOLVENT_PROTOCOL_ID
        or observed.get("scientifically_validated") is not False
        or observed.get("claim_safe") is not False
    ):
        raise OpenMMReferenceExplicitSolventError(
            "OpenMM explicit-solvent observation overstates its evidence claim"
        )
    current = _observation_projection()
    if projection != current:
        raise OpenMMReferenceExplicitSolventError(
            "OpenMM explicit-solvent observation does not reproduce current "
            "source, runtime, traces, failures, or numeric metrics"
        )
    return observed


def write_openmm_reference_explicit_solvent_observation(
    path: Path | str,
    observation: Mapping[str, object],
) -> Path:
    """Write one verified private receipt without replacing other evidence."""

    verified = require_openmm_reference_explicit_solvent_observation(
        observation
    )
    payload = json.dumps(
        verified,
        allow_nan=False,
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
    ) + "\n"
    encoded_size = len(payload.encode("utf-8"))
    if encoded_size > OPENMM_REFERENCE_EXPLICIT_SOLVENT_MAX_OBSERVATION_BYTES:
        raise OpenMMReferenceExplicitSolventError(
            "OpenMM explicit-solvent observation exceeds its bounded size"
        )
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_symlink():
        raise OpenMMReferenceExplicitSolventError(
            "OpenMM explicit-solvent observation path must not be a symlink"
        )
    if destination.exists():
        metadata = destination.lstat()
        if not stat.S_ISREG(metadata.st_mode):
            raise OpenMMReferenceExplicitSolventError(
                "OpenMM explicit-solvent observation path must be a regular file"
            )
        if metadata.st_size > OPENMM_REFERENCE_EXPLICIT_SOLVENT_MAX_OBSERVATION_BYTES:
            raise OpenMMReferenceExplicitSolventError(
                "existing OpenMM explicit-solvent observation exceeds its bound"
            )
        if destination.read_text(encoding="utf-8") != payload:
            raise OpenMMReferenceExplicitSolventError(
                "refusing to overwrite a different OpenMM explicit-solvent observation"
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
            raise OpenMMReferenceExplicitSolventError(
                "OpenMM explicit-solvent path appeared during creation"
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


def read_openmm_reference_explicit_solvent_observation(
    path: Path | str,
) -> dict[str, object]:
    """Read one private bounded receipt and reproduce it completely."""

    source = Path(path)
    metadata = source.lstat()
    if not stat.S_ISREG(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
        raise OpenMMReferenceExplicitSolventError(
            "OpenMM explicit-solvent observation must be a regular non-symlink file"
        )
    if metadata.st_mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise OpenMMReferenceExplicitSolventError(
            "OpenMM explicit-solvent observation must not be group/world accessible"
        )
    if metadata.st_size > OPENMM_REFERENCE_EXPLICIT_SOLVENT_MAX_OBSERVATION_BYTES:
        raise OpenMMReferenceExplicitSolventError(
            "OpenMM explicit-solvent observation exceeds its bounded size"
        )
    try:
        with source.open("rb") as handle:
            raw = handle.read(
                OPENMM_REFERENCE_EXPLICIT_SOLVENT_MAX_OBSERVATION_BYTES + 1
            )
        if (
            len(raw)
            > OPENMM_REFERENCE_EXPLICIT_SOLVENT_MAX_OBSERVATION_BYTES
        ):
            raise OpenMMReferenceExplicitSolventError(
                "OpenMM explicit-solvent observation exceeds its bounded size"
            )
        value = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise OpenMMReferenceExplicitSolventError(
            "OpenMM explicit-solvent observation is not readable JSON"
        ) from exc
    return require_openmm_reference_explicit_solvent_observation(value)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build or verify the claim-closed OpenMM Reference explicit-solvent "
            "trajectory and convergence observation"
        )
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--output", type=Path)
    action.add_argument("--verify", type=Path)
    arguments = parser.parse_args(argv)
    if arguments.output is not None:
        observation = build_openmm_reference_explicit_solvent_observation()
        destination = write_openmm_reference_explicit_solvent_observation(
            arguments.output,
            observation,
        )
        print(
            json.dumps(
                {
                    "observation_sha256": observation["observation_sha256"],
                    "path": str(destination),
                    "status": (
                        "openmm_reference_explicit_solvent_observation_written"
                    ),
                },
                allow_nan=False,
                ensure_ascii=True,
                sort_keys=True,
            )
        )
        return 0
    verified = read_openmm_reference_explicit_solvent_observation(
        arguments.verify
    )
    print(
        json.dumps(
            {
                "observation_sha256": verified["observation_sha256"],
                "path": str(arguments.verify),
                "status": (
                    "openmm_reference_explicit_solvent_observation_verified"
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
    "FROZEN_OPENMM_REFERENCE_EXPLICIT_SOLVENT_CONFIG_SHA256",
    "OPENMM_REFERENCE_EXPLICIT_SOLVENT_CONFIG_SCHEMA_ID",
    "OPENMM_REFERENCE_EXPLICIT_SOLVENT_MAX_OBSERVATION_BYTES",
    "OPENMM_REFERENCE_EXPLICIT_SOLVENT_OBSERVATION_SCHEMA_ID",
    "OPENMM_REFERENCE_EXPLICIT_SOLVENT_PROTOCOL_ID",
    "OPENMM_REFERENCE_EXPLICIT_SOLVENT_SCIENTIFIC_BLOCKERS",
    "OpenMMReferenceExplicitSolventError",
    "build_openmm_reference_explicit_solvent_observation",
    "main",
    "openmm_reference_explicit_solvent_configuration_document",
    "read_openmm_reference_explicit_solvent_observation",
    "require_openmm_reference_explicit_solvent_observation",
    "write_openmm_reference_explicit_solvent_observation",
]
