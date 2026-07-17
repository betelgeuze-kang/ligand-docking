"""Machine-readable capability state derived from executable Engine v2 contracts.

The capability snapshot separates implementation from calibration, public evidence,
scientific validation, product qualification, and customer enablement. A component
can exist and be tested while remaining claim-blocked and unavailable to product
routes.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from .engine import REFERENCE_CLAIM_BLOCKERS

CAPABILITY_SCHEMA_VERSION = 4
ENGINE_ID = "betelgeuze_independent_engine_v2"
IMPLEMENTATION_STAGE = "v2_l_cpu_reference_validation_protocol"

CPU_REFERENCE_CAPABILITY_ID = "v2_cpu_reference_orchestrator"
PDB_INGEST_CAPABILITY_ID = "v2_bounded_pdb_ingest"
SDF_INGEST_CAPABILITY_ID = "v2_bounded_sdf_v2000_ingest"
CIF_SYNTAX_CAPABILITY_ID = "v2_bounded_cif_syntax"
MMCIF_SEMANTICS_CAPABILITY_ID = "v2_bounded_mmcif_semantic_projection"
MMCIF_ZERO_OCCUPANCY_CAPABILITY_ID = "v2_bounded_mmcif_zero_occupancy_declarations"
MMCIF_ALTLOC_DECLARATIONS_CAPABILITY_ID = "v2_bounded_mmcif_altloc_declarations"
MMCIF_ATOM_SITE_MODEL_POLICY_CAPABILITY_ID = "v2_bounded_mmcif_atom_site_model_policy"
MMCIF_BIOLOGICAL_ASSEMBLY_POLICY_CAPABILITY_ID = (
    "v2_bounded_mmcif_biological_assembly_policy"
)
MMCIF_MISSING_ATOM_RESIDUE_POLICY_CAPABILITY_ID = (
    "v2_bounded_mmcif_missing_atom_residue_policy"
)
MMCIF_MODIFIED_RESIDUE_DECLARATIONS_CAPABILITY_ID = (
    "v2_bounded_mmcif_modified_residue_declarations"
)
MMCIF_NONPOLY_IDENTITY_CAPABILITY_ID = "v2_bounded_mmcif_nonpoly_identity"
MMCIF_NONPOLY_COMPONENT_DECLARATIONS_CAPABILITY_ID = (
    "v2_bounded_mmcif_nonpoly_component_declarations"
)
MMCIF_NONPOLY_COMPONENT_ROLE_CAPABILITY_ID = "v2_bounded_mmcif_nonpoly_component_roles"
MMCIF_STRUCT_CONN_DECLARATIONS_CAPABILITY_ID = (
    "v2_bounded_mmcif_struct_conn_declarations"
)
MMCIF_NONPOLY_ATOM_SITE_OBSERVATIONS_CAPABILITY_ID = (
    "v2_bounded_mmcif_nonpoly_atom_site_observations"
)
MMCIF_NONPOLY_COORDINATE_VALUES_CAPABILITY_ID = (
    "v2_bounded_mmcif_nonpoly_coordinate_values"
)
MMCIF_NONPOLY_ATOM_SITE_SCALAR_VALUES_CAPABILITY_ID = (
    "v2_bounded_mmcif_nonpoly_atom_site_scalar_values"
)
MMCIF_NONPOLY_CANONICAL_TOPOLOGY_CAPABILITY_ID = (
    "v2_bounded_mmcif_nonpoly_canonical_topology"
)
MMCIF_NONPOLY_PREPARATION_CAPABILITY_ID = (
    "v2_bounded_mmcif_nonpoly_neutral_coh_preparation"
)
MMCIF_NONPOLY_HYDROGEN_COORDINATE_CAPABILITY_ID = (
    "v2_bounded_mmcif_nonpoly_hydrogen_coordinates"
)
MMCIF_NONPOLY_ALL_ATOM_SYSTEM_CAPABILITY_ID = (
    "v2_bounded_mmcif_nonpoly_all_atom_systems"
)
MMCIF_NONPOLY_PARAMETER_SOURCE_BINDING_CAPABILITY_ID = (
    "v2_bounded_mmcif_nonpoly_parameter_source_binding"
)
MMCIF_NONPOLY_PARTIAL_CHARGE_ASSIGNMENT_CAPABILITY_ID = (
    "v2_bounded_mmcif_nonpoly_partial_charge_assignment"
)
MMCIF_NONPOLY_ALL_ATOM_ROUND_TRIP_CAPABILITY_ID = (
    "v2_bounded_mmcif_nonpoly_all_atom_round_trip"
)
MMCIF_NONPOLY_PH_PROTONATION_CAPABILITY_ID = (
    "v2_bounded_mmcif_nonpoly_ph_dependent_protonation"
)
MMCIF_NONPOLY_PH_PROTONATION_CORPUS_CAPABILITY_ID = (
    "v2_bounded_mmcif_nonpoly_ph_protonation_corpus"
)
MMCIF_NONPOLY_TAUTOMER_SELECTION_CAPABILITY_ID = (
    "v2_bounded_mmcif_nonpoly_reference_tautomer_selection"
)
MMCIF_NONPOLY_TAUTOMER_SELECTION_CORPUS_CAPABILITY_ID = (
    "v2_bounded_mmcif_nonpoly_tautomer_selection_corpus"
)
PARAMETER_SOURCE_PROVENANCE_CAPABILITY_ID = "v2_reviewed_parameter_source_provenance"
MMCIF_NONPOLY_PREPARATION_CORPUS_CAPABILITY_ID = (
    "v2_bounded_mmcif_nonpoly_preparation_corpus"
)
PHYSICS_REGISTRY_CAPABILITY_ID = "v2_independent_physics_registry"
H5_PARAMETER_APPLICABILITY_CAPABILITY_ID = (
    "v2_h5_reference_physics_parameter_applicability_record"
)
CPU_REFERENCE_VALIDATION_PROTOCOL_CAPABILITY_ID = (
    "v2_cpu_reference_energy_force_validation_protocol"
)
DOCKING_CAPABILITY_ID = "v2_bounded_docking_scaffold"
BENCHMARK_CAPABILITY_ID = "v2_benchmark_failure_row_ledger"
PUBLIC_BENCHMARK_PROTOCOL_CAPABILITY_ID = "v2_frozen_public_benchmark_protocol"
EXTERNAL_BASELINE_CAPABILITY_ID = "v2_external_baseline_receipts"
DISTRIBUTION_CAPABILITY_ID = "v2_independent_distribution"

CAPABILITY_BLOCKERS: dict[str, tuple[str, ...]] = {
    CPU_REFERENCE_CAPABILITY_ID: tuple(REFERENCE_CLAIM_BLOCKERS),
    PDB_INGEST_CAPABILITY_ID: (
        "chemistry_validation_missing",
        "hydrogen_and_protonation_inference_not_supported",
        "pdb_connectivity_policy_not_complete",
        "product_integration_not_qualified",
    ),
    SDF_INGEST_CAPABILITY_ID: (
        "chemistry_validation_missing",
        "aromaticity_and_tautomer_validation_missing",
        "multi_record_ingest_not_supported",
        "product_integration_not_qualified",
    ),
    CIF_SYNTAX_CAPABILITY_ID: (
        "semantic_mmcif_projection_is_separate_capability",
        "dictionary_conformance_not_established",
        "assembly_missingness_and_altloc_semantics_missing",
        "product_integration_not_qualified",
    ),
    MMCIF_SEMANTICS_CAPABILITY_ID: (
        "atom_site_coordinate_observation_not_interpreted",
        "mmcif_missingness_altloc_and_assembly_not_interpreted",
        "mmcif_chemistry_and_topology_not_interpreted",
        "product_integration_not_qualified",
    ),
    MMCIF_ZERO_OCCUPANCY_CAPABILITY_ID: (
        "atom_site_occupancy_not_crosschecked",
        "coordinate_observation_and_missingness_not_inferred",
        "alternate_location_population_not_interpreted",
        "mmcif_chemistry_topology_and_preparation_not_interpreted",
        "product_integration_not_qualified",
    ),
    MMCIF_ALTLOC_DECLARATIONS_CAPABILITY_ID: (
        "conformer_selection_not_implemented",
        "coordinate_and_occupancy_values_not_interpreted",
        "altloc_population_and_missingness_not_inferred",
        "mmcif_chemistry_topology_and_preparation_not_interpreted",
        "product_integration_not_qualified",
    ),
    MMCIF_ATOM_SITE_MODEL_POLICY_CAPABILITY_ID: (
        "multimodel_execution_not_supported",
        "single_model_non_1_execution_not_supported",
        "cross_category_model_references_not_reconciled",
        "model_selection_ensemble_and_trajectory_semantics_not_interpreted",
        "coordinate_identity_and_chemistry_not_interpreted",
        "scientific_validation_missing",
        "product_integration_not_qualified",
    ),
    MMCIF_BIOLOGICAL_ASSEMBLY_POLICY_CAPABILITY_ID: (
        "source_declared_biological_assembly_expansion_not_supported",
        "assembly_id_generation_expression_and_asym_list_not_interpreted",
        "operation_matrix_vector_and_composition_not_interpreted",
        "absence_does_not_prove_asymmetric_unit_is_biological_assembly",
        "biological_assembly_correctness_not_assessed",
        "coordinates_not_expanded",
        "scientific_validation_missing",
        "product_integration_not_qualified",
    ),
    MMCIF_MISSING_ATOM_RESIDUE_POLICY_CAPABILITY_ID: (
        "source_declared_unobserved_residue_repair_not_supported",
        "source_declared_unobserved_atom_repair_not_supported",
        "source_declared_zero_occupancy_residue_repair_not_supported",
        "source_declared_zero_occupancy_atom_repair_not_supported",
        "declaration_identity_not_interpreted",
        "absence_does_not_prove_structure_complete",
        "missingness_inference_and_coordinate_generation_not_supported",
        "scientific_validation_missing",
        "product_integration_not_qualified",
    ),
    MMCIF_MODIFIED_RESIDUE_DECLARATIONS_CAPABILITY_ID: (
        "source_authentication_missing",
        "atom_site_label_identity_not_crosschecked",
        "parent_component_chemistry_not_interpreted",
        "modification_nature_not_interpreted",
        "model_insertion_and_auth_semantics_not_interpreted",
        "modified_residue_preparation_not_supported",
        "scientific_validation_missing",
        "product_integration_not_qualified",
    ),
    MMCIF_NONPOLY_IDENTITY_CAPABILITY_ID: (
        "source_authentication_missing",
        "atom_site_identity_and_coordinates_not_joined",
        "component_chemistry_and_roles_not_interpreted",
        "bond_topology_and_preparation_not_interpreted",
        "product_integration_not_qualified",
    ),
    MMCIF_NONPOLY_COMPONENT_DECLARATIONS_CAPABILITY_ID: (
        "source_authentication_missing",
        "atom_site_identity_and_coordinates_not_joined",
        "component_chemistry_not_interpreted",
        "bond_order_and_topology_not_interpreted",
        "preparation_and_parameterability_not_assessed",
        "product_integration_not_qualified",
    ),
    MMCIF_NONPOLY_COMPONENT_ROLE_CAPABILITY_ID: (
        "source_authentication_missing",
        "general_ligand_role_not_interpreted",
        "cofactor_role_not_interpreted",
        "modified_residue_role_not_interpreted",
        "metal_coordination_chemistry_not_interpreted",
        "monoatomic_metal_preparation_not_supported",
        "monoatomic_nonmetal_ion_preparation_not_supported",
        "scientific_validation_missing",
        "product_integration_not_qualified",
    ),
    MMCIF_STRUCT_CONN_DECLARATIONS_CAPABILITY_ID: (
        "source_authentication_missing",
        "atom_site_identity_and_coordinates_not_joined",
        "connection_type_symmetry_and_order_not_interpreted",
        "covalence_coordination_and_topology_not_interpreted",
        "component_chemistry_and_preparation_not_interpreted",
        "product_integration_not_qualified",
    ),
    MMCIF_NONPOLY_ATOM_SITE_OBSERVATIONS_CAPABILITY_ID: (
        "source_authentication_missing",
        "coordinate_tokens_not_numerically_interpreted",
        "occupancy_b_factor_and_formal_charge_not_interpreted",
        "altloc_population_and_missingness_not_inferred",
        "connection_chemistry_and_topology_not_interpreted",
        "preparation_and_parameterability_not_assessed",
        "product_integration_not_qualified",
    ),
    MMCIF_NONPOLY_COORDINATE_VALUES_CAPABILITY_ID: (
        "source_authentication_missing",
        "coordinate_units_and_geometry_not_interpreted",
        "occupancy_b_factor_and_formal_charge_not_interpreted",
        "altloc_population_and_missingness_not_inferred",
        "connection_chemistry_and_topology_not_interpreted",
        "preparation_and_parameterability_not_assessed",
        "product_integration_not_qualified",
    ),
    MMCIF_NONPOLY_ATOM_SITE_SCALAR_VALUES_CAPABILITY_ID: (
        "source_authentication_missing",
        "occupancy_population_and_altloc_semantics_not_interpreted",
        "b_factor_quality_not_assessed",
        "formal_charge_chemistry_not_validated",
        "type_symbol_and_component_chemistry_not_crosschecked",
        "connection_chemistry_and_topology_not_interpreted",
        "preparation_and_parameterability_not_assessed",
        "product_integration_not_qualified",
    ),
    MMCIF_NONPOLY_CANONICAL_TOPOLOGY_CAPABILITY_ID: (
        "source_authentication_missing",
        "non_identity_symmetry_not_supported",
        "hydrogen_disulfide_and_extended_bond_orders_not_supported",
        "atom_element_charge_and_aromaticity_not_crosschecked",
        "coordinate_geometry_and_bond_distances_not_assessed",
        "chemistry_preparation_and_parameterability_not_assessed",
        "product_integration_not_qualified",
    ),
    MMCIF_NONPOLY_PREPARATION_CAPABILITY_ID: (
        "source_declared_biological_assembly_preparation_not_supported",
        "source_declared_observation_gap_preparation_not_supported",
        "hydrogen_coordinate_geometry_not_validated",
        "reviewed_parameter_source_binding_is_separate",
        "aromatic_charged_stereo_and_extended_elements_not_supported",
        "general_ph_tautomer_and_intercomponent_connections_not_prepared",
        "bounded_cid_176_ph_protonation_is_separate_capability",
        "canonical_all_atom_system_not_bound_to_preparation_report",
        "scientific_validation_missing",
        "product_integration_not_qualified",
    ),
    MMCIF_NONPOLY_HYDROGEN_COORDINATE_CAPABILITY_ID: (
        "fixed_parent_offset_does_not_interpret_neighbor_geometry",
        "hydrogen_bond_length_not_calibrated",
        "stereochemistry_protonation_and_tautomer_not_interpreted",
        "steric_clash_and_coordinate_quality_not_assessed",
        "coordinate_minimization_not_performed",
        "reviewed_parameter_source_binding_is_separate",
        "partial_charge_assignment_not_performed",
        "canonical_all_atom_system_adapter_is_separate",
        "scientific_validation_missing",
        "product_integration_not_qualified",
    ),
    PARAMETER_SOURCE_PROVENANCE_CAPABILITY_ID: (
        "source_artifact_not_bundled",
        "source_format_semantic_validation_missing",
        "candidate_scope_parameter_coverage_not_validated",
        "parameter_assignment_not_implemented",
        "partial_charge_assignment_is_separate_capability",
        "applicability_domain_validation_missing",
        "parameter_value_calibration_missing",
        "force_energy_validation_missing",
        "legal_compliance_determination_not_provided",
        "canonical_system_binding_is_separate_capability",
        "scientific_validation_missing",
        "product_integration_not_qualified",
    ),
    MMCIF_NONPOLY_ALL_ATOM_SYSTEM_CAPABILITY_ID: (
        "intercomponent_covalent_connections_not_materialized",
        "intercomponent_coordination_preserved_as_metadata_only",
        "fixed_parent_offset_geometry_not_validated",
        "source_authentication_missing",
        "reviewed_parameter_source_binding_is_separate_capability",
        "parameter_assignment_not_implemented",
        "partial_charge_assignment_is_separate_capability",
        "atom_masses_not_assigned",
        "canonical_all_atom_round_trip_is_separate_capability",
        "chemistry_validation_missing",
        "scientific_validation_missing",
        "product_integration_not_qualified",
    ),
    MMCIF_NONPOLY_PARAMETER_SOURCE_BINDING_CAPABILITY_ID: (
        "source_artifact_not_bundled",
        "offxml_semantic_parsing_not_implemented",
        "candidate_scope_parameter_coverage_not_validated",
        "applicability_domain_validation_missing",
        "parameter_assignment_not_implemented",
        "partial_charge_assignment_is_separate_capability",
        "atom_masses_not_assigned",
        "fixed_parent_offset_geometry_not_validated",
        "force_energy_validation_missing",
        "scientific_validation_missing",
        "product_integration_not_qualified",
    ),
    MMCIF_NONPOLY_PARTIAL_CHARGE_ASSIGNMENT_CAPABILITY_ID: (
        "explicit_charge_values_required_from_caller",
        "charge_generation_not_implemented",
        "charge_method_scientific_validation_missing",
        "charge_value_calibration_missing",
        "parameter_coverage_and_applicability_not_validated",
        "force_field_parameter_assignment_not_implemented",
        "atom_masses_not_assigned",
        "fixed_parent_offset_geometry_not_validated",
        "force_energy_validation_missing",
        "scientific_validation_missing",
        "product_integration_not_qualified",
    ),
    MMCIF_NONPOLY_ALL_ATOM_ROUND_TRIP_CAPABILITY_ID: (
        "original_mmcif_text_not_re_emitted",
        "source_token_spelling_order_comments_and_whitespace_not_preserved",
        "canonical_engine_v2_json_format_only",
        "caller_supplied_partial_charges_not_scientifically_validated",
        "force_field_parameter_assignment_not_implemented",
        "atom_masses_not_assigned",
        "fixed_parent_offset_geometry_not_validated",
        "chemistry_force_energy_and_scientific_validation_missing",
        "product_integration_not_qualified",
    ),
    MMCIF_NONPOLY_PH_PROTONATION_CAPABILITY_ID: (
        "exact_pubchem_cid_176_neutral_acetic_acid_graph_only",
        "source_structure_identity_not_authenticated",
        "single_monoprotic_acid_site_only",
        "fixed_reviewed_pka_not_predicted_or_calibrated",
        "ambiguous_population_abstains_below_90_percent_dominance",
        "localized_carboxylate_resonance_equivalence_not_interpreted",
        "bounded_cid_177_11199_tautomer_selection_is_separate_capability",
        "source_observed_acidic_hydrogen_removal_not_supported",
        "partial_charge_assignment_not_performed",
        "parameter_assignment_not_implemented",
        "atom_masses_not_assigned",
        "geometry_energy_and_force_not_validated",
        "scientific_validation_missing",
        "product_integration_not_qualified",
    ),
    MMCIF_NONPOLY_PH_PROTONATION_CORPUS_CAPABILITY_ID: (
        "two_pubchem_structure_identities_only",
        "manually_projected_mmcif_coordinates_are_contract_fixtures",
        "source_structure_identity_not_authenticated",
        "pubchem_source_specific_license_review_remains",
        "raw_pubchem_records_not_bundled",
        "tautomer_selection_evidence_is_separate_bounded_pair_corpus",
        "parameter_fitting_not_authorized",
        "scientific_validation_missing",
        "product_integration_not_qualified",
    ),
    MMCIF_NONPOLY_TAUTOMER_SELECTION_CAPABILITY_ID: (
        "exact_pubchem_cid_177_and_11199_neutral_c2h4o_graphs_only",
        "reviewed_reference_canonical_identity_not_thermodynamic_preference",
        "source_structure_identity_not_authenticated",
        "generated_hydroxyl_hydrogen_transfer_only",
        "source_observed_hydrogen_move_not_supported",
        "fixed_parent_offset_geometry_not_validated",
        "tautomer_population_equilibrium_and_ph_not_interpreted",
        "partial_charge_assignment_not_performed",
        "parameter_assignment_not_implemented",
        "atom_masses_not_assigned",
        "geometry_energy_and_force_not_validated",
        "scientific_validation_missing",
        "product_integration_not_qualified",
    ),
    MMCIF_NONPOLY_TAUTOMER_SELECTION_CORPUS_CAPABILITY_ID: (
        "three_pubchem_structure_identities_only",
        "manually_projected_mmcif_coordinates_are_contract_fixtures",
        "source_structure_identity_not_authenticated",
        "pubchem_source_specific_license_review_remains",
        "raw_pubchem_records_not_bundled",
        "parameter_fitting_not_authorized",
        "thermodynamic_and_population_evidence_missing",
        "scientific_validation_missing",
        "product_integration_not_qualified",
    ),
    MMCIF_NONPOLY_PREPARATION_CORPUS_CAPABILITY_ID: (
        "synthetic_base_corpus_plus_separate_real_world_ph_and_tautomer_corpora",
        "zero_classified_implementation_gaps_do_not_establish_scientific_readiness",
        "parameter_fitting_not_authorized",
        "scientific_validation_missing",
        "product_integration_not_qualified",
    ),
    PHYSICS_REGISTRY_CAPABILITY_ID: (
        "reference_physics_scientific_validation_missing",
        "applicability_domain_evidence_missing",
        "public_force_energy_validation_missing",
    ),
    H5_PARAMETER_APPLICABILITY_CAPABILITY_ID: (
        "production_reference_parameter_values_not_shipped",
        "caller_supplied_parameter_values_not_independently_reviewed",
        "reviewed_sage_source_not_bound_to_runtime_parameter_values",
        "offxml_parsing_atom_typing_and_parameter_assignment_not_implemented",
        "partial_charge_generation_and_atom_mass_assignment_not_implemented",
        "improper_torsions_constraints_long_range_and_solvation_not_supported",
        "automatic_bonded_exclusion_and_one_four_scaling_inference_not_implemented",
        "runtime_capacity_envelope_is_not_scientific_applicability_evidence",
        "molecule_element_charge_and_chemical_space_coverage_not_validated",
        "parameter_fitting_not_authorized",
        "independent_force_energy_validation_missing",
        "scientific_validation_missing",
        "product_integration_not_qualified",
    ),
    CPU_REFERENCE_VALIDATION_PROTOCOL_CAPABILITY_ID: (
        "fixture_materializer_not_implemented",
        "independent_analytic_oracle_not_implemented",
        "oracle_source_identity_not_bound",
        "reviewed_runtime_parameter_values_not_bound",
        "scientific_parameter_applicability_domain_not_established",
        "scientific_holdout_case_manifest_not_frozen",
        "independent_scientific_review_missing",
        "signed_execution_authorization_receipt_missing",
        "validation_execution_not_authorized",
        "validation_results_not_collected",
        "parameter_fitting_not_authorized",
        "minimization_validation_protocol_missing",
        "scientific_validation_missing",
        "product_integration_not_qualified",
    ),
    DOCKING_CAPABILITY_ID: (
        "docking_proposal_scaffold_not_scientifically_validated",
        "validated_docking_scorer_missing",
        "public_pose_validity_and_ranking_evidence_missing",
        "product_integration_not_qualified",
    ),
    BENCHMARK_CAPABILITY_ID: (
        "benchmark_protocol_not_publicly_validated",
        "public_holdout_results_missing",
        "public_asymmetric_attestation_and_transparency_missing",
    ),
    PUBLIC_BENCHMARK_PROTOCOL_CAPABILITY_ID: (
        "four_case_contract_cohort_not_statistically_representative",
        "posebusters_benchmark_equivalence_not_established",
        "symmetry_mapping_materializer_not_implemented",
        "reference_ligand_match_materializer_not_implemented",
        "public_benchmark_not_executed",
        "public_holdout_results_missing",
        "independent_attestation_missing",
        "legal_compliance_determination_not_made",
        "scientific_validation_missing",
        "product_integration_not_qualified",
    ),
    EXTERNAL_BASELINE_CAPABILITY_ID: (
        "reviewed_external_engine_results_missing",
        "public_comparison_evidence_missing",
        "operator_execution_not_authorized",
    ),
    DISTRIBUTION_CAPABILITY_ID: (
        "release_candidate_not_published",
        "scientific_validation_missing",
        "gpu_parity_evidence_missing",
    ),
}


def _row(
    capability_id: str,
    *,
    current_state: str,
    internal_execution_enabled: bool,
    blocker_source: str,
) -> dict[str, Any]:
    return {
        "current_state": current_state,
        "implemented": True,
        "reference_contract_ready": True,
        "internal_reference_execution_enabled": bool(internal_execution_enabled),
        "calibrated": False,
        "scientifically_validated": False,
        "public_evidence_ready": False,
        "benchmark_validated": False,
        "product_qualified": False,
        "customer_execution_enabled": False,
        "claim_safe": False,
        "blocker_source": blocker_source,
        "blockers": list(CAPABILITY_BLOCKERS[capability_id]),
    }


def capability_snapshot() -> dict[str, Any]:
    """Return the canonical capability snapshot for the bounded Engine v2 surface.

    The returned object is newly allocated so callers cannot mutate module-level
    policy state through a previously returned dictionary.
    """

    payload = {
        "schema_version": CAPABILITY_SCHEMA_VERSION,
        "engine_id": ENGINE_ID,
        "implementation_stage": IMPLEMENTATION_STAGE,
        "claim_policy": {
            "customer_execution_enabled": False,
            "scientific_validity_green": False,
            "benchmark_validity_green": False,
            "gpu_acceleration_claim_allowed": False,
            "docking_accuracy_claim_allowed": False,
            "free_energy_claim_allowed": False,
        },
        "capabilities": {
            CPU_REFERENCE_CAPABILITY_ID: _row(
                CPU_REFERENCE_CAPABILITY_ID,
                current_state="fail_closed_internal_reference",
                internal_execution_enabled=True,
                blocker_source="betelgeuze_engine_v2.engine.REFERENCE_CLAIM_BLOCKERS",
            ),
            PDB_INGEST_CAPABILITY_ID: _row(
                PDB_INGEST_CAPABILITY_ID,
                current_state="bounded_strict_ingest_only",
                internal_execution_enabled=True,
                blocker_source="betelgeuze_engine_v2.capabilities.CAPABILITY_BLOCKERS",
            ),
            SDF_INGEST_CAPABILITY_ID: _row(
                SDF_INGEST_CAPABILITY_ID,
                current_state="bounded_strict_ingest_only",
                internal_execution_enabled=True,
                blocker_source="betelgeuze_engine_v2.capabilities.CAPABILITY_BLOCKERS",
            ),
            CIF_SYNTAX_CAPABILITY_ID: _row(
                CIF_SYNTAX_CAPABILITY_ID,
                current_state="bounded_single_block_lexical_structural_subset",
                internal_execution_enabled=True,
                blocker_source="betelgeuze_engine_v2.capabilities.CAPABILITY_BLOCKERS",
            ),
            MMCIF_SEMANTICS_CAPABILITY_ID: _row(
                MMCIF_SEMANTICS_CAPABILITY_ID,
                current_state="bounded_entity_asym_polymer_sequence_projection",
                internal_execution_enabled=True,
                blocker_source="betelgeuze_engine_v2.capabilities.CAPABILITY_BLOCKERS",
            ),
            MMCIF_ZERO_OCCUPANCY_CAPABILITY_ID: _row(
                MMCIF_ZERO_OCCUPANCY_CAPABILITY_ID,
                current_state="bounded_source_reported_zero_occupancy_declarations",
                internal_execution_enabled=True,
                blocker_source="betelgeuze_engine_v2.capabilities.CAPABILITY_BLOCKERS",
            ),
            MMCIF_ALTLOC_DECLARATIONS_CAPABILITY_ID: _row(
                MMCIF_ALTLOC_DECLARATIONS_CAPABILITY_ID,
                current_state="bounded_polymer_atom_site_altloc_declarations",
                internal_execution_enabled=True,
                blocker_source="betelgeuze_engine_v2.capabilities.CAPABILITY_BLOCKERS",
            ),
            MMCIF_ATOM_SITE_MODEL_POLICY_CAPABILITY_ID: _row(
                MMCIF_ATOM_SITE_MODEL_POLICY_CAPABILITY_ID,
                current_state=(
                    "bounded_complete_atom_site_model_set_and_single_model_1_"
                    "execution_policy"
                ),
                internal_execution_enabled=True,
                blocker_source="betelgeuze_engine_v2.capabilities.CAPABILITY_BLOCKERS",
            ),
            MMCIF_BIOLOGICAL_ASSEMBLY_POLICY_CAPABILITY_ID: _row(
                MMCIF_BIOLOGICAL_ASSEMBLY_POLICY_CAPABILITY_ID,
                current_state=(
                    "bounded_source_declared_biological_assembly_preparation_admission"
                ),
                internal_execution_enabled=True,
                blocker_source="betelgeuze_engine_v2.capabilities.CAPABILITY_BLOCKERS",
            ),
            MMCIF_MISSING_ATOM_RESIDUE_POLICY_CAPABILITY_ID: _row(
                MMCIF_MISSING_ATOM_RESIDUE_POLICY_CAPABILITY_ID,
                current_state=(
                    "bounded_source_declared_observation_gap_preparation_admission"
                ),
                internal_execution_enabled=True,
                blocker_source="betelgeuze_engine_v2.capabilities.CAPABILITY_BLOCKERS",
            ),
            MMCIF_MODIFIED_RESIDUE_DECLARATIONS_CAPABILITY_ID: _row(
                MMCIF_MODIFIED_RESIDUE_DECLARATIONS_CAPABILITY_ID,
                current_state=(
                    "bounded_source_declared_modified_polymer_residue_identity"
                ),
                internal_execution_enabled=True,
                blocker_source="betelgeuze_engine_v2.capabilities.CAPABILITY_BLOCKERS",
            ),
            MMCIF_NONPOLY_IDENTITY_CAPABILITY_ID: _row(
                MMCIF_NONPOLY_IDENTITY_CAPABILITY_ID,
                current_state="bounded_nonpoly_component_instance_identity",
                internal_execution_enabled=True,
                blocker_source="betelgeuze_engine_v2.capabilities.CAPABILITY_BLOCKERS",
            ),
            MMCIF_NONPOLY_COMPONENT_DECLARATIONS_CAPABILITY_ID: _row(
                MMCIF_NONPOLY_COMPONENT_DECLARATIONS_CAPABILITY_ID,
                current_state="bounded_component_atom_and_bond_source_declarations",
                internal_execution_enabled=True,
                blocker_source="betelgeuze_engine_v2.capabilities.CAPABILITY_BLOCKERS",
            ),
            MMCIF_NONPOLY_COMPONENT_ROLE_CAPABILITY_ID: _row(
                MMCIF_NONPOLY_COMPONENT_ROLE_CAPABILITY_ID,
                current_state=(
                    "bounded_water_monoatomic_metal_and_nonmetal_ion_composition_roles"
                ),
                internal_execution_enabled=True,
                blocker_source="betelgeuze_engine_v2.capabilities.CAPABILITY_BLOCKERS",
            ),
            MMCIF_STRUCT_CONN_DECLARATIONS_CAPABILITY_ID: _row(
                MMCIF_STRUCT_CONN_DECLARATIONS_CAPABILITY_ID,
                current_state="bounded_nonpoly_struct_conn_identity_declarations",
                internal_execution_enabled=True,
                blocker_source="betelgeuze_engine_v2.capabilities.CAPABILITY_BLOCKERS",
            ),
            MMCIF_NONPOLY_ATOM_SITE_OBSERVATIONS_CAPABILITY_ID: _row(
                MMCIF_NONPOLY_ATOM_SITE_OBSERVATIONS_CAPABILITY_ID,
                current_state="bounded_nonpoly_atom_site_observation_identity_join",
                internal_execution_enabled=True,
                blocker_source="betelgeuze_engine_v2.capabilities.CAPABILITY_BLOCKERS",
            ),
            MMCIF_NONPOLY_COORDINATE_VALUES_CAPABILITY_ID: _row(
                MMCIF_NONPOLY_COORDINATE_VALUES_CAPABILITY_ID,
                current_state="bounded_nonpoly_finite_binary64_coordinate_values",
                internal_execution_enabled=True,
                blocker_source="betelgeuze_engine_v2.capabilities.CAPABILITY_BLOCKERS",
            ),
            MMCIF_NONPOLY_ATOM_SITE_SCALAR_VALUES_CAPABILITY_ID: _row(
                MMCIF_NONPOLY_ATOM_SITE_SCALAR_VALUES_CAPABILITY_ID,
                current_state="bounded_nonpoly_atom_site_scalar_value_semantics",
                internal_execution_enabled=True,
                blocker_source="betelgeuze_engine_v2.capabilities.CAPABILITY_BLOCKERS",
            ),
            MMCIF_NONPOLY_CANONICAL_TOPOLOGY_CAPABILITY_ID: _row(
                MMCIF_NONPOLY_CANONICAL_TOPOLOGY_CAPABILITY_ID,
                current_state="bounded_component_bonds_and_identity_connection_topology",
                internal_execution_enabled=True,
                blocker_source="betelgeuze_engine_v2.capabilities.CAPABILITY_BLOCKERS",
            ),
            MMCIF_NONPOLY_PREPARATION_CAPABILITY_ID: _row(
                MMCIF_NONPOLY_PREPARATION_CAPABILITY_ID,
                current_state=(
                    "bounded_neutral_acyclic_coh_graph_preparation_and_"
                    "parameterability_report"
                ),
                internal_execution_enabled=True,
                blocker_source="betelgeuze_engine_v2.capabilities.CAPABILITY_BLOCKERS",
            ),
            MMCIF_NONPOLY_HYDROGEN_COORDINATE_CAPABILITY_ID: _row(
                MMCIF_NONPOLY_HYDROGEN_COORDINATE_CAPABILITY_ID,
                current_state=(
                    "bounded_graph_bound_fixed_parent_offset_angstrom_coordinates"
                ),
                internal_execution_enabled=True,
                blocker_source="betelgeuze_engine_v2.capabilities.CAPABILITY_BLOCKERS",
            ),
            MMCIF_NONPOLY_ALL_ATOM_SYSTEM_CAPABILITY_ID: _row(
                MMCIF_NONPOLY_ALL_ATOM_SYSTEM_CAPABILITY_ID,
                current_state=(
                    "bounded_instance_canonical_all_atom_system_materialization"
                ),
                internal_execution_enabled=True,
                blocker_source="betelgeuze_engine_v2.capabilities.CAPABILITY_BLOCKERS",
            ),
            MMCIF_NONPOLY_PARAMETER_SOURCE_BINDING_CAPABILITY_ID: _row(
                MMCIF_NONPOLY_PARAMETER_SOURCE_BINDING_CAPABILITY_ID,
                current_state=(
                    "reviewed_parameter_source_identity_bound_to_bounded_"
                    "canonical_systems_without_assignment"
                ),
                internal_execution_enabled=True,
                blocker_source="betelgeuze_engine_v2.capabilities.CAPABILITY_BLOCKERS",
            ),
            MMCIF_NONPOLY_PARTIAL_CHARGE_ASSIGNMENT_CAPABILITY_ID: _row(
                MMCIF_NONPOLY_PARTIAL_CHARGE_ASSIGNMENT_CAPABILITY_ID,
                current_state=(
                    "bounded_explicit_charge_vector_application_without_"
                    "generation_or_validation"
                ),
                internal_execution_enabled=True,
                blocker_source="betelgeuze_engine_v2.capabilities.CAPABILITY_BLOCKERS",
            ),
            MMCIF_NONPOLY_ALL_ATOM_ROUND_TRIP_CAPABILITY_ID: _row(
                MMCIF_NONPOLY_ALL_ATOM_ROUND_TRIP_CAPABILITY_ID,
                current_state=("canonical_json_all_atom_identity_round_trip_receipts"),
                internal_execution_enabled=True,
                blocker_source="betelgeuze_engine_v2.capabilities.CAPABILITY_BLOCKERS",
            ),
            MMCIF_NONPOLY_PH_PROTONATION_CAPABILITY_ID: _row(
                MMCIF_NONPOLY_PH_PROTONATION_CAPABILITY_ID,
                current_state=(
                    "bounded_pubchem_cid_176_dominant_ph_state_selection_"
                    "with_abstention_and_canonical_round_trip"
                ),
                internal_execution_enabled=True,
                blocker_source="betelgeuze_engine_v2.capabilities.CAPABILITY_BLOCKERS",
            ),
            MMCIF_NONPOLY_PH_PROTONATION_CORPUS_CAPABILITY_ID: _row(
                MMCIF_NONPOLY_PH_PROTONATION_CORPUS_CAPABILITY_ID,
                current_state=(
                    "frozen_7_case_pubchem_identity_supported_abstention_"
                    "and_failure_corpus"
                ),
                internal_execution_enabled=True,
                blocker_source="betelgeuze_engine_v2.capabilities.CAPABILITY_BLOCKERS",
            ),
            MMCIF_NONPOLY_TAUTOMER_SELECTION_CAPABILITY_ID: _row(
                MMCIF_NONPOLY_TAUTOMER_SELECTION_CAPABILITY_ID,
                current_state=(
                    "bounded_pubchem_cid_177_11199_reference_canonical_"
                    "tautomer_selection_with_generated_hydrogen_transfer"
                ),
                internal_execution_enabled=True,
                blocker_source="betelgeuze_engine_v2.capabilities.CAPABILITY_BLOCKERS",
            ),
            MMCIF_NONPOLY_TAUTOMER_SELECTION_CORPUS_CAPABILITY_ID: _row(
                MMCIF_NONPOLY_TAUTOMER_SELECTION_CORPUS_CAPABILITY_ID,
                current_state=(
                    "frozen_6_case_pubchem_identity_supported_and_failure_"
                    "tautomer_corpus"
                ),
                internal_execution_enabled=True,
                blocker_source="betelgeuze_engine_v2.capabilities.CAPABILITY_BLOCKERS",
            ),
            PARAMETER_SOURCE_PROVENANCE_CAPABILITY_ID: _row(
                PARAMETER_SOURCE_PROVENANCE_CAPABILITY_ID,
                current_state=(
                    "reviewed_openff_sage_2_2_1_identity_license_scope_only"
                ),
                internal_execution_enabled=True,
                blocker_source="betelgeuze_engine_v2.capabilities.CAPABILITY_BLOCKERS",
            ),
            MMCIF_NONPOLY_PREPARATION_CORPUS_CAPABILITY_ID: _row(
                MMCIF_NONPOLY_PREPARATION_CORPUS_CAPABILITY_ID,
                current_state=(
                    "frozen_30_case_failure_complete_corpus_and_52_axis_coverage_ledger"
                ),
                internal_execution_enabled=True,
                blocker_source="betelgeuze_engine_v2.capabilities.CAPABILITY_BLOCKERS",
            ),
            PHYSICS_REGISTRY_CAPABILITY_ID: _row(
                PHYSICS_REGISTRY_CAPABILITY_ID,
                current_state="reference_terms_implemented_unvalidated",
                internal_execution_enabled=True,
                blocker_source="betelgeuze_engine_v2.capabilities.CAPABILITY_BLOCKERS",
            ),
            H5_PARAMETER_APPLICABILITY_CAPABILITY_ID: _row(
                H5_PARAMETER_APPLICABILITY_CAPABILITY_ID,
                current_state=(
                    "frozen_h5_parameter_origin_and_runtime_envelope_record_"
                    "without_parameter_set_or_scientific_validation"
                ),
                internal_execution_enabled=False,
                blocker_source="betelgeuze_engine_v2.capabilities.CAPABILITY_BLOCKERS",
            ),
            CPU_REFERENCE_VALIDATION_PROTOCOL_CAPABILITY_ID: _row(
                CPU_REFERENCE_VALIDATION_PROTOCOL_CAPABILITY_ID,
                current_state=(
                    "frozen_cpu_reference_energy_force_contract_validation_"
                    "protocol_with_closed_execution_and_fitting_gate"
                ),
                internal_execution_enabled=False,
                blocker_source="betelgeuze_engine_v2.capabilities.CAPABILITY_BLOCKERS",
            ),
            DOCKING_CAPABILITY_ID: _row(
                DOCKING_CAPABILITY_ID,
                current_state="bounded_internal_scaffold",
                internal_execution_enabled=True,
                blocker_source="betelgeuze_engine_v2.capabilities.CAPABILITY_BLOCKERS",
            ),
            BENCHMARK_CAPABILITY_ID: _row(
                BENCHMARK_CAPABILITY_ID,
                current_state="failure_complete_hmac_signed_internal_ledger",
                internal_execution_enabled=True,
                blocker_source="betelgeuze_engine_v2.capabilities.CAPABILITY_BLOCKERS",
            ),
            PUBLIC_BENCHMARK_PROTOCOL_CAPABILITY_ID: _row(
                PUBLIC_BENCHMARK_PROTOCOL_CAPABILITY_ID,
                current_state=(
                    "frozen_four_case_public_redocking_protocol_definition_"
                    "without_execution_or_results"
                ),
                internal_execution_enabled=False,
                blocker_source="betelgeuze_engine_v2.capabilities.CAPABILITY_BLOCKERS",
            ),
            EXTERNAL_BASELINE_CAPABILITY_ID: _row(
                EXTERNAL_BASELINE_CAPABILITY_ID,
                current_state="offline_work_order_and_verified_receipt_contract_ready",
                internal_execution_enabled=False,
                blocker_source="betelgeuze_engine_v2.capabilities.CAPABILITY_BLOCKERS",
            ),
            DISTRIBUTION_CAPABILITY_ID: _row(
                DISTRIBUTION_CAPABILITY_ID,
                current_state="reproducible_rc_wheel_with_spdx_sbom",
                internal_execution_enabled=True,
                blocker_source="betelgeuze_engine_v2.capabilities.CAPABILITY_BLOCKERS",
            ),
        },
        "promotion_requirements": {
            "require_strict_checkpoint_contract": True,
            "require_runtime_vocabulary_fingerprint": True,
            "require_runtime_conditioning_batch_preservation": True,
            "require_non_empty_row_level_evidence": True,
            "require_failure_rows": True,
            "require_public_holdout_evidence": True,
            "require_public_evidence_attestation": True,
            "require_reviewed_external_baseline_results": True,
            "require_validated_independent_physics": True,
            "require_gpu_parity_before_acceleration_claim": True,
            "external_state_mutated": False,
        },
    }
    return deepcopy(payload)


def require_capability_snapshot(payload: object) -> Mapping[str, object]:
    """Require exact agreement with executable capability policy."""

    if not isinstance(payload, Mapping):
        raise ValueError("capability payload must be a mapping")
    expected = capability_snapshot()
    if dict(payload) != expected:
        raise ValueError("capability snapshot drifted from executable Engine v2 policy")
    return payload


__all__ = [
    "BENCHMARK_CAPABILITY_ID",
    "CAPABILITY_BLOCKERS",
    "CAPABILITY_SCHEMA_VERSION",
    "CIF_SYNTAX_CAPABILITY_ID",
    "CPU_REFERENCE_CAPABILITY_ID",
    "CPU_REFERENCE_VALIDATION_PROTOCOL_CAPABILITY_ID",
    "DISTRIBUTION_CAPABILITY_ID",
    "DOCKING_CAPABILITY_ID",
    "ENGINE_ID",
    "EXTERNAL_BASELINE_CAPABILITY_ID",
    "H5_PARAMETER_APPLICABILITY_CAPABILITY_ID",
    "IMPLEMENTATION_STAGE",
    "MMCIF_ALTLOC_DECLARATIONS_CAPABILITY_ID",
    "MMCIF_ATOM_SITE_MODEL_POLICY_CAPABILITY_ID",
    "MMCIF_BIOLOGICAL_ASSEMBLY_POLICY_CAPABILITY_ID",
    "MMCIF_MISSING_ATOM_RESIDUE_POLICY_CAPABILITY_ID",
    "MMCIF_MODIFIED_RESIDUE_DECLARATIONS_CAPABILITY_ID",
    "MMCIF_NONPOLY_COMPONENT_DECLARATIONS_CAPABILITY_ID",
    "MMCIF_NONPOLY_COMPONENT_ROLE_CAPABILITY_ID",
    "MMCIF_NONPOLY_ATOM_SITE_OBSERVATIONS_CAPABILITY_ID",
    "MMCIF_NONPOLY_ATOM_SITE_SCALAR_VALUES_CAPABILITY_ID",
    "MMCIF_NONPOLY_COORDINATE_VALUES_CAPABILITY_ID",
    "MMCIF_NONPOLY_CANONICAL_TOPOLOGY_CAPABILITY_ID",
    "MMCIF_NONPOLY_PREPARATION_CAPABILITY_ID",
    "MMCIF_NONPOLY_PREPARATION_CORPUS_CAPABILITY_ID",
    "MMCIF_NONPOLY_IDENTITY_CAPABILITY_ID",
    "MMCIF_NONPOLY_HYDROGEN_COORDINATE_CAPABILITY_ID",
    "MMCIF_NONPOLY_ALL_ATOM_SYSTEM_CAPABILITY_ID",
    "MMCIF_NONPOLY_ALL_ATOM_ROUND_TRIP_CAPABILITY_ID",
    "MMCIF_NONPOLY_PARAMETER_SOURCE_BINDING_CAPABILITY_ID",
    "MMCIF_NONPOLY_PARTIAL_CHARGE_ASSIGNMENT_CAPABILITY_ID",
    "MMCIF_NONPOLY_PH_PROTONATION_CAPABILITY_ID",
    "MMCIF_NONPOLY_PH_PROTONATION_CORPUS_CAPABILITY_ID",
    "MMCIF_NONPOLY_TAUTOMER_SELECTION_CAPABILITY_ID",
    "MMCIF_NONPOLY_TAUTOMER_SELECTION_CORPUS_CAPABILITY_ID",
    "MMCIF_STRUCT_CONN_DECLARATIONS_CAPABILITY_ID",
    "MMCIF_SEMANTICS_CAPABILITY_ID",
    "MMCIF_ZERO_OCCUPANCY_CAPABILITY_ID",
    "PDB_INGEST_CAPABILITY_ID",
    "PARAMETER_SOURCE_PROVENANCE_CAPABILITY_ID",
    "PHYSICS_REGISTRY_CAPABILITY_ID",
    "PUBLIC_BENCHMARK_PROTOCOL_CAPABILITY_ID",
    "SDF_INGEST_CAPABILITY_ID",
    "capability_snapshot",
    "require_capability_snapshot",
]
