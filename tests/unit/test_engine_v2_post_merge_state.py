from __future__ import annotations

from pathlib import Path

import pytest


yaml = pytest.importorskip("yaml")

from betelgeuze_engine_v2.capabilities import (  # noqa: E402
    BENCHMARK_CAPABILITY_ID,
    CAPABILITY_SCHEMA_VERSION,
    CIF_SYNTAX_CAPABILITY_ID,
    EXTERNAL_BASELINE_CAPABILITY_ID,
    IMPLEMENTATION_STAGE,
    MMCIF_ALTLOC_DECLARATIONS_CAPABILITY_ID,
    MMCIF_ATOM_SITE_MODEL_POLICY_CAPABILITY_ID,
    MMCIF_BIOLOGICAL_ASSEMBLY_POLICY_CAPABILITY_ID,
    MMCIF_MISSING_ATOM_RESIDUE_POLICY_CAPABILITY_ID,
    MMCIF_MODIFIED_RESIDUE_DECLARATIONS_CAPABILITY_ID,
    MMCIF_NONPOLY_COMPONENT_DECLARATIONS_CAPABILITY_ID,
    MMCIF_NONPOLY_COMPONENT_ROLE_CAPABILITY_ID,
    MMCIF_NONPOLY_ATOM_SITE_OBSERVATIONS_CAPABILITY_ID,
    MMCIF_NONPOLY_ATOM_SITE_SCALAR_VALUES_CAPABILITY_ID,
    MMCIF_NONPOLY_COORDINATE_VALUES_CAPABILITY_ID,
    MMCIF_NONPOLY_HYDROGEN_COORDINATE_CAPABILITY_ID,
    MMCIF_NONPOLY_ALL_ATOM_SYSTEM_CAPABILITY_ID,
    MMCIF_NONPOLY_PARAMETER_SOURCE_BINDING_CAPABILITY_ID,
    MMCIF_NONPOLY_CANONICAL_TOPOLOGY_CAPABILITY_ID,
    MMCIF_NONPOLY_PREPARATION_CAPABILITY_ID,
    MMCIF_NONPOLY_PREPARATION_CORPUS_CAPABILITY_ID,
    MMCIF_NONPOLY_IDENTITY_CAPABILITY_ID,
    MMCIF_SEMANTICS_CAPABILITY_ID,
    MMCIF_STRUCT_CONN_DECLARATIONS_CAPABILITY_ID,
    MMCIF_ZERO_OCCUPANCY_CAPABILITY_ID,
    PHYSICS_REGISTRY_CAPABILITY_ID,
    PARAMETER_SOURCE_PROVENANCE_CAPABILITY_ID,
    capability_snapshot,
    require_capability_snapshot,
)


def test_capability_yaml_matches_executable_v2_schema_v4_snapshot() -> None:
    path = Path("config/independent_engine_v2_capabilities.yaml")
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert loaded == capability_snapshot()
    assert loaded["schema_version"] == CAPABILITY_SCHEMA_VERSION == 4
    assert loaded["implementation_stage"] == IMPLEMENTATION_STAGE
    assert len(loaded["capabilities"]) == 30

    rows = loaded["capabilities"]
    assert all(row["implemented"] is True for row in rows.values())
    assert all(row["reference_contract_ready"] is True for row in rows.values())
    assert all(row["calibrated"] is False for row in rows.values())
    assert all(row["scientifically_validated"] is False for row in rows.values())
    assert all(row["public_evidence_ready"] is False for row in rows.values())
    assert all(row["benchmark_validated"] is False for row in rows.values())
    assert all(row["product_qualified"] is False for row in rows.values())
    assert all(row["claim_safe"] is False for row in rows.values())
    assert all(row["customer_execution_enabled"] is False for row in rows.values())

    assert CIF_SYNTAX_CAPABILITY_ID in rows
    assert MMCIF_ALTLOC_DECLARATIONS_CAPABILITY_ID in rows
    assert MMCIF_ATOM_SITE_MODEL_POLICY_CAPABILITY_ID in rows
    assert MMCIF_BIOLOGICAL_ASSEMBLY_POLICY_CAPABILITY_ID in rows
    assert MMCIF_MISSING_ATOM_RESIDUE_POLICY_CAPABILITY_ID in rows
    assert MMCIF_MODIFIED_RESIDUE_DECLARATIONS_CAPABILITY_ID in rows
    assert MMCIF_NONPOLY_COMPONENT_DECLARATIONS_CAPABILITY_ID in rows
    assert MMCIF_NONPOLY_COMPONENT_ROLE_CAPABILITY_ID in rows
    assert MMCIF_NONPOLY_ATOM_SITE_OBSERVATIONS_CAPABILITY_ID in rows
    assert MMCIF_NONPOLY_ATOM_SITE_SCALAR_VALUES_CAPABILITY_ID in rows
    assert MMCIF_NONPOLY_CANONICAL_TOPOLOGY_CAPABILITY_ID in rows
    assert MMCIF_NONPOLY_PREPARATION_CAPABILITY_ID in rows
    assert MMCIF_NONPOLY_PREPARATION_CORPUS_CAPABILITY_ID in rows
    assert MMCIF_NONPOLY_COORDINATE_VALUES_CAPABILITY_ID in rows
    assert MMCIF_NONPOLY_HYDROGEN_COORDINATE_CAPABILITY_ID in rows
    assert MMCIF_NONPOLY_ALL_ATOM_SYSTEM_CAPABILITY_ID in rows
    assert MMCIF_NONPOLY_PARAMETER_SOURCE_BINDING_CAPABILITY_ID in rows
    assert PARAMETER_SOURCE_PROVENANCE_CAPABILITY_ID in rows
    assert MMCIF_NONPOLY_IDENTITY_CAPABILITY_ID in rows
    assert MMCIF_STRUCT_CONN_DECLARATIONS_CAPABILITY_ID in rows
    assert MMCIF_SEMANTICS_CAPABILITY_ID in rows
    assert MMCIF_ZERO_OCCUPANCY_CAPABILITY_ID in rows
    assert EXTERNAL_BASELINE_CAPABILITY_ID in rows
    assert rows[EXTERNAL_BASELINE_CAPABILITY_ID]["internal_reference_execution_enabled"] is False

    mmcif_semantics = rows[MMCIF_SEMANTICS_CAPABILITY_ID]
    assert mmcif_semantics["current_state"] == "bounded_entity_asym_polymer_sequence_projection"
    assert "atom_site_coordinate_observation_not_interpreted" in mmcif_semantics["blockers"]
    assert "mmcif_missingness_altloc_and_assembly_not_interpreted" in mmcif_semantics["blockers"]

    zero_occupancy = rows[MMCIF_ZERO_OCCUPANCY_CAPABILITY_ID]
    assert zero_occupancy["current_state"] == "bounded_source_reported_zero_occupancy_declarations"
    assert zero_occupancy["internal_reference_execution_enabled"] is True
    assert "atom_site_occupancy_not_crosschecked" in zero_occupancy["blockers"]
    assert "coordinate_observation_and_missingness_not_inferred" in zero_occupancy["blockers"]
    assert "alternate_location_population_not_interpreted" in zero_occupancy["blockers"]
    assert "mmcif_chemistry_topology_and_preparation_not_interpreted" in zero_occupancy["blockers"]

    altloc = rows[MMCIF_ALTLOC_DECLARATIONS_CAPABILITY_ID]
    assert altloc["current_state"] == "bounded_polymer_atom_site_altloc_declarations"
    assert altloc["internal_reference_execution_enabled"] is True
    assert "conformer_selection_not_implemented" in altloc["blockers"]
    assert "coordinate_and_occupancy_values_not_interpreted" in altloc["blockers"]
    assert "altloc_population_and_missingness_not_inferred" in altloc["blockers"]
    assert "mmcif_chemistry_topology_and_preparation_not_interpreted" in altloc["blockers"]

    model_policy = rows[MMCIF_ATOM_SITE_MODEL_POLICY_CAPABILITY_ID]
    assert model_policy["current_state"] == (
        "bounded_complete_atom_site_model_set_and_single_model_1_execution_policy"
    )
    assert model_policy["internal_reference_execution_enabled"] is True
    assert "multimodel_execution_not_supported" in model_policy["blockers"]
    assert "single_model_non_1_execution_not_supported" in model_policy["blockers"]
    assert "cross_category_model_references_not_reconciled" in model_policy["blockers"]
    assert (
        "model_selection_ensemble_and_trajectory_semantics_not_interpreted"
        in model_policy["blockers"]
    )

    assembly_policy = rows[MMCIF_BIOLOGICAL_ASSEMBLY_POLICY_CAPABILITY_ID]
    assert assembly_policy["current_state"] == (
        "bounded_source_declared_biological_assembly_preparation_admission"
    )
    assert assembly_policy["internal_reference_execution_enabled"] is True
    assert "source_declared_biological_assembly_expansion_not_supported" in (
        assembly_policy["blockers"]
    )
    assert "operation_matrix_vector_and_composition_not_interpreted" in (
        assembly_policy["blockers"]
    )
    assert "absence_does_not_prove_asymmetric_unit_is_biological_assembly" in (
        assembly_policy["blockers"]
    )

    missing_policy = rows[MMCIF_MISSING_ATOM_RESIDUE_POLICY_CAPABILITY_ID]
    assert missing_policy["current_state"] == (
        "bounded_source_declared_observation_gap_preparation_admission"
    )
    assert missing_policy["internal_reference_execution_enabled"] is True
    assert "source_declared_unobserved_residue_repair_not_supported" in (
        missing_policy["blockers"]
    )
    assert "source_declared_zero_occupancy_atom_repair_not_supported" in (
        missing_policy["blockers"]
    )
    assert "absence_does_not_prove_structure_complete" in (
        missing_policy["blockers"]
    )

    modified_residue = rows[MMCIF_MODIFIED_RESIDUE_DECLARATIONS_CAPABILITY_ID]
    assert modified_residue["current_state"] == (
        "bounded_source_declared_modified_polymer_residue_identity"
    )
    assert modified_residue["internal_reference_execution_enabled"] is True
    assert "atom_site_label_identity_not_crosschecked" in modified_residue["blockers"]
    assert "parent_component_chemistry_not_interpreted" in (
        modified_residue["blockers"]
    )
    assert "modified_residue_preparation_not_supported" in (
        modified_residue["blockers"]
    )

    nonpoly = rows[MMCIF_NONPOLY_IDENTITY_CAPABILITY_ID]
    assert nonpoly["current_state"] == "bounded_nonpoly_component_instance_identity"
    assert nonpoly["internal_reference_execution_enabled"] is True
    assert "source_authentication_missing" in nonpoly["blockers"]
    assert "atom_site_identity_and_coordinates_not_joined" in nonpoly["blockers"]
    assert "component_chemistry_and_roles_not_interpreted" in nonpoly["blockers"]
    assert "bond_topology_and_preparation_not_interpreted" in nonpoly["blockers"]

    component_declarations = rows[MMCIF_NONPOLY_COMPONENT_DECLARATIONS_CAPABILITY_ID]
    assert component_declarations["current_state"] == (
        "bounded_component_atom_and_bond_source_declarations"
    )
    assert component_declarations["internal_reference_execution_enabled"] is True
    assert "component_chemistry_not_interpreted" in component_declarations["blockers"]
    assert "bond_order_and_topology_not_interpreted" in component_declarations["blockers"]

    component_roles = rows[MMCIF_NONPOLY_COMPONENT_ROLE_CAPABILITY_ID]
    assert component_roles["current_state"] == (
        "bounded_water_monoatomic_metal_and_nonmetal_ion_composition_roles"
    )
    assert component_roles["internal_reference_execution_enabled"] is True
    assert "general_ligand_role_not_interpreted" in component_roles["blockers"]
    assert "cofactor_role_not_interpreted" in component_roles["blockers"]
    assert "modified_residue_role_not_interpreted" in component_roles["blockers"]
    assert "metal_coordination_chemistry_not_interpreted" in component_roles["blockers"]
    assert "monoatomic_metal_preparation_not_supported" in component_roles["blockers"]
    assert (
        "monoatomic_nonmetal_ion_preparation_not_supported"
        in component_roles["blockers"]
    )

    struct_conn = rows[MMCIF_STRUCT_CONN_DECLARATIONS_CAPABILITY_ID]
    assert struct_conn["current_state"] == (
        "bounded_nonpoly_struct_conn_identity_declarations"
    )
    assert struct_conn["internal_reference_execution_enabled"] is True
    assert "connection_type_symmetry_and_order_not_interpreted" in struct_conn["blockers"]
    assert "covalence_coordination_and_topology_not_interpreted" in struct_conn["blockers"]

    atom_site = rows[MMCIF_NONPOLY_ATOM_SITE_OBSERVATIONS_CAPABILITY_ID]
    assert atom_site["current_state"] == (
        "bounded_nonpoly_atom_site_observation_identity_join"
    )
    assert atom_site["internal_reference_execution_enabled"] is True
    assert "coordinate_tokens_not_numerically_interpreted" in atom_site["blockers"]
    assert "connection_chemistry_and_topology_not_interpreted" in atom_site["blockers"]

    coordinate_values = rows[MMCIF_NONPOLY_COORDINATE_VALUES_CAPABILITY_ID]
    assert coordinate_values["current_state"] == (
        "bounded_nonpoly_finite_binary64_coordinate_values"
    )
    assert coordinate_values["internal_reference_execution_enabled"] is True
    assert "coordinate_units_and_geometry_not_interpreted" in coordinate_values["blockers"]
    assert (
        "occupancy_b_factor_and_formal_charge_not_interpreted"
        in coordinate_values["blockers"]
    )

    scalar_values = rows[MMCIF_NONPOLY_ATOM_SITE_SCALAR_VALUES_CAPABILITY_ID]
    assert scalar_values["current_state"] == (
        "bounded_nonpoly_atom_site_scalar_value_semantics"
    )
    assert scalar_values["internal_reference_execution_enabled"] is True
    assert (
        "occupancy_population_and_altloc_semantics_not_interpreted"
        in scalar_values["blockers"]
    )
    assert "formal_charge_chemistry_not_validated" in scalar_values["blockers"]

    topology = rows[MMCIF_NONPOLY_CANONICAL_TOPOLOGY_CAPABILITY_ID]
    assert topology["current_state"] == (
        "bounded_component_bonds_and_identity_connection_topology"
    )
    assert topology["internal_reference_execution_enabled"] is True
    assert "non_identity_symmetry_not_supported" in topology["blockers"]
    assert (
        "atom_element_charge_and_aromaticity_not_crosschecked"
        in topology["blockers"]
    )

    preparation = rows[MMCIF_NONPOLY_PREPARATION_CAPABILITY_ID]
    assert preparation["current_state"] == (
        "bounded_neutral_acyclic_coh_graph_preparation_and_parameterability_report"
    )
    assert preparation["internal_reference_execution_enabled"] is True
    assert "source_declared_biological_assembly_preparation_not_supported" in (
        preparation["blockers"]
    )
    assert "source_declared_observation_gap_preparation_not_supported" in (
        preparation["blockers"]
    )
    assert "hydrogen_coordinate_geometry_not_validated" in preparation["blockers"]
    assert "reviewed_parameter_source_binding_is_separate" in (
        preparation["blockers"]
    )
    assert "canonical_all_atom_system_not_bound_to_preparation_report" in (
        preparation["blockers"]
    )

    hydrogen_coordinates = rows[MMCIF_NONPOLY_HYDROGEN_COORDINATE_CAPABILITY_ID]
    assert hydrogen_coordinates["current_state"] == (
        "bounded_graph_bound_fixed_parent_offset_angstrom_coordinates"
    )
    assert hydrogen_coordinates["internal_reference_execution_enabled"] is True
    assert "fixed_parent_offset_does_not_interpret_neighbor_geometry" in (
        hydrogen_coordinates["blockers"]
    )
    assert "hydrogen_bond_length_not_calibrated" in (
        hydrogen_coordinates["blockers"]
    )
    assert "partial_charge_assignment_not_performed" in (
        hydrogen_coordinates["blockers"]
    )

    all_atom_system = rows[MMCIF_NONPOLY_ALL_ATOM_SYSTEM_CAPABILITY_ID]
    assert all_atom_system["current_state"] == (
        "bounded_instance_canonical_all_atom_system_materialization"
    )
    assert all_atom_system["internal_reference_execution_enabled"] is True
    assert "intercomponent_covalent_connections_not_materialized" in (
        all_atom_system["blockers"]
    )
    assert "intercomponent_coordination_preserved_as_metadata_only" in (
        all_atom_system["blockers"]
    )
    assert "reviewed_parameter_source_binding_is_separate_capability" in (
        all_atom_system["blockers"]
    )
    assert "partial_charge_assignment_not_implemented" in (
        all_atom_system["blockers"]
    )
    assert "source_format_round_trip_not_implemented" in (
        all_atom_system["blockers"]
    )

    parameter_binding = rows[MMCIF_NONPOLY_PARAMETER_SOURCE_BINDING_CAPABILITY_ID]
    assert parameter_binding["current_state"] == (
        "reviewed_parameter_source_identity_bound_to_bounded_canonical_systems_"
        "without_assignment"
    )
    assert parameter_binding["internal_reference_execution_enabled"] is True
    assert "offxml_semantic_parsing_not_implemented" in parameter_binding["blockers"]
    assert "parameter_assignment_not_implemented" in parameter_binding["blockers"]
    assert "partial_charge_assignment_not_implemented" in (
        parameter_binding["blockers"]
    )

    parameter_source = rows[PARAMETER_SOURCE_PROVENANCE_CAPABILITY_ID]
    assert parameter_source["current_state"] == (
        "reviewed_openff_sage_2_2_1_identity_license_scope_only"
    )
    assert parameter_source["internal_reference_execution_enabled"] is True
    assert "source_artifact_not_bundled" in parameter_source["blockers"]
    assert "source_format_semantic_validation_missing" in (
        parameter_source["blockers"]
    )
    assert "parameter_assignment_not_implemented" in parameter_source["blockers"]
    assert "partial_charge_assignment_not_implemented" in (
        parameter_source["blockers"]
    )
    assert "applicability_domain_validation_missing" in (
        parameter_source["blockers"]
    )

    preparation_corpus = rows[MMCIF_NONPOLY_PREPARATION_CORPUS_CAPABILITY_ID]
    assert preparation_corpus["current_state"] == (
        "frozen_30_case_failure_complete_corpus_and_52_axis_coverage_ledger"
    )
    assert preparation_corpus["internal_reference_execution_enabled"] is True
    assert "synthetic_contract_corpus_only" in preparation_corpus["blockers"]
    assert "four_classified_implementation_gaps_remain" in (
        preparation_corpus["blockers"]
    )
    assert "parameter_fitting_not_authorized" in preparation_corpus["blockers"]

    physics_blockers = rows[PHYSICS_REGISTRY_CAPABILITY_ID]["blockers"]
    assert "reference_physics_scientific_validation_missing" in physics_blockers
    assert "validated_independent_physics_terms_missing" not in physics_blockers

    benchmark_blockers = rows[BENCHMARK_CAPABILITY_ID]["blockers"]
    assert "public_asymmetric_attestation_and_transparency_missing" in benchmark_blockers
    assert "artifact_signature_verification_missing" not in benchmark_blockers

    require_capability_snapshot(loaded)


def test_engine_v2_status_and_public_api_docs_state_non_promotion_boundary() -> None:
    status = Path("docs/engine_v2_status.md").read_text(encoding="utf-8")
    policy = Path("docs/engine_v2_public_api.md").read_text(encoding="utf-8")
    entrypoints = Path("docs/entrypoints.md").read_text(encoding="utf-8")

    assert IMPLEMENTATION_STAGE in status
    assert "implemented scaffold" in status
    assert "scientifically validated method" in status
    assert "Stable within an Engine API major version" in policy
    assert "Provisional submodule APIs" in policy
    assert "Independent Engine v2 reviewer" in entrypoints


def test_readmes_describe_conditional_complexity_and_v2_quick_start() -> None:
    english = Path("README.md").read_text(encoding="utf-8")
    korean = Path("README.ko.md").read_text(encoding="utf-8")

    assert "conditional bounded-degree" in english
    assert "betelgeuze-engine-v2" in english
    assert "docs/engine_v2_status.md" in english
    assert "조건부 제한 차수" in korean
    assert "betelgeuze-engine-v2" in korean
    assert "docs/engine_v2_status.md" in korean


def test_main_integration_workflow_targets_main_and_complete_v2_suite() -> None:
    source = Path(".github/workflows/ci-engine-v2-main.yml").read_text(encoding="utf-8")
    assert 'branches: ["main"]' in source
    assert 'python-version: ["3.10", "3.11", "3.12"]' in source
    for test_file in (
        "test_engine_v2_contracts_molecular.py",
        "test_engine_v2_mmcif_syntax.py",
        "test_engine_v2_mmcif_semantics.py",
        "test_engine_v2_mmcif_zero_occupancy.py",
        "test_engine_v2_mmcif_altloc_declarations.py",
        "test_engine_v2_mmcif_atom_site_model_policy.py",
        "test_engine_v2_mmcif_biological_assembly_policy.py",
        "test_engine_v2_mmcif_missing_atom_residue_policy.py",
        "test_engine_v2_mmcif_modified_residue_declarations.py",
        "test_engine_v2_mmcif_nonpoly_identity.py",
        "test_engine_v2_mmcif_nonpoly_component_declarations.py",
        "test_engine_v2_mmcif_nonpoly_component_roles.py",
        "test_engine_v2_mmcif_struct_conn_declarations.py",
        "test_engine_v2_mmcif_nonpoly_atom_site_observations.py",
        "test_engine_v2_mmcif_nonpoly_coordinate_values.py",
        "test_engine_v2_mmcif_nonpoly_hydrogen_coordinates.py",
        "test_engine_v2_mmcif_nonpoly_all_atom_systems.py",
        "test_engine_v2_parameter_source_provenance.py",
        "test_engine_v2_mmcif_nonpoly_atom_site_scalar_values.py",
        "test_engine_v2_mmcif_nonpoly_canonical_topology.py",
        "test_engine_v2_mmcif_nonpoly_preparation.py",
        "test_engine_v2_mmcif_nonpoly_preparation_corpus.py",
        "test_engine_v2_commercial_roadmap.py",
        "test_engine_v2_sparse_geometry_features.py",
        "test_engine_v2_ai_core.py",
        "test_engine_v2_periodic_energy.py",
        "test_engine_v2_orchestrator_contract.py",
        "test_engine_v2_runtime_checkpoint_contracts.py",
        "test_engine_v2_packaging_guards.py",
        "test_engine_v2_bounded_scaffolds.py",
        "test_engine_v2_post_merge_state.py",
        "test_engine_v2_input_identity.py",
        "test_engine_v2_docking_semantics.py",
        "test_engine_v2_benchmark_contracts.py",
        "test_engine_v2_reference_physics.py",
        "test_engine_v2_external_baseline.py",
    ):
        assert test_file in source
    assert "pip check" in source
    assert "check_engine_v2_architecture.py" in source
    assert "docs/independent_engine_v2_commercial_roadmap.ko.md" in source
