from __future__ import annotations

from typing import Any

RESTRICTED_LOCAL_DELIVERY_SCOPE = "restricted_local_delivery"
GENERAL_MD_ACCURACY_CLAIM = "general-MD-accuracy"

TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE = "placeholder_alanine"
TOPOLOGY_FIDELITY_SEQUENCE_MAPPED = "sequence_mapped"

CLAIM_SCOPE_PRODUCT_LIGAND = "product_ligand_htvs_backmapping"
CLAIM_SCOPE_RESTRICTED_LOCAL = RESTRICTED_LOCAL_DELIVERY_SCOPE

PRODUCT_CLAIM_BOUNDARY_TEXT = (
    "Restricted local-delivery scope only. Not a general-purpose OpenMM/Schrödinger-grade "
    "molecular-dynamics accuracy claim."
)


def topology_fidelity_for_residue_types(residue_types_source: str | None) -> str:
    if str(residue_types_source or "").strip() == TOPOLOGY_FIDELITY_SEQUENCE_MAPPED:
        return TOPOLOGY_FIDELITY_SEQUENCE_MAPPED
    return TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE


def default_topology_claim_metadata(*, residue_types_source: str | None = None) -> dict[str, str]:
    fidelity = topology_fidelity_for_residue_types(residue_types_source)
    return {
        "topology_fidelity": fidelity,
        "claim_scope": CLAIM_SCOPE_RESTRICTED_LOCAL,
        "accuracy_claim_grade": _accuracy_grade_for_fidelity(fidelity),
        "claim_boundary": PRODUCT_CLAIM_BOUNDARY_TEXT,
    }


def _accuracy_grade_for_fidelity(fidelity: str) -> str:
    if fidelity == TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE:
        return "restricted-local-delivery"
    return "restricted-local-delivery"


def general_md_accuracy_promotion_allowed(*, fidelity: str, claim_scope: str) -> bool:
    if fidelity == TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE:
        return False
    if claim_scope != CLAIM_SCOPE_RESTRICTED_LOCAL and claim_scope != CLAIM_SCOPE_PRODUCT_LIGAND:
        return False
    return False


def validate_manifest_claim_fields(manifest: dict[str, Any]) -> None:
    fidelity = str(manifest.get("fidelity", "") or manifest.get("topology_fidelity", "") or "").strip()
    claim_scope = str(manifest.get("claim_scope", "") or "").strip()
    accuracy_grade = str(manifest.get("accuracy_claim_grade", "") or "").strip()
    if not fidelity or not claim_scope:
        raise ValueError("manifest requires fidelity and claim_scope")
    if accuracy_grade == GENERAL_MD_ACCURACY_CLAIM and not general_md_accuracy_promotion_allowed(
        fidelity=fidelity,
        claim_scope=claim_scope,
    ):
        raise ValueError(
            f"accuracy_claim_grade '{GENERAL_MD_ACCURACY_CLAIM}' is forbidden for fidelity={fidelity}"
        )
