"""Dependency-light parser regressions; package integration stays in screening tests."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest

# Test the actual production file without bootstrapping optional physics backends.
_ROOT = Path(__file__).resolve().parents[2]
_SPEC = importlib.util.spec_from_file_location(
    "biodiscovery_protein_prep_under_test",
    _ROOT / "betelgeuze_engine/biodiscovery/protein_prep.py",
)
assert _SPEC is not None and _SPEC.loader is not None
prep = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(prep)


def _atom(serial=1, *, chain="A", resid=1, residue="ALA", insertion=" ",
          altloc=" ", atom="CA", x="1.000", record="ATOM", element="C"):
    return (
        f"{record:<6}{serial:5d} {atom:^4s}{altloc}{residue:>3s} {chain}{resid:4d}{insertion}   "
        f"{x:>8s}{2.0:8.3f}{3.0:8.3f}{1.0:6.2f}{20.0:6.2f}          {element:>2s}"
    )


_COLUMNS = (
    "group_PDB", "id", "type_symbol", "label_atom_id", "label_comp_id",
    "label_asym_id", "label_seq_id", "Cartn_x", "Cartn_y", "Cartn_z",
    "pdbx_PDB_model_num", "label_alt_id", "pdbx_PDB_ins_code",
    "auth_asym_id", "auth_seq_id",
)


def _row(**changes):
    row = dict(zip(_COLUMNS, (
        "ATOM", "1", "C", "CA", "ALA", "A", "1", "1.000", "2.000", "3.000",
        "1", ".", "?", "A", "1",
    )))
    row.update({key: str(value) for key, value in changes.items()})
    return row


def _cif(rows, columns=_COLUMNS):
    return "\n".join([
        "data_regression", "#", "loop_",
        *(f"_atom_site.{name}" for name in columns),
        *(" ".join(row[name] for name in columns) for row in rows), "#", "",
    ])


@pytest.mark.parametrize("format", ["pdb", "cif"])
def test_distinct_chains_with_reused_residue_numbers(format):
    chains = "ABCDEFGHIJ"
    if format == "pdb":
        text = "\n".join(_atom(i, chain=chain) for i, chain in enumerate(chains, 1))
    else:
        text = _cif([_row(id=i, label_asym_id=chain) for i, chain in enumerate(chains, 1)])
    coords, sequence = prep.parse_pdb_text(text)
    assert coords.shape == (10, 3)
    assert sequence == "A" * 10
    assert prep.validate_protein(coords, sequence)["valid"] is True


@pytest.mark.parametrize("format", ["pdb", "cif", "cif_auth"])
def test_insertion_codes_preserve_one_coordinate_per_residue(format):
    codes = " ABCDEFGHI"
    if format == "pdb":
        text = "\n".join(_atom(i, insertion=code) for i, code in enumerate(codes, 1))
    else:
        rows = [_row(id=i, pdbx_PDB_ins_code=code.strip() or "?")
                for i, code in enumerate(codes, 1)]
        if format == "cif_auth":
            for row in rows:
                row.update(label_asym_id=".", label_seq_id=".")
        text = _cif(rows)
    coords, sequence = prep.parse_pdb_text(text)
    assert coords.shape == (10, 3)
    assert sequence == "A" * 10
    assert prep.validate_protein(coords, sequence)["valid"] is True


def test_negative_pdb_residue_number_and_coordinate_order():
    text = "\n".join([
        _atom(1, resid=-1, residue="GLY", x="5.000"),
        _atom(2, resid=0, x="2.000"),
        _atom(3, resid=-1, insertion="A", residue="SER", x="8.000"),
    ])
    coords, sequence = prep.parse_pdb_text(text)
    assert sequence == "GAS"
    np.testing.assert_array_equal(coords[:, 0], [5.0, 2.0, 8.0])


@pytest.mark.parametrize("format", ["pdb", "cif"])
def test_duplicate_ca_is_rejected_instead_of_inflating_residue_count(format):
    text = _atom() + "\n" + _atom(2) if format == "pdb" else _cif([_row(), _row(id=2)])
    with pytest.raises(ValueError, match="duplicate_protein_ca_residue"):
        prep.parse_pdb_text(text)


@pytest.mark.parametrize("format", ["pdb", "cif"])
@pytest.mark.parametrize("altloc", ["A", "B"])
def test_explicit_alternate_locations_require_preparation(format, altloc):
    text = _atom(altloc=altloc) if format == "pdb" else _cif([_row(label_alt_id=altloc)])
    with pytest.raises(ValueError, match="unsupported_protein_altloc"):
        prep.parse_pdb_text(text)


@pytest.mark.parametrize("format", ["pdb", "cif"])
def test_models_are_never_combined_or_silently_dropped(format):
    if format == "pdb":
        text = f"MODEL        1\n{_atom()}\nENDMDL\nMODEL        2\n{_atom()}\nENDMDL"
    else:
        text = _cif([_row(), _row(id=2, pdbx_PDB_model_num=2)])
    with pytest.raises(ValueError, match="unsupported_multiple_protein_models"):
        prep.parse_pdb_text(text)


@pytest.mark.parametrize("format", ["pdb", "cif"])
@pytest.mark.parametrize("model", [1, 7])
def test_one_explicit_model_is_supported(format, model):
    text = f"MODEL     {model:4d}\n{_atom()}\nENDMDL" if format == "pdb" else _cif([
        _row(pdbx_PDB_model_num=model),
    ])
    coords, sequence = prep.parse_pdb_text(text)
    assert coords.shape == (1, 3)
    assert sequence == "A"


@pytest.mark.parametrize("text", [
    "ENDMDL\n" + _atom(),
    "MODEL        1\n" + _atom(),
    _atom() + "\nMODEL        1\nENDMDL",
    "MODEL        1\nENDMDL\n" + _atom(),
])
def test_malformed_pdb_model_boundaries_fail(text):
    with pytest.raises(ValueError, match="invalid_pdb_model_records"):
        prep.parse_pdb_text(text)


@pytest.mark.parametrize("model", ["0", "-1", "nope", "."])
def test_invalid_cif_model_numbers_fail(model):
    with pytest.raises(ValueError, match="invalid_protein_model_number"):
        prep.parse_pdb_text(_cif([_row(pdbx_PDB_model_num=model)]))


@pytest.mark.parametrize("format", ["pdb", "cif"])
@pytest.mark.parametrize("value,reason", [
    ("nan", "nonfinite"), ("inf", "nonfinite"), ("-inf", "nonfinite"),
    ("bad", "invalid_protein_coordinates"), ("1e39", "out_of_range"),
])
def test_bad_coordinate_rows_are_not_dropped(format, value, reason):
    if format == "pdb":
        text = "\n".join([_atom(), _atom(2, resid=2, x=value)])
    else:
        text = _cif([_row(), _row(id=2, label_seq_id=2, Cartn_x=value)])
    with pytest.raises(ValueError, match=reason):
        prep.parse_pdb_text(text)


@pytest.mark.parametrize("value", [np.nan, np.inf, -np.inf])
def test_validator_rejects_nonfinite_coordinates(value):
    coords = np.zeros((10, 3))
    coords[0, 1] = value
    result = prep.validate_protein(coords, "A" * 10)
    assert result["valid"] is False and result["blocked"] is True
    assert result["reason"] == "nonfinite_protein_coordinates"


@pytest.mark.parametrize("coords", [
    np.ones((10, 2)), np.ones((10, 3, 1)), np.ones(30), np.array(1), None,
])
def test_validator_rejects_bad_shapes(coords):
    result = prep.validate_protein(coords, "A" * 10)
    assert result["valid"] is False and result["blocked"] is True
    assert result["reason"] == "invalid_protein_coords_shape"


@pytest.mark.parametrize("dtype", [bool, complex, object, str])
def test_validator_rejects_nonreal_numeric_dtypes(dtype):
    result = prep.validate_protein(np.ones((10, 3), dtype=dtype), "A" * 10)
    assert result["valid"] is False
    assert result["reason"] == "invalid_protein_coords_dtype"


@pytest.mark.parametrize("dtype", [np.float32, np.float64, np.int32])
def test_validator_accepts_matching_real_arrays(dtype):
    result = prep.validate_protein(np.zeros((10, 3), dtype=dtype), "AGSLVFQWHT")
    assert result == {"valid": True, "blocked": False, "fidelity": "sequence_mapped", "residue_count": 10}


@pytest.mark.parametrize("sequence", ["A", "A" * 9, "A" * 11])
def test_validator_requires_coordinate_sequence_bijection(sequence):
    result = prep.validate_protein(np.zeros((10, 3)), sequence)
    assert result["valid"] is False
    assert result["reason"] == "protein_coordinate_sequence_length_mismatch"


@pytest.mark.parametrize("sequence", [None, "", "  "])
def test_missing_sequence_stays_blocked(sequence):
    result = prep.validate_protein(np.zeros((10, 3)), sequence)
    assert result["reason"] == "placeholder_or_missing_sequence"
    assert result["blocker"] == "placeholder_topology"


@pytest.mark.parametrize("sequence", ["X" * 10, "?" * 10, "A" * 9 + " "])
def test_unknown_sequence_stays_blocked(sequence):
    result = prep.validate_protein(np.zeros((10, 3)), sequence)
    assert result["reason"] == "unknown_residue_in_sequence"
    assert result["valid"] is False


@pytest.mark.parametrize("count,reason", [(0, "empty_protein_coords"), (5, "too_few_residues"),
                                         (5001, "too_many_residues")])
def test_residue_count_limits_are_preserved(count, reason):
    assert prep.validate_protein(np.zeros((count, 3)), "A" * count)["reason"] == reason


def test_mmcif_missing_identity_does_not_use_row_number():
    text = _cif([_row(label_seq_id=".", auth_seq_id="?")])
    with pytest.raises(ValueError, match="missing_protein_residue_identity"):
        prep.parse_pdb_text(text)


def test_mmcif_does_not_mix_label_chain_and_author_residue_number():
    text = _cif([_row(label_seq_id=".", auth_asym_id="?")])
    with pytest.raises(ValueError, match="missing_protein_residue_identity"):
        prep.parse_pdb_text(text)


@pytest.mark.parametrize("suffix", [" extra", "", " 'unclosed"])
def test_mmcif_malformed_row_is_rejected(suffix):
    columns = list(_COLUMNS)
    row = _row()
    values = " ".join(row[name] for name in columns)
    replacement = values.rsplit(" ", 1)[0] if not suffix else values + suffix
    text = _cif([row]).replace(values, replacement)
    with pytest.raises(ValueError, match="invalid_mmcif_atom_site_row"):
        prep.parse_pdb_text(text)


def test_mmcif_blank_lines_and_comments_do_not_truncate_rows():
    text = _cif([_row(), _row(id=2, label_seq_id=2, label_comp_id="GLY")])
    text = text.replace("\nATOM 2", "\n\n# comment\nATOM 2")
    coords, seq = prep.parse_pdb_text(text)
    assert coords.shape == (2, 3)
    assert seq == "AG"


def test_mmcif_multiple_blocks_are_explicitly_unsupported():
    with pytest.raises(ValueError, match="unsupported_multiple_mmcif_data_blocks"):
        prep.parse_pdb_text(_cif([_row()]) + _cif([_row()]))


@pytest.mark.parametrize("format", ["pdb", "cif"])
def test_unsupported_metal_remains_rejected(format):
    text = _atom(record="HETATM", residue="ZN", atom="ZN", element="ZN") if format == "pdb" else _cif([
        _row(group_PDB="HETATM", type_symbol="ZN", label_atom_id="ZN", label_comp_id="ZN"),
    ])
    with pytest.raises(ValueError, match="unsupported_metal:ZN"):
        prep.parse_pdb_text(text)


def test_repository_mmcif_fixture_and_file_resolution_are_preserved():
    path = _ROOT / "tests/fixtures/tier_beta/mini_protein.cif"
    coords, seq = prep.resolve_protein_input(str(path))
    assert coords.shape == (10, 3) and coords.dtype == np.float32
    assert seq == "AGSLVFQWHT"
    assert prep.validate_protein(coords, seq)["valid"] is True
    np.testing.assert_allclose(coords[0], [1.458, 0, 0])


@pytest.mark.parametrize("format", ["pdb", "cif"])
def test_residue_with_atoms_but_no_ca_cannot_disappear(format):
    if format == "pdb":
        text = "\n".join([
            *(_atom(i, resid=i) for i in range(1, 11)),
            _atom(11, resid=11, residue="GLY", atom="N", element="N"),
        ])
    else:
        text = _cif([
            *(_row(id=i, label_seq_id=i) for i in range(1, 11)),
            _row(id=11, label_seq_id=11, label_comp_id="GLY", label_atom_id="N", type_symbol="N"),
        ])
    with pytest.raises(ValueError, match="missing_protein_ca_residue"):
        prep.parse_pdb_text(text)


@pytest.mark.parametrize("format", ["pdb", "cif"])
def test_no_ca_atoms_cannot_fall_back_to_an_all_atom_projection(format):
    text = _atom(atom="N", element="N") if format == "pdb" else _cif([
        _row(label_atom_id="N", type_symbol="N"),
    ])
    with pytest.raises(ValueError, match="missing_protein_ca_residue"):
        prep.parse_pdb_text(text)


@pytest.mark.parametrize("format", ["pdb", "cif"])
@pytest.mark.parametrize("ca_first", [True, False])
def test_all_atoms_of_a_residue_must_agree_on_residue_name(format, ca_first):
    if format == "pdb":
        rows = [_atom(), _atom(2, residue="GLY", atom="N", element="N")]
        text = "\n".join(rows if ca_first else list(reversed(rows)))
    else:
        rows = [_row(), _row(id=2, label_comp_id="GLY", label_atom_id="N", type_symbol="N")]
        text = _cif(rows if ca_first else list(reversed(rows)))
    with pytest.raises(ValueError, match="conflicting_protein_residue_name"):
        prep.parse_pdb_text(text)


@pytest.mark.parametrize("format", ["pdb", "cif"])
def test_complete_residue_projection_keeps_ca_order_and_coordinates(format):
    if format == "pdb":
        text = "\n".join([
            _atom(1, resid=1, atom="N", element="N", residue="GLY"),
            _atom(2, resid=2, x="5.000"),
            _atom(3, resid=1, residue="GLY", x="8.000"),
            _atom(4, resid=2, atom="O", element="O"),
        ])
    else:
        text = _cif([
            _row(id=1, label_seq_id=1, label_atom_id="N", type_symbol="N", label_comp_id="GLY"),
            _row(id=2, label_seq_id=2, Cartn_x="5.000"),
            _row(id=3, label_seq_id=1, label_comp_id="GLY", Cartn_x="8.000"),
            _row(id=4, label_seq_id=2, label_atom_id="O", type_symbol="O"),
        ])
    coords, seq = prep.parse_pdb_text(text)
    assert seq == "AG"
    assert coords.dtype == np.float32
    np.testing.assert_array_equal(coords, [[5.0, 2.0, 3.0], [8.0, 2.0, 3.0]])


@pytest.mark.parametrize("format", ["pdb", "cif"])
def test_water_does_not_create_a_missing_protein_residue(format):
    if format == "pdb":
        text = _atom() + "\n" + _atom(2, resid=2, record="HETATM", residue="HOH", atom="O", element="O")
    else:
        text = _cif([_row(), _row(id=2, group_PDB="HETATM", label_seq_id=".",
                                label_comp_id="HOH", label_atom_id="O", type_symbol="O")])
    coords, seq = prep.parse_pdb_text(text)
    assert coords.shape == (1, 3) and seq == "A"


def _with_occupancy(format, occupancy):
    if format == "pdb":
        atom = _atom()
        return atom[:54] + f"{occupancy:>6s}" + atom[60:]
    return _cif([_row(occupancy=occupancy)], (*_COLUMNS, "occupancy"))


@pytest.mark.parametrize("format", ["pdb", "cif"])
@pytest.mark.parametrize("occupancy,reason", [
    ("0.00", "unsupported_zero_occupancy_atom"),
    ("-0.00", "unsupported_zero_occupancy_atom"),
    ("nan", "invalid_protein_occupancy"),
    ("inf", "invalid_protein_occupancy"),
    ("-0.10", "invalid_protein_occupancy"),
    ("1.10", "invalid_protein_occupancy"),
    ("bad", "invalid_protein_occupancy"),
])
def test_invalid_or_zero_occupancy_requires_explicit_preparation(format, occupancy, reason):
    with pytest.raises(ValueError, match=reason):
        prep.parse_pdb_text(_with_occupancy(format, occupancy))


@pytest.mark.parametrize("format", ["pdb", "cif"])
@pytest.mark.parametrize("occupancy", ["0.25", "1.00"])
def test_positive_occupancy_keeps_coordinates(format, occupancy):
    coords, seq = prep.parse_pdb_text(_with_occupancy(format, occupancy))
    np.testing.assert_array_equal(coords, [[1.0, 2.0, 3.0]])
    assert seq == "A"


def test_absent_occupancy_preserves_existing_restricted_input_support():
    atom = _atom()
    pdb_coords, pdb_seq = prep.parse_pdb_text(atom[:54] + " " * 6 + atom[60:])
    cif_coords, cif_seq = prep.parse_pdb_text(_cif([_row()]))
    np.testing.assert_array_equal(pdb_coords, cif_coords)
    assert pdb_seq == cif_seq == "A"


@pytest.mark.parametrize("format", ["pdb", "cif"])
def test_invalid_file_encoding_is_not_silently_repaired(tmp_path, format):
    text = _atom() if format == "pdb" else _cif([_row()])
    path = tmp_path / ("damaged." + format)
    path.write_bytes(text.encode("utf-8").replace(b"ATOM", b"AT\xffOM", 1))
    with pytest.raises(ValueError, match="invalid_protein_file_encoding"):
        prep.resolve_protein_input(str(path))


@pytest.mark.parametrize("format", ["pdb", "cif"])
def test_utf8_bom_file_matches_unmarked_input(tmp_path, format):
    text = _atom() if format == "pdb" else _cif([_row()])
    path = tmp_path / ("bom." + format)
    path.write_bytes(text.encode("utf-8-sig"))
    coords, seq = prep.resolve_protein_input(str(path))
    expected_coords, expected_seq = prep.parse_pdb_text(text)
    np.testing.assert_array_equal(coords, expected_coords)
    assert seq == expected_seq


@pytest.mark.parametrize("error", [PermissionError, FileNotFoundError, OSError])
def test_file_read_errors_remain_preparation_errors(tmp_path, monkeypatch, error):
    path = tmp_path / "unreadable.pdb"
    path.write_text(_atom(), encoding="utf-8")

    def fail_read(*args, **kwargs):
        raise error("simulated file read failure")

    monkeypatch.setattr("builtins.open", fail_read)
    with pytest.raises(ValueError, match="unreadable_protein_file"):
        prep.resolve_protein_input(str(path))
