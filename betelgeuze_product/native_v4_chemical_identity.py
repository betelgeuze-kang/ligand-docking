"""Installed native v4 chemical identity routines, frozen from public assay intake.

Only helpers used by the receptor source derivation are shipped here. This is
not an independent chemical-state or assay-state validation.
"""
from __future__ import annotations
import hashlib
import json
import re
from pathlib import Path
from rdkit import Chem, rdBase
from rdkit.Chem.Scaffolds import MurckoScaffold
SHA = re.compile(r"[0-9a-f]{64}\Z")

def digest(value: bytes | str) -> str:
    return hashlib.sha256(
        value.encode() if isinstance(value, str) else value
    ).hexdigest()


def json_text(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def file_sha(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def require_sha(value: str, expected: str) -> None:
    if not SHA.fullmatch(expected) or value != expected:
        raise ValueError("source_sha256_mismatch")


def chemical_identity(smiles: str) -> dict:
    mol = Chem.MolFromSmiles(smiles)
    if mol is None or mol.GetNumAtoms() == 0:
        raise ValueError("invalid_smiles")
    canonical = Chem.MolToSmiles(mol, canonical=True, isomericSmiles=True)
    unresolved_groups = [
        group for group in mol.GetStereoGroups()
        if group.GetGroupType() != Chem.StereoGroupType.STEREO_ABSOLUTE
    ]
    enhanced = {}
    if unresolved_groups:
        params = Chem.SmilesWriteParams()
        params.canonical = True
        params.doIsomericSmiles = True
        canonical = Chem.MolToCXSmiles(mol, params, Chem.CXSmilesFields.CX_ENHANCEDSTEREO)
        enhanced = {
            "unresolved_stereochemistry": True,
            "enhanced_stereo_groups": [
                {"type": str(group.GetGroupType()),
                 "atom_indices": [atom.GetIdx() for atom in group.GetAtoms()]}
                for group in unresolved_groups
            ],
            "enhanced_stereo_atom_index_basis": "parsed_input_smiles_zero_based",
            "canonicalization": "rdkit_canonical_CXSMILES_enhanced_stereo_no_salt_or_state_change",
        }
    no_stereo = Chem.Mol(mol)
    Chem.RemoveStereochemistry(no_stereo)
    connectivity = Chem.MolToSmiles(no_stereo, canonical=True, isomericSmiles=True)
    scaffold = MurckoScaffold.MurckoScaffoldSmiles(mol=mol, includeChirality=False)
    return {
        "canonical_isomeric_smiles": canonical,
        "canonical_isomeric_smiles_sha256": digest(canonical),
        "connectivity_smiles_sha256": digest(connectivity),
        "scaffold_smiles": scaffold,
        "scaffold_group": digest(scaffold or ("acyclic:" + connectivity)),
        "rdkit_inchikey": Chem.MolToInchiKey(mol),
        "heavy_atom_count": mol.GetNumHeavyAtoms(),
        "formal_charge": Chem.GetFormalCharge(mol),
        "fragment_count": len(Chem.GetMolFrags(mol)),
        "elements": sorted({atom.GetSymbol() for atom in mol.GetAtoms()}),
        "radical_electrons": sum(
            atom.GetNumRadicalElectrons() for atom in mol.GetAtoms()
        ),
        "isotope_atoms": sum(atom.GetIsotope() != 0 for atom in mol.GetAtoms()),
        "stereo_unspecified_count": sum(
            str(info.specified) == "Unspecified"
            for info in Chem.FindPotentialStereo(mol)
        ),
        "canonicalization": "rdkit_MolFromSmiles_MolToSmiles_isomeric_true_no_salt_or_state_change",
        "rdkit_version": rdBase.rdkitVersion,
        **enhanced,
    }
