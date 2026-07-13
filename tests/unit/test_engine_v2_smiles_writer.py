from __future__ import annotations

from dataclasses import fields, replace
import hashlib

import pytest
import torch

from betelgeuze_engine_v2.molecular import (
    SMILES_EZ_STEREO_PROJECTION_SCHEMA_ID,
    SMILES_TETRAHEDRAL_STEREO_PROJECTION_SCHEMA_ID,
    SMILES_REPRESENTABLE_STATE_SCHEMA_ID,
    SMILES_ROUND_TRIP_REPORT_SCHEMA_ID,
    SMILES_WRITER_VERSION,
    SMILES_WRITE_RECEIPT_SCHEMA_ID,
    SmilesParseError,
    UnitCell,
    SmilesWriteError,
    canonical_all_atom_snapshot_digest,
    canonical_topology_sha256,
    parse_smiles,
    parser_observation_sha256,
    round_trip_smiles_source,
    serialize_smiles,
    smiles_representable_state_sha256,
    write_smiles,
)
from betelgeuze_engine_v2.molecular import smiles as smiles_module
from betelgeuze_engine_v2.molecular import smiles_writer as writer_module


@pytest.fixture
def supported_local_rdkit(monkeypatch: pytest.MonkeyPatch) -> str:
    try:
        _, rd_base = smiles_module._import_rdkit()
    except (ImportError, ModuleNotFoundError):
        pytest.skip("RDKit is unavailable in this test environment")
    version = rd_base.rdkitVersion
    monkeypatch.setattr(
        smiles_module,
        "_SUPPORTED_RDKIT_VERSIONS",
        frozenset({version}),
    )
    return version


def _assert_error(system, code: str) -> None:
    with pytest.raises(SmilesWriteError) as exc_info:
        write_smiles(system)
    assert exc_info.value.code == code


def _replace_provenance_metadata(system, key: str, value):
    metadata = dict(system.provenance.metadata)
    metadata[key] = value
    return replace(
        system,
        provenance=replace(system.provenance, metadata=metadata),
    )


def _replace_atom(system, **changes):
    return replace(
        system,
        atoms=(replace(system.atoms[0], **changes), *system.atoms[1:]),
    )


def _public_artifact_kwargs(artifact) -> dict[str, object]:
    return {
        field.name: getattr(artifact, field.name)
        for field in fields(artifact)
        if not field.name.startswith("_")
    }


@pytest.mark.parametrize(
    "source",
    [
        b"C",
        b"CC",
        b"CCC",
        b"CCCC",
        b"CCO",
        b"CC(C)C",
        b"N",
        b"O",
        b"COC",
        b"ClCCl",
        b"C=C",
        b"C#C",
        b"C#N",
        b"O=C=O",
        b"CC#N",
        b"CC(C)=O",
        b"C=C(C)O",
        b"C.C",
        b"C.CC",
        b"C.CC(C)=O",
        b"C#N.C=C",
        b"CCO.ClCCl",
        b"CC.CC",
        b"C=C.C=C",
        b"C.C.C",
        b"C.N.O",
    ],
)
def test_canonical_implicit_hydrogen_trees_are_exact_fixed_points(
    supported_local_rdkit: str,
    source: bytes,
) -> None:
    result = round_trip_smiles_source(source, source_id="canonical-tree")
    before = result.source_ingest.system
    after = result.reparsed_ingest.system

    assert result.write_result.payload == source
    assert b"\n" not in source and b"\r" not in source
    assert serialize_smiles(before) == source
    assert serialize_smiles(after) == source
    assert write_smiles(after).payload == source
    assert canonical_topology_sha256(before) == canonical_topology_sha256(after)
    assert smiles_representable_state_sha256(before) == (
        smiles_representable_state_sha256(after)
    )
    assert parser_observation_sha256(before) == parser_observation_sha256(after)
    assert torch.equal(before.coordinates, after.coordinates)
    assert tuple(before.coordinates.shape) == (0, before.atom_count, 3)


@pytest.mark.parametrize(
    ("source", "expected_tokens", "expected_charged_count", "expected_total"),
    [
        (b"[Cl-]", ("[Cl-]",), 1, -1),
        (b"[F-]", ("[F-]",), 1, -1),
        (b"C[O-]", ("C", "[O-]"), 1, -1),
        (b"O=C[O-]", ("O", "C", "[O-]"), 1, -1),
        (b"CC(=O)[O-]", ("C", "C", "O", "[O-]"), 1, -1),
        (b"C[N+](C)(C)C", ("C", "[N+]", "C", "C", "C"), 1, 1),
        (b"CC[N+](C)(C)C", ("C", "C", "[N+]", "C", "C", "C"), 1, 1),
        (
            b"C[N+](C)(C)C.[Cl-]",
            ("C", "[N+]", "C", "C", "C", "[Cl-]"),
            2,
            0,
        ),
        (b"[Cl-].[F-]", ("[Cl-]", "[F-]"), 2, -2),
        (b"C.C[O-]", ("C", "C", "[O-]"), 1, -1),
        (b"C.[Cl-]", ("C", "[Cl-]"), 1, -1),
    ],
)
def test_bounded_parser_observed_formal_charge_tokens_are_exact_fixed_points(
    supported_local_rdkit: str,
    source: bytes,
    expected_tokens: tuple[str, ...],
    expected_charged_count: int,
    expected_total: int,
) -> None:
    result = round_trip_smiles_source(source, source_id="bounded-formal-charge")
    before = writer_module._validate_write_state(result.source_ingest.system)
    after = writer_module._validate_write_state(result.reparsed_ingest.system)
    receipt = result.write_result.receipt
    document = before.representable_state_document

    assert result.write_result.payload == source
    assert before.source_atom_tokens == expected_tokens
    assert before.source_atom_tokens == after.source_atom_tokens
    assert before.charged_source_atom_count == expected_charged_count
    assert before.charged_source_atom_count == after.charged_source_atom_count
    assert before.formal_charge_total == expected_total
    assert before.formal_charge_total == after.formal_charge_total
    assert before.formal_charge_profile_id == (
        "ordered_acyclic_organic_forest_bounded_formal_charge/1.0.0"
    )
    assert receipt.formal_charge_profile_id == before.formal_charge_profile_id
    assert receipt.charged_source_atom_count == expected_charged_count
    assert receipt.formal_charge_total == expected_total
    assert document["source_atom_tokens"] == list(expected_tokens)
    assert document["charged_source_atom_count"] == expected_charged_count
    assert document["formal_charge_total"] == expected_total
    assert document["coverage"]["formal_charge_total"] == expected_total
    assert result.source_ingest.coverage.chemistry_supported is False
    assert result.source_ingest.coverage.preparation_ready is False
    assert result.source_ingest.coverage.claim_safe is False
    assert result.report.to_dict()["claim_safe"] is False


def test_unit_charge_long_form_normalizes_but_source_order_is_not_reordered(
    supported_local_rdkit: str,
) -> None:
    normalized = round_trip_smiles_source(b"[Cl-1]")

    assert normalized.write_result.payload == b"[Cl-]"
    _assert_error(
        parse_smiles(b"[N+](C)(C)(C)C").system,
        "normalized_smiles_hash_mismatch",
    )


@pytest.mark.parametrize(
    ("source", "ring_size", "cyclic_component_index", "closure_index"),
    [
        (b"C1CC1", 3, 0, 2),
        (b"C1CCC1", 4, 0, 3),
        (b"C1CCCC1", 5, 0, 4),
        (b"C1CCCCC1", 6, 0, 5),
        (b"C1CCCCCC1", 7, 0, 6),
        (b"C1CCCCCCC1", 8, 0, 7),
        (b"CC1CCCCC1", 6, 0, 6),
        (b"FC1CCCCC1", 6, 0, 6),
        (b"C1CCOC1", 5, 0, 4),
        (b"C1CCNCC1", 6, 0, 5),
        (b"C1CCSCC1", 6, 0, 5),
        (b"C[N+]1(C)CCCCC1", 6, 0, 7),
        (b"C=C1CCCCC1", 6, 0, 6),
        (b"C.C1CC1", 3, 1, 2),
        (b"C1CC1.CC", 3, 0, 3),
        (b"C1CC1.[Cl-]", 3, 0, 2),
    ],
)
def test_bounded_simple_unicyclic_sources_are_exact_fixed_points(
    supported_local_rdkit: str,
    source: bytes,
    ring_size: int,
    cyclic_component_index: int,
    closure_index: int,
) -> None:
    result = round_trip_smiles_source(source, source_id="simple-ring")
    before = writer_module._validate_write_state(result.source_ingest.system)
    after = writer_module._validate_write_state(result.reparsed_ingest.system)
    receipt = result.write_result.receipt
    cycle = before.cycle_projection_document

    assert result.write_result.payload == source
    assert before.cycle_projection_sha256 == after.cycle_projection_sha256
    assert before.ring_closure_count == 1
    assert before.cyclic_component_count == 1
    assert before.cyclic_component_index == cyclic_component_index
    assert before.component_cyclomatic_numbers[cyclic_component_index] == 1
    assert sum(before.component_cyclomatic_numbers) == 1
    assert before.ring_size == ring_size
    assert len(before.ring_atom_indices) == ring_size
    assert len(before.ring_bond_indices) == ring_size
    assert before.ring_closure_source_bond_index == closure_index
    assert closure_index == before.source_bond_count - 1
    assert closure_index in before.ring_bond_indices
    assert before.ring_closure_endpoints == (
        before.ring_open_source_atom_index,
        before.ring_close_source_atom_index,
    )
    assert before.ring_open_source_atom_index < before.ring_close_source_atom_index
    assert (
        before.source_tree_edge_count
        == before.source_atom_count - before.fragment_count
    )
    assert before.source_bond_count == before.source_tree_edge_count + 1
    assert sum(marker == "1" for marker in before.source_ring_marker_table) == 2
    assert before.source_ring_marker_table[before.ring_open_source_atom_index] == "1"
    assert before.source_ring_marker_table[before.ring_close_source_atom_index] == "1"
    assert before.source_ring_marker_table == after.source_ring_marker_table
    assert receipt.input_cycle_projection_sha256 == before.cycle_projection_sha256
    assert receipt.cycle_projection_schema_id == (
        "betelgeuze.smiles_component_cycle_projection/1.3.0"
    )
    assert receipt.cycle_profile_id == (
        "at_most_one_simple_nonaromatic_3_8_member_all_single_bond_source_ring/1.0.0"
    )
    assert receipt.formal_charge_profile_id == (
        "ordered_forest_with_one_simple_unicyclic_component_bounded_formal_charge/1.0.0"
    )
    assert (
        receipt.bond_count == receipt.expanded_atom_count - receipt.fragment_count + 1
    )
    assert receipt.source_bond_count == before.source_bond_count
    assert receipt.source_tree_edge_count == before.source_tree_edge_count
    assert receipt.ring_closure_count == 1
    assert receipt.cyclic_component_count == 1
    assert receipt.ring_size == ring_size
    assert receipt.ring_closure_source_bond_index == closure_index
    assert receipt.ring_bond_profile_id == ("all_single_nonaromatic_stereo_none/1.0.0")
    assert receipt.ring_double_bond_count == 0
    assert receipt.ring_double_source_bond_index is None
    assert cycle["ring_closure_label"] == 1
    assert cycle["ring_bond_profile_id"] == ("all_single_nonaromatic_stereo_none/1.0.0")
    assert cycle["ring_double_bond_count"] == 0
    assert cycle["ring_double_source_bond_index"] is None
    assert len(cycle["ring_bond_order_table"]) == ring_size
    assert all(entry["bond_token"] == "" for entry in cycle["ring_bond_order_table"])
    assert cycle["ring_bond_order_table"][-1]["role"] == "closure"
    assert cycle["source_ring_marker_table"] == list(before.source_ring_marker_table)
    assert cycle["ring_closure_endpoints"] == list(before.ring_closure_endpoints)
    assert cycle["ring_open_source_atom_index"] == (before.ring_open_source_atom_index)
    assert cycle["ring_close_source_atom_index"] == (
        before.ring_close_source_atom_index
    )
    report = result.report.to_dict()
    assert report["cycle_projection_sha256_equal"] is True
    assert (
        report["input_cycle_projection_sha256"]
        == (report["reparsed_cycle_projection_sha256"])
    )
    for field_name in (
        "preparation_ready",
        "parameterability_assessed",
        "simulation_ready",
        "claim_safe",
    ):
        assert receipt.to_dict()[field_name] is False
        assert report[field_name] is False


@pytest.mark.parametrize(
    (
        "source",
        "ring_size",
        "double_index",
        "closure_index",
        "generated_hydrogens",
        "formal_charge_total",
    ),
    [
        (b"C1=CC1", 3, 0, 2, 4, 0),
        (b"C1=CCCCC1", 6, 0, 5, 10, 0),
        (b"C1=CCCCCCC1", 8, 0, 7, 14, 0),
        (b"CC1=CCCCC1", 6, 1, 6, 12, 0),
        (b"FC1=CCCCC1", 6, 1, 6, 9, 0),
        (b"C1=CCOCC1", 6, 0, 5, 8, 0),
        (b"C1=CCNCC1", 6, 0, 5, 9, 0),
        (b"C1=CCSCC1", 6, 0, 5, 8, 0),
        (b"C[N+]1(C)CC=CCC1", 6, 4, 7, 14, 1),
        (b"[O-]C1=CCCCC1", 6, 1, 6, 9, -1),
        (b"C.C1=CCCCC1", 6, 0, 5, 14, 0),
        (b"C1=CCCCC1.CC", 6, 0, 6, 16, 0),
    ],
)
def test_bounded_one_double_ring_sources_are_exact_fixed_points(
    supported_local_rdkit: str,
    source: bytes,
    ring_size: int,
    double_index: int,
    closure_index: int,
    generated_hydrogens: int,
    formal_charge_total: int,
) -> None:
    result = round_trip_smiles_source(source, source_id="one-double-ring")
    before = writer_module._validate_write_state(result.source_ingest.system)
    after = writer_module._validate_write_state(result.reparsed_ingest.system)
    receipt = result.write_result.receipt
    cycle = before.cycle_projection_document

    assert result.write_result.payload == source
    assert before.cycle_profile_id == (
        "at_most_one_simple_nonaromatic_3_8_member_source_ring_with_exactly_one_"
        "nonclosure_double_bond/1.0.0"
    )
    assert before.ring_bond_profile_id == (
        "one_nonclosure_double_otherwise_single_nonaromatic_stereo_none/1.0.0"
    )
    assert before.ring_size == ring_size
    assert before.ring_double_bond_count == 1
    assert before.ring_double_source_bond_index == double_index
    assert before.ring_closure_source_bond_index == closure_index
    assert closure_index == before.source_bond_count - 1
    assert double_index < closure_index
    assert before.generated_hydrogen_count == generated_hydrogens
    assert before.formal_charge_total == formal_charge_total
    assert before.cycle_projection_sha256 == after.cycle_projection_sha256
    assert before.ring_bond_order_table == after.ring_bond_order_table

    order_table = cycle["ring_bond_order_table"]
    assert [entry["source_bond_index"] for entry in order_table] == sorted(
        before.ring_bond_indices
    )
    assert sum(entry["bond_token"] == "=" for entry in order_table) == 1
    double_entry = next(entry for entry in order_table if entry["bond_token"] == "=")
    closure_entry = next(entry for entry in order_table if entry["role"] == "closure")
    assert double_entry["source_bond_index"] == double_index
    assert double_entry["role"] == "tree"
    assert closure_entry["source_bond_index"] == closure_index
    assert closure_entry["bond_token"] == ""
    assert cycle["ring_double_bond_count"] == 1
    assert cycle["ring_double_source_bond_index"] == double_index

    assert receipt.cycle_profile_id == before.cycle_profile_id
    assert receipt.ring_bond_profile_id == before.ring_bond_profile_id
    assert receipt.ring_double_bond_count == 1
    assert receipt.ring_double_source_bond_index == double_index
    assert receipt.input_cycle_projection_sha256 == before.cycle_projection_sha256
    assert result.report.input_cycle_projection_sha256 == (
        result.report.reparsed_cycle_projection_sha256
    )
    assert result.source_ingest.coverage.typed_atom_stereo_count == 0
    assert result.source_ingest.coverage.typed_bond_stereo_count == 0
    for atom in result.source_ingest.system.atoms[: before.source_atom_count]:
        if atom.formal_charge:
            assert all(
                generated.metadata["parent_source_atom_index"] != atom.index
                for generated in result.source_ingest.system.atoms[
                    before.source_atom_count :
                ]
            )
    for field_name in (
        "preparation_ready",
        "parameterability_assessed",
        "simulation_ready",
        "claim_safe",
    ):
        assert receipt.to_dict()[field_name] is False
        assert result.report.to_dict()[field_name] is False


@pytest.mark.parametrize(
    "source",
    [
        b"C2=CCCCC2",
        b"C9=CCCCC9",
        b"C%10=CCCCC%10",
        b"C1=C-C-C-C-C1",
    ],
)
def test_one_double_ring_labels_and_single_bond_spelling_normalize(
    supported_local_rdkit: str,
    source: bytes,
) -> None:
    result = round_trip_smiles_source(source, source_id="one-double-normalization")

    assert result.write_result.payload == b"C1=CCCCC1"
    assert result.write_result.receipt.ring_double_bond_count == 1
    assert result.write_result.receipt.ring_double_source_bond_index == 0
    assert result.write_result.receipt.ring_closure_source_bond_index == 5
    assert (
        result.write_result.receipt.output_source_sha256
        == hashlib.sha256(b"C1=CCCCC1").hexdigest()
    )


@pytest.mark.parametrize(
    ("source", "ring_size", "bracket_hydrogens", "formal_charge_total"),
    [
        (b"b1ccccc1", 6, 0, 0),
        (b"c1ccccc1", 6, 0, 0),
        (b"c1ccncc1", 6, 0, 0),
        (b"c1ccoc1", 5, 0, 0),
        (b"c1ccpcc1", 6, 0, 0),
        (b"c1ccsc1", 5, 0, 0),
        (b"[bH-]1ccccc1", 6, 1, -1),
        (b"[c-]1ccccc1", 6, 0, -1),
        (b"c1cc[cH-]c1", 5, 1, -1),
        (b"c1cc[nH]c1", 5, 1, 0),
        (b"c1c[nH]cn1", 5, 1, 0),
        (b"c1cc[n-]c1", 5, 0, -1),
        (b"c1cc[nH+]cc1", 6, 1, 1),
        (b"c1cc[o+]cc1", 6, 0, 1),
        (b"c1cc[oH+]c1", 5, 1, 1),
        (b"c1cc[pH]c1", 5, 1, 0),
        (b"c1cc[p-]c1", 5, 0, -1),
        (b"c1cc[pH+]cc1", 6, 1, 1),
        (b"c1cc[s+]cc1", 6, 0, 1),
        (b"c1cc[sH+]c1", 5, 1, 1),
    ],
)
def test_selected_fully_aromatic_ring_tokens_are_exact_fixed_points(
    supported_local_rdkit: str,
    source: bytes,
    ring_size: int,
    bracket_hydrogens: int,
    formal_charge_total: int,
) -> None:
    result = round_trip_smiles_source(source, source_id="aromatic-fixed-point")
    state = writer_module._validate_write_state(result.source_ingest.system)
    receipt = result.write_result.receipt
    aromatic = state.aromatic_projection_document

    assert result.write_result.payload == source
    assert state.ring_size == ring_size
    assert state.aromatic_source_atom_count == ring_size
    assert state.aromatic_source_bond_count == ring_size
    assert state.bracket_explicit_hydrogen_count == bracket_hydrogens
    assert state.implicit_hydrogen_count + bracket_hydrogens == (
        state.generated_hydrogen_count
    )
    assert state.formal_charge_total == formal_charge_total
    assert state.cycle_profile_id == (
        "at_most_one_simple_fully_aromatic_5_6_member_b_c_n_o_p_s_source_ring/1.0.0"
    )
    assert state.ring_bond_profile_id == ("all_order_1_5_aromatic_stereo_none/1.0.0")
    assert state.aromatic_atom_state_profile_id == (
        "selected_b_c_n_o_p_s_unit_charge_and_canonical_bracket_hydrogen_"
        "aromatic_atom_tokens/1.0.0"
    )
    assert state.formal_charge_profile_id == (
        "ordered_forest_with_one_simple_fully_aromatic_5_6_member_ring_selected_"
        "unit_charge_and_canonical_bracket_hydrogen_states/1.0.0"
    )
    assert aromatic["schema_id"] == ("betelgeuze.smiles_aromatic_ring_projection/1.0.0")
    assert len(aromatic["ring_atom_state_table"]) == ring_size
    assert len(aromatic["ring_bond_state_table"]) == ring_size
    assert len(aromatic["bracket_hydrogen_table"]) == bracket_hydrogens
    assert all(
        entry["aromatic"] is True
        and entry["formal_charge_known"] is True
        and type(entry["formal_charge"]) is int
        for entry in aromatic["ring_atom_state_table"]
    )
    assert all(
        entry["order_ieee754_binary64_be"] == "3ff8000000000000"
        and entry["aromatic"] is True
        and entry["bond_token"] == ""
        and entry["stereo"] == "none"
        and entry["role"] in {"tree", "closure"}
        for entry in aromatic["ring_bond_state_table"]
    )
    assert (
        sum(entry["role"] == "closure" for entry in aromatic["ring_bond_state_table"])
        == 1
    )
    assert all(
        entry["hydrogen_origin"] == "bracket_explicit"
        for entry in aromatic["bracket_hydrogen_table"]
    )
    assert result.source_ingest.coverage.aromatic_atom_count == ring_size
    assert (
        "aromaticity_not_independently_verified"
        in result.source_ingest.coverage.blockers
    )
    assert receipt.input_aromatic_projection_sha256 == (
        state.aromatic_projection_sha256
    )
    assert receipt.aromatic_projection_schema_id == (
        "betelgeuze.smiles_aromatic_ring_projection/1.0.0"
    )
    assert receipt.aromatic_source_atom_count == ring_size
    assert receipt.aromatic_source_bond_count == ring_size
    assert receipt.bracket_explicit_hydrogen_count == bracket_hydrogens
    assert result.report.input_aromatic_projection_sha256 == (
        result.report.reparsed_aromatic_projection_sha256
    )
    assert result.report.to_dict()["aromatic_projection_sha256_equal"] is True
    for document in (receipt.to_dict(), result.report.to_dict()):
        assert document["preparation_ready"] is False
        assert document["parameterability_assessed"] is False
        assert document["simulation_ready"] is False
        assert document["claim_safe"] is False


@pytest.mark.parametrize(
    ("source", "normalized"),
    [
        (b"c2ccccc2", b"c1ccccc1"),
        (b"c9ccccc9", b"c1ccccc1"),
        (b"c%10ccccc%10", b"c1ccccc1"),
        (b"c1:c:c:c:c:c:1", b"c1ccccc1"),
        (b"C1=CC=CC=C1", b"c1ccccc1"),
        (b"C1=CC=NC=C1", b"c1ccncc1"),
        (b"C1=CC=[NH+]C=C1", b"c1cc[nH+]cc1"),
        (b"c%10cc[nH]c%10", b"c1cc[nH]c1"),
    ],
)
def test_selected_aromatic_labels_bonds_and_kekule_spelling_normalize(
    supported_local_rdkit: str,
    source: bytes,
    normalized: bytes,
) -> None:
    result = round_trip_smiles_source(source, source_id="aromatic-normalization")

    assert result.write_result.payload == normalized
    assert result.write_result.receipt.output_source_sha256 == (
        hashlib.sha256(normalized).hexdigest()
    )
    assert result.write_result.receipt.parent_source_sha256 == (
        hashlib.sha256(source).hexdigest()
    )


@pytest.mark.parametrize(
    "source",
    [
        b"Cc1ccccc1",
        b"Cc1ccc(C)cc1",
        b"COc1ccncc1",
        b"C#Cc1ccccc1",
        b"O=Cc1ccccc1",
        b"CC(=O)Nc1ccccc1",
        b"Cc1cc[nH]c1",
        b"C.c1ccccc1",
        b"CC.c1ccoc1",
        b"[Cl-].c1cc[nH+]cc1",
    ],
)
def test_selected_aromatic_substituents_and_fragments_are_exact_fixed_points(
    supported_local_rdkit: str,
    source: bytes,
) -> None:
    result = round_trip_smiles_source(source, source_id="aromatic-context")

    assert result.write_result.payload == source
    assert result.write_result.receipt.aromatic_source_atom_count in {5, 6}
    assert result.write_result.receipt.aromatic_source_bond_count in {5, 6}
    assert result.source_ingest.coverage.chemistry_supported is False
    assert result.source_ingest.coverage.parameterability_assessed is False
    assert result.source_ingest.coverage.preparation_ready is False
    assert result.source_ingest.coverage.claim_safe is False


@pytest.mark.parametrize(
    "source",
    [
        b"n1ccccc1",
        b"[nH]1cccc1",
        b"o1cccc1",
        b"p1ccccc1",
        b"C1=CNC=C1",
        b"c1ccccc1C",
        b"c1ccc(C)cc1",
        b"c1ccccc1.C",
        b"c1cc[nH+]cc1.[Cl-]",
    ],
)
def test_selected_aromatic_writer_does_not_reorder_source_atoms_or_fragments(
    supported_local_rdkit: str,
    source: bytes,
) -> None:
    _assert_error(parse_smiles(source).system, "normalized_smiles_hash_mismatch")


def test_same_count_aromatic_atom_state_projections_cannot_be_cross_wired(
    supported_local_rdkit: str,
) -> None:
    left = round_trip_smiles_source(b"c1ccnnc1", source_id="pyridazine")
    right = round_trip_smiles_source(b"c1cncnc1", source_id="pyrimidine")
    left_state = writer_module._validate_write_state(left.source_ingest.system)
    right_state = writer_module._validate_write_state(right.source_ingest.system)

    for field_name in (
        "output_byte_count",
        "source_atom_count",
        "expanded_atom_count",
        "bond_count",
        "fragment_count",
        "generated_hydrogen_count",
        "implicit_hydrogen_count",
        "bracket_explicit_hydrogen_count",
        "source_bond_count",
        "source_tree_edge_count",
        "ring_closure_count",
        "ring_size",
        "aromatic_source_atom_count",
        "aromatic_source_bond_count",
        "charged_source_atom_count",
        "formal_charge_total",
    ):
        assert getattr(left.write_result.receipt, field_name) == getattr(
            right.write_result.receipt, field_name
        )
    assert left_state.aromatic_projection_sha256 != (
        right_state.aromatic_projection_sha256
    )
    assert left_state.cycle_projection_document["aromatic_projection_sha256"] == (
        left_state.aromatic_projection_sha256
    )
    assert right_state.cycle_projection_document["aromatic_projection_sha256"] == (
        right_state.aromatic_projection_sha256
    )
    assert left_state.cycle_projection_sha256 != right_state.cycle_projection_sha256
    with pytest.raises(ValueError, match="regenerated SMILES bindings"):
        type(left.write_result)(
            payload=left.write_result.payload,
            receipt=left.write_result.receipt,
            input_system=right.source_ingest.system,
            _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
        )
    with pytest.raises(ValueError, match="cross-consistent"):
        type(left)(
            source_ingest=right.source_ingest,
            write_result=left.write_result,
            reparsed_ingest=left.reparsed_ingest,
            report=left.report,
            _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
        )


def test_same_count_aromatic_bracket_token_elements_cannot_be_cross_wired(
    supported_local_rdkit: str,
) -> None:
    nitrogen = round_trip_smiles_source(b"c1cc[nH]c1", source_id="pyrrole")
    phosphorus = round_trip_smiles_source(b"c1cc[pH]c1", source_id="phosphole")
    left = nitrogen.write_result.receipt
    right = phosphorus.write_result.receipt

    for field_name in (
        "output_byte_count",
        "source_atom_count",
        "expanded_atom_count",
        "bond_count",
        "generated_hydrogen_count",
        "implicit_hydrogen_count",
        "bracket_explicit_hydrogen_count",
        "ring_size",
        "aromatic_source_atom_count",
        "aromatic_source_bond_count",
        "charged_source_atom_count",
        "formal_charge_total",
    ):
        assert getattr(left, field_name) == getattr(right, field_name)
    assert left.input_aromatic_projection_sha256 != (
        right.input_aromatic_projection_sha256
    )
    with pytest.raises(ValueError, match="regenerated SMILES bindings"):
        type(nitrogen.write_result)(
            payload=nitrogen.write_result.payload,
            receipt=nitrogen.write_result.receipt,
            input_system=phosphorus.source_ingest.system,
            _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
        )


def test_aromatic_projection_receipt_and_report_hashes_cannot_be_forged(
    supported_local_rdkit: str,
) -> None:
    result = round_trip_smiles_source(b"c1cc[nH]c1")
    receipt_kwargs = _public_artifact_kwargs(result.write_result.receipt)
    receipt_kwargs["input_aromatic_projection_sha256"] = "0" * 64
    forged_receipt = type(result.write_result.receipt)(
        **receipt_kwargs,
        _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
    )
    with pytest.raises(ValueError, match="regenerated SMILES bindings"):
        type(result.write_result)(
            payload=result.write_result.payload,
            receipt=forged_receipt,
            input_system=result.source_ingest.system,
            _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
        )

    report_kwargs = _public_artifact_kwargs(result.report)
    report_kwargs["input_aromatic_projection_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="aromatic-projection"):
        type(result.report)(
            **report_kwargs,
            _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
        )

    coherent_report_kwargs = _public_artifact_kwargs(result.report)
    coherent_report_kwargs["input_aromatic_projection_sha256"] = "0" * 64
    coherent_report_kwargs["reparsed_aromatic_projection_sha256"] = "0" * 64
    forged_report = type(result.report)(
        **coherent_report_kwargs,
        _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
    )
    with pytest.raises(ValueError, match="cross-consistent"):
        type(result)(
            source_ingest=result.source_ingest,
            write_result=result.write_result,
            reparsed_ingest=result.reparsed_ingest,
            report=forged_report,
            _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
        )


@pytest.mark.parametrize(
    ("field_name", "forged_value"),
    [
        ("implicit_hydrogen_count", True),
        ("implicit_hydrogen_count", 5.0),
        ("bracket_explicit_hydrogen_count", False),
        ("bracket_explicit_hydrogen_count", 1.0),
        ("aromatic_source_atom_count", True),
        ("aromatic_source_atom_count", 5.0),
        ("aromatic_source_bond_count", False),
        ("aromatic_source_bond_count", 5.0),
    ],
)
def test_aromatic_receipt_counts_are_exact_typed(
    supported_local_rdkit: str,
    field_name: str,
    forged_value: object,
) -> None:
    result = round_trip_smiles_source(b"c1cc[nH]c1")
    kwargs = _public_artifact_kwargs(result.write_result.receipt)
    kwargs[field_name] = forged_value
    with pytest.raises((TypeError, ValueError)):
        type(result.write_result.receipt)(
            **kwargs,
            _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
        )


def test_aromatic_ring_atom_bond_and_stereo_tampering_fails_closed(
    supported_local_rdkit: str,
) -> None:
    benzene = parse_smiles(b"c1ccccc1").system
    de_aromatized_atom = replace(
        benzene,
        atoms=(replace(benzene.atoms[0], aromatic=False), *benzene.atoms[1:]),
    )
    _assert_error(de_aromatized_atom, "unsupported_aromatic_ring_state")

    de_aromatized_bond = replace(
        benzene,
        bonds=(
            replace(benzene.bonds[0], order=1.0, aromatic=False),
            *benzene.bonds[1:],
        ),
    )
    _assert_error(de_aromatized_bond, "unsupported_aromatic_ring_state")

    stereo_bond = replace(
        benzene,
        bonds=(replace(benzene.bonds[0], stereo="unknown"), *benzene.bonds[1:]),
    )
    _assert_error(stereo_bond, "unsupported_bond_stereo")

    substituted = parse_smiles(b"Cc1ccccc1").system
    aromatic_substituent = replace(
        substituted,
        atoms=(replace(substituted.atoms[0], aromatic=True), *substituted.atoms[1:]),
    )
    _assert_error(aromatic_substituent, "unsupported_aromatic_ring_state")

    seven = parse_smiles(b"C1CCCCCC1").system
    source_count = seven.metadata["source_atom_count"]
    generated_count = seven.metadata["generated_hydrogen_count"]
    source_bond_count = len(seven.bonds) - generated_count
    fully_aromatic_seven = replace(
        seven,
        atoms=tuple(
            replace(atom, aromatic=True) if atom.index < source_count else atom
            for atom in seven.atoms
        ),
        bonds=tuple(
            replace(bond, order=1.5, aromatic=True)
            if bond.index < source_bond_count
            else bond
            for bond in seven.bonds
        ),
    )
    _assert_error(fully_aromatic_seven, "unsupported_aromatic_ring_size")


def test_aromatic_bracket_hydrogen_origin_and_ordinal_are_exact(
    supported_local_rdkit: str,
) -> None:
    system = parse_smiles(b"c1cc[nH]c1").system
    source_count = system.metadata["source_atom_count"]
    bracket_atom_index = next(
        atom.index
        for atom in system.atoms[source_count:]
        if atom.metadata["hydrogen_origin"] == "bracket_explicit"
    )
    bracket_bond_index = next(
        bond.index
        for bond in system.bonds
        if bond.metadata.get("hydrogen_origin") == "bracket_explicit"
    )

    atom_metadata = dict(system.atoms[bracket_atom_index].metadata)
    atom_metadata["hydrogen_origin"] = "implicit"
    bond_metadata = dict(system.bonds[bracket_bond_index].metadata)
    bond_metadata["hydrogen_origin"] = "implicit"
    origin_tampered = replace(
        system,
        atoms=tuple(
            replace(atom, metadata=atom_metadata)
            if atom.index == bracket_atom_index
            else atom
            for atom in system.atoms
        ),
        bonds=tuple(
            replace(bond, metadata=bond_metadata)
            if bond.index == bracket_bond_index
            else bond
            for bond in system.bonds
        ),
    )
    _assert_error(origin_tampered, "unsupported_aromatic_hydrogen_state")

    ordinal_metadata = dict(system.atoms[bracket_atom_index].metadata)
    ordinal_metadata["hydrogen_ordinal"] = True
    ordinal_tampered = replace(
        system,
        atoms=tuple(
            replace(atom, metadata=ordinal_metadata)
            if atom.index == bracket_atom_index
            else atom
            for atom in system.atoms
        ),
    )
    _assert_error(ordinal_tampered, "inconsistent_generated_hydrogen_metadata")

    bond_origin_metadata = dict(system.bonds[bracket_bond_index].metadata)
    bond_origin_metadata["hydrogen_origin"] = "implicit"
    bond_origin_tampered = replace(
        system,
        bonds=tuple(
            replace(bond, metadata=bond_origin_metadata)
            if bond.index == bracket_bond_index
            else bond
            for bond in system.bonds
        ),
    )
    _assert_error(bond_origin_tampered, "inconsistent_generated_hydrogen_bond")

    parent_metadata = dict(system.atoms[bracket_atom_index].metadata)
    parent_metadata["parent_source_atom_index"] = 2
    parent_bond_metadata = dict(system.bonds[bracket_bond_index].metadata)
    parent_bond_metadata["parent_source_atom_index"] = 2
    parent_tampered = replace(
        system,
        atoms=tuple(
            replace(atom, metadata=parent_metadata)
            if atom.index == bracket_atom_index
            else atom
            for atom in system.atoms
        ),
        bonds=tuple(
            replace(
                bond,
                atom_i=min(2, bracket_atom_index),
                atom_j=max(2, bracket_atom_index),
                metadata=parent_bond_metadata,
            )
            if bond.index == bracket_bond_index
            else bond
            for bond in system.bonds
        ),
    )
    _assert_error(parent_tampered, "generated_hydrogen_order_changed")


def test_aromatic_and_nonaromatic_profile_sets_cannot_be_cross_wired(
    supported_local_rdkit: str,
) -> None:
    aromatic = round_trip_smiles_source(b"c1ccccc1")
    nonaromatic = round_trip_smiles_source(b"C1CCCCC1")
    aromatic_receipt = aromatic.write_result.receipt
    nonaromatic_receipt = nonaromatic.write_result.receipt

    aromatic_as_nonaromatic = _public_artifact_kwargs(aromatic_receipt)
    for field_name in (
        "input_cycle_projection_sha256",
        "input_aromatic_projection_sha256",
        "cycle_profile_id",
        "ring_bond_profile_id",
        "aromatic_source_atom_count",
        "aromatic_source_bond_count",
        "aromatic_ring_profile_id",
        "aromatic_atom_state_profile_id",
        "formal_charge_profile_id",
    ):
        aromatic_as_nonaromatic[field_name] = getattr(nonaromatic_receipt, field_name)
    forged_nonaromatic = type(aromatic_receipt)(
        **aromatic_as_nonaromatic,
        _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
    )
    with pytest.raises(ValueError, match="regenerated SMILES bindings"):
        type(aromatic.write_result)(
            payload=aromatic.write_result.payload,
            receipt=forged_nonaromatic,
            input_system=aromatic.source_ingest.system,
            _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
        )

    nonaromatic_as_aromatic = _public_artifact_kwargs(nonaromatic_receipt)
    for field_name in (
        "input_cycle_projection_sha256",
        "input_aromatic_projection_sha256",
        "cycle_profile_id",
        "ring_bond_profile_id",
        "aromatic_source_atom_count",
        "aromatic_source_bond_count",
        "aromatic_ring_profile_id",
        "aromatic_atom_state_profile_id",
        "formal_charge_profile_id",
    ):
        nonaromatic_as_aromatic[field_name] = getattr(aromatic_receipt, field_name)
    forged_aromatic = type(nonaromatic_receipt)(
        **nonaromatic_as_aromatic,
        _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
    )
    with pytest.raises(ValueError, match="regenerated SMILES bindings"):
        type(nonaromatic.write_result)(
            payload=nonaromatic.write_result.payload,
            receipt=forged_aromatic,
            input_system=nonaromatic.source_ingest.system,
            _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
        )


@pytest.mark.parametrize(
    "source",
    [
        b"CCO",
        b"C=C",
        b"C#N",
        b"C.CC",
        b"C1CCCCC1",
        b"C[N+]1(C)CCCCC1",
        b"C1CC1.[Cl-]",
        b"C1=CCCCC1",
        b"CC1=CCCCC1",
    ],
)
def test_v1_5_acyclic_and_nonaromatic_ring_payload_bytes_are_unchanged(
    supported_local_rdkit: str,
    source: bytes,
) -> None:
    result = round_trip_smiles_source(source, source_id="v1.5-byte-regression")

    assert result.write_result.payload == source
    assert result.write_result.receipt.aromatic_source_atom_count == 0
    assert result.write_result.receipt.aromatic_source_bond_count == 0
    assert result.write_result.receipt.bracket_explicit_hydrogen_count == 0


@pytest.mark.parametrize(
    "source",
    [
        b"C0CC0",
        b"C2CC2",
        b"C9CC9",
        b"C%10CC%10",
        b"C%99CC%99",
        b"C1-C-C-1",
        b"C1(CC1)",
    ],
)
def test_raw_ring_labels_and_single_bond_spelling_normalize_to_label_one(
    supported_local_rdkit: str,
    source: bytes,
) -> None:
    result = round_trip_smiles_source(source, source_id="ring-normalization")

    assert result.write_result.payload == b"C1CC1"
    assert b"%10" not in result.write_result.payload
    assert (
        result.write_result.receipt.parent_source_sha256
        == hashlib.sha256(source).hexdigest()
    )
    assert (
        result.write_result.receipt.output_source_sha256
        == hashlib.sha256(b"C1CC1").hexdigest()
    )


def test_potential_stereogenicity_remains_unassessed_without_typed_stereo_state(
    supported_local_rdkit: str,
) -> None:
    result = round_trip_smiles_source(b"FC=CF")
    coverage = result.source_ingest.coverage
    preservation_scope = result.write_result.receipt.to_dict()["preservation_scope"]

    assert result.write_result.payload == b"FC=CF"
    assert coverage.typed_atom_stereo_count == 0
    assert coverage.typed_bond_stereo_count == 0
    assert "stereochemistry_completeness_not_assessed" in coverage.blockers
    assert (
        "known_minus_one_zero_or_plus_one_formal_charge_nonisotopic_optionally_mapped_nonaromatic_organic_subset_atoms_with_bounded_parser_typed_tetrahedral_state"
        in preservation_scope
    )
    assert (
        "single_double_or_triple_nonaromatic_source_bonds_with_bounded_tree_or_selected_eight_member_ring_parser_typed_e_or_z_double_bonds"
        in preservation_scope
    )


@pytest.mark.parametrize(
    (
        "source",
        "typed_count",
        "directional_count",
        "expected_parent_tokens",
        "expected_ring_markers",
    ),
    [
        (b"F/C=C/F", 1, 2, ("", "/", "=", "/"), ("", "", "", "")),
        (b"F/C=C\\F", 1, 2, ("", "/", "=", "\\"), ("", "", "", "")),
        (
            b"F/C(Cl)=C(/Br)I",
            1,
            2,
            ("", "/", "", "=", "/", ""),
            ("", "", "", "", "", ""),
        ),
        (
            b"F/C(Cl)=C(\\Br)I",
            1,
            2,
            ("", "/", "", "=", "\\", ""),
            ("", "", "", "", "", ""),
        ),
        (
            b"F/C=C(\\Br)I",
            1,
            2,
            ("", "/", "=", "\\", ""),
            ("", "", "", "", ""),
        ),
        (
            b"F/C=C(/Br)I",
            1,
            2,
            ("", "/", "=", "/", ""),
            ("", "", "", "", ""),
        ),
        (
            b"F/C=C/C=C/F",
            2,
            3,
            ("", "/", "=", "/", "=", "/"),
            ("", "", "", "", "", ""),
        ),
        (
            b"F/C=C\\C=C/F",
            2,
            3,
            ("", "/", "=", "\\", "=", "/"),
            ("", "", "", "", "", ""),
        ),
        (
            b"F/C=C/F.F/C=C\\F",
            2,
            4,
            ("", "/", "=", "/", "", "/", "=", "\\"),
            ("", "", "", "", "", "", "", ""),
        ),
        (
            b"C1=C/CCCCCC/1",
            1,
            2,
            ("", "=", "/", "", "", "", "", ""),
            ("1", "", "", "", "", "", "", "/1"),
        ),
        (
            b"C1=C\\CCCCCC/1",
            1,
            2,
            ("", "=", "\\", "", "", "", "", ""),
            ("1", "", "", "", "", "", "", "/1"),
        ),
        (
            b"F/C=C1/CC1Cl",
            1,
            2,
            ("", "/", "=", "/", "", ""),
            ("", "", "1", "", "1", ""),
        ),
        (
            b"F/C=C1\\CC1Cl",
            1,
            2,
            ("", "/", "=", "\\", "", ""),
            ("", "", "1", "", "1", ""),
        ),
        (
            b"F/C(Cl)=C1/CCCOC1",
            1,
            2,
            ("", "/", "", "=", "/", "", "", "", ""),
            ("", "", "", "1", "", "", "", "", "1"),
        ),
        (
            b"CC1CCC/C1=C/F",
            1,
            2,
            ("", "", "", "", "", "/", "=", "/"),
            ("", "1", "", "", "", "1", "", ""),
        ),
        (
            b"CC1C/C=C/CCCC1",
            1,
            2,
            ("", "", "", "/", "=", "/", "", "", ""),
            ("", "1", "", "", "", "", "", "", "1"),
        ),
        (
            b"CC1C/C=C\\CCCC1",
            1,
            2,
            ("", "", "", "/", "=", "\\", "", "", ""),
            ("", "1", "", "", "", "", "", "", "1"),
        ),
        (
            b"F/C=C/C1C/C=C/CCCC1",
            2,
            4,
            ("", "/", "=", "/", "", "/", "=", "/", "", "", ""),
            ("", "", "", "1", "", "", "", "", "", "", "1"),
        ),
    ],
)
def test_bounded_parser_typed_ez_is_exact_round_trip_projection(
    supported_local_rdkit: str,
    source: bytes,
    typed_count: int,
    directional_count: int,
    expected_parent_tokens: tuple[str, ...],
    expected_ring_markers: tuple[str, ...],
) -> None:
    result = round_trip_smiles_source(source, source_id="bounded-ez")
    before = writer_module._validate_write_state(result.source_ingest.system)
    after = writer_module._validate_write_state(result.reparsed_ingest.system)
    receipt = result.write_result.receipt
    projection = before.ez_stereo_projection_document

    assert result.write_result.payload == source
    assert before.typed_ez_bond_count == typed_count
    assert before.directional_source_bond_count == directional_count
    assert before.source_parent_bond_tokens == expected_parent_tokens
    assert before.source_ring_marker_table == expected_ring_markers
    assert before.ez_stereo_projection_sha256 == after.ez_stereo_projection_sha256
    assert before.ez_stereo_projection_document == after.ez_stereo_projection_document
    assert projection["schema_id"] == SMILES_EZ_STEREO_PROJECTION_SCHEMA_ID
    assert projection["profile_id"] == before.ez_stereo_profile_id
    assert projection["typed_ez_bond_count"] == typed_count
    assert projection["directional_source_bond_count"] == directional_count
    assert len(projection["stereo_bond_table"]) == typed_count
    assert len(projection["directional_bond_table"]) == directional_count
    assert (
        projection["selected_simple_ring_single_direction_carriers_supported"] is True
    )
    assert projection["independent_cip_assignment_claimed"] is False
    assert projection["stereo_completeness_claimed"] is False
    assert projection["stereo_geometry_claimed"] is False
    assert receipt.input_ez_stereo_projection_sha256 == (
        before.ez_stereo_projection_sha256
    )
    assert receipt.ez_stereo_projection_schema_id == (
        SMILES_EZ_STEREO_PROJECTION_SCHEMA_ID
    )
    assert receipt.typed_ez_bond_count == typed_count
    assert receipt.directional_source_bond_count == directional_count
    assert result.report.input_ez_stereo_projection_sha256 == (
        result.report.reparsed_ez_stereo_projection_sha256
    )
    assert result.report.to_dict()["ez_stereo_projection_sha256_equal"] is True
    assert result.source_ingest.coverage.typed_bond_stereo_count == typed_count
    assert "cip_assignment_not_independently_verified" in (
        result.source_ingest.coverage.blockers
    )
    for document in (receipt.to_dict(), result.report.to_dict()):
        for field_name in (
            "preparation_ready",
            "parameterability_assessed",
            "simulation_ready",
            "claim_safe",
        ):
            assert document[field_name] is False


@pytest.mark.parametrize(
    ("source", "canonical"),
    [
        (b"F\\C=C\\F", b"F/C=C/F"),
        (b"F\\C=C/F", b"F/C=C\\F"),
        (b"C1=C\\CCCCCC\\1", b"C1=C/CCCCCC/1"),
        (b"C1=C/CCCCCC\\1", b"C1=C\\CCCCCC/1"),
    ],
)
def test_raw_ez_direction_gauge_normalizes_to_one_canonical_spelling(
    supported_local_rdkit: str,
    source: bytes,
    canonical: bytes,
) -> None:
    result = round_trip_smiles_source(source, source_id="ez-gauge-normalization")

    assert result.write_result.payload == canonical
    assert result.write_result.receipt.parent_source_sha256 == (
        hashlib.sha256(source).hexdigest()
    )
    assert result.write_result.receipt.output_source_sha256 == (
        hashlib.sha256(canonical).hexdigest()
    )


def test_ez_projection_binds_tree_and_ring_closure_lexical_orientation(
    supported_local_rdkit: str,
) -> None:
    result = round_trip_smiles_source(b"C1=C/CCCCCC/1")
    state = writer_module._validate_write_state(result.source_ingest.system)
    projection = state.ez_stereo_projection_document
    stereo_row = projection["stereo_bond_table"][0]
    directional_rows = {
        row["source_bond_index"]: row for row in projection["directional_bond_table"]
    }

    assert stereo_row["direction_carrier_source_bond_indices"] == [7, 1]
    assert stereo_row["direction_carrier_emitted_toward_stereo_endpoint"] == [
        True,
        False,
    ]
    assert stereo_row["emission_orientation_parity_flipped"] is True
    assert directional_rows[1]["atom_indices"] == [1, 2]
    assert directional_rows[1]["emitted_from_source_atom_index"] == 1
    assert directional_rows[1]["emitted_to_source_atom_index"] == 2
    assert directional_rows[1]["emission_role"] == "tree"
    assert directional_rows[7]["atom_indices"] == [0, 7]
    assert directional_rows[7]["emitted_from_source_atom_index"] == 7
    assert directional_rows[7]["emitted_to_source_atom_index"] == 0
    assert directional_rows[7]["emission_role"] == "ring_closure"


def test_ez_typed_state_and_stereo_neighbor_tampering_fail_closed(
    supported_local_rdkit: str,
) -> None:
    system = parse_smiles(b"F/C=C/F").system
    double = system.bonds[1]

    _assert_error(
        replace(
            system,
            bonds=(
                system.bonds[0],
                replace(double, stereo="Z"),
                *system.bonds[2:],
            ),
        ),
        "normalized_smiles_hash_mismatch",
    )
    for forged_references in ([0, 0], [0, 2], [True, 3], [0], [0, 3, 2]):
        forged_metadata = dict(double.metadata)
        forged_metadata["stereo_atom_indices"] = forged_references
        _assert_error(
            replace(
                system,
                bonds=(
                    system.bonds[0],
                    replace(double, metadata=forged_metadata),
                    *system.bonds[2:],
                ),
            ),
            "inconsistent_ez_stereo_atoms",
        )

    _assert_error(
        replace(
            system,
            bonds=(
                system.bonds[0],
                replace(double, stereo="unknown"),
                *system.bonds[2:],
            ),
        ),
        "unsupported_bond_stereo",
    )
    _assert_error(
        replace(
            system,
            bonds=(replace(system.bonds[0], stereo="E"), *system.bonds[1:]),
        ),
        "canonical_validation_failed",
    )


def test_ring_ez_scope_is_exactly_the_selected_eight_member_projection(
    supported_local_rdkit: str,
) -> None:
    seven = parse_smiles(b"C1=CCCCCC1").system
    double = seven.bonds[0]
    metadata = dict(double.metadata)
    metadata["stereo_atom_indices"] = [6, 2]
    forged = replace(
        seven,
        bonds=(replace(double, stereo="E", metadata=metadata), *seven.bonds[1:]),
    )

    _assert_error(forged, "unsupported_ez_ring_stereo")


def test_ez_outside_lowest_index_normalized_spelling_subset_fails_closed(
    supported_local_rdkit: str,
) -> None:
    nonlowest_carrier = parse_smiles(b"F/C=C(F)/C1=C/CCCCCC1").system
    symmetric_center_reorder = parse_smiles(b"C/C=C/C=C\\C").system

    _assert_error(nonlowest_carrier, "normalized_smiles_hash_mismatch")
    _assert_error(symmetric_center_reorder, "normalized_smiles_hash_mismatch")


def test_ez_projection_receipt_and_report_hashes_cannot_be_forged(
    supported_local_rdkit: str,
) -> None:
    result = round_trip_smiles_source(b"F/C=C/F")
    receipt_kwargs = _public_artifact_kwargs(result.write_result.receipt)
    receipt_kwargs["input_ez_stereo_projection_sha256"] = "0" * 64
    forged_receipt = type(result.write_result.receipt)(
        **receipt_kwargs,
        _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
    )
    with pytest.raises(ValueError, match="regenerated SMILES bindings"):
        type(result.write_result)(
            payload=result.write_result.payload,
            receipt=forged_receipt,
            input_system=result.source_ingest.system,
            _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
        )

    report_kwargs = _public_artifact_kwargs(result.report)
    report_kwargs["input_ez_stereo_projection_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="E/Z stereo-projection"):
        type(result.report)(
            **report_kwargs,
            _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
        )

    coherent_report_kwargs = _public_artifact_kwargs(result.report)
    coherent_report_kwargs["input_ez_stereo_projection_sha256"] = "0" * 64
    coherent_report_kwargs["reparsed_ez_stereo_projection_sha256"] = "0" * 64
    forged_report = type(result.report)(
        **coherent_report_kwargs,
        _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
    )
    with pytest.raises(ValueError, match="cross-consistent"):
        type(result)(
            source_ingest=result.source_ingest,
            write_result=result.write_result,
            reparsed_ingest=result.reparsed_ingest,
            report=forged_report,
            _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
        )


@pytest.mark.parametrize(
    ("field_name", "forged_value", "message"),
    [
        (
            "ez_stereo_projection_schema_id",
            "betelgeuze.smiles_ez_stereo_projection/999.0.0",
            "ez_stereo_projection_schema_id is outside",
        ),
        (
            "ez_stereo_profile_id",
            "unbounded_ez/999.0.0",
            "ez_stereo_profile_id is outside",
        ),
        ("typed_ez_bond_count", 0, "stereo-free receipt"),
        (
            "directional_source_bond_count",
            1,
            "directional source-bond count is inconsistent",
        ),
    ],
)
def test_ez_receipt_schema_profile_and_count_invariants_fail_closed(
    supported_local_rdkit: str,
    field_name: str,
    forged_value: object,
    message: str,
) -> None:
    result = round_trip_smiles_source(b"F/C=C/F")
    receipt_kwargs = _public_artifact_kwargs(result.write_result.receipt)
    receipt_kwargs[field_name] = forged_value

    with pytest.raises(ValueError, match=message):
        type(result.write_result.receipt)(
            **receipt_kwargs,
            _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
        )


@pytest.mark.parametrize(
    ("source", "expected_children", "expected_parent_tokens"),
    [
        (b"CC(C)=O", ((1,), (2, 3), (), ()), ("", "", "", "=")),
        (b"C=C(C)O", ((1,), (2, 3), (), ()), ("", "=", "", "")),
        (b"CC#N", ((1,), (2,), ()), ("", "", "#")),
    ],
)
def test_branch_and_continuation_bond_tokens_are_parent_indexed_once(
    supported_local_rdkit: str,
    source: bytes,
    expected_children: tuple[tuple[int, ...], ...],
    expected_parent_tokens: tuple[str, ...],
) -> None:
    system = parse_smiles(source).system
    state = writer_module._validate_write_state(system)

    assert state.source_children == expected_children
    assert state.source_parent_bond_tokens == expected_parent_tokens
    assert state.source_parent_bond_tokens[0] == ""
    assert state.representable_state_document["emission_policy_id"] == (
        "ordered_source_forest_dfs_dot_bond_bounded_charge_selected_aromatic_atom_ring_label_bounded_tetrahedral_and_ez_direction_tokens/1.8.0"
    )
    assert state.representable_state_document["source_parent_bond_tokens"] == (
        list(expected_parent_tokens)
    )
    assert write_smiles(system).payload == source


@pytest.mark.parametrize(
    ("source", "expected_roots", "expected_parent_tokens"),
    [
        (b"C.C", (0, 1), ("", "")),
        (b"C.CC", (0, 1), ("", "", "")),
        (b"C.CC(C)=O", (0, 1), ("", "", "", "", "=")),
        (b"C#N.C=C", (0, 2), ("", "#", "", "=")),
        (b"CCO.ClCCl", (0, 3), ("", "", "", "", "", "")),
        (b"CC.CC", (0, 2), ("", "", "", "")),
        (b"C=C.C=C", (0, 2), ("", "=", "", "=")),
        (b"C.C.C", (0, 1, 2), ("", "", "")),
        (b"C.N.O", (0, 1, 2), ("", "", "")),
    ],
)
def test_ordered_source_forests_bind_roots_components_receipt_and_reparse(
    supported_local_rdkit: str,
    source: bytes,
    expected_roots: tuple[int, ...],
    expected_parent_tokens: tuple[str, ...],
) -> None:
    result = round_trip_smiles_source(source, source_id="ordered-forest")
    before = writer_module._validate_write_state(result.source_ingest.system)
    after = writer_module._validate_write_state(result.reparsed_ingest.system)
    receipt = result.write_result.receipt
    document = before.representable_state_document

    assert result.write_result.payload == source
    assert before.source_component_roots == expected_roots
    assert before.source_parent_bond_tokens == expected_parent_tokens
    assert before.fragment_count == len(expected_roots)
    assert before.source_component_roots == after.source_component_roots
    assert before.source_components == after.source_components
    assert before.expanded_components == after.expanded_components
    assert before.source_children == after.source_children
    assert before.source_parent_bond_tokens == after.source_parent_bond_tokens
    assert receipt.fragment_count == before.fragment_count
    assert receipt.bond_count == receipt.expanded_atom_count - receipt.fragment_count
    assert receipt.to_dict()["resource_limits"]["fragments"] == 256
    assert document["fragment_count"] == before.fragment_count
    assert document["source_component_roots"] == list(expected_roots)
    assert document["source_components"] == [
        list(component) for component in before.source_components
    ]
    assert document["expanded_components"] == [
        list(component) for component in before.expanded_components
    ]
    assert document["source_children"] == [
        list(children) for children in before.source_children
    ]
    assert document["source_parent_bond_tokens"] == list(expected_parent_tokens)
    assert document["coverage"]["fragment_count"] == before.fragment_count
    assert (
        "disconnected_fragment_roles_not_assessed" in document["coverage"]["blockers"]
    )
    assert result.reparsed_ingest.system.provenance.metadata["coverage"] == (
        result.reparsed_ingest.coverage.to_dict()
    )


@pytest.mark.parametrize(
    ("source", "expected_roots", "expected_source", "expected_expanded"),
    [
        (
            b"C.C",
            (0, 1),
            ((0,), (1,)),
            ((0, 2, 3, 4, 5), (1, 6, 7, 8, 9)),
        ),
        (
            b"C.CC",
            (0, 1),
            ((0,), (1, 2)),
            ((0, 3, 4, 5, 6), (1, 2, 7, 8, 9, 10, 11, 12)),
        ),
    ],
)
def test_graph_derived_components_bind_noncontiguous_parser_contexts(
    supported_local_rdkit: str,
    source: bytes,
    expected_roots: tuple[int, ...],
    expected_source: tuple[tuple[int, ...], ...],
    expected_expanded: tuple[tuple[int, ...], ...],
) -> None:
    system = parse_smiles(source).system
    state = writer_module._validate_write_state(system)

    assert state.source_component_roots == expected_roots
    assert state.source_components == expected_source
    assert state.expanded_components == expected_expanded
    assert tuple(residue.atom_indices for residue in system.residues) == (
        expected_expanded
    )
    assert tuple(residue.name for residue in system.residues) == tuple(
        f"L{index + 1}" for index in range(len(expected_roots))
    )
    assert tuple(chain.chain_id for chain in system.chains) == tuple(
        f"L{index + 1}" for index in range(len(expected_roots))
    )


def test_public_artifacts_bind_exact_state_and_never_promote(
    supported_local_rdkit: str,
) -> None:
    source = b"CCO"
    result = round_trip_smiles_source(source, source_id="ethanol-tree")
    receipt = result.write_result.receipt

    assert SMILES_WRITER_VERSION == "1.8.0"
    assert SMILES_REPRESENTABLE_STATE_SCHEMA_ID == (
        "betelgeuze.smiles_representable_state/1.8.0"
    )
    assert SMILES_WRITE_RECEIPT_SCHEMA_ID == ("betelgeuze.smiles_write_receipt/1.8.0")
    assert SMILES_ROUND_TRIP_REPORT_SCHEMA_ID == (
        "betelgeuze.smiles_round_trip_report/1.8.0"
    )
    assert receipt.parent_source_sha256 == hashlib.sha256(source).hexdigest()
    assert receipt.output_source_sha256 == hashlib.sha256(source).hexdigest()
    assert receipt.output_byte_count == len(source)
    assert receipt.input_snapshot_sha256 == canonical_all_atom_snapshot_digest(
        result.source_ingest.system
    )
    assert receipt.input_topology_sha256 == canonical_topology_sha256(
        result.source_ingest.system
    )
    assert receipt.input_representable_state_sha256 == (
        smiles_representable_state_sha256(result.source_ingest.system)
    )
    assert receipt.input_parser_observation_sha256 == parser_observation_sha256(
        result.source_ingest.system
    )
    assert receipt.formal_charge_profile_id == (
        "ordered_acyclic_organic_forest_bounded_formal_charge/1.0.0"
    )
    assert receipt.cycle_projection_schema_id == (
        "betelgeuze.smiles_component_cycle_projection/1.3.0"
    )
    assert receipt.ring_closure_count == 0
    assert receipt.cyclic_component_count == 0
    assert receipt.ring_size == 0
    assert receipt.ring_closure_source_bond_index is None
    assert receipt.ring_bond_profile_id is None
    assert receipt.ring_double_bond_count == 0
    assert receipt.ring_double_source_bond_index is None
    state = writer_module._validate_write_state(result.source_ingest.system)
    assert state.component_cyclomatic_numbers == (0,)
    assert state.source_ring_marker_table == ("", "", "")
    assert state.cycle_projection_document["ring_closure_label"] is None
    assert state.cycle_projection_document["ring_bond_profile_id"] is None
    assert state.cycle_projection_document["ring_double_bond_count"] == 0
    assert state.cycle_projection_document["ring_double_source_bond_index"] is None
    assert state.cycle_projection_document["ring_bond_order_table"] == []
    assert receipt.input_cycle_projection_sha256 == state.cycle_projection_sha256
    assert receipt.input_ez_stereo_projection_sha256 == (
        state.ez_stereo_projection_sha256
    )
    assert receipt.ez_stereo_projection_schema_id == (
        SMILES_EZ_STEREO_PROJECTION_SCHEMA_ID
    )
    assert receipt.typed_ez_bond_count == 0
    assert receipt.directional_source_bond_count == 0
    assert receipt.charged_source_atom_count == 0
    assert receipt.formal_charge_total == 0
    receipt_document = receipt.to_dict()
    assert receipt_document["schema_id"] == SMILES_WRITE_RECEIPT_SCHEMA_ID
    assert receipt_document["source_authentication_status"] == "not_authenticated"
    for field_name in (
        "preparation_ready",
        "parameterability_assessed",
        "simulation_ready",
        "claim_safe",
    ):
        assert receipt_document[field_name] is False
    assert receipt_document["receipt_sha256"] == receipt.receipt_sha256

    report = result.report.to_dict()
    assert report["schema_id"] == SMILES_ROUND_TRIP_REPORT_SCHEMA_ID
    for field_name in (
        "declared_projection_sha256_equal",
        "cycle_projection_sha256_equal",
        "ez_stereo_projection_sha256_equal",
        "canonical_topology_sha256_equal",
        "declared_parser_marker_projection_equal",
        "emitted_source_sha256_and_bytes_stable",
    ):
        assert report[field_name] is True
    assert report["full_canonical_snapshot_equality_claimed"] is False
    assert report["dynamic_source_provenance_equality_claimed"] is False
    assert report["claim_safe"] is False
    assert result.source_ingest.system.provenance.preparation_ready is False
    assert result.source_ingest.system.provenance.claim_safe is False
    assert result.reparsed_ingest.system.provenance.preparation_ready is False
    assert result.reparsed_ingest.system.provenance.claim_safe is False


@pytest.mark.parametrize(
    ("source", "normalized"),
    [
        (b"C-C", b"CC"),
        (b"C.C-C", b"C.CC"),
    ],
)
def test_raw_bond_spelling_normalizes_without_source_equality_claims(
    supported_local_rdkit: str,
    source: bytes,
    normalized: bytes,
) -> None:
    result = round_trip_smiles_source(source, source_id="explicit-single-bond")
    receipt = result.write_result.receipt
    report = result.report.to_dict()

    assert result.write_result.payload == normalized
    assert serialize_smiles(result.reparsed_ingest.system) == normalized
    assert receipt.parent_source_sha256 == hashlib.sha256(source).hexdigest()
    assert receipt.output_source_sha256 == hashlib.sha256(normalized).hexdigest()
    assert receipt.parent_source_sha256 != receipt.output_source_sha256
    assert report["full_canonical_snapshot_equality_claimed"] is False
    assert report["dynamic_source_provenance_equality_claimed"] is False
    assert report["input_snapshot_sha256"] != report["reparsed_snapshot_sha256"]
    assert report["emitted_source_sha256_and_bytes_stable"] is True


@pytest.mark.parametrize(
    "source",
    [
        b"OCC",
        b"C(C)(C)C",
        b"CC(=O)C",
        b"CC(O)=C",
        b"N#CC",
        b"CC=C",
        b"CC.C",
        b"C=C.C#N",
        b"ClCCl.CCO",
        b"C.O.N",
        b"C.N#C",
        b"N#C.C=C",
        b"C1CCCCC1C",
        b"C1(C)CCCCC1",
        b"C1CC(C)CCC1",
        b"C1CC1.C",
        b"CC.C1CC1",
    ],
)
def test_noncanonical_source_order_and_branch_spelling_are_rejected(
    supported_local_rdkit: str,
    source: bytes,
) -> None:
    _assert_error(
        parse_smiles(source, source_id="noncanonical-order").system,
        "normalized_smiles_hash_mismatch",
    )


@pytest.mark.parametrize(
    ("source", "typed_count", "mapped_count"),
    [
        (b"F[C@H](Cl)Br", 1, 0),
        (b"F[C@@H](Cl)Br", 1, 0),
        (b"F[C@](Cl)(Br)I", 1, 0),
        (b"F[C@@](Cl)(Br)I", 1, 0),
        (b"F[C@H:17](Cl)Br", 1, 1),
        (b"F[C@@H:17](Cl)Br", 1, 1),
        (b"C[N@+](F)(Cl)Br", 1, 0),
        (b"F[B@-](Cl)(Br)I", 1, 0),
        (b"C[P@+](F)(Cl)Br", 1, 0),
        (b"F[S@](Cl)(Br)I", 1, 0),
        (b"F[C@H](Cl)[C@@H](Br)I", 2, 0),
        (b"CC1CC[C@H](F)C1", 1, 0),
        (b"F/C=C/C[C@H](F)Cl", 1, 0),
        (b"C/C=C/C.F[C@H](Cl)Br", 1, 0),
    ],
)
def test_bounded_parser_typed_tetrahedral_state_is_an_exact_fixed_point(
    supported_local_rdkit: str,
    source: bytes,
    typed_count: int,
    mapped_count: int,
) -> None:
    result = round_trip_smiles_source(source, source_id="tetrahedral-fixed-point")
    before = writer_module._validate_write_state(result.source_ingest.system)
    after = writer_module._validate_write_state(result.reparsed_ingest.system)
    projection = before.tetrahedral_stereo_projection_document
    receipt = result.write_result.receipt
    report = result.report.to_dict()

    assert result.write_result.payload == source
    assert before.typed_tetrahedral_atom_count == typed_count
    assert before.mapped_source_atom_count == mapped_count
    assert before.tetrahedral_stereo_projection_sha256 == (
        after.tetrahedral_stereo_projection_sha256
    )
    assert projection["schema_id"] == SMILES_TETRAHEDRAL_STEREO_PROJECTION_SCHEMA_ID
    assert projection["typed_tetrahedral_atom_count"] == typed_count
    assert len(projection["atom_rows"]) == typed_count
    assert projection["calibration_trial_parse_count"] == 1
    assert projection["calibration_final_parse_count"] == 1
    assert projection["independent_cip_assignment"] is False
    assert projection["stereo_completeness_assessed"] is False
    assert projection["stereo_geometry_assessed"] is False
    for row in projection["atom_rows"]:
        assert row["trial_marker"] == "@"
        assert row["final_marker"] in {"@", "@@"}
        assert row["target_stereo"] == row["final_stereo"]
        assert row["target_rdkit_chiral_tag"] == row["final_rdkit_chiral_tag"]
        assert (
            len(row["source_neighbor_indices_in_bond_order"])
            + (row["bracket_explicit_hydrogen_count"])
            == 4
        )
    assert receipt.typed_tetrahedral_atom_count == typed_count
    assert receipt.mapped_source_atom_count == mapped_count
    assert receipt.tetrahedral_stereo_projection_schema_id == (
        SMILES_TETRAHEDRAL_STEREO_PROJECTION_SCHEMA_ID
    )
    assert receipt.input_tetrahedral_stereo_projection_sha256 == (
        before.tetrahedral_stereo_projection_sha256
    )
    assert report["input_tetrahedral_stereo_projection_sha256"] == (
        before.tetrahedral_stereo_projection_sha256
    )
    assert report["reparsed_tetrahedral_stereo_projection_sha256"] == (
        after.tetrahedral_stereo_projection_sha256
    )
    assert report["tetrahedral_stereo_projection_sha256_equal"] is True
    assert result.source_ingest.coverage.typed_atom_stereo_count == typed_count
    assert result.source_ingest.coverage.atom_map_count == mapped_count
    assert "cip_assignment_not_independently_verified" in (
        result.source_ingest.coverage.blockers
    )
    assert "stereo_geometry_unavailable" in result.source_ingest.coverage.blockers
    assert result.source_ingest.coverage.preparation_ready is False
    assert result.source_ingest.coverage.claim_safe is False


@pytest.mark.parametrize(
    ("source", "expected_total_bracket_h", "expected_aromatic_bracket_h_parents"),
    [
        (b"F[C@H](Cl)Br", 1, []),
        (b"F[C@H](Cl)Br.c1ccccc1", 1, []),
        (b"F[C@H](Cl)Br.c1cc[nH]c1", 2, [7]),
    ],
)
def test_tetrahedral_bracket_hydrogen_does_not_pollute_aromatic_projection(
    supported_local_rdkit: str,
    source: bytes,
    expected_total_bracket_h: int,
    expected_aromatic_bracket_h_parents: list[int],
) -> None:
    result = round_trip_smiles_source(source, source_id="tetrahedral-aromatic-split")
    state = writer_module._validate_write_state(result.source_ingest.system)
    projection = state.aromatic_projection_document
    rows = projection["bracket_hydrogen_table"]

    assert result.write_result.payload == source
    assert state.bracket_explicit_hydrogen_count == expected_total_bracket_h
    assert result.write_result.receipt.bracket_explicit_hydrogen_count == (
        expected_total_bracket_h
    )
    assert projection["aromatic_bracket_explicit_hydrogen_count"] == len(
        expected_aromatic_bracket_h_parents
    )
    assert [row["parent_source_atom_index"] for row in rows] == (
        expected_aromatic_bracket_h_parents
    )
    assert all(
        result.source_ingest.system.atoms[row["parent_source_atom_index"]].aromatic
        for row in rows
    )


@pytest.mark.parametrize(
    ("typed_center_count", "expected_error"),
    [(256, None), (257, "unsupported_tetrahedral_atom_count")],
)
def test_tetrahedral_center_resource_limit_is_exact_and_fail_closed(
    supported_local_rdkit: str,
    typed_center_count: int,
    expected_error: str | None,
) -> None:
    source = b"C" + (b"[C@H](F)" * typed_center_count) + b"Cl"
    system = parse_smiles(source, source_id="tetrahedral-resource-limit").system

    assert writer_module._MAX_TYPED_TETRAHEDRAL_ATOMS == 256
    if expected_error is not None:
        _assert_error(system, expected_error)
        return

    result = write_smiles(system)
    assert result.payload == source
    assert result.receipt.typed_tetrahedral_atom_count == typed_center_count
    assert result.receipt.to_dict()["resource_limits"]["typed_tetrahedral_atoms"] == 256
    assert (
        result.receipt.to_dict()["resource_limits"][
            "tetrahedral_calibration_source_atoms"
        ]
        == 514
    )
    assert (
        "at_most_256_parser_typed_tetrahedral_atoms_per_source_graph"
        in result.receipt.to_dict()["preservation_scope"]
    )
    assert (
        "at_most_514_source_atoms_when_parser_typed_tetrahedral_calibration_is_required"
        in result.receipt.to_dict()["preservation_scope"]
    )


@pytest.mark.parametrize(
    ("source_atom_count", "expected_error"),
    [(514, None), (515, "unsupported_tetrahedral_calibration_source_atom_count")],
)
def test_tetrahedral_calibration_source_atom_limit_is_exact_and_fail_closed(
    supported_local_rdkit: str,
    source_atom_count: int,
    expected_error: str | None,
) -> None:
    source = (b"C" * (source_atom_count - 3)) + b"[C@H](F)Cl"
    system = parse_smiles(
        source,
        source_id="tetrahedral-calibration-source-atom-limit",
    ).system

    assert writer_module._MAX_TETRAHEDRAL_CALIBRATION_SOURCE_ATOMS == 514
    assert system.metadata["source_atom_count"] == source_atom_count
    if expected_error is not None:
        _assert_error(system, expected_error)
        return

    result = write_smiles(system)
    receipt = result.receipt.to_dict()
    assert result.payload == source
    assert result.receipt.typed_tetrahedral_atom_count == 1
    assert receipt["resource_limits"]["tetrahedral_calibration_source_atoms"] == 514
    assert (
        "source_graphs_with_parser_typed_tetrahedral_state_and_more_than_514_source_atoms_unsupported"
        in receipt["blockers"]
    )


def test_opposite_mapped_tetrahedral_states_are_distinct_but_share_graph_shape(
    supported_local_rdkit: str,
) -> None:
    left = round_trip_smiles_source(b"F[C@H:17](Cl)Br")
    right = round_trip_smiles_source(b"F[C@@H:17](Cl)Br")
    left_system = left.source_ingest.system
    right_system = right.source_ingest.system
    left_state = writer_module._validate_write_state(left_system)
    right_state = writer_module._validate_write_state(right_system)

    assert [
        (atom.element, atom.formal_charge, atom.atom_map) for atom in left_system.atoms
    ] == [
        (atom.element, atom.formal_charge, atom.atom_map) for atom in right_system.atoms
    ]
    assert [(bond.atom_i, bond.atom_j, bond.order) for bond in left_system.bonds] == [
        (bond.atom_i, bond.atom_j, bond.order) for bond in right_system.bonds
    ]
    assert canonical_topology_sha256(left_system) != canonical_topology_sha256(
        right_system
    )
    assert canonical_all_atom_snapshot_digest(left_system) != (
        canonical_all_atom_snapshot_digest(right_system)
    )
    assert left_state.ordered_topology_sha256 != right_state.ordered_topology_sha256
    assert left_state.tetrahedral_stereo_projection_sha256 != (
        right_state.tetrahedral_stereo_projection_sha256
    )
    assert left.write_result.receipt.receipt_sha256 != (
        right.write_result.receipt.receipt_sha256
    )


@pytest.mark.parametrize(
    "source",
    [
        b"C[N+:7](C)(C)C",
        b"[Cl-:8]",
        b"C[O-:4]",
        b"C[C:7](C)(C)C",
        b"F[c:7]1ccccc1",
    ],
)
def test_selected_positive_atom_maps_are_preserved(
    supported_local_rdkit: str,
    source: bytes,
) -> None:
    result = round_trip_smiles_source(source, source_id="mapped-fixed-point")
    state = writer_module._validate_write_state(result.source_ingest.system)

    assert result.write_result.payload == source
    assert state.mapped_source_atom_count == 1
    assert result.source_ingest.coverage.atom_map_count == 1
    assert result.write_result.receipt.mapped_source_atom_count == 1
    assert any(":" in token for token in state.source_atom_tokens)


def test_tetrahedral_tag_map_and_hydrogen_tampering_fail_closed(
    supported_local_rdkit: str,
) -> None:
    system = parse_smiles(b"F[C@H:17](Cl)Br").system
    center = system.atoms[1]
    opposite_tag = (
        "CHI_TETRAHEDRAL_CW"
        if center.metadata["rdkit_chiral_tag"] == "CHI_TETRAHEDRAL_CCW"
        else "CHI_TETRAHEDRAL_CCW"
    )
    metadata = dict(center.metadata)
    metadata["rdkit_chiral_tag"] = opposite_tag
    atoms = list(system.atoms)
    atoms[1] = replace(center, metadata=metadata)
    _assert_error(
        replace(system, atoms=tuple(atoms)),
        "tetrahedral_calibration_failed",
    )

    duplicate_map_atoms = list(system.atoms)
    duplicate_map_atoms[0] = replace(duplicate_map_atoms[0], atom_map=17)
    _assert_error(
        replace(system, atoms=tuple(duplicate_map_atoms)),
        "canonical_validation_failed",
    )

    unknown_atoms = list(system.atoms)
    unknown_atoms[1] = replace(center, stereo="UNKNOWN")
    _assert_error(
        replace(system, atoms=tuple(unknown_atoms)),
        "unsupported_atom_stereo",
    )

    source_atom_count = system.metadata["source_atom_count"]
    hydrogen_index = source_atom_count
    hydrogen = system.atoms[hydrogen_index]
    hydrogen_metadata = dict(hydrogen.metadata)
    hydrogen_metadata["hydrogen_origin"] = "implicit"
    changed_atoms = list(system.atoms)
    changed_atoms[hydrogen_index] = replace(hydrogen, metadata=hydrogen_metadata)
    generated_bond = system.bonds[-1]
    generated_bond_metadata = dict(generated_bond.metadata)
    generated_bond_metadata["hydrogen_origin"] = "implicit"
    changed_bonds = (
        *system.bonds[:-1],
        replace(generated_bond, metadata=generated_bond_metadata),
    )
    _assert_error(
        replace(system, atoms=tuple(changed_atoms), bonds=changed_bonds),
        "unsupported_tetrahedral_ligand_inventory",
    )


@pytest.mark.parametrize(
    ("source", "code"),
    [
        (b"C1CCCCCCCC1", "unsupported_ring_size"),
        (b"C1CCCCC=1", "unsupported_ring_closure_bond"),
        (b"C1=CCCC=C1", "unsupported_ring_multiple_bond_count"),
        (b"C1#CCCCC1", "unsupported_ring_multiple_bond_order"),
        (b"C1C=CCCC1", "normalized_smiles_hash_mismatch"),
        (b"C1CCC2CCCCC2C1", "unsupported_source_cycle_rank"),
        (b"C1CCC2(CC1)CCCC2", "unsupported_source_cycle_rank"),
        (b"C12CC1CC2", "unsupported_source_cycle_rank"),
        (b"C1CC1.C1CC1", "unsupported_source_cycle_rank"),
        (b"c1ccc2ccccc2c1", "unsupported_source_cycle_rank"),
        (b"c1ccccc1-c2ccccc2", "unsupported_source_cycle_rank"),
        (b"c1ccccc1.c1ccccc1", "unsupported_source_cycle_rank"),
        (b"[cH]1ccccc1", "unsupported_aromatic_atom_state"),
        (b"[NH4+]", "unsupported_bracket_hydrogen"),
        (b"C[NH2+]C", "unsupported_bracket_hydrogen"),
        (b"[13CH4]", "unsupported_isotope"),
        (b"[CH4:7]", "unsupported_bracket_hydrogen"),
        (b"[C@H](F)(Cl)Br", "normalized_smiles_hash_mismatch"),
        (b"[H]O[H]", "unsupported_source_hydrogen"),
        (b"[H]C.C", "unsupported_source_hydrogen"),
        (b"[H+]", "unsupported_source_hydrogen"),
        (b"[CH4]", "unsupported_bracket_hydrogen"),
        (b"C.[CH4]", "unsupported_bracket_hydrogen"),
        (b"[Na+]", "unsupported_element"),
        (b"[Na+].[Cl-]", "unsupported_element"),
        (b"[NH4+].[Cl-]", "unsupported_bracket_hydrogen"),
        (b"C[S+2](C)(C)C", "unsupported_formal_charge"),
    ],
)
def test_v1_8_rejects_chemistry_outside_the_selected_source_graph_projection(
    supported_local_rdkit: str,
    source: bytes,
    code: str,
) -> None:
    _assert_error(parse_smiles(source).system, code)


def test_topology_only_coordinates_and_cell_are_typed_rejections(
    supported_local_rdkit: str,
) -> None:
    system = parse_smiles(b"CCO").system
    _assert_error(
        replace(
            system,
            coordinates=torch.zeros((1, system.atom_count, 3), dtype=torch.float64),
        ),
        "unsupported_coordinates",
    )
    _assert_error(
        replace(
            system,
            cell=UnitCell.orthorhombic((10.0, 10.0, 10.0)),
        ),
        "unsupported_cell",
    )


@pytest.mark.parametrize(
    ("mutator", "code"),
    [
        (
            lambda provenance: replace(provenance, source_format="sdf_v2000"),
            "unsupported_source_format",
        ),
        (
            lambda provenance: replace(provenance, parser_name="other"),
            "unsupported_parser_pedigree",
        ),
        (
            lambda provenance: replace(provenance, parser_version="0.0.0"),
            "unsupported_parser_pedigree",
        ),
        (
            lambda provenance: replace(
                provenance,
                operations=(*provenance.operations, "unrecorded_transform"),
            ),
            "unsupported_provenance_operations",
        ),
    ],
)
def test_parser_pedigree_drift_is_rejected(
    supported_local_rdkit: str,
    mutator,
    code: str,
) -> None:
    system = parse_smiles(b"CCO").system
    _assert_error(replace(system, provenance=mutator(system.provenance)), code)


def test_writer_rdkit_version_must_match_the_parser_owned_pin(
    supported_local_rdkit: str,
) -> None:
    system = parse_smiles(b"CCO").system
    _assert_error(
        _replace_provenance_metadata(system, "rdkit_version", "0.0.0"),
        "unsupported_rdkit_version",
    )


def test_attached_digests_coverage_and_normalized_hash_are_recomputed(
    supported_local_rdkit: str,
) -> None:
    system = parse_smiles(b"CCO").system
    for field_name, code in (
        ("canonical_topology_sha256", "stale_canonical_topology_digest"),
        ("parser_observation_sha256", "stale_parser_observation_digest"),
        ("normalized_isomeric_smiles_sha256", "normalized_smiles_hash_mismatch"),
    ):
        _assert_error(_replace_provenance_metadata(system, field_name, "0" * 64), code)

    coverage = dict(system.provenance.metadata["coverage"])
    coverage["source_atom_count"] += 1
    _assert_error(
        _replace_provenance_metadata(system, "coverage", coverage),
        "stale_smiles_coverage",
    )

    charged = parse_smiles(b"C[O-]").system
    _assert_error(
        _replace_provenance_metadata(
            charged,
            "normalized_isomeric_smiles_sha256",
            "0" * 64,
        ),
        "normalized_smiles_hash_mismatch",
    )
    for forged_total in (0, True, 1.0):
        charged_coverage = dict(charged.provenance.metadata["coverage"])
        charged_coverage["formal_charge_total"] = forged_total
        _assert_error(
            _replace_provenance_metadata(charged, "coverage", charged_coverage),
            "stale_smiles_coverage",
        )


@pytest.mark.parametrize(
    ("value", "code"),
    [
        (True, "invalid_fragment_count"),
        (0, "unsupported_fragment_count"),
        (257, "unsupported_fragment_count"),
    ],
)
def test_declared_fragment_marker_type_and_range_fail_before_graph_use(
    supported_local_rdkit: str,
    value: object,
    code: str,
) -> None:
    system = parse_smiles(b"C.C").system
    metadata = dict(system.metadata)
    metadata["fragment_count"] = value

    _assert_error(replace(system, metadata=metadata), code)


def test_declared_source_atom_marker_type_and_range_fail_early(
    supported_local_rdkit: str,
) -> None:
    system = parse_smiles(b"C.C").system
    for value, code in (
        (True, "invalid_source_atom_count"),
        (0, "unsupported_source_atom_count"),
        (system.atom_count + 1, "unsupported_source_atom_count"),
    ):
        metadata = dict(system.metadata)
        metadata["source_atom_count"] = value
        _assert_error(replace(system, metadata=metadata), code)


def test_fragment_count_coverage_and_context_must_match_graph_derived_components(
    supported_local_rdkit: str,
) -> None:
    system = parse_smiles(b"C.C").system

    metadata = dict(system.metadata)
    metadata["fragment_count"] = 1
    _assert_error(replace(system, metadata=metadata), "stale_system_markers")

    coverage = dict(system.provenance.metadata["coverage"])
    coverage["fragment_count"] = 1
    coverage["blockers"] = [
        blocker
        for blocker in coverage["blockers"]
        if blocker != "disconnected_fragment_roles_not_assessed"
    ]
    _assert_error(
        _replace_provenance_metadata(system, "coverage", coverage),
        "stale_smiles_coverage",
    )

    residue_metadata = dict(system.residues[1].metadata)
    residue_metadata["graph_component_index"] = 0
    residues = list(system.residues)
    residues[1] = replace(residues[1], metadata=residue_metadata)
    _assert_error(
        replace(system, residues=tuple(residues)),
        "unsupported_residue_context",
    )

    chain_metadata = dict(system.chains[1].metadata)
    chain_metadata["graph_component_index"] = 0
    chains = list(system.chains)
    chains[1] = replace(chains[1], metadata=chain_metadata)
    _assert_error(
        replace(system, chains=tuple(chains)),
        "unsupported_chain_context",
    )


def test_atom_component_membership_is_checked_against_the_source_graph(
    supported_local_rdkit: str,
) -> None:
    system = parse_smiles(b"C.C").system
    first = system.residues[0].atom_indices
    second = system.residues[1].atom_indices
    atoms = list(system.atoms)
    for atom_index in first:
        atoms[atom_index] = replace(atoms[atom_index], residue_index=1)
    for atom_index in second:
        atoms[atom_index] = replace(atoms[atom_index], residue_index=0)
    residues = (
        replace(system.residues[0], atom_indices=second),
        replace(system.residues[1], atom_indices=first),
    )

    _assert_error(
        replace(system, atoms=tuple(atoms), residues=residues),
        "unsupported_source_atom_identity",
    )


def test_source_and_generated_bond_prefixes_cannot_be_reordered(
    supported_local_rdkit: str,
) -> None:
    system = parse_smiles(b"C.CC").system
    source_bond_count = len(system.bonds) - system.metadata["generated_hydrogen_count"]
    bonds = list(system.bonds)
    source = bonds[0]
    generated = bonds[source_bond_count]
    bonds[0] = replace(generated, index=0)
    bonds[source_bond_count] = replace(source, index=source_bond_count)

    _assert_error(
        replace(system, bonds=tuple(bonds)),
        "unsupported_source_bond_metadata",
    )


def test_parser_owned_source_and_generated_metadata_are_exact(
    supported_local_rdkit: str,
) -> None:
    system = parse_smiles(b"CCO").system

    source_metadata = dict(system.atoms[0].metadata)
    source_metadata["source_atom_index"] = 1
    _assert_error(
        _replace_atom(system, metadata=source_metadata),
        "unsupported_source_atom_metadata",
    )

    source_metadata = dict(system.atoms[0].metadata)
    source_metadata["extra"] = True
    _assert_error(
        _replace_atom(system, metadata=source_metadata),
        "unsupported_source_atom_metadata",
    )

    generated_index = next(
        atom.index
        for atom in system.atoms
        if atom.metadata.get("hydrogen_origin") == "implicit"
    )
    generated_metadata = dict(system.atoms[generated_index].metadata)
    generated_metadata["hydrogen_ordinal"] = 99
    atoms = list(system.atoms)
    atoms[generated_index] = replace(
        atoms[generated_index],
        metadata=generated_metadata,
    )
    with pytest.raises(SmilesWriteError):
        write_smiles(replace(system, atoms=tuple(atoms)))

    source_bond_metadata = dict(system.bonds[0].metadata)
    source_bond_metadata["source_bond_index"] = 99
    bonds = list(system.bonds)
    bonds[0] = replace(bonds[0], metadata=source_bond_metadata)
    with pytest.raises(SmilesWriteError):
        write_smiles(replace(system, bonds=tuple(bonds)))


def test_source_formal_charge_type_range_and_metadata_fail_closed(
    supported_local_rdkit: str,
) -> None:
    charged = parse_smiles(b"[Cl-]").system
    atoms = list(charged.atoms)
    atoms[0] = replace(atoms[0], formal_charge_known=False)
    _assert_error(replace(charged, atoms=tuple(atoms)), "unsupported_formal_charge")

    charged = parse_smiles(b"[Cl-]").system
    object.__setattr__(charged.atoms[0], "formal_charge", True)
    with pytest.raises(SmilesWriteError) as bool_error:
        write_smiles(charged)
    assert bool_error.value.code in {
        "canonical_validation_failed",
        "unsupported_formal_charge",
    }

    charged = parse_smiles(b"[Cl-]").system
    metadata = dict(charged.atoms[0].metadata)
    metadata["formal_charge_source"] = "forged"
    atoms = list(charged.atoms)
    atoms[0] = replace(atoms[0], metadata=metadata)
    _assert_error(
        replace(charged, atoms=tuple(atoms)),
        "unsupported_source_atom_metadata",
    )

    charged = parse_smiles(b"[Cl-]").system
    atoms = list(charged.atoms)
    atoms[0] = replace(atoms[0], formal_charge=1)
    _assert_error(
        replace(charged, atoms=tuple(atoms)),
        "normalized_smiles_hash_mismatch",
    )


@pytest.mark.parametrize(
    ("changes", "code"),
    [
        ({"formal_charge": 1}, "unsupported_generated_hydrogen_formal_charge"),
        (
            {"formal_charge_known": False},
            "unsupported_generated_hydrogen_formal_charge",
        ),
    ],
)
def test_generated_hydrogen_charge_state_remains_known_neutral(
    supported_local_rdkit: str,
    changes: dict[str, object],
    code: str,
) -> None:
    system = parse_smiles(b"C").system
    generated_index = system.metadata["source_atom_count"]
    atoms = list(system.atoms)
    atoms[generated_index] = replace(atoms[generated_index], **changes)

    _assert_error(replace(system, atoms=tuple(atoms)), code)


def test_charged_source_atom_cannot_own_generated_hydrogen(
    supported_local_rdkit: str,
) -> None:
    system = parse_smiles(b"C").system
    atoms = list(system.atoms)
    atoms[0] = replace(atoms[0], formal_charge=1)

    _assert_error(
        replace(system, atoms=tuple(atoms)),
        "unsupported_charged_parent_hydrogen",
    )


def test_source_atom_token_table_is_bound_before_emission(
    supported_local_rdkit: str,
) -> None:
    state = writer_module._validate_write_state(parse_smiles(b"C[O-]").system)
    forged = replace(state, source_atom_tokens=("C", "O"))

    with pytest.raises(SmilesWriteError) as exc_info:
        writer_module._emit_payload(forged)
    assert exc_info.value.code == "normalized_smiles_hash_mismatch"


def test_parser_generated_hydrogen_bonds_remain_exact_single_bonds(
    supported_local_rdkit: str,
) -> None:
    system = parse_smiles(b"C=C").system
    generated_bond_index = next(
        bond.index
        for bond in system.bonds
        if bond.source == "manual_hydrogen_expansion"
    )
    bonds = list(system.bonds)
    bonds[generated_bond_index] = replace(
        bonds[generated_bond_index],
        order=2.0,
    )

    _assert_error(replace(system, bonds=tuple(bonds)), "unsupported_bond")


def test_source_bond_orders_outside_exact_single_double_triple_are_rejected(
    supported_local_rdkit: str,
) -> None:
    system = parse_smiles(b"C=C").system
    bonds = list(system.bonds)
    bonds[0] = replace(bonds[0], order=4.0)

    _assert_error(replace(system, bonds=tuple(bonds)), "unsupported_bond")


def test_unique_ring_closure_must_be_the_final_source_bond(
    supported_local_rdkit: str,
) -> None:
    system = parse_smiles(b"C1CC1.CC").system
    source_bond_count = len(system.bonds) - system.metadata["generated_hydrogen_count"]
    assert source_bond_count == 4
    reordered_source = []
    for new_index, old_index in enumerate((0, 3, 1, 2)):
        bond = system.bonds[old_index]
        metadata = dict(bond.metadata)
        metadata["source_bond_index"] = new_index
        reordered_source.append(replace(bond, index=new_index, metadata=metadata))
    tampered = replace(
        system,
        bonds=(*reordered_source, *system.bonds[source_bond_count:]),
    )

    _assert_error(tampered, "unsupported_ring_closure_order")


def test_ring_closure_must_remain_exact_single(
    supported_local_rdkit: str,
) -> None:
    system = parse_smiles(b"C1CCCCC1").system
    bonds = list(system.bonds)
    bonds[5] = replace(bonds[5], order=2.0)

    _assert_error(
        replace(system, bonds=tuple(bonds)),
        "unsupported_ring_closure_bond",
    )


def test_ring_marker_table_is_bound_before_emission(
    supported_local_rdkit: str,
) -> None:
    state = writer_module._validate_write_state(parse_smiles(b"C1CC1").system)
    forged = replace(state, source_ring_marker_table=("", "", ""))

    with pytest.raises(SmilesWriteError) as exc_info:
        writer_module._emit_payload(forged)
    assert exc_info.value.code == "normalized_smiles_hash_mismatch"


def test_system_markers_tree_order_and_duplicate_state_fail_closed(
    supported_local_rdkit: str,
) -> None:
    system = parse_smiles(b"CCO").system

    metadata = dict(system.metadata)
    metadata["source_atom_count"] += 1
    with pytest.raises(SmilesWriteError):
        write_smiles(replace(system, metadata=metadata))

    source_metadata = dict(system.atoms[1].metadata)
    source_metadata["source_atom_index"] = 0
    atoms = list(system.atoms)
    atoms[1] = replace(atoms[1], metadata=source_metadata)
    with pytest.raises(SmilesWriteError):
        write_smiles(replace(system, atoms=tuple(atoms)))

    duplicate = replace(
        system.bonds[1],
        index=len(system.bonds),
    )
    with pytest.raises(SmilesWriteError):
        write_smiles(replace(system, bonds=(*system.bonds, duplicate)))


def test_output_and_graph_resource_caps_fail_before_success(
    supported_local_rdkit: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    system = parse_smiles(b"CCO").system
    with monkeypatch.context() as scoped:
        scoped.setattr(writer_module, "_MAX_OUTPUT_BYTES", 1)
        _assert_error(system, "output_too_large")
    for limit_name in (
        "_MAX_SOURCE_ATOMS",
        "_MAX_EXPANDED_ATOMS",
        "_MAX_BONDS",
    ):
        with monkeypatch.context() as scoped:
            scoped.setattr(writer_module, limit_name, 1)
            with pytest.raises(SmilesWriteError):
                write_smiles(system)


@pytest.mark.parametrize(
    ("case", "code"),
    [
        ("expanded_atom_cap", "unsupported_expanded_atom_count"),
        ("bond_cap", "unsupported_bond_count"),
        ("coordinate_model", "unsupported_coordinates"),
        ("coordinate_atom_axis", "unsupported_coordinates"),
    ],
)
def test_live_caps_and_coordinate_shape_reject_before_snapshot_clone(
    supported_local_rdkit: str,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
    code: str,
) -> None:
    system = parse_smiles(b"CCO").system
    if case == "expanded_atom_cap":
        monkeypatch.setattr(writer_module, "_MAX_EXPANDED_ATOMS", system.atom_count - 1)
    elif case == "bond_cap":
        monkeypatch.setattr(writer_module, "_MAX_BONDS", len(system.bonds) - 1)
    elif case == "coordinate_model":
        system = replace(
            system,
            coordinates=torch.zeros(
                (1, system.atom_count, 3),
                dtype=torch.float64,
            ),
        )
    else:
        system = replace(
            system,
            coordinates=torch.empty(
                (0, system.atom_count + 1, 3),
                dtype=torch.float64,
            ),
        )

    def should_not_snapshot(_system):
        raise AssertionError("live preflight must reject before snapshot cloning")

    monkeypatch.setattr(writer_module, "_snapshot_parser_system", should_not_snapshot)
    _assert_error(system, code)


def test_fragment_cap_rejects_before_snapshot_clone(
    supported_local_rdkit: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    system = parse_smiles(b"C.C").system
    monkeypatch.setattr(writer_module, "_MAX_FRAGMENTS", 1)

    def should_not_snapshot(_system):
        raise AssertionError("fragment preflight must reject before snapshot cloning")

    monkeypatch.setattr(writer_module, "_snapshot_parser_system", should_not_snapshot)
    _assert_error(system, "unsupported_fragment_count")


def test_round_trip_accessors_are_fresh_detached_snapshots(
    supported_local_rdkit: str,
) -> None:
    result = round_trip_smiles_source(b"CCO")
    source_name = result.source_ingest.system.atoms[0].name
    reparsed_name = result.reparsed_ingest.system.atoms[0].name

    exposed_source = result.source_ingest
    exposed_reparsed = result.reparsed_ingest
    object.__setattr__(exposed_source.system.atoms[0], "name", "FORGED")
    object.__setattr__(exposed_reparsed.system.atoms[0], "name", "FORGED")

    assert result.source_ingest.system.atoms[0].name == source_name
    assert result.reparsed_ingest.system.atoms[0].name == reparsed_name
    result.__post_init__()


def test_success_artifacts_are_factory_only_and_cross_wiring_is_rejected(
    supported_local_rdkit: str,
) -> None:
    ethanol = round_trip_smiles_source(b"CCO", source_id="ethanol")
    ether = round_trip_smiles_source(b"COC", source_id="ether")

    with pytest.raises(TypeError, match="factory-only"):
        type(ethanol.write_result.receipt)(
            **_public_artifact_kwargs(ethanol.write_result.receipt)
        )
    with pytest.raises(TypeError, match="factory-only"):
        type(ethanol.write_result)(
            payload=ethanol.write_result.payload,
            receipt=ethanol.write_result.receipt,
        )
    with pytest.raises(TypeError, match="factory-only"):
        type(ethanol.report)(**_public_artifact_kwargs(ethanol.report))
    with pytest.raises(TypeError, match="factory-only"):
        type(ethanol)(
            source_ingest=ethanol.source_ingest,
            write_result=ethanol.write_result,
            reparsed_ingest=ethanol.reparsed_ingest,
            report=ethanol.report,
        )

    with pytest.raises(ValueError, match="cross-consistent"):
        type(ethanol)(
            source_ingest=ether.source_ingest,
            write_result=ethanol.write_result,
            reparsed_ingest=ethanol.reparsed_ingest,
            report=ethanol.report,
            _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
        )


def test_private_factory_token_cannot_cross_wire_different_forests(
    supported_local_rdkit: str,
) -> None:
    two = round_trip_smiles_source(b"C.C", source_id="two-components")
    three = round_trip_smiles_source(b"C.C.C", source_id="three-components")

    assert two.write_result.receipt.fragment_count == 2
    assert three.write_result.receipt.fragment_count == 3
    with pytest.raises(ValueError, match="regenerated SMILES bindings"):
        type(two.write_result)(
            payload=two.write_result.payload,
            receipt=two.write_result.receipt,
            input_system=three.source_ingest.system,
            _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
        )
    with pytest.raises(ValueError, match="cross-consistent"):
        type(two)(
            source_ingest=three.source_ingest,
            write_result=two.write_result,
            reparsed_ingest=two.reparsed_ingest,
            report=two.report,
            _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
        )


def test_private_factory_token_binds_same_count_same_fragment_forests(
    supported_local_rdkit: str,
) -> None:
    ethanol_forest = round_trip_smiles_source(b"C.CCO", source_id="ethanol-forest")
    ether_forest = round_trip_smiles_source(b"C.COC", source_id="ether-forest")
    first = ethanol_forest.write_result.receipt
    second = ether_forest.write_result.receipt

    for field_name in (
        "source_atom_count",
        "expanded_atom_count",
        "bond_count",
        "fragment_count",
        "generated_hydrogen_count",
        "source_bond_count",
        "source_tree_edge_count",
        "ring_closure_count",
        "cyclic_component_count",
        "ring_size",
        "charged_source_atom_count",
    ):
        assert getattr(first, field_name) == getattr(second, field_name)
    assert first.fragment_count == 2
    assert first.input_topology_sha256 != second.input_topology_sha256
    with pytest.raises(ValueError, match="regenerated SMILES bindings"):
        type(ether_forest.write_result)(
            payload=ether_forest.write_result.payload,
            receipt=ether_forest.write_result.receipt,
            input_system=ethanol_forest.source_ingest.system,
            _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
        )
    with pytest.raises(ValueError, match="cross-consistent"):
        type(ether_forest)(
            source_ingest=ethanol_forest.source_ingest,
            write_result=ether_forest.write_result,
            reparsed_ingest=ether_forest.reparsed_ingest,
            report=ether_forest.report,
            _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
        )


def test_private_token_cannot_cross_wire_same_count_canonical_payloads(
    supported_local_rdkit: str,
) -> None:
    ethanol = round_trip_smiles_source(b"CCO")
    ether = round_trip_smiles_source(b"COC")
    first = ethanol.write_result.receipt
    second = ether.write_result.receipt

    assert ethanol.write_result.payload != ether.write_result.payload
    assert first.input_topology_sha256 != second.input_topology_sha256
    for field_name in (
        "output_byte_count",
        "source_atom_count",
        "expanded_atom_count",
        "bond_count",
        "fragment_count",
        "generated_hydrogen_count",
    ):
        assert getattr(first, field_name) == getattr(second, field_name)

    receipt_kwargs = _public_artifact_kwargs(first)
    for field_name in (
        "normalized_isomeric_smiles_sha256",
        "output_source_sha256",
        "output_byte_count",
        "source_atom_count",
        "expanded_atom_count",
        "bond_count",
        "fragment_count",
        "generated_hydrogen_count",
        "rdkit_version",
    ):
        receipt_kwargs[field_name] = getattr(second, field_name)
    forged_receipt = type(first)(
        **receipt_kwargs,
        _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
    )

    with pytest.raises(ValueError, match="regenerated SMILES bindings"):
        type(ether.write_result)(
            payload=ether.write_result.payload,
            receipt=forged_receipt,
            input_system=ethanol.source_ingest.system,
            _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
        )


@pytest.mark.parametrize(
    "field_name",
    [
        "parent_source_sha256",
        "input_snapshot_sha256",
        "input_parser_observation_sha256",
    ],
)
def test_private_token_cannot_forge_live_input_receipt_bindings(
    supported_local_rdkit: str,
    field_name: str,
) -> None:
    result = round_trip_smiles_source(b"CCO", source_id="live-binding")
    receipt = result.write_result.receipt
    receipt_kwargs = _public_artifact_kwargs(receipt)
    original_value = str(receipt_kwargs[field_name])
    receipt_kwargs[field_name] = "0" * 64 if original_value != "0" * 64 else "1" * 64
    forged_receipt = type(receipt)(
        **receipt_kwargs,
        _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
    )

    with pytest.raises(ValueError, match="regenerated SMILES bindings"):
        type(result.write_result)(
            payload=result.write_result.payload,
            receipt=forged_receipt,
            input_system=result.source_ingest.system,
            _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
        )


@pytest.mark.parametrize(
    "field_name",
    [
        "output_byte_count",
        "source_atom_count",
        "expanded_atom_count",
        "bond_count",
        "fragment_count",
        "generated_hydrogen_count",
        "charged_source_atom_count",
    ],
)
def test_receipt_count_forgery_cannot_form_a_successful_result(
    supported_local_rdkit: str,
    field_name: str,
) -> None:
    result = round_trip_smiles_source(b"CCO")
    receipt_kwargs = _public_artifact_kwargs(result.write_result.receipt)
    receipt_kwargs[field_name] = int(receipt_kwargs[field_name]) + 1

    with pytest.raises((TypeError, ValueError)):
        forged_receipt = type(result.write_result.receipt)(
            **receipt_kwargs,
            _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
        )
        type(result.write_result)(
            payload=result.write_result.payload,
            receipt=forged_receipt,
            _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
        )


@pytest.mark.parametrize(
    ("charged_count", "formal_total"),
    [
        (0, 1),
        (1, 0),
        (2, 1),
        (True, 1),
        (1.0, 1),
        (False, 0),
        (0.0, 0),
        (1, True),
        (1, 1.0),
        (0, False),
        (0, 0.0),
    ],
)
def test_receipt_rejects_impossible_or_inexact_unit_charge_inventories(
    supported_local_rdkit: str,
    charged_count: object,
    formal_total: object,
) -> None:
    result = round_trip_smiles_source(b"C[N+](C)(C)C.[Cl-]")
    receipt_kwargs = _public_artifact_kwargs(result.write_result.receipt)
    receipt_kwargs["charged_source_atom_count"] = charged_count
    receipt_kwargs["formal_charge_total"] = formal_total

    with pytest.raises((TypeError, ValueError)):
        type(result.write_result.receipt)(
            **receipt_kwargs,
            _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
        )


@pytest.mark.parametrize(
    ("field_name", "forged_value"),
    [
        ("source_bond_count", True),
        ("source_bond_count", 3.0),
        ("source_tree_edge_count", False),
        ("source_tree_edge_count", 2.0),
        ("ring_closure_count", True),
        ("ring_closure_count", 1.0),
        ("ring_closure_count", -1),
        ("ring_closure_count", 2),
        ("cyclic_component_count", True),
        ("cyclic_component_count", 1.0),
        ("ring_size", True),
        ("ring_size", 3.0),
        ("ring_closure_source_bond_index", True),
        ("ring_closure_source_bond_index", 2.0),
        ("ring_double_bond_count", True),
        ("ring_double_bond_count", 1.0),
        ("ring_double_bond_count", -1),
        ("ring_double_bond_count", 2),
        ("ring_double_source_bond_index", True),
        ("ring_double_source_bond_index", 0.0),
    ],
)
def test_receipt_cycle_counts_and_closure_index_are_exact_typed(
    supported_local_rdkit: str,
    field_name: str,
    forged_value: object,
) -> None:
    result = round_trip_smiles_source(b"C1=CC1")
    receipt_kwargs = _public_artifact_kwargs(result.write_result.receipt)
    receipt_kwargs[field_name] = forged_value

    with pytest.raises((TypeError, ValueError)):
        type(result.write_result.receipt)(
            **receipt_kwargs,
            _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
        )


def test_receipt_profile_and_live_charge_bindings_cannot_be_forged(
    supported_local_rdkit: str,
) -> None:
    result = round_trip_smiles_source(b"C[N+](C)(C)C.[Cl-]")
    valid_profile = result.write_result.receipt.formal_charge_profile_id

    class EqualProfile:
        def __eq__(self, other: object) -> bool:
            return other == valid_profile

    class ProfileString(str):
        pass

    for forged_profile in (EqualProfile(), ProfileString(valid_profile)):
        receipt_kwargs = _public_artifact_kwargs(result.write_result.receipt)
        receipt_kwargs["formal_charge_profile_id"] = forged_profile
        with pytest.raises(TypeError, match="exact string"):
            type(result.write_result.receipt)(
                **receipt_kwargs,
                _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
            )

    receipt_kwargs = _public_artifact_kwargs(result.write_result.receipt)
    receipt_kwargs["formal_charge_profile_id"] = "other/1.0.0"
    with pytest.raises(ValueError, match="formal_charge_profile_id"):
        type(result.write_result.receipt)(
            **receipt_kwargs,
            _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
        )

    receipt_kwargs = _public_artifact_kwargs(result.write_result.receipt)
    receipt_kwargs["charged_source_atom_count"] = 0
    receipt_kwargs["formal_charge_total"] = 0
    forged_receipt = type(result.write_result.receipt)(
        **receipt_kwargs,
        _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
    )
    with pytest.raises(ValueError, match="regenerated SMILES bindings"):
        type(result.write_result)(
            payload=result.write_result.payload,
            receipt=forged_receipt,
            input_system=result.source_ingest.system,
            _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
        )


def test_same_count_net_charge_token_placement_cannot_be_cross_wired(
    supported_local_rdkit: str,
) -> None:
    chloride = round_trip_smiles_source(b"C[N+](C)(C)C.[Cl-]", source_id="chloride")
    bromide = round_trip_smiles_source(b"C[N+](C)(C)C.[Br-]", source_id="bromide")
    left = chloride.write_result.receipt
    right = bromide.write_result.receipt

    for field_name in (
        "output_byte_count",
        "source_atom_count",
        "expanded_atom_count",
        "bond_count",
        "fragment_count",
        "generated_hydrogen_count",
        "charged_source_atom_count",
        "formal_charge_total",
    ):
        assert getattr(left, field_name) == getattr(right, field_name)
    assert chloride.write_result.payload != bromide.write_result.payload
    assert left.input_topology_sha256 != right.input_topology_sha256
    with pytest.raises(ValueError, match="regenerated SMILES bindings"):
        type(chloride.write_result)(
            payload=chloride.write_result.payload,
            receipt=chloride.write_result.receipt,
            input_system=bromide.source_ingest.system,
            _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
        )
    with pytest.raises(ValueError, match="cross-consistent"):
        type(chloride)(
            source_ingest=bromide.source_ingest,
            write_result=chloride.write_result,
            reparsed_ingest=chloride.reparsed_ingest,
            report=chloride.report,
            _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
        )


def test_same_count_same_closure_endpoint_ring_atom_tables_cannot_be_cross_wired(
    supported_local_rdkit: str,
) -> None:
    left = round_trip_smiles_source(b"CC1(C)CCC1", source_id="ring-branch-left")
    right = round_trip_smiles_source(b"CC1CC(C)C1", source_id="ring-branch-right")
    left_state = writer_module._validate_write_state(left.source_ingest.system)
    right_state = writer_module._validate_write_state(right.source_ingest.system)

    for field_name in (
        "source_atom_count",
        "expanded_atom_count",
        "bond_count",
        "fragment_count",
        "generated_hydrogen_count",
        "source_bond_count",
        "source_tree_edge_count",
        "ring_closure_count",
        "cyclic_component_count",
        "ring_size",
        "ring_closure_source_bond_index",
        "charged_source_atom_count",
        "formal_charge_total",
    ):
        assert getattr(left.write_result.receipt, field_name) == getattr(
            right.write_result.receipt, field_name
        )
    assert left_state.ring_closure_endpoints == right_state.ring_closure_endpoints
    assert left_state.ring_atom_indices != right_state.ring_atom_indices
    assert left_state.cycle_projection_sha256 != right_state.cycle_projection_sha256
    with pytest.raises(ValueError, match="regenerated SMILES bindings"):
        type(left.write_result)(
            payload=left.write_result.payload,
            receipt=left.write_result.receipt,
            input_system=right.source_ingest.system,
            _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
        )
    with pytest.raises(ValueError, match="cross-consistent"):
        type(left)(
            source_ingest=right.source_ingest,
            write_result=left.write_result,
            reparsed_ingest=left.reparsed_ingest,
            report=left.report,
            _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
        )


def test_same_count_one_double_ring_positions_cannot_be_cross_wired(
    supported_local_rdkit: str,
) -> None:
    left = round_trip_smiles_source(
        b"CC1=CCCCC1",
        source_id="ring-double-position-left",
    )
    right = round_trip_smiles_source(
        b"CC1C=CCCC1",
        source_id="ring-double-position-right",
    )
    left_state = writer_module._validate_write_state(left.source_ingest.system)
    right_state = writer_module._validate_write_state(right.source_ingest.system)

    for field_name in (
        "output_byte_count",
        "source_atom_count",
        "expanded_atom_count",
        "bond_count",
        "fragment_count",
        "generated_hydrogen_count",
        "source_bond_count",
        "source_tree_edge_count",
        "ring_closure_count",
        "cyclic_component_count",
        "ring_size",
        "ring_closure_source_bond_index",
        "ring_bond_profile_id",
        "ring_double_bond_count",
        "charged_source_atom_count",
        "formal_charge_total",
    ):
        assert getattr(left.write_result.receipt, field_name) == getattr(
            right.write_result.receipt,
            field_name,
        )
    assert (
        left_state.ring_atom_indices
        == right_state.ring_atom_indices
        == (
            1,
            2,
            3,
            4,
            5,
            6,
        )
    )
    assert (
        left_state.ring_bond_indices
        == right_state.ring_bond_indices
        == (
            1,
            2,
            3,
            4,
            5,
            6,
        )
    )
    assert (
        left_state.ring_closure_endpoints
        == right_state.ring_closure_endpoints
        == (
            1,
            6,
        )
    )
    assert left_state.ring_double_source_bond_index == 1
    assert right_state.ring_double_source_bond_index == 2
    assert left_state.ring_bond_order_table != right_state.ring_bond_order_table
    assert left_state.cycle_projection_sha256 != right_state.cycle_projection_sha256

    receipt_kwargs = _public_artifact_kwargs(left.write_result.receipt)
    receipt_kwargs["input_cycle_projection_sha256"] = (
        right.write_result.receipt.input_cycle_projection_sha256
    )
    receipt_kwargs["ring_double_source_bond_index"] = 2
    forged_receipt = type(left.write_result.receipt)(
        **receipt_kwargs,
        _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
    )
    with pytest.raises(ValueError, match="regenerated SMILES bindings"):
        type(left.write_result)(
            payload=left.write_result.payload,
            receipt=forged_receipt,
            input_system=left.source_ingest.system,
            _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
        )
    with pytest.raises(ValueError):
        type(left.write_result)(
            payload=left.write_result.payload,
            receipt=right.write_result.receipt,
            input_system=left.source_ingest.system,
            _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
        )
    with pytest.raises(ValueError, match="cross-consistent"):
        type(left)(
            source_ingest=left.source_ingest,
            write_result=left.write_result,
            reparsed_ingest=left.reparsed_ingest,
            report=right.report,
            _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
        )
    with pytest.raises(ValueError, match="cross-consistent"):
        type(left)(
            source_ingest=left.source_ingest,
            write_result=right.write_result,
            reparsed_ingest=left.reparsed_ingest,
            report=left.report,
            _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
        )


def test_parser_signed_noncanonical_double_position_still_fails_hash_gate(
    supported_local_rdkit: str,
) -> None:
    system = parse_smiles(b"C1C=CCCC1", source_id="signed-noncanonical-ring").system

    assert system.provenance.metadata["canonical_topology_sha256"] == (
        canonical_topology_sha256(system)
    )
    assert system.provenance.metadata["parser_observation_sha256"] == (
        parser_observation_sha256(system)
    )
    _assert_error(system, "normalized_smiles_hash_mismatch")


def test_same_global_counts_different_ring_size_projection_cannot_be_cross_wired(
    supported_local_rdkit: str,
) -> None:
    six = round_trip_smiles_source(b"CC1CCCCC1", source_id="six-ring")
    five = round_trip_smiles_source(b"CCC1CCCC1", source_id="five-ring")
    six_state = writer_module._validate_write_state(six.source_ingest.system)
    five_state = writer_module._validate_write_state(five.source_ingest.system)

    for field_name in (
        "source_atom_count",
        "expanded_atom_count",
        "bond_count",
        "fragment_count",
        "generated_hydrogen_count",
        "source_bond_count",
        "source_tree_edge_count",
        "ring_closure_count",
        "cyclic_component_count",
        "charged_source_atom_count",
        "formal_charge_total",
    ):
        assert getattr(six.write_result.receipt, field_name) == getattr(
            five.write_result.receipt, field_name
        )
    assert six_state.ring_size == 6
    assert five_state.ring_size == 5
    assert six_state.cycle_projection_sha256 != five_state.cycle_projection_sha256
    with pytest.raises(ValueError, match="regenerated SMILES bindings"):
        type(six.write_result)(
            payload=six.write_result.payload,
            receipt=six.write_result.receipt,
            input_system=five.source_ingest.system,
            _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
        )


def test_cycle_projection_sha_and_profile_receipt_bindings_cannot_be_forged(
    supported_local_rdkit: str,
) -> None:
    result = round_trip_smiles_source(b"C1CC1")
    receipt = result.write_result.receipt

    receipt_kwargs = _public_artifact_kwargs(receipt)
    receipt_kwargs["input_cycle_projection_sha256"] = "0" * 64
    forged_receipt = type(receipt)(
        **receipt_kwargs,
        _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
    )
    with pytest.raises(ValueError, match="regenerated SMILES bindings"):
        type(result.write_result)(
            payload=result.write_result.payload,
            receipt=forged_receipt,
            input_system=result.source_ingest.system,
            _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
        )

    for field_name, forged_value in (
        ("cycle_projection_schema_id", "other/1.0.0"),
        ("cycle_profile_id", "other/1.0.0"),
    ):
        receipt_kwargs = _public_artifact_kwargs(receipt)
        receipt_kwargs[field_name] = forged_value
        with pytest.raises(ValueError, match=field_name):
            type(receipt)(
                **receipt_kwargs,
                _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
            )

    one_double = round_trip_smiles_source(b"C1=CCCCC1").write_result.receipt

    class ProfileString(str):
        pass

    for field_name in ("cycle_profile_id", "ring_bond_profile_id"):
        receipt_kwargs = _public_artifact_kwargs(one_double)
        receipt_kwargs[field_name] = ProfileString(str(receipt_kwargs[field_name]))
        with pytest.raises(TypeError, match="exact string"):
            type(one_double)(
                **receipt_kwargs,
                _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
            )

    for field_name, forged_value in (
        ("ring_bond_profile_id", "all_single_nonaromatic_stereo_none/1.0.0"),
        (
            "cycle_profile_id",
            "at_most_one_simple_nonaromatic_3_8_member_all_single_bond_source_ring/1.0.0",
        ),
        ("ring_double_source_bond_index", one_double.ring_closure_source_bond_index),
    ):
        receipt_kwargs = _public_artifact_kwargs(one_double)
        receipt_kwargs[field_name] = forged_value
        with pytest.raises(ValueError):
            type(one_double)(
                **receipt_kwargs,
                _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
            )


def test_forged_charged_payload_cannot_reuse_another_charge_receipt(
    supported_local_rdkit: str,
) -> None:
    chloride = round_trip_smiles_source(b"[Cl-]")
    payload = b"[Br-]"
    receipt_kwargs = _public_artifact_kwargs(chloride.write_result.receipt)
    payload_sha256 = hashlib.sha256(payload).hexdigest()
    receipt_kwargs["normalized_isomeric_smiles_sha256"] = payload_sha256
    receipt_kwargs["output_source_sha256"] = payload_sha256
    receipt_kwargs["output_byte_count"] = len(payload)
    forged_receipt = type(chloride.write_result.receipt)(
        **receipt_kwargs,
        _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
    )

    with pytest.raises(ValueError, match="regenerated SMILES bindings"):
        type(chloride.write_result)(
            payload=payload,
            receipt=forged_receipt,
            input_system=chloride.source_ingest.system,
            _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
        )


def test_hash_forgery_and_noncanonical_payload_cannot_form_a_successful_result(
    supported_local_rdkit: str,
) -> None:
    result = round_trip_smiles_source(b"CCO")
    payload = b"OCC"
    receipt_kwargs = _public_artifact_kwargs(result.write_result.receipt)
    forged_sha256 = hashlib.sha256(payload).hexdigest()
    receipt_kwargs["normalized_isomeric_smiles_sha256"] = forged_sha256
    receipt_kwargs["output_source_sha256"] = forged_sha256
    receipt_kwargs["output_byte_count"] = len(payload)
    forged_receipt = type(result.write_result.receipt)(
        **receipt_kwargs,
        _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
    )

    with pytest.raises(ValueError):
        type(result.write_result)(
            payload=payload,
            receipt=forged_receipt,
            _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
        )


def test_success_repr_is_bounded_and_payload_free(
    supported_local_rdkit: str,
) -> None:
    result = round_trip_smiles_source(b"CC(C)C", source_id="branched-secret")
    result_repr = repr(result)
    write_repr = repr(result.write_result)

    assert len(result_repr) < 4_000
    assert len(write_repr) < 2_000
    assert "CC(C)C" not in result_repr
    assert "CC(C)C" not in write_repr
    assert "branched-secret" not in result_repr
    assert "coordinates" not in result_repr


def test_writer_rejects_wrong_input_type_without_partial_output() -> None:
    with pytest.raises(TypeError, match="exact AllAtomSystem"):
        serialize_smiles(b"not-a-system")


def test_one_thousand_atom_chain_emission_is_iterative_and_bounded(
    supported_local_rdkit: str,
) -> None:
    source = b"C" * 1_000
    system = parse_smiles(source, source_id="chain-1000").system
    result = write_smiles(system)

    assert result.payload == source
    assert result.receipt.output_byte_count == 1_000
    assert result.receipt.atom_count == system.atom_count
    assert result.receipt.bond_count == len(system.bonds)
    assert b"\n" not in result.payload


def test_one_thousand_atom_simple_unicyclic_component_is_iterative_and_bounded(
    supported_local_rdkit: str,
) -> None:
    source = b"C" * 997 + b"C1CC1"
    system = parse_smiles(source, source_id="unicyclic-1000").system
    result = write_smiles(system)
    state = writer_module._validate_write_state(system)

    assert result.payload == source
    assert state.source_atom_count == 1_000
    assert state.ring_atom_indices == (997, 998, 999)
    assert state.ring_bond_indices == (997, 998, 999)
    assert state.ring_closure_source_bond_index == 999
    assert state.source_ring_marker_table[997:] == ("1", "", "1")
    assert result.receipt.ring_size == 3
    assert result.receipt.ring_closure_count == 1
    assert result.receipt.output_byte_count == 1_002
    assert b"\n" not in result.payload


def test_one_thousand_atom_aromatic_substituent_is_iterative_and_bounded(
    supported_local_rdkit: str,
) -> None:
    source = b"C" * 994 + b"c1ccccc1"
    result = round_trip_smiles_source(source, source_id="aromatic-1000")
    state = writer_module._validate_write_state(result.source_ingest.system)

    assert result.write_result.payload == source
    assert state.source_atom_count == 1_000
    assert state.ring_atom_indices == tuple(range(994, 1_000))
    assert state.aromatic_source_atom_count == 6
    assert state.aromatic_source_bond_count == 6
    assert result.write_result.receipt.output_byte_count == 1_002
    assert b"\n" not in result.write_result.payload


def test_one_aromatic_ring_among_256_fragments_is_iterative_and_bound(
    supported_local_rdkit: str,
) -> None:
    source = b".".join((*((b"C",) * 255), b"c1ccccc1"))
    result = round_trip_smiles_source(source, source_id="aromatic-forest-256")
    state = writer_module._validate_write_state(result.source_ingest.system)
    receipt = result.write_result.receipt

    assert result.write_result.payload == source
    assert state.fragment_count == 256
    assert state.source_atom_count == 261
    assert state.component_cyclomatic_numbers == (*((0,) * 255), 1)
    assert state.ring_atom_indices == tuple(range(255, 261))
    assert receipt.aromatic_source_atom_count == 6
    assert receipt.aromatic_source_bond_count == 6
    assert receipt.to_dict()["resource_limits"]["aromatic_ring_size_min"] == 5
    assert receipt.to_dict()["resource_limits"]["aromatic_ring_size_max"] == 6


def test_256_isolated_components_are_iterative_and_bound_to_l256(
    supported_local_rdkit: str,
) -> None:
    source = b".".join((b"C",) * 256)
    result = round_trip_smiles_source(source, source_id="forest-256")
    state = writer_module._validate_write_state(result.source_ingest.system)
    receipt = result.write_result.receipt

    assert result.write_result.payload == source
    assert state.fragment_count == 256
    assert state.source_atom_count == 256
    assert state.system.atom_count == 1_280
    assert len(state.system.bonds) == 1_024
    assert state.source_component_roots == tuple(range(256))
    assert state.source_parent_bond_tokens == ("",) * 256
    assert state.source_components[0] == (0,)
    assert state.source_components[-1] == (255,)
    assert state.expanded_components[0] == (0, 256, 257, 258, 259)
    assert state.expanded_components[-1] == (255, 1_276, 1_277, 1_278, 1_279)
    assert state.system.residues[-1].name == "L256"
    assert state.system.residues[-1].atom_indices == state.expanded_components[-1]
    assert state.system.chains[-1].chain_id == "L256"
    assert receipt.fragment_count == 256
    assert receipt.bond_count == receipt.expanded_atom_count - receipt.fragment_count
    assert receipt.to_dict()["resource_limits"]["fragments"] == 256


def test_256_charged_singletons_are_iterative_and_receipt_bound(
    supported_local_rdkit: str,
) -> None:
    source = b".".join((b"[Cl-]",) * 256)
    result = round_trip_smiles_source(source, source_id="charged-forest-256")
    state = writer_module._validate_write_state(result.source_ingest.system)
    receipt = result.write_result.receipt

    assert result.write_result.payload == source
    assert state.fragment_count == 256
    assert state.source_atom_count == 256
    assert state.system.atom_count == 256
    assert len(state.system.bonds) == 0
    assert state.source_atom_tokens == ("[Cl-]",) * 256
    assert state.charged_source_atom_count == 256
    assert state.formal_charge_total == -256
    assert receipt.charged_source_atom_count == 256
    assert receipt.formal_charge_total == -256
    assert receipt.bond_count == receipt.expanded_atom_count - receipt.fragment_count


def test_one_simple_ring_among_256_fragments_is_iterative_and_bound(
    supported_local_rdkit: str,
) -> None:
    source = b".".join((*((b"C",) * 255), b"C1CC1"))
    result = round_trip_smiles_source(source, source_id="ring-forest-256")
    state = writer_module._validate_write_state(result.source_ingest.system)
    receipt = result.write_result.receipt

    assert result.write_result.payload == source
    assert state.fragment_count == 256
    assert state.source_atom_count == 258
    assert state.component_cyclomatic_numbers == (*((0,) * 255), 1)
    assert state.ring_atom_indices == (255, 256, 257)
    assert state.ring_closure_source_bond_index == state.source_bond_count - 1
    assert receipt.ring_closure_count == 1
    assert receipt.cyclic_component_count == 1
    assert receipt.ring_size == 3
    assert receipt.bond_count == receipt.expanded_atom_count - 255
    assert receipt.to_dict()["resource_limits"]["ring_components"] == 1
    assert receipt.to_dict()["resource_limits"]["ring_size_min"] == 3
    assert receipt.to_dict()["resource_limits"]["ring_size_max"] == 8


def test_257_isolated_components_fail_at_the_parser_fragment_boundary(
    supported_local_rdkit: str,
) -> None:
    source = b".".join((b"C",) * 257)

    with pytest.raises(SmilesParseError) as exc_info:
        parse_smiles(source)

    assert exc_info.value.code == "too_many_fragments"
