from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from betelgeuze_engine_v2.molecular import preparation as preparation_module
from betelgeuze_engine_v2.molecular.applicability import (
    analyze_canonical_ingest_applicability,
)
from betelgeuze_engine_v2.molecular.mmcif_polymer_component_topology import (
    MMCIF_POLYMER_COMPONENT_TOPOLOGY_PARSER_NAME,
    MMCIF_POLYMER_COMPONENT_TOPOLOGY_PARSER_PEDIGREE_ID,
    MMCIF_POLYMER_COMPONENT_TOPOLOGY_PARSER_VERSION,
    parse_mmcif_polymer_component_topology,
)
from betelgeuze_engine_v2.molecular.observation import (
    attach_parser_observation_digest,
    attached_parser_observation_sha256_matches,
    mmcif_polymer_component_topology_preparation_inventory_sha256,
    parser_observation_document,
)
from betelgeuze_engine_v2.molecular.preparation import (
    analyze_molecular_preparation,
)
from betelgeuze_engine_v2.molecular.profile_preparation import (
    analyze_profile_local_preparation_evidence,
)
from betelgeuze_engine_v2.molecular.topology import (
    CANONICAL_TOPOLOGY_SCHEMA_ID,
    attached_canonical_topology_sha256_matches,
    canonical_topology_sha256,
)


FIXTURES = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "v2_1_mmcif_polymer_component_topology"
)
MARKER_KEY = "mmcif_polymer_component_topology"


def _system(fixture_name: str = "single_ala_like.cif"):
    return parse_mmcif_polymer_component_topology(
        (FIXTURES / fixture_name).read_bytes(),
        source_id=fixture_name,
    ).system


def _refresh_canonical_topology_digest(system: Any):
    metadata = dict(system.provenance.metadata)
    metadata["canonical_topology_schema_id"] = CANONICAL_TOPOLOGY_SCHEMA_ID
    metadata["canonical_topology_sha256"] = canonical_topology_sha256(system)
    return replace(
        system,
        provenance=replace(system.provenance, metadata=metadata),
    )


def _replace_atom_marker(system: Any, atom_index: int = 0, **updates: Any):
    atoms = list(system.atoms)
    metadata = dict(atoms[atom_index].metadata)
    marker = dict(metadata[MARKER_KEY])
    marker.update(updates)
    metadata[MARKER_KEY] = marker
    atoms[atom_index] = replace(atoms[atom_index], metadata=metadata)
    return replace(system, atoms=tuple(atoms))


def _replace_atom_metadata(system: Any, atom_index: int = 0, **updates: Any):
    atoms = list(system.atoms)
    metadata = dict(atoms[atom_index].metadata)
    metadata.update(updates)
    atoms[atom_index] = replace(atoms[atom_index], metadata=metadata)
    return replace(system, atoms=tuple(atoms))


def _replace_bond_marker(system: Any, bond_index: int = 0, **updates: Any):
    bonds = list(system.bonds)
    metadata = dict(bonds[bond_index].metadata)
    marker = dict(metadata[MARKER_KEY])
    marker.update(updates)
    metadata[MARKER_KEY] = marker
    bonds[bond_index] = replace(bonds[bond_index], metadata=metadata)
    return replace(system, bonds=tuple(bonds))


def _replace_profile_marker(system: Any, **updates: Any):
    metadata = dict(system.metadata)
    marker = dict(metadata[MARKER_KEY])
    marker.update(updates)
    metadata[MARKER_KEY] = marker
    return replace(system, metadata=metadata)


def _replace_provenance_marker(system: Any, **updates: Any):
    metadata = dict(system.provenance.metadata)
    marker = dict(metadata[MARKER_KEY])
    marker.update(updates)
    metadata[MARKER_KEY] = marker
    return replace(
        system,
        provenance=replace(system.provenance, metadata=metadata),
    )


def _replace_carrier_coverage(system: Any, **updates: Any):
    metadata = dict(system.provenance.metadata)
    coverage = dict(metadata["carrier_coverage"])
    coverage.update(updates)
    metadata["carrier_coverage"] = coverage
    return replace(
        system,
        provenance=replace(system.provenance, metadata=metadata),
    )


def _replace_mmcif_nested_ledger(system: Any, key: str, **updates: Any):
    metadata = dict(system.metadata)
    mmcif = dict(metadata["mmcif"])
    ledger = dict(mmcif[key])
    ledger.update(updates)
    mmcif[key] = ledger
    metadata["mmcif"] = mmcif
    return replace(system, metadata=metadata)


def _assert_strictly_unrecognized(system: Any) -> None:
    assert attached_canonical_topology_sha256_matches(system) is True
    assert attached_parser_observation_sha256_matches(system) is True
    report = analyze_molecular_preparation(system)
    assert report.parser_pedigree_id == "unrecognized"
    assert report.parser_observation_self_consistent is False
    assert report.preparation_assessed is False
    assert report.preparation_ready is False
    assert report.claim_safe is False


@pytest.mark.parametrize(
    ("fixture_name", "atom_count", "bond_count", "hydrogen_count"),
    [
        ("single_ala_like.cif", 6, 5, 1),
        ("single_ala_like_category_order_variant.cif", 6, 5, 1),
        ("repeated_ala_xaa_ala.cif", 22, 20, 2),
    ],
)
def test_polymer_component_topology_reaches_preparation_inventory(
    fixture_name: str,
    atom_count: int,
    bond_count: int,
    hydrogen_count: int,
) -> None:
    system = _system(fixture_name)
    report = analyze_molecular_preparation(system)
    applicability = analyze_canonical_ingest_applicability(system)
    local = analyze_profile_local_preparation_evidence(system)

    assert preparation_module._MMCIF_POLYMER_COMPONENT_TOPOLOGY_PARSER_NAME == (
        MMCIF_POLYMER_COMPONENT_TOPOLOGY_PARSER_NAME
    )
    assert preparation_module._MMCIF_POLYMER_COMPONENT_TOPOLOGY_PARSER_VERSION == (
        MMCIF_POLYMER_COMPONENT_TOPOLOGY_PARSER_VERSION
    )
    assert (
        preparation_module._MMCIF_POLYMER_COMPONENT_TOPOLOGY_PARSER_PEDIGREE_ID
        == MMCIF_POLYMER_COMPONENT_TOPOLOGY_PARSER_PEDIGREE_ID
    )
    assert attached_canonical_topology_sha256_matches(system) is True
    assert attached_parser_observation_sha256_matches(system) is True
    assert report.parser_pedigree_id == (
        "betelgeuze.mmcif_polymer_component_topology_parser/1.0.0"
    )
    assert report.parser_observation_self_consistent is True
    assert report.atom_count == atom_count
    assert report.bond_count == bond_count
    assert report.hydrogen_origin_counts == (
        ("metadata_observed_parser_source", hydrogen_count),
    )
    assert report.formal_charge_origin_counts == (
        ("metadata_observed_mmcif_chem_comp_atom", atom_count),
    )
    assert report.unknown_hydrogen_origin_count == 0
    assert report.unknown_formal_charge_count == 0
    assert report.preparation_assessed is False
    assert report.preparation_ready is False
    assert report.claim_safe is False
    assert applicability.canonical_ingest_status == "unsupported"
    assert "recognized_parser_pedigree" not in applicability.failed_constraint_codes
    assert (
        "parser_observation_self_consistent"
        not in applicability.failed_constraint_codes
    )
    assert local.profile_local_evidence_status == "not_satisfied"
    assert local.source_observed_formal_charge_count == atom_count
    assert local.preparation_assessed is False
    assert local.preparation_ready is False
    assert local.parameterability_assessed is False
    assert local.simulation_ready is False
    assert local.claim_safe is False

    profile = system.metadata[MARKER_KEY]
    assert set(profile) == (
        preparation_module._MMCIF_POLYMER_COMPONENT_TOPOLOGY_PROFILE_MARKER_KEYS
    )
    assert all(
        profile[field] is False
        for field in (
            preparation_module._MMCIF_POLYMER_COMPONENT_TOPOLOGY_FALSE_AUTHORITY_FIELDS
        )
    )
    assert all(residue.entity_type == "polymer" for residue in system.residues)
    assert all(
        set(atom.metadata[MARKER_KEY])
        == preparation_module._MMCIF_POLYMER_COMPONENT_TOPOLOGY_ATOM_MARKER_KEYS
        for atom in system.atoms
    )
    assert all(
        set(bond.metadata) == {MARKER_KEY}
        and set(bond.metadata[MARKER_KEY])
        == preparation_module._MMCIF_POLYMER_COMPONENT_TOPOLOGY_BOND_MARKER_KEYS
        for bond in system.bonds
    )
    provenance_marker = system.provenance.metadata[MARKER_KEY]
    assert provenance_marker["preparation_inventory_commitment_schema_id"] == (
        "betelgeuze.mmcif_polymer_component_topology_preparation_inventory_commitment/"
        "1.0.0"
    )
    assert provenance_marker["preparation_inventory_commitment_sha256"] == (
        mmcif_polymer_component_topology_preparation_inventory_sha256(system)
    )
    observation = parser_observation_document(system)
    assert MARKER_KEY in observation["system_markers"]
    assert MARKER_KEY in observation["provenance_markers"]


def test_stale_atom_marker_tamper_breaks_observation_binding() -> None:
    forged = _replace_atom_marker(_system(), template_ordinal=999)

    assert attached_canonical_topology_sha256_matches(forged) is True
    assert attached_parser_observation_sha256_matches(forged) is False
    report = analyze_molecular_preparation(forged)
    assert report.parser_pedigree_id == "unrecognized"
    assert report.parser_observation_self_consistent is False
    assert report.hydrogen_origin_counts == (("unknown", 1),)
    assert report.formal_charge_origin_counts == (("unclassified_known", 6),)


@pytest.mark.parametrize(
    "updates",
    [
        {"template_atom_id": "WRONG"},
        {"template_ordinal": 999},
        {"source_reported_aromatic": True},
        {"source_reported_stereo": "R"},
        {"unexpected_marker_key": False},
    ],
)
def test_coherently_rehashed_atom_marker_tamper_fails_closed(
    updates: dict[str, Any],
) -> None:
    forged = attach_parser_observation_digest(
        _replace_atom_marker(_system(), **updates)
    )
    _assert_strictly_unrecognized(forged)


@pytest.mark.parametrize(
    "updates",
    [
        {"formal_charge_interpretation": "explicit"},
        {"formal_charge_known": False},
        {"formal_charge_source": "cross_checked_atom_site_and_chem_comp_atom"},
        {"hydrogen_origin": "forged"},
    ],
)
def test_coherently_rehashed_atom_charge_or_origin_tamper_fails_closed(
    updates: dict[str, Any],
) -> None:
    atom_index = 1 if "hydrogen_origin" in updates else 0
    forged = attach_parser_observation_digest(
        _replace_atom_metadata(_system(), atom_index, **updates)
    )
    _assert_strictly_unrecognized(forged)


@pytest.mark.parametrize(
    "updates",
    [
        {"component_count": 99},
        {"bond_count": 99},
        {"preparation_ready": True},
        {"unexpected_profile_key": False},
    ],
)
def test_coherently_rehashed_profile_tamper_fails_closed(
    updates: dict[str, Any],
) -> None:
    forged = attach_parser_observation_digest(
        _replace_profile_marker(_system(), **updates)
    )
    _assert_strictly_unrecognized(forged)


@pytest.mark.parametrize(
    "updates",
    [
        {"parser_pedigree_id": "forged"},
        {"source_sha256_semantics": "forged"},
        {"carrier_evidence_semantics": "forged"},
        {"canonical_output_sha256": "0" * 63},
        {"unexpected_provenance_key": False},
    ],
)
def test_coherently_rehashed_provenance_marker_tamper_fails_closed(
    updates: dict[str, Any],
) -> None:
    forged = attach_parser_observation_digest(
        _replace_provenance_marker(_system(), **updates)
    )
    _assert_strictly_unrecognized(forged)


@pytest.mark.parametrize(
    "updates",
    [
        {"template_atom_id_1": "WRONG"},
        {"template_ordinal": 999},
        {"component_instance_residue_index": 99},
        {"source_reported_value_order": "DOUB"},
        {"source_reported_aromatic": True},
        {"source_reported_stereo": "R"},
        {"unexpected_bond_key": False},
    ],
)
def test_coherently_rehashed_bond_marker_tamper_fails_closed(
    updates: dict[str, Any],
) -> None:
    forged = attach_parser_observation_digest(
        _replace_bond_marker(_system(), **updates)
    )
    _assert_strictly_unrecognized(forged)


def test_coherently_rehashed_bond_order_tamper_fails_closed() -> None:
    system = _system()
    forged = replace(
        system,
        bonds=(replace(system.bonds[0], order=2.0), *system.bonds[1:]),
    )
    forged = attach_parser_observation_digest(
        _refresh_canonical_topology_digest(forged)
    )
    _assert_strictly_unrecognized(forged)


def test_raw_atom_site_element_mismatch_fails_after_coherent_rehash() -> None:
    system = _system()
    atom_index = next(atom.index for atom in system.atoms if atom.name == "CA")
    atoms = list(system.atoms)
    assert atoms[atom_index].element == "C"
    assert (
        atoms[atom_index].metadata["mmcif"]["atom_site"]["_atom_site.type_symbol"][
            "value"
        ]
        == "C"
    )
    atoms[atom_index] = replace(
        atoms[atom_index],
        element="N",
        atomic_number=7,
    )
    forged = replace(system, atoms=tuple(atoms))
    forged = attach_parser_observation_digest(
        _refresh_canonical_topology_digest(forged)
    )
    _assert_strictly_unrecognized(forged)


def test_raw_atom_site_group_pdb_mismatch_fails_after_coherent_rehash() -> None:
    system = _system()
    assert (
        system.atoms[0].metadata["mmcif"]["atom_site"]["_atom_site.group_pdb"]["value"]
        == "ATOM"
    )
    forged = attach_parser_observation_digest(
        _replace_atom_metadata(system, source_record="HETATM")
    )
    _assert_strictly_unrecognized(forged)


def test_commitment_rejects_count_adjusted_terminal_atom_and_bond_deletion() -> None:
    system = _system()
    removed_atom_index = len(system.atoms) - 1
    bonds = [
        bond
        for bond in system.bonds
        if removed_atom_index not in {bond.atom_i, bond.atom_j}
    ]
    residue = replace(
        system.residues[0],
        atom_indices=tuple(
            index
            for index in system.residues[0].atom_indices
            if index != removed_atom_index
        ),
    )
    profile = dict(system.metadata[MARKER_KEY])
    profile["bond_count"] = len(bonds)
    metadata = dict(system.metadata)
    mmcif = dict(metadata["mmcif"])
    category_inventory = [dict(entry) for entry in mmcif["category_inventory"]]
    atom_site_category = next(
        entry for entry in category_inventory if entry["category"] == "_atom_site"
    )
    atom_site_category["row_count"] = len(system.atoms) - 1
    resource_usage = dict(mmcif["resource_usage"])
    resource_usage["atom_site_rows"] = len(system.atoms) - 1
    mmcif["category_inventory"] = category_inventory
    mmcif["resource_usage"] = resource_usage
    metadata["mmcif"] = mmcif
    metadata[MARKER_KEY] = profile
    provenance_metadata = dict(system.provenance.metadata)
    carrier_coverage = dict(provenance_metadata["carrier_coverage"])
    carrier_coverage.update(
        {
            "atom_count": len(system.atoms) - 1,
            "source_atom_row_count": len(system.atoms) - 1,
            "altloc_kept_row_count": len(system.atoms) - 1,
            "unknown_formal_charge_count": len(system.atoms) - 1,
        }
    )
    provenance_metadata["carrier_coverage"] = carrier_coverage
    forged = replace(
        system,
        atoms=system.atoms[:-1],
        bonds=tuple(replace(bond, index=index) for index, bond in enumerate(bonds)),
        residues=(residue,),
        coordinates=system.coordinates[:, :-1, :].clone(),
        metadata=metadata,
        provenance=replace(system.provenance, metadata=provenance_metadata),
    )
    forged = attach_parser_observation_digest(
        _refresh_canonical_topology_digest(forged)
    )

    assert forged.provenance.metadata["carrier_coverage"]["atom_count"] == 5
    assert forged.metadata["mmcif"]["category_inventory"][2]["row_count"] == 5
    assert forged.metadata["mmcif"]["resource_usage"]["atom_site_rows"] == 5
    assert len(forged.atoms) == 5
    _assert_strictly_unrecognized(forged)


def test_commitment_rejects_count_adjusted_final_bond_ordinal_deletion() -> None:
    system = _system()
    removed_bond_index = next(
        bond.index
        for bond in system.bonds
        if bond.metadata[MARKER_KEY]["template_ordinal"] == 5
    )
    bonds = [bond for bond in system.bonds if bond.index != removed_bond_index]
    metadata = dict(system.metadata)
    profile = dict(metadata[MARKER_KEY])
    profile["bond_count"] = len(system.bonds) - 1
    metadata[MARKER_KEY] = profile
    forged = replace(
        system,
        bonds=tuple(replace(bond, index=index) for index, bond in enumerate(bonds)),
        metadata=metadata,
    )
    forged = attach_parser_observation_digest(
        _refresh_canonical_topology_digest(forged)
    )
    _assert_strictly_unrecognized(forged)


@pytest.mark.parametrize("field", ["preparation_ready", "claim_safe"])
def test_carrier_coverage_promotion_tamper_fails_closed(field: str) -> None:
    forged = attach_parser_observation_digest(
        _replace_carrier_coverage(_system(), **{field: True})
    )
    _assert_strictly_unrecognized(forged)


@pytest.mark.parametrize(
    "field",
    [
        "preparation_ready",
        "claim_safe",
        "completion_attempted",
        "completion_applied",
    ],
)
def test_carrier_missingness_promotion_tamper_fails_closed(field: str) -> None:
    forged = attach_parser_observation_digest(
        _replace_mmcif_nested_ledger(
            _system(),
            "carrier_source_reported_missingness",
            **{field: True},
        )
    )
    _assert_strictly_unrecognized(forged)


def test_expected_operations_tamper_fails_closed() -> None:
    system = _system()
    forged = replace(
        system,
        provenance=replace(
            system.provenance,
            operations=(*system.provenance.operations, "forged_operation/v1"),
        ),
    )
    forged = attach_parser_observation_digest(forged)
    _assert_strictly_unrecognized(forged)


def test_single_parent_digest_tamper_fails_closed() -> None:
    system = _system()
    forged = replace(
        system,
        provenance=replace(system.provenance, parent_sha256=("0" * 64,)),
    )
    forged = attach_parser_observation_digest(forged)
    _assert_strictly_unrecognized(forged)


def test_exact_atom_site_header_ledger_tamper_fails_closed() -> None:
    system = _system()
    metadata = dict(system.metadata)
    mmcif = dict(metadata["mmcif"])
    mmcif["atom_site_headers"] = list(reversed(mmcif["atom_site_headers"]))
    metadata["mmcif"] = mmcif
    forged = attach_parser_observation_digest(replace(system, metadata=metadata))
    _assert_strictly_unrecognized(forged)


@pytest.mark.parametrize(
    ("field", "value"),
    [("parser_name", "forged"), ("parser_version", "9.9.9")],
)
def test_coherently_rehashed_parser_identity_tamper_remains_unrecognized(
    field: str,
    value: str,
) -> None:
    system = _system()
    forged = replace(
        system,
        provenance=replace(system.provenance, **{field: value}),
    )
    forged = attach_parser_observation_digest(forged)
    _assert_strictly_unrecognized(forged)
