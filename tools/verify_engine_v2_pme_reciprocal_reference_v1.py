#!/usr/bin/env python3
"""Verify the bounded standalone particle-mesh reciprocal reference v1 evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Callable, NoReturn


ROOT = Path(__file__).resolve().parents[1]
PROFILE_RELATIVE_PATH = Path(
    "config/engine_v2_pme_reciprocal_reference_profile_v1.json"
)
SOURCE_MANIFEST_RELATIVE_PATH = Path(
    "config/engine_v2_pme_reciprocal_reference_profile_v1_sources.json"
)
CRATE_RELATIVE_PATH = Path("rust/reference-pme")
FIXTURE_RELATIVE_PATH = CRATE_RELATIVE_PATH / "fixtures/pme_reciprocal_v1.tsv"

SCHEMA_ID = "betelgeuze.engine_v2_pme_reciprocal_reference_profile/1.0.0"
PROFILE_ID = "engine_v2_four_charge_pme_reciprocal_reference_development_v1"
SOURCE_SCHEMA_ID = (
    "betelgeuze.engine_v2_pme_reciprocal_reference_sources/1.0.0"
)
SOURCE_SCOPE = "standalone_scalar_particle_mesh_reciprocal_v1_inputs"
REFERENCE_SCHEMA_ID = "betelgeuze.reference_particle_mesh_reciprocal/1.0.0"
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
OID_PATTERN = re.compile(r"[0-9a-f]{40}\Z")
BITS_PATTERN = re.compile(r"[0-9a-f]{16}\Z")

PREREQUISITE_PROFILE_RELATIVE_PATH = Path(
    "config/engine_v2_native_direct_ewald_composite_dynamics_profile_v1.json"
)
PREREQUISITE_MANIFEST_RELATIVE_PATH = Path(
    "config/engine_v2_native_direct_ewald_composite_dynamics_profile_v1_sources.json"
)
PREREQUISITE = {
    "merge_commit": "e434295b1711f612e0f7e9fac2d95de92abf19a8",
    "merge_tree": "3546ef29ae708c16c7af1e3be4925d2d7ad1f6b5",
    "profile_path": PREREQUISITE_PROFILE_RELATIVE_PATH.as_posix(),
    "profile_sha256": (
        "42aad2692719d3d0233d9b71e24e6b49fe50a27fbc150d31fb4d9688ae84215f"
    ),
    "pull_request": 438,
    "reviewed_head": "581a17a135d75ddf085c4edd29f3763c2f691fcf",
    "source_manifest_entry_count": 113,
    "source_manifest_path": PREREQUISITE_MANIFEST_RELATIVE_PATH.as_posix(),
    "source_manifest_sha256": (
        "1a7a284467958e7c153edb0afd86cc5ea4ad07b659266ecf59d9da7549a19d15"
    ),
}
PREREQUISITE_CURRENT_PATHS = {
    PREREQUISITE_PROFILE_RELATIVE_PATH: str(PREREQUISITE["profile_sha256"]),
    PREREQUISITE_MANIFEST_RELATIVE_PATH: str(
        PREREQUISITE["source_manifest_sha256"]
    ),
}

SEMANTIC_ORACLE_PROFILE_RELATIVE_PATH = Path(
    "config/engine_v2_direct_ewald_reference_profile_v1.json"
)
SEMANTIC_ORACLE = {
    "cargo_lock_path": "rust/reference-ewald/Cargo.lock",
    "cargo_lock_sha256": (
        "cc64500cc1c97dfda26a8a4c8b8825c5296935f1e63cbaf61676a321364b3d9d"
    ),
    "cargo_manifest_path": "rust/reference-ewald/Cargo.toml",
    "cargo_manifest_sha256": (
        "44422b2daa40776946235a91dcd120a6ea9ee7b0b521fd50293a3cce9fe2880f"
    ),
    "fixture_path": "rust/reference-ewald/fixtures/direct_ewald_v1.tsv",
    "fixture_sha256": (
        "a720c83852c79e401cb8838e9e20b2196985b6e424275949f77291b30b3da338"
    ),
    "merge_commit": "ba008fcaa75891bca45e7b3d33b67449d80fb7d4",
    "merge_tree": "0530a50af2cceeff02341ccb6fab141fd8c43726",
    "profile_path": SEMANTIC_ORACLE_PROFILE_RELATIVE_PATH.as_posix(),
    "profile_sha256": (
        "dd2c7460c2c3e7ea800da51e29bdf54d8933497ade086812d882a65cca4f4e6c"
    ),
    "pull_request": 435,
    "readme_path": "rust/reference-ewald/README.md",
    "readme_sha256": (
        "f03a26ad087ac8d2298de18632e6d62faaf5970619cff7a7c2b7df4d487d2feb"
    ),
    "reference_schema_id": "betelgeuze.reference_direct_ewald/1.0.0",
    "reviewed_head": "b94e4c008db1c8414f5d0f24fa266c85c828d13c",
    "source_path": "rust/reference-ewald/src/lib.rs",
    "source_sha256": (
        "2de8d94d69175053ccaf2a8057a385019fe5c398d7d95d96c84dc3d9bfafc99e"
    ),
}

SEMANTIC_ORACLE_CURRENT_PATHS = {
    Path(str(SEMANTIC_ORACLE["cargo_lock_path"])): str(
        SEMANTIC_ORACLE["cargo_lock_sha256"]
    ),
    Path(str(SEMANTIC_ORACLE["cargo_manifest_path"])): str(
        SEMANTIC_ORACLE["cargo_manifest_sha256"]
    ),
    Path(str(SEMANTIC_ORACLE["fixture_path"])): str(
        SEMANTIC_ORACLE["fixture_sha256"]
    ),
    Path(str(SEMANTIC_ORACLE["profile_path"])): str(
        SEMANTIC_ORACLE["profile_sha256"]
    ),
    Path(str(SEMANTIC_ORACLE["readme_path"])): str(
        SEMANTIC_ORACLE["readme_sha256"]
    ),
    Path(str(SEMANTIC_ORACLE["source_path"])): str(
        SEMANTIC_ORACLE["source_sha256"]
    ),
}

FIXTURE_CONTRACT = {
    "atom_count": 4,
    "charges_elementary": [0.7, -0.4, -0.6, 0.30000000000000004],
    "development_fixture_only": True,
    "net_charge_elementary": 0.0,
    "orthorhombic_lengths_angstrom": [18.0, 20.0, 22.0],
    "periodic_axes": [True, True, True],
    "positions_angstrom": [
        [1.25, 2.5, 3.75],
        [5.1, 3.2, 8.4],
        [10.2, 12.3, 7.7],
        [15.4, 17.1, 19.3],
    ],
}

UNDERFLOW_RESCUE_CONTRACT = {
    "common_force_spectrum": "all_normal_and_rescued_modes_share_one_scaled_spectrum",
    "common_scale_ieee754_bits_hex": "4ff0000000000000",
    "common_scale_is_exact_binary64": True,
    "common_scale_log_expression": (
        "binary64_core_f64_consts_ln_2_times_256_added_before_pinned_libm_exp"
    ),
    "common_scale_power_of_two_exponent": 256,
    "completed_rescued_energy_component_log": (
        "log_energy_prefactor_minus_log_wave_squared_minus_two_log_assignment_"
        "modulus_plus_damping_exponent_plus_two_log_absolute_charge_component_"
        "plus_256_times_binary64_ln_2"
    ),
    "completed_rescued_influence_spectrum_component_log": (
        "minus_log_wave_squared_minus_two_log_assignment_modulus_plus_damping_"
        "exponent_plus_log_absolute_charge_component_plus_256_times_binary64_ln_2"
    ),
    "completed_scaled_value_rounding": (
        "zero_when_log_magnitude_less_than_or_equal_to_"
        "ln_half_minimum_positive_subnormal_else_pinned_libm_exp"
    ),
    "energy_when_no_mode_requires_rescue": (
        "energy_prefactor_times_direct_compensated_regular_reciprocal_sum"
    ),
    "energy_when_any_mode_requires_rescue": (
        "compensated_sum_of_energy_prefactor_times_common_scale_times_regular_"
        "sum_and_scaled_rescued_components_then_divide_once_by_common_scale"
    ),
    "force_grid_multiplier": (
        "two_times_energy_prefactor_times_mesh_point_count_divided_by_common_scale"
    ),
    "force_method_in_scaled_domain": (
        "one_inverse_then_assignment_derivative_sum_then_negative_charge_times_"
        "axis_mesh_dimension_over_cell_length_times_force_grid_multiplier"
    ),
    "inverse_transform_count_after_influence": 1,
    "ln_half_minimum_positive_subnormal": -745.1332191019411,
    "normal_influence_spectrum_component": (
        "direct_influence_times_charge_component_then_exact_common_scale"
    ),
    "rescued_component_sign": "restored_after_log_domain_magnitude",
    "trigger": (
        "nonzero_charge_mode_when_damping_influence_energy_or_a_corresponding_"
        "nonzero_influence_spectrum_component_is_not_normal"
    ),
    "validated_bounds": {
        "accepted_mesh_point_count_power_of_two_maximum": 19,
        "common_scale_margin_over_energy_component_count_bits": 236,
        "conservative_scaled_intermediate_exclusive_power_of_two_bound": 356,
        "derivative_stencil_l1_maximum": 1.5,
        "energy_prefactor_exclusive_power_of_two_bound": 111,
        "force_geometry_multiplier_exclusive_power_of_two_bound": 31,
        "inverse_squared_spline_modulus_exclusive_power_of_two_bound": 10,
        "inverse_wave_squared_exclusive_power_of_two_bound": 55,
        "positive_energy_component_count_exclusive_power_of_two_bound": 20,
        "post_inverse_force_multiplier_exclusive_power_of_two_bound": -94,
        "reciprocal_charge_mode_magnitude_inclusive_power_of_two_bound": 16,
        "scaled_energy_sum_exclusive_power_of_two_bound": 484,
        "scaled_influence_spectrum_exclusive_power_of_two_bound": 337,
        "two_energy_prefactor_mesh_count_exclusive_power_of_two_bound": 131,
    },
}

UNDERFLOW_RESCUE_REGRESSION = {
    "focused_scaled_aggregation": {
        "mixed_regular_and_rescued_lanes_each_round_separately_to_zero": True,
        "mixed_regular_and_rescued_lanes_restore_ieee754_bits_hex": (
            "0000000000000001"
        ),
        "rescue_only_individual_component_count": 8,
        "rescue_only_individual_unscaled_ieee754_bits_hex": "0000000000000000",
        "rescue_only_restored_sum_ieee754_bits_hex": "0000000000000001",
    },
    "large_cell_normal_output": {
        "alpha_per_angstrom": 1.15e-10,
        "central_finite_difference_step_angstrom": 1000.0,
        "charges_elementary": [16.0, -16.0],
        "dielectric": 1e-12,
        "expected_particle_1_x_force_kcal_per_mol_angstrom": -1.6999574664e-295,
        "expected_reciprocal_space_kcal_per_mol": 7.4746417761e-287,
        "expected_values_are_normal_and_nonzero": True,
        "mesh_dimensions": [4, 4, 4],
        "orthorhombic_lengths_angstrom": [1e9, 1e-6, 1e-6],
        "positions_angstrom": [[0.0, 0.0, 0.0], [4e8, 0.0, 0.0]],
        "raw_first_wave_damping_ieee754_bits_hex": "0000000000000000",
        "relative_tolerance_without_unit_floor": 1e-8,
    },
    "small_cell_subnormal_output": {
        "aggregate_energy_dielectric": 2.5e10,
        "aggregate_energy_ieee754_bits_hex": "0000000000000001",
        "alpha_per_angstrom": 1.15e5,
        "charges_elementary": [16.0, -16.0],
        "force_only_dielectric": 1e12,
        "force_only_energy_ieee754_bits_hex": "0000000000000000",
        "force_only_expected_particle_1_x_kcal_per_mol_angstrom": (
            -1.6999574664e-319
        ),
        "force_only_expected_particle_1_x_is_negative_subnormal": True,
        "force_only_relative_tolerance_without_unit_floor": 1e-3,
        "mesh_dimensions": [4, 4, 4],
        "orthorhombic_lengths_angstrom": [1e-6, 1e-6, 1e-6],
        "positions_angstrom": [[0.0, 0.0, 0.0], [4e-7, 0.0, 0.0]],
        "raw_first_wave_damping_ieee754_bits_hex": "0000000000000000",
    },
    "synthetic_regressions_only": True,
}

NUMERICAL_CONTRACT = {
    "alpha_per_angstrom": 0.31,
    "assignment": "fixed_order_4_cardinal_b_spline",
    "cardinal_b_spline_order": 4,
    "central_finite_difference_step_angstrom": 1e-5,
    "coordinate_reduction": "bounded_per_axis_euclidean_remainder",
    "coulomb_kcal_angstrom_per_mol_e2": 332.063713299,
    "dielectric": 1.0,
    "direct_ewald_reference_reciprocal_max_indices": [9, 9, 9],
    "even_grid_nyquist_representative": "negative_half_dimension",
    "fft_axis_order": "z_then_y_then_x_for_z_fast_storage",
    "fft_forward_sign": "negative",
    "fft_forward_normalization": "unnormalized",
    "fft_inverse_sign": "positive",
    "fft_inverse_normalization": (
        "per_axis_one_over_axis_length_for_net_one_over_mesh_point_count"
    ),
    "force_method": "analytic_assignment_weight_derivative_of_mesh_energy",
    "mesh_dimensions": [16, 16, 16],
    "mesh_refinement_sequence": [[8, 8, 8], [16, 16, 16], [32, 32, 32]],
    "mesh_origin": "orthorhombic_cell_origin",
    "maximum_evaluation_work_units": 16000000,
    "evaluation_work_unit_equation": (
        "mesh_point_count_times_one_plus_sum_log2_mesh_dimensions_plus_particle_"
        "count_times_cardinal_b_spline_order_cubed_times_four"
    ),
    "evaluation_work_unit_components": {
        "fft_butterflies_forward_and_inverse": (
            "mesh_point_count_times_sum_log2_mesh_dimensions"
        ),
        "force_gather_support_visits_per_particle": 192,
        "influence_visits": "mesh_point_count",
        "spread_support_visits_per_particle": 64,
    },
    "neutralizing_background": False,
    "reciprocal_zero_mode": "omitted",
    "signed_frequency_mapping": (
        "index_when_index_less_than_half_dimension_else_index_minus_dimension"
    ),
    "spline_deconvolution": "discrete_cardinal_b_spline_modulus_squared",
    "underflow_rescue": dict(UNDERFLOW_RESCUE_CONTRACT),
    "underflow_rescue_regression": dict(UNDERFLOW_RESCUE_REGRESSION),
}

NUMERIC_ENVELOPE = {
    "alpha_per_angstrom": {"maximum": 1e6, "minimum": 1e-12},
    "cell_length_angstrom": {"maximum": 1e9, "minimum": 1e-6},
    "dielectric": {"maximum": 1e12, "minimum": 1e-12},
    "maximum_absolute_coordinate_angstrom": 1e12,
    "maximum_mesh_dimension": 128,
    "maximum_mesh_point_count": 1048576,
    "maximum_public_complex_mesh_buffer_bytes": 8388608,
    "maximum_public_complex_mesh_buffer_count": 1,
    "maximum_particle_count": 4096,
    "maximum_reachable_mesh_point_count_under_work_cap": 524288,
    "maximum_evaluation_work_units": 16000000,
    "mesh_point_cap_regression_dimensions": [128, 128, 128],
    "work_cap_regression_dimensions": [64, 128, 128],
    "work_cap_regression_mesh_point_count": 1048576,
    "work_cap_near_boundary_admitted_dimensions": [32, 128, 128],
    "work_cap_near_boundary_admitted_mesh_point_count": 524288,
    "minimum_mesh_dimension": 4,
    "mesh_dimensions_must_be_powers_of_two": True,
    "nonzero_absolute_charge_elementary": {"maximum": 16.0, "minimum": 1e-12},
}

ACCURACY_ACCEPTANCE_CONTRACT = {
    "arbitrary_translation_absolute_energy_difference_kcal_per_mol": {
        "exclusive_maximum": 0.02,
        "exclusive_minimum": 1e-6,
    },
    "central_finite_difference_scaled_absolute_tolerance": 2e-7,
    "fft_direct_dft_evaluation_energy_scaled_absolute_tolerance": 2e-12,
    "fft_direct_dft_evaluation_force_scaled_absolute_tolerance": 7e-12,
    "fft_direct_dft_transform_forward_scaled_absolute_tolerance": 3e-12,
    "fft_direct_dft_transform_inverse_scaled_absolute_tolerance": 5e-12,
    "integer_grid_translation_scaled_absolute_tolerance": 2e-13,
    "maximum_absolute_net_force_component_kcal_per_mol_angstrom": 0.05,
    "maximum_arbitrary_translation_force_difference_kcal_per_mol_angstrom": 0.05,
    "mesh_32_absolute_energy_difference_from_direct_ewald_kcal_per_mol": 0.002,
    "mesh_32_maximum_force_difference_from_direct_ewald_kcal_per_mol_angstrom": 0.003,
    "mesh_energy_and_force_errors_strictly_decrease": True,
}

ACCURACY_OBSERVATION = {
    "arbitrary_translation_absolute_energy_difference_kcal_per_mol": (
        8.671552197633048e-3
    ),
    "debug_release_observation_line_count": 31,
    "debug_release_observation_sha256": (
        "899845a391e23da253a5f0e2bdb5a78794ec7beb4dabee1f04726d6af1492144"
    ),
    "direct_ewald_bound_9_reciprocal_space_kcal_per_mol": 40.26672199941431,
    "fft_direct_dft_checked_in_tests": True,
    "integer_grid_translation_absolute_energy_difference_kcal_per_mol": 0.0,
    "maximum_absolute_net_force_component_kcal_per_mol_angstrom": (
        3.840533986220912e-2
    ),
    "maximum_arbitrary_translation_force_difference_kcal_per_mol_angstrom": (
        2.3738262606489924e-2
    ),
    "maximum_central_finite_difference_force_error_kcal_per_mol_angstrom": (
        5.949347681166728e-10
    ),
    "maximum_integer_grid_translation_force_difference_kcal_per_mol_angstrom": (
        1.7763568394002505e-15
    ),
    "mesh_refinement": [
        {
            "absolute_energy_difference_from_direct_ewald_kcal_per_mol": (
                9.181130620454852e-1
            ),
            "maximum_force_difference_from_direct_ewald_reciprocal_finite_difference_kcal_per_mol_angstrom": (
                3.1015104327656573e-1
            ),
            "mesh_dimensions": [8, 8, 8],
        },
        {
            "absolute_energy_difference_from_direct_ewald_kcal_per_mol": (
                3.310630558823391e-2
            ),
            "maximum_force_difference_from_direct_ewald_reciprocal_finite_difference_kcal_per_mol_angstrom": (
                3.6006726728953886e-2
            ),
            "mesh_dimensions": [16, 16, 16],
        },
        {
            "absolute_energy_difference_from_direct_ewald_kcal_per_mol": (
                1.9507390685902237e-3
            ),
            "maximum_force_difference_from_direct_ewald_reciprocal_finite_difference_kcal_per_mol_angstrom": (
                2.645625838342769e-3
            ),
            "mesh_dimensions": [32, 32, 32],
        },
    ],
}

IMPLEMENTATION_CONTRACT_BASE = {
    "actual_forward_inverse_fft": True,
    "analytic_reciprocal_forces": True,
    "arithmetic": "scalar_binary64_with_pinned_libm_transcendentals",
    "cardinal_b_spline_order": 4,
    "crate": CRATE_RELATIVE_PATH.as_posix(),
    "direct_discrete_fourier_oracle_is_test_only": True,
    "direct_ewald_semantic_oracle_is_dev_only": True,
    "external_fft_dependency": False,
    "external_md_engine_dependency": False,
    "fixed64_cpu_v7_qualification_invoked": False,
    "full_pme_implemented": False,
    "hip_device_execution_invoked": False,
    "molecular_execution_invoked": False,
    "normal_and_rescued_force_modes_share_one_scaled_spectrum": True,
    "normal_energy_path_is_direct_when_no_mode_requires_rescue": True,
    "native_abi_added": False,
    "native_runtime_integrated": False,
    "pair_correction_implemented": False,
    "particle_mesh_reciprocal_implemented": True,
    "performance_evidence_collected": False,
    "post_influence_inverse_transform_count": 1,
    "production_complex_mesh_buffer_byte_upper_bound": 8388608,
    "production_complex_mesh_buffer_count_upper_bound": 1,
    "real_space_implemented": False,
    "reference_schema_id": REFERENCE_SCHEMA_ID,
    "self_energy_implemented": False,
    "source_manifest_path": SOURCE_MANIFEST_RELATIVE_PATH.as_posix(),
    "standalone_workspace": True,
    "transcendental_implementation": "libm_0.2.16_exact_dependency_and_lockfile",
    "underflow_rescue_common_scale_power_of_two_exponent": 256,
    "underflow_rescue_combines_regular_and_rescued_energy_before_downscale": True,
    "underflow_rescue_rounds_scaled_completed_values_once": True,
    "underflow_rescue_uses_completed_mode_log_domain_scaling": True,
    "work_cap_checked_before_assignment_or_grid_allocation": True,
}

VALIDATION_CONTRACT = {
    "all_12_forces_match_central_finite_differences": True,
    "arbitrary_translation_is_bounded_accuracy_observation_not_exact_identity": True,
    "assignment_derivative_sum_zero": True,
    "assignment_partition_of_unity": True,
    "atom_permutation_property": True,
    "charge_inversion_property": True,
    "debug_release_frozen_observation_identity": True,
    "deposited_grid_charge_conservation": True,
    "direct_ewald_bound_9_reciprocal_accuracy_observed": True,
    "fft_conjugate_symmetry": True,
    "fft_round_trip": True,
    "fft_against_independent_full_3d_direct_dft_parity": True,
    "frozen_energy_and_force_bits": True,
    "integer_grid_cell_translation_property": True,
    "integer_periodic_image_property": True,
    "mesh_energy_equals_half_grid_charge_potential_sum": True,
    "mesh_refinement_sequence_observed_without_performance_claim": True,
    "mesh_128_cubed_point_capacity_rejection": True,
    "mesh_64_128_128_work_capacity_rejection": True,
    "mixed_regular_and_rescued_energy_lanes_round_once_to_minimum_subnormal": True,
    "net_force_is_bounded_accuracy_observation_not_exact_identity": True,
    "power_of_two_scaled_common_spectrum_preserves_subnormal_force": True,
    "raw_zero_damping_rescued_to_normal_nonzero_energy_and_force": True,
    "rescue_only_scaled_energy_components_round_once_to_minimum_subnormal": True,
    "small_cell_force_only_energy_rounds_to_zero": True,
    "small_cell_force_only_particle_1_x_is_negative_subnormal": True,
    "small_cell_scaled_energy_aggregation_has_minimum_subnormal_bits": True,
    "same_input_bitwise_repeat": True,
    "signed_frequency_and_nyquist_mapping": True,
    "typed_malformed_input_failures": True,
    "underflow_rescue_fft_matches_independent_full_3d_direct_dft": True,
    "underflow_rescue_force_matches_energy_central_finite_difference": True,
    "underflow_rescue_half_grid_charge_potential_identity": True,
    "work_cap_typed_capacity_rejection_before_allocation": True,
    "zero_mode_omitted_without_background_correction": True,
}

AUTHORITY_CONTRACT = {
    "acceleration_claim_authorized": False,
    "d1_d2_execution_authorized": False,
    "fresh_holdout_execution_authorized": False,
    "hip_device_execution_authorized": False,
    "historical_molecular_ab_execution_authorized": False,
    "molecular_execution_authorized": False,
    "performance_claim_authorized": False,
    "product_authority": False,
    "public_benchmark_authorized": False,
    "qualification_rerun_authorized": False,
    "reservation_authorized": False,
    "root_supervisor_install_authorized": False,
    "scientific_claim_authorized": False,
    "stage0_admission_authorized": False,
    "test_double_production_authority": False,
}

OPERATIONAL_BLOCKERS = (
    "external_reservation_endpoint_not_configured",
    "external_reservation_provider_not_operational",
    "external_reservation_trust_anchor_not_configured",
    "historical_execution_operational_authority_false",
)
OPERATIONAL_BOUNDARY = {
    "blockers": list(OPERATIONAL_BLOCKERS),
    "unresolved_operational_decisions": 32,
}

REQUIRED_CRATE_PATHS = (
    CRATE_RELATIVE_PATH / "Cargo.lock",
    CRATE_RELATIVE_PATH / "Cargo.toml",
    CRATE_RELATIVE_PATH / "README.md",
    CRATE_RELATIVE_PATH / "examples/profile_observation.rs",
    FIXTURE_RELATIVE_PATH,
    CRATE_RELATIVE_PATH / "src/direct_dft.rs",
    CRATE_RELATIVE_PATH / "src/fft.rs",
    CRATE_RELATIVE_PATH / "src/lib.rs",
    CRATE_RELATIVE_PATH / "tests/frozen_fixture.rs",
    CRATE_RELATIVE_PATH / "tests/properties.rs",
)
REQUIRED_SOURCE_PATHS = (
    *REQUIRED_CRATE_PATHS,
    Path("LICENSE"),
    Path("rust/Cargo.toml"),
    *PREREQUISITE_CURRENT_PATHS,
    *SEMANTIC_ORACLE_CURRENT_PATHS,
    Path("tools/__init__.py"),
    Path("tools/verify_engine_v2_pme_reciprocal_reference_v1.py"),
)
EXCLUDED_SOURCE_PATHS = frozenset(
    {
        PROFILE_RELATIVE_PATH,
        SOURCE_MANIFEST_RELATIVE_PATH,
        Path("tests/unit/test_engine_v2_pme_reciprocal_reference_v1.py"),
        Path("docs/engine_v2_pme_reciprocal_reference_v1.md"),
        Path(".github/workflows/ci-engine-v2-pme-reciprocal-reference.yml"),
    }
)

FIXTURE_VALUE_IDS = (
    "reciprocal_space_kcal_per_mol",
    *(f"force_{atom}_{axis}" for atom in range(4) for axis in "xyz"),
)


class PmeReciprocalReferenceV1Error(ValueError):
    """The standalone particle-mesh reciprocal v1 evidence failed closed."""


def _fail(message: str) -> NoReturn:
    raise PmeReciprocalReferenceV1Error(message)


def _duplicate_rejector(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            _fail(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> NoReturn:
    _fail(f"non-finite JSON constant is forbidden: {value}")


def canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("ascii")


def _load_ascii_object(raw: bytes, *, label: str) -> dict[str, object]:
    try:
        value = json.loads(
            raw.decode("ascii"),
            object_pairs_hook=_duplicate_rejector,
            parse_constant=_reject_constant,
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise PmeReciprocalReferenceV1Error(
            f"{label} is not valid finite ASCII JSON"
        ) from exc
    if type(value) is not dict:
        _fail(f"{label} is not a JSON object")
    return value


def _load_canonical_object(raw: bytes, *, label: str) -> dict[str, object]:
    value = _load_ascii_object(raw, label=label)
    if raw != canonical_bytes(value):
        _fail(f"{label} canonical serialization changed")
    return value


def _exact_keys(
    value: object, expected: set[str], *, label: str
) -> dict[str, object]:
    if type(value) is not dict or set(value) != expected:
        _fail(f"{label} field set changed")
    return value


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _require_regular_file(root: Path, relative: Path) -> Path:
    path = root / relative
    if path.is_symlink() or not path.is_file():
        _fail(f"source path is not a regular non-symlink file: {relative}")
    return path


def discover_source_paths(root: Path) -> tuple[Path, ...]:
    paths = set(REQUIRED_SOURCE_PATHS)
    crate = root / CRATE_RELATIVE_PATH
    if crate.is_symlink() or not crate.is_dir():
        _fail("standalone reference crate is not a regular non-symlink directory")
    for path in crate.rglob("*"):
        relative_inside_crate = path.relative_to(crate)
        if relative_inside_crate.parts and relative_inside_crate.parts[0] == "target":
            continue
        if path.is_symlink():
            _fail(
                "standalone reference crate source must not be a symlink: "
                f"{path.relative_to(root)}"
            )
        if path.is_file():
            paths.add(path.relative_to(root))
    if paths & EXCLUDED_SOURCE_PATHS:
        _fail("generated or consumer evidence entered the acyclic source closure")
    for relative in paths:
        if relative.is_absolute() or ".." in relative.parts:
            _fail(f"source path is not normalized: {relative}")
        _require_regular_file(root, relative)
    return tuple(sorted(paths, key=lambda value: value.as_posix()))


def build_source_manifest(root: Path) -> dict[str, object]:
    rows = []
    for relative in discover_source_paths(root):
        raw = _require_regular_file(root, relative).read_bytes()
        rows.append(
            {
                "byte_count": len(raw),
                "path": relative.as_posix(),
                "sha256": _sha256(raw),
            }
        )
    return {
        "files": rows,
        "schema_id": SOURCE_SCHEMA_ID,
        "scope": SOURCE_SCOPE,
    }


def require_source_manifest(
    root: Path, raw: bytes
) -> tuple[dict[str, object], dict[str, bytes]]:
    manifest = _load_canonical_object(raw, label="source manifest")
    _exact_keys(manifest, {"files", "schema_id", "scope"}, label="manifest")
    if manifest["schema_id"] != SOURCE_SCHEMA_ID:
        _fail("source manifest schema changed")
    if manifest["scope"] != SOURCE_SCOPE:
        _fail("source manifest scope changed")
    rows = manifest["files"]
    if type(rows) is not list or not rows:
        _fail("source manifest files must be a non-empty list")
    expected_paths = [path.as_posix() for path in discover_source_paths(root)]
    observed_paths: list[str] = []
    for index, row in enumerate(rows):
        entry = _exact_keys(
            row,
            {"byte_count", "path", "sha256"},
            label=f"source row {index}",
        )
        path_value = entry["path"]
        byte_count = entry["byte_count"]
        digest = entry["sha256"]
        if type(path_value) is not str or not path_value:
            _fail(f"source row {index} path is invalid")
        relative = Path(path_value)
        if (
            relative.is_absolute()
            or relative.as_posix() != path_value
            or ".." in relative.parts
        ):
            _fail(f"source row {index} path is not normalized")
        if type(byte_count) is not int or byte_count < 0:
            _fail(f"source row {index} byte_count is invalid")
        if type(digest) is not str or SHA256_PATTERN.fullmatch(digest) is None:
            _fail(f"source row {index} sha256 is invalid")
        observed_paths.append(path_value)
    if observed_paths != sorted(set(observed_paths)):
        _fail("source manifest paths must be sorted and unique")
    if observed_paths != expected_paths:
        _fail("source manifest path closure changed; run --refresh explicitly")
    sources: dict[str, bytes] = {}
    for row in rows:
        assert isinstance(row, dict)
        path_value = row["path"]
        byte_count = row["byte_count"]
        digest = row["sha256"]
        assert isinstance(path_value, str)
        assert isinstance(byte_count, int)
        assert isinstance(digest, str)
        source_raw = _require_regular_file(root, Path(path_value)).read_bytes()
        if len(source_raw) != byte_count or _sha256(source_raw) != digest:
            _fail(f"source bytes drifted: {path_value}")
        sources[path_value] = source_raw
    return manifest, sources


def _git(
    root: Path,
    arguments: list[str],
    *,
    expected_statuses: tuple[int, ...] = (0,),
) -> tuple[int, bytes]:
    environment = {
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_OPTIONAL_LOCKS": "0",
        "LC_ALL": "C",
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
    }
    try:
        completed = subprocess.run(
            ["/usr/bin/git", "--no-replace-objects", *arguments],
            cwd=root,
            check=False,
            capture_output=True,
            env=environment,
        )
    except OSError as exc:
        raise PmeReciprocalReferenceV1Error(
            "historical Git object inspection failed"
        ) from exc
    if completed.returncode not in expected_statuses or completed.stderr:
        _fail("historical Git object is unavailable or ambiguous")
    return completed.returncode, completed.stdout


def _require_commit_pair(
    root: Path, metadata: dict[str, object], *, label: str
) -> None:
    merge = str(metadata["merge_commit"])
    reviewed = str(metadata["reviewed_head"])
    expected_tree = str(metadata["merge_tree"])
    if (
        OID_PATTERN.fullmatch(merge) is None
        or OID_PATTERN.fullmatch(reviewed) is None
        or OID_PATTERN.fullmatch(expected_tree) is None
    ):
        _fail(f"{label} historical object identity is invalid")
    _, resolved_merge = _git(root, ["rev-parse", "--verify", f"{merge}^{{commit}}"])
    _, resolved_reviewed = _git(
        root, ["rev-parse", "--verify", f"{reviewed}^{{commit}}"]
    )
    if resolved_merge != f"{merge}\n".encode("ascii"):
        _fail(f"{label} merge object changed")
    if resolved_reviewed != f"{reviewed}\n".encode("ascii"):
        _fail(f"{label} reviewed-head object changed")
    _, merge_tree = _git(root, ["show", "-s", "--format=%T", merge])
    _, reviewed_tree = _git(root, ["show", "-s", "--format=%T", reviewed])
    expected = f"{expected_tree}\n".encode("ascii")
    if merge_tree != expected or reviewed_tree != expected:
        _fail(f"{label} reviewed and merged trees are not the frozen exact tree")
    _git(root, ["merge-base", "--is-ancestor", merge, "HEAD"])


def _historical_blob(root: Path, commit: str, relative: Path) -> bytes:
    _, raw = _git(
        root,
        ["cat-file", "blob", f"{commit}:{relative.as_posix()}"],
    )
    return raw


def require_historical_dependencies(root: Path) -> dict[str, object]:
    _require_commit_pair(root, PREREQUISITE, label="PR #438 prerequisite")
    prerequisite_merge = str(PREREQUISITE["merge_commit"])
    prerequisite_profile_raw = _historical_blob(
        root, prerequisite_merge, PREREQUISITE_PROFILE_RELATIVE_PATH
    )
    prerequisite_manifest_raw = _historical_blob(
        root, prerequisite_merge, PREREQUISITE_MANIFEST_RELATIVE_PATH
    )
    if _sha256(prerequisite_profile_raw) != PREREQUISITE["profile_sha256"]:
        _fail("historical PR #438 prerequisite profile bytes changed")
    if _sha256(prerequisite_manifest_raw) != PREREQUISITE["source_manifest_sha256"]:
        _fail("historical PR #438 prerequisite manifest bytes changed")
    prerequisite_profile = _load_canonical_object(
        prerequisite_profile_raw, label="historical PR #438 prerequisite profile"
    )
    prerequisite_manifest = _load_canonical_object(
        prerequisite_manifest_raw, label="historical PR #438 prerequisite manifest"
    )
    prerequisite_rows = prerequisite_manifest.get("files")
    if (
        type(prerequisite_rows) is not list
        or len(prerequisite_rows) != PREREQUISITE["source_manifest_entry_count"]
    ):
        _fail("historical PR #438 prerequisite manifest count changed")
    prerequisite_paths = [
        row.get("path") for row in prerequisite_rows if type(row) is dict
    ]
    if (
        len(prerequisite_paths) != len(prerequisite_rows)
        or prerequisite_paths != sorted(set(prerequisite_paths))
    ):
        _fail("historical PR #438 prerequisite manifest paths changed")
    prerequisite_implementation = prerequisite_profile.get("implementation")
    if (
        type(prerequisite_implementation) is not dict
        or prerequisite_implementation.get("source_manifest_entry_count")
        != len(prerequisite_rows)
        or prerequisite_implementation.get("source_manifest_sha256")
        != PREREQUISITE["source_manifest_sha256"]
    ):
        _fail("historical PR #438 profile-to-manifest binding changed")
    for relative, expected_digest in PREREQUISITE_CURRENT_PATHS.items():
        historical_raw = _historical_blob(root, prerequisite_merge, relative)
        if _sha256(historical_raw) != expected_digest:
            _fail(f"historical prerequisite bytes changed: {relative}")
        current_raw = _require_regular_file(root, relative).read_bytes()
        if current_raw != historical_raw:
            _fail(f"current prerequisite bytes drifted: {relative}")

    _require_commit_pair(root, SEMANTIC_ORACLE, label="PR #435 semantic oracle")
    oracle_merge = str(SEMANTIC_ORACLE["merge_commit"])
    oracle_profile_raw = _historical_blob(
        root, oracle_merge, SEMANTIC_ORACLE_PROFILE_RELATIVE_PATH
    )
    if _sha256(oracle_profile_raw) != SEMANTIC_ORACLE["profile_sha256"]:
        _fail("historical PR #435 semantic-oracle profile bytes changed")
    oracle_profile = _load_ascii_object(
        oracle_profile_raw, label="historical PR #435 semantic-oracle profile"
    )
    if oracle_profile.get("schema_id") != (
        "betelgeuze.engine_v2_direct_ewald_reference_profile/1.0.0"
    ):
        _fail("historical PR #435 semantic-oracle profile schema changed")
    oracle_implementation = oracle_profile.get("implementation")
    if type(oracle_implementation) is not dict:
        _fail("historical PR #435 semantic-oracle implementation is invalid")
    for profile_key, metadata_key in (
        ("source_sha256", "source_sha256"),
        ("frozen_fixture_sha256", "fixture_sha256"),
        ("cargo_lock_sha256", "cargo_lock_sha256"),
    ):
        if oracle_implementation.get(profile_key) != SEMANTIC_ORACLE[metadata_key]:
            _fail("historical PR #435 semantic-oracle artifact binding changed")

    for relative, expected_digest in SEMANTIC_ORACLE_CURRENT_PATHS.items():
        historical_raw = _historical_blob(root, oracle_merge, relative)
        if _sha256(historical_raw) != expected_digest:
            _fail(f"historical semantic-oracle bytes changed: {relative}")
        current_raw = _require_regular_file(root, relative).read_bytes()
        if current_raw != historical_raw:
            _fail(f"current semantic-oracle bytes drifted: {relative}")

    return {
        "prerequisite_merge_commit": prerequisite_merge,
        "prerequisite_current_file_count": len(PREREQUISITE_CURRENT_PATHS),
        "prerequisite_source_manifest_entry_count": len(prerequisite_rows),
        "semantic_oracle_file_count": len(SEMANTIC_ORACLE_CURRENT_PATHS),
        "semantic_oracle_merge_commit": oracle_merge,
    }


def _parse_fixture(raw: bytes) -> dict[str, str]:
    try:
        text = raw.decode("ascii")
    except UnicodeError as exc:
        raise PmeReciprocalReferenceV1Error("fixture is not ASCII") from exc
    if not text.endswith("\n"):
        _fail("fixture must end with one newline")
    lines = text.splitlines()
    if not lines or lines[0] != f"# schema_id={REFERENCE_SCHEMA_ID}":
        _fail("fixture schema changed")
    rows: list[tuple[str, str]] = []
    header_seen = False
    for line in lines[1:]:
        if not line or line.startswith("#"):
            continue
        if not header_seen:
            if line != "value_id\tbits_hex":
                _fail("fixture header changed")
            header_seen = True
            continue
        if line.count("\t") != 1:
            _fail("fixture row is not exactly two tab-separated fields")
        value_id, bits = line.split("\t")
        if BITS_PATTERN.fullmatch(bits) is None:
            _fail(f"fixture bits are invalid for {value_id}")
        rows.append((value_id, bits))
    if not header_seen or tuple(row[0] for row in rows) != FIXTURE_VALUE_IDS:
        _fail("fixture must contain the exact ordered 13-value closure")
    if len({row[0] for row in rows}) != len(rows):
        _fail("fixture value identifiers must be unique")
    return dict(rows)


def _require_source_contract(sources: dict[str, bytes]) -> dict[str, str]:
    def text(relative: Path) -> str:
        try:
            return sources[relative.as_posix()].decode("utf-8")
        except (KeyError, UnicodeError) as exc:
            raise PmeReciprocalReferenceV1Error(
                f"required UTF-8 source is missing or invalid: {relative}"
            ) from exc

    cargo = text(CRATE_RELATIVE_PATH / "Cargo.toml")
    for marker in (
        'name = "betelgeuze-reference-pme-reciprocal"',
        'license-file = "../../LICENSE"',
        "[workspace]",
        'version = "=0.2.16"',
        "betelgeuze-reference-ewald",
        'path = "../reference-ewald"',
        'unsafe_code = "forbid"',
    ):
        if marker not in cargo:
            _fail(f"standalone Cargo contract marker is missing: {marker}")
    for forbidden in (
        "betelgeuze-runtime",
        "betelgeuze-sys",
        "cpu-kernel",
        "rustfft",
        "hip-runtime",
    ):
        if forbidden in cargo.lower():
            _fail(f"forbidden standalone dependency appeared: {forbidden}")
    root_cargo = text(Path("rust/Cargo.toml"))
    if "reference-pme" in root_cargo or "pme-reciprocal" in root_cargo:
        _fail("standalone reference entered the production Rust workspace")

    lock = text(CRATE_RELATIVE_PATH / "Cargo.lock")
    for marker in (
        'name = "betelgeuze-reference-ewald"',
        'name = "betelgeuze-reference-pme-reciprocal"',
        'name = "libm"',
        'version = "0.2.16"',
    ):
        if marker not in lock:
            _fail(f"standalone Cargo.lock marker is missing: {marker}")
    for forbidden in ("rustfft", "hip", "betelgeuze-runtime", "betelgeuze-sys"):
        if forbidden in lock.lower():
            _fail(f"forbidden package appeared in standalone Cargo.lock: {forbidden}")

    library = text(CRATE_RELATIVE_PATH / "src/lib.rs")
    if "#[cfg(test)]\nmod direct_dft;" not in library:
        _fail("independent direct DFT must remain test-only")
    for marker in (
        "const MAX_EVALUATION_WORK_UNITS: usize = 16_000_000;",
        "const LN_HALF_MIN_POSITIVE_SUBNORMAL: f64 = -745.133_219_101_941_1;",
        "const LOG_RESCUE_SCALE: f64 = core::f64::consts::LN_2 * 256.0;",
        "const RESCUE_SCALE: f64 = f64::from_bits(0x4ff0_0000_0000_0000);",
        "fn mode_requires_log_rescue(",
        "fn completed_squared_component(",
        "fn completed_scaled_component(",
        "fn completed_positive_from_log(",
        "fn complete_energy(",
        "if log_magnitude <= LN_HALF_MIN_POSITIVE_SUBNORMAL",
        "let scaled_grid_multiplier = reciprocal.grid_derivative_scale / RESCUE_SCALE;",
        "let mut rescued_energy_scaled = CompensatedSum::default();",
        "energy_log_scale + LOG_RESCUE_SCALE",
        "-denominator_log + damping_exponent + LOG_RESCUE_SCALE",
        "regular_grid_mode.scale(RESCUE_SCALE)",
        "combined_scaled.add((energy_prefactor * RESCUE_SCALE) * regular_reciprocal_sum);",
        "combined_scaled.total() / RESCUE_SCALE",
        "stages.checked_add(1)",
        "mesh_point_count.checked_mul(stages_and_influence)",
    ):
        if marker not in library:
            _fail(f"underflow/work-cap library marker is missing: {marker}")

    properties = text(CRATE_RELATIVE_PATH / "tests/properties.rs")
    for marker in (
        "log_domain_rescues_representable_energy_and_force_after_raw_damping_underflow",
        "assert_eq!(raw_damping.to_bits(), 0);",
        "7.474_641_776_1e-287",
        "-1.699_957_466_4e-295",
        "assert_relative_without_unit_floor(force, finite_difference_force, 1.0e-8);",
        "power_of_two_scaled_rescue_preserves_force_when_energy_and_phihat_round_to_zero",
        "-1.699_957_466_4e-319",
        "aggregate_energy.settings.dielectric = 2.5e10;",
        "assert_eq!(aggregated.reciprocal_space_kcal_per_mol.to_bits(), 1);",
    ):
        if marker not in properties:
            _fail(f"underflow regression marker is missing: {marker}")
    for marker in (
        "let rescued_direct = compute_with_transform(&rescue, direct_dft::direct_dft_3d)",
        "let identity = half_grid_charge_potential_sum(&rescued);",
        "scaled_rescue_accumulation_preserves_a_representable_positive_sum",
        "regular_and_rescue_energy_lanes_round_only_after_combination",
    ):
        if marker not in library:
            _fail(f"underflow independent-check marker is missing: {marker}")

    rust_paths = sorted(
        path for path in sources if path.startswith(f"{CRATE_RELATIVE_PATH}/") and path.endswith(".rs")
    )
    rust_source = "\n".join(sources[path].decode("utf-8") for path in rust_paths)
    for marker in (
        "PARTICLE_MESH_RECIPROCAL_SCHEMA_ID",
        "CARDINAL_B_SPLINE_ORDER",
        "pub struct Position",
        "pub struct OrthorhombicCell",
        "pub struct ParticleMeshReciprocalSettings",
        "pub struct ParticleMeshReciprocalInput",
        "pub struct ParticleMeshReciprocalEvaluation",
        "pub enum ParticleMeshReciprocalErrorCode",
        "pub fn evaluate",
        "reciprocal_space_kcal_per_mol",
        "forces_kcal_per_mol_angstrom",
        "NonNeutralSystem",
        "InvalidMesh",
        "MAX_EVALUATION_WORK_UNITS",
        "validate_work_limit",
        "dimension.ilog2()",
        "checked_mul",
        "libm::",
    ):
        if marker not in rust_source:
            _fail(f"particle-mesh reciprocal source marker is missing: {marker}")
    if re.search(r"\bunsafe\b", rust_source) is not None:
        _fail("unsafe Rust entered the standalone scalar reference")
    for forbidden in (
        "std::time::Instant",
        "cargo bench",
        "betelgeuze_runtime",
        "betelgeuze_sys",
        "hipLaunchKernel",
        "rocfft",
    ):
        if forbidden in rust_source:
            _fail(f"forbidden execution or dependency marker appeared: {forbidden}")

    example = text(CRATE_RELATIVE_PATH / "examples/profile_observation.rs")
    if "direct_dft::" in example or "mod direct_dft" in example:
        _fail("direct DFT oracle entered the normal observation executable")
    for marker in (
        "full_pme_implemented=false",
        "maximum_fft_dft_checked_in_tests=true",
        "maximum_central_finite_difference",
    ):
        if marker not in example:
            _fail(f"profile observation marker is missing: {marker}")
    fixture_bits = _parse_fixture(sources[FIXTURE_RELATIVE_PATH.as_posix()])
    return fixture_bits


def build_profile(
    *,
    source_manifest_raw: bytes,
    source_count: int,
    sources: dict[str, bytes],
    fixture_bits: dict[str, str],
) -> dict[str, object]:
    force_bits = []
    for atom in range(4):
        force_bits.append(
            {
                "atom": atom,
                "x": fixture_bits[f"force_{atom}_x"],
                "y": fixture_bits[f"force_{atom}_y"],
                "z": fixture_bits[f"force_{atom}_z"],
            }
        )
    return {
        "accuracy_acceptance": dict(ACCURACY_ACCEPTANCE_CONTRACT),
        "accuracy_observation": dict(ACCURACY_OBSERVATION),
        "authority": dict(AUTHORITY_CONTRACT),
        "fixture": dict(FIXTURE_CONTRACT),
        "frozen_observation": {
            "debug_release_bitwise_identical": True,
            "energy_ieee754_bits_hex": fixture_bits[
                "reciprocal_space_kcal_per_mol"
            ],
            "force_ieee754_bits_hex": force_bits,
            "frozen_energy_and_force_component_count": 13,
        },
        "implementation": {
            **IMPLEMENTATION_CONTRACT_BASE,
            "cargo_lock_sha256": _sha256(
                sources[(CRATE_RELATIVE_PATH / "Cargo.lock").as_posix()]
            ),
            "frozen_fixture_sha256": _sha256(
                sources[FIXTURE_RELATIVE_PATH.as_posix()]
            ),
            "source_manifest_entry_count": source_count,
            "source_manifest_sha256": _sha256(source_manifest_raw),
        },
        "numerical_contract": dict(NUMERICAL_CONTRACT),
        "numeric_envelope": dict(NUMERIC_ENVELOPE),
        "operational_boundary": dict(OPERATIONAL_BOUNDARY),
        "prerequisite": dict(PREREQUISITE),
        "profile_id": PROFILE_ID,
        "roadmap_issue": 434,
        "schema_id": SCHEMA_ID,
        "semantic_oracle": dict(SEMANTIC_ORACLE),
        "validation": dict(VALIDATION_CONTRACT),
    }


def require_profile(
    raw: bytes,
    *,
    source_manifest_raw: bytes,
    source_count: int,
    sources: dict[str, bytes],
    fixture_bits: dict[str, str],
) -> dict[str, object]:
    profile = _load_canonical_object(raw, label="profile")
    expected = build_profile(
        source_manifest_raw=source_manifest_raw,
        source_count=source_count,
        sources=sources,
        fixture_bits=fixture_bits,
    )
    if profile != expected:
        _fail("particle-mesh reciprocal profile contract changed")
    authority = profile["authority"]
    assert isinstance(authority, dict)
    if any(value is not False for value in authority.values()):
        _fail("profile grants authority")
    implementation = profile["implementation"]
    assert isinstance(implementation, dict)
    if implementation.get("full_pme_implemented") is not False:
        _fail("reciprocal-only reference was mislabeled as full PME")
    if implementation.get("performance_evidence_collected") is not False:
        _fail("reciprocal-only reference contains performance evidence")
    return profile


def verify(root: Path = ROOT) -> dict[str, object]:
    profile_raw = _require_regular_file(root, PROFILE_RELATIVE_PATH).read_bytes()
    manifest_raw = _require_regular_file(
        root, SOURCE_MANIFEST_RELATIVE_PATH
    ).read_bytes()
    manifest, sources = require_source_manifest(root, manifest_raw)
    fixture_bits = _require_source_contract(sources)
    rows = manifest["files"]
    assert isinstance(rows, list)
    require_profile(
        profile_raw,
        source_manifest_raw=manifest_raw,
        source_count=len(rows),
        sources=sources,
        fixture_bits=fixture_bits,
    )
    historical = require_historical_dependencies(root)
    return {
        "all_authority_false": True,
        "fixed64_cpu_v7_qualification_invoked": False,
        "full_pme_implemented": False,
        "hip_device_execution_invoked": False,
        "molecular_execution_invoked": False,
        "operational_blocker_count": len(OPERATIONAL_BLOCKERS),
        "prerequisite_merge_commit": historical["prerequisite_merge_commit"],
        "profile_path": PROFILE_RELATIVE_PATH.as_posix(),
        "profile_sha256": _sha256(profile_raw),
        "semantic_oracle_merge_commit": historical["semantic_oracle_merge_commit"],
        "source_count": len(rows),
        "source_manifest_path": SOURCE_MANIFEST_RELATIVE_PATH.as_posix(),
        "source_manifest_sha256": _sha256(manifest_raw),
        "unresolved_operational_decisions": 32,
        "verified": True,
    }


def _stage_evidence_file(path: Path, raw: bytes, mode: int) -> Path:
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary = Path(temporary_name)
    try:
        stream = os.fdopen(descriptor, "wb")
        descriptor = -1
        with stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
    except BaseException as exc:
        cleanup_errors: list[str] = []
        if descriptor >= 0:
            try:
                os.close(descriptor)
            except OSError as close_exc:
                cleanup_errors.append(f"descriptor close: {close_exc}")
        cleanup_errors.extend(_cleanup_evidence_temporaries((temporary,)))
        if cleanup_errors:
            raise PmeReciprocalReferenceV1Error(
                "evidence staging failed and temporary cleanup was incomplete: "
                + "; ".join(cleanup_errors)
            ) from exc
        raise
    return temporary


def _cleanup_evidence_temporaries(
    temporaries: tuple[Path | None, ...],
    *,
    preserve: frozenset[Path] = frozenset(),
) -> list[str]:
    errors: list[str] = []
    for temporary in temporaries:
        if temporary is None or temporary in preserve:
            continue
        try:
            temporary.unlink(missing_ok=True)
        except OSError as exc:
            errors.append(f"{temporary}: {exc}")
    return errors


def _require_evidence_target(root: Path, relative: Path) -> Path:
    if (
        relative.is_absolute()
        or not relative.parts
        or any(part in ("", ".", "..") for part in relative.parts)
    ):
        _fail(f"invalid evidence path: {relative}")
    if root.is_symlink() or not root.is_dir():
        _fail(f"evidence root is not a regular directory: {root}")
    try:
        if root.resolve(strict=True) != Path(os.path.abspath(root)):
            _fail(f"evidence root has a symlinked ancestor: {root}")
    except OSError as exc:
        raise PmeReciprocalReferenceV1Error(
            f"cannot resolve evidence root: {root}"
        ) from exc
    parent = root
    for part in relative.parts[:-1]:
        parent /= part
        if parent.is_symlink() or not parent.is_dir():
            _fail(
                "evidence path has a symlinked or non-directory ancestor: "
                f"{relative}"
            )
    path = parent / relative.name
    if path.is_symlink() or (path.exists() and not path.is_file()):
        _fail(f"refusing to replace non-regular evidence path: {relative}")
    return path


def _replace_evidence_transactionally(
    root: Path,
    evidence: tuple[tuple[Path, bytes], ...],
    verify_current: Callable[[], dict[str, object]],
) -> dict[str, object]:
    snapshots: list[tuple[Path, bool, bytes, int]] = []
    seen_targets: set[Path] = set()
    for relative, _ in evidence:
        path = _require_evidence_target(root, relative)
        if path in seen_targets:
            _fail(f"duplicate evidence target: {relative}")
        seen_targets.add(path)
        existed = path.exists()
        snapshots.append(
            (
                path,
                existed,
                path.read_bytes() if existed else b"",
                (path.stat().st_mode & 0o777) if existed else 0o644,
            )
        )

    staged: list[Path] = []
    rollback: list[Path | None] = []
    try:
        for (path, existed, previous_raw, mode), (_, new_raw) in zip(
            snapshots, evidence, strict=True
        ):
            staged.append(_stage_evidence_file(path, new_raw, mode))
            rollback.append(
                _stage_evidence_file(path, previous_raw, mode)
                if existed
                else None
            )
    except BaseException as exc:
        cleanup_errors = _cleanup_evidence_temporaries((*staged, *rollback))
        if cleanup_errors:
            details = list(cleanup_errors)
            if isinstance(exc, PmeReciprocalReferenceV1Error):
                details.insert(0, str(exc))
            raise PmeReciprocalReferenceV1Error(
                "evidence refresh staging failed before commit and temporary "
                "cleanup was incomplete: " + "; ".join(details)
            ) from exc
        if not isinstance(exc, Exception):
            raise
        if isinstance(exc, PmeReciprocalReferenceV1Error):
            raise
        raise PmeReciprocalReferenceV1Error(
            "evidence refresh staging failed before commit"
        ) from exc

    try:
        for (path, _, _, _), temporary in zip(snapshots, staged, strict=True):
            os.replace(temporary, path)
        result = verify_current()
    except BaseException as exc:
        rollback_errors: list[str] = []
        preserved_backups: set[Path] = set()
        for (path, existed, previous_raw, mode), temporary in reversed(
            list(zip(snapshots, rollback, strict=True))
        ):
            try:
                if existed:
                    assert temporary is not None
                    os.replace(temporary, path)
                elif path.is_symlink() or path.exists():
                    path.unlink()
                if existed:
                    if path.is_symlink() or path.read_bytes() != previous_raw:
                        raise OSError("restored bytes do not match snapshot")
                elif path.is_symlink() or path.exists():
                    raise OSError("new evidence path survived rollback")
            except BaseException as rollback_exc:
                backup = temporary
                backup_error = ""
                if existed and (backup is None or not backup.exists()):
                    try:
                        backup = _stage_evidence_file(path, previous_raw, mode)
                    except BaseException as backup_exc:
                        backup = None
                        backup_error = f"; backup recreation failed: {backup_exc}"
                if backup is not None and backup.exists():
                    preserved_backups.add(backup)
                    backup_error += f"; backup preserved at {backup}"
                rollback_errors.append(f"{path}: {rollback_exc}{backup_error}")
        cleanup_errors = _cleanup_evidence_temporaries(
            (*staged, *rollback), preserve=frozenset(preserved_backups)
        )
        if rollback_errors:
            raise PmeReciprocalReferenceV1Error(
                "evidence refresh failed and rollback was incomplete: "
                + "; ".join((*rollback_errors, *cleanup_errors))
            ) from exc
        if cleanup_errors:
            raise PmeReciprocalReferenceV1Error(
                "evidence refresh failed; original evidence was restored but "
                "temporary cleanup was incomplete: "
                + "; ".join(cleanup_errors)
            ) from exc
        if not isinstance(exc, Exception):
            raise
        if isinstance(exc, PmeReciprocalReferenceV1Error):
            raise
        raise PmeReciprocalReferenceV1Error(
            "evidence refresh failed; original evidence restored"
        ) from exc

    cleanup_errors = _cleanup_evidence_temporaries((*staged, *rollback))
    if cleanup_errors:
        raise PmeReciprocalReferenceV1Error(
            "evidence refresh committed and verified but temporary cleanup "
            "was incomplete: " + "; ".join(cleanup_errors)
        )
    return result


def refresh(root: Path = ROOT) -> dict[str, object]:
    require_historical_dependencies(root)
    manifest = build_source_manifest(root)
    manifest_raw = canonical_bytes(manifest)
    rows = manifest["files"]
    assert isinstance(rows, list)
    _, sources = require_source_manifest(root, manifest_raw)
    fixture_bits = _require_source_contract(sources)
    profile_raw = canonical_bytes(
        build_profile(
            source_manifest_raw=manifest_raw,
            source_count=len(rows),
            sources=sources,
            fixture_bits=fixture_bits,
        )
    )
    require_profile(
        profile_raw,
        source_manifest_raw=manifest_raw,
        source_count=len(rows),
        sources=sources,
        fixture_bits=fixture_bits,
    )
    result = _replace_evidence_transactionally(
        root,
        (
            (SOURCE_MANIFEST_RELATIVE_PATH, manifest_raw),
            (PROFILE_RELATIVE_PATH, profile_raw),
        ),
        lambda: verify(root),
    )
    result["refreshed"] = True
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="explicitly regenerate the acyclic manifest and profile binding",
    )
    arguments = parser.parse_args(argv)
    try:
        result = refresh(ROOT) if arguments.refresh else verify(ROOT)
    except PmeReciprocalReferenceV1Error as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, allow_nan=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
