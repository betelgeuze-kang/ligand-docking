from __future__ import annotations

from dataclasses import fields
from pathlib import Path

import pytest

import betelgeuze_engine_v2.molecular.mmcif_nonpoly_covalent_struct_conn_topology as topology_module
from betelgeuze_engine_v2.molecular.mmcif_nonpoly_covalent_struct_conn_topology import (
    MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_PARSER_PEDIGREE_ID,
    MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_PROFILE_ID,
    MmcifNonpolyCovalentStructConnRow,
    MmcifNonpolyCovalentStructConnTopologyError,
    MmcifNonpolyCovalentStructConnTopologyIngestResult,
    MmcifNonpolyCovalentStructConnTopologyRoundTripResult,
    MmcifNonpolyCovalentStructConnTopologyWriteReceipt,
    parse_mmcif_nonpoly_covalent_struct_conn_topology,
    round_trip_mmcif_nonpoly_covalent_struct_conn_topology_source,
    serialize_mmcif_nonpoly_covalent_struct_conn_topology,
    write_mmcif_nonpoly_covalent_struct_conn_topology,
)
from betelgeuze_engine_v2.molecular.observation import (
    attached_parser_observation_sha256_matches,
)
from betelgeuze_engine_v2.molecular.topology import (
    attached_canonical_topology_sha256_matches,
)


FIXTURES = (
    Path(__file__).parents[1]
    / "fixtures"
    / "v2_1_mmcif_nonpoly_covalent_struct_conn_topology"
)
MARKER_KEY = "mmcif_nonpoly_covalent_struct_conn_topology"
MARKER_FIELDS = {
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


def _fixture(name: str = "split_ethane_sing.cif") -> bytes:
    return (FIXTURES / name).read_bytes()


def _row_tokens(data: bytes) -> tuple[list[bytes], int, list[bytes]]:
    lines = data.splitlines()
    for index, line in enumerate(lines):
        if line.startswith((b"ethane_cc ", b"formaldehyde_co ", b"hcn_cn ")):
            return lines, index, line.split()
    raise AssertionError("fixture struct_conn row not found")


def _mutate_row(data: bytes, **positions: str) -> bytes:
    lines, index, tokens = _row_tokens(data)
    for raw_position, value in positions.items():
        tokens[int(raw_position)] = value.encode("ascii")
    lines[index] = b" ".join(tokens)
    return b"\n".join(lines) + b"\n"


def _append_row(data: bytes, row: bytes) -> bytes:
    lines, index, _tokens = _row_tokens(data)
    lines.insert(index + 1, row)
    return b"\n".join(lines) + b"\n"


@pytest.mark.parametrize(
    ("filename", "order", "connection_id"),
    (
        ("split_ethane_sing.cif", 1.0, "ethane_cc"),
        ("split_formaldehyde_doub.cif", 2.0, "formaldehyde_co"),
        ("split_hydrogen_cyanide_trip.cif", 3.0, "hcn_cn"),
    ),
)
def test_materializes_exact_bounded_struct_conn_bond(
    filename: str, order: float, connection_id: str
) -> None:
    ingest = parse_mmcif_nonpoly_covalent_struct_conn_topology(
        _fixture(filename), source_id=filename
    )
    system = ingest.system
    bonds = [bond for bond in system.bonds if bond.source == "mmcif_struct_conn_covale"]

    assert len(bonds) == 1
    bond = bonds[0]
    assert bond.order == order
    assert bond.aromatic is False
    assert bond.stereo == "none"
    assert set(bond.metadata) == {MARKER_KEY}
    marker = bond.metadata[MARKER_KEY]
    assert set(marker) == MARKER_FIELDS
    assert marker["connection_id"] == connection_id
    assert marker["row_ordinal"] == 1
    assert marker["conn_type_id"] == "covale"
    assert marker["ptnr1_symmetry"] == marker["ptnr2_symmetry"] == "1_555"
    assert marker["ptnr1_residue_index"] != marker["ptnr2_residue_index"]
    assert bond.atom_i == min(marker["ptnr1_atom_index"], marker["ptnr2_atom_index"])
    assert bond.atom_j == max(marker["ptnr1_atom_index"], marker["ptnr2_atom_index"])
    assert [item.index for item in system.bonds] == list(range(len(system.bonds)))
    assert [(item.atom_i, item.atom_j) for item in system.bonds] == sorted(
        (item.atom_i, item.atom_j) for item in system.bonds
    )

    document = ingest.to_dict()
    assert (
        document["profile_id"] == MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_PROFILE_ID
    )
    assert (
        document["parser_pedigree_id"]
        == MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_PARSER_PEDIGREE_ID
    )
    assert document["bounded_source_reported_struct_conn_materialized"] is True
    assert document["bounded_inter_residue_topology_interpreted"] is True
    assert document["struct_conn_interpreted"] is False
    assert document["independent_chemistry_established"] is False
    assert document["independent_valence_established"] is False
    assert document["generic_molecular_preparation_ready"] is False
    assert document["parameterability_assessed"] is False
    assert document["runtime_eligible"] is False
    assert document["execution_authorized"] is False
    assert document["claim_safe"] is False
    assert attached_canonical_topology_sha256_matches(system)
    assert attached_parser_observation_sha256_matches(system)


def test_preserves_source_partner_orientation_in_marker() -> None:
    data = _mutate_row(
        _fixture(),
        **{
            "2": "B",
            "9": "A",
            "15": "B",
            "17": "2",
            "18": "A",
            "20": "1",
        },
    )
    ingest = parse_mmcif_nonpoly_covalent_struct_conn_topology(data)
    bond = next(
        item
        for item in ingest.system.bonds
        if item.source == "mmcif_struct_conn_covale"
    )
    marker = bond.metadata[MARKER_KEY]

    assert marker["ptnr1_atom_index"] > marker["ptnr2_atom_index"]
    assert bond.atom_i < bond.atom_j
    assert marker["ptnr1_atom_site_id"] == "5"
    assert marker["ptnr2_atom_site_id"] == "1"


def test_relabels_component_authority_metadata_as_carrier_only() -> None:
    system = parse_mmcif_nonpoly_covalent_struct_conn_topology(_fixture()).system

    assert "mmcif_nonpoly_component_topology" not in system.metadata
    assert "mmcif_nonpoly_component_topology" not in system.provenance.metadata
    assert "carrier_mmcif_nonpoly_component_topology" in system.metadata
    assert "carrier_mmcif_nonpoly_component_topology" in system.provenance.metadata
    assert system.metadata[MARKER_KEY]["general_struct_conn_supported"] is False
    assert system.metadata[MARKER_KEY]["bounded_inter_residue_topology_interpreted"]


def test_writer_emits_exact_category_position_and_stable_round_trip() -> None:
    data = _fixture()
    ingest = parse_mmcif_nonpoly_covalent_struct_conn_topology(data, source_id="ethane")
    written = write_mmcif_nonpoly_covalent_struct_conn_topology(ingest)

    assert written.payload == serialize_mmcif_nonpoly_covalent_struct_conn_topology(
        ingest
    )
    assert written.payload.find(b"\n_struct_conn.id\n") < written.payload.find(
        b"\n_atom_site.group_pdb\n"
    )
    assert (
        written.receipt.output_source_sha256
        == written.to_dict()["output_source_sha256"]
    )

    result = round_trip_mmcif_nonpoly_covalent_struct_conn_topology_source(
        data, source_id="ethane"
    )
    report = result.report.to_dict()
    assert isinstance(result, MmcifNonpolyCovalentStructConnTopologyRoundTripResult)
    assert report["struct_conn_projection_equal"] is True
    assert report["topology_state_equal"] is True
    assert report["topology_equal"] is True
    assert report["carrier_state_equal"] is True
    assert report["emitted_source_reparsed_exact"] is True
    assert report["second_emission_byte_stable"] is True
    assert report["source_reported_covalent_struct_conn_round_trip_preserved"] is True


@pytest.mark.parametrize(
    ("positions", "code"),
    (
        ({"1": "hydrog"}, "unsupported_struct_conn_type"),
        ({"4": "?"}, "unsupported_partner_label_seq_id"),
        ({"6": "?"}, "unsupported_partner_alt_id"),
        ({"7": "."}, "unsupported_partner_insertion_code"),
        ({"8": "2_555"}, "unsupported_partner_symmetry"),
        ({"22": "SING"}, "unsupported_struct_conn_bond_order"),
        ({"22": "quad"}, "unsupported_struct_conn_bond_order"),
        ({"2": "Z", "15": "Z"}, "unknown_struct_conn_partner"),
        ({"17": "2"}, "crosswired_struct_conn_partner"),
    ),
)
def test_rejects_out_of_profile_partner_rows(
    positions: dict[str, str], code: str
) -> None:
    with pytest.raises(MmcifNonpolyCovalentStructConnTopologyError) as caught:
        parse_mmcif_nonpoly_covalent_struct_conn_topology(
            _mutate_row(_fixture(), **positions)
        )
    assert caught.value.code == code


@pytest.mark.parametrize(
    ("positions", "code"),
    (
        (
            {
                "9": "A",
                "18": "A",
                "20": "1",
            },
            "self_struct_conn_bond",
        ),
        (
            {
                "5": "H1",
                "9": "A",
                "12": "H2",
                "18": "A",
                "20": "1",
            },
            "same_residue_struct_conn_bond",
        ),
        (
            {
                "9": "A",
                "12": "H1",
                "18": "A",
                "20": "1",
            },
            "already_materialized_bond",
        ),
    ),
)
def test_rejects_self_same_residue_and_already_bonded_rows(
    positions: dict[str, str], code: str
) -> None:
    with pytest.raises(MmcifNonpolyCovalentStructConnTopologyError) as caught:
        parse_mmcif_nonpoly_covalent_struct_conn_topology(
            _mutate_row(_fixture(), **positions)
        )
    assert caught.value.code == code


def test_rejects_duplicate_id_and_reversed_endpoint_pair() -> None:
    original = _row_tokens(_fixture())[2]
    with pytest.raises(MmcifNonpolyCovalentStructConnTopologyError) as duplicate_id:
        parse_mmcif_nonpoly_covalent_struct_conn_topology(
            _append_row(_fixture(), b" ".join(original))
        )
    assert duplicate_id.value.code == "duplicate_struct_conn_id"

    reversed_row = (
        b"ethane_cc_reverse covale B MTH . C . ? 1_555 "
        b"A MTH . C . ? B MTH 2 A MTH 1 1_555 sing"
    )
    with pytest.raises(MmcifNonpolyCovalentStructConnTopologyError) as reversed_pair:
        parse_mmcif_nonpoly_covalent_struct_conn_topology(
            _append_row(_fixture(), reversed_row)
        )
    assert reversed_pair.value.code == "duplicate_struct_conn_bond"


def test_requires_bare_tokens_exact_headers_and_at_least_one_row() -> None:
    quoted = _fixture().replace(b"ethane_cc covale", b"'ethane_cc' covale", 1)
    with pytest.raises(MmcifNonpolyCovalentStructConnTopologyError) as token_error:
        parse_mmcif_nonpoly_covalent_struct_conn_topology(quoted)
    assert token_error.value.code == "invalid_struct_conn_token"

    headers = _fixture().replace(
        b"_struct_conn.pdbx_value_order", b"_struct_conn.details", 1
    )
    with pytest.raises(MmcifNonpolyCovalentStructConnTopologyError) as header_error:
        parse_mmcif_nonpoly_covalent_struct_conn_topology(headers)
    assert header_error.value.code == "unsupported_struct_conn_headers"

    lines, index, _tokens = _row_tokens(_fixture())
    del lines[index]
    no_rows = b"\n".join(lines) + b"\n"
    with pytest.raises(MmcifNonpolyCovalentStructConnTopologyError) as row_error:
        parse_mmcif_nonpoly_covalent_struct_conn_topology(no_rows)
    assert row_error.value.code == "empty_loop"


def test_enforces_resource_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    data = _fixture()
    monkeypatch.setattr(
        topology_module, "MAX_MMCIF_NONPOLY_COVALENT_STRUCT_CONN_ROWS", 0
    )
    with pytest.raises(MmcifNonpolyCovalentStructConnTopologyError) as row_error:
        parse_mmcif_nonpoly_covalent_struct_conn_topology(data)
    assert row_error.value.code == "too_many_struct_conn_rows"

    monkeypatch.setattr(
        topology_module,
        "MAX_MMCIF_NONPOLY_COVALENT_STRUCT_CONN_ROWS",
        120_000,
    )
    monkeypatch.setattr(
        topology_module,
        "MAX_MMCIF_NONPOLY_COVALENT_STRUCT_CONN_MATERIALIZED_BONDS",
        6,
    )
    with pytest.raises(MmcifNonpolyCovalentStructConnTopologyError) as bond_error:
        parse_mmcif_nonpoly_covalent_struct_conn_topology(data)
    assert bond_error.value.code == "too_many_materialized_bonds"

    monkeypatch.setattr(
        topology_module,
        "MAX_MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_INPUT_BYTES",
        len(data) - 1,
    )
    with pytest.raises(MmcifNonpolyCovalentStructConnTopologyError) as input_error:
        parse_mmcif_nonpoly_covalent_struct_conn_topology(data)
    assert input_error.value.code == "input_too_large"


def test_factory_only_records_and_detached_system_snapshot() -> None:
    ingest = parse_mmcif_nonpoly_covalent_struct_conn_topology(_fixture())
    first = ingest.system
    second = ingest.system

    assert first is not second
    assert first.atoms == second.atoms
    assert first.bonds == second.bonds
    assert first.residues == second.residues
    assert first.chains == second.chains
    assert first.coordinates.equal(second.coordinates)
    with pytest.raises(TypeError, match="factory-only"):
        MmcifNonpolyCovalentStructConnRow(values=("x",) * 23, order=1.0, row_ordinal=1)
    with pytest.raises(TypeError, match="factory-only"):
        MmcifNonpolyCovalentStructConnTopologyIngestResult(None)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="factory-only"):
        MmcifNonpolyCovalentStructConnTopologyWriteReceipt(  # type: ignore[arg-type]
            ingest, b"", {}
        )


def test_ingest_and_artifact_tampering_fail_closed() -> None:
    ingest = parse_mmcif_nonpoly_covalent_struct_conn_topology(_fixture())
    object.__setattr__(ingest, "_projection_bytes", b"{}")
    with pytest.raises(MmcifNonpolyCovalentStructConnTopologyError) as stale_ingest:
        _ = ingest.system
    assert stale_ingest.value.code == "stale_ingest_binding"

    clean = parse_mmcif_nonpoly_covalent_struct_conn_topology(_fixture())
    written = write_mmcif_nonpoly_covalent_struct_conn_topology(clean)
    receipt = written.receipt
    object.__setattr__(receipt, "_document_bytes", b"{}")
    with pytest.raises(MmcifNonpolyCovalentStructConnTopologyError) as stale_receipt:
        _ = receipt.output_source_sha256
    assert stale_receipt.value.code == "stale_write_receipt_binding"


def test_struct_conn_rows_are_detached_and_internal_tampering_fails_closed() -> None:
    ingest = parse_mmcif_nonpoly_covalent_struct_conn_topology(_fixture())
    returned = ingest.struct_conn_rows[0]
    original_connection_id = returned.connection_id

    object.__setattr__(returned, "connection_id", "detached-forgery")
    assert ingest.struct_conn_rows[0].connection_id == original_connection_id
    assert write_mmcif_nonpoly_covalent_struct_conn_topology(ingest).payload

    internal = ingest._struct_conn_rows[0]
    object.__setattr__(internal, "connection_id", "internal-forgery")
    with pytest.raises(MmcifNonpolyCovalentStructConnTopologyError) as stale_ingest:
        ingest.to_dict()
    assert stale_ingest.value.code == "stale_ingest_binding"

    coherent = parse_mmcif_nonpoly_covalent_struct_conn_topology(_fixture())
    coherent_internal = coherent._struct_conn_rows[0]
    object.__setattr__(coherent_internal, "connection_id", "coherent-forgery")
    forged_state = topology_module._state_from_ingest(coherent)
    forged_access = topology_module._canonical_json_bytes(
        topology_module._state_access_binding_document(forged_state)
    )
    object.__setattr__(coherent, "_access_binding_bytes", forged_access)
    with pytest.raises(MmcifNonpolyCovalentStructConnTopologyError) as anchored:
        write_mmcif_nonpoly_covalent_struct_conn_topology(coherent)
    assert anchored.value.code == "stale_ingest_binding"


def test_semantic_state_excludes_source_identity_and_source_specific_snapshot() -> None:
    source = _fixture()
    first = parse_mmcif_nonpoly_covalent_struct_conn_topology(
        source, source_id="source-a"
    )
    second = parse_mmcif_nonpoly_covalent_struct_conn_topology(
        source, source_id="source-b"
    )

    assert first.topology_state_sha256 == second.topology_state_sha256
    assert first.struct_conn_projection_sha256 == second.struct_conn_projection_sha256
    assert first.augmented_topology_sha256 == second.augmented_topology_sha256
    assert first.source_binding_sha256 != second.source_binding_sha256
    assert first.source_id_sha256 != second.source_id_sha256
    semantic = topology_module._topology_state_document(
        topology_module._state_from_ingest(first)
    )
    assert "source_id_sha256" not in semantic
    assert "carrier_augmented_system_snapshot_sha256" not in semantic
    evidence = first.to_dict()
    assert evidence["source_id_sha256"] == first.source_id_sha256
    assert evidence["carrier_augmented_system_snapshot_sha256"] == (
        first.carrier_ingest.augmented_system_snapshot_sha256
    )


def test_public_nested_artifacts_are_detached_from_parent_state() -> None:
    source = _fixture()
    ingest = parse_mmcif_nonpoly_covalent_struct_conn_topology(
        source, source_id="detached"
    )
    carrier = ingest.carrier_ingest
    assert carrier is not ingest._carrier_ingest
    object.__setattr__(carrier, "_projection_bytes", b"{}")
    assert ingest.to_dict()["topology_state_sha256"] == ingest.topology_state_sha256

    written = write_mmcif_nonpoly_covalent_struct_conn_topology(ingest)
    receipt = written.receipt
    assert receipt is not written._receipt
    object.__setattr__(receipt, "_document_bytes", b"{}")
    assert (
        written.to_dict()["output_source_sha256"]
        == written.receipt.output_source_sha256
    )

    result = round_trip_mmcif_nonpoly_covalent_struct_conn_topology_source(
        source, source_id="detached"
    )
    detached_source = result.source_ingest
    detached_write = result.write_result
    detached_reparsed = result.reparsed_ingest
    detached_second = result.reemitted_write_result
    detached_report = result.report
    assert detached_source is not result._source_ingest
    assert detached_write is not result._write_result
    assert detached_reparsed is not result._reparsed_ingest
    assert detached_second is not result._reemitted_write_result
    assert detached_report is not result._report
    object.__setattr__(detached_source, "_projection_bytes", b"{}")
    object.__setattr__(detached_write, "_payload", b"")
    object.__setattr__(detached_reparsed, "_projection_bytes", b"{}")
    object.__setattr__(detached_second, "_payload", b"")
    object.__setattr__(detached_report, "_document_bytes", b"{}")
    assert (
        result.to_dict()["report"][
            "source_reported_covalent_struct_conn_round_trip_preserved"
        ]
        is True
    )


def test_forged_and_crosswired_artifacts_have_no_live_factory_anchor() -> None:
    first = parse_mmcif_nonpoly_covalent_struct_conn_topology(_fixture())
    forged = object.__new__(type(first))
    for item in fields(first):
        object.__setattr__(forged, item.name, getattr(first, item.name))
    with pytest.raises(MmcifNonpolyCovalentStructConnTopologyError) as forged_error:
        _ = forged.system
    assert forged_error.value.code == "stale_ingest_binding"

    first_write = write_mmcif_nonpoly_covalent_struct_conn_topology(first)
    second = parse_mmcif_nonpoly_covalent_struct_conn_topology(
        _fixture("split_formaldehyde_doub.cif")
    )
    second_write = write_mmcif_nonpoly_covalent_struct_conn_topology(second)
    object.__setattr__(first_write, "_receipt", second_write.receipt)
    with pytest.raises(MmcifNonpolyCovalentStructConnTopologyError) as crosswired:
        _ = first_write.payload
    assert crosswired.value.code == "stale_write_result_binding"
