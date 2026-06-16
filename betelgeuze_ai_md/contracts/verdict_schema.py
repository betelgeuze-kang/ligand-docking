from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from betelgeuze_ai_md.contracts.claim_scope import (
    CLAIM_SCOPE_RESTRICTED_LOCAL,
    PRODUCT_CLAIM_BOUNDARY_TEXT,
    TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE,
    validate_claim_fields,
)
from betelgeuze_ai_md.contracts.errors import ContractValidationError
from betelgeuze_ai_md.contracts.serialization import sha256_payload, to_plain


@dataclass(frozen=True)
class Verdict:
    claim_safe: bool
    verdict_label: str
    claim_scope: str = CLAIM_SCOPE_RESTRICTED_LOCAL
    topology_fidelity: str = TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE
    accuracy_claim_grade: str = "restricted-local-delivery"
    confidence: float = 0.0
    failure_flags: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    claim_boundary: str = PRODUCT_CLAIM_BOUNDARY_TEXT

    def __post_init__(self) -> None:
        label = str(self.verdict_label or "").strip()
        if not label:
            raise ContractValidationError("verdict_label is required")
        object.__setattr__(self, "verdict_label", label)
        object.__setattr__(self, "confidence", float(self.confidence))
        if not 0.0 <= self.confidence <= 1.0:
            raise ContractValidationError("confidence must be in [0, 1]")
        validate_claim_fields(
            claim_scope=self.claim_scope,
            topology_fidelity=self.topology_fidelity,
            accuracy_claim_grade=self.accuracy_claim_grade,
        )
        if self.claim_safe and self.failure_flags:
            raise ContractValidationError("claim_safe verdict cannot contain failure_flags")

    def to_dict(self) -> dict[str, Any]:
        return to_plain(self)

    def contract_hash(self) -> str:
        return sha256_payload(self)
