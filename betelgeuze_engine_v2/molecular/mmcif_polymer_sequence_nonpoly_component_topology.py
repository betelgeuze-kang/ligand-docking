"""Strict nine-category mmCIF sequence/component composition envelope.

This opt-in envelope composes, without changing either child implementation,
the six-category polymer-sequence/nonpoly-identity contract and the
eight-category nonpoly component-topology contract.  The component child owns
the detached molecular system.  The polymer sequence remains ordered source
evidence only.

The composition is accepted only when both children independently accept
their exact projections and their shared nonpoly carrier state and canonical
shared loops agree byte-for-byte.  No polymer template, chemistry,
preparation, parameterability, physics, runtime, or scientific claim is
promoted by this representation contract.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from typing import Any, Mapping
import weakref

from .mmcif_nonpoly_component_topology import (
    MMCIF_NONPOLY_COMPONENT_TOPOLOGY_CHEM_COMP_ATOM_HEADERS,
    MMCIF_NONPOLY_COMPONENT_TOPOLOGY_CHEM_COMP_BOND_HEADERS,
    MMCIF_NONPOLY_COMPONENT_TOPOLOGY_CHEM_COMP_HEADERS,
    MmcifNonpolyComponentTopologyError,
    MmcifNonpolyComponentTopologyIngestResult,
    parse_mmcif_nonpoly_component_topology,
    write_mmcif_nonpoly_component_topology,
)
from .mmcif_nonpoly_identity import write_mmcif_nonpoly_identity
from .mmcif_polymer_sequence import (
    MMCIF_ENTITY_POLY_SEQ_HEADERS,
    MmcifPolymerSequenceError,
    MmcifPolymerSequenceIngestResult,
    MmcifPolymerSequenceRow,
    emit_mmcif_polymer_sequence,
    parse_mmcif_polymer_sequence,
)
from .mmcif_syntax import CifBlock, CifLoop, CifSyntaxError, CifToken, parse_cif_block
from .models import AllAtomSystem


MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_ENVELOPE_VERSION = "1.0.0"
MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_PARSER_VERSION = "1.0.0"
MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_WRITER_VERSION = "1.0.0"
MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_PARSER_NAME = (
    "betelgeuze_engine_v2.molecular."
    "mmcif_polymer_sequence_nonpoly_component_topology."
    "parse_mmcif_polymer_sequence_nonpoly_component_topology"
)
MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_PROFILE_ID = (
    "strict_mmcif_polymer_sequence_nonpoly_component_topology_"
    "composition_envelope/1.0.0"
)
MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_STATE_SCHEMA_ID = (
    "betelgeuze.mmcif_polymer_sequence_nonpoly_component_topology_state/1.0.0"
)
MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_SOURCE_BINDING_SCHEMA_ID = (
    "betelgeuze.mmcif_polymer_sequence_nonpoly_component_topology_source_binding/1.0.0"
)
MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_WRITE_RECEIPT_SCHEMA_ID = (
    "betelgeuze.mmcif_polymer_sequence_nonpoly_component_topology_write_receipt/1.0.0"
)
MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_ROUND_TRIP_REPORT_SCHEMA_ID = (
    "betelgeuze."
    "mmcif_polymer_sequence_nonpoly_component_topology_round_trip_report/1.0.0"
)

MAX_MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_INPUT_BYTES = 64 * 1024 * 1024
MAX_MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_OUTPUT_BYTES = 64 * 1024 * 1024
MAX_MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_TOKEN_CHARS = 2_048
MAX_MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_SOURCE_ID_BYTES = 4_096
MAX_MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_OUTPUT_LINE_CHARS = 2_048

_ENTITY_HEADERS = ("_entity.id", "_entity.type")
_STRUCT_ASYM_HEADERS = ("_struct_asym.id", "_struct_asym.entity_id")
_ENTITY_NONPOLY_HEADERS = (
    ("_pdbx_entity_nonpoly.entity_id", "_pdbx_entity_nonpoly.comp_id"),
    (
        "_pdbx_entity_nonpoly.entity_id",
        "_pdbx_entity_nonpoly.name",
        "_pdbx_entity_nonpoly.comp_id",
    ),
)
_NONPOLY_SCHEME_HEADERS = (
    "_pdbx_nonpoly_scheme.asym_id",
    "_pdbx_nonpoly_scheme.entity_id",
    "_pdbx_nonpoly_scheme.mon_id",
    "_pdbx_nonpoly_scheme.ndb_seq_num",
    "_pdbx_nonpoly_scheme.pdb_seq_num",
    "_pdbx_nonpoly_scheme.auth_seq_num",
    "_pdbx_nonpoly_scheme.pdb_mon_id",
    "_pdbx_nonpoly_scheme.auth_mon_id",
    "_pdbx_nonpoly_scheme.pdb_strand_id",
    "_pdbx_nonpoly_scheme.pdb_ins_code",
)
_ATOM_SITE_HEADERS = (
    "_atom_site.group_pdb",
    "_atom_site.id",
    "_atom_site.type_symbol",
    "_atom_site.label_atom_id",
    "_atom_site.label_alt_id",
    "_atom_site.label_comp_id",
    "_atom_site.label_asym_id",
    "_atom_site.label_entity_id",
    "_atom_site.label_seq_id",
    "_atom_site.pdbx_pdb_ins_code",
    "_atom_site.cartn_x",
    "_atom_site.cartn_y",
    "_atom_site.cartn_z",
    "_atom_site.occupancy",
    "_atom_site.b_iso_or_equiv",
    "_atom_site.pdbx_formal_charge",
    "_atom_site.auth_seq_id",
    "_atom_site.auth_comp_id",
    "_atom_site.auth_asym_id",
    "_atom_site.auth_atom_id",
    "_atom_site.pdbx_pdb_model_num",
)
_CATEGORY_ORDER = (
    "_entity",
    "_struct_asym",
    "_entity_poly_seq",
    "_chem_comp",
    "_chem_comp_atom",
    "_chem_comp_bond",
    "_pdbx_entity_nonpoly",
    "_pdbx_nonpoly_scheme",
    "_atom_site",
)
_COMPONENT_CHILD_ORDER = (
    "_entity",
    "_struct_asym",
    "_chem_comp",
    "_chem_comp_atom",
    "_chem_comp_bond",
    "_pdbx_entity_nonpoly",
    "_pdbx_nonpoly_scheme",
    "_atom_site",
)
_POLYMER_CHILD_ORDER = (
    "_entity",
    "_struct_asym",
    "_entity_poly_seq",
    "_pdbx_entity_nonpoly",
    "_pdbx_nonpoly_scheme",
    "_atom_site",
)
_SHARED_ORDER = (
    "_entity",
    "_struct_asym",
    "_pdbx_entity_nonpoly",
    "_pdbx_nonpoly_scheme",
    "_atom_site",
)
_HEADERS: dict[str, tuple[str, ...] | tuple[tuple[str, ...], ...]] = {
    "_entity": _ENTITY_HEADERS,
    "_struct_asym": _STRUCT_ASYM_HEADERS,
    "_entity_poly_seq": MMCIF_ENTITY_POLY_SEQ_HEADERS,
    "_chem_comp": MMCIF_NONPOLY_COMPONENT_TOPOLOGY_CHEM_COMP_HEADERS,
    "_chem_comp_atom": MMCIF_NONPOLY_COMPONENT_TOPOLOGY_CHEM_COMP_ATOM_HEADERS,
    "_chem_comp_bond": MMCIF_NONPOLY_COMPONENT_TOPOLOGY_CHEM_COMP_BOND_HEADERS,
    "_pdbx_entity_nonpoly": _ENTITY_NONPOLY_HEADERS,
    "_pdbx_nonpoly_scheme": _NONPOLY_SCHEME_HEADERS,
    "_atom_site": _ATOM_SITE_HEADERS,
}
_FACTORY_TOKEN = object()
_FACTORY_ANCHORS: dict[int, tuple[weakref.ReferenceType[Any], bytes]] = {}
_INGEST_STATE_ANCHORS: dict[int, tuple[weakref.ReferenceType[Any], "_ParsedState"]] = {}

_FALSE_AUTHORITY_FIELDS = (
    "source_authenticated",
    "new_system_parser_pedigree_introduced",
    "auth_label_equivalence_inferred",
    "reference_sequence_equivalence_assessed",
    "coordinate_observation_completeness_assessed",
    "polymer_templates_supported",
    "polymer_template_chemistry_supported",
    "polymer_template_interpreted",
    "polymer_chemistry_interpreted",
    "modified_residue_identity_assessed",
    "microheterogeneity_interpreted",
    "independent_chemistry_established",
    "independent_valence_established",
    "independent_aromaticity_established",
    "independent_stereo_established",
    "chemistry_inferred",
    "chemistry_interpreted",
    "generic_chemistry_supported",
    "role_assignment_interpreted",
    "bond_topology_interpreted_beyond_component_child",
    "struct_conn_interpreted",
    "general_struct_conn_supported",
    "general_struct_conn_interpreted",
    "inter_residue_bonds_interpreted",
    "inter_residue_bonds_supported",
    "cross_component_bonds_interpreted",
    "cross_component_bonds_supported",
    "coordination_interpreted",
    "charge_interpreted_beyond_component_child",
    "protonation_interpreted",
    "tautomer_interpreted",
    "missing_residue_fact_claimed",
    "missing_residue_fact_established",
    "sequence_completeness_claimed",
    "sequence_completeness_assessed",
    "altloc_composition_supported",
    "assembly_composition_supported",
    "biological_assembly_composition_supported",
    "missingness_composition_supported",
    "cell_composition_supported",
    "multimodel_composition_supported",
    "preparation_ready",
    "generic_preparation_ready",
    "generic_molecular_preparation_ready",
    "global_preparation_ready",
    "global_molecular_preparation_ready",
    "parameterability_assessed",
    "physics_supported",
    "runtime_eligible",
    "simulation_ready",
    "execution_authorized",
    "claim_safe",
    "general_mmcif_topology_complete",
    "general_mmcif_round_trip_evidence_ready",
    "all_format_round_trip_evidence_ready",
    "v2_1_complete",
    "base_system_snapshot_equality_required",
)


class MmcifPolymerSequenceNonpolyComponentTopologyError(ValueError):
    """Privacy-safe failure for the exact composition envelope."""

    def __init__(
        self, code: str, message: str, *, line_number: int | None = None
    ) -> None:
        self.code = str(code)
        self.detail = str(message)
        self.line_number = None if line_number is None else int(line_number)
        suffix = "" if self.line_number is None else f" at line {self.line_number}"
        super().__init__(
            "mmcif_polymer_sequence_nonpoly_component_topology:"
            f"{self.code}{suffix}: {self.detail}"
        )


def _canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _authority_false_document() -> dict[str, bool]:
    return {field_name: False for field_name in _FALSE_AUTHORITY_FIELDS}


def _register_anchor(value: Any, access_binding: bytes) -> None:
    if type(access_binding) is not bytes:
        raise TypeError("factory access binding must be exact bytes")
    key = id(value)

    def discard(reference: weakref.ReferenceType[Any]) -> None:
        current = _FACTORY_ANCHORS.get(key)
        if current is not None and current[0] is reference:
            _FACTORY_ANCHORS.pop(key, None)

    reference = weakref.ref(value, discard)
    _FACTORY_ANCHORS[key] = (reference, access_binding)


def _validate_anchor(value: Any, current_access_binding: bytes) -> None:
    current = _FACTORY_ANCHORS.get(id(value))
    stored = getattr(value, "_access_binding_bytes", None)
    if (
        type(current_access_binding) is not bytes
        or current is None
        or current[0]() is not value
        or type(current[1]) is not bytes
        or type(stored) is not bytes
        or stored is not current[1]
        or current_access_binding != current[1]
    ):
        raise ValueError("artifact has no live factory access anchor")


def _register_ingest_state_anchor(value: Any, state: "_ParsedState") -> None:
    if type(state) is not _ParsedState:
        raise TypeError("ingest state anchor requires the exact private state")
    key = id(value)

    def discard(reference: weakref.ReferenceType[Any]) -> None:
        current = _INGEST_STATE_ANCHORS.get(key)
        if current is not None and current[0] is reference:
            _INGEST_STATE_ANCHORS.pop(key, None)

    reference = weakref.ref(value, discard)
    _INGEST_STATE_ANCHORS[key] = (reference, state)


def _ingest_state_anchor(value: Any) -> "_ParsedState":
    current = _INGEST_STATE_ANCHORS.get(id(value))
    if (
        current is None
        or current[0]() is not value
        or type(current[1]) is not _ParsedState
    ):
        raise ValueError("ingest has no live factory state anchor")
    return current[1]


def _parse_block(data: bytes) -> CifBlock:
    if type(data) is not bytes:
        raise TypeError("mmCIF composition input must be bytes")
    if not data:
        raise MmcifPolymerSequenceNonpolyComponentTopologyError(
            "empty_input", "input is empty"
        )
    if len(data) > MAX_MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_INPUT_BYTES:
        raise MmcifPolymerSequenceNonpolyComponentTopologyError(
            "input_too_large", "input exceeds the exact composition byte cap"
        )
    try:
        text = data.decode("ascii")
    except UnicodeDecodeError:
        raise MmcifPolymerSequenceNonpolyComponentTopologyError(
            "non_ascii_input", "the exact composition requires CIF 1.1 ASCII"
        ) from None
    try:
        return parse_cif_block(text)
    except CifSyntaxError as exc:
        raise MmcifPolymerSequenceNonpolyComponentTopologyError(
            "invalid_cif_syntax",
            "input is outside the exact single-block CIF grammar",
            line_number=exc.line_number,
        ) from None


def _loop_for(block: CifBlock, category: str) -> CifLoop:
    scalars = [
        name for name in block.scalar_values if name.split(".", 1)[0] == category
    ]
    loops = [loop for loop in block.loops if category in loop.categories]
    if scalars or len(loops) != 1 or loops[0].categories != (category,):
        raise MmcifPolymerSequenceNonpolyComponentTopologyError(
            "unsupported_category_representation",
            "each selected category must occur in one category-local loop",
        )
    return loops[0]


def _validate_surface(block: CifBlock) -> dict[str, CifLoop]:
    if set(block.categories) != set(_CATEGORY_ORDER):
        raise MmcifPolymerSequenceNonpolyComponentTopologyError(
            "unsupported_category_surface",
            "input categories must exactly match the nine-category composition",
        )
    loops = {category: _loop_for(block, category) for category in _CATEGORY_ORDER}
    for category, loop in loops.items():
        expected = _HEADERS[category]
        valid = (
            loop.tags in expected
            if category == "_pdbx_entity_nonpoly"
            else loop.tags == expected
        )
        if not valid:
            raise MmcifPolymerSequenceNonpolyComponentTopologyError(
                "unsupported_category_headers",
                "selected category headers are outside the exact composition",
                line_number=loop.line_number,
            )
        for row in loop.rows:
            for token in row:
                if (
                    len(token.value)
                    > MAX_MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_TOKEN_CHARS
                ):
                    raise MmcifPolymerSequenceNonpolyComponentTopologyError(
                        "token_too_long",
                        "selected source token exceeds the composition cap",
                        line_number=token.line_number,
                    )
    return loops


def _token_text(token: CifToken) -> str:
    if token.multiline:
        raise MmcifPolymerSequenceNonpolyComponentTopologyError(
            "unsupported_multiline_token",
            "multiline tokens are outside the exact composition",
            line_number=token.line_number,
        )
    if not token.quoted:
        return token.value
    if "'" not in token.value:
        return f"'{token.value}'"
    if '"' not in token.value:
        return f'"{token.value}"'
    raise MmcifPolymerSequenceNonpolyComponentTopologyError(
        "unsupported_quoted_token",
        "a quoted token cannot be emitted in the exact single-line profile",
        line_number=token.line_number,
    )


def _emit_loop(loop: CifLoop) -> bytes:
    lines = ["loop_", *loop.tags]
    for row in loop.rows:
        values = tuple(_token_text(token) for token in row)
        joined = " ".join(values)
        lines.extend(
            (joined,)
            if len(joined)
            <= MAX_MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_OUTPUT_LINE_CHARS
            else values
        )
    lines.append("#")
    return ("\n".join(lines) + "\n").encode("ascii")


def _emit_source(
    block_name: str,
    loops: Mapping[str, CifLoop],
    order: tuple[str, ...],
) -> bytes:
    return b"".join(
        (
            f"data_{block_name}\n#\n".encode("ascii"),
            *(_emit_loop(loops[category]) for category in order),
        )
    )


def _canonical_loops(data: bytes) -> tuple[CifBlock, dict[str, CifLoop]]:
    block = _parse_block(data)
    return block, {
        category: _loop_for(block, category) for category in block.categories
    }


def _child_summary(
    component: MmcifNonpolyComponentTopologyIngestResult,
    polymer: MmcifPolymerSequenceIngestResult,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    component_carrier = component.carrier_ingest
    polymer_carrier = polymer.nonpoly_ingest
    if polymer.carrier_kind != "mmcif_nonpoly_identity" or polymer_carrier is None:
        raise MmcifPolymerSequenceNonpolyComponentTopologyError(
            "polymer_child_missing_nonpoly_carrier",
            "the polymer child must contain the exact nonpoly identity carrier",
        )
    shared_fields = (
        "data_block_name",
        "identity_projection_sha256",
        "record_state_sha256",
        "base_topology_sha256",
        "base_representable_state_sha256",
    )
    for field_name in shared_fields:
        if getattr(component_carrier, field_name) != getattr(
            polymer_carrier, field_name
        ):
            raise MmcifPolymerSequenceNonpolyComponentTopologyError(
                "crosswired_child_carrier",
                "child nonpoly identity carriers do not describe the same base state",
            )
    if (
        polymer.data_block_name != component_carrier.data_block_name
        or polymer.base_topology_sha256 != component_carrier.base_topology_sha256
        or polymer.base_representable_state_sha256
        != component_carrier.base_representable_state_sha256
        or polymer.nonpoly_identity_projection_sha256
        != component_carrier.identity_projection_sha256
        or polymer.nonpoly_identity_record_state_sha256
        != component_carrier.record_state_sha256
        or polymer.source_id_sha256 != component.source_id_sha256
    ):
        raise MmcifPolymerSequenceNonpolyComponentTopologyError(
            "crosswired_child_state",
            "child state bindings do not share one source and nonpoly base",
        )
    component_nonpoly_output = write_mmcif_nonpoly_identity(component_carrier).payload
    polymer_nonpoly_output = write_mmcif_nonpoly_identity(polymer_carrier).payload
    if component_nonpoly_output != polymer_nonpoly_output:
        raise MmcifPolymerSequenceNonpolyComponentTopologyError(
            "canonical_nonpoly_carrier_mismatch",
            "child canonical nonpoly writer payloads differ byte-for-byte",
        )
    component_document = {
        "component_projection_sha256": component.component_projection_sha256,
        "component_topology_state_sha256": component.topology_state_sha256,
        "augmented_topology_sha256": component.augmented_topology_sha256,
    }
    polymer_document = {
        "polymer_sequence_projection_sha256": (
            polymer.polymer_sequence_projection_sha256
        ),
        "polymer_sequence_record_state_sha256": polymer.record_state_sha256,
    }
    shared_document = {
        "data_block_name": polymer.data_block_name,
        "nonpoly_identity_projection_sha256": (
            component_carrier.identity_projection_sha256
        ),
        "nonpoly_identity_record_state_sha256": component_carrier.record_state_sha256,
        "base_topology_sha256": component_carrier.base_topology_sha256,
        "base_representable_state_sha256": (
            component_carrier.base_representable_state_sha256
        ),
        "canonical_nonpoly_writer_payload_sha256": _sha256_bytes(
            component_nonpoly_output
        ),
    }
    return component_document, polymer_document, shared_document


def _bind_canonical_shared_loops(
    component_output: bytes, polymer_output: bytes
) -> tuple[dict[str, str], dict[str, CifLoop], dict[str, CifLoop]]:
    component_block, component_loops = _canonical_loops(component_output)
    polymer_block, polymer_loops = _canonical_loops(polymer_output)
    if component_block.name != polymer_block.name:
        raise MmcifPolymerSequenceNonpolyComponentTopologyError(
            "crosswired_child_block", "child canonical data blocks differ"
        )
    digests: dict[str, str] = {}
    for category in _SHARED_ORDER:
        component_bytes = _emit_loop(component_loops[category])
        polymer_bytes = _emit_loop(polymer_loops[category])
        if component_bytes != polymer_bytes:
            raise MmcifPolymerSequenceNonpolyComponentTopologyError(
                "canonical_shared_loop_mismatch",
                "child canonical shared loops differ byte-for-byte",
            )
        digests[category] = _sha256_bytes(component_bytes)
    return digests, component_loops, polymer_loops


@dataclass(frozen=True)
class _ParsedState:
    full_source: bytes
    source_id: str
    component_source: bytes
    polymer_source: bytes
    canonical_output: bytes
    block_name: str
    component_document_bytes: bytes
    polymer_document_bytes: bytes
    shared_document_bytes: bytes
    shared_loop_document_bytes: bytes
    record_state_bytes: bytes
    source_binding_bytes: bytes


def _record_state_document(state: _ParsedState) -> dict[str, Any]:
    return json.loads(state.record_state_bytes.decode("ascii"))


def _source_binding_document(state: _ParsedState) -> dict[str, Any]:
    return json.loads(state.source_binding_bytes.decode("ascii"))


def _build_state(data: bytes, *, source_id: str) -> _ParsedState:
    if type(source_id) is not str:
        raise TypeError("source_id must be a string")
    try:
        source_id_bytes = source_id.encode("utf-8")
    except UnicodeEncodeError:
        raise MmcifPolymerSequenceNonpolyComponentTopologyError(
            "invalid_source_id", "source identity must contain Unicode scalar values"
        ) from None
    if len(source_id_bytes) > (
        MAX_MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_SOURCE_ID_BYTES
    ):
        raise MmcifPolymerSequenceNonpolyComponentTopologyError(
            "source_id_too_long", "source identity exceeds the composition cap"
        )
    block = _parse_block(data)
    loops = _validate_surface(block)
    component_source = _emit_source(block.name, loops, _COMPONENT_CHILD_ORDER)
    polymer_source = _emit_source(block.name, loops, _POLYMER_CHILD_ORDER)
    try:
        component = parse_mmcif_nonpoly_component_topology(
            component_source, source_id=source_id
        )
    except MmcifNonpolyComponentTopologyError as exc:
        raise MmcifPolymerSequenceNonpolyComponentTopologyError(
            "component_child_rejected",
            f"the exact component child rejected its projection ({exc.code})",
        ) from None
    try:
        polymer = parse_mmcif_polymer_sequence(polymer_source, source_id=source_id)
    except MmcifPolymerSequenceError as exc:
        raise MmcifPolymerSequenceNonpolyComponentTopologyError(
            "polymer_child_rejected",
            f"the exact polymer child rejected its projection ({exc.code})",
        ) from None
    component_write = write_mmcif_nonpoly_component_topology(component)
    polymer_write = emit_mmcif_polymer_sequence(polymer)
    component_document, polymer_document, shared_document = _child_summary(
        component, polymer
    )
    shared_loop_document, component_loops, polymer_loops = _bind_canonical_shared_loops(
        component_write.payload, polymer_write.payload
    )
    canonical_loops = dict(component_loops)
    canonical_loops["_entity_poly_seq"] = polymer_loops["_entity_poly_seq"]
    canonical_output = _emit_source(block.name, canonical_loops, _CATEGORY_ORDER)
    if len(canonical_output) > (
        MAX_MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_OUTPUT_BYTES
    ):
        raise MmcifPolymerSequenceNonpolyComponentTopologyError(
            "output_too_large", "canonical composition exceeds the output byte cap"
        )
    component_bytes = _canonical_json_bytes(component_document)
    polymer_bytes = _canonical_json_bytes(polymer_document)
    shared_bytes = _canonical_json_bytes(shared_document)
    shared_loop_bytes = _canonical_json_bytes(shared_loop_document)
    state_document = {
        "schema_id": (
            MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_STATE_SCHEMA_ID
        ),
        "envelope_version": (
            MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_ENVELOPE_VERSION
        ),
        "parser_version": (
            MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_PARSER_VERSION
        ),
        "writer_version": (
            MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_WRITER_VERSION
        ),
        "profile_id": MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_PROFILE_ID,
        "component_child": component_document,
        "polymer_child": polymer_document,
        "shared_nonpoly_base": shared_document,
        "canonical_shared_loop_sha256": shared_loop_document,
        "system_owner": "mmcif_nonpoly_component_topology_child",
        "polymer_sequence_semantics": "source_evidence_only",
    }
    state_bytes = _canonical_json_bytes(state_document)
    binding_document = {
        "schema_id": (
            MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_SOURCE_BINDING_SCHEMA_ID
        ),
        "envelope_version": (
            MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_ENVELOPE_VERSION
        ),
        "profile_id": MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_PROFILE_ID,
        "full_nine_category_source_sha256": _sha256_bytes(data),
        "component_child_source_sha256": _sha256_bytes(component_source),
        "polymer_child_source_sha256": _sha256_bytes(polymer_source),
        "component_child_source_binding_sha256": component.source_binding_sha256,
        "polymer_child_source_binding_sha256": polymer.source_binding_sha256,
        "component_augmented_system_snapshot_sha256": (
            component.augmented_system_snapshot_sha256
        ),
        "component_child_canonical_output_sha256": _sha256_bytes(
            component_write.payload
        ),
        "polymer_child_canonical_output_sha256": _sha256_bytes(polymer_write.payload),
        "canonical_output_sha256": _sha256_bytes(canonical_output),
        "record_state_sha256": _sha256_bytes(state_bytes),
        "source_id_sha256": _sha256_bytes(source_id_bytes),
        "data_block_name_sha256": _sha256_bytes(block.name.encode("ascii")),
    }
    return _ParsedState(
        full_source=data,
        source_id=source_id,
        component_source=component_source,
        polymer_source=polymer_source,
        canonical_output=canonical_output,
        block_name=block.name,
        component_document_bytes=component_bytes,
        polymer_document_bytes=polymer_bytes,
        shared_document_bytes=shared_bytes,
        shared_loop_document_bytes=shared_loop_bytes,
        record_state_bytes=state_bytes,
        source_binding_bytes=_canonical_json_bytes(binding_document),
    )


def _ingest_access_document(
    value: "MmcifPolymerSequenceNonpolyComponentTopologyIngestResult",
) -> dict[str, Any]:
    byte_fields = (
        "_full_source",
        "_component_source",
        "_polymer_source",
        "_canonical_output",
        "_component_document_bytes",
        "_polymer_document_bytes",
        "_shared_document_bytes",
        "_shared_loop_document_bytes",
        "_record_state_bytes",
        "_source_binding_bytes",
    )
    document: dict[str, Any] = {
        "artifact_type": ("MmcifPolymerSequenceNonpolyComponentTopologyIngestResult"),
        "self_object_id": id(value),
        "source_id_object_id": id(value._source_id),
        "source_id_sha256": _sha256_bytes(value._source_id.encode("utf-8")),
        "block_name": value._block_name,
    }
    for name in byte_fields:
        payload = getattr(value, name)
        if type(payload) is not bytes:
            raise TypeError("ingest payload fields must be exact bytes")
        document[f"{name[1:]}_object_id"] = id(payload)
        document[f"{name[1:]}_sha256"] = _sha256_bytes(payload)
    return document


@dataclass(frozen=True, init=False)
class MmcifPolymerSequenceNonpolyComponentTopologyIngestResult:
    """Externally anchored result for one exact nine-category composition."""

    _full_source: bytes = field(repr=False)
    _source_id: str = field(repr=False)
    _component_source: bytes = field(repr=False)
    _polymer_source: bytes = field(repr=False)
    _canonical_output: bytes = field(repr=False)
    _block_name: str
    _component_document_bytes: bytes = field(repr=False)
    _polymer_document_bytes: bytes = field(repr=False)
    _shared_document_bytes: bytes = field(repr=False)
    _shared_loop_document_bytes: bytes = field(repr=False)
    _record_state_bytes: bytes = field(repr=False)
    _source_binding_bytes: bytes = field(repr=False)
    _access_binding_bytes: bytes = field(repr=False)

    def __init__(
        self, state: _ParsedState, *, _factory_token: object | None = None
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise TypeError(
                "MmcifPolymerSequenceNonpolyComponentTopologyIngestResult "
                "is factory-only"
            )
        if type(state) is not _ParsedState:
            raise TypeError("composition ingest requires exact private parsed state")
        for name in (
            "full_source",
            "source_id",
            "component_source",
            "polymer_source",
            "canonical_output",
            "block_name",
            "component_document_bytes",
            "polymer_document_bytes",
            "shared_document_bytes",
            "shared_loop_document_bytes",
            "record_state_bytes",
            "source_binding_bytes",
        ):
            object.__setattr__(self, f"_{name}", getattr(state, name))
        access = _canonical_json_bytes(_ingest_access_document(self))
        object.__setattr__(self, "_access_binding_bytes", access)
        _register_anchor(self, access)
        _register_ingest_state_anchor(self, state)

    @property
    def system(self) -> AllAtomSystem:
        """Return a detached system owned by the component-topology child."""

        _validate_ingest(self)
        return parse_mmcif_nonpoly_component_topology(
            self._component_source, source_id=self._source_id
        ).system

    @property
    def component_ingest(self) -> MmcifNonpolyComponentTopologyIngestResult:
        """Return a fresh detached exact component child."""

        _validate_ingest(self)
        return parse_mmcif_nonpoly_component_topology(
            self._component_source, source_id=self._source_id
        )

    @property
    def polymer_ingest(self) -> MmcifPolymerSequenceIngestResult:
        """Return a fresh detached exact polymer-sequence child."""

        _validate_ingest(self)
        return parse_mmcif_polymer_sequence(
            self._polymer_source, source_id=self._source_id
        )

    @property
    def sequence_rows(self) -> tuple[MmcifPolymerSequenceRow, ...]:
        return self.polymer_ingest.sequence_rows

    @property
    def data_block_name(self) -> str:
        _validate_ingest(self)
        return self._block_name

    @property
    def full_source_sha256(self) -> str:
        return str(
            _source_binding_document(_validate_ingest(self))[
                "full_nine_category_source_sha256"
            ]
        )

    @property
    def canonical_output_sha256(self) -> str:
        return str(
            _source_binding_document(_validate_ingest(self))["canonical_output_sha256"]
        )

    @property
    def record_state_sha256(self) -> str:
        return _sha256_bytes(_validate_ingest(self).record_state_bytes)

    @property
    def source_binding_sha256(self) -> str:
        return _sha256_bytes(_validate_ingest(self).source_binding_bytes)

    @property
    def component_topology_state_sha256(self) -> str:
        return str(
            _record_state_document(_validate_ingest(self))["component_child"][
                "component_topology_state_sha256"
            ]
        )

    @property
    def component_projection_sha256(self) -> str:
        return str(
            _record_state_document(_validate_ingest(self))["component_child"][
                "component_projection_sha256"
            ]
        )

    @property
    def component_augmented_topology_sha256(self) -> str:
        return str(
            _record_state_document(_validate_ingest(self))["component_child"][
                "augmented_topology_sha256"
            ]
        )

    @property
    def augmented_topology_sha256(self) -> str:
        return self.component_augmented_topology_sha256

    @property
    def polymer_sequence_record_state_sha256(self) -> str:
        return str(
            _record_state_document(_validate_ingest(self))["polymer_child"][
                "polymer_sequence_record_state_sha256"
            ]
        )

    @property
    def polymer_sequence_projection_sha256(self) -> str:
        return str(
            _record_state_document(_validate_ingest(self))["polymer_child"][
                "polymer_sequence_projection_sha256"
            ]
        )

    @property
    def nonpoly_identity_projection_sha256(self) -> str:
        return str(
            _record_state_document(_validate_ingest(self))["shared_nonpoly_base"][
                "nonpoly_identity_projection_sha256"
            ]
        )

    @property
    def nonpoly_identity_record_state_sha256(self) -> str:
        return str(
            _record_state_document(_validate_ingest(self))["shared_nonpoly_base"][
                "nonpoly_identity_record_state_sha256"
            ]
        )

    @property
    def component_system_snapshot_sha256(self) -> str:
        return str(
            _source_binding_document(_validate_ingest(self))[
                "component_augmented_system_snapshot_sha256"
            ]
        )

    @property
    def base_topology_sha256(self) -> str:
        return str(
            _record_state_document(_validate_ingest(self))["shared_nonpoly_base"][
                "base_topology_sha256"
            ]
        )

    @property
    def base_representable_state_sha256(self) -> str:
        return str(
            _record_state_document(_validate_ingest(self))["shared_nonpoly_base"][
                "base_representable_state_sha256"
            ]
        )

    @property
    def source_id_sha256(self) -> str:
        return str(_source_binding_document(_validate_ingest(self))["source_id_sha256"])

    def to_dict(self) -> dict[str, Any]:
        state = _validate_ingest(self)
        document = dict(_record_state_document(state))
        source_binding = _source_binding_document(state)
        document.update(
            {
                key: value
                for key, value in source_binding.items()
                if key not in {"schema_id", "envelope_version", "profile_id"}
            }
        )
        document["source_binding_schema_id"] = source_binding["schema_id"]
        document["record_state_sha256"] = _sha256_bytes(state.record_state_bytes)
        document["source_binding_sha256"] = _sha256_bytes(state.source_binding_bytes)
        document["polymer_sequence_row_count"] = len(self.sequence_rows)
        document["component_child_and_polymer_child_cross_bound"] = True
        document["canonical_shared_loops_byte_equal"] = True
        document.update(_authority_false_document())
        return document


def _state_from_ingest(
    value: MmcifPolymerSequenceNonpolyComponentTopologyIngestResult,
) -> _ParsedState:
    return _ParsedState(
        full_source=value._full_source,
        source_id=value._source_id,
        component_source=value._component_source,
        polymer_source=value._polymer_source,
        canonical_output=value._canonical_output,
        block_name=value._block_name,
        component_document_bytes=value._component_document_bytes,
        polymer_document_bytes=value._polymer_document_bytes,
        shared_document_bytes=value._shared_document_bytes,
        shared_loop_document_bytes=value._shared_loop_document_bytes,
        record_state_bytes=value._record_state_bytes,
        source_binding_bytes=value._source_binding_bytes,
    )


def _validate_ingest(
    value: MmcifPolymerSequenceNonpolyComponentTopologyIngestResult,
) -> _ParsedState:
    if type(value) is not MmcifPolymerSequenceNonpolyComponentTopologyIngestResult:
        raise TypeError("an exact composition ingest result is required")
    try:
        stored = _state_from_ingest(value)
        _validate_anchor(value, _canonical_json_bytes(_ingest_access_document(value)))
        anchored = _ingest_state_anchor(value)
    except Exception:
        raise MmcifPolymerSequenceNonpolyComponentTopologyError(
            "stale_ingest_binding", "stored composition evidence is stale"
        ) from None
    if stored != anchored:
        raise MmcifPolymerSequenceNonpolyComponentTopologyError(
            "stale_ingest_binding", "stored composition evidence is stale"
        )
    return stored


def parse_mmcif_polymer_sequence_nonpoly_component_topology(
    data: bytes, *, source_id: str = ""
) -> MmcifPolymerSequenceNonpolyComponentTopologyIngestResult:
    """Parse the strict nine-category composition envelope."""

    return MmcifPolymerSequenceNonpolyComponentTopologyIngestResult(
        _build_state(data, source_id=source_id), _factory_token=_FACTORY_TOKEN
    )


def mmcif_polymer_sequence_nonpoly_component_topology_state_sha256(
    value: MmcifPolymerSequenceNonpolyComponentTopologyIngestResult,
) -> str:
    return _sha256_bytes(_validate_ingest(value).record_state_bytes)


def mmcif_polymer_sequence_nonpoly_component_topology_record_state_sha256(
    value: MmcifPolymerSequenceNonpolyComponentTopologyIngestResult,
) -> str:
    return mmcif_polymer_sequence_nonpoly_component_topology_state_sha256(value)


def _receipt_document_from_state(state: _ParsedState, payload: bytes) -> dict[str, Any]:
    return {
        "schema_id": (
            MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_WRITE_RECEIPT_SCHEMA_ID
        ),
        "envelope_version": (
            MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_ENVELOPE_VERSION
        ),
        "writer_version": (
            MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_WRITER_VERSION
        ),
        "profile_id": MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_PROFILE_ID,
        "input_full_source_sha256": _sha256_bytes(state.full_source),
        "input_record_state_sha256": _sha256_bytes(state.record_state_bytes),
        "input_source_binding_sha256": _sha256_bytes(state.source_binding_bytes),
        "input_component_child_source_sha256": _sha256_bytes(state.component_source),
        "input_polymer_child_source_sha256": _sha256_bytes(state.polymer_source),
        "output_source_sha256": _sha256_bytes(payload),
        "output_byte_count": len(payload),
        "data_block_name_sha256": _sha256_bytes(state.block_name.encode("ascii")),
    }


def _receipt_document(
    ingest: MmcifPolymerSequenceNonpolyComponentTopologyIngestResult,
    payload: bytes,
) -> dict[str, Any]:
    return _receipt_document_from_state(_validate_ingest(ingest), payload)


def _receipt_access_document(
    value: "MmcifPolymerSequenceNonpolyComponentTopologyWriteReceipt",
) -> dict[str, Any]:
    return {
        "artifact_type": ("MmcifPolymerSequenceNonpolyComponentTopologyWriteReceipt"),
        "self_object_id": id(value),
        "ingest_object_id": id(value._ingest),
        "payload_object_id": id(value._payload),
        "payload_sha256": _sha256_bytes(value._payload),
        "document_object_id": id(value._document_bytes),
        "document_sha256": _sha256_bytes(value._document_bytes),
    }


@dataclass(frozen=True, init=False)
class MmcifPolymerSequenceNonpolyComponentTopologyWriteReceipt:
    _ingest: MmcifPolymerSequenceNonpolyComponentTopologyIngestResult = field(
        repr=False
    )
    _payload: bytes = field(repr=False)
    _document_bytes: bytes = field(repr=False)
    _access_binding_bytes: bytes = field(repr=False)

    def __init__(
        self,
        ingest: MmcifPolymerSequenceNonpolyComponentTopologyIngestResult,
        payload: bytes,
        *,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise TypeError(
                "MmcifPolymerSequenceNonpolyComponentTopologyWriteReceipt "
                "is factory-only"
            )
        document = _receipt_document(ingest, payload)
        object.__setattr__(self, "_ingest", ingest)
        object.__setattr__(self, "_payload", payload)
        object.__setattr__(self, "_document_bytes", _canonical_json_bytes(document))
        access = _canonical_json_bytes(_receipt_access_document(self))
        object.__setattr__(self, "_access_binding_bytes", access)
        _register_anchor(self, access)

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
        document = _validate_receipt(self)
        return {**document, "receipt_sha256": self.receipt_sha256}


def _validate_receipt(
    value: MmcifPolymerSequenceNonpolyComponentTopologyWriteReceipt,
    *,
    _validated_state: _ParsedState | None = None,
) -> dict[str, Any]:
    if type(value) is not MmcifPolymerSequenceNonpolyComponentTopologyWriteReceipt:
        raise TypeError("an exact composition write receipt is required")
    try:
        _validate_anchor(value, _canonical_json_bytes(_receipt_access_document(value)))
        state = (
            _validate_ingest(value._ingest)
            if _validated_state is None
            else _validated_state
        )
        if type(state) is not _ParsedState:
            raise TypeError("validated receipt state must use the exact private type")
        expected = _receipt_document_from_state(state, value._payload)
    except Exception:
        raise MmcifPolymerSequenceNonpolyComponentTopologyError(
            "stale_write_receipt_binding", "composition write receipt is stale"
        ) from None
    if value._document_bytes != _canonical_json_bytes(expected):
        raise MmcifPolymerSequenceNonpolyComponentTopologyError(
            "stale_write_receipt_binding", "composition write receipt is stale"
        )
    return expected


def _write_result_access_document(
    value: "MmcifPolymerSequenceNonpolyComponentTopologyWriteResult",
) -> dict[str, Any]:
    return {
        "artifact_type": "MmcifPolymerSequenceNonpolyComponentTopologyWriteResult",
        "self_object_id": id(value),
        "ingest_object_id": id(value._ingest),
        "payload_object_id": id(value._payload),
        "payload_sha256": _sha256_bytes(value._payload),
        "receipt_object_id": id(value._receipt),
    }


@dataclass(frozen=True, init=False)
class MmcifPolymerSequenceNonpolyComponentTopologyWriteResult:
    _ingest: MmcifPolymerSequenceNonpolyComponentTopologyIngestResult = field(
        repr=False
    )
    _payload: bytes = field(repr=False)
    _receipt: MmcifPolymerSequenceNonpolyComponentTopologyWriteReceipt = field(
        repr=False
    )
    _access_binding_bytes: bytes = field(repr=False)

    def __init__(
        self,
        ingest: MmcifPolymerSequenceNonpolyComponentTopologyIngestResult,
        payload: bytes,
        receipt: MmcifPolymerSequenceNonpolyComponentTopologyWriteReceipt,
        *,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise TypeError(
                "MmcifPolymerSequenceNonpolyComponentTopologyWriteResult "
                "is factory-only"
            )
        if receipt._ingest is not ingest or receipt._payload is not payload:
            raise MmcifPolymerSequenceNonpolyComponentTopologyError(
                "crosswired_write_artifacts", "write artifacts are crosswired"
            )
        _validate_receipt(receipt)
        object.__setattr__(self, "_ingest", ingest)
        object.__setattr__(self, "_payload", payload)
        object.__setattr__(self, "_receipt", receipt)
        access = _canonical_json_bytes(_write_result_access_document(self))
        object.__setattr__(self, "_access_binding_bytes", access)
        _register_anchor(self, access)

    @property
    def payload(self) -> bytes:
        _validate_write_result(self)
        return self._payload

    @property
    def receipt(self) -> MmcifPolymerSequenceNonpolyComponentTopologyWriteReceipt:
        _validate_write_result(self)
        detached_ingest = parse_mmcif_polymer_sequence_nonpoly_component_topology(
            self._ingest._full_source, source_id=self._ingest._source_id
        )
        return MmcifPolymerSequenceNonpolyComponentTopologyWriteReceipt(
            detached_ingest, self._payload, _factory_token=_FACTORY_TOKEN
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
    value: MmcifPolymerSequenceNonpolyComponentTopologyWriteResult,
) -> _ParsedState:
    if type(value) is not MmcifPolymerSequenceNonpolyComponentTopologyWriteResult:
        raise TypeError("an exact composition write result is required")
    try:
        _validate_anchor(
            value, _canonical_json_bytes(_write_result_access_document(value))
        )
        state = _validate_ingest(value._ingest)
        _validate_receipt(value._receipt, _validated_state=state)
    except Exception:
        raise MmcifPolymerSequenceNonpolyComponentTopologyError(
            "stale_write_result_binding", "composition write result is stale"
        ) from None
    if (
        value._payload != state.canonical_output
        or value._receipt._ingest is not value._ingest
        or value._receipt._payload is not value._payload
    ):
        raise MmcifPolymerSequenceNonpolyComponentTopologyError(
            "stale_write_result_binding", "composition write result is stale"
        )
    return state


def write_mmcif_polymer_sequence_nonpoly_component_topology(
    value: MmcifPolymerSequenceNonpolyComponentTopologyIngestResult,
) -> MmcifPolymerSequenceNonpolyComponentTopologyWriteResult:
    """Emit and revalidate the canonical nine-category composition."""

    state = _validate_ingest(value)
    reparsed = _build_state(state.canonical_output, source_id=state.source_id)
    if (
        reparsed.record_state_bytes != state.record_state_bytes
        or reparsed.canonical_output != state.canonical_output
    ):
        raise MmcifPolymerSequenceNonpolyComponentTopologyError(
            "canonical_output_state_mismatch",
            "canonical output did not recover the bound composed state",
        )
    payload = state.canonical_output
    receipt = MmcifPolymerSequenceNonpolyComponentTopologyWriteReceipt(
        value, payload, _factory_token=_FACTORY_TOKEN
    )
    return MmcifPolymerSequenceNonpolyComponentTopologyWriteResult(
        value, payload, receipt, _factory_token=_FACTORY_TOKEN
    )


def emit_mmcif_polymer_sequence_nonpoly_component_topology(
    value: MmcifPolymerSequenceNonpolyComponentTopologyIngestResult,
) -> MmcifPolymerSequenceNonpolyComponentTopologyWriteResult:
    return write_mmcif_polymer_sequence_nonpoly_component_topology(value)


def serialize_mmcif_polymer_sequence_nonpoly_component_topology(
    value: MmcifPolymerSequenceNonpolyComponentTopologyIngestResult,
) -> bytes:
    return write_mmcif_polymer_sequence_nonpoly_component_topology(value).payload


def _report_document(
    source: MmcifPolymerSequenceNonpolyComponentTopologyIngestResult,
    write_result: MmcifPolymerSequenceNonpolyComponentTopologyWriteResult,
    reparsed: MmcifPolymerSequenceNonpolyComponentTopologyIngestResult,
    second: MmcifPolymerSequenceNonpolyComponentTopologyWriteResult,
) -> dict[str, Any]:
    source_state = _validate_write_result(write_result)
    reparsed_state = _validate_write_result(second)
    if write_result._ingest is not source or second._ingest is not reparsed:
        raise MmcifPolymerSequenceNonpolyComponentTopologyError(
            "crosswired_round_trip_artifacts", "round-trip artifacts are crosswired"
        )
    source_record = _record_state_document(source_state)
    reparsed_record = _record_state_document(reparsed_state)
    source_record_sha = _sha256_bytes(source_state.record_state_bytes)
    reparsed_record_sha = _sha256_bytes(reparsed_state.record_state_bytes)
    source_component_state = str(
        source_record["component_child"]["component_topology_state_sha256"]
    )
    reparsed_component_state = str(
        reparsed_record["component_child"]["component_topology_state_sha256"]
    )
    source_polymer_state = str(
        source_record["polymer_child"]["polymer_sequence_record_state_sha256"]
    )
    reparsed_polymer_state = str(
        reparsed_record["polymer_child"]["polymer_sequence_record_state_sha256"]
    )
    source_nonpoly_state = str(
        source_record["shared_nonpoly_base"]["nonpoly_identity_record_state_sha256"]
    )
    reparsed_nonpoly_state = str(
        reparsed_record["shared_nonpoly_base"]["nonpoly_identity_record_state_sha256"]
    )
    source_id_sha = str(_source_binding_document(source_state)["source_id_sha256"])
    reparsed_source_id_sha = str(
        _source_binding_document(reparsed_state)["source_id_sha256"]
    )
    values = {
        "schema_id": (
            MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_ROUND_TRIP_REPORT_SCHEMA_ID
        ),
        "envelope_version": (
            MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_ENVELOPE_VERSION
        ),
        "profile_id": MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_PROFILE_ID,
        "input_full_source_sha256": _sha256_bytes(source_state.full_source),
        "reparsed_full_source_sha256": _sha256_bytes(reparsed_state.full_source),
        "input_record_state_sha256": source_record_sha,
        "reparsed_record_state_sha256": reparsed_record_sha,
        "input_component_topology_state_sha256": source_component_state,
        "reparsed_component_topology_state_sha256": reparsed_component_state,
        "input_polymer_sequence_record_state_sha256": source_polymer_state,
        "reparsed_polymer_sequence_record_state_sha256": reparsed_polymer_state,
        "input_nonpoly_identity_record_state_sha256": source_nonpoly_state,
        "reparsed_nonpoly_identity_record_state_sha256": reparsed_nonpoly_state,
        "input_source_id_sha256": source_id_sha,
        "reparsed_source_id_sha256": reparsed_source_id_sha,
        "writer_receipt_sha256": _sha256_bytes(write_result._receipt._document_bytes),
        "reemitted_writer_receipt_sha256": _sha256_bytes(
            second._receipt._document_bytes
        ),
        "emitted_source_sha256": _sha256_bytes(write_result._payload),
        "reemitted_source_sha256": _sha256_bytes(second._payload),
        "record_state_equal": source_record_sha == reparsed_record_sha,
        "component_topology_state_equal": (
            source_component_state == reparsed_component_state
        ),
        "polymer_sequence_state_equal": (
            source_polymer_state == reparsed_polymer_state
        ),
        "nonpoly_identity_state_equal": (
            source_nonpoly_state == reparsed_nonpoly_state
        ),
        "source_id_equal": source_id_sha == reparsed_source_id_sha,
        "emitted_source_reparsed_exact": (
            write_result._payload == reparsed_state.full_source
        ),
        "second_emission_byte_stable": (write_result._payload == second._payload),
    }
    values["composition_round_trip_preserved"] = all(
        values[field_name]
        for field_name in (
            "record_state_equal",
            "component_topology_state_equal",
            "polymer_sequence_state_equal",
            "nonpoly_identity_state_equal",
            "source_id_equal",
            "emitted_source_reparsed_exact",
            "second_emission_byte_stable",
        )
    )
    return values


def _report_access_document(
    value: "MmcifPolymerSequenceNonpolyComponentTopologyRoundTripReport",
) -> dict[str, Any]:
    return {
        "artifact_type": (
            "MmcifPolymerSequenceNonpolyComponentTopologyRoundTripReport"
        ),
        "self_object_id": id(value),
        "source_object_id": id(value._source),
        "write_object_id": id(value._write_result),
        "reparsed_object_id": id(value._reparsed),
        "second_object_id": id(value._second),
        "document_sha256": _sha256_bytes(value._document_bytes),
    }


@dataclass(frozen=True, init=False)
class MmcifPolymerSequenceNonpolyComponentTopologyRoundTripReport:
    _source: MmcifPolymerSequenceNonpolyComponentTopologyIngestResult = field(
        repr=False
    )
    _write_result: MmcifPolymerSequenceNonpolyComponentTopologyWriteResult = field(
        repr=False
    )
    _reparsed: MmcifPolymerSequenceNonpolyComponentTopologyIngestResult = field(
        repr=False
    )
    _second: MmcifPolymerSequenceNonpolyComponentTopologyWriteResult = field(repr=False)
    _document_bytes: bytes = field(repr=False)
    _access_binding_bytes: bytes = field(repr=False)

    def __init__(
        self,
        source: MmcifPolymerSequenceNonpolyComponentTopologyIngestResult,
        write_result: MmcifPolymerSequenceNonpolyComponentTopologyWriteResult,
        reparsed: MmcifPolymerSequenceNonpolyComponentTopologyIngestResult,
        second: MmcifPolymerSequenceNonpolyComponentTopologyWriteResult,
        *,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise TypeError(
                "MmcifPolymerSequenceNonpolyComponentTopologyRoundTripReport "
                "is factory-only"
            )
        document = _report_document(source, write_result, reparsed, second)
        if document["composition_round_trip_preserved"] is not True:
            raise MmcifPolymerSequenceNonpolyComponentTopologyError(
                "round_trip_mismatch", "composed state did not round trip exactly"
            )
        object.__setattr__(self, "_source", source)
        object.__setattr__(self, "_write_result", write_result)
        object.__setattr__(self, "_reparsed", reparsed)
        object.__setattr__(self, "_second", second)
        object.__setattr__(self, "_document_bytes", _canonical_json_bytes(document))
        access = _canonical_json_bytes(_report_access_document(self))
        object.__setattr__(self, "_access_binding_bytes", access)
        _register_anchor(self, access)

    @property
    def report_sha256(self) -> str:
        _validate_report(self)
        return _sha256_bytes(self._document_bytes)

    def to_dict(self) -> dict[str, Any]:
        document = _validate_report(self)
        return {
            **document,
            "report_sha256": self.report_sha256,
            **_authority_false_document(),
        }


def _validate_report(
    value: MmcifPolymerSequenceNonpolyComponentTopologyRoundTripReport,
) -> dict[str, Any]:
    if type(value) is not MmcifPolymerSequenceNonpolyComponentTopologyRoundTripReport:
        raise TypeError("an exact composition round-trip report is required")
    try:
        _validate_anchor(value, _canonical_json_bytes(_report_access_document(value)))
        expected = _report_document(
            value._source, value._write_result, value._reparsed, value._second
        )
    except Exception:
        raise MmcifPolymerSequenceNonpolyComponentTopologyError(
            "crosswired_round_trip_artifacts", "round-trip artifacts are crosswired"
        ) from None
    if (
        value._write_result._ingest is not value._source
        or value._second._ingest is not value._reparsed
        or value._document_bytes != _canonical_json_bytes(expected)
        or expected["composition_round_trip_preserved"] is not True
    ):
        raise MmcifPolymerSequenceNonpolyComponentTopologyError(
            "crosswired_round_trip_artifacts", "round-trip artifacts are crosswired"
        )
    return expected


def _aggregate_access_document(
    value: "MmcifPolymerSequenceNonpolyComponentTopologyRoundTripResult",
) -> dict[str, Any]:
    return {
        "artifact_type": (
            "MmcifPolymerSequenceNonpolyComponentTopologyRoundTripResult"
        ),
        "self_object_id": id(value),
        "source_object_id": id(value._source),
        "write_object_id": id(value._write_result),
        "reparsed_object_id": id(value._reparsed),
        "second_object_id": id(value._second),
        "report_object_id": id(value._report),
    }


@dataclass(frozen=True, init=False)
class MmcifPolymerSequenceNonpolyComponentTopologyRoundTripResult:
    _source: MmcifPolymerSequenceNonpolyComponentTopologyIngestResult = field(
        repr=False
    )
    _write_result: MmcifPolymerSequenceNonpolyComponentTopologyWriteResult = field(
        repr=False
    )
    _reparsed: MmcifPolymerSequenceNonpolyComponentTopologyIngestResult = field(
        repr=False
    )
    _second: MmcifPolymerSequenceNonpolyComponentTopologyWriteResult = field(repr=False)
    _report: MmcifPolymerSequenceNonpolyComponentTopologyRoundTripReport = field(
        repr=False
    )
    _access_binding_bytes: bytes = field(repr=False)

    def __init__(
        self,
        source: MmcifPolymerSequenceNonpolyComponentTopologyIngestResult,
        write_result: MmcifPolymerSequenceNonpolyComponentTopologyWriteResult,
        reparsed: MmcifPolymerSequenceNonpolyComponentTopologyIngestResult,
        second: MmcifPolymerSequenceNonpolyComponentTopologyWriteResult,
        report: MmcifPolymerSequenceNonpolyComponentTopologyRoundTripReport,
        *,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise TypeError(
                "MmcifPolymerSequenceNonpolyComponentTopologyRoundTripResult "
                "is factory-only"
            )
        object.__setattr__(self, "_source", source)
        object.__setattr__(self, "_write_result", write_result)
        object.__setattr__(self, "_reparsed", reparsed)
        object.__setattr__(self, "_second", second)
        object.__setattr__(self, "_report", report)
        _validate_aggregate_links(self)
        access = _canonical_json_bytes(_aggregate_access_document(self))
        object.__setattr__(self, "_access_binding_bytes", access)
        _register_anchor(self, access)

    @property
    def source_ingest(
        self,
    ) -> MmcifPolymerSequenceNonpolyComponentTopologyIngestResult:
        _validate_aggregate(self)
        return parse_mmcif_polymer_sequence_nonpoly_component_topology(
            self._source._full_source, source_id=self._source._source_id
        )

    @property
    def write_result(
        self,
    ) -> MmcifPolymerSequenceNonpolyComponentTopologyWriteResult:
        _validate_aggregate(self)
        return write_mmcif_polymer_sequence_nonpoly_component_topology(
            self.source_ingest
        )

    @property
    def reparsed_ingest(
        self,
    ) -> MmcifPolymerSequenceNonpolyComponentTopologyIngestResult:
        _validate_aggregate(self)
        return parse_mmcif_polymer_sequence_nonpoly_component_topology(
            self._reparsed._full_source, source_id=self._reparsed._source_id
        )

    @property
    def reemitted_write_result(
        self,
    ) -> MmcifPolymerSequenceNonpolyComponentTopologyWriteResult:
        _validate_aggregate(self)
        return write_mmcif_polymer_sequence_nonpoly_component_topology(
            self.reparsed_ingest
        )

    @property
    def report(
        self,
    ) -> MmcifPolymerSequenceNonpolyComponentTopologyRoundTripReport:
        _validate_aggregate(self)
        source = self.source_ingest
        first = write_mmcif_polymer_sequence_nonpoly_component_topology(source)
        reparsed = self.reparsed_ingest
        second = write_mmcif_polymer_sequence_nonpoly_component_topology(reparsed)
        return MmcifPolymerSequenceNonpolyComponentTopologyRoundTripReport(
            source,
            first,
            reparsed,
            second,
            _factory_token=_FACTORY_TOKEN,
        )

    def to_dict(self) -> dict[str, Any]:
        _validate_aggregate(self)
        return {
            "source_ingest": self._source.to_dict(),
            "write_result": self._write_result.to_dict(),
            "reparsed_ingest": self._reparsed.to_dict(),
            "reemitted_write_result": self._second.to_dict(),
            "report": self._report.to_dict(),
            **_authority_false_document(),
        }


def _validate_aggregate_links(
    value: MmcifPolymerSequenceNonpolyComponentTopologyRoundTripResult,
) -> None:
    if (
        type(value._source)
        is not MmcifPolymerSequenceNonpolyComponentTopologyIngestResult
        or type(value._write_result)
        is not MmcifPolymerSequenceNonpolyComponentTopologyWriteResult
        or type(value._reparsed)
        is not MmcifPolymerSequenceNonpolyComponentTopologyIngestResult
        or type(value._second)
        is not MmcifPolymerSequenceNonpolyComponentTopologyWriteResult
        or type(value._report)
        is not MmcifPolymerSequenceNonpolyComponentTopologyRoundTripReport
        or value._write_result._ingest is not value._source
        or value._second._ingest is not value._reparsed
        or value._report._source is not value._source
        or value._report._write_result is not value._write_result
        or value._report._reparsed is not value._reparsed
        or value._report._second is not value._second
    ):
        raise MmcifPolymerSequenceNonpolyComponentTopologyError(
            "crosswired_round_trip_artifacts", "round-trip artifacts are crosswired"
        )
    _validate_report(value._report)


def _validate_aggregate(
    value: MmcifPolymerSequenceNonpolyComponentTopologyRoundTripResult,
) -> None:
    if type(value) is not MmcifPolymerSequenceNonpolyComponentTopologyRoundTripResult:
        raise TypeError("an exact composition round-trip result is required")
    try:
        _validate_anchor(
            value, _canonical_json_bytes(_aggregate_access_document(value))
        )
        _validate_aggregate_links(value)
    except Exception:
        raise MmcifPolymerSequenceNonpolyComponentTopologyError(
            "crosswired_round_trip_artifacts", "round-trip artifacts are crosswired"
        ) from None


def round_trip_mmcif_polymer_sequence_nonpoly_component_topology_source(
    data: bytes, *, source_id: str = ""
) -> MmcifPolymerSequenceNonpolyComponentTopologyRoundTripResult:
    source = parse_mmcif_polymer_sequence_nonpoly_component_topology(
        data, source_id=source_id
    )
    write_result = write_mmcif_polymer_sequence_nonpoly_component_topology(source)
    reparsed = parse_mmcif_polymer_sequence_nonpoly_component_topology(
        write_result.payload, source_id=source_id
    )
    second = write_mmcif_polymer_sequence_nonpoly_component_topology(reparsed)
    report = MmcifPolymerSequenceNonpolyComponentTopologyRoundTripReport(
        source,
        write_result,
        reparsed,
        second,
        _factory_token=_FACTORY_TOKEN,
    )
    return MmcifPolymerSequenceNonpolyComponentTopologyRoundTripResult(
        source,
        write_result,
        reparsed,
        second,
        report,
        _factory_token=_FACTORY_TOKEN,
    )


__all__ = [
    "MAX_MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_INPUT_BYTES",
    "MAX_MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_OUTPUT_BYTES",
    "MAX_MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_OUTPUT_LINE_CHARS",
    "MAX_MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_SOURCE_ID_BYTES",
    "MAX_MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_TOKEN_CHARS",
    "MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_ENVELOPE_VERSION",
    "MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_PARSER_NAME",
    "MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_PARSER_VERSION",
    "MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_PROFILE_ID",
    "MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_ROUND_TRIP_REPORT_SCHEMA_ID",
    "MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_SOURCE_BINDING_SCHEMA_ID",
    "MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_STATE_SCHEMA_ID",
    "MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_WRITER_VERSION",
    "MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_WRITE_RECEIPT_SCHEMA_ID",
    "MmcifPolymerSequenceNonpolyComponentTopologyError",
    "MmcifPolymerSequenceNonpolyComponentTopologyIngestResult",
    "MmcifPolymerSequenceNonpolyComponentTopologyRoundTripReport",
    "MmcifPolymerSequenceNonpolyComponentTopologyRoundTripResult",
    "MmcifPolymerSequenceNonpolyComponentTopologyWriteReceipt",
    "MmcifPolymerSequenceNonpolyComponentTopologyWriteResult",
    "emit_mmcif_polymer_sequence_nonpoly_component_topology",
    "mmcif_polymer_sequence_nonpoly_component_topology_state_sha256",
    "mmcif_polymer_sequence_nonpoly_component_topology_record_state_sha256",
    "parse_mmcif_polymer_sequence_nonpoly_component_topology",
    "round_trip_mmcif_polymer_sequence_nonpoly_component_topology_source",
    "serialize_mmcif_polymer_sequence_nonpoly_component_topology",
    "write_mmcif_polymer_sequence_nonpoly_component_topology",
]
