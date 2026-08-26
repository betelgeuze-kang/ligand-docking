from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "water_box_reference_v1",
    ROOT / "tools/run_engine_v2_water_box_reference_v1.py",
)
assert SPEC is not None and SPEC.loader is not None
WATER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(WATER)
PROFILE = WATER.load_profile(ROOT / "config/engine_v2_water_box_reference_v1.json")
NATIVE_PROFILE = WATER.load_profile(
    ROOT / "config/engine_v2_native_water_box_profile_v1.json"
)
CONSTRAINTS_PROFILE = json.loads(
    (ROOT / "config/engine_v2_native_water_box_constraints_profile_v1.json").read_text()
)
NVT_ENSEMBLE_PROFILE = json.loads(
    (
        ROOT / "config/engine_v2_native_water_box_nvt_ensemble_profile_v1.json"
    ).read_text()
)
NVT_CONSTRAINT_RESIDUAL_PROFILE = json.loads(
    (
        ROOT
        / "config/engine_v2_native_water_box_nvt_constraint_residual_profile_v1.json"
    ).read_text()
)
NEIGHBOR_LIST_PROFILE = json.loads(
    (
        ROOT / "config/engine_v2_native_periodic_neighbor_list_profile_v1.json"
    ).read_text()
)
NEIGHBOR_CACHE_PROFILE = json.loads(
    (
        ROOT / "config/engine_v2_native_periodic_neighbor_list_profile_v2.json"
    ).read_text()
)
ION_PROFILE = json.loads(
    (ROOT / "config/engine_v2_native_water_ion_profile_v1.json").read_text()
)
ION_DYNAMICS_PROFILE = json.loads(
    (
        ROOT / "config/engine_v2_native_water_ion_dynamics_profile_v1.json"
    ).read_text()
)
DYNAMICS_FAILURE_PROFILE = json.loads(
    (
        ROOT
        / "config/engine_v2_native_water_box_dynamics_failure_profile_v1.json"
    ).read_text()
)
DYNAMICS_FAILURE_BOUNDARY_PROFILE = json.loads(
    (
        ROOT
        / "config/engine_v2_native_water_box_dynamics_failure_profile_v2.json"
    ).read_text()
)
DYNAMICS_EXCEPTION_BOUNDARY_MATRIX_PROFILE = json.loads(
    (
        ROOT
        / "config/engine_v2_native_water_box_dynamics_failure_profile_v3.json"
    ).read_text()
)


def test_native_profile_matches_the_packaged_runtime_asset() -> None:
    canonical = (
        ROOT / "config/engine_v2_native_water_box_profile_v1.json"
    ).read_bytes()
    packaged = (
        ROOT
        / "rust/betelgeuze-runtime/assets/engine_v2_native_water_box_profile_v1.json"
    ).read_bytes()
    assert packaged == canonical
    assert hashlib.sha256(canonical).hexdigest() == (
        "2b0be83b57085c655092ab0272aea5a91b9c3f90c344fa062d494ad324f0019e"
    )


def test_native_constraints_profile_matches_the_packaged_runtime_asset() -> None:
    canonical = (
        ROOT / "config/engine_v2_native_water_box_constraints_profile_v1.json"
    ).read_bytes()
    packaged = (
        ROOT
        / "rust/betelgeuze-runtime/assets/engine_v2_native_water_box_constraints_profile_v1.json"
    ).read_bytes()
    assert packaged == canonical
    assert hashlib.sha256(canonical).hexdigest() == (
        "8dcad0b5005b7a768ce0a88b1804b55ecddb9b3490e2dd59179dfa2393433507"
    )
    assert CONSTRAINTS_PROFILE["predecessor"]["sha256"] == (
        "2b0be83b57085c655092ab0272aea5a91b9c3f90c344fa062d494ad324f0019e"
    )
    constraints = CONSTRAINTS_PROFILE["constraints"]
    assert constraints["rows_per_water"] * constraints["water_count"] == 6
    positions, *_ = WATER.build_box(NATIVE_PROFILE)
    assert constraints["hh_distance_angstrom"] == pytest.approx(
        np.linalg.norm(positions[1] - positions[2]), abs=1.0e-15
    )
    assert constraints["expected_degrees_of_freedom"] == 12
    assert all(value is False for value in CONSTRAINTS_PROFILE["authority"].values())


def test_native_nvt_ensemble_profile_matches_the_packaged_runtime_asset() -> None:
    canonical = (
        ROOT / "config/engine_v2_native_water_box_nvt_ensemble_profile_v1.json"
    ).read_bytes()
    packaged = (
        ROOT
        / "rust/betelgeuze-runtime/assets/engine_v2_native_water_box_nvt_ensemble_profile_v1.json"
    ).read_bytes()
    assert packaged == canonical
    assert hashlib.sha256(canonical).hexdigest() == (
        "bb2577c0e227151b8aa95b5c288249823206020558a186eccc8b5ddcbca802de"
    )
    assert NVT_ENSEMBLE_PROFILE["predecessor"]["sha256"] == (
        "c9e671b925b8f5da48a43dec2abe264e695840b277cc3cf4a84aa7255b59150d"
    )
    assert NVT_ENSEMBLE_PROFILE["system_bindings"] == {
        "water_profile_sha256": (
            "2b0be83b57085c655092ab0272aea5a91b9c3f90c344fa062d494ad324f0019e"
        ),
        "constraint_profile_sha256": (
            "8dcad0b5005b7a768ce0a88b1804b55ecddb9b3490e2dd59179dfa2393433507"
        ),
        "atom_count": 6,
        "water_count": 2,
        "expected_degrees_of_freedom": 12,
    }
    sampling = NVT_ENSEMBLE_PROFILE["sampling"]
    assert sampling == {
        "integrator": "constrained_langevin_baoab",
        "timestep_femtoseconds": 0.5,
        "target_temperature_kelvin": 300.0,
        "friction_per_femtosecond": 0.01,
        "ordered_random_seeds": [101, 211, 307, 401, 503, 601, 701, 809],
        "burn_in_steps_per_seed": 2000,
        "sample_count_per_seed": 32,
        "sample_stride_steps": 100,
    }
    validation = NVT_ENSEMBLE_PROFILE["validation"]
    assert validation["cpu_backends"] == ["cpp_cpu_reference", "rust_cpu"]
    assert validation["same_seed_repeatability_required"] is True
    assert validation["ordered_observation_receipt_required"] is True
    assert validation["kinetic_temperature_identity_required"] is True
    assert validation["minimum_mean_temperature_kelvin"] == 240.0
    assert validation["maximum_mean_temperature_kelvin"] == 360.0
    assert validation["nonzero_temperature_variance_required"] is True
    assert validation["performance_measurement_present"] is False
    assert validation["performance_threshold_present"] is False
    assert all(
        value is False for value in NVT_ENSEMBLE_PROFILE["authority"].values()
    )


def test_native_nvt_constraint_residual_profile_matches_packaged_asset() -> None:
    canonical = (
        ROOT
        / "config/engine_v2_native_water_box_nvt_constraint_residual_profile_v1.json"
    ).read_bytes()
    packaged = (
        ROOT
        / "rust/betelgeuze-runtime/assets/engine_v2_native_water_box_nvt_constraint_residual_profile_v1.json"
    ).read_bytes()
    assert packaged == canonical
    assert hashlib.sha256(canonical).hexdigest() == (
        "a92070ade1d214e9526a101666b49e8a7d5b909888293b79437ca859ef4e7c35"
    )
    assert NVT_CONSTRAINT_RESIDUAL_PROFILE["predecessor"]["sha256"] == (
        "bb2577c0e227151b8aa95b5c288249823206020558a186eccc8b5ddcbca802de"
    )
    bindings = NVT_CONSTRAINT_RESIDUAL_PROFILE["system_bindings"]
    assert bindings["water_profile_sha256"] == (
        "2b0be83b57085c655092ab0272aea5a91b9c3f90c344fa062d494ad324f0019e"
    )
    assert bindings["constraint_profile_sha256"] == (
        "8dcad0b5005b7a768ce0a88b1804b55ecddb9b3490e2dd59179dfa2393433507"
    )
    assert bindings["nvt_ensemble_profile_sha256"] == (
        "bb2577c0e227151b8aa95b5c288249823206020558a186eccc8b5ddcbca802de"
    )
    assert bindings["constraint_count"] == 6
    assert bindings["expected_degrees_of_freedom"] == 12
    assert NVT_CONSTRAINT_RESIDUAL_PROFILE["sampling"] == NVT_ENSEMBLE_PROFILE[
        "sampling"
    ]
    validation = NVT_CONSTRAINT_RESIDUAL_PROFILE["validation"]
    assert validation["cpu_backends"] == ["cpp_cpu_reference", "rust_cpu"]
    assert validation["same_build_backend_bit_identity_required"] is True
    assert validation["same_seed_repeatability_required"] is True
    assert validation["ordered_residual_rows_required"] is True
    assert validation["maximum_position_constraint_residual_angstrom"] == 1.0e-10
    assert (
        validation[
            "maximum_radial_velocity_constraint_residual_angstrom_per_femtosecond"
        ]
        == 1.0e-10
    )
    assert validation["finite_nonnegative_residuals_required"] is True
    assert validation["population_distribution_rows_retained"] is True
    assert validation["backend_tagged_observation_receipt_required"] is True
    assert validation["performance_measurement_present"] is False
    assert validation["performance_threshold_present"] is False
    assert all(
        value is False
        for value in NVT_CONSTRAINT_RESIDUAL_PROFILE["authority"].values()
    )


def test_native_neighbor_list_profile_matches_the_packaged_runtime_asset() -> None:
    canonical = (
        ROOT / "config/engine_v2_native_periodic_neighbor_list_profile_v1.json"
    ).read_bytes()
    packaged = (
        ROOT
        / "rust/betelgeuze-runtime/assets/engine_v2_native_periodic_neighbor_list_profile_v1.json"
    ).read_bytes()
    assert packaged == canonical
    assert hashlib.sha256(canonical).hexdigest() == (
        "ee2c64b3e40ec1905a97b0c2646e36c59fe30f674adfd019dde016e2637e3628"
    )
    assert NEIGHBOR_LIST_PROFILE["predecessor"]["sha256"] == (
        "8dcad0b5005b7a768ce0a88b1804b55ecddb9b3490e2dd59179dfa2393433507"
    )
    activation = NEIGHBOR_LIST_PROFILE["activation"]
    assert activation["periodic_axes_required"] == [True, True, True]
    assert activation["pair_order"] == "ascending_atom_i_then_ascending_atom_j"
    assert activation["rebuild_policy"] == "every_nonbonded_evaluation"
    assert activation["search_radius_angstrom"] == (
        "max(cutoff_angstrom, minimum_pair_distance_angstrom)"
    )
    assert activation["evaluation_order"] == (
        "minimum_pair_distance validation before cutoff exclusion"
    )
    validation = NEIGHBOR_LIST_PROFILE["validation"]
    assert validation["performance_threshold_present"] is False
    assert validation["atom_permutation_invariance_required"] is True
    assert validation["minimum_distance_validation_outside_cutoff_required"] is True
    assert all(
        value is False for value in NEIGHBOR_LIST_PROFILE["authority"].values()
    )


def test_native_neighbor_cache_profile_matches_the_packaged_runtime_asset() -> None:
    canonical = (
        ROOT / "config/engine_v2_native_periodic_neighbor_list_profile_v2.json"
    ).read_bytes()
    packaged = (
        ROOT
        / "rust/betelgeuze-runtime/assets/engine_v2_native_periodic_neighbor_list_profile_v2.json"
    ).read_bytes()
    assert packaged == canonical
    assert hashlib.sha256(canonical).hexdigest() == (
        "c9e671b925b8f5da48a43dec2abe264e695840b277cc3cf4a84aa7255b59150d"
    )
    assert NEIGHBOR_CACHE_PROFILE["predecessor"]["sha256"] == (
        "409902e5f6776bd58c76f80a572c9cf978f7e2f4938003e5609036bfe91c631f"
    )
    activation = NEIGHBOR_CACHE_PROFILE["activation"]
    assert activation["owner"] == "native_simulation"
    assert activation["skin_angstrom"] == 1.0
    assert "strictly below" in activation["reuse_rule"]
    assert "greater than or equal" in activation["rebuild_rule"]
    assert "neither serialized nor fingerprinted" in activation["checkpoint_policy"]
    validation = NEIGHBOR_CACHE_PROFILE["validation"]
    assert validation["failed_operation_cache_rollback_required"] is True
    assert validation["checkpoint_load_invalidation_required"] is True
    assert validation["performance_measurement_present"] is False
    assert validation["performance_threshold_present"] is False
    assert all(
        value is False for value in NEIGHBOR_CACHE_PROFILE["authority"].values()
    )


def test_native_water_ion_profile_matches_the_packaged_runtime_asset() -> None:
    canonical = (ROOT / "config/engine_v2_native_water_ion_profile_v1.json").read_bytes()
    packaged = (
        ROOT
        / "rust/betelgeuze-runtime/assets/engine_v2_native_water_ion_profile_v1.json"
    ).read_bytes()
    assert packaged == canonical
    assert hashlib.sha256(canonical).hexdigest() == (
        "409902e5f6776bd58c76f80a572c9cf978f7e2f4938003e5609036bfe91c631f"
    )
    assert ION_PROFILE["predecessor"]["sha256"] == (
        "ee2c64b3e40ec1905a97b0c2646e36c59fe30f674adfd019dde016e2637e3628"
    )
    assert ION_PROFILE["parameter_source"]["doi"] == "10.1021/jp8001614"
    assert ION_PROFILE["parameter_source"]["water_model_target"] == "TIP3P"
    assert [
        (row["atomic_number"], row["formal_charge"])
        for row in ION_PROFILE["supported_identities"]
    ] == [(11, 1), (17, -1)]
    assert ION_PROFILE["fixture"]["total_charge_elementary"] == 0.0
    assert ION_PROFILE["fixture"]["static_energy_force_evaluation_only"] is True
    assert all(value is False for value in ION_PROFILE["authority"].values())


def test_native_water_ion_dynamics_profile_matches_packaged_asset() -> None:
    canonical = (
        ROOT / "config/engine_v2_native_water_ion_dynamics_profile_v1.json"
    ).read_bytes()
    packaged = (
        ROOT
        / "rust/betelgeuze-runtime/assets/engine_v2_native_water_ion_dynamics_profile_v1.json"
    ).read_bytes()
    assert packaged == canonical
    assert hashlib.sha256(canonical).hexdigest() == (
        "ad009e5a60c07dccf2d6c50e76d73aa9c8206201ae1bab7c585b63641df098e3"
    )
    assert ION_DYNAMICS_PROFILE["predecessor"]["sha256"] == (
        "409902e5f6776bd58c76f80a572c9cf978f7e2f4938003e5609036bfe91c631f"
    )
    bindings = ION_DYNAMICS_PROFILE["system_bindings"]
    assert bindings["water_ion_profile_sha256"] == (
        "409902e5f6776bd58c76f80a572c9cf978f7e2f4938003e5609036bfe91c631f"
    )
    assert bindings["water_constraint_profile_sha256"] == (
        "8dcad0b5005b7a768ce0a88b1804b55ecddb9b3490e2dd59179dfa2393433507"
    )
    assert bindings["periodic_neighbor_list_profile_sha256"] == (
        "ee2c64b3e40ec1905a97b0c2646e36c59fe30f674adfd019dde016e2637e3628"
    )
    assert bindings["atom_count"] == 8
    assert bindings["constraint_count"] == 6
    assert bindings["expected_degrees_of_freedom"] == 18
    assert bindings["total_charge_elementary"] == 0.0
    assert ION_DYNAMICS_PROFILE["trajectory"] == {
        "integrator": "constrained_velocity_verlet",
        "timestep_femtoseconds": 0.02,
        "primary_step_count": 100,
        "checkpoint_continuation_step_count": 32,
        "initial_ion_velocities_zero": True,
    }
    validation = ION_DYNAMICS_PROFILE["validation"]
    assert validation["cpu_backends"] == ["cpp_cpu_reference", "rust_cpu"]
    assert validation["same_build_backend_bit_identity_required"] is True
    assert validation["ion_position_change_required"] is True
    assert validation["exact_checkpoint_continuation_required"] is True
    assert validation["absolute_step_continuation_required"] is True
    assert validation["performance_measurement_present"] is False
    assert validation["performance_threshold_present"] is False
    assert all(
        value is False for value in ION_DYNAMICS_PROFILE["authority"].values()
    )


def test_native_dynamics_failure_profile_matches_packaged_asset() -> None:
    canonical = (
        ROOT / "config/engine_v2_native_water_box_dynamics_failure_profile_v1.json"
    ).read_bytes()
    packaged = (
        ROOT
        / "rust/betelgeuze-runtime/assets/engine_v2_native_water_box_dynamics_failure_profile_v1.json"
    ).read_bytes()
    assert packaged == canonical
    assert hashlib.sha256(canonical).hexdigest() == (
        "e6fef18952ef813b3f2e96b1614e7b9215f62f032b1abda92b4a2d13d453e6d0"
    )
    assert DYNAMICS_FAILURE_PROFILE["predecessor"]["sha256"] == (
        "ad009e5a60c07dccf2d6c50e76d73aa9c8206201ae1bab7c585b63641df098e3"
    )
    rows = DYNAMICS_FAILURE_PROFILE["ordered_failure_rows"]
    assert [row["case_id"] for row in rows] == [
        "nonfinite_particle_position",
        "linearly_dependent_constraint_jacobian",
        "absolute_step_uint64_overflow",
        "out_of_memory_status_mapping",
        "unsupported_ion_identity",
    ]
    assert [row["expected_typed_failure"] for row in rows] == [
        "invalid_argument",
        "invalid_argument",
        "capacity_overflow",
        "out_of_memory",
        "unsupported_ion_identity",
    ]
    assert [row["failure_attempted"] for row in rows] == [
        True,
        True,
        True,
        False,
        True,
    ]
    assert rows[2]["state_preservation_check"] == (
        "exact_checkpoint_and_snapshot_unchanged"
    )
    assert rows[3]["evidence_kind"] == "status_mapping_only"
    validation = DYNAMICS_FAILURE_PROFILE["validation"]
    assert validation["cpu_backends"] == ["cpp_cpu_reference", "rust_cpu"]
    assert validation["actual_failure_attempt_count"] == 4
    assert validation["mapping_only_row_count"] == 1
    assert validation["all_required_failure_classes_typed"] is True
    assert validation["all_required_failure_classes_runtime_exercised"] is False
    assert validation["oom_allocation_attempted"] is False
    assert validation["capacity_failure_transactionality_required"] is True
    assert validation["hip_device_execution_required"] is False
    assert validation["performance_measurement_present"] is False
    assert validation["performance_threshold_present"] is False
    assert all(
        value is False for value in DYNAMICS_FAILURE_PROFILE["authority"].values()
    )


def test_native_dynamics_failure_boundary_profile_matches_packaged_asset() -> None:
    canonical = (
        ROOT / "config/engine_v2_native_water_box_dynamics_failure_profile_v2.json"
    ).read_bytes()
    packaged = (
        ROOT
        / "rust/betelgeuze-runtime/assets/engine_v2_native_water_box_dynamics_failure_profile_v2.json"
    ).read_bytes()
    assert packaged == canonical
    assert hashlib.sha256(canonical).hexdigest() == (
        "0bf209eb62287f82080a123d7f48e8c63261d7a370283112e1af95ca5e4757be"
    )
    assert DYNAMICS_FAILURE_BOUNDARY_PROFILE["predecessor"]["sha256"] == (
        "e6fef18952ef813b3f2e96b1614e7b9215f62f032b1abda92b4a2d13d453e6d0"
    )
    probe = DYNAMICS_FAILURE_BOUNDARY_PROFILE["oom_boundary_probe"]
    assert probe == {
        "predecessor_case_id": "out_of_memory_status_mapping",
        "production_boundary": "betelgeuze::native::guarded_status",
        "deterministic_exception": "std::bad_alloc",
        "expected_native_status": "BG_STATUS_OUT_OF_MEMORY",
        "expected_native_message": "native allocation failed",
        "safe_rust_mapping": "ErrorCode::OutOfMemory",
        "native_probe_compiled_into_product_library": False,
        "native_probe_calls_production_boundary": True,
        "allocator_attempted": False,
        "allocation_failure_injected": False,
        "hip_device_execution_required": False,
    }
    validation = DYNAMICS_FAILURE_BOUNDARY_PROFILE["validation"]
    assert validation["predecessor_rows_unchanged"] is True
    assert validation["native_bad_alloc_exception_mapping_required"] is True
    assert validation["native_last_error_message_required"] is True
    assert validation["safe_rust_status_mapping_required"] is True
    assert validation["all_required_failure_classes_typed"] is True
    assert validation["all_required_failure_classes_runtime_exercised"] is False
    assert validation["production_oom_resilience_validated"] is False
    assert validation["performance_measurement_present"] is False
    assert validation["performance_threshold_present"] is False
    assert all(
        value is False
        for value in DYNAMICS_FAILURE_BOUNDARY_PROFILE["authority"].values()
    )


def test_native_exception_boundary_matrix_profile_matches_packaged_asset() -> None:
    canonical = (
        ROOT / "config/engine_v2_native_water_box_dynamics_failure_profile_v3.json"
    ).read_bytes()
    packaged = (
        ROOT
        / "rust/betelgeuze-runtime/assets/engine_v2_native_water_box_dynamics_failure_profile_v3.json"
    ).read_bytes()
    assert packaged == canonical
    assert hashlib.sha256(canonical).hexdigest() == (
        "b0f73f136489cbdc17c55be0f82d16b4cfd5dd3218373a0d2c4a310c9884f32c"
    )
    profile = DYNAMICS_EXCEPTION_BOUNDARY_MATRIX_PROFILE
    assert profile["predecessor"]["sha256"] == (
        "0bf209eb62287f82080a123d7f48e8c63261d7a370283112e1af95ca5e4757be"
    )
    boundary = profile["boundary"]
    assert boundary == {
        "source": "native/src/internal.hpp",
        "symbol": "betelgeuze::native::guarded_status",
        "test_translation_unit": "native/tests/guarded_status.cpp",
        "header_defined_production_boundary_source_exercised": True,
        "test_owned_last_error_storage": True,
        "probe_compiled_into_product_library": False,
        "product_library_test_hook_added": False,
        "exception_objects_constructed_before_boundary_where_applicable": True,
        "oom_allocator_attempted": False,
        "allocation_failure_injected": False,
        "hip_device_execution_required": False,
    }
    assert [row["row_id"] for row in profile["ordered_rows"]] == [
        "returned_status_passthrough",
        "length_error",
        "bad_alloc",
        "standard_exception",
        "unknown_exception",
        "success_clears_error",
    ]
    assert profile["safe_rust_mappings"] == {
        "BG_STATUS_CAPACITY_OVERFLOW": "ErrorCode::CapacityOverflow",
        "BG_STATUS_OUT_OF_MEMORY": "ErrorCode::OutOfMemory",
        "BG_STATUS_INTERNAL_ERROR": "ErrorCode::InternalError",
    }
    validation = profile["validation"]
    assert validation["predecessor_rows_unchanged"] is True
    assert validation["ordered_native_boundary_rows_required"] is True
    assert validation["exact_native_last_error_messages_required"] is True
    assert validation["safe_rust_status_mappings_required"] is True
    assert validation["all_boundary_rows_runtime_exercised_in_test_translation_unit"] is True
    assert validation["production_api_exception_injection_performed"] is False
    assert validation["production_oom_resilience_validated"] is False
    assert validation["performance_measurement_present"] is False
    assert validation["performance_threshold_present"] is False
    assert all(value is False for value in profile["authority"].values())


def test_analytic_force_matches_finite_difference() -> None:
    positions, _masses, charges, atom_types, box = WATER.build_box(PROFILE)
    energy, forces = WATER.energy_forces(
        PROFILE, positions, charges, atom_types, box
    )
    assert np.isfinite(energy)
    step = 1.0e-6
    numeric = np.zeros_like(forces)
    for atom in range(len(positions)):
        for axis in range(3):
            plus, minus = positions.copy(), positions.copy()
            plus[atom, axis] += step
            minus[atom, axis] -= step
            energy_plus, _ = WATER.energy_forces(
                PROFILE, plus, charges, atom_types, box
            )
            energy_minus, _ = WATER.energy_forces(
                PROFILE, minus, charges, atom_types, box
            )
            numeric[atom, axis] = -(energy_plus - energy_minus) / (2.0 * step)
    assert np.max(np.abs(numeric - forces)) < 2.0e-5


def test_checkpoint_continuation_is_exact() -> None:
    positions, masses, charges, atom_types, box = WATER.build_box(PROFILE)
    velocities = np.zeros_like(positions)
    velocities[1, 2] = 1.0e-4
    first_positions, first_velocities = positions.copy(), velocities.copy()
    for _ in range(100):
        first_positions, first_velocities, _ = WATER.step_verlet(
            PROFILE,
            first_positions,
            first_velocities,
            masses,
            charges,
            atom_types,
            box,
            0.02,
        )
    resumed_positions, resumed_velocities = positions.copy(), velocities.copy()
    for _ in range(50):
        resumed_positions, resumed_velocities, _ = WATER.step_verlet(
            PROFILE,
            resumed_positions,
            resumed_velocities,
            masses,
            charges,
            atom_types,
            box,
            0.02,
        )
    checkpoint_positions = resumed_positions.copy()
    checkpoint_velocities = resumed_velocities.copy()
    for _ in range(50):
        checkpoint_positions, checkpoint_velocities, _ = WATER.step_verlet(
            PROFILE,
            checkpoint_positions,
            checkpoint_velocities,
            masses,
            charges,
            atom_types,
            box,
            0.02,
        )
    assert np.array_equal(first_positions, checkpoint_positions)
    assert np.array_equal(first_velocities, checkpoint_velocities)


def test_small_timestep_nve_drift_is_bounded() -> None:
    result = WATER.run_nve(PROFILE, 100, 0.02)
    assert abs(result["absolute_drift"]) < 1.0e-5
    assert result["authority"]["production_md_validated"] is False


def test_nonfinite_state_is_rejected() -> None:
    positions, _masses, charges, atom_types, box = WATER.build_box(PROFILE)
    positions[0, 0] = np.nan
    with pytest.raises(WATER.WaterReferenceError, match="nonfinite"):
        WATER.energy_forces(PROFILE, positions, charges, atom_types, box)


def test_unsupported_atom_type_is_rejected() -> None:
    positions, _masses, charges, atom_types, box = WATER.build_box(PROFILE)
    atom_types[0] = 7
    with pytest.raises(WATER.WaterReferenceError, match="unsupported atom type"):
        WATER.energy_forces(PROFILE, positions, charges, atom_types, box)


def test_native_profile_matches_the_frozen_initial_energy_and_force() -> None:
    positions, _masses, charges, atom_types, box = WATER.build_box(NATIVE_PROFILE)
    energy, forces = WATER.energy_forces(
        NATIVE_PROFILE, positions, charges, atom_types, box
    )
    assert energy == pytest.approx(-2.235452238349433, abs=2.0e-14)
    assert forces[0, 0] == pytest.approx(-3.7730687065767325, abs=2.0e-14)
    assert forces[4, 1] == pytest.approx(0.246800271365888, abs=2.0e-14)


def test_native_profile_freezes_the_100_step_nve_observation() -> None:
    result = WATER.run_nve(NATIVE_PROFILE, 100, 0.02)
    repeated = WATER.run_nve(NATIVE_PROFILE, 100, 0.02)
    assert result["initial_total_energy"] == pytest.approx(
        -2.2354281465712305, abs=2.0e-14
    )
    assert result["final_total_energy"] == pytest.approx(
        -2.2354282714680176, abs=2.0e-14
    )
    assert result["absolute_drift"] == pytest.approx(
        -1.2489678713478725e-7, abs=2.0e-14
    )
    assert result["checkpoint_sha256"] == repeated["checkpoint_sha256"]
    assert len(result["checkpoint_sha256"]) == 64
    int(result["checkpoint_sha256"], 16)


def test_native_switch_force_matches_finite_difference() -> None:
    positions, _masses, charges, atom_types, box = WATER.build_box(NATIVE_PROFILE)
    positions[3:] += np.array([2.7, 0.0, 0.0])
    _energy, forces = WATER.energy_forces(
        NATIVE_PROFILE, positions, charges, atom_types, box
    )
    step = 1.0e-6
    plus, minus = positions.copy(), positions.copy()
    plus[3, 0] += step
    minus[3, 0] -= step
    energy_plus, _ = WATER.energy_forces(
        NATIVE_PROFILE, plus, charges, atom_types, box
    )
    energy_minus, _ = WATER.energy_forces(
        NATIVE_PROFILE, minus, charges, atom_types, box
    )
    numeric = -(energy_plus - energy_minus) / (2.0 * step)
    assert forces[3, 0] == pytest.approx(numeric, abs=2.0e-5)


def test_native_cutoff_removes_all_interwater_pairs() -> None:
    positions, _masses, charges, atom_types, box = WATER.build_box(NATIVE_PROFILE)
    positions[3:] += np.array([3.0, 7.0, 7.0])
    energy, forces = WATER.energy_forces(
        NATIVE_PROFILE, positions, charges, atom_types, box
    )
    assert abs(energy) < 1.0e-24
    assert np.max(np.abs(forces)) < 1.0e-12


def test_native_nonbonded_settings_fail_closed() -> None:
    profile = {**NATIVE_PROFILE, "nonbonded": {"cutoff_angstrom": 7.0}}
    positions, _masses, charges, atom_types, box = WATER.build_box(profile)
    with pytest.raises(WATER.WaterReferenceError, match="incomplete"):
        WATER.energy_forces(profile, positions, charges, atom_types, box)
