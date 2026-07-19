from __future__ import annotations

from pathlib import Path

import pytest


yaml = pytest.importorskip("yaml")

from betelgeuze_engine_v2.capabilities import (  # noqa: E402
    BENCHMARK_CAPABILITY_ID,
    CAPABILITY_SCHEMA_VERSION,
    CIF_SYNTAX_CAPABILITY_ID,
    CPU_FIXED_BORN_POLAR_SOLVATION_CAPABILITY_ID,
    CPU_MINIMIZATION_VALIDATION_PROTOCOL_CAPABILITY_ID,
    CPU_REFERENCE_IMPROPER_CONSTRAINT_CAPABILITY_ID,
    CPU_REFERENCE_MINIMIZATION_CAPABILITY_ID,
    CPU_REFERENCE_TERM_DIAGNOSTICS_CAPABILITY_ID,
    CPU_REFERENCE_VALIDATION_PROTOCOL_CAPABILITY_ID,
    EXTERNAL_BASELINE_CAPABILITY_ID,
    H5_PARAMETER_APPLICABILITY_CAPABILITY_ID,
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
    MMCIF_NONPOLY_ALL_ATOM_ROUND_TRIP_CAPABILITY_ID,
    MMCIF_NONPOLY_PARAMETER_SOURCE_BINDING_CAPABILITY_ID,
    MMCIF_NONPOLY_PARTIAL_CHARGE_ASSIGNMENT_CAPABILITY_ID,
    MMCIF_NONPOLY_PH_PROTONATION_CAPABILITY_ID,
    MMCIF_NONPOLY_PH_PROTONATION_CORPUS_CAPABILITY_ID,
    MMCIF_NONPOLY_TAUTOMER_SELECTION_CAPABILITY_ID,
    MMCIF_NONPOLY_TAUTOMER_SELECTION_CORPUS_CAPABILITY_ID,
    MMCIF_NONPOLY_CANONICAL_TOPOLOGY_CAPABILITY_ID,
    MMCIF_NONPOLY_PREPARATION_CAPABILITY_ID,
    MMCIF_NONPOLY_PREPARATION_CORPUS_CAPABILITY_ID,
    MMCIF_NONPOLY_IDENTITY_CAPABILITY_ID,
    MMCIF_SEMANTICS_CAPABILITY_ID,
    MMCIF_STRUCT_CONN_DECLARATIONS_CAPABILITY_ID,
    MMCIF_ZERO_OCCUPANCY_CAPABILITY_ID,
    PHYSICS_REGISTRY_CAPABILITY_ID,
    PARAMETER_SOURCE_PROVENANCE_CAPABILITY_ID,
    PUBLIC_BENCHMARK_PROTOCOL_CAPABILITY_ID,
    VALIDATION_PRODUCTION_EVIDENCE_CUSTODY_CAPABILITY_ID,
    capability_snapshot,
    require_capability_snapshot,
)


def test_energy_result_review_public_exports_and_shared_outcomes() -> None:
    from betelgeuze_engine_v2 import physics
    from betelgeuze_engine_v2.physics.reference_minimization_validation_result_review import (
        RESULT_REVIEW_OUTCOME_ACCEPTED as MINIMIZATION_ACCEPTED,
        RESULT_REVIEW_OUTCOME_REJECTED as MINIMIZATION_REJECTED,
    )
    from betelgeuze_engine_v2.physics.reference_validation_result_review import (
        RESULT_REVIEW_OUTCOME_ACCEPTED as ENERGY_FORCE_ACCEPTED,
        RESULT_REVIEW_OUTCOME_REJECTED as ENERGY_FORCE_REJECTED,
        __all__ as result_review_exports,
    )

    assert set(result_review_exports) <= set(physics.__all__)
    assert ENERGY_FORCE_ACCEPTED == MINIMIZATION_ACCEPTED == "accepted"
    assert ENERGY_FORCE_REJECTED == MINIMIZATION_REJECTED == "rejected"


def test_production_evidence_and_process_identity_public_exports_are_closed() -> None:
    from betelgeuze_engine_v2 import physics
    from betelgeuze_engine_v2.physics.validation_process_launch_identity import (
        __all__ as process_identity_exports,
        process_launch_identity_decision,
    )
    from betelgeuze_engine_v2.physics.validation_production_evidence_custody import (
        __all__ as custody_exports,
        validation_production_evidence_custody_contract_document,
        validation_production_evidence_custody_decision,
    )
    from betelgeuze_engine_v2.physics.validation_production_review_authorization_custody_extension import (
        FROZEN_VALIDATION_PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_CONTRACT_SHA256,
        __all__ as custody_extension_exports,
        validation_production_review_authorization_custody_extension_contract_document,
        validation_production_review_authorization_custody_extension_decision,
    )
    from betelgeuze_engine_v2.physics.validation_production_reservation_custody_extension import (
        FROZEN_VALIDATION_PRODUCTION_RESERVATION_CUSTODY_EXTENSION_CONTRACT_SHA256,
        __all__ as reservation_custody_extension_exports,
        validation_production_reservation_custody_extension_contract_document,
        validation_production_reservation_custody_extension_decision,
    )
    from betelgeuze_engine_v2.physics.validation_production_reservation_registry_proof import (
        FROZEN_VALIDATION_PRODUCTION_RESERVATION_REGISTRY_PROOF_CONTRACT_SHA256,
        __all__ as reservation_registry_proof_exports,
        validation_production_reservation_registry_proof_contract_document,
        validation_production_reservation_registry_proof_decision,
    )
    from betelgeuze_engine_v2.physics.validation_production_reservation_authenticated_head_receipt import (
        FROZEN_VALIDATION_PRODUCTION_RESERVATION_AUTHENTICATED_HEAD_RECEIPT_CONTRACT_SHA256,
        __all__ as reservation_authenticated_head_receipt_exports,
        validation_production_reservation_authenticated_head_receipt_contract_document,
        validation_production_reservation_authenticated_head_receipt_decision,
    )
    from betelgeuze_engine_v2.physics.validation_production_reservation_later_head_consistency import (
        FROZEN_VALIDATION_PRODUCTION_RESERVATION_LATER_HEAD_CONSISTENCY_CONTRACT_SHA256,
        __all__ as reservation_later_head_consistency_exports,
        validation_production_reservation_later_head_consistency_contract_document,
        validation_production_reservation_later_head_consistency_decision,
    )
    from betelgeuze_engine_v2.physics.validation_runtime_integrity_contract import (
        VALIDATION_RUNTIME_INTEGRITY_BOUND_RESERVATION_AUTHENTICATED_HEAD_RECEIPT_CONTRACT_SHA256,
        VALIDATION_RUNTIME_INTEGRITY_BOUND_RESERVATION_LATER_HEAD_CONSISTENCY_CONTRACT_SHA256,
        VALIDATION_RUNTIME_INTEGRITY_BOUND_RESERVATION_REGISTRY_PROOF_CONTRACT_SHA256,
        __all__ as runtime_integrity_exports,
        validation_runtime_integrity_contract_document,
    )

    assert set(process_identity_exports) <= set(physics.__all__)
    assert set(custody_exports) <= set(physics.__all__)
    assert set(custody_extension_exports) <= set(physics.__all__)
    assert set(reservation_custody_extension_exports) <= set(physics.__all__)
    assert set(reservation_registry_proof_exports) <= set(physics.__all__)
    assert set(reservation_authenticated_head_receipt_exports) <= set(physics.__all__)
    assert set(reservation_later_head_consistency_exports) <= set(physics.__all__)
    assert set(runtime_integrity_exports) <= set(physics.__all__)
    process_decision = process_launch_identity_decision()
    custody_contract = validation_production_evidence_custody_contract_document()
    custody_decision = validation_production_evidence_custody_decision()
    custody_extension_contract = (
        validation_production_review_authorization_custody_extension_contract_document()
    )
    custody_extension_decision = (
        validation_production_review_authorization_custody_extension_decision()
    )
    reservation_contract = (
        validation_production_reservation_custody_extension_contract_document()
    )
    reservation_decision = (
        validation_production_reservation_custody_extension_decision()
    )
    registry_proof_contract = (
        validation_production_reservation_registry_proof_contract_document()
    )
    registry_proof_decision = (
        validation_production_reservation_registry_proof_decision()
    )
    head_receipt_contract = (
        validation_production_reservation_authenticated_head_receipt_contract_document()
    )
    head_receipt_decision = (
        validation_production_reservation_authenticated_head_receipt_decision()
    )
    later_head_contract = (
        validation_production_reservation_later_head_consistency_contract_document()
    )
    later_head_decision = (
        validation_production_reservation_later_head_consistency_decision()
    )
    runtime_integrity_contract = validation_runtime_integrity_contract_document()
    assert process_decision["production_process_authenticity_established"] is False
    assert process_decision["same_tick_pid_reuse_collision_excluded"] is False
    assert custody_contract["permit"]["one_use_enforced"] is False
    assert custody_contract["custody_event"]["verified_stage_sequence"] == [
        "production_permit",
        "status_snapshot",
    ]
    assert custody_contract["custody_event"]["maximum_verified_sequence"] == 2
    assert (
        custody_contract["custody_event"]["custody_successor_uniqueness_enforced"]
        is False
    )
    assert custody_decision["production_permit_one_use_enforced"] is False
    assert custody_decision["maximum_verified_custody_sequence"] == 2
    assert custody_decision["custody_stages_after_status_snapshot_implemented"] is False
    assert custody_decision["custody_successor_uniqueness_enforced"] is False
    assert custody_decision["production_validation_results_collected"] is False
    assert custody_decision["claim_safe"] is False
    assert (
        custody_extension_contract["contract_sha256"]
        == FROZEN_VALIDATION_PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_CONTRACT_SHA256
    )
    assert custody_extension_contract["purpose"]["base_custody_v1_modified"] is False
    assert custody_extension_contract["custody_scope"]["verified_custody_sequence"] == [
        "production_permit",
        "status_snapshot",
        "pre_execution_review",
        "authorization",
    ]
    assert custody_extension_contract["custody_extension_event"][
        "implemented_sequences"
    ] == [3, 4]
    assert (
        custody_extension_contract["custody_extension_event"][
            "eligible_for_atomic_execution_reservation"
        ]
        is False
    )
    assert (
        custody_extension_decision["pre_execution_review_carrier_implemented"] is True
    )
    assert custody_extension_decision["authorization_carrier_implemented"] is True
    assert custody_extension_decision["custody_extension_event_implemented"] is True
    assert custody_extension_decision["custody_successor_uniqueness_enforced"] is False
    assert (
        custody_extension_decision["production_validation_execution_authorized"]
        is False
    )
    assert (
        custody_extension_decision["production_validation_results_collected"] is False
    )
    assert custody_extension_decision["claim_safe"] is False
    assert (
        reservation_contract["contract_sha256"]
        == FROZEN_VALIDATION_PRODUCTION_RESERVATION_CUSTODY_EXTENSION_CONTRACT_SHA256
    )
    assert (
        reservation_contract["atomic_commit"][
            "external_serializable_commit_independently_verified"
        ]
        is False
    )
    assert reservation_decision["actual_atomic_reservation_commit_present"] is False
    assert reservation_decision["permit_one_use_slot_consumed"] is False
    assert reservation_decision["custody_successor_uniqueness_enforced"] is False
    assert reservation_decision["claim_safe"] is False
    assert registry_proof_contract["contract_sha256"] == (
        FROZEN_VALIDATION_PRODUCTION_RESERVATION_REGISTRY_PROOF_CONTRACT_SHA256
    )
    assert registry_proof_contract["purpose"]["verifier_only"] is True
    assert registry_proof_contract["purpose"][
        "external_registry_backend_implemented_by_package"
    ] is False
    assert (
        runtime_integrity_contract["bound_contracts"][
            "production_reservation_registry_proof_contract_sha256"
        ]
        == VALIDATION_RUNTIME_INTEGRITY_BOUND_RESERVATION_REGISTRY_PROOF_CONTRACT_SHA256
        == FROZEN_VALIDATION_PRODUCTION_RESERVATION_REGISTRY_PROOF_CONTRACT_SHA256
    )
    assert registry_proof_decision["verifier_implemented"] is True
    assert registry_proof_decision[
        "external_registry_transaction_proof_present"
    ] is False
    assert registry_proof_decision[
        "external_serializable_registry_commit_verified"
    ] is False
    assert registry_proof_decision["permit_one_use_slot_consumed"] is False
    assert registry_proof_decision["external_registry_non_equivocation_verified"] is False
    assert registry_proof_decision["claim_safe"] is False
    assert head_receipt_contract["contract_sha256"] == (
        FROZEN_VALIDATION_PRODUCTION_RESERVATION_AUTHENTICATED_HEAD_RECEIPT_CONTRACT_SHA256
    )
    assert head_receipt_contract["purpose"]["verifier_only"] is True
    assert head_receipt_contract["purpose"][
        "strict_post_receipt_status_descendant_reverification_required"
    ] is True
    assert (
        runtime_integrity_contract["bound_contracts"][
            "production_reservation_authenticated_head_receipt_contract_sha256"
        ]
        == VALIDATION_RUNTIME_INTEGRITY_BOUND_RESERVATION_AUTHENTICATED_HEAD_RECEIPT_CONTRACT_SHA256
        == FROZEN_VALIDATION_PRODUCTION_RESERVATION_AUTHENTICATED_HEAD_RECEIPT_CONTRACT_SHA256
    )
    assert head_receipt_decision["verifier_implemented"] is True
    assert head_receipt_decision["external_authenticated_receipt_present"] is False
    assert head_receipt_decision[
        "authenticated_external_head_status_receipt_verified"
    ] is False
    assert head_receipt_decision["claim_safe"] is False
    assert later_head_contract["contract_sha256"] == (
        FROZEN_VALIDATION_PRODUCTION_RESERVATION_LATER_HEAD_CONSISTENCY_CONTRACT_SHA256
    )
    assert later_head_contract["purpose"]["verifier_only"] is True
    assert later_head_contract["purpose"][
        "global_non_equivocation_supported"
    ] is False
    assert (
        runtime_integrity_contract["bound_contracts"][
            "production_reservation_later_head_consistency_contract_sha256"
        ]
        == VALIDATION_RUNTIME_INTEGRITY_BOUND_RESERVATION_LATER_HEAD_CONSISTENCY_CONTRACT_SHA256
        == FROZEN_VALIDATION_PRODUCTION_RESERVATION_LATER_HEAD_CONSISTENCY_CONTRACT_SHA256
    )
    assert later_head_decision["verifier_implemented"] is True
    assert later_head_decision["external_consistency_proof_present"] is False
    assert later_head_decision["later_head_consistency_verified"] is False
    assert later_head_decision["external_registry_non_equivocation_verified"] is False
    assert later_head_decision["claim_safe"] is False


def test_capability_yaml_matches_executable_v2_schema_v4_snapshot() -> None:
    path = Path("config/independent_engine_v2_capabilities.yaml")
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert loaded == capability_snapshot()
    assert loaded["schema_version"] == CAPABILITY_SCHEMA_VERSION == 4
    assert loaded["implementation_stage"] == IMPLEMENTATION_STAGE
    assert len(loaded["capabilities"]) == 45

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
    assert MMCIF_NONPOLY_ALL_ATOM_ROUND_TRIP_CAPABILITY_ID in rows
    assert MMCIF_NONPOLY_PARAMETER_SOURCE_BINDING_CAPABILITY_ID in rows
    assert MMCIF_NONPOLY_PARTIAL_CHARGE_ASSIGNMENT_CAPABILITY_ID in rows
    assert MMCIF_NONPOLY_PH_PROTONATION_CAPABILITY_ID in rows
    assert MMCIF_NONPOLY_PH_PROTONATION_CORPUS_CAPABILITY_ID in rows
    assert MMCIF_NONPOLY_TAUTOMER_SELECTION_CAPABILITY_ID in rows
    assert MMCIF_NONPOLY_TAUTOMER_SELECTION_CORPUS_CAPABILITY_ID in rows
    assert PARAMETER_SOURCE_PROVENANCE_CAPABILITY_ID in rows
    assert MMCIF_NONPOLY_IDENTITY_CAPABILITY_ID in rows
    assert MMCIF_STRUCT_CONN_DECLARATIONS_CAPABILITY_ID in rows
    assert MMCIF_SEMANTICS_CAPABILITY_ID in rows
    assert MMCIF_ZERO_OCCUPANCY_CAPABILITY_ID in rows
    assert EXTERNAL_BASELINE_CAPABILITY_ID in rows
    assert PUBLIC_BENCHMARK_PROTOCOL_CAPABILITY_ID in rows
    assert H5_PARAMETER_APPLICABILITY_CAPABILITY_ID in rows
    assert CPU_REFERENCE_MINIMIZATION_CAPABILITY_ID in rows
    assert CPU_REFERENCE_TERM_DIAGNOSTICS_CAPABILITY_ID in rows
    assert CPU_REFERENCE_VALIDATION_PROTOCOL_CAPABILITY_ID in rows
    assert CPU_MINIMIZATION_VALIDATION_PROTOCOL_CAPABILITY_ID in rows
    assert VALIDATION_PRODUCTION_EVIDENCE_CUSTODY_CAPABILITY_ID in rows
    assert (
        rows[EXTERNAL_BASELINE_CAPABILITY_ID]["internal_reference_execution_enabled"]
        is False
    )
    custody_foundation = rows[VALIDATION_PRODUCTION_EVIDENCE_CUSTODY_CAPABILITY_ID]
    assert custody_foundation["internal_reference_execution_enabled"] is False
    assert custody_foundation["current_state"] == (
        "claim_closed_ed25519_permit_status_review_authorization_four_event_"
        "custody_process_identity_seq5_attestation_and_same_epoch_external_"
        "registry_proof_and_authenticated_head_status_receipt_and_later_head_"
        "consistency_verifiers_without_provisioned_receipt_registry_"
        "consistency_proof_or_global_non_equivocation"
    )
    assert (
        "final_production_carrier_family_not_implemented"
        in (custody_foundation["blockers"])
    )
    assert (
        "same_tick_pid_reuse_collision_not_excluded" in (custody_foundation["blockers"])
    )
    assert "permit_one_use_consumption_not_enforced" in custody_foundation["blockers"]
    assert (
        "custody_stages_after_status_snapshot_not_implemented"
        not in custody_foundation["blockers"]
    )
    for blocker in (
        "production_pre_execution_review_carrier_not_provisioned",
        "production_authorization_carrier_not_provisioned",
        "production_review_authorization_custody_events_not_provisioned",
        "trusted_production_review_key_not_provisioned",
        "trusted_production_authorization_key_not_provisioned",
        "environment_and_later_custody_stages_not_implemented",
        "external_serializable_reservation_registry_not_provisioned",
        "external_registry_transaction_proof_not_provisioned",
        "external_registry_backend_key_not_provisioned",
        "external_registry_head_observer_key_not_provisioned",
        "out_of_band_current_registry_head_not_provisioned",
        "authenticated_external_head_status_receipt_not_provisioned",
        "trusted_external_head_receipt_authority_key_not_provisioned",
        "caller_head_receipt_challenge_not_provisioned",
        "post_receipt_current_status_descendant_not_provisioned",
        "post_consistency_current_status_descendant_not_provisioned",
        "caller_challenge_freshness_and_one_use_not_independently_verified",
        "global_latest_registry_head_not_independently_verified",
        "global_latest_status_head_not_independently_verified",
        "later_head_consistency_proof_not_provisioned",
        "status_head_compare_and_set_not_independently_verified",
        "production_reservation_intent_not_provisioned",
        "production_atomic_reservation_commit_not_provisioned",
    ):
        assert blocker in custody_foundation["blockers"]
    assert (
        "external_custody_successor_uniqueness_not_provisioned"
        in custody_foundation["blockers"]
    )

    mmcif_semantics = rows[MMCIF_SEMANTICS_CAPABILITY_ID]
    assert (
        mmcif_semantics["current_state"]
        == "bounded_entity_asym_polymer_sequence_projection"
    )
    assert (
        "atom_site_coordinate_observation_not_interpreted"
        in mmcif_semantics["blockers"]
    )
    assert (
        "mmcif_missingness_altloc_and_assembly_not_interpreted"
        in mmcif_semantics["blockers"]
    )

    zero_occupancy = rows[MMCIF_ZERO_OCCUPANCY_CAPABILITY_ID]
    assert (
        zero_occupancy["current_state"]
        == "bounded_source_reported_zero_occupancy_declarations"
    )
    assert zero_occupancy["internal_reference_execution_enabled"] is True
    assert "atom_site_occupancy_not_crosschecked" in zero_occupancy["blockers"]
    assert (
        "coordinate_observation_and_missingness_not_inferred"
        in zero_occupancy["blockers"]
    )
    assert "alternate_location_population_not_interpreted" in zero_occupancy["blockers"]
    assert (
        "mmcif_chemistry_topology_and_preparation_not_interpreted"
        in zero_occupancy["blockers"]
    )

    altloc = rows[MMCIF_ALTLOC_DECLARATIONS_CAPABILITY_ID]
    assert altloc["current_state"] == "bounded_polymer_atom_site_altloc_declarations"
    assert altloc["internal_reference_execution_enabled"] is True
    assert "conformer_selection_not_implemented" in altloc["blockers"]
    assert "coordinate_and_occupancy_values_not_interpreted" in altloc["blockers"]
    assert "altloc_population_and_missingness_not_inferred" in altloc["blockers"]
    assert (
        "mmcif_chemistry_topology_and_preparation_not_interpreted" in altloc["blockers"]
    )

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
    assert (
        "source_declared_biological_assembly_expansion_not_supported"
        in (assembly_policy["blockers"])
    )
    assert (
        "operation_matrix_vector_and_composition_not_interpreted"
        in (assembly_policy["blockers"])
    )
    assert (
        "absence_does_not_prove_asymmetric_unit_is_biological_assembly"
        in (assembly_policy["blockers"])
    )

    missing_policy = rows[MMCIF_MISSING_ATOM_RESIDUE_POLICY_CAPABILITY_ID]
    assert missing_policy["current_state"] == (
        "bounded_source_declared_observation_gap_preparation_admission"
    )
    assert missing_policy["internal_reference_execution_enabled"] is True
    assert (
        "source_declared_unobserved_residue_repair_not_supported"
        in (missing_policy["blockers"])
    )
    assert (
        "source_declared_zero_occupancy_atom_repair_not_supported"
        in (missing_policy["blockers"])
    )
    assert "absence_does_not_prove_structure_complete" in (missing_policy["blockers"])

    modified_residue = rows[MMCIF_MODIFIED_RESIDUE_DECLARATIONS_CAPABILITY_ID]
    assert modified_residue["current_state"] == (
        "bounded_source_declared_modified_polymer_residue_identity"
    )
    assert modified_residue["internal_reference_execution_enabled"] is True
    assert "atom_site_label_identity_not_crosschecked" in modified_residue["blockers"]
    assert (
        "parent_component_chemistry_not_interpreted" in (modified_residue["blockers"])
    )
    assert (
        "modified_residue_preparation_not_supported" in (modified_residue["blockers"])
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
    assert (
        "bond_order_and_topology_not_interpreted" in component_declarations["blockers"]
    )

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
    assert (
        "connection_type_symmetry_and_order_not_interpreted" in struct_conn["blockers"]
    )
    assert (
        "covalence_coordination_and_topology_not_interpreted" in struct_conn["blockers"]
    )

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
    assert (
        "coordinate_units_and_geometry_not_interpreted" in coordinate_values["blockers"]
    )
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
        "atom_element_charge_and_aromaticity_not_crosschecked" in topology["blockers"]
    )

    preparation = rows[MMCIF_NONPOLY_PREPARATION_CAPABILITY_ID]
    assert preparation["current_state"] == (
        "bounded_neutral_acyclic_coh_graph_preparation_and_parameterability_report"
    )
    assert preparation["internal_reference_execution_enabled"] is True
    assert (
        "source_declared_biological_assembly_preparation_not_supported"
        in (preparation["blockers"])
    )
    assert (
        "source_declared_observation_gap_preparation_not_supported"
        in (preparation["blockers"])
    )
    assert "hydrogen_coordinate_geometry_not_validated" in preparation["blockers"]
    assert "reviewed_parameter_source_binding_is_separate" in (preparation["blockers"])
    assert (
        "canonical_all_atom_system_not_bound_to_preparation_report"
        in (preparation["blockers"])
    )

    hydrogen_coordinates = rows[MMCIF_NONPOLY_HYDROGEN_COORDINATE_CAPABILITY_ID]
    assert hydrogen_coordinates["current_state"] == (
        "bounded_graph_bound_fixed_parent_offset_angstrom_coordinates"
    )
    assert hydrogen_coordinates["internal_reference_execution_enabled"] is True
    assert (
        "fixed_parent_offset_does_not_interpret_neighbor_geometry"
        in (hydrogen_coordinates["blockers"])
    )
    assert "hydrogen_bond_length_not_calibrated" in (hydrogen_coordinates["blockers"])
    assert (
        "partial_charge_assignment_not_performed" in (hydrogen_coordinates["blockers"])
    )

    all_atom_system = rows[MMCIF_NONPOLY_ALL_ATOM_SYSTEM_CAPABILITY_ID]
    assert all_atom_system["current_state"] == (
        "bounded_instance_canonical_all_atom_system_materialization"
    )
    assert all_atom_system["internal_reference_execution_enabled"] is True
    assert (
        "intercomponent_covalent_connections_not_materialized"
        in (all_atom_system["blockers"])
    )
    assert (
        "intercomponent_coordination_preserved_as_metadata_only"
        in (all_atom_system["blockers"])
    )
    assert (
        "reviewed_parameter_source_binding_is_separate_capability"
        in (all_atom_system["blockers"])
    )
    assert (
        "partial_charge_assignment_is_separate_capability"
        in (all_atom_system["blockers"])
    )
    assert (
        "canonical_all_atom_round_trip_is_separate_capability"
        in (all_atom_system["blockers"])
    )

    parameter_binding = rows[MMCIF_NONPOLY_PARAMETER_SOURCE_BINDING_CAPABILITY_ID]
    assert parameter_binding["current_state"] == (
        "reviewed_parameter_source_identity_bound_to_bounded_canonical_systems_"
        "without_assignment"
    )
    assert parameter_binding["internal_reference_execution_enabled"] is True
    assert "offxml_semantic_parsing_not_implemented" in parameter_binding["blockers"]
    assert "parameter_assignment_not_implemented" in parameter_binding["blockers"]
    assert (
        "partial_charge_assignment_is_separate_capability"
        in (parameter_binding["blockers"])
    )

    partial_charge = rows[MMCIF_NONPOLY_PARTIAL_CHARGE_ASSIGNMENT_CAPABILITY_ID]
    assert partial_charge["current_state"] == (
        "bounded_explicit_charge_vector_application_without_generation_or_validation"
    )
    assert partial_charge["internal_reference_execution_enabled"] is True
    assert "explicit_charge_values_required_from_caller" in partial_charge["blockers"]
    assert "charge_generation_not_implemented" in partial_charge["blockers"]
    assert "charge_method_scientific_validation_missing" in (partial_charge["blockers"])

    round_trip = rows[MMCIF_NONPOLY_ALL_ATOM_ROUND_TRIP_CAPABILITY_ID]
    assert round_trip["current_state"] == (
        "canonical_json_all_atom_identity_round_trip_receipts"
    )
    assert round_trip["internal_reference_execution_enabled"] is True
    assert "original_mmcif_text_not_re_emitted" in round_trip["blockers"]
    assert "canonical_engine_v2_json_format_only" in round_trip["blockers"]
    assert (
        "caller_supplied_partial_charges_not_scientifically_validated"
        in (round_trip["blockers"])
    )

    ph_protonation = rows[MMCIF_NONPOLY_PH_PROTONATION_CAPABILITY_ID]
    assert ph_protonation["current_state"] == (
        "bounded_pubchem_cid_176_dominant_ph_state_selection_with_abstention_"
        "and_canonical_round_trip"
    )
    assert ph_protonation["internal_reference_execution_enabled"] is True
    assert (
        "exact_pubchem_cid_176_neutral_acetic_acid_graph_only"
        in (ph_protonation["blockers"])
    )
    assert "source_structure_identity_not_authenticated" in (ph_protonation["blockers"])
    assert (
        "ambiguous_population_abstains_below_90_percent_dominance"
        in (ph_protonation["blockers"])
    )
    assert (
        "bounded_cid_177_11199_tautomer_selection_is_separate_capability"
        in (ph_protonation["blockers"])
    )
    assert ph_protonation["scientifically_validated"] is False
    assert ph_protonation["claim_safe"] is False

    ph_corpus = rows[MMCIF_NONPOLY_PH_PROTONATION_CORPUS_CAPABILITY_ID]
    assert ph_corpus["current_state"] == (
        "frozen_7_case_pubchem_identity_supported_abstention_and_failure_corpus"
    )
    assert ph_corpus["internal_reference_execution_enabled"] is True
    assert "source_structure_identity_not_authenticated" in (ph_corpus["blockers"])
    assert "pubchem_source_specific_license_review_remains" in (ph_corpus["blockers"])
    assert (
        "tautomer_selection_evidence_is_separate_bounded_pair_corpus"
        in (ph_corpus["blockers"])
    )

    tautomer = rows[MMCIF_NONPOLY_TAUTOMER_SELECTION_CAPABILITY_ID]
    assert tautomer["current_state"] == (
        "bounded_pubchem_cid_177_11199_reference_canonical_tautomer_selection_"
        "with_generated_hydrogen_transfer"
    )
    assert tautomer["internal_reference_execution_enabled"] is True
    assert "source_structure_identity_not_authenticated" in tautomer["blockers"]
    assert "generated_hydroxyl_hydrogen_transfer_only" in tautomer["blockers"]
    assert "thermodynamic_preference_inferred" not in tautomer
    assert tautomer["scientifically_validated"] is False
    assert tautomer["claim_safe"] is False

    tautomer_corpus = rows[MMCIF_NONPOLY_TAUTOMER_SELECTION_CORPUS_CAPABILITY_ID]
    assert tautomer_corpus["current_state"] == (
        "frozen_6_case_pubchem_identity_supported_and_failure_tautomer_corpus"
    )
    assert tautomer_corpus["internal_reference_execution_enabled"] is True
    assert (
        "pubchem_source_specific_license_review_remains"
        in (tautomer_corpus["blockers"])
    )
    assert (
        "thermodynamic_and_population_evidence_missing" in (tautomer_corpus["blockers"])
    )

    parameter_source = rows[PARAMETER_SOURCE_PROVENANCE_CAPABILITY_ID]
    assert parameter_source["current_state"] == (
        "reviewed_openff_sage_2_2_1_identity_license_scope_only"
    )
    assert parameter_source["internal_reference_execution_enabled"] is True
    assert "source_artifact_not_bundled" in parameter_source["blockers"]
    assert "source_format_semantic_validation_missing" in (parameter_source["blockers"])
    assert "parameter_assignment_not_implemented" in parameter_source["blockers"]
    assert (
        "partial_charge_assignment_is_separate_capability"
        in (parameter_source["blockers"])
    )
    assert "applicability_domain_validation_missing" in (parameter_source["blockers"])

    preparation_corpus = rows[MMCIF_NONPOLY_PREPARATION_CORPUS_CAPABILITY_ID]
    assert preparation_corpus["current_state"] == (
        "frozen_30_case_failure_complete_corpus_and_52_axis_coverage_ledger"
    )
    assert preparation_corpus["internal_reference_execution_enabled"] is True
    assert (
        "synthetic_base_corpus_plus_separate_real_world_ph_and_tautomer_corpora"
        in (preparation_corpus["blockers"])
    )
    assert (
        "zero_classified_implementation_gaps_do_not_establish_scientific_readiness"
        in (preparation_corpus["blockers"])
    )
    assert "parameter_fitting_not_authorized" in preparation_corpus["blockers"]

    physics_blockers = rows[PHYSICS_REGISTRY_CAPABILITY_ID]["blockers"]
    assert "reference_physics_scientific_validation_missing" in physics_blockers
    assert "validated_independent_physics_terms_missing" not in physics_blockers

    benchmark_blockers = rows[BENCHMARK_CAPABILITY_ID]["blockers"]
    assert (
        "public_asymmetric_attestation_and_transparency_missing" in benchmark_blockers
    )
    assert "artifact_signature_verification_missing" not in benchmark_blockers

    public_protocol = rows[PUBLIC_BENCHMARK_PROTOCOL_CAPABILITY_ID]
    assert public_protocol["current_state"] == (
        "frozen_four_case_public_redocking_protocol_definition_"
        "without_execution_or_results"
    )
    assert public_protocol["internal_reference_execution_enabled"] is False
    assert "public_benchmark_not_executed" in public_protocol["blockers"]

    h5_record = rows[H5_PARAMETER_APPLICABILITY_CAPABILITY_ID]
    assert h5_record["current_state"] == (
        "frozen_h5_parameter_origin_and_runtime_envelope_record_"
        "without_parameter_set_or_scientific_validation"
    )
    assert h5_record["internal_reference_execution_enabled"] is False
    assert (
        "reviewed_sage_source_not_bound_to_runtime_parameter_values"
        in (h5_record["blockers"])
    )
    assert (
        "runtime_capacity_envelope_is_not_scientific_applicability_evidence"
        in (h5_record["blockers"])
    )
    assert "parameter_fitting_not_authorized" in h5_record["blockers"]

    minimization = rows[CPU_REFERENCE_MINIMIZATION_CAPABILITY_ID]
    assert minimization["current_state"] == (
        "bounded_deterministic_cpu_float64_steepest_descent_with_"
        "failure_ledger_and_checkpoint_restart"
    )
    assert minimization["internal_reference_execution_enabled"] is True
    assert minimization["scientifically_validated"] is False
    assert (
        "reference_minimization_not_scientifically_validated"
        in (minimization["blockers"])
    )
    assert (
        "independent_reference_minimization_evidence_missing"
        in (minimization["blockers"])
    )
    assert "public_minimization_validation_missing" in minimization["blockers"]

    diagnostics = rows[CPU_REFERENCE_TERM_DIAGNOSTICS_CAPABILITY_ID]
    assert diagnostics["current_state"] == (
        "bounded_cpu_float64_per_term_energy_central_difference_"
        "force_and_nonperiodic_virial_diagnostics"
    )
    assert diagnostics["internal_reference_execution_enabled"] is True
    assert diagnostics["scientifically_validated"] is False
    assert (
        "finite_difference_diagnostics_not_independent_scientific_validation"
        in (diagnostics["blockers"])
    )
    assert (
        "periodic_virial_cell_strain_derivative_not_implemented"
        in (diagnostics["blockers"])
    )
    assert "public_force_virial_validation_missing" in diagnostics["blockers"]

    improper_constraint = rows[CPU_REFERENCE_IMPROPER_CONSTRAINT_CAPABILITY_ID]
    assert improper_constraint["current_state"] == (
        "bounded_versioned_improper_symmetric_constraint_projection_"
        "and_constrained_minimization_checkpoint_restart"
    )
    assert improper_constraint["internal_reference_execution_enabled"] is True
    assert improper_constraint["scientifically_validated"] is False
    assert (
        "harmonic_out_of_plane_improper_not_scientifically_validated"
        in (improper_constraint["blockers"])
    )
    assert (
        "equal_weight_distance_constraints_ignore_atomic_masses"
        in (improper_constraint["blockers"])
    )
    assert (
        "equal_weight_constrained_minimization_not_scientifically_validated"
        in (improper_constraint["blockers"])
    )
    assert (
        "independent_constrained_minimization_evidence_missing"
        in (improper_constraint["blockers"])
    )

    solvation = rows[CPU_FIXED_BORN_POLAR_SOLVATION_CAPABILITY_ID]
    assert solvation["current_state"] == (
        "bounded_nonperiodic_cpu_float64_fixed_effective_radius_"
        "polar_gb_v2_evaluator_and_constrained_minimization_restart"
    )
    assert solvation["internal_reference_execution_enabled"] is True
    assert solvation["scientifically_validated"] is False
    assert "effective_born_radius_estimation_not_implemented" in (solvation["blockers"])
    assert "nonpolar_solvation_not_implemented" in solvation["blockers"]
    assert "periodic_solvation_not_supported" in solvation["blockers"]
    assert (
        "solvated_constrained_minimization_not_scientifically_validated"
        in (solvation["blockers"])
    )
    assert (
        "independent_solvated_minimization_evidence_missing" in (solvation["blockers"])
    )

    validation_protocol = rows[CPU_REFERENCE_VALIDATION_PROTOCOL_CAPABILITY_ID]
    assert validation_protocol["current_state"] == (
        "result_writer_and_independent_result_review_contract_"
        "without_production_receipt_or_review"
    )
    assert validation_protocol["internal_reference_execution_enabled"] is False
    assert "fixture_materializer_not_implemented" not in validation_protocol["blockers"]
    assert (
        "independent_analytic_oracle_not_implemented"
        not in validation_protocol["blockers"]
    )
    assert "independent_scientific_review_missing" in validation_protocol["blockers"]
    assert (
        "signed_independent_scientific_review_attestation_missing"
        in validation_protocol["blockers"]
    )
    assert (
        "trusted_independent_scientific_reviewer_key_not_provided"
        in validation_protocol["blockers"]
    )
    assert (
        "signed_execution_authorization_receipt_schema_not_frozen"
        not in validation_protocol["blockers"]
    )
    assert (
        "trusted_authorization_operator_key_not_provided"
        in validation_protocol["blockers"]
    )
    assert (
        "run_start_dependency_reverification_not_implemented"
        not in validation_protocol["blockers"]
    )
    assert (
        "authorization_nonce_not_atomically_reserved" in validation_protocol["blockers"]
    )
    assert (
        "execution_environment_contract_not_frozen"
        not in (validation_protocol["blockers"])
    )
    assert "result_receipt_contract_not_frozen" not in (validation_protocol["blockers"])
    assert "execution_environment_receipt_missing" in (validation_protocol["blockers"])
    assert "validation_runner_not_implemented" not in validation_protocol["blockers"]
    assert (
        "result_receipt_writer_not_implemented" not in (validation_protocol["blockers"])
    )
    assert (
        "production_validation_result_receipt_missing"
        in (validation_protocol["blockers"])
    )
    assert "independent_result_review_missing" in validation_protocol["blockers"]
    assert (
        "signed_independent_result_review_attestation_missing"
        in validation_protocol["blockers"]
    )
    assert (
        "trusted_independent_result_reviewer_key_not_provided"
        in validation_protocol["blockers"]
    )
    assert (
        "implementation_author_and_independent_result_reviewer_separation_not_attested"
        in validation_protocol["blockers"]
    )
    assert (
        "energy_force_upstream_symmetric_hmac_chain" in validation_protocol["blockers"]
    )
    assert "two_cpu_host_reproducibility_missing" in validation_protocol["blockers"]
    assert (
        "independent_external_implementation_comparison_missing"
        in validation_protocol["blockers"]
    )
    assert (
        "result_receipt_external_authenticity_not_established"
        in (validation_protocol["blockers"])
    )
    assert "validation_execution_not_authorized" in (validation_protocol["blockers"])
    assert "parameter_fitting_not_authorized" in (validation_protocol["blockers"])
    assert (
        "minimization_validation_protocol_frozen_but_not_executed"
        in (validation_protocol["blockers"])
    )
    minimization_protocol = rows[CPU_MINIMIZATION_VALIDATION_PROTOCOL_CAPABILITY_ID]
    assert minimization_protocol["current_state"] == (
        "failure_inclusive_complete_coordinate_trace_production_entrypoint_"
        "result_writer_and_independent_result_review_contract_without_"
        "production_result_receipt_or_review"
    )
    assert minimization_protocol["internal_reference_execution_enabled"] is False
    assert (
        "materializer_definition_is_not_validation_result_evidence"
        in (minimization_protocol["blockers"])
    )
    assert (
        "fixture_materializer_not_implemented"
        not in (minimization_protocol["blockers"])
    )
    assert (
        "independent_minimization_reference_is_not_validation_result_evidence"
        in (minimization_protocol["blockers"])
    )
    assert (
        "independent_minimization_reference_not_independently_reviewed"
        in (minimization_protocol["blockers"])
    )
    assert (
        "signed_independent_scientific_review_attestation_missing"
        in (minimization_protocol["blockers"])
    )
    assert (
        "trusted_independent_scientific_reviewer_key_not_provided"
        in (minimization_protocol["blockers"])
    )
    assert (
        "production_trust_store_not_provisioned" in (minimization_protocol["blockers"])
    )
    assert (
        "independent_minimization_reference_not_bound"
        not in (minimization_protocol["blockers"])
    )
    assert "production_result_receipt_missing" in (minimization_protocol["blockers"])
    assert (
        "signed_independent_result_review_attestation_missing"
        in (minimization_protocol["blockers"])
    )
    assert "two_cpu_host_reproducibility_missing" in (minimization_protocol["blockers"])
    assert (
        "coordinate_trace_not_retained_in_result_receipt"
        not in (minimization_protocol["blockers"])
    )
    assert (
        "trajectory_level_minimization_comparison_missing"
        in (minimization_protocol["blockers"])
    )
    assert (
        "signed_execution_authorization_receipt_schema_not_frozen"
        not in (minimization_protocol["blockers"])
    )
    assert (
        "execution_environment_receipt_missing" in (minimization_protocol["blockers"])
    )
    assert (
        "run_start_dependency_reverification_not_implemented"
        not in (minimization_protocol["blockers"])
    )
    assert (
        "validation_runner_not_implemented" not in (minimization_protocol["blockers"])
    )
    assert (
        "result_receipt_writer_not_implemented"
        not in (minimization_protocol["blockers"])
    )
    assert "scientific_validation_missing" in minimization_protocol["blockers"]
    assert (
        "posebusters_benchmark_equivalence_not_established"
        in public_protocol["blockers"]
    )
    assert "public_holdout_results_missing" in public_protocol["blockers"]

    require_capability_snapshot(loaded)


def test_engine_v2_status_and_public_api_docs_state_non_promotion_boundary() -> None:
    status = Path("docs/engine_v2_status.md").read_text(encoding="utf-8")
    policy = Path("docs/engine_v2_public_api.md").read_text(encoding="utf-8")
    entrypoints = Path("docs/entrypoints.md").read_text(encoding="utf-8")

    assert IMPLEMENTATION_STAGE in status
    assert "implemented scaffold" in status
    assert "scientifically validated method" in status
    assert "runtime-envelope record" in status
    assert "scientifically validated\n  chemical applicability domain" in status
    assert "CPU reference energy/force contract-validation protocol" in status
    assert "denies validation execution and parameter-fitting proposals" in status
    assert "Stable within an Engine API major version" in policy
    assert "Provisional submodule APIs" in policy
    assert "reference_parameter_applicability" in policy
    assert "reference_validation_protocol" in policy
    assert "reference_minimization_validation_protocol" in policy
    assert "reference_minimization_validation_materializer" in policy
    assert "reference_minimization_independent_oracle" in policy
    assert "reference_minimization_validation_artifact_binding" in policy
    assert "reference_minimization_validation_review" in policy
    assert "reference_minimization_validation_receipts" in policy
    assert "reference_minimization_validation_authorization" in policy
    assert "reference_minimization_validation_nonce_reservation" in policy
    assert "reference_minimization_validation_run_start" in policy
    assert "reference_minimization_validation_runner" in policy
    assert "reference_minimization_validation_result_writer" in policy
    assert "reference_minimization_validation_result_review" in policy
    assert "reference_validation_result_review" in policy
    assert "energy-force result-review" in policy
    assert "validation_process_launch_identity" in policy
    assert "validation_production_evidence_custody" in policy
    assert "validation_production_review_authorization_custody_extension" in policy
    assert "validation_production_reservation_custody_extension" in policy
    assert "validation_production_reservation_registry_proof" in policy
    assert "validation_production_reservation_authenticated_head_receipt" in policy
    assert "validation_production_reservation_later_head_consistency" in policy
    assert "fixed external root-owned mode-0600 trust store" in policy
    assert "child-preflighted fourteen-case run" in status
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
        "test_engine_v2_mmcif_nonpoly_parameter_source_binding.py",
        "test_engine_v2_mmcif_nonpoly_partial_charge_assignments.py",
        "test_engine_v2_mmcif_nonpoly_all_atom_round_trip.py",
        "test_engine_v2_mmcif_nonpoly_ph_protonation.py",
        "test_engine_v2_mmcif_nonpoly_ph_protonation_corpus.py",
        "test_engine_v2_mmcif_nonpoly_tautomer_selection.py",
        "test_engine_v2_mmcif_nonpoly_tautomer_selection_corpus.py",
        "test_engine_v2_parameter_source_provenance.py",
        "test_engine_v2_reference_parameter_applicability.py",
        "test_engine_v2_cpu_reference_validation_protocol.py",
        "test_engine_v2_reference_validation_artifacts.py",
        "test_engine_v2_reference_validation_review.py",
        "test_engine_v2_reference_validation_authorization.py",
        "test_engine_v2_reference_validation_receipts.py",
        "test_engine_v2_reference_validation_nonce_reservation.py",
        "test_engine_v2_reference_validation_run_start.py",
        "test_engine_v2_reference_validation_runner.py",
        "test_engine_v2_reference_validation_result_writer.py",
        "test_engine_v2_reference_validation_result_review.py",
        "test_engine_v2_validation_process_launch_identity.py",
        "test_engine_v2_validation_production_evidence_custody.py",
        "test_engine_v2_validation_production_review_authorization_custody_extension.py",
        "test_engine_v2_validation_production_reservation_custody_extension.py",
        "test_engine_v2_validation_production_reservation_registry_proof.py",
        "test_engine_v2_validation_production_reservation_authenticated_head_receipt.py",
        "test_engine_v2_validation_production_reservation_later_head_consistency.py",
        "test_engine_v2_validation_runtime_integrity_contract.py",
        "test_engine_v2_validation_legacy_contracts.py",
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
        "test_engine_v2_public_benchmark_protocol.py",
        "test_engine_v2_reference_constrained_minimization.py",
        "test_engine_v2_reference_diagnostics.py",
        "test_engine_v2_reference_forcefield_v2.py",
        "test_engine_v2_reference_minimization.py",
        "test_engine_v2_reference_physics.py",
        "test_engine_v2_reference_solvation.py",
        "test_engine_v2_reference_minimization_validation_protocol.py",
        "test_engine_v2_reference_minimization_validation_materializer.py",
        "test_engine_v2_reference_minimization_independent_oracle.py",
        "test_engine_v2_reference_minimization_validation_artifact_binding.py",
        "test_engine_v2_reference_minimization_validation_review.py",
        "test_engine_v2_reference_minimization_validation_receipts.py",
        "test_engine_v2_reference_minimization_validation_authorization.py",
        "test_engine_v2_reference_minimization_validation_nonce_reservation.py",
        "test_engine_v2_reference_minimization_validation_run_start.py",
        "test_engine_v2_reference_minimization_validation_runner.py",
        "test_engine_v2_reference_minimization_validation_result_writer.py",
        "test_engine_v2_reference_minimization_validation_result_review.py",
        "test_engine_v2_external_baseline.py",
    ):
        assert test_file in source
    assert "pip check" in source
    assert "check_engine_v2_architecture.py" in source
    assert "docs/independent_engine_v2_commercial_roadmap.ko.md" in source
    assert f'"{IMPLEMENTATION_STAGE}"' in source
    assert "FROZEN_REFERENCE_PARAMETER_APPLICABILITY_RECORD_SHA256" in source
    assert "FROZEN_CPU_REFERENCE_VALIDATION_PROTOCOL_SHA256" in source
    assert "FROZEN_REFERENCE_VALIDATION_ARTIFACT_BINDING_SHA256" in source
    assert "FROZEN_REFERENCE_VALIDATION_REVIEW_CONTRACT_SHA256" in source
    assert "FROZEN_REFERENCE_VALIDATION_AUTHORIZATION_CONTRACT_SHA256" in source
    assert "FROZEN_REFERENCE_VALIDATION_EXECUTION_ENVIRONMENT_CONTRACT_SHA256" in source
    assert "FROZEN_REFERENCE_VALIDATION_RESULT_RECEIPT_CONTRACT_SHA256" in source
    assert "FROZEN_REFERENCE_VALIDATION_NONCE_RESERVATION_CONTRACT_SHA256" in source
    assert "FROZEN_REFERENCE_VALIDATION_RUN_START_CONTRACT_SHA256" in source
    assert "FROZEN_REFERENCE_VALIDATION_RUNNER_CONTRACT_SHA256" in source
    assert "FROZEN_REFERENCE_VALIDATION_RESULT_WRITER_CONTRACT_SHA256" in source
    assert "FROZEN_REFERENCE_VALIDATION_RESULT_REVIEW_CONTRACT_SHA256" in source
    assert "FROZEN_PROCESS_LAUNCH_IDENTITY_CONTRACT_SHA256" in source
    assert "FROZEN_VALIDATION_PRODUCTION_EVIDENCE_CUSTODY_CONTRACT_SHA256" in source
    assert (
        "FROZEN_VALIDATION_PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_CONTRACT_SHA256"
        in source
    )
    assert (
        "FROZEN_VALIDATION_PRODUCTION_RESERVATION_CUSTODY_EXTENSION_CONTRACT_SHA256"
        in source
    )
    assert (
        "FROZEN_VALIDATION_PRODUCTION_RESERVATION_REGISTRY_PROOF_CONTRACT_SHA256"
        in source
    )
    assert (
        "VALIDATION_RUNTIME_INTEGRITY_BOUND_RESERVATION_REGISTRY_PROOF_CONTRACT_SHA256"
        in source
    )
    assert (
        "FROZEN_VALIDATION_PRODUCTION_RESERVATION_AUTHENTICATED_HEAD_RECEIPT_CONTRACT_SHA256"
        in source
    )
    assert (
        "VALIDATION_RUNTIME_INTEGRITY_BOUND_RESERVATION_AUTHENTICATED_HEAD_RECEIPT_CONTRACT_SHA256"
        in source
    )
    assert (
        "FROZEN_VALIDATION_PRODUCTION_RESERVATION_LATER_HEAD_CONSISTENCY_CONTRACT_SHA256"
        in source
    )
    assert (
        "VALIDATION_RUNTIME_INTEGRITY_BOUND_RESERVATION_LATER_HEAD_CONSISTENCY_CONTRACT_SHA256"
        in source
    )
    assert (
        "validation_production_review_authorization_custody_extension_decision"
        in source
    )
    assert "validation_production_reservation_custody_extension_decision" in source
    assert "validation_production_reservation_registry_proof.py" in source
    assert "validation_production_reservation_registry_proof_decision" in source
    assert "validation_production_reservation_authenticated_head_receipt" in source
    assert (
        "validation_production_reservation_authenticated_head_receipt_decision"
        in source
    )
    assert "validation_production_reservation_later_head_consistency" in source
    assert (
        "validation_production_reservation_later_head_consistency_decision"
        in source
    )
    assert "external_registry_transaction_proof_present" in source
    assert (
        "FROZEN_REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_CONTRACT_SHA256"
        in source
    )
    assert (
        "FROZEN_REFERENCE_MINIMIZATION_VALIDATION_NONCE_RESERVATION_CONTRACT_SHA256"
        in source
    )
    assert (
        "FROZEN_REFERENCE_MINIMIZATION_VALIDATION_RUN_START_CONTRACT_SHA256" in source
    )
    assert (
        "FROZEN_REFERENCE_MINIMIZATION_VALIDATION_RESULT_WRITER_CONTRACT_SHA256"
        in source
    )
    assert (
        "FROZEN_REFERENCE_MINIMIZATION_VALIDATION_RESULT_REVIEW_CONTRACT_SHA256"
        in source
    )


def test_cpu_reference_validation_workflow_covers_both_result_reviews() -> None:
    source = Path(
        ".github/workflows/ci-engine-v2-cpu-reference-validation-protocol.yml"
    ).read_text(encoding="utf-8")

    assert "test_engine_v2_reference_minimization_validation_result_review.py" in source
    assert "reference_minimization_validation_result_review.py" in source
    assert (
        "FROZEN_REFERENCE_MINIMIZATION_VALIDATION_RESULT_REVIEW_CONTRACT_SHA256"
        in source
    )
    assert "reference_minimization_validation_result_review_contract_decision" in source
    assert "test_engine_v2_reference_validation_result_review.py" in source
    assert "reference_validation_result_review.py" in source
    assert "FROZEN_REFERENCE_VALIDATION_RESULT_REVIEW_CONTRACT_SHA256" in source
    assert "reference_validation_result_review_contract_decision" in source
    assert "test_engine_v2_validation_process_launch_identity.py" in source
    assert "validation_process_launch_identity.py" in source
    assert "FROZEN_PROCESS_LAUNCH_IDENTITY_CONTRACT_SHA256" in source
    assert "test_engine_v2_validation_production_evidence_custody.py" in source
    assert "validation_production_evidence_custody.py" in source
    assert "FROZEN_VALIDATION_PRODUCTION_EVIDENCE_CUSTODY_CONTRACT_SHA256" in source
    assert (
        "test_engine_v2_validation_production_review_authorization_custody_extension.py"
        in source
    )
    assert (
        "test_engine_v2_validation_production_reservation_custody_extension.py"
        in source
    )
    assert (
        "test_engine_v2_validation_production_reservation_registry_proof.py"
        in source
    )
    assert (
        "test_engine_v2_validation_production_reservation_authenticated_head_receipt.py"
        in source
    )
    assert (
        "test_engine_v2_validation_production_reservation_later_head_consistency.py"
        in source
    )
    assert "test_engine_v2_validation_runtime_integrity_contract.py" in source
    assert "test_engine_v2_validation_legacy_contracts.py" in source
    assert "validation_production_review_authorization_custody_extension.py" in source
    assert "validation_production_reservation_custody_extension.py" in source
    assert "validation_production_reservation_registry_proof.py" in source
    assert "validation_production_reservation_authenticated_head_receipt.py" in source
    assert "validation_production_reservation_later_head_consistency.py" in source
    assert (
        "FROZEN_VALIDATION_PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_CONTRACT_SHA256"
        in source
    )
    assert (
        "validation_production_review_authorization_custody_extension_decision"
        in source
    )
    assert (
        "FROZEN_VALIDATION_PRODUCTION_RESERVATION_REGISTRY_PROOF_CONTRACT_SHA256"
        in source
    )
    assert (
        "VALIDATION_RUNTIME_INTEGRITY_BOUND_RESERVATION_REGISTRY_PROOF_CONTRACT_SHA256"
        in source
    )
    assert (
        "FROZEN_VALIDATION_PRODUCTION_RESERVATION_AUTHENTICATED_HEAD_RECEIPT_CONTRACT_SHA256"
        in source
    )
    assert (
        "VALIDATION_RUNTIME_INTEGRITY_BOUND_RESERVATION_AUTHENTICATED_HEAD_RECEIPT_CONTRACT_SHA256"
        in source
    )
    assert (
        "FROZEN_VALIDATION_PRODUCTION_RESERVATION_LATER_HEAD_CONSISTENCY_CONTRACT_SHA256"
        in source
    )
    assert (
        "VALIDATION_RUNTIME_INTEGRITY_BOUND_RESERVATION_LATER_HEAD_CONSISTENCY_CONTRACT_SHA256"
        in source
    )
    assert "validation_production_reservation_registry_proof_decision" in source
    assert (
        "validation_production_reservation_authenticated_head_receipt_decision"
        in source
    )
    assert (
        "validation_production_reservation_later_head_consistency_decision"
        in source
    )
    assert "external_registry_transaction_proof_present" in source
    assert f'"{IMPLEMENTATION_STAGE}"' in source
