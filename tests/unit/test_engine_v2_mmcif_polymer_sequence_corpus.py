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
    MMCIF_PARSER_VERSION,
    MMCIF_WRITER_VERSION,
    StructureParseError,
    parse_mmcif,
)
from betelgeuze_engine_v2.molecular.mmcif_nonpoly_identity import (
    MMCIF_NONPOLY_IDENTITY_ENVELOPE_VERSION,
)
from betelgeuze_engine_v2.molecular.mmcif_polymer_sequence import (
    MAX_MMCIF_POLYMER_SEQUENCE_INPUT_BYTES,
    MAX_MMCIF_POLYMER_SEQUENCE_ROWS,
    MAX_MMCIF_POLYMER_SEQUENCE_TOKEN_CHARS,
    MMCIF_ENTITY_POLY_SEQ_HEADERS,
    MMCIF_POLYMER_SEQUENCE_ENVELOPE_VERSION,
    MMCIF_POLYMER_SEQUENCE_PARSER_NAME,
    MMCIF_POLYMER_SEQUENCE_PARSER_VERSION,
    MMCIF_POLYMER_SEQUENCE_PROFILE_ID,
    MMCIF_POLYMER_SEQUENCE_PROJECTION_SCHEMA_ID,
    MMCIF_POLYMER_SEQUENCE_RECORD_STATE_SCHEMA_ID,
    MMCIF_POLYMER_SEQUENCE_ROUND_TRIP_REPORT_SCHEMA_ID,
    MMCIF_POLYMER_SEQUENCE_SOURCE_BINDING_SCHEMA_ID,
    MMCIF_POLYMER_SEQUENCE_WRITER_VERSION,
    MMCIF_POLYMER_SEQUENCE_WRITE_RECEIPT_SCHEMA_ID,
    MmcifPolymerSequenceError,
    parse_mmcif_polymer_sequence,
    round_trip_mmcif_polymer_sequence_source,
)


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = (
    ROOT / "config" / "independent_engine_v2_v2_1_mmcif_polymer_sequence_corpus.json"
)
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "v2_1_mmcif_polymer_sequence"
CORPUS_SCHEMA_ID = "betelgeuze.v2_1_mmcif_polymer_sequence_corpus/1.0.0"
CORPUS_ID = "v2_1_strict_mmcif_source_reported_polymer_sequence_membership_envelope_v1"
PAYLOAD_HASH_POLICY_ID = "sha256_canonical_json_without_payload_sha256/1.0.0"
EXPECTED_PAYLOAD_SHA256 = (
    "accee9d4f69cd85c069f2b58d515f0a5ea4b0bccce3d90b7422b54b295ced289"
)
_LOWER_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_CASE_ID = re.compile(r"^[a-z0-9_]+$")

_ROUND_TRIP_CASE_IDS = {
    "category_order_variant",
    "interleaved_two_polymer_entities",
    "mixed_polymer_nonpoly_water",
    "opaque_nonstandard_monomer",
    "shared_entity_multiple_asym",
    "single_polymer_complete",
    "unobserved_source_member",
}
_FAILURE_CODES = {
    "failure_atom_join": "polymer_atom_sequence_join_mismatch",
    "failure_category_surface": "unsupported_category_surface",
    "failure_entity_coverage": "polymer_entity_sequence_coverage_mismatch",
    "failure_header_order": "unsupported_category_headers",
    "failure_hetero_yes": "microheterogeneity_not_supported",
    "failure_non_ascii": "non_ascii_input",
    "failure_noncontiguous": "noncontiguous_sequence_positions",
}
_FALSE_GATES = (
    "source_authenticated",
    "auth_label_equivalence_inferred",
    "reference_sequence_equivalence_assessed",
    "coordinate_observation_completeness_assessed",
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
    "coordinate_observed_sequence_row_count",
    "coordinate_unobserved_sequence_row_count",
    "full_source_sha256",
    "nonpoly_identity_projection_sha256",
    "nonpoly_identity_record_state_sha256",
    "output_byte_count",
    "output_equals_input",
    "output_source_sha256",
    "polymer_sequence_projection_sha256",
    "polymer_sequence_row_count",
    "record_state_sha256",
    "round_trip_report_sha256",
    "second_emission_byte_stable",
    "source_binding_sha256",
    "source_id_sha256",
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
_EXPECTED_COUNT_KEYS = {
    "coordinate_observed_sequence_row_count",
    "coordinate_unobserved_sequence_row_count",
    "output_byte_count",
    "polymer_sequence_row_count",
}
_EXPECTED_BOOLEAN_KEYS = {
    "output_equals_input",
    "second_emission_byte_stable",
}
_MAX_MANIFEST_BYTES = 1024 * 1024


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
        manifest_root = (ROOT / "config").resolve(strict=True)
        manifest_path = MANIFEST.resolve(strict=True)
        if (
            manifest_path.parent != manifest_root
            or manifest_path.name
            != "independent_engine_v2_v2_1_mmcif_polymer_sequence_corpus.json"
            or not manifest_path.is_file()
            or manifest_path.stat().st_size > _MAX_MANIFEST_BYTES
        ):
            raise CorpusManifestError("manifest is absent or exceeds its byte cap")
        text = manifest_path.read_text(encoding="utf-8")
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
    expected_prefix = ("tests", "fixtures", "v2_1_mmcif_polymer_sequence")
    if pure.is_absolute() or ".." in pure.parts or pure.parts[:3] != expected_prefix:
        raise CorpusManifestError("fixture path escapes the selected corpus root")
    fixture_root = FIXTURE_ROOT.resolve(strict=True)
    try:
        path = ROOT.joinpath(*pure.parts).resolve(strict=True)
    except OSError as exc:
        raise CorpusManifestError("fixture path is not resolvable") from exc
    if path.parent != fixture_root or not path.is_file():
        raise CorpusManifestError("fixture path is outside the selected corpus root")
    if path.stat().st_size > MAX_MMCIF_POLYMER_SEQUENCE_INPUT_BYTES:
        raise CorpusManifestError("fixture exceeds the parser input byte cap")
    payload = path.read_bytes()
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
        try:
            old = bytes.fromhex(replacement["old_hex"])
            new = bytes.fromhex(replacement["new_hex"])
        except (TypeError, ValueError) as exc:
            raise CorpusManifestError(
                "fixture replacement must use hex strings"
            ) from exc
        if not old or payload.count(old) != 1:
            raise CorpusManifestError("fixture replacement source is not unique")
        payload = payload.replace(old, new, 1)
        if len(payload) > MAX_MMCIF_POLYMER_SEQUENCE_INPUT_BYTES:
            raise CorpusManifestError(
                "replaced fixture exceeds the parser input byte cap"
            )
    return path, payload


def _replay(case: dict[str, Any]) -> tuple[dict[str, Any], Any]:
    _path, source = _resolve_source(case["source"])
    assert hashlib.sha256(source).hexdigest() == case["source_sha256"]
    result = round_trip_mmcif_polymer_sequence_source(
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
            "canonical_carrier_source_sha256": ingest.canonical_carrier_source_sha256,
            "carrier_kind": ingest.carrier_kind,
            "carrier_source_sha256": ingest.carrier_source_sha256,
            "coordinate_observed_sequence_row_count": receipt.coordinate_observed_sequence_row_count,
            "coordinate_unobserved_sequence_row_count": receipt.coordinate_unobserved_sequence_row_count,
            "full_source_sha256": ingest.full_source_sha256,
            "nonpoly_identity_projection_sha256": ingest.nonpoly_identity_projection_sha256,
            "nonpoly_identity_record_state_sha256": ingest.nonpoly_identity_record_state_sha256,
            "output_byte_count": receipt.output_byte_count,
            "output_equals_input": result.write_result.payload == source,
            "output_source_sha256": receipt.output_source_sha256,
            "polymer_sequence_projection_sha256": ingest.polymer_sequence_projection_sha256,
            "polymer_sequence_row_count": len(ingest.sequence_rows),
            "record_state_sha256": ingest.record_state_sha256,
            "round_trip_report_sha256": result.report.report_sha256,
            "second_emission_byte_stable": result.report.second_emission_byte_stable,
            "source_binding_sha256": ingest.source_binding_sha256,
            "source_id_sha256": ingest.source_id_sha256,
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
        str((FIXTURE_ROOT / "single_polymer_complete.cif").resolve()),
        "../tests/fixtures/v2_1_mmcif_polymer_sequence/single_polymer_complete.cif",
        "tests/fixtures/v2_1_mmcif_nonpoly_identity/single_hem_complete.cif",
    ),
    ids=("absolute", "parent_traversal", "wrong_fixture_root"),
)
def test_fixture_resolver_rejects_paths_outside_exact_corpus(path: str) -> None:
    with pytest.raises(CorpusManifestError):
        _resolve_source({"kind": "fixture", "path": path})


def test_manifest_contract_versions_profiles_orders_and_limits_are_exact() -> None:
    assert _load_manifest()["contracts"] == {
        "all_atom_schema_id": ALL_ATOM_SCHEMA_ID,
        "base_mmcif_parser_version": MMCIF_PARSER_VERSION,
        "base_mmcif_writer_version": MMCIF_WRITER_VERSION,
        "nonpoly_identity_envelope_version": MMCIF_NONPOLY_IDENTITY_ENVELOPE_VERSION,
        "envelope_version": MMCIF_POLYMER_SEQUENCE_ENVELOPE_VERSION,
        "envelope_parser_version": MMCIF_POLYMER_SEQUENCE_PARSER_VERSION,
        "envelope_writer_version": MMCIF_POLYMER_SEQUENCE_WRITER_VERSION,
        "parser_name": MMCIF_POLYMER_SEQUENCE_PARSER_NAME,
        "profile_id": MMCIF_POLYMER_SEQUENCE_PROFILE_ID,
        "projection_schema_id": MMCIF_POLYMER_SEQUENCE_PROJECTION_SCHEMA_ID,
        "record_state_schema_id": MMCIF_POLYMER_SEQUENCE_RECORD_STATE_SCHEMA_ID,
        "source_binding_schema_id": MMCIF_POLYMER_SEQUENCE_SOURCE_BINDING_SCHEMA_ID,
        "write_receipt_schema_id": MMCIF_POLYMER_SEQUENCE_WRITE_RECEIPT_SCHEMA_ID,
        "round_trip_report_schema_id": MMCIF_POLYMER_SEQUENCE_ROUND_TRIP_REPORT_SCHEMA_ID,
        "projection_scope": "source_reported_polymer_entity_sequence_membership_and_coordinate_presence_only",
        "entity_poly_seq_headers": [
            tag.split(".", 1)[1] for tag in MMCIF_ENTITY_POLY_SEQ_HEADERS
        ],
        "carrier_kinds": ["common_core21", "mmcif_nonpoly_identity"],
        "canonical_category_orders": {
            "common_core21": [
                "_entity",
                "_struct_asym",
                "_entity_poly_seq",
                "_atom_site",
            ],
            "mmcif_nonpoly_identity": [
                "_entity",
                "_struct_asym",
                "_entity_poly_seq",
                "_pdbx_entity_nonpoly",
                "_pdbx_nonpoly_scheme",
                "_atom_site",
            ],
        },
        "limits": {
            "max_input_bytes": MAX_MMCIF_POLYMER_SEQUENCE_INPUT_BYTES,
            "max_sequence_rows": MAX_MMCIF_POLYMER_SEQUENCE_ROWS,
            "max_selected_token_chars": MAX_MMCIF_POLYMER_SEQUENCE_TOKEN_CHARS,
        },
    }


def test_manifest_claim_boundary_is_exactly_nonpromoting() -> None:
    assert _load_manifest()["claim_boundary"] == {
        "positive_true_fields": [
            "source_reported_sequence_preserved",
            "coordinate_absent_rows_preserved_without_missingness_claim",
        ],
        "always_false_fields": list(_FALSE_GATES),
        "base_parser_default_changed": False,
        "microheterogeneity_supported": False,
        "general_mmcif_round_trip_evidence_ready": False,
        "v2_1_complete": False,
    }


def test_case_shapes_hashes_and_fixture_closure_are_exact() -> None:
    cases = _load_manifest()["cases"]
    assert type(cases) is list and len(cases) == 14
    assert [case["case_id"] for case in cases] == sorted(
        _ROUND_TRIP_CASE_IDS | set(_FAILURE_CODES)
    )
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
        assert _LOWER_SHA256.fullmatch(case["source_sha256"])
        assert type(case["source_id"]) is str
        path, source = _resolve_source(case["source"])
        assert hashlib.sha256(source).hexdigest() == case["source_sha256"]
        referenced.add(path.resolve())
        if case["lane"] == "round_trip":
            assert case["case_id"] in _ROUND_TRIP_CASE_IDS
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
                    assert value in {"common_core21", "mmcif_nonpoly_identity"}
        else:
            assert case["lane"] == "parse_failure"
            assert case["expected"] == {"error_code": _FAILURE_CODES[case["case_id"]]}
    assert referenced == {path.resolve() for path in FIXTURE_ROOT.glob("*.cif")}


@pytest.mark.parametrize("case_id", sorted(_ROUND_TRIP_CASE_IDS))
def test_round_trip_cases_replay_exact_digests_and_keep_authority_false(
    case_id: str,
) -> None:
    case = next(row for row in _load_manifest()["cases"] if row["case_id"] == case_id)
    actual, result = _replay(case)
    assert actual == case["expected"]
    for artifact in (
        result.source_ingest.to_dict(),
        result.write_result.receipt.to_dict(),
        result.report.to_dict(),
        result.to_dict(),
    ):
        assert artifact["source_reported_sequence_preserved"] is True
        assert (
            artifact["coordinate_absent_rows_preserved_without_missingness_claim"]
            is True
        )
        for field in _FALSE_GATES:
            assert artifact[field] is False

    with pytest.raises(StructureParseError) as exc_info:
        _path, source = _resolve_source(case["source"])
        parse_mmcif(source, source_id=case_id)
    assert exc_info.value.code == "unsupported_context_category"


@pytest.mark.parametrize("case_id", sorted(_FAILURE_CODES))
def test_failure_cases_replay_exact_codes_without_raw_context(case_id: str) -> None:
    case = next(row for row in _load_manifest()["cases"] if row["case_id"] == case_id)
    _path, source = _resolve_source(case["source"])
    with pytest.raises(MmcifPolymerSequenceError) as exc_info:
        parse_mmcif_polymer_sequence(source, source_id=case["source_id"])
    assert exc_info.value.code == _FAILURE_CODES[case_id]
    if case_id == "failure_non_ascii":
        assert exc_info.value.__cause__ is None
        assert exc_info.value.__context__ is None
        assert "PRIVATE" not in str(exc_info.value)


def test_category_order_pair_has_same_semantics_but_distinct_source_binding() -> None:
    cases = {row["case_id"]: row for row in _load_manifest()["cases"]}
    canonical = cases["single_polymer_complete"]["expected"]
    reordered = cases["category_order_variant"]["expected"]
    assert (
        canonical["polymer_sequence_projection_sha256"]
        == reordered["polymer_sequence_projection_sha256"]
    )
    assert canonical["record_state_sha256"] == reordered["record_state_sha256"]
    assert canonical["output_source_sha256"] == reordered["output_source_sha256"]
    assert canonical["source_binding_sha256"] != reordered["source_binding_sha256"]
    assert canonical["write_receipt_sha256"] != reordered["write_receipt_sha256"]


def test_only_mixed_case_uses_nonpoly_composition() -> None:
    cases = {
        row["case_id"]: row["expected"]
        for row in _load_manifest()["cases"]
        if row["lane"] == "round_trip"
    }
    for case_id, expected in cases.items():
        composed = case_id == "mixed_polymer_nonpoly_water"
        assert (expected["carrier_kind"] == "mmcif_nonpoly_identity") is composed
        assert (expected["nonpoly_identity_projection_sha256"] is not None) is composed
        assert (
            expected["nonpoly_identity_record_state_sha256"] is not None
        ) is composed
