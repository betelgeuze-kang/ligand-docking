"""Same-coordinate OpenMM comparison for the claim-closed stationarity candidate."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import stat
import sys
from typing import Any, Mapping, Sequence

import torch

from betelgeuze_engine_v2.geometry import RadiusGraphConfig, build_compact_radius_graph
from betelgeuze_engine_v2.molecular import (
    canonical_system_sha256,
    canonical_topology_sha256,
)
from betelgeuze_engine_v2.physics.reference_constraint_stationarity import (
    REFERENCE_CONSTRAINT_STATIONARITY_DEFAULT_CONFIG_SHA256,
    REFERENCE_CONSTRAINT_STATIONARITY_SCIENTIFIC_BLOCKERS,
    ReferenceConstraintStationarityConfig,
    minimize_reference_constraint_stationarity,
    reference_constraint_stationarity_default_configuration_document,
)
from betelgeuze_engine_v2.physics.reference_forcefield_v2 import (
    evaluate_reference_force_field_v2,
)
from betelgeuze_engine_v2.physics.reference_minimization_validation_materializer import (
    materialize_frozen_cpu_minimization_validation_case,
)
from betelgeuze_engine_v2.physics.reference_solvation import (
    evaluate_reference_force_field_v2_with_fixed_born,
)
from .openmm_reference_oracle import (
    FROZEN_OPENMM_REFERENCE_MAPPING_CONTRACT_SHA256,
    OPENMM_REFERENCE_REQUIRED_DISTRIBUTION_VERSION,
    OPENMM_REFERENCE_REQUIRED_FULL_VERSION,
    OPENMM_REFERENCE_REQUIRED_GIT_REVISION,
    OPENMM_REFERENCE_REQUIRED_PLATFORM,
    coordinate_f64le_sha256,
    evaluate_openmm_reference,
    observe_openmm_reference_runtime_identity,
    require_openmm_reference_runtime_identity_document,
)


OPENMM_REFERENCE_CONSTRAINT_STATIONARITY_CONFIG_SCHEMA_ID = (
    "betelgeuze.engine_v2_openmm_constraint_stationarity_candidate_config/1.3.0"
)
OPENMM_REFERENCE_CONSTRAINT_STATIONARITY_RECEIPT_SCHEMA_ID = (
    "betelgeuze.engine_v2_openmm_constraint_stationarity_candidate_receipt/1.3.0"
)
FROZEN_LEGACY_OPENMM_REFERENCE_CONSTRAINT_STATIONARITY_CONFIG_SHA256_V1 = (
    "722d319c865eb15dd12296dee998b26332e2c1ad8edf3e5e6611914b960529d1"
)
FROZEN_LEGACY_OPENMM_REFERENCE_CONSTRAINT_STATIONARITY_CONFIG_SHA256_V1_1 = (
    "fca4701f842209076e939a3ae044ec317edf4705f0f979b62620e64fbb42405f"
)
FROZEN_LEGACY_OPENMM_REFERENCE_CONSTRAINT_STATIONARITY_CONFIG_SHA256_V1_2 = (
    "927e11cfccbb8110f8bacceffe5bd0e17ae54cb9bb2f9f4f001377faec0995e1"
)
FROZEN_OPENMM_REFERENCE_CONSTRAINT_STATIONARITY_CONFIG_SHA256 = (
    "69f5168dbf7bcaa9f4ff85f9e2e9f7800b8b21685110000a90c909d552eab6db"
)
OPENMM_REFERENCE_CONSTRAINT_STATIONARITY_ENERGY_THRESHOLD_KCAL_PER_MOL = 1.0e-10
OPENMM_REFERENCE_CONSTRAINT_STATIONARITY_FORCE_THRESHOLD_KCAL_PER_MOL_ANGSTROM = (
    1.0e-8
)
OPENMM_REFERENCE_CONSTRAINT_STATIONARITY_COMPONENT_THRESHOLD_KCAL_PER_MOL = (
    1.0e-10
)
OPENMM_REFERENCE_CONSTRAINT_STATIONARITY_TANGENT_THRESHOLD_KCAL_PER_MOL_ANGSTROM = (
    1.0e-8
)
OPENMM_REFERENCE_CONSTRAINT_STATIONARITY_CONSTRAINT_THRESHOLD_ANGSTROM = 1.0e-10

_ELIGIBLE_CASES = (
    (
        "v2_constrained_angle_energy_decrease",
        "v2_constrained_checkpoint_restart_exact",
    ),
    (
        "v2_fixed_born_constrained_energy_decrease",
        "v2_fixed_born_checkpoint_restart_exact",
    ),
)
_EXCLUDED_V1_CASES = (
    "v1_bonded_energy_decrease",
    "v1_mixed_term_energy_decrease",
    "v1_checkpoint_restart_exact",
    "v1_initially_converged_noop",
)
_PRESERVED_FAIL_CLOSED_CASES = (
    "checkpoint_topology_crosswire",
    "checkpoint_parameter_crosswire",
    "checkpoint_solvation_crosswire",
    "fixed_born_periodic_cell_rejected",
    "line_search_budget_exhausted",
    "constraint_projection_budget_exhausted",
)
_SOURCE_PATHS = (
    "betelgeuze_engine_v2/physics/reference_constraint_stationarity.py",
    "betelgeuze_engine_v2/offline/openmm_reference_constraint_stationarity.py",
    "betelgeuze_engine_v2/offline/openmm_reference_oracle.py",
    "betelgeuze_engine_v2/physics/reference_forcefield_v2.py",
    "betelgeuze_engine_v2/physics/reference_solvation.py",
    "betelgeuze_engine_v2/physics/reference_minimization_validation_protocol.py",
    "betelgeuze_engine_v2/physics/reference_minimization_validation_materializer.py",
)


class OpenMMReferenceConstraintStationarityError(RuntimeError):
    """The candidate comparison or its identity contract is invalid."""


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise OpenMMReferenceConstraintStationarityError(
            "candidate comparison payload is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _require_sha256(value: object, *, name: str) -> str:
    if not isinstance(value, str):
        raise OpenMMReferenceConstraintStationarityError(
            f"{name} must be a lowercase SHA-256 digest"
        )
    digest = value.strip().lower()
    if len(digest) != 64 or any(
        character not in "0123456789abcdef" for character in digest
    ):
        raise OpenMMReferenceConstraintStationarityError(
            f"{name} must be a lowercase SHA-256 digest"
        )
    return digest


def _finite(value: object, *, name: str, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise OpenMMReferenceConstraintStationarityError(
            f"{name} must be a finite real number"
        )
    result = float(value)
    if not math.isfinite(result):
        raise OpenMMReferenceConstraintStationarityError(f"{name} must be finite")
    if minimum is not None and result < minimum:
        raise OpenMMReferenceConstraintStationarityError(
            f"{name} must be >= {minimum}"
        )
    return result


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _hash_regular_file(path: Path, *, maximum_bytes: int = 512 * 1024**2) -> str:
    try:
        before = path.lstat()
    except OSError as exc:
        raise OpenMMReferenceConstraintStationarityError(
            f"cannot inspect identity file {path}"
        ) from exc
    if not stat.S_ISREG(before.st_mode) or stat.S_ISLNK(before.st_mode):
        raise OpenMMReferenceConstraintStationarityError(
            f"identity file must be a regular non-symlink: {path}"
        )
    if before.st_size > maximum_bytes:
        raise OpenMMReferenceConstraintStationarityError(
            f"identity file exceeds bounded size: {path}"
        )
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    after = path.lstat()
    if (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
    ) != (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    ):
        raise OpenMMReferenceConstraintStationarityError(
            f"identity file changed while hashing: {path}"
        )
    return digest.hexdigest()


def _source_identity_document() -> dict[str, object]:
    root = _repository_root()
    rows = []
    for relative in _SOURCE_PATHS:
        path = root / relative
        rows.append(
            {
                "path": relative,
                "sha256": _hash_regular_file(path),
                "size_bytes": path.stat().st_size,
            }
        )
    projection = {
        "schema_id": (
            "betelgeuze.engine_v2_constraint_stationarity_source_identity/1.0.0"
        ),
        "files": rows,
    }
    return {**projection, "source_identity_sha256": _sha256(projection)}


def _environment_identity_document() -> dict[str, object]:
    executable = Path(sys.executable).resolve()
    projection = {
        "schema_id": (
            "betelgeuze.engine_v2_constraint_stationarity_environment_identity/"
            "1.0.0"
        ),
        "python": {
            "implementation": platform.python_implementation(),
            "version": platform.python_version(),
            "executable_sha256": _hash_regular_file(executable),
        },
        "torch": {
            "version": torch.__version__,
            "git_version": torch.version.git_version,
            "cuda_version": torch.version.cuda,
            "default_dtype": str(torch.get_default_dtype()),
        },
        "host": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "logical_cpu_count": os.cpu_count(),
            "byteorder": sys.byteorder,
        },
        "execution": {
            "device": "cpu",
            "coordinate_dtype": "float64",
            "torch_deterministic_algorithms_enabled": (
                torch.are_deterministic_algorithms_enabled()
            ),
            "openmm_platform": OPENMM_REFERENCE_REQUIRED_PLATFORM,
        },
    }
    return {**projection, "environment_identity_sha256": _sha256(projection)}


def _configuration_projection() -> dict[str, object]:
    case_dispositions = [
        *(
            {
                "case_id": case_id,
                "disposition": "not_applicable_unconstrained_v1",
                "denominator": "excluded_10_case",
            }
            for case_id in _EXCLUDED_V1_CASES
        ),
        *(
            {
                "case_id": case_id,
                "disposition": "candidate_same_coordinate_execution",
                "denominator": "candidate_applicable_4_case",
            }
            for pair in _ELIGIBLE_CASES
            for case_id in pair
        ),
        *(
            {
                "case_id": case_id,
                "disposition": "preserved_frozen_fail_closed_not_reexecuted",
                "denominator": "excluded_10_case",
            }
            for case_id in _PRESERVED_FAIL_CLOSED_CASES
        ),
    ]
    return {
        "schema_id": OPENMM_REFERENCE_CONSTRAINT_STATIONARITY_CONFIG_SCHEMA_ID,
        "superseded_configuration_sha256": (
            FROZEN_LEGACY_OPENMM_REFERENCE_CONSTRAINT_STATIONARITY_CONFIG_SHA256_V1_2
        ),
        "legacy_configuration_chain_sha256s": [
            FROZEN_LEGACY_OPENMM_REFERENCE_CONSTRAINT_STATIONARITY_CONFIG_SHA256_V1_1,
            FROZEN_LEGACY_OPENMM_REFERENCE_CONSTRAINT_STATIONARITY_CONFIG_SHA256_V1
        ],
        "refreeze_reason": (
            "bind_openmm_mapping_contract_1_3_0_without_threshold_change"
        ),
        "candidate_configuration_sha256": (
            REFERENCE_CONSTRAINT_STATIONARITY_DEFAULT_CONFIG_SHA256
        ),
        "openmm_mapping_contract_sha256": (
            FROZEN_OPENMM_REFERENCE_MAPPING_CONTRACT_SHA256
        ),
        "openmm_required_identity": {
            "distribution_version": (
                OPENMM_REFERENCE_REQUIRED_DISTRIBUTION_VERSION
            ),
            "full_version": OPENMM_REFERENCE_REQUIRED_FULL_VERSION,
            "git_revision": OPENMM_REFERENCE_REQUIRED_GIT_REVISION,
            "platform": OPENMM_REFERENCE_REQUIRED_PLATFORM,
        },
        "comparison_method": {
            "coordinate_policy": "bitwise_same_f64le_coordinates",
            "external_evaluator": "OpenMM Reference static energy and force",
            "tangent_projection": (
                "independent_constraint_jacobian_gram_linear_solve"
            ),
            "native_openmm_minimizer_invoked": False,
            "native_openmm_lbfgs_status": "unchanged_rejected_6_of_8",
        },
        "thresholds": {
            "term_energy_abs_error_kcal_per_mol": (
                OPENMM_REFERENCE_CONSTRAINT_STATIONARITY_ENERGY_THRESHOLD_KCAL_PER_MOL
            ),
            "component_energy_abs_error_kcal_per_mol": (
                OPENMM_REFERENCE_CONSTRAINT_STATIONARITY_COMPONENT_THRESHOLD_KCAL_PER_MOL
            ),
            "force_max_abs_error_kcal_per_mol_angstrom": (
                OPENMM_REFERENCE_CONSTRAINT_STATIONARITY_FORCE_THRESHOLD_KCAL_PER_MOL_ANGSTROM
            ),
            "force_rms_error_kcal_per_mol_angstrom": (
                OPENMM_REFERENCE_CONSTRAINT_STATIONARITY_FORCE_THRESHOLD_KCAL_PER_MOL_ANGSTROM
            ),
            "absolute_tangent_force_max_kcal_per_mol_angstrom": (
                OPENMM_REFERENCE_CONSTRAINT_STATIONARITY_TANGENT_THRESHOLD_KCAL_PER_MOL_ANGSTROM
            ),
            "constraint_max_abs_residual_angstrom": (
                OPENMM_REFERENCE_CONSTRAINT_STATIONARITY_CONSTRAINT_THRESHOLD_ANGSTROM
            ),
            "checkpoint_restart_document_equality": True,
        },
        "case_dispositions": case_dispositions,
        "candidate_case_denominator": 4,
        "excluded_frozen_case_count": 10,
        "frozen_14_case_production_receipt_superseded": False,
        "frozen_native_openmm_receipt_superseded": False,
        "validation_receipt": False,
        "scientifically_validated": False,
        "claim_safe": False,
    }


def openmm_reference_constraint_stationarity_configuration_document() -> (
    dict[str, object]
):
    """Return the preregistered, result-free same-coordinate comparison contract."""

    candidate = reference_constraint_stationarity_default_configuration_document()
    if (
        candidate["configuration_sha256"]
        != REFERENCE_CONSTRAINT_STATIONARITY_DEFAULT_CONFIG_SHA256
    ):
        raise OpenMMReferenceConstraintStationarityError(
            "candidate configuration identity drifted"
        )
    projection = _configuration_projection()
    digest = _sha256(projection)
    if digest != FROZEN_OPENMM_REFERENCE_CONSTRAINT_STATIONARITY_CONFIG_SHA256:
        raise OpenMMReferenceConstraintStationarityError(
            "OpenMM stationarity comparison configuration drifted"
        )
    return {**projection, "configuration_sha256": digest}


def _coordinate_rows(coordinates: torch.Tensor) -> tuple[tuple[float, float, float], ...]:
    return tuple(
        tuple(float(value) for value in row)  # type: ignore[misc]
        for row in coordinates[0].tolist()
    )


def _constraint_residual(
    coordinates: torch.Tensor,
    case: Any,
) -> float:
    residuals = []
    for constraint in case.v2_parameters.constraints:
        vector = (
            coordinates[0, constraint.atom_i]
            - coordinates[0, constraint.atom_j]
        )
        if case.system.cell is not None:
            lengths = case.system.cell.orthorhombic_lengths().to(
                dtype=torch.float64,
                device="cpu",
            )
            periodic = torch.tensor(case.system.cell.periodic, dtype=torch.bool)
            safe = torch.where(periodic, lengths, torch.ones_like(lengths))
            vector = torch.where(
                periodic,
                vector - torch.round(vector / safe) * safe,
                vector,
            )
        residuals.append(
            abs(
                float(torch.linalg.vector_norm(vector).item())
                - constraint.target_distance_angstrom
            )
        )
    return max(residuals, default=0.0)


def _independent_tangent_projection(
    coordinates: torch.Tensor,
    forces: torch.Tensor,
    case: Any,
) -> tuple[float, float]:
    atom_count = case.system.atom_count
    jacobian_rows = []
    for constraint in case.v2_parameters.constraints:
        vector = (
            coordinates[0, constraint.atom_i]
            - coordinates[0, constraint.atom_j]
        )
        direction = vector / torch.linalg.vector_norm(vector)
        row = torch.zeros((atom_count, 3), dtype=torch.float64, device="cpu")
        row[constraint.atom_i] = direction
        row[constraint.atom_j] = -direction
        jacobian_rows.append(row.reshape(-1))
    jacobian = torch.stack(jacobian_rows)
    flat_force = forces.reshape(-1)
    gram = jacobian @ jacobian.T
    try:
        multipliers = torch.linalg.solve(gram, jacobian @ flat_force)
    except RuntimeError as exc:
        raise OpenMMReferenceConstraintStationarityError(
            "independent tangent projection constraint matrix is singular"
        ) from exc
    projected = (flat_force - jacobian.T @ multipliers).reshape(
        1,
        atom_count,
        3,
    )
    residual = float((jacobian @ projected.reshape(-1)).abs().max().item())
    maximum = float(torch.linalg.vector_norm(projected[0], dim=-1).max().item())
    return maximum, residual


def _engine_evaluation(case: Any, coordinates: torch.Tensor) -> tuple[
    float,
    torch.Tensor,
    dict[str, float],
]:
    state = case.system.with_coordinates(
        coordinates,
        operation="openmm_constraint_stationarity_same_coordinate_engine",
    )
    neighbors = build_compact_radius_graph(
        state.coordinates,
        RadiusGraphConfig(
            cutoff_angstrom=case.v2_parameters.base_parameters.cutoff_angstrom,
            max_neighbors=16,
            max_atoms_per_cell=16,
        ),
        cell=state.cell,
    )
    if case.solvation_parameters is None:
        evaluated = evaluate_reference_force_field_v2(
            state,
            neighbors,
            case.v2_parameters,
        )
    else:
        evaluated = evaluate_reference_force_field_v2_with_fixed_born(
            state,
            neighbors,
            case.v2_parameters,
            case.solvation_parameters,
        )
    components = {
        name: float(value[0].item())
        for name, value in evaluated.component_energies.items()
    }
    return (
        float(evaluated.term.energy[0].item()),
        evaluated.term.forces.detach().clone(),
        components,
    )


def _trace_sha256(result: Any, *, field: str) -> str:
    if field == "energy":
        payload = [row.energy_kcal_per_mol for row in result.observations]
    elif field == "coordinate":
        payload = [
            {
                "attempt_index": row.attempt_index,
                "coordinates_angstrom_hex": [
                    list(coordinate)
                    for coordinate in row.coordinates_angstrom_hex
                ],
                "coordinates_sha256": row.coordinates_sha256,
            }
            for row in result.observations
        ]
    else:
        raise AssertionError(field)
    return _sha256(payload)


def _compare_physical_case(
    energy_case_id: str,
    checkpoint_case_id: str,
    config: ReferenceConstraintStationarityConfig,
) -> tuple[dict[str, object], dict[str, Any]]:
    energy_case = materialize_frozen_cpu_minimization_validation_case(
        energy_case_id
    )
    checkpoint_case = materialize_frozen_cpu_minimization_validation_case(
        checkpoint_case_id
    )
    if (
        canonical_system_sha256(energy_case.system)
        != canonical_system_sha256(checkpoint_case.system)
        or energy_case.v2_parameters.fingerprint_sha256
        != checkpoint_case.v2_parameters.fingerprint_sha256
        or (
            None
            if energy_case.solvation_parameters is None
            else energy_case.solvation_parameters.fingerprint_sha256
        )
        != (
            None
            if checkpoint_case.solvation_parameters is None
            else checkpoint_case.solvation_parameters.fingerprint_sha256
        )
    ):
        raise OpenMMReferenceConstraintStationarityError(
            "energy and checkpoint aliases do not resolve to one physical input"
        )
    uninterrupted = minimize_reference_constraint_stationarity(
        energy_case.system,
        energy_case.v2_parameters,
        config,
        solvation_parameters=energy_case.solvation_parameters,
    )
    paused = minimize_reference_constraint_stationarity(
        checkpoint_case.system,
        checkpoint_case.v2_parameters,
        config,
        solvation_parameters=checkpoint_case.solvation_parameters,
        pause_after_accepted_iterations=3,
    )
    resumed = minimize_reference_constraint_stationarity(
        checkpoint_case.system,
        checkpoint_case.v2_parameters,
        config,
        solvation_parameters=checkpoint_case.solvation_parameters,
        checkpoint=paused.checkpoint,
    )
    checkpoint_equal = uninterrupted.to_dict() == resumed.to_dict()
    coordinates = uninterrupted.system.coordinates
    coordinate_rows = _coordinate_rows(coordinates)
    coordinate_sha256 = coordinate_f64le_sha256(coordinate_rows)
    engine_energy, engine_forces, engine_components = _engine_evaluation(
        energy_case,
        coordinates,
    )
    openmm = evaluate_openmm_reference(
        energy_case.system,
        energy_case.base_parameters,
        v2_parameters=energy_case.v2_parameters,
        solvation_parameters=energy_case.solvation_parameters,
        coordinates_angstrom=coordinate_rows,
    )
    openmm_forces = torch.tensor(
        openmm.forces_kcal_per_mol_angstrom,
        dtype=torch.float64,
        device="cpu",
    ).unsqueeze(0)
    force_error = engine_forces - openmm_forces
    force_max_error = float(force_error.abs().max().item())
    force_rms_error = float(torch.sqrt(torch.mean(force_error.square())).item())
    engine_tangent, engine_tangent_residual = _independent_tangent_projection(
        coordinates,
        engine_forces,
        energy_case,
    )
    openmm_tangent, openmm_tangent_residual = _independent_tangent_projection(
        coordinates,
        openmm_forces,
        energy_case,
    )
    constraint_residual = _constraint_residual(coordinates, energy_case)
    openmm_components = dict(openmm.component_energies_kcal_per_mol)
    component_names = tuple(sorted(set(engine_components) | set(openmm_components)))
    component_rows = []
    for name in component_names:
        engine_value = engine_components.get(name, 0.0)
        openmm_value = openmm_components.get(name, 0.0)
        error = abs(engine_value - openmm_value)
        component_rows.append(
            {
                "name": name,
                "engine_kcal_per_mol": engine_value,
                "openmm_kcal_per_mol": openmm_value,
                "absolute_error_kcal_per_mol": error,
                "threshold_kcal_per_mol": (
                    OPENMM_REFERENCE_CONSTRAINT_STATIONARITY_COMPONENT_THRESHOLD_KCAL_PER_MOL
                ),
                "passed": error
                <= OPENMM_REFERENCE_CONSTRAINT_STATIONARITY_COMPONENT_THRESHOLD_KCAL_PER_MOL,
            }
        )
    energy_error = abs(engine_energy - openmm.total_energy_kcal_per_mol)
    metric_passes = {
        "same_coordinate_identity": (
            coordinate_sha256
            == uninterrupted.to_dict()["final_coordinates_sha256"]
            == openmm.coordinate_f64le_sha256
        ),
        "term_energy_error": energy_error
        <= OPENMM_REFERENCE_CONSTRAINT_STATIONARITY_ENERGY_THRESHOLD_KCAL_PER_MOL,
        "component_energy_errors": all(row["passed"] for row in component_rows),
        "force_max_error": force_max_error
        <= OPENMM_REFERENCE_CONSTRAINT_STATIONARITY_FORCE_THRESHOLD_KCAL_PER_MOL_ANGSTROM,
        "force_rms_error": force_rms_error
        <= OPENMM_REFERENCE_CONSTRAINT_STATIONARITY_FORCE_THRESHOLD_KCAL_PER_MOL_ANGSTROM,
        "engine_absolute_tangent_force": engine_tangent
        <= OPENMM_REFERENCE_CONSTRAINT_STATIONARITY_TANGENT_THRESHOLD_KCAL_PER_MOL_ANGSTROM,
        "openmm_absolute_tangent_force": openmm_tangent
        <= OPENMM_REFERENCE_CONSTRAINT_STATIONARITY_TANGENT_THRESHOLD_KCAL_PER_MOL_ANGSTROM,
        "constraint_residual": constraint_residual
        <= OPENMM_REFERENCE_CONSTRAINT_STATIONARITY_CONSTRAINT_THRESHOLD_ANGSTROM,
        "checkpoint_restart_document_equality": checkpoint_equal,
    }
    physical = {
        "physical_input_id": energy_case.fixture_id,
        "energy_case_id": energy_case_id,
        "checkpoint_case_id": checkpoint_case_id,
        "source_system_sha256": canonical_system_sha256(energy_case.system),
        "topology_sha256": canonical_topology_sha256(energy_case.system),
        "parameter_fingerprint_sha256": (
            energy_case.v2_parameters.fingerprint_sha256
        ),
        "solvation_parameter_fingerprint_sha256": (
            None
            if energy_case.solvation_parameters is None
            else energy_case.solvation_parameters.fingerprint_sha256
        ),
        "candidate_result_sha256": uninterrupted.result_sha256,
        "candidate_checkpoint_sha256": (
            uninterrupted.checkpoint.checkpoint_sha256
        ),
        "checkpoint_restart_document_equality": checkpoint_equal,
        "coordinate_f64le_sha256": coordinate_sha256,
        "term_energy": {
            "engine_kcal_per_mol": engine_energy,
            "openmm_kcal_per_mol": openmm.total_energy_kcal_per_mol,
            "absolute_error_kcal_per_mol": energy_error,
        },
        "force_error": {
            "max_abs_kcal_per_mol_angstrom": force_max_error,
            "rms_kcal_per_mol_angstrom": force_rms_error,
        },
        "constraint_max_abs_residual_angstrom": constraint_residual,
        "tangent_force": {
            "engine_max_kcal_per_mol_angstrom": engine_tangent,
            "openmm_max_kcal_per_mol_angstrom": openmm_tangent,
            "engine_projection_residual_kcal_per_mol_angstrom": (
                engine_tangent_residual
            ),
            "openmm_projection_residual_kcal_per_mol_angstrom": (
                openmm_tangent_residual
            ),
        },
        "component_energies": component_rows,
        "fixed_born_self_pair_components_recorded_separately": (
            (
                "fixed_born_self_polar" in component_names
                and "fixed_born_pair_polar" in component_names
            )
            if energy_case.solvation_parameters is not None
            else None
        ),
        "accepted_iterations": uninterrupted.accepted_iterations,
        "accepted_armijo_iterations": (
            uninterrupted.accepted_armijo_iterations
        ),
        "accepted_stationarity_polish_iterations": (
            uninterrupted.accepted_stationarity_polish_iterations
        ),
        "rejected_trials": uninterrupted.rejected_trials,
        "energy_evaluation_count": uninterrupted.energy_evaluation_count,
        "energy_trace_sha256": _trace_sha256(uninterrupted, field="energy"),
        "coordinate_trace_sha256": _trace_sha256(
            uninterrupted,
            field="coordinate",
        ),
        "all_failure_rows": [
            row.to_dict()
            for row in uninterrupted.observations
            if row.failure_code is not None
        ],
        "metric_passes": metric_passes,
        "passed": all(metric_passes.values()),
        "openmm_evaluation_sha256": openmm.evaluation_sha256,
    }
    shared = {
        "physical": physical,
        "checkpoint_equal": checkpoint_equal,
    }
    return physical, shared


def build_openmm_reference_constraint_stationarity_receipt() -> dict[str, object]:
    """Execute the four eligible aliases and return a deterministic candidate receipt."""

    configuration = (
        openmm_reference_constraint_stationarity_configuration_document()
    )
    runtime_identity = observe_openmm_reference_runtime_identity()
    require_openmm_reference_runtime_identity_document(runtime_identity)
    source_identity = _source_identity_document()
    environment_identity = _environment_identity_document()
    config = ReferenceConstraintStationarityConfig()
    physical_rows = []
    case_rows = []
    for energy_case_id, checkpoint_case_id in _ELIGIBLE_CASES:
        physical, shared = _compare_physical_case(
            energy_case_id,
            checkpoint_case_id,
            config,
        )
        physical_rows.append(physical)
        for case_id, case_kind in (
            (energy_case_id, "same_coordinate_energy_force"),
            (checkpoint_case_id, "same_coordinate_checkpoint_restart"),
        ):
            case_passes = dict(physical["metric_passes"])
            if case_kind == "same_coordinate_energy_force":
                case_passes.pop("checkpoint_restart_document_equality")
            case_rows.append(
                {
                    "case_id": case_id,
                    "case_kind": case_kind,
                    "physical_input_id": physical["physical_input_id"],
                    "candidate_result_sha256": physical[
                        "candidate_result_sha256"
                    ],
                    "coordinate_f64le_sha256": physical[
                        "coordinate_f64le_sha256"
                    ],
                    "checkpoint_restart_document_equality": (
                        shared["checkpoint_equal"]
                        if case_kind
                        == "same_coordinate_checkpoint_restart"
                        else None
                    ),
                    "metric_passes": case_passes,
                    "passed": all(case_passes.values()),
                }
            )
    passed_case_count = sum(bool(row["passed"]) for row in case_rows)
    fixed_born_row = next(
        row
        for row in physical_rows
        if row["solvation_parameter_fingerprint_sha256"] is not None
    )
    projection = {
        "schema_id": OPENMM_REFERENCE_CONSTRAINT_STATIONARITY_RECEIPT_SCHEMA_ID,
        "configuration": configuration,
        "source_identity": source_identity,
        "environment_identity": environment_identity,
        "openmm_runtime_identity": runtime_identity,
        "physical_comparisons": physical_rows,
        "case_rows": case_rows,
        "excluded_case_rows": [
            *(
                {
                    "case_id": case_id,
                    "disposition": "not_applicable_unconstrained_v1",
                }
                for case_id in _EXCLUDED_V1_CASES
            ),
            *(
                {
                    "case_id": case_id,
                    "disposition": "preserved_frozen_fail_closed_not_reexecuted",
                }
                for case_id in _PRESERVED_FAIL_CLOSED_CASES
            ),
        ],
        "summary": {
            "candidate_case_denominator": len(case_rows),
            "candidate_case_passed_count": passed_case_count,
            "candidate_case_failed_count": len(case_rows) - passed_case_count,
            "physical_input_denominator": len(physical_rows),
            "checkpoint_case_denominator": 2,
            "checkpoint_restart_exact_count": sum(
                bool(row["checkpoint_restart_document_equality"])
                for row in case_rows
                if row["case_kind"] == "same_coordinate_checkpoint_restart"
            ),
            "excluded_frozen_case_count": 10,
            "frozen_14_case_production_denominator_claimed": False,
            "fixed_born_self_pair_components_recorded_separately": (
                fixed_born_row[
                    "fixed_born_self_pair_components_recorded_separately"
                ]
            ),
            "native_openmm_lbfgs_invoked": False,
            "native_openmm_lbfgs_status": "unchanged_rejected_6_of_8",
            "s0_complete": False,
        },
        "validation_receipt": False,
        "candidate_observation_receipt": True,
        "scientifically_validated": False,
        "claim_safe": False,
        "scientific_blockers": list(
            REFERENCE_CONSTRAINT_STATIONARITY_SCIENTIFIC_BLOCKERS
        ),
    }
    return {**projection, "receipt_sha256": _sha256(projection)}


def require_openmm_reference_constraint_stationarity_receipt(
    value: object,
    *,
    verify_current_sources: bool = True,
) -> dict[str, object]:
    """Verify receipt identity, denominators, thresholds, and current source bytes."""

    if not isinstance(value, Mapping):
        raise OpenMMReferenceConstraintStationarityError(
            "candidate receipt must be a mapping"
        )
    document = dict(value)
    supplied_digest = _require_sha256(
        document.get("receipt_sha256"),
        name="candidate receipt digest",
    )
    projection = {
        key: item for key, item in document.items() if key != "receipt_sha256"
    }
    if supplied_digest != _sha256(projection):
        raise OpenMMReferenceConstraintStationarityError(
            "candidate receipt digest mismatch"
        )
    if (
        document.get("schema_id")
        != OPENMM_REFERENCE_CONSTRAINT_STATIONARITY_RECEIPT_SCHEMA_ID
    ):
        raise OpenMMReferenceConstraintStationarityError(
            "unsupported candidate receipt schema"
        )
    expected_configuration = (
        openmm_reference_constraint_stationarity_configuration_document()
    )
    if document.get("configuration") != expected_configuration:
        raise OpenMMReferenceConstraintStationarityError(
            "candidate receipt configuration mismatch"
        )
    source_identity = document.get("source_identity")
    if not isinstance(source_identity, Mapping):
        raise OpenMMReferenceConstraintStationarityError(
            "candidate receipt source identity is missing"
        )
    source_projection = {
        key: item
        for key, item in source_identity.items()
        if key != "source_identity_sha256"
    }
    if source_identity.get("source_identity_sha256") != _sha256(
        source_projection
    ):
        raise OpenMMReferenceConstraintStationarityError(
            "candidate receipt source identity digest mismatch"
        )
    if verify_current_sources and source_identity != _source_identity_document():
        raise OpenMMReferenceConstraintStationarityError(
            "candidate receipt source identity does not match current bytes"
        )
    environment = document.get("environment_identity")
    if not isinstance(environment, Mapping):
        raise OpenMMReferenceConstraintStationarityError(
            "candidate receipt environment identity is missing"
        )
    environment_projection = {
        key: item
        for key, item in environment.items()
        if key != "environment_identity_sha256"
    }
    if environment.get("environment_identity_sha256") != _sha256(
        environment_projection
    ):
        raise OpenMMReferenceConstraintStationarityError(
            "candidate receipt environment identity digest mismatch"
        )
    if verify_current_sources and environment != _environment_identity_document():
        raise OpenMMReferenceConstraintStationarityError(
            "candidate receipt environment identity does not match current runtime"
        )
    runtime = document.get("openmm_runtime_identity")
    require_openmm_reference_runtime_identity_document(runtime)
    physical_rows = document.get("physical_comparisons")
    case_rows = document.get("case_rows")
    excluded_rows = document.get("excluded_case_rows")
    summary = document.get("summary")
    if (
        not isinstance(physical_rows, list)
        or len(physical_rows) != 2
        or not isinstance(case_rows, list)
        or len(case_rows) != 4
        or not isinstance(excluded_rows, list)
        or len(excluded_rows) != 10
        or not isinstance(summary, Mapping)
    ):
        raise OpenMMReferenceConstraintStationarityError(
            "candidate receipt denominator structure mismatch"
        )
    expected_case_ids = {
        case_id for pair in _ELIGIBLE_CASES for case_id in pair
    }
    if not all(isinstance(row, Mapping) for row in case_rows):
        raise OpenMMReferenceConstraintStationarityError(
            "candidate case row must be a mapping"
        )
    if {row.get("case_id") for row in case_rows} != expected_case_ids:
        raise OpenMMReferenceConstraintStationarityError(
            "candidate receipt case identity mismatch"
        )
    for row in physical_rows:
        if not isinstance(row, Mapping):
            raise OpenMMReferenceConstraintStationarityError(
                "candidate physical comparison must be a mapping"
            )
        energy = row.get("term_energy")
        force = row.get("force_error")
        tangent = row.get("tangent_force")
        components = row.get("component_energies")
        passes = row.get("metric_passes")
        if (
            not isinstance(energy, Mapping)
            or not isinstance(force, Mapping)
            or not isinstance(tangent, Mapping)
            or not isinstance(components, list)
            or not isinstance(passes, Mapping)
        ):
            raise OpenMMReferenceConstraintStationarityError(
                "candidate physical comparison metrics are incomplete"
            )
        invariants = (
            _finite(
                energy.get("absolute_error_kcal_per_mol"),
                name="term energy error",
                minimum=0.0,
            )
            <= OPENMM_REFERENCE_CONSTRAINT_STATIONARITY_ENERGY_THRESHOLD_KCAL_PER_MOL,
            _finite(
                force.get("max_abs_kcal_per_mol_angstrom"),
                name="force max error",
                minimum=0.0,
            )
            <= OPENMM_REFERENCE_CONSTRAINT_STATIONARITY_FORCE_THRESHOLD_KCAL_PER_MOL_ANGSTROM,
            _finite(
                force.get("rms_kcal_per_mol_angstrom"),
                name="force RMS error",
                minimum=0.0,
            )
            <= OPENMM_REFERENCE_CONSTRAINT_STATIONARITY_FORCE_THRESHOLD_KCAL_PER_MOL_ANGSTROM,
            _finite(
                tangent.get("engine_max_kcal_per_mol_angstrom"),
                name="Engine tangent force",
                minimum=0.0,
            )
            <= OPENMM_REFERENCE_CONSTRAINT_STATIONARITY_TANGENT_THRESHOLD_KCAL_PER_MOL_ANGSTROM,
            _finite(
                tangent.get("openmm_max_kcal_per_mol_angstrom"),
                name="OpenMM tangent force",
                minimum=0.0,
            )
            <= OPENMM_REFERENCE_CONSTRAINT_STATIONARITY_TANGENT_THRESHOLD_KCAL_PER_MOL_ANGSTROM,
            _finite(
                row.get("constraint_max_abs_residual_angstrom"),
                name="constraint residual",
                minimum=0.0,
            )
            <= OPENMM_REFERENCE_CONSTRAINT_STATIONARITY_CONSTRAINT_THRESHOLD_ANGSTROM,
            all(
                isinstance(component, Mapping)
                and bool(component.get("passed"))
                and _finite(
                    component.get("absolute_error_kcal_per_mol"),
                    name="component energy error",
                    minimum=0.0,
                )
                <= OPENMM_REFERENCE_CONSTRAINT_STATIONARITY_COMPONENT_THRESHOLD_KCAL_PER_MOL
                for component in components
            ),
        )
        if not all(invariants) or not all(bool(item) for item in passes.values()):
            raise OpenMMReferenceConstraintStationarityError(
                "candidate physical comparison does not pass frozen thresholds"
            )
        failure_rows = row.get("all_failure_rows")
        rejected = row.get("rejected_trials")
        if (
            not isinstance(failure_rows, list)
            or not isinstance(rejected, int)
            or isinstance(rejected, bool)
            or len(failure_rows) != rejected
        ):
            raise OpenMMReferenceConstraintStationarityError(
                "candidate failure row retention mismatch"
            )
    if not all(bool(row.get("passed")) for row in case_rows):
        raise OpenMMReferenceConstraintStationarityError(
            "candidate case row is not passing"
        )
    physical_by_id = {
        row["physical_input_id"]: row for row in physical_rows
    }
    for row in case_rows:
        physical = physical_by_id.get(row.get("physical_input_id"))
        if (
            physical is None
            or row.get("candidate_result_sha256")
            != physical.get("candidate_result_sha256")
            or row.get("coordinate_f64le_sha256")
            != physical.get("coordinate_f64le_sha256")
        ):
            raise OpenMMReferenceConstraintStationarityError(
                "candidate case row is cross-wired from its physical comparison"
            )
        if row.get("case_kind") == "same_coordinate_checkpoint_restart":
            if row.get("checkpoint_restart_document_equality") is not True:
                raise OpenMMReferenceConstraintStationarityError(
                    "candidate checkpoint case is missing exact restart equality"
                )
        elif (
            row.get("case_kind") != "same_coordinate_energy_force"
            or row.get("checkpoint_restart_document_equality") is not None
        ):
            raise OpenMMReferenceConstraintStationarityError(
                "candidate case kind or checkpoint disposition is invalid"
            )
    if (
        summary.get("candidate_case_denominator") != 4
        or summary.get("candidate_case_passed_count") != 4
        or summary.get("candidate_case_failed_count") != 0
        or summary.get("excluded_frozen_case_count") != 10
        or summary.get("frozen_14_case_production_denominator_claimed") is not False
        or summary.get("native_openmm_lbfgs_invoked") is not False
        or summary.get("native_openmm_lbfgs_status")
        != "unchanged_rejected_6_of_8"
        or summary.get("s0_complete") is not False
    ):
        raise OpenMMReferenceConstraintStationarityError(
            "candidate receipt summary is not claim-closed"
        )
    if (
        document.get("validation_receipt") is not False
        or document.get("candidate_observation_receipt") is not True
        or document.get("scientifically_validated") is not False
        or document.get("claim_safe") is not False
    ):
        raise OpenMMReferenceConstraintStationarityError(
            "candidate receipt overstates its evidence claim"
        )
    return document


def write_openmm_reference_constraint_stationarity_receipt(
    path: Path | str,
    receipt: Mapping[str, object],
) -> Path:
    """Write one verified receipt without silently replacing different evidence."""

    verified = require_openmm_reference_constraint_stationarity_receipt(receipt)
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        verified,
        allow_nan=False,
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
    ) + "\n"
    if destination.is_symlink():
        raise OpenMMReferenceConstraintStationarityError(
            "candidate receipt path must not be a symlink"
        )
    if destination.exists():
        if not stat.S_ISREG(destination.lstat().st_mode):
            raise OpenMMReferenceConstraintStationarityError(
                "candidate receipt path must be a regular file"
            )
        if destination.read_text(encoding="utf-8") != payload:
            raise OpenMMReferenceConstraintStationarityError(
                "refusing to overwrite a different candidate receipt"
            )
        os.chmod(destination, 0o600)
        return destination
    temporary = destination.with_name(f".{destination.name}.tmp-{os.getpid()}")
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
            raise OpenMMReferenceConstraintStationarityError(
                "candidate receipt path appeared during no-overwrite creation"
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


def read_openmm_reference_constraint_stationarity_receipt(
    path: Path | str,
) -> dict[str, object]:
    destination = Path(path)
    metadata = destination.lstat()
    if not stat.S_ISREG(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
        raise OpenMMReferenceConstraintStationarityError(
            "candidate receipt must be a regular non-symlink file"
        )
    mode = metadata.st_mode
    if mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise OpenMMReferenceConstraintStationarityError(
            "candidate receipt must not be group/world accessible"
        )
    try:
        value = json.loads(destination.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise OpenMMReferenceConstraintStationarityError(
            "candidate receipt is not readable canonical JSON"
        ) from exc
    return require_openmm_reference_constraint_stationarity_receipt(value)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build or verify the claim-closed stationarity candidate receipt"
        )
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify", type=Path)
    arguments = parser.parse_args(argv)
    if (arguments.output is None) == (arguments.verify is None):
        parser.error("exactly one of --output or --verify is required")
    if arguments.output is not None:
        receipt = build_openmm_reference_constraint_stationarity_receipt()
        destination = write_openmm_reference_constraint_stationarity_receipt(
            arguments.output,
            receipt,
        )
        print(
            json.dumps(
                {
                    "path": str(destination),
                    "receipt_sha256": receipt["receipt_sha256"],
                },
                sort_keys=True,
            )
        )
        return 0
    verified = read_openmm_reference_constraint_stationarity_receipt(
        arguments.verify
    )
    print(
        json.dumps(
            {
                "path": str(arguments.verify),
                "receipt_sha256": verified["receipt_sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "FROZEN_LEGACY_OPENMM_REFERENCE_CONSTRAINT_STATIONARITY_CONFIG_SHA256_V1",
    "FROZEN_LEGACY_OPENMM_REFERENCE_CONSTRAINT_STATIONARITY_CONFIG_SHA256_V1_1",
    "FROZEN_OPENMM_REFERENCE_CONSTRAINT_STATIONARITY_CONFIG_SHA256",
    "OPENMM_REFERENCE_CONSTRAINT_STATIONARITY_CONFIG_SCHEMA_ID",
    "OPENMM_REFERENCE_CONSTRAINT_STATIONARITY_RECEIPT_SCHEMA_ID",
    "OpenMMReferenceConstraintStationarityError",
    "build_openmm_reference_constraint_stationarity_receipt",
    "main",
    "openmm_reference_constraint_stationarity_configuration_document",
    "read_openmm_reference_constraint_stationarity_receipt",
    "require_openmm_reference_constraint_stationarity_receipt",
    "write_openmm_reference_constraint_stationarity_receipt",
]
