#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STRUCTURE_REPORT_JSON = "runs/product_structure_analysis_report_current.json"
DEFAULT_EXECUTION_PREFLIGHT_JSON = "runs/product_execution_preflight_current.json"
DEFAULT_CAPABILITY_JSON = "runs/product_capability_surface_contract_current.json"
DEFAULT_BUNDLE_JSON = "runs/product_bundle_contract_current.json"
DEFAULT_REGISTRY_JSON = "runs/residual_model_registry_current.json"
DEFAULT_REPORT_UX_JSON = "runs/product_ai_report_ux_contract_current.json"
DEFAULT_OUT_JSON = "runs/product_ai_decision_graph_contract_current.json"
DEFAULT_OUT_CSV = "runs/product_ai_decision_graph_contract_current.csv"
DEFAULT_OUT_MD = "runs/product_ai_decision_graph_contract_current.md"

CLAIM_BOUNDARY = (
    "Product AI decision graph contract only; audits that existing local structure-analysis, docking/scoring, "
    "uncertainty/physics-guard, report-bundle, and customer report UX evidence can be read as one fail-closed "
    "analysis graph. It does not run prediction, docking, scoring, model inference, training, report rendering, "
    "upload, or external mutation."
)

REQUIRED_EDGES = (
    (
        "structure_quality",
        "binding_site_context",
        "parsed_structure_context",
        "structure quality evidence must feed binding-site interpretation",
    ),
    (
        "binding_site_context",
        "pose_generation_contract",
        "binding_site_constraints",
        "binding-site context must bound pose generation claims",
    ),
    (
        "pose_generation_contract",
        "scoring_ranking_gate",
        "pose_candidate_inputs",
        "pose generation/preflight evidence must feed scoring and ranking",
    ),
    (
        "scoring_ranking_gate",
        "uncertainty_abstention_guard",
        "ranked_score_evidence",
        "ranked scores must pass through uncertainty and abstention before report language",
    ),
    (
        "uncertainty_abstention_guard",
        "report_bundle_contract",
        "fail_closed_report_decision",
        "report handoff must carry abstention/fail-closed state when production AI correction is blocked",
    ),
    (
        "report_bundle_contract",
        "customer_report_ux",
        "viewer_ready_explanation_packet",
        "auditable report bundle must feed the customer-facing viewer/explanation surface",
    ),
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


def _row(node_id: str, status: str, evidence: str, observed: str, required: str, reason: str) -> dict[str, Any]:
    return {
        "node_id": node_id,
        "status": status,
        "evidence": evidence,
        "observed": observed,
        "required": required,
        "reason": reason,
        "release_blocker": status != "ready",
        "execution_enabled": False,
        "docking_results_emitted": False,
        "model_inference_executed": False,
        "external_state_mutated": False,
    }


def _edge_row(
    *,
    edge_id: str,
    source_node_id: str,
    target_node_id: str,
    status: str,
    payload: str,
    observed: str,
    required: str,
) -> dict[str, Any]:
    return {
        "edge_id": edge_id,
        "source_node_id": source_node_id,
        "target_node_id": target_node_id,
        "status": status,
        "payload": payload,
        "observed": observed,
        "required": required,
        "release_blocker": status != "ready",
        "execution_enabled": False,
        "docking_results_emitted": False,
        "model_inference_executed": False,
        "external_state_mutated": False,
    }


def build_product_ai_decision_graph_contract(
    *,
    structure_report_packet: dict[str, Any],
    execution_preflight_packet: dict[str, Any],
    capability_packet: dict[str, Any],
    bundle_packet: dict[str, Any],
    registry_packet: dict[str, Any],
    report_ux_packet: dict[str, Any] | None = None,
    structure_report_path: str = DEFAULT_STRUCTURE_REPORT_JSON,
    execution_preflight_path: str = DEFAULT_EXECUTION_PREFLIGHT_JSON,
    capability_path: str = DEFAULT_CAPABILITY_JSON,
    bundle_path: str = DEFAULT_BUNDLE_JSON,
    registry_path: str = DEFAULT_REGISTRY_JSON,
    report_ux_path: str = DEFAULT_REPORT_UX_JSON,
) -> dict[str, Any]:
    structure = _summary(structure_report_packet)
    preflight = _summary(execution_preflight_packet)
    capability = _summary(capability_packet)
    bundle = _summary(bundle_packet)
    registry = _summary(registry_packet)
    report_ux = _summary(report_ux_packet or {})
    registry_abstention_detail = _registry_abstention_detail(registry)

    structure_ready = (
        _text(structure.get("status")) == "product_structure_analysis_report_ready"
        and _bool(structure.get("local_structure_parsed"))
        and _int(structure.get("atom_count")) > 0
    )
    binding_site_ready = (
        structure_ready
        and _int(structure.get("chain_count")) > 0
        and _int(structure.get("residue_count")) > 0
    )
    pose_ready = (
        _text(capability.get("status")) == "product_capability_surface_contract_ready"
        and _bool(capability.get("ligand_docking_capability_ready"))
        and _text(preflight.get("status")) == "product_execution_preflight_ready"
        and _int(preflight.get("config_count")) > 0
    )
    scoring_ready = (
        pose_ready
        and _text(preflight.get("operational_gate_feasibility_status")) == "pass"
    )
    uncertainty_ready = (
        _text(registry.get("status")) == "residual_model_registry_ready"
        and _bool(registry.get("product_model_layer_ready"))
        and _bool(registry.get("registry_ready"))
        and _text(registry.get("default_residual_mode")) == "shadow"
        and registry.get("production_promotion_allowed") is False
    )
    report_ready = (
        _text(bundle.get("status")) == "product_bundle_contract_ready"
        and _text(bundle.get("bundle_parser_status")) == "parsed"
        and _bool(bundle.get("bundle_validation_command_matches"))
    )
    customer_report_ux_ready = (
        _text(report_ux.get("status")) == "product_ai_report_ux_contract_ready"
        and _bool(report_ux.get("ai_report_ux_ready"))
        and _bool(report_ux.get("structured_customer_report_ready"))
        and _bool(report_ux.get("customer_report_card_ready"))
        and _bool(report_ux.get("binding_site_explanation_ready"))
        and _bool(report_ux.get("pose_comparison_ready"))
        and _bool(report_ux.get("interaction_rationale_ready"))
        and _bool(report_ux.get("viewer_interaction_surface_ready"))
        and _bool(report_ux.get("uncertainty_narrative_ready"))
        and _bool(report_ux.get("counterfactual_rescue_suggestion_ready"))
        and _bool(report_ux.get("evidence_traceability_ready"))
    )

    rows = [
        _row(
            "structure_quality",
            "ready" if structure_ready else "blocked",
            structure_report_path,
            f"status={structure.get('status')};parsed={structure.get('local_structure_parsed')};atoms={structure.get('atom_count')}",
            "parsed local structure-analysis report with atom_count>0",
            "The graph needs a structure quality node before binding-site and docking interpretation.",
        ),
        _row(
            "binding_site_context",
            "ready" if binding_site_ready else "blocked",
            structure_report_path,
            f"chains={structure.get('chain_count')};residues={structure.get('residue_count')};ligand_like={structure.get('ligand_like_residue_count')}",
            "structure context has chain and residue counts for binding-site interpretation",
            "Binding-site explanation should be grounded in parsed local structure context.",
        ),
        _row(
            "pose_generation_contract",
            "ready" if pose_ready else "blocked",
            f"{capability_path};{execution_preflight_path}",
            f"ligand_docking={capability.get('ligand_docking_capability_ready')};preflight={preflight.get('status')};configs={preflight.get('config_count')}",
            "ligand-docking capability and execution preflight with config evidence",
            "The graph needs a bounded pose generation/docking contract before scoring claims.",
        ),
        _row(
            "scoring_ranking_gate",
            "ready" if scoring_ready else "blocked",
            execution_preflight_path,
            f"preflight={preflight.get('status')};operational_gate={preflight.get('operational_gate_feasibility_status')}",
            "execution preflight operational gate passes",
            "The graph needs a scoring/ranking node with local gate evidence.",
        ),
        _row(
            "uncertainty_abstention_guard",
            "ready" if uncertainty_ready else "blocked",
            registry_path,
            (
                f"registry={registry.get('status')};product_model_layer={registry.get('product_model_layer_ready')};"
                f"default_mode={registry.get('default_residual_mode')};production_promotion={registry.get('production_promotion_allowed')};"
                f"{registry_abstention_detail}"
            ),
            "residual registry ready with shadow default and production promotion blocked",
            "The graph must know when AI residuals are evidence-only and must abstain from production correction.",
        ),
        _row(
            "report_bundle_contract",
            "ready" if report_ready else "blocked",
            bundle_path,
            f"bundle={bundle.get('status')};parser={bundle.get('bundle_parser_status')};validation_command={bundle.get('bundle_validation_command_matches')}",
            "report/result bundle contract parsed with validation command match",
            "The graph needs a report node that can hand off auditable local evidence.",
        ),
        _row(
            "customer_report_ux",
            "ready" if customer_report_ux_ready else "blocked",
            report_ux_path,
            (
                f"report_ux={report_ux.get('status')};structured_customer_report={report_ux.get('structured_customer_report_ready')};"
                f"viewer={report_ux.get('viewer_interaction_surface_ready')};interaction={report_ux.get('interaction_rationale_ready')};"
                f"uncertainty={report_ux.get('uncertainty_narrative_ready')};counterfactual={report_ux.get('counterfactual_rescue_suggestion_ready')};"
                f"traceability={report_ux.get('evidence_traceability_ready')}"
            ),
            "customer report UX contract covers viewer surface, explanations, uncertainty, counterfactuals, and evidence traceability",
            "The graph must terminate in the customer-facing report surface, not only internal evidence bundles.",
        ),
    ]
    node_status = {row["node_id"]: row["status"] for row in rows}
    edges = [
        _edge_row(
            edge_id=f"{source}->{target}",
            source_node_id=source,
            target_node_id=target,
            status="ready" if node_status.get(source) == "ready" and node_status.get(target) == "ready" else "blocked",
            payload=payload,
            observed=f"source={node_status.get(source, 'missing')};target={node_status.get(target, 'missing')}",
            required=required,
        )
        for source, target, payload, required in REQUIRED_EDGES
    ]
    blocked = [row for row in rows if row["status"] != "ready"]
    blocked_edges = [row for row in edges if row["status"] != "ready"]
    edge_ready = not blocked_edges and len(edges) == len(REQUIRED_EDGES)
    ready = not blocked and edge_ready
    summary = {
        "packet_type": "product_ai_decision_graph_contract",
        "status": "product_ai_decision_graph_contract_ready" if ready else "blocked_product_ai_decision_graph_contract",
        "closed_loop_decision_graph_ready": ready,
        "node_count": len(rows),
        "ready_node_count": sum(1 for row in rows if row["status"] == "ready"),
        "blocked_node_count": len(blocked),
        "required_edge_count": len(REQUIRED_EDGES),
        "edge_count": len(edges),
        "ready_edge_count": sum(1 for row in edges if row["status"] == "ready"),
        "blocked_edge_count": len(blocked_edges),
        "fail_closed_transition_ready": edge_ready and uncertainty_ready and report_ready and customer_report_ux_ready,
        "ordered_graph_path": [row["node_id"] for row in rows],
        "structure_quality_node_ready": structure_ready,
        "binding_site_node_ready": binding_site_ready,
        "pose_generation_node_ready": pose_ready,
        "scoring_node_ready": scoring_ready,
        "uncertainty_abstention_node_ready": uncertainty_ready,
        "report_node_ready": report_ready,
        "customer_report_ux_node_ready": customer_report_ux_ready,
        "viewer_interaction_surface_ready": _bool(report_ux.get("viewer_interaction_surface_ready")),
        "customer_report_card_ready": _bool(report_ux.get("customer_report_card_ready")),
        "interaction_rationale_ready": _bool(report_ux.get("interaction_rationale_ready")),
        "counterfactual_rescue_suggestion_ready": _bool(report_ux.get("counterfactual_rescue_suggestion_ready")),
        "evidence_traceability_ready": _bool(report_ux.get("evidence_traceability_ready")),
        "production_ai_inference_enabled": False,
        "uncertainty_abstention_detail": registry_abstention_detail,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "model_inference_executed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Closed-loop AI decision graph contract is ready as an evidence graph; production AI inference remains separately gated by checkpoint and benchmark promotion."
            if ready
            else "Repair blocked graph nodes before treating structure/docking evidence as one AI analysis graph."
        ),
    }
    return {"summary": summary, "rows": rows, "edges": edges, "blockers": blocked + blocked_edges}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Product AI Decision Graph Contract",
        "",
        f"- status: `{s['status']}`",
        f"- closed_loop_decision_graph_ready: `{s['closed_loop_decision_graph_ready']}`",
        f"- ready_node_count: `{s['ready_node_count']}` / `{s['node_count']}`",
        f"- ready_edge_count: `{s['ready_edge_count']}` / `{s['edge_count']}`",
        f"- fail_closed_transition_ready: `{s['fail_closed_transition_ready']}`",
        f"- customer_report_ux_node_ready: `{s['customer_report_ux_node_ready']}`",
        f"- viewer_interaction_surface_ready: `{s['viewer_interaction_surface_ready']}`",
        f"- customer_report_card_ready: `{s['customer_report_card_ready']}`",
        f"- uncertainty_abstention_detail: `{s['uncertainty_abstention_detail']}`",
        "",
        "## Nodes",
        "",
        "| node | status | observed | reason |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(f"| `{row['node_id']}` | `{row['status']}` | `{row['observed']}` | {row['reason']} |")
    lines.extend(
        [
            "",
            "## Edges",
            "",
            "| edge | status | payload | observed | required |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload["edges"]:
        lines.append(
            f"| `{row['edge_id']}` | `{row['status']}` | `{row['payload']}` | `{row['observed']}` | {row['required']} |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build product AI decision graph contract from local evidence.")
    parser.add_argument("--structure-report-json", default=DEFAULT_STRUCTURE_REPORT_JSON)
    parser.add_argument("--execution-preflight-json", default=DEFAULT_EXECUTION_PREFLIGHT_JSON)
    parser.add_argument("--capability-json", default=DEFAULT_CAPABILITY_JSON)
    parser.add_argument("--bundle-json", default=DEFAULT_BUNDLE_JSON)
    parser.add_argument("--registry-json", default=DEFAULT_REGISTRY_JSON)
    parser.add_argument("--report-ux-json", default=DEFAULT_REPORT_UX_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_product_ai_decision_graph_contract(
        structure_report_packet=_read_json(args.structure_report_json),
        execution_preflight_packet=_read_json(args.execution_preflight_json),
        capability_packet=_read_json(args.capability_json),
        bundle_packet=_read_json(args.bundle_json),
        registry_packet=_read_json(args.registry_json),
        report_ux_packet=_read_json(args.report_ux_json),
        structure_report_path=args.structure_report_json,
        execution_preflight_path=args.execution_preflight_json,
        capability_path=args.capability_json,
        bundle_path=args.bundle_json,
        registry_path=args.registry_json,
        report_ux_path=args.report_ux_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
