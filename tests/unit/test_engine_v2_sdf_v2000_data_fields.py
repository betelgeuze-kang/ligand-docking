from __future__ import annotations

from dataclasses import FrozenInstanceError
import hashlib
import json
from pathlib import Path

import pytest

from betelgeuze_engine_v2.molecular import (
    MAX_SDF_V2000_DATA_FIELDS,
    MAX_SDF_V2000_DATA_FIELD_NAME_CHARS,
    MAX_SDF_V2000_DATA_FIELD_PAYLOAD_BYTES,
    MAX_SDF_V2000_DATA_FIELD_TOTAL_VALUE_LINES,
    MAX_SDF_V2000_DATA_FIELD_VALUE_LINE_CHARS,
    MAX_SDF_V2000_DATA_FIELD_VALUE_LINES,
    SDF_V2000_DATA_FIELD_ENVELOPE_VERSION,
    SDF_V2000_DATA_FIELD_PARSER_NAME,
    SDF_V2000_DATA_FIELD_PARSER_VERSION,
    SDF_V2000_DATA_FIELD_PROFILE_ID,
    SDF_V2000_DATA_FIELD_PROJECTION_SCHEMA_ID,
    SDF_V2000_DATA_FIELD_RECORD_STATE_SCHEMA_ID,
    SDF_V2000_DATA_FIELD_ROUND_TRIP_REPORT_SCHEMA_ID,
    SDF_V2000_DATA_FIELD_WRITE_RECEIPT_SCHEMA_ID,
    SDF_V2000_DATA_FIELD_WRITER_VERSION,
    SDF_V2000_PARSER_VERSION,
    SDF_V2000_WRITER_VERSION,
    SdfV2000DataField,
    SdfV2000DataFieldError,
    SdfV2000DataFieldIngestResult,
    SdfV2000DataFieldRoundTripReport,
    SdfV2000DataFieldRoundTripResult,
    SdfV2000DataFieldWriteReceipt,
    SdfV2000DataFieldWriteResult,
    SdfV2000ParseError,
    parse_sdf_v2000,
    parse_sdf_v2000_data_fields,
    round_trip_sdf_v2000_data_fields_source,
    sdf_v2000_data_field_projection_sha256,
    sdf_v2000_data_field_record_state_sha256,
    serialize_sdf_v2000_data_fields,
    write_sdf_v2000,
    write_sdf_v2000_data_fields,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
ETHANOL = FIXTURES / "tier_beta" / "ethanol.sdf"


def _base_prefix() -> bytes:
    source = ETHANOL.read_bytes()
    assert source.endswith(b"$$$$\n")
    return source[: -len(b"$$$$\n")]


def _record_with_tail(lines: list[str], *, crlf: bool = False) -> bytes:
    newline = b"\r\n" if crlf else b"\n"
    base = _base_prefix().replace(b"\n", newline)
    return base + newline.join(line.encode("ascii") for line in lines) + newline


def _field_source(
    fields: tuple[tuple[str, tuple[str, ...]], ...],
    *,
    crlf: bool = False,
) -> bytes:
    lines: list[str] = []
    for name, values in fields:
        lines.append(f">  <{name}>")
        lines.extend(values)
        lines.append("")
    lines.append("$$$$")
    return _record_with_tail(lines, crlf=crlf)


def _atom_line(
    element: str,
    *,
    x: float = 0.0,
    charge_code: int = 0,
    atom_map: int = 0,
) -> str:
    return (
        f"{x:10.4f}{0.0:10.4f}{0.0:10.4f} {element:<3}"
        f"{0:2d}{charge_code:3d}{0:3d}{0:3d}"
        f"{0:3d}{0:3d}{0:3d}{0:3d}{0:3d}{atom_map:3d}{0:3d}{0:3d}"
    )


def _charged_isotope_source() -> bytes:
    lines = [
        "markers",
        "codex",
        "data field envelope",
        "  2  1  0  0  0  0  0  0  0  0999 V2000",
        _atom_line("C", atom_map=17),
        _atom_line("N", x=1.2),
        "  1  2  1  0",
        "M  CHG  1   1  -1",
        "M  ISO  1   2  15",
        "M  END",
        ">  <MARKER_NOTE>",
        "opaque",
        "",
        "$$$$",
    ]
    return ("\n".join(lines) + "\n").encode("ascii")


def _assert_parse_code(source: bytes, code: str) -> SdfV2000DataFieldError:
    with pytest.raises(SdfV2000DataFieldError) as exc_info:
        parse_sdf_v2000_data_fields(source)
    assert exc_info.value.code == code
    return exc_info.value


def test_public_contract_and_ordered_opaque_field_projection() -> None:
    source = _field_source(
        (
            ("Name", ("  leading and trailing  ",)),
            ("EMPTY", ()),
            ("Name", ("first", "second")),
        )
    )
    ingest = parse_sdf_v2000_data_fields(source, source_id="opaque-fields")

    assert SDF_V2000_DATA_FIELD_ENVELOPE_VERSION == "1.0.0"
    assert SDF_V2000_DATA_FIELD_PARSER_VERSION == "1.0.0"
    assert SDF_V2000_DATA_FIELD_WRITER_VERSION == "1.0.0"
    assert SDF_V2000_DATA_FIELD_PARSER_NAME == (
        "betelgeuze_engine_v2.molecular.sdf_v2000_data_fields"
    )
    assert SDF_V2000_DATA_FIELD_PROFILE_ID == (
        "strict_sdf_v2000_named_opaque_data_field_envelope/1.0.0"
    )
    assert SDF_V2000_DATA_FIELD_PROJECTION_SCHEMA_ID == (
        "betelgeuze.sdf_v2000_data_field_projection/1.0.0"
    )
    assert SDF_V2000_DATA_FIELD_RECORD_STATE_SCHEMA_ID == (
        "betelgeuze.sdf_v2000_data_field_record_representable_state/1.0.0"
    )
    assert SDF_V2000_DATA_FIELD_WRITE_RECEIPT_SCHEMA_ID == (
        "betelgeuze.sdf_v2000_data_field_write_receipt/1.0.0"
    )
    assert SDF_V2000_DATA_FIELD_ROUND_TRIP_REPORT_SCHEMA_ID == (
        "betelgeuze.sdf_v2000_data_field_round_trip_report/1.0.0"
    )
    assert [item.name for item in ingest.data_fields] == ["Name", "EMPTY", "Name"]
    assert ingest.data_fields[0].value_lines == ("  leading and trailing  ",)
    assert ingest.data_fields[1].value_lines == ()
    assert ingest.data_fields[2].value_lines == ("first", "second")
    assert ingest.data_field_count == 3
    assert ingest.data_field_value_line_count == 3
    assert ingest.full_source_sha256 == hashlib.sha256(source).hexdigest()
    legacy_metadata = parse_sdf_v2000(ETHANOL.read_bytes()).system.metadata
    assert ingest.system.metadata == legacy_metadata
    assert set(ingest.system.metadata) == {"sdf_v2000_header"}
    assert ingest.system.provenance.parser_version == SDF_V2000_PARSER_VERSION
    assert ingest.system.provenance.source_sha256 == ingest.base_mol_block_source_sha256
    assert ingest.system.provenance.source_sha256 != ingest.full_source_sha256
    assert sdf_v2000_data_field_projection_sha256(ingest) == (
        ingest.data_field_projection_sha256
    )
    assert sdf_v2000_data_field_record_state_sha256(ingest) == (
        ingest.record_representable_state_sha256
    )
    assert serialize_sdf_v2000_data_fields(ingest) == source


def test_charge_and_isotope_property_records_coexist_with_opaque_fields() -> None:
    source = _charged_isotope_source()
    ingest = parse_sdf_v2000_data_fields(source, source_id="markers")
    system = ingest.system

    assert system.atoms[0].formal_charge == -1
    assert system.atoms[0].atom_map == 17
    assert system.atoms[1].isotope_mass_number == 15
    assert ingest.coverage.formal_charge_count == 1
    assert ingest.coverage.isotope_count == 1
    assert ingest.data_fields[0].value_lines == ("opaque",)
    assert serialize_sdf_v2000_data_fields(ingest) == source


def test_crlf_is_accepted_and_canonicalized_to_deterministic_lf() -> None:
    crlf_source = _field_source(
        (("A", ("one", "two")), ("A", ())),
        crlf=True,
    )
    result = round_trip_sdf_v2000_data_fields_source(crlf_source, source_id="crlf")

    assert b"\r" not in result.write_result.payload
    assert result.write_result.payload == _field_source(
        (("A", ("one", "two")), ("A", ()))
    )
    assert result.reparsed_ingest.data_fields == result.source_ingest.data_fields
    assert result.report.input_data_field_projection_sha256 == (
        result.report.reparsed_data_field_projection_sha256
    )
    assert result.report.emitted_source_sha256 == result.report.reemitted_source_sha256


def test_receipt_and_report_are_explicitly_non_authoritative() -> None:
    source = _field_source(
        (
            ("COMMAND", ("run --not-executed",)),
            ("PATH", ("/not/opened",)),
            ("URL", ("https://not-fetched.invalid/",)),
            ("AUTHORITY", ("not-granted",)),
        )
    )
    result = round_trip_sdf_v2000_data_fields_source(source)

    for artifact in (
        result.source_ingest.to_dict(),
        result.write_result.receipt.to_dict(),
        result.report.to_dict(),
    ):
        assert artifact["source_authenticated"] is False
        assert artifact["preparation_ready"] is False
        assert artifact["parameterability_assessed"] is False
        assert artifact["simulation_ready"] is False
        assert artifact["runtime_eligible"] is False
        assert artifact["claim_safe"] is False
        assert artifact["chemistry_interpreted"] is False
        assert artifact["data_field_semantics_interpreted"] is False
        assert artifact["general_sdf_round_trip_evidence_ready"] is False
        assert artifact["all_format_round_trip_evidence_ready"] is False
    assert (
        result.source_ingest.to_dict()["named_field_opaque_projection_preserved"]
        is True
    )
    assert (
        result.write_result.receipt.to_dict()[
            "path_command_url_or_authority_semantics_granted"
        ]
        is False
    )


def test_no_field_opt_in_is_legacy_identical_and_old_golden_is_unchanged() -> None:
    source = ETHANOL.read_bytes()
    legacy = parse_sdf_v2000(source, source_id="tier-beta-ethanol")
    legacy_write = write_sdf_v2000(legacy.system)
    envelope = parse_sdf_v2000_data_fields(source, source_id="tier-beta-ethanol")

    assert SDF_V2000_PARSER_VERSION == "1.5.0"
    assert SDF_V2000_WRITER_VERSION == "1.0.0"
    assert envelope.data_fields == ()
    assert serialize_sdf_v2000_data_fields(envelope) == source
    assert serialize_sdf_v2000_data_fields(envelope) == legacy_write.payload
    assert legacy_write.receipt.output_source_sha256 == (
        "f4835419da95267ad2ef566a121b981011c202c882b071b86d35fc82b683563f"
    )
    assert legacy_write.receipt.receipt_sha256 == (
        "7bf0e7ee2368d700a57f82d4f2fb227a43d76155d3f43e8181d96e242f066855"
    )


def test_no_field_source_without_delimiter_is_allowed_and_canonicalized() -> None:
    source = _base_prefix()
    envelope = parse_sdf_v2000_data_fields(source)

    assert envelope.data_fields == ()
    assert serialize_sdf_v2000_data_fields(envelope) == ETHANOL.read_bytes()


def test_legacy_parser_still_rejects_data_fields() -> None:
    source = _field_source((("A", ("opaque",)),))
    with pytest.raises(SdfV2000ParseError) as exc_info:
        parse_sdf_v2000(source)
    assert exc_info.value.code == "unsupported_data_fields"


@pytest.mark.parametrize(
    ("tail", "code"),
    [
        ([">  <>", "", "$$$$"], "invalid_data_field_header"),
        (["> <A>", "", "$$$$"], "invalid_data_field_header"),
        ([">  <A> (registry)", "", "$$$$"], "invalid_data_field_header"),
        ([">  <A>suffix", "", "$$$$"], "invalid_data_field_header"),
        ([">  <A>", ">  <B>", "", "$$$$"], "nested_data_field_header"),
        ([">  <A>", "opaque", "$$$$"], "missing_data_field_terminator"),
        ([">  <A>", "opaque", ""], "missing_data_field_delimiter"),
        ([">  <A>", "", "$$$$", "next"], "multiple_records"),
        ([">  <A>", "", "$$$$", "$$$$"], "multiple_records"),
    ],
)
def test_malformed_headers_termination_and_record_boundaries_fail_closed(
    tail: list[str], code: str
) -> None:
    _assert_parse_code(_record_with_tail(tail), code)


def test_non_ascii_controls_and_nul_fail_without_echoing_content() -> None:
    ascii_source = _field_source((("A", ("opaque",)),))
    non_ascii = ascii_source.replace(b"opaque", b"PRIVATE-MARKER-\xff")
    control = ascii_source.replace(b"opaque", b"sensitive\tvalue")
    nul = ascii_source.replace(b"opaque", b"sensitive\x00value")

    for source, code in (
        (non_ascii, "invalid_ascii"),
        (control, "invalid_data_field_text"),
        (nul, "invalid_data_field_text"),
    ):
        error = _assert_parse_code(source, code)
        assert error.__cause__ is None
        assert error.__context__ is None
        assert "PRIVATE-MARKER" not in repr(error)


def test_name_value_and_field_count_caps() -> None:
    accepted = parse_sdf_v2000_data_fields(
        _field_source(
            (
                (
                    "N" * MAX_SDF_V2000_DATA_FIELD_NAME_CHARS,
                    ("v" * MAX_SDF_V2000_DATA_FIELD_VALUE_LINE_CHARS,),
                ),
            )
        )
    )
    assert len(accepted.data_fields[0].name) == MAX_SDF_V2000_DATA_FIELD_NAME_CHARS
    assert len(accepted.data_fields[0].value_lines[0]) == (
        MAX_SDF_V2000_DATA_FIELD_VALUE_LINE_CHARS
    )

    _assert_parse_code(
        _field_source((("N" * (MAX_SDF_V2000_DATA_FIELD_NAME_CHARS + 1), ()),)),
        "data_field_name_too_long",
    )
    _assert_parse_code(
        _field_source(
            (("A", ("v" * (MAX_SDF_V2000_DATA_FIELD_VALUE_LINE_CHARS + 1),)),)
        ),
        "data_field_value_line_too_long",
    )
    _assert_parse_code(
        _field_source(
            (
                (
                    "A",
                    tuple("v" for _ in range(MAX_SDF_V2000_DATA_FIELD_VALUE_LINES + 1)),
                ),
            )
        ),
        "too_many_data_field_value_lines",
    )
    _assert_parse_code(
        _field_source(
            tuple((f"F{index}", ()) for index in range(MAX_SDF_V2000_DATA_FIELDS + 1))
        ),
        "too_many_data_fields",
    )


def test_total_value_line_and_payload_caps() -> None:
    fields = tuple(
        (f"F{index}", tuple("v" for _ in range(MAX_SDF_V2000_DATA_FIELD_VALUE_LINES)))
        for index in range(
            MAX_SDF_V2000_DATA_FIELD_TOTAL_VALUE_LINES
            // MAX_SDF_V2000_DATA_FIELD_VALUE_LINES
        )
    ) + (("OVER", ("v",)),)
    _assert_parse_code(_field_source(fields), "too_many_total_data_field_value_lines")

    assert MAX_SDF_V2000_DATA_FIELD_PAYLOAD_BYTES == 384 * 1024
    payload_boundary_fields = tuple(
        (
            f"PAYLOAD{index}",
            tuple(
                "v" * MAX_SDF_V2000_DATA_FIELD_VALUE_LINE_CHARS
                for _ in range(MAX_SDF_V2000_DATA_FIELD_VALUE_LINES)
            ),
        )
        for index in range(30)
    )
    accepted = parse_sdf_v2000_data_fields(_field_source(payload_boundary_fields))
    assert (
        accepted.data_field_payload_byte_count <= MAX_SDF_V2000_DATA_FIELD_PAYLOAD_BYTES
    )
    _assert_parse_code(
        _field_source(
            payload_boundary_fields
            + (
                (
                    "PAYLOAD30",
                    tuple(
                        "v" * MAX_SDF_V2000_DATA_FIELD_VALUE_LINE_CHARS
                        for _ in range(MAX_SDF_V2000_DATA_FIELD_VALUE_LINES)
                    ),
                ),
            )
        ),
        "data_field_payload_too_large",
    )


def test_inherited_full_record_caps_are_enforced_first() -> None:
    _assert_parse_code(b"x" * (2 * 1024 * 1024 + 1), "input_too_large")
    _assert_parse_code(b"x\n" * 4_097, "too_many_lines")
    _assert_parse_code(b"x" * 257, "line_too_long")


def test_stale_projection_and_same_topology_crosswires_are_rejected() -> None:
    stale = parse_sdf_v2000_data_fields(_field_source((("A", ("one",)),)))
    object.__setattr__(stale, "data_field_projection_sha256", "0" * 64)
    with pytest.raises(SdfV2000DataFieldError) as exc_info:
        write_sdf_v2000_data_fields(stale)
    assert exc_info.value.code == "stale_data_field_projection"

    for first_fields, second_fields in (
        ((("A", ("one",)),), (("A", ("two",)),)),
        (
            (("A", ("one",)), ("B", ("two",))),
            (("B", ("two",)), ("A", ("one",))),
        ),
    ):
        first = parse_sdf_v2000_data_fields(_field_source(first_fields))
        second = parse_sdf_v2000_data_fields(_field_source(second_fields))
        object.__setattr__(first, "_data_fields", second.data_fields)
        object.__setattr__(
            first,
            "data_field_projection_sha256",
            second.data_field_projection_sha256,
        )
        object.__setattr__(
            first,
            "record_representable_state_sha256",
            second.record_representable_state_sha256,
        )
        with pytest.raises(SdfV2000DataFieldError) as exc_info:
            write_sdf_v2000_data_fields(first)
        assert exc_info.value.code == "crosswired_data_fields"


def test_round_trip_aggregate_rejects_same_output_crosswired_receipt() -> None:
    fields = (("A", ("opaque",)),)
    lf_result = round_trip_sdf_v2000_data_fields_source(_field_source(fields))
    crlf_result = round_trip_sdf_v2000_data_fields_source(
        _field_source(fields, crlf=True)
    )
    assert lf_result.write_result.payload == crlf_result.write_result.payload
    assert lf_result.write_result.receipt.receipt_sha256 != (
        crlf_result.write_result.receipt.receipt_sha256
    )

    object.__setattr__(lf_result, "write_result", crlf_result.write_result)
    with pytest.raises(ValueError, match="cross-consistent"):
        lf_result.__post_init__()


def test_artifacts_are_factory_only_frozen_and_value_safe_in_repr() -> None:
    secret = "PRIVATE-VALUE-DO-NOT-ECHO"
    source = _field_source((("SECRET", (secret,)),))
    result = round_trip_sdf_v2000_data_fields_source(source)

    for artifact in (
        result.source_ingest.data_fields[0],
        result.source_ingest,
        result.write_result,
        result.report,
        result,
    ):
        assert secret not in repr(artifact)
    assert secret not in json.dumps(result.source_ingest.to_dict(), sort_keys=True)
    assert secret not in json.dumps(
        result.write_result.receipt.to_dict(), sort_keys=True
    )
    assert secret not in json.dumps(result.report.to_dict(), sort_keys=True)

    leaking_error = _record_with_tail([">  <SECRET>", secret, "$$$$"])
    error = _assert_parse_code(leaking_error, "missing_data_field_terminator")
    assert secret not in str(error)
    assert secret not in repr(error)

    with pytest.raises(TypeError, match="factory-only"):
        SdfV2000DataField(name="A", value_lines=())
    with pytest.raises(TypeError):
        SdfV2000DataFieldIngestResult()  # type: ignore[call-arg]
    with pytest.raises(TypeError, match="factory-only"):
        SdfV2000DataFieldWriteReceipt()
    with pytest.raises(TypeError, match="factory-only"):
        SdfV2000DataFieldWriteResult(payload=b"", receipt=None)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="factory-only"):
        SdfV2000DataFieldRoundTripReport()
    with pytest.raises(TypeError):
        SdfV2000DataFieldRoundTripResult()  # type: ignore[call-arg]
    with pytest.raises(FrozenInstanceError):
        result.source_ingest.data_fields[0].name = "OTHER"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        result.write_result.receipt.output_byte_count = 0  # type: ignore[misc]
