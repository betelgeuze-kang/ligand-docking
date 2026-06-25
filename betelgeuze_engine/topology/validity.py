from __future__ import annotations

from typing import Any

from betelgeuze_engine.contracts.claim import default_claim_metadata
from betelgeuze_engine.topology.complex import ComplexTopology


def _ligand_validity_blocked_reason(validity: dict[str, Any]) -> str:
    blockers = validity.get("claim_safe_blockers")
    if isinstance(blockers, list):
        text = ";".join(str(v) for v in blockers if str(v))
        if text:
            return text
    return str(validity.get("blocked_reason") or validity.get("reason") or "ligand_topology_invalid")


def topology_claim_metadata(complex_topology: ComplexTopology) -> dict[str, Any]:
    validity = complex_topology.ligand.validity
    ligand_valid = bool(validity.get("valid"))
    ligand_claim_safe = bool(validity.get("claim_safe") is True)
    fidelity = str(complex_topology.protein.fidelity)
    protein_residue_count = int(complex_topology.protein.residue_indices.numel())
    protein_topology_valid = protein_residue_count > 0
    pocket_indices = [int(v) for v in complex_topology.pocket_residue_indices]
    pocket_indices_valid = all(0 <= idx < protein_residue_count for idx in pocket_indices)
    claim_safe = (
        ligand_claim_safe
        and fidelity == "sequence_mapped"
        and protein_topology_valid
        and pocket_indices_valid
    )
    if not ligand_valid:
        blocked = _ligand_validity_blocked_reason(validity)
    elif not ligand_claim_safe:
        blocked = _ligand_validity_blocked_reason(validity)
    elif not protein_topology_valid:
        blocked = "empty_protein_topology"
    elif fidelity != "sequence_mapped":
        blocked = "placeholder_alanine_topology"
    elif not pocket_indices_valid:
        blocked = "invalid_pocket_residue_indices"
    else:
        blocked = ""
    return default_claim_metadata(
        topology_fidelity=fidelity,
        ligand_topology_valid=ligand_valid,
        claim_safe=claim_safe,
        blocked_reason=blocked,
        claim_scope=complex_topology.claim_scope,
        protein_residue_count=protein_residue_count,
        protein_topology_valid=protein_topology_valid,
        protein_topology_blocker="" if protein_topology_valid else "empty_protein_topology",
        pocket_residue_count=len(pocket_indices),
        pocket_residue_indices=pocket_indices,
        pocket_residue_indices_valid=pocket_indices_valid,
        pocket_topology_blocker="" if pocket_indices_valid else "invalid_pocket_residue_indices",
        ligand_topology_schema_version=str(validity.get("schema_version") or ""),
        ligand_topology_claim_safe=ligand_claim_safe,
        ligand_topology_source=str(validity.get("source") or ""),
        ligand_atom_count=int(validity.get("atom_count") or len(complex_topology.ligand.atom_elements)),
        ligand_hbond_site_count=int(validity.get("hbond_site_count") or 0),
        ligand_ring_atom_count=int(validity.get("ring_atom_count") or 0),
        ligand_formal_charge_sum=int(validity.get("formal_charge_sum") or 0),
        ligand_charged_atom_count=int(validity.get("charged_atom_count") or 0),
        ligand_chiral_center_count=int(validity.get("chiral_center_count") or 0),
        ligand_specified_chiral_center_count=int(validity.get("specified_chiral_center_count") or 0),
        ligand_unassigned_chiral_center_count=int(validity.get("unassigned_chiral_center_count") or 0),
        ligand_chirality_status=str(validity.get("chirality_status") or "not_assessed"),
        ligand_chirality_valid=bool(validity.get("chirality_valid") is True),
        ligand_ring_status=str(validity.get("ring_status") or "not_assessed"),
        ligand_ring_valid=bool(validity.get("ring_valid") is True),
        ligand_protonation_status=str(validity.get("protonation_status") or "not_assessed"),
        ligand_protonation_source=str(validity.get("protonation_source") or "not_assessed"),
        ligand_protonation_valid=bool(validity.get("protonation_valid") is True),
        ligand_tautomer_status=str(validity.get("tautomer_status") or "not_assessed"),
        ligand_tautomer_source=str(validity.get("tautomer_source") or "not_assessed"),
        ligand_canonical_tautomer_smiles=str(validity.get("canonical_tautomer_smiles") or ""),
        ligand_tautomer_count=int(validity.get("tautomer_count") or 0),
        ligand_tautomer_valid=bool(validity.get("tautomer_valid") is True),
        ligand_feature_source=str(validity.get("feature_source") or "not_assessed"),
        ligand_donor_site_count=int(validity.get("donor_site_count") or 0),
        ligand_acceptor_site_count=int(validity.get("acceptor_site_count") or 0),
        ligand_salt_parent_smiles=str(validity.get("salt_parent_smiles") or ""),
        ligand_fragment_count=int(validity.get("fragment_count") or 0),
        ligand_salt_stripped=bool(validity.get("salt_stripped") is True),
        ligand_validity_blockers=list(validity.get("claim_safe_blockers") or []),
    )
