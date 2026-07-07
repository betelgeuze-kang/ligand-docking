"""Customer-facing response contract for the product docking API.

The internal docking job *record* (see
``betelgeuze_product.docking_request.build_docking_job_record``) carries ~80
flat fields, including deep internal diagnostics and, historically, an internal
filesystem ``ledger_path``. Returning that record verbatim from the public API
leaks internal paths and gives integrators an unstable, sprawling surface.

This module defines a small, stable, grouped response shape that the customer
API and the GUI can depend on:

- A short set of top-level identity/status fields.
- Grouped summaries: ``validation``, ``structure``, ``progress``, ``dispatch``,
  ``claim``, and ``links``.
- Internal diagnostics are exposed **only** when ``debug=True`` under a single
  ``diagnostics`` key, and the internal ``ledger_path`` is never exposed.

It is intentionally dependency-free (stdlib + typing only) so it can be unit
tested without FastAPI/Pydantic being installed.
"""

from __future__ import annotations

from typing import Any

# Single source of truth for the stable top-level keys of the docking
# submission response. ``api_contract`` imports this so the static API contract
# check and the live response can never drift apart.
DOCKING_SUBMISSION_TOP_LEVEL_KEYS = frozenset(
    {
        "job_id",
        "status",
        "request_type",
        "family",
        "target_id",
        "customer_id",
        "user_id",
        "validation_status",
        "execution_enabled",
        "docking_results_emitted",
        "validation",
        "structure",
        "progress",
        "dispatch",
        "claim",
        "links",
        "claim_boundary",
    }
)

# Verbose internal fields surfaced only under debug=True. Deliberately excludes
# the internal ledger_path and any sensitive raw input.
DOCKING_DIAGNOSTIC_KEYS: tuple[str, ...] = (
    "production_ai_inference_subject_active",
    "production_ai_correction_applied",
    "production_ai_abstention_enforced",
    "production_ai_abstention_reason",
    "production_ai_what_would_change_decision",
    "production_ai_default_residual_mode",
    "production_ai_promotion_allowed",
    "production_ai_customer_facing_auto_correction_allowed",
    "production_ai_customer_facing_score_mutation_allowed",
    "production_ai_customer_facing_ranking_mutation_allowed",
    "production_ai_trained_checkpoint_count",
    "production_ai_selected_sidecar_ready",
    "production_ai_selected_sidecar_missing_output_fields",
    "production_ai_blocked_reason",
    "scope_claim_guard_ready",
    "allowed_scope_families",
    "blocked_claim_scopes",
    "claim_blocked_domains",
    "scope_claim_boundary_detail",
    "ai_decision_graph_trace_ready",
    "ai_decision_graph_ordered_path",
    "ai_decision_graph_node_count",
    "ai_decision_graph_edge_count",
    "ai_decision_graph_blocked_node_ids",
    "ai_decision_graph_abstention_node_id",
    "ai_decision_graph_current_node_id",
    "ai_decision_graph_trace",
    "ai_decision_graph_edges",
    "customer_report_explanation_ready",
    "customer_report_card_ready",
    "customer_report_delivery_contract_ready",
    "customer_report_evidence_binding_ready",
    "customer_report_selection_rationale_ready",
    "customer_report_uncertainty_posture_ready",
    "customer_report_prohibited_claims_ready",
    "customer_report_selection_rationale",
    "customer_report_uncertainty_posture",
    "customer_report_prohibited_claims",
    "customer_report_required_block_count",
    "customer_report_ready_block_count",
    "customer_report_blocked_block_count",
    "customer_report_section_count",
    "customer_report_required_blocks",
    "customer_report_ready_blocks",
    "customer_report_missing_blocks",
    "customer_report_primary_abstention_reason",
    "customer_report_what_would_change_decision",
    "customer_report_card",
    "customer_report_sections",
    "worker_lease_id",
    "worker_id",
    "heartbeat_at_utc",
    "worker_cancel_acknowledged",
    "worker_cancel_acknowledged_at_utc",
    "max_retry_attempts",
    "retry_policy",
    "retry_limit_reached",
    "progress_percent_range_valid",
    "status_progress_contract_ready",
    "workflow_controls_ready",
    "workflow_allowed_actions",
    "workflow_disabled_actions",
    "workflow_next_customer_actions",
    "status_transition_contract",
    "status_snapshot_persisted",
    "job_retention_policy",
    "job_retention_days",
    "rerun_manifest_ready",
    "reproducible_rerun_ready",
    "long_running_status_persistence_ready",
)

_DEFAULT_LINKS_KEYS = ("self", "history", "cancel", "retry")

PROXY_SCORE_CONTRACT: dict[str, Any] = {
    "customer_score_name": "proxy_binding_energy_score",
    "method_kind": "heuristic_proxy",
    "internal_proxy_columns": [
        "binding_energy_proxy",
        "binding_energy_mmpbsa_kcal_mol_proxy",
        "binding_energy_explicit_water_recheck_kcal_mol_proxy",
    ],
    "not_claimed_as": [
        "experimental_delta_g",
        "true_mm_pbsa",
        "absolute_binding_free_energy",
        "clinical_or_therapeutic_evidence",
    ],
    "customer_safe_label": "Proxy docking score for triage only; not an experimental ΔG or true MM/PBSA claim.",
}


def proxy_score_contract() -> dict[str, Any]:
    """Customer-safe score naming contract.

    Internal columns may keep historical names for regression compatibility, but
    the API exposes a proxy label so customer reports do not over-read heuristic
    or surrogate energies as experimental ΔG/MM-PBSA evidence.
    """

    return {
        "customer_score_name": PROXY_SCORE_CONTRACT["customer_score_name"],
        "method_kind": PROXY_SCORE_CONTRACT["method_kind"],
        "internal_proxy_columns": list(PROXY_SCORE_CONTRACT["internal_proxy_columns"]),
        "not_claimed_as": list(PROXY_SCORE_CONTRACT["not_claimed_as"]),
        "customer_safe_label": PROXY_SCORE_CONTRACT["customer_safe_label"],
    }


def docking_validation_summary(record: dict[str, Any]) -> dict[str, Any]:
    blockers = record.get("blockers") or []
    warnings = record.get("warnings") or []
    return {
        "status": record.get("validation_status", ""),
        "blocker_count": len(blockers),
        "warning_count": len(warnings),
        "blockers": list(blockers),
        "warnings": list(warnings),
    }


def docking_structure_summary(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "analysis_status": record.get("structure_analysis_status", ""),
        "source_available": bool(record.get("structure_source_available", False)),
        "atom_count": record.get("structure_atom_count", 0),
        "chain_count": record.get("structure_chain_count", 0),
        "residue_count": record.get("structure_residue_count", 0),
        "ligand_like_residue_count": record.get("structure_ligand_like_residue_count", 0),
    }


def docking_progress_summary(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "percent": record.get("progress_percent", 0.0),
        "state": record.get("progress_state", ""),
        "current_step": record.get("current_step", ""),
        "queue_status": record.get("queue_status", ""),
        "queue_position": record.get("queue_position", 0),
        "worker_state": record.get("worker_state", ""),
    }


def docking_dispatch_summary(
    record: dict[str, Any],
    dispatch_outcome: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Dispatch state.

    At submission time the live ``dispatch_outcome`` is authoritative; when
    rebuilding from a persisted record (e.g. GET) the record's own fields are
    used as the fallback.
    """

    outcome = dispatch_outcome or {}
    if "dispatched" in outcome:
        enqueued = bool(outcome.get("dispatched", False))
    else:
        enqueued = bool(record.get("worker_dispatch_enqueued", False))
    reason = str(outcome.get("reason", record.get("worker_dispatch_reason", "")))
    return {
        "engine_dispatch_ready": bool(record.get("engine_dispatch_ready", False)),
        "worker_dispatch_enqueued": enqueued,
        "worker_dispatch_reason": reason,
    }


def docking_claim_summary(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "scope_claim_status": record.get("scope_claim_status", ""),
        "scope_claim_allowed_for_request": bool(record.get("scope_claim_allowed_for_request", False)),
        "general_platform_claim_allowed": bool(record.get("general_platform_claim_allowed", False)),
        "production_promotion_allowed": bool(record.get("production_ai_promotion_allowed", False)),
        "customer_pose_emission_allowed": bool(record.get("docking_results_emitted", False)),
        "score_contract": proxy_score_contract(),
        "claim_boundary": record.get("claim_boundary", ""),
    }


def docking_links(record: dict[str, Any]) -> dict[str, Any]:
    links = record.get("workflow_control_links")
    if isinstance(links, dict) and links:
        return dict(links)
    job_id = record.get("job_id", "")
    base = f"/product/docking/jobs/{job_id}"
    return {
        "self": base,
        "history": f"{base}/history",
        "cancel": f"{base}/cancel",
        "retry": f"{base}/retry",
    }


def docking_diagnostics(record: dict[str, Any]) -> dict[str, Any]:
    """Verbose internal fields, exposed only under debug=True.

    Never includes the internal ``ledger_path`` or sensitive raw inputs.
    """

    return {key: record.get(key) for key in DOCKING_DIAGNOSTIC_KEYS}


def docking_diagnostics_envelope(record: dict[str, Any]) -> dict[str, Any]:
    """Spread-friendly ``{"diagnostics": {...}}`` for debug responses."""

    return {"diagnostics": docking_diagnostics(record)}


def build_docking_submission_response(
    record: dict[str, Any],
    *,
    dispatch_outcome: dict[str, Any] | None = None,
    debug: bool = False,
) -> dict[str, Any]:
    """Assemble the stable, grouped docking submission/status response.

    The internal ``ledger_path`` is intentionally never included.
    """

    response: dict[str, Any] = {
        "job_id": record.get("job_id", ""),
        "status": record.get("status", ""),
        "request_type": record.get("request_type", ""),
        "family": record.get("family", ""),
        "target_id": record.get("target_id", ""),
        "customer_id": record.get("customer_id", ""),
        "user_id": record.get("user_id", ""),
        "validation_status": record.get("validation_status", ""),
        "execution_enabled": bool(record.get("execution_enabled", False)),
        "docking_results_emitted": bool(record.get("docking_results_emitted", False)),
        "validation": docking_validation_summary(record),
        "structure": docking_structure_summary(record),
        "progress": docking_progress_summary(record),
        "dispatch": docking_dispatch_summary(record, dispatch_outcome),
        "claim": docking_claim_summary(record),
        "links": docking_links(record),
        "claim_boundary": record.get("claim_boundary", ""),
    }
    if debug:
        response.update(docking_diagnostics_envelope(record))
    return response
