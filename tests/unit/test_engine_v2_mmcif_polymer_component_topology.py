from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from betelgeuze_engine_v2.molecular.mmcif_polymer_component_topology import (
    MAX_MMCIF_POLYMER_COMPONENT_ATOM_ROWS,
    MAX_MMCIF_POLYMER_COMPONENT_BOND_ROWS,
    MAX_MMCIF_POLYMER_COMPONENT_MATERIALIZED_BONDS,
    MAX_MMCIF_POLYMER_COMPONENT_ROWS,
    MAX_MMCIF_POLYMER_COMPONENT_SEQUENCE_ROWS,
    MAX_MMCIF_POLYMER_COMPONENT_TOPOLOGY_INPUT_BYTES,
    MAX_MMCIF_POLYMER_COMPONENT_TOPOLOGY_OUTPUT_BYTES,
    MAX_MMCIF_POLYMER_COMPONENT_TOPOLOGY_OUTPUT_LINE_CHARS,
    MAX_MMCIF_POLYMER_COMPONENT_TOPOLOGY_PROJECTION_BYTES,
    MAX_MMCIF_POLYMER_COMPONENT_TOPOLOGY_SOURCE_ID_BYTES,
    MAX_MMCIF_POLYMER_COMPONENT_TOPOLOGY_TOKEN_CHARS,
    MMCIF_POLYMER_COMPONENT_TOPOLOGY_PARSER_NAME,
    MMCIF_POLYMER_COMPONENT_TOPOLOGY_PARSER_PEDIGREE_ID,
    MMCIF_POLYMER_COMPONENT_TOPOLOGY_PREPARATION_INVENTORY_COMMITMENT_SCHEMA_ID,
    MMCIF_POLYMER_COMPONENT_TOPOLOGY_PROFILE_ID,
    MmcifPolymerComponentAtomRow,
    MmcifPolymerComponentBondRow,
    MmcifPolymerComponentRow,
    MmcifPolymerComponentTopologyError,
    MmcifPolymerComponentTopologyIngestResult,
    MmcifPolymerComponentTopologyRoundTripReport,
    MmcifPolymerComponentTopologyRoundTripResult,
    MmcifPolymerComponentTopologyWriteReceipt,
    MmcifPolymerComponentTopologyWriteResult,
    mmcif_polymer_component_topology_projection_sha256,
    mmcif_polymer_component_topology_state_sha256,
    parse_mmcif_polymer_component_topology,
    round_trip_mmcif_polymer_component_topology_source,
    serialize_mmcif_polymer_component_topology,
    write_mmcif_polymer_component_topology,
)
from betelgeuze_engine_v2.molecular.observation import (
    attached_parser_observation_sha256_matches,
    mmcif_polymer_component_topology_preparation_inventory_sha256,
)
from betelgeuze_engine_v2.molecular.topology import (
    attached_canonical_topology_sha256_matches,
)


ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "v2_1_mmcif_polymer_component_topology"


def _fixture(name: str = "single_ala_like.cif") -> bytes:
    return (FIXTURE_ROOT / name).read_bytes()


def _replace_once(source: bytes, old: bytes, new: bytes) -> bytes:
    assert old and source.count(old) == 1
    return source.replace(old, new, 1)


def _remove_atom_site_row(source: bytes, atom_id: int) -> bytes:
    marker = f"ATOM {atom_id} ".encode("ascii")
    lines = source.splitlines(keepends=True)
    selected = [line for line in lines if line.startswith(marker)]
    assert len(selected) == 1
    return source.replace(selected[0], b"", 1)


def _rename_component_definitions_only(source: bytes, old: bytes, new: bytes) -> bytes:
    start = source.index(b"loop_\n_chem_comp.id")
    end = source.index(b"loop_\n_atom_site.group_PDB")
    component_region = source[start:end]
    assert old in component_region
    return source[:start] + component_region.replace(old, new) + source[end:]


def test_profile_constants_and_hard_caps_are_exact() -> None:
    assert MMCIF_POLYMER_COMPONENT_TOPOLOGY_PROFILE_ID == (
        "strict_mmcif_polymer_component_topology_envelope/1.0.0"
    )
    assert MMCIF_POLYMER_COMPONENT_TOPOLOGY_PARSER_PEDIGREE_ID == (
        "betelgeuze.mmcif_polymer_component_topology_parser/1.0.0"
    )
    assert MAX_MMCIF_POLYMER_COMPONENT_TOPOLOGY_INPUT_BYTES == 64 * 1024 * 1024
    assert MAX_MMCIF_POLYMER_COMPONENT_TOPOLOGY_OUTPUT_BYTES == 64 * 1024 * 1024
    assert MAX_MMCIF_POLYMER_COMPONENT_TOPOLOGY_PROJECTION_BYTES == 64 * 1024 * 1024
    assert MAX_MMCIF_POLYMER_COMPONENT_SEQUENCE_ROWS == 100_000
    assert MAX_MMCIF_POLYMER_COMPONENT_ROWS == 4_096
    assert MAX_MMCIF_POLYMER_COMPONENT_ATOM_ROWS == 80_000
    assert MAX_MMCIF_POLYMER_COMPONENT_BOND_ROWS == 120_000
    assert MAX_MMCIF_POLYMER_COMPONENT_MATERIALIZED_BONDS == 120_000
    assert MAX_MMCIF_POLYMER_COMPONENT_TOPOLOGY_TOKEN_CHARS == 2_048
    assert MAX_MMCIF_POLYMER_COMPONENT_TOPOLOGY_OUTPUT_LINE_CHARS == 2_048
    assert MAX_MMCIF_POLYMER_COMPONENT_TOPOLOGY_SOURCE_ID_BYTES == 4_096


def test_single_component_materializes_only_explicit_intra_residue_state() -> None:
    ingest = parse_mmcif_polymer_component_topology(
        _fixture(), source_id="fixture:single"
    )
    system = ingest.system
    document = ingest.to_dict()

    assert system.atom_count == 6
    assert len(system.residues) == 1
    assert len(system.bonds) == 5
    assert {atom.element for atom in system.atoms} == {"H", "C", "N", "O"}
    assert all(atom.formal_charge_known for atom in system.atoms)
    assert all(
        "mmcif_polymer_component_topology" in atom.metadata for atom in system.atoms
    )
    assert all(
        "mmcif_polymer_component_topology" in bond.metadata for bond in system.bonds
    )
    assert all(
        system.atoms[bond.atom_i].residue_index
        == system.atoms[bond.atom_j].residue_index
        for bond in system.bonds
    )
    assert system.provenance.parser_name == MMCIF_POLYMER_COMPONENT_TOPOLOGY_PARSER_NAME
    assert (
        system.provenance.metadata["mmcif_polymer_component_topology"][
            "parser_pedigree_id"
        ]
        == MMCIF_POLYMER_COMPONENT_TOPOLOGY_PARSER_PEDIGREE_ID
    )
    preparation_inventory_marker = system.provenance.metadata[
        "mmcif_polymer_component_topology"
    ]
    assert (
        preparation_inventory_marker["preparation_inventory_commitment_schema_id"]
        == MMCIF_POLYMER_COMPONENT_TOPOLOGY_PREPARATION_INVENTORY_COMMITMENT_SCHEMA_ID
    )
    assert preparation_inventory_marker[
        "preparation_inventory_commitment_sha256"
    ] == mmcif_polymer_component_topology_preparation_inventory_sha256(system)
    assert attached_canonical_topology_sha256_matches(system)
    assert attached_parser_observation_sha256_matches(system)
    assert document["new_system_parser_pedigree_introduced"] is True
    assert document["only_intra_residue_component_bonds_materialized"] is True
    assert document["peptide_or_inter_residue_bonds_not_inferred"] is True


def test_repeated_fixture_preserves_elements_stereo_aromaticity_and_bond_orders() -> (
    None
):
    ingest = parse_mmcif_polymer_component_topology(
        _fixture("repeated_ala_xaa_ala.cif"), source_id="fixture:repeated"
    )
    system = ingest.system

    assert system.atom_count == 22
    assert len(system.residues) == 3
    assert len(system.bonds) == 20
    assert {atom.element for atom in system.atoms} == {"H", "C", "N", "O", "S"}
    assert {row.stereo for row in ingest.component_atom_rows} == {"N", "R", "S"}
    assert {atom.stereo for atom in system.atoms} == {"none", "R", "S"}
    assert {row.value_order for row in ingest.component_bond_rows} == {
        "SING",
        "DOUB",
        "TRIP",
        "AROM",
    }
    assert {bond.order for bond in system.bonds} == {1.0, 1.5, 2.0, 3.0}
    aromatic_atoms = {atom.name for atom in system.atoms if atom.aromatic}
    assert aromatic_atoms == {"CG", "CD", "CE"}
    assert sum(bond.aromatic for bond in system.bonds) == 3
    assert all(
        system.atoms[bond.atom_i].residue_index
        == system.atoms[bond.atom_j].residue_index
        for bond in system.bonds
    )


def test_category_order_variant_normalizes_to_one_semantic_state() -> None:
    first = parse_mmcif_polymer_component_topology(
        _fixture("single_ala_like.cif"), source_id="same"
    )
    variant = parse_mmcif_polymer_component_topology(
        _fixture("single_ala_like_category_order_variant.cif"), source_id="same"
    )

    assert first.full_source_sha256 != variant.full_source_sha256
    assert first.component_projection_sha256 == variant.component_projection_sha256
    assert first.topology_state_sha256 == variant.topology_state_sha256
    assert first.augmented_topology_sha256 == variant.augmented_topology_sha256
    assert first.source_binding_sha256 != variant.source_binding_sha256
    assert serialize_mmcif_polymer_component_topology(first) == (
        serialize_mmcif_polymer_component_topology(variant)
    )


def test_source_id_is_bound_outside_source_independent_semantic_state() -> None:
    source = _fixture()
    first = parse_mmcif_polymer_component_topology(source, source_id="source:a")
    second = parse_mmcif_polymer_component_topology(source, source_id="source:b")

    assert first.topology_state_sha256 == second.topology_state_sha256
    assert first.component_projection_sha256 == second.component_projection_sha256
    assert first.source_id_sha256 != second.source_id_sha256
    assert first.source_binding_sha256 != second.source_binding_sha256
    assert (
        first.to_dict()["augmented_system_snapshot_sha256"]
        != (second.to_dict()["augmented_system_snapshot_sha256"])
    )


def test_type_and_bond_order_case_are_canonicalized() -> None:
    source = _replace_once(_fixture(), b"'L-peptide linking'", b"'l-PEPTIDE LINKING'")
    source = _replace_once(source, b"ALA C O DOUB N N 4", b"ALA C O doub N N 4")
    ingest = parse_mmcif_polymer_component_topology(source)
    payload = serialize_mmcif_polymer_component_topology(ingest)

    assert ingest.component_rows[0].component_type == "L-peptide linking"
    assert b"ALA 'L-peptide linking' 0" in payload
    assert b"ALA C O DOUB N N 4" in payload


def test_round_trip_binds_exact_reparse_and_stable_second_emission() -> None:
    result = round_trip_mmcif_polymer_component_topology_source(
        _fixture("repeated_ala_xaa_ala.cif"), source_id="fixture:round-trip"
    )
    report = result.report

    assert report.component_projection_equal
    assert report.topology_state_equal
    assert report.topology_equal
    assert report.emitted_source_reparsed_exact
    assert report.second_emission_byte_stable
    assert result.write_result.payload == result.reparsed_ingest._full_source
    assert result.write_result.payload == result.reemitted_write_result.payload


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    (
        (
            lambda source: _replace_once(
                source, b"'L-peptide linking'", b"'D-peptide linking'"
            ),
            "unsupported_component_type",
        ),
        (
            lambda source: _remove_atom_site_row(source, 6),
            "component_instance_atom_coverage_mismatch",
        ),
        (
            lambda source: _replace_once(
                source, b"ALA C O DOUB N N 4", b"ALA C O QUAD N N 4"
            ),
            "unsupported_component_bond_order",
        ),
        (
            lambda source: _replace_once(
                source, b"ALA C O DOUB N N 4", b"ALA C O DOUB Y N 4"
            ),
            "component_bond_aromatic_mismatch",
        ),
        (
            lambda source: _replace_once(
                source, b"ALA CB C 0 N N 6", b"ALA CB P 0 N N 6"
            ),
            "unsupported_component_element",
        ),
    ),
)
def test_profile_rejects_missing_or_unsupported_component_state(
    mutation, expected_code: str
) -> None:
    with pytest.raises(MmcifPolymerComponentTopologyError) as caught:
        parse_mmcif_polymer_component_topology(mutation(_fixture()))
    assert caught.value.code == expected_code


def test_missing_cartesian_residue_coverage_fails_closed() -> None:
    source = _fixture("repeated_ala_xaa_ala.cif")
    for atom_id in range(7, 17):
        source = _remove_atom_site_row(source, atom_id)
    with pytest.raises(MmcifPolymerComponentTopologyError) as caught:
        parse_mmcif_polymer_component_topology(source)
    assert caught.value.code == "polymer_cartesian_residue_coverage_mismatch"


def test_aromatic_atom_and_bond_endpoint_sets_must_be_consistent() -> None:
    source = _replace_once(
        _fixture("repeated_ala_xaa_ala.cif"),
        b"XAA CG C 0 Y N 6",
        b"XAA CG C 0 N N 6",
    )
    with pytest.raises(MmcifPolymerComponentTopologyError) as caught:
        parse_mmcif_polymer_component_topology(source)
    assert caught.value.code == "component_atom_bond_aromatic_mismatch"


def test_input_line_character_cap_fails_closed() -> None:
    source = b"#" + (b"x" * 2_048) + b"\n" + _fixture()
    with pytest.raises(MmcifPolymerComponentTopologyError) as caught:
        parse_mmcif_polymer_component_topology(source)
    assert caught.value.code == "input_line_too_long"


def test_component_set_must_equal_sequence_monomer_set() -> None:
    source = _rename_component_definitions_only(
        _fixture("repeated_ala_xaa_ala.cif"),
        b"XAA ",
        b"GLY ",
    )
    with pytest.raises(MmcifPolymerComponentTopologyError) as caught:
        parse_mmcif_polymer_component_topology(source)
    assert caught.value.code == "component_definition_coverage_mismatch"


def test_known_atom_site_charge_is_cross_checked_and_unknown_is_filled() -> None:
    accepted = _replace_once(
        _fixture(), b"1.00 10.00 ? 1 ALA A N 1", b"1.00 10.00 0 1 ALA A N 1"
    )
    ingest = parse_mmcif_polymer_component_topology(accepted)
    assert ingest.system.atoms[0].metadata["formal_charge_source"] == (
        "cross_checked_atom_site_and_chem_comp_atom"
    )
    rejected = _replace_once(
        _fixture(), b"1.00 10.00 ? 1 ALA A N 1", b"1.00 10.00 1 1 ALA A N 1"
    )
    with pytest.raises(MmcifPolymerComponentTopologyError) as caught:
        parse_mmcif_polymer_component_topology(rejected)
    assert caught.value.code == "component_atom_charge_mismatch"


def test_factory_only_artifacts_reject_public_construction() -> None:
    with pytest.raises(TypeError):
        MmcifPolymerComponentRow(
            comp_id="ALA", component_type="L-peptide linking", formal_charge=0
        )
    with pytest.raises(TypeError):
        MmcifPolymerComponentAtomRow(
            comp_id="ALA",
            atom_id="CA",
            element="C",
            charge=0,
            aromatic=False,
            stereo="S",
            ordinal=1,
        )
    with pytest.raises(TypeError):
        MmcifPolymerComponentBondRow(
            comp_id="ALA",
            atom_id_1="N",
            atom_id_2="CA",
            value_order="SING",
            order=1.0,
            aromatic=False,
            stereo="N",
            ordinal=1,
        )
    for artifact in (
        MmcifPolymerComponentTopologyIngestResult,
        MmcifPolymerComponentTopologyWriteReceipt,
        MmcifPolymerComponentTopologyWriteResult,
        MmcifPolymerComponentTopologyRoundTripReport,
        MmcifPolymerComponentTopologyRoundTripResult,
    ):
        with pytest.raises(TypeError):
            artifact()  # type: ignore[call-arg]


def test_ingest_tamper_is_rejected_by_all_digest_helpers() -> None:
    ingest = parse_mmcif_polymer_component_topology(_fixture())
    object.__setattr__(ingest, "_projection_bytes", b"{}")
    for access in (
        lambda: ingest.system,
        lambda: ingest.to_dict(),
        lambda: mmcif_polymer_component_topology_projection_sha256(ingest),
        lambda: mmcif_polymer_component_topology_state_sha256(ingest),
        lambda: write_mmcif_polymer_component_topology(ingest),
    ):
        with pytest.raises(MmcifPolymerComponentTopologyError) as caught:
            access()
        assert caught.value.code == "stale_ingest_binding"


def test_public_nested_artifacts_are_fresh_and_detached() -> None:
    ingest = parse_mmcif_polymer_component_topology(_fixture(), source_id="detached")
    first_system = ingest.system
    second_system = ingest.system
    assert first_system is not second_system
    first_system.coordinates[0, 0, 0] = 999.0
    assert float(ingest.system.coordinates[0, 0, 0]) != 999.0
    assert ingest.carrier_ingest is not ingest.carrier_ingest
    assert ingest.component_rows is not ingest.component_rows
    assert ingest.component_rows[0] is not ingest.component_rows[0]

    write_result = write_mmcif_polymer_component_topology(ingest)
    assert write_result.receipt is not write_result.receipt
    round_trip = round_trip_mmcif_polymer_component_topology_source(
        _fixture(), source_id="detached"
    )
    assert round_trip.source_ingest is not round_trip.source_ingest
    assert round_trip.write_result is not round_trip.write_result
    assert round_trip.report is not round_trip.report


def test_science_runtime_claim_and_v2_1_promotions_remain_false() -> None:
    ingest = parse_mmcif_polymer_component_topology(_fixture())
    result = round_trip_mmcif_polymer_component_topology_source(_fixture())
    false_fields = {
        "source_authenticated",
        "independent_chemistry_established",
        "independent_valence_established",
        "independent_aromaticity_established",
        "independent_stereo_established",
        "chemistry_inferred",
        "peptide_bonds_inferred",
        "inter_residue_bonds_interpreted",
        "preparation_ready",
        "generic_preparation_ready",
        "parameterability_assessed",
        "physics_supported",
        "runtime_eligible",
        "simulation_ready",
        "execution_authorized",
        "claim_safe",
        "general_mmcif_topology_complete",
        "general_mmcif_round_trip_evidence_ready",
        "all_format_round_trip_evidence_ready",
        "v2_1_complete",
        "v2_1_promoted",
        "v2_1_common_ingest_promotion_eligible",
    }
    for document in (
        ingest.to_dict(),
        ingest.system.metadata["mmcif_polymer_component_topology"],
        result.report.to_dict(),
        result.to_dict(),
    ):
        assert all(document[field] is False for field in false_fields)


def test_raw_source_and_canonical_output_digests_bind_exact_bytes() -> None:
    source = _fixture()
    ingest = parse_mmcif_polymer_component_topology(source)
    write = write_mmcif_polymer_component_topology(ingest)
    assert ingest.full_source_sha256 == hashlib.sha256(source).hexdigest()
    assert (
        write.receipt.output_source_sha256 == hashlib.sha256(write.payload).hexdigest()
    )
