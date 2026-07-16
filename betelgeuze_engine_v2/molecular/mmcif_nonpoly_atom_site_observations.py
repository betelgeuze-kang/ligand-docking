"""Bounded nonpoly ``_atom_site`` observation-to-identity binding.

This contract composes the accepted nonpoly identity, component declaration,
and ``_struct_conn`` declaration carriers.  It binds selected source atom rows
to one nonpoly instance and one declared component atom and verifies that every
selected connection endpoint has a source atom observation.

Coordinate, occupancy, B-factor, formal-charge, type-symbol, connection,
chemistry, and topology tokens are preserved but not scientifically
interpreted.  No canonical molecular topology or prepared system is created.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Mapping

from .mmcif_nonpoly_component_declarations import (
    MmcifNonpolyComponentAtomDeclaration,
    MmcifNonpolyComponentDeclarationSnapshot,
    parse_mmcif_nonpoly_component_declarations,
)
from .mmcif_nonpoly_identity import (
    MmcifNonpolyIdentitySnapshot,
    MmcifNonpolyInstanceIdentity,
    parse_mmcif_nonpoly_identity,
)
from .mmcif_semantics import MmcifSemanticValue
from .mmcif_struct_conn_declarations import (
    MmcifStructConnDeclarationSnapshot,
    MmcifStructConnPartnerIdentity,
    parse_mmcif_struct_conn_declarations,
)
from .mmcif_syntax import CifBlock, CifLoop, CifToken, parse_cif_block


NONPOLY_ATOM_SITE_CATEGORY = "_atom_site"

MMCIF_NONPOLY_ATOM_SITE_OBSERVATION_PROJECTION_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_nonpoly_atom_site_observation_projection/1.0.0"
)
MMCIF_NONPOLY_ATOM_SITE_OBSERVATION_SOURCE_BINDING_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_nonpoly_atom_site_observation_source_binding/1.0.0"
)
MMCIF_NONPOLY_ATOM_SITE_OBSERVATION_DOCUMENT_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_nonpoly_atom_site_observation_document/1.0.0"
)
MMCIF_NONPOLY_ATOM_SITE_OBSERVATION_PROFILE_ID = (
    "bounded_mmcif_nonpoly_atom_site_observation_identity_join/1.0.0"
)
MMCIF_NONPOLY_ATOM_SITE_OBSERVATION_PARSER_VERSION = "1.0.0"

MAX_MMCIF_NONPOLY_ATOM_SITE_OBSERVATION_ROWS = 100_000
MAX_MMCIF_NONPOLY_ATOM_SITE_OBSERVATION_TOKEN_CHARS = 256
MAX_MMCIF_NONPOLY_ATOM_SITE_OBSERVATION_INTEGER = (1 << 53) - 1

MMCIF_NONPOLY_ATOM_SITE_HEADERS = (
    "_atom_site.group_pdb",
    "_atom_site.id",
    "_atom_site.type_symbol",
    "_atom_site.label_atom_id",
    "_atom_site.label_alt_id",
    "_atom_site.label_comp_id",
    "_atom_site.label_asym_id",
    "_atom_site.label_entity_id",
    "_atom_site.label_seq_id",
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
    "_atom_site.pdbx_pdb_ins_code",
)

_IDENTITY_JOIN_HEADERS = (
    "_atom_site.group_pdb",
    "_atom_site.id",
    "_atom_site.label_atom_id",
    "_atom_site.label_alt_id",
    "_atom_site.label_comp_id",
    "_atom_site.label_asym_id",
    "_atom_site.label_entity_id",
    "_atom_site.label_seq_id",
    "_atom_site.auth_seq_id",
    "_atom_site.auth_comp_id",
    "_atom_site.auth_asym_id",
    "_atom_site.auth_atom_id",
    "_atom_site.pdbx_pdb_model_num",
    "_atom_site.pdbx_pdb_ins_code",
)
_SUPPORTED_CATEGORIES = frozenset(
    {
        "_entity",
        "_struct_asym",
        "_chem_comp",
        "_chem_comp_atom",
        "_chem_comp_bond",
        "_pdbx_entity_nonpoly",
        "_pdbx_nonpoly_scheme",
        "_struct_conn",
        NONPOLY_ATOM_SITE_CATEGORY,
    }
)
_POSITIVE_INTEGER_RE = re.compile(r"^[1-9][0-9]*$")
_BARE_IDENTITY_RE = re.compile(r"^[!-~]+$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class MmcifNonpolyAtomSiteObservationError(ValueError):
    """Stable fail-closed error that does not echo source identity values."""

    def __init__(self, code: str, detail: str, *, line_number: int | None = None):
        self.code = str(code)
        self.detail = str(detail)
        self.line_number = None if line_number is None else int(line_number)
        suffix = "" if self.line_number is None else f" at line {self.line_number}"
        super().__init__(
            f"mmcif_nonpoly_atom_site_observation:{self.code}{suffix}: {self.detail}"
        )


@dataclass(frozen=True, slots=True, repr=False)
class MmcifNonpolyAtomSiteObservation:
    source_atom_id: int
    model_number: int
    group_pdb: str
    type_symbol: MmcifSemanticValue
    label_atom_id: str
    label_alt_id: MmcifSemanticValue
    label_comp_id: str
    label_asym_id: str
    label_entity_id: str
    label_seq_id: MmcifSemanticValue
    cartn_x: MmcifSemanticValue
    cartn_y: MmcifSemanticValue
    cartn_z: MmcifSemanticValue
    occupancy: MmcifSemanticValue
    b_iso_or_equiv: MmcifSemanticValue
    formal_charge: MmcifSemanticValue
    auth_seq_id: str
    auth_comp_id: str
    auth_asym_id: str
    auth_atom_id: str
    insertion_code: MmcifSemanticValue
    instance_identity_sha256: str
    component_atom_identity_sha256: str
    site_identity_sha256: str
    source_ordinal: int

    def __repr__(self) -> str:
        return (
            "MmcifNonpolyAtomSiteObservation("
            f"source_atom_id={self.source_atom_id}, source_ordinal={self.source_ordinal})"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_atom_id": self.source_atom_id,
            "model_number": self.model_number,
            "group_pdb": self.group_pdb,
            "type_symbol": _semantic_projection(self.type_symbol),
            "label_atom_id": self.label_atom_id,
            "label_alt_id": _semantic_projection(self.label_alt_id),
            "label_comp_id": self.label_comp_id,
            "label_asym_id": self.label_asym_id,
            "label_entity_id": self.label_entity_id,
            "label_seq_id": _semantic_projection(self.label_seq_id),
            "cartn_x": _semantic_projection(self.cartn_x),
            "cartn_y": _semantic_projection(self.cartn_y),
            "cartn_z": _semantic_projection(self.cartn_z),
            "occupancy": _semantic_projection(self.occupancy),
            "b_iso_or_equiv": _semantic_projection(self.b_iso_or_equiv),
            "formal_charge": _semantic_projection(self.formal_charge),
            "auth_seq_id": self.auth_seq_id,
            "auth_comp_id": self.auth_comp_id,
            "auth_asym_id": self.auth_asym_id,
            "auth_atom_id": self.auth_atom_id,
            "insertion_code": _semantic_projection(self.insertion_code),
            "instance_identity_sha256": self.instance_identity_sha256,
            "component_atom_identity_sha256": self.component_atom_identity_sha256,
            "site_identity_sha256": self.site_identity_sha256,
            "source_ordinal": self.source_ordinal,
        }


@dataclass(frozen=True, slots=True, repr=False)
class MmcifStructConnEndpointObservationBinding:
    connection_id: str
    partner_1_site_identity_sha256: str
    partner_2_site_identity_sha256: str
    source_ordinal: int

    def __repr__(self) -> str:
        return (
            "MmcifStructConnEndpointObservationBinding("
            f"source_ordinal={self.source_ordinal})"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "connection_id": self.connection_id,
            "partner_1_site_identity_sha256": self.partner_1_site_identity_sha256,
            "partner_2_site_identity_sha256": self.partner_2_site_identity_sha256,
            "source_ordinal": self.source_ordinal,
        }


@dataclass(frozen=True, slots=True)
class MmcifNonpolyAtomSiteCategoryBinding:
    category: str
    headers: tuple[str, ...]
    identity_join_headers: tuple[str, ...]
    preserved_uninterpreted_headers: tuple[str, ...]
    row_count: int
    selected_row_count: int
    source_ordinal: int
    row_sha256: tuple[str, ...]
    selected_row_sha256: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "representation": "loop",
            "headers": list(self.headers),
            "identity_join_headers": list(self.identity_join_headers),
            "preserved_uninterpreted_headers": list(
                self.preserved_uninterpreted_headers
            ),
            "row_count": self.row_count,
            "selected_row_count": self.selected_row_count,
            "source_ordinal": self.source_ordinal,
            "row_sha256": list(self.row_sha256),
            "selected_row_sha256": list(self.selected_row_sha256),
        }


@dataclass(frozen=True, slots=True, repr=False)
class MmcifNonpolyAtomSiteObservationSnapshot:
    source_sha256: str
    block_name: str
    identity_snapshot_sha256: str
    identity_projection_sha256: str
    identity_source_binding_sha256: str
    component_snapshot_sha256: str
    component_projection_sha256: str
    component_source_binding_sha256: str
    struct_conn_snapshot_sha256: str
    struct_conn_projection_sha256: str
    struct_conn_source_binding_sha256: str
    observations: tuple[MmcifNonpolyAtomSiteObservation, ...]
    endpoint_bindings: tuple[MmcifStructConnEndpointObservationBinding, ...]
    source_category_order: tuple[str, ...]
    category_binding: MmcifNonpolyAtomSiteCategoryBinding
    uninterpreted_categories: tuple[str, ...]

    def __repr__(self) -> str:
        return (
            "MmcifNonpolyAtomSiteObservationSnapshot("
            f"observation_count={len(self.observations)}, "
            f"endpoint_binding_count={len(self.endpoint_bindings)})"
        )

    @property
    def observation_projection_sha256(self) -> str:
        return _sha256(mmcif_nonpoly_atom_site_observation_projection(self))

    @property
    def source_binding_sha256(self) -> str:
        return _sha256(mmcif_nonpoly_atom_site_observation_source_binding(self))

    @property
    def snapshot_sha256(self) -> str:
        return _sha256(
            {
                "schema_id": MMCIF_NONPOLY_ATOM_SITE_OBSERVATION_DOCUMENT_SCHEMA_ID,
                "observation_projection_sha256": self.observation_projection_sha256,
                "source_binding_sha256": self.source_binding_sha256,
                "claim_policy": _claim_policy(),
            }
        )

    def to_dict(self) -> dict[str, Any]:
        instance_counts: dict[str, int] = {}
        for row in self.observations:
            instance_counts[row.instance_identity_sha256] = (
                instance_counts.get(row.instance_identity_sha256, 0) + 1
            )
        return {
            "schema_id": MMCIF_NONPOLY_ATOM_SITE_OBSERVATION_DOCUMENT_SCHEMA_ID,
            "profile_id": MMCIF_NONPOLY_ATOM_SITE_OBSERVATION_PROFILE_ID,
            "parser_version": MMCIF_NONPOLY_ATOM_SITE_OBSERVATION_PARSER_VERSION,
            "source_sha256": self.source_sha256,
            "block_name": self.block_name,
            "identity_snapshot_sha256": self.identity_snapshot_sha256,
            "component_snapshot_sha256": self.component_snapshot_sha256,
            "struct_conn_snapshot_sha256": self.struct_conn_snapshot_sha256,
            "observation_count": len(self.observations),
            "observed_instance_count": len(instance_counts),
            "instance_observation_counts": instance_counts,
            "endpoint_binding_count": len(self.endpoint_bindings),
            "uninterpreted_categories": list(self.uninterpreted_categories),
            "observation_projection_sha256": self.observation_projection_sha256,
            "source_binding_sha256": self.source_binding_sha256,
            "snapshot_sha256": self.snapshot_sha256,
            **_claim_policy(),
        }


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _claim_policy() -> dict[str, bool]:
    return {
        "source_atom_site_observations_preserved": True,
        "atom_site_identity_joined": True,
        "nonpoly_instance_identity_references_verified": True,
        "component_atom_identity_references_verified": True,
        "struct_conn_endpoint_observation_references_verified": True,
        "selected_instance_component_atom_coverage_verified": True,
        "single_model_identity_verified": True,
        "source_row_order_preserved": True,
        "source_category_headers_bound": True,
        "source_authenticated": False,
        "coordinate_values_interpreted": False,
        "coordinate_observation_scientifically_assessed": False,
        "occupancy_values_interpreted": False,
        "b_factor_interpreted": False,
        "formal_charge_interpreted": False,
        "type_symbol_interpreted": False,
        "auth_label_semantic_equivalence_interpreted": False,
        "altloc_population_interpreted": False,
        "missingness_inferred": False,
        "connection_type_interpreted": False,
        "symmetry_interpreted": False,
        "bond_order_interpreted": False,
        "covalence_interpreted": False,
        "coordination_interpreted": False,
        "topology_interpreted": False,
        "chemistry_interpreted": False,
        "preparation_ready": False,
        "parameterability_assessed": False,
        "physics_supported": False,
        "runtime_eligible": False,
        "scientifically_validated": False,
        "benchmark_validated": False,
        "product_qualified": False,
        "customer_execution_enabled": False,
        "claim_safe": False,
    }


def _semantic(token: CifToken, *, field: str) -> MmcifSemanticValue:
    if token.multiline or len(token.value) > MAX_MMCIF_NONPOLY_ATOM_SITE_OBSERVATION_TOKEN_CHARS:
        raise MmcifNonpolyAtomSiteObservationError(
            "source_token_out_of_bounds",
            f"{field} exceeds the bounded source token domain",
            line_number=token.line_number,
        )
    state = (
        "not_applicable"
        if not token.quoted and token.value == "."
        else "unknown"
        if not token.quoted and token.value == "?"
        else "known"
    )
    try:
        return MmcifSemanticValue(
            state=state,
            value=token.value,
            quoted=bool(token.quoted),
            line_number=int(token.line_number),
            column_number=int(token.column_number),
        )
    except (TypeError, ValueError) as exc:
        raise MmcifNonpolyAtomSiteObservationError(
            "source_token_out_of_bounds",
            f"{field} exceeds the bounded semantic value domain",
            line_number=token.line_number,
        ) from exc


def _semantic_projection(value: MmcifSemanticValue) -> dict[str, Any]:
    return {"state": value.state, "value": value.value, "quoted": value.quoted}


def _semantic_key(value: MmcifSemanticValue) -> tuple[str, str, bool]:
    return value.state, value.value, value.quoted


def _known_identity(token: CifToken, *, field: str) -> str:
    value = _semantic(token, field=field)
    if value.state != "known":
        raise MmcifNonpolyAtomSiteObservationError(
            "required_identity_marker",
            f"{field} must be a known source identity",
            line_number=token.line_number,
        )
    if value.quoted or _BARE_IDENTITY_RE.fullmatch(value.value) is None:
        raise MmcifNonpolyAtomSiteObservationError(
            "invalid_identity_token",
            f"{field} must be a bounded bare printable token",
            line_number=token.line_number,
        )
    return value.value


def _positive_integer(token: CifToken, *, field: str) -> int:
    if token.quoted or token.multiline or _POSITIVE_INTEGER_RE.fullmatch(token.value) is None:
        raise MmcifNonpolyAtomSiteObservationError(
            "invalid_positive_integer",
            f"{field} must be a canonical positive integer",
            line_number=token.line_number,
        )
    value = int(token.value)
    if value > MAX_MMCIF_NONPOLY_ATOM_SITE_OBSERVATION_INTEGER:
        raise MmcifNonpolyAtomSiteObservationError(
            "positive_integer_out_of_bounds",
            f"{field} exceeds the bounded integer domain",
            line_number=token.line_number,
        )
    return value


def _blank_marker(token: CifToken, *, field: str) -> MmcifSemanticValue:
    value = _semantic(token, field=field)
    if value.state == "known":
        raise MmcifNonpolyAtomSiteObservationError(
            "nonblank_atom_site_marker_not_supported",
            f"{field} must be an explicit dot or question marker in this profile",
            line_number=token.line_number,
        )
    return value


def _known_observation(token: CifToken, *, field: str) -> MmcifSemanticValue:
    value = _semantic(token, field=field)
    if value.state != "known":
        raise MmcifNonpolyAtomSiteObservationError(
            "coordinate_token_unavailable",
            f"{field} must contain one source-reported coordinate token",
            line_number=token.line_number,
        )
    return value


def _row_sha(loop: CifLoop, row: tuple[CifToken, ...]) -> str:
    return _sha256(
        [
            {
                "tag": tag,
                "value": token.value,
                "quoted": bool(token.quoted),
                "multiline": bool(token.multiline),
            }
            for tag, token in zip(loop.tags, row, strict=True)
        ]
    )


def _atom_site_loop(block: CifBlock) -> tuple[CifLoop, dict[str, int]]:
    scalar = tuple(
        tag
        for tag in block.scalar_values
        if tag.startswith(f"{NONPOLY_ATOM_SITE_CATEGORY}.")
    )
    if scalar:
        token = block.scalar_values[scalar[0]]
        raise MmcifNonpolyAtomSiteObservationError(
            "atom_site_must_be_loop",
            "_atom_site must use one category-local loop",
            line_number=token.line_number,
        )
    loops = [
        loop for loop in block.loops if NONPOLY_ATOM_SITE_CATEGORY in loop.categories
    ]
    if not loops:
        raise MmcifNonpolyAtomSiteObservationError(
            "atom_site_missing",
            "one bounded _atom_site loop is required",
        )
    if len(loops) != 1:
        raise MmcifNonpolyAtomSiteObservationError(
            "multiple_atom_site_loops",
            "_atom_site must occur in exactly one loop",
            line_number=loops[1].line_number,
        )
    loop = loops[0]
    if loop.categories != (NONPOLY_ATOM_SITE_CATEGORY,):
        raise MmcifNonpolyAtomSiteObservationError(
            "mixed_atom_site_loop",
            "cross-category atom-site loops are outside this bounded profile",
            line_number=loop.line_number,
        )
    if not loop.rows:
        raise MmcifNonpolyAtomSiteObservationError(
            "atom_site_empty",
            "_atom_site must contain at least one source row",
            line_number=loop.line_number,
        )
    if len(loop.rows) > MAX_MMCIF_NONPOLY_ATOM_SITE_OBSERVATION_ROWS:
        raise MmcifNonpolyAtomSiteObservationError(
            "too_many_atom_site_rows",
            "_atom_site exceeds the bounded row count",
            line_number=loop.line_number,
        )
    if len(loop.tags) != len(MMCIF_NONPOLY_ATOM_SITE_HEADERS) or set(loop.tags) != set(
        MMCIF_NONPOLY_ATOM_SITE_HEADERS
    ):
        raise MmcifNonpolyAtomSiteObservationError(
            "unsupported_atom_site_headers",
            "_atom_site must use the exact bounded source header set",
            line_number=loop.line_number,
        )
    for row in loop.rows:
        for token in row:
            if token.multiline or len(token.value) > MAX_MMCIF_NONPOLY_ATOM_SITE_OBSERVATION_TOKEN_CHARS:
                raise MmcifNonpolyAtomSiteObservationError(
                    "source_token_out_of_bounds",
                    "_atom_site contains a source token outside the bounded domain",
                    line_number=token.line_number,
                )
    return loop, {tag: position for position, tag in enumerate(loop.tags)}


def _join_instance(
    *,
    instances: tuple[MmcifNonpolyInstanceIdentity, ...],
    label_asym_id: str,
    label_comp_id: str,
    auth_asym_id: str,
    auth_comp_id: str,
    auth_seq_id: str,
    insertion_code: MmcifSemanticValue,
    line_number: int,
) -> MmcifNonpolyInstanceIdentity:
    matches = tuple(
        row
        for row in instances
        if row.asym_id == label_asym_id
        and row.mon_id == label_comp_id
        and row.pdb_strand_id == auth_asym_id
        and row.auth_mon_id == auth_comp_id
        and row.auth_seq_num == auth_seq_id
        and _semantic_key(row.pdb_ins_code) == _semantic_key(insertion_code)
    )
    if len(matches) != 1:
        raise MmcifNonpolyAtomSiteObservationError(
            "atom_site_instance_identity_join_failed",
            "each selected atom row must resolve to exactly one nonpoly source instance",
            line_number=line_number,
        )
    return matches[0]


def _component_atom_identity(
    atom: MmcifNonpolyComponentAtomDeclaration,
) -> str:
    return _sha256(
        {
            "comp_id": atom.comp_id,
            "atom_id": atom.atom_id,
            "ordinal": atom.ordinal,
        }
    )


def _site_identity(
    *,
    model_number: int,
    instance_identity_sha256: str,
    label_atom_id: str,
    label_alt_id: MmcifSemanticValue,
    auth_atom_id: str,
) -> str:
    return _sha256(
        {
            "model_number": model_number,
            "instance_identity_sha256": instance_identity_sha256,
            "label_atom_id": label_atom_id,
            "label_alt_id": _semantic_projection(label_alt_id),
            "auth_atom_id": auth_atom_id,
        }
    )


def _parse_observations(
    parsed: tuple[CifLoop, dict[str, int]],
    *,
    identity: MmcifNonpolyIdentitySnapshot,
    components: MmcifNonpolyComponentDeclarationSnapshot,
) -> tuple[
    tuple[MmcifNonpolyAtomSiteObservation, ...],
    tuple[str, ...],
]:
    loop, index = parsed
    selected_asym = {row.asym_id for row in identity.instances}
    component_atoms = {
        (row.comp_id, row.atom_id): row for row in components.atom_declarations
    }
    observations: list[MmcifNonpolyAtomSiteObservation] = []
    selected_hashes: list[str] = []
    source_ids: set[int] = set()
    logical_keys: set[tuple[str, str]] = set()

    for source_ordinal, row in enumerate(loop.rows):
        id_token = row[index["_atom_site.id"]]
        source_atom_id = _positive_integer(id_token, field="_atom_site.id")
        if source_atom_id in source_ids:
            raise MmcifNonpolyAtomSiteObservationError(
                "duplicate_source_atom_id",
                "_atom_site source identifiers must be unique",
                line_number=id_token.line_number,
            )
        source_ids.add(source_atom_id)

        asym_token = row[index["_atom_site.label_asym_id"]]
        label_asym_id = _known_identity(asym_token, field="_atom_site.label_asym_id")
        if label_asym_id not in selected_asym:
            continue

        group_pdb = _known_identity(
            row[index["_atom_site.group_pdb"]], field="_atom_site.group_pdb"
        )
        if group_pdb != "HETATM":
            raise MmcifNonpolyAtomSiteObservationError(
                "selected_nonpoly_record_kind_mismatch",
                "selected nonpoly atom rows must use HETATM",
                line_number=asym_token.line_number,
            )
        model_number = _positive_integer(
            row[index["_atom_site.pdbx_pdb_model_num"]],
            field="_atom_site.pdbx_pdb_model_num",
        )
        if model_number != 1:
            raise MmcifNonpolyAtomSiteObservationError(
                "selected_model_not_supported",
                "selected nonpoly atom rows must use model number 1",
                line_number=asym_token.line_number,
            )
        label_comp_id = _known_identity(
            row[index["_atom_site.label_comp_id"]],
            field="_atom_site.label_comp_id",
        )
        label_atom_id = _known_identity(
            row[index["_atom_site.label_atom_id"]],
            field="_atom_site.label_atom_id",
        )
        component_atom = component_atoms.get((label_comp_id, label_atom_id))
        if component_atom is None:
            raise MmcifNonpolyAtomSiteObservationError(
                "atom_site_component_atom_identity_missing",
                "selected atom rows must reference one declared component atom",
                line_number=asym_token.line_number,
            )
        label_entity_id = _known_identity(
            row[index["_atom_site.label_entity_id"]],
            field="_atom_site.label_entity_id",
        )
        label_seq_id = _blank_marker(
            row[index["_atom_site.label_seq_id"]],
            field="_atom_site.label_seq_id",
        )
        label_alt_id = _blank_marker(
            row[index["_atom_site.label_alt_id"]],
            field="_atom_site.label_alt_id",
        )
        auth_seq_id = _known_identity(
            row[index["_atom_site.auth_seq_id"]],
            field="_atom_site.auth_seq_id",
        )
        auth_comp_id = _known_identity(
            row[index["_atom_site.auth_comp_id"]],
            field="_atom_site.auth_comp_id",
        )
        auth_asym_id = _known_identity(
            row[index["_atom_site.auth_asym_id"]],
            field="_atom_site.auth_asym_id",
        )
        auth_atom_id = _known_identity(
            row[index["_atom_site.auth_atom_id"]],
            field="_atom_site.auth_atom_id",
        )
        insertion_code = _semantic(
            row[index["_atom_site.pdbx_pdb_ins_code"]],
            field="_atom_site.pdbx_pdb_ins_code",
        )
        instance = _join_instance(
            instances=identity.instances,
            label_asym_id=label_asym_id,
            label_comp_id=label_comp_id,
            auth_asym_id=auth_asym_id,
            auth_comp_id=auth_comp_id,
            auth_seq_id=auth_seq_id,
            insertion_code=insertion_code,
            line_number=asym_token.line_number,
        )
        if label_entity_id != instance.entity_id:
            raise MmcifNonpolyAtomSiteObservationError(
                "atom_site_label_entity_join_failed",
                "selected atom label entity must match the nonpoly instance carrier",
                line_number=asym_token.line_number,
            )
        logical_key = (instance.instance_identity_sha256, label_atom_id)
        if logical_key in logical_keys:
            raise MmcifNonpolyAtomSiteObservationError(
                "duplicate_atom_site_observation",
                "selected instance/component atom observations must be unique",
                line_number=asym_token.line_number,
            )
        logical_keys.add(logical_key)
        site_identity_sha256 = _site_identity(
            model_number=model_number,
            instance_identity_sha256=instance.instance_identity_sha256,
            label_atom_id=label_atom_id,
            label_alt_id=label_alt_id,
            auth_atom_id=auth_atom_id,
        )
        observations.append(
            MmcifNonpolyAtomSiteObservation(
                source_atom_id=source_atom_id,
                model_number=model_number,
                group_pdb=group_pdb,
                type_symbol=_semantic(
                    row[index["_atom_site.type_symbol"]],
                    field="_atom_site.type_symbol",
                ),
                label_atom_id=label_atom_id,
                label_alt_id=label_alt_id,
                label_comp_id=label_comp_id,
                label_asym_id=label_asym_id,
                label_entity_id=label_entity_id,
                label_seq_id=label_seq_id,
                cartn_x=_known_observation(
                    row[index["_atom_site.cartn_x"]], field="_atom_site.cartn_x"
                ),
                cartn_y=_known_observation(
                    row[index["_atom_site.cartn_y"]], field="_atom_site.cartn_y"
                ),
                cartn_z=_known_observation(
                    row[index["_atom_site.cartn_z"]], field="_atom_site.cartn_z"
                ),
                occupancy=_semantic(
                    row[index["_atom_site.occupancy"]],
                    field="_atom_site.occupancy",
                ),
                b_iso_or_equiv=_semantic(
                    row[index["_atom_site.b_iso_or_equiv"]],
                    field="_atom_site.b_iso_or_equiv",
                ),
                formal_charge=_semantic(
                    row[index["_atom_site.pdbx_formal_charge"]],
                    field="_atom_site.pdbx_formal_charge",
                ),
                auth_seq_id=auth_seq_id,
                auth_comp_id=auth_comp_id,
                auth_asym_id=auth_asym_id,
                auth_atom_id=auth_atom_id,
                insertion_code=insertion_code,
                instance_identity_sha256=instance.instance_identity_sha256,
                component_atom_identity_sha256=_component_atom_identity(component_atom),
                site_identity_sha256=site_identity_sha256,
                source_ordinal=source_ordinal,
            )
        )
        selected_hashes.append(_row_sha(loop, row))

    expected = {
        (instance.instance_identity_sha256, atom.atom_id)
        for instance in identity.instances
        for atom in components.atom_declarations
        if atom.comp_id == instance.mon_id
    }
    if logical_keys != expected:
        raise MmcifNonpolyAtomSiteObservationError(
            "selected_instance_atom_coverage_mismatch",
            "selected atom rows must exactly cover every declared atom of every nonpoly instance",
        )
    return tuple(observations), tuple(selected_hashes)


def _bind_endpoint(
    partner: MmcifStructConnPartnerIdentity,
    observations: Mapping[tuple[str, str], MmcifNonpolyAtomSiteObservation],
    *,
    line_number: int | None = None,
) -> MmcifNonpolyAtomSiteObservation:
    observation = observations.get(
        (partner.instance_identity_sha256, partner.label_atom_id)
    )
    if observation is None:
        raise MmcifNonpolyAtomSiteObservationError(
            "struct_conn_endpoint_observation_missing",
            "each selected connection endpoint must have one atom-site observation",
            line_number=line_number,
        )
    return observation


def _endpoint_bindings(
    struct_conn: MmcifStructConnDeclarationSnapshot,
    observations: tuple[MmcifNonpolyAtomSiteObservation, ...],
) -> tuple[MmcifStructConnEndpointObservationBinding, ...]:
    by_identity = {
        (row.instance_identity_sha256, row.label_atom_id): row for row in observations
    }
    return tuple(
        MmcifStructConnEndpointObservationBinding(
            connection_id=row.connection_id,
            partner_1_site_identity_sha256=_bind_endpoint(
                row.partner_1, by_identity
            ).site_identity_sha256,
            partner_2_site_identity_sha256=_bind_endpoint(
                row.partner_2, by_identity
            ).site_identity_sha256,
            source_ordinal=row.source_ordinal,
        )
        for row in struct_conn.declarations
    )


def parse_mmcif_nonpoly_atom_site_observations(
    text: str,
) -> MmcifNonpolyAtomSiteObservationSnapshot:
    """Parse and bind selected nonpoly atom-site source observations."""

    if type(text) is not str:
        raise TypeError("mmCIF nonpoly atom-site observation input must be a string")
    identity = parse_mmcif_nonpoly_identity(text)
    components = parse_mmcif_nonpoly_component_declarations(text)
    struct_conn = parse_mmcif_struct_conn_declarations(text)
    block = parse_cif_block(text)
    parsed = _atom_site_loop(block)
    loop, _index = parsed
    observations, selected_hashes = _parse_observations(
        parsed,
        identity=identity,
        components=components,
    )
    endpoint_bindings = _endpoint_bindings(struct_conn, observations)
    identity_headers = frozenset(_IDENTITY_JOIN_HEADERS)
    category_binding = MmcifNonpolyAtomSiteCategoryBinding(
        category=NONPOLY_ATOM_SITE_CATEGORY,
        headers=tuple(loop.tags),
        identity_join_headers=tuple(
            tag for tag in loop.tags if tag in identity_headers
        ),
        preserved_uninterpreted_headers=tuple(
            tag for tag in loop.tags if tag not in identity_headers
        ),
        row_count=len(loop.rows),
        selected_row_count=len(observations),
        source_ordinal=block.category_order.index(NONPOLY_ATOM_SITE_CATEGORY),
        row_sha256=tuple(_row_sha(loop, row) for row in loop.rows),
        selected_row_sha256=selected_hashes,
    )
    return MmcifNonpolyAtomSiteObservationSnapshot(
        source_sha256=hashlib.sha256(text.encode("ascii")).hexdigest(),
        block_name=block.name,
        identity_snapshot_sha256=identity.snapshot_sha256,
        identity_projection_sha256=identity.identity_projection_sha256,
        identity_source_binding_sha256=identity.source_binding_sha256,
        component_snapshot_sha256=components.snapshot_sha256,
        component_projection_sha256=components.declaration_projection_sha256,
        component_source_binding_sha256=components.source_binding_sha256,
        struct_conn_snapshot_sha256=struct_conn.snapshot_sha256,
        struct_conn_projection_sha256=struct_conn.declaration_projection_sha256,
        struct_conn_source_binding_sha256=struct_conn.source_binding_sha256,
        observations=observations,
        endpoint_bindings=endpoint_bindings,
        source_category_order=block.category_order,
        category_binding=category_binding,
        uninterpreted_categories=tuple(
            category
            for category in block.category_order
            if category not in _SUPPORTED_CATEGORIES
        ),
    )


def mmcif_nonpoly_atom_site_observation_projection(
    snapshot: MmcifNonpolyAtomSiteObservationSnapshot,
) -> dict[str, Any]:
    return {
        "schema_id": MMCIF_NONPOLY_ATOM_SITE_OBSERVATION_PROJECTION_SCHEMA_ID,
        "profile_id": MMCIF_NONPOLY_ATOM_SITE_OBSERVATION_PROFILE_ID,
        "parser_version": MMCIF_NONPOLY_ATOM_SITE_OBSERVATION_PARSER_VERSION,
        "identity_projection_sha256": snapshot.identity_projection_sha256,
        "component_projection_sha256": snapshot.component_projection_sha256,
        "struct_conn_projection_sha256": snapshot.struct_conn_projection_sha256,
        "observations": [row.to_dict() for row in snapshot.observations],
        "endpoint_bindings": [row.to_dict() for row in snapshot.endpoint_bindings],
        "row_order": "selected_source_atom_site_order",
        **_claim_policy(),
    }


def mmcif_nonpoly_atom_site_observation_source_binding(
    snapshot: MmcifNonpolyAtomSiteObservationSnapshot,
) -> dict[str, Any]:
    return {
        "schema_id": MMCIF_NONPOLY_ATOM_SITE_OBSERVATION_SOURCE_BINDING_SCHEMA_ID,
        "source_sha256": snapshot.source_sha256,
        "block_name": snapshot.block_name,
        "identity_snapshot_sha256": snapshot.identity_snapshot_sha256,
        "identity_source_binding_sha256": snapshot.identity_source_binding_sha256,
        "component_snapshot_sha256": snapshot.component_snapshot_sha256,
        "component_source_binding_sha256": snapshot.component_source_binding_sha256,
        "struct_conn_snapshot_sha256": snapshot.struct_conn_snapshot_sha256,
        "struct_conn_source_binding_sha256": snapshot.struct_conn_source_binding_sha256,
        "source_category_order": list(snapshot.source_category_order),
        "category_binding": snapshot.category_binding.to_dict(),
        "uninterpreted_categories": list(snapshot.uninterpreted_categories),
    }


def mmcif_nonpoly_atom_site_observation_document(
    snapshot: MmcifNonpolyAtomSiteObservationSnapshot,
) -> dict[str, Any]:
    projection = mmcif_nonpoly_atom_site_observation_projection(snapshot)
    binding = mmcif_nonpoly_atom_site_observation_source_binding(snapshot)
    return {
        "schema_id": MMCIF_NONPOLY_ATOM_SITE_OBSERVATION_DOCUMENT_SCHEMA_ID,
        "profile_id": MMCIF_NONPOLY_ATOM_SITE_OBSERVATION_PROFILE_ID,
        "parser_version": MMCIF_NONPOLY_ATOM_SITE_OBSERVATION_PARSER_VERSION,
        "observation_projection": projection,
        "source_binding": binding,
        "observation_projection_sha256": _sha256(projection),
        "source_binding_sha256": _sha256(binding),
        **snapshot.to_dict(),
    }


def require_mmcif_nonpoly_atom_site_observation_document(
    payload: object,
) -> Mapping[str, object]:
    if not isinstance(payload, Mapping):
        raise ValueError("nonpoly atom-site observation document must be a mapping")
    document = dict(payload)
    if document.get("schema_id") != MMCIF_NONPOLY_ATOM_SITE_OBSERVATION_DOCUMENT_SCHEMA_ID:
        raise ValueError("nonpoly atom-site observation document schema mismatch")
    if document.get("profile_id") != MMCIF_NONPOLY_ATOM_SITE_OBSERVATION_PROFILE_ID:
        raise ValueError("nonpoly atom-site observation profile mismatch")
    if document.get("parser_version") != MMCIF_NONPOLY_ATOM_SITE_OBSERVATION_PARSER_VERSION:
        raise ValueError("nonpoly atom-site observation parser version mismatch")
    projection = document.get("observation_projection")
    binding = document.get("source_binding")
    if not isinstance(projection, Mapping) or not isinstance(binding, Mapping):
        raise ValueError("nonpoly atom-site observation sections must be mappings")
    if projection.get("schema_id") != MMCIF_NONPOLY_ATOM_SITE_OBSERVATION_PROJECTION_SCHEMA_ID:
        raise ValueError("nonpoly atom-site observation projection schema mismatch")
    if binding.get("schema_id") != MMCIF_NONPOLY_ATOM_SITE_OBSERVATION_SOURCE_BINDING_SCHEMA_ID:
        raise ValueError("nonpoly atom-site observation source binding schema mismatch")

    projection_digest = _sha256(dict(projection))
    binding_digest = _sha256(dict(binding))
    if document.get("observation_projection_sha256") != projection_digest:
        raise ValueError("nonpoly atom-site observation projection digest mismatch")
    if document.get("source_binding_sha256") != binding_digest:
        raise ValueError("nonpoly atom-site observation source binding digest mismatch")
    expected_snapshot = _sha256(
        {
            "schema_id": MMCIF_NONPOLY_ATOM_SITE_OBSERVATION_DOCUMENT_SCHEMA_ID,
            "observation_projection_sha256": projection_digest,
            "source_binding_sha256": binding_digest,
            "claim_policy": _claim_policy(),
        }
    )
    if document.get("snapshot_sha256") != expected_snapshot:
        raise ValueError("nonpoly atom-site observation snapshot digest mismatch")
    for key, expected in _claim_policy().items():
        if document.get(key) is not expected or projection.get(key) is not expected:
            raise ValueError("nonpoly atom-site observation claim policy mismatch")

    observations = projection.get("observations")
    endpoint_bindings = projection.get("endpoint_bindings")
    if not isinstance(observations, list) or not observations:
        raise ValueError("nonpoly atom-site observations must be a non-empty list")
    if not isinstance(endpoint_bindings, list) or not endpoint_bindings:
        raise ValueError("nonpoly atom-site endpoint bindings must be a non-empty list")
    if document.get("observation_count") != len(observations):
        raise ValueError("nonpoly atom-site observation count mismatch")
    if document.get("endpoint_binding_count") != len(endpoint_bindings):
        raise ValueError("nonpoly atom-site endpoint binding count mismatch")

    source_sha = binding.get("source_sha256")
    if _SHA256_RE.fullmatch(str(source_sha or "")) is None:
        raise ValueError("nonpoly atom-site observation source digest invalid")
    if document.get("source_sha256") != source_sha:
        raise ValueError("nonpoly atom-site observation source digest mismatch")
    for value, label in (
        (projection.get("identity_projection_sha256"), "identity projection"),
        (projection.get("component_projection_sha256"), "component projection"),
        (projection.get("struct_conn_projection_sha256"), "struct_conn projection"),
        (binding.get("identity_snapshot_sha256"), "identity snapshot"),
        (binding.get("identity_source_binding_sha256"), "identity source binding"),
        (binding.get("component_snapshot_sha256"), "component snapshot"),
        (binding.get("component_source_binding_sha256"), "component source binding"),
        (binding.get("struct_conn_snapshot_sha256"), "struct_conn snapshot"),
        (binding.get("struct_conn_source_binding_sha256"), "struct_conn source binding"),
    ):
        if _SHA256_RE.fullmatch(str(value or "")) is None:
            raise ValueError(f"nonpoly atom-site observation {label} digest invalid")
    return payload


def mmcif_nonpoly_atom_site_observation_json_bytes(
    snapshot: MmcifNonpolyAtomSiteObservationSnapshot,
) -> bytes:
    return _canonical_bytes(mmcif_nonpoly_atom_site_observation_document(snapshot))


def write_mmcif_nonpoly_atom_site_observation_json(
    path: str | Path,
    snapshot: MmcifNonpolyAtomSiteObservationSnapshot,
) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = mmcif_nonpoly_atom_site_observation_json_bytes(snapshot) + b"\n"
    file_fd, temporary = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=destination.parent,
    )
    temporary_path = Path(temporary)
    try:
        os.fchmod(file_fd, 0o600)
        with os.fdopen(file_fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        file_fd = -1
        os.replace(temporary_path, destination)
        directory_fd = os.open(
            destination.parent,
            os.O_RDONLY
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_DIRECTORY", 0),
        )
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except Exception:
        if file_fd >= 0:
            try:
                os.close(file_fd)
            except OSError:
                pass
        try:
            temporary_path.unlink()
        except OSError:
            pass
        raise
    return destination


__all__ = [
    "MAX_MMCIF_NONPOLY_ATOM_SITE_OBSERVATION_INTEGER",
    "MAX_MMCIF_NONPOLY_ATOM_SITE_OBSERVATION_ROWS",
    "MAX_MMCIF_NONPOLY_ATOM_SITE_OBSERVATION_TOKEN_CHARS",
    "MMCIF_NONPOLY_ATOM_SITE_HEADERS",
    "MMCIF_NONPOLY_ATOM_SITE_OBSERVATION_DOCUMENT_SCHEMA_ID",
    "MMCIF_NONPOLY_ATOM_SITE_OBSERVATION_PARSER_VERSION",
    "MMCIF_NONPOLY_ATOM_SITE_OBSERVATION_PROFILE_ID",
    "MMCIF_NONPOLY_ATOM_SITE_OBSERVATION_PROJECTION_SCHEMA_ID",
    "MMCIF_NONPOLY_ATOM_SITE_OBSERVATION_SOURCE_BINDING_SCHEMA_ID",
    "MmcifNonpolyAtomSiteCategoryBinding",
    "MmcifNonpolyAtomSiteObservation",
    "MmcifNonpolyAtomSiteObservationError",
    "MmcifNonpolyAtomSiteObservationSnapshot",
    "MmcifStructConnEndpointObservationBinding",
    "NONPOLY_ATOM_SITE_CATEGORY",
    "mmcif_nonpoly_atom_site_observation_document",
    "mmcif_nonpoly_atom_site_observation_json_bytes",
    "mmcif_nonpoly_atom_site_observation_projection",
    "mmcif_nonpoly_atom_site_observation_source_binding",
    "parse_mmcif_nonpoly_atom_site_observations",
    "require_mmcif_nonpoly_atom_site_observation_document",
    "write_mmcif_nonpoly_atom_site_observation_json",
]
