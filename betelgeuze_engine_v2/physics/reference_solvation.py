"""Bounded fixed-effective-radius polar Generalized Born reference term."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
from numbers import Real
import operator
import struct
from types import MappingProxyType
from typing import Any, Mapping

import torch

from betelgeuze_engine_v2.contracts import QuantityDescriptor
from betelgeuze_engine_v2.geometry import CompactNeighborList
from betelgeuze_engine_v2.molecular import (
    AllAtomSystem,
    canonical_system_sha256,
    canonical_topology_sha256,
)
from .composition import EnergyTermResult
from .reference_forcefield_v2 import (
    ReferenceForceFieldV2Evaluation,
    ReferenceForceFieldV2Parameters,
    evaluate_reference_force_field_v2,
)
from .reference_parameters import COULOMB_KCAL_ANGSTROM_PER_MOL_E2


REFERENCE_FIXED_BORN_PARAMETER_SCHEMA_ID = (
    "betelgeuze.engine_v2_fixed_born_polar_solvation_parameters/1.0.0"
)
REFERENCE_FIXED_BORN_EVALUATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_fixed_born_polar_solvation_evaluation/1.0.0"
)
REFERENCE_FORCEFIELD_V2_SOLVATED_EVALUATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_forcefield_solvated_evaluation/1.0.0"
)
REFERENCE_FIXED_BORN_ALGORITHM_ID = (
    "still_fixed_effective_born_radius_polar_transfer/1.0.0"
)
REFERENCE_FIXED_BORN_PRIMARY_REFERENCE_DOI = "10.1021/ja00172a038"
REFERENCE_FIXED_BORN_MAX_ATOMS = 512
REFERENCE_FIXED_BORN_MAX_PAIRS = (
    REFERENCE_FIXED_BORN_MAX_ATOMS * (REFERENCE_FIXED_BORN_MAX_ATOMS - 1) // 2
)
REFERENCE_FIXED_BORN_SCIENTIFIC_BLOCKERS = (
    "caller_supplied_effective_born_radii_not_independently_reviewed",
    "effective_born_radius_estimation_not_implemented",
    "fixed_radius_polar_gb_not_scientifically_validated",
    "nonpolar_solvation_not_implemented",
    "salt_and_explicit_ion_effects_not_implemented",
    "periodic_solvation_not_supported",
    "solvated_constrained_minimization_not_scientifically_validated",
    "independent_solvated_minimization_evidence_missing",
    "independent_solvation_reference_evidence_missing",
    "product_integration_not_qualified",
)


class ReferenceFixedBornSolvationError(ValueError):
    """The fixed-radius solvation parameter or numerical contract is invalid."""


class ReferenceFixedBornSolvationApplicabilityError(RuntimeError):
    """The fixed-radius polar solvation term cannot evaluate the supplied state."""


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
        raise ReferenceFixedBornSolvationError(
            "fixed Born solvation payload is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _digest(value: object, *, name: str) -> str:
    if not isinstance(value, str):
        raise ReferenceFixedBornSolvationError(f"{name} must be a SHA-256 digest")
    digest = value.strip().lower()
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise ReferenceFixedBornSolvationError(
            f"{name} must be a lowercase SHA-256 digest"
        )
    return digest


def _exact_int(value: object, *, name: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool):
        raise ReferenceFixedBornSolvationError(f"{name} must be an integer")
    try:
        result = int(operator.index(value))
    except TypeError:
        raise ReferenceFixedBornSolvationError(f"{name} must be an integer") from None
    if result < minimum or result > maximum:
        raise ReferenceFixedBornSolvationError(
            f"{name} must be in [{minimum},{maximum}]"
        )
    return result


def _finite_float(
    value: object,
    *,
    name: str,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ReferenceFixedBornSolvationError(
            f"{name} must be a finite real number"
        )
    result = float(value)
    if not math.isfinite(result):
        raise ReferenceFixedBornSolvationError(f"{name} must be finite")
    if minimum is not None and result <= minimum:
        raise ReferenceFixedBornSolvationError(f"{name} must be > {minimum}")
    if maximum is not None and result > maximum:
        raise ReferenceFixedBornSolvationError(f"{name} must be <= {maximum}")
    return result


def _identifier(value: object, *, name: str) -> str:
    if not isinstance(value, str):
        raise ReferenceFixedBornSolvationError(f"{name} must be a string")
    result = value.strip()
    if not result or len(result) > 256 or not result.isascii():
        raise ReferenceFixedBornSolvationError(
            f"{name} must be non-empty ASCII with at most 256 characters"
        )
    return result


def _freeze_json(value: Any, *, path: str = "metadata") -> Any:
    if value is None or isinstance(value, (bool, str, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ReferenceFixedBornSolvationError(
                f"{path} contains a non-finite float"
            )
        return float(value)
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise ReferenceFixedBornSolvationError(f"{path} keys must be strings")
        return MappingProxyType(
            {
                key: _freeze_json(value[key], path=f"{path}.{key}")
                for key in sorted(value)
            }
        )
    if isinstance(value, (tuple, list)):
        return tuple(
            _freeze_json(item, path=f"{path}[{index}]")
            for index, item in enumerate(value)
        )
    raise ReferenceFixedBornSolvationError(
        f"{path} contains unsupported JSON value {type(value).__name__}"
    )


def _thaw_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return value


def _tensor_sha256(value: torch.Tensor) -> str:
    values = value.detach().to(dtype=torch.float64, device="cpu").contiguous().view(-1)
    payload = bytearray(8 * values.numel())
    for index, item in enumerate(values.tolist()):
        struct.pack_into("<d", payload, index * 8, float(item))
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True, slots=True)
class FixedBornAtomParameter:
    atom_index: int
    effective_born_radius_angstrom: float

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "atom_index",
            _exact_int(
                self.atom_index,
                name="fixed Born atom_index",
                minimum=0,
                maximum=2**31 - 1,
            ),
        )
        object.__setattr__(
            self,
            "effective_born_radius_angstrom",
            _finite_float(
                self.effective_born_radius_angstrom,
                name="effective_born_radius_angstrom",
                minimum=0.0,
                maximum=100.0,
            ),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "atom_index": self.atom_index,
            "effective_born_radius_angstrom": self.effective_born_radius_angstrom,
        }


@dataclass(frozen=True, slots=True)
class FixedBornPolarSolvationParameters:
    parameter_set_id: str
    parameter_set_version: str
    parameter_source_sha256: str
    topology_sha256: str
    charge_parameter_fingerprint_sha256: str
    atom_parameters: tuple[FixedBornAtomParameter, ...]
    solute_dielectric: float = 1.0
    solvent_dielectric: float = 78.5
    minimum_pair_distance_angstrom: float = 0.35
    max_atoms: int = REFERENCE_FIXED_BORN_MAX_ATOMS
    metadata: Mapping[str, Any] = field(default_factory=dict)
    scientifically_validated: bool = False
    schema_id: str = REFERENCE_FIXED_BORN_PARAMETER_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != REFERENCE_FIXED_BORN_PARAMETER_SCHEMA_ID:
            raise ReferenceFixedBornSolvationError(
                "unsupported fixed Born solvation parameter schema"
            )
        supplied_rows = tuple(self.atom_parameters)
        if not supplied_rows or not all(
            isinstance(row, FixedBornAtomParameter) for row in supplied_rows
        ):
            raise ReferenceFixedBornSolvationError(
                "atom_parameters must contain FixedBornAtomParameter rows"
            )
        rows = tuple(sorted(supplied_rows, key=lambda row: row.atom_index))
        indices = [row.atom_index for row in rows]
        if len(indices) != len(set(indices)):
            raise ReferenceFixedBornSolvationError(
                "fixed Born atom parameter indices must be unique"
            )
        max_atoms = _exact_int(
            self.max_atoms,
            name="max_atoms",
            minimum=1,
            maximum=REFERENCE_FIXED_BORN_MAX_ATOMS,
        )
        if len(rows) > max_atoms:
            raise ReferenceFixedBornSolvationError(
                "fixed Born atom parameter capacity exceeded"
            )
        solute = _finite_float(
            self.solute_dielectric,
            name="solute_dielectric",
            minimum=0.0,
            maximum=1.0e4,
        )
        solvent = _finite_float(
            self.solvent_dielectric,
            name="solvent_dielectric",
            minimum=0.0,
            maximum=1.0e4,
        )
        if solvent <= solute:
            raise ReferenceFixedBornSolvationError(
                "solvent_dielectric must be greater than solute_dielectric"
            )
        if not isinstance(self.metadata, Mapping):
            raise ReferenceFixedBornSolvationError("metadata must be a mapping")
        if not isinstance(self.scientifically_validated, bool):
            raise ReferenceFixedBornSolvationError(
                "scientifically_validated must be a boolean"
            )
        if self.scientifically_validated:
            raise ReferenceFixedBornSolvationError(
                "fixed Born scientific promotion requires independent evidence"
            )
        object.__setattr__(
            self, "parameter_set_id", _identifier(self.parameter_set_id, name="parameter_set_id")
        )
        object.__setattr__(
            self,
            "parameter_set_version",
            _identifier(self.parameter_set_version, name="parameter_set_version"),
        )
        object.__setattr__(
            self,
            "parameter_source_sha256",
            _digest(self.parameter_source_sha256, name="parameter_source_sha256"),
        )
        object.__setattr__(
            self,
            "topology_sha256",
            _digest(self.topology_sha256, name="topology_sha256"),
        )
        object.__setattr__(
            self,
            "charge_parameter_fingerprint_sha256",
            _digest(
                self.charge_parameter_fingerprint_sha256,
                name="charge_parameter_fingerprint_sha256",
            ),
        )
        object.__setattr__(self, "atom_parameters", rows)
        object.__setattr__(self, "solute_dielectric", solute)
        object.__setattr__(self, "solvent_dielectric", solvent)
        object.__setattr__(
            self,
            "minimum_pair_distance_angstrom",
            _finite_float(
                self.minimum_pair_distance_angstrom,
                name="minimum_pair_distance_angstrom",
                minimum=0.0,
                maximum=10.0,
            ),
        )
        object.__setattr__(self, "max_atoms", max_atoms)
        object.__setattr__(self, "metadata", _freeze_json(self.metadata))
        object.__setattr__(self, "scientifically_validated", False)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "algorithm_id": REFERENCE_FIXED_BORN_ALGORITHM_ID,
            "primary_reference_doi": REFERENCE_FIXED_BORN_PRIMARY_REFERENCE_DOI,
            "parameter_set_id": self.parameter_set_id,
            "parameter_set_version": self.parameter_set_version,
            "parameter_source_sha256": self.parameter_source_sha256,
            "topology_sha256": self.topology_sha256,
            "charge_parameter_fingerprint_sha256": (
                self.charge_parameter_fingerprint_sha256
            ),
            "atom_parameters": [row.to_dict() for row in self.atom_parameters],
            "solute_dielectric": self.solute_dielectric,
            "solvent_dielectric": self.solvent_dielectric,
            "minimum_pair_distance_angstrom": self.minimum_pair_distance_angstrom,
            "max_atoms": self.max_atoms,
            "max_pairs": self.max_atoms * (self.max_atoms - 1) // 2,
            "effective_radius_semantics": "caller_supplied_fixed_not_geometry_derived",
            "polar_pair_function": (
                "sqrt(r_ij^2 + alpha_i*alpha_j*"
                "exp(-r_ij^2/(4*alpha_i*alpha_j)))"
            ),
            "nonpolar_solvation": "not_implemented",
            "periodic_boundary_conditions": "not_supported",
            "metadata": _thaw_json(self.metadata),
            "scientifically_validated": False,
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _sha256(self.to_dict())


@dataclass(frozen=True, slots=True)
class FixedBornPolarSolvationEvaluation:
    term: EnergyTermResult
    component_energies: Mapping[str, torch.Tensor]
    pair_count: int
    parameter_fingerprint_sha256: str
    charge_parameter_fingerprint_sha256: str
    scientific_blockers: tuple[str, ...] = REFERENCE_FIXED_BORN_SCIENTIFIC_BLOCKERS
    schema_id: str = REFERENCE_FIXED_BORN_EVALUATION_SCHEMA_ID

    @property
    def scientifically_validated(self) -> bool:
        return False

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "algorithm_id": REFERENCE_FIXED_BORN_ALGORITHM_ID,
            "primary_reference_doi": REFERENCE_FIXED_BORN_PRIMARY_REFERENCE_DOI,
            "pair_count": self.pair_count,
            "parameter_fingerprint_sha256": self.parameter_fingerprint_sha256,
            "charge_parameter_fingerprint_sha256": (
                self.charge_parameter_fingerprint_sha256
            ),
            "energy_f64_sha256": _tensor_sha256(self.term.energy),
            "force_f64_sha256": _tensor_sha256(self.term.forces),
            "component_names": list(self.component_energies),
            "term_provenance_sha256": self.term.provenance_sha256,
            "scientifically_validated": False,
            "claim_safe": False,
            "scientific_blockers": list(self.scientific_blockers),
        }


def _validate_applicability(
    system: AllAtomSystem,
    forcefield_parameters: ReferenceForceFieldV2Parameters,
    solvation_parameters: FixedBornPolarSolvationParameters,
) -> None:
    if system.coordinates.device.type != "cpu" or system.coordinates.dtype != torch.float64:
        raise ReferenceFixedBornSolvationApplicabilityError(
            "fixed Born polar solvation requires CPU float64 coordinates"
        )
    if system.model_count != 1:
        raise ReferenceFixedBornSolvationApplicabilityError(
            "fixed Born polar solvation requires exactly one model"
        )
    if system.cell is not None:
        raise ReferenceFixedBornSolvationApplicabilityError(
            "fixed Born polar solvation does not support periodic cells"
        )
    if system.atom_count > solvation_parameters.max_atoms:
        raise ReferenceFixedBornSolvationApplicabilityError(
            "fixed Born atom capacity exceeded"
        )
    topology_sha256 = canonical_topology_sha256(system)
    if topology_sha256 != solvation_parameters.topology_sha256:
        raise ReferenceFixedBornSolvationApplicabilityError(
            "fixed Born topology identity mismatch"
        )
    if topology_sha256 != forcefield_parameters.topology_sha256:
        raise ReferenceFixedBornSolvationApplicabilityError(
            "forcefield topology identity mismatch"
        )
    if (
        solvation_parameters.charge_parameter_fingerprint_sha256
        != forcefield_parameters.fingerprint_sha256
    ):
        raise ReferenceFixedBornSolvationApplicabilityError(
            "fixed Born charge parameter fingerprint mismatch"
        )
    indices = tuple(row.atom_index for row in solvation_parameters.atom_parameters)
    if indices != tuple(range(system.atom_count)):
        raise ReferenceFixedBornSolvationApplicabilityError(
            "fixed Born atom parameter coverage must exactly match topology"
        )
    if not bool(torch.isfinite(system.coordinates).all().item()):
        raise ReferenceFixedBornSolvationApplicabilityError(
            "fixed Born coordinates must be finite"
        )


def evaluate_fixed_born_polar_solvation(
    system: AllAtomSystem,
    forcefield_parameters: ReferenceForceFieldV2Parameters,
    solvation_parameters: FixedBornPolarSolvationParameters,
) -> FixedBornPolarSolvationEvaluation:
    """Evaluate bounded nonperiodic polar GB transfer energy and exact forces."""

    if not isinstance(forcefield_parameters, ReferenceForceFieldV2Parameters):
        raise ReferenceFixedBornSolvationError(
            "forcefield_parameters must be ReferenceForceFieldV2Parameters"
        )
    if not isinstance(solvation_parameters, FixedBornPolarSolvationParameters):
        raise ReferenceFixedBornSolvationError(
            "solvation_parameters must be FixedBornPolarSolvationParameters"
        )
    _validate_applicability(system, forcefield_parameters, solvation_parameters)
    coordinates = system.coordinates.detach().clone().requires_grad_(True)
    atom_count = system.atom_count
    dtype = coordinates.dtype
    device = coordinates.device
    atom_map = forcefield_parameters.base_parameters.atom_parameter_map
    charges = torch.tensor(
        [atom_map[index].charge_e for index in range(atom_count)],
        dtype=dtype,
        device=device,
    )
    radii = torch.tensor(
        [row.effective_born_radius_angstrom for row in solvation_parameters.atom_parameters],
        dtype=dtype,
        device=device,
    )
    dielectric_factor = (
        1.0 / solvation_parameters.solute_dielectric
        - 1.0 / solvation_parameters.solvent_dielectric
    )
    coefficient = -0.5 * COULOMB_KCAL_ANGSTROM_PER_MOL_E2 * dielectric_factor
    zero = coordinates.sum(dim=(1, 2)) * 0.0
    self_energy = zero + coefficient * (charges.square() / radii).sum()
    pair_energy = zero.clone()
    pair_indices = torch.triu_indices(atom_count, atom_count, offset=1, device=device)
    pair_count = int(pair_indices.shape[1])
    if pair_count > REFERENCE_FIXED_BORN_MAX_PAIRS:
        raise ReferenceFixedBornSolvationApplicabilityError(
            "fixed Born pair capacity exceeded"
        )
    if pair_count:
        atom_i, atom_j = pair_indices[0], pair_indices[1]
        delta = coordinates[:, atom_i] - coordinates[:, atom_j]
        distance_squared = delta.square().sum(dim=-1)
        minimum_squared = solvation_parameters.minimum_pair_distance_angstrom**2
        if bool((distance_squared < minimum_squared).any().item()):
            raise ReferenceFixedBornSolvationApplicabilityError(
                "fixed Born pair is below minimum_pair_distance_angstrom"
            )
        radius_product = radii[atom_i] * radii[atom_j]
        pair_function = torch.sqrt(
            distance_squared
            + radius_product
            * torch.exp(-distance_squared / (4.0 * radius_product))
        )
        pair_values = 2.0 * charges[atom_i] * charges[atom_j] / pair_function
        pair_energy = pair_energy + coefficient * pair_values.sum(dim=-1)
    total = self_energy + pair_energy
    forces = -torch.autograd.grad(total.sum(), coordinates, create_graph=False)[0]
    components = MappingProxyType(
        {
            "fixed_born_self_polar": self_energy.detach(),
            "fixed_born_pair_polar": pair_energy.detach(),
        }
    )
    provenance = _sha256(
        {
            "schema_id": REFERENCE_FIXED_BORN_EVALUATION_SCHEMA_ID,
            "algorithm_id": REFERENCE_FIXED_BORN_ALGORITHM_ID,
            "source_system_sha256": canonical_system_sha256(system),
            "topology_sha256": canonical_topology_sha256(system),
            "charge_parameter_fingerprint_sha256": (
                forcefield_parameters.fingerprint_sha256
            ),
            "solvation_parameter_fingerprint_sha256": (
                solvation_parameters.fingerprint_sha256
            ),
            "pair_count": pair_count,
        }
    )
    term = EnergyTermResult(
        name="reference_fixed_born_polar_solvation",
        energy=total.detach(),
        forces=forces.detach(),
        energy_descriptor=QuantityDescriptor(
            name="fixed_born_polar_solvation_energy",
            unit="kcal/mol",
            semantics=(
                "nonperiodic_polar_dielectric_transfer_with_caller_supplied_"
                "fixed_effective_born_radii"
            ),
            physical_quantity=True,
            calibrated=False,
            reference_method=None,
        ),
        force_descriptor=QuantityDescriptor(
            name="fixed_born_polar_solvation_force",
            unit="kcal/mol/angstrom",
            semantics="negative_coordinate_gradient_of_fixed_radius_polar_gb_energy",
            physical_quantity=True,
            calibrated=False,
            reference_method=None,
        ),
        validated_for_composition=False,
        provenance_sha256=provenance,
    )
    return FixedBornPolarSolvationEvaluation(
        term=term,
        component_energies=components,
        pair_count=pair_count,
        parameter_fingerprint_sha256=solvation_parameters.fingerprint_sha256,
        charge_parameter_fingerprint_sha256=forcefield_parameters.fingerprint_sha256,
    )


@dataclass(frozen=True, slots=True)
class ReferenceForceFieldV2SolvatedEvaluation:
    term: EnergyTermResult
    component_energies: Mapping[str, torch.Tensor]
    forcefield_evaluation: ReferenceForceFieldV2Evaluation
    solvation_evaluation: FixedBornPolarSolvationEvaluation
    scientific_blockers: tuple[str, ...] = REFERENCE_FIXED_BORN_SCIENTIFIC_BLOCKERS
    schema_id: str = REFERENCE_FORCEFIELD_V2_SOLVATED_EVALUATION_SCHEMA_ID

    @property
    def constraints_satisfied(self) -> bool:
        return self.forcefield_evaluation.constraints_satisfied

    @property
    def scientifically_validated(self) -> bool:
        return False

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "forcefield_parameter_fingerprint_sha256": (
                self.forcefield_evaluation.parameter_fingerprint_sha256
            ),
            "solvation_parameter_fingerprint_sha256": (
                self.solvation_evaluation.parameter_fingerprint_sha256
            ),
            "energy_f64_sha256": _tensor_sha256(self.term.energy),
            "force_f64_sha256": _tensor_sha256(self.term.forces),
            "component_names": list(self.component_energies),
            "term_provenance_sha256": self.term.provenance_sha256,
            "constraints_satisfied": self.constraints_satisfied,
            "scientifically_validated": False,
            "claim_safe": False,
            "scientific_blockers": list(self.scientific_blockers),
        }


def evaluate_reference_force_field_v2_with_fixed_born(
    system: AllAtomSystem,
    neighbors: CompactNeighborList,
    forcefield_parameters: ReferenceForceFieldV2Parameters,
    solvation_parameters: FixedBornPolarSolvationParameters,
) -> ReferenceForceFieldV2SolvatedEvaluation:
    """Evaluate the provisional v2 force field plus fixed-radius polar GB."""

    forcefield = evaluate_reference_force_field_v2(
        system, neighbors, forcefield_parameters
    )
    solvation = evaluate_fixed_born_polar_solvation(
        system, forcefield_parameters, solvation_parameters
    )
    energy = forcefield.term.energy + solvation.term.energy
    forces = forcefield.term.forces + solvation.term.forces
    provenance = _sha256(
        {
            "schema_id": REFERENCE_FORCEFIELD_V2_SOLVATED_EVALUATION_SCHEMA_ID,
            "source_system_sha256": canonical_system_sha256(system),
            "forcefield_provenance_sha256": forcefield.term.provenance_sha256,
            "solvation_provenance_sha256": solvation.term.provenance_sha256,
        }
    )
    term = EnergyTermResult(
        name="reference_force_field_v2:fixed_born_polar_solvation",
        energy=energy,
        forces=forces,
        energy_descriptor=QuantityDescriptor(
            name="reference_force_field_v2_solvated_energy",
            unit="kcal/mol",
            semantics="v2_reference_energy_plus_fixed_effective_radius_polar_gb",
            physical_quantity=True,
            calibrated=False,
            reference_method=None,
        ),
        force_descriptor=QuantityDescriptor(
            name="reference_force_field_v2_solvated_force",
            unit="kcal/mol/angstrom",
            semantics="sum_of_v2_reference_and_fixed_radius_polar_gb_forces",
            physical_quantity=True,
            calibrated=False,
            reference_method=None,
        ),
        validated_for_composition=False,
        provenance_sha256=provenance,
    )
    return ReferenceForceFieldV2SolvatedEvaluation(
        term=term,
        component_energies=MappingProxyType(
            {**forcefield.component_energies, **solvation.component_energies}
        ),
        forcefield_evaluation=forcefield,
        solvation_evaluation=solvation,
    )


__all__ = [
    "REFERENCE_FIXED_BORN_ALGORITHM_ID",
    "REFERENCE_FIXED_BORN_EVALUATION_SCHEMA_ID",
    "REFERENCE_FIXED_BORN_MAX_ATOMS",
    "REFERENCE_FIXED_BORN_MAX_PAIRS",
    "REFERENCE_FIXED_BORN_PARAMETER_SCHEMA_ID",
    "REFERENCE_FIXED_BORN_PRIMARY_REFERENCE_DOI",
    "REFERENCE_FIXED_BORN_SCIENTIFIC_BLOCKERS",
    "REFERENCE_FORCEFIELD_V2_SOLVATED_EVALUATION_SCHEMA_ID",
    "FixedBornAtomParameter",
    "FixedBornPolarSolvationEvaluation",
    "FixedBornPolarSolvationParameters",
    "ReferenceFixedBornSolvationApplicabilityError",
    "ReferenceFixedBornSolvationError",
    "ReferenceForceFieldV2SolvatedEvaluation",
    "evaluate_fixed_born_polar_solvation",
    "evaluate_reference_force_field_v2_with_fixed_born",
]
