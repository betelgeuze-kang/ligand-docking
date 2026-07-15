from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from typing import Any

import pytest

from betelgeuze_engine_v2.molecular.mmcif_archive_standard_l_peptide_topology import (
    MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_PARSER_PEDIGREE_ID,
    MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_PROFILE_ID,
    MmcifArchiveStandardLPeptideTopologyError,
    parse_mmcif_archive_standard_l_peptide_topology,
    round_trip_mmcif_archive_standard_l_peptide_topology_source,
)
from betelgeuze_engine_v2.molecular.observation import (
    MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_PREPARATION_INVENTORY_COMMITMENT_SCHEMA_ID,
    mmcif_archive_standard_l_peptide_topology_preparation_inventory_sha256,
)
from betelgeuze_engine_v2.molecular.standard_l_peptide_rules import (
    STANDARD_L_PEPTIDE_RULE_MANIFEST_SCHEMA_ID,
    STANDARD_L_PEPTIDE_RULE_MANIFEST_SHA256,
    validate_standard_l_peptide_rule_manifest,
)
from tests.unit.test_engine_v2_mmcif_archive_standard_l_peptide_topology import (
    GLY_ALA,
    _negative_cases,
)


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = (
    ROOT
    / "config"
    / "independent_engine_v2_v2_1_mmcif_archive_standard_l_peptide_topology_corpus.json"
)
FIXTURE_ROOT = (
    ROOT / "tests" / "fixtures" / "v2_1_mmcif_archive_standard_l_peptide_topology"
)
CORPUS_SCHEMA_ID = (
    "betelgeuze.v2_1_mmcif_archive_standard_l_peptide_topology_corpus/1.0.0"
)
CORPUS_ID = "v2_1_strict_mmcif_archive_standard_l_peptide_topology_v1"
PAYLOAD_HASH_POLICY_ID = "sha256_canonical_json_without_payload_sha256/1.0.0"
EXPECTED_PAYLOAD_SHA256 = (
    "58377d1b60a493e62a53af8250c912b49b7475e76d41316ee8d2380ffaf967de"
)

_LOWER_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_CASE_ID = re.compile(r"^[a-z][a-z0-9_]*$")
_MAX_MANIFEST_BYTES = 1024 * 1024
_MAX_FIXTURE_BYTES = 32 * 1024
_MAX_TOTAL_FIXTURE_BYTES = 160 * 1024
_POSITIVE_CASE_IDS = (
    "single_gly",
    "gly_ala_one_asym",
    "ala_gly_ala",
    "gly_ala_two_asym",
    "category_order_variant",
)


class ArchiveStandardLPeptideTopologyCorpusError(ValueError):
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
            raise ArchiveStandardLPeptideTopologyCorpusError("duplicate JSON key")
        result[key] = value
    return result


def _load_manifest() -> dict[str, Any]:
    payload = MANIFEST.read_bytes()
    if len(payload) > _MAX_MANIFEST_BYTES:
        raise ArchiveStandardLPeptideTopologyCorpusError("manifest exceeds byte cap")
    try:
        document = json.loads(
            payload.decode("ascii"), object_pairs_hook=_reject_duplicate_keys
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ArchiveStandardLPeptideTopologyCorpusError(
            "manifest must be strict ASCII JSON"
        ) from exc
    if type(document) is not dict:
        raise ArchiveStandardLPeptideTopologyCorpusError(
            "manifest root must be an object"
        )
    return document


def _fixture_payload(name: str) -> bytes:
    if type(name) is not str:
        raise ArchiveStandardLPeptideTopologyCorpusError(
            "fixture name must be a string"
        )
    relative = PurePosixPath(name)
    if relative.is_absolute() or len(relative.parts) != 1 or relative.name != name:
        raise ArchiveStandardLPeptideTopologyCorpusError(
            "fixture path escapes fixed root"
        )
    path = FIXTURE_ROOT / name
    if not path.is_file() or path.is_symlink():
        raise ArchiveStandardLPeptideTopologyCorpusError(
            "fixture must be a regular fixed file"
        )
    if path.resolve().parent != FIXTURE_ROOT.resolve():
        raise ArchiveStandardLPeptideTopologyCorpusError(
            "fixture resolves outside fixed root"
        )
    payload = path.read_bytes()
    if len(payload) > _MAX_FIXTURE_BYTES:
        raise ArchiveStandardLPeptideTopologyCorpusError("fixture exceeds byte cap")
    return payload


def _failure_mutation_id(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")


def _observed_positive(case: dict[str, Any], source: bytes) -> dict[str, Any]:
    result = round_trip_mmcif_archive_standard_l_peptide_topology_source(
        source, source_id=case["source_id"]
    )
    ingest = result.source_ingest
    ingest_document = ingest.to_dict()
    system = ingest.system
    report_document = result.report.to_dict()
    inter_residue_bonds = sum(
        bond.metadata["mmcif_archive_standard_l_peptide_topology"]["bond_kind"]
        == "sequence_adjacent_peptide_reference"
        for bond in system.bonds
    )
    return {
        "full_source_sha256": ingest.full_source_sha256,
        "projection_sha256": ingest.projection_sha256,
        "topology_state_sha256": ingest.topology_state_sha256,
        "source_binding_sha256": ingest.source_binding_sha256,
        "canonical_topology_sha256": ingest.topology_sha256,
        "system_snapshot_sha256": ingest_document["system_snapshot_sha256"],
        "canonical_output_sha256": ingest_document["canonical_output_sha256"],
        "canonical_output_byte_count": len(result.write_result.payload),
        "parser_observation_sha256": system.provenance.metadata[
            "parser_observation_sha256"
        ],
        "preparation_inventory_commitment_sha256": (
            mmcif_archive_standard_l_peptide_topology_preparation_inventory_sha256(
                system
            )
        ),
        "round_trip_report_sha256": hashlib.sha256(
            _canonical_json_bytes(report_document)
        ).hexdigest(),
        "atom_count": system.atom_count,
        "bond_count": len(system.bonds),
        "residue_count": len(system.residues),
        "chain_count": len(system.chains),
        "inter_residue_reference_bond_count": inter_residue_bonds,
        "round_trip_preserved": all(
            (
                result.report.topology_state_equal,
                result.report.topology_equal,
                result.report.emitted_source_reparsed_exact,
                result.report.second_emission_byte_stable,
            )
        ),
        "second_emission_byte_stable": result.report.second_emission_byte_stable,
    }


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
    payload_document = dict(manifest)
    payload_document.pop("payload_sha256")
    assert hashlib.sha256(_canonical_json_bytes(payload_document)).hexdigest() == (
        EXPECTED_PAYLOAD_SHA256
    )
    assert manifest["payload_sha256"] == EXPECTED_PAYLOAD_SHA256

    contracts = manifest["contracts"]
    assert contracts["profile_id"] == (
        MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_PROFILE_ID
    )
    assert contracts["parser_pedigree_id"] == (
        MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_PARSER_PEDIGREE_ID
    )
    assert contracts["rule_manifest_schema_id"] == (
        STANDARD_L_PEPTIDE_RULE_MANIFEST_SCHEMA_ID
    )
    assert contracts["rule_manifest_sha256"] == (
        STANDARD_L_PEPTIDE_RULE_MANIFEST_SHA256
    )
    assert contracts["preparation_inventory_commitment_schema_id"] == (
        MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_PREPARATION_INVENTORY_COMMITMENT_SCHEMA_ID
    )
    assert contracts["positive_case_count"] == 5
    assert contracts["failure_case_count"] == 24
    assert validate_standard_l_peptide_rule_manifest() == (
        STANDARD_L_PEPTIDE_RULE_MANIFEST_SHA256
    )
    assert manifest["limits"] == {
        "input_bytes": 64 * 1024 * 1024,
        "output_bytes": 64 * 1024 * 1024,
        "source_id_utf8_bytes": 4096,
        "token_characters": 2048,
        "atom_rows": 80000,
        "materialized_bonds": 300000,
        "manifest_bytes": _MAX_MANIFEST_BYTES,
        "fixture_bytes": _MAX_FIXTURE_BYTES,
        "total_fixture_bytes": _MAX_TOTAL_FIXTURE_BYTES,
    }


@pytest.mark.parametrize("case_id", _POSITIVE_CASE_IDS)
def test_positive_corpus_case_is_hash_bound_and_exact(case_id: str) -> None:
    manifest = _load_manifest()
    cases = {case["case_id"]: case for case in manifest["positive_cases"]}
    assert tuple(cases) == _POSITIVE_CASE_IDS
    case = cases[case_id]
    assert _CASE_ID.fullmatch(case["case_id"])
    source = _fixture_payload(case["fixture"])
    assert len(source) == case["fixture_byte_count"]
    assert hashlib.sha256(source).hexdigest() == case["fixture_sha256"]
    assert _LOWER_SHA256.fullmatch(case["fixture_sha256"])
    assert _observed_positive(case, source) == case["expected"]

    ingest = parse_mmcif_archive_standard_l_peptide_topology(
        source, source_id=case["source_id"]
    )
    system_marker = ingest.system.metadata["mmcif_archive_standard_l_peptide_topology"]
    assert all(
        system_marker[field] is True
        for field in manifest["contracts"]["bounded_true_fields"]
    )
    assert all(
        system_marker[field] is False
        for field in manifest["contracts"]["false_authority_fields"]
    )


def test_corpus_fixture_budget_and_case_sets_are_exact() -> None:
    manifest = _load_manifest()
    positive = manifest["positive_cases"]
    failure = manifest["failure_cases"]
    assert tuple(case["case_id"] for case in positive) == _POSITIVE_CASE_IDS
    assert len(failure) == 24
    assert len({case["case_id"] for case in failure}) == 24
    assert all(_CASE_ID.fullmatch(case["case_id"]) for case in failure)
    fixture_names = {case["fixture"] for case in (*positive, *failure)}
    total = sum(len(_fixture_payload(name)) for name in fixture_names)
    assert total <= _MAX_TOTAL_FIXTURE_BYTES


@pytest.mark.parametrize(
    ("label", "mutated", "expected_error_code"),
    _negative_cases(GLY_ALA.read_bytes()),
)
def test_failure_corpus_case_is_manifest_bound_and_fail_closed(
    label: str, mutated: bytes, expected_error_code: str
) -> None:
    manifest = _load_manifest()
    cases = {case["mutation_id"]: case for case in manifest["failure_cases"]}
    mutation_id = _failure_mutation_id(label)
    case = cases[mutation_id]
    assert case["fixture"] == "gly_ala_one_asym.cif"
    assert case["expected_error_code"] == expected_error_code
    with pytest.raises(MmcifArchiveStandardLPeptideTopologyError) as exc_info:
        parse_mmcif_archive_standard_l_peptide_topology(
            mutated, source_id=f"corpus-failure:{mutation_id}"
        )
    assert exc_info.value.code == expected_error_code
