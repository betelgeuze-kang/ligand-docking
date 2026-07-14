"""Strict opt-in mmCIF polymer component-topology envelope.

The existing :mod:`mmcif_polymer_sequence` envelope remains the unchanged,
bondless carrier for coordinates and source-reported sequence identity.  This
module accepts exactly three additional chemical-component definition loops,
checks them against every Cartesian asym/sequence residue instance, and
materializes only the reported intra-residue atom and bond state in a detached
:class:`AllAtomSystem`.

This is a narrow representation contract.  It does not authenticate the
source, infer missing chemistry, prepare or parameterize a molecule, authorize
runtime use, or make a scientific claim.  Digests are deterministic tamper
evidence only.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field, replace
import hashlib
import json
import re
from typing import Any, Mapping
import weakref

from .mmcif_polymer_sequence import (
    MAX_MMCIF_POLYMER_SEQUENCE_ROWS,
    MMCIF_POLYMER_SEQUENCE_PROFILE_ID,
    MmcifPolymerSequenceError,
    MmcifPolymerSequenceIngestResult,
    MmcifPolymerSequenceRow,
    emit_mmcif_polymer_sequence,
    parse_mmcif_polymer_sequence,
)
from .mmcif_syntax import CifBlock, CifLoop, CifSyntaxError, CifToken, parse_cif_block
from .models import AllAtomSystem, Bond, canonical_element_symbol
from .observation import (
    MMCIF_POLYMER_COMPONENT_TOPOLOGY_ATOM_SITE_HEADERS,
    MMCIF_POLYMER_COMPONENT_TOPOLOGY_PREPARATION_INVENTORY_COMMITMENT_SCHEMA_ID,
    PARSER_OBSERVATION_SCHEMA_ID,
    attach_parser_observation_digest,
    attached_parser_observation_sha256_matches,
    mmcif_polymer_component_topology_preparation_inventory_sha256,
)
from .serialization import deserialize_all_atom_system, serialize_all_atom_system
from .topology import (
    CANONICAL_TOPOLOGY_SCHEMA_ID,
    attached_canonical_topology_sha256_matches,
    canonical_topology_sha256,
)


MMCIF_POLYMER_COMPONENT_TOPOLOGY_ENVELOPE_VERSION = "1.0.0"
MMCIF_POLYMER_COMPONENT_TOPOLOGY_PARSER_VERSION = "1.0.0"
MMCIF_POLYMER_COMPONENT_TOPOLOGY_WRITER_VERSION = "1.0.0"
MMCIF_POLYMER_COMPONENT_TOPOLOGY_PARSER_NAME = (
    "betelgeuze_engine_v2.molecular.mmcif_polymer_component_topology."
    "parse_mmcif_polymer_component_topology"
)
MMCIF_POLYMER_COMPONENT_TOPOLOGY_PARSER_PEDIGREE_ID = (
    "betelgeuze.mmcif_polymer_component_topology_parser/1.0.0"
)
MMCIF_POLYMER_COMPONENT_TOPOLOGY_PROFILE_ID = (
    "strict_mmcif_polymer_component_topology_envelope/1.0.0"
)
MMCIF_POLYMER_COMPONENT_TOPOLOGY_PROJECTION_SCHEMA_ID = (
    "betelgeuze.mmcif_polymer_component_topology_projection/1.0.0"
)
MMCIF_POLYMER_COMPONENT_TOPOLOGY_STATE_SCHEMA_ID = (
    "betelgeuze.mmcif_polymer_component_topology_state/1.0.0"
)
MMCIF_POLYMER_COMPONENT_TOPOLOGY_SOURCE_BINDING_SCHEMA_ID = (
    "betelgeuze.mmcif_polymer_component_topology_source_binding/1.0.0"
)
MMCIF_POLYMER_COMPONENT_TOPOLOGY_WRITE_RECEIPT_SCHEMA_ID = (
    "betelgeuze.mmcif_polymer_component_topology_write_receipt/1.0.0"
)
MMCIF_POLYMER_COMPONENT_TOPOLOGY_ROUND_TRIP_REPORT_SCHEMA_ID = (
    "betelgeuze.mmcif_polymer_component_topology_round_trip_report/1.0.0"
)

MAX_MMCIF_POLYMER_COMPONENT_TOPOLOGY_INPUT_BYTES = 64 * 1024 * 1024
MAX_MMCIF_POLYMER_COMPONENT_TOPOLOGY_OUTPUT_BYTES = 64 * 1024 * 1024
MAX_MMCIF_POLYMER_COMPONENT_TOPOLOGY_PROJECTION_BYTES = 64 * 1024 * 1024
MAX_MMCIF_POLYMER_COMPONENT_TOPOLOGY_SOURCE_ID_BYTES = 4_096
MAX_MMCIF_POLYMER_COMPONENT_TOPOLOGY_TOKEN_CHARS = 2_048
MAX_MMCIF_POLYMER_COMPONENT_TOPOLOGY_OUTPUT_LINE_CHARS = 2_048
MAX_MMCIF_POLYMER_COMPONENT_ROWS = 4_096
MAX_MMCIF_POLYMER_COMPONENT_ATOM_ROWS = 80_000
MAX_MMCIF_POLYMER_COMPONENT_BOND_ROWS = 120_000
MAX_MMCIF_POLYMER_COMPONENT_MATERIALIZED_BONDS = 120_000
MAX_MMCIF_POLYMER_COMPONENT_SEQUENCE_ROWS = MAX_MMCIF_POLYMER_SEQUENCE_ROWS

MMCIF_POLYMER_COMPONENT_TOPOLOGY_CHEM_COMP_HEADERS = (
    "_chem_comp.id",
    "_chem_comp.type",
    "_chem_comp.pdbx_formal_charge",
)
MMCIF_POLYMER_COMPONENT_TOPOLOGY_CHEM_COMP_ATOM_HEADERS = (
    "_chem_comp_atom.comp_id",
    "_chem_comp_atom.atom_id",
    "_chem_comp_atom.type_symbol",
    "_chem_comp_atom.charge",
    "_chem_comp_atom.pdbx_aromatic_flag",
    "_chem_comp_atom.pdbx_stereo_config",
    "_chem_comp_atom.pdbx_ordinal",
)
MMCIF_POLYMER_COMPONENT_TOPOLOGY_CHEM_COMP_BOND_HEADERS = (
    "_chem_comp_bond.comp_id",
    "_chem_comp_bond.atom_id_1",
    "_chem_comp_bond.atom_id_2",
    "_chem_comp_bond.value_order",
    "_chem_comp_bond.pdbx_aromatic_flag",
    "_chem_comp_bond.pdbx_stereo_config",
    "_chem_comp_bond.pdbx_ordinal",
)

_ENTITY_HEADERS = ("_entity.id", "_entity.type")
_STRUCT_ASYM_HEADERS = ("_struct_asym.id", "_struct_asym.entity_id")
_ENTITY_POLY_SEQ_HEADERS = (
    "_entity_poly_seq.entity_id",
    "_entity_poly_seq.num",
    "_entity_poly_seq.mon_id",
    "_entity_poly_seq.hetero",
)
_ATOM_SITE_HEADERS = MMCIF_POLYMER_COMPONENT_TOPOLOGY_ATOM_SITE_HEADERS

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
_CARRIER_CATEGORY_ORDER = (
    "_entity",
    "_struct_asym",
    "_entity_poly_seq",
    "_atom_site",
)
_HEADERS_BY_CATEGORY: dict[str, tuple[str, ...] | tuple[tuple[str, ...], ...]] = {
    "_entity": _ENTITY_HEADERS,
    "_struct_asym": _STRUCT_ASYM_HEADERS,
    "_entity_poly_seq": _ENTITY_POLY_SEQ_HEADERS,
    "_chem_comp": MMCIF_POLYMER_COMPONENT_TOPOLOGY_CHEM_COMP_HEADERS,
    "_chem_comp_atom": MMCIF_POLYMER_COMPONENT_TOPOLOGY_CHEM_COMP_ATOM_HEADERS,
    "_chem_comp_bond": MMCIF_POLYMER_COMPONENT_TOPOLOGY_CHEM_COMP_BOND_HEADERS,
    "_atom_site": _ATOM_SITE_HEADERS,
}
_SUPPORTED_ELEMENTS = frozenset({"H", "C", "N", "O", "S"})
_BOND_ORDERS = {"SING": 1.0, "DOUB": 2.0, "TRIP": 3.0, "AROM": 1.5}
_INTEGER_RE = re.compile(r"^[+-]?\d+$")
_FACTORY_TOKEN = object()
_INGEST_STATE_ANCHORS: dict[int, tuple[weakref.ReferenceType[Any], "_ParsedState"]] = {}
_FACTORY_ARTIFACT_ANCHORS: dict[int, tuple[weakref.ReferenceType[Any], bytes]] = {}

_FALSE_AUTHORITY_FIELDS = (
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


class MmcifPolymerComponentTopologyError(ValueError):
    """Privacy-safe fail-closed error for the exact topology envelope."""

    def __init__(
        self, code: str, message: str, *, line_number: int | None = None
    ) -> None:
        self.code = str(code)
        self.detail = str(message)
        self.line_number = None if line_number is None else int(line_number)
        suffix = "" if self.line_number is None else f" at line {self.line_number}"
        super().__init__(
            f"mmcif_polymer_component_topology:{self.code}{suffix}: {self.detail}"
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
    return {name: False for name in _FALSE_AUTHORITY_FIELDS}


def _source_id_sha256(source_id: str) -> str:
    if type(source_id) is not str:
        raise TypeError("source_id must be a string")
    try:
        encoded = source_id.encode("utf-8")
    except UnicodeError:
        raise MmcifPolymerComponentTopologyError(
            "invalid_source_id", "source identifier must contain Unicode scalar values"
        ) from None
    if len(encoded) > MAX_MMCIF_POLYMER_COMPONENT_TOPOLOGY_SOURCE_ID_BYTES:
        raise MmcifPolymerComponentTopologyError(
            "source_id_too_large", "source identifier exceeds the byte limit"
        )
    return _sha256_bytes(encoded)


def _strict_int_token(token: str, *, code: str, max_abs: int = 32_767) -> int:
    if _INTEGER_RE.fullmatch(token) is None:
        raise MmcifPolymerComponentTopologyError(code, "an exact integer is required")
    try:
        value = int(token, 10)
    except (ValueError, OverflowError):
        raise MmcifPolymerComponentTopologyError(
            code, "an exact integer is required"
        ) from None
    if abs(value) > max_abs:
        raise MmcifPolymerComponentTopologyError(
            code, "integer magnitude exceeds the profile limit"
        )
    return value


def _bare_value(token: CifToken, *, allow_missing: bool = False) -> str:
    if token.quoted or token.multiline or "\n" in token.value or "\r" in token.value:
        raise MmcifPolymerComponentTopologyError(
            "invalid_component_token",
            "component definition values must be bare single-line tokens",
            line_number=token.line_number,
        )
    if not allow_missing and token.value in {".", "?"}:
        raise MmcifPolymerComponentTopologyError(
            "invalid_component_token",
            "component definition values must be nonmissing",
            line_number=token.line_number,
        )
    if len(token.value) > MAX_MMCIF_POLYMER_COMPONENT_TOPOLOGY_TOKEN_CHARS:
        raise MmcifPolymerComponentTopologyError(
            "component_token_too_long",
            "component definition token exceeds the character limit",
            line_number=token.line_number,
        )
    return token.value


def _l_peptide_linking_type(token: CifToken) -> str:
    if (
        not token.quoted
        or token.multiline
        or token.value.casefold() != "l-peptide linking"
        or len(token.value) > MAX_MMCIF_POLYMER_COMPONENT_TOPOLOGY_TOKEN_CHARS
    ):
        raise MmcifPolymerComponentTopologyError(
            "unsupported_component_type",
            "component type must be the quoted case-insensitive L-peptide linking value",
            line_number=token.line_number,
        )
    return "L-peptide linking"


@dataclass(frozen=True, slots=True, init=False, repr=False)
class MmcifPolymerComponentRow:
    comp_id: str
    component_type: str
    formal_charge: int

    def __init__(
        self,
        *,
        comp_id: str,
        component_type: str,
        formal_charge: int,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise TypeError("MmcifPolymerComponentRow is factory-only")
        object.__setattr__(self, "comp_id", comp_id)
        object.__setattr__(self, "component_type", component_type)
        object.__setattr__(self, "formal_charge", formal_charge)
        if not all(type(value) is str for value in (comp_id, component_type)):
            raise TypeError("component identifiers and types must be strings")
        if type(formal_charge) is not int:
            raise TypeError("component formal charge must be an integer")


@dataclass(frozen=True, slots=True, init=False, repr=False)
class MmcifPolymerComponentAtomRow:
    comp_id: str
    atom_id: str
    element: str
    charge: int
    aromatic: bool
    stereo: str
    ordinal: int

    def __init__(
        self,
        *,
        comp_id: str,
        atom_id: str,
        element: str,
        charge: int,
        aromatic: bool,
        stereo: str,
        ordinal: int,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise TypeError("MmcifPolymerComponentAtomRow is factory-only")
        for name, value in (
            ("comp_id", comp_id),
            ("atom_id", atom_id),
            ("element", element),
            ("charge", charge),
            ("aromatic", aromatic),
            ("stereo", stereo),
            ("ordinal", ordinal),
        ):
            object.__setattr__(self, name, value)
        if not all(type(value) is str for value in (comp_id, atom_id, element, stereo)):
            raise TypeError("component atom strings must be exact strings")
        if type(charge) is not int or type(ordinal) is not int:
            raise TypeError("component atom charge and ordinal must be integers")
        if type(aromatic) is not bool:
            raise TypeError("component atom aromatic flag must be boolean")


@dataclass(frozen=True, slots=True, init=False, repr=False)
class MmcifPolymerComponentBondRow:
    comp_id: str
    atom_id_1: str
    atom_id_2: str
    value_order: str
    order: float
    aromatic: bool
    stereo: str
    ordinal: int

    def __init__(
        self,
        *,
        comp_id: str,
        atom_id_1: str,
        atom_id_2: str,
        value_order: str,
        order: float,
        aromatic: bool,
        stereo: str,
        ordinal: int,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise TypeError("MmcifPolymerComponentBondRow is factory-only")
        for name, value in (
            ("comp_id", comp_id),
            ("atom_id_1", atom_id_1),
            ("atom_id_2", atom_id_2),
            ("value_order", value_order),
            ("order", order),
            ("aromatic", aromatic),
            ("stereo", stereo),
            ("ordinal", ordinal),
        ):
            object.__setattr__(self, name, value)
        if not all(
            type(value) is str
            for value in (comp_id, atom_id_1, atom_id_2, value_order, stereo)
        ):
            raise TypeError("component bond strings must be exact strings")
        if type(order) is not float or type(ordinal) is not int:
            raise TypeError("component bond order and ordinal have invalid types")
        if type(aromatic) is not bool:
            raise TypeError("component bond aromatic flag must be boolean")


def _parse_block(data: bytes) -> CifBlock:
    if type(data) is not bytes:
        raise TypeError("mmCIF polymer component topology input must be bytes")
    if not data:
        raise MmcifPolymerComponentTopologyError("empty_input", "input is empty")
    if len(data) > MAX_MMCIF_POLYMER_COMPONENT_TOPOLOGY_INPUT_BYTES:
        raise MmcifPolymerComponentTopologyError(
            "input_too_large", "input exceeds the envelope byte limit"
        )
    try:
        decoded = data.decode("ascii")
    except UnicodeDecodeError:
        raise MmcifPolymerComponentTopologyError(
            "non_ascii_input",
            "input must use the printable CIF 1.1 ASCII character set",
        ) from None
    if any(
        len(line) > MAX_MMCIF_POLYMER_COMPONENT_TOPOLOGY_OUTPUT_LINE_CHARS
        for line in decoded.splitlines()
    ):
        raise MmcifPolymerComponentTopologyError(
            "input_line_too_long",
            "input line exceeds the fixed profile character limit",
        )
    try:
        return parse_cif_block(decoded)
    except CifSyntaxError as exc:
        code = (
            "unsupported_category_representation"
            if exc.code == "duplicate_data_name"
            else exc.code
        )
        raise MmcifPolymerComponentTopologyError(
            code,
            "input is outside the exact single-block CIF envelope grammar",
            line_number=exc.line_number,
        ) from None


def _loop_for(block: CifBlock, category: str) -> CifLoop:
    scalar = [name for name in block.scalar_values if name.split(".", 1)[0] == category]
    loops = [loop for loop in block.loops if category in loop.categories]
    if scalar or len(loops) != 1 or loops[0].categories != (category,):
        raise MmcifPolymerComponentTopologyError(
            "unsupported_category_representation",
            "each selected category must occur in one category-local loop",
        )
    return loops[0]


def _validate_surface(block: CifBlock) -> dict[str, CifLoop]:
    if (
        len(block.name) > MAX_MMCIF_POLYMER_COMPONENT_TOPOLOGY_TOKEN_CHARS
        or len("data_") + len(block.name)
        > MAX_MMCIF_POLYMER_COMPONENT_TOPOLOGY_OUTPUT_LINE_CHARS
    ):
        raise MmcifPolymerComponentTopologyError(
            "block_name_too_long",
            "data-block name exceeds the canonical line character limit",
        )
    if set(block.categories) != _EXPECTED_CATEGORIES:
        raise MmcifPolymerComponentTopologyError(
            "unsupported_category_surface",
            "input categories must exactly match the seven-category envelope",
        )
    loops = {category: _loop_for(block, category) for category in _CATEGORY_ORDER}
    for category, loop in loops.items():
        expected = _HEADERS_BY_CATEGORY[category]
        valid = loop.tags == expected
        if not valid:
            raise MmcifPolymerComponentTopologyError(
                "unsupported_category_headers",
                "selected category headers are outside the exact envelope profile",
                line_number=loop.line_number,
            )
        for row in loop.rows:
            for token in row:
                if len(token.value) > MAX_MMCIF_POLYMER_COMPONENT_TOPOLOGY_TOKEN_CHARS:
                    raise MmcifPolymerComponentTopologyError(
                        "token_too_long",
                        "selected source token exceeds the character limit",
                        line_number=token.line_number,
                    )
    limits = {
        "_entity_poly_seq": (
            MAX_MMCIF_POLYMER_SEQUENCE_ROWS,
            "too_many_sequence_rows",
        ),
        "_chem_comp": (MAX_MMCIF_POLYMER_COMPONENT_ROWS, "too_many_component_rows"),
        "_chem_comp_atom": (
            MAX_MMCIF_POLYMER_COMPONENT_ATOM_ROWS,
            "too_many_component_atom_rows",
        ),
        "_chem_comp_bond": (
            MAX_MMCIF_POLYMER_COMPONENT_BOND_ROWS,
            "too_many_component_bond_rows",
        ),
    }
    for category, (limit, code) in limits.items():
        if len(loops[category].rows) > limit:
            raise MmcifPolymerComponentTopologyError(
                code, "component definition row count exceeds the profile limit"
            )
    return loops


def _token_text(token: CifToken) -> str:
    if token.multiline:
        raise MmcifPolymerComponentTopologyError(
            "unsupported_multiline_token", "multiline tokens are outside the profile"
        )
    if not token.quoted:
        rendered = token.value
    elif "'" not in token.value:
        rendered = f"'{token.value}'"
    elif '"' not in token.value:
        rendered = f'"{token.value}"'
    else:
        raise MmcifPolymerComponentTopologyError(
            "unsupported_quoted_token", "a quoted token cannot be emitted canonically"
        )
    if len(rendered) > MAX_MMCIF_POLYMER_COMPONENT_TOPOLOGY_OUTPUT_LINE_CHARS:
        raise MmcifPolymerComponentTopologyError(
            "output_token_too_long",
            "canonical token exceeds the output line character limit",
            line_number=token.line_number,
        )
    return rendered


def _emit_rows(headers: tuple[str, ...], rows: tuple[tuple[str, ...], ...]) -> bytes:
    lines = ["loop_", *headers]
    for row in rows:
        joined = " ".join(row)
        lines.extend(
            (joined,)
            if len(joined) <= MAX_MMCIF_POLYMER_COMPONENT_TOPOLOGY_OUTPUT_LINE_CHARS
            else row
        )
    lines.append("#")
    return ("\n".join(lines) + "\n").encode("ascii")


def _emit_loop(loop: CifLoop) -> bytes:
    rows = tuple(tuple(_token_text(token) for token in row) for row in loop.rows)
    return _emit_rows(loop.tags, rows)


def _carrier_source(block: CifBlock, loops: Mapping[str, CifLoop]) -> bytes:
    return b"".join(
        (
            f"data_{block.name}\n#\n".encode("ascii"),
            *(_emit_loop(loops[category]) for category in _CARRIER_CATEGORY_ORDER),
        )
    )


def _parse_component_rows(
    loops: Mapping[str, CifLoop],
) -> tuple[
    tuple[MmcifPolymerComponentRow, ...],
    tuple[MmcifPolymerComponentAtomRow, ...],
    tuple[MmcifPolymerComponentBondRow, ...],
]:
    components: list[MmcifPolymerComponentRow] = []
    seen_components: set[str] = set()
    for tokens in loops["_chem_comp"].rows:
        comp_id = _bare_value(tokens[0])
        component_type = _l_peptide_linking_type(tokens[1])
        formal_charge = _strict_int_token(
            _bare_value(tokens[2]), code="invalid_component_formal_charge"
        )
        if comp_id in seen_components:
            raise MmcifPolymerComponentTopologyError(
                "duplicate_component_id", "component identifiers must be unique"
            )
        seen_components.add(comp_id)
        components.append(
            MmcifPolymerComponentRow(
                comp_id=comp_id,
                component_type=component_type,
                formal_charge=formal_charge,
                _factory_token=_FACTORY_TOKEN,
            )
        )

    atoms_by_component: dict[str, list[MmcifPolymerComponentAtomRow]] = defaultdict(
        list
    )
    seen_atoms: set[tuple[str, str]] = set()
    for tokens in loops["_chem_comp_atom"].rows:
        comp_id = _bare_value(tokens[0])
        atom_id = _bare_value(tokens[1])
        raw_element = _bare_value(tokens[2])
        element = canonical_element_symbol(raw_element)
        charge = _strict_int_token(
            _bare_value(tokens[3]), code="invalid_component_atom_charge"
        )
        aromatic_flag = _bare_value(tokens[4])
        stereo = _bare_value(tokens[5])
        ordinal = _strict_int_token(
            _bare_value(tokens[6]),
            code="invalid_component_atom_ordinal",
            max_abs=MAX_MMCIF_POLYMER_COMPONENT_ATOM_ROWS,
        )
        if comp_id not in seen_components:
            raise MmcifPolymerComponentTopologyError(
                "unknown_component_atom_component",
                "component atom row references an undefined component",
            )
        if element not in _SUPPORTED_ELEMENTS:
            raise MmcifPolymerComponentTopologyError(
                "unsupported_component_element",
                "component atom element is outside the supported element set",
            )
        if aromatic_flag not in {"Y", "N"}:
            raise MmcifPolymerComponentTopologyError(
                "invalid_component_atom_aromatic_flag",
                "component atom aromatic flag must be Y or N",
            )
        if stereo not in {"N", "R", "S"}:
            raise MmcifPolymerComponentTopologyError(
                "unsupported_component_atom_stereo",
                "component atom stereo must be one of the explicit N/R/S values",
            )
        if ordinal <= 0:
            raise MmcifPolymerComponentTopologyError(
                "invalid_component_atom_ordinal",
                "component atom ordinal must be positive",
            )
        key = (comp_id, atom_id)
        if key in seen_atoms:
            raise MmcifPolymerComponentTopologyError(
                "duplicate_component_atom_id",
                "component atom identifiers must be unique within a component",
            )
        seen_atoms.add(key)
        atoms_by_component[comp_id].append(
            MmcifPolymerComponentAtomRow(
                comp_id=comp_id,
                atom_id=atom_id,
                element=element,
                charge=charge,
                aromatic=aromatic_flag == "Y",
                stereo=stereo,
                ordinal=ordinal,
                _factory_token=_FACTORY_TOKEN,
            )
        )

    bonds_by_component: dict[str, list[MmcifPolymerComponentBondRow]] = defaultdict(
        list
    )
    seen_bonds: set[tuple[str, str, str]] = set()
    for tokens in loops["_chem_comp_bond"].rows:
        comp_id = _bare_value(tokens[0])
        atom_id_1 = _bare_value(tokens[1])
        atom_id_2 = _bare_value(tokens[2])
        value_order = _bare_value(tokens[3]).upper()
        aromatic_flag = _bare_value(tokens[4])
        stereo = _bare_value(tokens[5])
        ordinal = _strict_int_token(
            _bare_value(tokens[6]),
            code="invalid_component_bond_ordinal",
            max_abs=MAX_MMCIF_POLYMER_COMPONENT_BOND_ROWS,
        )
        if comp_id not in seen_components:
            raise MmcifPolymerComponentTopologyError(
                "unknown_component_bond_component",
                "component bond row references an undefined component",
            )
        if value_order not in _BOND_ORDERS:
            raise MmcifPolymerComponentTopologyError(
                "unsupported_component_bond_order",
                "component bond order is outside SING/DOUB/TRIP/AROM",
            )
        expected_aromatic = "Y" if value_order == "AROM" else "N"
        if aromatic_flag != expected_aromatic:
            raise MmcifPolymerComponentTopologyError(
                "component_bond_aromatic_mismatch",
                "component bond order and aromatic flag are inconsistent",
            )
        if stereo != "N":
            raise MmcifPolymerComponentTopologyError(
                "unsupported_component_bond_stereo",
                "component bond stereo must be the explicit N value",
            )
        if ordinal <= 0:
            raise MmcifPolymerComponentTopologyError(
                "invalid_component_bond_ordinal",
                "component bond ordinal must be positive",
            )
        if atom_id_1 == atom_id_2:
            raise MmcifPolymerComponentTopologyError(
                "self_component_bond", "component bonds must not be self bonds"
            )
        pair = tuple(sorted((atom_id_1, atom_id_2)))
        key = (comp_id, pair[0], pair[1])
        if key in seen_bonds:
            raise MmcifPolymerComponentTopologyError(
                "duplicate_component_bond",
                "component bond endpoint pairs must be unique",
            )
        seen_bonds.add(key)
        bonds_by_component[comp_id].append(
            MmcifPolymerComponentBondRow(
                comp_id=comp_id,
                atom_id_1=atom_id_1,
                atom_id_2=atom_id_2,
                value_order=value_order,
                order=_BOND_ORDERS[value_order],
                aromatic=aromatic_flag == "Y",
                stereo=stereo,
                ordinal=ordinal,
                _factory_token=_FACTORY_TOKEN,
            )
        )

    canonical_atoms: list[MmcifPolymerComponentAtomRow] = []
    canonical_bonds: list[MmcifPolymerComponentBondRow] = []
    for component in components:
        component_atoms = atoms_by_component.get(component.comp_id, [])
        if not component_atoms:
            raise MmcifPolymerComponentTopologyError(
                "missing_component_atoms",
                "every selected component must define at least one atom",
            )
        atom_ordinals = sorted(row.ordinal for row in component_atoms)
        if atom_ordinals != list(range(1, len(component_atoms) + 1)):
            raise MmcifPolymerComponentTopologyError(
                "noncontiguous_component_atom_ordinals",
                "component atom ordinals must be positive and contiguous",
            )
        component_atoms.sort(key=lambda row: row.ordinal)
        atom_ids = {row.atom_id for row in component_atoms}
        if sum(row.charge for row in component_atoms) != component.formal_charge:
            raise MmcifPolymerComponentTopologyError(
                "component_charge_sum_mismatch",
                "component formal charge must equal its atom charge sum",
            )
        component_bonds = bonds_by_component.get(component.comp_id, [])
        bond_ordinals = sorted(row.ordinal for row in component_bonds)
        if bond_ordinals != list(range(1, len(component_bonds) + 1)):
            raise MmcifPolymerComponentTopologyError(
                "noncontiguous_component_bond_ordinals",
                "component bond ordinals must be positive and contiguous",
            )
        component_bonds.sort(key=lambda row: row.ordinal)
        if any(
            row.atom_id_1 not in atom_ids or row.atom_id_2 not in atom_ids
            for row in component_bonds
        ):
            raise MmcifPolymerComponentTopologyError(
                "dangling_component_bond",
                "component bond endpoints must reference defined component atoms",
            )
        atom_aromatic = {row.atom_id: row.aromatic for row in component_atoms}
        aromatic_bond_atom_ids = {
            atom_id
            for row in component_bonds
            if row.aromatic
            for atom_id in (row.atom_id_1, row.atom_id_2)
        }
        if any(
            row.aromatic
            and not (atom_aromatic[row.atom_id_1] and atom_aromatic[row.atom_id_2])
            for row in component_bonds
        ) or aromatic_bond_atom_ids != {
            atom_id for atom_id, aromatic in atom_aromatic.items() if aromatic
        }:
            raise MmcifPolymerComponentTopologyError(
                "component_atom_bond_aromatic_mismatch",
                "aromatic atoms must exactly equal endpoints participating in aromatic bonds",
            )
        canonical_atoms.extend(component_atoms)
        canonical_bonds.extend(component_bonds)

    return tuple(components), tuple(canonical_atoms), tuple(canonical_bonds)


def _validate_component_coverage(
    carrier: MmcifPolymerSequenceIngestResult,
    components: tuple[MmcifPolymerComponentRow, ...],
) -> None:
    required = {row.mon_id for row in carrier.sequence_rows}
    observed = {row.comp_id for row in components}
    if observed != required:
        raise MmcifPolymerComponentTopologyError(
            "component_definition_coverage_mismatch",
            "component definitions must exactly equal the sequence monomer-ID set",
        )


def _validate_exact_polymer_instances(
    loops: Mapping[str, CifLoop], carrier: MmcifPolymerSequenceIngestResult
) -> None:
    entity_types = {row[0].value: row[1].value for row in loops["_entity"].rows}
    if not entity_types or set(entity_types.values()) != {"polymer"}:
        raise MmcifPolymerComponentTopologyError(
            "polymer_only_surface_required",
            "every selected entity must be an explicit polymer entity",
        )
    asym_entities = {row[0].value: row[1].value for row in loops["_struct_asym"].rows}
    if (
        not asym_entities
        or set(asym_entities.values()) != set(entity_types)
        or any(
            entity_types.get(entity_id) != "polymer"
            for entity_id in asym_entities.values()
        )
    ):
        raise MmcifPolymerComponentTopologyError(
            "polymer_asym_coverage_mismatch",
            "polymer entities and struct-asym rows must cover each other exactly",
        )
    expected_observation = {
        row.entity_id: frozenset(
            asym_id
            for asym_id, entity_id in asym_entities.items()
            if entity_id == row.entity_id
        )
        for row in carrier.sequence_rows
    }
    if any(
        not row.coordinate_observed
        or frozenset(row.observed_asym_ids) != expected_observation[row.entity_id]
        for row in carrier.sequence_rows
    ):
        raise MmcifPolymerComponentTopologyError(
            "polymer_cartesian_residue_coverage_mismatch",
            "every struct-asym by sequence-position residue must be coordinate-observed exactly once",
        )
    expected_instances = {
        (asym_id, entity_id, row.num, row.mon_id)
        for row in carrier.sequence_rows
        for asym_id, mapped_entity in asym_entities.items()
        if mapped_entity == row.entity_id
        for entity_id in (row.entity_id,)
    }
    observed_instances = {
        (
            carrier.system.chains[residue.chain_index].chain_id,
            carrier.system.chains[residue.chain_index].entity_id,
            residue.sequence_number,
            residue.name,
        )
        for residue in carrier.system.residues
    }
    if observed_instances != expected_instances or len(carrier.system.residues) != len(
        expected_instances
    ):
        raise MmcifPolymerComponentTopologyError(
            "polymer_cartesian_residue_coverage_mismatch",
            "the carrier residue set must equal the exact asym-by-sequence Cartesian product",
        )


def _component_projection_document(
    components: tuple[MmcifPolymerComponentRow, ...],
    atoms: tuple[MmcifPolymerComponentAtomRow, ...],
    bonds: tuple[MmcifPolymerComponentBondRow, ...],
    *,
    carrier_sequence_projection_sha256: str,
) -> dict[str, Any]:
    return {
        "schema_id": MMCIF_POLYMER_COMPONENT_TOPOLOGY_PROJECTION_SCHEMA_ID,
        "envelope_version": MMCIF_POLYMER_COMPONENT_TOPOLOGY_ENVELOPE_VERSION,
        "profile_id": MMCIF_POLYMER_COMPONENT_TOPOLOGY_PROFILE_ID,
        "carrier_sequence_projection_sha256": carrier_sequence_projection_sha256,
        "chem_comp_rows": [
            {
                "ordinal": ordinal,
                "comp_id": row.comp_id,
                "type": row.component_type,
                "formal_charge": row.formal_charge,
            }
            for ordinal, row in enumerate(components)
        ],
        "chem_comp_atom_rows": [
            {
                "comp_id": row.comp_id,
                "atom_id": row.atom_id,
                "element": row.element,
                "charge": row.charge,
                "aromatic": row.aromatic,
                "stereo": row.stereo,
                "ordinal": row.ordinal,
            }
            for row in atoms
        ],
        "chem_comp_bond_rows": [
            {
                "comp_id": row.comp_id,
                "atom_id_1": row.atom_id_1,
                "atom_id_2": row.atom_id_2,
                "value_order": row.value_order,
                "order": row.order,
                "aromatic": row.aromatic,
                "stereo": row.stereo,
                "ordinal": row.ordinal,
            }
            for row in bonds
        ],
        "semantics": "source_reported_explicit_polymer_intra_residue_component_topology_only",
        **_authority_false_document(),
    }


def _component_rows_for_emission(
    components: tuple[MmcifPolymerComponentRow, ...],
    atoms: tuple[MmcifPolymerComponentAtomRow, ...],
    bonds: tuple[MmcifPolymerComponentBondRow, ...],
) -> dict[str, tuple[tuple[str, ...], ...]]:
    return {
        "_chem_comp": tuple(
            (row.comp_id, "'L-peptide linking'", str(row.formal_charge))
            for row in components
        ),
        "_chem_comp_atom": tuple(
            (
                row.comp_id,
                row.atom_id,
                row.element,
                str(row.charge),
                "Y" if row.aromatic else "N",
                row.stereo,
                str(row.ordinal),
            )
            for row in atoms
        ),
        "_chem_comp_bond": tuple(
            (
                row.comp_id,
                row.atom_id_1,
                row.atom_id_2,
                row.value_order,
                "Y" if row.aromatic else "N",
                row.stereo,
                str(row.ordinal),
            )
            for row in bonds
        ),
    }


def _canonical_output(
    carrier: MmcifPolymerSequenceIngestResult,
    components: tuple[MmcifPolymerComponentRow, ...],
    atoms: tuple[MmcifPolymerComponentAtomRow, ...],
    bonds: tuple[MmcifPolymerComponentBondRow, ...],
) -> bytes:
    carrier_output = emit_mmcif_polymer_sequence(carrier).payload
    try:
        block = parse_cif_block(carrier_output.decode("ascii"))
    except (UnicodeDecodeError, CifSyntaxError):
        raise MmcifPolymerComponentTopologyError(
            "carrier_emission_invalid",
            "the bound polymer-sequence carrier emitted invalid CIF",
        ) from None
    carrier_loops = {
        category: _loop_for(block, category) for category in _CARRIER_CATEGORY_ORDER
    }
    component_rows = _component_rows_for_emission(components, atoms, bonds)
    pieces: list[bytes] = [f"data_{block.name}\n#\n".encode("ascii")]
    for category in _CATEGORY_ORDER:
        if category in component_rows:
            headers = _HEADERS_BY_CATEGORY[category]
            assert type(headers) is tuple and all(type(item) is str for item in headers)
            pieces.append(_emit_rows(headers, component_rows[category]))
        else:
            pieces.append(_emit_loop(carrier_loops[category]))
    payload = b"".join(pieces)
    if len(payload) > MAX_MMCIF_POLYMER_COMPONENT_TOPOLOGY_OUTPUT_BYTES:
        raise MmcifPolymerComponentTopologyError(
            "output_too_large", "canonical output exceeds the envelope byte limit"
        )
    parsed = _parse_block(payload)
    _validate_surface(parsed)
    return payload


def _materialize_system(
    carrier: MmcifPolymerSequenceIngestResult,
    components: tuple[MmcifPolymerComponentRow, ...],
    template_atoms: tuple[MmcifPolymerComponentAtomRow, ...],
    template_bonds: tuple[MmcifPolymerComponentBondRow, ...],
    *,
    full_source: bytes,
    canonical_output: bytes,
) -> AllAtomSystem:
    carrier_system = carrier.system
    if carrier_system.bonds:
        raise MmcifPolymerComponentTopologyError(
            "carrier_not_bondless",
            "the unchanged polymer-sequence carrier must remain bondless",
        )
    component_map = {row.comp_id: row for row in components}
    atom_templates: dict[str, dict[str, MmcifPolymerComponentAtomRow]] = defaultdict(
        dict
    )
    bond_templates: dict[str, list[MmcifPolymerComponentBondRow]] = defaultdict(list)
    for row in template_atoms:
        atom_templates[row.comp_id][row.atom_id] = row
    for row in template_bonds:
        bond_templates[row.comp_id].append(row)

    augmented_atoms = list(carrier_system.atoms)
    pending_bonds: list[tuple[int, int, MmcifPolymerComponentBondRow, int]] = []
    instance_count = 0
    for residue in carrier_system.residues:
        if residue.entity_type != "polymer":
            raise MmcifPolymerComponentTopologyError(
                "polymer_only_surface_required",
                "the carrier may contain only polymer residue instances",
            )
        if residue.name not in component_map:
            raise MmcifPolymerComponentTopologyError(
                "residue_component_join_mismatch",
                "a polymer residue lacks its exact sequence component definition",
            )
        templates = atom_templates[residue.name]
        instance_atoms = [carrier_system.atoms[index] for index in residue.atom_indices]
        by_name: dict[str, Any] = {}
        for atom in instance_atoms:
            if atom.name in by_name:
                raise MmcifPolymerComponentTopologyError(
                    "duplicate_instance_atom",
                    "a component instance contains a duplicate template atom identifier",
                )
            by_name[atom.name] = atom
        if set(by_name) != set(templates):
            raise MmcifPolymerComponentTopologyError(
                "component_instance_atom_coverage_mismatch",
                "every component instance must contain each template atom exactly once and no extras",
            )
        for atom_id, atom in by_name.items():
            template = templates[atom_id]
            if atom.element != template.element:
                raise MmcifPolymerComponentTopologyError(
                    "component_atom_element_mismatch",
                    "atom-site and component-template elements must agree",
                )
            if atom.formal_charge_known and atom.formal_charge != template.charge:
                raise MmcifPolymerComponentTopologyError(
                    "component_atom_charge_mismatch",
                    "known atom-site and component-template formal charges must agree",
                )
            metadata = dict(atom.metadata)
            metadata.update(
                {
                    "formal_charge_interpretation": "explicit_component_template",
                    "formal_charge_known": True,
                    "formal_charge_source": (
                        "cross_checked_atom_site_and_chem_comp_atom"
                        if atom.formal_charge_known
                        else "_chem_comp_atom.charge"
                    ),
                    "mmcif_polymer_component_topology": {
                        "component_id": residue.name,
                        "template_atom_id": atom_id,
                        "template_ordinal": template.ordinal,
                        "source_reported_aromatic": template.aromatic,
                        "source_reported_stereo": template.stereo,
                    },
                }
            )
            augmented_atoms[atom.index] = replace(
                atom,
                formal_charge=template.charge,
                formal_charge_known=True,
                aromatic=template.aromatic,
                stereo=("none" if template.stereo == "N" else template.stereo),
                metadata=metadata,
            )
        for template_bond in bond_templates[residue.name]:
            if len(pending_bonds) >= MAX_MMCIF_POLYMER_COMPONENT_MATERIALIZED_BONDS:
                raise MmcifPolymerComponentTopologyError(
                    "too_many_materialized_bonds",
                    "expanded component instances exceed the materialized bond limit",
                )
            atom_i = by_name[template_bond.atom_id_1].index
            atom_j = by_name[template_bond.atom_id_2].index
            pending_bonds.append(
                (min(atom_i, atom_j), max(atom_i, atom_j), template_bond, residue.index)
            )
        instance_count += 1

    pending_bonds.sort(key=lambda item: (item[0], item[1]))
    bonds = tuple(
        Bond(
            index=index,
            atom_i=atom_i,
            atom_j=atom_j,
            order=template.order,
            aromatic=template.aromatic,
            stereo="none",
            source="mmcif_chem_comp_bond",
            metadata={
                "mmcif_polymer_component_topology": {
                    "component_id": template.comp_id,
                    "template_atom_id_1": template.atom_id_1,
                    "template_atom_id_2": template.atom_id_2,
                    "template_ordinal": template.ordinal,
                    "component_instance_residue_index": residue_index,
                    "source_reported_value_order": template.value_order,
                    "source_reported_aromatic": template.aromatic,
                    "source_reported_stereo": template.stereo,
                },
            },
        )
        for index, (atom_i, atom_j, template, residue_index) in enumerate(pending_bonds)
    )
    provenance_metadata = dict(carrier_system.provenance.metadata)
    carrier_coverage = provenance_metadata.pop("coverage", None)
    carrier_missingness_schema_id = provenance_metadata.pop(
        "source_missingness_evidence_schema_id",
        None,
    )
    carrier_missingness_sha256 = provenance_metadata.pop(
        "source_missingness_evidence_sha256",
        None,
    )
    provenance_metadata["carrier_coverage"] = carrier_coverage
    provenance_metadata["carrier_source_missingness_evidence_schema_id"] = (
        carrier_missingness_schema_id
    )
    provenance_metadata["carrier_source_missingness_evidence_sha256"] = (
        carrier_missingness_sha256
    )
    provenance_metadata["mmcif_polymer_component_topology"] = {
        "canonical_output_sha256": _sha256_bytes(canonical_output),
        "parser_pedigree_id": MMCIF_POLYMER_COMPONENT_TOPOLOGY_PARSER_PEDIGREE_ID,
        "source_sha256_semantics": "raw_full_source_bytes",
        "carrier_evidence_semantics": (
            "preserved_polymer_sequence_carrier_only_not_augmented_topology_evidence"
        ),
    }
    provenance = replace(
        carrier_system.provenance,
        source_sha256=_sha256_bytes(full_source),
        parser_name=MMCIF_POLYMER_COMPONENT_TOPOLOGY_PARSER_NAME,
        parser_version=MMCIF_POLYMER_COMPONENT_TOPOLOGY_PARSER_VERSION,
        operations=(
            *carrier_system.provenance.operations,
            "join_explicit_chem_comp_atom_templates/v1",
            "fill_or_cross_check_formal_charge/v1",
            "materialize_explicit_chem_comp_bonds/v1",
        ),
        parent_sha256=(carrier.base_system_snapshot_sha256,),
        preparation_ready=False,
        claim_safe=False,
        metadata=provenance_metadata,
    )
    metadata = dict(carrier_system.metadata)
    carrier_mmcif_metadata = dict(metadata.get("mmcif", {}))
    carrier_source_missingness = carrier_mmcif_metadata.pop(
        "source_missingness",
        None,
    )
    carrier_source_reported_missingness = carrier_mmcif_metadata.pop(
        "source_reported_missingness",
        None,
    )
    carrier_mmcif_metadata["carrier_source_missingness"] = carrier_source_missingness
    carrier_mmcif_metadata["carrier_source_reported_missingness"] = (
        carrier_source_reported_missingness
    )
    carrier_mmcif_metadata["carrier_evidence_semantics"] = (
        "preserved_polymer_sequence_carrier_only_not_augmented_topology_evidence"
    )
    metadata["mmcif"] = carrier_mmcif_metadata
    metadata["mmcif_polymer_component_topology"] = {
        "profile_id": MMCIF_POLYMER_COMPONENT_TOPOLOGY_PROFILE_ID,
        "component_count": len(components),
        "component_instance_count": instance_count,
        "bond_count": len(bonds),
        **_authority_false_document(),
    }
    system = replace(
        carrier_system,
        atoms=tuple(augmented_atoms),
        bonds=bonds,
        provenance=provenance,
        metadata=metadata,
    )
    # The canonical topology function performs the shared structural validity
    # check, including endpoint ordering, duplicate bonds, and typed atom state.
    augmented_topology_sha256 = canonical_topology_sha256(system)
    augmented_provenance_metadata = dict(system.provenance.metadata)
    augmented_provenance_metadata["canonical_topology_schema_id"] = (
        CANONICAL_TOPOLOGY_SCHEMA_ID
    )
    augmented_provenance_metadata["canonical_topology_sha256"] = (
        augmented_topology_sha256
    )
    system = replace(
        system,
        provenance=replace(
            system.provenance,
            metadata=augmented_provenance_metadata,
        ),
    )
    # This unkeyed, source-bound commitment is tamper evidence only.  It does
    # not authenticate the source, and an actor rewriting it together with all
    # enclosing digests is outside the integrity check's threat model.
    preparation_inventory_sha256 = (
        mmcif_polymer_component_topology_preparation_inventory_sha256(system)
    )
    committed_provenance_metadata = dict(system.provenance.metadata)
    committed_marker = dict(
        committed_provenance_metadata["mmcif_polymer_component_topology"]
    )
    committed_marker["preparation_inventory_commitment_schema_id"] = (
        MMCIF_POLYMER_COMPONENT_TOPOLOGY_PREPARATION_INVENTORY_COMMITMENT_SCHEMA_ID
    )
    committed_marker["preparation_inventory_commitment_sha256"] = (
        preparation_inventory_sha256
    )
    committed_provenance_metadata["mmcif_polymer_component_topology"] = committed_marker
    system = replace(
        system,
        provenance=replace(
            system.provenance,
            metadata=committed_provenance_metadata,
        ),
    )
    return attach_parser_observation_digest(system)


@dataclass(frozen=True, slots=True)
class _ParsedState:
    full_source: bytes = field(repr=False)
    source_id: str = field(repr=False)
    carrier_source: bytes = field(repr=False)
    carrier_ingest: MmcifPolymerSequenceIngestResult = field(repr=False)
    carrier_object_id: int
    component_rows: tuple[MmcifPolymerComponentRow, ...] = field(repr=False)
    component_atom_rows: tuple[MmcifPolymerComponentAtomRow, ...] = field(repr=False)
    component_bond_rows: tuple[MmcifPolymerComponentBondRow, ...] = field(repr=False)
    projection_bytes: bytes = field(repr=False)
    system_snapshot: bytes = field(repr=False)
    canonical_output: bytes = field(repr=False)
    topology_state_bytes: bytes = field(repr=False)
    source_binding_bytes: bytes = field(repr=False)


def _compute_topology_state_document(state: _ParsedState) -> dict[str, Any]:
    system = deserialize_all_atom_system(state.system_snapshot)
    return {
        "schema_id": MMCIF_POLYMER_COMPONENT_TOPOLOGY_STATE_SCHEMA_ID,
        "envelope_version": MMCIF_POLYMER_COMPONENT_TOPOLOGY_ENVELOPE_VERSION,
        "parser_name": MMCIF_POLYMER_COMPONENT_TOPOLOGY_PARSER_NAME,
        "parser_version": MMCIF_POLYMER_COMPONENT_TOPOLOGY_PARSER_VERSION,
        "parser_pedigree_id": (MMCIF_POLYMER_COMPONENT_TOPOLOGY_PARSER_PEDIGREE_ID),
        "writer_version": MMCIF_POLYMER_COMPONENT_TOPOLOGY_WRITER_VERSION,
        "profile_id": MMCIF_POLYMER_COMPONENT_TOPOLOGY_PROFILE_ID,
        "canonical_topology_schema_id": CANONICAL_TOPOLOGY_SCHEMA_ID,
        "parser_observation_schema_id": PARSER_OBSERVATION_SCHEMA_ID,
        "attached_canonical_topology_digest_self_consistent": (
            attached_canonical_topology_sha256_matches(system)
        ),
        "attached_parser_observation_digest_self_consistent": (
            attached_parser_observation_sha256_matches(system)
        ),
        "carrier_profile_id": MMCIF_POLYMER_SEQUENCE_PROFILE_ID,
        "carrier_sequence_projection_sha256": state.carrier_ingest.polymer_sequence_projection_sha256,
        "carrier_record_state_sha256": state.carrier_ingest.record_state_sha256,
        "carrier_base_topology_sha256": state.carrier_ingest.base_topology_sha256,
        "carrier_base_representable_state_sha256": (
            state.carrier_ingest.base_representable_state_sha256
        ),
        "component_projection_sha256": _sha256_bytes(state.projection_bytes),
        "augmented_topology_sha256": canonical_topology_sha256(system),
        "component_count": len(state.component_rows),
        "component_atom_row_count": len(state.component_atom_rows),
        "component_bond_row_count": len(state.component_bond_rows),
        "materialized_atom_count": system.atom_count,
        "materialized_bond_count": len(system.bonds),
        "topology_state_scope": (
            "normalized_carrier_component_projection_and_canonical_topology"
        ),
        "source_specific_augmented_snapshot_bound_in": (
            "source_binding_and_write_receipt"
        ),
        "carrier_remains_bondless": len(state.carrier_ingest.system.bonds) == 0,
        "new_system_parser_pedigree_introduced": True,
        "exact_asym_sequence_cartesian_coverage_required": True,
        "exact_instance_template_atom_coverage_required": True,
        "only_intra_residue_component_bonds_materialized": True,
        "peptide_or_inter_residue_bonds_not_inferred": True,
        "formal_charge_fill_rule": (
            "fill_unknown_from_chem_comp_atom_and_cross_check_known_atom_site_values"
        ),
        "bond_topology_interpreted": True,
        "bond_order_interpreted": True,
        "charge_interpreted": True,
        "source_reported_component_topology_materialized": True,
        **_authority_false_document(),
    }


def _topology_state_document(state: _ParsedState) -> dict[str, Any]:
    return json.loads(state.topology_state_bytes.decode("ascii"))


def _compute_source_binding_document(state: _ParsedState) -> dict[str, Any]:
    system = deserialize_all_atom_system(state.system_snapshot)
    return {
        "schema_id": MMCIF_POLYMER_COMPONENT_TOPOLOGY_SOURCE_BINDING_SCHEMA_ID,
        "envelope_version": MMCIF_POLYMER_COMPONENT_TOPOLOGY_ENVELOPE_VERSION,
        "parser_version": MMCIF_POLYMER_COMPONENT_TOPOLOGY_PARSER_VERSION,
        "profile_id": MMCIF_POLYMER_COMPONENT_TOPOLOGY_PROFILE_ID,
        "parser_pedigree_id": (MMCIF_POLYMER_COMPONENT_TOPOLOGY_PARSER_PEDIGREE_ID),
        "full_source_sha256": _sha256_bytes(state.full_source),
        "source_id_sha256": _source_id_sha256(state.source_id),
        "carrier_source_sha256": _sha256_bytes(state.carrier_source),
        "carrier_full_source_sha256": state.carrier_ingest.full_source_sha256,
        "carrier_record_state_sha256": state.carrier_ingest.record_state_sha256,
        "carrier_base_system_snapshot_sha256": (
            state.carrier_ingest.base_system_snapshot_sha256
        ),
        "component_projection_sha256": _sha256_bytes(state.projection_bytes),
        "augmented_system_snapshot_sha256": _sha256_bytes(state.system_snapshot),
        "augmented_system_provenance_source_sha256": (system.provenance.source_sha256),
        "augmented_system_parser_observation_sha256": (
            system.provenance.metadata.get("parser_observation_sha256")
        ),
        "provenance_source_sha256_semantics": "raw_full_source_bytes",
        "canonical_output_sha256": _sha256_bytes(state.canonical_output),
        "topology_state_sha256": _sha256_bytes(state.topology_state_bytes),
        **_authority_false_document(),
    }


def _source_binding_document(state: _ParsedState) -> dict[str, Any]:
    return json.loads(state.source_binding_bytes.decode("ascii"))


def _parse_state(data: bytes, *, source_id: str) -> _ParsedState:
    _source_id_sha256(source_id)
    block = _parse_block(data)
    loops = _validate_surface(block)
    components, component_atoms, component_bonds = _parse_component_rows(loops)
    carrier_source = _carrier_source(block, loops)
    try:
        carrier = parse_mmcif_polymer_sequence(carrier_source, source_id=source_id)
    except MmcifPolymerSequenceError as exc:
        raise MmcifPolymerComponentTopologyError(
            "carrier_sequence_rejected",
            "the unchanged polymer-sequence carrier rejected its exact projection",
            line_number=exc.line_number,
        ) from None
    try:
        # Normalize only the unchanged four-category carrier.  The augmented
        # public system remains provenance-bound to the exact raw seven-category
        # input, while its topology-state document is source-format independent.
        carrier_source = emit_mmcif_polymer_sequence(carrier).payload
        carrier = parse_mmcif_polymer_sequence(carrier_source, source_id=source_id)
        _validate_exact_polymer_instances(loops, carrier)
        _validate_component_coverage(carrier, components)
        canonical_output = _canonical_output(
            carrier, components, component_atoms, component_bonds
        )
        system = _materialize_system(
            carrier,
            components,
            component_atoms,
            component_bonds,
            full_source=data,
            canonical_output=canonical_output,
        )
        projection = _component_projection_document(
            components,
            component_atoms,
            component_bonds,
            carrier_sequence_projection_sha256=carrier.polymer_sequence_projection_sha256,
        )
        projection_bytes = _canonical_json_bytes(projection)
        if (
            len(projection_bytes)
            > MAX_MMCIF_POLYMER_COMPONENT_TOPOLOGY_PROJECTION_BYTES
        ):
            raise MmcifPolymerComponentTopologyError(
                "projection_too_large", "component projection exceeds the byte limit"
            )
        state = _ParsedState(
            full_source=data,
            source_id=source_id,
            carrier_source=carrier_source,
            carrier_ingest=carrier,
            carrier_object_id=id(carrier),
            component_rows=components,
            component_atom_rows=component_atoms,
            component_bond_rows=component_bonds,
            projection_bytes=projection_bytes,
            system_snapshot=serialize_all_atom_system(system),
            canonical_output=canonical_output,
            topology_state_bytes=b"",
            source_binding_bytes=b"",
        )
        state = replace(
            state,
            topology_state_bytes=_canonical_json_bytes(
                _compute_topology_state_document(state)
            ),
        )
        return replace(
            state,
            source_binding_bytes=_canonical_json_bytes(
                _compute_source_binding_document(state)
            ),
        )
    except MmcifPolymerComponentTopologyError:
        raise
    except Exception:
        raise MmcifPolymerComponentTopologyError(
            "component_topology_integration_failed",
            "component topology integration failed closed",
        ) from None


def _state_access_binding_document(state: _ParsedState) -> dict[str, Any]:
    byte_fields = {
        "full_source": state.full_source,
        "carrier_source": state.carrier_source,
        "projection": state.projection_bytes,
        "system_snapshot": state.system_snapshot,
        "canonical_output": state.canonical_output,
        "topology_state": state.topology_state_bytes,
        "source_binding": state.source_binding_bytes,
    }
    if any(type(value) is not bytes for value in byte_fields.values()):
        raise TypeError("bound ingest byte fields must remain exact bytes")
    if (
        type(state.carrier_ingest) is not MmcifPolymerSequenceIngestResult
        or id(state.carrier_ingest) != state.carrier_object_id
    ):
        raise TypeError("bound polymer-sequence carrier object is inconsistent")
    if type(state.carrier_ingest.sequence_rows) is not tuple or any(
        type(row) is not MmcifPolymerSequenceRow
        or type(row.entity_id) is not str
        or type(row.num) is not int
        or type(row.mon_id) is not str
        or type(row.hetero) is not str
        or type(row.coordinate_observed) is not bool
        or type(row.observed_asym_ids) is not tuple
        or any(type(asym_id) is not str for asym_id in row.observed_asym_ids)
        for row in state.carrier_ingest.sequence_rows
    ):
        raise TypeError("bound polymer-sequence rows are inconsistent")
    carrier_sequence_rows = [
        {
            "entity_id": row.entity_id,
            "num": row.num,
            "mon_id": row.mon_id,
            "hetero": row.hetero,
            "coordinate_observed": row.coordinate_observed,
            "observed_asym_ids": list(row.observed_asym_ids),
        }
        for row in state.carrier_ingest.sequence_rows
    ]
    if type(state.component_rows) is not tuple:
        raise TypeError("bound component rows must remain an exact tuple")
    component_row_content: list[dict[str, Any]] = []
    for row in state.component_rows:
        if (
            type(row) is not MmcifPolymerComponentRow
            or type(row.comp_id) is not str
            or type(row.component_type) is not str
            or type(row.formal_charge) is not int
        ):
            raise TypeError("bound component row fields are not exact")
        component_row_content.append(
            {
                "comp_id": row.comp_id,
                "component_type": row.component_type,
                "formal_charge": row.formal_charge,
            }
        )
    if type(state.component_atom_rows) is not tuple:
        raise TypeError("bound component atom rows must remain an exact tuple")
    component_atom_row_content: list[dict[str, Any]] = []
    for row in state.component_atom_rows:
        if (
            type(row) is not MmcifPolymerComponentAtomRow
            or type(row.comp_id) is not str
            or type(row.atom_id) is not str
            or type(row.element) is not str
            or type(row.charge) is not int
            or type(row.aromatic) is not bool
            or type(row.stereo) is not str
            or type(row.ordinal) is not int
        ):
            raise TypeError("bound component atom row fields are not exact")
        component_atom_row_content.append(
            {
                "comp_id": row.comp_id,
                "atom_id": row.atom_id,
                "element": row.element,
                "charge": row.charge,
                "aromatic": row.aromatic,
                "stereo": row.stereo,
                "ordinal": row.ordinal,
            }
        )
    if type(state.component_bond_rows) is not tuple:
        raise TypeError("bound component bond rows must remain an exact tuple")
    component_bond_row_content: list[dict[str, Any]] = []
    for row in state.component_bond_rows:
        if (
            type(row) is not MmcifPolymerComponentBondRow
            or type(row.comp_id) is not str
            or type(row.atom_id_1) is not str
            or type(row.atom_id_2) is not str
            or type(row.value_order) is not str
            or type(row.order) is not float
            or type(row.aromatic) is not bool
            or type(row.stereo) is not str
            or type(row.ordinal) is not int
        ):
            raise TypeError("bound component bond row fields are not exact")
        component_bond_row_content.append(
            {
                "comp_id": row.comp_id,
                "atom_id_1": row.atom_id_1,
                "atom_id_2": row.atom_id_2,
                "value_order": row.value_order,
                "order_hex": row.order.hex(),
                "aromatic": row.aromatic,
                "stereo": row.stereo,
                "ordinal": row.ordinal,
            }
        )
    component_row_content_bytes = _canonical_json_bytes({"rows": component_row_content})
    component_atom_row_content_bytes = _canonical_json_bytes(
        {"rows": component_atom_row_content}
    )
    component_bond_row_content_bytes = _canonical_json_bytes(
        {"rows": component_bond_row_content}
    )
    _source_id_sha256(state.source_id)
    return {
        "byte_objects": {
            name: {
                "object_id": id(value),
                "byte_count": len(value),
                "sha256": _sha256_bytes(value),
            }
            for name, value in byte_fields.items()
        },
        "source_id_object_id": id(state.source_id),
        "source_id_sha256": _source_id_sha256(state.source_id),
        "carrier": {
            "object_id": id(state.carrier_ingest),
            "full_source_object_id": id(state.carrier_ingest._full_source_bytes),
            "full_source_sha256": _sha256_bytes(
                state.carrier_ingest._full_source_bytes
            ),
            "carrier_source_object_id": id(state.carrier_ingest._carrier_source_bytes),
            "carrier_source_sha256": _sha256_bytes(
                state.carrier_ingest._carrier_source_bytes
            ),
            "canonical_carrier_source_object_id": id(
                state.carrier_ingest._canonical_carrier_source_bytes
            ),
            "canonical_carrier_source_sha256": _sha256_bytes(
                state.carrier_ingest._canonical_carrier_source_bytes
            ),
            "system_snapshot_object_id": id(
                state.carrier_ingest._system_snapshot_payload
            ),
            "system_snapshot_sha256": _sha256_bytes(
                state.carrier_ingest._system_snapshot_payload
            ),
            "base_system_snapshot_sha256": (
                state.carrier_ingest.base_system_snapshot_sha256
            ),
            "base_topology_sha256": state.carrier_ingest.base_topology_sha256,
            "base_representable_state_sha256": (
                state.carrier_ingest.base_representable_state_sha256
            ),
            "polymer_sequence_projection_sha256": (
                state.carrier_ingest.polymer_sequence_projection_sha256
            ),
            "record_state_sha256": state.carrier_ingest.record_state_sha256,
            "source_binding_sha256": state.carrier_ingest.source_binding_sha256,
            "source_id_sha256": state.carrier_ingest.source_id_sha256,
            "data_block_name": state.carrier_ingest.data_block_name,
            "carrier_kind": state.carrier_ingest.carrier_kind,
            "sequence_rows_object_id": id(state.carrier_ingest.sequence_rows),
            "sequence_rows": carrier_sequence_rows,
            "nonpoly_identity_projection_sha256": (
                state.carrier_ingest.nonpoly_identity_projection_sha256
            ),
            "nonpoly_identity_record_state_sha256": (
                state.carrier_ingest.nonpoly_identity_record_state_sha256
            ),
        },
        "component_rows": {
            "object_id": id(state.component_rows),
            "row_count": len(state.component_rows),
            "content_sha256": _sha256_bytes(component_row_content_bytes),
        },
        "component_atom_rows": {
            "object_id": id(state.component_atom_rows),
            "row_count": len(state.component_atom_rows),
            "content_sha256": _sha256_bytes(component_atom_row_content_bytes),
        },
        "component_bond_rows": {
            "object_id": id(state.component_bond_rows),
            "row_count": len(state.component_bond_rows),
            "content_sha256": _sha256_bytes(component_bond_row_content_bytes),
        },
    }


def _register_ingest_state_anchor(
    value: "MmcifPolymerComponentTopologyIngestResult", state: _ParsedState
) -> None:
    key = id(value)

    def discard(reference: weakref.ReferenceType[Any]) -> None:
        current = _INGEST_STATE_ANCHORS.get(key)
        if current is not None and current[0] is reference:
            _INGEST_STATE_ANCHORS.pop(key, None)

    reference = weakref.ref(value, discard)
    _INGEST_STATE_ANCHORS[key] = (reference, state)


def _ingest_state_anchor(
    value: "MmcifPolymerComponentTopologyIngestResult",
) -> _ParsedState:
    current = _INGEST_STATE_ANCHORS.get(id(value))
    if (
        current is None
        or current[0]() is not value
        or type(current[1]) is not _ParsedState
    ):
        raise ValueError("ingest has no live factory state anchor")
    return current[1]


def _register_factory_artifact_anchor(value: Any, access_binding: bytes) -> None:
    if type(access_binding) is not bytes:
        raise TypeError("factory artifact access binding must be exact bytes")
    key = id(value)

    def discard(reference: weakref.ReferenceType[Any]) -> None:
        current = _FACTORY_ARTIFACT_ANCHORS.get(key)
        if current is not None and current[0] is reference:
            _FACTORY_ARTIFACT_ANCHORS.pop(key, None)

    reference = weakref.ref(value, discard)
    _FACTORY_ARTIFACT_ANCHORS[key] = (reference, access_binding)


def _validate_factory_artifact_anchor(
    value: Any, current_access_binding: bytes
) -> None:
    current = _FACTORY_ARTIFACT_ANCHORS.get(id(value))
    stored_access_binding = getattr(value, "_access_binding_bytes")
    if (
        type(current_access_binding) is not bytes
        or current is None
        or current[0]() is not value
        or type(current[1]) is not bytes
        or type(stored_access_binding) is not bytes
        or stored_access_binding is not current[1]
        or stored_access_binding != current_access_binding
    ):
        raise ValueError("artifact has no live factory access anchor")


@dataclass(frozen=True, init=False)
class MmcifPolymerComponentTopologyIngestResult:
    _full_source: bytes = field(repr=False)
    _source_id: str = field(repr=False)
    _carrier_source: bytes = field(repr=False)
    _carrier_ingest: MmcifPolymerSequenceIngestResult = field(repr=False)
    _carrier_object_id: int = field(repr=False)
    _component_rows: tuple[MmcifPolymerComponentRow, ...] = field(repr=False)
    _component_atom_rows: tuple[MmcifPolymerComponentAtomRow, ...] = field(repr=False)
    _component_bond_rows: tuple[MmcifPolymerComponentBondRow, ...] = field(repr=False)
    _projection_bytes: bytes = field(repr=False)
    _system_snapshot: bytes = field(repr=False)
    _canonical_output: bytes = field(repr=False)
    _topology_state_bytes: bytes = field(repr=False)
    _source_binding_bytes: bytes = field(repr=False)
    _access_binding_bytes: bytes = field(repr=False)

    def __init__(
        self, state: _ParsedState, *, _factory_token: object | None = None
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise TypeError("MmcifPolymerComponentTopologyIngestResult is factory-only")
        if type(state) is not _ParsedState:
            raise TypeError("ingest construction requires exact private parsed state")
        for name in (
            "full_source",
            "source_id",
            "carrier_source",
            "carrier_ingest",
            "carrier_object_id",
            "component_rows",
            "component_atom_rows",
            "component_bond_rows",
            "projection_bytes",
            "system_snapshot",
            "canonical_output",
            "topology_state_bytes",
            "source_binding_bytes",
        ):
            object.__setattr__(self, f"_{name}", getattr(state, name))
        object.__setattr__(
            self,
            "_access_binding_bytes",
            _canonical_json_bytes(_state_access_binding_document(state)),
        )
        _register_factory_artifact_anchor(self, self._access_binding_bytes)
        _register_ingest_state_anchor(self, state)

    @property
    def system(self) -> AllAtomSystem:
        return deserialize_all_atom_system(_validate_fresh_ingest(self).system_snapshot)

    @property
    def carrier_ingest(self) -> MmcifPolymerSequenceIngestResult:
        state = _validate_fresh_ingest(self)
        return parse_mmcif_polymer_sequence(
            state.carrier_source, source_id=state.source_id
        )

    @property
    def component_rows(self) -> tuple[MmcifPolymerComponentRow, ...]:
        rows = _validate_fresh_ingest(self).component_rows
        return tuple(
            MmcifPolymerComponentRow(
                comp_id=row.comp_id,
                component_type=row.component_type,
                formal_charge=row.formal_charge,
                _factory_token=_FACTORY_TOKEN,
            )
            for row in rows
        )

    @property
    def chem_comp_rows(self) -> tuple[MmcifPolymerComponentRow, ...]:
        return self.component_rows

    @property
    def component_atom_rows(self) -> tuple[MmcifPolymerComponentAtomRow, ...]:
        rows = _validate_fresh_ingest(self).component_atom_rows
        return tuple(
            MmcifPolymerComponentAtomRow(
                comp_id=row.comp_id,
                atom_id=row.atom_id,
                element=row.element,
                charge=row.charge,
                aromatic=row.aromatic,
                stereo=row.stereo,
                ordinal=row.ordinal,
                _factory_token=_FACTORY_TOKEN,
            )
            for row in rows
        )

    @property
    def chem_comp_atom_rows(self) -> tuple[MmcifPolymerComponentAtomRow, ...]:
        return self.component_atom_rows

    @property
    def component_bond_rows(self) -> tuple[MmcifPolymerComponentBondRow, ...]:
        rows = _validate_fresh_ingest(self).component_bond_rows
        return tuple(
            MmcifPolymerComponentBondRow(
                comp_id=row.comp_id,
                atom_id_1=row.atom_id_1,
                atom_id_2=row.atom_id_2,
                value_order=row.value_order,
                order=row.order,
                aromatic=row.aromatic,
                stereo=row.stereo,
                ordinal=row.ordinal,
                _factory_token=_FACTORY_TOKEN,
            )
            for row in rows
        )

    @property
    def chem_comp_bond_rows(self) -> tuple[MmcifPolymerComponentBondRow, ...]:
        return self.component_bond_rows

    @property
    def full_source_sha256(self) -> str:
        return str(
            _source_binding_document(_validate_fresh_ingest(self))["full_source_sha256"]
        )

    @property
    def source_id_sha256(self) -> str:
        return str(
            _source_binding_document(_validate_fresh_ingest(self))["source_id_sha256"]
        )

    @property
    def component_projection_sha256(self) -> str:
        return _sha256_bytes(_validate_fresh_ingest(self).projection_bytes)

    @property
    def topology_state_sha256(self) -> str:
        return _sha256_bytes(_validate_fresh_ingest(self).topology_state_bytes)

    @property
    def record_state_sha256(self) -> str:
        return self.topology_state_sha256

    @property
    def source_binding_sha256(self) -> str:
        return _sha256_bytes(_validate_fresh_ingest(self).source_binding_bytes)

    @property
    def augmented_system_snapshot_sha256(self) -> str:
        return str(
            _source_binding_document(_validate_fresh_ingest(self))[
                "augmented_system_snapshot_sha256"
            ]
        )

    @property
    def system_snapshot_sha256(self) -> str:
        return self.augmented_system_snapshot_sha256

    @property
    def augmented_topology_sha256(self) -> str:
        return str(
            _topology_state_document(_validate_fresh_ingest(self))[
                "augmented_topology_sha256"
            ]
        )

    @property
    def topology_sha256(self) -> str:
        return self.augmented_topology_sha256

    @property
    def base_representable_state_sha256(self) -> str:
        return self.carrier_ingest.base_representable_state_sha256

    def to_dict(self) -> dict[str, Any]:
        state = _validate_fresh_ingest(self)
        source_binding = _source_binding_document(state)
        return {
            **_topology_state_document(state),
            "full_source_sha256": source_binding["full_source_sha256"],
            "source_id_sha256": source_binding["source_id_sha256"],
            "carrier_base_system_snapshot_sha256": source_binding[
                "carrier_base_system_snapshot_sha256"
            ],
            "augmented_system_snapshot_sha256": source_binding[
                "augmented_system_snapshot_sha256"
            ],
            "augmented_system_provenance_source_sha256": source_binding[
                "augmented_system_provenance_source_sha256"
            ],
            "canonical_output_sha256": source_binding["canonical_output_sha256"],
            "augmented_system_parser_observation_sha256": source_binding[
                "augmented_system_parser_observation_sha256"
            ],
            "source_binding_sha256": _sha256_bytes(state.source_binding_bytes),
            "topology_state_sha256": _sha256_bytes(state.topology_state_bytes),
        }


def _state_from_ingest(
    value: MmcifPolymerComponentTopologyIngestResult,
) -> _ParsedState:
    return _ParsedState(
        full_source=value._full_source,
        source_id=value._source_id,
        carrier_source=value._carrier_source,
        carrier_ingest=value._carrier_ingest,
        carrier_object_id=value._carrier_object_id,
        component_rows=value._component_rows,
        component_atom_rows=value._component_atom_rows,
        component_bond_rows=value._component_bond_rows,
        projection_bytes=value._projection_bytes,
        system_snapshot=value._system_snapshot,
        canonical_output=value._canonical_output,
        topology_state_bytes=value._topology_state_bytes,
        source_binding_bytes=value._source_binding_bytes,
    )


def _validate_fresh_ingest(
    value: MmcifPolymerComponentTopologyIngestResult,
) -> _ParsedState:
    if type(value) is not MmcifPolymerComponentTopologyIngestResult:
        raise TypeError("an exact polymer component topology ingest result is required")
    try:
        stored = _state_from_ingest(value)
        anchor = _ingest_state_anchor(value)
        stored_access = _canonical_json_bytes(_state_access_binding_document(stored))
        anchor_access = _canonical_json_bytes(_state_access_binding_document(anchor))
        _validate_factory_artifact_anchor(value, stored_access)
        projection = _component_projection_document(
            stored.component_rows,
            stored.component_atom_rows,
            stored.component_bond_rows,
            carrier_sequence_projection_sha256=(
                stored.carrier_ingest.polymer_sequence_projection_sha256
            ),
        )
        topology_state = _topology_state_document(stored)
        source_binding = _source_binding_document(stored)
    except Exception:
        raise MmcifPolymerComponentTopologyError(
            "stale_ingest_binding", "stored ingest evidence differs from factory state"
        ) from None
    if (
        stored != anchor
        or stored_access != anchor_access
        or type(value._access_binding_bytes) is not bytes
        or value._access_binding_bytes != anchor_access
        or stored.carrier_object_id != id(stored.carrier_ingest)
        or stored.carrier_source != stored.carrier_ingest._full_source_bytes
        or stored.projection_bytes != _canonical_json_bytes(projection)
        or topology_state.get("component_projection_sha256")
        != _sha256_bytes(stored.projection_bytes)
        or topology_state.get("carrier_sequence_projection_sha256")
        != stored.carrier_ingest.polymer_sequence_projection_sha256
        or topology_state.get("carrier_record_state_sha256")
        != stored.carrier_ingest.record_state_sha256
        or topology_state.get("attached_canonical_topology_digest_self_consistent")
        is not True
        or topology_state.get("attached_parser_observation_digest_self_consistent")
        is not True
        or topology_state.get("new_system_parser_pedigree_introduced") is not True
        or any(
            topology_state.get(name) is not False for name in _FALSE_AUTHORITY_FIELDS
        )
        or source_binding.get("full_source_sha256") != _sha256_bytes(stored.full_source)
        or source_binding.get("source_id_sha256") != _source_id_sha256(stored.source_id)
        or source_binding.get("carrier_source_sha256")
        != _sha256_bytes(stored.carrier_source)
        or source_binding.get("component_projection_sha256")
        != _sha256_bytes(stored.projection_bytes)
        or source_binding.get("augmented_system_snapshot_sha256")
        != _sha256_bytes(stored.system_snapshot)
        or source_binding.get("canonical_output_sha256")
        != _sha256_bytes(stored.canonical_output)
        or source_binding.get("topology_state_sha256")
        != _sha256_bytes(stored.topology_state_bytes)
        or any(
            source_binding.get(name) is not False for name in _FALSE_AUTHORITY_FIELDS
        )
    ):
        raise MmcifPolymerComponentTopologyError(
            "stale_ingest_binding", "stored ingest evidence differs from factory state"
        )
    return stored


def parse_mmcif_polymer_component_topology(
    data: bytes, *, source_id: str = ""
) -> MmcifPolymerComponentTopologyIngestResult:
    """Parse the exact seven-category polymer component-topology envelope."""

    state = _parse_state(data, source_id=source_id)
    return MmcifPolymerComponentTopologyIngestResult(
        state, _factory_token=_FACTORY_TOKEN
    )


def mmcif_polymer_component_topology_projection_sha256(
    value: MmcifPolymerComponentTopologyIngestResult,
) -> str:
    return _sha256_bytes(_validate_fresh_ingest(value).projection_bytes)


def mmcif_polymer_component_topology_state_sha256(
    value: MmcifPolymerComponentTopologyIngestResult,
) -> str:
    return _sha256_bytes(_validate_fresh_ingest(value).topology_state_bytes)


def mmcif_polymer_component_topology_record_state_sha256(
    value: MmcifPolymerComponentTopologyIngestResult,
) -> str:
    return mmcif_polymer_component_topology_state_sha256(value)


def _receipt_document(state: _ParsedState, payload: bytes) -> dict[str, Any]:
    topology = _topology_state_document(state)
    source_binding = _source_binding_document(state)
    return {
        "schema_id": MMCIF_POLYMER_COMPONENT_TOPOLOGY_WRITE_RECEIPT_SCHEMA_ID,
        "envelope_version": MMCIF_POLYMER_COMPONENT_TOPOLOGY_ENVELOPE_VERSION,
        "parser_version": MMCIF_POLYMER_COMPONENT_TOPOLOGY_PARSER_VERSION,
        "writer_version": MMCIF_POLYMER_COMPONENT_TOPOLOGY_WRITER_VERSION,
        "profile_id": MMCIF_POLYMER_COMPONENT_TOPOLOGY_PROFILE_ID,
        "input_source_binding_sha256": _sha256_bytes(state.source_binding_bytes),
        "input_topology_state_sha256": _sha256_bytes(state.topology_state_bytes),
        "input_component_projection_sha256": _sha256_bytes(state.projection_bytes),
        "input_augmented_system_snapshot_sha256": source_binding[
            "augmented_system_snapshot_sha256"
        ],
        "input_augmented_topology_sha256": topology["augmented_topology_sha256"],
        "carrier_base_representable_state_sha256": topology[
            "carrier_base_representable_state_sha256"
        ],
        "output_source_sha256": _sha256_bytes(payload),
        "output_byte_count": len(payload),
        "component_count": len(state.component_rows),
        "component_atom_row_count": len(state.component_atom_rows),
        "component_bond_row_count": len(state.component_bond_rows),
        "materialized_bond_count": topology["materialized_bond_count"],
        "source_reported_component_topology_materialized": True,
        **_authority_false_document(),
    }


def _write_receipt_access_binding_document(
    value: "MmcifPolymerComponentTopologyWriteReceipt",
) -> dict[str, Any]:
    if (
        type(value) is not MmcifPolymerComponentTopologyWriteReceipt
        or type(value._ingest) is not MmcifPolymerComponentTopologyIngestResult
        or type(value._payload) is not bytes
        or type(value._document_bytes) is not bytes
    ):
        raise TypeError("write receipt access fields are not exact")
    return {
        "artifact_type": "MmcifPolymerComponentTopologyWriteReceipt",
        "self_object_id": id(value),
        "ingest_object_id": id(value._ingest),
        "payload_object_id": id(value._payload),
        "payload_sha256": _sha256_bytes(value._payload),
        "document_object_id": id(value._document_bytes),
        "document_sha256": _sha256_bytes(value._document_bytes),
    }


@dataclass(frozen=True, init=False)
class MmcifPolymerComponentTopologyWriteReceipt:
    _ingest: MmcifPolymerComponentTopologyIngestResult = field(repr=False)
    _payload: bytes = field(repr=False)
    _document_bytes: bytes = field(repr=False)
    _access_binding_bytes: bytes = field(repr=False)

    def __init__(
        self,
        ingest: MmcifPolymerComponentTopologyIngestResult,
        payload: bytes,
        document: Mapping[str, Any],
        *,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise TypeError("MmcifPolymerComponentTopologyWriteReceipt is factory-only")
        state = _validate_fresh_ingest(ingest)
        expected = _receipt_document(state, payload)
        if dict(document) != expected or payload != state.canonical_output:
            raise MmcifPolymerComponentTopologyError(
                "invalid_write_receipt", "write receipt does not bind canonical output"
            )
        object.__setattr__(self, "_ingest", ingest)
        object.__setattr__(self, "_payload", payload)
        object.__setattr__(self, "_document_bytes", _canonical_json_bytes(expected))
        access_binding = _canonical_json_bytes(
            _write_receipt_access_binding_document(self)
        )
        object.__setattr__(self, "_access_binding_bytes", access_binding)
        _register_factory_artifact_anchor(self, access_binding)

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
        return {**document, "receipt_sha256": _sha256_bytes(self._document_bytes)}


def _validate_receipt(
    value: MmcifPolymerComponentTopologyWriteReceipt,
) -> dict[str, Any]:
    if type(value) is not MmcifPolymerComponentTopologyWriteReceipt:
        raise TypeError("an exact polymer component topology receipt is required")
    try:
        _validate_factory_artifact_anchor(
            value,
            _canonical_json_bytes(_write_receipt_access_binding_document(value)),
        )
        state = _validate_fresh_ingest(value._ingest)
        expected = _receipt_document(state, value._payload)
        expected_bytes = _canonical_json_bytes(expected)
    except Exception:
        raise MmcifPolymerComponentTopologyError(
            "stale_write_receipt_binding", "write receipt artifacts are stale"
        ) from None
    if (
        type(value._payload) is not bytes
        or value._payload != state.canonical_output
        or type(value._document_bytes) is not bytes
        or value._document_bytes != expected_bytes
    ):
        raise MmcifPolymerComponentTopologyError(
            "stale_write_receipt_binding", "write receipt artifacts are stale"
        )
    return expected


def _write_binding_document(
    ingest: MmcifPolymerComponentTopologyIngestResult,
    payload: bytes,
    receipt: MmcifPolymerComponentTopologyWriteReceipt,
) -> dict[str, Any]:
    state = _validate_fresh_ingest(ingest)
    _validate_receipt(receipt)
    return {
        "ingest_object_id": id(ingest),
        "receipt_object_id": id(receipt),
        "receipt_ingest_object_id": id(receipt._ingest),
        "source_binding_sha256": _sha256_bytes(state.source_binding_bytes),
        "topology_state_sha256": _sha256_bytes(state.topology_state_bytes),
        "payload_sha256": _sha256_bytes(payload),
        "receipt_sha256": receipt.receipt_sha256,
    }


def _write_result_access_binding_document(
    value: "MmcifPolymerComponentTopologyWriteResult",
) -> dict[str, Any]:
    if (
        type(value) is not MmcifPolymerComponentTopologyWriteResult
        or type(value._ingest) is not MmcifPolymerComponentTopologyIngestResult
        or type(value._payload) is not bytes
        or type(value._receipt) is not MmcifPolymerComponentTopologyWriteReceipt
        or type(value._raw_binding_bytes) is not bytes
    ):
        raise TypeError("write result access fields are not exact")
    return {
        "artifact_type": "MmcifPolymerComponentTopologyWriteResult",
        "self_object_id": id(value),
        "ingest_object_id": id(value._ingest),
        "payload_object_id": id(value._payload),
        "payload_sha256": _sha256_bytes(value._payload),
        "receipt_object_id": id(value._receipt),
        "raw_binding_object_id": id(value._raw_binding_bytes),
        "raw_binding_sha256": _sha256_bytes(value._raw_binding_bytes),
    }


@dataclass(frozen=True, init=False)
class MmcifPolymerComponentTopologyWriteResult:
    _ingest: MmcifPolymerComponentTopologyIngestResult = field(repr=False)
    _payload: bytes = field(repr=False)
    _receipt: MmcifPolymerComponentTopologyWriteReceipt = field(repr=False)
    _raw_binding_bytes: bytes = field(repr=False)
    _access_binding_bytes: bytes = field(repr=False)

    def __init__(
        self,
        ingest: MmcifPolymerComponentTopologyIngestResult,
        payload: bytes,
        receipt: MmcifPolymerComponentTopologyWriteReceipt,
        *,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise TypeError("MmcifPolymerComponentTopologyWriteResult is factory-only")
        if (
            type(payload) is not bytes
            or type(receipt) is not MmcifPolymerComponentTopologyWriteReceipt
        ):
            raise TypeError("write result requires exact payload and receipt artifacts")
        binding = _write_binding_document(ingest, payload, receipt)
        object.__setattr__(self, "_ingest", ingest)
        object.__setattr__(self, "_payload", payload)
        object.__setattr__(self, "_receipt", receipt)
        object.__setattr__(self, "_raw_binding_bytes", _canonical_json_bytes(binding))
        access_binding = _canonical_json_bytes(
            _write_result_access_binding_document(self)
        )
        object.__setattr__(self, "_access_binding_bytes", access_binding)
        _register_factory_artifact_anchor(self, access_binding)

    @property
    def payload(self) -> bytes:
        _validate_write_result(self)
        return self._payload

    @property
    def receipt(self) -> MmcifPolymerComponentTopologyWriteReceipt:
        _validate_write_result(self)
        fresh_ingest = parse_mmcif_polymer_component_topology(
            self._ingest._full_source, source_id=self._ingest._source_id
        )
        return write_mmcif_polymer_component_topology(fresh_ingest)._receipt

    def to_dict(self) -> dict[str, Any]:
        _validate_write_result(self)
        return {
            "output_source_sha256": _sha256_bytes(self._payload),
            "output_byte_count": len(self._payload),
            "receipt": self._receipt.to_dict(),
            **_authority_false_document(),
        }


def _validate_write_result(value: MmcifPolymerComponentTopologyWriteResult) -> None:
    if type(value) is not MmcifPolymerComponentTopologyWriteResult:
        raise TypeError("an exact polymer component topology write result is required")
    try:
        _validate_factory_artifact_anchor(
            value,
            _canonical_json_bytes(_write_result_access_binding_document(value)),
        )
        state = _validate_fresh_ingest(value._ingest)
        _validate_receipt(value._receipt)
        binding = _write_binding_document(value._ingest, value._payload, value._receipt)
    except Exception:
        raise MmcifPolymerComponentTopologyError(
            "stale_write_result_binding", "write result artifacts are stale"
        ) from None
    if (
        value._payload != state.canonical_output
        or value._receipt._ingest is not value._ingest
        or value._receipt._payload is not value._payload
        or value._raw_binding_bytes != _canonical_json_bytes(binding)
    ):
        raise MmcifPolymerComponentTopologyError(
            "stale_write_result_binding", "write result artifacts are stale"
        )


def write_mmcif_polymer_component_topology(
    value: MmcifPolymerComponentTopologyIngestResult,
) -> MmcifPolymerComponentTopologyWriteResult:
    """Emit the deterministic seven-category canonical representation."""

    state = _validate_fresh_ingest(value)
    payload = state.canonical_output
    reparsed = _parse_state(payload, source_id=state.source_id)
    if (
        reparsed.projection_bytes != state.projection_bytes
        or reparsed.topology_state_bytes != state.topology_state_bytes
        or reparsed.canonical_output != payload
    ):
        raise MmcifPolymerComponentTopologyError(
            "round_trip_mismatch",
            "canonical output does not recover the bound topology state",
        )
    receipt = MmcifPolymerComponentTopologyWriteReceipt(
        value,
        payload,
        _receipt_document(state, payload),
        _factory_token=_FACTORY_TOKEN,
    )
    return MmcifPolymerComponentTopologyWriteResult(
        value, payload, receipt, _factory_token=_FACTORY_TOKEN
    )


def emit_mmcif_polymer_component_topology(
    value: MmcifPolymerComponentTopologyIngestResult,
) -> MmcifPolymerComponentTopologyWriteResult:
    return write_mmcif_polymer_component_topology(value)


def serialize_mmcif_polymer_component_topology(
    value: MmcifPolymerComponentTopologyIngestResult,
) -> bytes:
    return write_mmcif_polymer_component_topology(value).payload


def _report_document(
    source: MmcifPolymerComponentTopologyIngestResult,
    write_result: MmcifPolymerComponentTopologyWriteResult,
    reparsed: MmcifPolymerComponentTopologyIngestResult,
    second: MmcifPolymerComponentTopologyWriteResult,
) -> dict[str, Any]:
    source_state = _validate_fresh_ingest(source)
    reparsed_state = _validate_fresh_ingest(reparsed)
    _validate_write_result(write_result)
    _validate_write_result(second)
    projection_equal = source_state.projection_bytes == reparsed_state.projection_bytes
    topology_state_equal = (
        source_state.topology_state_bytes == reparsed_state.topology_state_bytes
    )
    topology_equal = (
        _topology_state_document(source_state)["augmented_topology_sha256"]
        == _topology_state_document(reparsed_state)["augmented_topology_sha256"]
    )
    carrier_state_equal = (
        source_state.carrier_ingest.record_state_sha256
        == reparsed_state.carrier_ingest.record_state_sha256
        and source_state.carrier_ingest.base_representable_state_sha256
        == reparsed_state.carrier_ingest.base_representable_state_sha256
    )
    exact_reparse = (
        write_result._payload == reparsed_state.full_source
        and _sha256_bytes(write_result._payload)
        == _source_binding_document(reparsed_state)["full_source_sha256"]
    )
    stable = write_result._payload == second._payload
    preserved = all(
        (
            projection_equal,
            topology_state_equal,
            topology_equal,
            carrier_state_equal,
            exact_reparse,
            stable,
            source_state.source_id == reparsed_state.source_id,
        )
    )
    return {
        "schema_id": MMCIF_POLYMER_COMPONENT_TOPOLOGY_ROUND_TRIP_REPORT_SCHEMA_ID,
        "envelope_version": MMCIF_POLYMER_COMPONENT_TOPOLOGY_ENVELOPE_VERSION,
        "parser_version": MMCIF_POLYMER_COMPONENT_TOPOLOGY_PARSER_VERSION,
        "writer_version": MMCIF_POLYMER_COMPONENT_TOPOLOGY_WRITER_VERSION,
        "profile_id": MMCIF_POLYMER_COMPONENT_TOPOLOGY_PROFILE_ID,
        "source_id_sha256": _source_id_sha256(source_state.source_id),
        "input_source_binding_sha256": _sha256_bytes(source_state.source_binding_bytes),
        "reparsed_source_binding_sha256": _sha256_bytes(
            reparsed_state.source_binding_bytes
        ),
        "input_component_projection_sha256": _sha256_bytes(
            source_state.projection_bytes
        ),
        "reparsed_component_projection_sha256": _sha256_bytes(
            reparsed_state.projection_bytes
        ),
        "input_topology_state_sha256": _sha256_bytes(source_state.topology_state_bytes),
        "reparsed_topology_state_sha256": _sha256_bytes(
            reparsed_state.topology_state_bytes
        ),
        "input_augmented_topology_sha256": _topology_state_document(source_state)[
            "augmented_topology_sha256"
        ],
        "reparsed_augmented_topology_sha256": _topology_state_document(reparsed_state)[
            "augmented_topology_sha256"
        ],
        "write_receipt_sha256": write_result._receipt.receipt_sha256,
        "reemitted_write_receipt_sha256": second._receipt.receipt_sha256,
        "emitted_source_sha256": _sha256_bytes(write_result._payload),
        "reemitted_source_sha256": _sha256_bytes(second._payload),
        "component_projection_equal": projection_equal,
        "topology_state_equal": topology_state_equal,
        "topology_equal": topology_equal,
        "carrier_state_equal": carrier_state_equal,
        "emitted_source_reparsed_exact": exact_reparse,
        "second_emission_byte_stable": stable,
        "source_reported_component_topology_round_trip_preserved": preserved,
        **_authority_false_document(),
    }


def _round_trip_report_access_binding_document(
    value: "MmcifPolymerComponentTopologyRoundTripReport",
) -> dict[str, Any]:
    if (
        type(value) is not MmcifPolymerComponentTopologyRoundTripReport
        or type(value._source_ingest) is not MmcifPolymerComponentTopologyIngestResult
        or type(value._write_result) is not MmcifPolymerComponentTopologyWriteResult
        or type(value._reparsed_ingest) is not MmcifPolymerComponentTopologyIngestResult
        or type(value._reemitted_write_result)
        is not MmcifPolymerComponentTopologyWriteResult
        or type(value._document_bytes) is not bytes
        or type(value._raw_binding_bytes) is not bytes
    ):
        raise TypeError("round-trip report access fields are not exact")
    return {
        "artifact_type": "MmcifPolymerComponentTopologyRoundTripReport",
        "self_object_id": id(value),
        "source_object_id": id(value._source_ingest),
        "write_object_id": id(value._write_result),
        "reparsed_object_id": id(value._reparsed_ingest),
        "reemitted_write_object_id": id(value._reemitted_write_result),
        "document_object_id": id(value._document_bytes),
        "document_sha256": _sha256_bytes(value._document_bytes),
        "raw_binding_object_id": id(value._raw_binding_bytes),
        "raw_binding_sha256": _sha256_bytes(value._raw_binding_bytes),
    }


@dataclass(frozen=True, init=False)
class MmcifPolymerComponentTopologyRoundTripReport:
    _source_ingest: MmcifPolymerComponentTopologyIngestResult = field(repr=False)
    _write_result: MmcifPolymerComponentTopologyWriteResult = field(repr=False)
    _reparsed_ingest: MmcifPolymerComponentTopologyIngestResult = field(repr=False)
    _reemitted_write_result: MmcifPolymerComponentTopologyWriteResult = field(
        repr=False
    )
    _document_bytes: bytes = field(repr=False)
    _raw_binding_bytes: bytes = field(repr=False)
    _access_binding_bytes: bytes = field(repr=False)

    def __init__(
        self,
        source: MmcifPolymerComponentTopologyIngestResult,
        write_result: MmcifPolymerComponentTopologyWriteResult,
        reparsed: MmcifPolymerComponentTopologyIngestResult,
        second: MmcifPolymerComponentTopologyWriteResult,
        document: Mapping[str, Any],
        *,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise TypeError(
                "MmcifPolymerComponentTopologyRoundTripReport is factory-only"
            )
        expected = _report_document(source, write_result, reparsed, second)
        if (
            dict(document) != expected
            or expected["source_reported_component_topology_round_trip_preserved"]
            is not True
        ):
            raise MmcifPolymerComponentTopologyError(
                "crosswired_round_trip_artifacts",
                "round-trip report is not an exact chain",
            )
        object.__setattr__(self, "_source_ingest", source)
        object.__setattr__(self, "_write_result", write_result)
        object.__setattr__(self, "_reparsed_ingest", reparsed)
        object.__setattr__(self, "_reemitted_write_result", second)
        object.__setattr__(self, "_document_bytes", _canonical_json_bytes(expected))
        object.__setattr__(
            self,
            "_raw_binding_bytes",
            _canonical_json_bytes(_report_binding_document(self)),
        )
        access_binding = _canonical_json_bytes(
            _round_trip_report_access_binding_document(self)
        )
        object.__setattr__(self, "_access_binding_bytes", access_binding)
        _register_factory_artifact_anchor(self, access_binding)

    @property
    def report_sha256(self) -> str:
        _validate_report(self)
        return _sha256_bytes(self._document_bytes)

    @property
    def round_trip_report_sha256(self) -> str:
        return self.report_sha256

    @property
    def component_projection_equal(self) -> bool:
        return _validate_report(self)["component_projection_equal"] is True

    @property
    def topology_state_equal(self) -> bool:
        return _validate_report(self)["topology_state_equal"] is True

    @property
    def topology_equal(self) -> bool:
        return _validate_report(self)["topology_equal"] is True

    @property
    def emitted_source_reparsed_exact(self) -> bool:
        return _validate_report(self)["emitted_source_reparsed_exact"] is True

    @property
    def second_emission_byte_stable(self) -> bool:
        return _validate_report(self)["second_emission_byte_stable"] is True

    def to_dict(self) -> dict[str, Any]:
        document = _validate_report(self)
        return {**document, "report_sha256": _sha256_bytes(self._document_bytes)}


def _report_binding_document(
    value: MmcifPolymerComponentTopologyRoundTripReport,
) -> dict[str, Any]:
    _validate_write_result(value._write_result)
    _validate_write_result(value._reemitted_write_result)
    return {
        "source_object_id": id(value._source_ingest),
        "write_object_id": id(value._write_result),
        "reparsed_object_id": id(value._reparsed_ingest),
        "reemitted_write_object_id": id(value._reemitted_write_result),
        "document_object_id": id(value._document_bytes),
        "document_sha256": _sha256_bytes(value._document_bytes),
        "source_binding_sha256": value._source_ingest.source_binding_sha256,
        "write_binding_sha256": _sha256_bytes(value._write_result._raw_binding_bytes),
        "reparsed_source_binding_sha256": value._reparsed_ingest.source_binding_sha256,
        "reemitted_write_binding_sha256": _sha256_bytes(
            value._reemitted_write_result._raw_binding_bytes
        ),
    }


def _validate_report(
    value: MmcifPolymerComponentTopologyRoundTripReport,
) -> dict[str, Any]:
    if type(value) is not MmcifPolymerComponentTopologyRoundTripReport:
        raise TypeError("an exact polymer component topology report is required")
    try:
        _validate_factory_artifact_anchor(
            value,
            _canonical_json_bytes(_round_trip_report_access_binding_document(value)),
        )
        binding = _report_binding_document(value)
        document = json.loads(value._document_bytes.decode("ascii"))
        expected = _report_document(
            value._source_ingest,
            value._write_result,
            value._reparsed_ingest,
            value._reemitted_write_result,
        )
    except Exception:
        raise MmcifPolymerComponentTopologyError(
            "crosswired_round_trip_artifacts", "round-trip artifacts are crosswired"
        ) from None
    if (
        document != expected
        or value._document_bytes != _canonical_json_bytes(expected)
        or value._raw_binding_bytes != _canonical_json_bytes(binding)
        or document.get("source_reported_component_topology_round_trip_preserved")
        is not True
    ):
        raise MmcifPolymerComponentTopologyError(
            "crosswired_round_trip_artifacts", "round-trip artifacts are crosswired"
        )
    return document


def _round_trip_result_access_binding_document(
    value: "MmcifPolymerComponentTopologyRoundTripResult",
) -> dict[str, Any]:
    if (
        type(value) is not MmcifPolymerComponentTopologyRoundTripResult
        or type(value._source_ingest) is not MmcifPolymerComponentTopologyIngestResult
        or type(value._write_result) is not MmcifPolymerComponentTopologyWriteResult
        or type(value._reparsed_ingest) is not MmcifPolymerComponentTopologyIngestResult
        or type(value._reemitted_write_result)
        is not MmcifPolymerComponentTopologyWriteResult
        or type(value._report) is not MmcifPolymerComponentTopologyRoundTripReport
        or type(value._raw_binding_bytes) is not bytes
    ):
        raise TypeError("round-trip result access fields are not exact")
    return {
        "artifact_type": "MmcifPolymerComponentTopologyRoundTripResult",
        "self_object_id": id(value),
        "source_object_id": id(value._source_ingest),
        "write_object_id": id(value._write_result),
        "reparsed_object_id": id(value._reparsed_ingest),
        "reemitted_write_object_id": id(value._reemitted_write_result),
        "report_object_id": id(value._report),
        "raw_binding_object_id": id(value._raw_binding_bytes),
        "raw_binding_sha256": _sha256_bytes(value._raw_binding_bytes),
    }


@dataclass(frozen=True, init=False)
class MmcifPolymerComponentTopologyRoundTripResult:
    _source_ingest: MmcifPolymerComponentTopologyIngestResult = field(repr=False)
    _write_result: MmcifPolymerComponentTopologyWriteResult = field(repr=False)
    _reparsed_ingest: MmcifPolymerComponentTopologyIngestResult = field(repr=False)
    _reemitted_write_result: MmcifPolymerComponentTopologyWriteResult = field(
        repr=False
    )
    _report: MmcifPolymerComponentTopologyRoundTripReport = field(repr=False)
    _raw_binding_bytes: bytes = field(repr=False)
    _access_binding_bytes: bytes = field(repr=False)

    def __init__(
        self,
        source: MmcifPolymerComponentTopologyIngestResult,
        write_result: MmcifPolymerComponentTopologyWriteResult,
        reparsed: MmcifPolymerComponentTopologyIngestResult,
        second: MmcifPolymerComponentTopologyWriteResult,
        report: MmcifPolymerComponentTopologyRoundTripReport,
        *,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise TypeError(
                "MmcifPolymerComponentTopologyRoundTripResult is factory-only"
            )
        binding = _aggregate_binding_document(
            source, write_result, reparsed, second, report
        )
        object.__setattr__(self, "_source_ingest", source)
        object.__setattr__(self, "_write_result", write_result)
        object.__setattr__(self, "_reparsed_ingest", reparsed)
        object.__setattr__(self, "_reemitted_write_result", second)
        object.__setattr__(self, "_report", report)
        object.__setattr__(self, "_raw_binding_bytes", _canonical_json_bytes(binding))
        access_binding = _canonical_json_bytes(
            _round_trip_result_access_binding_document(self)
        )
        object.__setattr__(self, "_access_binding_bytes", access_binding)
        _register_factory_artifact_anchor(self, access_binding)

    @property
    def source_ingest(self) -> MmcifPolymerComponentTopologyIngestResult:
        _validate_aggregate(self)
        return parse_mmcif_polymer_component_topology(
            self._source_ingest._full_source,
            source_id=self._source_ingest._source_id,
        )

    @property
    def write_result(self) -> MmcifPolymerComponentTopologyWriteResult:
        _validate_aggregate(self)
        fresh_ingest = parse_mmcif_polymer_component_topology(
            self._source_ingest._full_source,
            source_id=self._source_ingest._source_id,
        )
        return write_mmcif_polymer_component_topology(fresh_ingest)

    @property
    def reparsed_ingest(self) -> MmcifPolymerComponentTopologyIngestResult:
        _validate_aggregate(self)
        return parse_mmcif_polymer_component_topology(
            self._reparsed_ingest._full_source,
            source_id=self._reparsed_ingest._source_id,
        )

    @property
    def reemitted_write_result(self) -> MmcifPolymerComponentTopologyWriteResult:
        _validate_aggregate(self)
        fresh_ingest = parse_mmcif_polymer_component_topology(
            self._reparsed_ingest._full_source,
            source_id=self._reparsed_ingest._source_id,
        )
        return write_mmcif_polymer_component_topology(fresh_ingest)

    @property
    def report(self) -> MmcifPolymerComponentTopologyRoundTripReport:
        _validate_aggregate(self)
        return round_trip_mmcif_polymer_component_topology_source(
            self._source_ingest._full_source,
            source_id=self._source_ingest._source_id,
        )._report

    def to_dict(self) -> dict[str, Any]:
        _validate_aggregate(self)
        return {
            "source_ingest": self._source_ingest.to_dict(),
            "write_result": self._write_result.to_dict(),
            "reparsed_ingest": self._reparsed_ingest.to_dict(),
            "reemitted_write_result": self._reemitted_write_result.to_dict(),
            "report": self._report.to_dict(),
            **_authority_false_document(),
        }


def _aggregate_binding_document(
    source: MmcifPolymerComponentTopologyIngestResult,
    write_result: MmcifPolymerComponentTopologyWriteResult,
    reparsed: MmcifPolymerComponentTopologyIngestResult,
    second: MmcifPolymerComponentTopologyWriteResult,
    report: MmcifPolymerComponentTopologyRoundTripReport,
) -> dict[str, Any]:
    _validate_report(report)
    if (
        report._source_ingest is not source
        or report._write_result is not write_result
        or report._reparsed_ingest is not reparsed
        or report._reemitted_write_result is not second
        or write_result._ingest is not source
        or second._ingest is not reparsed
    ):
        raise MmcifPolymerComponentTopologyError(
            "crosswired_round_trip_artifacts", "round-trip artifacts are crosswired"
        )
    return {
        "source_object_id": id(source),
        "write_object_id": id(write_result),
        "reparsed_object_id": id(reparsed),
        "reemitted_write_object_id": id(second),
        "report_object_id": id(report),
        "source_binding_sha256": source.source_binding_sha256,
        "write_binding_sha256": _sha256_bytes(write_result._raw_binding_bytes),
        "reparsed_source_binding_sha256": reparsed.source_binding_sha256,
        "reemitted_write_binding_sha256": _sha256_bytes(second._raw_binding_bytes),
        "report_sha256": report.report_sha256,
    }


def _validate_aggregate(value: MmcifPolymerComponentTopologyRoundTripResult) -> None:
    if type(value) is not MmcifPolymerComponentTopologyRoundTripResult:
        raise TypeError(
            "an exact polymer component topology round-trip result is required"
        )
    try:
        _validate_factory_artifact_anchor(
            value,
            _canonical_json_bytes(_round_trip_result_access_binding_document(value)),
        )
        binding = _aggregate_binding_document(
            value._source_ingest,
            value._write_result,
            value._reparsed_ingest,
            value._reemitted_write_result,
            value._report,
        )
    except Exception:
        raise MmcifPolymerComponentTopologyError(
            "crosswired_round_trip_artifacts", "round-trip artifacts are crosswired"
        ) from None
    if value._raw_binding_bytes != _canonical_json_bytes(binding):
        raise MmcifPolymerComponentTopologyError(
            "crosswired_round_trip_artifacts", "round-trip artifacts are crosswired"
        )


def round_trip_mmcif_polymer_component_topology_source(
    data: bytes, *, source_id: str = ""
) -> MmcifPolymerComponentTopologyRoundTripResult:
    source = parse_mmcif_polymer_component_topology(data, source_id=source_id)
    write_result = write_mmcif_polymer_component_topology(source)
    reparsed = parse_mmcif_polymer_component_topology(
        write_result.payload, source_id=source_id
    )
    second = write_mmcif_polymer_component_topology(reparsed)
    document = _report_document(source, write_result, reparsed, second)
    if document["source_reported_component_topology_round_trip_preserved"] is not True:
        raise MmcifPolymerComponentTopologyError(
            "round_trip_mismatch", "component topology did not round trip exactly"
        )
    report = MmcifPolymerComponentTopologyRoundTripReport(
        source,
        write_result,
        reparsed,
        second,
        document,
        _factory_token=_FACTORY_TOKEN,
    )
    return MmcifPolymerComponentTopologyRoundTripResult(
        source,
        write_result,
        reparsed,
        second,
        report,
        _factory_token=_FACTORY_TOKEN,
    )


__all__ = [
    "MAX_MMCIF_POLYMER_COMPONENT_ATOM_ROWS",
    "MAX_MMCIF_POLYMER_COMPONENT_BOND_ROWS",
    "MAX_MMCIF_POLYMER_COMPONENT_MATERIALIZED_BONDS",
    "MAX_MMCIF_POLYMER_COMPONENT_ROWS",
    "MAX_MMCIF_POLYMER_COMPONENT_SEQUENCE_ROWS",
    "MAX_MMCIF_POLYMER_COMPONENT_TOPOLOGY_INPUT_BYTES",
    "MAX_MMCIF_POLYMER_COMPONENT_TOPOLOGY_OUTPUT_BYTES",
    "MAX_MMCIF_POLYMER_COMPONENT_TOPOLOGY_OUTPUT_LINE_CHARS",
    "MAX_MMCIF_POLYMER_COMPONENT_TOPOLOGY_PROJECTION_BYTES",
    "MAX_MMCIF_POLYMER_COMPONENT_TOPOLOGY_SOURCE_ID_BYTES",
    "MAX_MMCIF_POLYMER_COMPONENT_TOPOLOGY_TOKEN_CHARS",
    "MMCIF_POLYMER_COMPONENT_TOPOLOGY_CHEM_COMP_ATOM_HEADERS",
    "MMCIF_POLYMER_COMPONENT_TOPOLOGY_CHEM_COMP_BOND_HEADERS",
    "MMCIF_POLYMER_COMPONENT_TOPOLOGY_CHEM_COMP_HEADERS",
    "MMCIF_POLYMER_COMPONENT_TOPOLOGY_ENVELOPE_VERSION",
    "MMCIF_POLYMER_COMPONENT_TOPOLOGY_PREPARATION_INVENTORY_COMMITMENT_SCHEMA_ID",
    "MMCIF_POLYMER_COMPONENT_TOPOLOGY_PARSER_NAME",
    "MMCIF_POLYMER_COMPONENT_TOPOLOGY_PARSER_PEDIGREE_ID",
    "MMCIF_POLYMER_COMPONENT_TOPOLOGY_PARSER_VERSION",
    "MMCIF_POLYMER_COMPONENT_TOPOLOGY_PROFILE_ID",
    "MMCIF_POLYMER_COMPONENT_TOPOLOGY_PROJECTION_SCHEMA_ID",
    "MMCIF_POLYMER_COMPONENT_TOPOLOGY_ROUND_TRIP_REPORT_SCHEMA_ID",
    "MMCIF_POLYMER_COMPONENT_TOPOLOGY_SOURCE_BINDING_SCHEMA_ID",
    "MMCIF_POLYMER_COMPONENT_TOPOLOGY_STATE_SCHEMA_ID",
    "MMCIF_POLYMER_COMPONENT_TOPOLOGY_WRITER_VERSION",
    "MMCIF_POLYMER_COMPONENT_TOPOLOGY_WRITE_RECEIPT_SCHEMA_ID",
    "MmcifPolymerComponentAtomRow",
    "MmcifPolymerComponentBondRow",
    "MmcifPolymerComponentRow",
    "MmcifPolymerComponentTopologyError",
    "MmcifPolymerComponentTopologyIngestResult",
    "MmcifPolymerComponentTopologyRoundTripReport",
    "MmcifPolymerComponentTopologyRoundTripResult",
    "MmcifPolymerComponentTopologyWriteReceipt",
    "MmcifPolymerComponentTopologyWriteResult",
    "emit_mmcif_polymer_component_topology",
    "mmcif_polymer_component_topology_projection_sha256",
    "mmcif_polymer_component_topology_record_state_sha256",
    "mmcif_polymer_component_topology_state_sha256",
    "parse_mmcif_polymer_component_topology",
    "round_trip_mmcif_polymer_component_topology_source",
    "serialize_mmcif_polymer_component_topology",
    "write_mmcif_polymer_component_topology",
]
