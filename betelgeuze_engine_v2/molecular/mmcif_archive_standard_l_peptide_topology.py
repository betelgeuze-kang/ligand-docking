"""Archive-aligned, sequence-implied ALA/GLY heavy topology profile.

This opt-in parser accepts exactly five mmCIF categories.  It delegates the
four coordinate/sequence carrier categories unchanged to the existing strict
polymer-sequence parser, validates one engine-selected five-field
``_entity_poly`` profile, and materializes the pinned engine-owned ALA/GLY
heavy reference graph.  Sequence adjacency, not coordinate distance or auth
aliases, selects peptide C--N reference bonds.

The result is deliberately not observed-covalence evidence, source
authentication, protonation, hydrogen completion, preparation,
parameterability, physics support, or general mmCIF support.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
import hashlib
import json
import re
from typing import Any
import weakref

from .mmcif_polymer_sequence import (
    MMCIF_ENTITY_POLY_SEQ_HEADERS,
    MMCIF_POLYMER_SEQUENCE_PROFILE_ID,
    MmcifPolymerSequenceError,
    MmcifPolymerSequenceIngestResult,
    parse_mmcif_polymer_sequence,
    serialize_mmcif_polymer_sequence,
)
from .mmcif_syntax import CifBlock, CifLoop, CifSyntaxError, CifToken, parse_cif_block
from .models import AllAtomSystem, Bond
from .observation import (
    MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_PREPARATION_INVENTORY_COMMITMENT_SCHEMA_ID,
    attach_parser_observation_digest,
    attached_parser_observation_sha256_matches,
    mmcif_archive_standard_l_peptide_topology_preparation_inventory_sha256,
)
from .serialization import deserialize_all_atom_system, serialize_all_atom_system
from .standard_l_peptide_rules import (
    STANDARD_L_PEPTIDE_INTER_RESIDUE_ATOM_IDS,
    STANDARD_L_PEPTIDE_INTER_RESIDUE_BOND_ORDER,
    STANDARD_L_PEPTIDE_INTER_RESIDUE_RULE_ID,
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


MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_ENVELOPE_VERSION = "1.0.0"
MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_PARSER_VERSION = "1.0.0"
MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_WRITER_VERSION = "1.0.0"
MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_PARSER_NAME = (
    "betelgeuze_engine_v2.molecular.mmcif_archive_standard_l_peptide_topology."
    "parse_mmcif_archive_standard_l_peptide_topology"
)
MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_PARSER_PEDIGREE_ID = (
    "betelgeuze.mmcif_archive_standard_l_peptide_topology_parser/1.0.0"
)
MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_PROFILE_ID = (
    "strict_mmcif_archive_standard_l_peptide_ALA_GLY_heavy_topology/1.0.0"
)
MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_PROJECTION_SCHEMA_ID = (
    "betelgeuze.mmcif_archive_standard_l_peptide_topology_projection/1.0.0"
)
MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_STATE_SCHEMA_ID = (
    "betelgeuze.mmcif_archive_standard_l_peptide_topology_state/1.0.0"
)
MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_SOURCE_BINDING_SCHEMA_ID = (
    "betelgeuze.mmcif_archive_standard_l_peptide_topology_source_binding/1.0.0"
)
MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_WRITE_RECEIPT_SCHEMA_ID = (
    "betelgeuze.mmcif_archive_standard_l_peptide_topology_write_receipt/1.0.0"
)
MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_ROUND_TRIP_REPORT_SCHEMA_ID = (
    "betelgeuze.mmcif_archive_standard_l_peptide_topology_round_trip_report/1.0.0"
)

MAX_MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_INPUT_BYTES = 64 * 1024 * 1024
MAX_MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_OUTPUT_BYTES = 64 * 1024 * 1024
MAX_MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_SOURCE_ID_BYTES = 4_096
MAX_MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOKEN_CHARS = 2_048
MAX_MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_ATOMS = 80_000
MAX_MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_BONDS = 300_000

MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_ENTITY_HEADERS = (
    "_entity.id",
    "_entity.type",
)
MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_ENTITY_POLY_HEADERS = (
    "_entity_poly.entity_id",
    "_entity_poly.type",
    "_entity_poly.nstd_chirality",
    "_entity_poly.nstd_linkage",
    "_entity_poly.nstd_monomer",
)
MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_STRUCT_ASYM_HEADERS = (
    "_struct_asym.id",
    "_struct_asym.entity_id",
)
MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_ATOM_SITE_HEADERS = (
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
    "_entity_poly",
    "_struct_asym",
    "_entity_poly_seq",
    "_atom_site",
)
_CARRIER_CATEGORY_ORDER = (
    "_entity",
    "_struct_asym",
    "_entity_poly_seq",
    "_atom_site",
)
_EXPECTED_CATEGORIES = frozenset(_CATEGORY_ORDER)
_POSITIVE_INTEGER_RE = re.compile(r"^[1-9][0-9]*$")
_FACTORY_TOKEN = object()
_MARKER_KEY = "mmcif_archive_standard_l_peptide_topology"
_FACTORY_ARTIFACT_ANCHORS: dict[int, tuple[weakref.ReferenceType[Any], bytes]] = {}

_BOUNDED_TRUE_FIELDS = {
    "engine_rule_manifest_matched": True,
    "sequence_implied_standard_l_peptide_reference_topology_materialized": True,
    "sequence_implied_sequence_adjacent_peptide_reference_bonds_materialized": True,
}
_FALSE_AUTHORITY_FIELDS = (
    "source_authenticated",
    "observed_covalent_bond_established",
    "source_observed_covalence_established",
    "coordinate_peptide_geometry_validated",
    "coordinate_chain_breaks_excluded",
    "chemical_chain_breaks_detected_or_excluded",
    "independent_chemistry_established",
    "generic_chemistry_supported",
    "formal_charge_assigned",
    "protonation_interpreted",
    "hydrogens_completed",
    "stereochemistry_assigned",
    "modified_residue_supported",
    "nonstandard_monomer_supported",
    "preparation_ready",
    "generic_preparation_ready",
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
)


class MmcifArchiveStandardLPeptideTopologyError(ValueError):
    """Privacy-safe failure for the exact archive-aligned profile."""

    def __init__(
        self, code: str, message: str, *, line_number: int | None = None
    ) -> None:
        self.code = str(code)
        self.detail = str(message)
        self.line_number = None if line_number is None else int(line_number)
        suffix = "" if line_number is None else f" at line {line_number}"
        super().__init__(
            f"mmcif_archive_standard_l_peptide_topology:{self.code}{suffix}: "
            f"{self.detail}"
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


def _register_factory_artifact_anchor(value: Any, binding: bytes) -> None:
    object_id = id(value)

    def _discard(reference: weakref.ReferenceType[Any]) -> None:
        current = _FACTORY_ARTIFACT_ANCHORS.get(object_id)
        if current is not None and current[0] is reference:
            _FACTORY_ARTIFACT_ANCHORS.pop(object_id, None)

    _FACTORY_ARTIFACT_ANCHORS[object_id] = (weakref.ref(value, _discard), binding)


def _validate_factory_artifact_anchor(value: Any, binding: bytes) -> None:
    stored = _FACTORY_ARTIFACT_ANCHORS.get(id(value))
    if stored is None or stored[0]() is not value or stored[1] != binding:
        raise MmcifArchiveStandardLPeptideTopologyError(
            "stale_factory_artifact", "factory artifact identity binding is stale"
        )


def _source_id_sha256(source_id: str) -> str:
    if type(source_id) is not str:
        raise TypeError("source_id must be a string")
    encoded = source_id.encode("utf-8")
    if len(encoded) > MAX_MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_SOURCE_ID_BYTES:
        raise MmcifArchiveStandardLPeptideTopologyError(
            "source_id_too_long", "source identifier exceeds the UTF-8 byte limit"
        )
    return _sha256_bytes(encoded)


def _parse_block(data: bytes) -> CifBlock:
    if type(data) is not bytes:
        raise TypeError("mmCIF archive standard peptide input must be bytes")
    if not data:
        raise MmcifArchiveStandardLPeptideTopologyError("empty_input", "input is empty")
    if len(data) > MAX_MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_INPUT_BYTES:
        raise MmcifArchiveStandardLPeptideTopologyError(
            "input_too_large", "input exceeds the fixed byte limit"
        )
    try:
        text = data.decode("ascii")
    except UnicodeDecodeError:
        raise MmcifArchiveStandardLPeptideTopologyError(
            "non_ascii_input", "input must use the CIF 1.1 ASCII character set"
        ) from None
    try:
        return parse_cif_block(text)
    except CifSyntaxError as exc:
        raise MmcifArchiveStandardLPeptideTopologyError(
            "invalid_cif_syntax",
            "input is outside the exact single-block CIF grammar",
            line_number=exc.line_number,
        ) from None


def _loop_for(block: CifBlock, category: str) -> CifLoop:
    scalar = [name for name in block.scalar_values if name.split(".", 1)[0] == category]
    loops = [loop for loop in block.loops if category in loop.categories]
    if scalar or len(loops) != 1 or loops[0].categories != (category,):
        raise MmcifArchiveStandardLPeptideTopologyError(
            "unsupported_category_representation",
            "each selected category must occur in one category-local loop",
        )
    return loops[0]


def _bare(token: CifToken, *, code: str, allow_missing: bool = False) -> str:
    if token.quoted or token.multiline or not token.value:
        raise MmcifArchiveStandardLPeptideTopologyError(
            code,
            "selected value must be a bounded bare token",
            line_number=token.line_number,
        )
    if not allow_missing and token.value in {".", "?"}:
        raise MmcifArchiveStandardLPeptideTopologyError(
            code, "selected value must be nonmissing", line_number=token.line_number
        )
    if len(token.value) > MAX_MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOKEN_CHARS:
        raise MmcifArchiveStandardLPeptideTopologyError(
            "token_too_long", "selected token exceeds the character limit"
        )
    return token.value


def _validate_surface(block: CifBlock) -> dict[str, CifLoop]:
    if set(block.categories) != _EXPECTED_CATEGORIES:
        raise MmcifArchiveStandardLPeptideTopologyError(
            "unsupported_category_surface",
            "input categories must exactly match the five-category profile",
        )
    if block.scalar_values or len(block.loops) != len(_CATEGORY_ORDER):
        raise MmcifArchiveStandardLPeptideTopologyError(
            "unsupported_category_representation",
            "the profile requires exactly one loop per selected category",
        )
    loops = {category: _loop_for(block, category) for category in _CATEGORY_ORDER}
    expected_headers = {
        "_entity": MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_ENTITY_HEADERS,
        "_entity_poly": MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_ENTITY_POLY_HEADERS,
        "_struct_asym": MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_STRUCT_ASYM_HEADERS,
        "_entity_poly_seq": MMCIF_ENTITY_POLY_SEQ_HEADERS,
        "_atom_site": MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_ATOM_SITE_HEADERS,
    }
    for category, headers in expected_headers.items():
        loop = loops[category]
        if loop.tags != headers:
            raise MmcifArchiveStandardLPeptideTopologyError(
                f"unsupported_{category[1:]}_headers",
                "selected category headers are outside the exact engine profile",
                line_number=loop.line_number,
            )
        for row in loop.rows:
            for token in row:
                if len(token.value) > MAX_MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOKEN_CHARS:
                    raise MmcifArchiveStandardLPeptideTopologyError(
                        "token_too_long", "selected token exceeds the character limit"
                    )
    if not loops["_entity"].rows or not loops["_atom_site"].rows:
        raise MmcifArchiveStandardLPeptideTopologyError(
            "missing_required_rows", "entity and atom-site loops must be nonempty"
        )
    if len(loops["_atom_site"].rows) > MAX_MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_ATOMS:
        raise MmcifArchiveStandardLPeptideTopologyError(
            "too_many_atoms", "atom-site row count exceeds the profile limit"
        )
    return loops


def _token_text(token: CifToken) -> str:
    if token.multiline:
        raise MmcifArchiveStandardLPeptideTopologyError(
            "unsupported_multiline_token", "multiline values are outside the profile"
        )
    if not token.quoted:
        return token.value
    if "'" not in token.value:
        return f"'{token.value}'"
    if '"' not in token.value:
        return f'"{token.value}"'
    raise MmcifArchiveStandardLPeptideTopologyError(
        "unsupported_quoted_token", "quoted token has no single-line representation"
    )


def _emit_rows(headers: tuple[str, ...], rows: tuple[tuple[str, ...], ...]) -> bytes:
    lines = ["loop_", *headers]
    for row in rows:
        joined = " ".join(row)
        lines.extend((joined,) if len(joined) <= 2_048 else row)
    lines.append("#")
    return ("\n".join(lines) + "\n").encode("ascii")


def _emit_loop(loop: CifLoop) -> bytes:
    return _emit_rows(
        loop.tags,
        tuple(tuple(_token_text(token) for token in row) for row in loop.rows),
    )


def _carrier_source(block: CifBlock, loops: Mapping[str, CifLoop]) -> bytes:
    return b"".join(
        (
            f"data_{block.name}\n#\n".encode("ascii"),
            *(_emit_loop(loops[category]) for category in _CARRIER_CATEGORY_ORDER),
        )
    )


@dataclass(frozen=True, slots=True)
class MmcifArchiveStandardLPeptideEntityPolyRow:
    entity_id: str
    polymer_type: str = "polypeptide(L)"
    nstd_chirality: str = "no"
    nstd_linkage: str = "no"
    nstd_monomer: str = "no"

    def values(self) -> tuple[str, ...]:
        return (
            self.entity_id,
            self.polymer_type,
            self.nstd_chirality,
            self.nstd_linkage,
            self.nstd_monomer,
        )


def _parse_entities_and_poly(
    loops: Mapping[str, CifLoop],
) -> tuple[
    tuple[str, ...],
    tuple[MmcifArchiveStandardLPeptideEntityPolyRow, ...],
    dict[str, tuple[str, ...]],
]:
    entity_ids: list[str] = []
    for row in loops["_entity"].rows:
        entity_id = _bare(row[0], code="invalid_entity_id")
        entity_type = _bare(row[1], code="invalid_entity_type")
        if entity_type != "polymer":
            raise MmcifArchiveStandardLPeptideTopologyError(
                "nonpolymer_entity", "the exact profile is polymer-only"
            )
        if entity_id in entity_ids:
            raise MmcifArchiveStandardLPeptideTopologyError(
                "duplicate_entity_id", "entity IDs must be unique"
            )
        entity_ids.append(entity_id)

    poly_by_entity: dict[str, MmcifArchiveStandardLPeptideEntityPolyRow] = {}
    for row in loops["_entity_poly"].rows:
        values = tuple(_bare(token, code="invalid_entity_poly_value") for token in row)
        entity_id, polymer_type, chirality, linkage, monomer = values
        if entity_id not in entity_ids:
            raise MmcifArchiveStandardLPeptideTopologyError(
                "entity_poly_join_mismatch",
                "entity-poly row does not join a polymer entity",
            )
        if entity_id in poly_by_entity:
            raise MmcifArchiveStandardLPeptideTopologyError(
                "duplicate_entity_poly_row", "each polymer entity must have one row"
            )
        if (polymer_type, chirality, linkage, monomer) != (
            "polypeptide(L)",
            "no",
            "no",
            "no",
        ):
            raise MmcifArchiveStandardLPeptideTopologyError(
                "unsupported_entity_poly_profile",
                "entity-poly values are outside the standard L-peptide profile",
            )
        poly_by_entity[entity_id] = MmcifArchiveStandardLPeptideEntityPolyRow(
            entity_id=entity_id
        )
    if set(poly_by_entity) != set(entity_ids):
        raise MmcifArchiveStandardLPeptideTopologyError(
            "entity_poly_coverage_mismatch",
            "every polymer entity must have exactly one entity-poly row",
        )

    asym_lists: dict[str, list[str]] = {entity_id: [] for entity_id in entity_ids}
    seen_asym: set[str] = set()
    for row in loops["_struct_asym"].rows:
        asym_id = _bare(row[0], code="invalid_struct_asym_id")
        entity_id = _bare(row[1], code="invalid_struct_asym_entity_id")
        if asym_id in seen_asym:
            raise MmcifArchiveStandardLPeptideTopologyError(
                "duplicate_struct_asym_id", "struct-asym IDs must be unique"
            )
        if entity_id not in asym_lists:
            raise MmcifArchiveStandardLPeptideTopologyError(
                "struct_asym_join_mismatch", "struct-asym row does not join an entity"
            )
        seen_asym.add(asym_id)
        asym_lists[entity_id].append(asym_id)
    if any(not values for values in asym_lists.values()):
        raise MmcifArchiveStandardLPeptideTopologyError(
            "struct_asym_coverage_mismatch", "every entity must have an asym instance"
        )
    return (
        tuple(entity_ids),
        tuple(poly_by_entity[entity_id] for entity_id in entity_ids),
        {entity_id: tuple(values) for entity_id, values in asym_lists.items()},
    )


@dataclass(frozen=True, slots=True)
class _AtomPlan:
    atom_index: int
    entity_id: str
    asym_id: str
    sequence_number: int
    component_id: str
    atom_id: str
    element: str
    sequence_role: str


def _sequence_role(number: int, length: int) -> str:
    if length == 1:
        return "singleton"
    if number == 1:
        return "n_sequence_boundary"
    if number == length:
        return "c_sequence_boundary"
    return "internal"


def _validate_atom_roles(
    loops: Mapping[str, CifLoop],
    carrier: MmcifPolymerSequenceIngestResult,
    entity_ids: tuple[str, ...],
    asym_by_entity: Mapping[str, tuple[str, ...]],
) -> tuple[tuple[_AtomPlan, ...], dict[tuple[str, int, str], int]]:
    sequence_by_entity: dict[str, list[Any]] = {
        entity_id: [] for entity_id in entity_ids
    }
    for sequence_row in carrier.sequence_rows:
        if sequence_row.mon_id not in {"ALA", "GLY"}:
            raise MmcifArchiveStandardLPeptideTopologyError(
                "unsupported_monomer", "only ALA and GLY are admitted"
            )
        sequence_by_entity[sequence_row.entity_id].append(sequence_row)
    for entity_id, rows in sequence_by_entity.items():
        rows.sort(key=lambda item: item.num)
        if [row.num for row in rows] != list(range(1, len(rows) + 1)):
            raise MmcifArchiveStandardLPeptideTopologyError(
                "sequence_gap", "sequence positions must be contiguous from one"
            )
        expected_asym = set(asym_by_entity[entity_id])
        if any(set(row.observed_asym_ids) != expected_asym for row in rows):
            raise MmcifArchiveStandardLPeptideTopologyError(
                "missing_sequence_instance",
                "every sequence position must be coordinate-observed in every asym",
            )

    atom_loop = loops["_atom_site"]
    index = {tag: position for position, tag in enumerate(atom_loop.tags)}
    plans: list[_AtomPlan] = []
    endpoints: dict[tuple[str, int, str], int] = {}
    roles_by_instance: dict[tuple[str, int], dict[str, str]] = {}
    component_by_position = {
        (row.entity_id, row.num): row.mon_id for row in carrier.sequence_rows
    }
    asym_entity = {
        asym_id: entity_id
        for entity_id, asym_ids in asym_by_entity.items()
        for asym_id in asym_ids
    }
    sequence_lengths = {
        entity_id: len(rows) for entity_id, rows in sequence_by_entity.items()
    }
    for atom_index, row in enumerate(atom_loop.rows):
        group = _bare(row[index["_atom_site.group_pdb"]], code="invalid_atom_group")
        element = _bare(row[index["_atom_site.type_symbol"]], code="invalid_element")
        atom_id = _bare(row[index["_atom_site.label_atom_id"]], code="invalid_atom_id")
        alt = _bare(
            row[index["_atom_site.label_alt_id"]],
            code="unsupported_altloc",
            allow_missing=True,
        )
        component_id = _bare(
            row[index["_atom_site.label_comp_id"]], code="invalid_component_id"
        )
        asym_id = _bare(row[index["_atom_site.label_asym_id"]], code="invalid_asym_id")
        entity_id = _bare(
            row[index["_atom_site.label_entity_id"]], code="invalid_atom_entity_id"
        )
        seq_token = row[index["_atom_site.label_seq_id"]]
        insertion = _bare(
            row[index["_atom_site.pdbx_pdb_ins_code"]],
            code="unsupported_insertion_code",
            allow_missing=True,
        )
        formal_charge = _bare(
            row[index["_atom_site.pdbx_formal_charge"]],
            code="unsupported_formal_charge",
            allow_missing=True,
        )
        model = _bare(
            row[index["_atom_site.pdbx_pdb_model_num"]], code="unsupported_model"
        )
        if group != "ATOM":
            raise MmcifArchiveStandardLPeptideTopologyError(
                "unsupported_atom_group", "only ATOM rows are admitted"
            )
        if alt != ".":
            raise MmcifArchiveStandardLPeptideTopologyError(
                "unsupported_altloc", "alternate locations are outside the profile"
            )
        if insertion != "?":
            raise MmcifArchiveStandardLPeptideTopologyError(
                "unsupported_insertion_code", "insertion codes are outside the profile"
            )
        if formal_charge != "?":
            raise MmcifArchiveStandardLPeptideTopologyError(
                "formal_charge_must_be_unknown",
                "the profile preserves source formal-charge unknownness only",
            )
        if model != "1":
            raise MmcifArchiveStandardLPeptideTopologyError(
                "unsupported_model", "the profile accepts only model 1"
            )
        if (
            seq_token.quoted
            or seq_token.multiline
            or not _POSITIVE_INTEGER_RE.fullmatch(seq_token.value)
        ):
            raise MmcifArchiveStandardLPeptideTopologyError(
                "invalid_sequence_number",
                "label sequence ID must be a positive integer",
            )
        sequence_number = int(seq_token.value)
        if asym_entity.get(asym_id) != entity_id:
            raise MmcifArchiveStandardLPeptideTopologyError(
                "atom_asym_entity_join_mismatch", "atom asym/entity IDs do not join"
            )
        if component_by_position.get((entity_id, sequence_number)) != component_id:
            raise MmcifArchiveStandardLPeptideTopologyError(
                "atom_sequence_join_mismatch",
                "atom component does not join the sequence",
            )
        try:
            rule = standard_l_peptide_component_rule(component_id)
        except StandardLPeptideRuleError:
            raise MmcifArchiveStandardLPeptideTopologyError(
                "unsupported_monomer", "atom component has no admitted engine rule"
            ) from None
        expected_element = dict(
            rule.atom_elements(
                c_sequence_boundary=sequence_number == sequence_lengths[entity_id]
            )
        ).get(atom_id)
        if expected_element is None:
            raise MmcifArchiveStandardLPeptideTopologyError(
                "extra_or_disallowed_atom_role",
                "atom role is outside the exact residue-boundary rule",
            )
        if element == "H":
            raise MmcifArchiveStandardLPeptideTopologyError(
                "hydrogen_not_supported", "the profile is heavy-atom-only"
            )
        if element != expected_element:
            raise MmcifArchiveStandardLPeptideTopologyError(
                "atom_element_mismatch",
                "atom role element differs from the pinned rule",
            )
        instance = (asym_id, sequence_number)
        role_map = roles_by_instance.setdefault(instance, {})
        if atom_id in role_map:
            raise MmcifArchiveStandardLPeptideTopologyError(
                "duplicate_residue_atom", "residue atom roles must be unique"
            )
        role_map[atom_id] = element
        endpoints[(asym_id, sequence_number, atom_id)] = atom_index
        plans.append(
            _AtomPlan(
                atom_index=atom_index,
                entity_id=entity_id,
                asym_id=asym_id,
                sequence_number=sequence_number,
                component_id=component_id,
                atom_id=atom_id,
                element=element,
                sequence_role=_sequence_role(
                    sequence_number, sequence_lengths[entity_id]
                ),
            )
        )

    for entity_id, rows in sequence_by_entity.items():
        for asym_id in asym_by_entity[entity_id]:
            for row in rows:
                expected = dict(
                    standard_l_peptide_component_rule(row.mon_id).atom_elements(
                        c_sequence_boundary=row.num == len(rows)
                    )
                )
                observed = roles_by_instance.get((asym_id, row.num), {})
                if observed != expected:
                    missing = set(expected) - set(observed)
                    code = (
                        "missing_link_endpoint"
                        if missing & {"N", "C"} and len(rows) > 1
                        else "residue_atom_role_mismatch"
                    )
                    raise MmcifArchiveStandardLPeptideTopologyError(
                        code, "residue atom roles do not exactly match the pinned rule"
                    )
    if len(plans) != carrier.system.atom_count:
        raise MmcifArchiveStandardLPeptideTopologyError(
            "carrier_atom_count_mismatch",
            "carrier atom count differs from atom-site rows",
        )
    for plan, atom in zip(plans, carrier.system.atoms, strict=True):
        if (
            atom.index != plan.atom_index
            or atom.name != plan.atom_id
            or atom.element != plan.element
            or atom.formal_charge_known is not False
        ):
            raise MmcifArchiveStandardLPeptideTopologyError(
                "carrier_atom_projection_mismatch",
                "carrier atom projection differs from selected source rows",
            )
    return tuple(plans), endpoints


def _materialize_system(
    carrier: MmcifPolymerSequenceIngestResult,
    plans: tuple[_AtomPlan, ...],
    endpoints: Mapping[tuple[str, int, str], int],
    asym_by_entity: Mapping[str, tuple[str, ...]],
    *,
    full_source: bytes,
    canonical_output: bytes,
) -> AllAtomSystem:
    carrier_system = carrier.system
    if carrier_system.bonds:
        raise MmcifArchiveStandardLPeptideTopologyError(
            "carrier_bonds_not_empty",
            "the fully observed polymer-sequence carrier must not own chemistry bonds",
        )
    marker_by_atom = {plan.atom_index: plan for plan in plans}
    atoms = tuple(
        replace(
            atom,
            metadata={
                **dict(atom.metadata),
                _MARKER_KEY: {
                    "component_id": marker_by_atom[atom.index].component_id,
                    "atom_id": marker_by_atom[atom.index].atom_id,
                    "asym_id": marker_by_atom[atom.index].asym_id,
                    "sequence_number": marker_by_atom[atom.index].sequence_number,
                    "sequence_role": marker_by_atom[atom.index].sequence_role,
                    "rule_id": standard_l_peptide_component_rule(
                        marker_by_atom[atom.index].component_id
                    ).rule_id,
                    "rule_manifest_sha256": STANDARD_L_PEPTIDE_RULE_MANIFEST_SHA256,
                },
            },
        )
        for atom in carrier_system.atoms
    )

    sequence_by_entity: dict[str, list[Any]] = {}
    for row in carrier.sequence_rows:
        sequence_by_entity.setdefault(row.entity_id, []).append(row)
    for rows in sequence_by_entity.values():
        rows.sort(key=lambda item: item.num)
    pending: list[Bond] = []
    intra_count = 0
    inter_count = 0
    for entity_id, rows in sequence_by_entity.items():
        for asym_id in asym_by_entity[entity_id]:
            for row in rows:
                rule = standard_l_peptide_component_rule(row.mon_id)
                for rule_bond in rule.active_bonds(
                    c_sequence_boundary=row.num == len(rows)
                ):
                    atom_i = endpoints[(asym_id, row.num, rule_bond.atom_id_1)]
                    atom_j = endpoints[(asym_id, row.num, rule_bond.atom_id_2)]
                    pending.append(
                        Bond(
                            index=-1,
                            atom_i=min(atom_i, atom_j),
                            atom_j=max(atom_i, atom_j),
                            order=rule_bond.order,
                            aromatic=False,
                            stereo="none",
                            source="engine_sequence_implied_standard_l_peptide_rule",
                            metadata={
                                _MARKER_KEY: {
                                    "bond_kind": "intra_residue_reference",
                                    "rule_id": rule.rule_id,
                                    "rule_manifest_sha256": STANDARD_L_PEPTIDE_RULE_MANIFEST_SHA256,
                                    "asym_id": asym_id,
                                    "left_sequence_number": row.num,
                                    "right_sequence_number": row.num,
                                    "left_atom_id": rule_bond.atom_id_1,
                                    "right_atom_id": rule_bond.atom_id_2,
                                }
                            },
                        )
                    )
                    intra_count += 1
            for left, right in zip(rows, rows[1:]):
                left_atom_id, right_atom_id = STANDARD_L_PEPTIDE_INTER_RESIDUE_ATOM_IDS
                atom_i = endpoints[(asym_id, left.num, left_atom_id)]
                atom_j = endpoints[(asym_id, right.num, right_atom_id)]
                pending.append(
                    Bond(
                        index=-1,
                        atom_i=min(atom_i, atom_j),
                        atom_j=max(atom_i, atom_j),
                        order=STANDARD_L_PEPTIDE_INTER_RESIDUE_BOND_ORDER,
                        aromatic=False,
                        stereo="none",
                        source="engine_sequence_implied_standard_l_peptide_rule",
                        metadata={
                            _MARKER_KEY: {
                                "bond_kind": "sequence_adjacent_peptide_reference",
                                "rule_id": STANDARD_L_PEPTIDE_INTER_RESIDUE_RULE_ID,
                                "rule_manifest_sha256": STANDARD_L_PEPTIDE_RULE_MANIFEST_SHA256,
                                "asym_id": asym_id,
                                "left_sequence_number": left.num,
                                "right_sequence_number": right.num,
                                "left_atom_id": left_atom_id,
                                "right_atom_id": right_atom_id,
                            }
                        },
                    )
                )
                inter_count += 1
    if len(pending) > MAX_MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_BONDS:
        raise MmcifArchiveStandardLPeptideTopologyError(
            "too_many_materialized_bonds", "materialized bond count exceeds the limit"
        )
    endpoint_pairs = [(bond.atom_i, bond.atom_j) for bond in pending]
    if len(endpoint_pairs) != len(set(endpoint_pairs)):
        raise MmcifArchiveStandardLPeptideTopologyError(
            "duplicate_materialized_bond", "rule expansion produced duplicate endpoints"
        )
    pending.sort(key=lambda bond: (bond.atom_i, bond.atom_j))
    bonds = tuple(replace(bond, index=index) for index, bond in enumerate(pending))

    plan_by_residue: dict[int, _AtomPlan] = {}
    for plan, atom in zip(plans, carrier_system.atoms, strict=True):
        plan_by_residue.setdefault(atom.residue_index, plan)
    residues = tuple(
        replace(
            residue,
            metadata={
                **dict(residue.metadata),
                _MARKER_KEY: {
                    "component_id": plan_by_residue[residue.index].component_id,
                    "asym_id": plan_by_residue[residue.index].asym_id,
                    "sequence_number": plan_by_residue[residue.index].sequence_number,
                    "sequence_role": plan_by_residue[residue.index].sequence_role,
                    "rule_manifest_sha256": STANDARD_L_PEPTIDE_RULE_MANIFEST_SHA256,
                },
            },
        )
        for residue in carrier_system.residues
    )
    chains = tuple(
        replace(
            chain,
            metadata={
                **dict(chain.metadata),
                _MARKER_KEY: {
                    "asym_id": chain.chain_id,
                    "sequence_implied_link_count": max(
                        0, len(sequence_by_entity[chain.entity_id]) - 1
                    ),
                    "rule_manifest_sha256": STANDARD_L_PEPTIDE_RULE_MANIFEST_SHA256,
                },
            },
        )
        for chain in carrier_system.chains
    )

    provenance_metadata = dict(carrier_system.provenance.metadata)
    provenance_metadata.pop("canonical_topology_schema_id", None)
    provenance_metadata.pop("canonical_topology_sha256", None)
    provenance_metadata.pop("parser_observation_schema_id", None)
    provenance_metadata.pop("parser_observation_sha256", None)
    provenance_metadata[_MARKER_KEY] = {
        "profile_id": MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_PROFILE_ID,
        "parser_pedigree_id": MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_PARSER_PEDIGREE_ID,
        "rule_manifest_schema_id": STANDARD_L_PEPTIDE_RULE_MANIFEST_SCHEMA_ID,
        "rule_manifest_sha256": STANDARD_L_PEPTIDE_RULE_MANIFEST_SHA256,
        "canonical_output_sha256": _sha256_bytes(canonical_output),
        "source_hash_semantics": "raw_full_source_bytes_tamper_evidence",
        "source_authenticated": False,
    }
    provenance = replace(
        carrier_system.provenance,
        source_sha256=_sha256_bytes(full_source),
        parser_name=MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_PARSER_NAME,
        parser_version=MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_PARSER_VERSION,
        operations=(
            *carrier_system.provenance.operations,
            "validate_pinned_standard_l_peptide_rule_manifest/v1",
            "materialize_sequence_implied_ALA_GLY_heavy_reference_topology/v1",
        ),
        parent_sha256=(_sha256_bytes(serialize_all_atom_system(carrier_system)),),
        preparation_ready=False,
        claim_safe=False,
        metadata=provenance_metadata,
    )
    profile_marker = {
        "profile_id": MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_PROFILE_ID,
        "parser_pedigree_id": MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_PARSER_PEDIGREE_ID,
        "rule_manifest_schema_id": STANDARD_L_PEPTIDE_RULE_MANIFEST_SCHEMA_ID,
        "rule_manifest_sha256": STANDARD_L_PEPTIDE_RULE_MANIFEST_SHA256,
        "materialized_intra_residue_bond_count": intra_count,
        "materialized_inter_residue_bond_count": inter_count,
        **_BOUNDED_TRUE_FIELDS,
        **_authority_false_document(),
    }
    system = replace(
        carrier_system,
        atoms=atoms,
        bonds=bonds,
        residues=residues,
        chains=chains,
        provenance=provenance,
        metadata={**dict(carrier_system.metadata), _MARKER_KEY: profile_marker},
    )
    topology_sha = canonical_topology_sha256(system)
    system = replace(
        system,
        provenance=replace(
            system.provenance,
            metadata={
                **dict(system.provenance.metadata),
                "canonical_topology_schema_id": CANONICAL_TOPOLOGY_SCHEMA_ID,
                "canonical_topology_sha256": topology_sha,
            },
        ),
    )
    commitment_sha256 = (
        mmcif_archive_standard_l_peptide_topology_preparation_inventory_sha256(system)
    )
    provenance_metadata = dict(system.provenance.metadata)
    provenance_marker = dict(provenance_metadata[_MARKER_KEY])
    provenance_marker.update(
        {
            "preparation_inventory_commitment_schema_id": (
                MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_PREPARATION_INVENTORY_COMMITMENT_SCHEMA_ID
            ),
            "preparation_inventory_commitment_sha256": commitment_sha256,
        }
    )
    provenance_metadata[_MARKER_KEY] = provenance_marker
    system = replace(
        system,
        provenance=replace(system.provenance, metadata=provenance_metadata),
    )
    return attach_parser_observation_digest(system)


def _projection_document(
    carrier: MmcifPolymerSequenceIngestResult,
    entity_poly_rows: tuple[MmcifArchiveStandardLPeptideEntityPolyRow, ...],
    asym_by_entity: Mapping[str, tuple[str, ...]],
) -> dict[str, Any]:
    return {
        "schema_id": MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_PROJECTION_SCHEMA_ID,
        "profile_id": MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_PROFILE_ID,
        "carrier_profile_id": MMCIF_POLYMER_SEQUENCE_PROFILE_ID,
        "rule_manifest_sha256": STANDARD_L_PEPTIDE_RULE_MANIFEST_SHA256,
        "entity_poly_rows": [row.values() for row in entity_poly_rows],
        "entities": [
            {
                "entity_id": entity_id,
                "asym_ids": list(asym_by_entity[entity_id]),
                "sequence": [
                    {"num": row.num, "component_id": row.mon_id}
                    for row in carrier.sequence_rows
                    if row.entity_id == entity_id
                ],
            }
            for entity_id in asym_by_entity
        ],
    }


def _canonical_output(
    carrier: MmcifPolymerSequenceIngestResult,
    entity_poly_rows: tuple[MmcifArchiveStandardLPeptideEntityPolyRow, ...],
) -> bytes:
    carrier_payload = serialize_mmcif_polymer_sequence(carrier)
    carrier_block = _parse_block(carrier_payload)
    loops = {
        category: _loop_for(carrier_block, category)
        for category in _CARRIER_CATEGORY_ORDER
    }
    pieces: list[bytes] = [f"data_{carrier_block.name}\n#\n".encode("ascii")]
    for category in _CATEGORY_ORDER:
        if category == "_entity_poly":
            pieces.append(
                _emit_rows(
                    MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_ENTITY_POLY_HEADERS,
                    tuple(row.values() for row in entity_poly_rows),
                )
            )
        else:
            pieces.append(_emit_loop(loops[category]))
    payload = b"".join(pieces)
    if len(payload) > MAX_MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_OUTPUT_BYTES:
        raise MmcifArchiveStandardLPeptideTopologyError(
            "output_too_large", "canonical output exceeds the byte limit"
        )
    _validate_surface(_parse_block(payload))
    return payload


@dataclass(frozen=True, slots=True)
class _ParsedState:
    full_source: bytes = field(repr=False)
    source_id: str = field(repr=False)
    carrier_source: bytes = field(repr=False)
    canonical_output: bytes = field(repr=False)
    entity_poly_rows: tuple[MmcifArchiveStandardLPeptideEntityPolyRow, ...]
    projection_bytes: bytes = field(repr=False)
    system_snapshot: bytes = field(repr=False)
    topology_state_bytes: bytes = field(repr=False)
    source_binding_bytes: bytes = field(repr=False)


def _parse_state(data: bytes, *, source_id: str) -> _ParsedState:
    _source_id_sha256(source_id)
    try:
        validate_standard_l_peptide_rule_manifest()
    except StandardLPeptideRuleError:
        raise MmcifArchiveStandardLPeptideTopologyError(
            "rule_manifest_hash_mismatch",
            "runtime standard peptide rule manifest differs from the literal pin",
        ) from None
    block = _parse_block(data)
    loops = _validate_surface(block)
    entity_ids, entity_poly_rows, asym_by_entity = _parse_entities_and_poly(loops)
    carrier_source = _carrier_source(block, loops)
    try:
        carrier = parse_mmcif_polymer_sequence(carrier_source, source_id=source_id)
    except MmcifPolymerSequenceError as exc:
        code = (
            "sequence_microheterogeneity_not_supported"
            if exc.code == "microheterogeneity_not_supported"
            else "polymer_sequence_carrier_rejected"
        )
        raise MmcifArchiveStandardLPeptideTopologyError(
            code,
            "the exact polymer-sequence carrier rejected the selected projection",
            line_number=exc.line_number,
        ) from None
    if {row.entity_id for row in carrier.sequence_rows} != set(entity_ids):
        raise MmcifArchiveStandardLPeptideTopologyError(
            "sequence_entity_coverage_mismatch",
            "sequence rows must cover exactly the selected polymer entities",
        )
    plans, endpoints = _validate_atom_roles(loops, carrier, entity_ids, asym_by_entity)
    canonical_output = _canonical_output(carrier, entity_poly_rows)
    system = _materialize_system(
        carrier,
        plans,
        endpoints,
        asym_by_entity,
        full_source=data,
        canonical_output=canonical_output,
    )
    projection_bytes = _canonical_json_bytes(
        _projection_document(carrier, entity_poly_rows, asym_by_entity)
    )
    topology_document = {
        "schema_id": MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_STATE_SCHEMA_ID,
        "envelope_version": MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_ENVELOPE_VERSION,
        "parser_name": MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_PARSER_NAME,
        "parser_version": MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_PARSER_VERSION,
        "parser_pedigree_id": MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_PARSER_PEDIGREE_ID,
        "profile_id": MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_PROFILE_ID,
        "rule_manifest_sha256": STANDARD_L_PEPTIDE_RULE_MANIFEST_SHA256,
        "projection_sha256": _sha256_bytes(projection_bytes),
        "canonical_topology_sha256": canonical_topology_sha256(system),
        "atom_count": system.atom_count,
        "bond_count": len(system.bonds),
        "chain_count": len(system.chains),
        "attached_canonical_topology_digest_self_consistent": attached_canonical_topology_sha256_matches(
            system
        ),
        "attached_parser_observation_digest_self_consistent": attached_parser_observation_sha256_matches(
            system
        ),
        **_BOUNDED_TRUE_FIELDS,
        **_authority_false_document(),
    }
    topology_state_bytes = _canonical_json_bytes(topology_document)
    system_snapshot = serialize_all_atom_system(system)
    source_binding_bytes = _canonical_json_bytes(
        {
            "schema_id": MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_SOURCE_BINDING_SCHEMA_ID,
            "full_source_sha256": _sha256_bytes(data),
            "source_id_sha256": _source_id_sha256(source_id),
            "carrier_source_sha256": _sha256_bytes(carrier_source),
            "canonical_output_sha256": _sha256_bytes(canonical_output),
            "projection_sha256": _sha256_bytes(projection_bytes),
            "topology_state_sha256": _sha256_bytes(topology_state_bytes),
            "system_snapshot_sha256": _sha256_bytes(system_snapshot),
            "system_provenance_source_sha256": system.provenance.source_sha256,
            "rule_manifest_sha256": STANDARD_L_PEPTIDE_RULE_MANIFEST_SHA256,
            **_BOUNDED_TRUE_FIELDS,
            **_authority_false_document(),
        }
    )
    return _ParsedState(
        full_source=data,
        source_id=source_id,
        carrier_source=carrier_source,
        canonical_output=canonical_output,
        entity_poly_rows=entity_poly_rows,
        projection_bytes=projection_bytes,
        system_snapshot=system_snapshot,
        topology_state_bytes=topology_state_bytes,
        source_binding_bytes=source_binding_bytes,
    )


@dataclass(frozen=True, init=False)
class MmcifArchiveStandardLPeptideTopologyIngestResult:
    _state: _ParsedState = field(repr=False)
    _access_binding_bytes: bytes = field(repr=False)

    def __init__(
        self, state: _ParsedState, *, _factory_token: object | None = None
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN or type(state) is not _ParsedState:
            raise TypeError(
                "MmcifArchiveStandardLPeptideTopologyIngestResult is factory-only"
            )
        object.__setattr__(self, "_state", state)
        binding = _canonical_json_bytes(
            {
                "artifact_type": "MmcifArchiveStandardLPeptideTopologyIngestResult",
                "self_object_id": id(self),
                "state_object_id": id(state),
                "full_source_sha256": _sha256_bytes(state.full_source),
                "source_binding_sha256": _sha256_bytes(state.source_binding_bytes),
                "system_snapshot_sha256": _sha256_bytes(state.system_snapshot),
            }
        )
        object.__setattr__(self, "_access_binding_bytes", binding)
        _register_factory_artifact_anchor(self, binding)

    @property
    def system(self) -> AllAtomSystem:
        return deserialize_all_atom_system(_validate_ingest(self).system_snapshot)

    @property
    def entity_poly_rows(
        self,
    ) -> tuple[MmcifArchiveStandardLPeptideEntityPolyRow, ...]:
        return _validate_ingest(self).entity_poly_rows

    @property
    def full_source_sha256(self) -> str:
        return _sha256_bytes(_validate_ingest(self).full_source)

    @property
    def projection_sha256(self) -> str:
        return _sha256_bytes(_validate_ingest(self).projection_bytes)

    @property
    def topology_state_sha256(self) -> str:
        return _sha256_bytes(_validate_ingest(self).topology_state_bytes)

    @property
    def record_state_sha256(self) -> str:
        return self.topology_state_sha256

    @property
    def source_binding_sha256(self) -> str:
        return _sha256_bytes(_validate_ingest(self).source_binding_bytes)

    @property
    def topology_sha256(self) -> str:
        return str(
            _topology_document(_validate_ingest(self))["canonical_topology_sha256"]
        )

    def to_dict(self) -> dict[str, Any]:
        state = _validate_ingest(self)
        source = json.loads(state.source_binding_bytes.decode("ascii"))
        return {
            **_topology_document(state),
            "full_source_sha256": source["full_source_sha256"],
            "source_id_sha256": source["source_id_sha256"],
            "system_snapshot_sha256": source["system_snapshot_sha256"],
            "canonical_output_sha256": source["canonical_output_sha256"],
            "source_binding_sha256": _sha256_bytes(state.source_binding_bytes),
            "topology_state_sha256": _sha256_bytes(state.topology_state_bytes),
        }


def _topology_document(state: _ParsedState) -> dict[str, Any]:
    return json.loads(state.topology_state_bytes.decode("ascii"))


def _ingest_access_binding(
    value: MmcifArchiveStandardLPeptideTopologyIngestResult,
) -> bytes:
    state = value._state
    return _canonical_json_bytes(
        {
            "artifact_type": "MmcifArchiveStandardLPeptideTopologyIngestResult",
            "self_object_id": id(value),
            "state_object_id": id(state),
            "full_source_sha256": _sha256_bytes(state.full_source),
            "source_binding_sha256": _sha256_bytes(state.source_binding_bytes),
            "system_snapshot_sha256": _sha256_bytes(state.system_snapshot),
        }
    )


def _validate_ingest(
    value: MmcifArchiveStandardLPeptideTopologyIngestResult,
) -> _ParsedState:
    if type(value) is not MmcifArchiveStandardLPeptideTopologyIngestResult:
        raise TypeError("an exact archive standard peptide ingest is required")
    try:
        state = value._state
        access_binding = _ingest_access_binding(value)
        _validate_factory_artifact_anchor(value, access_binding)
        fresh = _parse_state(state.full_source, source_id=state.source_id)
        system = deserialize_all_atom_system(state.system_snapshot)
    except Exception:
        raise MmcifArchiveStandardLPeptideTopologyError(
            "stale_ingest_binding", "stored ingest evidence differs from factory state"
        ) from None
    if (
        state != fresh
        or value._access_binding_bytes != access_binding
        or system.provenance.parser_name
        != MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_PARSER_NAME
        or system.provenance.parser_version
        != MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_PARSER_VERSION
        or not attached_canonical_topology_sha256_matches(system)
        or not attached_parser_observation_sha256_matches(system)
        or system.metadata.get(_MARKER_KEY, {}).get("rule_manifest_sha256")
        != STANDARD_L_PEPTIDE_RULE_MANIFEST_SHA256
    ):
        raise MmcifArchiveStandardLPeptideTopologyError(
            "stale_ingest_binding", "stored ingest evidence differs from factory state"
        )
    return state


def parse_mmcif_archive_standard_l_peptide_topology(
    data: bytes, *, source_id: str = ""
) -> MmcifArchiveStandardLPeptideTopologyIngestResult:
    return MmcifArchiveStandardLPeptideTopologyIngestResult(
        _parse_state(data, source_id=source_id), _factory_token=_FACTORY_TOKEN
    )


def mmcif_archive_standard_l_peptide_topology_projection_sha256(
    value: MmcifArchiveStandardLPeptideTopologyIngestResult,
) -> str:
    return _sha256_bytes(_validate_ingest(value).projection_bytes)


def mmcif_archive_standard_l_peptide_topology_state_sha256(
    value: MmcifArchiveStandardLPeptideTopologyIngestResult,
) -> str:
    return _sha256_bytes(_validate_ingest(value).topology_state_bytes)


@dataclass(frozen=True, init=False)
class MmcifArchiveStandardLPeptideTopologyWriteReceipt:
    _ingest: MmcifArchiveStandardLPeptideTopologyIngestResult = field(repr=False)
    _payload: bytes = field(repr=False)
    _document_bytes: bytes = field(repr=False)
    _access_binding_bytes: bytes = field(repr=False)

    def __init__(
        self,
        ingest: MmcifArchiveStandardLPeptideTopologyIngestResult,
        payload: bytes,
        document: Mapping[str, Any],
        *,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise TypeError(
                "MmcifArchiveStandardLPeptideTopologyWriteReceipt is factory-only"
            )
        state = _validate_ingest(ingest)
        if payload != state.canonical_output or dict(document) != _receipt_document(
            state
        ):
            raise MmcifArchiveStandardLPeptideTopologyError(
                "crosswired_write_artifacts", "write receipt inputs are crosswired"
            )
        object.__setattr__(self, "_ingest", ingest)
        object.__setattr__(self, "_payload", payload)
        object.__setattr__(self, "_document_bytes", _canonical_json_bytes(document))
        binding = _write_receipt_access_binding(self)
        object.__setattr__(self, "_access_binding_bytes", binding)
        _register_factory_artifact_anchor(self, binding)

    @property
    def receipt_sha256(self) -> str:
        return _sha256_bytes(_validate_receipt(self))

    def to_dict(self) -> dict[str, Any]:
        document_bytes = _validate_receipt(self)
        return {
            **json.loads(document_bytes.decode("ascii")),
            "receipt_sha256": _sha256_bytes(document_bytes),
        }


def _validate_receipt(
    value: MmcifArchiveStandardLPeptideTopologyWriteReceipt,
) -> bytes:
    if type(value) is not MmcifArchiveStandardLPeptideTopologyWriteReceipt:
        raise TypeError("an exact archive standard peptide write receipt is required")
    try:
        access_binding = _write_receipt_access_binding(value)
        _validate_factory_artifact_anchor(value, access_binding)
        state = _validate_ingest(value._ingest)
        expected = _canonical_json_bytes(_receipt_document(state))
    except Exception:
        raise MmcifArchiveStandardLPeptideTopologyError(
            "crosswired_write_artifacts", "write receipt is stale or crosswired"
        ) from None
    if (
        value._payload != state.canonical_output
        or value._document_bytes != expected
        or value._access_binding_bytes != access_binding
    ):
        raise MmcifArchiveStandardLPeptideTopologyError(
            "crosswired_write_artifacts", "write receipt is stale or crosswired"
        )
    return expected


def _write_receipt_access_binding(
    value: MmcifArchiveStandardLPeptideTopologyWriteReceipt,
) -> bytes:
    return _canonical_json_bytes(
        {
            "artifact_type": "MmcifArchiveStandardLPeptideTopologyWriteReceipt",
            "self_object_id": id(value),
            "ingest_object_id": id(value._ingest),
            "payload_object_id": id(value._payload),
            "payload_sha256": _sha256_bytes(value._payload),
            "document_object_id": id(value._document_bytes),
            "document_sha256": _sha256_bytes(value._document_bytes),
        }
    )


@dataclass(frozen=True, init=False)
class MmcifArchiveStandardLPeptideTopologyWriteResult:
    _ingest: MmcifArchiveStandardLPeptideTopologyIngestResult = field(repr=False)
    _payload: bytes = field(repr=False)
    _receipt: MmcifArchiveStandardLPeptideTopologyWriteReceipt = field(repr=False)
    _access_binding_bytes: bytes = field(repr=False)

    def __init__(
        self,
        ingest: MmcifArchiveStandardLPeptideTopologyIngestResult,
        payload: bytes,
        receipt: MmcifArchiveStandardLPeptideTopologyWriteReceipt,
        *,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise TypeError(
                "MmcifArchiveStandardLPeptideTopologyWriteResult is factory-only"
            )
        object.__setattr__(self, "_ingest", ingest)
        object.__setattr__(self, "_payload", payload)
        object.__setattr__(self, "_receipt", receipt)
        binding = _write_result_access_binding(self)
        object.__setattr__(self, "_access_binding_bytes", binding)
        _register_factory_artifact_anchor(self, binding)

    @property
    def payload(self) -> bytes:
        _validate_write_result(self)
        return self._payload

    @property
    def receipt(self) -> MmcifArchiveStandardLPeptideTopologyWriteReceipt:
        _validate_write_result(self)
        return self._receipt

    def to_dict(self) -> dict[str, Any]:
        _validate_write_result(self)
        return {
            "payload_sha256": _sha256_bytes(self._payload),
            "receipt": self._receipt.to_dict(),
        }


def _validate_write_result(
    value: MmcifArchiveStandardLPeptideTopologyWriteResult,
) -> _ParsedState:
    if type(value) is not MmcifArchiveStandardLPeptideTopologyWriteResult:
        raise TypeError("an exact archive standard peptide write result is required")
    try:
        access_binding = _write_result_access_binding(value)
        _validate_factory_artifact_anchor(value, access_binding)
        state = _validate_ingest(value._ingest)
        _validate_receipt(value._receipt)
    except Exception:
        raise MmcifArchiveStandardLPeptideTopologyError(
            "crosswired_write_artifacts", "write artifacts are stale or crosswired"
        ) from None
    if (
        value._payload != state.canonical_output
        or value._access_binding_bytes != access_binding
        or value._receipt._ingest is not value._ingest
        or value._receipt._payload is not value._payload
    ):
        raise MmcifArchiveStandardLPeptideTopologyError(
            "crosswired_write_artifacts", "write artifacts are stale or crosswired"
        )
    return state


def _write_result_access_binding(
    value: MmcifArchiveStandardLPeptideTopologyWriteResult,
) -> bytes:
    return _canonical_json_bytes(
        {
            "artifact_type": "MmcifArchiveStandardLPeptideTopologyWriteResult",
            "self_object_id": id(value),
            "ingest_object_id": id(value._ingest),
            "payload_object_id": id(value._payload),
            "payload_sha256": _sha256_bytes(value._payload),
            "receipt_object_id": id(value._receipt),
            "receipt_document_sha256": _sha256_bytes(value._receipt._document_bytes),
        }
    )


def _receipt_document(state: _ParsedState) -> dict[str, Any]:
    return {
        "schema_id": MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_WRITE_RECEIPT_SCHEMA_ID,
        "writer_version": MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_WRITER_VERSION,
        "profile_id": MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_PROFILE_ID,
        "input_source_binding_sha256": _sha256_bytes(state.source_binding_bytes),
        "input_topology_state_sha256": _sha256_bytes(state.topology_state_bytes),
        "input_projection_sha256": _sha256_bytes(state.projection_bytes),
        "output_source_sha256": _sha256_bytes(state.canonical_output),
        "output_byte_count": len(state.canonical_output),
        "rule_manifest_sha256": STANDARD_L_PEPTIDE_RULE_MANIFEST_SHA256,
        **_BOUNDED_TRUE_FIELDS,
        **_authority_false_document(),
    }


def write_mmcif_archive_standard_l_peptide_topology(
    ingest: MmcifArchiveStandardLPeptideTopologyIngestResult,
) -> MmcifArchiveStandardLPeptideTopologyWriteResult:
    state = _validate_ingest(ingest)
    reparsed = _parse_state(state.canonical_output, source_id=state.source_id)
    if (
        reparsed.projection_bytes != state.projection_bytes
        or reparsed.topology_state_bytes != state.topology_state_bytes
        or reparsed.canonical_output != state.canonical_output
    ):
        raise MmcifArchiveStandardLPeptideTopologyError(
            "canonical_output_state_mismatch",
            "canonical output did not preserve the rule projection and topology state",
        )
    receipt = MmcifArchiveStandardLPeptideTopologyWriteReceipt(
        ingest,
        state.canonical_output,
        _receipt_document(state),
        _factory_token=_FACTORY_TOKEN,
    )
    return MmcifArchiveStandardLPeptideTopologyWriteResult(
        ingest,
        state.canonical_output,
        receipt,
        _factory_token=_FACTORY_TOKEN,
    )


emit_mmcif_archive_standard_l_peptide_topology = (
    write_mmcif_archive_standard_l_peptide_topology
)


def serialize_mmcif_archive_standard_l_peptide_topology(
    ingest: MmcifArchiveStandardLPeptideTopologyIngestResult,
) -> bytes:
    return write_mmcif_archive_standard_l_peptide_topology(ingest).payload


def _round_trip_report_document(
    source: MmcifArchiveStandardLPeptideTopologyIngestResult,
    first: MmcifArchiveStandardLPeptideTopologyWriteResult,
    reparsed: MmcifArchiveStandardLPeptideTopologyIngestResult,
    second: MmcifArchiveStandardLPeptideTopologyWriteResult,
) -> dict[str, Any]:
    source_state = _validate_ingest(source)
    reparsed_state = _validate_ingest(reparsed)
    _validate_write_result(first)
    _validate_write_result(second)
    if first._ingest is not source or second._ingest is not reparsed:
        raise MmcifArchiveStandardLPeptideTopologyError(
            "crosswired_round_trip_artifacts",
            "round-trip write artifacts are crosswired",
        )
    if source_state.source_id != reparsed_state.source_id:
        raise MmcifArchiveStandardLPeptideTopologyError(
            "crosswired_round_trip_artifacts",
            "round-trip source identifiers are crosswired",
        )
    source_topology = _topology_document(source_state)["canonical_topology_sha256"]
    reparsed_topology = _topology_document(reparsed_state)["canonical_topology_sha256"]
    input_projection = _sha256_bytes(source_state.projection_bytes)
    reparsed_projection = _sha256_bytes(reparsed_state.projection_bytes)
    input_state = _sha256_bytes(source_state.topology_state_bytes)
    reparsed_state_sha = _sha256_bytes(reparsed_state.topology_state_bytes)
    return {
        "schema_id": MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_ROUND_TRIP_REPORT_SCHEMA_ID,
        "source_id_sha256": _source_id_sha256(source_state.source_id),
        "input_source_binding_sha256": _sha256_bytes(source_state.source_binding_bytes),
        "reparsed_source_binding_sha256": _sha256_bytes(
            reparsed_state.source_binding_bytes
        ),
        "input_write_receipt_sha256": first._receipt.receipt_sha256,
        "reparsed_write_receipt_sha256": second._receipt.receipt_sha256,
        "input_projection_sha256": input_projection,
        "reparsed_projection_sha256": reparsed_projection,
        "input_topology_state_sha256": input_state,
        "reparsed_topology_state_sha256": reparsed_state_sha,
        "topology_state_equal": input_state == reparsed_state_sha,
        "topology_equal": source_topology == reparsed_topology,
        "emitted_source_reparsed_exact": (
            _sha256_bytes(first._payload)
            == json.loads(reparsed_state.source_binding_bytes.decode("ascii"))[
                "full_source_sha256"
            ]
        ),
        "second_emission_byte_stable": first._payload == second._payload,
        "rule_manifest_sha256": STANDARD_L_PEPTIDE_RULE_MANIFEST_SHA256,
        **_BOUNDED_TRUE_FIELDS,
        **_authority_false_document(),
    }


@dataclass(frozen=True, init=False)
class MmcifArchiveStandardLPeptideTopologyRoundTripReport:
    _source: MmcifArchiveStandardLPeptideTopologyIngestResult = field(repr=False)
    _first: MmcifArchiveStandardLPeptideTopologyWriteResult = field(repr=False)
    _reparsed: MmcifArchiveStandardLPeptideTopologyIngestResult = field(repr=False)
    _second: MmcifArchiveStandardLPeptideTopologyWriteResult = field(repr=False)
    _document_bytes: bytes = field(repr=False)
    _access_binding_bytes: bytes = field(repr=False)

    def __init__(
        self,
        source: MmcifArchiveStandardLPeptideTopologyIngestResult,
        first: MmcifArchiveStandardLPeptideTopologyWriteResult,
        reparsed: MmcifArchiveStandardLPeptideTopologyIngestResult,
        second: MmcifArchiveStandardLPeptideTopologyWriteResult,
        *,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise TypeError(
                "MmcifArchiveStandardLPeptideTopologyRoundTripReport is factory-only"
            )
        document = _round_trip_report_document(source, first, reparsed, second)
        if not all(
            document[name]
            for name in (
                "topology_state_equal",
                "topology_equal",
                "emitted_source_reparsed_exact",
                "second_emission_byte_stable",
            )
        ):
            raise MmcifArchiveStandardLPeptideTopologyError(
                "round_trip_mismatch",
                "archive standard peptide topology did not round trip",
            )
        object.__setattr__(self, "_source", source)
        object.__setattr__(self, "_first", first)
        object.__setattr__(self, "_reparsed", reparsed)
        object.__setattr__(self, "_second", second)
        object.__setattr__(self, "_document_bytes", _canonical_json_bytes(document))
        binding = _round_trip_report_access_binding(self)
        object.__setattr__(self, "_access_binding_bytes", binding)
        _register_factory_artifact_anchor(self, binding)

    def _field(self, name: str) -> Any:
        return _validate_round_trip_report(self)[name]

    @property
    def topology_state_equal(self) -> bool:
        return self._field("topology_state_equal") is True

    @property
    def topology_equal(self) -> bool:
        return self._field("topology_equal") is True

    @property
    def emitted_source_reparsed_exact(self) -> bool:
        return self._field("emitted_source_reparsed_exact") is True

    @property
    def second_emission_byte_stable(self) -> bool:
        return self._field("second_emission_byte_stable") is True

    def to_dict(self) -> dict[str, Any]:
        return _validate_round_trip_report(self)


def _validate_round_trip_report(
    value: MmcifArchiveStandardLPeptideTopologyRoundTripReport,
) -> dict[str, Any]:
    if type(value) is not MmcifArchiveStandardLPeptideTopologyRoundTripReport:
        raise TypeError(
            "an exact archive standard peptide round-trip report is required"
        )
    try:
        access_binding = _round_trip_report_access_binding(value)
        _validate_factory_artifact_anchor(value, access_binding)
        document = _round_trip_report_document(
            value._source, value._first, value._reparsed, value._second
        )
    except Exception:
        raise MmcifArchiveStandardLPeptideTopologyError(
            "crosswired_round_trip_artifacts",
            "round-trip report is stale or crosswired",
        ) from None
    if (
        value._document_bytes != _canonical_json_bytes(document)
        or value._access_binding_bytes != access_binding
    ):
        raise MmcifArchiveStandardLPeptideTopologyError(
            "crosswired_round_trip_artifacts",
            "round-trip report is stale or crosswired",
        )
    return document


def _round_trip_report_access_binding(
    value: MmcifArchiveStandardLPeptideTopologyRoundTripReport,
) -> bytes:
    return _canonical_json_bytes(
        {
            "artifact_type": "MmcifArchiveStandardLPeptideTopologyRoundTripReport",
            "self_object_id": id(value),
            "source_object_id": id(value._source),
            "first_object_id": id(value._first),
            "reparsed_object_id": id(value._reparsed),
            "second_object_id": id(value._second),
            "document_object_id": id(value._document_bytes),
            "document_sha256": _sha256_bytes(value._document_bytes),
        }
    )


@dataclass(frozen=True, init=False)
class MmcifArchiveStandardLPeptideTopologyRoundTripResult:
    _source_ingest: MmcifArchiveStandardLPeptideTopologyIngestResult = field(repr=False)
    _write_result: MmcifArchiveStandardLPeptideTopologyWriteResult = field(repr=False)
    _reparsed_ingest: MmcifArchiveStandardLPeptideTopologyIngestResult = field(
        repr=False
    )
    _reemitted_write_result: MmcifArchiveStandardLPeptideTopologyWriteResult = field(
        repr=False
    )
    _report: MmcifArchiveStandardLPeptideTopologyRoundTripReport = field(repr=False)
    _access_binding_bytes: bytes = field(repr=False)

    def __init__(
        self,
        source: MmcifArchiveStandardLPeptideTopologyIngestResult,
        first: MmcifArchiveStandardLPeptideTopologyWriteResult,
        reparsed: MmcifArchiveStandardLPeptideTopologyIngestResult,
        second: MmcifArchiveStandardLPeptideTopologyWriteResult,
        report: MmcifArchiveStandardLPeptideTopologyRoundTripReport,
        *,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise TypeError(
                "MmcifArchiveStandardLPeptideTopologyRoundTripResult is factory-only"
            )
        object.__setattr__(self, "_source_ingest", source)
        object.__setattr__(self, "_write_result", first)
        object.__setattr__(self, "_reparsed_ingest", reparsed)
        object.__setattr__(self, "_reemitted_write_result", second)
        object.__setattr__(self, "_report", report)
        binding = _round_trip_result_access_binding(self)
        object.__setattr__(self, "_access_binding_bytes", binding)
        _register_factory_artifact_anchor(self, binding)
        _validate_round_trip_result(self)

    @property
    def source_ingest(self) -> MmcifArchiveStandardLPeptideTopologyIngestResult:
        _validate_round_trip_result(self)
        return self._source_ingest

    @property
    def write_result(self) -> MmcifArchiveStandardLPeptideTopologyWriteResult:
        _validate_round_trip_result(self)
        return self._write_result

    @property
    def reparsed_ingest(self) -> MmcifArchiveStandardLPeptideTopologyIngestResult:
        _validate_round_trip_result(self)
        return self._reparsed_ingest

    @property
    def reemitted_write_result(
        self,
    ) -> MmcifArchiveStandardLPeptideTopologyWriteResult:
        _validate_round_trip_result(self)
        return self._reemitted_write_result

    @property
    def report(self) -> MmcifArchiveStandardLPeptideTopologyRoundTripReport:
        _validate_round_trip_result(self)
        return self._report

    def to_dict(self) -> dict[str, Any]:
        _validate_round_trip_result(self)
        return {
            "source_ingest": self._source_ingest.to_dict(),
            "write_result": self._write_result.to_dict(),
            "reparsed_ingest": self._reparsed_ingest.to_dict(),
            "reemitted_write_result": self._reemitted_write_result.to_dict(),
            "report": self._report.to_dict(),
        }


def _validate_round_trip_result(
    value: MmcifArchiveStandardLPeptideTopologyRoundTripResult,
) -> None:
    if type(value) is not MmcifArchiveStandardLPeptideTopologyRoundTripResult:
        raise TypeError(
            "an exact archive standard peptide round-trip result is required"
        )
    try:
        access_binding = _round_trip_result_access_binding(value)
        _validate_factory_artifact_anchor(value, access_binding)
        _validate_round_trip_report(value._report)
    except Exception:
        raise MmcifArchiveStandardLPeptideTopologyError(
            "crosswired_round_trip_artifacts",
            "round-trip result is stale or crosswired",
        ) from None
    if (
        value._report._source is not value._source_ingest
        or value._access_binding_bytes != access_binding
        or value._report._first is not value._write_result
        or value._report._reparsed is not value._reparsed_ingest
        or value._report._second is not value._reemitted_write_result
    ):
        raise MmcifArchiveStandardLPeptideTopologyError(
            "crosswired_round_trip_artifacts",
            "round-trip result is stale or crosswired",
        )


def _round_trip_result_access_binding(
    value: MmcifArchiveStandardLPeptideTopologyRoundTripResult,
) -> bytes:
    return _canonical_json_bytes(
        {
            "artifact_type": "MmcifArchiveStandardLPeptideTopologyRoundTripResult",
            "self_object_id": id(value),
            "source_object_id": id(value._source_ingest),
            "first_object_id": id(value._write_result),
            "reparsed_object_id": id(value._reparsed_ingest),
            "second_object_id": id(value._reemitted_write_result),
            "report_object_id": id(value._report),
        }
    )


def round_trip_mmcif_archive_standard_l_peptide_topology_source(
    data: bytes, *, source_id: str = ""
) -> MmcifArchiveStandardLPeptideTopologyRoundTripResult:
    source = parse_mmcif_archive_standard_l_peptide_topology(data, source_id=source_id)
    first = write_mmcif_archive_standard_l_peptide_topology(source)
    reparsed = parse_mmcif_archive_standard_l_peptide_topology(
        first.payload, source_id=source_id
    )
    second = write_mmcif_archive_standard_l_peptide_topology(reparsed)
    report = MmcifArchiveStandardLPeptideTopologyRoundTripReport(
        source,
        first,
        reparsed,
        second,
        _factory_token=_FACTORY_TOKEN,
    )
    return MmcifArchiveStandardLPeptideTopologyRoundTripResult(
        source,
        first,
        reparsed,
        second,
        report,
        _factory_token=_FACTORY_TOKEN,
    )


__all__ = [
    "MAX_MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_ATOMS",
    "MAX_MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_BONDS",
    "MAX_MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_INPUT_BYTES",
    "MAX_MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_OUTPUT_BYTES",
    "MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_ATOM_SITE_HEADERS",
    "MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_ENTITY_HEADERS",
    "MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_ENTITY_POLY_HEADERS",
    "MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_STRUCT_ASYM_HEADERS",
    "MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_ENVELOPE_VERSION",
    "MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_PARSER_NAME",
    "MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_PARSER_PEDIGREE_ID",
    "MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_PARSER_VERSION",
    "MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_PROFILE_ID",
    "MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_PROJECTION_SCHEMA_ID",
    "MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_ROUND_TRIP_REPORT_SCHEMA_ID",
    "MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_SOURCE_BINDING_SCHEMA_ID",
    "MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_STATE_SCHEMA_ID",
    "MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_WRITER_VERSION",
    "MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_WRITE_RECEIPT_SCHEMA_ID",
    "MmcifArchiveStandardLPeptideEntityPolyRow",
    "MmcifArchiveStandardLPeptideTopologyError",
    "MmcifArchiveStandardLPeptideTopologyIngestResult",
    "MmcifArchiveStandardLPeptideTopologyRoundTripReport",
    "MmcifArchiveStandardLPeptideTopologyRoundTripResult",
    "MmcifArchiveStandardLPeptideTopologyWriteReceipt",
    "MmcifArchiveStandardLPeptideTopologyWriteResult",
    "emit_mmcif_archive_standard_l_peptide_topology",
    "mmcif_archive_standard_l_peptide_topology_projection_sha256",
    "mmcif_archive_standard_l_peptide_topology_state_sha256",
    "parse_mmcif_archive_standard_l_peptide_topology",
    "round_trip_mmcif_archive_standard_l_peptide_topology_source",
    "serialize_mmcif_archive_standard_l_peptide_topology",
    "write_mmcif_archive_standard_l_peptide_topology",
]
