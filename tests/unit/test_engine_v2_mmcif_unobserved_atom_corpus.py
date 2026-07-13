from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from typing import Any

import pytest

from betelgeuze_engine_v2.molecular.mmcif_nonpoly_identity import (
    MMCIF_NONPOLY_IDENTITY_ENVELOPE_VERSION,
)
from betelgeuze_engine_v2.molecular.mmcif_polymer_sequence import (
    MMCIF_POLYMER_SEQUENCE_ENVELOPE_VERSION,
    MmcifPolymerSequenceError,
    parse_mmcif_polymer_sequence,
)
from betelgeuze_engine_v2.molecular.mmcif_unobserved_atoms import (
    MAX_MMCIF_UNOBSERVED_ATOM_INPUT_BYTES,
    MAX_MMCIF_UNOBSERVED_ATOM_ROWS,
    MAX_MMCIF_UNOBSERVED_ATOM_SOURCE_ID_BYTES,
    MAX_MMCIF_UNOBSERVED_ATOM_TOKEN_CHARS,
    MMCIF_UNOBSERVED_ATOM_ENVELOPE_VERSION,
    MMCIF_UNOBSERVED_ATOM_HEADERS,
    MMCIF_UNOBSERVED_ATOM_PARSER_VERSION,
    MMCIF_UNOBSERVED_ATOM_PROFILE_ID,
    MMCIF_UNOBSERVED_ATOM_PROJECTION_SCHEMA_ID,
    MMCIF_UNOBSERVED_ATOM_PROJECTION_SCOPE,
    MMCIF_UNOBSERVED_ATOM_RECORD_STATE_SCHEMA_ID,
    MMCIF_UNOBSERVED_ATOM_ROUND_TRIP_REPORT_SCHEMA_ID,
    MMCIF_UNOBSERVED_ATOM_SOURCE_BINDING_SCHEMA_ID,
    MMCIF_UNOBSERVED_ATOM_WRITER_VERSION,
    MMCIF_UNOBSERVED_ATOM_WRITE_RECEIPT_SCHEMA_ID,
    MmcifUnobservedAtomError,
    parse_mmcif_unobserved_atoms,
    round_trip_mmcif_unobserved_atoms_source,
)
from betelgeuze_engine_v2.molecular.mmcif_writer import MMCIF_WRITER_VERSION
from betelgeuze_engine_v2.molecular.pdb_mmcif import (
    MMCIF_PARSER_VERSION,
    StructureParseError,
    parse_mmcif,
)


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = (
    ROOT / "config" / "independent_engine_v2_v2_1_mmcif_unobserved_atom_corpus.json"
)
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "v2_1_mmcif_unobserved_atoms"
CORPUS_SCHEMA_ID = "betelgeuze.v2_1_mmcif_unobserved_atom_corpus/1.0.0"
CORPUS_ID = "v2_1_strict_mmcif_source_reported_unobserved_atom_claim_envelope_v1"
PAYLOAD_HASH_POLICY_ID = "sha256_canonical_json_without_payload_sha256/1.0.0"
EXPECTED_PAYLOAD_SHA256 = (
    "82081b2061386e90e2bf5e7ec94e5e6ab43d03c534d709dfbb76ffe7dbe33f7f"
)

_LOWER_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_CASE_ID = re.compile(r"^[a-z0-9_]+$")
_MAX_MANIFEST_BYTES = 1024 * 1024
_MAX_FIXTURE_BYTES = 16 * 1024
_MAX_TOTAL_FIXTURE_BYTES = 128 * 1024
_MAX_SOURCE_ROW_ID = (1 << 53) - 1
_SINGLE_ROW = b"1 Y 1 1 AX ALA AUTH-1 ? CB ? A ALA 1 CB"
_SINGLE_COORDINATE = b"ATOM 1 N N . ALA A 1 1 ? 0 0 0 1.0 20.0 ? AUTH-1 ALA AX N 1"

_ROUND_TRIP_CASE_IDS = (
    "category_order_variant",
    "composed_nonpoly_carrier",
    "insertion_and_alt_markers",
    "multiple_ordered_claims",
    "shared_entity_multiple_asym",
    "single_atom_claim",
)
_FAILURE_CODES = {
    "failure_atom_present": "unobserved_atom_present_in_coordinates",
    "failure_parent_insertion_absent": "unobserved_atom_residue_absent",
    "failure_duplicate_normalized_markers": "duplicate_unobserved_atom_identity",
    "failure_altloc_identifier": "unsupported_unobserved_atom_altloc",
    "failure_zero_occupancy_flag": "unsupported_unobserved_atom_occupancy_flag",
    "failure_wrong_model": "unsupported_unobserved_atom_model",
    "failure_unknown_asym": "unknown_unobserved_atom_asym_id",
    "failure_row_id_overflow": "duplicate_or_invalid_unobserved_atom_id",
    "failure_mixed_residue_loop": "mixed_residue_missingness_unsupported",
    "failure_row_cap_overflow": "too_many_unobserved_atom_rows",
}
_FALSE_GATES = (
    "source_authenticated",
    "auth_label_equivalence_inferred",
    "reference_sequence_equivalence_assessed",
    "coordinate_observation_completeness_assessed",
    "missing_atom_fact_claimed",
    "sequence_completeness_claimed",
    "modeled_atom_presence_assessed",
    "residue_template_consulted",
    "atom_name_dictionary_validated",
    "completion_attempted",
    "completion_applied",
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
    "canonical_carrier_source_sha256",
    "carrier_kind",
    "carrier_source_sha256",
    "full_source_sha256",
    "has_nonpoly_identity",
    "missingness_report_sha256",
    "nonpoly_projection_sha256",
    "nonpoly_record_state_sha256",
    "output_byte_count",
    "output_equals_input",
    "output_source_sha256",
    "polymer_projection_sha256",
    "polymer_record_state_sha256",
    "record_state_sha256",
    "round_trip_report_sha256",
    "rows",
    "second_emission_byte_stable",
    "source_binding_sha256",
    "source_id_sha256",
    "system_snapshot_sha256",
    "topology_sha256",
    "unobserved_atom_projection_sha256",
    "unobserved_atom_row_count",
    "write_receipt_sha256",
}
_ROW_KEYS = {
    "source_id",
    "auth_asym_id",
    "auth_comp_id",
    "auth_seq_id",
    "pdb_ins_code",
    "auth_atom_id",
    "label_alt_id",
    "label_asym_id",
    "label_comp_id",
    "label_seq_id",
    "label_atom_id",
    "entity_id",
}


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
            != "independent_engine_v2_v2_1_mmcif_unobserved_atom_corpus.json"
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


def _fixture_payload(name: str) -> tuple[Path, bytes]:
    if type(name) is not str:
        raise CorpusManifestError("fixture name must be text")
    pure = PurePosixPath(name)
    if pure.is_absolute() or len(pure.parts) != 1 or pure.suffix != ".cif":
        raise CorpusManifestError("fixture path escapes the exact corpus root")
    fixture_root = FIXTURE_ROOT.resolve(strict=True)
    try:
        path = (FIXTURE_ROOT / pure.name).resolve(strict=True)
    except OSError as exc:
        raise CorpusManifestError("fixture path is not resolvable") from exc
    if path.parent != fixture_root or not path.is_file():
        raise CorpusManifestError("fixture path is outside the exact corpus root")
    if path.stat().st_size > _MAX_FIXTURE_BYTES:
        raise CorpusManifestError("fixture exceeds its corpus byte cap")
    payload = path.read_bytes()
    if len(payload) > MAX_MMCIF_UNOBSERVED_ATOM_INPUT_BYTES:
        raise CorpusManifestError("fixture exceeds the parser input byte cap")
    return path, payload


def _replace_once(source: bytes, old: bytes, new: bytes) -> bytes:
    if not old or source.count(old) != 1:
        raise AssertionError("mutation source must occur exactly once")
    return source.replace(old, new, 1)


def _rows_payload(source: bytes, row_count: int) -> bytes:
    rows = b"\n".join(
        (f"{index} Y 1 1 AX ALA AUTH-1 ? M{index} ? A ALA 1 M{index}").encode("ascii")
        for index in range(1, row_count + 1)
    )
    return _replace_once(source, _SINGLE_ROW, rows)


def _mutate(source: bytes, mutation_id: str) -> bytes:
    if mutation_id == "atom_present":
        return _replace_once(
            source,
            _SINGLE_COORDINATE,
            b"ATOM 1 C CB . ALA A 1 1 ? 0 0 0 1.0 20.0 ? AUTH-1 ALA AX CB 1",
        )
    if mutation_id == "parent_insertion_absent":
        return _replace_once(
            source, _SINGLE_ROW, b"1 Y 1 1 AX ALA AUTH-1 B CB ? A ALA 1 CB"
        )
    if mutation_id == "duplicate_normalized_markers":
        return _replace_once(
            source,
            _SINGLE_ROW,
            _SINGLE_ROW + b"\n2 Y 1 1 AX ALA AUTH-1 . CB . A ALA 1 CB",
        )
    if mutation_id == "altloc_identifier":
        return _replace_once(
            source, _SINGLE_ROW, b"1 Y 1 1 AX ALA AUTH-1 ? CB A A ALA 1 CB"
        )
    if mutation_id == "zero_occupancy_flag":
        return _replace_once(
            source, _SINGLE_ROW, b"1 Y 0 1 AX ALA AUTH-1 ? CB ? A ALA 1 CB"
        )
    if mutation_id == "wrong_model":
        return _replace_once(
            source, _SINGLE_ROW, b"1 Y 1 2 AX ALA AUTH-1 ? CB ? A ALA 1 CB"
        )
    if mutation_id == "unknown_asym":
        return _replace_once(
            source, _SINGLE_ROW, b"1 Y 1 1 AX ALA AUTH-1 ? CB ? Z ALA 1 CB"
        )
    if mutation_id == "row_id_overflow":
        return _replace_once(
            source,
            _SINGLE_ROW,
            b"9007199254740992 Y 1 1 AX ALA AUTH-1 ? CB ? A ALA 1 CB",
        )
    if mutation_id == "mixed_residue_loop":
        residue_loop = b"""loop_
_pdbx_unobs_or_zero_occ_residues.id
_pdbx_unobs_or_zero_occ_residues.polymer_flag
_pdbx_unobs_or_zero_occ_residues.occupancy_flag
_pdbx_unobs_or_zero_occ_residues.pdb_model_num
_pdbx_unobs_or_zero_occ_residues.auth_asym_id
_pdbx_unobs_or_zero_occ_residues.auth_comp_id
_pdbx_unobs_or_zero_occ_residues.auth_seq_id
_pdbx_unobs_or_zero_occ_residues.pdb_ins_code
_pdbx_unobs_or_zero_occ_residues.label_asym_id
_pdbx_unobs_or_zero_occ_residues.label_comp_id
_pdbx_unobs_or_zero_occ_residues.label_seq_id
9 Y 1 1 AX ALA AUTH-1 ? A ALA 1
#
"""
        return _replace_once(
            source,
            b"loop_\n_atom_site.group_pdb",
            residue_loop + b"loop_\n_atom_site.group_pdb",
        )
    if mutation_id == "row_cap_overflow":
        return _rows_payload(source, MAX_MMCIF_UNOBSERVED_ATOM_ROWS + 1)
    raise CorpusManifestError("unknown corpus mutation")


def _row_document(row: Any) -> dict[str, Any]:
    return {key: getattr(row, key) for key in _ROW_KEYS}


def _replay(case: dict[str, Any]) -> tuple[dict[str, Any], Any]:
    _path, source = _fixture_payload(case["fixture"])
    result = round_trip_mmcif_unobserved_atoms_source(
        source, source_id=case["source_id"]
    )
    ingest = result.source_ingest
    receipt = result.write_result.receipt
    receipt_document = receipt.to_dict()
    return (
        {
            "canonical_carrier_source_sha256": ingest.canonical_carrier_source_sha256,
            "carrier_kind": ingest.carrier_kind,
            "carrier_source_sha256": ingest.carrier_source_sha256,
            "full_source_sha256": ingest.full_source_sha256,
            "has_nonpoly_identity": ingest.has_nonpoly_identity,
            "missingness_report_sha256": ingest.missingness_report_sha256,
            "nonpoly_projection_sha256": ingest.nonpoly_projection_sha256,
            "nonpoly_record_state_sha256": ingest.nonpoly_record_state_sha256,
            "output_byte_count": receipt_document["output_byte_count"],
            "output_equals_input": result.write_result.payload == source,
            "output_source_sha256": receipt.output_source_sha256,
            "polymer_projection_sha256": ingest.polymer_projection_sha256,
            "polymer_record_state_sha256": ingest.polymer_record_state_sha256,
            "record_state_sha256": ingest.record_state_sha256,
            "round_trip_report_sha256": result.report.round_trip_report_sha256,
            "rows": [_row_document(row) for row in ingest.unobserved_atom_rows],
            "second_emission_byte_stable": result.report.second_emission_byte_stable,
            "source_binding_sha256": ingest.source_binding_sha256,
            "source_id_sha256": ingest.source_id_sha256,
            "system_snapshot_sha256": ingest.system_snapshot_sha256,
            "topology_sha256": ingest.topology_sha256,
            "unobserved_atom_projection_sha256": (
                ingest.unobserved_atom_projection_sha256
            ),
            "unobserved_atom_row_count": len(ingest.unobserved_atom_rows),
            "write_receipt_sha256": receipt.receipt_sha256,
        },
        result,
    )


def test_manifest_payload_hash_and_inventory_are_exact() -> None:
    document = _load_manifest()
    assert set(document) == {
        "schema_id",
        "corpus_id",
        "payload_hash_policy_id",
        "payload_sha256",
        "contract",
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
        "[]",
    ),
)
def test_manifest_loader_rejects_noncanonical_json(payload: str) -> None:
    with pytest.raises(CorpusManifestError):
        _parse_manifest_json(payload)


@pytest.mark.parametrize(
    "name",
    (
        str((FIXTURE_ROOT / "single_atom_claim.cif").resolve()),
        "../single_atom_claim.cif",
        "v2_1_mmcif_unobserved_atoms/single_atom_claim.cif",
        "single_atom_claim.txt",
    ),
)
def test_fixture_resolver_rejects_paths_outside_exact_corpus(name: str) -> None:
    with pytest.raises(CorpusManifestError):
        _fixture_payload(name)


def test_manifest_contract_limits_and_false_claims_are_exact() -> None:
    document = _load_manifest()
    assert document["contract"] == {
        "actual_missing_atom_fact_established": False,
        "base_mmcif_parser_version": MMCIF_PARSER_VERSION,
        "base_mmcif_writer_version": MMCIF_WRITER_VERSION,
        "envelope_version": MMCIF_UNOBSERVED_ATOM_ENVELOPE_VERSION,
        "headers": list(MMCIF_UNOBSERVED_ATOM_HEADERS),
        "nonpoly_identity_envelope_version": MMCIF_NONPOLY_IDENTITY_ENVELOPE_VERSION,
        "parser_version": MMCIF_UNOBSERVED_ATOM_PARSER_VERSION,
        "polymer_sequence_envelope_version": MMCIF_POLYMER_SEQUENCE_ENVELOPE_VERSION,
        "profile_id": MMCIF_UNOBSERVED_ATOM_PROFILE_ID,
        "projection_schema_id": MMCIF_UNOBSERVED_ATOM_PROJECTION_SCHEMA_ID,
        "projection_scope": MMCIF_UNOBSERVED_ATOM_PROJECTION_SCOPE,
        "raw_dot_question_markers_projection_distinct": True,
        "record_state_schema_id": MMCIF_UNOBSERVED_ATOM_RECORD_STATE_SCHEMA_ID,
        "round_trip_report_schema_id": (
            MMCIF_UNOBSERVED_ATOM_ROUND_TRIP_REPORT_SCHEMA_ID
        ),
        "semantic_identity": (
            "model_label_asym_label_seq_label_comp_normalized_ins_"
            "label_atom_normalized_altloc"
        ),
        "source_binding_schema_id": MMCIF_UNOBSERVED_ATOM_SOURCE_BINDING_SCHEMA_ID,
        "write_receipt_schema_id": MMCIF_UNOBSERVED_ATOM_WRITE_RECEIPT_SCHEMA_ID,
        "writer_version": MMCIF_UNOBSERVED_ATOM_WRITER_VERSION,
    }
    assert document["limits"] == {
        "canonical_physical_line_characters": 2_048,
        "input_bytes": MAX_MMCIF_UNOBSERVED_ATOM_INPUT_BYTES,
        "row_count": MAX_MMCIF_UNOBSERVED_ATOM_ROWS,
        "source_id_utf8_bytes": MAX_MMCIF_UNOBSERVED_ATOM_SOURCE_ID_BYTES,
        "source_row_id_max": _MAX_SOURCE_ROW_ID,
        "token_characters": MAX_MMCIF_UNOBSERVED_ATOM_TOKEN_CHARS,
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
        assert len(pure.parts) == 4
        assert pure.parts[:3] == (
            "tests",
            "fixtures",
            "v2_1_mmcif_unobserved_atoms",
        )
        assert ".." not in pure.parts and pure.parts[-1] == pure.name
        path, payload = _fixture_payload(pure.parts[-1])
        assert path == ROOT.joinpath(*pure.parts).resolve(strict=True)
        assert len(payload) == fixture["byte_count"]
        assert hashlib.sha256(payload).hexdigest() == fixture["sha256"]
        assert _LOWER_SHA256.fullmatch(fixture["sha256"])
        referenced.add(path)
        total_bytes += len(payload)
    assert referenced == {path.resolve() for path in FIXTURE_ROOT.glob("*.cif")}
    assert total_bytes <= _MAX_TOTAL_FIXTURE_BYTES

    cases = document["cases"]
    assert type(cases) is list and len(cases) == 16
    assert [case["case_id"] for case in cases] == [
        *_ROUND_TRIP_CASE_IDS,
        *_FAILURE_CODES,
    ]
    for case in cases:
        assert type(case["case_id"]) is str and _CASE_ID.fullmatch(case["case_id"])
        _fixture_payload(case["fixture"])
        if case["kind"] == "round_trip":
            assert set(case) == {
                "case_id",
                "kind",
                "fixture",
                "source_id",
                "expected",
            }
            assert set(case["expected"]) == _EXPECTED_KEYS
            assert type(case["expected"]["rows"]) is list
            assert all(set(row) == _ROW_KEYS for row in case["expected"]["rows"])
            for key, value in case["expected"].items():
                if key.endswith("sha256") and value is not None:
                    assert type(value) is str and _LOWER_SHA256.fullmatch(value)
        else:
            assert case["kind"] == "failure"
            assert set(case) == {
                "case_id",
                "kind",
                "fixture",
                "mutation_id",
                "expected_error_code",
                "source_sha256",
            }
            assert case["expected_error_code"] == _FAILURE_CODES[case["case_id"]]
            assert type(case["source_sha256"]) is str
            assert _LOWER_SHA256.fullmatch(case["source_sha256"])


@pytest.mark.parametrize("case_id", _ROUND_TRIP_CASE_IDS)
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
        assert artifact["source_reported_unobserved_atom_claims_preserved"] is True
        for field in _FALSE_GATES:
            assert artifact[field] is False

    _path, source = _fixture_payload(case["fixture"])
    report = result.source_ingest.base_ingest.missingness_evidence
    assert report.source_reported_missing_residue_count == 0
    assert report.source_reported_missing_atom_count == len(
        result.source_ingest.unobserved_atom_rows
    )
    with pytest.raises(StructureParseError) as base_exc:
        parse_mmcif(source, source_id=case_id)
    assert base_exc.value.code == "unsupported_context_category"
    with pytest.raises(MmcifPolymerSequenceError) as polymer_exc:
        parse_mmcif_polymer_sequence(source, source_id=case_id)
    assert polymer_exc.value.code == "unsupported_category_surface"


@pytest.mark.parametrize("case_id", tuple(_FAILURE_CODES))
def test_failure_cases_replay_exact_codes(case_id: str) -> None:
    case = next(row for row in _load_manifest()["cases"] if row["case_id"] == case_id)
    _path, source = _fixture_payload(case["fixture"])
    mutated = _mutate(source, case["mutation_id"])
    assert hashlib.sha256(mutated).hexdigest() == case["source_sha256"]
    with pytest.raises(MmcifUnobservedAtomError) as exc_info:
        parse_mmcif_unobserved_atoms(mutated, source_id=case_id)
    assert exc_info.value.code == case["expected_error_code"]
    assert exc_info.value.__cause__ is None
    assert "AUTH-1" not in str(exc_info.value)


def test_category_order_pair_preserves_projection_state_and_output_only() -> None:
    cases = {row["case_id"]: row for row in _load_manifest()["cases"]}
    canonical = cases["single_atom_claim"]["expected"]
    reordered = cases["category_order_variant"]["expected"]
    assert (
        canonical["unobserved_atom_projection_sha256"]
        == reordered["unobserved_atom_projection_sha256"]
    )
    assert canonical["record_state_sha256"] == reordered["record_state_sha256"]
    assert canonical["output_source_sha256"] == reordered["output_source_sha256"]
    assert canonical["source_binding_sha256"] != reordered["source_binding_sha256"]
    assert canonical["write_receipt_sha256"] != reordered["write_receipt_sha256"]


def test_only_composed_case_carries_nonpoly_identity_evidence() -> None:
    cases = {
        row["case_id"]: row["expected"]
        for row in _load_manifest()["cases"]
        if row["kind"] == "round_trip"
    }
    for case_id, expected in cases.items():
        composed = case_id == "composed_nonpoly_carrier"
        assert expected["has_nonpoly_identity"] is composed
        assert (
            expected["carrier_kind"] == "mmcif_polymer_sequence_nonpoly_identity"
        ) is composed
        assert (expected["nonpoly_projection_sha256"] is not None) is composed
        assert (expected["nonpoly_record_state_sha256"] is not None) is composed
