from __future__ import annotations

from betelgeuze_ai_md.contracts.errors import ContractValidationError

CLAIM_SCOPE_RESTRICTED_LOCAL = "restricted_local_delivery"
CLAIM_SCOPE_PRODUCT_LIGAND = "product_ligand_htvs_backmapping"

GENERAL_MD_ACCURACY_CLAIM = "general-MD-accuracy"

TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE = "placeholder_alanine"
TOPOLOGY_FIDELITY_SEQUENCE_MAPPED = "sequence_mapped"

PRODUCT_CLAIM_BOUNDARY_TEXT = (
    "Restricted local-delivery scope only. Not a general-purpose OpenMM/Schrodinger-grade "
    "molecular-dynamics accuracy claim."
)


def general_md_accuracy_promotion_allowed(*, fidelity: str, claim_scope: str) -> bool:
    """Current product policy: no topology fidelity can promote a general-MD claim yet."""
    del fidelity, claim_scope
    return False


def validate_claim_fields(*, claim_scope: str, topology_fidelity: str, accuracy_claim_grade: str) -> None:
    if not str(claim_scope or "").strip():
        raise ContractValidationError("claim_scope is required")
    if not str(topology_fidelity or "").strip():
        raise ContractValidationError("topology_fidelity is required")
    if (
        str(accuracy_claim_grade or "").strip() == GENERAL_MD_ACCURACY_CLAIM
        and not general_md_accuracy_promotion_allowed(
            fidelity=str(topology_fidelity),
            claim_scope=str(claim_scope),
        )
    ):
        raise ContractValidationError(
            f"accuracy_claim_grade '{GENERAL_MD_ACCURACY_CLAIM}' is forbidden for current AI-MD contracts"
        )
