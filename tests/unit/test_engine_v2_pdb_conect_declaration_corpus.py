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
    CANONICAL_TOPOLOGY_SCHEMA_ID,
    MAX_PDB_CONECT_DECLARATION_INPUT_BYTES,
    MAX_PDB_CONECT_DECLARATION_LINE_COUNT,
    MAX_PDB_CONECT_DECLARATION_OUTPUT_BYTES,
    MAX_PDB_CONECT_DECLARATION_OUTPUT_LINE_CHARS,
    MAX_PDB_CONECT_DECLARATION_OUTPUT_LINES,
    MAX_PDB_CONECT_DECLARATION_PROJECTION_BYTES,
    MAX_PDB_CONECT_DECLARATION_RECORDS,
    MAX_PDB_CONECT_DECLARATION_SOURCE_ID_BYTES,
    MAX_PDB_CONECT_DECLARATION_TARGET_OCCURRENCES,
    PDB_CONECT_DECLARATION_ENVELOPE_VERSION,
    PDB_CONECT_DECLARATION_PARSER_NAME,
    PDB_CONECT_DECLARATION_PARSER_VERSION,
    PDB_CONECT_DECLARATION_PROFILE_ID,
    PDB_CONECT_DECLARATION_PROJECTION_SCHEMA_ID,
    PDB_CONECT_DECLARATION_PROJECTION_SCOPE,
    PDB_CONECT_DECLARATION_RECORD_STATE_SCHEMA_ID,
    PDB_CONECT_DECLARATION_ROUND_TRIP_REPORT_SCHEMA_ID,
    PDB_CONECT_DECLARATION_SOURCE_BINDING_SCHEMA_ID,
    PDB_CONECT_DECLARATION_WRITER_VERSION,
    PDB_CONECT_DECLARATION_WRITE_RECEIPT_SCHEMA_ID,
    PDB_PARSER_VERSION,
    PDB_REPRESENTABLE_STATE_SCHEMA_ID,
    PDB_WRITER_VERSION,
    PdbConectDeclarationError,
    StructureParseError,
    parse_pdb,
    parse_pdb_conect_declaration,
    round_trip_pdb_conect_declaration_source,
    serialize_pdb,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = (
    REPOSITORY_ROOT
    / "config"
    / "independent_engine_v2_v2_1_pdb_conect_declaration_corpus.json"
)
FIXTURE_ROOT = REPOSITORY_ROOT / "tests" / "fixtures" / "v2_1_pdb_conect_declaration"
CORPUS_SCHEMA_ID = "betelgeuze.v2_1_pdb_conect_declaration_corpus/1.0.0"
CORPUS_ID = "v2_1_strict_pdb_ordered_conect_source_declaration_envelope_v1"
PAYLOAD_HASH_POLICY_ID = "sha256_canonical_json_without_payload_sha256/1.0.0"
EXPECTED_PAYLOAD_SHA256 = (
    "c6346f7b046d157a70fb1629dfe3e7f3c13a4b9b079474961a613ec436c38a75"
)
MAX_MANIFEST_BYTES = 256 * 1024
MAX_JSON_DEPTH = 10
MAX_JSON_CONTAINER_ITEMS = 128
MAX_JSON_STRING_UTF8_BYTES = 8 * 1024

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
    "base_writer_receipt_sha256",
    "canonical_carrier_source_sha256",
    "carrier_atom_count",
    "carrier_bond_count",
    "carrier_model_count",
    "carrier_model_ids",
    "carrier_representable_state_sha256",
    "carrier_snapshot_sha256",
    "carrier_source_sha256",
    "carrier_topology_sha256",
    "conect_record_count",
    "declaration_projection_byte_count",
    "declaration_projection_sha256",
    "full_source_sha256",
    "normalized_source_sha256",
    "ordered_conect_declaration_round_trip_preserved",
    "output_byte_count",
    "output_equals_input",
    "output_line_count",
    "output_source_sha256",
    "record_state_sha256",
    "round_trip_report_sha256",
    "second_emission_byte_stable",
    "source_binding_sha256",
    "source_id_sha256",
    "target_occurrence_count",
    "write_receipt_sha256",
}
_FALSE_GATES = (
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
    "bare_system_preserves_declaration",
    "general_pdb_round_trip_evidence_ready",
    "all_format_round_trip_evidence_ready",
)
_ROUND_TRIP_CASE_IDS = {
    "contextual_metal_bidirectional",
    "explicit_model1_outside_declaration",
    "four_target_boundary",
    "ordered_duplicate_slots",
    "single_directed_declaration",
}
_FAILURE_CODES = {
    "failure_inside_model": "conect_inside_model",
    "failure_interior_target_gap": "invalid_conect",
    "failure_model_id2": "unsupported_model_profile",
    "failure_multimodel": "unsupported_model_profile",
    "failure_no_conect": "missing_conect_declaration",
    "failure_noncontiguous_before_ter": "noncontiguous_conect_suffix",
    "failure_reserved_columns": "invalid_conect",
    "failure_self_reference": "self_reference",
    "failure_unknown_source": "unknown_atom_reference",
    "failure_unknown_target": "unknown_atom_reference",
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


def _reject_json_number(token: str) -> Any:
    raise CorpusManifestError(f"unsupported JSON number {token!r}")


def _assert_bounded_json(value: Any, *, depth: int = 0) -> int:
    if depth > MAX_JSON_DEPTH:
        raise CorpusManifestError("manifest nesting exceeds the fixed depth limit")
    if type(value) is dict:
        if len(value) > MAX_JSON_CONTAINER_ITEMS:
            raise CorpusManifestError("manifest object exceeds the fixed item limit")
        total = 1
        for key, item in value.items():
            if type(key) is not str:
                raise CorpusManifestError("manifest object keys must be strings")
            if len(key.encode("utf-8")) > MAX_JSON_STRING_UTF8_BYTES:
                raise CorpusManifestError("manifest key exceeds the fixed byte limit")
            total += _assert_bounded_json(item, depth=depth + 1)
        return total
    if type(value) is list:
        if len(value) > MAX_JSON_CONTAINER_ITEMS:
            raise CorpusManifestError("manifest list exceeds the fixed item limit")
        return 1 + sum(_assert_bounded_json(item, depth=depth + 1) for item in value)
    if type(value) is str:
        if len(value.encode("utf-8")) > MAX_JSON_STRING_UTF8_BYTES:
            raise CorpusManifestError("manifest string exceeds the fixed byte limit")
        return 1
    if value is None or type(value) in {bool, int}:
        if type(value) is int and not -(2**63) <= value < 2**63:
            raise CorpusManifestError("manifest integer exceeds signed 64-bit range")
        return 1
    raise CorpusManifestError(f"unsupported manifest value type {type(value).__name__}")


def _load_manifest() -> dict[str, Any]:
    raw = MANIFEST_PATH.read_bytes()
    if not raw or len(raw) > MAX_MANIFEST_BYTES:
        raise CorpusManifestError("manifest exceeds the fixed byte envelope")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CorpusManifestError("manifest must be UTF-8") from exc
    if not text.endswith("\n") or "\r" in text:
        raise CorpusManifestError("manifest must use one final LF and no CR")
    try:
        value = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_float=_reject_json_number,
            parse_constant=_reject_json_number,
        )
    except json.JSONDecodeError as exc:
        raise CorpusManifestError("manifest must be strict JSON") from exc
    if type(value) is not dict:
        raise CorpusManifestError("manifest root must be an object")
    node_count = _assert_bounded_json(value)
    if node_count > 4096:
        raise CorpusManifestError("manifest exceeds the fixed JSON node limit")
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
    assert pure.parts[:3] == (
        "tests",
        "fixtures",
        "v2_1_pdb_conect_declaration",
    )
    assert len(pure.parts) == 4 and pure.suffix == ".pdb"
    path = REPOSITORY_ROOT.joinpath(*pure.parts)
    assert not path.is_symlink()
    resolved_root = FIXTURE_ROOT.resolve(strict=True)
    resolved = path.resolve(strict=True)
    assert resolved.parent == resolved_root
    assert resolved.is_file()
    return resolved


def _round_trip_document(case: dict[str, Any]) -> tuple[dict[str, Any], Any]:
    path = _resolve_fixture(case["source"])
    source = path.read_bytes()
    assert hashlib.sha256(source).hexdigest() == case["source_sha256"]
    result = round_trip_pdb_conect_declaration_source(
        source, source_id=case["source_id"]
    )
    ingest = result.source_ingest
    ingest_document = ingest.to_dict()
    receipt = result.write_result.receipt
    report = result.report
    payload = result.write_result.payload
    return (
        {
            "base_writer_receipt_sha256": ingest_document["base_writer_receipt_sha256"],
            "canonical_carrier_source_sha256": (ingest.canonical_carrier_source_sha256),
            "carrier_atom_count": ingest.system.atom_count,
            "carrier_bond_count": len(ingest.system.bonds),
            "carrier_model_count": ingest.system.model_count,
            "carrier_model_ids": ingest_document["carrier_model_ids"],
            "carrier_representable_state_sha256": (
                ingest.carrier_representable_state_sha256
            ),
            "carrier_snapshot_sha256": ingest.carrier_snapshot_sha256,
            "carrier_source_sha256": ingest.carrier_source_sha256,
            "carrier_topology_sha256": ingest.carrier_topology_sha256,
            "conect_record_count": ingest.conect_record_count,
            "declaration_projection_byte_count": (
                ingest.declaration_projection_byte_count
            ),
            "declaration_projection_sha256": (ingest.declaration_projection_sha256),
            "full_source_sha256": ingest.full_source_sha256,
            "normalized_source_sha256": ingest.normalized_source_sha256,
            "ordered_conect_declaration_round_trip_preserved": report.to_dict()[
                "ordered_conect_declaration_round_trip_preserved"
            ],
            "output_byte_count": len(payload),
            "output_equals_input": payload == source,
            "output_line_count": len(payload.splitlines()),
            "output_source_sha256": receipt.to_dict()["output_source_sha256"],
            "record_state_sha256": ingest.record_state_sha256,
            "round_trip_report_sha256": report.report_sha256,
            "second_emission_byte_stable": (
                payload == result.reemitted_write_result.payload
            ),
            "source_binding_sha256": ingest.source_binding_sha256,
            "source_id_sha256": ingest.source_id_sha256,
            "target_occurrence_count": ingest.target_occurrence_count,
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

    assert document["contracts"] == {
        "all_atom_schema_id": ALL_ATOM_SCHEMA_ID,
        "canonical_topology_schema_id": CANONICAL_TOPOLOGY_SCHEMA_ID,
        "base_pdb_parser_version": PDB_PARSER_VERSION,
        "base_pdb_writer_version": PDB_WRITER_VERSION,
        "base_pdb_representable_state_schema_id": (PDB_REPRESENTABLE_STATE_SCHEMA_ID),
        "envelope_version": PDB_CONECT_DECLARATION_ENVELOPE_VERSION,
        "envelope_parser_version": PDB_CONECT_DECLARATION_PARSER_VERSION,
        "envelope_writer_version": PDB_CONECT_DECLARATION_WRITER_VERSION,
        "parser_name": PDB_CONECT_DECLARATION_PARSER_NAME,
        "profile_id": PDB_CONECT_DECLARATION_PROFILE_ID,
        "projection_scope": PDB_CONECT_DECLARATION_PROJECTION_SCOPE,
        "declaration_projection_schema_id": (
            PDB_CONECT_DECLARATION_PROJECTION_SCHEMA_ID
        ),
        "record_state_schema_id": PDB_CONECT_DECLARATION_RECORD_STATE_SCHEMA_ID,
        "source_binding_schema_id": (PDB_CONECT_DECLARATION_SOURCE_BINDING_SCHEMA_ID),
        "write_receipt_schema_id": (PDB_CONECT_DECLARATION_WRITE_RECEIPT_SCHEMA_ID),
        "round_trip_report_schema_id": (
            PDB_CONECT_DECLARATION_ROUND_TRIP_REPORT_SCHEMA_ID
        ),
        "model_profile": "exactly_one_model_id1_implicit_or_explicit_source",
        "canonical_model_emission": "implicit_single_model_id1",
        "conect_placement": (
            "one_contiguous_suffix_outside_model_immediately_before_end"
        ),
        "target_slot_profile": "one_to_four_left_packed_positive_i5_occurrences",
        "carrier_bond_policy": "always_empty_and_not_derived_from_conect",
        "limits": {
            "max_input_bytes": MAX_PDB_CONECT_DECLARATION_INPUT_BYTES,
            "max_source_id_utf8_bytes": (MAX_PDB_CONECT_DECLARATION_SOURCE_ID_BYTES),
            "max_input_lines": MAX_PDB_CONECT_DECLARATION_LINE_COUNT,
            "max_conect_records": MAX_PDB_CONECT_DECLARATION_RECORDS,
            "max_target_occurrences": (MAX_PDB_CONECT_DECLARATION_TARGET_OCCURRENCES),
            "max_projection_bytes": (MAX_PDB_CONECT_DECLARATION_PROJECTION_BYTES),
            "max_output_bytes": MAX_PDB_CONECT_DECLARATION_OUTPUT_BYTES,
            "max_output_lines": MAX_PDB_CONECT_DECLARATION_OUTPUT_LINES,
            "canonical_output_line_characters": (
                MAX_PDB_CONECT_DECLARATION_OUTPUT_LINE_CHARS
            ),
        },
    }

    cases = document["cases"]
    assert type(cases) is list and len(cases) == 15
    case_ids = [case["case_id"] for case in cases]
    assert case_ids == sorted(case_ids)
    assert len(case_ids) == len(set(case_ids))
    assert set(case_ids) == _ROUND_TRIP_CASE_IDS | set(_FAILURE_CODES)
    assert sum(case["lane"] == "round_trip" for case in cases) == 5
    assert sum(case["lane"] == "parse_failure" for case in cases) == 10


def test_manifest_claim_boundary_is_exactly_nonpromoting() -> None:
    assert _load_manifest()["claim_boundary"] == {
        "positive_true_fields": [
            "ordered_declaration_projection_preserved",
            "ordered_conect_declaration_round_trip_preserved",
        ],
        "always_false_fields": list(_FALSE_GATES),
        "base_parser_default_changed": False,
        "bare_system_preserves_declaration": False,
        "canonical_bond_created_from_conect": False,
        "direction_duplicates_or_row_grouping_are_bond_semantics": False,
        "general_pdb_round_trip_evidence_ready": False,
        "all_format_round_trip_evidence_ready": False,
        "v2_1_complete": False,
    }


def test_strict_json_duplicate_rejection_and_fixture_confinement_are_live() -> None:
    with pytest.raises(CorpusManifestError, match="duplicate manifest key"):
        json.loads('{"key":1,"key":2}', object_pairs_hook=_reject_duplicate_keys)
    with pytest.raises(CorpusManifestError, match="unsupported JSON number"):
        json.loads('{"value":1.5}', parse_float=_reject_json_number)
    with pytest.raises(AssertionError):
        _resolve_fixture(
            {
                "kind": "fixture",
                "path": "tests/fixtures/v2_1_pdb_conect_declaration/../escape.pdb",
            }
        )


def test_case_shapes_hashes_and_dedicated_fixture_closure_are_exact() -> None:
    referenced: set[Path] = set()
    for case in _load_manifest()["cases"]:
        assert set(case) == _CASE_KEYS
        assert type(case["case_id"]) is str and _CASE_ID.fullmatch(case["case_id"])
        assert case["lane"] in {"round_trip", "parse_failure"}
        assert type(case["source_id"]) is str and case["source_id"] == case["case_id"]
        assert type(case["source_sha256"]) is str
        assert _LOWERCASE_SHA256.fullmatch(case["source_sha256"])
        path = _resolve_fixture(case["source"])
        assert hashlib.sha256(path.read_bytes()).hexdigest() == case["source_sha256"]
        referenced.add(path)
        if case["lane"] == "round_trip":
            expected = case["expected"]
            assert set(expected) == _ROUND_TRIP_EXPECTED_KEYS
            for key, value in expected.items():
                if key.endswith("sha256"):
                    assert type(value) is str and _LOWERCASE_SHA256.fullmatch(value)
            assert expected["carrier_bond_count"] == 0
            assert expected["carrier_model_count"] == 1
            assert expected["carrier_model_ids"] == [1]
            assert expected["ordered_conect_declaration_round_trip_preserved"] is True
            assert expected["second_emission_byte_stable"] is True
        else:
            assert case["expected"] == {"error_code": _FAILURE_CODES[case["case_id"]]}
    actual = {path.resolve() for path in FIXTURE_ROOT.glob("*.pdb")}
    assert referenced == actual


@pytest.mark.parametrize("case_id", sorted(_ROUND_TRIP_CASE_IDS))
def test_round_trip_rows_replay_exact_artifact_chain_and_nonpromotion(
    case_id: str,
) -> None:
    case = next(row for row in _load_manifest()["cases"] if row["case_id"] == case_id)
    actual, result = _round_trip_document(case)
    assert actual == case["expected"]

    ingest_document = result.source_ingest.to_dict()
    receipt_document = result.write_result.receipt.to_dict()
    report_document = result.report.to_dict()
    for document in (ingest_document, receipt_document, report_document):
        for field in _FALSE_GATES:
            assert document[field] is False
    assert ingest_document["ordered_declaration_projection_preserved"] is True
    assert receipt_document["ordered_declaration_projection_preserved"] is True
    for field in (
        "declaration_projection_equal",
        "carrier_topology_equal",
        "carrier_representable_state_equal",
        "canonical_carrier_source_equal",
        "record_state_equal",
        "source_id_equal",
        "emitted_source_reparsed_exact",
        "write_receipt_source_bound",
        "reemitted_receipt_reparsed_bound",
        "second_emission_byte_stable",
        "carrier_bond_count_zero",
        "ordered_conect_declaration_round_trip_preserved",
    ):
        assert report_document[field] is True

    assert result.source_ingest.system.bonds == ()
    assert result.reparsed_ingest.system.bonds == ()
    bare_payload = serialize_pdb(result.source_ingest.system)
    assert b"CONECT" not in bare_payload
    assert result.write_result.payload == result.reemitted_write_result.payload
    assert all(
        len(line) == MAX_PDB_CONECT_DECLARATION_OUTPUT_LINE_CHARS
        for line in result.write_result.payload.splitlines()
    )


@pytest.mark.parametrize("case_id", sorted(_FAILURE_CODES))
def test_failure_rows_replay_exact_typed_failures(case_id: str) -> None:
    case = next(row for row in _load_manifest()["cases"] if row["case_id"] == case_id)
    source = _resolve_fixture(case["source"]).read_bytes()
    with pytest.raises(PdbConectDeclarationError) as exc_info:
        parse_pdb_conect_declaration(source, source_id=case["source_id"])
    assert exc_info.value.code == case["expected"]["error_code"]
    assert source.decode("ascii", errors="ignore") not in str(exc_info.value)


def test_order_direction_duplicates_slots_and_base_parser_boundary_are_exact() -> None:
    cases = {case["case_id"]: case for case in _load_manifest()["cases"]}

    duplicate = parse_pdb_conect_declaration(
        _resolve_fixture(cases["ordered_duplicate_slots"]["source"]).read_bytes(),
        source_id="ordered_duplicate_slots",
    )
    assert [
        (row.ordinal, row.source_serial, row.target_serials) for row in duplicate.rows
    ] == [
        (0, 1, (2, 2, 3)),
        (1, 3, (1,)),
        (2, 2, (1, 1)),
    ]
    metal = parse_pdb_conect_declaration(
        _resolve_fixture(
            cases["contextual_metal_bidirectional"]["source"]
        ).read_bytes(),
        source_id="contextual_metal_bidirectional",
    )
    assert [(row.source_serial, row.target_serials) for row in metal.rows] == [
        (1, (2,)),
        (2, (1,)),
    ]
    boundary = parse_pdb_conect_declaration(
        _resolve_fixture(cases["four_target_boundary"]["source"]).read_bytes(),
        source_id="four_target_boundary",
    )
    assert boundary.rows[0].target_serials == (2, 3, 4, 5)

    for case_id in sorted(_ROUND_TRIP_CASE_IDS):
        source = _resolve_fixture(cases[case_id]["source"]).read_bytes()
        with pytest.raises(StructureParseError) as exc_info:
            parse_pdb(source, source_id=case_id)
        assert exc_info.value.code == "unsupported_contextual_conect_semantics"


def test_explicit_model1_normalizes_to_implicit_and_suffix_stays_canonical() -> None:
    case = next(
        row
        for row in _load_manifest()["cases"]
        if row["case_id"] == "explicit_model1_outside_declaration"
    )
    result = round_trip_pdb_conect_declaration_source(
        _resolve_fixture(case["source"]).read_bytes(),
        source_id=case["source_id"],
    )
    payload = result.write_result.payload
    lines = payload.splitlines()
    assert b"MODEL" not in payload and b"ENDMDL" not in payload
    assert lines[-2].startswith(b"CONECT")
    assert lines[-1] == b"END".ljust(MAX_PDB_CONECT_DECLARATION_OUTPUT_LINE_CHARS)
    assert result.source_ingest.to_dict()["carrier_model_ids"] == [1]
    assert result.reparsed_ingest.to_dict()["carrier_model_ids"] == [1]
