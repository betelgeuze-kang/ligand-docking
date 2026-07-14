from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from typing import Any

import pytest

from betelgeuze_engine_v2.contracts import ALL_ATOM_SCHEMA_ID
from betelgeuze_engine_v2.molecular.applicability import (
    analyze_canonical_ingest_applicability,
)
from betelgeuze_engine_v2.molecular.mmcif_nonpoly_component_topology import (
    MAX_MMCIF_NONPOLY_COMPONENT_ATOM_ROWS,
    MAX_MMCIF_NONPOLY_COMPONENT_BOND_ROWS,
    MAX_MMCIF_NONPOLY_COMPONENT_ROWS,
    MAX_MMCIF_NONPOLY_COMPONENT_TOPOLOGY_INPUT_BYTES,
    MAX_MMCIF_NONPOLY_COMPONENT_TOPOLOGY_OUTPUT_BYTES,
    MAX_MMCIF_NONPOLY_COMPONENT_TOPOLOGY_OUTPUT_LINE_CHARS,
    MAX_MMCIF_NONPOLY_COMPONENT_TOPOLOGY_PROJECTION_BYTES,
    MAX_MMCIF_NONPOLY_COMPONENT_TOPOLOGY_SOURCE_ID_BYTES,
    MAX_MMCIF_NONPOLY_COMPONENT_TOPOLOGY_TOKEN_CHARS,
    MMCIF_NONPOLY_COMPONENT_TOPOLOGY_CHEM_COMP_ATOM_HEADERS,
    MMCIF_NONPOLY_COMPONENT_TOPOLOGY_CHEM_COMP_BOND_HEADERS,
    MMCIF_NONPOLY_COMPONENT_TOPOLOGY_CHEM_COMP_HEADERS,
    MMCIF_NONPOLY_COMPONENT_TOPOLOGY_ENVELOPE_VERSION,
    MMCIF_NONPOLY_COMPONENT_TOPOLOGY_PARSER_NAME,
    MMCIF_NONPOLY_COMPONENT_TOPOLOGY_PARSER_PEDIGREE_ID,
    MMCIF_NONPOLY_COMPONENT_TOPOLOGY_PARSER_VERSION,
    MMCIF_NONPOLY_COMPONENT_TOPOLOGY_PROFILE_ID,
    MMCIF_NONPOLY_COMPONENT_TOPOLOGY_PROJECTION_SCHEMA_ID,
    MMCIF_NONPOLY_COMPONENT_TOPOLOGY_ROUND_TRIP_REPORT_SCHEMA_ID,
    MMCIF_NONPOLY_COMPONENT_TOPOLOGY_SOURCE_BINDING_SCHEMA_ID,
    MMCIF_NONPOLY_COMPONENT_TOPOLOGY_STATE_SCHEMA_ID,
    MMCIF_NONPOLY_COMPONENT_TOPOLOGY_WRITER_VERSION,
    MMCIF_NONPOLY_COMPONENT_TOPOLOGY_WRITE_RECEIPT_SCHEMA_ID,
    MmcifNonpolyComponentTopologyError,
    parse_mmcif_nonpoly_component_topology,
    round_trip_mmcif_nonpoly_component_topology_source,
)
from betelgeuze_engine_v2.molecular.mmcif_nonpoly_identity import (
    MMCIF_NONPOLY_IDENTITY_ENVELOPE_VERSION,
    MMCIF_NONPOLY_IDENTITY_PARSER_VERSION,
    MMCIF_NONPOLY_IDENTITY_PROFILE_ID,
    MMCIF_NONPOLY_IDENTITY_WRITER_VERSION,
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
    / "independent_engine_v2_v2_1_mmcif_nonpoly_component_topology_corpus.json"
)
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "v2_1_mmcif_nonpoly_component_topology"
CORPUS_SCHEMA_ID = "betelgeuze.v2_1_mmcif_nonpoly_component_topology_corpus/1.0.0"
CORPUS_ID = "v2_1_strict_mmcif_nonpoly_component_topology_envelope_v1"
PAYLOAD_HASH_POLICY_ID = "sha256_canonical_json_without_payload_sha256/1.0.0"
EXPECTED_PAYLOAD_SHA256 = (
    "d8e1ed2173707c74b0101cdaec1bbacb5df7e875f57ec5243905f8e66166e34d"
)

_LOWER_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_CASE_ID = re.compile(r"^[a-z][a-z0-9_]*$")
_MAX_MANIFEST_BYTES = 1024 * 1024
_MAX_FIXTURE_BYTES = 32 * 1024
_MAX_TOTAL_FIXTURE_BYTES = 128 * 1024

_ROUND_TRIP_CASE_IDS = (
    "aromatic_benzene_complete",
    "charged_ammonium_complete",
    "mixed_polymer_methane_complete",
    "single_methane_complete",
    "two_water_instances_complete",
)
_FAILURE_CASES = {
    "failure_unsupported_category": "unsupported_category_surface",
    "failure_header_order": "unsupported_category_headers",
    "failure_duplicate_component_id": "duplicate_component_id",
    "failure_unknown_component_atom": "unknown_component_atom_component",
    "failure_unsupported_element": "unsupported_component_element",
    "failure_atom_aromatic_flag": "invalid_component_atom_aromatic_flag",
    "failure_atom_stereo": "unsupported_component_atom_stereo",
    "failure_atom_ordinal_zero": "invalid_component_atom_ordinal",
    "failure_duplicate_component_atom": "duplicate_component_atom_id",
    "failure_unknown_component_bond": "unknown_component_bond_component",
    "failure_bond_order": "unsupported_component_bond_order",
    "failure_bond_aromatic_mismatch": "component_bond_aromatic_mismatch",
    "failure_bond_stereo": "unsupported_component_bond_stereo",
    "failure_bond_ordinal_zero": "invalid_component_bond_ordinal",
    "failure_self_bond": "self_component_bond",
    "failure_duplicate_bond": "duplicate_component_bond",
    "failure_missing_component_atoms": "missing_component_atoms",
    "failure_atom_ordinals_noncontiguous": ("noncontiguous_component_atom_ordinals"),
    "failure_charge_sum": "component_charge_sum_mismatch",
    "failure_bond_ordinals_noncontiguous": ("noncontiguous_component_bond_ordinals"),
    "failure_dangling_bond": "dangling_component_bond",
    "failure_definition_coverage": "component_definition_coverage_mismatch",
    "failure_instance_missing_atom": "component_instance_atom_coverage_mismatch",
    "failure_instance_element": "component_atom_element_mismatch",
    "failure_instance_charge": "component_atom_charge_mismatch",
}
_FALSE_GATES = (
    "source_authenticated",
    "independent_chemistry_established",
    "independent_valence_established",
    "independent_aromaticity_established",
    "independent_stereo_established",
    "chemistry_inferred",
    "role_assignment_interpreted",
    "coordination_interpreted",
    "struct_conn_interpreted",
    "inter_residue_bonds_interpreted",
    "general_mmcif_topology_complete",
    "protonation_interpreted",
    "preparation_ready",
    "parameterability_assessed",
    "physics_supported",
    "simulation_ready",
    "runtime_eligible",
    "execution_authorized",
    "claim_safe",
    "general_mmcif_round_trip_evidence_ready",
    "all_format_round_trip_evidence_ready",
)
_EVIDENCE_KEYS = {
    "attached_canonical_topology_digest_self_consistent",
    "attached_parser_observation_digest_self_consistent",
    "augmented_system_snapshot_sha256",
    "augmented_system_parser_observation_sha256",
    "augmented_topology_sha256",
    "canonical_ingest_supported",
    "canonical_topology_schema_id",
    "carrier_base_representable_state_sha256",
    "carrier_base_topology_sha256",
    "carrier_identity_projection_sha256",
    "carrier_record_state_sha256",
    "carrier_state_equal",
    "component_atom_row_count",
    "component_bond_row_count",
    "component_count",
    "component_projection_equal",
    "component_projection_sha256",
    "emitted_source_reparsed_exact",
    "full_source_sha256",
    "generic_chemistry_supported",
    "generic_preparation_ready",
    "materialized_atom_count",
    "materialized_bond_count",
    "output_byte_count",
    "output_equals_input",
    "output_source_sha256",
    "parser_observation_schema_id",
    "parser_pedigree_id",
    "profile_local_evidence_satisfied",
    "record_state_sha256",
    "round_trip_report_sha256",
    "second_emission_byte_stable",
    "source_binding_sha256",
    "source_byte_count",
    "source_id_sha256",
    "source_observed_hydrogen_count",
    "source_reported_component_topology_round_trip_preserved",
    "topology_equal",
    "topology_state_equal",
    "topology_state_sha256",
    "write_receipt_sha256",
    "unknown_hydrogen_origin_count",
}


class NonpolyComponentTopologyCorpusError(ValueError):
    pass


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    document: dict[str, Any] = {}
    for key, value in pairs:
        if key in document:
            raise NonpolyComponentTopologyCorpusError("duplicate manifest key")
        document[key] = value
    return document


def _parse_bounded_integer(token: str) -> int:
    digits = token[1:] if token.startswith("-") else token
    if len(digits) > 20:
        raise NonpolyComponentTopologyCorpusError("JSON integer exceeds corpus bounds")
    return int(token)


def _parse_manifest_json(text: str) -> dict[str, Any]:
    try:
        value = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=lambda _token: (_ for _ in ()).throw(
                NonpolyComponentTopologyCorpusError("nonstandard JSON constant")
            ),
            parse_float=lambda _token: (_ for _ in ()).throw(
                NonpolyComponentTopologyCorpusError("floating JSON number")
            ),
            parse_int=_parse_bounded_integer,
        )
    except (json.JSONDecodeError, RecursionError) as exc:
        raise NonpolyComponentTopologyCorpusError(
            "manifest must be strict JSON"
        ) from exc
    if type(value) is not dict:
        raise NonpolyComponentTopologyCorpusError("manifest root must be an object")
    return value


def _load_manifest() -> dict[str, Any]:
    try:
        config_root = (ROOT / "config").resolve(strict=True)
        path = MANIFEST.resolve(strict=True)
        if (
            path.parent != config_root
            or path.name
            != "independent_engine_v2_v2_1_mmcif_nonpoly_component_topology_corpus.json"
            or not path.is_file()
            or path.stat().st_size > _MAX_MANIFEST_BYTES
        ):
            raise NonpolyComponentTopologyCorpusError(
                "manifest is absent or exceeds its byte cap"
            )
        text = path.read_text(encoding="utf-8")
        if len(text.encode("utf-8")) > _MAX_MANIFEST_BYTES:
            raise NonpolyComponentTopologyCorpusError(
                "manifest is absent or exceeds its byte cap"
            )
    except (OSError, UnicodeError) as exc:
        raise NonpolyComponentTopologyCorpusError(
            "manifest must be bounded UTF-8 text"
        ) from exc
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
        raise NonpolyComponentTopologyCorpusError("fixture name must be text")
    pure = PurePosixPath(name)
    if (
        pure.is_absolute()
        or len(pure.parts) != 1
        or pure.suffix != ".cif"
        or pure.name != name
    ):
        raise NonpolyComponentTopologyCorpusError(
            "fixture path escapes the exact corpus root"
        )
    fixture_root = FIXTURE_ROOT.resolve(strict=True)
    try:
        path = (FIXTURE_ROOT / pure.name).resolve(strict=True)
    except OSError as exc:
        raise NonpolyComponentTopologyCorpusError(
            "fixture path is not resolvable"
        ) from exc
    if path.parent != fixture_root or not path.is_file():
        raise NonpolyComponentTopologyCorpusError(
            "fixture path is outside the exact corpus root"
        )
    if path.stat().st_size > _MAX_FIXTURE_BYTES:
        raise NonpolyComponentTopologyCorpusError("fixture exceeds its corpus byte cap")
    payload = path.read_bytes()
    if (
        len(payload) > _MAX_FIXTURE_BYTES
        or len(payload) > MAX_MMCIF_NONPOLY_COMPONENT_TOPOLOGY_INPUT_BYTES
    ):
        raise NonpolyComponentTopologyCorpusError(
            "fixture exceeds its corpus or parser byte cap"
        )
    return path, payload


def _replace_once(source: bytes, old: bytes, new: bytes) -> bytes:
    if not old or source.count(old) != 1:
        raise AssertionError("mutation source must occur exactly once")
    return source.replace(old, new, 1)


def _mutate(source: bytes, mutation_id: str) -> bytes:
    if mutation_id == "unsupported_category":
        return _replace_once(
            source,
            b"loop_\n_atom_site.group_PDB",
            b"_struct_conn.id x\n#\nloop_\n_atom_site.group_PDB",
        )
    if mutation_id == "header_order":
        return _replace_once(
            source,
            b"_chem_comp.id\n_chem_comp.type",
            b"_chem_comp.type\n_chem_comp.id",
        )
    if mutation_id == "duplicate_component_id":
        return _replace_once(
            source,
            b"MET non-polymer 0\n#",
            b"MET non-polymer 0\nMET non-polymer 0\n#",
        )
    if mutation_id == "unknown_component_atom":
        return _replace_once(source, b"MET H4 H 0 N N 5", b"BAD H4 H 0 N N 5")
    if mutation_id == "unsupported_element":
        return _replace_once(source, b"MET H4 H 0 N N 5", b"MET H4 Si 0 N N 5")
    if mutation_id == "atom_aromatic_flag":
        return _replace_once(source, b"MET H4 H 0 N N 5", b"MET H4 H 0 X N 5")
    if mutation_id == "atom_stereo":
        return _replace_once(source, b"MET H4 H 0 N N 5", b"MET H4 H 0 N R 5")
    if mutation_id == "atom_ordinal_zero":
        return _replace_once(source, b"MET C C 0 N N 1", b"MET C C 0 N N 0")
    if mutation_id == "duplicate_component_atom":
        return _replace_once(source, b"MET H4 H 0 N N 5", b"MET H1 H 0 N N 5")
    if mutation_id == "unknown_component_bond":
        return _replace_once(source, b"MET C H4 SING N N 4", b"BAD C H4 SING N N 4")
    if mutation_id == "bond_order":
        return _replace_once(source, b"MET C H4 SING N N 4", b"MET C H4 DELO N N 4")
    if mutation_id == "bond_aromatic_mismatch":
        return _replace_once(source, b"MET C H4 SING N N 4", b"MET C H4 SING Y N 4")
    if mutation_id == "bond_stereo":
        return _replace_once(source, b"MET C H4 SING N N 4", b"MET C H4 SING N E 4")
    if mutation_id == "bond_ordinal_zero":
        return _replace_once(source, b"MET C H1 SING N N 1", b"MET C H1 SING N N 0")
    if mutation_id == "self_bond":
        return _replace_once(source, b"MET C H4 SING N N 4", b"MET C C SING N N 4")
    if mutation_id == "duplicate_bond":
        return _replace_once(source, b"MET C H4 SING N N 4", b"MET C H1 SING N N 4")
    if mutation_id == "missing_component_atoms":
        return _replace_once(
            source,
            b"MET non-polymer 0\n#",
            b"MET non-polymer 0\nEXT non-polymer 0\n#",
        )
    if mutation_id == "atom_ordinals_noncontiguous":
        return _replace_once(source, b"MET H4 H 0 N N 5", b"MET H4 H 0 N N 6")
    if mutation_id == "charge_sum":
        return _replace_once(source, b"MET non-polymer 0\n#", b"MET non-polymer 1\n#")
    if mutation_id == "bond_ordinals_noncontiguous":
        return _replace_once(source, b"MET C H4 SING N N 4", b"MET C H4 SING N N 5")
    if mutation_id == "dangling_bond":
        return _replace_once(source, b"MET C H4 SING N N 4", b"MET C HX SING N N 4")
    if mutation_id == "definition_coverage":
        mutated = _replace_once(
            source,
            b"MET non-polymer 0\n#",
            b"MET non-polymer 0\nEXT non-polymer 0\n#",
        )
        return _replace_once(
            mutated,
            b"MET H4 H 0 N N 5\n#",
            b"MET H4 H 0 N N 5\nEXT X C 0 N N 1\n#",
        )
    if mutation_id == "instance_missing_atom":
        return _replace_once(
            source,
            b"HETATM 5 H H4 . MET L 1 . ? 0.625 -0.625 -0.625 "
            b"1.00 10.00 ? 1 MET L H4 1\n",
            b"",
        )
    if mutation_id == "instance_element":
        return _replace_once(
            source, b"HETATM 5 H H4 . MET L 1", b"HETATM 5 C H4 . MET L 1"
        )
    if mutation_id == "instance_charge":
        return _replace_once(
            source,
            b"HETATM 1 C C . MET L 1 . ? 0.000 0.000 0.000 1.00 10.00 ?",
            b"HETATM 1 C C . MET L 1 . ? 0.000 0.000 0.000 1.00 10.00 1",
        )
    raise NonpolyComponentTopologyCorpusError("unknown corpus mutation")


def _replay(case: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    _path, source = _fixture_payload(case["fixture"])
    result = round_trip_mmcif_nonpoly_component_topology_source(
        source, source_id=case["source_id"]
    )
    artifacts = result.to_dict()
    system = result.source_ingest.system
    preparation = analyze_molecular_preparation(system)
    applicability = analyze_canonical_ingest_applicability(system)
    local = analyze_profile_local_preparation_evidence(system)
    ingest = artifacts["source_ingest"]
    write_result = artifacts["write_result"]
    receipt = write_result["receipt"]
    report = artifacts["report"]
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
            "augmented_system_parser_observation_sha256": ingest[
                "augmented_system_parser_observation_sha256"
            ],
            "augmented_topology_sha256": ingest["augmented_topology_sha256"],
            "canonical_ingest_supported": applicability.canonical_ingest_supported,
            "canonical_topology_schema_id": ingest["canonical_topology_schema_id"],
            "carrier_base_representable_state_sha256": ingest[
                "carrier_base_representable_state_sha256"
            ],
            "carrier_base_topology_sha256": ingest["carrier_base_topology_sha256"],
            "carrier_identity_projection_sha256": ingest[
                "carrier_identity_projection_sha256"
            ],
            "carrier_record_state_sha256": ingest["carrier_record_state_sha256"],
            "carrier_state_equal": report["carrier_state_equal"],
            "component_atom_row_count": ingest["component_atom_row_count"],
            "component_bond_row_count": ingest["component_bond_row_count"],
            "component_count": ingest["component_count"],
            "component_projection_equal": report["component_projection_equal"],
            "component_projection_sha256": ingest["component_projection_sha256"],
            "emitted_source_reparsed_exact": report["emitted_source_reparsed_exact"],
            "full_source_sha256": ingest["full_source_sha256"],
            "generic_chemistry_supported": local.chemistry_report.chemistry_supported,
            "generic_preparation_ready": preparation.preparation_ready,
            "materialized_atom_count": ingest["materialized_atom_count"],
            "materialized_bond_count": ingest["materialized_bond_count"],
            "output_byte_count": receipt["output_byte_count"],
            "output_equals_input": (
                receipt["output_byte_count"] == len(source)
                and receipt["output_source_sha256"]
                == hashlib.sha256(source).hexdigest()
            ),
            "output_source_sha256": receipt["output_source_sha256"],
            "parser_observation_schema_id": ingest["parser_observation_schema_id"],
            "parser_pedigree_id": ingest["parser_pedigree_id"],
            "profile_local_evidence_satisfied": (
                local.profile_local_evidence_satisfied
            ),
            "record_state_sha256": ingest["topology_state_sha256"],
            "round_trip_report_sha256": report["report_sha256"],
            "second_emission_byte_stable": report["second_emission_byte_stable"],
            "source_binding_sha256": ingest["source_binding_sha256"],
            "source_byte_count": len(source),
            "source_id_sha256": ingest["source_id_sha256"],
            "source_observed_hydrogen_count": (
                preparation.metadata_observed_source_hydrogen_count
            ),
            "source_reported_component_topology_round_trip_preserved": report[
                "source_reported_component_topology_round_trip_preserved"
            ],
            "topology_equal": report["topology_equal"],
            "topology_state_equal": report["topology_state_equal"],
            "topology_state_sha256": ingest["topology_state_sha256"],
            "write_receipt_sha256": receipt["receipt_sha256"],
            "unknown_hydrogen_origin_count": (
                preparation.unknown_hydrogen_origin_count
            ),
        },
        artifacts,
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
            "_atom_site",
        ],
        "carrier_envelope_version": MMCIF_NONPOLY_IDENTITY_ENVELOPE_VERSION,
        "carrier_parser_version": MMCIF_NONPOLY_IDENTITY_PARSER_VERSION,
        "carrier_profile_id": MMCIF_NONPOLY_IDENTITY_PROFILE_ID,
        "carrier_writer_version": MMCIF_NONPOLY_IDENTITY_WRITER_VERSION,
        "chem_comp_atom_headers": list(
            MMCIF_NONPOLY_COMPONENT_TOPOLOGY_CHEM_COMP_ATOM_HEADERS
        ),
        "chem_comp_bond_headers": list(
            MMCIF_NONPOLY_COMPONENT_TOPOLOGY_CHEM_COMP_BOND_HEADERS
        ),
        "chem_comp_headers": list(MMCIF_NONPOLY_COMPONENT_TOPOLOGY_CHEM_COMP_HEADERS),
        "envelope_version": MMCIF_NONPOLY_COMPONENT_TOPOLOGY_ENVELOPE_VERSION,
        "parser_name": MMCIF_NONPOLY_COMPONENT_TOPOLOGY_PARSER_NAME,
        "parser_pedigree_id": (MMCIF_NONPOLY_COMPONENT_TOPOLOGY_PARSER_PEDIGREE_ID),
        "parser_version": MMCIF_NONPOLY_COMPONENT_TOPOLOGY_PARSER_VERSION,
        "canonical_topology_schema_id": CANONICAL_TOPOLOGY_SCHEMA_ID,
        "parser_observation_schema_id": PARSER_OBSERVATION_SCHEMA_ID,
        "profile_id": MMCIF_NONPOLY_COMPONENT_TOPOLOGY_PROFILE_ID,
        "projection_schema_id": (MMCIF_NONPOLY_COMPONENT_TOPOLOGY_PROJECTION_SCHEMA_ID),
        "round_trip_report_schema_id": (
            MMCIF_NONPOLY_COMPONENT_TOPOLOGY_ROUND_TRIP_REPORT_SCHEMA_ID
        ),
        "source_binding_schema_id": (
            MMCIF_NONPOLY_COMPONENT_TOPOLOGY_SOURCE_BINDING_SCHEMA_ID
        ),
        "state_schema_id": MMCIF_NONPOLY_COMPONENT_TOPOLOGY_STATE_SCHEMA_ID,
        "supported_bond_orders": ["SING", "DOUB", "TRIP", "AROM"],
        "supported_elements": ["H", "B", "C", "N", "O", "P", "S", "F", "Cl", "Br", "I"],
        "write_receipt_schema_id": (
            MMCIF_NONPOLY_COMPONENT_TOPOLOGY_WRITE_RECEIPT_SCHEMA_ID
        ),
        "writer_version": MMCIF_NONPOLY_COMPONENT_TOPOLOGY_WRITER_VERSION,
    }


def _assert_evidence_types(evidence: dict[str, Any]) -> None:
    integer_fields = {
        "component_atom_row_count",
        "component_bond_row_count",
        "component_count",
        "materialized_atom_count",
        "materialized_bond_count",
        "output_byte_count",
        "source_byte_count",
        "source_observed_hydrogen_count",
        "unknown_hydrogen_origin_count",
    }
    boolean_fields = {
        "attached_canonical_topology_digest_self_consistent",
        "attached_parser_observation_digest_self_consistent",
        "carrier_state_equal",
        "component_projection_equal",
        "emitted_source_reparsed_exact",
        "generic_chemistry_supported",
        "generic_preparation_ready",
        "output_equals_input",
        "second_emission_byte_stable",
        "canonical_ingest_supported",
        "profile_local_evidence_satisfied",
        "source_reported_component_topology_round_trip_preserved",
        "topology_equal",
        "topology_state_equal",
    }
    assert all(type(evidence[field]) is int for field in integer_fields)
    assert all(type(evidence[field]) is bool for field in boolean_fields)
    for key, value in evidence.items():
        if key.endswith("_sha256"):
            assert type(value) is str and _LOWER_SHA256.fullmatch(value)


def test_manifest_payload_hash_and_inventory_are_exact() -> None:
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
    with pytest.raises(NonpolyComponentTopologyCorpusError):
        _parse_manifest_json(payload)


@pytest.mark.parametrize(
    "name",
    (
        str((FIXTURE_ROOT / "single_methane_complete.cif").resolve()),
        "../single_methane_complete.cif",
        "v2_1_mmcif_nonpoly_component_topology/single_methane_complete.cif",
        "./single_methane_complete.cif",
        "single_methane_complete.cif/",
        "single_methane_complete.cif/.",
        "single_methane_complete.txt",
    ),
)
def test_fixture_resolver_rejects_paths_outside_exact_corpus(name: str) -> None:
    with pytest.raises(NonpolyComponentTopologyCorpusError):
        _fixture_payload(name)


def test_manifest_contract_limits_boundaries_and_false_claims_are_exact() -> None:
    document = _load_manifest()
    assert document["contracts"] == _expected_contracts()
    assert document["claim_boundary"] == {
        "bondless_identity_carrier_preserved": True,
        "complete_per_instance_template_atom_coverage_required": True,
        "final_augmented_digest_bindings_refreshed": True,
        "generic_chemistry_supported": False,
        "generic_molecular_preparation_ready": False,
        "general_mmcif_component_dictionary_supported": False,
        "single_methane_existing_hydrocarbon_profile_bridge_ready": True,
        "source_reported_component_topology_materialized": True,
        "struct_conn_supported": False,
        "v2_1_complete": False,
    }
    assert document["limits"] == {
        "component_atom_rows": MAX_MMCIF_NONPOLY_COMPONENT_ATOM_ROWS,
        "component_bond_rows": MAX_MMCIF_NONPOLY_COMPONENT_BOND_ROWS,
        "component_rows": MAX_MMCIF_NONPOLY_COMPONENT_ROWS,
        "input_bytes": MAX_MMCIF_NONPOLY_COMPONENT_TOPOLOGY_INPUT_BYTES,
        "materialized_bonds": MAX_MMCIF_NONPOLY_COMPONENT_BOND_ROWS,
        "output_bytes": MAX_MMCIF_NONPOLY_COMPONENT_TOPOLOGY_OUTPUT_BYTES,
        "output_line_characters": (
            MAX_MMCIF_NONPOLY_COMPONENT_TOPOLOGY_OUTPUT_LINE_CHARS
        ),
        "projection_bytes": MAX_MMCIF_NONPOLY_COMPONENT_TOPOLOGY_PROJECTION_BYTES,
        "source_id_utf8_bytes": (MAX_MMCIF_NONPOLY_COMPONENT_TOPOLOGY_SOURCE_ID_BYTES),
        "token_characters": MAX_MMCIF_NONPOLY_COMPONENT_TOPOLOGY_TOKEN_CHARS,
    }
    assert document["false_claims"] == {field: False for field in _FALSE_GATES}


def test_fixture_inventory_case_shapes_and_hashes_are_exact() -> None:
    document = _load_manifest()
    fixtures = document["fixtures"]
    assert type(fixtures) is list and len(fixtures) == 5
    referenced: set[Path] = set()
    total_bytes = 0
    for fixture in fixtures:
        assert type(fixture) is dict and set(fixture) == {
            "path",
            "byte_count",
            "sha256",
        }
        pure = PurePosixPath(fixture["path"])
        assert pure.parts[:3] == (
            "tests",
            "fixtures",
            "v2_1_mmcif_nonpoly_component_topology",
        )
        assert len(pure.parts) == 4 and ".." not in pure.parts
        path, payload = _fixture_payload(pure.name)
        assert path == ROOT.joinpath(*pure.parts).resolve(strict=True)
        assert len(payload) == fixture["byte_count"]
        assert type(fixture["byte_count"]) is int
        assert type(fixture["sha256"]) is str
        assert hashlib.sha256(payload).hexdigest() == fixture["sha256"]
        assert _LOWER_SHA256.fullmatch(fixture["sha256"])
        referenced.add(path)
        total_bytes += len(payload)
    assert referenced == {path.resolve() for path in FIXTURE_ROOT.glob("*.cif")}
    assert total_bytes <= _MAX_TOTAL_FIXTURE_BYTES

    cases = document["cases"]
    assert type(cases) is list
    assert [case["case_id"] for case in cases] == [
        *_ROUND_TRIP_CASE_IDS,
        *_FAILURE_CASES,
    ]
    assert len(_FAILURE_CASES) >= 18
    for case in cases:
        assert type(case["case_id"]) is str and _CASE_ID.fullmatch(case["case_id"])
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
            assert type(case["source_id"]) is str
            _assert_evidence_types(case["expected"])
        else:
            assert case["kind"] == "failure"
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
            assert type(case["source_byte_count"]) is int
            assert type(case["source_sha256"]) is str
            assert _LOWER_SHA256.fullmatch(case["source_sha256"])


@pytest.mark.parametrize("case_id", _ROUND_TRIP_CASE_IDS)
def test_round_trip_cases_replay_all_bound_evidence(case_id: str) -> None:
    case = next(row for row in _load_manifest()["cases"] if row["case_id"] == case_id)
    actual, artifacts = _replay(case)
    _assert_evidence_types(actual)
    assert actual == case["expected"]
    for artifact in (
        artifacts["source_ingest"],
        artifacts["write_result"],
        artifacts["write_result"]["receipt"],
        artifacts["report"],
        artifacts,
    ):
        for field in _FALSE_GATES:
            assert artifact[field] is False
    assert (
        artifacts["report"]["emitted_source_sha256"]
        == artifacts["report"]["reemitted_source_sha256"]
    )
    assert artifacts["report"]["second_emission_byte_stable"] is True


@pytest.mark.parametrize("case_id", tuple(_FAILURE_CASES))
def test_failure_cases_replay_exact_typed_codes(case_id: str) -> None:
    case = next(row for row in _load_manifest()["cases"] if row["case_id"] == case_id)
    _path, source = _fixture_payload(case["fixture"])
    mutated = _mutate(source, case["mutation_id"])
    assert len(mutated) == case["source_byte_count"]
    assert hashlib.sha256(mutated).hexdigest() == case["source_sha256"]
    with pytest.raises(MmcifNonpolyComponentTopologyError) as exc_info:
        parse_mmcif_nonpoly_component_topology(mutated, source_id="PRIVATE-AUTH-501")
    assert exc_info.value.code == case["expected_error_code"]
    assert exc_info.value.__cause__ is None
    assert "PRIVATE-AUTH-501" not in str(exc_info.value)
