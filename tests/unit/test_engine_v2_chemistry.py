from __future__ import annotations

from dataclasses import replace
import json

import pytest
import torch

from betelgeuze_engine_v2.molecular import (
    CHEMISTRY_COVERAGE_SCHEMA_VERSION,
    CANONICAL_TOPOLOGY_SCHEMA_ID,
    AllAtomSystem,
    Atom,
    Bond,
    Chain,
    ChemistryCoverageError,
    ChemistryCoverageLimitError,
    ORGANIC_GRAPH_ENCODING_INVENTORY_PROFILE_ID,
    Residue,
    StructureProvenance,
    analyze_canonical_chemistry,
    canonical_topology_sha256,
    deserialize_all_atom_system,
    require_supported_chemistry,
    serialize_all_atom_system,
)
from betelgeuze_engine_v2.molecular import chemistry as chemistry_module


def _system() -> AllAtomSystem:
    return AllAtomSystem(
        system_id="chemistry-audit",
        atoms=(
            Atom(index=0, name="C1", element="C", atomic_number=6, residue_index=0, atom_map=17),
            Atom(index=1, name="O1", element="O", atomic_number=8, residue_index=0),
            Atom(index=2, name="H1", element="H", atomic_number=1, residue_index=0),
        ),
        bonds=(
            Bond(index=0, atom_i=0, atom_j=1, order=1.0),
            Bond(index=1, atom_i=1, atom_j=2, order=1.0),
        ),
        residues=(
            Residue(
                index=0,
                name="LIG",
                chain_index=0,
                sequence_number=1,
                atom_indices=(0, 1, 2),
                entity_type="non_polymer",
                hetero=True,
            ),
        ),
        chains=(Chain(index=0, chain_id="L1", residue_indices=(0,), entity_id="L1"),),
        coordinates=torch.zeros((1, 3, 3), dtype=torch.float64),
        provenance=StructureProvenance(source_format="unit", preparation_ready=True),
    )


def _benzene() -> AllAtomSystem:
    atoms = tuple(
        Atom(
            index=index,
            name=f"C{index + 1}",
            element="C",
            atomic_number=6,
            residue_index=0,
            aromatic=True,
        )
        for index in range(6)
    )
    pairs = ((0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (0, 5))
    bonds = tuple(
        Bond(index=index, atom_i=atom_i, atom_j=atom_j, order=1.5, aromatic=True)
        for index, (atom_i, atom_j) in enumerate(pairs)
    )
    return AllAtomSystem(
        system_id="benzene-audit",
        atoms=atoms,
        bonds=bonds,
        residues=(
            Residue(
                index=0,
                name="BEN",
                chain_index=0,
                sequence_number=1,
                atom_indices=tuple(range(6)),
                entity_type="non_polymer",
                hetero=True,
            ),
        ),
        chains=(Chain(index=0, chain_id="L1", residue_indices=(0,)),),
        coordinates=torch.zeros((1, 6, 3), dtype=torch.float64),
        provenance=StructureProvenance(source_format="unit", preparation_ready=True),
    )


def test_report_is_deterministic_json_safe_and_never_promotes_chemistry() -> None:
    report = analyze_canonical_chemistry(_system())
    payload = report.to_dict()

    assert payload["schema_version"] == CHEMISTRY_COVERAGE_SCHEMA_VERSION == "1.2.0"
    assert report.profile_id == ORGANIC_GRAPH_ENCODING_INVENTORY_PROFILE_ID
    assert report.canonical_topology_schema_id == CANONICAL_TOPOLOGY_SCHEMA_ID
    assert report.canonical_topology_sha256 == canonical_topology_sha256(_system())
    assert report.canonical_topology_digest_available is True
    assert report.topology_validation_valid is True
    assert report.topology_validation_error_codes == ()
    assert report.canonical_validation_valid is True
    assert report.graph_representable is True
    assert report.chemistry_supported is False
    assert report.parameterability_assessed is False
    assert report.parameterizable is False
    assert report.claim_safe is False
    assert report.elements == ("C", "H", "O")
    assert report.element_counts == (("C", 1), ("H", 1), ("O", 1))
    assert report.atom_map_count == 1
    assert "parameter_assignment_not_implemented" in report.blockers
    assert len(report.report_sha256) == 64
    int(report.report_sha256, 16)
    assert json.loads(json.dumps(payload, sort_keys=True)) == payload
    assert analyze_canonical_chemistry(_system()).report_sha256 == report.report_sha256
    assert report.matches_system(_system()) is True
    assert replace(report, canonical_topology_sha256="0" * 64).matches_system(
        _system()
    ) is False


def test_snapshot_round_trip_preserves_core_chemistry_report() -> None:
    source = _system()
    restored = deserialize_all_atom_system(serialize_all_atom_system(source))
    assert analyze_canonical_chemistry(restored).to_dict() == analyze_canonical_chemistry(source).to_dict()


def test_report_identity_is_bound_to_full_ordered_topology_not_only_statistics() -> None:
    source = _system()
    rewired = replace(
        source,
        bonds=(
            replace(source.bonds[0], atom_j=2),
            replace(source.bonds[1], atom_i=1, atom_j=2),
        ),
    )
    source_report = analyze_canonical_chemistry(source)
    rewired_report = analyze_canonical_chemistry(rewired)

    assert source_report.atom_count == rewired_report.atom_count
    assert source_report.bond_count == rewired_report.bond_count
    assert source_report.component_count == rewired_report.component_count == 1
    assert source_report.elements == rewired_report.elements
    assert source_report.blockers == rewired_report.blockers
    assert source_report.canonical_topology_sha256 != (
        rewired_report.canonical_topology_sha256
    )
    assert source_report.report_sha256 != rewired_report.report_sha256


def test_mutable_metadata_cannot_promote_typed_chemistry_state() -> None:
    source = _system()
    forged = replace(
        source,
        metadata={
            "chemistry_supported": True,
            "parameterizable": True,
            "canonical_topology_sha256": "0" * 64,
        },
        provenance=replace(
            source.provenance,
            metadata={
                "canonical_topology_schema_id": "forged/9.9.9",
                "canonical_topology_sha256": "0" * 64,
                "coverage": {
                    "chemistry_supported": True,
                    "parameterizable": True,
                    "canonical_topology_sha256": "0" * 64,
                },
            },
        ),
    )
    baseline = analyze_canonical_chemistry(source)
    report = analyze_canonical_chemistry(forged)
    assert report.report_sha256 == baseline.report_sha256
    assert report.canonical_topology_sha256 == canonical_topology_sha256(source)
    assert report.chemistry_supported is False
    assert report.parameterizable is False

    with pytest.raises(ValueError, match="cannot promote"):
        replace(
            report,
            chemistry_supported=True,
            parameterability_assessed=True,
            parameterizable=True,
            claim_safe=True,
        )
    with pytest.raises(TypeError, match="chemistry_supported must be a boolean"):
        replace(report, chemistry_supported=0)
    with pytest.raises(ValueError, match="must match unknown_formal_charge_count"):
        replace(report, net_formal_charge_known=False)
    with pytest.raises(ValueError, match="unknown net_formal_charge must be None"):
        replace(
            report,
            unknown_formal_charge_count=1,
            net_formal_charge_known=False,
            net_formal_charge=0,
        )
    with pytest.raises(
        ValueError,
        match="canonical_topology_digest_available must match",
    ):
        replace(report, canonical_topology_sha256=None)
    with pytest.raises(ValueError, match="lowercase SHA-256"):
        replace(report, canonical_topology_sha256="٠" * 64)
    with pytest.raises(TypeError, match="atom_count must be a non-negative"):
        replace(report, atom_count=-1)
    with pytest.raises(ValueError, match="interoperable JSON integer range"):
        replace(report, atom_count=10**5000)
    with pytest.raises(ValueError, match="interoperable JSON integer range"):
        replace(report, net_formal_charge=10**5000)
    with pytest.raises(TypeError, match="system_schema_id"):
        replace(report, system_schema_id="")
    with pytest.raises(ValueError, match="canonical ordered blocker set"):
        replace(report, blockers=())
    with pytest.raises(ValueError, match="element_counts must sum"):
        replace(report, element_counts=())
    with pytest.raises(ValueError, match="cannot exceed atom_count"):
        replace(
            report,
            assigned_atom_stereo_count=2,
            unknown_atom_stereo_count=2,
        )
    with pytest.raises(ValueError, match="valid schema-2.1 topology"):
        replace(
            report,
            canonical_topology_sha256=None,
            canonical_topology_digest_available=False,
            canonical_validation_valid=False,
        )


def test_unknown_charge_duplicate_map_and_invalid_endpoint_are_reported_without_crashing() -> None:
    source = _system()
    unknown = replace(
        source,
        atoms=(replace(source.atoms[0], formal_charge_known=False), *source.atoms[1:]),
    )
    unknown_report = analyze_canonical_chemistry(unknown)
    assert unknown_report.unknown_formal_charge_count == 1
    assert unknown_report.net_formal_charge is None
    assert unknown_report.net_formal_charge_known is False
    assert "formal_charge_unknown_for_some_atoms" in unknown_report.blockers

    duplicate_map = replace(
        source,
        atoms=(source.atoms[0], replace(source.atoms[1], atom_map=17), source.atoms[2]),
    )
    duplicate_report = analyze_canonical_chemistry(duplicate_map)
    assert duplicate_report.atom_map_count == 2
    assert duplicate_report.canonical_validation_valid is False
    assert duplicate_report.graph_representable is False
    assert "atom_map_contract_invalid" in duplicate_report.blockers

    invalid_endpoint = replace(
        source,
        bonds=(replace(source.bonds[0], atom_j=99), source.bonds[1]),
    )
    invalid_report = analyze_canonical_chemistry(invalid_endpoint)
    assert invalid_report.canonical_validation_valid is False
    assert invalid_report.graph_representable is False
    assert invalid_report.canonical_topology_digest_available is False
    assert invalid_report.canonical_topology_sha256 is None
    assert "canonical_topology_digest_unavailable" in invalid_report.blockers
    assert "bond_graph_contract_invalid" in invalid_report.blockers
    with pytest.raises(ValueError, match="graph_representable"):
        replace(invalid_report, graph_representable=True)


def test_graph_representability_is_separate_from_coordinate_and_provenance_errors() -> None:
    source = _system()
    nonfinite_coordinates = replace(
        source,
        coordinates=torch.tensor(
            [[[float("nan"), 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]],
            dtype=torch.float64,
        ),
    )
    coordinate_report = analyze_canonical_chemistry(nonfinite_coordinates)
    assert coordinate_report.canonical_validation_valid is False
    assert coordinate_report.topology_validation_valid is True
    assert coordinate_report.canonical_topology_digest_available is True
    assert coordinate_report.canonical_topology_sha256 == canonical_topology_sha256(
        source
    )
    assert "canonical_topology_digest_unavailable" not in coordinate_report.blockers
    assert "nonfinite_coordinates" in coordinate_report.validation_error_codes
    assert coordinate_report.graph_representable is True

    invalid_provenance = replace(
        source,
        provenance=replace(source.provenance, source_sha256="not-a-digest"),
    )
    provenance_report = analyze_canonical_chemistry(invalid_provenance)
    assert provenance_report.canonical_validation_valid is False
    assert provenance_report.topology_validation_valid is True
    assert provenance_report.canonical_topology_sha256 == canonical_topology_sha256(
        source
    )
    assert "invalid_source_sha256" in provenance_report.validation_error_codes
    assert provenance_report.graph_representable is True

    outside_profile_bond = replace(
        source,
        bonds=(replace(source.bonds[0], order=4.0), source.bonds[1]),
    )
    outside_profile_report = analyze_canonical_chemistry(outside_profile_bond)
    assert outside_profile_report.canonical_validation_valid is True
    assert outside_profile_report.graph_representable is True
    assert "bond_order_outside_profile" in outside_profile_report.blockers

    assert chemistry_module._graph_validation_errors(
        ("nonfinite_coordinates", "future_graph_contract_error")
    ) == ("future_graph_contract_error",)


def test_non_graph_errors_preserve_distinct_topology_bound_report_identity() -> None:
    source = _system()
    rewired = replace(
        source,
        bonds=(
            replace(source.bonds[0], atom_j=2),
            replace(source.bonds[1], atom_i=1, atom_j=2),
        ),
    )
    invalid_left = replace(
        source,
        provenance=replace(source.provenance, source_sha256="invalid"),
    )
    invalid_right = replace(
        rewired,
        provenance=replace(rewired.provenance, source_sha256="invalid"),
    )
    left_report = analyze_canonical_chemistry(invalid_left)
    right_report = analyze_canonical_chemistry(invalid_right)

    assert left_report.canonical_validation_valid is False
    assert right_report.canonical_validation_valid is False
    assert left_report.topology_validation_valid is True
    assert right_report.topology_validation_valid is True
    assert left_report.canonical_topology_sha256 != (
        right_report.canonical_topology_sha256
    )
    assert left_report.report_sha256 != right_report.report_sha256


def test_report_fails_closed_when_system_schema_is_valid_but_not_digest_pinned() -> None:
    older_schema = replace(
        _system(),
        schema_id="betelgeuze.all_atom_system/2.0.0",
    )
    report = analyze_canonical_chemistry(older_schema)
    assert report.canonical_validation_valid is True
    assert report.graph_representable is True
    assert report.canonical_topology_schema_id == CANONICAL_TOPOLOGY_SCHEMA_ID
    assert report.canonical_topology_digest_available is False
    assert report.canonical_topology_sha256 is None
    assert "canonical_topology_digest_unavailable" in report.blockers


def test_profile_elements_isotopes_fragments_and_preparation_are_explicit_blockers() -> None:
    source = _system()
    metal = replace(
        source,
        atoms=(
            replace(source.atoms[0], name="ZN", element="Zn", atomic_number=30, isotope_mass_number=64),
            *source.atoms[1:],
        ),
    )
    metal_report = analyze_canonical_chemistry(metal)
    assert metal_report.graph_representable is True
    assert metal_report.outside_profile_elements == ("Zn",)
    assert "elements_outside_organic_graph_inventory_profile" in metal_report.blockers
    assert "isotope_parameter_coverage_not_assessed" in metal_report.blockers
    assert "physical_nuclide_validity_not_assessed" in metal_report.blockers

    fragmented = replace(source, bonds=())
    fragment_report = analyze_canonical_chemistry(fragmented)
    assert fragment_report.component_count == 3
    assert "disconnected_fragment_roles_not_assessed" in fragment_report.blockers

    topology_only = replace(
        source,
        coordinates=torch.empty((0, 3, 3), dtype=torch.float64),
        provenance=replace(source.provenance, preparation_ready=False),
    )
    topology_report = analyze_canonical_chemistry(topology_only)
    assert topology_report.coordinates_present is False
    assert topology_report.provenance_preparation_ready_attested is False
    assert "coordinates_missing" in topology_report.blockers
    assert "preparation_not_complete" in topology_report.blockers


def test_aromatic_cycle_is_independently_checked_but_perception_remains_blocked() -> None:
    source = _benzene()
    report = analyze_canonical_chemistry(source)
    assert report.graph_representable is True
    assert report.aromatic_atom_count == 6
    assert report.aromatic_bond_count == 6
    assert "aromaticity_perception_not_independently_available" in report.blockers
    with pytest.raises(ValueError, match="canonical ordered blocker set"):
        replace(
            report,
            blockers=tuple(
                blocker
                for blocker in report.blockers
                if blocker
                != "aromaticity_perception_not_independently_available"
            ),
        )

    tampered = replace(
        source,
        bonds=(replace(source.bonds[0], order=1.0, aromatic=False), *source.bonds[1:]),
    )
    tampered_report = analyze_canonical_chemistry(tampered)
    assert tampered_report.graph_representable is False
    assert "aromatic_cycle_contract_invalid" in tampered_report.blockers


def test_stereo_topology_eligibility_and_unknown_state_are_audited() -> None:
    source = _system()
    invalid_atom_stereo = replace(
        source,
        atoms=(replace(source.atoms[0], stereo="R"), *source.atoms[1:]),
    )
    atom_report = analyze_canonical_chemistry(invalid_atom_stereo)
    assert atom_report.assigned_atom_stereo_count == 1
    assert "stereo_topology_contract_invalid" in atom_report.blockers
    assert atom_report.graph_representable is False

    invalid_bond_stereo = replace(
        source,
        bonds=(replace(source.bonds[0], stereo="E"), source.bonds[1]),
    )
    bond_report = analyze_canonical_chemistry(invalid_bond_stereo)
    assert bond_report.assigned_bond_stereo_count == 1
    assert "stereo_topology_contract_invalid" in bond_report.blockers
    assert bond_report.graph_representable is False

    unknown = replace(
        source,
        atoms=(replace(source.atoms[0], stereo=" unknown "), *source.atoms[1:]),
    )
    unknown_report = analyze_canonical_chemistry(unknown)
    assert unknown_report.unknown_atom_stereo_count == 1
    assert "stereochemistry_incomplete_or_unknown" in unknown_report.blockers

    normalized_assigned = replace(
        source,
        atoms=(replace(source.atoms[0], stereo=" r "), *source.atoms[1:]),
    )
    normalized_report = analyze_canonical_chemistry(normalized_assigned)
    assert normalized_report.assigned_atom_stereo_count == 1
    assert "cip_assignment_not_independently_verified" in normalized_report.blockers


def test_require_supported_chemistry_is_fail_closed_and_type_checked() -> None:
    with pytest.raises(ChemistryCoverageError) as exc_info:
        require_supported_chemistry(_system())
    assert exc_info.value.report.chemistry_supported is False
    assert "parameterability_not_assessed" in exc_info.value.blockers

    with pytest.raises(TypeError, match="system must be an AllAtomSystem"):
        analyze_canonical_chemistry(object())  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="atoms must be a tuple of Atom records"):
        replace(_system(), atoms=(object(),))  # type: ignore[arg-type]


def test_chemistry_audit_resource_caps_fail_before_graph_allocation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(chemistry_module, "MAX_CHEMISTRY_AUDIT_ATOMS", 2)
    with pytest.raises(ChemistryCoverageLimitError) as exc_info:
        analyze_canonical_chemistry(_system())
    assert exc_info.value.code == "atom_limit_exceeded"

    monkeypatch.setattr(chemistry_module, "MAX_CHEMISTRY_AUDIT_ATOMS", 3)
    monkeypatch.setattr(chemistry_module, "MAX_CHEMISTRY_AUDIT_BONDS", 1)
    with pytest.raises(ChemistryCoverageLimitError) as exc_info:
        analyze_canonical_chemistry(_system())
    assert exc_info.value.code == "bond_limit_exceeded"
