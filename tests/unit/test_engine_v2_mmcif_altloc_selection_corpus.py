from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from typing import Any

import pytest

from betelgeuze_engine_v2.molecular.mmcif_altloc_selection import (
    MAX_MMCIF_ALTLOC_SELECTION_ALTLOC_ID_CHARS,
    MAX_MMCIF_ALTLOC_SELECTION_ATOM_ROWS,
    MAX_MMCIF_ALTLOC_SELECTION_ENTITY_ROWS,
    MAX_MMCIF_ALTLOC_SELECTION_INPUT_BYTES,
    MAX_MMCIF_ALTLOC_SELECTION_OUTPUT_BYTES,
    MAX_MMCIF_ALTLOC_SELECTION_OUTPUT_LINE_CHARS,
    MAX_MMCIF_ALTLOC_SELECTION_PROJECTION_BYTES,
    MAX_MMCIF_ALTLOC_SELECTION_SOURCE_ID_BYTES,
    MAX_MMCIF_ALTLOC_SELECTION_STRUCT_ASYM_ROWS,
    MAX_MMCIF_ALTLOC_SELECTION_TOKEN_CHARS,
    MMCIF_ALTLOC_RECORD_STATE_SCHEMA_ID,
    MMCIF_ALTLOC_ROUND_TRIP_REPORT_SCHEMA_ID,
    MMCIF_ALTLOC_SELECTED_STATE_SCHEMA_ID,
    MMCIF_ALTLOC_SELECTION_ATOM_SITE_HEADERS,
    MMCIF_ALTLOC_SELECTION_ENTITY_HEADERS,
    MMCIF_ALTLOC_SELECTION_ENVELOPE_VERSION,
    MMCIF_ALTLOC_SELECTION_PARSER_VERSION,
    MMCIF_ALTLOC_SELECTION_PROFILE_ID,
    MMCIF_ALTLOC_SELECTION_PROJECTION_SCOPE,
    MMCIF_ALTLOC_SELECTION_STRUCT_ASYM_HEADERS,
    MMCIF_ALTLOC_SELECTION_WRITER_VERSION,
    MMCIF_ALTLOC_SOURCE_BINDING_SCHEMA_ID,
    MMCIF_ALTLOC_SOURCE_PROJECTION_SCHEMA_ID,
    MMCIF_ALTLOC_WRITE_RECEIPT_SCHEMA_ID,
    MmcifAltlocSelectionError,
    parse_mmcif_altloc_selection,
    round_trip_mmcif_altloc_selection_source,
)
from betelgeuze_engine_v2.molecular.mmcif_writer import MMCIF_WRITER_VERSION
from betelgeuze_engine_v2.molecular.pdb_mmcif import MMCIF_PARSER_VERSION


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = (
    ROOT / "config" / "independent_engine_v2_v2_1_mmcif_altloc_selection_corpus.json"
)
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "v2_1_mmcif_altloc_selection"
CORPUS_SCHEMA_ID = "betelgeuze.v2_1_mmcif_altloc_selection_corpus/1.0.0"
CORPUS_ID = "v2_1_strict_mmcif_explicit_altloc_selection_envelope_v1"
PAYLOAD_HASH_POLICY_ID = "sha256_canonical_json_without_payload_sha256/1.0.0"
EXPECTED_PAYLOAD_SHA256 = (
    "652ff9e1c1f849e8f9978fbf57e50ef8b2f1bd80349dde06cf2c1a34ee411625"
)

_LOWER_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_CASE_ID = re.compile(r"^[a-z0-9_]+$")
_MAX_MANIFEST_BYTES = 512 * 1024
_MAX_FIXTURE_BYTES = 16 * 1024
_MAX_TOTAL_FIXTURE_BYTES = 96 * 1024

_ROUND_TRIP_CASE_IDS = (
    "select_a_with_blank",
    "select_b_with_blank",
    "multi_character_ids",
    "multiple_affected_residues",
    "mixed_entity_types",
    "category_order_numeric_markers",
)
_FAILURE_CASES = {
    "failure_no_altloc": "requested_altloc_not_present",
    "failure_requested_id_absent": "requested_altloc_missing_for_residue",
    "failure_requested_id_missing_for_residue": (
        "requested_altloc_missing_for_residue"
    ),
    "failure_inconsistent_atom_identity": "inconsistent_altloc_atom_identity",
    "failure_inconsistent_type_symbol": "inconsistent_altloc_atom_identity",
    "failure_blank_collision": "altloc_blank_collision",
    "failure_duplicate_altloc_identity": "duplicate_altloc_atom_identity",
    "failure_duplicate_atom_site_id": "duplicate_atom_site_id",
    "failure_second_model": "unsupported_model_id",
    "failure_quoted_token": "unsafe_cif_token",
    "failure_numeric_uncertainty": "numeric_uncertainty_unsupported",
    "failure_entity_type": "unsupported_category_representation",
    "failure_header_order": "unsupported_category_headers",
    "failure_partial_auth_identity": "unsupported_category_representation",
    "failure_unsupported_category": "unsupported_category_surface",
}

_FALSE_GATES = (
    "source_authenticated",
    "auth_label_equivalence_inferred",
    "coordinate_observation_completeness_assessed",
    "altloc_population_interpreted",
    "occupancy_population_interpreted",
    "occupancy_weighting_applied",
    "refinement_validity_assessed",
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
    "runtime_eligible",
    "simulation_ready",
    "execution_authorized",
    "claim_safe",
    "general_mmcif_round_trip_evidence_ready",
    "all_format_round_trip_evidence_ready",
)

_EXPECTED_EVIDENCE_KEYS = {
    "affected_residue_count",
    "altloc_id",
    "discarded_atom_row_count",
    "emitted_source_reparsed_exact",
    "entity_row_count",
    "full_source_sha256",
    "output_byte_count",
    "output_equals_input",
    "output_source_sha256",
    "record_state_sha256",
    "round_trip_report_sha256",
    "second_emission_byte_stable",
    "selected_altloc_ids",
    "selected_atom_row_count",
    "selected_state_equal",
    "selected_state_sha256",
    "source_atom_row_count",
    "source_binding_sha256",
    "source_id_sha256",
    "source_projection_equal",
    "source_projection_sha256",
    "struct_asym_row_count",
    "system_snapshot_sha256",
    "topology_equal",
    "topology_sha256",
    "write_receipt_sha256",
}


class AltlocSelectionCorpusError(ValueError):
    pass


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    document: dict[str, Any] = {}
    for key, value in pairs:
        if key in document:
            raise AltlocSelectionCorpusError("duplicate manifest key")
        document[key] = value
    return document


def _parse_bounded_integer(token: str) -> int:
    digits = token[1:] if token.startswith("-") else token
    if len(digits) > 20:
        raise AltlocSelectionCorpusError("JSON integer exceeds corpus bounds")
    return int(token)


def _parse_manifest_json(text: str) -> dict[str, Any]:
    try:
        value = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=lambda _token: (_ for _ in ()).throw(
                AltlocSelectionCorpusError("nonstandard JSON constant")
            ),
            parse_float=lambda _token: (_ for _ in ()).throw(
                AltlocSelectionCorpusError("floating JSON number")
            ),
            parse_int=_parse_bounded_integer,
        )
    except (json.JSONDecodeError, RecursionError) as exc:
        raise AltlocSelectionCorpusError("manifest must be strict JSON") from exc
    if type(value) is not dict:
        raise AltlocSelectionCorpusError("manifest root must be an object")
    return value


def _load_manifest() -> dict[str, Any]:
    try:
        config_root = (ROOT / "config").resolve(strict=True)
        path = MANIFEST.resolve(strict=True)
        if (
            path.parent != config_root
            or path.name
            != "independent_engine_v2_v2_1_mmcif_altloc_selection_corpus.json"
            or not path.is_file()
            or path.stat().st_size > _MAX_MANIFEST_BYTES
        ):
            raise AltlocSelectionCorpusError(
                "manifest is absent or exceeds its byte cap"
            )
        text = path.read_text(encoding="utf-8")
        if len(text.encode("utf-8")) > _MAX_MANIFEST_BYTES:
            raise AltlocSelectionCorpusError(
                "manifest is absent or exceeds its byte cap"
            )
    except (OSError, UnicodeError) as exc:
        raise AltlocSelectionCorpusError("manifest must be bounded UTF-8 text") from exc
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


def _fixture_payload(name: str) -> tuple[Path, bytes]:
    if type(name) is not str:
        raise AltlocSelectionCorpusError("fixture name must be text")
    pure = PurePosixPath(name)
    if (
        pure.is_absolute()
        or len(pure.parts) != 1
        or pure.suffix != ".cif"
        or name != pure.name
    ):
        raise AltlocSelectionCorpusError("fixture path escapes the exact corpus root")
    fixture_root = FIXTURE_ROOT.resolve(strict=True)
    try:
        path = (FIXTURE_ROOT / pure.name).resolve(strict=True)
    except OSError as exc:
        raise AltlocSelectionCorpusError("fixture path is not resolvable") from exc
    if path.parent != fixture_root or not path.is_file():
        raise AltlocSelectionCorpusError(
            "fixture path is outside the exact corpus root"
        )
    if path.stat().st_size > _MAX_FIXTURE_BYTES:
        raise AltlocSelectionCorpusError("fixture exceeds its corpus byte cap")
    payload = path.read_bytes()
    if len(payload) > _MAX_FIXTURE_BYTES:
        raise AltlocSelectionCorpusError("fixture exceeds its corpus byte cap")
    if len(payload) > MAX_MMCIF_ALTLOC_SELECTION_INPUT_BYTES:
        raise AltlocSelectionCorpusError("fixture exceeds the parser input byte cap")
    return path, payload


def _replace_once(source: bytes, old: bytes, new: bytes) -> bytes:
    if not old or source.count(old) != 1:
        raise AssertionError("mutation source must occur exactly once")
    return source.replace(old, new, 1)


def _drop_rows_with_ids(source: bytes, *source_ids: bytes) -> bytes:
    prefixes = tuple(b"ATOM " + source_id + b" " for source_id in source_ids)
    return (
        b"\n".join(
            line for line in source.splitlines() if not line.startswith(prefixes)
        )
        + b"\n"
    )


def _with_second_model(source: bytes) -> bytes:
    rows = tuple(
        line for line in source.splitlines() if line.startswith((b"ATOM ", b"HETATM "))
    )
    second_rows = []
    for ordinal, row in enumerate(rows, start=101):
        fields = row.split()
        fields[1] = str(ordinal).encode("ascii")
        fields[-1] = b"2"
        second_rows.append(b" ".join(fields))
    block = b"\n".join(rows)
    return source.replace(block, block + b"\n" + b"\n".join(second_rows), 1)


def _mutate(source: bytes, mutation_id: str) -> bytes:
    if mutation_id == "no_altloc":
        return _drop_rows_with_ids(source, b"2", b"3")
    if mutation_id == "requested_id_absent":
        return source
    if mutation_id == "requested_id_missing_for_residue":
        return _replace_once(
            source,
            b"ATOM 6 C CA B SER",
            b"ATOM 6 C CA C SER",
        )
    if mutation_id == "inconsistent_atom_identity":
        return _replace_once(
            source,
            b"ATOM 3 C CA B GLY A 1 1 ? 2.0 0.0 0.0 0.4 12.0 ? 10 GLY X CA 1\n",
            b"ATOM 3 C CB B GLY A 1 1 ? 2.0 0.0 0.0 0.4 12.0 ? 10 GLY X CB 1\n",
        )
    if mutation_id == "inconsistent_type_symbol":
        return _replace_once(
            source,
            b"ATOM 3 C CA B GLY",
            b"ATOM 3 N CA B GLY",
        )
    if mutation_id == "blank_collision":
        return _replace_once(
            source,
            b"ATOM 3 C CA B GLY",
            b"ATOM 3 C CA . GLY",
        )
    if mutation_id == "duplicate_altloc_identity":
        return _replace_once(
            source,
            b"ATOM 3 C CA B GLY",
            b"ATOM 22 C CA A GLY A 1 1 ? 1.0 0.0 0.0 0.6 11.0 ? "
            b"10 GLY X CA 1\nATOM 3 C CA B GLY",
        )
    if mutation_id == "duplicate_atom_site_id":
        return _replace_once(
            source,
            b"ATOM 3 C CA B GLY",
            b"ATOM 2 C CA B GLY",
        )
    if mutation_id == "second_model":
        return _with_second_model(source)
    if mutation_id == "quoted_token":
        return _replace_once(source, b" CA A GLY ", b" CA 'A' GLY ")
    if mutation_id == "numeric_uncertainty":
        return _replace_once(
            source,
            b" 1.0 0.0 0.0 0.6 ",
            b" 1.0(1) 0.0 0.0 0.6 ",
        )
    if mutation_id == "entity_type":
        return _replace_once(source, b"1 polymer\n#", b"1 branched\n#")
    if mutation_id == "header_order":
        return _replace_once(
            source,
            b"_entity.id\n_entity.type",
            b"_entity.type\n_entity.id",
        )
    if mutation_id == "partial_auth_identity":
        return _replace_once(
            source,
            b"ATOM 2 C CA A GLY A 1 1 ? 1.0 0.0 0.0 0.6 11.0 ? 10 GLY X CA 1\n",
            b"ATOM 2 C CA A GLY A 1 1 ? 1.0 0.0 0.0 0.6 11.0 ? 10 GLY X ? 1\n",
        )
    if mutation_id == "unsupported_category":
        section = b"_cell.length_a 10.0\n#\n"
        marker = b"loop_\n_atom_site.group_PDB"
        return _replace_once(source, marker, section + marker)
    raise AltlocSelectionCorpusError("unknown corpus mutation")


def _replay(case: dict[str, Any]) -> tuple[dict[str, Any], Any]:
    _path, source = _fixture_payload(case["fixture"])
    result = round_trip_mmcif_altloc_selection_source(
        source,
        altloc_id=case["altloc_id"],
        source_id=case["source_id"],
    )
    ingest = result.source_ingest
    receipt = result.write_result.receipt
    report = result.report
    return (
        {
            "affected_residue_count": ingest.affected_residue_count,
            "altloc_id": ingest.altloc_id,
            "discarded_atom_row_count": ingest.discarded_atom_row_count,
            "emitted_source_reparsed_exact": report.emitted_source_reparsed_exact,
            "entity_row_count": ingest.entity_row_count,
            "full_source_sha256": ingest.full_source_sha256,
            "output_byte_count": len(result.write_result.payload),
            "output_equals_input": result.write_result.payload == source,
            "output_source_sha256": receipt.output_source_sha256,
            "record_state_sha256": ingest.record_state_sha256,
            "round_trip_report_sha256": report.report_sha256,
            "second_emission_byte_stable": report.second_emission_byte_stable,
            "selected_altloc_ids": [atom.altloc for atom in ingest.system.atoms],
            "selected_atom_row_count": ingest.selected_atom_row_count,
            "selected_state_equal": report.selected_state_equal,
            "selected_state_sha256": ingest.selected_state_sha256,
            "source_atom_row_count": ingest.source_atom_row_count,
            "source_binding_sha256": ingest.source_binding_sha256,
            "source_id_sha256": ingest.source_id_sha256,
            "source_projection_equal": report.source_projection_equal,
            "source_projection_sha256": ingest.source_projection_sha256,
            "struct_asym_row_count": ingest.struct_asym_row_count,
            "system_snapshot_sha256": ingest.system_snapshot_sha256,
            "topology_equal": report.topology_equal,
            "topology_sha256": ingest.topology_sha256,
            "write_receipt_sha256": receipt.receipt_sha256,
        },
        result,
    )


def _expected_contracts() -> dict[str, Any]:
    return {
        "atom_site_headers": list(MMCIF_ALTLOC_SELECTION_ATOM_SITE_HEADERS),
        "base_mmcif_parser_version": MMCIF_PARSER_VERSION,
        "base_mmcif_writer_version": MMCIF_WRITER_VERSION,
        "entity_headers": list(MMCIF_ALTLOC_SELECTION_ENTITY_HEADERS),
        "envelope_version": MMCIF_ALTLOC_SELECTION_ENVELOPE_VERSION,
        "parser_version": MMCIF_ALTLOC_SELECTION_PARSER_VERSION,
        "profile_id": MMCIF_ALTLOC_SELECTION_PROFILE_ID,
        "projection_scope": MMCIF_ALTLOC_SELECTION_PROJECTION_SCOPE,
        "record_state_schema_id": MMCIF_ALTLOC_RECORD_STATE_SCHEMA_ID,
        "round_trip_report_schema_id": MMCIF_ALTLOC_ROUND_TRIP_REPORT_SCHEMA_ID,
        "selected_state_schema_id": MMCIF_ALTLOC_SELECTED_STATE_SCHEMA_ID,
        "source_binding_schema_id": MMCIF_ALTLOC_SOURCE_BINDING_SCHEMA_ID,
        "source_projection_schema_id": MMCIF_ALTLOC_SOURCE_PROJECTION_SCHEMA_ID,
        "struct_asym_headers": list(MMCIF_ALTLOC_SELECTION_STRUCT_ASYM_HEADERS),
        "write_receipt_schema_id": MMCIF_ALTLOC_WRITE_RECEIPT_SCHEMA_ID,
        "writer_version": MMCIF_ALTLOC_SELECTION_WRITER_VERSION,
    }


def _assert_evidence_types(evidence: dict[str, Any]) -> None:
    integer_fields = {
        "affected_residue_count",
        "discarded_atom_row_count",
        "entity_row_count",
        "output_byte_count",
        "selected_atom_row_count",
        "source_atom_row_count",
        "struct_asym_row_count",
    }
    boolean_fields = {
        "emitted_source_reparsed_exact",
        "output_equals_input",
        "second_emission_byte_stable",
        "selected_state_equal",
        "source_projection_equal",
        "topology_equal",
    }
    assert all(type(evidence[field]) is int for field in integer_fields)
    assert all(type(evidence[field]) is bool for field in boolean_fields)
    assert type(evidence["altloc_id"]) is str
    assert type(evidence["selected_altloc_ids"]) is list
    assert all(type(value) is str for value in evidence["selected_altloc_ids"])
    for key, value in evidence.items():
        if key.endswith("_sha256"):
            assert type(value) is str and _LOWER_SHA256.fullmatch(value)


def test_manifest_payload_hash_and_inventory_are_exact() -> None:
    document = _load_manifest()
    assert set(document) == {
        "schema_id",
        "corpus_id",
        "payload_hash_policy_id",
        "payload_sha256",
        "contracts",
        "claim_boundary",
        "limits",
        "false_claims",
        "fixtures",
        "cases",
    }
    assert document["schema_id"] == CORPUS_SCHEMA_ID
    assert document["corpus_id"] == CORPUS_ID
    assert document["payload_hash_policy_id"] == PAYLOAD_HASH_POLICY_ID
    assert document["payload_sha256"] == EXPECTED_PAYLOAD_SHA256
    assert _payload_sha256(document) == EXPECTED_PAYLOAD_SHA256


@pytest.mark.parametrize(
    "payload",
    (
        '{"schema_id":"first","schema_id":"second"}',
        '{"value":NaN}',
        '{"value":1.5}',
        '{"value":100000000000000000000}',
        "[]",
    ),
)
def test_manifest_loader_rejects_noncanonical_json(payload: str) -> None:
    with pytest.raises(AltlocSelectionCorpusError):
        _parse_manifest_json(payload)


@pytest.mark.parametrize(
    "name",
    (
        str((FIXTURE_ROOT / "select_a_with_blank.cif").resolve()),
        "../select_a_with_blank.cif",
        "v2_1_mmcif_altloc_selection/select_a_with_blank.cif",
        "./select_a_with_blank.cif",
        "select_a_with_blank.cif/",
        "select_a_with_blank.cif/.",
        "select_a_with_blank.txt",
    ),
)
def test_fixture_resolver_rejects_paths_outside_exact_corpus(name: str) -> None:
    with pytest.raises(AltlocSelectionCorpusError):
        _fixture_payload(name)


def test_manifest_contract_limits_boundaries_and_false_claims_are_exact() -> None:
    document = _load_manifest()
    assert document["contracts"] == _expected_contracts()
    assert document["claim_boundary"] == {
        "all_source_atom_rows_preserved": True,
        "explicit_altloc_selection_required": True,
        "selected_coordinate_projection_only": True,
        "source_altloc_population_interpreted": False,
        "source_occupancy_population_interpreted": False,
    }
    assert document["limits"] == {
        "altloc_id_characters": MAX_MMCIF_ALTLOC_SELECTION_ALTLOC_ID_CHARS,
        "atom_rows": MAX_MMCIF_ALTLOC_SELECTION_ATOM_ROWS,
        "entity_rows": MAX_MMCIF_ALTLOC_SELECTION_ENTITY_ROWS,
        "input_bytes": MAX_MMCIF_ALTLOC_SELECTION_INPUT_BYTES,
        "output_bytes": MAX_MMCIF_ALTLOC_SELECTION_OUTPUT_BYTES,
        "output_line_characters": MAX_MMCIF_ALTLOC_SELECTION_OUTPUT_LINE_CHARS,
        "projection_bytes": MAX_MMCIF_ALTLOC_SELECTION_PROJECTION_BYTES,
        "source_id_utf8_bytes": MAX_MMCIF_ALTLOC_SELECTION_SOURCE_ID_BYTES,
        "struct_asym_rows": MAX_MMCIF_ALTLOC_SELECTION_STRUCT_ASYM_ROWS,
        "token_characters": MAX_MMCIF_ALTLOC_SELECTION_TOKEN_CHARS,
    }
    assert document["false_claims"] == {field: False for field in _FALSE_GATES}


def test_fixture_inventory_case_shapes_and_hashes_are_exact() -> None:
    document = _load_manifest()
    fixtures = document["fixtures"]
    assert type(fixtures) is list and len(fixtures) == 6
    referenced: set[Path] = set()
    total_bytes = 0
    for fixture in fixtures:
        assert type(fixture) is dict and set(fixture) == {
            "path",
            "byte_count",
            "sha256",
        }
        pure = PurePosixPath(fixture["path"])
        assert pure.parts[:3] == (
            "tests",
            "fixtures",
            "v2_1_mmcif_altloc_selection",
        )
        assert len(pure.parts) == 4 and ".." not in pure.parts
        path, payload = _fixture_payload(pure.name)
        assert path == ROOT.joinpath(*pure.parts).resolve(strict=True)
        assert len(payload) == fixture["byte_count"]
        assert type(fixture["byte_count"]) is int
        assert type(fixture["sha256"]) is str
        assert hashlib.sha256(payload).hexdigest() == fixture["sha256"]
        assert _LOWER_SHA256.fullmatch(fixture["sha256"])
        referenced.add(path)
        total_bytes += len(payload)
    assert referenced == {path.resolve() for path in FIXTURE_ROOT.glob("*.cif")}
    assert total_bytes <= _MAX_TOTAL_FIXTURE_BYTES

    cases = document["cases"]
    assert type(cases) is list
    assert [case["case_id"] for case in cases] == [
        *_ROUND_TRIP_CASE_IDS,
        *_FAILURE_CASES,
    ]
    for case in cases:
        assert type(case["case_id"]) is str and _CASE_ID.fullmatch(case["case_id"])
        _fixture_payload(case["fixture"])
        if case["kind"] == "round_trip":
            assert set(case) == {
                "case_id",
                "kind",
                "fixture",
                "altloc_id",
                "source_id",
                "expected",
            }
            assert set(case["expected"]) == _EXPECTED_EVIDENCE_KEYS
            assert type(case["altloc_id"]) is str
            assert type(case["source_id"]) is str
            _assert_evidence_types(case["expected"])
        else:
            assert case["kind"] == "failure"
            assert set(case) == {
                "case_id",
                "kind",
                "fixture",
                "altloc_id",
                "mutation_id",
                "expected_error_code",
                "source_sha256",
            }
            assert case["expected_error_code"] == _FAILURE_CASES[case["case_id"]]
            assert _LOWER_SHA256.fullmatch(case["source_sha256"])


@pytest.mark.parametrize("case_id", _ROUND_TRIP_CASE_IDS)
def test_round_trip_cases_replay_all_bound_evidence(case_id: str) -> None:
    case = next(row for row in _load_manifest()["cases"] if row["case_id"] == case_id)
    actual, result = _replay(case)
    _assert_evidence_types(actual)
    assert actual == case["expected"]
    for artifact in (
        result.source_ingest.to_dict(),
        result.write_result.receipt.to_dict(),
        result.report.to_dict(),
        result.to_dict(),
    ):
        for field in _FALSE_GATES:
            assert artifact[field] is False
    assert result.write_result.payload == result.reemitted_write_result.payload
    assert result.report.second_emission_byte_stable is True


@pytest.mark.parametrize("case_id", tuple(_FAILURE_CASES))
def test_failure_cases_replay_exact_typed_codes(case_id: str) -> None:
    case = next(row for row in _load_manifest()["cases"] if row["case_id"] == case_id)
    _path, source = _fixture_payload(case["fixture"])
    mutated = _mutate(source, case["mutation_id"])
    assert hashlib.sha256(mutated).hexdigest() == case["source_sha256"]
    with pytest.raises(MmcifAltlocSelectionError) as exc_info:
        parse_mmcif_altloc_selection(
            mutated,
            altloc_id=case["altloc_id"],
            source_id=case_id,
        )
    assert exc_info.value.code == case["expected_error_code"]
    assert exc_info.value.__cause__ is None
    assert "AUTH-1" not in str(exc_info.value)
