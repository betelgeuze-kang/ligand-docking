"""Strict nonphysical C1-C4 scalar-energy evaluation-method contract.

The artifact in this module closes the method choices deliberately deferred by
the bounded linear-alkane parameter protocol.  It defines a tiny, direct,
uncut, cell-free scalar-energy method for contract testing only.  It contains
no evaluator, force, virial, minimizer, runtime dispatch, or scientific values.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import re
import struct
from typing import Any, Mapping


_FROZEN_PROTOCOL_SCHEMA_VERSION = "1.0.0"
_FROZEN_PROTOCOL_SCHEMA_ID = (
    "betelgeuze.linear_alkane_c1_c4_evaluation_method_protocol/"
    f"{_FROZEN_PROTOCOL_SCHEMA_VERSION}"
)
_FROZEN_METHOD_SCHEMA_VERSION = "1.0.0"
_FROZEN_METHOD_SCHEMA_ID = (
    "betelgeuze.linear_alkane_c1_c4_evaluation_method/"
    f"{_FROZEN_METHOD_SCHEMA_VERSION}"
)
_FROZEN_METHOD_SCOPE = (
    "bounded_nonphysical_c1_c4_scalar_energy_method_definition_only"
)
_FROZEN_METHOD_POLICY_ID = (
    "cell_free_cpu_float64_direct_uncut_inventory_pairs_scalar_energy/1.0.0"
)
_FROZEN_PARAMETER_PROTOCOL_SCHEMA_ID = (
    "betelgeuze.linear_alkane_c1_c4_parameter_protocol/1.0.0"
)
_FROZEN_PARAMETER_PROTOCOL_SHA256 = (
    "28219cd1492b31f3d151048e7ad9db297fe7a896d081b098e901f142f6d4602a"
)
_FROZEN_PARAMETER_SET_SCHEMA_ID = (
    "betelgeuze.linear_alkane_c1_c4_parameter_set/1.0.0"
)
_FROZEN_PARAMETER_ASSIGNMENT_POLICY_ID = (
    "exact_environment_and_term_keys_no_wildcards_no_precedence/1.0.0"
)
_FROZEN_ASSIGNMENT_SCHEMA_ID = (
    "betelgeuze.linear_alkane_c1_c4_parameter_assignment/1.0.0"
)
_FROZEN_ASSIGNMENT_POLICY_ID = (
    "fresh_snapshot_exact_environment_term_and_pair_parameter_mapping/1.0.0"
)
_FROZEN_UNIT_SYSTEM_ID = (
    "betelgeuze.kilojoule_per_mole_angstrom_radian_elementary_charge/1.0.0"
)
_FROZEN_BINARY64_ENCODING_ID = "ieee754_binary64_big_endian_hex/1.0.0"
_FROZEN_PAIR_CLASSIFICATION_POLICY_ID = (
    "covalent_shortest_graph_distance_1_2_excluded_1_3_excluded_"
    "1_4_separate_farther_full_v1"
)
_FROZEN_PAIR_SOURCE_POLICY_ID = (
    "canonical_inventory_all_unordered_pairs_n_le_14_no_neighbor_search/1.0.0"
)
_FROZEN_SELECTED_PAIR_POLICY_ID = (
    "assignment_one_four_and_full_pairs_exactly_once_excluded_1_2_1_3_omitted/"
    "1.0.0"
)
_FROZEN_CUTOFF_POLICY_ID = (
    "direct_uncut_bounded_tiny_reference_no_switch/1.0.0"
)
_FROZEN_NEIGHBOR_POLICY_ID = (
    "iterate_canonical_assignment_pairs_no_spatial_search_or_dense_matrix/1.0.0"
)
_FROZEN_PERIODIC_POLICY_ID = (
    "cell_free_nonperiodic_no_minimum_image/1.0.0"
)
_FROZEN_ELECTROSTATICS_PAIR_METHOD_ID = (
    "direct_nonperiodic_uncut_selected_pairs_tiny_reference_only_o_n_squared/"
    "1.0.0"
)
_FROZEN_SINGULARITY_POLICY_ID = (
    "reject_distance_or_normalized_angle_proper_sine_at_or_below_"
    "artifact_threshold/1.0.0"
)
_FROZEN_GEOMETRY_DOMAIN_ALGORITHM_ID = (
    "cpu_binary64_hypot_unit_vector_cross_sine_threshold_check/1.0.0"
)
_FROZEN_NONFINITE_POLICY_ID = (
    "reject_nonfinite_input_intermediate_or_output_without_regularization/1.0.0"
)
_FROZEN_ACCUMULATION_POLICY_ID = (
    "canonical_term_class_identity_component_and_pair_math_fsum/1.0.0"
)
_FROZEN_LJ_FUNCTIONAL_FORM_ID = "lj_12_6_four_epsilon_sigma/1.0.0"
_FROZEN_COULOMB_METHOD_FORM_ID = (
    "direct_pair_k_e_over_relative_dielectric_then_q_i_then_q_j_then_divide_r/"
    "1.0.0"
)
_FROZEN_BOND_ANGLE_FUNCTIONAL_FORM_ID = (
    "harmonic_half_k_delta_squared_bond_angle/1.0.0"
)
_FROZEN_PROPER_FUNCTIONAL_FORM_ID = (
    "periodic_proper_sum_k_one_plus_cos_n_phi_minus_delta/1.0.0"
)
_FROZEN_PROPER_COORDINATE_CONVENTION_ID = (
    "signed_dihedral_cross_normals_full_reversal_invariant/1.0.0"
)
_FROZEN_LJ_COMBINING_RULE_ID = (
    "lorentz_berthelot_sigma_arithmetic_epsilon_geometric/1.0.0"
)
_FROZEN_LJ_OVERRIDE_POLICY_ID = (
    "exact_unordered_type_pair_full_sigma_epsilon_override_before_1_4_scale/"
    "1.0.0"
)
_FROZEN_MAXIMUM_ATOM_COUNT = 14
_FROZEN_MAXIMUM_UNORDERED_PAIR_COUNT = 91
_FROZEN_MAXIMUM_SELECTED_PAIR_COUNT = 54
_MAXIMUM_FINITE_BINARY64 = float.fromhex("0x1.fffffffffffffp+1023")
_MAX_ARTIFACT_BYTES = 64 * 1024
_IDENTIFIER_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/+-]*\Z")
_SEMVER_PATTERN = re.compile(
    r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\Z"
)

LINEAR_ALKANE_EVALUATION_METHOD_PROTOCOL_SCHEMA_VERSION = (
    _FROZEN_PROTOCOL_SCHEMA_VERSION
)
LINEAR_ALKANE_EVALUATION_METHOD_PROTOCOL_SCHEMA_ID = _FROZEN_PROTOCOL_SCHEMA_ID
LINEAR_ALKANE_EVALUATION_METHOD_SCHEMA_VERSION = _FROZEN_METHOD_SCHEMA_VERSION
LINEAR_ALKANE_EVALUATION_METHOD_SCHEMA_ID = _FROZEN_METHOD_SCHEMA_ID
LINEAR_ALKANE_EVALUATION_METHOD_SCOPE = _FROZEN_METHOD_SCOPE
LINEAR_ALKANE_EVALUATION_METHOD_POLICY_ID = _FROZEN_METHOD_POLICY_ID
LINEAR_ALKANE_EVALUATION_METHOD_SINGULARITY_POLICY_ID = (
    _FROZEN_SINGULARITY_POLICY_ID
)
LINEAR_ALKANE_EVALUATION_METHOD_ACCUMULATION_POLICY_ID = (
    _FROZEN_ACCUMULATION_POLICY_ID
)


class LinearAlkaneEvaluationMethodContractError(ValueError):
    """Raised when a bounded evaluation-method artifact is inconsistent."""


class LinearAlkaneEvaluationMethodSerializationError(
    LinearAlkaneEvaluationMethodContractError
):
    """Raised when strict method-artifact bytes are invalid or noncanonical."""


def _require_identifier(name: str, value: Any) -> str:
    if type(value) is not str:
        raise TypeError(f"{name} must be an exact string")
    if _IDENTIFIER_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{name} must be a canonical identifier")
    return value


def _require_semver(name: str, value: Any) -> str:
    if type(value) is not str:
        raise TypeError(f"{name} must be an exact string")
    if _SEMVER_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{name} must be canonical semantic version text")
    return value


def _require_finite_binary64(
    name: str,
    value: Any,
    *,
    positive: bool = False,
    less_than_one: bool = False,
) -> float:
    if type(value) is not float:
        raise TypeError(f"{name} must be an exact float")
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    if value == 0.0 and math.copysign(1.0, value) < 0.0:
        raise ValueError(f"{name} must not be negative zero")
    if positive and value <= 0.0:
        raise ValueError(f"{name} must be positive")
    if less_than_one and value >= 1.0:
        raise ValueError(f"{name} must be strictly below one")
    return value


def _binary64_hex(value: float) -> str:
    _require_finite_binary64("binary64 value", value)
    return struct.pack(">d", value).hex()


def _binary64_from_hex(name: str, value: Any) -> float:
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{16}", value) is None:
        raise LinearAlkaneEvaluationMethodSerializationError(
            f"{name} must be canonical lowercase 16-digit binary64 hex"
        )
    number = struct.unpack(">d", bytes.fromhex(value))[0]
    _require_finite_binary64(name, number)
    if _binary64_hex(number) != value:
        raise LinearAlkaneEvaluationMethodSerializationError(
            f"{name} is not canonical binary64 hex"
        )
    return number


def _canonical_json_bytes(document: Mapping[str, Any]) -> bytes:
    try:
        payload = json.dumps(
            document,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise LinearAlkaneEvaluationMethodSerializationError(
            f"canonical JSON encoding failed: {exc}"
        ) from exc
    if len(payload) > _MAX_ARTIFACT_BYTES:
        raise LinearAlkaneEvaluationMethodSerializationError(
            "evaluation-method artifact exceeds the 64-KiB limit"
        )
    return payload


def _sha256_document(document: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json_bytes(document)).hexdigest()


def _unit_system_document() -> dict[str, Any]:
    return {
        "unit_system_id": _FROZEN_UNIT_SYSTEM_ID,
        "binary64_encoding_id": _FROZEN_BINARY64_ENCODING_ID,
        "distance": "angstrom",
        "angle": "radian",
        "energy": "kilojoule_per_mole",
        "charge": "elementary_charge",
        "coulomb_coefficient": (
            "kilojoule_angstrom_per_mole_per_elementary_charge_squared"
        ),
        "relative_dielectric": "dimensionless",
        "normalized_sine_threshold": "dimensionless",
    }


def _protocol_document() -> dict[str, Any]:
    return {
        "schema_id": _FROZEN_PROTOCOL_SCHEMA_ID,
        "schema_version": _FROZEN_PROTOCOL_SCHEMA_VERSION,
        "method_schema_id": _FROZEN_METHOD_SCHEMA_ID,
        "method_scope": _FROZEN_METHOD_SCOPE,
        "method_policy_id": _FROZEN_METHOD_POLICY_ID,
        "parameter_protocol_schema_id": _FROZEN_PARAMETER_PROTOCOL_SCHEMA_ID,
        "parameter_protocol_sha256": _FROZEN_PARAMETER_PROTOCOL_SHA256,
        "parameter_set_schema_id": _FROZEN_PARAMETER_SET_SCHEMA_ID,
        "parameter_assignment_policy_id": (
            _FROZEN_PARAMETER_ASSIGNMENT_POLICY_ID
        ),
        "assignment_schema_id": _FROZEN_ASSIGNMENT_SCHEMA_ID,
        "assignment_policy_id": _FROZEN_ASSIGNMENT_POLICY_ID,
        "pair_classification_policy_id": (
            _FROZEN_PAIR_CLASSIFICATION_POLICY_ID
        ),
        "pair_source_policy_id": _FROZEN_PAIR_SOURCE_POLICY_ID,
        "selected_pair_policy_id": _FROZEN_SELECTED_PAIR_POLICY_ID,
        "method_domain": {
            "molecule_domain": (
                "source_bound_explicit_h_neutral_linear_alkane_c1_c4_only"
            ),
            "maximum_atom_count": _FROZEN_MAXIMUM_ATOM_COUNT,
            "maximum_unordered_pair_count": (
                _FROZEN_MAXIMUM_UNORDERED_PAIR_COUNT
            ),
            "maximum_selected_pair_count": _FROZEN_MAXIMUM_SELECTED_PAIR_COUNT,
            "coordinate_model_count": 1,
            "coordinate_shape": "[1,N,3]",
            "coordinate_unit": "angstrom",
            "device": "cpu",
            "dtype": "torch.float64",
            "cell_policy": "cell_free_only",
            "coordinate_layout": "torch.strided_materialized",
            "coordinate_contiguity": "not_required_snapshot_is_contiguous",
            "coordinates_requires_grad": False,
        },
        "functional_form_bindings": {
            "bond_angle_functional_form_id": (
                _FROZEN_BOND_ANGLE_FUNCTIONAL_FORM_ID
            ),
            "proper_functional_form_id": _FROZEN_PROPER_FUNCTIONAL_FORM_ID,
            "proper_coordinate_convention_id": (
                _FROZEN_PROPER_COORDINATE_CONVENTION_ID
            ),
            "lj_functional_form_id": _FROZEN_LJ_FUNCTIONAL_FORM_ID,
            "lj_combining_rule_id": _FROZEN_LJ_COMBINING_RULE_ID,
            "lj_override_policy_id": _FROZEN_LJ_OVERRIDE_POLICY_ID,
            "coulomb_method_form_id": _FROZEN_COULOMB_METHOD_FORM_ID,
        },
        "scalar_energy_semantics": {
            "coulomb_pair": "U_q=(k_e/epsilon_r)*q_i*q_j/r",
            "coulomb_binary64_operation_order": [
                "effective_coefficient=k_e/epsilon_r",
                "charge_product_1=effective_coefficient*q_i",
                "charge_product_2=charge_product_1*q_j",
                "U_q=charge_product_2/r",
            ],
            "coulomb_coefficient_includes_dielectric": False,
            "excluded_1_2": "no_lj_or_coulomb_term",
            "excluded_1_3": "no_lj_or_coulomb_term",
            "one_four": "U_1_4=math_fsum([s_lj*U_lj,s_q*U_q])",
            "full_nonbonded": "U_full=math_fsum([U_lj,U_q])",
            "lj_resolution_order": (
                "exact_pair_override_else_lorentz_berthelot_then_1_4_scale"
            ),
            "total": "E_total=math_fsum(canonical_term_value_sequence)",
            "parameter_values_are_consumed_as_assigned": True,
            "assigned_lj_sigma_epsilon_recombination_or_modification": (
                "prohibited"
            ),
            "one_four_energy_scale_application": (
                "required_exactly_once_after_assigned_lj_resolution"
            ),
        },
        "pair_selection_semantics": {
            "selected_pair_policy_id": _FROZEN_SELECTED_PAIR_POLICY_ID,
            "excluded_1_2": "omit",
            "excluded_1_3": "omit",
            "one_four_separate": "include_exactly_once_with_both_scales",
            "full_nonbonded": "include_exactly_once_without_scale_fields",
            "c1_all_pair_count": 10,
            "c1_selected_pair_count": 0,
            "c4_all_pair_count": 91,
            "c4_selected_pair_count": 54,
            "vacuous_c1_selected_subset_requires_full_inventory_identity_check": (
                True
            ),
        },
        "cutoff_and_neighbor_semantics": {
            "cutoff_policy_id": _FROZEN_CUTOFF_POLICY_ID,
            "r_switch_angstrom": None,
            "r_cut_angstrom": None,
            "switch_function_id": None,
            "switch_status": "not_applicable_no_cutoff",
            "null_cutoff_interpretation": "not_a_default_zero_or_infinity",
            "neighbor_policy_id": _FROZEN_NEIGHBOR_POLICY_ID,
            "neighbor_skin_angstrom": None,
            "neighbor_capacity": None,
            "dense_n_by_n_pair_materialization": "prohibited",
            "cutoff_based_pair_omission": "prohibited",
            "complexity_claim": (
                "bounded_n_le_14_tiny_reference_only_no_scaling_claim"
            ),
        },
        "periodic_and_long_range_semantics": {
            "periodic_policy_id": _FROZEN_PERIODIC_POLICY_ID,
            "periodic_boundary_conditions": [False, False, False],
            "minimum_image_policy": None,
            "image_shift_policy": None,
            "electrostatics_pair_method_id": (
                _FROZEN_ELECTROSTATICS_PAIR_METHOD_ID
            ),
            "long_range_correction_method_id": None,
            "long_range_correction_status": (
                "not_applied_nonperiodic_direct_pair_sum"
            ),
            "reciprocal_space_method_id": None,
            "dispersion_tail_correction": False,
            "dispersion_tail_correction_status": "not_applied",
        },
        "geometry_domain_semantics": {
            "singularity_policy_id": _FROZEN_SINGULARITY_POLICY_ID,
            "assessment_algorithm_id": _FROZEN_GEOMETRY_DOMAIN_ALGORITHM_ID,
            "length_operation_order": (
                "difference_components_then_math_hypot_dx_dy_dz"
            ),
            "normalized_sine_operation_order": (
                "math_hypot_each_vector_then_componentwise_unit_vectors_then_"
                "explicit_cross_components_then_math_hypot_cross"
            ),
            "bond_and_selected_pair_distance_rule": (
                "every_required_distance>minimum_distance"
            ),
            "angle_rule": (
                "both_leg_norms>minimum_distance_and_normalized_cross_sine>"
                "minimum_angle_sine"
            ),
            "proper_rule": (
                "all_three_bond_norms>minimum_distance_and_both_normalized_"
                "adjacent_bond_cross_sines>minimum_proper_sine"
            ),
            "threshold_equality": "reject",
            "regularization": "prohibited",
            "clamping": "prohibited",
            "softcore": "prohibited",
            "epsilon_injection": "prohibited",
            "partial_output_after_failure": "prohibited",
            "nonfinite_policy_id": _FROZEN_NONFINITE_POLICY_ID,
        },
        "accumulation_semantics": {
            "policy_id": _FROZEN_ACCUMULATION_POLICY_ID,
            "term_class_order": [
                "bond",
                "angle",
                "proper",
                "selected_nonbonded_pair",
            ],
            "within_class_order": "canonical_identity_ascending",
            "proper_component_order": (
                "periodicity_then_phase_binary64_then_force_constant_binary64"
            ),
            "proper_component_reduction": "math_fsum_binary64",
            "pair_inner_order": "scaled_lj_then_scaled_coulomb",
            "pair_inner_reduction": "math_fsum_binary64",
            "total_reduction": (
                "one_math_fsum_over_all_term_values_in_exact_declared_order"
            ),
            "negative_zero_policy": "canonicalize_reported_zero_to_positive_zero",
            "force_accumulation": "not_defined_no_kernel",
            "virial_accumulation": "not_defined_no_kernel",
        },
        "numeric_execution_semantics": {
            "device": "cpu",
            "dtype": "ieee754_binary64",
            "rounding_mode": "round_to_nearest_ties_to_even",
            "mixed_precision": "prohibited",
            "fast_math": "prohibited",
            "fma_contraction": "prohibited",
            "cross_platform_libm_bit_replay_status": "not_assessed",
        },
        "definition_status": {
            "method_definition_status": (
                "declared_nonphysical_contract_fixture_not_executed"
            ),
            "energy_kernel": "missing",
            "force_method": "not_defined",
            "force_kernel": "missing",
            "virial_method": "not_defined",
            "virial_kernel": "missing",
            "runtime_dispatch": "prohibited",
            "evaluation_performed": False,
        },
        "artifact_variable_fields": [
            "coulomb_coefficient_kilojoule_angstrom_per_mole_e2",
            "relative_dielectric",
            "minimum_distance_angstrom",
            "minimum_angle_sine",
            "minimum_proper_sine",
        ],
        "unit_system": _unit_system_document(),
    }


_FROZEN_PROTOCOL_DOCUMENT = _protocol_document()
_FROZEN_PROTOCOL_BYTES = _canonical_json_bytes(_FROZEN_PROTOCOL_DOCUMENT)
_FROZEN_PROTOCOL_SHA256 = hashlib.sha256(_FROZEN_PROTOCOL_BYTES).hexdigest()

LINEAR_ALKANE_EVALUATION_METHOD_PROTOCOL_SHA256 = _FROZEN_PROTOCOL_SHA256


def linear_alkane_evaluation_method_protocol_document() -> dict[str, Any]:
    """Return an independent copy of the frozen method protocol."""

    return json.loads(_FROZEN_PROTOCOL_BYTES.decode("ascii"))


def linear_alkane_evaluation_method_protocol_bytes() -> bytes:
    """Return the exact frozen method-protocol bytes."""

    return bytes(_FROZEN_PROTOCOL_BYTES)


@dataclass(frozen=True, slots=True)
class LinearAlkaneC1C4EvaluationMethod:
    """Complete bounded method semantics with nonphysical fixture values."""

    method_id: str
    method_version: str
    coulomb_coefficient_kilojoule_angstrom_per_mole_e2: float
    relative_dielectric: float
    minimum_distance_angstrom: float
    minimum_angle_sine: float
    minimum_proper_sine: float
    scientific_source_sha256: None = None
    scientific_review_sha256: None = None
    license_review_sha256: None = None
    release_attestation_sha256: None = None
    reference_method_id: None = None

    def __post_init__(self) -> None:
        self._validate()

    def _validate(self) -> None:
        _require_identifier("method_id", self.method_id)
        _require_semver("method_version", self.method_version)
        _require_finite_binary64(
            "coulomb_coefficient_kilojoule_angstrom_per_mole_e2",
            self.coulomb_coefficient_kilojoule_angstrom_per_mole_e2,
            positive=True,
        )
        _require_finite_binary64(
            "relative_dielectric",
            self.relative_dielectric,
            positive=True,
        )
        effective_coulomb_coefficient = (
            self.coulomb_coefficient_kilojoule_angstrom_per_mole_e2
            / self.relative_dielectric
        )
        if (
            not math.isfinite(effective_coulomb_coefficient)
            or effective_coulomb_coefficient <= 0.0
        ):
            raise ValueError(
                "coulomb coefficient divided by relative dielectric must be "
                "positive finite binary64"
            )
        _require_finite_binary64(
            "minimum_distance_angstrom",
            self.minimum_distance_angstrom,
            positive=True,
        )
        if self.minimum_distance_angstrom >= _MAXIMUM_FINITE_BINARY64:
            raise ValueError(
                "minimum_distance_angstrom must be below maximum binary64"
            )
        _require_finite_binary64(
            "minimum_angle_sine",
            self.minimum_angle_sine,
            positive=True,
            less_than_one=True,
        )
        _require_finite_binary64(
            "minimum_proper_sine",
            self.minimum_proper_sine,
            positive=True,
            less_than_one=True,
        )
        for name in (
            "scientific_source_sha256",
            "scientific_review_sha256",
            "license_review_sha256",
            "release_attestation_sha256",
            "reference_method_id",
        ):
            if getattr(self, name) is not None:
                raise ValueError(
                    f"{name} must remain None for the nonphysical contract fixture"
                )

    @property
    def bounded_nonphysical_evaluation_method_contract_complete(self) -> bool:
        self._validate()
        return True

    def _false_gate(self) -> bool:
        self._validate()
        return False

    @property
    def production_evaluation_method_defined(self) -> bool:
        return self._false_gate()

    @property
    def diagnostic_evaluation_performed(self) -> bool:
        return self._false_gate()

    @property
    def energy_evaluated(self) -> bool:
        return self._false_gate()

    @property
    def forces_evaluated(self) -> bool:
        return self._false_gate()

    @property
    def virial_evaluated(self) -> bool:
        return self._false_gate()

    @property
    def energy_kernel_available(self) -> bool:
        return self._false_gate()

    @property
    def force_method_defined(self) -> bool:
        return self._false_gate()

    @property
    def virial_method_defined(self) -> bool:
        return self._false_gate()

    @property
    def scientifically_validated(self) -> bool:
        return self._false_gate()

    @property
    def physics_supported(self) -> bool:
        return self._false_gate()

    @property
    def production_parameter_assignment_complete(self) -> bool:
        return self._false_gate()

    @property
    def parameterability_assessed(self) -> bool:
        return self._false_gate()

    @property
    def global_parameter_coverage_complete(self) -> bool:
        return self._false_gate()

    @property
    def runtime_eligible(self) -> bool:
        return self._false_gate()

    @property
    def execution_authorized(self) -> bool:
        return self._false_gate()

    @property
    def energy_evaluation_authorized(self) -> bool:
        return self._false_gate()

    @property
    def force_evaluation_authorized(self) -> bool:
        return self._false_gate()

    @property
    def virial_evaluation_authorized(self) -> bool:
        return self._false_gate()

    @property
    def minimization_authorized(self) -> bool:
        return self._false_gate()

    @property
    def simulation_ready(self) -> bool:
        return self._false_gate()

    @property
    def claim_safe(self) -> bool:
        return self._false_gate()

    @property
    def blockers(self) -> tuple[str, ...]:
        self._validate()
        return (
            "coulomb_coefficient_and_thresholds_are_nonphysical_contract_fixtures",
            "scientific_source_fit_review_and_reference_validation_missing",
            "license_review_and_release_attestation_missing",
            "bounded_neutral_linear_c1_c4_tiny_reference_only",
            "direct_uncut_pair_method_has_no_scaling_claim",
            "energy_kernel_missing",
            "force_and_virial_methods_and_kernels_not_defined",
            "production_runtime_execution_and_claim_authority_prohibited",
            "digests_are_binding_not_authentication",
        )

    def _payload_document(self) -> dict[str, Any]:
        self._validate()
        return {
            "protocol_schema_id": _FROZEN_PROTOCOL_SCHEMA_ID,
            "protocol_sha256": _FROZEN_PROTOCOL_SHA256,
            "method_schema_id": _FROZEN_METHOD_SCHEMA_ID,
            "method_scope": _FROZEN_METHOD_SCOPE,
            "method_policy_id": _FROZEN_METHOD_POLICY_ID,
            "parameter_protocol_schema_id": (
                _FROZEN_PARAMETER_PROTOCOL_SCHEMA_ID
            ),
            "parameter_protocol_sha256": _FROZEN_PARAMETER_PROTOCOL_SHA256,
            "parameter_set_schema_id": _FROZEN_PARAMETER_SET_SCHEMA_ID,
            "parameter_assignment_policy_id": (
                _FROZEN_PARAMETER_ASSIGNMENT_POLICY_ID
            ),
            "assignment_schema_id": _FROZEN_ASSIGNMENT_SCHEMA_ID,
            "assignment_policy_id": _FROZEN_ASSIGNMENT_POLICY_ID,
            "pair_classification_policy_id": (
                _FROZEN_PAIR_CLASSIFICATION_POLICY_ID
            ),
            "pair_source_policy_id": _FROZEN_PAIR_SOURCE_POLICY_ID,
            "selected_pair_policy_id": _FROZEN_SELECTED_PAIR_POLICY_ID,
            "cutoff_policy_id": _FROZEN_CUTOFF_POLICY_ID,
            "r_switch_angstrom": None,
            "r_cut_angstrom": None,
            "switch_function_id": None,
            "switch_status": "not_applicable_no_cutoff",
            "neighbor_policy_id": _FROZEN_NEIGHBOR_POLICY_ID,
            "neighbor_skin_angstrom": None,
            "neighbor_capacity": None,
            "periodic_policy_id": _FROZEN_PERIODIC_POLICY_ID,
            "periodic_boundary_conditions": [False, False, False],
            "minimum_image_policy": None,
            "image_shift_policy": None,
            "electrostatics_pair_method_id": (
                _FROZEN_ELECTROSTATICS_PAIR_METHOD_ID
            ),
            "long_range_correction_method_id": None,
            "long_range_correction_status": (
                "not_applied_nonperiodic_direct_pair_sum"
            ),
            "reciprocal_space_method_id": None,
            "dispersion_tail_correction": False,
            "device": "cpu",
            "dtype": "torch.float64",
            "coordinate_model_count": 1,
            "coordinates_requires_grad": False,
            "cell_policy": "cell_free_only",
            "maximum_atom_count": _FROZEN_MAXIMUM_ATOM_COUNT,
            "maximum_unordered_pair_count": (
                _FROZEN_MAXIMUM_UNORDERED_PAIR_COUNT
            ),
            "maximum_selected_pair_count": _FROZEN_MAXIMUM_SELECTED_PAIR_COUNT,
            "coulomb_method_form_id": _FROZEN_COULOMB_METHOD_FORM_ID,
            "coulomb_coefficient_status": "nonphysical_contract_fixture",
            "coulomb_coefficient_kilojoule_angstrom_per_mole_e2_binary64": (
                _binary64_hex(
                    self.coulomb_coefficient_kilojoule_angstrom_per_mole_e2
                )
            ),
            "relative_dielectric_binary64": _binary64_hex(
                self.relative_dielectric
            ),
            "singularity_policy_id": _FROZEN_SINGULARITY_POLICY_ID,
            "geometry_domain_algorithm_id": _FROZEN_GEOMETRY_DOMAIN_ALGORITHM_ID,
            "minimum_distance_angstrom_binary64": _binary64_hex(
                self.minimum_distance_angstrom
            ),
            "minimum_angle_sine_binary64": _binary64_hex(
                self.minimum_angle_sine
            ),
            "minimum_proper_sine_binary64": _binary64_hex(
                self.minimum_proper_sine
            ),
            "nonfinite_policy_id": _FROZEN_NONFINITE_POLICY_ID,
            "accumulation_policy_id": _FROZEN_ACCUMULATION_POLICY_ID,
            "rounding_mode": "round_to_nearest_ties_to_even",
            "mixed_precision_status": "prohibited",
            "fast_math_status": "prohibited",
            "fma_contraction_status": "prohibited",
            "cross_platform_libm_bit_replay_status": "not_assessed",
            "bond_angle_functional_form_id": (
                _FROZEN_BOND_ANGLE_FUNCTIONAL_FORM_ID
            ),
            "proper_functional_form_id": _FROZEN_PROPER_FUNCTIONAL_FORM_ID,
            "proper_coordinate_convention_id": (
                _FROZEN_PROPER_COORDINATE_CONVENTION_ID
            ),
            "lj_functional_form_id": _FROZEN_LJ_FUNCTIONAL_FORM_ID,
            "lj_combining_rule_id": _FROZEN_LJ_COMBINING_RULE_ID,
            "lj_override_policy_id": _FROZEN_LJ_OVERRIDE_POLICY_ID,
            "method_definition_status": (
                "declared_nonphysical_contract_fixture_not_executed"
            ),
            "energy_kernel_status": "missing",
            "force_method_status": "not_defined",
            "virial_method_status": "not_defined",
            "unit_system": _unit_system_document(),
        }

    @property
    def method_payload_sha256(self) -> str:
        return _sha256_document(self._payload_document())

    def _core_dict(self) -> dict[str, Any]:
        payload = self._payload_document()
        return {
            "schema_id": _FROZEN_METHOD_SCHEMA_ID,
            "schema_version": _FROZEN_METHOD_SCHEMA_VERSION,
            "method_id": self.method_id,
            "method_version": self.method_version,
            "method_payload": payload,
            "method_payload_sha256": _sha256_document(payload),
            "artifact_purpose": "contract_fixture_only",
            "derivation_status": "declared_nonphysical_contract_fixture",
            "source_authentication_status": "not_authenticated",
            "scientific_validation_status": "missing",
            "license_review_status": "not_reviewed",
            "scientific_source_sha256": None,
            "scientific_review_sha256": None,
            "license_review_sha256": None,
            "release_attestation_sha256": None,
            "reference_method_id": None,
            "bounded_nonphysical_evaluation_method_contract_complete": True,
            "production_evaluation_method_defined": False,
            "diagnostic_evaluation_performed": False,
            "energy_evaluated": False,
            "forces_evaluated": False,
            "virial_evaluated": False,
            "energy_kernel_available": False,
            "force_method_defined": False,
            "virial_method_defined": False,
            "scientifically_validated": False,
            "physics_supported": False,
            "production_parameter_assignment_complete": False,
            "parameterability_assessed": False,
            "global_parameter_coverage_complete": False,
            "runtime_eligible": False,
            "execution_authorized": False,
            "energy_evaluation_authorized": False,
            "force_evaluation_authorized": False,
            "virial_evaluation_authorized": False,
            "minimization_authorized": False,
            "simulation_ready": False,
            "claim_safe": False,
            "blockers": list(self.blockers),
        }

    @property
    def method_sha256(self) -> str:
        return _sha256_document(self._core_dict())

    def to_dict(self) -> dict[str, Any]:
        document = self._core_dict()
        document["method_sha256"] = _sha256_document(document)
        return document


_ROOT_KEYS = frozenset(
    {
        "schema_id",
        "schema_version",
        "method_id",
        "method_version",
        "method_payload",
        "method_payload_sha256",
        "artifact_purpose",
        "derivation_status",
        "source_authentication_status",
        "scientific_validation_status",
        "license_review_status",
        "scientific_source_sha256",
        "scientific_review_sha256",
        "license_review_sha256",
        "release_attestation_sha256",
        "reference_method_id",
        "bounded_nonphysical_evaluation_method_contract_complete",
        "production_evaluation_method_defined",
        "diagnostic_evaluation_performed",
        "energy_evaluated",
        "forces_evaluated",
        "virial_evaluated",
        "energy_kernel_available",
        "force_method_defined",
        "virial_method_defined",
        "scientifically_validated",
        "physics_supported",
        "production_parameter_assignment_complete",
        "parameterability_assessed",
        "global_parameter_coverage_complete",
        "runtime_eligible",
        "execution_authorized",
        "energy_evaluation_authorized",
        "force_evaluation_authorized",
        "virial_evaluation_authorized",
        "minimization_authorized",
        "simulation_ready",
        "claim_safe",
        "blockers",
        "method_sha256",
    }
)
_PAYLOAD_KEYS = frozenset(
    {
        "protocol_schema_id",
        "protocol_sha256",
        "method_schema_id",
        "method_scope",
        "method_policy_id",
        "parameter_protocol_schema_id",
        "parameter_protocol_sha256",
        "parameter_set_schema_id",
        "parameter_assignment_policy_id",
        "assignment_schema_id",
        "assignment_policy_id",
        "pair_classification_policy_id",
        "pair_source_policy_id",
        "selected_pair_policy_id",
        "cutoff_policy_id",
        "r_switch_angstrom",
        "r_cut_angstrom",
        "switch_function_id",
        "switch_status",
        "neighbor_policy_id",
        "neighbor_skin_angstrom",
        "neighbor_capacity",
        "periodic_policy_id",
        "periodic_boundary_conditions",
        "minimum_image_policy",
        "image_shift_policy",
        "electrostatics_pair_method_id",
        "long_range_correction_method_id",
        "long_range_correction_status",
        "reciprocal_space_method_id",
        "dispersion_tail_correction",
        "device",
        "dtype",
        "coordinate_model_count",
        "coordinates_requires_grad",
        "cell_policy",
        "maximum_atom_count",
        "maximum_unordered_pair_count",
        "maximum_selected_pair_count",
        "coulomb_method_form_id",
        "coulomb_coefficient_status",
        "coulomb_coefficient_kilojoule_angstrom_per_mole_e2_binary64",
        "relative_dielectric_binary64",
        "singularity_policy_id",
        "geometry_domain_algorithm_id",
        "minimum_distance_angstrom_binary64",
        "minimum_angle_sine_binary64",
        "minimum_proper_sine_binary64",
        "nonfinite_policy_id",
        "accumulation_policy_id",
        "rounding_mode",
        "mixed_precision_status",
        "fast_math_status",
        "fma_contraction_status",
        "cross_platform_libm_bit_replay_status",
        "bond_angle_functional_form_id",
        "proper_functional_form_id",
        "proper_coordinate_convention_id",
        "lj_functional_form_id",
        "lj_combining_rule_id",
        "lj_override_policy_id",
        "method_definition_status",
        "energy_kernel_status",
        "force_method_status",
        "virial_method_status",
        "unit_system",
    }
)


def _require_mapping(value: Any, *, location: str) -> dict[str, Any]:
    if type(value) is not dict:
        raise LinearAlkaneEvaluationMethodSerializationError(
            f"{location} must be a JSON object"
        )
    return value


def _require_string(value: Any, *, location: str) -> str:
    if type(value) is not str:
        raise LinearAlkaneEvaluationMethodSerializationError(
            f"{location} must be a JSON string"
        )
    return value


def _require_exact_keys(
    value: Mapping[str, Any],
    expected: frozenset[str],
    *,
    location: str,
) -> None:
    observed = set(value)
    if observed != expected:
        raise LinearAlkaneEvaluationMethodSerializationError(
            f"{location} keys mismatch; missing={sorted(expected-observed)}, "
            f"extra={sorted(observed-expected)}"
        )


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise LinearAlkaneEvaluationMethodSerializationError(
                f"duplicate JSON object key {key!r}"
            )
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise LinearAlkaneEvaluationMethodSerializationError(
        f"nonstandard JSON constant {value!r} is not allowed"
    )


def serialize_linear_alkane_c1_c4_evaluation_method(
    method: LinearAlkaneC1C4EvaluationMethod,
) -> bytes:
    """Serialize a validated bounded method artifact to canonical JSON."""

    if type(method) is not LinearAlkaneC1C4EvaluationMethod:
        raise TypeError("method must be an exact C1-C4 evaluation method")
    method._validate()
    return _canonical_json_bytes(method.to_dict())


def deserialize_linear_alkane_c1_c4_evaluation_method(
    data: bytes,
) -> LinearAlkaneC1C4EvaluationMethod:
    """Parse strict method bytes and recompute all fixed semantics and hashes."""

    if type(data) is not bytes:
        raise LinearAlkaneEvaluationMethodSerializationError(
            "evaluation-method artifact must be exact bytes"
        )
    if len(data) > _MAX_ARTIFACT_BYTES:
        raise LinearAlkaneEvaluationMethodSerializationError(
            "evaluation-method artifact exceeds the 64-KiB limit"
        )
    try:
        text = data.decode("ascii")
    except UnicodeDecodeError as exc:
        raise LinearAlkaneEvaluationMethodSerializationError(
            "evaluation-method artifact must be ASCII"
        ) from exc
    try:
        document = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_json_constant,
        )
    except LinearAlkaneEvaluationMethodSerializationError:
        raise
    except (json.JSONDecodeError, RecursionError, ValueError) as exc:
        raise LinearAlkaneEvaluationMethodSerializationError(
            f"invalid evaluation-method JSON: {exc}"
        ) from exc
    root = _require_mapping(document, location="root")
    _require_exact_keys(root, _ROOT_KEYS, location="root")
    payload = _require_mapping(root["method_payload"], location="method_payload")
    _require_exact_keys(payload, _PAYLOAD_KEYS, location="method_payload")
    try:
        result = LinearAlkaneC1C4EvaluationMethod(
            method_id=_require_string(root["method_id"], location="method_id"),
            method_version=_require_string(
                root["method_version"],
                location="method_version",
            ),
            coulomb_coefficient_kilojoule_angstrom_per_mole_e2=(
                _binary64_from_hex(
                    (
                        "method_payload."
                        "coulomb_coefficient_kilojoule_angstrom_per_mole_e2_"
                        "binary64"
                    ),
                    payload[
                        "coulomb_coefficient_kilojoule_angstrom_per_mole_e2_"
                        "binary64"
                    ],
                )
            ),
            relative_dielectric=_binary64_from_hex(
                "method_payload.relative_dielectric_binary64",
                payload["relative_dielectric_binary64"],
            ),
            minimum_distance_angstrom=_binary64_from_hex(
                "method_payload.minimum_distance_angstrom_binary64",
                payload["minimum_distance_angstrom_binary64"],
            ),
            minimum_angle_sine=_binary64_from_hex(
                "method_payload.minimum_angle_sine_binary64",
                payload["minimum_angle_sine_binary64"],
            ),
            minimum_proper_sine=_binary64_from_hex(
                "method_payload.minimum_proper_sine_binary64",
                payload["minimum_proper_sine_binary64"],
            ),
            scientific_source_sha256=root["scientific_source_sha256"],
            scientific_review_sha256=root["scientific_review_sha256"],
            license_review_sha256=root["license_review_sha256"],
            release_attestation_sha256=root["release_attestation_sha256"],
            reference_method_id=root["reference_method_id"],
        )
    except LinearAlkaneEvaluationMethodSerializationError:
        raise
    except (TypeError, ValueError, KeyError, OverflowError) as exc:
        raise LinearAlkaneEvaluationMethodSerializationError(
            f"evaluation-method contract validation failed: {exc}"
        ) from exc
    canonical = serialize_linear_alkane_c1_c4_evaluation_method(result)
    if canonical != data:
        raise LinearAlkaneEvaluationMethodSerializationError(
            "evaluation-method artifact is noncanonical, stale, or tampered"
        )
    return result


__all__ = [
    "LINEAR_ALKANE_EVALUATION_METHOD_ACCUMULATION_POLICY_ID",
    "LINEAR_ALKANE_EVALUATION_METHOD_POLICY_ID",
    "LINEAR_ALKANE_EVALUATION_METHOD_PROTOCOL_SCHEMA_ID",
    "LINEAR_ALKANE_EVALUATION_METHOD_PROTOCOL_SCHEMA_VERSION",
    "LINEAR_ALKANE_EVALUATION_METHOD_PROTOCOL_SHA256",
    "LINEAR_ALKANE_EVALUATION_METHOD_SCHEMA_ID",
    "LINEAR_ALKANE_EVALUATION_METHOD_SCHEMA_VERSION",
    "LINEAR_ALKANE_EVALUATION_METHOD_SCOPE",
    "LINEAR_ALKANE_EVALUATION_METHOD_SINGULARITY_POLICY_ID",
    "LinearAlkaneC1C4EvaluationMethod",
    "LinearAlkaneEvaluationMethodContractError",
    "LinearAlkaneEvaluationMethodSerializationError",
    "deserialize_linear_alkane_c1_c4_evaluation_method",
    "linear_alkane_evaluation_method_protocol_bytes",
    "linear_alkane_evaluation_method_protocol_document",
    "serialize_linear_alkane_c1_c4_evaluation_method",
]
