from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from typing import Any

import pytest

from betelgeuze_engine_v2.contracts import ALL_ATOM_SCHEMA_ID
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
    SDF_V2000_DATA_FIELD_WRITER_VERSION,
    SDF_V2000_DATA_FIELD_WRITE_RECEIPT_SCHEMA_ID,
    SDF_V2000_PARSER_VERSION,
    SDF_V2000_WRITER_VERSION,
    SdfV2000DataFieldError,
    SdfV2000ParseError,
    parse_sdf_v2000,
    parse_sdf_v2000_data_fields,
    round_trip_sdf_v2000_data_fields_source,
    round_trip_sdf_v2000_source,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = (
    REPOSITORY_ROOT / "config" / "independent_engine_v2_v2_1_sdf_data_field_corpus.json"
)
FIXTURE_ROOT = REPOSITORY_ROOT / "tests" / "fixtures" / "v2_1_sdf_data_fields"
CORPUS_SCHEMA_ID = "betelgeuze.v2_1_sdf_v2000_data_field_corpus/1.0.0"
CORPUS_ID = "v2_1_strict_sdf_v2000_simple_named_opaque_data_field_envelope_v1"
PAYLOAD_HASH_POLICY_ID = "sha256_canonical_json_without_payload_sha256/1.0.0"
EXPECTED_PAYLOAD_SHA256 = (
    "b507b5e19addb804862614bee2944d533944ecb1673448a4971fa469c7b536fc"
)
PROJECTION_SCOPE = "ordered_opaque_ascii_simple_named_sd_data_items_only"

_LOWERCASE_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_CASE_ID = re.compile(r"^[a-z][a-z0-9_]*$")
_TOP_LEVEL_KEYS = {
    "schema_id",
    "corpus_id",
    "manifest_payload_hash_policy_id",
    "payload_sha256",
    "contracts",
    "claim_boundary",
    "cases",
}
_CASE_KEYS = {
    "case_id",
    "lane",
    "source",
    "source_id",
    "source_sha256",
    "expected",
}
_ROUND_TRIP_EXPECTED_KEYS = {
    "base_mol_block_source_sha256",
    "base_representable_state_sha256",
    "base_system_snapshot_sha256",
    "base_topology_sha256",
    "canonical_base_mol_block_sha256",
    "data_field_count",
    "data_field_payload_byte_count",
    "data_field_projection_sha256",
    "data_field_value_line_count",
    "full_source_sha256",
    "output_byte_count",
    "output_equals_input",
    "output_source_sha256",
    "record_representable_state_sha256",
    "round_trip_report_sha256",
    "write_receipt_sha256",
}
_FALSE_GATES = (
    "data_field_semantics_interpreted",
    "chemistry_interpreted",
    "source_authenticated",
    "preparation_ready",
    "parameterability_assessed",
    "simulation_ready",
    "runtime_eligible",
    "claim_safe",
    "general_sdf_round_trip_evidence_ready",
    "all_format_round_trip_evidence_ready",
)
_ROUND_TRIP_CASE_IDS = {
    "charge_isotope_field",
    "empty_field",
    "ethanol_no_fields",
    "ordered_duplicate_authority_fields",
    "single_field",
}
_FAILURE_CODES = {
    "content_after_delimiter": "multiple_records",
    "empty_name": "invalid_data_field_header",
    "header_suffix": "invalid_data_field_header",
    "missing_blank_terminator": "missing_data_field_terminator",
    "missing_delimiter": "missing_data_field_delimiter",
    "nested_header": "nested_data_field_header",
    "non_ascii_value": "invalid_ascii",
    "unsupported_registry_header": "invalid_data_field_header",
}


class CorpusManifestError(ValueError):
    pass


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CorpusManifestError("duplicate manifest key")
        result[key] = value
    return result


def _load_manifest() -> dict[str, Any]:
    try:
        value = json.loads(
            MANIFEST_PATH.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=lambda _token: (_ for _ in ()).throw(
                CorpusManifestError("nonstandard JSON constant")
            ),
        )
    except json.JSONDecodeError as exc:
        raise CorpusManifestError("manifest must be strict JSON") from exc
    if type(value) is not dict:
        raise CorpusManifestError("manifest root must be an object")
    return value


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _payload_sha256(document: dict[str, Any]) -> str:
    payload = deepcopy(document)
    payload.pop("payload_sha256")
    return hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()


def _resolve_fixture(source: dict[str, Any]) -> Path:
    assert set(source) == {"kind", "path"}
    assert source["kind"] == "fixture"
    relative = source["path"]
    assert type(relative) is str
    pure = PurePosixPath(relative)
    assert not pure.is_absolute()
    assert ".." not in pure.parts
    assert pure.parts[:2] == ("tests", "fixtures")
    path = REPOSITORY_ROOT.joinpath(*pure.parts)
    assert path.is_file()
    return path


def _round_trip_document(case: dict[str, Any]) -> tuple[dict[str, Any], Any]:
    path = _resolve_fixture(case["source"])
    source = path.read_bytes()
    assert hashlib.sha256(source).hexdigest() == case["source_sha256"]
    result = round_trip_sdf_v2000_data_fields_source(
        source, source_id=case["source_id"]
    )
    ingest = result.source_ingest
    receipt = result.write_result.receipt
    return (
        {
            "base_mol_block_source_sha256": ingest.base_mol_block_source_sha256,
            "base_representable_state_sha256": (ingest.base_representable_state_sha256),
            "base_system_snapshot_sha256": ingest.base_system_snapshot_sha256,
            "base_topology_sha256": ingest.base_topology_sha256,
            "canonical_base_mol_block_sha256": (ingest.canonical_base_mol_block_sha256),
            "data_field_count": ingest.data_field_count,
            "data_field_payload_byte_count": ingest.data_field_payload_byte_count,
            "data_field_projection_sha256": ingest.data_field_projection_sha256,
            "data_field_value_line_count": ingest.data_field_value_line_count,
            "full_source_sha256": ingest.full_source_sha256,
            "output_byte_count": receipt.output_byte_count,
            "output_equals_input": result.write_result.payload == source,
            "output_source_sha256": receipt.output_source_sha256,
            "record_representable_state_sha256": (
                ingest.record_representable_state_sha256
            ),
            "round_trip_report_sha256": result.report.report_sha256,
            "write_receipt_sha256": receipt.receipt_sha256,
        },
        result,
    )


def test_manifest_schema_contract_payload_hash_and_inventory_are_exact() -> None:
    document = _load_manifest()
    assert set(document) == _TOP_LEVEL_KEYS
    assert document["schema_id"] == CORPUS_SCHEMA_ID
    assert document["corpus_id"] == CORPUS_ID
    assert document["manifest_payload_hash_policy_id"] == PAYLOAD_HASH_POLICY_ID
    assert document["payload_sha256"] == EXPECTED_PAYLOAD_SHA256
    assert _payload_sha256(document) == EXPECTED_PAYLOAD_SHA256

    contracts = document["contracts"]
    assert contracts == {
        "all_atom_schema_id": ALL_ATOM_SCHEMA_ID,
        "base_sdf_v2000_parser_version": SDF_V2000_PARSER_VERSION,
        "base_sdf_v2000_writer_version": SDF_V2000_WRITER_VERSION,
        "envelope_version": SDF_V2000_DATA_FIELD_ENVELOPE_VERSION,
        "envelope_parser_version": SDF_V2000_DATA_FIELD_PARSER_VERSION,
        "envelope_writer_version": SDF_V2000_DATA_FIELD_WRITER_VERSION,
        "parser_name": SDF_V2000_DATA_FIELD_PARSER_NAME,
        "profile_id": SDF_V2000_DATA_FIELD_PROFILE_ID,
        "data_field_projection_schema_id": (SDF_V2000_DATA_FIELD_PROJECTION_SCHEMA_ID),
        "record_representable_state_schema_id": (
            SDF_V2000_DATA_FIELD_RECORD_STATE_SCHEMA_ID
        ),
        "write_receipt_schema_id": SDF_V2000_DATA_FIELD_WRITE_RECEIPT_SCHEMA_ID,
        "round_trip_report_schema_id": (
            SDF_V2000_DATA_FIELD_ROUND_TRIP_REPORT_SCHEMA_ID
        ),
        "projection_scope": PROJECTION_SCOPE,
        "limits": {
            "max_fields": MAX_SDF_V2000_DATA_FIELDS,
            "max_field_name_chars": MAX_SDF_V2000_DATA_FIELD_NAME_CHARS,
            "max_value_line_chars": MAX_SDF_V2000_DATA_FIELD_VALUE_LINE_CHARS,
            "max_value_lines_per_field": MAX_SDF_V2000_DATA_FIELD_VALUE_LINES,
            "max_total_value_lines": (MAX_SDF_V2000_DATA_FIELD_TOTAL_VALUE_LINES),
            "max_data_field_payload_bytes": (MAX_SDF_V2000_DATA_FIELD_PAYLOAD_BYTES),
            "inherited_max_full_record_bytes": 2 * 1024 * 1024,
            "inherited_max_full_record_lines": 4096,
            "inherited_max_line_chars": 256,
        },
    }

    cases = document["cases"]
    assert type(cases) is list and len(cases) == 13
    case_ids = [case["case_id"] for case in cases]
    assert case_ids == sorted(case_ids)
    assert len(case_ids) == len(set(case_ids))
    assert set(case_ids) == _ROUND_TRIP_CASE_IDS | set(_FAILURE_CODES)
    assert sum(case["lane"] == "round_trip" for case in cases) == 5
    assert sum(case["lane"] == "parse_failure" for case in cases) == 8


def test_manifest_claim_boundary_is_exactly_nonpromoting() -> None:
    boundary = _load_manifest()["claim_boundary"]
    assert boundary == {
        "positive_true_fields": ["named_field_opaque_projection_preserved"],
        "always_false_fields": list(_FALSE_GATES),
        "field_values_are_chemistry_role_path_command_url_or_authority_inputs": False,
        "base_parser_default_changed": False,
        "v2_1_complete": False,
    }


def test_case_shapes_hashes_and_dedicated_fixture_closure_are_exact() -> None:
    referenced_dedicated: set[Path] = set()
    for case in _load_manifest()["cases"]:
        assert set(case) == _CASE_KEYS
        assert type(case["case_id"]) is str
        assert _CASE_ID.fullmatch(case["case_id"])
        assert case["lane"] in {"round_trip", "parse_failure"}
        assert type(case["source_id"]) is str and case["source_id"]
        assert _LOWERCASE_SHA256.fullmatch(case["source_sha256"])
        path = _resolve_fixture(case["source"])
        assert hashlib.sha256(path.read_bytes()).hexdigest() == case["source_sha256"]
        if FIXTURE_ROOT in path.parents:
            referenced_dedicated.add(path.resolve())
        if case["lane"] == "round_trip":
            assert set(case["expected"]) == _ROUND_TRIP_EXPECTED_KEYS
            for key, value in case["expected"].items():
                if key.endswith("sha256"):
                    assert type(value) is str and _LOWERCASE_SHA256.fullmatch(value)
        else:
            assert case["expected"] == {"error_code": _FAILURE_CODES[case["case_id"]]}
    actual = {path.resolve() for path in FIXTURE_ROOT.glob("*.sdf")}
    assert referenced_dedicated == actual


@pytest.mark.parametrize("case_id", sorted(_ROUND_TRIP_CASE_IDS))
def test_round_trip_rows_replay_exact_digests_and_keep_authority_false(
    case_id: str,
) -> None:
    case = next(row for row in _load_manifest()["cases"] if row["case_id"] == case_id)
    actual, result = _round_trip_document(case)
    assert actual == case["expected"]

    summaries = (
        result.source_ingest.to_dict(),
        result.write_result.receipt.to_dict(),
        result.report.to_dict(),
    )
    assert summaries[0]["named_field_opaque_projection_preserved"] is True
    assert summaries[1]["named_field_opaque_projection_preserved"] is True
    assert summaries[2]["named_field_opaque_projection_sha256_equal"] is True
    for summary in summaries:
        for field in _FALSE_GATES:
            assert summary[field] is False
    for summary in summaries[1:]:
        assert summary["path_command_url_or_authority_semantics_granted"] is False


@pytest.mark.parametrize("case_id", sorted(_FAILURE_CODES))
def test_failure_rows_replay_exact_typed_parse_failures(case_id: str) -> None:
    case = next(row for row in _load_manifest()["cases"] if row["case_id"] == case_id)
    path = _resolve_fixture(case["source"])
    source = path.read_bytes()
    with pytest.raises(SdfV2000DataFieldError) as exc_info:
        parse_sdf_v2000_data_fields(source, source_id=case["source_id"])
    assert exc_info.value.code == case["expected"]["error_code"]
    assert source.decode("utf-8", errors="ignore") not in str(exc_info.value)


def test_order_duplicates_empty_values_and_authority_like_names_stay_opaque() -> None:
    cases = {case["case_id"]: case for case in _load_manifest()["cases"]}
    ordered = parse_sdf_v2000_data_fields(
        _resolve_fixture(
            cases["ordered_duplicate_authority_fields"]["source"]
        ).read_bytes(),
        source_id="ordered_duplicate_authority_fields",
    )
    assert [item.name for item in ordered.data_fields] == [
        "TAG",
        "TAG",
        "PREPARATION_READY",
        "SMILES",
    ]
    assert ordered.data_fields[0].value_lines == ("first", "second line")
    assert ordered.data_fields[1].value_lines == ("duplicate",)
    assert ordered.data_fields[2].value_lines == ("true",)
    assert ordered.data_fields[3].value_lines == ("C1=CC=CC=C1",)
    for field in _FALSE_GATES:
        assert ordered.to_dict()[field] is False

    empty = parse_sdf_v2000_data_fields(
        _resolve_fixture(cases["empty_field"]["source"]).read_bytes(),
        source_id="empty_field",
    )
    assert empty.data_fields[0].value_lines == ()

    charged = parse_sdf_v2000_data_fields(
        _resolve_fixture(cases["charge_isotope_field"]["source"]).read_bytes(),
        source_id="charge_isotope_field",
    )
    assert charged.system.atoms[0].formal_charge == -1
    assert charged.system.atoms[0].isotope_mass_number == 13


def test_legacy_default_rejects_fields_and_no_field_golden_is_unchanged() -> None:
    cases = {case["case_id"]: case for case in _load_manifest()["cases"]}
    for case_id in (
        "charge_isotope_field",
        "empty_field",
        "ordered_duplicate_authority_fields",
        "single_field",
    ):
        source = _resolve_fixture(cases[case_id]["source"]).read_bytes()
        with pytest.raises(SdfV2000ParseError) as exc_info:
            parse_sdf_v2000(source, source_id=case_id)
        assert exc_info.value.code == "unsupported_data_fields"

    ethanol = _resolve_fixture(cases["ethanol_no_fields"]["source"]).read_bytes()
    legacy = round_trip_sdf_v2000_source(ethanol, source_id="tier-beta-ethanol")
    assert legacy.write_result.payload == ethanol
    assert legacy.write_result.receipt.receipt_sha256 == (
        "7bf0e7ee2368d700a57f82d4f2fb227a43d76155d3f43e8181d96e242f066855"
    )
    assert legacy.report.report_sha256 == (
        "4d458d0a202c1da8578ba2db8fd129aad1c0dfc4261c395862e23d7c9f59fbfa"
    )
