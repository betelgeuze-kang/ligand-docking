"""Bounded nonphysical C1-C4 scalar-energy diagnostic evaluator.

The evaluator in this module is owned by its diagnostic schema.  It consumes
one exact method-binding report and replays that report's immutable inputs.  It
does not change the bound method artifact's explicit ``energy kernel missing``
state and does not define forces, virial, autograd, minimization, simulation,
runtime dispatch, scientific validity, or product authority.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
import re
import struct
from typing import Any, Iterable

from betelgeuze_engine_v2.molecular.bonded_inventory import (
    CanonicalAngleIdentity,
    CanonicalBondIdentity,
)
from betelgeuze_engine_v2.molecular.serialization import (
    deserialize_all_atom_system,
    serialize_all_atom_system,
)

from .linear_alkane_assignment import (
    serialize_linear_alkane_c1_c4_parameter_assignment_report,
)
from .linear_alkane_evaluation_method import (
    serialize_linear_alkane_c1_c4_evaluation_method,
)
from .linear_alkane_method_binding import (
    LinearAlkaneC1C4EvaluationMethodBindingReport,
    _LinearAlkaneC1C4ScalarEnergyDiagnosticReplay,
)
from .linear_alkane_parameters import (
    serialize_linear_alkane_c1_c4_parameter_set,
)
from .term_inventory import (
    CanonicalPairIdentity,
    CanonicalProperTorsionIdentity,
)


_FROZEN_PROTOCOL_SCHEMA_VERSION = "1.0.0"
_FROZEN_PROTOCOL_SCHEMA_ID = (
    "betelgeuze.linear_alkane_c1_c4_scalar_energy_diagnostic_protocol/"
    f"{_FROZEN_PROTOCOL_SCHEMA_VERSION}"
)
_FROZEN_REPORT_SCHEMA_VERSION = "1.0.0"
_FROZEN_REPORT_SCHEMA_ID = (
    "betelgeuze.linear_alkane_c1_c4_scalar_energy_diagnostic/"
    f"{_FROZEN_REPORT_SCHEMA_VERSION}"
)
_FROZEN_DIAGNOSTIC_POLICY_ID = (
    "method_binding_single_replay_diagnostic_owned_scalar_evaluator/1.0.0"
)
_FROZEN_SCALAR_ENERGY_ALGORITHM_ID = (
    "cpu_binary64_literal_parameter_forms_direct_uncut_flat_fsum/1.0.0"
)
_FROZEN_CLAIM_SCOPE = (
    "bounded_nonphysical_c1_c4_scalar_energy_diagnostic_only"
)
_FROZEN_BINARY64_ENCODING_ID = "ieee754_binary64_big_endian_hex/1.0.0"
_FROZEN_ENERGY_UNIT = "kilojoule_per_mole"
_FROZEN_PARAMETER_PROTOCOL_SHA256 = (
    "28219cd1492b31f3d151048e7ad9db297fe7a896d081b098e901f142f6d4602a"
)
_FROZEN_ASSIGNMENT_SCHEMA_ID = (
    "betelgeuze.linear_alkane_c1_c4_parameter_assignment/1.0.0"
)
_FROZEN_ASSIGNMENT_POLICY_ID = (
    "fresh_snapshot_exact_environment_term_and_pair_parameter_mapping/1.0.0"
)
_FROZEN_METHOD_SCHEMA_ID = (
    "betelgeuze.linear_alkane_c1_c4_evaluation_method/1.0.0"
)
_FROZEN_METHOD_PROTOCOL_SHA256 = (
    "7a8416632d83cab3e32ebbbdc43549d59b5a4efb472283d07f773ad66de461da"
)
_FROZEN_METHOD_BINDING_SCHEMA_ID = (
    "betelgeuze.linear_alkane_c1_c4_evaluation_method_binding/1.0.0"
)
_FROZEN_METHOD_BINDING_SCHEMA_VERSION = "1.0.0"
_FROZEN_METHOD_BINDING_POLICY_ID = (
    "fresh_system_parameter_method_snapshots_input_envelope_assignment_and_"
    "geometry_domain_no_evaluation/1.0.0"
)
_FROZEN_METHOD_BINDING_CLAIM_SCOPE = (
    "bounded_nonphysical_c1_c4_method_assignment_binding_only_no_evaluation"
)
_FROZEN_PARAMETER_SET_SCHEMA_ID = (
    "betelgeuze.linear_alkane_c1_c4_parameter_set/1.0.0"
)
_FROZEN_METHOD_PROTOCOL_SCHEMA_ID = (
    "betelgeuze.linear_alkane_c1_c4_evaluation_method_protocol/1.0.0"
)
_FROZEN_DIAGNOSTIC_STATUSES = frozenset(
    {
        "invalid_system",
        "unsupported_system",
        "method_incompatible",
        "contract_fixture_scalar_energy_evaluated",
    }
)
_FROZEN_PAIR_CLASSES = (
    "excluded_1_2",
    "excluded_1_3",
    "one_four_separate",
    "full_nonbonded",
)
_FROZEN_UPSTREAM_FALSE_GATES = (
    "evaluation_executed",
    "energy_evaluated",
    "forces_evaluated",
    "virial_evaluated",
    "production_evaluation_method_defined",
    "production_parameter_assignment_complete",
    "parameterability_assessed",
    "parameterizable",
    "global_parameter_coverage_complete",
    "physics_supported",
    "scientifically_validated",
    "runtime_eligible",
    "execution_authorized",
    "energy_evaluation_authorized",
    "force_evaluation_authorized",
    "virial_evaluation_authorized",
    "minimization_authorized",
    "simulation_ready",
    "claim_safe",
)
_FROZEN_INPUT_ENVELOPE_KEYS = frozenset(
    {
        "canonical_snapshot_normalization",
        "cell_periodic_flags",
        "cell_present",
        "cell_vectors_device_index",
        "cell_vectors_device_type",
        "cell_vectors_dtype",
        "cell_vectors_shape",
        "coordinate_model_count",
        "coordinate_unit",
        "coordinates_contiguous",
        "coordinates_device_index",
        "coordinates_device_type",
        "coordinates_dtype",
        "coordinates_layout",
        "coordinates_materialized",
        "coordinates_requires_grad",
        "coordinates_shape",
        "device_preservation_status",
        "observation_policy_id",
    }
)
_FROZEN_METHOD_BINDING_COMPATIBILITY_CODES = (
    "canonical_input_snapshot_round_trip_and_envelope_bound",
    "assignment_contract_fixture_mapped",
    "parameter_protocol_matches_method_contract",
    "assignment_schema_and_policy_match_method_contract",
    "force_field_unit_system_matches_method_contract",
    "atom_count_within_direct_reference_limit",
    "single_coordinate_model",
    "coordinate_unit_angstrom",
    "coordinate_dtype_float64",
    "coordinate_device_cpu",
    "coordinate_layout_strided_materialized",
    "coordinates_require_no_grad",
    "cell_free_nonperiodic_input",
    "exact_all_pair_inventory_bound",
    "exact_nonexcluded_pair_subset_covered",
    "all_parameter_deferred_method_fields_explicitly_closed",
    "bond_distances_above_method_minimum",
    "angle_legs_and_sines_above_method_minimum",
    "proper_bonds_and_sines_above_method_minimum",
    "selected_pair_distances_above_method_minimum",
    "geometry_intermediates_finite",
)
_FROZEN_METHOD_BINDING_REPORT_KEYS = frozenset(
    {
        "angle_assignment_count",
        "applicability_report_sha256",
        "assignment_policy_id",
        "assignment_report_sha256",
        "assignment_schema_id",
        "assignment_status",
        "atom_assignment_count",
        "binding_policy_id",
        "blockers",
        "bond_assignment_count",
        "bounded_contract_fixture_assignment_complete",
        "bounded_contract_fixture_geometry_domain_assessed",
        "bounded_contract_fixture_method_assignment_binding_complete",
        "bounded_nonphysical_evaluation_method_contract_complete",
        "canonical_method_artifact_sha256",
        "canonical_parameter_artifact_sha256",
        "canonical_snapshot_coordinates_device_type",
        "canonical_system_snapshot_sha256",
        "canonical_topology_sha256",
        "claim_safe",
        "claim_scope",
        "compatibility_results",
        "device_preservation_status",
        "energy_evaluated",
        "energy_evaluation_authorized",
        "evaluation_executed",
        "evaluation_method_sha256",
        "excluded_pair_count",
        "execution_authorized",
        "failed_compatibility_codes",
        "force_evaluation_authorized",
        "force_field_unit_system_id",
        "forces_evaluated",
        "geometry_domain_assessment_status",
        "global_parameter_coverage_complete",
        "input_execution_envelope",
        "input_execution_envelope_authentication_status",
        "input_execution_envelope_sha256",
        "inventory_report_sha256",
        "mapped_nonexcluded_pair_count",
        "method_binding_sha256",
        "method_binding_status",
        "method_covered_nonexcluded_pair_count",
        "method_id",
        "method_payload_sha256",
        "method_protocol_schema_id",
        "method_protocol_sha256",
        "method_schema_id",
        "method_version",
        "minimization_authorized",
        "pair_assignment_count",
        "pair_class_counts",
        "pair_classification_policy_id",
        "parameter_assignment_sha256",
        "parameter_payload_sha256",
        "parameter_protocol_sha256",
        "parameter_set_id",
        "parameter_set_schema_id",
        "parameter_set_sha256",
        "parameter_set_version",
        "parameterability_assessed",
        "parameterizable",
        "physics_supported",
        "production_evaluation_method_defined",
        "production_parameter_assignment_complete",
        "proper_assignment_count",
        "report_sha256",
        "runtime_eligible",
        "schema_id",
        "schema_version",
        "scientifically_validated",
        "simulation_ready",
        "source_authentication_status",
        "source_format",
        "source_sha256",
        "typing_report_sha256",
        "virial_evaluated",
        "virial_evaluation_authorized",
    }
)
_FROZEN_METHOD_BINDING_BASE_BLOCKERS = (
    "numeric_parameter_and_method_values_are_nonphysical_contract_fixtures",
    "geometry_domain_check_is_compatibility_only_no_energy_evaluation",
    "energy_force_and_virial_kernels_missing",
    "scientific_fit_reference_and_validation_missing",
    "licensed_method_provenance_and_review_missing",
    "bounded_n_le_14_direct_all_pair_reference_is_not_scaling_evidence",
    "cell_free_nonperiodic_cpu_float64_single_model_only",
    "production_parameterability_physics_runtime_and_claim_authority_prohibited",
    "digests_and_input_observations_are_binding_not_authentication",
)
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")

LINEAR_ALKANE_SCALAR_ENERGY_DIAGNOSTIC_PROTOCOL_SCHEMA_VERSION = (
    _FROZEN_PROTOCOL_SCHEMA_VERSION
)
LINEAR_ALKANE_SCALAR_ENERGY_DIAGNOSTIC_PROTOCOL_SCHEMA_ID = (
    _FROZEN_PROTOCOL_SCHEMA_ID
)
LINEAR_ALKANE_SCALAR_ENERGY_DIAGNOSTIC_SCHEMA_VERSION = (
    _FROZEN_REPORT_SCHEMA_VERSION
)
LINEAR_ALKANE_SCALAR_ENERGY_DIAGNOSTIC_SCHEMA_ID = _FROZEN_REPORT_SCHEMA_ID
LINEAR_ALKANE_SCALAR_ENERGY_DIAGNOSTIC_POLICY_ID = _FROZEN_DIAGNOSTIC_POLICY_ID
LINEAR_ALKANE_SCALAR_ENERGY_ALGORITHM_ID = _FROZEN_SCALAR_ENERGY_ALGORITHM_ID
LINEAR_ALKANE_SCALAR_ENERGY_DIAGNOSTIC_CLAIM_SCOPE = _FROZEN_CLAIM_SCOPE
LINEAR_ALKANE_SCALAR_ENERGY_DIAGNOSTIC_STATUSES = _FROZEN_DIAGNOSTIC_STATUSES


class LinearAlkaneScalarEnergyDiagnosticError(ValueError):
    """Fail-closed scalar diagnostic error with a stable code."""

    def __init__(self, code: str, message: str) -> None:
        if type(code) is not str or not code:
            raise TypeError("diagnostic error code must be an exact string")
        self.code = code
        self.blockers = (f"linear_alkane_scalar_energy_{code}",)
        super().__init__(message)


def _fail(code: str, message: str) -> None:
    raise LinearAlkaneScalarEnergyDiagnosticError(code, message)


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
        raise TypeError(f"{name} must be an exact lowercase SHA-256 digest")
    return value


def _finite(value: Any, *, location: str) -> float:
    if type(value) is not float:
        _fail("nonfinite_result", f"{location} must be an exact binary64 value")
    if not math.isfinite(value):
        _fail("nonfinite_result", f"{location} must remain finite")
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


def _hypot(vector: "Vector3", *, location: str) -> float:
    try:
        result = math.hypot(vector[0], vector[1], vector[2])
    except (OverflowError, ValueError) as exc:
        _fail("nonfinite_result", f"{location} hypot failed: {exc}")
    return _finite(result, location=location)


def _finite_fsum(values: Iterable[float], *, location: str) -> float:
    try:
        result = math.fsum(values)
    except (OverflowError, ValueError) as exc:
        _fail("nonfinite_result", f"{location} fsum failed: {exc}")
    return _finite(result, location=location)


def _cos(value: float, *, location: str) -> float:
    try:
        result = math.cos(value)
    except (OverflowError, ValueError) as exc:
        _fail("nonfinite_result", f"{location} cos failed: {exc}")
    return _finite(result, location=location)


def _atan2(y: float, x: float, *, location: str) -> float:
    try:
        result = math.atan2(y, x)
    except (OverflowError, ValueError) as exc:
        _fail("nonfinite_result", f"{location} atan2 failed: {exc}")
    return _finite(result, location=location)


Vector3 = tuple[float, float, float]


def _vector(values: Iterable[float], *, location: str) -> Vector3:
    result = tuple(
        _finite(value, location=f"{location}[{index}]")
        for index, value in enumerate(values)
    )
    if len(result) != 3:
        _fail("dependency_inconsistent", f"{location} must have three components")
    return result  # type: ignore[return-value]


def _difference(first: Vector3, second: Vector3, *, location: str) -> Vector3:
    return _vector(
        (
            _subtract(second[index], first[index], location=f"{location}[{index}]")
            for index in range(3)
        ),
        location=location,
    )


def _unit(vector: Vector3, length: float, *, location: str) -> Vector3:
    return _vector(
        (
            _divide(value, length, location=f"{location}[{index}]")
            for index, value in enumerate(vector)
        ),
        location=location,
    )


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
            _subtract(first, second, location=f"{location}[{index}]")
            for index, (first, second) in enumerate(products)
        ),
        location=location,
    )


def _dot(left: Vector3, right: Vector3, *, location: str) -> float:
    products = tuple(
        _multiply(left[index], right[index], location=f"{location}[{index}]")
        for index in range(3)
    )
    return _finite_fsum(products, location=location)


def _require_round_to_nearest_ties_to_even() -> None:
    half_ulp_above_one = math.ldexp(1.0, -53)
    half_ulp_below_one = math.ldexp(1.0, -54)
    rounded_above = 1.0 + half_ulp_above_one
    rounded_below = 1.0 - half_ulp_below_one
    if rounded_above != 1.0 or rounded_below != 1.0:
        _fail(
            "rounding_mode_incompatible",
            "scalar diagnostic requires round-to-nearest ties-to-even",
        )


def _protocol_document() -> dict[str, Any]:
    return {
        "schema_id": _FROZEN_PROTOCOL_SCHEMA_ID,
        "schema_version": _FROZEN_PROTOCOL_SCHEMA_VERSION,
        "report_schema_id": _FROZEN_REPORT_SCHEMA_ID,
        "diagnostic_policy_id": _FROZEN_DIAGNOSTIC_POLICY_ID,
        "scalar_energy_algorithm_id": _FROZEN_SCALAR_ENERGY_ALGORITHM_ID,
        "claim_scope": _FROZEN_CLAIM_SCOPE,
        "parameter_protocol_sha256": _FROZEN_PARAMETER_PROTOCOL_SHA256,
        "assignment_schema_id": _FROZEN_ASSIGNMENT_SCHEMA_ID,
        "assignment_policy_id": _FROZEN_ASSIGNMENT_POLICY_ID,
        "method_schema_id": _FROZEN_METHOD_SCHEMA_ID,
        "method_protocol_sha256": _FROZEN_METHOD_PROTOCOL_SHA256,
        "method_binding_schema_id": _FROZEN_METHOD_BINDING_SCHEMA_ID,
        "method_binding_policy_id": _FROZEN_METHOD_BINDING_POLICY_ID,
        "evaluator_ownership": {
            "owner": "diagnostic_schema_owned_scalar_evaluator",
            "bound_method_artifact_energy_kernel_status": "missing",
            "bounded_diagnostic_scalar_evaluator_available": True,
            "method_owned_energy_kernel_available": False,
            "production_runtime_energy_kernel_available": False,
        },
        "input_replay": {
            "input_type": (
                "exact_linear_alkane_c1_c4_evaluation_method_binding_report"
            ),
            "policy": "one_same_analysis_immutable_snapshot_replay_capsule",
            "raw_system_parameter_method_api": "prohibited",
            "live_tensor_reread_after_binding": "prohibited",
            "required_binding_status": "contract_fixture_method_bound",
            "required_geometry_status": (
                "passed_bounded_domain_check_no_evaluation"
            ),
        },
        "numeric_primitives": {
            "coordinate_scalar_source": "canonical_cpu_float64_snapshot_item",
            "vector_component_order": ["x", "y", "z"],
            "difference": "right_component-left_component",
            "length": "math_hypot_dx_dy_dz",
            "dot": "component_products_then_math_fsum_xyz",
            "cross": "explicit_two_products_then_subtract_per_xyz_component",
            "finite_check": "after_every_primitive_and_reduction",
            "rounding_mode": "round_to_nearest_ties_to_even_required",
            "rounding_mode_guard": (
                "binary64_tie_sensitive_preflight_and_postflight"
            ),
            "underflow": "allowed",
            "reported_negative_zero": "canonicalize_to_positive_zero",
            "intermediate_signed_zero": "preserve",
            "clamp_softcore_epsilon_regularization": "prohibited",
            "partial_report_after_failure": "prohibited",
            "cross_platform_libm_bit_replay_status": "not_assessed",
        },
        "bond_algorithm": [
            "d=coordinate_difference_rj_minus_ri_xyz",
            "r=math_hypot_d",
            "require_r_gt_minimum_distance",
            "delta=r-r0",
            "half_k=0.5*k",
            "temporary=half_k*delta",
            "energy=temporary*delta",
        ],
        "angle_algorithm": [
            "u=ri-rj;v=rk-rj",
            "ru=math_hypot_u;rv=math_hypot_v",
            "require_ru_and_rv_gt_minimum_distance",
            "normalized_cross=cross(u/ru,v/rv)",
            "require_math_hypot_normalized_cross_gt_minimum_angle_sine",
            "raw_cross=cross(u,v)",
            "raw_cross_norm=math_hypot_raw_cross_and_require_nonzero",
            "raw_dot=math_fsum_xyz_component_products",
            "theta=math_atan2_raw_cross_norm_raw_dot",
            "delta=theta-theta0",
            "half_k=0.5*k",
            "temporary=half_k*delta",
            "energy=temporary*delta",
        ],
        "proper_algorithm": [
            "b1=rj-ri;b2=rk-rj;b3=rl-rk",
            "require_each_math_hypot_bond_gt_minimum_distance",
            "require_hypot_cross_b1hat_b2hat_and_b2hat_b3hat_gt_minimum_sine",
            "n1=cross_raw_b1_b2;n2=cross_raw_b2_b3",
            "require_raw_normal_norms_nonzero",
            "b2hat=b2/norm_b2",
            "y=dot_math_fsum_xyz(cross(n1,n2),b2hat)",
            "x=dot_math_fsum_xyz(n1,n2)",
            "require_not_both_x_y_zero",
            "phi=math_atan2_y_x",
            "for_each_component_nphi=float(n)*phi;arg=nphi-phase;"
            "cosine=math_cos_arg;one_plus=1.0+cosine;energy=amplitude*one_plus",
            "proper_energy=math_fsum_canonical_component_energy_sequence",
        ],
        "lennard_jones_algorithm": [
            "s=sigma/r",
            "s2=s*s",
            "s4=s2*s2",
            "s6=s4*s2",
            "s12=s6*s6",
            "shape=s12-s6",
            "four_epsilon=4.0*epsilon",
            "base_lj=four_epsilon*shape",
        ],
        "coulomb_algorithm": [
            "effective_coefficient=k_e/relative_dielectric_once_per_evaluation",
            "temporary_1=effective_coefficient*q_i",
            "temporary_2=temporary_1*q_j",
            "base_coulomb=temporary_2/r",
        ],
        "pair_algorithm": {
            "source": "canonical_assignment_pair_rows",
            "excluded_1_2": "do_not_calculate_distance_or_energy",
            "excluded_1_3": "do_not_calculate_distance_or_energy",
            "one_four_separate": (
                "scale_each_base_exactly_once_then_math_fsum_lj_coulomb"
            ),
            "full_nonbonded": (
                "no_scale_multiplication_then_math_fsum_lj_coulomb"
            ),
            "assigned_sigma_epsilon": "consume_without_recombination",
        },
        "accumulation": {
            "term_sequence": (
                "canonical_bonds_then_angles_then_propers_then_selected_pairs"
            ),
            "total": "one_math_fsum_over_flat_term_energy_sequence",
            "class_subtotals": "reporting_only_not_inputs_to_total",
            "lj_coulomb_subtotals": "reporting_only_not_inputs_to_total",
            "empty_selected_pairs": "math_fsum_empty_is_positive_zero_after_full_inventory_check",
        },
        "output": {
            "numeric_encoding": _FROZEN_BINARY64_ENCODING_ID,
            "energy_unit": _FROZEN_ENERGY_UNIT,
            "term_decomposition": ["bond", "angle", "proper", "selected_pair"],
            "force": "not_defined",
            "virial": "not_defined",
            "gradient": "not_defined",
        },
    }


_FROZEN_PROTOCOL_DOCUMENT = _protocol_document()
_FROZEN_PROTOCOL_BYTES = _canonical_json_bytes(_FROZEN_PROTOCOL_DOCUMENT)
_FROZEN_PROTOCOL_SHA256 = hashlib.sha256(_FROZEN_PROTOCOL_BYTES).hexdigest()

LINEAR_ALKANE_SCALAR_ENERGY_DIAGNOSTIC_PROTOCOL_SHA256 = (
    _FROZEN_PROTOCOL_SHA256
)


def linear_alkane_scalar_energy_diagnostic_protocol_document() -> dict[str, Any]:
    """Return a fresh copy of the exact diagnostic evaluator protocol."""

    return json.loads(_FROZEN_PROTOCOL_BYTES.decode("ascii"))


def linear_alkane_scalar_energy_diagnostic_protocol_bytes() -> bytes:
    """Return the exact diagnostic evaluator protocol bytes."""

    return bytes(_FROZEN_PROTOCOL_BYTES)


@dataclass(frozen=True, order=True, slots=True)
class LinearAlkaneBondScalarEnergyTerm:
    identity: CanonicalBondIdentity
    parameter_id: str
    distance_angstrom: float
    displacement_angstrom: float
    energy_kilojoule_per_mole: float

    def __post_init__(self) -> None:
        if type(self.identity) is not CanonicalBondIdentity:
            raise TypeError("bond identity must be exact")
        CanonicalBondIdentity.__post_init__(self.identity)
        if type(self.parameter_id) is not str or not self.parameter_id:
            raise TypeError("bond parameter_id must be an exact string")
        _finite(self.distance_angstrom, location="bond.distance")
        _finite(self.displacement_angstrom, location="bond.displacement")
        _finite(self.energy_kilojoule_per_mole, location="bond.energy")

    def to_dict(self) -> dict[str, Any]:
        self.__post_init__()
        return {
            "identity": self.identity.to_dict(),
            "parameter_id": self.parameter_id,
            "distance_angstrom_binary64": _binary64_hex(
                self.distance_angstrom,
                location="bond.distance",
            ),
            "displacement_angstrom_binary64": _binary64_hex(
                self.displacement_angstrom,
                location="bond.displacement",
            ),
            "energy_kilojoule_per_mole_binary64": _binary64_hex(
                self.energy_kilojoule_per_mole,
                location="bond.energy",
            ),
        }


@dataclass(frozen=True, order=True, slots=True)
class LinearAlkaneAngleScalarEnergyTerm:
    identity: CanonicalAngleIdentity
    parameter_id: str
    angle_radian: float
    displacement_radian: float
    energy_kilojoule_per_mole: float

    def __post_init__(self) -> None:
        if type(self.identity) is not CanonicalAngleIdentity:
            raise TypeError("angle identity must be exact")
        CanonicalAngleIdentity.__post_init__(self.identity)
        if type(self.parameter_id) is not str or not self.parameter_id:
            raise TypeError("angle parameter_id must be an exact string")
        _finite(self.angle_radian, location="angle.coordinate")
        _finite(self.displacement_radian, location="angle.displacement")
        _finite(self.energy_kilojoule_per_mole, location="angle.energy")

    def to_dict(self) -> dict[str, Any]:
        self.__post_init__()
        return {
            "identity": self.identity.to_dict(),
            "parameter_id": self.parameter_id,
            "angle_radian_binary64": _binary64_hex(
                self.angle_radian,
                location="angle.coordinate",
            ),
            "displacement_radian_binary64": _binary64_hex(
                self.displacement_radian,
                location="angle.displacement",
            ),
            "energy_kilojoule_per_mole_binary64": _binary64_hex(
                self.energy_kilojoule_per_mole,
                location="angle.energy",
            ),
        }


@dataclass(frozen=True, order=True, slots=True)
class LinearAlkaneProperComponentScalarEnergy:
    periodicity: int
    phase_radian: float
    amplitude_kilojoule_per_mole: float
    energy_kilojoule_per_mole: float

    def __post_init__(self) -> None:
        if type(self.periodicity) is not int or not 1 <= self.periodicity <= 6:
            raise TypeError("proper periodicity must be an exact integer in [1,6]")
        _finite(self.phase_radian, location="proper_component.phase")
        _finite(
            self.amplitude_kilojoule_per_mole,
            location="proper_component.amplitude",
        )
        _finite(
            self.energy_kilojoule_per_mole,
            location="proper_component.energy",
        )

    def to_dict(self) -> dict[str, Any]:
        self.__post_init__()
        return {
            "periodicity": self.periodicity,
            "phase_radian_binary64": _binary64_hex(
                self.phase_radian,
                location="proper_component.phase",
            ),
            "amplitude_kilojoule_per_mole_binary64": _binary64_hex(
                self.amplitude_kilojoule_per_mole,
                location="proper_component.amplitude",
            ),
            "energy_kilojoule_per_mole_binary64": _binary64_hex(
                self.energy_kilojoule_per_mole,
                location="proper_component.energy",
            ),
        }


@dataclass(frozen=True, order=True, slots=True)
class LinearAlkaneProperScalarEnergyTerm:
    identity: CanonicalProperTorsionIdentity
    parameter_id: str
    dihedral_radian: float
    components: tuple[LinearAlkaneProperComponentScalarEnergy, ...]
    energy_kilojoule_per_mole: float

    def __post_init__(self) -> None:
        if type(self.identity) is not CanonicalProperTorsionIdentity:
            raise TypeError("proper identity must be exact")
        CanonicalProperTorsionIdentity.__post_init__(self.identity)
        if type(self.parameter_id) is not str or not self.parameter_id:
            raise TypeError("proper parameter_id must be an exact string")
        _finite(self.dihedral_radian, location="proper.coordinate")
        if type(self.components) is not tuple or not self.components:
            raise TypeError("proper components must be a non-empty exact tuple")
        if not all(
            type(value) is LinearAlkaneProperComponentScalarEnergy
            for value in self.components
        ):
            raise TypeError("proper components must use the exact result type")
        for value in self.components:
            value.__post_init__()
        if self.components != tuple(sorted(self.components)):
            raise ValueError("proper component results must be canonically sorted")
        _finite(self.energy_kilojoule_per_mole, location="proper.energy")
        expected_energy = _finite_fsum(
            (value.energy_kilojoule_per_mole for value in self.components),
            location="proper.component_energy_validation_fsum",
        )
        if self.energy_kilojoule_per_mole != expected_energy:
            raise ValueError("proper energy must equal the component math.fsum")

    def to_dict(self) -> dict[str, Any]:
        self.__post_init__()
        return {
            "identity": self.identity.to_dict(),
            "parameter_id": self.parameter_id,
            "dihedral_radian_binary64": _binary64_hex(
                self.dihedral_radian,
                location="proper.coordinate",
            ),
            "components": [value.to_dict() for value in self.components],
            "energy_kilojoule_per_mole_binary64": _binary64_hex(
                self.energy_kilojoule_per_mole,
                location="proper.energy",
            ),
        }


@dataclass(frozen=True, order=True, slots=True)
class LinearAlkanePairScalarEnergyTerm:
    identity: CanonicalPairIdentity
    shortest_graph_distance: int
    interaction_class: str
    lj_resolution_status: str
    lj_override_id: str | None
    distance_angstrom: float
    lj_base_energy_kilojoule_per_mole: float
    coulomb_base_energy_kilojoule_per_mole: float
    lj_energy_scale: float | None
    coulomb_energy_scale: float | None
    lj_energy_kilojoule_per_mole: float
    coulomb_energy_kilojoule_per_mole: float
    pair_energy_kilojoule_per_mole: float

    def __post_init__(self) -> None:
        if type(self.identity) is not CanonicalPairIdentity:
            raise TypeError("pair identity must be exact")
        CanonicalPairIdentity.__post_init__(self.identity)
        if (
            type(self.shortest_graph_distance) is not int
            or self.shortest_graph_distance < 3
        ):
            raise TypeError("selected pair graph distance must be an integer >=3")
        if type(self.interaction_class) is not str:
            raise TypeError("pair interaction class must be an exact string")
        if self.interaction_class not in {"one_four_separate", "full_nonbonded"}:
            raise ValueError("energy result may contain only selected pair classes")
        if (
            self.interaction_class == "one_four_separate"
            and self.shortest_graph_distance != 3
        ) or (
            self.interaction_class == "full_nonbonded"
            and self.shortest_graph_distance <= 3
        ):
            raise ValueError("selected pair class and graph distance disagree")
        if type(self.lj_resolution_status) is not str:
            raise TypeError("pair LJ resolution status must be an exact string")
        if self.lj_resolution_status not in {
            "lorentz_berthelot",
            "exact_pair_override",
        }:
            raise ValueError("pair LJ resolution status is inconsistent")
        if self.lj_resolution_status == "exact_pair_override":
            if type(self.lj_override_id) is not str or not self.lj_override_id:
                raise TypeError("override pair must carry an exact override ID")
        elif self.lj_override_id is not None:
            raise ValueError("combined pair cannot carry an override ID")
        for name in (
            "distance_angstrom",
            "lj_base_energy_kilojoule_per_mole",
            "coulomb_base_energy_kilojoule_per_mole",
            "lj_energy_kilojoule_per_mole",
            "coulomb_energy_kilojoule_per_mole",
            "pair_energy_kilojoule_per_mole",
        ):
            _finite(getattr(self, name), location=f"pair.{name}")
        if self.interaction_class == "one_four_separate":
            if type(self.lj_energy_scale) is not float or type(
                self.coulomb_energy_scale
            ) is not float:
                raise TypeError("one-four pair must carry exact float scales")
            _finite(self.lj_energy_scale, location="pair.lj_scale")
            _finite(self.coulomb_energy_scale, location="pair.coulomb_scale")
            expected_lj = _multiply(
                self.lj_energy_scale,
                self.lj_base_energy_kilojoule_per_mole,
                location="pair.expected_scaled_lj",
            )
            expected_coulomb = _multiply(
                self.coulomb_energy_scale,
                self.coulomb_base_energy_kilojoule_per_mole,
                location="pair.expected_scaled_coulomb",
            )
        elif self.lj_energy_scale is not None or self.coulomb_energy_scale is not None:
            raise ValueError("full pair must not carry scale fields")
        else:
            expected_lj = self.lj_base_energy_kilojoule_per_mole
            expected_coulomb = self.coulomb_base_energy_kilojoule_per_mole
        if self.lj_energy_kilojoule_per_mole != expected_lj:
            raise ValueError("pair applied LJ energy is inconsistent")
        if self.coulomb_energy_kilojoule_per_mole != expected_coulomb:
            raise ValueError("pair applied Coulomb energy is inconsistent")
        expected_pair = _finite_fsum(
            (
                self.lj_energy_kilojoule_per_mole,
                self.coulomb_energy_kilojoule_per_mole,
            ),
            location="pair.expected_inner_fsum",
        )
        if self.pair_energy_kilojoule_per_mole != expected_pair:
            raise ValueError("pair energy must equal applied LJ/Coulomb math.fsum")

    def to_dict(self) -> dict[str, Any]:
        self.__post_init__()
        return {
            "identity": self.identity.to_dict(),
            "shortest_graph_distance": self.shortest_graph_distance,
            "interaction_class": self.interaction_class,
            "lj_resolution_status": self.lj_resolution_status,
            "lj_override_id": self.lj_override_id,
            "distance_angstrom_binary64": _binary64_hex(
                self.distance_angstrom,
                location="pair.distance",
            ),
            "lj_base_energy_kilojoule_per_mole_binary64": _binary64_hex(
                self.lj_base_energy_kilojoule_per_mole,
                location="pair.lj_base",
            ),
            "coulomb_base_energy_kilojoule_per_mole_binary64": _binary64_hex(
                self.coulomb_base_energy_kilojoule_per_mole,
                location="pair.coulomb_base",
            ),
            "lj_energy_scale_binary64": (
                None
                if self.lj_energy_scale is None
                else _binary64_hex(self.lj_energy_scale, location="pair.lj_scale")
            ),
            "coulomb_energy_scale_binary64": (
                None
                if self.coulomb_energy_scale is None
                else _binary64_hex(
                    self.coulomb_energy_scale,
                    location="pair.coulomb_scale",
                )
            ),
            "lj_energy_kilojoule_per_mole_binary64": _binary64_hex(
                self.lj_energy_kilojoule_per_mole,
                location="pair.lj_energy",
            ),
            "coulomb_energy_kilojoule_per_mole_binary64": _binary64_hex(
                self.coulomb_energy_kilojoule_per_mole,
                location="pair.coulomb_energy",
            ),
            "pair_energy_kilojoule_per_mole_binary64": _binary64_hex(
                self.pair_energy_kilojoule_per_mole,
                location="pair.total",
            ),
        }


def _immutable_coordinate_points(
    replay: _LinearAlkaneC1C4ScalarEnergyDiagnosticReplay,
) -> tuple[Vector3, ...]:
    system = deserialize_all_atom_system(replay.canonical_system_snapshot_bytes)
    if serialize_all_atom_system(system) != replay.canonical_system_snapshot_bytes:
        _fail("dependency_inconsistent", "fresh coordinate replay is not canonical")
    coordinates = system.coordinates
    return tuple(
        _vector(
            (float(coordinates[0, index, axis].item()) for axis in range(3)),
            location=f"coordinates[{index}]",
        )
        for index in range(len(system.atoms))
    )


def _point(points: tuple[Vector3, ...], index: int) -> Vector3:
    try:
        return points[index]
    except IndexError:
        _fail("dependency_inconsistent", "term atom index is outside the snapshot")


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
            f"{location} distance must exceed the method threshold",
        )
    return distance


def _bond_term(
    replay: _LinearAlkaneC1C4ScalarEnergyDiagnosticReplay,
    points: tuple[Vector3, ...],
    row: dict[str, Any],
) -> LinearAlkaneBondScalarEnergyTerm:
    identity = row["identity"]
    atom_i = identity["atom_i"]
    atom_j = identity["atom_j"]
    difference = _difference(
        _point(points, atom_i),
        _point(points, atom_j),
        location=f"bond[{atom_i},{atom_j}].difference",
    )
    distance = _require_distance(
        difference,
        replay.method.minimum_distance_angstrom,
        location=f"bond[{atom_i},{atom_j}]",
    )
    equilibrium = _binary64_from_hex(
        row["equilibrium_length_angstrom_binary64"],
        location=f"bond[{atom_i},{atom_j}].equilibrium",
    )
    force_constant = _binary64_from_hex(
        row["force_constant_kilojoule_per_mole_per_angstrom2_binary64"],
        location=f"bond[{atom_i},{atom_j}].force_constant",
    )
    displacement = _subtract(
        distance,
        equilibrium,
        location=f"bond[{atom_i},{atom_j}].displacement",
    )
    half_k = _multiply(
        0.5,
        force_constant,
        location=f"bond[{atom_i},{atom_j}].half_k",
    )
    temporary = _multiply(
        half_k,
        displacement,
        location=f"bond[{atom_i},{atom_j}].temporary",
    )
    energy = _multiply(
        temporary,
        displacement,
        location=f"bond[{atom_i},{atom_j}].energy",
    )
    return LinearAlkaneBondScalarEnergyTerm(
        identity=CanonicalBondIdentity(atom_i, atom_j),
        parameter_id=row["parameter_id"],
        distance_angstrom=distance,
        displacement_angstrom=displacement,
        energy_kilojoule_per_mole=energy,
    )


def _angle_term(
    replay: _LinearAlkaneC1C4ScalarEnergyDiagnosticReplay,
    points: tuple[Vector3, ...],
    row: dict[str, Any],
) -> LinearAlkaneAngleScalarEnergyTerm:
    identity = row["identity"]
    atom_i = identity["outer_atom_i"]
    center = identity["center_atom"]
    atom_k = identity["outer_atom_k"]
    center_point = _point(points, center)
    vector_u = _difference(
        center_point,
        _point(points, atom_i),
        location=f"angle[{atom_i},{center},{atom_k}].u",
    )
    vector_v = _difference(
        center_point,
        _point(points, atom_k),
        location=f"angle[{atom_i},{center},{atom_k}].v",
    )
    length_u = _require_distance(
        vector_u,
        replay.method.minimum_distance_angstrom,
        location=f"angle[{atom_i},{center},{atom_k}].u",
    )
    length_v = _require_distance(
        vector_v,
        replay.method.minimum_distance_angstrom,
        location=f"angle[{atom_i},{center},{atom_k}].v",
    )
    normalized_cross = _cross(
        _unit(vector_u, length_u, location="angle.u_hat"),
        _unit(vector_v, length_v, location="angle.v_hat"),
        location=f"angle[{atom_i},{center},{atom_k}].normalized_cross",
    )
    normalized_sine = _hypot(
        normalized_cross,
        location=f"angle[{atom_i},{center},{atom_k}].normalized_sine",
    )
    if normalized_sine <= replay.method.minimum_angle_sine:
        _fail(
            "singular_geometry",
            f"angle[{atom_i},{center},{atom_k}] sine is at or below threshold",
        )
    raw_cross = _cross(
        vector_u,
        vector_v,
        location=f"angle[{atom_i},{center},{atom_k}].raw_cross",
    )
    raw_cross_norm = _hypot(
        raw_cross,
        location=f"angle[{atom_i},{center},{atom_k}].raw_cross_norm",
    )
    if raw_cross_norm == 0.0:
        _fail(
            "nonrepresentable_coordinate_intermediate",
            f"angle[{atom_i},{center},{atom_k}] raw cross underflowed to zero",
        )
    raw_dot = _dot(
        vector_u,
        vector_v,
        location=f"angle[{atom_i},{center},{atom_k}].raw_dot",
    )
    angle = _atan2(
        raw_cross_norm,
        raw_dot,
        location=f"angle[{atom_i},{center},{atom_k}].coordinate",
    )
    equilibrium = _binary64_from_hex(
        row["equilibrium_angle_radian_binary64"],
        location=f"angle[{atom_i},{center},{atom_k}].equilibrium",
    )
    force_constant = _binary64_from_hex(
        row["force_constant_kilojoule_per_mole_per_radian2_binary64"],
        location=f"angle[{atom_i},{center},{atom_k}].force_constant",
    )
    displacement = _subtract(
        angle,
        equilibrium,
        location=f"angle[{atom_i},{center},{atom_k}].displacement",
    )
    half_k = _multiply(
        0.5,
        force_constant,
        location=f"angle[{atom_i},{center},{atom_k}].half_k",
    )
    temporary = _multiply(
        half_k,
        displacement,
        location=f"angle[{atom_i},{center},{atom_k}].temporary",
    )
    energy = _multiply(
        temporary,
        displacement,
        location=f"angle[{atom_i},{center},{atom_k}].energy",
    )
    return LinearAlkaneAngleScalarEnergyTerm(
        identity=CanonicalAngleIdentity(atom_i, center, atom_k),
        parameter_id=row["parameter_id"],
        angle_radian=angle,
        displacement_radian=displacement,
        energy_kilojoule_per_mole=energy,
    )


def _proper_term(
    replay: _LinearAlkaneC1C4ScalarEnergyDiagnosticReplay,
    points: tuple[Vector3, ...],
    row: dict[str, Any],
) -> LinearAlkaneProperScalarEnergyTerm:
    identity = row["identity"]
    atom_i = identity["atom_i"]
    atom_j = identity["atom_j"]
    atom_k = identity["atom_k"]
    atom_l = identity["atom_l"]
    bond_1 = _difference(
        _point(points, atom_i),
        _point(points, atom_j),
        location=f"proper[{atom_i},{atom_j},{atom_k},{atom_l}].b1",
    )
    bond_2 = _difference(
        _point(points, atom_j),
        _point(points, atom_k),
        location=f"proper[{atom_i},{atom_j},{atom_k},{atom_l}].b2",
    )
    bond_3 = _difference(
        _point(points, atom_k),
        _point(points, atom_l),
        location=f"proper[{atom_i},{atom_j},{atom_k},{atom_l}].b3",
    )
    lengths = tuple(
        _require_distance(
            bond,
            replay.method.minimum_distance_angstrom,
            location=f"proper[{atom_i},{atom_j},{atom_k},{atom_l}].b{index}",
        )
        for index, bond in enumerate((bond_1, bond_2, bond_3), start=1)
    )
    unit_1 = _unit(bond_1, lengths[0], location="proper.b1_hat")
    unit_2 = _unit(bond_2, lengths[1], location="proper.b2_hat")
    unit_3 = _unit(bond_3, lengths[2], location="proper.b3_hat")
    normalized_sines = (
        _hypot(
            _cross(unit_1, unit_2, location="proper.normalized_cross_1"),
            location="proper.normalized_sine_1",
        ),
        _hypot(
            _cross(unit_2, unit_3, location="proper.normalized_cross_2"),
            location="proper.normalized_sine_2",
        ),
    )
    if any(value <= replay.method.minimum_proper_sine for value in normalized_sines):
        _fail(
            "singular_geometry",
            f"proper[{atom_i},{atom_j},{atom_k},{atom_l}] sine is at or below threshold",
        )
    normal_1 = _cross(bond_1, bond_2, location="proper.raw_normal_1")
    normal_2 = _cross(bond_2, bond_3, location="proper.raw_normal_2")
    if _hypot(normal_1, location="proper.raw_normal_1_norm") == 0.0 or _hypot(
        normal_2,
        location="proper.raw_normal_2_norm",
    ) == 0.0:
        _fail(
            "nonrepresentable_coordinate_intermediate",
            f"proper[{atom_i},{atom_j},{atom_k},{atom_l}] raw normal underflowed",
        )
    cross_normals = _cross(normal_1, normal_2, location="proper.cross_normals")
    y_value = _dot(cross_normals, unit_2, location="proper.atan2_y")
    x_value = _dot(normal_1, normal_2, location="proper.atan2_x")
    if x_value == 0.0 and y_value == 0.0:
        _fail(
            "nonrepresentable_coordinate_intermediate",
            f"proper[{atom_i},{atom_j},{atom_k},{atom_l}] atan2 inputs are zero",
        )
    dihedral = _atan2(y_value, x_value, location="proper.coordinate")
    components: list[LinearAlkaneProperComponentScalarEnergy] = []
    for component_index, component in enumerate(row["components"]):
        periodicity = component["periodicity"]
        if type(periodicity) is not int or not 1 <= periodicity <= 6:
            _fail(
                "dependency_inconsistent",
                f"proper component[{component_index}] periodicity is invalid",
            )
        phase = _binary64_from_hex(
            component["phase_radian_binary64"],
            location=f"proper.component[{component_index}].phase",
        )
        amplitude = _binary64_from_hex(
            component["amplitude_kilojoule_per_mole_binary64"],
            location=f"proper.component[{component_index}].amplitude",
        )
        periodicity_float = float(periodicity)
        n_phi = _multiply(
            periodicity_float,
            dihedral,
            location=f"proper.component[{component_index}].n_phi",
        )
        argument = _subtract(
            n_phi,
            phase,
            location=f"proper.component[{component_index}].argument",
        )
        cosine = _cos(
            argument,
            location=f"proper.component[{component_index}].cosine",
        )
        one_plus = _add(
            1.0,
            cosine,
            location=f"proper.component[{component_index}].one_plus_cosine",
        )
        energy = _multiply(
            amplitude,
            one_plus,
            location=f"proper.component[{component_index}].energy",
        )
        components.append(
            LinearAlkaneProperComponentScalarEnergy(
                periodicity=periodicity,
                phase_radian=phase,
                amplitude_kilojoule_per_mole=amplitude,
                energy_kilojoule_per_mole=energy,
            )
        )
    component_rows = tuple(components)
    energy = _finite_fsum(
        (value.energy_kilojoule_per_mole for value in component_rows),
        location="proper.component_energy_fsum",
    )
    return LinearAlkaneProperScalarEnergyTerm(
        identity=CanonicalProperTorsionIdentity(atom_i, atom_j, atom_k, atom_l),
        parameter_id=row["parameter_id"],
        dihedral_radian=dihedral,
        components=component_rows,
        energy_kilojoule_per_mole=energy,
    )


def _pair_term(
    replay: _LinearAlkaneC1C4ScalarEnergyDiagnosticReplay,
    points: tuple[Vector3, ...],
    row: dict[str, Any],
    effective_coulomb_coefficient: float,
) -> LinearAlkanePairScalarEnergyTerm:
    identity = row["identity"]
    atom_i = identity["atom_i"]
    atom_j = identity["atom_j"]
    difference = _difference(
        _point(points, atom_i),
        _point(points, atom_j),
        location=f"pair[{atom_i},{atom_j}].difference",
    )
    distance = _require_distance(
        difference,
        replay.method.minimum_distance_angstrom,
        location=f"pair[{atom_i},{atom_j}]",
    )
    sigma = _binary64_from_hex(
        row["lj_sigma_angstrom_binary64"],
        location=f"pair[{atom_i},{atom_j}].sigma",
    )
    epsilon = _binary64_from_hex(
        row["lj_epsilon_kilojoule_per_mole_binary64"],
        location=f"pair[{atom_i},{atom_j}].epsilon",
    )
    sigma_over_r = _divide(
        sigma,
        distance,
        location=f"pair[{atom_i},{atom_j}].sigma_over_r",
    )
    ratio_2 = _multiply(
        sigma_over_r,
        sigma_over_r,
        location=f"pair[{atom_i},{atom_j}].ratio_2",
    )
    ratio_4 = _multiply(
        ratio_2,
        ratio_2,
        location=f"pair[{atom_i},{atom_j}].ratio_4",
    )
    ratio_6 = _multiply(
        ratio_4,
        ratio_2,
        location=f"pair[{atom_i},{atom_j}].ratio_6",
    )
    ratio_12 = _multiply(
        ratio_6,
        ratio_6,
        location=f"pair[{atom_i},{atom_j}].ratio_12",
    )
    shape = _subtract(
        ratio_12,
        ratio_6,
        location=f"pair[{atom_i},{atom_j}].lj_shape",
    )
    four_epsilon = _multiply(
        4.0,
        epsilon,
        location=f"pair[{atom_i},{atom_j}].four_epsilon",
    )
    lj_base = _multiply(
        four_epsilon,
        shape,
        location=f"pair[{atom_i},{atom_j}].lj_base",
    )
    charge_i = _binary64_from_hex(
        row["atom_i_partial_charge_e_binary64"],
        location=f"pair[{atom_i},{atom_j}].charge_i",
    )
    charge_j = _binary64_from_hex(
        row["atom_j_partial_charge_e_binary64"],
        location=f"pair[{atom_i},{atom_j}].charge_j",
    )
    coulomb_temporary_1 = _multiply(
        effective_coulomb_coefficient,
        charge_i,
        location=f"pair[{atom_i},{atom_j}].coulomb_temporary_1",
    )
    coulomb_temporary_2 = _multiply(
        coulomb_temporary_1,
        charge_j,
        location=f"pair[{atom_i},{atom_j}].coulomb_temporary_2",
    )
    coulomb_base = _divide(
        coulomb_temporary_2,
        distance,
        location=f"pair[{atom_i},{atom_j}].coulomb_base",
    )
    if row["interaction_class"] == "one_four_separate":
        lj_scale = _binary64_from_hex(
            row["lj_energy_scale_binary64"],
            location=f"pair[{atom_i},{atom_j}].lj_scale",
        )
        coulomb_scale = _binary64_from_hex(
            row["coulomb_energy_scale_binary64"],
            location=f"pair[{atom_i},{atom_j}].coulomb_scale",
        )
        lj_energy = _multiply(
            lj_scale,
            lj_base,
            location=f"pair[{atom_i},{atom_j}].scaled_lj",
        )
        coulomb_energy = _multiply(
            coulomb_scale,
            coulomb_base,
            location=f"pair[{atom_i},{atom_j}].scaled_coulomb",
        )
    elif row["interaction_class"] == "full_nonbonded":
        lj_scale = None
        coulomb_scale = None
        lj_energy = lj_base
        coulomb_energy = coulomb_base
    else:
        _fail(
            "dependency_inconsistent",
            f"pair[{atom_i},{atom_j}] interaction class is not selected",
        )
    pair_energy = _finite_fsum(
        (lj_energy, coulomb_energy),
        location=f"pair[{atom_i},{atom_j}].inner_fsum",
    )
    return LinearAlkanePairScalarEnergyTerm(
        identity=CanonicalPairIdentity(atom_i, atom_j),
        shortest_graph_distance=row["shortest_graph_distance"],
        interaction_class=row["interaction_class"],
        lj_resolution_status=row["lj_resolution_status"],
        lj_override_id=row["lj_override_id"],
        distance_angstrom=distance,
        lj_base_energy_kilojoule_per_mole=lj_base,
        coulomb_base_energy_kilojoule_per_mole=coulomb_base,
        lj_energy_scale=lj_scale,
        coulomb_energy_scale=coulomb_scale,
        lj_energy_kilojoule_per_mole=lj_energy,
        coulomb_energy_kilojoule_per_mole=coulomb_energy,
        pair_energy_kilojoule_per_mole=pair_energy,
    )


@dataclass(frozen=True, slots=True)
class _ComputedScalarEnergyDiagnostic:
    replay: _LinearAlkaneC1C4ScalarEnergyDiagnosticReplay
    binding_document: dict[str, Any]
    assignment_document: dict[str, Any]
    diagnostic_status: str
    bond_terms: tuple[LinearAlkaneBondScalarEnergyTerm, ...] | None
    angle_terms: tuple[LinearAlkaneAngleScalarEnergyTerm, ...] | None
    proper_terms: tuple[LinearAlkaneProperScalarEnergyTerm, ...] | None
    pair_terms: tuple[LinearAlkanePairScalarEnergyTerm, ...] | None
    bond_energy: float | None
    angle_energy: float | None
    proper_energy: float | None
    selected_pair_energy: float | None
    applied_lj_energy: float | None
    applied_coulomb_energy: float | None
    total_energy: float | None
    canonical_term_energy_sequence_sha256: str | None


def _validate_replay_dependencies_unchecked(
    replay: _LinearAlkaneC1C4ScalarEnergyDiagnosticReplay,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if type(replay) is not _LinearAlkaneC1C4ScalarEnergyDiagnosticReplay:
        raise TypeError("replay must be the exact bounded scalar diagnostic capsule")
    try:
        binding_document = json.loads(replay.binding_report_bytes.decode("ascii"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        _fail("dependency_inconsistent", f"binding report bytes are invalid: {exc}")
    if type(binding_document) is not dict:
        _fail("dependency_inconsistent", "binding report must be an exact object")
    if set(binding_document) != _FROZEN_METHOD_BINDING_REPORT_KEYS:
        _fail("dependency_inconsistent", "binding report root keys are inconsistent")
    if _canonical_json_bytes(binding_document) != replay.binding_report_bytes:
        _fail("dependency_inconsistent", "binding report bytes are not canonical")
    if binding_document.get("schema_id") != _FROZEN_METHOD_BINDING_SCHEMA_ID:
        _fail("dependency_inconsistent", "binding report schema is inconsistent")
    if binding_document.get("binding_policy_id") != _FROZEN_METHOD_BINDING_POLICY_ID:
        _fail("dependency_inconsistent", "binding report policy is inconsistent")
    if binding_document["schema_version"] != _FROZEN_METHOD_BINDING_SCHEMA_VERSION:
        _fail("dependency_inconsistent", "binding schema version is inconsistent")
    if binding_document["claim_scope"] != _FROZEN_METHOD_BINDING_CLAIM_SCOPE:
        _fail("dependency_inconsistent", "binding claim scope is inconsistent")
    binding_core = dict(binding_document)
    binding_report_sha256 = binding_core.pop("report_sha256", None)
    _require_sha256("binding report SHA-256", binding_report_sha256)
    if _sha256_document(binding_core) != binding_report_sha256:
        _fail("dependency_inconsistent", "binding report hash is stale")
    try:
        input_envelope = json.loads(
            replay.input_execution_envelope_bytes.decode("ascii")
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        _fail("dependency_inconsistent", f"input envelope bytes are invalid: {exc}")
    if type(input_envelope) is not dict:
        _fail("dependency_inconsistent", "input envelope must be an exact object")
    if set(input_envelope) != _FROZEN_INPUT_ENVELOPE_KEYS:
        _fail("dependency_inconsistent", "input envelope keys are inconsistent")
    if _canonical_json_bytes(input_envelope) != replay.input_execution_envelope_bytes:
        _fail("dependency_inconsistent", "input envelope bytes are not canonical")
    if input_envelope != binding_document["input_execution_envelope"]:
        _fail("dependency_inconsistent", "binding input envelope differs from replay")
    if serialize_all_atom_system(replay.system) != replay.canonical_system_snapshot_bytes:
        _fail("dependency_inconsistent", "replay system bytes are inconsistent")
    if (
        serialize_linear_alkane_c1_c4_parameter_set(replay.parameter_set)
        != replay.canonical_parameter_artifact_bytes
    ):
        _fail("dependency_inconsistent", "replay parameter bytes are inconsistent")
    if (
        serialize_linear_alkane_c1_c4_evaluation_method(replay.method)
        != replay.canonical_method_artifact_bytes
    ):
        _fail("dependency_inconsistent", "replay method bytes are inconsistent")
    snapshot_bindings = (
        (
            "canonical_system_snapshot_sha256",
            replay.canonical_system_snapshot_bytes,
        ),
        (
            "canonical_parameter_artifact_sha256",
            replay.canonical_parameter_artifact_bytes,
        ),
        (
            "canonical_method_artifact_sha256",
            replay.canonical_method_artifact_bytes,
        ),
        (
            "input_execution_envelope_sha256",
            replay.input_execution_envelope_bytes,
        ),
    )
    for field_name, payload in snapshot_bindings:
        if binding_document[field_name] != hashlib.sha256(payload).hexdigest():
            _fail("dependency_inconsistent", f"{field_name} is inconsistent")
    assignment_document = replay.assignment_report.to_dict()
    if (
        serialize_linear_alkane_c1_c4_parameter_assignment_report(
            replay.assignment_report
        )
        != _canonical_json_bytes(assignment_document)
    ):
        _fail("dependency_inconsistent", "assignment report bytes are inconsistent")
    if assignment_document["schema_id"] != _FROZEN_ASSIGNMENT_SCHEMA_ID:
        _fail("dependency_inconsistent", "assignment report schema is inconsistent")
    if assignment_document["assignment_policy_id"] != _FROZEN_ASSIGNMENT_POLICY_ID:
        _fail("dependency_inconsistent", "assignment report policy is inconsistent")
    if assignment_document["parameter_protocol_sha256"] != (
        _FROZEN_PARAMETER_PROTOCOL_SHA256
    ):
        _fail("dependency_inconsistent", "parameter protocol binding is inconsistent")
    if assignment_document["report_sha256"] != binding_document[
        "assignment_report_sha256"
    ]:
        _fail("dependency_inconsistent", "binding does not match assignment report")
    if binding_document["assignment_schema_id"] != _FROZEN_ASSIGNMENT_SCHEMA_ID:
        _fail("dependency_inconsistent", "binding assignment schema is inconsistent")
    if binding_document["assignment_policy_id"] != _FROZEN_ASSIGNMENT_POLICY_ID:
        _fail("dependency_inconsistent", "binding assignment policy is inconsistent")
    if binding_document["assignment_status"] != assignment_document[
        "assignment_status"
    ]:
        _fail("dependency_inconsistent", "binding assignment status differs")
    if assignment_document["parameter_assignment_sha256"] != binding_document[
        "parameter_assignment_sha256"
    ]:
        _fail("dependency_inconsistent", "binding does not match assignment payload")
    assignment_binding_fields = (
        "parameter_protocol_sha256",
        "parameter_payload_sha256",
        "parameter_set_sha256",
        "force_field_unit_system_id",
        "pair_classification_policy_id",
        "applicability_report_sha256",
        "typing_report_sha256",
        "inventory_report_sha256",
        "canonical_topology_sha256",
        "source_format",
        "source_sha256",
        "source_authentication_status",
    )
    for field_name in assignment_binding_fields:
        if assignment_document[field_name] != binding_document[field_name]:
            _fail(
                "dependency_inconsistent",
                f"binding field {field_name} differs from assignment",
            )
    for field_name in ("parameter_set_id", "parameter_set_version"):
        if assignment_document[field_name] != binding_document[field_name]:
            _fail(
                "dependency_inconsistent",
                f"binding field {field_name} differs from assignment",
            )
    if binding_document["parameter_set_schema_id"] != _FROZEN_PARAMETER_SET_SCHEMA_ID:
        _fail("dependency_inconsistent", "binding parameter schema is inconsistent")
    expected_atom_assignment_count = (
        assignment_document["atom_count"]
        if assignment_document["assignment_status"] == "contract_fixture_mapped"
        else 0
    )
    if expected_atom_assignment_count != binding_document["atom_assignment_count"]:
        _fail(
            "dependency_inconsistent",
            "binding count atom_assignment_count differs from assignment",
        )
    assignment_count_fields = (
        ("bond_assignment_count", "bond_assignment_count"),
        ("angle_assignment_count", "angle_assignment_count"),
        ("proper_assignment_count", "proper_assignment_count"),
        ("pair_assignment_count", "pair_assignment_count"),
        ("excluded_pair_count", "excluded_pair_count"),
        ("mapped_nonexcluded_pair_count", "mapped_nonexcluded_pair_count"),
        ("pair_class_counts", "pair_class_counts"),
    )
    for assignment_name, binding_name in assignment_count_fields:
        if assignment_document[assignment_name] != binding_document[binding_name]:
            _fail(
                "dependency_inconsistent",
                f"binding count {binding_name} differs from assignment",
            )
    method_document = replay.method.to_dict()
    if method_document["method_payload"]["protocol_sha256"] != (
        _FROZEN_METHOD_PROTOCOL_SHA256
    ):
        _fail("dependency_inconsistent", "method protocol binding is inconsistent")
    method_binding_fields = (
        ("method_id", "method_id"),
        ("method_version", "method_version"),
        ("method_payload_sha256", "method_payload_sha256"),
        ("method_sha256", "evaluation_method_sha256"),
    )
    for method_name, binding_name in method_binding_fields:
        if method_document[method_name] != binding_document[binding_name]:
            _fail(
                "dependency_inconsistent",
                f"binding field {binding_name} differs from method",
            )
    if binding_document["method_protocol_sha256"] != _FROZEN_METHOD_PROTOCOL_SHA256:
        _fail("dependency_inconsistent", "binding method protocol is inconsistent")
    if binding_document["method_schema_id"] != _FROZEN_METHOD_SCHEMA_ID:
        _fail("dependency_inconsistent", "binding method schema is inconsistent")
    if binding_document["method_protocol_schema_id"] != (
        _FROZEN_METHOD_PROTOCOL_SCHEMA_ID
    ):
        _fail("dependency_inconsistent", "binding method protocol schema differs")
    if method_document["method_payload"]["energy_kernel_status"] != "missing":
        _fail("dependency_inconsistent", "bound method kernel must remain missing")
    if method_document["energy_kernel_available"] is not False:
        _fail("dependency_inconsistent", "bound method kernel gate must remain false")
    if method_document["diagnostic_evaluation_performed"] is not False:
        _fail("dependency_inconsistent", "bound method must remain unevaluated")
    if any(binding_document[name] is not False for name in _FROZEN_UPSTREAM_FALSE_GATES):
        _fail("dependency_inconsistent", "binding production gate is not closed")
    method_false_gates = tuple(
        name for name in _FROZEN_UPSTREAM_FALSE_GATES if name in method_document
    )
    if any(method_document[name] is not False for name in method_false_gates):
        _fail("dependency_inconsistent", "method production gate is not closed")
    if replay.method_binding_status != binding_document["method_binding_status"]:
        _fail("dependency_inconsistent", "replay binding status is inconsistent")
    if replay.geometry_domain_assessment_status != binding_document[
        "geometry_domain_assessment_status"
    ]:
        _fail("dependency_inconsistent", "replay geometry status is inconsistent")
    compatibility_rows = binding_document["compatibility_results"]
    if type(compatibility_rows) is not list or not all(
        type(row) is dict
        and set(row) == {"code", "passed"}
        and type(row["code"]) is str
        and type(row["passed"]) is bool
        for row in compatibility_rows
    ):
        _fail("dependency_inconsistent", "binding compatibility rows are malformed")
    if tuple(row["code"] for row in compatibility_rows) != (
        _FROZEN_METHOD_BINDING_COMPATIBILITY_CODES
    ):
        _fail("dependency_inconsistent", "binding compatibility codes differ")
    if compatibility_rows != [
        {"code": code, "passed": passed}
        for code, passed in replay.compatibility_results
    ]:
        _fail("dependency_inconsistent", "replay compatibility results differ")
    failed_codes = [
        row["code"] for row in compatibility_rows if not row["passed"]
    ]
    if binding_document["failed_compatibility_codes"] != failed_codes:
        _fail("dependency_inconsistent", "binding failed-code derivation differs")
    assignment_status = assignment_document["assignment_status"]
    if assignment_status == "invalid_system":
        expected_binding_status = "invalid_system"
    elif assignment_status == "unsupported_system":
        expected_binding_status = "unsupported_system"
    elif all(row["passed"] for row in compatibility_rows):
        expected_binding_status = "contract_fixture_method_bound"
    else:
        expected_binding_status = "method_incompatible"
    if binding_document["method_binding_status"] != expected_binding_status:
        _fail("dependency_inconsistent", "binding status derivation differs")
    assignment_mapped = assignment_status == "contract_fixture_mapped"
    bound = expected_binding_status == "contract_fixture_method_bound"
    geometry_status = binding_document["geometry_domain_assessment_status"]
    base_compatibility_rows = compatibility_rows[:-5]
    geometry_compatibility_rows = compatibility_rows[-5:]
    if not assignment_mapped or not all(
        row["passed"] for row in base_compatibility_rows
    ):
        expected_geometry_status = (
            "not_assessed_upstream_or_interface_incompatible"
        )
    elif not geometry_compatibility_rows[-1]["passed"]:
        expected_geometry_status = "failed_nonfinite_intermediate"
    elif all(row["passed"] for row in geometry_compatibility_rows):
        expected_geometry_status = "passed_bounded_domain_check_no_evaluation"
    else:
        expected_geometry_status = "failed_singularity_threshold"
    if geometry_status != expected_geometry_status:
        _fail("dependency_inconsistent", "binding geometry status derivation differs")
    geometry_assessed = geometry_status in {
        "passed_bounded_domain_check_no_evaluation",
        "failed_nonfinite_intermediate",
        "failed_singularity_threshold",
    }
    if bound and geometry_status != "passed_bounded_domain_check_no_evaluation":
        _fail("dependency_inconsistent", "bound geometry status is not passed")
    expected_boolean_fields = {
        "bounded_nonphysical_evaluation_method_contract_complete": True,
        "bounded_contract_fixture_assignment_complete": assignment_mapped,
        "bounded_contract_fixture_geometry_domain_assessed": geometry_assessed,
        "bounded_contract_fixture_method_assignment_binding_complete": bound,
    }
    for field_name, expected_value in expected_boolean_fields.items():
        if binding_document[field_name] is not expected_value:
            _fail(
                "dependency_inconsistent",
                f"binding derived gate {field_name} differs",
            )
    expected_covered_count = (
        assignment_document["mapped_nonexcluded_pair_count"]
        if assignment_mapped
        else 0
    )
    if binding_document["method_covered_nonexcluded_pair_count"] != (
        expected_covered_count
    ):
        _fail("dependency_inconsistent", "binding covered-pair count differs")
    if binding_document["canonical_snapshot_coordinates_device_type"] != "cpu":
        _fail("dependency_inconsistent", "binding canonical device differs")
    if binding_document["device_preservation_status"] != (
        "original_device_observed_separately_not_snapshot_encoded"
    ):
        _fail("dependency_inconsistent", "binding device policy differs")
    if binding_document["input_execution_envelope_authentication_status"] != (
        "digest_bound_not_authenticated"
    ):
        _fail("dependency_inconsistent", "binding envelope auth status differs")
    if bound:
        expected_bound_envelope = {
            "coordinate_model_count": 1,
            "coordinate_unit": "angstrom",
            "coordinates_dtype": "torch.float64",
            "coordinates_device_type": "cpu",
            "coordinates_layout": "torch.strided",
            "coordinates_materialized": True,
            "coordinates_requires_grad": False,
            "cell_present": False,
            "cell_periodic_flags": None,
        }
        if any(
            input_envelope[name] != expected_value
            for name, expected_value in expected_bound_envelope.items()
        ):
            _fail("dependency_inconsistent", "bound input envelope is incompatible")
        coordinates = replay.system.coordinates
        expected_shape = (1, len(replay.system.atoms), 3)
        if (
            tuple(coordinates.shape) != expected_shape
            or input_envelope["coordinates_shape"] != list(expected_shape)
            or str(coordinates.dtype) != "torch.float64"
            or coordinates.device.type != "cpu"
            or str(coordinates.layout) != "torch.strided"
            or coordinates.requires_grad
            or replay.system.coordinate_unit != "angstrom"
            or replay.system.cell is not None
            or len(replay.system.atoms) > 14
        ):
            _fail(
                "dependency_inconsistent",
                "bound canonical system interface is incompatible",
            )
    status_blocker = {
        "invalid_system": "canonical_input_invalid_for_bounded_upstream_contract",
        "unsupported_system": "chemistry_outside_bounded_c1_c4_domain",
        "method_incompatible": "input_or_geometry_incompatible_with_bounded_method",
        "contract_fixture_method_bound": None,
    }[expected_binding_status]
    expected_blockers = (
        _FROZEN_METHOD_BINDING_BASE_BLOCKERS
        if status_blocker is None
        else (status_blocker, *_FROZEN_METHOD_BINDING_BASE_BLOCKERS)
    )
    if binding_document["blockers"] != list(expected_blockers):
        _fail("dependency_inconsistent", "binding blockers differ")
    binding_projection = {
        "schema_id": binding_document["schema_id"],
        "schema_version": binding_document["schema_version"],
        "binding_policy_id": binding_document["binding_policy_id"],
        "claim_scope": binding_document["claim_scope"],
        "canonical_system_snapshot_sha256": binding_document[
            "canonical_system_snapshot_sha256"
        ],
        "canonical_parameter_artifact_sha256": binding_document[
            "canonical_parameter_artifact_sha256"
        ],
        "canonical_method_artifact_sha256": binding_document[
            "canonical_method_artifact_sha256"
        ],
        "input_execution_envelope_sha256": binding_document[
            "input_execution_envelope_sha256"
        ],
        "assignment_report_sha256": binding_document[
            "assignment_report_sha256"
        ],
        "parameter_assignment_sha256": binding_document[
            "parameter_assignment_sha256"
        ],
        "parameter_protocol_sha256": binding_document[
            "parameter_protocol_sha256"
        ],
        "parameter_payload_sha256": binding_document[
            "parameter_payload_sha256"
        ],
        "parameter_set_sha256": binding_document["parameter_set_sha256"],
        "method_protocol_sha256": binding_document["method_protocol_sha256"],
        "method_payload_sha256": binding_document["method_payload_sha256"],
        "evaluation_method_sha256": binding_document[
            "evaluation_method_sha256"
        ],
        "compatibility_results": binding_document["compatibility_results"],
        "geometry_domain_assessment_status": binding_document[
            "geometry_domain_assessment_status"
        ],
        "atom_assignment_count": binding_document["atom_assignment_count"],
        "bond_assignment_count": binding_document["bond_assignment_count"],
        "angle_assignment_count": binding_document["angle_assignment_count"],
        "proper_assignment_count": binding_document["proper_assignment_count"],
        "pair_assignment_count": binding_document["pair_assignment_count"],
        "pair_class_counts": binding_document["pair_class_counts"],
        "method_covered_nonexcluded_pair_count": binding_document[
            "method_covered_nonexcluded_pair_count"
        ],
    }
    if replay.method_binding_status == "contract_fixture_method_bound":
        method_binding_sha256 = _require_sha256(
            "method binding SHA-256",
            binding_document["method_binding_sha256"],
        )
        if _sha256_document(binding_projection) != method_binding_sha256:
            _fail("dependency_inconsistent", "method binding hash is stale")
    elif binding_document["method_binding_sha256"] is not None:
        _fail(
            "dependency_inconsistent",
            "unavailable method binding must not carry a binding hash",
        )
    return binding_document, assignment_document


def _validate_replay_dependencies(
    replay: _LinearAlkaneC1C4ScalarEnergyDiagnosticReplay,
) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        return _validate_replay_dependencies_unchecked(replay)
    except LinearAlkaneScalarEnergyDiagnosticError:
        raise
    except (AttributeError, IndexError, KeyError, TypeError, ValueError) as exc:
        _fail(
            "dependency_inconsistent",
            f"replay dependency structure is inconsistent: {exc}",
        )


def _compute_scalar_energy(
    replay: _LinearAlkaneC1C4ScalarEnergyDiagnosticReplay,
) -> _ComputedScalarEnergyDiagnostic:
    binding, assignment = _validate_replay_dependencies(replay)
    binding_status = replay.method_binding_status
    if binding_status != "contract_fixture_method_bound":
        status_by_binding = {
            "invalid_system": "invalid_system",
            "unsupported_system": "unsupported_system",
            "method_incompatible": "method_incompatible",
        }
        try:
            diagnostic_status = status_by_binding[binding_status]
        except KeyError:
            _fail("dependency_inconsistent", "unknown unavailable binding status")
        return _ComputedScalarEnergyDiagnostic(
            replay=replay,
            binding_document=binding,
            assignment_document=assignment,
            diagnostic_status=diagnostic_status,
            bond_terms=None,
            angle_terms=None,
            proper_terms=None,
            pair_terms=None,
            bond_energy=None,
            angle_energy=None,
            proper_energy=None,
            selected_pair_energy=None,
            applied_lj_energy=None,
            applied_coulomb_energy=None,
            total_energy=None,
            canonical_term_energy_sequence_sha256=None,
        )
    if replay.geometry_domain_assessment_status != (
        "passed_bounded_domain_check_no_evaluation"
    ):
        _fail("dependency_inconsistent", "bound replay geometry status is inconsistent")
    if assignment["assignment_status"] != "contract_fixture_mapped":
        _fail("dependency_inconsistent", "bound replay assignment is unavailable")

    _require_round_to_nearest_ties_to_even()
    points = _immutable_coordinate_points(replay)
    bond_terms = tuple(
        _bond_term(replay, points, row) for row in assignment["bond_assignments"]
    )
    angle_terms = tuple(
        _angle_term(replay, points, row) for row in assignment["angle_assignments"]
    )
    proper_terms = tuple(
        _proper_term(replay, points, row) for row in assignment["proper_assignments"]
    )
    effective_coulomb_coefficient = _divide(
        replay.method.coulomb_coefficient_kilojoule_angstrom_per_mole_e2,
        replay.method.relative_dielectric,
        location="effective_coulomb_coefficient",
    )
    selected_rows = tuple(
        row
        for row in assignment["pair_assignments"]
        if row["interaction_class"] in {"one_four_separate", "full_nonbonded"}
    )
    pair_terms = tuple(
        _pair_term(replay, points, row, effective_coulomb_coefficient)
        for row in selected_rows
    )
    if len(pair_terms) != assignment["mapped_nonexcluded_pair_count"]:
        _fail("dependency_inconsistent", "selected pair count is inconsistent")
    identity_sequences = (
        (
            tuple(value.identity.to_dict() for value in bond_terms),
            tuple(row["identity"] for row in assignment["bond_assignments"]),
            "bond",
        ),
        (
            tuple(value.identity.to_dict() for value in angle_terms),
            tuple(row["identity"] for row in assignment["angle_assignments"]),
            "angle",
        ),
        (
            tuple(value.identity.to_dict() for value in proper_terms),
            tuple(row["identity"] for row in assignment["proper_assignments"]),
            "proper",
        ),
        (
            tuple(value.identity.to_dict() for value in pair_terms),
            tuple(row["identity"] for row in selected_rows),
            "pair",
        ),
    )
    for actual, expected, term_class in identity_sequences:
        if actual != expected:
            _fail(
                "dependency_inconsistent",
                f"{term_class} result identities differ from assignment rows",
            )
    if tuple(value.identity for value in bond_terms) != tuple(
        sorted(value.identity for value in bond_terms)
    ):
        _fail("dependency_inconsistent", "bond energy terms are not canonical")
    if tuple(value.identity for value in angle_terms) != tuple(
        sorted(value.identity for value in angle_terms)
    ):
        _fail("dependency_inconsistent", "angle energy terms are not canonical")
    if tuple(value.identity for value in proper_terms) != tuple(
        sorted(value.identity for value in proper_terms)
    ):
        _fail("dependency_inconsistent", "proper energy terms are not canonical")
    if tuple(value.identity for value in pair_terms) != tuple(
        sorted(value.identity for value in pair_terms)
    ):
        _fail("dependency_inconsistent", "pair energy terms are not canonical")

    bond_energy = _finite_fsum(
        (value.energy_kilojoule_per_mole for value in bond_terms),
        location="bond_energy_subtotal",
    )
    angle_energy = _finite_fsum(
        (value.energy_kilojoule_per_mole for value in angle_terms),
        location="angle_energy_subtotal",
    )
    proper_energy = _finite_fsum(
        (value.energy_kilojoule_per_mole for value in proper_terms),
        location="proper_energy_subtotal",
    )
    selected_pair_energy = _finite_fsum(
        (value.pair_energy_kilojoule_per_mole for value in pair_terms),
        location="selected_pair_energy_subtotal",
    )
    applied_lj_energy = _finite_fsum(
        (value.lj_energy_kilojoule_per_mole for value in pair_terms),
        location="applied_lj_energy_subtotal",
    )
    applied_coulomb_energy = _finite_fsum(
        (value.coulomb_energy_kilojoule_per_mole for value in pair_terms),
        location="applied_coulomb_energy_subtotal",
    )
    flat_sequence = (
        *(value.energy_kilojoule_per_mole for value in bond_terms),
        *(value.energy_kilojoule_per_mole for value in angle_terms),
        *(value.energy_kilojoule_per_mole for value in proper_terms),
        *(value.pair_energy_kilojoule_per_mole for value in pair_terms),
    )
    total_energy = _finite_fsum(flat_sequence, location="flat_total_energy_fsum")
    sequence_document = [
        {
            "term_class": term_class,
            "identity": identity,
            "energy_kilojoule_per_mole_binary64": _binary64_hex(
                energy,
                location="term_sequence.energy",
            ),
        }
        for term_class, identity, energy in (
            *(
                ("bond", value.identity.to_dict(), value.energy_kilojoule_per_mole)
                for value in bond_terms
            ),
            *(
                ("angle", value.identity.to_dict(), value.energy_kilojoule_per_mole)
                for value in angle_terms
            ),
            *(
                ("proper", value.identity.to_dict(), value.energy_kilojoule_per_mole)
                for value in proper_terms
            ),
            *(
                (
                    "selected_pair",
                    value.identity.to_dict(),
                    value.pair_energy_kilojoule_per_mole,
                )
                for value in pair_terms
            ),
        )
    ]
    _require_round_to_nearest_ties_to_even()
    return _ComputedScalarEnergyDiagnostic(
        replay=replay,
        binding_document=binding,
        assignment_document=assignment,
        diagnostic_status="contract_fixture_scalar_energy_evaluated",
        bond_terms=bond_terms,
        angle_terms=angle_terms,
        proper_terms=proper_terms,
        pair_terms=pair_terms,
        bond_energy=bond_energy,
        angle_energy=angle_energy,
        proper_energy=proper_energy,
        selected_pair_energy=selected_pair_energy,
        applied_lj_energy=applied_lj_energy,
        applied_coulomb_energy=applied_coulomb_energy,
        total_energy=total_energy,
        canonical_term_energy_sequence_sha256=_sha256_document(sequence_document),
    )


@dataclass(frozen=True, init=False, slots=True)
class LinearAlkaneC1C4ScalarEnergyDiagnosticReport:
    """Factory-only report bound to one immutable method-binding artifact."""

    _binding_report: LinearAlkaneC1C4EvaluationMethodBindingReport = field(
        repr=False
    )
    _binding_report_snapshot: bytes = field(repr=False)
    _binding_report_snapshot_sha256: str = field(repr=False)

    def __init__(
        self,
        binding_report: LinearAlkaneC1C4EvaluationMethodBindingReport,
    ) -> None:
        if type(binding_report) is not LinearAlkaneC1C4EvaluationMethodBindingReport:
            raise TypeError(
                "binding_report must be an exact C1-C4 method-binding report"
            )
        _require_round_to_nearest_ties_to_even()
        replay = binding_report._replay_for_bounded_scalar_energy_diagnostic()
        snapshot = replay.binding_report_bytes
        object.__setattr__(self, "_binding_report", binding_report)
        object.__setattr__(self, "_binding_report_snapshot", snapshot)
        object.__setattr__(
            self,
            "_binding_report_snapshot_sha256",
            hashlib.sha256(snapshot).hexdigest(),
        )
        self._validate(_compute_scalar_energy(replay))

    def _validated_replay(self) -> _LinearAlkaneC1C4ScalarEnergyDiagnosticReplay:
        _require_round_to_nearest_ties_to_even()
        if type(self._binding_report) is not (
            LinearAlkaneC1C4EvaluationMethodBindingReport
        ):
            raise TypeError("stored binding report must retain its exact type")
        if type(self._binding_report_snapshot) is not bytes:
            raise TypeError("stored binding report snapshot must be exact bytes")
        expected = _require_sha256(
            "stored binding report snapshot digest",
            self._binding_report_snapshot_sha256,
        )
        if hashlib.sha256(self._binding_report_snapshot).hexdigest() != expected:
            _fail(
                "binding_snapshot_tampered",
                "stored binding report snapshot digest is inconsistent",
            )
        replay = (
            self._binding_report._replay_for_bounded_scalar_energy_diagnostic()
        )
        if replay.binding_report_bytes != self._binding_report_snapshot:
            _fail(
                "binding_snapshot_changed",
                "method-binding report no longer matches the captured snapshot",
            )
        return replay

    def _validate(
        self,
        analysis: _ComputedScalarEnergyDiagnostic | None = None,
    ) -> None:
        current = (
            _compute_scalar_energy(self._validated_replay())
            if analysis is None
            else analysis
        )
        if type(current) is not _ComputedScalarEnergyDiagnostic:
            raise TypeError("analysis must be an exact computed scalar diagnostic")
        if current.replay.binding_report_bytes != self._binding_report_snapshot:
            _fail(
                "binding_snapshot_changed",
                "analysis binding bytes differ from the captured snapshot",
            )
        if current.diagnostic_status not in _FROZEN_DIAGNOSTIC_STATUSES:
            _fail("dependency_inconsistent", "diagnostic status is unknown")
        expected_status = {
            "invalid_system": "invalid_system",
            "unsupported_system": "unsupported_system",
            "method_incompatible": "method_incompatible",
            "contract_fixture_method_bound": (
                "contract_fixture_scalar_energy_evaluated"
            ),
        }.get(current.replay.method_binding_status)
        if expected_status != current.diagnostic_status:
            _fail(
                "dependency_inconsistent",
                "diagnostic and method-binding statuses are inconsistent",
            )
        evaluated = current.diagnostic_status == (
            "contract_fixture_scalar_energy_evaluated"
        )
        term_groups = (
            current.bond_terms,
            current.angle_terms,
            current.proper_terms,
            current.pair_terms,
        )
        energy_values = (
            current.bond_energy,
            current.angle_energy,
            current.proper_energy,
            current.selected_pair_energy,
            current.applied_lj_energy,
            current.applied_coulomb_energy,
            current.total_energy,
        )
        if evaluated:
            if not all(type(group) is tuple for group in term_groups):
                _fail("dependency_inconsistent", "evaluated term groups are absent")
            if not all(type(value) is float for value in energy_values):
                _fail("dependency_inconsistent", "evaluated energy values are absent")
            for index, value in enumerate(energy_values):
                _finite(value, location=f"report.energy[{index}]")
            assignment = current.assignment_document
            expected_counts = (
                assignment["bond_assignment_count"],
                assignment["angle_assignment_count"],
                assignment["proper_assignment_count"],
                assignment["mapped_nonexcluded_pair_count"],
            )
            if tuple(len(group) for group in term_groups) != expected_counts:
                _fail(
                    "dependency_inconsistent",
                    "evaluated term counts differ from the bound assignment",
                )
            _require_sha256(
                "canonical term-energy sequence digest",
                current.canonical_term_energy_sequence_sha256,
            )
        elif any(value is not None for value in (*term_groups, *energy_values)):
            _fail(
                "dependency_inconsistent",
                "unavailable diagnostic must not carry partial energy results",
            )
        elif current.canonical_term_energy_sequence_sha256 is not None:
            _fail(
                "dependency_inconsistent",
                "unavailable diagnostic must not carry a term sequence digest",
            )

    def _analysis(self) -> _ComputedScalarEnergyDiagnostic:
        analysis = _compute_scalar_energy(self._validated_replay())
        self._validate(analysis)
        return analysis

    @property
    def diagnostic_status(self) -> str:
        return self._analysis().diagnostic_status

    @property
    def bond_terms(self) -> tuple[LinearAlkaneBondScalarEnergyTerm, ...] | None:
        return self._analysis().bond_terms

    @property
    def angle_terms(self) -> tuple[LinearAlkaneAngleScalarEnergyTerm, ...] | None:
        return self._analysis().angle_terms

    @property
    def proper_terms(self) -> tuple[LinearAlkaneProperScalarEnergyTerm, ...] | None:
        return self._analysis().proper_terms

    @property
    def pair_terms(self) -> tuple[LinearAlkanePairScalarEnergyTerm, ...] | None:
        return self._analysis().pair_terms

    @property
    def bond_energy_kilojoule_per_mole(self) -> float | None:
        return self._analysis().bond_energy

    @property
    def angle_energy_kilojoule_per_mole(self) -> float | None:
        return self._analysis().angle_energy

    @property
    def proper_energy_kilojoule_per_mole(self) -> float | None:
        return self._analysis().proper_energy

    @property
    def selected_pair_energy_kilojoule_per_mole(self) -> float | None:
        return self._analysis().selected_pair_energy

    @property
    def applied_lj_energy_kilojoule_per_mole(self) -> float | None:
        return self._analysis().applied_lj_energy

    @property
    def applied_coulomb_energy_kilojoule_per_mole(self) -> float | None:
        return self._analysis().applied_coulomb_energy

    @property
    def total_energy_kilojoule_per_mole(self) -> float | None:
        return self._analysis().total_energy

    def _evaluation_document(
        self,
        analysis: _ComputedScalarEnergyDiagnostic,
    ) -> dict[str, Any] | None:
        if analysis.diagnostic_status != (
            "contract_fixture_scalar_energy_evaluated"
        ):
            return None
        if (
            analysis.bond_terms is None
            or analysis.angle_terms is None
            or analysis.proper_terms is None
            or analysis.pair_terms is None
            or analysis.canonical_term_energy_sequence_sha256 is None
        ):
            _fail("dependency_inconsistent", "evaluated term data are absent")
        energy_values = {
            "bond_energy_kilojoule_per_mole_binary64": analysis.bond_energy,
            "angle_energy_kilojoule_per_mole_binary64": analysis.angle_energy,
            "proper_energy_kilojoule_per_mole_binary64": analysis.proper_energy,
            "selected_pair_energy_kilojoule_per_mole_binary64": (
                analysis.selected_pair_energy
            ),
            "applied_lj_energy_kilojoule_per_mole_binary64": (
                analysis.applied_lj_energy
            ),
            "applied_coulomb_energy_kilojoule_per_mole_binary64": (
                analysis.applied_coulomb_energy
            ),
            "total_energy_kilojoule_per_mole_binary64": analysis.total_energy,
        }
        if not all(type(value) is float for value in energy_values.values()):
            _fail("dependency_inconsistent", "evaluated totals are absent")
        binding = analysis.binding_document
        return {
            "schema_id": _FROZEN_REPORT_SCHEMA_ID,
            "schema_version": _FROZEN_REPORT_SCHEMA_VERSION,
            "diagnostic_policy_id": _FROZEN_DIAGNOSTIC_POLICY_ID,
            "scalar_energy_algorithm_id": _FROZEN_SCALAR_ENERGY_ALGORITHM_ID,
            "protocol_sha256": _FROZEN_PROTOCOL_SHA256,
            "method_binding_report_bytes_sha256": (
                self._binding_report_snapshot_sha256
            ),
            "method_binding_report_sha256": binding["report_sha256"],
            "method_binding_sha256": binding["method_binding_sha256"],
            "assignment_report_sha256": binding["assignment_report_sha256"],
            "parameter_assignment_sha256": binding[
                "parameter_assignment_sha256"
            ],
            "canonical_term_energy_sequence_sha256": (
                analysis.canonical_term_energy_sequence_sha256
            ),
            "bond_terms": [value.to_dict() for value in analysis.bond_terms],
            "angle_terms": [value.to_dict() for value in analysis.angle_terms],
            "proper_terms": [value.to_dict() for value in analysis.proper_terms],
            "selected_pair_terms": [
                value.to_dict() for value in analysis.pair_terms
            ],
            **{
                name: _binary64_hex(value, location=f"evaluation.{name}")
                for name, value in energy_values.items()
            },
        }

    def _blockers(
        self,
        analysis: _ComputedScalarEnergyDiagnostic,
    ) -> tuple[str, ...]:
        status_blocker = {
            "invalid_system": "canonical_input_invalid_for_bounded_upstream_contract",
            "unsupported_system": "chemistry_outside_bounded_c1_c4_domain",
            "method_incompatible": "input_or_geometry_incompatible_with_bounded_method",
            "contract_fixture_scalar_energy_evaluated": None,
        }[analysis.diagnostic_status]
        blockers = (
            "numeric_parameter_and_method_values_are_nonphysical_contract_fixtures",
            "diagnostic_schema_evaluator_is_not_a_method_or_runtime_energy_kernel",
            "forces_virial_gradients_minimization_and_simulation_not_defined",
            "scientific_fit_reference_and_validation_missing",
            "licensed_method_provenance_and_review_missing",
            "bounded_n_le_14_direct_uncut_reference_is_not_scaling_evidence",
            "cell_free_nonperiodic_cpu_float64_single_model_only",
            "production_parameterability_physics_runtime_and_claim_authority_prohibited",
            "digests_and_input_observations_are_binding_not_authentication",
        )
        return blockers if status_blocker is None else (status_blocker, *blockers)

    @staticmethod
    def _encoded_energy(value: float | None, *, location: str) -> str | None:
        return None if value is None else _binary64_hex(value, location=location)

    def _core_dict(
        self,
        analysis: _ComputedScalarEnergyDiagnostic,
    ) -> dict[str, Any]:
        binding = analysis.binding_document
        assignment = analysis.assignment_document
        evaluated = analysis.diagnostic_status == (
            "contract_fixture_scalar_energy_evaluated"
        )
        evaluation_document = self._evaluation_document(analysis)
        term_groups = (
            analysis.bond_terms,
            analysis.angle_terms,
            analysis.proper_terms,
            analysis.pair_terms,
        )
        evaluated_counts = (
            (0, 0, 0, 0)
            if not evaluated
            else tuple(len(group) for group in term_groups)
        )
        return {
            "schema_id": _FROZEN_REPORT_SCHEMA_ID,
            "schema_version": _FROZEN_REPORT_SCHEMA_VERSION,
            "diagnostic_policy_id": _FROZEN_DIAGNOSTIC_POLICY_ID,
            "scalar_energy_algorithm_id": _FROZEN_SCALAR_ENERGY_ALGORITHM_ID,
            "claim_scope": _FROZEN_CLAIM_SCOPE,
            "protocol_schema_id": _FROZEN_PROTOCOL_SCHEMA_ID,
            "protocol_sha256": _FROZEN_PROTOCOL_SHA256,
            "binary64_encoding_id": _FROZEN_BINARY64_ENCODING_ID,
            "energy_unit": _FROZEN_ENERGY_UNIT,
            "method_binding_schema_id": _FROZEN_METHOD_BINDING_SCHEMA_ID,
            "method_binding_policy_id": _FROZEN_METHOD_BINDING_POLICY_ID,
            "method_binding_report_bytes_sha256": (
                self._binding_report_snapshot_sha256
            ),
            "method_binding_report_sha256": binding["report_sha256"],
            "method_binding_sha256": binding["method_binding_sha256"],
            "canonical_system_snapshot_sha256": binding[
                "canonical_system_snapshot_sha256"
            ],
            "canonical_parameter_artifact_sha256": binding[
                "canonical_parameter_artifact_sha256"
            ],
            "canonical_method_artifact_sha256": binding[
                "canonical_method_artifact_sha256"
            ],
            "input_execution_envelope_sha256": binding[
                "input_execution_envelope_sha256"
            ],
            "assignment_schema_id": _FROZEN_ASSIGNMENT_SCHEMA_ID,
            "assignment_policy_id": _FROZEN_ASSIGNMENT_POLICY_ID,
            "assignment_report_sha256": binding["assignment_report_sha256"],
            "parameter_assignment_sha256": binding[
                "parameter_assignment_sha256"
            ],
            "parameter_protocol_sha256": binding["parameter_protocol_sha256"],
            "parameter_payload_sha256": binding["parameter_payload_sha256"],
            "parameter_set_sha256": binding["parameter_set_sha256"],
            "method_schema_id": _FROZEN_METHOD_SCHEMA_ID,
            "method_protocol_sha256": binding["method_protocol_sha256"],
            "method_payload_sha256": binding["method_payload_sha256"],
            "evaluation_method_sha256": binding["evaluation_method_sha256"],
            "assignment_status": assignment["assignment_status"],
            "method_binding_status": analysis.replay.method_binding_status,
            "geometry_domain_assessment_status": (
                analysis.replay.geometry_domain_assessment_status
            ),
            "diagnostic_status": analysis.diagnostic_status,
            "atom_assignment_count": binding["atom_assignment_count"],
            "bond_assignment_count": binding["bond_assignment_count"],
            "angle_assignment_count": binding["angle_assignment_count"],
            "proper_assignment_count": binding["proper_assignment_count"],
            "pair_assignment_count": binding["pair_assignment_count"],
            "pair_class_counts": dict(binding["pair_class_counts"]),
            "mapped_nonexcluded_pair_count": assignment[
                "mapped_nonexcluded_pair_count"
            ],
            "evaluated_bond_count": evaluated_counts[0],
            "evaluated_angle_count": evaluated_counts[1],
            "evaluated_proper_count": evaluated_counts[2],
            "evaluated_selected_pair_count": evaluated_counts[3],
            "bond_energy_kilojoule_per_mole_binary64": self._encoded_energy(
                analysis.bond_energy,
                location="report.bond_energy",
            ),
            "angle_energy_kilojoule_per_mole_binary64": self._encoded_energy(
                analysis.angle_energy,
                location="report.angle_energy",
            ),
            "proper_energy_kilojoule_per_mole_binary64": self._encoded_energy(
                analysis.proper_energy,
                location="report.proper_energy",
            ),
            "selected_pair_energy_kilojoule_per_mole_binary64": (
                self._encoded_energy(
                    analysis.selected_pair_energy,
                    location="report.selected_pair_energy",
                )
            ),
            "applied_lj_energy_kilojoule_per_mole_binary64": self._encoded_energy(
                analysis.applied_lj_energy,
                location="report.applied_lj_energy",
            ),
            "applied_coulomb_energy_kilojoule_per_mole_binary64": (
                self._encoded_energy(
                    analysis.applied_coulomb_energy,
                    location="report.applied_coulomb_energy",
                )
            ),
            "total_energy_kilojoule_per_mole_binary64": self._encoded_energy(
                analysis.total_energy,
                location="report.total_energy",
            ),
            "canonical_term_energy_sequence_sha256": (
                analysis.canonical_term_energy_sequence_sha256
            ),
            "scalar_energy_evaluation_sha256": (
                None
                if evaluation_document is None
                else _sha256_document(evaluation_document)
            ),
            "bound_method_artifact_energy_kernel_status": "missing",
            "diagnostic_schema_owned_scalar_evaluator": evaluated,
            "bounded_nonphysical_diagnostic_scalar_evaluation_authorized": (
                evaluated
            ),
            "bounded_nonphysical_diagnostic_scalar_energy_evaluated": evaluated,
            "diagnostic_evaluation_performed": evaluated,
            "method_owned_energy_kernel_available": False,
            "production_runtime_energy_kernel_available": False,
            "evaluation_executed": False,
            "energy_evaluated": False,
            "forces_evaluated": False,
            "virial_evaluated": False,
            "gradient_evaluated": False,
            "production_evaluation_method_defined": False,
            "production_parameter_assignment_complete": False,
            "parameterability_assessed": False,
            "parameterizable": False,
            "global_parameter_coverage_complete": False,
            "physics_supported": False,
            "scientifically_validated": False,
            "runtime_eligible": False,
            "execution_authorized": False,
            "energy_evaluation_authorized": False,
            "force_evaluation_authorized": False,
            "virial_evaluation_authorized": False,
            "gradient_evaluation_authorized": False,
            "minimization_authorized": False,
            "simulation_ready": False,
            "claim_safe": False,
            "runtime_dispatch_registered": False,
            "blockers": list(self._blockers(analysis)),
        }

    @property
    def scalar_energy_evaluation_sha256(self) -> str | None:
        analysis = self._analysis()
        document = self._evaluation_document(analysis)
        return None if document is None else _sha256_document(document)

    @property
    def report_sha256(self) -> str:
        return _sha256_document(self._core_dict(self._analysis()))

    def to_dict(self) -> dict[str, Any]:
        document = self._core_dict(self._analysis())
        document["report_sha256"] = _sha256_document(document)
        return document

    def matches(
        self,
        binding_report: LinearAlkaneC1C4EvaluationMethodBindingReport,
    ) -> bool:
        if type(binding_report) is not LinearAlkaneC1C4EvaluationMethodBindingReport:
            raise TypeError(
                "binding_report must be an exact C1-C4 method-binding report"
            )
        self._analysis()
        replay = binding_report._replay_for_bounded_scalar_energy_diagnostic()
        return replay.binding_report_bytes == self._binding_report_snapshot


def analyze_linear_alkane_c1_c4_scalar_energy_diagnostic(
    binding_report: LinearAlkaneC1C4EvaluationMethodBindingReport,
) -> LinearAlkaneC1C4ScalarEnergyDiagnosticReport:
    """Evaluate one bounded, nonphysical scalar diagnostic from a binding."""

    if type(binding_report) is not LinearAlkaneC1C4EvaluationMethodBindingReport:
        raise TypeError(
            "binding_report must be an exact C1-C4 method-binding report"
        )
    return LinearAlkaneC1C4ScalarEnergyDiagnosticReport(binding_report)


def serialize_linear_alkane_c1_c4_scalar_energy_diagnostic_report(
    report: LinearAlkaneC1C4ScalarEnergyDiagnosticReport,
) -> bytes:
    """Serialize one fresh validated diagnostic report to canonical JSON."""

    if type(report) is not LinearAlkaneC1C4ScalarEnergyDiagnosticReport:
        raise TypeError("report must be an exact C1-C4 scalar diagnostic report")
    analysis = report._analysis()
    document = report._core_dict(analysis)
    document["report_sha256"] = _sha256_document(document)
    return _canonical_json_bytes(document)


__all__ = [
    "LINEAR_ALKANE_SCALAR_ENERGY_DIAGNOSTIC_CLAIM_SCOPE",
    "LINEAR_ALKANE_SCALAR_ENERGY_DIAGNOSTIC_POLICY_ID",
    "LINEAR_ALKANE_SCALAR_ENERGY_DIAGNOSTIC_PROTOCOL_SCHEMA_ID",
    "LINEAR_ALKANE_SCALAR_ENERGY_DIAGNOSTIC_PROTOCOL_SCHEMA_VERSION",
    "LINEAR_ALKANE_SCALAR_ENERGY_DIAGNOSTIC_PROTOCOL_SHA256",
    "LINEAR_ALKANE_SCALAR_ENERGY_DIAGNOSTIC_SCHEMA_ID",
    "LINEAR_ALKANE_SCALAR_ENERGY_DIAGNOSTIC_SCHEMA_VERSION",
    "LINEAR_ALKANE_SCALAR_ENERGY_DIAGNOSTIC_STATUSES",
    "LINEAR_ALKANE_SCALAR_ENERGY_ALGORITHM_ID",
    "LinearAlkaneAngleScalarEnergyTerm",
    "LinearAlkaneBondScalarEnergyTerm",
    "LinearAlkaneC1C4ScalarEnergyDiagnosticReport",
    "LinearAlkanePairScalarEnergyTerm",
    "LinearAlkaneProperComponentScalarEnergy",
    "LinearAlkaneProperScalarEnergyTerm",
    "LinearAlkaneScalarEnergyDiagnosticError",
    "analyze_linear_alkane_c1_c4_scalar_energy_diagnostic",
    "linear_alkane_scalar_energy_diagnostic_protocol_bytes",
    "linear_alkane_scalar_energy_diagnostic_protocol_document",
    "serialize_linear_alkane_c1_c4_scalar_energy_diagnostic_report",
]
