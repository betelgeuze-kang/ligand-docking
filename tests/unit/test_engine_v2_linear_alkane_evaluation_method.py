from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys

import pytest

from betelgeuze_engine_v2.forcefield import linear_alkane_evaluation_method as module
from betelgeuze_engine_v2.forcefield.linear_alkane_evaluation_method import (
    LINEAR_ALKANE_EVALUATION_METHOD_POLICY_ID,
    LINEAR_ALKANE_EVALUATION_METHOD_PROTOCOL_SCHEMA_ID,
    LINEAR_ALKANE_EVALUATION_METHOD_PROTOCOL_SHA256,
    LINEAR_ALKANE_EVALUATION_METHOD_SCHEMA_ID,
    LinearAlkaneC1C4EvaluationMethod,
    LinearAlkaneEvaluationMethodSerializationError,
    deserialize_linear_alkane_c1_c4_evaluation_method,
    linear_alkane_evaluation_method_protocol_bytes,
    linear_alkane_evaluation_method_protocol_document,
    serialize_linear_alkane_c1_c4_evaluation_method,
)
from betelgeuze_engine_v2.forcefield.linear_alkane_parameters import (
    LINEAR_ALKANE_PARAMETER_PROTOCOL_SHA256,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


def _method(
    *,
    coulomb_coefficient: float = 1.0,
    relative_dielectric: float = 1.0,
    minimum_distance: float = 1.0e-8,
    minimum_angle_sine: float = 1.0e-8,
    minimum_proper_sine: float = 1.0e-8,
) -> LinearAlkaneC1C4EvaluationMethod:
    return LinearAlkaneC1C4EvaluationMethod(
        method_id="nonphysical.linear_alkane_c1_c4.direct_uncut",
        method_version="1.0.0",
        coulomb_coefficient_kilojoule_angstrom_per_mole_e2=(
            coulomb_coefficient
        ),
        relative_dielectric=relative_dielectric,
        minimum_distance_angstrom=minimum_distance,
        minimum_angle_sine=minimum_angle_sine,
        minimum_proper_sine=minimum_proper_sine,
    )


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _rehash_document(document: dict[str, object]) -> bytes:
    payload = document["method_payload"]
    assert type(payload) is dict
    document["method_payload_sha256"] = hashlib.sha256(
        _canonical_bytes(payload)
    ).hexdigest()
    document.pop("method_sha256", None)
    document["method_sha256"] = hashlib.sha256(
        _canonical_bytes(document)
    ).hexdigest()
    return _canonical_bytes(document)


def _all_keys(value: object) -> set[str]:
    if type(value) is dict:
        result = set(value)
        for nested in value.values():
            result.update(_all_keys(nested))
        return result
    if type(value) is list:
        result: set[str] = set()
        for nested in value:
            result.update(_all_keys(nested))
        return result
    return set()


def test_protocol_is_frozen_direct_uncut_and_binds_upstream_contracts() -> None:
    document = linear_alkane_evaluation_method_protocol_document()
    payload = linear_alkane_evaluation_method_protocol_bytes()

    assert document["schema_id"] == (
        LINEAR_ALKANE_EVALUATION_METHOD_PROTOCOL_SCHEMA_ID
    )
    assert len(payload) == 7719
    assert LINEAR_ALKANE_EVALUATION_METHOD_PROTOCOL_SHA256 == (
        "7a8416632d83cab3e32ebbbdc43549d59b5a4efb472283d07f773ad66de461da"
    )
    assert hashlib.sha256(payload).hexdigest() == (
        LINEAR_ALKANE_EVALUATION_METHOD_PROTOCOL_SHA256
    )
    assert json.loads(payload) == document
    assert document["parameter_protocol_sha256"] == (
        LINEAR_ALKANE_PARAMETER_PROTOCOL_SHA256
    )
    assert document["assignment_schema_id"] == (
        "betelgeuze.linear_alkane_c1_c4_parameter_assignment/1.0.0"
    )
    assert document["method_policy_id"] == (
        LINEAR_ALKANE_EVALUATION_METHOD_POLICY_ID
    )

    domain = document["method_domain"]
    assert domain == {
        "molecule_domain": (
            "source_bound_explicit_h_neutral_linear_alkane_c1_c4_only"
        ),
        "maximum_atom_count": 14,
        "maximum_unordered_pair_count": 91,
        "maximum_selected_pair_count": 54,
        "coordinate_model_count": 1,
        "coordinate_shape": "[1,N,3]",
        "coordinate_unit": "angstrom",
        "device": "cpu",
        "dtype": "torch.float64",
        "cell_policy": "cell_free_only",
        "coordinate_layout": "torch.strided_materialized",
        "coordinate_contiguity": "not_required_snapshot_is_contiguous",
        "coordinates_requires_grad": False,
    }


def test_protocol_closes_pair_cutoff_coulomb_and_periodic_semantics() -> None:
    document = linear_alkane_evaluation_method_protocol_document()
    energy = document["scalar_energy_semantics"]
    pairs = document["pair_selection_semantics"]
    cutoff = document["cutoff_and_neighbor_semantics"]
    periodic = document["periodic_and_long_range_semantics"]

    assert energy["coulomb_pair"] == "U_q=(k_e/epsilon_r)*q_i*q_j/r"
    assert energy["coulomb_binary64_operation_order"] == [
        "effective_coefficient=k_e/epsilon_r",
        "charge_product_1=effective_coefficient*q_i",
        "charge_product_2=charge_product_1*q_j",
        "U_q=charge_product_2/r",
    ]
    assert energy["coulomb_coefficient_includes_dielectric"] is False
    assert energy["one_four"] == (
        "U_1_4=math_fsum([s_lj*U_lj,s_q*U_q])"
    )
    assert energy["full_nonbonded"] == "U_full=math_fsum([U_lj,U_q])"
    assert energy["assigned_lj_sigma_epsilon_recombination_or_modification"] == (
        "prohibited"
    )
    assert energy["one_four_energy_scale_application"] == (
        "required_exactly_once_after_assigned_lj_resolution"
    )
    assert pairs["excluded_1_2"] == "omit"
    assert pairs["excluded_1_3"] == "omit"
    assert pairs["c1_all_pair_count"] == 10
    assert pairs["c1_selected_pair_count"] == 0
    assert pairs["c4_all_pair_count"] == 91
    assert pairs["c4_selected_pair_count"] == 54
    assert pairs[
        "vacuous_c1_selected_subset_requires_full_inventory_identity_check"
    ] is True
    assert cutoff["r_switch_angstrom"] is None
    assert cutoff["r_cut_angstrom"] is None
    assert cutoff["switch_status"] == "not_applicable_no_cutoff"
    assert cutoff["null_cutoff_interpretation"] == (
        "not_a_default_zero_or_infinity"
    )
    assert cutoff["dense_n_by_n_pair_materialization"] == "prohibited"
    assert periodic["periodic_boundary_conditions"] == [False, False, False]
    assert periodic["minimum_image_policy"] is None
    assert periodic["image_shift_policy"] is None
    assert periodic["electrostatics_pair_method_id"].startswith(
        "direct_nonperiodic_uncut_selected_pairs_tiny_reference_only"
    )
    assert periodic["long_range_correction_method_id"] is None
    assert periodic["reciprocal_space_method_id"] is None
    assert periodic["dispersion_tail_correction"] is False


def test_protocol_freezes_singularity_accumulation_and_numeric_policy() -> None:
    document = linear_alkane_evaluation_method_protocol_document()
    geometry = document["geometry_domain_semantics"]
    accumulation = document["accumulation_semantics"]
    numeric = document["numeric_execution_semantics"]
    status = document["definition_status"]

    assert geometry["threshold_equality"] == "reject"
    assert geometry["assessment_algorithm_id"] == (
        "cpu_binary64_hypot_unit_vector_cross_sine_threshold_check/1.0.0"
    )
    assert geometry["regularization"] == "prohibited"
    assert geometry["clamping"] == "prohibited"
    assert geometry["softcore"] == "prohibited"
    assert geometry["epsilon_injection"] == "prohibited"
    assert accumulation["term_class_order"] == [
        "bond",
        "angle",
        "proper",
        "selected_nonbonded_pair",
    ]
    assert accumulation["proper_component_reduction"] == (
        "math_fsum_binary64"
    )
    assert accumulation["pair_inner_order"] == (
        "scaled_lj_then_scaled_coulomb"
    )
    assert accumulation["pair_inner_reduction"] == "math_fsum_binary64"
    assert accumulation["force_accumulation"] == "not_defined_no_kernel"
    assert accumulation["virial_accumulation"] == "not_defined_no_kernel"
    assert numeric == {
        "device": "cpu",
        "dtype": "ieee754_binary64",
        "rounding_mode": "round_to_nearest_ties_to_even",
        "mixed_precision": "prohibited",
        "fast_math": "prohibited",
        "fma_contraction": "prohibited",
        "cross_platform_libm_bit_replay_status": "not_assessed",
    }
    assert status["evaluation_performed"] is False
    assert status["energy_kernel"] == "missing"
    assert status["force_method"] == "not_defined"
    assert status["virial_method"] == "not_defined"


def test_protocol_returns_fresh_copies() -> None:
    first = linear_alkane_evaluation_method_protocol_document()
    first["method_domain"]["maximum_atom_count"] = 10_000
    assert linear_alkane_evaluation_method_protocol_document()[
        "method_domain"
    ]["maximum_atom_count"] == 14
    assert linear_alkane_evaluation_method_protocol_bytes() == (
        linear_alkane_evaluation_method_protocol_bytes()
    )


def test_method_roundtrip_hashes_and_nonphysical_values_are_frozen() -> None:
    method = _method()
    payload = serialize_linear_alkane_c1_c4_evaluation_method(method)
    document = json.loads(payload)

    assert len(payload) == 6483
    assert method.method_payload_sha256 == (
        "8d37464e35d8abe59a0950c51d2e6b857092d4853504c405ee865fc0515727f2"
    )
    assert method.method_sha256 == (
        "13b7e1ccfc77c5e530846882916453d4600bf19046aa5633b5c30b816a81d5f9"
    )
    assert hashlib.sha256(payload).hexdigest() == (
        "e017b0028727d94411456c3e0d88d2923b90e11f931b77841ef0d1c744535335"
    )
    assert deserialize_linear_alkane_c1_c4_evaluation_method(payload) == method
    assert document["schema_id"] == LINEAR_ALKANE_EVALUATION_METHOD_SCHEMA_ID
    method_payload = document["method_payload"]
    assert method_payload[
        "coulomb_coefficient_kilojoule_angstrom_per_mole_e2_binary64"
    ] == "3ff0000000000000"
    assert method_payload["relative_dielectric_binary64"] == "3ff0000000000000"
    assert method_payload["minimum_distance_angstrom_binary64"] == (
        "3e45798ee2308c3a"
    )
    assert method_payload["minimum_angle_sine_binary64"] == (
        "3e45798ee2308c3a"
    )
    assert method_payload["minimum_proper_sine_binary64"] == (
        "3e45798ee2308c3a"
    )


def test_only_scoped_method_contract_is_true_and_no_results_exist() -> None:
    method = _method()
    document = method.to_dict()

    assert method.bounded_nonphysical_evaluation_method_contract_complete is True
    false_gates = (
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
    )
    assert all(getattr(method, name) is False for name in false_gates)
    assert all(document[name] is False for name in false_gates)
    assert {
        "energy_value",
        "forces",
        "force_values",
        "virial",
        "virial_value",
        "per_term_energies",
    }.isdisjoint(_all_keys(document))


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("coulomb_coefficient_kilojoule_angstrom_per_mole_e2", 0.0),
        ("coulomb_coefficient_kilojoule_angstrom_per_mole_e2", -1.0),
        ("coulomb_coefficient_kilojoule_angstrom_per_mole_e2", -0.0),
        ("coulomb_coefficient_kilojoule_angstrom_per_mole_e2", math.inf),
        ("coulomb_coefficient_kilojoule_angstrom_per_mole_e2", math.nan),
        ("relative_dielectric", 0.0),
        ("relative_dielectric", -1.0),
        ("relative_dielectric", -0.0),
        ("minimum_distance_angstrom", 0.0),
        ("minimum_distance_angstrom", -1.0),
        (
            "minimum_distance_angstrom",
            float.fromhex("0x1.fffffffffffffp+1023"),
        ),
        ("minimum_angle_sine", 0.0),
        ("minimum_angle_sine", 1.0),
        ("minimum_angle_sine", math.inf),
        ("minimum_proper_sine", 0.0),
        ("minimum_proper_sine", 1.0),
        ("minimum_proper_sine", math.nan),
    ),
)
def test_invalid_numeric_domains_fail_closed(field: str, value: float) -> None:
    with pytest.raises((TypeError, ValueError)):
        replace(_method(), **{field: value})


@pytest.mark.parametrize(
    "value",
    (True, 1, "1.0"),
)
def test_numeric_fields_require_exact_float(value: object) -> None:
    with pytest.raises(TypeError):
        replace(
            _method(),
            coulomb_coefficient_kilojoule_angstrom_per_mole_e2=value,
        )


def test_positive_subnormal_and_maximum_finite_binary64_are_representable() -> None:
    subnormal = math.ldexp(1.0, -1074)
    maximum = float.fromhex("0x1.fffffffffffffp+1023")
    first = _method(coulomb_coefficient=subnormal)
    second = _method(coulomb_coefficient=maximum, relative_dielectric=maximum)
    assert deserialize_linear_alkane_c1_c4_evaluation_method(
        serialize_linear_alkane_c1_c4_evaluation_method(first)
    ) == first
    assert deserialize_linear_alkane_c1_c4_evaluation_method(
        serialize_linear_alkane_c1_c4_evaluation_method(second)
    ) == second


def test_nonfinite_or_zero_effective_coulomb_coefficient_is_rejected() -> None:
    subnormal = math.ldexp(1.0, -1074)
    maximum = float.fromhex("0x1.fffffffffffffp+1023")
    with pytest.raises(ValueError, match="divided by relative dielectric"):
        _method(coulomb_coefficient=maximum, relative_dielectric=subnormal)
    with pytest.raises(ValueError, match="divided by relative dielectric"):
        _method(coulomb_coefficient=subnormal, relative_dielectric=maximum)


def test_identifiers_versions_and_evidence_are_strict() -> None:
    class StringSubclass(str):
        pass

    with pytest.raises(TypeError):
        replace(_method(), method_id=StringSubclass("forged.method"))
    with pytest.raises(ValueError):
        replace(_method(), method_id="not canonical whitespace")
    with pytest.raises(ValueError):
        replace(_method(), method_version="01.0.0")
    with pytest.raises(ValueError):
        replace(_method(), scientific_source_sha256="0" * 64)
    with pytest.raises(ValueError):
        replace(_method(), reference_method_id="forbidden")


def test_artifact_is_frozen_and_exact_type_is_required() -> None:
    method = _method()
    with pytest.raises(FrozenInstanceError):
        method.relative_dielectric = 2.0  # type: ignore[misc]
    with pytest.raises(TypeError):
        serialize_linear_alkane_c1_c4_evaluation_method(object())  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "mutation",
    (
        "payload_fixed_field",
        "payload_hash",
        "root_fixed_gate",
        "root_hash",
        "unknown_root",
        "missing_root",
        "unknown_payload",
        "missing_payload",
    ),
)
def test_strict_parser_rejects_tampering_even_with_recomputed_hashes(
    mutation: str,
) -> None:
    document = json.loads(serialize_linear_alkane_c1_c4_evaluation_method(_method()))
    payload = document["method_payload"]
    assert type(payload) is dict
    if mutation == "payload_fixed_field":
        payload["maximum_atom_count"] = 13
        data = _rehash_document(document)
    elif mutation == "payload_hash":
        document["method_payload_sha256"] = "0" * 64
        data = _canonical_bytes(document)
    elif mutation == "root_fixed_gate":
        document["runtime_eligible"] = True
        data = _rehash_document(document)
    elif mutation == "root_hash":
        document["method_sha256"] = "0" * 64
        data = _canonical_bytes(document)
    elif mutation == "unknown_root":
        document["unknown"] = None
        data = _canonical_bytes(document)
    elif mutation == "missing_root":
        document.pop("claim_safe")
        data = _canonical_bytes(document)
    elif mutation == "unknown_payload":
        payload["unknown"] = None
        data = _canonical_bytes(document)
    else:
        payload.pop("r_cut_angstrom")
        data = _canonical_bytes(document)
    with pytest.raises(LinearAlkaneEvaluationMethodSerializationError):
        deserialize_linear_alkane_c1_c4_evaluation_method(data)


def test_rehashed_variable_numeric_field_is_a_distinct_valid_method() -> None:
    document = json.loads(serialize_linear_alkane_c1_c4_evaluation_method(_method()))
    payload = document["method_payload"]
    assert type(payload) is dict
    payload["relative_dielectric_binary64"] = "4000000000000000"
    changed = deserialize_linear_alkane_c1_c4_evaluation_method(
        _rehash_document(document)
    )
    assert changed.relative_dielectric == 2.0
    assert changed.method_sha256 != _method().method_sha256


def test_parser_rejects_duplicate_noncanonical_nonascii_and_oversized_bytes() -> None:
    canonical = serialize_linear_alkane_c1_c4_evaluation_method(_method())
    duplicate = canonical.replace(
        b'"method_id":',
        b'"method_id":"duplicate","method_id":',
        1,
    )
    with pytest.raises(LinearAlkaneEvaluationMethodSerializationError):
        deserialize_linear_alkane_c1_c4_evaluation_method(duplicate)
    with pytest.raises(LinearAlkaneEvaluationMethodSerializationError):
        deserialize_linear_alkane_c1_c4_evaluation_method(
            json.dumps(json.loads(canonical), indent=2).encode("ascii")
        )
    with pytest.raises(LinearAlkaneEvaluationMethodSerializationError):
        deserialize_linear_alkane_c1_c4_evaluation_method(canonical + "é".encode())
    with pytest.raises(LinearAlkaneEvaluationMethodSerializationError):
        deserialize_linear_alkane_c1_c4_evaluation_method(b"{" + b" " * 65536)
    with pytest.raises(LinearAlkaneEvaluationMethodSerializationError):
        deserialize_linear_alkane_c1_c4_evaluation_method(bytearray(canonical))  # type: ignore[arg-type]


def test_parser_rejects_nonstandard_json_constants() -> None:
    canonical = serialize_linear_alkane_c1_c4_evaluation_method(_method())
    forged = canonical.replace(b'"claim_safe":false', b'"claim_safe":NaN', 1)
    with pytest.raises(LinearAlkaneEvaluationMethodSerializationError):
        deserialize_linear_alkane_c1_c4_evaluation_method(forged)


def test_public_alias_forgery_cannot_change_frozen_bytes_or_artifact() -> None:
    protocol_before = linear_alkane_evaluation_method_protocol_bytes()
    artifact_before = serialize_linear_alkane_c1_c4_evaluation_method(_method())
    original_schema = module.LINEAR_ALKANE_EVALUATION_METHOD_SCHEMA_ID
    original_policy = module.LINEAR_ALKANE_EVALUATION_METHOD_POLICY_ID
    try:
        module.LINEAR_ALKANE_EVALUATION_METHOD_SCHEMA_ID = "forged/9.9.9"
        module.LINEAR_ALKANE_EVALUATION_METHOD_POLICY_ID = "forged/9.9.9"
        assert linear_alkane_evaluation_method_protocol_bytes() == protocol_before
        assert serialize_linear_alkane_c1_c4_evaluation_method(_method()) == (
            artifact_before
        )
    finally:
        module.LINEAR_ALKANE_EVALUATION_METHOD_SCHEMA_ID = original_schema
        module.LINEAR_ALKANE_EVALUATION_METHOD_POLICY_ID = original_policy


@pytest.mark.parametrize("seed", ("0", "1", "42", "random"))
def test_protocol_and_artifact_are_hashseed_stable(seed: str) -> None:
    script = """
import hashlib
from betelgeuze_engine_v2.forcefield.linear_alkane_evaluation_method import (
    LinearAlkaneC1C4EvaluationMethod,
    linear_alkane_evaluation_method_protocol_bytes,
    serialize_linear_alkane_c1_c4_evaluation_method,
)
m = LinearAlkaneC1C4EvaluationMethod(
    method_id='nonphysical.linear_alkane_c1_c4.direct_uncut',
    method_version='1.0.0',
    coulomb_coefficient_kilojoule_angstrom_per_mole_e2=1.0,
    relative_dielectric=1.0,
    minimum_distance_angstrom=1e-8,
    minimum_angle_sine=1e-8,
    minimum_proper_sine=1e-8,
)
print(hashlib.sha256(linear_alkane_evaluation_method_protocol_bytes()).hexdigest())
print(hashlib.sha256(serialize_linear_alkane_c1_c4_evaluation_method(m)).hexdigest())
"""
    env = dict(os.environ)
    env["PYTHONHASHSEED"] = seed
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=REPO_ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    assert completed.stdout.splitlines() == [
        LINEAR_ALKANE_EVALUATION_METHOD_PROTOCOL_SHA256,
        hashlib.sha256(
            serialize_linear_alkane_c1_c4_evaluation_method(_method())
        ).hexdigest(),
    ]
