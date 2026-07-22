"""Bounded CPU float64 velocity-Verlet NVE reference integration.

The implementation rebuilds the compact neighbor list at every force
evaluation, supports either non-periodic coordinates or a fully periodic
orthorhombic cell, optionally applies canonical-pair inverse-mass SHAKE/RATTLE,
optionally replaces the short-range screened Coulomb term with the bounded
neutral direct-Ewald reference, and retains a binary64
state/energy/constraint trajectory chain plus a canonical restart checkpoint.
It is an implementation reference, not evidence of force-field accuracy,
constraint assignment, Ewald convergence, cross-host parity, or an equilibrium
MD product.
"""

from __future__ import annotations

from base64 import b64decode, b64encode
import binascii
from dataclasses import dataclass, replace
import hashlib
import json
import math
from numbers import Real
import struct
from typing import Mapping

import torch

from betelgeuze_engine_v2.geometry import (
    MAX_COMPACT_ATOMS_PER_CELL,
    MAX_COMPACT_NEIGHBORS,
    RadiusGraphConfig,
    build_compact_radius_graph,
)
from betelgeuze_engine_v2.molecular import (
    AllAtomSystem,
    canonical_system_sha256,
    canonical_topology_sha256,
    require_valid_all_atom_system,
)
from .reference_ewald import (
    ReferenceEwaldConfig,
    ReferenceEwaldError,
    evaluate_reference_force_field_with_ewald,
)
from .reference_forcefield import evaluate_reference_force_field
from .reference_parameters import ReferenceForceFieldParameters
from .reference_shake_rattle import (
    ReferenceSHAKERATTLEConfig,
    ReferenceSHAKERATTLEError,
    minimum_image_displacement,
    observe_reference_position_constraints,
    observe_reference_velocity_constraints,
    project_reference_rattle_velocities,
    project_reference_shake_positions,
    validate_reference_shake_rattle_inputs,
)


REFERENCE_NVE_ALGORITHM_ID = (
    "cpu_float64_velocity_verlet_optional_shake_rattle_direct_ewald/1.2.0"
)
REFERENCE_NVE_CONFIG_SCHEMA_ID = "betelgeuze.engine_v2_reference_nve_config/1.1.0"
REFERENCE_NVE_FRAME_SCHEMA_ID = "betelgeuze.engine_v2_reference_nve_frame/1.2.0"
REFERENCE_NVE_CHECKPOINT_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_nve_checkpoint/1.2.0"
)
REFERENCE_NVE_RESULT_SCHEMA_ID = "betelgeuze.engine_v2_reference_nve_result/1.2.0"
REFERENCE_NVE_TRAJECTORY_CHAIN_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_nve_trajectory_chain/1.2.0"
)

# 1 kcal mol^-1 A^-1 divided by 1 Da equals 418.4 A ps^-2.
FORCE_KCAL_PER_MOL_ANGSTROM_TO_ACCELERATION_ANGSTROM_PER_PS2_PER_DA = 418.4
MAX_REFERENCE_NVE_STEPS_PER_CALL = 1_000_000
MAX_REFERENCE_NVE_RETAINED_FRAMES = 10_001
MAX_REFERENCE_NVE_CHECKPOINT_BYTES = 128 * 1024 * 1024

REFERENCE_NVE_SCIENTIFIC_BLOCKERS = (
    "caller_supplied_parameter_values_not_independently_reviewed",
    "caller_supplied_solute_mass_assignment_not_independently_reviewed",
    "reference_force_field_not_scientifically_validated",
    "caller_supplied_nve_drift_thresholds_not_independently_reviewed",
    "independent_nve_drift_acceptance_evidence_missing",
    "cross_host_reproducibility_missing",
    "cpu_gpu_parity_evidence_missing",
    "caller_supplied_constraints_not_independently_reviewed",
    "shake_rattle_reference_path_not_independently_validated",
    "constraint_assignment_and_hydrogen_bond_selection_not_implemented",
    "direct_ewald_reference_path_not_independently_validated",
    "direct_ewald_convergence_acceptance_evidence_missing",
    "pme_not_implemented",
    "net_charge_background_and_triclinic_ewald_not_supported",
    "explicit_solvent_and_ion_preparation_not_independently_validated",
    "thermostat_and_barostat_not_implemented",
    "nvt_npt_ensemble_statistics_missing",
    "triclinic_periodic_cells_not_supported",
    "product_integration_not_qualified",
)


class ReferenceNVEError(ValueError):
    """The reference NVE request or restart state failed closed."""


def _finite_float(
    value: object,
    *,
    name: str,
    positive: bool = False,
    nonnegative: bool = False,
) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ReferenceNVEError(f"{name} must be a finite real number")
    number = float(value)
    if not math.isfinite(number):
        raise ReferenceNVEError(f"{name} must be finite")
    if positive and number <= 0.0:
        raise ReferenceNVEError(f"{name} must be positive")
    if nonnegative and number < 0.0:
        raise ReferenceNVEError(f"{name} must be non-negative")
    return number


def _exact_int(
    value: object,
    *,
    name: str,
    minimum: int = 0,
    maximum: int | None = None,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ReferenceNVEError(f"{name} must be an integer")
    integer = int(value)
    if integer < minimum or (maximum is not None and integer > maximum):
        upper = "" if maximum is None else f" and at most {maximum}"
        raise ReferenceNVEError(f"{name} must be at least {minimum}{upper}")
    return integer


def _digest(value: object, *, name: str) -> str:
    if not isinstance(value, str):
        raise ReferenceNVEError(f"{name} must be a SHA-256 string")
    digest = value.strip().lower()
    if len(digest) != 64 or any(
        character not in "0123456789abcdef" for character in digest
    ):
        raise ReferenceNVEError(f"{name} must be a lowercase SHA-256")
    return digest


def _canonical_bytes(payload: object) -> bytes:
    return (
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
        + b"\n"
    )


def _canonical_sha256(payload: object) -> str:
    return hashlib.sha256(_canonical_bytes(payload)[:-1]).hexdigest()


def _require_float_hex(value: object, *, name: str) -> float:
    if not isinstance(value, str):
        raise ReferenceNVEError(f"{name} must be canonical binary64 hex")
    try:
        number = float.fromhex(value)
    except ValueError as exc:
        raise ReferenceNVEError(f"{name} must be canonical binary64 hex") from exc
    if not math.isfinite(number) or number.hex() != value:
        raise ReferenceNVEError(f"{name} must be canonical finite binary64 hex")
    return number


def _tensor_payload(value: torch.Tensor, *, name: str) -> dict[str, object]:
    if (
        not isinstance(value, torch.Tensor)
        or value.dtype != torch.float64
        or value.device.type != "cpu"
        or value.ndim != 3
        or value.shape[0] != 1
        or value.shape[2] != 3
        or not bool(torch.isfinite(value).all().item())
    ):
        raise ReferenceNVEError(f"{name} must be finite CPU float64 [1,N,3]")
    rows = value.detach().contiguous().reshape(-1).tolist()
    raw = bytearray(8 * len(rows))
    for index, item in enumerate(rows):
        struct.pack_into("<d", raw, index * 8, float(item))
    binary = bytes(raw)
    return {
        "shape": [int(size) for size in value.shape],
        "dtype": "float64-le",
        "data_base64": b64encode(binary).decode("ascii"),
        "data_sha256": hashlib.sha256(binary).hexdigest(),
    }


def _tensor_from_payload(value: object, *, name: str) -> torch.Tensor:
    if not isinstance(value, Mapping) or set(value) != {
        "shape",
        "dtype",
        "data_base64",
        "data_sha256",
    }:
        raise ReferenceNVEError(f"{name} tensor payload shape is invalid")
    shape_raw = value["shape"]
    if (
        not isinstance(shape_raw, list)
        or len(shape_raw) != 3
        or any(isinstance(item, bool) or not isinstance(item, int) for item in shape_raw)
    ):
        raise ReferenceNVEError(f"{name} tensor shape is invalid")
    shape = tuple(int(item) for item in shape_raw)
    if shape[0] != 1 or shape[1] < 1 or shape[2] != 3:
        raise ReferenceNVEError(f"{name} tensor must have shape [1,N,3]")
    if value["dtype"] != "float64-le":
        raise ReferenceNVEError(f"{name} tensor dtype is invalid")
    encoded = value["data_base64"]
    if not isinstance(encoded, str):
        raise ReferenceNVEError(f"{name} tensor base64 must be a string")
    try:
        raw = b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ReferenceNVEError(f"{name} tensor base64 is invalid") from exc
    if b64encode(raw).decode("ascii") != encoded:
        raise ReferenceNVEError(f"{name} tensor base64 is not canonical")
    if len(raw) != math.prod(shape) * 8:
        raise ReferenceNVEError(f"{name} tensor byte length is invalid")
    if hashlib.sha256(raw).hexdigest() != _digest(
        value["data_sha256"],
        name=f"{name} data_sha256",
    ):
        raise ReferenceNVEError(f"{name} tensor digest mismatch")
    values = [item[0] for item in struct.iter_unpack("<d", raw)]
    tensor = torch.tensor(values, dtype=torch.float64).reshape(shape)
    if not bool(torch.isfinite(tensor).all().item()):
        raise ReferenceNVEError(f"{name} tensor contains non-finite values")
    if _tensor_payload(tensor, name=name) != dict(value):
        raise ReferenceNVEError(f"{name} tensor payload is not canonical")
    return tensor


@dataclass(frozen=True)
class ReferenceNVEConfig:
    timestep_ps: float = 0.001
    trajectory_stride: int = 1
    max_neighbors: int = 256
    max_atoms_per_cell: int = 256
    ewald_config: ReferenceEwaldConfig | None = None
    schema_id: str = REFERENCE_NVE_CONFIG_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != REFERENCE_NVE_CONFIG_SCHEMA_ID:
            raise ReferenceNVEError("unsupported reference NVE config schema")
        timestep = _finite_float(self.timestep_ps, name="timestep_ps", positive=True)
        if timestep > 0.1:
            raise ReferenceNVEError("timestep_ps exceeds the bounded limit 0.1 ps")
        object.__setattr__(self, "timestep_ps", timestep)
        object.__setattr__(
            self,
            "trajectory_stride",
            _exact_int(
                self.trajectory_stride,
                name="trajectory_stride",
                minimum=1,
                maximum=MAX_REFERENCE_NVE_STEPS_PER_CALL,
            ),
        )
        object.__setattr__(
            self,
            "max_neighbors",
            _exact_int(
                self.max_neighbors,
                name="max_neighbors",
                minimum=1,
                maximum=MAX_COMPACT_NEIGHBORS,
            ),
        )
        object.__setattr__(
            self,
            "max_atoms_per_cell",
            _exact_int(
                self.max_atoms_per_cell,
                name="max_atoms_per_cell",
                minimum=1,
                maximum=MAX_COMPACT_ATOMS_PER_CELL,
            ),
        )
        if self.ewald_config is not None and not isinstance(
            self.ewald_config,
            ReferenceEwaldConfig,
        ):
            raise ReferenceNVEError(
                "ewald_config must be ReferenceEwaldConfig or None"
            )

    @property
    def electrostatics_mode(self) -> str:
        if self.ewald_config is None:
            return "screened_coulomb_v1"
        return "neutral_direct_ewald_v1"

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "timestep_ps_hex": self.timestep_ps.hex(),
            "trajectory_stride": self.trajectory_stride,
            "max_neighbors": self.max_neighbors,
            "max_atoms_per_cell": self.max_atoms_per_cell,
            "electrostatics_mode": self.electrostatics_mode,
            "ewald_config": (
                None if self.ewald_config is None else self.ewald_config.to_dict()
            ),
            "neighbor_rebuild_policy": "every_force_evaluation",
            "periodic_policy": "none_or_full_3d_orthorhombic",
            "coordinate_wrapping": "zero_to_box_length_each_step",
        }

    @classmethod
    def from_dict(cls, value: object) -> "ReferenceNVEConfig":
        if not isinstance(value, Mapping) or set(value) != {
            "schema_id",
            "timestep_ps_hex",
            "trajectory_stride",
            "max_neighbors",
            "max_atoms_per_cell",
            "electrostatics_mode",
            "ewald_config",
            "neighbor_rebuild_policy",
            "periodic_policy",
            "coordinate_wrapping",
        }:
            raise ReferenceNVEError("reference NVE config payload is invalid")
        if value["neighbor_rebuild_policy"] != "every_force_evaluation":
            raise ReferenceNVEError("unsupported NVE neighbor rebuild policy")
        if value["periodic_policy"] != "none_or_full_3d_orthorhombic":
            raise ReferenceNVEError("unsupported NVE periodic policy")
        if value["coordinate_wrapping"] != "zero_to_box_length_each_step":
            raise ReferenceNVEError("unsupported NVE coordinate wrapping policy")
        mode = value["electrostatics_mode"]
        ewald_payload = value["ewald_config"]
        if mode == "screened_coulomb_v1":
            if ewald_payload is not None:
                raise ReferenceNVEError(
                    "screened-Coulomb NVE mode cannot carry an Ewald config"
                )
            ewald_config = None
        elif mode == "neutral_direct_ewald_v1":
            try:
                ewald_config = ReferenceEwaldConfig.from_dict(ewald_payload)
            except ReferenceEwaldError as exc:
                raise ReferenceNVEError("NVE Ewald config payload is invalid") from exc
        else:
            raise ReferenceNVEError("unsupported NVE electrostatics mode")
        result = cls(
            timestep_ps=_require_float_hex(
                value["timestep_ps_hex"],
                name="timestep_ps_hex",
            ),
            trajectory_stride=_exact_int(
                value["trajectory_stride"],
                name="trajectory_stride",
                minimum=1,
            ),
            max_neighbors=_exact_int(
                value["max_neighbors"],
                name="max_neighbors",
                minimum=1,
            ),
            max_atoms_per_cell=_exact_int(
                value["max_atoms_per_cell"],
                name="max_atoms_per_cell",
                minimum=1,
            ),
            ewald_config=ewald_config,
            schema_id=str(value["schema_id"]),
        )
        if result.to_dict() != dict(value):
            raise ReferenceNVEError("reference NVE config is not canonical")
        return result

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())


@dataclass(frozen=True)
class ReferenceNVEFrame:
    step: int
    time_ps: float
    coordinates: torch.Tensor
    velocities_angstrom_per_ps: torch.Tensor
    potential_energy_kcal_per_mol: float
    kinetic_energy_kcal_per_mol: float
    total_energy_kcal_per_mol: float
    max_abs_position_constraint_residual_angstrom: float = 0.0
    max_abs_velocity_constraint_residual_angstrom_per_ps: float = 0.0
    cumulative_shake_iteration_count: int = 0
    cumulative_rattle_iteration_count: int = 0
    schema_id: str = REFERENCE_NVE_FRAME_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != REFERENCE_NVE_FRAME_SCHEMA_ID:
            raise ReferenceNVEError("unsupported reference NVE frame schema")
        object.__setattr__(
            self,
            "step",
            _exact_int(self.step, name="frame step", minimum=0),
        )
        object.__setattr__(
            self,
            "time_ps",
            _finite_float(self.time_ps, name="frame time_ps", nonnegative=True),
        )
        coordinates = self.coordinates.detach().clone()
        velocities = self.velocities_angstrom_per_ps.detach().clone()
        coordinate_payload = _tensor_payload(coordinates, name="frame coordinates")
        velocity_payload = _tensor_payload(velocities, name="frame velocities")
        if coordinate_payload["shape"] != velocity_payload["shape"]:
            raise ReferenceNVEError("frame coordinate and velocity shapes differ")
        object.__setattr__(self, "coordinates", coordinates)
        object.__setattr__(self, "velocities_angstrom_per_ps", velocities)
        potential = _finite_float(
            self.potential_energy_kcal_per_mol,
            name="frame potential energy",
        )
        kinetic = _finite_float(
            self.kinetic_energy_kcal_per_mol,
            name="frame kinetic energy",
            nonnegative=True,
        )
        total = _finite_float(
            self.total_energy_kcal_per_mol,
            name="frame total energy",
        )
        if total.hex() != (potential + kinetic).hex():
            raise ReferenceNVEError("frame total energy does not exactly equal potential + kinetic")
        object.__setattr__(self, "potential_energy_kcal_per_mol", potential)
        object.__setattr__(self, "kinetic_energy_kcal_per_mol", kinetic)
        object.__setattr__(self, "total_energy_kcal_per_mol", total)
        object.__setattr__(
            self,
            "max_abs_position_constraint_residual_angstrom",
            _finite_float(
                self.max_abs_position_constraint_residual_angstrom,
                name="frame maximum absolute position constraint residual",
                nonnegative=True,
            ),
        )
        object.__setattr__(
            self,
            "max_abs_velocity_constraint_residual_angstrom_per_ps",
            _finite_float(
                self.max_abs_velocity_constraint_residual_angstrom_per_ps,
                name="frame maximum absolute velocity constraint residual",
                nonnegative=True,
            ),
        )
        object.__setattr__(
            self,
            "cumulative_shake_iteration_count",
            _exact_int(
                self.cumulative_shake_iteration_count,
                name="frame cumulative SHAKE iteration count",
                minimum=0,
            ),
        )
        object.__setattr__(
            self,
            "cumulative_rattle_iteration_count",
            _exact_int(
                self.cumulative_rattle_iteration_count,
                name="frame cumulative RATTLE iteration count",
                minimum=0,
            ),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "step": self.step,
            "time_ps_hex": self.time_ps.hex(),
            "coordinates_angstrom": _tensor_payload(
                self.coordinates,
                name="frame coordinates",
            ),
            "velocities_angstrom_per_ps": _tensor_payload(
                self.velocities_angstrom_per_ps,
                name="frame velocities",
            ),
            "potential_energy_kcal_per_mol_hex": (
                self.potential_energy_kcal_per_mol.hex()
            ),
            "kinetic_energy_kcal_per_mol_hex": self.kinetic_energy_kcal_per_mol.hex(),
            "total_energy_kcal_per_mol_hex": self.total_energy_kcal_per_mol.hex(),
            "max_abs_position_constraint_residual_angstrom_hex": (
                self.max_abs_position_constraint_residual_angstrom.hex()
            ),
            "max_abs_velocity_constraint_residual_angstrom_per_ps_hex": (
                self.max_abs_velocity_constraint_residual_angstrom_per_ps.hex()
            ),
            "cumulative_shake_iteration_count": (
                self.cumulative_shake_iteration_count
            ),
            "cumulative_rattle_iteration_count": (
                self.cumulative_rattle_iteration_count
            ),
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())


def _trajectory_head(previous: str, frame: ReferenceNVEFrame, frame_count: int) -> str:
    if previous:
        _digest(previous, name="previous trajectory head")
    return _canonical_sha256(
        {
            "schema_id": REFERENCE_NVE_TRAJECTORY_CHAIN_SCHEMA_ID,
            "frame_count": frame_count,
            "previous_head_sha256": previous,
            "frame_sha256": frame.fingerprint_sha256,
        }
    )


@dataclass(frozen=True)
class ReferenceNVECheckpoint:
    source_system_sha256: str
    topology_sha256: str
    parameter_fingerprint_sha256: str
    config: ReferenceNVEConfig
    constraint_config: ReferenceSHAKERATTLEConfig
    step: int
    time_ps: float
    initial_total_energy_kcal_per_mol: float
    current_potential_energy_kcal_per_mol: float
    current_kinetic_energy_kcal_per_mol: float
    current_total_energy_kcal_per_mol: float
    max_abs_energy_drift_kcal_per_mol: float
    max_abs_position_constraint_residual_angstrom: float
    max_abs_velocity_constraint_residual_angstrom_per_ps: float
    cumulative_shake_iteration_count: int
    cumulative_rattle_iteration_count: int
    coordinates: torch.Tensor
    velocities_angstrom_per_ps: torch.Tensor
    current_frame_sha256: str
    trajectory_head_sha256: str
    evaluated_frame_count: int
    schema_id: str = REFERENCE_NVE_CHECKPOINT_SCHEMA_ID
    algorithm_id: str = REFERENCE_NVE_ALGORITHM_ID

    def __post_init__(self) -> None:
        if self.schema_id != REFERENCE_NVE_CHECKPOINT_SCHEMA_ID:
            raise ReferenceNVEError("unsupported reference NVE checkpoint schema")
        if self.algorithm_id != REFERENCE_NVE_ALGORITHM_ID:
            raise ReferenceNVEError("unsupported reference NVE algorithm")
        for name in (
            "source_system_sha256",
            "topology_sha256",
            "parameter_fingerprint_sha256",
            "current_frame_sha256",
            "trajectory_head_sha256",
        ):
            object.__setattr__(self, name, _digest(getattr(self, name), name=name))
        if not isinstance(self.config, ReferenceNVEConfig):
            raise ReferenceNVEError("checkpoint config type is invalid")
        if not isinstance(self.constraint_config, ReferenceSHAKERATTLEConfig):
            raise ReferenceNVEError("checkpoint constraint config type is invalid")
        step = _exact_int(self.step, name="checkpoint step", minimum=0)
        object.__setattr__(self, "step", step)
        time_ps = _finite_float(self.time_ps, name="checkpoint time", nonnegative=True)
        if time_ps.hex() != (step * self.config.timestep_ps).hex():
            raise ReferenceNVEError("checkpoint time does not match step * timestep")
        object.__setattr__(self, "time_ps", time_ps)
        for name in (
            "initial_total_energy_kcal_per_mol",
            "current_potential_energy_kcal_per_mol",
            "current_total_energy_kcal_per_mol",
        ):
            object.__setattr__(
                self,
                name,
                _finite_float(getattr(self, name), name=name),
            )
        object.__setattr__(
            self,
            "current_kinetic_energy_kcal_per_mol",
            _finite_float(
                self.current_kinetic_energy_kcal_per_mol,
                name="current kinetic energy",
                nonnegative=True,
            ),
        )
        object.__setattr__(
            self,
            "max_abs_energy_drift_kcal_per_mol",
            _finite_float(
                self.max_abs_energy_drift_kcal_per_mol,
                name="max absolute energy drift",
                nonnegative=True,
            ),
        )
        object.__setattr__(
            self,
            "max_abs_position_constraint_residual_angstrom",
            _finite_float(
                self.max_abs_position_constraint_residual_angstrom,
                name="maximum absolute position constraint residual",
                nonnegative=True,
            ),
        )
        object.__setattr__(
            self,
            "max_abs_velocity_constraint_residual_angstrom_per_ps",
            _finite_float(
                self.max_abs_velocity_constraint_residual_angstrom_per_ps,
                name="maximum absolute velocity constraint residual",
                nonnegative=True,
            ),
        )
        object.__setattr__(
            self,
            "cumulative_shake_iteration_count",
            _exact_int(
                self.cumulative_shake_iteration_count,
                name="cumulative SHAKE iteration count",
                minimum=0,
            ),
        )
        object.__setattr__(
            self,
            "cumulative_rattle_iteration_count",
            _exact_int(
                self.cumulative_rattle_iteration_count,
                name="cumulative RATTLE iteration count",
                minimum=0,
            ),
        )
        if self.max_abs_energy_drift_kcal_per_mol < abs(
            self.current_total_energy_kcal_per_mol
            - self.initial_total_energy_kcal_per_mol
        ):
            raise ReferenceNVEError(
                "checkpoint maximum energy drift is smaller than current drift"
            )
        if self.current_total_energy_kcal_per_mol.hex() != (
            self.current_potential_energy_kcal_per_mol
            + self.current_kinetic_energy_kcal_per_mol
        ).hex():
            raise ReferenceNVEError("checkpoint current total energy is inconsistent")
        coordinates = self.coordinates.detach().clone()
        velocities = self.velocities_angstrom_per_ps.detach().clone()
        if _tensor_payload(coordinates, name="checkpoint coordinates")["shape"] != (
            _tensor_payload(velocities, name="checkpoint velocities")["shape"]
        ):
            raise ReferenceNVEError("checkpoint coordinate and velocity shapes differ")
        object.__setattr__(self, "coordinates", coordinates)
        object.__setattr__(self, "velocities_angstrom_per_ps", velocities)
        frame_count = _exact_int(
            self.evaluated_frame_count,
            name="evaluated_frame_count",
            minimum=1,
        )
        if frame_count != step + 1:
            raise ReferenceNVEError("evaluated_frame_count must equal step + 1")
        object.__setattr__(self, "evaluated_frame_count", frame_count)
        if self.current_frame().fingerprint_sha256 != self.current_frame_sha256:
            raise ReferenceNVEError("checkpoint current frame digest mismatch")

    def current_frame(self) -> ReferenceNVEFrame:
        return ReferenceNVEFrame(
            step=self.step,
            time_ps=self.time_ps,
            coordinates=self.coordinates,
            velocities_angstrom_per_ps=self.velocities_angstrom_per_ps,
            potential_energy_kcal_per_mol=self.current_potential_energy_kcal_per_mol,
            kinetic_energy_kcal_per_mol=self.current_kinetic_energy_kcal_per_mol,
            total_energy_kcal_per_mol=self.current_total_energy_kcal_per_mol,
            max_abs_position_constraint_residual_angstrom=(
                self.max_abs_position_constraint_residual_angstrom
            ),
            max_abs_velocity_constraint_residual_angstrom_per_ps=(
                self.max_abs_velocity_constraint_residual_angstrom_per_ps
            ),
            cumulative_shake_iteration_count=(
                self.cumulative_shake_iteration_count
            ),
            cumulative_rattle_iteration_count=(
                self.cumulative_rattle_iteration_count
            ),
        )

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "algorithm_id": self.algorithm_id,
            "source_system_sha256": self.source_system_sha256,
            "topology_sha256": self.topology_sha256,
            "parameter_fingerprint_sha256": self.parameter_fingerprint_sha256,
            "config": self.config.to_dict(),
            "config_fingerprint_sha256": self.config.fingerprint_sha256,
            "constraint_config": self.constraint_config.to_dict(),
            "constraint_config_fingerprint_sha256": (
                self.constraint_config.fingerprint_sha256
            ),
            "step": self.step,
            "time_ps_hex": self.time_ps.hex(),
            "initial_total_energy_kcal_per_mol_hex": (
                self.initial_total_energy_kcal_per_mol.hex()
            ),
            "current_potential_energy_kcal_per_mol_hex": (
                self.current_potential_energy_kcal_per_mol.hex()
            ),
            "current_kinetic_energy_kcal_per_mol_hex": (
                self.current_kinetic_energy_kcal_per_mol.hex()
            ),
            "current_total_energy_kcal_per_mol_hex": (
                self.current_total_energy_kcal_per_mol.hex()
            ),
            "max_abs_energy_drift_kcal_per_mol_hex": (
                self.max_abs_energy_drift_kcal_per_mol.hex()
            ),
            "max_abs_position_constraint_residual_angstrom_hex": (
                self.max_abs_position_constraint_residual_angstrom.hex()
            ),
            "max_abs_velocity_constraint_residual_angstrom_per_ps_hex": (
                self.max_abs_velocity_constraint_residual_angstrom_per_ps.hex()
            ),
            "cumulative_shake_iteration_count": (
                self.cumulative_shake_iteration_count
            ),
            "cumulative_rattle_iteration_count": (
                self.cumulative_rattle_iteration_count
            ),
            "coordinates_angstrom": _tensor_payload(
                self.coordinates,
                name="checkpoint coordinates",
            ),
            "velocities_angstrom_per_ps": _tensor_payload(
                self.velocities_angstrom_per_ps,
                name="checkpoint velocities",
            ),
            "current_frame_sha256": self.current_frame_sha256,
            "trajectory_head_sha256": self.trajectory_head_sha256,
            "evaluated_frame_count": self.evaluated_frame_count,
        }

    @property
    def checkpoint_sha256(self) -> str:
        return _canonical_sha256(self._projection())

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "checkpoint_sha256": self.checkpoint_sha256}

    def to_json_bytes(self) -> bytes:
        return _canonical_bytes(self.to_dict())

    @classmethod
    def from_json_bytes(cls, raw: bytes) -> "ReferenceNVECheckpoint":
        if not isinstance(raw, bytes) or not raw or len(raw) > MAX_REFERENCE_NVE_CHECKPOINT_BYTES:
            raise ReferenceNVEError("checkpoint bytes are empty or exceed the size bound")
        try:
            value = json.loads(raw.decode("ascii"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ReferenceNVEError("checkpoint is not canonical ASCII JSON") from exc
        expected_keys = {
            "schema_id",
            "algorithm_id",
            "source_system_sha256",
            "topology_sha256",
            "parameter_fingerprint_sha256",
            "config",
            "config_fingerprint_sha256",
            "constraint_config",
            "constraint_config_fingerprint_sha256",
            "step",
            "time_ps_hex",
            "initial_total_energy_kcal_per_mol_hex",
            "current_potential_energy_kcal_per_mol_hex",
            "current_kinetic_energy_kcal_per_mol_hex",
            "current_total_energy_kcal_per_mol_hex",
            "max_abs_energy_drift_kcal_per_mol_hex",
            "max_abs_position_constraint_residual_angstrom_hex",
            "max_abs_velocity_constraint_residual_angstrom_per_ps_hex",
            "cumulative_shake_iteration_count",
            "cumulative_rattle_iteration_count",
            "coordinates_angstrom",
            "velocities_angstrom_per_ps",
            "current_frame_sha256",
            "trajectory_head_sha256",
            "evaluated_frame_count",
            "checkpoint_sha256",
        }
        if not isinstance(value, dict) or set(value) != expected_keys:
            raise ReferenceNVEError("checkpoint document shape is invalid")
        config = ReferenceNVEConfig.from_dict(value["config"])
        if config.fingerprint_sha256 != _digest(
            value["config_fingerprint_sha256"],
            name="config_fingerprint_sha256",
        ):
            raise ReferenceNVEError("checkpoint config fingerprint mismatch")
        try:
            constraint_config = ReferenceSHAKERATTLEConfig.from_dict(
                value["constraint_config"]
            )
        except ReferenceSHAKERATTLEError as exc:
            raise ReferenceNVEError("checkpoint constraint config is invalid") from exc
        if constraint_config.fingerprint_sha256 != _digest(
            value["constraint_config_fingerprint_sha256"],
            name="constraint_config_fingerprint_sha256",
        ):
            raise ReferenceNVEError(
                "checkpoint constraint config fingerprint mismatch"
            )
        checkpoint = cls(
            source_system_sha256=str(value["source_system_sha256"]),
            topology_sha256=str(value["topology_sha256"]),
            parameter_fingerprint_sha256=str(value["parameter_fingerprint_sha256"]),
            config=config,
            constraint_config=constraint_config,
            step=_exact_int(value["step"], name="checkpoint step", minimum=0),
            time_ps=_require_float_hex(value["time_ps_hex"], name="time_ps_hex"),
            initial_total_energy_kcal_per_mol=_require_float_hex(
                value["initial_total_energy_kcal_per_mol_hex"],
                name="initial total energy",
            ),
            current_potential_energy_kcal_per_mol=_require_float_hex(
                value["current_potential_energy_kcal_per_mol_hex"],
                name="current potential energy",
            ),
            current_kinetic_energy_kcal_per_mol=_require_float_hex(
                value["current_kinetic_energy_kcal_per_mol_hex"],
                name="current kinetic energy",
            ),
            current_total_energy_kcal_per_mol=_require_float_hex(
                value["current_total_energy_kcal_per_mol_hex"],
                name="current total energy",
            ),
            max_abs_energy_drift_kcal_per_mol=_require_float_hex(
                value["max_abs_energy_drift_kcal_per_mol_hex"],
                name="max absolute energy drift",
            ),
            max_abs_position_constraint_residual_angstrom=_require_float_hex(
                value[
                    "max_abs_position_constraint_residual_angstrom_hex"
                ],
                name="maximum absolute position constraint residual",
            ),
            max_abs_velocity_constraint_residual_angstrom_per_ps=(
                _require_float_hex(
                    value[
                        "max_abs_velocity_constraint_residual_angstrom_per_ps_hex"
                    ],
                    name="maximum absolute velocity constraint residual",
                )
            ),
            cumulative_shake_iteration_count=_exact_int(
                value["cumulative_shake_iteration_count"],
                name="cumulative SHAKE iteration count",
                minimum=0,
            ),
            cumulative_rattle_iteration_count=_exact_int(
                value["cumulative_rattle_iteration_count"],
                name="cumulative RATTLE iteration count",
                minimum=0,
            ),
            coordinates=_tensor_from_payload(
                value["coordinates_angstrom"],
                name="checkpoint coordinates",
            ),
            velocities_angstrom_per_ps=_tensor_from_payload(
                value["velocities_angstrom_per_ps"],
                name="checkpoint velocities",
            ),
            current_frame_sha256=str(value["current_frame_sha256"]),
            trajectory_head_sha256=str(value["trajectory_head_sha256"]),
            evaluated_frame_count=_exact_int(
                value["evaluated_frame_count"],
                name="evaluated_frame_count",
                minimum=1,
            ),
            schema_id=str(value["schema_id"]),
            algorithm_id=str(value["algorithm_id"]),
        )
        if checkpoint.checkpoint_sha256 != _digest(
            value["checkpoint_sha256"],
            name="checkpoint_sha256",
        ):
            raise ReferenceNVEError("checkpoint self-digest mismatch")
        if checkpoint.to_json_bytes() != raw:
            raise ReferenceNVEError("checkpoint transport is not canonical")
        return checkpoint


@dataclass(frozen=True)
class ReferenceNVEProvenance:
    source_system_sha256: str
    topology_sha256: str
    parameter_fingerprint_sha256: str
    config_fingerprint_sha256: str
    constraint_config_fingerprint_sha256: str
    algorithm_id: str = REFERENCE_NVE_ALGORITHM_ID
    device: str = "cpu"
    dtype: str = "float64"
    torch_version: str = str(torch.__version__)

    def __post_init__(self) -> None:
        for name in (
            "source_system_sha256",
            "topology_sha256",
            "parameter_fingerprint_sha256",
            "config_fingerprint_sha256",
            "constraint_config_fingerprint_sha256",
        ):
            object.__setattr__(self, name, _digest(getattr(self, name), name=name))
        if self.algorithm_id != REFERENCE_NVE_ALGORITHM_ID:
            raise ReferenceNVEError("unsupported reference NVE provenance algorithm")
        if self.device != "cpu" or self.dtype != "float64":
            raise ReferenceNVEError("reference NVE provenance must identify CPU float64")
        version = str(self.torch_version).strip()
        if not version:
            raise ReferenceNVEError("reference NVE provenance requires a Torch version")
        object.__setattr__(self, "torch_version", version)

    def to_dict(self) -> dict[str, str]:
        return {
            "source_system_sha256": self.source_system_sha256,
            "topology_sha256": self.topology_sha256,
            "parameter_fingerprint_sha256": self.parameter_fingerprint_sha256,
            "config_fingerprint_sha256": self.config_fingerprint_sha256,
            "constraint_config_fingerprint_sha256": (
                self.constraint_config_fingerprint_sha256
            ),
            "algorithm_id": self.algorithm_id,
            "device": self.device,
            "dtype": self.dtype,
            "torch_version": self.torch_version,
        }


@dataclass(frozen=True)
class ReferenceNVEResult:
    start_step: int
    end_step: int
    frames: tuple[ReferenceNVEFrame, ...]
    checkpoint: ReferenceNVECheckpoint
    system: AllAtomSystem
    provenance: ReferenceNVEProvenance
    scientific_blockers: tuple[str, ...] = REFERENCE_NVE_SCIENTIFIC_BLOCKERS
    schema_id: str = REFERENCE_NVE_RESULT_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != REFERENCE_NVE_RESULT_SCHEMA_ID:
            raise ReferenceNVEError("unsupported reference NVE result schema")
        start = _exact_int(self.start_step, name="result start_step", minimum=0)
        end = _exact_int(self.end_step, name="result end_step", minimum=start)
        object.__setattr__(self, "start_step", start)
        object.__setattr__(self, "end_step", end)
        frames = tuple(self.frames)
        if not frames or not all(isinstance(frame, ReferenceNVEFrame) for frame in frames):
            raise ReferenceNVEError("reference NVE result requires retained frames")
        if frames[0].step != start or frames[-1].step != end:
            raise ReferenceNVEError("reference NVE retained-frame endpoints are inconsistent")
        if any(right.step <= left.step for left, right in zip(frames, frames[1:])):
            raise ReferenceNVEError("reference NVE retained-frame steps must increase")
        object.__setattr__(self, "frames", frames)
        if not isinstance(self.checkpoint, ReferenceNVECheckpoint):
            raise ReferenceNVEError("reference NVE result checkpoint type is invalid")
        if self.checkpoint.step != end:
            raise ReferenceNVEError("reference NVE result checkpoint step is inconsistent")
        if self.checkpoint.current_frame_sha256 != frames[-1].fingerprint_sha256:
            raise ReferenceNVEError("reference NVE result final-frame identity is inconsistent")
        if not isinstance(self.system, AllAtomSystem):
            raise ReferenceNVEError("reference NVE result system type is invalid")
        if not torch.equal(self.system.coordinates, self.checkpoint.coordinates):
            raise ReferenceNVEError("reference NVE result system coordinates are inconsistent")
        if not isinstance(self.provenance, ReferenceNVEProvenance):
            raise ReferenceNVEError("reference NVE result provenance type is invalid")
        checkpoint_identity = {
            "source_system_sha256": self.checkpoint.source_system_sha256,
            "topology_sha256": self.checkpoint.topology_sha256,
            "parameter_fingerprint_sha256": self.checkpoint.parameter_fingerprint_sha256,
            "config_fingerprint_sha256": self.checkpoint.config.fingerprint_sha256,
            "constraint_config_fingerprint_sha256": (
                self.checkpoint.constraint_config.fingerprint_sha256
            ),
            "algorithm_id": self.checkpoint.algorithm_id,
        }
        provenance_identity = {
            key: self.provenance.to_dict()[key] for key in checkpoint_identity
        }
        if checkpoint_identity != provenance_identity:
            raise ReferenceNVEError("reference NVE result provenance is inconsistent")
        blockers = tuple(self.scientific_blockers)
        if blockers != REFERENCE_NVE_SCIENTIFIC_BLOCKERS:
            raise ReferenceNVEError("reference NVE scientific blockers cannot be promoted")
        object.__setattr__(self, "scientific_blockers", blockers)

    @property
    def steps_completed(self) -> int:
        return self.end_step - self.start_step

    @property
    def initial_total_energy_kcal_per_mol(self) -> float:
        return self.checkpoint.initial_total_energy_kcal_per_mol

    @property
    def final_total_energy_kcal_per_mol(self) -> float:
        return self.checkpoint.current_total_energy_kcal_per_mol

    @property
    def energy_drift_kcal_per_mol(self) -> float:
        return self.final_total_energy_kcal_per_mol - self.initial_total_energy_kcal_per_mol

    @property
    def max_abs_energy_drift_kcal_per_mol(self) -> float:
        return self.checkpoint.max_abs_energy_drift_kcal_per_mol

    @property
    def max_abs_position_constraint_residual_angstrom(self) -> float:
        return self.checkpoint.max_abs_position_constraint_residual_angstrom

    @property
    def max_abs_velocity_constraint_residual_angstrom_per_ps(self) -> float:
        return self.checkpoint.max_abs_velocity_constraint_residual_angstrom_per_ps

    @property
    def cumulative_shake_iteration_count(self) -> int:
        return self.checkpoint.cumulative_shake_iteration_count

    @property
    def cumulative_rattle_iteration_count(self) -> int:
        return self.checkpoint.cumulative_rattle_iteration_count

    @property
    def claim_safe(self) -> bool:
        return False

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "status": "completed",
            "start_step": self.start_step,
            "end_step": self.end_step,
            "steps_completed": self.steps_completed,
            "retained_frame_count": len(self.frames),
            "evaluated_frame_count": self.checkpoint.evaluated_frame_count,
            "initial_total_energy_kcal_per_mol_hex": (
                self.initial_total_energy_kcal_per_mol.hex()
            ),
            "final_total_energy_kcal_per_mol_hex": (
                self.final_total_energy_kcal_per_mol.hex()
            ),
            "energy_drift_kcal_per_mol_hex": self.energy_drift_kcal_per_mol.hex(),
            "max_abs_energy_drift_kcal_per_mol_hex": (
                self.max_abs_energy_drift_kcal_per_mol.hex()
            ),
            "constraint_count": len(self.checkpoint.constraint_config.constraints),
            "electrostatics_mode": self.checkpoint.config.electrostatics_mode,
            "ewald_config_fingerprint_sha256": (
                ""
                if self.checkpoint.config.ewald_config is None
                else self.checkpoint.config.ewald_config.fingerprint_sha256
            ),
            "max_abs_position_constraint_residual_angstrom_hex": (
                self.max_abs_position_constraint_residual_angstrom.hex()
            ),
            "max_abs_velocity_constraint_residual_angstrom_per_ps_hex": (
                self.max_abs_velocity_constraint_residual_angstrom_per_ps.hex()
            ),
            "cumulative_shake_iteration_count": (
                self.cumulative_shake_iteration_count
            ),
            "cumulative_rattle_iteration_count": (
                self.cumulative_rattle_iteration_count
            ),
            "trajectory_head_sha256": self.checkpoint.trajectory_head_sha256,
            "frames": [frame.to_dict() for frame in self.frames],
            "checkpoint_sha256": self.checkpoint.checkpoint_sha256,
            "provenance": self.provenance.to_dict(),
            "scientific_blockers": list(self.scientific_blockers),
            "claim_safe": False,
        }


def _require_source_system(system: AllAtomSystem) -> torch.Tensor:
    require_valid_all_atom_system(system)
    if system.model_count != 1:
        raise ReferenceNVEError("reference NVE requires exactly one coordinate model")
    if system.coordinates.dtype != torch.float64 or system.coordinates.device.type != "cpu":
        raise ReferenceNVEError("reference NVE requires CPU float64 coordinates")
    masses = []
    for atom in system.atoms:
        if atom.mass_da is None:
            raise ReferenceNVEError(f"atom {atom.index} is missing mass_da")
        masses.append(_finite_float(atom.mass_da, name=f"atom {atom.index} mass", positive=True))
    if system.cell is not None:
        if (
            system.cell.vectors.dtype != torch.float64
            or system.cell.vectors.device.type != "cpu"
        ):
            raise ReferenceNVEError(
                "reference NVE periodic cells must use CPU float64 vectors"
            )
        if system.cell.periodic != (True, True, True):
            raise ReferenceNVEError(
                "reference NVE periodic cells must be periodic in all three dimensions"
            )
        try:
            lengths = system.cell.orthorhombic_lengths()
        except ValueError as exc:
            raise ReferenceNVEError(
                "reference NVE supports orthorhombic periodic cells only"
            ) from exc
        if not bool(torch.isfinite(lengths).all().item()) or bool((lengths <= 0.0).any().item()):
            raise ReferenceNVEError("periodic cell lengths must be finite and positive")
    return torch.tensor(masses, dtype=torch.float64)


def _wrap_coordinates(coordinates: torch.Tensor, system: AllAtomSystem) -> torch.Tensor:
    if system.cell is None:
        return coordinates
    lengths = system.cell.orthorhombic_lengths().to(dtype=torch.float64, device="cpu")
    return coordinates - torch.floor(coordinates / lengths.view(1, 1, 3)) * lengths.view(1, 1, 3)


def _evaluate(
    source_system: AllAtomSystem,
    coordinates: torch.Tensor,
    parameters: ReferenceForceFieldParameters,
    config: ReferenceNVEConfig,
) -> tuple[float, torch.Tensor]:
    current = replace(source_system, coordinates=coordinates)
    neighbors = build_compact_radius_graph(
        current.coordinates,
        RadiusGraphConfig(
            cutoff_angstrom=parameters.cutoff_angstrom,
            max_neighbors=config.max_neighbors,
            max_atoms_per_cell=config.max_atoms_per_cell,
        ),
        cell=current.cell,
    )
    try:
        if config.ewald_config is None:
            evaluation = evaluate_reference_force_field(
                current,
                neighbors,
                parameters,
            )
        else:
            evaluation = evaluate_reference_force_field_with_ewald(
                current,
                neighbors,
                parameters,
                config.ewald_config,
            )
    except ReferenceEwaldError as exc:
        raise ReferenceNVEError(
            f"direct Ewald force evaluation failed closed: {exc}"
        ) from exc
    potential = float(evaluation.term.energy.detach().cpu().reshape(-1)[0].item())
    forces = evaluation.term.forces.detach().to(dtype=torch.float64, device="cpu")
    if not math.isfinite(potential) or not bool(torch.isfinite(forces).all().item()):
        raise ReferenceNVEError("reference force evaluation returned non-finite values")
    return potential, forces


def _kinetic_energy(velocities: torch.Tensor, masses: torch.Tensor) -> float:
    value = (
        0.5
        * (
            masses.view(1, -1, 1)
            * velocities.square()
        ).sum()
        / FORCE_KCAL_PER_MOL_ANGSTROM_TO_ACCELERATION_ANGSTROM_PER_PS2_PER_DA
    )
    energy = float(value.item())
    return _finite_float(energy, name="kinetic energy", nonnegative=True)


def _frame(
    *,
    step: int,
    config: ReferenceNVEConfig,
    coordinates: torch.Tensor,
    velocities: torch.Tensor,
    potential: float,
    masses: torch.Tensor,
    max_abs_position_constraint_residual: float,
    max_abs_velocity_constraint_residual: float,
    cumulative_shake_iterations: int,
    cumulative_rattle_iterations: int,
) -> ReferenceNVEFrame:
    kinetic = _kinetic_energy(velocities, masses)
    return ReferenceNVEFrame(
        step=step,
        time_ps=step * config.timestep_ps,
        coordinates=coordinates,
        velocities_angstrom_per_ps=velocities,
        potential_energy_kcal_per_mol=potential,
        kinetic_energy_kcal_per_mol=kinetic,
        total_energy_kcal_per_mol=potential + kinetic,
        max_abs_position_constraint_residual_angstrom=(
            max_abs_position_constraint_residual
        ),
        max_abs_velocity_constraint_residual_angstrom_per_ps=(
            max_abs_velocity_constraint_residual
        ),
        cumulative_shake_iteration_count=cumulative_shake_iterations,
        cumulative_rattle_iteration_count=cumulative_rattle_iterations,
    )


def _provenance(
    system: AllAtomSystem,
    parameters: ReferenceForceFieldParameters,
    config: ReferenceNVEConfig,
    constraint_config: ReferenceSHAKERATTLEConfig,
) -> ReferenceNVEProvenance:
    return ReferenceNVEProvenance(
        source_system_sha256=canonical_system_sha256(system),
        topology_sha256=canonical_topology_sha256(system),
        parameter_fingerprint_sha256=parameters.fingerprint_sha256,
        config_fingerprint_sha256=config.fingerprint_sha256,
        constraint_config_fingerprint_sha256=(
            constraint_config.fingerprint_sha256
        ),
    )


def _checkpoint(
    provenance: ReferenceNVEProvenance,
    config: ReferenceNVEConfig,
    constraint_config: ReferenceSHAKERATTLEConfig,
    frame: ReferenceNVEFrame,
    *,
    initial_total_energy: float,
    max_abs_energy_drift: float,
    max_abs_position_constraint_residual: float,
    max_abs_velocity_constraint_residual: float,
    cumulative_shake_iterations: int,
    cumulative_rattle_iterations: int,
    trajectory_head: str,
    evaluated_frame_count: int,
) -> ReferenceNVECheckpoint:
    return ReferenceNVECheckpoint(
        source_system_sha256=provenance.source_system_sha256,
        topology_sha256=provenance.topology_sha256,
        parameter_fingerprint_sha256=provenance.parameter_fingerprint_sha256,
        config=config,
        constraint_config=constraint_config,
        step=frame.step,
        time_ps=frame.time_ps,
        initial_total_energy_kcal_per_mol=initial_total_energy,
        current_potential_energy_kcal_per_mol=frame.potential_energy_kcal_per_mol,
        current_kinetic_energy_kcal_per_mol=frame.kinetic_energy_kcal_per_mol,
        current_total_energy_kcal_per_mol=frame.total_energy_kcal_per_mol,
        max_abs_energy_drift_kcal_per_mol=max_abs_energy_drift,
        max_abs_position_constraint_residual_angstrom=(
            max_abs_position_constraint_residual
        ),
        max_abs_velocity_constraint_residual_angstrom_per_ps=(
            max_abs_velocity_constraint_residual
        ),
        cumulative_shake_iteration_count=cumulative_shake_iterations,
        cumulative_rattle_iteration_count=cumulative_rattle_iterations,
        coordinates=frame.coordinates,
        velocities_angstrom_per_ps=frame.velocities_angstrom_per_ps,
        current_frame_sha256=frame.fingerprint_sha256,
        trajectory_head_sha256=trajectory_head,
        evaluated_frame_count=evaluated_frame_count,
    )


def _constraint_residuals(
    system: AllAtomSystem,
    coordinates: torch.Tensor,
    velocities: torch.Tensor,
    constraint_config: ReferenceSHAKERATTLEConfig,
) -> tuple[float, float]:
    try:
        position_rows = observe_reference_position_constraints(
            system,
            coordinates,
            constraint_config,
        )
        velocity_rows = observe_reference_velocity_constraints(
            system,
            coordinates,
            velocities,
            constraint_config,
        )
    except ReferenceSHAKERATTLEError as exc:
        raise ReferenceNVEError(
            f"SHAKE/RATTLE constraint observation failed closed: {exc}"
        ) from exc
    position_residual = max(
        (abs(row.residual_angstrom) for row in position_rows),
        default=0.0,
    )
    velocity_residual = max(
        (
            abs(row.radial_relative_velocity_angstrom_per_ps)
            for row in velocity_rows
        ),
        default=0.0,
    )
    return position_residual, velocity_residual


def _require_constrained_state(
    system: AllAtomSystem,
    coordinates: torch.Tensor,
    velocities: torch.Tensor,
    constraint_config: ReferenceSHAKERATTLEConfig,
) -> tuple[float, float]:
    position_residual, velocity_residual = _constraint_residuals(
        system,
        coordinates,
        velocities,
        constraint_config,
    )
    position_rows = observe_reference_position_constraints(
        system,
        coordinates,
        constraint_config,
    )
    if any(
        abs(row.residual_angstrom)
        > constraint_config.convergence_tolerance_scale * row.tolerance_angstrom
        for row in position_rows
    ):
        raise ReferenceNVEError(
            "restart coordinates violate the internal SHAKE position tolerance"
        )
    if velocity_residual > (
        constraint_config.convergence_tolerance_scale
        * constraint_config.velocity_tolerance_angstrom_per_ps
    ):
        raise ReferenceNVEError(
            "restart velocities violate the internal RATTLE velocity tolerance"
        )
    return position_residual, velocity_residual


def _run_segment(
    system: AllAtomSystem,
    parameters: ReferenceForceFieldParameters,
    config: ReferenceNVEConfig,
    constraint_config: ReferenceSHAKERATTLEConfig,
    *,
    coordinates: torch.Tensor,
    velocities: torch.Tensor,
    start_step: int,
    steps: int,
    initial_total_energy: float | None,
    trajectory_head: str,
    evaluated_frame_count: int,
    max_abs_energy_drift: float,
    max_abs_position_constraint_residual: float,
    max_abs_velocity_constraint_residual: float,
    cumulative_shake_iterations: int,
    cumulative_rattle_iterations: int,
    expected_start_frame_sha256: str = "",
) -> ReferenceNVEResult:
    masses = _require_source_system(system)
    try:
        validate_reference_shake_rattle_inputs(system, masses, constraint_config)
    except ReferenceSHAKERATTLEError as exc:
        raise ReferenceNVEError(
            f"SHAKE/RATTLE applicability failed closed: {exc}"
        ) from exc
    expected_shape = (1, system.atom_count, 3)
    if _tensor_payload(coordinates, name="NVE coordinates")["shape"] != list(
        expected_shape
    ):
        raise ReferenceNVEError("NVE coordinates do not match the source atom count")
    if _tensor_payload(velocities, name="NVE velocities")["shape"] != list(
        expected_shape
    ):
        raise ReferenceNVEError("NVE velocities do not match the source atom count")
    end_step = start_step + steps
    retained_count = 1 + end_step // config.trajectory_stride - (
        start_step // config.trajectory_stride
    )
    if end_step % config.trajectory_stride != 0:
        retained_count += 1
    if retained_count > MAX_REFERENCE_NVE_RETAINED_FRAMES:
        raise ReferenceNVEError(
            "requested segment exceeds the retained trajectory-frame capacity"
        )
    if initial_total_energy is None and constraint_config.enabled:
        try:
            initial_shake = project_reference_shake_positions(
                system,
                coordinates,
                coordinates,
                masses,
                constraint_config,
            )
        except ReferenceSHAKERATTLEError as exc:
            raise ReferenceNVEError(
                f"initial SHAKE state failed closed: {exc}"
            ) from exc
        if not initial_shake.converged:
            raise ReferenceNVEError(
                "initial SHAKE state failed closed: "
                f"{initial_shake.failure_code}; "
                f"max_abs_residual_angstrom="
                f"{initial_shake.max_abs_residual_angstrom.hex()}"
            )
        coordinates = initial_shake.coordinates
        try:
            initial_rattle = project_reference_rattle_velocities(
                system,
                coordinates,
                velocities,
                masses,
                constraint_config,
            )
        except ReferenceSHAKERATTLEError as exc:
            raise ReferenceNVEError(
                f"initial RATTLE state failed closed: {exc}"
            ) from exc
        if not initial_rattle.converged:
            raise ReferenceNVEError(
                "initial RATTLE state failed closed: "
                f"{initial_rattle.failure_code}; "
                f"max_abs_residual_angstrom_per_ps="
                f"{initial_rattle.max_abs_residual_angstrom_per_ps.hex()}"
            )
        velocities = initial_rattle.velocities_angstrom_per_ps
        max_abs_position_constraint_residual = (
            initial_shake.max_abs_residual_angstrom
        )
        max_abs_velocity_constraint_residual = (
            initial_rattle.max_abs_residual_angstrom_per_ps
        )
        cumulative_shake_iterations = initial_shake.iteration_count
        cumulative_rattle_iterations = initial_rattle.iteration_count
    elif initial_total_energy is not None:
        observed_position_residual, observed_velocity_residual = (
            _require_constrained_state(
                system,
                coordinates,
                velocities,
                constraint_config,
            )
        )
        if observed_position_residual > max_abs_position_constraint_residual:
            raise ReferenceNVEError(
                "restart position residual exceeds checkpoint history"
            )
        if observed_velocity_residual > max_abs_velocity_constraint_residual:
            raise ReferenceNVEError(
                "restart velocity residual exceeds checkpoint history"
            )

    provenance = _provenance(system, parameters, config, constraint_config)
    potential, forces = _evaluate(system, coordinates, parameters, config)
    current = _frame(
        step=start_step,
        config=config,
        coordinates=coordinates,
        velocities=velocities,
        potential=potential,
        masses=masses,
        max_abs_position_constraint_residual=(
            max_abs_position_constraint_residual
        ),
        max_abs_velocity_constraint_residual=(
            max_abs_velocity_constraint_residual
        ),
        cumulative_shake_iterations=cumulative_shake_iterations,
        cumulative_rattle_iterations=cumulative_rattle_iterations,
    )
    if expected_start_frame_sha256 and current.fingerprint_sha256 != _digest(
        expected_start_frame_sha256,
        name="expected_start_frame_sha256",
    ):
        raise ReferenceNVEError("restart state does not reproduce the checkpoint frame")
    if initial_total_energy is None:
        initial_total_energy = current.total_energy_kcal_per_mol
        evaluated_frame_count = 1
        trajectory_head = _trajectory_head("", current, evaluated_frame_count)
        max_abs_energy_drift = 0.0
    captured = [current]
    timestep = config.timestep_ps
    inverse_mass = (
        FORCE_KCAL_PER_MOL_ANGSTROM_TO_ACCELERATION_ANGSTROM_PER_PS2_PER_DA
        / masses.view(1, -1, 1)
    )
    for offset in range(1, steps + 1):
        half_velocity = velocities + 0.5 * timestep * forces * inverse_mass
        predicted_coordinates = _wrap_coordinates(
            coordinates + timestep * half_velocity,
            system,
        )
        if constraint_config.enabled:
            try:
                shake = project_reference_shake_positions(
                    system,
                    coordinates,
                    predicted_coordinates,
                    masses,
                    constraint_config,
                )
            except ReferenceSHAKERATTLEError as exc:
                failed_step = start_step + offset
                raise ReferenceNVEError(
                    f"SHAKE failed closed at step {failed_step}: {exc}"
                ) from exc
            if not shake.converged:
                failed_step = start_step + offset
                raise ReferenceNVEError(
                    f"SHAKE failed closed at step {failed_step}: "
                    f"{shake.failure_code}; iterations={shake.iteration_count}; "
                    f"max_abs_residual_angstrom="
                    f"{shake.max_abs_residual_angstrom.hex()}"
                )
            coordinates = shake.coordinates
            shake_displacement = minimum_image_displacement(
                coordinates - predicted_coordinates,
                system,
            )
            half_velocity = half_velocity + shake_displacement / timestep
            cumulative_shake_iterations += shake.iteration_count
            max_abs_position_constraint_residual = max(
                max_abs_position_constraint_residual,
                shake.max_abs_residual_angstrom,
            )
        else:
            coordinates = predicted_coordinates
        potential, next_forces = _evaluate(system, coordinates, parameters, config)
        velocities = half_velocity + 0.5 * timestep * next_forces * inverse_mass
        if constraint_config.enabled:
            try:
                rattle = project_reference_rattle_velocities(
                    system,
                    coordinates,
                    velocities,
                    masses,
                    constraint_config,
                )
            except ReferenceSHAKERATTLEError as exc:
                failed_step = start_step + offset
                raise ReferenceNVEError(
                    f"RATTLE failed closed at step {failed_step}: {exc}"
                ) from exc
            if not rattle.converged:
                failed_step = start_step + offset
                raise ReferenceNVEError(
                    f"RATTLE failed closed at step {failed_step}: "
                    f"{rattle.failure_code}; iterations={rattle.iteration_count}; "
                    f"max_abs_residual_angstrom_per_ps="
                    f"{rattle.max_abs_residual_angstrom_per_ps.hex()}"
                )
            velocities = rattle.velocities_angstrom_per_ps
            cumulative_rattle_iterations += rattle.iteration_count
            max_abs_velocity_constraint_residual = max(
                max_abs_velocity_constraint_residual,
                rattle.max_abs_residual_angstrom_per_ps,
            )
        forces = next_forces
        step = start_step + offset
        current = _frame(
            step=step,
            config=config,
            coordinates=coordinates,
            velocities=velocities,
            potential=potential,
            masses=masses,
            max_abs_position_constraint_residual=(
                max_abs_position_constraint_residual
            ),
            max_abs_velocity_constraint_residual=(
                max_abs_velocity_constraint_residual
            ),
            cumulative_shake_iterations=cumulative_shake_iterations,
            cumulative_rattle_iterations=cumulative_rattle_iterations,
        )
        evaluated_frame_count += 1
        trajectory_head = _trajectory_head(
            trajectory_head,
            current,
            evaluated_frame_count,
        )
        drift = abs(current.total_energy_kcal_per_mol - initial_total_energy)
        max_abs_energy_drift = max(max_abs_energy_drift, drift)
        if step % config.trajectory_stride == 0 or offset == steps:
            captured.append(current)
    checkpoint = _checkpoint(
        provenance,
        config,
        constraint_config,
        current,
        initial_total_energy=initial_total_energy,
        max_abs_energy_drift=max_abs_energy_drift,
        max_abs_position_constraint_residual=(
            max_abs_position_constraint_residual
        ),
        max_abs_velocity_constraint_residual=(
            max_abs_velocity_constraint_residual
        ),
        cumulative_shake_iterations=cumulative_shake_iterations,
        cumulative_rattle_iterations=cumulative_rattle_iterations,
        trajectory_head=trajectory_head,
        evaluated_frame_count=evaluated_frame_count,
    )
    final_system = system.with_coordinates(
        current.coordinates,
        operation=f"reference_nve_velocity_verlet_steps_{start_step}_to_{current.step}",
        operation_evidence_sha256=checkpoint.checkpoint_sha256,
    )
    return ReferenceNVEResult(
        start_step=start_step,
        end_step=current.step,
        frames=tuple(captured),
        checkpoint=checkpoint,
        system=final_system,
        provenance=provenance,
    )


def run_reference_nve(
    system: AllAtomSystem,
    parameters: ReferenceForceFieldParameters,
    velocities_angstrom_per_ps: torch.Tensor,
    *,
    steps: int,
    config: ReferenceNVEConfig | None = None,
    constraint_config: ReferenceSHAKERATTLEConfig | None = None,
) -> ReferenceNVEResult:
    """Run a fresh bounded NVE segment from one canonical source system."""

    active = ReferenceNVEConfig() if config is None else config
    active_constraints = (
        ReferenceSHAKERATTLEConfig()
        if constraint_config is None
        else constraint_config
    )
    if not isinstance(active, ReferenceNVEConfig):
        raise ReferenceNVEError("config must be ReferenceNVEConfig")
    if not isinstance(active_constraints, ReferenceSHAKERATTLEConfig):
        raise ReferenceNVEError(
            "constraint_config must be ReferenceSHAKERATTLEConfig"
        )
    count = _exact_int(
        steps,
        name="steps",
        minimum=1,
        maximum=MAX_REFERENCE_NVE_STEPS_PER_CALL,
    )
    _require_source_system(system)
    velocity = velocities_angstrom_per_ps
    if not isinstance(velocity, torch.Tensor):
        raise ReferenceNVEError("velocities must be a torch.Tensor")
    if velocity.shape == (system.atom_count, 3):
        velocity = velocity.unsqueeze(0)
    if velocity.shape != (1, system.atom_count, 3):
        raise ReferenceNVEError("velocities must have shape [N,3] or [1,N,3]")
    if velocity.dtype != torch.float64 or velocity.device.type != "cpu":
        raise ReferenceNVEError("velocities must use CPU float64")
    if not bool(torch.isfinite(velocity).all().item()):
        raise ReferenceNVEError("velocities must be finite")
    coordinates = _wrap_coordinates(system.coordinates.detach().clone(), system)
    return _run_segment(
        system,
        parameters,
        active,
        active_constraints,
        coordinates=coordinates,
        velocities=velocity.detach().clone(),
        start_step=0,
        steps=count,
        initial_total_energy=None,
        trajectory_head="",
        evaluated_frame_count=0,
        max_abs_energy_drift=0.0,
        max_abs_position_constraint_residual=0.0,
        max_abs_velocity_constraint_residual=0.0,
        cumulative_shake_iterations=0,
        cumulative_rattle_iterations=0,
    )


def resume_reference_nve(
    source_system: AllAtomSystem,
    parameters: ReferenceForceFieldParameters,
    checkpoint: ReferenceNVECheckpoint,
    *,
    additional_steps: int,
) -> ReferenceNVEResult:
    """Resume only after exact source, parameter, config, and state replay."""

    if not isinstance(checkpoint, ReferenceNVECheckpoint):
        raise ReferenceNVEError("checkpoint type is invalid")
    count = _exact_int(
        additional_steps,
        name="additional_steps",
        minimum=1,
        maximum=MAX_REFERENCE_NVE_STEPS_PER_CALL,
    )
    provenance = _provenance(
        source_system,
        parameters,
        checkpoint.config,
        checkpoint.constraint_config,
    )
    expected = provenance.to_dict()
    observed = {
        "source_system_sha256": checkpoint.source_system_sha256,
        "topology_sha256": checkpoint.topology_sha256,
        "parameter_fingerprint_sha256": checkpoint.parameter_fingerprint_sha256,
        "config_fingerprint_sha256": checkpoint.config.fingerprint_sha256,
        "constraint_config_fingerprint_sha256": (
            checkpoint.constraint_config.fingerprint_sha256
        ),
        "algorithm_id": checkpoint.algorithm_id,
        "device": "cpu",
        "dtype": "float64",
        "torch_version": str(torch.__version__),
    }
    if observed != expected:
        raise ReferenceNVEError(
            "checkpoint source, parameter, config, or runtime provenance mismatch"
        )
    return _run_segment(
        source_system,
        parameters,
        checkpoint.config,
        checkpoint.constraint_config,
        coordinates=checkpoint.coordinates.detach().clone(),
        velocities=checkpoint.velocities_angstrom_per_ps.detach().clone(),
        start_step=checkpoint.step,
        steps=count,
        initial_total_energy=checkpoint.initial_total_energy_kcal_per_mol,
        trajectory_head=checkpoint.trajectory_head_sha256,
        evaluated_frame_count=checkpoint.evaluated_frame_count,
        max_abs_energy_drift=checkpoint.max_abs_energy_drift_kcal_per_mol,
        max_abs_position_constraint_residual=(
            checkpoint.max_abs_position_constraint_residual_angstrom
        ),
        max_abs_velocity_constraint_residual=(
            checkpoint.max_abs_velocity_constraint_residual_angstrom_per_ps
        ),
        cumulative_shake_iterations=(
            checkpoint.cumulative_shake_iteration_count
        ),
        cumulative_rattle_iterations=(
            checkpoint.cumulative_rattle_iteration_count
        ),
        expected_start_frame_sha256=checkpoint.current_frame_sha256,
    )


__all__ = [
    "FORCE_KCAL_PER_MOL_ANGSTROM_TO_ACCELERATION_ANGSTROM_PER_PS2_PER_DA",
    "MAX_REFERENCE_NVE_CHECKPOINT_BYTES",
    "MAX_REFERENCE_NVE_RETAINED_FRAMES",
    "MAX_REFERENCE_NVE_STEPS_PER_CALL",
    "REFERENCE_NVE_ALGORITHM_ID",
    "REFERENCE_NVE_CHECKPOINT_SCHEMA_ID",
    "REFERENCE_NVE_CONFIG_SCHEMA_ID",
    "REFERENCE_NVE_FRAME_SCHEMA_ID",
    "REFERENCE_NVE_RESULT_SCHEMA_ID",
    "REFERENCE_NVE_SCIENTIFIC_BLOCKERS",
    "REFERENCE_NVE_TRAJECTORY_CHAIN_SCHEMA_ID",
    "ReferenceNVECheckpoint",
    "ReferenceNVEConfig",
    "ReferenceNVEError",
    "ReferenceNVEFrame",
    "ReferenceNVEProvenance",
    "ReferenceNVEResult",
    "resume_reference_nve",
    "run_reference_nve",
]
