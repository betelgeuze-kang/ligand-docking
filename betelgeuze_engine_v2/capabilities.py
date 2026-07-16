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
IMPLEMENTATION_STAGE = "v2_g_bounded_scientific_scaffolds"

CPU_REFERENCE_CAPABILITY_ID = "v2_cpu_reference_orchestrator"
PDB_INGEST_CAPABILITY_ID = "v2_bounded_pdb_ingest"
SDF_INGEST_CAPABILITY_ID = "v2_bounded_sdf_v2000_ingest"
CIF_SYNTAX_CAPABILITY_ID = "v2_bounded_cif_syntax"
MMCIF_SEMANTICS_CAPABILITY_ID = "v2_bounded_mmcif_semantic_projection"
MMCIF_ZERO_OCCUPANCY_CAPABILITY_ID = (
    "v2_bounded_mmcif_zero_occupancy_declarations"
)
MMCIF_ALTLOC_DECLARATIONS_CAPABILITY_ID = "v2_bounded_mmcif_altloc_declarations"
MMCIF_NONPOLY_IDENTITY_CAPABILITY_ID = "v2_bounded_mmcif_nonpoly_identity"
MMCIF_NONPOLY_COMPONENT_DECLARATIONS_CAPABILITY_ID = (
    "v2_bounded_mmcif_nonpoly_component_declarations"
)
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
PHYSICS_REGISTRY_CAPABILITY_ID = "v2_independent_physics_registry"
DOCKING_CAPABILITY_ID = "v2_bounded_docking_scaffold"
BENCHMARK_CAPABILITY_ID = "v2_benchmark_failure_row_ledger"
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
    PHYSICS_REGISTRY_CAPABILITY_ID: (
        "reference_physics_scientific_validation_missing",
        "applicability_domain_evidence_missing",
        "public_force_energy_validation_missing",
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
            PHYSICS_REGISTRY_CAPABILITY_ID: _row(
                PHYSICS_REGISTRY_CAPABILITY_ID,
                current_state="reference_terms_implemented_unvalidated",
                internal_execution_enabled=True,
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
    "DISTRIBUTION_CAPABILITY_ID",
    "DOCKING_CAPABILITY_ID",
    "ENGINE_ID",
    "EXTERNAL_BASELINE_CAPABILITY_ID",
    "IMPLEMENTATION_STAGE",
    "MMCIF_ALTLOC_DECLARATIONS_CAPABILITY_ID",
    "MMCIF_NONPOLY_COMPONENT_DECLARATIONS_CAPABILITY_ID",
    "MMCIF_NONPOLY_ATOM_SITE_OBSERVATIONS_CAPABILITY_ID",
    "MMCIF_NONPOLY_ATOM_SITE_SCALAR_VALUES_CAPABILITY_ID",
    "MMCIF_NONPOLY_COORDINATE_VALUES_CAPABILITY_ID",
    "MMCIF_NONPOLY_CANONICAL_TOPOLOGY_CAPABILITY_ID",
    "MMCIF_NONPOLY_IDENTITY_CAPABILITY_ID",
    "MMCIF_STRUCT_CONN_DECLARATIONS_CAPABILITY_ID",
    "MMCIF_SEMANTICS_CAPABILITY_ID",
    "MMCIF_ZERO_OCCUPANCY_CAPABILITY_ID",
    "PDB_INGEST_CAPABILITY_ID",
    "PHYSICS_REGISTRY_CAPABILITY_ID",
    "SDF_INGEST_CAPABILITY_ID",
    "capability_snapshot",
    "require_capability_snapshot",
]
