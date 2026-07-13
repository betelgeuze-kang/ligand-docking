from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import struct
from typing import Any

import pytest

from betelgeuze_engine_v2.forcefield.term_inventory import (
    LINEAR_ALKANE_CONSTRAINT_SELECTION_POLICY_ID,
    LINEAR_ALKANE_ENVIRONMENT_MATCH_POLICY_ID,
    LINEAR_ALKANE_IMPROPER_SELECTION_POLICY_ID,
    LINEAR_ALKANE_PAIR_CLASSIFICATION_POLICY_ID,
    LINEAR_ALKANE_PAIR_INTERACTION_CLASSES,
    LINEAR_ALKANE_TERM_PAIR_INVENTORY_CLAIM_SCOPE,
    LINEAR_ALKANE_TERM_PAIR_INVENTORY_PROFILE_ID,
    LINEAR_ALKANE_TERM_PAIR_INVENTORY_SCHEMA_ID,
    analyze_linear_alkane_term_pair_inventory,
)
from betelgeuze_engine_v2.forcefield.typing import (
    LINEAR_ALKANE_TOPOLOGICAL_ENVIRONMENT_ASSIGNMENT_POLICY_ID,
    LINEAR_ALKANE_TOPOLOGICAL_ENVIRONMENT_TYPING_CLAIM_SCOPE,
    LINEAR_ALKANE_TOPOLOGICAL_ENVIRONMENT_TYPING_SCHEMA_ID,
    analyze_linear_alkane_topological_environment_typing,
)
from betelgeuze_engine_v2.molecular.alkane_forcefield_applicability import (
    LINEAR_ALKANE_C1_C4_FORCE_FIELD_APPLICABILITY_CLAIM_SCOPE,
    LINEAR_ALKANE_C1_C4_FORCE_FIELD_APPLICABILITY_PROFILE_ID,
    LINEAR_ALKANE_C1_C4_FORCE_FIELD_APPLICABILITY_SCHEMA_ID,
    analyze_linear_alkane_c1_c4_force_field_applicability,
)
from betelgeuze_engine_v2.molecular.models import AllAtomSystem
from betelgeuze_engine_v2.molecular.sdf_v2000 import (
    SDF_V2000_PARSER_VERSION,
    parse_sdf_v2000,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = (
    REPOSITORY_ROOT
    / "config"
    / "independent_engine_v2_v2_2_linear_alkane_corpus.json"
)
CORPUS_SCHEMA_ID = "betelgeuze.v2_2_linear_alkane_corpus/1.0.0"
CORPUS_ID = "v2_2_linear_alkane_topology_contract_corpus_v1"
PAYLOAD_HASH_POLICY_ID = (
    "sha256_canonical_json_without_payload_sha256/1.0.0"
)

_LOWERCASE_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_CASE_ID = re.compile(r"^[a-z][a-z0-9_]*$")
_ENVIRONMENT_ID = re.compile(r"^[a-z][a-z0-9_]*$")
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
    "sdf_v2000_parser_version",
    "applicability_schema_id",
    "applicability_profile_id",
    "applicability_claim_scope",
    "typing_schema_id",
    "typing_assignment_policy_id",
    "typing_claim_scope",
    "inventory_schema_id",
    "inventory_profile_id",
    "inventory_claim_scope",
    "environment_match_policy_id",
    "pair_classification_policy_id",
    "improper_selection_policy_id",
    "constraint_selection_policy_id",
    "pair_interaction_classes",
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
_EXPECTED_KEYS = {
    "canonical_system_snapshot_sha256",
    "atom_count",
    "source_bond_count",
    "observed_source_partial_charge_count",
    "applicability_status",
    "applicability_failed_constraint_codes",
    "applicability_report_sha256",
    "typing_status",
    "typing_report_sha256",
    "inventory_status",
    "inventory_report_sha256",
    "environment_counts",
    "environment_assignment_count",
    "bond_term_count",
    "angle_term_count",
    "proper_term_count",
    "improper_term_count",
    "constraint_term_count",
    "pair_classification_count",
    "pair_class_counts",
    "topological_environment_coverage_complete",
    "topological_term_and_pair_classification_complete",
    "gates",
}
_PAIR_CLASS_KEYS = set(LINEAR_ALKANE_PAIR_INTERACTION_CLASSES)
_GATE_KEYS = {
    "preparation_ready",
    "parameterability_assessed",
    "parameterizable",
    "force_field_atom_types_assigned",
    "partial_charges_assigned",
    "parameter_assignment_complete",
    "physics_supported",
    "scientifically_validated",
    "runtime_ready",
    "execution_authorized",
    "energy_evaluation_authorized",
    "force_evaluation_authorized",
    "virial_evaluation_authorized",
    "minimization_authorized",
    "simulation_ready",
    "claim_safe",
}
_FALSE_GATES = {key: False for key in _GATE_KEYS}
_EXPECTED_CASE_IDS = (
    "methane_c1_explicit_h",
    "ethane_c2_explicit_h",
    "propane_c3_explicit_h",
    "n_butane_c4_explicit_h",
    "isobutane_branched_negative",
    "cyclobutane_cycle_negative",
    "ethane_missing_h_negative",
    "ethane_c13_negative",
    "ethane_charged_negative",
    "ethane_source_partial_charge_negative",
)
_POSITIVE_CASE_IDS = frozenset(_EXPECTED_CASE_IDS[:4])

_ETHANE_PATH = "tests/fixtures/v2_2_linear_alkane/ethane_explicit_h.sdf"
_ETHANE_SHA256 = "0507a3e8367929b3a6ea42925c2499d1f467a20a6c78de436c3b29d53b16ab9c"
_EXPECTED_SOURCE_SPECS: dict[str, dict[str, Any]] = {
    "methane_c1_explicit_h": {
        "kind": "fixture",
        "path": "tests/fixtures/v2_1_ingest_corpus/methane_explicit_h.sdf",
    },
    "ethane_c2_explicit_h": {"kind": "fixture", "path": _ETHANE_PATH},
    "propane_c3_explicit_h": {
        "kind": "fixture",
        "path": "tests/fixtures/v2_2_linear_alkane/propane_explicit_h.sdf",
    },
    "n_butane_c4_explicit_h": {
        "kind": "fixture",
        "path": "tests/fixtures/v2_2_linear_alkane/n_butane_explicit_h.sdf",
    },
    "isobutane_branched_negative": {
        "kind": "fixture",
        "path": (
            "tests/fixtures/v2_2_linear_alkane/"
            "isobutane_branched_explicit_h.sdf"
        ),
    },
    "cyclobutane_cycle_negative": {
        "kind": "fixture",
        "path": "tests/fixtures/v2_2_linear_alkane/cyclobutane_explicit_h.sdf",
    },
    "ethane_missing_h_negative": {
        "kind": "fixture",
        "path": "tests/fixtures/v2_2_linear_alkane/ethane_missing_h.sdf",
    },
    "ethane_c13_negative": {
        "kind": "derived_fixture",
        "path": _ETHANE_PATH,
        "base_source_sha256": _ETHANE_SHA256,
        "mutation": {
            "kind": "insert_ascii_before_first_m_end",
            "ascii": "M  ISO  1   1  13\n",
        },
    },
    "ethane_charged_negative": {
        "kind": "derived_fixture",
        "path": _ETHANE_PATH,
        "base_source_sha256": _ETHANE_SHA256,
        "mutation": {
            "kind": "insert_ascii_before_first_m_end",
            "ascii": "M  CHG  1   1   1\n",
        },
    },
    "ethane_source_partial_charge_negative": {
        "kind": "fixture",
        "path": _ETHANE_PATH,
    },
}


class LinearAlkaneCorpusManifestError(ValueError):
    """Raised when corpus JSON or replayed contract evidence is inconsistent."""


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise LinearAlkaneCorpusManifestError(
                f"duplicate JSON object key {key!r}"
            )
        output[key] = value
    return output


def _reject_nonstandard_constant(token: str) -> None:
    raise LinearAlkaneCorpusManifestError(
        f"nonstandard JSON constant {token!r}"
    )


def _expect_mapping(value: Any, context: str) -> dict[str, Any]:
    if type(value) is not dict:
        raise LinearAlkaneCorpusManifestError(f"{context} must be an object")
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
        raise LinearAlkaneCorpusManifestError(
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
        raise LinearAlkaneCorpusManifestError(
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
    except LinearAlkaneCorpusManifestError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LinearAlkaneCorpusManifestError(
            "manifest must be strict UTF-8 JSON"
        ) from exc
    return _expect_mapping(value, "manifest")


def _expected_contracts() -> dict[str, Any]:
    return {
        "sdf_v2000_parser_version": SDF_V2000_PARSER_VERSION,
        "applicability_schema_id": (
            LINEAR_ALKANE_C1_C4_FORCE_FIELD_APPLICABILITY_SCHEMA_ID
        ),
        "applicability_profile_id": (
            LINEAR_ALKANE_C1_C4_FORCE_FIELD_APPLICABILITY_PROFILE_ID
        ),
        "applicability_claim_scope": (
            LINEAR_ALKANE_C1_C4_FORCE_FIELD_APPLICABILITY_CLAIM_SCOPE
        ),
        "typing_schema_id": (
            LINEAR_ALKANE_TOPOLOGICAL_ENVIRONMENT_TYPING_SCHEMA_ID
        ),
        "typing_assignment_policy_id": (
            LINEAR_ALKANE_TOPOLOGICAL_ENVIRONMENT_ASSIGNMENT_POLICY_ID
        ),
        "typing_claim_scope": (
            LINEAR_ALKANE_TOPOLOGICAL_ENVIRONMENT_TYPING_CLAIM_SCOPE
        ),
        "inventory_schema_id": LINEAR_ALKANE_TERM_PAIR_INVENTORY_SCHEMA_ID,
        "inventory_profile_id": LINEAR_ALKANE_TERM_PAIR_INVENTORY_PROFILE_ID,
        "inventory_claim_scope": LINEAR_ALKANE_TERM_PAIR_INVENTORY_CLAIM_SCOPE,
        "environment_match_policy_id": LINEAR_ALKANE_ENVIRONMENT_MATCH_POLICY_ID,
        "pair_classification_policy_id": (
            LINEAR_ALKANE_PAIR_CLASSIFICATION_POLICY_ID
        ),
        "improper_selection_policy_id": (
            LINEAR_ALKANE_IMPROPER_SELECTION_POLICY_ID
        ),
        "constraint_selection_policy_id": (
            LINEAR_ALKANE_CONSTRAINT_SELECTION_POLICY_ID
        ),
        "pair_interaction_classes": list(
            LINEAR_ALKANE_PAIR_INTERACTION_CLASSES
        ),
        "source_authentication_status": "digest_bound_not_authenticated",
    }


def _require_sha256(value: Any, context: str) -> str:
    if type(value) is not str or _LOWERCASE_SHA256.fullmatch(value) is None:
        raise LinearAlkaneCorpusManifestError(
            f"{context} must be a lowercase SHA-256"
        )
    return value


def _fixture_path(relative_path: Any) -> Path:
    if type(relative_path) is not str:
        raise LinearAlkaneCorpusManifestError("source path must be a string")
    pure = PurePosixPath(relative_path)
    if (
        pure.is_absolute()
        or ".." in pure.parts
        or pure.suffix != ".sdf"
        or pure.parts[:2] != ("tests", "fixtures")
    ):
        raise LinearAlkaneCorpusManifestError(
            "source path must be a repository-relative SDF fixture"
        )
    path = (REPOSITORY_ROOT / Path(*pure.parts)).resolve()
    fixtures_root = (REPOSITORY_ROOT / "tests" / "fixtures").resolve()
    if not path.is_relative_to(fixtures_root) or not path.is_file():
        raise LinearAlkaneCorpusManifestError(
            "source fixture must resolve under tests/fixtures"
        )
    return path


def _materialize_source(case: Mapping[str, Any]) -> bytes:
    case_id = case["case_id"]
    source = _expect_mapping(case["source"], f"{case_id}.source")
    expected_source = _EXPECTED_SOURCE_SPECS.get(case_id)
    if source != expected_source:
        raise LinearAlkaneCorpusManifestError(
            f"{case_id}.source does not match the frozen source policy"
        )
    source_bytes = _fixture_path(source["path"]).read_bytes()
    if source["kind"] == "derived_fixture":
        observed_base_sha256 = hashlib.sha256(source_bytes).hexdigest()
        if observed_base_sha256 != source["base_source_sha256"]:
            raise LinearAlkaneCorpusManifestError(
                f"{case_id} base source SHA-256 mismatch"
            )
        mutation = source["mutation"]
        marker = b"M  END\n"
        if source_bytes.count(marker) != 1:
            raise LinearAlkaneCorpusManifestError(
                f"{case_id} requires exactly one M  END marker"
            )
        try:
            insertion = mutation["ascii"].encode("ascii", errors="strict")
        except UnicodeEncodeError as exc:
            raise LinearAlkaneCorpusManifestError(
                f"{case_id} mutation must be ASCII"
            ) from exc
        source_bytes = source_bytes.replace(
            marker,
            insertion + marker,
            1,
        )
    observed_sha256 = hashlib.sha256(source_bytes).hexdigest()
    if observed_sha256 != case["source_sha256"]:
        raise LinearAlkaneCorpusManifestError(
            f"{case_id} materialized source SHA-256 mismatch"
        )
    return source_bytes


def _apply_system_mutation(
    system: AllAtomSystem,
    case: Mapping[str, Any],
) -> AllAtomSystem:
    mutation = case["system_mutation"]
    case_id = case["case_id"]
    if case_id != "ethane_source_partial_charge_negative":
        if mutation is not None:
            raise LinearAlkaneCorpusManifestError(
                f"{case_id} cannot declare a system mutation"
            )
        return system
    expected = {
        "kind": "set_atom_partial_charge_e",
        "atom_index": 0,
        "value_ieee754_binary64_be": "0000000000000000",
    }
    if mutation != expected:
        raise LinearAlkaneCorpusManifestError(
            "source-partial-charge mutation does not match the frozen policy"
        )
    value = struct.unpack(">d", bytes.fromhex(mutation["value_ieee754_binary64_be"]))[0]
    atoms = list(system.atoms)
    atom_index = mutation["atom_index"]
    atoms[atom_index] = replace(atoms[atom_index], partial_charge_e=value)
    return replace(system, atoms=tuple(atoms))


def _require_nonnegative_integer(value: Any, context: str) -> int:
    if type(value) is not int or value < 0:
        raise LinearAlkaneCorpusManifestError(
            f"{context} must be a non-negative integer"
        )
    return value


def _validate_expected(case: Mapping[str, Any]) -> None:
    case_id = case["case_id"]
    expected = _expect_mapping(case["expected"], f"{case_id}.expected")
    _expect_exact_keys(expected, _EXPECTED_KEYS, f"{case_id}.expected")
    for digest_name in (
        "canonical_system_snapshot_sha256",
        "applicability_report_sha256",
        "typing_report_sha256",
        "inventory_report_sha256",
    ):
        _require_sha256(expected[digest_name], f"{case_id}.{digest_name}")
    for count_name in (
        "atom_count",
        "source_bond_count",
        "observed_source_partial_charge_count",
        "environment_assignment_count",
        "bond_term_count",
        "angle_term_count",
        "proper_term_count",
        "improper_term_count",
        "constraint_term_count",
        "pair_classification_count",
    ):
        _require_nonnegative_integer(
            expected[count_name],
            f"{case_id}.{count_name}",
        )
    failures = expected["applicability_failed_constraint_codes"]
    if type(failures) is not list or any(
        type(code) is not str or not code for code in failures
    ):
        raise LinearAlkaneCorpusManifestError(
            f"{case_id} failed constraint codes must be a string list"
        )
    environment_counts = _expect_mapping(
        expected["environment_counts"],
        f"{case_id}.environment_counts",
    )
    if any(
        _ENVIRONMENT_ID.fullmatch(environment_id) is None
        or type(count) is not int
        or count <= 0
        for environment_id, count in environment_counts.items()
    ):
        raise LinearAlkaneCorpusManifestError(
            f"{case_id} environment counts are invalid"
        )
    pair_counts = _expect_mapping(
        expected["pair_class_counts"],
        f"{case_id}.pair_class_counts",
    )
    _expect_exact_keys(pair_counts, _PAIR_CLASS_KEYS, f"{case_id}.pair_class_counts")
    if any(type(value) is not int or value < 0 for value in pair_counts.values()):
        raise LinearAlkaneCorpusManifestError(
            f"{case_id} pair class counts must be non-negative integers"
        )
    gates = _expect_mapping(expected["gates"], f"{case_id}.gates")
    _expect_exact_keys(gates, _GATE_KEYS, f"{case_id}.gates")
    if gates != _FALSE_GATES:
        raise LinearAlkaneCorpusManifestError(
            f"{case_id} cannot promote any force-field or authority gate"
        )
    for coverage_name in (
        "topological_environment_coverage_complete",
        "topological_term_and_pair_classification_complete",
    ):
        if type(expected[coverage_name]) is not bool:
            raise LinearAlkaneCorpusManifestError(
                f"{case_id}.{coverage_name} must be a boolean"
            )

    positive = case["lane"] == "positive"
    expected_statuses = (
        ("available", "environments_available", "available")
        if positive
        else ("unsupported", "unsupported_system", "unsupported")
    )
    if (
        expected["applicability_status"],
        expected["typing_status"],
        expected["inventory_status"],
    ) != expected_statuses:
        raise LinearAlkaneCorpusManifestError(
            f"{case_id} statuses do not match its lane"
        )
    if positive:
        if failures:
            raise LinearAlkaneCorpusManifestError(
                f"{case_id} positive case cannot have failed constraints"
            )
        if sum(environment_counts.values()) != expected["atom_count"]:
            raise LinearAlkaneCorpusManifestError(
                f"{case_id} environment counts must cover every atom"
            )
        if expected["environment_assignment_count"] != expected["atom_count"]:
            raise LinearAlkaneCorpusManifestError(
                f"{case_id} environment assignment count is incomplete"
            )
        if expected["bond_term_count"] != expected["source_bond_count"]:
            raise LinearAlkaneCorpusManifestError(
                f"{case_id} bond terms must cover every source bond"
            )
        if expected["pair_classification_count"] != (
            expected["atom_count"] * (expected["atom_count"] - 1) // 2
        ):
            raise LinearAlkaneCorpusManifestError(
                f"{case_id} pair classification count is incomplete"
            )
        if sum(pair_counts.values()) != expected["pair_classification_count"]:
            raise LinearAlkaneCorpusManifestError(
                f"{case_id} pair class counts are incomplete"
            )
        if not all(
            expected[name]
            for name in (
                "topological_environment_coverage_complete",
                "topological_term_and_pair_classification_complete",
            )
        ):
            raise LinearAlkaneCorpusManifestError(
                f"{case_id} positive topology coverage must be complete"
            )
    else:
        if not failures:
            raise LinearAlkaneCorpusManifestError(
                f"{case_id} negative case requires failed constraints"
            )
        zero_fields = (
            "environment_assignment_count",
            "bond_term_count",
            "angle_term_count",
            "proper_term_count",
            "improper_term_count",
            "constraint_term_count",
            "pair_classification_count",
        )
        if (
            environment_counts
            or any(expected[name] != 0 for name in zero_fields)
            or any(pair_counts.values())
            or expected["topological_environment_coverage_complete"]
            or expected["topological_term_and_pair_classification_complete"]
        ):
            raise LinearAlkaneCorpusManifestError(
                f"{case_id} negative case cannot expose assignments, terms, or pairs"
            )


def _observed_gates(applicability: Any, typing_report: Any, inventory: Any) -> dict[str, bool]:
    return {
        "preparation_ready": bool(
            applicability.preparation_ready or inventory.preparation_ready
        ),
        "parameterability_assessed": bool(
            applicability.parameterability_assessed
            or typing_report.parameterability_assessed
        ),
        "parameterizable": bool(
            applicability.parameterizable or typing_report.parameterizable
        ),
        "force_field_atom_types_assigned": bool(
            applicability.atom_types_assigned
            or typing_report.force_field_atom_types_assigned
            or inventory.force_field_atom_typing_complete
        ),
        "partial_charges_assigned": bool(
            applicability.partial_charges_assigned
            or typing_report.partial_charges_assigned
            or inventory.partial_charge_assignment_complete
        ),
        "parameter_assignment_complete": bool(
            applicability.force_field_parameters_assigned
            or typing_report.parameter_set_id is not None
            or typing_report.parameter_assignment_sha256 is not None
            or inventory.parameter_assignment_complete
        ),
        "physics_supported": bool(
            applicability.physics_supported
            or typing_report.physics_supported
            or inventory.physics_supported
        ),
        "scientifically_validated": bool(
            applicability.scientific_validity_green
            or typing_report.scientifically_validated
        ),
        "runtime_ready": bool(
            applicability.runtime_eligible
            or typing_report.runtime_ready
            or inventory.simulation_ready
        ),
        "execution_authorized": bool(
            applicability.execution_authorized
            or typing_report.authority_granted
        ),
        "energy_evaluation_authorized": bool(
            applicability.energy_evaluation_authorized
            or typing_report.energy_evaluation_authorized
            or inventory.energy_evaluation_authorized
        ),
        "force_evaluation_authorized": bool(
            applicability.force_evaluation_authorized
            or typing_report.force_evaluation_authorized
            or inventory.force_evaluation_authorized
        ),
        "virial_evaluation_authorized": bool(
            applicability.virial_evaluation_authorized
            or typing_report.virial_evaluation_authorized
            or inventory.virial_evaluation_authorized
        ),
        "minimization_authorized": bool(
            applicability.minimization_authorized
            or typing_report.minimization_authorized
            or inventory.minimization_authorized
        ),
        "simulation_ready": bool(
            applicability.simulation_ready
            or typing_report.simulation_ready
            or inventory.simulation_ready
        ),
        "claim_safe": bool(
            applicability.claim_safe
            or typing_report.claim_safe
            or inventory.claim_safe
        ),
    }


def _runtime_expected(case: Mapping[str, Any]) -> dict[str, Any]:
    source = _materialize_source(case)
    system = parse_sdf_v2000(source, source_id=case["source_id"]).system
    system = _apply_system_mutation(system, case)
    applicability = analyze_linear_alkane_c1_c4_force_field_applicability(
        system
    )
    typing_report = analyze_linear_alkane_topological_environment_typing(
        system
    )
    inventory = analyze_linear_alkane_term_pair_inventory(system)
    environment_counts = Counter(
        assignment.topological_environment_id
        for assignment in typing_report.environment_assignments
    )
    return {
        "canonical_system_snapshot_sha256": (
            applicability.canonical_system_snapshot_sha256
        ),
        "atom_count": system.atom_count,
        "source_bond_count": len(system.bonds),
        "observed_source_partial_charge_count": (
            applicability.observed_partial_charge_count
        ),
        "applicability_status": applicability.applicability_status,
        "applicability_failed_constraint_codes": list(
            applicability.failed_constraint_codes
        ),
        "applicability_report_sha256": applicability.report_sha256,
        "typing_status": typing_report.typing_status,
        "typing_report_sha256": typing_report.report_sha256,
        "inventory_status": inventory.inventory_status,
        "inventory_report_sha256": inventory.report_sha256,
        "environment_counts": dict(sorted(environment_counts.items())),
        "environment_assignment_count": len(
            typing_report.environment_assignments
        ),
        "bond_term_count": len(inventory.bond_terms),
        "angle_term_count": len(inventory.angle_terms),
        "proper_term_count": len(inventory.proper_terms),
        "improper_term_count": len(inventory.improper_identities),
        "constraint_term_count": len(inventory.constraint_identities),
        "pair_classification_count": len(inventory.pair_classifications),
        "pair_class_counts": dict(inventory.pair_class_counts),
        "topological_environment_coverage_complete": (
            typing_report.topological_environment_coverage_complete
        ),
        "topological_term_and_pair_classification_complete": (
            inventory.topological_term_and_pair_classification_complete
        ),
        "gates": _observed_gates(applicability, typing_report, inventory),
    }


def _validate_case_runtime(case: Mapping[str, Any]) -> None:
    observed = _runtime_expected(case)
    if observed != case["expected"]:
        mismatches = tuple(
            key
            for key in sorted(_EXPECTED_KEYS)
            if observed.get(key) != case["expected"].get(key)
        )
        raise LinearAlkaneCorpusManifestError(
            f"{case['case_id']} runtime replay mismatch: {mismatches}"
        )


def _validate_manifest(
    document: dict[str, Any],
    *,
    replay_cases: bool = False,
) -> None:
    _expect_exact_keys(document, _TOP_LEVEL_KEYS, "manifest")
    if document["schema_id"] != CORPUS_SCHEMA_ID:
        raise LinearAlkaneCorpusManifestError("manifest schema_id mismatch")
    if document["corpus_id"] != CORPUS_ID:
        raise LinearAlkaneCorpusManifestError("manifest corpus_id mismatch")
    if document["manifest_payload_hash_policy_id"] != PAYLOAD_HASH_POLICY_ID:
        raise LinearAlkaneCorpusManifestError(
            "manifest payload hash policy mismatch"
        )
    declared_payload_sha256 = _require_sha256(
        document["payload_sha256"],
        "payload_sha256",
    )
    if declared_payload_sha256 != _manifest_payload_sha256(document):
        raise LinearAlkaneCorpusManifestError("manifest payload SHA-256 mismatch")
    contracts = _expect_mapping(document["contracts"], "contracts")
    _expect_exact_keys(contracts, _CONTRACT_KEYS, "contracts")
    if contracts != _expected_contracts():
        raise LinearAlkaneCorpusManifestError(
            "manifest contract pins do not match runtime contracts"
        )
    claim_boundary = _expect_mapping(
        document["claim_boundary"],
        "claim_boundary",
    )
    _expect_exact_keys(claim_boundary, _GATE_KEYS, "claim_boundary")
    if claim_boundary != _FALSE_GATES:
        raise LinearAlkaneCorpusManifestError(
            "claim boundary cannot promote force-field or authority gates"
        )
    cases = document["cases"]
    if type(cases) is not list:
        raise LinearAlkaneCorpusManifestError("cases must be a list")
    observed_ids: list[str] = []
    for index, value in enumerate(cases):
        case = _expect_mapping(value, f"cases[{index}]")
        _expect_exact_keys(case, _CASE_KEYS, f"cases[{index}]")
        case_id = case["case_id"]
        if type(case_id) is not str or _CASE_ID.fullmatch(case_id) is None:
            raise LinearAlkaneCorpusManifestError("case_id is invalid")
        observed_ids.append(case_id)
        expected_lane = "positive" if case_id in _POSITIVE_CASE_IDS else "negative"
        if case["lane"] != expected_lane:
            raise LinearAlkaneCorpusManifestError(
                f"{case_id} lane does not match the frozen corpus"
            )
        if case["source_id"] != case_id:
            raise LinearAlkaneCorpusManifestError(
                f"{case_id} source_id must equal case_id"
            )
        _require_sha256(case["source_sha256"], f"{case_id}.source_sha256")
        _materialize_source(case)
        _validate_expected(case)
        _apply_system_mutation(
            parse_sdf_v2000(
                _materialize_source(case),
                source_id=case_id,
            ).system,
            case,
        )
        if replay_cases:
            _validate_case_runtime(case)
    if tuple(observed_ids) != _EXPECTED_CASE_IDS:
        raise LinearAlkaneCorpusManifestError(
            "case IDs must be unique and match the frozen ordered corpus"
        )


def _manifest_document() -> dict[str, Any]:
    return _load_strict_json(MANIFEST_PATH.read_bytes())


def test_manifest_is_strict_self_hashed_and_replays_every_case_exactly() -> None:
    document = _manifest_document()

    _validate_manifest(document, replay_cases=True)

    assert document["payload_sha256"] == (
        "a840cc50878195f2a3ce9a33086ed6b84828312c39ace56119af06539417c0f6"
    )
    assert tuple(case["case_id"] for case in document["cases"]) == (
        _EXPECTED_CASE_IDS
    )
    assert all(case["expected"]["gates"] == _FALSE_GATES for case in document["cases"])


def test_duplicate_keys_and_nonstandard_json_constants_fail_closed() -> None:
    source = MANIFEST_PATH.read_bytes()
    duplicate = source.replace(
        b'  "corpus_id":',
        b'  "corpus_id": "duplicate",\n  "corpus_id":',
        1,
    )
    nonstandard = source.replace(
        b'"atom_count": 5',
        b'"atom_count": NaN',
        1,
    )

    with pytest.raises(LinearAlkaneCorpusManifestError, match="duplicate"):
        _load_strict_json(duplicate)
    with pytest.raises(LinearAlkaneCorpusManifestError, match="nonstandard"):
        _load_strict_json(nonstandard)


def test_stale_payload_hash_and_unknown_nested_keys_fail_closed() -> None:
    stale = deepcopy(_manifest_document())
    stale["cases"][0]["expected"]["atom_count"] = 6
    with pytest.raises(LinearAlkaneCorpusManifestError, match="payload SHA-256"):
        _validate_manifest(stale)

    unknown = deepcopy(_manifest_document())
    unknown["cases"][0]["expected"]["unreviewed_authority"] = True
    _refresh_payload_sha256(unknown)
    with pytest.raises(LinearAlkaneCorpusManifestError, match="keys mismatch"):
        _validate_manifest(unknown)


def test_source_hash_path_and_derived_mutation_tamper_fail_closed() -> None:
    wrong_hash = deepcopy(_manifest_document())
    wrong_hash["cases"][1]["source_sha256"] = "0" * 64
    _refresh_payload_sha256(wrong_hash)
    with pytest.raises(LinearAlkaneCorpusManifestError, match="source SHA-256"):
        _validate_manifest(wrong_hash)

    wrong_path = deepcopy(_manifest_document())
    wrong_path["cases"][1]["source"]["path"] = "../../outside.sdf"
    _refresh_payload_sha256(wrong_path)
    with pytest.raises(LinearAlkaneCorpusManifestError, match="source policy"):
        _validate_manifest(wrong_path)

    wrong_mutation = deepcopy(_manifest_document())
    wrong_mutation["cases"][7]["source"]["mutation"]["ascii"] = (
        "M  ISO  1   1  12\n"
    )
    _refresh_payload_sha256(wrong_mutation)
    with pytest.raises(LinearAlkaneCorpusManifestError, match="source policy"):
        _validate_manifest(wrong_mutation)


def test_report_hash_count_and_gate_tamper_fail_runtime_replay() -> None:
    report_hash = deepcopy(_manifest_document())
    report_hash["cases"][3]["expected"]["inventory_report_sha256"] = "f" * 64
    _refresh_payload_sha256(report_hash)
    with pytest.raises(LinearAlkaneCorpusManifestError, match="runtime replay"):
        _validate_manifest(report_hash, replay_cases=True)

    count = deepcopy(_manifest_document())
    count["cases"][3]["expected"]["proper_term_count"] = 26
    _refresh_payload_sha256(count)
    with pytest.raises(LinearAlkaneCorpusManifestError, match="runtime replay"):
        _validate_manifest(count, replay_cases=True)

    gate = deepcopy(_manifest_document())
    gate["cases"][0]["expected"]["gates"]["claim_safe"] = True
    _refresh_payload_sha256(gate)
    with pytest.raises(LinearAlkaneCorpusManifestError, match="cannot promote"):
        _validate_manifest(gate)


def test_negative_rows_pin_zero_assignments_terms_and_pairs() -> None:
    document = _manifest_document()
    _validate_manifest(document)

    for case in document["cases"]:
        if case["lane"] != "negative":
            continue
        expected = case["expected"]
        assert expected["environment_counts"] == {}
        assert expected["environment_assignment_count"] == 0
        assert expected["bond_term_count"] == 0
        assert expected["angle_term_count"] == 0
        assert expected["proper_term_count"] == 0
        assert expected["improper_term_count"] == 0
        assert expected["constraint_term_count"] == 0
        assert expected["pair_classification_count"] == 0
        assert all(count == 0 for count in expected["pair_class_counts"].values())
        assert expected["topological_environment_coverage_complete"] is False
        assert (
            expected["topological_term_and_pair_classification_complete"]
            is False
        )
