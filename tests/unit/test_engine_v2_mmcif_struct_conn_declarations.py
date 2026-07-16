from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import stat

import pytest

import betelgeuze_engine_v2.molecular.mmcif_struct_conn_declarations as module
from betelgeuze_engine_v2.molecular.mmcif_nonpoly_component_declarations import (
    MMCIF_NONPOLY_COMPONENT_ATOM_HEADERS,
    MMCIF_NONPOLY_COMPONENT_BOND_HEADERS,
)
from betelgeuze_engine_v2.molecular.mmcif_struct_conn_declarations import (
    MMCIF_STRUCT_CONN_DECLARATION_DOCUMENT_SCHEMA_ID,
    MMCIF_STRUCT_CONN_DECLARATION_PROFILE_ID,
    MMCIF_STRUCT_CONN_HEADERS,
    MmcifStructConnDeclarationError,
    STRUCT_CONN_CATEGORY,
    mmcif_struct_conn_declaration_document,
    mmcif_struct_conn_declaration_json_bytes,
    parse_mmcif_struct_conn_declarations,
    require_mmcif_struct_conn_declaration_document,
    write_mmcif_struct_conn_declaration_json,
)


ENTITY_HEADERS = ("_entity.id", "_entity.type")
ASYM_HEADERS = ("_struct_asym.id", "_struct_asym.entity_id")
CHEM_COMP_HEADERS = (
    "_chem_comp.id",
    "_chem_comp.type",
    "_chem_comp.pdbx_formal_charge",
)
ENTITY_NONPOLY_HEADERS = (
    "_pdbx_entity_nonpoly.entity_id",
    "_pdbx_entity_nonpoly.name",
    "_pdbx_entity_nonpoly.comp_id",
)
SCHEME_HEADERS = (
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

ENTITY_ROWS = (
    {"_entity.id": "1", "_entity.type": "non-polymer"},
    {"_entity.id": "2", "_entity.type": "water"},
)
ASYM_ROWS = (
    {"_struct_asym.id": "L", "_struct_asym.entity_id": "1"},
    {"_struct_asym.id": "W", "_struct_asym.entity_id": "2"},
)
CHEM_COMP_ROWS = (
    {
        "_chem_comp.id": "LIG",
        "_chem_comp.type": "non-polymer",
        "_chem_comp.pdbx_formal_charge": "0",
    },
    {
        "_chem_comp.id": "HOH",
        "_chem_comp.type": "water",
        "_chem_comp.pdbx_formal_charge": "0",
    },
)
ENTITY_NONPOLY_ROWS = (
    {
        "_pdbx_entity_nonpoly.entity_id": "1",
        "_pdbx_entity_nonpoly.name": "'Opaque ligand source name'",
        "_pdbx_entity_nonpoly.comp_id": "LIG",
    },
    {
        "_pdbx_entity_nonpoly.entity_id": "2",
        "_pdbx_entity_nonpoly.name": "water",
        "_pdbx_entity_nonpoly.comp_id": "HOH",
    },
)
SCHEME_ROWS = (
    {
        "_pdbx_nonpoly_scheme.asym_id": "L",
        "_pdbx_nonpoly_scheme.entity_id": "1",
        "_pdbx_nonpoly_scheme.mon_id": "LIG",
        "_pdbx_nonpoly_scheme.ndb_seq_num": "1",
        "_pdbx_nonpoly_scheme.pdb_seq_num": "501",
        "_pdbx_nonpoly_scheme.auth_seq_num": "AUTH-L",
        "_pdbx_nonpoly_scheme.pdb_mon_id": "LIG",
        "_pdbx_nonpoly_scheme.auth_mon_id": "AUTHL",
        "_pdbx_nonpoly_scheme.pdb_strand_id": "LX",
        "_pdbx_nonpoly_scheme.pdb_ins_code": ".",
    },
    {
        "_pdbx_nonpoly_scheme.asym_id": "W",
        "_pdbx_nonpoly_scheme.entity_id": "2",
        "_pdbx_nonpoly_scheme.mon_id": "HOH",
        "_pdbx_nonpoly_scheme.ndb_seq_num": "1",
        "_pdbx_nonpoly_scheme.pdb_seq_num": "601",
        "_pdbx_nonpoly_scheme.auth_seq_num": "AUTH-W",
        "_pdbx_nonpoly_scheme.pdb_mon_id": "HOH",
        "_pdbx_nonpoly_scheme.auth_mon_id": "AUTHW",
        "_pdbx_nonpoly_scheme.pdb_strand_id": "WX",
        "_pdbx_nonpoly_scheme.pdb_ins_code": "?",
    },
)
ATOM_ROWS = (
    {
        "_chem_comp_atom.comp_id": "LIG",
        "_chem_comp_atom.atom_id": "C1",
        "_chem_comp_atom.type_symbol": "C",
        "_chem_comp_atom.charge": "0",
        "_chem_comp_atom.pdbx_aromatic_flag": "N",
        "_chem_comp_atom.pdbx_stereo_config": "N",
        "_chem_comp_atom.pdbx_ordinal": "1",
    },
    {
        "_chem_comp_atom.comp_id": "LIG",
        "_chem_comp_atom.atom_id": "O1",
        "_chem_comp_atom.type_symbol": "O",
        "_chem_comp_atom.charge": "0",
        "_chem_comp_atom.pdbx_aromatic_flag": "N",
        "_chem_comp_atom.pdbx_stereo_config": "N",
        "_chem_comp_atom.pdbx_ordinal": "2",
    },
    {
        "_chem_comp_atom.comp_id": "HOH",
        "_chem_comp_atom.atom_id": "O",
        "_chem_comp_atom.type_symbol": "O",
        "_chem_comp_atom.charge": "0",
        "_chem_comp_atom.pdbx_aromatic_flag": "N",
        "_chem_comp_atom.pdbx_stereo_config": "N",
        "_chem_comp_atom.pdbx_ordinal": "1",
    },
)
BOND_ROWS = (
    {
        "_chem_comp_bond.comp_id": "LIG",
        "_chem_comp_bond.atom_id_1": "C1",
        "_chem_comp_bond.atom_id_2": "O1",
        "_chem_comp_bond.value_order": "DOUB",
        "_chem_comp_bond.pdbx_aromatic_flag": "N",
        "_chem_comp_bond.pdbx_stereo_config": "N",
        "_chem_comp_bond.pdbx_ordinal": "1",
    },
)

STRUCT_CONN_ROWS = (
    {
        "_struct_conn.id": "conn-1",
        "_struct_conn.conn_type_id": "'covale'",
        "_struct_conn.ptnr1_label_asym_id": "L",
        "_struct_conn.ptnr1_label_comp_id": "LIG",
        "_struct_conn.ptnr1_label_seq_id": ".",
        "_struct_conn.ptnr1_label_atom_id": "C1",
        "_struct_conn.pdbx_ptnr1_label_alt_id": ".",
        "_struct_conn.pdbx_ptnr1_pdb_ins_code": ".",
        "_struct_conn.ptnr1_symmetry": "1_555",
        "_struct_conn.ptnr2_label_asym_id": "W",
        "_struct_conn.ptnr2_label_comp_id": "HOH",
        "_struct_conn.ptnr2_label_seq_id": "?",
        "_struct_conn.ptnr2_label_atom_id": "O",
        "_struct_conn.pdbx_ptnr2_label_alt_id": "?",
        "_struct_conn.pdbx_ptnr2_pdb_ins_code": "?",
        "_struct_conn.ptnr1_auth_asym_id": "LX",
        "_struct_conn.ptnr1_auth_comp_id": "AUTHL",
        "_struct_conn.ptnr1_auth_seq_id": "AUTH-L",
        "_struct_conn.ptnr2_auth_asym_id": "WX",
        "_struct_conn.ptnr2_auth_comp_id": "AUTHW",
        "_struct_conn.ptnr2_auth_seq_id": "AUTH-W",
        "_struct_conn.ptnr2_symmetry": "2_666",
        "_struct_conn.pdbx_value_order": "sing",
    },
    {
        "_struct_conn.id": "conn-2",
        "_struct_conn.conn_type_id": "metalc",
        "_struct_conn.ptnr1_label_asym_id": "W",
        "_struct_conn.ptnr1_label_comp_id": "HOH",
        "_struct_conn.ptnr1_label_seq_id": "?",
        "_struct_conn.ptnr1_label_atom_id": "O",
        "_struct_conn.pdbx_ptnr1_label_alt_id": "?",
        "_struct_conn.pdbx_ptnr1_pdb_ins_code": "?",
        "_struct_conn.ptnr1_symmetry": "?",
        "_struct_conn.ptnr2_label_asym_id": "L",
        "_struct_conn.ptnr2_label_comp_id": "LIG",
        "_struct_conn.ptnr2_label_seq_id": ".",
        "_struct_conn.ptnr2_label_atom_id": "O1",
        "_struct_conn.pdbx_ptnr2_label_alt_id": ".",
        "_struct_conn.pdbx_ptnr2_pdb_ins_code": ".",
        "_struct_conn.ptnr1_auth_asym_id": "WX",
        "_struct_conn.ptnr1_auth_comp_id": "AUTHW",
        "_struct_conn.ptnr1_auth_seq_id": "AUTH-W",
        "_struct_conn.ptnr2_auth_asym_id": "LX",
        "_struct_conn.ptnr2_auth_comp_id": "AUTHL",
        "_struct_conn.ptnr2_auth_seq_id": "AUTH-L",
        "_struct_conn.ptnr2_symmetry": "1_555",
        "_struct_conn.pdbx_value_order": "?",
    },
)

UNINTERPRETED_TAIL = """loop_
_atom_site.id
_atom_site.occupancy
1 0.50
#
_audit_conform.dict_name SOURCE_ONLY
"""


def _loop(headers: tuple[str, ...], rows: tuple[dict[str, str], ...]) -> str:
    assert rows
    lines = ["loop_", *headers]
    lines.extend(" ".join(row[header] for header in headers) for row in rows)
    lines.append("#")
    return "\n".join(lines) + "\n"


def _source(
    *,
    struct_rows: tuple[dict[str, str], ...] | None = STRUCT_CONN_ROWS,
    struct_headers: tuple[str, ...] = MMCIF_STRUCT_CONN_HEADERS,
    atom_rows: tuple[dict[str, str], ...] = ATOM_ROWS,
    tail: str = UNINTERPRETED_TAIL,
) -> str:
    source = (
        "data_struct_conn_declarations\n#\n"
        + _loop(ENTITY_HEADERS, ENTITY_ROWS)
        + _loop(ASYM_HEADERS, ASYM_ROWS)
        + _loop(CHEM_COMP_HEADERS, CHEM_COMP_ROWS)
        + _loop(ENTITY_NONPOLY_HEADERS, ENTITY_NONPOLY_ROWS)
        + _loop(SCHEME_HEADERS, SCHEME_ROWS)
        + _loop(MMCIF_NONPOLY_COMPONENT_ATOM_HEADERS, atom_rows)
        + _loop(MMCIF_NONPOLY_COMPONENT_BOND_HEADERS, BOND_ROWS)
    )
    if struct_rows is not None:
        source += _loop(struct_headers, struct_rows)
    return source + tail


def _updated(
    rows: tuple[dict[str, str], ...],
    row_index: int,
    field: str,
    value: str,
) -> tuple[dict[str, str], ...]:
    copied = [dict(row) for row in rows]
    copied[row_index][field] = value
    return tuple(copied)


def _error(source: str, code: str) -> MmcifStructConnDeclarationError:
    with pytest.raises(MmcifStructConnDeclarationError) as exc_info:
        parse_mmcif_struct_conn_declarations(source)
    assert exc_info.value.code == code
    return exc_info.value


def test_projection_preserves_rows_and_verifies_only_source_identity() -> None:
    source = _source()
    snapshot = parse_mmcif_struct_conn_declarations(source)

    assert snapshot.source_sha256 == hashlib.sha256(source.encode("ascii")).hexdigest()
    assert [row.connection_id for row in snapshot.declarations] == ["conn-1", "conn-2"]
    first = snapshot.declarations[0]
    assert first.connection_type.state == "known"
    assert first.connection_type.value == "covale"
    assert first.connection_type.quoted is True
    assert first.partner_1.label_seq_id.state == "not_applicable"
    assert first.partner_2.label_seq_id.state == "unknown"
    assert first.partner_2.symmetry.value == "2_666"
    assert first.value_order.value == "sing"
    assert len(first.partner_1.instance_identity_sha256) == 64
    assert len(first.partner_2.instance_identity_sha256) == 64
    assert snapshot.uninterpreted_categories == ("_atom_site", "_audit_conform")

    binding = snapshot.category_binding
    assert binding.category == STRUCT_CONN_CATEGORY
    assert binding.row_count == 2
    assert binding.interpreted_headers == _expected_interpreted_headers(
        MMCIF_STRUCT_CONN_HEADERS
    )
    assert binding.uninterpreted_headers == (
        "_struct_conn.conn_type_id",
        "_struct_conn.ptnr1_symmetry",
        "_struct_conn.ptnr2_symmetry",
        "_struct_conn.pdbx_value_order",
    )

    payload = snapshot.to_dict()
    for flag in (
        "source_struct_conn_declarations_preserved",
        "connection_identity_references_verified",
        "partner_nonpoly_instance_references_verified",
        "partner_component_atom_references_verified",
        "source_row_order_preserved",
        "source_category_headers_bound",
    ):
        assert payload[flag] is True
    for flag in (
        "source_authenticated",
        "atom_site_identity_joined",
        "coordinates_interpreted",
        "label_auth_semantic_equivalence_interpreted",
        "connection_type_interpreted",
        "symmetry_interpreted",
        "bond_order_interpreted",
        "covalence_interpreted",
        "coordination_interpreted",
        "bond_topology_interpreted",
        "component_chemistry_interpreted",
        "preparation_ready",
        "parameterability_assessed",
        "physics_supported",
        "runtime_eligible",
        "scientifically_validated",
        "benchmark_validated",
        "product_qualified",
        "customer_execution_enabled",
        "claim_safe",
    ):
        assert payload[flag] is False


def _expected_interpreted_headers(headers: tuple[str, ...]) -> tuple[str, ...]:
    uninterpreted = {
        "_struct_conn.conn_type_id",
        "_struct_conn.ptnr1_symmetry",
        "_struct_conn.ptnr2_symmetry",
        "_struct_conn.pdbx_value_order",
    }
    return tuple(header for header in headers if header not in uninterpreted)


def test_header_order_changes_binding_not_projection() -> None:
    canonical = parse_mmcif_struct_conn_declarations(_source())
    reordered = parse_mmcif_struct_conn_declarations(
        _source(struct_headers=tuple(reversed(MMCIF_STRUCT_CONN_HEADERS)))
    )

    assert canonical.declaration_projection_sha256 == reordered.declaration_projection_sha256
    assert canonical.source_binding_sha256 != reordered.source_binding_sha256
    assert canonical.snapshot_sha256 != reordered.snapshot_sha256


def test_source_token_and_row_order_are_bound() -> None:
    changed = parse_mmcif_struct_conn_declarations(
        _source(
            struct_rows=_updated(
                STRUCT_CONN_ROWS,
                0,
                "_struct_conn.conn_type_id",
                "hydrog",
            )
        )
    )
    reordered = parse_mmcif_struct_conn_declarations(
        _source(struct_rows=tuple(reversed(STRUCT_CONN_ROWS)))
    )
    canonical = parse_mmcif_struct_conn_declarations(_source())

    assert canonical.declaration_projection_sha256 != changed.declaration_projection_sha256
    assert [row.connection_id for row in reordered.declarations] == ["conn-2", "conn-1"]
    assert canonical.declaration_projection_sha256 != reordered.declaration_projection_sha256


def test_document_is_canonical_self_verifying_and_written_private(tmp_path: Path) -> None:
    snapshot = parse_mmcif_struct_conn_declarations(_source())
    document = mmcif_struct_conn_declaration_document(snapshot)

    assert document["schema_id"] == MMCIF_STRUCT_CONN_DECLARATION_DOCUMENT_SCHEMA_ID
    assert document["profile_id"] == MMCIF_STRUCT_CONN_DECLARATION_PROFILE_ID
    assert require_mmcif_struct_conn_declaration_document(document) == document
    encoded = mmcif_struct_conn_declaration_json_bytes(snapshot)
    assert json.loads(encoded) == document

    destination = write_mmcif_struct_conn_declaration_json(
        tmp_path / "struct-conn-declarations.json",
        snapshot,
    )
    assert destination.read_bytes() == encoded + b"\n"
    assert stat.S_IMODE(destination.stat().st_mode) == 0o600
    assert not list(tmp_path.glob(".struct-conn-declarations.json.*.tmp"))

    tampered = deepcopy(document)
    tampered["declaration_projection"]["declarations"][0]["connection_id"] = "PRIVATE"
    with pytest.raises(ValueError, match="projection digest mismatch"):
        require_mmcif_struct_conn_declaration_document(tampered)


def test_missing_scalar_mixed_and_header_surfaces_fail_closed() -> None:
    _error(_source(struct_rows=None), "required_category_missing")

    scalar = _source(struct_rows=None) + "_struct_conn.id conn-1\n"
    _error(scalar, "category_must_be_loop")

    mixed_headers = MMCIF_STRUCT_CONN_HEADERS + ("_custom.value",)
    mixed_rows = tuple({**row, "_custom.value": "x"} for row in STRUCT_CONN_ROWS)
    _error(
        _source(struct_rows=mixed_rows, struct_headers=mixed_headers),
        "mixed_category_loop",
    )

    missing_header = tuple(
        header for header in MMCIF_STRUCT_CONN_HEADERS if header != "_struct_conn.pdbx_value_order"
    )
    _error(_source(struct_headers=missing_header), "unsupported_headers")


@pytest.mark.parametrize(
    ("field", "value", "code"),
    (
        (
            "_struct_conn.ptnr1_label_asym_id",
            "PRIVATE-ASYM",
            "partner_instance_identity_join_failed",
        ),
        (
            "_struct_conn.ptnr1_auth_comp_id",
            "PRIVATE-COMP",
            "partner_instance_identity_join_failed",
        ),
        (
            "_struct_conn.pdbx_ptnr1_pdb_ins_code",
            "?",
            "partner_instance_identity_join_failed",
        ),
        (
            "_struct_conn.ptnr1_label_atom_id",
            "PRIVATE-ATOM",
            "partner_component_atom_identity_missing",
        ),
    ),
)
def test_partner_instance_and_component_atom_joins_fail_closed(
    field: str,
    value: str,
    code: str,
) -> None:
    rows = _updated(STRUCT_CONN_ROWS, 0, field, value)
    _error(_source(struct_rows=rows), code)


def test_duplicate_connection_id_and_nonblank_partner_markers_are_rejected() -> None:
    duplicate = dict(STRUCT_CONN_ROWS[1])
    duplicate["_struct_conn.id"] = "conn-1"
    _error(_source(struct_rows=(STRUCT_CONN_ROWS[0], duplicate)), "duplicate_connection_id")

    known_seq = _updated(
        STRUCT_CONN_ROWS,
        0,
        "_struct_conn.ptnr1_label_seq_id",
        "501",
    )
    _error(_source(struct_rows=known_seq), "nonblank_partner_marker_not_supported")

    known_alt = _updated(
        STRUCT_CONN_ROWS,
        0,
        "_struct_conn.pdbx_ptnr1_label_alt_id",
        "A",
    )
    _error(_source(struct_rows=known_alt), "nonblank_partner_marker_not_supported")


def test_identity_token_row_and_source_token_bounds_are_enforced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    quoted_id = _updated(STRUCT_CONN_ROWS, 0, "_struct_conn.id", "'conn-1'")
    _error(_source(struct_rows=quoted_id), "invalid_identity_token")

    oversized = _updated(
        STRUCT_CONN_ROWS,
        0,
        "_struct_conn.conn_type_id",
        "'" + ("X" * 257) + "'",
    )
    _error(_source(struct_rows=oversized), "source_token_out_of_bounds")

    monkeypatch.setattr(module, "MAX_MMCIF_STRUCT_CONN_DECLARATION_ROWS", 1)
    _error(_source(), "too_many_declaration_rows")


def test_errors_do_not_echo_private_identity_values() -> None:
    private = _updated(
        STRUCT_CONN_ROWS,
        0,
        "_struct_conn.ptnr1_auth_seq_id",
        "PRIVATE-SEQUENCE-IDENTITY",
    )
    error = _error(_source(struct_rows=private), "partner_instance_identity_join_failed")

    assert "PRIVATE-SEQUENCE-IDENTITY" not in str(error)
    assert "PRIVATE-SEQUENCE-IDENTITY" not in error.detail


def test_input_type_is_strict() -> None:
    with pytest.raises(TypeError, match="must be a string"):
        parse_mmcif_struct_conn_declarations(b"data_x")  # type: ignore[arg-type]
