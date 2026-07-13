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
    MAX_MMCIF_NONPOLY_ENTITY_ROWS,
    MAX_MMCIF_NONPOLY_IDENTITY_INPUT_BYTES,
    MAX_MMCIF_NONPOLY_SCHEME_ROWS,
    MMCIF_NONPOLY_IDENTITY_ENVELOPE_VERSION,
    MMCIF_NONPOLY_IDENTITY_PARSER_NAME,
    MMCIF_NONPOLY_IDENTITY_PARSER_VERSION,
    MMCIF_NONPOLY_IDENTITY_PROFILE_ID,
    MMCIF_NONPOLY_IDENTITY_PROJECTION_SCHEMA_ID,
    MMCIF_NONPOLY_IDENTITY_RECORD_STATE_SCHEMA_ID,
    MMCIF_NONPOLY_IDENTITY_ROUND_TRIP_REPORT_SCHEMA_ID,
    MMCIF_NONPOLY_IDENTITY_WRITER_VERSION,
    MMCIF_NONPOLY_IDENTITY_WRITE_RECEIPT_SCHEMA_ID,
    MMCIF_PARSER_VERSION,
    MMCIF_WRITER_VERSION,
    MmcifNonpolyIdentityError,
    parse_mmcif_nonpoly_identity,
    round_trip_mmcif_nonpoly_identity_source,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = (
    REPOSITORY_ROOT
    / "config"
    / "independent_engine_v2_v2_1_mmcif_nonpoly_identity_corpus.json"
)
FIXTURE_ROOT = REPOSITORY_ROOT / "tests" / "fixtures" / "v2_1_mmcif_nonpoly_identity"
CORPUS_SCHEMA_ID = "betelgeuze.v2_1_mmcif_nonpoly_identity_corpus/1.0.0"
CORPUS_ID = "v2_1_strict_mmcif_source_reported_nonpoly_identity_envelope_v1"
PAYLOAD_HASH_POLICY_ID = "sha256_canonical_json_without_payload_sha256/1.0.0"
EXPECTED_PAYLOAD_SHA256 = (
    "fc66aa69e146d12df1fa8a041ad47ae1cf8363210a31345eb1724df27d7dd26c"
)
PROJECTION_SCOPE = (
    "source_reported_nonpolymer_identity_and_instance_nomenclature_aliases_only"
)

_LOWERCASE_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_CASE_ID = re.compile(r"^[a-z][a-z0-9_]*$")
_FALSE_GATES = (
    "source_authenticated",
    "chemistry_interpreted",
    "role_assignment_interpreted",
    "bond_topology_interpreted",
    "bond_order_interpreted",
    "coordination_interpreted",
    "charge_interpreted",
    "protonation_interpreted",
    "preparation_ready",
    "parameterability_assessed",
    "physics_supported",
    "simulation_ready",
    "runtime_eligible",
    "execution_authorized",
    "claim_safe",
    "general_mmcif_round_trip_evidence_ready",
    "all_format_round_trip_evidence_ready",
)
_ROUND_TRIP_CASE_IDS = {
    "category_order_variant",
    "mixed_polymer_nonpoly_water",
    "quoted_name_multiword",
    "same_comp_multiple_instances",
    "single_hem_complete",
}
_FAILURE_CODES = {
    "failure_category_surface": "unsupported_category_surface",
    "failure_header_order": "unsupported_category_headers",
    "failure_join_mismatch": "nonpoly_scheme_join_mismatch",
    "failure_non_ascii": "non_ascii_input",
}
_CASE_IDS = _ROUND_TRIP_CASE_IDS | set(_FAILURE_CODES)
_EXPECTED_KEYS = {
    "base_representable_state_sha256",
    "base_system_snapshot_sha256",
    "base_topology_sha256",
    "canonical_base_source_sha256",
    "entity_nonpoly_row_count",
    "full_source_sha256",
    "identity_projection_sha256",
    "nonpoly_scheme_row_count",
    "normalized_base_source_sha256",
    "output_byte_count",
    "output_equals_input",
    "output_source_sha256",
    "record_state_sha256",
    "round_trip_report_sha256",
    "second_emission_byte_stable",
    "write_receipt_sha256",
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


def _resolve_source(source: dict[str, Any]) -> tuple[Path, bytes]:
    assert source["kind"] in {"fixture", "fixture_replacements"}
    relative = source["path"]
    assert type(relative) is str
    pure = PurePosixPath(relative)
    assert not pure.is_absolute() and ".." not in pure.parts
    assert pure.parts[:2] == ("tests", "fixtures")
    path = REPOSITORY_ROOT.joinpath(*pure.parts)
    assert path.is_file()
    payload = path.read_bytes()
    if source["kind"] == "fixture":
        assert set(source) == {"kind", "path"}
        return path, payload
    assert set(source) == {"kind", "path", "replacements"}
    replacements = source["replacements"]
    assert type(replacements) is list and replacements
    for replacement in replacements:
        assert set(replacement) == {"old_hex", "new_hex"}
        old = bytes.fromhex(replacement["old_hex"])
        new = bytes.fromhex(replacement["new_hex"])
        assert old and payload.count(old) == 1
        payload = payload.replace(old, new, 1)
    return path, payload


def _replay(case: dict[str, Any]) -> tuple[dict[str, Any], Any]:
    _path, source = _resolve_source(case["source"])
    assert hashlib.sha256(source).hexdigest() == case["source_sha256"]
    result = round_trip_mmcif_nonpoly_identity_source(
        source,
        source_id=case["source_id"],
    )
    ingest = result.source_ingest
    receipt = result.write_result.receipt
    return (
        {
            "base_representable_state_sha256": ingest.base_representable_state_sha256,
            "base_system_snapshot_sha256": ingest.base_system_snapshot_sha256,
            "base_topology_sha256": ingest.base_topology_sha256,
            "canonical_base_source_sha256": ingest.canonical_base_source_sha256,
            "entity_nonpoly_row_count": len(ingest.entity_rows),
            "full_source_sha256": ingest.full_source_sha256,
            "identity_projection_sha256": ingest.identity_projection_sha256,
            "nonpoly_scheme_row_count": len(ingest.scheme_rows),
            "normalized_base_source_sha256": ingest.normalized_base_source_sha256,
            "output_byte_count": receipt.output_byte_count,
            "output_equals_input": result.write_result.payload == source,
            "output_source_sha256": receipt.output_source_sha256,
            "record_state_sha256": ingest.record_state_sha256,
            "round_trip_report_sha256": result.report.report_sha256,
            "second_emission_byte_stable": result.report.second_emission_byte_stable,
            "write_receipt_sha256": receipt.receipt_sha256,
        },
        result,
    )


def test_manifest_contract_payload_hash_and_inventory_are_exact() -> None:
    document = _load_manifest()
    assert set(document) == {
        "schema_id",
        "corpus_id",
        "manifest_payload_hash_policy_id",
        "payload_sha256",
        "contracts",
        "claim_boundary",
        "cases",
    }
    assert document["schema_id"] == CORPUS_SCHEMA_ID
    assert document["corpus_id"] == CORPUS_ID
    assert document["manifest_payload_hash_policy_id"] == PAYLOAD_HASH_POLICY_ID
    assert document["payload_sha256"] == EXPECTED_PAYLOAD_SHA256
    assert _payload_sha256(document) == EXPECTED_PAYLOAD_SHA256

    assert document["contracts"] == {
        "all_atom_schema_id": ALL_ATOM_SCHEMA_ID,
        "base_mmcif_parser_version": MMCIF_PARSER_VERSION,
        "base_mmcif_writer_version": MMCIF_WRITER_VERSION,
        "envelope_version": MMCIF_NONPOLY_IDENTITY_ENVELOPE_VERSION,
        "envelope_parser_version": MMCIF_NONPOLY_IDENTITY_PARSER_VERSION,
        "envelope_writer_version": MMCIF_NONPOLY_IDENTITY_WRITER_VERSION,
        "parser_name": MMCIF_NONPOLY_IDENTITY_PARSER_NAME,
        "profile_id": MMCIF_NONPOLY_IDENTITY_PROFILE_ID,
        "identity_projection_schema_id": MMCIF_NONPOLY_IDENTITY_PROJECTION_SCHEMA_ID,
        "record_state_schema_id": MMCIF_NONPOLY_IDENTITY_RECORD_STATE_SCHEMA_ID,
        "write_receipt_schema_id": MMCIF_NONPOLY_IDENTITY_WRITE_RECEIPT_SCHEMA_ID,
        "round_trip_report_schema_id": (
            MMCIF_NONPOLY_IDENTITY_ROUND_TRIP_REPORT_SCHEMA_ID
        ),
        "projection_scope": PROJECTION_SCOPE,
        "entity_nonpoly_header_profiles": [
            ["entity_id", "comp_id"],
            ["entity_id", "name", "comp_id"],
        ],
        "nonpoly_scheme_headers": [
            "asym_id",
            "entity_id",
            "mon_id",
            "ndb_seq_num",
            "pdb_seq_num",
            "auth_seq_num",
            "pdb_mon_id",
            "auth_mon_id",
            "pdb_strand_id",
            "pdb_ins_code",
        ],
        "canonical_category_order": [
            "_entity",
            "_struct_asym",
            "_pdbx_entity_nonpoly",
            "_pdbx_nonpoly_scheme",
            "_atom_site",
        ],
        "limits": {
            "max_input_bytes": MAX_MMCIF_NONPOLY_IDENTITY_INPUT_BYTES,
            "max_entity_nonpoly_rows": MAX_MMCIF_NONPOLY_ENTITY_ROWS,
            "max_nonpoly_scheme_rows": MAX_MMCIF_NONPOLY_SCHEME_ROWS,
        },
    }


def test_manifest_claim_boundary_is_exactly_nonpromoting() -> None:
    assert _load_manifest()["claim_boundary"] == {
        "positive_true_fields": ["source_identity_projection_preserved"],
        "always_false_fields": list(_FALSE_GATES),
        "base_parser_default_changed": False,
        "general_mmcif_round_trip_evidence_ready": False,
        "v2_1_complete": False,
    }


def test_case_shapes_hashes_and_fixture_closure_are_exact() -> None:
    cases = _load_manifest()["cases"]
    assert type(cases) is list and len(cases) == 9
    assert [case["case_id"] for case in cases] == sorted(_CASE_IDS)
    referenced: set[Path] = set()
    for case in cases:
        assert set(case) == {
            "case_id",
            "lane",
            "source",
            "source_id",
            "source_sha256",
            "expected",
        }
        assert _CASE_ID.fullmatch(case["case_id"])
        assert _LOWERCASE_SHA256.fullmatch(case["source_sha256"])
        path, source = _resolve_source(case["source"])
        assert hashlib.sha256(source).hexdigest() == case["source_sha256"]
        referenced.add(path.resolve())
        if case["lane"] == "round_trip":
            assert case["case_id"] in _ROUND_TRIP_CASE_IDS
            assert set(case["expected"]) == _EXPECTED_KEYS
            for key, value in case["expected"].items():
                if key.endswith("sha256"):
                    assert type(value) is str and _LOWERCASE_SHA256.fullmatch(value)
        else:
            assert case["lane"] == "parse_failure"
            assert case["expected"] == {"error_code": _FAILURE_CODES[case["case_id"]]}
    assert referenced == {path.resolve() for path in FIXTURE_ROOT.glob("*.cif")}


@pytest.mark.parametrize("case_id", sorted(_ROUND_TRIP_CASE_IDS))
def test_round_trip_rows_replay_exact_digests_and_keep_authority_false(
    case_id: str,
) -> None:
    case = next(row for row in _load_manifest()["cases"] if row["case_id"] == case_id)
    actual, result = _replay(case)
    assert actual == case["expected"]
    for artifact in (
        result.source_ingest.to_dict(),
        result.write_result.receipt.to_dict(),
        result.report.to_dict(),
    ):
        assert artifact["source_identity_projection_preserved"] is True
        for field in _FALSE_GATES:
            assert artifact[field] is False


@pytest.mark.parametrize("case_id", sorted(_FAILURE_CODES))
def test_parse_failure_rows_replay_exact_error_codes_without_raw_context(
    case_id: str,
) -> None:
    case = next(row for row in _load_manifest()["cases"] if row["case_id"] == case_id)
    _path, source = _resolve_source(case["source"])
    assert hashlib.sha256(source).hexdigest() == case["source_sha256"]
    with pytest.raises(MmcifNonpolyIdentityError) as exc_info:
        parse_mmcif_nonpoly_identity(source, source_id=case["source_id"])
    assert exc_info.value.code == _FAILURE_CODES[case_id]
    if case_id == "failure_non_ascii":
        assert exc_info.value.__cause__ is None
        assert exc_info.value.__context__ is None
