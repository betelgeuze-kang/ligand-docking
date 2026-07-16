from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import stat

import pytest

from betelgeuze_engine_v2.molecular.mmcif_altloc_source import (
    MMCIF_ALTLOC_SOURCE_ATOM_SITE_HEADERS,
    MMCIF_ALTLOC_SOURCE_DOCUMENT_SCHEMA_ID,
    MMCIF_ALTLOC_SOURCE_PROFILE_ID,
    MmcifAltlocSourceError,
    mmcif_altloc_source_document,
    mmcif_altloc_source_json_bytes,
    parse_mmcif_altloc_source,
    require_mmcif_altloc_source_document,
    write_mmcif_altloc_source_json,
)


SEMANTIC_PREFIX = """data_altloc
_entry.id ALTLOC
#
loop_
_entity.id
_entity.type
1 polymer
2 water
#
loop_
_struct_asym.id
_struct_asym.entity_id
A 1
W 2
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
#
"""

ATOM_ROWS: tuple[tuple[str, ...], ...] = (
    (
        "ATOM", "1", "N", "N", ".", "GLY", "A", "1", "1", "?",
        "0.0", "0.0", "0.0", "1.00", "10.0", "?", "1", "GLY", "X", "N", "1",
    ),
    (
        "ATOM", "2", "C", "CA", "A", "GLY", "A", "1", "1", "?",
        "1.000(5)", "0.0", "0.0", "0.60", "11.0", "?", "1", "GLY", "X", "CA", "1",
    ),
    (
        "ATOM", "3", "C", "CA", "B", "GLY", "A", "1", "1", "?",
        "2.0", "0.0", "0.0", "+4.0E-1", "12.0", "?", "1", "GLY", "X", "CA", "1",
    ),
    (
        "HETATM", "4", "O", "O", "conf-A", "HOH", "W", "2", ".", "?",
        "3.0", "0.0", "0.0", "1.00", "13.0", "?", "5", "HOH", "W", "O", "1",
    ),
)

AUDIT_LOOP = """loop_
_audit_author.name
'Example Author'
#
"""

ZERO_OCCUPANCY_ATOM_LOOP = """loop_
_pdbx_unobs_or_zero_occ_atoms.id
_pdbx_unobs_or_zero_occ_atoms.polymer_flag
_pdbx_unobs_or_zero_occ_atoms.occupancy_flag
_pdbx_unobs_or_zero_occ_atoms.pdb_model_num
_pdbx_unobs_or_zero_occ_atoms.auth_asym_id
_pdbx_unobs_or_zero_occ_atoms.auth_comp_id
_pdbx_unobs_or_zero_occ_atoms.auth_seq_id
_pdbx_unobs_or_zero_occ_atoms.pdb_ins_code
_pdbx_unobs_or_zero_occ_atoms.auth_atom_id
_pdbx_unobs_or_zero_occ_atoms.label_alt_id
_pdbx_unobs_or_zero_occ_atoms.label_asym_id
_pdbx_unobs_or_zero_occ_atoms.label_comp_id
_pdbx_unobs_or_zero_occ_atoms.label_seq_id
_pdbx_unobs_or_zero_occ_atoms.label_atom_id
1 Y -0.0E+0 1 AX GLY 1 ? CA Z A GLY 1 CA
#
"""


def _atom_site_loop(
    *,
    headers: tuple[str, ...] = MMCIF_ALTLOC_SOURCE_ATOM_SITE_HEADERS,
    rows: tuple[tuple[str, ...], ...] = ATOM_ROWS,
    extra_values: dict[str, str] | None = None,
) -> str:
    canonical_index = {
        header: index for index, header in enumerate(MMCIF_ALTLOC_SOURCE_ATOM_SITE_HEADERS)
    }
    extras = dict(extra_values or {})
    rendered_rows: list[str] = []
    for row in rows:
        values = [
            row[canonical_index[header]] if header in canonical_index else extras[header]
            for header in headers
        ]
        rendered_rows.append(" ".join(values))
    return "loop_\n" + "\n".join(headers) + "\n" + "\n".join(rendered_rows) + "\n#\n"


def _source(
    *,
    headers: tuple[str, ...] = MMCIF_ALTLOC_SOURCE_ATOM_SITE_HEADERS,
    rows: tuple[tuple[str, ...], ...] = ATOM_ROWS,
    zero_occupancy: bool = False,
    audit: bool = True,
    extra_values: dict[str, str] | None = None,
) -> str:
    return (
        SEMANTIC_PREFIX
        + _atom_site_loop(headers=headers, rows=rows, extra_values=extra_values)
        + (ZERO_OCCUPANCY_ATOM_LOOP if zero_occupancy else "")
        + (AUDIT_LOOP if audit else "")
    )


def _replace_row(row_index: int, field: str, value: str) -> tuple[tuple[str, ...], ...]:
    rows = [list(row) for row in ATOM_ROWS]
    field_index = MMCIF_ALTLOC_SOURCE_ATOM_SITE_HEADERS.index(field)
    rows[row_index][field_index] = value
    return tuple(tuple(row) for row in rows)


def _error(source: str, code: str) -> MmcifAltlocSourceError:
    with pytest.raises(MmcifAltlocSourceError) as exc_info:
        parse_mmcif_altloc_source(source)
    assert exc_info.value.code == code
    return exc_info.value


def test_projection_preserves_ordered_rows_tokens_sites_and_claim_boundary() -> None:
    source = _source()
    snapshot = parse_mmcif_altloc_source(source)

    assert snapshot.source_sha256 == hashlib.sha256(source.encode("ascii")).hexdigest()
    assert snapshot.block_name == "altloc"
    assert len(snapshot.atom_site_rows) == 4
    assert snapshot.explicit_altloc_ids == ("A", "B", "conf-A")
    assert snapshot.uninterpreted_categories == ("_audit_author",)

    blank, alt_a, alt_b, water = snapshot.atom_site_rows
    assert blank.label_alt_id.state == "not_applicable"
    assert alt_a.label_alt_id.to_dict() == {
        "state": "known",
        "value": "A",
        "quoted": False,
    }
    assert alt_a.cartn_x.value == "1.000(5)"
    assert alt_a.occupancy.value == "0.60"
    assert alt_b.occupancy.value == "+4.0E-1"
    assert water.entity_type == "water"
    assert water.label_seq_id.state == "not_applicable"
    assert water.label_seq_number is None

    assert len(snapshot.affected_sites) == 2
    polymer_site, water_site = snapshot.affected_sites
    assert polymer_site.label_atom_id == "CA"
    assert polymer_site.source_row_ordinals == (1, 2)
    assert polymer_site.explicit_altloc_ids == ("A", "B")
    assert water_site.label_atom_id == "O"
    assert water_site.source_row_ordinals == (3,)
    assert water_site.explicit_altloc_ids == ("conf-A",)

    payload = snapshot.to_dict()
    assert payload["profile_id"] == MMCIF_ALTLOC_SOURCE_PROFILE_ID
    assert payload["source_atom_site_rows_preserved"] is True
    assert payload["source_row_order_preserved"] is True
    assert payload["label_alt_id_tokens_preserved"] is True
    assert payload["semantic_identity_references_verified"] is True
    assert payload["explicit_altloc_row_count"] == 3
    for flag in (
        "altloc_selected",
        "coordinates_materialized",
        "coordinate_values_interpreted",
        "coordinate_observation_assessed",
        "missingness_inferred",
        "auth_label_equivalence_inferred",
        "altloc_population_interpreted",
        "occupancy_population_interpreted",
        "occupancy_weighting_applied",
        "zero_occupancy_atom_site_crosschecked",
        "refinement_validity_assessed",
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


def test_header_order_changes_source_binding_but_not_projection() -> None:
    canonical = parse_mmcif_altloc_source(_source(audit=False))
    reordered = parse_mmcif_altloc_source(
        _source(headers=tuple(reversed(MMCIF_ALTLOC_SOURCE_ATOM_SITE_HEADERS)), audit=False)
    )

    assert canonical.semantic_projection_sha256 == reordered.semantic_projection_sha256
    assert canonical.altloc_projection_sha256 == reordered.altloc_projection_sha256
    assert canonical.source_binding_sha256 != reordered.source_binding_sha256
    assert canonical.atom_site_binding.headers != reordered.atom_site_binding.headers


def test_optional_zero_occupancy_is_validated_but_never_crosschecked() -> None:
    snapshot = parse_mmcif_altloc_source(_source(zero_occupancy=True, audit=False))

    assert snapshot.zero_occupancy_snapshot_sha256
    assert snapshot.zero_occupancy_projection_sha256
    assert snapshot.zero_occupancy_source_binding_sha256
    assert snapshot.to_dict()["zero_occupancy_declarations_present"] is True
    assert snapshot.to_dict()["zero_occupancy_atom_site_crosschecked"] is False
    # The declaration intentionally names altloc Z, which is absent from atom_site.
    assert "Z" not in snapshot.explicit_altloc_ids


def test_quoted_marker_is_a_known_explicit_altloc_identifier() -> None:
    rows = _replace_row(2, "_atom_site.label_alt_id", "'?'")
    snapshot = parse_mmcif_altloc_source(_source(rows=rows, audit=False))

    assert snapshot.atom_site_rows[2].label_alt_id.state == "known"
    assert snapshot.atom_site_rows[2].label_alt_id.value == "?"
    assert snapshot.atom_site_rows[2].label_alt_id.quoted is True
    assert snapshot.explicit_altloc_ids == ("A", "?", "conf-A")


def test_document_is_canonical_self_verifying_and_written_private(tmp_path: Path) -> None:
    snapshot = parse_mmcif_altloc_source(_source())
    document = mmcif_altloc_source_document(snapshot)

    assert document["schema_id"] == MMCIF_ALTLOC_SOURCE_DOCUMENT_SCHEMA_ID
    assert require_mmcif_altloc_source_document(document) == document
    encoded = mmcif_altloc_source_json_bytes(snapshot)
    assert json.loads(encoded) == document

    destination = write_mmcif_altloc_source_json(tmp_path / "altloc.json", snapshot)
    assert destination.read_bytes() == encoded + b"\n"
    assert stat.S_IMODE(destination.stat().st_mode) == 0o600
    assert not list(tmp_path.glob(".altloc.json.*.tmp"))

    tampered = deepcopy(document)
    tampered["altloc_projection"]["atom_site_rows"][1]["occupancy"]["value"] = "PRIVATE"
    with pytest.raises(ValueError, match="projection digest mismatch"):
        require_mmcif_altloc_source_document(tampered)


def test_identity_sequence_and_model_contracts_fail_closed() -> None:
    _error(
        _source(
            rows=_replace_row(1, "_atom_site.label_asym_id", "PRIVATE"),
            audit=False,
        ),
        "label_asym_reference_missing",
    )
    _error(
        _source(
            rows=_replace_row(1, "_atom_site.label_entity_id", "2"),
            audit=False,
        ),
        "label_entity_reference_mismatch",
    )
    _error(
        _source(
            rows=_replace_row(1, "_atom_site.label_seq_id", "2"),
            audit=False,
        ),
        "label_sequence_reference_missing",
    )
    _error(
        _source(
            rows=_replace_row(1, "_atom_site.label_comp_id", "ALA"),
            audit=False,
        ),
        "label_component_mismatch",
    )
    _error(
        _source(
            rows=_replace_row(1, "_atom_site.pdbx_pdb_model_num", "01"),
            audit=False,
        ),
        "invalid_positive_integer",
    )
    _error(
        _source(
            rows=_replace_row(1, "_atom_site.group_pdb", "OTHER"),
            audit=False,
        ),
        "unsupported_group_pdb",
    )


def test_explicit_altloc_duplicate_and_header_contracts_fail_closed() -> None:
    all_blank = tuple(
        tuple("." if index == 4 else value for index, value in enumerate(row))
        for row in ATOM_ROWS
    )
    _error(_source(rows=all_blank, audit=False), "explicit_altloc_missing")

    duplicate_id = _replace_row(2, "_atom_site.id", "2")
    _error(_source(rows=duplicate_id, audit=False), "duplicate_atom_site_id")

    duplicate_row = list(ATOM_ROWS[1])
    duplicate_row[1] = "5"
    _error(
        _source(rows=ATOM_ROWS + (tuple(duplicate_row),), audit=False),
        "duplicate_atom_site_logical_row",
    )

    missing_header = tuple(
        header
        for header in MMCIF_ALTLOC_SOURCE_ATOM_SITE_HEADERS
        if header != "_atom_site.pdbx_formal_charge"
    )
    _error(
        _source(headers=missing_header, audit=False),
        "unsupported_atom_site_headers",
    )

    mixed_headers = MMCIF_ALTLOC_SOURCE_ATOM_SITE_HEADERS + ("_audit_author.name",)
    _error(
        _source(
            headers=mixed_headers,
            audit=False,
            extra_values={"_audit_author.name": "AUTHOR"},
        ),
        "mixed_atom_site_loop",
    )


def test_missing_and_scalar_atom_site_contracts_fail_closed() -> None:
    _error(SEMANTIC_PREFIX, "atom_site_category_missing")
    _error(SEMANTIC_PREFIX + "_atom_site.id 1\n", "atom_site_must_be_loop")
    with pytest.raises(TypeError, match="must be a string"):
        parse_mmcif_altloc_source(b"data_altloc")  # type: ignore[arg-type]
