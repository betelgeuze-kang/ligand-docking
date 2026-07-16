from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import stat

import pytest

from betelgeuze_engine_v2.molecular.mmcif_altloc_declarations import (
    MMCIF_ALTLOC_DECLARATION_DOCUMENT_SCHEMA_ID,
    MMCIF_ALTLOC_DECLARATION_PROFILE_ID,
    MmcifAltlocDeclarationError,
    mmcif_altloc_declaration_document,
    mmcif_altloc_declaration_json_bytes,
    parse_mmcif_altloc_declarations,
    require_mmcif_altloc_declaration_document,
    write_mmcif_altloc_declaration_json,
)


SEMANTIC_PREFIX = """data_altloc
_entry.id ALTLOC
#
loop_
_entity.id
_entity.type
1 polymer
#
loop_
_struct_asym.id
_struct_asym.entity_id
A 1
#
loop_
_entity_poly.entity_id
_entity_poly.type
1 'polypeptide(L)'
#
loop_
_entity_poly_seq.entity_id
_entity_poly_seq.num
_entity_poly_seq.mon_id
_entity_poly_seq.hetero
1 1 GLY n
1 2 ALA .
#
"""
EXTRA_CATEGORY = "_audit_conform.dict_name source_only\n#\n"
HEADERS = (
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
    "_atom_site.pdbx_pdb_model_num",
    "_atom_site.cartn_x",
    "_atom_site.cartn_y",
    "_atom_site.cartn_z",
    "_atom_site.occupancy",
    "_atom_site.b_iso_or_equiv",
)
ROWS = (
    {
        "_atom_site.group_pdb": "ATOM",
        "_atom_site.id": "1",
        "_atom_site.type_symbol": "N",
        "_atom_site.label_atom_id": "N",
        "_atom_site.label_alt_id": ".",
        "_atom_site.label_comp_id": "GLY",
        "_atom_site.label_asym_id": "A",
        "_atom_site.label_entity_id": "1",
        "_atom_site.label_seq_id": "1",
        "_atom_site.pdbx_pdb_ins_code": "?",
        "_atom_site.pdbx_pdb_model_num": "1",
        "_atom_site.cartn_x": "0.0",
        "_atom_site.cartn_y": "0.0",
        "_atom_site.cartn_z": "0.0",
        "_atom_site.occupancy": "1.00",
        "_atom_site.b_iso_or_equiv": "10.0",
    },
    {
        "_atom_site.group_pdb": "ATOM",
        "_atom_site.id": "2",
        "_atom_site.type_symbol": "C",
        "_atom_site.label_atom_id": "CA",
        "_atom_site.label_alt_id": "A",
        "_atom_site.label_comp_id": "GLY",
        "_atom_site.label_asym_id": "A",
        "_atom_site.label_entity_id": "1",
        "_atom_site.label_seq_id": "1",
        "_atom_site.pdbx_pdb_ins_code": "?",
        "_atom_site.pdbx_pdb_model_num": "1",
        "_atom_site.cartn_x": "1.0",
        "_atom_site.cartn_y": "0.0",
        "_atom_site.cartn_z": "0.0",
        "_atom_site.occupancy": "0.60",
        "_atom_site.b_iso_or_equiv": "11.0",
    },
    {
        "_atom_site.group_pdb": "ATOM",
        "_atom_site.id": "3",
        "_atom_site.type_symbol": "C",
        "_atom_site.label_atom_id": "CA",
        "_atom_site.label_alt_id": "B",
        "_atom_site.label_comp_id": "GLY",
        "_atom_site.label_asym_id": "A",
        "_atom_site.label_entity_id": "1",
        "_atom_site.label_seq_id": "1",
        "_atom_site.pdbx_pdb_ins_code": "?",
        "_atom_site.pdbx_pdb_model_num": "1",
        "_atom_site.cartn_x": "1.2",
        "_atom_site.cartn_y": "0.1",
        "_atom_site.cartn_z": "0.0",
        "_atom_site.occupancy": "0.40",
        "_atom_site.b_iso_or_equiv": "12.0",
    },
    {
        "_atom_site.group_pdb": "ATOM",
        "_atom_site.id": "4",
        "_atom_site.type_symbol": "C",
        "_atom_site.label_atom_id": "C",
        "_atom_site.label_alt_id": "'?'",
        "_atom_site.label_comp_id": "ALA",
        "_atom_site.label_asym_id": "A",
        "_atom_site.label_entity_id": "1",
        "_atom_site.label_seq_id": "2",
        "_atom_site.pdbx_pdb_ins_code": "'.'",
        "_atom_site.pdbx_pdb_model_num": "1",
        "_atom_site.cartn_x": "2.0",
        "_atom_site.cartn_y": "0.0",
        "_atom_site.cartn_z": "0.0",
        "_atom_site.occupancy": "1.00",
        "_atom_site.b_iso_or_equiv": "13.0",
    },
)


def _atom_site_loop(
    headers: tuple[str, ...] = HEADERS,
    rows: tuple[dict[str, str], ...] = ROWS,
) -> str:
    lines = ["loop_", *headers]
    lines.extend(" ".join(row[header] for header in headers) for row in rows)
    lines.append("#")
    return "\n".join(lines) + "\n"


CANONICAL = SEMANTIC_PREFIX + EXTRA_CATEGORY + _atom_site_loop()


def _rows(*updates: tuple[int, str, str]) -> tuple[dict[str, str], ...]:
    rows = [dict(row) for row in ROWS]
    for index, key, value in updates:
        rows[index][key] = value
    return tuple(rows)


def _error(source: str, code: str) -> MmcifAltlocDeclarationError:
    with pytest.raises(MmcifAltlocDeclarationError) as exc_info:
        parse_mmcif_altloc_declarations(source)
    assert exc_info.value.code == code
    return exc_info.value


def test_projection_preserves_altloc_markers_and_polymer_label_identity() -> None:
    snapshot = parse_mmcif_altloc_declarations(CANONICAL)

    assert snapshot.source_sha256 == hashlib.sha256(CANONICAL.encode("ascii")).hexdigest()
    assert snapshot.block_name == "altloc"
    assert len(snapshot.declarations) == 4
    assert snapshot.explicit_altloc_ids == ("A", "B", "?")
    assert snapshot.site_identity_count == 3
    assert snapshot.uninterpreted_categories == ("_audit_conform",)
    assert snapshot.uninterpreted_atom_site_headers == (
        "_atom_site.cartn_x",
        "_atom_site.cartn_y",
        "_atom_site.cartn_z",
        "_atom_site.occupancy",
        "_atom_site.b_iso_or_equiv",
    )

    blank, alt_a, alt_b, quoted_marker = snapshot.declarations
    assert blank.label_alt_id.state == "not_applicable"
    assert alt_a.label_alt_id.state == "known"
    assert alt_a.label_alt_id.value == "A"
    assert alt_b.label_alt_id.value == "B"
    assert alt_a.site_identity_sha256 == alt_b.site_identity_sha256
    assert blank.site_identity_sha256 != alt_a.site_identity_sha256
    assert quoted_marker.label_alt_id.state == "known"
    assert quoted_marker.label_alt_id.value == "?"
    assert quoted_marker.label_alt_id.quoted is True
    assert quoted_marker.insertion_code.state == "known"
    assert quoted_marker.insertion_code.value == "."
    assert quoted_marker.insertion_code.quoted is True

    payload = snapshot.to_dict()
    assert payload["profile_id"] == MMCIF_ALTLOC_DECLARATION_PROFILE_ID
    assert payload["source_altloc_markers_preserved"] is True
    assert payload["polymer_label_identity_references_verified"] is True
    assert payload["source_atom_order_preserved"] is True
    for flag in (
        "conformer_selected",
        "coordinate_values_interpreted",
        "coordinate_observation_assessed",
        "occupancy_values_interpreted",
        "occupancy_weighting_applied",
        "altloc_population_interpreted",
        "missingness_inferred",
        "auth_label_equivalence_inferred",
        "chemistry_interpreted",
        "topology_interpreted",
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


def test_header_order_and_uninterpreted_numeric_changes_do_not_change_projection() -> None:
    reordered_headers = tuple(reversed(HEADERS))
    reordered = SEMANTIC_PREFIX + EXTRA_CATEGORY + _atom_site_loop(reordered_headers)
    changed_numeric = (
        SEMANTIC_PREFIX
        + EXTRA_CATEGORY
        + _atom_site_loop(
            HEADERS,
            _rows(
                (1, "_atom_site.cartn_x", "999.0"),
                (1, "_atom_site.occupancy", "0.01"),
            ),
        )
    )

    canonical = parse_mmcif_altloc_declarations(CANONICAL)
    header_variant = parse_mmcif_altloc_declarations(reordered)
    numeric_variant = parse_mmcif_altloc_declarations(changed_numeric)

    assert canonical.declaration_projection_sha256 == header_variant.declaration_projection_sha256
    assert canonical.declaration_projection_sha256 == numeric_variant.declaration_projection_sha256
    assert canonical.source_binding_sha256 != header_variant.source_binding_sha256
    assert canonical.source_binding_sha256 != numeric_variant.source_binding_sha256
    assert canonical.snapshot_sha256 != numeric_variant.snapshot_sha256


def test_source_row_order_is_preserved_and_affects_projection() -> None:
    reordered_rows = (ROWS[0], ROWS[3], ROWS[1], ROWS[2])
    canonical = parse_mmcif_altloc_declarations(CANONICAL)
    variant = parse_mmcif_altloc_declarations(
        SEMANTIC_PREFIX + EXTRA_CATEGORY + _atom_site_loop(HEADERS, reordered_rows)
    )

    assert [row.source_atom_id for row in canonical.declarations] == [1, 2, 3, 4]
    assert [row.source_atom_id for row in variant.declarations] == [1, 4, 2, 3]
    assert canonical.declaration_projection_sha256 != variant.declaration_projection_sha256


def test_document_is_canonical_self_verifying_and_written_private(tmp_path: Path) -> None:
    snapshot = parse_mmcif_altloc_declarations(CANONICAL)
    document = mmcif_altloc_declaration_document(snapshot)

    assert document["schema_id"] == MMCIF_ALTLOC_DECLARATION_DOCUMENT_SCHEMA_ID
    assert require_mmcif_altloc_declaration_document(document) == document
    encoded = mmcif_altloc_declaration_json_bytes(snapshot)
    assert json.loads(encoded) == document

    destination = write_mmcif_altloc_declaration_json(tmp_path / "altloc.json", snapshot)
    assert destination.read_bytes() == encoded + b"\n"
    assert stat.S_IMODE(destination.stat().st_mode) == 0o600
    assert not list(tmp_path.glob(".altloc.json.*.tmp"))

    tampered = deepcopy(document)
    tampered["declaration_projection"]["declarations"][1]["label_atom_id"] = "PRIVATE"
    with pytest.raises(ValueError, match="projection digest mismatch"):
        require_mmcif_altloc_declaration_document(tampered)


@pytest.mark.parametrize(
    ("source", "code"),
    [
        (SEMANTIC_PREFIX, "atom_site_missing"),
        (SEMANTIC_PREFIX + "_atom_site.id 1\n", "atom_site_must_be_loop"),
        (
            SEMANTIC_PREFIX
            + _atom_site_loop(
                tuple(header for header in HEADERS if header != "_atom_site.label_alt_id")
            ),
            "required_atom_site_headers_missing",
        ),
        (
            SEMANTIC_PREFIX
            + _atom_site_loop(
                HEADERS + ("_custom.value",),
                tuple({**row, "_custom.value": "x"} for row in ROWS),
            ),
            "mixed_atom_site_loop",
        ),
    ],
)
def test_atom_site_surface_failures_are_explicit(source: str, code: str) -> None:
    _error(source, code)


def test_at_least_one_explicit_altloc_identifier_is_required() -> None:
    rows = _rows(
        (1, "_atom_site.label_alt_id", "."),
        (2, "_atom_site.label_alt_id", "?"),
        (3, "_atom_site.label_alt_id", "."),
    )
    _error(
        SEMANTIC_PREFIX + _atom_site_loop(HEADERS, rows),
        "explicit_altloc_declaration_missing",
    )


@pytest.mark.parametrize(
    ("index", "key", "value", "code"),
    [
        (1, "_atom_site.group_pdb", "HETATM", "nonpoly_atom_site_row_not_supported"),
        (1, "_atom_site.label_asym_id", "PRIVATE", "label_asym_reference_missing"),
        (1, "_atom_site.label_entity_id", "2", "label_entity_reference_mismatch"),
        (1, "_atom_site.label_seq_id", "3", "label_sequence_reference_missing"),
        (1, "_atom_site.label_comp_id", "ALA", "label_component_mismatch"),
        (1, "_atom_site.type_symbol", "?", "required_identity_marker"),
        (1, "_atom_site.id", "'2'", "invalid_positive_integer"),
    ],
)
def test_polymer_identity_contracts_fail_closed(
    index: int,
    key: str,
    value: str,
    code: str,
) -> None:
    _error(
        SEMANTIC_PREFIX + _atom_site_loop(HEADERS, _rows((index, key, value))),
        code,
    )


def test_duplicate_source_and_logical_altloc_declarations_are_rejected() -> None:
    _error(
        SEMANTIC_PREFIX + _atom_site_loop(HEADERS, _rows((2, "_atom_site.id", "2"))),
        "duplicate_source_atom_id",
    )
    duplicate = dict(ROWS[1])
    duplicate["_atom_site.id"] = "5"
    _error(
        SEMANTIC_PREFIX + _atom_site_loop(HEADERS, ROWS + (duplicate,)),
        "duplicate_altloc_declaration",
    )


def test_errors_do_not_echo_private_identity_values() -> None:
    source = SEMANTIC_PREFIX + _atom_site_loop(
        HEADERS,
        _rows((1, "_atom_site.label_asym_id", "PRIVATE-ASYM")),
    )
    error = _error(source, "label_asym_reference_missing")
    assert "PRIVATE-ASYM" not in str(error)
    assert "PRIVATE-ASYM" not in error.detail


def test_input_type_marker_and_integer_bounds_are_enforced() -> None:
    with pytest.raises(TypeError, match="must be a string"):
        parse_mmcif_altloc_declarations(b"data_x")  # type: ignore[arg-type]

    _error(
        SEMANTIC_PREFIX
        + _atom_site_loop(
            HEADERS,
            _rows((1, "_atom_site.id", str(1 << 53))),
        ),
        "positive_integer_out_of_bounds",
    )
    _error(
        SEMANTIC_PREFIX
        + _atom_site_loop(
            HEADERS,
            _rows((1, "_atom_site.label_alt_id", "'" + ("A" * 257) + "'")),
        ),
        "marker_token_out_of_bounds",
    )
