"""Bounded deterministic minimization for the unvalidated CPU reference force field."""

from __future__ import annotations

from base64 import b64decode, b64encode
from binascii import Error as Base64Error
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

from betelgeuze_engine_v2.geometry import RadiusGraphConfig, build_compact_radius_graph
from betelgeuze_engine_v2.molecular import (
    AllAtomSystem,
    canonical_system_sha256,
    canonical_topology_sha256,
)
from .reference_forcefield import (
    ReferencePhysicsApplicabilityError,
    evaluate_reference_force_field,
)
from .reference_parameters import ReferenceForceFieldParameters


REFERENCE_MINIMIZATION_ALGORITHM_ID = (
    "betelgeuze.engine_v2_reference_force_steepest_descent/1.0.0"
)
REFERENCE_MINIMIZATION_CONFIG_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_minimization_config/1.0.0"
)
REFERENCE_MINIMIZATION_CHECKPOINT_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_minimization_checkpoint/1.0.0"
)
REFERENCE_MINIMIZATION_RESULT_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_minimization_result/1.0.0"
)
REFERENCE_MINIMIZATION_MAX_ITERATIONS = 1_000
REFERENCE_MINIMIZATION_MAX_BACKTRACKS = 64
REFERENCE_MINIMIZATION_SCIENTIFIC_BLOCKERS = (
    "caller_supplied_reference_parameters_not_independently_reviewed",
    "reference_minimization_not_scientifically_validated",
    "independent_reference_minimization_evidence_missing",
    "public_minimization_validation_missing",
    "product_integration_not_qualified",
)


class ReferenceMinimizationError(ValueError):
    """The minimization request or checkpoint violates the bounded contract."""


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
        raise ReferenceMinimizationError(
            "minimization payload is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _digest(value: object, *, name: str) -> str:
    if not isinstance(value, str):
        raise ReferenceMinimizationError(f"{name} must be a SHA-256 digest")
    digest = value.strip().lower()
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise ReferenceMinimizationError(f"{name} must be a lowercase SHA-256 digest")
    return digest


def _exact_int(
    value: object,
    *,
    name: str,
    minimum: int,
    maximum: int,
) -> int:
    if isinstance(value, bool):
        raise ReferenceMinimizationError(f"{name} must be an integer")
    try:
        result = int(operator.index(value))
    except TypeError:
        raise ReferenceMinimizationError(f"{name} must be an integer") from None
    if result < minimum or result > maximum:
        raise ReferenceMinimizationError(
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
        raise ReferenceMinimizationError(f"{name} must be a finite real number")
    result = float(value)
    if not math.isfinite(result):
        raise ReferenceMinimizationError(f"{name} must be finite")
    if minimum is not None:
        invalid = result < minimum if minimum_inclusive else result <= minimum
        if invalid:
            relation = ">=" if minimum_inclusive else ">"
            raise ReferenceMinimizationError(f"{name} must be {relation} {minimum}")
    if maximum is not None and result > maximum:
        raise ReferenceMinimizationError(f"{name} must be <= {maximum}")
    return result


def _coordinate_bytes(coordinates: torch.Tensor) -> bytes:
    values = coordinates.detach().contiguous().view(-1).tolist()
    payload = bytearray(8 * len(values))
    for index, value in enumerate(values):
        struct.pack_into("<d", payload, 8 * index, float(value))
    return bytes(payload)


def _coordinate_digest(coordinates: torch.Tensor) -> str:
    return hashlib.sha256(_coordinate_bytes(coordinates)).hexdigest()


@dataclass(frozen=True)
class ReferenceMinimizationConfig:
    """Immutable numerical and capacity bounds for one minimization run."""

    max_iterations: int = 100
    max_backtracks: int = 16
    initial_step_size_angstrom2_mol_per_kcal: float = 1.0e-3
    backtrack_factor: float = 0.5
    armijo_constant: float = 1.0e-4
    maximum_atom_displacement_angstrom: float = 0.05
    force_tolerance_kcal_per_mol_angstrom: float = 1.0e-3
    max_neighbors: int = 256
    max_atoms_per_cell: int = 512
    schema_id: str = REFERENCE_MINIMIZATION_CONFIG_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != REFERENCE_MINIMIZATION_CONFIG_SCHEMA_ID:
            raise ReferenceMinimizationError("unsupported minimization config schema")
        object.__setattr__(
            self,
            "max_iterations",
            _exact_int(
                self.max_iterations,
                name="max_iterations",
                minimum=1,
                maximum=REFERENCE_MINIMIZATION_MAX_ITERATIONS,
            ),
        )
        object.__setattr__(
            self,
            "max_backtracks",
            _exact_int(
                self.max_backtracks,
                name="max_backtracks",
                minimum=0,
                maximum=REFERENCE_MINIMIZATION_MAX_BACKTRACKS,
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
        for name in (
            "initial_step_size_angstrom2_mol_per_kcal",
            "maximum_atom_displacement_angstrom",
            "force_tolerance_kcal_per_mol_angstrom",
        ):
            object.__setattr__(
                self,
                name,
                _finite_float(getattr(self, name), name=name, minimum=0.0),
            )
        object.__setattr__(
            self,
            "backtrack_factor",
            _finite_float(
                self.backtrack_factor,
                name="backtrack_factor",
                minimum=0.0,
                maximum=1.0,
            ),
        )
        if self.backtrack_factor >= 1.0:
            raise ReferenceMinimizationError("backtrack_factor must be < 1")
        object.__setattr__(
            self,
            "armijo_constant",
            _finite_float(
                self.armijo_constant,
                name="armijo_constant",
                minimum=0.0,
                maximum=1.0,
            ),
        )
        if self.armijo_constant >= 1.0:
            raise ReferenceMinimizationError("armijo_constant must be < 1")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "algorithm_id": REFERENCE_MINIMIZATION_ALGORITHM_ID,
            "max_iterations": self.max_iterations,
            "max_backtracks": self.max_backtracks,
            "initial_step_size_angstrom2_mol_per_kcal": (
                self.initial_step_size_angstrom2_mol_per_kcal
            ),
            "backtrack_factor": self.backtrack_factor,
            "armijo_constant": self.armijo_constant,
            "maximum_atom_displacement_angstrom": (
                self.maximum_atom_displacement_angstrom
            ),
            "force_tolerance_kcal_per_mol_angstrom": (
                self.force_tolerance_kcal_per_mol_angstrom
            ),
            "max_neighbors": self.max_neighbors,
            "max_atoms_per_cell": self.max_atoms_per_cell,
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _sha256(self.to_dict())


@dataclass(frozen=True)
class ReferenceMinimizationObservation:
    iteration: int
    trial: int
    evaluation_index: int
    outcome: str
    coordinates_sha256: str
    step_size_angstrom2_mol_per_kcal: float
    energy_kcal_per_mol: float | None
    max_force_kcal_per_mol_angstrom: float | None
    failure_code: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "iteration": self.iteration,
            "trial": self.trial,
            "evaluation_index": self.evaluation_index,
            "outcome": self.outcome,
            "coordinates_sha256": self.coordinates_sha256,
            "step_size_angstrom2_mol_per_kcal": (
                self.step_size_angstrom2_mol_per_kcal
            ),
            "energy_kcal_per_mol": self.energy_kcal_per_mol,
            "max_force_kcal_per_mol_angstrom": (
                self.max_force_kcal_per_mol_angstrom
            ),
            "failure_code": self.failure_code,
        }

    @classmethod
    def from_dict(cls, value: object) -> "ReferenceMinimizationObservation":
        if not isinstance(value, Mapping):
            raise ReferenceMinimizationError("checkpoint observation must be a mapping")
        try:
            row = cls(
                iteration=_exact_int(
                    value["iteration"],
                    name="observation iteration",
                    minimum=0,
                    maximum=REFERENCE_MINIMIZATION_MAX_ITERATIONS,
                ),
                trial=_exact_int(
                    value["trial"],
                    name="observation trial",
                    minimum=0,
                    maximum=REFERENCE_MINIMIZATION_MAX_BACKTRACKS + 1,
                ),
                evaluation_index=_exact_int(
                    value["evaluation_index"],
                    name="observation evaluation_index",
                    minimum=1,
                    maximum=(REFERENCE_MINIMIZATION_MAX_ITERATIONS * 65 + 1),
                ),
                outcome=str(value["outcome"]),
                coordinates_sha256=_digest(
                    value["coordinates_sha256"], name="coordinates_sha256"
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
                max_force_kcal_per_mol_angstrom=(
                    None
                    if value["max_force_kcal_per_mol_angstrom"] is None
                    else _finite_float(
                        value["max_force_kcal_per_mol_angstrom"],
                        name="observation max force",
                        minimum=0.0,
                        minimum_inclusive=True,
                    )
                ),
                failure_code=(
                    None
                    if value["failure_code"] is None
                    else str(value["failure_code"])
                ),
            )
        except KeyError as exc:
            raise ReferenceMinimizationError(
                f"checkpoint observation is missing {exc.args[0]}"
            ) from None
        if row.outcome not in {
            "initial",
            "accepted",
            "rejected_armijo",
            "rejected_applicability",
            "rejected_nonfinite",
        }:
            raise ReferenceMinimizationError("checkpoint observation outcome is invalid")
        if not row.failure_code and row.outcome.startswith("rejected_"):
            raise ReferenceMinimizationError("rejected observation requires failure_code")
        if row.failure_code and not row.outcome.startswith("rejected_"):
            raise ReferenceMinimizationError("accepted observation cannot carry failure_code")
        if row.to_dict() != dict(value):
            raise ReferenceMinimizationError("checkpoint observation is not canonical")
        return row


@dataclass(frozen=True)
class ReferenceMinimizationCheckpoint:
    source_system_sha256: str
    topology_sha256: str
    parameter_fingerprint_sha256: str
    config: Mapping[str, object]
    config_fingerprint_sha256: str
    accepted_iterations: int
    evaluation_count: int
    initial_energy_kcal_per_mol: float
    initial_max_force_kcal_per_mol_angstrom: float
    current_energy_kcal_per_mol: float
    current_max_force_kcal_per_mol_angstrom: float
    coordinate_shape: tuple[int, int, int]
    coordinates_f64le_base64: str
    coordinates_sha256: str
    observations: tuple[ReferenceMinimizationObservation, ...]
    checkpoint_sha256: str
    schema_id: str = REFERENCE_MINIMIZATION_CHECKPOINT_SCHEMA_ID
    algorithm_id: str = REFERENCE_MINIMIZATION_ALGORITHM_ID

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "algorithm_id": self.algorithm_id,
            "source_system_sha256": self.source_system_sha256,
            "topology_sha256": self.topology_sha256,
            "parameter_fingerprint_sha256": self.parameter_fingerprint_sha256,
            "config": dict(self.config),
            "config_fingerprint_sha256": self.config_fingerprint_sha256,
            "accepted_iterations": self.accepted_iterations,
            "evaluation_count": self.evaluation_count,
            "initial_energy_kcal_per_mol": self.initial_energy_kcal_per_mol,
            "initial_max_force_kcal_per_mol_angstrom": (
                self.initial_max_force_kcal_per_mol_angstrom
            ),
            "current_energy_kcal_per_mol": self.current_energy_kcal_per_mol,
            "current_max_force_kcal_per_mol_angstrom": (
                self.current_max_force_kcal_per_mol_angstrom
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
            raise ReferenceMinimizationError(
                "checkpoint coordinates are not canonical base64"
            ) from exc
        if b64encode(raw).decode("ascii") != self.coordinates_f64le_base64:
            raise ReferenceMinimizationError(
                "checkpoint coordinates are not canonical base64"
            )
        expected_count = math.prod(self.coordinate_shape)
        if len(raw) != expected_count * 8:
            raise ReferenceMinimizationError("checkpoint coordinate byte length mismatch")
        if hashlib.sha256(raw).hexdigest() != self.coordinates_sha256:
            raise ReferenceMinimizationError("checkpoint coordinate SHA-256 mismatch")
        values = [row[0] for row in struct.iter_unpack("<d", raw)]
        coordinates = torch.tensor(values, dtype=torch.float64).reshape(
            self.coordinate_shape
        )
        if not bool(torch.isfinite(coordinates).all().item()):
            raise ReferenceMinimizationError("checkpoint coordinates are non-finite")
        return coordinates


@dataclass(frozen=True)
class ReferenceMinimizationResult:
    status: str
    failure_code: str | None
    initial_energy_kcal_per_mol: float
    final_energy_kcal_per_mol: float
    initial_max_force_kcal_per_mol_angstrom: float
    final_max_force_kcal_per_mol_angstrom: float
    accepted_iterations: int
    rejected_evaluations: int
    evaluation_count: int
    observations: tuple[ReferenceMinimizationObservation, ...]
    checkpoint: ReferenceMinimizationCheckpoint
    system: AllAtomSystem
    scientific_blockers: tuple[str, ...] = REFERENCE_MINIMIZATION_SCIENTIFIC_BLOCKERS
    schema_id: str = REFERENCE_MINIMIZATION_RESULT_SCHEMA_ID

    @property
    def converged(self) -> bool:
        return self.status == "converged"

    @property
    def energy_decreased(self) -> bool:
        return self.final_energy_kcal_per_mol < self.initial_energy_kcal_per_mol

    @property
    def scientifically_validated(self) -> bool:
        return False

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "algorithm_id": REFERENCE_MINIMIZATION_ALGORITHM_ID,
            "status": self.status,
            "failure_code": self.failure_code,
            "converged": self.converged,
            "energy_decreased": self.energy_decreased,
            "scientifically_validated": False,
            "initial_energy_kcal_per_mol": self.initial_energy_kcal_per_mol,
            "final_energy_kcal_per_mol": self.final_energy_kcal_per_mol,
            "initial_max_force_kcal_per_mol_angstrom": (
                self.initial_max_force_kcal_per_mol_angstrom
            ),
            "final_max_force_kcal_per_mol_angstrom": (
                self.final_max_force_kcal_per_mol_angstrom
            ),
            "accepted_iterations": self.accepted_iterations,
            "rejected_evaluations": self.rejected_evaluations,
            "evaluation_count": self.evaluation_count,
            "checkpoint_sha256": self.checkpoint.checkpoint_sha256,
            "observations": [row.to_dict() for row in self.observations],
            "scientific_blockers": list(self.scientific_blockers),
        }


def _config_from_document(value: object) -> ReferenceMinimizationConfig:
    if not isinstance(value, Mapping):
        raise ReferenceMinimizationError("checkpoint config must be a mapping")
    expected_keys = set(ReferenceMinimizationConfig().to_dict())
    if set(value) != expected_keys:
        raise ReferenceMinimizationError("checkpoint config fields are not canonical")
    if value.get("algorithm_id") != REFERENCE_MINIMIZATION_ALGORITHM_ID:
        raise ReferenceMinimizationError("checkpoint algorithm identity mismatch")
    return ReferenceMinimizationConfig(
        max_iterations=value["max_iterations"],
        max_backtracks=value["max_backtracks"],
        initial_step_size_angstrom2_mol_per_kcal=value[
            "initial_step_size_angstrom2_mol_per_kcal"
        ],
        backtrack_factor=value["backtrack_factor"],
        armijo_constant=value["armijo_constant"],
        maximum_atom_displacement_angstrom=value[
            "maximum_atom_displacement_angstrom"
        ],
        force_tolerance_kcal_per_mol_angstrom=value[
            "force_tolerance_kcal_per_mol_angstrom"
        ],
        max_neighbors=value["max_neighbors"],
        max_atoms_per_cell=value["max_atoms_per_cell"],
        schema_id=str(value["schema_id"]),
    )


def require_reference_minimization_checkpoint_document(
    value: object,
) -> ReferenceMinimizationCheckpoint:
    """Verify a canonical checkpoint and return its immutable representation."""

    if not isinstance(value, Mapping):
        raise ReferenceMinimizationError("checkpoint must be a mapping")
    expected_fields = {
        "schema_id",
        "algorithm_id",
        "source_system_sha256",
        "topology_sha256",
        "parameter_fingerprint_sha256",
        "config",
        "config_fingerprint_sha256",
        "accepted_iterations",
        "evaluation_count",
        "initial_energy_kcal_per_mol",
        "initial_max_force_kcal_per_mol_angstrom",
        "current_energy_kcal_per_mol",
        "current_max_force_kcal_per_mol_angstrom",
        "coordinate_shape",
        "coordinate_dtype",
        "coordinates_f64le_base64",
        "coordinates_sha256",
        "observations",
        "checkpoint_sha256",
    }
    if set(value) != expected_fields:
        raise ReferenceMinimizationError("checkpoint fields are not canonical")
    if value["schema_id"] != REFERENCE_MINIMIZATION_CHECKPOINT_SCHEMA_ID:
        raise ReferenceMinimizationError("unsupported minimization checkpoint schema")
    if value["algorithm_id"] != REFERENCE_MINIMIZATION_ALGORITHM_ID:
        raise ReferenceMinimizationError("checkpoint algorithm identity mismatch")
    if value["coordinate_dtype"] != "float64-le":
        raise ReferenceMinimizationError("checkpoint coordinate dtype must be float64-le")
    projection = {key: value[key] for key in value if key != "checkpoint_sha256"}
    checkpoint_sha256 = _digest(
        value["checkpoint_sha256"], name="checkpoint_sha256"
    )
    if _sha256(projection) != checkpoint_sha256:
        raise ReferenceMinimizationError("checkpoint SHA-256 mismatch")
    config = _config_from_document(value["config"])
    config_fingerprint = _digest(
        value["config_fingerprint_sha256"], name="config_fingerprint_sha256"
    )
    if config.fingerprint_sha256 != config_fingerprint:
        raise ReferenceMinimizationError("checkpoint config fingerprint mismatch")
    shape_value = value["coordinate_shape"]
    if not isinstance(shape_value, list) or len(shape_value) != 3:
        raise ReferenceMinimizationError("checkpoint coordinate shape is invalid")
    shape = tuple(
        _exact_int(item, name="coordinate shape", minimum=1, maximum=1_000_000)
        for item in shape_value
    )
    if shape[0] != 1 or shape[2] != 3:
        raise ReferenceMinimizationError("checkpoint coordinates must have shape [1,N,3]")
    rows_value = value["observations"]
    if not isinstance(rows_value, list) or not rows_value:
        raise ReferenceMinimizationError("checkpoint observations must be non-empty")
    observations = tuple(
        ReferenceMinimizationObservation.from_dict(row) for row in rows_value
    )
    accepted = _exact_int(
        value["accepted_iterations"],
        name="accepted_iterations",
        minimum=0,
        maximum=config.max_iterations,
    )
    evaluation_count = _exact_int(
        value["evaluation_count"],
        name="evaluation_count",
        minimum=1,
        maximum=(config.max_iterations * (config.max_backtracks + 1) + 1),
    )
    if observations[-1].evaluation_index != evaluation_count:
        raise ReferenceMinimizationError("checkpoint evaluation count mismatch")
    if [row.evaluation_index for row in observations] != list(
        range(1, evaluation_count + 1)
    ):
        raise ReferenceMinimizationError(
            "checkpoint observation evaluation indices are not contiguous"
        )
    initial_row = observations[0]
    if initial_row.outcome != "initial" or initial_row.iteration != 0:
        raise ReferenceMinimizationError(
            "checkpoint must begin with the initial evaluation"
        )
    accepted_rows = tuple(row for row in observations if row.outcome == "accepted")
    if sum(row.outcome == "accepted" for row in observations) != accepted:
        raise ReferenceMinimizationError("checkpoint accepted iteration count mismatch")
    if [row.iteration for row in accepted_rows] != list(range(1, accepted + 1)):
        raise ReferenceMinimizationError(
            "checkpoint accepted iteration sequence is invalid"
        )
    for row in observations:
        has_values = (
            row.energy_kcal_per_mol is not None
            and row.max_force_kcal_per_mol_angstrom is not None
        )
        if row.outcome in {"initial", "accepted", "rejected_armijo"} and not has_values:
            raise ReferenceMinimizationError(
                "checkpoint observation is missing energy or force"
            )
        if row.outcome in {"rejected_applicability", "rejected_nonfinite"} and (
            row.energy_kcal_per_mol is not None
            or row.max_force_kcal_per_mol_angstrom is not None
        ):
            raise ReferenceMinimizationError(
                "failed checkpoint observation cannot carry energy or force"
            )
    checkpoint = ReferenceMinimizationCheckpoint(
        source_system_sha256=_digest(
            value["source_system_sha256"], name="source_system_sha256"
        ),
        topology_sha256=_digest(value["topology_sha256"], name="topology_sha256"),
        parameter_fingerprint_sha256=_digest(
            value["parameter_fingerprint_sha256"],
            name="parameter_fingerprint_sha256",
        ),
        config=MappingProxyType(dict(config.to_dict())),
        config_fingerprint_sha256=config_fingerprint,
        accepted_iterations=accepted,
        evaluation_count=evaluation_count,
        initial_energy_kcal_per_mol=_finite_float(
            value["initial_energy_kcal_per_mol"], name="initial energy"
        ),
        initial_max_force_kcal_per_mol_angstrom=_finite_float(
            value["initial_max_force_kcal_per_mol_angstrom"],
            name="initial max force",
            minimum=0.0,
            minimum_inclusive=True,
        ),
        current_energy_kcal_per_mol=_finite_float(
            value["current_energy_kcal_per_mol"], name="current energy"
        ),
        current_max_force_kcal_per_mol_angstrom=_finite_float(
            value["current_max_force_kcal_per_mol_angstrom"],
            name="current max force",
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
    decoded_coordinates = checkpoint.coordinates()
    current_row = accepted_rows[-1] if accepted_rows else initial_row
    if _coordinate_digest(decoded_coordinates) != current_row.coordinates_sha256:
        raise ReferenceMinimizationError(
            "checkpoint current coordinates do not match the accepted ledger state"
        )
    if (
        struct.pack("<d", checkpoint.initial_energy_kcal_per_mol)
        != struct.pack("<d", float(initial_row.energy_kcal_per_mol))
        or struct.pack("<d", checkpoint.initial_max_force_kcal_per_mol_angstrom)
        != struct.pack("<d", float(initial_row.max_force_kcal_per_mol_angstrom))
        or struct.pack("<d", checkpoint.current_energy_kcal_per_mol)
        != struct.pack("<d", float(current_row.energy_kcal_per_mol))
        or struct.pack("<d", checkpoint.current_max_force_kcal_per_mol_angstrom)
        != struct.pack("<d", float(current_row.max_force_kcal_per_mol_angstrom))
    ):
        raise ReferenceMinimizationError(
            "checkpoint energy or force does not match the observation ledger"
        )
    if checkpoint.to_dict() != dict(value):
        raise ReferenceMinimizationError("checkpoint is not canonical")
    return checkpoint


def _build_checkpoint(
    *,
    source_system: AllAtomSystem,
    parameters: ReferenceForceFieldParameters,
    config: ReferenceMinimizationConfig,
    coordinates: torch.Tensor,
    accepted_iterations: int,
    evaluation_count: int,
    initial_energy: float,
    initial_max_force: float,
    current_energy: float,
    current_max_force: float,
    observations: tuple[ReferenceMinimizationObservation, ...],
) -> ReferenceMinimizationCheckpoint:
    raw = _coordinate_bytes(coordinates)
    arguments: dict[str, object] = {
        "schema_id": REFERENCE_MINIMIZATION_CHECKPOINT_SCHEMA_ID,
        "algorithm_id": REFERENCE_MINIMIZATION_ALGORITHM_ID,
        "source_system_sha256": canonical_system_sha256(source_system),
        "topology_sha256": canonical_topology_sha256(source_system),
        "parameter_fingerprint_sha256": parameters.fingerprint_sha256,
        "config": config.to_dict(),
        "config_fingerprint_sha256": config.fingerprint_sha256,
        "accepted_iterations": accepted_iterations,
        "evaluation_count": evaluation_count,
        "initial_energy_kcal_per_mol": initial_energy,
        "initial_max_force_kcal_per_mol_angstrom": initial_max_force,
        "current_energy_kcal_per_mol": current_energy,
        "current_max_force_kcal_per_mol_angstrom": current_max_force,
        "coordinate_shape": list(coordinates.shape),
        "coordinate_dtype": "float64-le",
        "coordinates_f64le_base64": b64encode(raw).decode("ascii"),
        "coordinates_sha256": hashlib.sha256(raw).hexdigest(),
        "observations": [row.to_dict() for row in observations],
    }
    return require_reference_minimization_checkpoint_document(
        {**arguments, "checkpoint_sha256": _sha256(arguments)}
    )


def _validate_source_system(system: AllAtomSystem) -> None:
    if system.coordinates.device.type != "cpu":
        raise ReferenceMinimizationError("reference minimization requires CPU coordinates")
    if system.coordinates.dtype != torch.float64:
        raise ReferenceMinimizationError("reference minimization requires float64 coordinates")
    if system.model_count != 1:
        raise ReferenceMinimizationError("reference minimization requires exactly one model")
    if system.atom_count < 1 or tuple(system.coordinates.shape) != (1, system.atom_count, 3):
        raise ReferenceMinimizationError("system atom identity and coordinate shape mismatch")
    if not bool(torch.isfinite(system.coordinates).all().item()):
        raise ReferenceMinimizationError("reference minimization coordinates must be finite")


def _evaluate(
    source_system: AllAtomSystem,
    coordinates: torch.Tensor,
    parameters: ReferenceForceFieldParameters,
    config: ReferenceMinimizationConfig,
    *,
    operation: str,
) -> tuple[float, torch.Tensor, float]:
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
    evaluation = evaluate_reference_force_field(state, neighbors, parameters)
    energy = float(evaluation.term.energy[0].item())
    forces = evaluation.term.forces.detach().clone()
    max_force = float(torch.linalg.vector_norm(forces[0], dim=-1).max().item())
    if not math.isfinite(energy) or not bool(torch.isfinite(forces).all().item()):
        raise FloatingPointError("reference evaluation produced non-finite values")
    return energy, forces, max_force


def minimize_reference_force_field(
    system: AllAtomSystem,
    parameters: ReferenceForceFieldParameters,
    config: ReferenceMinimizationConfig | None = None,
    *,
    checkpoint: ReferenceMinimizationCheckpoint | Mapping[str, object] | None = None,
    pause_after_accepted_iterations: int | None = None,
) -> ReferenceMinimizationResult:
    """Run or resume bounded deterministic steepest descent with backtracking."""

    config = ReferenceMinimizationConfig() if config is None else config
    if not isinstance(config, ReferenceMinimizationConfig):
        raise ReferenceMinimizationError("config must be ReferenceMinimizationConfig")
    if not isinstance(parameters, ReferenceForceFieldParameters):
        raise ReferenceMinimizationError(
            "parameters must be ReferenceForceFieldParameters"
        )
    _validate_source_system(system)
    source_sha256 = canonical_system_sha256(system)
    topology_sha256 = canonical_topology_sha256(system)

    checkpoint_row: ReferenceMinimizationCheckpoint | None
    if checkpoint is None:
        checkpoint_row = None
    elif isinstance(checkpoint, ReferenceMinimizationCheckpoint):
        checkpoint_row = require_reference_minimization_checkpoint_document(
            checkpoint.to_dict()
        )
    else:
        checkpoint_row = require_reference_minimization_checkpoint_document(checkpoint)

    if checkpoint_row is None:
        coordinates = system.coordinates.detach().clone()
        accepted_iterations = 0
        evaluation_count = 0
        observations: list[ReferenceMinimizationObservation] = []
        try:
            current_energy, current_forces, current_max_force = _evaluate(
                system,
                coordinates,
                parameters,
                config,
                operation="reference_minimization_initial_evaluation",
            )
        except (ReferencePhysicsApplicabilityError, FloatingPointError) as exc:
            raise ReferenceMinimizationError(
                f"initial minimization state is not evaluable: {exc}"
            ) from exc
        evaluation_count = 1
        initial_energy = current_energy
        initial_max_force = current_max_force
        observations.append(
            ReferenceMinimizationObservation(
                iteration=0,
                trial=0,
                evaluation_index=1,
                outcome="initial",
                coordinates_sha256=_coordinate_digest(coordinates),
                step_size_angstrom2_mol_per_kcal=0.0,
                energy_kcal_per_mol=current_energy,
                max_force_kcal_per_mol_angstrom=current_max_force,
            )
        )
    else:
        if checkpoint_row.source_system_sha256 != source_sha256:
            raise ReferenceMinimizationError("checkpoint source system identity mismatch")
        if checkpoint_row.topology_sha256 != topology_sha256:
            raise ReferenceMinimizationError("checkpoint topology identity mismatch")
        if checkpoint_row.parameter_fingerprint_sha256 != parameters.fingerprint_sha256:
            raise ReferenceMinimizationError("checkpoint parameter fingerprint mismatch")
        if checkpoint_row.config_fingerprint_sha256 != config.fingerprint_sha256:
            raise ReferenceMinimizationError("checkpoint config fingerprint mismatch")
        if checkpoint_row.coordinate_shape != (1, system.atom_count, 3):
            raise ReferenceMinimizationError("checkpoint atom count mismatch")
        coordinates = checkpoint_row.coordinates()
        accepted_iterations = checkpoint_row.accepted_iterations
        evaluation_count = checkpoint_row.evaluation_count
        observations = list(checkpoint_row.observations)
        initial_energy = checkpoint_row.initial_energy_kcal_per_mol
        initial_max_force = checkpoint_row.initial_max_force_kcal_per_mol_angstrom
        try:
            current_energy, current_forces, current_max_force = _evaluate(
                system,
                coordinates,
                parameters,
                config,
                operation="reference_minimization_restart_verification",
            )
        except (ReferencePhysicsApplicabilityError, FloatingPointError) as exc:
            raise ReferenceMinimizationError(
                f"checkpoint state is not evaluable: {exc}"
            ) from exc
        if (
            struct.pack("<d", current_energy)
            != struct.pack("<d", checkpoint_row.current_energy_kcal_per_mol)
            or struct.pack("<d", current_max_force)
            != struct.pack(
                "<d", checkpoint_row.current_max_force_kcal_per_mol_angstrom
            )
        ):
            raise ReferenceMinimizationError(
                "checkpoint state does not reproduce stored energy and force"
            )

    pause_at: int | None = None
    if pause_after_accepted_iterations is not None:
        pause_at = _exact_int(
            pause_after_accepted_iterations,
            name="pause_after_accepted_iterations",
            minimum=0,
            maximum=config.max_iterations,
        )
        if pause_at < accepted_iterations:
            raise ReferenceMinimizationError(
                "pause_after_accepted_iterations precedes checkpoint progress"
            )

    status = "max_iterations_reached"
    failure_code: str | None = "maximum_iteration_budget_exhausted"
    while accepted_iterations < config.max_iterations:
        if current_max_force <= config.force_tolerance_kcal_per_mol_angstrom:
            status = "converged"
            failure_code = None
            break
        if pause_at is not None and accepted_iterations >= pause_at:
            status = "checkpointed"
            failure_code = None
            break

        iteration = accepted_iterations + 1
        step = config.initial_step_size_angstrom2_mol_per_kcal
        direction = current_forces.clone()
        raw_max_displacement = step * current_max_force
        if raw_max_displacement > config.maximum_atom_displacement_angstrom:
            direction.mul_(
                config.maximum_atom_displacement_angstrom / raw_max_displacement
            )
        directional_derivative = -float((current_forces * direction).sum().item())
        accepted = False

        for trial in range(config.max_backtracks + 1):
            trial_coordinates = coordinates + step * direction
            evaluation_count += 1
            coordinate_sha256 = _coordinate_digest(trial_coordinates)
            try:
                trial_energy, trial_forces, trial_max_force = _evaluate(
                    system,
                    trial_coordinates,
                    parameters,
                    config,
                    operation=f"reference_minimization_iteration_{iteration}_trial_{trial}",
                )
            except ReferencePhysicsApplicabilityError as exc:
                observations.append(
                    ReferenceMinimizationObservation(
                        iteration=iteration,
                        trial=trial,
                        evaluation_index=evaluation_count,
                        outcome="rejected_applicability",
                        coordinates_sha256=coordinate_sha256,
                        step_size_angstrom2_mol_per_kcal=step,
                        energy_kcal_per_mol=None,
                        max_force_kcal_per_mol_angstrom=None,
                        failure_code=(
                            "reference_physics_applicability_failed:"
                            + str(exc).split(":", 1)[0]
                        ),
                    )
                )
            except FloatingPointError:
                observations.append(
                    ReferenceMinimizationObservation(
                        iteration=iteration,
                        trial=trial,
                        evaluation_index=evaluation_count,
                        outcome="rejected_nonfinite",
                        coordinates_sha256=coordinate_sha256,
                        step_size_angstrom2_mol_per_kcal=step,
                        energy_kcal_per_mol=None,
                        max_force_kcal_per_mol_angstrom=None,
                        failure_code="nonfinite_energy_or_force",
                    )
                )
            else:
                armijo_limit = (
                    current_energy
                    + config.armijo_constant * step * directional_derivative
                )
                if trial_energy <= armijo_limit:
                    observations.append(
                        ReferenceMinimizationObservation(
                            iteration=iteration,
                            trial=trial,
                            evaluation_index=evaluation_count,
                            outcome="accepted",
                            coordinates_sha256=coordinate_sha256,
                            step_size_angstrom2_mol_per_kcal=step,
                            energy_kcal_per_mol=trial_energy,
                            max_force_kcal_per_mol_angstrom=trial_max_force,
                        )
                    )
                    coordinates = trial_coordinates
                    current_energy = trial_energy
                    current_forces = trial_forces
                    current_max_force = trial_max_force
                    accepted_iterations += 1
                    accepted = True
                    break
                observations.append(
                    ReferenceMinimizationObservation(
                        iteration=iteration,
                        trial=trial,
                        evaluation_index=evaluation_count,
                        outcome="rejected_armijo",
                        coordinates_sha256=coordinate_sha256,
                        step_size_angstrom2_mol_per_kcal=step,
                        energy_kcal_per_mol=trial_energy,
                        max_force_kcal_per_mol_angstrom=trial_max_force,
                        failure_code="armijo_decrease_not_satisfied",
                    )
                )
            step *= config.backtrack_factor

        if not accepted:
            status = "line_search_failed"
            failure_code = "bounded_backtracking_exhausted"
            break
    else:
        status = "max_iterations_reached"
        failure_code = "maximum_iteration_budget_exhausted"

    if current_max_force <= config.force_tolerance_kcal_per_mol_angstrom:
        status = "converged"
        failure_code = None

    observation_rows = tuple(observations)
    checkpoint_result = _build_checkpoint(
        source_system=system,
        parameters=parameters,
        config=config,
        coordinates=coordinates,
        accepted_iterations=accepted_iterations,
        evaluation_count=evaluation_count,
        initial_energy=initial_energy,
        initial_max_force=initial_max_force,
        current_energy=current_energy,
        current_max_force=current_max_force,
        observations=observation_rows,
    )
    result_system = system.with_coordinates(
        coordinates,
        operation="bounded_reference_force_field_minimization",
        operation_evidence_sha256=checkpoint_result.checkpoint_sha256,
    )
    return ReferenceMinimizationResult(
        status=status,
        failure_code=failure_code,
        initial_energy_kcal_per_mol=initial_energy,
        final_energy_kcal_per_mol=current_energy,
        initial_max_force_kcal_per_mol_angstrom=initial_max_force,
        final_max_force_kcal_per_mol_angstrom=current_max_force,
        accepted_iterations=accepted_iterations,
        rejected_evaluations=sum(
            row.outcome.startswith("rejected_") for row in observation_rows
        ),
        evaluation_count=evaluation_count,
        observations=observation_rows,
        checkpoint=checkpoint_result,
        system=result_system,
    )


__all__ = [
    "REFERENCE_MINIMIZATION_ALGORITHM_ID",
    "REFERENCE_MINIMIZATION_CHECKPOINT_SCHEMA_ID",
    "REFERENCE_MINIMIZATION_CONFIG_SCHEMA_ID",
    "REFERENCE_MINIMIZATION_MAX_BACKTRACKS",
    "REFERENCE_MINIMIZATION_MAX_ITERATIONS",
    "REFERENCE_MINIMIZATION_RESULT_SCHEMA_ID",
    "REFERENCE_MINIMIZATION_SCIENTIFIC_BLOCKERS",
    "ReferenceMinimizationCheckpoint",
    "ReferenceMinimizationConfig",
    "ReferenceMinimizationError",
    "ReferenceMinimizationObservation",
    "ReferenceMinimizationResult",
    "minimize_reference_force_field",
    "require_reference_minimization_checkpoint_document",
]
