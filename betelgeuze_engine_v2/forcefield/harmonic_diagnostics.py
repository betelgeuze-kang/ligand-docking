"""Diagnostic-only exact-methane harmonic bond and angle mechanics.

This module is a deliberately narrow numerical check of the existing
exact-methane identity, parameter, and assignment contracts.  It evaluates
only the four assigned C-H bonds and six assigned H-C-H angles.  The reported
numbers are not a complete molecular energy and never authorize runtime force
field use, minimization, simulation, scientific validity, or product claims.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
import struct
from typing import Any, Iterable

import torch

from betelgeuze_engine_v2.forcefield.parameters import (
    EXACT_METHANE_HARMONIC_FUNCTIONAL_FORM_ID,
    ExactMethaneBondAngleParameterAssignmentReport,
    ExactMethaneBondAngleParameterSet,
    analyze_exact_methane_bond_angle_parameter_assignment,
    deserialize_exact_methane_bond_angle_parameter_set,
    serialize_exact_methane_bond_angle_parameter_set,
)
from betelgeuze_engine_v2.molecular.bonded_inventory import (
    CanonicalAngleIdentity,
    CanonicalBondIdentity,
)
from betelgeuze_engine_v2.molecular.models import AllAtomSystem
from betelgeuze_engine_v2.molecular.serialization import (
    deserialize_all_atom_system,
    serialize_all_atom_system,
)


_FROZEN_EXACT_METHANE_HARMONIC_DIAGNOSTIC_SCHEMA_VERSION = "1.0.0"
_FROZEN_EXACT_METHANE_HARMONIC_DIAGNOSTIC_SCHEMA_ID = (
    "betelgeuze.exact_methane_harmonic_diagnostic/"
    f"{_FROZEN_EXACT_METHANE_HARMONIC_DIAGNOSTIC_SCHEMA_VERSION}"
)
_FROZEN_EXACT_METHANE_HARMONIC_DIAGNOSTIC_CLAIM_SCOPE = (
    "nonphysical_exact_methane_bond_angle_numerical_diagnostic_only"
)
_FROZEN_EXACT_METHANE_HARMONIC_SINGULARITY_POLICY_ID = (
    "reject_bond_le_1e-8_angstrom_or_angle_sine_le_1e-8/1.0.0"
)
_FROZEN_MIN_DIAGNOSTIC_BOND_LENGTH_ANGSTROM = 1.0e-8
_FROZEN_MIN_DIAGNOSTIC_ANGLE_SINE = 1.0e-8
_FROZEN_DIAGNOSTIC_FORCE_DEFINITION = (
    "negative_exact_analytic_coordinate_gradient_of_reported_scalar_"
    "bond_angle_diagnostic_energy"
)

EXACT_METHANE_HARMONIC_DIAGNOSTIC_SCHEMA_VERSION = (
    _FROZEN_EXACT_METHANE_HARMONIC_DIAGNOSTIC_SCHEMA_VERSION
)
EXACT_METHANE_HARMONIC_DIAGNOSTIC_SCHEMA_ID = (
    _FROZEN_EXACT_METHANE_HARMONIC_DIAGNOSTIC_SCHEMA_ID
)
EXACT_METHANE_HARMONIC_DIAGNOSTIC_CLAIM_SCOPE = (
    _FROZEN_EXACT_METHANE_HARMONIC_DIAGNOSTIC_CLAIM_SCOPE
)
EXACT_METHANE_HARMONIC_SINGULARITY_POLICY_ID = (
    _FROZEN_EXACT_METHANE_HARMONIC_SINGULARITY_POLICY_ID
)
MIN_DIAGNOSTIC_BOND_LENGTH_ANGSTROM = (
    _FROZEN_MIN_DIAGNOSTIC_BOND_LENGTH_ANGSTROM
)
MIN_DIAGNOSTIC_ANGLE_SINE = _FROZEN_MIN_DIAGNOSTIC_ANGLE_SINE
DIAGNOSTIC_FORCE_DEFINITION = _FROZEN_DIAGNOSTIC_FORCE_DEFINITION

_VECTOR_WIDTH = 3
_EXPECTED_ATOM_COUNT = 5
_EXPECTED_BOND_TERM_COUNT = 4
_EXPECTED_ANGLE_TERM_COUNT = 6
_FROZEN_EXACT_METHANE_HARMONIC_FUNCTIONAL_FORM_ID = (
    "harmonic_half_k_delta_squared_bond_angle/1.0.0"
)


class ExactMethaneHarmonicDiagnosticError(ValueError):
    """Fail-closed diagnostic error with a stable machine-readable code."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.blockers = (f"harmonic_diagnostic_{code}",)
        super().__init__(message)


def _fail(code: str, message: str) -> None:
    raise ExactMethaneHarmonicDiagnosticError(code, message)


def _canonical_float(value: float, *, location: str) -> float:
    try:
        result = float(value)
    except (OverflowError, TypeError, ValueError) as exc:
        _fail("nonfinite_result", f"{location} must be finite: {exc}")
    if not math.isfinite(result):
        _fail("nonfinite_result", f"{location} must be finite")
    return 0.0 if result == 0.0 else result


def _finite_fsum(values: Iterable[float], *, location: str) -> float:
    try:
        result = math.fsum(values)
    except (OverflowError, ValueError) as exc:
        _fail("nonfinite_result", f"{location} must remain finite: {exc}")
    return _canonical_float(result, location=location)


def _binary64_hex(value: float, *, location: str) -> str:
    return struct.pack(">d", _canonical_float(value, location=location)).hex()


def _canonical_json_bytes(document: dict[str, Any]) -> bytes:
    try:
        return json.dumps(
            document,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError) as exc:  # pragma: no cover - typed rows guard this
        _fail("serialization_failed", f"diagnostic serialization failed: {exc}")


def _sha256_document(document: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json_bytes(document)).hexdigest()


Vector3 = tuple[float, float, float]


def _vector(values: Iterable[float], *, location: str) -> Vector3:
    result = tuple(
        _canonical_float(value, location=f"{location}[{index}]")
        for index, value in enumerate(values)
    )
    if len(result) != _VECTOR_WIDTH:
        _fail("invalid_vector", f"{location} must contain three values")
    return result  # type: ignore[return-value]


def _add(left: Vector3, right: Vector3) -> Vector3:
    return _vector(
        (left[index] + right[index] for index in range(_VECTOR_WIDTH)),
        location="vector_sum",
    )


def _subtract(left: Vector3, right: Vector3) -> Vector3:
    return _vector(
        (left[index] - right[index] for index in range(_VECTOR_WIDTH)),
        location="vector_difference",
    )


def _scale(value: float, vector: Vector3) -> Vector3:
    return _vector(
        (value * component for component in vector),
        location="scaled_vector",
    )


def _dot(left: Vector3, right: Vector3) -> float:
    return _finite_fsum(
        (left[index] * right[index] for index in range(_VECTOR_WIDTH)),
        location="dot_product",
    )


def _cross(left: Vector3, right: Vector3) -> Vector3:
    return _vector(
        (
            left[1] * right[2] - left[2] * right[1],
            left[2] * right[0] - left[0] * right[2],
            left[0] * right[1] - left[1] * right[0],
        ),
        location="cross_product",
    )


def _norm(vector: Vector3) -> float:
    return _canonical_float(math.sqrt(_dot(vector, vector)), location="norm")


def _vector_dict(vector: Vector3, *, location: str) -> dict[str, str]:
    return {
        axis: _binary64_hex(vector[index], location=f"{location}.{axis}")
        for index, axis in enumerate(("x", "y", "z"))
    }


@dataclass(frozen=True, slots=True)
class HarmonicBondDiagnosticTerm:
    identity: CanonicalBondIdentity
    parameter_id: str
    distance_angstrom: float
    displacement_angstrom: float
    energy_kj_mol: float
    force_on_atom_i_kj_mol_angstrom: Vector3
    force_on_atom_j_kj_mol_angstrom: Vector3

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.identity.to_dict(),
            "parameter_id": self.parameter_id,
            "distance_ieee754_binary64_be": _binary64_hex(
                self.distance_angstrom,
                location="bond.distance",
            ),
            "displacement_ieee754_binary64_be": _binary64_hex(
                self.displacement_angstrom,
                location="bond.displacement",
            ),
            "energy_ieee754_binary64_be": _binary64_hex(
                self.energy_kj_mol,
                location="bond.energy",
            ),
            "force_on_atom_i_ieee754_binary64_be": _vector_dict(
                self.force_on_atom_i_kj_mol_angstrom,
                location="bond.force_on_atom_i",
            ),
            "force_on_atom_j_ieee754_binary64_be": _vector_dict(
                self.force_on_atom_j_kj_mol_angstrom,
                location="bond.force_on_atom_j",
            ),
        }


@dataclass(frozen=True, slots=True)
class HarmonicAngleDiagnosticTerm:
    identity: CanonicalAngleIdentity
    parameter_id: str
    angle_radian: float
    displacement_radian: float
    energy_kj_mol: float
    force_on_outer_i_kj_mol_angstrom: Vector3
    force_on_center_kj_mol_angstrom: Vector3
    force_on_outer_k_kj_mol_angstrom: Vector3

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.identity.to_dict(),
            "parameter_id": self.parameter_id,
            "angle_ieee754_binary64_be": _binary64_hex(
                self.angle_radian,
                location="angle.angle",
            ),
            "displacement_ieee754_binary64_be": _binary64_hex(
                self.displacement_radian,
                location="angle.displacement",
            ),
            "energy_ieee754_binary64_be": _binary64_hex(
                self.energy_kj_mol,
                location="angle.energy",
            ),
            "force_on_outer_i_ieee754_binary64_be": _vector_dict(
                self.force_on_outer_i_kj_mol_angstrom,
                location="angle.force_on_outer_i",
            ),
            "force_on_center_ieee754_binary64_be": _vector_dict(
                self.force_on_center_kj_mol_angstrom,
                location="angle.force_on_center",
            ),
            "force_on_outer_k_ieee754_binary64_be": _vector_dict(
                self.force_on_outer_k_kj_mol_angstrom,
                location="angle.force_on_outer_k",
            ),
        }


def _validate_input_state(system: AllAtomSystem) -> None:
    if type(system) is not AllAtomSystem:
        raise TypeError("system must be an AllAtomSystem")
    coordinates = system.coordinates
    if system.coordinate_unit != "angstrom":
        _fail("unsupported_coordinate_unit", "coordinates must use angstrom")
    if system.cell is not None:
        _fail("cell_not_supported", "the diagnostic requires a cell-free system")
    if system.model_count != 1:
        _fail(
            "coordinate_model_count_not_one",
            "the diagnostic requires exactly one coordinate model",
        )
    if system.atom_count != _EXPECTED_ATOM_COUNT or tuple(coordinates.shape) != (
        1,
        _EXPECTED_ATOM_COUNT,
        3,
    ):
        _fail(
            "coordinate_shape_not_exact_methane",
            "coordinates must have exact shape [1, 5, 3]",
        )
    if coordinates.device.type != "cpu":
        _fail("coordinates_not_cpu", "the diagnostic is CPU-only")
    if coordinates.dtype is not torch.float64:
        _fail("coordinates_not_float64", "coordinates must use torch.float64")
    if not bool(torch.isfinite(coordinates).all().item()):
        _fail("nonfinite_coordinates", "coordinates must be finite")


def _snapshot_inputs(
    system: AllAtomSystem,
    parameter_set: ExactMethaneBondAngleParameterSet,
) -> tuple[bytes, bytes]:
    if type(system) is not AllAtomSystem:
        raise TypeError("system must be an AllAtomSystem")
    if type(parameter_set) is not ExactMethaneBondAngleParameterSet:
        raise TypeError(
            "parameter_set must be an ExactMethaneBondAngleParameterSet"
        )
    try:
        _validate_input_state(system)
    except ExactMethaneHarmonicDiagnosticError:
        raise
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _fail("system_snapshot_failed", f"invalid system state: {exc}")
    try:
        system_bytes = serialize_all_atom_system(system)
        system_snapshot = deserialize_all_atom_system(system_bytes)
    except (TypeError, ValueError, RuntimeError) as exc:
        _fail("system_snapshot_failed", f"canonical system snapshot failed: {exc}")
    _validate_input_state(system_snapshot)

    try:
        parameter_copy = (
            ExactMethaneBondAngleParameterSet._validated_copy(parameter_set)
        )
        parameter_bytes = serialize_exact_methane_bond_angle_parameter_set(
            parameter_copy
        )
        deserialize_exact_methane_bond_angle_parameter_set(parameter_bytes)
    except (AttributeError, TypeError, ValueError, OverflowError, RuntimeError) as exc:
        _fail(
            "parameter_snapshot_failed",
            f"canonical parameter snapshot failed: {exc}",
        )
    return system_bytes, parameter_bytes


def _require_exact_assignment(
    system: AllAtomSystem,
    parameter_set: ExactMethaneBondAngleParameterSet,
) -> ExactMethaneBondAngleParameterAssignmentReport:
    assignment = analyze_exact_methane_bond_angle_parameter_assignment(
        system,
        parameter_set,
    )
    if not assignment.bond_angle_assignment_complete:
        _fail(
            "assignment_unavailable",
            "the exact methane bond/angle assignment is unavailable",
        )
    if assignment.parameter_assignment_sha256 is None:
        _fail(
            "assignment_digest_missing",
            "a complete assignment must have a content digest",
        )
    if (
        len(assignment.bond_assignments) != _EXPECTED_BOND_TERM_COUNT
        or len(assignment.angle_assignments) != _EXPECTED_ANGLE_TERM_COUNT
        or tuple(item.identity for item in assignment.bond_assignments)
        != assignment.inventory_report.bond_identities
        or tuple(item.identity for item in assignment.angle_assignments)
        != assignment.inventory_report.angle_identities
    ):
        _fail(
            "term_set_not_exact",
            "the diagnostic requires exactly four bond and six angle terms",
        )
    return assignment


def _bond_term(
    identity: CanonicalBondIdentity,
    parameter_id: str,
    coordinates: tuple[Vector3, ...],
    *,
    equilibrium_length: float,
    force_constant: float,
) -> HarmonicBondDiagnosticTerm:
    displacement = _subtract(
        coordinates[identity.atom_i],
        coordinates[identity.atom_j],
    )
    distance = _norm(displacement)
    if distance <= _FROZEN_MIN_DIAGNOSTIC_BOND_LENGTH_ANGSTROM:
        _fail(
            "singular_bond_geometry",
            "all assigned bond lengths must exceed the singularity threshold",
        )
    delta = _canonical_float(
        distance - equilibrium_length,
        location="bond_displacement",
    )
    energy = _canonical_float(
        0.5 * force_constant * delta * delta,
        location="bond_energy",
    )
    d_energy_d_distance = _canonical_float(
        force_constant * delta,
        location="bond_energy_derivative",
    )
    force_i = _scale(-d_energy_d_distance / distance, displacement)
    force_j = _scale(-1.0, force_i)
    return HarmonicBondDiagnosticTerm(
        identity=identity,
        parameter_id=parameter_id,
        distance_angstrom=distance,
        displacement_angstrom=delta,
        energy_kj_mol=energy,
        force_on_atom_i_kj_mol_angstrom=force_i,
        force_on_atom_j_kj_mol_angstrom=force_j,
    )


def _angle_term(
    identity: CanonicalAngleIdentity,
    parameter_id: str,
    coordinates: tuple[Vector3, ...],
    *,
    equilibrium_angle: float,
    force_constant: float,
) -> HarmonicAngleDiagnosticTerm:
    outer_i = coordinates[identity.outer_atom_i]
    center = coordinates[identity.center_atom]
    outer_k = coordinates[identity.outer_atom_k]
    u = _subtract(outer_i, center)
    v = _subtract(outer_k, center)
    length_u = _norm(u)
    length_v = _norm(v)
    if (
        length_u <= _FROZEN_MIN_DIAGNOSTIC_BOND_LENGTH_ANGSTROM
        or length_v <= _FROZEN_MIN_DIAGNOSTIC_BOND_LENGTH_ANGSTROM
    ):
        _fail(
            "singular_bond_geometry",
            "angle legs must exceed the bond singularity threshold",
        )
    cross_norm = _norm(_cross(u, v))
    denominator = _canonical_float(
        length_u * length_v,
        location="angle_length_product",
    )
    sine = _canonical_float(
        cross_norm / denominator,
        location="angle_sine",
    )
    if sine <= _FROZEN_MIN_DIAGNOSTIC_ANGLE_SINE:
        _fail(
            "singular_angle_geometry",
            "assigned angles must remain away from zero and pi",
        )
    dot = _dot(u, v)
    cosine = _canonical_float(dot / denominator, location="angle_cosine")
    angle = _canonical_float(
        math.atan2(cross_norm, dot),
        location="angle_radian",
    )
    delta = _canonical_float(
        angle - equilibrium_angle,
        location="angle_displacement",
    )
    energy = _canonical_float(
        0.5 * force_constant * delta * delta,
        location="angle_energy",
    )
    d_energy_d_angle = _canonical_float(
        force_constant * delta,
        location="angle_energy_derivative",
    )
    unit_u = _scale(1.0 / length_u, u)
    unit_v = _scale(1.0 / length_v, v)
    gradient_u = _scale(
        1.0 / (length_u * sine),
        _subtract(_scale(cosine, unit_u), unit_v),
    )
    gradient_v = _scale(
        1.0 / (length_v * sine),
        _subtract(_scale(cosine, unit_v), unit_u),
    )
    force_i = _scale(-d_energy_d_angle, gradient_u)
    force_k = _scale(-d_energy_d_angle, gradient_v)
    force_center = _scale(-1.0, _add(force_i, force_k))
    return HarmonicAngleDiagnosticTerm(
        identity=identity,
        parameter_id=parameter_id,
        angle_radian=angle,
        displacement_radian=delta,
        energy_kj_mol=energy,
        force_on_outer_i_kj_mol_angstrom=force_i,
        force_on_center_kj_mol_angstrom=force_center,
        force_on_outer_k_kj_mol_angstrom=force_k,
    )


def _aggregate_forces(
    bond_terms: tuple[HarmonicBondDiagnosticTerm, ...],
    angle_terms: tuple[HarmonicAngleDiagnosticTerm, ...],
) -> tuple[Vector3, ...]:
    contributions: list[list[list[float]]] = [
        [[], [], []] for _ in range(_EXPECTED_ATOM_COUNT)
    ]

    def add(atom_index: int, force: Vector3) -> None:
        for axis in range(_VECTOR_WIDTH):
            contributions[atom_index][axis].append(force[axis])

    for term in bond_terms:
        add(term.identity.atom_i, term.force_on_atom_i_kj_mol_angstrom)
        add(term.identity.atom_j, term.force_on_atom_j_kj_mol_angstrom)
    for term in angle_terms:
        add(
            term.identity.outer_atom_i,
            term.force_on_outer_i_kj_mol_angstrom,
        )
        add(term.identity.center_atom, term.force_on_center_kj_mol_angstrom)
        add(
            term.identity.outer_atom_k,
            term.force_on_outer_k_kj_mol_angstrom,
        )
    return tuple(
        _vector(
            (
                _finite_fsum(
                    contributions[atom][axis],
                    location=f"atom_forces[{atom}][{axis}]",
                )
                for axis in range(3)
            ),
            location=f"atom_forces[{atom}]",
        )
        for atom in range(_EXPECTED_ATOM_COUNT)
    )


@dataclass(frozen=True, slots=True)
class _DerivedHarmonicDiagnostic:
    assignment_report: ExactMethaneBondAngleParameterAssignmentReport
    input_snapshot_sha256: str
    parameter_artifact_bytes_sha256: str
    bond_terms: tuple[HarmonicBondDiagnosticTerm, ...]
    angle_terms: tuple[HarmonicAngleDiagnosticTerm, ...]
    bond_energy_kj_mol: float
    angle_energy_kj_mol: float
    total_energy_kj_mol: float
    atom_forces_kj_mol_angstrom: tuple[Vector3, ...]


def _derive_diagnostic_from_snapshots(
    system_bytes: bytes,
    parameter_bytes: bytes,
) -> _DerivedHarmonicDiagnostic:
    if type(system_bytes) is not bytes or type(parameter_bytes) is not bytes:
        _fail(
            "snapshot_recomputation_failed",
            "diagnostic snapshots must remain immutable byte strings",
        )
    try:
        system_snapshot = deserialize_all_atom_system(system_bytes)
        parameter_snapshot = deserialize_exact_methane_bond_angle_parameter_set(
            parameter_bytes
        )
    except (TypeError, ValueError, RuntimeError) as exc:
        _fail(
            "snapshot_recomputation_failed",
            f"diagnostic snapshot recomputation failed: {exc}",
        )
    try:
        system_is_canonical = (
            serialize_all_atom_system(system_snapshot) == system_bytes
        )
        parameter_is_canonical = (
            serialize_exact_methane_bond_angle_parameter_set(parameter_snapshot)
            == parameter_bytes
        )
    except (TypeError, ValueError, RuntimeError) as exc:
        _fail(
            "snapshot_recomputation_failed",
            f"diagnostic snapshot canonicalization failed: {exc}",
        )
    if not system_is_canonical or not parameter_is_canonical:
        _fail(
            "snapshot_recomputation_failed",
            "diagnostic snapshots must remain byte-canonical",
        )
    _validate_input_state(system_snapshot)
    assignment = _require_exact_assignment(
        system_snapshot,
        parameter_snapshot,
    )
    coordinates = tuple(
        _vector(row, location=f"coordinates[0][{atom_index}]")
        for atom_index, row in enumerate(system_snapshot.coordinates[0].tolist())
    )
    bond_parameter = parameter_snapshot.bond_parameter
    angle_parameter = parameter_snapshot.angle_parameter
    bond_terms = tuple(
        _bond_term(
            item.identity,
            item.parameter_id,
            coordinates,
            equilibrium_length=bond_parameter.equilibrium_length_angstrom,
            force_constant=(
                bond_parameter.force_constant_kj_mol_angstrom2
            ),
        )
        for item in assignment.bond_assignments
    )
    angle_terms = tuple(
        _angle_term(
            item.identity,
            item.parameter_id,
            coordinates,
            equilibrium_angle=angle_parameter.equilibrium_angle_radian,
            force_constant=(
                angle_parameter.force_constant_kj_mol_radian2
            ),
        )
        for item in assignment.angle_assignments
    )
    bond_energy = _finite_fsum(
        (term.energy_kj_mol for term in bond_terms),
        location="bond_energy_total",
    )
    angle_energy = _finite_fsum(
        (term.energy_kj_mol for term in angle_terms),
        location="angle_energy_total",
    )
    total_energy = _finite_fsum(
        (bond_energy, angle_energy),
        location="diagnostic_energy_total",
    )
    forces = _aggregate_forces(bond_terms, angle_terms)
    return _DerivedHarmonicDiagnostic(
        assignment_report=assignment,
        input_snapshot_sha256=hashlib.sha256(system_bytes).hexdigest(),
        parameter_artifact_bytes_sha256=(
            hashlib.sha256(parameter_bytes).hexdigest()
        ),
        bond_terms=bond_terms,
        angle_terms=angle_terms,
        bond_energy_kj_mol=bond_energy,
        angle_energy_kj_mol=angle_energy,
        total_energy_kj_mol=total_energy,
        atom_forces_kj_mol_angstrom=forces,
    )


def _diagnostic_blockers(
    assignment: ExactMethaneBondAngleParameterAssignmentReport,
) -> tuple[str, ...]:
    parameter_form_id = assignment.parameter_set.functional_form_id
    form_blockers = (
        ("parameter_functional_form_not_embedded_in_parameter_set_v1",)
        if (
            type(parameter_form_id) is not str
            or parameter_form_id
            != _FROZEN_EXACT_METHANE_HARMONIC_FUNCTIONAL_FORM_ID
        )
        else ()
    )
    return tuple(
        dict.fromkeys(
            (
                *assignment.blockers,
                "diagnostic_only_not_runtime_energy",
                *form_blockers,
                "parameter_artifact_not_scientifically_validated",
                "global_parameter_coverage_incomplete",
                "nonbonded_terms_not_evaluated",
                "virial_not_assessed",
                "runtime_energy_evaluation_not_authorized",
                "runtime_force_evaluation_not_authorized",
                "minimization_not_authorized",
                "simulation_not_authorized",
                "claim_not_authorized",
            )
        )
    )


@dataclass(frozen=True, init=False, slots=True)
class ExactMethaneHarmonicDiagnosticReport:
    """Factory-only immutable diagnostic result with no runtime authority."""

    _system_snapshot_bytes: bytes = field(repr=False)
    _parameter_snapshot_bytes: bytes = field(repr=False)

    def __init__(
        self,
        system: AllAtomSystem,
        parameter_set: ExactMethaneBondAngleParameterSet,
    ) -> None:
        system_bytes, parameter_bytes = _snapshot_inputs(system, parameter_set)
        _derive_diagnostic_from_snapshots(system_bytes, parameter_bytes)
        object.__setattr__(self, "_system_snapshot_bytes", system_bytes)
        object.__setattr__(self, "_parameter_snapshot_bytes", parameter_bytes)

    def _derive(self) -> _DerivedHarmonicDiagnostic:
        return _derive_diagnostic_from_snapshots(
            self._system_snapshot_bytes,
            self._parameter_snapshot_bytes,
        )

    @property
    def assignment_report(self) -> ExactMethaneBondAngleParameterAssignmentReport:
        return ExactMethaneHarmonicDiagnosticReport._derive(
            self
        ).assignment_report

    @property
    def input_snapshot_sha256(self) -> str:
        return ExactMethaneHarmonicDiagnosticReport._derive(
            self
        ).input_snapshot_sha256

    @property
    def parameter_artifact_bytes_sha256(self) -> str:
        return ExactMethaneHarmonicDiagnosticReport._derive(
            self
        ).parameter_artifact_bytes_sha256

    @property
    def bond_terms(self) -> tuple[HarmonicBondDiagnosticTerm, ...]:
        return ExactMethaneHarmonicDiagnosticReport._derive(self).bond_terms

    @property
    def angle_terms(self) -> tuple[HarmonicAngleDiagnosticTerm, ...]:
        return ExactMethaneHarmonicDiagnosticReport._derive(self).angle_terms

    @property
    def bond_energy_kj_mol(self) -> float:
        return ExactMethaneHarmonicDiagnosticReport._derive(
            self
        ).bond_energy_kj_mol

    @property
    def angle_energy_kj_mol(self) -> float:
        return ExactMethaneHarmonicDiagnosticReport._derive(
            self
        ).angle_energy_kj_mol

    @property
    def total_energy_kj_mol(self) -> float:
        return ExactMethaneHarmonicDiagnosticReport._derive(
            self
        ).total_energy_kj_mol

    @property
    def atom_forces_kj_mol_angstrom(self) -> tuple[Vector3, ...]:
        return ExactMethaneHarmonicDiagnosticReport._derive(
            self
        ).atom_forces_kj_mol_angstrom

    @property
    def diagnostic_evaluation_performed(self) -> bool:
        return True

    @property
    def physics_supported(self) -> bool:
        return False

    @property
    def scientific_validity_green(self) -> bool:
        return False

    @property
    def parameterability_assessed(self) -> bool:
        return False

    @property
    def parameterizable(self) -> bool:
        return False

    @property
    def global_parameter_coverage_complete(self) -> bool:
        return False

    @property
    def preparation_ready(self) -> bool:
        return False

    @property
    def runtime_eligible(self) -> bool:
        return False

    @property
    def execution_authorized(self) -> bool:
        return False

    @property
    def energy_evaluation_authorized(self) -> bool:
        return False

    @property
    def force_evaluation_authorized(self) -> bool:
        return False

    @property
    def minimization_authorized(self) -> bool:
        return False

    @property
    def simulation_ready(self) -> bool:
        return False

    @property
    def claim_safe(self) -> bool:
        return False

    @property
    def blockers(self) -> tuple[str, ...]:
        derived = ExactMethaneHarmonicDiagnosticReport._derive(self)
        return _diagnostic_blockers(derived.assignment_report)

    def forces_tensor(self) -> torch.Tensor:
        """Return a detached copy; the report itself stores immutable tuples."""

        derived = ExactMethaneHarmonicDiagnosticReport._derive(self)
        return torch.tensor(
            [derived.atom_forces_kj_mol_angstrom],
            dtype=torch.float64,
            device="cpu",
        )

    def _core_dict(self) -> dict[str, Any]:
        derived = ExactMethaneHarmonicDiagnosticReport._derive(self)
        assignment = derived.assignment_report
        parameter_set = assignment.parameter_set
        return {
            "schema_id": _FROZEN_EXACT_METHANE_HARMONIC_DIAGNOSTIC_SCHEMA_ID,
            "schema_version": (
                _FROZEN_EXACT_METHANE_HARMONIC_DIAGNOSTIC_SCHEMA_VERSION
            ),
            "claim_scope": (
                _FROZEN_EXACT_METHANE_HARMONIC_DIAGNOSTIC_CLAIM_SCOPE
            ),
            "functional_form_id": (
                _FROZEN_EXACT_METHANE_HARMONIC_FUNCTIONAL_FORM_ID
            ),
            "singularity_policy_id": (
                _FROZEN_EXACT_METHANE_HARMONIC_SINGULARITY_POLICY_ID
            ),
            "force_definition": _FROZEN_DIAGNOSTIC_FORCE_DEFINITION,
            "energy_convention": "E(q)=0.5*k*(q-q0)^2",
            "coordinate_unit": "angstrom",
            "angle_unit": "radian",
            "energy_unit": "kilojoule_per_mole",
            "force_unit": "kilojoule_per_mole_per_angstrom",
            "numeric_encoding": "ieee754_binary64_big_endian_hex",
            "input_snapshot_sha256": derived.input_snapshot_sha256,
            "canonical_topology_sha256": (
                assignment.inventory_report.canonical_topology_sha256
            ),
            "inventory_report_sha256": (
                assignment.inventory_report.report_sha256
            ),
            "parameter_payload_sha256": parameter_set.parameter_payload_sha256,
            "parameter_set_sha256": parameter_set.parameter_set_sha256,
            "parameter_artifact_bytes_sha256": (
                derived.parameter_artifact_bytes_sha256
            ),
            "parameter_assignment_sha256": (
                assignment.parameter_assignment_sha256
            ),
            "parameter_assignment_report_sha256": assignment.report_sha256,
            "parameter_derivation_status": parameter_set.derivation_status,
            "parameter_artifact_purpose": parameter_set.artifact_purpose,
            "parameter_artifact_schema_version": (
                parameter_set.artifact_schema_version
            ),
            "parameter_functional_form_id": parameter_set.functional_form_id,
            "functional_form_binding_status": (
                "parameter_payload_bound_match"
                if (
                    type(parameter_set.functional_form_id) is str
                    and parameter_set.functional_form_id
                    == _FROZEN_EXACT_METHANE_HARMONIC_FUNCTIONAL_FORM_ID
                )
                else "diagnostic_owned_legacy_parameter_schema_1_0"
            ),
            "diagnostic_status": "diagnostic_evaluated",
            "diagnostic_evaluation_performed": True,
            "bond_term_count": len(derived.bond_terms),
            "angle_term_count": len(derived.angle_terms),
            "bond_terms": [
                HarmonicBondDiagnosticTerm.to_dict(term)
                for term in derived.bond_terms
            ],
            "angle_terms": [
                HarmonicAngleDiagnosticTerm.to_dict(term)
                for term in derived.angle_terms
            ],
            "bond_energy_ieee754_binary64_be": _binary64_hex(
                derived.bond_energy_kj_mol,
                location="bond_energy_total",
            ),
            "angle_energy_ieee754_binary64_be": _binary64_hex(
                derived.angle_energy_kj_mol,
                location="angle_energy_total",
            ),
            "total_energy_ieee754_binary64_be": _binary64_hex(
                derived.total_energy_kj_mol,
                location="diagnostic_energy_total",
            ),
            "atom_forces_ieee754_binary64_be": [
                _vector_dict(force, location=f"atom_forces[{index}]")
                for index, force in enumerate(
                    derived.atom_forces_kj_mol_angstrom
                )
            ],
            "virial_status": "not_assessed",
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
            "minimization_authorized": False,
            "simulation_ready": False,
            "claim_safe": False,
            "blockers": list(_diagnostic_blockers(assignment)),
        }

    @property
    def report_sha256(self) -> str:
        return _sha256_document(
            ExactMethaneHarmonicDiagnosticReport._core_dict(self)
        )

    def to_dict(self) -> dict[str, Any]:
        payload = ExactMethaneHarmonicDiagnosticReport._core_dict(self)
        payload["report_sha256"] = _sha256_document(payload)
        return payload

    def matches(
        self,
        system: AllAtomSystem,
        parameter_set: ExactMethaneBondAngleParameterSet,
    ) -> bool:
        """Recompute both snapshots and assignment before comparing reports."""

        recomputed = analyze_exact_methane_harmonic_diagnostic(
            system,
            parameter_set,
        )
        return ExactMethaneHarmonicDiagnosticReport.to_dict(
            self
        ) == ExactMethaneHarmonicDiagnosticReport.to_dict(recomputed)


def analyze_exact_methane_harmonic_diagnostic(
    system: AllAtomSystem,
    parameter_set: ExactMethaneBondAngleParameterSet,
) -> ExactMethaneHarmonicDiagnosticReport:
    """Evaluate the scoped diagnostic without granting any runtime authority."""

    return ExactMethaneHarmonicDiagnosticReport(system, parameter_set)


__all__ = [
    "DIAGNOSTIC_FORCE_DEFINITION",
    "EXACT_METHANE_HARMONIC_DIAGNOSTIC_CLAIM_SCOPE",
    "EXACT_METHANE_HARMONIC_DIAGNOSTIC_SCHEMA_ID",
    "EXACT_METHANE_HARMONIC_DIAGNOSTIC_SCHEMA_VERSION",
    "EXACT_METHANE_HARMONIC_FUNCTIONAL_FORM_ID",
    "EXACT_METHANE_HARMONIC_SINGULARITY_POLICY_ID",
    "MIN_DIAGNOSTIC_ANGLE_SINE",
    "MIN_DIAGNOSTIC_BOND_LENGTH_ANGSTROM",
    "ExactMethaneHarmonicDiagnosticError",
    "ExactMethaneHarmonicDiagnosticReport",
    "HarmonicAngleDiagnosticTerm",
    "HarmonicBondDiagnosticTerm",
    "analyze_exact_methane_harmonic_diagnostic",
]
