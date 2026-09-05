"""Dependency-light parser tests: no docking, native execution, or holdout access."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
# Load the real module without importing the optional screening/simulation stack.
_SPEC = importlib.util.spec_from_file_location(
    "biodiscovery_protein_prep_under_test",
    ROOT / "betelgeuze_engine/biodiscovery/protein_prep.py",
)
assert _SPEC is not None and _SPEC.loader is not None
prep = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(prep)


def pdb_atom(
    serial: int = 1, *, chain: str = "A", residue_id: int = 1,
    residue: str = "ALA", insertion: str = " ", altloc: str = " ",
    atom_name: str = "CA", x: float = 1.0, record: str = "ATOM", element: str = "C",
) -> str:
    return (
        f"{record:<6}{serial:5d} {atom_name:^4s}{altloc}{residue:>3s} {chain}"
        f"{residue_id:4d}{insertion}   {x:8.3f}{2.0:8.3f}{3.0:8.3f}"
        f"{1.0:6.2f}{20.0:6.2f}          {element:>2s}"
    )


def cif_row(**changes: str) -> dict[str, str]:
    row = {
        "group_PDB": "ATOM", "id": "1", "type_symbol": "C", "label_atom_id": "CA",
        "label_comp_id": "ALA", "label_asym_id": "A", "label_seq_id": "1",
        "auth_asym_id": "A", "auth_seq_id": "1", "pdbx_PDB_ins_code": "?",
        "label_alt_id": ".", "Cartn_x": "1.0", "Cartn_y": "2.0", "Cartn_z": "3.0",
        "pdbx_PDB_model_num": "1",
    }
    row.update(changes)
    return row


def cif_text(rows: list[dict[str, str]]) -> str:
    headers = list(rows[0])
    return "\n".join([
        "data_test", "#", "loop_", *[f"_atom_site.{key}" for key in headers],
        *[" ".join(row[key] for key in headers) for row in rows], "#", "",
    ])


def assert_projection(text: str, sequence: str) -> None:
    coords, actual = prep.parse_pdb_text(text)
    assert actual == sequence
    assert coords.shape == (len(sequence), 3)
    assert coords.dtype == np.float32
    assert np.isfinite(coords).all()
    assert prep.validate_protein(coords, actual)["valid"] is (len(sequence) >= 10)


def test_normal_pdb_keeps_ca_projection_and_atom_order():
    text = "\n".join(
        pdb_atom(2 * i + j, residue_id=i, atom_name=name, x=float(i))
        for i in range(1, 11) for j, name in enumerate(("N", "CA"))
    )
    assert_projection(text, "A" * 10)
    coords, _ = prep.parse_pdb_text(text)
    np.testing.assert_array_equal(coords[:, 0], np.arange(1, 11))


def test_existing_mmcif_fixture_keeps_sequence_and_coordinates():
    text = (ROOT / "tests/fixtures/tier_beta/mini_protein.cif").read_text(encoding="utf-8")
    assert_projection(text, "AGSLVFQWHT")
    coords, _ = prep.parse_pdb_text(text)
    np.testing.assert_array_equal(coords[0], np.array([1.458, 0, 0], dtype=np.float32))
    np.testing.assert_array_equal(coords[-1], np.array([30.2, 14.9, 0], dtype=np.float32))


def test_pdb_chain_identity_is_not_collapsed():
    text = "\n".join(
        pdb_atom(i, chain=chr(64 + i), residue="ALA" if i % 2 else "GLY")
        for i in range(1, 11)
    )
    assert_projection(text, "AG" * 5)


def test_pdb_insertion_identity_is_not_collapsed():
    assert_projection("\n".join(
        pdb_atom(i, insertion=chr(64 + i)) for i in range(1, 11)
    ), "A" * 10)


@pytest.mark.parametrize("residue_id", [-1, 0, 42])
def test_pdb_blank_chain_and_signed_residue_id_are_supported(residue_id):
    assert_projection(pdb_atom(chain=" ", residue_id=residue_id), "A")


@pytest.mark.parametrize("model_id", [1, 2])
def test_single_explicit_pdb_model_is_supported(model_id):
    text = f"MODEL     {model_id:4d}\n{pdb_atom()}\nENDMDL\nEND\n"
    assert_projection(text, "A")


def test_pdb_models_cannot_combine_to_pass_minimum_size():
    atoms = "\n".join(pdb_atom(i, residue_id=i) for i in range(1, 6))
    with pytest.raises(ValueError, match="unsupported_multiple_models"):
        prep.parse_pdb_text(f"MODEL        1\n{atoms}\nENDMDL\nMODEL        2\n{atoms}\nENDMDL")


@pytest.mark.parametrize("text", [
    "ENDMDL", f"MODEL        1\n{pdb_atom()}",
    f"{pdb_atom()}\nMODEL        1\nENDMDL",
    f"MODEL        1\n{pdb_atom()}\nENDMDL\n{pdb_atom(residue_id=2)}",
    f"MODEL        0\n{pdb_atom()}\nENDMDL",
    f"MODEL      bad\n{pdb_atom()}\nENDMDL",
])
def test_pdb_malformed_model_records_are_rejected(text):
    with pytest.raises(ValueError, match="invalid_model_records"):
        prep.parse_pdb_text(text)


@pytest.mark.parametrize("altloc", ["A", "B"])
@pytest.mark.parametrize("atom_name", ["CA", "CB"])
def test_pdb_alternate_locations_require_upstream_selection(altloc, atom_name):
    with pytest.raises(ValueError, match="unsupported_alternate_location"):
        prep.parse_pdb_text(pdb_atom(altloc=altloc, atom_name=atom_name))


@pytest.mark.parametrize("residue", ["ALA", "GLY"])
def test_pdb_duplicate_ca_identity_is_rejected_even_nonconsecutively(residue):
    text = "\n".join([pdb_atom(), pdb_atom(2, residue_id=2), pdb_atom(3, residue=residue)])
    with pytest.raises(ValueError, match="duplicate_ca_residue"):
        prep.parse_pdb_text(text)


@pytest.mark.parametrize("field", ["    ", "abcd"])
def test_pdb_missing_or_bad_residue_number_is_not_invented(field):
    atom = pdb_atom()
    with pytest.raises(ValueError, match="invalid_residue_identity"):
        prep.parse_pdb_text(atom[:22] + field + atom[26:])


@pytest.mark.parametrize("x", [float("nan"), float("inf"), -float("inf")])
@pytest.mark.parametrize("atom_name", ["CA", "N"])
def test_pdb_nonfinite_atoms_are_rejected_before_projection(x, atom_name):
    with pytest.raises(ValueError, match="nonfinite_atom_coordinates"):
        prep.parse_pdb_text(pdb_atom(x=x, atom_name=atom_name))


@pytest.mark.parametrize("bad_x", ["        ", " garbage"])
def test_pdb_malformed_atoms_are_not_silently_dropped(bad_x):
    bad = pdb_atom(99, atom_name="N", residue_id=99)
    text = "\n".join([pdb_atom(i, residue_id=i) for i in range(1, 11)])
    with pytest.raises(ValueError, match="invalid_atom_coordinates"):
        prep.parse_pdb_text(text + "\n" + bad[:30] + bad_x + bad[38:])


@pytest.mark.parametrize("format_name", ["pdb", "cif"])
@pytest.mark.parametrize("element,residue,reason", [
    ("FE", "FE", "unsupported_metal:FE"),
    ("C", "LIG", "unsupported_cofactor_or_bound_ligand:LIG"),
])
def test_existing_heterogen_guards_are_preserved(format_name, element, residue, reason):
    text = pdb_atom(record="HETATM", element=element, residue=residue, atom_name=element)
    if format_name == "cif":
        text = cif_text([cif_row(group_PDB="HETATM", type_symbol=element, label_comp_id=residue)])
    with pytest.raises(ValueError, match=reason):
        prep.parse_pdb_text(text)


def test_water_does_not_change_ca_projection():
    text = pdb_atom() + "\n" + pdb_atom(2, record="HETATM", residue="HOH", atom_name="O", element="O")
    assert_projection(text, "A")


def test_no_ca_fallback_cannot_masquerade_as_sequence_mapped():
    coords, sequence = prep.parse_pdb_text("\n".join(
        pdb_atom(i, residue_id=i, atom_name="N") for i in range(1, 11)
    ))
    assert coords.shape == (10, 3)
    assert sequence == ""
    assert prep.validate_protein(coords, sequence)["reason"] == "placeholder_or_missing_sequence"


def test_mmcif_distinct_label_chains_are_preserved():
    assert_projection(cif_text([
        cif_row(id=str(i), label_asym_id=chr(64 + i)) for i in range(1, 11)
    ]), "A" * 10)


def test_mmcif_author_fallback_preserves_insertion_codes():
    assert_projection(cif_text([
        cif_row(id=str(i), label_seq_id=".", pdbx_PDB_ins_code=chr(64 + i))
        for i in range(1, 11)
    ]), "A" * 10)


def test_mmcif_author_fallback_uses_author_chain_not_label_chain():
    assert_projection(cif_text([
        cif_row(id=str(i), label_seq_id="?", auth_asym_id=chr(64 + i))
        for i in range(1, 11)
    ]), "A" * 10)


def test_mmcif_label_namespace_does_not_collapse_repeated_author_ids():
    assert_projection(cif_text([
        cif_row(id=str(i), label_seq_id=str(i)) for i in range(1, 11)
    ]), "A" * 10)


@pytest.mark.parametrize("changes", [
    {"label_seq_id": ".", "auth_seq_id": "."},
    {"label_seq_id": ".", "auth_asym_id": "?"},
    {"label_asym_id": ".", "auth_asym_id": "?"},
])
def test_mmcif_incomplete_residue_identity_is_not_invented(changes):
    with pytest.raises(ValueError, match="invalid_residue_identity"):
        prep.parse_pdb_text(cif_text([cif_row(**changes)]))


@pytest.mark.parametrize("changes", [{}, {"label_seq_id": "."}])
def test_mmcif_duplicate_ca_residue_is_rejected(changes):
    with pytest.raises(ValueError, match="duplicate_ca_residue"):
        prep.parse_pdb_text(cif_text([cif_row(**changes), cif_row(id="2", **changes)]))


@pytest.mark.parametrize("model", ["1", "2"])
def test_mmcif_single_model_is_supported(model):
    assert_projection(cif_text([cif_row(pdbx_PDB_model_num=model)]), "A")


def test_mmcif_without_model_column_is_supported():
    row = cif_row()
    del row["pdbx_PDB_model_num"]
    assert_projection(cif_text([row]), "A")


def test_mmcif_multiple_models_are_not_silently_selected():
    text = cif_text([cif_row(), cif_row(id="2", pdbx_PDB_model_num="2")])
    with pytest.raises(ValueError, match="unsupported_multiple_models"):
        prep.parse_pdb_text(text)


@pytest.mark.parametrize("model", ["0", "-1", "?", ".", "not_a_model"])
def test_mmcif_invalid_model_ids_are_rejected(model):
    with pytest.raises(ValueError, match="invalid_model_records"):
        prep.parse_pdb_text(cif_text([cif_row(pdbx_PDB_model_num=model)]))


@pytest.mark.parametrize("altloc", ["A", "B"])
def test_mmcif_alternate_locations_require_upstream_selection(altloc):
    with pytest.raises(ValueError, match="unsupported_alternate_location"):
        prep.parse_pdb_text(cif_text([cif_row(label_alt_id=altloc)]))


@pytest.mark.parametrize("x", ["NaN", "inf", "-inf"])
def test_mmcif_nonfinite_coordinates_are_rejected(x):
    with pytest.raises(ValueError, match="nonfinite_atom_coordinates"):
        prep.parse_pdb_text(cif_text([cif_row(Cartn_x=x)]))


@pytest.mark.parametrize("x", ["1e39", "-1e39", "1e300"])
def test_mmcif_coordinates_cannot_overflow_float32(x):
    with pytest.raises(ValueError, match="atom_coordinates_out_of_range"):
        prep.parse_pdb_text(cif_text([cif_row(Cartn_x=x)]))


@pytest.mark.parametrize("x", ["?", ".", "not_a_coordinate"])
def test_mmcif_invalid_coordinates_are_not_dropped(x):
    with pytest.raises(ValueError, match="invalid_atom_coordinates"):
        prep.parse_pdb_text(cif_text([cif_row(Cartn_x=x)]))


@pytest.mark.parametrize("bad_row", ["ATOM 1", "ATOM 1 'unterminated"])
def test_mmcif_bad_rows_are_not_silently_skipped(bad_row):
    text = cif_text([cif_row()]) + bad_row + "\n"
    with pytest.raises(ValueError, match="invalid_mmcif_atom_site_row"):
        prep.parse_pdb_text(text)


def test_mmcif_comments_do_not_hide_later_atoms():
    text = cif_text([cif_row()]) + "\n" + " ".join(cif_row(id="2", label_seq_id="2").values()) + "\n"
    assert_projection(text, "AA")


def test_mmcif_multiple_blocks_are_rejected():
    with pytest.raises(ValueError, match="unsupported_mmcif_multiple_data_blocks"):
        prep.parse_pdb_text(cif_text([cif_row()]) + cif_text([cif_row()]))


@pytest.mark.parametrize("coords", [
    None, np.array(1), np.ones(10), np.ones((10, 2)), np.ones((10, 4)), np.ones((10, 3, 1)),
    [[1, 2, 3]] * 10,
])
def test_validator_rejects_wrong_coordinate_shapes_without_crashing(coords):
    result = prep.validate_protein(coords, "A" * 10)
    assert result["valid"] is False and result["blocked"] is True
    assert result["reason"] == "invalid_protein_coordinate_shape"


@pytest.mark.parametrize("dtype", [object, str, complex, bool])
def test_validator_requires_real_numeric_coordinates(dtype):
    result = prep.validate_protein(np.ones((10, 3), dtype=dtype), "A" * 10)
    assert result["valid"] is False
    assert result["reason"] == "invalid_protein_coordinate_dtype"


@pytest.mark.parametrize("dtype", [np.float32, np.float64, np.int64, np.uint32])
def test_validator_accepts_finite_real_coordinates(dtype):
    result = prep.validate_protein(np.ones((10, 3), dtype=dtype), "A" * 10)
    assert result == {"valid": True, "blocked": False, "fidelity": "sequence_mapped", "residue_count": 10}


@pytest.mark.parametrize("bad", [np.nan, np.inf, -np.inf])
def test_validator_rejects_nonfinite_coordinates(bad):
    coords = np.ones((10, 3))
    coords[3, 1] = bad
    assert prep.validate_protein(coords, "A" * 10)["reason"] == "nonfinite_protein_coordinates"


@pytest.mark.parametrize("sequence", ["A", "A" * 9, "A" * 11])
def test_validator_requires_one_sequence_residue_per_coordinate(sequence):
    result = prep.validate_protein(np.ones((10, 3)), sequence)
    assert result["valid"] is False
    assert result["reason"] == "protein_coordinate_sequence_length_mismatch"


@pytest.mark.parametrize("sequence,reason", [
    ("", "placeholder_or_missing_sequence"), (None, "placeholder_or_missing_sequence"),
    (" " * 10, "placeholder_or_missing_sequence"), ("X" * 10, "unknown_residue_in_sequence"),
    ("A" * 9 + "?", "invalid_protein_sequence"), ("A" * 9 + " "+"A", "invalid_protein_sequence"),
])
def test_validator_sequence_errors_remain_blocked(sequence, reason):
    result = prep.validate_protein(np.ones((10, 3)), sequence)
    assert result["valid"] is False and result["blocked"] is True
    assert result["reason"] == reason
    assert result["blocker"] == "placeholder_topology"


@pytest.mark.parametrize("n,reason", [(0, "empty_protein_coords"), (9, "too_few_residues"), (5001, "too_many_residues")])
def test_validator_preserves_residue_count_bounds(n, reason):
    assert prep.validate_protein(np.ones((n, 3)), "A" * n)["reason"] == reason


def test_file_resolution_preserves_the_same_parser(tmp_path):
    path = tmp_path / "protein.pdb"
    text = "\n".join(pdb_atom(i, residue_id=i) for i in range(1, 11))
    path.write_text(text, encoding="utf-8")
    direct, sequence = prep.resolve_protein_input(text)
    from_file, from_file_sequence = prep.resolve_protein_input(str(path))
    np.testing.assert_array_equal(from_file, direct)
    assert from_file_sequence == sequence == "A" * 10


@pytest.mark.parametrize("label_seq", ["0", "-1", "invalid", "1.5"])
def test_mmcif_invalid_label_sequence_ids_are_rejected(label_seq):
    with pytest.raises(ValueError, match="invalid_residue_identity"):
        prep.parse_pdb_text(cif_text([cif_row(label_seq_id=label_seq)]))


def test_mmcif_numeric_label_alias_does_not_duplicate_a_residue():
    with pytest.raises(ValueError, match="duplicate_ca_residue"):
        prep.parse_pdb_text(cif_text([cif_row(), cif_row(id="2", label_seq_id="01")]))


def test_mmcif_mixed_identity_namespaces_are_not_combined():
    with pytest.raises(ValueError, match="inconsistent_residue_identity"):
        prep.parse_pdb_text(cif_text([cif_row(), cif_row(id="2", label_seq_id=".")]))
