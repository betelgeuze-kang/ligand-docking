from __future__ import annotations

import builtins
import hashlib
import io

import numpy as np
import pytest

from betelgeuze_engine.biodiscovery import ligand_prep
from betelgeuze_engine.biodiscovery.pose import generate_conformers

Chem = pytest.importorskip("rdkit.Chem")
pytestmark = pytest.mark.requires_rdkit


def _molblock(smiles: str, *, reverse: bool = False, explicit_h: bool = False) -> str:
    mol = Chem.MolFromSmiles(smiles)
    assert mol is not None
    if explicit_h:
        mol = Chem.AddHs(mol)
    if reverse:
        mol = Chem.RenumberAtoms(mol, list(reversed(range(mol.GetNumAtoms()))))
    return Chem.MolToMolBlock(mol)


@pytest.mark.parametrize("explicit_h", [False, True])
def test_reordered_ethanol_has_same_coordinate_topology_and_generated_coordinates(explicit_h):
    inputs = [
        ligand_prep.resolve_ligand_input(_molblock("CCO", reverse=reverse, explicit_h=explicit_h))
        for reverse in (False, True)
    ]
    results = [ligand_prep.validate_ligand(item.smiles, item) for item in inputs]
    assert [item.smiles for item in inputs] == ["CCO", "CCO"]
    for result in results:
        assert result["atom_count"] == 3
        assert result["atom_elements"] == ["C", "C", "O"]
        assert result["atom_mapping_status"] == "exact_chemical_identity"
    assert results[0]["atom_order_sha256"] == results[1]["atom_order_sha256"]
    assert results[0]["bonds"] == results[1]["bonds"]
    assert results[0]["coordinate_to_source_atom_indices"] != results[1]["coordinate_to_source_atom_indices"]
    np.testing.assert_array_equal(
        generate_conformers(inputs[0].smiles, 1, 0),
        generate_conformers(inputs[1].smiles, 1, 0),
    )


@pytest.mark.parametrize("smiles", ["CCO", "[13CH3]CO", "[NH4+]", "c1ccccc1O", "C[C@H](O)F", "F/C=C/F"])
def test_mapping_preserves_identity_and_original_indices_after_hydrogen_removal(smiles):
    block = _molblock(smiles, reverse=True, explicit_h=True)
    source = Chem.MolFromMolBlock(block, removeHs=False)
    resolved = ligand_prep.resolve_ligand_input(block)
    result = ligand_prep.validate_ligand(resolved.smiles, resolved)
    state = Chem.MolFromSmiles(resolved.smiles)
    forward = result["coordinate_to_source_atom_indices"]
    backward = result["source_to_coordinate_atom_indices"]
    assert len(forward) == state.GetNumAtoms()
    assert len(backward) == source.GetNumAtoms()
    removed = resolved.provenance["removed_source_hydrogen_indices"]
    assert removed == [atom.GetIdx() for atom in source.GetAtoms() if atom.GetAtomicNum() == 1]
    for idx in removed:
        assert backward[idx] is None
    for idx, source_idx in enumerate(forward):
        assert backward[source_idx] == idx
        actual, original = state.GetAtomWithIdx(idx), source.GetAtomWithIdx(source_idx)
        assert (actual.GetAtomicNum(), actual.GetIsotope(), actual.GetFormalCharge(), actual.GetIsAromatic()) == (
            original.GetAtomicNum(), original.GetIsotope(), original.GetFormalCharge(), original.GetIsAromatic(),
        )
    for bond in state.GetBonds():
        original = source.GetBondBetweenAtoms(forward[bond.GetBeginAtomIdx()], forward[bond.GetEndAtomIdx()])
        assert original is not None
        assert original.GetBondType() == bond.GetBondType()
        assert original.GetIsAromatic() == bond.GetIsAromatic()
        assert original.GetStereo() == bond.GetStereo()
    source_topology = result["input_provenance"]["source_topology"]
    assert source_topology["atom_count"] == source.GetNumAtoms()
    assert source_topology["coordinates_used_for_docking"] is False
    assert len(source_topology["coordinates"]) == source.GetNumAtoms()


def test_state_order_is_validated_and_remapped_even_when_input_order_differs():
    resolved = ligand_prep.resolve_ligand_input(_molblock("CCO"))
    result = ligand_prep.validate_ligand("OCC", resolved)
    assert result["coordinate_smiles"] == "OCC"
    assert result["atom_elements"] == ["O", "C", "C"]
    assert result["coordinate_to_source_atom_indices"] == [2, 1, 0]
    assert result["source_to_coordinate_atom_indices"] == [2, 1, 0]
    assert result["input_provenance"]["canonical_to_source_atom_indices"] == [0, 1, 2]


@pytest.mark.parametrize(("source", "state"), [
    ("CCO", "CCN"),  # element
    ("CCO", "[13CH3]CO"),  # isotope
    ("CCO", "CC[O-]"),  # protonation and formal charge
    ("CCO", "COC"),  # connectivity
    ("CCO", "CC=O"),  # bond order
    ("c1ccccc1", "C1CCCCC1"),  # aromaticity
    ("C[C@H](O)F", "C[C@@H](O)F"),  # tetrahedral stereo
    ("F/C=C/F", "F/C=C\\F"),  # bond stereo
    ("CCO", "CC"),  # atom count
])
def test_changed_state_keeps_input_evidence_without_claiming_source_mapping(source, state):
    resolved = ligand_prep.resolve_ligand_input(_molblock(source))
    result = ligand_prep.validate_ligand(state, resolved)
    assert result["atom_mapping_status"] == "not_available_chemical_state_changed"
    assert result["coordinate_to_source_atom_indices"] is None
    assert result["source_to_coordinate_atom_indices"] is None
    assert result["input_provenance"] == resolved.provenance
    assert result["atom_elements"] == [atom.GetSymbol() for atom in Chem.MolFromSmiles(state).GetAtoms()]
    assert result["formal_charges"] == [atom.GetFormalCharge() for atom in Chem.MolFromSmiles(state).GetAtoms()]


@pytest.mark.parametrize("smiles", ["[2H]C", "[3H]O", "[H][H]", "[H-]"])
def test_unsupported_hydrogen_states_are_explicitly_rejected(smiles):
    mol = Chem.MolFromSmiles(smiles)
    with pytest.raises(ValueError, match="unsupported_.*hydrogen"):
        ligand_prep.resolve_ligand_input(Chem.MolToMolBlock(mol))


def test_blank_title_is_preserved_for_inline_molblock():
    block = _molblock("CCO")
    assert block.startswith("\n")
    result = ligand_prep.resolve_ligand_input(block)
    assert result.source_kind == "sdf_text"
    assert result.smiles == "CCO"
    assert result.provenance["input_content_sha256"] == hashlib.sha256(block.encode("utf-8")).hexdigest()


@pytest.mark.parametrize("separator", ["$$$$\n", ""])
def test_single_ligand_path_rejects_multiple_sdf_records(separator):
    with pytest.raises(ValueError, match="multiple_or_invalid_records"):
        ligand_prep.resolve_ligand_input(_molblock("CCO") + separator + _molblock("CCN") + "$$$$\n")


def test_single_sdf_record_with_properties_and_terminator_is_accepted():
    sdf = _molblock("CCO") + ">  <identifier>\nsynthetic ethanol\n\n$$$$\n"
    assert ligand_prep.resolve_ligand_input(sdf).smiles == "CCO"


def test_extra_empty_sdf_record_is_rejected():
    with pytest.raises(ValueError, match="multiple_or_invalid_records"):
        ligand_prep.resolve_ligand_input(_molblock("CCO") + "$$$$\n$$$$\n")


def test_supplied_snapshot_must_be_the_bytes_that_were_parsed():
    with pytest.raises(ValueError, match="input_snapshot_text_mismatch"):
        ligand_prep.resolve_sdf_text(
            _molblock("CCO"), source_kind="sdf_text", source_label="inline_text", input_bytes=b"other contents",
        )


def test_invalid_utf8_is_rejected_instead_of_discarded(tmp_path):
    path = tmp_path / "broken.sdf"
    path.write_bytes(_molblock("CCO").encode("utf-8") + b"\xff")
    with pytest.raises(ValueError, match="invalid_utf8"):
        ligand_prep.resolve_ligand_input(str(path))


@pytest.mark.parametrize("suffix", ["sdf", "smi"])
def test_path_parsing_and_hash_use_one_binary_snapshot(tmp_path, monkeypatch, suffix):
    snapshot = (_molblock("CCO") if suffix == "sdf" else " OCC \n").encode("utf-8")
    path = tmp_path / f"input.{suffix}"
    path.write_bytes(b"changed contents must never be read")
    opened = []
    real_open = builtins.open

    def snapshot_open(filename, mode="r", *args, **kwargs):
        if str(filename) == str(path):
            opened.append(mode)
            assert len(opened) == 1
            return io.BytesIO(snapshot)
        return real_open(filename, mode, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", snapshot_open)
    resolved = ligand_prep.resolve_ligand_input(str(path))
    assert opened == ["rb"]
    assert resolved.smiles == "CCO"
    assert resolved.provenance["input_content_sha256"] == hashlib.sha256(snapshot).hexdigest()
    assert resolved.provenance["input_byte_count"] == len(snapshot)


def test_smiles_file_contents_are_not_interpreted_as_another_path(tmp_path):
    other = tmp_path / "other.smi"
    other.write_text("CCO", encoding="utf-8")
    path = tmp_path / "input.smi"
    snapshot = str(other).encode("utf-8")
    path.write_bytes(snapshot)
    resolved = ligand_prep.resolve_ligand_input(str(path))
    assert resolved.smiles == str(other)
    assert resolved.provenance["input_content_sha256"] == hashlib.sha256(snapshot).hexdigest()
    assert ligand_prep.validate_ligand(resolved.smiles)["blocked"] is True


def test_payload_retains_mapping_and_cannot_mutate_resolved_source_provenance():
    resolved = ligand_prep.resolve_ligand_input(_molblock("CCO", reverse=True))
    validation = ligand_prep.validate_ligand(resolved.smiles, resolved)
    payload = ligand_prep.ligand_topology_payload(validation)
    assert payload["atom_count"] == 3
    assert payload["coordinate_to_source_atom_indices"] == [2, 1, 0]
    assert payload["coordinates_source"] == "generated_conformer_not_input_sdf_coordinates"
    payload["input_provenance"]["source_topology"]["atom_elements"][0] = "X"
    assert resolved.provenance["source_topology"]["atom_elements"][0] == "O"


def test_atom_order_fingerprint_includes_chirality():
    left = ligand_prep.validate_ligand("C[C@H](O)F")
    right = ligand_prep.validate_ligand("C[C@@H](O)F")
    assert left["atom_order_sha256"] != right["atom_order_sha256"]
