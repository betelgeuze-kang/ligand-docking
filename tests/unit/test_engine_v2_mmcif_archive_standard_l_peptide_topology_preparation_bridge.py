from __future__ import annotations

from collections.abc import Callable
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
from betelgeuze_engine_v2.molecular.mmcif_archive_standard_l_peptide_topology import (
    MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_PARSER_NAME,
    MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_PARSER_PEDIGREE_ID,
    MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_PARSER_VERSION,
    parse_mmcif_archive_standard_l_peptide_topology,
)
from betelgeuze_engine_v2.molecular.missingness import (
    build_source_reported_missingness_report,
)
from betelgeuze_engine_v2.molecular.observation import (
    MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_PREPARATION_INVENTORY_COMMITMENT_SCHEMA_ID,
    attach_parser_observation_digest,
    attached_parser_observation_sha256_matches,
    mmcif_archive_standard_l_peptide_topology_preparation_inventory_sha256,
)
from betelgeuze_engine_v2.molecular.preparation import analyze_molecular_preparation
from betelgeuze_engine_v2.molecular.topology import (
    CANONICAL_TOPOLOGY_SCHEMA_ID,
    attached_canonical_topology_sha256_matches,
    canonical_topology_sha256,
)


FIXTURES = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "v2_1_mmcif_archive_standard_l_peptide_topology"
)
MARKER_KEY = "mmcif_archive_standard_l_peptide_topology"


def _system(fixture_name: str = "gly_ala_one_asym.cif"):
    return parse_mmcif_archive_standard_l_peptide_topology(
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


def _refresh_preparation_inventory_commitment(system: Any):
    metadata = dict(system.provenance.metadata)
    marker = dict(metadata[MARKER_KEY])
    marker["preparation_inventory_commitment_sha256"] = (
        mmcif_archive_standard_l_peptide_topology_preparation_inventory_sha256(system)
    )
    metadata[MARKER_KEY] = marker
    return replace(
        system,
        provenance=replace(system.provenance, metadata=metadata),
    )


def _coherently_rehash(system: Any):
    refreshed = _refresh_canonical_topology_digest(system)
    refreshed = _refresh_preparation_inventory_commitment(refreshed)
    return attach_parser_observation_digest(refreshed)


def _replace_atom_marker(system: Any, **updates: Any):
    atoms = list(system.atoms)
    metadata = dict(atoms[0].metadata)
    marker = dict(metadata[MARKER_KEY])
    marker.update(updates)
    metadata[MARKER_KEY] = marker
    atoms[0] = replace(atoms[0], metadata=metadata)
    return replace(system, atoms=tuple(atoms))


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


def _replace_mmcif_value(system: Any, key: str, value: Any):
    metadata = dict(system.metadata)
    mmcif = dict(metadata["mmcif"])
    mmcif[key] = value
    metadata["mmcif"] = mmcif
    return replace(system, metadata=metadata)


def _replace_coverage(system: Any, **updates: Any):
    metadata = dict(system.provenance.metadata)
    coverage = dict(metadata["coverage"])
    coverage.update(updates)
    metadata["coverage"] = coverage
    return replace(
        system,
        provenance=replace(system.provenance, metadata=metadata),
    )


def _replace_atom_site_token(
    system: Any,
    atom_index: int,
    header: str,
    *,
    value: str | None = None,
    quoted: bool | None = None,
    multiline: bool | None = None,
    refresh_source_id_views: bool = False,
):
    atoms = list(system.atoms)
    metadata = dict(atoms[atom_index].metadata)
    mmcif = dict(metadata["mmcif"])
    atom_site = dict(mmcif["atom_site"])
    payload = dict(atom_site[header])
    if value is not None:
        payload["value"] = value
    if quoted is not None:
        payload["quoted"] = quoted
    if multiline is not None:
        payload["multiline"] = multiline
    atom_site[header] = payload
    mmcif["atom_site"] = atom_site

    by_model = list(mmcif["atom_site_by_model"])
    model_entry = dict(by_model[0])
    model_values = dict(model_entry["values"])
    model_values[header] = payload
    model_entry["values"] = model_values
    by_model[0] = model_entry
    mmcif["atom_site_by_model"] = by_model

    if refresh_source_id_views:
        assert header == "_atom_site.id"
        assert value is not None
        mmcif["source_atom_site_id"] = value
        id_by_model = list(mmcif["atom_site_id_by_model"])
        id_entry = dict(id_by_model[0])
        id_entry["atom_site_id"] = value
        id_by_model[0] = id_entry
        mmcif["atom_site_id_by_model"] = id_by_model

    metadata["mmcif"] = mmcif
    atoms[atom_index] = replace(atoms[atom_index], metadata=metadata)
    return replace(system, atoms=tuple(atoms))


def _replace_missingness_binding(
    system: Any,
    *,
    source_sha256: str | None = None,
    canonical_topology_sha256: str | None = None,
):
    current = system.metadata["mmcif"]["source_reported_missingness"]
    source_sha256 = source_sha256 or current["source_sha256"]
    canonical_topology_sha256 = (
        canonical_topology_sha256 or current["canonical_topology_sha256"]
    )
    report = build_source_reported_missingness_report(
        source_format="mmcif",
        source_sha256=source_sha256,
        canonical_topology_sha256=canonical_topology_sha256,
        coordinate_scope="deposited_asymmetric_unit",
        altloc_status="not_present",
        requested_altloc_id="",
        assembly_status="not_present",
        requested_assembly_id="",
    ).to_dict()
    forged = _replace_mmcif_value(system, "source_reported_missingness", report)
    provenance_metadata = dict(forged.provenance.metadata)
    coverage = dict(provenance_metadata["coverage"])
    coverage["canonical_topology_sha256"] = canonical_topology_sha256
    coverage["source_missingness_evidence_sha256"] = report["report_sha256"]
    provenance_metadata["coverage"] = coverage
    provenance_metadata["source_missingness_evidence_sha256"] = report["report_sha256"]
    return replace(
        forged,
        provenance=replace(forged.provenance, metadata=provenance_metadata),
    )


def _sorted_reindexed_bonds(bonds: list[Any]) -> tuple[Any, ...]:
    bonds.sort(key=lambda bond: (bond.atom_i, bond.atom_j))
    return tuple(replace(bond, index=index) for index, bond in enumerate(bonds))


def _mutate_atom_element(system: Any):
    atoms = list(system.atoms)
    atoms[0] = replace(atoms[0], element="C", atomic_number=6)
    return replace(system, atoms=tuple(atoms))


def _mutate_atom_marker(system: Any):
    return _replace_atom_marker(system, sequence_role="singleton")


def _mutate_oxt_role(system: Any):
    atom_index = next(atom.index for atom in system.atoms if atom.name == "OXT")
    atoms = list(system.atoms)
    atoms[atom_index] = replace(atoms[atom_index], name="OT2")
    return replace(system, atoms=tuple(atoms))


def _mutate_sequence_link(system: Any):
    bonds = list(system.bonds)
    bond_index = next(
        bond.index
        for bond in bonds
        if bond.metadata[MARKER_KEY]["bond_kind"]
        == "sequence_adjacent_peptide_reference"
    )
    bonds[bond_index] = replace(bonds[bond_index], atom_i=0, atom_j=4)
    return replace(system, bonds=_sorted_reindexed_bonds(bonds))


def _mutate_bond_order(system: Any):
    bonds = list(system.bonds)
    bonds[0] = replace(bonds[0], order=2.0)
    return replace(system, bonds=tuple(bonds))


def _mutate_bond_source(system: Any):
    bonds = list(system.bonds)
    bonds[0] = replace(bonds[0], source="forged_source")
    return replace(system, bonds=tuple(bonds))


def _mutate_bond_marker(system: Any):
    bonds = list(system.bonds)
    metadata = dict(bonds[0].metadata)
    marker = dict(metadata[MARKER_KEY])
    marker["left_atom_id"] = "WRONG"
    metadata[MARKER_KEY] = marker
    bonds[0] = replace(bonds[0], metadata=metadata)
    return replace(system, bonds=tuple(bonds))


def _mutate_missing_bond(system: Any):
    return replace(system, bonds=_sorted_reindexed_bonds(list(system.bonds[1:])))


def _mutate_cross_chain_link(_: Any):
    system = _system("gly_ala_two_asym.cif")
    bonds = list(system.bonds)
    first_chain_c = next(
        atom.index
        for atom in system.atoms
        if atom.metadata[MARKER_KEY]["asym_id"] == "A"
        and atom.metadata[MARKER_KEY]["sequence_number"] == 1
        and atom.name == "C"
    )
    second_chain_n = next(
        atom.index
        for atom in system.atoms
        if atom.metadata[MARKER_KEY]["asym_id"] == "B"
        and atom.metadata[MARKER_KEY]["sequence_number"] == 2
        and atom.name == "N"
    )
    bond_index = next(
        bond.index
        for bond in bonds
        if bond.metadata[MARKER_KEY]["bond_kind"]
        == "sequence_adjacent_peptide_reference"
    )
    bonds[bond_index] = replace(
        bonds[bond_index],
        atom_i=min(first_chain_c, second_chain_n),
        atom_j=max(first_chain_c, second_chain_n),
    )
    return replace(system, bonds=_sorted_reindexed_bonds(bonds))


def _mutate_extra_unmarked_bond(system: Any):
    occupied = {(bond.atom_i, bond.atom_j) for bond in system.bonds}
    endpoints = next(
        (atom_i, atom_j)
        for atom_i in range(len(system.atoms))
        for atom_j in range(atom_i + 1, len(system.atoms))
        if (atom_i, atom_j) not in occupied
    )
    extra = replace(
        system.bonds[0],
        index=-1,
        atom_i=endpoints[0],
        atom_j=endpoints[1],
        metadata={},
    )
    return replace(
        system,
        bonds=_sorted_reindexed_bonds([*system.bonds, extra]),
    )


def _mutate_profile_bounded_true(system: Any):
    return _replace_profile_marker(system, engine_rule_manifest_matched=False)


def _mutate_profile_false_authority(system: Any):
    return _replace_profile_marker(system, preparation_ready=True)


def _mutate_profile_count(system: Any):
    return _replace_profile_marker(
        system,
        materialized_inter_residue_bond_count=999,
    )


def _mutate_rule_manifest(system: Any):
    return _replace_profile_marker(system, rule_manifest_sha256="0" * 64)


def _mutate_provenance_rule_manifest(system: Any):
    return _replace_provenance_marker(system, rule_manifest_sha256="0" * 64)


def _mutate_missingness_source_sha(system: Any):
    return _replace_missingness_binding(system, source_sha256="0" * 64)


def _mutate_chain_auth_asym_ids(system: Any):
    chains = list(system.chains)
    metadata = dict(chains[0].metadata)
    metadata["auth_asym_ids"] = [*metadata["auth_asym_ids"], "FORGED"]
    chains[0] = replace(chains[0], metadata=metadata)
    return replace(system, chains=tuple(chains))


def _mutate_resource_limits(system: Any):
    return _replace_mmcif_value(system, "resource_limits", {"forged": True})


def _mutate_coverage_blockers(system: Any):
    return _replace_coverage(system, blockers=["forged"])


def _mutate_missingness_canonical_topology(system: Any):
    return _replace_missingness_binding(
        system,
        canonical_topology_sha256="0" * 64,
    )


def _mutate_raw_formal_charge(system: Any):
    return _replace_atom_site_token(
        system,
        0,
        "_atom_site.pdbx_formal_charge",
        value="0",
    )


def _mutate_preserved_category_payloads(system: Any):
    return _replace_mmcif_value(system, "preserved_category_payloads", [])


def _mutate_raw_label_alt_id(system: Any):
    return _replace_atom_site_token(
        system,
        0,
        "_atom_site.label_alt_id",
        value="?",
    )


def _mutate_raw_insertion_code(system: Any):
    return _replace_atom_site_token(
        system,
        0,
        "_atom_site.pdbx_pdb_ins_code",
        value=".",
    )


def _mutate_quoted_label_atom_id(system: Any):
    return _replace_atom_site_token(
        system,
        0,
        "_atom_site.label_atom_id",
        quoted=True,
    )


def _mutate_raw_cartn_x(system: Any):
    return _replace_atom_site_token(
        system,
        0,
        "_atom_site.cartn_x",
        value="NOT_A_NUMBER",
    )


def _mutate_duplicate_atom_site_ids(system: Any):
    duplicate_id = system.atoms[0].metadata["mmcif"]["source_atom_site_id"]
    return _replace_atom_site_token(
        system,
        1,
        "_atom_site.id",
        value=duplicate_id,
        refresh_source_id_views=True,
    )


def _mutate_outer_canonical_output_binding(_: Any):
    original = _system()
    source = (FIXTURES / "gly_ala_one_asym.cif").read_bytes()
    original_row = b"ATOM 1 N N . GLY A 1 1 ? 0.0 0.0 0.0 1.0 10.0 ? 101 GLY X N 1\n"
    modified_row = b"ATOM 1 N N . GLY A 1 1 ? 9.0 0.0 0.0 1.0 10.0 ? 101 GLY X N 1\n"
    assert source.count(original_row) == 1
    variant = parse_mmcif_archive_standard_l_peptide_topology(
        source.replace(original_row, modified_row),
        source_id="gly_ala_one_asym.cif",
    ).system
    provenance_metadata = dict(variant.provenance.metadata)
    provenance_marker = dict(provenance_metadata[MARKER_KEY])
    provenance_marker["canonical_output_sha256"] = original.provenance.metadata[
        MARKER_KEY
    ]["canonical_output_sha256"]
    provenance_metadata[MARKER_KEY] = provenance_marker
    return replace(
        variant,
        provenance=replace(
            variant.provenance,
            source_sha256=original.provenance.source_sha256,
            metadata=provenance_metadata,
        ),
    )


def _assert_coherently_rehashed_invalid(
    system: Any,
    *,
    commitment_bound: bool = True,
) -> None:
    assert attached_canonical_topology_sha256_matches(system) is True
    assert attached_parser_observation_sha256_matches(system) is True
    if commitment_bound:
        assert system.provenance.metadata[MARKER_KEY][
            "preparation_inventory_commitment_sha256"
        ] == mmcif_archive_standard_l_peptide_topology_preparation_inventory_sha256(
            system
        )

    preparation = analyze_molecular_preparation(system)
    applicability = analyze_canonical_ingest_applicability(system)
    assert preparation.parser_pedigree_id == "unrecognized"
    assert preparation.parser_observation_self_consistent is False
    assert preparation.preparation_assessed is False
    assert preparation.preparation_ready is False
    assert preparation.claim_safe is False
    assert applicability.canonical_ingest_status == "invalid"
    assert applicability.parser_observation_self_consistent is False
    assert applicability.preparation_status == "incomplete"
    assert applicability.preparation_ready is False
    assert applicability.parameterability_assessed is False
    assert applicability.parameterizable is False
    assert applicability.simulation_ready is False
    assert applicability.claim_safe is False


@pytest.mark.parametrize(
    "fixture_name",
    [
        "single_gly.cif",
        "gly_ala_one_asym.cif",
        "ala_gly_ala.cif",
        "gly_ala_two_asym.cif",
        "category_order_variant.cif",
    ],
)
def test_archive_standard_l_peptide_is_recognized_but_remains_unsupported(
    fixture_name: str,
) -> None:
    system = _system(fixture_name)
    preparation = analyze_molecular_preparation(system)
    applicability = analyze_canonical_ingest_applicability(system)

    assert (
        preparation_module._MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_PARSER_NAME
        == MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_PARSER_NAME
    )
    assert (
        preparation_module._MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_PARSER_VERSION
        == MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_PARSER_VERSION
    )
    assert (
        preparation_module._MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_PARSER_PEDIGREE_ID
        == MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_PARSER_PEDIGREE_ID
    )
    assert attached_canonical_topology_sha256_matches(system) is True
    assert attached_parser_observation_sha256_matches(system) is True
    assert preparation.parser_pedigree_id == (
        MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_PARSER_PEDIGREE_ID
    )
    assert preparation.parser_observation_self_consistent is True
    assert preparation.formal_charge_origin_counts == (
        ("metadata_observed_mmcif_missing", len(system.atoms)),
    )
    assert preparation.preparation_assessed is False
    assert preparation.preparation_ready is False
    assert preparation.claim_safe is False
    assert applicability.canonical_ingest_status == "unsupported"
    assert applicability.parser_pedigree_id == (
        MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_PARSER_PEDIGREE_ID
    )
    assert applicability.parser_observation_self_consistent is True
    assert "recognized_parser_pedigree" not in applicability.failed_constraint_codes
    assert (
        "parser_observation_self_consistent"
        not in applicability.failed_constraint_codes
    )
    assert applicability.preparation_status == "incomplete"
    assert applicability.preparation_ready is False
    assert applicability.parameterability_assessed is False
    assert applicability.parameterizable is False
    assert applicability.simulation_ready is False
    assert applicability.claim_safe is False

    provenance_marker = system.provenance.metadata[MARKER_KEY]
    assert provenance_marker["preparation_inventory_commitment_schema_id"] == (
        MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_PREPARATION_INVENTORY_COMMITMENT_SCHEMA_ID
    )
    assert provenance_marker["preparation_inventory_commitment_sha256"] == (
        mmcif_archive_standard_l_peptide_topology_preparation_inventory_sha256(system)
    )
    with pytest.raises(CanonicalIngestApplicabilityError):
        require_canonical_ingest_applicable(system)


def test_stale_atom_marker_tamper_breaks_observation_binding() -> None:
    forged = _replace_atom_marker(_system(), sequence_number=999)

    assert attached_canonical_topology_sha256_matches(forged) is True
    assert attached_parser_observation_sha256_matches(forged) is False
    preparation = analyze_molecular_preparation(forged)
    applicability = analyze_canonical_ingest_applicability(forged)
    assert preparation.parser_pedigree_id == "unrecognized"
    assert preparation.parser_observation_self_consistent is False
    assert applicability.canonical_ingest_status == "invalid"


def test_stale_commitment_tamper_breaks_observation_binding() -> None:
    forged = _replace_provenance_marker(
        _system(), preparation_inventory_commitment_sha256="0" * 64
    )

    assert attached_canonical_topology_sha256_matches(forged) is True
    assert attached_parser_observation_sha256_matches(forged) is False
    assert analyze_molecular_preparation(forged).parser_pedigree_id == "unrecognized"


def test_observation_rehashed_commitment_tamper_still_fails_closed() -> None:
    forged = attach_parser_observation_digest(
        _replace_provenance_marker(
            _system(), preparation_inventory_commitment_sha256="0" * 64
        )
    )
    _assert_coherently_rehashed_invalid(forged, commitment_bound=False)


@pytest.mark.parametrize(
    "mutator",
    [
        pytest.param(_mutate_atom_element, id="atom-element"),
        pytest.param(_mutate_atom_marker, id="atom-marker"),
        pytest.param(_mutate_oxt_role, id="oxt-boundary-role"),
        pytest.param(_mutate_sequence_link, id="sequence-link"),
        pytest.param(_mutate_bond_order, id="bond-order"),
        pytest.param(_mutate_bond_source, id="bond-source"),
        pytest.param(_mutate_bond_marker, id="bond-marker"),
        pytest.param(_mutate_missing_bond, id="missing-bond"),
        pytest.param(_mutate_cross_chain_link, id="cross-chain-link"),
        pytest.param(_mutate_extra_unmarked_bond, id="extra-unmarked-bond"),
        pytest.param(_mutate_profile_bounded_true, id="profile-bounded-true"),
        pytest.param(_mutate_profile_false_authority, id="profile-false-authority"),
        pytest.param(_mutate_profile_count, id="profile-count"),
        pytest.param(_mutate_rule_manifest, id="rule-manifest"),
        pytest.param(
            _mutate_provenance_rule_manifest,
            id="provenance-rule-manifest",
        ),
    ],
)
def test_coherently_rehashed_semantic_mutations_fail_identity_closed(
    mutator: Callable[[Any], Any],
) -> None:
    forged = _coherently_rehash(mutator(_system()))
    _assert_coherently_rehashed_invalid(forged)


@pytest.mark.parametrize(
    "mutator",
    [
        pytest.param(
            _mutate_missingness_source_sha,
            id="missingness-source-sha",
        ),
        pytest.param(
            _mutate_chain_auth_asym_ids,
            id="chain-auth-asym-extra",
        ),
        pytest.param(_mutate_resource_limits, id="resource-limits"),
        pytest.param(_mutate_coverage_blockers, id="coverage-blockers"),
        pytest.param(
            _mutate_missingness_canonical_topology,
            id="missingness-canonical-topology-and-report",
        ),
        pytest.param(_mutate_raw_formal_charge, id="raw-formal-charge"),
        pytest.param(
            _mutate_preserved_category_payloads,
            id="preserved-category-payloads",
        ),
        pytest.param(_mutate_raw_label_alt_id, id="raw-label-alt-id"),
        pytest.param(_mutate_raw_insertion_code, id="raw-insertion-code"),
        pytest.param(_mutate_quoted_label_atom_id, id="quoted-label-atom-id"),
        pytest.param(_mutate_raw_cartn_x, id="invalid-cartn-x"),
        pytest.param(
            _mutate_duplicate_atom_site_ids,
            id="duplicate-atom-site-ids-with-local-views",
        ),
        pytest.param(
            _mutate_outer_canonical_output_binding,
            id="outer-canonical-output-binding",
        ),
    ],
)
def test_coherently_rehashed_exact_carrier_bypasses_fail_closed(
    mutator: Callable[[Any], Any],
) -> None:
    forged = _coherently_rehash(mutator(_system()))
    _assert_coherently_rehashed_invalid(forged)
