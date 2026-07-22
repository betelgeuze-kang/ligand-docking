"""Bounded CPU float64 NVT/NPT reference molecular dynamics.

The reference path combines a constrained BAOAB Langevin thermostat with an
optional isotropic molecular-centre Monte Carlo barostat.  It uses a
domain-separated counter random stream whose exact word index is stored in the
checkpoint, rebuilds the compact neighbour list for every force evaluation,
and supports the same optional neutral direct-Ewald path as reference NVE.

This module is an executable protocol reference.  It is not evidence that the
force field, ensemble distribution, finite-difference molecular virial,
thermostat, barostat, or cross-platform random stream has been independently
validated.
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
    UnitCell,
    canonical_system_sha256,
    canonical_topology_sha256,
    require_valid_all_atom_system,
)
from .reference_ewald import (
    ReferenceEwaldConfig,
    ReferenceEwaldError,
    evaluate_reference_force_field_with_ewald,
)
from .reference_forcefield import (
    ReferencePhysicsApplicabilityError,
    evaluate_reference_force_field,
)
from .reference_nve import (
    FORCE_KCAL_PER_MOL_ANGSTROM_TO_ACCELERATION_ANGSTROM_PER_PS2_PER_DA,
)
from .reference_nve_drift import MOLAR_GAS_CONSTANT_KCAL_PER_MOL_K
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


REFERENCE_CANONICAL_ENSEMBLE_ALGORITHM_ID = (
    "cpu_float64_constrained_baoab_langevin_optional_molecular_com_mc_barostat/"
    "1.0.0"
)
REFERENCE_LANGEVIN_THERMOSTAT_CONFIG_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_langevin_thermostat_config/1.0.0"
)
REFERENCE_MONTE_CARLO_BAROSTAT_CONFIG_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_monte_carlo_barostat_config/1.0.0"
)
REFERENCE_CANONICAL_ENSEMBLE_CONFIG_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_canonical_ensemble_config/1.0.0"
)
REFERENCE_CANONICAL_ENSEMBLE_FRAME_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_canonical_ensemble_frame/1.0.0"
)
REFERENCE_BAROSTAT_ATTEMPT_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_barostat_attempt/1.0.0"
)
REFERENCE_CANONICAL_ENSEMBLE_CHECKPOINT_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_canonical_ensemble_checkpoint/1.0.0"
)
REFERENCE_CANONICAL_ENSEMBLE_RESULT_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_canonical_ensemble_result/1.0.0"
)
REFERENCE_CANONICAL_ENSEMBLE_TRAJECTORY_CHAIN_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_canonical_ensemble_trajectory_chain/1.0.0"
)
REFERENCE_BAROSTAT_ATTEMPT_CHAIN_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_barostat_attempt_chain/1.0.0"
)
REFERENCE_COUNTER_RNG_ALGORITHM_ID = "sha256_counter_u64_box_muller/1.0.0"

# The Avogadro constant is exact in SI and one thermochemical calorie is
# exactly 4.184 joules.  This converts bar*angstrom^3 to kcal/mol.
BAR_ANGSTROM3_TO_KCAL_PER_MOL = 1.0e-25 * 6.02214076e23 / 4184.0

MAX_REFERENCE_CANONICAL_ENSEMBLE_STEPS_PER_CALL = 1_000_000
MAX_REFERENCE_CANONICAL_ENSEMBLE_RETAINED_FRAMES = 10_001
MAX_REFERENCE_CANONICAL_ENSEMBLE_BAROSTAT_ATTEMPTS = 100_000
MAX_REFERENCE_CANONICAL_ENSEMBLE_CHECKPOINT_BYTES = 128 * 1024 * 1024
MAX_REFERENCE_COUNTER_RNG_WORD_INDEX = (1 << 63) - 1
MIN_BAROSTAT_VOLUME_RATIO_PER_ATTEMPT = 0.5
MAX_BAROSTAT_VOLUME_RATIO_PER_ATTEMPT = 2.0

REFERENCE_CANONICAL_ENSEMBLE_SCIENTIFIC_BLOCKERS = (
    "caller_supplied_parameter_values_not_independently_reviewed",
    "reference_force_field_not_scientifically_validated",
    "caller_supplied_temperature_pressure_and_integrator_settings_not_reviewed",
    "baoab_langevin_thermostat_not_independently_validated",
    "counter_rng_cross_host_reproducibility_not_validated",
    "molecular_com_mc_barostat_not_independently_validated",
    "finite_difference_molecular_virial_not_independently_validated",
    "nvt_npt_ensemble_acceptance_evidence_missing",
    "equilibration_and_production_length_protocol_missing",
    "autocorrelation_and_effective_sample_size_review_missing",
    "cross_host_reproducibility_missing",
    "cpu_gpu_parity_evidence_missing",
    "pme_not_implemented",
    "net_charge_background_and_triclinic_ewald_not_supported",
    "triclinic_periodic_cells_not_supported",
    "product_integration_not_qualified",
)


class ReferenceCanonicalEnsembleError(ValueError):
    """A canonical-ensemble request or restart failed closed."""


def _finite_float(
    value: object,
    *,
    name: str,
    positive: bool = False,
    nonnegative: bool = False,
) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ReferenceCanonicalEnsembleError(
            f"{name} must be a finite real number"
        )
    number = float(value)
    if not math.isfinite(number):
        raise ReferenceCanonicalEnsembleError(f"{name} must be finite")
    if positive and number <= 0.0:
        raise ReferenceCanonicalEnsembleError(f"{name} must be positive")
    if nonnegative and number < 0.0:
        raise ReferenceCanonicalEnsembleError(f"{name} must be non-negative")
    return number


def _exact_int(
    value: object,
    *,
    name: str,
    minimum: int = 0,
    maximum: int | None = None,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ReferenceCanonicalEnsembleError(f"{name} must be an integer")
    integer = int(value)
    if integer < minimum or (maximum is not None and integer > maximum):
        upper = "" if maximum is None else f" and at most {maximum}"
        raise ReferenceCanonicalEnsembleError(
            f"{name} must be at least {minimum}{upper}"
        )
    return integer


def _digest(value: object, *, name: str) -> str:
    if not isinstance(value, str):
        raise ReferenceCanonicalEnsembleError(f"{name} must be a SHA-256")
    digest = value.strip().lower()
    if len(digest) != 64 or any(
        character not in "0123456789abcdef" for character in digest
    ):
        raise ReferenceCanonicalEnsembleError(
            f"{name} must be a lowercase SHA-256"
        )
    return digest


def _canonical_bytes(payload: object) -> bytes:
    try:
        return json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise ReferenceCanonicalEnsembleError(
            "canonical-ensemble payload is not canonical JSON"
        ) from exc


def _canonical_sha256(payload: object) -> str:
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def _require_float_hex(value: object, *, name: str) -> float:
    if not isinstance(value, str):
        raise ReferenceCanonicalEnsembleError(
            f"{name} must be canonical binary64 hex"
        )
    try:
        number = float.fromhex(value)
    except ValueError as exc:
        raise ReferenceCanonicalEnsembleError(
            f"{name} must be canonical binary64 hex"
        ) from exc
    if not math.isfinite(number) or number.hex() != value:
        raise ReferenceCanonicalEnsembleError(
            f"{name} must be canonical finite binary64 hex"
        )
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
        raise ReferenceCanonicalEnsembleError(
            f"{name} must be finite CPU float64 [1,N,3]"
        )
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
        raise ReferenceCanonicalEnsembleError(
            f"{name} tensor payload shape is invalid"
        )
    shape_raw = value["shape"]
    if (
        not isinstance(shape_raw, list)
        or len(shape_raw) != 3
        or any(
            isinstance(item, bool) or not isinstance(item, int)
            for item in shape_raw
        )
    ):
        raise ReferenceCanonicalEnsembleError(f"{name} tensor shape is invalid")
    shape = tuple(int(item) for item in shape_raw)
    if shape[0] != 1 or shape[1] < 1 or shape[2] != 3:
        raise ReferenceCanonicalEnsembleError(
            f"{name} tensor must have shape [1,N,3]"
        )
    if value["dtype"] != "float64-le":
        raise ReferenceCanonicalEnsembleError(f"{name} tensor dtype is invalid")
    encoded = value["data_base64"]
    if not isinstance(encoded, str):
        raise ReferenceCanonicalEnsembleError(
            f"{name} tensor base64 must be a string"
        )
    try:
        raw = b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ReferenceCanonicalEnsembleError(
            f"{name} tensor base64 is invalid"
        ) from exc
    if b64encode(raw).decode("ascii") != encoded:
        raise ReferenceCanonicalEnsembleError(
            f"{name} tensor base64 is not canonical"
        )
    if len(raw) != math.prod(shape) * 8:
        raise ReferenceCanonicalEnsembleError(
            f"{name} tensor byte length is invalid"
        )
    if hashlib.sha256(raw).hexdigest() != _digest(
        value["data_sha256"],
        name=f"{name} data_sha256",
    ):
        raise ReferenceCanonicalEnsembleError(f"{name} tensor digest mismatch")
    rows = [item[0] for item in struct.iter_unpack("<d", raw)]
    tensor = torch.tensor(rows, dtype=torch.float64).reshape(shape)
    if not bool(torch.isfinite(tensor).all().item()):
        raise ReferenceCanonicalEnsembleError(
            f"{name} tensor contains non-finite values"
        )
    if _tensor_payload(tensor, name=name) != dict(value):
        raise ReferenceCanonicalEnsembleError(
            f"{name} tensor payload is not canonical"
        )
    return tensor


def _cell_lengths_payload(
    value: tuple[float, float, float] | None,
) -> list[str] | None:
    if value is None:
        return None
    return [item.hex() for item in value]


def _cell_lengths_from_payload(
    value: object,
) -> tuple[float, float, float] | None:
    if value is None:
        return None
    if not isinstance(value, list) or len(value) != 3:
        raise ReferenceCanonicalEnsembleError(
            "cell lengths payload must contain three values"
        )
    return tuple(
        _require_float_hex(item, name=f"cell_lengths_angstrom[{index}]")
        for index, item in enumerate(value)
    )


@dataclass(frozen=True)
class ReferenceLangevinThermostatConfig:
    temperature_kelvin: float = 300.0
    collision_rate_per_ps: float = 1.0
    random_seed: int = 20260722
    schema_id: str = REFERENCE_LANGEVIN_THERMOSTAT_CONFIG_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != REFERENCE_LANGEVIN_THERMOSTAT_CONFIG_SCHEMA_ID:
            raise ReferenceCanonicalEnsembleError(
                "unsupported Langevin thermostat config schema"
            )
        temperature = _finite_float(
            self.temperature_kelvin,
            name="temperature_kelvin",
            positive=True,
        )
        if temperature > 10_000.0:
            raise ReferenceCanonicalEnsembleError(
                "temperature_kelvin exceeds the bounded limit 10000 K"
            )
        collision = _finite_float(
            self.collision_rate_per_ps,
            name="collision_rate_per_ps",
            positive=True,
        )
        if collision > 10_000.0:
            raise ReferenceCanonicalEnsembleError(
                "collision_rate_per_ps exceeds the bounded limit 10000"
            )
        seed = _exact_int(
            self.random_seed,
            name="random_seed",
            minimum=0,
            maximum=(1 << 64) - 1,
        )
        object.__setattr__(self, "temperature_kelvin", temperature)
        object.__setattr__(self, "collision_rate_per_ps", collision)
        object.__setattr__(self, "random_seed", seed)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "temperature_kelvin_hex": self.temperature_kelvin.hex(),
            "collision_rate_per_ps_hex": self.collision_rate_per_ps.hex(),
            "random_seed": self.random_seed,
            "random_algorithm_id": REFERENCE_COUNTER_RNG_ALGORITHM_ID,
            "center_of_mass_motion_policy": (
                "remove_initial_and_after_each_ornstein_uhlenbeck_step"
            ),
        }

    @classmethod
    def from_dict(
        cls,
        value: object,
    ) -> "ReferenceLangevinThermostatConfig":
        expected = {
            "schema_id",
            "temperature_kelvin_hex",
            "collision_rate_per_ps_hex",
            "random_seed",
            "random_algorithm_id",
            "center_of_mass_motion_policy",
        }
        if not isinstance(value, Mapping) or set(value) != expected:
            raise ReferenceCanonicalEnsembleError(
                "Langevin thermostat config payload is invalid"
            )
        if value["random_algorithm_id"] != REFERENCE_COUNTER_RNG_ALGORITHM_ID:
            raise ReferenceCanonicalEnsembleError(
                "unsupported thermostat random algorithm"
            )
        if value["center_of_mass_motion_policy"] != (
            "remove_initial_and_after_each_ornstein_uhlenbeck_step"
        ):
            raise ReferenceCanonicalEnsembleError(
                "unsupported center-of-mass motion policy"
            )
        result = cls(
            temperature_kelvin=_require_float_hex(
                value["temperature_kelvin_hex"],
                name="temperature_kelvin_hex",
            ),
            collision_rate_per_ps=_require_float_hex(
                value["collision_rate_per_ps_hex"],
                name="collision_rate_per_ps_hex",
            ),
            random_seed=_exact_int(
                value["random_seed"],
                name="random_seed",
                minimum=0,
                maximum=(1 << 64) - 1,
            ),
            schema_id=str(value["schema_id"]),
        )
        if result.to_dict() != dict(value):
            raise ReferenceCanonicalEnsembleError(
                "Langevin thermostat config is not canonical"
            )
        return result

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())


@dataclass(frozen=True)
class ReferenceMonteCarloBarostatConfig:
    pressure_bar: float = 1.0
    interval_steps: int = 25
    max_delta_volume_angstrom3: float = 50.0
    pressure_observation_stride: int = 25
    pressure_log_length_step: float = 1.0e-5
    schema_id: str = REFERENCE_MONTE_CARLO_BAROSTAT_CONFIG_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != REFERENCE_MONTE_CARLO_BAROSTAT_CONFIG_SCHEMA_ID:
            raise ReferenceCanonicalEnsembleError(
                "unsupported Monte Carlo barostat config schema"
            )
        pressure = _finite_float(self.pressure_bar, name="pressure_bar")
        if abs(pressure) > 1.0e6:
            raise ReferenceCanonicalEnsembleError(
                "absolute pressure_bar exceeds the bounded limit 1e6 bar"
            )
        delta = _finite_float(
            self.max_delta_volume_angstrom3,
            name="max_delta_volume_angstrom3",
            positive=True,
        )
        log_step = _finite_float(
            self.pressure_log_length_step,
            name="pressure_log_length_step",
            positive=True,
        )
        if log_step < 1.0e-8 or log_step > 1.0e-2:
            raise ReferenceCanonicalEnsembleError(
                "pressure_log_length_step must be in [1e-8, 1e-2]"
            )
        object.__setattr__(self, "pressure_bar", pressure)
        object.__setattr__(
            self,
            "interval_steps",
            _exact_int(
                self.interval_steps,
                name="interval_steps",
                minimum=1,
                maximum=MAX_REFERENCE_CANONICAL_ENSEMBLE_STEPS_PER_CALL,
            ),
        )
        object.__setattr__(self, "max_delta_volume_angstrom3", delta)
        object.__setattr__(
            self,
            "pressure_observation_stride",
            _exact_int(
                self.pressure_observation_stride,
                name="pressure_observation_stride",
                minimum=1,
                maximum=MAX_REFERENCE_CANONICAL_ENSEMBLE_STEPS_PER_CALL,
            ),
        )
        object.__setattr__(self, "pressure_log_length_step", log_step)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "pressure_bar_hex": self.pressure_bar.hex(),
            "interval_steps": self.interval_steps,
            "max_delta_volume_angstrom3_hex": (
                self.max_delta_volume_angstrom3.hex()
            ),
            "pressure_observation_stride": self.pressure_observation_stride,
            "pressure_log_length_step_hex": (
                self.pressure_log_length_step.hex()
            ),
            "proposal_policy": "fixed_absolute_uniform_delta_volume",
            "coordinate_scaling_policy": "mass_weighted_molecular_centres_only",
            "jacobian_policy": "molecular_component_count_log_volume_ratio",
            "pressure_policy": "central_difference_molecular_virial",
        }

    @classmethod
    def from_dict(
        cls,
        value: object,
    ) -> "ReferenceMonteCarloBarostatConfig":
        expected = {
            "schema_id",
            "pressure_bar_hex",
            "interval_steps",
            "max_delta_volume_angstrom3_hex",
            "pressure_observation_stride",
            "pressure_log_length_step_hex",
            "proposal_policy",
            "coordinate_scaling_policy",
            "jacobian_policy",
            "pressure_policy",
        }
        if not isinstance(value, Mapping) or set(value) != expected:
            raise ReferenceCanonicalEnsembleError(
                "Monte Carlo barostat config payload is invalid"
            )
        policies = {
            "proposal_policy": "fixed_absolute_uniform_delta_volume",
            "coordinate_scaling_policy": (
                "mass_weighted_molecular_centres_only"
            ),
            "jacobian_policy": (
                "molecular_component_count_log_volume_ratio"
            ),
            "pressure_policy": "central_difference_molecular_virial",
        }
        for key, expected_value in policies.items():
            if value[key] != expected_value:
                raise ReferenceCanonicalEnsembleError(
                    f"unsupported barostat {key}"
                )
        result = cls(
            pressure_bar=_require_float_hex(
                value["pressure_bar_hex"],
                name="pressure_bar_hex",
            ),
            interval_steps=_exact_int(
                value["interval_steps"],
                name="interval_steps",
                minimum=1,
            ),
            max_delta_volume_angstrom3=_require_float_hex(
                value["max_delta_volume_angstrom3_hex"],
                name="max_delta_volume_angstrom3_hex",
            ),
            pressure_observation_stride=_exact_int(
                value["pressure_observation_stride"],
                name="pressure_observation_stride",
                minimum=1,
            ),
            pressure_log_length_step=_require_float_hex(
                value["pressure_log_length_step_hex"],
                name="pressure_log_length_step_hex",
            ),
            schema_id=str(value["schema_id"]),
        )
        if result.to_dict() != dict(value):
            raise ReferenceCanonicalEnsembleError(
                "Monte Carlo barostat config is not canonical"
            )
        return result

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())


@dataclass(frozen=True)
class ReferenceCanonicalEnsembleConfig:
    timestep_ps: float = 0.001
    trajectory_stride: int = 1
    max_neighbors: int = 256
    max_atoms_per_cell: int = 256
    thermostat: ReferenceLangevinThermostatConfig = (
        ReferenceLangevinThermostatConfig()
    )
    barostat: ReferenceMonteCarloBarostatConfig | None = None
    ewald_config: ReferenceEwaldConfig | None = None
    schema_id: str = REFERENCE_CANONICAL_ENSEMBLE_CONFIG_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != REFERENCE_CANONICAL_ENSEMBLE_CONFIG_SCHEMA_ID:
            raise ReferenceCanonicalEnsembleError(
                "unsupported canonical-ensemble config schema"
            )
        timestep = _finite_float(
            self.timestep_ps,
            name="timestep_ps",
            positive=True,
        )
        if timestep > 0.1:
            raise ReferenceCanonicalEnsembleError(
                "timestep_ps exceeds the bounded limit 0.1 ps"
            )
        if not isinstance(self.thermostat, ReferenceLangevinThermostatConfig):
            raise ReferenceCanonicalEnsembleError(
                "thermostat must be ReferenceLangevinThermostatConfig"
            )
        if self.barostat is not None and not isinstance(
            self.barostat,
            ReferenceMonteCarloBarostatConfig,
        ):
            raise ReferenceCanonicalEnsembleError(
                "barostat must be ReferenceMonteCarloBarostatConfig or None"
            )
        if self.ewald_config is not None and not isinstance(
            self.ewald_config,
            ReferenceEwaldConfig,
        ):
            raise ReferenceCanonicalEnsembleError(
                "ewald_config must be ReferenceEwaldConfig or None"
            )
        object.__setattr__(self, "timestep_ps", timestep)
        object.__setattr__(
            self,
            "trajectory_stride",
            _exact_int(
                self.trajectory_stride,
                name="trajectory_stride",
                minimum=1,
                maximum=MAX_REFERENCE_CANONICAL_ENSEMBLE_STEPS_PER_CALL,
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

    @property
    def ensemble(self) -> str:
        return "NVT" if self.barostat is None else "NPT"

    @property
    def electrostatics_mode(self) -> str:
        return (
            "screened_coulomb_v1"
            if self.ewald_config is None
            else "neutral_direct_ewald_v1"
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "algorithm_id": REFERENCE_CANONICAL_ENSEMBLE_ALGORITHM_ID,
            "ensemble": self.ensemble,
            "timestep_ps_hex": self.timestep_ps.hex(),
            "trajectory_stride": self.trajectory_stride,
            "max_neighbors": self.max_neighbors,
            "max_atoms_per_cell": self.max_atoms_per_cell,
            "thermostat": self.thermostat.to_dict(),
            "barostat": None if self.barostat is None else self.barostat.to_dict(),
            "electrostatics_mode": self.electrostatics_mode,
            "ewald_config": (
                None if self.ewald_config is None else self.ewald_config.to_dict()
            ),
            "splitting": "B-A-O-A-B",
            "constraint_policy": "SHAKE_after_each_A_and_RATTLE_after_O_and_final_B",
            "neighbor_rebuild_policy": "every_force_evaluation",
            "periodic_policy": "NVT_none_or_full_orthorhombic_NPT_full_orthorhombic",
        }

    @classmethod
    def from_dict(cls, value: object) -> "ReferenceCanonicalEnsembleConfig":
        expected = {
            "schema_id",
            "algorithm_id",
            "ensemble",
            "timestep_ps_hex",
            "trajectory_stride",
            "max_neighbors",
            "max_atoms_per_cell",
            "thermostat",
            "barostat",
            "electrostatics_mode",
            "ewald_config",
            "splitting",
            "constraint_policy",
            "neighbor_rebuild_policy",
            "periodic_policy",
        }
        if not isinstance(value, Mapping) or set(value) != expected:
            raise ReferenceCanonicalEnsembleError(
                "canonical-ensemble config payload is invalid"
            )
        if value["algorithm_id"] != REFERENCE_CANONICAL_ENSEMBLE_ALGORITHM_ID:
            raise ReferenceCanonicalEnsembleError(
                "unsupported canonical-ensemble algorithm"
            )
        fixed = {
            "splitting": "B-A-O-A-B",
            "constraint_policy": (
                "SHAKE_after_each_A_and_RATTLE_after_O_and_final_B"
            ),
            "neighbor_rebuild_policy": "every_force_evaluation",
            "periodic_policy": (
                "NVT_none_or_full_orthorhombic_NPT_full_orthorhombic"
            ),
        }
        for key, expected_value in fixed.items():
            if value[key] != expected_value:
                raise ReferenceCanonicalEnsembleError(
                    f"unsupported canonical-ensemble {key}"
                )
        thermostat = ReferenceLangevinThermostatConfig.from_dict(
            value["thermostat"]
        )
        barostat_payload = value["barostat"]
        barostat = (
            None
            if barostat_payload is None
            else ReferenceMonteCarloBarostatConfig.from_dict(barostat_payload)
        )
        if value["ensemble"] != ("NVT" if barostat is None else "NPT"):
            raise ReferenceCanonicalEnsembleError(
                "ensemble label does not match barostat presence"
            )
        mode = value["electrostatics_mode"]
        ewald_payload = value["ewald_config"]
        if mode == "screened_coulomb_v1":
            if ewald_payload is not None:
                raise ReferenceCanonicalEnsembleError(
                    "screened Coulomb mode cannot carry an Ewald config"
                )
            ewald = None
        elif mode == "neutral_direct_ewald_v1":
            try:
                ewald = ReferenceEwaldConfig.from_dict(ewald_payload)
            except ReferenceEwaldError as exc:
                raise ReferenceCanonicalEnsembleError(
                    "canonical-ensemble Ewald config is invalid"
                ) from exc
        else:
            raise ReferenceCanonicalEnsembleError(
                "unsupported canonical-ensemble electrostatics mode"
            )
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
            thermostat=thermostat,
            barostat=barostat,
            ewald_config=ewald,
            schema_id=str(value["schema_id"]),
        )
        if result.to_dict() != dict(value):
            raise ReferenceCanonicalEnsembleError(
                "canonical-ensemble config is not canonical"
            )
        return result

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())


@dataclass(frozen=True)
class ReferenceBarostatAttempt:
    step: int
    old_volume_angstrom3: float
    proposed_volume_angstrom3: float
    proposal_uniform: float
    acceptance_uniform: float
    old_potential_energy_kcal_per_mol: float
    proposed_potential_energy_kcal_per_mol: float | None
    pressure_work_kcal_per_mol: float | None
    jacobian_log_term: float | None
    log_acceptance_probability: float | None
    molecule_count: int
    accepted: bool
    disposition: str
    schema_id: str = REFERENCE_BAROSTAT_ATTEMPT_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != REFERENCE_BAROSTAT_ATTEMPT_SCHEMA_ID:
            raise ReferenceCanonicalEnsembleError(
                "unsupported barostat attempt schema"
            )
        object.__setattr__(self, "step", _exact_int(self.step, name="step", minimum=1))
        object.__setattr__(
            self,
            "old_volume_angstrom3",
            _finite_float(
                self.old_volume_angstrom3,
                name="old_volume_angstrom3",
                positive=True,
            ),
        )
        object.__setattr__(
            self,
            "proposed_volume_angstrom3",
            _finite_float(
                self.proposed_volume_angstrom3,
                name="proposed_volume_angstrom3",
            ),
        )
        for name in ("proposal_uniform", "acceptance_uniform"):
            value = _finite_float(getattr(self, name), name=name, positive=True)
            if value >= 1.0:
                raise ReferenceCanonicalEnsembleError(f"{name} must be below 1")
            object.__setattr__(self, name, value)
        object.__setattr__(
            self,
            "old_potential_energy_kcal_per_mol",
            _finite_float(
                self.old_potential_energy_kcal_per_mol,
                name="old_potential_energy_kcal_per_mol",
            ),
        )
        for name in (
            "proposed_potential_energy_kcal_per_mol",
            "pressure_work_kcal_per_mol",
            "jacobian_log_term",
            "log_acceptance_probability",
        ):
            raw = getattr(self, name)
            if raw is not None:
                object.__setattr__(self, name, _finite_float(raw, name=name))
        object.__setattr__(
            self,
            "molecule_count",
            _exact_int(self.molecule_count, name="molecule_count", minimum=1),
        )
        allowed = {"accepted", "metropolis_rejected", "domain_rejected"}
        if self.disposition not in allowed:
            raise ReferenceCanonicalEnsembleError(
                "unsupported barostat attempt disposition"
            )
        if self.accepted != (self.disposition == "accepted"):
            raise ReferenceCanonicalEnsembleError(
                "barostat accepted flag and disposition disagree"
            )
        complete = all(
            getattr(self, name) is not None
            for name in (
                "proposed_potential_energy_kcal_per_mol",
                "pressure_work_kcal_per_mol",
                "jacobian_log_term",
                "log_acceptance_probability",
            )
        )
        if (self.disposition == "domain_rejected") == complete:
            raise ReferenceCanonicalEnsembleError(
                "barostat attempt numeric disposition is inconsistent"
            )

    def to_dict(self) -> dict[str, object]:
        def optional_hex(value: float | None) -> str | None:
            return None if value is None else value.hex()

        return {
            "schema_id": self.schema_id,
            "step": self.step,
            "old_volume_angstrom3_hex": self.old_volume_angstrom3.hex(),
            "proposed_volume_angstrom3_hex": (
                self.proposed_volume_angstrom3.hex()
            ),
            "proposal_uniform_hex": self.proposal_uniform.hex(),
            "acceptance_uniform_hex": self.acceptance_uniform.hex(),
            "old_potential_energy_kcal_per_mol_hex": (
                self.old_potential_energy_kcal_per_mol.hex()
            ),
            "proposed_potential_energy_kcal_per_mol_hex": optional_hex(
                self.proposed_potential_energy_kcal_per_mol
            ),
            "pressure_work_kcal_per_mol_hex": optional_hex(
                self.pressure_work_kcal_per_mol
            ),
            "jacobian_log_term_hex": optional_hex(self.jacobian_log_term),
            "log_acceptance_probability_hex": optional_hex(
                self.log_acceptance_probability
            ),
            "molecule_count": self.molecule_count,
            "accepted": self.accepted,
            "disposition": self.disposition,
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())


@dataclass(frozen=True)
class ReferenceCanonicalEnsembleFrame:
    step: int
    time_ps: float
    coordinates: torch.Tensor
    velocities_angstrom_per_ps: torch.Tensor
    cell_lengths_angstrom: tuple[float, float, float] | None
    potential_energy_kcal_per_mol: float
    kinetic_energy_kcal_per_mol: float
    total_energy_kcal_per_mol: float
    kinetic_temperature_kelvin: float
    volume_angstrom3: float | None
    instantaneous_pressure_bar: float | None
    max_abs_position_constraint_residual_angstrom: float
    max_abs_velocity_constraint_residual_angstrom_per_ps: float
    cumulative_shake_iteration_count: int
    cumulative_rattle_iteration_count: int
    cumulative_barostat_attempt_count: int
    cumulative_barostat_accept_count: int
    cumulative_barostat_reject_count: int
    random_word_index: int
    schema_id: str = REFERENCE_CANONICAL_ENSEMBLE_FRAME_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != REFERENCE_CANONICAL_ENSEMBLE_FRAME_SCHEMA_ID:
            raise ReferenceCanonicalEnsembleError(
                "unsupported canonical-ensemble frame schema"
            )
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
        if _tensor_payload(coordinates, name="frame coordinates")["shape"] != (
            _tensor_payload(velocities, name="frame velocities")["shape"]
        ):
            raise ReferenceCanonicalEnsembleError(
                "frame coordinate and velocity shapes differ"
            )
        object.__setattr__(self, "coordinates", coordinates)
        object.__setattr__(self, "velocities_angstrom_per_ps", velocities)
        if self.cell_lengths_angstrom is not None:
            if len(self.cell_lengths_angstrom) != 3:
                raise ReferenceCanonicalEnsembleError(
                    "frame cell lengths must contain three values"
                )
            lengths = tuple(
                _finite_float(item, name="frame cell length", positive=True)
                for item in self.cell_lengths_angstrom
            )
            object.__setattr__(self, "cell_lengths_angstrom", lengths)
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
            raise ReferenceCanonicalEnsembleError(
                "frame total energy does not equal potential plus kinetic"
            )
        object.__setattr__(self, "potential_energy_kcal_per_mol", potential)
        object.__setattr__(self, "kinetic_energy_kcal_per_mol", kinetic)
        object.__setattr__(self, "total_energy_kcal_per_mol", total)
        object.__setattr__(
            self,
            "kinetic_temperature_kelvin",
            _finite_float(
                self.kinetic_temperature_kelvin,
                name="frame kinetic temperature",
                nonnegative=True,
            ),
        )
        if self.volume_angstrom3 is not None:
            volume = _finite_float(
                self.volume_angstrom3,
                name="frame volume",
                positive=True,
            )
            if self.cell_lengths_angstrom is None:
                raise ReferenceCanonicalEnsembleError(
                    "frame volume requires periodic cell lengths"
                )
            expected_volume = math.prod(self.cell_lengths_angstrom)
            if volume.hex() != expected_volume.hex():
                raise ReferenceCanonicalEnsembleError(
                    "frame volume does not match cell lengths"
                )
            object.__setattr__(self, "volume_angstrom3", volume)
        elif self.cell_lengths_angstrom is not None:
            raise ReferenceCanonicalEnsembleError(
                "periodic frame must record volume"
            )
        if self.instantaneous_pressure_bar is not None:
            object.__setattr__(
                self,
                "instantaneous_pressure_bar",
                _finite_float(
                    self.instantaneous_pressure_bar,
                    name="frame instantaneous pressure",
                ),
            )
            if self.volume_angstrom3 is None:
                raise ReferenceCanonicalEnsembleError(
                    "pressure observation requires a periodic volume"
                )
        for name in (
            "max_abs_position_constraint_residual_angstrom",
            "max_abs_velocity_constraint_residual_angstrom_per_ps",
        ):
            object.__setattr__(
                self,
                name,
                _finite_float(getattr(self, name), name=name, nonnegative=True),
            )
        for name in (
            "cumulative_shake_iteration_count",
            "cumulative_rattle_iteration_count",
            "cumulative_barostat_attempt_count",
            "cumulative_barostat_accept_count",
            "cumulative_barostat_reject_count",
        ):
            object.__setattr__(
                self,
                name,
                _exact_int(getattr(self, name), name=name, minimum=0),
            )
        if self.cumulative_barostat_attempt_count != (
            self.cumulative_barostat_accept_count
            + self.cumulative_barostat_reject_count
        ):
            raise ReferenceCanonicalEnsembleError(
                "frame barostat counts are inconsistent"
            )
        object.__setattr__(
            self,
            "random_word_index",
            _exact_int(
                self.random_word_index,
                name="random_word_index",
                minimum=0,
                maximum=MAX_REFERENCE_COUNTER_RNG_WORD_INDEX,
            ),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "step": self.step,
            "time_ps_hex": self.time_ps.hex(),
            "coordinates": _tensor_payload(
                self.coordinates,
                name="frame coordinates",
            ),
            "velocities_angstrom_per_ps": _tensor_payload(
                self.velocities_angstrom_per_ps,
                name="frame velocities",
            ),
            "cell_lengths_angstrom_hex": _cell_lengths_payload(
                self.cell_lengths_angstrom
            ),
            "potential_energy_kcal_per_mol_hex": (
                self.potential_energy_kcal_per_mol.hex()
            ),
            "kinetic_energy_kcal_per_mol_hex": (
                self.kinetic_energy_kcal_per_mol.hex()
            ),
            "total_energy_kcal_per_mol_hex": (
                self.total_energy_kcal_per_mol.hex()
            ),
            "kinetic_temperature_kelvin_hex": (
                self.kinetic_temperature_kelvin.hex()
            ),
            "volume_angstrom3_hex": (
                None if self.volume_angstrom3 is None else self.volume_angstrom3.hex()
            ),
            "instantaneous_pressure_bar_hex": (
                None
                if self.instantaneous_pressure_bar is None
                else self.instantaneous_pressure_bar.hex()
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
            "cumulative_barostat_attempt_count": (
                self.cumulative_barostat_attempt_count
            ),
            "cumulative_barostat_accept_count": (
                self.cumulative_barostat_accept_count
            ),
            "cumulative_barostat_reject_count": (
                self.cumulative_barostat_reject_count
            ),
            "random_word_index": self.random_word_index,
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())


@dataclass(frozen=True)
class ReferenceCanonicalEnsembleProvenance:
    source_system_sha256: str
    topology_sha256: str
    parameter_fingerprint_sha256: str
    config_fingerprint_sha256: str
    constraint_config_fingerprint_sha256: str
    algorithm_id: str = REFERENCE_CANONICAL_ENSEMBLE_ALGORITHM_ID
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
        if self.algorithm_id != REFERENCE_CANONICAL_ENSEMBLE_ALGORITHM_ID:
            raise ReferenceCanonicalEnsembleError(
                "unsupported provenance algorithm"
            )
        if self.device != "cpu" or self.dtype != "float64":
            raise ReferenceCanonicalEnsembleError(
                "canonical-ensemble provenance requires CPU float64"
            )
        if self.torch_version != str(torch.__version__):
            raise ReferenceCanonicalEnsembleError(
                "canonical-ensemble torch runtime mismatch"
            )

    def to_dict(self) -> dict[str, object]:
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
            "random_algorithm_id": REFERENCE_COUNTER_RNG_ALGORITHM_ID,
        }


def _trajectory_head(
    previous: str,
    frame: ReferenceCanonicalEnsembleFrame,
    frame_count: int,
) -> str:
    if previous:
        _digest(previous, name="previous trajectory head")
    return _canonical_sha256(
        {
            "schema_id": REFERENCE_CANONICAL_ENSEMBLE_TRAJECTORY_CHAIN_SCHEMA_ID,
            "frame_count": frame_count,
            "previous_head_sha256": previous,
            "frame_sha256": frame.fingerprint_sha256,
        }
    )


def _barostat_head(
    previous: str,
    attempt: ReferenceBarostatAttempt,
    attempt_count: int,
) -> str:
    if previous:
        _digest(previous, name="previous barostat head")
    return _canonical_sha256(
        {
            "schema_id": REFERENCE_BAROSTAT_ATTEMPT_CHAIN_SCHEMA_ID,
            "attempt_count": attempt_count,
            "previous_head_sha256": previous,
            "attempt_sha256": attempt.fingerprint_sha256,
        }
    )


@dataclass(frozen=True)
class ReferenceCanonicalEnsembleCheckpoint:
    source_system_sha256: str
    topology_sha256: str
    parameter_fingerprint_sha256: str
    config: ReferenceCanonicalEnsembleConfig
    constraint_config: ReferenceSHAKERATTLEConfig
    step: int
    time_ps: float
    coordinates: torch.Tensor
    velocities_angstrom_per_ps: torch.Tensor
    cell_lengths_angstrom: tuple[float, float, float] | None
    current_potential_energy_kcal_per_mol: float
    current_kinetic_energy_kcal_per_mol: float
    current_total_energy_kcal_per_mol: float
    current_kinetic_temperature_kelvin: float
    current_instantaneous_pressure_bar: float | None
    max_abs_position_constraint_residual_angstrom: float
    max_abs_velocity_constraint_residual_angstrom_per_ps: float
    cumulative_shake_iteration_count: int
    cumulative_rattle_iteration_count: int
    cumulative_barostat_attempt_count: int
    cumulative_barostat_accept_count: int
    cumulative_barostat_reject_count: int
    random_word_index: int
    current_frame_sha256: str
    trajectory_head_sha256: str
    evaluated_frame_count: int
    barostat_head_sha256: str
    schema_id: str = REFERENCE_CANONICAL_ENSEMBLE_CHECKPOINT_SCHEMA_ID
    algorithm_id: str = REFERENCE_CANONICAL_ENSEMBLE_ALGORITHM_ID
    device: str = "cpu"
    dtype: str = "float64"
    torch_version: str = str(torch.__version__)

    def __post_init__(self) -> None:
        if self.schema_id != REFERENCE_CANONICAL_ENSEMBLE_CHECKPOINT_SCHEMA_ID:
            raise ReferenceCanonicalEnsembleError(
                "unsupported canonical-ensemble checkpoint schema"
            )
        if self.algorithm_id != REFERENCE_CANONICAL_ENSEMBLE_ALGORITHM_ID:
            raise ReferenceCanonicalEnsembleError(
                "unsupported canonical-ensemble checkpoint algorithm"
            )
        if self.device != "cpu" or self.dtype != "float64":
            raise ReferenceCanonicalEnsembleError(
                "canonical-ensemble checkpoint requires CPU float64"
            )
        version = str(self.torch_version).strip()
        if not version:
            raise ReferenceCanonicalEnsembleError(
                "canonical-ensemble checkpoint requires a Torch runtime version"
            )
        object.__setattr__(self, "torch_version", version)
        for name in (
            "source_system_sha256",
            "topology_sha256",
            "parameter_fingerprint_sha256",
            "current_frame_sha256",
            "trajectory_head_sha256",
        ):
            object.__setattr__(self, name, _digest(getattr(self, name), name=name))
        if not isinstance(self.config, ReferenceCanonicalEnsembleConfig):
            raise ReferenceCanonicalEnsembleError(
                "checkpoint config type is invalid"
            )
        if not isinstance(self.constraint_config, ReferenceSHAKERATTLEConfig):
            raise ReferenceCanonicalEnsembleError(
                "checkpoint constraint config type is invalid"
            )
        step = _exact_int(self.step, name="checkpoint step", minimum=0)
        object.__setattr__(self, "step", step)
        time_ps = _finite_float(
            self.time_ps,
            name="checkpoint time",
            nonnegative=True,
        )
        if time_ps.hex() != (step * self.config.timestep_ps).hex():
            raise ReferenceCanonicalEnsembleError(
                "checkpoint time does not match step times timestep"
            )
        object.__setattr__(self, "time_ps", time_ps)
        coordinates = self.coordinates.detach().clone()
        velocities = self.velocities_angstrom_per_ps.detach().clone()
        if _tensor_payload(coordinates, name="checkpoint coordinates")["shape"] != (
            _tensor_payload(velocities, name="checkpoint velocities")["shape"]
        ):
            raise ReferenceCanonicalEnsembleError(
                "checkpoint coordinate and velocity shapes differ"
            )
        object.__setattr__(self, "coordinates", coordinates)
        object.__setattr__(self, "velocities_angstrom_per_ps", velocities)
        lengths = self.cell_lengths_angstrom
        if lengths is not None:
            if len(lengths) != 3:
                raise ReferenceCanonicalEnsembleError(
                    "checkpoint cell lengths must contain three values"
                )
            lengths = tuple(
                _finite_float(item, name="checkpoint cell length", positive=True)
                for item in lengths
            )
            object.__setattr__(self, "cell_lengths_angstrom", lengths)
        if self.config.barostat is not None and lengths is None:
            raise ReferenceCanonicalEnsembleError(
                "NPT checkpoint requires periodic cell lengths"
            )
        for name in (
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
                name="current_kinetic_energy_kcal_per_mol",
                nonnegative=True,
            ),
        )
        if self.current_total_energy_kcal_per_mol.hex() != (
            self.current_potential_energy_kcal_per_mol
            + self.current_kinetic_energy_kcal_per_mol
        ).hex():
            raise ReferenceCanonicalEnsembleError(
                "checkpoint total energy is inconsistent"
            )
        object.__setattr__(
            self,
            "current_kinetic_temperature_kelvin",
            _finite_float(
                self.current_kinetic_temperature_kelvin,
                name="current_kinetic_temperature_kelvin",
                nonnegative=True,
            ),
        )
        if self.current_instantaneous_pressure_bar is not None:
            object.__setattr__(
                self,
                "current_instantaneous_pressure_bar",
                _finite_float(
                    self.current_instantaneous_pressure_bar,
                    name="current_instantaneous_pressure_bar",
                ),
            )
        for name in (
            "max_abs_position_constraint_residual_angstrom",
            "max_abs_velocity_constraint_residual_angstrom_per_ps",
        ):
            object.__setattr__(
                self,
                name,
                _finite_float(getattr(self, name), name=name, nonnegative=True),
            )
        for name in (
            "cumulative_shake_iteration_count",
            "cumulative_rattle_iteration_count",
            "cumulative_barostat_attempt_count",
            "cumulative_barostat_accept_count",
            "cumulative_barostat_reject_count",
        ):
            object.__setattr__(
                self,
                name,
                _exact_int(getattr(self, name), name=name, minimum=0),
            )
        if self.cumulative_barostat_attempt_count != (
            self.cumulative_barostat_accept_count
            + self.cumulative_barostat_reject_count
        ):
            raise ReferenceCanonicalEnsembleError(
                "checkpoint barostat counts are inconsistent"
            )
        expected_attempt_count = (
            0
            if self.config.barostat is None
            else step // self.config.barostat.interval_steps
        )
        if self.cumulative_barostat_attempt_count != expected_attempt_count:
            raise ReferenceCanonicalEnsembleError(
                "checkpoint barostat attempt count does not match step"
            )
        if expected_attempt_count == 0:
            if self.barostat_head_sha256 != "":
                raise ReferenceCanonicalEnsembleError(
                    "empty barostat trace must have an empty head"
                )
        else:
            object.__setattr__(
                self,
                "barostat_head_sha256",
                _digest(self.barostat_head_sha256, name="barostat_head_sha256"),
            )
        random_word_index = _exact_int(
            self.random_word_index,
            name="random_word_index",
            minimum=0,
            maximum=MAX_REFERENCE_COUNTER_RNG_WORD_INDEX,
        )
        atom_count = int(coordinates.shape[1])
        normal_words_per_step = 2 * math.ceil((3 * atom_count) / 2)
        expected_random_words = (
            step * normal_words_per_step + 2 * expected_attempt_count
        )
        if random_word_index != expected_random_words:
            raise ReferenceCanonicalEnsembleError(
                "checkpoint random word index does not match deterministic draw policy"
            )
        object.__setattr__(self, "random_word_index", random_word_index)
        count = _exact_int(
            self.evaluated_frame_count,
            name="evaluated_frame_count",
            minimum=1,
        )
        if count != step + 1:
            raise ReferenceCanonicalEnsembleError(
                "checkpoint evaluated frame count must equal step plus one"
            )
        object.__setattr__(self, "evaluated_frame_count", count)
        frame = self.current_frame
        if frame.fingerprint_sha256 != self.current_frame_sha256:
            raise ReferenceCanonicalEnsembleError(
                "checkpoint current frame fingerprint mismatch"
            )

    @property
    def current_frame(self) -> ReferenceCanonicalEnsembleFrame:
        volume = (
            None
            if self.cell_lengths_angstrom is None
            else math.prod(self.cell_lengths_angstrom)
        )
        return ReferenceCanonicalEnsembleFrame(
            step=self.step,
            time_ps=self.time_ps,
            coordinates=self.coordinates,
            velocities_angstrom_per_ps=self.velocities_angstrom_per_ps,
            cell_lengths_angstrom=self.cell_lengths_angstrom,
            potential_energy_kcal_per_mol=(
                self.current_potential_energy_kcal_per_mol
            ),
            kinetic_energy_kcal_per_mol=self.current_kinetic_energy_kcal_per_mol,
            total_energy_kcal_per_mol=self.current_total_energy_kcal_per_mol,
            kinetic_temperature_kelvin=self.current_kinetic_temperature_kelvin,
            volume_angstrom3=volume,
            instantaneous_pressure_bar=self.current_instantaneous_pressure_bar,
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
            cumulative_barostat_attempt_count=(
                self.cumulative_barostat_attempt_count
            ),
            cumulative_barostat_accept_count=(
                self.cumulative_barostat_accept_count
            ),
            cumulative_barostat_reject_count=(
                self.cumulative_barostat_reject_count
            ),
            random_word_index=self.random_word_index,
        )

    def _payload_without_digest(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "algorithm_id": self.algorithm_id,
            "device": self.device,
            "dtype": self.dtype,
            "torch_version": self.torch_version,
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
            "coordinates": _tensor_payload(
                self.coordinates,
                name="checkpoint coordinates",
            ),
            "velocities_angstrom_per_ps": _tensor_payload(
                self.velocities_angstrom_per_ps,
                name="checkpoint velocities",
            ),
            "cell_lengths_angstrom_hex": _cell_lengths_payload(
                self.cell_lengths_angstrom
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
            "current_kinetic_temperature_kelvin_hex": (
                self.current_kinetic_temperature_kelvin.hex()
            ),
            "current_instantaneous_pressure_bar_hex": (
                None
                if self.current_instantaneous_pressure_bar is None
                else self.current_instantaneous_pressure_bar.hex()
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
            "cumulative_barostat_attempt_count": (
                self.cumulative_barostat_attempt_count
            ),
            "cumulative_barostat_accept_count": (
                self.cumulative_barostat_accept_count
            ),
            "cumulative_barostat_reject_count": (
                self.cumulative_barostat_reject_count
            ),
            "random_word_index": self.random_word_index,
            "random_algorithm_id": REFERENCE_COUNTER_RNG_ALGORITHM_ID,
            "current_frame_sha256": self.current_frame_sha256,
            "trajectory_head_sha256": self.trajectory_head_sha256,
            "evaluated_frame_count": self.evaluated_frame_count,
            "barostat_head_sha256": self.barostat_head_sha256,
        }

    @property
    def checkpoint_sha256(self) -> str:
        return _canonical_sha256(self._payload_without_digest())

    def to_dict(self) -> dict[str, object]:
        return {
            **self._payload_without_digest(),
            "checkpoint_sha256": self.checkpoint_sha256,
        }

    def to_json_bytes(self) -> bytes:
        payload = _canonical_bytes(self.to_dict()) + b"\n"
        if len(payload) > MAX_REFERENCE_CANONICAL_ENSEMBLE_CHECKPOINT_BYTES:
            raise ReferenceCanonicalEnsembleError(
                "canonical-ensemble checkpoint exceeds byte capacity"
            )
        return payload

    @classmethod
    def from_json_bytes(
        cls,
        value: bytes,
    ) -> "ReferenceCanonicalEnsembleCheckpoint":
        if not isinstance(value, bytes):
            raise ReferenceCanonicalEnsembleError(
                "checkpoint transport must be bytes"
            )
        if len(value) > MAX_REFERENCE_CANONICAL_ENSEMBLE_CHECKPOINT_BYTES:
            raise ReferenceCanonicalEnsembleError(
                "canonical-ensemble checkpoint exceeds byte capacity"
            )
        if not value.endswith(b"\n"):
            raise ReferenceCanonicalEnsembleError(
                "checkpoint transport is not canonical"
            )
        try:
            payload = json.loads(value.decode("ascii"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ReferenceCanonicalEnsembleError(
                "checkpoint transport is invalid JSON"
            ) from exc
        if not isinstance(payload, Mapping):
            raise ReferenceCanonicalEnsembleError(
                "checkpoint document must be an object"
            )
        expected = {
            "schema_id",
            "algorithm_id",
            "device",
            "dtype",
            "torch_version",
            "source_system_sha256",
            "topology_sha256",
            "parameter_fingerprint_sha256",
            "config",
            "config_fingerprint_sha256",
            "constraint_config",
            "constraint_config_fingerprint_sha256",
            "step",
            "time_ps_hex",
            "coordinates",
            "velocities_angstrom_per_ps",
            "cell_lengths_angstrom_hex",
            "current_potential_energy_kcal_per_mol_hex",
            "current_kinetic_energy_kcal_per_mol_hex",
            "current_total_energy_kcal_per_mol_hex",
            "current_kinetic_temperature_kelvin_hex",
            "current_instantaneous_pressure_bar_hex",
            "max_abs_position_constraint_residual_angstrom_hex",
            "max_abs_velocity_constraint_residual_angstrom_per_ps_hex",
            "cumulative_shake_iteration_count",
            "cumulative_rattle_iteration_count",
            "cumulative_barostat_attempt_count",
            "cumulative_barostat_accept_count",
            "cumulative_barostat_reject_count",
            "random_word_index",
            "random_algorithm_id",
            "current_frame_sha256",
            "trajectory_head_sha256",
            "evaluated_frame_count",
            "barostat_head_sha256",
            "checkpoint_sha256",
        }
        if set(payload) != expected:
            raise ReferenceCanonicalEnsembleError(
                "checkpoint document fields are invalid"
            )
        if payload["random_algorithm_id"] != REFERENCE_COUNTER_RNG_ALGORITHM_ID:
            raise ReferenceCanonicalEnsembleError(
                "checkpoint random algorithm is unsupported"
            )
        config = ReferenceCanonicalEnsembleConfig.from_dict(payload["config"])
        if config.fingerprint_sha256 != _digest(
            payload["config_fingerprint_sha256"],
            name="config_fingerprint_sha256",
        ):
            raise ReferenceCanonicalEnsembleError(
                "checkpoint config fingerprint mismatch"
            )
        try:
            constraint_config = ReferenceSHAKERATTLEConfig.from_dict(
                payload["constraint_config"]
            )
        except ReferenceSHAKERATTLEError as exc:
            raise ReferenceCanonicalEnsembleError(
                "checkpoint constraint config is invalid"
            ) from exc
        if constraint_config.fingerprint_sha256 != _digest(
            payload["constraint_config_fingerprint_sha256"],
            name="constraint_config_fingerprint_sha256",
        ):
            raise ReferenceCanonicalEnsembleError(
                "checkpoint constraint config fingerprint mismatch"
            )
        pressure_hex = payload["current_instantaneous_pressure_bar_hex"]
        result = cls(
            source_system_sha256=str(payload["source_system_sha256"]),
            topology_sha256=str(payload["topology_sha256"]),
            parameter_fingerprint_sha256=str(
                payload["parameter_fingerprint_sha256"]
            ),
            config=config,
            constraint_config=constraint_config,
            step=_exact_int(payload["step"], name="step", minimum=0),
            time_ps=_require_float_hex(payload["time_ps_hex"], name="time_ps_hex"),
            coordinates=_tensor_from_payload(
                payload["coordinates"],
                name="checkpoint coordinates",
            ),
            velocities_angstrom_per_ps=_tensor_from_payload(
                payload["velocities_angstrom_per_ps"],
                name="checkpoint velocities",
            ),
            cell_lengths_angstrom=_cell_lengths_from_payload(
                payload["cell_lengths_angstrom_hex"]
            ),
            current_potential_energy_kcal_per_mol=_require_float_hex(
                payload["current_potential_energy_kcal_per_mol_hex"],
                name="current_potential_energy_kcal_per_mol_hex",
            ),
            current_kinetic_energy_kcal_per_mol=_require_float_hex(
                payload["current_kinetic_energy_kcal_per_mol_hex"],
                name="current_kinetic_energy_kcal_per_mol_hex",
            ),
            current_total_energy_kcal_per_mol=_require_float_hex(
                payload["current_total_energy_kcal_per_mol_hex"],
                name="current_total_energy_kcal_per_mol_hex",
            ),
            current_kinetic_temperature_kelvin=_require_float_hex(
                payload["current_kinetic_temperature_kelvin_hex"],
                name="current_kinetic_temperature_kelvin_hex",
            ),
            current_instantaneous_pressure_bar=(
                None
                if pressure_hex is None
                else _require_float_hex(
                    pressure_hex,
                    name="current_instantaneous_pressure_bar_hex",
                )
            ),
            max_abs_position_constraint_residual_angstrom=_require_float_hex(
                payload["max_abs_position_constraint_residual_angstrom_hex"],
                name="max_abs_position_constraint_residual_angstrom_hex",
            ),
            max_abs_velocity_constraint_residual_angstrom_per_ps=(
                _require_float_hex(
                    payload[
                        "max_abs_velocity_constraint_residual_angstrom_per_ps_hex"
                    ],
                    name=(
                        "max_abs_velocity_constraint_residual_angstrom_per_ps_hex"
                    ),
                )
            ),
            cumulative_shake_iteration_count=_exact_int(
                payload["cumulative_shake_iteration_count"],
                name="cumulative_shake_iteration_count",
            ),
            cumulative_rattle_iteration_count=_exact_int(
                payload["cumulative_rattle_iteration_count"],
                name="cumulative_rattle_iteration_count",
            ),
            cumulative_barostat_attempt_count=_exact_int(
                payload["cumulative_barostat_attempt_count"],
                name="cumulative_barostat_attempt_count",
            ),
            cumulative_barostat_accept_count=_exact_int(
                payload["cumulative_barostat_accept_count"],
                name="cumulative_barostat_accept_count",
            ),
            cumulative_barostat_reject_count=_exact_int(
                payload["cumulative_barostat_reject_count"],
                name="cumulative_barostat_reject_count",
            ),
            random_word_index=_exact_int(
                payload["random_word_index"],
                name="random_word_index",
            ),
            current_frame_sha256=str(payload["current_frame_sha256"]),
            trajectory_head_sha256=str(payload["trajectory_head_sha256"]),
            evaluated_frame_count=_exact_int(
                payload["evaluated_frame_count"],
                name="evaluated_frame_count",
                minimum=1,
            ),
            barostat_head_sha256=str(payload["barostat_head_sha256"]),
            schema_id=str(payload["schema_id"]),
            algorithm_id=str(payload["algorithm_id"]),
            device=str(payload["device"]),
            dtype=str(payload["dtype"]),
            torch_version=str(payload["torch_version"]),
        )
        if result.checkpoint_sha256 != _digest(
            payload["checkpoint_sha256"],
            name="checkpoint_sha256",
        ):
            raise ReferenceCanonicalEnsembleError(
                "checkpoint self-digest mismatch"
            )
        if result.to_json_bytes() != value:
            raise ReferenceCanonicalEnsembleError(
                "checkpoint transport is not canonical"
            )
        return result


@dataclass(frozen=True)
class ReferenceCanonicalEnsembleResult:
    start_step: int
    end_step: int
    frames: tuple[ReferenceCanonicalEnsembleFrame, ...]
    barostat_attempts: tuple[ReferenceBarostatAttempt, ...]
    checkpoint: ReferenceCanonicalEnsembleCheckpoint
    system: AllAtomSystem
    provenance: ReferenceCanonicalEnsembleProvenance
    scientific_blockers: tuple[str, ...] = (
        REFERENCE_CANONICAL_ENSEMBLE_SCIENTIFIC_BLOCKERS
    )
    schema_id: str = REFERENCE_CANONICAL_ENSEMBLE_RESULT_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != REFERENCE_CANONICAL_ENSEMBLE_RESULT_SCHEMA_ID:
            raise ReferenceCanonicalEnsembleError(
                "unsupported canonical-ensemble result schema"
            )
        start = _exact_int(self.start_step, name="start_step", minimum=0)
        end = _exact_int(self.end_step, name="end_step", minimum=start + 1)
        object.__setattr__(self, "start_step", start)
        object.__setattr__(self, "end_step", end)
        frames = tuple(self.frames)
        attempts = tuple(self.barostat_attempts)
        if not frames or frames[0].step != start or frames[-1].step != end:
            raise ReferenceCanonicalEnsembleError(
                "result frame endpoints are inconsistent"
            )
        if any(
            not isinstance(frame, ReferenceCanonicalEnsembleFrame)
            for frame in frames
        ):
            raise ReferenceCanonicalEnsembleError("result frame type is invalid")
        if any(
            not isinstance(attempt, ReferenceBarostatAttempt)
            for attempt in attempts
        ):
            raise ReferenceCanonicalEnsembleError(
                "result barostat attempt type is invalid"
            )
        if any(
            attempts[index].step >= attempts[index + 1].step
            for index in range(len(attempts) - 1)
        ):
            raise ReferenceCanonicalEnsembleError(
                "result barostat attempt steps are not strictly increasing"
            )
        object.__setattr__(self, "frames", frames)
        object.__setattr__(self, "barostat_attempts", attempts)
        if not isinstance(self.checkpoint, ReferenceCanonicalEnsembleCheckpoint):
            raise ReferenceCanonicalEnsembleError(
                "result checkpoint type is invalid"
            )
        if self.checkpoint.step != end:
            raise ReferenceCanonicalEnsembleError(
                "result endpoint does not match checkpoint"
            )
        if frames[-1].fingerprint_sha256 != self.checkpoint.current_frame_sha256:
            raise ReferenceCanonicalEnsembleError(
                "result final frame does not match checkpoint"
            )
        if not isinstance(self.provenance, ReferenceCanonicalEnsembleProvenance):
            raise ReferenceCanonicalEnsembleError(
                "result provenance type is invalid"
            )
        if tuple(self.scientific_blockers) != (
            REFERENCE_CANONICAL_ENSEMBLE_SCIENTIFIC_BLOCKERS
        ):
            raise ReferenceCanonicalEnsembleError(
                "canonical-ensemble scientific blockers are fixed"
            )
        if self.system.coordinates.shape != self.checkpoint.coordinates.shape:
            raise ReferenceCanonicalEnsembleError(
                "result system coordinate shape is inconsistent"
            )
        if not torch.equal(self.system.coordinates, self.checkpoint.coordinates):
            raise ReferenceCanonicalEnsembleError(
                "result system coordinates do not match checkpoint"
            )

    @property
    def ensemble(self) -> str:
        return self.checkpoint.config.ensemble

    @property
    def steps_completed(self) -> int:
        return self.end_step - self.start_step

    @property
    def claim_safe(self) -> bool:
        return False

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "status": "completed",
            "ensemble": self.ensemble,
            "start_step": self.start_step,
            "end_step": self.end_step,
            "steps_completed": self.steps_completed,
            "retained_frame_count": len(self.frames),
            "evaluated_frame_count": self.checkpoint.evaluated_frame_count,
            "segment_barostat_attempt_count": len(self.barostat_attempts),
            "cumulative_barostat_attempt_count": (
                self.checkpoint.cumulative_barostat_attempt_count
            ),
            "cumulative_barostat_accept_count": (
                self.checkpoint.cumulative_barostat_accept_count
            ),
            "cumulative_barostat_reject_count": (
                self.checkpoint.cumulative_barostat_reject_count
            ),
            "random_word_index": self.checkpoint.random_word_index,
            "trajectory_head_sha256": self.checkpoint.trajectory_head_sha256,
            "barostat_head_sha256": self.checkpoint.barostat_head_sha256,
            "checkpoint_sha256": self.checkpoint.checkpoint_sha256,
            "frames": [frame.to_dict() for frame in self.frames],
            "barostat_attempts": [row.to_dict() for row in self.barostat_attempts],
            "provenance": self.provenance.to_dict(),
            "scientific_blockers": list(self.scientific_blockers),
            "claim_safe": False,
        }


class _CounterRandomStream:
    def __init__(self, *, seed: int, word_index: int) -> None:
        self.seed = _exact_int(
            seed,
            name="random seed",
            minimum=0,
            maximum=(1 << 64) - 1,
        )
        self.word_index = _exact_int(
            word_index,
            name="random word index",
            minimum=0,
            maximum=MAX_REFERENCE_COUNTER_RNG_WORD_INDEX,
        )
        self._cached_block_index = -1
        self._cached_words: tuple[int, ...] = ()

    def _word(self) -> int:
        if self.word_index >= MAX_REFERENCE_COUNTER_RNG_WORD_INDEX:
            raise ReferenceCanonicalEnsembleError(
                "counter random stream capacity exhausted"
            )
        block_index, lane = divmod(self.word_index, 4)
        if block_index != self._cached_block_index:
            digest = hashlib.sha256(
                REFERENCE_COUNTER_RNG_ALGORITHM_ID.encode("ascii")
                + b"\x00"
                + self.seed.to_bytes(8, "little", signed=False)
                + block_index.to_bytes(16, "little", signed=False)
            ).digest()
            self._cached_words = struct.unpack("<QQQQ", digest)
            self._cached_block_index = block_index
        result = self._cached_words[lane]
        self.word_index += 1
        return result

    def uniform_open(self) -> float:
        # Midpoints of the 2**53 equiprobable bins avoid log(0) in Box-Muller.
        return ((self._word() >> 11) + 0.5) / float(1 << 53)

    def standard_normals(self, count: int) -> torch.Tensor:
        size = _exact_int(count, name="normal count", minimum=1)
        rows: list[float] = []
        while len(rows) < size:
            first = self.uniform_open()
            second = self.uniform_open()
            radius = math.sqrt(-2.0 * math.log(first))
            angle = 2.0 * math.pi * second
            rows.append(radius * math.cos(angle))
            if len(rows) < size:
                rows.append(radius * math.sin(angle))
        return torch.tensor(rows, dtype=torch.float64)


def _require_source_system(system: AllAtomSystem) -> torch.Tensor:
    require_valid_all_atom_system(system)
    if system.model_count != 1:
        raise ReferenceCanonicalEnsembleError(
            "canonical-ensemble MD requires exactly one coordinate model"
        )
    if system.coordinates.dtype != torch.float64 or system.coordinates.device.type != "cpu":
        raise ReferenceCanonicalEnsembleError(
            "canonical-ensemble MD requires CPU float64 coordinates"
        )
    if system.atom_count < 2:
        raise ReferenceCanonicalEnsembleError(
            "center-of-mass constrained canonical MD requires at least two atoms"
        )
    masses: list[float] = []
    for atom in system.atoms:
        if atom.mass_da is None:
            raise ReferenceCanonicalEnsembleError(
                f"atom {atom.index} is missing mass_da"
            )
        masses.append(
            _finite_float(
                atom.mass_da,
                name=f"atom {atom.index} mass",
                positive=True,
            )
        )
    if system.cell is not None:
        if (
            system.cell.vectors.dtype != torch.float64
            or system.cell.vectors.device.type != "cpu"
        ):
            raise ReferenceCanonicalEnsembleError(
                "canonical-ensemble periodic cells require CPU float64 vectors"
            )
        if system.cell.periodic != (True, True, True):
            raise ReferenceCanonicalEnsembleError(
                "canonical-ensemble periodic cells must be fully periodic"
            )
        try:
            lengths = system.cell.orthorhombic_lengths()
        except ValueError as exc:
            raise ReferenceCanonicalEnsembleError(
                "canonical-ensemble MD supports orthorhombic cells only"
            ) from exc
        if not bool(torch.isfinite(lengths).all().item()) or bool(
            (lengths <= 0.0).any().item()
        ):
            raise ReferenceCanonicalEnsembleError(
                "periodic cell lengths must be finite and positive"
            )
    return torch.tensor(masses, dtype=torch.float64)


def _cell_lengths(system: AllAtomSystem) -> torch.Tensor | None:
    if system.cell is None:
        return None
    return system.cell.orthorhombic_lengths().to(dtype=torch.float64, device="cpu")


def _cell_tuple(lengths: torch.Tensor | None) -> tuple[float, float, float] | None:
    if lengths is None:
        return None
    return tuple(float(item) for item in lengths.tolist())


def _system_for_state(
    source_system: AllAtomSystem,
    coordinates: torch.Tensor,
    lengths: torch.Tensor | None,
) -> AllAtomSystem:
    cell = (
        None
        if lengths is None
        else UnitCell.orthorhombic(
            lengths,
            dtype=torch.float64,
            device="cpu",
            periodic=(True, True, True),
        )
    )
    return replace(source_system, coordinates=coordinates, cell=cell)


def _wrap_coordinates(
    coordinates: torch.Tensor,
    lengths: torch.Tensor | None,
) -> torch.Tensor:
    if lengths is None:
        return coordinates
    shaped = lengths.view(1, 1, 3)
    return coordinates - torch.floor(coordinates / shaped) * shaped


def _evaluate(
    source_system: AllAtomSystem,
    coordinates: torch.Tensor,
    lengths: torch.Tensor | None,
    parameters: ReferenceForceFieldParameters,
    config: ReferenceCanonicalEnsembleConfig,
) -> tuple[float, torch.Tensor]:
    current = _system_for_state(source_system, coordinates, lengths)
    neighbors = build_compact_radius_graph(
        coordinates,
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
    except (ReferenceEwaldError, ReferencePhysicsApplicabilityError) as exc:
        raise ReferenceCanonicalEnsembleError(
            f"canonical-ensemble force evaluation failed closed: {exc}"
        ) from exc
    potential = float(evaluation.term.energy.detach().cpu().reshape(-1)[0].item())
    forces = evaluation.term.forces.detach().to(dtype=torch.float64, device="cpu")
    if not math.isfinite(potential) or not bool(torch.isfinite(forces).all().item()):
        raise ReferenceCanonicalEnsembleError(
            "canonical-ensemble force evaluation returned non-finite values"
        )
    return potential, forces


def _molecular_components(system: AllAtomSystem) -> tuple[tuple[int, ...], ...]:
    parent = list(range(system.atom_count))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(first: int, second: int) -> None:
        root_first = find(first)
        root_second = find(second)
        if root_first == root_second:
            return
        lower, upper = sorted((root_first, root_second))
        parent[upper] = lower

    for bond in system.bonds:
        union(bond.atom_i, bond.atom_j)
    groups: dict[int, list[int]] = {}
    for atom_index in range(system.atom_count):
        groups.setdefault(find(atom_index), []).append(atom_index)
    return tuple(tuple(groups[root]) for root in sorted(groups))


def _unwrapped_component(
    system: AllAtomSystem,
    coordinates: torch.Tensor,
    lengths: torch.Tensor,
    component: tuple[int, ...],
) -> torch.Tensor:
    component_set = set(component)
    adjacency: dict[int, list[int]] = {index: [] for index in component}
    for bond in system.bonds:
        if bond.atom_i in component_set and bond.atom_j in component_set:
            adjacency[bond.atom_i].append(bond.atom_j)
            adjacency[bond.atom_j].append(bond.atom_i)
    root = component[0]
    unwrapped: dict[int, torch.Tensor] = {root: coordinates[0, root].clone()}
    queue = [root]
    while queue:
        current = queue.pop(0)
        for neighbor in sorted(adjacency[current]):
            if neighbor in unwrapped:
                continue
            displacement = coordinates[0, neighbor] - coordinates[0, current]
            displacement = displacement - torch.round(displacement / lengths) * lengths
            unwrapped[neighbor] = unwrapped[current] + displacement
            queue.append(neighbor)
    for atom_index in component:
        if atom_index not in unwrapped:
            unwrapped[atom_index] = coordinates[0, atom_index].clone()
    return torch.stack([unwrapped[index] for index in component], dim=0)


def _scale_molecular_centres(
    system: AllAtomSystem,
    coordinates: torch.Tensor,
    old_lengths: torch.Tensor,
    new_lengths: torch.Tensor,
    masses: torch.Tensor,
    components: tuple[tuple[int, ...], ...],
) -> torch.Tensor:
    scale = new_lengths / old_lengths
    result = torch.empty_like(coordinates)
    for component in components:
        unwrapped = _unwrapped_component(
            system,
            coordinates,
            old_lengths,
            component,
        )
        indices = torch.tensor(component, dtype=torch.long)
        component_masses = masses.index_select(0, indices)
        centre = (
            unwrapped * component_masses.view(-1, 1)
        ).sum(dim=0) / component_masses.sum()
        wrapped_centre = centre - torch.floor(centre / old_lengths) * old_lengths
        new_centre = wrapped_centre * scale
        translated = unwrapped + (new_centre - centre)
        result[0, indices] = translated
    return _wrap_coordinates(result, new_lengths)


def _remove_center_of_mass_velocity(
    velocities: torch.Tensor,
    masses: torch.Tensor,
) -> torch.Tensor:
    total_mass = masses.sum()
    centre_velocity = (
        velocities * masses.view(1, -1, 1)
    ).sum(dim=1, keepdim=True) / total_mass
    return velocities - centre_velocity


def _kinetic_energy(velocities: torch.Tensor, masses: torch.Tensor) -> float:
    value = (
        0.5
        * (masses.view(1, -1, 1) * velocities.square()).sum()
        / FORCE_KCAL_PER_MOL_ANGSTROM_TO_ACCELERATION_ANGSTROM_PER_PS2_PER_DA
    )
    return _finite_float(
        float(value.item()),
        name="kinetic energy",
        nonnegative=True,
    )


def _degrees_of_freedom(
    atom_count: int,
    constraint_config: ReferenceSHAKERATTLEConfig,
) -> int:
    degrees = 3 * atom_count - 3 - len(constraint_config.constraints)
    if degrees <= 0:
        raise ReferenceCanonicalEnsembleError(
            "canonical-ensemble kinetic degrees of freedom are not positive"
        )
    return degrees


def _temperature(kinetic_energy: float, degrees_of_freedom: int) -> float:
    return 2.0 * kinetic_energy / (
        degrees_of_freedom * MOLAR_GAS_CONSTANT_KCAL_PER_MOL_K
    )


def _constraint_residuals(
    system: AllAtomSystem,
    coordinates: torch.Tensor,
    velocities: torch.Tensor,
    constraint_config: ReferenceSHAKERATTLEConfig,
) -> tuple[float, float]:
    try:
        positions = observe_reference_position_constraints(
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
        raise ReferenceCanonicalEnsembleError(
            f"canonical-ensemble constraint observation failed closed: {exc}"
        ) from exc
    position_residual = max(
        (abs(row.residual_angstrom) for row in positions),
        default=0.0,
    )
    velocity_residual = max(
        (
            abs(row.radial_relative_velocity_angstrom_per_ps)
            for row in velocity_rows
        ),
        default=0.0,
    )
    if any(
        abs(row.residual_angstrom)
        > constraint_config.convergence_tolerance_scale * row.tolerance_angstrom
        for row in positions
    ):
        raise ReferenceCanonicalEnsembleError(
            "canonical-ensemble state violates SHAKE position tolerance"
        )
    if velocity_residual > (
        constraint_config.convergence_tolerance_scale
        * constraint_config.velocity_tolerance_angstrom_per_ps
    ):
        raise ReferenceCanonicalEnsembleError(
            "canonical-ensemble state violates RATTLE velocity tolerance"
        )
    return position_residual, velocity_residual


def _validate_current_cell_domain(
    lengths: torch.Tensor,
    parameters: ReferenceForceFieldParameters,
) -> None:
    if parameters.cutoff_angstrom >= 0.5 * float(lengths.min().item()):
        raise ReferenceCanonicalEnsembleError(
            "NPT cutoff must remain below half the shortest box length"
        )


def _pressure_observation(
    source_system: AllAtomSystem,
    coordinates: torch.Tensor,
    lengths: torch.Tensor,
    masses: torch.Tensor,
    components: tuple[tuple[int, ...], ...],
    parameters: ReferenceForceFieldParameters,
    config: ReferenceCanonicalEnsembleConfig,
) -> float:
    barostat = config.barostat
    if barostat is None:
        raise ReferenceCanonicalEnsembleError(
            "pressure observation requires an NPT config"
        )
    epsilon = barostat.pressure_log_length_step
    plus_lengths = lengths * math.exp(epsilon)
    minus_lengths = lengths * math.exp(-epsilon)
    _validate_current_cell_domain(plus_lengths, parameters)
    _validate_current_cell_domain(minus_lengths, parameters)
    plus_coordinates = _scale_molecular_centres(
        source_system,
        coordinates,
        lengths,
        plus_lengths,
        masses,
        components,
    )
    minus_coordinates = _scale_molecular_centres(
        source_system,
        coordinates,
        lengths,
        minus_lengths,
        masses,
        components,
    )
    plus_energy, _ = _evaluate(
        source_system,
        plus_coordinates,
        plus_lengths,
        parameters,
        config,
    )
    minus_energy, _ = _evaluate(
        source_system,
        minus_coordinates,
        minus_lengths,
        parameters,
        config,
    )
    derivative_log_length = (plus_energy - minus_energy) / (2.0 * epsilon)
    derivative_log_volume = derivative_log_length / 3.0
    volume = float(torch.prod(lengths).item())
    ideal_term = (
        len(components)
        * MOLAR_GAS_CONSTANT_KCAL_PER_MOL_K
        * config.thermostat.temperature_kelvin
    )
    pressure_energy_density = (ideal_term - derivative_log_volume) / volume
    return _finite_float(
        pressure_energy_density / BAR_ANGSTROM3_TO_KCAL_PER_MOL,
        name="instantaneous molecular pressure",
    )


def _frame(
    *,
    step: int,
    config: ReferenceCanonicalEnsembleConfig,
    coordinates: torch.Tensor,
    velocities: torch.Tensor,
    lengths: torch.Tensor | None,
    potential: float,
    masses: torch.Tensor,
    degrees_of_freedom: int,
    instantaneous_pressure: float | None,
    max_position_residual: float,
    max_velocity_residual: float,
    cumulative_shake_iterations: int,
    cumulative_rattle_iterations: int,
    cumulative_barostat_attempts: int,
    cumulative_barostat_accepts: int,
    cumulative_barostat_rejects: int,
    random_word_index: int,
) -> ReferenceCanonicalEnsembleFrame:
    kinetic = _kinetic_energy(velocities, masses)
    length_tuple = _cell_tuple(lengths)
    return ReferenceCanonicalEnsembleFrame(
        step=step,
        time_ps=step * config.timestep_ps,
        coordinates=coordinates,
        velocities_angstrom_per_ps=velocities,
        cell_lengths_angstrom=length_tuple,
        potential_energy_kcal_per_mol=potential,
        kinetic_energy_kcal_per_mol=kinetic,
        total_energy_kcal_per_mol=potential + kinetic,
        kinetic_temperature_kelvin=_temperature(kinetic, degrees_of_freedom),
        volume_angstrom3=(
            None if length_tuple is None else math.prod(length_tuple)
        ),
        instantaneous_pressure_bar=instantaneous_pressure,
        max_abs_position_constraint_residual_angstrom=max_position_residual,
        max_abs_velocity_constraint_residual_angstrom_per_ps=max_velocity_residual,
        cumulative_shake_iteration_count=cumulative_shake_iterations,
        cumulative_rattle_iteration_count=cumulative_rattle_iterations,
        cumulative_barostat_attempt_count=cumulative_barostat_attempts,
        cumulative_barostat_accept_count=cumulative_barostat_accepts,
        cumulative_barostat_reject_count=cumulative_barostat_rejects,
        random_word_index=random_word_index,
    )


def _provenance(
    system: AllAtomSystem,
    parameters: ReferenceForceFieldParameters,
    config: ReferenceCanonicalEnsembleConfig,
    constraint_config: ReferenceSHAKERATTLEConfig,
) -> ReferenceCanonicalEnsembleProvenance:
    return ReferenceCanonicalEnsembleProvenance(
        source_system_sha256=canonical_system_sha256(system),
        topology_sha256=canonical_topology_sha256(system),
        parameter_fingerprint_sha256=parameters.fingerprint_sha256,
        config_fingerprint_sha256=config.fingerprint_sha256,
        constraint_config_fingerprint_sha256=(
            constraint_config.fingerprint_sha256
        ),
    )


def _project_positions(
    source_system: AllAtomSystem,
    lengths: torch.Tensor | None,
    reference_coordinates: torch.Tensor,
    predicted_coordinates: torch.Tensor,
    velocities: torch.Tensor,
    masses: torch.Tensor,
    constraint_config: ReferenceSHAKERATTLEConfig,
    interval_ps: float,
    *,
    step: int,
) -> tuple[torch.Tensor, torch.Tensor, int, float]:
    if not constraint_config.enabled:
        return predicted_coordinates, velocities, 0, 0.0
    state_system = _system_for_state(
        source_system,
        reference_coordinates,
        lengths,
    )
    try:
        report = project_reference_shake_positions(
            state_system,
            reference_coordinates,
            predicted_coordinates,
            masses,
            constraint_config,
        )
    except ReferenceSHAKERATTLEError as exc:
        raise ReferenceCanonicalEnsembleError(
            f"SHAKE failed closed at step {step}: {exc}"
        ) from exc
    if not report.converged:
        raise ReferenceCanonicalEnsembleError(
            f"SHAKE failed closed at step {step}: {report.failure_code}; "
            f"iterations={report.iteration_count}; "
            f"max_abs_residual_angstrom={report.max_abs_residual_angstrom.hex()}"
        )
    displacement = minimum_image_displacement(
        report.coordinates - predicted_coordinates,
        state_system,
    )
    return (
        report.coordinates,
        velocities + displacement / interval_ps,
        report.iteration_count,
        report.max_abs_residual_angstrom,
    )


def _project_velocities(
    source_system: AllAtomSystem,
    lengths: torch.Tensor | None,
    coordinates: torch.Tensor,
    velocities: torch.Tensor,
    masses: torch.Tensor,
    constraint_config: ReferenceSHAKERATTLEConfig,
    *,
    step: int,
) -> tuple[torch.Tensor, int, float]:
    if not constraint_config.enabled:
        return velocities, 0, 0.0
    state_system = _system_for_state(source_system, coordinates, lengths)
    try:
        report = project_reference_rattle_velocities(
            state_system,
            coordinates,
            velocities,
            masses,
            constraint_config,
        )
    except ReferenceSHAKERATTLEError as exc:
        raise ReferenceCanonicalEnsembleError(
            f"RATTLE failed closed at step {step}: {exc}"
        ) from exc
    if not report.converged:
        raise ReferenceCanonicalEnsembleError(
            f"RATTLE failed closed at step {step}: {report.failure_code}; "
            f"iterations={report.iteration_count}; "
            "max_abs_residual_angstrom_per_ps="
            f"{report.max_abs_residual_angstrom_per_ps.hex()}"
        )
    return (
        report.velocities_angstrom_per_ps,
        report.iteration_count,
        report.max_abs_residual_angstrom_per_ps,
    )


def _thermostat_ou_step(
    velocities: torch.Tensor,
    masses: torch.Tensor,
    config: ReferenceCanonicalEnsembleConfig,
    random_stream: _CounterRandomStream,
) -> torch.Tensor:
    coefficient = math.exp(
        -config.thermostat.collision_rate_per_ps * config.timestep_ps
    )
    variance_factor = max(0.0, 1.0 - coefficient * coefficient)
    thermal_variance = (
        FORCE_KCAL_PER_MOL_ANGSTROM_TO_ACCELERATION_ANGSTROM_PER_PS2_PER_DA
        * MOLAR_GAS_CONSTANT_KCAL_PER_MOL_K
        * config.thermostat.temperature_kelvin
        / masses
    )
    noise = random_stream.standard_normals(int(velocities.numel())).reshape(
        velocities.shape
    )
    thermal = noise * torch.sqrt(variance_factor * thermal_variance).view(
        1,
        -1,
        1,
    )
    return _remove_center_of_mass_velocity(
        coefficient * velocities + thermal,
        masses,
    )


def _attempt_barostat(
    *,
    step: int,
    source_system: AllAtomSystem,
    coordinates: torch.Tensor,
    lengths: torch.Tensor,
    potential: float,
    forces: torch.Tensor,
    masses: torch.Tensor,
    components: tuple[tuple[int, ...], ...],
    parameters: ReferenceForceFieldParameters,
    config: ReferenceCanonicalEnsembleConfig,
    constraint_config: ReferenceSHAKERATTLEConfig,
    random_stream: _CounterRandomStream,
) -> tuple[
    ReferenceBarostatAttempt,
    torch.Tensor,
    torch.Tensor,
    float,
    torch.Tensor,
]:
    barostat = config.barostat
    if barostat is None:
        raise ReferenceCanonicalEnsembleError(
            "barostat attempt requires an NPT config"
        )
    proposal_uniform = random_stream.uniform_open()
    acceptance_uniform = random_stream.uniform_open()
    old_volume = float(torch.prod(lengths).item())
    delta_volume = (
        2.0 * proposal_uniform - 1.0
    ) * barostat.max_delta_volume_angstrom3
    new_volume = old_volume + delta_volume
    ratio = new_volume / old_volume
    domain_valid = (
        new_volume > 0.0
        and MIN_BAROSTAT_VOLUME_RATIO_PER_ATTEMPT
        <= ratio
        <= MAX_BAROSTAT_VOLUME_RATIO_PER_ATTEMPT
    )
    new_lengths = lengths
    new_coordinates = coordinates
    proposed_potential: float | None = None
    proposed_forces = forces
    if domain_valid:
        scale = ratio ** (1.0 / 3.0)
        new_lengths = lengths * scale
        try:
            _validate_current_cell_domain(new_lengths, parameters)
            new_coordinates = _scale_molecular_centres(
                source_system,
                coordinates,
                lengths,
                new_lengths,
                masses,
                components,
            )
            proposal_system = _system_for_state(
                source_system,
                new_coordinates,
                new_lengths,
            )
            validate_reference_shake_rattle_inputs(
                proposal_system,
                masses,
                constraint_config,
            )
            proposed_potential, proposed_forces = _evaluate(
                source_system,
                new_coordinates,
                new_lengths,
                parameters,
                config,
            )
        except (ReferenceCanonicalEnsembleError, ReferenceSHAKERATTLEError):
            domain_valid = False
    if not domain_valid or proposed_potential is None:
        attempt = ReferenceBarostatAttempt(
            step=step,
            old_volume_angstrom3=old_volume,
            proposed_volume_angstrom3=new_volume,
            proposal_uniform=proposal_uniform,
            acceptance_uniform=acceptance_uniform,
            old_potential_energy_kcal_per_mol=potential,
            proposed_potential_energy_kcal_per_mol=None,
            pressure_work_kcal_per_mol=None,
            jacobian_log_term=None,
            log_acceptance_probability=None,
            molecule_count=len(components),
            accepted=False,
            disposition="domain_rejected",
        )
        return attempt, coordinates, lengths, potential, forces
    pressure_work = (
        barostat.pressure_bar
        * (new_volume - old_volume)
        * BAR_ANGSTROM3_TO_KCAL_PER_MOL
    )
    jacobian = len(components) * math.log(ratio)
    beta = 1.0 / (
        MOLAR_GAS_CONSTANT_KCAL_PER_MOL_K
        * config.thermostat.temperature_kelvin
    )
    log_acceptance = (
        -beta * (proposed_potential - potential + pressure_work) + jacobian
    )
    accepted = log_acceptance >= 0.0 or math.log(acceptance_uniform) < log_acceptance
    attempt = ReferenceBarostatAttempt(
        step=step,
        old_volume_angstrom3=old_volume,
        proposed_volume_angstrom3=new_volume,
        proposal_uniform=proposal_uniform,
        acceptance_uniform=acceptance_uniform,
        old_potential_energy_kcal_per_mol=potential,
        proposed_potential_energy_kcal_per_mol=proposed_potential,
        pressure_work_kcal_per_mol=pressure_work,
        jacobian_log_term=jacobian,
        log_acceptance_probability=log_acceptance,
        molecule_count=len(components),
        accepted=accepted,
        disposition="accepted" if accepted else "metropolis_rejected",
    )
    if accepted:
        return (
            attempt,
            new_coordinates,
            new_lengths,
            proposed_potential,
            proposed_forces,
        )
    return attempt, coordinates, lengths, potential, forces


def _checkpoint(
    *,
    provenance: ReferenceCanonicalEnsembleProvenance,
    config: ReferenceCanonicalEnsembleConfig,
    constraint_config: ReferenceSHAKERATTLEConfig,
    frame: ReferenceCanonicalEnsembleFrame,
    trajectory_head: str,
    evaluated_frame_count: int,
    barostat_head: str,
) -> ReferenceCanonicalEnsembleCheckpoint:
    return ReferenceCanonicalEnsembleCheckpoint(
        source_system_sha256=provenance.source_system_sha256,
        topology_sha256=provenance.topology_sha256,
        parameter_fingerprint_sha256=provenance.parameter_fingerprint_sha256,
        config=config,
        constraint_config=constraint_config,
        step=frame.step,
        time_ps=frame.time_ps,
        coordinates=frame.coordinates,
        velocities_angstrom_per_ps=frame.velocities_angstrom_per_ps,
        cell_lengths_angstrom=frame.cell_lengths_angstrom,
        current_potential_energy_kcal_per_mol=(
            frame.potential_energy_kcal_per_mol
        ),
        current_kinetic_energy_kcal_per_mol=frame.kinetic_energy_kcal_per_mol,
        current_total_energy_kcal_per_mol=frame.total_energy_kcal_per_mol,
        current_kinetic_temperature_kelvin=frame.kinetic_temperature_kelvin,
        current_instantaneous_pressure_bar=frame.instantaneous_pressure_bar,
        max_abs_position_constraint_residual_angstrom=(
            frame.max_abs_position_constraint_residual_angstrom
        ),
        max_abs_velocity_constraint_residual_angstrom_per_ps=(
            frame.max_abs_velocity_constraint_residual_angstrom_per_ps
        ),
        cumulative_shake_iteration_count=(
            frame.cumulative_shake_iteration_count
        ),
        cumulative_rattle_iteration_count=(
            frame.cumulative_rattle_iteration_count
        ),
        cumulative_barostat_attempt_count=(
            frame.cumulative_barostat_attempt_count
        ),
        cumulative_barostat_accept_count=(
            frame.cumulative_barostat_accept_count
        ),
        cumulative_barostat_reject_count=(
            frame.cumulative_barostat_reject_count
        ),
        random_word_index=frame.random_word_index,
        current_frame_sha256=frame.fingerprint_sha256,
        trajectory_head_sha256=trajectory_head,
        evaluated_frame_count=evaluated_frame_count,
        barostat_head_sha256=barostat_head,
    )


def _run_segment(
    source_system: AllAtomSystem,
    parameters: ReferenceForceFieldParameters,
    config: ReferenceCanonicalEnsembleConfig,
    constraint_config: ReferenceSHAKERATTLEConfig,
    *,
    coordinates: torch.Tensor,
    velocities: torch.Tensor,
    lengths: torch.Tensor | None,
    start_step: int,
    steps: int,
    trajectory_head: str,
    evaluated_frame_count: int,
    barostat_head: str,
    random_word_index: int,
    max_position_residual: float,
    max_velocity_residual: float,
    cumulative_shake_iterations: int,
    cumulative_rattle_iterations: int,
    cumulative_barostat_attempts: int,
    cumulative_barostat_accepts: int,
    cumulative_barostat_rejects: int,
    expected_start_frame_sha256: str = "",
) -> ReferenceCanonicalEnsembleResult:
    masses = _require_source_system(source_system)
    current_system = _system_for_state(source_system, coordinates, lengths)
    try:
        validate_reference_shake_rattle_inputs(
            current_system,
            masses,
            constraint_config,
        )
    except ReferenceSHAKERATTLEError as exc:
        raise ReferenceCanonicalEnsembleError(
            f"SHAKE/RATTLE applicability failed closed: {exc}"
        ) from exc
    if lengths is not None:
        _validate_current_cell_domain(lengths, parameters)
    if config.barostat is not None:
        if lengths is None:
            raise ReferenceCanonicalEnsembleError(
                "NPT integration requires a fully periodic cell"
            )
    expected_shape = (1, source_system.atom_count, 3)
    if tuple(coordinates.shape) != expected_shape or tuple(velocities.shape) != expected_shape:
        raise ReferenceCanonicalEnsembleError(
            "canonical-ensemble state shape does not match source atom count"
        )
    end_step = start_step + steps
    retained_count = 1 + end_step // config.trajectory_stride - (
        start_step // config.trajectory_stride
    )
    if end_step % config.trajectory_stride != 0:
        retained_count += 1
    if retained_count > MAX_REFERENCE_CANONICAL_ENSEMBLE_RETAINED_FRAMES:
        raise ReferenceCanonicalEnsembleError(
            "requested segment exceeds retained trajectory-frame capacity"
        )
    segment_attempt_count = (
        0
        if config.barostat is None
        else end_step // config.barostat.interval_steps
        - start_step // config.barostat.interval_steps
    )
    if segment_attempt_count > MAX_REFERENCE_CANONICAL_ENSEMBLE_BAROSTAT_ATTEMPTS:
        raise ReferenceCanonicalEnsembleError(
            "requested segment exceeds barostat-attempt capacity"
        )
    degrees = _degrees_of_freedom(source_system.atom_count, constraint_config)
    components = _molecular_components(source_system)
    provenance = _provenance(
        source_system,
        parameters,
        config,
        constraint_config,
    )
    random_stream = _CounterRandomStream(
        seed=config.thermostat.random_seed,
        word_index=random_word_index,
    )
    if start_step == 0:
        if constraint_config.enabled:
            coordinates, velocities, shake_iterations, position_residual = (
                _project_positions(
                    source_system,
                    lengths,
                    coordinates,
                    coordinates,
                    velocities,
                    masses,
                    constraint_config,
                    config.timestep_ps,
                    step=0,
                )
            )
            cumulative_shake_iterations += shake_iterations
            max_position_residual = max(
                max_position_residual,
                position_residual,
            )
        velocities = _remove_center_of_mass_velocity(velocities, masses)
        velocities, rattle_iterations, velocity_residual = _project_velocities(
            source_system,
            lengths,
            coordinates,
            velocities,
            masses,
            constraint_config,
            step=0,
        )
        cumulative_rattle_iterations += rattle_iterations
        max_velocity_residual = max(max_velocity_residual, velocity_residual)
    else:
        observed_position, observed_velocity = _constraint_residuals(
            current_system,
            coordinates,
            velocities,
            constraint_config,
        )
        if observed_position > max_position_residual:
            raise ReferenceCanonicalEnsembleError(
                "restart position residual exceeds checkpoint history"
            )
        if observed_velocity > max_velocity_residual:
            raise ReferenceCanonicalEnsembleError(
                "restart velocity residual exceeds checkpoint history"
            )
    potential, forces = _evaluate(
        source_system,
        coordinates,
        lengths,
        parameters,
        config,
    )
    pressure: float | None = None
    if (
        config.barostat is not None
        and start_step % config.barostat.pressure_observation_stride == 0
    ):
        assert lengths is not None
        pressure = _pressure_observation(
            source_system,
            coordinates,
            lengths,
            masses,
            components,
            parameters,
            config,
        )
    current = _frame(
        step=start_step,
        config=config,
        coordinates=coordinates,
        velocities=velocities,
        lengths=lengths,
        potential=potential,
        masses=masses,
        degrees_of_freedom=degrees,
        instantaneous_pressure=pressure,
        max_position_residual=max_position_residual,
        max_velocity_residual=max_velocity_residual,
        cumulative_shake_iterations=cumulative_shake_iterations,
        cumulative_rattle_iterations=cumulative_rattle_iterations,
        cumulative_barostat_attempts=cumulative_barostat_attempts,
        cumulative_barostat_accepts=cumulative_barostat_accepts,
        cumulative_barostat_rejects=cumulative_barostat_rejects,
        random_word_index=random_stream.word_index,
    )
    if expected_start_frame_sha256 and current.fingerprint_sha256 != _digest(
        expected_start_frame_sha256,
        name="expected_start_frame_sha256",
    ):
        raise ReferenceCanonicalEnsembleError(
            "restart state does not reproduce the checkpoint frame"
        )
    if start_step == 0:
        evaluated_frame_count = 1
        trajectory_head = _trajectory_head("", current, evaluated_frame_count)
    captured = [current]
    attempts: list[ReferenceBarostatAttempt] = []
    timestep = config.timestep_ps
    half_timestep = 0.5 * timestep
    inverse_mass = (
        FORCE_KCAL_PER_MOL_ANGSTROM_TO_ACCELERATION_ANGSTROM_PER_PS2_PER_DA
        / masses.view(1, -1, 1)
    )
    for offset in range(1, steps + 1):
        step = start_step + offset
        velocities = velocities + half_timestep * forces * inverse_mass
        predicted = _wrap_coordinates(
            coordinates + half_timestep * velocities,
            lengths,
        )
        coordinates, velocities, shake_iterations, position_residual = (
            _project_positions(
                source_system,
                lengths,
                coordinates,
                predicted,
                velocities,
                masses,
                constraint_config,
                half_timestep,
                step=step,
            )
        )
        cumulative_shake_iterations += shake_iterations
        max_position_residual = max(max_position_residual, position_residual)
        velocities = _thermostat_ou_step(
            velocities,
            masses,
            config,
            random_stream,
        )
        velocities, rattle_iterations, velocity_residual = _project_velocities(
            source_system,
            lengths,
            coordinates,
            velocities,
            masses,
            constraint_config,
            step=step,
        )
        cumulative_rattle_iterations += rattle_iterations
        max_velocity_residual = max(max_velocity_residual, velocity_residual)
        predicted = _wrap_coordinates(
            coordinates + half_timestep * velocities,
            lengths,
        )
        coordinates, velocities, shake_iterations, position_residual = (
            _project_positions(
                source_system,
                lengths,
                coordinates,
                predicted,
                velocities,
                masses,
                constraint_config,
                half_timestep,
                step=step,
            )
        )
        cumulative_shake_iterations += shake_iterations
        max_position_residual = max(max_position_residual, position_residual)
        potential, next_forces = _evaluate(
            source_system,
            coordinates,
            lengths,
            parameters,
            config,
        )
        velocities = velocities + half_timestep * next_forces * inverse_mass
        velocities, rattle_iterations, velocity_residual = _project_velocities(
            source_system,
            lengths,
            coordinates,
            velocities,
            masses,
            constraint_config,
            step=step,
        )
        cumulative_rattle_iterations += rattle_iterations
        max_velocity_residual = max(max_velocity_residual, velocity_residual)
        forces = next_forces
        if config.barostat is not None and step % config.barostat.interval_steps == 0:
            assert lengths is not None
            (
                attempt,
                coordinates,
                lengths,
                potential,
                forces,
            ) = _attempt_barostat(
                step=step,
                source_system=source_system,
                coordinates=coordinates,
                lengths=lengths,
                potential=potential,
                forces=forces,
                masses=masses,
                components=components,
                parameters=parameters,
                config=config,
                constraint_config=constraint_config,
                random_stream=random_stream,
            )
            attempts.append(attempt)
            cumulative_barostat_attempts += 1
            if attempt.accepted:
                cumulative_barostat_accepts += 1
            else:
                cumulative_barostat_rejects += 1
            barostat_head = _barostat_head(
                barostat_head,
                attempt,
                cumulative_barostat_attempts,
            )
            state_system = _system_for_state(
                source_system,
                coordinates,
                lengths,
            )
            observed_position, observed_velocity = _constraint_residuals(
                state_system,
                coordinates,
                velocities,
                constraint_config,
            )
            max_position_residual = max(
                max_position_residual,
                observed_position,
            )
            max_velocity_residual = max(
                max_velocity_residual,
                observed_velocity,
            )
        pressure = None
        if (
            config.barostat is not None
            and step % config.barostat.pressure_observation_stride == 0
        ):
            assert lengths is not None
            pressure = _pressure_observation(
                source_system,
                coordinates,
                lengths,
                masses,
                components,
                parameters,
                config,
            )
        current = _frame(
            step=step,
            config=config,
            coordinates=coordinates,
            velocities=velocities,
            lengths=lengths,
            potential=potential,
            masses=masses,
            degrees_of_freedom=degrees,
            instantaneous_pressure=pressure,
            max_position_residual=max_position_residual,
            max_velocity_residual=max_velocity_residual,
            cumulative_shake_iterations=cumulative_shake_iterations,
            cumulative_rattle_iterations=cumulative_rattle_iterations,
            cumulative_barostat_attempts=cumulative_barostat_attempts,
            cumulative_barostat_accepts=cumulative_barostat_accepts,
            cumulative_barostat_rejects=cumulative_barostat_rejects,
            random_word_index=random_stream.word_index,
        )
        evaluated_frame_count += 1
        trajectory_head = _trajectory_head(
            trajectory_head,
            current,
            evaluated_frame_count,
        )
        if step % config.trajectory_stride == 0 or offset == steps:
            captured.append(current)
    checkpoint = _checkpoint(
        provenance=provenance,
        config=config,
        constraint_config=constraint_config,
        frame=current,
        trajectory_head=trajectory_head,
        evaluated_frame_count=evaluated_frame_count,
        barostat_head=barostat_head,
    )
    final_system = source_system.with_coordinates(
        current.coordinates,
        operation=(
            f"reference_{config.ensemble.lower()}_baoab_steps_"
            f"{start_step}_to_{current.step}"
        ),
        operation_evidence_sha256=checkpoint.checkpoint_sha256,
    )
    if current.cell_lengths_angstrom is not None:
        final_system = replace(
            final_system,
            cell=UnitCell.orthorhombic(
                current.cell_lengths_angstrom,
                dtype=torch.float64,
                device="cpu",
            ),
        )
    return ReferenceCanonicalEnsembleResult(
        start_step=start_step,
        end_step=current.step,
        frames=tuple(captured),
        barostat_attempts=tuple(attempts),
        checkpoint=checkpoint,
        system=final_system,
        provenance=provenance,
    )


def run_reference_canonical_ensemble(
    system: AllAtomSystem,
    parameters: ReferenceForceFieldParameters,
    velocities_angstrom_per_ps: torch.Tensor,
    *,
    steps: int,
    config: ReferenceCanonicalEnsembleConfig | None = None,
    constraint_config: ReferenceSHAKERATTLEConfig | None = None,
) -> ReferenceCanonicalEnsembleResult:
    """Run a fresh bounded NVT or NPT segment from one source system."""

    active = ReferenceCanonicalEnsembleConfig() if config is None else config
    active_constraints = (
        ReferenceSHAKERATTLEConfig()
        if constraint_config is None
        else constraint_config
    )
    if not isinstance(active, ReferenceCanonicalEnsembleConfig):
        raise ReferenceCanonicalEnsembleError(
            "config must be ReferenceCanonicalEnsembleConfig"
        )
    if not isinstance(active_constraints, ReferenceSHAKERATTLEConfig):
        raise ReferenceCanonicalEnsembleError(
            "constraint_config must be ReferenceSHAKERATTLEConfig"
        )
    count = _exact_int(
        steps,
        name="steps",
        minimum=1,
        maximum=MAX_REFERENCE_CANONICAL_ENSEMBLE_STEPS_PER_CALL,
    )
    _require_source_system(system)
    velocity = velocities_angstrom_per_ps
    if not isinstance(velocity, torch.Tensor):
        raise ReferenceCanonicalEnsembleError(
            "velocities must be a torch.Tensor"
        )
    if velocity.shape == (system.atom_count, 3):
        velocity = velocity.unsqueeze(0)
    if velocity.shape != (1, system.atom_count, 3):
        raise ReferenceCanonicalEnsembleError(
            "velocities must have shape [N,3] or [1,N,3]"
        )
    if velocity.dtype != torch.float64 or velocity.device.type != "cpu":
        raise ReferenceCanonicalEnsembleError(
            "velocities must use CPU float64"
        )
    if not bool(torch.isfinite(velocity).all().item()):
        raise ReferenceCanonicalEnsembleError("velocities must be finite")
    lengths = _cell_lengths(system)
    coordinates = _wrap_coordinates(system.coordinates.detach().clone(), lengths)
    return _run_segment(
        system,
        parameters,
        active,
        active_constraints,
        coordinates=coordinates,
        velocities=velocity.detach().clone(),
        lengths=lengths,
        start_step=0,
        steps=count,
        trajectory_head="",
        evaluated_frame_count=0,
        barostat_head="",
        random_word_index=0,
        max_position_residual=0.0,
        max_velocity_residual=0.0,
        cumulative_shake_iterations=0,
        cumulative_rattle_iterations=0,
        cumulative_barostat_attempts=0,
        cumulative_barostat_accepts=0,
        cumulative_barostat_rejects=0,
    )


def resume_reference_canonical_ensemble(
    source_system: AllAtomSystem,
    parameters: ReferenceForceFieldParameters,
    checkpoint: ReferenceCanonicalEnsembleCheckpoint,
    *,
    additional_steps: int,
) -> ReferenceCanonicalEnsembleResult:
    """Resume only after exact source, config, runtime, RNG, and cell replay."""

    if not isinstance(checkpoint, ReferenceCanonicalEnsembleCheckpoint):
        raise ReferenceCanonicalEnsembleError("checkpoint type is invalid")
    count = _exact_int(
        additional_steps,
        name="additional_steps",
        minimum=1,
        maximum=MAX_REFERENCE_CANONICAL_ENSEMBLE_STEPS_PER_CALL,
    )
    provenance = _provenance(
        source_system,
        parameters,
        checkpoint.config,
        checkpoint.constraint_config,
    )
    if provenance.to_dict() != {
        "source_system_sha256": checkpoint.source_system_sha256,
        "topology_sha256": checkpoint.topology_sha256,
        "parameter_fingerprint_sha256": checkpoint.parameter_fingerprint_sha256,
        "config_fingerprint_sha256": checkpoint.config.fingerprint_sha256,
        "constraint_config_fingerprint_sha256": (
            checkpoint.constraint_config.fingerprint_sha256
        ),
        "algorithm_id": checkpoint.algorithm_id,
        "device": checkpoint.device,
        "dtype": checkpoint.dtype,
        "torch_version": checkpoint.torch_version,
        "random_algorithm_id": REFERENCE_COUNTER_RNG_ALGORITHM_ID,
    }:
        raise ReferenceCanonicalEnsembleError(
            "checkpoint source, parameter, config, or runtime provenance mismatch"
        )
    lengths = (
        None
        if checkpoint.cell_lengths_angstrom is None
        else torch.tensor(
            checkpoint.cell_lengths_angstrom,
            dtype=torch.float64,
        )
    )
    return _run_segment(
        source_system,
        parameters,
        checkpoint.config,
        checkpoint.constraint_config,
        coordinates=checkpoint.coordinates.detach().clone(),
        velocities=checkpoint.velocities_angstrom_per_ps.detach().clone(),
        lengths=lengths,
        start_step=checkpoint.step,
        steps=count,
        trajectory_head=checkpoint.trajectory_head_sha256,
        evaluated_frame_count=checkpoint.evaluated_frame_count,
        barostat_head=checkpoint.barostat_head_sha256,
        random_word_index=checkpoint.random_word_index,
        max_position_residual=(
            checkpoint.max_abs_position_constraint_residual_angstrom
        ),
        max_velocity_residual=(
            checkpoint.max_abs_velocity_constraint_residual_angstrom_per_ps
        ),
        cumulative_shake_iterations=(
            checkpoint.cumulative_shake_iteration_count
        ),
        cumulative_rattle_iterations=(
            checkpoint.cumulative_rattle_iteration_count
        ),
        cumulative_barostat_attempts=(
            checkpoint.cumulative_barostat_attempt_count
        ),
        cumulative_barostat_accepts=(
            checkpoint.cumulative_barostat_accept_count
        ),
        cumulative_barostat_rejects=(
            checkpoint.cumulative_barostat_reject_count
        ),
        expected_start_frame_sha256=checkpoint.current_frame_sha256,
    )


def run_reference_nvt(
    system: AllAtomSystem,
    parameters: ReferenceForceFieldParameters,
    velocities_angstrom_per_ps: torch.Tensor,
    *,
    steps: int,
    config: ReferenceCanonicalEnsembleConfig | None = None,
    constraint_config: ReferenceSHAKERATTLEConfig | None = None,
) -> ReferenceCanonicalEnsembleResult:
    """Run a bounded NVT segment and reject an attached barostat."""

    active = ReferenceCanonicalEnsembleConfig() if config is None else config
    if not isinstance(active, ReferenceCanonicalEnsembleConfig):
        raise ReferenceCanonicalEnsembleError(
            "config must be ReferenceCanonicalEnsembleConfig"
        )
    if active.barostat is not None:
        raise ReferenceCanonicalEnsembleError(
            "run_reference_nvt requires barostat=None"
        )
    return run_reference_canonical_ensemble(
        system,
        parameters,
        velocities_angstrom_per_ps,
        steps=steps,
        config=active,
        constraint_config=constraint_config,
    )


def run_reference_npt(
    system: AllAtomSystem,
    parameters: ReferenceForceFieldParameters,
    velocities_angstrom_per_ps: torch.Tensor,
    *,
    steps: int,
    config: ReferenceCanonicalEnsembleConfig,
    constraint_config: ReferenceSHAKERATTLEConfig | None = None,
) -> ReferenceCanonicalEnsembleResult:
    """Run a bounded NPT segment and require an explicit barostat config."""

    if not isinstance(config, ReferenceCanonicalEnsembleConfig):
        raise ReferenceCanonicalEnsembleError(
            "config must be ReferenceCanonicalEnsembleConfig"
        )
    if config.barostat is None:
        raise ReferenceCanonicalEnsembleError(
            "run_reference_npt requires a barostat config"
        )
    return run_reference_canonical_ensemble(
        system,
        parameters,
        velocities_angstrom_per_ps,
        steps=steps,
        config=config,
        constraint_config=constraint_config,
    )


def resume_reference_nvt(
    source_system: AllAtomSystem,
    parameters: ReferenceForceFieldParameters,
    checkpoint: ReferenceCanonicalEnsembleCheckpoint,
    *,
    additional_steps: int,
) -> ReferenceCanonicalEnsembleResult:
    """Resume a checkpoint only when it records the NVT ensemble."""

    if not isinstance(checkpoint, ReferenceCanonicalEnsembleCheckpoint):
        raise ReferenceCanonicalEnsembleError("checkpoint type is invalid")
    if checkpoint.config.barostat is not None:
        raise ReferenceCanonicalEnsembleError(
            "resume_reference_nvt requires an NVT checkpoint"
        )
    return resume_reference_canonical_ensemble(
        source_system,
        parameters,
        checkpoint,
        additional_steps=additional_steps,
    )


def resume_reference_npt(
    source_system: AllAtomSystem,
    parameters: ReferenceForceFieldParameters,
    checkpoint: ReferenceCanonicalEnsembleCheckpoint,
    *,
    additional_steps: int,
) -> ReferenceCanonicalEnsembleResult:
    """Resume a checkpoint only when it records the NPT ensemble."""

    if not isinstance(checkpoint, ReferenceCanonicalEnsembleCheckpoint):
        raise ReferenceCanonicalEnsembleError("checkpoint type is invalid")
    if checkpoint.config.barostat is None:
        raise ReferenceCanonicalEnsembleError(
            "resume_reference_npt requires an NPT checkpoint"
        )
    return resume_reference_canonical_ensemble(
        source_system,
        parameters,
        checkpoint,
        additional_steps=additional_steps,
    )


__all__ = [
    "BAR_ANGSTROM3_TO_KCAL_PER_MOL",
    "MAX_BAROSTAT_VOLUME_RATIO_PER_ATTEMPT",
    "MAX_REFERENCE_CANONICAL_ENSEMBLE_BAROSTAT_ATTEMPTS",
    "MAX_REFERENCE_CANONICAL_ENSEMBLE_CHECKPOINT_BYTES",
    "MAX_REFERENCE_CANONICAL_ENSEMBLE_RETAINED_FRAMES",
    "MAX_REFERENCE_CANONICAL_ENSEMBLE_STEPS_PER_CALL",
    "MAX_REFERENCE_COUNTER_RNG_WORD_INDEX",
    "MIN_BAROSTAT_VOLUME_RATIO_PER_ATTEMPT",
    "REFERENCE_BAROSTAT_ATTEMPT_CHAIN_SCHEMA_ID",
    "REFERENCE_BAROSTAT_ATTEMPT_SCHEMA_ID",
    "REFERENCE_CANONICAL_ENSEMBLE_ALGORITHM_ID",
    "REFERENCE_CANONICAL_ENSEMBLE_CHECKPOINT_SCHEMA_ID",
    "REFERENCE_CANONICAL_ENSEMBLE_CONFIG_SCHEMA_ID",
    "REFERENCE_CANONICAL_ENSEMBLE_FRAME_SCHEMA_ID",
    "REFERENCE_CANONICAL_ENSEMBLE_RESULT_SCHEMA_ID",
    "REFERENCE_CANONICAL_ENSEMBLE_SCIENTIFIC_BLOCKERS",
    "REFERENCE_CANONICAL_ENSEMBLE_TRAJECTORY_CHAIN_SCHEMA_ID",
    "REFERENCE_COUNTER_RNG_ALGORITHM_ID",
    "REFERENCE_LANGEVIN_THERMOSTAT_CONFIG_SCHEMA_ID",
    "REFERENCE_MONTE_CARLO_BAROSTAT_CONFIG_SCHEMA_ID",
    "ReferenceBarostatAttempt",
    "ReferenceCanonicalEnsembleCheckpoint",
    "ReferenceCanonicalEnsembleConfig",
    "ReferenceCanonicalEnsembleError",
    "ReferenceCanonicalEnsembleFrame",
    "ReferenceCanonicalEnsembleProvenance",
    "ReferenceCanonicalEnsembleResult",
    "ReferenceLangevinThermostatConfig",
    "ReferenceMonteCarloBarostatConfig",
    "resume_reference_canonical_ensemble",
    "resume_reference_npt",
    "resume_reference_nvt",
    "run_reference_canonical_ensemble",
    "run_reference_npt",
    "run_reference_nvt",
]
