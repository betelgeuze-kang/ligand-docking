"""Bounded numerical per-term diagnostics for the frozen reference evaluator."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from numbers import Real
import operator
import struct
from types import MappingProxyType
from typing import Mapping

import torch

from betelgeuze_engine_v2.geometry import (
    NeighborOverflowError,
    RadiusGraphConfig,
    build_compact_radius_graph,
)
from betelgeuze_engine_v2.molecular import (
    AllAtomSystem,
    canonical_system_sha256,
    canonical_topology_sha256,
)
from .reference_forcefield import (
    ReferencePhysicsApplicabilityError,
    ReferencePhysicsEvaluation,
    evaluate_reference_force_field,
)
from .reference_parameters import ReferenceForceFieldParameters
from .reference_validation_artifact_binding import reference_forcefield_source_sha256


REFERENCE_TERM_DIAGNOSTICS_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_term_diagnostics/1.0.0"
)
REFERENCE_TERM_DIAGNOSTICS_CONFIG_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_term_diagnostics_config/1.0.0"
)
REFERENCE_TERM_DIAGNOSTICS_ALGORITHM_ID = (
    "bounded_component_energy_central_difference_force_virial/1.0.0"
)
REFERENCE_TERM_DIAGNOSTICS_MAX_ATOMS = 128
REFERENCE_TERM_DIAGNOSTICS_MAX_PERTURBATIONS = 6 * REFERENCE_TERM_DIAGNOSTICS_MAX_ATOMS
REFERENCE_TERM_NAMES = (
    "harmonic_bond",
    "harmonic_angle",
    "periodic_torsion",
    "lennard_jones",
    "screened_coulomb",
)
REFERENCE_VIRIAL_CONVENTION = (
    "W_ab=sum_i((r_i-r_center_of_geometry)_a*F_i_b); "
    "units=kcal/mol; configurational diagnostic only; not pressure or stress"
)
REFERENCE_TERM_DIAGNOSTICS_SCIENTIFIC_BLOCKERS = (
    "caller_supplied_reference_parameters_not_independently_reviewed",
    "finite_difference_diagnostics_not_independent_scientific_validation",
    "reference_parameter_applicability_domain_not_scientifically_established",
    "public_force_virial_validation_missing",
    "product_integration_not_qualified",
)


class ReferenceTermDiagnosticsError(ValueError):
    """The diagnostics request violates a numerical, identity, or capacity bound."""


class _ReferenceTermNumericalError(ArithmeticError):
    """One perturbation produced non-finite component energy."""


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
        raise ReferenceTermDiagnosticsError(
            "diagnostics payload is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _exact_int(
    value: object,
    *,
    name: str,
    minimum: int,
    maximum: int,
) -> int:
    if isinstance(value, bool):
        raise ReferenceTermDiagnosticsError(f"{name} must be an integer")
    try:
        result = int(operator.index(value))
    except TypeError:
        raise ReferenceTermDiagnosticsError(f"{name} must be an integer") from None
    if result < minimum or result > maximum:
        raise ReferenceTermDiagnosticsError(
            f"{name} must be in [{minimum},{maximum}]"
        )
    return result


def _finite_positive(value: object, *, name: str, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ReferenceTermDiagnosticsError(f"{name} must be a finite real number")
    result = float(value)
    if not math.isfinite(result) or result <= 0.0 or result > maximum:
        raise ReferenceTermDiagnosticsError(
            f"{name} must be finite and in (0,{maximum}]"
        )
    return result


def _tensor_bytes(value: torch.Tensor) -> bytes:
    tensor = value.detach().to(device="cpu", dtype=torch.float64).contiguous()
    values = tensor.view(-1).tolist()
    payload = bytearray(8 * len(values))
    for index, item in enumerate(values):
        struct.pack_into("<d", payload, index * 8, float(item))
    return bytes(payload)


def _tensor_sha256(value: torch.Tensor) -> str:
    return hashlib.sha256(_tensor_bytes(value)).hexdigest()


def _coordinate_sha256(value: torch.Tensor) -> str:
    return _tensor_sha256(value)


@dataclass(frozen=True, slots=True)
class ReferenceTermDiagnosticsConfig:
    """Finite-difference, tolerance, and neighbor-capacity bounds."""

    central_difference_step_angstrom: float = 1.0e-5
    force_consistency_atol_kcal_per_mol_angstrom: float = 5.0e-4
    force_consistency_rtol: float = 5.0e-4
    net_force_atol_kcal_per_mol_angstrom: float = 5.0e-4
    virial_symmetry_atol_kcal_per_mol: float = 5.0e-4
    max_atoms: int = REFERENCE_TERM_DIAGNOSTICS_MAX_ATOMS
    max_neighbors: int = 256
    max_atoms_per_cell: int = 512
    schema_id: str = REFERENCE_TERM_DIAGNOSTICS_CONFIG_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != REFERENCE_TERM_DIAGNOSTICS_CONFIG_SCHEMA_ID:
            raise ReferenceTermDiagnosticsError(
                "unsupported reference term diagnostics config schema"
            )
        object.__setattr__(
            self,
            "central_difference_step_angstrom",
            _finite_positive(
                self.central_difference_step_angstrom,
                name="central_difference_step_angstrom",
                maximum=0.1,
            ),
        )
        for name, maximum in (
            ("force_consistency_atol_kcal_per_mol_angstrom", 1.0),
            ("force_consistency_rtol", 1.0),
            ("net_force_atol_kcal_per_mol_angstrom", 1.0),
            ("virial_symmetry_atol_kcal_per_mol", 1.0),
        ):
            object.__setattr__(
                self,
                name,
                _finite_positive(getattr(self, name), name=name, maximum=maximum),
            )
        object.__setattr__(
            self,
            "max_atoms",
            _exact_int(
                self.max_atoms,
                name="max_atoms",
                minimum=1,
                maximum=REFERENCE_TERM_DIAGNOSTICS_MAX_ATOMS,
            ),
        )
        object.__setattr__(
            self,
            "max_neighbors",
            _exact_int(
                self.max_neighbors,
                name="max_neighbors",
                minimum=1,
                maximum=65_536,
            ),
        )
        object.__setattr__(
            self,
            "max_atoms_per_cell",
            _exact_int(
                self.max_atoms_per_cell,
                name="max_atoms_per_cell",
                minimum=1,
                maximum=1_000_000,
            ),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "algorithm_id": REFERENCE_TERM_DIAGNOSTICS_ALGORITHM_ID,
            "central_difference_step_angstrom": self.central_difference_step_angstrom,
            "force_consistency_atol_kcal_per_mol_angstrom": (
                self.force_consistency_atol_kcal_per_mol_angstrom
            ),
            "force_consistency_rtol": self.force_consistency_rtol,
            "net_force_atol_kcal_per_mol_angstrom": (
                self.net_force_atol_kcal_per_mol_angstrom
            ),
            "virial_symmetry_atol_kcal_per_mol": (
                self.virial_symmetry_atol_kcal_per_mol
            ),
            "max_atoms": self.max_atoms,
            "max_neighbors": self.max_neighbors,
            "max_atoms_per_cell": self.max_atoms_per_cell,
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _sha256(self.to_dict())


@dataclass(frozen=True, slots=True)
class ReferenceTermDiagnosticsObservation:
    """One retained plus/minus coordinate perturbation outcome."""

    atom_index: int
    axis: int
    direction: int
    coordinates_sha256: str
    status: str
    component_energies_kcal_per_mol: tuple[tuple[str, float], ...]
    failure_code: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "atom_index": self.atom_index,
            "axis": self.axis,
            "direction": self.direction,
            "coordinates_sha256": self.coordinates_sha256,
            "status": self.status,
            "component_energies_kcal_per_mol": [
                {"term": name, "value": value, "unit": "kcal/mol"}
                for name, value in self.component_energies_kcal_per_mol
            ],
            "failure_code": self.failure_code,
        }


@dataclass(frozen=True, slots=True)
class ReferenceTermDiagnosticsResult:
    """Failure-inclusive component force and bounded virial diagnostics."""

    source_system_sha256: str
    topology_sha256: str
    parameter_fingerprint_sha256: str
    evaluator_source_sha256: str
    config_fingerprint_sha256: str
    base_evaluation: ReferencePhysicsEvaluation
    component_forces: Mapping[str, torch.Tensor]
    component_virials: Mapping[str, torch.Tensor]
    observations: tuple[ReferenceTermDiagnosticsObservation, ...]
    blockers: tuple[str, ...]
    max_component_force_sum_error_kcal_per_mol_angstrom: float | None
    max_component_net_force_kcal_per_mol_angstrom: float | None
    max_component_virial_antisymmetry_kcal_per_mol: float | None
    provenance_sha256: str
    scientific_blockers: tuple[str, ...] = (
        REFERENCE_TERM_DIAGNOSTICS_SCIENTIFIC_BLOCKERS
    )
    schema_id: str = REFERENCE_TERM_DIAGNOSTICS_SCHEMA_ID

    @property
    def expected_perturbation_count(self) -> int:
        return 6 * self.base_evaluation.term.forces.shape[1]

    @property
    def observed_perturbation_count(self) -> int:
        return len(self.observations)

    @property
    def failed_perturbation_count(self) -> int:
        return sum(row.status != "success" for row in self.observations)

    @property
    def force_diagnostics_complete(self) -> bool:
        return bool(self.component_forces) and not any(
            blocker.startswith("force_")
            or blocker.startswith("component_energy_")
            or blocker.startswith("perturbation_")
            for blocker in self.blockers
        )

    @property
    def virial_diagnostics_complete(self) -> bool:
        return self.force_diagnostics_complete and bool(self.component_virials) and not any(
            blocker.startswith("virial_") or blocker.startswith("periodic_virial_")
            for blocker in self.blockers
        )

    @property
    def diagnostics_complete(self) -> bool:
        return self.force_diagnostics_complete and self.virial_diagnostics_complete

    @property
    def scientifically_validated(self) -> bool:
        return False

    def total_component_force(self) -> torch.Tensor | None:
        if not self.component_forces:
            return None
        return sum(
            (self.component_forces[name] for name in REFERENCE_TERM_NAMES),
            torch.zeros_like(self.base_evaluation.term.forces),
        )

    def total_component_virial(self) -> torch.Tensor | None:
        if not self.component_virials:
            return None
        template = self.component_virials[REFERENCE_TERM_NAMES[0]]
        return sum(
            (self.component_virials[name] for name in REFERENCE_TERM_NAMES),
            torch.zeros_like(template),
        )

    def to_dict(self) -> dict[str, object]:
        component_rows: list[dict[str, object]] = []
        for name in REFERENCE_TERM_NAMES:
            force = self.component_forces.get(name)
            virial = self.component_virials.get(name)
            component_rows.append(
                {
                    "term": name,
                    "energy_kcal_per_mol": float(
                        self.base_evaluation.component_energies[name][0].item()
                    ),
                    "force_unit": "kcal/mol/angstrom",
                    "force_shape": [] if force is None else list(force.shape),
                    "force_sha256": "" if force is None else _tensor_sha256(force),
                    "net_force_kcal_per_mol_angstrom": (
                        []
                        if force is None
                        else [float(value) for value in force.sum(dim=1)[0].tolist()]
                    ),
                    "virial_available": virial is not None,
                    "virial_unit": "kcal/mol",
                    "virial_shape": [] if virial is None else list(virial.shape),
                    "virial_sha256": "" if virial is None else _tensor_sha256(virial),
                    "virial_trace_kcal_per_mol": (
                        None if virial is None else float(torch.trace(virial[0]).item())
                    ),
                }
            )
        total_force = self.total_component_force()
        total_virial = self.total_component_virial()
        return {
            "schema_id": self.schema_id,
            "algorithm_id": REFERENCE_TERM_DIAGNOSTICS_ALGORITHM_ID,
            "source_system_sha256": self.source_system_sha256,
            "topology_sha256": self.topology_sha256,
            "parameter_fingerprint_sha256": self.parameter_fingerprint_sha256,
            "evaluator_source_sha256": self.evaluator_source_sha256,
            "config_fingerprint_sha256": self.config_fingerprint_sha256,
            "provenance_sha256": self.provenance_sha256,
            "expected_perturbation_count": self.expected_perturbation_count,
            "observed_perturbation_count": self.observed_perturbation_count,
            "failed_perturbation_count": self.failed_perturbation_count,
            "force_diagnostics_complete": self.force_diagnostics_complete,
            "virial_diagnostics_complete": self.virial_diagnostics_complete,
            "diagnostics_complete": self.diagnostics_complete,
            "scientifically_validated": False,
            "claim_safe": False,
            "virial_convention": REFERENCE_VIRIAL_CONVENTION,
            "component_rows": component_rows,
            "analytic_total_force_sha256": _tensor_sha256(
                self.base_evaluation.term.forces
            ),
            "component_force_sum_sha256": (
                "" if total_force is None else _tensor_sha256(total_force)
            ),
            "component_virial_sum_sha256": (
                "" if total_virial is None else _tensor_sha256(total_virial)
            ),
            "max_component_force_sum_error_kcal_per_mol_angstrom": (
                self.max_component_force_sum_error_kcal_per_mol_angstrom
            ),
            "max_component_net_force_kcal_per_mol_angstrom": (
                self.max_component_net_force_kcal_per_mol_angstrom
            ),
            "max_component_virial_antisymmetry_kcal_per_mol": (
                self.max_component_virial_antisymmetry_kcal_per_mol
            ),
            "blockers": list(self.blockers),
            "observations": [row.to_dict() for row in self.observations],
            "scientific_blockers": list(self.scientific_blockers),
        }


def _validate_request(
    system: AllAtomSystem,
    parameters: ReferenceForceFieldParameters,
    config: ReferenceTermDiagnosticsConfig,
) -> None:
    if not isinstance(system, AllAtomSystem):
        raise ReferenceTermDiagnosticsError("system must be AllAtomSystem")
    if not isinstance(parameters, ReferenceForceFieldParameters):
        raise ReferenceTermDiagnosticsError(
            "parameters must be ReferenceForceFieldParameters"
        )
    if system.coordinates.device.type != "cpu":
        raise ReferenceTermDiagnosticsError("diagnostics require CPU coordinates")
    if system.coordinates.dtype != torch.float64:
        raise ReferenceTermDiagnosticsError("diagnostics require float64 coordinates")
    if system.model_count != 1:
        raise ReferenceTermDiagnosticsError("diagnostics require exactly one model")
    if system.atom_count < 1 or system.atom_count > config.max_atoms:
        raise ReferenceTermDiagnosticsError(
            "system atom count exceeds the bounded diagnostics capacity"
        )
    if tuple(system.coordinates.shape) != (1, system.atom_count, 3):
        raise ReferenceTermDiagnosticsError(
            "system atom identity and coordinate shape mismatch"
        )
    if not bool(torch.isfinite(system.coordinates).all().item()):
        raise ReferenceTermDiagnosticsError("diagnostics coordinates must be finite")


def _evaluate(
    source_system: AllAtomSystem,
    coordinates: torch.Tensor,
    parameters: ReferenceForceFieldParameters,
    config: ReferenceTermDiagnosticsConfig,
    *,
    operation: str,
) -> ReferencePhysicsEvaluation:
    state = source_system.with_coordinates(coordinates, operation=operation)
    neighbors = build_compact_radius_graph(
        state.coordinates,
        RadiusGraphConfig(
            cutoff_angstrom=parameters.cutoff_angstrom,
            max_neighbors=config.max_neighbors,
            max_atoms_per_cell=config.max_atoms_per_cell,
        ),
        cell=state.cell,
    )
    return evaluate_reference_force_field(state, neighbors, parameters)


def _component_energy_rows(
    evaluation: ReferencePhysicsEvaluation,
) -> tuple[tuple[str, float], ...]:
    if tuple(sorted(evaluation.component_energies)) != tuple(
        sorted(REFERENCE_TERM_NAMES)
    ):
        raise ReferenceTermDiagnosticsError(
            "reference evaluator component names drifted from diagnostics contract"
        )
    rows = tuple(
        (name, float(evaluation.component_energies[name][0].item()))
        for name in REFERENCE_TERM_NAMES
    )
    if not all(math.isfinite(value) for _, value in rows):
        raise _ReferenceTermNumericalError(
            "reference evaluator produced non-finite component energy"
        )
    return rows


def evaluate_reference_term_diagnostics(
    system: AllAtomSystem,
    parameters: ReferenceForceFieldParameters,
    config: ReferenceTermDiagnosticsConfig | None = None,
) -> ReferenceTermDiagnosticsResult:
    """Numerically differentiate every component without modifying the frozen evaluator."""

    config = ReferenceTermDiagnosticsConfig() if config is None else config
    if not isinstance(config, ReferenceTermDiagnosticsConfig):
        raise ReferenceTermDiagnosticsError(
            "config must be ReferenceTermDiagnosticsConfig"
        )
    _validate_request(system, parameters, config)
    evaluator_sha256 = reference_forcefield_source_sha256()
    coordinates = system.coordinates.detach().clone()
    try:
        base = _evaluate(
            system,
            coordinates,
            parameters,
            config,
            operation="reference_term_diagnostics_base",
        )
    except (NeighborOverflowError, ReferencePhysicsApplicabilityError) as exc:
        raise ReferenceTermDiagnosticsError(
            f"base reference state is not applicable: {exc}"
        ) from exc
    if not bool(torch.isfinite(base.term.forces).all().item()):
        raise ReferenceTermDiagnosticsError(
            "base reference evaluator produced non-finite analytic force"
        )
    try:
        base_components = dict(_component_energy_rows(base))
    except _ReferenceTermNumericalError as exc:
        raise ReferenceTermDiagnosticsError(str(exc)) from exc
    observations: list[ReferenceTermDiagnosticsObservation] = []
    perturbation_energies: dict[tuple[int, int, int], dict[str, float]] = {}
    step = config.central_difference_step_angstrom

    for atom_index in range(system.atom_count):
        for axis in range(3):
            for direction in (-1, 1):
                perturbed = coordinates.clone()
                perturbed[0, atom_index, axis] += direction * step
                coordinate_sha256 = _coordinate_sha256(perturbed)
                try:
                    evaluation = _evaluate(
                        system,
                        perturbed,
                        parameters,
                        config,
                        operation=(
                            "reference_term_diagnostics_"
                            f"atom_{atom_index}_axis_{axis}_direction_{direction}"
                        ),
                    )
                    rows = _component_energy_rows(evaluation)
                except (NeighborOverflowError, ReferencePhysicsApplicabilityError) as exc:
                    failure_kind = (
                        "neighbor_capacity"
                        if isinstance(exc, NeighborOverflowError)
                        else "reference_physics_applicability"
                    )
                    observations.append(
                        ReferenceTermDiagnosticsObservation(
                            atom_index=atom_index,
                            axis=axis,
                            direction=direction,
                            coordinates_sha256=coordinate_sha256,
                            status=f"failed_{failure_kind}",
                            component_energies_kcal_per_mol=(),
                            failure_code=(
                                f"{failure_kind}_failed:"
                                + str(exc).split(":", 1)[0]
                            ),
                        )
                    )
                    continue
                except _ReferenceTermNumericalError as exc:
                    observations.append(
                        ReferenceTermDiagnosticsObservation(
                            atom_index=atom_index,
                            axis=axis,
                            direction=direction,
                            coordinates_sha256=coordinate_sha256,
                            status="failed_nonfinite_component_energy",
                            component_energies_kcal_per_mol=(),
                            failure_code=str(exc),
                        )
                    )
                    continue
                perturbation_energies[(atom_index, axis, direction)] = dict(rows)
                observations.append(
                    ReferenceTermDiagnosticsObservation(
                        atom_index=atom_index,
                        axis=axis,
                        direction=direction,
                        coordinates_sha256=coordinate_sha256,
                        status="success",
                        component_energies_kcal_per_mol=rows,
                        failure_code=None,
                    )
                )

    blockers: list[str] = []
    failed_count = sum(row.status != "success" for row in observations)
    if len(observations) != 6 * system.atom_count:
        blockers.append("perturbation_denominator_incomplete")
    if failed_count:
        blockers.append("perturbation_evaluations_failed")

    component_forces: dict[str, torch.Tensor] = {}
    component_virials: dict[str, torch.Tensor] = {}
    max_force_error: float | None = None
    max_net_force: float | None = None
    max_virial_antisymmetry: float | None = None

    if not blockers:
        for name in REFERENCE_TERM_NAMES:
            force = torch.zeros_like(coordinates)
            for atom_index in range(system.atom_count):
                for axis in range(3):
                    plus = perturbation_energies[(atom_index, axis, 1)][name]
                    minus = perturbation_energies[(atom_index, axis, -1)][name]
                    force[0, atom_index, axis] = -(plus - minus) / (2.0 * step)
            component_forces[name] = force

        energy_sum = sum(base_components.values())
        total_energy = float(base.term.energy[0].item())
        if not math.isclose(energy_sum, total_energy, rel_tol=1.0e-12, abs_tol=1.0e-12):
            blockers.append("component_energy_sum_not_equal_to_total")

        numerical_total = sum(
            (component_forces[name] for name in REFERENCE_TERM_NAMES),
            torch.zeros_like(base.term.forces),
        )
        difference = (numerical_total - base.term.forces).abs()
        max_force_error = float(difference.max().item())
        analytic_scale = float(base.term.forces.abs().max().item())
        force_limit = (
            config.force_consistency_atol_kcal_per_mol_angstrom
            + config.force_consistency_rtol * analytic_scale
        )
        if max_force_error > force_limit:
            blockers.append("force_component_sum_not_within_analytic_tolerance")

        max_net_force = max(
            float(component_forces[name].sum(dim=1).abs().max().item())
            for name in REFERENCE_TERM_NAMES
        )
        if max_net_force > config.net_force_atol_kcal_per_mol_angstrom:
            blockers.append("force_component_net_force_not_within_tolerance")

        if system.cell is not None:
            blockers.append("periodic_virial_requires_cell_strain_derivative")
        else:
            centered = coordinates - coordinates.mean(dim=1, keepdim=True)
            for name in REFERENCE_TERM_NAMES:
                component_virials[name] = torch.einsum(
                    "bni,bnj->bij", centered, component_forces[name]
                )
            max_virial_antisymmetry = max(
                float(
                    (
                        component_virials[name]
                        - component_virials[name].transpose(-1, -2)
                    )
                    .abs()
                    .max()
                    .item()
                )
                for name in REFERENCE_TERM_NAMES
            )
            if (
                max_virial_antisymmetry
                > config.virial_symmetry_atol_kcal_per_mol
            ):
                blockers.append("virial_component_antisymmetry_exceeds_tolerance")

    observation_rows = tuple(observations)
    provenance_projection = {
        "schema_id": REFERENCE_TERM_DIAGNOSTICS_SCHEMA_ID,
        "algorithm_id": REFERENCE_TERM_DIAGNOSTICS_ALGORITHM_ID,
        "source_system_sha256": canonical_system_sha256(system),
        "topology_sha256": canonical_topology_sha256(system),
        "parameter_fingerprint_sha256": parameters.fingerprint_sha256,
        "evaluator_source_sha256": evaluator_sha256,
        "config_fingerprint_sha256": config.fingerprint_sha256,
        "observation_rows": [row.to_dict() for row in observation_rows],
        "blockers": list(dict.fromkeys(blockers)),
    }
    return ReferenceTermDiagnosticsResult(
        source_system_sha256=canonical_system_sha256(system),
        topology_sha256=canonical_topology_sha256(system),
        parameter_fingerprint_sha256=parameters.fingerprint_sha256,
        evaluator_source_sha256=evaluator_sha256,
        config_fingerprint_sha256=config.fingerprint_sha256,
        base_evaluation=base,
        component_forces=MappingProxyType(component_forces),
        component_virials=MappingProxyType(component_virials),
        observations=observation_rows,
        blockers=tuple(dict.fromkeys(blockers)),
        max_component_force_sum_error_kcal_per_mol_angstrom=max_force_error,
        max_component_net_force_kcal_per_mol_angstrom=max_net_force,
        max_component_virial_antisymmetry_kcal_per_mol=max_virial_antisymmetry,
        provenance_sha256=_sha256(provenance_projection),
    )


__all__ = [
    "REFERENCE_TERM_DIAGNOSTICS_ALGORITHM_ID",
    "REFERENCE_TERM_DIAGNOSTICS_CONFIG_SCHEMA_ID",
    "REFERENCE_TERM_DIAGNOSTICS_MAX_ATOMS",
    "REFERENCE_TERM_DIAGNOSTICS_MAX_PERTURBATIONS",
    "REFERENCE_TERM_DIAGNOSTICS_SCHEMA_ID",
    "REFERENCE_TERM_DIAGNOSTICS_SCIENTIFIC_BLOCKERS",
    "REFERENCE_TERM_NAMES",
    "REFERENCE_VIRIAL_CONVENTION",
    "ReferenceTermDiagnosticsConfig",
    "ReferenceTermDiagnosticsError",
    "ReferenceTermDiagnosticsObservation",
    "ReferenceTermDiagnosticsResult",
    "evaluate_reference_term_diagnostics",
]
