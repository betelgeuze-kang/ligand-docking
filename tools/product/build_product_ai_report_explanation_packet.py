#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DECISION_GRAPH_JSON = "runs/product_ai_decision_graph_contract_current.json"
DEFAULT_STRUCTURE_REPORT_JSON = "runs/product_structure_analysis_report_current.json"
DEFAULT_EXECUTION_PREFLIGHT_JSON = "runs/product_execution_preflight_current.json"
DEFAULT_BUNDLE_JSON = "runs/product_bundle_contract_current.json"
DEFAULT_REGISTRY_JSON = "runs/residual_model_registry_current.json"
DEFAULT_SCOPE_CLAIM_GUARD_JSON = "runs/product_scope_breadth_closure_checklist_current.json"
DEFAULT_OUT_JSON = "runs/product_ai_report_explanation_packet_current.json"
DEFAULT_OUT_CSV = "runs/product_ai_report_explanation_packet_current.csv"
DEFAULT_OUT_MD = "runs/product_ai_report_explanation_packet_current.md"

REQUIRED_SECTIONS = (
    "binding_site_explanation",
    "pose_comparison",
    "interaction_rationale",
    "ligand_selection_rationale",
    "uncertainty_narrative",
    "scope_claim_limit",
    "counterfactual_rescue_suggestion",
)
REQUIRED_CUSTOMER_REPORT_BLOCKS = REQUIRED_SECTIONS
REQUIRED_STRUCTURED_FIELDS = (
    "customer_question",
    "claim_limit",
    "abstention_reason",
    "what_would_change_decision",
    "confidence_posture",
    "evidence_traceability",
)

CLAIM_BOUNDARY = (
    "Product AI report explanation packet only; transforms existing local structure, preflight, bundle, registry, and "
    "decision-graph evidence into customer-facing explanation sections. It does not render a browser, run docking, run "
    "model inference, train models, promote production mode, upload, email, delete, or mutate external state."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
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


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _bool(value: Any) -> bool:
    return value is True


def _section(
    section_id: str,
    status: str,
    evidence: str,
    title: str,
    narrative: str,
    customer_takeaway: str,
    next_action: str,
    *,
    customer_question: str,
    claim_limit: str,
    abstention_reason: str,
    what_would_change_decision: str,
    confidence_posture: str,
    evidence_traceability: str,
) -> dict[str, Any]:
    return {
        "section_id": section_id,
        "status": status,
        "evidence": evidence,
        "evidence_refs": [item for item in evidence.split(";") if item],
        "title": title,
        "customer_question": customer_question,
        "narrative": narrative,
        "customer_takeaway": customer_takeaway,
        "claim_limit": claim_limit,
        "abstention_reason": abstention_reason,
        "what_would_change_decision": what_would_change_decision,
        "confidence_posture": confidence_posture,
        "evidence_traceability": evidence_traceability,
        "next_action": next_action,
        "release_blocker": status != "ready",
        "execution_enabled": False,
        "docking_results_emitted": False,
        "model_inference_executed": False,
        "external_state_mutated": False,
    }


def build_product_ai_report_explanation_packet(
    *,
    decision_graph_packet: dict[str, Any],
    structure_report_packet: dict[str, Any],
    execution_preflight_packet: dict[str, Any],
    bundle_packet: dict[str, Any],
    registry_packet: dict[str, Any],
    scope_claim_guard_packet: dict[str, Any] | None = None,
    decision_graph_path: str = DEFAULT_DECISION_GRAPH_JSON,
    structure_report_path: str = DEFAULT_STRUCTURE_REPORT_JSON,
    execution_preflight_path: str = DEFAULT_EXECUTION_PREFLIGHT_JSON,
    bundle_path: str = DEFAULT_BUNDLE_JSON,
    registry_path: str = DEFAULT_REGISTRY_JSON,
    scope_claim_guard_path: str = DEFAULT_SCOPE_CLAIM_GUARD_JSON,
) -> dict[str, Any]:
    graph = _summary(decision_graph_packet)
    structure = _summary(structure_report_packet)
    preflight = _summary(execution_preflight_packet)
    bundle = _summary(bundle_packet)
    registry = _summary(registry_packet)
    scope = _summary(scope_claim_guard_packet or {})
    command_check = execution_preflight_packet.get("execution_command_check")
    command_check = command_check if isinstance(command_check, dict) else {}
    command_argv = command_check.get("argv") if isinstance(command_check.get("argv"), list) else []

    def _argv_value(flag: str) -> str:
        for index, value in enumerate(command_argv):
            if str(value) == flag and index + 1 < len(command_argv):
                return _text(command_argv[index + 1])
        return ""

    graph_ready = _bool(graph.get("closed_loop_decision_graph_ready"))
    structure_ready = (
        _text(structure.get("status")) == "product_structure_analysis_report_ready"
        and _bool(structure.get("local_structure_parsed"))
        and _int(structure.get("atom_count")) > 0
    )
    pose_ready = (
        _text(preflight.get("status")) == "product_execution_preflight_ready"
        and _text(preflight.get("operational_gate_feasibility_status")) == "pass"
        and _text(bundle.get("status")) == "product_bundle_contract_ready"
    )
    production_promotion_allowed = registry.get("production_promotion_allowed") is True
    default_residual_mode = _text(registry.get("default_residual_mode")) or "unknown"
    missing_sidecar_outputs = ",".join(str(item) for item in registry.get("selected_sidecar_missing_output_fields") or [])
    shadow_abstention_ready = (
        default_residual_mode in {"shadow", "shadow_only"}
        and not production_promotion_allowed
    )
    guarded_active_ready = (
        default_residual_mode == "production_guarded"
        and production_promotion_allowed
        and registry.get("customer_facing_auto_correction_allowed") is True
        and registry.get("customer_facing_score_mutation_allowed") is True
        and registry.get("selected_sidecar_ready") is True
        and not missing_sidecar_outputs
    )
    uncertainty_ready = (
        _text(registry.get("status")) == "residual_model_registry_ready"
        and (shadow_abstention_ready or guarded_active_ready)
    )
    bundle_ready = _text(bundle.get("expected_bundle_dir")) and _bool(bundle.get("bundle_validation_command_matches"))
    ligand_context_ready = _int(structure.get("ligand_like_residue_count")) > 0
    ranking_score_col = _argv_value("--ranking-score-col") or _argv_value("--ranking-probability-score-col") or "not_reported"
    distance_gate = _argv_value("--gate-max-mean-min-distance-A") or "not_reported"
    topk_hit_gate = _argv_value("--gate-topk-hit-rate-min") or "not_reported"
    ranking_score_ready = ranking_score_col != "not_reported"
    abstention_reason = (
        "production_residual_checkpoint_not_promoted"
        if not production_promotion_allowed
        else "production_guarded_active_report_packet_does_not_apply_correction"
    )
    force_receipt_ready = registry.get("selected_sidecar_force_receipt_ready") is True
    checkpoint_change_condition = (
        "Bind a signed execution result manifest, preserve score/ranking provenance, and keep customer-facing "
        "correction or ranking changes separately audited from this explanation packet."
        if guarded_active_ready
        else (
            "Return and verify the full GPU force-label receipt, derive delta_force/uncertainty labels, train a "
            "checkpoint, and promote the residual model registry out of shadow mode."
        )
    )
    target = _text(structure.get("target_id")) or _text(preflight.get("target_id")) or "target"
    family = _text(structure.get("family")) or _text(preflight.get("family")) or "unknown"
    atom_count = _int(structure.get("atom_count"))
    chain_count_text = _text(structure.get("chain_count")) or "not_reported"
    residue_count_text = _text(structure.get("residue_count")) or "not_reported"
    ligand_like_count = _int(structure.get("ligand_like_residue_count"))
    allowed_scope_families = [str(item) for item in scope.get("allowed_scope_families") or [] if str(item)]
    if not allowed_scope_families:
        allowed_scope_families = [family] if family != "unknown" else []
    blocked_claim_scopes = [str(item) for item in scope.get("blocked_claim_scopes") or [] if str(item)]
    claim_blocked_domains = [str(item) for item in scope.get("claim_blocked_domains") or [] if str(item)]
    general_platform_claim_allowed = scope.get("general_platform_claim_allowed") is True
    scope_guard_ready = scope.get("closure_checklist_ready") is True
    scope_claim_limit_ready = bool(
        scope_guard_ready
        and allowed_scope_families
        and blocked_claim_scopes
        and general_platform_claim_allowed is False
    )

    sections = [
        _section(
            "binding_site_explanation",
            "ready" if graph_ready and structure_ready and atom_count > 0 else "blocked",
            structure_report_path,
            "Structure and Binding-Site Context",
            (
                f"{target} ({family}) was parsed locally with {atom_count} atoms, "
                f"{chain_count_text} chains, {residue_count_text} residues, "
                f"and {ligand_like_count} ligand-like residues. This grounds the "
                "binding-site discussion in the submitted structure rather than in a detached score."
            ),
            "The report can explain what structural context was available before interpreting any ligand pose.",
            "Repair or replace the local structure report before presenting binding-site explanations." if not structure_ready else "Use the parsed structure context as the binding-site explanation source.",
            customer_question="What structural context did the analysis actually inspect before discussing binding?",
            claim_limit="Binding-site language is limited to parsed local structure context; it is not a new binding-site prediction.",
            abstention_reason=abstention_reason,
            what_would_change_decision="A repaired structure report with parsed chains, residues, and ligand-like context would unlock stronger binding-site wording.",
            confidence_posture="structure_context_ready" if structure_ready else "structure_context_blocked",
            evidence_traceability=f"{structure_report_path}:local_structure_parse",
        ),
        _section(
            "pose_comparison",
            "ready" if graph_ready and pose_ready and _int(bundle.get("artifact_count")) > 0 else "blocked",
            f"{execution_preflight_path};{bundle_path}",
            "Pose and Scoring Evidence",
            (
                f"The docking/scoring lane is represented by {_int(preflight.get('config_count'))} approved config "
                f"record(s), operational gate `{_text(preflight.get('operational_gate_feasibility_status')) or 'unknown'}`, "
                f"and {_int(bundle.get('artifact_count'))} bundle artifact(s). The report should compare existing pose/scoring "
                "evidence and must not imply a fresh execution occurred."
            ),
            "The report can show accepted pose/scoring evidence while preserving the fail-closed execution boundary.",
            "Refresh execution preflight and bundle evidence before showing pose comparisons." if not pose_ready else "Compare only the audited bundled pose/scoring artifacts.",
            customer_question="Which pose/scoring evidence is being compared, and did this request run new docking?",
            claim_limit="Pose comparison is limited to audited bundled artifacts; the packet does not claim fresh docking execution.",
            abstention_reason="docking_execution_fail_closed_until_explicit_worker_gate",
            what_would_change_decision="A worker-approved run with persisted pose artifacts and scoring provenance would change this section from evidence review to execution result review.",
            confidence_posture="pose_evidence_review_only" if pose_ready else "pose_evidence_blocked",
            evidence_traceability=f"{execution_preflight_path}:execution_command_check;{bundle_path}:bundle_validation_evidence",
        ),
        _section(
            "interaction_rationale",
            "ready" if graph_ready and structure_ready and pose_ready and ligand_context_ready and _int(bundle.get("artifact_count")) > 0 else "blocked",
            f"{structure_report_path};{execution_preflight_path};{bundle_path}",
            "Interaction Rationale",
            (
                f"The customer-facing rationale should explain pose quality through interaction evidence, not only a scalar score. "
                f"For {target}, the local structure reports {_int(structure.get('ligand_like_residue_count'))} ligand-like residue(s), "
                f"pocket center `{structure.get('pocket_center') or 'not_reported'}`, ranking score column `{ranking_score_col}`, "
                f"mean-min-distance gate `{distance_gate}`, and top-k hit-rate gate `{topk_hit_gate}`. These values let the report "
                "separate contact plausibility, scoring/ranking evidence, and abstention limits."
            ),
            "The report can answer why a pose is plausible by naming interaction context, score provenance, and guardrail thresholds.",
            (
                "Restore structure ligand-context, execution command provenance, and bundle evidence before presenting interaction rationale."
                if not (structure_ready and pose_ready and ligand_context_ready)
                else "Use ligand-context, score-column, and gate-threshold provenance as the interaction rationale source."
            ),
            customer_question="Why is this pose plausible or weak beyond the aggregate score?",
            claim_limit="Interaction rationale is explanatory evidence from audited artifacts; it is not a newly computed interaction fingerprint.",
            abstention_reason="interaction_fingerprint_not_recomputed_in_report_packet",
            what_would_change_decision="Persisted per-pose contact fingerprints, residue interaction counts, and trajectory-derived contact stability would allow stronger pose-quality language.",
            confidence_posture="interaction_context_ready" if ligand_context_ready and pose_ready else "interaction_context_blocked",
            evidence_traceability=(
                f"{structure_report_path}:ligand_like_residue_scan;"
                f"{execution_preflight_path}:ranking_score_col={ranking_score_col};"
                f"{bundle_path}:artifact_count={_int(bundle.get('artifact_count'))}"
            ),
        ),
        _section(
            "ligand_selection_rationale",
            (
                "ready"
                if graph_ready
                and structure_ready
                and pose_ready
                and ligand_context_ready
                and ranking_score_ready
                and _int(bundle.get("artifact_count")) > 0
                else "blocked"
            ),
            f"{structure_report_path};{execution_preflight_path};{bundle_path};{scope_claim_guard_path}",
            "Ligand Selection Rationale",
            (
                f"The report can explain why the current {target} ligand/pose evidence is eligible for customer "
                f"review: family `{family}` is inside the restricted delivery lane, the local structure exposes "
                f"{ligand_like_count} ligand-like residue(s), the ranking source is `{ranking_score_col}`, and the "
                f"review remains bounded by distance gate `{distance_gate}` plus top-k hit-rate gate `{topk_hit_gate}`. "
                "This is a selection rationale for an audited evidence packet, not a claim that the ligand is a "
                "therapeutic winner or that ranking was silently mutated by AI."
            ),
            "The report can tell the customer why this ligand/pose evidence was surfaced while keeping winner claims gated.",
            (
                "Restore ligand context, ranking-score provenance, bundle evidence, and scope-claim guard before explaining selection."
                if not (structure_ready and pose_ready and ligand_context_ready and ranking_score_ready)
                else "Use ranking-score provenance, ligand context, and restricted-scope guardrails as the selection rationale source."
            ),
            customer_question="Why was this ligand or pose surfaced for review instead of another candidate?",
            claim_limit=(
                "Ligand selection rationale explains audited surfacing criteria only; it does not claim clinical efficacy, "
                "therapeutic superiority, broad-platform generality, or ungated customer ranking mutation."
            ),
            abstention_reason="ligand_winner_claim_requires_pose_score_result_manifest_and_ranking_gate",
            what_would_change_decision=(
                "A signed result manifest with per-ligand score provenance, pose/contact evidence, and an open "
                "customer ranking-mutation gate would allow stronger ligand-winner language."
            ),
            confidence_posture=(
                "ligand_selection_rationale_ready"
                if ligand_context_ready and ranking_score_ready and scope_claim_limit_ready
                else "ligand_selection_rationale_blocked"
            ),
            evidence_traceability=(
                f"{structure_report_path}:ligand_like_residue_count={ligand_like_count};"
                f"{execution_preflight_path}:ranking_score_col={ranking_score_col};"
                f"{bundle_path}:artifact_count={_int(bundle.get('artifact_count'))};"
                f"{scope_claim_guard_path}:allowed_scope_families={','.join(allowed_scope_families) or 'not_reported'}"
            ),
        ),
        _section(
            "uncertainty_narrative",
            "ready" if graph_ready and uncertainty_ready else "blocked",
            registry_path,
            "Uncertainty and Abstention",
            (
                f"The residual model layer is registered with default mode `{_text(registry.get('default_residual_mode')) or 'unknown'}` "
                f"and production promotion `{registry.get('production_promotion_allowed')}`. The customer narrative must state "
                "whether learned residual corrections are abstained, or active under a guarded policy that still keeps "
                "this explanation packet from silently changing customer scores."
            ),
            "The report can explain why the system may abstain instead of automatically correcting customer results.",
            "Keep residual correction language tied to the guarded execution/result-manifest gate." if uncertainty_ready else "Repair residual registry evidence before presenting uncertainty/abstention narrative.",
            customer_question="Why did the AI layer abstain or avoid silently correcting the result?",
            claim_limit=f"Residual AI is in `{default_residual_mode}` mode; production correction is not claimed while promotion is {production_promotion_allowed}.",
            abstention_reason=abstention_reason,
            what_would_change_decision=checkpoint_change_condition,
            confidence_posture=(
                "abstain_force_receipt_ready" if force_receipt_ready else f"abstain_missing_sidecar_outputs={missing_sidecar_outputs or 'not_reported'}"
            ),
            evidence_traceability=f"{registry_path}:residual_model_registry_summary",
        ),
        _section(
            "counterfactual_rescue_suggestion",
            "ready" if graph_ready and uncertainty_ready and bundle_ready else "blocked",
            f"{decision_graph_path};{bundle_path}",
            "Counterfactual and Rescue Suggestions",
            (
                f"The report can point to `{_text(bundle.get('expected_bundle_dir')) or 'missing_bundle_dir'}` and the closed-loop "
                "decision graph for rerun/rescue actions. Suggestions should be phrased as next evidence actions, such as "
                "rerunning guarded docking, restoring trajectory evidence, or keeping broad claims blocked when uncertainty is high."
            ),
            "The report can tell the customer what evidence would change the decision, not only display a score.",
            "Repair the bundle validation handoff before emitting rescue suggestions." if not bundle_ready else "Use the graph and bundle handoff to generate conservative next-action suggestions.",
            customer_question="What evidence would change the recommendation or unblock a rerun?",
            claim_limit="Rescue suggestions are next evidence actions, not therapeutic, clinical, or broad platform claims.",
            abstention_reason=abstention_reason,
            what_would_change_decision="A validated rerun bundle, restored trajectory evidence, and green production AI promotion gates would allow stronger recommendation language.",
            confidence_posture="counterfactual_next_actions_ready" if bundle_ready else "counterfactual_next_actions_blocked",
            evidence_traceability=f"{decision_graph_path}:closed_loop_decision_graph;{bundle_path}:bundle_validation_command",
        ),
    ]
    sections.insert(
        5,
        _section(
            "scope_claim_limit",
            "ready" if graph_ready and scope_claim_limit_ready else "blocked",
            scope_claim_guard_path,
            "Scope and Claim Limits",
            (
                f"The customer-facing report is limited to the current delivery families "
                f"`{','.join(allowed_scope_families) or 'not_reported'}`. It must keep "
                f"`{','.join(blocked_claim_scopes) or 'no_blocked_scope_reported'}` blocked, and broad/general "
                f"protein-ligand platform wording remains `{general_platform_claim_allowed}` until transporter/PXR and "
                "general claim gates are closed."
            ),
            "The report can state the allowed restricted scope and explicitly block broader transporter/PXR/general platform claims.",
            (
                "Rebuild the scope-claim guard before presenting customer claim limits."
                if not scope_claim_limit_ready
                else "Use the scope claim guard as the customer claim-limit source."
            ),
            customer_question="What can this report safely claim, and which product claims remain blocked?",
            claim_limit=(
                f"Allowed families: {','.join(allowed_scope_families) or 'not_reported'}; "
                f"blocked claim scopes: {','.join(blocked_claim_scopes) or 'none'}; "
                f"blocked domains: {','.join(claim_blocked_domains) or 'none'}; "
                f"general platform claim allowed: {general_platform_claim_allowed}."
            ),
            abstention_reason="scope_claim_guard_blocks_broad_platform_wording",
            what_would_change_decision=_text(scope.get("next_required_step"))
            or "Close transporter/PXR scientific rows and explicit general platform claim gates.",
            confidence_posture="restricted_scope_claim_guard_ready" if scope_claim_limit_ready else "scope_claim_guard_blocked",
            evidence_traceability=f"{scope_claim_guard_path}:claim_boundary_matrix",
        ),
    )
    ready_sections = [row for row in sections if row["status"] == "ready"]
    blocked_sections = [row for row in sections if row["status"] != "ready"]
    required_ready = all(row["status"] == "ready" for row in sections if row["section_id"] in REQUIRED_SECTIONS)
    narrative_ready = required_ready and all(_text(row["narrative"]) and _text(row["customer_takeaway"]) for row in sections)
    structured_report_ready = narrative_ready and all(
        all(_text(row.get(field)) for field in REQUIRED_STRUCTURED_FIELDS) and bool(row.get("evidence_refs"))
        for row in sections
    )
    required_block_ids = list(REQUIRED_CUSTOMER_REPORT_BLOCKS)
    section_by_id = {row["section_id"]: row for row in sections}
    missing_delivery_blocks = [block_id for block_id in required_block_ids if block_id not in section_by_id]
    ready_delivery_blocks: list[str] = []
    blocked_delivery_blocks: list[str] = []
    for row in sections:
        required_block = row["section_id"] in REQUIRED_CUSTOMER_REPORT_BLOCKS
        evidence_binding_ready = bool(row.get("evidence_refs")) and bool(_text(row.get("evidence_traceability")))
        delivery_block_ready = bool(
            required_block
            and row["status"] == "ready"
            and evidence_binding_ready
            and _text(row.get("narrative"))
            and _text(row.get("customer_takeaway"))
            and all(_text(row.get(field)) for field in REQUIRED_STRUCTURED_FIELDS)
        )
        row["customer_report_required_block"] = required_block
        row["customer_report_delivery_block_ready"] = delivery_block_ready
        row["customer_report_evidence_binding_ready"] = evidence_binding_ready
        row["customer_report_delivery_blocker"] = "" if delivery_block_ready else "customer_report_block_not_delivery_ready"
        if not required_block:
            continue
        if delivery_block_ready:
            ready_delivery_blocks.append(row["section_id"])
        else:
            blocked_delivery_blocks.append(row["section_id"])
    customer_report_evidence_binding_ready = all(
        bool(section_by_id.get(block_id, {}).get("customer_report_evidence_binding_ready"))
        for block_id in required_block_ids
    )
    customer_report_delivery_contract_ready = bool(
        structured_report_ready
        and not missing_delivery_blocks
        and len(ready_delivery_blocks) == len(required_block_ids)
        and customer_report_evidence_binding_ready
    )
    customer_report_blocks = {
        row["section_id"]: {
            "title": row["title"],
            "status": row["status"],
            "narrative": row["narrative"],
            "customer_takeaway": row["customer_takeaway"],
            "claim_limit": row["claim_limit"],
            "abstention_reason": row["abstention_reason"],
            "what_would_change_decision": row["what_would_change_decision"],
            "confidence_posture": row["confidence_posture"],
            "evidence_traceability": row["evidence_traceability"],
            "delivery_block_ready": row["customer_report_delivery_block_ready"],
        }
        for row in sections
    }
    selection_section = section_by_id.get("ligand_selection_rationale", {})
    selection_rationale_ready = bool(selection_section.get("status") == "ready")
    selection_rationale = _text(selection_section.get("narrative"))
    customer_report_card = {
        "target_id": target,
        "family": family,
        "production_ai_correction_applied": False,
        "production_ai_abstention_enforced": not production_promotion_allowed,
        "default_residual_mode": default_residual_mode,
        "uncertainty_policy_mode": (
            "production_guarded_active"
            if guarded_active_ready
            else "shadow_abstention"
            if shadow_abstention_ready
            else "blocked"
        ),
        "shadow_abstention_ready": shadow_abstention_ready,
        "production_guarded_active_ready": guarded_active_ready,
        "primary_abstention_reason": abstention_reason,
        "claim_limit": "Customer report is an evidence review over local artifacts; it does not run docking, apply learned correction, or widen delivery scope.",
        "what_would_change_decision": checkpoint_change_condition,
        "allowed_scope_families": allowed_scope_families,
        "blocked_claim_scopes": blocked_claim_scopes,
        "claim_blocked_domains": claim_blocked_domains,
        "general_platform_claim_allowed": general_platform_claim_allowed,
        "scope_claim_guard_ready": scope_guard_ready,
        "scope_claim_limit_ready": scope_claim_limit_ready,
        "interaction_rationale_ready": any(
            row["section_id"] == "interaction_rationale" and row["status"] == "ready" for row in sections
        ),
        "ligand_selection_rationale_ready": selection_rationale_ready,
        "selection_rationale_ready": selection_rationale_ready,
        "selection_rationale": selection_rationale,
        "ligand_selection_policy": "audited_score_provenance_and_restricted_scope_required_before_customer_winner_claim",
        "evidence_traceability_ready": all(_text(row.get("evidence_traceability")) for row in sections),
        "blocks": customer_report_blocks,
        "customer_report_delivery_contract_ready": customer_report_delivery_contract_ready,
        "customer_report_required_block_count": len(required_block_ids),
        "customer_report_ready_block_count": len(ready_delivery_blocks),
        "customer_report_blocked_block_count": len(blocked_delivery_blocks) + len(missing_delivery_blocks),
        "customer_report_required_blocks": required_block_ids,
        "customer_report_ready_blocks": ready_delivery_blocks,
        "customer_report_blocked_blocks": blocked_delivery_blocks,
        "customer_report_missing_blocks": missing_delivery_blocks,
        "customer_report_evidence_binding_ready": customer_report_evidence_binding_ready,
        "ready_section_count": len(ready_sections),
        "blocked_section_count": len(blocked_sections),
    }
    summary = {
        "packet_type": "product_ai_report_explanation_packet",
        "status": "product_ai_report_explanation_packet_ready" if structured_report_ready else "blocked_product_ai_report_explanation_packet",
        "ai_report_explanation_packet_ready": structured_report_ready,
        "structured_customer_report_ready": structured_report_ready,
        "required_structured_field_count": len(REQUIRED_STRUCTURED_FIELDS),
        "customer_report_card": customer_report_card,
        "customer_report_delivery_contract_ready": customer_report_delivery_contract_ready,
        "customer_report_required_block_count": len(required_block_ids),
        "customer_report_ready_block_count": len(ready_delivery_blocks),
        "customer_report_blocked_block_count": len(blocked_delivery_blocks) + len(missing_delivery_blocks),
        "customer_report_required_blocks": required_block_ids,
        "customer_report_ready_blocks": ready_delivery_blocks,
        "customer_report_blocked_blocks": blocked_delivery_blocks,
        "customer_report_missing_blocks": missing_delivery_blocks,
        "customer_report_evidence_binding_ready": customer_report_evidence_binding_ready,
        "interaction_rationale_ready": customer_report_card["interaction_rationale_ready"],
        "ligand_selection_rationale_ready": selection_rationale_ready,
        "selection_rationale": selection_rationale,
        "ranking_score_ready": ranking_score_ready,
        "evidence_traceability_ready": customer_report_card["evidence_traceability_ready"],
        "ranking_score_col": ranking_score_col,
        "interaction_distance_gate_A": distance_gate,
        "interaction_topk_hit_rate_gate": topk_hit_gate,
        "production_ai_correction_applied": False,
        "production_ai_abstention_enforced": not production_promotion_allowed,
        "uncertainty_policy_mode": (
            "production_guarded_active"
            if guarded_active_ready
            else "shadow_abstention"
            if shadow_abstention_ready
            else "blocked"
        ),
        "shadow_abstention_ready": shadow_abstention_ready,
        "production_guarded_active_ready": guarded_active_ready,
        "primary_abstention_reason": abstention_reason,
        "allowed_scope_families": allowed_scope_families,
        "blocked_claim_scopes": blocked_claim_scopes,
        "claim_blocked_domains": claim_blocked_domains,
        "general_platform_claim_allowed": general_platform_claim_allowed,
        "scope_claim_guard_ready": scope_guard_ready,
        "scope_claim_limit_ready": scope_claim_limit_ready,
        "required_section_count": len(REQUIRED_SECTIONS),
        "section_count": len(sections),
        "ready_section_count": len(ready_sections),
        "blocked_section_count": len(blocked_sections),
        "ready_sections": [row["section_id"] for row in ready_sections],
        "blocked_sections": [row["section_id"] for row in blocked_sections],
        "target_id": target,
        "family": family,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "model_inference_executed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Attach this explanation packet to the report UX contract and keep production AI correction separately gated."
            if customer_report_delivery_contract_ready
            else "Repair blocked explanation sections before claiming customer-facing AI analysis report readiness."
        ),
    }
    return {"summary": summary, "rows": sections}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Product AI Report Explanation Packet",
        "",
        f"- status: `{s['status']}`",
        f"- ai_report_explanation_packet_ready: `{s['ai_report_explanation_packet_ready']}`",
        f"- structured_customer_report_ready: `{s['structured_customer_report_ready']}`",
        f"- customer_report_delivery_contract_ready: `{s['customer_report_delivery_contract_ready']}`",
        f"- customer_report_ready_block_count: `{s['customer_report_ready_block_count']}` / `{s['customer_report_required_block_count']}`",
        f"- primary_abstention_reason: `{s['primary_abstention_reason']}`",
        f"- ready_section_count: `{s['ready_section_count']}` / `{s['section_count']}`",
        f"- target_id: `{s['target_id']}`",
        f"- family: `{s['family']}`",
        "",
        "## Sections",
        "",
    ]
    for row in payload["rows"]:
        lines.extend(
            [
                f"### {row['title']}",
                "",
                f"- section_id: `{row['section_id']}`",
                f"- status: `{row['status']}`",
                f"- evidence: `{row['evidence']}`",
                f"- customer_question: {row['customer_question']}",
                f"- claim_limit: {row['claim_limit']}",
                f"- abstention_reason: `{row['abstention_reason']}`",
                f"- what_would_change_decision: {row['what_would_change_decision']}",
                f"- confidence_posture: `{row['confidence_posture']}`",
                f"- evidence_traceability: `{row['evidence_traceability']}`",
                "",
                row["narrative"],
                "",
                f"Customer takeaway: {row['customer_takeaway']}",
                "",
                f"Next action: {row['next_action']}",
                "",
            ]
        )
    lines.extend(["## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build product AI report explanation packet.")
    parser.add_argument("--decision-graph-json", default=DEFAULT_DECISION_GRAPH_JSON)
    parser.add_argument("--structure-report-json", default=DEFAULT_STRUCTURE_REPORT_JSON)
    parser.add_argument("--execution-preflight-json", default=DEFAULT_EXECUTION_PREFLIGHT_JSON)
    parser.add_argument("--bundle-json", default=DEFAULT_BUNDLE_JSON)
    parser.add_argument("--registry-json", default=DEFAULT_REGISTRY_JSON)
    parser.add_argument("--scope-claim-guard-json", default=DEFAULT_SCOPE_CLAIM_GUARD_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_product_ai_report_explanation_packet(
        decision_graph_packet=_read_json(args.decision_graph_json),
        structure_report_packet=_read_json(args.structure_report_json),
        execution_preflight_packet=_read_json(args.execution_preflight_json),
        bundle_packet=_read_json(args.bundle_json),
        registry_packet=_read_json(args.registry_json),
        scope_claim_guard_packet=_read_json(args.scope_claim_guard_json),
        decision_graph_path=args.decision_graph_json,
        structure_report_path=args.structure_report_json,
        execution_preflight_path=args.execution_preflight_json,
        bundle_path=args.bundle_json,
        registry_path=args.registry_json,
        scope_claim_guard_path=args.scope_claim_guard_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
