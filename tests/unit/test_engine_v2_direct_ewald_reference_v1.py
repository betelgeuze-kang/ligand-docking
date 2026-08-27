from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROFILE_PATH = ROOT / "config/engine_v2_direct_ewald_reference_profile_v1.json"
CRATE = ROOT / "rust/reference-ewald"
PROFILE_SHA256 = "a6b5023fb896a94668bfd3c65049746b12c01665913237aa44c3b126a8258e78"


def test_profile_identity_parent_and_reference_boundary_are_frozen() -> None:
    raw = PROFILE_PATH.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == PROFILE_SHA256
    profile = json.loads(raw)
    assert profile["schema_id"] == (
        "betelgeuze.engine_v2_direct_ewald_reference_profile/1.0.0"
    )
    assert profile["profile_id"] == (
        "engine_v2_four_charge_direct_ewald_reference_development_v1"
    )
    assert profile["roadmap_issue"] == 434
    assert profile["parent"] == {
        "explicit_composition_profile_sha256": (
            "a9fad385e3eaf84c673507ee513778ad05842da139c282ce9def1c712eb13079"
        ),
        "explicit_composition_merge_commit": (
            "579fe48ea1320ad6139b55118d6368553f6b895b"
        ),
        "explicit_composition_tree": (
            "feac1d09582980a8fc947f5262eec86d4466633b"
        ),
    }
    assert profile["implementation"] == {
        "crate": "rust/reference-ewald",
        "reference_schema_id": "betelgeuze.reference_direct_ewald/1.0.0",
        "arithmetic": "scalar_binary64_with_pinned_libm_transcendentals",
        "transcendental_implementation": (
            "libm_0.2.16_exact_dependency_and_lockfile"
        ),
        "platform_std_transcendentals_used": False,
        "direct_ewald_implemented": True,
        "pme_implemented": False,
        "native_runtime_integrated": False,
        "native_abi_version_allocated": False,
        "external_md_engine_dependency": False,
        "fixed64_cpu_v7_source_closure_modified": False,
        "source_sha256": (
            "0e700dfbbc2204628fbd43254bb51e838039fa436fa7d6c112322156249ae102"
        ),
        "frozen_fixture_sha256": (
            "a720c83852c79e401cb8838e9e20b2196985b6e424275949f77291b30b3da338"
        ),
        "cargo_lock_sha256": (
            "cc64500cc1c97dfda26a8a4c8b8825c5296935f1e63cbaf61676a321364b3d9d"
        ),
    }
    assert "reference-ewald" not in (ROOT / "rust/Cargo.toml").read_text()


def test_fixture_settings_and_frozen_observations_are_exact() -> None:
    profile = json.loads(PROFILE_PATH.read_text())
    assert profile["fixture"] == {
        "atom_count": 4,
        "positions_angstrom": [
            [1.25, 2.5, 3.75],
            [5.1, 3.2, 8.4],
            [10.2, 12.3, 7.7],
            [15.4, 17.1, 19.3],
        ],
        "charges_elementary": [0.7, -0.4, -0.6, 0.30000000000000004],
        "net_charge_elementary": 0.0,
        "net_charge_admission": "canonical_compensated_sum_exactly_zero",
        "orthorhombic_lengths_angstrom": [18.0, 20.0, 22.0],
        "periodic_axes": [True, True, True],
        "excluded_pairs": [[0, 1]],
        "scaled_pairs": [
            {"atom_i": 2, "atom_j": 3, "coulomb_scale": 0.5}
        ],
    }
    assert profile["settings"] == {
        "coulomb_kcal_angstrom_per_mol_e2": 332.063713299,
        "alpha_per_angstrom": 0.31,
        "real_space_cutoff_angstrom": 8.9,
        "reciprocal_max_indices": [5, 5, 5],
        "dielectric": 1.0,
        "minimum_pair_distance_angstrom": 1e-8,
        "periodic_image_comparison_relative_tolerance": 5e-12,
        "real_space_cutoff_ambiguity": (
            "typed_AmbiguousRealSpaceCutoff_within_periodic_image_relative_"
            "tolerance"
        ),
        "neutrality_accumulation": (
            "canonical_absolute_magnitude_then_total_order_neumaier_exact_"
            "zero_required"
        ),
        "self_charge_square_accumulation": (
            "canonical_absolute_magnitude_then_total_order_neumaier"
        ),
        "charge_normalization_scale_elementary": 9.094947017729282e-13,
        "maximum_evaluation_work_units": 10000000,
        "evaluation_work_unit_equation": (
            "seven_times_pair_count_plus_seven_times_pair_rule_count_plus_two_"
            "times_atom_count_times_reciprocal_vector_count_plus_atom_count_"
            "times_maximum_absolute_charge_phase_origin_candidate_count"
        ),
        "real_pair_order": "lexicographic_i_then_j",
        "reciprocal_vector_order": (
            "nx_then_ny_then_nz_ascending_inclusive_omit_zero"
        ),
        "minimum_image_interval": (
            "closed_negative_half_length_to_positive_half_length_with_"
            "atom_order_antisymmetric_exact_tie"
        ),
        "minimum_image_selection": (
            "error_free_separation_comparison_and_wrapped_displacement_"
            "expansion_after_periodic_reduction"
        ),
        "exact_half_tie_detection": (
            "error_free_two_difference_expansion_compared_with_half_before_"
            "rounded_coordinate_difference"
        ),
        "coordinate_reduction": (
            "per_axis_euclidean_remainder_with_rounded_upper_boundary_"
            "recovered_as_nonzero_signed_residual_and_signed_zero_"
            "canonicalized_periodic_equivalent_binary64_inputs_compared_with_"
            "frozen_relative_tolerance_not_bitwise_identity"
        ),
        "cell_volume_multiplication_order": (
            "sorted_minimum_times_maximum_then_middle"
        ),
        "pair_correction_half_cell_tie": (
            "typed_rejection_ambiguous_pair_correction_image"
        ),
        "unit_pair_scale": (
            "semantic_noop_before_pair_correction_image_selection"
        ),
        "zero_charge_pair_rule": (
            "semantic_noop_before_pair_correction_image_selection"
        ),
        "pair_correction_energy_accumulation": (
            "canonical_absolute_magnitude_then_total_order_neumaier"
        ),
        "pair_correction_force_accumulation": (
            "per_atom_axis_canonical_absolute_magnitude_then_total_order_neumaier"
        ),
        "real_space_energy_accumulation": (
            "canonical_absolute_magnitude_then_total_order_neumaier"
        ),
        "real_space_force_accumulation": (
            "per_atom_axis_canonical_absolute_magnitude_then_total_order_neumaier"
        ),
        "reciprocal_damping_order": (
            "translation_equivariant_maximum_absolute_charge_then_global_"
            "inversion_invariant_nonzero_charge_only_rooted_signed_minimum_"
            "image_geometry_"
            "signature_atom_order_independent_common_origin_relative_phases_"
            "with_canonical_"
            "compensated_axis_sum_then_exact_power_of_two_charge_normalization_"
            "then_canonical_compensated_structure_sum_then_wave_scaled_prefactor_"
            "before_phase_combination_with_log_domain_scaled_subnormal_or_zero_"
            "exponential_reconstruction"
        ),
        "real_space_energy_order": (
            "charge_prefactor_times_erfc_over_distance_for_subunit_distance_"
            "else_charge_prefactor_times_erfc_then_divide"
        ),
        "real_space_force_order": (
            "distance_adaptive_damping_division_then_distance_adaptive_"
            "cartesian_component_scaling"
        ),
    }
    assert profile["numeric_envelope"] == {
        "maximum_absolute_coordinate_angstrom": 1e12,
        "cell_length_angstrom": {"minimum": 1e-6, "maximum": 1e9},
        "nonzero_absolute_charge_elementary": {
            "minimum": 1e-12,
            "maximum": 16.0,
        },
        "alpha_per_angstrom": {"minimum": 1e-12, "maximum": 1e6},
        "real_space_cutoff_angstrom": {"minimum": 1e-8, "maximum": 1e8},
        "dielectric": {"minimum": 1e-12, "maximum": 1e12},
        "minimum_pair_distance_angstrom": {
            "minimum": 1e-8,
            "maximum": 1e3,
        },
        "minimum_pair_distance_below_cutoff_required": True,
        "pair_distance_safety": (
            "minimum_squared_is_normal_and_checked_before_any_inverse_"
            "distance_operation"
        ),
        "charge_product_safety": "minimum_nonzero_charge_product_is_normal",
        "real_space_zero_damping": (
            "typed_DampingUnderflow_for_subnormal_or_zero_erfc_or_"
            "exponential_on_nonzero_charge_pair"
        ),
        "reciprocal_zero_damping": (
            "log_domain_scaled_reconstruction_when_completed_energy_or_force_"
            "can_round_nonzero"
        ),
        "reciprocal_phase_product_underflow": (
            "typed_PhaseUnderflow_for_subnormal_or_zero_product"
        ),
    }
    observation = profile["frozen_observation"]
    assert observation["total_kcal_per_mol"] == -6.0630802511248305
    assert observation["maximum_central_finite_difference_force_error_kcal_per_mol_angstrom"] == (
        1.1746751238383979e-8
    )
    assert observation[
        "reciprocal_bound_absolute_total_difference_from_bound_9_kcal_per_mol"
    ] == {
        "bound_3": 0.21813662961478286,
        "bound_5": 0.0011959243365424754,
        "bound_7": 1.6123660202538304e-6,
    }
    assert observation["debug_release_bitwise_identical"] is True
    assert observation["frozen_energy_and_force_component_count"] == 17


def test_validation_authority_and_standalone_crate_are_bounded() -> None:
    profile = json.loads(PROFILE_PATH.read_text())
    assert all(profile["validation"].values())
    authority = profile["authority"]
    assert authority["development_fixture_only"] is True
    assert all(
        value is False
        for key, value in authority.items()
        if key != "development_fixture_only"
    )

    manifest = (CRATE / "Cargo.toml").read_text()
    assert "[workspace]" in manifest
    assert 'libm = { version = "=0.2.16"' in manifest
    assert "betelgeuze-runtime" not in manifest
    assert "reference-physics" not in manifest
    source = (CRATE / "src/lib.rs").read_text()
    for required in (
        "pub const EWALD_SCHEMA_ID",
        "pub fn evaluate",
        "real_space_kcal_per_mol",
        "reciprocal_space_kcal_per_mol",
        "self_kcal_per_mol",
        "pair_correction_kcal_per_mol",
        "libm::erfc",
        "libm::exp",
        "libm::sincos",
        "libm::sqrt",
        "libm::log",
        "reciprocal_max_indices",
        "NonNeutralSystem",
        "CutoffViolatesMinimumImage",
        "ConflictingPairRule",
        "AmbiguousPairCorrectionImage",
        "AmbiguousRealSpaceCutoff",
        "DampingUnderflow",
        "PhaseUnderflow",
        "MAX_EVALUATION_WORK_UNITS",
        "pair_rule_count",
        "signed_residual",
        "MIN_NONZERO_ABSOLUTE_CHARGE_E",
        "MIN_SUPPORTED_PAIR_DISTANCE_ANGSTROM",
        "apply_canonical_force_terms",
        "phase_origin_signature",
        "phase_origin_candidate_count",
    ):
        assert required in source
    for forbidden in (".exp()", ".sin_cos()", ".sqrt()"):
        assert forbidden not in source

    fixture = (CRATE / "fixtures/direct_ewald_v1.tsv").read_text()
    assert "betelgeuze.reference_direct_ewald/1.0.0" in fixture
    assert len([line for line in fixture.splitlines() if "\t" in line]) == 18

    implementation = profile["implementation"]
    assert hashlib.sha256((CRATE / "src/lib.rs").read_bytes()).hexdigest() == (
        implementation["source_sha256"]
    )
    assert hashlib.sha256(
        (CRATE / "fixtures/direct_ewald_v1.tsv").read_bytes()
    ).hexdigest() == implementation["frozen_fixture_sha256"]
    assert hashlib.sha256((CRATE / "Cargo.lock").read_bytes()).hexdigest() == (
        implementation["cargo_lock_sha256"]
    )
