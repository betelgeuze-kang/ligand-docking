from __future__ import annotations

import asyncio
import json
from pathlib import Path

from api import product_operator_cockpit as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_product_operator_cockpit_endpoint_reads_current_artifact(monkeypatch, tmp_path: Path) -> None:
    artifact = tmp_path / "runs/product_operator_cockpit_current.json"
    monkeypatch.setattr(mod, "PRODUCT_OPERATOR_COCKPIT_ARTIFACT", artifact)
    _write_json(
        artifact,
        {
            "summary": {
                "status": "product_operator_cockpit_ready_claims_blocked",
                "schema_version": "product_operator_cockpit_v1",
                "phase8_surface_ready": True,
                "required_phase8_panel_count": 9,
                "required_phase8_panel_ids": ["product_capabilities_dashboard"],
                "observed_phase8_panel_count": 9,
                "missing_required_phase8_panel_count": 0,
                "missing_required_phase8_panel_ids": [],
                "surface_ready_panel_count": 9,
                "source_artifact_ready_panel_count": 6,
                "source_artifact_blocked_panel_count": 3,
                "source_artifact_blocked_panel_ids": ["hbond_backmap_candidate_table"],
                "operator_action_required_panel_count": 8,
                "operator_action_required_panel_ids": ["release_blockers_operator_actions"],
                "allowed_claim_count": 4,
                "disallowed_claim_count": 6,
                "paid_pilot_wording_allowed": False,
                "general_platform_claim_allowed": False,
                "gpcr_hard_decoy_metric_ready": True,
                "gpcr_broad_claim_allowed": False,
                "pocketmd_lite_refinement_evidence_ready": True,
                "pocketmd_lite_claim_allowed": False,
                "public_benchmark_claim_allowed": False,
                "public_benchmark_receipt_attach_packet_ready": False,
                "public_benchmark_receipt_attach_packet_present": True,
                "public_benchmark_vina_gnina_pending_score_count": 32,
                "public_benchmark_metric_source_pending_field_count": 510,
                "public_benchmark_metric_source_pending_approval_token_count": 51,
                "evidence_bundle_export_ready": True,
                "customer_shadow_paid_pilot_evidence_ready": False,
                "release_allowed": False,
                "next_required_step": "Keep claims locked.",
                "claim_boundary": "cockpit boundary",
            },
            "rows": [{"panel_id": "product_capabilities_dashboard", "route": "/product/capabilities"}],
            "claim_matrix": [{"claim_id": "paid_pilot_wording", "allowed": False}],
        },
    )

    response = asyncio.run(mod.get_product_operator_cockpit())

    assert response["status"] == "product_operator_cockpit_ready_claims_blocked"
    assert response["artifact_path"] == str(artifact)
    assert response["phase8_surface_ready"] is True
    assert response["required_phase8_panel_count"] == 9
    assert response["source_artifact_blocked_panel_ids"] == ["hbond_backmap_candidate_table"]
    assert response["paid_pilot_wording_allowed"] is False
    assert response["general_platform_claim_allowed"] is False
    assert response["gpcr_hard_decoy_metric_ready"] is True
    assert response["gpcr_broad_claim_allowed"] is False
    assert response["public_benchmark_receipt_attach_packet_ready"] is False
    assert response["public_benchmark_receipt_attach_packet_present"] is True
    assert response["public_benchmark_vina_gnina_pending_score_count"] == 32
    assert response["public_benchmark_metric_source_pending_field_count"] == 510
    assert response["public_benchmark_metric_source_pending_approval_token_count"] == 51
    assert response["evidence_bundle_export_ready"] is True
    assert response["panels"][0]["panel_id"] == "product_capabilities_dashboard"
    assert response["claim_matrix"][0]["claim_id"] == "paid_pilot_wording"
    assert response["execution_enabled"] is False
    assert response["docking_results_emitted"] is False
    assert response["external_state_mutated"] is False
    assert response["claim_boundary"] == "cockpit boundary"


def test_product_operator_cockpit_endpoint_fails_closed_when_artifact_missing(monkeypatch, tmp_path: Path) -> None:
    missing = tmp_path / "runs/product_operator_cockpit_current.json"
    monkeypatch.setattr(mod, "PRODUCT_OPERATOR_COCKPIT_ARTIFACT", missing)

    response = asyncio.run(mod.get_product_operator_cockpit())

    assert response["status"] == "missing_product_operator_cockpit"
    assert response["phase8_surface_ready"] is False
    assert response["required_phase8_panel_count"] == 9
    assert response["observed_phase8_panel_count"] == 0
    assert response["paid_pilot_wording_allowed"] is False
    assert response["general_platform_claim_allowed"] is False
    assert response["gpcr_broad_claim_allowed"] is False
    assert response["pocketmd_lite_claim_allowed"] is False
    assert response["public_benchmark_claim_allowed"] is False
    assert response["public_benchmark_receipt_attach_packet_ready"] is False
    assert response["public_benchmark_receipt_attach_packet_present"] is False
    assert response["public_benchmark_vina_gnina_pending_score_count"] == 0
    assert response["public_benchmark_metric_source_pending_field_count"] == 0
    assert response["public_benchmark_metric_source_pending_approval_token_count"] == 0
    assert response["evidence_bundle_export_ready"] is False
    assert response["panels"] == []
    assert response["claim_matrix"] == []
    assert response["execution_enabled"] is False
    assert response["external_state_mutated"] is False
