from __future__ import annotations

import os
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
        "bond_count": len(bonds),
        "bonds": bonds,
        "chiral_center_count": len(chiral_centers),
        "unassigned_chiral_center_count": int(unassigned_chiral),
        "chirality_status": chirality_status,
        "protonation_source": f"{source_kind}_molblock_atoms_no_enumeration",
        "tautomer_source": f"{source_kind}_molblock_connectivity_no_enumeration",
    }


def ligand_topology_payload(ligand_valid: dict[str, Any]) -> dict[str, Any]:
    return {
        "valid": bool(ligand_valid.get("valid", False)),
        "claim_safe": bool(ligand_valid.get("claim_safe", False)),
        "blocked": bool(ligand_valid.get("blocked", False)),
        "blockers": list(ligand_valid.get("blockers", [])),
        "atom_elements": ligand_valid.get("atom_elements", []),
        "formal_charges": ligand_valid.get("formal_charges", []),
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
    if Chem is not None and valid:
        mol = Chem.MolFromSmiles(str(smiles).strip())
        if mol is not None:
            bond_count = int(mol.GetNumBonds())
            exact_bonds = [
                {
                    "begin_atom_idx": int(bond.GetBeginAtomIdx()),
                    "end_atom_idx": int(bond.GetEndAtomIdx()),
                    "bond_type": str(bond.GetBondType()),
                    "is_aromatic": bool(bond.GetIsAromatic()),
                }
                for bond in mol.GetBonds()
            ]
    provenance = dict(resolved_input.provenance) if resolved_input is not None else {}
    if provenance:
        bond_count = int(provenance.get("bond_count", bond_count))
        exact_bonds = list(provenance.get("bonds", exact_bonds))
        unassigned_chiral = int(provenance.get("unassigned_chiral_center_count", unassigned_chiral))
        if valid and unassigned_chiral > 0 and "unassigned_ligand_chirality" not in blockers:
            blockers.append("unassigned_ligand_chirality")
    blocked = bool(not valid or blockers)
    return {
        "valid": valid,
        "claim_safe": claim_safe and not blocked,
        "blocked": blocked,
        "reason": str(ligand.validity.get("reason", "")),
        "blockers": blockers,
        "atom_count": int(provenance.get("atom_count", ligand.validity.get("atom_count", 0))),
        "atom_elements": list(provenance.get("atom_elements", list(ligand.atom_elements))),
        "formal_charges": list(provenance.get("formal_charges", list(ligand.formal_charges))),
        "bond_count": bond_count,
        "bonds": exact_bonds,
        "feature_source": str(ligand.validity.get("feature_source") or "not_assessed"),
        "feature_sites": list(ligand.validity.get("feature_sites", [])),
        "donor_site_count": int(ligand.validity.get("donor_site_count", 0) or 0),
        "acceptor_site_count": int(ligand.validity.get("acceptor_site_count", 0) or 0),
        "hbond_site_count": int(ligand.validity.get("hbond_site_count", 0) or 0),
        "chiral_center_count": int(provenance.get("chiral_center_count", ligand.validity.get("chiral_center_count", 0))),
        "unassigned_chiral_center_count": unassigned_chiral,
        "potential_stereo_count": int(ligand.validity.get("potential_stereo_count", 0) or 0),
        "specified_stereo_count": int(ligand.validity.get("specified_stereo_count", 0) or 0),
        "unassigned_stereo_count": int(ligand.validity.get("unassigned_stereo_count", 0) or 0),
        "unassigned_stereo_bond_count": int(ligand.validity.get("unassigned_stereo_bond_count", 0) or 0),
        "chirality_status": str(
            provenance.get("chirality_status", ligand.validity.get("chirality_status") or "not_assessed")
        ),
        "protonation_status": str(ligand.validity.get("protonation_status") or "not_assessed"),
        "tautomer_status": str(ligand.validity.get("tautomer_status") or "not_assessed"),
        "protonation_source": str(
            provenance.get("protonation_source", ligand.validity.get("protonation_source") or "not_assessed")
        ),
        "protonation_policy": str(
            provenance.get("protonation_policy", ligand.validity.get("protonation_policy") or "not_assessed")
        ),
        "protonation_ph_values": list(
            provenance.get("protonation_ph_values", ligand.validity.get("protonation_ph_values") or [])
        ),
        "protonation_claim_boundary": str(
            provenance.get(
                "protonation_claim_boundary",
                ligand.validity.get("protonation_claim_boundary") or "",
            )
        ),
        "tautomer_source": str(
            provenance.get("tautomer_source", ligand.validity.get("tautomer_source") or "not_assessed")
        ),
        "input_source_kind": str(resolved_input.source_kind if resolved_input is not None else "smiles_text"),
        "input_source_label": str(provenance.get("input_source_label", "inline_text")),
        "input_provenance": provenance,
    }


def looks_like_sdf_text(text: str) -> bool:
    body = str(text or "")
    return "M  END" in body or " V2000" in body or " V3000" in body or "$$$$" in body


def resolve_sdf_text(text: str, *, source_kind: str, source_label: str) -> ResolvedLigandInput | None:
    if not looks_like_sdf_text(text):
        return None
    if Chem is None:
        raise ValueError("invalid_sdf_ligand:rdkit_unavailable")
    molblock = str(text).split("$$$$", 1)[0].rstrip("\n")
    mol = Chem.MolFromMolBlock(molblock, sanitize=True, removeHs=False)
    if mol is None or mol.GetNumAtoms() <= 0:
        raise ValueError("invalid_sdf_ligand:molblock_parse_failed")
    smiles = Chem.MolToSmiles(mol, isomericSmiles=True)
    if not smiles:
        raise ValueError("invalid_sdf_ligand:empty_canonical_smiles")
    provenance = mol_topology_provenance(mol, source_kind=source_kind, source_label=source_label)
    provenance["canonical_smiles"] = smiles
    return ResolvedLigandInput(smiles=smiles, source_kind=source_kind, provenance=provenance)


def resolve_ligand_input(ligand_input: str) -> ResolvedLigandInput:
    if not ligand_input.strip():
        raise ValueError("empty ligand input")
    stripped = ligand_input.strip()
    if os.path.isfile(stripped):
        with open(stripped, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
        source_label = stripped
        suffix = os.path.splitext(stripped)[1].lower()
        source_kind = "sdf_path" if suffix in {".sdf", ".mol"} or looks_like_sdf_text(text) else "smiles_path"
    else:
        text = stripped
        source_label = "inline_text"
        source_kind = "sdf_text" if looks_like_sdf_text(text) else "smiles_text"
    if not text.strip():
        raise ValueError("empty ligand content")
    if source_kind.startswith("sdf"):
        resolved_sdf = resolve_sdf_text(text, source_kind=source_kind, source_label=source_label)
        if resolved_sdf is None:
            raise ValueError("invalid_sdf_ligand:missing_molblock")
        return resolved_sdf
    return ResolvedLigandInput(
        smiles=text.strip(),
        source_kind=source_kind,
        provenance={
            "input_source_kind": source_kind,
            "input_source_label": source_label,
            "format": "smiles",
        },
    )
