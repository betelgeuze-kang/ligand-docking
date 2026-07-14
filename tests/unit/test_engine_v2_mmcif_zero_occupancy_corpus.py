from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from typing import Any

import pytest

from betelgeuze_engine_v2.molecular.mmcif_nonpoly_identity import (
    MMCIF_NONPOLY_IDENTITY_ENVELOPE_VERSION,
)
from betelgeuze_engine_v2.molecular.mmcif_polymer_sequence import (
    MMCIF_POLYMER_SEQUENCE_ENVELOPE_VERSION,
)
from betelgeuze_engine_v2.molecular.mmcif_writer import MMCIF_WRITER_VERSION
from betelgeuze_engine_v2.molecular.mmcif_zero_occupancy_atoms import (
    MAX_MMCIF_ZERO_OCCUPANCY_ATOM_INPUT_BYTES,
    MAX_MMCIF_ZERO_OCCUPANCY_ATOM_ROWS,
    MAX_MMCIF_ZERO_OCCUPANCY_ATOM_SOURCE_ID_BYTES,
    MAX_MMCIF_ZERO_OCCUPANCY_ATOM_TOKEN_CHARS,
    MMCIF_ZERO_OCCUPANCY_ATOM_ENVELOPE_VERSION,
    MMCIF_ZERO_OCCUPANCY_ATOM_HEADERS,
    MMCIF_ZERO_OCCUPANCY_ATOM_PARSER_VERSION,
    MMCIF_ZERO_OCCUPANCY_ATOM_PROFILE_ID,
    MMCIF_ZERO_OCCUPANCY_ATOM_PROJECTION_SCHEMA_ID,
    MMCIF_ZERO_OCCUPANCY_ATOM_PROJECTION_SCOPE,
    MMCIF_ZERO_OCCUPANCY_ATOM_RECORD_STATE_SCHEMA_ID,
    MMCIF_ZERO_OCCUPANCY_ATOM_ROUND_TRIP_REPORT_SCHEMA_ID,
    MMCIF_ZERO_OCCUPANCY_ATOM_SOURCE_BINDING_SCHEMA_ID,
    MMCIF_ZERO_OCCUPANCY_ATOM_WRITER_VERSION,
    MMCIF_ZERO_OCCUPANCY_ATOM_WRITE_RECEIPT_SCHEMA_ID,
    MmcifZeroOccupancyAtomError,
    parse_mmcif_zero_occupancy_atoms,
    round_trip_mmcif_zero_occupancy_atoms_source,
)
from betelgeuze_engine_v2.molecular.mmcif_zero_occupancy_residues import (
    MAX_MMCIF_ZERO_OCCUPANCY_RESIDUE_INPUT_BYTES,
    MAX_MMCIF_ZERO_OCCUPANCY_RESIDUE_ROWS,
    MAX_MMCIF_ZERO_OCCUPANCY_RESIDUE_SOURCE_ID_BYTES,
    MAX_MMCIF_ZERO_OCCUPANCY_RESIDUE_TOKEN_CHARS,
    MMCIF_ZERO_OCCUPANCY_RESIDUE_ENVELOPE_VERSION,
    MMCIF_ZERO_OCCUPANCY_RESIDUE_HEADERS,
    MMCIF_ZERO_OCCUPANCY_RESIDUE_PARSER_VERSION,
    MMCIF_ZERO_OCCUPANCY_RESIDUE_PROFILE_ID,
    MMCIF_ZERO_OCCUPANCY_RESIDUE_PROJECTION_SCHEMA_ID,
    MMCIF_ZERO_OCCUPANCY_RESIDUE_PROJECTION_SCOPE,
    MMCIF_ZERO_OCCUPANCY_RESIDUE_RECORD_STATE_SCHEMA_ID,
    MMCIF_ZERO_OCCUPANCY_RESIDUE_ROUND_TRIP_REPORT_SCHEMA_ID,
    MMCIF_ZERO_OCCUPANCY_RESIDUE_SOURCE_BINDING_SCHEMA_ID,
    MMCIF_ZERO_OCCUPANCY_RESIDUE_WRITER_VERSION,
    MMCIF_ZERO_OCCUPANCY_RESIDUE_WRITE_RECEIPT_SCHEMA_ID,
    MmcifZeroOccupancyResidueError,
    parse_mmcif_zero_occupancy_residues,
    round_trip_mmcif_zero_occupancy_residues_source,
)
from betelgeuze_engine_v2.molecular.pdb_mmcif import MMCIF_PARSER_VERSION


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = (
    ROOT / "config" / "independent_engine_v2_v2_1_mmcif_zero_occupancy_corpus.json"
)
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "v2_1_mmcif_zero_occupancy"
CORPUS_SCHEMA_ID = "betelgeuze.v2_1_mmcif_zero_occupancy_corpus/1.0.0"
CORPUS_ID = (
    "v2_1_strict_mmcif_source_reported_zero_occupancy_residue_and_atom_envelopes_v1"
)
PAYLOAD_HASH_POLICY_ID = "sha256_canonical_json_without_payload_sha256/1.0.0"
EXPECTED_PAYLOAD_SHA256 = (
    "96564c7b9d4d70eed7ac65188783a6de0acf33a01ac18b7e0559afb28f61ae40"
)

_LOWER_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_CASE_ID = re.compile(r"^[a-z0-9_]+$")
_MAX_MANIFEST_BYTES = 1024 * 1024
_MAX_FIXTURE_BYTES = 16 * 1024
_MAX_TOTAL_FIXTURE_BYTES = 128 * 1024

_ROUND_TRIP_CASE_IDS = (
    "atom_composed_nonpoly",
    "atom_ordered_markers",
    "atom_single_zero",
    "residue_composed_nonpoly",
    "residue_ordered_markers",
    "residue_single_zero",
)
_FAILURE_CASES = {
    "failure_atom_altloc": (
        "atom",
        "unsupported_zero_occupancy_atom_altloc",
    ),
    "failure_atom_atom_absent": (
        "atom",
        "zero_occupancy_atom_atom_absent",
    ),
    "failure_atom_duplicate_identity": (
        "atom",
        "duplicate_zero_occupancy_atom_identity",
    ),
    "failure_atom_mixed_residue_category": (
        "atom",
        "mixed_residue_zero_occupancy_unsupported",
    ),
    "failure_atom_nonzero_occupancy": (
        "atom",
        "zero_occupancy_atom_occupancy_nonzero",
    ),
    "failure_atom_occupancy_flag_one": (
        "atom",
        "unsupported_zero_occupancy_atom_occupancy_flag",
    ),
    "failure_atom_occupancy_unavailable": (
        "atom",
        "zero_occupancy_atom_occupancy_unavailable",
    ),
    "failure_atom_polymer_flag": (
        "atom",
        "unsupported_zero_occupancy_atom_polymer_flag",
    ),
    "failure_atom_residue_absent": (
        "atom",
        "zero_occupancy_atom_residue_absent",
    ),
    "failure_atom_sequence_join": (
        "atom",
        "zero_occupancy_atom_sequence_join_mismatch",
    ),
    "failure_atom_wrong_model": (
        "atom",
        "unsupported_zero_occupancy_atom_model",
    ),
    "failure_residue_absent_coordinate": (
        "residue",
        "zero_occupancy_residue_not_present",
    ),
    "failure_residue_duplicate_identity": (
        "residue",
        "duplicate_zero_occupancy_residue_identity",
    ),
    "failure_residue_mixed_atom_category": (
        "residue",
        "mixed_zero_occupancy_categories_unsupported",
    ),
    "failure_residue_nonzero_occupancy": (
        "residue",
        "zero_occupancy_residue_value_conflict",
    ),
    "failure_residue_occupancy_flag_one": (
        "residue",
        "unsupported_zero_occupancy_residue_occupancy_flag",
    ),
    "failure_residue_polymer_flag": (
        "residue",
        "unsupported_zero_occupancy_residue_polymer_flag",
    ),
    "failure_residue_sequence_join": (
        "residue",
        "zero_occupancy_residue_sequence_join_mismatch",
    ),
    "failure_residue_wrong_model": (
        "residue",
        "unsupported_zero_occupancy_residue_model",
    ),
}

_COMMON_FALSE_GATES = (
    "source_authenticated",
    "auth_label_equivalence_inferred",
    "reference_sequence_equivalence_assessed",
    "coordinate_observation_completeness_assessed",
    "occupancy_population_interpreted",
    "occupancy_weighting_applied",
    "refinement_validity_assessed",
    "altloc_population_interpreted",
    "sequence_completeness_claimed",
    "modified_residue_identity_assessed",
    "polymer_chemistry_interpreted",
    "microheterogeneity_interpreted",
    "chemistry_interpreted",
    "role_assignment_interpreted",
    "bond_topology_interpreted",
    "bond_order_interpreted",
    "coordination_interpreted",
    "charge_interpreted",
    "protonation_interpreted",
    "preparation_ready",
    "parameterability_assessed",
    "physics_supported",
    "runtime_eligible",
    "simulation_ready",
    "execution_authorized",
    "claim_safe",
    "general_mmcif_round_trip_evidence_ready",
    "all_format_round_trip_evidence_ready",
)
_FALSE_GATES = {
    "atom": (
        *_COMMON_FALSE_GATES,
        "missing_atom_fact_claimed",
        "zero_occupancy_atom_fact_claimed",
        "modeled_atom_presence_assessed",
        "residue_template_consulted",
        "atom_name_dictionary_validated",
        "completion_attempted",
        "completion_applied",
    ),
    "residue": (
        *_COMMON_FALSE_GATES,
        "missing_residue_fact_claimed",
        "zero_occupancy_missingness_inferred",
        "modeled_residue_presence_assessed",
    ),
}
_ROW_KEYS = {
    "atom": (
        "source_id",
        "auth_asym_id",
        "auth_comp_id",
        "auth_seq_id",
        "pdb_ins_code",
        "auth_atom_id",
        "label_alt_id",
        "label_asym_id",
        "label_comp_id",
        "label_seq_id",
        "label_atom_id",
        "entity_id",
    ),
    "residue": (
        "source_id",
        "auth_asym_id",
        "auth_comp_id",
        "auth_seq_id",
        "pdb_ins_code",
        "label_asym_id",
        "label_comp_id",
        "label_seq_id",
        "entity_id",
    ),
}
_EXPECTED_KEYS = {
    "base_missing_atom_claim_count",
    "base_missing_residue_claim_count",
    "base_missingness_metadata_sha256",
    "base_zero_occupancy_atom_row_count",
    "base_zero_occupancy_residue_row_count",
    "canonical_carrier_source_sha256",
    "carrier_kind",
    "carrier_source_sha256",
    "full_source_sha256",
    "has_nonpoly_identity",
    "missingness_report_sha256",
    "nonpoly_projection_sha256",
    "nonpoly_record_state_sha256",
    "output_byte_count",
    "output_equals_input",
    "output_source_sha256",
    "polymer_projection_sha256",
    "polymer_record_state_sha256",
    "record_state_sha256",
    "round_trip_report_sha256",
    "rows",
    "second_emission_byte_stable",
    "source_binding_sha256",
    "source_id_sha256",
    "system_snapshot_sha256",
    "topology_sha256",
    "write_receipt_sha256",
    "zero_occupancy_projection_sha256",
    "zero_occupancy_row_count",
}

_RESIDUE_ROW = b"1 Y 0 1 AX GLY AUTH-1 ? A GLY 1"
_RESIDUE_COORDINATE = (
    b"ATOM 1 C CA . GLY A 1 1 ? 0.0 0.0 0.0 0.0 20.0 ? AUTH-1 GLY AX CA 1"
)
_ATOM_ROW = b"1 Y 0 1 AX ALA AUTH-1 ? CB ? A ALA 1 CB"
_ATOM_ZERO_COORDINATE = (
    b"ATOM 2 C CB . ALA A 1 1 ? 1.0 0.0 0.0 0.0 20.0 ? AUTH-1 ALA AX CB 1"
)


class CorpusManifestError(ValueError):
    pass


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    document: dict[str, Any] = {}
    for key, value in pairs:
        if key in document:
            raise CorpusManifestError("duplicate manifest key")
        document[key] = value
    return document


def _parse_manifest_json(text: str) -> dict[str, Any]:
    try:
        document = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=lambda _token: (_ for _ in ()).throw(
                CorpusManifestError("nonstandard JSON constant")
            ),
            parse_float=lambda _token: (_ for _ in ()).throw(
                CorpusManifestError("floating JSON number")
            ),
        )
    except json.JSONDecodeError as exc:
        raise CorpusManifestError("manifest must be strict JSON") from exc
    if type(document) is not dict:
        raise CorpusManifestError("manifest root must be an object")
    return document


def _load_manifest() -> dict[str, Any]:
    try:
        config_root = (ROOT / "config").resolve(strict=True)
        path = MANIFEST.resolve(strict=True)
        if (
            path.parent != config_root
            or path.name
            != "independent_engine_v2_v2_1_mmcif_zero_occupancy_corpus.json"
            or not path.is_file()
            or path.stat().st_size > _MAX_MANIFEST_BYTES
        ):
            raise CorpusManifestError("manifest is absent or exceeds its byte cap")
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise CorpusManifestError("manifest must be bounded UTF-8 text") from exc
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
        raise CorpusManifestError("fixture name must be text")
    pure = PurePosixPath(name)
    if pure.is_absolute() or len(pure.parts) != 1 or pure.suffix != ".cif":
        raise CorpusManifestError("fixture path escapes the exact corpus root")
    fixture_root = FIXTURE_ROOT.resolve(strict=True)
    try:
        path = (FIXTURE_ROOT / pure.name).resolve(strict=True)
    except OSError as exc:
        raise CorpusManifestError("fixture path is not resolvable") from exc
    if path.parent != fixture_root or not path.is_file():
        raise CorpusManifestError("fixture path is outside the exact corpus root")
    if path.stat().st_size > _MAX_FIXTURE_BYTES:
        raise CorpusManifestError("fixture exceeds its corpus byte cap")
    payload = path.read_bytes()
    if len(payload) > max(
        MAX_MMCIF_ZERO_OCCUPANCY_ATOM_INPUT_BYTES,
        MAX_MMCIF_ZERO_OCCUPANCY_RESIDUE_INPUT_BYTES,
    ):
        raise CorpusManifestError("fixture exceeds the parser input byte cap")
    return path, payload


def _replace_once(source: bytes, old: bytes, new: bytes) -> bytes:
    if not old or source.count(old) != 1:
        raise AssertionError("mutation source must occur exactly once")
    return source.replace(old, new, 1)


def _opposite_category_loop(profile_kind: str) -> bytes:
    if profile_kind == "atom":
        return b"""loop_
_pdbx_unobs_or_zero_occ_residues.id
_pdbx_unobs_or_zero_occ_residues.polymer_flag
_pdbx_unobs_or_zero_occ_residues.occupancy_flag
_pdbx_unobs_or_zero_occ_residues.PDB_model_num
_pdbx_unobs_or_zero_occ_residues.auth_asym_id
_pdbx_unobs_or_zero_occ_residues.auth_comp_id
_pdbx_unobs_or_zero_occ_residues.auth_seq_id
_pdbx_unobs_or_zero_occ_residues.PDB_ins_code
_pdbx_unobs_or_zero_occ_residues.label_asym_id
_pdbx_unobs_or_zero_occ_residues.label_comp_id
_pdbx_unobs_or_zero_occ_residues.label_seq_id
9 Y 0 1 AX ALA AUTH-1 ? A ALA 1
#
"""
    return b"""loop_
_pdbx_unobs_or_zero_occ_atoms.id
_pdbx_unobs_or_zero_occ_atoms.polymer_flag
_pdbx_unobs_or_zero_occ_atoms.occupancy_flag
_pdbx_unobs_or_zero_occ_atoms.PDB_model_num
_pdbx_unobs_or_zero_occ_atoms.auth_asym_id
_pdbx_unobs_or_zero_occ_atoms.auth_comp_id
_pdbx_unobs_or_zero_occ_atoms.auth_seq_id
_pdbx_unobs_or_zero_occ_atoms.PDB_ins_code
_pdbx_unobs_or_zero_occ_atoms.auth_atom_id
_pdbx_unobs_or_zero_occ_atoms.label_alt_id
_pdbx_unobs_or_zero_occ_atoms.label_asym_id
_pdbx_unobs_or_zero_occ_atoms.label_comp_id
_pdbx_unobs_or_zero_occ_atoms.label_seq_id
_pdbx_unobs_or_zero_occ_atoms.label_atom_id
9 Y 0 1 AX GLY AUTH-1 ? CA ? A GLY 1 CA
#
"""


def _mutate(source: bytes, mutation_id: str) -> bytes:
    if mutation_id == "atom_altloc":
        return _replace_once(
            source, _ATOM_ROW, b"1 Y 0 1 AX ALA AUTH-1 ? CB A A ALA 1 CB"
        )
    if mutation_id == "atom_absent":
        return _replace_once(
            source, _ATOM_ROW, b"1 Y 0 1 AX ALA AUTH-1 ? CB ? A ALA 1 ZZ"
        )
    if mutation_id == "atom_duplicate_identity":
        return _replace_once(
            source,
            _ATOM_ROW,
            _ATOM_ROW + b"\n2 Y 0 1 AX ALA AUTH-1 . CB . A ALA 1 CB",
        )
    if mutation_id == "atom_mixed_residue_category":
        return _replace_once(
            source,
            b"loop_\n_atom_site.group_PDB",
            _opposite_category_loop("atom") + b"loop_\n_atom_site.group_PDB",
        )
    if mutation_id == "atom_nonzero_occupancy":
        return _replace_once(
            source,
            _ATOM_ZERO_COORDINATE,
            _ATOM_ZERO_COORDINATE.replace(b" 0.0 20.0", b" 1.0 20.0"),
        )
    if mutation_id == "atom_occupancy_flag_one":
        return _replace_once(
            source, _ATOM_ROW, b"1 Y 1 1 AX ALA AUTH-1 ? CB ? A ALA 1 CB"
        )
    if mutation_id == "atom_occupancy_unavailable":
        return _replace_once(
            source,
            _ATOM_ZERO_COORDINATE,
            _ATOM_ZERO_COORDINATE.replace(b" 0.0 20.0", b" ? 20.0"),
        )
    if mutation_id == "atom_polymer_flag":
        return _replace_once(
            source, _ATOM_ROW, b"1 N 0 1 AX ALA AUTH-1 ? CB ? A ALA 1 CB"
        )
    if mutation_id == "atom_residue_absent":
        return _replace_once(
            source, _ATOM_ROW, b"1 Y 0 1 AX ALA AUTH-1 B CB ? A ALA 1 CB"
        )
    if mutation_id == "atom_sequence_join":
        return _replace_once(
            source, _ATOM_ROW, b"1 Y 0 1 AX ALA AUTH-1 ? CB ? A SER 1 CB"
        )
    if mutation_id == "atom_wrong_model":
        return _replace_once(
            source, _ATOM_ROW, b"1 Y 0 2 AX ALA AUTH-1 ? CB ? A ALA 1 CB"
        )
    if mutation_id == "residue_absent_coordinate":
        return _replace_once(
            source,
            _RESIDUE_COORDINATE,
            _RESIDUE_COORDINATE.replace(b" GLY A 1 1 ?", b" GLY A 1 2 ?"),
        )
    if mutation_id == "residue_duplicate_identity":
        return _replace_once(
            source,
            _RESIDUE_ROW,
            _RESIDUE_ROW + b"\n2 Y 0 1 AX GLY AUTH-1 . A GLY 1",
        )
    if mutation_id == "residue_mixed_atom_category":
        return _replace_once(
            source,
            b"loop_\n_atom_site.group_PDB",
            _opposite_category_loop("residue") + b"loop_\n_atom_site.group_PDB",
        )
    if mutation_id == "residue_nonzero_occupancy":
        return _replace_once(
            source,
            _RESIDUE_COORDINATE,
            _RESIDUE_COORDINATE.replace(b" 0.0 20.0", b" 1.0 20.0"),
        )
    if mutation_id == "residue_occupancy_flag_one":
        return _replace_once(source, _RESIDUE_ROW, b"1 Y 1 1 AX GLY AUTH-1 ? A GLY 1")
    if mutation_id == "residue_polymer_flag":
        return _replace_once(source, _RESIDUE_ROW, b"1 N 0 1 AX GLY AUTH-1 ? A GLY 1")
    if mutation_id == "residue_sequence_join":
        return _replace_once(source, _RESIDUE_ROW, b"1 Y 0 1 AX GLY AUTH-1 ? A ALA 1")
    if mutation_id == "residue_wrong_model":
        return _replace_once(source, _RESIDUE_ROW, b"1 Y 0 2 AX GLY AUTH-1 ? A GLY 1")
    raise CorpusManifestError("unknown corpus mutation")


def _row_document(row: Any, profile_kind: str) -> dict[str, Any]:
    return {key: getattr(row, key) for key in _ROW_KEYS[profile_kind]}


def _replay(case: dict[str, Any]) -> tuple[dict[str, Any], Any]:
    _path, source = _fixture_payload(case["fixture"])
    profile_kind = case["profile_kind"]
    if profile_kind == "atom":
        result = round_trip_mmcif_zero_occupancy_atoms_source(
            source, source_id=case["source_id"]
        )
        rows = result.source_ingest.zero_occupancy_atom_rows
        projection_sha256 = result.source_ingest.zero_occupancy_atom_projection_sha256
    else:
        result = round_trip_mmcif_zero_occupancy_residues_source(
            source, source_id=case["source_id"]
        )
        rows = result.source_ingest.zero_occupancy_residue_rows
        projection_sha256 = (
            result.source_ingest.zero_occupancy_residue_projection_sha256
        )
    ingest = result.source_ingest
    receipt = result.write_result.receipt
    receipt_document = receipt.to_dict()
    missingness = ingest.base_ingest.missingness_evidence
    metadata = ingest.base_ingest.system.metadata["mmcif"]["source_missingness"]
    return (
        {
            "base_missing_atom_claim_count": (
                missingness.source_reported_missing_atom_count
            ),
            "base_missing_residue_claim_count": (
                missingness.source_reported_missing_residue_count
            ),
            "base_missingness_metadata_sha256": (
                ingest.base_missingness_metadata_sha256
            ),
            "base_zero_occupancy_atom_row_count": metadata[
                "zero_occupancy_atom_row_count"
            ],
            "base_zero_occupancy_residue_row_count": metadata[
                "zero_occupancy_residue_row_count"
            ],
            "canonical_carrier_source_sha256": (ingest.canonical_carrier_source_sha256),
            "carrier_kind": ingest.carrier_kind,
            "carrier_source_sha256": ingest.carrier_source_sha256,
            "full_source_sha256": ingest.full_source_sha256,
            "has_nonpoly_identity": ingest.has_nonpoly_identity,
            "missingness_report_sha256": ingest.missingness_report_sha256,
            "nonpoly_projection_sha256": ingest.nonpoly_projection_sha256,
            "nonpoly_record_state_sha256": ingest.nonpoly_record_state_sha256,
            "output_byte_count": receipt_document["output_byte_count"],
            "output_equals_input": result.write_result.payload == source,
            "output_source_sha256": receipt.output_source_sha256,
            "polymer_projection_sha256": ingest.polymer_projection_sha256,
            "polymer_record_state_sha256": ingest.polymer_record_state_sha256,
            "record_state_sha256": ingest.record_state_sha256,
            "round_trip_report_sha256": result.report.round_trip_report_sha256,
            "rows": [_row_document(row, profile_kind) for row in rows],
            "second_emission_byte_stable": (result.report.second_emission_byte_stable),
            "source_binding_sha256": ingest.source_binding_sha256,
            "source_id_sha256": ingest.source_id_sha256,
            "system_snapshot_sha256": ingest.system_snapshot_sha256,
            "topology_sha256": ingest.topology_sha256,
            "write_receipt_sha256": receipt.receipt_sha256,
            "zero_occupancy_projection_sha256": projection_sha256,
            "zero_occupancy_row_count": len(rows),
        },
        result,
    )


def _expected_contracts() -> dict[str, Any]:
    common = {
        "base_mmcif_parser_version": MMCIF_PARSER_VERSION,
        "base_mmcif_writer_version": MMCIF_WRITER_VERSION,
        "nonpoly_identity_envelope_version": MMCIF_NONPOLY_IDENTITY_ENVELOPE_VERSION,
        "polymer_sequence_envelope_version": MMCIF_POLYMER_SEQUENCE_ENVELOPE_VERSION,
    }
    return {
        "common": common,
        "atom": {
            "envelope_version": MMCIF_ZERO_OCCUPANCY_ATOM_ENVELOPE_VERSION,
            "headers": list(MMCIF_ZERO_OCCUPANCY_ATOM_HEADERS),
            "parser_version": MMCIF_ZERO_OCCUPANCY_ATOM_PARSER_VERSION,
            "profile_id": MMCIF_ZERO_OCCUPANCY_ATOM_PROFILE_ID,
            "projection_schema_id": MMCIF_ZERO_OCCUPANCY_ATOM_PROJECTION_SCHEMA_ID,
            "projection_scope": MMCIF_ZERO_OCCUPANCY_ATOM_PROJECTION_SCOPE,
            "record_state_schema_id": MMCIF_ZERO_OCCUPANCY_ATOM_RECORD_STATE_SCHEMA_ID,
            "round_trip_report_schema_id": (
                MMCIF_ZERO_OCCUPANCY_ATOM_ROUND_TRIP_REPORT_SCHEMA_ID
            ),
            "source_binding_schema_id": (
                MMCIF_ZERO_OCCUPANCY_ATOM_SOURCE_BINDING_SCHEMA_ID
            ),
            "write_receipt_schema_id": (
                MMCIF_ZERO_OCCUPANCY_ATOM_WRITE_RECEIPT_SCHEMA_ID
            ),
            "writer_version": MMCIF_ZERO_OCCUPANCY_ATOM_WRITER_VERSION,
        },
        "residue": {
            "envelope_version": MMCIF_ZERO_OCCUPANCY_RESIDUE_ENVELOPE_VERSION,
            "headers": list(MMCIF_ZERO_OCCUPANCY_RESIDUE_HEADERS),
            "parser_version": MMCIF_ZERO_OCCUPANCY_RESIDUE_PARSER_VERSION,
            "profile_id": MMCIF_ZERO_OCCUPANCY_RESIDUE_PROFILE_ID,
            "projection_schema_id": (MMCIF_ZERO_OCCUPANCY_RESIDUE_PROJECTION_SCHEMA_ID),
            "projection_scope": MMCIF_ZERO_OCCUPANCY_RESIDUE_PROJECTION_SCOPE,
            "record_state_schema_id": (
                MMCIF_ZERO_OCCUPANCY_RESIDUE_RECORD_STATE_SCHEMA_ID
            ),
            "round_trip_report_schema_id": (
                MMCIF_ZERO_OCCUPANCY_RESIDUE_ROUND_TRIP_REPORT_SCHEMA_ID
            ),
            "source_binding_schema_id": (
                MMCIF_ZERO_OCCUPANCY_RESIDUE_SOURCE_BINDING_SCHEMA_ID
            ),
            "write_receipt_schema_id": (
                MMCIF_ZERO_OCCUPANCY_RESIDUE_WRITE_RECEIPT_SCHEMA_ID
            ),
            "writer_version": MMCIF_ZERO_OCCUPANCY_RESIDUE_WRITER_VERSION,
        },
    }


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
        "[]",
    ),
)
def test_manifest_loader_rejects_noncanonical_json(payload: str) -> None:
    with pytest.raises(CorpusManifestError):
        _parse_manifest_json(payload)


@pytest.mark.parametrize(
    "name",
    (
        str((FIXTURE_ROOT / "atom_single_zero.cif").resolve()),
        "../atom_single_zero.cif",
        "v2_1_mmcif_zero_occupancy/atom_single_zero.cif",
        "atom_single_zero.txt",
    ),
)
def test_fixture_resolver_rejects_paths_outside_exact_corpus(name: str) -> None:
    with pytest.raises(CorpusManifestError):
        _fixture_payload(name)


def test_manifest_contract_limits_boundaries_and_false_claims_are_exact() -> None:
    document = _load_manifest()
    assert document["contracts"] == _expected_contracts()
    assert document["claim_boundary"] == {
        "actual_missing_atom_fact_established": False,
        "actual_missing_residue_fact_established": False,
        "base_missing_claim_counts_required_zero": True,
        "exact_matching_coordinate_occupancy_required_zero": True,
        "occupancy_population_interpreted": False,
        "source_reported_declarations_preserved_only": True,
    }
    assert document["limits"] == {
        "atom": {
            "input_bytes": MAX_MMCIF_ZERO_OCCUPANCY_ATOM_INPUT_BYTES,
            "row_count": MAX_MMCIF_ZERO_OCCUPANCY_ATOM_ROWS,
            "source_id_utf8_bytes": MAX_MMCIF_ZERO_OCCUPANCY_ATOM_SOURCE_ID_BYTES,
            "token_characters": MAX_MMCIF_ZERO_OCCUPANCY_ATOM_TOKEN_CHARS,
        },
        "residue": {
            "input_bytes": MAX_MMCIF_ZERO_OCCUPANCY_RESIDUE_INPUT_BYTES,
            "row_count": MAX_MMCIF_ZERO_OCCUPANCY_RESIDUE_ROWS,
            "source_id_utf8_bytes": (MAX_MMCIF_ZERO_OCCUPANCY_RESIDUE_SOURCE_ID_BYTES),
            "token_characters": MAX_MMCIF_ZERO_OCCUPANCY_RESIDUE_TOKEN_CHARS,
        },
    }
    assert document["false_claims"] == {
        kind: {field: False for field in fields}
        for kind, fields in _FALSE_GATES.items()
    }


def test_fixture_inventory_case_shapes_and_hashes_are_exact() -> None:
    document = _load_manifest()
    fixtures = document["fixtures"]
    assert type(fixtures) is list and len(fixtures) == 6
    referenced: set[Path] = set()
    total_bytes = 0
    for fixture in fixtures:
        assert type(fixture) is dict and set(fixture) == {
            "path",
            "byte_count",
            "sha256",
        }
        pure = PurePosixPath(fixture["path"])
        assert len(pure.parts) == 4
        assert pure.parts[:3] == (
            "tests",
            "fixtures",
            "v2_1_mmcif_zero_occupancy",
        )
        assert ".." not in pure.parts and pure.parts[-1] == pure.name
        path, payload = _fixture_payload(pure.parts[-1])
        assert path == ROOT.joinpath(*pure.parts).resolve(strict=True)
        assert len(payload) == fixture["byte_count"]
        assert hashlib.sha256(payload).hexdigest() == fixture["sha256"]
        assert _LOWER_SHA256.fullmatch(fixture["sha256"])
        referenced.add(path)
        total_bytes += len(payload)
    assert referenced == {path.resolve() for path in FIXTURE_ROOT.glob("*.cif")}
    assert total_bytes <= _MAX_TOTAL_FIXTURE_BYTES

    cases = document["cases"]
    assert type(cases) is list and len(cases) == len(_ROUND_TRIP_CASE_IDS) + len(
        _FAILURE_CASES
    )
    assert [case["case_id"] for case in cases] == [
        *_ROUND_TRIP_CASE_IDS,
        *_FAILURE_CASES,
    ]
    for case in cases:
        assert type(case["case_id"]) is str and _CASE_ID.fullmatch(case["case_id"])
        assert case["profile_kind"] in {"atom", "residue"}
        _fixture_payload(case["fixture"])
        if case["kind"] == "round_trip":
            assert set(case) == {
                "case_id",
                "kind",
                "profile_kind",
                "fixture",
                "source_id",
                "expected",
            }
            assert set(case["expected"]) == _EXPECTED_KEYS
            assert type(case["expected"]["rows"]) is list
            assert all(
                set(row) == set(_ROW_KEYS[case["profile_kind"]])
                for row in case["expected"]["rows"]
            )
            for key, value in case["expected"].items():
                if key.endswith("sha256") and value is not None:
                    assert type(value) is str and _LOWER_SHA256.fullmatch(value)
        else:
            assert case["kind"] == "failure"
            assert set(case) == {
                "case_id",
                "kind",
                "profile_kind",
                "fixture",
                "mutation_id",
                "expected_error_code",
                "source_sha256",
            }
            profile_kind, error_code = _FAILURE_CASES[case["case_id"]]
            assert case["profile_kind"] == profile_kind
            assert case["expected_error_code"] == error_code
            assert type(case["source_sha256"]) is str
            assert _LOWER_SHA256.fullmatch(case["source_sha256"])


@pytest.mark.parametrize("case_id", _ROUND_TRIP_CASE_IDS)
def test_round_trip_cases_replay_all_bound_evidence(case_id: str) -> None:
    case = next(row for row in _load_manifest()["cases"] if row["case_id"] == case_id)
    actual, result = _replay(case)
    assert actual == case["expected"]
    profile_kind = case["profile_kind"]
    preserve_key = (
        "source_reported_zero_occupancy_atom_declarations_preserved"
        if profile_kind == "atom"
        else "source_reported_zero_occupancy_residue_declarations_preserved"
    )
    for artifact in (
        result.source_ingest.to_dict(),
        result.write_result.receipt.to_dict(),
        result.report.to_dict(),
        result.to_dict(),
    ):
        assert artifact[preserve_key] is True
        for field in _FALSE_GATES[profile_kind]:
            assert artifact[field] is False

    ingest = result.source_ingest
    report = ingest.base_ingest.missingness_evidence
    assert report.source_reported_missing_residue_count == 0
    assert report.source_reported_missing_atom_count == 0
    assert not report.missing_residue_claims
    assert not report.missing_atom_claims
    metadata = ingest.base_ingest.system.metadata["mmcif"]["source_missingness"]
    expected_rows = actual["zero_occupancy_row_count"]
    assert metadata["zero_occupancy_atom_row_count"] == (
        expected_rows if profile_kind == "atom" else 0
    )
    assert metadata["zero_occupancy_residue_row_count"] == (
        expected_rows if profile_kind == "residue" else 0
    )
    assert result.write_result.payload == result.reemitted_write_result.payload
    assert result.report.second_emission_byte_stable is True


@pytest.mark.parametrize("case_id", tuple(_FAILURE_CASES))
def test_failure_cases_replay_exact_typed_codes(case_id: str) -> None:
    case = next(row for row in _load_manifest()["cases"] if row["case_id"] == case_id)
    _path, source = _fixture_payload(case["fixture"])
    mutated = _mutate(source, case["mutation_id"])
    assert hashlib.sha256(mutated).hexdigest() == case["source_sha256"]
    if case["profile_kind"] == "atom":
        error_type = MmcifZeroOccupancyAtomError
        parser = parse_mmcif_zero_occupancy_atoms
    else:
        error_type = MmcifZeroOccupancyResidueError
        parser = parse_mmcif_zero_occupancy_residues
    with pytest.raises(error_type) as exc_info:
        parser(mutated, source_id=case_id)
    assert exc_info.value.code == case["expected_error_code"]
    assert exc_info.value.__cause__ is None
    assert "AUTH-1" not in str(exc_info.value)


def test_optional_nonpoly_composition_and_ordered_marker_normalization() -> None:
    cases = {
        row["case_id"]: row["expected"]
        for row in _load_manifest()["cases"]
        if row["kind"] == "round_trip"
    }
    for case_id, expected in cases.items():
        composed = case_id.endswith("composed_nonpoly")
        assert expected["has_nonpoly_identity"] is composed
        assert (
            expected["carrier_kind"] == "mmcif_polymer_sequence_nonpoly_identity"
        ) is composed
        assert (expected["nonpoly_projection_sha256"] is not None) is composed
        assert (expected["nonpoly_record_state_sha256"] is not None) is composed

    for profile_kind in ("atom", "residue"):
        ordered = cases[f"{profile_kind}_ordered_markers"]["rows"]
        assert [row["source_id"] for row in ordered] == [7, 2]
        assert [row["pdb_ins_code"] for row in ordered] == [".", "?"]
    assert [row["label_alt_id"] for row in cases["atom_ordered_markers"]["rows"]] == [
        ".",
        "?",
    ]
