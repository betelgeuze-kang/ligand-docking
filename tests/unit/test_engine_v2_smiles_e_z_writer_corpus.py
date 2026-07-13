from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any, Mapping

import pytest

from betelgeuze_engine_v2.contracts import ALL_ATOM_SCHEMA_ID
from betelgeuze_engine_v2.molecular import (
    SMILES_AROMATIC_RING_PROJECTION_SCHEMA_ID,
    SMILES_COMPONENT_CYCLE_PROJECTION_SCHEMA_ID,
    SMILES_EZ_STEREO_PROJECTION_SCHEMA_ID,
    SMILES_PARSER_VERSION,
    SMILES_REPRESENTABLE_STATE_SCHEMA_ID,
    SMILES_ROUND_TRIP_REPORT_SCHEMA_ID,
    SMILES_TETRAHEDRAL_STEREO_PROJECTION_SCHEMA_ID,
    SMILES_WRITER_VERSION,
    SMILES_WRITE_RECEIPT_SCHEMA_ID,
    canonical_all_atom_snapshot_digest,
    round_trip_smiles_source,
    smiles_representable_state_sha256,
    write_smiles,
)
from betelgeuze_engine_v2.molecular import smiles as smiles_module
from betelgeuze_engine_v2.molecular import smiles_writer as writer_module


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = (
    REPOSITORY_ROOT
    / "config"
    / "independent_engine_v2_v2_1_smiles_e_z_writer_corpus.json"
)
UPSTREAM_INGEST_MANIFEST_PATH = (
    REPOSITORY_ROOT / "config" / "independent_engine_v2_v2_1_ingest_corpus.json"
)
CORPUS_SCHEMA_ID = "betelgeuze.v2_1_smiles_e_z_writer_corpus/1.1.0"
CORPUS_ID = "v2_1_strict_smiles_bounded_e_z_writer_v1"
PAYLOAD_HASH_POLICY_ID = "sha256_canonical_json_without_payload_sha256/1.0.0"
EXPECTED_PAYLOAD_SHA256 = (
    "a58207f72b9127b3adf1cde9499b765ec934f7162fe52ef720aae74ebff8b03f"
)
PINNED_RDKIT_VERSION_KEY = (2025, 9, 6)
PINNED_RDKIT_OBSERVED_VERSION = "2025.09.6"
EZ_PROFILE_ID = (
    "source_order_dfs_lowest_index_lexically_oriented_tree_or_selected_simple_"
    "ring_single_bond_direction_carriers/1.0.0"
)

_LOWERCASE_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_CASE_ID = re.compile(r"^[a-z][a-z0-9_]*$")
_MAX_MANIFEST_BYTES = 1024 * 1024
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
    "category",
    "source",
    "source_id",
    "source_sha256",
    "expected",
}
_EXPECTED_KEYS = {
    "output_ascii",
    "output_sha256",
    "output_byte_count",
    "output_equals_input",
    "canonical_topology_sha256",
    "ordered_topology_sha256",
    "source_snapshot_sha256",
    "reparsed_snapshot_sha256",
    "representable_state_sha256",
    "cycle_projection_sha256",
    "aromatic_projection_sha256",
    "ez_stereo_projection_sha256",
    "tetrahedral_stereo_projection_sha256",
    "source_parser_observation_sha256",
    "reparsed_parser_observation_sha256",
    "receipt_sha256",
    "report_sha256",
    "typed_ez_bond_count",
    "directional_source_bond_count",
    "stereo_labels",
    "reference_carrier_parity_flipped",
    "direction_carrier_tokens",
    "directional_bond_tokens",
}
_SHA256_EXPECTED_KEYS = {key for key in _EXPECTED_KEYS if key.endswith("_sha256")}
_PINNED_ONLY_EXPECTED_KEYS = {
    "source_snapshot_sha256",
    "reparsed_snapshot_sha256",
    "representable_state_sha256",
    "source_parser_observation_sha256",
    "reparsed_parser_observation_sha256",
    "receipt_sha256",
    "report_sha256",
}
_EXPECTED_CASE_IDS = {
    "conjugated_shared_carrier_z_z",
    "external_internal_mixed_e_z",
    "multi_component_e_z",
    "one_reference_mismatch_e",
    "raw_gauge_normalization_e",
    "ring3_exocyclic_e",
    "ring3_exocyclic_z",
    "ring6_exocyclic_e",
    "ring6_exocyclic_z",
    "ring8_closure_e",
    "ring8_closure_z",
    "ring8_shifted_internal_e",
    "ring8_shifted_internal_z",
    "simple_e",
    "simple_z",
    "tetrasubstituted_e",
    "unspecified_baseline",
}
_EXPECTED_CATEGORIES = {
    "conjugated_shared_carrier",
    "external_internal_mixed",
    "multi_component",
    "one_reference_mismatch",
    "raw_gauge_normalization",
    "ring3_exocyclic",
    "ring6_exocyclic",
    "ring8_closure",
    "ring8_shifted_internal",
    "simple_e",
    "simple_z",
    "tetrasubstituted",
    "unspecified_baseline",
}


class SmilesEzWriterCorpusError(ValueError):
    """Raised when the fixed positive corpus is ambiguous or mutable."""


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise SmilesEzWriterCorpusError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _reject_float(_: str) -> None:
    raise SmilesEzWriterCorpusError("floating-point JSON values are forbidden")


def _reject_constant(_: str) -> None:
    raise SmilesEzWriterCorpusError("non-finite JSON values are forbidden")


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _manifest_payload_sha256(document: Mapping[str, Any]) -> str:
    payload = deepcopy(document)
    payload.pop("payload_sha256", None)
    return hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()


def _artifact_sha256(document: Mapping[str, Any], digest_key: str) -> str:
    payload = deepcopy(document)
    payload.pop(digest_key)
    return hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()


def _expect_exact_keys(value: Any, expected: set[str], context: str) -> dict[str, Any]:
    if type(value) is not dict:
        raise SmilesEzWriterCorpusError(f"{context} must be an object")
    if set(value) != expected:
        raise SmilesEzWriterCorpusError(f"{context} keys do not match the schema")
    return value


def _require_sha256(value: Any, context: str) -> str:
    if type(value) is not str or _LOWERCASE_SHA256.fullmatch(value) is None:
        raise SmilesEzWriterCorpusError(f"{context} must be lowercase SHA-256")
    return value


def _load_manifest() -> dict[str, Any]:
    raw = MANIFEST_PATH.read_bytes()
    if not 1 <= len(raw) <= _MAX_MANIFEST_BYTES:
        raise SmilesEzWriterCorpusError("manifest byte size is outside the fixed limit")
    try:
        document = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_float=_reject_float,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SmilesEzWriterCorpusError("manifest must be strict UTF-8 JSON") from exc
    document = _expect_exact_keys(document, _TOP_LEVEL_KEYS, "manifest")
    if _require_sha256(document["payload_sha256"], "payload_sha256") != (
        _manifest_payload_sha256(document)
    ):
        raise SmilesEzWriterCorpusError("manifest payload hash mismatch")

    cases = document["cases"]
    if type(cases) is not list or not cases:
        raise SmilesEzWriterCorpusError("cases must be a nonempty list")
    case_ids: list[str] = []
    for index, case_value in enumerate(cases):
        case = _expect_exact_keys(case_value, _CASE_KEYS, f"cases[{index}]")
        case_id = case["case_id"]
        if type(case_id) is not str or _CASE_ID.fullmatch(case_id) is None:
            raise SmilesEzWriterCorpusError(f"cases[{index}].case_id is invalid")
        if case["source_id"] != case_id:
            raise SmilesEzWriterCorpusError(
                f"cases[{index}].source_id must equal case_id"
            )
        if type(case["category"]) is not str:
            raise SmilesEzWriterCorpusError(f"cases[{index}].category must be a string")
        source = _expect_exact_keys(case["source"], {"kind", "value"}, "source")
        if source["kind"] != "ascii" or type(source["value"]) is not str:
            raise SmilesEzWriterCorpusError("case source must be inline ASCII")
        try:
            source_bytes = source["value"].encode("ascii")
        except UnicodeEncodeError as exc:
            raise SmilesEzWriterCorpusError("case source must be ASCII") from exc
        if not source_bytes or len(source_bytes) > 64 * 1024:
            raise SmilesEzWriterCorpusError("case source is outside parser byte limits")
        if b"\n" in source_bytes or b"\r" in source_bytes:
            raise SmilesEzWriterCorpusError("case source must be one unterminated line")
        if hashlib.sha256(source_bytes).hexdigest() != _require_sha256(
            case["source_sha256"], f"cases[{index}].source_sha256"
        ):
            raise SmilesEzWriterCorpusError("case source digest mismatch")

        expected = _expect_exact_keys(
            case["expected"], _EXPECTED_KEYS, f"cases[{index}].expected"
        )
        for key in _SHA256_EXPECTED_KEYS:
            _require_sha256(expected[key], f"cases[{index}].expected.{key}")
        if type(expected["output_ascii"]) is not str:
            raise SmilesEzWriterCorpusError("expected output must be ASCII text")
        try:
            output = expected["output_ascii"].encode("ascii")
        except UnicodeEncodeError as exc:
            raise SmilesEzWriterCorpusError("expected output must be ASCII") from exc
        if hashlib.sha256(output).hexdigest() != expected["output_sha256"]:
            raise SmilesEzWriterCorpusError("expected output digest mismatch")
        if type(expected["output_byte_count"]) is not int or (
            expected["output_byte_count"] != len(output)
        ):
            raise SmilesEzWriterCorpusError("expected output byte count mismatch")
        if type(expected["output_equals_input"]) is not bool or (
            expected["output_equals_input"] != (output == source_bytes)
        ):
            raise SmilesEzWriterCorpusError("expected input/output equality mismatch")
        for count_key in ("typed_ez_bond_count", "directional_source_bond_count"):
            if type(expected[count_key]) is not int or expected[count_key] < 0:
                raise SmilesEzWriterCorpusError(f"{count_key} must be nonnegative")
        if type(expected["stereo_labels"]) is not list or any(
            value not in {"E", "Z"} for value in expected["stereo_labels"]
        ):
            raise SmilesEzWriterCorpusError("stereo_labels are invalid")
        if len(expected["stereo_labels"]) != expected["typed_ez_bond_count"]:
            raise SmilesEzWriterCorpusError("stereo label count mismatch")
        if type(expected["reference_carrier_parity_flipped"]) is not list or any(
            type(value) is not bool
            for value in expected["reference_carrier_parity_flipped"]
        ):
            raise SmilesEzWriterCorpusError("reference/carrier parity rows are invalid")
        if (
            len(expected["reference_carrier_parity_flipped"])
            != (expected["typed_ez_bond_count"])
        ):
            raise SmilesEzWriterCorpusError("reference/carrier parity count mismatch")
        case_ids.append(case_id)
    if case_ids != sorted(case_ids) or len(case_ids) != len(set(case_ids)):
        raise SmilesEzWriterCorpusError("case IDs must be sorted and unique")
    return document


@pytest.fixture
def supported_rdkit_contract(monkeypatch: pytest.MonkeyPatch) -> tuple[str, bool]:
    try:
        _, rd_base = smiles_module._import_rdkit()
    except (ImportError, ModuleNotFoundError):
        pytest.skip("RDKit is unavailable in this test environment")
    version = rd_base.rdkitVersion
    is_pinned = smiles_module._version_key(version) == PINNED_RDKIT_VERSION_KEY
    if os.environ.get("BETELGEUZE_REQUIRE_PINNED_RDKIT") == "1":
        assert is_pinned, f"expected RDKit 2025.9.6, observed {version}"
    if not is_pinned:
        monkeypatch.setattr(
            smiles_module,
            "_SUPPORTED_RDKIT_VERSIONS",
            frozenset({version}),
        )
    return version, is_pinned


def test_manifest_contract_hash_inventory_and_positive_scope_are_exact() -> None:
    document = _load_manifest()
    assert document["schema_id"] == CORPUS_SCHEMA_ID
    assert document["corpus_id"] == CORPUS_ID
    assert document["manifest_payload_hash_policy_id"] == PAYLOAD_HASH_POLICY_ID
    assert document["payload_sha256"] == EXPECTED_PAYLOAD_SHA256
    assert document["contracts"] == {
        "system_schema_id": ALL_ATOM_SCHEMA_ID,
        "writer_version": SMILES_WRITER_VERSION,
        "parser_version": SMILES_PARSER_VERSION,
        "rdkit_requirement": "rdkit==2025.9.6",
        "rdkit_version_key": "2025.9.6",
        "rdkit_observed_version": PINNED_RDKIT_OBSERVED_VERSION,
        "representable_state_schema_id": SMILES_REPRESENTABLE_STATE_SCHEMA_ID,
        "write_receipt_schema_id": SMILES_WRITE_RECEIPT_SCHEMA_ID,
        "round_trip_report_schema_id": SMILES_ROUND_TRIP_REPORT_SCHEMA_ID,
        "cycle_projection_schema_id": SMILES_COMPONENT_CYCLE_PROJECTION_SCHEMA_ID,
        "aromatic_projection_schema_id": SMILES_AROMATIC_RING_PROJECTION_SCHEMA_ID,
        "ez_stereo_projection_schema_id": SMILES_EZ_STEREO_PROJECTION_SCHEMA_ID,
        "tetrahedral_stereo_projection_schema_id": (
            SMILES_TETRAHEDRAL_STEREO_PROJECTION_SCHEMA_ID
        ),
        "tetrahedral_stereo_max_atom_count": 256,
        "max_tetrahedral_calibration_source_atom_count": 514,
        "ez_stereo_profile_id": EZ_PROFILE_ID,
        "ez_stereo_admission_scope": (
            "normalized_hash_admitted_lowest_index_carrier_subset_only"
        ),
        "upstream_ingest_corpus_schema_id": "betelgeuze.v2_1_ingest_corpus/1.4.0",
        "upstream_ingest_corpus_id": (
            "v2_1_supported_ingest_identity_context_and_failure_v5"
        ),
        "upstream_ingest_e_z_case_ids": ["smiles_alkene_e", "smiles_alkene_z"],
        "upstream_ingest_e_z_case_record_sha256": {
            "smiles_alkene_e": (
                "c686d06882d579f498ff5038d20a1f479404e547fbcacc5c4aa52f1c36c3ec98"
            ),
            "smiles_alkene_z": (
                "b39e94deaa33190a33f29f535e165b0e553dcf926c979c52a80b8f74f7ac6939"
            ),
        },
    }
    assert document["claim_boundary"] == {
        "bounded_normalized_spelling_admitted_parser_typed_e_z_preserved": True,
        "general_parser_typed_e_z_preserved": False,
        "ordered_stereo_center_remapping_claimed": False,
        "raw_direction_spelling_preserved": False,
        "independent_cip_assignment_claimed": False,
        "stereo_completeness_claimed": False,
        "stereo_geometry_claimed": False,
        "full_canonical_snapshot_equality_claimed": False,
        "dynamic_source_provenance_equality_claimed": False,
        "source_authenticated": False,
        "chemistry_supported": False,
        "preparation_ready": False,
        "parameterability_assessed": False,
        "simulation_ready": False,
        "claim_safe": False,
    }

    cases = document["cases"]
    assert {case["case_id"] for case in cases} == _EXPECTED_CASE_IDS
    assert {case["category"] for case in cases} == _EXPECTED_CATEGORIES
    by_id = {case["case_id"]: case for case in cases}
    assert (
        by_id["raw_gauge_normalization_e"]["expected"]["output_equals_input"] is False
    )
    assert by_id["one_reference_mismatch_e"]["expected"][
        "reference_carrier_parity_flipped"
    ] == [True]
    assert (
        by_id["conjugated_shared_carrier_z_z"]["expected"][
            "directional_source_bond_count"
        ]
        == 3
    )
    assert by_id["external_internal_mixed_e_z"]["expected"]["stereo_labels"] == [
        "E",
        "Z",
    ]
    assert by_id["unspecified_baseline"]["expected"]["typed_ez_bond_count"] == 0

    upstream = json.loads(
        UPSTREAM_INGEST_MANIFEST_PATH.read_text(encoding="utf-8"),
        object_pairs_hook=_reject_duplicate_keys,
        parse_float=_reject_float,
        parse_constant=_reject_constant,
    )
    assert (
        upstream["schema_id"]
        == document["contracts"]["upstream_ingest_corpus_schema_id"]
    )
    assert upstream["corpus_id"] == document["contracts"]["upstream_ingest_corpus_id"]
    upstream_ids = set(document["contracts"]["upstream_ingest_e_z_case_ids"])
    upstream_records = {
        case["case_id"]: hashlib.sha256(_canonical_json_bytes(case)).hexdigest()
        for case in upstream["cases"]
        if case["case_id"] in upstream_ids
    }
    assert (
        upstream_records
        == document["contracts"]["upstream_ingest_e_z_case_record_sha256"]
    )


@pytest.mark.parametrize("case_id", sorted(_EXPECTED_CASE_IDS))
def test_positive_fixed_point_replays_bytes_stereo_receipts_and_abstentions(
    case_id: str,
    supported_rdkit_contract: tuple[str, bool],
) -> None:
    observed_rdkit_version, is_pinned = supported_rdkit_contract
    case = next(row for row in _load_manifest()["cases"] if row["case_id"] == case_id)
    expected = case["expected"]
    source = case["source"]["value"].encode("ascii")
    output = expected["output_ascii"].encode("ascii")
    result = round_trip_smiles_source(source, source_id=case["source_id"])
    source_state = writer_module._validate_write_state(result.source_ingest.system)
    reparsed_state = writer_module._validate_write_state(result.reparsed_ingest.system)
    receipt = result.write_result.receipt
    report = result.report
    projection = source_state.ez_stereo_projection_document

    assert result.write_result.payload == output
    assert hashlib.sha256(output).hexdigest() == expected["output_sha256"]
    assert receipt.output_byte_count == expected["output_byte_count"]
    assert (output == source) is expected["output_equals_input"]
    assert write_smiles(result.reparsed_ingest.system).payload == output
    assert (
        source_state.canonical_topology_sha256 == expected["canonical_topology_sha256"]
    )
    assert source_state.ordered_topology_sha256 == expected["ordered_topology_sha256"]
    assert source_state.cycle_projection_sha256 == expected["cycle_projection_sha256"]
    assert (
        source_state.aromatic_projection_sha256
        == expected["aromatic_projection_sha256"]
    )
    assert (
        source_state.ez_stereo_projection_sha256
        == expected["ez_stereo_projection_sha256"]
    )
    assert (
        source_state.tetrahedral_stereo_projection_sha256
        == (expected["tetrahedral_stereo_projection_sha256"])
    )
    assert source_state.ez_stereo_projection_document == (
        reparsed_state.ez_stereo_projection_document
    )
    assert source_state.tetrahedral_stereo_projection_document == (
        reparsed_state.tetrahedral_stereo_projection_document
    )
    assert (
        source_state.tetrahedral_stereo_projection_document[
            "typed_tetrahedral_atom_count"
        ]
        == 0
    )
    assert projection["schema_id"] == SMILES_EZ_STEREO_PROJECTION_SCHEMA_ID
    assert projection["profile_id"] == EZ_PROFILE_ID
    assert projection["typed_ez_bond_count"] == expected["typed_ez_bond_count"]
    assert (
        projection["directional_source_bond_count"]
        == expected["directional_source_bond_count"]
    )
    stereo_rows = projection["stereo_bond_table"]
    directional_rows = projection["directional_bond_table"]
    assert [row["stereo"] for row in stereo_rows] == expected["stereo_labels"]
    assert [row["reference_carrier_parity_flipped"] for row in stereo_rows] == (
        expected["reference_carrier_parity_flipped"]
    )
    assert [row["direction_carrier_tokens"] for row in stereo_rows] == expected[
        "direction_carrier_tokens"
    ]
    assert [row["bond_token"] for row in directional_rows] == expected[
        "directional_bond_tokens"
    ]
    assert all(
        token in {"/", "\\"}
        for row in stereo_rows
        for token in row["direction_carrier_tokens"]
    )
    assert projection["ring_bond_ez_supported"] is True
    assert (
        projection["selected_simple_ring_single_direction_carriers_supported"] is True
    )
    assert projection["independent_cip_assignment_claimed"] is False
    assert projection["stereo_completeness_claimed"] is False
    assert projection["stereo_geometry_claimed"] is False

    receipt_document = receipt.to_dict()
    report_document = report.to_dict()
    assert receipt_document["schema_id"] == SMILES_WRITE_RECEIPT_SCHEMA_ID
    assert receipt_document["writer_version"] == SMILES_WRITER_VERSION
    assert receipt_document["parser_version"] == SMILES_PARSER_VERSION
    assert receipt.rdkit_version == observed_rdkit_version
    assert receipt.parent_source_sha256 == case["source_sha256"]
    assert receipt.output_source_sha256 == expected["output_sha256"]
    assert receipt.normalized_isomeric_smiles_sha256 == expected["output_sha256"]
    assert receipt.input_topology_sha256 == source_state.canonical_topology_sha256
    assert receipt.input_ordered_topology_sha256 == source_state.ordered_topology_sha256
    assert receipt.input_ez_stereo_projection_sha256 == (
        source_state.ez_stereo_projection_sha256
    )
    assert receipt.input_tetrahedral_stereo_projection_sha256 == (
        source_state.tetrahedral_stereo_projection_sha256
    )
    assert receipt.typed_ez_bond_count == expected["typed_ez_bond_count"]
    assert (
        receipt.directional_source_bond_count
        == expected["directional_source_bond_count"]
    )
    assert (
        receipt_document["resource_limits"]["tetrahedral_calibration_source_atoms"]
        == 514
    )
    assert receipt_document["receipt_sha256"] == _artifact_sha256(
        receipt_document, "receipt_sha256"
    )

    assert report_document["schema_id"] == SMILES_ROUND_TRIP_REPORT_SCHEMA_ID
    assert report.writer_receipt_sha256 == receipt.receipt_sha256
    assert report.input_source_sha256 == case["source_sha256"]
    assert report.emitted_source_sha256 == expected["output_sha256"]
    assert report.reemitted_source_sha256 == expected["output_sha256"]
    assert report.input_topology_sha256 == report.reparsed_topology_sha256
    assert (
        report.input_ordered_topology_sha256 == report.reparsed_ordered_topology_sha256
    )
    assert report.input_representable_state_sha256 == (
        report.reparsed_representable_state_sha256
    )
    assert report.input_ez_stereo_projection_sha256 == (
        report.reparsed_ez_stereo_projection_sha256
    )
    assert report.input_tetrahedral_stereo_projection_sha256 == (
        report.reparsed_tetrahedral_stereo_projection_sha256
    )
    assert report_document["emitted_source_sha256_and_bytes_stable"] is True
    assert report_document["ez_stereo_projection_sha256_equal"] is True
    assert report_document["tetrahedral_stereo_projection_sha256_equal"] is True
    assert report_document["report_sha256"] == _artifact_sha256(
        report_document, "report_sha256"
    )

    coverage = result.source_ingest.coverage.to_dict()
    assert coverage["chemistry_supported"] is False
    assert coverage["parameterability_assessed"] is False
    assert coverage["preparation_ready"] is False
    assert coverage["claim_safe"] is False
    for document in (receipt_document, report_document):
        assert document["source_authentication_status"] == "not_authenticated"
        assert document["preparation_ready"] is False
        assert document["parameterability_assessed"] is False
        assert document["simulation_ready"] is False
        assert document["claim_safe"] is False
    assert report_document["full_canonical_snapshot_equality_claimed"] is False
    assert report_document["dynamic_source_provenance_equality_claimed"] is False

    if is_pinned:
        pinned_actual = {
            "source_snapshot_sha256": canonical_all_atom_snapshot_digest(
                result.source_ingest.system
            ),
            "reparsed_snapshot_sha256": canonical_all_atom_snapshot_digest(
                result.reparsed_ingest.system
            ),
            "representable_state_sha256": smiles_representable_state_sha256(
                result.source_ingest.system
            ),
            "source_parser_observation_sha256": (
                result.source_ingest.system.provenance.metadata[
                    "parser_observation_sha256"
                ]
            ),
            "reparsed_parser_observation_sha256": (
                result.reparsed_ingest.system.provenance.metadata[
                    "parser_observation_sha256"
                ]
            ),
            "receipt_sha256": receipt.receipt_sha256,
            "report_sha256": report.report_sha256,
        }
        assert set(pinned_actual) == _PINNED_ONLY_EXPECTED_KEYS
        assert pinned_actual == {
            key: expected[key] for key in _PINNED_ONLY_EXPECTED_KEYS
        }
