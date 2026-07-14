from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from betelgeuze_engine_v2.molecular import preparation as preparation_module
from betelgeuze_engine_v2.molecular.applicability import (
    CanonicalIngestApplicabilityError,
    analyze_canonical_ingest_applicability,
    require_canonical_ingest_applicable,
)
from betelgeuze_engine_v2.molecular.chemistry import analyze_canonical_chemistry
from betelgeuze_engine_v2.molecular.mmcif_nonpoly_covalent_struct_conn_topology import (
    MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_PARSER_NAME,
    MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_PARSER_PEDIGREE_ID,
    MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_PARSER_VERSION,
    parse_mmcif_nonpoly_covalent_struct_conn_topology,
)
from betelgeuze_engine_v2.molecular.observation import (
    attach_parser_observation_digest,
    attached_parser_observation_sha256_matches,
    parser_observation_document,
)
from betelgeuze_engine_v2.molecular.preparation import (
    analyze_molecular_preparation,
)
from betelgeuze_engine_v2.molecular.profile_preparation import (
    ProfileLocalPreparationEvidenceError,
    analyze_profile_local_preparation_evidence,
    require_profile_local_preparation_evidence,
)
from betelgeuze_engine_v2.molecular.topology import (
    CANONICAL_TOPOLOGY_SCHEMA_ID,
    attached_canonical_topology_sha256_matches,
    canonical_topology_sha256,
)


FIXTURES = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "v2_1_mmcif_nonpoly_covalent_struct_conn_topology"
)
STRUCT_CONN_MARKER_KEY = "mmcif_nonpoly_covalent_struct_conn_topology"
STRUCT_CONN_MARKER_KEYS = {
    "connection_id",
    "row_ordinal",
    "conn_type_id",
    "value_order",
    "ptnr1_atom_site_id",
    "ptnr2_atom_site_id",
    "ptnr1_atom_index",
    "ptnr2_atom_index",
    "ptnr1_residue_index",
    "ptnr2_residue_index",
    "ptnr1_symmetry",
    "ptnr2_symmetry",
}


def _system(fixture_name: str = "split_ethane_sing.cif"):
    return parse_mmcif_nonpoly_covalent_struct_conn_topology(
        (FIXTURES / fixture_name).read_bytes(),
        source_id=fixture_name,
    ).system


def _two_row_split_ethane_system():
    data = (FIXTURES / "split_ethane_sing.cif").read_bytes()
    first_row = (
        b"ethane_cc covale A MTH . C . ? 1_555 B MTH . C . ? "
        b"A MTH 1 B MTH 2 1_555 sing\n"
    )
    second_row = (
        b"ethane_hh covale A MTH . H1 . ? 1_555 B MTH . H1 . ? "
        b"A MTH 1 B MTH 2 1_555 sing\n"
    )
    assert data.count(first_row) == 1
    return parse_mmcif_nonpoly_covalent_struct_conn_topology(
        data.replace(first_row, first_row + second_row),
        source_id="split_ethane_two_rows",
    ).system


def _struct_conn_bond_index(system: Any) -> int:
    matches = [
        bond.index for bond in system.bonds if STRUCT_CONN_MARKER_KEY in bond.metadata
    ]
    assert len(matches) == 1
    return matches[0]


def _replace_struct_conn_marker(system: Any, **updates: Any):
    index = _struct_conn_bond_index(system)
    bonds = list(system.bonds)
    metadata = dict(bonds[index].metadata)
    marker = dict(metadata[STRUCT_CONN_MARKER_KEY])
    marker.update(updates)
    metadata[STRUCT_CONN_MARKER_KEY] = marker
    bonds[index] = replace(bonds[index], metadata=metadata)
    return replace(system, bonds=tuple(bonds))


def _refresh_canonical_topology_digest(system: Any):
    metadata = dict(system.provenance.metadata)
    metadata["canonical_topology_schema_id"] = CANONICAL_TOPOLOGY_SCHEMA_ID
    metadata["canonical_topology_sha256"] = canonical_topology_sha256(system)
    return replace(
        system,
        provenance=replace(system.provenance, metadata=metadata),
    )


def _replace_system_profile_marker(system: Any, **updates: Any):
    metadata = dict(system.metadata)
    profile_marker = dict(metadata[STRUCT_CONN_MARKER_KEY])
    profile_marker.update(updates)
    metadata[STRUCT_CONN_MARKER_KEY] = profile_marker
    return replace(system, metadata=metadata)


def test_split_ethane_reaches_only_existing_local_hydrocarbon_gates() -> None:
    system = _system()
    chemistry = analyze_canonical_chemistry(system)
    preparation = analyze_molecular_preparation(system)
    applicability = require_canonical_ingest_applicable(system)
    local = require_profile_local_preparation_evidence(system)

    assert MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_PARSER_PEDIGREE_ID == (
        "betelgeuze.mmcif_nonpoly_covalent_struct_conn_topology_parser/1.0.0"
    )
    assert (
        preparation_module._MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_PARSER_NAME
        == MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_PARSER_NAME
    )
    assert (
        preparation_module._MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_PARSER_VERSION
        == MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_PARSER_VERSION
    )
    assert (
        preparation_module._MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_PARSER_PEDIGREE_ID
        == MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_PARSER_PEDIGREE_ID
    )
    assert attached_canonical_topology_sha256_matches(system) is True
    assert attached_parser_observation_sha256_matches(system) is True
    assert preparation.parser_pedigree_id == (
        MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_PARSER_PEDIGREE_ID
    )
    assert preparation.parser_observation_self_consistent is True
    assert preparation.atom_count == 8
    assert preparation.bond_count == 7
    assert preparation.residue_count == 2
    assert preparation.hydrogen_origin_counts == (
        ("metadata_observed_parser_source", 6),
    )
    assert preparation.formal_charge_origin_counts == (
        ("metadata_observed_mmcif_chem_comp_atom", 8),
    )
    assert applicability.canonical_ingest_status == "supported"
    assert applicability.failed_constraint_codes == ()
    assert local.profile_local_evidence_status == "satisfied"
    assert local.source_observed_formal_charge_count == 8

    assert chemistry.chemistry_supported is False
    assert chemistry.parameterability_assessed is False
    assert chemistry.parameterizable is False
    assert preparation.preparation_assessed is False
    assert preparation.preparation_ready is False
    assert local.preparation_assessed is False
    assert local.preparation_ready is False
    assert local.parameterability_assessed is False
    assert local.parameterizable is False
    assert local.simulation_ready is False
    assert local.claim_safe is False

    struct_conn_bond = system.bonds[_struct_conn_bond_index(system)]
    assert struct_conn_bond.source == "mmcif_struct_conn_covale"
    assert struct_conn_bond.order == 1.0
    assert struct_conn_bond.aromatic is False
    assert struct_conn_bond.stereo == "none"
    assert set(struct_conn_bond.metadata) == {STRUCT_CONN_MARKER_KEY}
    assert set(struct_conn_bond.metadata[STRUCT_CONN_MARKER_KEY]) == (
        STRUCT_CONN_MARKER_KEYS
    )
    observed = parser_observation_document(system)
    assert observed["bonds"][_struct_conn_bond_index(system)]["markers"][
        STRUCT_CONN_MARKER_KEY
    ]["unexpected_mapping"] == dict(struct_conn_bond.metadata[STRUCT_CONN_MARKER_KEY])


def test_stale_struct_conn_marker_breaks_observation_binding() -> None:
    system = _system()
    forged = _replace_struct_conn_marker(system, connection_id="forged")

    assert attached_canonical_topology_sha256_matches(forged) is True
    assert attached_parser_observation_sha256_matches(forged) is False
    preparation = analyze_molecular_preparation(forged)
    assert preparation.parser_pedigree_id == "unrecognized"
    assert preparation.parser_observation_self_consistent is False
    applicability = analyze_canonical_ingest_applicability(forged)
    assert applicability.canonical_ingest_status == "invalid"
    assert "parser_observation_self_consistent" in (
        applicability.failed_constraint_codes
    )


@pytest.mark.parametrize(
    ("updates"),
    [
        {"connection_id": ""},
        {"row_ordinal": 2},
        {"conn_type_id": "hydrog"},
        {"value_order": "doub"},
        {"ptnr1_symmetry": "2_555"},
        {"ptnr2_atom_site_id": "wrong"},
        {"ptnr1_residue_index": 999},
    ],
)
def test_coherently_rehashed_struct_conn_marker_tamper_fails_identity_closed(
    updates: dict[str, Any],
) -> None:
    forged = attach_parser_observation_digest(
        _replace_struct_conn_marker(_system(), **updates)
    )

    assert attached_canonical_topology_sha256_matches(forged) is True
    assert attached_parser_observation_sha256_matches(forged) is True
    preparation = analyze_molecular_preparation(forged)
    assert preparation.parser_pedigree_id == "unrecognized"
    assert preparation.parser_observation_self_consistent is False
    applicability = analyze_canonical_ingest_applicability(forged)
    assert applicability.canonical_ingest_status == "invalid"
    assert "recognized_parser_pedigree" in applicability.failed_constraint_codes
    assert "parser_observation_self_consistent" in (
        applicability.failed_constraint_codes
    )
    local = analyze_profile_local_preparation_evidence(forged)
    assert local.profile_local_evidence_status == "invalid"
    assert local.profile_local_evidence_satisfied is False


def test_coherently_rehashed_order_mismatch_fails_identity_closed() -> None:
    system = _system()
    index = _struct_conn_bond_index(system)
    bonds = list(system.bonds)
    bonds[index] = replace(bonds[index], order=2.0)
    forged = replace(system, bonds=tuple(bonds))
    forged = attach_parser_observation_digest(
        _refresh_canonical_topology_digest(forged)
    )

    assert attached_canonical_topology_sha256_matches(forged) is True
    assert attached_parser_observation_sha256_matches(forged) is True
    preparation = analyze_molecular_preparation(forged)
    assert preparation.parser_pedigree_id == "unrecognized"
    assert preparation.parser_observation_self_consistent is False
    assert analyze_canonical_ingest_applicability(forged).canonical_ingest_status == (
        "invalid"
    )


def test_coherently_rehashed_unmarked_inter_residue_bond_fails_identity_closed() -> (
    None
):
    system = _system()
    index = _struct_conn_bond_index(system)
    bonds = list(system.bonds)
    bonds[index] = replace(bonds[index], metadata={})
    forged = attach_parser_observation_digest(replace(system, bonds=tuple(bonds)))

    assert attached_canonical_topology_sha256_matches(forged) is True
    assert attached_parser_observation_sha256_matches(forged) is True
    preparation = analyze_molecular_preparation(forged)
    assert preparation.parser_pedigree_id == "unrecognized"
    assert preparation.parser_observation_self_consistent is False
    applicability = analyze_canonical_ingest_applicability(forged)
    assert applicability.canonical_ingest_status == "invalid"
    with pytest.raises(CanonicalIngestApplicabilityError):
        require_canonical_ingest_applicable(forged)
    with pytest.raises(ProfileLocalPreparationEvidenceError):
        require_profile_local_preparation_evidence(forged)


def test_coherently_rehashed_additional_unmarked_inter_residue_bond_fails_closed() -> (
    None
):
    system = _system()
    struct_conn_bond = system.bonds[_struct_conn_bond_index(system)]
    existing_pairs = {(bond.atom_i, bond.atom_j) for bond in system.bonds}
    endpoint_pair = next(
        (min(atom_i, atom_j), max(atom_i, atom_j))
        for atom_i in system.residues[0].atom_indices
        for atom_j in system.residues[1].atom_indices
        if (min(atom_i, atom_j), max(atom_i, atom_j)) not in existing_pairs
    )
    forged_bond = replace(
        struct_conn_bond,
        atom_i=endpoint_pair[0],
        atom_j=endpoint_pair[1],
        source="forged_unmarked_inter_residue_bond",
        metadata={},
    )
    sorted_bonds = sorted(
        (*system.bonds, forged_bond),
        key=lambda bond: (bond.atom_i, bond.atom_j),
    )
    forged = replace(
        system,
        bonds=tuple(
            replace(bond, index=index) for index, bond in enumerate(sorted_bonds)
        ),
    )
    forged = attach_parser_observation_digest(
        _refresh_canonical_topology_digest(forged)
    )

    assert attached_canonical_topology_sha256_matches(forged) is True
    assert attached_parser_observation_sha256_matches(forged) is True
    preparation = analyze_molecular_preparation(forged)
    assert preparation.parser_pedigree_id == "unrecognized"
    assert preparation.parser_observation_self_consistent is False
    applicability = analyze_canonical_ingest_applicability(forged)
    assert applicability.canonical_ingest_status == "invalid"
    assert "recognized_parser_pedigree" in applicability.failed_constraint_codes


def test_coherent_second_row_bond_deletion_disagrees_with_profile_counts() -> None:
    system = _two_row_split_ethane_system()
    assert system.metadata[STRUCT_CONN_MARKER_KEY]["struct_conn_row_count"] == 2
    assert (
        system.metadata[STRUCT_CONN_MARKER_KEY]["materialized_inter_residue_bond_count"]
        == 2
    )
    assert analyze_molecular_preparation(system).parser_pedigree_id == (
        MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_PARSER_PEDIGREE_ID
    )

    bonds = [
        bond
        for bond in system.bonds
        if bond.metadata.get(STRUCT_CONN_MARKER_KEY, {}).get("connection_id")
        != "ethane_hh"
    ]
    assert len(bonds) == len(system.bonds) - 1
    forged = replace(
        system,
        bonds=tuple(replace(bond, index=index) for index, bond in enumerate(bonds)),
    )
    forged = attach_parser_observation_digest(
        _refresh_canonical_topology_digest(forged)
    )

    assert attached_canonical_topology_sha256_matches(forged) is True
    assert attached_parser_observation_sha256_matches(forged) is True
    preparation = analyze_molecular_preparation(forged)
    assert preparation.parser_pedigree_id == "unrecognized"
    assert preparation.parser_observation_self_consistent is False
    applicability = analyze_canonical_ingest_applicability(forged)
    assert applicability.canonical_ingest_status == "invalid"
    assert "recognized_parser_pedigree" in applicability.failed_constraint_codes


@pytest.mark.parametrize(
    "updates",
    [
        {"struct_conn_row_count": 2},
        {"materialized_inter_residue_bond_count": 2},
        {"bounded_inter_residue_topology_interpreted": False},
        {"unexpected_profile_authority": True},
    ],
)
def test_coherent_profile_marker_or_count_tamper_fails_identity_closed(
    updates: dict[str, Any],
) -> None:
    forged = attach_parser_observation_digest(
        _replace_system_profile_marker(_system(), **updates)
    )

    assert attached_canonical_topology_sha256_matches(forged) is True
    assert attached_parser_observation_sha256_matches(forged) is True
    preparation = analyze_molecular_preparation(forged)
    assert preparation.parser_pedigree_id == "unrecognized"
    assert preparation.parser_observation_self_consistent is False
    assert analyze_canonical_ingest_applicability(forged).canonical_ingest_status == (
        "invalid"
    )


def test_coherent_struct_conn_provenance_semantics_tamper_fails_closed() -> None:
    system = _system()
    provenance_metadata = dict(system.provenance.metadata)
    provenance_marker = dict(provenance_metadata[STRUCT_CONN_MARKER_KEY])
    provenance_marker["carrier_evidence_semantics"] = "forged"
    provenance_metadata[STRUCT_CONN_MARKER_KEY] = provenance_marker
    forged = replace(
        system,
        provenance=replace(system.provenance, metadata=provenance_metadata),
    )
    forged = attach_parser_observation_digest(forged)

    assert attached_canonical_topology_sha256_matches(forged) is True
    assert attached_parser_observation_sha256_matches(forged) is True
    preparation = analyze_molecular_preparation(forged)
    assert preparation.parser_pedigree_id == "unrecognized"
    assert preparation.parser_observation_self_consistent is False
    assert analyze_canonical_ingest_applicability(forged).canonical_ingest_status == (
        "invalid"
    )


def test_inherited_component_marker_checks_remain_exact_for_derived_parser() -> None:
    system = _system()
    hydrogen_index = next(atom.index for atom in system.atoms if atom.element == "H")
    atoms = list(system.atoms)
    metadata = dict(atoms[hydrogen_index].metadata)
    component_marker = dict(metadata["mmcif_nonpoly_component_topology"])
    component_marker["template_ordinal"] = 999
    metadata["mmcif_nonpoly_component_topology"] = component_marker
    atoms[hydrogen_index] = replace(atoms[hydrogen_index], metadata=metadata)
    forged = attach_parser_observation_digest(replace(system, atoms=tuple(atoms)))

    assert attached_canonical_topology_sha256_matches(forged) is True
    assert attached_parser_observation_sha256_matches(forged) is True
    preparation = analyze_molecular_preparation(forged)
    assert preparation.parser_pedigree_id == (
        MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_PARSER_PEDIGREE_ID
    )
    assert preparation.parser_observation_self_consistent is True
    assert preparation.unknown_hydrogen_origin_count > 0
    assert ("unclassified_known", 4) in preparation.formal_charge_origin_counts
    applicability = analyze_canonical_ingest_applicability(forged)
    assert applicability.canonical_ingest_status == "unsupported"
    assert "hydrogens_source_observed" in applicability.failed_constraint_codes
    assert (
        analyze_profile_local_preparation_evidence(
            forged
        ).profile_local_evidence_satisfied
        is False
    )


@pytest.mark.parametrize(
    "fixture_name",
    ["split_formaldehyde_doub.cif", "split_hydrogen_cyanide_trip.cif"],
)
def test_explicit_multiple_order_struct_conn_fixtures_remain_nonpositive(
    fixture_name: str,
) -> None:
    if not (FIXTURES / fixture_name).is_file():
        pytest.skip(f"optional fixture is not available: {fixture_name}")
    system = _system(fixture_name)
    preparation = analyze_molecular_preparation(system)
    applicability = analyze_canonical_ingest_applicability(system)

    assert preparation.parser_pedigree_id == (
        MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_PARSER_PEDIGREE_ID
    )
    assert preparation.parser_observation_self_consistent is True
    assert applicability.canonical_ingest_status == "unsupported"
    assert "single_bonds_only" in applicability.failed_constraint_codes
    assert (
        analyze_profile_local_preparation_evidence(
            system
        ).profile_local_evidence_satisfied
        is False
    )
