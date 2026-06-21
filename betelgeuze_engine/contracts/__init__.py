"""Shared contracts for product engine modules."""

from betelgeuze_engine.contracts.claim import ClaimMetadata, default_claim_metadata
from betelgeuze_engine.contracts.result import (
    BOUNDED_CORRECTION_CLAIM_KEYS,
    BOUNDED_CORRECTION_POLICY_CAP_KEYS,
    REQUIRED_CLAIM_METADATA_KEYS,
    REQUIRED_FORCE_TERM_CLAIM_KEYS,
    EnergyForces,
    PRODUCT_CORRECTION_POLICY_CAP_KEYS,
    TermResult,
    normalize_bounded_correction_policy_caps,
    term_result_requests_bounded_correction_validation,
    validate_energy_forces_contract,
    validate_term_result_contract,
)
from betelgeuze_engine.contracts.state import EngineState

__all__ = [
    "ClaimMetadata",
    "BOUNDED_CORRECTION_CLAIM_KEYS",
    "BOUNDED_CORRECTION_POLICY_CAP_KEYS",
    "EnergyForces",
    "EngineState",
    "PRODUCT_CORRECTION_POLICY_CAP_KEYS",
    "REQUIRED_CLAIM_METADATA_KEYS",
    "REQUIRED_FORCE_TERM_CLAIM_KEYS",
    "TermResult",
    "default_claim_metadata",
    "normalize_bounded_correction_policy_caps",
    "term_result_requests_bounded_correction_validation",
    "validate_energy_forces_contract",
    "validate_term_result_contract",
]
