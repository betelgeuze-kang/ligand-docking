from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import re
from dataclasses import dataclass, field
from typing import Any

from betelgeuze_engine.topology.ligand import ligand_topology_from_smiles

try:
    from rdkit import Chem
except Exception:
    Chem = None


@dataclass(frozen=True)
class ResolvedLigandInput:
    smiles: str
    source_kind: str
    provenance: dict[str, Any] = field(default_factory=dict)


def mol_topology_provenance(mol: Any, *, source_kind: str, source_label: str) -> dict[str, Any]:
    chiral_centers = []
    unassigned_chiral = 0
    if Chem is not None and mol is not None:
        chiral_centers = Chem.FindMolChiralCenters(mol, includeUnassigned=True)
        unassigned_chiral = sum(1 for _, label in chiral_centers if str(label) == "?")
    bonds = [
        {
            "begin_atom_idx": int(bond.GetBeginAtomIdx()),
            "end_atom_idx": int(bond.GetEndAtomIdx()),
            "bond_type": str(bond.GetBondType()),
            "is_aromatic": bool(bond.GetIsAromatic()),
            "stereo": str(bond.GetStereo()),
            "stereo_atom_indices": [int(idx) for idx in bond.GetStereoAtoms()],
        }
        for bond in mol.GetBonds()
    ]
    atom_elements = [str(atom.GetSymbol()) for atom in mol.GetAtoms()]
    formal_charges = [int(atom.GetFormalCharge()) for atom in mol.GetAtoms()]
    if unassigned_chiral > 0:
        chirality_status = "unassigned"
    elif chiral_centers:
        chirality_status = "assigned"
    else:
        chirality_status = "no_chiral_centers"
    return {
        "input_source_kind": source_kind,
        "input_source_label": source_label,
        "format": "sdf_molblock",
        "atom_count": int(mol.GetNumAtoms()),
        "atom_elements": atom_elements,
        "formal_charges": formal_charges,
        "atom_isotopes": [int(atom.GetIsotope()) for atom in mol.GetAtoms()],
        "atom_aromatic_flags": [bool(atom.GetIsAromatic()) for atom in mol.GetAtoms()],
        "atom_stereo_labels": [atom.GetProp("_CIPCode") if atom.HasProp("_CIPCode") else "" for atom in mol.GetAtoms()],
        "bond_count": len(bonds),
        "bonds": bonds,
        "chiral_center_count": len(chiral_centers),
        "unassigned_chiral_center_count": int(unassigned_chiral),
        "chirality_status": chirality_status,
        "protonation_source": f"{source_kind}_molblock_atoms_no_enumeration",
        "tautomer_source": f"{source_kind}_molblock_connectivity_no_enumeration",
    }


def _atom_identity(atom: Any) -> tuple[Any, ...]:
    # Chiral tag CW/CCW depends on neighbor order; CIP labels do not.
    return (
        atom.GetAtomicNum(), atom.GetIsotope(), atom.GetFormalCharge(),
        atom.GetIsAromatic(), atom.GetTotalNumHs(), atom.GetNumRadicalElectrons(),
        atom.GetProp("_CIPCode") if atom.HasProp("_CIPCode") else "",
    )


def _chemical_atom_mapping(source_mol: Any, coordinate_mol: Any) -> list[int] | None:
    """Map coordinate indices to source indices only for the same chemical state."""
    if source_mol.GetNumAtoms() != coordinate_mol.GetNumAtoms():
        return None
    if source_mol.GetNumBonds() != coordinate_mol.GetNumBonds():
        return None
    if Chem.MolToSmiles(source_mol, isomericSmiles=True) != Chem.MolToSmiles(
        coordinate_mol, isomericSmiles=True,
    ):
        return None
    mapping = list(source_mol.GetSubstructMatch(coordinate_mol, useChirality=True))
    if len(mapping) != coordinate_mol.GetNumAtoms() or len(set(mapping)) != len(mapping):
        return None
    for coordinate_idx, source_idx in enumerate(mapping):
        if _atom_identity(coordinate_mol.GetAtomWithIdx(coordinate_idx)) != _atom_identity(
            source_mol.GetAtomWithIdx(source_idx),
        ):
            return None
    for bond in coordinate_mol.GetBonds():
        source_bond = source_mol.GetBondBetweenAtoms(
            mapping[bond.GetBeginAtomIdx()], mapping[bond.GetEndAtomIdx()],
        )
        if source_bond is None or (
            source_bond.GetBondType(), source_bond.GetIsAromatic(), source_bond.GetStereo()
        ) != (bond.GetBondType(), bond.GetIsAromatic(), bond.GetStereo()):
            return None
    return mapping


def _remove_supported_hydrogens(mol: Any) -> tuple[Any, list[int]]:
    """Remove ordinary single-bonded H while retaining original atom indices."""
    indexed = Chem.Mol(mol)
    removed = []
    for atom in indexed.GetAtoms():
        atom.SetIntProp("_biodiscovery_source_atom_idx", int(atom.GetIdx()))
        if atom.GetAtomicNum() != 1:
            continue
        if atom.GetIsotope() != 0:
            raise ValueError("invalid_ligand:unsupported_isotopic_hydrogen")
        if (
            atom.GetFormalCharge() != 0 or atom.GetNumRadicalElectrons() != 0
            or atom.GetDegree() != 1 or atom.GetNeighbors()[0].GetAtomicNum() == 1
            or atom.GetBonds()[0].GetBondType() != Chem.BondType.SINGLE
        ):
            raise ValueError("invalid_ligand:unsupported_hydrogen_state")
        removed.append(int(atom.GetIdx()))
    reduced = Chem.RemoveHs(indexed)
    if any(atom.GetAtomicNum() == 1 for atom in reduced.GetAtoms()):
        raise ValueError("invalid_ligand:unsupported_hydrogen_state")
    return reduced, removed


def ligand_state_provenance(smiles: str, resolved_input: ResolvedLigandInput | None) -> dict[str, Any]:
    """Attach source evidence to a state without claiming a mapping across chemistry changes.

    Call this through ``validate_ligand`` for every enumerated state's actual
    SMILES, including rank zero. A tautomer/protomer may have no exact source
    correspondence even when its atom count matches the input.
    """
    result: dict[str, Any] = {
        "coordinate_smiles": str(smiles).strip(),
        "coordinate_atom_order": "parsed_state_smiles",
        "coordinates_source": "generated_conformer_not_input_sdf_coordinates",
        "atom_mapping_status": "not_available_no_sdf_source",
        "coordinate_to_source_atom_indices": None,
        "source_to_coordinate_atom_indices": None,
    }
    if resolved_input is None or not resolved_input.source_kind.startswith("sdf"):
        return result
    provenance = resolved_input.provenance
    if Chem is None:
        result["atom_mapping_status"] = "not_available_rdkit_unavailable"
        return result
    original = Chem.MolFromSmiles(resolved_input.smiles)
    state = Chem.MolFromSmiles(str(smiles).strip())
    state_to_original = _chemical_atom_mapping(original, state) if original is not None and state is not None else None
    if state_to_original is None:
        result["atom_mapping_status"] = "not_available_chemical_state_changed"
        return result
    original_to_source = provenance.get("canonical_to_source_atom_indices")
    source_count = int(provenance.get("source_topology", {}).get("atom_count", 0))
    if not isinstance(original_to_source, list) or len(original_to_source) != len(state_to_original):
        result["atom_mapping_status"] = "not_available_source_mapping_missing"
        return result
    coordinate_to_source = [original_to_source[idx] for idx in state_to_original]
    if any(type(idx) is not int or idx < 0 or idx >= source_count for idx in coordinate_to_source) or len(
        set(coordinate_to_source)
    ) != len(coordinate_to_source):
        raise ValueError("invalid_ligand:invalid_source_atom_mapping")
    source_to_coordinate: list[int | None] = [None] * source_count
    for coordinate_idx, source_idx in enumerate(coordinate_to_source):
        source_to_coordinate[source_idx] = coordinate_idx
    result.update({
        "atom_mapping_status": "exact_chemical_identity",
        "coordinate_to_source_atom_indices": coordinate_to_source,
        "source_to_coordinate_atom_indices": source_to_coordinate,
    })
    return result


def ligand_topology_payload(ligand_valid: dict[str, Any]) -> dict[str, Any]:
    return {
        "valid": bool(ligand_valid.get("valid", False)),
        "claim_safe": bool(ligand_valid.get("claim_safe", False)),
        "blocked": bool(ligand_valid.get("blocked", False)),
        "blockers": list(ligand_valid.get("blockers", [])),
        "atom_elements": ligand_valid.get("atom_elements", []),
        "formal_charges": ligand_valid.get("formal_charges", []),
        "atom_count": ligand_valid.get("atom_count", 0),
        "atom_isotopes": ligand_valid.get("atom_isotopes", []),
        "atom_aromatic_flags": ligand_valid.get("atom_aromatic_flags", []),
        "atom_stereo_labels": ligand_valid.get("atom_stereo_labels", []),
        "atom_order_sha256": ligand_valid.get("atom_order_sha256"),
        "coordinate_smiles": ligand_valid.get("coordinate_smiles"),
        "coordinate_atom_order": ligand_valid.get("coordinate_atom_order"),
        "coordinates_source": ligand_valid.get("coordinates_source"),
        "atom_mapping_status": ligand_valid.get("atom_mapping_status"),
        "coordinate_to_source_atom_indices": ligand_valid.get("coordinate_to_source_atom_indices"),
        "source_to_coordinate_atom_indices": ligand_valid.get("source_to_coordinate_atom_indices"),
        "bond_count": ligand_valid.get("bond_count", 0),
        "bonds": ligand_valid.get("bonds", []),
        "feature_source": ligand_valid.get("feature_source", "not_assessed"),
        "feature_sites": ligand_valid.get("feature_sites", []),
        "donor_site_count": int(ligand_valid.get("donor_site_count", 0) or 0),
        "acceptor_site_count": int(ligand_valid.get("acceptor_site_count", 0) or 0),
        "hbond_site_count": int(ligand_valid.get("hbond_site_count", 0) or 0),
        "chirality_status": ligand_valid.get("chirality_status", "not_assessed"),
        "potential_stereo_count": int(ligand_valid.get("potential_stereo_count", 0) or 0),
        "specified_stereo_count": int(ligand_valid.get("specified_stereo_count", 0) or 0),
        "unassigned_stereo_count": int(ligand_valid.get("unassigned_stereo_count", 0) or 0),
        "unassigned_stereo_bond_count": int(ligand_valid.get("unassigned_stereo_bond_count", 0) or 0),
        "protonation_status": ligand_valid.get("protonation_status", "not_assessed"),
        "protonation_source": ligand_valid.get("protonation_source", "not_assessed"),
        "protonation_policy": ligand_valid.get("protonation_policy", "not_assessed"),
        "protonation_ph_values": ligand_valid.get("protonation_ph_values", []),
        "protonation_claim_boundary": ligand_valid.get("protonation_claim_boundary", ""),
        "tautomer_status": ligand_valid.get("tautomer_status", "not_assessed"),
        "tautomer_source": ligand_valid.get("tautomer_source", "not_assessed"),
        "input_source_kind": ligand_valid.get("input_source_kind", "smiles_text"),
        "input_source_label": ligand_valid.get("input_source_label", "inline_text"),
        "input_provenance": ligand_valid.get("input_provenance", {}),
    }


def validate_ligand(smiles: str, resolved_input: ResolvedLigandInput | None = None) -> dict[str, Any]:
    if not str(smiles).strip():
        return {"valid": False, "reason": "empty_smiles", "blocked": True, "blockers": ["empty_smiles"]}
    ligand = ligand_topology_from_smiles(str(smiles).strip())
    valid = bool(ligand.validity.get("valid", False) is True)
    claim_safe = bool(ligand.validity.get("claim_safe", False) is True)
    blockers = list(ligand.validity.get("claim_safe_blockers", [])) if not claim_safe else []
    unassigned_chiral = int(ligand.validity.get("unassigned_chiral_center_count", 0))
    if valid and unassigned_chiral > 0:
        blockers.append("unassigned_ligand_chirality")
    bond_count = 0
    exact_bonds: list[dict[str, Any]] = []
    atom_isotopes: list[int] = []
    atom_aromatic_flags: list[bool] = []
    atom_stereo_labels: list[str] = []
    if Chem is not None and valid:
        mol = Chem.MolFromSmiles(str(smiles).strip())
        if mol is not None:
            atom_isotopes = [int(atom.GetIsotope()) for atom in mol.GetAtoms()]
            atom_aromatic_flags = [bool(atom.GetIsAromatic()) for atom in mol.GetAtoms()]
            atom_stereo_labels = [atom.GetProp("_CIPCode") if atom.HasProp("_CIPCode") else "" for atom in mol.GetAtoms()]
            bond_count = int(mol.GetNumBonds())
            exact_bonds = [
                {
                    "begin_atom_idx": int(bond.GetBeginAtomIdx()),
                    "end_atom_idx": int(bond.GetEndAtomIdx()),
                    "bond_type": str(bond.GetBondType()),
                    "is_aromatic": bool(bond.GetIsAromatic()),
                    "stereo": str(bond.GetStereo()),
                    "stereo_atom_indices": [int(idx) for idx in bond.GetStereoAtoms()],
                }
                for bond in mol.GetBonds()
            ]
    provenance = copy.deepcopy(resolved_input.provenance) if resolved_input is not None else {}
    state_provenance = ligand_state_provenance(smiles, resolved_input)
    atom_order = {
        "atom_elements": list(ligand.atom_elements),
        "formal_charges": list(ligand.formal_charges),
        "atom_isotopes": atom_isotopes,
        "atom_aromatic_flags": atom_aromatic_flags,
        "atom_stereo_labels": atom_stereo_labels,
        "bonds": exact_bonds,
    }
    blocked = bool(not valid or blockers)
    return {
        **state_provenance,
        "valid": valid,
        "claim_safe": claim_safe and not blocked,
        "blocked": blocked,
        "reason": str(ligand.validity.get("reason", "")),
        "blockers": blockers,
        "atom_count": int(ligand.validity.get("atom_count", 0)),
        **atom_order,
        "atom_order_sha256": hashlib.sha256(
            json.dumps(atom_order, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
        ).hexdigest(),
        "bond_count": bond_count,
        "bonds": exact_bonds,
        "feature_source": str(ligand.validity.get("feature_source") or "not_assessed"),
        "feature_sites": list(ligand.validity.get("feature_sites", [])),
        "donor_site_count": int(ligand.validity.get("donor_site_count", 0) or 0),
        "acceptor_site_count": int(ligand.validity.get("acceptor_site_count", 0) or 0),
        "hbond_site_count": int(ligand.validity.get("hbond_site_count", 0) or 0),
        "chiral_center_count": int(ligand.validity.get("chiral_center_count", 0)),
        "unassigned_chiral_center_count": unassigned_chiral,
        "potential_stereo_count": int(ligand.validity.get("potential_stereo_count", 0) or 0),
        "specified_stereo_count": int(ligand.validity.get("specified_stereo_count", 0) or 0),
        "unassigned_stereo_count": int(ligand.validity.get("unassigned_stereo_count", 0) or 0),
        "unassigned_stereo_bond_count": int(ligand.validity.get("unassigned_stereo_bond_count", 0) or 0),
        "chirality_status": str(ligand.validity.get("chirality_status") or "not_assessed"),
        "protonation_status": str(ligand.validity.get("protonation_status") or "not_assessed"),
        "tautomer_status": str(ligand.validity.get("tautomer_status") or "not_assessed"),
        "protonation_source": str(ligand.validity.get("protonation_source") or "not_assessed"),
        "protonation_policy": str(ligand.validity.get("protonation_policy") or "not_assessed"),
        "protonation_ph_values": list(ligand.validity.get("protonation_ph_values") or []),
        "protonation_claim_boundary": str(ligand.validity.get("protonation_claim_boundary") or ""),
        "tautomer_source": str(ligand.validity.get("tautomer_source") or "not_assessed"),
        "input_source_kind": str(resolved_input.source_kind if resolved_input is not None else "smiles_text"),
        "input_source_label": str(provenance.get("input_source_label", "inline_text")),
        "input_provenance": provenance,
    }


def looks_like_sdf_text(text: str) -> bool:
    body = str(text or "")
    return "M  END" in body or " V2000" in body or " V3000" in body or "$$$$" in body


def resolve_sdf_text(
    text: str, *, source_kind: str, source_label: str, input_bytes: bytes | None = None,
) -> ResolvedLigandInput | None:
    if not looks_like_sdf_text(text):
        return None
    if Chem is None:
        raise ValueError("invalid_sdf_ligand:rdkit_unavailable")
    records = re.split(r"(?m)^\$\$\$\$[ \t]*\r?$", str(text))
    if len(records) > 2 or sum(bool(record.strip()) for record in records) != 1 or sum(
        line.strip() == "M  END" for line in str(text).splitlines()
    ) != 1:
        raise ValueError("invalid_sdf_ligand:multiple_or_invalid_records")
    # A blank title is the first required molblock line, so never lstrip it.
    molblock = records[0]
    mol = Chem.MolFromMolBlock(molblock, sanitize=True, removeHs=False, strictParsing=True)
    if mol is None or mol.GetNumAtoms() <= 0:
        raise ValueError("invalid_sdf_ligand:molblock_parse_failed")
    reduced, removed_hydrogens = _remove_supported_hydrogens(mol)
    smiles = Chem.MolToSmiles(reduced, isomericSmiles=True)
    if not smiles:
        raise ValueError("invalid_sdf_ligand:empty_canonical_smiles")
    canonical = Chem.MolFromSmiles(smiles)
    mapping = _chemical_atom_mapping(reduced, canonical) if canonical is not None else None
    if mapping is None:
        raise ValueError("invalid_sdf_ligand:canonical_chemical_identity_mismatch")
    canonical_to_source = [
        int(reduced.GetAtomWithIdx(idx).GetIntProp("_biodiscovery_source_atom_idx")) for idx in mapping
    ]
    source_to_canonical: list[int | None] = [None] * mol.GetNumAtoms()
    for canonical_idx, source_idx in enumerate(canonical_to_source):
        source_to_canonical[source_idx] = canonical_idx
    source_topology = mol_topology_provenance(mol, source_kind=source_kind, source_label=source_label)
    if mol.GetNumConformers():
        coordinates = [[float(value) for value in row] for row in mol.GetConformer().GetPositions()]
        if not all(math.isfinite(value) for row in coordinates for value in row):
            raise ValueError("invalid_sdf_ligand:nonfinite_source_coordinates")
        source_topology["coordinates"] = coordinates
        source_topology["coordinates_used_for_docking"] = False
    snapshot = input_bytes if input_bytes is not None else str(text).encode("utf-8")
    if snapshot.decode("utf-8", errors="strict") != str(text):
        raise ValueError("invalid_sdf_ligand:input_snapshot_text_mismatch")
    provenance = {
        "input_source_kind": source_kind,
        "input_source_label": source_label,
        "input_content_sha256": hashlib.sha256(snapshot).hexdigest(),
        "input_byte_count": len(snapshot),
        "format": "sdf_molblock",
        "source_topology": source_topology,
        "canonical_smiles": smiles,
        "canonical_to_source_atom_indices": canonical_to_source,
        "source_to_canonical_atom_indices": source_to_canonical,
        "hydrogen_policy": "remove_ordinary_single_bonded_hydrogens",
        "removed_source_hydrogen_indices": removed_hydrogens,
        "source_mapping_chemical_identity_checked": True,
    }
    return ResolvedLigandInput(smiles=smiles, source_kind=source_kind, provenance=provenance)


def resolve_ligand_input(ligand_input: str, *, input_snapshot: dict | None = None) -> ResolvedLigandInput:
    if not ligand_input.strip():
        raise ValueError("empty ligand input")
    stripped = ligand_input.strip()
    if os.path.isfile(stripped):
        try:
            with open(stripped, "rb") as f:
                snapshot = f.read()
            if input_snapshot is not None:
                input_snapshot.update(sha256=hashlib.sha256(snapshot).hexdigest(),
                                      byte_count=len(snapshot), source_kind="path")
            text = snapshot.decode("utf-8", errors="strict")
        except (OSError, UnicodeError) as exc:
            raise ValueError("invalid_ligand_input:unreadable_or_invalid_utf8") from exc
        source_label = stripped
        suffix = os.path.splitext(stripped)[1].lower()
        source_kind = "sdf_path" if suffix in {".sdf", ".mol"} or looks_like_sdf_text(text) else "smiles_path"
    else:
        text = ligand_input
        try:
            snapshot = text.encode("utf-8", errors="strict")
        except UnicodeError as exc:
            raise ValueError("invalid_ligand_input:invalid_utf8") from exc
        source_label = "inline_text"
        source_kind = "sdf_text" if looks_like_sdf_text(text) else "smiles_text"
    if input_snapshot is not None:
        input_snapshot.update(sha256=hashlib.sha256(snapshot).hexdigest(),
                              byte_count=len(snapshot), source_kind=source_kind)
    if not text.strip():
        raise ValueError("empty ligand content")
    if source_kind.startswith("sdf"):
        resolved_sdf = resolve_sdf_text(
            text, source_kind=source_kind, source_label=source_label, input_bytes=snapshot,
        )
        if resolved_sdf is None:
            raise ValueError("invalid_sdf_ligand:missing_molblock")
        return resolved_sdf
    smiles = text.strip()
    if Chem is not None:
        mol = Chem.MolFromSmiles(smiles)
        if mol is not None:
            reduced, _ = _remove_supported_hydrogens(mol)
            smiles = Chem.MolToSmiles(reduced, isomericSmiles=True)
    return ResolvedLigandInput(
        smiles=smiles,
        source_kind=source_kind,
        provenance={
            "input_source_kind": source_kind,
            "input_source_label": source_label,
            "format": "smiles",
            "input_content_sha256": hashlib.sha256(snapshot).hexdigest(),
            "input_byte_count": len(snapshot),
            "source_smiles": text.strip(),
            "canonical_smiles": smiles,
        },
    )
