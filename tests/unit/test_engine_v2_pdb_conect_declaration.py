from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import betelgeuze_engine_v2.molecular as molecular
import betelgeuze_engine_v2.molecular.pdb_conect_declaration as conect
from betelgeuze_engine_v2.molecular.pdb_mmcif import (
    PDB_PARSER_VERSION,
    StructureParseError,
    parse_pdb,
)
from betelgeuze_engine_v2.molecular.pdb_writer import (
    PDB_REPRESENTABLE_STATE_SCHEMA_ID,
    PDB_WRITER_VERSION,
    write_pdb,
)


FIXTURES = (
    Path(__file__).resolve().parents[1] / "fixtures" / "v2_1_pdb_conect_declaration"
)

POSITIVE_ROWS = {
    "contextual_metal_bidirectional.pdb": ((1, (2,)), (2, (1,))),
    "explicit_model1_outside_declaration.pdb": ((1, (2,)),),
    "four_target_boundary.pdb": ((1, (2, 3, 4, 5)),),
    "ordered_duplicate_slots.pdb": (
        (1, (2, 2, 3)),
        (3, (1,)),
        (2, (1, 1)),
    ),
    "single_directed_declaration.pdb": ((1, (2,)),),
}

FAILURE_CODES = {
    "failure_inside_model.pdb": "conect_inside_model",
    "failure_interior_target_gap.pdb": "invalid_conect",
    "failure_model_id2.pdb": "unsupported_model_profile",
    "failure_multimodel.pdb": "unsupported_model_profile",
    "failure_no_conect.pdb": "missing_conect_declaration",
    "failure_noncontiguous_before_ter.pdb": ("noncontiguous_conect_suffix"),
    "failure_reserved_columns.pdb": "invalid_conect",
    "failure_self_reference.pdb": "self_reference",
    "failure_unknown_source.pdb": "unknown_atom_reference",
    "failure_unknown_target.pdb": "unknown_atom_reference",
}

FALSE_AUTHORITY_FIELDS = (
    "bare_system_preserves_declaration",
    "source_authenticated",
    "conect_declaration_authoritative",
    "bond_topology_established",
    "bond_topology_interpreted",
    "bond_order_assigned",
    "bond_order_interpreted",
    "covalent_bond_interpreted",
    "coordination_bond_interpreted",
    "chemistry_interpreted",
    "preparation_ready",
    "parameterability_assessed",
    "physics_supported",
    "runtime_eligible",
    "execution_authorized",
    "simulation_ready",
    "claim_safe",
    "general_pdb_round_trip_evidence_ready",
    "all_format_round_trip_evidence_ready",
)


def _payload(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def _assert_code(
    payload: bytes,
    code: str,
    *,
    source_id: str = "fixture",
) -> conect.PdbConectDeclarationError:
    with pytest.raises(conect.PdbConectDeclarationError) as exc_info:
        conect.parse_pdb_conect_declaration(payload, source_id=source_id)
    assert exc_info.value.code == code
    return exc_info.value


def _rows(
    value: conect.PdbConectDeclarationIngestResult,
) -> tuple[tuple[int, tuple[int, ...]], ...]:
    return tuple((row.source_serial, row.target_serials) for row in value.rows)


def _declaration_source(*rows: bytes) -> bytes:
    carrier = _payload("single_directed_declaration.pdb").splitlines()[:2]
    return b"\n".join((*carrier, *rows, b"END")) + b"\n"


def test_contract_ids_versions_limits_and_public_exports_are_exact() -> None:
    assert conect.PDB_CONECT_DECLARATION_ENVELOPE_VERSION == "1.0.0"
    assert conect.PDB_CONECT_DECLARATION_PARSER_VERSION == "1.0.0"
    assert conect.PDB_CONECT_DECLARATION_WRITER_VERSION == "1.0.0"
    assert conect.PDB_CONECT_DECLARATION_PARSER_NAME == (
        "betelgeuze_engine_v2.molecular.pdb_conect_declaration"
    )
    assert conect.PDB_CONECT_DECLARATION_PROFILE_ID == (
        "strict_pdb_single_model_id1_ordered_conect_declaration_envelope/1.0.0"
    )
    assert conect.PDB_CONECT_DECLARATION_PROJECTION_SCOPE == (
        "ordered_source_directed_conect_rows_and_target_slot_occurrences_only"
    )
    assert conect.PDB_CONECT_DECLARATION_PROJECTION_SCHEMA_ID == (
        "betelgeuze.pdb_conect_declaration_projection/1.0.0"
    )
    assert conect.PDB_CONECT_DECLARATION_RECORD_STATE_SCHEMA_ID == (
        "betelgeuze.pdb_conect_declaration_record_state/1.0.0"
    )
    assert conect.PDB_CONECT_DECLARATION_SOURCE_BINDING_SCHEMA_ID == (
        "betelgeuze.pdb_conect_declaration_source_binding/1.0.0"
    )
    assert conect.PDB_CONECT_DECLARATION_WRITE_RECEIPT_SCHEMA_ID == (
        "betelgeuze.pdb_conect_declaration_write_receipt/1.0.0"
    )
    assert conect.PDB_CONECT_DECLARATION_ROUND_TRIP_REPORT_SCHEMA_ID == (
        "betelgeuze.pdb_conect_declaration_round_trip_report/1.0.0"
    )

    assert PDB_PARSER_VERSION == "1.8.0"
    assert PDB_WRITER_VERSION == "1.2.0"
    assert PDB_REPRESENTABLE_STATE_SCHEMA_ID == (
        "betelgeuze.pdb_representable_state/1.2.0"
    )
    assert conect.MAX_PDB_CONECT_DECLARATION_INPUT_BYTES == 67_108_864
    assert conect.MAX_PDB_CONECT_DECLARATION_SOURCE_ID_BYTES == 4_096
    assert conect.MAX_PDB_CONECT_DECLARATION_LINE_COUNT == 250_000
    assert conect.MAX_PDB_CONECT_DECLARATION_RECORDS == 20_000
    assert conect.MAX_PDB_CONECT_DECLARATION_TARGET_OCCURRENCES == 80_000
    assert conect.MAX_PDB_CONECT_DECLARATION_PROJECTION_BYTES == 16_777_216
    assert conect.MAX_PDB_CONECT_DECLARATION_OUTPUT_BYTES == 67_108_864
    assert conect.MAX_PDB_CONECT_DECLARATION_OUTPUT_LINES == 250_000
    assert conect.MAX_PDB_CONECT_DECLARATION_OUTPUT_LINE_CHARS == 80

    for name in conect.__all__:
        assert getattr(molecular, name) == getattr(conect, name)


def test_fixture_inventory_is_exactly_five_positive_and_ten_failure_rows() -> None:
    assert {path.name for path in FIXTURES.glob("*.pdb")} == (
        set(POSITIVE_ROWS) | set(FAILURE_CODES)
    )
    assert len(POSITIVE_ROWS) == 5
    assert len(FAILURE_CODES) == 10


@pytest.mark.parametrize(
    ("fixture", "expected_rows"),
    tuple(POSITIVE_ROWS.items()),
)
def test_positive_fixtures_preserve_exact_ordered_rows_and_artifact_chain(
    fixture: str,
    expected_rows: tuple[tuple[int, tuple[int, ...]], ...],
) -> None:
    result = conect.round_trip_pdb_conect_declaration_source(
        _payload(fixture),
        source_id=fixture,
    )
    ingest = result.source_ingest
    report = result.report.to_dict()

    assert _rows(ingest) == expected_rows
    assert tuple(row.ordinal for row in ingest.rows) == tuple(range(len(expected_rows)))
    assert ingest.conect_record_count == len(expected_rows)
    assert ingest.target_occurrence_count == sum(
        len(targets) for _, targets in expected_rows
    )
    assert ingest.system.bonds == ()
    assert ingest.coverage.bond_count == 0
    assert ingest.coverage.model_count == 1
    assert ingest.system.provenance.metadata["model_ids"] == [1]

    assert conect.pdb_conect_declaration_projection_sha256(ingest) == (
        ingest.declaration_projection_sha256
    )
    assert conect.pdb_conect_declaration_source_binding_sha256(ingest) == (
        ingest.source_binding_sha256
    )
    assert conect.pdb_conect_declaration_record_state_sha256(ingest) == (
        ingest.record_state_sha256
    )
    assert conect.serialize_pdb_conect_declaration(ingest) == (
        result.write_result.payload
    )
    assert result.write_result.payload == result.reemitted_write_result.payload
    assert report["declaration_projection_equal"] is True
    assert report["carrier_topology_equal"] is True
    assert report["carrier_representable_state_equal"] is True
    assert report["canonical_carrier_source_equal"] is True
    assert report["record_state_equal"] is True
    assert report["source_id_equal"] is True
    assert report["emitted_source_reparsed_exact"] is True
    assert report["write_receipt_source_bound"] is True
    assert report["reemitted_receipt_reparsed_bound"] is True
    assert report["second_emission_byte_stable"] is True
    assert report["carrier_bond_count_zero"] is True
    assert report["ordered_conect_declaration_round_trip_preserved"] is True

    documents = (
        ingest.to_dict(),
        result.write_result.receipt.to_dict(),
        result.write_result.to_dict(),
        report,
        result.to_dict(),
    )
    for document in documents:
        for field_name in FALSE_AUTHORITY_FIELDS:
            assert document[field_name] is False


def test_order_duplicates_grouping_and_asymmetry_are_not_multiplicity() -> None:
    ordered = conect.parse_pdb_conect_declaration(
        _payload("ordered_duplicate_slots.pdb")
    )
    projection = conect._projection_document(ordered.rows)

    assert _rows(ordered) == POSITIVE_ROWS["ordered_duplicate_slots.pdb"]
    assert projection["rows"][0]["target_serials"] == [2, 2, 3]
    assert projection["rows"][0]["target_slot_occurrences"] == [
        {"slot_ordinal": 0, "target_serial": 2},
        {"slot_ordinal": 1, "target_serial": 2},
        {"slot_ordinal": 2, "target_serial": 3},
    ]
    assert projection["direction_preserved"] is True
    assert projection["duplicate_rows_preserved"] is True
    assert projection["duplicate_target_occurrences_preserved"] is True
    assert projection["row_grouping_preserved"] is True
    assert projection["unordered_normalization_applied"] is False
    assert projection["duplicate_occurrences_interpreted_as_bond_order"] is False

    repeated = _declaration_source(*(b"CONECT    1    2" for _ in range(4)))
    repeated_result = conect.round_trip_pdb_conect_declaration_source(repeated)
    assert _rows(repeated_result.source_ingest) == (
        (1, (2,)),
        (1, (2,)),
        (1, (2,)),
        (1, (2,)),
    )
    assert repeated_result.source_ingest.target_occurrence_count == 4
    assert repeated_result.source_ingest.system.bonds == ()

    directed = conect.parse_pdb_conect_declaration(
        _payload("single_directed_declaration.pdb")
    )
    assert _rows(directed) == ((1, (2,)),)
    assert all(row.source_serial != 2 for row in directed.rows)


def test_explicit_model_one_normalizes_to_implicit_without_state_loss() -> None:
    explicit = conect.parse_pdb_conect_declaration(
        _payload("explicit_model1_outside_declaration.pdb"),
        source_id="same",
    )
    implicit = conect.parse_pdb_conect_declaration(
        _payload("single_directed_declaration.pdb"),
        source_id="same",
    )
    explicit_write = conect.write_pdb_conect_declaration(explicit)
    implicit_write = conect.write_pdb_conect_declaration(implicit)

    assert explicit_write.payload == implicit_write.payload
    assert explicit.declaration_projection_sha256 == (
        implicit.declaration_projection_sha256
    )
    assert explicit.record_state_sha256 == implicit.record_state_sha256
    assert explicit.source_binding_sha256 != implicit.source_binding_sha256
    assert b"MODEL " not in explicit_write.payload
    assert b"ENDMDL" not in explicit_write.payload
    assert _rows(explicit) == ((1, (2,)),)


def test_four_target_boundary_and_canonical_eighty_column_tail() -> None:
    result = conect.round_trip_pdb_conect_declaration_source(
        _payload("four_target_boundary.pdb")
    )
    lines = result.write_result.payload.splitlines()
    declaration = next(line for line in lines if line.startswith(b"CONECT"))

    assert result.source_ingest.rows[0].target_serials == (2, 3, 4, 5)
    assert declaration[:31] == b"CONECT    1    2    3    4    5"
    assert declaration[31:] == b" " * 49
    assert all(len(line) == 80 for line in lines)
    assert lines[-1] == b"END".ljust(80)
    assert result.write_result.payload.endswith(b"\n")


def test_contextual_metal_declaration_never_promotes_coordination() -> None:
    result = conect.round_trip_pdb_conect_declaration_source(
        _payload("contextual_metal_bidirectional.pdb")
    )
    system = result.source_ingest.system

    assert tuple(atom.element for atom in system.atoms) == ("Zn", "N")
    assert system.bonds == ()
    assert result.source_ingest.coverage.bond_count == 0
    for document in (
        result.source_ingest.to_dict(),
        result.write_result.receipt.to_dict(),
        result.report.to_dict(),
    ):
        assert document["coordination_bond_interpreted"] is False
        assert document["covalent_bond_interpreted"] is False
        assert document["bond_order_interpreted"] is False
        assert document["chemistry_interpreted"] is False


def test_base_parser_remains_fail_closed_and_bare_system_loses_declaration() -> None:
    payload = _payload("single_directed_declaration.pdb")
    with pytest.raises(StructureParseError) as exc_info:
        parse_pdb(payload)
    assert exc_info.value.code == "unsupported_contextual_conect_semantics"

    ingest = conect.parse_pdb_conect_declaration(payload)
    bare_write = write_pdb(ingest.system)
    assert b"CONECT" not in bare_write.payload
    assert ingest.to_dict()["bare_system_preserves_declaration"] is False
    _assert_code(bare_write.payload, "missing_conect_declaration")
    with pytest.raises(TypeError, match="exact ingest result"):
        conect.write_pdb_conect_declaration(ingest.system)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("fixture", "code"),
    tuple(FAILURE_CODES.items()),
)
def test_failure_fixtures_return_exact_typed_codes(
    fixture: str,
    code: str,
) -> None:
    error = _assert_code(_payload(fixture), code)
    assert error.detail
    assert _payload(fixture).decode("ascii") not in str(error)


@pytest.mark.parametrize(
    ("row", "code"),
    (
        (b"conect    1    2", "invalid_conect"),
        (b"CONECT   +1    2", "invalid_conect"),
        (b"CONECT    1", "invalid_conect"),
        (b"CONECT    1    2    2    2    2    2", "invalid_conect"),
    ),
)
def test_additional_fixed_column_syntax_boundaries_fail_closed(
    row: bytes,
    code: str,
) -> None:
    _assert_code(_declaration_source(row), code)


def test_additional_placement_and_profile_boundaries_have_stable_codes() -> None:
    source = _payload("single_directed_declaration.pdb")
    _assert_code(
        source.replace(b"CONECT    1    2\nEND", b"CONECT    1    2\n\nEND"),
        "noncontiguous_conect_suffix",
    )
    _assert_code(source + b"CONECT    1    2\n", "conect_after_end")
    _assert_code(source + b"HEADER AFTER END\n", "content_after_end")
    _assert_code(
        source.replace(b"END\n", b"END\nEND\n"),
        "invalid_end_layout",
    )

    _assert_code(b"CRYST1" + b" " * 74 + b"\n" + source, "unsupported_cryst1")
    _assert_code(b"REMARK 465 OPAQUE\n" + source, "unsupported_missingness")
    atom_lines = source.splitlines()
    altloc = bytearray(atom_lines[0])
    altloc[16] = ord("A")
    _assert_code(
        b"\n".join((bytes(altloc), *atom_lines[1:])) + b"\n",
        "unsupported_altloc",
    )


def test_public_argument_text_and_line_ending_validation_is_strict() -> None:
    payload = _payload("single_directed_declaration.pdb")
    with pytest.raises(TypeError, match="exact bytes"):
        conect.parse_pdb_conect_declaration("not bytes")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="exact string"):
        conect.parse_pdb_conect_declaration(
            payload,
            source_id=1,  # type: ignore[arg-type]
        )
    _assert_code(b"", "empty_input")
    _assert_code(payload.replace(b"LIG", b"L\xffG", 1), "invalid_ascii")
    _assert_code(payload.replace(b"\n", b"\r", 1), "invalid_line_endings")


def test_all_resource_caps_accept_exact_boundary_and_reject_one_over(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    single = _payload("single_directed_declaration.pdb")
    ordered = _payload("ordered_duplicate_slots.pdb")
    normal = conect.parse_pdb_conect_declaration(ordered)
    output = conect.write_pdb_conect_declaration(normal).payload

    with monkeypatch.context() as scoped:
        scoped.setattr(
            conect,
            "MAX_PDB_CONECT_DECLARATION_INPUT_BYTES",
            len(single),
        )
        conect.parse_pdb_conect_declaration(single)
        scoped.setattr(
            conect,
            "MAX_PDB_CONECT_DECLARATION_INPUT_BYTES",
            len(single) - 1,
        )
        _assert_code(single, "input_too_large")

    physical_lines = single.count(b"\n") + 1
    with monkeypatch.context() as scoped:
        scoped.setattr(
            conect,
            "MAX_PDB_CONECT_DECLARATION_LINE_COUNT",
            physical_lines,
        )
        conect.parse_pdb_conect_declaration(single)
        scoped.setattr(
            conect,
            "MAX_PDB_CONECT_DECLARATION_LINE_COUNT",
            physical_lines - 1,
        )
        _assert_code(single, "too_many_lines")

    exact_source_id = "x" * conect.MAX_PDB_CONECT_DECLARATION_SOURCE_ID_BYTES
    conect.parse_pdb_conect_declaration(single, source_id=exact_source_id)
    _assert_code(
        single,
        "source_id_too_large",
        source_id=exact_source_id + "x",
    )

    with monkeypatch.context() as scoped:
        scoped.setattr(conect, "MAX_PDB_CONECT_DECLARATION_RECORDS", 3)
        conect.parse_pdb_conect_declaration(ordered)
        scoped.setattr(conect, "MAX_PDB_CONECT_DECLARATION_RECORDS", 2)
        _assert_code(ordered, "too_many_conect_records")

    with monkeypatch.context() as scoped:
        scoped.setattr(
            conect,
            "MAX_PDB_CONECT_DECLARATION_TARGET_OCCURRENCES",
            6,
        )
        conect.parse_pdb_conect_declaration(ordered)
        scoped.setattr(
            conect,
            "MAX_PDB_CONECT_DECLARATION_TARGET_OCCURRENCES",
            5,
        )
        _assert_code(ordered, "too_many_target_occurrences")

    projection_bytes = normal.declaration_projection_byte_count
    with monkeypatch.context() as scoped:
        scoped.setattr(
            conect,
            "MAX_PDB_CONECT_DECLARATION_PROJECTION_BYTES",
            projection_bytes,
        )
        conect.parse_pdb_conect_declaration(ordered)
        scoped.setattr(
            conect,
            "MAX_PDB_CONECT_DECLARATION_PROJECTION_BYTES",
            projection_bytes - 1,
        )
        _assert_code(ordered, "projection_too_large")

    with monkeypatch.context() as scoped:
        scoped.setattr(
            conect,
            "MAX_PDB_CONECT_DECLARATION_OUTPUT_BYTES",
            len(output),
        )
        conect.parse_pdb_conect_declaration(ordered)
        scoped.setattr(
            conect,
            "MAX_PDB_CONECT_DECLARATION_OUTPUT_BYTES",
            len(output) - 1,
        )
        _assert_code(ordered, "output_too_large")

    output_physical_lines = len(output.splitlines()) + 1
    with monkeypatch.context() as scoped:
        scoped.setattr(
            conect,
            "MAX_PDB_CONECT_DECLARATION_OUTPUT_LINES",
            output_physical_lines,
        )
        conect.parse_pdb_conect_declaration(ordered)
        scoped.setattr(
            conect,
            "MAX_PDB_CONECT_DECLARATION_OUTPUT_LINES",
            output_physical_lines - 1,
        )
        _assert_code(ordered, "output_too_many_lines")


def test_input_resource_preflight_runs_before_nested_parser(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _payload("single_directed_declaration.pdb")

    def forbidden_base_parse(*_args: Any, **_kwargs: Any) -> Any:
        pytest.fail("base parser must not run after an envelope preflight failure")

    monkeypatch.setattr(
        conect,
        "MAX_PDB_CONECT_DECLARATION_INPUT_BYTES",
        len(payload) - 1,
    )
    monkeypatch.setattr(conect, "parse_pdb", forbidden_base_parse)
    _assert_code(payload, "input_too_large")


def test_crlf_normalization_binds_full_source_but_emits_identically() -> None:
    lf = _payload("single_directed_declaration.pdb")
    crlf = lf.replace(b"\n", b"\r\n")
    lf_ingest = conect.parse_pdb_conect_declaration(lf, source_id="same")
    crlf_ingest = conect.parse_pdb_conect_declaration(crlf, source_id="same")
    lf_write = conect.write_pdb_conect_declaration(lf_ingest)
    crlf_write = conect.write_pdb_conect_declaration(crlf_ingest)

    assert lf_ingest.full_source_sha256 != crlf_ingest.full_source_sha256
    assert lf_ingest.normalized_source_sha256 == (crlf_ingest.normalized_source_sha256)
    assert lf_ingest.declaration_projection_sha256 == (
        crlf_ingest.declaration_projection_sha256
    )
    assert lf_ingest.record_state_sha256 == crlf_ingest.record_state_sha256
    assert lf_ingest.source_binding_sha256 != crlf_ingest.source_binding_sha256
    assert lf_write.payload == crlf_write.payload
    assert lf_write.receipt.receipt_sha256 != crlf_write.receipt.receipt_sha256
    assert b"\r" not in lf_write.payload


def test_ingest_detects_stale_crosswire_and_returns_detached_state() -> None:
    source = conect.parse_pdb_conect_declaration(
        _payload("single_directed_declaration.pdb")
    )
    reverse_payload = _payload("single_directed_declaration.pdb").replace(
        b"CONECT    1    2",
        b"CONECT    2    1",
    )
    reverse = conect.parse_pdb_conect_declaration(reverse_payload)

    original_coordinate = float(source.system.coordinates[0, 0, 0].item())
    detached = source.system
    detached.coordinates[0, 0, 0] = 999.0
    assert float(source.system.coordinates[0, 0, 0].item()) == original_coordinate

    document = source.to_dict()
    document["carrier_model_ids"][0] = 99
    document["claim_safe"] = True
    assert source.to_dict()["carrier_model_ids"] == [1]
    assert source.to_dict()["claim_safe"] is False

    object.__setattr__(
        source,
        "_components",
        replace(source._components, rows=reverse.rows),
    )
    with pytest.raises(conect.PdbConectDeclarationError) as exc_info:
        conect.write_pdb_conect_declaration(source)
    assert exc_info.value.code == "stale_or_crosswired_ingest"


@pytest.mark.parametrize(
    "factory",
    (
        lambda: conect.PdbConectDeclarationRow(
            ordinal=0,
            source_serial=1,
            target_serials=(2,),
        ),
        conect.PdbConectDeclarationIngestResult,
        conect.PdbConectDeclarationWriteReceipt,
        conect.PdbConectDeclarationWriteResult,
        conect.PdbConectDeclarationRoundTripReport,
        conect.PdbConectDeclarationRoundTripResult,
    ),
)
def test_success_artifacts_are_factory_only(factory: Any) -> None:
    with pytest.raises(TypeError, match="factory-only"):
        factory()


def test_receipt_and_write_result_reject_tamper_and_crosswire() -> None:
    source = conect.parse_pdb_conect_declaration(
        _payload("single_directed_declaration.pdb"),
        source_id="tamper",
    )
    write_result = conect.write_pdb_conect_declaration(source)
    components = source._components

    forged_document = write_result.receipt.to_dict()
    forged_document.pop("receipt_sha256")
    forged_document["claim_safe"] = True
    with pytest.raises(conect.PdbConectDeclarationError) as exc_info:
        conect.PdbConectDeclarationWriteReceipt(
            forged_document,
            components=components,
            payload=write_result.payload,
            _factory_token=conect._FACTORY_TOKEN,
        )
    assert exc_info.value.code == "invalid_write_receipt"

    with pytest.raises(conect.PdbConectDeclarationError) as exc_info:
        conect.PdbConectDeclarationWriteReceipt(
            conect._receipt_document(components, b""),
            components=components,
            payload=b"",
            _factory_token=conect._FACTORY_TOKEN,
        )
    assert exc_info.value.code == "invalid_write_payload"

    reverse = conect.parse_pdb_conect_declaration(
        _payload("single_directed_declaration.pdb").replace(
            b"CONECT    1    2",
            b"CONECT    2    1",
        ),
        source_id="tamper",
    )
    stale_components = replace(components, rows=reverse.rows)
    with pytest.raises(conect.PdbConectDeclarationError) as exc_info:
        conect.PdbConectDeclarationWriteReceipt(
            conect._receipt_document(components, write_result.payload),
            components=stale_components,
            payload=write_result.payload,
            _factory_token=conect._FACTORY_TOKEN,
        )
    assert exc_info.value.code == "stale_or_crosswired_receipt"

    with pytest.raises(conect.PdbConectDeclarationError) as exc_info:
        conect.PdbConectDeclarationWriteResult(
            write_result.payload + b"X",
            write_result.receipt,
            _factory_token=conect._FACTORY_TOKEN,
        )
    assert exc_info.value.code == "invalid_write_artifacts"


def test_report_and_aggregate_reject_same_output_crosswires() -> None:
    lf = _payload("single_directed_declaration.pdb")
    crlf = lf.replace(b"\n", b"\r\n")
    normal = conect.round_trip_pdb_conect_declaration_source(
        lf,
        source_id="same",
    )
    crlf_ingest = conect.parse_pdb_conect_declaration(crlf, source_id="same")
    crlf_write = conect.write_pdb_conect_declaration(crlf_ingest)
    assert crlf_write.payload == normal.write_result.payload

    crosswired = conect._report_document(
        normal.source_ingest,
        normal.reparsed_ingest,
        crlf_write,
        normal.reemitted_write_result,
    )
    assert crosswired["write_receipt_source_bound"] is False
    assert crosswired["ordered_conect_declaration_round_trip_preserved"] is False
    with pytest.raises(conect.PdbConectDeclarationError) as exc_info:
        conect.PdbConectDeclarationRoundTripReport(
            crosswired,
            source=normal.source_ingest,
            reparsed=normal.reparsed_ingest,
            write_result=crlf_write,
            reemitted_write_result=normal.reemitted_write_result,
            _factory_token=conect._FACTORY_TOKEN,
        )
    assert exc_info.value.code == "crosswired_round_trip_artifacts"

    valid_document = normal.report.to_dict()
    valid_document.pop("report_sha256")
    valid_document["claim_safe"] = True
    with pytest.raises(conect.PdbConectDeclarationError) as exc_info:
        conect.PdbConectDeclarationRoundTripReport(
            valid_document,
            source=normal.source_ingest,
            reparsed=normal.reparsed_ingest,
            write_result=normal.write_result,
            reemitted_write_result=normal.reemitted_write_result,
            _factory_token=conect._FACTORY_TOKEN,
        )
    assert exc_info.value.code == "crosswired_round_trip_artifacts"

    with pytest.raises(conect.PdbConectDeclarationError) as exc_info:
        conect.PdbConectDeclarationRoundTripResult(
            normal.source_ingest,
            crlf_write,
            normal.reparsed_ingest,
            normal.reemitted_write_result,
            normal.report,
            _factory_token=conect._FACTORY_TOKEN,
        )
    assert exc_info.value.code == "crosswired_round_trip_artifacts"


def test_base_parser_and_writer_contract_drift_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _payload("single_directed_declaration.pdb")
    real_parse = conect.parse_pdb

    def forged_parse(*args: Any, **kwargs: Any) -> Any:
        result = real_parse(*args, **kwargs)
        provenance = replace(result.system.provenance, parser_version="9.9.9")
        return replace(result, system=replace(result.system, provenance=provenance))

    with monkeypatch.context() as scoped:
        scoped.setattr(conect, "parse_pdb", forged_parse)
        _assert_code(payload, "base_parser_contract_drift")

    real_write = conect.write_pdb

    def forged_write(system: Any) -> Any:
        result = real_write(system)
        bad_end = b"BROKEN".ljust(80) + b"\n"
        return SimpleNamespace(
            payload=result.payload[:-81] + bad_end,
            receipt=result.receipt,
        )

    with monkeypatch.context() as scoped:
        scoped.setattr(conect, "write_pdb", forged_write)
        _assert_code(payload, "base_writer_contract_drift")


def test_base_parser_detached_authority_coverage_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _payload("single_directed_declaration.pdb")
    real_parse = conect.parse_pdb

    def forged_parse(*args: Any, **kwargs: Any) -> Any:
        result = real_parse(*args, **kwargs)
        forged_coverage = replace(
            result.coverage,
            preparation_ready=True,
            claim_safe=True,
        )
        return replace(result, coverage=forged_coverage)

    monkeypatch.setattr(conect, "parse_pdb", forged_parse)
    _assert_code(payload, "base_authority_drift")


def test_base_parser_detached_missingness_crosswire_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _payload("single_directed_declaration.pdb")
    real_parse = conect.parse_pdb

    def forged_parse(*args: Any, **kwargs: Any) -> Any:
        result = real_parse(*args, **kwargs)
        forged_missingness = replace(
            result.missingness_evidence,
            source_sha256="0" * 64,
        )
        return replace(result, missingness_evidence=forged_missingness)

    monkeypatch.setattr(conect, "parse_pdb", forged_parse)
    _assert_code(payload, "stale_base_missingness")


@pytest.mark.parametrize(
    ("nested_attr", "accessor"),
    (
        ("_source_ingest", lambda result: result.report),
        ("_reparsed_ingest", lambda result: result.to_dict()),
    ),
)
def test_aggregate_rejects_nested_ingest_component_mutation_on_access(
    nested_attr: str,
    accessor: Any,
) -> None:
    result = conect.round_trip_pdb_conect_declaration_source(
        _payload("single_directed_declaration.pdb"),
        source_id="aggregate-tamper",
    )
    reverse = conect.parse_pdb_conect_declaration(
        _payload("single_directed_declaration.pdb").replace(
            b"CONECT    1    2",
            b"CONECT    2    1",
        ),
        source_id="aggregate-tamper",
    )
    nested_ingest = getattr(result, nested_attr)
    object.__setattr__(
        nested_ingest,
        "_components",
        replace(nested_ingest._components, rows=reverse.rows),
    )

    with pytest.raises(conect.PdbConectDeclarationError) as exc_info:
        accessor(result)
    assert exc_info.value.code == "crosswired_round_trip_artifacts"
