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
    mmcif_polymer_component_topology as component_topology,
)
from betelgeuze_engine_v2.molecular.mmcif_polymer_sequence import (
    MMCIF_POLYMER_SEQUENCE_ENVELOPE_VERSION,
    MMCIF_POLYMER_SEQUENCE_PARSER_VERSION,
    MMCIF_POLYMER_SEQUENCE_PROFILE_ID,
    MMCIF_POLYMER_SEQUENCE_WRITER_VERSION,
)
from betelgeuze_engine_v2.molecular.mmcif_writer import MMCIF_WRITER_VERSION
from betelgeuze_engine_v2.molecular.observation import (
    PARSER_OBSERVATION_SCHEMA_ID,
)
from betelgeuze_engine_v2.molecular.pdb_mmcif import MMCIF_PARSER_VERSION
from betelgeuze_engine_v2.molecular.topology import CANONICAL_TOPOLOGY_SCHEMA_ID


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = (
    ROOT
    / "config"
    / "independent_engine_v2_v2_1_mmcif_polymer_component_topology_corpus.json"
)
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "v2_1_mmcif_polymer_component_topology"
CORPUS_SCHEMA_ID = "betelgeuze.v2_1_mmcif_polymer_component_topology_corpus/1.0.0"
CORPUS_ID = "v2_1_strict_mmcif_polymer_component_topology_v1"
PAYLOAD_HASH_POLICY_ID = "sha256_canonical_json_without_payload_sha256/1.0.0"
EXPECTED_PAYLOAD_SHA256 = (
    "6ae0e794e849b66f3d9f98717d3608e29e99852ed4853812692d6b54afea2808"
)

_LOWER_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_CASE_ID = re.compile(r"^[a-z][a-z0-9_]*$")
_MAX_MANIFEST_BYTES = 1024 * 1024
_MAX_FIXTURE_BYTES = 32 * 1024
_MAX_TOTAL_FIXTURE_BYTES = 64 * 1024

_ROUND_TRIP_CASE_IDS = (
    "single_ala_like",
    "single_ala_like_category_order_variant",
    "repeated_ala_xaa_ala",
)
_FAILURE_CASES = {
    "failure_missing_category": "unsupported_category_surface",
    "failure_extra_category": "unsupported_category_surface",
    "failure_scalar_component": "unsupported_category_representation",
    "failure_component_header_order": "unsupported_category_headers",
    "failure_component_type": "unsupported_component_type",
    "failure_atom_stereo": "unsupported_component_atom_stereo",
    "failure_bond_order": "unsupported_component_bond_order",
    "failure_component_definition_join": "component_definition_coverage_mismatch",
    "failure_instance_missing_atom": "component_instance_atom_coverage_mismatch",
    "failure_instance_extra_atom": "component_instance_atom_coverage_mismatch",
    "failure_charge_sum": "component_charge_sum_mismatch",
    "failure_instance_known_charge": "component_atom_charge_mismatch",
    "failure_dangling_bond": "dangling_component_bond",
    "failure_bond_aromaticity": "component_bond_aromatic_mismatch",
    "failure_missing_cartesian_residue": (
        "polymer_cartesian_residue_coverage_mismatch"
    ),
}
_FAILURE_MUTATIONS = {
    "failure_missing_category": "missing_sequence_category",
    "failure_extra_category": "extra_category",
    "failure_scalar_component": "scalar_component_representation",
    "failure_component_header_order": "component_header_order",
    "failure_component_type": "unsupported_component_type",
    "failure_atom_stereo": "unsupported_atom_stereo",
    "failure_bond_order": "unsupported_bond_order",
    "failure_component_definition_join": "component_definition_join",
    "failure_instance_missing_atom": "incomplete_residue_instance",
    "failure_instance_extra_atom": "extra_residue_instance_atom",
    "failure_charge_sum": "component_charge_sum",
    "failure_instance_known_charge": "known_instance_charge",
    "failure_dangling_bond": "dangling_component_bond",
    "failure_bond_aromaticity": "component_bond_aromaticity",
    "failure_missing_cartesian_residue": "missing_cartesian_residue",
}
_FALSE_GATES = (
    "source_authenticated",
    "auth_label_equivalence_inferred",
    "reference_sequence_equivalence_assessed",
    "coordinate_observation_completeness_assessed",
    "modified_residue_identity_assessed",
    "microheterogeneity_interpreted",
    "polymer_sequence_inferred",
    "polymer_sequence_completed",
    "peptide_bonds_inferred",
    "independent_chemistry_established",
    "independent_valence_established",
    "independent_aromaticity_established",
    "independent_stereo_established",
    "chemistry_inferred",
    "chemistry_interpreted",
    "generic_chemistry_supported",
    "struct_conn_interpreted",
    "general_struct_conn_supported",
    "general_struct_conn_interpreted",
    "inter_residue_bonds_interpreted",
    "inter_residue_bonds_supported",
    "cross_component_bonds_interpreted",
    "cross_component_bonds_supported",
    "general_mmcif_topology_complete",
    "role_assignment_interpreted",
    "coordination_interpreted",
    "protonation_interpreted",
    "tautomer_interpreted",
    "missing_residue_fact_claimed",
    "missing_residue_fact_established",
    "sequence_completeness_claimed",
    "sequence_completeness_assessed",
    "preparation_ready",
    "generic_preparation_ready",
    "generic_molecular_preparation_ready",
    "global_preparation_ready",
    "global_molecular_preparation_ready",
    "parameterability_assessed",
    "physics_supported",
    "simulation_ready",
    "runtime_eligible",
    "execution_authorized",
    "claim_safe",
    "general_mmcif_round_trip_evidence_ready",
    "all_format_round_trip_evidence_ready",
    "v2_1_complete",
    "v2_1_promoted",
    "v2_1_common_ingest_promotion_eligible",
)
_EVIDENCE_KEYS = {
    "attached_canonical_topology_digest_self_consistent",
    "attached_parser_observation_digest_self_consistent",
    "augmented_system_parser_observation_sha256",
    "augmented_system_snapshot_sha256",
    "augmented_topology_sha256",
    "canonical_output_sha256",
    "carrier_base_representable_state_sha256",
    "carrier_base_system_snapshot_sha256",
    "carrier_base_topology_sha256",
    "carrier_record_state_sha256",
    "carrier_sequence_projection_sha256",
    "carrier_state_equal",
    "component_atom_row_count",
    "component_bond_row_count",
    "component_count",
    "component_projection_equal",
    "component_projection_sha256",
    "emitted_source_reparsed_exact",
    "full_source_sha256",
    "materialized_atom_count",
    "materialized_bond_count",
    "only_intra_residue_component_bonds_materialized",
    "output_byte_count",
    "output_equals_input",
    "output_source_sha256",
    "parser_observation_schema_id",
    "parser_pedigree_id",
    "peptide_or_inter_residue_bonds_not_inferred",
    "round_trip_report_sha256",
    "second_emission_byte_stable",
    "source_binding_sha256",
    "source_byte_count",
    "source_id_sha256",
    "source_reported_component_topology_materialized",
    "source_reported_component_topology_round_trip_preserved",
    "topology_equal",
    "topology_state_equal",
    "topology_state_sha256",
    "write_receipt_sha256",
}

_SEQUENCE_LOOP = b"""loop_
_entity_poly_seq.entity_id
_entity_poly_seq.num
_entity_poly_seq.mon_id
_entity_poly_seq.hetero
1 1 ALA n
#
"""
_CHEM_COMP_LOOP = b"""loop_
_chem_comp.id
_chem_comp.type
_chem_comp.pdbx_formal_charge
ALA 'L-peptide linking' 0
#
"""
_SCALAR_CHEM_COMP = b"""_chem_comp.id ALA
_chem_comp.type 'L-peptide linking'
_chem_comp.pdbx_formal_charge 0
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
_ALA_CB_ATOM_ROW = (
    b"ATOM 6 C CB . ALA A 1 1 ? 0.000 1.300 0.000 1.00 10.00 ? 1 ALA A CB 1\n"
)
_EXTRA_ALA_ATOM_ROW = (
    b"ATOM 7 H HX . ALA A 1 1 ? 0.000 2.300 0.000 1.00 10.00 ? 1 ALA A HX 1\n"
)
_ALA_N_ATOM_ROW = (
    b"ATOM 1 N N . ALA A 1 1 ? -1.200 0.000 0.000 1.00 10.00 ? 1 ALA A N 1\n"
)
_CHARGED_ALA_N_ATOM_ROW = (
    b"ATOM 1 N N . ALA A 1 1 ? -1.200 0.000 0.000 1.00 10.00 1 1 ALA A N 1\n"
)
_STRUCT_ASYM_LOOP = b"""loop_
_struct_asym.id
_struct_asym.entity_id
A 1
#
"""
_STRUCT_ASYM_MISSING_CARTESIAN_LOOP = b"""loop_
_struct_asym.id
_struct_asym.entity_id
A 1
B 1
#
"""


class PolymerComponentTopologyCorpusError(ValueError):
    pass


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    document: dict[str, Any] = {}
    for key, value in pairs:
        if key in document:
            raise PolymerComponentTopologyCorpusError("duplicate manifest key")
        document[key] = value
    return document


def _parse_bounded_integer(token: str) -> int:
    digits = token[1:] if token.startswith("-") else token
    if len(digits) > 20:
        raise PolymerComponentTopologyCorpusError("JSON integer exceeds corpus bounds")
    return int(token)


def _parse_manifest_json(text: str) -> dict[str, Any]:
    try:
        value = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=lambda _token: (_ for _ in ()).throw(
                PolymerComponentTopologyCorpusError("nonstandard JSON constant")
            ),
            parse_float=lambda _token: (_ for _ in ()).throw(
                PolymerComponentTopologyCorpusError("floating JSON number")
            ),
            parse_int=_parse_bounded_integer,
        )
    except (json.JSONDecodeError, RecursionError) as exc:
        raise PolymerComponentTopologyCorpusError(
            "manifest must be strict JSON"
        ) from exc
    if type(value) is not dict:
        raise PolymerComponentTopologyCorpusError("manifest root must be an object")
    return value


def _load_manifest() -> dict[str, Any]:
    config_root = (ROOT / "config").resolve(strict=True)
    path = MANIFEST.resolve(strict=True)
    if (
        path.parent != config_root
        or path.is_symlink()
        or path.name
        != "independent_engine_v2_v2_1_mmcif_polymer_component_topology_corpus.json"
        or not path.is_file()
        or path.stat().st_size > _MAX_MANIFEST_BYTES
    ):
        raise PolymerComponentTopologyCorpusError(
            "manifest is absent or exceeds its byte cap"
        )
    raw = path.read_bytes()
    if not raw.endswith(b"\n") or raw.endswith(b"\n\n") or b"\r" in raw:
        raise PolymerComponentTopologyCorpusError(
            "manifest must use one final LF and no CR"
        )
    try:
        text = raw.decode("utf-8")
    except UnicodeError as exc:
        raise PolymerComponentTopologyCorpusError("manifest must be UTF-8") from exc
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
        raise PolymerComponentTopologyCorpusError("fixture name must be text")
    pure = PurePosixPath(name)
    if (
        pure.is_absolute()
        or len(pure.parts) != 1
        or pure.suffix != ".cif"
        or pure.name != name
    ):
        raise PolymerComponentTopologyCorpusError(
            "fixture path escapes the exact corpus root"
        )
    fixture_root = FIXTURE_ROOT.resolve(strict=True)
    candidate = FIXTURE_ROOT / pure.name
    if candidate.is_symlink():
        raise PolymerComponentTopologyCorpusError("fixture symlinks are forbidden")
    path = candidate.resolve(strict=True)
    if path.parent != fixture_root or not path.is_file():
        raise PolymerComponentTopologyCorpusError(
            "fixture path is outside the exact corpus root"
        )
    payload = path.read_bytes()
    if len(payload) > _MAX_FIXTURE_BYTES:
        raise PolymerComponentTopologyCorpusError("fixture exceeds its byte cap")
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
    if mutation_id == "scalar_component_representation":
        return _replace_once(source, _CHEM_COMP_LOOP, _SCALAR_CHEM_COMP)
    if mutation_id == "component_header_order":
        return _replace_once(
            source,
            b"_chem_comp.id\n_chem_comp.type\n",
            b"_chem_comp.type\n_chem_comp.id\n",
        )
    if mutation_id == "unsupported_component_type":
        return _replace_once(source, b"'L-peptide linking'", b"'D-peptide linking'")
    if mutation_id == "unsupported_atom_stereo":
        return _replace_once(source, b"ALA CA C 0 N S 3\n", b"ALA CA C 0 N T 3\n")
    if mutation_id == "unsupported_bond_order":
        return _replace_once(source, b"ALA C O DOUB N N 4\n", b"ALA C O QUAD N N 4\n")
    if mutation_id == "incomplete_residue_instance":
        return _replace_once(source, _ALA_CB_ATOM_ROW, b"")
    if mutation_id == "extra_residue_instance_atom":
        return _replace_once(
            source,
            _ALA_CB_ATOM_ROW,
            _ALA_CB_ATOM_ROW + _EXTRA_ALA_ATOM_ROW,
        )
    if mutation_id == "component_definition_join":
        start = source.index(b"loop_\n_chem_comp.id")
        end = source.index(_ATOM_SITE_HEADER)
        definitions = source[start:end]
        if definitions.count(b"ALA ") != 12:
            raise AssertionError("expected exact ALA component-definition rows")
        return source[:start] + definitions.replace(b"ALA ", b"GLY ") + source[end:]
    if mutation_id == "component_charge_sum":
        return _replace_once(
            source,
            b"ALA 'L-peptide linking' 0\n",
            b"ALA 'L-peptide linking' 1\n",
        )
    if mutation_id == "known_instance_charge":
        return _replace_once(source, _ALA_N_ATOM_ROW, _CHARGED_ALA_N_ATOM_ROW)
    if mutation_id == "dangling_component_bond":
        return _replace_once(source, b"ALA C O DOUB N N 4\n", b"ALA C OX DOUB N N 4\n")
    if mutation_id == "component_bond_aromaticity":
        return _replace_once(source, b"ALA C O DOUB N N 4\n", b"ALA C O DOUB Y N 4\n")
    if mutation_id == "missing_cartesian_residue":
        return _replace_once(
            source, _STRUCT_ASYM_LOOP, _STRUCT_ASYM_MISSING_CARTESIAN_LOOP
        )
    raise PolymerComponentTopologyCorpusError("unknown corpus mutation")


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
            "_atom_site",
        ],
        "canonical_component_type": "'L-peptide linking'",
        "carrier_envelope_version": MMCIF_POLYMER_SEQUENCE_ENVELOPE_VERSION,
        "carrier_parser_version": MMCIF_POLYMER_SEQUENCE_PARSER_VERSION,
        "carrier_profile_id": MMCIF_POLYMER_SEQUENCE_PROFILE_ID,
        "carrier_writer_version": MMCIF_POLYMER_SEQUENCE_WRITER_VERSION,
        "chem_comp_atom_headers": list(
            component_topology.MMCIF_POLYMER_COMPONENT_TOPOLOGY_CHEM_COMP_ATOM_HEADERS
        ),
        "chem_comp_bond_headers": list(
            component_topology.MMCIF_POLYMER_COMPONENT_TOPOLOGY_CHEM_COMP_BOND_HEADERS
        ),
        "chem_comp_headers": list(
            component_topology.MMCIF_POLYMER_COMPONENT_TOPOLOGY_CHEM_COMP_HEADERS
        ),
        "envelope_version": (
            component_topology.MMCIF_POLYMER_COMPONENT_TOPOLOGY_ENVELOPE_VERSION
        ),
        "parser_name": (
            component_topology.MMCIF_POLYMER_COMPONENT_TOPOLOGY_PARSER_NAME
        ),
        "parser_pedigree_id": (
            component_topology.MMCIF_POLYMER_COMPONENT_TOPOLOGY_PARSER_PEDIGREE_ID
        ),
        "parser_version": (
            component_topology.MMCIF_POLYMER_COMPONENT_TOPOLOGY_PARSER_VERSION
        ),
        "canonical_topology_schema_id": CANONICAL_TOPOLOGY_SCHEMA_ID,
        "parser_observation_schema_id": PARSER_OBSERVATION_SCHEMA_ID,
        "preparation_inventory_commitment_schema_id": (
            component_topology.MMCIF_POLYMER_COMPONENT_TOPOLOGY_PREPARATION_INVENTORY_COMMITMENT_SCHEMA_ID
        ),
        "profile_id": component_topology.MMCIF_POLYMER_COMPONENT_TOPOLOGY_PROFILE_ID,
        "projection_schema_id": (
            component_topology.MMCIF_POLYMER_COMPONENT_TOPOLOGY_PROJECTION_SCHEMA_ID
        ),
        "round_trip_report_schema_id": (
            component_topology.MMCIF_POLYMER_COMPONENT_TOPOLOGY_ROUND_TRIP_REPORT_SCHEMA_ID
        ),
        "source_binding_schema_id": (
            component_topology.MMCIF_POLYMER_COMPONENT_TOPOLOGY_SOURCE_BINDING_SCHEMA_ID
        ),
        "state_schema_id": (
            component_topology.MMCIF_POLYMER_COMPONENT_TOPOLOGY_STATE_SCHEMA_ID
        ),
        "supported_atom_stereo": ["N", "R", "S"],
        "supported_bond_orders": ["SING", "DOUB", "TRIP", "AROM"],
        "supported_bond_stereo": ["N"],
        "supported_elements": ["H", "C", "N", "O", "S"],
        "write_receipt_schema_id": (
            component_topology.MMCIF_POLYMER_COMPONENT_TOPOLOGY_WRITE_RECEIPT_SCHEMA_ID
        ),
        "writer_version": (
            component_topology.MMCIF_POLYMER_COMPONENT_TOPOLOGY_WRITER_VERSION
        ),
    }


def _expected_limits() -> dict[str, int]:
    return {
        "component_atom_rows": (
            component_topology.MAX_MMCIF_POLYMER_COMPONENT_ATOM_ROWS
        ),
        "component_bond_rows": (
            component_topology.MAX_MMCIF_POLYMER_COMPONENT_BOND_ROWS
        ),
        "component_rows": component_topology.MAX_MMCIF_POLYMER_COMPONENT_ROWS,
        "input_bytes": (
            component_topology.MAX_MMCIF_POLYMER_COMPONENT_TOPOLOGY_INPUT_BYTES
        ),
        "materialized_bonds": (
            component_topology.MAX_MMCIF_POLYMER_COMPONENT_MATERIALIZED_BONDS
        ),
        "output_bytes": (
            component_topology.MAX_MMCIF_POLYMER_COMPONENT_TOPOLOGY_OUTPUT_BYTES
        ),
        "output_line_characters": (
            component_topology.MAX_MMCIF_POLYMER_COMPONENT_TOPOLOGY_OUTPUT_LINE_CHARS
        ),
        "projection_bytes": (
            component_topology.MAX_MMCIF_POLYMER_COMPONENT_TOPOLOGY_PROJECTION_BYTES
        ),
        "sequence_rows": (component_topology.MAX_MMCIF_POLYMER_COMPONENT_SEQUENCE_ROWS),
        "source_id_utf8_bytes": (
            component_topology.MAX_MMCIF_POLYMER_COMPONENT_TOPOLOGY_SOURCE_ID_BYTES
        ),
        "token_characters": (
            component_topology.MAX_MMCIF_POLYMER_COMPONENT_TOPOLOGY_TOKEN_CHARS
        ),
    }


def _replay(
    case: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], Any]:
    _path, source = _fixture_payload(case["fixture"])
    result = component_topology.round_trip_mmcif_polymer_component_topology_source(
        source, source_id=case["source_id"]
    )
    artifacts = result.to_dict()
    ingest = artifacts["source_ingest"]
    receipt = artifacts["write_result"]["receipt"]
    report = artifacts["report"]
    return (
        {
            "attached_canonical_topology_digest_self_consistent": ingest[
                "attached_canonical_topology_digest_self_consistent"
            ],
            "attached_parser_observation_digest_self_consistent": ingest[
                "attached_parser_observation_digest_self_consistent"
            ],
            "augmented_system_parser_observation_sha256": ingest[
                "augmented_system_parser_observation_sha256"
            ],
            "augmented_system_snapshot_sha256": ingest[
                "augmented_system_snapshot_sha256"
            ],
            "augmented_topology_sha256": ingest["augmented_topology_sha256"],
            "canonical_output_sha256": ingest["canonical_output_sha256"],
            "carrier_base_representable_state_sha256": ingest[
                "carrier_base_representable_state_sha256"
            ],
            "carrier_base_system_snapshot_sha256": ingest[
                "carrier_base_system_snapshot_sha256"
            ],
            "carrier_base_topology_sha256": ingest["carrier_base_topology_sha256"],
            "carrier_record_state_sha256": ingest["carrier_record_state_sha256"],
            "carrier_sequence_projection_sha256": ingest[
                "carrier_sequence_projection_sha256"
            ],
            "carrier_state_equal": report["carrier_state_equal"],
            "component_atom_row_count": ingest["component_atom_row_count"],
            "component_bond_row_count": ingest["component_bond_row_count"],
            "component_count": ingest["component_count"],
            "component_projection_equal": report["component_projection_equal"],
            "component_projection_sha256": ingest["component_projection_sha256"],
            "emitted_source_reparsed_exact": report["emitted_source_reparsed_exact"],
            "full_source_sha256": ingest["full_source_sha256"],
            "materialized_atom_count": ingest["materialized_atom_count"],
            "materialized_bond_count": ingest["materialized_bond_count"],
            "only_intra_residue_component_bonds_materialized": ingest[
                "only_intra_residue_component_bonds_materialized"
            ],
            "output_byte_count": receipt["output_byte_count"],
            "output_equals_input": (
                receipt["output_byte_count"] == len(source)
                and receipt["output_source_sha256"]
                == hashlib.sha256(source).hexdigest()
            ),
            "output_source_sha256": receipt["output_source_sha256"],
            "parser_observation_schema_id": ingest["parser_observation_schema_id"],
            "parser_pedigree_id": ingest["parser_pedigree_id"],
            "peptide_or_inter_residue_bonds_not_inferred": ingest[
                "peptide_or_inter_residue_bonds_not_inferred"
            ],
            "round_trip_report_sha256": report["report_sha256"],
            "second_emission_byte_stable": report["second_emission_byte_stable"],
            "source_binding_sha256": ingest["source_binding_sha256"],
            "source_byte_count": len(source),
            "source_id_sha256": ingest["source_id_sha256"],
            "source_reported_component_topology_materialized": ingest[
                "source_reported_component_topology_materialized"
            ],
            "source_reported_component_topology_round_trip_preserved": report[
                "source_reported_component_topology_round_trip_preserved"
            ],
            "topology_equal": report["topology_equal"],
            "topology_state_equal": report["topology_state_equal"],
            "topology_state_sha256": ingest["topology_state_sha256"],
            "write_receipt_sha256": receipt["receipt_sha256"],
        },
        artifacts,
        result,
    )


def _assert_evidence_types(evidence: dict[str, Any]) -> None:
    integer_fields = {
        "component_atom_row_count",
        "component_bond_row_count",
        "component_count",
        "materialized_atom_count",
        "materialized_bond_count",
        "output_byte_count",
        "source_byte_count",
    }
    boolean_fields = {
        "attached_canonical_topology_digest_self_consistent",
        "attached_parser_observation_digest_self_consistent",
        "carrier_state_equal",
        "component_projection_equal",
        "emitted_source_reparsed_exact",
        "only_intra_residue_component_bonds_materialized",
        "output_equals_input",
        "peptide_or_inter_residue_bonds_not_inferred",
        "second_emission_byte_stable",
        "source_reported_component_topology_materialized",
        "source_reported_component_topology_round_trip_preserved",
        "topology_equal",
        "topology_state_equal",
    }
    assert all(type(evidence[field]) is int for field in integer_fields)
    assert all(type(evidence[field]) is bool for field in boolean_fields)
    for key, value in evidence.items():
        if key.endswith("_sha256"):
            assert type(value) is str and _LOWER_SHA256.fullmatch(value)


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
    with pytest.raises(PolymerComponentTopologyCorpusError):
        _parse_manifest_json(payload)


@pytest.mark.parametrize(
    "name",
    (
        str((FIXTURE_ROOT / "single_ala_like.cif").resolve()),
        "../single_ala_like.cif",
        "nested/single_ala_like.cif",
        "./single_ala_like.cif",
        "single_ala_like.cif/",
        "single_ala_like.txt",
    ),
)
def test_fixture_resolver_rejects_paths_outside_exact_corpus(name: str) -> None:
    with pytest.raises(PolymerComponentTopologyCorpusError):
        _fixture_payload(name)


def test_fixture_byte_cap_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(globals(), "_MAX_FIXTURE_BYTES", 1)
    with pytest.raises(PolymerComponentTopologyCorpusError):
        _fixture_payload("single_ala_like.cif")


def test_contract_dependencies_remain_explicit() -> None:
    assert ALL_ATOM_SCHEMA_ID == "betelgeuze.all_atom_system/2.1.0"
    assert MMCIF_PARSER_VERSION == "1.9.0"
    assert MMCIF_WRITER_VERSION == "1.5.0"
    assert CANONICAL_TOPOLOGY_SCHEMA_ID == (
        "betelgeuze.canonical_ordered_topology/1.0.0"
    )
    assert CORPUS_SCHEMA_ID.endswith("/1.0.0")
    assert CORPUS_ID.endswith("_v1")
    assert PAYLOAD_HASH_POLICY_ID.endswith("/1.0.0")


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


def test_manifest_contract_limits_boundaries_and_false_claims_are_exact() -> None:
    document = _load_manifest()
    assert document["contracts"] == _expected_contracts()
    assert document["claim_boundary"] == {
        "bondless_polymer_sequence_carrier_preserved": True,
        "complete_per_residue_template_atom_coverage_required": True,
        "exact_asym_sequence_cartesian_coverage_required": True,
        "final_augmented_digest_bindings_refreshed": True,
        "generic_chemistry_supported": False,
        "generic_molecular_preparation_ready": False,
        "general_mmcif_component_dictionary_supported": False,
        "only_intra_residue_component_bonds_materialized": True,
        "peptide_or_inter_residue_bonds_inferred": False,
        "polymer_only": True,
        "source_reported_component_topology_materialized": True,
        "struct_conn_supported": False,
        "v2_1_complete": False,
    }
    assert document["limits"] == _expected_limits()
    assert document["false_claims"] == {field: False for field in _FALSE_GATES}


def test_fixture_inventory_case_shapes_and_hashes_are_exact() -> None:
    document = _load_manifest()
    fixtures = document["fixtures"]
    assert type(fixtures) is list and len(fixtures) == len(_ROUND_TRIP_CASE_IDS)
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
            "v2_1_mmcif_polymer_component_topology",
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
    assert set(_FAILURE_CASES) == set(_FAILURE_MUTATIONS)
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
            assert case["mutation_id"] == _FAILURE_MUTATIONS[case["case_id"]]
            assert case["expected_error_code"] == _FAILURE_CASES[case["case_id"]]
            assert type(case["source_byte_count"]) is int
            assert type(case["source_sha256"]) is str
            assert _LOWER_SHA256.fullmatch(case["source_sha256"])


def test_manifest_binds_semantic_equivalence_and_repeated_residue_expectations() -> (
    None
):
    cases = {case["case_id"]: case for case in _load_manifest()["cases"]}
    single = cases["single_ala_like"]["expected"]
    variant = cases["single_ala_like_category_order_variant"]["expected"]
    repeated = cases["repeated_ala_xaa_ala"]["expected"]
    for field in (
        "augmented_topology_sha256",
        "canonical_output_sha256",
        "carrier_base_representable_state_sha256",
        "carrier_base_topology_sha256",
        "carrier_record_state_sha256",
        "carrier_sequence_projection_sha256",
        "component_projection_sha256",
        "output_source_sha256",
        "topology_state_sha256",
    ):
        assert single[field] == variant[field]
    for field in ("full_source_sha256", "source_binding_sha256"):
        assert single[field] != variant[field]
    assert single["output_equals_input"] is False
    assert variant["output_equals_input"] is False
    assert repeated["materialized_atom_count"] == 22
    assert repeated["materialized_bond_count"] == 20


@pytest.mark.parametrize("case_id", _ROUND_TRIP_CASE_IDS)
def test_round_trip_cases_replay_all_bound_evidence(case_id: str) -> None:
    case = next(row for row in _load_manifest()["cases"] if row["case_id"] == case_id)
    actual, artifacts, result = _replay(case)
    _assert_evidence_types(actual)
    assert actual == case["expected"]
    for artifact in (
        artifacts["source_ingest"],
        artifacts["write_result"],
        artifacts["write_result"]["receipt"],
        artifacts["reparsed_ingest"],
        artifacts["reemitted_write_result"],
        artifacts["reemitted_write_result"]["receipt"],
        artifacts["report"],
        artifacts,
    ):
        for field in _FALSE_GATES:
            assert artifact[field] is False
    assert (
        artifacts["report"]["emitted_source_sha256"]
        == artifacts["report"]["reemitted_source_sha256"]
    )
    if case_id == "single_ala_like":
        object.__setattr__(result._report, "_document_bytes", b"{}")
        with pytest.raises(
            component_topology.MmcifPolymerComponentTopologyError
        ) as exc:
            result.to_dict()
        assert exc.value.code == "crosswired_round_trip_artifacts"


@pytest.mark.parametrize("case_id", tuple(_FAILURE_CASES))
def test_failure_cases_replay_exact_typed_codes(case_id: str) -> None:
    case = next(row for row in _load_manifest()["cases"] if row["case_id"] == case_id)
    _path, source = _fixture_payload(case["fixture"])
    mutated = _mutate(source, case["mutation_id"])
    assert len(mutated) == case["source_byte_count"]
    assert hashlib.sha256(mutated).hexdigest() == case["source_sha256"]
    with pytest.raises(component_topology.MmcifPolymerComponentTopologyError) as exc:
        component_topology.parse_mmcif_polymer_component_topology(
            mutated, source_id="PRIVATE-AUTH-501"
        )
    assert exc.value.code == case["expected_error_code"]
    assert exc.value.__cause__ is None
    assert "PRIVATE-AUTH-501" not in str(exc.value)


def test_repeated_residue_materialization_is_exact_and_intra_residue_only() -> None:
    _path, source = _fixture_payload("repeated_ala_xaa_ala.cif")
    ingest = component_topology.parse_mmcif_polymer_component_topology(
        source, source_id="repeated_semantics"
    )
    system = ingest.system
    assert system.atom_count == 22
    assert len(system.bonds) == 20
    assert len(system.residues) == 3
    assert [residue.name for residue in system.residues] == ["ALA", "XAA", "ALA"]
    assert all(residue.entity_type == "polymer" for residue in system.residues)
    assert {atom.element for atom in system.atoms} == {"H", "C", "N", "O", "S"}
    assert {atom.stereo for atom in system.atoms} == {"none", "R", "S"}
    assert {bond.order for bond in system.bonds} == {1.0, 1.5, 2.0, 3.0}
    assert any(atom.aromatic for atom in system.atoms)
    assert any(bond.aromatic for bond in system.bonds)
    assert all(bond.stereo == "none" for bond in system.bonds)
    assert all(
        system.atoms[bond.atom_i].residue_index
        == system.atoms[bond.atom_j].residue_index
        for bond in system.bonds
    )
    assert all(
        row.component_type == "L-peptide linking" for row in ingest.component_rows
    )


@pytest.mark.parametrize(
    ("constant", "limit", "source_id", "expected_code"),
    (
        (
            "MAX_MMCIF_POLYMER_COMPONENT_TOPOLOGY_INPUT_BYTES",
            1,
            "",
            "input_too_large",
        ),
        (
            "MAX_MMCIF_POLYMER_COMPONENT_TOPOLOGY_SOURCE_ID_BYTES",
            1,
            "xx",
            "source_id_too_large",
        ),
        (
            "MAX_MMCIF_POLYMER_COMPONENT_TOPOLOGY_TOKEN_CHARS",
            3,
            "",
            "token_too_long",
        ),
        (
            "MAX_MMCIF_POLYMER_COMPONENT_TOPOLOGY_OUTPUT_BYTES",
            1,
            "",
            "output_too_large",
        ),
        (
            "MAX_MMCIF_POLYMER_COMPONENT_TOPOLOGY_PROJECTION_BYTES",
            1,
            "",
            "projection_too_large",
        ),
        (
            "MAX_MMCIF_POLYMER_COMPONENT_MATERIALIZED_BONDS",
            4,
            "",
            "too_many_materialized_bonds",
        ),
    ),
)
def test_generated_resource_limits_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
    constant: str,
    limit: int,
    source_id: str,
    expected_code: str,
) -> None:
    _path, source = _fixture_payload("single_ala_like.cif")
    if constant == "MAX_MMCIF_POLYMER_COMPONENT_TOPOLOGY_TOKEN_CHARS":
        source = _replace_once(source, b"data_single_ala_like", b"data_x")
    monkeypatch.setattr(component_topology, constant, limit)
    with pytest.raises(component_topology.MmcifPolymerComponentTopologyError) as exc:
        component_topology.parse_mmcif_polymer_component_topology(
            source, source_id=source_id
        )
    assert exc.value.code == expected_code
