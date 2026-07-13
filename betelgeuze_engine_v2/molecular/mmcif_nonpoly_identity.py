"""Opt-in mmCIF envelope for source-reported non-polymer identity.

The base mmCIF parser and writer deliberately reject chemical-context
categories that they cannot preserve losslessly.  This module leaves those
defaults unchanged.  It admits exactly two additional identity-only loops,
projects them as opaque source nomenclature, and delegates molecular state to
the existing common-core21 parser/writer contract.

Nothing in this envelope interprets component chemistry, roles, bonds,
coordination, charge, protonation, preparation, parameterability, runtime, or
scientific authority.  Hashes are deterministic tamper evidence only.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any, Mapping

from .mmcif_syntax import CifBlock, CifLoop, CifSyntaxError, CifToken, parse_cif_block
from .mmcif_writer import (
    MMCIF_REPRESENTABLE_STATE_SCHEMA_ID,
    MMCIF_WRITER_VERSION,
    MmcifWriteError,
    mmcif_representable_state_sha256,
    write_mmcif,
)
from .models import AllAtomSystem
from .pdb_mmcif import (
    MMCIF_PARSER_VERSION,
    StructureIngestResult,
    StructureParseError,
    parse_mmcif,
)
from .serialization import (
    MolecularSerializationError,
    canonical_all_atom_snapshot_digest,
    deserialize_all_atom_system,
    serialize_all_atom_system,
)
from .topology import canonical_topology_sha256


MMCIF_NONPOLY_IDENTITY_ENVELOPE_VERSION = "1.0.0"
MMCIF_NONPOLY_IDENTITY_PARSER_VERSION = "1.0.0"
MMCIF_NONPOLY_IDENTITY_WRITER_VERSION = "1.0.0"
MMCIF_NONPOLY_IDENTITY_PARSER_NAME = (
    "betelgeuze_engine_v2.molecular.mmcif_nonpoly_identity"
)
MMCIF_NONPOLY_IDENTITY_PROFILE_ID = (
    "strict_mmcif_source_reported_nonpoly_identity_envelope/1.0.0"
)
MMCIF_NONPOLY_IDENTITY_PROJECTION_SCHEMA_ID = (
    "betelgeuze.mmcif_nonpoly_identity_projection/1.0.0"
)
MMCIF_NONPOLY_IDENTITY_RECORD_STATE_SCHEMA_ID = (
    "betelgeuze.mmcif_nonpoly_identity_record_state/1.0.0"
)
MMCIF_NONPOLY_IDENTITY_WRITE_RECEIPT_SCHEMA_ID = (
    "betelgeuze.mmcif_nonpoly_identity_write_receipt/1.0.0"
)
MMCIF_NONPOLY_IDENTITY_ROUND_TRIP_REPORT_SCHEMA_ID = (
    "betelgeuze.mmcif_nonpoly_identity_round_trip_report/1.0.0"
)

MAX_MMCIF_NONPOLY_IDENTITY_INPUT_BYTES = 64 * 1024 * 1024
MAX_MMCIF_NONPOLY_ENTITY_ROWS = 4_096
MAX_MMCIF_NONPOLY_SCHEME_ROWS = 80_000

_ENTITY_HEADERS = ("_entity.id", "_entity.type")
_STRUCT_ASYM_HEADERS = ("_struct_asym.id", "_struct_asym.entity_id")
_ENTITY_NONPOLY_HEADERS_A = (
    "_pdbx_entity_nonpoly.entity_id",
    "_pdbx_entity_nonpoly.comp_id",
)
_ENTITY_NONPOLY_HEADERS_B = (
    "_pdbx_entity_nonpoly.entity_id",
    "_pdbx_entity_nonpoly.name",
    "_pdbx_entity_nonpoly.comp_id",
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
_EXPECTED_CATEGORIES = frozenset(
    {
        "_entity",
        "_struct_asym",
        "_pdbx_entity_nonpoly",
        "_pdbx_nonpoly_scheme",
        "_atom_site",
    }
)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_FACTORY_TOKEN = object()

_FALSE_AUTHORITY_FIELDS = (
    "source_authenticated",
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
    "simulation_ready",
    "runtime_eligible",
    "execution_authorized",
    "claim_safe",
    "general_mmcif_round_trip_evidence_ready",
    "all_format_round_trip_evidence_ready",
)


class MmcifNonpolyIdentityError(ValueError):
    """Stable fail-closed error that never includes opaque source values."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        line_number: int | None = None,
    ) -> None:
        self.code = str(code)
        self.detail = str(message)
        self.line_number = None if line_number is None else int(line_number)
        suffix = "" if self.line_number is None else f" at line {self.line_number}"
        super().__init__(f"mmcif_nonpoly_identity:{self.code}{suffix}: {self.detail}")


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


def _require_sha256(value: Any, *, field_name: str) -> None:
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        raise ValueError(f"{field_name} must be a lowercase SHA-256")


def _authority_false_document() -> dict[str, bool]:
    return {field: False for field in _FALSE_AUTHORITY_FIELDS}


@dataclass(frozen=True, slots=True, init=False, repr=False)
class MmcifNonpolyEntityRow:
    """One selected entity-nonpoly row; opaque values are repr-hidden."""

    entity_id: str
    comp_id: str
    name: str | None
    _name_quoted: bool

    def __init__(
        self,
        *,
        entity_id: str,
        comp_id: str,
        name: str | None,
        _name_quoted: bool = False,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise TypeError("MmcifNonpolyEntityRow is factory-only")
        object.__setattr__(self, "entity_id", entity_id)
        object.__setattr__(self, "comp_id", comp_id)
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "_name_quoted", _name_quoted)
        self.__post_init__()

    def __post_init__(self) -> None:
        if not all(type(value) is str for value in (self.entity_id, self.comp_id)):
            raise TypeError("entity-nonpoly identifiers must be strings")
        if self.name is not None and type(self.name) is not str:
            raise TypeError("entity-nonpoly name must be a string or None")
        if type(self._name_quoted) is not bool:
            raise TypeError("entity-nonpoly name quote state must be boolean")


@dataclass(frozen=True, slots=True, init=False, repr=False)
class MmcifNonpolySchemeRow:
    """One selected nonpoly-scheme row; aliases are repr-hidden."""

    asym_id: str
    entity_id: str
    mon_id: str
    ndb_seq_num: str
    pdb_seq_num: str
    auth_seq_num: str
    pdb_mon_id: str
    auth_mon_id: str
    pdb_strand_id: str
    pdb_ins_code: str

    def __init__(
        self,
        *,
        asym_id: str,
        entity_id: str,
        mon_id: str,
        ndb_seq_num: str,
        pdb_seq_num: str,
        auth_seq_num: str,
        pdb_mon_id: str,
        auth_mon_id: str,
        pdb_strand_id: str,
        pdb_ins_code: str,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise TypeError("MmcifNonpolySchemeRow is factory-only")
        for field_name, value in (
            ("asym_id", asym_id),
            ("entity_id", entity_id),
            ("mon_id", mon_id),
            ("ndb_seq_num", ndb_seq_num),
            ("pdb_seq_num", pdb_seq_num),
            ("auth_seq_num", auth_seq_num),
            ("pdb_mon_id", pdb_mon_id),
            ("auth_mon_id", auth_mon_id),
            ("pdb_strand_id", pdb_strand_id),
            ("pdb_ins_code", pdb_ins_code),
        ):
            object.__setattr__(self, field_name, value)
        self.__post_init__()

    def __post_init__(self) -> None:
        for field_name in (
            "asym_id",
            "entity_id",
            "mon_id",
            "ndb_seq_num",
            "pdb_seq_num",
            "auth_seq_num",
            "pdb_mon_id",
            "auth_mon_id",
            "pdb_strand_id",
            "pdb_ins_code",
        ):
            if type(getattr(self, field_name)) is not str:
                raise TypeError("nonpoly-scheme aliases must be strings")


def _projection_document(
    entity_rows: tuple[MmcifNonpolyEntityRow, ...],
    scheme_rows: tuple[MmcifNonpolySchemeRow, ...],
) -> dict[str, Any]:
    return {
        "schema_id": MMCIF_NONPOLY_IDENTITY_PROJECTION_SCHEMA_ID,
        "envelope_version": MMCIF_NONPOLY_IDENTITY_ENVELOPE_VERSION,
        "parser_version": MMCIF_NONPOLY_IDENTITY_PARSER_VERSION,
        "profile_id": MMCIF_NONPOLY_IDENTITY_PROFILE_ID,
        "entity_nonpoly_rows": [
            {
                "ordinal": ordinal,
                "entity_id": row.entity_id,
                "comp_id": row.comp_id,
                "name": (
                    None
                    if row.name is None
                    else {"value": row.name, "quoted": row._name_quoted}
                ),
            }
            for ordinal, row in enumerate(entity_rows)
        ],
        "nonpoly_scheme_rows": [
            {
                "ordinal": ordinal,
                "asym_id": row.asym_id,
                "entity_id": row.entity_id,
                "mon_id": row.mon_id,
                "ndb_seq_num": row.ndb_seq_num,
                "pdb_seq_num": row.pdb_seq_num,
                "auth_seq_num": row.auth_seq_num,
                "pdb_mon_id": row.pdb_mon_id,
                "auth_mon_id": row.auth_mon_id,
                "pdb_strand_id": row.pdb_strand_id,
                "pdb_ins_code": row.pdb_ins_code,
            }
            for ordinal, row in enumerate(scheme_rows)
        ],
        "row_order": "source_order",
        "semantics": "source_reported_identity_and_instance_nomenclature_aliases_only",
    }


def _projection_sha256(
    entity_rows: tuple[MmcifNonpolyEntityRow, ...],
    scheme_rows: tuple[MmcifNonpolySchemeRow, ...],
) -> str:
    return _sha256_document(_projection_document(entity_rows, scheme_rows))


def _record_state_document(
    *,
    base_representable_state_sha256: str,
    identity_projection_sha256: str,
) -> dict[str, Any]:
    return {
        "schema_id": MMCIF_NONPOLY_IDENTITY_RECORD_STATE_SCHEMA_ID,
        "envelope_version": MMCIF_NONPOLY_IDENTITY_ENVELOPE_VERSION,
        "parser_version": MMCIF_NONPOLY_IDENTITY_PARSER_VERSION,
        "writer_version": MMCIF_NONPOLY_IDENTITY_WRITER_VERSION,
        "profile_id": MMCIF_NONPOLY_IDENTITY_PROFILE_ID,
        "base_parser_version": MMCIF_PARSER_VERSION,
        "base_writer_version": MMCIF_WRITER_VERSION,
        "base_representable_state_schema_id": MMCIF_REPRESENTABLE_STATE_SCHEMA_ID,
        "base_representable_state_sha256": base_representable_state_sha256,
        "identity_projection_schema_id": MMCIF_NONPOLY_IDENTITY_PROJECTION_SCHEMA_ID,
        "identity_projection_sha256": identity_projection_sha256,
    }


def _record_state_sha256(
    *,
    base_representable_state_sha256: str,
    identity_projection_sha256: str,
) -> str:
    return _sha256_document(
        _record_state_document(
            base_representable_state_sha256=base_representable_state_sha256,
            identity_projection_sha256=identity_projection_sha256,
        )
    )


def _loop_for(block: CifBlock, category: str) -> CifLoop:
    scalar = [tag for tag in block.scalar_values if tag.split(".", 1)[0] == category]
    loops = [loop for loop in block.loops if category in loop.categories]
    if scalar or len(loops) != 1 or loops[0].categories != (category,):
        raise MmcifNonpolyIdentityError(
            "unsupported_category_representation",
            "each selected category must occur in exactly one category-local loop",
        )
    return loops[0]


def _require_headers(loop: CifLoop, expected: tuple[str, ...]) -> None:
    if loop.tags != expected:
        raise MmcifNonpolyIdentityError(
            "unsupported_category_headers",
            "selected category headers are outside the exact envelope profile",
            line_number=loop.line_number,
        )


def _identity_value(token: CifToken, *, allow_missing: bool = False) -> str:
    if token.quoted or token.multiline:
        raise MmcifNonpolyIdentityError(
            "invalid_identity_token",
            "identity and alias tokens must be bare single-line CIF tokens",
            line_number=token.line_number,
        )
    if token.value in {".", "?"} and not allow_missing:
        raise MmcifNonpolyIdentityError(
            "invalid_identity_token",
            "identity and alias tokens must be nonmissing",
            line_number=token.line_number,
        )
    return token.value


def _name_value(token: CifToken) -> tuple[str, bool]:
    if token.multiline or "\n" in token.value or "\r" in token.value:
        raise MmcifNonpolyIdentityError(
            "invalid_nonpoly_name",
            "entity-nonpoly names must be single-line tokens",
            line_number=token.line_number,
        )
    if token.quoted and "'" in token.value and '"' in token.value:
        raise MmcifNonpolyIdentityError(
            "invalid_nonpoly_name",
            "entity-nonpoly name cannot be canonically quoted by this profile",
            line_number=token.line_number,
        )
    return token.value, token.quoted


def _token_text(token: CifToken) -> str:
    if token.multiline:
        raise MmcifNonpolyIdentityError(
            "unsupported_multiline_token",
            "multiline values are outside the exact envelope profile",
            line_number=token.line_number,
        )
    value = token.value
    if not token.quoted:
        return value
    if "'" not in value:
        return f"'{value}'"
    if '"' not in value:
        return f'"{value}"'
    raise MmcifNonpolyIdentityError(
        "unsupported_quoted_token",
        "quoted token cannot be canonically represented by the envelope",
        line_number=token.line_number,
    )


def _emit_cif_loop(loop: CifLoop) -> bytes:
    lines = ["loop_", *loop.tags]
    for row in loop.rows:
        values = [_token_text(token) for token in row]
        joined = " ".join(values)
        lines.extend((joined,) if len(joined) <= 2_048 else values)
    lines.append("#")
    return ("\n".join(lines) + "\n").encode("ascii")


def _emit_base_source(
    block: CifBlock,
    entity_loop: CifLoop,
    struct_asym_loop: CifLoop,
    atom_site_loop: CifLoop,
) -> bytes:
    return b"".join(
        (
            f"data_{block.name}\n#\n".encode("ascii"),
            _emit_cif_loop(entity_loop),
            _emit_cif_loop(struct_asym_loop),
            _emit_cif_loop(atom_site_loop),
        )
    )


def _parse_selected_rows(
    entity_nonpoly_loop: CifLoop,
    scheme_loop: CifLoop,
) -> tuple[tuple[MmcifNonpolyEntityRow, ...], tuple[MmcifNonpolySchemeRow, ...]]:
    if len(entity_nonpoly_loop.rows) > MAX_MMCIF_NONPOLY_ENTITY_ROWS:
        raise MmcifNonpolyIdentityError(
            "too_many_nonpoly_entity_rows",
            "entity-nonpoly row count exceeds the envelope limit",
        )
    if len(scheme_loop.rows) > MAX_MMCIF_NONPOLY_SCHEME_ROWS:
        raise MmcifNonpolyIdentityError(
            "too_many_nonpoly_scheme_rows",
            "nonpoly-scheme row count exceeds the envelope limit",
        )
    has_name = entity_nonpoly_loop.tags == _ENTITY_NONPOLY_HEADERS_B
    entity_rows: list[MmcifNonpolyEntityRow] = []
    for tokens in entity_nonpoly_loop.rows:
        entity_id = _identity_value(tokens[0])
        if has_name:
            name, quoted = _name_value(tokens[1])
            comp_id = _identity_value(tokens[2])
        else:
            name, quoted = None, False
            comp_id = _identity_value(tokens[1])
        entity_rows.append(
            MmcifNonpolyEntityRow(
                entity_id=entity_id,
                comp_id=comp_id,
                name=name,
                _name_quoted=quoted,
                _factory_token=_FACTORY_TOKEN,
            )
        )

    scheme_rows: list[MmcifNonpolySchemeRow] = []
    for tokens in scheme_loop.rows:
        values = [
            _identity_value(token, allow_missing=index == 9)
            for index, token in enumerate(tokens)
        ]
        scheme_rows.append(
            MmcifNonpolySchemeRow(
                asym_id=values[0],
                entity_id=values[1],
                mon_id=values[2],
                ndb_seq_num=values[3],
                pdb_seq_num=values[4],
                auth_seq_num=values[5],
                pdb_mon_id=values[6],
                auth_mon_id=values[7],
                pdb_strand_id=values[8],
                pdb_ins_code=values[9],
                _factory_token=_FACTORY_TOKEN,
            )
        )
    return tuple(entity_rows), tuple(scheme_rows)


def _raw_row_map(loop: CifLoop) -> list[dict[str, CifToken]]:
    return [dict(zip(loop.tags, row, strict=True)) for row in loop.rows]


def _validate_joins(
    *,
    entity_loop: CifLoop,
    struct_asym_loop: CifLoop,
    atom_site_loop: CifLoop,
    entity_rows: tuple[MmcifNonpolyEntityRow, ...],
    scheme_rows: tuple[MmcifNonpolySchemeRow, ...],
) -> None:
    entity_types: dict[str, str] = {}
    for row in _raw_row_map(entity_loop):
        entity_id = _identity_value(row["_entity.id"])
        entity_type = _identity_value(row["_entity.type"])
        if entity_id in entity_types:
            raise MmcifNonpolyIdentityError(
                "duplicate_base_entity_id",
                "base entity identifiers must be unique",
            )
        entity_types[entity_id] = entity_type

    selected: dict[str, str] = {}
    for row in entity_rows:
        if row.entity_id in selected:
            raise MmcifNonpolyIdentityError(
                "duplicate_nonpoly_entity_id",
                "entity-nonpoly identifiers must be unique",
            )
        selected[row.entity_id] = row.comp_id
    required = {
        entity_id
        for entity_id, entity_type in entity_types.items()
        if entity_type in {"non-polymer", "water"}
    }
    if set(selected) != required:
        raise MmcifNonpolyIdentityError(
            "nonpoly_entity_selection_mismatch",
            "entity-nonpoly rows must exactly cover non-polymer and water entities",
        )

    asym_entities: dict[str, str] = {}
    for row in _raw_row_map(struct_asym_loop):
        asym_id = _identity_value(row["_struct_asym.id"])
        entity_id = _identity_value(row["_struct_asym.entity_id"])
        if asym_id in asym_entities:
            raise MmcifNonpolyIdentityError(
                "duplicate_struct_asym_id",
                "struct-asym identifiers must be unique",
            )
        asym_entities[asym_id] = entity_id

    scheme_counts: Counter[tuple[str, str, str]] = Counter()
    seen_scheme_keys: set[tuple[str, str]] = set()
    for row in scheme_rows:
        key = (row.asym_id, row.ndb_seq_num)
        if key in seen_scheme_keys:
            raise MmcifNonpolyIdentityError(
                "duplicate_nonpoly_scheme_key",
                "nonpoly-scheme keys must be unique",
            )
        seen_scheme_keys.add(key)
        if (
            asym_entities.get(row.asym_id) != row.entity_id
            or row.entity_id not in selected
        ):
            raise MmcifNonpolyIdentityError(
                "nonpoly_scheme_join_mismatch",
                "nonpoly-scheme asym and entity joins are inconsistent",
            )
        if selected[row.entity_id] != row.mon_id:
            raise MmcifNonpolyIdentityError(
                "nonpoly_component_join_mismatch",
                "nonpoly-scheme component identity is inconsistent",
            )
        scheme_counts[(row.asym_id, row.entity_id, row.mon_id)] += 1

    for row in _raw_row_map(atom_site_loop):
        entity_id = _identity_value(row["_atom_site.label_entity_id"])
        if entity_id not in selected:
            continue
        asym_id = _identity_value(row["_atom_site.label_asym_id"])
        comp_id = _identity_value(row["_atom_site.label_comp_id"])
        if asym_entities.get(asym_id) != entity_id:
            raise MmcifNonpolyIdentityError(
                "nonpoly_atom_join_mismatch",
                "nonpoly atom-site asym and entity joins are inconsistent",
            )
        if selected[entity_id] != comp_id:
            raise MmcifNonpolyIdentityError(
                "nonpoly_component_join_mismatch",
                "nonpoly atom-site component identity is inconsistent",
            )
        _identity_value(row["_atom_site.auth_seq_id"])
        _identity_value(row["_atom_site.pdbx_pdb_ins_code"], allow_missing=True)


def _validate_scheme_counts_against_system(
    *,
    system: AllAtomSystem,
    scheme_rows: tuple[MmcifNonpolySchemeRow, ...],
) -> None:
    scheme_counts: Counter[tuple[str, str, str]] = Counter(
        (row.asym_id, row.entity_id, row.mon_id) for row in scheme_rows
    )
    chains = {chain.index: chain for chain in system.chains}
    residue_counts: Counter[tuple[str, str, str]] = Counter()
    for residue in system.residues:
        if residue.entity_type not in {"non_polymer", "water"}:
            continue
        chain = chains[residue.chain_index]
        residue_counts[(chain.chain_id, chain.entity_id, residue.name)] += 1
    if scheme_counts != residue_counts:
        raise MmcifNonpolyIdentityError(
            "nonpoly_residue_count_mismatch",
            "nonpoly-scheme rows must match canonical nonpoly residue instances",
        )


@dataclass(frozen=True, slots=True, init=False, repr=False)
class MmcifNonpolyIdentityIngestResult:
    _system_snapshot_payload: bytes
    _base_coverage: Any
    _base_missingness_evidence: Any
    _full_source_bytes: bytes
    _normalized_base_source_bytes: bytes
    _canonical_base_source_bytes: bytes
    entity_rows: tuple[MmcifNonpolyEntityRow, ...]
    scheme_rows: tuple[MmcifNonpolySchemeRow, ...]
    data_block_name: str
    full_source_sha256: str
    normalized_base_source_sha256: str
    canonical_base_source_sha256: str
    base_system_snapshot_sha256: str
    base_topology_sha256: str
    base_representable_state_sha256: str
    identity_projection_sha256: str
    record_state_sha256: str

    def __init__(
        self,
        *,
        system: AllAtomSystem,
        base_ingest: StructureIngestResult,
        entity_rows: tuple[MmcifNonpolyEntityRow, ...],
        scheme_rows: tuple[MmcifNonpolySchemeRow, ...],
        data_block_name: str,
        full_source_sha256: str,
        normalized_base_source_sha256: str,
        canonical_base_source_sha256: str,
        full_source_bytes: bytes,
        normalized_base_source_bytes: bytes,
        canonical_base_source_bytes: bytes,
        base_system_snapshot_sha256: str,
        base_topology_sha256: str,
        base_representable_state_sha256: str,
        identity_projection_sha256: str,
        record_state_sha256: str,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise TypeError("MmcifNonpolyIdentityIngestResult is factory-only")
        if base_ingest.system is not system:
            raise ValueError("ingest result base/system binding is inconsistent")
        for field_name, value in (
            ("_system_snapshot_payload", serialize_all_atom_system(system)),
            ("_base_coverage", base_ingest.coverage),
            ("_base_missingness_evidence", base_ingest.missingness_evidence),
            ("_full_source_bytes", full_source_bytes),
            ("_normalized_base_source_bytes", normalized_base_source_bytes),
            ("_canonical_base_source_bytes", canonical_base_source_bytes),
            ("entity_rows", entity_rows),
            ("scheme_rows", scheme_rows),
            ("data_block_name", data_block_name),
            ("full_source_sha256", full_source_sha256),
            ("normalized_base_source_sha256", normalized_base_source_sha256),
            ("canonical_base_source_sha256", canonical_base_source_sha256),
            ("base_system_snapshot_sha256", base_system_snapshot_sha256),
            ("base_topology_sha256", base_topology_sha256),
            ("base_representable_state_sha256", base_representable_state_sha256),
            ("identity_projection_sha256", identity_projection_sha256),
            ("record_state_sha256", record_state_sha256),
        ):
            object.__setattr__(self, field_name, value)
        self.__post_init__()

    @property
    def system(self) -> AllAtomSystem:
        """Return a detached system reconstructed from the bound snapshot."""

        return deserialize_all_atom_system(self._system_snapshot_payload)

    @property
    def base_ingest(self) -> StructureIngestResult:
        """Return a detached view of the base parser result."""

        return StructureIngestResult(
            system=self.system,
            coverage=self._base_coverage,
            missingness_evidence=self._base_missingness_evidence,
        )

    def __post_init__(self) -> None:
        for field_name in (
            "_system_snapshot_payload",
            "_full_source_bytes",
            "_normalized_base_source_bytes",
            "_canonical_base_source_bytes",
        ):
            if type(getattr(self, field_name)) is not bytes:
                raise TypeError("bound ingest payloads must be bytes")
        if type(self.data_block_name) is not str:
            raise TypeError("data_block_name must be a string")
        if not self.data_block_name.isascii():
            raise ValueError("ingest data-block name must be ASCII")
        data_block_name_bytes = self.data_block_name.encode("ascii")
        if type(self.entity_rows) is not tuple or type(self.scheme_rows) is not tuple:
            raise TypeError("selected rows must be tuples")
        for field_name in (
            "full_source_sha256",
            "normalized_base_source_sha256",
            "canonical_base_source_sha256",
            "base_system_snapshot_sha256",
            "base_topology_sha256",
            "base_representable_state_sha256",
            "identity_projection_sha256",
            "record_state_sha256",
        ):
            _require_sha256(getattr(self, field_name), field_name=field_name)
        if (
            hashlib.sha256(self._full_source_bytes).hexdigest()
            != self.full_source_sha256
        ):
            raise ValueError("ingest full-source digest is inconsistent")
        if (
            hashlib.sha256(self._normalized_base_source_bytes).hexdigest()
            != self.normalized_base_source_sha256
        ):
            raise ValueError("ingest normalized-base digest is inconsistent")
        normalized_header_end = self._normalized_base_source_bytes.find(b"\n")
        if (
            normalized_header_end < 0
            or self._normalized_base_source_bytes[:normalized_header_end]
            != b"data_" + data_block_name_bytes
        ):
            raise ValueError("ingest data-block binding is inconsistent")
        if (
            hashlib.sha256(self._canonical_base_source_bytes).hexdigest()
            != self.canonical_base_source_sha256
        ):
            raise ValueError("ingest canonical-base digest is inconsistent")
        system = self.system
        if (
            canonical_all_atom_snapshot_digest(system)
            != self.base_system_snapshot_sha256
        ):
            raise ValueError("ingest system snapshot digest is inconsistent")
        if canonical_topology_sha256(system) != self.base_topology_sha256:
            raise ValueError("ingest topology digest is inconsistent")
        if (
            mmcif_representable_state_sha256(system)
            != self.base_representable_state_sha256
        ):
            raise ValueError("ingest representable-state digest is inconsistent")
        expected_projection = _projection_sha256(self.entity_rows, self.scheme_rows)
        if self.identity_projection_sha256 != expected_projection:
            raise ValueError("ingest identity projection digest is inconsistent")
        expected_state = _record_state_sha256(
            base_representable_state_sha256=self.base_representable_state_sha256,
            identity_projection_sha256=self.identity_projection_sha256,
        )
        if self.record_state_sha256 != expected_state:
            raise ValueError("ingest record-state digest is inconsistent")

    def to_dict(self) -> dict[str, Any]:
        document: dict[str, Any] = {
            "schema_id": MMCIF_NONPOLY_IDENTITY_RECORD_STATE_SCHEMA_ID,
            "profile_id": MMCIF_NONPOLY_IDENTITY_PROFILE_ID,
            "envelope_version": MMCIF_NONPOLY_IDENTITY_ENVELOPE_VERSION,
            "parser_version": MMCIF_NONPOLY_IDENTITY_PARSER_VERSION,
            "base_parser_version": MMCIF_PARSER_VERSION,
            "base_writer_version": MMCIF_WRITER_VERSION,
            "full_source_sha256": self.full_source_sha256,
            "normalized_base_source_sha256": self.normalized_base_source_sha256,
            "canonical_base_source_sha256": self.canonical_base_source_sha256,
            "base_system_snapshot_sha256": self.base_system_snapshot_sha256,
            "base_topology_sha256": self.base_topology_sha256,
            "base_representable_state_sha256": self.base_representable_state_sha256,
            "identity_projection_sha256": self.identity_projection_sha256,
            "record_state_sha256": self.record_state_sha256,
            "entity_nonpoly_row_count": len(self.entity_rows),
            "nonpoly_scheme_row_count": len(self.scheme_rows),
            "source_identity_projection_preserved": True,
        }
        document.update(_authority_false_document())
        return document


def parse_mmcif_nonpoly_identity(
    data: bytes,
    *,
    source_id: str = "",
) -> MmcifNonpolyIdentityIngestResult:
    """Parse the exact five-loop nonpoly identity envelope."""

    if type(data) is not bytes:
        raise TypeError("mmCIF nonpoly identity input must be bytes")
    if type(source_id) is not str:
        raise TypeError("source_id must be a string")
    if not data:
        raise MmcifNonpolyIdentityError("empty_input", "input is empty")
    if len(data) > MAX_MMCIF_NONPOLY_IDENTITY_INPUT_BYTES:
        raise MmcifNonpolyIdentityError(
            "input_too_large",
            "input exceeds the nonpoly identity envelope byte limit",
        )
    decoded: str | None
    try:
        decoded = data.decode("ascii")
    except UnicodeDecodeError:
        decoded = None
    if decoded is None:
        raise MmcifNonpolyIdentityError(
            "non_ascii_input",
            "input must use the printable CIF 1.1 ASCII character set",
        )

    syntax_error: CifSyntaxError | None = None
    try:
        block = parse_cif_block(decoded)
    except CifSyntaxError as exc:
        syntax_error = exc
    if syntax_error is not None:
        code = (
            "unsupported_category_representation"
            if syntax_error.code == "duplicate_data_name"
            else syntax_error.code
        )
        raise MmcifNonpolyIdentityError(
            code,
            "input is outside the exact single-block CIF envelope grammar",
            line_number=syntax_error.line_number,
        )
    assert block is not None

    if set(block.categories) != _EXPECTED_CATEGORIES:
        raise MmcifNonpolyIdentityError(
            "unsupported_category_surface",
            "input categories must exactly match the five-category envelope",
        )

    entity_loop = _loop_for(block, "_entity")
    struct_asym_loop = _loop_for(block, "_struct_asym")
    entity_nonpoly_loop = _loop_for(block, "_pdbx_entity_nonpoly")
    scheme_loop = _loop_for(block, "_pdbx_nonpoly_scheme")
    atom_site_loop = _loop_for(block, "_atom_site")
    _require_headers(entity_loop, _ENTITY_HEADERS)
    _require_headers(struct_asym_loop, _STRUCT_ASYM_HEADERS)
    if entity_nonpoly_loop.tags not in {
        _ENTITY_NONPOLY_HEADERS_A,
        _ENTITY_NONPOLY_HEADERS_B,
    }:
        raise MmcifNonpolyIdentityError(
            "unsupported_category_headers",
            "entity-nonpoly headers are outside the exact envelope profiles",
        )
    _require_headers(scheme_loop, _NONPOLY_SCHEME_HEADERS)
    _require_headers(atom_site_loop, _COMMON_CORE21_ATOM_SITE_HEADERS)

    entity_rows, scheme_rows = _parse_selected_rows(entity_nonpoly_loop, scheme_loop)
    _validate_joins(
        entity_loop=entity_loop,
        struct_asym_loop=struct_asym_loop,
        atom_site_loop=atom_site_loop,
        entity_rows=entity_rows,
        scheme_rows=scheme_rows,
    )
    normalized_base_source = _emit_base_source(
        block, entity_loop, struct_asym_loop, atom_site_loop
    )
    base_ingest: StructureIngestResult | None = None
    try:
        base_ingest = parse_mmcif(normalized_base_source, source_id=source_id)
    except StructureParseError:
        pass
    if base_ingest is None:
        raise MmcifNonpolyIdentityError(
            "base_parser_rejected",
            "the common-core21 base projection was rejected",
        )
    _validate_scheme_counts_against_system(
        system=base_ingest.system,
        scheme_rows=scheme_rows,
    )
    base_write = None
    base_representable: str | None = None
    try:
        base_write = write_mmcif(base_ingest.system)
        base_representable = mmcif_representable_state_sha256(base_ingest.system)
    except MmcifWriteError:
        pass
    if base_write is None or base_representable is None:
        raise MmcifNonpolyIdentityError(
            "base_writer_rejected",
            "the common-core21 base state was not representable",
        )

    projection_sha = _projection_sha256(entity_rows, scheme_rows)
    record_state_sha = _record_state_sha256(
        base_representable_state_sha256=base_representable,
        identity_projection_sha256=projection_sha,
    )
    return MmcifNonpolyIdentityIngestResult(
        system=base_ingest.system,
        base_ingest=base_ingest,
        entity_rows=entity_rows,
        scheme_rows=scheme_rows,
        data_block_name=block.name,
        full_source_sha256=hashlib.sha256(data).hexdigest(),
        normalized_base_source_sha256=hashlib.sha256(
            normalized_base_source
        ).hexdigest(),
        canonical_base_source_sha256=hashlib.sha256(base_write.payload).hexdigest(),
        full_source_bytes=data,
        normalized_base_source_bytes=normalized_base_source,
        canonical_base_source_bytes=base_write.payload,
        base_system_snapshot_sha256=canonical_all_atom_snapshot_digest(
            base_ingest.system
        ),
        base_topology_sha256=canonical_topology_sha256(base_ingest.system),
        base_representable_state_sha256=base_representable,
        identity_projection_sha256=projection_sha,
        record_state_sha256=record_state_sha,
        _factory_token=_FACTORY_TOKEN,
    )


def mmcif_nonpoly_identity_projection_sha256(
    ingest: MmcifNonpolyIdentityIngestResult,
) -> str:
    if not isinstance(ingest, MmcifNonpolyIdentityIngestResult):
        raise TypeError("ingest must be an MmcifNonpolyIdentityIngestResult")
    if (
        hashlib.sha256(ingest._full_source_bytes).hexdigest()
        != ingest.full_source_sha256
        or hashlib.sha256(ingest._normalized_base_source_bytes).hexdigest()
        != ingest.normalized_base_source_sha256
        or hashlib.sha256(ingest._canonical_base_source_bytes).hexdigest()
        != ingest.canonical_base_source_sha256
    ):
        raise MmcifNonpolyIdentityError(
            "stale_source_binding",
            "bound source bytes no longer match the ingest digests",
        )
    return _projection_sha256(ingest.entity_rows, ingest.scheme_rows)


def mmcif_nonpoly_identity_record_state_sha256(
    ingest: MmcifNonpolyIdentityIngestResult,
) -> str:
    if not isinstance(ingest, MmcifNonpolyIdentityIngestResult):
        raise TypeError("ingest must be an MmcifNonpolyIdentityIngestResult")
    return _record_state_sha256(
        base_representable_state_sha256=mmcif_representable_state_sha256(ingest.system),
        identity_projection_sha256=mmcif_nonpoly_identity_projection_sha256(ingest),
    )


def _emit_selected_loops(ingest: MmcifNonpolyIdentityIngestResult) -> bytes:
    def append_row(lines: list[str], values: list[str]) -> None:
        joined = " ".join(values)
        lines.extend((joined,) if len(joined) <= 2_048 else values)

    has_name = [row.name is not None for row in ingest.entity_rows]
    if all(has_name):
        entity_headers = _ENTITY_NONPOLY_HEADERS_B
    elif not any(has_name):
        entity_headers = _ENTITY_NONPOLY_HEADERS_A
    else:
        raise MmcifNonpolyIdentityError(
            "stale_entity_profile",
            "entity-nonpoly rows no longer share one exact header profile",
        )

    entity_lines = ["loop_", *entity_headers]
    for row in ingest.entity_rows:
        values = [row.entity_id]
        if row.name is not None:
            token = CifToken(
                value=row.name,
                line_number=0,
                column_number=0,
                quoted=row._name_quoted,
            )
            values.append(_token_text(token))
        values.append(row.comp_id)
        append_row(entity_lines, values)
    entity_lines.append("#")

    scheme_lines = ["loop_", *_NONPOLY_SCHEME_HEADERS]
    for row in ingest.scheme_rows:
        append_row(
            scheme_lines,
            [
                row.asym_id,
                row.entity_id,
                row.mon_id,
                row.ndb_seq_num,
                row.pdb_seq_num,
                row.auth_seq_num,
                row.pdb_mon_id,
                row.auth_mon_id,
                row.pdb_strand_id,
                row.pdb_ins_code,
            ],
        )
    scheme_lines.append("#")
    return ("\n".join((*entity_lines, *scheme_lines)) + "\n").encode("ascii")


def _receipt_payload(receipt: "MmcifNonpolyIdentityWriteReceipt") -> dict[str, Any]:
    return {
        "schema_id": receipt.schema_id,
        "envelope_version": receipt.envelope_version,
        "writer_version": receipt.writer_version,
        "profile_id": receipt.profile_id,
        "input_full_source_sha256": receipt.input_full_source_sha256,
        "input_normalized_base_source_sha256": (
            receipt.input_normalized_base_source_sha256
        ),
        "input_canonical_base_source_sha256": (
            receipt.input_canonical_base_source_sha256
        ),
        "input_base_system_snapshot_sha256": (
            receipt.input_base_system_snapshot_sha256
        ),
        "input_base_topology_sha256": receipt.input_base_topology_sha256,
        "input_base_representable_state_sha256": (
            receipt.input_base_representable_state_sha256
        ),
        "input_identity_projection_sha256": receipt.input_identity_projection_sha256,
        "input_record_state_sha256": receipt.input_record_state_sha256,
        "base_writer_receipt_sha256": receipt.base_writer_receipt_sha256,
        "output_source_sha256": receipt.output_source_sha256,
        "output_byte_count": receipt.output_byte_count,
        "entity_nonpoly_row_count": receipt.entity_nonpoly_row_count,
        "nonpoly_scheme_row_count": receipt.nonpoly_scheme_row_count,
    }


@dataclass(frozen=True, slots=True, init=False, repr=False)
class MmcifNonpolyIdentityWriteReceipt:
    """Factory-only binding for one deterministic five-category emission."""

    schema_id: str
    envelope_version: str
    writer_version: str
    profile_id: str
    input_full_source_sha256: str
    input_normalized_base_source_sha256: str
    input_canonical_base_source_sha256: str
    input_base_system_snapshot_sha256: str
    input_base_topology_sha256: str
    input_base_representable_state_sha256: str
    input_identity_projection_sha256: str
    input_record_state_sha256: str
    base_writer_receipt_sha256: str
    output_source_sha256: str
    output_byte_count: int
    entity_nonpoly_row_count: int
    nonpoly_scheme_row_count: int
    receipt_sha256: str

    def __init__(
        self,
        *,
        schema_id: Any = None,
        envelope_version: Any = None,
        writer_version: Any = None,
        profile_id: Any = None,
        input_full_source_sha256: Any = None,
        input_normalized_base_source_sha256: Any = None,
        input_canonical_base_source_sha256: Any = None,
        input_base_system_snapshot_sha256: Any = None,
        input_base_topology_sha256: Any = None,
        input_base_representable_state_sha256: Any = None,
        input_identity_projection_sha256: Any = None,
        input_record_state_sha256: Any = None,
        base_writer_receipt_sha256: Any = None,
        output_source_sha256: Any = None,
        output_byte_count: Any = None,
        entity_nonpoly_row_count: Any = None,
        nonpoly_scheme_row_count: Any = None,
        receipt_sha256: Any = None,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise TypeError("MmcifNonpolyIdentityWriteReceipt is factory-only")
        for field_name, value in (
            ("schema_id", schema_id),
            ("envelope_version", envelope_version),
            ("writer_version", writer_version),
            ("profile_id", profile_id),
            ("input_full_source_sha256", input_full_source_sha256),
            (
                "input_normalized_base_source_sha256",
                input_normalized_base_source_sha256,
            ),
            (
                "input_canonical_base_source_sha256",
                input_canonical_base_source_sha256,
            ),
            (
                "input_base_system_snapshot_sha256",
                input_base_system_snapshot_sha256,
            ),
            ("input_base_topology_sha256", input_base_topology_sha256),
            (
                "input_base_representable_state_sha256",
                input_base_representable_state_sha256,
            ),
            ("input_identity_projection_sha256", input_identity_projection_sha256),
            ("input_record_state_sha256", input_record_state_sha256),
            ("base_writer_receipt_sha256", base_writer_receipt_sha256),
            ("output_source_sha256", output_source_sha256),
            ("output_byte_count", output_byte_count),
            ("entity_nonpoly_row_count", entity_nonpoly_row_count),
            ("nonpoly_scheme_row_count", nonpoly_scheme_row_count),
            ("receipt_sha256", receipt_sha256),
        ):
            object.__setattr__(self, field_name, value)
        self.__post_init__()

    def __post_init__(self) -> None:
        if self.schema_id != MMCIF_NONPOLY_IDENTITY_WRITE_RECEIPT_SCHEMA_ID:
            raise ValueError("write receipt schema is inconsistent")
        if self.envelope_version != MMCIF_NONPOLY_IDENTITY_ENVELOPE_VERSION:
            raise ValueError("write receipt envelope version is inconsistent")
        if self.writer_version != MMCIF_NONPOLY_IDENTITY_WRITER_VERSION:
            raise ValueError("write receipt writer version is inconsistent")
        if self.profile_id != MMCIF_NONPOLY_IDENTITY_PROFILE_ID:
            raise ValueError("write receipt profile is inconsistent")
        for field_name in (
            "input_full_source_sha256",
            "input_normalized_base_source_sha256",
            "input_canonical_base_source_sha256",
            "input_base_system_snapshot_sha256",
            "input_base_topology_sha256",
            "input_base_representable_state_sha256",
            "input_identity_projection_sha256",
            "input_record_state_sha256",
            "base_writer_receipt_sha256",
            "output_source_sha256",
            "receipt_sha256",
        ):
            _require_sha256(getattr(self, field_name), field_name=field_name)
        for field_name in (
            "output_byte_count",
            "entity_nonpoly_row_count",
            "nonpoly_scheme_row_count",
        ):
            value = getattr(self, field_name)
            if type(value) is not int or value < 0:
                raise TypeError(f"{field_name} must be a nonnegative integer")
        if self.receipt_sha256 != _sha256_document(_receipt_payload(self)):
            raise ValueError("write receipt digest is inconsistent")

    def to_dict(self) -> dict[str, Any]:
        document = _receipt_payload(self)
        document["receipt_sha256"] = self.receipt_sha256
        document["source_identity_projection_preserved"] = True
        document.update(_authority_false_document())
        return document


@dataclass(frozen=True, slots=True, init=False, repr=False)
class MmcifNonpolyIdentityWriteResult:
    payload: bytes
    receipt: MmcifNonpolyIdentityWriteReceipt

    def __init__(
        self,
        *,
        payload: bytes,
        receipt: MmcifNonpolyIdentityWriteReceipt,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise TypeError("MmcifNonpolyIdentityWriteResult is factory-only")
        object.__setattr__(self, "payload", payload)
        object.__setattr__(self, "receipt", receipt)
        self.__post_init__()

    def __post_init__(self) -> None:
        if type(self.payload) is not bytes:
            raise TypeError("write payload must be bytes")
        if not isinstance(self.receipt, MmcifNonpolyIdentityWriteReceipt):
            raise TypeError("write result must contain its typed receipt")
        self.receipt.__post_init__()
        if (
            hashlib.sha256(self.payload).hexdigest()
            != self.receipt.output_source_sha256
        ):
            raise ValueError("write payload and receipt digest are inconsistent")
        if len(self.payload) != self.receipt.output_byte_count:
            raise ValueError("write payload and receipt byte count are inconsistent")


def _make_receipt(
    *,
    ingest: MmcifNonpolyIdentityIngestResult,
    base_writer_receipt_sha256: str,
    payload: bytes,
) -> MmcifNonpolyIdentityWriteReceipt:
    values: dict[str, Any] = {
        "schema_id": MMCIF_NONPOLY_IDENTITY_WRITE_RECEIPT_SCHEMA_ID,
        "envelope_version": MMCIF_NONPOLY_IDENTITY_ENVELOPE_VERSION,
        "writer_version": MMCIF_NONPOLY_IDENTITY_WRITER_VERSION,
        "profile_id": MMCIF_NONPOLY_IDENTITY_PROFILE_ID,
        "input_full_source_sha256": ingest.full_source_sha256,
        "input_normalized_base_source_sha256": ingest.normalized_base_source_sha256,
        "input_canonical_base_source_sha256": ingest.canonical_base_source_sha256,
        "input_base_system_snapshot_sha256": ingest.base_system_snapshot_sha256,
        "input_base_topology_sha256": ingest.base_topology_sha256,
        "input_base_representable_state_sha256": ingest.base_representable_state_sha256,
        "input_identity_projection_sha256": ingest.identity_projection_sha256,
        "input_record_state_sha256": ingest.record_state_sha256,
        "base_writer_receipt_sha256": base_writer_receipt_sha256,
        "output_source_sha256": hashlib.sha256(payload).hexdigest(),
        "output_byte_count": len(payload),
        "entity_nonpoly_row_count": len(ingest.entity_rows),
        "nonpoly_scheme_row_count": len(ingest.scheme_rows),
    }
    provisional = type("_ReceiptDocument", (), values)()
    values["receipt_sha256"] = _sha256_document(_receipt_payload(provisional))
    return MmcifNonpolyIdentityWriteReceipt(
        **values,
        _factory_token=_FACTORY_TOKEN,
    )


def write_mmcif_nonpoly_identity(
    ingest: MmcifNonpolyIdentityIngestResult,
) -> MmcifNonpolyIdentityWriteResult:
    """Emit the canonical five-category envelope from one fresh ingest."""

    if not isinstance(ingest, MmcifNonpolyIdentityIngestResult):
        raise TypeError("ingest must be an MmcifNonpolyIdentityIngestResult")
    if (
        hashlib.sha256(ingest._full_source_bytes).hexdigest()
        != ingest.full_source_sha256
        or hashlib.sha256(ingest._normalized_base_source_bytes).hexdigest()
        != ingest.normalized_base_source_sha256
        or hashlib.sha256(ingest._canonical_base_source_bytes).hexdigest()
        != ingest.canonical_base_source_sha256
    ):
        raise MmcifNonpolyIdentityError(
            "stale_source_binding",
            "bound source bytes no longer match the ingest digests",
        )
    projection_sha = _projection_sha256(ingest.entity_rows, ingest.scheme_rows)
    if projection_sha != ingest.identity_projection_sha256:
        raise MmcifNonpolyIdentityError(
            "stale_identity_projection",
            "selected identity projection no longer matches the ingest binding",
        )
    system: AllAtomSystem | None = None
    try:
        system = ingest.system
    except (MolecularSerializationError, ValueError, TypeError):
        pass
    if system is None:
        raise MmcifNonpolyIdentityError(
            "stale_base_state",
            "bound system snapshot can no longer be reconstructed",
        )
    snapshot_sha: str | None = None
    topology_sha: str | None = None
    representable_sha: str | None = None
    base_write = None
    try:
        snapshot_sha = canonical_all_atom_snapshot_digest(system)
        topology_sha = canonical_topology_sha256(system)
        representable_sha = mmcif_representable_state_sha256(system)
        base_write = write_mmcif(system)
    except (MmcifWriteError, ValueError, TypeError):
        pass
    if (
        snapshot_sha is None
        or topology_sha is None
        or representable_sha is None
        or base_write is None
    ):
        raise MmcifNonpolyIdentityError(
            "stale_base_state",
            "base molecular state no longer satisfies the exact writer contract",
        )
    if (
        snapshot_sha != ingest.base_system_snapshot_sha256
        or topology_sha != ingest.base_topology_sha256
        or representable_sha != ingest.base_representable_state_sha256
        or base_write.payload != ingest._canonical_base_source_bytes
    ):
        raise MmcifNonpolyIdentityError(
            "stale_base_state",
            "base molecular state no longer matches the ingest binding",
        )
    state_sha = _record_state_sha256(
        base_representable_state_sha256=representable_sha,
        identity_projection_sha256=projection_sha,
    )
    if state_sha != ingest.record_state_sha256:
        raise MmcifNonpolyIdentityError(
            "stale_record_state",
            "combined record state no longer matches the ingest binding",
        )

    marker = b"loop_\n_atom_site.group_pdb\n"
    if base_write.payload.count(marker) != 1:
        raise MmcifNonpolyIdentityError(
            "base_emission_mismatch",
            "canonical base emission lacks its exact atom-site boundary",
        )
    offset = base_write.payload.index(marker)
    payload = (
        base_write.payload[:offset]
        + _emit_selected_loops(ingest)
        + base_write.payload[offset:]
    )
    if len(payload) > MAX_MMCIF_NONPOLY_IDENTITY_INPUT_BYTES:
        raise MmcifNonpolyIdentityError(
            "output_too_large",
            "canonical output exceeds the envelope byte limit",
        )
    output_syntax_error: CifSyntaxError | None = None
    output_block: CifBlock | None = None
    try:
        output_block = parse_cif_block(payload.decode("ascii"))
    except CifSyntaxError as exc:
        output_syntax_error = exc
    if output_syntax_error is not None:
        raise MmcifNonpolyIdentityError(
            "invalid_canonical_output",
            "canonical output failed its CIF syntax preflight",
        )
    assert output_block is not None
    if set(output_block.categories) != _EXPECTED_CATEGORIES:
        raise MmcifNonpolyIdentityError(
            "invalid_canonical_output",
            "canonical output category surface is inconsistent",
        )
    receipt = _make_receipt(
        ingest=ingest,
        base_writer_receipt_sha256=base_write.receipt.receipt_sha256,
        payload=payload,
    )
    return MmcifNonpolyIdentityWriteResult(
        payload=payload,
        receipt=receipt,
        _factory_token=_FACTORY_TOKEN,
    )


def serialize_mmcif_nonpoly_identity(
    ingest: MmcifNonpolyIdentityIngestResult,
) -> bytes:
    return write_mmcif_nonpoly_identity(ingest).payload


def _report_payload(report: "MmcifNonpolyIdentityRoundTripReport") -> dict[str, Any]:
    return {
        "schema_id": report.schema_id,
        "envelope_version": report.envelope_version,
        "profile_id": report.profile_id,
        "input_full_source_sha256": report.input_full_source_sha256,
        "writer_receipt_sha256": report.writer_receipt_sha256,
        "reemitted_writer_receipt_sha256": (report.reemitted_writer_receipt_sha256),
        "input_identity_projection_sha256": report.input_identity_projection_sha256,
        "reparsed_identity_projection_sha256": (
            report.reparsed_identity_projection_sha256
        ),
        "input_record_state_sha256": report.input_record_state_sha256,
        "reparsed_record_state_sha256": report.reparsed_record_state_sha256,
        "emitted_source_sha256": report.emitted_source_sha256,
        "reemitted_source_sha256": report.reemitted_source_sha256,
        "identity_projection_sha256_equal": (report.identity_projection_sha256_equal),
        "record_state_sha256_equal": report.record_state_sha256_equal,
        "second_emission_byte_stable": report.second_emission_byte_stable,
    }


@dataclass(frozen=True, slots=True, init=False, repr=False)
class MmcifNonpolyIdentityRoundTripReport:
    schema_id: str
    envelope_version: str
    profile_id: str
    input_full_source_sha256: str
    writer_receipt_sha256: str
    reemitted_writer_receipt_sha256: str
    input_identity_projection_sha256: str
    reparsed_identity_projection_sha256: str
    input_record_state_sha256: str
    reparsed_record_state_sha256: str
    emitted_source_sha256: str
    reemitted_source_sha256: str
    identity_projection_sha256_equal: bool
    record_state_sha256_equal: bool
    second_emission_byte_stable: bool
    report_sha256: str

    def __init__(
        self,
        *,
        schema_id: Any = None,
        envelope_version: Any = None,
        profile_id: Any = None,
        input_full_source_sha256: Any = None,
        writer_receipt_sha256: Any = None,
        reemitted_writer_receipt_sha256: Any = None,
        input_identity_projection_sha256: Any = None,
        reparsed_identity_projection_sha256: Any = None,
        input_record_state_sha256: Any = None,
        reparsed_record_state_sha256: Any = None,
        emitted_source_sha256: Any = None,
        reemitted_source_sha256: Any = None,
        identity_projection_sha256_equal: Any = None,
        record_state_sha256_equal: Any = None,
        second_emission_byte_stable: Any = None,
        report_sha256: Any = None,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise TypeError("MmcifNonpolyIdentityRoundTripReport is factory-only")
        for field_name, value in (
            ("schema_id", schema_id),
            ("envelope_version", envelope_version),
            ("profile_id", profile_id),
            ("input_full_source_sha256", input_full_source_sha256),
            ("writer_receipt_sha256", writer_receipt_sha256),
            ("reemitted_writer_receipt_sha256", reemitted_writer_receipt_sha256),
            ("input_identity_projection_sha256", input_identity_projection_sha256),
            (
                "reparsed_identity_projection_sha256",
                reparsed_identity_projection_sha256,
            ),
            ("input_record_state_sha256", input_record_state_sha256),
            ("reparsed_record_state_sha256", reparsed_record_state_sha256),
            ("emitted_source_sha256", emitted_source_sha256),
            ("reemitted_source_sha256", reemitted_source_sha256),
            ("identity_projection_sha256_equal", identity_projection_sha256_equal),
            ("record_state_sha256_equal", record_state_sha256_equal),
            ("second_emission_byte_stable", second_emission_byte_stable),
            ("report_sha256", report_sha256),
        ):
            object.__setattr__(self, field_name, value)
        self.__post_init__()

    def __post_init__(self) -> None:
        if self.schema_id != MMCIF_NONPOLY_IDENTITY_ROUND_TRIP_REPORT_SCHEMA_ID:
            raise ValueError("round-trip report schema is inconsistent")
        if self.envelope_version != MMCIF_NONPOLY_IDENTITY_ENVELOPE_VERSION:
            raise ValueError("round-trip report envelope version is inconsistent")
        if self.profile_id != MMCIF_NONPOLY_IDENTITY_PROFILE_ID:
            raise ValueError("round-trip report profile is inconsistent")
        for field_name in (
            "input_full_source_sha256",
            "writer_receipt_sha256",
            "reemitted_writer_receipt_sha256",
            "input_identity_projection_sha256",
            "reparsed_identity_projection_sha256",
            "input_record_state_sha256",
            "reparsed_record_state_sha256",
            "emitted_source_sha256",
            "reemitted_source_sha256",
            "report_sha256",
        ):
            _require_sha256(getattr(self, field_name), field_name=field_name)
        for field_name in (
            "identity_projection_sha256_equal",
            "record_state_sha256_equal",
            "second_emission_byte_stable",
        ):
            if type(getattr(self, field_name)) is not bool:
                raise TypeError(f"{field_name} must be boolean")
        if self.identity_projection_sha256_equal != (
            self.input_identity_projection_sha256
            == self.reparsed_identity_projection_sha256
        ):
            raise ValueError(
                "round-trip report identity projection invariant is inconsistent"
            )
        if self.record_state_sha256_equal != (
            self.input_record_state_sha256 == self.reparsed_record_state_sha256
        ):
            raise ValueError("round-trip report record-state invariant is inconsistent")
        if self.second_emission_byte_stable != (
            self.emitted_source_sha256 == self.reemitted_source_sha256
        ):
            raise ValueError(
                "round-trip report second-emission invariant is inconsistent"
            )
        if not all(
            (
                self.identity_projection_sha256_equal,
                self.record_state_sha256_equal,
                self.second_emission_byte_stable,
            )
        ):
            raise ValueError("round-trip report cannot attest a failed invariant")
        if self.report_sha256 != _sha256_document(_report_payload(self)):
            raise ValueError("round-trip report digest is inconsistent")

    def to_dict(self) -> dict[str, Any]:
        document = _report_payload(self)
        document["report_sha256"] = self.report_sha256
        document["source_identity_projection_preserved"] = True
        document.update(_authority_false_document())
        return document


def _make_report(
    *,
    source_ingest: MmcifNonpolyIdentityIngestResult,
    write_result: MmcifNonpolyIdentityWriteResult,
    reparsed_ingest: MmcifNonpolyIdentityIngestResult,
    reemitted_write_result: MmcifNonpolyIdentityWriteResult,
) -> MmcifNonpolyIdentityRoundTripReport:
    values: dict[str, Any] = {
        "schema_id": MMCIF_NONPOLY_IDENTITY_ROUND_TRIP_REPORT_SCHEMA_ID,
        "envelope_version": MMCIF_NONPOLY_IDENTITY_ENVELOPE_VERSION,
        "profile_id": MMCIF_NONPOLY_IDENTITY_PROFILE_ID,
        "input_full_source_sha256": source_ingest.full_source_sha256,
        "writer_receipt_sha256": write_result.receipt.receipt_sha256,
        "reemitted_writer_receipt_sha256": (
            reemitted_write_result.receipt.receipt_sha256
        ),
        "input_identity_projection_sha256": source_ingest.identity_projection_sha256,
        "reparsed_identity_projection_sha256": (
            reparsed_ingest.identity_projection_sha256
        ),
        "input_record_state_sha256": source_ingest.record_state_sha256,
        "reparsed_record_state_sha256": reparsed_ingest.record_state_sha256,
        "emitted_source_sha256": write_result.receipt.output_source_sha256,
        "reemitted_source_sha256": (
            reemitted_write_result.receipt.output_source_sha256
        ),
        "identity_projection_sha256_equal": (
            source_ingest.identity_projection_sha256
            == reparsed_ingest.identity_projection_sha256
        ),
        "record_state_sha256_equal": (
            source_ingest.record_state_sha256 == reparsed_ingest.record_state_sha256
        ),
        "second_emission_byte_stable": (
            write_result.payload == reemitted_write_result.payload
        ),
    }
    provisional = type("_ReportDocument", (), values)()
    values["report_sha256"] = _sha256_document(_report_payload(provisional))
    return MmcifNonpolyIdentityRoundTripReport(
        **values,
        _factory_token=_FACTORY_TOKEN,
    )


@dataclass(frozen=True, slots=True, init=False, repr=False)
class MmcifNonpolyIdentityRoundTripResult:
    source_ingest: MmcifNonpolyIdentityIngestResult
    write_result: MmcifNonpolyIdentityWriteResult
    reparsed_ingest: MmcifNonpolyIdentityIngestResult
    reemitted_write_result: MmcifNonpolyIdentityWriteResult
    report: MmcifNonpolyIdentityRoundTripReport

    def __init__(
        self,
        *,
        source_ingest: MmcifNonpolyIdentityIngestResult,
        write_result: MmcifNonpolyIdentityWriteResult,
        reparsed_ingest: MmcifNonpolyIdentityIngestResult,
        reemitted_write_result: MmcifNonpolyIdentityWriteResult,
        report: MmcifNonpolyIdentityRoundTripReport,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise TypeError("MmcifNonpolyIdentityRoundTripResult is factory-only")
        for field_name, value in (
            ("source_ingest", source_ingest),
            ("write_result", write_result),
            ("reparsed_ingest", reparsed_ingest),
            ("reemitted_write_result", reemitted_write_result),
            ("report", report),
        ):
            object.__setattr__(self, field_name, value)
        self.__post_init__()

    def __post_init__(self) -> None:
        try:
            self.source_ingest.__post_init__()
            self.reparsed_ingest.__post_init__()
            self.write_result.receipt.__post_init__()
            self.write_result.__post_init__()
            self.reemitted_write_result.receipt.__post_init__()
            self.reemitted_write_result.__post_init__()
            self.report.__post_init__()
            consistent = (
                self.write_result.receipt.input_full_source_sha256
                == self.source_ingest.full_source_sha256
                and self.write_result.receipt.input_normalized_base_source_sha256
                == self.source_ingest.normalized_base_source_sha256
                and self.write_result.receipt.input_canonical_base_source_sha256
                == self.source_ingest.canonical_base_source_sha256
                and self.write_result.receipt.input_base_system_snapshot_sha256
                == self.source_ingest.base_system_snapshot_sha256
                and self.write_result.receipt.input_base_topology_sha256
                == self.source_ingest.base_topology_sha256
                and self.write_result.receipt.input_base_representable_state_sha256
                == self.source_ingest.base_representable_state_sha256
                and self.write_result.receipt.input_identity_projection_sha256
                == self.source_ingest.identity_projection_sha256
                and self.write_result.receipt.receipt_sha256
                == self.report.writer_receipt_sha256
                and self.write_result.receipt.output_source_sha256
                == self.report.emitted_source_sha256
                and self.reparsed_ingest.full_source_sha256
                == self.report.emitted_source_sha256
                and self.reemitted_write_result.receipt.output_source_sha256
                == self.report.reemitted_source_sha256
                and self.reemitted_write_result.receipt.receipt_sha256
                == self.report.reemitted_writer_receipt_sha256
                and self.reemitted_write_result.receipt.input_full_source_sha256
                == self.reparsed_ingest.full_source_sha256
                and self.reemitted_write_result.receipt.input_identity_projection_sha256
                == self.reparsed_ingest.identity_projection_sha256
                and self.reemitted_write_result.receipt.input_record_state_sha256
                == self.reparsed_ingest.record_state_sha256
                and self.reemitted_write_result.receipt.input_base_system_snapshot_sha256
                == self.reparsed_ingest.base_system_snapshot_sha256
                and self.reemitted_write_result.receipt.input_base_topology_sha256
                == self.reparsed_ingest.base_topology_sha256
                and self.reemitted_write_result.receipt.input_base_representable_state_sha256
                == self.reparsed_ingest.base_representable_state_sha256
                and self.source_ingest.identity_projection_sha256
                == self.report.input_identity_projection_sha256
                and self.reparsed_ingest.identity_projection_sha256
                == self.report.reparsed_identity_projection_sha256
                and self.source_ingest.record_state_sha256
                == self.report.input_record_state_sha256
                and self.reparsed_ingest.record_state_sha256
                == self.report.reparsed_record_state_sha256
                and self.write_result.payload == self.reemitted_write_result.payload
                and self.report.identity_projection_sha256_equal
                == (
                    self.source_ingest.identity_projection_sha256
                    == self.reparsed_ingest.identity_projection_sha256
                )
                and self.report.record_state_sha256_equal
                == (
                    self.source_ingest.record_state_sha256
                    == self.reparsed_ingest.record_state_sha256
                )
                and self.report.second_emission_byte_stable
                == (self.write_result.payload == self.reemitted_write_result.payload)
            )
        except AttributeError as exc:
            raise TypeError("round-trip result contains an invalid artifact") from exc
        if not consistent:
            raise ValueError("round-trip artifacts are not cross-consistent")


def round_trip_mmcif_nonpoly_identity_source(
    data: bytes,
    *,
    source_id: str = "",
) -> MmcifNonpolyIdentityRoundTripResult:
    source_ingest = parse_mmcif_nonpoly_identity(data, source_id=source_id)
    write_result = write_mmcif_nonpoly_identity(source_ingest)
    reparsed_ingest = parse_mmcif_nonpoly_identity(
        write_result.payload,
        source_id=source_id,
    )
    reemitted_write_result = write_mmcif_nonpoly_identity(reparsed_ingest)
    report = _make_report(
        source_ingest=source_ingest,
        write_result=write_result,
        reparsed_ingest=reparsed_ingest,
        reemitted_write_result=reemitted_write_result,
    )
    return MmcifNonpolyIdentityRoundTripResult(
        source_ingest=source_ingest,
        write_result=write_result,
        reparsed_ingest=reparsed_ingest,
        reemitted_write_result=reemitted_write_result,
        report=report,
        _factory_token=_FACTORY_TOKEN,
    )
