from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import stat

import pytest

from betelgeuze_engine_v2.molecular.mmcif_nonpoly_identity import (
    CHEM_COMP_CATEGORY,
    ENTITY_CATEGORY,
    ENTITY_NONPOLY_CATEGORY,
    MMCIF_NONPOLY_IDENTITY_DOCUMENT_SCHEMA_ID,
    MMCIF_NONPOLY_IDENTITY_PROFILE_ID,
    MMCIF_NONPOLY_IDENTITY_SCHEME_HEADERS,
    MmcifNonpolyIdentityError,
    NONPOLY_SCHEME_CATEGORY,
    STRUCT_ASYM_CATEGORY,
    mmcif_nonpoly_identity_document,
    mmcif_nonpoly_identity_json_bytes,
    parse_mmcif_nonpoly_identity,
    require_mmcif_nonpoly_identity_document,
    write_mmcif_nonpoly_identity_json,
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
SCHEME_HEADERS = MMCIF_NONPOLY_IDENTITY_SCHEME_HEADERS


def _loop(
    headers: tuple[str, ...],
    rows: tuple[dict[str, str], ...],
) -> str:
    lines = ["loop_", *headers]
    lines.extend(" ".join(row[header] for header in headers) for row in rows)
    lines.append("#")
    return "\n".join(lines) + "\n"


def _source(
    *,
    entity_rows: tuple[dict[str, str], ...],
    asym_rows: tuple[dict[str, str], ...],
    component_rows: tuple[dict[str, str], ...],
    entity_nonpoly_rows: tuple[dict[str, str], ...],
    scheme_rows: tuple[dict[str, str], ...],
    entity_headers: tuple[str, ...] = ENTITY_HEADERS,
    asym_headers: tuple[str, ...] = ASYM_HEADERS,
    component_headers: tuple[str, ...] = CHEM_COMP_HEADERS,
    entity_nonpoly_headers: tuple[str, ...] = ENTITY_NONPOLY_HEADERS,
    scheme_headers: tuple[str, ...] = SCHEME_HEADERS,
    tail: str = "",
) -> str:
    return (
        "data_nonpoly\n#\n"
        + _loop(entity_headers, entity_rows)
        + _loop(asym_headers, asym_rows)
        + _loop(component_headers, component_rows)
        + _loop(entity_nonpoly_headers, entity_nonpoly_rows)
        + _loop(scheme_headers, scheme_rows)
        + tail
    )


PURE_ENTITY_ROWS = ({"_entity.id": "1", "_entity.type": "non-polymer"},)
PURE_ASYM_ROWS = ({"_struct_asym.id": "L", "_struct_asym.entity_id": "1"},)
PURE_COMPONENT_ROWS = (
    {
        "_chem_comp.id": "HEM",
        "_chem_comp.type": "non-polymer",
        "_chem_comp.pdbx_formal_charge": "+2",
    },
)
PURE_ENTITY_NONPOLY_ROWS = (
    {
        "_pdbx_entity_nonpoly.entity_id": "1",
        "_pdbx_entity_nonpoly.name": "'Heme cofactor alpha'",
        "_pdbx_entity_nonpoly.comp_id": "HEM",
    },
)
PURE_SCHEME_ROWS = (
    {
        "_pdbx_nonpoly_scheme.asym_id": "L",
        "_pdbx_nonpoly_scheme.entity_id": "1",
        "_pdbx_nonpoly_scheme.mon_id": "HEM",
        "_pdbx_nonpoly_scheme.ndb_seq_num": "2",
        "_pdbx_nonpoly_scheme.pdb_seq_num": "501",
        "_pdbx_nonpoly_scheme.auth_seq_num": "AUTH-B",
        "_pdbx_nonpoly_scheme.pdb_mon_id": "PHEM",
        "_pdbx_nonpoly_scheme.auth_mon_id": "AHEM",
        "_pdbx_nonpoly_scheme.pdb_strand_id": "AUTHZ",
        "_pdbx_nonpoly_scheme.pdb_ins_code": "?",
    },
    {
        "_pdbx_nonpoly_scheme.asym_id": "L",
        "_pdbx_nonpoly_scheme.entity_id": "1",
        "_pdbx_nonpoly_scheme.mon_id": "HEM",
        "_pdbx_nonpoly_scheme.ndb_seq_num": "1",
        "_pdbx_nonpoly_scheme.pdb_seq_num": "500",
        "_pdbx_nonpoly_scheme.auth_seq_num": "AUTH-A",
        "_pdbx_nonpoly_scheme.pdb_mon_id": "PHEM-A",
        "_pdbx_nonpoly_scheme.auth_mon_id": "AHEM-A",
        "_pdbx_nonpoly_scheme.pdb_strand_id": "AUTHZ",
        "_pdbx_nonpoly_scheme.pdb_ins_code": ".",
    },
)

UNINTERPRETED_ATOM_SITE = """loop_
_atom_site.id
_atom_site.auth_seq_id
1 PRIVATE-A
#
_audit_conform.dict_name SOURCE_ONLY
"""


def _pure_source(
    *,
    component_rows: tuple[dict[str, str], ...] = PURE_COMPONENT_ROWS,
    entity_nonpoly_rows: tuple[dict[str, str], ...] = PURE_ENTITY_NONPOLY_ROWS,
    scheme_rows: tuple[dict[str, str], ...] = PURE_SCHEME_ROWS,
    component_headers: tuple[str, ...] = CHEM_COMP_HEADERS,
    entity_nonpoly_headers: tuple[str, ...] = ENTITY_NONPOLY_HEADERS,
    scheme_headers: tuple[str, ...] = SCHEME_HEADERS,
    tail: str = UNINTERPRETED_ATOM_SITE,
) -> str:
    return _source(
        entity_rows=PURE_ENTITY_ROWS,
        asym_rows=PURE_ASYM_ROWS,
        component_rows=component_rows,
        entity_nonpoly_rows=entity_nonpoly_rows,
        scheme_rows=scheme_rows,
        component_headers=component_headers,
        entity_nonpoly_headers=entity_nonpoly_headers,
        scheme_headers=scheme_headers,
        tail=tail,
    )


MIXED_ENTITY_ROWS = (
    {"_entity.id": "1", "_entity.type": "polymer"},
    {"_entity.id": "2", "_entity.type": "non-polymer"},
    {"_entity.id": "3", "_entity.type": "water"},
)
MIXED_ASYM_ROWS = (
    {"_struct_asym.id": "A", "_struct_asym.entity_id": "1"},
    {"_struct_asym.id": "L", "_struct_asym.entity_id": "2"},
    {"_struct_asym.id": "W", "_struct_asym.entity_id": "3"},
)
MIXED_COMPONENT_ROWS = (
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
MIXED_ENTITY_NONPOLY_ROWS = (
    {
        "_pdbx_entity_nonpoly.entity_id": "2",
        "_pdbx_entity_nonpoly.name": "'Opaque compound identity'",
        "_pdbx_entity_nonpoly.comp_id": "LIG",
    },
    {
        "_pdbx_entity_nonpoly.entity_id": "3",
        "_pdbx_entity_nonpoly.name": "water",
        "_pdbx_entity_nonpoly.comp_id": "HOH",
    },
)
MIXED_SCHEME_ROWS = (
    {
        "_pdbx_nonpoly_scheme.asym_id": "L",
        "_pdbx_nonpoly_scheme.entity_id": "2",
        "_pdbx_nonpoly_scheme.mon_id": "LIG",
        "_pdbx_nonpoly_scheme.ndb_seq_num": "1",
        "_pdbx_nonpoly_scheme.pdb_seq_num": "10",
        "_pdbx_nonpoly_scheme.auth_seq_num": "AUTH-L",
        "_pdbx_nonpoly_scheme.pdb_mon_id": "LIG",
        "_pdbx_nonpoly_scheme.auth_mon_id": "AUTHL",
        "_pdbx_nonpoly_scheme.pdb_strand_id": "LX",
        "_pdbx_nonpoly_scheme.pdb_ins_code": ".",
    },
    {
        "_pdbx_nonpoly_scheme.asym_id": "W",
        "_pdbx_nonpoly_scheme.entity_id": "3",
        "_pdbx_nonpoly_scheme.mon_id": "HOH",
        "_pdbx_nonpoly_scheme.ndb_seq_num": "1",
        "_pdbx_nonpoly_scheme.pdb_seq_num": "20",
        "_pdbx_nonpoly_scheme.auth_seq_num": "AUTH-W",
        "_pdbx_nonpoly_scheme.pdb_mon_id": "WAT",
        "_pdbx_nonpoly_scheme.auth_mon_id": "AUTHW",
        "_pdbx_nonpoly_scheme.pdb_strand_id": "WX",
        "_pdbx_nonpoly_scheme.pdb_ins_code": "?",
    },
)


def _mixed_source() -> str:
    return _source(
        entity_rows=MIXED_ENTITY_ROWS,
        asym_rows=MIXED_ASYM_ROWS,
        component_rows=MIXED_COMPONENT_ROWS,
        entity_nonpoly_rows=MIXED_ENTITY_NONPOLY_ROWS,
        scheme_rows=MIXED_SCHEME_ROWS,
        tail="_entry.id MIXED\n",
    )


def _updated(
    rows: tuple[dict[str, str], ...],
    row_index: int,
    field: str,
    value: str,
) -> tuple[dict[str, str], ...]:
    copied = [dict(row) for row in rows]
    copied[row_index][field] = value
    return tuple(copied)


def _error(source: str, code: str) -> MmcifNonpolyIdentityError:
    with pytest.raises(MmcifNonpolyIdentityError) as exc_info:
        parse_mmcif_nonpoly_identity(source)
    assert exc_info.value.code == code
    return exc_info.value


def test_pure_nonpoly_source_preserves_opaque_identity_without_atom_site_parsing() -> None:
    source = _pure_source()
    snapshot = parse_mmcif_nonpoly_identity(source)

    assert snapshot.source_sha256 == hashlib.sha256(source.encode("ascii")).hexdigest()
    assert snapshot.block_name == "nonpoly"
    assert [row.comp_id for row in snapshot.components] == ["HEM"]
    assert [(row.entity_id, row.entity_type, row.comp_id) for row in snapshot.entities] == [
        ("1", "non-polymer", "HEM")
    ]
    entity = snapshot.entities[0]
    assert entity.name is not None
    assert entity.name.to_dict() == {
        "state": "known",
        "value": "Heme cofactor alpha",
        "quoted": True,
    }
    assert [row.ndb_seq_num for row in snapshot.instances] == ["2", "1"]
    assert snapshot.instances[0].pdb_ins_code.state == "unknown"
    assert snapshot.instances[1].pdb_ins_code.state == "not_applicable"
    assert snapshot.uninterpreted_categories == ("_atom_site", "_audit_conform")
    assert "Heme cofactor alpha" not in repr(entity)
    assert "AUTH-B" not in repr(snapshot.instances[0])
    assert "PHEM" not in repr(snapshot.instances[0])
    assert "PRIVATE-A" not in repr(snapshot)

    bindings = {row.category: row for row in snapshot.category_bindings}
    chem_comp = bindings[CHEM_COMP_CATEGORY]
    assert chem_comp.interpreted_headers == ("_chem_comp.id",)
    assert chem_comp.uninterpreted_headers == (
        "_chem_comp.type",
        "_chem_comp.pdbx_formal_charge",
    )
    assert bindings[ENTITY_CATEGORY].source_ordinal == 0
    assert bindings[STRUCT_ASYM_CATEGORY].source_ordinal == 1
    assert bindings[ENTITY_NONPOLY_CATEGORY].source_ordinal == 3
    assert bindings[NONPOLY_SCHEME_CATEGORY].source_ordinal == 4

    payload = snapshot.to_dict()
    assert payload["source_component_ids_preserved"] is True
    assert payload["source_nonpoly_entity_identity_preserved"] is True
    assert payload["source_nonpoly_instance_aliases_preserved"] is True
    assert payload["entity_asym_component_joins_verified"] is True
    for flag in (
        "source_authenticated",
        "atom_site_identity_joined",
        "atom_site_coordinates_interpreted",
        "chem_comp_type_interpreted",
        "formal_charge_interpreted",
        "auth_label_equivalence_inferred",
        "component_chemistry_interpreted",
        "role_assignment_interpreted",
        "bond_topology_interpreted",
        "bond_order_interpreted",
        "coordination_interpreted",
        "charge_interpreted",
        "protonation_interpreted",
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


def test_mixed_polymer_nonpoly_and_water_cover_only_selected_entity_types() -> None:
    snapshot = parse_mmcif_nonpoly_identity(_mixed_source())

    assert [(row.entity_id, row.entity_type, row.comp_id) for row in snapshot.entities] == [
        ("2", "non-polymer", "LIG"),
        ("3", "water", "HOH"),
    ]
    assert [row.asym_id for row in snapshot.instances] == ["L", "W"]
    assert [row.entity_type for row in snapshot.instances] == ["non-polymer", "water"]
    assert snapshot.to_dict()["entity_type_counts"] == {
        "non-polymer": 1,
        "water": 1,
    }
    assert snapshot.uninterpreted_categories == ("_entry",)


def test_header_order_and_uninterpreted_values_change_only_source_binding() -> None:
    canonical = parse_mmcif_nonpoly_identity(_pure_source(tail=""))
    reordered = parse_mmcif_nonpoly_identity(
        _pure_source(
            component_headers=tuple(reversed(CHEM_COMP_HEADERS)),
            entity_nonpoly_headers=tuple(reversed(ENTITY_NONPOLY_HEADERS)),
            scheme_headers=tuple(reversed(SCHEME_HEADERS)),
            tail="",
        )
    )
    changed_uninterpreted = parse_mmcif_nonpoly_identity(
        _pure_source(
            component_rows=_updated(
                _updated(
                    PURE_COMPONENT_ROWS,
                    0,
                    "_chem_comp.type",
                    "PRIVATE-TYPE",
                ),
                0,
                "_chem_comp.pdbx_formal_charge",
                "999",
            ),
            tail="",
        )
    )

    assert canonical.identity_projection_sha256 == reordered.identity_projection_sha256
    assert canonical.identity_projection_sha256 == changed_uninterpreted.identity_projection_sha256
    assert canonical.source_binding_sha256 != reordered.source_binding_sha256
    assert canonical.source_binding_sha256 != changed_uninterpreted.source_binding_sha256


def test_uninterpreted_atom_site_changes_do_not_change_identity_projection() -> None:
    first = parse_mmcif_nonpoly_identity(
        _pure_source(
            tail="""loop_
_atom_site.id
_atom_site.auth_seq_id
1 PRIVATE-A
#
"""
        )
    )
    second = parse_mmcif_nonpoly_identity(
        _pure_source(
            tail="""loop_
_atom_site.id
_atom_site.auth_seq_id
999 PRIVATE-B
#
"""
        )
    )

    assert first.identity_projection_sha256 == second.identity_projection_sha256
    assert first.source_binding_sha256 != second.source_binding_sha256


def test_source_scheme_row_order_is_preserved_and_projection_significant() -> None:
    canonical = parse_mmcif_nonpoly_identity(_pure_source(tail=""))
    reordered = parse_mmcif_nonpoly_identity(
        _pure_source(scheme_rows=tuple(reversed(PURE_SCHEME_ROWS)), tail="")
    )

    assert [row.ndb_seq_num for row in canonical.instances] == ["2", "1"]
    assert [row.ndb_seq_num for row in reordered.instances] == ["1", "2"]
    assert canonical.identity_projection_sha256 != reordered.identity_projection_sha256


def test_name_markers_remain_distinct_source_values() -> None:
    dot = parse_mmcif_nonpoly_identity(
        _pure_source(
            entity_nonpoly_rows=_updated(
                PURE_ENTITY_NONPOLY_ROWS,
                0,
                "_pdbx_entity_nonpoly.name",
                ".",
            ),
            tail="",
        )
    )
    question = parse_mmcif_nonpoly_identity(
        _pure_source(
            entity_nonpoly_rows=_updated(
                PURE_ENTITY_NONPOLY_ROWS,
                0,
                "_pdbx_entity_nonpoly.name",
                "?",
            ),
            tail="",
        )
    )

    assert dot.entities[0].name is not None
    assert dot.entities[0].name.state == "not_applicable"
    assert question.entities[0].name is not None
    assert question.entities[0].name.state == "unknown"
    assert dot.identity_projection_sha256 != question.identity_projection_sha256


def test_document_is_canonical_self_verifying_and_written_private(tmp_path: Path) -> None:
    snapshot = parse_mmcif_nonpoly_identity(_pure_source())
    document = mmcif_nonpoly_identity_document(snapshot)

    assert document["schema_id"] == MMCIF_NONPOLY_IDENTITY_DOCUMENT_SCHEMA_ID
    assert document["profile_id"] == MMCIF_NONPOLY_IDENTITY_PROFILE_ID
    assert require_mmcif_nonpoly_identity_document(document) == document
    encoded = mmcif_nonpoly_identity_json_bytes(snapshot)
    assert json.loads(encoded) == document

    destination = write_mmcif_nonpoly_identity_json(tmp_path / "nonpoly.json", snapshot)
    assert destination.read_bytes() == encoded + b"\n"
    assert stat.S_IMODE(destination.stat().st_mode) == 0o600
    assert not list(tmp_path.glob(".nonpoly.json.*.tmp"))

    tampered = deepcopy(document)
    tampered["identity_projection"]["instances"][0]["auth_seq_num"] = "PRIVATE"
    with pytest.raises(ValueError, match="projection digest mismatch"):
        require_mmcif_nonpoly_identity_document(tampered)


@pytest.mark.parametrize(
    ("source", "code"),
    [
        (
            "data_missing\n"
            + _loop(ENTITY_HEADERS, PURE_ENTITY_ROWS)
            + _loop(ASYM_HEADERS, PURE_ASYM_ROWS)
            + _loop(ENTITY_NONPOLY_HEADERS, PURE_ENTITY_NONPOLY_ROWS)
            + _loop(SCHEME_HEADERS, PURE_SCHEME_ROWS),
            "required_category_missing",
        ),
        (
            "data_scalar\n"
            "_entity.id 1\n"
            "_entity.type non-polymer\n"
            + _loop(ASYM_HEADERS, PURE_ASYM_ROWS)
            + _loop(CHEM_COMP_HEADERS, PURE_COMPONENT_ROWS)
            + _loop(ENTITY_NONPOLY_HEADERS, PURE_ENTITY_NONPOLY_ROWS)
            + _loop(SCHEME_HEADERS, PURE_SCHEME_ROWS),
            "category_must_be_loop",
        ),
        (
            _pure_source(
                entity_nonpoly_headers=(
                    "_pdbx_entity_nonpoly.entity_id",
                    "_audit_author.name",
                    "_pdbx_entity_nonpoly.comp_id",
                ),
                entity_nonpoly_rows=(
                    {
                        "_pdbx_entity_nonpoly.entity_id": "1",
                        "_audit_author.name": "AUTHOR",
                        "_pdbx_entity_nonpoly.comp_id": "HEM",
                    },
                ),
                tail="",
            ),
            "mixed_category_loop",
        ),
        (
            _pure_source(
                scheme_headers=tuple(
                    header
                    for header in SCHEME_HEADERS
                    if header != "_pdbx_nonpoly_scheme.auth_seq_num"
                ),
                tail="",
            ),
            "required_header_missing",
        ),
    ],
)
def test_selected_category_surface_failures_are_explicit(source: str, code: str) -> None:
    _error(source, code)


def test_entity_component_and_scheme_coverage_fail_closed() -> None:
    duplicate_entity_nonpoly = PURE_ENTITY_NONPOLY_ROWS + PURE_ENTITY_NONPOLY_ROWS
    _error(
        _pure_source(entity_nonpoly_rows=duplicate_entity_nonpoly, tail=""),
        "duplicate_nonpoly_entity_id",
    )

    _error(
        _source(
            entity_rows=MIXED_ENTITY_ROWS,
            asym_rows=MIXED_ASYM_ROWS,
            component_rows=MIXED_COMPONENT_ROWS,
            entity_nonpoly_rows=(MIXED_ENTITY_NONPOLY_ROWS[0],),
            scheme_rows=(MIXED_SCHEME_ROWS[0],),
        ),
        "nonpoly_entity_coverage_mismatch",
    )

    extra_component = PURE_COMPONENT_ROWS + (
        {
            "_chem_comp.id": "EXTRA",
            "_chem_comp.type": "non-polymer",
            "_chem_comp.pdbx_formal_charge": "0",
        },
    )
    _error(
        _pure_source(component_rows=extra_component, tail=""),
        "component_coverage_mismatch",
    )

    missing_component = _updated(
        PURE_ENTITY_NONPOLY_ROWS,
        0,
        "_pdbx_entity_nonpoly.comp_id",
        "PRIVATE",
    )
    error = _error(
        _pure_source(entity_nonpoly_rows=missing_component, tail=""),
        "component_reference_missing",
    )
    assert "PRIVATE" not in str(error)

    bad_join = _updated(
        PURE_SCHEME_ROWS,
        0,
        "_pdbx_nonpoly_scheme.entity_id",
        "2",
    )
    _error(
        _pure_source(scheme_rows=bad_join, tail=""),
        "nonpoly_scheme_join_mismatch",
    )

    bad_component = _updated(
        PURE_SCHEME_ROWS,
        0,
        "_pdbx_nonpoly_scheme.mon_id",
        "PRIVATE",
    )
    error = _error(
        _pure_source(scheme_rows=bad_component, tail=""),
        "nonpoly_component_join_mismatch",
    )
    assert "PRIVATE" not in str(error)

    duplicate_key = _updated(
        PURE_SCHEME_ROWS,
        1,
        "_pdbx_nonpoly_scheme.ndb_seq_num",
        "2",
    )
    _error(
        _pure_source(scheme_rows=duplicate_key, tail=""),
        "duplicate_nonpoly_scheme_key",
    )

    _error(
        _source(
            entity_rows=MIXED_ENTITY_ROWS,
            asym_rows=MIXED_ASYM_ROWS,
            component_rows=MIXED_COMPONENT_ROWS,
            entity_nonpoly_rows=MIXED_ENTITY_NONPOLY_ROWS,
            scheme_rows=(MIXED_SCHEME_ROWS[0],),
        ),
        "nonpoly_scheme_coverage_mismatch",
    )


def test_invalid_opaque_tokens_fail_without_echo() -> None:
    quoted_alias = _updated(
        PURE_SCHEME_ROWS,
        0,
        "_pdbx_nonpoly_scheme.auth_seq_num",
        "'PRIVATE-AUTH'",
    )
    error = _error(
        _pure_source(scheme_rows=quoted_alias, tail=""),
        "invalid_identity_token",
    )
    assert "PRIVATE-AUTH" not in str(error)
    assert "PRIVATE-AUTH" not in repr(error)

    multiline_source = _pure_source(
        entity_nonpoly_rows=(
            {
                "_pdbx_entity_nonpoly.entity_id": "1",
                "_pdbx_entity_nonpoly.name": "\n;PRIVATE-NAME\nSECOND-LINE\n;",
                "_pdbx_entity_nonpoly.comp_id": "HEM",
            },
        ),
        tail="",
    )
    error = _error(multiline_source, "multiline_value_not_supported")
    assert "PRIVATE-NAME" not in str(error)
    assert "SECOND-LINE" not in repr(error)


def test_nonpoly_entity_requires_struct_asym_carrier() -> None:
    _error(
        _source(
            entity_rows=PURE_ENTITY_ROWS,
            asym_rows=({"_struct_asym.id": "P", "_struct_asym.entity_id": "9"},),
            component_rows=PURE_COMPONENT_ROWS,
            entity_nonpoly_rows=PURE_ENTITY_NONPOLY_ROWS,
            scheme_rows=PURE_SCHEME_ROWS,
            tail="",
        ),
        "struct_asym_entity_reference_missing",
    )

    entity_rows = PURE_ENTITY_ROWS + ({"_entity.id": "9", "_entity.type": "polymer"},)
    _error(
        _source(
            entity_rows=entity_rows,
            asym_rows=({"_struct_asym.id": "P", "_struct_asym.entity_id": "9"},),
            component_rows=PURE_COMPONENT_ROWS,
            entity_nonpoly_rows=PURE_ENTITY_NONPOLY_ROWS,
            scheme_rows=PURE_SCHEME_ROWS,
            tail="",
        ),
        "nonpoly_asym_coverage_mismatch",
    )


def test_input_type_is_strict() -> None:
    with pytest.raises(TypeError, match="must be a string"):
        parse_mmcif_nonpoly_identity(b"data_nonpoly")  # type: ignore[arg-type]
