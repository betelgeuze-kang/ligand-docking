from __future__ import annotations

from typing import Any

from betelgeuze_engine.contracts.claim import default_claim_metadata
from betelgeuze_engine.contracts.result import normalize_bounded_correction_policy_caps
from betelgeuze_engine.contracts.state import EngineState

CLAIM_METADATA_KEYS = (
    "topology_fidelity",
    "ligand_topology_valid",
    "hbond_evidence_status",
    "force_residual_applied",
    "claim_safe",
    "blocked_reason",
)
PASS_STATUSES = {"pass", "ok", "not_applicable"}
BASE_CLAIM_BLOCKER_FALLBACKS = {"", "not_assessed", "term_result_unscoped"}


def claim_metadata_from_state(state: EngineState) -> dict[str, Any]:
    """Extract claim-boundary metadata carried by an EngineState."""
    nested = state.metadata.get("claim_metadata")
    source: dict[str, Any] = dict(nested) if isinstance(nested, dict) else {}
    for key in CLAIM_METADATA_KEYS:
        if key in state.metadata:
            source[key] = state.metadata[key]
    return default_claim_metadata(**source)


def state_with_claim_metadata(
    state: EngineState,
    claim_metadata: dict[str, Any] | None,
) -> EngineState:
    if not claim_metadata:
        return state
    metadata = dict(state.metadata)
    merged_source = claim_metadata_from_state(state)
    merged_source.update(dict(claim_metadata))
    merged = default_claim_metadata(**merged_source)
    metadata["claim_metadata"] = merged
    for key in CLAIM_METADATA_KEYS:
        metadata[key] = merged[key]
    return EngineState(
        coords=state.coords,
        atom_types=state.atom_types,
        residue_types=state.residue_types,
        box=state.box,
        metadata=metadata,
    )


def term_claim_metadata(
    *,
    state: EngineState,
    term_name: str,
    status: str = "pass",
    blocked_reason: str = "",
    hbond_evidence_status: str | None = None,
    extras: dict[str, Any] | None = None,
) -> dict[str, Any]:
    base = claim_metadata_from_state(state)
    clean_status = str(status or "pass")
    explicit_blocker = str(blocked_reason or "")
    if clean_status not in PASS_STATUSES and not explicit_blocker:
        explicit_blocker = f"{term_name}_{clean_status}"

    base_claim_safe = base.get("claim_safe") is True
    base_blocker = str(base.get("blocked_reason") or "")
    if base_blocker in BASE_CLAIM_BLOCKER_FALLBACKS:
        base_blocker = "force_term_base_claim_not_safe"

    term_safe = clean_status in PASS_STATUSES and not explicit_blocker
    claim_safe = bool(base_claim_safe and term_safe)
    if claim_safe:
        final_blocker = ""
    else:
        final_blocker = explicit_blocker or base_blocker

    metadata = default_claim_metadata(**base)
    if hbond_evidence_status is not None:
        metadata["hbond_evidence_status"] = str(hbond_evidence_status)
    metadata.update(
        {
            "claim_safe": claim_safe,
            "blocked_reason": final_blocker,
            "force_term_name": str(term_name),
            "force_term_status": clean_status,
        }
    )
    if extras:
        normalized_extras = dict(extras)
        caps = normalized_extras.get("force_term_policy_caps")
        if isinstance(caps, dict):
            normalized_extras["force_term_policy_caps"] = normalize_bounded_correction_policy_caps(caps)
        metadata.update(normalized_extras)
    return metadata
