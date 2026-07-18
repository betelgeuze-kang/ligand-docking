"""Bounded deterministic minimization on the provisional v2 constraint surface."""

from __future__ import annotations

from base64 import b64decode, b64encode
from binascii import Error as Base64Error
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

from betelgeuze_engine_v2.geometry import RadiusGraphConfig, build_compact_radius_graph
from betelgeuze_engine_v2.molecular import (
    AllAtomSystem,
    canonical_system_sha256,
    canonical_topology_sha256,
)
from .reference_forcefield_v2 import (
    REFERENCE_DISTANCE_CONSTRAINT_PROJECTION_SCHEMA_ID,
    DistanceConstraintProjectionConfig,
    DistanceConstraintProjectionResult,
    ReferenceForceFieldV2ApplicabilityError,
    ReferenceForceFieldV2Parameters,
    evaluate_reference_force_field_v2,
    project_distance_constraints,
)
from .reference_minimization import ReferenceMinimizationConfig
from .reference_solvation import (
    FixedBornPolarSolvationParameters,
    ReferenceFixedBornSolvationApplicabilityError,
    evaluate_reference_force_field_v2_with_fixed_born,
)


REFERENCE_CONSTRAINED_MINIMIZATION_ALGORITHM_ID = (
    "betelgeuze.engine_v2_reference_constrained_steepest_descent/2.0.0"
)
REFERENCE_CONSTRAINED_MINIMIZATION_CONFIG_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_constrained_minimization_config/1.0.0"
)
REFERENCE_CONSTRAINED_MINIMIZATION_CHECKPOINT_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_constrained_minimization_checkpoint/3.0.0"
)
REFERENCE_CONSTRAINED_MINIMIZATION_RESULT_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_constrained_minimization_result/3.0.0"
)
REFERENCE_CONSTRAINED_MINIMIZATION_MAX_FORCE_PROJECTION_SWEEPS = 1_000
REFERENCE_CONSTRAINED_MINIMIZATION_SCIENTIFIC_BLOCKERS = (
    "caller_supplied_extension_parameters_not_independently_reviewed",
    "harmonic_out_of_plane_improper_not_scientifically_validated",
    "equal_weight_distance_constraints_ignore_atomic_masses",
    "constrained_minimization_not_scientifically_validated",
    "independent_constrained_minimization_evidence_missing",
    "general_improper_and_constraint_assignment_not_implemented",
    "long_range_vacuum_electrostatics_not_supported",
    "solvation_scope_limited_to_fixed_effective_radius_polar_gb",
    "effective_born_radius_estimation_not_implemented",
    "nonpolar_solvation_not_implemented",
    "solvated_constrained_minimization_not_scientifically_validated",
    "product_integration_not_qualified",
)


class ReferenceConstrainedMinimizationError(ValueError):
    """The constrained minimization request violates its bounded contract."""


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
        raise ReferenceConstrainedMinimizationError(
            "constrained minimization payload is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _digest(value: object, *, name: str) -> str:
    if not isinstance(value, str):
        raise ReferenceConstrainedMinimizationError(f"{name} must be a SHA-256 digest")
    digest = value.strip().lower()
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise ReferenceConstrainedMinimizationError(
            f"{name} must be a lowercase SHA-256 digest"
        )
    return digest


def _exact_int(value: object, *, name: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool):
        raise ReferenceConstrainedMinimizationError(f"{name} must be an integer")
    try:
        result = int(operator.index(value))
    except TypeError:
        raise ReferenceConstrainedMinimizationError(
            f"{name} must be an integer"
        ) from None
    if result < minimum or result > maximum:
        raise ReferenceConstrainedMinimizationError(
            f"{name} must be in [{minimum},{maximum}]"
        )
    return result


def _finite_float(
    value: object,
    *,
    name: str,
    minimum: float | None = None,
    maximum: float | None = None,
    minimum_inclusive: bool = False,
) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ReferenceConstrainedMinimizationError(
            f"{name} must be a finite real number"
        )
    result = float(value)
    if not math.isfinite(result):
        raise ReferenceConstrainedMinimizationError(f"{name} must be finite")
    if minimum is not None:
        invalid = result < minimum if minimum_inclusive else result <= minimum
        if invalid:
            relation = ">=" if minimum_inclusive else ">"
            raise ReferenceConstrainedMinimizationError(
                f"{name} must be {relation} {minimum}"
            )
    if maximum is not None and result > maximum:
        raise ReferenceConstrainedMinimizationError(f"{name} must be <= {maximum}")
    return result


def _freeze_json(value: Any, *, path: str = "payload") -> Any:
    if value is None or isinstance(value, (bool, str, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ReferenceConstrainedMinimizationError(
                f"{path} contains a non-finite float"
            )
        return float(value)
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise ReferenceConstrainedMinimizationError(
                f"{path} keys must be strings"
            )
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
    raise ReferenceConstrainedMinimizationError(
        f"{path} contains unsupported JSON value {type(value).__name__}"
    )


def _thaw_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return value


def _coordinate_bytes(coordinates: torch.Tensor) -> bytes:
    values = coordinates.detach().to(dtype=torch.float64, device="cpu").contiguous()
    payload = bytearray(8 * values.numel())
    for index, value in enumerate(values.view(-1).tolist()):
        struct.pack_into("<d", payload, 8 * index, float(value))
    return bytes(payload)


def _coordinate_digest(coordinates: torch.Tensor) -> str:
    return hashlib.sha256(_coordinate_bytes(coordinates)).hexdigest()


def _coordinate_hex_rows(
    coordinates: torch.Tensor,
) -> tuple[tuple[str, str, str], ...]:
    if coordinates.device.type != "cpu" or coordinates.dtype != torch.float64:
        raise ReferenceConstrainedMinimizationError(
            "trace coordinates must be CPU float64"
        )
    rows = coordinates.detach().contiguous()
    if rows.ndim != 3 or rows.shape[0] != 1 or rows.shape[2] != 3:
        raise ReferenceConstrainedMinimizationError(
            "trace coordinates must have shape [1,N,3]"
        )
    return tuple(
        tuple(float(value).hex() for value in row)  # type: ignore[misc]
        for row in rows[0].tolist()
    )


def _require_coordinate_hex_rows(
    value: object,
) -> tuple[tuple[str, str, str], ...]:
    if not isinstance(value, list) or not value:
        raise ReferenceConstrainedMinimizationError(
            "observation coordinate trace must cover every atom"
        )
    normalized: list[tuple[str, str, str]] = []
    for row in value:
        if not isinstance(row, list) or len(row) != 3:
            raise ReferenceConstrainedMinimizationError(
                "observation coordinates must have [atom,3] shape"
            )
        values: list[str] = []
        for item in row:
            if not isinstance(item, str):
                raise ReferenceConstrainedMinimizationError(
                    "observation coordinate must be canonical binary64 hex"
                )
            try:
                number = float.fromhex(item)
            except ValueError as exc:
                raise ReferenceConstrainedMinimizationError(
                    "observation coordinate must be canonical binary64 hex"
                ) from exc
            if not math.isfinite(number) or number.hex() != item:
                raise ReferenceConstrainedMinimizationError(
                    "observation coordinate must be canonical finite binary64 hex"
                )
            values.append(item)
        normalized.append((values[0], values[1], values[2]))
    return tuple(normalized)


def _coordinate_hex_digest(
    rows: tuple[tuple[str, str, str], ...],
) -> str:
    raw = bytearray()
    for row in rows:
        for item in row:
            raw.extend(struct.pack("<d", float.fromhex(item)))
    return hashlib.sha256(raw).hexdigest()


def _same_float(first: float, second: float) -> bool:
    return struct.pack("<d", first) == struct.pack("<d", second)


@dataclass(frozen=True, slots=True)
class ReferenceConstrainedMinimizationConfig:
    """Numerical, projection, and capacity bounds for one constrained run."""

    minimization: ReferenceMinimizationConfig = field(
        default_factory=ReferenceMinimizationConfig
    )
    constraint_projection: DistanceConstraintProjectionConfig = field(
        default_factory=DistanceConstraintProjectionConfig
    )
    force_projection_max_sweeps: int = 100
    force_projection_tolerance_kcal_per_mol_angstrom: float = 1.0e-8
    schema_id: str = REFERENCE_CONSTRAINED_MINIMIZATION_CONFIG_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != REFERENCE_CONSTRAINED_MINIMIZATION_CONFIG_SCHEMA_ID:
            raise ReferenceConstrainedMinimizationError(
                "unsupported constrained minimization config schema"
            )
        if not isinstance(self.minimization, ReferenceMinimizationConfig):
            raise ReferenceConstrainedMinimizationError(
                "minimization must be ReferenceMinimizationConfig"
            )
        if not isinstance(
            self.constraint_projection, DistanceConstraintProjectionConfig
        ):
            raise ReferenceConstrainedMinimizationError(
                "constraint_projection must be DistanceConstraintProjectionConfig"
            )
        object.__setattr__(
            self,
            "force_projection_max_sweeps",
            _exact_int(
                self.force_projection_max_sweeps,
                name="force_projection_max_sweeps",
                minimum=1,
                maximum=REFERENCE_CONSTRAINED_MINIMIZATION_MAX_FORCE_PROJECTION_SWEEPS,
            ),
        )
        object.__setattr__(
            self,
            "force_projection_tolerance_kcal_per_mol_angstrom",
            _finite_float(
                self.force_projection_tolerance_kcal_per_mol_angstrom,
                name="force_projection_tolerance_kcal_per_mol_angstrom",
                minimum=0.0,
            ),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "algorithm_id": REFERENCE_CONSTRAINED_MINIMIZATION_ALGORITHM_ID,
            "minimization": self.minimization.to_dict(),
            "constraint_projection": self.constraint_projection.to_dict(),
            "force_projection_max_sweeps": self.force_projection_max_sweeps,
            "force_projection_tolerance_kcal_per_mol_angstrom": (
                self.force_projection_tolerance_kcal_per_mol_angstrom
            ),
            "constraint_weighting": "equal_weight_without_atomic_masses",
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _sha256(self.to_dict())

    @classmethod
    def from_dict(
        cls, value: object
    ) -> "ReferenceConstrainedMinimizationConfig":
        if not isinstance(value, Mapping):
            raise ReferenceConstrainedMinimizationError(
                "checkpoint config must be a mapping"
            )
        try:
            minimization_payload = value["minimization"]
            projection_payload = value["constraint_projection"]
            if not isinstance(minimization_payload, Mapping) or not isinstance(
                projection_payload, Mapping
            ):
                raise ReferenceConstrainedMinimizationError(
                    "checkpoint nested config must be a mapping"
                )
            minimization = ReferenceMinimizationConfig(
                **{
                    key: item
                    for key, item in minimization_payload.items()
                    if key != "algorithm_id"
                }
            )
            projection = DistanceConstraintProjectionConfig(
                **{
                    key: item
                    for key, item in projection_payload.items()
                    if key != "algorithm"
                }
            )
            row = cls(
                minimization=minimization,
                constraint_projection=projection,
                force_projection_max_sweeps=value["force_projection_max_sweeps"],
                force_projection_tolerance_kcal_per_mol_angstrom=value[
                    "force_projection_tolerance_kcal_per_mol_angstrom"
                ],
                schema_id=str(value["schema_id"]),
            )
        except KeyError as exc:
            raise ReferenceConstrainedMinimizationError(
                f"checkpoint config is missing {exc.args[0]}"
            ) from None
        if row.to_dict() != dict(value):
            raise ReferenceConstrainedMinimizationError(
                "checkpoint constrained minimization config is not canonical"
            )
        return row


def _projection_document(
    result: DistanceConstraintProjectionResult,
) -> Mapping[str, object]:
    payload = {
        "schema_id": result.schema_id,
        "status": result.status,
        "failure_code": result.failure_code,
        "source_system_sha256": result.source_system_sha256,
        "parameter_fingerprint_sha256": result.parameter_fingerprint_sha256,
        "config_fingerprint_sha256": result.config_fingerprint_sha256,
        "final_coordinates_sha256": _coordinate_digest(result.system.coordinates),
        "projection_sha256": result.projection_sha256,
        "iterations": [row.to_dict() for row in result.iterations],
    }
    return _validate_projection_document(payload)


def _validate_projection_document(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ReferenceConstrainedMinimizationError(
            "constraint projection observation must be a mapping"
        )
    required = {
        "schema_id",
        "status",
        "failure_code",
        "source_system_sha256",
        "parameter_fingerprint_sha256",
        "config_fingerprint_sha256",
        "final_coordinates_sha256",
        "projection_sha256",
        "iterations",
    }
    if set(value) != required:
        raise ReferenceConstrainedMinimizationError(
            "constraint projection observation fields are not canonical"
        )
    payload = _thaw_json(_freeze_json(dict(value), path="constraint_projection"))
    if payload["schema_id"] != REFERENCE_DISTANCE_CONSTRAINT_PROJECTION_SCHEMA_ID:
        raise ReferenceConstrainedMinimizationError(
            "constraint projection observation schema is invalid"
        )
    for key in (
        "source_system_sha256",
        "parameter_fingerprint_sha256",
        "config_fingerprint_sha256",
        "final_coordinates_sha256",
        "projection_sha256",
    ):
        payload[key] = _digest(payload[key], name=key)
    if not isinstance(payload["iterations"], list) or not payload["iterations"]:
        raise ReferenceConstrainedMinimizationError(
            "constraint projection observation requires iteration rows"
        )
    projection = {
        "schema_id": payload["schema_id"],
        "source_system_sha256": payload["source_system_sha256"],
        "parameter_fingerprint_sha256": payload[
            "parameter_fingerprint_sha256"
        ],
        "config_fingerprint_sha256": payload["config_fingerprint_sha256"],
        "status": payload["status"],
        "failure_code": payload["failure_code"],
        "final_coordinates_sha256": payload["final_coordinates_sha256"],
        "iterations": payload["iterations"],
    }
    if _sha256(projection) != payload["projection_sha256"]:
        raise ReferenceConstrainedMinimizationError(
            "constraint projection observation digest mismatch"
        )
    if (payload["status"] == "converged") != (payload["failure_code"] is None):
        raise ReferenceConstrainedMinimizationError(
            "constraint projection status and failure code disagree"
        )
    return _freeze_json(payload, path="constraint_projection")


def _projection_max_residual(document: Mapping[str, object]) -> float:
    iterations = document["iterations"]
    if not isinstance(iterations, tuple) or not iterations:
        raise ReferenceConstrainedMinimizationError(
            "constraint projection iteration rows are invalid"
        )
    final = iterations[-1]
    if not isinstance(final, Mapping):
        raise ReferenceConstrainedMinimizationError(
            "constraint projection final row is invalid"
        )
    return _finite_float(
        final["max_absolute_residual_angstrom"],
        name="constraint projection maximum residual",
        minimum=0.0,
        minimum_inclusive=True,
    )


@dataclass(frozen=True, slots=True)
class ReferenceConstrainedMinimizationObservation:
    iteration: int
    trial: int
    evaluation_index: int
    outcome: str
    raw_coordinates_angstrom_hex: tuple[tuple[str, str, str], ...]
    raw_coordinates_sha256: str
    projected_coordinates_angstrom_hex: tuple[tuple[str, str, str], ...]
    projected_coordinates_sha256: str
    step_size_angstrom2_mol_per_kcal: float
    energy_kcal_per_mol: float | None
    max_tangent_force_kcal_per_mol_angstrom: float | None
    max_constraint_residual_angstrom: float
    force_projection_sweeps: int | None
    max_constraint_force_residual_kcal_per_mol_angstrom: float | None
    constraint_projection: Mapping[str, object]
    failure_code: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "iteration": self.iteration,
            "trial": self.trial,
            "evaluation_index": self.evaluation_index,
            "outcome": self.outcome,
            "raw_coordinates_angstrom_hex": [
                list(row) for row in self.raw_coordinates_angstrom_hex
            ],
            "raw_coordinates_sha256": self.raw_coordinates_sha256,
            "projected_coordinates_angstrom_hex": [
                list(row) for row in self.projected_coordinates_angstrom_hex
            ],
            "projected_coordinates_sha256": self.projected_coordinates_sha256,
            "step_size_angstrom2_mol_per_kcal": (
                self.step_size_angstrom2_mol_per_kcal
            ),
            "energy_kcal_per_mol": self.energy_kcal_per_mol,
            "max_tangent_force_kcal_per_mol_angstrom": (
                self.max_tangent_force_kcal_per_mol_angstrom
            ),
            "max_constraint_residual_angstrom": (
                self.max_constraint_residual_angstrom
            ),
            "force_projection_sweeps": self.force_projection_sweeps,
            "max_constraint_force_residual_kcal_per_mol_angstrom": (
                self.max_constraint_force_residual_kcal_per_mol_angstrom
            ),
            "constraint_projection": _thaw_json(self.constraint_projection),
            "failure_code": self.failure_code,
        }

    @classmethod
    def from_dict(
        cls, value: object
    ) -> "ReferenceConstrainedMinimizationObservation":
        if not isinstance(value, Mapping):
            raise ReferenceConstrainedMinimizationError(
                "checkpoint observation must be a mapping"
        )
        try:
            raw_coordinate_rows = _require_coordinate_hex_rows(
                value["raw_coordinates_angstrom_hex"]
            )
            projected_coordinate_rows = _require_coordinate_hex_rows(
                value["projected_coordinates_angstrom_hex"]
            )
            force_sweeps = value["force_projection_sweeps"]
            force_residual = value[
                "max_constraint_force_residual_kcal_per_mol_angstrom"
            ]
            row = cls(
                iteration=_exact_int(
                    value["iteration"], name="observation iteration", minimum=0, maximum=1_000
                ),
                trial=_exact_int(
                    value["trial"], name="observation trial", minimum=0, maximum=65
                ),
                evaluation_index=_exact_int(
                    value["evaluation_index"],
                    name="observation evaluation_index",
                    minimum=1,
                    maximum=65_001,
                ),
                outcome=str(value["outcome"]),
                raw_coordinates_angstrom_hex=raw_coordinate_rows,
                raw_coordinates_sha256=_digest(
                    value["raw_coordinates_sha256"],
                    name="raw_coordinates_sha256",
                ),
                projected_coordinates_angstrom_hex=projected_coordinate_rows,
                projected_coordinates_sha256=_digest(
                    value["projected_coordinates_sha256"],
                    name="projected_coordinates_sha256",
                ),
                step_size_angstrom2_mol_per_kcal=_finite_float(
                    value["step_size_angstrom2_mol_per_kcal"],
                    name="observation step size",
                    minimum=0.0,
                    minimum_inclusive=True,
                ),
                energy_kcal_per_mol=(
                    None
                    if value["energy_kcal_per_mol"] is None
                    else _finite_float(
                        value["energy_kcal_per_mol"], name="observation energy"
                    )
                ),
                max_tangent_force_kcal_per_mol_angstrom=(
                    None
                    if value["max_tangent_force_kcal_per_mol_angstrom"] is None
                    else _finite_float(
                        value["max_tangent_force_kcal_per_mol_angstrom"],
                        name="observation tangent force",
                        minimum=0.0,
                        minimum_inclusive=True,
                    )
                ),
                max_constraint_residual_angstrom=_finite_float(
                    value["max_constraint_residual_angstrom"],
                    name="observation constraint residual",
                    minimum=0.0,
                    minimum_inclusive=True,
                ),
                force_projection_sweeps=(
                    None
                    if force_sweeps is None
                    else _exact_int(
                        force_sweeps,
                        name="force projection sweeps",
                        minimum=0,
                        maximum=REFERENCE_CONSTRAINED_MINIMIZATION_MAX_FORCE_PROJECTION_SWEEPS,
                    )
                ),
                max_constraint_force_residual_kcal_per_mol_angstrom=(
                    None
                    if force_residual is None
                    else _finite_float(
                        force_residual,
                        name="constraint force residual",
                        minimum=0.0,
                        minimum_inclusive=True,
                    )
                ),
                constraint_projection=_validate_projection_document(
                    value["constraint_projection"]
                ),
                failure_code=(
                    None if value["failure_code"] is None else str(value["failure_code"])
                ),
            )
        except KeyError as exc:
            raise ReferenceConstrainedMinimizationError(
                f"checkpoint observation is missing {exc.args[0]}"
            ) from None
        if _coordinate_hex_digest(row.raw_coordinates_angstrom_hex) != (
            row.raw_coordinates_sha256
        ) or _coordinate_hex_digest(row.projected_coordinates_angstrom_hex) != (
            row.projected_coordinates_sha256
        ):
            raise ReferenceConstrainedMinimizationError(
                "checkpoint observation coordinate payload digest mismatch"
            )
        allowed = {
            "initial",
            "accepted",
            "rejected_constraint_projection",
            "rejected_projected_displacement",
            "rejected_applicability",
            "rejected_nonfinite",
            "rejected_force_projection",
            "rejected_non_descent",
            "rejected_armijo",
        }
        if row.outcome not in allowed:
            raise ReferenceConstrainedMinimizationError(
                "checkpoint observation outcome is invalid"
            )
        rejected = row.outcome.startswith("rejected_")
        if rejected != (row.failure_code is not None):
            raise ReferenceConstrainedMinimizationError(
                "observation outcome and failure code disagree"
            )
        evaluated = row.outcome in {
            "initial",
            "accepted",
            "rejected_force_projection",
            "rejected_non_descent",
            "rejected_armijo",
        }
        has_energy_force = (
            row.energy_kcal_per_mol is not None
            and row.max_tangent_force_kcal_per_mol_angstrom is not None
            and row.force_projection_sweeps is not None
            and row.max_constraint_force_residual_kcal_per_mol_angstrom is not None
        )
        if evaluated != has_energy_force:
            raise ReferenceConstrainedMinimizationError(
                "observation evaluation fields disagree with its outcome"
            )
        if row.to_dict() != dict(value):
            raise ReferenceConstrainedMinimizationError(
                "checkpoint observation is not canonical"
            )
        return row


@dataclass(frozen=True, slots=True)
class ReferenceConstrainedMinimizationCheckpoint:
    source_system_sha256: str
    topology_sha256: str
    parameter_fingerprint_sha256: str
    solvation_parameter_fingerprint_sha256: str | None
    config: Mapping[str, object]
    config_fingerprint_sha256: str
    accepted_iterations: int
    evaluation_count: int
    initial_energy_kcal_per_mol: float
    initial_max_tangent_force_kcal_per_mol_angstrom: float
    current_energy_kcal_per_mol: float
    current_max_tangent_force_kcal_per_mol_angstrom: float
    current_max_constraint_residual_angstrom: float
    coordinate_shape: tuple[int, int, int]
    coordinates_f64le_base64: str
    coordinates_sha256: str
    observations: tuple[ReferenceConstrainedMinimizationObservation, ...]
    checkpoint_sha256: str
    schema_id: str = REFERENCE_CONSTRAINED_MINIMIZATION_CHECKPOINT_SCHEMA_ID
    algorithm_id: str = REFERENCE_CONSTRAINED_MINIMIZATION_ALGORITHM_ID

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "algorithm_id": self.algorithm_id,
            "source_system_sha256": self.source_system_sha256,
            "topology_sha256": self.topology_sha256,
            "parameter_fingerprint_sha256": self.parameter_fingerprint_sha256,
            "solvation_parameter_fingerprint_sha256": (
                self.solvation_parameter_fingerprint_sha256
            ),
            "config": _thaw_json(self.config),
            "config_fingerprint_sha256": self.config_fingerprint_sha256,
            "accepted_iterations": self.accepted_iterations,
            "evaluation_count": self.evaluation_count,
            "initial_energy_kcal_per_mol": self.initial_energy_kcal_per_mol,
            "initial_max_tangent_force_kcal_per_mol_angstrom": (
                self.initial_max_tangent_force_kcal_per_mol_angstrom
            ),
            "current_energy_kcal_per_mol": self.current_energy_kcal_per_mol,
            "current_max_tangent_force_kcal_per_mol_angstrom": (
                self.current_max_tangent_force_kcal_per_mol_angstrom
            ),
            "current_max_constraint_residual_angstrom": (
                self.current_max_constraint_residual_angstrom
            ),
            "coordinate_shape": list(self.coordinate_shape),
            "coordinate_dtype": "float64-le",
            "coordinates_f64le_base64": self.coordinates_f64le_base64,
            "coordinates_sha256": self.coordinates_sha256,
            "observations": [row.to_dict() for row in self.observations],
        }

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "checkpoint_sha256": self.checkpoint_sha256}

    def coordinates(self) -> torch.Tensor:
        try:
            raw = b64decode(self.coordinates_f64le_base64, validate=True)
        except (Base64Error, ValueError) as exc:
            raise ReferenceConstrainedMinimizationError(
                "checkpoint coordinates are not canonical base64"
            ) from exc
        expected = math.prod(self.coordinate_shape) * 8
        if len(raw) != expected or hashlib.sha256(raw).hexdigest() != self.coordinates_sha256:
            raise ReferenceConstrainedMinimizationError(
                "checkpoint coordinate byte identity mismatch"
            )
        values = [item[0] for item in struct.iter_unpack("<d", raw)]
        tensor = torch.tensor(values, dtype=torch.float64).reshape(self.coordinate_shape)
        if not bool(torch.isfinite(tensor).all().item()):
            raise ReferenceConstrainedMinimizationError(
                "checkpoint coordinates must be finite"
            )
        if _coordinate_bytes(tensor) != raw:
            raise ReferenceConstrainedMinimizationError(
                "checkpoint coordinates do not round-trip as binary64"
            )
        return tensor


def require_reference_constrained_minimization_checkpoint_document(
    value: object,
) -> ReferenceConstrainedMinimizationCheckpoint:
    if not isinstance(value, Mapping):
        raise ReferenceConstrainedMinimizationError(
            "constrained minimization checkpoint must be a mapping"
        )
    required = {
        "schema_id",
        "algorithm_id",
        "source_system_sha256",
        "topology_sha256",
        "parameter_fingerprint_sha256",
        "solvation_parameter_fingerprint_sha256",
        "config",
        "config_fingerprint_sha256",
        "accepted_iterations",
        "evaluation_count",
        "initial_energy_kcal_per_mol",
        "initial_max_tangent_force_kcal_per_mol_angstrom",
        "current_energy_kcal_per_mol",
        "current_max_tangent_force_kcal_per_mol_angstrom",
        "current_max_constraint_residual_angstrom",
        "coordinate_shape",
        "coordinate_dtype",
        "coordinates_f64le_base64",
        "coordinates_sha256",
        "observations",
        "checkpoint_sha256",
    }
    if set(value) != required:
        raise ReferenceConstrainedMinimizationError(
            "constrained minimization checkpoint fields are not canonical"
        )
    if value["schema_id"] != REFERENCE_CONSTRAINED_MINIMIZATION_CHECKPOINT_SCHEMA_ID:
        raise ReferenceConstrainedMinimizationError(
            "unsupported constrained minimization checkpoint schema"
        )
    if value["algorithm_id"] != REFERENCE_CONSTRAINED_MINIMIZATION_ALGORITHM_ID:
        raise ReferenceConstrainedMinimizationError(
            "constrained minimization checkpoint algorithm mismatch"
        )
    if value["coordinate_dtype"] != "float64-le":
        raise ReferenceConstrainedMinimizationError(
            "checkpoint coordinate dtype must be float64-le"
        )
    config = ReferenceConstrainedMinimizationConfig.from_dict(value["config"])
    config_fingerprint = _digest(
        value["config_fingerprint_sha256"], name="config_fingerprint_sha256"
    )
    if config.fingerprint_sha256 != config_fingerprint:
        raise ReferenceConstrainedMinimizationError(
            "checkpoint config fingerprint mismatch"
        )
    checkpoint_sha256 = _digest(
        value["checkpoint_sha256"], name="checkpoint_sha256"
    )
    projection = {key: _thaw_json(item) for key, item in value.items() if key != "checkpoint_sha256"}
    if _sha256(projection) != checkpoint_sha256:
        raise ReferenceConstrainedMinimizationError("checkpoint digest mismatch")
    shape_payload = value["coordinate_shape"]
    if not isinstance(shape_payload, (tuple, list)) or len(shape_payload) != 3:
        raise ReferenceConstrainedMinimizationError(
            "checkpoint coordinate shape must contain three dimensions"
        )
    shape = tuple(
        _exact_int(item, name="coordinate shape", minimum=1, maximum=1_000_000)
        for item in shape_payload
    )
    if shape[0] != 1 or shape[2] != 3:
        raise ReferenceConstrainedMinimizationError(
            "checkpoint coordinates must have shape [1,N,3]"
        )
    observations_payload = value["observations"]
    if not isinstance(observations_payload, (tuple, list)) or not observations_payload:
        raise ReferenceConstrainedMinimizationError(
            "checkpoint requires an observation ledger"
        )
    observations = tuple(
        ReferenceConstrainedMinimizationObservation.from_dict(row)
        for row in observations_payload
    )
    if any(
        len(row.raw_coordinates_angstrom_hex) != shape[1]
        or len(row.projected_coordinates_angstrom_hex) != shape[1]
        for row in observations
    ):
        raise ReferenceConstrainedMinimizationError(
            "checkpoint observation atom count does not match coordinate shape"
        )
    if [row.evaluation_index for row in observations] != list(
        range(1, len(observations) + 1)
    ):
        raise ReferenceConstrainedMinimizationError(
            "checkpoint observation evaluation sequence is invalid"
        )
    initial = observations[0]
    if initial.outcome != "initial" or initial.iteration != 0 or initial.trial != 0:
        raise ReferenceConstrainedMinimizationError(
            "checkpoint first observation must be the initial state"
        )
    expected_iteration = 1
    expected_trial = 0
    for row in observations[1:]:
        if (
            row.iteration != expected_iteration
            or row.trial != expected_trial
            or row.iteration > config.minimization.max_iterations
            or row.trial > config.minimization.max_backtracks
        ):
            raise ReferenceConstrainedMinimizationError(
                "checkpoint projected line-search sequence is invalid"
            )
        if row.outcome == "accepted":
            expected_iteration += 1
            expected_trial = 0
        elif row.outcome.startswith("rejected_"):
            expected_trial += 1
        else:
            raise ReferenceConstrainedMinimizationError(
                "checkpoint observation ledger repeats the initial state"
            )
    accepted_rows = [row for row in observations if row.outcome == "accepted"]
    accepted = _exact_int(
        value["accepted_iterations"],
        name="accepted_iterations",
        minimum=0,
        maximum=config.minimization.max_iterations,
    )
    if len(accepted_rows) != accepted or [row.iteration for row in accepted_rows] != list(
        range(1, accepted + 1)
    ):
        raise ReferenceConstrainedMinimizationError(
            "checkpoint accepted iteration sequence is invalid"
        )
    evaluation_count = _exact_int(
        value["evaluation_count"],
        name="evaluation_count",
        minimum=1,
        maximum=(config.minimization.max_iterations * 65 + 1),
    )
    if evaluation_count != len(observations):
        raise ReferenceConstrainedMinimizationError(
            "checkpoint evaluation count does not match observations"
        )
    checkpoint = ReferenceConstrainedMinimizationCheckpoint(
        source_system_sha256=_digest(
            value["source_system_sha256"], name="source_system_sha256"
        ),
        topology_sha256=_digest(value["topology_sha256"], name="topology_sha256"),
        parameter_fingerprint_sha256=_digest(
            value["parameter_fingerprint_sha256"],
            name="parameter_fingerprint_sha256",
        ),
        solvation_parameter_fingerprint_sha256=(
            None
            if value["solvation_parameter_fingerprint_sha256"] is None
            else _digest(
                value["solvation_parameter_fingerprint_sha256"],
                name="solvation_parameter_fingerprint_sha256",
            )
        ),
        config=_freeze_json(config.to_dict(), path="config"),
        config_fingerprint_sha256=config_fingerprint,
        accepted_iterations=accepted,
        evaluation_count=evaluation_count,
        initial_energy_kcal_per_mol=_finite_float(
            value["initial_energy_kcal_per_mol"], name="initial energy"
        ),
        initial_max_tangent_force_kcal_per_mol_angstrom=_finite_float(
            value["initial_max_tangent_force_kcal_per_mol_angstrom"],
            name="initial tangent force",
            minimum=0.0,
            minimum_inclusive=True,
        ),
        current_energy_kcal_per_mol=_finite_float(
            value["current_energy_kcal_per_mol"], name="current energy"
        ),
        current_max_tangent_force_kcal_per_mol_angstrom=_finite_float(
            value["current_max_tangent_force_kcal_per_mol_angstrom"],
            name="current tangent force",
            minimum=0.0,
            minimum_inclusive=True,
        ),
        current_max_constraint_residual_angstrom=_finite_float(
            value["current_max_constraint_residual_angstrom"],
            name="current constraint residual",
            minimum=0.0,
            minimum_inclusive=True,
        ),
        coordinate_shape=shape,
        coordinates_f64le_base64=str(value["coordinates_f64le_base64"]),
        coordinates_sha256=_digest(
            value["coordinates_sha256"], name="coordinates_sha256"
        ),
        observations=observations,
        checkpoint_sha256=checkpoint_sha256,
    )
    for row in observations:
        document = row.constraint_projection
        if (
            document["parameter_fingerprint_sha256"]
            != checkpoint.parameter_fingerprint_sha256
            or document["config_fingerprint_sha256"]
            != config.constraint_projection.fingerprint_sha256
        ):
            raise ReferenceConstrainedMinimizationError(
                "checkpoint constraint projection identity crosswire"
            )
        if document["final_coordinates_sha256"] != row.projected_coordinates_sha256:
            raise ReferenceConstrainedMinimizationError(
                "checkpoint projected coordinate identity mismatch"
            )
        if not _same_float(
            row.max_constraint_residual_angstrom,
            _projection_max_residual(document),
        ):
            raise ReferenceConstrainedMinimizationError(
                "checkpoint constraint residual disagrees with projection rows"
            )
        projection_converged = document["status"] == "converged"
        if (row.outcome == "rejected_constraint_projection") == projection_converged:
            raise ReferenceConstrainedMinimizationError(
                "checkpoint projection outcome disagrees with projection status"
            )
    coordinates = checkpoint.coordinates()
    current = accepted_rows[-1] if accepted_rows else initial
    if _coordinate_digest(coordinates) != current.projected_coordinates_sha256:
        raise ReferenceConstrainedMinimizationError(
            "checkpoint coordinates do not match the accepted ledger state"
        )
    if current.energy_kcal_per_mol is None or current.max_tangent_force_kcal_per_mol_angstrom is None:
        raise ReferenceConstrainedMinimizationError(
            "checkpoint current observation is missing energy or tangent force"
        )
    comparisons = (
        (checkpoint.initial_energy_kcal_per_mol, initial.energy_kcal_per_mol),
        (
            checkpoint.initial_max_tangent_force_kcal_per_mol_angstrom,
            initial.max_tangent_force_kcal_per_mol_angstrom,
        ),
        (checkpoint.current_energy_kcal_per_mol, current.energy_kcal_per_mol),
        (
            checkpoint.current_max_tangent_force_kcal_per_mol_angstrom,
            current.max_tangent_force_kcal_per_mol_angstrom,
        ),
        (
            checkpoint.current_max_constraint_residual_angstrom,
            current.max_constraint_residual_angstrom,
        ),
    )
    if any(second is None or not _same_float(first, second) for first, second in comparisons):
        raise ReferenceConstrainedMinimizationError(
            "checkpoint scalar state does not match the observation ledger"
        )
    if checkpoint.to_dict() != dict(value):
        raise ReferenceConstrainedMinimizationError("checkpoint is not canonical")
    return checkpoint


def _minimum_image(delta: torch.Tensor, system: AllAtomSystem) -> torch.Tensor:
    if system.cell is None:
        return delta
    lengths = system.cell.orthorhombic_lengths().to(
        dtype=delta.dtype, device=delta.device
    )
    periodic = torch.tensor(system.cell.periodic, dtype=torch.bool, device=delta.device)
    safe_lengths = torch.where(periodic, lengths, torch.ones_like(lengths))
    wrapped = delta - torch.round(delta / safe_lengths) * safe_lengths
    return torch.where(periodic, wrapped, delta)


def _constraint_vector(
    coordinates: torch.Tensor, system: AllAtomSystem, atom_i: int, atom_j: int
) -> torch.Tensor:
    return _minimum_image(coordinates[0, atom_i] - coordinates[0, atom_j], system)


def _project_forces_to_constraint_tangent(
    system: AllAtomSystem,
    coordinates: torch.Tensor,
    forces: torch.Tensor,
    parameters: ReferenceForceFieldV2Parameters,
    config: ReferenceConstrainedMinimizationConfig,
) -> tuple[torch.Tensor, float, float, int, bool]:
    projected = forces.detach().clone()
    if not parameters.constraints:
        maximum = float(torch.linalg.vector_norm(projected[0], dim=-1).max().item())
        return projected, maximum, 0.0, 0, True
    constraint_degrees = [0] * system.atom_count
    for constraint in parameters.constraints:
        constraint_degrees[constraint.atom_i] += 1
        constraint_degrees[constraint.atom_j] += 1
    relaxation_degree = max(constraint_degrees, default=1)
    maximum_residual = math.inf
    for sweep in range(1, config.force_projection_max_sweeps + 1):
        updates = torch.zeros_like(projected)
        for constraint in parameters.constraints:
            vector = _constraint_vector(
                coordinates, system, constraint.atom_i, constraint.atom_j
            )
            distance = float(torch.linalg.vector_norm(vector).item())
            if distance <= 1.0e-12:
                raise ReferenceConstrainedMinimizationError(
                    "constraint tangent is undefined at zero pair distance"
                )
            direction = vector / distance
            relative = torch.dot(
                projected[0, constraint.atom_i] - projected[0, constraint.atom_j],
                direction,
            )
            correction = 0.5 * relative * direction
            updates[0, constraint.atom_i] -= correction
            updates[0, constraint.atom_j] += correction
        projected += updates / float(relaxation_degree)
        residuals = []
        for constraint in parameters.constraints:
            vector = _constraint_vector(
                coordinates, system, constraint.atom_i, constraint.atom_j
            )
            distance = float(torch.linalg.vector_norm(vector).item())
            direction = vector / distance
            residuals.append(
                abs(
                    float(
                        torch.dot(
                            projected[0, constraint.atom_i]
                            - projected[0, constraint.atom_j],
                            direction,
                        ).item()
                    )
                )
            )
        maximum_residual = max(residuals, default=0.0)
        if maximum_residual <= (
            config.force_projection_tolerance_kcal_per_mol_angstrom
        ):
            maximum = float(
                torch.linalg.vector_norm(projected[0], dim=-1).max().item()
            )
            return projected, maximum, maximum_residual, sweep, True
    maximum = float(torch.linalg.vector_norm(projected[0], dim=-1).max().item())
    return (
        projected,
        maximum,
        maximum_residual,
        config.force_projection_max_sweeps,
        False,
    )


def _validate_source_system(system: AllAtomSystem) -> None:
    if system.coordinates.device.type != "cpu" or system.coordinates.dtype != torch.float64:
        raise ReferenceConstrainedMinimizationError(
            "constrained minimization requires CPU float64 coordinates"
        )
    if system.model_count != 1:
        raise ReferenceConstrainedMinimizationError(
            "constrained minimization requires exactly one model"
        )
    if tuple(system.coordinates.shape) != (1, system.atom_count, 3):
        raise ReferenceConstrainedMinimizationError(
            "system atom identity and coordinate shape mismatch"
        )
    if not bool(torch.isfinite(system.coordinates).all().item()):
        raise ReferenceConstrainedMinimizationError(
            "constrained minimization coordinates must be finite"
        )


def _evaluate(
    source_system: AllAtomSystem,
    coordinates: torch.Tensor,
    parameters: ReferenceForceFieldV2Parameters,
    solvation_parameters: FixedBornPolarSolvationParameters | None,
    config: ReferenceConstrainedMinimizationConfig,
    *,
    operation: str,
) -> tuple[float, torch.Tensor, float, float, int, bool]:
    state = source_system.with_coordinates(coordinates, operation=operation)
    neighbors = build_compact_radius_graph(
        state.coordinates,
        RadiusGraphConfig(
            cutoff_angstrom=parameters.base_parameters.cutoff_angstrom,
            max_neighbors=config.minimization.max_neighbors,
            max_atoms_per_cell=config.minimization.max_atoms_per_cell,
        ),
        cell=state.cell,
    )
    if solvation_parameters is None:
        evaluation = evaluate_reference_force_field_v2(state, neighbors, parameters)
    else:
        evaluation = evaluate_reference_force_field_v2_with_fixed_born(
            state,
            neighbors,
            parameters,
            solvation_parameters,
        )
    energy = float(evaluation.term.energy[0].item())
    forces = evaluation.term.forces.detach().clone()
    if not math.isfinite(energy) or not bool(torch.isfinite(forces).all().item()):
        raise FloatingPointError("v2 reference evaluation produced non-finite values")
    tangent, maximum, residual, sweeps, converged = (
        _project_forces_to_constraint_tangent(
            source_system, coordinates, forces, parameters, config
        )
    )
    return energy, tangent, maximum, residual, sweeps, converged


def _build_checkpoint(
    *,
    source_system: AllAtomSystem,
    parameters: ReferenceForceFieldV2Parameters,
    solvation_parameters: FixedBornPolarSolvationParameters | None,
    config: ReferenceConstrainedMinimizationConfig,
    coordinates: torch.Tensor,
    accepted_iterations: int,
    evaluation_count: int,
    initial_energy: float,
    initial_max_force: float,
    current_energy: float,
    current_max_force: float,
    current_max_constraint_residual: float,
    observations: tuple[ReferenceConstrainedMinimizationObservation, ...],
) -> ReferenceConstrainedMinimizationCheckpoint:
    raw = _coordinate_bytes(coordinates)
    payload: dict[str, object] = {
        "schema_id": REFERENCE_CONSTRAINED_MINIMIZATION_CHECKPOINT_SCHEMA_ID,
        "algorithm_id": REFERENCE_CONSTRAINED_MINIMIZATION_ALGORITHM_ID,
        "source_system_sha256": canonical_system_sha256(source_system),
        "topology_sha256": canonical_topology_sha256(source_system),
        "parameter_fingerprint_sha256": parameters.fingerprint_sha256,
        "solvation_parameter_fingerprint_sha256": (
            None
            if solvation_parameters is None
            else solvation_parameters.fingerprint_sha256
        ),
        "config": config.to_dict(),
        "config_fingerprint_sha256": config.fingerprint_sha256,
        "accepted_iterations": accepted_iterations,
        "evaluation_count": evaluation_count,
        "initial_energy_kcal_per_mol": initial_energy,
        "initial_max_tangent_force_kcal_per_mol_angstrom": initial_max_force,
        "current_energy_kcal_per_mol": current_energy,
        "current_max_tangent_force_kcal_per_mol_angstrom": current_max_force,
        "current_max_constraint_residual_angstrom": current_max_constraint_residual,
        "coordinate_shape": list(coordinates.shape),
        "coordinate_dtype": "float64-le",
        "coordinates_f64le_base64": b64encode(raw).decode("ascii"),
        "coordinates_sha256": hashlib.sha256(raw).hexdigest(),
        "observations": [row.to_dict() for row in observations],
    }
    return require_reference_constrained_minimization_checkpoint_document(
        {**payload, "checkpoint_sha256": _sha256(payload)}
    )


@dataclass(frozen=True, slots=True)
class ReferenceConstrainedMinimizationResult:
    status: str
    failure_code: str | None
    initial_energy_kcal_per_mol: float
    final_energy_kcal_per_mol: float
    initial_max_tangent_force_kcal_per_mol_angstrom: float
    final_max_tangent_force_kcal_per_mol_angstrom: float
    final_max_constraint_residual_angstrom: float
    accepted_iterations: int
    rejected_evaluations: int
    evaluation_count: int
    observations: tuple[ReferenceConstrainedMinimizationObservation, ...]
    checkpoint: ReferenceConstrainedMinimizationCheckpoint
    system: AllAtomSystem
    solvation_parameter_fingerprint_sha256: str | None
    scientific_blockers: tuple[str, ...] = (
        REFERENCE_CONSTRAINED_MINIMIZATION_SCIENTIFIC_BLOCKERS
    )
    schema_id: str = REFERENCE_CONSTRAINED_MINIMIZATION_RESULT_SCHEMA_ID

    @property
    def converged(self) -> bool:
        return self.status == "converged"

    @property
    def scientifically_validated(self) -> bool:
        return False

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "algorithm_id": REFERENCE_CONSTRAINED_MINIMIZATION_ALGORITHM_ID,
            "status": self.status,
            "failure_code": self.failure_code,
            "converged": self.converged,
            "initial_energy_kcal_per_mol": self.initial_energy_kcal_per_mol,
            "final_energy_kcal_per_mol": self.final_energy_kcal_per_mol,
            "initial_max_tangent_force_kcal_per_mol_angstrom": (
                self.initial_max_tangent_force_kcal_per_mol_angstrom
            ),
            "final_max_tangent_force_kcal_per_mol_angstrom": (
                self.final_max_tangent_force_kcal_per_mol_angstrom
            ),
            "final_max_constraint_residual_angstrom": (
                self.final_max_constraint_residual_angstrom
            ),
            "accepted_iterations": self.accepted_iterations,
            "rejected_evaluations": self.rejected_evaluations,
            "evaluation_count": self.evaluation_count,
            "checkpoint_sha256": self.checkpoint.checkpoint_sha256,
            "observations": [row.to_dict() for row in self.observations],
            "coordinate_trace_length": len(self.observations),
            "coordinate_trace_sha256": _sha256(
                [row.to_dict() for row in self.observations]
            ),
            "solvation_parameter_fingerprint_sha256": (
                self.solvation_parameter_fingerprint_sha256
            ),
            "final_system_sha256": canonical_system_sha256(self.system),
            "scientifically_validated": False,
            "claim_safe": False,
            "scientific_blockers": list(self.scientific_blockers),
        }


def minimize_reference_force_field_v2_constrained(
    system: AllAtomSystem,
    parameters: ReferenceForceFieldV2Parameters,
    config: ReferenceConstrainedMinimizationConfig | None = None,
    *,
    solvation_parameters: FixedBornPolarSolvationParameters | None = None,
    checkpoint: (
        ReferenceConstrainedMinimizationCheckpoint | Mapping[str, object] | None
    ) = None,
    pause_after_accepted_iterations: int | None = None,
) -> ReferenceConstrainedMinimizationResult:
    """Minimize optional fixed-Born-solvated v2 energy on distance constraints."""

    config = ReferenceConstrainedMinimizationConfig() if config is None else config
    if not isinstance(config, ReferenceConstrainedMinimizationConfig):
        raise ReferenceConstrainedMinimizationError(
            "config must be ReferenceConstrainedMinimizationConfig"
        )
    if not isinstance(parameters, ReferenceForceFieldV2Parameters):
        raise ReferenceConstrainedMinimizationError(
            "parameters must be ReferenceForceFieldV2Parameters"
        )
    if solvation_parameters is not None and not isinstance(
        solvation_parameters, FixedBornPolarSolvationParameters
    ):
        raise ReferenceConstrainedMinimizationError(
            "solvation_parameters must be FixedBornPolarSolvationParameters or None"
        )
    _validate_source_system(system)
    source_sha256 = canonical_system_sha256(system)
    topology_sha256 = canonical_topology_sha256(system)
    expected_solvation_fingerprint = (
        None
        if solvation_parameters is None
        else solvation_parameters.fingerprint_sha256
    )

    checkpoint_row: ReferenceConstrainedMinimizationCheckpoint | None
    if checkpoint is None:
        checkpoint_row = None
    elif isinstance(checkpoint, ReferenceConstrainedMinimizationCheckpoint):
        checkpoint_row = require_reference_constrained_minimization_checkpoint_document(
            checkpoint.to_dict()
        )
    else:
        checkpoint_row = require_reference_constrained_minimization_checkpoint_document(
            checkpoint
        )

    if checkpoint_row is None:
        initial_projection = project_distance_constraints(
            system, parameters, config.constraint_projection
        )
        if not initial_projection.converged:
            raise ReferenceConstrainedMinimizationError(
                "initial constraint projection failed: "
                f"{initial_projection.failure_code} "
                f"({initial_projection.projection_sha256})"
            )
        coordinates = initial_projection.system.coordinates.detach().clone()
        try:
            (
                current_energy,
                current_forces,
                current_max_force,
                force_residual,
                force_sweeps,
                force_converged,
            ) = _evaluate(
                system,
                coordinates,
                parameters,
                solvation_parameters,
                config,
                operation="reference_constrained_minimization_initial_evaluation",
            )
        except (
            ReferenceForceFieldV2ApplicabilityError,
            ReferenceFixedBornSolvationApplicabilityError,
            FloatingPointError,
        ) as exc:
            raise ReferenceConstrainedMinimizationError(
                f"initial constrained minimization state is not evaluable: {exc}"
            ) from exc
        if not force_converged:
            raise ReferenceConstrainedMinimizationError(
                "initial constraint tangent force projection exhausted its budget"
            )
        constraint_document = _projection_document(initial_projection)
        current_constraint_residual = _projection_max_residual(constraint_document)
        observations: list[ReferenceConstrainedMinimizationObservation] = [
            ReferenceConstrainedMinimizationObservation(
                iteration=0,
                trial=0,
                evaluation_index=1,
                outcome="initial",
                raw_coordinates_angstrom_hex=_coordinate_hex_rows(
                    system.coordinates
                ),
                raw_coordinates_sha256=_coordinate_digest(system.coordinates),
                projected_coordinates_angstrom_hex=_coordinate_hex_rows(
                    coordinates
                ),
                projected_coordinates_sha256=_coordinate_digest(coordinates),
                step_size_angstrom2_mol_per_kcal=0.0,
                energy_kcal_per_mol=current_energy,
                max_tangent_force_kcal_per_mol_angstrom=current_max_force,
                max_constraint_residual_angstrom=current_constraint_residual,
                force_projection_sweeps=force_sweeps,
                max_constraint_force_residual_kcal_per_mol_angstrom=force_residual,
                constraint_projection=constraint_document,
            )
        ]
        accepted_iterations = 0
        evaluation_count = 1
        initial_energy = current_energy
        initial_max_force = current_max_force
    else:
        if checkpoint_row.source_system_sha256 != source_sha256:
            raise ReferenceConstrainedMinimizationError(
                "checkpoint source system identity mismatch"
            )
        if checkpoint_row.topology_sha256 != topology_sha256:
            raise ReferenceConstrainedMinimizationError(
                "checkpoint topology identity mismatch"
            )
        if checkpoint_row.parameter_fingerprint_sha256 != parameters.fingerprint_sha256:
            raise ReferenceConstrainedMinimizationError(
                "checkpoint parameter fingerprint mismatch"
            )
        if (
            checkpoint_row.solvation_parameter_fingerprint_sha256
            != expected_solvation_fingerprint
        ):
            raise ReferenceConstrainedMinimizationError(
                "checkpoint solvation parameter fingerprint mismatch"
            )
        if checkpoint_row.config_fingerprint_sha256 != config.fingerprint_sha256:
            raise ReferenceConstrainedMinimizationError(
                "checkpoint config fingerprint mismatch"
            )
        if checkpoint_row.coordinate_shape != (1, system.atom_count, 3):
            raise ReferenceConstrainedMinimizationError("checkpoint atom count mismatch")
        if checkpoint_row.observations[-1].outcome.startswith("rejected_"):
            raise ReferenceConstrainedMinimizationError(
                "terminal failed line-search checkpoint cannot be resumed"
            )
        replayed = minimize_reference_force_field_v2_constrained(
            system,
            parameters,
            config,
            solvation_parameters=solvation_parameters,
            pause_after_accepted_iterations=checkpoint_row.accepted_iterations,
        )
        if replayed.checkpoint.to_dict() != checkpoint_row.to_dict():
            raise ReferenceConstrainedMinimizationError(
                "checkpoint history does not replay exactly from the source system"
            )
        coordinates = checkpoint_row.coordinates()
        verification_projection = project_distance_constraints(
            system.with_coordinates(
                coordinates,
                operation="reference_constrained_minimization_restart_projection",
            ),
            parameters,
            config.constraint_projection,
        )
        if not verification_projection.converged or not torch.equal(
            verification_projection.system.coordinates, coordinates
        ):
            raise ReferenceConstrainedMinimizationError(
                "checkpoint coordinates do not reproduce the constraint surface"
            )
        try:
            (
                current_energy,
                current_forces,
                current_max_force,
                _,
                _,
                force_converged,
            ) = _evaluate(
                system,
                coordinates,
                parameters,
                solvation_parameters,
                config,
                operation="reference_constrained_minimization_restart_verification",
            )
        except (
            ReferenceForceFieldV2ApplicabilityError,
            ReferenceFixedBornSolvationApplicabilityError,
            FloatingPointError,
        ) as exc:
            raise ReferenceConstrainedMinimizationError(
                f"checkpoint state is not evaluable: {exc}"
            ) from exc
        if not force_converged:
            raise ReferenceConstrainedMinimizationError(
                "checkpoint tangent force projection exhausted its budget"
            )
        if not _same_float(
            current_energy, checkpoint_row.current_energy_kcal_per_mol
        ) or not _same_float(
            current_max_force,
            checkpoint_row.current_max_tangent_force_kcal_per_mol_angstrom,
        ):
            raise ReferenceConstrainedMinimizationError(
                "checkpoint state does not reproduce stored energy and tangent force"
            )
        accepted_iterations = checkpoint_row.accepted_iterations
        evaluation_count = checkpoint_row.evaluation_count
        observations = list(checkpoint_row.observations)
        initial_energy = checkpoint_row.initial_energy_kcal_per_mol
        initial_max_force = (
            checkpoint_row.initial_max_tangent_force_kcal_per_mol_angstrom
        )
        current_constraint_residual = (
            checkpoint_row.current_max_constraint_residual_angstrom
        )

    minimum = config.minimization
    pause_at: int | None = None
    if pause_after_accepted_iterations is not None:
        pause_at = _exact_int(
            pause_after_accepted_iterations,
            name="pause_after_accepted_iterations",
            minimum=0,
            maximum=minimum.max_iterations,
        )
        if pause_at < accepted_iterations:
            raise ReferenceConstrainedMinimizationError(
                "pause_after_accepted_iterations precedes checkpoint progress"
            )

    status = "max_iterations_reached"
    failure_code: str | None = "maximum_iteration_budget_exhausted"
    while accepted_iterations < minimum.max_iterations:
        if current_max_force <= minimum.force_tolerance_kcal_per_mol_angstrom:
            status = "converged"
            failure_code = None
            break
        if pause_at is not None and accepted_iterations >= pause_at:
            status = "checkpointed"
            failure_code = None
            break
        iteration = accepted_iterations + 1
        step = minimum.initial_step_size_angstrom2_mol_per_kcal
        direction = current_forces.clone()
        raw_max_displacement = step * current_max_force
        if raw_max_displacement > minimum.maximum_atom_displacement_angstrom:
            direction.mul_(
                minimum.maximum_atom_displacement_angstrom / raw_max_displacement
            )
        accepted = False

        for trial in range(minimum.max_backtracks + 1):
            raw_coordinates = coordinates + step * direction
            raw_digest = _coordinate_digest(raw_coordinates)
            raw_state = system.with_coordinates(
                raw_coordinates,
                operation=(
                    f"reference_constrained_minimization_iteration_{iteration}_"
                    f"trial_{trial}_raw"
                ),
            )
            projection = project_distance_constraints(
                raw_state, parameters, config.constraint_projection
            )
            document = _projection_document(projection)
            trial_coordinates = projection.system.coordinates.detach().clone()
            trial_digest = _coordinate_digest(trial_coordinates)
            constraint_residual = _projection_max_residual(document)
            evaluation_count += 1

            def reject(
                outcome: str,
                code: str,
                *,
                energy: float | None = None,
                maximum_force: float | None = None,
                sweeps: int | None = None,
                force_projection_residual: float | None = None,
            ) -> None:
                observations.append(
                    ReferenceConstrainedMinimizationObservation(
                        iteration=iteration,
                        trial=trial,
                        evaluation_index=evaluation_count,
                        outcome=outcome,
                        raw_coordinates_angstrom_hex=_coordinate_hex_rows(
                            raw_coordinates
                        ),
                        raw_coordinates_sha256=raw_digest,
                        projected_coordinates_angstrom_hex=_coordinate_hex_rows(
                            trial_coordinates
                        ),
                        projected_coordinates_sha256=trial_digest,
                        step_size_angstrom2_mol_per_kcal=step,
                        energy_kcal_per_mol=energy,
                        max_tangent_force_kcal_per_mol_angstrom=maximum_force,
                        max_constraint_residual_angstrom=constraint_residual,
                        force_projection_sweeps=sweeps,
                        max_constraint_force_residual_kcal_per_mol_angstrom=(
                            force_projection_residual
                        ),
                        constraint_projection=document,
                        failure_code=code,
                    )
                )

            if not projection.converged:
                reject(
                    "rejected_constraint_projection",
                    projection.failure_code or "constraint_projection_failed",
                )
                step *= minimum.backtrack_factor
                continue
            maximum_displacement = float(
                torch.linalg.vector_norm(
                    trial_coordinates[0] - coordinates[0], dim=-1
                ).max().item()
            )
            if maximum_displacement > minimum.maximum_atom_displacement_angstrom + 1.0e-12:
                reject(
                    "rejected_projected_displacement",
                    "projected_displacement_bound_exceeded",
                )
                step *= minimum.backtrack_factor
                continue
            try:
                (
                    trial_energy,
                    trial_forces,
                    trial_max_force,
                    force_residual,
                    force_sweeps,
                    force_converged,
                ) = _evaluate(
                    system,
                    trial_coordinates,
                    parameters,
                    solvation_parameters,
                    config,
                    operation=(
                        f"reference_constrained_minimization_iteration_{iteration}_"
                        f"trial_{trial}_evaluation"
                    ),
                )
            except (
                ReferenceForceFieldV2ApplicabilityError,
                ReferenceFixedBornSolvationApplicabilityError,
            ) as exc:
                reject(
                    "rejected_applicability",
                    "reference_v2_evaluator_applicability_failed:"
                    + str(exc).split(":", 1)[0],
                )
                step *= minimum.backtrack_factor
                continue
            except FloatingPointError:
                reject("rejected_nonfinite", "nonfinite_energy_or_force")
                step *= minimum.backtrack_factor
                continue
            if not force_converged:
                reject(
                    "rejected_force_projection",
                    "constraint_tangent_force_projection_budget_exhausted",
                    energy=trial_energy,
                    maximum_force=trial_max_force,
                    sweeps=force_sweeps,
                    force_projection_residual=force_residual,
                )
                step *= minimum.backtrack_factor
                continue
            displacement = trial_coordinates - coordinates
            directional_derivative = -float(
                (current_forces * displacement).sum().item()
            )
            if directional_derivative >= 0.0:
                reject(
                    "rejected_non_descent",
                    "constraint_projection_removed_descent_direction",
                    energy=trial_energy,
                    maximum_force=trial_max_force,
                    sweeps=force_sweeps,
                    force_projection_residual=force_residual,
                )
                step *= minimum.backtrack_factor
                continue
            armijo_limit = current_energy + minimum.armijo_constant * directional_derivative
            if trial_energy > armijo_limit:
                reject(
                    "rejected_armijo",
                    "armijo_decrease_not_satisfied",
                    energy=trial_energy,
                    maximum_force=trial_max_force,
                    sweeps=force_sweeps,
                    force_projection_residual=force_residual,
                )
                step *= minimum.backtrack_factor
                continue
            observations.append(
                ReferenceConstrainedMinimizationObservation(
                    iteration=iteration,
                    trial=trial,
                    evaluation_index=evaluation_count,
                    outcome="accepted",
                    raw_coordinates_angstrom_hex=_coordinate_hex_rows(
                        raw_coordinates
                    ),
                    raw_coordinates_sha256=raw_digest,
                    projected_coordinates_angstrom_hex=_coordinate_hex_rows(
                        trial_coordinates
                    ),
                    projected_coordinates_sha256=trial_digest,
                    step_size_angstrom2_mol_per_kcal=step,
                    energy_kcal_per_mol=trial_energy,
                    max_tangent_force_kcal_per_mol_angstrom=trial_max_force,
                    max_constraint_residual_angstrom=constraint_residual,
                    force_projection_sweeps=force_sweeps,
                    max_constraint_force_residual_kcal_per_mol_angstrom=(
                        force_residual
                    ),
                    constraint_projection=document,
                )
            )
            coordinates = trial_coordinates
            current_energy = trial_energy
            current_forces = trial_forces
            current_max_force = trial_max_force
            current_constraint_residual = constraint_residual
            accepted_iterations += 1
            accepted = True
            break

        if not accepted:
            status = "line_search_failed"
            failure_code = "bounded_projected_backtracking_exhausted"
            break
    else:
        status = "max_iterations_reached"
        failure_code = "maximum_iteration_budget_exhausted"

    if current_max_force <= minimum.force_tolerance_kcal_per_mol_angstrom:
        status = "converged"
        failure_code = None

    rows = tuple(observations)
    checkpoint_result = _build_checkpoint(
        source_system=system,
        parameters=parameters,
        solvation_parameters=solvation_parameters,
        config=config,
        coordinates=coordinates,
        accepted_iterations=accepted_iterations,
        evaluation_count=evaluation_count,
        initial_energy=initial_energy,
        initial_max_force=initial_max_force,
        current_energy=current_energy,
        current_max_force=current_max_force,
        current_max_constraint_residual=current_constraint_residual,
        observations=rows,
    )
    result_system = system.with_coordinates(
        coordinates,
        operation="bounded_reference_force_field_v2_constrained_minimization",
        operation_evidence_sha256=checkpoint_result.checkpoint_sha256,
    )
    return ReferenceConstrainedMinimizationResult(
        status=status,
        failure_code=failure_code,
        initial_energy_kcal_per_mol=initial_energy,
        final_energy_kcal_per_mol=current_energy,
        initial_max_tangent_force_kcal_per_mol_angstrom=initial_max_force,
        final_max_tangent_force_kcal_per_mol_angstrom=current_max_force,
        final_max_constraint_residual_angstrom=current_constraint_residual,
        accepted_iterations=accepted_iterations,
        rejected_evaluations=sum(row.outcome.startswith("rejected_") for row in rows),
        evaluation_count=evaluation_count,
        observations=rows,
        checkpoint=checkpoint_result,
        system=result_system,
        solvation_parameter_fingerprint_sha256=expected_solvation_fingerprint,
    )


__all__ = [
    "REFERENCE_CONSTRAINED_MINIMIZATION_ALGORITHM_ID",
    "REFERENCE_CONSTRAINED_MINIMIZATION_CHECKPOINT_SCHEMA_ID",
    "REFERENCE_CONSTRAINED_MINIMIZATION_CONFIG_SCHEMA_ID",
    "REFERENCE_CONSTRAINED_MINIMIZATION_MAX_FORCE_PROJECTION_SWEEPS",
    "REFERENCE_CONSTRAINED_MINIMIZATION_RESULT_SCHEMA_ID",
    "REFERENCE_CONSTRAINED_MINIMIZATION_SCIENTIFIC_BLOCKERS",
    "ReferenceConstrainedMinimizationCheckpoint",
    "ReferenceConstrainedMinimizationConfig",
    "ReferenceConstrainedMinimizationError",
    "ReferenceConstrainedMinimizationObservation",
    "ReferenceConstrainedMinimizationResult",
    "minimize_reference_force_field_v2_constrained",
    "require_reference_constrained_minimization_checkpoint_document",
]
