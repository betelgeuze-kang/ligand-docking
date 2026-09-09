"""Fresh schema, chemistry, invariance and scalar-reference development controls."""
import copy
import math

import numpy as np
import pytest
from rdkit import Chem
from rdkit.Chem import AllChem

from betelgeuze_engine.product import des370k_interaction as bridge

UNITS = {"xyz": "angstrom", "charge0": "elementary charge",
         "charge1": "elementary charge", "cbs_CCSD(T)_all": "kcal/mol"}


def fixture(smiles=("O", "NC=O")):
    mols = []
    for side, smi in enumerate(smiles):
        mol = Chem.AddHs(Chem.MolFromSmiles(smi))
        assert AllChem.EmbedMolecule(mol, randomSeed=519 + side) == 0
        conf = mol.GetConformer()
        for i, xyz in enumerate(conf.GetPositions()):
            conf.SetAtomPosition(i, xyz + np.array([5.0 * side, 0, 0]))
        mols.append(mol)
    mol = Chem.CombineMols(*mols)
    row = {"smiles0": smiles[0], "smiles1": smiles[1],
           "natoms0": str(mols[0].GetNumAtoms()), "natoms1": str(mols[1].GetNumAtoms()),
           "charge0": str(Chem.GetFormalCharge(mols[0])), "charge1": str(Chem.GetFormalCharge(mols[1])),
           "system_id": "19", "group_id": "23", "geom_id": "129", "k_index": "0",
           "group_orig": "synthetic_schema_control", "cbs_CCSD(T)_all": "0.0",
           "nn_CCSD(T)_all": "4321", "role": "evaluation", "evaluation_only": True}
    return record(mol, row)


def record(mol, row):
    row = dict(row)
    row["xyz"] = " ".join(str(float(x)) for x in mol.GetConformer().GetPositions().ravel())
    row["elements"] = " ".join(atom.GetSymbol() for atom in mol.GetAtoms())
    return row, Chem.MolToMolBlock(mol)


def evaluate(row, block, **kw):
    return bridge.evaluate_native_dimer(row, block, units=UNITS,
                                       parameter_profile=bridge.PARAMETER_PROFILE, **kw)


def test_native_zero_reference_and_evidence_are_preserved():
    row, block = fixture()
    before = copy.deepcopy(row)
    result = evaluate(row, block)
    assert row == before == result["native_record"]
    assert result["reference"]["value"] == 0.0
    assert result["residual_target"]["value_kcal_per_mol"] == -result["baseline"]["quantities"]["cross_total_kcal_per_mol"]
    assert result["reference"]["atom_forces"] is None
    assert result["residual_target"]["force_labels"] is None
    assert result["reference"]["evidence_kind"] == "external_computed_reference"
    assert not result["experimental_label_used"] and not result["customer_execution"]
    assert result["native_record"]["evaluation_only"] is True
    assert result["provenance"]["parameter_source"]["native_partial_charges_supplied"] is False
    assert "not UFF" in result["provenance"]["parameter_source"]["mixing"]


def test_existing_v2_energy_matches_independent_scalar_sum():
    row, block = fixture()
    systems, params, _ = bridge.prepare_native_dimer(row, block, units=UNITS,
                                                    parameter_profile=bridge.PARAMETER_PROFILE)
    result = evaluate(row, block)
    energy = 0.0
    for i, first in enumerate(params[0]):
        for j, second in enumerate(params[1]):
            r = float(np.linalg.norm(systems[0].coordinates[0, i].numpy() - systems[1].coordinates[0, j].numpy()))
            assert r < 18.0  # this fixture is within the unchanged switch start
            sigma = (first["sigma_angstrom"] + second["sigma_angstrom"]) / 2
            epsilon = math.sqrt(first["epsilon_kcal_per_mol"] * second["epsilon_kcal_per_mol"])
            energy += 4 * epsilon * ((sigma / r) ** 12 - (sigma / r) ** 6)
            energy += 332.063713299 * first["charge_e"] * second["charge_e"] / r
    assert result["baseline"]["quantities"]["cross_total_kcal_per_mol"] == pytest.approx(energy, abs=1e-10)


def test_rigid_rotation_translation_and_atom_permutation():
    row, block = fixture(("c1ccncc1", "NC=O"))
    mol = Chem.MolFromMolBlock(block, removeHs=False)
    # Start every comparison from the same MOL-rounded coordinates.
    row, block = record(mol, row)
    base = evaluate(row, block)["baseline"]["quantities"]
    rotation = np.array([[0., -1., 0.], [1., 0., 0.], [0., 0., 1.]])
    for i, xyz in enumerate(mol.GetConformer().GetPositions()):
        mol.GetConformer().SetAtomPosition(i, rotation @ xyz + [4., -7., 2.])
    moved = evaluate(*record(mol, row))["baseline"]["quantities"]
    assert moved["cross_total_kcal_per_mol"] == pytest.approx(base["cross_total_kcal_per_mol"], abs=1e-10)
    for side in ["receptor", "ligand"]:
        name = side + "_cross_forces_kcal_per_mol_angstrom"
        np.testing.assert_allclose(moved[name], np.asarray(base[name]) @ rotation.T, atol=1e-10)
    count0 = int(row["natoms0"])
    order = list(reversed(range(count0))) + list(reversed(range(count0, mol.GetNumAtoms())))
    permuted = evaluate(*record(Chem.RenumberAtoms(mol, order), row))["baseline"]["quantities"]
    assert permuted["cross_total_kcal_per_mol"] == pytest.approx(moved["cross_total_kcal_per_mol"], abs=1e-10)
    for side in ["receptor", "ligand"]:
        name = side + "_cross_forces_kcal_per_mol_angstrom"
        np.testing.assert_allclose(permuted[name], np.asarray(moved[name])[::-1], atol=1e-10)


@pytest.mark.parametrize("column,value,reason", [
    ("natoms0", True, "invalid_integer"), ("natoms1", "2.5", "invalid_integer"),
    ("charge0", "1", "charged_monomer"), ("xyz", "NaN", "nonfinite_number"),
    ("elements", "C", "atom_coordinate_count"), ("smiles0", "N", "smiles_chemistry"),
    ("cbs_CCSD(T)_all", "inf", "nonfinite_number"), ("cbs_CCSD(T)_all", True, "invalid_number"),
])
def test_invalid_native_fields_have_no_fallback(column, value, reason):
    row, block = fixture()
    row[column] = value
    with pytest.raises(bridge.DimerInputError, match=reason):
        evaluate(row, block)


def test_nn_prediction_does_not_substitute_for_missing_computed_reference():
    row, block = fixture()
    del row["cbs_CCSD(T)_all"]
    with pytest.raises(KeyError, match="cbs_CCSD"):
        evaluate(row, block)


@pytest.mark.parametrize("units", [{}, {**UNITS, "xyz": "bohr"}, {**UNITS, "cbs_CCSD(T)_all": "hartree"}])
def test_units_are_not_guessed(units):
    row, block = fixture()
    with pytest.raises(bridge.DimerInputError, match="units"):
        bridge.prepare_native_dimer(row, block, units=units, parameter_profile=bridge.PARAMETER_PROFILE)


def test_explicit_profile_is_required():
    row, block = fixture()
    with pytest.raises(bridge.DimerInputError, match="explicit_development_parameter_profile_required"):
        bridge.prepare_native_dimer(row, block, units=UNITS, parameter_profile="measured_charges")


def test_missing_hydrogen_coordinates_are_rejected():
    row, block = fixture()
    mol = Chem.RemoveHs(Chem.MolFromMolBlock(block, removeHs=False))
    row["natoms0"], row["natoms1"] = "1", "3"
    row, block = record(mol, row)
    with pytest.raises(bridge.DimerInputError, match="hydrogen_coordinates_incomplete"):
        evaluate(row, block)


def test_mol_and_csv_coordinate_mapping_must_agree():
    row, block = fixture()
    values = row["xyz"].split()
    values[0] = str(float(values[0]) + .01)
    row["xyz"] = " ".join(values)
    with pytest.raises(bridge.DimerInputError, match="coordinate_mapping_mismatch"):
        evaluate(row, block)


def test_shadow_geometry_scoring_never_accesses_labels_or_role():
    row, block = fixture()
    class Guarded(dict):
        def __getitem__(self, key):
            assert key in bridge.GEOMETRY_FIELDS, "label access before prediction freeze"
            return super().__getitem__(key)
        def keys(self):
            raise AssertionError("must not copy a full record")
    result = bridge.score_native_dimer(Guarded(row), block, units=UNITS,
                                      parameter_profile=bridge.PARAMETER_PROFILE)
    assert set(result["native_record"]) == set(bridge.GEOMETRY_FIELDS)
    assert "reference" not in result and "residual_target" not in result
