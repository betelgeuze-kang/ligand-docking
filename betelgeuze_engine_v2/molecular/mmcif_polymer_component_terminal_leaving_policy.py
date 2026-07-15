"""Strict metadata-only polymer terminal/leaving annotation envelope.

The envelope adds four exact source annotations to the existing seven-field
``_chem_comp_atom`` surface: leaving-atom, backbone-atom, N-terminal-group,
and C-terminal-group flags.  It strips those four fields and requires the
unchanged :mod:`mmcif_polymer_component_topology` child to accept the exact
remaining seven-field projection independently.

The child owns the returned :class:`AllAtomSystem`.  Wrapper annotations and
sequence-boundary positions live only in factory-created evidence artifacts;
extracting or serializing the bare child system intentionally loses them.
Sequence boundaries are ordering facts, not chemical termini.  No atom is
removed, no bond is inferred, and no preparation or runtime authority is
promoted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from typing import Any, Mapping
import weakref

from .mmcif_polymer_component_topology import (
    MAX_MMCIF_POLYMER_COMPONENT_ATOM_ROWS,
    MAX_MMCIF_POLYMER_COMPONENT_BOND_ROWS,
    MAX_MMCIF_POLYMER_COMPONENT_MATERIALIZED_BONDS,
    MAX_MMCIF_POLYMER_COMPONENT_ROWS,
    MAX_MMCIF_POLYMER_COMPONENT_SEQUENCE_ROWS,
    MAX_MMCIF_POLYMER_COMPONENT_TOPOLOGY_INPUT_BYTES,
    MAX_MMCIF_POLYMER_COMPONENT_TOPOLOGY_OUTPUT_BYTES,
    MAX_MMCIF_POLYMER_COMPONENT_TOPOLOGY_OUTPUT_LINE_CHARS,
    MAX_MMCIF_POLYMER_COMPONENT_TOPOLOGY_PROJECTION_BYTES,
    MAX_MMCIF_POLYMER_COMPONENT_TOPOLOGY_SOURCE_ID_BYTES,
    MAX_MMCIF_POLYMER_COMPONENT_TOPOLOGY_TOKEN_CHARS,
    MMCIF_POLYMER_COMPONENT_TOPOLOGY_CHEM_COMP_ATOM_HEADERS,
    MMCIF_POLYMER_COMPONENT_TOPOLOGY_CHEM_COMP_BOND_HEADERS,
    MMCIF_POLYMER_COMPONENT_TOPOLOGY_CHEM_COMP_HEADERS,
    MMCIF_POLYMER_COMPONENT_TOPOLOGY_PARSER_PEDIGREE_ID,
    MMCIF_POLYMER_COMPONENT_TOPOLOGY_PROFILE_ID,
    MmcifPolymerComponentTopologyError,
    MmcifPolymerComponentTopologyIngestResult,
    parse_mmcif_polymer_component_topology,
    write_mmcif_polymer_component_topology,
)
from .mmcif_polymer_sequence import MMCIF_ENTITY_POLY_SEQ_HEADERS
from .mmcif_syntax import CifBlock, CifLoop, CifSyntaxError, CifToken, parse_cif_block
from .models import AllAtomSystem
from .observation import MMCIF_POLYMER_COMPONENT_TOPOLOGY_ATOM_SITE_HEADERS
from .serialization import serialize_all_atom_system


MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_ENVELOPE_VERSION = "1.0.0"
MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_PARSER_VERSION = "1.0.0"
MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_WRITER_VERSION = "1.0.0"
MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_PARSER_NAME = (
    "betelgeuze_engine_v2.molecular."
    "mmcif_polymer_component_terminal_leaving_policy."
    "parse_mmcif_polymer_component_terminal_leaving_policy"
)
MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_PROFILE_ID = (
    "strict_mmcif_polymer_component_terminal_leaving_annotation_envelope/1.0.0"
)
MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_PROJECTION_SCHEMA_ID = (
    "betelgeuze.mmcif_polymer_component_terminal_leaving_annotation_projection/1.0.0"
)
MMCIF_POLYMER_TERMINAL_LEAVING_RULES_SCHEMA_ID = (
    "betelgeuze.mmcif_polymer_terminal_leaving_rules/1.0.0"
)
MMCIF_POLYMER_TERMINAL_LEAVING_POLICY_SCHEMA_ID = (
    "betelgeuze.mmcif_polymer_terminal_leaving_policy/1.0.0"
)
MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_STATE_SCHEMA_ID = (
    "betelgeuze.mmcif_polymer_component_terminal_leaving_policy_state/1.0.0"
)
MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_SOURCE_BINDING_SCHEMA_ID = (
    "betelgeuze.mmcif_polymer_component_terminal_leaving_policy_source_binding/1.0.0"
)
_CHILD_STAGE_PROOF_SCHEMA_ID = (
    "betelgeuze.mmcif_polymer_component_terminal_leaving_policy_child_stage_proof/1.0.0"
)
MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_WRITE_RECEIPT_SCHEMA_ID = (
    "betelgeuze.mmcif_polymer_component_terminal_leaving_policy_write_receipt/1.0.0"
)
MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_ROUND_TRIP_REPORT_SCHEMA_ID = (
    "betelgeuze.mmcif_polymer_component_terminal_leaving_policy_round_trip_report/1.0.0"
)
MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_SCOPE = (
    "source_reported_l_peptide_terminal_leaving_annotation_inventory_only"
)

MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_INPUT_BYTES = (
    MAX_MMCIF_POLYMER_COMPONENT_TOPOLOGY_INPUT_BYTES
)
MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_OUTPUT_BYTES = (
    MAX_MMCIF_POLYMER_COMPONENT_TOPOLOGY_OUTPUT_BYTES
)
MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_PROJECTION_BYTES = (
    MAX_MMCIF_POLYMER_COMPONENT_TOPOLOGY_PROJECTION_BYTES
)
MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_SOURCE_ID_BYTES = (
    MAX_MMCIF_POLYMER_COMPONENT_TOPOLOGY_SOURCE_ID_BYTES
)
MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_TOKEN_CHARS = (
    MAX_MMCIF_POLYMER_COMPONENT_TOPOLOGY_TOKEN_CHARS
)
MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_OUTPUT_LINE_CHARS = (
    MAX_MMCIF_POLYMER_COMPONENT_TOPOLOGY_OUTPUT_LINE_CHARS
)
MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_SEQUENCE_ROWS = (
    MAX_MMCIF_POLYMER_COMPONENT_SEQUENCE_ROWS
)
MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_COMPONENT_ROWS = (
    MAX_MMCIF_POLYMER_COMPONENT_ROWS
)
MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_COMPONENT_ATOM_ROWS = (
    MAX_MMCIF_POLYMER_COMPONENT_ATOM_ROWS
)
MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_COMPONENT_BOND_ROWS = (
    MAX_MMCIF_POLYMER_COMPONENT_BOND_ROWS
)
MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_CHILD_MATERIALIZED_BONDS = (
    MAX_MMCIF_POLYMER_COMPONENT_MATERIALIZED_BONDS
)

MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_CHEM_COMP_ATOM_HEADERS = (
    "_chem_comp_atom.comp_id",
    "_chem_comp_atom.atom_id",
    "_chem_comp_atom.type_symbol",
    "_chem_comp_atom.charge",
    "_chem_comp_atom.pdbx_aromatic_flag",
    "_chem_comp_atom.pdbx_leaving_atom_flag",
    "_chem_comp_atom.pdbx_stereo_config",
    "_chem_comp_atom.pdbx_backbone_atom_flag",
    "_chem_comp_atom.pdbx_n_terminal_atom_flag",
    "_chem_comp_atom.pdbx_c_terminal_atom_flag",
    "_chem_comp_atom.pdbx_ordinal",
)

_ENTITY_HEADERS = ("_entity.id", "_entity.type")
_STRUCT_ASYM_HEADERS = ("_struct_asym.id", "_struct_asym.entity_id")
_CATEGORY_ORDER = (
    "_entity",
    "_struct_asym",
    "_entity_poly_seq",
    "_chem_comp",
    "_chem_comp_atom",
    "_chem_comp_bond",
    "_atom_site",
)
_EXPECTED_CATEGORIES = frozenset(_CATEGORY_ORDER)
_HEADERS_BY_CATEGORY = {
    "_entity": _ENTITY_HEADERS,
    "_struct_asym": _STRUCT_ASYM_HEADERS,
    "_entity_poly_seq": MMCIF_ENTITY_POLY_SEQ_HEADERS,
    "_chem_comp": MMCIF_POLYMER_COMPONENT_TOPOLOGY_CHEM_COMP_HEADERS,
    "_chem_comp_atom": (
        MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_CHEM_COMP_ATOM_HEADERS
    ),
    "_chem_comp_bond": MMCIF_POLYMER_COMPONENT_TOPOLOGY_CHEM_COMP_BOND_HEADERS,
    "_atom_site": MMCIF_POLYMER_COMPONENT_TOPOLOGY_ATOM_SITE_HEADERS,
}
_CHILD_ATOM_FIELD_INDICES = (0, 1, 2, 3, 4, 6, 10)
_FLAG_FIELDS = (
    (5, "invalid_leaving_atom_flag", "leaving_atom"),
    (7, "invalid_backbone_atom_flag", "backbone_atom"),
    (8, "invalid_n_terminal_atom_flag", "n_terminal_atom"),
    (9, "invalid_c_terminal_atom_flag", "c_terminal_atom"),
)
_BOUNDARY_ROLES = frozenset(
    {"singleton", "n_sequence_boundary", "internal", "c_sequence_boundary"}
)
_MAX_CHILD_STAGE_PROOF_BYTES = 64 * 1024
_CHILD_STAGE_GATE_FIELDS = (
    "child_stage_local_validation_required",
    "child_stage_local_validation_passed",
    "child_stage_local_parser_pedigree_equal",
    "child_stage_local_component_projection_equal",
    "child_stage_local_topology_state_equal",
    "child_stage_local_augmented_topology_equal",
    "child_stage_local_source_binding_equal",
    "child_stage_local_system_byte_exact",
    "child_stage_local_snapshot_equal",
    "child_stage_local_parser_observation_equal",
    "child_stage_local_preparation_commitment_equal",
    "child_stage_local_canonical_emission_byte_exact",
)
_FACTORY_TOKEN = object()
_ARTIFACT_ANCHORS: dict[int, tuple[weakref.ReferenceType[Any], bytes]] = {}

_FALSE_AUTHORITY_FIELDS = (
    "source_authenticated",
    "new_system_parser_pedigree_introduced",
    "atom_names_used_to_infer_links",
    "auth_identity_used_for_policy",
    "coordinate_geometry_used",
    "geometry_or_distance_used",
    "role_assignment_interpreted",
    "chemical_terminal_state_assessed",
    "terminal_chemistry_assigned",
    "leaving_atom_policy_applied",
    "leaving_atoms_removed",
    "peptide_bonds_inferred",
    "inter_residue_bonds_interpreted",
    "inter_residue_bonds_materialized",
    "cross_component_bonds_interpreted",
    "independent_chemistry_established",
    "chemistry_inferred",
    "chemistry_interpreted",
    "generic_chemistry_supported",
    "preparation_ready",
    "generic_preparation_ready",
    "generic_molecular_preparation_ready",
    "global_preparation_ready",
    "global_molecular_preparation_ready",
    "parameterability_assessed",
    "parameterizable",
    "physics_supported",
    "runtime_eligible",
    "simulation_ready",
    "execution_authorized",
    "claim_safe",
    "general_mmcif_round_trip_evidence_ready",
    "all_format_round_trip_evidence_ready",
    "v2_1_complete",
)


def _authority_false_document() -> dict[str, bool]:
    return {name: False for name in _FALSE_AUTHORITY_FIELDS}


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


_RULES_BYTES = _canonical_json_bytes(
    {
        "schema_id": MMCIF_POLYMER_TERMINAL_LEAVING_RULES_SCHEMA_ID,
        "profile_id": MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_PROFILE_ID,
        "policy_schema_id": MMCIF_POLYMER_TERMINAL_LEAVING_POLICY_SCHEMA_ID,
        "scope": MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_SCOPE,
        "category_order": list(_CATEGORY_ORDER),
        "chem_comp_atom_headers": list(
            MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_CHEM_COMP_ATOM_HEADERS
        ),
        "child_chem_comp_atom_headers": list(
            MMCIF_POLYMER_COMPONENT_TOPOLOGY_CHEM_COMP_ATOM_HEADERS
        ),
        "child_field_indices_zero_based": list(_CHILD_ATOM_FIELD_INDICES),
        "annotation_flags": [name for _, _, name in _FLAG_FIELDS],
        "annotation_values": ["N", "Y"],
        "hard_caps": {
            "component_atom_rows": (
                MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_COMPONENT_ATOM_ROWS
            ),
            "component_bond_rows": (
                MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_COMPONENT_BOND_ROWS
            ),
            "component_rows": (
                MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_COMPONENT_ROWS
            ),
            "input_bytes": (
                MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_INPUT_BYTES
            ),
            "output_bytes": (
                MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_OUTPUT_BYTES
            ),
            "output_line_characters": (
                MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_OUTPUT_LINE_CHARS
            ),
            "projection_bytes": (
                MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_PROJECTION_BYTES
            ),
            "sequence_rows": (
                MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_SEQUENCE_ROWS
            ),
            "source_id_utf8_bytes": (
                MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_SOURCE_ID_BYTES
            ),
            "token_characters": (
                MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_TOKEN_CHARS
            ),
        },
        "sequence_boundary_roles": sorted(_BOUNDARY_ROLES),
        "sequence_boundary_semantics": (
            "ordered_entity_poly_seq_position_per_asym_not_chemical_terminus"
        ),
        "bare_system_semantics": (
            "wrapper_annotation_evidence_intentionally_lost_on_bare_system_"
            "serialization"
        ),
        "application_policy": (
            "preserve_only_no_atom_removal_no_bond_inference_no_geometry_use"
        ),
        **_authority_false_document(),
    }
)
MMCIF_POLYMER_TERMINAL_LEAVING_RULES_SHA256 = _sha256_bytes(_RULES_BYTES)


def mmcif_polymer_terminal_leaving_rules_bytes() -> bytes:
    """Return immutable canonical rules for the metadata-only envelope."""

    return _RULES_BYTES


class MmcifPolymerComponentTerminalLeavingPolicyError(ValueError):
    """Stable privacy-safe error for the exact annotation envelope."""

    def __init__(
        self, code: str, message: str, *, line_number: int | None = None
    ) -> None:
        self.code = str(code)
        self.detail = str(message)
        self.line_number = None if line_number is None else int(line_number)
        suffix = "" if self.line_number is None else f" at line {self.line_number}"
        super().__init__(
            "mmcif_polymer_component_terminal_leaving_policy:"
            f"{self.code}{suffix}: {self.detail}"
        )


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
        raise MmcifPolymerComponentTerminalLeavingPolicyError(
            "stale_artifact_binding", "factory artifact binding is stale"
        )


def _source_id_sha256(source_id: str) -> str:
    if type(source_id) is not str:
        raise TypeError("source_id must be a string")
    try:
        encoded = source_id.encode("utf-8")
    except UnicodeError:
        raise MmcifPolymerComponentTerminalLeavingPolicyError(
            "invalid_source_id", "source identifier must contain Unicode scalar values"
        ) from None
    if len(encoded) > (
        MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_SOURCE_ID_BYTES
    ):
        raise MmcifPolymerComponentTerminalLeavingPolicyError(
            "source_id_too_large", "source identifier exceeds the byte limit"
        )
    return _sha256_bytes(encoded)


def _parse_block(data: bytes) -> CifBlock:
    if type(data) is not bytes:
        raise TypeError("mmCIF terminal/leaving policy input must be bytes")
    if not data:
        raise MmcifPolymerComponentTerminalLeavingPolicyError(
            "empty_input", "input is empty"
        )
    if len(data) > MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_INPUT_BYTES:
        raise MmcifPolymerComponentTerminalLeavingPolicyError(
            "input_too_large", "input exceeds the envelope byte limit"
        )
    try:
        text = data.decode("ascii")
    except UnicodeDecodeError:
        raise MmcifPolymerComponentTerminalLeavingPolicyError(
            "non_ascii_input", "input must use CIF 1.1 ASCII"
        ) from None
    if any(
        len(line)
        > MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_OUTPUT_LINE_CHARS
        for line in text.splitlines()
    ):
        raise MmcifPolymerComponentTerminalLeavingPolicyError(
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
        raise MmcifPolymerComponentTerminalLeavingPolicyError(
            code,
            "input is outside the exact single-block CIF envelope grammar",
            line_number=exc.line_number,
        ) from None


def _loop_for(block: CifBlock, category: str) -> CifLoop:
    scalar = [name for name in block.scalar_values if name.split(".", 1)[0] == category]
    loops = [loop for loop in block.loops if category in loop.categories]
    if scalar or len(loops) != 1 or loops[0].categories != (category,):
        raise MmcifPolymerComponentTerminalLeavingPolicyError(
            "unsupported_category_representation",
            "each selected category must occur in one category-local loop",
        )
    return loops[0]


def _validate_surface(block: CifBlock) -> dict[str, CifLoop]:
    if (
        len(block.name)
        > MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_TOKEN_CHARS
        or len("data_") + len(block.name)
        > MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_OUTPUT_LINE_CHARS
    ):
        raise MmcifPolymerComponentTerminalLeavingPolicyError(
            "block_name_too_long", "data-block name exceeds the profile limit"
        )
    if set(block.categories) != _EXPECTED_CATEGORIES:
        raise MmcifPolymerComponentTerminalLeavingPolicyError(
            "unsupported_category_surface",
            "input categories must exactly match the seven-category envelope",
        )
    loops = {category: _loop_for(block, category) for category in _CATEGORY_ORDER}
    for category, loop in loops.items():
        if loop.tags != _HEADERS_BY_CATEGORY[category]:
            raise MmcifPolymerComponentTerminalLeavingPolicyError(
                "unsupported_category_headers",
                "selected category headers are outside the exact envelope profile",
                line_number=loop.line_number,
            )
        for row in loop.rows:
            for token in row:
                if len(token.value) > (
                    MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_TOKEN_CHARS
                ):
                    raise MmcifPolymerComponentTerminalLeavingPolicyError(
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
    }
    for category, (limit, code) in limits.items():
        if len(loops[category].rows) > limit:
            raise MmcifPolymerComponentTerminalLeavingPolicyError(
                code, "selected category row count exceeds the profile limit"
            )
    return loops


def _token_text(token: CifToken) -> str:
    if token.multiline:
        raise MmcifPolymerComponentTerminalLeavingPolicyError(
            "unsupported_multiline_token", "multiline tokens are outside the profile"
        )
    if not token.quoted:
        rendered = token.value
    elif "'" not in token.value:
        rendered = f"'{token.value}'"
    elif '"' not in token.value:
        rendered = f'"{token.value}"'
    else:
        raise MmcifPolymerComponentTerminalLeavingPolicyError(
            "unsupported_quoted_token", "quoted token cannot be emitted canonically"
        )
    if len(rendered) > (
        MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_OUTPUT_LINE_CHARS
    ):
        raise MmcifPolymerComponentTerminalLeavingPolicyError(
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
            <= MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_OUTPUT_LINE_CHARS
            else row
        )
    lines.append("#")
    return ("\n".join(lines) + "\n").encode("ascii")


def _emit_loop(loop: CifLoop) -> bytes:
    return _emit_rows(
        loop.tags,
        tuple(tuple(_token_text(token) for token in row) for row in loop.rows),
    )


def _emit_source(
    block_name: str,
    loops: Mapping[str, CifLoop],
    *,
    child_atom_projection: bool,
) -> bytes:
    pieces = [f"data_{block_name}\n#\n".encode("ascii")]
    for category in _CATEGORY_ORDER:
        loop = loops[category]
        if category == "_chem_comp_atom" and child_atom_projection:
            rows = tuple(
                tuple(_token_text(row[index]) for index in _CHILD_ATOM_FIELD_INDICES)
                for row in loop.rows
            )
            pieces.append(
                _emit_rows(
                    MMCIF_POLYMER_COMPONENT_TOPOLOGY_CHEM_COMP_ATOM_HEADERS, rows
                )
            )
        else:
            pieces.append(_emit_loop(loop))
    return b"".join(pieces)


@dataclass(frozen=True)
class _AnnotationState:
    comp_id: str
    atom_id: str
    template_ordinal: int
    leaving_atom: bool
    backbone_atom: bool
    n_terminal_atom: bool
    c_terminal_atom: bool


@dataclass(frozen=True)
class _BoundaryState:
    asym_id: str
    entity_id: str
    sequence_number: int
    component_id: str
    position_role: str
    at_n_sequence_boundary: bool
    at_c_sequence_boundary: bool


def _flag_value(token: CifToken, *, code: str) -> bool:
    if token.quoted or token.multiline or token.value not in {"N", "Y"}:
        raise MmcifPolymerComponentTerminalLeavingPolicyError(
            code,
            "terminal/leaving annotations must be mandatory bare uppercase Y or N",
            line_number=token.line_number,
        )
    return token.value == "Y"


def _annotation_states(
    loop: CifLoop, child: MmcifPolymerComponentTopologyIngestResult
) -> tuple[_AnnotationState, ...]:
    observed: dict[tuple[str, str, int], _AnnotationState] = {}
    for row in loop.rows:
        try:
            ordinal = int(row[10].value, 10)
        except (ValueError, OverflowError):
            raise MmcifPolymerComponentTerminalLeavingPolicyError(
                "invalid_component_atom_ordinal",
                "component atom ordinal must be an exact integer",
                line_number=row[10].line_number,
            ) from None
        values = {
            name: _flag_value(row[index], code=code)
            for index, code, name in _FLAG_FIELDS
        }
        state = _AnnotationState(
            comp_id=row[0].value,
            atom_id=row[1].value,
            template_ordinal=ordinal,
            **values,
        )
        key = (state.comp_id, state.atom_id, state.template_ordinal)
        if key in observed:
            raise MmcifPolymerComponentTerminalLeavingPolicyError(
                "duplicate_annotation_atom_key",
                "annotation rows must have unique component/atom/ordinal identity",
            )
        observed[key] = state

    child_rows = child.component_atom_rows
    child_keys = tuple((row.comp_id, row.atom_id, row.ordinal) for row in child_rows)
    if set(observed) != set(child_keys) or len(observed) != len(child_keys):
        raise MmcifPolymerComponentTerminalLeavingPolicyError(
            "annotation_child_join_mismatch",
            "annotation rows must join the exact independently accepted child atoms",
        )
    return tuple(observed[key] for key in child_keys)


def _boundary_states(
    loops: Mapping[str, CifLoop], child: MmcifPolymerComponentTopologyIngestResult
) -> tuple[_BoundaryState, ...]:
    sequence_by_entity: dict[str, list[tuple[int, str]]] = {}
    for row in child.carrier_ingest.sequence_rows:
        sequence_by_entity.setdefault(row.entity_id, []).append((row.num, row.mon_id))
    for values in sequence_by_entity.values():
        values.sort()

    boundaries: list[_BoundaryState] = []
    for row in loops["_struct_asym"].rows:
        asym_id = row[0].value
        entity_id = row[1].value
        sequence = sequence_by_entity.get(entity_id)
        if not sequence:
            raise MmcifPolymerComponentTerminalLeavingPolicyError(
                "sequence_boundary_join_mismatch",
                "every asym must join one independently accepted polymer sequence",
            )
        first = sequence[0][0]
        last = sequence[-1][0]
        for number, component_id in sequence:
            at_n = number == first
            at_c = number == last
            if at_n and at_c:
                role = "singleton"
            elif at_n:
                role = "n_sequence_boundary"
            elif at_c:
                role = "c_sequence_boundary"
            else:
                role = "internal"
            boundaries.append(
                _BoundaryState(
                    asym_id=asym_id,
                    entity_id=entity_id,
                    sequence_number=number,
                    component_id=component_id,
                    position_role=role,
                    at_n_sequence_boundary=at_n,
                    at_c_sequence_boundary=at_c,
                )
            )
    return tuple(boundaries)


def _annotation_document(row: _AnnotationState) -> dict[str, Any]:
    return {
        "comp_id": row.comp_id,
        "atom_id": row.atom_id,
        "template_ordinal": row.template_ordinal,
        "leaving_atom": row.leaving_atom,
        "backbone_atom": row.backbone_atom,
        "n_terminal_atom": row.n_terminal_atom,
        "c_terminal_atom": row.c_terminal_atom,
    }


def _boundary_document(row: _BoundaryState) -> dict[str, Any]:
    return {
        "asym_id": row.asym_id,
        "entity_id": row.entity_id,
        "sequence_number": row.sequence_number,
        "component_id": row.component_id,
        "position_role": row.position_role,
        "at_n_sequence_boundary": row.at_n_sequence_boundary,
        "at_c_sequence_boundary": row.at_c_sequence_boundary,
    }


def _canonical_output(
    child_payload: bytes, annotations: tuple[_AnnotationState, ...]
) -> bytes:
    try:
        block = parse_cif_block(child_payload.decode("ascii"))
    except (UnicodeDecodeError, CifSyntaxError):
        raise MmcifPolymerComponentTerminalLeavingPolicyError(
            "child_emission_invalid", "unchanged child emitted invalid CIF"
        ) from None
    loops = {category: _loop_for(block, category) for category in _CATEGORY_ORDER}
    by_key = {
        (row.comp_id, row.atom_id, row.template_ordinal): row for row in annotations
    }
    atom_rows: list[tuple[str, ...]] = []
    consumed: set[tuple[str, str, int]] = set()
    for child_row in loops["_chem_comp_atom"].rows:
        try:
            key = (child_row[0].value, child_row[1].value, int(child_row[6].value, 10))
        except (ValueError, OverflowError):
            raise MmcifPolymerComponentTerminalLeavingPolicyError(
                "child_emission_invalid", "child atom ordinal is invalid"
            ) from None
        annotation = by_key.get(key)
        if annotation is None or key in consumed:
            raise MmcifPolymerComponentTerminalLeavingPolicyError(
                "canonical_annotation_join_mismatch",
                "canonical child rows do not join the bound annotations",
            )
        consumed.add(key)
        atom_rows.append(
            (
                _token_text(child_row[0]),
                _token_text(child_row[1]),
                _token_text(child_row[2]),
                _token_text(child_row[3]),
                _token_text(child_row[4]),
                "Y" if annotation.leaving_atom else "N",
                _token_text(child_row[5]),
                "Y" if annotation.backbone_atom else "N",
                "Y" if annotation.n_terminal_atom else "N",
                "Y" if annotation.c_terminal_atom else "N",
                _token_text(child_row[6]),
            )
        )
    if consumed != set(by_key):
        raise MmcifPolymerComponentTerminalLeavingPolicyError(
            "canonical_annotation_join_mismatch",
            "canonical child rows do not exhaust the bound annotations",
        )
    pieces = [f"data_{block.name}\n#\n".encode("ascii")]
    for category in _CATEGORY_ORDER:
        if category == "_chem_comp_atom":
            pieces.append(
                _emit_rows(
                    MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_CHEM_COMP_ATOM_HEADERS,
                    tuple(atom_rows),
                )
            )
        else:
            pieces.append(_emit_loop(loops[category]))
    payload = b"".join(pieces)
    if len(payload) > MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_OUTPUT_BYTES:
        raise MmcifPolymerComponentTerminalLeavingPolicyError(
            "output_too_large", "canonical output exceeds the envelope byte limit"
        )
    _validate_surface(_parse_block(payload))
    return payload


def _child_stage_proof_bytes(
    child: MmcifPolymerComponentTopologyIngestResult,
    independent_child: MmcifPolymerComponentTopologyIngestResult,
    *,
    child_source: bytes,
    child_payload: bytes,
    independent_child_payload: bytes,
) -> bytes:
    """Compute and fail closed over a second exact child parse."""

    child_document = child.to_dict()
    independent_document = independent_child.to_dict()
    child_system = child.system
    independent_system = independent_child.system
    child_marker = child_system.provenance.metadata.get(
        "mmcif_polymer_component_topology", {}
    )
    independent_marker = independent_system.provenance.metadata.get(
        "mmcif_polymer_component_topology", {}
    )
    child_system_bytes = serialize_all_atom_system(child_system)
    independent_system_bytes = serialize_all_atom_system(independent_system)
    proof: dict[str, Any] = {
        "schema_id": (_CHILD_STAGE_PROOF_SCHEMA_ID),
        "child_source_sha256": _sha256_bytes(child_source),
        "primary_child_source_binding_sha256": child.source_binding_sha256,
        "independent_child_source_binding_sha256": (
            independent_child.source_binding_sha256
        ),
        "primary_child_component_projection_sha256": (
            child.component_projection_sha256
        ),
        "independent_child_component_projection_sha256": (
            independent_child.component_projection_sha256
        ),
        "primary_child_topology_state_sha256": child.topology_state_sha256,
        "independent_child_topology_state_sha256": (
            independent_child.topology_state_sha256
        ),
        "primary_child_augmented_topology_sha256": child.augmented_topology_sha256,
        "independent_child_augmented_topology_sha256": (
            independent_child.augmented_topology_sha256
        ),
        "primary_child_system_sha256": _sha256_bytes(child_system_bytes),
        "independent_child_system_sha256": _sha256_bytes(independent_system_bytes),
        "primary_child_snapshot_sha256": child.augmented_system_snapshot_sha256,
        "independent_child_snapshot_sha256": (
            independent_child.augmented_system_snapshot_sha256
        ),
        "primary_child_parser_observation_sha256": child_document.get(
            "augmented_system_parser_observation_sha256"
        ),
        "independent_child_parser_observation_sha256": independent_document.get(
            "augmented_system_parser_observation_sha256"
        ),
        "primary_child_preparation_commitment_schema_id": child_marker.get(
            "preparation_inventory_commitment_schema_id"
        ),
        "independent_child_preparation_commitment_schema_id": (
            independent_marker.get("preparation_inventory_commitment_schema_id")
        ),
        "primary_child_preparation_commitment_sha256": child_marker.get(
            "preparation_inventory_commitment_sha256"
        ),
        "independent_child_preparation_commitment_sha256": independent_marker.get(
            "preparation_inventory_commitment_sha256"
        ),
        "primary_child_canonical_output_sha256": _sha256_bytes(child_payload),
        "independent_child_canonical_output_sha256": _sha256_bytes(
            independent_child_payload
        ),
        "parser_pedigree_equal": (
            child_document.get("parser_pedigree_id")
            == independent_document.get("parser_pedigree_id")
            == MMCIF_POLYMER_COMPONENT_TOPOLOGY_PARSER_PEDIGREE_ID
        ),
        "component_projection_equal": (
            child.component_projection_sha256
            == independent_child.component_projection_sha256
        ),
        "topology_state_equal": (
            child.topology_state_sha256 == independent_child.topology_state_sha256
        ),
        "augmented_topology_equal": (
            child.augmented_topology_sha256
            == independent_child.augmented_topology_sha256
        ),
        "source_binding_equal": (
            child.source_binding_sha256 == independent_child.source_binding_sha256
        ),
        "system_byte_exact": child_system_bytes == independent_system_bytes,
        "snapshot_equal": (
            child.augmented_system_snapshot_sha256
            == independent_child.augmented_system_snapshot_sha256
        ),
        "parser_observation_equal": (
            type(child_document.get("augmented_system_parser_observation_sha256"))
            is str
            and child_document.get("augmented_system_parser_observation_sha256")
            == independent_document.get("augmented_system_parser_observation_sha256")
        ),
        "preparation_commitment_equal": (
            type(child_marker.get("preparation_inventory_commitment_schema_id")) is str
            and type(child_marker.get("preparation_inventory_commitment_sha256")) is str
            and child_marker.get("preparation_inventory_commitment_schema_id")
            == independent_marker.get("preparation_inventory_commitment_schema_id")
            and child_marker.get("preparation_inventory_commitment_sha256")
            == independent_marker.get("preparation_inventory_commitment_sha256")
        ),
        "canonical_emission_byte_exact": child_payload == independent_child_payload,
    }
    comparison_fields = (
        "parser_pedigree_equal",
        "component_projection_equal",
        "topology_state_equal",
        "augmented_topology_equal",
        "source_binding_equal",
        "system_byte_exact",
        "snapshot_equal",
        "parser_observation_equal",
        "preparation_commitment_equal",
        "canonical_emission_byte_exact",
    )
    proof["validated"] = all(proof[name] is True for name in comparison_fields)
    proof_bytes = _canonical_json_bytes(proof)
    if proof["validated"] is not True:
        raise MmcifPolymerComponentTerminalLeavingPolicyError(
            "stage_local_child_mismatch",
            "independent seven-field child evidence did not match byte-exactly",
        )
    if len(proof_bytes) > _MAX_CHILD_STAGE_PROOF_BYTES:
        raise MmcifPolymerComponentTerminalLeavingPolicyError(
            "child_proof_too_large", "stage-local child proof exceeds the byte limit"
        )
    return proof_bytes


@dataclass(frozen=True)
class _ParsedState:
    full_source: bytes
    source_id: str
    block_name: str
    child_source: bytes
    canonical_output: bytes
    annotations: tuple[_AnnotationState, ...]
    boundaries: tuple[_BoundaryState, ...]
    child_stage_proof_bytes: bytes
    projection_bytes: bytes
    state_bytes: bytes
    source_binding_bytes: bytes


def _build_state(data: bytes, *, source_id: str) -> _ParsedState:
    source_id_sha = _source_id_sha256(source_id)
    block = _parse_block(data)
    loops = _validate_surface(block)
    child_source = _emit_source(block.name, loops, child_atom_projection=True)
    try:
        child = parse_mmcif_polymer_component_topology(
            child_source, source_id=source_id
        )
    except MmcifPolymerComponentTopologyError as exc:
        raise MmcifPolymerComponentTerminalLeavingPolicyError(
            "child_rejected",
            f"the unchanged exact seven-field child rejected its projection ({exc.code})",
        ) from None
    annotations = _annotation_states(loops["_chem_comp_atom"], child)
    boundaries = _boundary_states(loops, child)
    child_write = write_mmcif_polymer_component_topology(child)
    try:
        independent_child = parse_mmcif_polymer_component_topology(
            child_source, source_id=source_id
        )
        independent_child_write = write_mmcif_polymer_component_topology(
            independent_child
        )
    except MmcifPolymerComponentTopologyError as exc:
        raise MmcifPolymerComponentTerminalLeavingPolicyError(
            "independent_child_rejected",
            f"the independent exact seven-field child replay failed ({exc.code})",
        ) from None
    child_stage_proof_bytes = _child_stage_proof_bytes(
        child,
        independent_child,
        child_source=child_source,
        child_payload=child_write.payload,
        independent_child_payload=independent_child_write.payload,
    )
    child_stage_proof = json.loads(child_stage_proof_bytes.decode("ascii"))
    canonical_output = _canonical_output(child_write.payload, annotations)
    projection_document = {
        "schema_id": (
            MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_PROJECTION_SCHEMA_ID
        ),
        "profile_id": MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_PROFILE_ID,
        "policy_schema_id": MMCIF_POLYMER_TERMINAL_LEAVING_POLICY_SCHEMA_ID,
        "rules_schema_id": MMCIF_POLYMER_TERMINAL_LEAVING_RULES_SCHEMA_ID,
        "rules_sha256": MMCIF_POLYMER_TERMINAL_LEAVING_RULES_SHA256,
        "scope": MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_SCOPE,
        "child_profile_id": MMCIF_POLYMER_COMPONENT_TOPOLOGY_PROFILE_ID,
        "child_parser_pedigree_id": (
            MMCIF_POLYMER_COMPONENT_TOPOLOGY_PARSER_PEDIGREE_ID
        ),
        "child_component_projection_sha256": child.component_projection_sha256,
        "component_atom_annotations": [
            _annotation_document(row) for row in annotations
        ],
        "sequence_boundaries": [_boundary_document(row) for row in boundaries],
        "sequence_boundary_semantics": (
            "ordered_entity_poly_seq_position_per_asym_not_chemical_terminus"
        ),
        "materialized_inter_residue_bond_count": 0,
        "bare_system_retains_wrapper_evidence": False,
        **_authority_false_document(),
    }
    projection_bytes = _canonical_json_bytes(projection_document)
    if len(projection_bytes) > (
        MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_PROJECTION_BYTES
    ):
        raise MmcifPolymerComponentTerminalLeavingPolicyError(
            "projection_too_large", "annotation projection exceeds the byte limit"
        )
    state_document = {
        "schema_id": MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_STATE_SCHEMA_ID,
        "envelope_version": (
            MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_ENVELOPE_VERSION
        ),
        "parser_version": (
            MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_PARSER_VERSION
        ),
        "writer_version": (
            MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_WRITER_VERSION
        ),
        "profile_id": MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_PROFILE_ID,
        "projection_sha256": _sha256_bytes(projection_bytes),
        "child_profile_id": MMCIF_POLYMER_COMPONENT_TOPOLOGY_PROFILE_ID,
        "child_parser_pedigree_id": (
            MMCIF_POLYMER_COMPONENT_TOPOLOGY_PARSER_PEDIGREE_ID
        ),
        "child_component_projection_sha256": child.component_projection_sha256,
        "child_topology_state_sha256": child.topology_state_sha256,
        "child_augmented_topology_sha256": child.augmented_topology_sha256,
        "child_parser_observation_digest_binding_location": "source_binding",
        "child_stage_local_validation_required": True,
        "child_stage_local_validation_passed": child_stage_proof["validated"],
        "child_stage_local_parser_pedigree_equal": child_stage_proof[
            "parser_pedigree_equal"
        ],
        "child_stage_local_component_projection_equal": child_stage_proof[
            "component_projection_equal"
        ],
        "child_stage_local_topology_state_equal": child_stage_proof[
            "topology_state_equal"
        ],
        "child_stage_local_augmented_topology_equal": child_stage_proof[
            "augmented_topology_equal"
        ],
        "child_stage_local_source_binding_equal": child_stage_proof[
            "source_binding_equal"
        ],
        "child_stage_local_system_byte_exact": child_stage_proof["system_byte_exact"],
        "child_stage_local_snapshot_equal": child_stage_proof["snapshot_equal"],
        "child_stage_local_parser_observation_equal": child_stage_proof[
            "parser_observation_equal"
        ],
        "child_stage_local_preparation_commitment_equal": child_stage_proof[
            "preparation_commitment_equal"
        ],
        "child_stage_local_canonical_emission_byte_exact": child_stage_proof[
            "canonical_emission_byte_exact"
        ],
        "system_owner": "mmcif_polymer_component_topology_child",
        "wrapper_evidence_location": "factory_artifacts_only",
        "materialized_inter_residue_bond_count": 0,
        **_authority_false_document(),
    }
    state_bytes = _canonical_json_bytes(state_document)
    child_system = child.system
    provenance_marker = child_system.provenance.metadata.get(
        "mmcif_polymer_component_topology", {}
    )
    commitment_schema_id = provenance_marker.get(
        "preparation_inventory_commitment_schema_id"
    )
    commitment_sha256 = provenance_marker.get("preparation_inventory_commitment_sha256")
    child_observation_sha256 = child.to_dict().get(
        "augmented_system_parser_observation_sha256"
    )
    if (
        type(commitment_schema_id) is not str
        or type(commitment_sha256) is not str
        or type(child_observation_sha256) is not str
    ):
        raise MmcifPolymerComponentTerminalLeavingPolicyError(
            "child_commitment_missing",
            "unchanged child observation or preparation commitment is missing",
        )
    source_binding_document = {
        "schema_id": (
            MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_SOURCE_BINDING_SCHEMA_ID
        ),
        "envelope_version": (
            MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_ENVELOPE_VERSION
        ),
        "profile_id": MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_PROFILE_ID,
        "full_source_sha256": _sha256_bytes(data),
        "child_source_sha256": _sha256_bytes(child_source),
        "child_source_binding_sha256": child.source_binding_sha256,
        "child_canonical_output_sha256": _sha256_bytes(child_write.payload),
        "child_augmented_system_snapshot_sha256": (
            child.augmented_system_snapshot_sha256
        ),
        "child_augmented_system_parser_observation_sha256": (child_observation_sha256),
        "child_stage_proof_sha256": _sha256_bytes(child_stage_proof_bytes),
        "child_stage_local_gate_results": {
            name: state_document[name] for name in _CHILD_STAGE_GATE_FIELDS
        },
        "child_preparation_inventory_commitment_schema_id": commitment_schema_id,
        "child_preparation_inventory_commitment_sha256": commitment_sha256,
        "canonical_output_sha256": _sha256_bytes(canonical_output),
        "projection_sha256": _sha256_bytes(projection_bytes),
        "state_sha256": _sha256_bytes(state_bytes),
        "source_id_sha256": source_id_sha,
        "data_block_name_sha256": _sha256_bytes(block.name.encode("ascii")),
    }
    return _ParsedState(
        full_source=data,
        source_id=source_id,
        block_name=block.name,
        child_source=child_source,
        canonical_output=canonical_output,
        annotations=annotations,
        boundaries=boundaries,
        child_stage_proof_bytes=child_stage_proof_bytes,
        projection_bytes=projection_bytes,
        state_bytes=state_bytes,
        source_binding_bytes=_canonical_json_bytes(source_binding_document),
    )


def _state_document(state: _ParsedState) -> dict[str, Any]:
    return json.loads(state.state_bytes.decode("ascii"))


def _projection_document(state: _ParsedState) -> dict[str, Any]:
    return json.loads(state.projection_bytes.decode("ascii"))


def _source_binding_document(state: _ParsedState) -> dict[str, Any]:
    return json.loads(state.source_binding_bytes.decode("ascii"))


def _child_stage_proof_document(state: _ParsedState) -> dict[str, Any]:
    return json.loads(state.child_stage_proof_bytes.decode("ascii"))


@dataclass(frozen=True, init=False)
class MmcifPolymerComponentTerminalLeavingAtomAnnotation:
    """One detached source-reported component-atom annotation row."""

    comp_id: str
    atom_id: str
    template_ordinal: int
    leaving_atom: bool
    backbone_atom: bool
    n_terminal_atom: bool
    c_terminal_atom: bool

    def __init__(
        self, row: _AnnotationState, *, _factory_token: object | None = None
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN or type(row) is not _AnnotationState:
            raise TypeError(
                "MmcifPolymerComponentTerminalLeavingAtomAnnotation is factory-only"
            )
        for name in (
            "comp_id",
            "atom_id",
            "template_ordinal",
            "leaving_atom",
            "backbone_atom",
            "n_terminal_atom",
            "c_terminal_atom",
        ):
            object.__setattr__(self, name, getattr(row, name))

    def to_dict(self) -> dict[str, Any]:
        return {
            "comp_id": self.comp_id,
            "atom_id": self.atom_id,
            "template_ordinal": self.template_ordinal,
            "leaving_atom": self.leaving_atom,
            "backbone_atom": self.backbone_atom,
            "n_terminal_atom": self.n_terminal_atom,
            "c_terminal_atom": self.c_terminal_atom,
        }


@dataclass(frozen=True, init=False)
class MmcifPolymerSequenceBoundary:
    """One per-asym sequence position, without chemical-terminus semantics."""

    asym_id: str
    entity_id: str
    sequence_number: int
    component_id: str
    position_role: str
    at_n_sequence_boundary: bool
    at_c_sequence_boundary: bool

    def __init__(
        self, row: _BoundaryState, *, _factory_token: object | None = None
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN or type(row) is not _BoundaryState:
            raise TypeError("MmcifPolymerSequenceBoundary is factory-only")
        for name in (
            "asym_id",
            "entity_id",
            "sequence_number",
            "component_id",
            "position_role",
            "at_n_sequence_boundary",
            "at_c_sequence_boundary",
        ):
            object.__setattr__(self, name, getattr(row, name))

    def to_dict(self) -> dict[str, Any]:
        return {
            "asym_id": self.asym_id,
            "entity_id": self.entity_id,
            "sequence_number": self.sequence_number,
            "component_id": self.component_id,
            "position_role": self.position_role,
            "at_n_sequence_boundary": self.at_n_sequence_boundary,
            "at_c_sequence_boundary": self.at_c_sequence_boundary,
        }


def _ingest_access_document(
    value: "MmcifPolymerComponentTerminalLeavingPolicyIngestResult",
) -> dict[str, Any]:
    state = value._state
    return {
        "artifact_type": "MmcifPolymerComponentTerminalLeavingPolicyIngestResult",
        "self_object_id": id(value),
        "state_object_id": id(state),
        "full_source_sha256": _sha256_bytes(state.full_source),
        "source_id_sha256": _sha256_bytes(state.source_id.encode("utf-8")),
        "block_name_sha256": _sha256_bytes(state.block_name.encode("ascii")),
        "child_source_sha256": _sha256_bytes(state.child_source),
        "canonical_output_sha256": _sha256_bytes(state.canonical_output),
        "annotations_sha256": _sha256_bytes(
            _canonical_json_bytes(
                [_annotation_document(row) for row in state.annotations]
            )
        ),
        "boundaries_sha256": _sha256_bytes(
            _canonical_json_bytes([_boundary_document(row) for row in state.boundaries])
        ),
        "child_stage_proof_sha256": _sha256_bytes(state.child_stage_proof_bytes),
        "projection_sha256": _sha256_bytes(state.projection_bytes),
        "state_sha256": _sha256_bytes(state.state_bytes),
        "source_binding_sha256": _sha256_bytes(state.source_binding_bytes),
    }


@dataclass(frozen=True, init=False)
class MmcifPolymerComponentTerminalLeavingPolicyIngestResult:
    """Factory-only wrapper ingest retaining an unchanged child system."""

    _state: _ParsedState = field(repr=False)
    _access_binding_bytes: bytes = field(repr=False)

    def __init__(
        self, state: _ParsedState, *, _factory_token: object | None = None
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN or type(state) is not _ParsedState:
            raise TypeError(
                "MmcifPolymerComponentTerminalLeavingPolicyIngestResult is factory-only"
            )
        object.__setattr__(self, "_state", state)
        binding = _canonical_json_bytes(_ingest_access_document(self))
        object.__setattr__(self, "_access_binding_bytes", binding)
        _register_anchor(self, binding)

    @property
    def system(self) -> AllAtomSystem:
        """Return the unchanged detached seven-field child system."""

        state = _validate_ingest(self)
        return parse_mmcif_polymer_component_topology(
            state.child_source, source_id=state.source_id
        ).system

    @property
    def child_ingest(self) -> MmcifPolymerComponentTopologyIngestResult:
        state = _validate_ingest(self)
        return parse_mmcif_polymer_component_topology(
            state.child_source, source_id=state.source_id
        )

    @property
    def atom_annotations(
        self,
    ) -> tuple[MmcifPolymerComponentTerminalLeavingAtomAnnotation, ...]:
        state = _validate_ingest(self)
        return tuple(
            MmcifPolymerComponentTerminalLeavingAtomAnnotation(
                row, _factory_token=_FACTORY_TOKEN
            )
            for row in state.annotations
        )

    @property
    def sequence_boundaries(self) -> tuple[MmcifPolymerSequenceBoundary, ...]:
        state = _validate_ingest(self)
        return tuple(
            MmcifPolymerSequenceBoundary(row, _factory_token=_FACTORY_TOKEN)
            for row in state.boundaries
        )

    @property
    def data_block_name(self) -> str:
        return _validate_ingest(self).block_name

    @property
    def projection_sha256(self) -> str:
        return _sha256_bytes(_validate_ingest(self).projection_bytes)

    @property
    def state_sha256(self) -> str:
        return _sha256_bytes(_validate_ingest(self).state_bytes)

    @property
    def source_binding_sha256(self) -> str:
        return _sha256_bytes(_validate_ingest(self).source_binding_bytes)

    @property
    def full_source_sha256(self) -> str:
        return str(
            _source_binding_document(_validate_ingest(self))["full_source_sha256"]
        )

    @property
    def canonical_output_sha256(self) -> str:
        return str(
            _source_binding_document(_validate_ingest(self))["canonical_output_sha256"]
        )

    def to_dict(self) -> dict[str, Any]:
        state = _validate_ingest(self)
        document = dict(_state_document(state))
        binding = _source_binding_document(state)
        projection = _projection_document(state)
        document.update(
            {
                "policy_schema_id": MMCIF_POLYMER_TERMINAL_LEAVING_POLICY_SCHEMA_ID,
                "scope": MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_SCOPE,
                "projection_schema_id": projection["schema_id"],
                "projection_sha256": _sha256_bytes(state.projection_bytes),
                "source_binding_schema_id": binding["schema_id"],
                "source_binding_sha256": _sha256_bytes(state.source_binding_bytes),
                "full_source_sha256": binding["full_source_sha256"],
                "canonical_output_sha256": binding["canonical_output_sha256"],
                "child_source_binding_sha256": binding["child_source_binding_sha256"],
                "child_augmented_system_snapshot_sha256": binding[
                    "child_augmented_system_snapshot_sha256"
                ],
                "child_augmented_system_parser_observation_sha256": binding[
                    "child_augmented_system_parser_observation_sha256"
                ],
                "child_preparation_inventory_commitment_schema_id": binding[
                    "child_preparation_inventory_commitment_schema_id"
                ],
                "child_preparation_inventory_commitment_sha256": binding[
                    "child_preparation_inventory_commitment_sha256"
                ],
                "child_stage_proof_sha256": _sha256_bytes(
                    state.child_stage_proof_bytes
                ),
                "component_atom_annotation_count": len(state.annotations),
                "sequence_boundary_count": len(state.boundaries),
                "component_atom_annotations": projection["component_atom_annotations"],
                "sequence_boundaries": projection["sequence_boundaries"],
                "bare_system_retains_wrapper_evidence": False,
                **_authority_false_document(),
            }
        )
        return document


def _validate_ingest(
    value: MmcifPolymerComponentTerminalLeavingPolicyIngestResult,
) -> _ParsedState:
    if type(value) is not MmcifPolymerComponentTerminalLeavingPolicyIngestResult:
        raise TypeError("an exact terminal/leaving policy ingest result is required")
    try:
        binding = _canonical_json_bytes(_ingest_access_document(value))
        _validate_anchor(value, binding)
        state = value._state
    except Exception:
        raise MmcifPolymerComponentTerminalLeavingPolicyError(
            "stale_ingest_binding", "stored wrapper ingest evidence is stale"
        ) from None
    if value._access_binding_bytes != binding:
        raise MmcifPolymerComponentTerminalLeavingPolicyError(
            "stale_ingest_binding", "stored wrapper ingest evidence is stale"
        )
    return state


def parse_mmcif_polymer_component_terminal_leaving_policy(
    data: bytes, *, source_id: str = ""
) -> MmcifPolymerComponentTerminalLeavingPolicyIngestResult:
    """Parse the strict metadata-only terminal/leaving annotation envelope."""

    return MmcifPolymerComponentTerminalLeavingPolicyIngestResult(
        _build_state(data, source_id=source_id), _factory_token=_FACTORY_TOKEN
    )


def mmcif_polymer_component_terminal_leaving_policy_projection_sha256(
    value: MmcifPolymerComponentTerminalLeavingPolicyIngestResult,
) -> str:
    return _sha256_bytes(_validate_ingest(value).projection_bytes)


def mmcif_polymer_component_terminal_leaving_policy_state_sha256(
    value: MmcifPolymerComponentTerminalLeavingPolicyIngestResult,
) -> str:
    return _sha256_bytes(_validate_ingest(value).state_bytes)


def _policy_report_document(state: _ParsedState) -> dict[str, Any]:
    binding = _source_binding_document(state)
    state_document = _state_document(state)
    return {
        "schema_id": MMCIF_POLYMER_TERMINAL_LEAVING_POLICY_SCHEMA_ID,
        "profile_id": MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_PROFILE_ID,
        "scope": MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_SCOPE,
        "status": "available",
        "rules_schema_id": MMCIF_POLYMER_TERMINAL_LEAVING_RULES_SCHEMA_ID,
        "rules_sha256": MMCIF_POLYMER_TERMINAL_LEAVING_RULES_SHA256,
        "projection_schema_id": (
            MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_PROJECTION_SCHEMA_ID
        ),
        "projection_sha256": _sha256_bytes(state.projection_bytes),
        "state_schema_id": (
            MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_STATE_SCHEMA_ID
        ),
        "state_sha256": _sha256_bytes(state.state_bytes),
        "source_binding_schema_id": binding["schema_id"],
        "source_binding_sha256": _sha256_bytes(state.source_binding_bytes),
        "child_profile_id": state_document["child_profile_id"],
        "child_parser_pedigree_id": state_document["child_parser_pedigree_id"],
        "child_component_projection_sha256": state_document[
            "child_component_projection_sha256"
        ],
        "child_topology_state_sha256": state_document["child_topology_state_sha256"],
        "child_augmented_topology_sha256": state_document[
            "child_augmented_topology_sha256"
        ],
        "child_source_binding_sha256": binding["child_source_binding_sha256"],
        "child_augmented_system_snapshot_sha256": binding[
            "child_augmented_system_snapshot_sha256"
        ],
        "child_augmented_system_parser_observation_sha256": binding[
            "child_augmented_system_parser_observation_sha256"
        ],
        "child_preparation_inventory_commitment_schema_id": binding[
            "child_preparation_inventory_commitment_schema_id"
        ],
        "child_preparation_inventory_commitment_sha256": binding[
            "child_preparation_inventory_commitment_sha256"
        ],
        "child_stage_proof_sha256": _sha256_bytes(state.child_stage_proof_bytes),
        **{name: state_document[name] for name in _CHILD_STAGE_GATE_FIELDS},
        "component_atom_annotation_count": len(state.annotations),
        "sequence_boundary_count": len(state.boundaries),
        "materialized_inter_residue_bond_count": 0,
        "system_unchanged_from_child": state_document[
            "child_stage_local_system_byte_exact"
        ],
        "wrapper_evidence_factory_only": True,
        "bare_system_retains_wrapper_evidence": False,
        "blockers": (
            "source_digest_is_not_authentication",
            "sequence_boundaries_are_not_chemical_termini",
            "terminal_and_leaving_annotations_are_not_applied_chemistry",
            "peptide_and_inter_residue_bonds_are_not_inferred",
            "preparation_and_parameterability_not_assessed",
            "runtime_and_claims_not_authorized",
        ),
        **_authority_false_document(),
    }


def _policy_report_access_document(
    value: "MmcifPolymerTerminalLeavingPolicyReport",
) -> dict[str, Any]:
    return {
        "artifact_type": "MmcifPolymerTerminalLeavingPolicyReport",
        "self_object_id": id(value),
        "ingest_object_id": id(value._ingest),
        "document_sha256": _sha256_bytes(value._document_bytes),
    }


@dataclass(frozen=True, init=False)
class MmcifPolymerTerminalLeavingPolicyReport:
    """Factory-only non-promoting policy report over wrapper evidence."""

    _ingest: MmcifPolymerComponentTerminalLeavingPolicyIngestResult = field(repr=False)
    _document_bytes: bytes = field(repr=False)
    _access_binding_bytes: bytes = field(repr=False)

    def __init__(
        self,
        ingest: MmcifPolymerComponentTerminalLeavingPolicyIngestResult,
        *,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise TypeError("MmcifPolymerTerminalLeavingPolicyReport is factory-only")
        document = _policy_report_document(_validate_ingest(ingest))
        object.__setattr__(self, "_ingest", ingest)
        object.__setattr__(self, "_document_bytes", _canonical_json_bytes(document))
        binding = _canonical_json_bytes(_policy_report_access_document(self))
        object.__setattr__(self, "_access_binding_bytes", binding)
        _register_anchor(self, binding)

    @property
    def report_sha256(self) -> str:
        _validate_policy_report(self)
        return _sha256_bytes(self._document_bytes)

    def to_dict(self) -> dict[str, Any]:
        document = _validate_policy_report(self)
        return {**document, "report_sha256": self.report_sha256}


def _validate_policy_report(
    value: MmcifPolymerTerminalLeavingPolicyReport,
) -> dict[str, Any]:
    if type(value) is not MmcifPolymerTerminalLeavingPolicyReport:
        raise TypeError("an exact terminal/leaving policy report is required")
    try:
        binding = _canonical_json_bytes(_policy_report_access_document(value))
        _validate_anchor(value, binding)
        expected = _policy_report_document(_validate_ingest(value._ingest))
    except Exception:
        raise MmcifPolymerComponentTerminalLeavingPolicyError(
            "stale_policy_report_binding", "policy report binding is stale"
        ) from None
    if (
        value._access_binding_bytes != binding
        or value._document_bytes != _canonical_json_bytes(expected)
    ):
        raise MmcifPolymerComponentTerminalLeavingPolicyError(
            "stale_policy_report_binding", "policy report binding is stale"
        )
    return expected


def analyze_mmcif_polymer_terminal_leaving_policy(
    value: MmcifPolymerComponentTerminalLeavingPolicyIngestResult,
) -> MmcifPolymerTerminalLeavingPolicyReport:
    """Return fresh metadata-only policy evidence for an exact wrapper ingest."""

    return MmcifPolymerTerminalLeavingPolicyReport(value, _factory_token=_FACTORY_TOKEN)


def _receipt_document(state: _ParsedState, payload: bytes) -> dict[str, Any]:
    return {
        "schema_id": (
            MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_WRITE_RECEIPT_SCHEMA_ID
        ),
        "envelope_version": (
            MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_ENVELOPE_VERSION
        ),
        "writer_version": (
            MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_WRITER_VERSION
        ),
        "profile_id": MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_PROFILE_ID,
        "input_full_source_sha256": _sha256_bytes(state.full_source),
        "input_child_source_sha256": _sha256_bytes(state.child_source),
        "input_projection_sha256": _sha256_bytes(state.projection_bytes),
        "input_state_sha256": _sha256_bytes(state.state_bytes),
        "input_source_binding_sha256": _sha256_bytes(state.source_binding_bytes),
        "output_source_sha256": _sha256_bytes(payload),
        "output_byte_count": len(payload),
        "materialized_inter_residue_bond_count": 0,
        **_authority_false_document(),
    }


def _receipt_access_document(
    value: "MmcifPolymerComponentTerminalLeavingPolicyWriteReceipt",
) -> dict[str, Any]:
    return {
        "artifact_type": "MmcifPolymerComponentTerminalLeavingPolicyWriteReceipt",
        "self_object_id": id(value),
        "ingest_object_id": id(value._ingest),
        "payload_object_id": id(value._payload),
        "payload_sha256": _sha256_bytes(value._payload),
        "document_sha256": _sha256_bytes(value._document_bytes),
    }


@dataclass(frozen=True, init=False)
class MmcifPolymerComponentTerminalLeavingPolicyWriteReceipt:
    _ingest: MmcifPolymerComponentTerminalLeavingPolicyIngestResult = field(repr=False)
    _payload: bytes = field(repr=False)
    _document_bytes: bytes = field(repr=False)
    _access_binding_bytes: bytes = field(repr=False)

    def __init__(
        self,
        ingest: MmcifPolymerComponentTerminalLeavingPolicyIngestResult,
        payload: bytes,
        *,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN or type(payload) is not bytes:
            raise TypeError(
                "MmcifPolymerComponentTerminalLeavingPolicyWriteReceipt is factory-only"
            )
        document = _receipt_document(_validate_ingest(ingest), payload)
        object.__setattr__(self, "_ingest", ingest)
        object.__setattr__(self, "_payload", payload)
        object.__setattr__(self, "_document_bytes", _canonical_json_bytes(document))
        binding = _canonical_json_bytes(_receipt_access_document(self))
        object.__setattr__(self, "_access_binding_bytes", binding)
        _register_anchor(self, binding)

    @property
    def output_source_sha256(self) -> str:
        return str(_validate_receipt(self)["output_source_sha256"])

    @property
    def output_byte_count(self) -> int:
        return int(_validate_receipt(self)["output_byte_count"])

    @property
    def receipt_sha256(self) -> str:
        _validate_receipt(self)
        return _sha256_bytes(self._document_bytes)

    def to_dict(self) -> dict[str, Any]:
        return {**_validate_receipt(self), "receipt_sha256": self.receipt_sha256}


def _validate_receipt(
    value: MmcifPolymerComponentTerminalLeavingPolicyWriteReceipt,
    *,
    state: _ParsedState | None = None,
) -> dict[str, Any]:
    if type(value) is not MmcifPolymerComponentTerminalLeavingPolicyWriteReceipt:
        raise TypeError("an exact terminal/leaving write receipt is required")
    try:
        binding = _canonical_json_bytes(_receipt_access_document(value))
        _validate_anchor(value, binding)
        validated_state = _validate_ingest(value._ingest) if state is None else state
        expected = _receipt_document(validated_state, value._payload)
    except Exception:
        raise MmcifPolymerComponentTerminalLeavingPolicyError(
            "stale_write_receipt_binding", "write receipt binding is stale"
        ) from None
    if (
        value._access_binding_bytes != binding
        or value._document_bytes != _canonical_json_bytes(expected)
    ):
        raise MmcifPolymerComponentTerminalLeavingPolicyError(
            "stale_write_receipt_binding", "write receipt binding is stale"
        )
    return expected


def _write_result_access_document(
    value: "MmcifPolymerComponentTerminalLeavingPolicyWriteResult",
) -> dict[str, Any]:
    return {
        "artifact_type": "MmcifPolymerComponentTerminalLeavingPolicyWriteResult",
        "self_object_id": id(value),
        "ingest_object_id": id(value._ingest),
        "payload_object_id": id(value._payload),
        "payload_sha256": _sha256_bytes(value._payload),
        "receipt_object_id": id(value._receipt),
    }


@dataclass(frozen=True, init=False)
class MmcifPolymerComponentTerminalLeavingPolicyWriteResult:
    _ingest: MmcifPolymerComponentTerminalLeavingPolicyIngestResult = field(repr=False)
    _payload: bytes = field(repr=False)
    _receipt: MmcifPolymerComponentTerminalLeavingPolicyWriteReceipt = field(repr=False)
    _access_binding_bytes: bytes = field(repr=False)

    def __init__(
        self,
        ingest: MmcifPolymerComponentTerminalLeavingPolicyIngestResult,
        payload: bytes,
        receipt: MmcifPolymerComponentTerminalLeavingPolicyWriteReceipt,
        *,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise TypeError(
                "MmcifPolymerComponentTerminalLeavingPolicyWriteResult is factory-only"
            )
        if receipt._ingest is not ingest or receipt._payload is not payload:
            raise MmcifPolymerComponentTerminalLeavingPolicyError(
                "crosswired_write_artifacts", "write artifacts are crosswired"
            )
        _validate_receipt(receipt)
        object.__setattr__(self, "_ingest", ingest)
        object.__setattr__(self, "_payload", payload)
        object.__setattr__(self, "_receipt", receipt)
        binding = _canonical_json_bytes(_write_result_access_document(self))
        object.__setattr__(self, "_access_binding_bytes", binding)
        _register_anchor(self, binding)

    @property
    def payload(self) -> bytes:
        _validate_write_result(self)
        return self._payload

    @property
    def receipt(self) -> MmcifPolymerComponentTerminalLeavingPolicyWriteReceipt:
        _validate_write_result(self)
        detached = parse_mmcif_polymer_component_terminal_leaving_policy(
            self._ingest._state.full_source,
            source_id=self._ingest._state.source_id,
        )
        return MmcifPolymerComponentTerminalLeavingPolicyWriteReceipt(
            detached, self._payload, _factory_token=_FACTORY_TOKEN
        )

    def to_dict(self) -> dict[str, Any]:
        _validate_write_result(self)
        return {
            "output_source_sha256": _sha256_bytes(self._payload),
            "output_byte_count": len(self._payload),
            "receipt": self._receipt.to_dict(),
            **_authority_false_document(),
        }


def _validate_write_result(
    value: MmcifPolymerComponentTerminalLeavingPolicyWriteResult,
) -> _ParsedState:
    if type(value) is not MmcifPolymerComponentTerminalLeavingPolicyWriteResult:
        raise TypeError("an exact terminal/leaving write result is required")
    try:
        binding = _canonical_json_bytes(_write_result_access_document(value))
        _validate_anchor(value, binding)
        state = _validate_ingest(value._ingest)
        _validate_receipt(value._receipt, state=state)
    except Exception:
        raise MmcifPolymerComponentTerminalLeavingPolicyError(
            "stale_write_result_binding", "write result binding is stale"
        ) from None
    if (
        value._access_binding_bytes != binding
        or value._payload != state.canonical_output
        or value._receipt._ingest is not value._ingest
        or value._receipt._payload is not value._payload
    ):
        raise MmcifPolymerComponentTerminalLeavingPolicyError(
            "stale_write_result_binding", "write result binding is stale"
        )
    return state


def write_mmcif_polymer_component_terminal_leaving_policy(
    value: MmcifPolymerComponentTerminalLeavingPolicyIngestResult,
) -> MmcifPolymerComponentTerminalLeavingPolicyWriteResult:
    """Emit and independently revalidate the canonical 11-field envelope."""

    state = _validate_ingest(value)
    reparsed = _build_state(state.canonical_output, source_id=state.source_id)
    if (
        reparsed.state_bytes != state.state_bytes
        or reparsed.projection_bytes != state.projection_bytes
        or reparsed.canonical_output != state.canonical_output
    ):
        raise MmcifPolymerComponentTerminalLeavingPolicyError(
            "canonical_output_state_mismatch",
            "canonical output did not recover the bound wrapper state",
        )
    payload = state.canonical_output
    receipt = MmcifPolymerComponentTerminalLeavingPolicyWriteReceipt(
        value, payload, _factory_token=_FACTORY_TOKEN
    )
    return MmcifPolymerComponentTerminalLeavingPolicyWriteResult(
        value, payload, receipt, _factory_token=_FACTORY_TOKEN
    )


def emit_mmcif_polymer_component_terminal_leaving_policy(
    value: MmcifPolymerComponentTerminalLeavingPolicyIngestResult,
) -> MmcifPolymerComponentTerminalLeavingPolicyWriteResult:
    return write_mmcif_polymer_component_terminal_leaving_policy(value)


def serialize_mmcif_polymer_component_terminal_leaving_policy(
    value: MmcifPolymerComponentTerminalLeavingPolicyIngestResult,
) -> bytes:
    return write_mmcif_polymer_component_terminal_leaving_policy(value).payload


def _round_trip_report_document(
    source: MmcifPolymerComponentTerminalLeavingPolicyIngestResult,
    first: MmcifPolymerComponentTerminalLeavingPolicyWriteResult,
    reparsed: MmcifPolymerComponentTerminalLeavingPolicyIngestResult,
    second: MmcifPolymerComponentTerminalLeavingPolicyWriteResult,
) -> dict[str, Any]:
    source_state = _validate_write_result(first)
    reparsed_state = _validate_write_result(second)
    if first._ingest is not source or second._ingest is not reparsed:
        raise MmcifPolymerComponentTerminalLeavingPolicyError(
            "crosswired_round_trip_artifacts", "round-trip artifacts are crosswired"
        )
    source_binding = _source_binding_document(source_state)
    reparsed_binding = _source_binding_document(reparsed_state)
    source_child_proof = _child_stage_proof_document(source_state)
    reparsed_child_proof = _child_stage_proof_document(reparsed_state)
    values: dict[str, Any] = {
        "schema_id": (
            MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_ROUND_TRIP_REPORT_SCHEMA_ID
        ),
        "envelope_version": (
            MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_ENVELOPE_VERSION
        ),
        "profile_id": MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_PROFILE_ID,
        "policy_schema_id": MMCIF_POLYMER_TERMINAL_LEAVING_POLICY_SCHEMA_ID,
        "scope": MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_SCOPE,
        "input_full_source_sha256": _sha256_bytes(source_state.full_source),
        "reparsed_full_source_sha256": _sha256_bytes(reparsed_state.full_source),
        "input_projection_sha256": _sha256_bytes(source_state.projection_bytes),
        "reparsed_projection_sha256": _sha256_bytes(reparsed_state.projection_bytes),
        "input_state_sha256": _sha256_bytes(source_state.state_bytes),
        "reparsed_state_sha256": _sha256_bytes(reparsed_state.state_bytes),
        "input_child_component_projection_sha256": _state_document(source_state)[
            "child_component_projection_sha256"
        ],
        "reparsed_child_component_projection_sha256": _state_document(reparsed_state)[
            "child_component_projection_sha256"
        ],
        "input_child_topology_state_sha256": _state_document(source_state)[
            "child_topology_state_sha256"
        ],
        "reparsed_child_topology_state_sha256": _state_document(reparsed_state)[
            "child_topology_state_sha256"
        ],
        "input_child_source_binding_sha256": source_binding[
            "child_source_binding_sha256"
        ],
        "reparsed_child_source_binding_sha256": reparsed_binding[
            "child_source_binding_sha256"
        ],
        "input_child_augmented_system_snapshot_sha256": source_binding[
            "child_augmented_system_snapshot_sha256"
        ],
        "reparsed_child_augmented_system_snapshot_sha256": reparsed_binding[
            "child_augmented_system_snapshot_sha256"
        ],
        "input_child_augmented_system_parser_observation_sha256": source_binding[
            "child_augmented_system_parser_observation_sha256"
        ],
        "reparsed_child_augmented_system_parser_observation_sha256": (
            reparsed_binding["child_augmented_system_parser_observation_sha256"]
        ),
        "input_child_preparation_inventory_commitment_sha256": source_binding[
            "child_preparation_inventory_commitment_sha256"
        ],
        "reparsed_child_preparation_inventory_commitment_sha256": reparsed_binding[
            "child_preparation_inventory_commitment_sha256"
        ],
        "input_child_canonical_output_sha256": source_binding[
            "child_canonical_output_sha256"
        ],
        "reparsed_child_canonical_output_sha256": reparsed_binding[
            "child_canonical_output_sha256"
        ],
        "input_child_stage_proof_sha256": _sha256_bytes(
            source_state.child_stage_proof_bytes
        ),
        "reparsed_child_stage_proof_sha256": _sha256_bytes(
            reparsed_state.child_stage_proof_bytes
        ),
        "emitted_source_sha256": _sha256_bytes(first._payload),
        "reemitted_source_sha256": _sha256_bytes(second._payload),
        "writer_receipt_sha256": _sha256_bytes(first._receipt._document_bytes),
        "reemitted_writer_receipt_sha256": _sha256_bytes(
            second._receipt._document_bytes
        ),
        "projection_equal": source_state.projection_bytes
        == reparsed_state.projection_bytes,
        "state_equal": source_state.state_bytes == reparsed_state.state_bytes,
        "child_component_projection_equal": _state_document(source_state)[
            "child_component_projection_sha256"
        ]
        == _state_document(reparsed_state)["child_component_projection_sha256"],
        "child_topology_state_equal": _state_document(source_state)[
            "child_topology_state_sha256"
        ]
        == _state_document(reparsed_state)["child_topology_state_sha256"],
        "child_source_binding_equal": source_binding["child_source_binding_sha256"]
        == reparsed_binding["child_source_binding_sha256"],
        "child_snapshot_equal": source_binding["child_augmented_system_snapshot_sha256"]
        == reparsed_binding["child_augmented_system_snapshot_sha256"],
        "child_parser_observation_equal": source_binding[
            "child_augmented_system_parser_observation_sha256"
        ]
        == reparsed_binding["child_augmented_system_parser_observation_sha256"],
        "child_preparation_inventory_commitment_equal": source_binding[
            "child_preparation_inventory_commitment_sha256"
        ]
        == reparsed_binding["child_preparation_inventory_commitment_sha256"],
        "child_stage_proof_equal": source_state.child_stage_proof_bytes
        == reparsed_state.child_stage_proof_bytes,
        "input_child_stage_local_independent_projection_validated": (
            source_child_proof["validated"]
        ),
        "reparsed_child_stage_local_independent_projection_validated": (
            reparsed_child_proof["validated"]
        ),
        "input_child_stage_local_system_byte_exact": source_child_proof[
            "system_byte_exact"
        ],
        "reparsed_child_stage_local_system_byte_exact": reparsed_child_proof[
            "system_byte_exact"
        ],
        "input_child_stage_local_canonical_emission_byte_exact": source_child_proof[
            "canonical_emission_byte_exact"
        ],
        "reparsed_child_stage_local_canonical_emission_byte_exact": (
            reparsed_child_proof["canonical_emission_byte_exact"]
        ),
        "emitted_source_reparsed_exact": first._payload == reparsed_state.full_source,
        "second_emission_byte_stable": first._payload == second._payload,
        "system_unchanged_from_child": source_child_proof["system_byte_exact"]
        and reparsed_child_proof["system_byte_exact"],
        "materialized_inter_residue_bond_count": 0,
        **_authority_false_document(),
    }
    values["round_trip_preserved"] = all(
        values[name]
        for name in (
            "projection_equal",
            "state_equal",
            "child_component_projection_equal",
            "child_topology_state_equal",
            "input_child_stage_local_independent_projection_validated",
            "reparsed_child_stage_local_independent_projection_validated",
            "input_child_stage_local_system_byte_exact",
            "reparsed_child_stage_local_system_byte_exact",
            "input_child_stage_local_canonical_emission_byte_exact",
            "reparsed_child_stage_local_canonical_emission_byte_exact",
            "emitted_source_reparsed_exact",
            "second_emission_byte_stable",
            "system_unchanged_from_child",
        )
    )
    return values


def _round_trip_report_access_document(
    value: "MmcifPolymerComponentTerminalLeavingPolicyRoundTripReport",
) -> dict[str, Any]:
    return {
        "artifact_type": ("MmcifPolymerComponentTerminalLeavingPolicyRoundTripReport"),
        "self_object_id": id(value),
        "source_object_id": id(value._source),
        "first_object_id": id(value._first),
        "reparsed_object_id": id(value._reparsed),
        "second_object_id": id(value._second),
        "document_sha256": _sha256_bytes(value._document_bytes),
    }


@dataclass(frozen=True, init=False)
class MmcifPolymerComponentTerminalLeavingPolicyRoundTripReport:
    _source: MmcifPolymerComponentTerminalLeavingPolicyIngestResult = field(repr=False)
    _first: MmcifPolymerComponentTerminalLeavingPolicyWriteResult = field(repr=False)
    _reparsed: MmcifPolymerComponentTerminalLeavingPolicyIngestResult = field(
        repr=False
    )
    _second: MmcifPolymerComponentTerminalLeavingPolicyWriteResult = field(repr=False)
    _document_bytes: bytes = field(repr=False)
    _access_binding_bytes: bytes = field(repr=False)

    def __init__(
        self,
        source: MmcifPolymerComponentTerminalLeavingPolicyIngestResult,
        first: MmcifPolymerComponentTerminalLeavingPolicyWriteResult,
        reparsed: MmcifPolymerComponentTerminalLeavingPolicyIngestResult,
        second: MmcifPolymerComponentTerminalLeavingPolicyWriteResult,
        *,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise TypeError(
                "MmcifPolymerComponentTerminalLeavingPolicyRoundTripReport "
                "is factory-only"
            )
        document = _round_trip_report_document(source, first, reparsed, second)
        if document["round_trip_preserved"] is not True:
            raise MmcifPolymerComponentTerminalLeavingPolicyError(
                "round_trip_mismatch", "wrapper state did not round trip exactly"
            )
        object.__setattr__(self, "_source", source)
        object.__setattr__(self, "_first", first)
        object.__setattr__(self, "_reparsed", reparsed)
        object.__setattr__(self, "_second", second)
        object.__setattr__(self, "_document_bytes", _canonical_json_bytes(document))
        binding = _canonical_json_bytes(_round_trip_report_access_document(self))
        object.__setattr__(self, "_access_binding_bytes", binding)
        _register_anchor(self, binding)

    @property
    def report_sha256(self) -> str:
        _validate_round_trip_report(self)
        return _sha256_bytes(self._document_bytes)

    def to_dict(self) -> dict[str, Any]:
        return {
            **_validate_round_trip_report(self),
            "report_sha256": self.report_sha256,
        }


def _validate_round_trip_report(
    value: MmcifPolymerComponentTerminalLeavingPolicyRoundTripReport,
) -> dict[str, Any]:
    if type(value) is not MmcifPolymerComponentTerminalLeavingPolicyRoundTripReport:
        raise TypeError("an exact terminal/leaving round-trip report is required")
    try:
        binding = _canonical_json_bytes(_round_trip_report_access_document(value))
        _validate_anchor(value, binding)
        expected = _round_trip_report_document(
            value._source, value._first, value._reparsed, value._second
        )
    except Exception:
        raise MmcifPolymerComponentTerminalLeavingPolicyError(
            "crosswired_round_trip_artifacts", "round-trip artifacts are crosswired"
        ) from None
    if (
        value._access_binding_bytes != binding
        or value._document_bytes != _canonical_json_bytes(expected)
        or expected["round_trip_preserved"] is not True
    ):
        raise MmcifPolymerComponentTerminalLeavingPolicyError(
            "crosswired_round_trip_artifacts", "round-trip artifacts are crosswired"
        )
    return expected


def _round_trip_result_access_document(
    value: "MmcifPolymerComponentTerminalLeavingPolicyRoundTripResult",
) -> dict[str, Any]:
    return {
        "artifact_type": ("MmcifPolymerComponentTerminalLeavingPolicyRoundTripResult"),
        "self_object_id": id(value),
        "source_object_id": id(value._source),
        "first_object_id": id(value._first),
        "reparsed_object_id": id(value._reparsed),
        "second_object_id": id(value._second),
        "report_object_id": id(value._report),
    }


@dataclass(frozen=True, init=False)
class MmcifPolymerComponentTerminalLeavingPolicyRoundTripResult:
    _source: MmcifPolymerComponentTerminalLeavingPolicyIngestResult = field(repr=False)
    _first: MmcifPolymerComponentTerminalLeavingPolicyWriteResult = field(repr=False)
    _reparsed: MmcifPolymerComponentTerminalLeavingPolicyIngestResult = field(
        repr=False
    )
    _second: MmcifPolymerComponentTerminalLeavingPolicyWriteResult = field(repr=False)
    _report: MmcifPolymerComponentTerminalLeavingPolicyRoundTripReport = field(
        repr=False
    )
    _access_binding_bytes: bytes = field(repr=False)

    def __init__(
        self,
        source: MmcifPolymerComponentTerminalLeavingPolicyIngestResult,
        first: MmcifPolymerComponentTerminalLeavingPolicyWriteResult,
        reparsed: MmcifPolymerComponentTerminalLeavingPolicyIngestResult,
        second: MmcifPolymerComponentTerminalLeavingPolicyWriteResult,
        report: MmcifPolymerComponentTerminalLeavingPolicyRoundTripReport,
        *,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise TypeError(
                "MmcifPolymerComponentTerminalLeavingPolicyRoundTripResult "
                "is factory-only"
            )
        object.__setattr__(self, "_source", source)
        object.__setattr__(self, "_first", first)
        object.__setattr__(self, "_reparsed", reparsed)
        object.__setattr__(self, "_second", second)
        object.__setattr__(self, "_report", report)
        _validate_round_trip_links(self)
        binding = _canonical_json_bytes(_round_trip_result_access_document(self))
        object.__setattr__(self, "_access_binding_bytes", binding)
        _register_anchor(self, binding)

    @property
    def source_ingest(
        self,
    ) -> MmcifPolymerComponentTerminalLeavingPolicyIngestResult:
        _validate_round_trip_result(self)
        return parse_mmcif_polymer_component_terminal_leaving_policy(
            self._source._state.full_source, source_id=self._source._state.source_id
        )

    @property
    def write_result(
        self,
    ) -> MmcifPolymerComponentTerminalLeavingPolicyWriteResult:
        return write_mmcif_polymer_component_terminal_leaving_policy(self.source_ingest)

    @property
    def reparsed_ingest(
        self,
    ) -> MmcifPolymerComponentTerminalLeavingPolicyIngestResult:
        _validate_round_trip_result(self)
        return parse_mmcif_polymer_component_terminal_leaving_policy(
            self._reparsed._state.full_source,
            source_id=self._reparsed._state.source_id,
        )

    @property
    def reemitted_write_result(
        self,
    ) -> MmcifPolymerComponentTerminalLeavingPolicyWriteResult:
        return write_mmcif_polymer_component_terminal_leaving_policy(
            self.reparsed_ingest
        )

    @property
    def report(self) -> MmcifPolymerComponentTerminalLeavingPolicyRoundTripReport:
        _validate_round_trip_result(self)
        source = self.source_ingest
        first = write_mmcif_polymer_component_terminal_leaving_policy(source)
        reparsed = self.reparsed_ingest
        second = write_mmcif_polymer_component_terminal_leaving_policy(reparsed)
        return MmcifPolymerComponentTerminalLeavingPolicyRoundTripReport(
            source,
            first,
            reparsed,
            second,
            _factory_token=_FACTORY_TOKEN,
        )

    def to_dict(self) -> dict[str, Any]:
        _validate_round_trip_result(self)
        return {
            "source_ingest": self._source.to_dict(),
            "write_result": self._first.to_dict(),
            "reparsed_ingest": self._reparsed.to_dict(),
            "reemitted_write_result": self._second.to_dict(),
            "report": self._report.to_dict(),
            **_authority_false_document(),
        }


def _validate_round_trip_links(
    value: MmcifPolymerComponentTerminalLeavingPolicyRoundTripResult,
) -> None:
    if (
        type(value._source)
        is not MmcifPolymerComponentTerminalLeavingPolicyIngestResult
        or type(value._first)
        is not MmcifPolymerComponentTerminalLeavingPolicyWriteResult
        or type(value._reparsed)
        is not MmcifPolymerComponentTerminalLeavingPolicyIngestResult
        or type(value._second)
        is not MmcifPolymerComponentTerminalLeavingPolicyWriteResult
        or type(value._report)
        is not MmcifPolymerComponentTerminalLeavingPolicyRoundTripReport
        or value._first._ingest is not value._source
        or value._second._ingest is not value._reparsed
        or value._report._source is not value._source
        or value._report._first is not value._first
        or value._report._reparsed is not value._reparsed
        or value._report._second is not value._second
    ):
        raise MmcifPolymerComponentTerminalLeavingPolicyError(
            "crosswired_round_trip_artifacts", "round-trip artifacts are crosswired"
        )
    _validate_round_trip_report(value._report)


def _validate_round_trip_result(
    value: MmcifPolymerComponentTerminalLeavingPolicyRoundTripResult,
) -> None:
    if type(value) is not MmcifPolymerComponentTerminalLeavingPolicyRoundTripResult:
        raise TypeError("an exact terminal/leaving round-trip result is required")
    try:
        binding = _canonical_json_bytes(_round_trip_result_access_document(value))
        _validate_anchor(value, binding)
        _validate_round_trip_links(value)
    except Exception:
        raise MmcifPolymerComponentTerminalLeavingPolicyError(
            "crosswired_round_trip_artifacts", "round-trip artifacts are crosswired"
        ) from None
    if value._access_binding_bytes != binding:
        raise MmcifPolymerComponentTerminalLeavingPolicyError(
            "crosswired_round_trip_artifacts", "round-trip artifacts are crosswired"
        )


def round_trip_mmcif_polymer_component_terminal_leaving_policy_source(
    data: bytes, *, source_id: str = ""
) -> MmcifPolymerComponentTerminalLeavingPolicyRoundTripResult:
    """Parse, emit, reparse, and prove stable metadata-only round trip."""

    source = parse_mmcif_polymer_component_terminal_leaving_policy(
        data, source_id=source_id
    )
    first = write_mmcif_polymer_component_terminal_leaving_policy(source)
    reparsed = parse_mmcif_polymer_component_terminal_leaving_policy(
        first.payload, source_id=source_id
    )
    second = write_mmcif_polymer_component_terminal_leaving_policy(reparsed)
    report = MmcifPolymerComponentTerminalLeavingPolicyRoundTripReport(
        source,
        first,
        reparsed,
        second,
        _factory_token=_FACTORY_TOKEN,
    )
    return MmcifPolymerComponentTerminalLeavingPolicyRoundTripResult(
        source,
        first,
        reparsed,
        second,
        report,
        _factory_token=_FACTORY_TOKEN,
    )


__all__ = [
    "MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_CHILD_MATERIALIZED_BONDS",
    "MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_COMPONENT_ATOM_ROWS",
    "MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_COMPONENT_BOND_ROWS",
    "MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_COMPONENT_ROWS",
    "MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_INPUT_BYTES",
    "MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_OUTPUT_BYTES",
    "MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_OUTPUT_LINE_CHARS",
    "MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_PROJECTION_BYTES",
    "MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_SOURCE_ID_BYTES",
    "MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_SEQUENCE_ROWS",
    "MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_TOKEN_CHARS",
    "MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_CHEM_COMP_ATOM_HEADERS",
    "MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_ENVELOPE_VERSION",
    "MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_PARSER_NAME",
    "MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_PARSER_VERSION",
    "MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_PROFILE_ID",
    "MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_PROJECTION_SCHEMA_ID",
    "MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_ROUND_TRIP_REPORT_SCHEMA_ID",
    "MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_SCOPE",
    "MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_SOURCE_BINDING_SCHEMA_ID",
    "MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_STATE_SCHEMA_ID",
    "MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_WRITER_VERSION",
    "MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_WRITE_RECEIPT_SCHEMA_ID",
    "MMCIF_POLYMER_TERMINAL_LEAVING_POLICY_SCHEMA_ID",
    "MMCIF_POLYMER_TERMINAL_LEAVING_RULES_SCHEMA_ID",
    "MMCIF_POLYMER_TERMINAL_LEAVING_RULES_SHA256",
    "MmcifPolymerComponentTerminalLeavingAtomAnnotation",
    "MmcifPolymerComponentTerminalLeavingPolicyError",
    "MmcifPolymerComponentTerminalLeavingPolicyIngestResult",
    "MmcifPolymerComponentTerminalLeavingPolicyRoundTripReport",
    "MmcifPolymerComponentTerminalLeavingPolicyRoundTripResult",
    "MmcifPolymerComponentTerminalLeavingPolicyWriteReceipt",
    "MmcifPolymerComponentTerminalLeavingPolicyWriteResult",
    "MmcifPolymerSequenceBoundary",
    "MmcifPolymerTerminalLeavingPolicyReport",
    "analyze_mmcif_polymer_terminal_leaving_policy",
    "emit_mmcif_polymer_component_terminal_leaving_policy",
    "mmcif_polymer_component_terminal_leaving_policy_projection_sha256",
    "mmcif_polymer_component_terminal_leaving_policy_state_sha256",
    "mmcif_polymer_terminal_leaving_rules_bytes",
    "parse_mmcif_polymer_component_terminal_leaving_policy",
    "round_trip_mmcif_polymer_component_terminal_leaving_policy_source",
    "serialize_mmcif_polymer_component_terminal_leaving_policy",
    "write_mmcif_polymer_component_terminal_leaving_policy",
]
