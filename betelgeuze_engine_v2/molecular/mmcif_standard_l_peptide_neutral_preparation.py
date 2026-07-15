"""Exact source-explicit ALA/GLY neutral-linkage preparation profile.

This module composes two independently validated projections from one exact
eight-category mmCIF source.  The first projection is the fully observed
polymer component topology plus terminal/leaving annotation inventory.  The
second is the archive-standard ALA/GLY heavy reference topology.  Only after
both children and a hash-pinned engine policy agree does the transformer remove
the policy-declared atoms and materialize same-asym sequence-adjacent C--N
bonds.

The selected state is the source-explicit CCD-neutral linkage microstate.  It
is not a pH prediction, an independent protonation or CIP assessment, source
authentication, generic preparation, parameterability, or runtime authority.
No hydrogen coordinates are generated: every retained hydrogen and coordinate
must already be present in the source.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
import hashlib
import json
import struct
from typing import Any
import weakref

import torch

from .mmcif_archive_standard_l_peptide_topology import (
    MAX_MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_ATOMS,
    MAX_MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_BONDS,
    MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_ATOM_SITE_HEADERS,
    MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_ENTITY_HEADERS,
    MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_ENTITY_POLY_HEADERS,
    MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_STRUCT_ASYM_HEADERS,
    MmcifArchiveStandardLPeptideTopologyError,
    MmcifArchiveStandardLPeptideTopologyIngestResult,
    parse_mmcif_archive_standard_l_peptide_topology,
)
from .mmcif_polymer_component_terminal_leaving_policy import (
    MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_COMPONENT_ATOM_ROWS,
    MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_COMPONENT_BOND_ROWS,
    MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_COMPONENT_ROWS,
    MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_INPUT_BYTES,
    MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_OUTPUT_LINE_CHARS,
    MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_SEQUENCE_ROWS,
    MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_SOURCE_ID_BYTES,
    MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_TOKEN_CHARS,
    MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_CHEM_COMP_ATOM_HEADERS,
    MmcifPolymerComponentTerminalLeavingPolicyError,
    MmcifPolymerComponentTerminalLeavingPolicyIngestResult,
    parse_mmcif_polymer_component_terminal_leaving_policy,
)
from .mmcif_polymer_component_topology import (
    MMCIF_POLYMER_COMPONENT_TOPOLOGY_CHEM_COMP_BOND_HEADERS,
    MMCIF_POLYMER_COMPONENT_TOPOLOGY_CHEM_COMP_HEADERS,
)
from .mmcif_polymer_sequence import MMCIF_ENTITY_POLY_SEQ_HEADERS
from .mmcif_syntax import CifBlock, CifLoop, CifSyntaxError, CifToken, parse_cif_block
from .models import AllAtomSystem, Atom, Bond, Chain, Residue
from .observation import (
    attach_parser_observation_digest,
    attached_parser_observation_sha256_matches,
)
from .serialization import deserialize_all_atom_system, serialize_all_atom_system
from .standard_l_peptide_preparation_rules import (
    STANDARD_L_PEPTIDE_PREPARATION_INTER_RESIDUE_RULE,
    STANDARD_L_PEPTIDE_PREPARATION_RULE_MANIFEST_SCHEMA_ID,
    STANDARD_L_PEPTIDE_PREPARATION_RULE_MANIFEST_SHA256,
    StandardLPeptidePreparationRuleError,
    standard_l_peptide_expected_retained_atoms,
    standard_l_peptide_expected_retained_bonds,
    standard_l_peptide_preparation_component_rule,
    standard_l_peptide_preparation_role_rule,
    validate_standard_l_peptide_preparation_rule_manifest,
)
from .standard_l_peptide_rules import (
    STANDARD_L_PEPTIDE_RULE_MANIFEST_SCHEMA_ID,
    STANDARD_L_PEPTIDE_RULE_MANIFEST_SHA256,
    StandardLPeptideRuleError,
    standard_l_peptide_component_rule,
    validate_standard_l_peptide_rule_manifest,
)
from .topology import (
    CANONICAL_TOPOLOGY_SCHEMA_ID,
    attached_canonical_topology_sha256_matches,
    canonical_topology_sha256,
)
from .validation import validate_all_atom_system


MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_VERSION = "1.0.0"
MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_PROFILE_ID = (
    "strict_mmcif_ALA_GLY_source_explicit_CCD_neutral_linkage_preparation/1.0.0"
)
MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_POLICY_ID = (
    "exact_ALA_GLY_source_explicit_CCD_neutral_linkage_policy/1.0.0"
)
MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_TRANSFORMER_NAME = (
    "betelgeuze_engine_v2.molecular.mmcif_standard_l_peptide_neutral_preparation."
    "prepare_mmcif_standard_l_peptide_neutral_linkage"
)
MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_TRANSFORMER_VERSION = "1.0.0"
MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_MAPPING_SCHEMA_ID = (
    "betelgeuze.mmcif_standard_l_peptide_neutral_preparation_atom_mapping/1.0.0"
)
MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_PARAMETER_REQUIREMENT_SCHEMA_ID = (
    "betelgeuze.mmcif_standard_l_peptide_parameter_requirement_inventory/1.0.0"
)
MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_REPORT_SCHEMA_ID = (
    "betelgeuze.mmcif_standard_l_peptide_neutral_preparation_report/1.0.0"
)
MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_SOURCE_BINDING_SCHEMA_ID = (
    "betelgeuze.mmcif_standard_l_peptide_neutral_preparation_source_binding/1.0.0"
)
MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_STATE_SCHEMA_ID = (
    "betelgeuze.mmcif_standard_l_peptide_neutral_preparation_state/1.0.0"
)
MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_MARKER_KEY = (
    "mmcif_standard_l_peptide_neutral_preparation"
)

MAX_MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_INPUT_BYTES = (
    MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_INPUT_BYTES
)
MAX_MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_SOURCE_ID_BYTES = (
    MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_SOURCE_ID_BYTES
)
MAX_MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_TOKEN_CHARS = (
    MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_TOKEN_CHARS
)
MAX_MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_OUTPUT_LINE_CHARS = (
    MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_OUTPUT_LINE_CHARS
)
MAX_MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_ATOMS = min(
    MAX_MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_ATOMS,
    MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_COMPONENT_ATOM_ROWS,
)
MAX_MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_BONDS = min(
    MAX_MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_BONDS,
    MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_COMPONENT_BOND_ROWS,
)
MAX_MMCIF_STANDARD_L_PEPTIDE_PARAMETER_ANGLES = 1_000_000
MAX_MMCIF_STANDARD_L_PEPTIDE_PARAMETER_PROPERS = 1_000_000

_ENTITY_HEADERS = MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_ENTITY_HEADERS
_ENTITY_POLY_HEADERS = MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_ENTITY_POLY_HEADERS
_STRUCT_ASYM_HEADERS = MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_STRUCT_ASYM_HEADERS
_ENTITY_POLY_SEQ_HEADERS = MMCIF_ENTITY_POLY_SEQ_HEADERS
_CHEM_COMP_HEADERS = MMCIF_POLYMER_COMPONENT_TOPOLOGY_CHEM_COMP_HEADERS
_CHEM_COMP_ATOM_HEADERS = (
    MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_CHEM_COMP_ATOM_HEADERS
)
_CHEM_COMP_BOND_HEADERS = MMCIF_POLYMER_COMPONENT_TOPOLOGY_CHEM_COMP_BOND_HEADERS
_ATOM_SITE_HEADERS = MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_ATOM_SITE_HEADERS
_CATEGORY_ORDER = (
    "_entity",
    "_entity_poly",
    "_struct_asym",
    "_entity_poly_seq",
    "_chem_comp",
    "_chem_comp_atom",
    "_chem_comp_bond",
    "_atom_site",
)
_TERMINAL_CHILD_CATEGORY_ORDER = tuple(
    category for category in _CATEGORY_ORDER if category != "_entity_poly"
)
_ARCHIVE_CHILD_CATEGORY_ORDER = (
    "_entity",
    "_entity_poly",
    "_struct_asym",
    "_entity_poly_seq",
    "_atom_site",
)
_EXPECTED_CATEGORIES = frozenset(_CATEGORY_ORDER)
_HEADERS_BY_CATEGORY = {
    "_entity": _ENTITY_HEADERS,
    "_entity_poly": _ENTITY_POLY_HEADERS,
    "_struct_asym": _STRUCT_ASYM_HEADERS,
    "_entity_poly_seq": _ENTITY_POLY_SEQ_HEADERS,
    "_chem_comp": _CHEM_COMP_HEADERS,
    "_chem_comp_atom": _CHEM_COMP_ATOM_HEADERS,
    "_chem_comp_bond": _CHEM_COMP_BOND_HEADERS,
    "_atom_site": _ATOM_SITE_HEADERS,
}
_FACTORY_TOKEN = object()
_ARTIFACT_ANCHORS: dict[int, tuple[weakref.ReferenceType[Any], bytes]] = {}

_PROFILE_TRUE_FIELDS = (
    "single_outer_source_reprojected",
    "terminal_component_child_independently_accepted",
    "archive_heavy_child_independently_accepted",
    "exact_microstate_policy_matched",
    "source_explicit_hydrogen_inventory_complete_for_profile",
    "per_atom_formal_charge_policy_matched",
    "source_stereochemistry_policy_matched",
    "role_specific_atom_transform_applied",
    "retained_source_to_prepared_atom_bijection_verified",
    "input_bond_partition_verified",
    "sequence_adjacent_peptide_bonds_materialized",
    "prepared_heavy_reference_graph_matched",
    "profile_molecular_preparation_assessed",
    "profile_molecular_preparation_ready",
)
_FALSE_AUTHORITY_FIELDS = (
    "source_authenticated",
    "source_observed_covalence_established",
    "coordinate_peptide_geometry_validated",
    "coordinate_chain_breaks_excluded",
    "environmental_ph_assessed",
    "environmental_protonation_correctness_assessed",
    "generic_hydrogen_generation_performed",
    "generic_hydrogen_completion_assessed",
    "independent_tautomer_assessed",
    "independent_aromaticity_assessed",
    "independent_cip_assessed",
    "electronic_structure_assessed",
    "modified_residue_supported",
    "nonstandard_monomer_supported",
    "water_role_assessed",
    "ion_role_assessed",
    "metal_role_or_coordination_assessed",
    "cofactor_role_assessed",
    "generic_chemistry_supported",
    "preparation_ready",
    "generic_preparation_ready",
    "generic_molecular_preparation_ready",
    "global_preparation_ready",
    "global_molecular_preparation_ready",
    "parameterability_assessed",
    "parameterizable",
    "production_parameter_set_available",
    "physics_supported",
    "runtime_eligible",
    "energy_supported",
    "force_supported",
    "minimization_supported",
    "simulation_ready",
    "execution_authorized",
    "claim_safe",
    "general_mmcif_round_trip_evidence_ready",
    "all_format_round_trip_evidence_ready",
    "v2_1_complete",
)


class MmcifStandardLPeptideNeutralPreparationError(ValueError):
    """Stable privacy-safe failure for the exact preparation profile."""

    def __init__(
        self, code: str, message: str, *, line_number: int | None = None
    ) -> None:
        self.code = str(code)
        self.detail = str(message)
        self.line_number = None if line_number is None else int(line_number)
        suffix = "" if self.line_number is None else f" at line {self.line_number}"
        super().__init__(
            "mmcif_standard_l_peptide_neutral_preparation:"
            f"{self.code}{suffix}: {self.detail}"
        )


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _is_sha256(value: Any) -> bool:
    return bool(
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _source_id_sha256(source_id: str) -> str:
    if type(source_id) is not str:
        raise TypeError("source_id must be a string")
    try:
        encoded = source_id.encode("utf-8")
    except UnicodeError:
        raise MmcifStandardLPeptideNeutralPreparationError(
            "invalid_source_id", "source identifier must contain Unicode scalar values"
        ) from None
    if len(encoded) > MAX_MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_SOURCE_ID_BYTES:
        raise MmcifStandardLPeptideNeutralPreparationError(
            "source_id_too_large", "source identifier exceeds the byte limit"
        )
    return _sha256_bytes(encoded)


def _authority_false_document() -> dict[str, bool]:
    return {name: False for name in _FALSE_AUTHORITY_FIELDS}


def _profile_true_document() -> dict[str, bool]:
    return {name: True for name in _PROFILE_TRUE_FIELDS}


def _register_anchor(value: Any, binding: bytes) -> None:
    key = id(value)

    def discard(reference: weakref.ReferenceType[Any]) -> None:
        current = _ARTIFACT_ANCHORS.get(key)
        if current is not None and current[0] is reference:
            _ARTIFACT_ANCHORS.pop(key, None)

    reference = weakref.ref(value, discard)
    _ARTIFACT_ANCHORS[key] = (reference, binding)


def _validate_anchor(value: Any, binding: bytes) -> None:
    anchor = _ARTIFACT_ANCHORS.get(id(value))
    if anchor is None or anchor[0]() is not value or anchor[1] != binding:
        raise MmcifStandardLPeptideNeutralPreparationError(
            "stale_artifact_binding", "factory artifact binding is stale"
        )


def _parse_block(data: bytes) -> CifBlock:
    if type(data) is not bytes:
        raise TypeError("mmCIF preparation input must be bytes")
    if not data:
        raise MmcifStandardLPeptideNeutralPreparationError(
            "empty_input", "input is empty"
        )
    if len(data) > MAX_MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_INPUT_BYTES:
        raise MmcifStandardLPeptideNeutralPreparationError(
            "input_too_large", "input exceeds the profile byte limit"
        )
    try:
        text = data.decode("ascii")
    except UnicodeDecodeError:
        raise MmcifStandardLPeptideNeutralPreparationError(
            "non_ascii_input", "input must use CIF 1.1 ASCII"
        ) from None
    if any(
        len(line) > MAX_MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_OUTPUT_LINE_CHARS
        for line in text.splitlines()
    ):
        raise MmcifStandardLPeptideNeutralPreparationError(
            "input_line_too_long", "input line exceeds the profile limit"
        )
    try:
        return parse_cif_block(text)
    except CifSyntaxError as exc:
        code = (
            "unsupported_category_representation"
            if exc.code == "duplicate_data_name"
            else exc.code
        )
        raise MmcifStandardLPeptideNeutralPreparationError(
            code,
            "input is outside the exact single-block CIF envelope grammar",
            line_number=exc.line_number,
        ) from None


def _loop_for(block: CifBlock, category: str) -> CifLoop:
    scalar = [name for name in block.scalar_values if name.split(".", 1)[0] == category]
    loops = [loop for loop in block.loops if category in loop.categories]
    if scalar or len(loops) != 1 or loops[0].categories != (category,):
        raise MmcifStandardLPeptideNeutralPreparationError(
            "unsupported_category_representation",
            "each selected category must occur in one category-local loop",
        )
    return loops[0]


def _validate_surface(block: CifBlock) -> dict[str, CifLoop]:
    if (
        len(block.name) > MAX_MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_TOKEN_CHARS
        or len("data_") + len(block.name)
        > MAX_MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_OUTPUT_LINE_CHARS
    ):
        raise MmcifStandardLPeptideNeutralPreparationError(
            "block_name_too_long", "data-block name exceeds the profile limit"
        )
    if set(block.categories) != _EXPECTED_CATEGORIES:
        raise MmcifStandardLPeptideNeutralPreparationError(
            "unsupported_category_surface",
            "input categories must exactly match the eight-category preparation profile",
        )
    loops = {category: _loop_for(block, category) for category in _CATEGORY_ORDER}
    for category, loop in loops.items():
        if loop.tags != _HEADERS_BY_CATEGORY[category]:
            raise MmcifStandardLPeptideNeutralPreparationError(
                "unsupported_category_headers",
                "selected category headers are outside the exact preparation profile",
                line_number=loop.line_number,
            )
        for row in loop.rows:
            for token in row:
                if len(token.value) > (
                    MAX_MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_TOKEN_CHARS
                ):
                    raise MmcifStandardLPeptideNeutralPreparationError(
                        "token_too_long",
                        "selected source token exceeds the character limit",
                        line_number=token.line_number,
                    )
    limits = {
        "_entity_poly_seq": (
            MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_SEQUENCE_ROWS,
            "too_many_sequence_rows",
        ),
        "_chem_comp": (
            MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_COMPONENT_ROWS,
            "too_many_component_rows",
        ),
        "_chem_comp_atom": (
            MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_COMPONENT_ATOM_ROWS,
            "too_many_component_atom_rows",
        ),
        "_chem_comp_bond": (
            MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_COMPONENT_BOND_ROWS,
            "too_many_component_bond_rows",
        ),
        "_atom_site": (
            MAX_MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_ATOMS,
            "too_many_atom_rows",
        ),
    }
    for category, (limit, code) in limits.items():
        if len(loops[category].rows) > limit:
            raise MmcifStandardLPeptideNeutralPreparationError(
                code, "selected category row count exceeds the profile limit"
            )
    return loops


def _token_text(token: CifToken) -> str:
    if token.multiline:
        raise MmcifStandardLPeptideNeutralPreparationError(
            "unsupported_multiline_token", "multiline tokens are outside the profile"
        )
    if not token.quoted:
        rendered = token.value
    elif "'" not in token.value:
        rendered = f"'{token.value}'"
    elif '"' not in token.value:
        rendered = f'"{token.value}"'
    else:
        raise MmcifStandardLPeptideNeutralPreparationError(
            "unsupported_quoted_token", "quoted token cannot be emitted canonically"
        )
    if len(rendered) > (
        MAX_MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_OUTPUT_LINE_CHARS
    ):
        raise MmcifStandardLPeptideNeutralPreparationError(
            "output_token_too_long", "canonical token exceeds the line limit"
        )
    return rendered


def _emit_rows(headers: tuple[str, ...], rows: tuple[tuple[str, ...], ...]) -> bytes:
    lines = ["loop_", *headers]
    for row in rows:
        joined = " ".join(row)
        lines.extend(
            (joined,)
            if len(joined)
            <= MAX_MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_OUTPUT_LINE_CHARS
            else row
        )
    lines.append("#")
    return ("\n".join(lines) + "\n").encode("ascii")


def _emit_loop(loop: CifLoop) -> bytes:
    return _emit_rows(
        loop.tags,
        tuple(tuple(_token_text(token) for token in row) for row in loop.rows),
    )


def _emit_selected_source(
    block_name: str,
    loops: Mapping[str, CifLoop],
    categories: tuple[str, ...],
    *,
    atom_rows: tuple[tuple[str, ...], ...] | None = None,
) -> bytes:
    pieces = [f"data_{block_name}\n#\n".encode("ascii")]
    for category in categories:
        if category == "_atom_site" and atom_rows is not None:
            pieces.append(_emit_rows(_ATOM_SITE_HEADERS, atom_rows))
        else:
            pieces.append(_emit_loop(loops[category]))
    return b"".join(pieces)


def _terminal_child_source(block: CifBlock, loops: Mapping[str, CifLoop]) -> bytes:
    return _emit_selected_source(block.name, loops, _TERMINAL_CHILD_CATEGORY_ORDER)


def _archive_child_source(
    block: CifBlock,
    loops: Mapping[str, CifLoop],
    terminal: MmcifPolymerComponentTerminalLeavingPolicyIngestResult,
) -> bytes:
    boundary_by_key = {
        (row.asym_id, row.sequence_number): row for row in terminal.sequence_boundaries
    }
    index = {name: position for position, name in enumerate(_ATOM_SITE_HEADERS)}
    selected: list[tuple[str, ...]] = []
    observed_keys: set[tuple[str, int, str]] = set()
    for row in loops["_atom_site"].rows:
        asym_id = row[index["_atom_site.label_asym_id"]].value
        try:
            sequence_number = int(row[index["_atom_site.label_seq_id"]].value, 10)
        except (ValueError, OverflowError):
            raise MmcifStandardLPeptideNeutralPreparationError(
                "invalid_sequence_number",
                "atom-site sequence number must be an exact integer",
                line_number=row[index["_atom_site.label_seq_id"]].line_number,
            ) from None
        component_id = row[index["_atom_site.label_comp_id"]].value
        atom_id = row[index["_atom_site.label_atom_id"]].value
        element = row[index["_atom_site.type_symbol"]].value
        boundary = boundary_by_key.get((asym_id, sequence_number))
        if boundary is None or boundary.component_id != component_id:
            raise MmcifStandardLPeptideNeutralPreparationError(
                "outer_atom_boundary_join_mismatch",
                "outer atom row does not join the terminal child boundary evidence",
            )
        try:
            heavy_rule = standard_l_peptide_component_rule(component_id)
        except StandardLPeptideRuleError:
            raise MmcifStandardLPeptideNeutralPreparationError(
                "unsupported_component",
                "outer source contains a component outside the exact ALA/GLY profile",
            ) from None
        c_boundary = boundary.position_role in {"singleton", "c_sequence_boundary"}
        expected_heavy = dict(heavy_rule.atom_elements(c_sequence_boundary=c_boundary))
        if atom_id not in expected_heavy:
            if element == "H" or atom_id == "OXT":
                continue
            raise MmcifStandardLPeptideNeutralPreparationError(
                "outer_heavy_atom_not_partitioned",
                "outer heavy atom is neither retained nor a policy deletion",
            )
        if element != expected_heavy[atom_id]:
            raise MmcifStandardLPeptideNeutralPreparationError(
                "outer_heavy_atom_element_mismatch",
                "outer heavy atom element differs from the heavy reference policy",
            )
        key = (asym_id, sequence_number, atom_id)
        if key in observed_keys:
            raise MmcifStandardLPeptideNeutralPreparationError(
                "duplicate_outer_heavy_atom_identity",
                "outer heavy atom identities must be unique",
            )
        observed_keys.add(key)
        rendered = [_token_text(token) for token in row]
        rendered[index["_atom_site.pdbx_formal_charge"]] = "?"
        selected.append(tuple(rendered))
    return _emit_selected_source(
        block.name,
        loops,
        _ARCHIVE_CHILD_CATEGORY_ORDER,
        atom_rows=tuple(selected),
    )


@dataclass(frozen=True, slots=True)
class _Instance:
    asym_id: str
    entity_id: str
    sequence_number: int
    component_id: str
    role: str
    source_chain_index: int
    source_residue_index: int


@dataclass(frozen=True, slots=True)
class _PreparedAtomIdentity:
    prepared_index: int
    source_index: int
    source_serial: int | None
    asym_id: str
    entity_id: str
    sequence_number: int
    component_id: str
    role: str
    atom_id: str
    element: str
    formal_charge: int
    stereo: str
    h_parent_atom_id: str | None


@dataclass(frozen=True, slots=True)
class _TransformOutput:
    system: AllAtomSystem
    mapping_bytes: bytes
    parameter_inventory_bytes: bytes
    prepared_identities: tuple[_PreparedAtomIdentity, ...]
    retained_input_bond_count: int
    deleted_input_bond_count: int
    peptide_bond_count: int


def _raise_policy(code: str, detail: str) -> None:
    raise MmcifStandardLPeptideNeutralPreparationError(code, detail)


def _validate_component_policy(
    terminal: MmcifPolymerComponentTerminalLeavingPolicyIngestResult,
) -> None:
    """Cross-check every child template row against the literal policy."""

    try:
        validate_standard_l_peptide_preparation_rule_manifest()
        validate_standard_l_peptide_rule_manifest()
    except (StandardLPeptidePreparationRuleError, StandardLPeptideRuleError):
        _raise_policy(
            "rule_manifest_hash_mismatch",
            "runtime standard peptide rules differ from their literal pins",
        )
    child = terminal.child_ingest
    used_components = {row.component_id for row in terminal.sequence_boundaries}
    if not used_components or not used_components.issubset({"ALA", "GLY"}):
        _raise_policy(
            "unsupported_component",
            "the exact preparation profile accepts only ALA and GLY",
        )
    component_rows = {row.comp_id: row for row in child.component_rows}
    if set(component_rows) != used_components:
        _raise_policy(
            "component_template_coverage_mismatch",
            "component definitions must exactly equal sequence-used components",
        )
    annotations = {
        (row.comp_id, row.atom_id, row.template_ordinal): row
        for row in terminal.atom_annotations
    }
    child_atoms_by_component: dict[str, list[Any]] = {}
    for row in child.component_atom_rows:
        child_atoms_by_component.setdefault(row.comp_id, []).append(row)
    child_bonds_by_component: dict[str, list[Any]] = {}
    for row in child.component_bond_rows:
        child_bonds_by_component.setdefault(row.comp_id, []).append(row)

    for component_id in sorted(used_components):
        component = component_rows[component_id]
        if component.component_type != "L-peptide linking":
            _raise_policy(
                "component_type_policy_mismatch",
                "child-normalized component type must be L-peptide linking",
            )
        if component.formal_charge != 0:
            _raise_policy(
                "component_formal_charge_policy_mismatch",
                "selected component formal charge must be zero",
            )
        rule = standard_l_peptide_preparation_component_rule(component_id)
        observed_atoms = child_atoms_by_component.get(component_id, [])
        if len(observed_atoms) != len(rule.atoms):
            _raise_policy(
                "component_atom_policy_mismatch",
                "component atom inventory differs from the exact policy",
            )
        for observed, expected in zip(observed_atoms, rule.atoms, strict=True):
            if (
                observed.atom_id != expected.atom_id
                or observed.element != expected.element
                or observed.charge != expected.formal_charge
                or observed.aromatic != (expected.aromatic_flag == "Y")
                or observed.stereo != expected.stereo_config
                or observed.ordinal != expected.ccd_ordinal
            ):
                _raise_policy(
                    "component_atom_policy_mismatch",
                    "component atom row differs from the exact policy",
                )
            annotation = annotations.get(
                (component_id, expected.atom_id, expected.ccd_ordinal)
            )
            if annotation is None or (
                annotation.leaving_atom != (expected.leaving_atom_flag == "Y")
                or annotation.backbone_atom != (expected.backbone_atom_flag == "Y")
                or annotation.n_terminal_atom != (expected.n_terminal_atom_flag == "Y")
                or annotation.c_terminal_atom != (expected.c_terminal_atom_flag == "Y")
            ):
                _raise_policy(
                    "terminal_annotation_policy_mismatch",
                    "terminal/leaving flags differ from the exact engine policy",
                )
        observed_bonds = child_bonds_by_component.get(component_id, [])
        if len(observed_bonds) != len(rule.bonds):
            _raise_policy(
                "component_bond_policy_mismatch",
                "component bond inventory differs from the exact policy",
            )
        for observed, expected in zip(observed_bonds, rule.bonds, strict=True):
            if (
                observed.atom_id_1 != expected.atom_id_1
                or observed.atom_id_2 != expected.atom_id_2
                or observed.value_order != expected.value_order
                or observed.order != expected.bond_order
                or observed.aromatic != (expected.aromatic_flag == "Y")
                or observed.stereo != expected.stereo_config
                or observed.ordinal != expected.ccd_ordinal
            ):
                _raise_policy(
                    "component_bond_policy_mismatch",
                    "component bond row differs from the exact policy",
                )


def _instances_for_system(
    terminal: MmcifPolymerComponentTerminalLeavingPolicyIngestResult,
    system: AllAtomSystem,
) -> tuple[_Instance, ...]:
    residue_by_key: dict[tuple[str, int], tuple[Chain, Residue]] = {}
    for chain in system.chains:
        for residue_index in chain.residue_indices:
            residue = system.residues[residue_index]
            key = (chain.chain_id, residue.sequence_number)
            if key in residue_by_key:
                _raise_policy(
                    "duplicate_system_residue_identity",
                    "source residue label identities must be unique",
                )
            residue_by_key[key] = (chain, residue)
    instances: list[_Instance] = []
    observed_keys: set[tuple[str, int]] = set()
    for boundary in terminal.sequence_boundaries:
        key = (boundary.asym_id, boundary.sequence_number)
        pair = residue_by_key.get(key)
        if pair is None or key in observed_keys:
            _raise_policy(
                "boundary_system_join_mismatch",
                "sequence boundary evidence must bijectively join source residues",
            )
        observed_keys.add(key)
        chain, residue = pair
        if (
            chain.entity_id != boundary.entity_id
            or residue.name != boundary.component_id
            or residue.entity_type != "polymer"
            or residue.insertion_code
        ):
            _raise_policy(
                "boundary_system_join_mismatch",
                "source residue identity differs from boundary evidence",
            )
        standard_l_peptide_preparation_role_rule(boundary.position_role)
        instances.append(
            _Instance(
                asym_id=boundary.asym_id,
                entity_id=boundary.entity_id,
                sequence_number=boundary.sequence_number,
                component_id=boundary.component_id,
                role=boundary.position_role,
                source_chain_index=chain.index,
                source_residue_index=residue.index,
            )
        )
    if observed_keys != set(residue_by_key):
        _raise_policy(
            "boundary_system_join_mismatch",
            "source residues and boundary evidence do not have equal coverage",
        )
    instances.sort(key=lambda row: (row.asym_id, row.sequence_number))
    return tuple(instances)


def _hydrogen_parent_by_atom_id(component_id: str) -> dict[str, str]:
    rule = standard_l_peptide_preparation_component_rule(component_id)
    element_by_id = {row.atom_id: row.element for row in rule.atoms}
    parents: dict[str, str] = {}
    for atom in rule.atoms:
        if atom.element != "H":
            continue
        matches = [
            bond
            for bond in rule.bonds
            if atom.atom_id in {bond.atom_id_1, bond.atom_id_2}
        ]
        if len(matches) != 1 or matches[0].bond_order != 1.0:
            _raise_policy(
                "hydrogen_parent_policy_invalid",
                "every policy hydrogen must have exactly one single-bond parent",
            )
        bond = matches[0]
        parent = bond.atom_id_2 if bond.atom_id_1 == atom.atom_id else bond.atom_id_1
        if element_by_id[parent] == "H":
            _raise_policy(
                "hydrogen_parent_policy_invalid",
                "policy hydrogen parent must be a heavy atom",
            )
        parents[atom.atom_id] = parent
    return parents


def _validate_source_system_policy(
    terminal: MmcifPolymerComponentTerminalLeavingPolicyIngestResult,
    system: AllAtomSystem,
    instances: tuple[_Instance, ...],
) -> None:
    validation = validate_all_atom_system(system)
    if validation.errors:
        _raise_policy(
            "source_system_invalid",
            "terminal component child returned an invalid all-atom system",
        )
    if not attached_canonical_topology_sha256_matches(system):
        _raise_policy(
            "source_topology_binding_mismatch",
            "source child canonical topology attachment is stale",
        )
    if not attached_parser_observation_sha256_matches(system):
        _raise_policy(
            "source_observation_binding_mismatch",
            "source child parser observation attachment is stale",
        )
    if system.model_count != 1 or system.cell is not None:
        _raise_policy(
            "unsupported_source_context",
            "the exact profile requires one nonperiodic coordinate model",
        )

    instance_by_residue = {row.source_residue_index: row for row in instances}
    bonds_by_residue: dict[int, list[Bond]] = {
        residue.index: [] for residue in system.residues
    }
    for bond in system.bonds:
        residue_i = system.atoms[bond.atom_i].residue_index
        residue_j = system.atoms[bond.atom_j].residue_index
        if residue_i != residue_j:
            _raise_policy(
                "source_inter_residue_bond_not_allowed",
                "component child must not contain inter-residue bonds",
            )
        bonds_by_residue[residue_i].append(bond)

    for residue in system.residues:
        instance = instance_by_residue[residue.index]
        rule = standard_l_peptide_preparation_component_rule(instance.component_id)
        expected_by_id = {row.atom_id: row for row in rule.atoms}
        source_atoms = [system.atoms[index] for index in residue.atom_indices]
        observed_by_id = {atom.name: atom for atom in source_atoms}
        if len(observed_by_id) != len(source_atoms) or set(observed_by_id) != set(
            expected_by_id
        ):
            _raise_policy(
                "source_residue_atom_policy_mismatch",
                "every source residue must contain the complete exact component template",
            )
        for atom_id, expected in expected_by_id.items():
            atom = observed_by_id[atom_id]
            metadata = atom.metadata
            expected_atom_stereo = (
                "none" if expected.stereo_config == "N" else expected.stereo_config
            )
            if (
                atom.element != expected.element
                or atom.formal_charge_known is not True
                or atom.formal_charge != expected.formal_charge
                or atom.aromatic is not False
                or atom.stereo.lower() != expected_atom_stereo.lower()
                or atom.altloc
                or atom.isotope_mass_number is not None
                or atom.atom_map is not None
                or atom.partial_charge_e is not None
            ):
                _raise_policy(
                    "source_atom_state_policy_mismatch",
                    "source atom state differs from the exact component policy",
                )
            if expected.element == "H" and metadata.get("hydrogen_origin") != "source":
                _raise_policy(
                    "source_hydrogen_origin_mismatch",
                    "every profile hydrogen must be explicitly observed in source",
                )
            if metadata.get("formal_charge_source") not in {
                "_atom_site.pdbx_formal_charge",
                "_chem_comp_atom.charge",
            }:
                _raise_policy(
                    "source_formal_charge_origin_mismatch",
                    "formal charge must be observed in the exact mmCIF projection",
                )

        expected_pairs = {
            tuple(sorted((bond.atom_id_1, bond.atom_id_2))): (
                bond.bond_order,
                bond.aromatic_flag == "Y",
            )
            for bond in rule.bonds
        }
        observed_pairs: dict[tuple[str, str], tuple[float, bool]] = {}
        for bond in bonds_by_residue[residue.index]:
            left = system.atoms[bond.atom_i].name
            right = system.atoms[bond.atom_j].name
            pair = tuple(sorted((left, right)))
            if pair in observed_pairs:
                _raise_policy(
                    "duplicate_source_residue_bond",
                    "component child contains a duplicate residue bond",
                )
            observed_pairs[pair] = (bond.order, bond.aromatic)
        if observed_pairs != expected_pairs:
            _raise_policy(
                "source_residue_bond_policy_mismatch",
                "source residue bonds differ from the exact component policy",
            )


def _mapping_document(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_id": MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_MAPPING_SCHEMA_ID,
        "profile_id": MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_PROFILE_ID,
        "partition_semantics": (
            "all_source_atoms_equal_retained_disjoint_union_policy_deleted"
        ),
        "rows": rows,
    }


def _parameter_inventory_document(
    system: AllAtomSystem,
    identities: tuple[_PreparedAtomIdentity, ...],
) -> dict[str, Any]:
    identity_by_index = {row.prepared_index: row for row in identities}
    neighbors: list[list[int]] = [[] for _ in system.atoms]
    for bond in system.bonds:
        neighbors[bond.atom_i].append(bond.atom_j)
        neighbors[bond.atom_j].append(bond.atom_i)
    for values in neighbors:
        values.sort()
    angles: list[dict[str, Any]] = []
    for center, values in enumerate(neighbors):
        for first_index, atom_i in enumerate(values):
            for atom_k in values[first_index + 1 :]:
                angles.append({"atom_i": atom_i, "atom_j": center, "atom_k": atom_k})
                if len(angles) > MAX_MMCIF_STANDARD_L_PEPTIDE_PARAMETER_ANGLES:
                    _raise_policy(
                        "too_many_parameter_angle_requirements",
                        "parameter angle requirement count exceeds the hard cap",
                    )
    proper_paths: set[tuple[int, int, int, int]] = set()
    for bond in system.bonds:
        atom_j, atom_k = bond.atom_i, bond.atom_j
        for atom_i in neighbors[atom_j]:
            if atom_i == atom_k:
                continue
            for atom_l in neighbors[atom_k]:
                if atom_l in {atom_j, atom_i}:
                    continue
                forward = (atom_i, atom_j, atom_k, atom_l)
                reverse = tuple(reversed(forward))
                proper_paths.add(min(forward, reverse))
                if len(proper_paths) > MAX_MMCIF_STANDARD_L_PEPTIDE_PARAMETER_PROPERS:
                    _raise_policy(
                        "too_many_parameter_proper_requirements",
                        "parameter proper requirement count exceeds the hard cap",
                    )
    propers = [
        {
            "atom_i": path[0],
            "atom_j": path[1],
            "atom_k": path[2],
            "atom_l": path[3],
        }
        for path in sorted(proper_paths)
    ]
    atom_rows = [
        {
            "prepared_index": row.prepared_index,
            "asym_id": row.asym_id,
            "sequence_number": row.sequence_number,
            "component_id": row.component_id,
            "sequence_role": row.role,
            "atom_id": row.atom_id,
            "element": row.element,
            "formal_charge": row.formal_charge,
            "stereo": row.stereo,
            "partial_charge_parameter_required": True,
            "nonbonded_parameter_required": True,
        }
        for row in identities
    ]
    bond_rows = [
        {
            "bond_index": bond.index,
            "atom_i": bond.atom_i,
            "atom_j": bond.atom_j,
            "order_ieee754_binary64_be": struct.pack(">d", bond.order).hex(),
            "identity_i": identity_by_index[bond.atom_i].atom_id,
            "identity_j": identity_by_index[bond.atom_j].atom_id,
        }
        for bond in system.bonds
    ]
    return {
        "schema_id": (
            MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_PARAMETER_REQUIREMENT_SCHEMA_ID
        ),
        "profile_id": MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_PROFILE_ID,
        "inventory_semantics": (
            "exact_instance_requirements_not_force_field_types_or_parameters"
        ),
        "production_parameter_set_status": "missing",
        "atom_requirements": atom_rows,
        "bond_requirements": bond_rows,
        "angle_requirements": angles,
        "proper_torsion_requirements": propers,
        "nonbonded_site_count": len(atom_rows),
        "partial_charge_site_count": len(atom_rows),
        "parameterability_assessed": False,
        "parameterizable": False,
    }


def _prepared_atom_marker(identity: _PreparedAtomIdentity) -> dict[str, Any]:
    return {
        "profile_id": MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_PROFILE_ID,
        "source_atom_index": identity.source_index,
        "source_atom_serial": identity.source_serial,
        "asym_id": identity.asym_id,
        "entity_id": identity.entity_id,
        "sequence_number": identity.sequence_number,
        "component_id": identity.component_id,
        "sequence_role": identity.role,
        "atom_id": identity.atom_id,
        "hydrogen_parent_atom_id": identity.h_parent_atom_id,
        "preparation_rule_manifest_sha256": (
            STANDARD_L_PEPTIDE_PREPARATION_RULE_MANIFEST_SHA256
        ),
    }


def _transform_system(
    outer_source: bytes,
    source_id: str,
    terminal: MmcifPolymerComponentTerminalLeavingPolicyIngestResult,
    archive: MmcifArchiveStandardLPeptideTopologyIngestResult,
) -> _TransformOutput:
    source = terminal.system
    instances = _instances_for_system(terminal, source)
    _validate_source_system_policy(terminal, source, instances)
    if source.atom_count > MAX_MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_ATOMS:
        _raise_policy("too_many_source_atoms", "source atom count exceeds the hard cap")

    source_atom_by_identity: dict[tuple[str, int, str], Atom] = {}
    for instance in instances:
        residue = source.residues[instance.source_residue_index]
        for atom_index in residue.atom_indices:
            atom = source.atoms[atom_index]
            key = (instance.asym_id, instance.sequence_number, atom.name)
            if key in source_atom_by_identity:
                _raise_policy(
                    "duplicate_source_atom_identity",
                    "source atom label identities must be unique",
                )
            source_atom_by_identity[key] = atom

    canonical_instances = tuple(
        sorted(instances, key=lambda row: (row.asym_id, row.sequence_number))
    )
    chain_ids = tuple(sorted({row.asym_id for row in canonical_instances}))
    chain_index_by_id = {chain_id: index for index, chain_id in enumerate(chain_ids)}
    source_index_to_prepared: dict[int, int] = {}
    prepared_atoms: list[Atom] = []
    prepared_identities: list[_PreparedAtomIdentity] = []
    prepared_residues: list[Residue] = []
    prepared_chains: list[Chain] = []
    prepared_atom_indices_by_instance: dict[tuple[str, int], tuple[int, ...]] = {}
    prepared_endpoint_by_identity: dict[tuple[str, int, str], int] = {}
    source_indices_in_prepared_order: list[int] = []

    residue_index_by_instance: dict[tuple[str, int], int] = {}
    for instance in canonical_instances:
        key = (instance.asym_id, instance.sequence_number)
        residue_index = len(prepared_residues)
        residue_index_by_instance[key] = residue_index
        retained_rules = standard_l_peptide_expected_retained_atoms(
            instance.component_id, instance.role
        )
        h_parents = _hydrogen_parent_by_atom_id(instance.component_id)
        atom_indices: list[int] = []
        for atom_rule in retained_rules:
            source_atom = source_atom_by_identity.get(
                (instance.asym_id, instance.sequence_number, atom_rule.atom_id)
            )
            if source_atom is None:
                _raise_policy(
                    "retained_source_atom_missing",
                    "policy-retained source atom is missing",
                )
            prepared_index = len(prepared_atoms)
            identity = _PreparedAtomIdentity(
                prepared_index=prepared_index,
                source_index=source_atom.index,
                source_serial=source_atom.serial,
                asym_id=instance.asym_id,
                entity_id=instance.entity_id,
                sequence_number=instance.sequence_number,
                component_id=instance.component_id,
                role=instance.role,
                atom_id=atom_rule.atom_id,
                element=atom_rule.element,
                formal_charge=atom_rule.formal_charge,
                stereo=atom_rule.stereo_config,
                h_parent_atom_id=h_parents.get(atom_rule.atom_id),
            )
            atom_metadata = dict(source_atom.metadata)
            atom_metadata.pop("mmcif_polymer_component_topology", None)
            atom_metadata[MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_MARKER_KEY] = (
                _prepared_atom_marker(identity)
            )
            prepared_atoms.append(
                replace(
                    source_atom,
                    index=prepared_index,
                    residue_index=residue_index,
                    metadata=atom_metadata,
                )
            )
            prepared_identities.append(identity)
            source_index_to_prepared[source_atom.index] = prepared_index
            source_indices_in_prepared_order.append(source_atom.index)
            atom_indices.append(prepared_index)
            prepared_endpoint_by_identity[
                (instance.asym_id, instance.sequence_number, atom_rule.atom_id)
            ] = prepared_index
        prepared_atom_indices_by_instance[key] = tuple(atom_indices)
        source_residue = source.residues[instance.source_residue_index]
        residue_metadata = dict(source_residue.metadata)
        residue_metadata.pop("mmcif_polymer_component_topology", None)
        residue_metadata[MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_MARKER_KEY] = {
            "profile_id": MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_PROFILE_ID,
            "asym_id": instance.asym_id,
            "entity_id": instance.entity_id,
            "sequence_number": instance.sequence_number,
            "component_id": instance.component_id,
            "sequence_role": instance.role,
            "preparation_rule_manifest_sha256": (
                STANDARD_L_PEPTIDE_PREPARATION_RULE_MANIFEST_SHA256
            ),
        }
        prepared_residues.append(
            replace(
                source_residue,
                index=residue_index,
                chain_index=chain_index_by_id[instance.asym_id],
                atom_indices=tuple(atom_indices),
                metadata=residue_metadata,
            )
        )

    for chain_id in chain_ids:
        chain_instances = [
            row for row in canonical_instances if row.asym_id == chain_id
        ]
        source_chain = source.chains[chain_instances[0].source_chain_index]
        chain_metadata = dict(source_chain.metadata)
        chain_metadata.pop("mmcif_polymer_component_topology", None)
        chain_metadata[MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_MARKER_KEY] = {
            "profile_id": MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_PROFILE_ID,
            "asym_id": chain_id,
            "sequence_adjacent_link_count": max(0, len(chain_instances) - 1),
            "preparation_rule_manifest_sha256": (
                STANDARD_L_PEPTIDE_PREPARATION_RULE_MANIFEST_SHA256
            ),
        }
        prepared_chains.append(
            replace(
                source_chain,
                index=chain_index_by_id[chain_id],
                residue_indices=tuple(
                    residue_index_by_instance[(row.asym_id, row.sequence_number)]
                    for row in chain_instances
                ),
                metadata=chain_metadata,
            )
        )

    mapping_rows: list[dict[str, Any]] = []
    source_instance_by_residue = {
        row.source_residue_index: row for row in canonical_instances
    }
    for atom in source.atoms:
        instance = source_instance_by_residue[atom.residue_index]
        prepared_index = source_index_to_prepared.get(atom.index)
        role_rule = standard_l_peptide_preparation_role_rule(instance.role)
        deleted = atom.name in role_rule.deleted_atom_ids
        if deleted != (prepared_index is None):
            _raise_policy(
                "atom_partition_mismatch",
                "source atom is not exactly retained or policy-deleted",
            )
        h_parent = _hydrogen_parent_by_atom_id(instance.component_id).get(atom.name)
        deletion_reason = None
        if deleted:
            deletion_reason = (
                "incoming_n_terminal_leaving_hydrogen"
                if atom.name == "H2"
                else "outgoing_c_terminal_leaving_group"
            )
        mapping_rows.append(
            {
                "source_index": atom.index,
                "source_serial": atom.serial,
                "prepared_index": prepared_index,
                "status": "policy_deleted" if deleted else "retained",
                "deletion_reason": deletion_reason,
                "asym_id": instance.asym_id,
                "entity_id": instance.entity_id,
                "sequence_number": instance.sequence_number,
                "component_id": instance.component_id,
                "sequence_role": instance.role,
                "atom_id": atom.name,
                "element": atom.element,
                "formal_charge_known": atom.formal_charge_known,
                "formal_charge": atom.formal_charge,
                "stereo": atom.stereo.upper(),
                "hydrogen_parent_atom_id": h_parent,
            }
        )
    if len(mapping_rows) != source.atom_count:
        _raise_policy(
            "atom_partition_mismatch", "atom mapping does not cover every source atom"
        )
    prepared_targets = sorted(
        row["prepared_index"]
        for row in mapping_rows
        if row["prepared_index"] is not None
    )
    if prepared_targets != list(range(len(prepared_atoms))):
        _raise_policy(
            "retained_atom_mapping_not_bijective",
            "retained source atoms must bijectively cover prepared indices",
        )
    mapping_bytes = _canonical_json_bytes(_mapping_document(mapping_rows))

    retained_input_bonds = 0
    deleted_input_bonds = 0
    for bond in source.bonds:
        retained_i = bond.atom_i in source_index_to_prepared
        retained_j = bond.atom_j in source_index_to_prepared
        if retained_i and retained_j:
            retained_input_bonds += 1
        else:
            deleted_input_bonds += 1

    pending_bonds: list[Bond] = []
    for instance in canonical_instances:
        for rule_bond in standard_l_peptide_expected_retained_bonds(
            instance.component_id, instance.role
        ):
            atom_i = prepared_endpoint_by_identity[
                (instance.asym_id, instance.sequence_number, rule_bond.atom_id_1)
            ]
            atom_j = prepared_endpoint_by_identity[
                (instance.asym_id, instance.sequence_number, rule_bond.atom_id_2)
            ]
            pending_bonds.append(
                Bond(
                    index=-1,
                    atom_i=min(atom_i, atom_j),
                    atom_j=max(atom_i, atom_j),
                    order=rule_bond.bond_order,
                    aromatic=False,
                    stereo="none",
                    source="exact_standard_l_peptide_neutral_preparation_policy",
                    metadata={
                        MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_MARKER_KEY: {
                            "bond_kind": "retained_component_policy_bond",
                            "asym_id": instance.asym_id,
                            "sequence_number": instance.sequence_number,
                            "component_id": instance.component_id,
                            "source_component_bond_ordinal": rule_bond.ccd_ordinal,
                            "rule_manifest_sha256": (
                                STANDARD_L_PEPTIDE_PREPARATION_RULE_MANIFEST_SHA256
                            ),
                        }
                    },
                )
            )
    if len(pending_bonds) != retained_input_bonds:
        _raise_policy(
            "input_bond_partition_mismatch",
            "retained input bonds differ from the policy-induced graph",
        )

    peptide_bond_count = 0
    for chain_id in chain_ids:
        chain_instances = [
            row for row in canonical_instances if row.asym_id == chain_id
        ]
        for left, right in zip(chain_instances, chain_instances[1:]):
            if right.sequence_number != left.sequence_number + 1:
                _raise_policy(
                    "noncontiguous_sequence_positions",
                    "peptide links require contiguous sequence positions",
                )
            atom_i = prepared_endpoint_by_identity[
                (left.asym_id, left.sequence_number, "C")
            ]
            atom_j = prepared_endpoint_by_identity[
                (right.asym_id, right.sequence_number, "N")
            ]
            pending_bonds.append(
                Bond(
                    index=-1,
                    atom_i=min(atom_i, atom_j),
                    atom_j=max(atom_i, atom_j),
                    order=STANDARD_L_PEPTIDE_PREPARATION_INTER_RESIDUE_RULE.bond_order,
                    aromatic=False,
                    stereo="none",
                    source="exact_standard_l_peptide_neutral_preparation_policy",
                    metadata={
                        MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_MARKER_KEY: {
                            "bond_kind": "sequence_adjacent_peptide_bond",
                            "asym_id": chain_id,
                            "left_sequence_number": left.sequence_number,
                            "right_sequence_number": right.sequence_number,
                            "left_atom_id": "C",
                            "right_atom_id": "N",
                            "rule_id": (
                                STANDARD_L_PEPTIDE_PREPARATION_INTER_RESIDUE_RULE.rule_id
                            ),
                            "rule_manifest_sha256": (
                                STANDARD_L_PEPTIDE_PREPARATION_RULE_MANIFEST_SHA256
                            ),
                        }
                    },
                )
            )
            peptide_bond_count += 1
    if len(pending_bonds) > MAX_MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_BONDS:
        _raise_policy(
            "too_many_prepared_bonds", "prepared bond count exceeds the hard cap"
        )
    endpoint_pairs = [(bond.atom_i, bond.atom_j) for bond in pending_bonds]
    if len(endpoint_pairs) != len(set(endpoint_pairs)):
        _raise_policy(
            "duplicate_prepared_bond", "prepared graph contains duplicate bonds"
        )
    pending_bonds.sort(key=lambda bond: (bond.atom_i, bond.atom_j))
    prepared_bonds = tuple(
        replace(bond, index=index) for index, bond in enumerate(pending_bonds)
    )

    expected_link_count = sum(
        max(0, len([row for row in canonical_instances if row.asym_id == chain_id]) - 1)
        for chain_id in chain_ids
    )
    deleted_atom_count = source.atom_count - len(prepared_atoms)
    if (
        peptide_bond_count != expected_link_count
        or deleted_atom_count != 3 * expected_link_count
        or deleted_input_bonds != 3 * expected_link_count
        or len(prepared_bonds) != len(source.bonds) - 2 * expected_link_count
    ):
        _raise_policy(
            "transform_partition_count_mismatch",
            "atom and bond partitions differ from the exact linkage policy",
        )

    coordinate_indices = torch.tensor(
        source_indices_in_prepared_order,
        dtype=torch.long,
        device=source.coordinates.device,
    )
    prepared_coordinates = source.coordinates.index_select(
        1, coordinate_indices
    ).clone()
    source_snapshot_sha256 = _sha256_bytes(serialize_all_atom_system(source))
    archive_snapshot_sha256 = _sha256_bytes(serialize_all_atom_system(archive.system))
    base_marker = {
        "profile_id": MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_PROFILE_ID,
        "policy_id": MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_POLICY_ID,
        "preparation_rule_manifest_schema_id": (
            STANDARD_L_PEPTIDE_PREPARATION_RULE_MANIFEST_SCHEMA_ID
        ),
        "preparation_rule_manifest_sha256": (
            STANDARD_L_PEPTIDE_PREPARATION_RULE_MANIFEST_SHA256
        ),
        "heavy_rule_manifest_schema_id": STANDARD_L_PEPTIDE_RULE_MANIFEST_SCHEMA_ID,
        "heavy_rule_manifest_sha256": STANDARD_L_PEPTIDE_RULE_MANIFEST_SHA256,
        "source_hash_semantics": "raw_outer_source_bytes_tamper_evidence",
        "source_authenticated": False,
    }
    provenance = replace(
        source.provenance,
        source_id=source_id,
        source_sha256=_sha256_bytes(outer_source),
        parser_name=(MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_TRANSFORMER_NAME),
        parser_version=(
            MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_TRANSFORMER_VERSION
        ),
        operations=(
            "reproject_exact_terminal_component_child/v1",
            "reproject_exact_archive_heavy_child/v1",
            "validate_exact_ALA_GLY_CCD_neutral_linkage_policy/v1",
            "apply_role_specific_leaving_atom_deletions/v1",
            "materialize_same_asym_sequence_adjacent_C_N_bonds/v1",
        ),
        parent_sha256=(source_snapshot_sha256, archive_snapshot_sha256),
        preparation_ready=False,
        claim_safe=False,
        metadata={MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_MARKER_KEY: base_marker},
    )
    provisional = AllAtomSystem(
        system_id=(f"{source.system_id}:ALA_GLY_CCD_neutral_linkage_prepared_v1"),
        atoms=tuple(prepared_atoms),
        bonds=prepared_bonds,
        residues=tuple(prepared_residues),
        chains=tuple(prepared_chains),
        coordinates=prepared_coordinates,
        provenance=provenance,
        cell=None,
        coordinate_unit=source.coordinate_unit,
        metadata={MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_MARKER_KEY: base_marker},
        schema_id=source.schema_id,
    )
    topology_sha256 = canonical_topology_sha256(provisional)
    inventory_document = _parameter_inventory_document(
        provisional, tuple(prepared_identities)
    )
    inventory_document["canonical_topology_schema_id"] = CANONICAL_TOPOLOGY_SCHEMA_ID
    inventory_document["canonical_topology_sha256"] = topology_sha256
    parameter_inventory_bytes = _canonical_json_bytes(inventory_document)
    marker = {
        **base_marker,
        "atom_mapping_schema_id": (
            MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_MAPPING_SCHEMA_ID
        ),
        "atom_mapping_sha256": _sha256_bytes(mapping_bytes),
        "parameter_requirement_inventory_schema_id": (
            MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_PARAMETER_REQUIREMENT_SCHEMA_ID
        ),
        "parameter_requirement_inventory_sha256": _sha256_bytes(
            parameter_inventory_bytes
        ),
        "source_atom_count": source.atom_count,
        "prepared_atom_count": len(prepared_atoms),
        "policy_deleted_atom_count": deleted_atom_count,
        "source_bond_count": len(source.bonds),
        "retained_input_bond_count": retained_input_bonds,
        "policy_deleted_input_bond_count": deleted_input_bonds,
        "materialized_peptide_bond_count": peptide_bond_count,
        "prepared_bond_count": len(prepared_bonds),
        **_profile_true_document(),
        **_authority_false_document(),
    }
    system = replace(
        provisional,
        metadata={MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_MARKER_KEY: marker},
        provenance=replace(
            provisional.provenance,
            metadata={
                MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_MARKER_KEY: marker,
                "canonical_topology_schema_id": CANONICAL_TOPOLOGY_SCHEMA_ID,
                "canonical_topology_sha256": topology_sha256,
            },
        ),
    )
    system = attach_parser_observation_digest(system)
    validation = validate_all_atom_system(system)
    if validation.errors:
        _raise_policy(
            "prepared_system_invalid",
            "transformed system violates canonical invariants",
        )
    if not attached_canonical_topology_sha256_matches(system):
        _raise_policy(
            "prepared_topology_binding_mismatch",
            "prepared canonical topology attachment is stale",
        )
    if not attached_parser_observation_sha256_matches(system):
        _raise_policy(
            "prepared_observation_binding_mismatch",
            "prepared observation attachment is stale",
        )
    return _TransformOutput(
        system=system,
        mapping_bytes=mapping_bytes,
        parameter_inventory_bytes=parameter_inventory_bytes,
        prepared_identities=tuple(prepared_identities),
        retained_input_bond_count=retained_input_bonds,
        deleted_input_bond_count=deleted_input_bonds,
        peptide_bond_count=peptide_bond_count,
    )


def _normalized_heavy_projection(
    system: AllAtomSystem,
    *,
    prepared_identities: tuple[_PreparedAtomIdentity, ...] | None = None,
) -> dict[str, Any]:
    identity_by_index: dict[int, tuple[str, str, int, str, str]] = {}
    if prepared_identities is not None:
        for identity in prepared_identities:
            if identity.element != "H":
                identity_by_index[identity.prepared_index] = (
                    identity.asym_id,
                    identity.entity_id,
                    identity.sequence_number,
                    identity.component_id,
                    identity.atom_id,
                )
    else:
        for chain in system.chains:
            for residue_index in chain.residue_indices:
                residue = system.residues[residue_index]
                for atom_index in residue.atom_indices:
                    atom = system.atoms[atom_index]
                    if atom.element != "H":
                        identity_by_index[atom.index] = (
                            chain.chain_id,
                            chain.entity_id,
                            residue.sequence_number,
                            residue.name,
                            atom.name,
                        )
    atom_rows: list[dict[str, Any]] = []
    for atom_index, identity in identity_by_index.items():
        atom = system.atoms[atom_index]
        coordinate_models = [
            [
                struct.pack(">d", float(value)).hex()
                for value in system.coordinates[model_index, atom_index].tolist()
            ]
            for model_index in range(system.model_count)
        ]
        atom_rows.append(
            {
                "identity": list(identity),
                "element": atom.element,
                "coordinate_models_binary64_be": coordinate_models,
            }
        )
    atom_rows.sort(key=lambda row: tuple(row["identity"]))
    bond_rows: list[dict[str, Any]] = []
    for bond in system.bonds:
        if bond.atom_i not in identity_by_index or bond.atom_j not in identity_by_index:
            continue
        left = identity_by_index[bond.atom_i]
        right = identity_by_index[bond.atom_j]
        endpoint_pair = sorted((left, right))
        bond_rows.append(
            {
                "left": list(endpoint_pair[0]),
                "right": list(endpoint_pair[1]),
                "order_ieee754_binary64_be": struct.pack(">d", bond.order).hex(),
                "aromatic": bond.aromatic,
            }
        )
    bond_rows.sort(key=lambda row: (tuple(row["left"]), tuple(row["right"])))
    return {
        "schema_id": "betelgeuze.standard_l_peptide_heavy_crosscheck/1.0.0",
        "atom_rows": atom_rows,
        "bond_rows": bond_rows,
    }


def _crosscheck_heavy_projection(
    archive: MmcifArchiveStandardLPeptideTopologyIngestResult,
    transformed: _TransformOutput,
) -> bytes:
    archive_document = _normalized_heavy_projection(archive.system)
    prepared_document = _normalized_heavy_projection(
        transformed.system, prepared_identities=transformed.prepared_identities
    )
    if archive_document != prepared_document:
        _raise_policy(
            "prepared_heavy_reference_mismatch",
            "prepared heavy induced graph differs from the independent archive child",
        )
    return _canonical_json_bytes(prepared_document)


@dataclass(frozen=True, slots=True)
class _PreparedState:
    outer_source: bytes = field(repr=False)
    source_id: str = field(repr=False)
    block_name: str
    terminal_source: bytes = field(repr=False)
    archive_source: bytes = field(repr=False)
    prepared_snapshot: bytes = field(repr=False)
    mapping_bytes: bytes = field(repr=False)
    parameter_inventory_bytes: bytes = field(repr=False)
    heavy_crosscheck_bytes: bytes = field(repr=False)
    source_binding_bytes: bytes = field(repr=False)
    report_bytes: bytes = field(repr=False)


def _source_binding_document(
    *,
    outer_source: bytes,
    source_id: str,
    block_name: str,
    terminal_source: bytes,
    archive_source: bytes,
    terminal_document: Mapping[str, Any],
    archive_document: Mapping[str, Any],
    prepared_system: AllAtomSystem,
    prepared_snapshot: bytes,
    mapping_bytes: bytes,
    parameter_inventory_bytes: bytes,
    heavy_crosscheck_bytes: bytes,
) -> dict[str, Any]:
    return {
        "schema_id": (
            MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_SOURCE_BINDING_SCHEMA_ID
        ),
        "profile_id": MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_PROFILE_ID,
        "policy_id": MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_POLICY_ID,
        "outer_source_sha256": _sha256_bytes(outer_source),
        "source_id_sha256": _source_id_sha256(source_id),
        "data_block_name_sha256": _sha256_bytes(block_name.encode("ascii")),
        "terminal_child_source_sha256": _sha256_bytes(terminal_source),
        "terminal_child_projection_sha256": terminal_document["projection_sha256"],
        "terminal_child_state_sha256": terminal_document["state_sha256"],
        "terminal_child_source_binding_sha256": terminal_document[
            "source_binding_sha256"
        ],
        "terminal_child_stage_proof_sha256": terminal_document[
            "child_stage_proof_sha256"
        ],
        "terminal_component_child_source_binding_sha256": terminal_document[
            "child_source_binding_sha256"
        ],
        "terminal_component_child_snapshot_sha256": terminal_document[
            "child_augmented_system_snapshot_sha256"
        ],
        "terminal_component_child_observation_sha256": terminal_document[
            "child_augmented_system_parser_observation_sha256"
        ],
        "terminal_component_child_preparation_commitment_sha256": terminal_document[
            "child_preparation_inventory_commitment_sha256"
        ],
        "archive_child_source_sha256": _sha256_bytes(archive_source),
        "archive_child_projection_sha256": archive_document["projection_sha256"],
        "archive_child_topology_state_sha256": archive_document[
            "topology_state_sha256"
        ],
        "archive_child_source_binding_sha256": archive_document[
            "source_binding_sha256"
        ],
        "archive_child_system_snapshot_sha256": archive_document[
            "system_snapshot_sha256"
        ],
        "archive_child_topology_sha256": archive_document["canonical_topology_sha256"],
        "atom_mapping_sha256": _sha256_bytes(mapping_bytes),
        "parameter_requirement_inventory_sha256": _sha256_bytes(
            parameter_inventory_bytes
        ),
        "heavy_crosscheck_sha256": _sha256_bytes(heavy_crosscheck_bytes),
        "prepared_topology_sha256": canonical_topology_sha256(prepared_system),
        "prepared_observation_sha256": prepared_system.provenance.metadata[
            "parser_observation_sha256"
        ],
        "prepared_system_snapshot_sha256": _sha256_bytes(prepared_snapshot),
        "source_binding_semantics": (
            "tamper_evidence_recomputed_from_one_raw_outer_source_not_authentication"
        ),
        "source_authenticated": False,
    }


def _report_document(
    *,
    source_binding: Mapping[str, Any],
    terminal: MmcifPolymerComponentTerminalLeavingPolicyIngestResult,
    archive: MmcifArchiveStandardLPeptideTopologyIngestResult,
    transformed: _TransformOutput,
) -> dict[str, Any]:
    system = transformed.system
    mapping = json.loads(transformed.mapping_bytes.decode("ascii"))
    inventory = json.loads(transformed.parameter_inventory_bytes.decode("ascii"))
    source_system = terminal.system
    mapping_rows = mapping["rows"]
    retained_rows = [row for row in mapping_rows if row["status"] == "retained"]
    deleted_rows = [row for row in mapping_rows if row["status"] == "policy_deleted"]
    source_h_count = sum(atom.element == "H" for atom in source_system.atoms)
    prepared_h_count = sum(atom.element == "H" for atom in system.atoms)
    role_counts: dict[str, int] = {}
    component_counts: dict[str, int] = {}
    for boundary in terminal.sequence_boundaries:
        role_counts[boundary.position_role] = (
            role_counts.get(boundary.position_role, 0) + 1
        )
        component_counts[boundary.component_id] = (
            component_counts.get(boundary.component_id, 0) + 1
        )
    formal_charge_known_zero = all(
        atom.formal_charge_known and atom.formal_charge == 0 for atom in system.atoms
    )
    if not formal_charge_known_zero:
        _raise_policy(
            "prepared_formal_charge_policy_mismatch",
            "prepared atoms must all have known zero formal charge",
        )
    return {
        "schema_id": MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_REPORT_SCHEMA_ID,
        "schema_version": MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_VERSION,
        "profile_id": MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_PROFILE_ID,
        "policy_id": MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_POLICY_ID,
        "claim_scope": "exact_profile_preparation_transform_only",
        "status": "satisfied",
        "microstate_semantics": (
            "source_explicit_CCD_neutral_linkage_not_environmental_pH_or_"
            "protonation_correctness"
        ),
        "component_type_semantics": (
            "child_normalized_quoted_L_peptide_linking_for_ALA_and_GLY_not_"
            "byte_exact_official_GLY_component_type"
        ),
        "preparation_rule_manifest_schema_id": (
            STANDARD_L_PEPTIDE_PREPARATION_RULE_MANIFEST_SCHEMA_ID
        ),
        "preparation_rule_manifest_sha256": (
            STANDARD_L_PEPTIDE_PREPARATION_RULE_MANIFEST_SHA256
        ),
        "heavy_rule_manifest_schema_id": STANDARD_L_PEPTIDE_RULE_MANIFEST_SCHEMA_ID,
        "heavy_rule_manifest_sha256": STANDARD_L_PEPTIDE_RULE_MANIFEST_SHA256,
        "source_binding_schema_id": source_binding["schema_id"],
        "source_binding_sha256": _sha256_bytes(_canonical_json_bytes(source_binding)),
        **{
            key: value
            for key, value in source_binding.items()
            if key
            not in {
                "schema_id",
                "profile_id",
                "policy_id",
                "source_authenticated",
            }
        },
        "atom_mapping_schema_id": (
            MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_MAPPING_SCHEMA_ID
        ),
        "parameter_requirement_inventory_schema_id": (
            MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_PARAMETER_REQUIREMENT_SCHEMA_ID
        ),
        "source_atom_count": source_system.atom_count,
        "retained_source_atom_count": len(retained_rows),
        "policy_deleted_source_atom_count": len(deleted_rows),
        "prepared_atom_count": system.atom_count,
        "source_bond_count": len(source_system.bonds),
        "retained_input_bond_count": transformed.retained_input_bond_count,
        "policy_deleted_input_bond_count": transformed.deleted_input_bond_count,
        "materialized_peptide_bond_count": transformed.peptide_bond_count,
        "prepared_bond_count": len(system.bonds),
        "residue_count": len(system.residues),
        "chain_count": len(system.chains),
        "sequence_role_counts": [list(item) for item in sorted(role_counts.items())],
        "component_instance_counts": [
            list(item) for item in sorted(component_counts.items())
        ],
        "source_explicit_hydrogen_count": source_h_count,
        "prepared_retained_explicit_hydrogen_count": prepared_h_count,
        "policy_deleted_hydrogen_count": source_h_count - prepared_h_count,
        "generated_hydrogen_count": 0,
        "all_prepared_formal_charges_known_zero": formal_charge_known_zero,
        "prepared_net_formal_charge": sum(atom.formal_charge for atom in system.atoms),
        "parameter_atom_requirement_count": len(inventory["atom_requirements"]),
        "parameter_bond_requirement_count": len(inventory["bond_requirements"]),
        "parameter_angle_requirement_count": len(inventory["angle_requirements"]),
        "parameter_proper_requirement_count": len(
            inventory["proper_torsion_requirements"]
        ),
        "profile_preparation_status": "satisfied",
        "generic_preparation_status": "incomplete",
        "parameterability_status": ("not_assessed_production_parameter_set_missing"),
        "blockers": [
            "source_digest_is_not_authentication",
            "environmental_ph_and_protonation_correctness_unassessed",
            "coordinate_geometry_and_chain_breaks_unassessed",
            "generic_preparation_not_ready",
            "production_parameter_set_missing",
            "parameterability_not_assessed",
            "physics_not_supported",
            "runtime_not_eligible",
            "simulation_not_authorized",
            "execution_not_authorized",
            "claim_not_authorized",
            "v2_1_not_complete",
        ],
        **_profile_true_document(),
        **_authority_false_document(),
    }


def _build_state(data: bytes, *, source_id: str) -> _PreparedState:
    _source_id_sha256(source_id)
    block = _parse_block(data)
    loops = _validate_surface(block)
    terminal_source = _terminal_child_source(block, loops)
    try:
        terminal = parse_mmcif_polymer_component_terminal_leaving_policy(
            terminal_source, source_id=source_id
        )
    except MmcifPolymerComponentTerminalLeavingPolicyError as exc:
        raise MmcifStandardLPeptideNeutralPreparationError(
            "terminal_component_child_rejected",
            f"terminal/component child rejected the exact projection ({exc.code})",
            line_number=exc.line_number,
        ) from None
    _validate_component_policy(terminal)
    archive_source = _archive_child_source(block, loops, terminal)
    try:
        archive = parse_mmcif_archive_standard_l_peptide_topology(
            archive_source, source_id=source_id
        )
    except MmcifArchiveStandardLPeptideTopologyError as exc:
        raise MmcifStandardLPeptideNeutralPreparationError(
            "archive_heavy_child_rejected",
            f"archive-heavy child rejected the exact projection ({exc.code})",
            line_number=exc.line_number,
        ) from None
    transformed = _transform_system(data, source_id, terminal, archive)
    heavy_crosscheck_bytes = _crosscheck_heavy_projection(archive, transformed)
    prepared_snapshot = serialize_all_atom_system(transformed.system)
    terminal_document = terminal.to_dict()
    terminal_document["state_sha256"] = terminal.state_sha256
    archive_document = archive.to_dict()
    source_binding = _source_binding_document(
        outer_source=data,
        source_id=source_id,
        block_name=block.name,
        terminal_source=terminal_source,
        archive_source=archive_source,
        terminal_document=terminal_document,
        archive_document=archive_document,
        prepared_system=transformed.system,
        prepared_snapshot=prepared_snapshot,
        mapping_bytes=transformed.mapping_bytes,
        parameter_inventory_bytes=transformed.parameter_inventory_bytes,
        heavy_crosscheck_bytes=heavy_crosscheck_bytes,
    )
    source_binding_bytes = _canonical_json_bytes(source_binding)
    report = _report_document(
        source_binding=source_binding,
        terminal=terminal,
        archive=archive,
        transformed=transformed,
    )
    report_bytes = _canonical_json_bytes(report)
    return _PreparedState(
        outer_source=data,
        source_id=source_id,
        block_name=block.name,
        terminal_source=terminal_source,
        archive_source=archive_source,
        prepared_snapshot=prepared_snapshot,
        mapping_bytes=transformed.mapping_bytes,
        parameter_inventory_bytes=transformed.parameter_inventory_bytes,
        heavy_crosscheck_bytes=heavy_crosscheck_bytes,
        source_binding_bytes=source_binding_bytes,
        report_bytes=report_bytes,
    )


def _state_document(state: _PreparedState) -> dict[str, Any]:
    report = json.loads(state.report_bytes.decode("ascii"))
    return {
        "schema_id": MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_STATE_SCHEMA_ID,
        "profile_id": MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_PROFILE_ID,
        "outer_source_sha256": _sha256_bytes(state.outer_source),
        "source_id_sha256": _source_id_sha256(state.source_id),
        "data_block_name_sha256": _sha256_bytes(state.block_name.encode("ascii")),
        "terminal_source_sha256": _sha256_bytes(state.terminal_source),
        "archive_source_sha256": _sha256_bytes(state.archive_source),
        "prepared_snapshot_sha256": _sha256_bytes(state.prepared_snapshot),
        "mapping_sha256": _sha256_bytes(state.mapping_bytes),
        "parameter_inventory_sha256": _sha256_bytes(state.parameter_inventory_bytes),
        "heavy_crosscheck_sha256": _sha256_bytes(state.heavy_crosscheck_bytes),
        "source_binding_sha256": _sha256_bytes(state.source_binding_bytes),
        "report_sha256": _sha256_bytes(state.report_bytes),
        "prepared_topology_sha256": report["prepared_topology_sha256"],
    }


def _result_access_binding(
    value: "MmcifStandardLPeptideNeutralPreparationResult",
) -> bytes:
    state = value._state
    return _canonical_json_bytes(
        {
            "artifact_type": "MmcifStandardLPeptideNeutralPreparationResult",
            "self_object_id": id(value),
            "state_object_id": id(state),
            **_state_document(state),
        }
    )


def _report_access_binding(
    value: "MmcifStandardLPeptideNeutralPreparationReport",
) -> bytes:
    return _canonical_json_bytes(
        {
            "artifact_type": "MmcifStandardLPeptideNeutralPreparationReport",
            "self_object_id": id(value),
            "report_sha256": _sha256_bytes(value._report_bytes),
        }
    )


@dataclass(frozen=True, init=False)
class MmcifStandardLPeptideNeutralPreparationReport:
    """Detached immutable view of one factory-recomputed profile report."""

    _report_bytes: bytes = field(repr=False)
    _access_binding_bytes: bytes = field(repr=False)

    def __init__(
        self, report_bytes: bytes, *, _factory_token: object | None = None
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN or type(report_bytes) is not bytes:
            raise TypeError(
                "MmcifStandardLPeptideNeutralPreparationReport is factory-only"
            )
        document = json.loads(report_bytes.decode("ascii"))
        if (
            document.get("schema_id")
            != MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_REPORT_SCHEMA_ID
            or document.get("profile_id")
            != MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_PROFILE_ID
            or any(document.get(name) is not True for name in _PROFILE_TRUE_FIELDS)
            or any(document.get(name) is not False for name in _FALSE_AUTHORITY_FIELDS)
        ):
            raise MmcifStandardLPeptideNeutralPreparationError(
                "invalid_report_document", "stored report violates the fixed schema"
            )
        object.__setattr__(self, "_report_bytes", bytes(report_bytes))
        binding = _report_access_binding(self)
        object.__setattr__(self, "_access_binding_bytes", binding)
        _register_anchor(self, binding)

    @property
    def report_sha256(self) -> str:
        return _sha256_bytes(_validate_report(self))

    @property
    def profile_molecular_preparation_ready(self) -> bool:
        _validate_report(self)
        return True

    def to_dict(self) -> dict[str, Any]:
        report_bytes = _validate_report(self)
        document = json.loads(report_bytes.decode("ascii"))
        document["report_sha256"] = _sha256_bytes(report_bytes)
        return document


def _validate_report(
    value: MmcifStandardLPeptideNeutralPreparationReport,
) -> bytes:
    if type(value) is not MmcifStandardLPeptideNeutralPreparationReport:
        raise TypeError("an exact preparation report is required")
    try:
        report_bytes = value._report_bytes
        if type(report_bytes) is not bytes:
            raise TypeError("stored report payload must be bytes")
        binding = _report_access_binding(value)
        _validate_anchor(value, binding)
    except MmcifStandardLPeptideNeutralPreparationError:
        raise
    except Exception:
        raise MmcifStandardLPeptideNeutralPreparationError(
            "stale_report_binding", "stored preparation report evidence is stale"
        ) from None
    if value._access_binding_bytes != binding:
        raise MmcifStandardLPeptideNeutralPreparationError(
            "stale_report_binding", "stored preparation report evidence is stale"
        )
    return report_bytes


@dataclass(frozen=True, init=False)
class MmcifStandardLPeptideNeutralPreparationResult:
    """Factory-only atomic result retaining the raw outer-source authority."""

    _state: _PreparedState = field(repr=False)
    _access_binding_bytes: bytes = field(repr=False)

    def __init__(
        self, state: _PreparedState, *, _factory_token: object | None = None
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN or type(state) is not _PreparedState:
            raise TypeError(
                "MmcifStandardLPeptideNeutralPreparationResult is factory-only"
            )
        object.__setattr__(self, "_state", state)
        binding = _result_access_binding(self)
        object.__setattr__(self, "_access_binding_bytes", binding)
        _register_anchor(self, binding)

    @property
    def system(self) -> AllAtomSystem:
        return deserialize_all_atom_system(_validate_result(self).prepared_snapshot)

    @property
    def terminal_leaving_ingest(
        self,
    ) -> MmcifPolymerComponentTerminalLeavingPolicyIngestResult:
        state = _validate_result(self)
        return parse_mmcif_polymer_component_terminal_leaving_policy(
            state.terminal_source, source_id=state.source_id
        )

    @property
    def archive_heavy_ingest(
        self,
    ) -> MmcifArchiveStandardLPeptideTopologyIngestResult:
        state = _validate_result(self)
        return parse_mmcif_archive_standard_l_peptide_topology(
            state.archive_source, source_id=state.source_id
        )

    @property
    def report(self) -> MmcifStandardLPeptideNeutralPreparationReport:
        state = _validate_result(self)
        return MmcifStandardLPeptideNeutralPreparationReport(
            state.report_bytes, _factory_token=_FACTORY_TOKEN
        )

    @property
    def atom_mapping(self) -> tuple[dict[str, Any], ...]:
        state = _validate_result(self)
        document = json.loads(state.mapping_bytes.decode("ascii"))
        return tuple(dict(row) for row in document["rows"])

    @property
    def parameter_requirement_inventory(self) -> dict[str, Any]:
        state = _validate_result(self)
        return json.loads(state.parameter_inventory_bytes.decode("ascii"))

    @property
    def full_source_sha256(self) -> str:
        return _sha256_bytes(_validate_result(self).outer_source)

    @property
    def transformed_topology_sha256(self) -> str:
        return str(self.report.to_dict()["prepared_topology_sha256"])

    @property
    def transformed_system_snapshot_sha256(self) -> str:
        return _sha256_bytes(_validate_result(self).prepared_snapshot)

    @property
    def state_sha256(self) -> str:
        return _sha256_bytes(
            _canonical_json_bytes(_state_document(_validate_result(self)))
        )

    @property
    def source_binding_sha256(self) -> str:
        return _sha256_bytes(_validate_result(self).source_binding_bytes)

    def verify_replay(self) -> bool:
        """Reproject the retained raw source and require byte-exact factory replay."""

        state = _validate_result(self)
        return state == _build_state(state.outer_source, source_id=state.source_id)

    def to_dict(self) -> dict[str, Any]:
        state = _validate_result(self)
        document = self.report.to_dict()
        document.update(
            {
                "state_sha256": _sha256_bytes(
                    _canonical_json_bytes(_state_document(state))
                ),
                "result_source_binding_sha256": _sha256_bytes(
                    state.source_binding_bytes
                ),
            }
        )
        return document


def _validate_result(
    value: MmcifStandardLPeptideNeutralPreparationResult,
) -> _PreparedState:
    if type(value) is not MmcifStandardLPeptideNeutralPreparationResult:
        raise TypeError("an exact preparation result is required")
    try:
        state = value._state
        binding = _result_access_binding(value)
        _validate_anchor(value, binding)
    except MmcifStandardLPeptideNeutralPreparationError:
        raise
    except Exception:
        raise MmcifStandardLPeptideNeutralPreparationError(
            "stale_result_binding", "stored preparation evidence is stale"
        ) from None
    if value._access_binding_bytes != binding:
        raise MmcifStandardLPeptideNeutralPreparationError(
            "stale_result_binding", "stored preparation evidence is stale"
        )
    return state


def prepare_mmcif_standard_l_peptide_neutral_linkage(
    data: bytes,
    *,
    source_id: str = "",
    policy_id: str = MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_POLICY_ID,
) -> MmcifStandardLPeptideNeutralPreparationResult:
    """Prepare the exact profile atomically from one raw eight-category source."""

    if policy_id != MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_POLICY_ID:
        raise MmcifStandardLPeptideNeutralPreparationError(
            "unsupported_policy_id",
            "only the literal v1 preparation policy is accepted",
        )
    return MmcifStandardLPeptideNeutralPreparationResult(
        _build_state(data, source_id=source_id), _factory_token=_FACTORY_TOKEN
    )


def require_mmcif_standard_l_peptide_neutral_preparation(
    data: bytes,
    *,
    source_id: str = "",
    policy_id: str = MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_POLICY_ID,
) -> MmcifStandardLPeptideNeutralPreparationResult:
    """Require the exact profile without promoting generic preparation authority."""

    result = prepare_mmcif_standard_l_peptide_neutral_linkage(
        data, source_id=source_id, policy_id=policy_id
    )
    if result.report.profile_molecular_preparation_ready is not True:
        raise MmcifStandardLPeptideNeutralPreparationError(
            "profile_preparation_not_ready",
            "exact profile preparation was not satisfied",
        )
    return result


__all__ = [
    "MAX_MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_ATOMS",
    "MAX_MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_BONDS",
    "MAX_MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_INPUT_BYTES",
    "MAX_MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_OUTPUT_LINE_CHARS",
    "MAX_MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_SOURCE_ID_BYTES",
    "MAX_MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_TOKEN_CHARS",
    "MAX_MMCIF_STANDARD_L_PEPTIDE_PARAMETER_ANGLES",
    "MAX_MMCIF_STANDARD_L_PEPTIDE_PARAMETER_PROPERS",
    "MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_MAPPING_SCHEMA_ID",
    "MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_MARKER_KEY",
    "MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_PARAMETER_REQUIREMENT_SCHEMA_ID",
    "MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_POLICY_ID",
    "MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_PROFILE_ID",
    "MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_REPORT_SCHEMA_ID",
    "MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_SOURCE_BINDING_SCHEMA_ID",
    "MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_STATE_SCHEMA_ID",
    "MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_TRANSFORMER_NAME",
    "MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_TRANSFORMER_VERSION",
    "MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_VERSION",
    "MmcifStandardLPeptideNeutralPreparationError",
    "MmcifStandardLPeptideNeutralPreparationReport",
    "MmcifStandardLPeptideNeutralPreparationResult",
    "prepare_mmcif_standard_l_peptide_neutral_linkage",
    "require_mmcif_standard_l_peptide_neutral_preparation",
]
