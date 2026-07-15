from __future__ import annotations

from pathlib import Path
import json

import torch
import pytest

import betelgeuze_engine_v2.molecular.standard_l_peptide_rules as rules_module
from betelgeuze_engine_v2.molecular.observation import (
    MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_PREPARATION_INVENTORY_COMMITMENT_SCHEMA_ID,
    mmcif_archive_standard_l_peptide_topology_preparation_inventory_sha256,
    parser_observation_document,
)
from betelgeuze_engine_v2.molecular.mmcif_archive_standard_l_peptide_topology import (
    MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_PARSER_PEDIGREE_ID,
    MmcifArchiveStandardLPeptideTopologyError,
    parse_mmcif_archive_standard_l_peptide_topology,
    round_trip_mmcif_archive_standard_l_peptide_topology_source,
)
from betelgeuze_engine_v2.molecular.mmcif_polymer_sequence import (
    parse_mmcif_polymer_sequence,
)
from betelgeuze_engine_v2.molecular.standard_l_peptide_rules import (
    STANDARD_L_PEPTIDE_RULE_MANIFEST_SHA256,
    validate_standard_l_peptide_rule_manifest,
)


FIXTURES = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "v2_1_mmcif_archive_standard_l_peptide_topology"
)
GLY_ALA = FIXTURES / "gly_ala_one_asym.cif"
ALA_GLY_ALA = FIXTURES / "ala_gly_ala.cif"
TWO_ASYM = FIXTURES / "gly_ala_two_asym.cif"
CATEGORY_ORDER = FIXTURES / "category_order_variant.cif"
SINGLE_GLY = FIXTURES / "single_gly.cif"


def _carrier_source(source: bytes) -> bytes:
    text = source.decode("ascii")
    start = text.index("loop_\n_entity_poly.entity_id")
    end = text.index("#\n", start) + 2
    return (text[:start] + text[end:]).encode("ascii")


def test_gly_ala_materializes_exact_sequence_implied_reference_topology() -> None:
    source = GLY_ALA.read_bytes()
    carrier = parse_mmcif_polymer_sequence(_carrier_source(source))
    ingest = parse_mmcif_archive_standard_l_peptide_topology(
        source, source_id="gly-ala"
    )
    system = ingest.system

    assert validate_standard_l_peptide_rule_manifest() == (
        STANDARD_L_PEPTIDE_RULE_MANIFEST_SHA256
    )
    assert system.atom_count == 10
    assert len(system.bonds) == 9
    assert torch.equal(system.coordinates, carrier.system.coordinates)
    assert system.coordinates.dtype == carrier.system.coordinates.dtype
    assert system.provenance.metadata["mmcif_archive_standard_l_peptide_topology"][
        "parser_pedigree_id"
    ] == (MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_PARSER_PEDIGREE_ID)
    named_bonds = {
        (
            system.atoms[bond.atom_i].residue_index,
            system.atoms[bond.atom_i].name,
            system.atoms[bond.atom_j].residue_index,
            system.atoms[bond.atom_j].name,
            bond.order,
        )
        for bond in system.bonds
    }
    assert (0, "C", 1, "N", 1.0) in named_bonds
    assert (0, "C", 0, "O", 2.0) in named_bonds
    assert (1, "C", 1, "OXT", 1.0) in named_bonds
    assert all(atom.formal_charge_known is False for atom in system.atoms)
    marker = system.metadata["mmcif_archive_standard_l_peptide_topology"]
    assert (
        marker["sequence_implied_standard_l_peptide_reference_topology_materialized"]
        is True
    )
    assert marker["coordinate_peptide_geometry_validated"] is False
    assert marker["observed_covalent_bond_established"] is False
    assert marker["preparation_ready"] is False
    assert marker["parameterability_assessed"] is False


def test_gly_ala_canonical_round_trip_is_topology_and_byte_stable() -> None:
    result = round_trip_mmcif_archive_standard_l_peptide_topology_source(
        GLY_ALA.read_bytes(), source_id="gly-ala"
    )

    assert result.report.topology_state_equal is True
    assert result.report.topology_equal is True
    assert result.report.emitted_source_reparsed_exact is True
    assert result.report.second_emission_byte_stable is True
    text = result.write_result.payload.decode("ascii").lower()
    offsets = [
        text.index("_entity.id"),
        text.index("_entity_poly.entity_id"),
        text.index("_struct_asym.id"),
        text.index("_entity_poly_seq.entity_id"),
        text.index("_atom_site.group_pdb"),
    ]
    assert offsets == sorted(offsets)


def _semantic_bonds(system):
    result = set()
    for bond in system.bonds:
        marker = bond.metadata["mmcif_archive_standard_l_peptide_topology"]
        result.add(
            (
                marker["asym_id"],
                marker["left_sequence_number"],
                marker["left_atom_id"],
                marker["right_sequence_number"],
                marker["right_atom_id"],
                bond.order,
            )
        )
    return result


def test_ala_gly_ala_expands_two_sequence_adjacent_links_without_distance_gating() -> (
    None
):
    source = ALA_GLY_ALA.read_bytes()
    system = parse_mmcif_archive_standard_l_peptide_topology(source).system
    moved = source.replace(
        b"ATOM 6 N N . GLY A 1 2 ? 20 0 0",
        b"ATOM 6 N N . GLY A 1 2 ? 9999 9999 9999",
    ).replace(b" XA ", b" ZZ ")
    moved_system = parse_mmcif_archive_standard_l_peptide_topology(moved).system

    assert system.atom_count == 15
    assert len(system.bonds) == 14
    assert (
        len(
            [
                bond
                for bond in system.bonds
                if bond.metadata["mmcif_archive_standard_l_peptide_topology"][
                    "bond_kind"
                ]
                == "sequence_adjacent_peptide_reference"
            ]
        )
        == 2
    )
    assert _semantic_bonds(system) == _semantic_bonds(moved_system)
    assert (
        system.metadata["mmcif_archive_standard_l_peptide_topology"][
            "coordinate_peptide_geometry_validated"
        ]
        is False
    )


def test_same_entity_two_asym_expands_independently_without_cross_asym_bonds() -> None:
    system = parse_mmcif_archive_standard_l_peptide_topology(
        TWO_ASYM.read_bytes()
    ).system

    assert system.atom_count == 20
    assert len(system.bonds) == 18
    inter = [
        bond
        for bond in system.bonds
        if bond.metadata["mmcif_archive_standard_l_peptide_topology"]["bond_kind"]
        == "sequence_adjacent_peptide_reference"
    ]
    assert len(inter) == 2
    for bond in system.bonds:
        left = system.atoms[bond.atom_i].metadata[
            "mmcif_archive_standard_l_peptide_topology"
        ]["asym_id"]
        right = system.atoms[bond.atom_j].metadata[
            "mmcif_archive_standard_l_peptide_topology"
        ]["asym_id"]
        assert left == right


def test_singleton_gly_requires_oxt_and_has_no_inter_residue_link() -> None:
    system = parse_mmcif_archive_standard_l_peptide_topology(
        SINGLE_GLY.read_bytes()
    ).system

    assert system.atom_count == 5
    assert len(system.bonds) == 4
    assert all(
        atom.metadata["mmcif_archive_standard_l_peptide_topology"]["sequence_role"]
        == "singleton"
        for atom in system.atoms
    )
    assert not any(
        bond.metadata["mmcif_archive_standard_l_peptide_topology"]["bond_kind"]
        == "sequence_adjacent_peptide_reference"
        for bond in system.bonds
    )


def test_category_order_variant_normalizes_to_same_canonical_output() -> None:
    canonical = round_trip_mmcif_archive_standard_l_peptide_topology_source(
        GLY_ALA.read_bytes()
    )
    reordered = round_trip_mmcif_archive_standard_l_peptide_topology_source(
        CATEGORY_ORDER.read_bytes()
    )

    assert canonical.write_result.payload == reordered.write_result.payload
    assert canonical.source_ingest.projection_sha256 == (
        reordered.source_ingest.projection_sha256
    )
    assert (
        canonical.source_ingest.topology_sha256
        == reordered.source_ingest.topology_sha256
    )
    assert canonical.source_ingest.source_binding_sha256 != (
        reordered.source_ingest.source_binding_sha256
    )


def test_atom_and_residue_row_order_do_not_select_sequence_adjacency() -> None:
    source = GLY_ALA.read_bytes()
    rows = [line for line in source.splitlines() if line.startswith(b"ATOM ")]
    shuffled_rows = [rows[index] for index in (7, 4, 9, 5, 8, 6, 2, 0, 3, 1)]
    original_block = b"\n".join(rows)
    shuffled = source.replace(original_block, b"\n".join(shuffled_rows), 1)

    canonical_system = parse_mmcif_archive_standard_l_peptide_topology(source).system
    shuffled_system = parse_mmcif_archive_standard_l_peptide_topology(shuffled).system

    assert _semantic_bonds(canonical_system) == _semantic_bonds(shuffled_system)
    inter = [
        bond
        for bond in shuffled_system.bonds
        if bond.metadata["mmcif_archive_standard_l_peptide_topology"]["bond_kind"]
        == "sequence_adjacent_peptide_reference"
    ]
    assert len(inter) == 1


def _delete_line(source: bytes, line: bytes) -> bytes:
    assert source.count(line + b"\n") == 1
    return source.replace(line + b"\n", b"", 1)


def _negative_cases(source: bytes) -> list[tuple[str, bytes, str]]:
    atom_extra = b"ATOM 10 O OXT . ALA A 1 2 ? 6.0 1.0 0.0 1.0 11.0 ? 102 ALA X OXT 1\n"
    return [
        ("missing category", _carrier_source(source), "unsupported_category_surface"),
        (
            "extra category",
            source + b"loop_\n_struct_conn.id\nx\n#\n",
            "unsupported_category_surface",
        ),
        (
            "bad entity-poly header",
            source.replace(b"_entity_poly.type", b"_entity_poly.pdbx_type", 1),
            "unsupported_entity_poly_headers",
        ),
        (
            "explicit-link field not selected",
            source.replace(
                b"_entity_poly.nstd_monomer\n1 polypeptide(L) no no no",
                b"_entity_poly.nstd_monomer\n_entity_poly.pdbx_explicit_linking_flag\n1 polypeptide(L) no no no N",
                1,
            ),
            "unsupported_entity_poly_headers",
        ),
        (
            "wrong polymer type",
            source.replace(b"polypeptide(L) no no no", b"polypeptide(D) no no no", 1),
            "unsupported_entity_poly_profile",
        ),
        (
            "nonstandard chirality",
            source.replace(b"polypeptide(L) no no no", b"polypeptide(L) yes no no", 1),
            "unsupported_entity_poly_profile",
        ),
        (
            "nonstandard linkage",
            source.replace(b"polypeptide(L) no no no", b"polypeptide(L) no yes no", 1),
            "unsupported_entity_poly_profile",
        ),
        (
            "nonstandard monomer flag",
            source.replace(b"polypeptide(L) no no no", b"polypeptide(L) no no yes", 1),
            "unsupported_entity_poly_profile",
        ),
        (
            "quoted selected value",
            source.replace(b"polypeptide(L) no no no", b"'polypeptide(L)' no no no", 1),
            "invalid_entity_poly_value",
        ),
        (
            "unknown residue",
            source.replace(b"GLY", b"MSE"),
            "unsupported_monomer",
        ),
        (
            "microheterogeneity",
            source.replace(b"1 1 GLY n", b"1 1 GLY y", 1),
            "sequence_microheterogeneity_not_supported",
        ),
        (
            "missing sequence instance",
            b"\n".join(
                line
                for line in source.split(b"\n")
                if not line.startswith((b"ATOM 1 ", b"ATOM 2 ", b"ATOM 3 ", b"ATOM 4 "))
            ),
            "missing_sequence_instance",
        ),
        (
            "missing core role",
            _delete_line(
                source,
                b"ATOM 2 C CA . GLY A 1 1 ? 1.0 0.0 0.0 1.0 10.0 ? 101 GLY X CA 1",
            ),
            "residue_atom_role_mismatch",
        ),
        (
            "missing link endpoint",
            _delete_line(
                source,
                b"ATOM 3 C C . GLY A 1 1 ? 2.0 0.0 0.0 1.0 10.0 ? 101 GLY X C 1",
            ),
            "missing_link_endpoint",
        ),
        (
            "missing c boundary OXT",
            _delete_line(source, atom_extra.rstrip(b"\n")),
            "residue_atom_role_mismatch",
        ),
        (
            "outgoing OXT",
            source.replace(
                atom_extra,
                b"ATOM 11 O OXT . GLY A 1 1 ? 2.5 1 0 1 10 ? 101 GLY X OXT 1\n"
                + atom_extra,
                1,
            ),
            "extra_or_disallowed_atom_role",
        ),
        (
            "duplicate atom role",
            source.replace(b"ATOM 2 C CA . GLY", b"ATOM 2 N N . GLY", 1),
            "polymer_sequence_carrier_rejected",
        ),
        (
            "element mismatch",
            source.replace(b"ATOM 1 N N . GLY", b"ATOM 1 C N . GLY", 1),
            "atom_element_mismatch",
        ),
        (
            "altloc",
            source.replace(b"ATOM 1 N N . GLY", b"ATOM 1 N N A GLY", 1),
            "polymer_sequence_carrier_rejected",
        ),
        (
            "multimodel",
            source.replace(b"101 GLY X N 1", b"101 GLY X N 2", 1),
            "polymer_sequence_carrier_rejected",
        ),
        (
            "known formal charge",
            source.replace(b"10.0 ? 101 GLY X N", b"10.0 0 101 GLY X N", 1),
            "formal_charge_must_be_unknown",
        ),
        (
            "insertion code",
            source.replace(b"GLY A 1 1 ? 0.0", b"GLY A 1 1 A 0.0", 1),
            "unsupported_insertion_code",
        ),
        (
            "nonpoly entity",
            source.replace(b"1 polymer", b"1 non-polymer", 1),
            "nonpolymer_entity",
        ),
        (
            "non-ATOM group",
            source.replace(b"ATOM 1 N N", b"HETATM 1 N N", 1),
            "polymer_sequence_carrier_rejected",
        ),
    ]


@pytest.mark.parametrize("label,mutated,code", _negative_cases(GLY_ALA.read_bytes()))
def test_exact_profile_rejects_typed_negative_without_partial_result(
    label: str, mutated: bytes, code: str
) -> None:
    with pytest.raises(MmcifArchiveStandardLPeptideTopologyError) as exc_info:
        parse_mmcif_archive_standard_l_peptide_topology(mutated)
    assert exc_info.value.code == code, label


def test_rule_manifest_runtime_tamper_fails_before_parsing(monkeypatch) -> None:
    monkeypatch.setattr(
        rules_module,
        "STANDARD_L_PEPTIDE_COMPONENT_RULES",
        tuple(reversed(rules_module.STANDARD_L_PEPTIDE_COMPONENT_RULES)),
    )

    with pytest.raises(MmcifArchiveStandardLPeptideTopologyError) as exc_info:
        parse_mmcif_archive_standard_l_peptide_topology(GLY_ALA.read_bytes())
    assert exc_info.value.code == "rule_manifest_hash_mismatch"


def test_marker_key_sets_and_observation_manifest_binding_are_exact() -> None:
    system = parse_mmcif_archive_standard_l_peptide_topology(
        GLY_ALA.read_bytes()
    ).system
    atom_keys = {
        "component_id",
        "atom_id",
        "asym_id",
        "sequence_number",
        "sequence_role",
        "rule_id",
        "rule_manifest_sha256",
    }
    bond_keys = {
        "bond_kind",
        "rule_id",
        "rule_manifest_sha256",
        "asym_id",
        "left_sequence_number",
        "right_sequence_number",
        "left_atom_id",
        "right_atom_id",
    }
    assert all(
        set(atom.metadata["mmcif_archive_standard_l_peptide_topology"]) == atom_keys
        for atom in system.atoms
    )
    assert all(
        set(bond.metadata["mmcif_archive_standard_l_peptide_topology"]) == bond_keys
        for bond in system.bonds
    )
    observation = parser_observation_document(system)
    assert STANDARD_L_PEPTIDE_RULE_MANIFEST_SHA256 in json.dumps(
        observation, sort_keys=True
    )
    provenance_marker = system.provenance.metadata[
        "mmcif_archive_standard_l_peptide_topology"
    ]
    assert provenance_marker["preparation_inventory_commitment_schema_id"] == (
        MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_PREPARATION_INVENTORY_COMMITMENT_SCHEMA_ID
    )
    assert provenance_marker["preparation_inventory_commitment_sha256"] == (
        mmcif_archive_standard_l_peptide_topology_preparation_inventory_sha256(system)
    )


def test_factory_artifacts_reject_receipt_forgery_and_cross_source_half_swap() -> None:
    first = round_trip_mmcif_archive_standard_l_peptide_topology_source(
        GLY_ALA.read_bytes(), source_id="source-A"
    )
    second = round_trip_mmcif_archive_standard_l_peptide_topology_source(
        GLY_ALA.read_bytes(), source_id="source-B"
    )

    with pytest.raises(TypeError):
        type(first._report)(
            first._source_ingest,
            first._write_result,
            first._reparsed_ingest,
            first._reemitted_write_result,
        )

    receipt = first._write_result._receipt
    object.__setattr__(receipt, "_document_bytes", b'{"claim_safe":true}')
    with pytest.raises(MmcifArchiveStandardLPeptideTopologyError) as exc_info:
        receipt.to_dict()
    assert exc_info.value.code == "crosswired_write_artifacts"

    report = second._report
    object.__setattr__(report, "_reparsed", first._reparsed_ingest)
    object.__setattr__(report, "_second", first._reemitted_write_result)
    with pytest.raises(MmcifArchiveStandardLPeptideTopologyError) as exc_info:
        report.to_dict()
    assert exc_info.value.code == "crosswired_round_trip_artifacts"
