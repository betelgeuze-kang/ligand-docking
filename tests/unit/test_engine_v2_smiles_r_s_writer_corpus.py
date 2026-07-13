from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
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
    SmilesParseError,
    SmilesWriteError,
    canonical_all_atom_snapshot_digest,
    canonical_topology_sha256,
    parse_smiles,
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
    / "independent_engine_v2_v2_1_smiles_r_s_writer_corpus.json"
)
UPSTREAM_INGEST_MANIFEST_PATH = (
    REPOSITORY_ROOT / "config" / "independent_engine_v2_v2_1_ingest_corpus.json"
)
CORPUS_SCHEMA_ID = "betelgeuze.v2_1_smiles_r_s_writer_corpus/1.0.0"
CORPUS_ID = "v2_1_strict_smiles_bounded_r_s_writer_v1"
PAYLOAD_HASH_POLICY_ID = "sha256_canonical_json_without_payload_sha256/1.0.0"
EXPECTED_PAYLOAD_SHA256 = (
    "34a1cadfe0c3fa321bfb256c28d723c29465c85384ec2e99f1022aef71a636fc"
)
PINNED_RDKIT_VERSION_KEY = (2025, 9, 6)
PINNED_RDKIT_OBSERVED_VERSION = "2025.09.6"
TETRAHEDRAL_PROFILE_ID = (
    "source_order_dfs_parser_typed_tetrahedral_cw_ccw_lexical_parity_with_"
    "zero_or_one_bracket_hydrogen/1.0.0"
)
ZERO_SHA256 = "0" * 64

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
    "typed_tetrahedral_atom_count",
    "mapped_source_atom_count",
    "mapped_tetrahedral_atom_count",
    "bracket_hydrogen_tetrahedral_atom_count",
    "marker_flip_count",
    "source_center_atom_indices",
    "center_atom_maps",
    "target_stereo_labels",
    "target_rdkit_chiral_tags",
    "trial_markers",
    "final_markers",
    "final_atom_tokens",
    "typed_ez_bond_count",
    "directional_source_bond_count",
    "fragment_count",
    "ring_closure_count",
    "ring_size",
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
    "boron_center",
    "bracket_h_r",
    "bracket_h_s",
    "charged_n_center",
    "ez_coexistence",
    "mapped_r",
    "mapped_s",
    "multi_center",
    "multi_component",
    "no_h_r",
    "no_h_s",
    "ring_center",
    "stereo_free_baseline",
    "sulfur_center",
}
_EXPECTED_CATEGORIES = {
    "bracket_hydrogen",
    "bracket_no_hydrogen",
    "e_z_coexistence",
    "element_diversity",
    "mapped_pair",
    "multiple_centers",
    "multicomponent",
    "ring",
    "stereo_free_baseline",
}


class SmilesRsWriterCorpusError(ValueError):
    """Raised when the fixed positive corpus is ambiguous or mutable."""


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise SmilesRsWriterCorpusError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _reject_float(_: str) -> None:
    raise SmilesRsWriterCorpusError("floating-point JSON values are forbidden")


def _reject_constant(_: str) -> None:
    raise SmilesRsWriterCorpusError("non-finite JSON values are forbidden")


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
        raise SmilesRsWriterCorpusError(f"{context} must be an object")
    if set(value) != expected:
        raise SmilesRsWriterCorpusError(f"{context} keys do not match the schema")
    return value


def _require_sha256(value: Any, context: str) -> str:
    if type(value) is not str or _LOWERCASE_SHA256.fullmatch(value) is None:
        raise SmilesRsWriterCorpusError(f"{context} must be lowercase SHA-256")
    return value


def _load_manifest() -> dict[str, Any]:
    raw = MANIFEST_PATH.read_bytes()
    if not 1 <= len(raw) <= _MAX_MANIFEST_BYTES:
        raise SmilesRsWriterCorpusError("manifest byte size is outside the fixed limit")
    try:
        document = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_float=_reject_float,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SmilesRsWriterCorpusError("manifest must be strict UTF-8 JSON") from exc
    document = _expect_exact_keys(document, _TOP_LEVEL_KEYS, "manifest")
    if _require_sha256(document["payload_sha256"], "payload_sha256") != (
        _manifest_payload_sha256(document)
    ):
        raise SmilesRsWriterCorpusError("manifest payload hash mismatch")

    cases = document["cases"]
    if type(cases) is not list or not cases:
        raise SmilesRsWriterCorpusError("cases must be a nonempty list")
    case_ids: list[str] = []
    pinned_values: list[str] = []
    count_keys = {
        "typed_tetrahedral_atom_count",
        "mapped_source_atom_count",
        "mapped_tetrahedral_atom_count",
        "bracket_hydrogen_tetrahedral_atom_count",
        "marker_flip_count",
        "typed_ez_bond_count",
        "directional_source_bond_count",
        "fragment_count",
        "ring_closure_count",
        "ring_size",
    }
    row_keys = {
        "source_center_atom_indices",
        "center_atom_maps",
        "target_stereo_labels",
        "target_rdkit_chiral_tags",
        "trial_markers",
        "final_markers",
        "final_atom_tokens",
    }
    for index, case_value in enumerate(cases):
        case = _expect_exact_keys(case_value, _CASE_KEYS, f"cases[{index}]")
        case_id = case["case_id"]
        if type(case_id) is not str or _CASE_ID.fullmatch(case_id) is None:
            raise SmilesRsWriterCorpusError(f"cases[{index}].case_id is invalid")
        if case["source_id"] != case_id:
            raise SmilesRsWriterCorpusError(
                f"cases[{index}].source_id must equal case_id"
            )
        if type(case["category"]) is not str:
            raise SmilesRsWriterCorpusError("case category must be a string")
        source = _expect_exact_keys(case["source"], {"kind", "value"}, "source")
        if source["kind"] != "ascii" or type(source["value"]) is not str:
            raise SmilesRsWriterCorpusError("case source must be inline ASCII")
        try:
            source_bytes = source["value"].encode("ascii")
        except UnicodeEncodeError as exc:
            raise SmilesRsWriterCorpusError("case source must be ASCII") from exc
        if not source_bytes or len(source_bytes) > 64 * 1024:
            raise SmilesRsWriterCorpusError("case source is outside parser byte limits")
        if b"\n" in source_bytes or b"\r" in source_bytes:
            raise SmilesRsWriterCorpusError("case source must be one unterminated line")
        if hashlib.sha256(source_bytes).hexdigest() != _require_sha256(
            case["source_sha256"], f"cases[{index}].source_sha256"
        ):
            raise SmilesRsWriterCorpusError("case source digest mismatch")

        expected = _expect_exact_keys(
            case["expected"], _EXPECTED_KEYS, f"cases[{index}].expected"
        )
        for key in _SHA256_EXPECTED_KEYS:
            _require_sha256(expected[key], f"cases[{index}].expected.{key}")
        pinned_values.extend(expected[key] for key in _PINNED_ONLY_EXPECTED_KEYS)
        if type(expected["output_ascii"]) is not str:
            raise SmilesRsWriterCorpusError("expected output must be ASCII text")
        try:
            output = expected["output_ascii"].encode("ascii")
        except UnicodeEncodeError as exc:
            raise SmilesRsWriterCorpusError("expected output must be ASCII") from exc
        if hashlib.sha256(output).hexdigest() != expected["output_sha256"]:
            raise SmilesRsWriterCorpusError("expected output digest mismatch")
        if type(expected["output_byte_count"]) is not int or (
            expected["output_byte_count"] != len(output)
        ):
            raise SmilesRsWriterCorpusError("expected output byte count mismatch")
        if type(expected["output_equals_input"]) is not bool or (
            expected["output_equals_input"] != (output == source_bytes)
        ):
            raise SmilesRsWriterCorpusError("expected input/output equality mismatch")
        for key in count_keys:
            if type(expected[key]) is not int or expected[key] < 0:
                raise SmilesRsWriterCorpusError(f"{key} must be nonnegative")
        for key in row_keys:
            if type(expected[key]) is not list:
                raise SmilesRsWriterCorpusError(f"{key} must be a list")
        typed_count = expected["typed_tetrahedral_atom_count"]
        if any(len(expected[key]) != typed_count for key in row_keys):
            raise SmilesRsWriterCorpusError("tetrahedral row counts do not match")
        if any(
            type(value) is not int for value in expected["source_center_atom_indices"]
        ):
            raise SmilesRsWriterCorpusError("source center indices are invalid")
        if any(
            value is not None and type(value) is not int
            for value in expected["center_atom_maps"]
        ):
            raise SmilesRsWriterCorpusError("center atom maps are invalid")
        if any(value not in {"R", "S"} for value in expected["target_stereo_labels"]):
            raise SmilesRsWriterCorpusError("target stereo labels are invalid")
        if any(
            value not in {"CHI_TETRAHEDRAL_CW", "CHI_TETRAHEDRAL_CCW"}
            for value in expected["target_rdkit_chiral_tags"]
        ):
            raise SmilesRsWriterCorpusError("target chiral tags are invalid")
        if any(value != "@" for value in expected["trial_markers"]):
            raise SmilesRsWriterCorpusError("trial markers are invalid")
        if any(value not in {"@", "@@"} for value in expected["final_markers"]):
            raise SmilesRsWriterCorpusError("final markers are invalid")
        if any(type(value) is not str for value in expected["final_atom_tokens"]):
            raise SmilesRsWriterCorpusError("final atom tokens are invalid")
        if expected["marker_flip_count"] != expected["final_markers"].count("@@"):
            raise SmilesRsWriterCorpusError("marker flip count is inconsistent")
        if expected["mapped_tetrahedral_atom_count"] != sum(
            value is not None for value in expected["center_atom_maps"]
        ):
            raise SmilesRsWriterCorpusError("mapped tetrahedral count is inconsistent")
        if (
            expected["mapped_tetrahedral_atom_count"]
            > expected["mapped_source_atom_count"]
        ):
            raise SmilesRsWriterCorpusError("mapped center count exceeds mapped atoms")
        if expected["bracket_hydrogen_tetrahedral_atom_count"] > typed_count:
            raise SmilesRsWriterCorpusError(
                "bracket-H center count exceeds typed centers"
            )
        case_ids.append(case_id)
    if case_ids != sorted(case_ids) or len(case_ids) != len(set(case_ids)):
        raise SmilesRsWriterCorpusError("case IDs must be sorted and unique")
    if any(value == ZERO_SHA256 for value in pinned_values):
        raise SmilesRsWriterCorpusError(
            "pinned artifact digests must be fully frozen and nonzero"
        )
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


def test_manifest_contract_hash_inventory_upstream_binding_and_scope_are_exact() -> (
    None
):
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
        "tetrahedral_stereo_profile_id": TETRAHEDRAL_PROFILE_ID,
        "tetrahedral_stereo_admission_scope": (
            "canonical_normalized_parser_typed_cw_ccw_with_at_most_256_centers_"
            "at_most_514_source_atoms_and_zero_or_one_bracket_hydrogen_per_center"
        ),
        "max_typed_tetrahedral_atom_count": 256,
        "max_tetrahedral_calibration_source_atom_count": 514,
        "artifact_digest_policy_id": (
            "pinned_expected_with_dynamic_public_factory_artifact_self_hash_"
            "reverification/1.0.0"
        ),
        "static_pinned_artifact_digests_included": True,
        "static_pinned_artifact_digest_rdkit_requirement": "rdkit==2025.9.6",
        "upstream_ingest_corpus_schema_id": "betelgeuze.v2_1_ingest_corpus/1.4.0",
        "upstream_ingest_corpus_id": (
            "v2_1_supported_ingest_identity_context_and_failure_v5"
        ),
        "upstream_ingest_r_s_case_ids": ["smiles_chiral_r", "smiles_chiral_s"],
        "upstream_ingest_r_s_case_record_sha256": {
            "smiles_chiral_r": (
                "b67dbdf4ca12f4a18aadc250ddc828a12db16aeb1f01964872f744bba00888a7"
            ),
            "smiles_chiral_s": (
                "b61d219596a8e8be014a7c9ef5c4c97d736e8d3b967a015e1102b3ce12d3d1f0"
            ),
        },
    }
    assert document["claim_boundary"] == {
        "bounded_normalized_spelling_admitted_parser_typed_tetrahedral_preserved": True,
        "bounded_atom_maps_preserved": True,
        "parser_observed_r_s_labels_reproduced": True,
        "general_parser_typed_tetrahedral_preserved": False,
        "general_atom_map_preservation_claimed": False,
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
    assert len(cases) == 14
    assert {case["case_id"] for case in cases} == _EXPECTED_CASE_IDS
    assert {case["category"] for case in cases} == _EXPECTED_CATEGORIES
    by_id = {case["case_id"]: case for case in cases}
    assert (
        by_id["bracket_h_r"]["expected"]["bracket_hydrogen_tetrahedral_atom_count"] == 1
    )
    assert by_id["no_h_r"]["expected"]["bracket_hydrogen_tetrahedral_atom_count"] == 0
    assert by_id["mapped_r"]["expected"]["center_atom_maps"] == [17]
    assert by_id["mapped_s"]["expected"]["target_stereo_labels"] == ["S"]
    assert by_id["multi_center"]["expected"]["target_stereo_labels"] == ["R", "S"]
    assert by_id["ring_center"]["expected"]["ring_closure_count"] == 1
    assert by_id["ez_coexistence"]["expected"]["typed_ez_bond_count"] == 1
    assert by_id["multi_component"]["expected"]["fragment_count"] == 2
    assert (
        by_id["stereo_free_baseline"]["expected"]["typed_tetrahedral_atom_count"] == 0
    )
    assert {
        by_id[case_id]["expected"]["final_atom_tokens"][0]
        for case_id in ("boron_center", "charged_n_center", "sulfur_center")
    } == {"[B@-]", "[N@+]", "[S@]"}

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
    upstream_ids = set(document["contracts"]["upstream_ingest_r_s_case_ids"])
    upstream_records = {
        case["case_id"]: hashlib.sha256(_canonical_json_bytes(case)).hexdigest()
        for case in upstream["cases"]
        if case["case_id"] in upstream_ids
    }
    assert (
        upstream_records
        == document["contracts"]["upstream_ingest_r_s_case_record_sha256"]
    )


@pytest.mark.parametrize("case_id", sorted(_EXPECTED_CASE_IDS))
def test_positive_fixed_point_replays_projection_public_artifacts_and_abstentions(
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
    projection = source_state.tetrahedral_stereo_projection_document
    rows = projection["atom_rows"]

    assert result.write_result.payload == output
    assert hashlib.sha256(output).hexdigest() == expected["output_sha256"]
    assert receipt.output_byte_count == expected["output_byte_count"]
    assert (output == source) is expected["output_equals_input"]
    assert write_smiles(result.reparsed_ingest.system).payload == output
    result.write_result.__post_init__()
    result.__post_init__()

    assert (
        source_state.canonical_topology_sha256 == expected["canonical_topology_sha256"]
    )
    assert (
        canonical_topology_sha256(result.source_ingest.system)
        == expected["canonical_topology_sha256"]
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
        == expected["tetrahedral_stereo_projection_sha256"]
    )
    assert source_state.representable_state_document == (
        reparsed_state.representable_state_document
    )
    assert source_state.tetrahedral_stereo_projection_document == (
        reparsed_state.tetrahedral_stereo_projection_document
    )

    assert projection["schema_id"] == SMILES_TETRAHEDRAL_STEREO_PROJECTION_SCHEMA_ID
    assert projection["tetrahedral_stereo_profile_id"] == TETRAHEDRAL_PROFILE_ID
    assert (
        projection["typed_tetrahedral_atom_count"]
        == expected["typed_tetrahedral_atom_count"]
    )
    assert (
        projection["mapped_tetrahedral_atom_count"]
        == expected["mapped_tetrahedral_atom_count"]
    )
    assert (
        projection["bracket_hydrogen_tetrahedral_atom_count"]
        == expected["bracket_hydrogen_tetrahedral_atom_count"]
    )
    assert projection["marker_flip_count"] == expected["marker_flip_count"]
    parse_count = int(bool(expected["typed_tetrahedral_atom_count"]))
    assert projection["calibration_trial_parse_count"] == parse_count
    assert projection["calibration_final_parse_count"] == parse_count
    assert [row["source_atom_index"] for row in rows] == expected[
        "source_center_atom_indices"
    ]
    assert [row["atom_map"] for row in rows] == expected["center_atom_maps"]
    assert [row["target_stereo"] for row in rows] == expected["target_stereo_labels"]
    assert [row["target_rdkit_chiral_tag"] for row in rows] == expected[
        "target_rdkit_chiral_tags"
    ]
    assert [row["trial_marker"] for row in rows] == expected["trial_markers"]
    assert [row["final_marker"] for row in rows] == expected["final_markers"]
    assert [row["final_atom_token"] for row in rows] == expected["final_atom_tokens"]
    assert [row["marker_flipped"] for row in rows] == [
        marker == "@@" for marker in expected["final_markers"]
    ]
    assert all(row["target_stereo"] == row["final_stereo"] for row in rows)
    assert all(
        row["target_rdkit_chiral_tag"] == row["final_rdkit_chiral_tag"] for row in rows
    )
    assert projection["independent_cip_assignment"] is False
    assert projection["stereo_completeness_assessed"] is False
    assert projection["stereo_geometry_assessed"] is False

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
    assert receipt.input_cycle_projection_sha256 == source_state.cycle_projection_sha256
    assert receipt.input_aromatic_projection_sha256 == (
        source_state.aromatic_projection_sha256
    )
    assert receipt.input_ez_stereo_projection_sha256 == (
        source_state.ez_stereo_projection_sha256
    )
    assert receipt.input_tetrahedral_stereo_projection_sha256 == (
        source_state.tetrahedral_stereo_projection_sha256
    )
    assert receipt.tetrahedral_stereo_projection_schema_id == (
        SMILES_TETRAHEDRAL_STEREO_PROJECTION_SCHEMA_ID
    )
    assert receipt.tetrahedral_stereo_profile_id == TETRAHEDRAL_PROFILE_ID
    assert (
        receipt.typed_tetrahedral_atom_count == expected["typed_tetrahedral_atom_count"]
    )
    assert receipt.mapped_source_atom_count == expected["mapped_source_atom_count"]
    assert receipt.typed_ez_bond_count == expected["typed_ez_bond_count"]
    assert (
        receipt.directional_source_bond_count
        == expected["directional_source_bond_count"]
    )
    assert receipt.fragment_count == expected["fragment_count"]
    assert receipt.ring_closure_count == expected["ring_closure_count"]
    assert receipt.ring_size == expected["ring_size"]
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
    assert report.input_cycle_projection_sha256 == (
        report.reparsed_cycle_projection_sha256
    )
    assert report.input_aromatic_projection_sha256 == (
        report.reparsed_aromatic_projection_sha256
    )
    assert report.input_ez_stereo_projection_sha256 == (
        report.reparsed_ez_stereo_projection_sha256
    )
    assert report.input_tetrahedral_stereo_projection_sha256 == (
        report.reparsed_tetrahedral_stereo_projection_sha256
    )
    assert report_document["emitted_source_sha256_and_bytes_stable"] is True
    assert report_document["tetrahedral_stereo_projection_sha256_equal"] is True
    assert report_document["report_sha256"] == _artifact_sha256(
        report_document, "report_sha256"
    )

    assert canonical_all_atom_snapshot_digest(result.source_ingest.system) == (
        canonical_all_atom_snapshot_digest(result.reparsed_ingest.system)
    )
    assert smiles_representable_state_sha256(result.source_ingest.system) == (
        smiles_representable_state_sha256(result.reparsed_ingest.system)
    )
    assert (
        result.source_ingest.system.provenance.metadata["parser_observation_sha256"]
        == result.reparsed_ingest.system.provenance.metadata[
            "parser_observation_sha256"
        ]
    )

    coverage = result.source_ingest.coverage.to_dict()
    assert (
        coverage["typed_atom_stereo_count"] == expected["typed_tetrahedral_atom_count"]
    )
    assert coverage["atom_map_count"] == expected["mapped_source_atom_count"]
    assert coverage["chemistry_supported"] is False
    assert coverage["parameterability_assessed"] is False
    assert coverage["preparation_ready"] is False
    assert coverage["claim_safe"] is False
    for artifact in (receipt_document, report_document):
        assert artifact["source_authentication_status"] == "not_authenticated"
        assert artifact["preparation_ready"] is False
        assert artifact["parameterability_assessed"] is False
        assert artifact["simulation_ready"] is False
        assert artifact["claim_safe"] is False
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


def test_opposite_mapped_r_s_artifacts_are_distinct_and_cannot_be_crosswired(
    supported_rdkit_contract: tuple[str, bool],
) -> None:
    left = round_trip_smiles_source(b"F[C@H:17](Cl)Br", source_id="mapped-r")
    right = round_trip_smiles_source(b"F[C@@H:17](Cl)Br", source_id="mapped-s")
    left_system = left.source_ingest.system
    right_system = right.source_ingest.system
    left_state = writer_module._validate_write_state(left_system)
    right_state = writer_module._validate_write_state(right_system)

    assert [
        (atom.element, atom.formal_charge, atom.atom_map) for atom in left_system.atoms
    ] == [
        (atom.element, atom.formal_charge, atom.atom_map) for atom in right_system.atoms
    ]
    assert [(bond.atom_i, bond.atom_j, bond.order) for bond in left_system.bonds] == [
        (bond.atom_i, bond.atom_j, bond.order) for bond in right_system.bonds
    ]
    assert (
        left_state.tetrahedral_stereo_projection_document["atom_rows"][0][
            "target_stereo"
        ]
        == "R"
    )
    assert (
        right_state.tetrahedral_stereo_projection_document["atom_rows"][0][
            "target_stereo"
        ]
        == "S"
    )
    assert canonical_topology_sha256(left_system) != canonical_topology_sha256(
        right_system
    )
    assert left_state.ordered_topology_sha256 != right_state.ordered_topology_sha256
    assert left_state.tetrahedral_stereo_projection_sha256 != (
        right_state.tetrahedral_stereo_projection_sha256
    )
    assert smiles_representable_state_sha256(left_system) != (
        smiles_representable_state_sha256(right_system)
    )
    assert canonical_all_atom_snapshot_digest(left_system) != (
        canonical_all_atom_snapshot_digest(right_system)
    )
    assert left.write_result.receipt.receipt_sha256 != (
        right.write_result.receipt.receipt_sha256
    )
    assert left.report.report_sha256 != right.report.report_sha256

    with pytest.raises(ValueError, match="regenerated SMILES bindings"):
        type(left.write_result)(
            payload=right.write_result.payload,
            receipt=right.write_result.receipt,
            input_system=left_system,
            _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
        )
    with pytest.raises(ValueError, match="cross-consistent"):
        type(left)(
            source_ingest=right.source_ingest,
            write_result=left.write_result,
            reparsed_ingest=left.reparsed_ingest,
            report=left.report,
            _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
        )


def test_public_tetrahedral_artifact_digest_tampering_fails_closed(
    supported_rdkit_contract: tuple[str, bool],
) -> None:
    receipt_tampered = round_trip_smiles_source(b"F[C@H:17](Cl)Br")
    object.__setattr__(
        receipt_tampered.write_result.receipt,
        "input_tetrahedral_stereo_projection_sha256",
        ZERO_SHA256,
    )
    with pytest.raises(ValueError, match="regenerated SMILES bindings"):
        receipt_tampered.write_result.__post_init__()

    report_tampered = round_trip_smiles_source(b"F[C@H:17](Cl)Br")
    object.__setattr__(
        report_tampered.report,
        "input_tetrahedral_stereo_projection_sha256",
        ZERO_SHA256,
    )
    with pytest.raises(ValueError, match="cross-consistent"):
        report_tampered.__post_init__()


@pytest.mark.parametrize(
    ("source", "error_type", "code"),
    [
        (b"F[C@H](F)Br", SmilesParseError, "stereo_marker_not_retained"),
        (b"[C@H](F)(Cl)Br", SmilesWriteError, "normalized_smiles_hash_mismatch"),
        (b"F[Pt@SP1](Cl)(Br)I", SmilesParseError, "unsupported_atom_stereo"),
    ],
)
def test_nonadmitted_tetrahedral_sources_fail_closed(
    source: bytes,
    error_type: type[Exception],
    code: str,
    supported_rdkit_contract: tuple[str, bool],
) -> None:
    with pytest.raises(error_type) as exc_info:
        round_trip_smiles_source(source, source_id="nonadmitted-tetrahedral")
    assert getattr(exc_info.value, "code") == code


def test_forged_tetrahedral_tag_and_claim_boundary_fail_closed(
    supported_rdkit_contract: tuple[str, bool],
) -> None:
    system = parse_smiles(b"F[C@H:17](Cl)Br").system
    center = system.atoms[1]
    opposite_tag = (
        "CHI_TETRAHEDRAL_CW"
        if center.metadata["rdkit_chiral_tag"] == "CHI_TETRAHEDRAL_CCW"
        else "CHI_TETRAHEDRAL_CCW"
    )
    metadata = dict(center.metadata)
    metadata["rdkit_chiral_tag"] = opposite_tag
    changed_atoms = list(system.atoms)
    changed_atoms[1] = replace(center, metadata=metadata)
    with pytest.raises(SmilesWriteError) as tag_exc:
        write_smiles(replace(system, atoms=tuple(changed_atoms)))
    assert tag_exc.value.code == "tetrahedral_calibration_failed"

    changed_atoms[1] = replace(center, stereo="UNKNOWN")
    with pytest.raises(SmilesWriteError) as stereo_exc:
        write_smiles(replace(system, atoms=tuple(changed_atoms)))
    assert stereo_exc.value.code == "unsupported_atom_stereo"

    claim_boundary = _load_manifest()["claim_boundary"]
    assert claim_boundary["independent_cip_assignment_claimed"] is False
    assert claim_boundary["stereo_completeness_claimed"] is False
    assert claim_boundary["stereo_geometry_claimed"] is False
    assert claim_boundary["source_authenticated"] is False
    assert claim_boundary["chemistry_supported"] is False
    assert claim_boundary["preparation_ready"] is False
    assert claim_boundary["parameterability_assessed"] is False
    assert claim_boundary["simulation_ready"] is False
    assert claim_boundary["claim_safe"] is False
