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
    CANONICAL_TOPOLOGY_SCHEMA_ID,
    EXACT_H2O_GRAPH_AUDIT_CONSUMER_IDS,
    EXACT_H2O_GRAPH_PREPARATION_SCOPE,
    EXACT_H2O_GRAPH_PROFILE_ID,
    EXACT_H2O_GRAPH_PROFILE_SCHEMA_ID,
    EXACT_H2O_GRAPH_PROFILE_SCHEMA_VERSION,
    EXACT_H2O_GRAPH_PROJECTION_IDENTITY_SEMANTICS,
    EXACT_H2O_GRAPH_PROJECTION_SCHEMA_ID,
    EXACT_H2O_GRAPH_RULE_SET_SCHEMA_ID,
    EXACT_H2O_GRAPH_RULE_SET_SHA256,
    PARSER_OBSERVATION_SCHEMA_ID,
    SDF_V2000_PARSER_VERSION,
    ExactH2OGraphProfileError,
    analyze_exact_h2o_graph_profile,
    parse_sdf_v2000,
    require_exact_h2o_graph_profile,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = (
    REPOSITORY_ROOT
    / "config"
    / "independent_engine_v2_v2_1_exact_h2o_graph_corpus.json"
)
FIXTURE_ROOT = REPOSITORY_ROOT / "tests" / "fixtures" / "v2_1_exact_h2o_graph"
CORPUS_SCHEMA_ID = "betelgeuze.v2_1_exact_h2o_graph_corpus/1.0.0"
CORPUS_ID = "v2_1_source_observed_exact_h2o_graph_profile_corpus_v1"
PAYLOAD_HASH_POLICY_ID = "sha256_canonical_json_without_payload_sha256/1.0.0"
EXPECTED_PAYLOAD_SHA256 = (
    "6eed177ca25e584f3de189d98ea302b8cffc4f99869d61579f724ce38dbf7f09"
)
PARSER_PEDIGREE_ID = "betelgeuze.sdf_v2000_parser/1.5.0"
SOURCE_AUTHENTICATION_STATUS = "digest_bound_not_authenticated"

_LOWERCASE_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_CASE_ID = re.compile(r"^[a-z][a-z0-9_]*$")
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
    "lane",
    "source",
    "source_id",
    "source_sha256",
    "expected",
}
_EXPECTED_KEYS = {
    "canonical_system_snapshot_sha256",
    "canonical_topology_sha256",
    "attached_parser_observation_sha256",
    "graph_projection_sha256",
    "report_sha256",
    "status",
    "failed_constraint_codes",
    "profile_chemistry_supported",
    "profile_graph_preparation_ready",
    "canonical_water_entity_marker_observed",
}
_FALSE_GATES = (
    "source_authenticated",
    "generic_chemistry_supported",
    "generic_molecular_preparation_ready",
    "global_molecular_preparation_ready",
    "water_role_assessed",
    "solvent_role_assessed",
    "hydration_state_assessed",
    "ph_assessed",
    "protonation_correctness_assessed",
    "autoionization_assessed",
    "hydrogen_bonding_assessed",
    "source_bond_order_independently_validated",
    "valence_independently_validated",
    "electronic_structure_assessed",
    "geometry_quality_assessed",
    "bond_lengths_assessed",
    "bond_angle_assessed",
    "conformation_assessed",
    "isotope_speciation_assessed",
    "parameterability_assessed",
    "parameterizable",
    "atom_types_assigned",
    "partial_charges_assigned",
    "force_field_parameters_assigned",
    "water_model_assigned",
    "constraints_assigned",
    "pbc_assessed",
    "periodicity_assessed",
    "physics_supported",
    "runtime_eligible",
    "execution_authorized",
    "energy_evaluation_authorized",
    "force_evaluation_authorized",
    "minimization_authorized",
    "simulation_ready",
    "claim_safe",
)
_POSITIVE_CASE_IDS = {
    "h2o_h_first_reordered_positive",
    "h2o_o_first_bent_positive",
    "h2o_o_first_collinear_positive",
}
_NEGATIVE_REQUIRED_FAILURE = {
    "aromatic_type4_negative": "aromaticity_absent",
    "atom_map_negative": "atom_maps_absent",
    "carbon_substitution_negative": "exact_atom_inventory_o1_h2",
    "charged_negative": "formal_charges_source_observed_known_zero",
    "double_oh_negative": "exact_two_single_oxygen_hydrogen_bonds",
    "h2o2_peroxide_negative": "exact_atom_inventory_o1_h2",
    "h3o_excess_h_negative": "exact_atom_inventory_o1_h2",
    "hh_plus_o_disconnected_negative": "single_component",
    "net_zero_opposite_charges_negative": ("formal_charges_source_observed_known_zero"),
    "oh_missing_h_negative": "exact_atom_inventory_o1_h2",
    "one_oh_isolated_h_negative": "single_component",
}


def _canonical_json_bytes(document: Any) -> bytes:
    return json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _payload_sha256(document: dict[str, Any]) -> str:
    payload = deepcopy(document)
    payload.pop("payload_sha256")
    return hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()


def _load_manifest() -> dict[str, Any]:
    document = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert type(document) is dict
    return document


def _resolve_fixture(source: dict[str, Any]) -> Path:
    assert set(source) == {"kind", "path"}
    assert source["kind"] == "fixture"
    relative = source["path"]
    assert type(relative) is str
    pure = PurePosixPath(relative)
    assert not pure.is_absolute()
    assert ".." not in pure.parts
    assert pure.parts[:3] == ("tests", "fixtures", "v2_1_exact_h2o_graph")
    path = REPOSITORY_ROOT.joinpath(*pure.parts)
    assert path.is_file()
    return path


def _replay_case(case: dict[str, Any]) -> dict[str, Any]:
    path = _resolve_fixture(case["source"])
    source = path.read_bytes()
    assert hashlib.sha256(source).hexdigest() == case["source_sha256"]
    system = parse_sdf_v2000(source, source_id=case["source_id"]).system
    return analyze_exact_h2o_graph_profile(system).to_dict()


def test_manifest_schema_contracts_payload_hash_and_case_inventory_are_exact() -> None:
    document = _load_manifest()
    assert set(document) == _TOP_LEVEL_KEYS
    assert document["schema_id"] == CORPUS_SCHEMA_ID
    assert document["corpus_id"] == CORPUS_ID
    assert document["manifest_payload_hash_policy_id"] == PAYLOAD_HASH_POLICY_ID
    assert document["payload_sha256"] == EXPECTED_PAYLOAD_SHA256
    assert _payload_sha256(document) == EXPECTED_PAYLOAD_SHA256
    contracts = document["contracts"]
    assert contracts == {
        "all_atom_schema_id": ALL_ATOM_SCHEMA_ID,
        "sdf_v2000_parser_version": SDF_V2000_PARSER_VERSION,
        "parser_pedigree_id": PARSER_PEDIGREE_ID,
        "parser_observation_schema_id": PARSER_OBSERVATION_SCHEMA_ID,
        "canonical_topology_schema_id": CANONICAL_TOPOLOGY_SCHEMA_ID,
        "profile_schema_id": EXACT_H2O_GRAPH_PROFILE_SCHEMA_ID,
        "profile_schema_version": EXACT_H2O_GRAPH_PROFILE_SCHEMA_VERSION,
        "profile_id": EXACT_H2O_GRAPH_PROFILE_ID,
        "graph_projection_schema_id": EXACT_H2O_GRAPH_PROJECTION_SCHEMA_ID,
        "graph_projection_identity_semantics": (
            EXACT_H2O_GRAPH_PROJECTION_IDENTITY_SEMANTICS
        ),
        "rule_set_schema_id": EXACT_H2O_GRAPH_RULE_SET_SCHEMA_ID,
        "rule_set_sha256": EXACT_H2O_GRAPH_RULE_SET_SHA256,
        "profile_preparation_scope": EXACT_H2O_GRAPH_PREPARATION_SCOPE,
        "eligible_consumer_ids": list(EXACT_H2O_GRAPH_AUDIT_CONSUMER_IDS),
        "source_authentication_status": SOURCE_AUTHENTICATION_STATUS,
    }
    cases = document["cases"]
    assert type(cases) is list
    assert len(cases) == 14
    case_ids = [case["case_id"] for case in cases]
    assert case_ids == sorted(case_ids)
    assert len(case_ids) == len(set(case_ids))
    assert set(case_ids) == _POSITIVE_CASE_IDS | set(_NEGATIVE_REQUIRED_FAILURE)
    assert sum(case["lane"] == "positive" for case in cases) == 3
    assert sum(case["lane"] == "negative" for case in cases) == 11


def test_manifest_claim_boundary_is_strictly_nonpromoting() -> None:
    boundary = _load_manifest()["claim_boundary"]
    assert boundary["positive_true_fields"] == [
        "profile_chemistry_supported",
        "profile_graph_preparation_ready",
    ]
    assert boundary["positive_canonical_water_entity_marker_observed"] is False
    assert boundary["always_false_fields"] == list(_FALSE_GATES)
    for field in (
        "h2o_graph_is_water_or_solvent_role_evidence",
        "source_ledger_is_independent_chemistry_validation",
        "v2_1_complete",
        "v2_4_solvent_or_pbc_scope_expanded",
    ):
        assert boundary[field] is False


def test_case_shapes_fixture_closure_and_digest_spelling_are_exact() -> None:
    cases = _load_manifest()["cases"]
    referenced: set[Path] = set()
    for case in cases:
        assert set(case) == _CASE_KEYS
        assert type(case["case_id"]) is str and _CASE_ID.fullmatch(case["case_id"])
        assert case["lane"] in {"positive", "negative"}
        assert case["source_id"] == case["case_id"]
        assert type(case["source_sha256"]) is str
        assert _LOWERCASE_SHA256.fullmatch(case["source_sha256"])
        assert set(case["expected"]) == _EXPECTED_KEYS
        for key in (
            "canonical_system_snapshot_sha256",
            "canonical_topology_sha256",
            "attached_parser_observation_sha256",
            "graph_projection_sha256",
            "report_sha256",
        ):
            assert _LOWERCASE_SHA256.fullmatch(case["expected"][key])
        referenced.add(_resolve_fixture(case["source"]).resolve())
    actual = {path.resolve() for path in FIXTURE_ROOT.glob("*.sdf")}
    assert referenced == actual


@pytest.mark.parametrize("case_id", sorted(_POSITIVE_CASE_IDS))
def test_positive_rows_replay_exact_reports_and_keep_all_authority_false(
    case_id: str,
) -> None:
    case = next(row for row in _load_manifest()["cases"] if row["case_id"] == case_id)
    document = _replay_case(case)
    for key, expected in case["expected"].items():
        assert document[key] == expected
    assert document["status"] == "available"
    assert document["failed_constraint_codes"] == []
    assert document["profile_chemistry_supported"] is True
    assert document["profile_graph_preparation_ready"] is True
    assert document["canonical_water_entity_marker_observed"] is False
    for field in _FALSE_GATES:
        assert document[field] is False
    system = parse_sdf_v2000(
        _resolve_fixture(case["source"]).read_bytes(),
        source_id=case["source_id"],
    ).system
    assert (
        require_exact_h2o_graph_profile(
            system,
            consumer_id=EXACT_H2O_GRAPH_AUDIT_CONSUMER_IDS[0],
        ).report_sha256
        == document["report_sha256"]
    )


@pytest.mark.parametrize("case_id", sorted(_NEGATIVE_REQUIRED_FAILURE))
def test_negative_rows_replay_exact_failures_and_typed_require_error(
    case_id: str,
) -> None:
    case = next(row for row in _load_manifest()["cases"] if row["case_id"] == case_id)
    document = _replay_case(case)
    for key, expected in case["expected"].items():
        assert document[key] == expected
    assert document["status"] == "unsupported"
    assert _NEGATIVE_REQUIRED_FAILURE[case_id] in document["failed_constraint_codes"]
    assert document["profile_chemistry_supported"] is False
    assert document["profile_graph_preparation_ready"] is False
    for field in _FALSE_GATES:
        assert document[field] is False
    system = parse_sdf_v2000(
        _resolve_fixture(case["source"]).read_bytes(),
        source_id=case["source_id"],
    ).system
    with pytest.raises(ExactH2OGraphProfileError) as exc_info:
        require_exact_h2o_graph_profile(
            system,
            consumer_id=EXACT_H2O_GRAPH_AUDIT_CONSUMER_IDS[0],
        )
    assert _NEGATIVE_REQUIRED_FAILURE[case_id] in (
        exc_info.value.failed_constraint_codes
    )


def test_coordinate_and_atom_order_positive_boundaries_are_explicit() -> None:
    rows = {case["case_id"]: case for case in _load_manifest()["cases"]}
    bent = rows["h2o_o_first_bent_positive"]["expected"]
    collinear = rows["h2o_o_first_collinear_positive"]["expected"]
    reordered = rows["h2o_h_first_reordered_positive"]["expected"]
    assert bent["graph_projection_sha256"] == collinear["graph_projection_sha256"]
    assert (
        bent["canonical_system_snapshot_sha256"]
        != collinear["canonical_system_snapshot_sha256"]
    )
    assert bent["report_sha256"] != collinear["report_sha256"]
    assert bent["graph_projection_sha256"] != reordered["graph_projection_sha256"]


def test_manifest_expected_report_and_source_tamper_are_detected() -> None:
    document = _load_manifest()
    changed = deepcopy(document)
    changed["cases"][0]["expected"]["report_sha256"] = "0" * 64
    assert _payload_sha256(changed) != EXPECTED_PAYLOAD_SHA256

    case = document["cases"][0]
    source = _resolve_fixture(case["source"]).read_bytes()
    tampered = source.replace(b"betelgeuze-v2", b"betelgeuze-v3", 1)
    assert hashlib.sha256(tampered).hexdigest() != case["source_sha256"]
