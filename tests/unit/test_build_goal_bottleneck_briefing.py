from __future__ import annotations

import json
from pathlib import Path

from tools import build_goal_bottleneck_briefing as mod


def _release_gate() -> dict:
    return {
        "summary": {
            "status": "blocked_goal_release_decision",
            "release_allowed": False,
            "blocker_count": 5,
            "check_count": 15,
            "cleanup_completion_transition_approval_gated_reclaim_size_gb": 43.206,
            "cleanup_completion_ligand_heavy_candidate_size_gb": 6.011,
            "protected_cleanup_payload_size_gb": 396.794,
        }
    }


def _burndown() -> dict:
    return {
        "summary": {
            "status": "goal_release_burndown_work_order_ready",
            "approval_reclaim_size_gb": 49.216,
        },
        "rows": [
            {
                "sequence": 1,
                "phase": "P1_product_execution_and_bundle_validation",
                "lane_id": "commercial_product_release",
                "burndown_status": "approval_required",
                "approval_token_required": "APPROVE_PRODUCT_DOCKING_EXECUTION",
                "release_checks": "product_architecture_release_ready;pilot_delivery_ready",
                "release_check_count": 2,
                "release_observed": "pilot_delivery_ready=false",
                "release_required": "pilot_delivery_ready=true",
                "requires_operator_action": True,
                "source_artifact": "runs/product_execution_work_order_current.json",
                "command": "python3 tools/run_ligand_htvs_pipeline.py --no-dry-run",
                "recommended_action": "Review and approve product execution.",
            },
            {
                "sequence": 3,
                "phase": "P2_cameo_official_validation_and_registration",
                "lane_id": "cameo_architecture_validation",
                "burndown_status": "official_results_required",
                "approval_token_required": "",
                "release_checks": "official_cameo_validation_evidence_ready;official_cameo_results_used",
                "release_check_count": 2,
                "release_observed": "official_cameo_results_used=false",
                "release_required": "official_cameo_results_used=true",
                "requires_operator_action": True,
                "source_artifact": "runs/cameo_official_results_intake_gate_current.json",
                "command": "python3 tools/build_cameo_official_results_intake_gate.py",
                "recommended_action": "Attach official CAMEO result rows.",
            },
            {
                "sequence": 6,
                "phase": "P3_cleanup_execution_or_policy_resolution",
                "lane_id": "cleanup_release",
                "burndown_status": "approval_required",
                "approval_token_required": "APPROVE_EXTERNALIZE_HEAVY_ARTIFACTS",
                "release_checks": "transition_cleanup_complete",
                "release_check_count": 1,
                "release_observed": "approval_awaiting=5",
                "release_required": "transition_cleanup_execution_complete",
                "requires_operator_action": True,
                "source_artifact": "runs/transition_cleanup_work_order_current.json",
                "command": "",
                "recommended_action": "Review transition cleanup approvals.",
            },
            {
                "sequence": 8,
                "phase": "P3_cleanup_execution_or_policy_resolution",
                "lane_id": "cleanup_release",
                "burndown_status": "policy_decision_required",
                "approval_token_required": "",
                "release_checks": "protected_cleanup_policy_resolved",
                "release_check_count": 1,
                "release_observed": "policy_resolved=false",
                "release_required": "policy_resolved=true",
                "requires_operator_action": True,
                "source_artifact": "runs/protected_cleanup_payload_review_current.json",
                "command": "",
                "recommended_action": "Review protected cleanup policy.",
            },
        ],
    }


def _action_board() -> dict:
    return {
        "summary": {
            "status": "operator_actions_required",
            "approval_reclaim_size_gb": 49.216,
        },
        "rows": [
            {
                "lane_id": "commercial_product_execution",
                "action_type": "review_product_execution_approval",
                "status": "approval_required",
                "approval_token": "APPROVE_PRODUCT_DOCKING_EXECUTION",
                "artifact_path": "runs/product_execution_work_order_current.json",
                "required_input": "",
                "size_gb": 0,
            },
            {
                "lane_id": "cameo_validation",
                "action_type": "fill_cameo_official_results_intake",
                "status": "required",
                "approval_token": "",
                "artifact_path": "runs/cameo_official_results_intake_gate_current.json",
                "required_input": "official CAMEO results operator intake CSV;runs/cameo_official_results_operator_intake.csv",
                "reason": "missing_required_columns=target_id;candidate_id;cameo_model_rank;blocker_codes=official_result_rows_missing",
                "size_gb": 0,
            },
            {
                "lane_id": "transition_cleanup",
                "action_type": "review_cleanup_approval_token",
                "status": "approval_required",
                "approval_token": "APPROVE_EXTERNALIZE_HEAVY_ARTIFACTS",
                "artifact_path": "runs/transition_cleanup_work_order_current.json",
                "required_input": "",
                "size_gb": 32.36,
            },
            {
                "lane_id": "ligand_heavy_cleanup",
                "action_type": "review_protected_ligand_heavy_policy",
                "status": "policy_decision_required",
                "approval_token": "",
                "artifact_path": "runs/protected_cleanup_payload_review_current.json",
                "required_input": "protected cleanup policy decision intake CSV",
                "size_gb": 396.794,
            },
        ],
    }


def _intake_kit() -> dict:
    return {
        "summary": {
            "status": "goal_operator_intake_kit_ready",
            "release_burndown_linked_entry_count": 4,
        },
        "rows": [
            {
                "kit_entry_id": "product_execution",
                "kit_status": "approval_required",
                "release_checks": "product_architecture_release_ready;pilot_delivery_ready",
                "action_types": "review_product_execution_approval",
                "operator_input_required": True,
                "approval_token_required": "APPROVE_PRODUCT_DOCKING_EXECUTION",
                "intake_path": "runs/product_execution_operator_approval_intake.csv",
                "source_artifacts": "runs/product_execution_work_order_current.json",
            },
            {
                "kit_entry_id": "cameo_official_results",
                "kit_status": "operator_input_required",
                "release_checks": "official_cameo_validation_evidence_ready;official_cameo_results_used",
                "action_types": "fill_cameo_official_results_intake",
                "operator_input_required": True,
                "approval_token_required": "",
                "intake_path": "runs/cameo_official_results_operator_intake.csv",
                "source_artifacts": "runs/cameo_official_results_intake_gate_current.json",
            },
            {
                "kit_entry_id": "cleanup_execution_approval",
                "kit_status": "approval_required",
                "release_checks": "transition_cleanup_complete;ligand_heavy_cleanup_complete",
                "action_types": "review_cleanup_approval_token;review_ligand_heavy_cleanup_approval",
                "operator_input_required": True,
                "approval_token_required": "APPROVE_EXTERNALIZE_HEAVY_ARTIFACTS;APPROVE_DELETE_STALE_LIGAND_HEAVY_PAYLOADS",
                "intake_path": "runs/cleanup_execution_operator_approval_intake.csv",
                "source_artifacts": "runs/transition_cleanup_work_order_current.json",
            },
            {
                "kit_entry_id": "protected_cleanup_policy",
                "kit_status": "policy_decision_required",
                "release_checks": "protected_cleanup_policy_resolved",
                "action_types": "review_protected_ligand_heavy_policy",
                "operator_input_required": True,
                "approval_token_required": "",
                "intake_path": "runs/protected_cleanup_policy_decision_intake.csv",
                "source_artifacts": "runs/protected_cleanup_payload_review_current.json",
            },
        ],
    }


def test_goal_bottleneck_briefing_links_release_blockers_to_intake_and_actions() -> None:
    payload = mod.build_goal_bottleneck_briefing(
        release_gate_packet=_release_gate(),
        burndown_packet=_burndown(),
        action_board_packet=_action_board(),
        intake_kit_packet=_intake_kit(),
    )

    summary = payload["summary"]
    by_sequence = {row["sequence"]: row for row in payload["rows"]}
    assert summary["status"] == "goal_bottleneck_briefing_ready"
    assert summary["release_allowed"] is False
    assert summary["source_release_blocker_count"] == 5
    assert summary["bottleneck_count"] == 4
    assert summary["approval_required_bottleneck_count"] == 2
    assert summary["official_results_required_bottleneck_count"] == 1
    assert summary["policy_decision_required_bottleneck_count"] == 1
    assert summary["approval_reclaim_size_gb"] == 49.216
    assert summary["cleanup_transition_approval_gated_reclaim_size_gb"] == 43.206
    assert summary["cleanup_ligand_heavy_candidate_size_gb"] == 6.011
    assert summary["protected_cleanup_payload_size_gb"] == 396.794
    assert summary["operator_intake_kit_release_burndown_linked_entry_count"] == 4
    assert summary["primary_bottleneck_sequence"] == 1
    assert "APPROVE_PRODUCT_DOCKING_EXECUTION" in summary["approval_tokens_required"]
    assert "APPROVE_EXTERNALIZE_HEAVY_ARTIFACTS" in summary["approval_tokens_required"]
    assert by_sequence[1]["bottleneck_kind"] == "operator_approval_required"
    assert by_sequence[1]["operator_intake_entries"] == "product_execution"
    assert by_sequence[1]["approval_token_required"] == "APPROVE_PRODUCT_DOCKING_EXECUTION"
    assert by_sequence[3]["bottleneck_kind"] == "official_cameo_results_missing"
    assert "runs/cameo_official_results_operator_intake.csv" in by_sequence[3]["required_inputs"]
    assert "missing_required_columns=target_id" in by_sequence[3]["operator_action_reasons"]
    assert "official_result_rows_missing" in by_sequence[3]["operator_action_reasons"]
    assert by_sequence[6]["size_gb"] == 32.36
    assert "APPROVE_DELETE_STALE_LIGAND_HEAVY_PAYLOADS" in by_sequence[6]["approval_token_required"]
    assert by_sequence[8]["bottleneck_kind"] == "protected_payload_policy_decision"
    assert "protected cleanup policy decision intake CSV" in by_sequence[8]["required_inputs"]
    assert summary["execution_enabled"] is False
    assert summary["delete_executed"] is False
    assert summary["external_state_mutated"] is False


def test_goal_bottleneck_briefing_filters_stale_intake_tokens_when_burndown_token_is_current() -> None:
    burndown = {
        "summary": {"status": "goal_release_burndown_work_order_ready"},
        "rows": [
            {
                "sequence": 4,
                "phase": "P2_cameo_official_validation_and_registration",
                "lane_id": "cameo_architecture_validation",
                "burndown_status": "approval_required",
                "approval_token_required": "APPROVE_CAMEO_SERVER_REGISTRATION;APPROVE_CAMEO_OUTBOUND_EMAIL",
                "release_checks": "cameo_public_registration_allowed",
                "release_check_count": 1,
                "release_observed": "public_registration_allowed=false",
                "release_required": "public_registration_allowed=true",
                "requires_operator_action": True,
                "source_artifact": "runs/cameo_capability_preflight_current.json",
                "command": "",
                "recommended_action": "Review registration/email approval.",
            }
        ],
    }
    intake = {
        "summary": {"status": "goal_operator_intake_kit_ready", "release_burndown_linked_entry_count": 2},
        "rows": [
            {
                "kit_entry_id": "cameo_api_dependency_install",
                "kit_status": "approval_required",
                "release_checks": "cameo_public_registration_allowed",
                "action_types": "repair_cameo_receiver_runtime_smoke",
                "operator_input_required": True,
                "approval_token_required": "APPROVE_API_DEPENDENCY_INSTALL",
                "source_artifacts": "runs/cameo_runtime_repair_work_order_current.json",
            },
            {
                "kit_entry_id": "cameo_public_registration",
                "kit_status": "approval_required",
                "release_checks": "cameo_public_registration_allowed",
                "action_types": "fill_cameo_public_registration_approval",
                "operator_input_required": True,
                "approval_token_required": "APPROVE_CAMEO_SERVER_REGISTRATION;APPROVE_CAMEO_OUTBOUND_EMAIL",
                "intake_path": "runs/cameo_public_registration_operator_approval_intake.csv",
                "source_artifacts": "runs/cameo_public_registration_approval_gate_current.json",
            },
        ],
    }

    payload = mod.build_goal_bottleneck_briefing(
        release_gate_packet=_release_gate(),
        burndown_packet=burndown,
        action_board_packet={"summary": {"status": "operator_actions_required"}, "rows": []},
        intake_kit_packet=intake,
    )

    row = payload["rows"][0]
    assert row["approval_token_required"] == "APPROVE_CAMEO_SERVER_REGISTRATION;APPROVE_CAMEO_OUTBOUND_EMAIL"
    assert row["operator_intake_entries"] == "cameo_public_registration"
    assert "APPROVE_API_DEPENDENCY_INSTALL" not in payload["summary"]["approval_tokens_required"]


def test_goal_bottleneck_briefing_does_not_attach_stale_tokens_to_blocked_until_rows() -> None:
    burndown = {
        "summary": {"status": "goal_release_burndown_work_order_ready"},
        "rows": [
            {
                "sequence": 1,
                "phase": "P1_product_execution_and_bundle_validation",
                "lane_id": "commercial_product_release",
                "burndown_status": "blocked_until_cameo_architecture_validation",
                "approval_token_required": "",
                "release_checks": "product_architecture_release_ready",
                "release_check_count": 1,
                "release_observed": "architecture_release_ready=false",
                "release_required": "architecture_release_ready=true",
                "requires_operator_action": True,
                "source_artifact": "runs/product_architecture_contract_current.json",
                "command": "",
                "recommended_action": "Clear CAMEO architecture validation.",
            }
        ],
    }
    action_board = {
        "summary": {"status": "operator_actions_required"},
        "rows": [
            {
                "lane_id": "commercial_product_execution",
                "action_type": "review_product_execution_approval",
                "status": "approval_required",
                "approval_token": "APPROVE_PRODUCT_DOCKING_EXECUTION",
                "artifact_path": "runs/product_execution_work_order_current.json",
            }
        ],
    }
    intake = {
        "summary": {"status": "goal_operator_intake_kit_ready"},
        "rows": [
            {
                "kit_entry_id": "product_execution",
                "kit_status": "approval_required",
                "release_checks": "product_architecture_release_ready",
                "action_types": "review_product_execution_approval",
                "operator_input_required": True,
                "approval_token_required": "APPROVE_PRODUCT_DOCKING_EXECUTION",
                "intake_path": "runs/product_execution_operator_approval_intake.csv",
                "source_artifacts": "runs/product_execution_work_order_current.json",
            }
        ],
    }

    payload = mod.build_goal_bottleneck_briefing(
        release_gate_packet=_release_gate(),
        burndown_packet=burndown,
        action_board_packet=action_board,
        intake_kit_packet=intake,
    )

    assert payload["summary"]["approval_tokens_required"] == []
    assert payload["rows"][0]["approval_token_required"] == ""
    assert payload["rows"][0]["operator_intake_entries"] == ""


def test_goal_bottleneck_briefing_zeroes_cleanup_sizes_when_cleanup_objective_ready() -> None:
    release = _release_gate()
    release["summary"] = {
        **release["summary"],
        "cleanup_objective_ready": True,
        "cleanup_completion_complete": True,
    }

    payload = mod.build_goal_bottleneck_briefing(
        release_gate_packet=release,
        burndown_packet=_burndown(),
        action_board_packet=_action_board(),
        intake_kit_packet=_intake_kit(),
    )

    summary = payload["summary"]
    assert summary["cleanup_transition_approval_gated_reclaim_size_gb"] == 0.0
    assert summary["cleanup_ligand_heavy_candidate_size_gb"] == 0.0
    assert "cleanup approvals/policy" not in summary["next_required_step"]


def test_goal_bottleneck_briefing_links_public_benchmark_work_order() -> None:
    burndown = {
        "summary": {"status": "goal_release_burndown_work_order_ready"},
        "rows": [
            {
                "sequence": 1,
                "phase": "P1_product_execution_and_bundle_validation",
                "lane_id": "commercial_product_release",
                "burndown_status": "blocked_until_public_benchmark_validation",
                "approval_token_required": "",
                "release_checks": "product_architecture_release_ready",
                "release_check_count": 1,
                "release_observed": "public_benchmark_ready=false",
                "release_required": "architecture_release_ready=true",
                "requires_operator_action": True,
                "source_artifact": "runs/product_pilot_packet_contract_current.json",
                "command": "python3 tools/build_product_public_benchmark_work_order.py",
                "recommended_action": "Run and attach public benchmark scorecards.",
            }
        ],
    }
    work_order = {
        "summary": {
            "status": "product_public_benchmark_work_order_ready",
            "open_suite_count": 5,
            "materialization_required_suite_count": 5,
            "scorecard_required_suite_count": 0,
        }
    }

    payload = mod.build_goal_bottleneck_briefing(
        release_gate_packet=_release_gate(),
        burndown_packet=burndown,
        action_board_packet={"summary": {"status": "operator_actions_required"}, "rows": []},
        intake_kit_packet={"summary": {"status": "goal_operator_intake_kit_ready"}, "rows": []},
        public_benchmark_work_order_packet=work_order,
    )

    summary = payload["summary"]
    row = payload["rows"][0]
    assert summary["public_benchmark_work_order_status"] == "product_public_benchmark_work_order_ready"
    assert summary["public_benchmark_open_suite_count"] == 5
    assert summary["public_benchmark_materialization_required_suite_count"] == 5
    assert row["bottleneck_kind"] == "blocked_until_public_benchmark_validation"
    assert row["public_benchmark_work_order_json"] == "runs/product_public_benchmark_work_order_current.json"
    assert row["public_benchmark_open_suite_count"] == 5
    assert "runs/product_public_benchmark_work_order_current.json" in row["source_artifacts"]


def test_goal_bottleneck_briefing_tool_writes_outputs(tmp_path: Path) -> None:
    release = tmp_path / "release.json"
    burndown = tmp_path / "burndown.json"
    actions = tmp_path / "actions.json"
    intake = tmp_path / "intake.json"
    release.write_text(json.dumps(_release_gate()) + "\n", encoding="utf-8")
    burndown.write_text(json.dumps(_burndown()) + "\n", encoding="utf-8")
    actions.write_text(json.dumps(_action_board()) + "\n", encoding="utf-8")
    intake.write_text(json.dumps(_intake_kit()) + "\n", encoding="utf-8")
    out_json = tmp_path / "bottlenecks.json"
    out_csv = tmp_path / "bottlenecks.csv"
    out_md = tmp_path / "bottlenecks.md"

    mod.main(
        [
            "--release-gate-json",
            str(release),
            "--burndown-json",
            str(burndown),
            "--action-board-json",
            str(actions),
            "--intake-kit-json",
            str(intake),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["status"] == "goal_bottleneck_briefing_ready"
    assert out_csv.read_text(encoding="utf-8").startswith("bottleneck_id,sequence,")
    assert "Goal Bottleneck Briefing" in out_md.read_text(encoding="utf-8")
