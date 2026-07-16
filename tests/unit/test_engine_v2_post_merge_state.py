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
    MMCIF_NONPOLY_COMPONENT_DECLARATIONS_CAPABILITY_ID,
    MMCIF_NONPOLY_IDENTITY_CAPABILITY_ID,
    MMCIF_SEMANTICS_CAPABILITY_ID,
    MMCIF_STRUCT_CONN_DECLARATIONS_CAPABILITY_ID,
    MMCIF_ZERO_OCCUPANCY_CAPABILITY_ID,
    PHYSICS_REGISTRY_CAPABILITY_ID,
    capability_snapshot,
    require_capability_snapshot,
)


def test_capability_yaml_matches_executable_v2_schema_v4_snapshot() -> None:
    path = Path("config/independent_engine_v2_capabilities.yaml")
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert loaded == capability_snapshot()
    assert loaded["schema_version"] == CAPABILITY_SCHEMA_VERSION == 4
    assert loaded["implementation_stage"] == IMPLEMENTATION_STAGE
    assert len(loaded["capabilities"]) == 15

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
    assert MMCIF_NONPOLY_COMPONENT_DECLARATIONS_CAPABILITY_ID in rows
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

    struct_conn = rows[MMCIF_STRUCT_CONN_DECLARATIONS_CAPABILITY_ID]
    assert struct_conn["current_state"] == (
        "bounded_nonpoly_struct_conn_identity_declarations"
    )
    assert struct_conn["internal_reference_execution_enabled"] is True
    assert "connection_type_symmetry_and_order_not_interpreted" in struct_conn["blockers"]
    assert "covalence_coordination_and_topology_not_interpreted" in struct_conn["blockers"]

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
        "test_engine_v2_mmcif_nonpoly_identity.py",
        "test_engine_v2_mmcif_nonpoly_component_declarations.py",
        "test_engine_v2_mmcif_struct_conn_declarations.py",
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
