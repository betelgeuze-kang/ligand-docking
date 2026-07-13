"""Bounded nonphysical C1-C4 method-kernel reference potential.

This module adds a separate method-kernel overlay.  It does not reinterpret the
frozen v1 evaluation-method artifact, whose own energy-kernel status remains
``missing``.  The overlay compiles one exact, successful v1 binding report into
an immutable interaction plan and can evaluate fresh CPU float64 coordinates
repeatedly.  Its local reverse-mode VJPs provide force and complete cell-free
nonperiodic configurational virial values for contract verification only.

Nothing here is a scientific parameter set, a production runtime, a periodic
or pressure virial, an engine dispatch route, or product authority.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
import re
import struct
from typing import Any, Iterable, Mapping

import torch

from betelgeuze_engine_v2.forcefield.linear_alkane_method_binding import (
    LinearAlkaneC1C4EvaluationMethodBindingReport,
)


_FROZEN_PROTOCOL_SCHEMA_VERSION = "1.0.0"
_FROZEN_PROTOCOL_SCHEMA_ID = (
    "betelgeuze.linear_alkane_c1_c4_method_kernel_protocol/"
    f"{_FROZEN_PROTOCOL_SCHEMA_VERSION}"
)
_FROZEN_RESULT_SCHEMA_VERSION = "1.0.0"
_FROZEN_RESULT_SCHEMA_ID = (
    "betelgeuze.linear_alkane_c1_c4_reference_kernel_result/"
    f"{_FROZEN_RESULT_SCHEMA_VERSION}"
)
_FROZEN_POLICY_ID = (
    "exact_v1_binding_compiled_reusable_cpu_binary64_local_vjp_reference/1.0.0"
)
_FROZEN_ALGORITHM_ID = (
    "literal_energy_same_graph_local_reverse_vjp_and_anchor_virial/1.0.0"
)
_FROZEN_CLAIM_SCOPE = (
    "bounded_nonphysical_c1_c4_method_owned_cpu_reference_kernel_only"
)
_FROZEN_BASE_METHOD_PROTOCOL_SCHEMA_ID = (
    "betelgeuze.linear_alkane_c1_c4_evaluation_method_protocol/1.0.0"
)
_FROZEN_BASE_METHOD_PROTOCOL_SHA256 = (
    "7a8416632d83cab3e32ebbbdc43549d59b5a4efb472283d07f773ad66de461da"
)
_FROZEN_BASE_METHOD_SCHEMA_ID = (
    "betelgeuze.linear_alkane_c1_c4_evaluation_method/1.0.0"
)
_FROZEN_BINDING_SCHEMA_ID = (
    "betelgeuze.linear_alkane_c1_c4_evaluation_method_binding/1.0.0"
)
_FROZEN_BINDING_POLICY_ID = (
    "fresh_system_parameter_method_snapshots_input_envelope_assignment_and_"
    "geometry_domain_no_evaluation/1.0.0"
)
_FROZEN_ASSIGNMENT_SCHEMA_ID = (
    "betelgeuze.linear_alkane_c1_c4_parameter_assignment/1.0.0"
)
_FROZEN_PARAMETER_PROTOCOL_SHA256 = (
    "28219cd1492b31f3d151048e7ad9db297fe7a896d081b098e901f142f6d4602a"
)
_FROZEN_PARAMETER_SET_SCHEMA_ID = (
    "betelgeuze.linear_alkane_c1_c4_parameter_set/1.0.0"
)
_FROZEN_UNIT_SYSTEM_ID = (
    "betelgeuze.kilojoule_per_mole_angstrom_radian_elementary_charge/1.0.0"
)
_FROZEN_BINARY64_ENCODING_ID = "ieee754_binary64_big_endian_hex/1.0.0"
_FROZEN_COORDINATE_ENCODING_ID = (
    "shape_then_row_major_ieee754_binary64_big_endian_hex/1.0.0"
)
_FROZEN_FORCE_DEFINITION = "force_i_axis=-d_total_energy/d_coordinate_i_axis"
_FROZEN_VIRIAL_CONVENTION_ID = (
    "cell_free_nonperiodic_local_force_outer_anchor_displacement/1.0.0"
)
_FROZEN_VIRIAL_DEFINITION = (
    "W[a,b]=sum_terms,sum_local_atoms(F[a]*(r[b]-anchor[b]))="
    "-dE/d_epsilon[a,b] for r_prime=r@(I+epsilon).T"
)
_FROZEN_CLASS_ORDER = (
    "bond",
    "angle",
    "proper",
    "lennard_jones",
    "coulomb",
)
_FROZEN_MAXIMUM_ATOM_COUNT = 14
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")

LINEAR_ALKANE_METHOD_KERNEL_PROTOCOL_SCHEMA_VERSION = (
    _FROZEN_PROTOCOL_SCHEMA_VERSION
)
LINEAR_ALKANE_METHOD_KERNEL_PROTOCOL_SCHEMA_ID = _FROZEN_PROTOCOL_SCHEMA_ID
LINEAR_ALKANE_REFERENCE_KERNEL_RESULT_SCHEMA_VERSION = (
    _FROZEN_RESULT_SCHEMA_VERSION
)
LINEAR_ALKANE_REFERENCE_KERNEL_RESULT_SCHEMA_ID = _FROZEN_RESULT_SCHEMA_ID
LINEAR_ALKANE_METHOD_KERNEL_POLICY_ID = _FROZEN_POLICY_ID
LINEAR_ALKANE_METHOD_KERNEL_ALGORITHM_ID = _FROZEN_ALGORITHM_ID
LINEAR_ALKANE_METHOD_KERNEL_CLAIM_SCOPE = _FROZEN_CLAIM_SCOPE
LINEAR_ALKANE_REFERENCE_KERNEL_FORCE_DEFINITION = _FROZEN_FORCE_DEFINITION
LINEAR_ALKANE_REFERENCE_KERNEL_VIRIAL_DEFINITION = _FROZEN_VIRIAL_DEFINITION
LINEAR_ALKANE_REFERENCE_KERNEL_VIRIAL_CONVENTION_ID = (
    _FROZEN_VIRIAL_CONVENTION_ID
)


class LinearAlkaneReferenceKernelError(ValueError):
    """Fail-closed reference-kernel error carrying a stable code."""

    def __init__(self, code: str, message: str) -> None:
        if type(code) is not str or not code:
            raise TypeError("kernel error code must be an exact non-empty string")
        self.code = code
        self.blockers = (f"linear_alkane_reference_kernel_{code}",)
        super().__init__(message)


def _fail(code: str, message: str) -> None:
    raise LinearAlkaneReferenceKernelError(code, message)


def _canonical_json_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        _fail("serialization_failed", f"canonical JSON serialization failed: {exc}")


def _sha256_document(value: Any) -> str:
    return hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


def _require_sha256(name: str, value: Any) -> str:
    if type(value) is not str or _SHA256_PATTERN.fullmatch(value) is None:
        _fail("dependency_inconsistent", f"{name} must be a lowercase SHA-256")
    return value


def _finite(value: Any, *, location: str) -> float:
    if type(value) is not float or not math.isfinite(value):
        _fail("nonfinite_result", f"{location} must be a finite binary64 value")
    return value


def _reported(value: float, *, location: str) -> float:
    result = _finite(value, location=location)
    return 0.0 if result == 0.0 else result


def _binary64_hex(value: float, *, location: str) -> str:
    return struct.pack(">d", _reported(value, location=location)).hex()


def _binary64_from_hex(value: Any, *, location: str) -> float:
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{16}", value) is None:
        _fail("dependency_inconsistent", f"{location} is not binary64 hex")
    result = struct.unpack(">d", bytes.fromhex(value))[0]
    return _finite(result, location=location)


def _add(left: float, right: float, *, location: str) -> float:
    return _finite(left + right, location=location)


def _subtract(left: float, right: float, *, location: str) -> float:
    return _finite(left - right, location=location)


def _multiply(left: float, right: float, *, location: str) -> float:
    return _finite(left * right, location=location)


def _divide(numerator: float, denominator: float, *, location: str) -> float:
    try:
        result = numerator / denominator
    except ZeroDivisionError as exc:
        _fail("singular_geometry", f"{location} divided by zero: {exc}")
    return _finite(result, location=location)


def _finite_fsum(values: Iterable[float], *, location: str) -> float:
    try:
        result = math.fsum(values)
    except (OverflowError, ValueError) as exc:
        _fail("nonfinite_result", f"{location} fsum failed: {exc}")
    return _finite(result, location=location)


def _hypot(vector: "Vector3", *, location: str) -> float:
    try:
        result = math.hypot(vector[0], vector[1], vector[2])
    except (OverflowError, ValueError) as exc:
        _fail("nonfinite_result", f"{location} hypot failed: {exc}")
    return _finite(result, location=location)


def _cos(value: float, *, location: str) -> float:
    try:
        return _finite(math.cos(value), location=location)
    except (OverflowError, ValueError) as exc:
        _fail("nonfinite_result", f"{location} cosine failed: {exc}")


def _sin(value: float, *, location: str) -> float:
    try:
        return _finite(math.sin(value), location=location)
    except (OverflowError, ValueError) as exc:
        _fail("nonfinite_result", f"{location} sine failed: {exc}")


def _atan2(y_value: float, x_value: float, *, location: str) -> float:
    try:
        return _finite(math.atan2(y_value, x_value), location=location)
    except (OverflowError, ValueError) as exc:
        _fail("nonfinite_result", f"{location} atan2 failed: {exc}")


def _require_round_to_nearest_ties_to_even() -> None:
    half_ulp_above_one = math.ldexp(1.0, -53)
    half_ulp_below_one = math.ldexp(1.0, -54)
    if 1.0 + half_ulp_above_one != 1.0 or 1.0 - half_ulp_below_one != 1.0:
        _fail(
            "rounding_mode_incompatible",
            "reference kernel requires round-to-nearest ties-to-even",
        )


Vector3 = tuple[float, float, float]
Matrix3 = tuple[Vector3, Vector3, Vector3]
LocalForces = tuple[tuple[int, Vector3], ...]


def _vector(values: Iterable[float], *, location: str) -> Vector3:
    result = tuple(
        _finite(value, location=f"{location}[{index}]")
        for index, value in enumerate(values)
    )
    if len(result) != 3:
        _fail("dependency_inconsistent", f"{location} must have three components")
    return result  # type: ignore[return-value]


def _zero_vector() -> Vector3:
    return (0.0, 0.0, 0.0)


def _zero_matrix() -> Matrix3:
    return (_zero_vector(), _zero_vector(), _zero_vector())


def _difference(first: Vector3, second: Vector3, *, location: str) -> Vector3:
    """Return ``second - first`` with explicit component operations."""

    return _vector(
        (
            _subtract(
                second[index],
                first[index],
                location=f"{location}[{index}]",
            )
            for index in range(3)
        ),
        location=location,
    )


def _scale(scalar: float, vector: Vector3, *, location: str) -> Vector3:
    return _vector(
        (
            _multiply(scalar, value, location=f"{location}[{index}]")
            for index, value in enumerate(vector)
        ),
        location=location,
    )


def _negate(vector: Vector3, *, location: str) -> Vector3:
    return _scale(-1.0, vector, location=location)


def _sum_vectors(vectors: Iterable[Vector3], *, location: str) -> Vector3:
    rows = tuple(vectors)
    return _vector(
        (
            _finite_fsum(
                (row[axis] for row in rows),
                location=f"{location}[{axis}]",
            )
            for axis in range(3)
        ),
        location=location,
    )


def _unit(vector: Vector3, length: float, *, location: str) -> Vector3:
    return _vector(
        (
            _divide(value, length, location=f"{location}[{axis}]")
            for axis, value in enumerate(vector)
        ),
        location=location,
    )


def _dot(left: Vector3, right: Vector3, *, location: str) -> float:
    products = tuple(
        _multiply(left[axis], right[axis], location=f"{location}[{axis}]")
        for axis in range(3)
    )
    return _finite_fsum(products, location=location)


def _cross(left: Vector3, right: Vector3, *, location: str) -> Vector3:
    products = (
        (
            _multiply(left[1], right[2], location=f"{location}.x.left"),
            _multiply(left[2], right[1], location=f"{location}.x.right"),
        ),
        (
            _multiply(left[2], right[0], location=f"{location}.y.left"),
            _multiply(left[0], right[2], location=f"{location}.y.right"),
        ),
        (
            _multiply(left[0], right[1], location=f"{location}.z.left"),
            _multiply(left[1], right[0], location=f"{location}.z.right"),
        ),
    )
    return _vector(
        (
            _subtract(first, second, location=f"{location}[{axis}]")
            for axis, (first, second) in enumerate(products)
        ),
        location=location,
    )


def _sum_matrices(matrices: Iterable[Matrix3], *, location: str) -> Matrix3:
    rows = tuple(matrices)
    return tuple(
        _vector(
            (
                _finite_fsum(
                    (matrix[a][b] for matrix in rows),
                    location=f"{location}[{a},{b}]",
                )
                for b in range(3)
            ),
            location=f"{location}[{a}]",
        )
        for a in range(3)
    )  # type: ignore[return-value]


def _local_virial(
    local_forces: LocalForces,
    points: tuple[Vector3, ...],
    anchor_index: int,
    *,
    location: str,
) -> Matrix3:
    try:
        anchor = points[anchor_index]
    except IndexError:
        _fail("dependency_inconsistent", f"{location} anchor is outside coordinates")
    contributions: list[Matrix3] = []
    for row_index, (atom_index, force) in enumerate(local_forces):
        try:
            displacement = _difference(
                anchor,
                points[atom_index],
                location=f"{location}.displacement[{row_index}]",
            )
        except IndexError:
            _fail(
                "dependency_inconsistent",
                f"{location} local atom is outside coordinates",
            )
        contributions.append(
            tuple(
                _vector(
                    (
                        _multiply(
                            force[a],
                            displacement[b],
                            location=f"{location}.outer[{row_index},{a},{b}]",
                        )
                        for b in range(3)
                    ),
                    location=f"{location}.outer[{row_index},{a}]",
                )
                for a in range(3)
            )  # type: ignore[arg-type]
        )
    return _sum_matrices(contributions, location=location)


def _protocol_document() -> dict[str, Any]:
    return {
        "schema_id": _FROZEN_PROTOCOL_SCHEMA_ID,
        "schema_version": _FROZEN_PROTOCOL_SCHEMA_VERSION,
        "result_schema_id": _FROZEN_RESULT_SCHEMA_ID,
        "policy_id": _FROZEN_POLICY_ID,
        "algorithm_id": _FROZEN_ALGORITHM_ID,
        "claim_scope": _FROZEN_CLAIM_SCOPE,
        "ownership": {
            "base_v1_method_energy_kernel_status": "missing_unchanged",
            "overlay_method_kernel_status": "available_bounded_nonphysical",
            "production_runtime_kernel_status": "unavailable",
        },
        "dependencies": {
            "base_method_protocol_schema_id": (
                _FROZEN_BASE_METHOD_PROTOCOL_SCHEMA_ID
            ),
            "base_method_protocol_sha256": _FROZEN_BASE_METHOD_PROTOCOL_SHA256,
            "base_method_schema_id": _FROZEN_BASE_METHOD_SCHEMA_ID,
            "binding_schema_id": _FROZEN_BINDING_SCHEMA_ID,
            "binding_policy_id": _FROZEN_BINDING_POLICY_ID,
            "assignment_schema_id": _FROZEN_ASSIGNMENT_SCHEMA_ID,
            "parameter_protocol_sha256": _FROZEN_PARAMETER_PROTOCOL_SHA256,
            "parameter_set_schema_id": _FROZEN_PARAMETER_SET_SCHEMA_ID,
            "unit_system_id": _FROZEN_UNIT_SYSTEM_ID,
        },
        "compile_boundary": {
            "accepted_type": (
                "exact_LinearAlkaneC1C4EvaluationMethodBindingReport"
            ),
            "required_binding_status": "contract_fixture_method_bound",
            "required_geometry_status": (
                "passed_bounded_domain_check_no_evaluation"
            ),
            "raw_system_parameter_method_overload": "prohibited",
            "immutable_snapshot_replay": True,
        },
        "coordinate_boundary": {
            "shape": ["atom_count", 3],
            "dtype": "torch.float64",
            "device": "cpu",
            "layout": "torch.strided",
            "requires_grad": False,
            "alias_policy": "clone_contiguous_before_scalar_read",
            "coordinate_unit": "angstrom",
            "maximum_atom_count": _FROZEN_MAXIMUM_ATOM_COUNT,
            "cell": None,
            "periodic": False,
        },
        "energy": {
            "unit": "kilojoule_per_mole",
            "term_order": ["bond", "angle", "proper", "selected_pair"],
            "pair_components": ["lennard_jones", "coulomb"],
            "one_four_scaling": "apply_each_component_exactly_once",
            "total_accumulation": "flat_canonical_math_fsum",
        },
        "term_algorithms": {
            "common": [
                "difference=right_point-left_point_componentwise",
                "length=math.hypot(dx,dy,dz)",
                "dot=component_products_then_math.fsum_xyz",
                "cross=two_explicit_products_then_subtract_per_component",
                "all_forward_intermediates_reused_by_local_reverse_vjp",
            ],
            "bond": [
                "d=r_j-r_i;r=length(d);delta=r-r0",
                "energy=(0.5*k*delta)*delta",
                "dE_dr=k*delta",
                "F_i=(dE_dr/r)*d;F_j=-F_i",
            ],
            "angle": [
                "u=r_i-r_center;v=r_k-r_center",
                "normalized_sine=length(cross(u/length(u),v/length(v)))",
                "theta=atan2(length(cross(u,v)),dot(u,v))",
                "energy=(0.5*k*(theta-theta0))*(theta-theta0)",
                "c=dot(u_hat,v_hat);s=normalized_sine",
                "grad_u=(c*u_hat-v_hat)/(length(u)*s)",
                "grad_v=(c*v_hat-u_hat)/(length(v)*s)",
                "F_i=-dE_dtheta*grad_u;F_k=-dE_dtheta*grad_v",
                "F_center=-(F_i+F_k)",
            ],
            "proper": [
                "b1=r_j-r_i;b2=r_k-r_j;b3=r_l-r_k",
                "n1=cross(b1,b2);n2=cross(b2,b3)",
                "phi=atan2(dot(cross(n1,n2),b2/length(b2)),dot(n1,n2))",
                "component_energy=A*(1+cos(periodicity*phi-phase))",
                "component_dE_dphi=-A*periodicity*sin(periodicity*phi-phase)",
                "energy_and_dE_dphi=canonical_component_math.fsum",
                "grad_i=-length(b2)*n1/dot(n1,n1)",
                "grad_l=length(b2)*n2/dot(n2,n2)",
                "alpha=dot(b1,b2)/dot(b2,b2);beta=dot(b3,b2)/dot(b2,b2)",
                "grad_j=-(1+alpha)*grad_i+beta*grad_l",
                "grad_k=alpha*grad_i-(1+beta)*grad_l",
                "F_atom=-dE_dphi*grad_atom",
            ],
            "selected_pair": [
                "d=r_j-r_i;r=length(d);x=sigma/r",
                "s2=x*x;s4=s2*s2;s6=s4*s2;s12=s6*s6",
                "U_lj=(4*epsilon)*(s12-s6)",
                "U_q=(((coulomb_coefficient/relative_dielectric)*q_i)*q_j)/r",
                "dU_lj_dr=((4*epsilon)/r)*(6*s6-12*s12)",
                "dU_q_dr=(-U_q)/r",
                "one_four_scale_applied_once_to_each_energy_and_derivative",
                "full_nonbonded_has_no_scale_multiplication",
                "pair_energy=math.fsum(U_lj_applied,U_q_applied)",
                "pair_derivative=math.fsum(dU_lj_applied,dU_q_applied)",
                "F_i=(pair_derivative/r)*d;F_j=-F_i",
            ],
        },
        "force": {
            "unit": "kilojoule_per_mole_per_angstrom",
            "definition": _FROZEN_FORCE_DEFINITION,
            "algorithm": "same_forward_intermediates_local_reverse_mode_vjp",
            "atom_accumulation": "flat_canonical_term_math_fsum_per_axis",
            "caller_autograd_graph": "not_preserved",
        },
        "virial": {
            "unit": "kilojoule_per_mole",
            "convention_id": _FROZEN_VIRIAL_CONVENTION_ID,
            "definition": _FROZEN_VIRIAL_DEFINITION,
            "index_order": ["force_axis_a", "coordinate_axis_b"],
            "anchors": {
                "bond": "canonical_atom_j",
                "angle": "center_atom",
                "proper": "canonical_atom_j",
                "selected_pair": "canonical_atom_j",
            },
            "pressure_stress_volume_pbc_semantics": "not_defined",
        },
        "numeric_policy": {
            "encoding_id": _FROZEN_BINARY64_ENCODING_ID,
            "coordinate_encoding_id": _FROZEN_COORDINATE_ENCODING_ID,
            "rounding_mode": "round_to_nearest_ties_to_even_required",
            "finite_check": "every_primitive_reduction_input_and_output",
            "reported_negative_zero": "canonicalize_to_positive_zero",
            "clamp_softcore_epsilon": "prohibited",
            "partial_result_after_failure": "prohibited",
            "cross_platform_libm_bit_replay": "not_assessed",
        },
        "promotion": {
            "scientific_parameters": False,
            "scientifically_validated": False,
            "physics_supported": False,
            "runtime_eligible": False,
            "engine_dispatch_registered": False,
            "minimization_authorized": False,
            "simulation_ready": False,
            "claim_safe": False,
        },
    }


_FROZEN_PROTOCOL_DOCUMENT = _protocol_document()
_FROZEN_PROTOCOL_BYTES = _canonical_json_bytes(_FROZEN_PROTOCOL_DOCUMENT)
_FROZEN_PROTOCOL_SHA256 = hashlib.sha256(_FROZEN_PROTOCOL_BYTES).hexdigest()
LINEAR_ALKANE_METHOD_KERNEL_PROTOCOL_SHA256 = _FROZEN_PROTOCOL_SHA256


def linear_alkane_method_kernel_protocol_document() -> dict[str, Any]:
    """Return a detached copy of the frozen method-kernel protocol."""

    return json.loads(_FROZEN_PROTOCOL_BYTES.decode("ascii"))


def linear_alkane_method_kernel_protocol_bytes() -> bytes:
    """Return the canonical frozen method-kernel protocol bytes."""

    return bytes(_FROZEN_PROTOCOL_BYTES)


@dataclass(frozen=True, slots=True)
class _BondSpec:
    atom_i: int
    atom_j: int
    parameter_id: str
    equilibrium: float
    force_constant: float


@dataclass(frozen=True, slots=True)
class _AngleSpec:
    atom_i: int
    center: int
    atom_k: int
    parameter_id: str
    equilibrium: float
    force_constant: float


@dataclass(frozen=True, slots=True)
class _ProperSpec:
    atom_i: int
    atom_j: int
    atom_k: int
    atom_l: int
    parameter_id: str
    components: tuple[tuple[int, float, float], ...]


@dataclass(frozen=True, slots=True)
class _PairSpec:
    atom_i: int
    atom_j: int
    interaction_class: str
    shortest_graph_distance: int
    parameter_id: str
    sigma: float
    epsilon: float
    charge_i: float
    charge_j: float
    lj_scale: float | None
    coulomb_scale: float | None


@dataclass(frozen=True, slots=True)
class _CompiledSpec:
    atom_count: int
    minimum_distance: float
    minimum_angle_sine: float
    minimum_proper_sine: float
    effective_coulomb_coefficient: float
    bonds: tuple[_BondSpec, ...]
    angles: tuple[_AngleSpec, ...]
    propers: tuple[_ProperSpec, ...]
    pairs: tuple[_PairSpec, ...]
    binding_report_sha256: str
    binding_report_snapshot_sha256: str
    method_binding_sha256: str
    canonical_system_snapshot_sha256: str
    canonical_parameter_artifact_sha256: str
    canonical_method_artifact_sha256: str
    assignment_report_sha256: str
    parameter_assignment_sha256: str
    method_payload_sha256: str
    evaluation_method_sha256: str
    canonical_topology_sha256: str
    source_sha256: str
    component_id: str
    plan_sha256: str


@dataclass(frozen=True, slots=True)
class _FlatTerm:
    term_class: str
    identity: tuple[int, ...]
    energy: float
    local_forces: LocalForces
    virial: Matrix3


def _identity_document(term_class: str, identity: tuple[int, ...]) -> dict[str, int]:
    if term_class == "bond":
        names = ("atom_i", "atom_j")
    elif term_class == "angle":
        names = ("outer_atom_i", "center_atom", "outer_atom_k")
    elif term_class == "proper":
        names = ("atom_i", "atom_j", "atom_k", "atom_l")
    elif term_class in {"lennard_jones", "coulomb", "selected_pair"}:
        names = ("atom_i", "atom_j")
    else:
        _fail("dependency_inconsistent", f"unknown term class {term_class!r}")
    if len(names) != len(identity):
        _fail("dependency_inconsistent", "term identity width is inconsistent")
    return dict(zip(names, identity, strict=True))


def _vector_document(vector: Vector3, *, location: str) -> list[str]:
    return [
        _binary64_hex(value, location=f"{location}[{axis}]")
        for axis, value in enumerate(vector)
    ]


def _matrix_document(matrix: Matrix3, *, location: str) -> list[list[str]]:
    return [
        _vector_document(row, location=f"{location}[{axis}]")
        for axis, row in enumerate(matrix)
    ]


def _validate_stored_vector(vector: Any, *, location: str) -> Vector3:
    if type(vector) is not tuple or len(vector) != 3:
        raise TypeError(f"{location} must be an exact three-component tuple")
    return _vector(vector, location=location)


def _validate_stored_matrix(matrix: Any, *, location: str) -> Matrix3:
    if type(matrix) is not tuple or len(matrix) != 3:
        raise TypeError(f"{location} must be an exact 3x3 tuple matrix")
    for axis, row in enumerate(matrix):
        _validate_stored_vector(row, location=f"{location}[{axis}]")
    return matrix


@dataclass(frozen=True, slots=True)
class LinearAlkaneReferenceKernelTermResult:
    """One immutable energy term and its local VJP/virial contribution."""

    term_class: str
    identity: tuple[int, ...]
    parameter_id: str
    energy_kilojoule_per_mole: float
    local_forces: LocalForces
    virial_kilojoule_per_mole: Matrix3

    def __post_init__(self) -> None:
        if self.term_class not in _FROZEN_CLASS_ORDER:
            raise ValueError("kernel term class is unknown")
        if type(self.identity) is not tuple or not all(
            type(value) is int and value >= 0 for value in self.identity
        ):
            raise TypeError("kernel term identity must be an exact index tuple")
        _identity_document(self.term_class, self.identity)
        if type(self.parameter_id) is not str or not self.parameter_id:
            raise TypeError("kernel term parameter_id must be an exact string")
        _finite(self.energy_kilojoule_per_mole, location="term.energy")
        if type(self.local_forces) is not tuple or not self.local_forces:
            raise TypeError("kernel term local forces must be a non-empty tuple")
        seen: set[int] = set()
        for atom_index, vector in self.local_forces:
            if type(atom_index) is not int or atom_index < 0:
                raise TypeError("kernel local-force atom index is invalid")
            if atom_index in seen:
                raise ValueError("kernel local-force atom indices must be unique")
            seen.add(atom_index)
            _validate_stored_vector(
                vector,
                location=f"term.local_force[{atom_index}]",
            )
        _validate_stored_matrix(
            self.virial_kilojoule_per_mole,
            location="term.virial",
        )

    def to_dict(self) -> dict[str, Any]:
        self.__post_init__()
        return {
            "term_class": self.term_class,
            "identity": _identity_document(self.term_class, self.identity),
            "parameter_id": self.parameter_id,
            "energy_kilojoule_per_mole_binary64": _binary64_hex(
                self.energy_kilojoule_per_mole,
                location="term.energy",
            ),
            "local_forces_kilojoule_per_mole_per_angstrom_binary64": [
                {
                    "atom_index": atom_index,
                    "vector": _vector_document(
                        vector,
                        location=f"term.local_force[{atom_index}]",
                    ),
                }
                for atom_index, vector in self.local_forces
            ],
            "virial_kilojoule_per_mole_binary64": _matrix_document(
                self.virial_kilojoule_per_mole,
                location="term.virial",
            ),
        }


@dataclass(frozen=True, slots=True)
class LinearAlkaneReferenceKernelClassResult:
    """One canonical force-field class subtotal and decomposition."""

    term_class: str
    term_count: int
    energy_kilojoule_per_mole: float
    atom_forces: tuple[Vector3, ...]
    virial_kilojoule_per_mole: Matrix3

    def __post_init__(self) -> None:
        if self.term_class not in _FROZEN_CLASS_ORDER:
            raise ValueError("kernel class result name is unknown")
        if type(self.term_count) is not int or self.term_count < 0:
            raise TypeError("kernel class term count must be non-negative")
        _finite(self.energy_kilojoule_per_mole, location="class.energy")
        if type(self.atom_forces) is not tuple:
            raise TypeError("kernel class forces must be an exact tuple")
        for atom_index, vector in enumerate(self.atom_forces):
            _validate_stored_vector(
                vector,
                location=f"class.force[{atom_index}]",
            )
        _validate_stored_matrix(
            self.virial_kilojoule_per_mole,
            location="class.virial",
        )

    def to_dict(self) -> dict[str, Any]:
        self.__post_init__()
        return {
            "term_class": self.term_class,
            "term_count": self.term_count,
            "energy_kilojoule_per_mole_binary64": _binary64_hex(
                self.energy_kilojoule_per_mole,
                location="class.energy",
            ),
            "atom_forces_kilojoule_per_mole_per_angstrom_binary64": [
                _vector_document(vector, location=f"class.force[{index}]")
                for index, vector in enumerate(self.atom_forces)
            ],
            "virial_kilojoule_per_mole_binary64": _matrix_document(
                self.virial_kilojoule_per_mole,
                location="class.virial",
            ),
        }


def _aggregate_atom_forces(
    term_rows: Iterable[tuple[str, tuple[int, ...], LocalForces]],
    atom_count: int,
    *,
    location: str,
) -> tuple[Vector3, ...]:
    rows = tuple(term_rows)
    contributions: list[list[list[float]]] = [
        [[], [], []] for _ in range(atom_count)
    ]
    for _term_class, _identity, local_forces in rows:
        for atom_index, vector in local_forces:
            if not 0 <= atom_index < atom_count:
                _fail(
                    "dependency_inconsistent",
                    f"{location} term force index is outside atom range",
                )
            for axis in range(3):
                contributions[atom_index][axis].append(vector[axis])
    return tuple(
        _vector(
            (
                _finite_fsum(
                    contributions[atom_index][axis],
                    location=f"{location}[{atom_index},{axis}]",
                )
                for axis in range(3)
            ),
            location=f"{location}[{atom_index}]",
        )
        for atom_index in range(atom_count)
    )


@dataclass(frozen=True, init=False, slots=True)
class LinearAlkaneC1C4ReferenceKernelResult:
    """Factory-only immutable result from one compiled potential evaluation."""

    _spec: _CompiledSpec = field(repr=False)
    _coordinate_snapshot_sha256: str
    _term_results: tuple[LinearAlkaneReferenceKernelTermResult, ...]
    _class_results: tuple[LinearAlkaneReferenceKernelClassResult, ...]
    _atom_forces: tuple[Vector3, ...]
    _total_virial: Matrix3
    _total_energy: float
    _flat_term_sequence_sha256: str
    _output_sequence_sha256: str
    _evaluation_sha256: str

    @classmethod
    def _create(
        cls,
        *,
        spec: _CompiledSpec,
        coordinate_snapshot_sha256: str,
        term_results: tuple[LinearAlkaneReferenceKernelTermResult, ...],
        class_results: tuple[LinearAlkaneReferenceKernelClassResult, ...],
        atom_forces: tuple[Vector3, ...],
        total_virial: Matrix3,
        total_energy: float,
        flat_term_sequence_sha256: str,
        output_sequence_sha256: str,
    ) -> "LinearAlkaneC1C4ReferenceKernelResult":
        result = object.__new__(cls)
        object.__setattr__(result, "_spec", spec)
        object.__setattr__(
            result,
            "_coordinate_snapshot_sha256",
            coordinate_snapshot_sha256,
        )
        object.__setattr__(result, "_term_results", term_results)
        object.__setattr__(result, "_class_results", class_results)
        object.__setattr__(result, "_atom_forces", atom_forces)
        object.__setattr__(result, "_total_virial", total_virial)
        object.__setattr__(result, "_total_energy", total_energy)
        object.__setattr__(
            result,
            "_flat_term_sequence_sha256",
            flat_term_sequence_sha256,
        )
        object.__setattr__(
            result,
            "_output_sequence_sha256",
            output_sequence_sha256,
        )
        core = result._core_dict(include_evaluation_sha256=False)
        object.__setattr__(result, "_evaluation_sha256", _sha256_document(core))
        result._validate()
        return result

    def _validate(self) -> None:
        if type(self._spec) is not _CompiledSpec:
            raise TypeError("kernel result must retain its exact compiled spec")
        _require_sha256("coordinate snapshot", self._coordinate_snapshot_sha256)
        _require_sha256("flat term sequence", self._flat_term_sequence_sha256)
        _require_sha256("output sequence", self._output_sequence_sha256)
        _require_sha256("evaluation", self._evaluation_sha256)
        if type(self._term_results) is not tuple:
            raise TypeError("kernel term results must be an exact tuple")
        for row in self._term_results:
            if type(row) is not LinearAlkaneReferenceKernelTermResult:
                raise TypeError("kernel term result type is inconsistent")
            row.__post_init__()
        if type(self._class_results) is not tuple or tuple(
            row.term_class for row in self._class_results
        ) != _FROZEN_CLASS_ORDER:
            raise ValueError("kernel class result order is inconsistent")
        for row in self._class_results:
            if type(row) is not LinearAlkaneReferenceKernelClassResult:
                raise TypeError("kernel class result type is inconsistent")
            row.__post_init__()
        if len(self._atom_forces) != self._spec.atom_count:
            raise ValueError("kernel total force atom count is inconsistent")
        for atom_index, vector in enumerate(self._atom_forces):
            _validate_stored_vector(
                vector,
                location=f"result.force[{atom_index}]",
            )
        _validate_stored_matrix(self._total_virial, location="result.virial")
        _finite(self._total_energy, location="result.total_energy")
        expected_class_counts = {
            name: sum(row.term_class == name for row in self._term_results)
            for name in _FROZEN_CLASS_ORDER
        }
        if any(
            row.term_count != expected_class_counts[row.term_class]
            for row in self._class_results
        ):
            raise ValueError("kernel class term counts are inconsistent")
        core = self._core_dict(include_evaluation_sha256=False)
        if _sha256_document(core) != self._evaluation_sha256:
            _fail("result_tampered", "kernel evaluation digest is stale")

    @property
    def total_energy_kilojoule_per_mole(self) -> float:
        self._validate()
        return self._total_energy

    @property
    def term_results(self) -> tuple[LinearAlkaneReferenceKernelTermResult, ...]:
        self._validate()
        return self._term_results

    @property
    def class_results(self) -> tuple[LinearAlkaneReferenceKernelClassResult, ...]:
        self._validate()
        return self._class_results

    @property
    def coordinate_snapshot_sha256(self) -> str:
        self._validate()
        return self._coordinate_snapshot_sha256

    @property
    def evaluation_sha256(self) -> str:
        self._validate()
        return self._evaluation_sha256

    def forces_tensor(self) -> torch.Tensor:
        """Return a detached CPU float64 ``[1,N,3]`` copy."""

        self._validate()
        return torch.tensor(
            [self._atom_forces],
            dtype=torch.float64,
            device="cpu",
        )

    def virial_tensor(self) -> torch.Tensor:
        """Return a detached CPU float64 ``[3,3]`` copy."""

        self._validate()
        return torch.tensor(
            self._total_virial,
            dtype=torch.float64,
            device="cpu",
        )

    def class_forces_tensor(self, term_class: str) -> torch.Tensor:
        if type(term_class) is not str:
            raise TypeError("term_class must be an exact string")
        self._validate()
        for row in self._class_results:
            if row.term_class == term_class:
                return torch.tensor(
                    [row.atom_forces],
                    dtype=torch.float64,
                    device="cpu",
                )
        raise KeyError(term_class)

    def class_virial_tensor(self, term_class: str) -> torch.Tensor:
        if type(term_class) is not str:
            raise TypeError("term_class must be an exact string")
        self._validate()
        for row in self._class_results:
            if row.term_class == term_class:
                return torch.tensor(
                    row.virial_kilojoule_per_mole,
                    dtype=torch.float64,
                    device="cpu",
                )
        raise KeyError(term_class)

    def _core_dict(self, *, include_evaluation_sha256: bool) -> dict[str, Any]:
        spec = self._spec
        document: dict[str, Any] = {
            "schema_id": _FROZEN_RESULT_SCHEMA_ID,
            "schema_version": _FROZEN_RESULT_SCHEMA_VERSION,
            "protocol_schema_id": _FROZEN_PROTOCOL_SCHEMA_ID,
            "protocol_sha256": _FROZEN_PROTOCOL_SHA256,
            "policy_id": _FROZEN_POLICY_ID,
            "algorithm_id": _FROZEN_ALGORITHM_ID,
            "claim_scope": _FROZEN_CLAIM_SCOPE,
            "status": "bounded_nonphysical_energy_force_virial_evaluated",
            "component_id": spec.component_id,
            "binding_report_sha256": spec.binding_report_sha256,
            "binding_report_snapshot_sha256": (
                spec.binding_report_snapshot_sha256
            ),
            "method_binding_sha256": spec.method_binding_sha256,
            "canonical_system_snapshot_sha256": (
                spec.canonical_system_snapshot_sha256
            ),
            "canonical_parameter_artifact_sha256": (
                spec.canonical_parameter_artifact_sha256
            ),
            "canonical_method_artifact_sha256": (
                spec.canonical_method_artifact_sha256
            ),
            "assignment_report_sha256": spec.assignment_report_sha256,
            "parameter_assignment_sha256": spec.parameter_assignment_sha256,
            "method_payload_sha256": spec.method_payload_sha256,
            "evaluation_method_sha256": spec.evaluation_method_sha256,
            "canonical_topology_sha256": spec.canonical_topology_sha256,
            "source_sha256": spec.source_sha256,
            "compiled_plan_sha256": spec.plan_sha256,
            "coordinate_snapshot_sha256": self._coordinate_snapshot_sha256,
            "coordinate_encoding_id": _FROZEN_COORDINATE_ENCODING_ID,
            "atom_count": spec.atom_count,
            "energy_unit": "kilojoule_per_mole",
            "force_unit": "kilojoule_per_mole_per_angstrom",
            "virial_unit": "kilojoule_per_mole",
            "force_definition": _FROZEN_FORCE_DEFINITION,
            "virial_convention_id": _FROZEN_VIRIAL_CONVENTION_ID,
            "virial_definition": _FROZEN_VIRIAL_DEFINITION,
            "term_results": [row.to_dict() for row in self._term_results],
            "class_results": [row.to_dict() for row in self._class_results],
            "total_energy_kilojoule_per_mole_binary64": _binary64_hex(
                self._total_energy,
                location="result.total_energy",
            ),
            "atom_forces_kilojoule_per_mole_per_angstrom_binary64": [
                _vector_document(vector, location=f"result.force[{index}]")
                for index, vector in enumerate(self._atom_forces)
            ],
            "total_virial_kilojoule_per_mole_binary64": _matrix_document(
                self._total_virial,
                location="result.virial",
            ),
            "flat_term_sequence_sha256": self._flat_term_sequence_sha256,
            "output_sequence_sha256": self._output_sequence_sha256,
            "bounded_nonphysical_method_owned_reference_kernel_complete": True,
            "method_owned_energy_kernel_available": True,
            "method_owned_force_kernel_available": True,
            "method_owned_virial_kernel_available": True,
            "energy_evaluated": True,
            "forces_evaluated": True,
            "virial_evaluated": True,
            "production_runtime_energy_kernel_available": False,
            "production_runtime_force_kernel_available": False,
            "production_runtime_virial_kernel_available": False,
            "production_evaluation_method_defined": False,
            "production_parameter_assignment_complete": False,
            "parameterability_assessed": False,
            "parameterizable": False,
            "global_parameter_coverage_complete": False,
            "scientific_parameters": False,
            "scientifically_validated": False,
            "physics_supported": False,
            "runtime_eligible": False,
            "engine_dispatch_registered": False,
            "execution_authorized": False,
            "energy_evaluation_authorized": False,
            "force_evaluation_authorized": False,
            "virial_evaluation_authorized": False,
            "minimization_authorized": False,
            "simulation_ready": False,
            "claim_safe": False,
            "blockers": [
                "numeric_parameters_are_nonphysical_contract_fixtures",
                "licensed_scientific_fit_and_provenance_missing",
                "force_energy_reference_validation_missing",
                "production_cutoff_switch_pbc_long_range_and_pressure_virial_missing",
                "production_runtime_dispatch_and_release_attestation_missing",
            ],
        }
        if include_evaluation_sha256:
            document["evaluation_sha256"] = self._evaluation_sha256
        return document

    @property
    def report_sha256(self) -> str:
        self._validate()
        return _sha256_document(self._core_dict(include_evaluation_sha256=True))

    def to_dict(self) -> dict[str, Any]:
        self._validate()
        document = self._core_dict(include_evaluation_sha256=True)
        document["report_sha256"] = _sha256_document(document)
        return document


def _coordinate_points(
    coordinates: torch.Tensor,
    atom_count: int,
) -> tuple[tuple[Vector3, ...], str]:
    if type(coordinates) is not torch.Tensor:
        raise TypeError("coordinates must be an exact torch.Tensor")
    if coordinates.layout is not torch.strided:
        _fail("coordinate_interface_incompatible", "coordinates must be strided")
    if coordinates.device.type != "cpu" or coordinates.device.index is not None:
        _fail("coordinate_interface_incompatible", "coordinates must be on CPU")
    if coordinates.dtype is not torch.float64:
        _fail(
            "coordinate_interface_incompatible",
            "coordinates must use torch.float64",
        )
    if coordinates.requires_grad:
        _fail(
            "coordinate_interface_incompatible",
            "caller coordinates must not require gradients",
        )
    if coordinates.ndim != 2 or tuple(coordinates.shape) != (atom_count, 3):
        _fail(
            "coordinate_interface_incompatible",
            f"coordinates must have exact shape ({atom_count}, 3)",
        )
    snapshot = coordinates.detach().clone(memory_format=torch.contiguous_format)
    if not bool(torch.isfinite(snapshot).all().item()):
        _fail("nonfinite_coordinate", "coordinates must be finite")
    points = tuple(
        _vector(
            (
                float(snapshot[atom_index, axis].item())
                for axis in range(3)
            ),
            location=f"coordinates[{atom_index}]",
        )
        for atom_index in range(atom_count)
    )
    coordinate_document = {
        "encoding_id": _FROZEN_COORDINATE_ENCODING_ID,
        "shape": [atom_count, 3],
        "values_binary64": [
            _vector_document(point, location=f"coordinates[{index}]")
            for index, point in enumerate(points)
        ],
    }
    return points, _sha256_document(coordinate_document)


def _point(points: tuple[Vector3, ...], atom_index: int) -> Vector3:
    try:
        return points[atom_index]
    except IndexError:
        _fail("dependency_inconsistent", "term atom index is outside coordinates")


def _require_distance(
    vector: Vector3,
    minimum: float,
    *,
    location: str,
) -> float:
    distance = _hypot(vector, location=f"{location}.distance")
    if distance <= minimum:
        _fail(
            "singular_geometry",
            f"{location} distance must exceed the compiled method threshold",
        )
    return distance


def _bond_result(
    spec: _CompiledSpec,
    term: _BondSpec,
    points: tuple[Vector3, ...],
) -> tuple[LinearAlkaneReferenceKernelTermResult, _FlatTerm]:
    location = f"bond[{term.atom_i},{term.atom_j}]"
    difference = _difference(
        _point(points, term.atom_i),
        _point(points, term.atom_j),
        location=f"{location}.difference",
    )
    distance = _require_distance(
        difference,
        spec.minimum_distance,
        location=location,
    )
    displacement = _subtract(
        distance,
        term.equilibrium,
        location=f"{location}.displacement",
    )
    half_k = _multiply(0.5, term.force_constant, location=f"{location}.half_k")
    temporary = _multiply(
        half_k,
        displacement,
        location=f"{location}.energy_temporary",
    )
    energy = _multiply(
        temporary,
        displacement,
        location=f"{location}.energy",
    )
    derivative = _multiply(
        term.force_constant,
        displacement,
        location=f"{location}.d_energy_d_distance",
    )
    force_i = _scale(
        _divide(derivative, distance, location=f"{location}.force_scale"),
        difference,
        location=f"{location}.force_i",
    )
    force_j = _negate(force_i, location=f"{location}.force_j")
    local_forces: LocalForces = (
        (term.atom_i, force_i),
        (term.atom_j, force_j),
    )
    virial = _local_virial(
        local_forces,
        points,
        term.atom_j,
        location=f"{location}.virial",
    )
    result = LinearAlkaneReferenceKernelTermResult(
        term_class="bond",
        identity=(term.atom_i, term.atom_j),
        parameter_id=term.parameter_id,
        energy_kilojoule_per_mole=energy,
        local_forces=local_forces,
        virial_kilojoule_per_mole=virial,
    )
    return result, _FlatTerm("bond", result.identity, energy, local_forces, virial)


def _angle_result(
    spec: _CompiledSpec,
    term: _AngleSpec,
    points: tuple[Vector3, ...],
) -> tuple[LinearAlkaneReferenceKernelTermResult, _FlatTerm]:
    location = f"angle[{term.atom_i},{term.center},{term.atom_k}]"
    center_point = _point(points, term.center)
    vector_u = _difference(
        center_point,
        _point(points, term.atom_i),
        location=f"{location}.u",
    )
    vector_v = _difference(
        center_point,
        _point(points, term.atom_k),
        location=f"{location}.v",
    )
    length_u = _require_distance(
        vector_u,
        spec.minimum_distance,
        location=f"{location}.u",
    )
    length_v = _require_distance(
        vector_v,
        spec.minimum_distance,
        location=f"{location}.v",
    )
    unit_u = _unit(vector_u, length_u, location=f"{location}.u_hat")
    unit_v = _unit(vector_v, length_v, location=f"{location}.v_hat")
    normalized_cross = _cross(
        unit_u,
        unit_v,
        location=f"{location}.normalized_cross",
    )
    normalized_sine = _hypot(
        normalized_cross,
        location=f"{location}.normalized_sine",
    )
    if normalized_sine <= spec.minimum_angle_sine:
        _fail("singular_geometry", f"{location} sine is at or below threshold")
    raw_cross = _cross(vector_u, vector_v, location=f"{location}.raw_cross")
    raw_cross_norm = _hypot(raw_cross, location=f"{location}.raw_cross_norm")
    if raw_cross_norm == 0.0:
        _fail(
            "nonrepresentable_coordinate_intermediate",
            f"{location} raw cross underflowed to zero",
        )
    raw_dot = _dot(vector_u, vector_v, location=f"{location}.raw_dot")
    angle = _atan2(raw_cross_norm, raw_dot, location=f"{location}.coordinate")
    displacement = _subtract(
        angle,
        term.equilibrium,
        location=f"{location}.displacement",
    )
    half_k = _multiply(0.5, term.force_constant, location=f"{location}.half_k")
    temporary = _multiply(
        half_k,
        displacement,
        location=f"{location}.energy_temporary",
    )
    energy = _multiply(
        temporary,
        displacement,
        location=f"{location}.energy",
    )
    derivative = _multiply(
        term.force_constant,
        displacement,
        location=f"{location}.d_energy_d_angle",
    )
    cosine = _dot(unit_u, unit_v, location=f"{location}.normalized_cosine")
    gradient_u_numerator = _difference(
        unit_v,
        _scale(cosine, unit_u, location=f"{location}.cos_u"),
        location=f"{location}.gradient_u_numerator",
    )
    gradient_v_numerator = _difference(
        unit_u,
        _scale(cosine, unit_v, location=f"{location}.cos_v"),
        location=f"{location}.gradient_v_numerator",
    )
    gradient_u = _scale(
        _divide(
            1.0,
            _multiply(
                length_u,
                normalized_sine,
                location=f"{location}.gradient_u_denominator",
            ),
            location=f"{location}.gradient_u_inverse",
        ),
        gradient_u_numerator,
        location=f"{location}.gradient_u",
    )
    gradient_v = _scale(
        _divide(
            1.0,
            _multiply(
                length_v,
                normalized_sine,
                location=f"{location}.gradient_v_denominator",
            ),
            location=f"{location}.gradient_v_inverse",
        ),
        gradient_v_numerator,
        location=f"{location}.gradient_v",
    )
    force_i = _scale(
        _multiply(-1.0, derivative, location=f"{location}.minus_derivative"),
        gradient_u,
        location=f"{location}.force_i",
    )
    force_k = _scale(
        _multiply(-1.0, derivative, location=f"{location}.minus_derivative_k"),
        gradient_v,
        location=f"{location}.force_k",
    )
    force_center = _negate(
        _sum_vectors((force_i, force_k), location=f"{location}.outer_force_sum"),
        location=f"{location}.force_center",
    )
    local_forces: LocalForces = (
        (term.atom_i, force_i),
        (term.center, force_center),
        (term.atom_k, force_k),
    )
    virial = _local_virial(
        local_forces,
        points,
        term.center,
        location=f"{location}.virial",
    )
    result = LinearAlkaneReferenceKernelTermResult(
        term_class="angle",
        identity=(term.atom_i, term.center, term.atom_k),
        parameter_id=term.parameter_id,
        energy_kilojoule_per_mole=energy,
        local_forces=local_forces,
        virial_kilojoule_per_mole=virial,
    )
    return result, _FlatTerm("angle", result.identity, energy, local_forces, virial)


def _proper_result(
    spec: _CompiledSpec,
    term: _ProperSpec,
    points: tuple[Vector3, ...],
) -> tuple[LinearAlkaneReferenceKernelTermResult, _FlatTerm]:
    identity = (term.atom_i, term.atom_j, term.atom_k, term.atom_l)
    location = f"proper[{','.join(str(value) for value in identity)}]"
    bond_1 = _difference(
        _point(points, term.atom_i),
        _point(points, term.atom_j),
        location=f"{location}.b1",
    )
    bond_2 = _difference(
        _point(points, term.atom_j),
        _point(points, term.atom_k),
        location=f"{location}.b2",
    )
    bond_3 = _difference(
        _point(points, term.atom_k),
        _point(points, term.atom_l),
        location=f"{location}.b3",
    )
    length_1 = _require_distance(
        bond_1,
        spec.minimum_distance,
        location=f"{location}.b1",
    )
    length_2 = _require_distance(
        bond_2,
        spec.minimum_distance,
        location=f"{location}.b2",
    )
    length_3 = _require_distance(
        bond_3,
        spec.minimum_distance,
        location=f"{location}.b3",
    )
    unit_1 = _unit(bond_1, length_1, location=f"{location}.b1_hat")
    unit_2 = _unit(bond_2, length_2, location=f"{location}.b2_hat")
    unit_3 = _unit(bond_3, length_3, location=f"{location}.b3_hat")
    sine_1 = _hypot(
        _cross(unit_1, unit_2, location=f"{location}.normalized_cross_1"),
        location=f"{location}.normalized_sine_1",
    )
    sine_2 = _hypot(
        _cross(unit_2, unit_3, location=f"{location}.normalized_cross_2"),
        location=f"{location}.normalized_sine_2",
    )
    if sine_1 <= spec.minimum_proper_sine or sine_2 <= spec.minimum_proper_sine:
        _fail("singular_geometry", f"{location} sine is at or below threshold")
    normal_1 = _cross(bond_1, bond_2, location=f"{location}.normal_1")
    normal_2 = _cross(bond_2, bond_3, location=f"{location}.normal_2")
    normal_1_sq = _dot(normal_1, normal_1, location=f"{location}.normal_1_sq")
    normal_2_sq = _dot(normal_2, normal_2, location=f"{location}.normal_2_sq")
    if normal_1_sq == 0.0 or normal_2_sq == 0.0:
        _fail(
            "nonrepresentable_coordinate_intermediate",
            f"{location} raw normal underflowed to zero",
        )
    cross_normals = _cross(
        normal_1,
        normal_2,
        location=f"{location}.cross_normals",
    )
    y_value = _dot(cross_normals, unit_2, location=f"{location}.atan2_y")
    x_value = _dot(normal_1, normal_2, location=f"{location}.atan2_x")
    if x_value == 0.0 and y_value == 0.0:
        _fail(
            "nonrepresentable_coordinate_intermediate",
            f"{location} atan2 inputs are both zero",
        )
    dihedral = _atan2(y_value, x_value, location=f"{location}.coordinate")
    component_energies: list[float] = []
    component_derivatives: list[float] = []
    for component_index, (periodicity, phase, amplitude) in enumerate(
        term.components
    ):
        n_phi = _multiply(
            float(periodicity),
            dihedral,
            location=f"{location}.component[{component_index}].n_phi",
        )
        argument = _subtract(
            n_phi,
            phase,
            location=f"{location}.component[{component_index}].argument",
        )
        one_plus_cosine = _add(
            1.0,
            _cos(argument, location=f"{location}.component[{component_index}].cos"),
            location=f"{location}.component[{component_index}].one_plus_cos",
        )
        component_energies.append(
            _multiply(
                amplitude,
                one_plus_cosine,
                location=f"{location}.component[{component_index}].energy",
            )
        )
        amplitude_n = _multiply(
            amplitude,
            float(periodicity),
            location=f"{location}.component[{component_index}].amplitude_n",
        )
        component_derivatives.append(
            _multiply(
                _multiply(
                    -1.0,
                    amplitude_n,
                    location=f"{location}.component[{component_index}].minus_amplitude_n",
                ),
                _sin(
                    argument,
                    location=f"{location}.component[{component_index}].sin",
                ),
                location=f"{location}.component[{component_index}].derivative",
            )
        )
    energy = _finite_fsum(component_energies, location=f"{location}.energy")
    derivative = _finite_fsum(
        component_derivatives,
        location=f"{location}.d_energy_d_phi",
    )
    gradient_i = _scale(
        _divide(
            _multiply(-1.0, length_2, location=f"{location}.minus_b2_length"),
            normal_1_sq,
            location=f"{location}.gradient_i_scale",
        ),
        normal_1,
        location=f"{location}.gradient_i",
    )
    gradient_l = _scale(
        _divide(length_2, normal_2_sq, location=f"{location}.gradient_l_scale"),
        normal_2,
        location=f"{location}.gradient_l",
    )
    length_2_sq = _multiply(
        length_2,
        length_2,
        location=f"{location}.b2_length_sq",
    )
    alpha = _divide(
        _dot(bond_1, bond_2, location=f"{location}.b1_dot_b2"),
        length_2_sq,
        location=f"{location}.alpha",
    )
    beta = _divide(
        _dot(bond_3, bond_2, location=f"{location}.b3_dot_b2"),
        length_2_sq,
        location=f"{location}.beta",
    )
    gradient_j = _sum_vectors(
        (
            _scale(
                _multiply(
                    -1.0,
                    _add(1.0, alpha, location=f"{location}.one_plus_alpha"),
                    location=f"{location}.minus_one_plus_alpha",
                ),
                gradient_i,
                location=f"{location}.gradient_j_i",
            ),
            _scale(beta, gradient_l, location=f"{location}.gradient_j_l"),
        ),
        location=f"{location}.gradient_j",
    )
    gradient_k = _sum_vectors(
        (
            _scale(alpha, gradient_i, location=f"{location}.gradient_k_i"),
            _scale(
                _multiply(
                    -1.0,
                    _add(1.0, beta, location=f"{location}.one_plus_beta"),
                    location=f"{location}.minus_one_plus_beta",
                ),
                gradient_l,
                location=f"{location}.gradient_k_l",
            ),
        ),
        location=f"{location}.gradient_k",
    )
    minus_derivative = _multiply(
        -1.0,
        derivative,
        location=f"{location}.minus_derivative",
    )
    local_forces: LocalForces = (
        (
            term.atom_i,
            _scale(minus_derivative, gradient_i, location=f"{location}.force_i"),
        ),
        (
            term.atom_j,
            _scale(minus_derivative, gradient_j, location=f"{location}.force_j"),
        ),
        (
            term.atom_k,
            _scale(minus_derivative, gradient_k, location=f"{location}.force_k"),
        ),
        (
            term.atom_l,
            _scale(minus_derivative, gradient_l, location=f"{location}.force_l"),
        ),
    )
    virial = _local_virial(
        local_forces,
        points,
        term.atom_j,
        location=f"{location}.virial",
    )
    result = LinearAlkaneReferenceKernelTermResult(
        term_class="proper",
        identity=identity,
        parameter_id=term.parameter_id,
        energy_kilojoule_per_mole=energy,
        local_forces=local_forces,
        virial_kilojoule_per_mole=virial,
    )
    return result, _FlatTerm("proper", identity, energy, local_forces, virial)


def _radial_local_forces(
    atom_i: int,
    atom_j: int,
    difference: Vector3,
    distance: float,
    derivative: float,
    *,
    location: str,
) -> LocalForces:
    force_i = _scale(
        _divide(derivative, distance, location=f"{location}.force_scale"),
        difference,
        location=f"{location}.force_i",
    )
    return (
        (atom_i, force_i),
        (atom_j, _negate(force_i, location=f"{location}.force_j")),
    )


def _pair_results(
    spec: _CompiledSpec,
    term: _PairSpec,
    points: tuple[Vector3, ...],
) -> tuple[
    LinearAlkaneReferenceKernelTermResult,
    LinearAlkaneReferenceKernelTermResult,
    _FlatTerm,
]:
    identity = (term.atom_i, term.atom_j)
    location = f"pair[{term.atom_i},{term.atom_j}]"
    difference = _difference(
        _point(points, term.atom_i),
        _point(points, term.atom_j),
        location=f"{location}.difference",
    )
    distance = _require_distance(
        difference,
        spec.minimum_distance,
        location=location,
    )
    sigma_over_r = _divide(
        term.sigma,
        distance,
        location=f"{location}.sigma_over_r",
    )
    ratio_2 = _multiply(
        sigma_over_r,
        sigma_over_r,
        location=f"{location}.ratio_2",
    )
    ratio_4 = _multiply(ratio_2, ratio_2, location=f"{location}.ratio_4")
    ratio_6 = _multiply(ratio_4, ratio_2, location=f"{location}.ratio_6")
    ratio_12 = _multiply(ratio_6, ratio_6, location=f"{location}.ratio_12")
    shape = _subtract(
        ratio_12,
        ratio_6,
        location=f"{location}.lj_shape",
    )
    four_epsilon = _multiply(
        4.0,
        term.epsilon,
        location=f"{location}.four_epsilon",
    )
    lj_base = _multiply(four_epsilon, shape, location=f"{location}.lj_base")
    coulomb_temporary_1 = _multiply(
        spec.effective_coulomb_coefficient,
        term.charge_i,
        location=f"{location}.coulomb_temporary_1",
    )
    coulomb_temporary_2 = _multiply(
        coulomb_temporary_1,
        term.charge_j,
        location=f"{location}.coulomb_temporary_2",
    )
    coulomb_base = _divide(
        coulomb_temporary_2,
        distance,
        location=f"{location}.coulomb_base",
    )
    six_ratio_6 = _multiply(6.0, ratio_6, location=f"{location}.six_ratio_6")
    twelve_ratio_12 = _multiply(
        12.0,
        ratio_12,
        location=f"{location}.twelve_ratio_12",
    )
    derivative_shape = _subtract(
        six_ratio_6,
        twelve_ratio_12,
        location=f"{location}.derivative_shape",
    )
    derivative_lj_base = _multiply(
        _divide(four_epsilon, distance, location=f"{location}.four_epsilon_over_r"),
        derivative_shape,
        location=f"{location}.lj_derivative_base",
    )
    derivative_coulomb_base = _divide(
        _multiply(-1.0, coulomb_base, location=f"{location}.minus_coulomb"),
        distance,
        location=f"{location}.coulomb_derivative_base",
    )
    if term.interaction_class == "one_four_separate":
        if type(term.lj_scale) is not float or type(term.coulomb_scale) is not float:
            _fail("dependency_inconsistent", f"{location} one-four scales are absent")
        lj_energy = _multiply(
            term.lj_scale,
            lj_base,
            location=f"{location}.scaled_lj_energy",
        )
        coulomb_energy = _multiply(
            term.coulomb_scale,
            coulomb_base,
            location=f"{location}.scaled_coulomb_energy",
        )
        derivative_lj = _multiply(
            term.lj_scale,
            derivative_lj_base,
            location=f"{location}.scaled_lj_derivative",
        )
        derivative_coulomb = _multiply(
            term.coulomb_scale,
            derivative_coulomb_base,
            location=f"{location}.scaled_coulomb_derivative",
        )
    elif term.interaction_class == "full_nonbonded":
        if term.lj_scale is not None or term.coulomb_scale is not None:
            _fail("dependency_inconsistent", f"{location} full pair carries scales")
        lj_energy = lj_base
        coulomb_energy = coulomb_base
        derivative_lj = derivative_lj_base
        derivative_coulomb = derivative_coulomb_base
    else:
        _fail("dependency_inconsistent", f"{location} pair class is unavailable")
    lj_forces = _radial_local_forces(
        term.atom_i,
        term.atom_j,
        difference,
        distance,
        derivative_lj,
        location=f"{location}.lj",
    )
    coulomb_forces = _radial_local_forces(
        term.atom_i,
        term.atom_j,
        difference,
        distance,
        derivative_coulomb,
        location=f"{location}.coulomb",
    )
    lj_virial = _local_virial(
        lj_forces,
        points,
        term.atom_j,
        location=f"{location}.lj_virial",
    )
    coulomb_virial = _local_virial(
        coulomb_forces,
        points,
        term.atom_j,
        location=f"{location}.coulomb_virial",
    )
    lj_result = LinearAlkaneReferenceKernelTermResult(
        term_class="lennard_jones",
        identity=identity,
        parameter_id=term.parameter_id,
        energy_kilojoule_per_mole=lj_energy,
        local_forces=lj_forces,
        virial_kilojoule_per_mole=lj_virial,
    )
    coulomb_result = LinearAlkaneReferenceKernelTermResult(
        term_class="coulomb",
        identity=identity,
        parameter_id=term.parameter_id,
        energy_kilojoule_per_mole=coulomb_energy,
        local_forces=coulomb_forces,
        virial_kilojoule_per_mole=coulomb_virial,
    )
    pair_energy = _finite_fsum(
        (lj_energy, coulomb_energy),
        location=f"{location}.pair_energy",
    )
    pair_derivative = _finite_fsum(
        (derivative_lj, derivative_coulomb),
        location=f"{location}.pair_derivative",
    )
    pair_local_forces = _radial_local_forces(
        term.atom_i,
        term.atom_j,
        difference,
        distance,
        pair_derivative,
        location=f"{location}.pair",
    )
    pair_virial = _local_virial(
        pair_local_forces,
        points,
        term.atom_j,
        location=f"{location}.pair_virial",
    )
    return (
        lj_result,
        coulomb_result,
        _FlatTerm(
            "selected_pair",
            identity,
            pair_energy,
            pair_local_forces,
            pair_virial,
        ),
    )


def _evaluate_spec(
    spec: _CompiledSpec,
    coordinates: torch.Tensor,
) -> LinearAlkaneC1C4ReferenceKernelResult:
    _require_round_to_nearest_ties_to_even()
    points, coordinate_snapshot_sha256 = _coordinate_points(
        coordinates,
        spec.atom_count,
    )
    public_terms: list[LinearAlkaneReferenceKernelTermResult] = []
    flat_terms: list[_FlatTerm] = []
    for term in spec.bonds:
        result, flat = _bond_result(spec, term, points)
        public_terms.append(result)
        flat_terms.append(flat)
    for term in spec.angles:
        result, flat = _angle_result(spec, term, points)
        public_terms.append(result)
        flat_terms.append(flat)
    for term in spec.propers:
        result, flat = _proper_result(spec, term, points)
        public_terms.append(result)
        flat_terms.append(flat)
    for term in spec.pairs:
        lj_result, coulomb_result, flat = _pair_results(spec, term, points)
        public_terms.extend((lj_result, coulomb_result))
        flat_terms.append(flat)
    term_results = tuple(public_terms)
    flat_rows = tuple(flat_terms)
    total_energy = _finite_fsum(
        (row.energy for row in flat_rows),
        location="flat_total_energy",
    )
    atom_forces = _aggregate_atom_forces(
        (
            (row.term_class, row.identity, row.local_forces)
            for row in flat_rows
        ),
        spec.atom_count,
        location="flat_total_force",
    )
    total_virial = _sum_matrices(
        (row.virial for row in flat_rows),
        location="flat_total_virial",
    )
    class_results: list[LinearAlkaneReferenceKernelClassResult] = []
    for term_class in _FROZEN_CLASS_ORDER:
        selected = tuple(row for row in term_results if row.term_class == term_class)
        class_results.append(
            LinearAlkaneReferenceKernelClassResult(
                term_class=term_class,
                term_count=len(selected),
                energy_kilojoule_per_mole=_finite_fsum(
                    (row.energy_kilojoule_per_mole for row in selected),
                    location=f"class[{term_class}].energy",
                ),
                atom_forces=_aggregate_atom_forces(
                    (
                        (row.term_class, row.identity, row.local_forces)
                        for row in selected
                    ),
                    spec.atom_count,
                    location=f"class[{term_class}].force",
                ),
                virial_kilojoule_per_mole=_sum_matrices(
                    (row.virial_kilojoule_per_mole for row in selected),
                    location=f"class[{term_class}].virial",
                ),
            )
        )
    flat_sequence_document = [
        {
            "term_class": row.term_class,
            "identity": _identity_document(row.term_class, row.identity),
            "energy_kilojoule_per_mole_binary64": _binary64_hex(
                row.energy,
                location=f"flat_sequence[{index}].energy",
            ),
        }
        for index, row in enumerate(flat_rows)
    ]
    output_sequence_document = {
        "total_energy_kilojoule_per_mole_binary64": _binary64_hex(
            total_energy,
            location="output.total_energy",
        ),
        "atom_forces": [
            _vector_document(vector, location=f"output.force[{index}]")
            for index, vector in enumerate(atom_forces)
        ],
        "total_virial": _matrix_document(total_virial, location="output.virial"),
    }
    _require_round_to_nearest_ties_to_even()
    return LinearAlkaneC1C4ReferenceKernelResult._create(
        spec=spec,
        coordinate_snapshot_sha256=coordinate_snapshot_sha256,
        term_results=term_results,
        class_results=tuple(class_results),
        atom_forces=atom_forces,
        total_virial=total_virial,
        total_energy=total_energy,
        flat_term_sequence_sha256=_sha256_document(flat_sequence_document),
        output_sequence_sha256=_sha256_document(output_sequence_document),
    )


def _plan_document_from_parts(
    *,
    atom_count: int,
    minimum_distance: float,
    minimum_angle_sine: float,
    minimum_proper_sine: float,
    effective_coulomb_coefficient: float,
    bonds: tuple[_BondSpec, ...],
    angles: tuple[_AngleSpec, ...],
    propers: tuple[_ProperSpec, ...],
    pairs: tuple[_PairSpec, ...],
    bindings: Mapping[str, str],
    component_id: str,
) -> dict[str, Any]:
    return {
        "protocol_sha256": _FROZEN_PROTOCOL_SHA256,
        "component_id": component_id,
        "atom_count": atom_count,
        "minimum_distance_angstrom_binary64": _binary64_hex(
            minimum_distance,
            location="plan.minimum_distance",
        ),
        "minimum_angle_sine_binary64": _binary64_hex(
            minimum_angle_sine,
            location="plan.minimum_angle_sine",
        ),
        "minimum_proper_sine_binary64": _binary64_hex(
            minimum_proper_sine,
            location="plan.minimum_proper_sine",
        ),
        "effective_coulomb_coefficient_binary64": _binary64_hex(
            effective_coulomb_coefficient,
            location="plan.effective_coulomb",
        ),
        "bindings": dict(bindings),
        "bonds": [
            {
                "identity": {"atom_i": row.atom_i, "atom_j": row.atom_j},
                "parameter_id": row.parameter_id,
                "equilibrium_binary64": _binary64_hex(
                    row.equilibrium,
                    location=f"plan.bond[{index}].equilibrium",
                ),
                "force_constant_binary64": _binary64_hex(
                    row.force_constant,
                    location=f"plan.bond[{index}].force_constant",
                ),
            }
            for index, row in enumerate(bonds)
        ],
        "angles": [
            {
                "identity": {
                    "outer_atom_i": row.atom_i,
                    "center_atom": row.center,
                    "outer_atom_k": row.atom_k,
                },
                "parameter_id": row.parameter_id,
                "equilibrium_binary64": _binary64_hex(
                    row.equilibrium,
                    location=f"plan.angle[{index}].equilibrium",
                ),
                "force_constant_binary64": _binary64_hex(
                    row.force_constant,
                    location=f"plan.angle[{index}].force_constant",
                ),
            }
            for index, row in enumerate(angles)
        ],
        "propers": [
            {
                "identity": {
                    "atom_i": row.atom_i,
                    "atom_j": row.atom_j,
                    "atom_k": row.atom_k,
                    "atom_l": row.atom_l,
                },
                "parameter_id": row.parameter_id,
                "components": [
                    {
                        "periodicity": periodicity,
                        "phase_binary64": _binary64_hex(
                            phase,
                            location=f"plan.proper[{index}].phase[{component_index}]",
                        ),
                        "amplitude_binary64": _binary64_hex(
                            amplitude,
                            location=f"plan.proper[{index}].amplitude[{component_index}]",
                        ),
                    }
                    for component_index, (periodicity, phase, amplitude) in enumerate(
                        row.components
                    )
                ],
            }
            for index, row in enumerate(propers)
        ],
        "pairs": [
            {
                "identity": {"atom_i": row.atom_i, "atom_j": row.atom_j},
                "interaction_class": row.interaction_class,
                "shortest_graph_distance": row.shortest_graph_distance,
                "parameter_id": row.parameter_id,
                "sigma_binary64": _binary64_hex(
                    row.sigma,
                    location=f"plan.pair[{index}].sigma",
                ),
                "epsilon_binary64": _binary64_hex(
                    row.epsilon,
                    location=f"plan.pair[{index}].epsilon",
                ),
                "charge_i_binary64": _binary64_hex(
                    row.charge_i,
                    location=f"plan.pair[{index}].charge_i",
                ),
                "charge_j_binary64": _binary64_hex(
                    row.charge_j,
                    location=f"plan.pair[{index}].charge_j",
                ),
                "lj_scale_binary64": (
                    None
                    if row.lj_scale is None
                    else _binary64_hex(
                        row.lj_scale,
                        location=f"plan.pair[{index}].lj_scale",
                    )
                ),
                "coulomb_scale_binary64": (
                    None
                    if row.coulomb_scale is None
                    else _binary64_hex(
                        row.coulomb_scale,
                        location=f"plan.pair[{index}].coulomb_scale",
                    )
                ),
            }
            for index, row in enumerate(pairs)
        ],
    }


def _compile_spec(
    binding_report: LinearAlkaneC1C4EvaluationMethodBindingReport,
) -> tuple[_CompiledSpec, bytes]:
    if type(binding_report) is not LinearAlkaneC1C4EvaluationMethodBindingReport:
        raise TypeError("binding_report must be an exact C1-C4 binding report")
    _require_round_to_nearest_ties_to_even()
    try:
        replay = binding_report._replay_for_bounded_scalar_energy_diagnostic()
    except (AttributeError, TypeError, ValueError) as exc:
        _fail("binding_replay_failed", f"binding replay failed: {exc}")
    if replay.method_binding_status != "contract_fixture_method_bound":
        _fail(
            "binding_not_executable",
            f"binding status {replay.method_binding_status!r} is not executable",
        )
    if replay.geometry_domain_assessment_status != (
        "passed_bounded_domain_check_no_evaluation"
    ):
        _fail(
            "binding_not_executable",
            "binding geometry domain did not pass",
        )
    binding_bytes = bytes(replay.binding_report_bytes)
    try:
        binding = json.loads(binding_bytes.decode("ascii"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        _fail("dependency_inconsistent", f"binding report is invalid: {exc}")
    if type(binding) is not dict or _canonical_json_bytes(binding) != binding_bytes:
        _fail("dependency_inconsistent", "binding report is not canonical")
    binding_core = dict(binding)
    binding_report_sha256 = binding_core.pop("report_sha256", None)
    _require_sha256("binding report", binding_report_sha256)
    if _sha256_document(binding_core) != binding_report_sha256:
        _fail("dependency_inconsistent", "binding report digest is stale")
    binding_report_snapshot_sha256 = hashlib.sha256(binding_bytes).hexdigest()
    if binding.get("schema_id") != _FROZEN_BINDING_SCHEMA_ID:
        _fail("dependency_inconsistent", "binding schema is inconsistent")
    if binding.get("binding_policy_id") != _FROZEN_BINDING_POLICY_ID:
        _fail("dependency_inconsistent", "binding policy is inconsistent")
    if binding.get("method_binding_status") != "contract_fixture_method_bound":
        _fail("dependency_inconsistent", "binding status projection differs")
    if binding.get("geometry_domain_assessment_status") != (
        "passed_bounded_domain_check_no_evaluation"
    ):
        _fail("dependency_inconsistent", "binding geometry projection differs")
    if binding.get("method_protocol_sha256") != _FROZEN_BASE_METHOD_PROTOCOL_SHA256:
        _fail("dependency_inconsistent", "base method protocol digest differs")
    if binding.get("method_schema_id") != _FROZEN_BASE_METHOD_SCHEMA_ID:
        _fail("dependency_inconsistent", "base method schema differs")
    if binding.get("assignment_schema_id") != _FROZEN_ASSIGNMENT_SCHEMA_ID:
        _fail("dependency_inconsistent", "assignment schema differs")
    if binding.get("parameter_protocol_sha256") != (
        _FROZEN_PARAMETER_PROTOCOL_SHA256
    ):
        _fail("dependency_inconsistent", "parameter protocol digest differs")
    if binding.get("parameter_set_schema_id") != _FROZEN_PARAMETER_SET_SCHEMA_ID:
        _fail("dependency_inconsistent", "parameter schema differs")
    if binding.get("force_field_unit_system_id") != _FROZEN_UNIT_SYSTEM_ID:
        _fail("dependency_inconsistent", "unit-system binding differs")
    method_document = replay.method.to_dict()
    method_payload = method_document["method_payload"]
    if method_payload.get("energy_kernel_status") != "missing":
        _fail("dependency_inconsistent", "base v1 kernel status changed")
    if method_payload.get("force_method_status") != "not_defined":
        _fail("dependency_inconsistent", "base v1 force status changed")
    if method_payload.get("virial_method_status") != "not_defined":
        _fail("dependency_inconsistent", "base v1 virial status changed")
    if method_payload.get("protocol_sha256") != _FROZEN_BASE_METHOD_PROTOCOL_SHA256:
        _fail("dependency_inconsistent", "base method payload protocol differs")
    assignment = replay.assignment_report.to_dict()
    if assignment.get("schema_id") != _FROZEN_ASSIGNMENT_SCHEMA_ID:
        _fail("dependency_inconsistent", "assignment report schema differs")
    if assignment.get("assignment_status") != "contract_fixture_mapped":
        _fail("binding_not_executable", "assignment is not completely mapped")
    if assignment.get("report_sha256") != binding.get("assignment_report_sha256"):
        _fail("dependency_inconsistent", "assignment report binding differs")
    atom_count = assignment.get("atom_count")
    if type(atom_count) is not int or not 5 <= atom_count <= _FROZEN_MAXIMUM_ATOM_COUNT:
        _fail("dependency_inconsistent", "assignment atom count is out of bounds")
    bonds = tuple(
        _BondSpec(
            atom_i=row["identity"]["atom_i"],
            atom_j=row["identity"]["atom_j"],
            parameter_id=row["parameter_id"],
            equilibrium=_binary64_from_hex(
                row["equilibrium_length_angstrom_binary64"],
                location=f"bond[{index}].equilibrium",
            ),
            force_constant=_binary64_from_hex(
                row[
                    "force_constant_kilojoule_per_mole_per_angstrom2_binary64"
                ],
                location=f"bond[{index}].force_constant",
            ),
        )
        for index, row in enumerate(assignment["bond_assignments"])
    )
    angles = tuple(
        _AngleSpec(
            atom_i=row["identity"]["outer_atom_i"],
            center=row["identity"]["center_atom"],
            atom_k=row["identity"]["outer_atom_k"],
            parameter_id=row["parameter_id"],
            equilibrium=_binary64_from_hex(
                row["equilibrium_angle_radian_binary64"],
                location=f"angle[{index}].equilibrium",
            ),
            force_constant=_binary64_from_hex(
                row["force_constant_kilojoule_per_mole_per_radian2_binary64"],
                location=f"angle[{index}].force_constant",
            ),
        )
        for index, row in enumerate(assignment["angle_assignments"])
    )
    propers = tuple(
        _ProperSpec(
            atom_i=row["identity"]["atom_i"],
            atom_j=row["identity"]["atom_j"],
            atom_k=row["identity"]["atom_k"],
            atom_l=row["identity"]["atom_l"],
            parameter_id=row["parameter_id"],
            components=tuple(
                (
                    component["periodicity"],
                    _binary64_from_hex(
                        component["phase_radian_binary64"],
                        location=f"proper[{index}].phase[{component_index}]",
                    ),
                    _binary64_from_hex(
                        component["amplitude_kilojoule_per_mole_binary64"],
                        location=f"proper[{index}].amplitude[{component_index}]",
                    ),
                )
                for component_index, component in enumerate(row["components"])
            ),
        )
        for index, row in enumerate(assignment["proper_assignments"])
    )
    selected_pair_rows = tuple(
        row
        for row in assignment["pair_assignments"]
        if row["interaction_class"] in {"one_four_separate", "full_nonbonded"}
    )
    pairs = tuple(
        _PairSpec(
            atom_i=row["identity"]["atom_i"],
            atom_j=row["identity"]["atom_j"],
            interaction_class=row["interaction_class"],
            shortest_graph_distance=row["shortest_graph_distance"],
            parameter_id=(
                row["lj_override_id"]
                if row["lj_override_id"] is not None
                else (
                    f"{row['lj_resolution_status']}:"
                    f"{row['resolved_lj_type_i']}:{row['resolved_lj_type_j']}:"
                    f"{row['atom_i_charge_parameter_id']}:"
                    f"{row['atom_j_charge_parameter_id']}"
                )
            ),
            sigma=_binary64_from_hex(
                row["lj_sigma_angstrom_binary64"],
                location=f"pair[{index}].sigma",
            ),
            epsilon=_binary64_from_hex(
                row["lj_epsilon_kilojoule_per_mole_binary64"],
                location=f"pair[{index}].epsilon",
            ),
            charge_i=_binary64_from_hex(
                row["atom_i_partial_charge_e_binary64"],
                location=f"pair[{index}].charge_i",
            ),
            charge_j=_binary64_from_hex(
                row["atom_j_partial_charge_e_binary64"],
                location=f"pair[{index}].charge_j",
            ),
            lj_scale=(
                None
                if row["lj_energy_scale_binary64"] is None
                else _binary64_from_hex(
                    row["lj_energy_scale_binary64"],
                    location=f"pair[{index}].lj_scale",
                )
            ),
            coulomb_scale=(
                None
                if row["coulomb_energy_scale_binary64"] is None
                else _binary64_from_hex(
                    row["coulomb_energy_scale_binary64"],
                    location=f"pair[{index}].coulomb_scale",
                )
            ),
        )
        for index, row in enumerate(selected_pair_rows)
    )
    if len(bonds) != assignment["bond_assignment_count"]:
        _fail("dependency_inconsistent", "bond assignment count differs")
    if len(angles) != assignment["angle_assignment_count"]:
        _fail("dependency_inconsistent", "angle assignment count differs")
    if len(propers) != assignment["proper_assignment_count"]:
        _fail("dependency_inconsistent", "proper assignment count differs")
    if len(pairs) != assignment["mapped_nonexcluded_pair_count"]:
        _fail("dependency_inconsistent", "selected pair count differs")
    minimum_distance = replay.method.minimum_distance_angstrom
    minimum_angle_sine = replay.method.minimum_angle_sine
    minimum_proper_sine = replay.method.minimum_proper_sine
    effective_coulomb = _divide(
        replay.method.coulomb_coefficient_kilojoule_angstrom_per_mole_e2,
        replay.method.relative_dielectric,
        location="compiled.effective_coulomb",
    )
    digest_fields = (
        "method_binding_sha256",
        "canonical_system_snapshot_sha256",
        "canonical_parameter_artifact_sha256",
        "canonical_method_artifact_sha256",
        "assignment_report_sha256",
        "parameter_assignment_sha256",
        "method_payload_sha256",
        "evaluation_method_sha256",
        "canonical_topology_sha256",
        "source_sha256",
    )
    digest_values = {
        name: _require_sha256(name, binding.get(name)) for name in digest_fields
    }
    component_id = assignment.get("molecule_label")
    if type(component_id) is not str or not component_id:
        _fail("dependency_inconsistent", "assignment molecule label is absent")
    plan_document = _plan_document_from_parts(
        atom_count=atom_count,
        minimum_distance=minimum_distance,
        minimum_angle_sine=minimum_angle_sine,
        minimum_proper_sine=minimum_proper_sine,
        effective_coulomb_coefficient=effective_coulomb,
        bonds=bonds,
        angles=angles,
        propers=propers,
        pairs=pairs,
        bindings={
            "binding_report_sha256": binding_report_sha256,
            "binding_report_snapshot_sha256": binding_report_snapshot_sha256,
            **digest_values,
        },
        component_id=component_id,
    )
    spec = _CompiledSpec(
        atom_count=atom_count,
        minimum_distance=minimum_distance,
        minimum_angle_sine=minimum_angle_sine,
        minimum_proper_sine=minimum_proper_sine,
        effective_coulomb_coefficient=effective_coulomb,
        bonds=bonds,
        angles=angles,
        propers=propers,
        pairs=pairs,
        binding_report_sha256=binding_report_sha256,
        binding_report_snapshot_sha256=binding_report_snapshot_sha256,
        method_binding_sha256=digest_values["method_binding_sha256"],
        canonical_system_snapshot_sha256=digest_values[
            "canonical_system_snapshot_sha256"
        ],
        canonical_parameter_artifact_sha256=digest_values[
            "canonical_parameter_artifact_sha256"
        ],
        canonical_method_artifact_sha256=digest_values[
            "canonical_method_artifact_sha256"
        ],
        assignment_report_sha256=digest_values["assignment_report_sha256"],
        parameter_assignment_sha256=digest_values[
            "parameter_assignment_sha256"
        ],
        method_payload_sha256=digest_values["method_payload_sha256"],
        evaluation_method_sha256=digest_values["evaluation_method_sha256"],
        canonical_topology_sha256=digest_values["canonical_topology_sha256"],
        source_sha256=digest_values["source_sha256"],
        component_id=component_id,
        plan_sha256=_sha256_document(plan_document),
    )
    _require_round_to_nearest_ties_to_even()
    return spec, binding_bytes


@dataclass(frozen=True, init=False, slots=True)
class LinearAlkaneC1C4ReferencePotential:
    """Immutable compiled potential for repeated coordinate evaluation."""

    _spec: _CompiledSpec = field(repr=False)
    _binding_report_snapshot: bytes = field(repr=False)

    @classmethod
    def _create(
        cls,
        binding_report: LinearAlkaneC1C4EvaluationMethodBindingReport,
    ) -> "LinearAlkaneC1C4ReferencePotential":
        spec, binding_bytes = _compile_spec(binding_report)
        potential = object.__new__(cls)
        object.__setattr__(potential, "_spec", spec)
        object.__setattr__(potential, "_binding_report_snapshot", binding_bytes)
        potential._validate()
        return potential

    def _validate(self) -> None:
        if type(self._spec) is not _CompiledSpec:
            raise TypeError("compiled potential must retain its exact spec")
        if type(self._binding_report_snapshot) is not bytes:
            raise TypeError("compiled potential binding snapshot must be exact bytes")
        if hashlib.sha256(self._binding_report_snapshot).hexdigest() != (
            self._spec.binding_report_snapshot_sha256
        ):
            _fail("compiled_potential_tampered", "binding snapshot digest differs")
        digest_fields = {
            "method_binding_sha256": self._spec.method_binding_sha256,
            "canonical_system_snapshot_sha256": (
                self._spec.canonical_system_snapshot_sha256
            ),
            "canonical_parameter_artifact_sha256": (
                self._spec.canonical_parameter_artifact_sha256
            ),
            "canonical_method_artifact_sha256": (
                self._spec.canonical_method_artifact_sha256
            ),
            "assignment_report_sha256": self._spec.assignment_report_sha256,
            "parameter_assignment_sha256": self._spec.parameter_assignment_sha256,
            "method_payload_sha256": self._spec.method_payload_sha256,
            "evaluation_method_sha256": self._spec.evaluation_method_sha256,
            "canonical_topology_sha256": self._spec.canonical_topology_sha256,
            "source_sha256": self._spec.source_sha256,
        }
        plan_document = _plan_document_from_parts(
            atom_count=self._spec.atom_count,
            minimum_distance=self._spec.minimum_distance,
            minimum_angle_sine=self._spec.minimum_angle_sine,
            minimum_proper_sine=self._spec.minimum_proper_sine,
            effective_coulomb_coefficient=self._spec.effective_coulomb_coefficient,
            bonds=self._spec.bonds,
            angles=self._spec.angles,
            propers=self._spec.propers,
            pairs=self._spec.pairs,
            bindings={
                "binding_report_sha256": self._spec.binding_report_sha256,
                "binding_report_snapshot_sha256": (
                    self._spec.binding_report_snapshot_sha256
                ),
                **digest_fields,
            },
            component_id=self._spec.component_id,
        )
        if _sha256_document(plan_document) != self._spec.plan_sha256:
            _fail("compiled_potential_tampered", "compiled plan digest differs")

    @property
    def atom_count(self) -> int:
        self._validate()
        return self._spec.atom_count

    @property
    def component_id(self) -> str:
        self._validate()
        return self._spec.component_id

    @property
    def compiled_plan_sha256(self) -> str:
        self._validate()
        return self._spec.plan_sha256

    def evaluate(
        self,
        coordinates: torch.Tensor,
    ) -> LinearAlkaneC1C4ReferenceKernelResult:
        self._validate()
        return _evaluate_spec(self._spec, coordinates)

    def to_dict(self) -> dict[str, Any]:
        self._validate()
        return {
            "protocol_schema_id": _FROZEN_PROTOCOL_SCHEMA_ID,
            "protocol_sha256": _FROZEN_PROTOCOL_SHA256,
            "claim_scope": _FROZEN_CLAIM_SCOPE,
            "status": "bounded_nonphysical_reference_potential_compiled",
            "component_id": self._spec.component_id,
            "atom_count": self._spec.atom_count,
            "binding_report_sha256": self._spec.binding_report_sha256,
            "binding_report_snapshot_sha256": (
                self._spec.binding_report_snapshot_sha256
            ),
            "method_binding_sha256": self._spec.method_binding_sha256,
            "compiled_plan_sha256": self._spec.plan_sha256,
            "bond_term_count": len(self._spec.bonds),
            "angle_term_count": len(self._spec.angles),
            "proper_term_count": len(self._spec.propers),
            "selected_pair_count": len(self._spec.pairs),
            "base_v1_method_energy_kernel_status": "missing_unchanged",
            "overlay_method_kernel_status": "available_bounded_nonphysical",
            "production_runtime_kernel_available": False,
            "runtime_eligible": False,
            "engine_dispatch_registered": False,
            "scientifically_validated": False,
            "claim_safe": False,
        }


def compile_linear_alkane_c1_c4_reference_potential(
    binding_report: LinearAlkaneC1C4EvaluationMethodBindingReport,
) -> LinearAlkaneC1C4ReferencePotential:
    """Compile one exact successful binding report into a reusable potential."""

    if type(binding_report) is not LinearAlkaneC1C4EvaluationMethodBindingReport:
        raise TypeError("binding_report must be an exact C1-C4 binding report")
    return LinearAlkaneC1C4ReferencePotential._create(binding_report)


def evaluate_linear_alkane_c1_c4_reference_kernel(
    potential: LinearAlkaneC1C4ReferencePotential,
    coordinates: torch.Tensor,
) -> LinearAlkaneC1C4ReferenceKernelResult:
    """Evaluate an exact compiled potential at one coordinate snapshot."""

    if type(potential) is not LinearAlkaneC1C4ReferencePotential:
        raise TypeError("potential must be an exact C1-C4 reference potential")
    return potential.evaluate(coordinates)


def serialize_linear_alkane_c1_c4_reference_kernel_result(
    result: LinearAlkaneC1C4ReferenceKernelResult,
) -> bytes:
    """Serialize an exact validated kernel result as canonical JSON."""

    if type(result) is not LinearAlkaneC1C4ReferenceKernelResult:
        raise TypeError("result must be an exact C1-C4 reference-kernel result")
    result._validate()
    return _canonical_json_bytes(result.to_dict())


__all__ = [
    "LINEAR_ALKANE_METHOD_KERNEL_ALGORITHM_ID",
    "LINEAR_ALKANE_METHOD_KERNEL_CLAIM_SCOPE",
    "LINEAR_ALKANE_METHOD_KERNEL_POLICY_ID",
    "LINEAR_ALKANE_METHOD_KERNEL_PROTOCOL_SCHEMA_ID",
    "LINEAR_ALKANE_METHOD_KERNEL_PROTOCOL_SCHEMA_VERSION",
    "LINEAR_ALKANE_METHOD_KERNEL_PROTOCOL_SHA256",
    "LINEAR_ALKANE_REFERENCE_KERNEL_FORCE_DEFINITION",
    "LINEAR_ALKANE_REFERENCE_KERNEL_RESULT_SCHEMA_ID",
    "LINEAR_ALKANE_REFERENCE_KERNEL_RESULT_SCHEMA_VERSION",
    "LINEAR_ALKANE_REFERENCE_KERNEL_VIRIAL_CONVENTION_ID",
    "LINEAR_ALKANE_REFERENCE_KERNEL_VIRIAL_DEFINITION",
    "LinearAlkaneC1C4ReferenceKernelResult",
    "LinearAlkaneC1C4ReferencePotential",
    "LinearAlkaneReferenceKernelClassResult",
    "LinearAlkaneReferenceKernelError",
    "LinearAlkaneReferenceKernelTermResult",
    "compile_linear_alkane_c1_c4_reference_potential",
    "evaluate_linear_alkane_c1_c4_reference_kernel",
    "linear_alkane_method_kernel_protocol_bytes",
    "linear_alkane_method_kernel_protocol_document",
    "serialize_linear_alkane_c1_c4_reference_kernel_result",
]
