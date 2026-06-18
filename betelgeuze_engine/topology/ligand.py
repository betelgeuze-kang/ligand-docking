from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any

try:
    from rdkit import Chem  # type: ignore
except Exception:  # pragma: no cover
    Chem = None


_ELEMENT_RE = re.compile(r"Cl|Br|[BCNOFPSIHK]")
_HBOND_ELEMENTS = {"N", "O", "S", "P"}


def _base_validity(
    *,
    valid: bool,
    reason: str,
    source: str,
    atom_count: int = 0,
    hbond_site_count: int = 0,
    ring_atom_count: int = 0,
    formal_charge_sum: int = 0,
    chiral_center_count: int = 0,
    specified_chiral_center_count: int = 0,
    unassigned_chiral_center_count: int = 0,
    blockers: list[str] | None = None,
) -> dict[str, Any]:
    blocker_values = [str(v) for v in blockers or [] if str(v)]
    chirality_valid = int(unassigned_chiral_center_count) == 0
    if unassigned_chiral_center_count > 0:
        chirality_status = "unassigned_chiral_centers"
    elif specified_chiral_center_count > 0:
        chirality_status = "specified"
    else:
        chirality_status = "not_applicable"
    ring_status = "present" if ring_atom_count > 0 else "not_applicable"
    protonation_status = "charged_state_parsed" if formal_charge_sum != 0 else "neutral_state_parsed"
    tautomer_status = "connectivity_parsed_tautomer_not_canonicalized" if valid else "not_assessed"
    claim_safe = bool(valid and chirality_valid and source == "rdkit")
    if valid and source != "rdkit":
        blocker_values.append("rdkit_unavailable_ligand_topology")
    if valid and not chirality_valid:
        blocker_values.append("unassigned_ligand_chirality")
    blocked_reason = ";".join(dict.fromkeys(blocker_values))
    return {
        "schema_version": "ligand_topology_validity_v1",
        "valid": bool(valid),
        "claim_safe": bool(claim_safe and not blocked_reason),
        "reason": str(reason),
        "source": str(source),
        "blocked_reason": blocked_reason,
        "claim_safe_blockers": list(dict.fromkeys(blocker_values)),
        "atom_count": int(atom_count),
        "hbond_site_count": int(hbond_site_count),
        "ring_atom_count": int(ring_atom_count),
        "formal_charge_sum": int(formal_charge_sum),
        "chiral_center_count": int(chiral_center_count),
        "specified_chiral_center_count": int(specified_chiral_center_count),
        "unassigned_chiral_center_count": int(unassigned_chiral_center_count),
        "chirality_valid": bool(chirality_valid),
        "chirality_status": chirality_status,
        "ring_valid": bool(valid),
        "ring_status": ring_status,
        "protonation_valid": bool(valid),
        "protonation_status": protonation_status,
        "tautomer_valid": bool(valid),
        "tautomer_status": tautomer_status,
    }


@dataclass
class LigandTopology:
    smiles: str
    atom_elements: list[str]
    formal_charges: list[int]
    donor_acceptor_roles: list[str]
    ring_flags: list[bool]
    chirality_tags: list[str]
    validity: dict[str, Any] = field(default_factory=dict)


def _fallback_elements(smiles: str) -> list[str]:
    return [m.group(0) for m in _ELEMENT_RE.finditer(str(smiles or ""))]


def ligand_topology_from_smiles(smiles: str) -> LigandTopology:
    smi = str(smiles or "").strip()
    if not smi:
        return LigandTopology(
            "",
            [],
            [],
            [],
            [],
            [],
            _base_validity(valid=False, reason="empty_smiles", source="none", blockers=["empty_smiles"]),
        )
    if Chem is not None:
        mol = Chem.MolFromSmiles(smi)
        if mol is None:
            return LigandTopology(
                smi,
                [],
                [],
                [],
                [],
                [],
                _base_validity(valid=False, reason="invalid_smiles", source="rdkit", blockers=["invalid_smiles"]),
            )
        atom_elements: list[str] = []
        formal_charges: list[int] = []
        donor_acceptor_roles: list[str] = []
        ring_flags: list[bool] = []
        chirality_tags: list[str] = []
        for atom in mol.GetAtoms():
            symbol = str(atom.GetSymbol())
            atom_elements.append(symbol)
            formal_charges.append(int(atom.GetFormalCharge()))
            ring_flags.append(bool(atom.IsInRing()))
            chirality_tags.append(str(atom.GetChiralTag()))
            if symbol in _HBOND_ELEMENTS:
                has_h = int(atom.GetTotalNumHs()) > 0
                if has_h and symbol in {"N", "O", "S"}:
                    donor_acceptor_roles.append("donor")
                else:
                    donor_acceptor_roles.append("acceptor")
            else:
                donor_acceptor_roles.append("none")
        chiral_centers = Chem.FindMolChiralCenters(mol, includeUnassigned=True)
        unassigned_chiral_center_count = sum(1 for _idx, tag in chiral_centers if str(tag) == "?")
        specified_chiral_center_count = len(chiral_centers) - unassigned_chiral_center_count
        return LigandTopology(
            smiles=smi,
            atom_elements=atom_elements,
            formal_charges=formal_charges,
            donor_acceptor_roles=donor_acceptor_roles,
            ring_flags=ring_flags,
            chirality_tags=chirality_tags,
            validity=_base_validity(
                valid=True,
                reason="rdkit_parse_ok",
                source="rdkit",
                atom_count=len(atom_elements),
                hbond_site_count=sum(1 for role in donor_acceptor_roles if role in {"donor", "acceptor"}),
                ring_atom_count=sum(1 for flag in ring_flags if flag),
                formal_charge_sum=sum(formal_charges),
                chiral_center_count=len(chiral_centers),
                specified_chiral_center_count=specified_chiral_center_count,
                unassigned_chiral_center_count=unassigned_chiral_center_count,
            ),
        )

    atom_elements = _fallback_elements(smi)
    roles = ["acceptor" if element in _HBOND_ELEMENTS else "none" for element in atom_elements]
    return LigandTopology(
        smiles=smi,
        atom_elements=atom_elements,
        formal_charges=[0 for _ in atom_elements],
        donor_acceptor_roles=roles,
        ring_flags=[False for _ in atom_elements],
        chirality_tags=["unspecified" for _ in atom_elements],
        validity=_base_validity(
            valid=bool(atom_elements),
            reason="fallback_parse" if atom_elements else "fallback_empty_parse",
            source="fallback",
            atom_count=len(atom_elements),
            hbond_site_count=sum(1 for role in roles if role in {"donor", "acceptor"}),
            blockers=[] if atom_elements else ["fallback_empty_parse"],
        ),
    )
