from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from typing import Any, Mapping

import pytest

from betelgeuze_engine_v2.contracts import ALL_ATOM_SCHEMA_ID
from betelgeuze_engine_v2.molecular import (
    CANONICAL_TOPOLOGY_SCHEMA_ID,
    CHEMISTRY_COVERAGE_SCHEMA_VERSION,
    CYCLOALKANE_C3_C8_AUDIT_CONSUMER_IDS,
    CYCLOALKANE_C3_C8_CONSTRAINT_CODES,
    CYCLOALKANE_C3_C8_GRAPH_PROJECTION_SCHEMA_ID,
    CYCLOALKANE_C3_C8_PREPARATION_SCOPE,
    CYCLOALKANE_C3_C8_PROFILE_ID,
    CYCLOALKANE_C3_C8_PROFILE_SCHEMA_ID,
    CYCLOALKANE_C3_C8_PROFILE_SCHEMA_VERSION,
    CYCLOALKANE_C3_C8_RULE_SET_SCHEMA_ID,
    CYCLOALKANE_C3_C8_RULE_SET_SHA256,
    PARSER_OBSERVATION_SCHEMA_ID,
    PREPARATION_REPORT_SCHEMA_VERSION,
    SDF_V2000_PARSER_VERSION,
    CycloalkaneC3C8ProfileError,
    analyze_cycloalkane_c3_c8_profile,
    cycloalkane_c3_c8_rule_set_bytes,
    parse_sdf_v2000,
    require_cycloalkane_c3_c8_graph_profile,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = (
    REPOSITORY_ROOT
    / "config"
    / "independent_engine_v2_v2_1_cycloalkane_c3_c8_corpus.json"
)
CORPUS_SCHEMA_ID = "betelgeuze.v2_1_cycloalkane_c3_c8_corpus/1.0.0"
CORPUS_ID = "v2_1_source_observed_cycloalkane_c3_c8_graph_profile_corpus_v1"
PAYLOAD_HASH_POLICY_ID = "sha256_canonical_json_without_payload_sha256/1.0.0"
EXPECTED_PAYLOAD_SHA256 = (
    "819f0721c6304d1b86520cb173376443bf191a7f12fd8272ff7070d5d64c5f33"
)
PARSER_PEDIGREE_ID = "betelgeuze.sdf_v2000_parser/1.5.0"
SOURCE_AUTHENTICATION_STATUS = "digest_bound_not_authenticated"
GRAPH_PROJECTION_IDENTITY_SEMANTICS = (
    "source_indexed_exact_projection_not_order_independent_graph_isomorphism_identity"
)

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
_CONTRACT_KEYS = {
    "all_atom_schema_id",
    "sdf_v2000_parser_version",
    "parser_pedigree_id",
    "parser_observation_schema_id",
    "canonical_topology_schema_id",
    "chemistry_report_schema_version",
    "preparation_report_schema_version",
    "profile_schema_id",
    "profile_schema_version",
    "profile_id",
    "graph_projection_schema_id",
    "rule_set_schema_id",
    "rule_set_sha256",
    "profile_preparation_scope",
    "eligible_consumer_ids",
    "source_authentication_status",
}
_CASE_KEYS = {
    "case_id",
    "lane",
    "source",
    "source_id",
    "source_sha256",
    "system_mutation",
    "expected",
}
_REPORT_FIELD_KEYS = (
    "canonical_system_snapshot_sha256",
    "canonical_topology_schema_id",
    "canonical_topology_sha256",
    "chemistry_report_schema_version",
    "chemistry_report_sha256",
    "preparation_report_schema_version",
    "preparation_report_sha256",
    "source_format",
    "source_sha256",
    "source_digest_available",
    "parser_pedigree_id",
    "parser_observation_self_consistent",
    "parser_observation_schema_id",
    "attached_parser_observation_sha256",
    "recomputed_parser_observation_sha256",
    "parser_observation_sha256_equal",
    "source_authentication_status",
    "source_authenticated",
    "graph_projection_schema_id",
    "graph_projection_identity_semantics",
    "graph_projection_sha256",
    "report_sha256",
    "status",
    "failed_constraint_codes",
    "carbon_atom_count",
    "hydrogen_atom_count",
    "molecular_formula",
    "molecule_label",
    "profile_chemistry_supported",
    "profile_graph_preparation_ready",
)
_EXPECTED_KEYS = {*_REPORT_FIELD_KEYS, "gates"}
_GATE_KEYS = {
    "global_molecular_preparation_ready",
    "parameterability_assessed",
    "parameterizable",
    "physics_supported",
    "runtime_eligible",
    "execution_authorized",
    "energy_evaluation_authorized",
    "force_evaluation_authorized",
    "minimization_authorized",
    "simulation_ready",
    "claim_safe",
}
_FALSE_GATES = {key: False for key in _GATE_KEYS}

_POSITIVE_EXPECTATIONS = {
    "cyclopropane_c3_positive": (3, "cyclopropane"),
    "cyclobutane_c4_positive": (4, "cyclobutane"),
    "cyclopentane_c5_positive": (5, "cyclopentane"),
    "cyclohexane_c6_positive": (6, "cyclohexane"),
    "cycloheptane_c7_positive": (7, "cycloheptane"),
    "cyclooctane_c8_positive": (8, "cyclooctane"),
}
_NEGATIVE_REQUIRED_FAILURE = {
    "c2_lower_bound_negative": "carbon_count_c3_c8",
    "c9_upper_bound_negative": "carbon_count_c3_c8",
    "c4_branched_same_formula_negative": ("carbon_subgraph_connected_simple_cycle"),
    "c5_spiro_bicyclic_negative": "carbon_subgraph_connected_simple_cycle",
    "c4_fused_shared_edge_bicyclic_negative": (
        "carbon_subgraph_connected_simple_cycle"
    ),
    "c4_unsaturated_negative": "single_bonds_only",
    "c4_missing_h_negative": "exact_cycloalkane_formula_c_n_h_2n",
    "c4_excess_h_negative": "exact_cycloalkane_formula_c_n_h_2n",
    "c4_hetero_o_negative": "elements_h_c_only",
    "c4_charged_negative": "formal_charges_source_observed_known_zero",
    "c4_disconnected_negative": "single_component",
    "c4_isotope_negative": "isotopes_absent",
}
_EXPECTED_CASE_IDS = (
    *_POSITIVE_EXPECTATIONS,
    *_NEGATIVE_REQUIRED_FAILURE,
)
_POSITIVE_CASE_IDS = frozenset(_POSITIVE_EXPECTATIONS)


def _fixture_source(filename: str) -> dict[str, Any]:
    return {
        "kind": "fixture",
        "path": f"tests/fixtures/v2_1_cycloalkane_c3_c8/{filename}",
    }


_C4_SOURCE_SHA256 = "9fa1285a2774181a700c95743e3c32f68adfa2f97a0cc880712c759a2a0b1068"
_ISOTOPE_MUTATION = {
    "kind": "insert_ascii_before_first_m_end",
    "ascii": "M  ISO  1   1  13\n",
}
_EXPECTED_SOURCE_SPECS = {
    "cyclopropane_c3_positive": _fixture_source("cyclopropane_c3_explicit_h.sdf"),
    "cyclobutane_c4_positive": _fixture_source("cyclobutane_c4_explicit_h.sdf"),
    "cyclopentane_c5_positive": _fixture_source("cyclopentane_c5_explicit_h.sdf"),
    "cyclohexane_c6_positive": _fixture_source("cyclohexane_c6_explicit_h.sdf"),
    "cycloheptane_c7_positive": _fixture_source("cycloheptane_c7_explicit_h.sdf"),
    "cyclooctane_c8_positive": _fixture_source("cyclooctane_c8_explicit_h.sdf"),
    "c2_lower_bound_negative": _fixture_source("c2_lower_bound_negative.sdf"),
    "c9_upper_bound_negative": _fixture_source("c9_upper_bound_negative.sdf"),
    "c4_branched_same_formula_negative": _fixture_source(
        "c4_branched_same_formula_negative.sdf"
    ),
    "c5_spiro_bicyclic_negative": _fixture_source("c5_spiro_bicyclic_negative.sdf"),
    "c4_fused_shared_edge_bicyclic_negative": _fixture_source(
        "c4_fused_shared_edge_bicyclic_negative.sdf"
    ),
    "c4_unsaturated_negative": _fixture_source("c4_unsaturated_negative.sdf"),
    "c4_missing_h_negative": _fixture_source("c4_missing_h_negative.sdf"),
    "c4_excess_h_negative": _fixture_source("c4_excess_h_negative.sdf"),
    "c4_hetero_o_negative": _fixture_source("c4_hetero_o_negative.sdf"),
    "c4_charged_negative": _fixture_source("c4_charged_negative.sdf"),
    "c4_disconnected_negative": _fixture_source("c4_disconnected_negative.sdf"),
    "c4_isotope_negative": {
        "kind": "derived_fixture",
        "path": ("tests/fixtures/v2_1_cycloalkane_c3_c8/cyclobutane_c4_explicit_h.sdf"),
        "base_source_sha256": _C4_SOURCE_SHA256,
        "mutation": _ISOTOPE_MUTATION,
    },
}


class CycloalkaneCorpusManifestError(ValueError):
    """Raised when the frozen graph-profile corpus is inconsistent."""


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise CycloalkaneCorpusManifestError(f"duplicate JSON object key {key!r}")
        output[key] = value
    return output


def _reject_nonstandard_constant(token: str) -> None:
    raise CycloalkaneCorpusManifestError(f"nonstandard JSON constant {token!r}")


def _expect_mapping(value: Any, context: str) -> dict[str, Any]:
    if type(value) is not dict:
        raise CycloalkaneCorpusManifestError(f"{context} must be an object")
    return value


def _expect_exact_keys(
    value: Mapping[str, Any],
    expected: set[str],
    context: str,
) -> None:
    observed = set(value)
    if observed != expected:
        missing = sorted(expected - observed)
        extra = sorted(observed - expected)
        raise CycloalkaneCorpusManifestError(
            f"{context} keys mismatch; missing={missing}; extra={extra}"
        )


def _canonical_json_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise CycloalkaneCorpusManifestError(
            f"manifest cannot be canonically encoded: {exc}"
        ) from exc


def _manifest_payload_sha256(document: Mapping[str, Any]) -> str:
    payload = dict(document)
    payload.pop("payload_sha256", None)
    return hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()


def _refresh_payload_sha256(document: dict[str, Any]) -> None:
    document["payload_sha256"] = _manifest_payload_sha256(document)


def _load_strict_json(data: bytes) -> dict[str, Any]:
    if type(data) is not bytes:
        raise TypeError("manifest data must be exact bytes")
    try:
        text = data.decode("utf-8", errors="strict")
        value = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_nonstandard_constant,
        )
    except CycloalkaneCorpusManifestError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CycloalkaneCorpusManifestError(
            "manifest must be strict UTF-8 JSON"
        ) from exc
    return _expect_mapping(value, "manifest")


def _require_sha256(value: Any, context: str) -> str:
    if type(value) is not str or _LOWERCASE_SHA256.fullmatch(value) is None:
        raise CycloalkaneCorpusManifestError(f"{context} must be a lowercase SHA-256")
    return value


def _require_nonnegative_integer(value: Any, context: str) -> int:
    if type(value) is not int or value < 0:
        raise CycloalkaneCorpusManifestError(
            f"{context} must be a non-negative integer"
        )
    return value


def _expected_contracts() -> dict[str, Any]:
    return {
        "all_atom_schema_id": ALL_ATOM_SCHEMA_ID,
        "sdf_v2000_parser_version": SDF_V2000_PARSER_VERSION,
        "parser_pedigree_id": PARSER_PEDIGREE_ID,
        "parser_observation_schema_id": PARSER_OBSERVATION_SCHEMA_ID,
        "canonical_topology_schema_id": CANONICAL_TOPOLOGY_SCHEMA_ID,
        "chemistry_report_schema_version": CHEMISTRY_COVERAGE_SCHEMA_VERSION,
        "preparation_report_schema_version": PREPARATION_REPORT_SCHEMA_VERSION,
        "profile_schema_id": CYCLOALKANE_C3_C8_PROFILE_SCHEMA_ID,
        "profile_schema_version": CYCLOALKANE_C3_C8_PROFILE_SCHEMA_VERSION,
        "profile_id": CYCLOALKANE_C3_C8_PROFILE_ID,
        "graph_projection_schema_id": (CYCLOALKANE_C3_C8_GRAPH_PROJECTION_SCHEMA_ID),
        "rule_set_schema_id": CYCLOALKANE_C3_C8_RULE_SET_SCHEMA_ID,
        "rule_set_sha256": CYCLOALKANE_C3_C8_RULE_SET_SHA256,
        "profile_preparation_scope": CYCLOALKANE_C3_C8_PREPARATION_SCOPE,
        "eligible_consumer_ids": list(CYCLOALKANE_C3_C8_AUDIT_CONSUMER_IDS),
        "source_authentication_status": SOURCE_AUTHENTICATION_STATUS,
    }


def _fixture_path(relative_path: Any) -> Path:
    if type(relative_path) is not str:
        raise CycloalkaneCorpusManifestError("source path must be a string")
    pure = PurePosixPath(relative_path)
    expected_prefix = (
        "tests",
        "fixtures",
        "v2_1_cycloalkane_c3_c8",
    )
    if (
        pure.is_absolute()
        or ".." in pure.parts
        or pure.suffix != ".sdf"
        or len(pure.parts) != 4
        or pure.parts[:3] != expected_prefix
    ):
        raise CycloalkaneCorpusManifestError(
            "source path must be a repository-relative corpus SDF fixture"
        )
    path = (REPOSITORY_ROOT / Path(*pure.parts)).resolve()
    fixture_root = (
        REPOSITORY_ROOT / "tests" / "fixtures" / "v2_1_cycloalkane_c3_c8"
    ).resolve()
    if not path.is_relative_to(fixture_root) or not path.is_file():
        raise CycloalkaneCorpusManifestError(
            "source fixture must resolve under the cycloalkane corpus"
        )
    return path


def _materialize_source(case: Mapping[str, Any]) -> bytes:
    case_id = case["case_id"]
    source = _expect_mapping(case["source"], f"{case_id}.source")
    expected_source = _EXPECTED_SOURCE_SPECS.get(case_id)
    if source != expected_source:
        raise CycloalkaneCorpusManifestError(
            f"{case_id}.source does not match the frozen source policy"
        )
    source_bytes = _fixture_path(source["path"]).read_bytes()
    if source["kind"] == "derived_fixture":
        observed_base_sha256 = hashlib.sha256(source_bytes).hexdigest()
        if observed_base_sha256 != source["base_source_sha256"]:
            raise CycloalkaneCorpusManifestError(
                f"{case_id} base source SHA-256 mismatch"
            )
        marker = b"M  END\n"
        if source_bytes.count(marker) != 1:
            raise CycloalkaneCorpusManifestError(
                f"{case_id} requires exactly one M  END marker"
            )
        try:
            insertion = source["mutation"]["ascii"].encode(
                "ascii",
                errors="strict",
            )
        except UnicodeEncodeError as exc:
            raise CycloalkaneCorpusManifestError(
                f"{case_id} mutation must be ASCII"
            ) from exc
        source_bytes = source_bytes.replace(
            marker,
            insertion + marker,
            1,
        )
    observed_sha256 = hashlib.sha256(source_bytes).hexdigest()
    if observed_sha256 != case["source_sha256"]:
        raise CycloalkaneCorpusManifestError(
            f"{case_id} materialized source SHA-256 mismatch"
        )
    return source_bytes


def _validate_expected(case: Mapping[str, Any]) -> None:
    case_id = case["case_id"]
    expected = _expect_mapping(case["expected"], f"{case_id}.expected")
    _expect_exact_keys(expected, _EXPECTED_KEYS, f"{case_id}.expected")
    for digest_name in (
        "canonical_system_snapshot_sha256",
        "canonical_topology_sha256",
        "chemistry_report_sha256",
        "preparation_report_sha256",
        "attached_parser_observation_sha256",
        "recomputed_parser_observation_sha256",
        "graph_projection_sha256",
        "report_sha256",
    ):
        _require_sha256(expected[digest_name], f"{case_id}.{digest_name}")
    for count_name in ("carbon_atom_count", "hydrogen_atom_count"):
        _require_nonnegative_integer(
            expected[count_name],
            f"{case_id}.{count_name}",
        )
    failures = expected["failed_constraint_codes"]
    if (
        type(failures) is not list
        or any(type(code) is not str or not code for code in failures)
        or len(failures) != len(set(failures))
        or any(code not in CYCLOALKANE_C3_C8_CONSTRAINT_CODES for code in failures)
    ):
        raise CycloalkaneCorpusManifestError(
            f"{case_id} failed constraint codes are invalid"
        )
    gates = _expect_mapping(expected["gates"], f"{case_id}.gates")
    _expect_exact_keys(gates, _GATE_KEYS, f"{case_id}.gates")
    if gates != _FALSE_GATES:
        raise CycloalkaneCorpusManifestError(
            f"{case_id} cannot promote any global or authority gate"
        )
    if expected["canonical_topology_schema_id"] != CANONICAL_TOPOLOGY_SCHEMA_ID:
        raise CycloalkaneCorpusManifestError(
            f"{case_id} topology schema binding mismatch"
        )
    if (
        expected["chemistry_report_schema_version"] != CHEMISTRY_COVERAGE_SCHEMA_VERSION
        or expected["preparation_report_schema_version"]
        != PREPARATION_REPORT_SCHEMA_VERSION
    ):
        raise CycloalkaneCorpusManifestError(
            f"{case_id} upstream report schema binding mismatch"
        )
    if (
        expected["source_format"] != "sdf_v2000"
        or expected["source_sha256"] != case["source_sha256"]
        or expected["source_digest_available"] is not True
        or expected["parser_pedigree_id"] != PARSER_PEDIGREE_ID
        or expected["parser_observation_self_consistent"] is not True
        or expected["parser_observation_schema_id"] != PARSER_OBSERVATION_SCHEMA_ID
        or expected["attached_parser_observation_sha256"]
        != expected["recomputed_parser_observation_sha256"]
        or expected["parser_observation_sha256_equal"] is not True
    ):
        raise CycloalkaneCorpusManifestError(
            f"{case_id} source or parser binding mismatch"
        )
    if (
        expected["source_authentication_status"] != SOURCE_AUTHENTICATION_STATUS
        or expected["source_authenticated"] is not False
    ):
        raise CycloalkaneCorpusManifestError(
            f"{case_id} source authentication boundary mismatch"
        )
    if (
        expected["graph_projection_schema_id"]
        != CYCLOALKANE_C3_C8_GRAPH_PROJECTION_SCHEMA_ID
        or expected["graph_projection_identity_semantics"]
        != GRAPH_PROJECTION_IDENTITY_SEMANTICS
    ):
        raise CycloalkaneCorpusManifestError(
            f"{case_id} graph projection binding mismatch"
        )
    if (
        type(expected["molecular_formula"]) is not str
        or not expected["molecular_formula"]
    ):
        raise CycloalkaneCorpusManifestError(
            f"{case_id} molecular formula must be non-empty"
        )

    positive = case["lane"] == "positive"
    if positive:
        carbon_count, molecule_label = _POSITIVE_EXPECTATIONS[case_id]
        if (
            expected["status"] != "available"
            or failures
            or expected["profile_chemistry_supported"] is not True
            or expected["profile_graph_preparation_ready"] is not True
            or expected["carbon_atom_count"] != carbon_count
            or expected["hydrogen_atom_count"] != 2 * carbon_count
            or expected["molecular_formula"] != f"C{carbon_count}H{2 * carbon_count}"
            or expected["molecule_label"] != molecule_label
        ):
            raise CycloalkaneCorpusManifestError(
                f"{case_id} positive profile expectations are inconsistent"
            )
    else:
        required_failure = _NEGATIVE_REQUIRED_FAILURE[case_id]
        if (
            expected["status"] != "unsupported"
            or not failures
            or required_failure not in failures
            or expected["profile_chemistry_supported"] is not False
            or expected["profile_graph_preparation_ready"] is not False
            or expected["molecule_label"] is not None
        ):
            raise CycloalkaneCorpusManifestError(
                f"{case_id} negative profile expectations are inconsistent"
            )


def _runtime_expected(case: Mapping[str, Any]) -> dict[str, Any]:
    source = _materialize_source(case)
    system = parse_sdf_v2000(source, source_id=case["source_id"]).system
    report = analyze_cycloalkane_c3_c8_profile(system)
    document = report.to_dict()
    observed = {key: document[key] for key in _REPORT_FIELD_KEYS}
    observed["gates"] = {key: document[key] for key in _GATE_KEYS}
    return observed


def _validate_case_runtime(case: Mapping[str, Any]) -> None:
    observed = _runtime_expected(case)
    if observed != case["expected"]:
        mismatches = tuple(
            key
            for key in sorted(_EXPECTED_KEYS)
            if observed.get(key) != case["expected"].get(key)
        )
        raise CycloalkaneCorpusManifestError(
            f"{case['case_id']} runtime replay mismatch: {mismatches}"
        )


def _validate_manifest(
    document: dict[str, Any],
    *,
    replay_cases: bool = False,
) -> None:
    _expect_exact_keys(document, _TOP_LEVEL_KEYS, "manifest")
    if document["schema_id"] != CORPUS_SCHEMA_ID:
        raise CycloalkaneCorpusManifestError("manifest schema_id mismatch")
    if document["corpus_id"] != CORPUS_ID:
        raise CycloalkaneCorpusManifestError("manifest corpus_id mismatch")
    if document["manifest_payload_hash_policy_id"] != PAYLOAD_HASH_POLICY_ID:
        raise CycloalkaneCorpusManifestError("manifest payload hash policy mismatch")
    declared_payload_sha256 = _require_sha256(
        document["payload_sha256"],
        "payload_sha256",
    )
    if declared_payload_sha256 != _manifest_payload_sha256(document):
        raise CycloalkaneCorpusManifestError("manifest payload SHA-256 mismatch")
    contracts = _expect_mapping(document["contracts"], "contracts")
    _expect_exact_keys(contracts, _CONTRACT_KEYS, "contracts")
    if contracts != _expected_contracts():
        raise CycloalkaneCorpusManifestError(
            "manifest contract pins do not match runtime contracts"
        )
    if tuple(contracts["eligible_consumer_ids"]) != (
        CYCLOALKANE_C3_C8_AUDIT_CONSUMER_IDS
    ):
        raise CycloalkaneCorpusManifestError(
            "manifest must declare the sole audit consumer"
        )
    claim_boundary = _expect_mapping(
        document["claim_boundary"],
        "claim_boundary",
    )
    _expect_exact_keys(claim_boundary, _GATE_KEYS, "claim_boundary")
    if claim_boundary != _FALSE_GATES:
        raise CycloalkaneCorpusManifestError(
            "claim boundary cannot promote global or authority gates"
        )
    cases = document["cases"]
    if type(cases) is not list:
        raise CycloalkaneCorpusManifestError("cases must be a list")
    observed_ids: list[str] = []
    for index, value in enumerate(cases):
        case = _expect_mapping(value, f"cases[{index}]")
        _expect_exact_keys(case, _CASE_KEYS, f"cases[{index}]")
        case_id = case["case_id"]
        if type(case_id) is not str or _CASE_ID.fullmatch(case_id) is None:
            raise CycloalkaneCorpusManifestError("case_id is invalid")
        observed_ids.append(case_id)
        expected_lane = "positive" if case_id in _POSITIVE_CASE_IDS else "negative"
        if case["lane"] != expected_lane:
            raise CycloalkaneCorpusManifestError(
                f"{case_id} lane does not match the frozen corpus"
            )
        if case["source_id"] != case_id:
            raise CycloalkaneCorpusManifestError(
                f"{case_id} source_id must equal case_id"
            )
        if case["system_mutation"] is not None:
            raise CycloalkaneCorpusManifestError(
                f"{case_id} cannot apply a hidden canonical-system mutation"
            )
        _require_sha256(case["source_sha256"], f"{case_id}.source_sha256")
        _materialize_source(case)
        _validate_expected(case)
        if replay_cases:
            _validate_case_runtime(case)
    if tuple(observed_ids) != _EXPECTED_CASE_IDS:
        raise CycloalkaneCorpusManifestError(
            "case IDs must be unique and match the frozen ordered corpus"
        )


def _manifest_document() -> dict[str, Any]:
    return _load_strict_json(MANIFEST_PATH.read_bytes())


def test_manifest_is_strict_self_hashed_and_replays_every_case_exactly() -> None:
    document = _manifest_document()

    _validate_manifest(document, replay_cases=True)

    assert document["payload_sha256"] == EXPECTED_PAYLOAD_SHA256
    assert tuple(case["case_id"] for case in document["cases"]) == (_EXPECTED_CASE_IDS)
    assert len(_POSITIVE_CASE_IDS) == 6
    assert len(CYCLOALKANE_C3_C8_AUDIT_CONSUMER_IDS) == 1
    assert hashlib.sha256(cycloalkane_c3_c8_rule_set_bytes()).hexdigest() == (
        CYCLOALKANE_C3_C8_RULE_SET_SHA256
    )


def test_duplicate_keys_and_nonstandard_json_constants_fail_closed() -> None:
    source = MANIFEST_PATH.read_bytes()
    duplicate = source.replace(
        b'  "corpus_id":',
        b'  "corpus_id": "duplicate",\n  "corpus_id":',
        1,
    )
    nonstandard = source.replace(
        b'"carbon_atom_count": 3',
        b'"carbon_atom_count": NaN',
        1,
    )

    with pytest.raises(CycloalkaneCorpusManifestError, match="duplicate"):
        _load_strict_json(duplicate)
    with pytest.raises(CycloalkaneCorpusManifestError, match="nonstandard"):
        _load_strict_json(nonstandard)


def test_stale_payload_hash_and_unknown_nested_keys_fail_closed() -> None:
    stale = deepcopy(_manifest_document())
    stale["cases"][0]["expected"]["status"] = "unsupported"
    with pytest.raises(
        CycloalkaneCorpusManifestError,
        match="payload SHA-256",
    ):
        _validate_manifest(stale)

    unknown = deepcopy(_manifest_document())
    unknown["cases"][0]["expected"]["unreviewed_authority"] = True
    _refresh_payload_sha256(unknown)
    with pytest.raises(
        CycloalkaneCorpusManifestError,
        match="keys mismatch",
    ):
        _validate_manifest(unknown)


def test_source_hash_path_and_isotope_mutation_tamper_fail_closed() -> None:
    wrong_hash = deepcopy(_manifest_document())
    wrong_hash["cases"][1]["source_sha256"] = "0" * 64
    _refresh_payload_sha256(wrong_hash)
    with pytest.raises(
        CycloalkaneCorpusManifestError,
        match="source SHA-256",
    ):
        _validate_manifest(wrong_hash)

    wrong_path = deepcopy(_manifest_document())
    wrong_path["cases"][1]["source"]["path"] = "../../outside.sdf"
    _refresh_payload_sha256(wrong_path)
    with pytest.raises(
        CycloalkaneCorpusManifestError,
        match="source policy",
    ):
        _validate_manifest(wrong_path)

    wrong_mutation = deepcopy(_manifest_document())
    wrong_mutation["cases"][-1]["source"]["mutation"]["ascii"] = "M  ISO  1   1  12\n"
    _refresh_payload_sha256(wrong_mutation)
    with pytest.raises(
        CycloalkaneCorpusManifestError,
        match="source policy",
    ):
        _validate_manifest(wrong_mutation)


@pytest.mark.parametrize(
    "field",
    (
        "report_sha256",
        "graph_projection_sha256",
        "canonical_topology_sha256",
    ),
)
def test_report_projection_and_topology_tamper_fail_runtime_replay(
    field: str,
) -> None:
    tampered = deepcopy(_manifest_document())
    tampered["cases"][3]["expected"][field] = "f" * 64
    _refresh_payload_sha256(tampered)

    with pytest.raises(
        CycloalkaneCorpusManifestError,
        match="runtime replay",
    ):
        _validate_manifest(tampered, replay_cases=True)


def test_parser_binding_and_global_gate_promotion_fail_closed() -> None:
    parser = deepcopy(_manifest_document())
    parser["cases"][0]["expected"]["recomputed_parser_observation_sha256"] = "e" * 64
    _refresh_payload_sha256(parser)
    with pytest.raises(
        CycloalkaneCorpusManifestError,
        match="source or parser binding",
    ):
        _validate_manifest(parser)

    gate = deepcopy(_manifest_document())
    gate["cases"][0]["expected"]["gates"]["claim_safe"] = True
    _refresh_payload_sha256(gate)
    with pytest.raises(
        CycloalkaneCorpusManifestError,
        match="cannot promote",
    ):
        _validate_manifest(gate)


def test_positive_require_gate_and_negative_typed_errors_match_manifest() -> None:
    document = _manifest_document()
    _validate_manifest(document)

    for case in document["cases"]:
        system = parse_sdf_v2000(
            _materialize_source(case),
            source_id=case["source_id"],
        ).system
        if case["lane"] == "positive":
            report = require_cycloalkane_c3_c8_graph_profile(
                system,
                consumer_id=CYCLOALKANE_C3_C8_AUDIT_CONSUMER_IDS[0],
            )
            assert (
                report.to_dict()["report_sha256"] == (case["expected"]["report_sha256"])
            )
            assert report.profile_chemistry_supported is True
            assert report.profile_graph_preparation_ready is True
        else:
            with pytest.raises(CycloalkaneC3C8ProfileError) as exc_info:
                require_cycloalkane_c3_c8_graph_profile(
                    system,
                    consumer_id=CYCLOALKANE_C3_C8_AUDIT_CONSUMER_IDS[0],
                )
            assert (
                exc_info.value.report.to_dict()["report_sha256"]
                == (case["expected"]["report_sha256"])
            )
            assert exc_info.value.report.profile_chemistry_supported is False
            assert exc_info.value.report.profile_graph_preparation_ready is False


def test_existing_acyclic_and_linear_cyclobutane_rows_remain_negative() -> None:
    ingest_manifest = json.loads(
        (
            REPOSITORY_ROOT / "config" / "independent_engine_v2_v2_1_ingest_corpus.json"
        ).read_text(encoding="utf-8")
    )
    ingest_row = next(
        case
        for case in ingest_manifest["cases"]
        if case["case_id"] == "sdf_v2000_cyclobutane_explicit_h"
    )
    assert ingest_row["expected"]["canonical_ingest_supported"] is False
    assert ingest_row["expected"]["applicability_failed_constraint_codes"] == [
        "acyclic_graph"
    ]

    linear_manifest = json.loads(
        (
            REPOSITORY_ROOT
            / "config"
            / "independent_engine_v2_v2_2_linear_alkane_corpus.json"
        ).read_text(encoding="utf-8")
    )
    linear_row = next(
        case
        for case in linear_manifest["cases"]
        if case["case_id"] == "cyclobutane_cycle_negative"
    )
    assert linear_row["expected"]["applicability_status"] == "unsupported"
    assert linear_row["expected"]["topological_environment_coverage_complete"] is False
    assert (
        linear_row["expected"]["topological_term_and_pair_classification_complete"]
        is False
    )
