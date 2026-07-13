from __future__ import annotations

from dataclasses import replace
import hashlib
from pathlib import Path
import struct

import pytest
import torch

from betelgeuze_engine_v2.molecular import (
    Bond,
    PDB_REPRESENTABLE_STATE_SCHEMA_ID,
    PDB_ROUND_TRIP_REPORT_SCHEMA_ID,
    PDB_WRITER_VERSION,
    PDB_WRITE_RECEIPT_SCHEMA_ID,
    PdbRoundTripReport,
    PdbRoundTripResult,
    PdbWriteError,
    PdbWriteReceipt,
    PdbWriteResult,
    SourceReportedMissingAtomClaim,
    SourceReportedMissingResidueClaim,
    UnitCell,
    build_source_reported_missingness_report,
    canonical_all_atom_snapshot_digest,
    canonical_topology_sha256,
    parse_pdb,
    pdb_representable_state_sha256,
    round_trip_pdb_source,
    serialize_pdb,
    write_pdb,
)
from betelgeuze_engine_v2.molecular import pdb_writer as writer_module


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
MINI_PROTEIN = FIXTURES / "tier_beta" / "mini_protein.pdb"


def _atom(
    serial: int,
    *,
    record: str = "ATOM",
    atom_name_field: str = " CA ",
    residue: str = "GLY",
    chain: str = "A",
    residue_number: int = 1,
    insertion_code: str = " ",
    altloc: str = " ",
    x: float = 0.0,
    y: float = 0.0,
    z: float = 0.0,
    occupancy: float | None = 1.0,
    b_factor: float | None = 20.0,
    segment_id: str = "",
    element: str = "C",
    charge: str = "",
) -> str:
    assert len(atom_name_field) == 4
    occupancy_field = " " * 6 if occupancy is None else f"{occupancy:6.2f}"
    b_factor_field = " " * 6 if b_factor is None else f"{b_factor:6.2f}"
    line = (
        f"{record:<6}{serial:5d} {atom_name_field}{altloc:1}{residue:>3} {chain:1}"
        f"{residue_number:4d}{insertion_code:1}   {x:8.3f}{y:8.3f}{z:8.3f}"
        f"{occupancy_field}{b_factor_field}{'':6}{segment_id:<4}{element:>2}{charge:>2}"
    )
    assert len(line) == 80
    return line


def _ter(
    serial: int,
    *,
    residue: str = "GLY",
    chain: str = "A",
    residue_number: int = 1,
    insertion_code: str = " ",
) -> str:
    return (
        f"{'TER':<6}{serial:5d}{'':6}{residue:>3} {chain:1}"
        f"{residue_number:4d}{insertion_code:1}"
    )


def _model(model_id: int) -> str:
    return f"MODEL     {model_id:4d}"


def _cryst1(
    *,
    a: float = 20.0,
    b: float = 21.0,
    c: float = 22.0,
    alpha: float = 90.0,
    beta: float = 90.0,
    gamma: float = 90.0,
    space_group: str = "P 1",
    z: int | None = 1,
) -> str:
    z_field = " " * 4 if z is None else f"{z:4d}"
    return (
        f"CRYST1{a:9.3f}{b:9.3f}{c:9.3f}"
        f"{alpha:7.2f}{beta:7.2f}{gamma:7.2f} {space_group:<11}{z_field}"
    )


def _raw_cryst1(
    *,
    lengths: tuple[str, str, str],
    angles: tuple[str, str, str],
    space_group: str = "P 1",
    z: str = "   1",
) -> str:
    assert all(len(value) == 9 for value in lengths)
    assert all(len(value) == 7 for value in angles)
    assert len(space_group) <= 11
    assert len(z) == 4
    return (
        "CRYST1" + "".join(lengths) + "".join(angles) + " " + f"{space_group:<11}" + z
    )


def _remark_header(number: int, text: str = "") -> str:
    return f"REMARK {number:3d} {text}".rstrip()


def _remark_465(
    residue: str,
    chain: str,
    residue_number: int,
    *,
    model_id: int | None = None,
    insertion_code: str = " ",
) -> str:
    line = [" "] * 80
    line[0:6] = "REMARK"
    line[7:10] = "465"
    if model_id is not None:
        line[11:14] = f"{model_id:3d}"
    line[15:18] = f"{residue:>3}"
    line[19] = chain or " "
    line[21:26] = f"{residue_number:5d}"
    line[26] = insertion_code
    return "".join(line).rstrip()


def _remark_470(
    residue: str,
    chain: str,
    residue_number: int,
    atoms: tuple[str, ...],
    *,
    model_id: int | None = None,
    insertion_code: str = " ",
) -> str:
    line = [" "] * 80
    line[0:6] = "REMARK"
    line[7:10] = "470"
    if model_id is not None:
        line[11:14] = f"{model_id:3d}"
    line[15:18] = f"{residue:>3}"
    line[20] = chain or " "
    line[21:25] = f"{residue_number:4d}"
    line[25] = insertion_code
    atom_text = " ".join(atoms)
    line[28 : 28 + len(atom_text)] = atom_text
    return "".join(line).rstrip()


def _pdb(*lines: str) -> bytes:
    return ("\n".join((*lines, "END")) + "\n").encode("ascii")


def _assert_error(system, code: str) -> None:
    with pytest.raises(PdbWriteError) as exc_info:
        write_pdb(system)
    assert exc_info.value.code == code


def _binary64(value: float) -> bytes:
    return struct.pack(">d", float(value))


def _base_system():
    return parse_pdb(
        _pdb(
            _atom(1),
            _atom(2, atom_name_field=" N  ", residue_number=2, element="N"),
        )
    ).system


def _replace_coordinate(system, value: float):
    coordinates = system.coordinates.clone()
    coordinates[0, 0, 0] = value
    return replace(system, coordinates=coordinates)


def _replace_atom(system, **changes):
    return replace(
        system,
        atoms=(replace(system.atoms[0], **changes), *system.atoms[1:]),
    )


def _replace_provenance_metadata(system, key: str, value):
    metadata = dict(system.provenance.metadata)
    metadata[key] = value
    return replace(system, provenance=replace(system.provenance, metadata=metadata))


def _replace_pdb_metadata(system, key: str, value):
    pdb_metadata = dict(system.metadata["pdb"])
    pdb_metadata[key] = value
    return replace(system, metadata={"pdb": pdb_metadata})


def _replace_cryst1_metadata(system, key: str, value):
    cryst1 = dict(system.metadata["pdb"]["cryst1"])
    cryst1[key] = value
    return _replace_pdb_metadata(system, "cryst1", cryst1)


def _replace_missingness_report(system, report):
    pdb_metadata = dict(system.metadata["pdb"])
    pdb_metadata["source_reported_missingness"] = report.to_dict()
    provenance_metadata = dict(system.provenance.metadata)
    provenance_metadata["source_missingness_evidence_sha256"] = report.report_sha256
    coverage = dict(provenance_metadata["coverage"])
    coverage["source_missingness_evidence_sha256"] = report.report_sha256
    provenance_metadata["coverage"] = coverage
    return replace(
        system,
        provenance=replace(system.provenance, metadata=provenance_metadata),
        metadata={"pdb": pdb_metadata},
    )


def test_writer_public_contract_and_mini_protein_normalized_golden() -> None:
    source = MINI_PROTEIN.read_bytes()
    result = round_trip_pdb_source(source, source_id="tier-beta-mini-protein")
    payload = result.write_result.payload

    assert PDB_WRITER_VERSION == "1.2.0"
    assert PDB_REPRESENTABLE_STATE_SCHEMA_ID == (
        "betelgeuze.pdb_representable_state/1.2.0"
    )
    assert PDB_WRITE_RECEIPT_SCHEMA_ID == "betelgeuze.pdb_write_receipt/1.2.0"
    assert PDB_ROUND_TRIP_REPORT_SCHEMA_ID == ("betelgeuze.pdb_round_trip_report/1.2.0")
    assert writer_module.PDB_MISSINGNESS_SEMANTIC_SCHEMA_ID == (
        "betelgeuze.pdb_source_reported_missingness_semantic_projection/1.0.0"
    )
    assert writer_module.PDB_MISSINGNESS_PROFILE_ID == (
        "single_model_id1_source_reported_remark_465_470_semantic_roundtrip/1.0.0"
    )
    expected = b"\n".join(line.ljust(80) for line in source.splitlines()) + b"\n"
    assert payload == expected
    assert payload != source
    assert hashlib.sha256(payload).hexdigest() == (
        result.write_result.receipt.output_source_sha256
    )
    assert (
        result.write_result.receipt.parent_source_sha256
        == hashlib.sha256(source).hexdigest()
    )
    assert result.write_result.receipt.input_snapshot_sha256 == (
        canonical_all_atom_snapshot_digest(result.source_ingest.system)
    )
    assert result.write_result.receipt.input_topology_sha256 == (
        canonical_topology_sha256(result.source_ingest.system)
    )
    assert result.write_result.receipt.input_representable_state_sha256 == (
        pdb_representable_state_sha256(result.source_ingest.system)
    )
    assert len(payload) == 891
    assert result.write_result.receipt.input_snapshot_sha256 == (
        "fd82f7360362ba09d531a1865a258a34fa1a0c27ba6d8d2e9d8888d032451e0a"
    )
    assert result.write_result.receipt.input_topology_sha256 == (
        "176ae0513e65d06c9740b3d83544df0928c43f900a659ef152fca223ba1caf99"
    )
    assert result.write_result.receipt.input_representable_state_sha256 == (
        "603f9a24a8903539c3f03d0dc1e589c3de6ec01ae81b67cd062100d99325f1a4"
    )
    assert result.write_result.receipt.output_source_sha256 == (
        "77927d40c699eec7bf150a304af89ad7365ef3d4f1e070110cfafceb7d39c3cb"
    )
    receipt = result.write_result.receipt.to_dict()
    assert receipt["schema_id"] == PDB_WRITE_RECEIPT_SCHEMA_ID
    assert receipt["source_authentication_status"] == "not_authenticated"
    assert receipt["cell_present"] is False
    assert receipt["cryst1_count"] == 0
    assert receipt["preparation_ready"] is False
    assert receipt["claim_safe"] is False
    assert receipt["receipt_sha256"] == result.write_result.receipt.receipt_sha256
    assert receipt["receipt_sha256"] == (
        "bc3d22bad36bac41b24cd8e0e87d38d784a33c9a82c7177db7a3a16eafb5b4af"
    )

    report = result.report.to_dict()
    assert report["schema_id"] == PDB_ROUND_TRIP_REPORT_SCHEMA_ID
    assert report["declared_projection_sha256_equal"] is True
    assert report["canonical_topology_sha256_equal"] is True
    assert report["coordinate_binary64_projection_equal"] is True
    assert report["cryst1_cell_binary64_projection_equal"] is True
    assert report["declared_parser_marker_projection_equal"] is True
    assert report["emitted_source_sha256_and_bytes_stable"] is True
    assert report["full_canonical_snapshot_equality_claimed"] is False
    assert report["dynamic_source_provenance_equality_claimed"] is False
    assert report["claim_safe"] is False
    assert report["report_sha256"] == result.report.report_sha256
    assert report["report_sha256"] == (
        "4e0ca55a8a71c9ec98c2527e1617c13451bbb86b0b83c0464be976314a8b4e62"
    )


def test_single_model_missingness_465_and_470_semantic_round_trip() -> None:
    residue_only = round_trip_pdb_source(_pdb(_remark_465("ALA", "A", 2), _atom(1)))
    assert residue_only.write_result.receipt.missingness_evidence_present is True
    assert residue_only.write_result.receipt.missing_residue_claim_count == 1
    assert residue_only.write_result.receipt.missing_atom_claim_count == 0
    residue_semantic = writer_module._validate_write_state(
        residue_only.source_ingest.system
    ).missingness_semantic_document
    assert residue_semantic["evidence_status"] == "present_fully_preserved"
    assert residue_semantic["coordinate_scope"] == "deposited_coordinates"
    assert residue_semantic["total_claim_count"] == 1
    assert residue_semantic["completion_attempted"] is False
    assert residue_semantic["preparation_ready"] is False
    assert residue_semantic["claim_safe"] is False
    assert residue_only.write_result.receipt.to_dict()["simulation_ready"] is False
    residue_lines = residue_only.write_result.payload.decode("ascii").splitlines()
    assert [line[:10] for line in residue_lines[:3]] == [
        "REMARK 465",
        "REMARK 465",
        "REMARK 465",
    ]

    atom_only = round_trip_pdb_source(
        _pdb(_remark_470("GLY", "A", 1, ("CB", "O")), _atom(1))
    )
    receipt = atom_only.write_result.receipt
    assert receipt.missing_residue_claim_count == 0
    assert receipt.missing_atom_claim_count == 2
    assert receipt.input_missingness_remark_line_count == 1
    assert receipt.emitted_missingness_remark_line_count == 4
    atom_lines = atom_only.write_result.payload.decode("ascii").splitlines()
    data_lines = [line for line in atom_lines if line.startswith("REMARK 470     GLY")]
    assert len(data_lines) == 2
    assert data_lines[0][28:].strip() == "CB"
    assert data_lines[1][28:].strip() == "O"
    assert all(len(line) == 80 and line.isascii() for line in atom_lines)


def test_grouped_missingness_normalizes_raw_layout_but_preserves_semantics() -> None:
    source = _pdb(
        _remark_header(465, "MISSING RESIDUES"),
        _remark_465("ALA", "A", 2),
        _remark_header(470, "MISSING ATOM"),
        _remark_470("GLY", "A", 1, ("CB", "O")),
        _atom(1),
    )
    result = round_trip_pdb_source(source)
    assert (
        result.report.input_missingness_report_sha256
        != result.report.reparsed_missingness_report_sha256
    )
    assert (
        result.report.input_missingness_semantic_sha256
        == result.report.reparsed_missingness_semantic_sha256
    )
    report = result.report.to_dict()
    assert report["missingness_semantic_sha256_equal"] is True
    assert report["missingness_raw_report_sha256_equal_claimed"] is False
    assert report["missingness_raw_source_layout_equal_claimed"] is False
    assert result.write_result.payload.count(b"REMARK 470     GLY") == 2


def test_missingness_blank_chain_negative_sequence_and_insertion_round_trip() -> None:
    source = _pdb(
        _remark_465("GLY", "", -2, insertion_code="A"),
        _remark_470("GLY", "", -1, ("CB",), insertion_code="B"),
        _atom(1, chain="", residue_number=-1, insertion_code="B"),
    )
    result = round_trip_pdb_source(source)
    semantic = writer_module._validate_write_state(
        result.source_ingest.system
    ).missingness_semantic_document
    residue = semantic["ordered_missing_residue_claims"][0]
    atom = semantic["ordered_missing_atom_claims"][0]
    assert (
        residue["chain_id"],
        residue["residue_number"],
        residue["insertion_code"],
    ) == (
        "",
        -2,
        "A",
    )
    assert (atom["chain_id"], atom["residue_number"], atom["insertion_code"]) == (
        "",
        -1,
        "B",
    )


def test_implicit_and_explicit_model_one_have_equal_missingness_semantics() -> None:
    implicit = round_trip_pdb_source(_pdb(_remark_465("ALA", "A", 2), _atom(1)))
    explicit = round_trip_pdb_source(
        _pdb(
            _remark_465("ALA", "A", 2, model_id=1),
            _model(1),
            _atom(1),
            "ENDMDL",
        )
    )
    assert (
        implicit.report.input_missingness_semantic_sha256
        == explicit.report.input_missingness_semantic_sha256
    )
    assert (
        implicit.report.input_missingness_report_sha256
        != explicit.report.input_missingness_report_sha256
    )
    assert implicit.write_result.payload == explicit.write_result.payload


def test_missingness_integer_source_spelling_normalizes_to_canonical_fields() -> None:
    residue_line = list(_remark_465("ALA", "A", 2).ljust(80))
    residue_line[21:26] = "  +02"
    atom_line = list(_remark_470("GLY", "A", 1, ("CB",)).ljust(80))
    atom_line[21:25] = "+001"
    result = round_trip_pdb_source(
        _pdb(
            "".join(residue_line).rstrip(),
            "".join(atom_line).rstrip(),
            _atom(1),
        )
    )
    output = result.write_result.payload.decode("ascii").splitlines()
    assert any(
        line[21:26] == "    2" for line in output if line.startswith("REMARK 465")
    )
    assert any(
        line[21:25] == "   1" for line in output if line.startswith("REMARK 470")
    )
    assert result.report.input_missingness_semantic_sha256 == (
        result.report.reparsed_missingness_semantic_sha256
    )


def test_cryst1_missingness_ter_order_and_canonical_fixed_point() -> None:
    source = _pdb(
        _cryst1(),
        _remark_465("ALA", "A", 2),
        _remark_470("GLY", "A", 1, ("CB",)),
        _atom(1),
        _ter(2),
    )
    result = round_trip_pdb_source(source)
    lines = result.write_result.payload.splitlines()
    assert lines[0].startswith(b"CRYST1")
    assert lines[1].startswith(b"REMARK 465")
    assert next(
        index for index, line in enumerate(lines) if line.startswith(b"ATOM")
    ) > (
        next(
            index for index, line in enumerate(lines) if line.startswith(b"REMARK 470")
        )
    )
    assert next(
        index for index, line in enumerate(lines) if line.startswith(b"TER")
    ) > (next(index for index, line in enumerate(lines) if line.startswith(b"ATOM")))
    assert serialize_pdb(parse_pdb(result.write_result.payload).system) == (
        result.write_result.payload
    )


def test_missingness_writer_rejects_nmr_range_and_non_id1_scope() -> None:
    nmr_source = _pdb(
        "REMARK 465   MODELS 1-2",
        _remark_465("ALA", "A", 2),
        _model(1),
        _atom(1),
        "ENDMDL",
        _model(2),
        _atom(1),
        "ENDMDL",
    )
    _assert_error(parse_pdb(nmr_source).system, "unsupported_missingness_model_scope")

    model_two_source = _pdb(
        _remark_465("ALA", "A", 2, model_id=2),
        _model(2),
        _atom(1),
        "ENDMDL",
    )
    _assert_error(
        parse_pdb(model_two_source).system,
        "unsupported_missingness_model_scope",
    )


def test_missingness_raw_report_resource_and_width_tamper_fail_closed() -> None:
    system = parse_pdb(_pdb(_remark_465("ALA", "A", 2), _atom(1))).system

    source_missingness = dict(system.metadata["pdb"]["source_missingness"])
    raw_records = [dict(record) for record in source_missingness["raw_records"]]
    raw_records[0]["raw_line"] = _remark_465("GLY", "A", 3)
    source_missingness["raw_records"] = raw_records
    _assert_error(
        _replace_pdb_metadata(system, "source_missingness", source_missingness),
        "missingness_raw_claim_mismatch",
    )

    resource_usage = dict(system.metadata["pdb"]["resource_usage"])
    resource_usage["missing_residue_claims"] = 0
    _assert_error(
        _replace_pdb_metadata(system, "resource_usage", resource_usage),
        "unsupported_resource_metadata",
    )

    old_claim = system.metadata["pdb"]["source_reported_missingness"][
        "missing_residue_claims"
    ][0]
    overflow_claim = SourceReportedMissingResidueClaim(
        source_ordinal=1,
        source_category="PDB_REMARK_465",
        source_model_id=old_claim["source_model_id"],
        source_chain_id=old_claim["source_chain_id"],
        source_residue_id="100000",
        source_residue_name=old_claim["source_residue_name"],
        source_insertion_code=old_claim["source_insertion_code"],
        raw_payload={
            "line_number": old_claim["raw_payload"]["line_number"],
            "raw_line": old_claim["raw_payload"]["raw_line"],
            "model_field": old_claim["raw_payload"]["model_field"],
            "target_model_scope": {
                "kind": "explicit_model_ids",
                "model_ids": [1],
                "count": 1,
            },
        },
    )
    overflow_report = build_source_reported_missingness_report(
        source_format="pdb",
        source_sha256=system.provenance.source_sha256,
        canonical_topology_sha256=canonical_topology_sha256(system),
        coordinate_scope="deposited_coordinates",
        altloc_status="not_present",
        requested_altloc_id="",
        assembly_status="not_supported_for_pdb",
        requested_assembly_id="",
        missing_residue_claims=(overflow_claim,),
    )
    _assert_error(
        _replace_missingness_report(system, overflow_report),
        "missingness_residue_number_overflow",
    )

    atom_system = parse_pdb(_pdb(_remark_470("GLY", "A", 1, ("CB",)), _atom(1))).system
    old_atom_claim = atom_system.metadata["pdb"]["source_reported_missingness"][
        "missing_atom_claims"
    ][0]
    atom_overflow_claim = SourceReportedMissingAtomClaim(
        source_ordinal=1,
        source_category="PDB_REMARK_470",
        source_model_id=old_atom_claim["source_model_id"],
        source_chain_id=old_atom_claim["source_chain_id"],
        source_residue_id="10000",
        source_residue_name=old_atom_claim["source_residue_name"],
        source_insertion_code=old_atom_claim["source_insertion_code"],
        source_atom_name=old_atom_claim["source_atom_name"],
        source_altloc_id="",
        raw_payload={
            "line_number": old_atom_claim["raw_payload"]["line_number"],
            "raw_line": old_atom_claim["raw_payload"]["raw_line"],
            "atom_position_in_row": old_atom_claim["raw_payload"][
                "atom_position_in_row"
            ],
            "model_field": old_atom_claim["raw_payload"]["model_field"],
            "target_model_scope": {
                "kind": "explicit_model_ids",
                "model_ids": [1],
                "count": 1,
            },
        },
    )
    atom_overflow_report = build_source_reported_missingness_report(
        source_format="pdb",
        source_sha256=atom_system.provenance.source_sha256,
        canonical_topology_sha256=canonical_topology_sha256(atom_system),
        coordinate_scope="deposited_coordinates",
        altloc_status="not_present",
        requested_altloc_id="",
        assembly_status="not_supported_for_pdb",
        requested_assembly_id="",
        missing_atom_claims=(atom_overflow_claim,),
    )
    _assert_error(
        _replace_missingness_report(atom_system, atom_overflow_report),
        "missingness_residue_number_overflow",
    )


def test_missingness_report_selection_binding_is_exact_pdb_state() -> None:
    result = parse_pdb(_pdb(_remark_465("ALA", "A", 2), _atom(1)))
    system = result.system
    original = result.missingness_evidence

    wrong_format = build_source_reported_missingness_report(
        source_format="mmcif",
        source_sha256=system.provenance.source_sha256,
        canonical_topology_sha256=canonical_topology_sha256(system),
        coordinate_scope="deposited_asymmetric_unit",
        altloc_status="not_present",
        requested_altloc_id="",
        assembly_status="not_present",
        requested_assembly_id="",
        missing_residue_claims=original.missing_residue_claims,
        missing_atom_claims=original.missing_atom_claims,
    )
    _assert_error(
        _replace_missingness_report(system, wrong_format),
        "unsupported_missingness_evidence_binding",
    )

    selected_altloc = build_source_reported_missingness_report(
        source_format="pdb",
        source_sha256=system.provenance.source_sha256,
        canonical_topology_sha256=canonical_topology_sha256(system),
        coordinate_scope="deposited_coordinates",
        altloc_status="explicit_id_selected",
        requested_altloc_id="A",
        assembly_status="not_supported_for_pdb",
        requested_assembly_id="",
        missing_residue_claims=original.missing_residue_claims,
        missing_atom_claims=original.missing_atom_claims,
    )
    _assert_error(
        _replace_missingness_report(system, selected_altloc),
        "unsupported_missingness_evidence_binding",
    )


def test_missingness_nested_metadata_rejects_bool_integer_coercion() -> None:
    result = parse_pdb(_pdb(_remark_465("ALA", "A", 2), _atom(1)))
    system = result.system
    original = result.missingness_evidence.missing_residue_claims[0]
    forged_claim = SourceReportedMissingResidueClaim(
        source_ordinal=1,
        source_category=original.source_category,
        source_model_id=original.source_model_id,
        source_chain_id=original.source_chain_id,
        source_residue_id=original.source_residue_id,
        source_residue_name=original.source_residue_name,
        source_insertion_code=original.source_insertion_code,
        raw_payload={
            "line_number": original.raw_payload["line_number"],
            "raw_line": original.raw_payload["raw_line"],
            "model_field": original.raw_payload["model_field"],
            "target_model_scope": {
                "kind": "explicit_model_ids",
                "model_ids": [True],
                "count": True,
            },
        },
    )
    forged_report = build_source_reported_missingness_report(
        source_format="pdb",
        source_sha256=system.provenance.source_sha256,
        canonical_topology_sha256=canonical_topology_sha256(system),
        coordinate_scope="deposited_coordinates",
        altloc_status="not_present",
        requested_altloc_id="",
        assembly_status="not_supported_for_pdb",
        requested_assembly_id="",
        missing_residue_claims=(forged_claim,),
    )
    _assert_error(
        _replace_missingness_report(system, forged_report),
        "unsupported_missingness_model_scope",
    )

    coverage = dict(system.provenance.metadata["coverage"])
    coverage["supported"] = 1
    _assert_error(
        _replace_provenance_metadata(system, "coverage", coverage),
        "stale_pdb_coverage",
    )

    resource_usage = dict(system.metadata["pdb"]["resource_usage"])
    resource_usage["atom_rows"] = True
    _assert_error(
        _replace_pdb_metadata(system, "resource_usage", resource_usage),
        "unsupported_resource_metadata",
    )


@pytest.mark.parametrize("field_name", ["after_atom_serial", "residue_number"])
def test_ter_metadata_rejects_bool_integer_coercion(field_name: str) -> None:
    system = parse_pdb(_pdb(_atom(1), _ter(2))).system
    models = [dict(model) for model in system.metadata["pdb"]["ter_records_by_model"]]
    records = [dict(record) for record in models[0]["records"]]
    records[0][field_name] = True
    models[0]["records"] = records

    _assert_error(
        _replace_pdb_metadata(system, "ter_records_by_model", models),
        "unsupported_ter_metadata",
    )


def test_missingness_claim_order_and_residue_locator_ambiguity_fail_closed() -> None:
    locator_conflict = parse_pdb(
        _pdb(_remark_465("ALA", "A", 1), _atom(1, residue="GLY"))
    ).system
    _assert_error(locator_conflict, "missing_residue_present_in_coordinates")

    ambiguous = parse_pdb(
        _pdb(
            _remark_465("ALA", "A", 2),
            _remark_465("GLY", "A", 2),
            _atom(1),
        )
    ).system
    _assert_error(ambiguous, "ambiguous_missing_residue_identity")

    residue_system = parse_pdb(
        _pdb(
            _remark_465("ALA", "A", 2),
            _remark_465("GLY", "A", 3),
            _atom(1),
        )
    ).system
    raw_residue_claims = residue_system.metadata["pdb"]["source_reported_missingness"][
        "missing_residue_claims"
    ]

    def reordered_residue_claim(raw_claim, ordinal: int):
        raw_payload = raw_claim["raw_payload"]
        return SourceReportedMissingResidueClaim(
            source_ordinal=ordinal,
            source_category=raw_claim["source_category"],
            source_model_id=raw_claim["source_model_id"],
            source_chain_id=raw_claim["source_chain_id"],
            source_residue_id=raw_claim["source_residue_id"],
            source_residue_name=raw_claim["source_residue_name"],
            source_insertion_code=raw_claim["source_insertion_code"],
            raw_payload={
                "line_number": raw_payload["line_number"],
                "raw_line": raw_payload["raw_line"],
                "model_field": raw_payload["model_field"],
                "target_model_scope": {
                    "kind": "explicit_model_ids",
                    "model_ids": [1],
                    "count": 1,
                },
            },
        )

    residue_report = build_source_reported_missingness_report(
        source_format="pdb",
        source_sha256=residue_system.provenance.source_sha256,
        canonical_topology_sha256=canonical_topology_sha256(residue_system),
        coordinate_scope="deposited_coordinates",
        altloc_status="not_present",
        requested_altloc_id="",
        assembly_status="not_supported_for_pdb",
        requested_assembly_id="",
        missing_residue_claims=(
            reordered_residue_claim(raw_residue_claims[1], 1),
            reordered_residue_claim(raw_residue_claims[0], 2),
        ),
    )
    _assert_error(
        _replace_missingness_report(residue_system, residue_report),
        "invalid_missingness_claim_order",
    )

    atom_system = parse_pdb(
        _pdb(_remark_470("GLY", "A", 1, ("CB", "O")), _atom(1))
    ).system
    raw_atom_claims = atom_system.metadata["pdb"]["source_reported_missingness"][
        "missing_atom_claims"
    ]

    def reordered_atom_claim(raw_claim, ordinal: int):
        raw_payload = raw_claim["raw_payload"]
        return SourceReportedMissingAtomClaim(
            source_ordinal=ordinal,
            source_category=raw_claim["source_category"],
            source_model_id=raw_claim["source_model_id"],
            source_chain_id=raw_claim["source_chain_id"],
            source_residue_id=raw_claim["source_residue_id"],
            source_residue_name=raw_claim["source_residue_name"],
            source_insertion_code=raw_claim["source_insertion_code"],
            source_atom_name=raw_claim["source_atom_name"],
            source_altloc_id=raw_claim["source_altloc_id"],
            raw_payload={
                "line_number": raw_payload["line_number"],
                "raw_line": raw_payload["raw_line"],
                "atom_position_in_row": raw_payload["atom_position_in_row"],
                "model_field": raw_payload["model_field"],
                "target_model_scope": {
                    "kind": "explicit_model_ids",
                    "model_ids": [1],
                    "count": 1,
                },
            },
        )

    atom_report = build_source_reported_missingness_report(
        source_format="pdb",
        source_sha256=atom_system.provenance.source_sha256,
        canonical_topology_sha256=canonical_topology_sha256(atom_system),
        coordinate_scope="deposited_coordinates",
        altloc_status="not_present",
        requested_altloc_id="",
        assembly_status="not_supported_for_pdb",
        requested_assembly_id="",
        missing_atom_claims=(
            reordered_atom_claim(raw_atom_claims[1], 1),
            reordered_atom_claim(raw_atom_claims[0], 2),
        ),
    )
    _assert_error(
        _replace_missingness_report(atom_system, atom_report),
        "invalid_missingness_claim_order",
    )


def test_missingness_line_cap_and_same_count_cross_wires_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    system = parse_pdb(_pdb(_remark_470("GLY", "A", 1, ("CB",)), _atom(1))).system
    with monkeypatch.context() as scoped:
        scoped.setattr(writer_module, "_MAX_MISSINGNESS_REMARK_LINES", 2)
        _assert_error(system, "missingness_line_limit_exceeded")

    claim_two = round_trip_pdb_source(
        _pdb(_remark_465("ALA", "A", 2), _atom(1)),
        source_id="claim-two",
    )
    claim_three = round_trip_pdb_source(
        _pdb(_remark_465("ALA", "A", 3), _atom(1)),
        source_id="claim-three",
    )
    assert claim_two.write_result.receipt.missing_residue_claim_count == (
        claim_three.write_result.receipt.missing_residue_claim_count
    )
    assert claim_two.write_result.receipt.input_missingness_semantic_sha256 != (
        claim_three.write_result.receipt.input_missingness_semantic_sha256
    )
    with pytest.raises(ValueError, match="cross-consistent"):
        PdbRoundTripResult(
            source_ingest=claim_three.source_ingest,
            write_result=claim_two.write_result,
            reparsed_ingest=claim_two.reparsed_ingest,
            report=claim_two.report,
            _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
        )


def test_missingness_receipt_rejects_bool_and_inconsistent_count_pairs() -> None:
    result = round_trip_pdb_source(_pdb(_remark_465("ALA", "A", 2), _atom(1)))
    receipt = result.write_result.receipt
    kwargs = {
        "input_system_schema_id": receipt.input_system_schema_id,
        "parent_source_sha256": receipt.parent_source_sha256,
        "input_snapshot_sha256": receipt.input_snapshot_sha256,
        "input_topology_sha256": receipt.input_topology_sha256,
        "input_representable_state_sha256": receipt.input_representable_state_sha256,
        "input_parser_observation_sha256": receipt.input_parser_observation_sha256,
        "output_source_sha256": receipt.output_source_sha256,
        "output_byte_count": receipt.output_byte_count,
        "atom_count": receipt.atom_count,
        "bond_count": receipt.bond_count,
        "model_count": receipt.model_count,
        "ter_count": receipt.ter_count,
        "cell_present": receipt.cell_present,
        "cryst1_count": receipt.cryst1_count,
        "input_missingness_report_sha256": receipt.input_missingness_report_sha256,
        "input_missingness_semantic_sha256": receipt.input_missingness_semantic_sha256,
        "input_missingness_remark_line_count": (
            receipt.input_missingness_remark_line_count
        ),
        "emitted_missingness_remark_line_count": (
            receipt.emitted_missingness_remark_line_count
        ),
        "missing_residue_claim_count": receipt.missing_residue_claim_count,
        "missing_atom_claim_count": receipt.missing_atom_claim_count,
        "_factory_token": writer_module._ARTIFACT_FACTORY_TOKEN,
    }
    with pytest.raises(TypeError, match="exact boolean"):
        PdbWriteReceipt(**kwargs, missingness_evidence_present=1)
    with pytest.raises(TypeError, match="nonnegative integer"):
        PdbWriteReceipt(
            **{
                **kwargs,
                "missingness_evidence_present": True,
                "missing_residue_claim_count": 1.0,
            }
        )
    with pytest.raises(ValueError, match="exactly one coordinate model"):
        PdbWriteReceipt(
            **{
                **kwargs,
                "missingness_evidence_present": True,
                "model_count": 2,
            }
        )
    with pytest.raises(ValueError, match="canonical section shape"):
        PdbWriteReceipt(
            **{
                **kwargs,
                "missingness_evidence_present": True,
                "emitted_missingness_remark_line_count": 4,
            }
        )

    report = result.report
    report_kwargs = {
        "input_source_sha256": report.input_source_sha256,
        "input_snapshot_sha256": report.input_snapshot_sha256,
        "input_topology_sha256": report.input_topology_sha256,
        "input_representable_state_sha256": (report.input_representable_state_sha256),
        "input_parser_observation_sha256": report.input_parser_observation_sha256,
        "writer_receipt_sha256": report.writer_receipt_sha256,
        "emitted_source_sha256": report.emitted_source_sha256,
        "reparsed_snapshot_sha256": report.reparsed_snapshot_sha256,
        "reparsed_topology_sha256": report.reparsed_topology_sha256,
        "reparsed_representable_state_sha256": (
            report.reparsed_representable_state_sha256
        ),
        "reparsed_parser_observation_sha256": (
            report.reparsed_parser_observation_sha256
        ),
        "reemitted_source_sha256": report.reemitted_source_sha256,
        "input_missingness_report_sha256": (report.input_missingness_report_sha256),
        "reparsed_missingness_report_sha256": (
            report.reparsed_missingness_report_sha256
        ),
        "input_missingness_semantic_sha256": (report.input_missingness_semantic_sha256),
        "reparsed_missingness_semantic_sha256": (
            report.reparsed_missingness_semantic_sha256
        ),
        "missingness_evidence_present": True,
        "missing_atom_claim_count": 0,
        "_factory_token": writer_module._ARTIFACT_FACTORY_TOKEN,
    }
    with pytest.raises(ValueError, match="exceed fixed limits"):
        PdbRoundTripReport(
            **report_kwargs,
            missing_residue_claim_count=(writer_module.MAX_MISSING_RESIDUE_CLAIMS + 1),
        )


def test_composite_parser_owned_fields_and_ter_round_trip() -> None:
    source = _pdb(
        _atom(
            7,
            record="HETATM",
            atom_name_field="ZN  ",
            residue="ZN",
            chain="Z",
            residue_number=-2,
            insertion_code="A",
            x=-0.0,
            y=1.25,
            z=-3.5,
            occupancy=0.25,
            b_factor=12.34,
            segment_id="METL",
            element="Zn",
            charge="2+",
        ),
        _ter(8, residue="ZN", chain="Z", residue_number=-2, insertion_code="A"),
        _atom(
            20,
            atom_name_field=" N  ",
            residue="GLY",
            chain="A",
            residue_number=3,
            segment_id="SEG1",
            element="N",
            charge="",
        ),
        _ter(21, residue="GLY", chain="A", residue_number=3),
    )
    result = round_trip_pdb_source(source, source_id="composite")
    before = result.source_ingest.system
    after = result.reparsed_ingest.system
    lines = result.write_result.payload.decode("ascii").splitlines()

    assert [line[0:6].strip() for line in lines] == [
        "HETATM",
        "TER",
        "ATOM",
        "TER",
        "END",
    ]
    assert lines[0][12:16] == "ZN  "
    assert lines[0][16] == " "
    assert lines[0][26] == "A"
    assert lines[0][72:76] == "METL"
    assert lines[0][78:80] == "2+"
    assert lines[2][12:16] == " N  "
    assert lines[2][72:76] == "SEG1"
    assert lines[2][78:80] == "  "
    assert before.atoms[0].formal_charge_known is True
    assert before.atoms[1].formal_charge_known is False
    assert before.residues[0].hetero is True
    assert before.residues[1].hetero is False
    assert before.chains[0].chain_id == "Z"
    assert before.chains[1].chain_id == "A"
    assert pdb_representable_state_sha256(before) == (
        pdb_representable_state_sha256(after)
    )
    assert serialize_pdb(after) == result.write_result.payload


def test_multimodel_ids_coordinates_and_ter_are_preserved() -> None:
    source = _pdb(
        _model(2),
        _atom(1, x=0.0),
        _ter(2),
        "ENDMDL",
        _model(7),
        _atom(1, x=0.125),
        _ter(2),
        "ENDMDL",
    )
    result = round_trip_pdb_source(source, source_id="models")
    payload = result.write_result.payload.decode("ascii")

    assert result.source_ingest.system.provenance.metadata["model_ids"] == [2, 7]
    assert result.reparsed_ingest.system.provenance.metadata["model_ids"] == [2, 7]
    assert payload.count("MODEL ") == 2
    assert payload.count("ENDMDL") == 2
    assert payload.count("TER   ") == 2
    assert serialize_pdb(result.reparsed_ingest.system) == (result.write_result.payload)
    assert torch.equal(
        result.source_ingest.system.coordinates.view(torch.int64),
        result.reparsed_ingest.system.coordinates.view(torch.int64),
    )


def test_single_nondefault_model_blank_numeric_fields_and_negative_charge() -> None:
    source = _pdb(
        _model(5),
        _atom(
            9,
            record="HETATM",
            atom_name_field="CL  ",
            residue="CL",
            chain="",
            residue_number=-1,
            occupancy=None,
            b_factor=None,
            element="Cl",
            charge="9-",
        ),
        "ENDMDL",
    )
    result = round_trip_pdb_source(source, source_id="single-model-five")
    lines = result.write_result.payload.decode("ascii").splitlines()

    assert [line[0:6].strip() for line in lines] == [
        "MODEL",
        "HETATM",
        "ENDMDL",
        "END",
    ]
    assert lines[1][21] == " "
    assert lines[1][54:66] == " " * 12
    assert lines[1][78:80] == "9-"
    assert result.reparsed_ingest.system.provenance.metadata["model_ids"] == [5]
    assert result.reparsed_ingest.system.atoms[0].formal_charge == -9
    assert result.reparsed_ingest.system.atoms[0].formal_charge_known is True


def test_duplicate_atom_site_identity_fails_before_emission() -> None:
    system = parse_pdb(
        _pdb(
            _atom(1, atom_name_field=" CA "),
            _atom(2, atom_name_field=" N  ", element="N"),
        )
    ).system
    second_metadata = dict(system.atoms[1].metadata)
    second_metadata["pdb_atom_name_field"] = " CA "
    duplicate = replace(
        system,
        atoms=(
            system.atoms[0],
            replace(system.atoms[1], name="CA", metadata=second_metadata),
        ),
    )

    _assert_error(duplicate, "duplicate_atom_identity")


def test_atom_first_occurrence_must_reconstruct_chain_and_residue_order() -> None:
    chain_system = parse_pdb(
        _pdb(
            _atom(1, chain="A"),
            _atom(2, chain="B"),
        )
    ).system
    reordered_chain = replace(
        chain_system,
        atoms=(
            replace(chain_system.atoms[1], index=0),
            replace(chain_system.atoms[0], index=1),
        ),
        residues=(
            replace(chain_system.residues[0], atom_indices=(1,)),
            replace(chain_system.residues[1], atom_indices=(0,)),
        ),
        coordinates=chain_system.coordinates[:, (1, 0), :].clone(),
    )
    _assert_error(reordered_chain, "unsupported_chain_topology")

    residue_system = _base_system()
    reordered_residue = replace(
        residue_system,
        atoms=(
            replace(residue_system.atoms[1], index=0),
            replace(residue_system.atoms[0], index=1),
        ),
        residues=(
            replace(residue_system.residues[0], atom_indices=(1,)),
            replace(residue_system.residues[1], atom_indices=(0,)),
        ),
        coordinates=residue_system.coordinates[:, (1, 0), :].clone(),
    )
    _assert_error(reordered_residue, "unsupported_residue_topology")


def test_interleaved_chains_and_reappearing_residue_without_ter_round_trip() -> None:
    source = _pdb(
        _atom(1, atom_name_field=" N  ", chain="A", element="N"),
        _atom(2, atom_name_field=" N  ", chain="B", element="N"),
        _atom(3, chain="A", residue_number=2),
        _atom(4, chain="B", residue_number=2),
        _atom(5, atom_name_field=" C  ", chain="A", element="C"),
    )
    result = round_trip_pdb_source(source, source_id="interleaved-no-ter")
    before = result.source_ingest.system
    after = result.reparsed_ingest.system

    assert [chain.chain_id for chain in before.chains] == ["A", "B"]
    assert [residue.sequence_number for residue in before.residues] == [1, 2, 1, 2]
    assert [atom.residue_index for atom in before.atoms] == [0, 2, 1, 3, 0]
    assert canonical_topology_sha256(before) == canonical_topology_sha256(after)
    assert pdb_representable_state_sha256(before) == (
        pdb_representable_state_sha256(after)
    )
    assert serialize_pdb(after) == result.write_result.payload


def test_source_independent_projection_and_second_emission_are_stable() -> None:
    canonical_source = _pdb(_atom(1))
    source = canonical_source.replace(b"\n", b"\r\n") + b"\r\n"
    result = round_trip_pdb_source(source, source_id="noncanonical-layout")
    before = result.source_ingest.system
    after = result.reparsed_ingest.system

    assert result.write_result.payload != source
    assert pdb_representable_state_sha256(before) == (
        pdb_representable_state_sha256(after)
    )
    assert serialize_pdb(after) == result.write_result.payload
    assert result.report.input_source_sha256 != result.report.emitted_source_sha256
    assert result.report.input_snapshot_sha256 != result.report.reparsed_snapshot_sha256
    assert result.report.input_representable_state_sha256 == (
        result.report.reparsed_representable_state_sha256
    )
    assert result.report.to_dict()["full_canonical_snapshot_equality_claimed"] is False
    assert (
        result.report.to_dict()["dynamic_source_provenance_equality_claimed"] is False
    )


def test_implicit_and_explicit_single_model_one_share_projection_and_output() -> None:
    atom = _atom(1, x=1.25, occupancy=0.5, b_factor=7.25)
    implicit_source = _pdb(atom)
    explicit_source = _pdb(_model(1), atom, "ENDMDL")
    implicit = round_trip_pdb_source(implicit_source, source_id="implicit")
    explicit = round_trip_pdb_source(explicit_source, source_id="explicit")

    assert implicit_source != explicit_source
    assert pdb_representable_state_sha256(implicit.source_ingest.system) == (
        pdb_representable_state_sha256(explicit.source_ingest.system)
    )
    assert implicit.write_result.payload == explicit.write_result.payload
    assert b"MODEL " not in implicit.write_result.payload
    assert b"ENDMDL" not in implicit.write_result.payload
    assert (
        implicit.report.to_dict()["full_canonical_snapshot_equality_claimed"] is False
    )
    assert (
        explicit.report.to_dict()["dynamic_source_provenance_equality_claimed"] is False
    )


def test_atom_name_alignment_signed_zero_and_numeric_state_round_trip_exactly() -> None:
    source = _pdb(
        _atom(
            1,
            atom_name_field=" CA ",
            x=-0.0,
            y=9999.999,
            z=-999.999,
            occupancy=-0.0,
            b_factor=-0.0,
        ),
        _atom(
            2,
            atom_name_field="CA  ",
            residue_number=2,
            x=1.125,
            y=-2.25,
            z=3.5,
            occupancy=0.75,
            b_factor=99.99,
        ),
    )
    result = round_trip_pdb_source(source)
    before = result.source_ingest.system
    after = result.reparsed_ingest.system
    lines = result.write_result.payload.decode("ascii").splitlines()

    assert lines[0][12:16] == " CA "
    assert lines[1][12:16] == "CA  "
    assert torch.equal(
        before.coordinates.view(torch.int64), after.coordinates.view(torch.int64)
    )
    assert int(after.coordinates.view(torch.int64)[0, 0, 0].item()) == -(1 << 63)
    for old, new in zip(before.atoms, after.atoms, strict=True):
        assert _binary64(old.occupancy) == _binary64(new.occupancy)
        assert _binary64(old.b_factor) == _binary64(new.b_factor)
    assert _binary64(after.atoms[0].occupancy) == struct.pack(">Q", 1 << 63)
    assert _binary64(after.atoms[0].b_factor) == struct.pack(">Q", 1 << 63)


def test_coordinate_and_tensor_states_outside_fixed_f8_3_scope_fail_closed() -> None:
    system = _base_system()

    _assert_error(_replace_coordinate(system, 0.0001), "coordinate_rounding_required")
    _assert_error(_replace_coordinate(system, 10_000.0), "coordinate_field_overflow")
    _assert_error(
        replace(system, coordinates=system.coordinates.to(dtype=torch.float32)),
        "unsupported_coordinate_dtype",
    )
    _assert_error(
        replace(system, coordinates=system.coordinates.clone().requires_grad_(True)),
        "coordinate_gradient_state_unsupported",
    )


@pytest.mark.parametrize(
    ("changes", "code"),
    [
        ({"occupancy": 0.125}, "occupancy_rounding_required"),
        ({"b_factor": 20.005}, "b_factor_rounding_required"),
        ({"b_factor": 10_000.0}, "b_factor_field_overflow"),
        ({"occupancy": -0.01}, "canonical_validation_failed"),
        ({"occupancy": 1.01}, "canonical_validation_failed"),
        ({"occupancy": float("inf")}, "canonical_validation_failed"),
        ({"b_factor": float("nan")}, "canonical_validation_failed"),
    ],
)
def test_occupancy_and_b_factor_rounding_overflow_nonfinite_and_range_fail_closed(
    changes: dict[str, float],
    code: str,
) -> None:
    _assert_error(_replace_atom(_base_system(), **changes), code)


def test_parser_owned_orthorhombic_p1_cryst1_round_trips_bitwise() -> None:
    source = _pdb(_cryst1(), _atom(1))
    result = round_trip_pdb_source(source, source_id="orthorhombic-p1")
    before = result.source_ingest.system
    after = result.reparsed_ingest.system
    lines = result.write_result.payload.decode("ascii").splitlines()

    assert lines[0] == _cryst1().ljust(80)
    assert [line[0:6].strip() for line in lines] == ["CRYST1", "ATOM", "END"]
    assert before.cell is not None
    assert after.cell is not None
    assert before.cell.periodic == (False, False, False)
    assert after.cell.periodic == (False, False, False)
    assert torch.equal(
        before.cell.vectors.view(torch.int64),
        after.cell.vectors.view(torch.int64),
    )
    assert before.metadata["pdb"]["cryst1"] == after.metadata["pdb"]["cryst1"]
    assert result.source_ingest.coverage.cell_present is True
    assert result.source_ingest.coverage.blockers[-1] == (
        "crystallographic_cell_not_simulation_box"
    )
    assert result.write_result.receipt.cell_present is True
    assert result.write_result.receipt.cryst1_count == 1
    assert serialize_pdb(after) == result.write_result.payload
    assert result.report.to_dict()["cryst1_cell_binary64_projection_equal"] is True
    assert result.report.to_dict()["simulation_ready"] is False


def test_triclinic_non_p1_cryst1_and_blank_z_or_space_group_round_trip() -> None:
    triclinic_source = _pdb(
        _cryst1(
            a=33.125,
            b=34.25,
            c=35.5,
            alpha=80.0,
            beta=75.0,
            gamma=70.0,
            space_group="P 21 21 21",
            z=4,
        ),
        _atom(1),
    )
    triclinic = round_trip_pdb_source(triclinic_source)
    metadata = triclinic.source_ingest.system.metadata["pdb"]["cryst1"]

    assert metadata["lengths_angstrom"] == (33.125, 34.25, 35.5)
    assert metadata["angles_degrees"] == (80.0, 75.0, 70.0)
    assert metadata["space_group"] == "P 21 21 21"
    assert metadata["z"] == 4
    assert triclinic.source_ingest.coverage.blockers[-2:] == (
        "crystallographic_cell_not_simulation_box",
        "crystallographic_symmetry_not_expanded",
    )
    assert serialize_pdb(triclinic.reparsed_ingest.system) == (
        triclinic.write_result.payload
    )

    blank_source = _pdb(
        _cryst1(space_group="", z=None),
        _atom(1),
    )
    blank = round_trip_pdb_source(blank_source)
    blank_metadata = blank.source_ingest.system.metadata["pdb"]["cryst1"]
    blank_line = blank.write_result.payload.decode("ascii").splitlines()[0]

    assert blank_metadata["space_group"] == ""
    assert blank_metadata["z"] is None
    assert blank_line[55:66] == " " * 11
    assert blank_line[66:70] == " " * 4
    assert blank.source_ingest.coverage.blockers[-2:] == (
        "crystallographic_cell_not_simulation_box",
        "crystallographic_symmetry_not_expanded",
    )


def test_cryst1_multimodel_ter_layout_and_raw_decimal_normalization() -> None:
    source = _pdb(
        _cryst1(z=4),
        _model(2),
        _atom(1, x=0.0),
        _ter(2),
        "ENDMDL",
        _model(7),
        _atom(1, x=0.125),
        _ter(2),
        "ENDMDL",
    )
    result = round_trip_pdb_source(source)
    lines = result.write_result.payload.decode("ascii").splitlines()

    assert [line[0:6].strip() for line in lines] == [
        "CRYST1",
        "MODEL",
        "ATOM",
        "TER",
        "ENDMDL",
        "MODEL",
        "ATOM",
        "TER",
        "ENDMDL",
        "END",
    ]
    assert result.write_result.receipt.model_count == 2
    assert result.write_result.receipt.ter_count == 2
    assert result.write_result.receipt.cryst1_count == 1

    raw_line = _raw_cryst1(
        lengths=("  +20.000", "   21.000", "   22.000"),
        angles=("+090.00", "  90.00", "  90.00"),
    )
    normalized = round_trip_pdb_source(_pdb(raw_line, _atom(1)))
    normalized_line = normalized.write_result.payload.decode("ascii").splitlines()[0]

    assert raw_line != _cryst1()
    assert normalized_line == _cryst1().ljust(80)
    assert serialize_pdb(normalized.reparsed_ingest.system) == (
        normalized.write_result.payload
    )


@pytest.mark.parametrize(
    ("line", "code"),
    [
        (
            _raw_cryst1(
                lengths=("  20.0001", "   21.000", "   22.000"),
                angles=("  90.00", "  90.00", "  90.00"),
            ),
            "cryst1_length_rounding_required",
        ),
        (
            _raw_cryst1(
                lengths=("   20.000", "   21.000", "   22.000"),
                angles=(" 90.001", "  90.00", "  90.00"),
            ),
            "cryst1_angle_rounding_required",
        ),
        (
            _raw_cryst1(
                lengths=("999999999", "   21.000", "   22.000"),
                angles=("  90.00", "  90.00", "  90.00"),
            ),
            "cryst1_length_field_overflow",
        ),
    ],
)
def test_cryst1_fixed_width_rounding_and_overflow_fail_closed(
    line: str,
    code: str,
) -> None:
    _assert_error(parse_pdb(_pdb(line, _atom(1))).system, code)


class _UnitCellSubclass(UnitCell):
    pass


def test_cryst1_cell_presence_vector_and_runtime_state_fail_closed() -> None:
    system = _base_system()
    _assert_error(
        replace(
            system,
            cell=UnitCell.orthorhombic(
                (10.0, 10.0, 10.0),
                dtype=torch.float64,
                periodic=(False, False, False),
            ),
        ),
        "cryst1_state_mismatch",
    )
    cell_system = parse_pdb(_pdb(_cryst1(), _atom(1))).system
    assert cell_system.cell is not None
    _assert_error(
        replace(cell_system, cell=None),
        "cryst1_state_mismatch",
    )
    _assert_error(
        _replace_pdb_metadata(cell_system, "cryst1", None),
        "cryst1_state_mismatch",
    )

    mismatched_vectors = cell_system.cell.vectors.clone()
    mismatched_vectors[0, 0] += 0.001
    _assert_error(
        replace(
            cell_system,
            cell=UnitCell(
                vectors=mismatched_vectors,
                periodic=(False, False, False),
            ),
        ),
        "cryst1_cell_mismatch",
    )
    _assert_error(
        replace(
            cell_system,
            cell=UnitCell(
                vectors=cell_system.cell.vectors.to(dtype=torch.float32),
                periodic=(False, False, False),
            ),
        ),
        "unsupported_unit_cell_dtype",
    )
    _assert_error(
        replace(
            cell_system,
            cell=UnitCell(
                vectors=cell_system.cell.vectors.clone().requires_grad_(True),
                periodic=(False, False, False),
            ),
        ),
        "unit_cell_gradient_state_unsupported",
    )
    _assert_error(
        replace(
            cell_system,
            cell=UnitCell(
                vectors=cell_system.cell.vectors.clone(),
                periodic=(True, False, False),
            ),
        ),
        "unsupported_unit_cell_periodic_state",
    )
    _assert_error(
        replace(
            cell_system,
            cell=_UnitCellSubclass(
                vectors=cell_system.cell.vectors.clone(),
                periodic=(False, False, False),
            ),
        ),
        "unsupported_unit_cell_type",
    )

    malformed_cell = UnitCell(
        vectors=cell_system.cell.vectors.clone(),
        periodic=(False, False, False),
    )
    object.__setattr__(
        malformed_cell, "vectors", torch.zeros((2, 3), dtype=torch.float64)
    )
    _assert_error(
        replace(cell_system, cell=malformed_cell),
        "unsupported_unit_cell_shape",
    )
    malformed_cell = UnitCell(
        vectors=cell_system.cell.vectors.clone(),
        periodic=(False, False, False),
    )
    object.__setattr__(
        malformed_cell,
        "vectors",
        torch.sparse_coo_tensor(
            torch.empty((2, 0), dtype=torch.int64),
            torch.empty((0,), dtype=torch.float64),
            (3, 3),
        ),
    )
    _assert_error(
        replace(cell_system, cell=malformed_cell),
        "unsupported_unit_cell_layout",
    )
    malformed_cell = UnitCell(
        vectors=cell_system.cell.vectors.clone(),
        periodic=(False, False, False),
    )
    object.__setattr__(
        malformed_cell,
        "vectors",
        torch.empty((3, 3), dtype=torch.float64, device="meta"),
    )
    _assert_error(
        replace(cell_system, cell=malformed_cell),
        "unsupported_unit_cell_device",
    )

    dummy_vectors = cell_system.cell.vectors.clone()
    dummy_vectors[0] /= 20.0
    dummy_vectors[1] /= 21.0
    dummy_vectors[2] /= 22.0
    dummy = _replace_cryst1_metadata(
        cell_system,
        "lengths_angstrom",
        [1.0, 1.0, 1.0],
    )
    dummy = replace(
        dummy,
        cell=UnitCell(
            vectors=dummy_vectors,
            periodic=(False, False, False),
        ),
    )
    _assert_error(dummy, "dummy_cryst1")


def test_cryst1_snapshot_detaches_cell_vectors_before_emission(monkeypatch) -> None:
    system = parse_pdb(_pdb(_cryst1(), _atom(1))).system
    assert system.cell is not None
    caller_vectors = system.cell.vectors
    original_emit = writer_module._emit_payload

    def mutate_caller_then_emit(state):
        caller_vectors[0, 0] = 999.0
        assert state.system.cell is not None
        assert float(state.system.cell.vectors[0, 0].item()) == 20.0
        return original_emit(state)

    monkeypatch.setattr(writer_module, "_emit_payload", mutate_caller_then_emit)
    result = write_pdb(system)

    assert result.payload.splitlines()[0] == _cryst1().ljust(80).encode("ascii")


@pytest.mark.parametrize("z", [True, False, 0, -1, 10_000])
def test_cryst1_z_must_be_none_or_exact_positive_i4(z: object) -> None:
    system = parse_pdb(_pdb(_cryst1(), _atom(1))).system
    _assert_error(_replace_cryst1_metadata(system, "z", z), "unsupported_cryst1_z")


@pytest.mark.parametrize("space_group", ["P\N{SNOWMAN}1", "P" * 12, " P 1", "P 1 "])
def test_cryst1_space_group_must_be_bounded_printable_ascii(
    space_group: str,
) -> None:
    system = parse_pdb(_pdb(_cryst1(), _atom(1))).system
    _assert_error(
        _replace_cryst1_metadata(system, "space_group", space_group),
        "unsupported_cryst1_space_group",
    )


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("lengths_angstrom", [20, 21.0, 22.0]),
        ("lengths_angstrom", [20.0, True, 22.0]),
        ("lengths_angstrom", [20.0, 21.0]),
        ("lengths_angstrom", [0.0, 21.0, 22.0]),
        ("angles_degrees", [90.0, 90, 90.0]),
        ("angles_degrees", [90.0, False, 90.0]),
        ("angles_degrees", [90.0, 90.0, 90.0, 90.0]),
        ("angles_degrees", [0.0, 90.0, 90.0]),
    ],
)
def test_cryst1_numeric_metadata_requires_exact_float_triplets(
    field_name: str,
    value: list[object],
) -> None:
    system = parse_pdb(_pdb(_cryst1(), _atom(1))).system
    _assert_error(
        _replace_cryst1_metadata(system, field_name, value),
        "unsupported_cryst1_metadata",
    )


def test_cryst1_unknown_metadata_and_coverage_tamper_fail_closed() -> None:
    system = parse_pdb(_pdb(_cryst1(), _atom(1))).system
    cryst1 = dict(system.metadata["pdb"]["cryst1"])
    cryst1["unknown"] = "forged"
    _assert_error(
        _replace_pdb_metadata(system, "cryst1", cryst1),
        "unsupported_cryst1_metadata",
    )

    coverage = dict(system.provenance.metadata["coverage"])
    coverage["cell_present"] = False
    _assert_error(
        _replace_provenance_metadata(system, "coverage", coverage),
        "stale_pdb_coverage",
    )
    coverage = dict(system.provenance.metadata["coverage"])
    coverage["blockers"] = [
        blocker
        for blocker in coverage["blockers"]
        if blocker != "crystallographic_cell_not_simulation_box"
    ]
    _assert_error(
        _replace_provenance_metadata(system, "coverage", coverage),
        "stale_pdb_coverage",
    )


def test_altloc_header_only_missingness_and_bonds_remain_rejected() -> None:
    system = _base_system()

    altloc = parse_pdb(
        _pdb(
            _atom(1, altloc="A", x=1.0),
            _atom(2, altloc="B", x=2.0),
        ),
        altloc_id="A",
    ).system
    _assert_error(altloc, "unsupported_altloc_selection")

    header_only = parse_pdb(
        _pdb(
            _remark_header(465),
            _remark_header(465, "MISSING RESIDUES"),
            _atom(1),
        )
    ).system
    missing_claim = parse_pdb(_pdb(_remark_465("ALA", "A", 2), _atom(1))).system
    _assert_error(header_only, "header_only_missingness_evidence")
    assert write_pdb(missing_claim).receipt.missing_residue_claim_count == 1

    bond = Bond(index=0, atom_i=0, atom_j=1, source="pdb")
    _assert_error(replace(system, bonds=(bond,)), "unsupported_bonds")


@pytest.mark.parametrize(
    ("mutator", "code"),
    [
        (
            lambda system: _replace_atom(
                system,
                formal_charge_known=True,
                metadata={
                    **dict(system.atoms[0].metadata),
                    "formal_charge_known": True,
                    "formal_charge_source": "pdb_columns_79_80",
                    "formal_charge_interpretation": "explicit",
                },
            ),
            "known_neutral_charge",
        ),
        (
            lambda system: _replace_atom(system, formal_charge=1),
            "unknown_nonzero_formal_charge",
        ),
        (
            lambda system: _replace_atom(
                system,
                formal_charge=10,
                formal_charge_known=True,
                metadata={
                    **dict(system.atoms[0].metadata),
                    "formal_charge_known": True,
                    "formal_charge_source": "pdb_columns_79_80",
                    "formal_charge_interpretation": "explicit",
                },
            ),
            "unsupported_formal_charge",
        ),
        (
            lambda system: _replace_atom(system, partial_charge_e=0.1),
            "unsupported_partial_charge",
        ),
        (
            lambda system: _replace_atom(system, mass_da=12.0),
            "unsupported_atom_mass",
        ),
        (
            lambda system: _replace_atom(system, isotope_mass_number=13),
            "unsupported_isotope",
        ),
        (
            lambda system: _replace_atom(system, atom_map=1),
            "unsupported_atom_map",
        ),
        (
            lambda system: _replace_atom(system, aromatic=True),
            "unsupported_aromatic_atom",
        ),
        (
            lambda system: _replace_atom(system, stereo="R"),
            "unsupported_atom_stereo",
        ),
    ],
)
def test_unrepresentable_atom_fields_are_never_silently_discarded(
    mutator,
    code: str,
) -> None:
    _assert_error(mutator(_base_system()), code)


@pytest.mark.parametrize(
    ("mutator", "code"),
    [
        (
            lambda system: _replace_atom(
                system,
                metadata={**dict(system.atoms[0].metadata), "extra": True},
            ),
            "unsupported_atom_metadata",
        ),
        (
            lambda system: replace(
                system,
                residues=(
                    replace(
                        system.residues[0],
                        metadata={
                            **dict(system.residues[0].metadata),
                            "extra": True,
                        },
                    ),
                    *system.residues[1:],
                ),
            ),
            "unsupported_residue_metadata",
        ),
        (
            lambda system: replace(
                system,
                chains=(
                    replace(
                        system.chains[0],
                        metadata={**dict(system.chains[0].metadata), "extra": True},
                    ),
                ),
            ),
            "unsupported_chain_metadata",
        ),
        (
            lambda system: replace(
                system,
                metadata={**dict(system.metadata), "extra": True},
            ),
            "unsupported_system_metadata",
        ),
    ],
)
def test_parser_owned_metadata_shape_drift_fails_closed(mutator, code: str) -> None:
    _assert_error(mutator(_base_system()), code)


def test_coverage_topology_missingness_and_observation_digest_drift_fails_closed() -> (
    None
):
    system = _base_system()
    _assert_error(
        _replace_provenance_metadata(system, "parser_observation_sha256", "0" * 64),
        "stale_parser_observation_digest",
    )
    _assert_error(
        _replace_provenance_metadata(system, "canonical_topology_sha256", "0" * 64),
        "stale_canonical_topology_digest",
    )
    _assert_error(
        _replace_provenance_metadata(
            system,
            "source_missingness_evidence_sha256",
            "0" * 64,
        ),
        "stale_missingness_digest",
    )
    coverage = dict(system.provenance.metadata["coverage"])
    coverage["atom_count"] += 1
    _assert_error(
        _replace_provenance_metadata(system, "coverage", coverage),
        "stale_pdb_coverage",
    )


@pytest.mark.parametrize(
    ("mutator", "code"),
    [
        (
            lambda provenance: replace(provenance, source_format="mmcif"),
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
        (
            lambda provenance: replace(provenance, parent_sha256=("0" * 64,)),
            "unsupported_parent_provenance",
        ),
        (
            lambda provenance: replace(provenance, preparation_ready=True),
            "unsupported_authority_state",
        ),
        (
            lambda provenance: replace(provenance, claim_safe=True),
            "unsupported_authority_state",
        ),
    ],
)
def test_provenance_pedigree_and_authority_drift_fails_closed(
    mutator,
    code: str,
) -> None:
    system = _base_system()
    _assert_error(replace(system, provenance=mutator(system.provenance)), code)


def test_model_serial_ter_and_output_resource_limits_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    system = _base_system()
    model_metadata = dict(system.provenance.metadata)
    model_metadata["model_ids"] = [10_000]
    _assert_error(
        replace(system, provenance=replace(system.provenance, metadata=model_metadata)),
        "unsupported_model_id",
    )
    _assert_error(_replace_atom(system, serial=100_000), "unsupported_atom_serial")

    with_ter = parse_pdb(_pdb(_atom(1), _ter(2))).system
    pdb_metadata = dict(with_ter.metadata["pdb"])
    entries = [dict(entry) for entry in pdb_metadata["ter_records_by_model"]]
    records = [dict(record) for record in entries[0]["records"]]
    records[0]["after_atom_serial"] = 999
    entries[0]["records"] = records
    pdb_metadata["ter_records_by_model"] = entries
    _assert_error(
        replace(with_ter, metadata={"pdb": pdb_metadata}),
        "unsupported_ter_metadata",
    )

    pdb_metadata = dict(with_ter.metadata["pdb"])
    entries = [dict(entry) for entry in pdb_metadata["ter_records_by_model"]]
    records = [dict(record) for record in entries[0]["records"]]
    records[0]["serial"] = 100_000
    entries[0]["records"] = records
    pdb_metadata["ter_records_by_model"] = entries
    _assert_error(
        replace(with_ter, metadata={"pdb": pdb_metadata}),
        "unsupported_ter_serial",
    )

    with monkeypatch.context() as scoped:
        scoped.setattr(writer_module, "_MAX_ATOM_ROWS", 1)
        _assert_error(system, "too_many_atom_rows")
    with monkeypatch.context() as scoped:
        scoped.setattr(writer_module, "_MAX_OUTPUT_LINES", 2)
        _assert_error(system, "output_line_limit_exceeded")
    with monkeypatch.context() as scoped:
        scoped.setattr(writer_module, "_MAX_OUTPUT_LINES", 4)
        assert write_pdb(system).receipt.cryst1_count == 0
        _assert_error(
            parse_pdb(
                _pdb(
                    _cryst1(),
                    _atom(1),
                    _atom(2, atom_name_field=" N  ", residue_number=2, element="N"),
                )
            ).system,
            "output_line_limit_exceeded",
        )
    with monkeypatch.context() as scoped:
        scoped.setattr(writer_module, "_MAX_OUTPUT_BYTES", 1)
        _assert_error(system, "output_too_large")


def test_success_artifacts_are_factory_only_and_cross_wiring_is_rejected() -> None:
    mini = round_trip_pdb_source(MINI_PROTEIN.read_bytes(), source_id="mini")
    other = round_trip_pdb_source(_pdb(_atom(11, x=2.0)), source_id="other")
    zero = "0" * 64

    with pytest.raises(TypeError, match="factory-only"):
        PdbWriteReceipt(
            input_system_schema_id=mini.source_ingest.system.schema_id,
            parent_source_sha256=zero,
            input_snapshot_sha256=zero,
            input_topology_sha256=zero,
            input_representable_state_sha256=zero,
            input_parser_observation_sha256=zero,
            output_source_sha256=zero,
            output_byte_count=1,
            atom_count=1,
            bond_count=0,
            model_count=1,
            ter_count=0,
            cell_present=False,
            cryst1_count=0,
            input_missingness_report_sha256=zero,
            input_missingness_semantic_sha256=zero,
            missingness_evidence_present=False,
            input_missingness_remark_line_count=0,
            emitted_missingness_remark_line_count=0,
            missing_residue_claim_count=0,
            missing_atom_claim_count=0,
        )
    with pytest.raises(TypeError, match="factory-only"):
        PdbWriteResult(
            payload=mini.write_result.payload,
            receipt=mini.write_result.receipt,
            input_snapshot=mini.write_result._input_snapshot,
        )
    with pytest.raises(TypeError, match="factory-only"):
        PdbRoundTripReport(
            input_source_sha256=zero,
            input_snapshot_sha256=zero,
            input_topology_sha256=zero,
            input_representable_state_sha256=zero,
            input_parser_observation_sha256=zero,
            writer_receipt_sha256=zero,
            emitted_source_sha256=zero,
            reparsed_snapshot_sha256=zero,
            reparsed_topology_sha256=zero,
            reparsed_representable_state_sha256=zero,
            reparsed_parser_observation_sha256=zero,
            reemitted_source_sha256=zero,
            input_missingness_report_sha256=zero,
            reparsed_missingness_report_sha256=zero,
            input_missingness_semantic_sha256=zero,
            reparsed_missingness_semantic_sha256=zero,
            missingness_evidence_present=False,
            missing_residue_claim_count=0,
            missing_atom_claim_count=0,
        )
    with pytest.raises(TypeError, match="factory-only"):
        PdbRoundTripResult(
            source_ingest=mini.source_ingest,
            write_result=mini.write_result,
            reparsed_ingest=mini.reparsed_ingest,
            report=mini.report,
        )
    with pytest.raises(TypeError):
        replace(mini, _source_coverage=other.source_ingest.coverage)

    with pytest.raises(ValueError, match="cross-consistent"):
        PdbRoundTripResult(
            source_ingest=other.source_ingest,
            write_result=mini.write_result,
            reparsed_ingest=mini.reparsed_ingest,
            report=mini.report,
            _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
        )

    cell_result = round_trip_pdb_source(_pdb(_cryst1(), _atom(1)))
    with pytest.raises(ValueError, match="cross-consistent"):
        PdbRoundTripResult(
            source_ingest=mini.source_ingest,
            write_result=cell_result.write_result,
            reparsed_ingest=cell_result.reparsed_ingest,
            report=cell_result.report,
            _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
        )
    triclinic_result = round_trip_pdb_source(
        _pdb(
            _cryst1(
                a=33.125,
                b=34.25,
                c=35.5,
                alpha=80.0,
                beta=75.0,
                gamma=70.0,
                space_group="P 21 21 21",
                z=4,
            ),
            _atom(1),
        )
    )
    assert cell_result.write_result.receipt.cryst1_count == (
        triclinic_result.write_result.receipt.cryst1_count
    )
    assert cell_result.write_result.receipt.atom_count == (
        triclinic_result.write_result.receipt.atom_count
    )
    with pytest.raises(ValueError, match="source representable state"):
        PdbRoundTripResult(
            source_ingest=cell_result.source_ingest,
            write_result=triclinic_result.write_result,
            reparsed_ingest=triclinic_result.reparsed_ingest,
            report=triclinic_result.report,
            _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
        )

    original_receipt = mini.write_result.receipt
    receipt_kwargs = {
        "input_system_schema_id": original_receipt.input_system_schema_id,
        "parent_source_sha256": original_receipt.parent_source_sha256,
        "input_snapshot_sha256": original_receipt.input_snapshot_sha256,
        "input_topology_sha256": original_receipt.input_topology_sha256,
        "input_representable_state_sha256": (
            original_receipt.input_representable_state_sha256
        ),
        "input_parser_observation_sha256": (
            original_receipt.input_parser_observation_sha256
        ),
        "output_source_sha256": original_receipt.output_source_sha256,
        "output_byte_count": original_receipt.output_byte_count,
        "atom_count": original_receipt.atom_count,
        "bond_count": original_receipt.bond_count,
        "model_count": original_receipt.model_count,
        "ter_count": original_receipt.ter_count,
        "input_missingness_report_sha256": (
            original_receipt.input_missingness_report_sha256
        ),
        "input_missingness_semantic_sha256": (
            original_receipt.input_missingness_semantic_sha256
        ),
        "missingness_evidence_present": (original_receipt.missingness_evidence_present),
        "input_missingness_remark_line_count": (
            original_receipt.input_missingness_remark_line_count
        ),
        "emitted_missingness_remark_line_count": (
            original_receipt.emitted_missingness_remark_line_count
        ),
        "missing_residue_claim_count": original_receipt.missing_residue_claim_count,
        "missing_atom_claim_count": original_receipt.missing_atom_claim_count,
    }
    with pytest.raises(ValueError, match="agree with cell presence"):
        PdbWriteReceipt(
            **receipt_kwargs,
            cell_present=True,
            cryst1_count=0,
            _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
        )
    forged_cell_receipt = PdbWriteReceipt(
        **receipt_kwargs,
        cell_present=True,
        cryst1_count=1,
        _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
    )
    with pytest.raises(ValueError, match="CRYST1 count"):
        PdbWriteResult(
            payload=mini.write_result.payload,
            receipt=forged_cell_receipt,
            input_snapshot=mini.write_result._input_snapshot,
            _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
        )

    forged_receipt = PdbWriteReceipt(
        input_system_schema_id=original_receipt.input_system_schema_id,
        parent_source_sha256=original_receipt.parent_source_sha256,
        input_snapshot_sha256=original_receipt.input_snapshot_sha256,
        input_topology_sha256=original_receipt.input_topology_sha256,
        input_representable_state_sha256=(
            original_receipt.input_representable_state_sha256
        ),
        input_parser_observation_sha256=(
            original_receipt.input_parser_observation_sha256
        ),
        output_source_sha256=original_receipt.output_source_sha256,
        output_byte_count=original_receipt.output_byte_count,
        atom_count=1,
        bond_count=0,
        model_count=original_receipt.model_count,
        ter_count=original_receipt.ter_count,
        cell_present=original_receipt.cell_present,
        cryst1_count=original_receipt.cryst1_count,
        input_missingness_report_sha256=(
            original_receipt.input_missingness_report_sha256
        ),
        input_missingness_semantic_sha256=(
            original_receipt.input_missingness_semantic_sha256
        ),
        missingness_evidence_present=(original_receipt.missingness_evidence_present),
        input_missingness_remark_line_count=(
            original_receipt.input_missingness_remark_line_count
        ),
        emitted_missingness_remark_line_count=(
            original_receipt.emitted_missingness_remark_line_count
        ),
        missing_residue_claim_count=original_receipt.missing_residue_claim_count,
        missing_atom_claim_count=original_receipt.missing_atom_claim_count,
        _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
    )
    with pytest.raises(ValueError, match="atom count"):
        PdbWriteResult(
            payload=mini.write_result.payload,
            receipt=forged_receipt,
            input_snapshot=mini.write_result._input_snapshot,
            _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
        )


def test_round_trip_accessors_return_fresh_detached_snapshot_copies() -> None:
    result = round_trip_pdb_source(MINI_PROTEIN.read_bytes())
    source_coordinates = result.source_ingest.system.coordinates.clone()
    reparsed_coordinates = result.reparsed_ingest.system.coordinates.clone()

    exposed_source = result.source_ingest
    exposed_reparsed = result.reparsed_ingest
    exposed_source.system.coordinates[0, 0, 0] = 123.0
    exposed_reparsed.system.coordinates[0, 0, 0] = -456.0

    assert torch.equal(result.source_ingest.system.coordinates, source_coordinates)
    assert torch.equal(result.reparsed_ingest.system.coordinates, reparsed_coordinates)
    result.__post_init__()


def test_success_repr_is_bounded_and_does_not_expose_pdb_or_coordinate_payloads() -> (
    None
):
    result = round_trip_pdb_source(MINI_PROTEIN.read_bytes())
    result_repr = repr(result)
    write_repr = repr(result.write_result)

    assert len(result_repr) < 5_000
    assert len(write_repr) < 2_000
    assert "ATOM      1" not in result_repr
    assert "ATOM      1" not in write_repr
    assert "coordinates_ieee754" not in result_repr
    assert "raw_line" not in result_repr
    assert "tier-beta-mini-protein" not in result_repr


def test_writer_rejects_non_system_input_without_partial_output() -> None:
    with pytest.raises(TypeError, match="exact AllAtomSystem"):
        serialize_pdb(b"not-a-system")
