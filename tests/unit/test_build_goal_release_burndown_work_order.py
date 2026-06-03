from __future__ import annotations

import json
from pathlib import Path

from tools import build_goal_release_burndown_work_order as mod


def _release_gate_blocked() -> dict:
    return {
        "summary": {
            "status": "blocked_goal_release_decision",
            "release_allowed": False,
            "blocker_count": 5,
        },
        "rows": [
            {
                "lane_id": "commercial_product_release",
                "check": "bundle_validation_passed",
                "observed": "false",
                "required": "true",
                "release_blocker": True,
                "reason": "bundle validator must pass",
            },
            {
                "lane_id": "commercial_product_release",
                "check": "commercial_independence_gate_ready",
                "observed": "blocked_product_commercial_independence_gate;claim_allowed=false",
                "required": "product_commercial_independence_gate_ready",
                "artifact_path": "runs/product_commercial_independence_gate_current.json",
                "release_blocker": True,
                "reason": "commercial independence gate must pass",
            },
            {
                "lane_id": "cameo_architecture_validation",
                "check": "official_cameo_results_used",
                "observed": "false",
                "required": "true",
                "release_blocker": True,
                "reason": "official CAMEO rows required",
            },
            {
                "lane_id": "cameo_architecture_validation",
                "check": "cameo_public_registration_allowed",
                "observed": "false",
                "required": "true",
                "release_blocker": True,
                "reason": "public registration blocked",
            },
            {
                "lane_id": "cleanup_release",
                "check": "ligand_heavy_cleanup_complete",
                "observed": "ligand_heavy_cleanup_execution_preflight_ready",
                "required": "ligand_heavy_cleanup_execution_complete",
                "release_blocker": True,
                "reason": "ligand-heavy cleanup must complete",
            },
            {
                "lane_id": "goal_release",
                "check": "goal_readiness_rollup_ready",
                "observed": "blocked_goal_readiness",
                "required": "goal_readiness_ready",
                "release_blocker": True,
                "reason": "rollup must clear",
            },
        ],
    }


def _release_gate_ready() -> dict:
    return {"summary": {"status": "goal_release_ready", "release_allowed": True, "blocker_count": 0}, "rows": []}


def _release_gate_postcheck_blocked() -> dict:
    return {
        "summary": {
            "status": "blocked_goal_release_decision",
            "release_allowed": False,
            "blocker_count": 1,
        },
        "rows": [
            {
                "lane_id": "cleanup_release",
                "check": "cleanup_postcheck_contract_ready",
                "observed": "blocked_cleanup_postcheck_contract;ready=false;rows=7;blocked_rows=1",
                "required": "cleanup_postcheck_contract_ready;postcheck_contract_ready=true;blocked_row_count=0",
                "release_blocker": True,
                "reason": "postcheck contract must be ready",
            }
        ],
    }


def _release_gate_goal_api_surface_blocked() -> dict:
    return {
        "summary": {
            "status": "blocked_goal_release_decision",
            "release_allowed": False,
            "blocker_count": 1,
        },
        "rows": [
            {
                "lane_id": "goal_release",
                "check": "goal_api_surface_contract_ready",
                "observed": "blocked_goal_api_surface_contract;surface_ready=false;check_count=7;blocker_count=1;missing_endpoint_count=1",
                "required": "goal_api_surface_contract_ready;surface_ready=true;blocker_count=0",
                "artifact_path": "runs/goal_api_surface_contract_current.json",
                "release_blocker": True,
                "reason": "goal API surface contract must be ready",
            }
        ],
    }


def _operator_action_board() -> dict:
    return {
        "summary": {
            "status": "operator_actions_required",
            "action_count": 17,
            "approval_reclaim_size_gb": 49.216,
            "product_cli_status_set_status": "blocked_product_cli_status_set",
            "product_cli_approval_token_count": 2,
            "product_cli_operations_blocked_stage_count": 4,
            "product_cli_operational_quality_ready": True,
            "product_release_operations_operational_quality_ready": True,
            "product_release_operations_operational_quality_blocker_count": 0,
            "product_release_operations_source_operational_quality_status": "product_operational_quality_contract_ready",
            "product_cli_authorized_for_execution": False,
            "product_cli_bundle_validation_passed": False,
            "product_cli_delivery_ready_claim_allowed": False,
            "cameo_cli_status_set_status": "blocked_cameo_cli_status_set",
            "cameo_cli_approval_token_count": 3,
            "cameo_cli_official_result_required": True,
            "cameo_cli_evidence_integrity_ready": True,
            "cameo_cli_official_results_pending_honest": True,
            "cameo_cli_no_local_native_accuracy_substitution": True,
            "cameo_validation_operations_evidence_integrity_status": "cameo_evidence_integrity_contract_ready",
            "cameo_validation_operations_evidence_integrity_ready": True,
            "cameo_validation_operations_evidence_integrity_blocker_count": 0,
            "cameo_validation_operations_official_results_pending_honest": True,
            "cameo_validation_operations_no_local_native_accuracy_substitution": True,
            "cameo_cli_api_install_approval_required": True,
            "cameo_cli_receiver_smoke_status": "blocked_cameo_receiver_smoke",
            "cleanup_cli_status_set_status": "blocked_cleanup_cli_status_set",
            "cleanup_cli_approval_token_count": 4,
            "cleanup_cli_approval_reclaim_size_gb": 49.216,
            "cleanup_cli_postcheck_contract_ready": True,
            "cleanup_cli_protected_payload_size_gb": 396.794,
            "cleanup_cli_protected_policy_change_required_count": 2,
            "goal_operator_intake_kit_status": "goal_operator_intake_kit_ready",
            "goal_operator_intake_kit_json": "runs/goal_operator_intake_kit_current/manifest.json",
            "goal_operator_intake_kit_operator_input_required_count": 7,
            "goal_operator_intake_kit_release_burndown_linked_entry_count": 6,
            "goal_operator_intake_kit_current_action_required_count": 5,
            "goal_operator_intake_kit_deferred_operator_input_count": 2,
            "goal_operator_intake_kit_approval_token_count": 9,
            "goal_operator_intake_kit_current_action_approval_token_count": 7,
            "goal_operator_intake_kit_current_action_approval_tokens": [
                "APPROVE_API_DEPENDENCY_INSTALL",
                "APPROVE_ARCHIVE_LEGACY_RUNS",
                "APPROVE_DELETE_REGENERABLE_LOCAL_ARTIFACTS",
                "APPROVE_DELETE_STALE_LIGAND_HEAVY_PAYLOADS",
                "APPROVE_EXTERNALIZE_HEAVY_ARTIFACTS",
                "APPROVE_PRODUCT_DOCKING_EXECUTION",
                "APPROVE_PRODUCT_LICENSE_FILE_CREATION",
            ],
        },
        "rows": [
            {
                "lane_id": "commercial_product_license",
                "action_type": "fill_product_license_decision",
                "approval_token": "APPROVE_PRODUCT_LICENSE_FILE_CREATION",
                "status": "required",
            }
        ],
    }


def _operator_action_board_runtime_ready() -> dict:
    payload = _operator_action_board()
    payload["summary"] = {
        **payload["summary"],
        "cameo_cli_api_install_approval_required": False,
        "cameo_cli_receiver_smoke_status": "cameo_receiver_smoke_ready",
    }
    return payload


def _product_work_order() -> dict:
    return {
        "summary": {"status": "product_execution_work_order_ready", "approval_token_required": "APPROVE_PRODUCT_DOCKING_EXECUTION"},
        "rows": [{"step": "execution", "command": "python3 tools/run_ligand_htvs_pipeline.py --no-dry-run"}],
    }


def _cameo_validation_repair() -> dict:
    return {
        "summary": {"status": "operator_input_required"},
        "rows": [
            {"step": "selection", "command": "python3 tools/build_cameo_model1_selection_packet.py --candidates-csv OPERATOR_FILL"},
            {"step": "performance", "command": "python3 tools/build_cameo_performance_scorecard.py"},
        ],
    }


def _cameo_runtime_repair() -> dict:
    return {
        "summary": {"status": "cameo_runtime_repair_work_order_ready", "approval_token_required": "APPROVE_API_DEPENDENCY_INSTALL"},
        "rows": [{"step": "install_or_activate_api_dependency_profile", "command": "python3 -m pip install -r requirements-api.txt"}],
    }


def _cameo_capability() -> dict:
    return {
        "summary": {
            "status": "blocked_cameo_capability_preflight",
            "registration_approval_token_required": "APPROVE_CAMEO_SERVER_REGISTRATION",
            "outbound_email_approval_token_required": "APPROVE_CAMEO_OUTBOUND_EMAIL",
        }
    }


def _transition_cleanup() -> dict:
    return {"summary": {"status": "transition_cleanup_work_order_ready"}}


def _ligand_cleanup() -> dict:
    return {
        "summary": {"status": "cleanup_work_order_ready", "approval_token_required": "APPROVE_DELETE_STALE_LIGAND_HEAVY_PAYLOADS"},
        "rows": [{"step": "execute_after_approval", "command": "python3 tools/cleanup_ligand_heavy_runs.py --execute"}],
    }


def _protected_cleanup() -> dict:
    return {"summary": {"status": "protected_cleanup_payload_review_ready", "protected_payload_size_gb": 396.794}}


def _cleanup_postcheck() -> dict:
    return {
        "summary": {
            "status": "blocked_cleanup_postcheck_contract",
            "postcheck_contract_ready": False,
            "row_count": 7,
            "blocked_row_count": 1,
        }
    }


def test_goal_release_burndown_work_order_maps_blockers_to_phases_and_tokens() -> None:
    payload = mod.build_goal_release_burndown_work_order(
        release_gate_packet=_release_gate_blocked(),
        operator_action_board_packet=_operator_action_board(),
        product_work_order_packet=_product_work_order(),
        product_pilot_packet={},
        cameo_validation_repair_packet=_cameo_validation_repair(),
        cameo_runtime_repair_packet=_cameo_runtime_repair(),
        cameo_capability_packet=_cameo_capability(),
        transition_cleanup_work_order_packet=_transition_cleanup(),
        ligand_cleanup_work_order_packet=_ligand_cleanup(),
        protected_cleanup_review_packet=_protected_cleanup(),
    )

    summary = payload["summary"]
    assert summary["status"] == "goal_release_burndown_work_order_ready"
    assert summary["work_item_count"] == 6
    assert summary["approval_required_item_count"] == 4
    assert summary["operator_input_required_item_count"] == 5
    assert summary["burndown_operator_input_required_work_item_count"] == 0
    assert summary["goal_operator_intake_kit_status"] == "goal_operator_intake_kit_ready"
    assert summary["goal_operator_intake_kit_json"] == "runs/goal_operator_intake_kit_current/manifest.json"
    assert summary["goal_operator_intake_kit_operator_input_required_count"] == 7
    assert summary["goal_operator_intake_kit_release_burndown_linked_entry_count"] == 6
    assert summary["goal_operator_intake_kit_current_action_required_count"] == 5
    assert summary["goal_operator_intake_kit_deferred_operator_input_count"] == 2
    assert summary["goal_operator_intake_kit_approval_token_count"] == 9
    assert summary["goal_operator_intake_kit_current_action_approval_token_count"] == 7
    assert "APPROVE_PRODUCT_DOCKING_EXECUTION" in summary["goal_operator_intake_kit_current_action_approval_tokens"]
    assert summary["official_results_required_item_count"] == 1
    assert summary["postcheck_required_item_count"] == 0
    assert summary["operator_action_count"] == 17
    assert summary["product_cli_status_set_status"] == "blocked_product_cli_status_set"
    assert summary["product_cli_approval_token_count"] == 2
    assert summary["product_cli_operations_blocked_stage_count"] == 4
    assert summary["product_cli_operational_quality_ready"] is True
    assert summary["product_operational_quality_ready"] is True
    assert summary["product_operational_quality_status"] == "product_operational_quality_contract_ready"
    assert summary["product_operational_quality_blocker_count"] == 0
    assert summary["product_cli_authorized_for_execution"] is False
    assert summary["product_cli_bundle_validation_passed"] is False
    assert summary["product_cli_delivery_ready_claim_allowed"] is False
    assert summary["cameo_cli_status_set_status"] == "blocked_cameo_cli_status_set"
    assert summary["cameo_cli_approval_token_count"] == 3
    assert summary["cameo_cli_official_result_required"] is True
    assert summary["cameo_cli_evidence_integrity_ready"] is True
    assert summary["cameo_evidence_integrity_ready"] is True
    assert summary["cameo_evidence_integrity_status"] == "cameo_evidence_integrity_contract_ready"
    assert summary["cameo_evidence_integrity_blocker_count"] == 0
    assert summary["cameo_official_results_pending_honest"] is True
    assert summary["cameo_no_local_native_accuracy_substitution"] is True
    assert summary["cameo_cli_receiver_smoke_status"] == "blocked_cameo_receiver_smoke"
    assert summary["cleanup_cli_status_set_status"] == "blocked_cleanup_cli_status_set"
    assert summary["cleanup_cli_approval_token_count"] == 4
    assert summary["cleanup_cli_approval_reclaim_size_gb"] == 49.216
    assert summary["cleanup_cli_postcheck_contract_ready"] is True
    assert summary["cleanup_cli_protected_payload_size_gb"] == 396.794
    assert summary["cleanup_cli_protected_policy_change_required_count"] == 2
    assert "APPROVE_PRODUCT_DOCKING_EXECUTION" in summary["approval_tokens_required"]
    assert "APPROVE_PRODUCT_LICENSE_FILE_CREATION" in summary["approval_tokens_required"]
    assert "APPROVE_API_DEPENDENCY_INSTALL" in summary["approval_tokens_required"]
    assert "APPROVE_DELETE_STALE_LIGAND_HEAVY_PAYLOADS" in summary["approval_tokens_required"]
    assert all(";" not in token for token in summary["approval_tokens_required"])
    assert summary["execution_enabled"] is False
    assert summary["delete_executed"] is False
    assert summary["external_state_mutated"] is False
    assert any(row["phase"] == "P1_product_execution_and_bundle_validation" for row in payload["rows"])
    assert any(row["phase"] == "P1_product_commercial_independence" for row in payload["rows"])
    assert any(row["phase"] == "P2_cameo_official_validation_and_registration" for row in payload["rows"])
    cameo_rows = [row for row in payload["rows"] if row["phase"] == "P2_cameo_official_validation_and_registration"]
    assert any(row["burndown_status"] == "official_results_required" for row in cameo_rows)
    assert any("build_cameo_official_results_intake_gate.py" in row["command"] for row in cameo_rows)
    assert any(row["phase"] == "P3_cleanup_execution_or_policy_resolution" for row in payload["rows"])
    assert any(row["phase"] == "P4_refresh_release_evidence" for row in payload["rows"])


def test_goal_release_burndown_work_order_maps_cleanup_postcheck_blocker() -> None:
    payload = mod.build_goal_release_burndown_work_order(
        release_gate_packet=_release_gate_postcheck_blocked(),
        operator_action_board_packet=_operator_action_board(),
        product_work_order_packet={},
        product_pilot_packet={},
        cameo_validation_repair_packet={},
        cameo_runtime_repair_packet={},
        cameo_capability_packet={},
        transition_cleanup_work_order_packet=_transition_cleanup(),
        ligand_cleanup_work_order_packet=_ligand_cleanup(),
        protected_cleanup_review_packet=_protected_cleanup(),
        cleanup_postcheck_contract_packet=_cleanup_postcheck(),
    )

    summary = payload["summary"]
    assert summary["status"] == "goal_release_burndown_work_order_ready"
    assert summary["postcheck_required_item_count"] == 1
    assert summary["cleanup_postcheck_contract_status"] == "blocked_cleanup_postcheck_contract"
    assert summary["cleanup_postcheck_contract_ready"] is False
    assert summary["cleanup_postcheck_blocked_row_count"] == 1
    row = payload["rows"][0]
    assert row["burndown_status"] == "postcheck_required"
    assert row["source_artifact"] == "runs/cleanup_postcheck_contract_current.json"
    assert "build_cleanup_postcheck_contract.py" in row["command"]


def test_goal_release_burndown_work_order_maps_goal_api_surface_contract_blocker() -> None:
    payload = mod.build_goal_release_burndown_work_order(
        release_gate_packet=_release_gate_goal_api_surface_blocked(),
        operator_action_board_packet=_operator_action_board(),
        product_work_order_packet={},
        product_pilot_packet={},
        cameo_validation_repair_packet={},
        cameo_runtime_repair_packet={},
        cameo_capability_packet={},
        transition_cleanup_work_order_packet=_transition_cleanup(),
        ligand_cleanup_work_order_packet=_ligand_cleanup(),
        protected_cleanup_review_packet=_protected_cleanup(),
    )

    summary = payload["summary"]
    assert summary["status"] == "goal_release_burndown_work_order_ready"
    assert summary["work_item_count"] == 1
    row = payload["rows"][0]
    assert row["phase"] == "P4_refresh_release_evidence"
    assert row["release_check"] == "goal_api_surface_contract_ready"
    assert row["burndown_status"] == "api_contract_refresh_required"
    assert row["source_artifact"] == "runs/goal_release_decision_gate_current.json;runs/goal_api_surface_contract_current.json"
    assert "build_goal_api_surface_contract.py" in row["command"]
    assert "build_goal_release_decision_gate.py" in row["command"]


def test_goal_release_burndown_work_order_merges_duplicate_operator_work_items() -> None:
    release_gate = {
        "summary": {"status": "blocked_goal_release_decision", "release_allowed": False, "blocker_count": 4},
        "rows": [
            {
                "lane_id": "commercial_product_release",
                "check": "pilot_delivery_ready",
                "observed": "false",
                "required": "true",
                "release_blocker": True,
                "reason": "pilot must be ready",
            },
            {
                "lane_id": "commercial_product_release",
                "check": "bundle_validation_passed",
                "observed": "false",
                "required": "true",
                "release_blocker": True,
                "reason": "bundle validator must pass",
            },
            {
                "lane_id": "cameo_architecture_validation",
                "check": "official_cameo_validation_evidence_ready",
                "observed": "cameo_validation_pending_official_results",
                "required": "cameo_validation_evidence_ready",
                "release_blocker": True,
                "reason": "official evidence required",
            },
            {
                "lane_id": "cameo_architecture_validation",
                "check": "official_cameo_results_used",
                "observed": "false",
                "required": "true",
                "release_blocker": True,
                "reason": "official rows required",
            },
        ],
    }

    payload = mod.build_goal_release_burndown_work_order(
        release_gate_packet=release_gate,
        operator_action_board_packet=_operator_action_board(),
        product_work_order_packet=_product_work_order(),
        product_pilot_packet={},
        cameo_validation_repair_packet=_cameo_validation_repair(),
        cameo_runtime_repair_packet=_cameo_runtime_repair(),
        cameo_capability_packet=_cameo_capability(),
        transition_cleanup_work_order_packet=_transition_cleanup(),
        ligand_cleanup_work_order_packet=_ligand_cleanup(),
        protected_cleanup_review_packet=_protected_cleanup(),
    )

    summary = payload["summary"]
    assert summary["release_blocker_check_count"] == 4
    assert summary["work_item_count"] == 2
    assert summary["approval_required_item_count"] == 1
    assert summary["official_results_required_item_count"] == 1
    assert summary["operator_input_required_item_count"] == 5
    assert summary["burndown_operator_input_required_work_item_count"] == 0
    assert all(row["release_check_count"] == 2 for row in payload["rows"])
    assert any("pilot_delivery_ready;bundle_validation_passed" in row["release_checks"] for row in payload["rows"])
    assert any("official_cameo_validation_evidence_ready;official_cameo_results_used" in row["release_checks"] for row in payload["rows"])


def test_goal_release_burndown_work_order_uses_registration_tokens_when_runtime_ready() -> None:
    release_gate = {
        "summary": {"status": "blocked_goal_release_decision", "release_allowed": False, "blocker_count": 1},
        "rows": [
            {
                "lane_id": "cameo_architecture_validation",
                "check": "cameo_public_registration_allowed",
                "observed": "false",
                "required": "true",
                "release_blocker": True,
                "reason": "public registration blocked",
            }
        ],
    }

    payload = mod.build_goal_release_burndown_work_order(
        release_gate_packet=release_gate,
        operator_action_board_packet=_operator_action_board_runtime_ready(),
        product_work_order_packet={},
        product_pilot_packet={},
        cameo_validation_repair_packet=_cameo_validation_repair(),
        cameo_runtime_repair_packet=_cameo_runtime_repair(),
        cameo_capability_packet=_cameo_capability(),
        transition_cleanup_work_order_packet=_transition_cleanup(),
        ligand_cleanup_work_order_packet=_ligand_cleanup(),
        protected_cleanup_review_packet=_protected_cleanup(),
    )

    row = payload["rows"][0]
    assert row["approval_token_required"] == "APPROVE_CAMEO_SERVER_REGISTRATION;APPROVE_CAMEO_OUTBOUND_EMAIL"
    assert row["command"] == ""
    assert "APPROVE_API_DEPENDENCY_INSTALL" not in payload["summary"]["approval_tokens_required"]
    assert payload["summary"]["approval_tokens_required"] == [
        "APPROVE_CAMEO_OUTBOUND_EMAIL",
        "APPROVE_CAMEO_SERVER_REGISTRATION",
    ]
    assert payload["summary"]["approval_token_count"] == 2


def test_goal_release_burndown_next_step_omits_runtime_and_cleanup_when_not_work_items() -> None:
    release_gate = {
        "summary": {"status": "blocked_goal_release_decision", "release_allowed": False, "blocker_count": 4},
        "rows": [
            {
                "lane_id": "commercial_product_release",
                "check": "bundle_validation_passed",
                "observed": "false",
                "required": "true",
                "release_blocker": True,
                "reason": "bundle validator must pass",
            },
            {
                "lane_id": "commercial_product_release",
                "check": "commercial_independence_gate_ready",
                "observed": "blocked_product_commercial_independence_gate;claim_allowed=false",
                "required": "product_commercial_independence_gate_ready",
                "artifact_path": "runs/product_commercial_independence_gate_current.json",
                "release_blocker": True,
                "reason": "commercial independence gate must pass",
            },
            {
                "lane_id": "cameo_architecture_validation",
                "check": "official_cameo_results_used",
                "observed": "false",
                "required": "true",
                "release_blocker": True,
                "reason": "official CAMEO rows required",
            },
            {
                "lane_id": "cameo_architecture_validation",
                "check": "cameo_public_registration_allowed",
                "observed": "false",
                "required": "true",
                "release_blocker": True,
                "reason": "public registration blocked",
            },
            {
                "lane_id": "goal_release",
                "check": "goal_readiness_rollup_ready",
                "observed": "blocked_goal_readiness",
                "required": "goal_readiness_ready",
                "release_blocker": True,
                "reason": "rollup must clear",
            },
        ],
    }

    payload = mod.build_goal_release_burndown_work_order(
        release_gate_packet=release_gate,
        operator_action_board_packet=_operator_action_board_runtime_ready(),
        product_work_order_packet=_product_work_order(),
        product_pilot_packet={},
        cameo_validation_repair_packet=_cameo_validation_repair(),
        cameo_runtime_repair_packet=_cameo_runtime_repair(),
        cameo_capability_packet=_cameo_capability(),
        transition_cleanup_work_order_packet=_transition_cleanup(),
        ligand_cleanup_work_order_packet=_ligand_cleanup(),
        protected_cleanup_review_packet=_protected_cleanup(),
    )

    next_step = payload["summary"]["next_required_step"]
    assert "P1 product execution/bundle validation" in next_step
    assert "P1 commercial license/independence" in next_step
    assert "P2 official CAMEO evidence" in next_step
    assert "P2 CAMEO registration/email approval" in next_step
    assert "P2 CAMEO runtime repair" not in next_step
    assert "P3 cleanup" not in next_step
    assert "P4 release evidence refresh" in next_step
    assert not next_step.endswith("then refresh release evidence.")
    refresh_row = next(row for row in payload["rows"] if row["phase"] == "P4_refresh_release_evidence")
    assert refresh_row["recommended_action"] == (
        "After prior blocking phases are cleared, refresh goal rollup, action board, release gate, and this burndown work order."
    )


def test_goal_release_burndown_work_order_clears_when_release_gate_has_no_blockers() -> None:
    payload = mod.build_goal_release_burndown_work_order(
        release_gate_packet=_release_gate_ready(),
        operator_action_board_packet={"summary": {"action_count": 0}},
        product_work_order_packet={},
        product_pilot_packet={},
        cameo_validation_repair_packet={},
        cameo_runtime_repair_packet={},
        cameo_capability_packet={},
        transition_cleanup_work_order_packet={},
        ligand_cleanup_work_order_packet={},
        protected_cleanup_review_packet={},
    )

    assert payload["summary"]["status"] == "goal_release_burndown_clear"
    assert payload["summary"]["work_item_count"] == 0
    assert payload["rows"] == []


def test_goal_release_burndown_work_order_tool_writes_outputs(tmp_path: Path) -> None:
    paths = {
        "release_gate": tmp_path / "release_gate.json",
        "operator_action_board": tmp_path / "operator_action_board.json",
        "product_work_order": tmp_path / "product_work_order.json",
        "cameo_validation_repair": tmp_path / "cameo_validation_repair.json",
        "cameo_runtime_repair": tmp_path / "cameo_runtime_repair.json",
        "cameo_capability": tmp_path / "cameo_capability.json",
        "transition_cleanup": tmp_path / "transition_cleanup.json",
        "ligand_cleanup": tmp_path / "ligand_cleanup.json",
        "protected_cleanup": tmp_path / "protected_cleanup.json",
    }
    paths["release_gate"].write_text(json.dumps(_release_gate_blocked()) + "\n", encoding="utf-8")
    paths["operator_action_board"].write_text(json.dumps(_operator_action_board()) + "\n", encoding="utf-8")
    paths["product_work_order"].write_text(json.dumps(_product_work_order()) + "\n", encoding="utf-8")
    paths["cameo_validation_repair"].write_text(json.dumps(_cameo_validation_repair()) + "\n", encoding="utf-8")
    paths["cameo_runtime_repair"].write_text(json.dumps(_cameo_runtime_repair()) + "\n", encoding="utf-8")
    paths["cameo_capability"].write_text(json.dumps(_cameo_capability()) + "\n", encoding="utf-8")
    paths["transition_cleanup"].write_text(json.dumps(_transition_cleanup()) + "\n", encoding="utf-8")
    paths["ligand_cleanup"].write_text(json.dumps(_ligand_cleanup()) + "\n", encoding="utf-8")
    paths["protected_cleanup"].write_text(json.dumps(_protected_cleanup()) + "\n", encoding="utf-8")
    out_json = tmp_path / "burndown.json"
    out_csv = tmp_path / "burndown.csv"
    out_md = tmp_path / "burndown.md"

    mod.main(
        [
            "--release-gate-json",
            str(paths["release_gate"]),
            "--operator-action-board-json",
            str(paths["operator_action_board"]),
            "--product-work-order-json",
            str(paths["product_work_order"]),
            "--cameo-validation-repair-json",
            str(paths["cameo_validation_repair"]),
            "--cameo-runtime-repair-json",
            str(paths["cameo_runtime_repair"]),
            "--cameo-capability-json",
            str(paths["cameo_capability"]),
            "--transition-cleanup-work-order-json",
            str(paths["transition_cleanup"]),
            "--ligand-cleanup-work-order-json",
            str(paths["ligand_cleanup"]),
            "--protected-cleanup-review-json",
            str(paths["protected_cleanup"]),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["status"] == "goal_release_burndown_work_order_ready"
    assert out_csv.read_text(encoding="utf-8").startswith("sequence,phase,")
    assert "Goal Release Burndown Work Order" in out_md.read_text(encoding="utf-8")
