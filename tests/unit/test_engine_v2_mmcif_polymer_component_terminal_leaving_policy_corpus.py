from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from typing import Any

import pytest

from betelgeuze_engine_v2.molecular import (
    mmcif_polymer_component_terminal_leaving_policy as policy,
)
from betelgeuze_engine_v2.molecular.mmcif_polymer_component_topology import (
    MMCIF_POLYMER_COMPONENT_TOPOLOGY_PARSER_PEDIGREE_ID,
    MMCIF_POLYMER_COMPONENT_TOPOLOGY_PROFILE_ID,
    parse_mmcif_polymer_component_topology,
    write_mmcif_polymer_component_topology,
)
from betelgeuze_engine_v2.molecular.serialization import serialize_all_atom_system


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = (
    ROOT
    / "config"
    / "independent_engine_v2_v2_1_mmcif_polymer_component_terminal_leaving_policy_corpus.json"
)
FIXTURE_ROOT = (
    ROOT / "tests" / "fixtures" / "v2_1_mmcif_polymer_component_terminal_leaving_policy"
)
CORPUS_SCHEMA_ID = (
    "betelgeuze.v2_1_mmcif_polymer_component_terminal_leaving_policy_corpus/1.0.0"
)
CORPUS_ID = "v2_1_strict_mmcif_polymer_component_terminal_leaving_policy_v1"
PAYLOAD_HASH_POLICY_ID = "sha256_canonical_json_without_payload_sha256/1.0.0"
EXPECTED_PAYLOAD_SHA256 = (
    "3cfc5731f9943479f7246baf17148ac52a52b3557b35a584a14a6e606a579a3d"
)

_LOWER_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_CASE_ID = re.compile(r"^[a-z][a-z0-9_]*$")
_MAX_MANIFEST_BYTES = 1024 * 1024
_MAX_FIXTURE_BYTES = 32 * 1024
_MAX_TOTAL_FIXTURE_BYTES = 96 * 1024

_POSITIVE_CASE_IDS = (
    "single_xaa",
    "xaa_mid_xaa",
    "multi_asym_category_order",
)
_FAILURE_MUTATIONS = (
    "missing_category",
    "extra_category",
    "header_order",
    "scalar_category",
    "quoted_leaving",
    "lowercase_leaving",
    "missing_backbone",
    "unknown_n_terminal",
    "lowercase_c_terminal",
    "unsupported_component_type",
    "unsupported_element",
    "duplicate_component_atom",
    "noncontiguous_ordinal",
    "sequence_component_join",
    "dangling_component_bond",
    "missing_instance_atom",
    "component_charge_sum",
    "non_ascii_input",
    "input_line_limit",
    "source_id_limit",
)

_POSITIVE_EXPECTED_KEYS = {
    "canonical_output_byte_count",
    "canonical_output_sha256",
    "child_augmented_system_parser_observation_sha256",
    "child_augmented_system_snapshot_sha256",
    "child_augmented_topology_sha256",
    "child_canonical_output_sha256",
    "child_component_projection_sha256",
    "child_parser_pedigree_id",
    "child_preparation_inventory_commitment_sha256",
    "child_profile_id",
    "child_source_binding_sha256",
    "child_stage_proof_sha256",
    "child_topology_state_sha256",
    "component_atom_annotation_count",
    "full_source_sha256",
    "materialized_atom_count",
    "materialized_bond_count",
    "materialized_inter_residue_bond_count",
    "materialized_residue_count",
    "policy_report_sha256",
    "projection_sha256",
    "reparsed_child_stage_proof_sha256",
    "round_trip_preserved",
    "round_trip_report_sha256",
    "second_emission_byte_stable",
    "sequence_boundary_roles",
    "source_binding_sha256",
    "state_sha256",
}


class TerminalLeavingPolicyCorpusError(ValueError):
    pass


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise TerminalLeavingPolicyCorpusError("duplicate JSON key")
        result[key] = value
    return result


def _load_manifest() -> dict[str, Any]:
    payload = MANIFEST.read_bytes()
    if len(payload) > _MAX_MANIFEST_BYTES:
        raise TerminalLeavingPolicyCorpusError("manifest exceeds byte cap")
    try:
        document = json.loads(
            payload.decode("ascii"), object_pairs_hook=_reject_duplicate_keys
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TerminalLeavingPolicyCorpusError(
            "manifest must be strict ASCII JSON"
        ) from exc
    if type(document) is not dict:
        raise TerminalLeavingPolicyCorpusError("manifest root must be an object")
    return document


def _fixture_payload(name: str) -> tuple[Path, bytes]:
    if type(name) is not str:
        raise TerminalLeavingPolicyCorpusError("fixture name must be a string")
    relative = PurePosixPath(name)
    if relative.is_absolute() or len(relative.parts) != 1 or relative.name != name:
        raise TerminalLeavingPolicyCorpusError("fixture path escapes fixed root")
    path = FIXTURE_ROOT / name
    if not path.is_file() or path.is_symlink():
        raise TerminalLeavingPolicyCorpusError("fixture must be a regular fixed file")
    if path.resolve().parent != FIXTURE_ROOT.resolve():
        raise TerminalLeavingPolicyCorpusError("fixture resolves outside fixed root")
    payload = path.read_bytes()
    if len(payload) > _MAX_FIXTURE_BYTES:
        raise TerminalLeavingPolicyCorpusError("fixture exceeds byte cap")
    return path, payload


def _replace_once(source: bytes, old: bytes, new: bytes) -> bytes:
    if not old or source.count(old) != 1:
        raise TerminalLeavingPolicyCorpusError("mutation marker is not unique")
    return source.replace(old, new, 1)


def _mutation(source: bytes, mutation_id: str, source_id: str) -> tuple[bytes, str]:
    entity_loop = b"loop_\n_entity.id\n_entity.type\n1 polymer\n#\n"
    if mutation_id == "missing_category":
        return _replace_once(source, entity_loop, b""), source_id
    if mutation_id == "extra_category":
        extra = b"loop_\n_audit_author.name\nNobody\n#\n"
        return _replace_once(source, entity_loop, entity_loop + extra), source_id
    if mutation_id == "header_order":
        return (
            _replace_once(
                source,
                b"_chem_comp_atom.comp_id\n_chem_comp_atom.atom_id\n",
                b"_chem_comp_atom.atom_id\n_chem_comp_atom.comp_id\n",
            ),
            source_id,
        )
    if mutation_id == "scalar_category":
        return (
            _replace_once(
                source, entity_loop, b"_entity.id 1\n_entity.type polymer\n#\n"
            ),
            source_id,
        )
    atom_q1 = b"XAA Q1 N 0 N Y N Y Y N 1"
    if mutation_id == "quoted_leaving":
        return _replace_once(source, atom_q1, b"XAA Q1 N 0 N 'Y' N Y Y N 1"), source_id
    if mutation_id == "lowercase_leaving":
        return _replace_once(source, atom_q1, b"XAA Q1 N 0 N y N Y Y N 1"), source_id
    if mutation_id == "missing_backbone":
        return _replace_once(source, atom_q1, b"XAA Q1 N 0 N Y N . Y N 1"), source_id
    if mutation_id == "unknown_n_terminal":
        return _replace_once(source, atom_q1, b"XAA Q1 N 0 N Y N Y ? N 1"), source_id
    if mutation_id == "lowercase_c_terminal":
        return (
            _replace_once(
                source,
                b"XAA Q2 C 0 N N N Y N Y 2",
                b"XAA Q2 C 0 N N N Y N y 2",
            ),
            source_id,
        )
    if mutation_id == "unsupported_component_type":
        return (
            _replace_once(
                source,
                b"XAA 'L-peptide linking' 0",
                b"XAA 'D-peptide linking' 0",
            ),
            source_id,
        )
    atom_q3 = b"XAA Q3 O 0 N Y N Y N Y 3"
    if mutation_id == "unsupported_element":
        return _replace_once(source, atom_q3, b"XAA Q3 Xx 0 N Y N Y N Y 3"), source_id
    if mutation_id == "duplicate_component_atom":
        return _replace_once(source, atom_q3, b"XAA Q2 O 0 N Y N Y N Y 3"), source_id
    if mutation_id == "noncontiguous_ordinal":
        return _replace_once(source, atom_q3, b"XAA Q3 O 0 N Y N Y N Y 4"), source_id
    if mutation_id == "sequence_component_join":
        return _replace_once(source, b"1 1 XAA n", b"1 1 XXX n"), source_id
    if mutation_id == "dangling_component_bond":
        return (
            _replace_once(
                source,
                b"XAA Q2 Q3 DOUB N N 2",
                b"XAA Q2 Q9 DOUB N N 2",
            ),
            source_id,
        )
    if mutation_id == "missing_instance_atom":
        row = (
            b"ATOM 3 O Q3 . XAA A 1 1 ? 0.500 90.000 -3.000 "
            b"1.00 10.00 ? 901 AX Z QQ3 1\n"
        )
        return _replace_once(source, row, b""), source_id
    if mutation_id == "component_charge_sum":
        return _replace_once(source, atom_q1, b"XAA Q1 N 1 N Y N Y Y N 1"), source_id
    if mutation_id == "non_ascii_input":
        return source + b"\xff", source_id
    if mutation_id == "input_line_limit":
        return (
            source
            + b"#"
            + b"x"
            * (
                policy.MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_OUTPUT_LINE_CHARS
                + 1
            )
            + b"\n",
            source_id,
        )
    if mutation_id == "source_id_limit":
        return (
            source,
            "x"
            * (
                policy.MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_SOURCE_ID_BYTES
                + 1
            ),
        )
    raise TerminalLeavingPolicyCorpusError("unknown fixed mutation")


def _observed_positive(case: dict[str, Any], source: bytes) -> dict[str, Any]:
    result = policy.round_trip_mmcif_polymer_component_terminal_leaving_policy_source(
        source, source_id=case["source_id"]
    )
    ingest = result._source
    child = ingest.child_ingest
    child_document = child.to_dict()
    ingest_document = ingest.to_dict()
    reparsed_document = result._reparsed.to_dict()
    system = ingest.system
    policy_report = policy.analyze_mmcif_polymer_terminal_leaving_policy(
        ingest
    ).to_dict()
    round_trip_report = result._report.to_dict()
    child_marker = system.provenance.metadata["mmcif_polymer_component_topology"]
    inter_residue_bonds = sum(
        system.atoms[bond.atom_i].residue_index
        != system.atoms[bond.atom_j].residue_index
        for bond in system.bonds
    )
    observed = {
        "full_source_sha256": ingest.full_source_sha256,
        "projection_sha256": ingest.projection_sha256,
        "state_sha256": ingest.state_sha256,
        "source_binding_sha256": ingest.source_binding_sha256,
        "canonical_output_sha256": ingest.canonical_output_sha256,
        "canonical_output_byte_count": len(result._first.payload),
        "policy_report_sha256": policy_report["report_sha256"],
        "round_trip_report_sha256": round_trip_report["report_sha256"],
        "child_stage_proof_sha256": ingest_document["child_stage_proof_sha256"],
        "reparsed_child_stage_proof_sha256": round_trip_report[
            "reparsed_child_stage_proof_sha256"
        ],
        "component_atom_annotation_count": len(ingest.atom_annotations),
        "sequence_boundary_roles": [
            row.position_role for row in ingest.sequence_boundaries
        ],
        "materialized_atom_count": system.atom_count,
        "materialized_bond_count": len(system.bonds),
        "materialized_residue_count": len(system.residues),
        "materialized_inter_residue_bond_count": inter_residue_bonds,
        "child_profile_id": child_document["profile_id"],
        "child_parser_pedigree_id": child_marker["parser_pedigree_id"],
        "child_component_projection_sha256": child.component_projection_sha256,
        "child_topology_state_sha256": child.topology_state_sha256,
        "child_augmented_topology_sha256": child.augmented_topology_sha256,
        "child_source_binding_sha256": child.source_binding_sha256,
        "child_augmented_system_snapshot_sha256": (
            child.augmented_system_snapshot_sha256
        ),
        "child_augmented_system_parser_observation_sha256": child_document[
            "augmented_system_parser_observation_sha256"
        ],
        "child_canonical_output_sha256": hashlib.sha256(
            write_mmcif_polymer_component_topology(child).payload
        ).hexdigest(),
        "child_preparation_inventory_commitment_sha256": child_marker[
            "preparation_inventory_commitment_sha256"
        ],
        "round_trip_preserved": round_trip_report["round_trip_preserved"],
        "second_emission_byte_stable": round_trip_report["second_emission_byte_stable"],
    }

    for stage, stage_document in (
        (ingest, ingest_document),
        (result._reparsed, reparsed_document),
    ):
        binding = policy._source_binding_document(stage._state)
        assert (
            binding["child_stage_proof_sha256"]
            == stage_document["child_stage_proof_sha256"]
        )
        assert binding["child_stage_local_gate_results"] == {
            field: stage_document[field] for field in policy._CHILD_STAGE_GATE_FIELDS
        }
        stage_child = stage.child_ingest
        direct_child = parse_mmcif_polymer_component_topology(
            stage._state.child_source, source_id=case["source_id"]
        )
        assert serialize_all_atom_system(stage.system) == serialize_all_atom_system(
            direct_child.system
        )
        assert (
            stage_child.to_dict()["augmented_system_parser_observation_sha256"]
            == direct_child.to_dict()["augmented_system_parser_observation_sha256"]
        )
        assert (
            stage_child.system.provenance.metadata["mmcif_polymer_component_topology"][
                "preparation_inventory_commitment_sha256"
            ]
            == (
                direct_child.system.provenance.metadata[
                    "mmcif_polymer_component_topology"
                ]["preparation_inventory_commitment_sha256"]
            )
        )
        assert write_mmcif_polymer_component_topology(stage_child).payload == (
            write_mmcif_polymer_component_topology(direct_child).payload
        )
    assert round_trip_report["child_parser_observation_equal"] is False
    assert (
        policy_report["child_stage_proof_sha256"]
        == ingest_document["child_stage_proof_sha256"]
    )
    assert (
        round_trip_report["input_child_stage_proof_sha256"]
        == ingest_document["child_stage_proof_sha256"]
    )
    assert (
        round_trip_report["reparsed_child_stage_proof_sha256"]
        == (reparsed_document["child_stage_proof_sha256"])
    )
    for gate in (
        "input_child_stage_local_independent_projection_validated",
        "reparsed_child_stage_local_independent_projection_validated",
        "input_child_stage_local_system_byte_exact",
        "reparsed_child_stage_local_system_byte_exact",
        "input_child_stage_local_canonical_emission_byte_exact",
        "reparsed_child_stage_local_canonical_emission_byte_exact",
    ):
        assert round_trip_report[gate] is True
    assert round_trip_report["child_stage_proof_equal"] is False
    for document in (ingest_document, policy_report):
        assert all(
            document[field] is True
            for field in _load_manifest()["contracts"]["child_stage_gate_fields"]
        )

    false_fields = _load_manifest()["contracts"]["false_authority_fields"]
    artifacts = result.to_dict()
    public_documents = (
        artifacts,
        artifacts["source_ingest"],
        artifacts["write_result"],
        artifacts["write_result"]["receipt"],
        artifacts["reparsed_ingest"],
        artifacts["reemitted_write_result"],
        artifacts["reemitted_write_result"]["receipt"],
        artifacts["report"],
        policy_report,
    )
    for document in public_documents:
        assert all(document[field] is False for field in false_fields)
    return observed


def test_manifest_identity_contracts_limits_and_payload_hash_are_fixed() -> None:
    manifest = _load_manifest()
    assert set(manifest) == {
        "schema_id",
        "corpus_id",
        "payload_hash_policy_id",
        "payload_sha256",
        "contracts",
        "limits",
        "positive_cases",
        "failure_cases",
    }
    assert manifest["schema_id"] == CORPUS_SCHEMA_ID
    assert manifest["corpus_id"] == CORPUS_ID
    assert manifest["payload_hash_policy_id"] == PAYLOAD_HASH_POLICY_ID
    assert manifest["payload_sha256"] == EXPECTED_PAYLOAD_SHA256
    payload_document = dict(manifest)
    payload_document.pop("payload_sha256")
    assert hashlib.sha256(_canonical_json_bytes(payload_document)).hexdigest() == (
        EXPECTED_PAYLOAD_SHA256
    )

    contracts = manifest["contracts"]
    assert set(contracts) == {
        "profile_id",
        "projection_schema_id",
        "rules_schema_id",
        "rules_sha256",
        "policy_schema_id",
        "state_schema_id",
        "source_binding_schema_id",
        "write_receipt_schema_id",
        "round_trip_report_schema_id",
        "scope",
        "child_profile_id",
        "child_parser_pedigree_id",
        "chem_comp_atom_headers",
        "sequence_boundary_roles",
        "positive_case_count",
        "failure_case_count",
        "stage_local_child_system_and_emission_equality_required",
        "child_stage_proof_sha256_bound",
        "child_stage_gate_fields",
        "cross_stage_child_proof_equality_required",
        "cross_stage_child_source_binding_equality_required",
        "cross_stage_child_snapshot_equality_required",
        "cross_stage_child_parser_observation_equality_required",
        "cross_stage_child_preparation_commitment_equality_required",
        "false_authority_fields",
    }
    assert contracts["profile_id"] == (
        policy.MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_PROFILE_ID
    )
    assert contracts["projection_schema_id"] == (
        policy.MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_PROJECTION_SCHEMA_ID
    )
    assert contracts["rules_schema_id"] == (
        policy.MMCIF_POLYMER_TERMINAL_LEAVING_RULES_SCHEMA_ID
    )
    assert (
        contracts["rules_sha256"] == policy.MMCIF_POLYMER_TERMINAL_LEAVING_RULES_SHA256
    )
    assert contracts["policy_schema_id"] == (
        policy.MMCIF_POLYMER_TERMINAL_LEAVING_POLICY_SCHEMA_ID
    )
    assert contracts["state_schema_id"] == (
        policy.MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_STATE_SCHEMA_ID
    )
    assert contracts["source_binding_schema_id"] == (
        policy.MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_SOURCE_BINDING_SCHEMA_ID
    )
    assert contracts["write_receipt_schema_id"] == (
        policy.MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_WRITE_RECEIPT_SCHEMA_ID
    )
    assert contracts["round_trip_report_schema_id"] == (
        policy.MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_ROUND_TRIP_REPORT_SCHEMA_ID
    )
    assert contracts["scope"] == (
        policy.MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_SCOPE
    )
    assert contracts["child_profile_id"] == MMCIF_POLYMER_COMPONENT_TOPOLOGY_PROFILE_ID
    assert contracts["child_parser_pedigree_id"] == (
        MMCIF_POLYMER_COMPONENT_TOPOLOGY_PARSER_PEDIGREE_ID
    )
    assert contracts["chem_comp_atom_headers"] == list(
        policy.MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_CHEM_COMP_ATOM_HEADERS
    )
    assert contracts["sequence_boundary_roles"] == [
        "singleton",
        "n_sequence_boundary",
        "internal",
        "c_sequence_boundary",
    ]
    assert contracts["false_authority_fields"] == list(policy._FALSE_AUTHORITY_FIELDS)
    assert contracts["positive_case_count"] == 3
    assert contracts["failure_case_count"] == 20
    assert contracts["stage_local_child_system_and_emission_equality_required"] is True
    assert contracts["child_stage_proof_sha256_bound"] is True
    assert contracts["child_stage_gate_fields"] == list(policy._CHILD_STAGE_GATE_FIELDS)
    assert contracts["cross_stage_child_proof_equality_required"] is False
    for name in (
        "cross_stage_child_source_binding_equality_required",
        "cross_stage_child_snapshot_equality_required",
        "cross_stage_child_parser_observation_equality_required",
        "cross_stage_child_preparation_commitment_equality_required",
    ):
        assert contracts[name] is False

    limits = manifest["limits"]
    assert limits == {
        "input_bytes": policy.MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_INPUT_BYTES,
        "output_bytes": policy.MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_OUTPUT_BYTES,
        "projection_bytes": policy.MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_PROJECTION_BYTES,
        "source_id_utf8_bytes": policy.MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_SOURCE_ID_BYTES,
        "token_characters": policy.MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_TOKEN_CHARS,
        "output_line_characters": policy.MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_OUTPUT_LINE_CHARS,
        "sequence_rows": policy.MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_SEQUENCE_ROWS,
        "component_rows": policy.MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_COMPONENT_ROWS,
        "component_atom_rows": policy.MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_COMPONENT_ATOM_ROWS,
        "component_bond_rows": policy.MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_COMPONENT_BOND_ROWS,
        "child_materialized_bonds": policy.MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_CHILD_MATERIALIZED_BONDS,
        "manifest_bytes": _MAX_MANIFEST_BYTES,
        "fixture_bytes": _MAX_FIXTURE_BYTES,
        "total_fixture_bytes": _MAX_TOTAL_FIXTURE_BYTES,
    }


def test_duplicate_json_keys_are_rejected() -> None:
    with pytest.raises(TerminalLeavingPolicyCorpusError, match="duplicate JSON key"):
        json.loads(
            '{"case_id":"a","case_id":"b"}',
            object_pairs_hook=_reject_duplicate_keys,
        )


def test_manifest_cases_and_fixture_payloads_are_closed_and_hashed() -> None:
    manifest = _load_manifest()
    positives = manifest["positive_cases"]
    failures = manifest["failure_cases"]
    assert tuple(case["case_id"] for case in positives) == _POSITIVE_CASE_IDS
    assert tuple(case["mutation_id"] for case in failures) == _FAILURE_MUTATIONS
    all_cases = positives + failures
    case_ids = [case["case_id"] for case in all_cases]
    assert len(case_ids) == len(set(case_ids)) == 23
    assert all(_CASE_ID.fullmatch(case_id) for case_id in case_ids)
    assert all(type(case["source_id"]) is str for case in all_cases)
    assert len(failures) >= 15

    fixture_names = {case["fixture"] for case in positives}
    assert fixture_names == {path.name for path in FIXTURE_ROOT.glob("*.cif")}
    total_bytes = 0
    for case in positives:
        assert set(case) == {
            "case_id",
            "fixture",
            "source_id",
            "fixture_byte_count",
            "fixture_sha256",
            "expected",
        }
        _path, payload = _fixture_payload(case["fixture"])
        total_bytes += len(payload)
        assert len(payload) == case["fixture_byte_count"]
        assert hashlib.sha256(payload).hexdigest() == case["fixture_sha256"]
        assert _LOWER_SHA256.fullmatch(case["fixture_sha256"])
        assert set(case["expected"]) == _POSITIVE_EXPECTED_KEYS
        for name, value in case["expected"].items():
            if name.endswith("_sha256"):
                assert type(value) is str and _LOWER_SHA256.fullmatch(value)
    assert total_bytes <= _MAX_TOTAL_FIXTURE_BYTES

    for case in failures:
        assert set(case) == {
            "case_id",
            "fixture",
            "source_id",
            "mutation_id",
            "expected_error_code",
            "expected_detail_marker",
        }
        assert case["fixture"] == "single_xaa.cif"
        assert case["expected_error_code"]
        assert case["expected_detail_marker"]


@pytest.mark.parametrize("case_id", _POSITIVE_CASE_IDS)
def test_positive_case_replay_is_exact(case_id: str) -> None:
    manifest = _load_manifest()
    case = next(
        case for case in manifest["positive_cases"] if case["case_id"] == case_id
    )
    _path, source = _fixture_payload(case["fixture"])
    assert _observed_positive(case, source) == case["expected"]


@pytest.mark.parametrize("mutation_id", _FAILURE_MUTATIONS)
def test_failure_case_replay_is_typed_and_fail_closed(mutation_id: str) -> None:
    manifest = _load_manifest()
    case = next(
        case for case in manifest["failure_cases"] if case["mutation_id"] == mutation_id
    )
    _path, source = _fixture_payload(case["fixture"])
    mutated, source_id = _mutation(source, mutation_id, case["source_id"])
    with pytest.raises(
        policy.MmcifPolymerComponentTerminalLeavingPolicyError
    ) as captured:
        policy.parse_mmcif_polymer_component_terminal_leaving_policy(
            mutated, source_id=source_id
        )
    assert captured.value.code == case["expected_error_code"]
    assert case["expected_detail_marker"] in captured.value.detail
