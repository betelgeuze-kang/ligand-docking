from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import stat

import pytest

from betelgeuze_engine_v2.molecular.mmcif_zero_occupancy_atom_declarations import (
    MMCIF_ZERO_OCCUPANCY_ATOM_DOCUMENT_SCHEMA_ID,
    MMCIF_ZERO_OCCUPANCY_ATOM_HEADERS,
    MMCIF_ZERO_OCCUPANCY_ATOM_PROFILE_ID,
    MmcifZeroOccupancyAtomDeclarationError,
    parse_mmcif_zero_occupancy_atom_declarations,
    require_zero_occupancy_atom_document,
    write_zero_occupancy_atom_json,
    zero_occupancy_atom_document,
    zero_occupancy_atom_json_bytes,
)


ZERO_HEADERS = "\n".join(MMCIF_ZERO_OCCUPANCY_ATOM_HEADERS)

CANONICAL = f"""data_demo
_entry.id DEMO
loop_
_entity.id
_entity.type
1 polymer
2 water
loop_
_struct_asym.id
_struct_asym.entity_id
A 1
B 1
W 2
loop_
_entity_poly.entity_id
_entity_poly.type
1 'polypeptide(L)'
loop_
_entity_poly_seq.entity_id
_entity_poly_seq.num
_entity_poly_seq.mon_id
_entity_poly_seq.hetero
1 1 GLY n
1 2 ALA .
loop_
{ZERO_HEADERS}
1 Y 0 1 AX GLY AUTH-1 ? N . A GLY 1 N
2 y 0.00 1 AX ALA AUTH-2 B CB ? A ALA 2 CB
loop_
_atom_site.group_PDB
_atom_site.id
_atom_site.label_asym_id
_atom_site.label_seq_id
_atom_site.label_atom_id
_atom_site.occupancy
ATOM 1 A 1 N 1.0
ATOM 2 A 2 CB 1.0
"""

CATEGORY_ORDER_VARIANT = f"""data_demo
loop_
_atom_site.group_PDB
_atom_site.id
_atom_site.label_asym_id
_atom_site.label_seq_id
_atom_site.label_atom_id
_atom_site.occupancy
ATOM 1 A 1 N 1.0
ATOM 2 A 2 CB 1.0
loop_
{ZERO_HEADERS}
1 Y 0e0 1 AX GLY AUTH-1 ? N . A GLY 1 N
2 Y -0 1 AX ALA AUTH-2 B CB ? A ALA 2 CB
loop_
_entity_poly_seq.entity_id
_entity_poly_seq.num
_entity_poly_seq.mon_id
_entity_poly_seq.hetero
1 1 GLY n
1 2 ALA .
loop_
_entity_poly.entity_id
_entity_poly.type
1 'polypeptide(L)'
loop_
_struct_asym.id
_struct_asym.entity_id
A 1
B 1
W 2
loop_
_entity.id
_entity.type
1 polymer
2 water
_entry.id DEMO
"""


NO_ATOM_SITE = CANONICAL.split("loop_\n_atom_site.group_PDB", 1)[0]


def _replace_once(source: str, old: str, new: str) -> str:
    assert source.count(old) == 1
    return source.replace(old, new, 1)


def _error(source: str, code: str) -> MmcifZeroOccupancyAtomDeclarationError:
    with pytest.raises(MmcifZeroOccupancyAtomDeclarationError) as exc_info:
        parse_mmcif_zero_occupancy_atom_declarations(source)
    assert exc_info.value.code == code
    return exc_info.value


def test_declarations_are_preserved_and_bound_only_to_semantic_identity() -> None:
    snapshot = parse_mmcif_zero_occupancy_atom_declarations(CANONICAL)

    assert snapshot.source_sha256 == hashlib.sha256(CANONICAL.encode("ascii")).hexdigest()
    assert len(snapshot.declarations) == 2
    first, second = snapshot.declarations
    assert (
        first.source_id,
        first.model_number,
        first.auth_asym_id,
        first.auth_comp_id,
        first.auth_seq_id,
        first.auth_atom_id,
        first.label_asym_id,
        first.label_comp_id,
        first.label_seq_id,
        first.label_atom_id,
        first.entity_id,
    ) == (1, 1, "AX", "GLY", "AUTH-1", "N", "A", "GLY", 1, "N", "1")
    assert first.insertion_code.state == "unknown"
    assert first.label_alt_id.state == "not_applicable"
    assert second.insertion_code.state == "known"
    assert second.insertion_code.value == "B"
    assert second.label_alt_id.state == "unknown"

    summary = snapshot.to_dict()
    assert summary["profile_id"] == MMCIF_ZERO_OCCUPANCY_ATOM_PROFILE_ID
    assert summary["declaration_count"] == 2
    assert summary["source_reported_zero_occupancy_atom_declarations_preserved"] is True
    for field in (
        "atom_site_semantics_interpreted",
        "coordinate_row_crosscheck_performed",
        "coordinate_observation_completeness_assessed",
        "zero_occupancy_atom_fact_claimed",
        "missing_atom_fact_claimed",
        "occupancy_population_interpreted",
        "occupancy_weighting_applied",
        "refinement_validity_assessed",
        "auth_label_equivalence_inferred",
        "altloc_population_interpreted",
        "chemistry_interpreted",
        "topology_interpreted",
        "completion_attempted",
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
        assert summary[field] is False


def test_atom_site_is_not_required_or_cross_checked() -> None:
    without_atom_site = parse_mmcif_zero_occupancy_atom_declarations(NO_ATOM_SITE)
    with_nonzero_atom_site = parse_mmcif_zero_occupancy_atom_declarations(CANONICAL)

    assert without_atom_site.declaration_projection_sha256 == (
        with_nonzero_atom_site.declaration_projection_sha256
    )
    assert without_atom_site.to_dict()["coordinate_row_crosscheck_performed"] is False
    assert with_nonzero_atom_site.to_dict()["zero_occupancy_atom_fact_claimed"] is False


def test_category_order_and_numeric_zero_spelling_do_not_change_declaration_projection() -> None:
    canonical = parse_mmcif_zero_occupancy_atom_declarations(CANONICAL)
    reordered = parse_mmcif_zero_occupancy_atom_declarations(CATEGORY_ORDER_VARIANT)

    assert canonical.semantic_projection_sha256 == reordered.semantic_projection_sha256
    assert canonical.declaration_projection_sha256 == reordered.declaration_projection_sha256
    assert canonical.source_binding_sha256 != reordered.source_binding_sha256
    assert canonical.snapshot_sha256 != reordered.snapshot_sha256


def test_quoted_marker_is_known_literal_not_missing_marker() -> None:
    source = _replace_once(
        CANONICAL,
        "1 Y 0 1 AX GLY AUTH-1 ? N . A GLY 1 N",
        "1 Y 0 1 AX GLY AUTH-1 '.' N '?' A GLY 1 N",
    )
    declaration = parse_mmcif_zero_occupancy_atom_declarations(source).declarations[0]

    assert declaration.insertion_code.state == "known"
    assert declaration.insertion_code.value == "."
    assert declaration.label_alt_id.state == "known"
    assert declaration.label_alt_id.value == "?"


def test_shared_polymer_entity_asym_instances_are_bound_independently() -> None:
    source = _replace_once(
        CANONICAL,
        "2 y 0.00 1 AX ALA AUTH-2 B CB ? A ALA 2 CB",
        "2 Y 0 1 BX ALA AUTH-2 ? CB . B ALA 2 CB",
    )
    declarations = parse_mmcif_zero_occupancy_atom_declarations(source).declarations

    assert declarations[0].label_asym_id == "A"
    assert declarations[1].label_asym_id == "B"
    assert declarations[0].entity_id == declarations[1].entity_id == "1"


def test_document_is_canonical_self_verifying_and_written_private(tmp_path: Path) -> None:
    snapshot = parse_mmcif_zero_occupancy_atom_declarations(CANONICAL)
    document = zero_occupancy_atom_document(snapshot)

    assert document["schema_id"] == MMCIF_ZERO_OCCUPANCY_ATOM_DOCUMENT_SCHEMA_ID
    assert require_zero_occupancy_atom_document(document) == document
    encoded = zero_occupancy_atom_json_bytes(snapshot)
    assert json.loads(encoded) == document

    destination = write_zero_occupancy_atom_json(tmp_path / "zero-occ-atoms.json", snapshot)
    assert destination.read_bytes() == encoded + b"\n"
    assert stat.S_IMODE(destination.stat().st_mode) == 0o600
    assert not list(tmp_path.glob(".zero-occ-atoms.json.*.tmp"))

    tampered = deepcopy(document)
    tampered["declaration_projection"]["declarations"][0]["label_atom_id"] = "PRIVATE"
    with pytest.raises(ValueError, match="projection digest mismatch"):
        require_zero_occupancy_atom_document(tampered)


def test_errors_do_not_echo_private_identity_values() -> None:
    source = _replace_once(CANONICAL, "A GLY 1 N", "PRIVATE-ASYM GLY 1 N")
    error = _error(source, "label_asym_reference_missing")

    assert "PRIVATE-ASYM" not in str(error)
    assert "PRIVATE-ASYM" not in error.detail


@pytest.mark.parametrize(
    ("source", "code"),
    [
        (
            _replace_once(
                CANONICAL,
                "loop_\n" + ZERO_HEADERS + "\n1 Y 0 1",
                "_pdbx_unobs_or_zero_occ_atoms.id 1\n"
                "_pdbx_unobs_or_zero_occ_atoms.polymer_flag Y\n"
                "_pdbx_unobs_or_zero_occ_atoms.occupancy_flag 0\n"
                "_pdbx_unobs_or_zero_occ_atoms.pdb_model_num 1\n"
                "_pdbx_unobs_or_zero_occ_atoms.auth_asym_id AX\n"
                "_pdbx_unobs_or_zero_occ_atoms.auth_comp_id GLY\n"
                "_pdbx_unobs_or_zero_occ_atoms.auth_seq_id AUTH-1\n"
                "_pdbx_unobs_or_zero_occ_atoms.pdb_ins_code ?\n"
                "_pdbx_unobs_or_zero_occ_atoms.auth_atom_id N\n"
                "_pdbx_unobs_or_zero_occ_atoms.label_alt_id .\n"
                "_pdbx_unobs_or_zero_occ_atoms.label_asym_id A\n"
                "_pdbx_unobs_or_zero_occ_atoms.label_comp_id GLY\n"
                "_pdbx_unobs_or_zero_occ_atoms.label_seq_id 1\n"
                "_pdbx_unobs_or_zero_occ_atoms.label_atom_id N\n"
                "1 Y 0 1",
            ),
            "category_must_be_loop",
        ),
        (
            _replace_once(
                CANONICAL,
                "_pdbx_unobs_or_zero_occ_atoms.label_atom_id\n",
                "",
            ),
            "required_header_missing",
        ),
        (
            _replace_once(CANONICAL, "2 y 0.00 1", "1 Y 0.00 1"),
            "duplicate_declaration_id",
        ),
        (
            _replace_once(CANONICAL, "1 Y 0 1", "1 N 0 1"),
            "nonpolymer_declaration_not_supported",
        ),
        (
            _replace_once(CANONICAL, "1 Y 0 1", "1 Y 1 1"),
            "occupancy_flag_not_numeric_zero",
        ),
        (
            _replace_once(CANONICAL, "1 Y 0 1", "1 Y NaN 1"),
            "occupancy_flag_not_numeric_zero",
        ),
        (
            _replace_once(CANONICAL, "1 Y 0 1", "1 Y 0 01"),
            "invalid_positive_integer",
        ),
        (
            _replace_once(CANONICAL, "A GLY 1 N", "UNKNOWN GLY 1 N"),
            "label_asym_reference_missing",
        ),
        (
            _replace_once(CANONICAL, "A GLY 1 N", "W GLY 1 N"),
            "label_asym_not_polymer",
        ),
        (
            _replace_once(CANONICAL, "A GLY 1 N", "A GLY 9 N"),
            "label_sequence_reference_missing",
        ),
        (
            _replace_once(CANONICAL, "A GLY 1 N", "A ALA 1 N"),
            "label_component_sequence_mismatch",
        ),
        (
            _replace_once(CANONICAL, "AX GLY AUTH-1", "'AX' GLY AUTH-1"),
            "invalid_identity_token",
        ),
    ],
)
def test_declaration_contracts_fail_closed(source: str, code: str) -> None:
    _error(source, code)


def test_missing_or_mixed_declaration_loop_is_rejected() -> None:
    missing = CANONICAL.split("loop_\n" + ZERO_HEADERS, 1)[0]
    _error(missing, "declaration_loop_missing")

    mixed = _replace_once(
        CANONICAL,
        ZERO_HEADERS,
        ZERO_HEADERS + "\n_atom_site.id",
    )
    _error(mixed, "mixed_category_loop")


def test_input_type_is_strict() -> None:
    with pytest.raises(TypeError, match="must be a string"):
        parse_mmcif_zero_occupancy_atom_declarations(b"data_x")  # type: ignore[arg-type]
