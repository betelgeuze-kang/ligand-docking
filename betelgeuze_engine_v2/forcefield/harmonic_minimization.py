"""Deterministic, non-runtime exact-methane descent diagnostics.

This module deliberately implements only a bounded numerical contract over the
existing form-bound exact-methane harmonic diagnostic.  It is not a production
minimizer and never grants scientific, runtime, simulation, or claim authority.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field, replace
import hashlib
import json
import math
import struct
from typing import Any, Iterable

import torch

from betelgeuze_engine_v2.forcefield.harmonic_diagnostics import (
    ExactMethaneHarmonicDiagnosticError,
    _snapshot_inputs as _snapshot_harmonic_inputs,
    analyze_exact_methane_harmonic_diagnostic,
)
from betelgeuze_engine_v2.forcefield.harmonic_virial_diagnostics import (
    ExactMethaneHarmonicVirialDiagnosticError,
    analyze_exact_methane_harmonic_virial_diagnostic,
)
from betelgeuze_engine_v2.forcefield.parameters import (
    ExactMethaneBondAngleParameterSet,
    deserialize_exact_methane_bond_angle_parameter_set,
    serialize_exact_methane_bond_angle_parameter_set,
)
from betelgeuze_engine_v2.molecular.models import AllAtomSystem
from betelgeuze_engine_v2.molecular.observation import (
    attach_parser_observation_digest,
)
from betelgeuze_engine_v2.molecular.serialization import (
    deserialize_all_atom_system,
    serialize_all_atom_system,
)


_FROZEN_REPORT_SCHEMA_VERSION = "1.0.0"
_FROZEN_REPORT_SCHEMA_ID = (
    "betelgeuze.exact_methane_harmonic_minimization_diagnostic/1.0.0"
)
_FROZEN_CHECKPOINT_SCHEMA_VERSION = "1.0.0"
_FROZEN_CHECKPOINT_SCHEMA_ID = (
    "betelgeuze.exact_methane_harmonic_minimization_checkpoint/1.0.0"
)
_FROZEN_CONFIG_SCHEMA_VERSION = "1.0.0"
_FROZEN_CONFIG_SCHEMA_ID = "betelgeuze.exact_methane_harmonic_minimization_config/1.0.0"
_FROZEN_ALGORITHM_PROTOCOL_ID = (
    "exact_methane_cartesian_steepest_descent_strict_armijo/1.0.0"
)
_FROZEN_CLAIM_SCOPE = "nonphysical_exact_methane_bond_angle_descent_diagnostic_only"
_FROZEN_PARAMETER_SCHEMA_VERSION = "1.1.0"
_FROZEN_LEGACY_PARAMETER_SCHEMA_VERSION = "1.0.0"
_FROZEN_FUNCTIONAL_FORM_ID = "harmonic_half_k_delta_squared_bond_angle/1.0.0"
_FROZEN_DETERMINISM_SCOPE = (
    "same_python_torch_cpu_libm_runtime_and_frozen_protocol_only"
)
_FROZEN_NEGATIVE_ZERO_POLICY = (
    "reject_initial_coordinate_negative_zero_and_normalize_trial_exact_zero"
)
_FROZEN_START_PROVENANCE_OPERATION = (
    "exact_methane_harmonic_minimization_diagnostic_start/1.0.0"
)
_FROZEN_STEP_PROVENANCE_OPERATION = (
    "exact_methane_harmonic_minimization_diagnostic_coordinate_trial/1.0.0"
)
_TRACE_SEED_SHA256 = hashlib.sha256(
    b"betelgeuze.exact_methane_harmonic_minimization_trace/1.0.0"
).hexdigest()
_MAX_ACCEPTED_STEPS = 256
_MAX_LINE_SEARCH_TRIALS = 64
_MAX_FORCE_TOLERANCE = 1.0e-6
_MAX_CHECKPOINT_BYTES = 1_000_000
_MAX_EMBEDDED_ARTIFACT_BYTES = 250_000

EXACT_METHANE_HARMONIC_MINIMIZATION_DIAGNOSTIC_SCHEMA_VERSION = (
    _FROZEN_REPORT_SCHEMA_VERSION
)
EXACT_METHANE_HARMONIC_MINIMIZATION_DIAGNOSTIC_SCHEMA_ID = _FROZEN_REPORT_SCHEMA_ID
EXACT_METHANE_HARMONIC_MINIMIZATION_CHECKPOINT_SCHEMA_VERSION = (
    _FROZEN_CHECKPOINT_SCHEMA_VERSION
)
EXACT_METHANE_HARMONIC_MINIMIZATION_CHECKPOINT_SCHEMA_ID = _FROZEN_CHECKPOINT_SCHEMA_ID
EXACT_METHANE_HARMONIC_MINIMIZATION_ALGORITHM_PROTOCOL_ID = (
    _FROZEN_ALGORITHM_PROTOCOL_ID
)
EXACT_METHANE_HARMONIC_MINIMIZATION_CLAIM_SCOPE = _FROZEN_CLAIM_SCOPE


class ExactMethaneHarmonicMinimizationError(ValueError):
    """Fail-closed minimization diagnostic error with a stable code."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.blockers = (f"harmonic_minimization_{code}",)
        super().__init__(message)


def _fail(code: str, message: str) -> None:
    raise ExactMethaneHarmonicMinimizationError(code, message)


def _canonical_float(value: float, *, location: str) -> float:
    if type(value) is not float:
        _fail("invalid_numeric_type", f"{location} must be an exact float")
    if not math.isfinite(value):
        _fail("nonfinite_result", f"{location} must be finite")
    return 0.0 if value == 0.0 else value


def _finite_fsum(values: Iterable[float], *, location: str) -> float:
    try:
        value = math.fsum(values)
    except (OverflowError, ValueError) as exc:
        _fail("nonfinite_result", f"{location} must remain finite: {exc}")
    if not math.isfinite(value):
        _fail("nonfinite_result", f"{location} must remain finite")
    return 0.0 if value == 0.0 else value


def _binary64_hex(value: float, *, location: str) -> str:
    return struct.pack(">d", _canonical_float(value, location=location)).hex()


def _float_from_hex(value: Any, *, location: str) -> float:
    if (
        type(value) is not str
        or len(value) != 16
        or value != value.lower()
        or any(character not in "0123456789abcdef" for character in value)
    ):
        _fail("invalid_binary64", f"{location} must be lowercase binary64 hex")
    result = struct.unpack(">d", bytes.fromhex(value))[0]
    if not math.isfinite(result) or (result == 0.0 and value.startswith("8")):
        _fail("invalid_binary64", f"{location} must be finite canonical binary64")
    return 0.0 if result == 0.0 else result


def _canonical_json_bytes(document: Any) -> bytes:
    try:
        return json.dumps(
            document,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError, RecursionError) as exc:
        _fail("serialization_failed", f"canonical serialization failed: {exc}")


def _sha256_document(document: Any) -> str:
    return hashlib.sha256(_canonical_json_bytes(document)).hexdigest()


def _require_sha256(value: Any, *, location: str) -> str:
    if (
        type(value) is not str
        or len(value) != 64
        or value != value.lower()
        or any(character not in "0123456789abcdef" for character in value)
    ):
        _fail("invalid_sha256", f"{location} must be lowercase SHA-256")
    return value


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            _fail("duplicate_json_key", f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    _fail("nonstandard_json_constant", f"JSON constant {value!r} is prohibited")


def _parse_json_bytes(data: bytes, *, location: str, byte_cap: int) -> dict[str, Any]:
    if type(data) is not bytes:
        raise TypeError(f"{location} must be bytes")
    if len(data) > byte_cap:
        _fail("artifact_too_large", f"{location} exceeds the fixed byte cap")
    try:
        text = data.decode("ascii")
        document = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_json_constant,
        )
    except ExactMethaneHarmonicMinimizationError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        _fail("invalid_json", f"invalid {location} JSON: {exc}")
    if type(document) is not dict:
        _fail("invalid_json", f"{location} root must be an object")
    return document


def _require_exact_keys(
    document: dict[str, Any],
    expected: frozenset[str],
    *,
    location: str,
) -> None:
    if frozenset(document) != expected:
        _fail("schema_key_mismatch", f"{location} keys must match the fixed schema")


@dataclass(frozen=True, slots=True)
class ExactMethaneHarmonicMinimizationConfig:
    max_accepted_steps: int = 128
    max_line_search_trials: int = 33
    initial_step_size: float = 0.1
    backtracking_factor: float = 0.5
    armijo_coefficient: float = 1.0e-4
    force_tolerance: float = 1.0e-8

    def __post_init__(self) -> None:
        if (
            type(self.max_accepted_steps) is not int
            or not 0 <= self.max_accepted_steps <= _MAX_ACCEPTED_STEPS
        ):
            raise TypeError("max_accepted_steps must be an exact bounded integer")
        if (
            type(self.max_line_search_trials) is not int
            or not 1 <= self.max_line_search_trials <= _MAX_LINE_SEARCH_TRIALS
        ):
            raise TypeError("max_line_search_trials must be an exact bounded integer")
        for name in (
            "initial_step_size",
            "backtracking_factor",
            "armijo_coefficient",
            "force_tolerance",
        ):
            value = getattr(self, name)
            if type(value) is not float or not math.isfinite(value):
                raise TypeError(f"{name} must be an exact finite float")
        if self.initial_step_size <= 0.0:
            raise ValueError("initial_step_size must be positive")
        if not 0.0 < self.backtracking_factor < 1.0:
            raise ValueError("backtracking_factor must lie strictly between 0 and 1")
        if not 0.0 < self.armijo_coefficient < 0.5:
            raise ValueError("armijo_coefficient must lie strictly between 0 and 0.5")
        if not 0.0 < self.force_tolerance <= _MAX_FORCE_TOLERANCE:
            raise ValueError(
                "force_tolerance must be positive and no greater than 1e-6"
            )

    def _validated_copy(self) -> "ExactMethaneHarmonicMinimizationConfig":
        return ExactMethaneHarmonicMinimizationConfig(
            max_accepted_steps=self.max_accepted_steps,
            max_line_search_trials=self.max_line_search_trials,
            initial_step_size=self.initial_step_size,
            backtracking_factor=self.backtracking_factor,
            armijo_coefficient=self.armijo_coefficient,
            force_tolerance=self.force_tolerance,
        )

    def _core_dict(self) -> dict[str, Any]:
        return {
            "schema_id": _FROZEN_CONFIG_SCHEMA_ID,
            "schema_version": _FROZEN_CONFIG_SCHEMA_VERSION,
            "algorithm_protocol_id": _FROZEN_ALGORITHM_PROTOCOL_ID,
            "step_size_unit": "angstrom_squared_mole_per_kilojoule",
            "force_tolerance_unit": "kilojoule_per_mole_per_angstrom",
            "force_metric": "maximum_per_atom_l2_norm",
            "max_accepted_steps": self.max_accepted_steps,
            "max_line_search_trials": self.max_line_search_trials,
            "initial_step_size_ieee754_binary64_be": _binary64_hex(
                self.initial_step_size,
                location="config.initial_step_size",
            ),
            "backtracking_factor_ieee754_binary64_be": _binary64_hex(
                self.backtracking_factor,
                location="config.backtracking_factor",
            ),
            "armijo_coefficient_ieee754_binary64_be": _binary64_hex(
                self.armijo_coefficient,
                location="config.armijo_coefficient",
            ),
            "force_tolerance_ieee754_binary64_be": _binary64_hex(
                self.force_tolerance,
                location="config.force_tolerance",
            ),
        }

    def to_dict(self) -> dict[str, Any]:
        validated = ExactMethaneHarmonicMinimizationConfig._validated_copy(self)
        payload = ExactMethaneHarmonicMinimizationConfig._core_dict(validated)
        payload["config_sha256"] = _sha256_document(payload)
        return payload


_CONFIG_KEYS = frozenset(
    {
        "schema_id",
        "schema_version",
        "algorithm_protocol_id",
        "step_size_unit",
        "force_tolerance_unit",
        "force_metric",
        "max_accepted_steps",
        "max_line_search_trials",
        "initial_step_size_ieee754_binary64_be",
        "backtracking_factor_ieee754_binary64_be",
        "armijo_coefficient_ieee754_binary64_be",
        "force_tolerance_ieee754_binary64_be",
        "config_sha256",
    }
)


def _config_bytes(config: ExactMethaneHarmonicMinimizationConfig) -> bytes:
    if type(config) is not ExactMethaneHarmonicMinimizationConfig:
        raise TypeError("config must be an ExactMethaneHarmonicMinimizationConfig")
    return _canonical_json_bytes(ExactMethaneHarmonicMinimizationConfig.to_dict(config))


def _config_from_bytes(data: bytes) -> ExactMethaneHarmonicMinimizationConfig:
    document = _parse_json_bytes(data, location="config", byte_cap=16_384)
    _require_exact_keys(document, _CONFIG_KEYS, location="config")
    if _canonical_json_bytes(document) != data:
        _fail("noncanonical_config", "config bytes must be canonical")
    if (
        document["schema_id"] != _FROZEN_CONFIG_SCHEMA_ID
        or document["schema_version"] != _FROZEN_CONFIG_SCHEMA_VERSION
        or document["algorithm_protocol_id"] != _FROZEN_ALGORITHM_PROTOCOL_ID
    ):
        _fail("config_protocol_mismatch", "config protocol labels do not match")
    provided_sha = _require_sha256(
        document["config_sha256"],
        location="config.config_sha256",
    )
    core = {key: value for key, value in document.items() if key != "config_sha256"}
    if provided_sha != _sha256_document(core):
        _fail("config_hash_mismatch", "config hash does not match its content")
    try:
        config = ExactMethaneHarmonicMinimizationConfig(
            max_accepted_steps=document["max_accepted_steps"],
            max_line_search_trials=document["max_line_search_trials"],
            initial_step_size=_float_from_hex(
                document["initial_step_size_ieee754_binary64_be"],
                location="config.initial_step_size",
            ),
            backtracking_factor=_float_from_hex(
                document["backtracking_factor_ieee754_binary64_be"],
                location="config.backtracking_factor",
            ),
            armijo_coefficient=_float_from_hex(
                document["armijo_coefficient_ieee754_binary64_be"],
                location="config.armijo_coefficient",
            ),
            force_tolerance=_float_from_hex(
                document["force_tolerance_ieee754_binary64_be"],
                location="config.force_tolerance",
            ),
        )
    except ExactMethaneHarmonicMinimizationError:
        raise
    except (TypeError, ValueError, OverflowError) as exc:
        _fail("invalid_config", f"config values are invalid: {exc}")
    if ExactMethaneHarmonicMinimizationConfig.to_dict(config) != document:
        _fail("config_round_trip_mismatch", "config does not round trip exactly")
    return config


def _protocol_document() -> dict[str, Any]:
    return {
        "protocol_id": _FROZEN_ALGORITHM_PROTOCOL_ID,
        "parameter_schema_version": _FROZEN_PARAMETER_SCHEMA_VERSION,
        "functional_form_id": _FROZEN_FUNCTIONAL_FORM_ID,
        "device": "cpu",
        "dtype": "torch.float64",
        "cell_policy": "cell_free_only",
        "direction": "raw_exact_analytic_force",
        "trial_update": "x_trial=x_current+alpha*force_current",
        "step_reset_policy": "reset_to_config_initial_step_each_accepted_step",
        "acceptance": "strict_energy_decrease_and_armijo",
        "armijo_rhs": (
            "E_trial<=E_current-c1*alpha*sum_over_atoms_and_axes(F_component^2)"
        ),
        "armijo_descent_norm": (
            "sum_over_atoms_and_cartesian_axes_of_force_component_squared"
        ),
        "armijo_descent_norm_unit": (
            "kilojoule_squared_per_mole_squared_per_angstrom_squared"
        ),
        "trial_failure_policy": "reject_and_backtrack_without_fallback",
        "negative_zero_policy": _FROZEN_NEGATIVE_ZERO_POLICY,
        "derived_provenance_policy": (
            "start_bounded_diagnostic_lineage_and_append_parent_snapshot_with_authority_false"
        ),
        "start_provenance_operation": _FROZEN_START_PROVENANCE_OPERATION,
        "step_provenance_operation": _FROZEN_STEP_PROVENANCE_OPERATION,
        "determinism_scope": _FROZEN_DETERMINISM_SCOPE,
        "rigid_mode_projection": "not_applied",
        "termination_force_metric": "maximum_per_atom_l2_norm",
        "force_tolerance_upper_bound_ieee754_binary64_be": _binary64_hex(
            _MAX_FORCE_TOLERANCE,
            location="protocol.force_tolerance_upper_bound",
        ),
        "max_accepted_steps_hard_cap": _MAX_ACCEPTED_STEPS,
        "max_line_search_trials_hard_cap": _MAX_LINE_SEARCH_TRIALS,
        "trace_seed_sha256": _TRACE_SEED_SHA256,
    }


_FROZEN_PROTOCOL_BYTES = _canonical_json_bytes(_protocol_document())
_FROZEN_PROTOCOL_SHA256 = hashlib.sha256(_FROZEN_PROTOCOL_BYTES).hexdigest()


def _require_form_bound_parameter_set(
    parameter_set: ExactMethaneBondAngleParameterSet,
) -> None:
    if type(parameter_set) is not ExactMethaneBondAngleParameterSet:
        raise TypeError("parameter_set must be an ExactMethaneBondAngleParameterSet")
    schema_version = parameter_set.artifact_schema_version
    form_id = parameter_set.functional_form_id
    if type(schema_version) is not str:
        _fail("unsupported_parameter_schema", "parameter schema must be a string")
    if schema_version == _FROZEN_LEGACY_PARAMETER_SCHEMA_VERSION:
        _fail(
            "legacy_parameter_schema_not_supported",
            "minimization diagnostics require form-bound parameter schema 1.1",
        )
    if schema_version != _FROZEN_PARAMETER_SCHEMA_VERSION:
        _fail("unsupported_parameter_schema", "parameter schema 1.1 is required")
    if type(form_id) is not str or form_id != _FROZEN_FUNCTIONAL_FORM_ID:
        _fail("functional_form_mismatch", "the fixed harmonic form is required")


def _has_negative_zero(coordinates: torch.Tensor) -> bool:
    return bool(((coordinates == 0.0) & torch.signbit(coordinates)).any().item())


def _derived_diagnostic_system(
    system: AllAtomSystem,
    coordinates: torch.Tensor,
    *,
    parent_system_bytes: bytes,
    operation: str,
) -> AllAtomSystem:
    if type(system) is not AllAtomSystem:
        raise TypeError("system must be an AllAtomSystem")
    if type(coordinates) is not torch.Tensor:
        raise TypeError("coordinates must be a torch.Tensor")
    if type(parent_system_bytes) is not bytes:
        raise TypeError("parent_system_bytes must be bytes")
    if type(operation) is not str:
        raise TypeError("operation must be a string")
    parent_sha256 = hashlib.sha256(parent_system_bytes).hexdigest()
    if operation == _FROZEN_START_PROVENANCE_OPERATION:
        operations = (_FROZEN_START_PROVENANCE_OPERATION,)
        parent_sha256_chain = (parent_sha256,)
    elif operation == _FROZEN_STEP_PROVENANCE_OPERATION:
        operations = (*system.provenance.operations, operation)
        parent_sha256_chain = (*system.provenance.parent_sha256, parent_sha256)
    else:
        _fail("derived_provenance_mismatch", "unsupported diagnostic operation")
    provenance = replace(
        system.provenance,
        operations=operations,
        parent_sha256=parent_sha256_chain,
        preparation_ready=False,
        claim_safe=False,
    )
    derived = replace(
        system,
        coordinates=coordinates,
        provenance=provenance,
    )
    return attach_parser_observation_digest(derived)


def _snapshot_inputs(
    system: AllAtomSystem,
    parameter_set: ExactMethaneBondAngleParameterSet,
) -> tuple[bytes, bytes]:
    if type(system) is not AllAtomSystem:
        raise TypeError("system must be an AllAtomSystem")
    _require_form_bound_parameter_set(parameter_set)
    if _has_negative_zero(system.coordinates):
        _fail(
            "negative_zero_coordinate_not_supported",
            "initial coordinates cannot contain IEEE-754 negative zero",
        )
    try:
        source_system_bytes, parameter_bytes = _snapshot_harmonic_inputs(
            system,
            parameter_set,
        )
        diagnostic_system = _derived_diagnostic_system(
            system,
            system.coordinates,
            parent_system_bytes=source_system_bytes,
            operation=_FROZEN_START_PROVENANCE_OPERATION,
        )
        system_bytes = serialize_all_atom_system(diagnostic_system)
        analyze_exact_methane_harmonic_virial_diagnostic(
            diagnostic_system,
            parameter_set,
        )
    except ExactMethaneHarmonicMinimizationError:
        raise
    except (
        ExactMethaneHarmonicDiagnosticError,
        ExactMethaneHarmonicVirialDiagnosticError,
    ) as exc:
        _fail(exc.code, f"input diagnostic failed: {exc}")
    except (TypeError, ValueError, OverflowError, RuntimeError, RecursionError) as exc:
        _fail("snapshot_failed", f"input snapshot failed: {exc}")
    return system_bytes, parameter_bytes


@dataclass(frozen=True, slots=True)
class _EvaluatedState:
    system: AllAtomSystem
    system_bytes: bytes
    energy: float
    forces: torch.Tensor = field(repr=False, compare=False)
    max_atom_force_norm: float
    force_norm_squared: float
    harmonic_report_sha256: str
    virial_report_sha256: str
    assignment_sha256: str


def _evaluate_state(system_bytes: bytes, parameter_bytes: bytes) -> _EvaluatedState:
    if type(system_bytes) is not bytes or type(parameter_bytes) is not bytes:
        _fail("snapshot_recomputation_failed", "state snapshots must be bytes")
    try:
        system = deserialize_all_atom_system(system_bytes)
        parameter_set = deserialize_exact_methane_bond_angle_parameter_set(
            parameter_bytes
        )
        if serialize_all_atom_system(system) != system_bytes:
            _fail("snapshot_recomputation_failed", "system bytes are not canonical")
        if (
            serialize_exact_methane_bond_angle_parameter_set(parameter_set)
            != parameter_bytes
        ):
            _fail("snapshot_recomputation_failed", "parameter bytes are not canonical")
        _require_form_bound_parameter_set(parameter_set)
        harmonic = analyze_exact_methane_harmonic_diagnostic(system, parameter_set)
        virial = analyze_exact_methane_harmonic_virial_diagnostic(
            system,
            parameter_set,
        )
        forces = harmonic.forces_tensor()
    except ExactMethaneHarmonicMinimizationError:
        raise
    except (
        ExactMethaneHarmonicDiagnosticError,
        ExactMethaneHarmonicVirialDiagnosticError,
    ) as exc:
        _fail(exc.code, f"state diagnostic failed: {exc}")
    except (TypeError, ValueError, OverflowError, RuntimeError, RecursionError) as exc:
        _fail("snapshot_recomputation_failed", f"state recomputation failed: {exc}")
    atom_norms = torch.linalg.vector_norm(forces[0], dim=-1)
    max_force = float(torch.max(atom_norms).item())
    force_norm_squared = _finite_fsum(
        (
            float(component) * float(component)
            for atom in forces[0].tolist()
            for component in atom
        ),
        location="force_norm_squared",
    )
    assignment_sha = harmonic.assignment_report.parameter_assignment_sha256
    if type(assignment_sha) is not str:
        _fail("assignment_digest_missing", "assignment digest is required")
    return _EvaluatedState(
        system=system,
        system_bytes=system_bytes,
        energy=_canonical_float(
            float(harmonic.total_energy_kj_mol),
            location="state.energy",
        ),
        forces=forces.detach().clone(),
        max_atom_force_norm=_canonical_float(
            max_force,
            location="state.max_atom_force_norm",
        ),
        force_norm_squared=force_norm_squared,
        harmonic_report_sha256=harmonic.report_sha256,
        virial_report_sha256=virial.report_sha256,
        assignment_sha256=assignment_sha,
    )


@dataclass(frozen=True, slots=True)
class HarmonicMinimizationAcceptedStep:
    accepted_step_index: int
    line_search_trial_count: int
    total_trial_count: int
    total_rejected_trial_count: int
    accepted_step_size: float
    energy_before: float
    energy_after: float
    armijo_rhs: float
    force_norm_squared_before: float
    max_atom_force_norm_before: float
    max_atom_force_norm_after: float
    system_snapshot_sha256_after: str
    harmonic_report_sha256_after: str
    virial_report_sha256_after: str
    transcript_sha256: str

    def __post_init__(self) -> None:
        for name in (
            "accepted_step_index",
            "line_search_trial_count",
            "total_trial_count",
            "total_rejected_trial_count",
        ):
            if type(getattr(self, name)) is not int:
                _fail("invalid_step_record", f"step.{name} must be an exact integer")
        if self.accepted_step_index < 1:
            _fail("invalid_step_record", "accepted_step_index must be positive")
        if not 1 <= self.line_search_trial_count <= _MAX_LINE_SEARCH_TRIALS:
            _fail("invalid_step_record", "line_search_trial_count is out of range")
        if self.total_trial_count < self.accepted_step_index:
            _fail("invalid_step_record", "total_trial_count is inconsistent")
        if self.total_rejected_trial_count != (
            self.total_trial_count - self.accepted_step_index
        ):
            _fail("invalid_step_record", "trial counters are inconsistent")
        for name in (
            "accepted_step_size",
            "energy_before",
            "energy_after",
            "armijo_rhs",
            "force_norm_squared_before",
            "max_atom_force_norm_before",
            "max_atom_force_norm_after",
        ):
            _canonical_float(getattr(self, name), location=f"step.{name}")
        if self.accepted_step_size <= 0.0:
            _fail("invalid_step_record", "accepted_step_size must be positive")
        if self.force_norm_squared_before < 0.0:
            _fail("invalid_step_record", "force_norm_squared_before cannot be negative")
        if (
            self.max_atom_force_norm_before < 0.0
            or self.max_atom_force_norm_after < 0.0
        ):
            _fail("invalid_step_record", "force norms cannot be negative")
        if not self.energy_after < self.energy_before:
            _fail("invalid_step_record", "accepted energy must decrease strictly")
        if not self.energy_after <= self.armijo_rhs:
            _fail("invalid_step_record", "accepted energy must satisfy Armijo")
        for name in (
            "system_snapshot_sha256_after",
            "harmonic_report_sha256_after",
            "virial_report_sha256_after",
            "transcript_sha256",
        ):
            _require_sha256(getattr(self, name), location=f"step.{name}")

    def _validated_copy(self) -> "HarmonicMinimizationAcceptedStep":
        if type(self) is not HarmonicMinimizationAcceptedStep:
            raise TypeError("step must be a HarmonicMinimizationAcceptedStep")
        return HarmonicMinimizationAcceptedStep(
            accepted_step_index=self.accepted_step_index,
            line_search_trial_count=self.line_search_trial_count,
            total_trial_count=self.total_trial_count,
            total_rejected_trial_count=self.total_rejected_trial_count,
            accepted_step_size=self.accepted_step_size,
            energy_before=self.energy_before,
            energy_after=self.energy_after,
            armijo_rhs=self.armijo_rhs,
            force_norm_squared_before=self.force_norm_squared_before,
            max_atom_force_norm_before=self.max_atom_force_norm_before,
            max_atom_force_norm_after=self.max_atom_force_norm_after,
            system_snapshot_sha256_after=self.system_snapshot_sha256_after,
            harmonic_report_sha256_after=self.harmonic_report_sha256_after,
            virial_report_sha256_after=self.virial_report_sha256_after,
            transcript_sha256=self.transcript_sha256,
        )

    def _core_dict(self) -> dict[str, Any]:
        return {
            "accepted_step_index": self.accepted_step_index,
            "line_search_trial_count": self.line_search_trial_count,
            "total_trial_count": self.total_trial_count,
            "total_rejected_trial_count": self.total_rejected_trial_count,
            "accepted_step_size_ieee754_binary64_be": _binary64_hex(
                self.accepted_step_size,
                location="step.accepted_step_size",
            ),
            "energy_before_ieee754_binary64_be": _binary64_hex(
                self.energy_before,
                location="step.energy_before",
            ),
            "energy_after_ieee754_binary64_be": _binary64_hex(
                self.energy_after,
                location="step.energy_after",
            ),
            "armijo_rhs_ieee754_binary64_be": _binary64_hex(
                self.armijo_rhs,
                location="step.armijo_rhs",
            ),
            "force_norm_squared_before_ieee754_binary64_be": _binary64_hex(
                self.force_norm_squared_before,
                location="step.force_norm_squared_before",
            ),
            "max_atom_force_norm_before_ieee754_binary64_be": _binary64_hex(
                self.max_atom_force_norm_before,
                location="step.max_atom_force_norm_before",
            ),
            "max_atom_force_norm_after_ieee754_binary64_be": _binary64_hex(
                self.max_atom_force_norm_after,
                location="step.max_atom_force_norm_after",
            ),
            "system_snapshot_sha256_after": self.system_snapshot_sha256_after,
            "harmonic_report_sha256_after": self.harmonic_report_sha256_after,
            "virial_report_sha256_after": self.virial_report_sha256_after,
            "strict_energy_decrease": True,
            "armijo_satisfied": True,
        }

    def to_dict(self) -> dict[str, Any]:
        validated = HarmonicMinimizationAcceptedStep._validated_copy(self)
        payload = HarmonicMinimizationAcceptedStep._core_dict(validated)
        payload["transcript_sha256"] = validated.transcript_sha256
        return payload


@dataclass(frozen=True, slots=True)
class _RunResult:
    states: tuple[_EvaluatedState, ...]
    steps: tuple[HarmonicMinimizationAcceptedStep, ...]
    total_trial_count: int
    rejected_trial_count: int
    termination_code: str
    termination_status: str
    last_trial_rejection_code: str | None
    transcript_sha256: str


@dataclass(frozen=True, slots=True)
class _CheckpointReplay:
    document: dict[str, Any] = field(repr=False, compare=False)
    initial_system_bytes: bytes = field(repr=False)
    parameter_bytes: bytes = field(repr=False)
    config: ExactMethaneHarmonicMinimizationConfig
    prefix: _RunResult = field(repr=False)


def _validate_run_provenance(result: _RunResult) -> None:
    if type(result) is not _RunResult or not result.states:
        _fail("derived_provenance_mismatch", "run must contain a derived state")
    for state_index, state in enumerate(result.states):
        provenance = state.system.provenance
        if provenance.preparation_ready or provenance.claim_safe:
            _fail(
                "derived_provenance_mismatch",
                "diagnostic state provenance must remain non-promoted",
            )
        expected_operations = (
            _FROZEN_START_PROVENANCE_OPERATION,
            *(_FROZEN_STEP_PROVENANCE_OPERATION for _ in range(state_index)),
        )
        if (
            provenance.operations != expected_operations
            or len(provenance.parent_sha256) != state_index + 1
        ):
            _fail(
                "derived_provenance_mismatch",
                "diagnostic state provenance operation is not bound",
            )
        if state_index == 0:
            _require_sha256(
                provenance.parent_sha256[-1],
                location="run.source_input_system_snapshot_sha256",
            )
        elif (
            provenance.parent_sha256[-1]
            != hashlib.sha256(result.states[state_index - 1].system_bytes).hexdigest()
        ):
            _fail(
                "derived_provenance_mismatch",
                "diagnostic state parent snapshot does not match",
            )


def _trial_state(
    current: _EvaluatedState,
    parameter_bytes: bytes,
    alpha: float,
) -> _EvaluatedState | None:
    trial_coordinates = current.system.coordinates + alpha * current.forces
    if not bool(torch.isfinite(trial_coordinates).all().item()):
        return None
    trial_coordinates = torch.where(
        trial_coordinates == 0.0,
        torch.zeros_like(trial_coordinates),
        trial_coordinates,
    )
    if torch.equal(trial_coordinates, current.system.coordinates):
        _fail(
            "no_representable_coordinate_change",
            "the next binary64 coordinate update is not representable",
        )
    try:
        trial_system = _derived_diagnostic_system(
            current.system,
            trial_coordinates,
            parent_system_bytes=current.system_bytes,
            operation=_FROZEN_STEP_PROVENANCE_OPERATION,
        )
        trial_bytes = serialize_all_atom_system(trial_system)
        return _evaluate_state(trial_bytes, parameter_bytes)
    except ExactMethaneHarmonicMinimizationError:
        return None
    except (TypeError, ValueError, OverflowError, RuntimeError, RecursionError):
        return None


def _run_descent(
    initial_system_bytes: bytes,
    parameter_bytes: bytes,
    config: ExactMethaneHarmonicMinimizationConfig,
    *,
    prefix: _RunResult | None = None,
    stop_after_accepted_steps: int | None = None,
) -> _RunResult:
    config = ExactMethaneHarmonicMinimizationConfig._validated_copy(config)
    if stop_after_accepted_steps is not None and (
        type(stop_after_accepted_steps) is not int
        or not 0 <= stop_after_accepted_steps <= config.max_accepted_steps
    ):
        _fail(
            "invalid_checkpoint_boundary",
            "stop_after_accepted_steps must be an exact configured boundary",
        )
    if prefix is None:
        initial = _evaluate_state(initial_system_bytes, parameter_bytes)
        states = [initial]
        steps: list[HarmonicMinimizationAcceptedStep] = []
        total_trials = 0
        total_rejected = 0
        trace_sha = _TRACE_SEED_SHA256
        last_rejection: str | None = None
    else:
        if type(prefix) is not _RunResult:
            _fail("invalid_resume_prefix", "resume prefix must be a run result")
        if (
            not prefix.states
            or prefix.states[0].system_bytes != initial_system_bytes
            or len(prefix.states) != len(prefix.steps) + 1
            or prefix.total_trial_count - prefix.rejected_trial_count
            != len(prefix.steps)
            or (
                prefix.steps
                and prefix.steps[-1].transcript_sha256 != prefix.transcript_sha256
            )
            or (not prefix.steps and prefix.transcript_sha256 != _TRACE_SEED_SHA256)
        ):
            _fail("invalid_resume_prefix", "resume prefix is internally inconsistent")
        if stop_after_accepted_steps is not None and stop_after_accepted_steps < len(
            prefix.steps
        ):
            _fail("invalid_checkpoint_boundary", "stop boundary precedes the prefix")
        states = list(prefix.states)
        steps = list(prefix.steps)
        total_trials = prefix.total_trial_count
        total_rejected = prefix.rejected_trial_count
        trace_sha = prefix.transcript_sha256
        last_rejection = prefix.last_trial_rejection_code

    current = states[-1]
    if current.max_atom_force_norm <= config.force_tolerance:
        return _RunResult(
            states=tuple(states),
            steps=tuple(steps),
            total_trial_count=total_trials,
            rejected_trial_count=total_rejected,
            termination_code="stationarity_tolerance_met",
            termination_status="stationarity_observed",
            last_trial_rejection_code=last_rejection,
            transcript_sha256=trace_sha,
        )
    if len(steps) >= config.max_accepted_steps:
        return _RunResult(
            tuple(states),
            tuple(steps),
            total_trials,
            total_rejected,
            "accepted_step_limit_reached",
            "nonconverged",
            last_rejection,
            trace_sha,
        )
    if (
        stop_after_accepted_steps is not None
        and len(steps) >= stop_after_accepted_steps
    ):
        return _RunResult(
            tuple(states),
            tuple(steps),
            total_trials,
            total_rejected,
            "checkpoint_boundary_reached",
            "paused",
            last_rejection,
            trace_sha,
        )

    while True:
        current = states[-1]
        if not math.isfinite(current.force_norm_squared):
            return _RunResult(
                tuple(states),
                tuple(steps),
                total_trials,
                total_rejected,
                "line_search_exhausted",
                "failed",
                "descent_norm_nonfinite",
                trace_sha,
            )
        alpha = config.initial_step_size
        accepted: _EvaluatedState | None = None
        accepted_trial_count = 0
        accepted_rhs = 0.0
        valid_candidate_count = 0
        strict_decrease_count = 0
        for trial_index in range(1, config.max_line_search_trials + 1):
            total_trials += 1
            try:
                candidate = _trial_state(current, parameter_bytes, alpha)
            except ExactMethaneHarmonicMinimizationError as exc:
                if exc.code == "no_representable_coordinate_change":
                    total_rejected += 1
                    code = (
                        "no_representable_energy_decrease_on_configured_backtracking_path"
                        if valid_candidate_count > 0 and strict_decrease_count == 0
                        else exc.code
                    )
                    return _RunResult(
                        tuple(states),
                        tuple(steps),
                        total_trials,
                        total_rejected,
                        code,
                        "stagnated",
                        code,
                        trace_sha,
                    )
                candidate = None
            if candidate is None:
                total_rejected += 1
                last_rejection = "candidate_evaluation_failed"
                alpha = _canonical_float(
                    alpha * config.backtracking_factor,
                    location="line_search.alpha",
                )
                continue
            valid_candidate_count += 1
            strict_decrease = candidate.energy < current.energy
            if strict_decrease:
                strict_decrease_count += 1
            try:
                armijo_rhs = _canonical_float(
                    current.energy
                    - config.armijo_coefficient * alpha * current.force_norm_squared,
                    location="line_search.armijo_rhs",
                )
            except ExactMethaneHarmonicMinimizationError:
                total_rejected += 1
                last_rejection = "armijo_rhs_nonfinite"
                alpha = _canonical_float(
                    alpha * config.backtracking_factor,
                    location="line_search.alpha",
                )
                continue
            if strict_decrease and candidate.energy <= armijo_rhs:
                accepted = candidate
                accepted_trial_count = trial_index
                accepted_rhs = armijo_rhs
                break
            total_rejected += 1
            last_rejection = (
                "armijo_not_satisfied"
                if strict_decrease
                else "strict_energy_decrease_not_observed"
            )
            alpha = _canonical_float(
                alpha * config.backtracking_factor,
                location="line_search.alpha",
            )
        if accepted is None:
            if valid_candidate_count == 0:
                code = "line_search_exhausted"
                last_rejection = "candidate_evaluation_exhausted"
            elif strict_decrease_count == 0:
                code = "line_search_exhausted"
                last_rejection = (
                    "strict_energy_decrease_not_observed_within_trial_limit"
                )
            else:
                code = "line_search_exhausted"
                last_rejection = "armijo_backtracking_exhausted"
            return _RunResult(
                tuple(states),
                tuple(steps),
                total_trials,
                total_rejected,
                code,
                "failed",
                last_rejection,
                trace_sha,
            )
        row_without_trace = HarmonicMinimizationAcceptedStep(
            accepted_step_index=len(steps) + 1,
            line_search_trial_count=accepted_trial_count,
            total_trial_count=total_trials,
            total_rejected_trial_count=total_rejected,
            accepted_step_size=alpha,
            energy_before=current.energy,
            energy_after=accepted.energy,
            armijo_rhs=accepted_rhs,
            force_norm_squared_before=current.force_norm_squared,
            max_atom_force_norm_before=current.max_atom_force_norm,
            max_atom_force_norm_after=accepted.max_atom_force_norm,
            system_snapshot_sha256_after=hashlib.sha256(
                accepted.system_bytes
            ).hexdigest(),
            harmonic_report_sha256_after=accepted.harmonic_report_sha256,
            virial_report_sha256_after=accepted.virial_report_sha256,
            transcript_sha256="0" * 64,
        )
        trace_sha = hashlib.sha256(
            bytes.fromhex(trace_sha)
            + _canonical_json_bytes(
                HarmonicMinimizationAcceptedStep._core_dict(row_without_trace)
            )
        ).hexdigest()
        row = replace(
            row_without_trace,
            transcript_sha256=trace_sha,
        )
        steps.append(row)
        states.append(accepted)
        if accepted.max_atom_force_norm <= config.force_tolerance:
            return _RunResult(
                tuple(states),
                tuple(steps),
                total_trials,
                total_rejected,
                "stationarity_tolerance_met",
                "stationarity_observed",
                last_rejection,
                trace_sha,
            )
        if len(steps) >= config.max_accepted_steps:
            return _RunResult(
                tuple(states),
                tuple(steps),
                total_trials,
                total_rejected,
                "accepted_step_limit_reached",
                "nonconverged",
                last_rejection,
                trace_sha,
            )
        if (
            stop_after_accepted_steps is not None
            and len(steps) >= stop_after_accepted_steps
        ):
            return _RunResult(
                tuple(states),
                tuple(steps),
                total_trials,
                total_rejected,
                "checkpoint_boundary_reached",
                "paused",
                last_rejection,
                trace_sha,
            )


def _report_blockers(result: _RunResult) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            (
                "diagnostic_descent_not_runtime_minimization",
                "first_order_stationarity_not_minimum",
                "global_optimum_not_assessed",
                "bonded_only_nonbonded_terms_missing",
                "parameter_artifact_not_scientifically_validated",
                "same_runtime_replay_digest_is_binding_not_authentication",
                "cross_platform_bitwise_replay_not_claimed",
                "rigid_pose_gauge_not_canonicalized",
                "runtime_energy_evaluation_not_authorized",
                "runtime_force_evaluation_not_authorized",
                "runtime_virial_evaluation_not_authorized",
                "runtime_minimization_not_authorized",
                "simulation_not_authorized",
                "claim_not_authorized",
                *(
                    (f"diagnostic_termination_{result.termination_code}",)
                    if result.termination_code != "stationarity_tolerance_met"
                    else ()
                ),
            )
        )
    )


@dataclass(frozen=True, init=False, slots=True)
class ExactMethaneHarmonicMinimizationReport:
    """Factory-only self-recomputing descent diagnostic report."""

    _initial_system_bytes: bytes = field(repr=False)
    _parameter_bytes: bytes = field(repr=False)
    _config_bytes: bytes = field(repr=False)
    _resume_checkpoint_bytes: bytes | None = field(repr=False, compare=False)

    def __init__(
        self,
        system: AllAtomSystem,
        parameter_set: ExactMethaneBondAngleParameterSet,
        *,
        config: ExactMethaneHarmonicMinimizationConfig | None = None,
    ) -> None:
        selected_config = (
            ExactMethaneHarmonicMinimizationConfig() if config is None else config
        )
        if type(selected_config) is not ExactMethaneHarmonicMinimizationConfig:
            raise TypeError("config must be an ExactMethaneHarmonicMinimizationConfig")
        system_bytes, parameter_bytes = _snapshot_inputs(system, parameter_set)
        config_bytes = _config_bytes(selected_config)
        initial_result = _run_descent(
            system_bytes,
            parameter_bytes,
            _config_from_bytes(config_bytes),
        )
        _validate_run_provenance(initial_result)
        object.__setattr__(self, "_initial_system_bytes", system_bytes)
        object.__setattr__(self, "_parameter_bytes", parameter_bytes)
        object.__setattr__(self, "_config_bytes", config_bytes)
        object.__setattr__(self, "_resume_checkpoint_bytes", None)

    @classmethod
    def _from_validated_snapshots(
        cls,
        initial_system_bytes: bytes,
        parameter_bytes: bytes,
        config_bytes: bytes,
        *,
        resume_checkpoint_bytes: bytes | None = None,
    ) -> "ExactMethaneHarmonicMinimizationReport":
        instance = object.__new__(cls)
        object.__setattr__(instance, "_initial_system_bytes", initial_system_bytes)
        object.__setattr__(instance, "_parameter_bytes", parameter_bytes)
        object.__setattr__(instance, "_config_bytes", config_bytes)
        object.__setattr__(
            instance,
            "_resume_checkpoint_bytes",
            resume_checkpoint_bytes,
        )
        return instance

    def _derive(
        self,
    ) -> tuple[ExactMethaneHarmonicMinimizationConfig, _RunResult]:
        if (
            type(self._initial_system_bytes) is not bytes
            or type(self._parameter_bytes) is not bytes
            or type(self._config_bytes) is not bytes
            or (
                self._resume_checkpoint_bytes is not None
                and type(self._resume_checkpoint_bytes) is not bytes
            )
        ):
            _fail("snapshot_recomputation_failed", "report snapshots must be bytes")
        config = _config_from_bytes(self._config_bytes)
        if self._resume_checkpoint_bytes is None:
            result = _run_descent(
                self._initial_system_bytes,
                self._parameter_bytes,
                config,
            )
        else:
            replay = _validate_checkpoint_bytes(self._resume_checkpoint_bytes)
            if (
                replay.initial_system_bytes != self._initial_system_bytes
                or replay.parameter_bytes != self._parameter_bytes
                or _config_bytes(replay.config) != self._config_bytes
            ):
                _fail(
                    "checkpoint_report_binding_mismatch",
                    "resume checkpoint does not match report snapshots",
                )
            result = _run_descent(
                self._initial_system_bytes,
                self._parameter_bytes,
                config,
                prefix=replay.prefix,
            )
        _validate_run_provenance(result)
        return config, result

    @property
    def config(self) -> ExactMethaneHarmonicMinimizationConfig:
        return ExactMethaneHarmonicMinimizationReport._derive(self)[0]

    @property
    def accepted_steps(self) -> tuple[HarmonicMinimizationAcceptedStep, ...]:
        return ExactMethaneHarmonicMinimizationReport._derive(self)[1].steps

    @property
    def termination_code(self) -> str:
        return ExactMethaneHarmonicMinimizationReport._derive(self)[1].termination_code

    @property
    def scoped_first_order_stationarity_observed(self) -> bool:
        return (
            ExactMethaneHarmonicMinimizationReport._derive(self)[1].termination_code
            == "stationarity_tolerance_met"
        )

    @property
    def final_system(self) -> AllAtomSystem:
        result = ExactMethaneHarmonicMinimizationReport._derive(self)[1]
        return deserialize_all_atom_system(result.states[-1].system_bytes)

    @property
    def initial_energy_kj_mol(self) -> float:
        return ExactMethaneHarmonicMinimizationReport._derive(self)[1].states[0].energy

    @property
    def final_energy_kj_mol(self) -> float:
        return ExactMethaneHarmonicMinimizationReport._derive(self)[1].states[-1].energy

    @property
    def diagnostic_minimization_performed(self) -> bool:
        return bool(ExactMethaneHarmonicMinimizationReport._derive(self)[1].steps)

    @property
    def scientific_validity_green(self) -> bool:
        ExactMethaneHarmonicMinimizationReport._derive(self)
        return False

    @property
    def physics_supported(self) -> bool:
        ExactMethaneHarmonicMinimizationReport._derive(self)
        return False

    @property
    def parameterability_assessed(self) -> bool:
        ExactMethaneHarmonicMinimizationReport._derive(self)
        return False

    @property
    def parameterizable(self) -> bool:
        ExactMethaneHarmonicMinimizationReport._derive(self)
        return False

    @property
    def global_parameter_coverage_complete(self) -> bool:
        ExactMethaneHarmonicMinimizationReport._derive(self)
        return False

    @property
    def preparation_ready(self) -> bool:
        ExactMethaneHarmonicMinimizationReport._derive(self)
        return False

    @property
    def runtime_eligible(self) -> bool:
        ExactMethaneHarmonicMinimizationReport._derive(self)
        return False

    @property
    def execution_authorized(self) -> bool:
        ExactMethaneHarmonicMinimizationReport._derive(self)
        return False

    @property
    def energy_evaluation_authorized(self) -> bool:
        ExactMethaneHarmonicMinimizationReport._derive(self)
        return False

    @property
    def force_evaluation_authorized(self) -> bool:
        ExactMethaneHarmonicMinimizationReport._derive(self)
        return False

    @property
    def virial_evaluation_authorized(self) -> bool:
        ExactMethaneHarmonicMinimizationReport._derive(self)
        return False

    @property
    def minimization_authorized(self) -> bool:
        ExactMethaneHarmonicMinimizationReport._derive(self)
        return False

    @property
    def simulation_ready(self) -> bool:
        ExactMethaneHarmonicMinimizationReport._derive(self)
        return False

    @property
    def claim_safe(self) -> bool:
        ExactMethaneHarmonicMinimizationReport._derive(self)
        return False

    @property
    def blockers(self) -> tuple[str, ...]:
        return _report_blockers(ExactMethaneHarmonicMinimizationReport._derive(self)[1])

    def _core_dict(self) -> dict[str, Any]:
        config, result = ExactMethaneHarmonicMinimizationReport._derive(self)
        initial = result.states[0]
        final = result.states[-1]
        parameter_set = deserialize_exact_methane_bond_angle_parameter_set(
            self._parameter_bytes
        )
        if (
            not initial.system.provenance.parent_sha256
            or initial.system.provenance.operations[-1]
            != _FROZEN_START_PROVENANCE_OPERATION
            or initial.system.provenance.preparation_ready
            or initial.system.provenance.claim_safe
            or final.system.provenance.preparation_ready
            or final.system.provenance.claim_safe
        ):
            _fail(
                "derived_provenance_mismatch",
                "diagnostic system provenance is not fail-closed",
            )
        source_input_sha256 = initial.system.provenance.parent_sha256[-1]
        _require_sha256(
            source_input_sha256,
            location="report.source_input_system_snapshot_sha256",
        )
        return {
            "schema_id": _FROZEN_REPORT_SCHEMA_ID,
            "schema_version": _FROZEN_REPORT_SCHEMA_VERSION,
            "claim_scope": _FROZEN_CLAIM_SCOPE,
            "functional_form_id": _FROZEN_FUNCTIONAL_FORM_ID,
            "coordinate_unit": "angstrom",
            "energy_unit": "kilojoule_per_mole",
            "force_unit": "kilojoule_per_mole_per_angstrom",
            "numeric_encoding": "ieee754_binary64_big_endian_hex",
            "algorithm_protocol": json.loads(_FROZEN_PROTOCOL_BYTES),
            "algorithm_protocol_sha256": _FROZEN_PROTOCOL_SHA256,
            "determinism_scope": _FROZEN_DETERMINISM_SCOPE,
            "config": ExactMethaneHarmonicMinimizationConfig.to_dict(config),
            "source_input_system_snapshot_sha256": source_input_sha256,
            "initial_system_snapshot_sha256": hashlib.sha256(
                initial.system_bytes
            ).hexdigest(),
            "final_system_snapshot_sha256": hashlib.sha256(
                final.system_bytes
            ).hexdigest(),
            "parameter_artifact_bytes_sha256": hashlib.sha256(
                self._parameter_bytes
            ).hexdigest(),
            "parameter_payload_sha256": parameter_set.parameter_payload_sha256,
            "parameter_set_sha256": parameter_set.parameter_set_sha256,
            "parameter_artifact_schema_version": (
                parameter_set.artifact_schema_version
            ),
            "parameter_functional_form_id": parameter_set.functional_form_id,
            "functional_form_binding_status": "parameter_payload_bound_match",
            "initial_parameter_assignment_sha256": initial.assignment_sha256,
            "final_parameter_assignment_sha256": final.assignment_sha256,
            "initial_harmonic_report_sha256": initial.harmonic_report_sha256,
            "final_harmonic_report_sha256": final.harmonic_report_sha256,
            "initial_virial_report_sha256": initial.virial_report_sha256,
            "final_virial_report_sha256": final.virial_report_sha256,
            "initial_energy_ieee754_binary64_be": _binary64_hex(
                initial.energy,
                location="report.initial_energy",
            ),
            "final_energy_ieee754_binary64_be": _binary64_hex(
                final.energy,
                location="report.final_energy",
            ),
            "initial_max_atom_force_norm_ieee754_binary64_be": _binary64_hex(
                initial.max_atom_force_norm,
                location="report.initial_max_atom_force_norm",
            ),
            "final_max_atom_force_norm_ieee754_binary64_be": _binary64_hex(
                final.max_atom_force_norm,
                location="report.final_max_atom_force_norm",
            ),
            "accepted_step_count": len(result.steps),
            "total_trial_count": result.total_trial_count,
            "rejected_trial_count": result.rejected_trial_count,
            "accepted_steps": [
                HarmonicMinimizationAcceptedStep.to_dict(step) for step in result.steps
            ],
            "accepted_trajectory_sha256": result.transcript_sha256,
            "termination_status": result.termination_status,
            "termination_code": result.termination_code,
            "last_trial_rejection_code": result.last_trial_rejection_code,
            "scoped_first_order_stationarity_observed": (
                result.termination_code == "stationarity_tolerance_met"
            ),
            "stationarity_is_not_a_minimum_attestation": True,
            "diagnostic_minimization_performed": bool(result.steps),
            "strict_energy_decrease_for_every_accepted_step": all(
                step.energy_after < step.energy_before for step in result.steps
            ),
            "derived_system_provenance_status": (
                "diagnostic_nonpromoted_lineage_bound"
            ),
            "final_system_provenance_preparation_ready": (
                final.system.provenance.preparation_ready
            ),
            "final_system_provenance_claim_safe": final.system.provenance.claim_safe,
            "runtime_minimizer_status": "not_implemented",
            "scientific_validation_status": "missing",
            "physics_supported": False,
            "scientific_validity_green": False,
            "parameterability_assessed": False,
            "parameterizable": False,
            "global_parameter_coverage_complete": False,
            "preparation_ready": False,
            "runtime_eligible": False,
            "execution_authorized": False,
            "energy_evaluation_authorized": False,
            "force_evaluation_authorized": False,
            "virial_evaluation_authorized": False,
            "minimization_authorized": False,
            "simulation_ready": False,
            "claim_safe": False,
            "blockers": list(_report_blockers(result)),
        }

    @property
    def report_sha256(self) -> str:
        return _sha256_document(ExactMethaneHarmonicMinimizationReport._core_dict(self))

    def to_dict(self) -> dict[str, Any]:
        payload = ExactMethaneHarmonicMinimizationReport._core_dict(self)
        payload["report_sha256"] = _sha256_document(payload)
        return payload

    def checkpoint_bytes(self, accepted_step_count: int) -> bytes:
        checkpoint = create_exact_methane_harmonic_minimization_checkpoint(
            self,
            accepted_step_count,
        )
        return serialize_exact_methane_harmonic_minimization_checkpoint(checkpoint)


_CHECKPOINT_KEYS = frozenset(
    {
        "schema_id",
        "schema_version",
        "claim_scope",
        "algorithm_protocol",
        "algorithm_protocol_sha256",
        "determinism_scope",
        "config",
        "source_input_system_snapshot_sha256",
        "initial_system_snapshot_base64",
        "initial_system_snapshot_sha256",
        "current_system_snapshot_base64",
        "current_system_snapshot_sha256",
        "parameter_artifact_base64",
        "parameter_artifact_bytes_sha256",
        "parameter_payload_sha256",
        "parameter_set_sha256",
        "parameter_assignment_sha256",
        "harmonic_report_sha256",
        "virial_report_sha256",
        "accepted_step_boundary",
        "accepted_step_count",
        "total_trial_count",
        "rejected_trial_count",
        "accepted_trajectory_sha256",
        "current_energy_ieee754_binary64_be",
        "current_max_atom_force_norm_ieee754_binary64_be",
        "physics_supported",
        "scientific_validity_green",
        "parameterability_assessed",
        "parameterizable",
        "global_parameter_coverage_complete",
        "preparation_ready",
        "runtime_eligible",
        "execution_authorized",
        "energy_evaluation_authorized",
        "force_evaluation_authorized",
        "virial_evaluation_authorized",
        "minimization_authorized",
        "simulation_ready",
        "claim_safe",
        "checkpoint_sha256",
    }
)


def _encode_artifact(data: bytes, *, location: str) -> str:
    if type(data) is not bytes or len(data) > _MAX_EMBEDDED_ARTIFACT_BYTES:
        _fail("artifact_too_large", f"{location} exceeds its byte cap")
    return base64.b64encode(data).decode("ascii")


def _decode_artifact(value: Any, *, location: str) -> bytes:
    if type(value) is not str or len(value) > 4 * _MAX_EMBEDDED_ARTIFACT_BYTES:
        _fail("invalid_base64", f"{location} must be bounded base64")
    try:
        data = base64.b64decode(value, validate=True)
    except (ValueError, TypeError) as exc:
        _fail("invalid_base64", f"invalid {location} base64: {exc}")
    if len(data) > _MAX_EMBEDDED_ARTIFACT_BYTES:
        _fail("artifact_too_large", f"{location} exceeds its byte cap")
    if base64.b64encode(data).decode("ascii") != value:
        _fail("noncanonical_base64", f"{location} base64 is not canonical")
    return data


@dataclass(frozen=True, init=False, slots=True)
class ExactMethaneHarmonicMinimizationCheckpoint:
    _canonical_bytes: bytes = field(repr=False)

    @classmethod
    def _from_bytes(
        cls,
        data: bytes,
    ) -> "ExactMethaneHarmonicMinimizationCheckpoint":
        _validate_checkpoint_bytes(data)
        instance = object.__new__(cls)
        object.__setattr__(instance, "_canonical_bytes", data)
        return instance

    @property
    def accepted_step_count(self) -> int:
        replay = _validate_checkpoint_bytes(self._canonical_bytes)
        return replay.document["accepted_step_count"]

    def to_dict(self) -> dict[str, Any]:
        replay = _validate_checkpoint_bytes(self._canonical_bytes)
        return json.loads(_canonical_json_bytes(replay.document))


def _checkpoint_document_from_prefix(
    initial_system_bytes: bytes,
    parameter_bytes: bytes,
    config: ExactMethaneHarmonicMinimizationConfig,
    prefix: _RunResult,
) -> dict[str, Any]:
    if type(initial_system_bytes) is not bytes or type(parameter_bytes) is not bytes:
        raise TypeError("checkpoint artifacts must be bytes")
    if type(config) is not ExactMethaneHarmonicMinimizationConfig:
        raise TypeError("config must be an ExactMethaneHarmonicMinimizationConfig")
    if type(prefix) is not _RunResult or not prefix.states:
        _fail("invalid_resume_prefix", "checkpoint prefix must contain a state")
    _validate_run_provenance(prefix)
    accepted_step_count = len(prefix.steps)
    if len(prefix.states) != accepted_step_count + 1:
        _fail("invalid_resume_prefix", "checkpoint prefix state count is invalid")
    state = prefix.states[-1]
    parameter_set = deserialize_exact_methane_bond_angle_parameter_set(parameter_bytes)
    initial_system = deserialize_all_atom_system(initial_system_bytes)
    if (
        not initial_system.provenance.parent_sha256
        or initial_system.provenance.operations[-1]
        != _FROZEN_START_PROVENANCE_OPERATION
    ):
        _fail(
            "derived_provenance_mismatch",
            "checkpoint initial provenance is not diagnostic-derived",
        )
    source_input_sha256 = initial_system.provenance.parent_sha256[-1]
    _require_sha256(
        source_input_sha256,
        location="checkpoint.source_input_system_snapshot_sha256",
    )
    core = {
        "schema_id": _FROZEN_CHECKPOINT_SCHEMA_ID,
        "schema_version": _FROZEN_CHECKPOINT_SCHEMA_VERSION,
        "claim_scope": _FROZEN_CLAIM_SCOPE,
        "algorithm_protocol": json.loads(_FROZEN_PROTOCOL_BYTES),
        "algorithm_protocol_sha256": _FROZEN_PROTOCOL_SHA256,
        "determinism_scope": _FROZEN_DETERMINISM_SCOPE,
        "config": ExactMethaneHarmonicMinimizationConfig.to_dict(config),
        "source_input_system_snapshot_sha256": source_input_sha256,
        "initial_system_snapshot_base64": _encode_artifact(
            initial_system_bytes,
            location="initial system",
        ),
        "initial_system_snapshot_sha256": hashlib.sha256(
            initial_system_bytes
        ).hexdigest(),
        "current_system_snapshot_base64": _encode_artifact(
            state.system_bytes,
            location="current system",
        ),
        "current_system_snapshot_sha256": hashlib.sha256(
            state.system_bytes
        ).hexdigest(),
        "parameter_artifact_base64": _encode_artifact(
            parameter_bytes,
            location="parameter artifact",
        ),
        "parameter_artifact_bytes_sha256": hashlib.sha256(parameter_bytes).hexdigest(),
        "parameter_payload_sha256": parameter_set.parameter_payload_sha256,
        "parameter_set_sha256": parameter_set.parameter_set_sha256,
        "parameter_assignment_sha256": state.assignment_sha256,
        "harmonic_report_sha256": state.harmonic_report_sha256,
        "virial_report_sha256": state.virial_report_sha256,
        "accepted_step_boundary": True,
        "accepted_step_count": accepted_step_count,
        "total_trial_count": prefix.total_trial_count,
        "rejected_trial_count": prefix.rejected_trial_count,
        "accepted_trajectory_sha256": prefix.transcript_sha256,
        "current_energy_ieee754_binary64_be": _binary64_hex(
            state.energy,
            location="checkpoint.current_energy",
        ),
        "current_max_atom_force_norm_ieee754_binary64_be": _binary64_hex(
            state.max_atom_force_norm,
            location="checkpoint.current_max_atom_force_norm",
        ),
        "physics_supported": False,
        "scientific_validity_green": False,
        "parameterability_assessed": False,
        "parameterizable": False,
        "global_parameter_coverage_complete": False,
        "preparation_ready": False,
        "runtime_eligible": False,
        "execution_authorized": False,
        "energy_evaluation_authorized": False,
        "force_evaluation_authorized": False,
        "virial_evaluation_authorized": False,
        "minimization_authorized": False,
        "simulation_ready": False,
        "claim_safe": False,
    }
    core["checkpoint_sha256"] = _sha256_document(core)
    return core


def _checkpoint_document(
    report: ExactMethaneHarmonicMinimizationReport,
    accepted_step_count: int,
) -> dict[str, Any]:
    if type(report) is not ExactMethaneHarmonicMinimizationReport:
        raise TypeError("report must be an ExactMethaneHarmonicMinimizationReport")
    if type(accepted_step_count) is not int:
        raise TypeError("accepted_step_count must be an exact integer")
    config, completed = ExactMethaneHarmonicMinimizationReport._derive(report)
    if not 0 <= accepted_step_count < len(completed.states):
        raise ValueError("accepted_step_count must name an accepted-step boundary")
    prefix = _run_descent(
        report._initial_system_bytes,
        report._parameter_bytes,
        config,
        stop_after_accepted_steps=accepted_step_count,
    )
    if len(prefix.steps) != accepted_step_count:
        raise ValueError("accepted_step_count is beyond deterministic termination")
    return _checkpoint_document_from_prefix(
        report._initial_system_bytes,
        report._parameter_bytes,
        config,
        prefix,
    )


def create_exact_methane_harmonic_minimization_checkpoint(
    report: ExactMethaneHarmonicMinimizationReport,
    accepted_step_count: int,
) -> ExactMethaneHarmonicMinimizationCheckpoint:
    document = _checkpoint_document(report, accepted_step_count)
    return ExactMethaneHarmonicMinimizationCheckpoint._from_bytes(
        _canonical_json_bytes(document)
    )


def _validate_checkpoint_bytes(
    data: bytes,
) -> _CheckpointReplay:
    document = _parse_json_bytes(
        data,
        location="checkpoint",
        byte_cap=_MAX_CHECKPOINT_BYTES,
    )
    _require_exact_keys(document, _CHECKPOINT_KEYS, location="checkpoint")
    if _canonical_json_bytes(document) != data:
        _fail("noncanonical_checkpoint", "checkpoint bytes must be canonical")
    if (
        document["schema_id"] != _FROZEN_CHECKPOINT_SCHEMA_ID
        or document["schema_version"] != _FROZEN_CHECKPOINT_SCHEMA_VERSION
        or document["claim_scope"] != _FROZEN_CLAIM_SCOPE
        or document["algorithm_protocol"] != json.loads(_FROZEN_PROTOCOL_BYTES)
        or document["algorithm_protocol_sha256"] != _FROZEN_PROTOCOL_SHA256
        or document["determinism_scope"] != _FROZEN_DETERMINISM_SCOPE
    ):
        _fail("checkpoint_protocol_mismatch", "checkpoint protocol does not match")
    provided_sha = _require_sha256(
        document["checkpoint_sha256"],
        location="checkpoint.checkpoint_sha256",
    )
    core = {key: value for key, value in document.items() if key != "checkpoint_sha256"}
    if provided_sha != _sha256_document(core):
        _fail("checkpoint_hash_mismatch", "checkpoint hash does not match")
    for name in (
        "accepted_step_boundary",
        "physics_supported",
        "scientific_validity_green",
        "parameterability_assessed",
        "parameterizable",
        "global_parameter_coverage_complete",
        "preparation_ready",
        "runtime_eligible",
        "execution_authorized",
        "energy_evaluation_authorized",
        "force_evaluation_authorized",
        "virial_evaluation_authorized",
        "minimization_authorized",
        "simulation_ready",
        "claim_safe",
    ):
        expected = name == "accepted_step_boundary"
        if type(document[name]) is not bool or document[name] is not expected:
            _fail("checkpoint_authority_mismatch", f"checkpoint {name} is invalid")
    config_document = document["config"]
    if type(config_document) is not dict:
        _fail("checkpoint_config_invalid", "checkpoint config must be an object")
    config = _config_from_bytes(_canonical_json_bytes(config_document))
    initial_bytes = _decode_artifact(
        document["initial_system_snapshot_base64"],
        location="initial system",
    )
    current_bytes = _decode_artifact(
        document["current_system_snapshot_base64"],
        location="current system",
    )
    parameter_bytes = _decode_artifact(
        document["parameter_artifact_base64"],
        location="parameter artifact",
    )
    for payload, key, location in (
        (initial_bytes, "initial_system_snapshot_sha256", "initial system"),
        (current_bytes, "current_system_snapshot_sha256", "current system"),
        (parameter_bytes, "parameter_artifact_bytes_sha256", "parameter artifact"),
    ):
        expected_sha = _require_sha256(document[key], location=f"checkpoint.{key}")
        if hashlib.sha256(payload).hexdigest() != expected_sha:
            _fail("checkpoint_artifact_hash_mismatch", f"{location} hash mismatch")
    try:
        initial_system = deserialize_all_atom_system(initial_bytes)
        current_system = deserialize_all_atom_system(current_bytes)
        parameter_set = deserialize_exact_methane_bond_angle_parameter_set(
            parameter_bytes
        )
        if serialize_all_atom_system(initial_system) != initial_bytes:
            _fail("checkpoint_artifact_noncanonical", "initial system is noncanonical")
        if serialize_all_atom_system(current_system) != current_bytes:
            _fail("checkpoint_artifact_noncanonical", "current system is noncanonical")
        if (
            serialize_exact_methane_bond_angle_parameter_set(parameter_set)
            != parameter_bytes
        ):
            _fail("checkpoint_artifact_noncanonical", "parameter is noncanonical")
    except ExactMethaneHarmonicMinimizationError:
        raise
    except (TypeError, ValueError, OverflowError, RuntimeError, RecursionError) as exc:
        _fail("checkpoint_artifact_invalid", f"checkpoint artifact failed: {exc}")
    _require_form_bound_parameter_set(parameter_set)
    if (
        not initial_system.provenance.operations
        or initial_system.provenance.operations[-1]
        != _FROZEN_START_PROVENANCE_OPERATION
        or not initial_system.provenance.parent_sha256
    ):
        _fail(
            "checkpoint_embedded_provenance_mismatch",
            "checkpoint initial system is not diagnostic-derived",
        )
    source_input_sha256 = _require_sha256(
        document["source_input_system_snapshot_sha256"],
        location="checkpoint.source_input_system_snapshot_sha256",
    )
    if initial_system.provenance.parent_sha256[-1] != source_input_sha256:
        _fail(
            "checkpoint_embedded_provenance_mismatch",
            "checkpoint source-input lineage does not match",
        )
    if any(
        value
        for value in (
            initial_system.provenance.preparation_ready,
            initial_system.provenance.claim_safe,
            current_system.provenance.preparation_ready,
            current_system.provenance.claim_safe,
        )
    ):
        _fail(
            "checkpoint_embedded_authority_mismatch",
            "checkpoint systems must carry non-promoted provenance",
        )
    accepted_count = document["accepted_step_count"]
    if (
        type(accepted_count) is not int
        or not 0 <= accepted_count <= config.max_accepted_steps
    ):
        _fail("checkpoint_step_invalid", "checkpoint accepted step is invalid")
    replay = _run_descent(
        initial_bytes,
        parameter_bytes,
        config,
        stop_after_accepted_steps=accepted_count,
    )
    _validate_run_provenance(replay)
    if len(replay.steps) != accepted_count or len(replay.states) != accepted_count + 1:
        _fail(
            "checkpoint_step_invalid",
            "checkpoint boundary lies beyond deterministic termination",
        )
    for name in ("total_trial_count", "rejected_trial_count"):
        if type(document[name]) is not int or document[name] < 0:
            _fail("checkpoint_counter_invalid", f"checkpoint {name} is invalid")
    state = replay.states[accepted_count]
    comparisons = (
        (state.system_bytes, current_bytes),
        (document["total_trial_count"], replay.total_trial_count),
        (document["rejected_trial_count"], replay.rejected_trial_count),
        (document["accepted_trajectory_sha256"], replay.transcript_sha256),
        (
            document["source_input_system_snapshot_sha256"],
            initial_system.provenance.parent_sha256[-1],
        ),
        (
            document["current_energy_ieee754_binary64_be"],
            _binary64_hex(state.energy, location="checkpoint.replay_energy"),
        ),
        (
            document["current_max_atom_force_norm_ieee754_binary64_be"],
            _binary64_hex(
                state.max_atom_force_norm,
                location="checkpoint.replay_max_force",
            ),
        ),
        (document["parameter_payload_sha256"], parameter_set.parameter_payload_sha256),
        (document["parameter_set_sha256"], parameter_set.parameter_set_sha256),
        (document["parameter_assignment_sha256"], state.assignment_sha256),
        (document["harmonic_report_sha256"], state.harmonic_report_sha256),
        (document["virial_report_sha256"], state.virial_report_sha256),
    )
    if any(observed != expected for observed, expected in comparisons):
        _fail(
            "checkpoint_replay_mismatch",
            "checkpoint does not match full accepted-prefix replay",
        )
    for key in (
        "accepted_trajectory_sha256",
        "source_input_system_snapshot_sha256",
        "parameter_payload_sha256",
        "parameter_set_sha256",
        "parameter_assignment_sha256",
        "harmonic_report_sha256",
        "virial_report_sha256",
    ):
        _require_sha256(document[key], location=f"checkpoint.{key}")
    return _CheckpointReplay(
        document=document,
        initial_system_bytes=initial_bytes,
        parameter_bytes=parameter_bytes,
        config=config,
        prefix=replay,
    )


def serialize_exact_methane_harmonic_minimization_checkpoint(
    checkpoint: ExactMethaneHarmonicMinimizationCheckpoint,
) -> bytes:
    if type(checkpoint) is not ExactMethaneHarmonicMinimizationCheckpoint:
        raise TypeError(
            "checkpoint must be an ExactMethaneHarmonicMinimizationCheckpoint"
        )
    _validate_checkpoint_bytes(checkpoint._canonical_bytes)
    return bytes(checkpoint._canonical_bytes)


def deserialize_exact_methane_harmonic_minimization_checkpoint(
    data: bytes,
) -> ExactMethaneHarmonicMinimizationCheckpoint:
    return ExactMethaneHarmonicMinimizationCheckpoint._from_bytes(data)


def resume_exact_methane_harmonic_minimization_diagnostic(
    checkpoint_bytes: bytes,
    *,
    pause_after_additional_accepted_steps: int | None = None,
) -> (
    ExactMethaneHarmonicMinimizationReport | ExactMethaneHarmonicMinimizationCheckpoint
):
    replay = _validate_checkpoint_bytes(checkpoint_bytes)
    if (
        pause_after_additional_accepted_steps is not None
        and type(pause_after_additional_accepted_steps) is not int
    ):
        raise TypeError(
            "pause_after_additional_accepted_steps must be an exact integer or None"
        )
    stop_after = None
    if pause_after_additional_accepted_steps is not None:
        stop_after = len(replay.prefix.steps) + pause_after_additional_accepted_steps
    continued = _run_descent(
        replay.initial_system_bytes,
        replay.parameter_bytes,
        replay.config,
        prefix=replay.prefix,
        stop_after_accepted_steps=stop_after,
    )
    _validate_run_provenance(continued)
    if continued.termination_code == "checkpoint_boundary_reached":
        document = _checkpoint_document_from_prefix(
            replay.initial_system_bytes,
            replay.parameter_bytes,
            replay.config,
            continued,
        )
        return ExactMethaneHarmonicMinimizationCheckpoint._from_bytes(
            _canonical_json_bytes(document)
        )
    return ExactMethaneHarmonicMinimizationReport._from_validated_snapshots(
        replay.initial_system_bytes,
        replay.parameter_bytes,
        _config_bytes(replay.config),
        resume_checkpoint_bytes=bytes(checkpoint_bytes),
    )


def run_exact_methane_harmonic_minimization_diagnostic(
    system: AllAtomSystem,
    parameter_set: ExactMethaneBondAngleParameterSet,
    *,
    config: ExactMethaneHarmonicMinimizationConfig | None = None,
    pause_after_accepted_steps: int | None = None,
) -> (
    ExactMethaneHarmonicMinimizationReport | ExactMethaneHarmonicMinimizationCheckpoint
):
    if pause_after_accepted_steps is None:
        return ExactMethaneHarmonicMinimizationReport(
            system,
            parameter_set,
            config=config,
        )
    if type(pause_after_accepted_steps) is not int:
        raise TypeError("pause_after_accepted_steps must be an exact integer or None")
    selected_config = (
        ExactMethaneHarmonicMinimizationConfig() if config is None else config
    )
    if type(selected_config) is not ExactMethaneHarmonicMinimizationConfig:
        raise TypeError("config must be an ExactMethaneHarmonicMinimizationConfig")
    initial_system_bytes, parameter_bytes = _snapshot_inputs(system, parameter_set)
    config_bytes = _config_bytes(selected_config)
    validated_config = _config_from_bytes(config_bytes)
    prefix = _run_descent(
        initial_system_bytes,
        parameter_bytes,
        validated_config,
        stop_after_accepted_steps=pause_after_accepted_steps,
    )
    _validate_run_provenance(prefix)
    report = ExactMethaneHarmonicMinimizationReport._from_validated_snapshots(
        initial_system_bytes,
        parameter_bytes,
        config_bytes,
    )
    if prefix.termination_code != "checkpoint_boundary_reached":
        return report
    document = _checkpoint_document_from_prefix(
        initial_system_bytes,
        parameter_bytes,
        validated_config,
        prefix,
    )
    return ExactMethaneHarmonicMinimizationCheckpoint._from_bytes(
        _canonical_json_bytes(document)
    )


__all__ = [
    "EXACT_METHANE_HARMONIC_MINIMIZATION_ALGORITHM_PROTOCOL_ID",
    "EXACT_METHANE_HARMONIC_MINIMIZATION_CHECKPOINT_SCHEMA_ID",
    "EXACT_METHANE_HARMONIC_MINIMIZATION_CHECKPOINT_SCHEMA_VERSION",
    "EXACT_METHANE_HARMONIC_MINIMIZATION_CLAIM_SCOPE",
    "EXACT_METHANE_HARMONIC_MINIMIZATION_DIAGNOSTIC_SCHEMA_ID",
    "EXACT_METHANE_HARMONIC_MINIMIZATION_DIAGNOSTIC_SCHEMA_VERSION",
    "ExactMethaneHarmonicMinimizationCheckpoint",
    "ExactMethaneHarmonicMinimizationConfig",
    "ExactMethaneHarmonicMinimizationError",
    "ExactMethaneHarmonicMinimizationReport",
    "HarmonicMinimizationAcceptedStep",
    "create_exact_methane_harmonic_minimization_checkpoint",
    "deserialize_exact_methane_harmonic_minimization_checkpoint",
    "resume_exact_methane_harmonic_minimization_diagnostic",
    "run_exact_methane_harmonic_minimization_diagnostic",
    "serialize_exact_methane_harmonic_minimization_checkpoint",
]
