"""Bounded CPU float64 direct-Ewald electrostatics reference.

This module deliberately implements a small, explicit scientific reference:
one neutral coordinate model in a fully periodic orthorhombic cell, conducting
(tin-foil) boundary conditions, a finite real-space cutoff, and a finite
rectangular reciprocal lattice.  It is direct Ewald rather than PME and is not
scientifically validated or product-qualified.

The public force-field evaluator replaces the frozen v1 screened-Coulomb term;
it never adds Ewald on top of that term.  Excluded and scaled same-cell pairs
receive the corresponding ``erf(alpha*r)/r`` reciprocal correction.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from numbers import Real
import operator
from typing import Mapping

import torch

from betelgeuze_engine_v2.contracts import QuantityDescriptor
from betelgeuze_engine_v2.geometry import CompactNeighborList
from betelgeuze_engine_v2.molecular import (
    AllAtomSystem,
    canonical_system_sha256,
    canonical_topology_sha256,
    require_valid_all_atom_system,
)
from .composition import EnergyTermResult
from .reference_forcefield import (
    ReferencePhysicsEvaluation,
    evaluate_reference_force_field,
)
from .reference_parameters import (
    COULOMB_KCAL_ANGSTROM_PER_MOL_E2,
    ReferenceForceFieldParameters,
)


REFERENCE_EWALD_ALGORITHM_ID = (
    "cpu_float64_neutral_orthorhombic_direct_ewald_tinfoil/1.0.0"
)
REFERENCE_EWALD_CONFIG_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_ewald_config/1.0.0"
)
REFERENCE_EWALD_EVALUATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_ewald_evaluation/1.0.0"
)
REFERENCE_EWALD_MAX_ATOMS = 512
REFERENCE_EWALD_MAX_INDEX_PER_AXIS = 16
REFERENCE_EWALD_MAX_RECIPROCAL_VECTORS = 32_768
REFERENCE_EWALD_MAX_UNIQUE_PAIRS = (
    REFERENCE_EWALD_MAX_ATOMS * (REFERENCE_EWALD_MAX_ATOMS - 1) // 2
)
REFERENCE_EWALD_SCIENTIFIC_BLOCKERS = (
    "direct_ewald_reference_not_independently_validated",
    "ewald_parameter_convergence_evidence_missing",
    "neutral_orthorhombic_cpu_reference_only",
    "pme_not_implemented",
    "ewald_force_energy_validation_receipt_missing",
    "cross_host_reproducibility_missing",
    "reference_parameter_set_not_scientifically_validated",
)


class ReferenceEwaldError(ValueError):
    """The direct-Ewald request is malformed or outside its bounded domain."""


def _finite_float(
    value: object,
    *,
    name: str,
    positive: bool = False,
) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ReferenceEwaldError(f"{name} must be a finite real number")
    number = float(value)
    if not math.isfinite(number):
        raise ReferenceEwaldError(f"{name} must be finite")
    if positive and number <= 0.0:
        raise ReferenceEwaldError(f"{name} must be positive")
    return number


def _exact_int(
    value: object,
    *,
    name: str,
    minimum: int,
    maximum: int,
) -> int:
    if isinstance(value, bool):
        raise ReferenceEwaldError(f"{name} must be an integer")
    try:
        integer = int(operator.index(value))
    except TypeError:
        raise ReferenceEwaldError(f"{name} must be an integer") from None
    if not minimum <= integer <= maximum:
        raise ReferenceEwaldError(
            f"{name} must be in [{minimum},{maximum}]"
        )
    return integer


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise ReferenceEwaldError("Ewald payload is not canonical JSON") from exc


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _require_float_hex(value: object, *, name: str) -> float:
    if not isinstance(value, str):
        raise ReferenceEwaldError(f"{name} must be a hexadecimal float string")
    try:
        number = float.fromhex(value)
    except ValueError:
        raise ReferenceEwaldError(f"{name} is not a hexadecimal float") from None
    if not math.isfinite(number) or number.hex() != value:
        raise ReferenceEwaldError(f"{name} is not canonical finite binary64")
    return number


@dataclass(frozen=True)
class ReferenceEwaldConfig:
    """Immutable truncation and boundary policy for direct Ewald."""

    alpha_per_angstrom: float = 0.35
    reciprocal_max_indices: tuple[int, int, int] = (5, 5, 5)
    neutrality_tolerance_e: float = 1.0e-12
    boundary_condition: str = "conducting_tinfoil"
    net_charge_policy: str = "require_neutral_no_background"
    real_space_policy: str = "erfc_potential_shift_at_parameter_cutoff"
    reciprocal_lattice_policy: str = "full_symmetric_rectangular_integer_lattice"
    schema_id: str = REFERENCE_EWALD_CONFIG_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != REFERENCE_EWALD_CONFIG_SCHEMA_ID:
            raise ReferenceEwaldError("unsupported reference Ewald config schema")
        alpha = _finite_float(
            self.alpha_per_angstrom,
            name="alpha_per_angstrom",
            positive=True,
        )
        if alpha > 4.0:
            raise ReferenceEwaldError("alpha_per_angstrom exceeds bounded limit 4.0")
        object.__setattr__(self, "alpha_per_angstrom", alpha)
        tolerance = _finite_float(
            self.neutrality_tolerance_e,
            name="neutrality_tolerance_e",
            positive=True,
        )
        if tolerance > 1.0e-6:
            raise ReferenceEwaldError(
                "neutrality_tolerance_e exceeds bounded limit 1e-6"
            )
        object.__setattr__(self, "neutrality_tolerance_e", tolerance)
        try:
            values = tuple(self.reciprocal_max_indices)
        except TypeError:
            raise ReferenceEwaldError(
                "reciprocal_max_indices must be an iterable of integers"
            ) from None
        if len(values) != 3:
            raise ReferenceEwaldError(
                "reciprocal_max_indices must contain exactly three integers"
            )
        indices = tuple(
            _exact_int(
                value,
                name=f"reciprocal_max_indices[{axis}]",
                minimum=1,
                maximum=REFERENCE_EWALD_MAX_INDEX_PER_AXIS,
            )
            for axis, value in enumerate(values)
        )
        object.__setattr__(self, "reciprocal_max_indices", indices)
        if self.reciprocal_vector_count > REFERENCE_EWALD_MAX_RECIPROCAL_VECTORS:
            raise ReferenceEwaldError(
                "reciprocal lattice exceeds the bounded vector-count limit"
            )
        fixed = {
            "boundary_condition": "conducting_tinfoil",
            "net_charge_policy": "require_neutral_no_background",
            "real_space_policy": "erfc_potential_shift_at_parameter_cutoff",
            "reciprocal_lattice_policy": (
                "full_symmetric_rectangular_integer_lattice"
            ),
        }
        for name, expected in fixed.items():
            if getattr(self, name) != expected:
                raise ReferenceEwaldError(f"unsupported Ewald {name}")

    @property
    def reciprocal_vector_count(self) -> int:
        first, second, third = self.reciprocal_max_indices
        return (2 * first + 1) * (2 * second + 1) * (2 * third + 1) - 1

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "algorithm_id": REFERENCE_EWALD_ALGORITHM_ID,
            "alpha_per_angstrom_hex": self.alpha_per_angstrom.hex(),
            "reciprocal_max_indices": list(self.reciprocal_max_indices),
            "reciprocal_vector_count": self.reciprocal_vector_count,
            "neutrality_tolerance_e_hex": self.neutrality_tolerance_e.hex(),
            "boundary_condition": self.boundary_condition,
            "net_charge_policy": self.net_charge_policy,
            "real_space_policy": self.real_space_policy,
            "reciprocal_lattice_policy": self.reciprocal_lattice_policy,
        }

    @classmethod
    def from_dict(cls, value: object) -> "ReferenceEwaldConfig":
        expected_keys = {
            "schema_id",
            "algorithm_id",
            "alpha_per_angstrom_hex",
            "reciprocal_max_indices",
            "reciprocal_vector_count",
            "neutrality_tolerance_e_hex",
            "boundary_condition",
            "net_charge_policy",
            "real_space_policy",
            "reciprocal_lattice_policy",
        }
        if not isinstance(value, Mapping) or set(value) != expected_keys:
            raise ReferenceEwaldError("reference Ewald config payload is invalid")
        if value["algorithm_id"] != REFERENCE_EWALD_ALGORITHM_ID:
            raise ReferenceEwaldError("unsupported reference Ewald algorithm")
        raw_indices = value["reciprocal_max_indices"]
        if not isinstance(raw_indices, list) or len(raw_indices) != 3:
            raise ReferenceEwaldError(
                "reciprocal_max_indices payload must be a three-item list"
            )
        result = cls(
            alpha_per_angstrom=_require_float_hex(
                value["alpha_per_angstrom_hex"],
                name="alpha_per_angstrom_hex",
            ),
            reciprocal_max_indices=tuple(raw_indices),
            neutrality_tolerance_e=_require_float_hex(
                value["neutrality_tolerance_e_hex"],
                name="neutrality_tolerance_e_hex",
            ),
            boundary_condition=str(value["boundary_condition"]),
            net_charge_policy=str(value["net_charge_policy"]),
            real_space_policy=str(value["real_space_policy"]),
            reciprocal_lattice_policy=str(value["reciprocal_lattice_policy"]),
            schema_id=str(value["schema_id"]),
        )
        if value["reciprocal_vector_count"] != result.reciprocal_vector_count:
            raise ReferenceEwaldError("reciprocal vector count is inconsistent")
        if result.to_dict() != dict(value):
            raise ReferenceEwaldError("reference Ewald config is not canonical")
        return result

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())


@dataclass(frozen=True)
class ReferenceEwaldEvaluation:
    """Full v1 force-field result after exact Coulomb-term replacement."""

    term: EnergyTermResult
    electrostatics_term: EnergyTermResult
    component_energies: dict[str, torch.Tensor]
    parameter_fingerprint_sha256: str
    config_fingerprint_sha256: str
    total_charge_e: float
    real_pair_count: int
    reciprocal_vector_count: int
    scientific_blockers: tuple[str, ...] = REFERENCE_EWALD_SCIENTIFIC_BLOCKERS
    schema_id: str = REFERENCE_EWALD_EVALUATION_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != REFERENCE_EWALD_EVALUATION_SCHEMA_ID:
            raise ReferenceEwaldError("unsupported reference Ewald evaluation schema")
        for name in ("parameter_fingerprint_sha256", "config_fingerprint_sha256"):
            digest = getattr(self, name)
            if (
                not isinstance(digest, str)
                or len(digest) != 64
                or any(char not in "0123456789abcdef" for char in digest)
            ):
                raise ReferenceEwaldError(f"{name} must be a lowercase SHA-256 digest")
        object.__setattr__(
            self,
            "total_charge_e",
            _finite_float(self.total_charge_e, name="total_charge_e"),
        )
        for name, maximum in (
            ("real_pair_count", REFERENCE_EWALD_MAX_UNIQUE_PAIRS),
            ("reciprocal_vector_count", REFERENCE_EWALD_MAX_RECIPROCAL_VECTORS),
        ):
            object.__setattr__(
                self,
                name,
                _exact_int(
                    getattr(self, name),
                    name=name,
                    minimum=0,
                    maximum=maximum,
                ),
            )
        if tuple(self.scientific_blockers) != REFERENCE_EWALD_SCIENTIFIC_BLOCKERS:
            raise ReferenceEwaldError("Ewald scientific blockers cannot be promoted")

    @property
    def execution_complete(self) -> bool:
        return True

    @property
    def scientifically_validated(self) -> bool:
        return False

    @property
    def claim_safe(self) -> bool:
        return False

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "algorithm_id": REFERENCE_EWALD_ALGORITHM_ID,
            "execution_complete": True,
            "scientifically_validated": False,
            "validated_for_composition": False,
            "component_energy_kcal_per_mol_hex": {
                name: float(value.reshape(-1)[0].item()).hex()
                for name, value in sorted(self.component_energies.items())
            },
            "parameter_fingerprint_sha256": self.parameter_fingerprint_sha256,
            "config_fingerprint_sha256": self.config_fingerprint_sha256,
            "total_charge_e_hex": self.total_charge_e.hex(),
            "real_pair_count": self.real_pair_count,
            "reciprocal_vector_count": self.reciprocal_vector_count,
            "scientific_blockers": list(self.scientific_blockers),
            "claim_safe": False,
        }


def _switch(distance: torch.Tensor, start: float, cutoff: float) -> torch.Tensor:
    """Exact local copy of the frozen v1 screened-Coulomb switch."""

    x = ((distance - start) / (cutoff - start)).clamp(0.0, 1.0)
    smooth = 1.0 - 10.0 * x.pow(3) + 15.0 * x.pow(4) - 6.0 * x.pow(5)
    return torch.where(
        distance <= start,
        torch.ones_like(distance),
        torch.where(distance < cutoff, smooth, torch.zeros_like(distance)),
    )


def _minimum_image(
    delta: torch.Tensor,
    lengths: torch.Tensor,
) -> torch.Tensor:
    return delta - torch.round(delta / lengths.view(1, 1, 3)) * lengths.view(
        1, 1, 3
    )


def _pair_scales(
    parameters: ReferenceForceFieldParameters,
    source: torch.Tensor,
    target: torch.Tensor,
    *,
    dtype: torch.dtype,
    device: torch.device,
) -> tuple[torch.Tensor, torch.Tensor]:
    atom_map = parameters.atom_parameter_map
    scaling_map = parameters.pair_scaling_map
    excluded = set(parameters.excluded_pairs)
    charge_products: list[float] = []
    electrostatic_scales: list[float] = []
    for atom_i, atom_j in zip(
        source.detach().cpu().tolist(),
        target.detach().cpu().tolist(),
    ):
        pair = tuple(sorted((int(atom_i), int(atom_j))))
        charge_products.append(
            atom_map[int(atom_i)].charge_e * atom_map[int(atom_j)].charge_e
        )
        if pair in excluded:
            electrostatic_scales.append(0.0)
        elif pair in scaling_map:
            electrostatic_scales.append(
                scaling_map[pair].electrostatic_scale
            )
        else:
            electrostatic_scales.append(1.0)
    return (
        torch.tensor(charge_products, dtype=dtype, device=device),
        torch.tensor(electrostatic_scales, dtype=dtype, device=device),
    )


def _screened_coulomb_being_replaced(
    coordinates: torch.Tensor,
    system: AllAtomSystem,
    neighbors: CompactNeighborList,
    parameters: ReferenceForceFieldParameters,
) -> torch.Tensor:
    zero = coordinates.sum(dim=(1, 2)) * 0.0
    upper = neighbors.upper_mask()
    batch_index, source_index, slot = torch.nonzero(upper, as_tuple=True)
    if not int(batch_index.numel()):
        return zero
    target_index = neighbors.indices[batch_index, source_index, slot]
    raw = coordinates[batch_index, source_index] - coordinates[
        batch_index, target_index
    ]
    shifts = neighbors.image_shifts[batch_index, source_index, slot].to(
        dtype=coordinates.dtype,
        device=coordinates.device,
    )
    vectors = system.cell.vectors.to(
        dtype=coordinates.dtype,
        device=coordinates.device,
    )
    raw = raw - shifts @ vectors
    distance = torch.linalg.vector_norm(raw, dim=-1)
    charge_product, electrostatic_scale = _pair_scales(
        parameters,
        source_index,
        target_index,
        dtype=coordinates.dtype,
        device=coordinates.device,
    )
    pair_energy = (
        COULOMB_KCAL_ANGSTROM_PER_MOL_E2
        * charge_product
        * torch.exp(-parameters.screening_kappa_per_angstrom * distance)
        / (parameters.dielectric * distance)
        * electrostatic_scale
    )
    pair_energy = pair_energy * _switch(
        distance,
        parameters.switch_start_angstrom,
        parameters.cutoff_angstrom,
    )
    return zero.scatter_add(0, batch_index, pair_energy)


def _reciprocal_integer_vectors(
    config: ReferenceEwaldConfig,
    *,
    device: torch.device,
) -> torch.Tensor:
    limits = config.reciprocal_max_indices
    values = [
        (first, second, third)
        for first in range(-limits[0], limits[0] + 1)
        for second in range(-limits[1], limits[1] + 1)
        for third in range(-limits[2], limits[2] + 1)
        if (first, second, third) != (0, 0, 0)
    ]
    return torch.tensor(values, dtype=torch.float64, device=device)


def _require_applicability(
    system: AllAtomSystem,
    parameters: ReferenceForceFieldParameters,
    config: ReferenceEwaldConfig,
) -> tuple[torch.Tensor, torch.Tensor, float]:
    if not isinstance(config, ReferenceEwaldConfig):
        raise ReferenceEwaldError("config must be ReferenceEwaldConfig")
    if not isinstance(system, AllAtomSystem):
        raise ReferenceEwaldError("system must be AllAtomSystem")
    if system.atom_count > REFERENCE_EWALD_MAX_ATOMS:
        raise ReferenceEwaldError("atom count exceeds the bounded Ewald limit")
    try:
        require_valid_all_atom_system(system)
    except ValueError as exc:
        raise ReferenceEwaldError(
            "reference Ewald all-atom system validation failed"
        ) from exc
    if system.model_count != 1:
        raise ReferenceEwaldError("reference Ewald requires exactly one model")
    if system.coordinate_unit != "angstrom":
        raise ReferenceEwaldError("reference Ewald requires angstrom coordinates")
    if (
        system.coordinates.dtype != torch.float64
        or system.coordinates.device.type != "cpu"
    ):
        raise ReferenceEwaldError("reference Ewald requires CPU float64 coordinates")
    if system.cell is None or system.cell.periodic != (True, True, True):
        raise ReferenceEwaldError(
            "reference Ewald requires a fully periodic three-dimensional cell"
        )
    if (
        system.cell.vectors.dtype != torch.float64
        or system.cell.vectors.device.type != "cpu"
    ):
        raise ReferenceEwaldError("reference Ewald requires a CPU float64 cell")
    try:
        lengths = system.cell.orthorhombic_lengths().to(
            dtype=torch.float64,
            device="cpu",
        )
    except ValueError as exc:
        raise ReferenceEwaldError(
            "reference Ewald supports orthorhombic cells only"
        ) from exc
    if not bool(torch.isfinite(lengths).all().item()) or bool(
        (lengths <= 0.0).any().item()
    ):
        raise ReferenceEwaldError("cell lengths must be finite and positive")
    if parameters.cutoff_angstrom >= 0.5 * float(lengths.min().item()):
        raise ReferenceEwaldError(
            "real-space cutoff must be below half the shortest box length"
        )
    if parameters.screening_kappa_per_angstrom != 0.0:
        raise ReferenceEwaldError(
            "Ewald replacement requires zero screened-Coulomb kappa"
        )
    atom_map = parameters.atom_parameter_map
    if set(atom_map) != set(range(system.atom_count)):
        raise ReferenceEwaldError("Ewald charges do not cover every atom")
    charge_values = [atom_map[index].charge_e for index in range(system.atom_count)]
    total_charge = math.fsum(charge_values)
    if abs(total_charge) > config.neutrality_tolerance_e:
        raise ReferenceEwaldError(
            "net charge exceeds require-neutral Ewald tolerance; no background correction is defined"
        )
    charges = torch.tensor(charge_values, dtype=torch.float64, device="cpu")
    return lengths, charges, total_charge


def _ewald_components(
    coordinates: torch.Tensor,
    system: AllAtomSystem,
    parameters: ReferenceForceFieldParameters,
    config: ReferenceEwaldConfig,
    lengths: torch.Tensor,
    charges: torch.Tensor,
) -> tuple[dict[str, torch.Tensor], int]:
    zero = coordinates.sum(dim=(1, 2)) * 0.0
    indices = torch.triu_indices(
        system.atom_count,
        system.atom_count,
        offset=1,
        device=coordinates.device,
    )
    source, target = indices[0], indices[1]
    real = zero.clone()
    pair_correction = zero.clone()
    real_pair_count = 0
    if int(source.numel()):
        displacement = _minimum_image(
            coordinates[:, source] - coordinates[:, target],
            lengths,
        )
        distance = torch.linalg.vector_norm(displacement, dim=-1).reshape(-1)
        minimum = parameters.applicability_domain.minimum_pair_distance_angstrom
        if bool((distance < minimum).any().item()):
            raise ReferenceEwaldError(
                "Ewald pair is below minimum_pair_distance_angstrom"
            )
        charge_product, scale = _pair_scales(
            parameters,
            source,
            target,
            dtype=coordinates.dtype,
            device=coordinates.device,
        )
        within = distance < parameters.cutoff_angstrom
        real_pair_count = int(within.sum().detach().cpu().item())
        cutoff = torch.tensor(
            parameters.cutoff_angstrom,
            dtype=coordinates.dtype,
            device=coordinates.device,
        )
        alpha = config.alpha_per_angstrom
        shifted_kernel = (
            torch.erfc(alpha * distance) / distance
            - torch.erfc(alpha * cutoff) / cutoff
        )
        pair_real = torch.where(
            within,
            charge_product * scale * shifted_kernel,
            torch.zeros_like(distance),
        )
        real = zero + pair_real.sum().reshape(1)
        # The reciprocal sum includes the same-cell ``erf(alpha*r)/r`` pair.
        # Remove or scale that piece while preserving periodic-image terms.
        pair_correction = zero + (
            charge_product
            * (scale - 1.0)
            * torch.erf(alpha * distance)
            / distance
        ).sum().reshape(1)

    integer_vectors = _reciprocal_integer_vectors(
        config,
        device=coordinates.device,
    )
    reciprocal_vectors = 2.0 * math.pi * integer_vectors / lengths.view(1, 3)
    reciprocal_norm2 = reciprocal_vectors.square().sum(dim=1)
    weights = torch.exp(
        -reciprocal_norm2 / (4.0 * config.alpha_per_angstrom**2)
    ) / reciprocal_norm2
    wrapped = coordinates - torch.floor(
        coordinates / lengths.view(1, 1, 3)
    ) * lengths.view(1, 1, 3)
    phase = wrapped[0] @ reciprocal_vectors.transpose(0, 1)
    structure_real = (charges.view(-1, 1) * torch.cos(phase)).sum(dim=0)
    structure_imag = (charges.view(-1, 1) * torch.sin(phase)).sum(dim=0)
    volume = lengths.prod()
    # Every nonzero integer vector, including both +k and -k, is present;
    # consequently the full-lattice energy prefactor is 2*pi/V.
    reciprocal = zero + (
        (2.0 * math.pi / volume)
        * (
            weights
            * (structure_real.square() + structure_imag.square())
        ).sum()
    ).reshape(1)
    self_energy = zero + (
        -config.alpha_per_angstrom
        / math.sqrt(math.pi)
        * charges.square().sum()
    ).reshape(1)
    factor = COULOMB_KCAL_ANGSTROM_PER_MOL_E2 / parameters.dielectric
    return (
        {
            "ewald_real": real * factor,
            "ewald_reciprocal": reciprocal * factor,
            "ewald_self": self_energy * factor,
            "ewald_pair_scaling_correction": pair_correction * factor,
        },
        real_pair_count,
    )


def _provenance_sha256(
    *,
    scope: str,
    system: AllAtomSystem,
    neighbors: CompactNeighborList,
    parameters: ReferenceForceFieldParameters,
    config: ReferenceEwaldConfig,
) -> str:
    return _canonical_sha256(
        {
            "algorithm_id": REFERENCE_EWALD_ALGORITHM_ID,
            "scope": scope,
            "system_sha256": canonical_system_sha256(system),
            "topology_sha256": canonical_topology_sha256(system),
            "parameter_fingerprint_sha256": parameters.fingerprint_sha256,
            "config_fingerprint_sha256": config.fingerprint_sha256,
            "neighbor_schema": neighbors.diagnostics.schema_version,
            "neighbor_cutoff_angstrom_hex": float(
                neighbors.diagnostics.cutoff_angstrom
            ).hex(),
            "directed_pair_count": neighbors.diagnostics.directed_pair_count,
        }
    )


def evaluate_reference_force_field_with_ewald(
    system: AllAtomSystem,
    neighbors: CompactNeighborList,
    parameters: ReferenceForceFieldParameters,
    config: ReferenceEwaldConfig,
) -> ReferenceEwaldEvaluation:
    """Replace v1 screened Coulomb with bounded direct-Ewald electrostatics."""

    if not isinstance(parameters, ReferenceForceFieldParameters):
        raise ReferenceEwaldError(
            "parameters must be ReferenceForceFieldParameters"
        )
    lengths, charges, total_charge = _require_applicability(
        system,
        parameters,
        config,
    )
    base: ReferencePhysicsEvaluation = evaluate_reference_force_field(
        system,
        neighbors,
        parameters,
    )
    coordinates = system.coordinates.detach().clone().requires_grad_(True)
    components, real_pair_count = _ewald_components(
        coordinates,
        system,
        parameters,
        config,
        lengths,
        charges,
    )
    ewald_energy = sum(components.values(), coordinates.sum(dim=(1, 2)) * 0.0)
    old_energy = _screened_coulomb_being_replaced(
        coordinates,
        system,
        neighbors,
        parameters,
    )
    expected_old = base.component_energies["screened_coulomb"]
    if not torch.equal(old_energy.detach(), expected_old):
        raise ReferenceEwaldError(
            "screened-Coulomb replacement identity does not match frozen v1 evaluation"
        )
    ewald_gradient = torch.autograd.grad(
        ewald_energy.sum(),
        coordinates,
        retain_graph=True,
        create_graph=False,
    )[0]
    old_gradient = torch.autograd.grad(
        old_energy.sum(),
        coordinates,
        create_graph=False,
    )[0]
    ewald_forces = -ewald_gradient
    old_forces = -old_gradient
    total_energy = base.term.energy - expected_old + ewald_energy.detach()
    total_forces = base.term.forces + ewald_forces.detach() - old_forces.detach()
    if not bool(torch.isfinite(total_energy).all().item()) or not bool(
        torch.isfinite(total_forces).all().item()
    ):
        raise ReferenceEwaldError("Ewald evaluation produced non-finite values")

    electrostatic_provenance = _provenance_sha256(
        scope="direct_ewald_electrostatics",
        system=system,
        neighbors=neighbors,
        parameters=parameters,
        config=config,
    )
    full_provenance = _provenance_sha256(
        scope="force_field_with_screened_coulomb_replaced_by_direct_ewald",
        system=system,
        neighbors=neighbors,
        parameters=parameters,
        config=config,
    )
    electrostatics_term = EnergyTermResult(
        name="reference_direct_ewald_electrostatics",
        energy=ewald_energy.detach(),
        forces=ewald_forces.detach(),
        energy_descriptor=QuantityDescriptor(
            name="reference_direct_ewald_energy",
            unit="kcal/mol",
            semantics=(
                "neutral_orthorhombic_direct_ewald_real_reciprocal_self_"
                "pair_scaling_correction"
            ),
            physical_quantity=True,
            calibrated=False,
            reference_method=None,
        ),
        force_descriptor=QuantityDescriptor(
            name="reference_direct_ewald_force",
            unit="kcal/mol/angstrom",
            semantics="negative_coordinate_gradient_of_direct_ewald_energy",
            physical_quantity=True,
            calibrated=False,
            reference_method=None,
        ),
        validated_for_composition=False,
        provenance_sha256=electrostatic_provenance,
    )
    term = EnergyTermResult(
        name=(
            f"reference_force_field_direct_ewald:"
            f"{parameters.parameter_set_id}/{parameters.parameter_set_version}"
        ),
        energy=total_energy.detach(),
        forces=total_forces.detach(),
        energy_descriptor=QuantityDescriptor(
            name="reference_force_field_direct_ewald_energy",
            unit="kcal/mol",
            semantics=(
                "explicit_bond_angle_torsion_lj_neutral_direct_ewald_total"
            ),
            physical_quantity=True,
            calibrated=False,
            reference_method=None,
        ),
        force_descriptor=QuantityDescriptor(
            name="reference_force_field_direct_ewald_force",
            unit="kcal/mol/angstrom",
            semantics=(
                "negative_coordinate_gradient_after_exact_screened_coulomb_"
                "replacement_by_direct_ewald"
            ),
            physical_quantity=True,
            calibrated=False,
            reference_method=None,
        ),
        validated_for_composition=False,
        provenance_sha256=full_provenance,
    )
    all_components = {
        name: value.detach()
        for name, value in base.component_energies.items()
        if name != "screened_coulomb"
    }
    all_components.update(
        {name: value.detach() for name, value in components.items()}
    )
    return ReferenceEwaldEvaluation(
        term=term,
        electrostatics_term=electrostatics_term,
        component_energies=all_components,
        parameter_fingerprint_sha256=parameters.fingerprint_sha256,
        config_fingerprint_sha256=config.fingerprint_sha256,
        total_charge_e=total_charge,
        real_pair_count=real_pair_count,
        reciprocal_vector_count=config.reciprocal_vector_count,
    )


__all__ = [
    "REFERENCE_EWALD_ALGORITHM_ID",
    "REFERENCE_EWALD_CONFIG_SCHEMA_ID",
    "REFERENCE_EWALD_EVALUATION_SCHEMA_ID",
    "REFERENCE_EWALD_MAX_ATOMS",
    "REFERENCE_EWALD_MAX_INDEX_PER_AXIS",
    "REFERENCE_EWALD_MAX_RECIPROCAL_VECTORS",
    "REFERENCE_EWALD_MAX_UNIQUE_PAIRS",
    "REFERENCE_EWALD_SCIENTIFIC_BLOCKERS",
    "ReferenceEwaldConfig",
    "ReferenceEwaldError",
    "ReferenceEwaldEvaluation",
    "evaluate_reference_force_field_with_ewald",
]
