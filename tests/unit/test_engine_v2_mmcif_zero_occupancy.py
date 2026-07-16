from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import stat

import pytest

from betelgeuze_engine_v2.molecular.mmcif_zero_occupancy import (
    MMCIF_ZERO_OCCUPANCY_DOCUMENT_SCHEMA_ID,
    MMCIF_ZERO_OCCUPANCY_PROFILE_ID,
    MmcifZeroOccupancyError,
    mmcif_zero_occupancy_document,
    mmcif_zero_occupancy_json_bytes,
    parse_mmcif_zero_occupancy_declarations,
    require_mmcif_zero_occupancy_document,
    write_mmcif_zero_occupancy_json,
)


SEMANTIC_PREFIX = """data_zero
_entry.id ZERO
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

RESIDUE_LOOP = """loop_
_pdbx_unobs_or_zero_occ_residues.id
_pdbx_unobs_or_zero_occ_residues.polymer_flag
_pdbx_unobs_or_zero_occ_residues.occupancy_flag
_pdbx_unobs_or_zero_occ_residues.pdb_model_num
_pdbx_unobs_or_zero_occ_residues.auth_asym_id
_pdbx_unobs_or_zero_occ_residues.auth_comp_id
_pdbx_unobs_or_zero_occ_residues.auth_seq_id
_pdbx_unobs_or_zero_occ_residues.pdb_ins_code
_pdbx_unobs_or_zero_occ_residues.label_asym_id
_pdbx_unobs_or_zero_occ_residues.label_comp_id
_pdbx_unobs_or_zero_occ_residues.label_seq_id
1 Y 0 1 AX GLY AUTH-1 ? A GLY 1
2 Y -0.0E+0 2 AX ALA AUTH-2 '.' A ALA 2
#
"""

ATOM_LOOP = """loop_
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
1 Y 0.000 1 AX GLY AUTH-1 ? CA . A GLY 1 CA
2 Y +0E0 1 AX GLY AUTH-1 . CB '?' A GLY 1 CB
#
"""

ATOM_SITE = """loop_
_atom_site.id
_atom_site.occupancy
1 1.00
#
"""

CANONICAL = SEMANTIC_PREFIX + RESIDUE_LOOP + ATOM_LOOP + ATOM_SITE
NO_ATOM_SITE = SEMANTIC_PREFIX + RESIDUE_LOOP + ATOM_LOOP
CATEGORY_ORDER_VARIANT = (
    "data_zero\n"
    + ATOM_LOOP
    + ATOM_SITE
    + RESIDUE_LOOP
    + "_entry.id ZERO\n#\n"
    + """loop_
_entity_poly_seq.hetero
_entity_poly_seq.mon_id
_entity_poly_seq.num
_entity_poly_seq.entity_id
n GLY 1 1
. ALA 2 1
#
loop_
_entity_poly.type
_entity_poly.entity_id
'polypeptide(L)' 1
#
loop_
_struct_asym.entity_id
_struct_asym.id
1 A
#
loop_
_entity.type
_entity.id
polymer 1
#
"""
)


def _replace_once(source: str, old: str, new: str) -> str:
    assert source.count(old) == 1
    return source.replace(old, new, 1)


def _error(source: str, code: str) -> MmcifZeroOccupancyError:
    with pytest.raises(MmcifZeroOccupancyError) as exc_info:
        parse_mmcif_zero_occupancy_declarations(source)
    assert exc_info.value.code == code
    return exc_info.value


def test_projection_preserves_ordered_residue_atom_and_marker_declarations() -> None:
    snapshot = parse_mmcif_zero_occupancy_declarations(CANONICAL)

    assert snapshot.source_sha256 == hashlib.sha256(CANONICAL.encode("ascii")).hexdigest()
    assert snapshot.block_name == "zero"
    assert len(snapshot.residue_declarations) == 2
    assert len(snapshot.atom_declarations) == 2
    assert snapshot.uninterpreted_categories == ("_atom_site",)

    residue_a, residue_b = snapshot.residue_declarations
    assert (
        residue_a.source_id,
        residue_a.model_number,
        residue_a.entity_id,
        residue_a.label_asym_id,
        residue_a.label_comp_id,
        residue_a.label_seq_id,
        residue_a.occupancy_token,
        residue_a.source_ordinal,
    ) == (1, 1, "1", "A", "GLY", 1, "0", 0)
    assert residue_a.insertion_code.state == "unknown"
    assert residue_b.occupancy_token == "-0.0E+0"
    assert residue_b.insertion_code.state == "known"
    assert residue_b.insertion_code.value == "."
    assert residue_b.insertion_code.quoted is True

    atom_a, atom_b = snapshot.atom_declarations
    assert atom_a.label_atom_id == "CA"
    assert atom_a.label_alt_id.state == "not_applicable"
    assert atom_b.label_atom_id == "CB"
    assert atom_b.label_alt_id.state == "known"
    assert atom_b.label_alt_id.value == "?"
    assert atom_b.label_alt_id.quoted is True
    assert atom_b.occupancy_token == "+0E0"

    payload = snapshot.to_dict()
    assert payload["profile_id"] == MMCIF_ZERO_OCCUPANCY_PROFILE_ID
    assert payload["source_declarations_preserved"] is True
    assert payload["exact_zero_tokens_verified"] is True
    assert payload["semantic_sequence_references_verified"] is True
    for flag in (
        "atom_site_semantics_interpreted",
        "atom_site_occupancy_crosschecked",
        "coordinate_observation_assessed",
        "missingness_inferred",
        "auth_label_equivalence_inferred",
        "altloc_population_interpreted",
        "occupancy_population_interpreted",
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


def test_category_and_header_order_change_source_binding_not_projection() -> None:
    canonical = parse_mmcif_zero_occupancy_declarations(CANONICAL)
    reordered = parse_mmcif_zero_occupancy_declarations(CATEGORY_ORDER_VARIANT)

    assert canonical.semantic_projection_sha256 == reordered.semantic_projection_sha256
    assert canonical.declaration_projection_sha256 == reordered.declaration_projection_sha256
    assert canonical.source_binding_sha256 != reordered.source_binding_sha256
    assert canonical.snapshot_sha256 != reordered.snapshot_sha256
    assert canonical.source_category_order != reordered.source_category_order


def test_atom_site_is_optional_uninterpreted_and_never_crosschecked() -> None:
    with_atom_site = parse_mmcif_zero_occupancy_declarations(CANONICAL)
    without_atom_site = parse_mmcif_zero_occupancy_declarations(NO_ATOM_SITE)

    assert with_atom_site.declaration_projection_sha256 == without_atom_site.declaration_projection_sha256
    assert with_atom_site.source_binding_sha256 != without_atom_site.source_binding_sha256
    assert with_atom_site.to_dict()["atom_site_occupancy_crosschecked"] is False
    assert without_atom_site.uninterpreted_categories == ()


def test_document_is_canonical_self_verifying_and_written_private(tmp_path: Path) -> None:
    snapshot = parse_mmcif_zero_occupancy_declarations(CANONICAL)
    document = mmcif_zero_occupancy_document(snapshot)

    assert document["schema_id"] == MMCIF_ZERO_OCCUPANCY_DOCUMENT_SCHEMA_ID
    assert require_mmcif_zero_occupancy_document(document) == document
    encoded = mmcif_zero_occupancy_json_bytes(snapshot)
    assert json.loads(encoded) == document

    destination = write_mmcif_zero_occupancy_json(tmp_path / "zero.json", snapshot)
    assert destination.read_bytes() == encoded + b"\n"
    assert stat.S_IMODE(destination.stat().st_mode) == 0o600
    assert not list(tmp_path.glob(".zero.json.*.tmp"))

    tampered = deepcopy(document)
    tampered["declaration_projection"]["residue_declarations"][0]["label_comp_id"] = "PRIVATE"
    with pytest.raises(ValueError, match="projection digest mismatch"):
        require_mmcif_zero_occupancy_document(tampered)


def test_residue_only_and_atom_only_documents_are_supported() -> None:
    residue_only = parse_mmcif_zero_occupancy_declarations(SEMANTIC_PREFIX + RESIDUE_LOOP)
    atom_only = parse_mmcif_zero_occupancy_declarations(SEMANTIC_PREFIX + ATOM_LOOP)

    assert len(residue_only.residue_declarations) == 2
    assert residue_only.atom_declarations == ()
    assert atom_only.residue_declarations == ()
    assert len(atom_only.atom_declarations) == 2


@pytest.mark.parametrize(
    ("old", "new", "code"),
    [
        ("1 Y 0 1 AX GLY AUTH-1 ? A GLY 1", "1 N 0 1 AX GLY AUTH-1 ? A GLY 1", "polymer_flag_not_supported"),
        ("1 Y 0 1 AX GLY AUTH-1 ? A GLY 1", "1 Y 0.5 1 AX GLY AUTH-1 ? A GLY 1", "nonzero_occupancy_flag"),
        ("1 Y 0 1 AX GLY AUTH-1 ? A GLY 1", "1 Y '0' 1 AX GLY AUTH-1 ? A GLY 1", "invalid_occupancy_flag"),
        ("1 Y 0 1 AX GLY AUTH-1 ? A GLY 1", "1 Y ? 1 AX GLY AUTH-1 ? A GLY 1", "invalid_occupancy_flag"),
        ("1 Y 0 1 AX GLY AUTH-1 ? A GLY 1", "1 Y 0 01 AX GLY AUTH-1 ? A GLY 1", "invalid_positive_integer"),
        ("1 Y 0 1 AX GLY AUTH-1 ? A GLY 1", "1 Y 0 1 AX GLY AUTH-1 ? PRIVATE GLY 1", "label_asym_reference_missing"),
        ("1 Y 0 1 AX GLY AUTH-1 ? A GLY 1", "1 Y 0 1 AX GLY AUTH-1 ? A GLY 3", "label_sequence_reference_missing"),
        ("1 Y 0 1 AX GLY AUTH-1 ? A GLY 1", "1 Y 0 1 AX GLY AUTH-1 ? A ALA 1", "label_component_mismatch"),
    ],
)
def test_source_declaration_contracts_fail_closed(old: str, new: str, code: str) -> None:
    _error(_replace_once(CANONICAL, old, new), code)


def test_duplicate_source_and_logical_declarations_are_rejected() -> None:
    duplicate_source = _replace_once(
        CANONICAL,
        "2 Y -0.0E+0 2 AX ALA AUTH-2 '.' A ALA 2",
        "1 Y -0.0E+0 2 AX ALA AUTH-2 '.' A ALA 2",
    )
    _error(duplicate_source, "duplicate_residue_source_id")

    duplicate_logical = _replace_once(
        CANONICAL,
        "2 Y -0.0E+0 2 AX ALA AUTH-2 '.' A ALA 2",
        "2 Y -0.0E+0 1 AX GLY AUTH-2 '.' A GLY 1",
    )
    _error(duplicate_logical, "duplicate_residue_declaration")

    duplicate_atom = _replace_once(
        CANONICAL,
        "2 Y +0E0 1 AX GLY AUTH-1 . CB '?' A GLY 1 CB",
        "2 Y +0E0 1 AX GLY AUTH-1 . CA . A GLY 1 CA",
    )
    _error(duplicate_atom, "duplicate_atom_declaration")


def test_missing_scalar_mixed_and_extra_header_categories_are_rejected() -> None:
    _error(SEMANTIC_PREFIX + ATOM_SITE, "declaration_category_missing")

    scalar = SEMANTIC_PREFIX + "_pdbx_unobs_or_zero_occ_residues.id 1\n"
    _error(scalar, "category_must_be_loop")

    mixed = _replace_once(
        CANONICAL,
        "_pdbx_unobs_or_zero_occ_residues.label_seq_id\n",
        "_pdbx_unobs_or_zero_occ_residues.label_seq_id\n_atom_site.id\n",
    )
    _error(mixed, "mixed_category_loop")

    extra = _replace_once(
        CANONICAL,
        "_pdbx_unobs_or_zero_occ_residues.label_seq_id\n",
        "_pdbx_unobs_or_zero_occ_residues.label_seq_id\n_pdbx_unobs_or_zero_occ_residues.details\n",
    )
    _error(extra, "unsupported_headers")


def test_errors_do_not_echo_private_identity_values() -> None:
    source = _replace_once(
        CANONICAL,
        "1 Y 0 1 AX GLY AUTH-1 ? A GLY 1",
        "1 Y 0 1 AX GLY AUTH-1 ? PRIVATE-ASYM GLY 1",
    )
    error = _error(source, "label_asym_reference_missing")
    assert "PRIVATE-ASYM" not in str(error)
    assert "PRIVATE-ASYM" not in error.detail


def test_input_type_and_integer_bounds_are_enforced() -> None:
    with pytest.raises(TypeError, match="must be a string"):
        parse_mmcif_zero_occupancy_declarations(b"data_x")  # type: ignore[arg-type]

    out_of_bounds = _replace_once(
        CANONICAL,
        "1 Y 0 1 AX GLY AUTH-1 ? A GLY 1",
        f"{1 << 53} Y 0 1 AX GLY AUTH-1 ? A GLY 1",
    )
    _error(out_of_bounds, "positive_integer_out_of_bounds")
