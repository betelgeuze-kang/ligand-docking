from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from typing import Any

import pytest

from betelgeuze_engine_v2.molecular import (
    MMCIF_ASSEMBLY_ENVELOPE_VERSION,
    MMCIF_ASSEMBLY_PARSER_VERSION,
    MMCIF_ASSEMBLY_WRITER_VERSION,
    MmcifAssemblyEnvelopeError,
    parse_mmcif_assembly,
    round_trip_mmcif_assembly_source,
)


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "config" / "independent_engine_v2_v2_1_mmcif_assembly_corpus.json"
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "v2_1_mmcif_assembly"
CORPUS_SCHEMA_ID = "betelgeuze.v2_1_mmcif_assembly_corpus/1.0.0"
CORPUS_ID = "v2_1_strict_mmcif_explicit_biological_assembly_envelope_v1"
PAYLOAD_HASH_POLICY_ID = "sha256_canonical_json_without_payload_sha256/1.0.0"
EXPECTED_PAYLOAD_SHA256 = (
    "39a9d73e74ef71b7d740f4751edb35a78439eac059ec0f93f7b9eb5e40edffc5"
)
EXPECTED_CASE_IDS = (
    "identity_single_chain",
    "two_copy_translation",
    "noncommuting_composition",
    "failure_numeric_uncertainty",
)
EXPECTED_FAILURE_CODES = {
    "failure_numeric_uncertainty": "assembly_numeric_uncertainty_unsupported"
}
LOWER_SHA256 = re.compile(r"^[0-9a-f]{64}$")
CASE_ID = re.compile(r"^[a-z0-9_]+$")
MAX_MANIFEST_BYTES = 128 * 1024
MAX_FIXTURE_BYTES = 16 * 1024
MAX_TOTAL_FIXTURE_BYTES = 64 * 1024


class AssemblyCorpusError(ValueError):
    pass


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    document: dict[str, Any] = {}
    for key, value in pairs:
        if key in document:
            raise AssemblyCorpusError("duplicate manifest key")
        document[key] = value
    return document


def _load_manifest() -> dict[str, Any]:
    if not MANIFEST.is_file() or MANIFEST.stat().st_size > MAX_MANIFEST_BYTES:
        raise AssemblyCorpusError("manifest is missing or too large")
    try:
        value = json.loads(
            MANIFEST.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=lambda _value: (_ for _ in ()).throw(
                AssemblyCorpusError("nonstandard JSON constant")
            ),
            parse_float=lambda _value: (_ for _ in ()).throw(
                AssemblyCorpusError("floating JSON numbers are not admitted")
            ),
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AssemblyCorpusError("manifest must be strict bounded UTF-8 JSON") from exc
    if type(value) is not dict:
        raise AssemblyCorpusError("manifest root must be an object")
    return value


def _payload_sha256(document: dict[str, Any]) -> str:
    payload = deepcopy(document)
    payload.pop("payload_sha256")
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def _fixture(case: dict[str, Any]) -> bytes:
    value = case.get("fixture")
    if type(value) is not str:
        raise AssemblyCorpusError("fixture path must be a string")
    posix = PurePosixPath(value)
    if posix.is_absolute() or len(posix.parts) != 1 or posix.suffix != ".cif":
        raise AssemblyCorpusError("fixture path escapes the fixed corpus directory")
    path = (FIXTURE_ROOT / value).resolve(strict=True)
    if path.parent != FIXTURE_ROOT.resolve(strict=True) or not path.is_file():
        raise AssemblyCorpusError("fixture is outside the fixed corpus directory")
    if path.stat().st_size > MAX_FIXTURE_BYTES:
        raise AssemblyCorpusError("fixture exceeds its byte cap")
    payload = path.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    if digest != case.get("fixture_sha256"):
        raise AssemblyCorpusError("fixture SHA-256 does not match the manifest")
    return payload


def _round_trip_evidence(case: dict[str, Any], payload: bytes) -> dict[str, Any]:
    result = round_trip_mmcif_assembly_source(
        payload,
        assembly_id=case["assembly_id"],
        source_id=case["source_id"],
    )
    ingest = result.source_ingest
    write = result.write_result
    ingest_document = ingest.to_dict()
    report_document = result.report.to_dict()
    receipt_document = write.receipt.to_dict()
    return {
        "assembly_generator_row_count": ingest.assembly_generator_row_count,
        "assembly_operator_row_count": ingest.assembly_operator_row_count,
        "base_parser_version": ingest_document["base_parser_version"],
        "base_writer_version": receipt_document["base_writer_version"],
        "envelope_parser_version": ingest_document["parser_version"],
        "envelope_writer_version": receipt_document["writer_version"],
        "carrier_representable_state_sha256": (
            ingest.carrier_representable_state_sha256
        ),
        "declaration_projection_sha256": ingest.declaration_projection_sha256,
        "expanded_atom_count": ingest.expanded_system.atom_count,
        "expanded_chain_count": len(ingest.expanded_system.chains),
        "expanded_state_sha256": ingest.expanded_state_sha256,
        "expanded_topology_sha256": ingest.expanded_topology_sha256,
        "explicit_assembly_round_trip_preserved": report_document[
            "explicit_assembly_round_trip_preserved"
        ],
        "full_source_sha256": ingest.full_source_sha256,
        "output_byte_count": len(write.payload),
        "output_source_sha256": hashlib.sha256(write.payload).hexdigest(),
        "record_state_sha256": ingest.record_state_sha256,
        "record_state_equal": report_document["record_state_equal"],
        "emitted_source_reparsed_exact": report_document[
            "emitted_source_reparsed_exact"
        ],
        "write_receipt_source_bound": report_document[
            "write_receipt_source_bound"
        ],
        "reemitted_receipt_reparsed_bound": report_document[
            "reemitted_receipt_reparsed_bound"
        ],
        "round_trip_report_sha256": result.report.report_sha256,
        "second_emission_byte_stable": (
            write.payload == result.reemitted_write_result.payload
        ),
        "source_binding_sha256": ingest.source_binding_sha256,
        "source_id_sha256": ingest.source_id_sha256,
        "write_receipt_sha256": write.receipt.receipt_sha256,
    }


def test_manifest_identity_hash_and_fixed_case_inventory() -> None:
    document = _load_manifest()
    assert document["schema_id"] == CORPUS_SCHEMA_ID
    assert document["corpus_id"] == CORPUS_ID
    assert document["envelope_version"] == MMCIF_ASSEMBLY_ENVELOPE_VERSION
    assert document["parser_version"] == MMCIF_ASSEMBLY_PARSER_VERSION
    assert document["writer_version"] == MMCIF_ASSEMBLY_WRITER_VERSION
    assert document["payload_hash_policy_id"] == PAYLOAD_HASH_POLICY_ID
    assert document["payload_sha256"] == EXPECTED_PAYLOAD_SHA256
    assert LOWER_SHA256.fullmatch(document["payload_sha256"])
    assert _payload_sha256(document) == EXPECTED_PAYLOAD_SHA256
    cases = document["cases"]
    assert type(cases) is list
    assert tuple(case["case_id"] for case in cases) == EXPECTED_CASE_IDS
    assert len(set(EXPECTED_CASE_IDS)) == len(EXPECTED_CASE_IDS)
    assert all(CASE_ID.fullmatch(case["case_id"]) for case in cases)


def test_every_fixture_is_confined_hash_bound_and_within_total_cap() -> None:
    cases = _load_manifest()["cases"]
    payloads = [_fixture(case) for case in cases]
    assert sum(map(len, payloads)) <= MAX_TOTAL_FIXTURE_BYTES
    assert {path.name for path in FIXTURE_ROOT.iterdir() if path.is_file()} == {
        case["fixture"] for case in cases
    }


@pytest.mark.parametrize("case_id", EXPECTED_CASE_IDS[:3])
def test_round_trip_rows_match_all_frozen_evidence(case_id: str) -> None:
    case = next(
        item for item in _load_manifest()["cases"] if item["case_id"] == case_id
    )
    assert case["kind"] == "round_trip"
    evidence = _round_trip_evidence(case, _fixture(case))
    assert evidence == case["expected"]
    assert all(
        LOWER_SHA256.fullmatch(value)
        for key, value in evidence.items()
        if key.endswith("_sha256")
    )


def test_failure_rows_return_the_exact_typed_code() -> None:
    failures = [case for case in _load_manifest()["cases"] if case["kind"] == "failure"]
    assert {case["case_id"] for case in failures} == set(EXPECTED_FAILURE_CODES)
    for case in failures:
        assert case["expected_error_code"] == EXPECTED_FAILURE_CODES[case["case_id"]]
        with pytest.raises(MmcifAssemblyEnvelopeError) as exc_info:
            parse_mmcif_assembly(
                _fixture(case),
                assembly_id=case["assembly_id"],
                source_id=case["source_id"],
            )
        assert exc_info.value.code == case["expected_error_code"]


def test_projection_hashes_distinguish_declared_expansions() -> None:
    cases = [case for case in _load_manifest()["cases"] if case["kind"] == "round_trip"]
    declaration_hashes = {
        case["expected"]["declaration_projection_sha256"] for case in cases
    }
    expanded_hashes = {case["expected"]["expanded_state_sha256"] for case in cases}
    assert len(declaration_hashes) == len(cases)
    assert len(expanded_hashes) == len(cases)


def test_manifest_payload_hash_detects_tampering() -> None:
    document = _load_manifest()
    tampered = deepcopy(document)
    tampered["cases"][0]["assembly_id"] = "forged"
    assert _payload_sha256(tampered) != EXPECTED_PAYLOAD_SHA256
