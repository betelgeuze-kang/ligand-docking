from __future__ import annotations

import json
from pathlib import Path

from tools import build_goal_readiness_rollup as mod


def _product_readiness() -> dict:
    return {"summary": {"status": "product_handoff_ready", "blocker_count": 0, "execution_approval_token_required": "APPROVE_PRODUCT_DOCKING_EXECUTION"}}


def _product_preflight() -> dict:
    return {"summary": {"status": "product_execution_preflight_ready", "blocker_count": 0, "approval_token_required": "APPROVE_PRODUCT_DOCKING_EXECUTION"}}


def _product_delivery_evidence() -> dict:
    return {
        "summary": {
            "status": "product_delivery_evidence_contract_ready",
            "blocker_count": 0,
            "warning_count": 2,
            "delivery_ready_claim_allowed": False,
        }
    }


def _product_pilot_packet() -> dict:
    return {
        "summary": {
            "status": "product_pilot_packet_preflight_ready",
            "blocker_count": 0,
            "warning_count": 2,
            "pilot_delivery_ready": False,
        }
    }


def _product_architecture(blocked_lane_count: int = 1, approval_required_lane_count: int = 2, release_ready: bool = False) -> dict:
    return {
        "summary": {
            "status": "product_architecture_contract_ready" if release_ready else "blocked_product_architecture_contract",
            "local_architecture_surface_ready": True,
            "architecture_release_ready": release_ready,
            "blocked_lane_count": blocked_lane_count,
            "approval_required_lane_count": approval_required_lane_count,
            "structure_analysis_product_surface_ready": True,
            "ligand_docking_execution_contract_ready": True,
            "commercial_independence_ready": release_ready,
            "cameo_architecture_validation_ready": release_ready,
            "cleanup_control_surface_ready": True,
            "casp17_transition_surface_ready": True,
        }
    }


def _cameo(status: str = "blocked_cameo_validation_readiness", blocker_count: int = 4) -> dict:
    return {"summary": {"status": status, "blocker_count": blocker_count, "external_state_mutated": False}}


def _cameo_repair() -> dict:
    return {"summary": {"status": "operator_input_required", "operator_input_missing_count": 2}}


def _cameo_input_kit() -> dict:
    return {"summary": {"status": "cameo_operator_input_kit_ready", "template_count": 3}}


def _cameo_input_validation() -> dict:
    return {"summary": {"status": "blocked_cameo_operator_input_validation", "blocker_count": 3}}


def _cameo_repair_preflight() -> dict:
    return {"summary": {"status": "blocked_cameo_repair_execution_preflight", "blocker_count": 4}}


def _cameo_capability_preflight() -> dict:
    return {
        "summary": {
            "status": "cameo_development_capability_preflight_ready",
            "public_registration_allowed": False,
            "public_registration_blocker_count": 4,
            "source_receiver_smoke_status": "cameo_receiver_smoke_ready",
            "source_api_dependency_status": "cameo_api_dependency_ready",
            "api_dependency_ready": True,
            "api_dependency_blocker_count": 0,
            "receiver_smoke_post_200_ok": True,
            "receiver_smoke_blocker_count": 0,
        }
    }


def _transition_cleanup() -> dict:
    return {
        "summary": {
            "status": "transition_cleanup_work_order_ready",
            "blocker_count": 0,
            "approval_gated_reclaim_size_gb": 43.206,
            "delete_enabled": False,
            "action_executed": False,
        }
    }


def _transition_cleanup_preflight() -> dict:
    return {
        "summary": {
            "status": "transition_cleanup_execution_preflight_ready",
            "blocker_count": 0,
        }
    }


def _ligand_cleanup() -> dict:
    return {
        "summary": {
            "status": "cleanup_work_order_ready",
            "blocker_count": 0,
            "candidate_size_gb": 6.011,
            "approval_token_required": "APPROVE_DELETE_STALE_LIGAND_HEAVY_PAYLOADS",
            "delete_enabled": False,
            "delete_executed": False,
        }
    }


def _ligand_cleanup_preflight() -> dict:
    return {
        "summary": {
            "status": "ligand_heavy_cleanup_execution_preflight_ready",
            "blocker_count": 0,
            "approval_token_required": "APPROVE_DELETE_STALE_LIGAND_HEAVY_PAYLOADS",
        }
    }


def _cleanup_postcheck() -> dict:
    return {
        "summary": {
            "status": "cleanup_postcheck_contract_ready",
            "postcheck_contract_ready": True,
            "row_count": 7,
            "blocked_row_count": 0,
            "global_refresh_command_count": 9,
        }
    }


def _product_cli_status() -> dict:
    return {
        "status": "blocked_product_cli_status_set",
        "approval_token_count": 2,
        "operations_blocked_stage_count": 4,
        "operations_approval_required_stage_count": 2,
        "capability_surface_ready": True,
        "operational_quality_ready": True,
        "architecture_release_ready": False,
        "commercial_independence_ready": False,
        "authorized_for_execution": False,
        "bundle_validation_passed": False,
        "delivery_ready_claim_allowed": False,
    }


def _cameo_cli_status() -> dict:
    return {
        "status": "blocked_cameo_cli_status_set",
        "approval_token_count": 3,
        "official_result_required": True,
        "official_results_accepted_count": 0,
        "evidence_integrity_ready": True,
        "official_results_pending_honest": True,
        "no_local_native_accuracy_substitution": True,
        "api_install_approval_required": True,
        "receiver_smoke_status": "blocked_cameo_receiver_smoke",
    }


def _cleanup_cli_status() -> dict:
    return {
        "status": "blocked_cleanup_cli_status_set",
        "approval_token_count": 4,
        "approval_reclaim_size_gb": 49.216,
        "postcheck_contract_ready": True,
        "protected_payload_size_gb": 396.794,
        "protected_policy_change_required_count": 2,
    }


def _ready_product_ai_gap() -> dict:
    return {
        "summary": {
            "status": "product_ai_architecture_gap_closure_complete",
            "all_gaps_closed": True,
            "open_gap_count": 0,
            "current_primary_open_gap": "none",
        }
    }


def _blocked_product_ai_gap() -> dict:
    return {
        "summary": {
            "status": "blocked_product_ai_architecture_gap_closure",
            "all_gaps_closed": False,
            "open_gap_count": 1,
            "current_primary_open_gap": "scope_breadth_expansion",
        }
    }


def _ready_product_ai_backlog() -> dict:
    return {
        "summary": {
            "status": "product_ai_architecture_execution_backlog_clear",
            "backlog_clear": True,
            "work_item_count": 0,
            "primary_work_item_id": "none",
        }
    }


def _blocked_product_ai_backlog() -> dict:
    return {
        "summary": {
            "status": "product_ai_architecture_execution_backlog_ready",
            "backlog_clear": False,
            "work_item_count": 21,
            "primary_work_item_id": "scope_breadth.transporter.AQP1.core_binder_01",
            "next_required_step": "Close transporter/PXR scientific rows first.",
        }
    }


def test_goal_readiness_rollup_blocks_when_cameo_validation_blocked() -> None:
    payload = mod.build_rollup(
        product_readiness_packet=_product_readiness(),
        product_preflight_packet=_product_preflight(),
        product_delivery_evidence_packet=_product_delivery_evidence(),
        product_pilot_packet=_product_pilot_packet(),
        product_architecture_packet=_product_architecture(),
        cameo_readiness_packet=_cameo(),
        cameo_repair_packet=_cameo_repair(),
        cameo_input_kit_packet=_cameo_input_kit(),
        cameo_input_validation_packet=_cameo_input_validation(),
        cameo_repair_preflight_packet=_cameo_repair_preflight(),
        cameo_capability_preflight_packet=_cameo_capability_preflight(),
        transition_cleanup_packet=_transition_cleanup(),
        transition_cleanup_preflight_packet=_transition_cleanup_preflight(),
        ligand_cleanup_packet=_ligand_cleanup(),
        ligand_cleanup_preflight_packet=_ligand_cleanup_preflight(),
        cleanup_postcheck_packet=_cleanup_postcheck(),
        product_cli_status_packet=_product_cli_status(),
        cameo_cli_status_packet=_cameo_cli_status(),
        cleanup_cli_status_packet=_cleanup_cli_status(),
    )
    rows = {row["lane_id"]: row for row in payload["rows"]}

    assert payload["summary"]["status"] == "blocked_goal_readiness"
    assert payload["summary"]["blocked_lane_count"] == 2
    assert payload["summary"]["operator_approval_pending_count"] == 3
    assert payload["summary"]["total_reclaim_size_gb"] == 49.217
    assert payload["summary"]["cleanup_postcheck_contract_status"] == "cleanup_postcheck_contract_ready"
    assert payload["summary"]["cleanup_postcheck_contract_ready"] is True
    assert payload["summary"]["cleanup_postcheck_row_count"] == 7
    assert payload["summary"]["cleanup_postcheck_blocked_row_count"] == 0
    assert payload["summary"]["cleanup_postcheck_global_refresh_command_count"] == 9
    assert payload["summary"]["product_cli_status_set_status"] == "blocked_product_cli_status_set"
    assert payload["summary"]["product_cli_approval_token_count"] == 2
    assert payload["summary"]["product_cli_operations_blocked_stage_count"] == 4
    assert payload["summary"]["product_cli_capability_surface_ready"] is True
    assert payload["summary"]["product_cli_operational_quality_ready"] is True
    assert payload["summary"]["product_operational_quality_ready"] is True
    assert payload["summary"]["product_cli_architecture_release_ready"] is False
    assert payload["summary"]["product_cli_authorized_for_execution"] is False
    assert payload["summary"]["product_cli_delivery_ready_claim_allowed"] is False
    assert payload["summary"]["cameo_cli_status_set_status"] == "blocked_cameo_cli_status_set"
    assert payload["summary"]["cameo_cli_approval_token_count"] == 3
    assert payload["summary"]["cameo_cli_official_result_required"] is True
    assert payload["summary"]["cameo_cli_evidence_integrity_ready"] is True
    assert payload["summary"]["cameo_evidence_integrity_ready"] is True
    assert payload["summary"]["cameo_official_results_pending_honest"] is True
    assert payload["summary"]["cameo_no_local_native_accuracy_substitution"] is True
    assert payload["summary"]["cameo_cli_receiver_smoke_status"] == "blocked_cameo_receiver_smoke"
    assert payload["summary"]["cleanup_cli_status_set_status"] == "blocked_cleanup_cli_status_set"
    assert payload["summary"]["cleanup_cli_approval_token_count"] == 4
    assert payload["summary"]["cleanup_cli_approval_reclaim_size_gb"] == 49.216
    assert payload["summary"]["cleanup_cli_postcheck_contract_ready"] is True
    assert payload["summary"]["cleanup_cli_protected_payload_size_gb"] == 396.794
    assert payload["summary"]["cleanup_cli_protected_policy_change_required_count"] == 2
    assert rows["cameo_validation"]["lane_status"] == "blocked"
    assert rows["cameo_validation"]["repair_work_order_status"] == "operator_input_required"
    assert rows["cameo_validation"]["repair_operator_input_missing_count"] == 2
    assert rows["cameo_validation"]["operator_input_kit_status"] == "cameo_operator_input_kit_ready"
    assert rows["cameo_validation"]["operator_input_kit_template_count"] == 3
    assert rows["cameo_validation"]["operator_input_validation_status"] == "blocked_cameo_operator_input_validation"
    assert rows["cameo_validation"]["operator_input_validation_blocker_count"] == 3
    assert rows["cameo_validation"]["repair_execution_preflight_status"] == "blocked_cameo_repair_execution_preflight"
    assert rows["cameo_validation"]["repair_execution_preflight_blocker_count"] == 4
    assert rows["cameo_validation"]["capability_preflight_status"] == "cameo_development_capability_preflight_ready"
    assert rows["cameo_validation"]["public_registration_allowed"] is False
    assert rows["cameo_validation"]["public_registration_blocker_count"] == 4
    assert rows["cameo_validation"]["receiver_smoke_status"] == "cameo_receiver_smoke_ready"
    assert rows["cameo_validation"]["api_dependency_status"] == "cameo_api_dependency_ready"
    assert rows["cameo_validation"]["api_dependency_ready"] is True
    assert rows["cameo_validation"]["api_dependency_blocker_count"] == 0
    assert rows["cameo_validation"]["receiver_smoke_post_200_ok"] is True
    assert rows["cameo_validation"]["receiver_smoke_blocker_count"] == 0
    assert rows["commercial_product_execution"]["lane_status"] == "operator_approval_pending"
    assert rows["commercial_product_execution"]["delivery_evidence_status"] == "product_delivery_evidence_contract_ready"
    assert rows["commercial_product_execution"]["delivery_ready_claim_allowed"] is False
    assert rows["commercial_product_execution"]["delivery_evidence_warning_count"] == 2
    assert rows["commercial_product_execution"]["pilot_packet_status"] == "product_pilot_packet_preflight_ready"
    assert rows["commercial_product_execution"]["pilot_delivery_ready"] is False
    assert rows["commercial_product_execution"]["pilot_packet_warning_count"] == 2
    assert rows["product_architecture"]["lane_status"] == "blocked"
    assert rows["product_architecture"]["local_architecture_surface_ready"] is True
    assert rows["product_architecture"]["architecture_release_ready"] is False
    assert rows["product_architecture"]["architecture_approval_required_lane_count"] == 2
    assert rows["transition_cleanup"]["transition_cleanup_preflight_status"] == "transition_cleanup_execution_preflight_ready"
    assert rows["transition_cleanup"]["transition_cleanup_preflight_blocker_count"] == 0
    assert rows["ligand_heavy_cleanup"]["cleanup_execution_preflight_status"] == "ligand_heavy_cleanup_execution_preflight_ready"
    assert rows["ligand_heavy_cleanup"]["cleanup_execution_preflight_blocker_count"] == 0
    assert payload["summary"]["external_state_mutated"] is False


def test_goal_readiness_rollup_pending_when_no_blockers_but_approvals_required() -> None:
    payload = mod.build_rollup(
        product_readiness_packet=_product_readiness(),
        product_preflight_packet=_product_preflight(),
        product_delivery_evidence_packet=_product_delivery_evidence(),
        product_pilot_packet=_product_pilot_packet(),
        product_architecture_packet=_product_architecture(blocked_lane_count=0, approval_required_lane_count=2, release_ready=False),
        cameo_readiness_packet=_cameo("cameo_validation_evidence_ready", 0),
        transition_cleanup_packet=_transition_cleanup(),
        ligand_cleanup_packet=_ligand_cleanup(),
    )

    assert payload["summary"]["status"] == "goal_readiness_pending_operator_or_external_results"
    assert payload["summary"]["blocked_lane_count"] == 0
    assert payload["summary"]["evidence_ready_count"] == 1
    assert payload["summary"]["operator_approval_pending_count"] == 4


def test_goal_readiness_rollup_blocks_on_product_ai_architecture_backlog_when_supplied() -> None:
    payload = mod.build_rollup(
        product_readiness_packet=_product_readiness(),
        product_preflight_packet=_product_preflight(),
        product_delivery_evidence_packet=_product_delivery_evidence(),
        product_pilot_packet=_product_pilot_packet(),
        product_architecture_packet=_product_architecture(blocked_lane_count=0, approval_required_lane_count=0, release_ready=True),
        cameo_readiness_packet=_cameo("cameo_validation_evidence_ready", 0),
        transition_cleanup_packet=_transition_cleanup(),
        ligand_cleanup_packet=_ligand_cleanup(),
        product_ai_architecture_gap_packet=_blocked_product_ai_gap(),
        product_ai_execution_backlog_packet=_blocked_product_ai_backlog(),
    )

    rows = {row["lane_id"]: row for row in payload["rows"]}
    summary = payload["summary"]
    assert summary["status"] == "blocked_goal_readiness"
    assert summary["blocked_lane_count"] == 1
    assert summary["product_ai_architecture_gate_present"] is True
    assert summary["product_ai_architecture_ready"] is False
    assert summary["product_ai_architecture_open_gap_count"] == 1
    assert summary["product_ai_execution_backlog_work_item_count"] == 21
    assert summary["product_ai_execution_backlog_primary_work_item_id"] == "scope_breadth.transporter.AQP1.core_binder_01"
    assert rows["product_ai_architecture"]["lane_status"] == "blocked"
    assert rows["product_ai_architecture"]["blocker_count"] == 21
    assert "scope_breadth_expansion" in rows["product_ai_architecture"]["current_primary_open_gap"]
    assert "Close transporter/PXR scientific rows first." in rows["product_ai_architecture"]["next_required_step"]


def test_goal_readiness_rollup_accepts_product_ai_architecture_clear_when_supplied() -> None:
    payload = mod.build_rollup(
        product_readiness_packet=_product_readiness(),
        product_preflight_packet=_product_preflight(),
        product_delivery_evidence_packet=_product_delivery_evidence(),
        product_pilot_packet=_product_pilot_packet(),
        product_architecture_packet=_product_architecture(blocked_lane_count=0, approval_required_lane_count=0, release_ready=True),
        cameo_readiness_packet=_cameo("cameo_validation_evidence_ready", 0),
        transition_cleanup_packet=_transition_cleanup(),
        ligand_cleanup_packet=_ligand_cleanup(),
        product_ai_architecture_gap_packet=_ready_product_ai_gap(),
        product_ai_execution_backlog_packet=_ready_product_ai_backlog(),
    )

    rows = {row["lane_id"]: row for row in payload["rows"]}
    assert payload["summary"]["blocked_lane_count"] == 0
    assert payload["summary"]["product_ai_architecture_ready"] is True
    assert rows["product_ai_architecture"]["lane_status"] == "evidence_ready"


def test_goal_readiness_rollup_blocks_missing_product_preflight() -> None:
    payload = mod.build_rollup(
        product_readiness_packet=_product_readiness(),
        product_preflight_packet={},
        product_architecture_packet=_product_architecture(release_ready=True, blocked_lane_count=0, approval_required_lane_count=0),
        cameo_readiness_packet=_cameo("cameo_validation_evidence_ready", 0),
        transition_cleanup_packet=_transition_cleanup(),
        ligand_cleanup_packet=_ligand_cleanup(),
    )

    assert payload["summary"]["status"] == "blocked_goal_readiness"
    assert payload["rows"][0]["lane_status"] == "blocked_missing_artifact"


def test_goal_readiness_rollup_splits_release_complete_from_operator_pending() -> None:
    payload = mod.build_rollup(
        product_readiness_packet=_product_readiness(),
        product_preflight_packet=_product_preflight(),
        product_delivery_evidence_packet=_product_delivery_evidence(),
        product_pilot_packet=_product_pilot_packet(),
        product_architecture_packet=_product_architecture(
            blocked_lane_count=0,
            approval_required_lane_count=0,
            release_ready=True,
        ),
        cameo_readiness_packet=_cameo("cameo_validation_pending_official_results", 0),
        transition_cleanup_packet=_transition_cleanup(),
        ligand_cleanup_packet=_ligand_cleanup(),
        product_ai_architecture_gap_packet=_ready_product_ai_gap(),
        product_ai_execution_backlog_packet=_ready_product_ai_backlog(),
        goal_completion_audit_packet={"summary": {"goal_complete": True, "status": "product_goal_completion_audit_pass"}},
    )
    summary = payload["summary"]
    assert summary["goal_completion_audit_goal_complete"] is True
    assert summary["release_complete_lane_ready"] is True
    assert summary["operator_pending_lane_ready"] is False
    assert summary["status"] == "goal_readiness_release_complete_operator_pending"
    assert summary["release_complete_vs_operator_pending_lane"] == "release_complete_operator_pending_split"
    matrix = summary["release_complete_vs_operator_pending_matrix"]
    assert matrix[0]["lane"] == "release_complete"
    assert matrix[0]["ready"] is True
    assert matrix[1]["lane"] == "operator_or_external_pending"
    assert matrix[1]["ready"] is False


def test_goal_readiness_rollup_tool_writes_outputs(tmp_path: Path) -> None:
    paths = {
        "product_readiness": tmp_path / "product_readiness.json",
        "product_preflight": tmp_path / "product_preflight.json",
        "product_delivery_evidence": tmp_path / "product_delivery_evidence.json",
        "product_pilot_packet": tmp_path / "product_pilot_packet.json",
        "product_architecture": tmp_path / "product_architecture.json",
        "cameo": tmp_path / "cameo.json",
        "cameo_input_kit": tmp_path / "cameo_input_kit.json",
        "cameo_input_validation": tmp_path / "cameo_input_validation.json",
        "cameo_repair_preflight": tmp_path / "cameo_repair_preflight.json",
        "cameo_capability_preflight": tmp_path / "cameo_capability_preflight.json",
        "transition": tmp_path / "transition.json",
        "transition_preflight": tmp_path / "transition_preflight.json",
        "ligand": tmp_path / "ligand.json",
        "ligand_preflight": tmp_path / "ligand_preflight.json",
        "cleanup_postcheck": tmp_path / "cleanup_postcheck.json",
        "product_ai_gap": tmp_path / "product_ai_gap.json",
        "product_ai_backlog": tmp_path / "product_ai_backlog.json",
    }
    paths["product_readiness"].write_text(json.dumps(_product_readiness()) + "\n", encoding="utf-8")
    paths["product_preflight"].write_text(json.dumps(_product_preflight()) + "\n", encoding="utf-8")
    paths["product_delivery_evidence"].write_text(json.dumps(_product_delivery_evidence()) + "\n", encoding="utf-8")
    paths["product_pilot_packet"].write_text(json.dumps(_product_pilot_packet()) + "\n", encoding="utf-8")
    paths["product_architecture"].write_text(json.dumps(_product_architecture()) + "\n", encoding="utf-8")
    paths["cameo"].write_text(json.dumps(_cameo()) + "\n", encoding="utf-8")
    paths["cameo_input_kit"].write_text(json.dumps(_cameo_input_kit()) + "\n", encoding="utf-8")
    paths["cameo_input_validation"].write_text(json.dumps(_cameo_input_validation()) + "\n", encoding="utf-8")
    paths["cameo_repair_preflight"].write_text(json.dumps(_cameo_repair_preflight()) + "\n", encoding="utf-8")
    paths["cameo_capability_preflight"].write_text(json.dumps(_cameo_capability_preflight()) + "\n", encoding="utf-8")
    paths["transition"].write_text(json.dumps(_transition_cleanup()) + "\n", encoding="utf-8")
    paths["transition_preflight"].write_text(json.dumps(_transition_cleanup_preflight()) + "\n", encoding="utf-8")
    paths["ligand"].write_text(json.dumps(_ligand_cleanup()) + "\n", encoding="utf-8")
    paths["ligand_preflight"].write_text(json.dumps(_ligand_cleanup_preflight()) + "\n", encoding="utf-8")
    paths["cleanup_postcheck"].write_text(json.dumps(_cleanup_postcheck()) + "\n", encoding="utf-8")
    paths["product_ai_gap"].write_text(json.dumps(_ready_product_ai_gap()) + "\n", encoding="utf-8")
    paths["product_ai_backlog"].write_text(json.dumps(_ready_product_ai_backlog()) + "\n", encoding="utf-8")
    out_json = tmp_path / "rollup.json"
    out_csv = tmp_path / "rollup.csv"
    out_md = tmp_path / "rollup.md"

    mod.main(
        [
            "--product-readiness-json",
            str(paths["product_readiness"]),
            "--product-preflight-json",
            str(paths["product_preflight"]),
            "--product-delivery-evidence-json",
            str(paths["product_delivery_evidence"]),
            "--product-pilot-packet-json",
            str(paths["product_pilot_packet"]),
            "--product-architecture-json",
            str(paths["product_architecture"]),
            "--cameo-readiness-json",
            str(paths["cameo"]),
            "--cameo-input-kit-json",
            str(paths["cameo_input_kit"]),
            "--cameo-input-validation-json",
            str(paths["cameo_input_validation"]),
            "--cameo-repair-preflight-json",
            str(paths["cameo_repair_preflight"]),
            "--cameo-capability-preflight-json",
            str(paths["cameo_capability_preflight"]),
            "--transition-cleanup-json",
            str(paths["transition"]),
            "--transition-cleanup-preflight-json",
            str(paths["transition_preflight"]),
            "--ligand-cleanup-json",
            str(paths["ligand"]),
            "--ligand-cleanup-preflight-json",
            str(paths["ligand_preflight"]),
            "--cleanup-postcheck-json",
            str(paths["cleanup_postcheck"]),
            "--product-ai-architecture-gap-json",
            str(paths["product_ai_gap"]),
            "--product-ai-execution-backlog-json",
            str(paths["product_ai_backlog"]),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["status"] == "blocked_goal_readiness"
    assert out_csv.read_text(encoding="utf-8").startswith("lane_id,")
    assert "Goal Readiness Rollup" in out_md.read_text(encoding="utf-8")
