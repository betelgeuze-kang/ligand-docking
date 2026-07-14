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
    mmcif_polymer_sequence_nonpoly_component_topology as composition_module,
)
from betelgeuze_engine_v2.molecular.mmcif_nonpoly_component_topology import (
    MAX_MMCIF_NONPOLY_COMPONENT_ATOM_ROWS,
    MAX_MMCIF_NONPOLY_COMPONENT_BOND_ROWS,
    MAX_MMCIF_NONPOLY_COMPONENT_ROWS,
    MMCIF_NONPOLY_COMPONENT_TOPOLOGY_PROFILE_ID,
)
from betelgeuze_engine_v2.molecular.mmcif_polymer_sequence import (
    MAX_MMCIF_POLYMER_SEQUENCE_ROWS,
    MMCIF_POLYMER_SEQUENCE_PROFILE_ID,
)
from betelgeuze_engine_v2.molecular.mmcif_polymer_sequence_nonpoly_component_topology import (
    MAX_MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_INPUT_BYTES,
    MAX_MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_OUTPUT_BYTES,
    MAX_MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_OUTPUT_LINE_CHARS,
    MAX_MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_SOURCE_ID_BYTES,
    MAX_MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_TOKEN_CHARS,
    MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_ENVELOPE_VERSION,
    MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_PARSER_NAME,
    MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_PARSER_VERSION,
    MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_PROFILE_ID,
    MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_ROUND_TRIP_REPORT_SCHEMA_ID,
    MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_SOURCE_BINDING_SCHEMA_ID,
    MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_STATE_SCHEMA_ID,
    MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_WRITER_VERSION,
    MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_WRITE_RECEIPT_SCHEMA_ID,
    MmcifPolymerSequenceNonpolyComponentTopologyError,
    parse_mmcif_polymer_sequence_nonpoly_component_topology,
    round_trip_mmcif_polymer_sequence_nonpoly_component_topology_source,
)
from betelgeuze_engine_v2.molecular.mmcif_writer import MMCIF_WRITER_VERSION
from betelgeuze_engine_v2.molecular.pdb_mmcif import MMCIF_PARSER_VERSION
from betelgeuze_engine_v2.molecular.topology import CANONICAL_TOPOLOGY_SCHEMA_ID


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = (
    ROOT
    / "config"
    / "independent_engine_v2_v2_1_mmcif_polymer_sequence_nonpoly_component_topology_composition_corpus.json"
)
FIXTURE_ROOT = (
    ROOT
    / "tests"
    / "fixtures"
    / "v2_1_mmcif_polymer_sequence_nonpoly_component_topology_composition"
)
CORPUS_SCHEMA_ID = "betelgeuze.v2_1_mmcif_polymer_sequence_nonpoly_component_topology_composition_corpus/1.0.0"
CORPUS_ID = (
    "v2_1_strict_mmcif_polymer_sequence_nonpoly_component_topology_composition_v1"
)
PAYLOAD_HASH_POLICY_ID = "sha256_canonical_json_without_payload_sha256/1.0.0"
EXPECTED_PAYLOAD_SHA256 = (
    "6ac10b99e058134bdcbf1739afd7d2d719dd15667890530e9c716beb14592e69"
)

_LOWER_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_CASE_ID = re.compile(r"^[a-z][a-z0-9_]*$")
_MAX_MANIFEST_BYTES = 1024 * 1024
_MAX_FIXTURE_BYTES = 32 * 1024
_MAX_TOTAL_FIXTURE_BYTES = 64 * 1024

_ROUND_TRIP_CASE_IDS = (
    "mixed_polymer_methane_sequence_complete",
    "category_order_variant",
)
_FAILURE_CASES = {
    "failure_missing_sequence_category": "unsupported_category_surface",
    "failure_extra_category": "unsupported_category_surface",
    "failure_scalar_sequence_representation": "unsupported_category_representation",
    "failure_sequence_header_order": "unsupported_category_headers",
    "failure_sequence_join": "polymer_child_rejected",
    "failure_component_instance_atom_coverage": "component_child_rejected",
}
_FALSE_GATES = (
    "source_authenticated",
    "auth_label_equivalence_inferred",
    "reference_sequence_equivalence_assessed",
    "coordinate_observation_completeness_assessed",
    "polymer_templates_supported",
    "polymer_template_chemistry_supported",
    "polymer_template_interpreted",
    "polymer_chemistry_interpreted",
    "modified_residue_identity_assessed",
    "microheterogeneity_interpreted",
    "independent_chemistry_established",
    "independent_valence_established",
    "independent_aromaticity_established",
    "independent_stereo_established",
    "chemistry_inferred",
    "chemistry_interpreted",
    "generic_chemistry_supported",
    "role_assignment_interpreted",
    "bond_topology_interpreted_beyond_component_child",
    "struct_conn_interpreted",
    "general_struct_conn_supported",
    "general_struct_conn_interpreted",
    "inter_residue_bonds_interpreted",
    "inter_residue_bonds_supported",
    "cross_component_bonds_interpreted",
    "cross_component_bonds_supported",
    "coordination_interpreted",
    "charge_interpreted_beyond_component_child",
    "protonation_interpreted",
    "tautomer_interpreted",
    "missing_residue_fact_claimed",
    "missing_residue_fact_established",
    "sequence_completeness_claimed",
    "sequence_completeness_assessed",
    "altloc_composition_supported",
    "assembly_composition_supported",
    "biological_assembly_composition_supported",
    "missingness_composition_supported",
    "cell_composition_supported",
    "multimodel_composition_supported",
    "preparation_ready",
    "generic_preparation_ready",
    "generic_molecular_preparation_ready",
    "global_preparation_ready",
    "global_molecular_preparation_ready",
    "parameterability_assessed",
    "physics_supported",
    "runtime_eligible",
    "simulation_ready",
    "execution_authorized",
    "claim_safe",
    "general_mmcif_topology_complete",
    "general_mmcif_round_trip_evidence_ready",
    "all_format_round_trip_evidence_ready",
    "v2_1_complete",
    "base_system_snapshot_equality_required",
    "new_system_parser_pedigree_introduced",
)
_EVIDENCE_KEYS = {
    "base_representable_state_sha256",
    "base_topology_sha256",
    "canonical_nonpoly_writer_payload_sha256",
    "canonical_output_sha256",
    "canonical_shared_loop_sha256",
    "canonical_shared_loops_byte_equal",
    "component_augmented_system_snapshot_sha256",
    "component_augmented_topology_sha256",
    "component_child_and_polymer_child_cross_bound",
    "component_child_canonical_output_sha256",
    "component_child_source_binding_sha256",
    "component_child_source_sha256",
    "component_projection_sha256",
    "component_topology_state_sha256",
    "composition_round_trip_preserved",
    "data_block_name_sha256",
    "emitted_source_reparsed_exact",
    "emitted_source_sha256",
    "full_nine_category_source_sha256",
    "nonpoly_identity_projection_sha256",
    "nonpoly_identity_record_state_sha256",
    "output_byte_count",
    "polymer_child_canonical_output_sha256",
    "polymer_child_source_binding_sha256",
    "polymer_child_source_sha256",
    "polymer_sequence_projection_sha256",
    "polymer_sequence_record_state_sha256",
    "polymer_sequence_row_count",
    "record_state_sha256",
    "reparsed_full_source_sha256",
    "report_sha256",
    "second_emission_byte_stable",
    "source_binding_sha256",
    "source_id_sha256",
    "write_receipt_sha256",
}

_SEQUENCE_LOOP = b"""loop_
_entity_poly_seq.entity_id
_entity_poly_seq.num
_entity_poly_seq.mon_id
_entity_poly_seq.hetero
1 1 GLY n
1 2 ALA n
#
"""
_SCALAR_SEQUENCE = b"""_entity_poly_seq.entity_id 1
_entity_poly_seq.num 1
_entity_poly_seq.mon_id GLY
_entity_poly_seq.hetero n
#
"""
_EXTRA_CATEGORY = b"""loop_
_audit_author.name
CorpusAuthor
#
"""
_ATOM_SITE_HEADER = b"""loop_
_atom_site.group_PDB
"""
_MET_H4_ATOM_ROW = (
    b"HETATM 6 H H4 . MET L 2 . ? 0.625 -0.625 -0.625 1.00 10.00 ? 2 MET L H4 1\n"
)


class CompositionCorpusError(ValueError):
    pass


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    document: dict[str, Any] = {}
    for key, value in pairs:
        if key in document:
            raise CompositionCorpusError("duplicate manifest key")
        document[key] = value
    return document


def _parse_bounded_integer(token: str) -> int:
    digits = token[1:] if token.startswith("-") else token
    if len(digits) > 20:
        raise CompositionCorpusError("JSON integer exceeds corpus bounds")
    return int(token)


def _parse_manifest_json(text: str) -> dict[str, Any]:
    try:
        value = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=lambda _token: (_ for _ in ()).throw(
                CompositionCorpusError("nonstandard JSON constant")
            ),
            parse_float=lambda _token: (_ for _ in ()).throw(
                CompositionCorpusError("floating JSON number")
            ),
            parse_int=_parse_bounded_integer,
        )
    except (json.JSONDecodeError, RecursionError) as exc:
        raise CompositionCorpusError("manifest must be strict JSON") from exc
    if type(value) is not dict:
        raise CompositionCorpusError("manifest root must be an object")
    return value


def _load_manifest() -> dict[str, Any]:
    config_root = (ROOT / "config").resolve(strict=True)
    path = MANIFEST.resolve(strict=True)
    if (
        path.parent != config_root
        or path.is_symlink()
        or path.name
        != "independent_engine_v2_v2_1_mmcif_polymer_sequence_nonpoly_component_topology_composition_corpus.json"
        or not path.is_file()
        or path.stat().st_size > _MAX_MANIFEST_BYTES
    ):
        raise CompositionCorpusError("manifest is absent or exceeds its byte cap")
    raw = path.read_bytes()
    if not raw.endswith(b"\n") or raw.endswith(b"\n\n") or b"\r" in raw:
        raise CompositionCorpusError("manifest must use one final LF and no CR")
    try:
        text = raw.decode("utf-8")
    except UnicodeError as exc:
        raise CompositionCorpusError("manifest must be UTF-8") from exc
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
        raise CompositionCorpusError("fixture name must be text")
    pure = PurePosixPath(name)
    if (
        pure.is_absolute()
        or len(pure.parts) != 1
        or pure.suffix != ".cif"
        or pure.name != name
    ):
        raise CompositionCorpusError("fixture path escapes the exact corpus root")
    fixture_root = FIXTURE_ROOT.resolve(strict=True)
    candidate = FIXTURE_ROOT / pure.name
    if candidate.is_symlink():
        raise CompositionCorpusError("fixture symlinks are forbidden")
    path = candidate.resolve(strict=True)
    if path.parent != fixture_root or not path.is_file():
        raise CompositionCorpusError("fixture path is outside the exact corpus root")
    payload = path.read_bytes()
    if len(payload) > _MAX_FIXTURE_BYTES:
        raise CompositionCorpusError("fixture exceeds its byte cap")
    return path, payload


def _replace_once(source: bytes, old: bytes, new: bytes) -> bytes:
    if not old or source.count(old) != 1:
        raise AssertionError("mutation source must occur exactly once")
    return source.replace(old, new, 1)


def _mutate(source: bytes, mutation_id: str) -> bytes:
    if mutation_id == "missing_sequence_category":
        return _replace_once(source, _SEQUENCE_LOOP, b"")
    if mutation_id == "extra_category":
        return _replace_once(
            source, _ATOM_SITE_HEADER, _EXTRA_CATEGORY + _ATOM_SITE_HEADER
        )
    if mutation_id == "scalar_sequence_representation":
        return _replace_once(source, _SEQUENCE_LOOP, _SCALAR_SEQUENCE)
    if mutation_id == "sequence_header_order":
        return _replace_once(
            source,
            b"_entity_poly_seq.entity_id\n_entity_poly_seq.num\n",
            b"_entity_poly_seq.num\n_entity_poly_seq.entity_id\n",
        )
    if mutation_id == "sequence_join":
        return _replace_once(source, b"1 1 GLY n\n", b"1 1 SER n\n")
    if mutation_id == "component_instance_atom_coverage":
        return _replace_once(source, _MET_H4_ATOM_ROW, b"")
    raise CompositionCorpusError("unknown corpus mutation")


def _replay(case: dict[str, Any]) -> tuple[dict[str, Any], Any]:
    _path, source = _fixture_payload(case["fixture"])
    result = round_trip_mmcif_polymer_sequence_nonpoly_component_topology_source(
        source, source_id=case["source_id"]
    )
    artifacts = result.to_dict()
    ingest = artifacts["source_ingest"]
    component = ingest["component_child"]
    polymer = ingest["polymer_child"]
    shared = ingest["shared_nonpoly_base"]
    receipt = artifacts["write_result"]["receipt"]
    report = artifacts["report"]
    return (
        {
            "base_representable_state_sha256": shared[
                "base_representable_state_sha256"
            ],
            "base_topology_sha256": shared["base_topology_sha256"],
            "canonical_nonpoly_writer_payload_sha256": shared[
                "canonical_nonpoly_writer_payload_sha256"
            ],
            "canonical_output_sha256": ingest["canonical_output_sha256"],
            "canonical_shared_loop_sha256": ingest["canonical_shared_loop_sha256"],
            "canonical_shared_loops_byte_equal": ingest[
                "canonical_shared_loops_byte_equal"
            ],
            "component_augmented_system_snapshot_sha256": ingest[
                "component_augmented_system_snapshot_sha256"
            ],
            "component_augmented_topology_sha256": component[
                "augmented_topology_sha256"
            ],
            "component_child_and_polymer_child_cross_bound": ingest[
                "component_child_and_polymer_child_cross_bound"
            ],
            "component_child_canonical_output_sha256": ingest[
                "component_child_canonical_output_sha256"
            ],
            "component_child_source_binding_sha256": ingest[
                "component_child_source_binding_sha256"
            ],
            "component_child_source_sha256": ingest["component_child_source_sha256"],
            "component_projection_sha256": component["component_projection_sha256"],
            "component_topology_state_sha256": component[
                "component_topology_state_sha256"
            ],
            "composition_round_trip_preserved": report[
                "composition_round_trip_preserved"
            ],
            "data_block_name_sha256": ingest["data_block_name_sha256"],
            "emitted_source_reparsed_exact": report["emitted_source_reparsed_exact"],
            "emitted_source_sha256": report["emitted_source_sha256"],
            "full_nine_category_source_sha256": ingest[
                "full_nine_category_source_sha256"
            ],
            "nonpoly_identity_projection_sha256": shared[
                "nonpoly_identity_projection_sha256"
            ],
            "nonpoly_identity_record_state_sha256": shared[
                "nonpoly_identity_record_state_sha256"
            ],
            "output_byte_count": receipt["output_byte_count"],
            "polymer_child_canonical_output_sha256": ingest[
                "polymer_child_canonical_output_sha256"
            ],
            "polymer_child_source_binding_sha256": ingest[
                "polymer_child_source_binding_sha256"
            ],
            "polymer_child_source_sha256": ingest["polymer_child_source_sha256"],
            "polymer_sequence_projection_sha256": polymer[
                "polymer_sequence_projection_sha256"
            ],
            "polymer_sequence_record_state_sha256": polymer[
                "polymer_sequence_record_state_sha256"
            ],
            "polymer_sequence_row_count": ingest["polymer_sequence_row_count"],
            "record_state_sha256": ingest["record_state_sha256"],
            "reparsed_full_source_sha256": report["reparsed_full_source_sha256"],
            "report_sha256": report["report_sha256"],
            "second_emission_byte_stable": report["second_emission_byte_stable"],
            "source_binding_sha256": ingest["source_binding_sha256"],
            "source_id_sha256": ingest["source_id_sha256"],
            "write_receipt_sha256": receipt["receipt_sha256"],
        },
        result,
    )


def _expected_contracts() -> dict[str, Any]:
    return {
        "all_atom_schema_id": ALL_ATOM_SCHEMA_ID,
        "base_mmcif_parser_version": MMCIF_PARSER_VERSION,
        "base_mmcif_writer_version": MMCIF_WRITER_VERSION,
        "canonical_category_order": [
            "_entity",
            "_struct_asym",
            "_entity_poly_seq",
            "_chem_comp",
            "_chem_comp_atom",
            "_chem_comp_bond",
            "_pdbx_entity_nonpoly",
            "_pdbx_nonpoly_scheme",
            "_atom_site",
        ],
        "canonical_topology_schema_id": CANONICAL_TOPOLOGY_SCHEMA_ID,
        "component_child_profile_id": MMCIF_NONPOLY_COMPONENT_TOPOLOGY_PROFILE_ID,
        "envelope_version": (
            MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_ENVELOPE_VERSION
        ),
        "parser_name": MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_PARSER_NAME,
        "parser_version": (
            MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_PARSER_VERSION
        ),
        "polymer_child_profile_id": MMCIF_POLYMER_SEQUENCE_PROFILE_ID,
        "profile_id": MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_PROFILE_ID,
        "round_trip_report_schema_id": (
            MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_ROUND_TRIP_REPORT_SCHEMA_ID
        ),
        "source_binding_schema_id": (
            MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_SOURCE_BINDING_SCHEMA_ID
        ),
        "state_schema_id": (
            MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_STATE_SCHEMA_ID
        ),
        "write_receipt_schema_id": (
            MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_WRITE_RECEIPT_SCHEMA_ID
        ),
        "writer_version": (
            MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_WRITER_VERSION
        ),
    }


def test_manifest_payload_contracts_and_claim_boundary_are_exact() -> None:
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
    assert document["contracts"] == _expected_contracts()
    assert document["claim_boundary"] == {
        "canonical_shared_loops_byte_equal": True,
        "component_child_owns_molecular_system": True,
        "exact_nine_category_composition_required": True,
        "generic_molecular_preparation_ready": False,
        "polymer_sequence_is_source_evidence_only": True,
        "shared_nonpoly_base_cross_bound": True,
        "v2_1_complete": False,
    }
    assert document["limits"] == {
        "input_bytes": (
            MAX_MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_INPUT_BYTES
        ),
        "output_bytes": (
            MAX_MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_OUTPUT_BYTES
        ),
        "output_line_characters": (
            MAX_MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_OUTPUT_LINE_CHARS
        ),
        "polymer_sequence_rows": MAX_MMCIF_POLYMER_SEQUENCE_ROWS,
        "component_rows": MAX_MMCIF_NONPOLY_COMPONENT_ROWS,
        "component_atom_rows": MAX_MMCIF_NONPOLY_COMPONENT_ATOM_ROWS,
        "component_bond_rows": MAX_MMCIF_NONPOLY_COMPONENT_BOND_ROWS,
        "source_id_utf8_bytes": (
            MAX_MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_SOURCE_ID_BYTES
        ),
        "token_characters": (
            MAX_MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_TOKEN_CHARS
        ),
    }
    assert document["false_claims"] == {field: False for field in _FALSE_GATES}


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
    with pytest.raises(CompositionCorpusError):
        _parse_manifest_json(payload)


def test_manifest_and_fixture_byte_caps_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(globals(), "_MAX_MANIFEST_BYTES", 1)
    with pytest.raises(CompositionCorpusError):
        _load_manifest()
    monkeypatch.setitem(globals(), "_MAX_MANIFEST_BYTES", 1024 * 1024)
    monkeypatch.setitem(globals(), "_MAX_FIXTURE_BYTES", 1)
    with pytest.raises(CompositionCorpusError):
        _fixture_payload("mixed_polymer_methane_sequence_complete.cif")


@pytest.mark.parametrize(
    "name",
    (
        str((FIXTURE_ROOT / "mixed_polymer_methane_sequence_complete.cif").resolve()),
        "../mixed_polymer_methane_sequence_complete.cif",
        "nested/mixed_polymer_methane_sequence_complete.cif",
        "./mixed_polymer_methane_sequence_complete.cif",
        "mixed_polymer_methane_sequence_complete.cif/",
        "mixed_polymer_methane_sequence_complete.txt",
    ),
)
def test_fixture_resolver_rejects_paths_outside_exact_corpus(name: str) -> None:
    with pytest.raises(CompositionCorpusError):
        _fixture_payload(name)


def test_fixture_inventory_case_shapes_and_hashes_are_exact() -> None:
    document = _load_manifest()
    fixture_paths = [fixture["path"] for fixture in document["fixtures"]]
    assert len(fixture_paths) == 2
    assert len(set(fixture_paths)) == len(fixture_paths)
    referenced: set[Path] = set()
    total_bytes = 0
    for fixture in document["fixtures"]:
        assert set(fixture) == {"path", "byte_count", "sha256"}
        pure = PurePosixPath(fixture["path"])
        assert pure.parts[:3] == (
            "tests",
            "fixtures",
            "v2_1_mmcif_polymer_sequence_nonpoly_component_topology_composition",
        )
        assert len(pure.parts) == 4 and ".." not in pure.parts
        path, payload = _fixture_payload(pure.name)
        assert len(payload) == fixture["byte_count"]
        assert hashlib.sha256(payload).hexdigest() == fixture["sha256"]
        referenced.add(path)
        total_bytes += len(payload)
    assert referenced == {path.resolve() for path in FIXTURE_ROOT.glob("*.cif")}
    assert total_bytes <= _MAX_TOTAL_FIXTURE_BYTES

    cases = document["cases"]
    assert [case["case_id"] for case in cases] == [
        *_ROUND_TRIP_CASE_IDS,
        *_FAILURE_CASES,
    ]
    round_trip_fixture_counts = {
        fixture["path"]: sum(
            case["kind"] == "round_trip"
            and fixture["path"].endswith(f"/{case['fixture']}")
            for case in cases
        )
        for fixture in document["fixtures"]
    }
    assert set(round_trip_fixture_counts.values()) == {1}
    for case in cases:
        assert _CASE_ID.fullmatch(case["case_id"])
        _fixture_payload(case["fixture"])
        if case["kind"] == "round_trip":
            assert set(case) == {
                "case_id",
                "kind",
                "fixture",
                "source_id",
                "expected",
            }
            assert set(case["expected"]) == _EVIDENCE_KEYS
        else:
            assert set(case) == {
                "case_id",
                "kind",
                "fixture",
                "mutation_id",
                "source_byte_count",
                "source_sha256",
                "expected_error_code",
            }
            assert case["expected_error_code"] == _FAILURE_CASES[case["case_id"]]
            assert _LOWER_SHA256.fullmatch(case["source_sha256"])


@pytest.mark.parametrize("case_id", _ROUND_TRIP_CASE_IDS)
def test_round_trip_cases_replay_bound_evidence_and_nonpromotion(case_id: str) -> None:
    case = next(row for row in _load_manifest()["cases"] if row["case_id"] == case_id)
    actual, result = _replay(case)
    assert actual == case["expected"]
    artifacts = result.to_dict()
    for artifact in (
        artifacts["source_ingest"],
        artifacts["write_result"],
        artifacts["reparsed_ingest"],
        artifacts["reemitted_write_result"],
        artifacts["report"],
        artifacts,
    ):
        assert all(artifact[field] is False for field in _FALSE_GATES)

    rows = result.source_ingest.sequence_rows
    assert [(row.mon_id, row.coordinate_observed) for row in rows] == [
        ("GLY", True),
        ("ALA", False),
    ]
    assert len(result.source_ingest.system.atoms) == 6
    assert len(result.source_ingest.system.bonds) == 4
    assert result.write_result.payload == result.reemitted_write_result.payload
    assert max(map(len, result.write_result.payload.splitlines())) <= (
        MAX_MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_OUTPUT_LINE_CHARS
    )


@pytest.mark.parametrize("case_id", tuple(_FAILURE_CASES))
def test_failure_cases_replay_exact_typed_codes(case_id: str) -> None:
    case = next(row for row in _load_manifest()["cases"] if row["case_id"] == case_id)
    _path, source = _fixture_payload(case["fixture"])
    mutated = _mutate(source, case["mutation_id"])
    assert len(mutated) == case["source_byte_count"]
    assert hashlib.sha256(mutated).hexdigest() == case["source_sha256"]
    with pytest.raises(MmcifPolymerSequenceNonpolyComponentTopologyError) as exc_info:
        parse_mmcif_polymer_sequence_nonpoly_component_topology(
            mutated, source_id="PRIVATE-AUTH-501"
        )
    assert exc_info.value.code == case["expected_error_code"]
    assert exc_info.value.__cause__ is None
    assert "PRIVATE-AUTH-501" not in str(exc_info.value)


def test_live_input_token_and_source_id_limits_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _path, source = _fixture_payload("mixed_polymer_methane_sequence_complete.cif")
    monkeypatch.setattr(
        composition_module,
        "MAX_MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_INPUT_BYTES",
        len(source) - 1,
    )
    with pytest.raises(MmcifPolymerSequenceNonpolyComponentTopologyError) as exc_info:
        parse_mmcif_polymer_sequence_nonpoly_component_topology(source)
    assert exc_info.value.code == "input_too_large"
    monkeypatch.setattr(
        composition_module,
        "MAX_MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_INPUT_BYTES",
        MAX_MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_INPUT_BYTES,
    )
    monkeypatch.setattr(
        composition_module,
        "MAX_MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_TOKEN_CHARS",
        2,
    )
    with pytest.raises(MmcifPolymerSequenceNonpolyComponentTopologyError) as exc_info:
        parse_mmcif_polymer_sequence_nonpoly_component_topology(source)
    assert exc_info.value.code == "token_too_long"

    with pytest.raises(MmcifPolymerSequenceNonpolyComponentTopologyError) as exc_info:
        parse_mmcif_polymer_sequence_nonpoly_component_topology(
            source,
            source_id="x"
            * (
                MAX_MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_SOURCE_ID_BYTES
                + 1
            ),
        )
    assert exc_info.value.code == "source_id_too_long"


def test_round_trip_artifact_crosswire_and_receipt_tamper_fail_closed() -> None:
    _path, source = _fixture_payload("mixed_polymer_methane_sequence_complete.cif")
    result = round_trip_mmcif_polymer_sequence_nonpoly_component_topology_source(
        source, source_id="artifact_binding_probe"
    )
    original_write = result._write_result
    object.__setattr__(result, "_write_result", result._second)
    with pytest.raises(MmcifPolymerSequenceNonpolyComponentTopologyError) as exc_info:
        result.to_dict()
    assert exc_info.value.code == "crosswired_round_trip_artifacts"

    object.__setattr__(result, "_write_result", original_write)
    receipt = result._write_result._receipt
    object.__setattr__(receipt, "_document_bytes", b"{}")
    with pytest.raises(MmcifPolymerSequenceNonpolyComponentTopologyError) as exc_info:
        receipt.to_dict()
    assert exc_info.value.code == "stale_write_receipt_binding"
