from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any

from betelgeuze_engine.chemistry.ligand_states import ligand_chemistry_state_from_smiles
from betelgeuze_engine.chemistry.rotor_perception import (
    STATUS_SUPPORTED,
    STATUS_UNSUPPORTED_MACROCYCLE,
    RotorPerception,
    perceive_ligand_rotors,
)

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
    charged_atom_count: int = 0,
    chiral_center_count: int = 0,
    specified_chiral_center_count: int = 0,
    unassigned_chiral_center_count: int = 0,
    protonation_source: str = "not_assessed",
    protonation_policy: str = "not_assessed",
    protonation_ph_values: tuple[float, ...] | None = None,
    protonation_claim_boundary: str = "",
    tautomer_source: str = "not_assessed",
    canonical_tautomer_smiles: str = "",
    tautomer_count: int = 0,
    potential_stereo_count: int = 0,
    specified_stereo_count: int = 0,
    unassigned_stereo_count: int = 0,
    unassigned_stereo_bond_count: int = 0,
    feature_source: str = "not_assessed",
    donor_site_count: int = 0,
    acceptor_site_count: int = 0,
    feature_sites: list[dict[str, Any]] | None = None,
    salt_parent_smiles: str = "",
    fragment_count: int = 0,
    salt_stripped: bool = False,
    rotor_perception: RotorPerception | None = None,
    blockers: list[str] | None = None,
) -> dict[str, Any]:
    blocker_values = [str(v) for v in blockers or [] if str(v)]
    chirality_valid = int(unassigned_chiral_center_count) == 0 and int(unassigned_stereo_count) == 0
    if unassigned_stereo_count > 0:
        chirality_status = "unassigned_stereochemistry"
    elif specified_chiral_center_count > 0 or specified_stereo_count > 0:
        chirality_status = "specified"
    else:
        chirality_status = "not_applicable"
    ring_status = "present" if ring_atom_count > 0 else "not_applicable"
    protonation_status = "charged_state_parsed" if charged_atom_count > 0 else "neutral_state_parsed"
    tautomer_status = "canonical_tautomer_enumerated" if valid and canonical_tautomer_smiles else "not_assessed"
    claim_safe = bool(valid and chirality_valid and source == "rdkit")
    if valid and source != "rdkit":
        blocker_values.append("rdkit_unavailable_ligand_topology")
    rotor_payload = rotor_perception.to_dict() if rotor_perception is not None else {}
    rotor_status = str(rotor_payload.get("status") or "not_assessed")
    rotor_supported = rotor_status == STATUS_SUPPORTED
    macrocycle_present = bool(rotor_payload.get("macrocycle_present"))
    if valid and rotor_perception is not None and not rotor_supported:
        # A ligand whose flexibility cannot be perceived must not read as
        # claim-safe: macrocycles need a separate ring-closure lane.
        blocker_values.append(
            "macrocycle_ligand_unsupported_lane"
            if rotor_status == STATUS_UNSUPPORTED_MACROCYCLE
            else "ligand_rotor_perception_unsupported"
        )
    if valid and not chirality_valid:
        if int(unassigned_chiral_center_count) > 0:
            blocker_values.append("unassigned_ligand_chirality")
        if int(unassigned_stereo_count) > 0:
            blocker_values.append("unassigned_ligand_stereochemistry")
        if int(unassigned_stereo_bond_count) > 0:
            blocker_values.append("unassigned_ligand_double_bond_stereochemistry")
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
        "charged_atom_count": int(charged_atom_count),
        "chiral_center_count": int(chiral_center_count),
        "specified_chiral_center_count": int(specified_chiral_center_count),
        "unassigned_chiral_center_count": int(unassigned_chiral_center_count),
        "potential_stereo_count": int(potential_stereo_count),
        "specified_stereo_count": int(specified_stereo_count),
        "unassigned_stereo_count": int(unassigned_stereo_count),
        "unassigned_stereo_bond_count": int(unassigned_stereo_bond_count),
        "chirality_valid": bool(chirality_valid),
        "chirality_status": chirality_status,
        "ring_valid": bool(valid),
        "ring_status": ring_status,
        "protonation_valid": bool(valid),
        "protonation_status": protonation_status,
        "protonation_source": protonation_source,
        "protonation_policy": protonation_policy,
        "protonation_ph_values": [float(value) for value in protonation_ph_values or ()],
        "protonation_claim_boundary": protonation_claim_boundary,
        "tautomer_valid": bool(valid),
        "tautomer_status": tautomer_status,
        "tautomer_source": tautomer_source,
        "canonical_tautomer_smiles": canonical_tautomer_smiles,
        "tautomer_count": int(tautomer_count),
        "feature_source": feature_source,
        "feature_sites": [dict(site) for site in feature_sites or []],
        "donor_site_count": int(donor_site_count),
        "acceptor_site_count": int(acceptor_site_count),
        "salt_parent_smiles": salt_parent_smiles,
        "fragment_count": int(fragment_count),
        "salt_stripped": bool(salt_stripped),
        "rotor_perception_status": rotor_status,
        "rotor_perception_supported": bool(rotor_supported),
        "rotor_perception_schema_version": str(rotor_payload.get("schema_version") or ""),
        "rotor_count": int(rotor_payload.get("rotor_count") or 0),
        "free_rotor_count": int(rotor_payload.get("free_rotor_count") or 0),
        "restrained_rotor_count": int(rotor_payload.get("restrained_rotor_count") or 0),
        "conjugated_rotor_count": int(rotor_payload.get("conjugated_rotor_count") or 0),
        "exocyclic_ring_rotor_count": int(rotor_payload.get("exocyclic_ring_rotor_count") or 0),
        "ring_ring_rotor_count": int(rotor_payload.get("ring_ring_rotor_count") or 0),
        "stereo_locked_bond_count": int(rotor_payload.get("stereo_locked_bond_count") or 0),
        "rigid_component_count": int(rotor_payload.get("rigid_component_count") or 0),
        "macrocycle_present": macrocycle_present,
        "macrocycle_ring_sizes": list(rotor_payload.get("macrocycle_ring_sizes") or []),
        "ligand_flexibility_lane": (
            "macrocycle_unsupported"
            if rotor_status == STATUS_UNSUPPORTED_MACROCYCLE
            else ("rigid_component_plus_rotor" if rotor_supported else "unsupported")
        ),
        "rotor_perception": rotor_payload,
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
    rotor_perception: RotorPerception | None = None


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
        chemistry = ligand_chemistry_state_from_smiles(smi)
        rotors = perceive_ligand_rotors(smi)
        roles_by_atom: dict[int, set[str]] = {}
        for site in chemistry.feature_sites:
            roles_by_atom.setdefault(int(site.atom_idx), set()).add(str(site.role))
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
            roles = roles_by_atom.get(int(atom.GetIdx()), set())
            if roles == {"donor", "acceptor"}:
                donor_acceptor_roles.append("donor_acceptor")
            elif "donor" in roles:
                donor_acceptor_roles.append("donor")
            elif "acceptor" in roles:
                donor_acceptor_roles.append("acceptor")
            else:
                donor_acceptor_roles.append("none")
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
                hbond_site_count=chemistry.donor_site_count + chemistry.acceptor_site_count,
                ring_atom_count=sum(1 for flag in ring_flags if flag),
                formal_charge_sum=sum(formal_charges),
                charged_atom_count=chemistry.charged_atom_count,
                chiral_center_count=chemistry.chiral_center_count,
                specified_chiral_center_count=chemistry.specified_chiral_center_count,
                unassigned_chiral_center_count=chemistry.unassigned_chiral_center_count,
                protonation_source=chemistry.protonation_source,
                protonation_policy=chemistry.protonation_policy,
                protonation_ph_values=chemistry.protonation_ph_values,
                protonation_claim_boundary=chemistry.protonation_claim_boundary,
                tautomer_source=chemistry.tautomer_source,
                canonical_tautomer_smiles=chemistry.canonical_tautomer_smiles,
                tautomer_count=chemistry.tautomer_count,
                potential_stereo_count=chemistry.potential_stereo_count,
                specified_stereo_count=chemistry.specified_stereo_count,
                unassigned_stereo_count=chemistry.unassigned_stereo_count,
                unassigned_stereo_bond_count=chemistry.unassigned_stereo_bond_count,
                feature_source=chemistry.feature_source,
                donor_site_count=chemistry.donor_site_count,
                acceptor_site_count=chemistry.acceptor_site_count,
                feature_sites=[site.to_dict() for site in chemistry.feature_sites],
                salt_parent_smiles=chemistry.salt_parent_smiles,
                fragment_count=chemistry.fragment_count,
                salt_stripped=chemistry.salt_stripped,
                rotor_perception=rotors,
                blockers=list(chemistry.claim_safe_blockers),
            ),
            rotor_perception=rotors,
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
