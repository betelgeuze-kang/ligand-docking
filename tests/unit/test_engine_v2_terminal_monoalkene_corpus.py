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
    PARSER_OBSERVATION_SCHEMA_ID,
    PREPARATION_REPORT_SCHEMA_VERSION,
    SDF_V2000_PARSER_VERSION,
    TERMINAL_MONOALKENE_C2_C8_AUDIT_CONSUMER_IDS,
    TERMINAL_MONOALKENE_C2_C8_CONSTRAINT_CODES,
    TERMINAL_MONOALKENE_C2_C8_GRAPH_PROJECTION_IDENTITY_SEMANTICS,
    TERMINAL_MONOALKENE_C2_C8_GRAPH_PROJECTION_SCHEMA_ID,
    TERMINAL_MONOALKENE_C2_C8_PREPARATION_SCOPE,
    TERMINAL_MONOALKENE_C2_C8_PROFILE_ID,
    TERMINAL_MONOALKENE_C2_C8_PROFILE_SCHEMA_ID,
    TERMINAL_MONOALKENE_C2_C8_PROFILE_SCHEMA_VERSION,
    TERMINAL_MONOALKENE_C2_C8_RULE_SET_SCHEMA_ID,
    TERMINAL_MONOALKENE_C2_C8_RULE_SET_SHA256,
    TerminalMonoalkeneC2C8ConsumerError,
    TerminalMonoalkeneC2C8ProfileError,
    analyze_terminal_monoalkene_c2_c8_profile,
    parse_sdf_v2000,
    require_terminal_monoalkene_c2_c8_graph_profile,
    terminal_monoalkene_c2_c8_rule_set_bytes,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = (
    REPOSITORY_ROOT
    / "config"
    / "independent_engine_v2_v2_1_terminal_monoalkene_c2_c8_corpus.json"
)
CORPUS_SCHEMA_ID = "betelgeuze.v2_1_terminal_monoalkene_c2_c8_corpus/1.0.0"
CORPUS_ID = "v2_1_source_observed_terminal_monoalkene_c2_c8_graph_profile_corpus_v1"
PAYLOAD_HASH_POLICY_ID = "sha256_canonical_json_without_payload_sha256/1.0.0"
EXPECTED_PAYLOAD_SHA256 = (
    "5151921d25fca62a03a7691172a8608bdaa87c3d8e761e3895ee85ed7c46393e"
)
PARSER_PEDIGREE_ID = "betelgeuze.sdf_v2000_parser/1.5.0"
SOURCE_AUTHENTICATION_STATUS = "digest_bound_not_authenticated"
UNBRANCHED_PATH_DEFINITION = "unbranched_carbon_simple_path_not_coordinate_geometry"
BOND_ORDER_VALENCE_LEDGER_SEMANTICS = (
    "source_sdf_annotation_ledger_not_independent_bond_order_valence_"
    "unsaturation_or_electronic_structure_validation"
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
    "graph_projection_identity_semantics",
    "rule_set_schema_id",
    "rule_set_sha256",
    "profile_preparation_scope",
    "unbranched_path_definition",
    "bond_order_valence_ledger_semantics",
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
    "unbranched_path_definition",
    "bond_order_valence_ledger_semantics",
    "graph_projection_sha256",
    "report_sha256",
    "status",
    "failed_constraint_codes",
    "carbon_atom_count",
    "hydrogen_atom_count",
    "molecular_formula",
    "molecule_label",
    "canonical_carbon_path",
    "double_bond_index",
    "double_bond_source_index",
    "double_bond_endpoints",
    "terminal_double_endpoint_count",
    "source_bond_order_ledger_closed",
    "source_atom_marker_ledger_closed",
    "atom_bond_order_valence_ledger_closed",
    "profile_chemistry_supported",
    "profile_graph_preparation_ready",
)
_GATE_FIELD_KEYS = (
    "generic_chemistry_supported",
    "generic_molecular_preparation_ready",
    "global_molecular_preparation_ready",
    "e_z_assessed",
    "cip_assessed",
    "stereochemistry_applicability_assessed",
    "source_bond_order_independently_validated",
    "electronic_structure_assessed",
    "coordinate_linearity_assessed",
    "protonation_assessed",
    "tautomer_assessed",
    "geometry_quality_assessed",
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
)
_GATE_KEYS = set(_GATE_FIELD_KEYS)
_FALSE_GATES = {key: False for key in _GATE_FIELD_KEYS}
_EXPECTED_KEYS = {*_REPORT_FIELD_KEYS, "gates"}

_POSITIVE_EXPECTATIONS = {
    "ethene_c2_positive": (2, "ethene"),
    "propene_c3_positive": (3, "propene"),
    "one_butene_c4_positive": (4, "but-1-ene"),
    "one_pentene_c5_positive": (5, "pent-1-ene"),
    "one_hexene_c6_positive": (6, "hex-1-ene"),
    "one_heptene_c7_positive": (7, "hept-1-ene"),
    "one_octene_c8_positive": (8, "oct-1-ene"),
}
_NEGATIVE_REQUIRED_FAILURE = {
    "c1_lower_bound_negative": "carbon_count_c2_c8",
    "c9_upper_bound_negative": "carbon_count_c2_c8",
    "two_butene_internal_double_negative": ("exact_one_terminal_carbon_double_bond"),
    "isobutene_branched_negative": ("carbon_subgraph_connected_simple_path"),
    "cyclobutene_cycle_negative": "carbon_subgraph_connected_simple_path",
    "butadiene_two_double_negative": ("exact_terminal_monoalkene_formula_c_n_h_2n"),
    "propyne_triple_bond_negative": "source_sdf_bond_order_ledger_exact",
    "ethane_no_double_negative": ("exact_terminal_monoalkene_formula_c_n_h_2n"),
    "propene_missing_h_negative": ("exact_terminal_monoalkene_formula_c_n_h_2n"),
    "propene_excess_h_negative": ("exact_terminal_monoalkene_formula_c_n_h_2n"),
    "propene_hetero_o_negative": "elements_h_c_only",
    "propene_charged_negative": ("formal_charges_source_observed_known_zero"),
    "propene_disconnected_negative": "single_component",
    "propene_atom_map_negative": "atom_maps_absent",
    "propene_aromatic_type4_negative": "aromaticity_absent",
    "propene_isotope_negative": "isotopes_absent",
    "one_butene_same_formula_h_redistribution_negative": (
        "exact_atom_bond_order_valence_ledger"
    ),
    "propene_net_zero_opposite_charges_negative": (
        "formal_charges_source_observed_known_zero"
    ),
}
_EXPECTED_CASE_IDS = (
    *_POSITIVE_EXPECTATIONS,
    *_NEGATIVE_REQUIRED_FAILURE,
)
_POSITIVE_CASE_IDS = frozenset(_POSITIVE_EXPECTATIONS)


def _fixture_source(filename: str) -> dict[str, Any]:
    return {
        "kind": "fixture",
        "path": ("tests/fixtures/v2_1_terminal_monoalkene_c2_c8/" + filename),
    }


_FIXTURE_FILENAMES = {
    "ethene_c2_positive": "ethene_c2_explicit_h.sdf",
    "propene_c3_positive": "propene_c3_explicit_h.sdf",
    "one_butene_c4_positive": "one_butene_c4_explicit_h.sdf",
    "one_pentene_c5_positive": "one_pentene_c5_explicit_h.sdf",
    "one_hexene_c6_positive": "one_hexene_c6_explicit_h.sdf",
    "one_heptene_c7_positive": "one_heptene_c7_explicit_h.sdf",
    "one_octene_c8_positive": "one_octene_c8_explicit_h.sdf",
    "c1_lower_bound_negative": "c1_lower_bound_negative.sdf",
    "c9_upper_bound_negative": "c9_upper_bound_negative.sdf",
    "two_butene_internal_double_negative": ("two_butene_internal_double_negative.sdf"),
    "isobutene_branched_negative": "isobutene_branched_negative.sdf",
    "cyclobutene_cycle_negative": "cyclobutene_cycle_negative.sdf",
    "butadiene_two_double_negative": "butadiene_two_double_negative.sdf",
    "propyne_triple_bond_negative": "propyne_triple_bond_negative.sdf",
    "ethane_no_double_negative": "ethane_no_double_negative.sdf",
    "propene_missing_h_negative": "propene_missing_h_negative.sdf",
    "propene_excess_h_negative": "propene_excess_h_negative.sdf",
    "propene_hetero_o_negative": "propene_hetero_o_negative.sdf",
    "propene_charged_negative": "propene_charged_negative.sdf",
    "propene_disconnected_negative": "propene_disconnected_negative.sdf",
    "propene_atom_map_negative": "propene_atom_map_negative.sdf",
    "propene_aromatic_type4_negative": ("propene_aromatic_type4_negative.sdf"),
    "one_butene_same_formula_h_redistribution_negative": (
        "one_butene_same_formula_h_redistribution_negative.sdf"
    ),
    "propene_net_zero_opposite_charges_negative": (
        "propene_net_zero_opposite_charges_negative.sdf"
    ),
}
_EXPECTED_SOURCE_SPECS = {
    case_id: _fixture_source(filename)
    for case_id, filename in _FIXTURE_FILENAMES.items()
}
_PROPENE_SOURCE_SHA256 = (
    "f6e2764ed5a105aac83a76070f9db13bab218bdf3f49b86ffc117b4ba750a94a"
)
_ISOTOPE_MUTATION = {
    "kind": "insert_ascii_before_first_m_end",
    "ascii": "M  ISO  1   1  13\n",
}
_EXPECTED_SOURCE_SPECS["propene_isotope_negative"] = {
    "kind": "derived_fixture",
    "path": ("tests/fixtures/v2_1_terminal_monoalkene_c2_c8/propene_c3_explicit_h.sdf"),
    "base_source_sha256": _PROPENE_SOURCE_SHA256,
    "mutation": _ISOTOPE_MUTATION,
}


class TerminalMonoalkeneCorpusManifestError(ValueError):
    """Raised when the frozen monoalkene corpus is inconsistent."""


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise TerminalMonoalkeneCorpusManifestError(
                f"duplicate JSON object key {key!r}"
            )
        output[key] = value
    return output


def _reject_nonstandard_constant(token: str) -> None:
    raise TerminalMonoalkeneCorpusManifestError(f"nonstandard JSON constant {token!r}")


def _expect_mapping(value: Any, context: str) -> dict[str, Any]:
    if type(value) is not dict:
        raise TerminalMonoalkeneCorpusManifestError(f"{context} must be an object")
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
        raise TerminalMonoalkeneCorpusManifestError(
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
        raise TerminalMonoalkeneCorpusManifestError(
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
    except TerminalMonoalkeneCorpusManifestError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TerminalMonoalkeneCorpusManifestError(
            "manifest must be strict UTF-8 JSON"
        ) from exc
    return _expect_mapping(value, "manifest")


def _require_sha256(value: Any, context: str) -> str:
    if type(value) is not str or _LOWERCASE_SHA256.fullmatch(value) is None:
        raise TerminalMonoalkeneCorpusManifestError(
            f"{context} must be a lowercase SHA-256"
        )
    return value


def _require_nonnegative_integer(value: Any, context: str) -> int:
    if type(value) is not int or value < 0:
        raise TerminalMonoalkeneCorpusManifestError(
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
        "profile_schema_id": TERMINAL_MONOALKENE_C2_C8_PROFILE_SCHEMA_ID,
        "profile_schema_version": (TERMINAL_MONOALKENE_C2_C8_PROFILE_SCHEMA_VERSION),
        "profile_id": TERMINAL_MONOALKENE_C2_C8_PROFILE_ID,
        "graph_projection_schema_id": (
            TERMINAL_MONOALKENE_C2_C8_GRAPH_PROJECTION_SCHEMA_ID
        ),
        "graph_projection_identity_semantics": (
            TERMINAL_MONOALKENE_C2_C8_GRAPH_PROJECTION_IDENTITY_SEMANTICS
        ),
        "rule_set_schema_id": TERMINAL_MONOALKENE_C2_C8_RULE_SET_SCHEMA_ID,
        "rule_set_sha256": TERMINAL_MONOALKENE_C2_C8_RULE_SET_SHA256,
        "profile_preparation_scope": (TERMINAL_MONOALKENE_C2_C8_PREPARATION_SCOPE),
        "unbranched_path_definition": UNBRANCHED_PATH_DEFINITION,
        "bond_order_valence_ledger_semantics": (BOND_ORDER_VALENCE_LEDGER_SEMANTICS),
        "eligible_consumer_ids": list(TERMINAL_MONOALKENE_C2_C8_AUDIT_CONSUMER_IDS),
        "source_authentication_status": SOURCE_AUTHENTICATION_STATUS,
    }


def _fixture_path(relative_path: Any) -> Path:
    if type(relative_path) is not str:
        raise TerminalMonoalkeneCorpusManifestError("source path must be a string")
    pure = PurePosixPath(relative_path)
    prefix = ("tests", "fixtures", "v2_1_terminal_monoalkene_c2_c8")
    if (
        pure.is_absolute()
        or ".." in pure.parts
        or pure.suffix != ".sdf"
        or len(pure.parts) != 4
        or pure.parts[:3] != prefix
    ):
        raise TerminalMonoalkeneCorpusManifestError(
            "source path must be a repository-relative corpus SDF fixture"
        )
    path = (REPOSITORY_ROOT / Path(*pure.parts)).resolve()
    fixture_root = (
        REPOSITORY_ROOT / "tests" / "fixtures" / "v2_1_terminal_monoalkene_c2_c8"
    ).resolve()
    if not path.is_relative_to(fixture_root) or not path.is_file():
        raise TerminalMonoalkeneCorpusManifestError(
            "source fixture must resolve under the monoalkene corpus"
        )
    return path


def _materialize_source(case: Mapping[str, Any]) -> bytes:
    case_id = case["case_id"]
    source = _expect_mapping(case["source"], f"{case_id}.source")
    expected_source = _EXPECTED_SOURCE_SPECS.get(case_id)
    if source != expected_source:
        raise TerminalMonoalkeneCorpusManifestError(
            f"{case_id}.source does not match the frozen source policy"
        )
    source_bytes = _fixture_path(source["path"]).read_bytes()
    if source["kind"] == "derived_fixture":
        if hashlib.sha256(source_bytes).hexdigest() != (source["base_source_sha256"]):
            raise TerminalMonoalkeneCorpusManifestError(
                f"{case_id} base source SHA-256 mismatch"
            )
        marker = b"M  END\n"
        if source_bytes.count(marker) != 1:
            raise TerminalMonoalkeneCorpusManifestError(
                f"{case_id} requires exactly one M  END marker"
            )
        try:
            insertion = source["mutation"]["ascii"].encode(
                "ascii",
                errors="strict",
            )
        except UnicodeEncodeError as exc:
            raise TerminalMonoalkeneCorpusManifestError(
                f"{case_id} mutation must be ASCII"
            ) from exc
        source_bytes = source_bytes.replace(
            marker,
            insertion + marker,
            1,
        )
    if hashlib.sha256(source_bytes).hexdigest() != case["source_sha256"]:
        raise TerminalMonoalkeneCorpusManifestError(
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
    for count_name in (
        "carbon_atom_count",
        "hydrogen_atom_count",
        "terminal_double_endpoint_count",
    ):
        _require_nonnegative_integer(
            expected[count_name],
            f"{case_id}.{count_name}",
        )
    failures = expected["failed_constraint_codes"]
    if (
        type(failures) is not list
        or any(type(code) is not str or not code for code in failures)
        or len(failures) != len(set(failures))
        or any(
            code not in TERMINAL_MONOALKENE_C2_C8_CONSTRAINT_CODES for code in failures
        )
    ):
        raise TerminalMonoalkeneCorpusManifestError(
            f"{case_id} failed constraint codes are invalid"
        )
    gates = _expect_mapping(expected["gates"], f"{case_id}.gates")
    _expect_exact_keys(gates, _GATE_KEYS, f"{case_id}.gates")
    if gates != _FALSE_GATES:
        raise TerminalMonoalkeneCorpusManifestError(
            f"{case_id} cannot promote any global or authority gate"
        )
    if (
        expected["canonical_topology_schema_id"] != CANONICAL_TOPOLOGY_SCHEMA_ID
        or expected["chemistry_report_schema_version"]
        != CHEMISTRY_COVERAGE_SCHEMA_VERSION
        or expected["preparation_report_schema_version"]
        != PREPARATION_REPORT_SCHEMA_VERSION
    ):
        raise TerminalMonoalkeneCorpusManifestError(
            f"{case_id} topology or upstream report binding mismatch"
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
        raise TerminalMonoalkeneCorpusManifestError(
            f"{case_id} source or parser binding mismatch"
        )
    if (
        expected["source_authentication_status"] != SOURCE_AUTHENTICATION_STATUS
        or expected["source_authenticated"] is not False
    ):
        raise TerminalMonoalkeneCorpusManifestError(
            f"{case_id} source authentication boundary mismatch"
        )
    if (
        expected["graph_projection_schema_id"]
        != TERMINAL_MONOALKENE_C2_C8_GRAPH_PROJECTION_SCHEMA_ID
        or expected["graph_projection_identity_semantics"]
        != TERMINAL_MONOALKENE_C2_C8_GRAPH_PROJECTION_IDENTITY_SEMANTICS
        or expected["unbranched_path_definition"] != UNBRANCHED_PATH_DEFINITION
        or expected["bond_order_valence_ledger_semantics"]
        != BOND_ORDER_VALENCE_LEDGER_SEMANTICS
    ):
        raise TerminalMonoalkeneCorpusManifestError(
            f"{case_id} projection or ledger semantics mismatch"
        )
    for bool_name in (
        "source_bond_order_ledger_closed",
        "source_atom_marker_ledger_closed",
        "atom_bond_order_valence_ledger_closed",
        "profile_chemistry_supported",
        "profile_graph_preparation_ready",
    ):
        if type(expected[bool_name]) is not bool:
            raise TerminalMonoalkeneCorpusManifestError(
                f"{case_id}.{bool_name} must be a boolean"
            )
    path = expected["canonical_carbon_path"]
    if type(path) is not list or any(type(index) is not int for index in path):
        raise TerminalMonoalkeneCorpusManifestError(
            f"{case_id} canonical carbon path is invalid"
        )
    endpoints = expected["double_bond_endpoints"]
    if endpoints is not None and (
        type(endpoints) is not list
        or len(endpoints) != 2
        or any(type(index) is not int for index in endpoints)
        or endpoints != sorted(endpoints)
    ):
        raise TerminalMonoalkeneCorpusManifestError(
            f"{case_id} double-bond endpoints are invalid"
        )
    double_index = expected["double_bond_index"]
    source_index = expected["double_bond_source_index"]
    if (double_index is None) != (source_index is None):
        raise TerminalMonoalkeneCorpusManifestError(
            f"{case_id} double-bond indices must both be present or absent"
        )
    if double_index is not None and (
        type(double_index) is not int
        or double_index < 0
        or type(source_index) is not int
        or source_index != double_index + 1
        or endpoints is None
    ):
        raise TerminalMonoalkeneCorpusManifestError(
            f"{case_id} double-bond index ledger is invalid"
        )

    positive = case["lane"] == "positive"
    if positive:
        carbon_count, label = _POSITIVE_EXPECTATIONS[case_id]
        if (
            expected["status"] != "available"
            or failures
            or expected["carbon_atom_count"] != carbon_count
            or expected["hydrogen_atom_count"] != 2 * carbon_count
            or expected["molecular_formula"] != f"C{carbon_count}H{2 * carbon_count}"
            or expected["molecule_label"] != label
            or expected["canonical_carbon_path"] != list(range(carbon_count))
            or expected["double_bond_index"] != 0
            or expected["double_bond_source_index"] != 1
            or expected["double_bond_endpoints"] != [0, 1]
            or expected["terminal_double_endpoint_count"]
            != (2 if carbon_count == 2 else 1)
            or expected["source_bond_order_ledger_closed"] is not True
            or expected["source_atom_marker_ledger_closed"] is not True
            or expected["atom_bond_order_valence_ledger_closed"] is not True
            or expected["profile_chemistry_supported"] is not True
            or expected["profile_graph_preparation_ready"] is not True
        ):
            raise TerminalMonoalkeneCorpusManifestError(
                f"{case_id} positive profile expectations are inconsistent"
            )
    else:
        required_failure = _NEGATIVE_REQUIRED_FAILURE[case_id]
        if (
            expected["status"] != "unsupported"
            or not failures
            or required_failure not in failures
            or expected["molecule_label"] is not None
            or expected["profile_chemistry_supported"] is not False
            or expected["profile_graph_preparation_ready"] is not False
        ):
            raise TerminalMonoalkeneCorpusManifestError(
                f"{case_id} negative profile expectations are inconsistent"
            )
        if case_id == "c9_upper_bound_negative" and failures != ["carbon_count_c2_c8"]:
            raise TerminalMonoalkeneCorpusManifestError(
                "C9 must fail only the versioned carbon-count boundary"
            )


def _runtime_expected(case: Mapping[str, Any]) -> dict[str, Any]:
    system = parse_sdf_v2000(
        _materialize_source(case),
        source_id=case["source_id"],
    ).system
    document = analyze_terminal_monoalkene_c2_c8_profile(system).to_dict()
    observed = {key: document[key] for key in _REPORT_FIELD_KEYS}
    observed["gates"] = {key: document[key] for key in _GATE_FIELD_KEYS}
    return observed


def _validate_case_runtime(case: Mapping[str, Any]) -> None:
    observed = _runtime_expected(case)
    if observed != case["expected"]:
        mismatches = tuple(
            key
            for key in sorted(_EXPECTED_KEYS)
            if observed.get(key) != case["expected"].get(key)
        )
        raise TerminalMonoalkeneCorpusManifestError(
            f"{case['case_id']} runtime replay mismatch: {mismatches}"
        )


def _validate_manifest(
    document: dict[str, Any],
    *,
    replay_cases: bool = False,
) -> None:
    _expect_exact_keys(document, _TOP_LEVEL_KEYS, "manifest")
    if document["schema_id"] != CORPUS_SCHEMA_ID:
        raise TerminalMonoalkeneCorpusManifestError("manifest schema_id mismatch")
    if document["corpus_id"] != CORPUS_ID:
        raise TerminalMonoalkeneCorpusManifestError("manifest corpus_id mismatch")
    if document["manifest_payload_hash_policy_id"] != (PAYLOAD_HASH_POLICY_ID):
        raise TerminalMonoalkeneCorpusManifestError(
            "manifest payload hash policy mismatch"
        )
    if _require_sha256(
        document["payload_sha256"],
        "payload_sha256",
    ) != _manifest_payload_sha256(document):
        raise TerminalMonoalkeneCorpusManifestError("manifest payload SHA-256 mismatch")
    contracts = _expect_mapping(document["contracts"], "contracts")
    _expect_exact_keys(contracts, _CONTRACT_KEYS, "contracts")
    if contracts != _expected_contracts():
        raise TerminalMonoalkeneCorpusManifestError(
            "manifest contract pins do not match runtime contracts"
        )
    if tuple(contracts["eligible_consumer_ids"]) != (
        TERMINAL_MONOALKENE_C2_C8_AUDIT_CONSUMER_IDS
    ):
        raise TerminalMonoalkeneCorpusManifestError(
            "manifest must declare the sole audit consumer"
        )
    claim_boundary = _expect_mapping(
        document["claim_boundary"],
        "claim_boundary",
    )
    _expect_exact_keys(claim_boundary, _GATE_KEYS, "claim_boundary")
    if claim_boundary != _FALSE_GATES:
        raise TerminalMonoalkeneCorpusManifestError(
            "claim boundary cannot promote global or authority gates"
        )
    cases = document["cases"]
    if type(cases) is not list:
        raise TerminalMonoalkeneCorpusManifestError("cases must be a list")
    observed_ids: list[str] = []
    for index, value in enumerate(cases):
        case = _expect_mapping(value, f"cases[{index}]")
        _expect_exact_keys(case, _CASE_KEYS, f"cases[{index}]")
        case_id = case["case_id"]
        if type(case_id) is not str or _CASE_ID.fullmatch(case_id) is None:
            raise TerminalMonoalkeneCorpusManifestError("case_id is invalid")
        observed_ids.append(case_id)
        expected_lane = "positive" if case_id in _POSITIVE_CASE_IDS else "negative"
        if case["lane"] != expected_lane:
            raise TerminalMonoalkeneCorpusManifestError(
                f"{case_id} lane does not match the frozen corpus"
            )
        if case["source_id"] != case_id:
            raise TerminalMonoalkeneCorpusManifestError(
                f"{case_id} source_id must equal case_id"
            )
        if case["system_mutation"] is not None:
            raise TerminalMonoalkeneCorpusManifestError(
                f"{case_id} cannot apply a hidden canonical-system mutation"
            )
        _require_sha256(case["source_sha256"], f"{case_id}.source_sha256")
        _materialize_source(case)
        _validate_expected(case)
        if replay_cases:
            _validate_case_runtime(case)
    if tuple(observed_ids) != _EXPECTED_CASE_IDS:
        raise TerminalMonoalkeneCorpusManifestError(
            "case IDs must be unique and match the frozen ordered corpus"
        )


def _manifest_document() -> dict[str, Any]:
    return _load_strict_json(MANIFEST_PATH.read_bytes())


def _case_by_id(document: Mapping[str, Any], case_id: str) -> dict[str, Any]:
    return next(case for case in document["cases"] if case["case_id"] == case_id)


def test_manifest_is_strict_self_hashed_and_replays_every_case_exactly() -> None:
    document = _manifest_document()

    _validate_manifest(document, replay_cases=True)

    assert document["payload_sha256"] == EXPECTED_PAYLOAD_SHA256
    assert tuple(case["case_id"] for case in document["cases"]) == (_EXPECTED_CASE_IDS)
    assert len(_POSITIVE_CASE_IDS) == 7
    assert len(_NEGATIVE_REQUIRED_FAILURE) == 18
    assert (
        hashlib.sha256(terminal_monoalkene_c2_c8_rule_set_bytes()).hexdigest()
        == TERMINAL_MONOALKENE_C2_C8_RULE_SET_SHA256
    )
    assert all(
        "smiles" not in json.dumps(case["source"]).lower() for case in document["cases"]
    )


def test_duplicate_keys_and_nonstandard_json_constants_fail_closed() -> None:
    source = MANIFEST_PATH.read_bytes()
    duplicate = source.replace(
        b'  "corpus_id":',
        b'  "corpus_id": "duplicate",\n  "corpus_id":',
        1,
    )
    nonstandard = source.replace(
        b'"carbon_atom_count": 2',
        b'"carbon_atom_count": NaN',
        1,
    )

    with pytest.raises(
        TerminalMonoalkeneCorpusManifestError,
        match="duplicate",
    ):
        _load_strict_json(duplicate)
    with pytest.raises(
        TerminalMonoalkeneCorpusManifestError,
        match="nonstandard",
    ):
        _load_strict_json(nonstandard)


def test_stale_payload_hash_and_unknown_nested_keys_fail_closed() -> None:
    stale = deepcopy(_manifest_document())
    stale["cases"][0]["expected"]["status"] = "unsupported"
    with pytest.raises(
        TerminalMonoalkeneCorpusManifestError,
        match="payload SHA-256",
    ):
        _validate_manifest(stale)

    unknown = deepcopy(_manifest_document())
    unknown["cases"][0]["expected"]["unreviewed_authority"] = True
    _refresh_payload_sha256(unknown)
    with pytest.raises(
        TerminalMonoalkeneCorpusManifestError,
        match="keys mismatch",
    ):
        _validate_manifest(unknown)


def test_source_hash_path_and_isotope_mutation_tamper_fail_closed() -> None:
    wrong_hash = deepcopy(_manifest_document())
    wrong_hash["cases"][1]["source_sha256"] = "0" * 64
    _refresh_payload_sha256(wrong_hash)
    with pytest.raises(
        TerminalMonoalkeneCorpusManifestError,
        match="source SHA-256",
    ):
        _validate_manifest(wrong_hash)

    wrong_path = deepcopy(_manifest_document())
    wrong_path["cases"][1]["source"]["path"] = "../../outside.sdf"
    _refresh_payload_sha256(wrong_path)
    with pytest.raises(
        TerminalMonoalkeneCorpusManifestError,
        match="source policy",
    ):
        _validate_manifest(wrong_path)

    wrong_mutation = deepcopy(_manifest_document())
    isotope = _case_by_id(wrong_mutation, "propene_isotope_negative")
    isotope["source"]["mutation"]["ascii"] = "M  ISO  1   1  12\n"
    _refresh_payload_sha256(wrong_mutation)
    with pytest.raises(
        TerminalMonoalkeneCorpusManifestError,
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
    tampered["cases"][2]["expected"][field] = "f" * 64
    _refresh_payload_sha256(tampered)

    with pytest.raises(
        TerminalMonoalkeneCorpusManifestError,
        match="runtime replay",
    ):
        _validate_manifest(tampered, replay_cases=True)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("double_bond_index", 1),
        ("double_bond_source_index", 2),
        ("double_bond_endpoints", [0, 2]),
        ("source_bond_order_ledger_closed", False),
        ("source_atom_marker_ledger_closed", False),
        ("atom_bond_order_valence_ledger_closed", False),
    ),
)
def test_double_index_endpoint_and_ledger_tamper_fail_closed(
    field: str,
    value: Any,
) -> None:
    tampered = deepcopy(_manifest_document())
    expected = tampered["cases"][0]["expected"]
    expected[field] = value
    if field == "double_bond_index":
        expected["double_bond_source_index"] = 2
    elif field == "double_bond_source_index":
        expected["double_bond_index"] = 1
    _refresh_payload_sha256(tampered)

    with pytest.raises(
        TerminalMonoalkeneCorpusManifestError,
        match="runtime replay|positive profile",
    ):
        _validate_manifest(tampered, replay_cases=True)


def test_parser_binding_and_global_gate_promotion_fail_closed() -> None:
    parser = deepcopy(_manifest_document())
    parser["cases"][0]["expected"]["recomputed_parser_observation_sha256"] = "e" * 64
    _refresh_payload_sha256(parser)
    with pytest.raises(
        TerminalMonoalkeneCorpusManifestError,
        match="source or parser binding",
    ):
        _validate_manifest(parser)

    gate = deepcopy(_manifest_document())
    gate["cases"][0]["expected"]["gates"]["e_z_assessed"] = True
    _refresh_payload_sha256(gate)
    with pytest.raises(
        TerminalMonoalkeneCorpusManifestError,
        match="cannot promote",
    ):
        _validate_manifest(gate)


def test_positive_require_gate_negative_errors_and_consumer_allowlist() -> None:
    document = _manifest_document()
    _validate_manifest(document)
    consumer = TERMINAL_MONOALKENE_C2_C8_AUDIT_CONSUMER_IDS[0]

    for case in document["cases"]:
        system = parse_sdf_v2000(
            _materialize_source(case),
            source_id=case["source_id"],
        ).system
        if case["lane"] == "positive":
            report = require_terminal_monoalkene_c2_c8_graph_profile(
                system,
                consumer_id=consumer,
            )
            assert report.report_sha256 == case["expected"]["report_sha256"]
        else:
            with pytest.raises(TerminalMonoalkeneC2C8ProfileError) as exc_info:
                require_terminal_monoalkene_c2_c8_graph_profile(
                    system,
                    consumer_id=consumer,
                )
            assert (
                exc_info.value.report.report_sha256
                == (case["expected"]["report_sha256"])
            )

    positive_system = parse_sdf_v2000(
        _materialize_source(document["cases"][0]),
        source_id=document["cases"][0]["source_id"],
    ).system
    with pytest.raises(TerminalMonoalkeneC2C8ConsumerError):
        require_terminal_monoalkene_c2_c8_graph_profile(
            positive_system,
            consumer_id="runtime_force_field",
        )


def test_exact_negative_boundaries_and_additional_adversaries_are_pinned() -> None:
    document = _manifest_document()
    _validate_manifest(document)

    c9 = _case_by_id(document, "c9_upper_bound_negative")
    assert c9["expected"]["failed_constraint_codes"] == ["carbon_count_c2_c8"]
    redistributed = _case_by_id(
        document,
        "one_butene_same_formula_h_redistribution_negative",
    )
    assert redistributed["expected"]["molecular_formula"] == "C4H8"
    assert redistributed["expected"]["failed_constraint_codes"] == [
        "exact_atom_bond_order_valence_ledger"
    ]

    charged = _case_by_id(
        document,
        "propene_net_zero_opposite_charges_negative",
    )
    charged_system = parse_sdf_v2000(
        _materialize_source(charged),
        source_id=charged["source_id"],
    ).system
    assert sum(atom.formal_charge for atom in charged_system.atoms) == 0
    assert any(atom.formal_charge > 0 for atom in charged_system.atoms)
    assert any(atom.formal_charge < 0 for atom in charged_system.atoms)
    assert charged["expected"]["failed_constraint_codes"] == [
        "formal_charges_source_observed_known_zero"
    ]


def test_existing_corpora_and_cycloalkene_fixture_bytes_remain_unchanged() -> None:
    expected_hashes = {
        "config/independent_engine_v2_v2_1_cycloalkane_c3_c8_corpus.json": (
            "f3b2bf52ef58c05560a8b44a5d39abb9e3db04f6da74c6a5207b33201e7df581"
        ),
        "config/independent_engine_v2_v2_1_ingest_corpus.json": (
            "685c81fcc8580a57c8495e224eada6beb912c150e4feacaf652f8bdad2aee5b2"
        ),
        "config/independent_engine_v2_v2_2_linear_alkane_corpus.json": (
            "5a9a319ab748ab3ac50920e3f539208503bb04db27ee3295fb50a8af3035898f"
        ),
        ("tests/fixtures/v2_1_cycloalkane_c3_c8/c4_unsaturated_negative.sdf"): (
            "40e62239bbe7e8f48f2bac2ecf54d6eae903a495011a59ff54d1ce87989665f6"
        ),
    }
    for relative_path, expected_sha256 in expected_hashes.items():
        observed = hashlib.sha256(
            (REPOSITORY_ROOT / relative_path).read_bytes()
        ).hexdigest()
        assert observed == expected_sha256
