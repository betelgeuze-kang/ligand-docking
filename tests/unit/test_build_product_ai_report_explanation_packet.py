from __future__ import annotations

import json
from pathlib import Path

from tools.product import build_product_ai_report_explanation_packet as mod


def _packet(summary: dict[str, object]) -> dict[str, object]:
    return {"summary": summary}


def test_report_explanation_packet_ready_from_local_evidence() -> None:
    payload = mod.build_product_ai_report_explanation_packet(
        decision_graph_packet=_packet({"closed_loop_decision_graph_ready": True}),
        structure_report_packet=_packet(
            {
                "status": "product_structure_analysis_report_ready",
                "local_structure_parsed": True,
                "target_id": "ADRB2",
                "family": "gpcr",
                "atom_count": 3804,
                "chain_count": 2,
                "residue_count": 507,
                "ligand_like_residue_count": 17,
            }
        ),
        execution_preflight_packet=_packet(
            {"status": "product_execution_preflight_ready", "operational_gate_feasibility_status": "pass", "config_count": 1}
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
            {"status": "residual_model_registry_ready", "default_residual_mode": "shadow", "production_promotion_allowed": False}
        ),
        scope_claim_guard_packet=_packet(
            {
                "closure_checklist_ready": True,
                "allowed_scope_families": ["gpcr", "ion_channel", "kinase"],
                "blocked_claim_scopes": [
                    "transporter_domain_promotion",
                    "pxr_domain_promotion",
                    "general_protein_ligand_platform",
                ],
                "claim_blocked_domains": ["transporter", "pxr"],
                "general_platform_claim_allowed": False,
                "next_required_step": "Close transporter/PXR scientific rows first.",
            }
        ),
    )

    summary = payload["summary"]
    assert summary["status"] == "product_ai_report_explanation_packet_ready"
    assert summary["ai_report_explanation_packet_ready"] is True
    assert summary["structured_customer_report_ready"] is True
    assert summary["required_structured_field_count"] == len(mod.REQUIRED_STRUCTURED_FIELDS)
    assert summary["customer_report_delivery_contract_ready"] is True
    assert summary["customer_report_evidence_binding_ready"] is True
    assert summary["customer_report_required_block_count"] == len(mod.REQUIRED_CUSTOMER_REPORT_BLOCKS)
    assert summary["customer_report_ready_block_count"] == len(mod.REQUIRED_CUSTOMER_REPORT_BLOCKS)
    assert summary["customer_report_blocked_block_count"] == 0
    assert summary["customer_report_required_blocks"] == list(mod.REQUIRED_CUSTOMER_REPORT_BLOCKS)
    assert summary["customer_report_card"]["production_ai_correction_applied"] is False
    assert summary["customer_report_card"]["primary_abstention_reason"] == "production_residual_checkpoint_not_promoted"
    assert summary["customer_report_card"]["customer_report_delivery_contract_ready"] is True
    assert "delta_force" in summary["customer_report_card"]["what_would_change_decision"]
    assert summary["customer_report_card"]["allowed_scope_families"] == ["gpcr", "ion_channel", "kinase"]
    assert summary["customer_report_card"]["blocked_claim_scopes"] == [
        "transporter_domain_promotion",
        "pxr_domain_promotion",
        "general_protein_ligand_platform",
    ]
    assert summary["customer_report_card"]["general_platform_claim_allowed"] is False
    assert summary["customer_report_card"]["scope_claim_limit_ready"] is True
    assert summary["interaction_rationale_ready"] is True
    assert summary["evidence_traceability_ready"] is True
    assert summary["ranking_score_col"] == "not_reported"
    assert summary["ready_section_count"] == 6
    assert {row["section_id"] for row in payload["rows"]} == set(mod.REQUIRED_SECTIONS)
    assert "3804 atoms" in payload["rows"][0]["narrative"]
    interaction = next(row for row in payload["rows"] if row["section_id"] == "interaction_rationale")
    assert interaction["status"] == "ready"
    assert "why is this pose plausible" in interaction["customer_question"].lower()
    assert "artifact_count=1" in interaction["evidence_traceability"]
    assert all(row["customer_question"] for row in payload["rows"])
    assert all(row["claim_limit"] for row in payload["rows"])
    assert all(row["what_would_change_decision"] for row in payload["rows"])
    assert all(row["evidence_traceability"] for row in payload["rows"])
    assert all(row["customer_report_delivery_block_ready"] for row in payload["rows"])
    assert all(row["customer_report_evidence_binding_ready"] for row in payload["rows"])
    uncertainty = next(row for row in payload["rows"] if row["section_id"] == "uncertainty_narrative")
    assert uncertainty["abstention_reason"] == "production_residual_checkpoint_not_promoted"
    scope = next(row for row in payload["rows"] if row["section_id"] == "scope_claim_limit")
    assert scope["status"] == "ready"
    assert "general_protein_ligand_platform" in scope["claim_limit"]


def test_report_explanation_packet_blocks_missing_graph() -> None:
    payload = mod.build_product_ai_report_explanation_packet(
        decision_graph_packet=_packet({"closed_loop_decision_graph_ready": False}),
        structure_report_packet=_packet({}),
        execution_preflight_packet=_packet({}),
        bundle_packet=_packet({}),
        registry_packet=_packet({}),
    )

    assert payload["summary"]["status"] == "blocked_product_ai_report_explanation_packet"
    assert payload["summary"]["blocked_section_count"] == 6
    assert payload["summary"]["customer_report_delivery_contract_ready"] is False


def test_report_explanation_packet_cli_writes_outputs(tmp_path: Path) -> None:
    paths: dict[str, Path] = {}
    for name in ["graph", "structure", "preflight", "bundle", "registry", "scope"]:
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps(_packet({})) + "\n", encoding="utf-8")
        paths[name] = path
    out_json = tmp_path / "explanation.json"
    out_csv = tmp_path / "explanation.csv"
    out_md = tmp_path / "explanation.md"

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
            "--scope-claim-guard-json",
            str(paths["scope"]),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["section_count"] == 6
    assert "binding_site_explanation" in out_csv.read_text(encoding="utf-8")
    md = out_md.read_text(encoding="utf-8")
    assert "Product AI Report Explanation Packet" in md
    assert "structured_customer_report_ready" in md
