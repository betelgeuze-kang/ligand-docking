from __future__ import annotations

import json
from pathlib import Path

from tools.product import build_product_ai_report_ux_contract as mod


def _packet(summary: dict[str, object]) -> dict[str, object]:
    return {"summary": summary}


def test_product_ai_report_ux_contract_ready_from_local_evidence(tmp_path: Path) -> None:
    viewer_index = tmp_path / "viewer" / "index.html"
    viewer_app = tmp_path / "viewer" / "app.js"
    viewer_index.parent.mkdir()
    viewer_index.write_text("<html></html>\n", encoding="utf-8")
    viewer_app.write_text(
        "const interactionOverlay = true; const contactMap = true; "
        "const CUSTOMER_REPORT_REQUIRED_BLOCKS = ['binding_site_explanation','pose_comparison',"
        "'interaction_rationale','ligand_selection_rationale','uncertainty_narrative','scope_claim_limit',"
        "'counterfactual_rescue_suggestion']; "
        "const customerReportCard = {}; "
        "function summarizeInteractionTypes(){} function renderInteractionOverlay(){} "
        "function normalizeCustomerReportBlock(){} function renderCustomerReportCard(){}\n",
        encoding="utf-8",
    )

    payload = mod.build_product_ai_report_ux_contract(
        decision_graph_packet=_packet({"status": "product_ai_decision_graph_contract_ready", "closed_loop_decision_graph_ready": True}),
        structure_report_packet=_packet(
            {
                "status": "product_structure_analysis_report_ready",
                "chain_count": 1,
                "residue_count": 20,
                "ligand_like_residue_count": 2,
            }
        ),
        execution_preflight_packet=_packet(
            {
                "status": "product_execution_preflight_ready",
                "operational_gate_feasibility_status": "pass",
            }
        ),
        bundle_packet=_packet(
            {
                "status": "product_bundle_contract_ready",
                "artifact_count": 1,
                "expected_bundle_dir": "runs/local_delivery/bundle",
                "bundle_validation_command_matches": True,
            }
        ),
        registry_packet=_packet(
            {
                "status": "residual_model_registry_ready",
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
        explanation_packet={
            "summary": {
                "status": "product_ai_report_explanation_packet_ready",
                "ai_report_explanation_packet_ready": True,
                "structured_customer_report_ready": True,
                "customer_report_card": {
                    "primary_abstention_reason": "production_residual_checkpoint_not_promoted",
                    "what_would_change_decision": "Return delta_force labels and promote the checkpoint.",
                    "ligand_selection_rationale_ready": True,
                    "selection_rationale": "Ligand was surfaced by audited score provenance and restricted-scope guardrails.",
                    "allowed_scope_families": ["gpcr", "ion_channel", "kinase"],
                    "blocked_claim_scopes": [
                        "transporter_domain_promotion",
                        "pxr_domain_promotion",
                        "general_protein_ligand_platform",
                    ],
                    "claim_blocked_domains": ["transporter", "pxr"],
                    "general_platform_claim_allowed": False,
                    "scope_claim_guard_ready": True,
                    "scope_claim_limit_ready": True,
                },
                "interaction_rationale_ready": True,
                "ligand_selection_rationale_ready": True,
                "evidence_traceability_ready": True,
                "customer_report_delivery_contract_ready": True,
                "customer_report_evidence_binding_ready": True,
                "customer_report_required_block_count": 7,
                "customer_report_ready_block_count": 7,
                "customer_report_blocked_block_count": 0,
                "customer_report_required_blocks": list(mod.REQUIRED_CUSTOMER_REPORT_BLOCKS),
                "customer_report_ready_blocks": list(mod.REQUIRED_CUSTOMER_REPORT_BLOCKS),
                "customer_report_missing_blocks": [],
                "ranking_score_col": "binding_score_composite_v5",
                "interaction_distance_gate_A": "4.75",
                "interaction_topk_hit_rate_gate": "0.2",
                "ready_section_count": 7,
                "blocked_section_count": 0,
            },
            "rows": [{"section_id": section_id} for section_id in mod.REQUIRED_CUSTOMER_REPORT_BLOCKS],
        },
        viewer_index=str(viewer_index),
        viewer_app=str(viewer_app),
    )

    summary = payload["summary"]
    assert summary["status"] == "product_ai_report_ux_contract_ready"
    assert summary["ai_report_ux_ready"] is True
    assert summary["ready_section_count"] == 10
    assert summary["viewer_ready"] is True
    assert summary["viewer_interaction_surface_ready"] is True
    assert summary["viewer_customer_report_binding_ready"] is True
    assert summary["customer_report_viewer_binding_ready"] is True
    assert summary["explanation_packet_ready"] is True
    assert summary["interaction_rationale_ready"] is True
    assert summary["ligand_selection_rationale_ready"] is True
    assert summary["selection_rationale"] == (
        "Ligand was surfaced by audited score provenance and restricted-scope guardrails."
    )
    assert summary["evidence_traceability_ready"] is True
    assert summary["ranking_score_col"] == "binding_score_composite_v5"
    assert summary["structured_customer_report_ready"] is True
    assert summary["customer_report_delivery_contract_ready"] is True
    assert summary["customer_report_evidence_binding_ready"] is True
    assert summary["customer_report_ready_block_count"] == 7
    assert summary["customer_report_required_block_count"] == 7
    assert summary["customer_report_blocked_block_count"] == 0
    assert summary["customer_report_card_ready"] is True
    assert summary["customer_report_card"]["primary_abstention_reason"] == (
        "production_residual_checkpoint_not_promoted"
    )
    assert summary["customer_report_card"]["what_would_change_decision"] == (
        "Return delta_force labels and promote the checkpoint."
    )
    assert summary["primary_abstention_reason"] == "production_residual_checkpoint_not_promoted"
    assert summary["scope_claim_limit_ready"] is True
    assert summary["allowed_scope_families"] == ["gpcr", "ion_channel", "kinase"]
    assert summary["blocked_claim_scopes"] == [
        "transporter_domain_promotion",
        "pxr_domain_promotion",
        "general_protein_ligand_platform",
    ]
    assert summary["general_platform_claim_allowed"] is False
    assert "selected_sidecar_missing_output_fields=delta_force" in summary["uncertainty_abstention_detail"]
    assert "selected_sidecar_force_receipt_expected_queue_rows=768" in summary["uncertainty_abstention_detail"]
    uncertainty = next(row for row in payload["rows"] if row["section_id"] == "uncertainty_narrative")
    assert "selected_sidecar_force_receipt_operator_verified=False" in uncertainty["observed"]
    interaction = next(row for row in payload["rows"] if row["section_id"] == "interaction_rationale")
    assert "viewer_interaction_surface_ready=True" in interaction["observed"]
    ligand_selection = next(row for row in payload["rows"] if row["section_id"] == "ligand_selection_rationale")
    assert "selection_rationale_present=True" in ligand_selection["observed"]
    delivery = next(row for row in payload["rows"] if row["section_id"] == "customer_report_delivery_contract")
    assert "ready_block_count=7" in delivery["observed"]
    viewer_binding = next(row for row in payload["rows"] if row["section_id"] == "customer_report_viewer_binding")
    assert "viewer_customer_report_binding_ready=True" in viewer_binding["observed"]


def test_product_ai_report_ux_contract_accepts_production_guarded_policy(tmp_path: Path) -> None:
    viewer_index = tmp_path / "viewer" / "index.html"
    viewer_app = tmp_path / "viewer" / "app.js"
    viewer_index.parent.mkdir()
    viewer_index.write_text("<html></html>\n", encoding="utf-8")
    viewer_app.write_text(
        "const interactionOverlay = true; const contactMap = true; "
        "const CUSTOMER_REPORT_REQUIRED_BLOCKS = ['binding_site_explanation','pose_comparison',"
        "'interaction_rationale','ligand_selection_rationale','uncertainty_narrative','scope_claim_limit',"
        "'counterfactual_rescue_suggestion']; "
        "const customerReportCard = {}; "
        "function summarizeInteractionTypes(){} function renderInteractionOverlay(){} "
        "function normalizeCustomerReportBlock(){} function renderCustomerReportCard(){}\n",
        encoding="utf-8",
    )

    payload = mod.build_product_ai_report_ux_contract(
        decision_graph_packet=_packet({"status": "product_ai_decision_graph_contract_ready", "closed_loop_decision_graph_ready": True}),
        structure_report_packet=_packet(
            {
                "status": "product_structure_analysis_report_ready",
                "chain_count": 1,
                "residue_count": 20,
                "ligand_like_residue_count": 2,
            }
        ),
        execution_preflight_packet=_packet(
            {
                "status": "product_execution_preflight_ready",
                "operational_gate_feasibility_status": "pass",
            }
        ),
        bundle_packet=_packet(
            {
                "status": "product_bundle_contract_ready",
                "artifact_count": 1,
                "expected_bundle_dir": "runs/local_delivery/bundle",
                "bundle_validation_command_matches": True,
            }
        ),
        registry_packet=_packet(
            {
                "status": "residual_model_registry_ready",
                "default_residual_mode": "production_guarded",
                "production_promotion_allowed": True,
                "customer_facing_auto_correction_allowed": True,
                "customer_facing_score_mutation_allowed": True,
                "customer_facing_ranking_mutation_allowed": True,
                "selected_sidecar_status": "residual_production_checkpoint_sidecar_ready",
                "selected_sidecar_ready": True,
                "selected_sidecar_missing_output_fields": [],
                "selected_sidecar_training_contract_missing_label_fields": [],
                "selected_sidecar_force_receipt_ready": True,
                "selected_sidecar_force_receipt_operator_verified": True,
                "selected_sidecar_force_receipt_operator_verified_true_count": 768,
                "selected_sidecar_force_receipt_expected_queue_rows": 768,
            }
        ),
        explanation_packet={
            "summary": {
                "status": "product_ai_report_explanation_packet_ready",
                "ai_report_explanation_packet_ready": True,
                "structured_customer_report_ready": True,
                "customer_report_card": {
                    "primary_abstention_reason": "production_guarded_active_report_packet_does_not_apply_correction",
                    "what_would_change_decision": "Bind a signed execution result manifest.",
                    "ligand_selection_rationale_ready": True,
                    "selection_rationale": "Ligand was surfaced by audited score provenance and restricted-scope guardrails.",
                    "allowed_scope_families": ["gpcr", "ion_channel", "kinase"],
                    "blocked_claim_scopes": [
                        "transporter_domain_promotion",
                        "pxr_domain_promotion",
                        "general_protein_ligand_platform",
                    ],
                    "general_platform_claim_allowed": False,
                    "scope_claim_guard_ready": True,
                    "scope_claim_limit_ready": True,
                },
                "interaction_rationale_ready": True,
                "ligand_selection_rationale_ready": True,
                "evidence_traceability_ready": True,
                "customer_report_delivery_contract_ready": True,
                "customer_report_evidence_binding_ready": True,
                "customer_report_required_block_count": 7,
                "customer_report_ready_block_count": 7,
                "customer_report_blocked_block_count": 0,
                "customer_report_required_blocks": list(mod.REQUIRED_CUSTOMER_REPORT_BLOCKS),
                "customer_report_ready_blocks": list(mod.REQUIRED_CUSTOMER_REPORT_BLOCKS),
                "customer_report_missing_blocks": [],
                "ranking_score_col": "binding_score_composite_v5",
                "interaction_distance_gate_A": "4.75",
                "ready_section_count": 7,
                "blocked_section_count": 0,
            },
            "rows": [{"section_id": section_id} for section_id in mod.REQUIRED_CUSTOMER_REPORT_BLOCKS],
        },
        viewer_index=str(viewer_index),
        viewer_app=str(viewer_app),
    )

    summary = payload["summary"]
    assert summary["status"] == "product_ai_report_ux_contract_ready"
    assert summary["uncertainty_policy_mode"] == "production_guarded_active"
    assert summary["production_guarded_active_ready"] is True
    assert summary["shadow_abstention_ready"] is False
    uncertainty = next(row for row in payload["rows"] if row["section_id"] == "uncertainty_narrative")
    assert "guarded_active_ready=True" in uncertainty["observed"]


def test_product_ai_report_ux_contract_accepts_core_graph_before_full_graph(tmp_path: Path) -> None:
    viewer_index = tmp_path / "viewer" / "index.html"
    viewer_app = tmp_path / "viewer" / "app.js"
    viewer_index.parent.mkdir()
    viewer_index.write_text("<html></html>\n", encoding="utf-8")
    viewer_app.write_text(
        "const interactionOverlay = true; const contactMap = true; "
        "const CUSTOMER_REPORT_REQUIRED_BLOCKS = ['binding_site_explanation','pose_comparison',"
        "'interaction_rationale','ligand_selection_rationale','uncertainty_narrative','scope_claim_limit',"
        "'counterfactual_rescue_suggestion']; "
        "const customerReportCard = {}; "
        "function summarizeInteractionTypes(){} function renderInteractionOverlay(){} "
        "function normalizeCustomerReportBlock(){} function renderCustomerReportCard(){}\n",
        encoding="utf-8",
    )

    payload = mod.build_product_ai_report_ux_contract(
        decision_graph_packet=_packet(
            {
                "status": "blocked_product_ai_decision_graph_contract",
                "closed_loop_decision_graph_ready": False,
                "core_analysis_graph_ready": True,
            }
        ),
        structure_report_packet=_packet(
            {
                "status": "product_structure_analysis_report_ready",
                "chain_count": 1,
                "residue_count": 20,
                "ligand_like_residue_count": 2,
            }
        ),
        execution_preflight_packet=_packet(
            {
                "status": "product_execution_preflight_ready",
                "operational_gate_feasibility_status": "pass",
            }
        ),
        bundle_packet=_packet(
            {
                "status": "product_bundle_contract_ready",
                "artifact_count": 1,
                "expected_bundle_dir": "runs/local_delivery/bundle",
                "bundle_validation_command_matches": True,
            }
        ),
        registry_packet=_packet(
            {
                "status": "residual_model_registry_ready",
                "default_residual_mode": "shadow",
                "production_promotion_allowed": False,
            }
        ),
        explanation_packet={
            "summary": {
                "status": "product_ai_report_explanation_packet_ready",
                "ai_report_explanation_packet_ready": True,
                "structured_customer_report_ready": True,
                "customer_report_card": {
                    "primary_abstention_reason": "production_residual_checkpoint_not_promoted",
                    "what_would_change_decision": "Return delta_force labels and promote the checkpoint.",
                    "ligand_selection_rationale_ready": True,
                    "selection_rationale": "Ligand was surfaced by audited score provenance and restricted-scope guardrails.",
                    "allowed_scope_families": ["gpcr"],
                    "blocked_claim_scopes": ["general_protein_ligand_platform"],
                    "general_platform_claim_allowed": False,
                    "scope_claim_guard_ready": True,
                    "scope_claim_limit_ready": True,
                },
                "interaction_rationale_ready": True,
                "ligand_selection_rationale_ready": True,
                "evidence_traceability_ready": True,
                "customer_report_delivery_contract_ready": True,
                "customer_report_evidence_binding_ready": True,
                "customer_report_required_block_count": 7,
                "customer_report_ready_block_count": 7,
                "customer_report_blocked_block_count": 0,
                "customer_report_required_blocks": list(mod.REQUIRED_CUSTOMER_REPORT_BLOCKS),
                "customer_report_ready_blocks": list(mod.REQUIRED_CUSTOMER_REPORT_BLOCKS),
                "customer_report_missing_blocks": [],
                "ranking_score_col": "binding_score_composite_v5",
                "interaction_distance_gate_A": "4.75",
                "interaction_topk_hit_rate_gate": "0.2",
            },
            "rows": [{"section_id": section_id} for section_id in mod.REQUIRED_CUSTOMER_REPORT_BLOCKS],
        },
        viewer_index=str(viewer_index),
        viewer_app=str(viewer_app),
    )

    assert payload["summary"]["status"] == "product_ai_report_ux_contract_ready"
    assert payload["summary"]["ai_report_ux_ready"] is True


def test_product_ai_report_ux_contract_blocks_missing_viewer() -> None:
    payload = mod.build_product_ai_report_ux_contract(
        decision_graph_packet=_packet({"closed_loop_decision_graph_ready": True}),
        structure_report_packet=_packet({"status": "product_structure_analysis_report_ready", "chain_count": 1, "residue_count": 1}),
        execution_preflight_packet=_packet({"status": "product_execution_preflight_ready", "operational_gate_feasibility_status": "pass"}),
        bundle_packet=_packet({"status": "product_bundle_contract_ready", "artifact_count": 1, "expected_bundle_dir": "x", "bundle_validation_command_matches": True}),
        registry_packet=_packet({"status": "residual_model_registry_ready", "default_residual_mode": "shadow", "production_promotion_allowed": False}),
        explanation_packet=_packet({
            "ai_report_explanation_packet_ready": True,
            "structured_customer_report_ready": True,
            "interaction_rationale_ready": True,
            "evidence_traceability_ready": True,
            "ranking_score_col": "score",
            "interaction_distance_gate_A": "4.75",
            "customer_report_card": {"primary_abstention_reason": "blocked", "what_would_change_decision": "repair viewer"},
        }),
        viewer_index="/tmp/missing-product-viewer-index.html",
        viewer_app="/tmp/missing-product-viewer-app.js",
    )

    assert payload["summary"]["status"] == "blocked_product_ai_report_ux_contract"
    assert payload["summary"]["viewer_ready"] is False


def test_product_ai_report_ux_contract_cli_writes_outputs(tmp_path: Path) -> None:
    paths: dict[str, Path] = {}
    for name in ["graph", "structure", "preflight", "bundle", "registry", "explanation"]:
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps(_packet({})) + "\n", encoding="utf-8")
        paths[name] = path
    out_json = tmp_path / "report.json"
    out_csv = tmp_path / "report.csv"
    out_md = tmp_path / "report.md"

    mod.main(
        [
            "--decision-graph-json",
            str(paths["graph"]),
            "--structure-report-json",
            str(paths["structure"]),
            "--execution-preflight-json",
            str(paths["preflight"]),
            "--bundle-json",
            str(paths["bundle"]),
            "--registry-json",
            str(paths["registry"]),
            "--explanation-packet-json",
            str(paths["explanation"]),
            "--viewer-index",
            str(tmp_path / "missing-index.html"),
            "--viewer-app",
            str(tmp_path / "missing-app.js"),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["section_count"] == 10
    assert out_csv.exists()
    assert "# Product AI Report UX Contract" in out_md.read_text(encoding="utf-8")
