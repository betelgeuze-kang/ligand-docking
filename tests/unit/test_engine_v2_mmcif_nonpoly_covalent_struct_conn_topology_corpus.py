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
    mmcif_nonpoly_covalent_struct_conn_topology as struct_conn_module,
)
from betelgeuze_engine_v2.molecular.applicability import (
    analyze_canonical_ingest_applicability,
)
from betelgeuze_engine_v2.molecular.mmcif_nonpoly_component_topology import (
    MMCIF_NONPOLY_COMPONENT_TOPOLOGY_PROFILE_ID,
)
from betelgeuze_engine_v2.molecular.mmcif_nonpoly_covalent_struct_conn_topology import (
    MAX_MMCIF_NONPOLY_COVALENT_STRUCT_CONN_MATERIALIZED_BONDS,
    MAX_MMCIF_NONPOLY_COVALENT_STRUCT_CONN_ROWS,
    MAX_MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_INPUT_BYTES,
    MAX_MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_OUTPUT_BYTES,
    MAX_MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_OUTPUT_LINE_CHARS,
    MAX_MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_PROJECTION_BYTES,
    MAX_MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_SOURCE_ID_BYTES,
    MAX_MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_TOKEN_CHARS,
    MMCIF_NONPOLY_COVALENT_STRUCT_CONN_HEADERS,
    MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_ENVELOPE_VERSION,
    MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_PARSER_NAME,
    MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_PARSER_PEDIGREE_ID,
    MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_PARSER_VERSION,
    MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_PROFILE_ID,
    MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_PROJECTION_SCHEMA_ID,
    MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_ROUND_TRIP_REPORT_SCHEMA_ID,
    MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_SOURCE_BINDING_SCHEMA_ID,
    MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_STATE_SCHEMA_ID,
    MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_WRITER_VERSION,
    MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_WRITE_RECEIPT_SCHEMA_ID,
    MmcifNonpolyCovalentStructConnTopologyError,
    parse_mmcif_nonpoly_covalent_struct_conn_topology,
    round_trip_mmcif_nonpoly_covalent_struct_conn_topology_source,
)
from betelgeuze_engine_v2.molecular.mmcif_writer import MMCIF_WRITER_VERSION
from betelgeuze_engine_v2.molecular.observation import PARSER_OBSERVATION_SCHEMA_ID
from betelgeuze_engine_v2.molecular.pdb_mmcif import MMCIF_PARSER_VERSION
from betelgeuze_engine_v2.molecular.preparation import analyze_molecular_preparation
from betelgeuze_engine_v2.molecular.profile_preparation import (
    analyze_profile_local_preparation_evidence,
)
from betelgeuze_engine_v2.molecular.topology import CANONICAL_TOPOLOGY_SCHEMA_ID


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = (
    ROOT
    / "config"
    / "independent_engine_v2_v2_1_mmcif_nonpoly_covalent_struct_conn_topology_corpus.json"
)
FIXTURE_ROOT = (
    ROOT / "tests" / "fixtures" / "v2_1_mmcif_nonpoly_covalent_struct_conn_topology"
)
CORPUS_SCHEMA_ID = (
    "betelgeuze.v2_1_mmcif_nonpoly_covalent_struct_conn_topology_corpus/1.0.0"
)
CORPUS_ID = "v2_1_strict_mmcif_nonpoly_covalent_struct_conn_topology_v1"
PAYLOAD_HASH_POLICY_ID = "sha256_canonical_json_without_payload_sha256/1.0.0"
EXPECTED_PAYLOAD_SHA256 = (
    "2a8a2428ff39646f964af01773bc69b3f71cb03cfaba78b7ebb30ef2ba2d2704"
)

_LOWER_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_CASE_ID = re.compile(r"^[a-z][a-z0-9_]*$")
_MAX_MANIFEST_BYTES = 1024 * 1024
_MAX_FIXTURE_BYTES = 32 * 1024
_MAX_TOTAL_FIXTURE_BYTES = 128 * 1024

_ROUND_TRIP_CASE_IDS = (
    "split_ethane_sing",
    "split_formaldehyde_doub",
    "split_hydrogen_cyanide_trip",
)
_FAILURE_CASES = {
    "failure_unsupported_type": "unsupported_struct_conn_type",
    "failure_uppercase_order": "unsupported_struct_conn_bond_order",
    "failure_missing_order": "missing_required_struct_conn_value",
    "failure_quad_order": "unsupported_struct_conn_bond_order",
    "failure_nonidentity_symmetry": "unsupported_partner_symmetry",
    "failure_unknown_label_partner": "unknown_struct_conn_partner",
    "failure_crosswired_auth_partner": "crosswired_struct_conn_partner",
    "failure_self_partner": "self_struct_conn_bond",
    "failure_same_residue_pair": "same_residue_struct_conn_bond",
    "failure_duplicate_pair": "duplicate_struct_conn_bond",
    "failure_reversed_pair": "duplicate_struct_conn_bond",
    "failure_existing_component_bond": "already_materialized_bond",
    "failure_duplicate_id": "duplicate_struct_conn_id",
    "failure_header_order": "unsupported_struct_conn_headers",
    "failure_carrier_component_topology": "carrier_component_topology_rejected",
}
_FALSE_GATES = (
    "source_authenticated",
    "independent_chemistry_established",
    "independent_valence_established",
    "independent_aromaticity_established",
    "independent_stereo_established",
    "chemistry_inferred",
    "struct_conn_interpreted",
    "general_struct_conn_supported",
    "general_struct_conn_interpreted",
    "general_inter_residue_topology_supported",
    "role_assignment_interpreted",
    "coordination_interpreted",
    "protonation_interpreted",
    "preparation_ready",
    "generic_preparation_ready",
    "global_preparation_ready",
    "parameterability_assessed",
    "physics_supported",
    "simulation_ready",
    "runtime_eligible",
    "execution_authorized",
    "claim_safe",
    "general_mmcif_topology_complete",
    "general_mmcif_round_trip_evidence_ready",
    "all_format_round_trip_evidence_ready",
)
_TRUE_GATES = (
    "bounded_source_reported_struct_conn_materialized",
    "bounded_inter_residue_topology_interpreted",
    "source_reported_covalent_struct_conn_materialized",
)
_EVIDENCE_KEYS = {
    "attached_canonical_topology_digest_self_consistent",
    "attached_parser_observation_digest_self_consistent",
    "augmented_system_snapshot_sha256",
    "augmented_topology_sha256",
    "canonical_ingest_supported",
    "carrier_component_projection_sha256",
    "carrier_state_equal",
    "carrier_topology_state_sha256",
    "emitted_source_reparsed_exact",
    "full_source_sha256",
    "generic_preparation_ready",
    "materialized_atom_count",
    "materialized_bond_count",
    "materialized_inter_residue_bond_count",
    "output_byte_count",
    "output_source_sha256",
    "parser_pedigree_id",
    "profile_local_evidence_satisfied",
    "round_trip_report_sha256",
    "second_emission_byte_stable",
    "source_binding_sha256",
    "source_byte_count",
    "source_reported_covalent_struct_conn_round_trip_preserved",
    "struct_conn_projection_equal",
    "struct_conn_projection_sha256",
    "struct_conn_row_count",
    "topology_equal",
    "topology_state_equal",
    "topology_state_sha256",
    "write_receipt_sha256",
}
_MARKER_KEY = "mmcif_nonpoly_covalent_struct_conn_topology"
_MARKER_FIELDS = {
    "connection_id",
    "row_ordinal",
    "conn_type_id",
    "value_order",
    "ptnr1_atom_site_id",
    "ptnr2_atom_site_id",
    "ptnr1_atom_index",
    "ptnr2_atom_index",
    "ptnr1_residue_index",
    "ptnr2_residue_index",
    "ptnr1_symmetry",
    "ptnr2_symmetry",
}
_ETHANE_ROW = (
    b"ethane_cc covale A MTH . C . ? 1_555 B MTH . C . ? A MTH 1 B MTH 2 1_555 sing\n"
)


class StructConnCorpusError(ValueError):
    pass


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    document: dict[str, Any] = {}
    for key, value in pairs:
        if key in document:
            raise StructConnCorpusError("duplicate manifest key")
        document[key] = value
    return document


def _parse_bounded_integer(token: str) -> int:
    digits = token[1:] if token.startswith("-") else token
    if len(digits) > 20:
        raise StructConnCorpusError("JSON integer exceeds corpus bounds")
    return int(token)


def _parse_manifest_json(text: str) -> dict[str, Any]:
    try:
        value = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=lambda _token: (_ for _ in ()).throw(
                StructConnCorpusError("nonstandard JSON constant")
            ),
            parse_float=lambda _token: (_ for _ in ()).throw(
                StructConnCorpusError("floating JSON number")
            ),
            parse_int=_parse_bounded_integer,
        )
    except (json.JSONDecodeError, RecursionError) as exc:
        raise StructConnCorpusError("manifest must be strict JSON") from exc
    if type(value) is not dict:
        raise StructConnCorpusError("manifest root must be an object")
    return value


def _load_manifest() -> dict[str, Any]:
    config_root = (ROOT / "config").resolve(strict=True)
    path = MANIFEST.resolve(strict=True)
    if (
        path.parent != config_root
        or path.is_symlink()
        or not path.is_file()
        or path.stat().st_size > _MAX_MANIFEST_BYTES
    ):
        raise StructConnCorpusError("manifest is absent or exceeds its byte cap")
    raw = path.read_bytes()
    if not raw.endswith(b"\n") or b"\r" in raw:
        raise StructConnCorpusError("manifest must use one final LF and no CR")
    try:
        text = raw.decode("utf-8")
    except UnicodeError as exc:
        raise StructConnCorpusError("manifest must be UTF-8") from exc
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
        raise StructConnCorpusError("fixture name must be text")
    pure = PurePosixPath(name)
    if (
        pure.is_absolute()
        or len(pure.parts) != 1
        or pure.suffix != ".cif"
        or pure.name != name
    ):
        raise StructConnCorpusError("fixture path escapes the exact corpus root")
    fixture_root = FIXTURE_ROOT.resolve(strict=True)
    candidate = FIXTURE_ROOT / pure.name
    if candidate.is_symlink():
        raise StructConnCorpusError("fixture symlinks are forbidden")
    path = candidate.resolve(strict=True)
    if path.parent != fixture_root or not path.is_file():
        raise StructConnCorpusError("fixture path is outside the exact corpus root")
    payload = path.read_bytes()
    if (
        len(payload) > _MAX_FIXTURE_BYTES
        or len(payload) > MAX_MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_INPUT_BYTES
    ):
        raise StructConnCorpusError("fixture exceeds its byte cap")
    return path, payload


def _replace_once(source: bytes, old: bytes, new: bytes) -> bytes:
    if not old or source.count(old) != 1:
        raise AssertionError("mutation source must occur exactly once")
    return source.replace(old, new, 1)


def _mutate(source: bytes, mutation_id: str) -> bytes:
    replacements = {
        "unsupported_type": (b"ethane_cc covale", b"ethane_cc disulf"),
        "uppercase_order": (
            _ETHANE_ROW,
            _ETHANE_ROW.removesuffix(b"sing\n") + b"SING\n",
        ),
        "missing_order": (_ETHANE_ROW, _ETHANE_ROW.removesuffix(b"sing\n") + b"?\n"),
        "quad_order": (_ETHANE_ROW, _ETHANE_ROW.removesuffix(b"sing\n") + b"quad\n"),
        "nonidentity_symmetry": (
            _ETHANE_ROW,
            _ETHANE_ROW.replace(b"? 1_555 B", b"? 2_555 B"),
        ),
        "unknown_label_partner": (
            _ETHANE_ROW,
            b"ethane_cc covale A MTH . C . ? 1_555 Z MTH . X . ? "
            b"A MTH 1 Z MTH 9 1_555 sing\n",
        ),
        "crosswired_auth_partner": (
            _ETHANE_ROW,
            b"ethane_cc covale A MTH . C . ? 1_555 B MTH . C . ? "
            b"A MTH 1 A MTH 1 1_555 sing\n",
        ),
        "self_partner": (
            _ETHANE_ROW,
            b"ethane_cc covale A MTH . C . ? 1_555 A MTH . C . ? "
            b"A MTH 1 A MTH 1 1_555 sing\n",
        ),
        "same_residue_pair": (
            _ETHANE_ROW,
            b"ethane_cc covale A MTH . H1 . ? 1_555 A MTH . H2 . ? "
            b"A MTH 1 A MTH 1 1_555 sing\n",
        ),
        "existing_component_bond": (
            _ETHANE_ROW,
            b"ethane_cc covale A MTH . C . ? 1_555 A MTH . H1 . ? "
            b"A MTH 1 A MTH 1 1_555 sing\n",
        ),
        "header_order": (
            b"_struct_conn.id\n_struct_conn.conn_type_id",
            b"_struct_conn.conn_type_id\n_struct_conn.id",
        ),
        "carrier_component_topology": (
            b"MTH C H3 SING N N 3",
            b"MTH C H3 DELO N N 3",
        ),
    }
    if mutation_id in replacements:
        return _replace_once(source, *replacements[mutation_id])
    if mutation_id == "duplicate_pair":
        second = _ETHANE_ROW.replace(b"ethane_cc ", b"ethane_cc_2 ")
        return _replace_once(
            source, _ETHANE_ROW + b"#\n", _ETHANE_ROW + second + b"#\n"
        )
    if mutation_id == "reversed_pair":
        second = (
            b"ethane_cc_reverse covale B MTH . C . ? 1_555 A MTH . C . ? "
            b"B MTH 2 A MTH 1 1_555 sing\n"
        )
        return _replace_once(
            source, _ETHANE_ROW + b"#\n", _ETHANE_ROW + second + b"#\n"
        )
    if mutation_id == "duplicate_id":
        return _replace_once(
            source, _ETHANE_ROW + b"#\n", _ETHANE_ROW + _ETHANE_ROW + b"#\n"
        )
    raise StructConnCorpusError("unknown corpus mutation")


def _replay(case: dict[str, Any]) -> tuple[dict[str, Any], Any]:
    _path, source = _fixture_payload(case["fixture"])
    result = round_trip_mmcif_nonpoly_covalent_struct_conn_topology_source(
        source, source_id=case["source_id"]
    )
    artifacts = result.to_dict()
    ingest = artifacts["source_ingest"]
    receipt = artifacts["write_result"]["receipt"]
    report = artifacts["report"]
    system = result.source_ingest.system
    preparation = analyze_molecular_preparation(system)
    applicability = analyze_canonical_ingest_applicability(system)
    local = analyze_profile_local_preparation_evidence(system)
    return (
        {
            "attached_canonical_topology_digest_self_consistent": ingest[
                "attached_canonical_topology_digest_self_consistent"
            ],
            "attached_parser_observation_digest_self_consistent": ingest[
                "attached_parser_observation_digest_self_consistent"
            ],
            "augmented_system_snapshot_sha256": ingest[
                "augmented_system_snapshot_sha256"
            ],
            "augmented_topology_sha256": ingest["augmented_topology_sha256"],
            "canonical_ingest_supported": applicability.canonical_ingest_supported,
            "carrier_component_projection_sha256": ingest[
                "carrier_component_projection_sha256"
            ],
            "carrier_state_equal": report["carrier_state_equal"],
            "carrier_topology_state_sha256": ingest["carrier_topology_state_sha256"],
            "emitted_source_reparsed_exact": report["emitted_source_reparsed_exact"],
            "full_source_sha256": ingest["full_source_sha256"],
            "generic_preparation_ready": preparation.preparation_ready,
            "materialized_atom_count": ingest["materialized_atom_count"],
            "materialized_bond_count": ingest["materialized_bond_count"],
            "materialized_inter_residue_bond_count": ingest[
                "materialized_inter_residue_bond_count"
            ],
            "output_byte_count": receipt["output_byte_count"],
            "output_source_sha256": receipt["output_source_sha256"],
            "parser_pedigree_id": ingest["parser_pedigree_id"],
            "profile_local_evidence_satisfied": (
                local.profile_local_evidence_satisfied
            ),
            "round_trip_report_sha256": report["report_sha256"],
            "second_emission_byte_stable": report["second_emission_byte_stable"],
            "source_binding_sha256": ingest["source_binding_sha256"],
            "source_byte_count": len(source),
            "source_reported_covalent_struct_conn_round_trip_preserved": report[
                "source_reported_covalent_struct_conn_round_trip_preserved"
            ],
            "struct_conn_projection_equal": report["struct_conn_projection_equal"],
            "struct_conn_projection_sha256": ingest["struct_conn_projection_sha256"],
            "struct_conn_row_count": ingest["struct_conn_row_count"],
            "topology_equal": report["topology_equal"],
            "topology_state_equal": report["topology_state_equal"],
            "topology_state_sha256": ingest["topology_state_sha256"],
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
            "_chem_comp",
            "_chem_comp_atom",
            "_chem_comp_bond",
            "_pdbx_entity_nonpoly",
            "_pdbx_nonpoly_scheme",
            "_struct_conn",
            "_atom_site",
        ],
        "canonical_topology_schema_id": CANONICAL_TOPOLOGY_SCHEMA_ID,
        "carrier_profile_id": MMCIF_NONPOLY_COMPONENT_TOPOLOGY_PROFILE_ID,
        "envelope_version": MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_ENVELOPE_VERSION,
        "parser_name": MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_PARSER_NAME,
        "parser_observation_schema_id": PARSER_OBSERVATION_SCHEMA_ID,
        "parser_pedigree_id": (
            MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_PARSER_PEDIGREE_ID
        ),
        "parser_version": MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_PARSER_VERSION,
        "profile_id": MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_PROFILE_ID,
        "projection_schema_id": (
            MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_PROJECTION_SCHEMA_ID
        ),
        "round_trip_report_schema_id": (
            MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_ROUND_TRIP_REPORT_SCHEMA_ID
        ),
        "source_binding_schema_id": (
            MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_SOURCE_BINDING_SCHEMA_ID
        ),
        "state_schema_id": MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_STATE_SCHEMA_ID,
        "struct_conn_headers": list(MMCIF_NONPOLY_COVALENT_STRUCT_CONN_HEADERS),
        "supported_conn_type_ids": ["covale"],
        "supported_identity_symmetry": "1_555",
        "supported_value_orders": ["sing", "doub", "trip"],
        "write_receipt_schema_id": (
            MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_WRITE_RECEIPT_SCHEMA_ID
        ),
        "writer_version": MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_WRITER_VERSION,
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
        "component_topology_carrier_required": True,
        "combined_label_auth_partner_join_required": True,
        "explicit_covale_sing_doub_trip_only": True,
        "generic_molecular_preparation_ready": False,
        "general_struct_conn_supported": False,
        "identity_symmetry_only": True,
        "source_reported_covalent_struct_conn_materialized": True,
        "split_ethane_existing_hydrocarbon_profile_bridge_ready": True,
        "v2_1_complete": False,
    }
    assert document["limits"] == {
        "input_bytes": MAX_MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_INPUT_BYTES,
        "materialized_bonds": (
            MAX_MMCIF_NONPOLY_COVALENT_STRUCT_CONN_MATERIALIZED_BONDS
        ),
        "output_bytes": MAX_MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_OUTPUT_BYTES,
        "output_line_characters": (
            MAX_MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_OUTPUT_LINE_CHARS
        ),
        "projection_bytes": (
            MAX_MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_PROJECTION_BYTES
        ),
        "source_id_utf8_bytes": (
            MAX_MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_SOURCE_ID_BYTES
        ),
        "struct_conn_rows": MAX_MMCIF_NONPOLY_COVALENT_STRUCT_CONN_ROWS,
        "token_characters": MAX_MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_TOKEN_CHARS,
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
    with pytest.raises(StructConnCorpusError):
        _parse_manifest_json(payload)


@pytest.mark.parametrize(
    "name",
    (
        str((FIXTURE_ROOT / "split_ethane_sing.cif").resolve()),
        "../split_ethane_sing.cif",
        "nested/split_ethane_sing.cif",
        "./split_ethane_sing.cif",
        "split_ethane_sing.cif/",
        "split_ethane_sing.txt",
    ),
)
def test_fixture_resolver_rejects_paths_outside_exact_corpus(name: str) -> None:
    with pytest.raises(StructConnCorpusError):
        _fixture_payload(name)


def test_fixture_inventory_case_shapes_and_hashes_are_exact() -> None:
    document = _load_manifest()
    referenced: set[Path] = set()
    total_bytes = 0
    for fixture in document["fixtures"]:
        assert set(fixture) == {"path", "byte_count", "sha256"}
        pure = PurePosixPath(fixture["path"])
        assert pure.parts[:3] == (
            "tests",
            "fixtures",
            "v2_1_mmcif_nonpoly_covalent_struct_conn_topology",
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
        artifacts["write_result"]["receipt"],
        artifacts["report"],
        artifacts,
    ):
        assert all(artifact[field] is False for field in _FALSE_GATES)
        assert all(artifact[field] is True for field in _TRUE_GATES)

    struct_conn_bonds = [
        bond
        for bond in result.source_ingest.system.bonds
        if bond.source == "mmcif_struct_conn_covale"
    ]
    assert len(struct_conn_bonds) == 1
    bond = struct_conn_bonds[0]
    assert bond.atom_i < bond.atom_j
    assert bond.aromatic is False and bond.stereo == "none"
    assert set(bond.metadata) == {_MARKER_KEY}
    assert set(bond.metadata[_MARKER_KEY]) == _MARKER_FIELDS
    assert result.write_result.payload == result.reemitted_write_result.payload


@pytest.mark.parametrize("case_id", tuple(_FAILURE_CASES))
def test_failure_cases_replay_exact_typed_codes(case_id: str) -> None:
    case = next(row for row in _load_manifest()["cases"] if row["case_id"] == case_id)
    _path, source = _fixture_payload(case["fixture"])
    mutated = _mutate(source, case["mutation_id"])
    assert len(mutated) == case["source_byte_count"]
    assert hashlib.sha256(mutated).hexdigest() == case["source_sha256"]
    with pytest.raises(MmcifNonpolyCovalentStructConnTopologyError) as exc_info:
        parse_mmcif_nonpoly_covalent_struct_conn_topology(
            mutated, source_id="PRIVATE-AUTH-501"
        )
    assert exc_info.value.code == case["expected_error_code"]
    assert exc_info.value.__cause__ is None
    assert "PRIVATE-AUTH-501" not in str(exc_info.value)


@pytest.mark.parametrize(
    ("constant", "error_code"),
    (
        (
            "MAX_MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_INPUT_BYTES",
            "input_too_large",
        ),
        ("MAX_MMCIF_NONPOLY_COVALENT_STRUCT_CONN_ROWS", "too_many_struct_conn_rows"),
        (
            "MAX_MMCIF_NONPOLY_COVALENT_STRUCT_CONN_MATERIALIZED_BONDS",
            "too_many_materialized_bonds",
        ),
        (
            "MAX_MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_OUTPUT_BYTES",
            "output_too_large",
        ),
        (
            "MAX_MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_PROJECTION_BYTES",
            "projection_too_large",
        ),
    ),
)
def test_live_parser_limits_fail_closed(
    constant: str, error_code: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    _path, source = _fixture_payload("split_ethane_sing.cif")
    if constant.endswith("INPUT_BYTES"):
        value = len(source) - 1
    elif constant.endswith("ROWS"):
        value = 0
    elif constant.endswith("MATERIALIZED_BONDS"):
        value = 6
    else:
        value = 1
    monkeypatch.setattr(struct_conn_module, constant, value)
    with pytest.raises(MmcifNonpolyCovalentStructConnTopologyError) as exc_info:
        parse_mmcif_nonpoly_covalent_struct_conn_topology(source)
    assert exc_info.value.code == error_code


def test_source_id_limit_and_artifact_crosswire_fail_closed() -> None:
    _path, ethane = _fixture_payload("split_ethane_sing.cif")
    _path, formaldehyde = _fixture_payload("split_formaldehyde_doub.cif")
    with pytest.raises(MmcifNonpolyCovalentStructConnTopologyError) as exc_info:
        parse_mmcif_nonpoly_covalent_struct_conn_topology(
            ethane,
            source_id="x"
            * (MAX_MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_SOURCE_ID_BYTES + 1),
        )
    assert exc_info.value.code == "source_id_too_long"

    first = round_trip_mmcif_nonpoly_covalent_struct_conn_topology_source(ethane)
    second = round_trip_mmcif_nonpoly_covalent_struct_conn_topology_source(formaldehyde)
    object.__setattr__(first, "_write_result", second.write_result)
    with pytest.raises(MmcifNonpolyCovalentStructConnTopologyError) as exc_info:
        first.to_dict()
    assert exc_info.value.code == "crosswired_round_trip_artifacts"
