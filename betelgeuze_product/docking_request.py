from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from betelgeuze_product.engine_dispatch import build_dispatch_manifest
from betelgeuze_product.payload_privacy import sanitize_request_for_ledger
from betelgeuze_product.residual_mode_policy import (
    customer_ranking_mutation_allowed_at_runtime,
    production_ai_inference_subject_active,
)
from betelgeuze_product.structure_analysis import analyze_structure_source

ROOT = Path(__file__).resolve().parents[1]
RESIDUAL_MODEL_REGISTRY_ARTIFACT = ROOT / "runs" / "residual_model_registry_current.json"
PRODUCT_AI_PROMOTION_WORKBENCH_ARTIFACT = ROOT / "runs" / "product_production_ai_promotion_workbench_current.json"
PRODUCT_SCOPE_CLAIM_GUARD_ARTIFACT = ROOT / "runs" / "product_scope_breadth_closure_checklist_current.json"
PRODUCT_EXECUTION_APPROVAL_ARTIFACT = ROOT / "runs" / "product_execution_approval_gate_current.json"
EXECUTION_APPROVAL_TOKEN = "APPROVE_PRODUCT_DOCKING_EXECUTION"
ALLOWED_SCOPE_FAMILIES = {"kinase", "gpcr", "ion_channel"}
DEFAULT_BLOCKED_CLAIM_SCOPES = [
    "transporter_domain_promotion",
    "pxr_domain_promotion",
    "general_protein_ligand_platform",
]
MAX_P0_LIGAND_COUNT = 10000
JOB_LEDGER_RETENTION_DAYS = 90
MAX_RETRY_ATTEMPTS = 3
JOB_RETRY_POLICY = "operator_requested_retry_child_preserves_request_sha256_max_3"
CLAIM_BOUNDARY = (
    "Commercial docking request contract only; validates intake and records a local fail-closed ledger. "
    "It does not run docking, emit scientific results, apply production AI correction, send data externally, or widen delivery-ready scope."
)
CUSTOMER_REPORT_REQUIRED_BLOCKS = (
    "binding_site_explanation",
    "pose_comparison",
    "interaction_rationale",
    "ligand_selection_rationale",
    "uncertainty_narrative",
    "scope_claim_limit",
    "counterfactual_rescue_suggestion",
)
AI_DECISION_GRAPH_NODE_IDS = (
    "structure_quality",
    "binding_site_context",
    "pose_generation_contract",
    "scoring_ranking_gate",
    "uncertainty_abstention_guard",
    "report_bundle_contract",
    "customer_report_ux",
)
PROHIBITED_CUSTOMER_CLAIMS = (
    "fresh_docking_pose_claim",
    "learned_score_correction_claim",
    "customer_facing_ranking_mutation_claim",
    "clinical_or_therapeutic_claim",
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _canonical_family(value: Any) -> str:
    text = _text(value).lower().replace("-", "_").replace(" ", "_")
    if text == "ionchannel":
        return "ion_channel"
    return text


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _blocker(code: str, reason: str) -> dict[str, str]:
    return {"code": code, "severity": "hard", "reason": reason}


def _read_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _execution_approval_posture(approval_packet: dict[str, Any] | None = None) -> dict[str, Any]:
    approval = _summary(approval_packet or _read_json_object(PRODUCT_EXECUTION_APPROVAL_ARTIFACT))
    gate_status = _text(approval.get("status"))
    row = {}
    rows = approval.get("rows")
    if isinstance(rows, list) and rows and isinstance(rows[0], dict):
        row = rows[0]
    row_gate_status = _text(row.get("approval_gate_status"))
    authorized = (
        approval.get("authorized_for_execution") is True
        or row_gate_status == "authorized_for_operator_execution"
        or gate_status == "authorized_for_operator_execution"
    )
    return {
        "execution_approval_gate_ready": bool(approval),
        "execution_approval_gate_status": gate_status or "missing_product_execution_approval_gate",
        "execution_approval_token_required": _text(approval.get("approval_token_required") or EXECUTION_APPROVAL_TOKEN),
        "execution_approval_authorized": authorized,
        "execution_approval_operator_csv_present": approval.get("operator_approval_csv_present") is True,
        "execution_enabled": False,
        "execution_enabled_conditional_would_enable": authorized,
        "docking_results_emitted": False,
        "docking_results_emitted_conditional_would_emit": False,
        "execution_approval_row_status": row_gate_status,
        "execution_approval_next_required_step": _text(approval.get("next_required_step"))
        or "Review product execution approval gate and provide operator approval token before scoped execution.",
    }


def _production_ai_posture_from_registry(
    registry: dict[str, Any],
    *,
    shadow_only_active_locked: bool = True,
) -> dict[str, Any]:
    default_mode = _text(registry.get("default_residual_mode"))
    trained_count = int(registry.get("trained_model_checkpoint_count") or 0)
    promotion_allowed = registry.get("production_promotion_allowed") is True
    customer_auto_correction_allowed = registry.get("customer_facing_auto_correction_allowed") is True
    customer_score_mutation_allowed = registry.get("customer_facing_score_mutation_allowed") is True
    customer_ranking_mutation_allowed = customer_ranking_mutation_allowed_at_runtime(
        registry,
        shadow_only_active_locked=shadow_only_active_locked,
    )
    active = production_ai_inference_subject_active(registry)
    blocked_reason = _text(registry.get("production_promotion_blocked_reason"))
    if not blocked_reason and not active:
        blocked_reason = "production_ai_inference_subject_not_active"
    what_would_change = _text(registry.get("what_would_change_decision"))
    if not what_would_change and not active:
        what_would_change = (
            "Return and verify GPU force-label evidence, close production training-data outputs, train a guarded "
            "checkpoint, and promote the residual model registry out of shadow mode."
        )
    return {
        "production_ai_inference_subject_active": active,
        "production_ai_correction_applied": False,
        "production_ai_abstention_enforced": not active,
        "production_ai_abstention_reason": "" if active else blocked_reason,
        "production_ai_what_would_change_decision": "" if active else what_would_change,
        "production_ai_default_residual_mode": default_mode,
        "production_ai_promotion_allowed": promotion_allowed,
        "production_ai_customer_facing_auto_correction_allowed": customer_auto_correction_allowed,
        "production_ai_customer_facing_score_mutation_allowed": customer_score_mutation_allowed,
        "production_ai_customer_facing_ranking_mutation_allowed": customer_ranking_mutation_allowed,
        "production_ai_trained_checkpoint_count": trained_count,
        "production_ai_selected_sidecar_ready": registry.get("selected_sidecar_ready") is True,
        "production_ai_selected_sidecar_missing_output_fields": list(
            registry.get("selected_sidecar_missing_output_fields") or []
        ),
        "production_ai_blocked_reason": blocked_reason,
    }


def _commercial_fail_closed_ai_posture(registry: dict[str, Any], workbench: dict[str, Any]) -> dict[str, Any]:
    blocked_reason = _text(workbench.get("next_required_step")) or "production checkpoint preflight is blocked"
    if "preflight" not in blocked_reason.lower():
        blocked_reason = f"production checkpoint preflight is blocked; {blocked_reason}"
    what_would_change = (
        "Return and verify GPU force-label evidence, close production training-data outputs, train a guarded "
        "checkpoint, and promote the residual model registry out of shadow mode."
    )
    return {
        "production_ai_inference_subject_active": False,
        "production_ai_correction_applied": False,
        "production_ai_abstention_enforced": True,
        "production_ai_abstention_reason": blocked_reason,
        "production_ai_what_would_change_decision": what_would_change,
        "production_ai_default_residual_mode": "shadow",
        "production_ai_promotion_allowed": False,
        "production_ai_customer_facing_auto_correction_allowed": False,
        "production_ai_customer_facing_score_mutation_allowed": False,
        "production_ai_customer_facing_ranking_mutation_allowed": False,
        "production_ai_trained_checkpoint_count": 0,
        "production_ai_selected_sidecar_ready": False,
        "production_ai_selected_sidecar_missing_output_fields": ["delta_force"],
        "production_ai_blocked_reason": blocked_reason,
    }


def _production_ai_posture(
    registry_packet: dict[str, Any] | None = None,
    *,
    shadow_only_active_locked: bool = True,
) -> dict[str, Any]:
    registry = _summary(registry_packet or _read_json_object(RESIDUAL_MODEL_REGISTRY_ARTIFACT))
    if registry_packet is not None:
        return _production_ai_posture_from_registry(
            registry,
            shadow_only_active_locked=shadow_only_active_locked,
        )
    workbench = _summary(_read_json_object(PRODUCT_AI_PROMOTION_WORKBENCH_ARTIFACT))
    if _bool(workbench.get("production_ai_inference_subject_active")):
        return _production_ai_posture_from_registry(
            registry,
            shadow_only_active_locked=shadow_only_active_locked,
        )
    return _commercial_fail_closed_ai_posture(registry, workbench)


def _bool(value: Any) -> bool:
    return bool(value is True)


def _redacted_ligand_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, ligand in enumerate(_as_list(payload.get("ligands")), start=1):
        rows.append({"ligand_id": _ligand_id(ligand, index), "source_redacted": True})
    return rows


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest() if value else ""


def _ligand_source_ref(ligand: dict[str, Any]) -> tuple[str, str]:
    for key in ("smiles", "inchi", "sdf_path", "mol2_path", "pdbqt_path", "compound_id"):
        value = _text(ligand.get(key))
        if value:
            return key, value
    return "", ""


def _materialization_ligand_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, ligand in enumerate(_as_list(payload.get("ligands")), start=1):
        if not isinstance(ligand, dict):
            continue
        source_kind, source_value = _ligand_source_ref(ligand)
        compound_id = _text(ligand.get("compound_id") or ligand.get("ligand_id") or ligand.get("id"))
        rows.append(
            {
                "ligand_id": _ligand_id(ligand, index),
                "compound_id_sha256": _sha256_text(compound_id),
                "source_kind": source_kind,
                "source_value_sha256": _sha256_text(source_value),
                "source_redacted": True,
            }
        )
    return rows


def _scope_claim_guard(
    *,
    family: str,
    scope_claim_guard_packet: dict[str, Any] | None = None,
) -> dict[str, Any]:
    summary = _summary(scope_claim_guard_packet or _read_json_object(PRODUCT_SCOPE_CLAIM_GUARD_ARTIFACT))
    allowed_families = [
        _canonical_family(item)
        for item in (summary.get("allowed_scope_families") or sorted(ALLOWED_SCOPE_FAMILIES))
        if _text(item)
    ]
    blocked_claim_scopes = list(DEFAULT_BLOCKED_CLAIM_SCOPES)
    extra_blocked = [
        str(item)
        for item in (summary.get("blocked_claim_scopes") or [])
        if _text(item) and str(item) not in blocked_claim_scopes
    ]
    blocked_claim_scopes.extend(extra_blocked)
    claim_blocked_domains = list(summary.get("claim_blocked_domains") or [])
    family_allowed = family in set(allowed_families)
    return {
        "scope_claim_guard_ready": bool(summary.get("closure_checklist_ready") is True or not summary),
        "scope_claim_allowed_for_request": family_allowed,
        "scope_claim_status": "allowed_restricted_delivery_scope" if family_allowed else "blocked_scope_family_not_delivery_ready",
        "allowed_scope_families": allowed_families,
        "blocked_claim_scopes": blocked_claim_scopes,
        "claim_blocked_domains": claim_blocked_domains,
        "general_platform_claim_allowed": bool(summary.get("general_platform_claim_allowed") is True),
        "scope_claim_boundary_detail": _text(summary.get("claim_boundary_detail"))
        or "allowed_scope_families=gpcr,ion_channel,kinase;general_platform_claim_allowed=False",
        "scope_claim_guard_next_required_step": _text(summary.get("next_required_step")),
    }


def request_sha256(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _job_status_snapshot(job_id: str, digest: str, status: str, customer_id: str = "", user_id: str = "") -> dict[str, Any]:
    return {
        "job_id": job_id,
        "request_sha256": digest,
        "customer_id": customer_id,
        "user_id": user_id,
        "status": status,
        "progress_percent": 0.0,
        "progress_state": "ledger_intake_recorded",
        "current_step": "contract_validation",
        "worker_state": "not_started_fail_closed",
        "worker_lease_id": "",
        "worker_id": "",
        "heartbeat_at_utc": "",
        "worker_cancel_acknowledged": False,
        "worker_cancel_acknowledged_at_utc": "",
        "queue_status": "queued_fail_closed" if status == "accepted_fail_closed" else "blocked_contract_validation",
        "progress_percent_range_valid": True,
        "status_progress_contract_ready": True,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
    }


def _customer_id(payload: dict[str, Any]) -> str:
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    return _text(payload.get("customer_id") or metadata.get("customer_id") or metadata.get("tenant_id"))


def _user_id(payload: dict[str, Any]) -> str:
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    return _text(payload.get("user_id") or metadata.get("user_id") or metadata.get("operator_id"))


def _rerun_manifest(job_id: str, digest: str, source_host: str, customer_id: str = "", user_id: str = "") -> dict[str, Any]:
    return {
        "manifest_type": "docking_job_rerun_manifest",
        "root_job_id": job_id,
        "request_sha256": digest,
        "idempotency_key": digest,
        "source_host": source_host,
        "customer_id": customer_id,
        "user_id": user_id,
        "required_replay_policy": "same_request_sha256_and_operator_retry_event",
        "rerun_command": f"POST /product/docking/jobs/{job_id}/retry",
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
    }


def _workflow_controls(
    *,
    job_id: str,
    status: str,
    queue_status: str,
    cancellable: bool,
    retryable: bool,
    retry_limit_reached: bool,
) -> dict[str, Any]:
    allowed_actions = ["view_status", "view_history"]
    if cancellable:
        allowed_actions.append("cancel")
    if retryable and not retry_limit_reached:
        allowed_actions.append("retry")
    disabled_actions = [
        action
        for action in ("cancel", "retry")
        if action not in allowed_actions
    ]
    return {
        "workflow_controls_ready": True,
        "workflow_control_links": {
            "self": f"/product/docking/jobs/{job_id}",
            "history": f"/product/docking/jobs/{job_id}/history",
            "cancel": f"/product/docking/jobs/{job_id}/cancel",
            "retry": f"/product/docking/jobs/{job_id}/retry",
        },
        "workflow_allowed_actions": allowed_actions,
        "workflow_disabled_actions": disabled_actions,
        "workflow_next_customer_actions": allowed_actions,
        "status_transition_contract": {
            "current_status": status,
            "queue_status": queue_status,
            "cancellable": cancellable,
            "retryable": retryable,
            "retry_limit_reached": retry_limit_reached,
            "terminal_state": False,
            "fail_closed": True,
            "execution_enabled": False,
            "docking_results_emitted": False,
        },
    }


def _customer_report_packet(
    *,
    normalized: dict[str, Any],
    structure_analysis: dict[str, Any],
    validation: dict[str, Any],
    ai_posture: dict[str, Any],
    scope_claim_guard: dict[str, Any],
) -> dict[str, Any]:
    primary_abstention = ai_posture["production_ai_abstention_reason"] or (
        "" if scope_claim_guard["scope_claim_allowed_for_request"] else scope_claim_guard["scope_claim_status"]
    )
    what_would_change = (
        ai_posture["production_ai_what_would_change_decision"]
        or scope_claim_guard["scope_claim_guard_next_required_step"]
        or "Resolve intake blockers and rerun the same request sha256 through the product queue."
    )
    target_id = _text(normalized.get("target_id"))
    family = _text(normalized.get("family"))
    ligand_count = int(normalized.get("ligand_count") or 0)
    structure_ready = structure_analysis.get("source_available") is True
    scope_allowed = scope_claim_guard["scope_claim_allowed_for_request"]
    ranking_mutation_allowed = ai_posture["production_ai_customer_facing_ranking_mutation_allowed"]
    production_ai_active = ai_posture["production_ai_inference_subject_active"]
    uncertainty_posture = (
        "production_guarded_active_customer_ranking_locked"
        if production_ai_active and not ranking_mutation_allowed
        else "production_guarded_active_customer_ranking_allowed"
        if production_ai_active
        else "production_ai_abstained"
    )
    selection_rationale = (
        "No ligand winner is selected in the intake ledger. Ligand ordering remains input-order only until "
        "audited pose artifacts, score provenance, and the customer ranking-mutation gate are present."
    )
    prohibited_claims = list(
        dict.fromkeys([*scope_claim_guard["blocked_claim_scopes"], *PROHIBITED_CUSTOMER_CLAIMS])
    )
    report_card = {
        "target_id": target_id,
        "family": family,
        "ligand_count": ligand_count,
        "structure_source_kind": _text(normalized.get("structure_source_kind")),
        "structure_atom_count": int(structure_analysis.get("atom_count") or 0),
        "structure_chain_count": int(structure_analysis.get("chain_count") or 0),
        "structure_residue_count": int(structure_analysis.get("residue_count") or 0),
        "structure_ligand_like_residue_count": int(
            structure_analysis.get("ligand_like_residue_count") or 0
        ),
        "validation_status": validation["status"],
        "blocker_count": len(validation["blockers"]),
        "warning_count": len(validation["warnings"]),
        "production_ai_inference_subject_active": ai_posture[
            "production_ai_inference_subject_active"
        ],
        "production_ai_correction_applied": ai_posture["production_ai_correction_applied"],
        "production_ai_abstention_enforced": ai_posture["production_ai_abstention_enforced"],
        "primary_abstention_reason": primary_abstention,
        "what_would_change_decision": what_would_change,
        "scope_claim_allowed_for_request": scope_allowed,
        "scope_claim_status": scope_claim_guard["scope_claim_status"],
        "allowed_scope_families": scope_claim_guard["allowed_scope_families"],
        "blocked_claim_scopes": scope_claim_guard["blocked_claim_scopes"],
        "general_platform_claim_allowed": scope_claim_guard["general_platform_claim_allowed"],
        "selection_rationale_ready": True,
        "selection_rationale": selection_rationale,
        "ligand_selection_policy": "no_customer_ligand_selection_without_pose_score_and_ranking_gate",
        "uncertainty_posture_ready": True,
        "uncertainty_posture": uncertainty_posture,
        "prohibited_claims_ready": True,
        "prohibited_claims": prohibited_claims,
        "result_interpretation_policy": "evidence_review_until_execution_result_manifest_is_bound",
        "ranking_mutation_policy": (
            "customer_ranking_mutation_locked_by_shadow_guard"
            if not ranking_mutation_allowed
            else "customer_ranking_mutation_allowed_by_registry_and_runtime_guard"
        ),
        "claim_limit": (
            "Customer report is an intake and evidence explanation. Docking poses, learned score corrections, "
            "and broad platform claims remain disabled until their gates are explicitly green."
        ),
    }
    sections = [
        {
            "section_id": "binding_site_explanation",
            "title": "Binding Site Explanation",
            "ready": True,
            "narrative": (
                f"Structure intake recognized {report_card['structure_atom_count']} atoms across "
                f"{report_card['structure_chain_count']} chains for target {target_id or 'unknown target'}."
                if structure_ready
                else "Binding-site explanation is limited because no single valid structure source was accepted."
            ),
            "evidence_fields": [
                "structure_source_kind",
                "structure_atom_count",
                "structure_chain_count",
                "structure_ligand_like_residue_count",
            ],
        },
        {
            "section_id": "pose_comparison",
            "title": "Pose Comparison",
            "ready": True,
            "narrative": (
                "Pose comparison is prepared as a customer report block, but no docking poses are emitted while "
                "execution_enabled=false."
            ),
            "evidence_fields": ["docking_results_emitted", "execution_enabled", "ligand_count"],
        },
        {
            "section_id": "interaction_rationale",
            "title": "Interaction Rationale",
            "ready": True,
            "narrative": (
                "Interaction rationale is presented as a guarded explanation over intake and scoring contract "
                "state until pose-level interactions are available. No customer-facing ligand winner is selected "
                "from this intake-only record."
            ),
            "evidence_fields": [
                "family",
                "target_id",
                "scope_claim_status",
                "selection_rationale",
                "ligand_selection_policy",
            ],
        },
        {
            "section_id": "ligand_selection_rationale",
            "title": "Ligand Selection Rationale",
            "ready": True,
            "narrative": selection_rationale,
            "evidence_fields": [
                "ligand_count",
                "selection_rationale",
                "ligand_selection_policy",
                "ranking_mutation_policy",
                "scope_claim_status",
            ],
        },
        {
            "section_id": "uncertainty_narrative",
            "title": "Uncertainty And Abstention",
            "ready": True,
            "narrative": primary_abstention or "Production AI abstention is not active for this record.",
            "evidence_fields": [
                "production_ai_abstention_enforced",
                "production_ai_abstention_reason",
                "production_ai_trained_checkpoint_count",
                "uncertainty_posture",
                "ranking_mutation_policy",
            ],
        },
        {
            "section_id": "scope_claim_limit",
            "title": "Scope Claim Limit",
            "ready": True,
            "narrative": (
                "This request is inside the restricted delivery scope."
                if scope_allowed
                else "This request is outside the restricted delivery scope and remains blocked."
            ),
            "evidence_fields": [
                "allowed_scope_families",
                "blocked_claim_scopes",
                "general_platform_claim_allowed",
                "prohibited_claims",
            ],
        },
        {
            "section_id": "counterfactual_rescue_suggestion",
            "title": "What Would Change This Decision",
            "ready": True,
            "narrative": what_would_change,
            "evidence_fields": [
                "production_ai_what_would_change_decision",
                "scope_claim_guard_next_required_step",
            ],
        },
    ]
    report_card["blocks"] = {
        section["section_id"]: {
            "title": section["title"],
            "status": "ready" if section["ready"] else "blocked",
            "narrative": section["narrative"],
            "claim_limit": report_card["claim_limit"],
            "abstention_reason": primary_abstention,
            "what_would_change_decision": what_would_change,
        }
        for section in sections
    }
    return {
        "customer_report_explanation_ready": True,
        "customer_report_card_ready": True,
        "customer_report_delivery_contract_ready": True,
        "customer_report_evidence_binding_ready": True,
        "customer_report_selection_rationale_ready": True,
        "customer_report_uncertainty_posture_ready": True,
        "customer_report_prohibited_claims_ready": True,
        "customer_report_selection_rationale": selection_rationale,
        "customer_report_uncertainty_posture": uncertainty_posture,
        "customer_report_prohibited_claims": prohibited_claims,
        "customer_report_required_blocks": list(CUSTOMER_REPORT_REQUIRED_BLOCKS),
        "customer_report_ready_blocks": list(CUSTOMER_REPORT_REQUIRED_BLOCKS),
        "customer_report_missing_blocks": [],
        "customer_report_required_block_count": len(CUSTOMER_REPORT_REQUIRED_BLOCKS),
        "customer_report_ready_block_count": len(CUSTOMER_REPORT_REQUIRED_BLOCKS),
        "customer_report_blocked_block_count": 0,
        "customer_report_section_count": len(sections),
        "customer_report_primary_abstention_reason": primary_abstention,
        "customer_report_what_would_change_decision": what_would_change,
        "customer_report_card": report_card,
        "customer_report_sections": sections,
    }


def _ai_decision_graph_trace(
    *,
    normalized: dict[str, Any],
    structure_analysis: dict[str, Any],
    validation: dict[str, Any],
    ai_posture: dict[str, Any],
    scope_claim_guard: dict[str, Any],
    customer_report: dict[str, Any],
    pose_generation_contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    pose_generation_contract = pose_generation_contract or {}
    scope_allowed = scope_claim_guard["scope_claim_allowed_for_request"]
    production_ai_active = ai_posture["production_ai_inference_subject_active"]
    production_abstained = ai_posture["production_ai_abstention_enforced"]
    execution_enabled = False
    docking_results_emitted = False
    nodes = [
        {
            "node_id": "structure_quality",
            "status": "ready" if structure_analysis.get("source_available") is True else "blocked",
            "customer_visible": True,
            "executed": True,
            "abstained": False,
            "evidence": {
                "structure_source_kind": _text(normalized.get("structure_source_kind")),
                "atom_count": int(structure_analysis.get("atom_count") or 0),
                "chain_count": int(structure_analysis.get("chain_count") or 0),
                "validation_status": validation["status"],
            },
        },
        {
            "node_id": "binding_site_context",
            "status": "ready" if structure_analysis.get("source_available") is True else "blocked",
            "customer_visible": True,
            "executed": True,
            "abstained": False,
            "evidence": {
                "target_id": _text(normalized.get("target_id")),
                "family": _text(normalized.get("family")),
                "structure_ligand_like_residue_count": int(
                    structure_analysis.get("ligand_like_residue_count") or 0
                ),
            },
        },
        {
            "node_id": "pose_generation_contract",
            "status": "contract_ready_execution_disabled",
            "customer_visible": True,
            "executed": False,
            "abstained": False,
            "evidence": {
                "ligand_count": int(normalized.get("ligand_count") or 0),
                "execution_enabled": execution_enabled,
                "docking_results_emitted": docking_results_emitted,
                "pocket_detection_available": bool(pose_generation_contract.get("pocket_detection_available")),
                "pocket_method": _text(pose_generation_contract.get("pocket_method")),
                "pose_generation_modes": pose_generation_contract.get("pose_generation_modes", []),
            },
        },
        {
            "node_id": "scoring_ranking_gate",
            "status": "contract_ready_no_customer_mutation",
            "customer_visible": True,
            "executed": False,
            "abstained": False,
            "evidence": {
                "production_ai_correction_applied": ai_posture["production_ai_correction_applied"],
                "production_ai_customer_facing_score_mutation_allowed": ai_posture[
                    "production_ai_customer_facing_score_mutation_allowed"
                ],
                "production_ai_customer_facing_ranking_mutation_allowed": ai_posture[
                    "production_ai_customer_facing_ranking_mutation_allowed"
                ],
            },
        },
        {
            "node_id": "uncertainty_abstention_guard",
            "status": "abstained" if production_abstained else "ready",
            "customer_visible": True,
            "executed": True,
            "abstained": production_abstained,
            "evidence": {
                "production_ai_inference_subject_active": production_ai_active,
                "production_ai_abstention_reason": ai_posture["production_ai_abstention_reason"],
                "production_ai_trained_checkpoint_count": ai_posture[
                    "production_ai_trained_checkpoint_count"
                ],
                "scope_claim_allowed_for_request": scope_allowed,
            },
        },
        {
            "node_id": "report_bundle_contract",
            "status": "ready",
            "customer_visible": True,
            "executed": True,
            "abstained": False,
            "evidence": {
                "customer_report_required_block_count": customer_report[
                    "customer_report_required_block_count"
                ],
                "customer_report_ready_block_count": customer_report[
                    "customer_report_ready_block_count"
                ],
                "customer_report_blocked_block_count": customer_report[
                    "customer_report_blocked_block_count"
                ],
            },
        },
        {
            "node_id": "customer_report_ux",
            "status": "ready",
            "customer_visible": True,
            "executed": True,
            "abstained": False,
            "evidence": {
                "customer_report_card_ready": customer_report["customer_report_card_ready"],
                "customer_report_section_count": customer_report["customer_report_section_count"],
                "primary_abstention_reason": customer_report[
                    "customer_report_primary_abstention_reason"
                ],
            },
        },
    ]
    edges = [
        {"from_node": start, "to_node": end, "status": "ready"}
        for start, end in zip(AI_DECISION_GRAPH_NODE_IDS, AI_DECISION_GRAPH_NODE_IDS[1:])
    ]
    blocked_nodes = [row["node_id"] for row in nodes if row["status"] == "blocked"]
    return {
        "ai_decision_graph_trace_ready": True,
        "ai_decision_graph_ordered_path": list(AI_DECISION_GRAPH_NODE_IDS),
        "ai_decision_graph_node_count": len(nodes),
        "ai_decision_graph_edge_count": len(edges),
        "ai_decision_graph_blocked_node_ids": blocked_nodes,
        "ai_decision_graph_abstention_node_id": (
            "uncertainty_abstention_guard" if production_abstained else ""
        ),
        "ai_decision_graph_current_node_id": "customer_report_ux",
        "ai_decision_graph_trace": nodes,
        "ai_decision_graph_edges": edges,
    }


def _structure_source(payload: dict[str, Any]) -> dict[str, str]:
    candidates = {
        "pdb_id": _text(payload.get("pdb_id")),
        "pdb_path": _text(payload.get("pdb_path")),
        "pdb_content": _text(payload.get("pdb_content")),
        "mmcif_path": _text(payload.get("mmcif_path")),
        "mmcif_content": _text(payload.get("mmcif_content")),
    }
    present = {key: value for key, value in candidates.items() if value}
    return present


def _ligand_id(row: Any, index: int) -> str:
    if isinstance(row, dict):
        return _text(row.get("ligand_id") or row.get("id") or row.get("name") or f"ligand_{index}")
    return f"ligand_{index}"


def _ligand_has_source(row: Any) -> bool:
    if not isinstance(row, dict):
        return bool(_text(row))
    for key in ("smiles", "sdf_path", "mol2_path", "pdbqt_path", "inchi", "compound_id"):
        if _text(row.get(key)):
            return True
    return False


def validate_docking_request(payload: dict[str, Any]) -> dict[str, Any]:
    blockers: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    family = _canonical_family(payload.get("family") or payload.get("scope_family"))
    ligands = _as_list(payload.get("ligands"))
    structure_source = _structure_source(payload)
    request_type = _text(payload.get("request_type") or "structure_analysis_ligand_docking")

    if request_type not in {"structure_analysis_ligand_docking", "ligand_docking", "docking_screen"}:
        blockers.append(_blocker("unsupported_request_type", "Request type must be a structure-analysis or ligand-docking product request."))
    if family not in ALLOWED_SCOPE_FAMILIES:
        blockers.append(
            _blocker(
                "scope_family_not_delivery_ready",
                "Initial commercial delivery scope is restricted to kinase, gpcr, and ion_channel.",
            )
        )
    if not _text(payload.get("target_id") or payload.get("target_name")):
        blockers.append(_blocker("target_id_missing", "A stable target_id or target_name is required."))
    if not structure_source:
        blockers.append(_blocker("structure_source_missing", "Provide one structure source: pdb_id, pdb_path, pdb_content, mmcif_path, or mmcif_content."))
    if len(structure_source) > 1:
        blockers.append(_blocker("multiple_structure_sources", "Provide exactly one structure source for reproducible product intake."))
    if not ligands:
        blockers.append(_blocker("ligands_missing", "At least one ligand row is required for a docking request."))
    if len(ligands) > MAX_P0_LIGAND_COUNT:
        blockers.append(_blocker("ligand_count_exceeds_p0_limit", f"P0 intake is capped at {MAX_P0_LIGAND_COUNT} ligands."))

    ligand_ids: list[str] = []
    ligand_source_missing = 0
    for index, ligand in enumerate(ligands, start=1):
        ligand_id = _ligand_id(ligand, index)
        ligand_ids.append(ligand_id)
        if not _ligand_has_source(ligand):
            ligand_source_missing += 1
    duplicate_ligand_ids = sorted({ligand_id for ligand_id in ligand_ids if ligand_ids.count(ligand_id) > 1})
    if duplicate_ligand_ids:
        blockers.append(_blocker("duplicate_ligand_ids", "Ligand ids must be unique within a product request."))
    if ligand_source_missing:
        blockers.append(_blocker("ligand_source_missing", "Every ligand row must provide smiles, sdf_path, mol2_path, pdbqt_path, inchi, or compound_id."))

    if len(ligands) > 1000:
        warnings.append({"code": "large_ligand_request", "severity": "warning", "reason": "Large ligand requests should use an externalized heavy-artifact manifest."})

    return {
        "status": "pass" if not blockers else "fail",
        "blockers": blockers,
        "warnings": warnings,
        "normalized": {
            "request_type": request_type,
            "family": family,
            "target_id": _text(payload.get("target_id") or payload.get("target_name")),
            "structure_source_kind": next(iter(structure_source.keys()), ""),
            "ligand_count": len(ligands),
            "ligand_ids": ligand_ids,
        },
        "claim_boundary": CLAIM_BOUNDARY,
    }


def _pose_generation_contract(payload: dict[str, Any], normalized: dict[str, Any]) -> dict[str, Any]:
    """Preview pose-generation capability without emitting customer poses (fail-closed)."""
    contract: dict[str, Any] = {
        "pose_generation_modes": ["standard", "cross_docking", "induced_fit"],
        "planned_poses_per_ligand": 3,
        "pocket_detection_available": False,
        "pocket_method": "",
        "execution_enabled": False,
        "docking_results_emitted": False,
    }
    pdb_text = _text(payload.get("pdb_content"))
    if not pdb_text:
        path_value = _text(payload.get("pdb_path"))
        if path_value:
            candidate = Path(path_value)
            if not candidate.is_absolute():
                candidate = ROOT / candidate
            if candidate.is_file():
                try:
                    pdb_text = candidate.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    pdb_text = ""
    if not pdb_text:
        return contract
    try:
        import numpy as np

        from core.pocket_detection import detect_binding_pocket
        from core.structure_metrics import parse_pdb_atoms_with_coords

        atoms = parse_pdb_atoms_with_coords(pdb_text)
        protein_atoms = [a for a in atoms if a.get("record") == "ATOM"]
        if protein_atoms:
            coords = np.stack([a["xyz"] for a in protein_atoms], axis=0)
            pocket = detect_binding_pocket(coords)
            contract["pocket_detection_available"] = pocket.get("status") == "pocket_ready"
            contract["pocket_method"] = pocket.get("method", "")
            contract["pocket_center"] = pocket.get("pocket_center")
            contract["pocket_radius_a"] = pocket.get("pocket_radius_a")
    except Exception:
        return contract
    return contract


def build_docking_job_record(
    payload: dict[str, Any],
    *,
    job_id: str | None = None,
    source_host: str = "",
    residual_registry_packet: dict[str, Any] | None = None,
    scope_claim_guard_packet: dict[str, Any] | None = None,
    shadow_only_active_locked: bool = True,
) -> dict[str, Any]:
    validation = validate_docking_request(payload)
    normalized = validation["normalized"]
    structure_analysis = analyze_structure_source(payload)
    pose_generation_contract = _pose_generation_contract(payload, normalized)
    ai_posture = _production_ai_posture(
        residual_registry_packet,
        shadow_only_active_locked=shadow_only_active_locked,
    )
    execution_approval = _execution_approval_posture()
    scope_claim_guard = _scope_claim_guard(
        family=normalized["family"],
        scope_claim_guard_packet=scope_claim_guard_packet,
    )
    customer_report = _customer_report_packet(
        normalized=normalized,
        structure_analysis=structure_analysis,
        validation=validation,
        ai_posture=ai_posture,
        scope_claim_guard=scope_claim_guard,
    )
    ai_decision_trace = _ai_decision_graph_trace(
        normalized=normalized,
        structure_analysis=structure_analysis,
        validation=validation,
        ai_posture=ai_posture,
        scope_claim_guard=scope_claim_guard,
        customer_report=customer_report,
        pose_generation_contract=pose_generation_contract,
    )
    digest = request_sha256(payload)
    resolved_job_id = job_id or str(uuid.uuid4())
    status = "accepted_fail_closed" if validation["status"] == "pass" else "blocked_contract_validation"
    customer_id = _customer_id(payload)
    user_id = _user_id(payload)
    queue_status = "queued_fail_closed" if status == "accepted_fail_closed" else "blocked_contract_validation"
    cancellable = True
    retryable = True
    retry_limit_reached = False
    workflow_controls = _workflow_controls(
        job_id=resolved_job_id,
        status=status,
        queue_status=queue_status,
        cancellable=cancellable,
        retryable=retryable,
        retry_limit_reached=retry_limit_reached,
    )
    engine_dispatch = build_dispatch_manifest(
        job_id=resolved_job_id,
        target_id=str(normalized["target_id"]),
        family=str(normalized["family"]),
        ligand_model_hint="auto",
    )
    return {
        "job_id": resolved_job_id,
        "status": status,
        "created_at_utc": utc_now_iso(),
        "updated_at_utc": "",
        "attempt_index": 1,
        "root_job_id": resolved_job_id,
        "retry_of_job_id": "",
        "parent_job_id": "",
        "last_event_type": "created",
        "event_history": [
            {
                "event_type": "created",
                "created_at_utc": utc_now_iso(),
                "reason": "docking intake ledger created",
                "actor": source_host,
                "execution_enabled": False,
                "docking_results_emitted": False,
                "external_state_mutated": False,
            }
        ],
        "source_host": source_host,
        "customer_id": customer_id,
        "user_id": user_id,
        "request_sha256": digest,
        "idempotency_key": digest,
        "request_type": normalized["request_type"],
        "target_id": normalized["target_id"],
        "family": normalized["family"],
        "structure_source_kind": normalized["structure_source_kind"],
        "ligand_count": normalized["ligand_count"],
        "structure_analysis_status": structure_analysis["status"],
        "structure_source_available": structure_analysis["source_available"],
        "structure_atom_count": structure_analysis["atom_count"],
        "structure_chain_count": structure_analysis["chain_count"],
        "structure_residue_count": structure_analysis["residue_count"],
        "structure_ligand_like_residue_count": structure_analysis["ligand_like_residue_count"],
        "structure_analysis": structure_analysis,
        "pose_generation_contract": pose_generation_contract,
        "pocket_detection_available": bool(pose_generation_contract.get("pocket_detection_available")),
        "validation_status": validation["status"],
        "blockers": validation["blockers"],
        "warnings": validation["warnings"],
        "progress_percent": 0.0,
        "progress_state": "ledger_intake_recorded",
        "current_step": "contract_validation",
        "worker_state": "not_started_fail_closed",
        "worker_lease_id": "",
        "worker_id": "",
        "heartbeat_at_utc": "",
        "worker_cancel_acknowledged": False,
        "worker_cancel_acknowledged_at_utc": "",
        "queue_status": queue_status,
        "queue_position": 0,
        "max_retry_attempts": MAX_RETRY_ATTEMPTS,
        "retry_policy": JOB_RETRY_POLICY,
        "progress_percent_range_valid": True,
        "status_progress_contract_ready": True,
        "retry_limit_reached": retry_limit_reached,
        "status_snapshot": _job_status_snapshot(resolved_job_id, digest, status, customer_id, user_id),
        "status_snapshot_persisted": True,
        "job_retention_policy": "local_job_ledger_retain_90_days_minimum",
        "job_retention_days": JOB_LEDGER_RETENTION_DAYS,
        "rerun_manifest": _rerun_manifest(resolved_job_id, digest, source_host, customer_id, user_id),
        "rerun_manifest_ready": True,
        "reproducible_rerun_ready": True,
        "long_running_status_persistence_ready": True,
        "cancellable": cancellable,
        "retryable": retryable,
        "execution_enabled": False,
        "docking_results_emitted": False,
        **ai_posture,
        **execution_approval,
        **scope_claim_guard,
        "external_state_mutated": False,
        **workflow_controls,
        **ai_decision_trace,
        **customer_report,
        "heavy_artifact_policy": "manifest_first_externalize_before_delete",
        "engine_dispatch_manifest": engine_dispatch,
        "engine_dispatch_ready": bool(engine_dispatch.get("dispatch_ready", False)),
        "scoring_ranking_contract_ready": bool(engine_dispatch.get("engine_roadmap_ready", False)),
        "intake_payload": {
            "family": str(normalized["family"]),
            "target_id": str(normalized["target_id"]),
            "structure_source_kind": str(normalized["structure_source_kind"]),
            "ligand_count": int(normalized["ligand_count"]),
            "ligands": _redacted_ligand_rows(payload),
            "pdb_id": _text(payload.get("pdb_id")),
            "pdb_path": _text(payload.get("pdb_path")),
            "mmcif_path": _text(payload.get("mmcif_path")),
        },
        "materialization_ligands": (
            _materialization_ligand_rows(payload) if execution_approval.get("execution_approval_authorized") else []
        ),
        "claim_boundary": CLAIM_BOUNDARY,
    }


def persist_docking_job_record(record: dict[str, Any], jobs_dir: Path) -> Path:
    jobs_dir.mkdir(parents=True, exist_ok=True)
    out_path = jobs_dir / f"{record['job_id']}.json"
    safe_record = sanitize_request_for_ledger(record)
    out_path.write_text(json.dumps(safe_record, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return out_path
