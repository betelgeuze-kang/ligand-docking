"""Deterministic writer for the exactly representable strict mmCIF subset.

This is deliberately not a general mmCIF exporter.  It accepts selected
single-model, model-ID-1 state produced by the current strict mmCIF reader.
The six legacy profiles remain ``_atom_site``-only.  The exact core-11 profile
may independently add an appended ``_atom_site.pdbx_formal_charge`` or
``_atom_site.pdbx_PDB_ins_code`` field, add both in that fixed order, or add an
appended uncertainty-free ``_atom_site.occupancy`` field by itself.  The exact
core-11 profile may also append the ordered pair ``_atom_site.occupancy`` then
``_atom_site.B_iso_or_equiv``.  The common-core21 profile instead requires exact
two-column ``_entity`` and ``_struct_asym`` loops plus the official-order 21-column
``_atom_site`` identity/measurement surface.  It preserves complete auth
aliases while canonical identity remains label-owned.  Other atom-site fields
and combinations, other category state,
alternate-location selection, assembly expansion, missingness evidence, unit
cells, and bonds fail closed.

Round-trip equality is a versioned, source-independent representable-state
projection.  Raw coordinate spelling, source layout, dynamic provenance,
resource usage, parser-observation digests, system identifiers, and the full
canonical snapshot are receipt-bound but are not equality claims.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
import hashlib
import json
import math
import re
import struct
from typing import Any, Mapping

import torch

from betelgeuze_engine_v2.contracts import ALL_ATOM_SCHEMA_ID

from .missingness import (
    MAX_MISSING_ATOM_CLAIMS,
    MAX_MISSING_RESIDUE_CLAIMS,
    MAX_TOTAL_MISSINGNESS_CLAIMS,
    MISSINGNESS_PRESERVATION_POLICY_ID,
    MISSINGNESS_REPORT_SCHEMA_ID,
    SourceReportedMissingnessReport,
    build_source_reported_missingness_report,
)
from .models import (
    AllAtomSystem,
    atomic_number_for_element,
    canonical_element_symbol,
)
from .mmcif_syntax import CifSyntaxError, parse_cif_block
from .observation import (
    PARSER_OBSERVATION_SCHEMA_ID,
    attached_parser_observation_sha256_matches,
)
from .pdb_mmcif import (
    MMCIF_PARSER_VERSION,
    STRUCTURE_INGEST_SUPPORT_SCOPE,
    StructureIngestCoverage,
    StructureIngestResult,
    parse_mmcif,
)
from .serialization import (
    canonical_all_atom_snapshot_digest,
    deserialize_all_atom_system,
    serialize_all_atom_system,
)
from .topology import (
    CANONICAL_TOPOLOGY_SCHEMA_ID,
    attached_canonical_topology_sha256_matches,
    canonical_topology_sha256,
)
from .validation import MolecularValidationError, require_valid_all_atom_system


MMCIF_WRITER_VERSION = "1.5.0"
MMCIF_REPRESENTABLE_STATE_SCHEMA_ID = "betelgeuze.mmcif_representable_state/1.5.0"
MMCIF_WRITE_RECEIPT_SCHEMA_ID = "betelgeuze.mmcif_write_receipt/1.5.0"
MMCIF_ROUND_TRIP_REPORT_SCHEMA_ID = "betelgeuze.mmcif_round_trip_report/1.5.0"
MMCIF_LABEL_AUTH_ENTITY_IDENTITY_PROJECTION_SCHEMA_ID = (
    "betelgeuze.mmcif_label_auth_entity_identity_projection/1.0.0"
)

_MMCIF_PARSER_NAME = "betelgeuze_engine_v2.molecular.pdb_mmcif.parse_mmcif"
_MAX_OUTPUT_BYTES = 64 * 1024 * 1024
_MAX_ATOM_ROWS = 80_000
_MAX_ENTITY_ROWS = 4_096
_MAX_STRUCT_ASYM_ROWS = 16_384
_MAX_OUTPUT_LINES = 250_000
_MAX_LINE_CHARS = 2_048
_MAX_TOKEN_COUNT = 2_000_000
_MAX_DATA_BLOCK_CHARS = 75
_MAX_ABS_FORMAL_CHARGE = 32_767
_MAX_MISSINGNESS_TOKEN_CHARS = 4_096
_MAX_MISSINGNESS_PRESERVED_ITEMS = 40_000
_MAX_MISSINGNESS_PRESERVED_UTF8_BYTES = 12 * 1024 * 1024
_MAX_ASSEMBLY_DEFINITION_ROWS = 1_024
_MAX_ASSEMBLY_GENERATOR_ROWS = 1_024
_MAX_ASSEMBLY_OPERATOR_ROWS = 4_096
_MAX_ASSEMBLY_OPER_EXPRESSION_CHARS = 4_096
_MAX_ASSEMBLY_ASYM_ID_LIST_CHARS = 4_096
_MAX_ASSEMBLY_ASYM_IDS_PER_GENERATOR = 4_096
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_INTEGER_RE = re.compile(r"^[+-]?\d+$")
_CIF_NUMBER_RE = re.compile(
    r"^(?P<mantissa>[+-]?(?:\d+(?:\.\d*)?|\.\d+))"
    r"(?P<exponent>[eE][+-]?\d+)?$"
)
_DATA_BLOCK_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.+\-]*$")

_CORE_ATOM_SITE_HEADERS = (
    "_atom_site.group_pdb",
    "_atom_site.id",
    "_atom_site.type_symbol",
    "_atom_site.label_atom_id",
    "_atom_site.label_comp_id",
    "_atom_site.label_asym_id",
    "_atom_site.label_seq_id",
    "_atom_site.cartn_x",
    "_atom_site.cartn_y",
    "_atom_site.cartn_z",
    "_atom_site.pdbx_pdb_model_num",
)
_FORMAL_CHARGE_HEADER = "_atom_site.pdbx_formal_charge"
_INSERTION_CODE_HEADER = "_atom_site.pdbx_pdb_ins_code"
_OCCUPANCY_HEADER = "_atom_site.occupancy"
_B_FACTOR_HEADER = "_atom_site.b_iso_or_equiv"
_LABEL_ALT_ID_HEADER = "_atom_site.label_alt_id"
_LABEL_ENTITY_ID_HEADER = "_atom_site.label_entity_id"
_AUTH_SEQ_ID_HEADER = "_atom_site.auth_seq_id"
_AUTH_COMP_ID_HEADER = "_atom_site.auth_comp_id"
_AUTH_ASYM_ID_HEADER = "_atom_site.auth_asym_id"
_AUTH_ATOM_ID_HEADER = "_atom_site.auth_atom_id"
_FORMAL_CHARGE_ATOM_SITE_HEADERS = (*_CORE_ATOM_SITE_HEADERS, _FORMAL_CHARGE_HEADER)
_INSERTION_CODE_ATOM_SITE_HEADERS = (*_CORE_ATOM_SITE_HEADERS, _INSERTION_CODE_HEADER)
_OCCUPANCY_ATOM_SITE_HEADERS = (*_CORE_ATOM_SITE_HEADERS, _OCCUPANCY_HEADER)
_OCCUPANCY_B_FACTOR_ATOM_SITE_HEADERS = (
    *_CORE_ATOM_SITE_HEADERS,
    _OCCUPANCY_HEADER,
    _B_FACTOR_HEADER,
)
_FORMAL_CHARGE_INSERTION_CODE_ATOM_SITE_HEADERS = (
    *_CORE_ATOM_SITE_HEADERS,
    _FORMAL_CHARGE_HEADER,
    _INSERTION_CODE_HEADER,
)
_COMMON_CORE21_ATOM_SITE_HEADERS = (
    "_atom_site.group_pdb",
    "_atom_site.id",
    "_atom_site.type_symbol",
    "_atom_site.label_atom_id",
    _LABEL_ALT_ID_HEADER,
    "_atom_site.label_comp_id",
    "_atom_site.label_asym_id",
    _LABEL_ENTITY_ID_HEADER,
    "_atom_site.label_seq_id",
    _INSERTION_CODE_HEADER,
    "_atom_site.cartn_x",
    "_atom_site.cartn_y",
    "_atom_site.cartn_z",
    _OCCUPANCY_HEADER,
    _B_FACTOR_HEADER,
    _FORMAL_CHARGE_HEADER,
    _AUTH_SEQ_ID_HEADER,
    _AUTH_COMP_ID_HEADER,
    _AUTH_ASYM_ID_HEADER,
    _AUTH_ATOM_ID_HEADER,
    "_atom_site.pdbx_pdb_model_num",
)
_CORE11_ATOM_SITE_PROFILE = "core11"
_CORE12_FORMAL_CHARGE_ATOM_SITE_PROFILE = "core12_pdbx_formal_charge"
_CORE12_INSERTION_CODE_ATOM_SITE_PROFILE = "core12_pdbx_pdb_ins_code"
_CORE12_OCCUPANCY_ATOM_SITE_PROFILE = "core12_occupancy"
_CORE13_OCCUPANCY_B_FACTOR_ATOM_SITE_PROFILE = "core13_occupancy_b_iso_or_equiv"
_CORE13_FORMAL_CHARGE_INSERTION_CODE_ATOM_SITE_PROFILE = (
    "core13_pdbx_formal_charge_pdbx_pdb_ins_code"
)
_COMMON_CORE21_IDENTITY_PROFILE = (
    "pdbx_common_core21_complete_label_auth_entity_identity/1.0.0"
)
_ATOM_SITE_ONLY_CATEGORY_PROFILE = "atom_site_only/1.0.0"
_COMMON_THREE_LOOP_CATEGORY_PROFILE = (
    "exact_entity_struct_asym_atom_site_three_loop_categories/1.0.0"
)
_NO_AUTH_ENTITY_IDENTITY_PROFILE = (
    "label_identity_without_auth_or_entity_categories/1.0.0"
)
_ENTITY_HEADERS = ("_entity.id", "_entity.type")
_STRUCT_ASYM_HEADERS = ("_struct_asym.id", "_struct_asym.entity_id")
_SUPPORTED_COMMON_ENTITY_TYPES = {
    "polymer": "polymer",
    "non-polymer": "non_polymer",
    "water": "water",
}
_OCCUPANCY_VALUE_PROFILE_ID = (
    "bare_dot_question_or_uncertainty_free_finite_binary64_zero_to_one/1.0.0"
)
_B_FACTOR_VALUE_PROFILE_ID = (
    "bare_dot_question_or_uncertainty_free_finite_binary64/1.0.0"
)
_ATOM_SITE_HEADERS_BY_PROFILE = {
    _CORE11_ATOM_SITE_PROFILE: _CORE_ATOM_SITE_HEADERS,
    _CORE12_FORMAL_CHARGE_ATOM_SITE_PROFILE: _FORMAL_CHARGE_ATOM_SITE_HEADERS,
    _CORE12_INSERTION_CODE_ATOM_SITE_PROFILE: _INSERTION_CODE_ATOM_SITE_HEADERS,
    _CORE12_OCCUPANCY_ATOM_SITE_PROFILE: _OCCUPANCY_ATOM_SITE_HEADERS,
    _CORE13_OCCUPANCY_B_FACTOR_ATOM_SITE_PROFILE: (
        _OCCUPANCY_B_FACTOR_ATOM_SITE_HEADERS
    ),
    _CORE13_FORMAL_CHARGE_INSERTION_CODE_ATOM_SITE_PROFILE: (
        _FORMAL_CHARGE_INSERTION_CODE_ATOM_SITE_HEADERS
    ),
    _COMMON_CORE21_IDENTITY_PROFILE: _COMMON_CORE21_ATOM_SITE_HEADERS,
}
_ATOM_SITE_PROFILE_BY_HEADERS = {
    headers: profile for profile, headers in _ATOM_SITE_HEADERS_BY_PROFILE.items()
}
_COORDINATE_HEADERS = (
    "_atom_site.cartn_x",
    "_atom_site.cartn_y",
    "_atom_site.cartn_z",
)
_PARSER_OPERATIONS = (
    "parse_cif_1_1_block_structure",
    "parse_pdbx_atom_site_label_identity",
    "align_models_by_canonical_label_identity",
    "preserve_source_atom_order_from_first_model",
    "synthesize_canonical_atom_serials_from_first_model_order",
)
_COVERAGE_BASE_BLOCKERS = (
    "bond_topology_incomplete_or_unverified",
    "biological_assembly_not_applied",
    "missing_atom_and_residue_completion_not_assessed",
    "hydrogen_and_protonation_not_assessed",
    "stereochemistry_not_assessed",
    "modified_residue_cofactor_and_parameterability_not_assessed",
)
_ATOM_METADATA_KEYS = frozenset(
    {
        "source_record",
        "formal_charge_known",
        "formal_charge_source",
        "formal_charge_interpretation",
        "mmcif_auth_asym_id",
        "mmcif",
        "hydrogen_origin",
    }
)
_ATOM_MMCIF_METADATA_KEYS = frozenset(
    {
        "atom_site",
        "canonical_identity_namespace",
        "residue_sequence_source",
        "auth_identity",
        "entity_id",
        "entity_type",
        "source_atom_site_id",
        "atom_site_id_by_model",
        "atom_site_by_model",
    }
)
_AUTH_IDENTITY_KEYS = frozenset({"atom_id", "comp_id", "asym_id", "seq_id", "alt_id"})
_CIF_TOKEN_PAYLOAD_KEYS = frozenset({"value", "quoted", "multiline"})
_MODEL_ATOM_SITE_ID_KEYS = frozenset({"model_id", "atom_site_id"})
_MODEL_ATOM_SITE_KEYS = frozenset({"model_id", "values"})
_RESIDUE_METADATA_KEYS = frozenset(
    {
        "source_record",
        "entity_id",
        "source_residue_namespace",
        "entity_type_basis",
        "mmcif_label_seq_id",
        "mmcif_auth_seq_id",
        "canonical_sequence_source",
    }
)
_CHAIN_METADATA_KEYS = frozenset({"source_format", "auth_asym_ids"})
_PROVENANCE_METADATA_KEYS = frozenset(
    {
        "coverage",
        "model_ids",
        "canonical_topology_schema_id",
        "canonical_topology_sha256",
        "source_missingness_evidence_schema_id",
        "source_missingness_evidence_sha256",
        "parser_observation_schema_id",
        "parser_observation_sha256",
    }
)
_MMCIF_METADATA_KEYS = frozenset(
    {
        "data_block",
        "coordinate_scope",
        "assembly",
        "altloc_selection",
        "atom_site_headers",
        "category_inventory",
        "preserved_category_payloads",
        "source_missingness",
        "cell",
        "resource_usage",
        "resource_limits",
        "source_reported_missingness",
    }
)
_CATEGORY_INVENTORY_KEYS = frozenset(
    {"category", "scalar_item_count", "loop_count", "row_count", "policy"}
)
_PRESERVED_CATEGORY_KEYS = frozenset({"category", "policy", "scalar_items", "loops"})
_PRESERVED_LOOP_KEYS = frozenset({"source_loop_index", "tags", "rows"})
_RESOURCE_USAGE_KEYS = frozenset(
    {
        "input_bytes",
        "token_count",
        "atom_site_rows",
        "missing_residue_evidence_rows",
        "missing_atom_evidence_rows",
        "total_missingness_evidence_rows",
        "missingness_preserved_items",
        "missingness_preserved_value_utf8_bytes",
    }
)
_RESOURCE_LIMITS = {
    "input_bytes": _MAX_OUTPUT_BYTES,
    "token_count": _MAX_TOKEN_COUNT,
    "atom_site_rows": _MAX_ATOM_ROWS,
    "missing_residue_evidence_rows": MAX_MISSING_RESIDUE_CLAIMS,
    "missing_atom_evidence_rows": MAX_MISSING_ATOM_CLAIMS,
    "total_missingness_evidence_rows": MAX_TOTAL_MISSINGNESS_CLAIMS,
    "missingness_token_characters": _MAX_MISSINGNESS_TOKEN_CHARS,
    "missingness_preserved_items": _MAX_MISSINGNESS_PRESERVED_ITEMS,
    "missingness_preserved_value_utf8_bytes": (_MAX_MISSINGNESS_PRESERVED_UTF8_BYTES),
    "assembly_definition_rows": _MAX_ASSEMBLY_DEFINITION_ROWS,
    "assembly_generator_rows": _MAX_ASSEMBLY_GENERATOR_ROWS,
    "assembly_operator_rows": _MAX_ASSEMBLY_OPERATOR_ROWS,
    "assembly_oper_expression_characters": _MAX_ASSEMBLY_OPER_EXPRESSION_CHARS,
    "assembly_asym_id_list_characters": _MAX_ASSEMBLY_ASYM_ID_LIST_CHARS,
    "assembly_asym_ids_per_generator": _MAX_ASSEMBLY_ASYM_IDS_PER_GENERATOR,
}
_SOURCE_MISSINGNESS = {
    "interpretation_policy": (
        "documented_items_preserved_without_full_dictionary_validation/v1"
    ),
    "dictionary_validation_status": "not_assessed",
    "residue_row_count": 0,
    "atom_row_count": 0,
    "unobserved_residue_claim_count": 0,
    "unobserved_atom_claim_count": 0,
    "zero_occupancy_residue_row_count": 0,
    "zero_occupancy_atom_row_count": 0,
    "extension_item_count": 0,
}
_ALTLOC_SELECTION = {
    "status": "not_present",
    "requested_altloc_id": "",
    "models": [],
}
_ASSEMBLY = {
    "status": "not_present",
    "selection_policy": "explicit_only",
    "assembly_id": "",
}
_PRESERVATION_SCOPE = (
    "source_atom_residue_and_chain_first_occurrence_order",
    "mmcif_atom_or_hetatm_record_class",
    "source_atom_site_identifiers",
    "raw_bare_noncoordinate_selected_atom_site_profile_tokens",
    "label_atom_comp_asym_and_positive_sequence_identity",
    "source_pdbx_pdb_ins_code_raw_marker_and_canonical_residue_insertion_identity",
    "source_occupancy_raw_marker_and_exact_optional_binary64_canonical_value",
    "source_b_iso_or_equiv_raw_marker_and_exact_optional_binary64_canonical_value",
    "selected_common_core21_blank_label_alt_raw_marker",
    "selected_common_core21_complete_source_auth_atom_comp_asym_and_seq_aliases_without_canonical_namespace_promotion",
    "selected_common_core21_label_entity_struct_asym_and_recognized_entity_type_join",
    "selected_common_core21_entity_and_struct_asym_row_order_and_raw_bare_tokens",
    "selected_common_core21_nonpolymer_and_water_synthetic_negative_residue_number_carrier",
    "element_and_source_formal_charge_marker_state",
    "exact_ieee754_binary64_model_one_coordinates_angstrom",
    "single_explicit_model_id_one",
    "atom_site_only_exact_core_eleven_selected_formal_charge_and_insertion_code_profiles_independently_appended_occupancy_or_ordered_occupancy_b_factor_pair",
    "absence_of_altloc_assembly_cell_missingness_and_other_optional_atom_site_state",
)
_NON_PROMOTION_BLOCKERS = (
    "raw_source_bytes_comments_layout_header_case_and_coordinate_spelling_are_not_preserved",
    "system_id_source_id_parser_observation_and_resource_usage_are_outside_declared_projection",
    "full_canonical_snapshot_and_dynamic_source_provenance_equality_not_claimed",
    "sha256_receipts_are_tamper_evidence_not_source_authentication",
    "formal_charge_source_notation_is_not_charge_assignment_protonation_oxidation_or_electronic_state_assessment",
    "pdbx_pdb_ins_code_preservation_is_not_auth_numbering_polymer_sequence_alignment_completeness_or_modified_residue_assessment",
    "occupancy_source_notation_is_not_altloc_population_zero_occupancy_missingness_completeness_or_experimental_uncertainty_assessment",
    "b_iso_or_equiv_source_notation_is_not_refinement_validity_atomic_mobility_temperature_disorder_altloc_population_occupancy_weighting_experimental_uncertainty_or_uncertainty_propagation_assessment",
    "source_auth_identity_is_an_alias_and_is_not_equal_to_or_a_replacement_for_canonical_label_identity",
    "source_entity_type_is_not_polymer_sequence_completeness_modified_residue_chemistry_or_water_ion_ligand_cofactor_role_inference",
    "selected_entity_and_struct_asym_declarations_are_not_general_mmcif_category_support",
    "ion_metal_cofactor_roles_and_chemistry_are_not_assessed",
    "bonds_altloc_assembly_missingness_cell_and_atom_site_fields_or_combinations_outside_the_selected_profiles_unsupported",
    "preparation_parameterability_simulation_and_claim_authority_not_granted",
)
_ARTIFACT_FACTORY_TOKEN = object()


class MmcifWriteError(ValueError):
    """Stable fail-closed error for unrepresentable canonical mmCIF state."""

    def __init__(self, code: str, message: str, *, location: str | None = None):
        self.code = str(code)
        self.location = None if location is None else str(location)
        self.detail = str(message)
        suffix = "" if self.location is None else f" at {self.location}"
        super().__init__(f"{self.code}{suffix}: {self.detail}")


def _canonical_json_bytes(document: Mapping[str, Any]) -> bytes:
    return json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _sha256_document(document: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json_bytes(document)).hexdigest()


def _require_sha256(value: str, *, field_name: str) -> None:
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        raise TypeError(f"{field_name} must be a lowercase SHA-256")


def _require_exact_keys(
    value: Any,
    expected: frozenset[str],
    *,
    code: str,
    location: str,
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise MmcifWriteError(code, "value must be a mapping", location=location)
    actual = frozenset(value)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        raise MmcifWriteError(
            code,
            "mapping keys do not match parser-owned state; "
            f"missing={missing}, unknown={unknown}",
            location=location,
        )
    return value


def _atom_site_profile_for_headers(
    value: Any,
    *,
    location: str,
) -> tuple[str, tuple[str, ...]]:
    if not isinstance(value, (list, tuple)) or any(
        type(header) is not str for header in value
    ):
        raise MmcifWriteError(
            "unsupported_atom_site_headers",
            "atom-site headers must be an ordered string sequence",
            location=location,
        )
    headers = tuple(value)
    profile = _ATOM_SITE_PROFILE_BY_HEADERS.get(headers)
    if profile is None:
        raise MmcifWriteError(
            "unsupported_atom_site_headers",
            "writer requires one of the six legacy atom-site-only profiles or "
            "the exact common-core21 label/auth/entity profile",
            location=location,
        )
    return profile, headers


def _expected_output_token_count(
    atom_site_headers: tuple[str, ...],
    atom_count: int,
    *,
    entity_row_count: int = 0,
    struct_asym_row_count: int = 0,
) -> int:
    if atom_site_headers == _COMMON_CORE21_ATOM_SITE_HEADERS:
        # data token + three loop tokens + two two-column category loops.
        return (
            8
            + 2 * entity_row_count
            + 2 * struct_asym_row_count
            + len(atom_site_headers) * (atom_count + 1)
        )
    # One data-block token, one loop token, H headers, and H tokens per row.
    return 2 + len(atom_site_headers) * (atom_count + 1)


def _exact_typed_structure_equal(actual: Any, expected: Any) -> bool:
    """Compare frozen parser metadata without Python's bool/int coercions."""

    if isinstance(expected, Mapping):
        if not isinstance(actual, Mapping):
            return False
        if frozenset(actual) != frozenset(expected):
            return False
        return all(
            _exact_typed_structure_equal(actual[key], expected_value)
            for key, expected_value in expected.items()
        )
    if isinstance(expected, (list, tuple)):
        if not isinstance(actual, (list, tuple)) or len(actual) != len(expected):
            return False
        return all(
            _exact_typed_structure_equal(actual_value, expected_value)
            for actual_value, expected_value in zip(actual, expected, strict=True)
        )
    if type(actual) is not type(expected):
        return False
    if type(expected) is float:
        return struct.pack(">d", actual) == struct.pack(">d", expected)
    return bool(actual == expected)


def _binary64_hex(value: float) -> str:
    return struct.pack(">d", float(value)).hex()


@dataclass(frozen=True, slots=True)
class _SelectedCategoryState:
    category_profile: str
    identity_profile: str
    entity_rows: tuple[tuple[str, str], ...]
    struct_asym_rows: tuple[tuple[str, str], ...]
    entity_documents: tuple[Mapping[str, Any], ...]
    struct_asym_documents: tuple[Mapping[str, Any], ...]
    entity_types: Mapping[str, str]
    asym_entities: Mapping[str, str]
    category_inventory: tuple[Mapping[str, Any], ...]

    @property
    def entity_row_count(self) -> int:
        return len(self.entity_rows)

    @property
    def struct_asym_row_count(self) -> int:
        return len(self.struct_asym_rows)


@dataclass(frozen=True, slots=True, init=False)
class MmcifWriteReceipt:
    """Hash and live-count binding for one deterministic mmCIF emission."""

    input_system_schema_id: str
    parent_source_sha256: str
    input_snapshot_sha256: str
    input_topology_sha256: str
    input_representable_state_sha256: str
    identity_projection_schema_id: str
    identity_profile: str
    input_identity_projection_sha256: str
    category_profile: str
    input_parser_observation_sha256: str
    output_source_sha256: str
    output_byte_count: int
    output_token_count: int
    output_physical_line_count: int
    atom_count: int
    bond_count: int
    model_count: int
    atom_site_row_count: int
    atom_site_header_profile: str
    atom_site_header_count: int
    entity_row_count: int
    struct_asym_row_count: int
    complete_auth_row_count: int

    def __init__(
        self,
        *,
        input_system_schema_id: str,
        parent_source_sha256: str,
        input_snapshot_sha256: str,
        input_topology_sha256: str,
        input_representable_state_sha256: str,
        identity_projection_schema_id: str,
        identity_profile: str,
        input_identity_projection_sha256: str,
        category_profile: str,
        input_parser_observation_sha256: str,
        output_source_sha256: str,
        output_byte_count: int,
        output_token_count: int,
        output_physical_line_count: int,
        atom_count: int,
        bond_count: int,
        model_count: int,
        atom_site_row_count: int,
        atom_site_header_profile: str,
        atom_site_header_count: int,
        entity_row_count: int,
        struct_asym_row_count: int,
        complete_auth_row_count: int,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _ARTIFACT_FACTORY_TOKEN:
            raise TypeError("MmcifWriteReceipt is factory-only")
        for field_name, value in (
            ("input_system_schema_id", input_system_schema_id),
            ("parent_source_sha256", parent_source_sha256),
            ("input_snapshot_sha256", input_snapshot_sha256),
            ("input_topology_sha256", input_topology_sha256),
            ("input_representable_state_sha256", input_representable_state_sha256),
            ("identity_projection_schema_id", identity_projection_schema_id),
            ("identity_profile", identity_profile),
            (
                "input_identity_projection_sha256",
                input_identity_projection_sha256,
            ),
            ("category_profile", category_profile),
            ("input_parser_observation_sha256", input_parser_observation_sha256),
            ("output_source_sha256", output_source_sha256),
            ("output_byte_count", output_byte_count),
            ("output_token_count", output_token_count),
            ("output_physical_line_count", output_physical_line_count),
            ("atom_count", atom_count),
            ("bond_count", bond_count),
            ("model_count", model_count),
            ("atom_site_row_count", atom_site_row_count),
            ("atom_site_header_profile", atom_site_header_profile),
            ("atom_site_header_count", atom_site_header_count),
            ("entity_row_count", entity_row_count),
            ("struct_asym_row_count", struct_asym_row_count),
            ("complete_auth_row_count", complete_auth_row_count),
        ):
            object.__setattr__(self, field_name, value)
        self.__post_init__()

    def __post_init__(self) -> None:
        if self.input_system_schema_id != ALL_ATOM_SCHEMA_ID:
            raise ValueError("write receipt must bind the current all-atom schema")
        for field_name in (
            "parent_source_sha256",
            "input_snapshot_sha256",
            "input_topology_sha256",
            "input_representable_state_sha256",
            "input_identity_projection_sha256",
            "input_parser_observation_sha256",
            "output_source_sha256",
        ):
            _require_sha256(getattr(self, field_name), field_name=field_name)
        for field_name in (
            "output_byte_count",
            "output_token_count",
            "output_physical_line_count",
            "atom_count",
            "bond_count",
            "model_count",
            "atom_site_row_count",
            "atom_site_header_count",
            "entity_row_count",
            "struct_asym_row_count",
            "complete_auth_row_count",
        ):
            value = getattr(self, field_name)
            if type(value) is not int or value < 0:
                raise TypeError(f"{field_name} must be a nonnegative integer")
        if self.atom_count < 1 or self.atom_count > _MAX_ATOM_ROWS:
            raise ValueError("write receipt atom_count is outside the mmCIF limit")
        if self.bond_count != 0:
            raise ValueError("strict mmCIF write receipt bond_count must be zero")
        if self.model_count != 1:
            raise ValueError("strict mmCIF write receipt model_count must be one")
        if self.atom_site_row_count != self.atom_count:
            raise ValueError("write receipt atom-site row count must equal atom_count")
        if type(self.atom_site_header_profile) is not str:
            raise TypeError("atom_site_header_profile must be an exact string")
        expected_headers = _ATOM_SITE_HEADERS_BY_PROFILE.get(
            self.atom_site_header_profile
        )
        if expected_headers is None:
            raise ValueError("write receipt atom-site header profile is unsupported")
        if self.atom_site_header_count != len(expected_headers):
            raise ValueError(
                "write receipt atom-site header count does not match its profile"
            )
        if (
            self.identity_projection_schema_id
            != MMCIF_LABEL_AUTH_ENTITY_IDENTITY_PROJECTION_SCHEMA_ID
        ):
            raise ValueError("write receipt identity projection schema is unsupported")
        if self.atom_site_header_profile == _COMMON_CORE21_IDENTITY_PROFILE:
            if (
                self.identity_profile != _COMMON_CORE21_IDENTITY_PROFILE
                or self.category_profile != _COMMON_THREE_LOOP_CATEGORY_PROFILE
                or not 1 <= self.entity_row_count <= _MAX_ENTITY_ROWS
                or not 1 <= self.struct_asym_row_count <= _MAX_STRUCT_ASYM_ROWS
                or self.complete_auth_row_count != self.atom_count
            ):
                raise ValueError(
                    "common-core21 receipt identity/category bindings are inconsistent"
                )
        elif (
            self.identity_profile != _NO_AUTH_ENTITY_IDENTITY_PROFILE
            or self.category_profile != _ATOM_SITE_ONLY_CATEGORY_PROFILE
            or self.entity_row_count != 0
            or self.struct_asym_row_count != 0
            or self.complete_auth_row_count != 0
        ):
            raise ValueError(
                "atom-site-only receipt identity/category bindings are inconsistent"
            )
        if not 1 <= self.output_byte_count <= _MAX_OUTPUT_BYTES:
            raise ValueError(
                "write receipt output_byte_count is outside the writer limit"
            )
        if not 1 <= self.output_token_count <= _MAX_TOKEN_COUNT:
            raise ValueError(
                "write receipt output_token_count is outside the parser limit"
            )
        if not 1 <= self.output_physical_line_count <= _MAX_OUTPUT_LINES:
            raise ValueError(
                "write receipt output_physical_line_count is outside the parser limit"
            )

    def _core_dict(self) -> dict[str, Any]:
        return {
            "schema_id": MMCIF_WRITE_RECEIPT_SCHEMA_ID,
            "writer_version": MMCIF_WRITER_VERSION,
            "parser_version": MMCIF_PARSER_VERSION,
            "input_system_schema_id": self.input_system_schema_id,
            "parent_source_sha256": self.parent_source_sha256,
            "input_snapshot_sha256": self.input_snapshot_sha256,
            "input_topology_schema_id": CANONICAL_TOPOLOGY_SCHEMA_ID,
            "input_topology_sha256": self.input_topology_sha256,
            "representable_state_schema_id": MMCIF_REPRESENTABLE_STATE_SCHEMA_ID,
            "input_representable_state_sha256": (self.input_representable_state_sha256),
            "identity_projection_schema_id": self.identity_projection_schema_id,
            "identity_profile": self.identity_profile,
            "input_identity_projection_sha256": (self.input_identity_projection_sha256),
            "category_profile": self.category_profile,
            "parser_observation_schema_id": PARSER_OBSERVATION_SCHEMA_ID,
            "input_parser_observation_sha256": (self.input_parser_observation_sha256),
            "output_source_sha256": self.output_source_sha256,
            "output_byte_count": self.output_byte_count,
            "output_token_count": self.output_token_count,
            "output_physical_line_count": self.output_physical_line_count,
            "atom_count": self.atom_count,
            "bond_count": self.bond_count,
            "model_count": self.model_count,
            "atom_site_row_count": self.atom_site_row_count,
            "atom_site_header_profile": self.atom_site_header_profile,
            "atom_site_header_count": self.atom_site_header_count,
            "entity_row_count": self.entity_row_count,
            "struct_asym_row_count": self.struct_asym_row_count,
            "complete_auth_row_count": self.complete_auth_row_count,
            "coordinate_unit": "angstrom",
            "coordinate_format": (
                "cif_number_python_shortest_round_trip_exact_binary64"
            ),
            "preservation_scope": list(_PRESERVATION_SCOPE),
            "source_authentication_status": "not_authenticated",
            "preparation_ready": False,
            "parameterability_assessed": False,
            "simulation_ready": False,
            "claim_safe": False,
            "blockers": list(_NON_PROMOTION_BLOCKERS),
        }

    @property
    def receipt_sha256(self) -> str:
        return _sha256_document(self._core_dict())

    def to_dict(self) -> dict[str, Any]:
        payload = self._core_dict()
        payload["receipt_sha256"] = self.receipt_sha256
        return payload


@dataclass(frozen=True, slots=True, init=False)
class MmcifWriteResult:
    payload: bytes = field(repr=False)
    receipt: MmcifWriteReceipt

    def __init__(
        self,
        *,
        payload: bytes,
        receipt: MmcifWriteReceipt,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _ARTIFACT_FACTORY_TOKEN:
            raise TypeError("MmcifWriteResult is factory-only")
        object.__setattr__(self, "payload", payload)
        object.__setattr__(self, "receipt", receipt)
        self.__post_init__()

    def __post_init__(self) -> None:
        if type(self.payload) is not bytes:
            raise TypeError("mmCIF write payload must be exact bytes")
        if type(self.receipt) is not MmcifWriteReceipt:
            raise TypeError("receipt must be a MmcifWriteReceipt")
        if len(self.payload) != self.receipt.output_byte_count:
            raise ValueError("write payload length does not match receipt")
        if (
            hashlib.sha256(self.payload).hexdigest()
            != self.receipt.output_source_sha256
        ):
            raise ValueError("write payload SHA-256 does not match receipt")
        try:
            text = self.payload.decode("ascii")
            block = parse_cif_block(text)
        except (UnicodeDecodeError, CifSyntaxError) as exc:
            raise ValueError("write payload is not canonical parseable mmCIF") from exc
        physical_line_count = text.count("\n") + text.count("\r") + 1
        atom_site_loops = [
            loop for loop in block.loops if "_atom_site" in loop.categories
        ]
        entity_loops = [loop for loop in block.loops if "_entity" in loop.categories]
        struct_asym_loops = [
            loop for loop in block.loops if "_struct_asym" in loop.categories
        ]
        expected_headers = _ATOM_SITE_HEADERS_BY_PROFILE.get(
            self.receipt.atom_site_header_profile
        )
        common_identity = (
            self.receipt.category_profile == _COMMON_THREE_LOOP_CATEGORY_PROFILE
        )
        expected_categories = (
            ("_entity", "_struct_asym", "_atom_site")
            if common_identity
            else ("_atom_site",)
        )
        if (
            expected_headers is None
            or block.categories != expected_categories
            or block.scalar_values
            or len(block.loops) != (3 if common_identity else 1)
            or len(atom_site_loops) != 1
            or atom_site_loops[0].tags != expected_headers
            or len(atom_site_loops[0].tags) != self.receipt.atom_site_header_count
            or (
                common_identity
                and (
                    len(entity_loops) != 1
                    or entity_loops[0].tags != _ENTITY_HEADERS
                    or len(struct_asym_loops) != 1
                    or struct_asym_loops[0].tags != _STRUCT_ASYM_HEADERS
                )
            )
            or (not common_identity and (entity_loops or struct_asym_loops))
        ):
            raise ValueError(
                "write payload does not match its atom-site header profile"
            )
        rows = atom_site_loops[0].rows
        entity_row_count = len(entity_loops[0].rows) if common_identity else 0
        struct_asym_row_count = len(struct_asym_loops[0].rows) if common_identity else 0
        complete_auth_row_count = len(rows) if common_identity else 0
        model_id_index = expected_headers.index("_atom_site.pdbx_pdb_model_num")
        if any(
            row[model_id_index].quoted
            or row[model_id_index].multiline
            or _INTEGER_RE.fullmatch(row[model_id_index].value) is None
            or int(row[model_id_index].value, 10) != 1
            for row in rows
        ):
            raise ValueError("write payload does not contain only model ID 1 rows")
        live_pairs = (
            ("output_token_count", block.token_count, self.receipt.output_token_count),
            (
                "output_physical_line_count",
                physical_line_count,
                self.receipt.output_physical_line_count,
            ),
            ("atom_count", len(rows), self.receipt.atom_count),
            ("atom_site_row_count", len(rows), self.receipt.atom_site_row_count),
            (
                "atom_site_header_count",
                len(atom_site_loops[0].tags),
                self.receipt.atom_site_header_count,
            ),
            (
                "entity_row_count",
                entity_row_count,
                self.receipt.entity_row_count,
            ),
            (
                "struct_asym_row_count",
                struct_asym_row_count,
                self.receipt.struct_asym_row_count,
            ),
            (
                "complete_auth_row_count",
                complete_auth_row_count,
                self.receipt.complete_auth_row_count,
            ),
            ("model_count", 1, self.receipt.model_count),
            ("bond_count", 0, self.receipt.bond_count),
        )
        mismatches = [
            name for name, expected, observed in live_pairs if expected != observed
        ]
        if mismatches:
            raise ValueError(
                f"write payload live counts do not match receipt: {mismatches}"
            )
        try:
            reparsed = parse_mmcif(self.payload)
            regenerated_state = _validate_write_state(reparsed.system)
            (
                regenerated_payload,
                regenerated_token_count,
                regenerated_physical_line_count,
            ) = _emit_payload(regenerated_state)
        except (TypeError, ValueError, OverflowError, RuntimeError) as exc:
            raise ValueError(
                "write payload is outside the strict canonical mmCIF writer image"
            ) from exc
        if regenerated_payload != self.payload:
            raise ValueError(
                "write payload is not byte-for-byte canonical mmCIF writer output"
            )
        regenerated_pairs = (
            (
                "input_topology_sha256",
                canonical_topology_sha256(regenerated_state.system),
                self.receipt.input_topology_sha256,
            ),
            (
                "input_representable_state_sha256",
                _sha256_document(regenerated_state.representable_state_document),
                self.receipt.input_representable_state_sha256,
            ),
            (
                "input_identity_projection_sha256",
                _sha256_document(regenerated_state.identity_projection_document),
                self.receipt.input_identity_projection_sha256,
            ),
            (
                "output_byte_count",
                len(regenerated_payload),
                self.receipt.output_byte_count,
            ),
            (
                "output_token_count",
                regenerated_token_count,
                self.receipt.output_token_count,
            ),
            (
                "output_physical_line_count",
                regenerated_physical_line_count,
                self.receipt.output_physical_line_count,
            ),
            (
                "atom_count",
                regenerated_state.system.atom_count,
                self.receipt.atom_count,
            ),
            (
                "atom_site_row_count",
                len(regenerated_state.row_tokens),
                self.receipt.atom_site_row_count,
            ),
            (
                "atom_site_header_profile",
                regenerated_state.atom_site_header_profile,
                self.receipt.atom_site_header_profile,
            ),
            (
                "atom_site_header_count",
                len(regenerated_state.atom_site_headers),
                self.receipt.atom_site_header_count,
            ),
            (
                "identity_profile",
                regenerated_state.category_state.identity_profile,
                self.receipt.identity_profile,
            ),
            (
                "category_profile",
                regenerated_state.category_state.category_profile,
                self.receipt.category_profile,
            ),
            (
                "entity_row_count",
                regenerated_state.category_state.entity_row_count,
                self.receipt.entity_row_count,
            ),
            (
                "struct_asym_row_count",
                regenerated_state.category_state.struct_asym_row_count,
                self.receipt.struct_asym_row_count,
            ),
            (
                "complete_auth_row_count",
                (
                    regenerated_state.system.atom_count
                    if regenerated_state.atom_site_header_profile
                    == _COMMON_CORE21_IDENTITY_PROFILE
                    else 0
                ),
                self.receipt.complete_auth_row_count,
            ),
            (
                "model_count",
                regenerated_state.system.model_count,
                self.receipt.model_count,
            ),
            (
                "bond_count",
                len(regenerated_state.system.bonds),
                self.receipt.bond_count,
            ),
        )
        regenerated_mismatches = [
            name
            for name, expected, observed in regenerated_pairs
            if type(expected) is not type(observed) or expected != observed
        ]
        if regenerated_mismatches:
            raise ValueError(
                "regenerated payload bindings do not match receipt: "
                f"{regenerated_mismatches}"
            )


@dataclass(frozen=True, slots=True, init=False)
class MmcifRoundTripReport:
    """Evidence for the declared source-independent mmCIF projection."""

    input_source_sha256: str
    input_snapshot_sha256: str
    input_topology_sha256: str
    input_representable_state_sha256: str
    identity_projection_schema_id: str
    identity_profile: str
    category_profile: str
    input_identity_projection_sha256: str
    reparsed_identity_projection_sha256: str
    entity_row_count: int
    struct_asym_row_count: int
    complete_auth_row_count: int
    input_parser_observation_sha256: str
    writer_receipt_sha256: str
    emitted_source_sha256: str
    reparsed_snapshot_sha256: str
    reparsed_topology_sha256: str
    reparsed_representable_state_sha256: str
    reparsed_parser_observation_sha256: str
    reemitted_source_sha256: str

    def __init__(
        self,
        *,
        input_source_sha256: str,
        input_snapshot_sha256: str,
        input_topology_sha256: str,
        input_representable_state_sha256: str,
        identity_projection_schema_id: str,
        identity_profile: str,
        category_profile: str,
        input_identity_projection_sha256: str,
        reparsed_identity_projection_sha256: str,
        entity_row_count: int,
        struct_asym_row_count: int,
        complete_auth_row_count: int,
        input_parser_observation_sha256: str,
        writer_receipt_sha256: str,
        emitted_source_sha256: str,
        reparsed_snapshot_sha256: str,
        reparsed_topology_sha256: str,
        reparsed_representable_state_sha256: str,
        reparsed_parser_observation_sha256: str,
        reemitted_source_sha256: str,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _ARTIFACT_FACTORY_TOKEN:
            raise TypeError("MmcifRoundTripReport is factory-only")
        for field_name, value in (
            ("input_source_sha256", input_source_sha256),
            ("input_snapshot_sha256", input_snapshot_sha256),
            ("input_topology_sha256", input_topology_sha256),
            ("input_representable_state_sha256", input_representable_state_sha256),
            ("identity_projection_schema_id", identity_projection_schema_id),
            ("identity_profile", identity_profile),
            ("category_profile", category_profile),
            (
                "input_identity_projection_sha256",
                input_identity_projection_sha256,
            ),
            (
                "reparsed_identity_projection_sha256",
                reparsed_identity_projection_sha256,
            ),
            ("entity_row_count", entity_row_count),
            ("struct_asym_row_count", struct_asym_row_count),
            ("complete_auth_row_count", complete_auth_row_count),
            ("input_parser_observation_sha256", input_parser_observation_sha256),
            ("writer_receipt_sha256", writer_receipt_sha256),
            ("emitted_source_sha256", emitted_source_sha256),
            ("reparsed_snapshot_sha256", reparsed_snapshot_sha256),
            ("reparsed_topology_sha256", reparsed_topology_sha256),
            (
                "reparsed_representable_state_sha256",
                reparsed_representable_state_sha256,
            ),
            ("reparsed_parser_observation_sha256", reparsed_parser_observation_sha256),
            ("reemitted_source_sha256", reemitted_source_sha256),
        ):
            object.__setattr__(self, field_name, value)
        self.__post_init__()

    def __post_init__(self) -> None:
        for field_name in (
            "input_source_sha256",
            "input_snapshot_sha256",
            "input_topology_sha256",
            "input_representable_state_sha256",
            "input_identity_projection_sha256",
            "reparsed_identity_projection_sha256",
            "input_parser_observation_sha256",
            "writer_receipt_sha256",
            "emitted_source_sha256",
            "reparsed_snapshot_sha256",
            "reparsed_topology_sha256",
            "reparsed_representable_state_sha256",
            "reparsed_parser_observation_sha256",
            "reemitted_source_sha256",
        ):
            _require_sha256(getattr(self, field_name), field_name=field_name)
        if (
            self.identity_projection_schema_id
            != MMCIF_LABEL_AUTH_ENTITY_IDENTITY_PROJECTION_SCHEMA_ID
        ):
            raise ValueError("round-trip identity projection schema is unsupported")
        for field_name in (
            "entity_row_count",
            "struct_asym_row_count",
            "complete_auth_row_count",
        ):
            if (
                type(getattr(self, field_name)) is not int
                or getattr(self, field_name) < 0
            ):
                raise TypeError(f"{field_name} must be a nonnegative integer")
        if self.identity_profile == _COMMON_CORE21_IDENTITY_PROFILE:
            if (
                self.category_profile != _COMMON_THREE_LOOP_CATEGORY_PROFILE
                or not 1 <= self.entity_row_count <= _MAX_ENTITY_ROWS
                or not 1 <= self.struct_asym_row_count <= _MAX_STRUCT_ASYM_ROWS
                or self.complete_auth_row_count < 1
            ):
                raise ValueError(
                    "common-core21 report identity/category bindings are inconsistent"
                )
        elif (
            self.identity_profile != _NO_AUTH_ENTITY_IDENTITY_PROFILE
            or self.category_profile != _ATOM_SITE_ONLY_CATEGORY_PROFILE
            or self.entity_row_count != 0
            or self.struct_asym_row_count != 0
            or self.complete_auth_row_count != 0
        ):
            raise ValueError(
                "atom-site-only report identity/category bindings are inconsistent"
            )
        if self.input_topology_sha256 != self.reparsed_topology_sha256:
            raise ValueError("round-trip topology hashes must match")
        if (
            self.input_representable_state_sha256
            != self.reparsed_representable_state_sha256
        ):
            raise ValueError("round-trip representable-state hashes must match")
        if (
            self.input_identity_projection_sha256
            != self.reparsed_identity_projection_sha256
        ):
            raise ValueError("round-trip identity-projection hashes must match")
        if self.emitted_source_sha256 != self.reemitted_source_sha256:
            raise ValueError("round-trip emitted bytes must be stable")

    def _core_dict(self) -> dict[str, Any]:
        return {
            "schema_id": MMCIF_ROUND_TRIP_REPORT_SCHEMA_ID,
            "writer_version": MMCIF_WRITER_VERSION,
            "parser_version": MMCIF_PARSER_VERSION,
            "representable_state_schema_id": MMCIF_REPRESENTABLE_STATE_SCHEMA_ID,
            "identity_projection_schema_id": self.identity_projection_schema_id,
            "identity_profile": self.identity_profile,
            "category_profile": self.category_profile,
            "input_source_sha256": self.input_source_sha256,
            "input_snapshot_sha256": self.input_snapshot_sha256,
            "input_topology_sha256": self.input_topology_sha256,
            "input_representable_state_sha256": (self.input_representable_state_sha256),
            "input_identity_projection_sha256": (self.input_identity_projection_sha256),
            "input_parser_observation_sha256": (self.input_parser_observation_sha256),
            "writer_receipt_sha256": self.writer_receipt_sha256,
            "emitted_source_sha256": self.emitted_source_sha256,
            "reparsed_snapshot_sha256": self.reparsed_snapshot_sha256,
            "reparsed_topology_sha256": self.reparsed_topology_sha256,
            "reparsed_representable_state_sha256": (
                self.reparsed_representable_state_sha256
            ),
            "reparsed_identity_projection_sha256": (
                self.reparsed_identity_projection_sha256
            ),
            "entity_row_count": self.entity_row_count,
            "struct_asym_row_count": self.struct_asym_row_count,
            "complete_auth_row_count": self.complete_auth_row_count,
            "reparsed_parser_observation_sha256": (
                self.reparsed_parser_observation_sha256
            ),
            "reemitted_source_sha256": self.reemitted_source_sha256,
            "declared_projection_sha256_equal": True,
            "label_auth_entity_identity_projection_sha256_equal": True,
            "canonical_topology_sha256_equal": True,
            "coordinate_binary64_projection_equal": True,
            "declared_parser_marker_projection_equal": True,
            "emitted_source_sha256_and_bytes_stable": True,
            "full_canonical_snapshot_equality_claimed": False,
            "dynamic_source_provenance_equality_claimed": False,
            "source_authentication_status": "not_authenticated",
            "preparation_ready": False,
            "parameterability_assessed": False,
            "simulation_ready": False,
            "claim_safe": False,
            "blockers": list(_NON_PROMOTION_BLOCKERS),
        }

    @property
    def report_sha256(self) -> str:
        return _sha256_document(self._core_dict())

    def to_dict(self) -> dict[str, Any]:
        payload = self._core_dict()
        payload["report_sha256"] = self.report_sha256
        return payload


@dataclass(frozen=True, slots=True, init=False)
class MmcifRoundTripResult:
    """Snapshot-backed aggregate for one verified mmCIF source round trip."""

    _source_snapshot: bytes = field(repr=False)
    _source_coverage: StructureIngestCoverage
    _source_missingness: SourceReportedMissingnessReport = field(repr=False)
    _write_result: MmcifWriteResult = field(repr=False)
    _reparsed_snapshot: bytes = field(repr=False)
    _reparsed_coverage: StructureIngestCoverage
    _reparsed_missingness: SourceReportedMissingnessReport = field(repr=False)
    _report: MmcifRoundTripReport = field(repr=False)

    def __init__(
        self,
        *,
        source_ingest: StructureIngestResult,
        write_result: MmcifWriteResult,
        reparsed_ingest: StructureIngestResult,
        report: MmcifRoundTripReport,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _ARTIFACT_FACTORY_TOKEN:
            raise TypeError("MmcifRoundTripResult is factory-only")
        if type(source_ingest) is not StructureIngestResult:
            raise TypeError("source_ingest must be a StructureIngestResult")
        if type(source_ingest.coverage) is not StructureIngestCoverage:
            raise TypeError("source_ingest.coverage must be a StructureIngestCoverage")
        if (
            type(source_ingest.missingness_evidence)
            is not SourceReportedMissingnessReport
        ):
            raise TypeError(
                "source_ingest.missingness_evidence must be a "
                "SourceReportedMissingnessReport"
            )
        if type(write_result) is not MmcifWriteResult:
            raise TypeError("write_result must be a MmcifWriteResult")
        if type(reparsed_ingest) is not StructureIngestResult:
            raise TypeError("reparsed_ingest must be a StructureIngestResult")
        if type(reparsed_ingest.coverage) is not StructureIngestCoverage:
            raise TypeError(
                "reparsed_ingest.coverage must be a StructureIngestCoverage"
            )
        if (
            type(reparsed_ingest.missingness_evidence)
            is not SourceReportedMissingnessReport
        ):
            raise TypeError(
                "reparsed_ingest.missingness_evidence must be a "
                "SourceReportedMissingnessReport"
            )
        if type(report) is not MmcifRoundTripReport:
            raise TypeError("report must be a MmcifRoundTripReport")
        object.__setattr__(
            self,
            "_source_snapshot",
            serialize_all_atom_system(source_ingest.system),
        )
        object.__setattr__(self, "_source_coverage", source_ingest.coverage)
        object.__setattr__(
            self,
            "_source_missingness",
            source_ingest.missingness_evidence,
        )
        object.__setattr__(self, "_write_result", write_result)
        object.__setattr__(
            self,
            "_reparsed_snapshot",
            serialize_all_atom_system(reparsed_ingest.system),
        )
        object.__setattr__(self, "_reparsed_coverage", reparsed_ingest.coverage)
        object.__setattr__(
            self,
            "_reparsed_missingness",
            reparsed_ingest.missingness_evidence,
        )
        object.__setattr__(self, "_report", report)
        self.__post_init__()

    @property
    def source_ingest(self) -> StructureIngestResult:
        """Return a fresh detached copy of the source canonical snapshot."""

        return StructureIngestResult(
            system=deserialize_all_atom_system(self._source_snapshot),
            coverage=self._source_coverage,
            missingness_evidence=self._source_missingness,
        )

    @property
    def write_result(self) -> MmcifWriteResult:
        return self._write_result

    @property
    def reparsed_ingest(self) -> StructureIngestResult:
        """Return a fresh detached copy of the reparsed canonical snapshot."""

        return StructureIngestResult(
            system=deserialize_all_atom_system(self._reparsed_snapshot),
            coverage=self._reparsed_coverage,
            missingness_evidence=self._reparsed_missingness,
        )

    @property
    def report(self) -> MmcifRoundTripReport:
        return self._report

    def __post_init__(self) -> None:
        if type(self._source_snapshot) is not bytes:
            raise TypeError("source snapshot must be exact bytes")
        if type(self._source_coverage) is not StructureIngestCoverage:
            raise TypeError("source coverage must be a StructureIngestCoverage")
        if type(self._source_missingness) is not SourceReportedMissingnessReport:
            raise TypeError(
                "source missingness must be a SourceReportedMissingnessReport"
            )
        if type(self._write_result) is not MmcifWriteResult:
            raise TypeError("write result must be a MmcifWriteResult")
        if type(self._reparsed_snapshot) is not bytes:
            raise TypeError("reparsed snapshot must be exact bytes")
        if type(self._reparsed_coverage) is not StructureIngestCoverage:
            raise TypeError("reparsed coverage must be a StructureIngestCoverage")
        if type(self._reparsed_missingness) is not SourceReportedMissingnessReport:
            raise TypeError(
                "reparsed missingness must be a SourceReportedMissingnessReport"
            )
        if type(self._report) is not MmcifRoundTripReport:
            raise TypeError("report must be a MmcifRoundTripReport")

        source_ingest = self.source_ingest
        reparsed_ingest = self.reparsed_ingest
        source_system = source_ingest.system
        reparsed_system = reparsed_ingest.system
        source_snapshot_sha256 = canonical_all_atom_snapshot_digest(source_system)
        source_topology_sha256 = canonical_topology_sha256(source_system)
        source_state = _validate_write_state(source_system)
        source_state_sha256 = _sha256_document(
            source_state.representable_state_document
        )
        source_identity_sha256 = _sha256_document(
            source_state.identity_projection_document
        )
        reparsed_snapshot_sha256 = canonical_all_atom_snapshot_digest(reparsed_system)
        reparsed_topology_sha256 = canonical_topology_sha256(reparsed_system)
        reparsed_state = _validate_write_state(reparsed_system)
        reparsed_state_sha256 = _sha256_document(
            reparsed_state.representable_state_document
        )
        reparsed_identity_sha256 = _sha256_document(
            reparsed_state.identity_projection_document
        )
        output_source_sha256 = hashlib.sha256(self.write_result.payload).hexdigest()
        reemitted = write_mmcif(reparsed_system)
        source_observation = source_system.provenance.metadata.get(
            "parser_observation_sha256"
        )
        reparsed_observation = reparsed_system.provenance.metadata.get(
            "parser_observation_sha256"
        )
        source_header_profile = source_state.atom_site_header_profile
        source_headers = source_state.atom_site_headers
        output_token_count = _expected_output_token_count(
            source_headers,
            source_system.atom_count,
            entity_row_count=source_state.category_state.entity_row_count,
            struct_asym_row_count=(source_state.category_state.struct_asym_row_count),
        )
        output_physical_line_count = self.write_result.payload.count(b"\n") + 1
        expected_pairs = (
            (
                "source system schema to receipt",
                source_system.schema_id,
                self.write_result.receipt.input_system_schema_id,
            ),
            (
                "source atom count to receipt",
                source_system.atom_count,
                self.write_result.receipt.atom_count,
            ),
            (
                "source bond count to receipt",
                len(source_system.bonds),
                self.write_result.receipt.bond_count,
            ),
            (
                "source model count to receipt",
                source_system.model_count,
                self.write_result.receipt.model_count,
            ),
            (
                "source atom-site row count to receipt",
                source_system.atom_count,
                self.write_result.receipt.atom_site_row_count,
            ),
            (
                "source atom-site header profile to receipt",
                source_header_profile,
                self.write_result.receipt.atom_site_header_profile,
            ),
            (
                "source atom-site header count to receipt",
                len(source_headers),
                self.write_result.receipt.atom_site_header_count,
            ),
            (
                "source identity profile to receipt",
                source_state.category_state.identity_profile,
                self.write_result.receipt.identity_profile,
            ),
            (
                "source category profile to receipt",
                source_state.category_state.category_profile,
                self.write_result.receipt.category_profile,
            ),
            (
                "source entity row count to receipt",
                source_state.category_state.entity_row_count,
                self.write_result.receipt.entity_row_count,
            ),
            (
                "source struct-asym row count to receipt",
                source_state.category_state.struct_asym_row_count,
                self.write_result.receipt.struct_asym_row_count,
            ),
            (
                "source complete-auth row count to receipt",
                (
                    source_system.atom_count
                    if source_header_profile == _COMMON_CORE21_IDENTITY_PROFILE
                    else 0
                ),
                self.write_result.receipt.complete_auth_row_count,
            ),
            (
                "payload byte count to receipt",
                len(self.write_result.payload),
                self.write_result.receipt.output_byte_count,
            ),
            (
                "payload token count to receipt",
                output_token_count,
                self.write_result.receipt.output_token_count,
            ),
            (
                "payload physical line count to receipt",
                output_physical_line_count,
                self.write_result.receipt.output_physical_line_count,
            ),
            (
                "source provenance to report input source",
                source_system.provenance.source_sha256,
                self.report.input_source_sha256,
            ),
            (
                "source provenance to receipt parent source",
                source_system.provenance.source_sha256,
                self.write_result.receipt.parent_source_sha256,
            ),
            (
                "source snapshot to receipt",
                source_snapshot_sha256,
                self.write_result.receipt.input_snapshot_sha256,
            ),
            (
                "source snapshot to report",
                source_snapshot_sha256,
                self.report.input_snapshot_sha256,
            ),
            (
                "source topology to receipt",
                source_topology_sha256,
                self.write_result.receipt.input_topology_sha256,
            ),
            (
                "source topology to report",
                source_topology_sha256,
                self.report.input_topology_sha256,
            ),
            (
                "source representable state to receipt",
                source_state_sha256,
                self.write_result.receipt.input_representable_state_sha256,
            ),
            (
                "source representable state to report",
                source_state_sha256,
                self.report.input_representable_state_sha256,
            ),
            (
                "source identity projection to receipt",
                source_identity_sha256,
                self.write_result.receipt.input_identity_projection_sha256,
            ),
            (
                "source identity projection to report",
                source_identity_sha256,
                self.report.input_identity_projection_sha256,
            ),
            (
                "source identity profile to report",
                source_state.category_state.identity_profile,
                self.report.identity_profile,
            ),
            (
                "source category profile to report",
                source_state.category_state.category_profile,
                self.report.category_profile,
            ),
            (
                "source entity row count to report",
                source_state.category_state.entity_row_count,
                self.report.entity_row_count,
            ),
            (
                "source struct-asym row count to report",
                source_state.category_state.struct_asym_row_count,
                self.report.struct_asym_row_count,
            ),
            (
                "source complete-auth row count to report",
                (
                    source_system.atom_count
                    if source_header_profile == _COMMON_CORE21_IDENTITY_PROFILE
                    else 0
                ),
                self.report.complete_auth_row_count,
            ),
            (
                "source parser observation to receipt",
                source_observation,
                self.write_result.receipt.input_parser_observation_sha256,
            ),
            (
                "source parser observation to report",
                source_observation,
                self.report.input_parser_observation_sha256,
            ),
            (
                "write receipt to report",
                self.write_result.receipt.receipt_sha256,
                self.report.writer_receipt_sha256,
            ),
            (
                "payload to receipt output source",
                output_source_sha256,
                self.write_result.receipt.output_source_sha256,
            ),
            (
                "payload to report emitted source",
                output_source_sha256,
                self.report.emitted_source_sha256,
            ),
            (
                "payload to reparsed source provenance",
                output_source_sha256,
                reparsed_system.provenance.source_sha256,
            ),
            (
                "reparsed snapshot to report",
                reparsed_snapshot_sha256,
                self.report.reparsed_snapshot_sha256,
            ),
            (
                "reparsed topology to report",
                reparsed_topology_sha256,
                self.report.reparsed_topology_sha256,
            ),
            (
                "reparsed representable state to report",
                reparsed_state_sha256,
                self.report.reparsed_representable_state_sha256,
            ),
            (
                "reparsed identity projection to report",
                reparsed_identity_sha256,
                self.report.reparsed_identity_projection_sha256,
            ),
            (
                "reparsed parser observation to report",
                reparsed_observation,
                self.report.reparsed_parser_observation_sha256,
            ),
            (
                "reemitted payload to report",
                hashlib.sha256(reemitted.payload).hexdigest(),
                self.report.reemitted_source_sha256,
            ),
        )
        mismatches = [
            label
            for label, expected, observed in expected_pairs
            if expected != observed
        ]
        for label, ingest in (
            ("source", source_ingest),
            ("reparsed", reparsed_ingest),
        ):
            if not _exact_typed_structure_equal(
                ingest.system.provenance.metadata.get("coverage"),
                ingest.coverage.to_dict(),
            ):
                mismatches.append(f"{label} ingest coverage")
            if not _exact_typed_structure_equal(
                ingest.system.metadata.get("mmcif", {}).get(
                    "source_reported_missingness"
                ),
                ingest.missingness_evidence.to_dict(),
            ):
                mismatches.append(f"{label} ingest missingness")
        if reemitted.payload != self.write_result.payload:
            mismatches.append("reemitted payload bytes")
        if mismatches:
            raise ValueError(
                "mmCIF round-trip result artifacts are not cross-consistent: "
                f"{mismatches}"
            )


@dataclass(frozen=True, slots=True)
class _ValidatedWriteState:
    system: AllAtomSystem
    data_block: str
    atom_site_header_profile: str
    atom_site_headers: tuple[str, ...]
    category_state: _SelectedCategoryState
    row_tokens: tuple[tuple[str, ...], ...]
    identity_projection_document: Mapping[str, Any]
    representable_state_document: Mapping[str, Any]


def _snapshot_parser_system(system: AllAtomSystem) -> AllAtomSystem:
    if type(system) is not AllAtomSystem:
        raise TypeError("mmCIF writer input must be an exact AllAtomSystem")
    coordinates = system.coordinates
    if coordinates.device.type != "cpu":
        raise MmcifWriteError(
            "unsupported_coordinate_device",
            "parser-owned mmCIF coordinates must be on CPU",
            location="coordinates",
        )
    if coordinates.dtype is not torch.float64:
        raise MmcifWriteError(
            "unsupported_coordinate_dtype",
            "parser-owned mmCIF coordinates must use float64",
            location="coordinates",
        )
    if coordinates.requires_grad:
        raise MmcifWriteError(
            "coordinate_gradient_state_unsupported",
            "mmCIF writing does not accept coordinates requiring gradients",
            location="coordinates",
        )
    if system.coordinate_unit != "angstrom":
        raise MmcifWriteError(
            "unsupported_coordinate_unit",
            "mmCIF core coordinates must be in angstrom",
            location="coordinate_unit",
        )
    try:
        snapshot = replace(system, coordinates=coordinates.detach().clone())
        require_valid_all_atom_system(snapshot)
    except (MolecularValidationError, TypeError, ValueError, RuntimeError) as exc:
        raise MmcifWriteError(
            "canonical_validation_failed",
            str(exc),
            location="system",
        ) from exc
    return snapshot


def _safe_data_block(value: Any, *, location: str) -> str:
    if (
        type(value) is not str
        or not 1 <= len(value) <= _MAX_DATA_BLOCK_CHARS
        or _DATA_BLOCK_RE.fullmatch(value) is None
    ):
        raise MmcifWriteError(
            "unsupported_data_block",
            "data block must contain 1-75 ASCII letters, digits, '.', '_', '+', or '-' and start alphanumeric",
            location=location,
        )
    return value


def _safe_bare_token(value: Any, *, location: str) -> str:
    if type(value) is not str or not value:
        raise MmcifWriteError(
            "unsafe_cif_token",
            "core atom-site value must be a nonempty string",
            location=location,
        )
    if not value.isascii() or any(
        ord(character) < 0x21 or ord(character) > 0x7E for character in value
    ):
        raise MmcifWriteError(
            "unsafe_cif_token",
            "core atom-site value must contain only non-whitespace printable ASCII",
            location=location,
        )
    lower = value.lower()
    if (
        value in {".", "?"}
        or value[0] in {"$", "[", "]"}
        or any(character in value for character in {"#", ";", "'", '"'})
        or value.startswith("_")
        or lower in {"loop_", "stop_", "global_"}
        or lower.startswith(("data_", "save_"))
    ):
        raise MmcifWriteError(
            "unsafe_cif_token",
            "value is missing, quoted, comment-like, or structural when emitted bare",
            location=location,
        )
    return value


def _strict_integer_token(value: str, *, location: str) -> int:
    if _INTEGER_RE.fullmatch(value) is None:
        raise MmcifWriteError(
            "unsupported_atom_site_metadata",
            "value must be an unquoted decimal integer",
            location=location,
        )
    significant_digits = value.lstrip("+-").lstrip("0") or "0"
    if len(significant_digits) > 16:
        raise MmcifWriteError(
            "unsupported_atom_site_metadata",
            "integer exceeds the interoperable JSON range",
            location=location,
        )
    magnitude = int(significant_digits, 10)
    result = -magnitude if value.startswith("-") else magnitude
    if abs(result) > (1 << 53) - 1:
        raise MmcifWriteError(
            "unsupported_atom_site_metadata",
            "integer exceeds the interoperable JSON range",
            location=location,
        )
    return result


def _strict_coordinate_token(value: str, *, location: str) -> float:
    match = _CIF_NUMBER_RE.fullmatch(value)
    if match is None:
        raise MmcifWriteError(
            "unsupported_atom_site_metadata",
            "coordinate token must be an uncertainty-free CIF number",
            location=location,
        )
    parsed = float(match.group("mantissa") + (match.group("exponent") or ""))
    if not math.isfinite(parsed):
        raise MmcifWriteError(
            "nonfinite_coordinate",
            "coordinate token must parse to a finite binary64 value",
            location=location,
        )
    return parsed


def _strict_occupancy_token(value: Any, *, location: str) -> float | None:
    if type(value) is not str or not value.isascii():
        raise MmcifWriteError(
            "unsupported_occupancy",
            "occupancy marker must be an ASCII string",
            location=location,
        )
    if value in {".", "?"}:
        return None
    match = _CIF_NUMBER_RE.fullmatch(value)
    if match is None:
        raise MmcifWriteError(
            "unsupported_occupancy",
            "occupancy token must be an uncertainty-free bare CIF number, '.', or '?'",
            location=location,
        )
    try:
        parsed = float(match.group("mantissa") + (match.group("exponent") or ""))
    except (OverflowError, ValueError) as exc:
        raise MmcifWriteError(
            "unsupported_occupancy",
            "occupancy token must parse to a finite binary64 value",
            location=location,
        ) from exc
    if not math.isfinite(parsed) or not 0.0 <= parsed <= 1.0:
        raise MmcifWriteError(
            "unsupported_occupancy",
            "occupancy token must parse to a finite binary64 value in [0, 1]",
            location=location,
        )
    return parsed


def _strict_b_factor_token(value: Any, *, location: str) -> float | None:
    if type(value) is not str or not value.isascii():
        raise MmcifWriteError(
            "unsupported_b_factor",
            "B_iso_or_equiv marker must be an ASCII string",
            location=location,
        )
    if value in {".", "?"}:
        return None
    match = _CIF_NUMBER_RE.fullmatch(value)
    if match is None:
        raise MmcifWriteError(
            "unsupported_b_factor",
            "B_iso_or_equiv token must be an uncertainty-free bare CIF number, '.', or '?'",
            location=location,
        )
    try:
        parsed = float(match.group("mantissa") + (match.group("exponent") or ""))
    except (OverflowError, ValueError) as exc:
        raise MmcifWriteError(
            "unsupported_b_factor",
            "B_iso_or_equiv token must parse to a finite binary64 value",
            location=location,
        ) from exc
    if not math.isfinite(parsed):
        raise MmcifWriteError(
            "unsupported_b_factor",
            "B_iso_or_equiv token must parse to a finite binary64 value",
            location=location,
        )
    return parsed


def _expected_missingness_report(
    system: AllAtomSystem,
    *,
    topology_sha256: str,
) -> SourceReportedMissingnessReport:
    try:
        return build_source_reported_missingness_report(
            source_format="mmcif",
            source_sha256=system.provenance.source_sha256,
            canonical_topology_sha256=topology_sha256,
            coordinate_scope="deposited_asymmetric_unit",
            altloc_status="not_present",
            requested_altloc_id="",
            assembly_status="not_present",
            requested_assembly_id="",
        )
    except (TypeError, ValueError, OverflowError) as exc:
        raise MmcifWriteError(
            "stale_missingness_digest",
            "source provenance cannot produce the parser-owned empty missingness report",
            location="provenance.source_sha256",
        ) from exc


def _expected_coverage_document(
    system: AllAtomSystem,
    *,
    topology_sha256: str,
    missingness_sha256: str,
) -> dict[str, Any]:
    atom_count = system.atom_count
    unknown_formal_charge_count = sum(
        not atom.formal_charge_known for atom in system.atoms
    )
    unknown_entity_type_count = sum(
        residue.entity_type == "unknown" for residue in system.residues
    )
    blockers = list(_COVERAGE_BASE_BLOCKERS)
    if unknown_formal_charge_count:
        blockers.append("formal_charge_unknown_for_some_atoms")
    if unknown_entity_type_count:
        blockers.append("entity_type_unknown_for_some_residues")
    return {
        "source_format": "mmcif",
        "support_scope": STRUCTURE_INGEST_SUPPORT_SCOPE,
        "supported": True,
        "syntax_ingest_supported": True,
        "preparation_ready": False,
        "claim_safe": False,
        "atom_count": atom_count,
        "bond_count": 0,
        "residue_count": len(system.residues),
        "chain_count": len(system.chains),
        "model_count": 1,
        "explicit_hydrogen_count": sum(atom.element == "H" for atom in system.atoms),
        "hetero_residue_count": sum(residue.hetero for residue in system.residues),
        "cell_present": False,
        "unknown_formal_charge_count": unknown_formal_charge_count,
        "unknown_entity_type_count": unknown_entity_type_count,
        "uninterpreted_category_count": 0,
        "canonical_topology_schema_id": CANONICAL_TOPOLOGY_SCHEMA_ID,
        "canonical_topology_sha256": topology_sha256,
        "source_atom_row_count": atom_count,
        "altloc_status": "not_present",
        "requested_altloc_id": "",
        "altloc_affected_residue_count": 0,
        "altloc_kept_row_count": atom_count,
        "altloc_discarded_row_count": 0,
        "coordinate_scope": "deposited_asymmetric_unit",
        "assembly_status": "not_present",
        "requested_assembly_id": "",
        "assembly_operation_sequence_count": 0,
        "assembly_operation_application_count": 0,
        "assembly_chain_instance_count": 0,
        "assembly_output_atom_count": 0,
        "missingness_evidence_status": "not_present",
        "source_reported_missing_residue_claim_count": 0,
        "source_reported_missing_atom_claim_count": 0,
        "source_missingness_evidence_schema_id": MISSINGNESS_REPORT_SCHEMA_ID,
        "source_missingness_evidence_sha256": missingness_sha256,
        "missingness_completion_policy_id": MISSINGNESS_PRESERVATION_POLICY_ID,
        "missingness_completion_status": "not_assessed",
        "blockers": blockers,
    }


def _validate_provenance_and_metadata(
    system: AllAtomSystem,
    *,
    atom_site_headers: tuple[str, ...],
    category_state: _SelectedCategoryState,
) -> tuple[str, Mapping[str, Any], SourceReportedMissingnessReport]:
    provenance = system.provenance
    if provenance.source_format != "mmcif":
        raise MmcifWriteError(
            "unsupported_source_format",
            "writer accepts only strict mmCIF parser output",
            location="provenance.source_format",
        )
    if (
        provenance.parser_name != _MMCIF_PARSER_NAME
        or provenance.parser_version != MMCIF_PARSER_VERSION
    ):
        raise MmcifWriteError(
            "unsupported_parser_pedigree",
            "writer requires the current strict mmCIF parser pedigree",
            location="provenance",
        )
    if "select_explicit_altloc_id/v1" in provenance.operations:
        raise MmcifWriteError(
            "unsupported_altloc_selection",
            "mmCIF writer v1 does not emit selected alternate locations",
            location="provenance.operations",
        )
    if any("assembly" in operation for operation in provenance.operations):
        raise MmcifWriteError(
            "unsupported_assembly",
            "mmCIF writer v1 does not emit assembly-expanded state",
            location="provenance.operations",
        )
    if "preserve_source_reported_missingness_without_completion/v1" in (
        provenance.operations
    ):
        raise MmcifWriteError(
            "unsupported_missingness_evidence",
            "mmCIF writer v1 does not emit source-reported missingness evidence",
            location="provenance.operations",
        )
    if provenance.operations != _PARSER_OPERATIONS:
        raise MmcifWriteError(
            "unsupported_provenance_operations",
            "provenance operations are not the selected-profile single-model parser ledger",
            location="provenance.operations",
        )
    if provenance.parent_sha256:
        raise MmcifWriteError(
            "unsupported_parent_provenance",
            "parser-owned mmCIF state must not carry parent source hashes",
            location="provenance.parent_sha256",
        )
    if provenance.preparation_ready or provenance.claim_safe:
        raise MmcifWriteError(
            "unsupported_authority_state",
            "mmCIF source writing cannot preserve preparation or claim authority",
            location="provenance",
        )
    if _SHA256_RE.fullmatch(provenance.source_sha256) is None:
        raise MmcifWriteError(
            "unsupported_source_provenance",
            "parser source SHA-256 is missing or malformed",
            location="provenance.source_sha256",
        )

    provenance_metadata = _require_exact_keys(
        provenance.metadata,
        _PROVENANCE_METADATA_KEYS,
        code="unsupported_provenance_metadata",
        location="provenance.metadata",
    )
    topology_sha256 = canonical_topology_sha256(system)
    if (
        provenance_metadata.get("canonical_topology_schema_id")
        != CANONICAL_TOPOLOGY_SCHEMA_ID
        or provenance_metadata.get("canonical_topology_sha256") != topology_sha256
        or not attached_canonical_topology_sha256_matches(system)
    ):
        raise MmcifWriteError(
            "stale_canonical_topology_digest",
            "attached canonical topology digest does not match current state",
            location="provenance.metadata.canonical_topology_sha256",
        )
    if provenance_metadata.get(
        "parser_observation_schema_id"
    ) != PARSER_OBSERVATION_SCHEMA_ID or not attached_parser_observation_sha256_matches(
        system
    ):
        raise MmcifWriteError(
            "stale_parser_observation_digest",
            "attached parser-observation digest does not match current state",
            location="provenance.metadata.parser_observation_sha256",
        )
    raw_model_ids = provenance_metadata.get("model_ids")
    if (
        not isinstance(raw_model_ids, (list, tuple))
        or len(raw_model_ids) != 1
        or type(raw_model_ids[0]) is not int
        or raw_model_ids[0] != 1
    ):
        raise MmcifWriteError(
            "unsupported_model_id",
            "mmCIF writer v1 requires exactly one parser model ID equal to 1",
            location="provenance.metadata.model_ids",
        )

    expected_missingness = _expected_missingness_report(
        system,
        topology_sha256=topology_sha256,
    )
    if (
        provenance_metadata.get("source_missingness_evidence_schema_id")
        != MISSINGNESS_REPORT_SCHEMA_ID
        or provenance_metadata.get("source_missingness_evidence_sha256")
        != expected_missingness.report_sha256
    ):
        raise MmcifWriteError(
            "stale_missingness_digest",
            "attached empty missingness digest does not match current source/topology",
            location="provenance.metadata.source_missingness_evidence_sha256",
        )
    expected_coverage = _expected_coverage_document(
        system,
        topology_sha256=topology_sha256,
        missingness_sha256=expected_missingness.report_sha256,
    )
    coverage = provenance_metadata.get("coverage")
    if not _exact_typed_structure_equal(coverage, expected_coverage):
        raise MmcifWriteError(
            "stale_mmcif_coverage",
            "attached mmCIF coverage does not match current parser-owned state",
            location="provenance.metadata.coverage",
        )

    system_metadata = _require_exact_keys(
        system.metadata,
        frozenset({"mmcif"}),
        code="unsupported_system_metadata",
        location="metadata",
    )
    mmcif_metadata = _require_exact_keys(
        system_metadata["mmcif"],
        _MMCIF_METADATA_KEYS,
        code="unsupported_mmcif_metadata",
        location="metadata.mmcif",
    )
    data_block = _safe_data_block(
        mmcif_metadata.get("data_block"),
        location="metadata.mmcif.data_block",
    )
    if mmcif_metadata.get("coordinate_scope") != "deposited_asymmetric_unit":
        raise MmcifWriteError(
            "unsupported_coordinate_scope",
            "mmCIF writer v1 requires deposited asymmetric-unit coordinates",
            location="metadata.mmcif.coordinate_scope",
        )
    assembly = mmcif_metadata.get("assembly")
    if not _exact_typed_structure_equal(assembly, _ASSEMBLY):
        raise MmcifWriteError(
            "unsupported_assembly",
            "mmCIF writer v1 requires parser-owned absent assembly state",
            location="metadata.mmcif.assembly",
        )
    altloc_selection = mmcif_metadata.get("altloc_selection")
    if not _exact_typed_structure_equal(altloc_selection, _ALTLOC_SELECTION):
        raise MmcifWriteError(
            "unsupported_altloc_selection",
            "mmCIF writer v1 requires parser-owned no-altloc state",
            location="metadata.mmcif.altloc_selection",
        )
    raw_headers = mmcif_metadata.get("atom_site_headers")
    if (
        not isinstance(raw_headers, (list, tuple))
        or tuple(raw_headers) != atom_site_headers
    ):
        raise MmcifWriteError(
            "unsupported_atom_site_headers",
            "atom-site headers changed after profile selection",
            location="metadata.mmcif.atom_site_headers",
        )
    # The full category/payload surface was validated before source-bound digest
    # checks.  Re-evaluate it here so later validation cannot bypass that join.
    regenerated_category_state = _selected_category_state(
        mmcif_metadata,
        atom_site_header_profile=_ATOM_SITE_PROFILE_BY_HEADERS[atom_site_headers],
        atom_count=system.atom_count,
    )
    if (
        not _exact_typed_structure_equal(
            regenerated_category_state.category_inventory,
            category_state.category_inventory,
        )
        or not _exact_typed_structure_equal(
            regenerated_category_state.entity_documents,
            category_state.entity_documents,
        )
        or not _exact_typed_structure_equal(
            regenerated_category_state.struct_asym_documents,
            category_state.struct_asym_documents,
        )
    ):
        raise MmcifWriteError(
            "unsupported_category_inventory",
            "selected identity category state changed during validation",
            location="metadata.mmcif.category_inventory",
        )
    source_missingness = mmcif_metadata.get("source_missingness")
    if not _exact_typed_structure_equal(source_missingness, _SOURCE_MISSINGNESS):
        raise MmcifWriteError(
            "unsupported_missingness_evidence",
            "mmCIF writer v1 requires absent source missingness evidence",
            location="metadata.mmcif.source_missingness",
        )
    if mmcif_metadata.get("cell") is not None:
        raise MmcifWriteError(
            "unsupported_unit_cell",
            "mmCIF writer v1 does not emit cell metadata",
            location="metadata.mmcif.cell",
        )
    attached_missingness = mmcif_metadata.get("source_reported_missingness")
    if not _exact_typed_structure_equal(
        attached_missingness,
        expected_missingness.to_dict(),
    ):
        raise MmcifWriteError(
            "stale_missingness_digest",
            "attached source-reported missingness report is stale",
            location="metadata.mmcif.source_reported_missingness",
        )
    resource_limits = mmcif_metadata.get("resource_limits")
    if not _exact_typed_structure_equal(resource_limits, _RESOURCE_LIMITS):
        raise MmcifWriteError(
            "unsupported_resource_metadata",
            "mmCIF parser resource limits are missing or stale",
            location="metadata.mmcif.resource_limits",
        )
    resource_usage = _require_exact_keys(
        mmcif_metadata.get("resource_usage"),
        _RESOURCE_USAGE_KEYS,
        code="unsupported_resource_metadata",
        location="metadata.mmcif.resource_usage",
    )
    input_bytes = resource_usage.get("input_bytes")
    if (
        type(input_bytes) is not int
        or not 1 <= input_bytes <= _RESOURCE_LIMITS["input_bytes"]
    ):
        raise MmcifWriteError(
            "unsupported_resource_metadata",
            "input_bytes is outside the parser limit",
            location="metadata.mmcif.resource_usage.input_bytes",
        )
    expected_token_count = _expected_output_token_count(
        atom_site_headers,
        system.atom_count,
        entity_row_count=category_state.entity_row_count,
        struct_asym_row_count=category_state.struct_asym_row_count,
    )
    token_count = resource_usage.get("token_count")
    if type(token_count) is not int or token_count != expected_token_count:
        raise MmcifWriteError(
            "unsupported_resource_metadata",
            "source token count does not match the selected atom-site profile",
            location="metadata.mmcif.resource_usage.token_count",
        )
    atom_site_rows = resource_usage.get("atom_site_rows")
    if type(atom_site_rows) is not int or atom_site_rows != system.atom_count:
        raise MmcifWriteError(
            "unsupported_resource_metadata",
            "source atom-site row usage does not match atom_count",
            location="metadata.mmcif.resource_usage.atom_site_rows",
        )
    for field_name in (
        "missing_residue_evidence_rows",
        "missing_atom_evidence_rows",
        "total_missingness_evidence_rows",
        "missingness_preserved_items",
        "missingness_preserved_value_utf8_bytes",
    ):
        value = resource_usage.get(field_name)
        if type(value) is not int or value != 0:
            raise MmcifWriteError(
                "unsupported_missingness_evidence",
                "missingness resource usage must remain zero",
                location=f"metadata.mmcif.resource_usage.{field_name}",
            )
    return data_block, mmcif_metadata, expected_missingness


def _validated_token_payload(
    atom_site: Mapping[str, Any],
    header: str,
    *,
    location: str,
) -> tuple[str, dict[str, Any]]:
    payload = _require_exact_keys(
        atom_site.get(header),
        _CIF_TOKEN_PAYLOAD_KEYS,
        code="unsupported_atom_site_metadata",
        location=location,
    )
    if payload.get("quoted") is not False or payload.get("multiline") is not False:
        raise MmcifWriteError(
            "unsupported_atom_site_metadata",
            "core atom-site values must be parser-owned bare single-line tokens",
            location=location,
        )
    raw_value = payload.get("value")
    if header == _FORMAL_CHARGE_HEADER:
        if type(raw_value) is not str or not raw_value.isascii():
            raise MmcifWriteError(
                "unsupported_atom_site_metadata",
                "formal-charge marker must be an ASCII string",
                location=f"{location}.value",
            )
        value = raw_value
        if value not in {".", "?"}:
            formal_charge = _strict_integer_token(
                value,
                location=f"{location}.value",
            )
            if abs(formal_charge) > _MAX_ABS_FORMAL_CHARGE:
                raise MmcifWriteError(
                    "unsupported_formal_charge",
                    "formal charge exceeds the parser canonical magnitude limit",
                    location=f"{location}.value",
                )
    elif header == _INSERTION_CODE_HEADER:
        if type(raw_value) is not str or not raw_value.isascii():
            raise MmcifWriteError(
                "unsupported_atom_site_metadata",
                "insertion-code marker must be an ASCII string",
                location=f"{location}.value",
            )
        value = raw_value
        if value not in {".", "?"}:
            _safe_bare_token(value, location=f"{location}.value")
    elif header == _OCCUPANCY_HEADER:
        value = raw_value
        _strict_occupancy_token(value, location=f"{location}.value")
    elif header == _B_FACTOR_HEADER:
        value = raw_value
        _strict_b_factor_token(value, location=f"{location}.value")
    elif header == _LABEL_ALT_ID_HEADER:
        if type(raw_value) is not str or raw_value not in {".", "?"}:
            raise MmcifWriteError(
                "unsupported_altloc_selection",
                "common-core21 label_alt_id must be a bare missing marker",
                location=f"{location}.value",
            )
        value = raw_value
    elif header == "_atom_site.label_seq_id":
        if type(raw_value) is not str:
            raise MmcifWriteError(
                "unsupported_atom_site_metadata",
                "label_seq_id must be an exact string token",
                location=f"{location}.value",
            )
        value = raw_value
        if value not in {".", "?"}:
            _safe_bare_token(value, location=f"{location}.value")
    else:
        value = _safe_bare_token(raw_value, location=f"{location}.value")
    return value, {"value": value, "quoted": False, "multiline": False}


def _canonical_insertion_code_from_token(value: str, *, location: str) -> str:
    if value in {".", "?"}:
        return ""
    return _safe_bare_token(value, location=location)


def _preflight_insertion_code_state(
    system: AllAtomSystem,
    *,
    atom_site_headers: tuple[str, ...],
) -> None:
    """Reject raw/canonical insertion drift before attached digest checks."""

    insertion_header_present = _INSERTION_CODE_HEADER in atom_site_headers
    if not insertion_header_present:
        nonempty = next(
            (residue for residue in system.residues if residue.insertion_code != ""),
            None,
        )
        if nonempty is not None:
            raise MmcifWriteError(
                "unsupported_insertion_code",
                "canonical insertion code requires the selected insertion-code header",
                location=f"residues[{nonempty.index}].insertion_code",
            )
        return

    for atom in system.atoms:
        location = f"atoms[{atom.index}]"
        residue = system.residues[atom.residue_index]
        mmcif = atom.metadata.get("mmcif")
        if not isinstance(mmcif, Mapping):
            continue
        atom_site = mmcif.get("atom_site")
        if (
            not isinstance(atom_site, Mapping)
            or _INSERTION_CODE_HEADER not in atom_site
        ):
            continue
        raw_value, _ = _validated_token_payload(
            atom_site,
            _INSERTION_CODE_HEADER,
            location=(
                f"{location}.metadata.mmcif.atom_site[{_INSERTION_CODE_HEADER!r}]"
            ),
        )
        expected = _canonical_insertion_code_from_token(
            raw_value,
            location=(
                f"{location}.metadata.mmcif.atom_site[{_INSERTION_CODE_HEADER!r}].value"
            ),
        )
        if residue.insertion_code != expected:
            raise MmcifWriteError(
                "unsupported_insertion_code",
                "canonical residue insertion code does not match its raw atom-site marker",
                location=f"residues[{residue.index}].insertion_code",
            )


def _preflight_occupancy_state(
    system: AllAtomSystem,
    *,
    atom_site_headers: tuple[str, ...],
) -> None:
    """Reject raw/canonical occupancy drift before attached digest checks."""

    occupancy_header_present = _OCCUPANCY_HEADER in atom_site_headers
    if not occupancy_header_present:
        occupied = next(
            (atom for atom in system.atoms if atom.occupancy is not None),
            None,
        )
        if occupied is not None:
            raise MmcifWriteError(
                "unsupported_occupancy",
                "canonical occupancy requires the selected occupancy header",
                location=f"atoms[{occupied.index}].occupancy",
            )
        return

    for atom in system.atoms:
        location = f"atoms[{atom.index}]"
        mmcif = atom.metadata.get("mmcif")
        if not isinstance(mmcif, Mapping):
            continue
        atom_site = mmcif.get("atom_site")
        if not isinstance(atom_site, Mapping) or _OCCUPANCY_HEADER not in atom_site:
            raise MmcifWriteError(
                "unsupported_atom_site_headers",
                "selected occupancy profile is missing its atom-row payload",
                location=f"{location}.metadata.mmcif.atom_site",
            )
        raw_value, raw_payload = _validated_token_payload(
            atom_site,
            _OCCUPANCY_HEADER,
            location=(f"{location}.metadata.mmcif.atom_site[{_OCCUPANCY_HEADER!r}]"),
        )
        expected = _strict_occupancy_token(
            raw_value,
            location=(
                f"{location}.metadata.mmcif.atom_site[{_OCCUPANCY_HEADER!r}].value"
            ),
        )

        sites_by_model = mmcif.get("atom_site_by_model")
        if not isinstance(sites_by_model, (list, tuple)) or len(sites_by_model) != 1:
            raise MmcifWriteError(
                "unsupported_atom_site_headers",
                "selected occupancy profile requires one first-model payload",
                location=f"{location}.metadata.mmcif.atom_site_by_model",
            )
        model_entry = sites_by_model[0]
        model_values = (
            model_entry.get("values") if isinstance(model_entry, Mapping) else None
        )
        if (
            not isinstance(model_values, Mapping)
            or _OCCUPANCY_HEADER not in model_values
        ):
            raise MmcifWriteError(
                "unsupported_atom_site_headers",
                "selected occupancy profile is missing its first-model payload",
                location=(f"{location}.metadata.mmcif.atom_site_by_model[0].values"),
            )
        model_value, model_payload = _validated_token_payload(
            model_values,
            _OCCUPANCY_HEADER,
            location=(
                f"{location}.metadata.mmcif.atom_site_by_model[0]"
                f".values[{_OCCUPANCY_HEADER!r}]"
            ),
        )
        if not _exact_typed_structure_equal(model_payload, raw_payload):
            raise MmcifWriteError(
                "unsupported_atom_site_metadata",
                "first-model occupancy payload disagrees with the row payload",
                location=(
                    f"{location}.metadata.mmcif.atom_site_by_model[0]"
                    f".values[{_OCCUPANCY_HEADER!r}]"
                ),
            )
        model_expected = _strict_occupancy_token(
            model_value,
            location=(
                f"{location}.metadata.mmcif.atom_site_by_model[0]"
                f".values[{_OCCUPANCY_HEADER!r}].value"
            ),
        )
        if (model_expected is None) != (expected is None) or (
            model_expected is not None
            and expected is not None
            and _binary64_hex(model_expected) != _binary64_hex(expected)
        ):
            raise MmcifWriteError(
                "unsupported_occupancy",
                "first-model occupancy value disagrees with the row value",
                location=f"{location}.metadata.mmcif.atom_site_by_model[0]",
            )

        actual = atom.occupancy
        if expected is None:
            mismatch = actual is not None
        else:
            mismatch = type(actual) is not float or _binary64_hex(
                actual
            ) != _binary64_hex(expected)
        if mismatch:
            raise MmcifWriteError(
                "unsupported_occupancy",
                "canonical occupancy does not match its raw atom-site marker",
                location=f"{location}.occupancy",
            )


def _preflight_b_factor_state(
    system: AllAtomSystem,
    *,
    atom_site_headers: tuple[str, ...],
) -> None:
    """Reject raw/canonical B-factor drift before attached digest checks."""

    b_factor_header_present = _B_FACTOR_HEADER in atom_site_headers
    if not b_factor_header_present:
        measured = next(
            (atom for atom in system.atoms if atom.b_factor is not None),
            None,
        )
        if measured is not None:
            raise MmcifWriteError(
                "unsupported_b_factor",
                "canonical B factor requires the selected occupancy+B-factor profile",
                location=f"atoms[{measured.index}].b_factor",
            )
        return

    for atom in system.atoms:
        location = f"atoms[{atom.index}]"
        mmcif = atom.metadata.get("mmcif")
        if not isinstance(mmcif, Mapping):
            continue
        atom_site = mmcif.get("atom_site")
        if not isinstance(atom_site, Mapping) or _B_FACTOR_HEADER not in atom_site:
            raise MmcifWriteError(
                "unsupported_atom_site_headers",
                "selected occupancy+B-factor profile is missing its atom-row B-factor payload",
                location=f"{location}.metadata.mmcif.atom_site",
            )
        raw_value, raw_payload = _validated_token_payload(
            atom_site,
            _B_FACTOR_HEADER,
            location=f"{location}.metadata.mmcif.atom_site[{_B_FACTOR_HEADER!r}]",
        )
        expected = _strict_b_factor_token(
            raw_value,
            location=(
                f"{location}.metadata.mmcif.atom_site[{_B_FACTOR_HEADER!r}].value"
            ),
        )

        sites_by_model = mmcif.get("atom_site_by_model")
        if not isinstance(sites_by_model, (list, tuple)) or len(sites_by_model) != 1:
            raise MmcifWriteError(
                "unsupported_atom_site_headers",
                "selected occupancy+B-factor profile requires one first-model payload",
                location=f"{location}.metadata.mmcif.atom_site_by_model",
            )
        model_entry = sites_by_model[0]
        model_values = (
            model_entry.get("values") if isinstance(model_entry, Mapping) else None
        )
        if (
            not isinstance(model_values, Mapping)
            or _B_FACTOR_HEADER not in model_values
        ):
            raise MmcifWriteError(
                "unsupported_atom_site_headers",
                "selected occupancy+B-factor profile is missing its first-model B-factor payload",
                location=f"{location}.metadata.mmcif.atom_site_by_model[0].values",
            )
        model_value, model_payload = _validated_token_payload(
            model_values,
            _B_FACTOR_HEADER,
            location=(
                f"{location}.metadata.mmcif.atom_site_by_model[0]"
                f".values[{_B_FACTOR_HEADER!r}]"
            ),
        )
        if not _exact_typed_structure_equal(model_payload, raw_payload):
            raise MmcifWriteError(
                "unsupported_atom_site_metadata",
                "first-model B-factor payload disagrees with the row payload",
                location=(
                    f"{location}.metadata.mmcif.atom_site_by_model[0]"
                    f".values[{_B_FACTOR_HEADER!r}]"
                ),
            )
        model_expected = _strict_b_factor_token(
            model_value,
            location=(
                f"{location}.metadata.mmcif.atom_site_by_model[0]"
                f".values[{_B_FACTOR_HEADER!r}].value"
            ),
        )
        if (model_expected is None) != (expected is None) or (
            model_expected is not None
            and expected is not None
            and _binary64_hex(model_expected) != _binary64_hex(expected)
        ):
            raise MmcifWriteError(
                "unsupported_b_factor",
                "first-model B-factor value disagrees with the row value",
                location=f"{location}.metadata.mmcif.atom_site_by_model[0]",
            )

        actual = atom.b_factor
        if expected is None:
            mismatch = actual is not None
        else:
            mismatch = type(actual) is not float or _binary64_hex(
                actual
            ) != _binary64_hex(expected)
        if mismatch:
            raise MmcifWriteError(
                "unsupported_b_factor",
                "canonical B factor does not match its raw atom-site marker",
                location=f"{location}.b_factor",
            )


def _validate_atoms_residues_chains(
    system: AllAtomSystem,
    *,
    atom_site_header_profile: str,
    atom_site_headers: tuple[str, ...],
    category_state: _SelectedCategoryState,
) -> tuple[
    tuple[tuple[str, ...], ...],
    tuple[Mapping[str, Any], ...],
    tuple[Mapping[str, Any], ...],
    tuple[Mapping[str, Any], ...],
]:
    seen_source_ids: set[str] = set()
    seen_atom_identities: set[tuple[str, int, str, str, str]] = set()
    atom_indices_by_residue: list[list[int]] = [[] for _ in system.residues]
    residue_indices_by_chain: list[list[int]] = [[] for _ in system.chains]
    seen_residue_indices: set[int] = set()
    seen_chain_indices: set[int] = set()
    chain_indices_in_atom_order: list[int] = []
    row_tokens: list[tuple[str, ...]] = []
    atom_documents: list[Mapping[str, Any]] = []
    raw_sequence_tokens_by_residue: list[list[str]] = [[] for _ in system.residues]
    raw_auth_residue_tuples: list[list[tuple[str, str, str]]] = [
        [] for _ in system.residues
    ]
    entity_tuples_by_residue: list[list[tuple[str, str]]] = [
        [] for _ in system.residues
    ]
    auth_asym_ids_by_chain: list[set[str]] = [set() for _ in system.chains]
    nonpoly_residue_numbers: dict[tuple[str, str, str, str], int] = {}
    next_nonpoly_number_by_chain: dict[str, int] = {}
    common_identity = atom_site_header_profile == _COMMON_CORE21_IDENTITY_PROFILE
    non_coordinate_headers = tuple(
        header for header in atom_site_headers if header not in _COORDINATE_HEADERS
    )

    for expected_index, atom in enumerate(system.atoms):
        location = f"atoms[{expected_index}]"
        if atom.index != expected_index:
            raise MmcifWriteError(
                "unsupported_atom_topology",
                "canonical atom indices must be contiguous source order",
                location=f"{location}.index",
            )
        if atom.serial != expected_index + 1:
            raise MmcifWriteError(
                "unsupported_atom_serial",
                "parser-owned mmCIF serial must be synthesized index plus one",
                location=f"{location}.serial",
            )
        metadata = _require_exact_keys(
            atom.metadata,
            _ATOM_METADATA_KEYS,
            code="unsupported_atom_metadata",
            location=f"{location}.metadata",
        )
        record = metadata.get("source_record")
        if record not in {"ATOM", "HETATM"}:
            raise MmcifWriteError(
                "unsupported_record_class",
                "source_record must be ATOM or HETATM",
                location=f"{location}.metadata.source_record",
            )
        mmcif = _require_exact_keys(
            metadata.get("mmcif"),
            _ATOM_MMCIF_METADATA_KEYS,
            code="unsupported_atom_metadata",
            location=f"{location}.metadata.mmcif",
        )
        atom_site = _require_exact_keys(
            mmcif.get("atom_site"),
            frozenset(atom_site_headers),
            code="unsupported_atom_site_headers",
            location=f"{location}.metadata.mmcif.atom_site",
        )
        source_payloads: dict[str, dict[str, Any]] = {}
        source_values: dict[str, str] = {}
        for header in atom_site_headers:
            value, payload = _validated_token_payload(
                atom_site,
                header,
                location=f"{location}.metadata.mmcif.atom_site[{header!r}]",
            )
            source_values[header] = value
            source_payloads[header] = payload

        if mmcif.get("canonical_identity_namespace") != "label":
            raise MmcifWriteError(
                "unsupported_atom_metadata",
                "canonical identity namespace must remain label",
                location=f"{location}.metadata.mmcif.canonical_identity_namespace",
            )
        auth_identity = _require_exact_keys(
            mmcif.get("auth_identity"),
            _AUTH_IDENTITY_KEYS,
            code="unsupported_atom_metadata",
            location=f"{location}.metadata.mmcif.auth_identity",
        )
        if common_identity:
            expected_auth_identity = {
                "atom_id": source_values[_AUTH_ATOM_ID_HEADER],
                "comp_id": source_values[_AUTH_COMP_ID_HEADER],
                "asym_id": source_values[_AUTH_ASYM_ID_HEADER],
                "seq_id": source_values[_AUTH_SEQ_ID_HEADER],
                "alt_id": None,
            }
            if not _exact_typed_structure_equal(auth_identity, expected_auth_identity):
                raise MmcifWriteError(
                    "unsupported_auth_identity",
                    "complete auth quartet metadata must match its raw row tokens",
                    location=f"{location}.metadata.mmcif.auth_identity",
                )
            label_asym_id = source_values["_atom_site.label_asym_id"]
            label_entity_id = source_values[_LABEL_ENTITY_ID_HEADER]
            mapped_entity_id = category_state.asym_entities.get(label_asym_id)
            if mapped_entity_id is None:
                raise MmcifWriteError(
                    "unknown_label_asym_id",
                    "label_asym_id must resolve through the selected _struct_asym loop",
                    location=f"{location}.metadata.mmcif.atom_site",
                )
            if label_entity_id != mapped_entity_id:
                raise MmcifWriteError(
                    "conflicting_entity_identity",
                    "label_entity_id must equal the _struct_asym entity mapping",
                    location=f"{location}.metadata.mmcif.atom_site",
                )
            expected_entity_type = category_state.entity_types[label_entity_id]
            if (
                mmcif.get("entity_id") != label_entity_id
                or mmcif.get("entity_type") != expected_entity_type
            ):
                raise MmcifWriteError(
                    "unsupported_entity_identity",
                    "atom entity metadata must match the selected category join",
                    location=f"{location}.metadata.mmcif",
                )
        else:
            if mmcif.get("residue_sequence_source") != "label_seq_id":
                raise MmcifWriteError(
                    "unsupported_atom_metadata",
                    "residue sequence source must remain label_seq_id",
                    location=f"{location}.metadata.mmcif.residue_sequence_source",
                )
            if any(value is not None for value in auth_identity.values()):
                raise MmcifWriteError(
                    "unsupported_atom_metadata",
                    "atom-site-only profiles do not emit auth identity fields",
                    location=f"{location}.metadata.mmcif.auth_identity",
                )
            if mmcif.get("entity_id") != "" or mmcif.get("entity_type") != "unknown":
                raise MmcifWriteError(
                    "unsupported_atom_metadata",
                    "atom-site-only profiles require absent entity identity",
                    location=f"{location}.metadata.mmcif",
                )

        source_atom_site_id = mmcif.get("source_atom_site_id")
        if (
            type(source_atom_site_id) is not str
            or source_atom_site_id != source_values["_atom_site.id"]
        ):
            raise MmcifWriteError(
                "unsupported_atom_site_metadata",
                "source atom-site ID marker does not match the core row token",
                location=f"{location}.metadata.mmcif.source_atom_site_id",
            )
        if source_atom_site_id in seen_source_ids:
            raise MmcifWriteError(
                "duplicate_atom_site_id",
                "source atom-site IDs must be globally unique",
                location=f"{location}.metadata.mmcif.source_atom_site_id",
            )
        seen_source_ids.add(source_atom_site_id)

        ids_by_model = mmcif.get("atom_site_id_by_model")
        if not isinstance(ids_by_model, (list, tuple)) or len(ids_by_model) != 1:
            raise MmcifWriteError(
                "unsupported_model_id",
                "atom-site ID marker must contain exactly model ID 1",
                location=f"{location}.metadata.mmcif.atom_site_id_by_model",
            )
        model_id_entry = _require_exact_keys(
            ids_by_model[0],
            _MODEL_ATOM_SITE_ID_KEYS,
            code="unsupported_atom_site_metadata",
            location=f"{location}.metadata.mmcif.atom_site_id_by_model[0]",
        )
        if (
            type(model_id_entry.get("model_id")) is not int
            or model_id_entry.get("model_id") != 1
            or type(model_id_entry.get("atom_site_id")) is not str
            or model_id_entry.get("atom_site_id") != source_atom_site_id
        ):
            raise MmcifWriteError(
                "unsupported_model_id",
                "atom-site ID marker must agree with model ID 1 and source ID",
                location=f"{location}.metadata.mmcif.atom_site_id_by_model[0]",
            )

        sites_by_model = mmcif.get("atom_site_by_model")
        if not isinstance(sites_by_model, (list, tuple)) or len(sites_by_model) != 1:
            raise MmcifWriteError(
                "unsupported_model_id",
                "atom-site values marker must contain exactly model ID 1",
                location=f"{location}.metadata.mmcif.atom_site_by_model",
            )
        model_site_entry = _require_exact_keys(
            sites_by_model[0],
            _MODEL_ATOM_SITE_KEYS,
            code="unsupported_atom_site_metadata",
            location=f"{location}.metadata.mmcif.atom_site_by_model[0]",
        )
        if (
            type(model_site_entry.get("model_id")) is not int
            or model_site_entry.get("model_id") != 1
        ):
            raise MmcifWriteError(
                "unsupported_model_id",
                "atom-site values marker must use model ID 1",
                location=f"{location}.metadata.mmcif.atom_site_by_model[0].model_id",
            )
        model_values = _require_exact_keys(
            model_site_entry.get("values"),
            frozenset(atom_site_headers),
            code="unsupported_atom_site_headers",
            location=f"{location}.metadata.mmcif.atom_site_by_model[0].values",
        )
        model_source_values: dict[str, str] = {}
        for header in atom_site_headers:
            model_value, model_payload = _validated_token_payload(
                model_values,
                header,
                location=(
                    f"{location}.metadata.mmcif.atom_site_by_model[0]"
                    f".values[{header!r}]"
                ),
            )
            model_source_values[header] = model_value
            if (
                header not in _COORDINATE_HEADERS
                and model_payload != source_payloads[header]
            ):
                raise MmcifWriteError(
                    "unsupported_atom_site_metadata",
                    "first-model atom-site payload disagrees with the row payload",
                    location=(
                        f"{location}.metadata.mmcif.atom_site_by_model[0]"
                        f".values[{header!r}]"
                    ),
                )

        residue = system.residues[atom.residue_index]
        chain = system.chains[residue.chain_index]
        if source_values["_atom_site.group_pdb"].upper() != record:
            raise MmcifWriteError(
                "unsupported_record_class",
                "group_PDB token does not match source_record",
                location=f"{location}.metadata.mmcif.atom_site",
            )
        try:
            source_element = canonical_element_symbol(
                source_values["_atom_site.type_symbol"]
            )
        except (TypeError, ValueError) as exc:
            raise MmcifWriteError(
                "unsupported_element",
                "type_symbol is not a canonical element",
                location=f"{location}.metadata.mmcif.atom_site",
            ) from exc
        if (
            source_element != atom.element
            or atomic_number_for_element(atom.element) != atom.atomic_number
        ):
            raise MmcifWriteError(
                "unsupported_element",
                "type_symbol, canonical element, and atomic number disagree",
                location=f"{location}.element",
            )
        if source_values["_atom_site.label_atom_id"] != atom.name:
            raise MmcifWriteError(
                "unsupported_atom_site_metadata",
                "label_atom_id does not match canonical atom name",
                location=f"{location}.name",
            )
        if source_values["_atom_site.label_comp_id"].upper() != residue.name:
            raise MmcifWriteError(
                "unsupported_atom_site_metadata",
                "label_comp_id does not match canonical residue name",
                location=f"{location}.residue_index",
            )
        if source_values["_atom_site.label_asym_id"] != chain.chain_id:
            raise MmcifWriteError(
                "unsupported_atom_site_metadata",
                "label_asym_id does not match canonical chain ID",
                location=f"{location}.residue_index",
            )
        sequence_token = source_values["_atom_site.label_seq_id"]
        if common_identity:
            entity_id = source_values[_LABEL_ENTITY_ID_HEADER]
            entity_type = category_state.entity_types[entity_id]
            auth_seq_id = source_values[_AUTH_SEQ_ID_HEADER]
            if entity_type == "polymer":
                if sequence_token in {".", "?"}:
                    raise MmcifWriteError(
                        "unsupported_residue_number",
                        "polymer atoms require a positive label_seq_id",
                        location=f"{location}.metadata.mmcif.atom_site",
                    )
                sequence_number = _strict_integer_token(
                    sequence_token,
                    location=(
                        f"{location}.metadata.mmcif.atom_site"
                        "['_atom_site.label_seq_id']"
                    ),
                )
                sequence_source = "label_seq_id"
                if sequence_number < 1:
                    raise MmcifWriteError(
                        "unsupported_residue_number",
                        "polymer label_seq_id must be positive",
                        location=f"{location}.metadata.mmcif.atom_site",
                    )
            else:
                if sequence_token not in {".", "?"}:
                    raise MmcifWriteError(
                        "unsupported_residue_number",
                        "non-polymer and water atoms require a missing label_seq_id marker",
                        location=f"{location}.metadata.mmcif.atom_site",
                    )
                sequence_source = "synthetic_negative_from_nonpolymer_auth_identity"
                nonpoly_key = (
                    chain.chain_id,
                    auth_seq_id,
                    residue.insertion_code,
                    residue.name,
                )
                if nonpoly_key not in nonpoly_residue_numbers:
                    next_number = next_nonpoly_number_by_chain.get(chain.chain_id, -1)
                    nonpoly_residue_numbers[nonpoly_key] = next_number
                    next_nonpoly_number_by_chain[chain.chain_id] = next_number - 1
                sequence_number = nonpoly_residue_numbers[nonpoly_key]
            if (
                sequence_number != residue.sequence_number
                or mmcif.get("residue_sequence_source") != sequence_source
            ):
                raise MmcifWriteError(
                    "unsupported_residue_number",
                    "canonical sequence carrier does not match label/auth/entity source state",
                    location=f"{location}.metadata.mmcif.residue_sequence_source",
                )
        else:
            sequence_number = _strict_integer_token(
                sequence_token,
                location=(
                    f"{location}.metadata.mmcif.atom_site['_atom_site.label_seq_id']"
                ),
            )
            sequence_source = "label_seq_id"
            if sequence_number < 1 or sequence_number != residue.sequence_number:
                raise MmcifWriteError(
                    "unsupported_residue_number",
                    "label_seq_id must be positive and match the canonical residue",
                    location=f"{location}.metadata.mmcif.atom_site",
                )
        model_id = _strict_integer_token(
            source_values["_atom_site.pdbx_pdb_model_num"],
            location=(
                f"{location}.metadata.mmcif.atom_site['_atom_site.pdbx_pdb_model_num']"
            ),
        )
        if model_id != 1:
            raise MmcifWriteError(
                "unsupported_model_id",
                "every atom-site row must carry model ID 1",
                location=f"{location}.metadata.mmcif.atom_site",
            )

        coordinate_tokens: list[str] = []
        coordinate_hex: list[str] = []
        for axis_index, (axis, header) in enumerate(
            zip(("x", "y", "z"), _COORDINATE_HEADERS, strict=True)
        ):
            current = float(system.coordinates[0, expected_index, axis_index].item())
            if not math.isfinite(current):
                raise MmcifWriteError(
                    "nonfinite_coordinate",
                    "current coordinate must be finite",
                    location=f"coordinates[0,{expected_index},{axis}]",
                )
            parsed_source = _strict_coordinate_token(
                source_values[header],
                location=f"{location}.metadata.mmcif.atom_site[{header!r}]",
            )
            if _binary64_hex(parsed_source) != _binary64_hex(current):
                raise MmcifWriteError(
                    "coordinate_metadata_mismatch",
                    "raw coordinate token does not encode the current binary64 value",
                    location=f"coordinates[0,{expected_index},{axis}]",
                )
            parsed_model_source = _strict_coordinate_token(
                model_source_values[header],
                location=(
                    f"{location}.metadata.mmcif.atom_site_by_model[0]"
                    f".values[{header!r}]"
                ),
            )
            if _binary64_hex(parsed_model_source) != _binary64_hex(current):
                raise MmcifWriteError(
                    "coordinate_metadata_mismatch",
                    "model coordinate token does not encode the current binary64 value",
                    location=f"coordinates[0,{expected_index},{axis}]",
                )
            token = repr(current)
            reparsed_token = _strict_coordinate_token(
                token,
                location=f"coordinates[0,{expected_index},{axis}]",
            )
            if _binary64_hex(reparsed_token) != _binary64_hex(current):
                raise MmcifWriteError(
                    "coordinate_token_round_trip_failed",
                    "shortest coordinate token did not preserve binary64 state",
                    location=f"coordinates[0,{expected_index},{axis}]",
                )
            coordinate_tokens.append(token)
            coordinate_hex.append(_binary64_hex(current))

        if atom.altloc:
            raise MmcifWriteError(
                "unsupported_altloc_selection",
                "mmCIF writer v1 requires blank canonical altloc state",
                location=f"{location}.altloc",
            )
        if _OCCUPANCY_HEADER in atom_site_headers:
            expected_occupancy = _strict_occupancy_token(
                source_values[_OCCUPANCY_HEADER],
                location=(
                    f"{location}.metadata.mmcif.atom_site[{_OCCUPANCY_HEADER!r}].value"
                ),
            )
        else:
            expected_occupancy = None
        if expected_occupancy is None:
            occupancy_mismatch = atom.occupancy is not None
        else:
            occupancy_mismatch = type(atom.occupancy) is not float or _binary64_hex(
                atom.occupancy
            ) != _binary64_hex(expected_occupancy)
        if occupancy_mismatch:
            raise MmcifWriteError(
                "unsupported_occupancy",
                "canonical occupancy does not match its selected-profile source marker",
                location=f"{location}.occupancy",
            )
        if _B_FACTOR_HEADER in atom_site_headers:
            expected_b_factor = _strict_b_factor_token(
                source_values[_B_FACTOR_HEADER],
                location=(
                    f"{location}.metadata.mmcif.atom_site[{_B_FACTOR_HEADER!r}].value"
                ),
            )
        else:
            expected_b_factor = None
        if expected_b_factor is None:
            b_factor_mismatch = atom.b_factor is not None
        else:
            b_factor_mismatch = type(atom.b_factor) is not float or _binary64_hex(
                atom.b_factor
            ) != _binary64_hex(expected_b_factor)
        if b_factor_mismatch:
            raise MmcifWriteError(
                "unsupported_b_factor",
                "canonical B factor does not match its selected-profile source marker",
                location=f"{location}.b_factor",
            )
        if atom.partial_charge_e is not None:
            raise MmcifWriteError(
                "unsupported_partial_charge",
                "mmCIF writer cannot preserve partial charge in the core subset",
                location=f"{location}.partial_charge_e",
            )
        if atom.mass_da is not None:
            raise MmcifWriteError(
                "unsupported_atom_mass",
                "mmCIF writer cannot preserve atom mass in the core subset",
                location=f"{location}.mass_da",
            )
        if atom.isotope_mass_number is not None:
            raise MmcifWriteError(
                "unsupported_isotope",
                "mmCIF writer cannot preserve isotope state in the core subset",
                location=f"{location}.isotope_mass_number",
            )
        if atom.atom_map is not None:
            raise MmcifWriteError(
                "unsupported_atom_map",
                "mmCIF writer cannot preserve atom-map state in the core subset",
                location=f"{location}.atom_map",
            )
        if atom.aromatic:
            raise MmcifWriteError(
                "unsupported_aromatic_atom",
                "strict mmCIF parser does not produce aromatic atom state",
                location=f"{location}.aromatic",
            )
        if atom.stereo != "unspecified":
            raise MmcifWriteError(
                "unsupported_atom_stereo",
                "strict mmCIF parser does not produce atom stereochemistry",
                location=f"{location}.stereo",
            )
        expected_hydrogen_origin = "source" if atom.element == "H" else "not_hydrogen"
        if metadata.get("hydrogen_origin") != expected_hydrogen_origin:
            raise MmcifWriteError(
                "unsupported_atom_metadata",
                "hydrogen origin marker does not match the element",
                location=f"{location}.metadata.hydrogen_origin",
            )
        if _FORMAL_CHARGE_HEADER not in atom_site_headers:
            expected_formal_charge = 0
            expected_formal_charge_known = False
            expected_formal_charge_source = "missing_in_mmcif"
            expected_formal_charge_interpretation = "placeholder_zero_unknown"
        else:
            charge_token = source_values[_FORMAL_CHARGE_HEADER]
            if charge_token in {".", "?"}:
                expected_formal_charge = 0
                expected_formal_charge_known = False
                expected_formal_charge_source = "missing_in_mmcif"
                expected_formal_charge_interpretation = "placeholder_zero_unknown"
            else:
                expected_formal_charge = _strict_integer_token(
                    charge_token,
                    location=(
                        f"{location}.metadata.mmcif.atom_site"
                        f"[{_FORMAL_CHARGE_HEADER!r}]"
                    ),
                )
                if abs(expected_formal_charge) > _MAX_ABS_FORMAL_CHARGE:
                    raise MmcifWriteError(
                        "unsupported_formal_charge",
                        "formal charge exceeds the parser canonical magnitude limit",
                        location=f"{location}.formal_charge",
                    )
                expected_formal_charge_known = True
                expected_formal_charge_source = _FORMAL_CHARGE_HEADER
                expected_formal_charge_interpretation = "explicit"
        if (
            type(atom.formal_charge) is not int
            or atom.formal_charge != expected_formal_charge
            or atom.formal_charge_known is not expected_formal_charge_known
            or metadata.get("formal_charge_known") is not expected_formal_charge_known
            or metadata.get("formal_charge_source") != expected_formal_charge_source
            or metadata.get("formal_charge_interpretation")
            != expected_formal_charge_interpretation
        ):
            raise MmcifWriteError(
                "unsupported_formal_charge",
                "canonical charge state does not match its source formal-charge marker",
                location=f"{location}.formal_charge",
            )
        if _INSERTION_CODE_HEADER in atom_site_headers:
            insertion_token = source_values[_INSERTION_CODE_HEADER]
            expected_insertion_code = _canonical_insertion_code_from_token(
                insertion_token,
                location=(
                    f"{location}.metadata.mmcif.atom_site"
                    f"[{_INSERTION_CODE_HEADER!r}].value"
                ),
            )
        else:
            expected_insertion_code = ""
        if residue.insertion_code != expected_insertion_code:
            raise MmcifWriteError(
                "unsupported_insertion_code",
                "canonical residue insertion code does not match its source marker profile",
                location=f"residues[{residue.index}].insertion_code",
            )
        expected_auth_asym_id = (
            source_values[_AUTH_ASYM_ID_HEADER] if common_identity else ""
        )
        if metadata.get("mmcif_auth_asym_id") != expected_auth_asym_id:
            raise MmcifWriteError(
                "unsupported_atom_metadata",
                "mmCIF auth asym marker does not match the selected profile",
                location=f"{location}.metadata.mmcif_auth_asym_id",
            )

        identity = (
            chain.chain_id,
            residue.sequence_number,
            residue.insertion_code,
            residue.name,
            atom.name,
        )
        if identity in seen_atom_identities:
            raise MmcifWriteError(
                "duplicate_atom_identity",
                "label atom-site identity must be unique before emission",
                location=location,
            )
        seen_atom_identities.add(identity)
        atom_indices_by_residue[residue.index].append(atom.index)
        raw_sequence_tokens_by_residue[residue.index].append(sequence_token)
        if common_identity:
            raw_auth_residue_tuples[residue.index].append(
                (
                    source_values[_AUTH_COMP_ID_HEADER],
                    source_values[_AUTH_ASYM_ID_HEADER],
                    source_values[_AUTH_SEQ_ID_HEADER],
                )
            )
            entity_tuples_by_residue[residue.index].append(
                (
                    source_values[_LABEL_ENTITY_ID_HEADER],
                    category_state.entity_types[source_values[_LABEL_ENTITY_ID_HEADER]],
                )
            )
            auth_asym_ids_by_chain[chain.index].add(source_values[_AUTH_ASYM_ID_HEADER])
        if chain.index not in seen_chain_indices:
            seen_chain_indices.add(chain.index)
            chain_indices_in_atom_order.append(chain.index)
        if residue.index not in seen_residue_indices:
            seen_residue_indices.add(residue.index)
            residue_indices_by_chain[chain.index].append(residue.index)

        emitted_row = []
        for header in atom_site_headers:
            if header in _COORDINATE_HEADERS:
                emitted_row.append(coordinate_tokens[_COORDINATE_HEADERS.index(header)])
            else:
                emitted_row.append(source_values[header])
        row_tokens.append(tuple(emitted_row))
        atom_documents.append(
            {
                "index": atom.index,
                "serial": atom.serial,
                "record": record,
                "name": atom.name,
                "element": atom.element,
                "atomic_number": atom.atomic_number,
                "residue_index": atom.residue_index,
                "formal_charge": expected_formal_charge,
                "formal_charge_known": expected_formal_charge_known,
                "partial_charge_e": None,
                "mass_da": None,
                "isotope_mass_number": None,
                "atom_map": None,
                "altloc": "",
                "occupancy": expected_occupancy,
                "occupancy_ieee754_binary64_be": (
                    None
                    if expected_occupancy is None
                    else _binary64_hex(expected_occupancy)
                ),
                "b_factor": expected_b_factor,
                "b_factor_ieee754_binary64_be": (
                    None
                    if expected_b_factor is None
                    else _binary64_hex(expected_b_factor)
                ),
                "aromatic": False,
                "stereo": "unspecified",
                "coordinates_ieee754_binary64_be": coordinate_hex,
                "coordinate_tokens_shortest_round_trip": coordinate_tokens,
                "metadata": {
                    "source_record": record,
                    "formal_charge_known": expected_formal_charge_known,
                    "formal_charge_source": expected_formal_charge_source,
                    "formal_charge_interpretation": (
                        expected_formal_charge_interpretation
                    ),
                    "mmcif_auth_asym_id": expected_auth_asym_id,
                    "mmcif": {
                        "noncoordinate_atom_site": {
                            header: source_payloads[header]
                            for header in non_coordinate_headers
                        },
                        "canonical_identity_namespace": "label",
                        "residue_sequence_source": sequence_source,
                        "auth_identity": dict(auth_identity),
                        "entity_id": (
                            source_values[_LABEL_ENTITY_ID_HEADER]
                            if common_identity
                            else ""
                        ),
                        "entity_type": (
                            category_state.entity_types[
                                source_values[_LABEL_ENTITY_ID_HEADER]
                            ]
                            if common_identity
                            else "unknown"
                        ),
                        "source_atom_site_id": source_atom_site_id,
                        "atom_site_id_by_model": [dict(model_id_entry)],
                        "model_id": 1,
                    },
                    "hydrogen_origin": expected_hydrogen_origin,
                },
            }
        )

    residue_documents: list[Mapping[str, Any]] = []
    seen_residue_bases: set[tuple[int, int, str]] = set()
    for expected_index, residue in enumerate(system.residues):
        location = f"residues[{expected_index}]"
        if residue.index != expected_index:
            raise MmcifWriteError(
                "unsupported_residue_topology",
                "canonical residue indices must be contiguous parser order",
                location=f"{location}.index",
            )
        metadata = _require_exact_keys(
            residue.metadata,
            _RESIDUE_METADATA_KEYS,
            code="unsupported_residue_metadata",
            location=f"{location}.metadata",
        )
        _safe_bare_token(residue.name, location=f"{location}.name")
        if residue.name != residue.name.upper():
            raise MmcifWriteError(
                "unsupported_residue_name",
                "parser-owned residue names must be uppercase",
                location=f"{location}.name",
            )
        if not common_identity and residue.sequence_number < 1:
            raise MmcifWriteError(
                "unsupported_residue_number",
                "core label_seq_id residue numbers must be positive",
                location=f"{location}.sequence_number",
            )
        if (
            _INSERTION_CODE_HEADER not in atom_site_headers
            and residue.insertion_code != ""
        ):
            raise MmcifWriteError(
                "unsupported_insertion_code",
                "canonical insertion code requires the selected insertion-code header",
                location=f"{location}.insertion_code",
            )
        if residue.insertion_code:
            _safe_bare_token(
                residue.insertion_code,
                location=f"{location}.insertion_code",
            )
        expected_atom_indices = tuple(atom_indices_by_residue[residue.index])
        if residue.atom_indices != expected_atom_indices or not expected_atom_indices:
            raise MmcifWriteError(
                "unsupported_residue_topology",
                "residue atom_indices do not match ordered canonical atoms",
                location=f"{location}.atom_indices",
            )
        source_record = "HETATM" if residue.hetero else "ATOM"
        raw_sequence_tokens = raw_sequence_tokens_by_residue[residue.index]
        if not common_identity and len(set(raw_sequence_tokens)) != 1:
            raise MmcifWriteError(
                "unsupported_residue_metadata",
                "all atoms in one residue must share the label_seq_id spelling",
                location=location,
            )
        raw_sequence_token = raw_sequence_tokens[0]
        if common_identity:
            auth_tuples = raw_auth_residue_tuples[residue.index]
            entity_tuples = entity_tuples_by_residue[residue.index]
            if len(set(auth_tuples)) != 1:
                raise MmcifWriteError(
                    "inconsistent_auth_residue_identity",
                    "auth comp/asym/seq must be consistent within one label residue",
                    location=location,
                )
            if len(set(entity_tuples)) != 1:
                raise MmcifWriteError(
                    "conflicting_entity_identity",
                    "entity identity must be consistent within one label residue",
                    location=location,
                )
            auth_comp_id, auth_asym_id, auth_seq_id = auth_tuples[0]
            del auth_comp_id, auth_asym_id
            entity_id, entity_type = entity_tuples[0]
            expected_sequence_source = (
                "label_seq_id"
                if entity_type == "polymer"
                else "synthetic_negative_from_nonpolymer_auth_identity"
            )
            expected_label_seq_id = (
                raw_sequence_token if raw_sequence_token not in {".", "?"} else None
            )
            if (
                residue.entity_type != entity_type
                or metadata.get("source_record") != source_record
                or metadata.get("entity_id") != entity_id
                or metadata.get("source_residue_namespace") != ""
                or metadata.get("entity_type_basis") != "mmcif_entity_category"
                or metadata.get("mmcif_label_seq_id") != expected_label_seq_id
                or metadata.get("mmcif_auth_seq_id") != auth_seq_id
                or metadata.get("canonical_sequence_source") != expected_sequence_source
                or any(
                    system.atoms[index].metadata.get("source_record") != source_record
                    for index in expected_atom_indices
                )
            ):
                raise MmcifWriteError(
                    "unsupported_residue_metadata",
                    "residue metadata does not match label/auth/entity source state",
                    location=location,
                )
        elif (
            residue.entity_type != "unknown"
            or metadata.get("source_record") != source_record
            or metadata.get("entity_id") != ""
            or metadata.get("source_residue_namespace") != ""
            or metadata.get("entity_type_basis") != "unresolved_from_source"
            or metadata.get("mmcif_label_seq_id") != raw_sequence_token
            or metadata.get("mmcif_auth_seq_id") is not None
            or metadata.get("canonical_sequence_source") != "label_seq_id"
            or any(
                system.atoms[index].metadata.get("source_record") != source_record
                for index in expected_atom_indices
            )
        ):
            raise MmcifWriteError(
                "unsupported_residue_metadata",
                "residue metadata does not match parser-owned core-label state",
                location=location,
            )
        base = (
            residue.chain_index,
            residue.sequence_number,
            residue.insertion_code,
        )
        if base in seen_residue_bases:
            raise MmcifWriteError(
                "unsupported_residue_topology",
                "residue base identity must be unique within a chain",
                location=location,
            )
        seen_residue_bases.add(base)
        residue_documents.append(
            {
                "index": residue.index,
                "name": residue.name,
                "chain_index": residue.chain_index,
                "sequence_number": residue.sequence_number,
                "atom_indices": list(residue.atom_indices),
                "insertion_code": residue.insertion_code,
                "entity_type": residue.entity_type,
                "hetero": residue.hetero,
                "metadata": dict(metadata),
            }
        )

    canonical_chain_indices = tuple(chain.index for chain in system.chains)
    if tuple(chain_indices_in_atom_order) != canonical_chain_indices:
        raise MmcifWriteError(
            "unsupported_chain_topology",
            "canonical chain indices must follow first occurrence in atom order",
            location="chains",
        )
    parser_residue_order = tuple(
        residue_index
        for chain_index in chain_indices_in_atom_order
        for residue_index in residue_indices_by_chain[chain_index]
    )
    canonical_residue_indices = tuple(residue.index for residue in system.residues)
    if parser_residue_order != canonical_residue_indices:
        raise MmcifWriteError(
            "unsupported_residue_topology",
            "canonical residue indices must match parser first-occurrence order",
            location="residues",
        )

    chain_documents: list[Mapping[str, Any]] = []
    seen_chain_ids: set[str] = set()
    for expected_index, chain in enumerate(system.chains):
        location = f"chains[{expected_index}]"
        if chain.index != expected_index:
            raise MmcifWriteError(
                "unsupported_chain_topology",
                "canonical chain indices must be contiguous parser order",
                location=f"{location}.index",
            )
        metadata = _require_exact_keys(
            chain.metadata,
            _CHAIN_METADATA_KEYS,
            code="unsupported_chain_metadata",
            location=f"{location}.metadata",
        )
        chain_id = _safe_bare_token(chain.chain_id, location=f"{location}.chain_id")
        if chain_id in seen_chain_ids:
            raise MmcifWriteError(
                "unsupported_chain_topology",
                "label_asym_id chain IDs must be unique",
                location=f"{location}.chain_id",
            )
        seen_chain_ids.add(chain_id)
        expected_residue_indices = tuple(residue_indices_by_chain[chain.index])
        if (
            chain.residue_indices != expected_residue_indices
            or not expected_residue_indices
        ):
            raise MmcifWriteError(
                "unsupported_chain_topology",
                "chain residue_indices do not match ordered residues",
                location=f"{location}.residue_indices",
            )
        auth_asym_ids = metadata.get("auth_asym_ids")
        expected_chain_entity_id = (
            category_state.asym_entities.get(chain_id, "") if common_identity else ""
        )
        expected_auth_asym_ids = (
            tuple(sorted(auth_asym_ids_by_chain[chain.index]))
            if common_identity
            else ()
        )
        if (
            chain.entity_id != expected_chain_entity_id
            or metadata.get("source_format") != "mmcif"
            or not isinstance(auth_asym_ids, (list, tuple))
            or tuple(auth_asym_ids) != expected_auth_asym_ids
        ):
            raise MmcifWriteError(
                "unsupported_chain_metadata",
                "chain metadata does not match selected label/auth/entity state",
                location=location,
            )
        chain_documents.append(
            {
                "index": chain.index,
                "chain_id": chain_id,
                "residue_indices": list(chain.residue_indices),
                "entity_id": expected_chain_entity_id,
                "metadata": {
                    "source_format": "mmcif",
                    "auth_asym_ids": list(expected_auth_asym_ids),
                },
            }
        )

    return (
        tuple(row_tokens),
        tuple(atom_documents),
        tuple(residue_documents),
        tuple(chain_documents),
    )


def _validated_identity_category_payload(
    value: Any,
    *,
    location: str,
) -> tuple[str, dict[str, Any]]:
    payload = _require_exact_keys(
        value,
        _CIF_TOKEN_PAYLOAD_KEYS,
        code="unsupported_identity_category_payload",
        location=location,
    )
    if payload.get("quoted") is not False or payload.get("multiline") is not False:
        raise MmcifWriteError(
            "unsupported_identity_category_payload",
            "selected identity-category values must be bare single-line tokens",
            location=location,
        )
    token = _safe_bare_token(payload.get("value"), location=f"{location}.value")
    return token, {"value": token, "quoted": False, "multiline": False}


def _selected_category_state(
    mmcif: Mapping[str, Any],
    *,
    atom_site_header_profile: str,
    atom_count: int,
) -> _SelectedCategoryState:
    inventory_value = mmcif.get("category_inventory")
    if not isinstance(inventory_value, (list, tuple)):
        raise MmcifWriteError(
            "unsupported_category_inventory",
            "category inventory must be an ordered sequence",
            location="metadata.mmcif.category_inventory",
        )
    inventory_by_category: dict[str, Mapping[str, Any]] = {}
    for index, raw_entry in enumerate(inventory_value):
        entry = _require_exact_keys(
            raw_entry,
            _CATEGORY_INVENTORY_KEYS,
            code="unsupported_category_inventory",
            location=f"metadata.mmcif.category_inventory[{index}]",
        )
        category = entry.get("category")
        if type(category) is not str or category in inventory_by_category:
            raise MmcifWriteError(
                "unsupported_category_inventory",
                "category inventory names must be unique exact strings",
                location=f"metadata.mmcif.category_inventory[{index}].category",
            )
        inventory_by_category[category] = entry

    preserved_value = mmcif.get("preserved_category_payloads")
    if not isinstance(preserved_value, (list, tuple)):
        raise MmcifWriteError(
            "unsupported_preserved_category_payloads",
            "preserved category payloads must be an ordered sequence",
            location="metadata.mmcif.preserved_category_payloads",
        )

    if atom_site_header_profile != _COMMON_CORE21_IDENTITY_PROFILE:
        expected_inventory = {
            "category": "_atom_site",
            "scalar_item_count": 0,
            "loop_count": 1,
            "row_count": atom_count,
            "policy": "interpreted_with_source_values_preserved",
        }
        if frozenset(inventory_by_category) != {
            "_atom_site"
        } or not _exact_typed_structure_equal(
            inventory_by_category["_atom_site"], expected_inventory
        ):
            raise MmcifWriteError(
                "unsupported_category_inventory",
                "atom-site-only profiles require exactly one _atom_site loop",
                location="metadata.mmcif.category_inventory",
            )
        if tuple(preserved_value):
            raise MmcifWriteError(
                "unsupported_preserved_category_payloads",
                "atom-site-only profiles require no preserved category payloads",
                location="metadata.mmcif.preserved_category_payloads",
            )
        return _SelectedCategoryState(
            category_profile=_ATOM_SITE_ONLY_CATEGORY_PROFILE,
            identity_profile=_NO_AUTH_ENTITY_IDENTITY_PROFILE,
            entity_rows=(),
            struct_asym_rows=(),
            entity_documents=(),
            struct_asym_documents=(),
            entity_types={},
            asym_entities={},
            category_inventory=(expected_inventory,),
        )

    payload_by_category: dict[str, Mapping[str, Any]] = {}
    for index, raw_payload in enumerate(preserved_value):
        payload = _require_exact_keys(
            raw_payload,
            _PRESERVED_CATEGORY_KEYS,
            code="unsupported_preserved_category_payloads",
            location=f"metadata.mmcif.preserved_category_payloads[{index}]",
        )
        category = payload.get("category")
        if type(category) is not str or category in payload_by_category:
            raise MmcifWriteError(
                "unsupported_preserved_category_payloads",
                "preserved category names must be unique exact strings",
                location=(
                    f"metadata.mmcif.preserved_category_payloads[{index}].category"
                ),
            )
        payload_by_category[category] = payload
    if frozenset(payload_by_category) != {"_entity", "_struct_asym"}:
        raise MmcifWriteError(
            "unsupported_preserved_category_payloads",
            "common-core21 requires exactly _entity and _struct_asym payloads",
            location="metadata.mmcif.preserved_category_payloads",
        )

    def category_rows(
        category: str,
        headers: tuple[str, str],
        *,
        limit: int,
    ) -> tuple[tuple[tuple[str, str], ...], tuple[tuple[dict[str, Any], ...], ...]]:
        payload = payload_by_category[category]
        if payload.get("policy") != "partially_interpreted":
            raise MmcifWriteError(
                "unsupported_preserved_category_payloads",
                f"{category} must retain the parser partially-interpreted policy",
                location=f"metadata.mmcif.preserved_category_payloads[{category!r}]",
            )
        scalar_items = payload.get("scalar_items")
        loops = payload.get("loops")
        if (
            not isinstance(scalar_items, (list, tuple))
            or tuple(scalar_items)
            or not isinstance(loops, (list, tuple))
            or len(loops) != 1
        ):
            raise MmcifWriteError(
                "unsupported_preserved_category_payloads",
                f"{category} must be exactly one loop and no scalar items",
                location=f"metadata.mmcif.preserved_category_payloads[{category!r}]",
            )
        loop = _require_exact_keys(
            loops[0],
            _PRESERVED_LOOP_KEYS,
            code="unsupported_preserved_category_payloads",
            location=(
                f"metadata.mmcif.preserved_category_payloads[{category!r}].loops[0]"
            ),
        )
        source_loop_index = loop.get("source_loop_index")
        if type(source_loop_index) is not int or source_loop_index < 0:
            raise MmcifWriteError(
                "unsupported_preserved_category_payloads",
                "source_loop_index must be an exact nonnegative integer",
                location=(
                    f"metadata.mmcif.preserved_category_payloads[{category!r}]"
                    ".loops[0].source_loop_index"
                ),
            )
        tags = loop.get("tags")
        rows_value = loop.get("rows")
        if (
            not isinstance(tags, (list, tuple))
            or tuple(tags) != headers
            or not isinstance(rows_value, (list, tuple))
            or not 1 <= len(rows_value) <= limit
        ):
            raise MmcifWriteError(
                "unsupported_identity_category_profile",
                f"{category} headers or row count are outside the exact profile",
                location=(
                    f"metadata.mmcif.preserved_category_payloads[{category!r}].loops[0]"
                ),
            )
        token_rows: list[tuple[str, str]] = []
        document_rows: list[tuple[dict[str, Any], ...]] = []
        for row_index, raw_row in enumerate(rows_value):
            if not isinstance(raw_row, (list, tuple)) or len(raw_row) != 2:
                raise MmcifWriteError(
                    "unsupported_identity_category_profile",
                    f"{category} rows must contain exactly two values",
                    location=(
                        f"metadata.mmcif.preserved_category_payloads[{category!r}]"
                        f".loops[0].rows[{row_index}]"
                    ),
                )
            values: list[str] = []
            documents: list[dict[str, Any]] = []
            for column_index, raw_value in enumerate(raw_row):
                value, document = _validated_identity_category_payload(
                    raw_value,
                    location=(
                        f"metadata.mmcif.preserved_category_payloads[{category!r}]"
                        f".loops[0].rows[{row_index}][{column_index}]"
                    ),
                )
                values.append(value)
                documents.append(document)
            token_rows.append((values[0], values[1]))
            document_rows.append((documents[0], documents[1]))
        return tuple(token_rows), tuple(document_rows)

    entity_rows, entity_payload_rows = category_rows(
        "_entity", _ENTITY_HEADERS, limit=_MAX_ENTITY_ROWS
    )
    struct_rows, struct_payload_rows = category_rows(
        "_struct_asym", _STRUCT_ASYM_HEADERS, limit=_MAX_STRUCT_ASYM_ROWS
    )

    entity_types: dict[str, str] = {}
    entity_documents: list[Mapping[str, Any]] = []
    for row_index, ((entity_id, raw_type), payload_row) in enumerate(
        zip(entity_rows, entity_payload_rows, strict=True)
    ):
        if entity_id in entity_types:
            raise MmcifWriteError(
                "duplicate_entity_id",
                "common-core21 _entity.id values must be unique",
                location=f"metadata.mmcif.entity_rows[{row_index}]",
            )
        normalized_type = _SUPPORTED_COMMON_ENTITY_TYPES.get(raw_type)
        if normalized_type is None:
            raise MmcifWriteError(
                "unsupported_entity_type",
                "common-core21 supports exact polymer, non-polymer, or water types",
                location=f"metadata.mmcif.entity_rows[{row_index}].type",
            )
        entity_types[entity_id] = normalized_type
        entity_documents.append(
            {
                "source_row_index": row_index,
                "id": payload_row[0],
                "type": payload_row[1],
                "normalized_type": normalized_type,
            }
        )

    asym_entities: dict[str, str] = {}
    struct_documents: list[Mapping[str, Any]] = []
    for row_index, ((asym_id, entity_id), payload_row) in enumerate(
        zip(struct_rows, struct_payload_rows, strict=True)
    ):
        if asym_id in asym_entities:
            raise MmcifWriteError(
                "duplicate_struct_asym_id",
                "common-core21 _struct_asym.id values must be unique",
                location=f"metadata.mmcif.struct_asym_rows[{row_index}]",
            )
        if entity_id not in entity_types:
            raise MmcifWriteError(
                "unknown_struct_asym_entity",
                "_struct_asym.entity_id must resolve to the selected _entity loop",
                location=f"metadata.mmcif.struct_asym_rows[{row_index}].entity_id",
            )
        asym_entities[asym_id] = entity_id
        struct_documents.append(
            {
                "source_row_index": row_index,
                "id": payload_row[0],
                "entity_id": payload_row[1],
            }
        )

    expected_inventory_by_category = {
        "_entity": {
            "category": "_entity",
            "scalar_item_count": 0,
            "loop_count": 1,
            "row_count": len(entity_rows),
            "policy": "partially_interpreted",
        },
        "_struct_asym": {
            "category": "_struct_asym",
            "scalar_item_count": 0,
            "loop_count": 1,
            "row_count": len(struct_rows),
            "policy": "partially_interpreted",
        },
        "_atom_site": {
            "category": "_atom_site",
            "scalar_item_count": 0,
            "loop_count": 1,
            "row_count": atom_count,
            "policy": "interpreted_with_source_values_preserved",
        },
    }
    if frozenset(inventory_by_category) != frozenset(
        expected_inventory_by_category
    ) or any(
        not _exact_typed_structure_equal(
            inventory_by_category[category], expected_entry
        )
        for category, expected_entry in expected_inventory_by_category.items()
    ):
        raise MmcifWriteError(
            "unsupported_category_inventory",
            "common-core21 requires exact entity, struct_asym, and atom_site loops",
            location="metadata.mmcif.category_inventory",
        )
    canonical_inventory = tuple(
        expected_inventory_by_category[category]
        for category in ("_entity", "_struct_asym", "_atom_site")
    )
    return _SelectedCategoryState(
        category_profile=_COMMON_THREE_LOOP_CATEGORY_PROFILE,
        identity_profile=_COMMON_CORE21_IDENTITY_PROFILE,
        entity_rows=entity_rows,
        struct_asym_rows=struct_rows,
        entity_documents=tuple(entity_documents),
        struct_asym_documents=tuple(struct_documents),
        entity_types=entity_types,
        asym_entities=asym_entities,
        category_inventory=canonical_inventory,
    )


def _preflight_mmcif_surface(
    system: AllAtomSystem,
) -> tuple[str, tuple[str, ...], _SelectedCategoryState]:
    """Reject broad source surfaces before source-bound digest comparisons."""

    system_metadata = _require_exact_keys(
        system.metadata,
        frozenset({"mmcif"}),
        code="unsupported_system_metadata",
        location="metadata",
    )
    mmcif = _require_exact_keys(
        system_metadata["mmcif"],
        _MMCIF_METADATA_KEYS,
        code="unsupported_mmcif_metadata",
        location="metadata.mmcif",
    )
    _safe_data_block(mmcif.get("data_block"), location="metadata.mmcif.data_block")
    assembly = mmcif.get("assembly")
    if not _exact_typed_structure_equal(assembly, _ASSEMBLY):
        raise MmcifWriteError(
            "unsupported_assembly",
            "mmCIF writer v1 requires parser-owned absent assembly state",
            location="metadata.mmcif.assembly",
        )
    missingness = mmcif.get("source_missingness")
    if not _exact_typed_structure_equal(missingness, _SOURCE_MISSINGNESS):
        raise MmcifWriteError(
            "unsupported_missingness_evidence",
            "mmCIF writer v1 requires absent source missingness evidence",
            location="metadata.mmcif.source_missingness",
        )
    if mmcif.get("coordinate_scope") != "deposited_asymmetric_unit":
        raise MmcifWriteError(
            "unsupported_coordinate_scope",
            "mmCIF writer v1 requires deposited asymmetric-unit coordinates",
            location="metadata.mmcif.coordinate_scope",
        )
    altloc = mmcif.get("altloc_selection")
    if not _exact_typed_structure_equal(altloc, _ALTLOC_SELECTION):
        raise MmcifWriteError(
            "unsupported_altloc_selection",
            "mmCIF writer v1 requires parser-owned no-altloc state",
            location="metadata.mmcif.altloc_selection",
        )
    headers = mmcif.get("atom_site_headers")
    atom_site_header_profile, atom_site_headers = _atom_site_profile_for_headers(
        headers,
        location="metadata.mmcif.atom_site_headers",
    )
    category_state = _selected_category_state(
        mmcif,
        atom_site_header_profile=atom_site_header_profile,
        atom_count=system.atom_count,
    )
    if mmcif.get("cell") is not None:
        raise MmcifWriteError(
            "unsupported_unit_cell",
            "mmCIF writer v1 does not emit cell metadata",
            location="metadata.mmcif.cell",
        )
    return atom_site_header_profile, atom_site_headers, category_state


def _preflight_unrepresentable_atom_state(
    system: AllAtomSystem,
    *,
    atom_site_headers: tuple[str, ...],
) -> None:
    """Give stable scope errors before topology-digest drift can mask them."""

    for atom in system.atoms:
        location = f"atoms[{atom.index}]"
        checks = (
            (
                atom.partial_charge_e is not None,
                "unsupported_partial_charge",
                "partial_charge_e",
            ),
            (atom.mass_da is not None, "unsupported_atom_mass", "mass_da"),
            (
                atom.isotope_mass_number is not None,
                "unsupported_isotope",
                "isotope_mass_number",
            ),
            (atom.atom_map is not None, "unsupported_atom_map", "atom_map"),
            (atom.aromatic, "unsupported_aromatic_atom", "aromatic"),
            (atom.stereo != "unspecified", "unsupported_atom_stereo", "stereo"),
            (bool(atom.altloc), "unsupported_altloc_selection", "altloc"),
            (
                _OCCUPANCY_HEADER not in atom_site_headers
                and atom.occupancy is not None,
                "unsupported_occupancy",
                "occupancy",
            ),
            (
                _B_FACTOR_HEADER not in atom_site_headers and atom.b_factor is not None,
                "unsupported_b_factor",
                "b_factor",
            ),
        )
        for rejected, code, field_name in checks:
            if rejected:
                raise MmcifWriteError(
                    code,
                    "canonical atom state is outside the selected mmCIF subset",
                    location=f"{location}.{field_name}",
                )


def _identity_projection_document(
    *,
    atom_site_header_profile: str,
    category_state: _SelectedCategoryState,
    atom_documents: tuple[Mapping[str, Any], ...],
    residue_documents: tuple[Mapping[str, Any], ...],
    chain_documents: tuple[Mapping[str, Any], ...],
) -> Mapping[str, Any]:
    common_identity = atom_site_header_profile == _COMMON_CORE21_IDENTITY_PROFILE
    if not common_identity:
        return {
            "schema_id": MMCIF_LABEL_AUTH_ENTITY_IDENTITY_PROJECTION_SCHEMA_ID,
            "identity_profile": _NO_AUTH_ENTITY_IDENTITY_PROFILE,
            "category_profile": _ATOM_SITE_ONLY_CATEGORY_PROFILE,
            "atom_site_header_profile": atom_site_header_profile,
            "entity_row_count": 0,
            "struct_asym_row_count": 0,
            "complete_auth_row_count": 0,
            "entity_rows": [],
            "struct_asym_rows": [],
            "atoms": [],
            "residues": [],
            "chains": [],
        }

    identity_atoms: list[Mapping[str, Any]] = []
    raw_identity_headers = (
        "_atom_site.group_pdb",
        "_atom_site.id",
        "_atom_site.type_symbol",
        "_atom_site.label_atom_id",
        _LABEL_ALT_ID_HEADER,
        "_atom_site.label_comp_id",
        "_atom_site.label_asym_id",
        _LABEL_ENTITY_ID_HEADER,
        "_atom_site.label_seq_id",
        _INSERTION_CODE_HEADER,
        _OCCUPANCY_HEADER,
        _B_FACTOR_HEADER,
        _FORMAL_CHARGE_HEADER,
        _AUTH_SEQ_ID_HEADER,
        _AUTH_COMP_ID_HEADER,
        _AUTH_ASYM_ID_HEADER,
        _AUTH_ATOM_ID_HEADER,
        "_atom_site.pdbx_pdb_model_num",
    )
    for atom in atom_documents:
        mmcif = atom["metadata"]["mmcif"]
        raw = mmcif["noncoordinate_atom_site"]
        identity_atoms.append(
            {
                "index": atom["index"],
                "residue_index": atom["residue_index"],
                "canonical_name": atom["name"],
                "canonical_element": atom["element"],
                "canonical_formal_charge": atom["formal_charge"],
                "canonical_formal_charge_known": atom["formal_charge_known"],
                "canonical_occupancy_ieee754_binary64_be": atom[
                    "occupancy_ieee754_binary64_be"
                ],
                "canonical_b_factor_ieee754_binary64_be": atom[
                    "b_factor_ieee754_binary64_be"
                ],
                "canonical_identity_namespace": "label",
                "residue_sequence_source": mmcif["residue_sequence_source"],
                "entity_id": mmcif["entity_id"],
                "entity_type": mmcif["entity_type"],
                "auth_identity": mmcif["auth_identity"],
                "raw_selected_identity_and_measurement_tokens": {
                    header: raw[header] for header in raw_identity_headers
                },
            }
        )
    identity_residues = [
        {
            "index": residue["index"],
            "name": residue["name"],
            "chain_index": residue["chain_index"],
            "sequence_number": residue["sequence_number"],
            "insertion_code": residue["insertion_code"],
            "entity_type": residue["entity_type"],
            "hetero": residue["hetero"],
            "entity_id": residue["metadata"]["entity_id"],
            "mmcif_label_seq_id": residue["metadata"]["mmcif_label_seq_id"],
            "mmcif_auth_seq_id": residue["metadata"]["mmcif_auth_seq_id"],
            "canonical_sequence_source": residue["metadata"][
                "canonical_sequence_source"
            ],
            "atom_indices": residue["atom_indices"],
        }
        for residue in residue_documents
    ]
    identity_chains = [
        {
            "index": chain["index"],
            "label_asym_id": chain["chain_id"],
            "entity_id": chain["entity_id"],
            "auth_asym_ids": chain["metadata"]["auth_asym_ids"],
            "residue_indices": chain["residue_indices"],
        }
        for chain in chain_documents
    ]
    return {
        "schema_id": MMCIF_LABEL_AUTH_ENTITY_IDENTITY_PROJECTION_SCHEMA_ID,
        "identity_profile": category_state.identity_profile,
        "category_profile": category_state.category_profile,
        "atom_site_header_profile": atom_site_header_profile,
        "entity_row_count": category_state.entity_row_count,
        "struct_asym_row_count": category_state.struct_asym_row_count,
        "complete_auth_row_count": len(atom_documents),
        "entity_rows": list(category_state.entity_documents),
        "struct_asym_rows": list(category_state.struct_asym_documents),
        "atoms": identity_atoms,
        "residues": identity_residues,
        "chains": identity_chains,
    }


def _validate_write_state(system: AllAtomSystem) -> _ValidatedWriteState:
    snapshot = _snapshot_parser_system(system)
    if snapshot.schema_id != ALL_ATOM_SCHEMA_ID:
        raise MmcifWriteError(
            "unsupported_system_schema",
            "writer requires the current all-atom schema",
            location="schema_id",
        )
    if snapshot.atom_count < 1:
        raise MmcifWriteError(
            "unsupported_atom_count",
            "strict mmCIF writer requires at least one atom",
            location="atoms",
        )
    if snapshot.bonds:
        raise MmcifWriteError(
            "unsupported_bonds",
            "core _atom_site-only mmCIF cannot preserve bond topology",
            location="bonds",
        )
    if snapshot.cell is not None:
        raise MmcifWriteError(
            "unsupported_unit_cell",
            "mmCIF writer v1 does not emit cell or symmetry categories",
            location="cell",
        )
    if snapshot.model_count != 1:
        raise MmcifWriteError(
            "unsupported_model_id",
            "mmCIF writer v1 requires exactly one coordinate model",
            location="coordinates",
        )
    if snapshot.atom_count > _MAX_ATOM_ROWS:
        raise MmcifWriteError(
            "too_many_atom_rows",
            "emitted mmCIF atom rows exceed the parser safety limit",
            location="coordinates",
        )

    (
        atom_site_header_profile,
        atom_site_headers,
        category_state,
    ) = _preflight_mmcif_surface(snapshot)
    _preflight_unrepresentable_atom_state(
        snapshot,
        atom_site_headers=atom_site_headers,
    )
    _preflight_insertion_code_state(
        snapshot,
        atom_site_headers=atom_site_headers,
    )
    _preflight_occupancy_state(
        snapshot,
        atom_site_headers=atom_site_headers,
    )
    _preflight_b_factor_state(
        snapshot,
        atom_site_headers=atom_site_headers,
    )
    data_block, _, _ = _validate_provenance_and_metadata(
        snapshot,
        atom_site_headers=atom_site_headers,
        category_state=category_state,
    )
    (
        row_tokens,
        atom_documents,
        residue_documents,
        chain_documents,
    ) = _validate_atoms_residues_chains(
        snapshot,
        atom_site_header_profile=atom_site_header_profile,
        atom_site_headers=atom_site_headers,
        category_state=category_state,
    )
    identity_projection_document = _identity_projection_document(
        atom_site_header_profile=atom_site_header_profile,
        category_state=category_state,
        atom_documents=atom_documents,
        residue_documents=residue_documents,
        chain_documents=chain_documents,
    )
    coordinate_document = [
        [
            [
                _binary64_hex(
                    float(snapshot.coordinates[0, atom_index, axis_index].item())
                )
                for axis_index in range(3)
            ]
            for atom_index in range(snapshot.atom_count)
        ]
    ]
    coordinate_tokens = [
        [
            [
                repr(float(snapshot.coordinates[0, atom_index, axis_index].item()))
                for axis_index in range(3)
            ]
            for atom_index in range(snapshot.atom_count)
        ]
    ]
    representable_state_document: Mapping[str, Any] = {
        "schema_id": MMCIF_REPRESENTABLE_STATE_SCHEMA_ID,
        "system_schema_id": snapshot.schema_id,
        "parser_name": snapshot.provenance.parser_name,
        "parser_version": snapshot.provenance.parser_version,
        "parser_operations": list(snapshot.provenance.operations),
        "canonical_topology_sha256": canonical_topology_sha256(snapshot),
        "data_block": data_block,
        "atom_site_header_profile": atom_site_header_profile,
        "atom_site_headers": list(atom_site_headers),
        "category_profile": category_state.category_profile,
        "identity_projection_schema_id": (
            MMCIF_LABEL_AUTH_ENTITY_IDENTITY_PROJECTION_SCHEMA_ID
        ),
        "identity_profile": category_state.identity_profile,
        "identity_projection_sha256": _sha256_document(identity_projection_document),
        "occupancy_value_profile_id": (
            _OCCUPANCY_VALUE_PROFILE_ID
            if _OCCUPANCY_HEADER in atom_site_headers
            else None
        ),
        "b_factor_value_profile_id": (
            _B_FACTOR_VALUE_PROFILE_ID
            if _B_FACTOR_HEADER in atom_site_headers
            else None
        ),
        "category_inventory": list(category_state.category_inventory),
        "entity_rows": list(category_state.entity_documents),
        "struct_asym_rows": list(category_state.struct_asym_documents),
        "entity_row_count": category_state.entity_row_count,
        "struct_asym_row_count": category_state.struct_asym_row_count,
        "complete_auth_row_count": (
            snapshot.atom_count
            if atom_site_header_profile == _COMMON_CORE21_IDENTITY_PROFILE
            else 0
        ),
        "atom_count": snapshot.atom_count,
        "bond_count": 0,
        "residue_count": len(snapshot.residues),
        "chain_count": len(snapshot.chains),
        "model_count": 1,
        "model_ids": [1],
        "coordinate_unit": "angstrom",
        "coordinates_ieee754_binary64_be": coordinate_document,
        "coordinate_tokens_shortest_round_trip": coordinate_tokens,
        "atoms": list(atom_documents),
        "residues": list(residue_documents),
        "chains": list(chain_documents),
        "coordinate_scope": "deposited_asymmetric_unit",
        "assembly_status": "not_present",
        "altloc_status": "not_present",
        "missingness_evidence_status": "not_present",
        "cell": None,
        "preservation_scope": list(_PRESERVATION_SCOPE),
    }
    return _ValidatedWriteState(
        system=snapshot,
        data_block=data_block,
        atom_site_header_profile=atom_site_header_profile,
        atom_site_headers=atom_site_headers,
        category_state=category_state,
        row_tokens=row_tokens,
        identity_projection_document=identity_projection_document,
        representable_state_document=representable_state_document,
    )


def _emit_payload(state: _ValidatedWriteState) -> tuple[bytes, int, int]:
    lines = [f"data_{state.data_block}", "#"]
    if state.category_state.category_profile == _COMMON_THREE_LOOP_CATEGORY_PROFILE:
        lines.extend(
            (
                "loop_",
                *_ENTITY_HEADERS,
                *(" ".join(row) for row in state.category_state.entity_rows),
                "#",
                "loop_",
                *_STRUCT_ASYM_HEADERS,
                *(" ".join(row) for row in state.category_state.struct_asym_rows),
                "#",
            )
        )
    lines.extend(
        (
            "loop_",
            *state.atom_site_headers,
            *(" ".join(row) for row in state.row_tokens),
            "#",
        )
    )
    token_count = _expected_output_token_count(
        state.atom_site_headers,
        state.system.atom_count,
        entity_row_count=state.category_state.entity_row_count,
        struct_asym_row_count=state.category_state.struct_asym_row_count,
    )
    if token_count > _MAX_TOKEN_COUNT:
        raise MmcifWriteError(
            "output_token_limit_exceeded",
            "emitted mmCIF exceeds the parser token safety limit",
        )
    physical_line_count = len(lines) + 1
    if physical_line_count > _MAX_OUTPUT_LINES:
        raise MmcifWriteError(
            "output_line_limit_exceeded",
            "emitted mmCIF exceeds the parser physical-line safety limit",
        )
    overlong_index = next(
        (index for index, line in enumerate(lines) if len(line) > _MAX_LINE_CHARS),
        None,
    )
    if overlong_index is not None:
        raise MmcifWriteError(
            "output_line_too_long",
            "emitted mmCIF line exceeds the CIF 1.1 line-length limit",
            location=f"output.lines[{overlong_index}]",
        )
    try:
        payload = ("\n".join(lines) + "\n").encode("ascii")
    except UnicodeEncodeError as exc:
        raise MmcifWriteError(
            "unsafe_cif_token",
            "validated mmCIF output contains non-ASCII text",
        ) from exc
    if len(payload) > _MAX_OUTPUT_BYTES:
        raise MmcifWriteError(
            "output_too_large",
            "emitted mmCIF exceeds the parser byte safety limit",
        )
    return payload, token_count, physical_line_count


def mmcif_representable_state_sha256(system: AllAtomSystem) -> str:
    """Hash the exact parser-owned mmCIF state reproduced by this writer."""

    state = _validate_write_state(system)
    return _sha256_document(state.representable_state_document)


def write_mmcif(system: AllAtomSystem) -> MmcifWriteResult:
    """Emit deterministic selected-profile mmCIF bytes and a receipt."""

    state = _validate_write_state(system)
    payload, token_count, physical_line_count = _emit_payload(state)
    output_source_sha256 = hashlib.sha256(payload).hexdigest()
    parser_observation_sha256 = state.system.provenance.metadata.get(
        "parser_observation_sha256"
    )
    if type(parser_observation_sha256) is not str:
        raise MmcifWriteError(
            "stale_parser_observation_digest",
            "validated parser observation digest is missing",
            location="provenance.metadata.parser_observation_sha256",
        )
    receipt = MmcifWriteReceipt(
        input_system_schema_id=state.system.schema_id,
        parent_source_sha256=state.system.provenance.source_sha256,
        input_snapshot_sha256=canonical_all_atom_snapshot_digest(state.system),
        input_topology_sha256=canonical_topology_sha256(state.system),
        input_representable_state_sha256=_sha256_document(
            state.representable_state_document
        ),
        identity_projection_schema_id=(
            MMCIF_LABEL_AUTH_ENTITY_IDENTITY_PROJECTION_SCHEMA_ID
        ),
        identity_profile=state.category_state.identity_profile,
        input_identity_projection_sha256=_sha256_document(
            state.identity_projection_document
        ),
        category_profile=state.category_state.category_profile,
        input_parser_observation_sha256=parser_observation_sha256,
        output_source_sha256=output_source_sha256,
        output_byte_count=len(payload),
        output_token_count=token_count,
        output_physical_line_count=physical_line_count,
        atom_count=state.system.atom_count,
        bond_count=0,
        model_count=1,
        atom_site_row_count=state.system.atom_count,
        atom_site_header_profile=state.atom_site_header_profile,
        atom_site_header_count=len(state.atom_site_headers),
        entity_row_count=state.category_state.entity_row_count,
        struct_asym_row_count=state.category_state.struct_asym_row_count,
        complete_auth_row_count=(
            state.system.atom_count
            if state.atom_site_header_profile == _COMMON_CORE21_IDENTITY_PROFILE
            else 0
        ),
        _factory_token=_ARTIFACT_FACTORY_TOKEN,
    )
    return MmcifWriteResult(
        payload=payload,
        receipt=receipt,
        _factory_token=_ARTIFACT_FACTORY_TOKEN,
    )


def serialize_mmcif(system: AllAtomSystem) -> bytes:
    """Return deterministic mmCIF bytes for exactly representable state."""

    return write_mmcif(system).payload


def round_trip_mmcif_source(
    data: bytes,
    *,
    source_id: str = "",
) -> MmcifRoundTripResult:
    """Execute and verify ``source -> canonical -> mmCIF -> canonical``.

    Equality covers only :data:`MMCIF_REPRESENTABLE_STATE_SCHEMA_ID`.  Dynamic
    raw-source provenance and the complete canonical snapshot are bound in the
    report but intentionally are not equality or authentication claims.
    """

    source_ingest = parse_mmcif(data, source_id=source_id)
    write_result = write_mmcif(source_ingest.system)
    reparsed_ingest = parse_mmcif(write_result.payload, source_id=source_id)
    reemitted = write_mmcif(reparsed_ingest.system)

    input_topology_sha256 = canonical_topology_sha256(source_ingest.system)
    reparsed_topology_sha256 = canonical_topology_sha256(reparsed_ingest.system)
    input_state_sha256 = write_result.receipt.input_representable_state_sha256
    reparsed_state_sha256 = reemitted.receipt.input_representable_state_sha256
    input_identity_sha256 = write_result.receipt.input_identity_projection_sha256
    reparsed_identity_sha256 = reemitted.receipt.input_identity_projection_sha256
    input_source_sha256 = hashlib.sha256(data).hexdigest()
    mismatches: list[str] = []
    if source_ingest.system.provenance.source_sha256 != input_source_sha256:
        mismatches.append("input_source_sha256")
    if write_result.receipt.parent_source_sha256 != input_source_sha256:
        mismatches.append("writer_parent_source_sha256")
    if input_topology_sha256 != reparsed_topology_sha256:
        mismatches.append("canonical_topology")
    if input_state_sha256 != reparsed_state_sha256:
        mismatches.append("representable_state")
    if input_identity_sha256 != reparsed_identity_sha256:
        mismatches.append("label_auth_entity_identity_projection")
    if (
        reparsed_ingest.system.provenance.source_sha256
        != write_result.receipt.output_source_sha256
    ):
        mismatches.append("reparsed_source_sha256")
    if reemitted.payload != write_result.payload:
        mismatches.append("reemitted_bytes")
    if mismatches:
        raise MmcifWriteError(
            "round_trip_mismatch",
            f"declared mmCIF round-trip projection failed: {mismatches}",
        )

    input_observation_sha256 = source_ingest.system.provenance.metadata.get(
        "parser_observation_sha256"
    )
    reparsed_observation_sha256 = reparsed_ingest.system.provenance.metadata.get(
        "parser_observation_sha256"
    )
    if (
        type(input_observation_sha256) is not str
        or type(reparsed_observation_sha256) is not str
    ):
        raise MmcifWriteError(
            "stale_parser_observation_digest",
            "round-trip parser observation digests are missing",
        )
    report = MmcifRoundTripReport(
        input_source_sha256=input_source_sha256,
        input_snapshot_sha256=write_result.receipt.input_snapshot_sha256,
        input_topology_sha256=input_topology_sha256,
        input_representable_state_sha256=input_state_sha256,
        identity_projection_schema_id=(
            MMCIF_LABEL_AUTH_ENTITY_IDENTITY_PROJECTION_SCHEMA_ID
        ),
        identity_profile=write_result.receipt.identity_profile,
        category_profile=write_result.receipt.category_profile,
        input_identity_projection_sha256=input_identity_sha256,
        reparsed_identity_projection_sha256=reparsed_identity_sha256,
        entity_row_count=write_result.receipt.entity_row_count,
        struct_asym_row_count=write_result.receipt.struct_asym_row_count,
        complete_auth_row_count=write_result.receipt.complete_auth_row_count,
        input_parser_observation_sha256=input_observation_sha256,
        writer_receipt_sha256=write_result.receipt.receipt_sha256,
        emitted_source_sha256=write_result.receipt.output_source_sha256,
        reparsed_snapshot_sha256=canonical_all_atom_snapshot_digest(
            reparsed_ingest.system
        ),
        reparsed_topology_sha256=reparsed_topology_sha256,
        reparsed_representable_state_sha256=reparsed_state_sha256,
        reparsed_parser_observation_sha256=reparsed_observation_sha256,
        reemitted_source_sha256=hashlib.sha256(reemitted.payload).hexdigest(),
        _factory_token=_ARTIFACT_FACTORY_TOKEN,
    )
    return MmcifRoundTripResult(
        source_ingest=source_ingest,
        write_result=write_result,
        reparsed_ingest=reparsed_ingest,
        report=report,
        _factory_token=_ARTIFACT_FACTORY_TOKEN,
    )


__all__ = [
    "MMCIF_LABEL_AUTH_ENTITY_IDENTITY_PROJECTION_SCHEMA_ID",
    "MMCIF_REPRESENTABLE_STATE_SCHEMA_ID",
    "MMCIF_ROUND_TRIP_REPORT_SCHEMA_ID",
    "MMCIF_WRITER_VERSION",
    "MMCIF_WRITE_RECEIPT_SCHEMA_ID",
    "MmcifRoundTripReport",
    "MmcifRoundTripResult",
    "MmcifWriteError",
    "MmcifWriteReceipt",
    "MmcifWriteResult",
    "mmcif_representable_state_sha256",
    "round_trip_mmcif_source",
    "serialize_mmcif",
    "write_mmcif",
]
