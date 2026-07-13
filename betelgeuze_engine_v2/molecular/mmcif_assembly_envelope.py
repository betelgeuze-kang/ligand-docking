"""Opt-in strict mmCIF biological-assembly round-trip envelope.

The base mmCIF parser and writer intentionally keep biological assemblies
outside their writer contract.  This module composes that unchanged base
writer with three exact PDBx assembly loops.  It writes the deposited
asymmetric unit plus its operators and verifies the explicitly requested
assembly after reparsing; it never flattens an expanded assembly back into an
``_atom_site`` loop.

The envelope preserves a narrow source declaration and the deterministic
expanded atom/chain/coordinate projection.  It does not authenticate the
declaration, establish that the selected assembly is biologically correct, or
grant chemistry, preparation, parameterability, PBC, runtime, or claim
authority.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import itertools
import json
import math
import re
import struct
from typing import Any, Mapping

import torch

from .mmcif_syntax import CifBlock, CifLoop, CifSyntaxError, CifToken, parse_cif_block
from .mmcif_writer import (
    MMCIF_REPRESENTABLE_STATE_SCHEMA_ID,
    MMCIF_WRITER_VERSION,
    MmcifWriteError,
    round_trip_mmcif_source,
)
from .pdb_mmcif import MMCIF_PARSER_VERSION, StructureParseError, parse_mmcif
from .serialization import (
    deserialize_all_atom_system,
    serialize_all_atom_system,
)
from .topology import CANONICAL_TOPOLOGY_SCHEMA_ID, canonical_topology_sha256


MMCIF_ASSEMBLY_ENVELOPE_VERSION = "1.0.0"
MMCIF_ASSEMBLY_PARSER_VERSION = "1.0.0"
MMCIF_ASSEMBLY_WRITER_VERSION = "1.0.0"
MMCIF_ASSEMBLY_PROFILE_ID = (
    "strict_mmcif_single_model_common_core21_explicit_assembly_envelope/1.0.0"
)
MMCIF_ASSEMBLY_PROJECTION_SCOPE = (
    "source_declared_rigid_operator_expansion_and_expanded_identity_coordinates_only"
)
MMCIF_ASSEMBLY_DECLARATION_PROJECTION_SCHEMA_ID = (
    "betelgeuze.mmcif_assembly_declaration_projection/1.0.0"
)
MMCIF_ASSEMBLY_EXPANDED_STATE_SCHEMA_ID = (
    "betelgeuze.mmcif_assembly_expanded_state/1.0.0"
)
MMCIF_ASSEMBLY_RECORD_STATE_SCHEMA_ID = (
    "betelgeuze.mmcif_assembly_record_state/1.0.0"
)
MMCIF_ASSEMBLY_SOURCE_BINDING_SCHEMA_ID = (
    "betelgeuze.mmcif_assembly_source_binding/1.0.0"
)
MMCIF_ASSEMBLY_WRITE_RECEIPT_SCHEMA_ID = (
    "betelgeuze.mmcif_assembly_write_receipt/1.0.0"
)
MMCIF_ASSEMBLY_ROUND_TRIP_REPORT_SCHEMA_ID = (
    "betelgeuze.mmcif_assembly_round_trip_report/1.0.0"
)

MAX_MMCIF_ASSEMBLY_ENVELOPE_INPUT_BYTES = 64 * 1024 * 1024
MAX_MMCIF_ASSEMBLY_ENVELOPE_SOURCE_ID_BYTES = 4_096
MAX_MMCIF_ASSEMBLY_ENVELOPE_GENERATOR_ROWS = 256
MAX_MMCIF_ASSEMBLY_ENVELOPE_OPERATOR_ROWS = 1_024
MAX_MMCIF_ASSEMBLY_ENVELOPE_TOKEN_CHARS = 2_048
MAX_MMCIF_ASSEMBLY_ENVELOPE_OUTPUT_LINE_CHARS = 2_048

MMCIF_ASSEMBLY_DEFINITION_HEADERS = ("_pdbx_struct_assembly.id",)
MMCIF_ASSEMBLY_GENERATOR_HEADERS = (
    "_pdbx_struct_assembly_gen.assembly_id",
    "_pdbx_struct_assembly_gen.oper_expression",
    "_pdbx_struct_assembly_gen.asym_id_list",
)
MMCIF_ASSEMBLY_OPERATOR_HEADERS = (
    "_pdbx_struct_oper_list.id",
    "_pdbx_struct_oper_list.matrix[1][1]",
    "_pdbx_struct_oper_list.matrix[1][2]",
    "_pdbx_struct_oper_list.matrix[1][3]",
    "_pdbx_struct_oper_list.matrix[2][1]",
    "_pdbx_struct_oper_list.matrix[2][2]",
    "_pdbx_struct_oper_list.matrix[2][3]",
    "_pdbx_struct_oper_list.matrix[3][1]",
    "_pdbx_struct_oper_list.matrix[3][2]",
    "_pdbx_struct_oper_list.matrix[3][3]",
    "_pdbx_struct_oper_list.vector[1]",
    "_pdbx_struct_oper_list.vector[2]",
    "_pdbx_struct_oper_list.vector[3]",
)

_ENTITY_HEADERS = ("_entity.id", "_entity.type")
_STRUCT_ASYM_HEADERS = ("_struct_asym.id", "_struct_asym.entity_id")
_COMMON_CORE21_ATOM_SITE_HEADERS = (
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
    "_pdbx_struct_assembly",
    "_pdbx_struct_assembly_gen",
    "_pdbx_struct_oper_list",
    "_atom_site",
)
_CARRIER_CATEGORY_ORDER = ("_entity", "_struct_asym", "_atom_site")
_ASSEMBLY_CATEGORIES = (
    "_pdbx_struct_assembly",
    "_pdbx_struct_assembly_gen",
    "_pdbx_struct_oper_list",
)
_HEADERS_BY_CATEGORY = {
    "_entity": _ENTITY_HEADERS,
    "_struct_asym": _STRUCT_ASYM_HEADERS,
    "_pdbx_struct_assembly": MMCIF_ASSEMBLY_DEFINITION_HEADERS,
    "_pdbx_struct_assembly_gen": MMCIF_ASSEMBLY_GENERATOR_HEADERS,
    "_pdbx_struct_oper_list": MMCIF_ASSEMBLY_OPERATOR_HEADERS,
    "_atom_site": _COMMON_CORE21_ATOM_SITE_HEADERS,
}
_PLAIN_NUMBER_RE = re.compile(
    r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$"
)
_ASSEMBLY_OPERATION_CODE_RE = re.compile(
    r'''^[\[\]_;.:"&<>/{}'`~!@#$%A-Za-z0-9*|+\-]+$'''
)
_ASSEMBLY_CANONICAL_RANGE_RE = re.compile(
    r"^(?P<start>0|[1-9]\d*)-(?P<end>0|[1-9]\d*)$"
)
_ASSEMBLY_NUMERIC_RANGE_LIKE_RE = re.compile(r"^\d+-\d+$")
_DATA_BLOCK_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.+\-]*$")
_FACTORY_TOKEN = object()

_BASE_MMCIF_PARSER_NAME = (
    "betelgeuze_engine_v2.molecular.pdb_mmcif.parse_mmcif"
)
_BASE_MMCIF_CARRIER_OPERATIONS = (
    "parse_cif_1_1_block_structure",
    "parse_pdbx_atom_site_label_identity",
    "align_models_by_canonical_label_identity",
    "preserve_source_atom_order_from_first_model",
    "synthesize_canonical_atom_serials_from_first_model_order",
)
_BASE_MMCIF_ASSEMBLY_OPERATIONS = (
    "parse_cif_1_1_block_structure",
    "parse_pdbx_atom_site_label_identity",
    "align_models_by_canonical_label_identity",
    "parse_explicit_pdbx_biological_assembly/v1",
    "compose_pdbx_oper_expression_right_to_left/v1",
    "expand_explicit_biological_assembly/v1",
    "reorder_atoms_by_assembly_instance_then_source_order/v1",
    "preserve_source_atom_order_within_each_assembly_instance/v1",
    "synthesize_assembly_chain_ids/v1",
    "synthesize_canonical_atom_serials_from_assembly_instance_order/v1",
)
_BASE_MMCIF_ASSEMBLY_RESOURCE_LIMITS = {
    "definition_rows": 1_024,
    "generator_rows": 1_024,
    "operator_rows": 4_096,
    "oper_expression_characters": 4_096,
    "operation_sequences": 4_096,
    "operation_applications": 16_384,
    "asym_id_list_characters": 4_096,
    "asym_ids_per_generator": 4_096,
    "chain_instances": 4_096,
    "topology_atoms": 20_000,
    "model_atom_rows": 40_000,
}

_FALSE_AUTHORITY_FIELDS = (
    "source_authenticated",
    "biological_assembly_correctness_assessed",
    "assembly_declaration_authoritative",
    "crystallographic_symmetry_expanded",
    "pbc_interpreted",
    "bond_topology_interpreted",
    "chemistry_interpreted",
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


class MmcifAssemblyEnvelopeError(ValueError):
    """Stable fail-closed error for the opt-in assembly envelope."""

    def __init__(
        self, code: str, message: str, *, line_number: int | None = None
    ) -> None:
        self.code = str(code)
        self.detail = str(message)
        self.line_number = None if line_number is None else int(line_number)
        suffix = "" if self.line_number is None else f" at line {self.line_number}"
        super().__init__(f"mmcif_assembly:{self.code}{suffix}: {self.detail}")


def _canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _sha256_document(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _authority_false_document() -> dict[str, bool]:
    return {field_name: False for field_name in _FALSE_AUTHORITY_FIELDS}


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    if value is None or type(value) in {str, bool, int, float}:
        if type(value) is float and not math.isfinite(value):
            raise MmcifAssemblyEnvelopeError(
                "nonfinite_assembly_evidence",
                "assembly evidence contains a non-finite floating-point value",
            )
        return value
    raise MmcifAssemblyEnvelopeError(
        "unsupported_assembly_evidence",
        f"assembly evidence contains unsupported type {type(value).__name__}",
    )


def _source_id_sha256(source_id: str) -> str:
    if type(source_id) is not str:
        raise TypeError("source_id must be an exact string")
    encoded = source_id.encode("utf-8")
    if len(encoded) > MAX_MMCIF_ASSEMBLY_ENVELOPE_SOURCE_ID_BYTES:
        raise MmcifAssemblyEnvelopeError(
            "source_id_limit_exceeded",
            "source_id exceeds the fixed UTF-8 byte limit",
        )
    return hashlib.sha256(encoded).hexdigest()


def _parse_block(data: bytes) -> CifBlock:
    if type(data) is not bytes:
        raise TypeError("mmCIF assembly input must be exact bytes")
    if not 1 <= len(data) <= MAX_MMCIF_ASSEMBLY_ENVELOPE_INPUT_BYTES:
        raise MmcifAssemblyEnvelopeError(
            "input_byte_limit_exceeded",
            "mmCIF assembly input is empty or exceeds the fixed byte limit",
        )
    try:
        text = data.decode("ascii")
        return parse_cif_block(text)
    except UnicodeDecodeError as exc:
        raise MmcifAssemblyEnvelopeError(
            "invalid_cif_character_set", "mmCIF assembly input must be ASCII"
        ) from exc
    except CifSyntaxError as exc:
        raise MmcifAssemblyEnvelopeError(
            exc.code, exc.detail, line_number=exc.line_number
        ) from exc


def _loop_for(block: CifBlock, category: str) -> CifLoop:
    loops = [loop for loop in block.loops if category in loop.categories]
    if len(loops) != 1 or loops[0].categories != (category,):
        raise MmcifAssemblyEnvelopeError(
            "unsupported_category_layout",
            f"{category} must occupy exactly one unmixed loop",
        )
    return loops[0]


def _token_text(token: CifToken, *, location: str) -> str:
    if token.quoted or token.multiline:
        raise MmcifAssemblyEnvelopeError(
            "unsupported_token_quoting",
            "selected assembly envelope values must be bare single-line tokens",
            line_number=token.line_number,
        )
    value = token.value
    if (
        not value
        or len(value) > MAX_MMCIF_ASSEMBLY_ENVELOPE_TOKEN_CHARS
        or not value.isascii()
        or not value.isprintable()
        or any(character.isspace() for character in value)
        or value.startswith(("_", "#", ";", "$", "[", "]"))
        or value.lower() in {"loop_", "stop_", "global_"}
        or value.lower().startswith(("data_", "save_"))
    ):
        raise MmcifAssemblyEnvelopeError(
            "unsafe_cif_token",
            f"{location} is outside the bare-token envelope",
            line_number=token.line_number,
        )
    return value


def _validated_surface(
    block: CifBlock, *, assembly_id: str
) -> dict[str, tuple[tuple[str, ...], ...]]:
    if type(assembly_id) is not str:
        raise TypeError("assembly_id must be an exact string")
    if not assembly_id:
        raise MmcifAssemblyEnvelopeError(
            "invalid_assembly_id", "assembly_id must be nonempty"
        )
    if block.scalar_values:
        raise MmcifAssemblyEnvelopeError(
            "unsupported_scalar_items",
            "assembly envelope v1 requires exact loop-form categories",
        )
    if block.categories != _CATEGORY_ORDER or len(block.loops) != len(_CATEGORY_ORDER):
        raise MmcifAssemblyEnvelopeError(
            "unsupported_category_surface",
            "assembly envelope categories must use the exact reviewed order",
        )
    if _DATA_BLOCK_RE.fullmatch(block.name) is None:
        raise MmcifAssemblyEnvelopeError(
            "unsafe_data_block", "data block name is outside the envelope"
        )

    rows_by_category: dict[str, tuple[tuple[str, ...], ...]] = {}
    for category in _CATEGORY_ORDER:
        loop = _loop_for(block, category)
        expected_headers = _HEADERS_BY_CATEGORY[category]
        if loop.tags != expected_headers:
            raise MmcifAssemblyEnvelopeError(
                "unsupported_category_headers",
                f"{category} headers differ from the exact envelope profile",
                line_number=loop.line_number,
            )
        rows_by_category[category] = tuple(
            tuple(
                _token_text(
                    token,
                    location=f"{category}.rows[{row_index}][{column_index}]",
                )
                for column_index, token in enumerate(row)
            )
            for row_index, row in enumerate(loop.rows)
        )

    definition_rows = rows_by_category["_pdbx_struct_assembly"]
    generator_rows = rows_by_category["_pdbx_struct_assembly_gen"]
    operator_rows = rows_by_category["_pdbx_struct_oper_list"]
    if len(definition_rows) != 1:
        raise MmcifAssemblyEnvelopeError(
            "unsupported_assembly_definition_count",
            "assembly envelope v1 requires exactly one assembly definition row",
        )
    if definition_rows[0][0] != assembly_id:
        raise MmcifAssemblyEnvelopeError(
            "assembly_id_mismatch",
            "requested assembly_id differs from the sole declared assembly",
        )
    if not 1 <= len(generator_rows) <= MAX_MMCIF_ASSEMBLY_ENVELOPE_GENERATOR_ROWS:
        raise MmcifAssemblyEnvelopeError(
            "assembly_generator_limit_exceeded",
            "assembly generator rows are empty or exceed the envelope limit",
        )
    if not 1 <= len(operator_rows) <= MAX_MMCIF_ASSEMBLY_ENVELOPE_OPERATOR_ROWS:
        raise MmcifAssemblyEnvelopeError(
            "assembly_operator_limit_exceeded",
            "assembly operator rows are empty or exceed the envelope limit",
        )
    if any(row[0] != assembly_id for row in generator_rows):
        raise MmcifAssemblyEnvelopeError(
            "assembly_id_mismatch",
            "every generator row must target the sole declared assembly",
        )
    for row_index, row in enumerate(operator_rows):
        for column_index, token in enumerate(row[1:], start=1):
            if _PLAIN_NUMBER_RE.fullmatch(token) is None:
                raise MmcifAssemblyEnvelopeError(
                    "assembly_numeric_uncertainty_unsupported",
                    "operator values must be uncertainty-free finite CIF numbers",
                    line_number=_loop_for(block, "_pdbx_struct_oper_list").rows[
                        row_index
                    ][column_index].line_number,
                )
            value = float(token)
            if not math.isfinite(value):
                raise MmcifAssemblyEnvelopeError(
                    "nonfinite_assembly_operator",
                    "operator values must be finite",
                )
    for category in _ASSEMBLY_CATEGORIES:
        for row in rows_by_category[category]:
            if len(" ".join(row)) > MAX_MMCIF_ASSEMBLY_ENVELOPE_OUTPUT_LINE_CHARS:
                raise MmcifAssemblyEnvelopeError(
                    "assembly_output_line_limit_exceeded",
                    "canonical assembly row exceeds the fixed output line limit",
                )
    if any(row[-1] != "1" for row in rows_by_category["_atom_site"]):
        raise MmcifAssemblyEnvelopeError(
            "unsupported_model_id",
            "assembly envelope v1 requires every atom row to use model ID 1",
        )
    return rows_by_category


def _emit_loop(
    category: str, rows: tuple[tuple[str, ...], ...]
) -> list[str]:
    return [
        "loop_",
        *_HEADERS_BY_CATEGORY[category],
        *(" ".join(row) for row in rows),
        "#",
    ]


def _emit_categories(
    block_name: str,
    rows_by_category: Mapping[str, tuple[tuple[str, ...], ...]],
    categories: tuple[str, ...],
) -> bytes:
    lines = [f"data_{block_name}", "#"]
    for category in categories:
        lines.extend(_emit_loop(category, rows_by_category[category]))
    try:
        return ("\n".join(lines) + "\n").encode("ascii")
    except UnicodeEncodeError as exc:
        raise MmcifAssemblyEnvelopeError(
            "unsafe_cif_token", "validated output is not ASCII"
        ) from exc


def _carrier_source(
    block: CifBlock,
    rows_by_category: Mapping[str, tuple[tuple[str, ...], ...]],
) -> bytes:
    return _emit_categories(block.name, rows_by_category, _CARRIER_CATEGORY_ORDER)


def _rows_from_block(
    block: CifBlock,
) -> dict[str, tuple[tuple[str, ...], ...]]:
    rows: dict[str, tuple[tuple[str, ...], ...]] = {}
    for category in _CARRIER_CATEGORY_ORDER:
        loop = _loop_for(block, category)
        if loop.tags != _HEADERS_BY_CATEGORY[category]:
            raise MmcifAssemblyEnvelopeError(
                "canonical_carrier_surface_mismatch",
                "base writer emitted an unexpected carrier surface",
            )
        rows[category] = tuple(
            tuple(
                _token_text(token, location=f"canonical_carrier.{category}")
                for token in row
            )
            for row in loop.rows
        )
    return rows


def _declaration_projection_document(
    *,
    assembly_id: str,
    rows_by_category: Mapping[str, tuple[tuple[str, ...], ...]],
    assembly_ledger: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_id": MMCIF_ASSEMBLY_DECLARATION_PROJECTION_SCHEMA_ID,
        "envelope_version": MMCIF_ASSEMBLY_ENVELOPE_VERSION,
        "profile_id": MMCIF_ASSEMBLY_PROFILE_ID,
        "projection_scope": MMCIF_ASSEMBLY_PROJECTION_SCOPE,
        "assembly_id": assembly_id,
        "expression_semantics": assembly_ledger.get("expression_semantics"),
        "categories": [
            {
                "category": category,
                "headers": list(_HEADERS_BY_CATEGORY[category]),
                "rows": [list(row) for row in rows_by_category[category]],
            }
            for category in _ASSEMBLY_CATEGORIES
        ],
        "parsed_generators": _plain(assembly_ledger.get("generators")),
        "resource_limits": {
            "input_bytes": MAX_MMCIF_ASSEMBLY_ENVELOPE_INPUT_BYTES,
            "canonical_output_bytes": MAX_MMCIF_ASSEMBLY_ENVELOPE_INPUT_BYTES,
            "source_id_utf8_bytes": (
                MAX_MMCIF_ASSEMBLY_ENVELOPE_SOURCE_ID_BYTES
            ),
            "generator_rows": MAX_MMCIF_ASSEMBLY_ENVELOPE_GENERATOR_ROWS,
            "operator_rows": MAX_MMCIF_ASSEMBLY_ENVELOPE_OPERATOR_ROWS,
            "token_characters": MAX_MMCIF_ASSEMBLY_ENVELOPE_TOKEN_CHARS,
            "output_line_characters": (
                MAX_MMCIF_ASSEMBLY_ENVELOPE_OUTPUT_LINE_CHARS
            ),
        },
        "parser_version": MMCIF_ASSEMBLY_PARSER_VERSION,
        "base_parser_version": MMCIF_PARSER_VERSION,
        "base_writer_version": MMCIF_WRITER_VERSION,
        "carrier_representable_state_schema_id": (
            MMCIF_REPRESENTABLE_STATE_SCHEMA_ID
        ),
        **_authority_false_document(),
    }


def _binary64_hex(value: float) -> str:
    return struct.pack(">d", float(value)).hex()


def _binary64_nested_document(value: Any) -> Any:
    if type(value) in {int, float}:
        return _binary64_hex(float(value))
    if type(value) is list:
        return [_binary64_nested_document(item) for item in value]
    raise MmcifAssemblyEnvelopeError(
        "base_mmcif_assembly_semantic_mismatch",
        "assembly transform evidence is not an exact finite numeric array",
    )


def _binary64_tensor_equal(left: torch.Tensor, right: torch.Tensor) -> bool:
    return (
        type(left) is torch.Tensor
        and type(right) is torch.Tensor
        and left.dtype is torch.float64
        and right.dtype is torch.float64
        and left.device.type == "cpu"
        and right.device.type == "cpu"
        and tuple(left.shape) == tuple(right.shape)
        and torch.equal(
            left.contiguous().view(torch.int64),
            right.contiguous().view(torch.int64),
        )
    )


def _parse_operation_sequences(expression: str) -> tuple[tuple[str, ...], ...]:
    if type(expression) is not str or not expression:
        raise MmcifAssemblyEnvelopeError(
            "base_mmcif_assembly_semantic_mismatch",
            "assembly operation expression is absent from the exact source rows",
        )
    if "(" in expression or ")" in expression:
        if re.fullmatch(r"(?:\([^()]+\))+", expression) is None:
            raise MmcifAssemblyEnvelopeError(
                "base_mmcif_assembly_semantic_mismatch",
                "assembly operation expression differs from the reviewed grammar",
            )
        raw_groups = re.findall(r"\(([^()]+)\)", expression)
    else:
        if "," in expression or _ASSEMBLY_NUMERIC_RANGE_LIKE_RE.fullmatch(
            expression
        ):
            raise MmcifAssemblyEnvelopeError(
                "base_mmcif_assembly_semantic_mismatch",
                "bare assembly operation expression is not one exact code",
            )
        raw_groups = [expression]

    groups: list[tuple[str, ...]] = []
    for raw_group in raw_groups:
        expanded: list[str] = []
        for item in raw_group.split(","):
            range_match = _ASSEMBLY_CANONICAL_RANGE_RE.fullmatch(item)
            if range_match is not None:
                start = int(range_match.group("start"), 10)
                end = int(range_match.group("end"), 10)
                if end < start:
                    raise MmcifAssemblyEnvelopeError(
                        "base_mmcif_assembly_semantic_mismatch",
                        "assembly operation range is descending",
                    )
                expanded.extend(str(value) for value in range(start, end + 1))
            elif (
                _ASSEMBLY_NUMERIC_RANGE_LIKE_RE.fullmatch(item) is not None
                or _ASSEMBLY_OPERATION_CODE_RE.fullmatch(item) is None
            ):
                raise MmcifAssemblyEnvelopeError(
                    "base_mmcif_assembly_semantic_mismatch",
                    "assembly operation code differs from the reviewed grammar",
                )
            else:
                expanded.append(item)
        if not expanded or len(set(expanded)) != len(expanded):
            raise MmcifAssemblyEnvelopeError(
                "base_mmcif_assembly_semantic_mismatch",
                "assembly operation factor is empty or duplicated",
            )
        groups.append(tuple(expanded))
    return tuple(tuple(sequence) for sequence in itertools.product(*groups))


def _stable_base_coverage_document(value: Mapping[str, Any]) -> dict[str, Any]:
    document = _plain(value)
    document.pop("source_missingness_evidence_sha256", None)
    return {
        "coverage": document,
        "excluded_source_specific_fields": [
            "source_missingness_evidence_sha256"
        ],
    }


def _expanded_state_document(system: Any, *, assembly_id: str) -> dict[str, Any]:
    if system.coordinates.device.type != "cpu" or system.coordinates.dtype is not torch.float64:
        raise MmcifAssemblyEnvelopeError(
            "unsupported_coordinate_state",
            "expanded assembly coordinates must be parser-owned CPU float64",
        )
    if system.coordinates.requires_grad or system.model_count != 1:
        raise MmcifAssemblyEnvelopeError(
            "unsupported_coordinate_state",
            "expanded assembly envelope requires one detached coordinate model",
        )
    if system.cell is not None or system.coordinate_unit != "angstrom":
        raise MmcifAssemblyEnvelopeError(
            "unsupported_periodic_state",
            "expanded assembly envelope requires no periodic cell and angstrom coordinates",
        )
    mmcif = system.metadata.get("mmcif")
    if not isinstance(mmcif, Mapping):
        raise MmcifAssemblyEnvelopeError(
            "missing_assembly_ledger", "expanded system lacks mmCIF metadata"
        )
    ledger = mmcif.get("assembly")
    if not isinstance(ledger, Mapping) or ledger.get("assembly_id") != assembly_id:
        raise MmcifAssemblyEnvelopeError(
            "missing_assembly_ledger", "expanded system assembly ledger is absent or stale"
        )
    provenance_coverage = system.provenance.metadata.get("coverage")
    if not isinstance(provenance_coverage, Mapping):
        raise MmcifAssemblyEnvelopeError(
            "base_mmcif_pedigree_mismatch",
            "expanded system lacks the base coverage mirror",
        )

    atoms: list[dict[str, Any]] = []
    for atom in system.atoms:
        residue = system.residues[atom.residue_index]
        chain = system.chains[residue.chain_index]
        atom_mmcif = atom.metadata.get("mmcif")
        instance = atom.metadata.get("assembly_instance")
        if not isinstance(atom_mmcif, Mapping) or not isinstance(instance, Mapping):
            raise MmcifAssemblyEnvelopeError(
                "missing_assembly_instance",
                "expanded atom lacks source or assembly-instance metadata",
            )
        atoms.append(
            {
                "index": atom.index,
                "serial": atom.serial,
                "name": atom.name,
                "element": atom.element,
                "formal_charge": atom.formal_charge,
                "formal_charge_known": atom.formal_charge_known,
                "residue_index": atom.residue_index,
                "residue_name": residue.name,
                "chain_index": residue.chain_index,
                "output_chain_id": chain.chain_id,
                "source_atom_site_id": atom_mmcif.get("source_atom_site_id"),
                "source_label_asym_id": instance.get("source_label_asym_id"),
                "assembly_instance_index": instance.get("assembly_instance_index"),
                "assembly_copy_group_index": instance.get(
                    "assembly_copy_group_index"
                ),
                "assembly_instance": _plain(instance),
            }
        )
    chains = [
        {
            "index": chain.index,
            "output_chain_id": chain.chain_id,
            "residue_indices": list(chain.residue_indices),
            "assembly_instance": _plain(chain.metadata.get("assembly_instance")),
        }
        for chain in system.chains
    ]
    coordinates = [
        [
            _binary64_hex(float(system.coordinates[0, atom_index, axis].item()))
            for axis in range(3)
        ]
        for atom_index in range(system.atom_count)
    ]
    return {
        "schema_id": MMCIF_ASSEMBLY_EXPANDED_STATE_SCHEMA_ID,
        "envelope_version": MMCIF_ASSEMBLY_ENVELOPE_VERSION,
        "profile_id": MMCIF_ASSEMBLY_PROFILE_ID,
        "assembly_id": assembly_id,
        "canonical_topology_sha256": canonical_topology_sha256(system),
        "atom_count": system.atom_count,
        "residue_count": len(system.residues),
        "chain_count": len(system.chains),
        "model_count": system.model_count,
        "parser_version": MMCIF_ASSEMBLY_PARSER_VERSION,
        "coordinate_unit": system.coordinate_unit,
        "cell": None,
        "atom_order": atoms,
        "chain_order": chains,
        "coordinates_ieee754_binary64_be": coordinates,
        "assembly_ledger": _plain(ledger),
        "base_parser": {
            "name": system.provenance.parser_name,
            "version": system.provenance.parser_version,
            "operations": list(system.provenance.operations),
            "parent_sha256": list(system.provenance.parent_sha256),
            "model_ids": _plain(
                system.provenance.metadata.get("model_ids")
            ),
            "preparation_ready": system.provenance.preparation_ready,
            "claim_safe": system.provenance.claim_safe,
        },
        "base_coverage": _stable_base_coverage_document(provenance_coverage),
        **_authority_false_document(),
    }


@dataclass(frozen=True, slots=True)
class _ParsedComponents:
    full_source: bytes = field(repr=False)
    source_id: str = field(repr=False)
    source_id_sha256: str
    assembly_id: str
    carrier_source: bytes = field(repr=False)
    canonical_carrier_source: bytes = field(repr=False)
    carrier_representable_state_sha256: str
    expanded_snapshot: bytes = field(repr=False)
    _declaration_document_bytes: bytes = field(repr=False)
    _expanded_document_bytes: bytes = field(repr=False)
    _category_rows: tuple[
        tuple[str, tuple[tuple[str, ...], ...]], ...
    ] = field(repr=False)

    @property
    def declaration_document(self) -> dict[str, Any]:
        return json.loads(self._declaration_document_bytes.decode("ascii"))

    @property
    def expanded_document(self) -> dict[str, Any]:
        return json.loads(self._expanded_document_bytes.decode("ascii"))

    @property
    def rows_by_category(self) -> dict[str, tuple[tuple[str, ...], ...]]:
        return dict(self._category_rows)


def _nested_error(exc: Exception) -> MmcifAssemblyEnvelopeError:
    code = getattr(exc, "code", "nested_mmcif_error")
    detail = getattr(exc, "detail", str(exc))
    line_number = getattr(exc, "line_number", None)
    return MmcifAssemblyEnvelopeError(code, detail, line_number=line_number)


def _validate_base_ingest_pedigree(
    ingest: Any,
    *,
    source: bytes,
    source_id: str,
    coordinate_scope: str,
    assembly_status: str,
    operations: tuple[str, ...],
) -> None:
    system = ingest.system
    provenance = ingest.system.provenance
    coverage = ingest.coverage
    provenance_coverage = provenance.metadata.get("coverage")
    topology_sha256 = canonical_topology_sha256(system)
    if (
        provenance.source_format != "mmcif"
        or provenance.source_id != source_id
        or provenance.source_sha256 != _sha256_bytes(source)
        or provenance.parser_name != _BASE_MMCIF_PARSER_NAME
        or provenance.parser_version != MMCIF_PARSER_VERSION
        or tuple(provenance.operations) != operations
        or tuple(provenance.parent_sha256) != ()
        or _plain(provenance.metadata.get("model_ids")) != [1]
        or provenance.metadata.get("canonical_topology_schema_id")
        != CANONICAL_TOPOLOGY_SCHEMA_ID
        or provenance.metadata.get("canonical_topology_sha256")
        != topology_sha256
        or provenance.preparation_ready is not False
        or provenance.claim_safe is not False
        or coverage.source_format != "mmcif"
        or coverage.supported is not True
        or coverage.preparation_ready is not False
        or coverage.claim_safe is not False
        or coverage.coordinate_scope != coordinate_scope
        or coverage.assembly_status != assembly_status
        or coverage.atom_count != system.atom_count
        or coverage.bond_count != len(system.bonds)
        or coverage.residue_count != len(system.residues)
        or coverage.chain_count != len(system.chains)
        or coverage.model_count != system.model_count
        or coverage.explicit_hydrogen_count
        != sum(atom.element == "H" for atom in system.atoms)
        or coverage.hetero_residue_count
        != sum(residue.hetero for residue in system.residues)
        or coverage.unknown_formal_charge_count
        != sum(atom.formal_charge_known is False for atom in system.atoms)
        or coverage.unknown_entity_type_count
        != sum(residue.entity_type == "unknown" for residue in system.residues)
        or coverage.cell_present is not (system.cell is not None)
        or coverage.canonical_topology_schema_id
        != CANONICAL_TOPOLOGY_SCHEMA_ID
        or coverage.canonical_topology_sha256 != topology_sha256
        or not isinstance(provenance_coverage, Mapping)
        or _plain(provenance_coverage) != _plain(coverage.to_dict())
    ):
        raise MmcifAssemblyEnvelopeError(
            "base_mmcif_pedigree_mismatch",
            "base parser pedigree or negative-authority state differs from the envelope contract",
        )


def _validate_explicit_assembly_semantics(
    ingest: Any,
    *,
    assembly_id: str,
    carrier_system: Any,
    rows_by_category: Mapping[str, tuple[tuple[str, ...], ...]],
) -> None:
    system = ingest.system
    coverage = ingest.coverage
    mmcif = system.metadata.get("mmcif")
    if not isinstance(mmcif, Mapping):
        raise MmcifAssemblyEnvelopeError(
            "base_mmcif_assembly_semantic_mismatch",
            "expanded system lacks mmCIF semantic metadata",
        )
    ledger = mmcif.get("assembly")
    if not isinstance(ledger, Mapping):
        raise MmcifAssemblyEnvelopeError(
            "base_mmcif_assembly_semantic_mismatch",
            "expanded system lacks an assembly ledger",
        )
    document = _plain(ledger)
    generators = document.get("generators")
    instances = document.get("instances")
    usage = document.get("resource_usage")
    resource_limits = document.get("resource_limits")
    generator_rows = rows_by_category["_pdbx_struct_assembly_gen"]
    operator_rows = rows_by_category["_pdbx_struct_oper_list"]
    atom_rows = rows_by_category["_atom_site"]
    try:
        carrier_match = (
            carrier_system.model_count == 1
            and carrier_system.cell is None
            and carrier_system.coordinate_unit == "angstrom"
            and carrier_system.atom_count == len(atom_rows)
        )
        source_rows_by_asym: dict[
            str, list[tuple[int, tuple[str, ...]]]
        ] = {}
        for row_index, row in enumerate(atom_rows):
            source_rows_by_asym.setdefault(row[6], []).append((row_index, row))
            source_atom = carrier_system.atoms[row_index]
            source_residue = carrier_system.residues[source_atom.residue_index]
            source_chain = carrier_system.chains[source_residue.chain_index]
            source_mmcif = source_atom.metadata.get("mmcif")
            source_coordinates = torch.tensor(
                [float(row[10]), float(row[11]), float(row[12])],
                dtype=torch.float64,
            )
            carrier_match = carrier_match and (
                isinstance(source_mmcif, Mapping)
                and source_atom.index == row_index
                and source_chain.chain_id == row[6]
                and source_mmcif.get("source_atom_site_id") == row[1]
                and _binary64_tensor_equal(
                    carrier_system.coordinates[0, row_index],
                    source_coordinates,
                )
            )
        source_chain_by_asym = {
            chain.chain_id: chain for chain in carrier_system.chains
        }
        carrier_match = carrier_match and (
            len(source_chain_by_asym) == len(carrier_system.chains)
            and set(source_rows_by_asym).issubset(source_chain_by_asym)
        )

        operations: dict[str, tuple[torch.Tensor, torch.Tensor]] = {}
        for row in operator_rows:
            if row[0] in operations:
                raise ValueError("duplicate operator in exact source rows")
            values = [float(value) for value in row[1:]]
            operations[row[0]] = (
                torch.tensor(values[:9], dtype=torch.float64).reshape(3, 3),
                torch.tensor(values[9:], dtype=torch.float64),
            )

        expected_generators: list[dict[str, Any]] = []
        components: list[
            tuple[
                dict[str, Any],
                tuple[str, ...],
                torch.Tensor,
                torch.Tensor,
                list[tuple[int, tuple[str, ...]]],
            ]
        ] = []
        sequence_count = 0
        application_count = 0
        copy_group_count = 0
        for row_index, row in enumerate(generator_rows):
            operation_sequences = _parse_operation_sequences(row[1])
            asym_ids = tuple(row[2].split(","))
            expected_generators.append(
                {
                    "source_row_index": row_index,
                    "asym_ids": list(asym_ids),
                    "raw_oper_expression": row[1],
                    "operation_sequences": [
                        list(sequence) for sequence in operation_sequences
                    ],
                }
            )
            sequence_count += len(operation_sequences)
            application_count += sum(map(len, operation_sequences))
            for sequence in operation_sequences:
                copy_group_count += 1
                rotation = torch.eye(3, dtype=torch.float64)
                translation = torch.zeros(3, dtype=torch.float64)
                for operation_id in sequence:
                    next_rotation, next_translation = operations[operation_id]
                    translation = rotation @ next_translation + translation
                    rotation = rotation @ next_rotation
                for asym_id in asym_ids:
                    source_rows = source_rows_by_asym[asym_id]
                    instance_index = len(components) + 1
                    pointer = {
                        "assembly_id": assembly_id,
                        "assembly_instance_index": instance_index,
                        "assembly_copy_group_index": copy_group_count,
                        "source_label_asym_id": asym_id,
                        "output_chain_id": f"ASM{instance_index:06d}",
                    }
                    components.append(
                        (
                            pointer,
                            sequence,
                            rotation,
                            translation,
                            source_rows,
                        )
                    )

        expected_instances: list[dict[str, Any]] = []
        for pointer, sequence, rotation, translation, source_rows in components:
            expected_instances.append(
                {
                    "instance_index": pointer["assembly_instance_index"],
                    "copy_group_index": pointer["assembly_copy_group_index"],
                    "source_label_asym_id": pointer["source_label_asym_id"],
                    "output_chain_id": pointer["output_chain_id"],
                    "operation_sequence": list(sequence),
                    "rotation": rotation.tolist(),
                    "translation": translation.tolist(),
                    "source_atom_count": len(source_rows),
                }
            )
        instances_match = (
            type(instances) is list and len(instances) == len(expected_instances)
        )
        if instances_match:
            for instance, expected in zip(
                instances, expected_instances, strict=True
            ):
                instance_nontransform = {
                    key: value
                    for key, value in instance.items()
                    if key not in {"rotation", "translation"}
                }
                expected_nontransform = {
                    key: value
                    for key, value in expected.items()
                    if key not in {"rotation", "translation"}
                }
                instances_match = instances_match and (
                    type(instance) is dict
                    and instance_nontransform == expected_nontransform
                    and _binary64_nested_document(instance.get("rotation"))
                    == _binary64_nested_document(expected["rotation"])
                    and _binary64_nested_document(instance.get("translation"))
                    == _binary64_nested_document(expected["translation"])
                )

        chain_instances_match = len(system.chains) == len(components)
        atom_instances_match = system.atom_count == sum(
            len(component[4]) for component in components
        )
        expanded_atom_index = 0
        for chain_index, component in enumerate(components):
            pointer, _, rotation, translation, source_rows = component
            chain = system.chains[chain_index]
            source_chain = source_chain_by_asym[
                pointer["source_label_asym_id"]
            ]
            chain_metadata = _plain(chain.metadata.get("assembly_instance"))
            chain_source_metadata = _plain(chain.metadata)
            chain_source_metadata.pop("assembly_instance", None)
            chain_atom_indices = [
                atom_index
                for residue_index in chain.residue_indices
                for atom_index in system.residues[residue_index].atom_indices
            ]
            source_chain_atom_indices = [
                atom_index
                for residue_index in source_chain.residue_indices
                for atom_index in carrier_system.residues[
                    residue_index
                ].atom_indices
            ]
            expected_chain_atom_indices = list(
                range(expanded_atom_index, expanded_atom_index + len(source_rows))
            )
            source_to_expanded_atom = {
                source_atom_index: expanded_atom_index + offset
                for offset, source_atom_index in enumerate(
                    source_chain_atom_indices
                )
            }
            chain_instances_match = chain_instances_match and (
                chain.index == chain_index
                and chain.chain_id == pointer["output_chain_id"]
                and chain_metadata == pointer
                and chain.entity_id == source_chain.entity_id
                and chain_source_metadata == _plain(source_chain.metadata)
                and len(chain.residue_indices)
                == len(source_chain.residue_indices)
                and chain_atom_indices == expected_chain_atom_indices
                and source_chain_atom_indices
                == [source_row_index for source_row_index, _ in source_rows]
            )
            for residue_index, source_residue_index in zip(
                chain.residue_indices,
                source_chain.residue_indices,
                strict=True,
            ):
                residue = system.residues[residue_index]
                source_residue = carrier_system.residues[source_residue_index]
                expected_residue_atom_indices = tuple(
                    source_to_expanded_atom[atom_index]
                    for atom_index in source_residue.atom_indices
                )
                chain_instances_match = chain_instances_match and (
                    residue.index == residue_index
                    and residue.chain_index == chain_index
                    and residue.name == source_residue.name
                    and residue.sequence_number == source_residue.sequence_number
                    and residue.atom_indices == expected_residue_atom_indices
                    and residue.insertion_code == source_residue.insertion_code
                    and residue.entity_type == source_residue.entity_type
                    and residue.hetero is source_residue.hetero
                    and _plain(residue.metadata)
                    == _plain(source_residue.metadata)
                )
            for source_row_index, source_row in source_rows:
                atom = system.atoms[expanded_atom_index]
                residue = system.residues[atom.residue_index]
                source_atom = carrier_system.atoms[source_row_index]
                source_residue = carrier_system.residues[
                    source_atom.residue_index
                ]
                atom_mmcif = atom.metadata.get("mmcif")
                atom_pointer = _plain(atom.metadata.get("assembly_instance"))
                atom_source_metadata = _plain(atom.metadata)
                atom_source_metadata.pop("assembly_instance", None)
                source_coordinates = carrier_system.coordinates[
                    0, source_row_index
                ]
                expected_coordinates = rotation @ source_coordinates + translation
                atom_instances_match = atom_instances_match and (
                    atom.index == expanded_atom_index
                    and atom.serial == expanded_atom_index + 1
                    and residue.chain_index == chain_index
                    and isinstance(atom_mmcif, Mapping)
                    and atom_mmcif.get("source_atom_site_id") == source_row[1]
                    and atom_pointer == pointer
                    and atom.name == source_atom.name
                    and atom.element == source_atom.element
                    and atom.atomic_number == source_atom.atomic_number
                    and atom.formal_charge == source_atom.formal_charge
                    and atom.formal_charge_known
                    is source_atom.formal_charge_known
                    and (
                        None
                        if atom.partial_charge_e is None
                        else _binary64_hex(atom.partial_charge_e)
                    )
                    == (
                        None
                        if source_atom.partial_charge_e is None
                        else _binary64_hex(source_atom.partial_charge_e)
                    )
                    and (
                        None
                        if atom.mass_da is None
                        else _binary64_hex(atom.mass_da)
                    )
                    == (
                        None
                        if source_atom.mass_da is None
                        else _binary64_hex(source_atom.mass_da)
                    )
                    and atom.isotope_mass_number
                    == source_atom.isotope_mass_number
                    and atom.atom_map == source_atom.atom_map
                    and atom.altloc == source_atom.altloc
                    and (
                        None
                        if atom.occupancy is None
                        else _binary64_hex(atom.occupancy)
                    )
                    == (
                        None
                        if source_atom.occupancy is None
                        else _binary64_hex(source_atom.occupancy)
                    )
                    and (
                        None
                        if atom.b_factor is None
                        else _binary64_hex(atom.b_factor)
                    )
                    == (
                        None
                        if source_atom.b_factor is None
                        else _binary64_hex(source_atom.b_factor)
                    )
                    and atom.aromatic is source_atom.aromatic
                    and atom.stereo == source_atom.stereo
                    and atom_source_metadata == _plain(source_atom.metadata)
                    and residue.name == source_residue.name
                    and _binary64_tensor_equal(
                        system.coordinates[0, expanded_atom_index],
                        expected_coordinates,
                    )
                )
                expanded_atom_index += 1

        chain_instance_count = len(components)
        expanded_atom_count = expanded_atom_index
        expected_usage = {
            "definition_rows": 1,
            "generator_rows": len(generator_rows),
            "selected_generator_rows": len(generator_rows),
            "operator_rows": len(operator_rows),
            "selected_oper_expression_characters": sum(
                len(row[1]) for row in generator_rows
            ),
            "selected_oper_expression_max_characters": max(
                len(row[1]) for row in generator_rows
            ),
            "selected_asym_id_list_characters": sum(
                len(row[2]) for row in generator_rows
            ),
            "selected_asym_id_list_max_characters": max(
                len(row[2]) for row in generator_rows
            ),
            "selected_asym_ids": sum(
                len(row[2].split(",")) for row in generator_rows
            ),
            "operation_sequences": sequence_count,
            "operation_applications": application_count,
            "chain_instances": chain_instance_count,
            "topology_atoms": expanded_atom_count,
            "model_atom_rows": system.model_count * expanded_atom_count,
        }
        expected_ledger_keys = {
            "status",
            "selection_policy",
            "assembly_id",
            "expression_semantics",
            "source_topology_atom_count",
            "expanded_topology_atom_count",
            "operation_sequence_count",
            "operation_application_count",
            "copy_group_count",
            "chain_instance_count",
            "expanded_model_atom_rows",
            "resource_usage",
            "generators",
            "instances",
            "resource_limits",
        }
        semantic_match = (
            system.cell is None
            and system.coordinate_unit == "angstrom"
            and coverage.cell_present is False
            and mmcif.get("cell") is None
            and mmcif.get("atom_site_headers")
            == list(_COMMON_CORE21_ATOM_SITE_HEADERS)
            and mmcif.get("coordinate_scope") == "explicit_biological_assembly"
            and set(document) == expected_ledger_keys
            and document.get("status") == "explicit_id_applied"
            and document.get("selection_policy") == "explicit_only"
            and document.get("assembly_id") == assembly_id
            and document.get("expression_semantics") == "pdbx_right_to_left/v1"
            and document.get("source_topology_atom_count") == len(atom_rows)
            and document.get("expanded_topology_atom_count") == system.atom_count
            and document.get("expanded_model_atom_rows")
            == system.model_count * system.atom_count
            and document.get("operation_sequence_count") == sequence_count
            and document.get("operation_application_count") == application_count
            and document.get("chain_instance_count") == chain_instance_count
            and document.get("chain_instance_count") == len(system.chains)
            and document.get("copy_group_count") == copy_group_count
            and coverage.source_atom_row_count == len(atom_rows)
            and coverage.altloc_status == "not_present"
            and coverage.requested_altloc_id == ""
            and coverage.altloc_affected_residue_count == 0
            and coverage.altloc_kept_row_count == len(atom_rows)
            and coverage.altloc_discarded_row_count == 0
            and coverage.requested_assembly_id == assembly_id
            and coverage.assembly_operation_sequence_count == sequence_count
            and coverage.assembly_operation_application_count == application_count
            and coverage.assembly_chain_instance_count == chain_instance_count
            and coverage.assembly_output_atom_count == system.atom_count
            and coverage.missingness_evidence_status == "not_present"
            and coverage.source_reported_missing_residue_claim_count == 0
            and coverage.source_reported_missing_atom_claim_count == 0
            and len(system.bonds) == 0
            and generators == expected_generators
            and usage == expected_usage
            and resource_limits == _BASE_MMCIF_ASSEMBLY_RESOURCE_LIMITS
            and carrier_match
            and instances_match
            and chain_instances_match
            and atom_instances_match
        )
    except (KeyError, TypeError, ValueError):
        semantic_match = False
    if not semantic_match:
        raise MmcifAssemblyEnvelopeError(
            "base_mmcif_assembly_semantic_mismatch",
            "base assembly metadata, coverage, and live expanded state disagree",
        )


def _parse_components(
    data: bytes, *, assembly_id: str, source_id: str
) -> _ParsedComponents:
    source_id_digest = _source_id_sha256(source_id)
    block = _parse_block(data)
    rows_by_category = _validated_surface(block, assembly_id=assembly_id)
    carrier_source = _carrier_source(block, rows_by_category)
    try:
        carrier_round_trip = round_trip_mmcif_source(
            carrier_source, source_id=source_id
        )
        expanded_ingest = parse_mmcif(
            data, source_id=source_id, assembly_id=assembly_id
        )
    except MmcifWriteError as exc:
        if exc.code == "output_too_large":
            raise MmcifAssemblyEnvelopeError(
                "assembly_output_byte_limit_exceeded",
                "canonical assembly carrier exceeds the fixed output byte limit",
            ) from exc
        raise _nested_error(exc) from exc
    except (StructureParseError, CifSyntaxError) as exc:
        raise _nested_error(exc) from exc
    _validate_base_ingest_pedigree(
        carrier_round_trip.source_ingest,
        source=carrier_source,
        source_id=source_id,
        coordinate_scope="deposited_asymmetric_unit",
        assembly_status="not_present",
        operations=_BASE_MMCIF_CARRIER_OPERATIONS,
    )
    _validate_base_ingest_pedigree(
        expanded_ingest,
        source=data,
        source_id=source_id,
        coordinate_scope="explicit_biological_assembly",
        assembly_status="explicit_id_applied",
        operations=_BASE_MMCIF_ASSEMBLY_OPERATIONS,
    )
    if (
        expanded_ingest.coverage.assembly_status != "explicit_id_applied"
        or expanded_ingest.coverage.requested_assembly_id != assembly_id
    ):
        raise MmcifAssemblyEnvelopeError(
            "assembly_not_applied",
            "base parser did not apply the explicitly requested assembly",
        )
    if "assembly_operation_numeric_standard_uncertainty_not_propagated" in (
        expanded_ingest.coverage.blockers
    ):
        raise MmcifAssemblyEnvelopeError(
            "assembly_numeric_uncertainty_unsupported",
            "operator numeric uncertainty is outside envelope v1",
        )
    ledger = expanded_ingest.system.metadata["mmcif"]["assembly"]
    source_atom_count = ledger.get("source_topology_atom_count")
    carrier_atom_count = carrier_round_trip.source_ingest.system.atom_count
    if source_atom_count != carrier_atom_count:
        raise MmcifAssemblyEnvelopeError(
            "carrier_assembly_atom_count_mismatch",
            "assembly source atom count differs from the deposited carrier",
        )
    _validate_explicit_assembly_semantics(
        expanded_ingest,
        assembly_id=assembly_id,
        carrier_system=carrier_round_trip.source_ingest.system,
        rows_by_category=rows_by_category,
    )
    declaration = _declaration_projection_document(
        assembly_id=assembly_id,
        rows_by_category=rows_by_category,
        assembly_ledger=ledger,
    )
    expanded = _expanded_state_document(
        expanded_ingest.system, assembly_id=assembly_id
    )
    components = _ParsedComponents(
        full_source=data,
        source_id=source_id,
        source_id_sha256=source_id_digest,
        assembly_id=assembly_id,
        carrier_source=carrier_source,
        canonical_carrier_source=carrier_round_trip.write_result.payload,
        carrier_representable_state_sha256=(
            carrier_round_trip.write_result.receipt.input_representable_state_sha256
        ),
        expanded_snapshot=serialize_all_atom_system(expanded_ingest.system),
        _declaration_document_bytes=_canonical_json_bytes(declaration),
        _expanded_document_bytes=_canonical_json_bytes(expanded),
        _category_rows=tuple(
            (category, rows_by_category[category]) for category in _CATEGORY_ORDER
        ),
    )
    _compose_output(components)
    return components


def _record_state_document(components: _ParsedComponents) -> dict[str, Any]:
    return {
        "schema_id": MMCIF_ASSEMBLY_RECORD_STATE_SCHEMA_ID,
        "envelope_version": MMCIF_ASSEMBLY_ENVELOPE_VERSION,
        "parser_version": MMCIF_ASSEMBLY_PARSER_VERSION,
        "profile_id": MMCIF_ASSEMBLY_PROFILE_ID,
        "assembly_id": components.assembly_id,
        "base_parser_name": _BASE_MMCIF_PARSER_NAME,
        "base_parser_version": MMCIF_PARSER_VERSION,
        "base_parser_operations": list(_BASE_MMCIF_ASSEMBLY_OPERATIONS),
        "base_writer_version": MMCIF_WRITER_VERSION,
        "carrier_representable_state_schema_id": (
            MMCIF_REPRESENTABLE_STATE_SCHEMA_ID
        ),
        "source_id_sha256": components.source_id_sha256,
        "carrier_representable_state_sha256": (
            components.carrier_representable_state_sha256
        ),
        "declaration_projection_sha256": _sha256_document(
            components.declaration_document
        ),
        "expanded_state_sha256": _sha256_document(components.expanded_document),
        "expanded_topology_sha256": components.expanded_document[
            "canonical_topology_sha256"
        ],
        "assembly_definition_row_count": 1,
        "assembly_generator_row_count": len(
            components.rows_by_category["_pdbx_struct_assembly_gen"]
        ),
        "assembly_operator_row_count": len(
            components.rows_by_category["_pdbx_struct_oper_list"]
        ),
        **_authority_false_document(),
    }


def _source_binding_document(components: _ParsedComponents) -> dict[str, Any]:
    return {
        "schema_id": MMCIF_ASSEMBLY_SOURCE_BINDING_SCHEMA_ID,
        "envelope_version": MMCIF_ASSEMBLY_ENVELOPE_VERSION,
        "parser_version": MMCIF_ASSEMBLY_PARSER_VERSION,
        "profile_id": MMCIF_ASSEMBLY_PROFILE_ID,
        "full_source_sha256": _sha256_bytes(components.full_source),
        "carrier_source_sha256": _sha256_bytes(components.carrier_source),
        "canonical_carrier_source_sha256": _sha256_bytes(
            components.canonical_carrier_source
        ),
        "source_id_sha256": components.source_id_sha256,
        "record_state_sha256": _sha256_document(
            _record_state_document(components)
        ),
        **_authority_false_document(),
    }


@dataclass(frozen=True, slots=True, init=False)
class MmcifAssemblyIngestResult:
    _components: _ParsedComponents = field(repr=False)

    def __init__(
        self,
        components: _ParsedComponents,
        *,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise TypeError("MmcifAssemblyIngestResult is factory-only")
        if type(components) is not _ParsedComponents:
            raise TypeError("components must be exact parsed assembly components")
        fresh = _parse_components(
            components.full_source,
            assembly_id=components.assembly_id,
            source_id=components.source_id,
        )
        if fresh != components:
            raise MmcifAssemblyEnvelopeError(
                "stale_or_crosswired_ingest",
                "supplied assembly components differ from a fresh parse",
            )
        object.__setattr__(self, "_components", fresh)

    @property
    def assembly_id(self) -> str:
        return self._components.assembly_id

    @property
    def source_id_sha256(self) -> str:
        return self._components.source_id_sha256

    @property
    def full_source_sha256(self) -> str:
        return _sha256_bytes(self._components.full_source)

    @property
    def declaration_projection_sha256(self) -> str:
        return _sha256_document(self._components.declaration_document)

    @property
    def expanded_state_sha256(self) -> str:
        return _sha256_document(self._components.expanded_document)

    @property
    def expanded_topology_sha256(self) -> str:
        return str(
            self._components.expanded_document["canonical_topology_sha256"]
        )

    @property
    def carrier_representable_state_sha256(self) -> str:
        return self._components.carrier_representable_state_sha256

    @property
    def record_state_sha256(self) -> str:
        return _sha256_document(_record_state_document(self._components))

    @property
    def source_binding_sha256(self) -> str:
        return _sha256_document(_source_binding_document(self._components))

    @property
    def expanded_system(self) -> Any:
        return deserialize_all_atom_system(self._components.expanded_snapshot)

    @property
    def assembly_generator_row_count(self) -> int:
        return len(
            self._components.rows_by_category["_pdbx_struct_assembly_gen"]
        )

    @property
    def assembly_operator_row_count(self) -> int:
        return len(self._components.rows_by_category["_pdbx_struct_oper_list"])

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": MMCIF_ASSEMBLY_RECORD_STATE_SCHEMA_ID,
            "envelope_version": MMCIF_ASSEMBLY_ENVELOPE_VERSION,
            "parser_version": MMCIF_ASSEMBLY_PARSER_VERSION,
            "profile_id": MMCIF_ASSEMBLY_PROFILE_ID,
            "projection_scope": MMCIF_ASSEMBLY_PROJECTION_SCOPE,
            "assembly_id": self.assembly_id,
            "base_parser_name": _BASE_MMCIF_PARSER_NAME,
            "base_parser_version": MMCIF_PARSER_VERSION,
            "base_parser_operations": list(_BASE_MMCIF_ASSEMBLY_OPERATIONS),
            "base_writer_version": MMCIF_WRITER_VERSION,
            "carrier_representable_state_schema_id": (
                MMCIF_REPRESENTABLE_STATE_SCHEMA_ID
            ),
            "full_source_sha256": self.full_source_sha256,
            "source_id_sha256": self.source_id_sha256,
            "source_binding_sha256": self.source_binding_sha256,
            "record_state_sha256": self.record_state_sha256,
            "declaration_projection_sha256": self.declaration_projection_sha256,
            "expanded_state_sha256": self.expanded_state_sha256,
            "expanded_topology_sha256": self.expanded_topology_sha256,
            "carrier_representable_state_sha256": (
                self.carrier_representable_state_sha256
            ),
            "expanded_atom_count": self.expanded_system.atom_count,
            "expanded_chain_count": len(self.expanded_system.chains),
            "assembly_definition_row_count": 1,
            "assembly_generator_row_count": self.assembly_generator_row_count,
            "assembly_operator_row_count": self.assembly_operator_row_count,
            **_authority_false_document(),
        }


def _validate_fresh_ingest(value: MmcifAssemblyIngestResult) -> _ParsedComponents:
    if type(value) is not MmcifAssemblyIngestResult:
        raise TypeError("assembly emission requires an exact ingest result")
    stored = value._components
    fresh = _parse_components(
        stored.full_source,
        assembly_id=stored.assembly_id,
        source_id=stored.source_id,
    )
    if fresh != stored:
        raise MmcifAssemblyEnvelopeError(
            "stale_or_crosswired_ingest",
            "stored assembly ingest evidence differs from a fresh parse",
        )
    return fresh


def parse_mmcif_assembly(
    data: bytes, *, assembly_id: str, source_id: str = ""
) -> MmcifAssemblyIngestResult:
    """Parse the exact envelope and explicitly materialize ``assembly_id``."""

    components = _parse_components(
        data, assembly_id=assembly_id, source_id=source_id
    )
    return MmcifAssemblyIngestResult(
        components, _factory_token=_FACTORY_TOKEN
    )


def mmcif_assembly_declaration_projection_sha256(
    value: MmcifAssemblyIngestResult,
) -> str:
    components = _validate_fresh_ingest(value)
    return _sha256_document(components.declaration_document)


def mmcif_assembly_expanded_state_sha256(
    value: MmcifAssemblyIngestResult,
) -> str:
    components = _validate_fresh_ingest(value)
    return _sha256_document(components.expanded_document)


def _compose_output(components: _ParsedComponents) -> bytes:
    if not 1 <= len(components.canonical_carrier_source) <= (
        MAX_MMCIF_ASSEMBLY_ENVELOPE_INPUT_BYTES
    ):
        raise MmcifAssemblyEnvelopeError(
            "assembly_output_byte_limit_exceeded",
            "canonical assembly carrier is empty or exceeds the fixed output byte limit",
        )
    canonical_block = _parse_block(components.canonical_carrier_source)
    if canonical_block.categories != _CARRIER_CATEGORY_ORDER:
        raise MmcifAssemblyEnvelopeError(
            "canonical_carrier_surface_mismatch",
            "base writer emitted an unexpected category surface",
        )
    carrier_rows = _rows_from_block(canonical_block)
    rows = {
        **carrier_rows,
        **{
            category: components.rows_by_category[category]
            for category in _ASSEMBLY_CATEGORIES
        },
    }
    payload = _emit_categories(canonical_block.name, rows, _CATEGORY_ORDER)
    if not 1 <= len(payload) <= MAX_MMCIF_ASSEMBLY_ENVELOPE_INPUT_BYTES:
        raise MmcifAssemblyEnvelopeError(
            "assembly_output_byte_limit_exceeded",
            "canonical assembly output is empty or exceeds the fixed output byte limit",
        )
    return payload


def _receipt_document(
    components: _ParsedComponents, payload: bytes
) -> dict[str, Any]:
    record = _record_state_document(components)
    return {
        "schema_id": MMCIF_ASSEMBLY_WRITE_RECEIPT_SCHEMA_ID,
        "envelope_version": MMCIF_ASSEMBLY_ENVELOPE_VERSION,
        "parser_version": MMCIF_ASSEMBLY_PARSER_VERSION,
        "writer_version": MMCIF_ASSEMBLY_WRITER_VERSION,
        "base_parser_name": _BASE_MMCIF_PARSER_NAME,
        "base_parser_version": MMCIF_PARSER_VERSION,
        "base_parser_operations": list(_BASE_MMCIF_ASSEMBLY_OPERATIONS),
        "base_writer_version": MMCIF_WRITER_VERSION,
        "carrier_representable_state_schema_id": (
            MMCIF_REPRESENTABLE_STATE_SCHEMA_ID
        ),
        "profile_id": MMCIF_ASSEMBLY_PROFILE_ID,
        "input_source_binding_sha256": _sha256_document(
            _source_binding_document(components)
        ),
        "input_record_state_sha256": _sha256_document(record),
        "input_declaration_projection_sha256": record[
            "declaration_projection_sha256"
        ],
        "input_expanded_state_sha256": record["expanded_state_sha256"],
        "input_expanded_topology_sha256": record["expanded_topology_sha256"],
        "input_carrier_representable_state_sha256": record[
            "carrier_representable_state_sha256"
        ],
        "source_id_sha256": components.source_id_sha256,
        "assembly_id": components.assembly_id,
        "output_source_sha256": _sha256_bytes(payload),
        "output_byte_count": len(payload),
        "assembly_definition_row_count": 1,
        "assembly_generator_row_count": record["assembly_generator_row_count"],
        "assembly_operator_row_count": record["assembly_operator_row_count"],
        "expanded_atom_count": components.expanded_document["atom_count"],
        "expanded_chain_count": components.expanded_document["chain_count"],
        "preservation_scope": MMCIF_ASSEMBLY_PROJECTION_SCOPE,
        **_authority_false_document(),
    }


@dataclass(frozen=True, slots=True, init=False)
class MmcifAssemblyWriteReceipt:
    _document_bytes: bytes = field(repr=False)

    def __init__(
        self,
        document: Mapping[str, Any],
        *,
        components: _ParsedComponents | None = None,
        payload: bytes | None = None,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise TypeError("MmcifAssemblyWriteReceipt is factory-only")
        if type(components) is not _ParsedComponents or type(payload) is not bytes:
            raise TypeError("write receipt requires exact parsed components and payload")
        fresh = _parse_components(
            components.full_source,
            assembly_id=components.assembly_id,
            source_id=components.source_id,
        )
        if fresh != components:
            raise MmcifAssemblyEnvelopeError(
                "stale_or_crosswired_receipt",
                "write receipt components differ from a fresh parse",
            )
        canonical_payload = _compose_output(fresh)
        if payload != canonical_payload:
            raise MmcifAssemblyEnvelopeError(
                "invalid_write_payload",
                "write receipt payload differs from the canonical assembly emission",
            )
        reparsed = _parse_components(
            payload,
            assembly_id=fresh.assembly_id,
            source_id=fresh.source_id,
        )
        if _record_state_document(reparsed) != _record_state_document(fresh):
            raise MmcifAssemblyEnvelopeError(
                "round_trip_mismatch",
                "write receipt payload does not recover the input record state",
            )
        expected = _receipt_document(fresh, payload)
        if _plain(document) != expected:
            raise MmcifAssemblyEnvelopeError(
                "invalid_write_receipt",
                "write receipt document differs from the exact artifact binding",
            )
        object.__setattr__(self, "_document_bytes", _canonical_json_bytes(expected))

    @property
    def receipt_sha256(self) -> str:
        return _sha256_bytes(self._document_bytes)

    def to_dict(self) -> dict[str, Any]:
        document = json.loads(self._document_bytes.decode("ascii"))
        document["receipt_sha256"] = self.receipt_sha256
        return document


@dataclass(frozen=True, slots=True, init=False)
class MmcifAssemblyWriteResult:
    payload: bytes = field(repr=False)
    receipt: MmcifAssemblyWriteReceipt

    def __init__(
        self,
        payload: bytes,
        receipt: MmcifAssemblyWriteReceipt,
        *,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise TypeError("MmcifAssemblyWriteResult is factory-only")
        if type(payload) is not bytes or type(receipt) is not MmcifAssemblyWriteReceipt:
            raise TypeError("invalid assembly write artifacts")
        document = receipt.to_dict()
        if (
            document["output_byte_count"] != len(payload)
            or document["output_source_sha256"] != _sha256_bytes(payload)
        ):
            raise MmcifAssemblyEnvelopeError(
                "invalid_write_receipt", "write receipt does not bind its payload"
            )
        object.__setattr__(self, "payload", payload)
        object.__setattr__(self, "receipt", receipt)

    def to_dict(self) -> dict[str, Any]:
        return {
            "output_source_sha256": _sha256_bytes(self.payload),
            "output_byte_count": len(self.payload),
            "receipt": self.receipt.to_dict(),
            **_authority_false_document(),
        }


def emit_mmcif_assembly(
    value: MmcifAssemblyIngestResult,
) -> MmcifAssemblyWriteResult:
    """Emit canonical ASU plus exact assembly declarations."""

    components = _validate_fresh_ingest(value)
    payload = _compose_output(components)
    reparsed = _parse_components(
        payload,
        assembly_id=components.assembly_id,
        source_id=components.source_id,
    )
    if _record_state_document(reparsed) != _record_state_document(components):
        raise MmcifAssemblyEnvelopeError(
            "round_trip_mismatch",
            "emitted assembly does not recover the declared projection",
        )
    receipt = MmcifAssemblyWriteReceipt(
        _receipt_document(components, payload),
        components=components,
        payload=payload,
        _factory_token=_FACTORY_TOKEN,
    )
    return MmcifAssemblyWriteResult(
        payload, receipt, _factory_token=_FACTORY_TOKEN
    )


def serialize_mmcif_assembly(value: MmcifAssemblyIngestResult) -> bytes:
    return emit_mmcif_assembly(value).payload


def _receipt_exactly_binds(
    write_result: MmcifAssemblyWriteResult,
    ingest: MmcifAssemblyIngestResult,
) -> bool:
    receipt = write_result.receipt.to_dict()
    receipt.pop("receipt_sha256", None)
    return receipt == _receipt_document(
        ingest._components,
        write_result.payload,
    )


def _report_document(
    source: MmcifAssemblyIngestResult,
    reparsed: MmcifAssemblyIngestResult,
    write_result: MmcifAssemblyWriteResult,
    second: MmcifAssemblyWriteResult,
) -> dict[str, Any]:
    stable = write_result.payload == second.payload
    declaration_equal = (
        source.declaration_projection_sha256
        == reparsed.declaration_projection_sha256
    )
    expanded_equal = source.expanded_state_sha256 == reparsed.expanded_state_sha256
    topology_equal = (
        source.expanded_topology_sha256 == reparsed.expanded_topology_sha256
    )
    carrier_equal = (
        source.carrier_representable_state_sha256
        == reparsed.carrier_representable_state_sha256
    )
    source_id_equal = source.source_id_sha256 == reparsed.source_id_sha256
    record_state_equal = source.record_state_sha256 == reparsed.record_state_sha256
    emitted_source_reparsed_exact = (
        _sha256_bytes(write_result.payload) == reparsed.full_source_sha256
    )
    write_receipt_source_bound = _receipt_exactly_binds(write_result, source)
    reemitted_receipt_reparsed_bound = _receipt_exactly_binds(second, reparsed)
    return {
        "schema_id": MMCIF_ASSEMBLY_ROUND_TRIP_REPORT_SCHEMA_ID,
        "envelope_version": MMCIF_ASSEMBLY_ENVELOPE_VERSION,
        "parser_version": MMCIF_ASSEMBLY_PARSER_VERSION,
        "profile_id": MMCIF_ASSEMBLY_PROFILE_ID,
        "assembly_id": source.assembly_id,
        "base_parser_name": _BASE_MMCIF_PARSER_NAME,
        "base_parser_version": MMCIF_PARSER_VERSION,
        "base_parser_operations": list(_BASE_MMCIF_ASSEMBLY_OPERATIONS),
        "base_writer_version": MMCIF_WRITER_VERSION,
        "carrier_representable_state_schema_id": (
            MMCIF_REPRESENTABLE_STATE_SCHEMA_ID
        ),
        "source_id_sha256": source.source_id_sha256,
        "input_source_binding_sha256": source.source_binding_sha256,
        "input_full_source_sha256": source.full_source_sha256,
        "input_record_state_sha256": source.record_state_sha256,
        "reparsed_full_source_sha256": reparsed.full_source_sha256,
        "reparsed_source_binding_sha256": reparsed.source_binding_sha256,
        "reparsed_record_state_sha256": reparsed.record_state_sha256,
        "input_declaration_projection_sha256": (
            source.declaration_projection_sha256
        ),
        "reparsed_declaration_projection_sha256": (
            reparsed.declaration_projection_sha256
        ),
        "input_expanded_state_sha256": source.expanded_state_sha256,
        "reparsed_expanded_state_sha256": reparsed.expanded_state_sha256,
        "input_expanded_topology_sha256": source.expanded_topology_sha256,
        "reparsed_expanded_topology_sha256": reparsed.expanded_topology_sha256,
        "input_carrier_representable_state_sha256": (
            source.carrier_representable_state_sha256
        ),
        "reparsed_carrier_representable_state_sha256": (
            reparsed.carrier_representable_state_sha256
        ),
        "write_receipt_sha256": write_result.receipt.receipt_sha256,
        "reemitted_write_receipt_sha256": second.receipt.receipt_sha256,
        "emitted_source_sha256": _sha256_bytes(write_result.payload),
        "reemitted_source_sha256": _sha256_bytes(second.payload),
        "declaration_projection_equal": declaration_equal,
        "expanded_state_equal": expanded_equal,
        "expanded_topology_equal": topology_equal,
        "carrier_representable_state_equal": carrier_equal,
        "source_id_equal": source_id_equal,
        "record_state_equal": record_state_equal,
        "emitted_source_reparsed_exact": emitted_source_reparsed_exact,
        "write_receipt_source_bound": write_receipt_source_bound,
        "reemitted_receipt_reparsed_bound": (
            reemitted_receipt_reparsed_bound
        ),
        "second_emission_byte_stable": stable,
        "explicit_assembly_round_trip_preserved": all(
            (
                declaration_equal,
                expanded_equal,
                topology_equal,
                carrier_equal,
                source_id_equal,
                record_state_equal,
                emitted_source_reparsed_exact,
                write_receipt_source_bound,
                reemitted_receipt_reparsed_bound,
                stable,
            )
        ),
        **_authority_false_document(),
    }


@dataclass(frozen=True, slots=True, init=False)
class MmcifAssemblyRoundTripReport:
    _document_bytes: bytes = field(repr=False)

    def __init__(
        self,
        document: Mapping[str, Any],
        *,
        source: MmcifAssemblyIngestResult | None = None,
        reparsed: MmcifAssemblyIngestResult | None = None,
        write_result: MmcifAssemblyWriteResult | None = None,
        reemitted_write_result: MmcifAssemblyWriteResult | None = None,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise TypeError("MmcifAssemblyRoundTripReport is factory-only")
        expected_types = (
            type(source) is MmcifAssemblyIngestResult,
            type(reparsed) is MmcifAssemblyIngestResult,
            type(write_result) is MmcifAssemblyWriteResult,
            type(reemitted_write_result) is MmcifAssemblyWriteResult,
        )
        if not all(expected_types):
            raise TypeError("round-trip report requires exact bound artifacts")
        expected = _report_document(
            source,
            reparsed,
            write_result,
            reemitted_write_result,
        )
        if (
            _plain(document) != expected
            or expected["explicit_assembly_round_trip_preserved"] is not True
        ):
            raise MmcifAssemblyEnvelopeError(
                "crosswired_round_trip_artifacts",
                "round-trip report does not prove the exact artifact chain",
            )
        object.__setattr__(self, "_document_bytes", _canonical_json_bytes(expected))

    @property
    def report_sha256(self) -> str:
        return _sha256_bytes(self._document_bytes)

    def to_dict(self) -> dict[str, Any]:
        document = json.loads(self._document_bytes.decode("ascii"))
        document["report_sha256"] = self.report_sha256
        return document


@dataclass(frozen=True, slots=True, init=False)
class MmcifAssemblyRoundTripResult:
    source_ingest: MmcifAssemblyIngestResult
    write_result: MmcifAssemblyWriteResult
    reparsed_ingest: MmcifAssemblyIngestResult
    reemitted_write_result: MmcifAssemblyWriteResult
    report: MmcifAssemblyRoundTripReport

    def __init__(
        self,
        source_ingest: MmcifAssemblyIngestResult,
        write_result: MmcifAssemblyWriteResult,
        reparsed_ingest: MmcifAssemblyIngestResult,
        reemitted_write_result: MmcifAssemblyWriteResult,
        report: MmcifAssemblyRoundTripReport,
        *,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise TypeError("MmcifAssemblyRoundTripResult is factory-only")
        expected_types = (
            type(source_ingest) is MmcifAssemblyIngestResult,
            type(write_result) is MmcifAssemblyWriteResult,
            type(reparsed_ingest) is MmcifAssemblyIngestResult,
            type(reemitted_write_result) is MmcifAssemblyWriteResult,
            type(report) is MmcifAssemblyRoundTripReport,
        )
        if not all(expected_types):
            raise TypeError("invalid assembly round-trip artifacts")
        expected_report = _report_document(
            source_ingest,
            reparsed_ingest,
            write_result,
            reemitted_write_result,
        )
        if report.to_dict() != {
            **expected_report,
            "report_sha256": _sha256_document(expected_report),
        }:
            raise MmcifAssemblyEnvelopeError(
                "crosswired_round_trip_artifacts",
                "round-trip report does not bind the supplied artifacts",
            )
        if expected_report["explicit_assembly_round_trip_preserved"] is not True:
            raise MmcifAssemblyEnvelopeError(
                "crosswired_round_trip_artifacts",
                "round-trip artifacts do not form an exact preservation chain",
            )
        object.__setattr__(self, "source_ingest", source_ingest)
        object.__setattr__(self, "write_result", write_result)
        object.__setattr__(self, "reparsed_ingest", reparsed_ingest)
        object.__setattr__(self, "reemitted_write_result", reemitted_write_result)
        object.__setattr__(self, "report", report)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_ingest": self.source_ingest.to_dict(),
            "write_result": self.write_result.to_dict(),
            "reparsed_ingest": self.reparsed_ingest.to_dict(),
            "reemitted_write_result": self.reemitted_write_result.to_dict(),
            "report": self.report.to_dict(),
            **_authority_false_document(),
        }


def round_trip_mmcif_assembly_source(
    data: bytes, *, assembly_id: str, source_id: str = ""
) -> MmcifAssemblyRoundTripResult:
    source = parse_mmcif_assembly(
        data, assembly_id=assembly_id, source_id=source_id
    )
    write_result = emit_mmcif_assembly(source)
    reparsed = parse_mmcif_assembly(
        write_result.payload, assembly_id=assembly_id, source_id=source_id
    )
    second = emit_mmcif_assembly(reparsed)
    report_document = _report_document(source, reparsed, write_result, second)
    if not report_document["explicit_assembly_round_trip_preserved"]:
        raise MmcifAssemblyEnvelopeError(
            "round_trip_mismatch",
            "declared assembly projection failed round-trip validation",
        )
    report = MmcifAssemblyRoundTripReport(
        report_document,
        source=source,
        reparsed=reparsed,
        write_result=write_result,
        reemitted_write_result=second,
        _factory_token=_FACTORY_TOKEN,
    )
    return MmcifAssemblyRoundTripResult(
        source,
        write_result,
        reparsed,
        second,
        report,
        _factory_token=_FACTORY_TOKEN,
    )


__all__ = [
    "MAX_MMCIF_ASSEMBLY_ENVELOPE_GENERATOR_ROWS",
    "MAX_MMCIF_ASSEMBLY_ENVELOPE_INPUT_BYTES",
    "MAX_MMCIF_ASSEMBLY_ENVELOPE_OPERATOR_ROWS",
    "MAX_MMCIF_ASSEMBLY_ENVELOPE_OUTPUT_LINE_CHARS",
    "MAX_MMCIF_ASSEMBLY_ENVELOPE_SOURCE_ID_BYTES",
    "MAX_MMCIF_ASSEMBLY_ENVELOPE_TOKEN_CHARS",
    "MMCIF_ASSEMBLY_DECLARATION_PROJECTION_SCHEMA_ID",
    "MMCIF_ASSEMBLY_DEFINITION_HEADERS",
    "MMCIF_ASSEMBLY_ENVELOPE_VERSION",
    "MMCIF_ASSEMBLY_EXPANDED_STATE_SCHEMA_ID",
    "MMCIF_ASSEMBLY_GENERATOR_HEADERS",
    "MMCIF_ASSEMBLY_OPERATOR_HEADERS",
    "MMCIF_ASSEMBLY_PARSER_VERSION",
    "MMCIF_ASSEMBLY_PROFILE_ID",
    "MMCIF_ASSEMBLY_PROJECTION_SCOPE",
    "MMCIF_ASSEMBLY_RECORD_STATE_SCHEMA_ID",
    "MMCIF_ASSEMBLY_ROUND_TRIP_REPORT_SCHEMA_ID",
    "MMCIF_ASSEMBLY_SOURCE_BINDING_SCHEMA_ID",
    "MMCIF_ASSEMBLY_WRITER_VERSION",
    "MMCIF_ASSEMBLY_WRITE_RECEIPT_SCHEMA_ID",
    "MmcifAssemblyEnvelopeError",
    "MmcifAssemblyIngestResult",
    "MmcifAssemblyRoundTripReport",
    "MmcifAssemblyRoundTripResult",
    "MmcifAssemblyWriteReceipt",
    "MmcifAssemblyWriteResult",
    "emit_mmcif_assembly",
    "mmcif_assembly_declaration_projection_sha256",
    "mmcif_assembly_expanded_state_sha256",
    "parse_mmcif_assembly",
    "round_trip_mmcif_assembly_source",
    "serialize_mmcif_assembly",
]
