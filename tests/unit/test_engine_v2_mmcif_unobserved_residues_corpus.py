from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from typing import Any

import pytest

from betelgeuze_engine_v2.contracts import ALL_ATOM_SCHEMA_ID
from betelgeuze_engine_v2.molecular.mmcif_nonpoly_identity import (
    MMCIF_NONPOLY_IDENTITY_ENVELOPE_VERSION,
)
from betelgeuze_engine_v2.molecular.mmcif_polymer_sequence import (
    MMCIF_POLYMER_SEQUENCE_ENVELOPE_VERSION,
    MmcifPolymerSequenceError,
    parse_mmcif_polymer_sequence,
)
from betelgeuze_engine_v2.molecular.mmcif_unobserved_residues import (
    MAX_MMCIF_UNOBSERVED_RESIDUE_INPUT_BYTES,
    MAX_MMCIF_UNOBSERVED_RESIDUE_ROWS,
    MAX_MMCIF_UNOBSERVED_RESIDUE_SOURCE_ID_BYTES,
    MAX_MMCIF_UNOBSERVED_RESIDUE_TOKEN_CHARS,
    MMCIF_UNOBSERVED_RESIDUE_ENVELOPE_VERSION,
    MMCIF_UNOBSERVED_RESIDUE_HEADERS,
    MMCIF_UNOBSERVED_RESIDUE_PARSER_NAME,
    MMCIF_UNOBSERVED_RESIDUE_PARSER_VERSION,
    MMCIF_UNOBSERVED_RESIDUE_PROFILE_ID,
    MMCIF_UNOBSERVED_RESIDUE_PROJECTION_SCOPE,
    MMCIF_UNOBSERVED_RESIDUE_PROJECTION_SCHEMA_ID,
    MMCIF_UNOBSERVED_RESIDUE_RECORD_STATE_SCHEMA_ID,
    MMCIF_UNOBSERVED_RESIDUE_ROUND_TRIP_REPORT_SCHEMA_ID,
    MMCIF_UNOBSERVED_RESIDUE_SOURCE_BINDING_SCHEMA_ID,
    MMCIF_UNOBSERVED_RESIDUE_WRITER_VERSION,
    MMCIF_UNOBSERVED_RESIDUE_WRITE_RECEIPT_SCHEMA_ID,
    MmcifUnobservedResidueError,
    parse_mmcif_unobserved_residues,
    round_trip_mmcif_unobserved_residues_source,
)
from betelgeuze_engine_v2.molecular.mmcif_writer import MMCIF_WRITER_VERSION
from betelgeuze_engine_v2.molecular.pdb_mmcif import (
    MMCIF_PARSER_VERSION,
    StructureParseError,
    parse_mmcif,
)


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = (
    ROOT / "config" / "independent_engine_v2_v2_1_mmcif_unobserved_residue_corpus.json"
)
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "v2_1_mmcif_unobserved_residues"
CORPUS_SCHEMA_ID = "betelgeuze.v2_1_mmcif_unobserved_residue_corpus/1.0.0"
CORPUS_ID = "v2_1_strict_mmcif_source_reported_unobserved_residue_claim_envelope_v1"
PAYLOAD_HASH_POLICY_ID = "sha256_canonical_json_without_payload_sha256/1.0.0"
EXPECTED_PAYLOAD_SHA256 = (
    "003b7f870a988fd39f83ca23302edeef2cd7d7123ea72a1c0508c8ee202b4750"
)

_LOWER_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_CASE_ID = re.compile(r"^[a-z0-9_]+$")
_MAX_MANIFEST_BYTES = 1024 * 1024
_MAX_CASE_COUNT = 32
_MAX_FIXTURE_COUNT = 8
_MAX_FIXTURE_BYTES = 16 * 1024
_MAX_TOTAL_FIXTURE_BYTES = 128 * 1024

_ROUND_TRIP_CASE_IDS = {
    "category_order_variant",
    "composed_nonpoly_carrier",
    "insertion_marker_auth_alias",
    "multiple_ordered_claims",
    "shared_entity_multiple_asym",
    "single_unobserved_member",
}
_FAILURE_CODES = {
    "failure_atom_missing_category": "unsupported_category_surface",
    "failure_category_surface": "unsupported_category_surface",
    "failure_coordinate_contradiction": "unobserved_residue_present_in_coordinates",
    "failure_duplicate_id": "duplicate_or_invalid_unobserved_residue_id",
    "failure_duplicate_semantic_key": "duplicate_unobserved_residue_identity",
    "failure_extension_header": "unsupported_category_headers",
    "failure_header_order": "unsupported_category_headers",
    "failure_non_ascii": "non_ascii_input",
    "failure_nonpoly_entity": "unobserved_residue_nonpolymer_entity",
    "failure_sequence_join": "unobserved_residue_sequence_join_mismatch",
    "failure_unknown_asym": "unknown_unobserved_residue_asym_id",
    "failure_wrong_model": "unsupported_unobserved_residue_model",
    "failure_wrong_polymer_flag": "unsupported_unobserved_residue_polymer_flag",
    "failure_zero_occupancy": "unsupported_unobserved_residue_occupancy_flag",
}
_FALSE_GATES = (
    "source_authenticated",
    "auth_label_equivalence_inferred",
    "reference_sequence_equivalence_assessed",
    "coordinate_observation_completeness_assessed",
    "modeled_residue_presence_assessed",
    "modified_residue_identity_assessed",
    "polymer_chemistry_interpreted",
    "microheterogeneity_interpreted",
    "chemistry_interpreted",
    "role_assignment_interpreted",
    "bond_topology_interpreted",
    "bond_order_interpreted",
    "coordination_interpreted",
    "charge_interpreted",
    "protonation_interpreted",
    "missing_residue_fact_claimed",
    "sequence_completeness_claimed",
    "preparation_ready",
    "parameterability_assessed",
    "physics_supported",
    "runtime_eligible",
    "simulation_ready",
    "execution_authorized",
    "claim_safe",
    "general_mmcif_round_trip_evidence_ready",
    "all_format_round_trip_evidence_ready",
)
_EXPECTED_KEYS = {
    "base_representable_state_sha256",
    "base_system_snapshot_sha256",
    "base_topology_sha256",
    "canonical_carrier_source_sha256",
    "carrier_kind",
    "carrier_source_sha256",
    "full_source_sha256",
    "nonpoly_identity_projection_sha256",
    "nonpoly_identity_record_state_sha256",
    "output_byte_count",
    "output_equals_input",
    "output_source_sha256",
    "polymer_sequence_projection_sha256",
    "polymer_sequence_record_state_sha256",
    "record_state_sha256",
    "round_trip_report_sha256",
    "second_emission_byte_stable",
    "source_binding_sha256",
    "source_id_sha256",
    "unobserved_residue_projection_sha256",
    "unobserved_residue_row_count",
    "write_receipt_sha256",
}
_EXPECTED_REQUIRED_SHA_KEYS = {
    key
    for key in _EXPECTED_KEYS
    if key.endswith("sha256")
    and key
    not in {
        "nonpoly_identity_projection_sha256",
        "nonpoly_identity_record_state_sha256",
    }
}
_EXPECTED_NULLABLE_SHA_KEYS = {
    "nonpoly_identity_projection_sha256",
    "nonpoly_identity_record_state_sha256",
}
_EXPECTED_COUNT_KEYS = {"output_byte_count", "unobserved_residue_row_count"}
_EXPECTED_BOOLEAN_KEYS = {"output_equals_input", "second_emission_byte_stable"}


class CorpusManifestError(ValueError):
    pass


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    document: dict[str, Any] = {}
    for key, value in pairs:
        if key in document:
            raise CorpusManifestError("duplicate manifest key")
        document[key] = value
    return document


def _parse_manifest_json(text: str) -> dict[str, Any]:
    try:
        document = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=lambda _token: (_ for _ in ()).throw(
                CorpusManifestError("nonstandard JSON constant")
            ),
            parse_float=lambda _token: (_ for _ in ()).throw(
                CorpusManifestError("floating JSON number")
            ),
        )
    except json.JSONDecodeError as exc:
        raise CorpusManifestError("manifest must be strict JSON") from exc
    if type(document) is not dict:
        raise CorpusManifestError("manifest root must be an object")
    return document


def _load_manifest() -> dict[str, Any]:
    try:
        config_root = (ROOT / "config").resolve(strict=True)
        path = MANIFEST.resolve(strict=True)
        if (
            path.parent != config_root
            or path.name
            != "independent_engine_v2_v2_1_mmcif_unobserved_residue_corpus.json"
            or not path.is_file()
            or path.stat().st_size > _MAX_MANIFEST_BYTES
        ):
            raise CorpusManifestError("manifest is absent or exceeds its byte cap")
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise CorpusManifestError("manifest must be bounded UTF-8 text") from exc
    return _parse_manifest_json(text)


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


def _resolve_source(source: dict[str, Any]) -> tuple[Path, bytes]:
    if type(source) is not dict or set(source) not in (
        {"kind", "path"},
        {"kind", "path", "replacements"},
    ):
        raise CorpusManifestError("fixture source shape is invalid")
    kind = source["kind"]
    relative = source["path"]
    if kind not in {"fixture", "fixture_replacements"} or type(relative) is not str:
        raise CorpusManifestError("fixture kind or path is invalid")
    pure = PurePosixPath(relative)
    expected_prefix = ("tests", "fixtures", "v2_1_mmcif_unobserved_residues")
    if pure.is_absolute() or ".." in pure.parts or pure.parts[:3] != expected_prefix:
        raise CorpusManifestError("fixture path escapes the selected corpus root")
    fixture_root = FIXTURE_ROOT.resolve(strict=True)
    try:
        path = ROOT.joinpath(*pure.parts).resolve(strict=True)
    except OSError as exc:
        raise CorpusManifestError("fixture path is not resolvable") from exc
    if path.parent != fixture_root or not path.is_file():
        raise CorpusManifestError("fixture path is outside the selected corpus root")
    if path.stat().st_size > _MAX_FIXTURE_BYTES:
        raise CorpusManifestError("fixture exceeds the corpus fixture byte cap")
    payload = path.read_bytes()
    if len(payload) > MAX_MMCIF_UNOBSERVED_RESIDUE_INPUT_BYTES:
        raise CorpusManifestError("fixture exceeds the parser input byte cap")
    if kind == "fixture":
        if "replacements" in source:
            raise CorpusManifestError("plain fixture cannot define replacements")
        return path, payload
    replacements = source["replacements"]
    if type(replacements) is not list or not replacements:
        raise CorpusManifestError("fixture replacements must be a nonempty list")
    for replacement in replacements:
        if type(replacement) is not dict or set(replacement) != {
            "old_hex",
            "new_hex",
        }:
            raise CorpusManifestError("fixture replacement shape is invalid")
        old_hex = replacement["old_hex"]
        new_hex = replacement["new_hex"]
        if type(old_hex) is not str or type(new_hex) is not str:
            raise CorpusManifestError("fixture replacement must use hex strings")
        try:
            old = bytes.fromhex(old_hex)
            new = bytes.fromhex(new_hex)
        except ValueError as exc:
            raise CorpusManifestError(
                "fixture replacement must use hex strings"
            ) from exc
        if not old or payload.count(old) != 1:
            raise CorpusManifestError("fixture replacement source is not unique")
        payload = payload.replace(old, new, 1)
        if (
            len(payload) > _MAX_FIXTURE_BYTES
            or len(payload) > MAX_MMCIF_UNOBSERVED_RESIDUE_INPUT_BYTES
        ):
            raise CorpusManifestError("replaced fixture exceeds a byte cap")
    return path, payload


def _replay(case: dict[str, Any]) -> tuple[dict[str, Any], Any]:
    _path, source = _resolve_source(case["source"])
    assert hashlib.sha256(source).hexdigest() == case["source_sha256"]
    result = round_trip_mmcif_unobserved_residues_source(
        source, source_id=case["source_id"]
    )
    ingest = result.source_ingest
    receipt = result.write_result.receipt
    receipt_document = receipt.to_dict()
    polymer_ingest = ingest.polymer_ingest
    return (
        {
            "base_representable_state_sha256": (
                polymer_ingest.base_representable_state_sha256
            ),
            "base_system_snapshot_sha256": polymer_ingest.base_system_snapshot_sha256,
            "base_topology_sha256": polymer_ingest.base_topology_sha256,
            "canonical_carrier_source_sha256": ingest.canonical_carrier_source_sha256,
            "carrier_kind": ingest.carrier_kind,
            "carrier_source_sha256": ingest.carrier_source_sha256,
            "full_source_sha256": ingest.full_source_sha256,
            "nonpoly_identity_projection_sha256": ingest.nonpoly_identity_projection_sha256,
            "nonpoly_identity_record_state_sha256": ingest.nonpoly_identity_record_state_sha256,
            "output_byte_count": receipt_document["output_byte_count"],
            "output_equals_input": result.write_result.payload == source,
            "output_source_sha256": receipt.output_source_sha256,
            "polymer_sequence_projection_sha256": ingest.polymer_projection_sha256,
            "polymer_sequence_record_state_sha256": ingest.polymer_record_state_sha256,
            "record_state_sha256": ingest.record_state_sha256,
            "round_trip_report_sha256": result.report.round_trip_report_sha256,
            "second_emission_byte_stable": result.report.second_emission_byte_stable,
            "source_binding_sha256": ingest.source_binding_sha256,
            "source_id_sha256": ingest.source_id_sha256,
            "unobserved_residue_projection_sha256": ingest.unobserved_residue_projection_sha256,
            "unobserved_residue_row_count": len(ingest.unobserved_residue_rows),
            "write_receipt_sha256": receipt.receipt_sha256,
        },
        result,
    )


def test_manifest_payload_hash_and_top_level_inventory_are_exact() -> None:
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


@pytest.mark.parametrize(
    "payload",
    (
        '{"schema_id":"first","schema_id":"second"}',
        '{"value":NaN}',
        '{"value":1.5}',
        "[]",
    ),
    ids=("duplicate_key", "nonstandard_constant", "floating_number", "non_object"),
)
def test_manifest_loader_rejects_noncanonical_json(payload: str) -> None:
    with pytest.raises(CorpusManifestError):
        _parse_manifest_json(payload)


@pytest.mark.parametrize(
    "path",
    (
        str((FIXTURE_ROOT / "single_unobserved_member.cif").resolve()),
        "../tests/fixtures/v2_1_mmcif_unobserved_residues/single_unobserved_member.cif",
        "tests/fixtures/v2_1_mmcif_polymer_sequence/unobserved_source_member.cif",
    ),
    ids=("absolute", "parent_traversal", "wrong_fixture_root"),
)
def test_fixture_resolver_rejects_paths_outside_exact_corpus(path: str) -> None:
    with pytest.raises(CorpusManifestError):
        _resolve_source({"kind": "fixture", "path": path})


def test_manifest_contract_versions_profiles_orders_and_caps_are_exact() -> None:
    assert _load_manifest()["contracts"] == {
        "all_atom_schema_id": ALL_ATOM_SCHEMA_ID,
        "base_mmcif_parser_version": MMCIF_PARSER_VERSION,
        "base_mmcif_writer_version": MMCIF_WRITER_VERSION,
        "nonpoly_identity_envelope_version": MMCIF_NONPOLY_IDENTITY_ENVELOPE_VERSION,
        "polymer_sequence_envelope_version": MMCIF_POLYMER_SEQUENCE_ENVELOPE_VERSION,
        "envelope_version": MMCIF_UNOBSERVED_RESIDUE_ENVELOPE_VERSION,
        "envelope_parser_version": MMCIF_UNOBSERVED_RESIDUE_PARSER_VERSION,
        "envelope_writer_version": MMCIF_UNOBSERVED_RESIDUE_WRITER_VERSION,
        "parser_name": MMCIF_UNOBSERVED_RESIDUE_PARSER_NAME,
        "profile_id": MMCIF_UNOBSERVED_RESIDUE_PROFILE_ID,
        "projection_schema_id": MMCIF_UNOBSERVED_RESIDUE_PROJECTION_SCHEMA_ID,
        "record_state_schema_id": MMCIF_UNOBSERVED_RESIDUE_RECORD_STATE_SCHEMA_ID,
        "source_binding_schema_id": MMCIF_UNOBSERVED_RESIDUE_SOURCE_BINDING_SCHEMA_ID,
        "write_receipt_schema_id": MMCIF_UNOBSERVED_RESIDUE_WRITE_RECEIPT_SCHEMA_ID,
        "round_trip_report_schema_id": MMCIF_UNOBSERVED_RESIDUE_ROUND_TRIP_REPORT_SCHEMA_ID,
        "projection_scope": MMCIF_UNOBSERVED_RESIDUE_PROJECTION_SCOPE,
        "unobserved_residue_headers": [
            tag.split(".", 1)[1] for tag in MMCIF_UNOBSERVED_RESIDUE_HEADERS
        ],
        "carrier_kinds": [
            "mmcif_polymer_sequence",
            "mmcif_polymer_sequence_nonpoly_identity",
        ],
        "canonical_category_orders": {
            "mmcif_polymer_sequence": [
                "_entity",
                "_struct_asym",
                "_entity_poly_seq",
                "_pdbx_unobs_or_zero_occ_residues",
                "_atom_site",
            ],
            "mmcif_polymer_sequence_nonpoly_identity": [
                "_entity",
                "_struct_asym",
                "_entity_poly_seq",
                "_pdbx_entity_nonpoly",
                "_pdbx_nonpoly_scheme",
                "_pdbx_unobs_or_zero_occ_residues",
                "_atom_site",
            ],
        },
        "limits": {
            "max_input_bytes": MAX_MMCIF_UNOBSERVED_RESIDUE_INPUT_BYTES,
            "max_unobserved_residue_rows": MAX_MMCIF_UNOBSERVED_RESIDUE_ROWS,
            "max_source_id_utf8_bytes": (MAX_MMCIF_UNOBSERVED_RESIDUE_SOURCE_ID_BYTES),
            "max_selected_token_chars": MAX_MMCIF_UNOBSERVED_RESIDUE_TOKEN_CHARS,
            "max_manifest_bytes": _MAX_MANIFEST_BYTES,
            "max_case_count": _MAX_CASE_COUNT,
            "max_fixture_count": _MAX_FIXTURE_COUNT,
            "max_fixture_bytes": _MAX_FIXTURE_BYTES,
            "max_total_fixture_bytes": _MAX_TOTAL_FIXTURE_BYTES,
        },
    }


def test_manifest_claim_boundary_is_exactly_nonpromoting() -> None:
    assert _load_manifest()["claim_boundary"] == {
        "positive_true_fields": ["source_reported_unobserved_residue_claims_preserved"],
        "always_false_fields": list(_FALSE_GATES),
        "base_parser_default_changed": False,
        "polymer_sequence_parser_default_changed": False,
        "nonpoly_identity_parser_default_changed": False,
        "missing_residue_fact_established": False,
        "sequence_completeness_established": False,
        "general_mmcif_round_trip_evidence_ready": False,
        "v2_1_complete": False,
    }


def test_case_shapes_types_hashes_fixture_counts_and_closure_are_exact() -> None:
    cases = _load_manifest()["cases"]
    assert type(cases) is list
    assert len(cases) == len(_ROUND_TRIP_CASE_IDS) + len(_FAILURE_CODES)
    assert len(cases) <= _MAX_CASE_COUNT
    assert [case["case_id"] for case in cases] == sorted(
        _ROUND_TRIP_CASE_IDS | set(_FAILURE_CODES)
    )
    referenced: set[Path] = set()
    for case in cases:
        assert type(case) is dict and set(case) == {
            "case_id",
            "lane",
            "source",
            "source_id",
            "source_sha256",
            "expected",
        }
        assert type(case["case_id"]) is str and _CASE_ID.fullmatch(case["case_id"])
        assert type(case["source_id"]) is str
        assert type(case["source_sha256"]) is str and _LOWER_SHA256.fullmatch(
            case["source_sha256"]
        )
        path, source = _resolve_source(case["source"])
        assert hashlib.sha256(source).hexdigest() == case["source_sha256"]
        referenced.add(path.resolve())
        if case["lane"] == "round_trip":
            assert case["case_id"] in _ROUND_TRIP_CASE_IDS
            assert type(case["expected"]) is dict
            assert set(case["expected"]) == _EXPECTED_KEYS
            for key, value in case["expected"].items():
                if key in _EXPECTED_REQUIRED_SHA_KEYS:
                    assert type(value) is str and _LOWER_SHA256.fullmatch(value)
                elif key in _EXPECTED_NULLABLE_SHA_KEYS:
                    assert value is None or (
                        type(value) is str and _LOWER_SHA256.fullmatch(value)
                    )
                elif key in _EXPECTED_COUNT_KEYS:
                    assert type(value) is int and value >= 0
                elif key in _EXPECTED_BOOLEAN_KEYS:
                    assert type(value) is bool
                else:
                    assert key == "carrier_kind"
                    assert value in {
                        "mmcif_polymer_sequence",
                        "mmcif_polymer_sequence_nonpoly_identity",
                    }
        else:
            assert case["lane"] == "parse_failure"
            assert case["expected"] == {"error_code": _FAILURE_CODES[case["case_id"]]}
    fixtures = {path.resolve() for path in FIXTURE_ROOT.glob("*.cif")}
    assert referenced == fixtures
    assert len(fixtures) == 6 and len(fixtures) <= _MAX_FIXTURE_COUNT
    sizes = [path.stat().st_size for path in fixtures]
    assert all(size <= _MAX_FIXTURE_BYTES for size in sizes)
    assert sum(sizes) <= _MAX_TOTAL_FIXTURE_BYTES


@pytest.mark.parametrize("case_id", sorted(_ROUND_TRIP_CASE_IDS))
def test_round_trip_cases_replay_every_digest_and_false_gate(case_id: str) -> None:
    case = next(row for row in _load_manifest()["cases"] if row["case_id"] == case_id)
    actual, result = _replay(case)
    assert actual == case["expected"]
    for artifact in (
        result.source_ingest.to_dict(),
        result.write_result.receipt.to_dict(),
        result.report.to_dict(),
        result.to_dict(),
    ):
        assert artifact["source_reported_unobserved_residue_claims_preserved"] is True
        for field_name in _FALSE_GATES:
            assert artifact[field_name] is False

    _path, source = _resolve_source(case["source"])
    assert (
        result.source_ingest.base_ingest.missingness_evidence.source_reported_missing_residue_count
        >= 1
    )
    with pytest.raises(StructureParseError) as base_exc:
        parse_mmcif(source, source_id=case_id)
    assert base_exc.value.code == "unsupported_context_category"
    with pytest.raises(MmcifPolymerSequenceError) as exc_info:
        parse_mmcif_polymer_sequence(source, source_id=case_id)
    assert exc_info.value.code == "unsupported_category_surface"


@pytest.mark.parametrize("case_id", sorted(_FAILURE_CODES))
def test_failure_cases_replay_exact_codes_without_raw_context(case_id: str) -> None:
    case = next(row for row in _load_manifest()["cases"] if row["case_id"] == case_id)
    _path, source = _resolve_source(case["source"])
    with pytest.raises(MmcifUnobservedResidueError) as exc_info:
        parse_mmcif_unobserved_residues(source, source_id=case["source_id"])
    assert exc_info.value.code == _FAILURE_CODES[case_id]
    if case_id == "failure_non_ascii":
        assert exc_info.value.__cause__ is None
        assert exc_info.value.__context__ is None
        assert "PRIVATE" not in str(exc_info.value)
        assert "PRIVATE" not in repr(exc_info.value)


def test_category_order_pair_has_equal_projection_state_output_not_binding() -> None:
    cases = {row["case_id"]: row for row in _load_manifest()["cases"]}
    canonical = cases["single_unobserved_member"]["expected"]
    reordered = cases["category_order_variant"]["expected"]
    assert (
        canonical["unobserved_residue_projection_sha256"]
        == (reordered["unobserved_residue_projection_sha256"])
    )
    assert canonical["record_state_sha256"] == reordered["record_state_sha256"]
    assert canonical["output_source_sha256"] == reordered["output_source_sha256"]
    assert canonical["source_binding_sha256"] != reordered["source_binding_sha256"]
    assert canonical["write_receipt_sha256"] != reordered["write_receipt_sha256"]


def test_only_composed_case_carries_nonpoly_identity_evidence() -> None:
    cases = {
        row["case_id"]: row["expected"]
        for row in _load_manifest()["cases"]
        if row["lane"] == "round_trip"
    }
    for case_id, expected in cases.items():
        composed = case_id == "composed_nonpoly_carrier"
        assert (
            expected["carrier_kind"] == "mmcif_polymer_sequence_nonpoly_identity"
        ) is composed
        assert (expected["nonpoly_identity_projection_sha256"] is not None) is composed
        assert (
            expected["nonpoly_identity_record_state_sha256"] is not None
        ) is composed
