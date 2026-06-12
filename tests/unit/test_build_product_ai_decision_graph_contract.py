from __future__ import annotations

import json
from pathlib import Path

from tools.product import build_product_ai_decision_graph_contract as mod


def _packet(summary: dict[str, object]) -> dict[str, object]:
    return {"summary": summary}


def test_product_ai_decision_graph_contract_ready_from_local_evidence() -> None:
    payload = mod.build_product_ai_decision_graph_contract(
        structure_report_packet=_packet(
            {
                "status": "product_structure_analysis_report_ready",
                "local_structure_parsed": True,
                "atom_count": 10,
                "chain_count": 1,
                "residue_count": 8,
            }
        ),
        execution_preflight_packet=_packet(
            {
                "status": "product_execution_preflight_ready",
                "operational_gate_feasibility_status": "pass",
                "config_count": 1,
            }
        ),
        capability_packet=_packet(
            {
                "status": "product_capability_surface_contract_ready",
                "ligand_docking_capability_ready": True,
            }
        ),
        bundle_packet=_packet(
            {
                "status": "product_bundle_contract_ready",
                "bundle_parser_status": "parsed",
                "bundle_validation_command_matches": True,
            }
        ),
        registry_packet=_packet(
            {
                "status": "residual_model_registry_ready",
                "product_model_layer_ready": True,
                "registry_ready": True,
                "default_residual_mode": "shadow",
                "production_promotion_allowed": False,
                "selected_sidecar_status": "blocked_residual_production_checkpoint_sidecar",
                "selected_sidecar_ready": False,
                "selected_sidecar_missing_output_fields": ["delta_force"],
                "selected_sidecar_training_contract_missing_label_fields": ["delta_force"],
                "selected_sidecar_force_receipt_ready": False,
                "selected_sidecar_force_receipt_operator_verified": False,
                "selected_sidecar_force_receipt_operator_verified_true_count": 0,
                "selected_sidecar_force_receipt_expected_queue_rows": 768,
            }
        ),
        report_ux_packet=_packet(
            {
                "status": "product_ai_report_ux_contract_ready",
                "ai_report_ux_ready": True,
                "structured_customer_report_ready": True,
                "customer_report_card_ready": True,
                "binding_site_explanation_ready": True,
                "pose_comparison_ready": True,
                "interaction_rationale_ready": True,
                "ligand_selection_rationale_ready": True,
                "viewer_interaction_surface_ready": True,
                "uncertainty_narrative_ready": True,
                "counterfactual_rescue_suggestion_ready": True,
                "evidence_traceability_ready": True,
            }
        ),
    )

    summary = payload["summary"]
    assert summary["status"] == "product_ai_decision_graph_contract_ready"
    assert summary["closed_loop_decision_graph_ready"] is True
    assert summary["core_analysis_graph_ready"] is True
    assert summary["core_ready_node_count"] == 6
    assert summary["core_ready_edge_count"] == 5
    assert summary["ready_node_count"] == 7
    assert summary["ready_edge_count"] == 6
    assert summary["required_edge_count"] == 6
    assert summary["fail_closed_transition_ready"] is True
    assert summary["customer_report_ux_node_ready"] is True
    assert summary["viewer_interaction_surface_ready"] is True
    assert summary["customer_report_card_ready"] is True
    assert summary["interaction_rationale_ready"] is True
    assert summary["ligand_selection_rationale_ready"] is True
    assert summary["counterfactual_rescue_suggestion_ready"] is True
    assert summary["evidence_traceability_ready"] is True
    assert summary["production_ai_inference_enabled"] is False
    assert "selected_sidecar_missing_output_fields=delta_force" in summary["uncertainty_abstention_detail"]
    assert "selected_sidecar_force_receipt_expected_queue_rows=768" in summary["uncertainty_abstention_detail"]
    uncertainty_row = next(row for row in payload["rows"] if row["node_id"] == "uncertainty_abstention_guard")
    assert "selected_sidecar_force_receipt_operator_verified=False" in uncertainty_row["observed"]
    assert [edge["edge_id"] for edge in payload["edges"]] == [
        "structure_quality->binding_site_context",
        "binding_site_context->pose_generation_contract",
        "pose_generation_contract->scoring_ranking_gate",
        "scoring_ranking_gate->uncertainty_abstention_guard",
        "uncertainty_abstention_guard->report_bundle_contract",
        "report_bundle_contract->customer_report_ux",
    ]


def test_product_ai_decision_graph_accepts_guarded_active_registry_with_atom_context() -> None:
    payload = mod.build_product_ai_decision_graph_contract(
        structure_report_packet=_packet(
            {
                "status": "product_structure_analysis_report_ready",
                "local_structure_parsed": True,
                "atom_count": 42,
                "ligand_like_residue_count": 1,
            }
        ),
        execution_preflight_packet=_packet(
            {
                "status": "product_execution_preflight_ready",
                "operational_gate_feasibility_status": "pass",
                "config_count": 1,
            }
        ),
        capability_packet=_packet(
            {
                "status": "product_capability_surface_contract_ready",
                "ligand_docking_capability_ready": True,
            }
        ),
        bundle_packet=_packet(
            {
                "status": "product_bundle_contract_ready",
                "bundle_parser_status": "parsed",
                "bundle_validation_command_matches": True,
            }
        ),
        registry_packet=_packet(
            {
                "status": "residual_model_registry_ready",
                "product_model_layer_ready": True,
                "registry_ready": True,
                "default_residual_mode": "production_guarded",
                "production_promotion_allowed": True,
                "customer_facing_auto_correction_allowed": True,
                "customer_facing_score_mutation_allowed": True,
                "selected_sidecar_ready": True,
                "selected_sidecar_missing_output_fields": [],
            }
        ),
        report_ux_packet=_packet(
            {
                "status": "product_ai_report_ux_contract_ready",
                "ai_report_ux_ready": True,
                "structured_customer_report_ready": True,
                "customer_report_card_ready": True,
                "binding_site_explanation_ready": True,
                "pose_comparison_ready": True,
                "interaction_rationale_ready": True,
                "ligand_selection_rationale_ready": True,
                "viewer_interaction_surface_ready": True,
                "uncertainty_narrative_ready": True,
                "counterfactual_rescue_suggestion_ready": True,
                "evidence_traceability_ready": True,
            }
        ),
    )

    summary = payload["summary"]
    assert summary["status"] == "product_ai_decision_graph_contract_ready"
    assert summary["binding_site_node_ready"] is True
    assert summary["uncertainty_abstention_node_ready"] is True
    assert summary["shadow_abstention_ready"] is False
    assert summary["production_guarded_active_ready"] is True
    assert summary["uncertainty_policy_mode"] == "production_guarded_active"
    uncertainty_row = next(row for row in payload["rows"] if row["node_id"] == "uncertainty_abstention_guard")
    assert "guarded_active_ready=True" in uncertainty_row["observed"]


def test_product_ai_decision_graph_contract_blocks_missing_structure() -> None:
    payload = mod.build_product_ai_decision_graph_contract(
        structure_report_packet=_packet({"status": "missing"}),
        execution_preflight_packet=_packet({}),
        capability_packet=_packet({}),
        bundle_packet=_packet({}),
        registry_packet=_packet({}),
        report_ux_packet=_packet({}),
    )

    assert payload["summary"]["status"] == "blocked_product_ai_decision_graph_contract"
    assert payload["summary"]["closed_loop_decision_graph_ready"] is False
    assert payload["summary"]["core_analysis_graph_ready"] is False
    assert payload["summary"]["blocked_node_count"] >= 1
    assert payload["summary"]["blocked_edge_count"] >= 1


def test_product_ai_decision_graph_exposes_core_ready_before_report_ux() -> None:
    payload = mod.build_product_ai_decision_graph_contract(
        structure_report_packet=_packet(
            {
                "status": "product_structure_analysis_report_ready",
                "local_structure_parsed": True,
                "atom_count": 10,
                "chain_count": 1,
                "residue_count": 8,
            }
        ),
        execution_preflight_packet=_packet(
            {
                "status": "product_execution_preflight_ready",
                "operational_gate_feasibility_status": "pass",
                "config_count": 1,
            }
        ),
        capability_packet=_packet(
            {
                "status": "product_capability_surface_contract_ready",
                "ligand_docking_capability_ready": True,
            }
        ),
        bundle_packet=_packet(
            {
                "status": "product_bundle_contract_ready",
                "bundle_parser_status": "parsed",
                "bundle_validation_command_matches": True,
            }
        ),
        registry_packet=_packet(
            {
                "status": "residual_model_registry_ready",
                "product_model_layer_ready": True,
                "registry_ready": True,
                "default_residual_mode": "shadow",
                "production_promotion_allowed": False,
            }
        ),
        report_ux_packet=_packet({"status": "blocked_product_ai_report_ux_contract"}),
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_product_ai_decision_graph_contract"
    assert summary["closed_loop_decision_graph_ready"] is False
    assert summary["core_analysis_graph_ready"] is True
    assert summary["core_ready_node_count"] == 6
    assert summary["core_ready_edge_count"] == 5
    assert summary["customer_report_ux_node_ready"] is False


def test_product_ai_decision_graph_contract_cli_writes_outputs(tmp_path: Path) -> None:
    paths: dict[str, Path] = {}
    packets = {
        "structure": _packet({"status": "missing"}),
        "preflight": _packet({}),
        "capability": _packet({}),
        "bundle": _packet({}),
        "registry": _packet({}),
        "report_ux": _packet({}),
    }
    for name, packet in packets.items():
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps(packet) + "\n", encoding="utf-8")
        paths[name] = path
    out_json = tmp_path / "graph.json"
    out_csv = tmp_path / "graph.csv"
    out_md = tmp_path / "graph.md"

    mod.main(
        [
            "--structure-report-json",
            str(paths["structure"]),
            "--execution-preflight-json",
            str(paths["preflight"]),
            "--capability-json",
            str(paths["capability"]),
            "--bundle-json",
            str(paths["bundle"]),
            "--registry-json",
            str(paths["registry"]),
            "--report-ux-json",
            str(paths["report_ux"]),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["node_count"] == 7
    assert out_csv.exists()
    md = out_md.read_text(encoding="utf-8")
    assert "# Product AI Decision Graph Contract" in md
    assert "## Edges" in md
