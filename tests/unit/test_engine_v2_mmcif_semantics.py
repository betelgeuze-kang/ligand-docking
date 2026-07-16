from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import stat

import pytest

from betelgeuze_engine_v2.molecular.mmcif_semantics import (
    MMCIF_SEMANTIC_DOCUMENT_SCHEMA_ID,
    MMCIF_SEMANTIC_PROFILE_ID,
    MmcifSemanticError,
    mmcif_semantic_document,
    mmcif_semantic_json_bytes,
    parse_mmcif_semantics,
    require_mmcif_semantic_document,
    write_mmcif_semantic_json,
)


CANONICAL = """data_demo
_entry.id DEMO
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
B 1
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
1 2 ALA .
#
loop_
_atom_site.group_PDB
_atom_site.id
ATOM 1
#
"""

CATEGORY_ORDER_VARIANT = """data_demo
loop_
_atom_site.group_PDB
_atom_site.id
ATOM 1
#
loop_
_entity_poly_seq.entity_id
_entity_poly_seq.num
_entity_poly_seq.mon_id
_entity_poly_seq.hetero
1 1 GLY n
1 2 ALA .
#
loop_
_entity_poly.entity_id
_entity_poly.type
1 'polypeptide(L)'
#
loop_
_struct_asym.id
_struct_asym.entity_id
A 1
B 1
W 2
#
loop_
_entity.id
_entity.type
1 polymer
2 water
#
_entry.id DEMO
"""

INTERLEAVED = """data_interleaved
_entry.id ?
loop_
_entity.id
_entity.type
1 polymer
2 polymer
loop_
_struct_asym.id
_struct_asym.entity_id
A 1
B 2
loop_
_entity_poly.entity_id
_entity_poly.type
1 'polypeptide(L)'
2 ?
loop_
_entity_poly_seq.entity_id
_entity_poly_seq.num
_entity_poly_seq.mon_id
_entity_poly_seq.hetero
1 1 GLY n
2 1 ALA no
1 2 SER ?
2 2 THR .
"""


def _replace_once(source: str, old: str, new: str) -> str:
    assert source.count(old) == 1
    return source.replace(old, new, 1)


def _error(source: str, code: str) -> MmcifSemanticError:
    with pytest.raises(MmcifSemanticError) as exc_info:
        parse_mmcif_semantics(source)
    assert exc_info.value.code == code
    return exc_info.value


def test_bounded_projection_preserves_identity_sequence_and_nonpromotion_boundary() -> None:
    snapshot = parse_mmcif_semantics(CANONICAL)

    assert snapshot.source_sha256 == hashlib.sha256(CANONICAL.encode("ascii")).hexdigest()
    assert snapshot.block_name == "demo"
    assert snapshot.entry_id is not None
    assert (snapshot.entry_id.state, snapshot.entry_id.value) == ("known", "DEMO")
    assert [(row.entity_id, row.entity_type) for row in snapshot.entities] == [
        ("1", "polymer"),
        ("2", "water"),
    ]
    assert [(row.asym_id, row.entity_id) for row in snapshot.asym_units] == [
        ("A", "1"),
        ("B", "1"),
        ("W", "2"),
    ]
    assert snapshot.polymer_definitions[0].polymer_type.value == "polypeptide(L)"
    assert [
        (row.entity_id, row.sequence_number, row.monomer_id, row.heterogeneity.state)
        for row in snapshot.polymer_sequence
    ] == [
        ("1", 1, "GLY", "known"),
        ("1", 2, "ALA", "not_applicable"),
    ]
    assert snapshot.uninterpreted_categories == ("_atom_site",)

    payload = snapshot.to_dict()
    assert payload["profile_id"] == MMCIF_SEMANTIC_PROFILE_ID
    assert payload["entity_count"] == 2
    assert payload["asym_count"] == 3
    assert payload["polymer_sequence_row_count"] == 2
    for flag in (
        "dictionary_conformance_assessed",
        "atom_site_semantics_interpreted",
        "coordinate_observation_assessed",
        "missingness_interpreted",
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


def test_category_order_changes_source_binding_but_not_semantic_projection() -> None:
    canonical = parse_mmcif_semantics(CANONICAL)
    reordered = parse_mmcif_semantics(CATEGORY_ORDER_VARIANT)

    assert canonical.semantic_projection_sha256 == reordered.semantic_projection_sha256
    assert canonical.source_binding_sha256 != reordered.source_binding_sha256
    assert canonical.snapshot_sha256 != reordered.snapshot_sha256
    assert canonical.source_category_order != reordered.source_category_order


def test_unknown_markers_and_quoted_markers_remain_distinct() -> None:
    source = _replace_once(INTERLEAVED, "_entry.id ?", "_entry.id '.'")
    snapshot = parse_mmcif_semantics(source)

    assert snapshot.entry_id is not None
    assert snapshot.entry_id.state == "known"
    assert snapshot.entry_id.value == "."
    definitions = {row.entity_id: row for row in snapshot.polymer_definitions}
    assert definitions["2"].polymer_type.state == "unknown"
    sequence = {(row.entity_id, row.sequence_number): row for row in snapshot.polymer_sequence}
    assert sequence[("1", 2)].heterogeneity.state == "unknown"
    assert sequence[("2", 2)].heterogeneity.state == "not_applicable"
    assert sequence[("2", 1)].heterogeneity.value == "n"


def test_interleaved_entities_preserve_global_source_order_and_per_entity_contiguity() -> None:
    snapshot = parse_mmcif_semantics(INTERLEAVED)

    assert [
        (row.entity_id, row.sequence_number, row.source_ordinal)
        for row in snapshot.polymer_sequence
    ] == [
        ("1", 1, 0),
        ("2", 1, 1),
        ("1", 2, 2),
        ("2", 2, 3),
    ]
    projection = mmcif_semantic_document(snapshot)["semantic_projection"]
    assert projection["sequence_row_order"] == (
        "source_order_with_per_entity_contiguous_positions"
    )


def test_shared_polymer_entity_may_have_multiple_asym_instances() -> None:
    snapshot = parse_mmcif_semantics(CANONICAL)
    assert [row.asym_id for row in snapshot.asym_units if row.entity_id == "1"] == [
        "A",
        "B",
    ]


def test_extra_headers_are_bound_but_not_promoted_to_semantics() -> None:
    source = _replace_once(
        CANONICAL,
        "_entity.type\n1 polymer\n2 water",
        "_entity.type\n_entity.pdbx_description\n1 polymer 'protein chain'\n2 water solvent",
    )
    snapshot = parse_mmcif_semantics(source)
    binding = next(item for item in snapshot.category_bindings if item.category == "_entity")

    assert binding.headers == (
        "_entity.id",
        "_entity.type",
        "_entity.pdbx_description",
    )
    assert [(row.entity_id, row.entity_type) for row in snapshot.entities] == [
        ("1", "polymer"),
        ("2", "water"),
    ]


def test_document_is_canonical_self_verifying_and_written_private(tmp_path: Path) -> None:
    snapshot = parse_mmcif_semantics(CANONICAL)
    document = mmcif_semantic_document(snapshot)

    assert document["schema_id"] == MMCIF_SEMANTIC_DOCUMENT_SCHEMA_ID
    assert require_mmcif_semantic_document(document) == document
    encoded = mmcif_semantic_json_bytes(snapshot)
    assert json.loads(encoded) == document

    destination = write_mmcif_semantic_json(tmp_path / "semantic.json", snapshot)
    assert destination.read_bytes() == encoded + b"\n"
    assert stat.S_IMODE(destination.stat().st_mode) == 0o600
    assert not list(tmp_path.glob(".semantic.json.*.tmp"))

    tampered = deepcopy(document)
    tampered["semantic_projection"]["polymer_sequence"][0]["monomer_id"] = "PRIVATE"
    with pytest.raises(ValueError, match="projection digest mismatch"):
        require_mmcif_semantic_document(tampered)


def test_semantic_errors_do_not_echo_private_identity_values() -> None:
    source = _replace_once(CANONICAL, "W 2", "W PRIVATE-UNKNOWN-ENTITY")
    error = _error(source, "asym_entity_reference_missing")
    assert "PRIVATE-UNKNOWN-ENTITY" not in str(error)
    assert "PRIVATE-UNKNOWN-ENTITY" not in error.detail


@pytest.mark.parametrize(
    ("source", "code"),
    [
        (
            _replace_once(
                CANONICAL,
                "loop_\n_entity.id\n_entity.type\n1 polymer\n2 water\n#",
                "_entity.id 1\n_entity.type polymer\n#",
            ),
            "category_must_be_loop",
        ),
        (
            _replace_once(CANONICAL, "_entity.type\n1 polymer", "_entity.pdbx_description\n1 protein"),
            "required_header_missing",
        ),
        (
            _replace_once(CANONICAL, "1 polymer\n2 water", "1 polymer\n1 water"),
            "duplicate_entity_id",
        ),
        (
            _replace_once(CANONICAL, "B 1\nW 2", "A 1\nW 2"),
            "duplicate_asym_id",
        ),
        (
            _replace_once(CANONICAL, "W 2", "W 99"),
            "asym_entity_reference_missing",
        ),
        (
            _replace_once(CANONICAL, "1 'polypeptide(L)'", "2 'polypeptide(L)'"),
            "entity_poly_nonpolymer_reference",
        ),
        (
            _replace_once(CANONICAL, "1 2 ALA .", "1 01 ALA ."),
            "invalid_sequence_number",
        ),
        (
            _replace_once(CANONICAL, "1 2 ALA .", "1 3 ALA ."),
            "noncontiguous_sequence_positions",
        ),
        (
            _replace_once(CANONICAL, "1 2 ALA .", "1 2 ALA yes"),
            "microheterogeneity_not_supported",
        ),
        (
            _replace_once(CANONICAL, "1 2 ALA .", "2 1 ALA ."),
            "sequence_nonpolymer_reference",
        ),
        (
            _replace_once(CANONICAL, "1 polymer\n2 water", "1 water\n2 water"),
            "polymer_entity_missing",
        ),
        (
            _replace_once(CANONICAL, "A 1\nB 1\nW 2", "W 2"),
            "polymer_asym_coverage_missing",
        ),
    ],
)
def test_referential_and_sequence_contracts_fail_closed(source: str, code: str) -> None:
    _error(source, code)


def test_cross_category_loop_and_required_identity_markers_are_rejected() -> None:
    mixed = """data_mixed
loop_
_entity.id
_entity.type
_struct_asym.id
_struct_asym.entity_id
1 polymer A 1
loop_
_entity_poly.entity_id
_entity_poly.type
1 polypeptide
loop_
_entity_poly_seq.entity_id
_entity_poly_seq.num
_entity_poly_seq.mon_id
_entity_poly_seq.hetero
1 1 GLY n
"""
    _error(mixed, "mixed_category_loop")
    _error(_replace_once(CANONICAL, "1 polymer", ". polymer"), "required_identity_marker")


def test_input_type_and_semantic_token_bounds_are_enforced() -> None:
    with pytest.raises(TypeError, match="must be a string"):
        parse_mmcif_semantics(b"data_x")  # type: ignore[arg-type]

    long_type = "x" * 257
    source = _replace_once(CANONICAL, "1 'polypeptide(L)'", f"1 '{long_type}'")
    _error(source, "semantic_value_out_of_bounds")
