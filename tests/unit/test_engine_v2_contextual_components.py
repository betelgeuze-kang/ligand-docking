from __future__ import annotations

from dataclasses import replace
import json

import pytest
import torch

from betelgeuze_engine_v2.molecular import contextual_components as inventory_module
from betelgeuze_engine_v2.molecular.contextual_components import (
    CANONICAL_MARKER_NOT_OBSERVED_STATUS,
    CANONICAL_MARKER_OBSERVED_STATUS,
    CONTEXTUAL_COMPONENT_INVENTORY_BLOCKERS,
    CONTEXTUAL_COMPONENT_INVENTORY_CLAIM_SCOPE,
    CONTEXTUAL_COMPONENT_INVENTORY_SCHEMA_ID,
    CONTEXTUAL_COMPONENT_INVENTORY_SCHEMA_VERSION,
    CONTEXTUAL_COMPONENT_SOURCE_AUTHENTICATION_STATUS,
    CONTEXTUAL_COMPONENT_UNASSESSED_STATUS,
    ContextualComponentInventoryReport,
    analyze_contextual_component_inventory,
)
from betelgeuze_engine_v2.molecular.models import (
    AllAtomSystem,
    Atom,
    Bond,
    Chain,
    Residue,
    StructureProvenance,
)
from betelgeuze_engine_v2.molecular.preparation import (
    PREPARATION_POLICY_ID,
    PREPARATION_REPORT_SCHEMA_VERSION,
    PreparationCoverageLimitError,
    analyze_molecular_preparation,
)
from betelgeuze_engine_v2.molecular import preparation as preparation_module
from betelgeuze_engine_v2.molecular.serialization import (
    canonical_all_atom_systems_equal,
    deserialize_all_atom_system,
    serialize_all_atom_system,
)
from betelgeuze_engine_v2.molecular.topology import (
    CANONICAL_TOPOLOGY_SCHEMA_ID,
    canonical_topology_sha256,
)


def _context_system() -> AllAtomSystem:
    atoms = (
        Atom(0, "O", "O", 8, 0),
        Atom(1, "H1", "H", 1, 0),
        Atom(2, "H2", "H", 1, 0),
        Atom(3, "NA", "Na", 11, 1, formal_charge=1),
        Atom(4, "ZN", "Zn", 30, 2, formal_charge=2),
        Atom(5, "FE", "Fe", 26, 3),
        Atom(
            6,
            "N1",
            "N",
            7,
            3,
            formal_charge=0,
            formal_charge_known=False,
        ),
        Atom(7, "CE", "C", 6, 4),
        Atom(8, "SE", "Se", 34, 4),
    )
    residues = (
        Residue(0, "HOH", 0, 1, (0, 1, 2), entity_type="water", hetero=True),
        Residue(
            1,
            "NA",
            0,
            2,
            (3,),
            entity_type="non_polymer",
            hetero=True,
        ),
        Residue(
            2,
            "ZN",
            0,
            3,
            (4,),
            entity_type="non_polymer",
            hetero=True,
        ),
        Residue(
            3,
            "HEM",
            0,
            4,
            (5, 6),
            entity_type="non_polymer",
            hetero=True,
        ),
        Residue(
            4,
            "MSE",
            0,
            5,
            (7, 8),
            entity_type="polymer",
            hetero=True,
        ),
    )
    return AllAtomSystem(
        system_id="contextual-component-observations",
        atoms=atoms,
        bonds=(
            Bond(0, 0, 1, order=1.0),
            Bond(1, 0, 2, order=1.0),
            Bond(2, 5, 6, order=1.0),
            Bond(3, 7, 8, order=1.0),
        ),
        residues=residues,
        chains=(Chain(0, "A", (0, 1, 2, 3, 4)),),
        coordinates=torch.zeros((1, len(atoms), 3), dtype=torch.float64),
        provenance=StructureProvenance(
            source_format="unit",
            source_id="manual-context-components",
            source_sha256="a" * 64,
            parser_name="manual-test-builder",
            parser_version="1",
        ),
    )


def test_inventory_is_source_topology_and_preparation_bound() -> None:
    system = _context_system()
    report = analyze_contextual_component_inventory(system)
    preparation = analyze_molecular_preparation(system)
    payload = report.to_dict()

    assert payload["schema_id"] == CONTEXTUAL_COMPONENT_INVENTORY_SCHEMA_ID
    assert (
        payload["schema_version"]
        == CONTEXTUAL_COMPONENT_INVENTORY_SCHEMA_VERSION
        == "1.0.0"
    )
    assert report.system_schema_id == system.schema_id
    assert report.source_format == "unit"
    assert report.source_sha256 == "a" * 64
    assert report.source_digest_available is True
    assert report.source_authentication_status == (
        CONTEXTUAL_COMPONENT_SOURCE_AUTHENTICATION_STATUS
    )
    assert report.parser_pedigree_id == "unrecognized"
    assert report.parser_observation_self_consistent is False
    assert report.canonical_topology_schema_id == CANONICAL_TOPOLOGY_SCHEMA_ID
    assert report.canonical_topology_sha256 == canonical_topology_sha256(system)
    assert report.preparation_report_schema_version == (
        PREPARATION_REPORT_SCHEMA_VERSION
    )
    assert report.preparation_policy_id == PREPARATION_POLICY_ID
    assert report.preparation_report_sha256 == preparation.report_sha256
    assert report.preparation_report == preparation
    assert report.atom_count == 9
    assert report.residue_count == 5
    assert CONTEXTUAL_COMPONENT_INVENTORY_CLAIM_SCOPE == (
        "canonical_component_observation_only"
    )
    assert payload["claim_scope"] == CONTEXTUAL_COMPONENT_INVENTORY_CLAIM_SCOPE
    assert json.loads(json.dumps(payload, sort_keys=True)) == payload
    assert len(report.report_sha256) == 64
    assert analyze_contextual_component_inventory(system).to_dict() == payload
    assert report.matches_system(system) is True


@pytest.mark.parametrize(
    ("limit_name", "count_attribute", "expected_code"),
    [
        ("MAX_PREPARATION_AUDIT_ATOMS", "atoms", "atom_limit_exceeded"),
        ("MAX_PREPARATION_AUDIT_BONDS", "bonds", "bond_limit_exceeded"),
        (
            "MAX_PREPARATION_AUDIT_RESIDUES",
            "residues",
            "residue_limit_exceeded",
        ),
        ("MAX_PREPARATION_AUDIT_CHAINS", "chains", "chain_limit_exceeded"),
    ],
)
def test_contextual_inventory_propagates_preparation_resource_limits(
    monkeypatch: pytest.MonkeyPatch,
    limit_name: str,
    count_attribute: str,
    expected_code: str,
) -> None:
    system = _context_system()
    monkeypatch.setattr(
        preparation_module,
        limit_name,
        len(getattr(system, count_attribute)) - 1,
    )

    with pytest.raises(PreparationCoverageLimitError) as exc_info:
        analyze_contextual_component_inventory(system)
    assert exc_info.value.code == expected_code


def test_contextual_matches_system_propagates_preparation_resource_limits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    system = _context_system()
    report = analyze_contextual_component_inventory(system)
    monkeypatch.setattr(
        preparation_module,
        "MAX_PREPARATION_AUDIT_ATOMS",
        len(system.atoms) - 1,
    )

    with pytest.raises(PreparationCoverageLimitError) as exc_info:
        report.matches_system(system)
    assert exc_info.value.code == "atom_limit_exceeded"


def test_missing_source_digest_remains_explicitly_unauthenticated() -> None:
    source = _context_system()
    without_digest = replace(
        source,
        provenance=replace(source.provenance, source_sha256=""),
    )
    report = analyze_contextual_component_inventory(without_digest)

    assert report.source_sha256 is None
    assert report.source_digest_available is False
    assert report.source_authentication_status == "not_authenticated"
    assert "source_authentication_not_established" in report.blockers
    assert report.preparation_ready is False
    assert report.claim_safe is False


def test_rows_preserve_only_canonical_markers_without_role_inference() -> None:
    report = analyze_contextual_component_inventory(_context_system())
    water, sodium, zinc, heme, mse = report.components

    assert water.residue_index == 0
    assert water.residue_name == "HOH"
    assert water.entity_type == "water"
    assert water.hetero is True
    assert water.atom_indices == (0, 1, 2)
    assert water.atom_count == 3
    assert water.element_counts == (("H", 2), ("O", 1))
    assert water.formal_charge_known_count == 3
    assert water.formal_charge_unknown_count == 0
    assert water.canonical_net_formal_charge == 0
    assert water.canonical_water_entity_marker_status == (
        CANONICAL_MARKER_OBSERVED_STATUS
    )
    assert water.water_role_status == CONTEXTUAL_COMPONENT_UNASSESSED_STATUS

    for monatomic in (sodium, zinc):
        assert monatomic.atom_count == 1
        assert monatomic.formal_charge_known_count == 1
        assert monatomic.canonical_known_charged_monatomic_marker_status == (
            CANONICAL_MARKER_OBSERVED_STATUS
        )
        assert monatomic.ion_role_status == (CONTEXTUAL_COMPONENT_UNASSESSED_STATUS)
        assert monatomic.metal_role_status == (CONTEXTUAL_COMPONENT_UNASSESSED_STATUS)
        assert monatomic.oxidation_state_status == (
            CONTEXTUAL_COMPONENT_UNASSESSED_STATUS
        )
    assert sodium.canonical_net_formal_charge == 1
    assert zinc.canonical_net_formal_charge == 2

    assert heme.residue_name == "HEM"
    assert heme.entity_type == "non_polymer"
    assert heme.element_counts == (("Fe", 1), ("N", 1))
    assert heme.formal_charge_known_count == 1
    assert heme.formal_charge_unknown_count == 1
    assert heme.canonical_net_formal_charge is None
    assert heme.canonical_known_charged_monatomic_marker_status == (
        CANONICAL_MARKER_NOT_OBSERVED_STATUS
    )
    assert heme.metal_role_status == CONTEXTUAL_COMPONENT_UNASSESSED_STATUS
    assert heme.metal_coordination_status == (CONTEXTUAL_COMPONENT_UNASSESSED_STATUS)
    assert heme.cofactor_role_status == CONTEXTUAL_COMPONENT_UNASSESSED_STATUS

    assert mse.residue_name == "MSE"
    assert mse.entity_type == "polymer"
    assert mse.hetero is True
    assert mse.canonical_polymer_hetero_marker_status == (
        CANONICAL_MARKER_OBSERVED_STATUS
    )
    assert mse.modified_residue_identity_status == (
        CONTEXTUAL_COMPONENT_UNASSESSED_STATUS
    )

    for component in report.components:
        assert component.connection_context_status == (
            CONTEXTUAL_COMPONENT_UNASSESSED_STATUS
        )
        assert component.water_role_status == (CONTEXTUAL_COMPONENT_UNASSESSED_STATUS)
        assert component.ion_role_status == (CONTEXTUAL_COMPONENT_UNASSESSED_STATUS)
        assert component.cofactor_role_status == (
            CONTEXTUAL_COMPONENT_UNASSESSED_STATUS
        )


def test_report_never_promotes_context_chemistry_or_readiness() -> None:
    report = analyze_contextual_component_inventory(_context_system())

    assert report.contextual_role_status == CONTEXTUAL_COMPONENT_UNASSESSED_STATUS
    assert report.connection_context_status == (CONTEXTUAL_COMPONENT_UNASSESSED_STATUS)
    assert report.water_role_status == CONTEXTUAL_COMPONENT_UNASSESSED_STATUS
    assert report.ion_role_status == CONTEXTUAL_COMPONENT_UNASSESSED_STATUS
    assert report.metal_role_status == CONTEXTUAL_COMPONENT_UNASSESSED_STATUS
    assert report.metal_coordination_status == (CONTEXTUAL_COMPONENT_UNASSESSED_STATUS)
    assert report.oxidation_state_status == (CONTEXTUAL_COMPONENT_UNASSESSED_STATUS)
    assert report.cofactor_role_status == CONTEXTUAL_COMPONENT_UNASSESSED_STATUS
    assert report.modified_residue_identity_status == (
        CONTEXTUAL_COMPONENT_UNASSESSED_STATUS
    )
    assert report.chemistry_supported is False
    assert report.preparation_assessed is False
    assert report.preparation_ready is False
    assert report.parameterability_assessed is False
    assert report.parameterizable is False
    assert report.simulation_ready is False
    assert report.claim_safe is False
    assert report.blockers == CONTEXTUAL_COMPONENT_INVENTORY_BLOCKERS
    assert report.blockers == (
        "canonical_component_markers_are_not_contextual_role_evidence",
        "connection_context_unassessed",
        "source_authentication_not_established",
        "water_role_unassessed",
        "ion_role_unassessed",
        "metal_role_unassessed",
        "metal_coordination_unassessed",
        "oxidation_state_unassessed",
        "cofactor_role_unassessed",
        "modified_residue_identity_unassessed",
        "chemistry_support_not_established",
        "preparation_not_assessed",
        "preparation_not_ready",
        "parameterability_not_assessed",
        "parameterization_not_authorized",
        "simulation_not_authorized",
        "claim_not_authorized",
    )


def test_round_trip_preserves_inventory_and_hash() -> None:
    source = _context_system()
    restored = deserialize_all_atom_system(serialize_all_atom_system(source))

    assert canonical_all_atom_systems_equal(source, restored)
    source_report = analyze_contextual_component_inventory(source)
    restored_report = analyze_contextual_component_inventory(restored)
    assert restored_report.to_dict() == source_report.to_dict()
    assert restored_report.report_sha256 == source_report.report_sha256


def test_matches_system_detects_source_topology_and_marker_tampering() -> None:
    source = _context_system()
    report = analyze_contextual_component_inventory(source)

    changed_source = replace(
        source,
        provenance=replace(source.provenance, source_sha256="b" * 64),
    )
    assert canonical_topology_sha256(changed_source) == (
        report.canonical_topology_sha256
    )
    assert report.matches_system(changed_source) is False

    changed_charge = replace(
        source,
        atoms=(
            *source.atoms[:4],
            replace(source.atoms[4], formal_charge=0),
            *source.atoms[5:],
        ),
    )
    assert report.matches_system(changed_charge) is False

    changed_water_marker = replace(
        source,
        residues=(
            replace(source.residues[0], entity_type="non_polymer"),
            *source.residues[1:],
        ),
    )
    changed_report = analyze_contextual_component_inventory(changed_water_marker)
    assert changed_report.components[0].residue_name == "HOH"
    assert changed_report.components[0].canonical_water_entity_marker_status == (
        CANONICAL_MARKER_NOT_OBSERVED_STATUS
    )
    assert changed_report.components[0].water_role_status == (
        CONTEXTUAL_COMPONENT_UNASSESSED_STATUS
    )
    assert report.matches_system(changed_water_marker) is False

    forged_role_metadata = replace(
        source,
        metadata={"water_role": "solvent", "simulation_ready": True},
        residues=(
            replace(source.residues[0], metadata={"water_role": "solvent"}),
            *source.residues[1:],
        ),
        provenance=replace(
            source.provenance,
            preparation_ready=True,
            claim_safe=True,
        ),
    )
    assert analyze_contextual_component_inventory(forged_role_metadata).to_dict() == (
        report.to_dict()
    )
    assert report.matches_system(forged_role_metadata) is True


def test_factory_calls_fresh_preparation_and_rejects_report_injection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _context_system()
    calls: list[AllAtomSystem] = []
    original = inventory_module.analyze_molecular_preparation

    def recording_analyzer(system: AllAtomSystem):
        calls.append(system)
        return original(system)

    monkeypatch.setattr(
        inventory_module,
        "analyze_molecular_preparation",
        recording_analyzer,
    )
    report = ContextualComponentInventoryReport(source)
    assert calls == [source]
    assert report.matches_system(source) is True
    assert calls == [source, source]

    with pytest.raises(TypeError, match="unexpected keyword"):
        ContextualComponentInventoryReport(
            preparation_report=report.preparation_report,
            components=report.components,
        )
    with pytest.raises(TypeError, match="unexpected keyword"):
        replace(report, preparation_report=report.preparation_report)
    with pytest.raises(TypeError, match="unexpected keyword"):
        replace(report, claim_safe=True)
    with pytest.raises(TypeError, match="unexpected keyword"):
        replace(report, blockers=())
    with pytest.raises(TypeError, match="system must be an AllAtomSystem"):
        analyze_contextual_component_inventory("not-a-system")  # type: ignore[arg-type]


def test_component_constructor_invariants_reject_promoted_or_forged_rows() -> None:
    water, _, _, heme, _ = analyze_contextual_component_inventory(
        _context_system()
    ).components

    with pytest.raises(ValueError, match="water marker"):
        replace(
            water,
            canonical_water_entity_marker_status=(CANONICAL_MARKER_NOT_OBSERVED_STATUS),
        )
    with pytest.raises(ValueError, match="must sum to atom_count"):
        replace(water, element_counts=(("O", 1),))
    with pytest.raises(ValueError, match="known and unknown counts"):
        replace(water, formal_charge_known_count=2)
    with pytest.raises(ValueError, match="must be None"):
        replace(heme, canonical_net_formal_charge=0)
    with pytest.raises(ValueError, match="must remain unassessed"):
        replace(water, water_role_status="assigned")
    with pytest.raises(ValueError, match="must remain unassessed"):
        replace(heme, cofactor_role_status="heme_cofactor")


def test_invalid_canonical_system_is_rejected_fail_closed() -> None:
    source = _context_system()
    invalid = replace(
        source,
        residues=(
            replace(source.residues[0], atom_indices=(0, 1)),
            *source.residues[1:],
        ),
    )

    with pytest.raises(ValueError, match="valid canonical topology digest"):
        analyze_contextual_component_inventory(invalid)
