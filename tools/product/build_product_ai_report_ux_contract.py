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
DEFAULT_EXPLANATION_PACKET_JSON = "runs/product_ai_report_explanation_packet_current.json"
DEFAULT_VIEWER_INDEX = "viewer/index.html"
DEFAULT_VIEWER_APP = "viewer/app.js"
DEFAULT_OUT_JSON = "runs/product_ai_report_ux_contract_current.json"
DEFAULT_OUT_CSV = "runs/product_ai_report_ux_contract_current.csv"
DEFAULT_OUT_MD = "runs/product_ai_report_ux_contract_current.md"

REQUIRED_CUSTOMER_REPORT_BLOCKS = (
    "binding_site_explanation",
    "pose_comparison",
    "interaction_rationale",
    "ligand_selection_rationale",
    "uncertainty_narrative",
    "scope_claim_limit",
    "counterfactual_rescue_suggestion",
)

CLAIM_BOUNDARY = (
    "Product AI report UX contract only; audits local evidence for a customer-facing explanation packet over "
    "structure context, pose/scoring evidence, uncertainty/abstention, and counterfactual next actions. It does not "
    "render a browser, run docking, run model inference, train models, upload, email, delete, or mutate external state."
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
    return bool(value is True)


def _join_list(value: Any) -> str:
    return ",".join(str(item) for item in value or [])


def _file_contains(path_like: str | Path, required_tokens: tuple[str, ...]) -> bool:
    path = _resolve(path_like)
    if not path.is_file():
        return False
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    return all(token in text for token in required_tokens)


def _registry_abstention_detail(registry: dict[str, Any]) -> str:
    return (
        f"selected_sidecar_status={_text(registry.get('selected_sidecar_status'))};"
        f"selected_sidecar_ready={registry.get('selected_sidecar_ready')};"
        f"selected_sidecar_missing_output_fields={_join_list(registry.get('selected_sidecar_missing_output_fields'))};"
        f"selected_sidecar_training_contract_missing_label_fields={_join_list(registry.get('selected_sidecar_training_contract_missing_label_fields'))};"
        f"selected_sidecar_force_receipt_ready={registry.get('selected_sidecar_force_receipt_ready')};"
        f"selected_sidecar_force_receipt_operator_verified={registry.get('selected_sidecar_force_receipt_operator_verified')};"
        f"selected_sidecar_force_receipt_operator_verified_true_count={registry.get('selected_sidecar_force_receipt_operator_verified_true_count')};"
        f"selected_sidecar_force_receipt_expected_queue_rows={registry.get('selected_sidecar_force_receipt_expected_queue_rows')}"
    )


def _row(section_id: str, status: str, evidence: str, observed: str, required: str, narrative: str) -> dict[str, Any]:
    return {
        "section_id": section_id,
        "status": status,
        "evidence": evidence,
        "observed": observed,
        "required": required,
        "narrative": narrative,
        "release_blocker": status != "ready",
        "execution_enabled": False,
        "docking_results_emitted": False,
        "model_inference_executed": False,
        "external_state_mutated": False,
    }


def build_product_ai_report_ux_contract(
    *,
    decision_graph_packet: dict[str, Any],
    structure_report_packet: dict[str, Any],
    execution_preflight_packet: dict[str, Any],
    bundle_packet: dict[str, Any],
    registry_packet: dict[str, Any],
    explanation_packet: dict[str, Any] | None = None,
    viewer_index: str = DEFAULT_VIEWER_INDEX,
    viewer_app: str = DEFAULT_VIEWER_APP,
    decision_graph_path: str = DEFAULT_DECISION_GRAPH_JSON,
    structure_report_path: str = DEFAULT_STRUCTURE_REPORT_JSON,
    execution_preflight_path: str = DEFAULT_EXECUTION_PREFLIGHT_JSON,
    bundle_path: str = DEFAULT_BUNDLE_JSON,
    registry_path: str = DEFAULT_REGISTRY_JSON,
    explanation_packet_path: str = DEFAULT_EXPLANATION_PACKET_JSON,
) -> dict[str, Any]:
    graph = _summary(decision_graph_packet)
    structure = _summary(structure_report_packet)
    preflight = _summary(execution_preflight_packet)
    bundle = _summary(bundle_packet)
    registry = _summary(registry_packet)
    explanation_payload = explanation_packet or {}
    explanation = _summary(explanation_payload)
    explanation_rows = explanation_payload.get("rows") if isinstance(explanation_payload.get("rows"), list) else []
    explanation_section_ids = {
        _text(row.get("section_id"))
        for row in explanation_rows
        if isinstance(row, dict) and _text(row.get("section_id"))
    }
    report_card = explanation.get("customer_report_card") if isinstance(explanation.get("customer_report_card"), dict) else {}
    registry_abstention_detail = _registry_abstention_detail(registry)
    viewer_ready = _resolve(viewer_index).is_file() and _resolve(viewer_app).is_file()
    viewer_interaction_surface_ready = viewer_ready and _file_contains(
        viewer_app,
        ("interactionOverlay", "contactMap", "summarizeInteractionTypes", "renderInteractionOverlay"),
    )
    viewer_customer_report_binding_ready = viewer_ready and _file_contains(
        viewer_app,
        (
            "CUSTOMER_REPORT_REQUIRED_BLOCKS",
            "normalizeCustomerReportBlock",
            "renderCustomerReportCard",
            "customerReportCard",
            *REQUIRED_CUSTOMER_REPORT_BLOCKS,
        ),
    )
    graph_ready = _bool(graph.get("closed_loop_decision_graph_ready"))
    customer_report_required_blocks = [
        str(item) for item in explanation.get("customer_report_required_blocks") or [] if str(item)
    ]
    customer_report_ready_blocks = [
        str(item) for item in explanation.get("customer_report_ready_blocks") or [] if str(item)
    ]
    customer_report_missing_blocks = [
        str(item) for item in explanation.get("customer_report_missing_blocks") or [] if str(item)
    ]
    customer_report_delivery_contract_ready = bool(
        _bool(explanation.get("customer_report_delivery_contract_ready"))
        and _bool(explanation.get("customer_report_evidence_binding_ready"))
        and _int(explanation.get("customer_report_required_block_count")) > 0
        and _int(explanation.get("customer_report_ready_block_count"))
        == _int(explanation.get("customer_report_required_block_count"))
        and _int(explanation.get("customer_report_blocked_block_count")) == 0
        and not customer_report_missing_blocks
        and bool(customer_report_required_blocks)
        and set(customer_report_ready_blocks) == set(customer_report_required_blocks)
        and set(customer_report_required_blocks) == set(REQUIRED_CUSTOMER_REPORT_BLOCKS)
    )
    customer_report_viewer_binding_ready = bool(
        customer_report_delivery_contract_ready
        and viewer_customer_report_binding_ready
        and "customer_report_delivery_contract" not in customer_report_missing_blocks
    )
    explanation_ready = bool(
        _bool(explanation.get("ai_report_explanation_packet_ready"))
        and _bool(explanation.get("structured_customer_report_ready"))
        and customer_report_delivery_contract_ready
        and _bool(explanation.get("interaction_rationale_ready"))
        and _bool(explanation.get("ligand_selection_rationale_ready"))
        and _bool(explanation.get("evidence_traceability_ready"))
        and customer_report_viewer_binding_ready
        and "interaction_rationale" in explanation_section_ids
        and "ligand_selection_rationale" in explanation_section_ids
        and "scope_claim_limit" in explanation_section_ids
        and isinstance(report_card, dict)
        and _text(report_card.get("primary_abstention_reason"))
        and _text(report_card.get("what_would_change_decision"))
        and _text(report_card.get("selection_rationale"))
        and _bool(report_card.get("scope_claim_limit_ready"))
        and _bool(report_card.get("ligand_selection_rationale_ready"))
        and report_card.get("general_platform_claim_allowed") is False
        and bool(report_card.get("blocked_claim_scopes"))
    )
    binding_site_ready = (
        graph_ready
        and explanation_ready
        and _text(structure.get("status")) == "product_structure_analysis_report_ready"
        and (
            _int(structure.get("atom_count")) > 0
            or (_int(structure.get("chain_count")) > 0 and _int(structure.get("residue_count")) > 0)
        )
    )
    pose_comparison_ready = (
        graph_ready
        and explanation_ready
        and viewer_interaction_surface_ready
        and _text(preflight.get("status")) == "product_execution_preflight_ready"
        and _text(preflight.get("operational_gate_feasibility_status")) == "pass"
        and _text(bundle.get("status")) == "product_bundle_contract_ready"
        and _int(bundle.get("artifact_count")) > 0
    )
    interaction_rationale_ready = bool(
        graph_ready
        and explanation_ready
        and viewer_interaction_surface_ready
        and _bool(explanation.get("interaction_rationale_ready"))
        and _bool(explanation.get("evidence_traceability_ready"))
        and _text(explanation.get("ranking_score_col"))
        and _text(explanation.get("interaction_distance_gate_A"))
    )
    ligand_selection_rationale_ready = bool(
        graph_ready
        and explanation_ready
        and customer_report_viewer_binding_ready
        and _bool(explanation.get("ligand_selection_rationale_ready"))
        and _bool(report_card.get("ligand_selection_rationale_ready"))
        and "ligand_selection_rationale" in explanation_section_ids
        and _text(report_card.get("selection_rationale"))
        and _text(explanation.get("ranking_score_col"))
        and explanation.get("ranking_score_col") != "not_reported"
    )
    default_residual_mode = _text(registry.get("default_residual_mode"))
    missing_sidecar_outputs = [str(item) for item in registry.get("selected_sidecar_missing_output_fields") or []]
    shadow_abstention_ready = (
        default_residual_mode in {"shadow", "shadow_only"}
        and registry.get("production_promotion_allowed") is False
    )
    guarded_active_ready = (
        default_residual_mode == "production_guarded"
        and registry.get("production_promotion_allowed") is True
        and registry.get("customer_facing_auto_correction_allowed") is True
        and registry.get("customer_facing_score_mutation_allowed") is True
        and registry.get("selected_sidecar_ready") is True
        and not missing_sidecar_outputs
    )
    uncertainty_ready = (
        graph_ready
        and explanation_ready
        and _text(registry.get("status")) == "residual_model_registry_ready"
        and (shadow_abstention_ready or guarded_active_ready)
    )
    counterfactual_ready = (
        graph_ready
        and explanation_ready
        and uncertainty_ready
        and _text(bundle.get("expected_bundle_dir"))
        and _bool(bundle.get("bundle_validation_command_matches"))
    )
    report_ready = (
        binding_site_ready
        and pose_comparison_ready
        and interaction_rationale_ready
        and ligand_selection_rationale_ready
        and uncertainty_ready
        and counterfactual_ready
        and viewer_ready
        and viewer_interaction_surface_ready
        and customer_report_viewer_binding_ready
    )

    rows = [
        _row(
            "explanation_packet",
            "ready" if explanation_ready else "blocked",
            explanation_packet_path,
            (
                f"explanation={explanation.get('status')};"
                f"structured_customer_report_ready={explanation.get('structured_customer_report_ready')};"
                f"primary_abstention_reason={(explanation.get('customer_report_card') or {}).get('primary_abstention_reason')};"
                f"interaction_rationale_ready={explanation.get('interaction_rationale_ready')};"
                f"ligand_selection_rationale_ready={explanation.get('ligand_selection_rationale_ready')};"
                f"evidence_traceability_ready={explanation.get('evidence_traceability_ready')};"
                f"ready_sections={explanation.get('ready_section_count')};"
                f"blocked_sections={explanation.get('blocked_section_count')};"
                f"scope_claim_limit_ready={report_card.get('scope_claim_limit_ready')};"
                f"blocked_claim_scopes={_join_list(report_card.get('blocked_claim_scopes'))};"
                f"general_platform_claim_allowed={report_card.get('general_platform_claim_allowed')}"
            ),
            "structured customer-facing explanation packet has required narrative sections, interaction rationale, evidence traceability, claim limits, abstention reason, and decision-change conditions",
            "Report UX must be backed by structured explanation text, not only evidence contracts.",
        ),
        _row(
            "customer_report_delivery_contract",
            "ready" if customer_report_delivery_contract_ready else "blocked",
            explanation_packet_path,
            (
                f"customer_report_delivery_contract_ready={explanation.get('customer_report_delivery_contract_ready')};"
                f"customer_report_evidence_binding_ready={explanation.get('customer_report_evidence_binding_ready')};"
                f"required_blocks={_join_list(customer_report_required_blocks)};"
                f"ready_blocks={_join_list(customer_report_ready_blocks)};"
                f"missing_blocks={_join_list(customer_report_missing_blocks)};"
                f"ready_block_count={explanation.get('customer_report_ready_block_count')};"
                f"required_block_count={explanation.get('customer_report_required_block_count')};"
                f"blocked_block_count={explanation.get('customer_report_blocked_block_count')}"
            ),
            "all customer-deliverable report blocks are present, ready, and bound to evidence traceability",
            "Customer report can be handed off as a complete explanation deliverable, not only an internal readiness score.",
        ),
        _row(
            "customer_report_viewer_binding",
            "ready" if customer_report_viewer_binding_ready else "blocked",
            f"{explanation_packet_path};{viewer_app}",
            (
                f"viewer_customer_report_binding_ready={viewer_customer_report_binding_ready};"
                f"required_blocks={_join_list(customer_report_required_blocks)};"
                f"canonical_required_blocks={_join_list(REQUIRED_CUSTOMER_REPORT_BLOCKS)};"
                f"viewer_app={_resolve(viewer_app).is_file()}"
            ),
            "viewer can normalize and render every canonical customer report block from the explanation packet",
            "Customer report card must be bound to the local viewer surface, not only emitted as JSON.",
        ),
        _row(
            "binding_site_explanation",
            "ready" if binding_site_ready else "blocked",
            structure_report_path,
            (
                f"atoms={structure.get('atom_count')};chains={structure.get('chain_count')};"
                f"residues={structure.get('residue_count')};ligand_like={structure.get('ligand_like_residue_count')}"
            ),
            "parsed atom-level or chain/residue structure context for binding-site explanation",
            "Report can explain the available local structure context used before docking/scoring.",
        ),
        _row(
            "pose_comparison",
            "ready" if pose_comparison_ready else "blocked",
            f"{execution_preflight_path};{bundle_path}",
            f"preflight={preflight.get('status')};gate={preflight.get('operational_gate_feasibility_status')};bundle={bundle.get('status')};artifacts={bundle.get('artifact_count')}",
            "scoring gate plus report bundle artifact evidence",
            "Report can compare accepted pose/scoring evidence without pretending to run new docking.",
        ),
        _row(
            "interaction_rationale",
            "ready" if interaction_rationale_ready else "blocked",
            f"{explanation_packet_path};{viewer_app}",
            (
                f"interaction_rationale_ready={explanation.get('interaction_rationale_ready')};"
                f"evidence_traceability_ready={explanation.get('evidence_traceability_ready')};"
                f"ranking_score_col={explanation.get('ranking_score_col')};"
                f"distance_gate_A={explanation.get('interaction_distance_gate_A')};"
                f"viewer_interaction_surface_ready={viewer_interaction_surface_ready}"
            ),
            "customer report explains pose plausibility through interaction context, score provenance, gate thresholds, and viewer contact/overlay surface",
            "Report can answer why a pose is plausible or weak beyond the aggregate score.",
        ),
        _row(
            "ligand_selection_rationale",
            "ready" if ligand_selection_rationale_ready else "blocked",
            explanation_packet_path,
            (
                f"ligand_selection_rationale_ready={explanation.get('ligand_selection_rationale_ready')};"
                f"report_card_ligand_selection_rationale_ready={report_card.get('ligand_selection_rationale_ready')};"
                f"ranking_score_col={explanation.get('ranking_score_col')};"
                f"selection_rationale_present={bool(_text(report_card.get('selection_rationale')))};"
                f"section_bound={'ligand_selection_rationale' in explanation_section_ids}"
            ),
            "customer report explains why a ligand or pose was surfaced using score provenance, ligand context, and restricted-scope guardrails",
            "Report can answer why this ligand/pose was selected for review without making winner, clinical, or broad-platform claims.",
        ),
        _row(
            "uncertainty_narrative",
            "ready" if uncertainty_ready else "blocked",
            registry_path,
            (
                f"registry={registry.get('status')};default_mode={registry.get('default_residual_mode')};"
                f"production_promotion={registry.get('production_promotion_allowed')};"
                f"shadow_abstention_ready={shadow_abstention_ready};guarded_active_ready={guarded_active_ready};"
                f"{registry_abstention_detail}"
            ),
            "residual registry has either shadow abstention or production_guarded active policy with sidecar evidence",
            "Report can state when AI residuals abstain or when guarded AI is active without silently changing scores.",
        ),
        _row(
            "counterfactual_rescue_suggestion",
            "ready" if counterfactual_ready else "blocked",
            f"{decision_graph_path};{bundle_path}",
            f"graph={graph.get('status')};expected_bundle_dir={bundle.get('expected_bundle_dir')};validation_command={bundle.get('bundle_validation_command_matches')}",
            "closed-loop graph and validated rerun/report bundle handoff",
            "Report can suggest rerun/rescue next actions from the audited graph rather than opaque scores.",
        ),
        _row(
            "viewer_ready_surface",
            "ready" if viewer_ready and viewer_interaction_surface_ready else "blocked",
            f"{viewer_index};{viewer_app}",
            (
                f"viewer_index={_resolve(viewer_index).is_file()};"
                f"viewer_app={_resolve(viewer_app).is_file()};"
                f"viewer_interaction_surface_ready={viewer_interaction_surface_ready}"
            ),
            "local viewer shell, app assets, contact map, and interaction overlay functions present",
            "Report packet has a local viewer surface for customer-facing interaction review.",
        ),
    ]
    blockers = [row for row in rows if row["status"] != "ready"]
    summary = {
        "packet_type": "product_ai_report_ux_contract",
        "status": "product_ai_report_ux_contract_ready" if report_ready else "blocked_product_ai_report_ux_contract",
        "ai_report_ux_ready": report_ready,
        "section_count": len(rows),
        "ready_section_count": sum(1 for row in rows if row["status"] == "ready"),
        "blocked_section_count": len(blockers),
        "binding_site_explanation_ready": binding_site_ready,
        "pose_comparison_ready": pose_comparison_ready,
        "interaction_rationale_ready": interaction_rationale_ready,
        "ligand_selection_rationale_ready": ligand_selection_rationale_ready,
        "viewer_interaction_surface_ready": viewer_interaction_surface_ready,
        "viewer_customer_report_binding_ready": viewer_customer_report_binding_ready,
        "customer_report_viewer_binding_ready": customer_report_viewer_binding_ready,
        "uncertainty_narrative_ready": uncertainty_ready,
        "counterfactual_rescue_suggestion_ready": counterfactual_ready,
        "viewer_ready": viewer_ready,
        "explanation_packet_ready": explanation_ready,
        "structured_customer_report_ready": _bool(explanation.get("structured_customer_report_ready")),
        "customer_report_delivery_contract_ready": customer_report_delivery_contract_ready,
        "customer_report_evidence_binding_ready": _bool(explanation.get("customer_report_evidence_binding_ready")),
        "customer_report_required_block_count": _int(explanation.get("customer_report_required_block_count")),
        "customer_report_ready_block_count": _int(explanation.get("customer_report_ready_block_count")),
        "customer_report_blocked_block_count": _int(explanation.get("customer_report_blocked_block_count")),
        "customer_report_required_blocks": customer_report_required_blocks,
        "canonical_customer_report_required_blocks": list(REQUIRED_CUSTOMER_REPORT_BLOCKS),
        "customer_report_ready_blocks": customer_report_ready_blocks,
        "customer_report_missing_blocks": customer_report_missing_blocks,
        "customer_report_card_ready": isinstance(explanation.get("customer_report_card"), dict),
        "customer_report_card": report_card,
        "evidence_traceability_ready": _bool(explanation.get("evidence_traceability_ready")),
        "ranking_score_col": explanation.get("ranking_score_col", ""),
        "selection_rationale": report_card.get("selection_rationale", ""),
        "interaction_distance_gate_A": explanation.get("interaction_distance_gate_A", ""),
        "interaction_topk_hit_rate_gate": explanation.get("interaction_topk_hit_rate_gate", ""),
        "primary_abstention_reason": (explanation.get("customer_report_card") or {}).get("primary_abstention_reason", ""),
        "what_would_change_decision": (explanation.get("customer_report_card") or {}).get("what_would_change_decision", ""),
        "uncertainty_policy_mode": (
            "production_guarded_active"
            if guarded_active_ready
            else "shadow_abstention"
            if shadow_abstention_ready
            else "blocked"
        ),
        "shadow_abstention_ready": shadow_abstention_ready,
        "production_guarded_active_ready": guarded_active_ready,
        "allowed_scope_families": list(report_card.get("allowed_scope_families") or []),
        "blocked_claim_scopes": list(report_card.get("blocked_claim_scopes") or []),
        "claim_blocked_domains": list(report_card.get("claim_blocked_domains") or []),
        "general_platform_claim_allowed": report_card.get("general_platform_claim_allowed") is True,
        "scope_claim_guard_ready": report_card.get("scope_claim_guard_ready") is True,
        "scope_claim_limit_ready": report_card.get("scope_claim_limit_ready") is True,
        "explanation_packet_artifact": explanation_packet_path,
        "viewer_index": viewer_index,
        "viewer_app": viewer_app,
        "uncertainty_abstention_detail": registry_abstention_detail,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "model_inference_executed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "AI report UX contract is ready with structured explanation packet; keep production AI correction and broad scope claims separately gated."
            if report_ready
            else "Repair blocked report sections before claiming customer-facing AI analysis report readiness."
        ),
    }
    return {"summary": summary, "rows": rows, "blockers": blockers}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Product AI Report UX Contract",
        "",
        f"- status: `{s['status']}`",
        f"- ai_report_ux_ready: `{s['ai_report_ux_ready']}`",
        f"- ready_section_count: `{s['ready_section_count']}` / `{s['section_count']}`",
        f"- viewer_ready: `{s['viewer_ready']}`",
        f"- viewer_interaction_surface_ready: `{s['viewer_interaction_surface_ready']}`",
        f"- customer_report_viewer_binding_ready: `{s['customer_report_viewer_binding_ready']}`",
        f"- structured_customer_report_ready: `{s['structured_customer_report_ready']}`",
        f"- customer_report_delivery_contract_ready: `{s['customer_report_delivery_contract_ready']}`",
        f"- customer_report_ready_block_count: `{s['customer_report_ready_block_count']}` / `{s['customer_report_required_block_count']}`",
        f"- interaction_rationale_ready: `{s['interaction_rationale_ready']}`",
        f"- ligand_selection_rationale_ready: `{s['ligand_selection_rationale_ready']}`",
        f"- evidence_traceability_ready: `{s['evidence_traceability_ready']}`",
        f"- ranking_score_col: `{s['ranking_score_col']}`",
        f"- primary_abstention_reason: `{s['primary_abstention_reason']}`",
        f"- uncertainty_abstention_detail: `{s['uncertainty_abstention_detail']}`",
        "",
        "## Sections",
        "",
        "| section | status | observed | narrative |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(f"| `{row['section_id']}` | `{row['status']}` | `{row['observed']}` | {row['narrative']} |")
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build product AI report UX contract from local evidence.")
    parser.add_argument("--decision-graph-json", default=DEFAULT_DECISION_GRAPH_JSON)
    parser.add_argument("--structure-report-json", default=DEFAULT_STRUCTURE_REPORT_JSON)
    parser.add_argument("--execution-preflight-json", default=DEFAULT_EXECUTION_PREFLIGHT_JSON)
    parser.add_argument("--bundle-json", default=DEFAULT_BUNDLE_JSON)
    parser.add_argument("--registry-json", default=DEFAULT_REGISTRY_JSON)
    parser.add_argument("--explanation-packet-json", default=DEFAULT_EXPLANATION_PACKET_JSON)
    parser.add_argument("--viewer-index", default=DEFAULT_VIEWER_INDEX)
    parser.add_argument("--viewer-app", default=DEFAULT_VIEWER_APP)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_product_ai_report_ux_contract(
        decision_graph_packet=_read_json(args.decision_graph_json),
        structure_report_packet=_read_json(args.structure_report_json),
        execution_preflight_packet=_read_json(args.execution_preflight_json),
        bundle_packet=_read_json(args.bundle_json),
        registry_packet=_read_json(args.registry_json),
        explanation_packet=_read_json(args.explanation_packet_json),
        viewer_index=args.viewer_index,
        viewer_app=args.viewer_app,
        decision_graph_path=args.decision_graph_json,
        structure_report_path=args.structure_report_json,
        execution_preflight_path=args.execution_preflight_json,
        bundle_path=args.bundle_json,
        registry_path=args.registry_json,
        explanation_packet_path=args.explanation_packet_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
