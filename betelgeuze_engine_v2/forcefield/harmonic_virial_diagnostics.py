"""Diagnostic-only exact-methane nonperiodic bonded virial mechanics.

The report in this module is intentionally narrower than a runtime virial,
stress, or pressure implementation.  It recomputes four C-H bond and six
H-C-H angle term virials from canonical system and form-bound parameter
snapshots.  No result authorizes energy, force, virial, minimization,
simulation, scientific-validity, or product claims.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
import struct
from typing import Any, Iterable

import torch

from betelgeuze_engine_v2.forcefield.harmonic_diagnostics import (
    ExactMethaneHarmonicDiagnosticError,
    _derive_diagnostic_from_snapshots as _derive_harmonic_from_snapshots,
    _snapshot_inputs as _snapshot_harmonic_inputs,
)
from betelgeuze_engine_v2.forcefield.parameters import (
    ExactMethaneBondAngleParameterAssignmentReport,
    ExactMethaneBondAngleParameterSet,
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


_FROZEN_DIAGNOSTIC_SCHEMA_VERSION = "1.0.0"
_FROZEN_DIAGNOSTIC_SCHEMA_ID = (
    "betelgeuze.exact_methane_harmonic_virial_diagnostic/"
    f"{_FROZEN_DIAGNOSTIC_SCHEMA_VERSION}"
)
_FROZEN_VIRIAL_CONVENTION_ID = (
    "nonperiodic_force_outer_displacement_virial/1.0.0"
)
_FROZEN_DIAGNOSTIC_CLAIM_SCOPE = (
    "nonphysical_exact_methane_nonperiodic_bonded_virial_diagnostic_only"
)
_FROZEN_VIRIAL_DEFINITION = (
    "W[a,b]=sum_i(F_i[a]*(r_i[b]-r_anchor[b]))=-dE/d_affine_strain[a,b]"
)

# Public names are compatibility aliases.  Serialized behavior below uses the
# import-time literals so monkeypatching a convenience export cannot redefine
# an already-versioned report contract.
EXACT_METHANE_HARMONIC_VIRIAL_DIAGNOSTIC_SCHEMA_VERSION = (
    _FROZEN_DIAGNOSTIC_SCHEMA_VERSION
)
EXACT_METHANE_HARMONIC_VIRIAL_DIAGNOSTIC_SCHEMA_ID = (
    _FROZEN_DIAGNOSTIC_SCHEMA_ID
)
EXACT_METHANE_HARMONIC_VIRIAL_CONVENTION_ID = _FROZEN_VIRIAL_CONVENTION_ID
EXACT_METHANE_HARMONIC_VIRIAL_DIAGNOSTIC_CLAIM_SCOPE = (
    _FROZEN_DIAGNOSTIC_CLAIM_SCOPE
)
DIAGNOSTIC_VIRIAL_DEFINITION = _FROZEN_VIRIAL_DEFINITION

_VECTOR_WIDTH = 3
_EXPECTED_ATOM_COUNT = 5
_EXPECTED_BOND_TERM_COUNT = 4
_EXPECTED_ANGLE_TERM_COUNT = 6
_FROZEN_PARAMETER_SCHEMA_VERSION = "1.1.0"
_FROZEN_LEGACY_PARAMETER_SCHEMA_VERSION = "1.0.0"
_FROZEN_FUNCTIONAL_FORM_ID = (
    "harmonic_half_k_delta_squared_bond_angle/1.0.0"
)


class ExactMethaneHarmonicVirialDiagnosticError(ValueError):
    """Fail-closed virial diagnostic error with a stable code."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.blockers = (f"harmonic_virial_diagnostic_{code}",)
        super().__init__(message)


def _fail(code: str, message: str) -> None:
    raise ExactMethaneHarmonicVirialDiagnosticError(code, message)


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
    except (TypeError, ValueError) as exc:  # pragma: no cover - typed rows guard
        _fail("serialization_failed", f"virial serialization failed: {exc}")


def _sha256_document(document: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json_bytes(document)).hexdigest()


Vector3 = tuple[float, float, float]
Matrix3 = tuple[Vector3, Vector3, Vector3]


def _vector(values: Iterable[float], *, location: str) -> Vector3:
    result = tuple(
        _canonical_float(value, location=f"{location}[{index}]")
        for index, value in enumerate(values)
    )
    if len(result) != _VECTOR_WIDTH:
        _fail("invalid_vector", f"{location} must contain three values")
    return result  # type: ignore[return-value]


def _matrix(rows: Iterable[Iterable[float]], *, location: str) -> Matrix3:
    result = tuple(
        _vector(row, location=f"{location}[{index}]")
        for index, row in enumerate(rows)
    )
    if len(result) != _VECTOR_WIDTH:
        _fail("invalid_matrix", f"{location} must contain three rows")
    return result  # type: ignore[return-value]


def _subtract(left: Vector3, right: Vector3, *, location: str) -> Vector3:
    return _vector(
        (left[index] - right[index] for index in range(_VECTOR_WIDTH)),
        location=location,
    )


def _outer(force: Vector3, displacement: Vector3, *, location: str) -> Matrix3:
    return _matrix(
        (
            (
                _canonical_float(
                    force[force_axis] * displacement[displacement_axis],
                    location=(
                        f"{location}[{force_axis}]"
                        f"[{displacement_axis}]"
                    ),
                )
                for displacement_axis in range(_VECTOR_WIDTH)
            )
            for force_axis in range(_VECTOR_WIDTH)
        ),
        location=location,
    )


def _sum_matrices(matrices: Iterable[Matrix3], *, location: str) -> Matrix3:
    materialized = tuple(matrices)
    return _matrix(
        (
            (
                _finite_fsum(
                    (matrix[row][column] for matrix in materialized),
                    location=f"{location}[{row}][{column}]",
                )
                for column in range(_VECTOR_WIDTH)
            )
            for row in range(_VECTOR_WIDTH)
        ),
        location=location,
    )


def _matrix_dict(matrix: Matrix3, *, location: str) -> list[list[str]]:
    return [
        [
            _binary64_hex(
                matrix[row][column],
                location=f"{location}[{row}][{column}]",
            )
            for column in range(_VECTOR_WIDTH)
        ]
        for row in range(_VECTOR_WIDTH)
    ]


def _validated_bond_identity(
    identity: CanonicalBondIdentity,
) -> CanonicalBondIdentity:
    if type(identity) is not CanonicalBondIdentity:
        raise TypeError("identity must be a CanonicalBondIdentity")
    return CanonicalBondIdentity(identity.atom_i, identity.atom_j)


def _validated_angle_identity(
    identity: CanonicalAngleIdentity,
) -> CanonicalAngleIdentity:
    if type(identity) is not CanonicalAngleIdentity:
        raise TypeError("identity must be a CanonicalAngleIdentity")
    return CanonicalAngleIdentity(
        identity.outer_atom_i,
        identity.center_atom,
        identity.outer_atom_k,
    )


@dataclass(frozen=True, slots=True)
class HarmonicBondVirialDiagnosticTerm:
    identity: CanonicalBondIdentity
    parameter_id: str
    anchor_atom: int
    virial_kj_mol: Matrix3

    def to_dict(self) -> dict[str, Any]:
        identity = _validated_bond_identity(self.identity)
        if type(self.parameter_id) is not str:
            raise TypeError("parameter_id must be a string")
        if type(self.anchor_atom) is not int or self.anchor_atom != identity.atom_j:
            _fail(
                "invalid_bond_anchor",
                "bond virial anchor must be canonical atom_j",
            )
        virial = _matrix(self.virial_kj_mol, location="bond_term.virial")
        return {
            **CanonicalBondIdentity.to_dict(identity),
            "parameter_id": self.parameter_id,
            "anchor_atom": self.anchor_atom,
            "anchor_role": "canonical_atom_j",
            "virial_tensor_ieee754_binary64_be": _matrix_dict(
                virial,
                location="bond_term.virial",
            ),
        }


@dataclass(frozen=True, slots=True)
class HarmonicAngleVirialDiagnosticTerm:
    identity: CanonicalAngleIdentity
    parameter_id: str
    anchor_atom: int
    virial_kj_mol: Matrix3

    def to_dict(self) -> dict[str, Any]:
        identity = _validated_angle_identity(self.identity)
        if type(self.parameter_id) is not str:
            raise TypeError("parameter_id must be a string")
        if (
            type(self.anchor_atom) is not int
            or self.anchor_atom != identity.center_atom
        ):
            _fail(
                "invalid_angle_anchor",
                "angle virial anchor must be the center atom",
            )
        virial = _matrix(self.virial_kj_mol, location="angle_term.virial")
        return {
            **CanonicalAngleIdentity.to_dict(identity),
            "parameter_id": self.parameter_id,
            "anchor_atom": self.anchor_atom,
            "anchor_role": "center_atom",
            "virial_tensor_ieee754_binary64_be": _matrix_dict(
                virial,
                location="angle_term.virial",
            ),
        }


def _require_form_bound_parameter_set(
    parameter_set: ExactMethaneBondAngleParameterSet,
) -> None:
    try:
        schema_version = parameter_set.artifact_schema_version
        functional_form_id = parameter_set.functional_form_id
    except AttributeError as exc:
        _fail("parameter_snapshot_failed", f"invalid parameter state: {exc}")
    if type(schema_version) is not str:
        _fail(
            "unsupported_parameter_schema",
            "parameter artifact schema version must be an exact string",
        )
    if schema_version == _FROZEN_LEGACY_PARAMETER_SCHEMA_VERSION:
        _fail(
            "legacy_parameter_schema_not_supported",
            "virial diagnostics require form-bound parameter schema 1.1",
        )
    if schema_version != _FROZEN_PARAMETER_SCHEMA_VERSION:
        _fail(
            "unsupported_parameter_schema",
            "virial diagnostics require parameter schema 1.1",
        )
    if (
        type(functional_form_id) is not str
        or functional_form_id != _FROZEN_FUNCTIONAL_FORM_ID
    ):
        _fail(
            "functional_form_mismatch",
            "parameter schema 1.1 must bind the fixed harmonic form",
        )


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
    _require_form_bound_parameter_set(parameter_set)
    try:
        system_bytes, parameter_bytes = _snapshot_harmonic_inputs(
            system,
            parameter_set,
        )
    except ExactMethaneHarmonicDiagnosticError as exc:
        _fail(exc.code, f"underlying harmonic snapshot failed: {exc}")
    except (
        TypeError,
        ValueError,
        OverflowError,
        RuntimeError,
        RecursionError,
    ) as exc:
        _fail(
            "snapshot_recomputation_failed",
            f"underlying harmonic snapshot failed: {exc}",
        )
    _derive_virial_from_snapshots(system_bytes, parameter_bytes)
    return system_bytes, parameter_bytes


def _coordinates(system: AllAtomSystem) -> tuple[Vector3, ...]:
    coordinates = tuple(
        _vector(row, location=f"coordinates[0][{atom_index}]")
        for atom_index, row in enumerate(system.coordinates[0].tolist())
    )
    if len(coordinates) != _EXPECTED_ATOM_COUNT:
        _fail(
            "coordinate_shape_not_exact_methane",
            "coordinates must contain exactly five atoms",
        )
    return coordinates


def _bond_virial_term(
    term: Any,
    coordinates: tuple[Vector3, ...],
) -> HarmonicBondVirialDiagnosticTerm:
    identity = _validated_bond_identity(term.identity)
    anchor = identity.atom_j
    displacement_i = _subtract(
        coordinates[identity.atom_i],
        coordinates[anchor],
        location="bond.displacement_i",
    )
    displacement_j = _subtract(
        coordinates[identity.atom_j],
        coordinates[anchor],
        location="bond.displacement_j",
    )
    force_i = _vector(
        term.force_on_atom_i_kj_mol_angstrom,
        location="bond.force_i",
    )
    force_j = _vector(
        term.force_on_atom_j_kj_mol_angstrom,
        location="bond.force_j",
    )
    virial = _sum_matrices(
        (
            _outer(force_i, displacement_i, location="bond.outer_i"),
            _outer(force_j, displacement_j, location="bond.outer_j"),
        ),
        location="bond.virial",
    )
    return HarmonicBondVirialDiagnosticTerm(
        identity=identity,
        parameter_id=term.parameter_id,
        anchor_atom=anchor,
        virial_kj_mol=virial,
    )


def _angle_virial_term(
    term: Any,
    coordinates: tuple[Vector3, ...],
) -> HarmonicAngleVirialDiagnosticTerm:
    identity = _validated_angle_identity(term.identity)
    anchor = identity.center_atom
    atom_indices = (
        identity.outer_atom_i,
        identity.center_atom,
        identity.outer_atom_k,
    )
    forces = (
        _vector(
            term.force_on_outer_i_kj_mol_angstrom,
            location="angle.force_outer_i",
        ),
        _vector(
            term.force_on_center_kj_mol_angstrom,
            location="angle.force_center",
        ),
        _vector(
            term.force_on_outer_k_kj_mol_angstrom,
            location="angle.force_outer_k",
        ),
    )
    contributions = tuple(
        _outer(
            force,
            _subtract(
                coordinates[atom_index],
                coordinates[anchor],
                location=f"angle.displacement[{atom_index}]",
            ),
            location=f"angle.outer[{atom_index}]",
        )
        for atom_index, force in zip(atom_indices, forces, strict=True)
    )
    return HarmonicAngleVirialDiagnosticTerm(
        identity=identity,
        parameter_id=term.parameter_id,
        anchor_atom=anchor,
        virial_kj_mol=_sum_matrices(
            contributions,
            location="angle.virial",
        ),
    )


@dataclass(frozen=True, slots=True)
class _DerivedHarmonicVirialDiagnostic:
    assignment_report: ExactMethaneBondAngleParameterAssignmentReport
    input_snapshot_sha256: str
    parameter_artifact_bytes_sha256: str
    bond_terms: tuple[HarmonicBondVirialDiagnosticTerm, ...]
    angle_terms: tuple[HarmonicAngleVirialDiagnosticTerm, ...]
    bond_virial_kj_mol: Matrix3
    angle_virial_kj_mol: Matrix3
    total_virial_kj_mol: Matrix3
    total_virial_trace_kj_mol: float


def _derive_virial_from_snapshots(
    system_bytes: bytes,
    parameter_bytes: bytes,
) -> _DerivedHarmonicVirialDiagnostic:
    if type(system_bytes) is not bytes or type(parameter_bytes) is not bytes:
        _fail(
            "snapshot_recomputation_failed",
            "virial diagnostic snapshots must remain immutable byte strings",
        )
    try:
        system = deserialize_all_atom_system(system_bytes)
        parameter_set = deserialize_exact_methane_bond_angle_parameter_set(
            parameter_bytes
        )
        system_is_canonical = serialize_all_atom_system(system) == system_bytes
        parameter_is_canonical = (
            serialize_exact_methane_bond_angle_parameter_set(parameter_set)
            == parameter_bytes
        )
    except (
        TypeError,
        ValueError,
        OverflowError,
        RuntimeError,
        RecursionError,
    ) as exc:
        _fail(
            "snapshot_recomputation_failed",
            f"virial snapshot recomputation failed: {exc}",
        )
    if not system_is_canonical or not parameter_is_canonical:
        _fail(
            "snapshot_recomputation_failed",
            "virial diagnostic snapshots must remain byte-canonical",
        )
    _require_form_bound_parameter_set(parameter_set)
    try:
        harmonic = _derive_harmonic_from_snapshots(
            system_bytes,
            parameter_bytes,
        )
    except ExactMethaneHarmonicDiagnosticError as exc:
        _fail(exc.code, f"underlying harmonic diagnostic failed: {exc}")
    except (
        TypeError,
        ValueError,
        OverflowError,
        RuntimeError,
        RecursionError,
    ) as exc:
        _fail(
            "snapshot_recomputation_failed",
            f"underlying harmonic diagnostic failed: {exc}",
        )
    if (
        len(harmonic.bond_terms) != _EXPECTED_BOND_TERM_COUNT
        or len(harmonic.angle_terms) != _EXPECTED_ANGLE_TERM_COUNT
    ):
        _fail(
            "term_set_not_exact",
            "virial diagnostics require exactly four bond and six angle terms",
        )
    coordinates = _coordinates(system)
    bond_terms = tuple(
        _bond_virial_term(term, coordinates) for term in harmonic.bond_terms
    )
    angle_terms = tuple(
        _angle_virial_term(term, coordinates) for term in harmonic.angle_terms
    )
    bond_virial = _sum_matrices(
        (term.virial_kj_mol for term in bond_terms),
        location="bond_virial_total",
    )
    angle_virial = _sum_matrices(
        (term.virial_kj_mol for term in angle_terms),
        location="angle_virial_total",
    )
    total_virial = _sum_matrices(
        (bond_virial, angle_virial),
        location="total_virial",
    )
    trace = _finite_fsum(
        (total_virial[index][index] for index in range(_VECTOR_WIDTH)),
        location="total_virial_trace",
    )
    return _DerivedHarmonicVirialDiagnostic(
        assignment_report=harmonic.assignment_report,
        input_snapshot_sha256=hashlib.sha256(system_bytes).hexdigest(),
        parameter_artifact_bytes_sha256=(
            hashlib.sha256(parameter_bytes).hexdigest()
        ),
        bond_terms=bond_terms,
        angle_terms=angle_terms,
        bond_virial_kj_mol=bond_virial,
        angle_virial_kj_mol=angle_virial,
        total_virial_kj_mol=total_virial,
        total_virial_trace_kj_mol=trace,
    )


def _diagnostic_blockers(
    assignment: ExactMethaneBondAngleParameterAssignmentReport,
) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            (
                *assignment.blockers,
                "diagnostic_only_not_runtime_virial",
                "parameter_artifact_not_scientifically_validated",
                "global_parameter_coverage_incomplete",
                "complete_virial_not_assessed",
                "nonbonded_terms_not_evaluated",
                "pressure_not_assessed",
                "stress_not_assessed",
                "volume_not_assessed",
                "periodic_terms_not_evaluated",
                "runtime_energy_evaluation_not_authorized",
                "runtime_force_evaluation_not_authorized",
                "runtime_virial_evaluation_not_authorized",
                "minimization_not_authorized",
                "simulation_not_authorized",
                "claim_not_authorized",
            )
        )
    )


@dataclass(frozen=True, init=False, slots=True)
class ExactMethaneHarmonicVirialDiagnosticReport:
    """Factory-only immutable diagnostic result with no runtime authority."""

    _system_snapshot_bytes: bytes = field(repr=False)
    _parameter_snapshot_bytes: bytes = field(repr=False)

    def __init__(
        self,
        system: AllAtomSystem,
        parameter_set: ExactMethaneBondAngleParameterSet,
    ) -> None:
        system_bytes, parameter_bytes = _snapshot_inputs(system, parameter_set)
        object.__setattr__(self, "_system_snapshot_bytes", system_bytes)
        object.__setattr__(self, "_parameter_snapshot_bytes", parameter_bytes)

    def _derive(self) -> _DerivedHarmonicVirialDiagnostic:
        return _derive_virial_from_snapshots(
            self._system_snapshot_bytes,
            self._parameter_snapshot_bytes,
        )

    @property
    def assignment_report(self) -> ExactMethaneBondAngleParameterAssignmentReport:
        return ExactMethaneHarmonicVirialDiagnosticReport._derive(
            self
        ).assignment_report

    @property
    def input_snapshot_sha256(self) -> str:
        return ExactMethaneHarmonicVirialDiagnosticReport._derive(
            self
        ).input_snapshot_sha256

    @property
    def parameter_artifact_bytes_sha256(self) -> str:
        return ExactMethaneHarmonicVirialDiagnosticReport._derive(
            self
        ).parameter_artifact_bytes_sha256

    @property
    def bond_terms(self) -> tuple[HarmonicBondVirialDiagnosticTerm, ...]:
        return ExactMethaneHarmonicVirialDiagnosticReport._derive(self).bond_terms

    @property
    def angle_terms(self) -> tuple[HarmonicAngleVirialDiagnosticTerm, ...]:
        return ExactMethaneHarmonicVirialDiagnosticReport._derive(self).angle_terms

    @property
    def bond_virial_kj_mol(self) -> Matrix3:
        return ExactMethaneHarmonicVirialDiagnosticReport._derive(
            self
        ).bond_virial_kj_mol

    @property
    def angle_virial_kj_mol(self) -> Matrix3:
        return ExactMethaneHarmonicVirialDiagnosticReport._derive(
            self
        ).angle_virial_kj_mol

    @property
    def total_virial_kj_mol(self) -> Matrix3:
        return ExactMethaneHarmonicVirialDiagnosticReport._derive(
            self
        ).total_virial_kj_mol

    @property
    def total_virial_trace_kj_mol(self) -> float:
        return ExactMethaneHarmonicVirialDiagnosticReport._derive(
            self
        ).total_virial_trace_kj_mol

    @property
    def diagnostic_evaluation_performed(self) -> bool:
        ExactMethaneHarmonicVirialDiagnosticReport._derive(self)
        return True

    @property
    def scoped_bonded_virial_assessed(self) -> bool:
        ExactMethaneHarmonicVirialDiagnosticReport._derive(self)
        return True

    @property
    def complete_virial_assessed(self) -> bool:
        ExactMethaneHarmonicVirialDiagnosticReport._derive(self)
        return False

    @property
    def physics_supported(self) -> bool:
        ExactMethaneHarmonicVirialDiagnosticReport._derive(self)
        return False

    @property
    def scientific_validity_green(self) -> bool:
        ExactMethaneHarmonicVirialDiagnosticReport._derive(self)
        return False

    @property
    def parameterability_assessed(self) -> bool:
        ExactMethaneHarmonicVirialDiagnosticReport._derive(self)
        return False

    @property
    def parameterizable(self) -> bool:
        ExactMethaneHarmonicVirialDiagnosticReport._derive(self)
        return False

    @property
    def global_parameter_coverage_complete(self) -> bool:
        ExactMethaneHarmonicVirialDiagnosticReport._derive(self)
        return False

    @property
    def preparation_ready(self) -> bool:
        ExactMethaneHarmonicVirialDiagnosticReport._derive(self)
        return False

    @property
    def runtime_eligible(self) -> bool:
        ExactMethaneHarmonicVirialDiagnosticReport._derive(self)
        return False

    @property
    def execution_authorized(self) -> bool:
        ExactMethaneHarmonicVirialDiagnosticReport._derive(self)
        return False

    @property
    def energy_evaluation_authorized(self) -> bool:
        ExactMethaneHarmonicVirialDiagnosticReport._derive(self)
        return False

    @property
    def force_evaluation_authorized(self) -> bool:
        ExactMethaneHarmonicVirialDiagnosticReport._derive(self)
        return False

    @property
    def virial_evaluation_authorized(self) -> bool:
        ExactMethaneHarmonicVirialDiagnosticReport._derive(self)
        return False

    @property
    def minimization_authorized(self) -> bool:
        ExactMethaneHarmonicVirialDiagnosticReport._derive(self)
        return False

    @property
    def simulation_ready(self) -> bool:
        ExactMethaneHarmonicVirialDiagnosticReport._derive(self)
        return False

    @property
    def claim_safe(self) -> bool:
        ExactMethaneHarmonicVirialDiagnosticReport._derive(self)
        return False

    @property
    def blockers(self) -> tuple[str, ...]:
        derived = ExactMethaneHarmonicVirialDiagnosticReport._derive(self)
        return _diagnostic_blockers(derived.assignment_report)

    def virial_tensor(self) -> torch.Tensor:
        """Return a detached CPU float64 copy of the diagnostic tensor."""

        derived = ExactMethaneHarmonicVirialDiagnosticReport._derive(self)
        return torch.tensor(
            derived.total_virial_kj_mol,
            dtype=torch.float64,
            device="cpu",
        )

    def _core_dict(self) -> dict[str, Any]:
        derived = ExactMethaneHarmonicVirialDiagnosticReport._derive(self)
        assignment = derived.assignment_report
        parameter_set = assignment.parameter_set
        return {
            "schema_id": _FROZEN_DIAGNOSTIC_SCHEMA_ID,
            "schema_version": _FROZEN_DIAGNOSTIC_SCHEMA_VERSION,
            "claim_scope": _FROZEN_DIAGNOSTIC_CLAIM_SCOPE,
            "virial_convention_id": _FROZEN_VIRIAL_CONVENTION_ID,
            "virial_definition": _FROZEN_VIRIAL_DEFINITION,
            "tensor_index_order": ["force_axis", "displacement_axis"],
            "bond_anchor_policy": "canonical_atom_j",
            "angle_anchor_policy": "center_atom",
            "functional_form_id": _FROZEN_FUNCTIONAL_FORM_ID,
            "coordinate_unit": "angstrom",
            "force_unit": "kilojoule_per_mole_per_angstrom",
            "virial_unit": "kilojoule_per_mole",
            "numeric_encoding": "ieee754_binary64_big_endian_hex",
            "input_snapshot_sha256": derived.input_snapshot_sha256,
            "canonical_topology_sha256": (
                assignment.inventory_report.canonical_topology_sha256
            ),
            "inventory_report_sha256": assignment.inventory_report.report_sha256,
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
            "parameter_artifact_schema_version": (
                parameter_set.artifact_schema_version
            ),
            "parameter_functional_form_id": parameter_set.functional_form_id,
            "functional_form_binding_status": "parameter_payload_bound_match",
            "diagnostic_status": "diagnostic_evaluated",
            "diagnostic_evaluation_performed": True,
            "virial_status": "scoped_nonperiodic_bonded_virial_evaluated",
            "scoped_bonded_virial_assessed": True,
            "complete_virial_assessed": False,
            "bond_term_count": len(derived.bond_terms),
            "angle_term_count": len(derived.angle_terms),
            "bond_terms": [
                HarmonicBondVirialDiagnosticTerm.to_dict(term)
                for term in derived.bond_terms
            ],
            "angle_terms": [
                HarmonicAngleVirialDiagnosticTerm.to_dict(term)
                for term in derived.angle_terms
            ],
            "bond_virial_tensor_ieee754_binary64_be": _matrix_dict(
                derived.bond_virial_kj_mol,
                location="bond_virial_total",
            ),
            "angle_virial_tensor_ieee754_binary64_be": _matrix_dict(
                derived.angle_virial_kj_mol,
                location="angle_virial_total",
            ),
            "total_virial_tensor_ieee754_binary64_be": _matrix_dict(
                derived.total_virial_kj_mol,
                location="total_virial",
            ),
            "total_virial_trace_ieee754_binary64_be": _binary64_hex(
                derived.total_virial_trace_kj_mol,
                location="total_virial_trace",
            ),
            "pressure_status": "not_assessed",
            "stress_status": "not_assessed",
            "volume_status": "not_assessed",
            "periodic_status": "not_assessed",
            "nonbonded_status": "not_assessed",
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
            "blockers": list(_diagnostic_blockers(assignment)),
        }

    @property
    def report_sha256(self) -> str:
        return _sha256_document(
            ExactMethaneHarmonicVirialDiagnosticReport._core_dict(self)
        )

    def to_dict(self) -> dict[str, Any]:
        payload = ExactMethaneHarmonicVirialDiagnosticReport._core_dict(self)
        payload["report_sha256"] = _sha256_document(payload)
        return payload

    def matches(
        self,
        system: AllAtomSystem,
        parameter_set: ExactMethaneBondAngleParameterSet,
    ) -> bool:
        recomputed = analyze_exact_methane_harmonic_virial_diagnostic(
            system,
            parameter_set,
        )
        return ExactMethaneHarmonicVirialDiagnosticReport.to_dict(
            self
        ) == ExactMethaneHarmonicVirialDiagnosticReport.to_dict(recomputed)


def analyze_exact_methane_harmonic_virial_diagnostic(
    system: AllAtomSystem,
    parameter_set: ExactMethaneBondAngleParameterSet,
) -> ExactMethaneHarmonicVirialDiagnosticReport:
    """Evaluate scoped bonded virials without granting runtime authority."""

    return ExactMethaneHarmonicVirialDiagnosticReport(system, parameter_set)


__all__ = [
    "DIAGNOSTIC_VIRIAL_DEFINITION",
    "EXACT_METHANE_HARMONIC_VIRIAL_CONVENTION_ID",
    "EXACT_METHANE_HARMONIC_VIRIAL_DIAGNOSTIC_CLAIM_SCOPE",
    "EXACT_METHANE_HARMONIC_VIRIAL_DIAGNOSTIC_SCHEMA_ID",
    "EXACT_METHANE_HARMONIC_VIRIAL_DIAGNOSTIC_SCHEMA_VERSION",
    "ExactMethaneHarmonicVirialDiagnosticError",
    "ExactMethaneHarmonicVirialDiagnosticReport",
    "HarmonicAngleVirialDiagnosticTerm",
    "HarmonicBondVirialDiagnosticTerm",
    "analyze_exact_methane_harmonic_virial_diagnostic",
]
