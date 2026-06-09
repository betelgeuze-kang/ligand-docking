from __future__ import annotations

import json
from pathlib import Path

from betelgeuze_product import cli


def _write_packet(root: Path, rel_path: str, status: str, *, extra_summary: dict | None = None) -> None:
    path = root / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    summary = {
        "status": status,
        "blocker_count": 0,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
    }
    summary.update(extra_summary or {})
    path.write_text(
        json.dumps(
            {
                "summary": summary,
                "rows": [{"status": "ready"}],
            }
        )
        + "\n",
        encoding="utf-8",
    )


def test_product_cli_reads_local_status_artifact_without_execution(tmp_path: Path) -> None:
    _write_packet(tmp_path, cli.ARTIFACTS["capabilities"], "product_capability_surface_contract_ready")

    payload = cli.build_cli_status("capabilities", root=tmp_path)

    assert payload["status"] == "product_capability_surface_contract_ready"
    assert payload["artifact_present"] is True
    assert payload["row_count"] == 1
    assert payload["blocker_count"] == 0
    assert payload["execution_enabled"] is False
    assert payload["docking_results_emitted"] is False
    assert payload["license_file_written"] is False
    assert payload["bundle_assembled"] is False
    assert payload["external_state_mutated"] is False


def test_product_cli_blocks_missing_artifact_without_mutation(tmp_path: Path) -> None:
    payload = cli.build_cli_status("architecture", root=tmp_path)

    assert payload["status"] == "missing_architecture_artifact"
    assert payload["artifact_present"] is False
    assert payload["blocker_count"] == 1
    assert payload["execution_enabled"] is False
    assert payload["external_state_mutated"] is False


def test_product_cli_main_prints_json(tmp_path: Path, capsys) -> None:
    _write_packet(tmp_path, cli.ARTIFACTS["commercial-independence"], "product_commercial_independence_gate_ready")

    assert cli.main(["commercial-independence", "--root", str(tmp_path)]) == 0
    output = json.loads(capsys.readouterr().out)

    assert output["command"] == "commercial-independence"
    assert output["status"] == "product_commercial_independence_gate_ready"
    assert output["execution_enabled"] is False


def test_product_cli_reads_goal_completion_audit_status(tmp_path: Path) -> None:
    _write_packet(
        tmp_path,
        cli.ARTIFACTS["goal-completion-audit"],
        "blocked_product_goal_completion_audit",
        extra_summary={
            "goal_complete": False,
            "pass_count": 3,
            "fail_count": 2,
            "primary_bottleneck_phase": "P1_product_commercial_independence",
            "approval_tokens_required": ["APPROVE_PRODUCT_LICENSE_FILE_CREATION"],
            "next_command": "python3 tools/fill_product_license_decision_operator_intake.py --approval-token APPROVE_PRODUCT_LICENSE_FILE_CREATION",
            "next_command_candidate_count": 1,
            "next_command_candidates": [
                "python3 tools/fill_product_license_decision_operator_intake.py --spdx-license-id Apache-2.0"
            ],
        },
    )

    payload = cli.build_cli_status("goal-completion-audit", root=tmp_path)

    assert payload["status"] == "blocked_product_goal_completion_audit"
    assert payload["summary"]["goal_complete"] is False
    assert payload["summary"]["primary_bottleneck_phase"] == "P1_product_commercial_independence"
    assert payload["summary"]["next_command_candidate_count"] == 1
    assert payload["execution_enabled"] is False
    assert payload["external_state_mutated"] is False


def test_product_cli_reads_scope_evidence_priority_status(tmp_path: Path) -> None:
    _write_packet(
        tmp_path,
        cli.ARTIFACTS["scope-evidence-priority"],
        "product_scope_breadth_evidence_priority_packet_ready",
        extra_summary={
            "priority_packet_ready": True,
            "scope_promotion_allowed": False,
            "queue_item_count": 21,
        },
    )

    payload = cli.build_cli_status("scope-evidence-priority", root=tmp_path)

    assert payload["status"] == "product_scope_breadth_evidence_priority_packet_ready"
    assert payload["artifact_present"] is True
    assert payload["execution_enabled"] is False


def test_product_cli_reads_scope_review_workbench_statuses(tmp_path: Path) -> None:
    _write_packet(
        tmp_path,
        cli.ARTIFACTS["scope-evidence-intake-readiness"],
        "product_scope_breadth_evidence_intake_readiness_ready",
        extra_summary={"intake_readiness_ready": True, "row_count": 21},
    )
    _write_packet(
        tmp_path,
        cli.ARTIFACTS["transporter-manual-review-intake"],
        "transporter_manual_review_intake_template_ready",
        extra_summary={"manual_review_intake_ready": True, "manual_review_template_row_count": 11},
    )
    _write_packet(
        tmp_path,
        cli.ARTIFACTS["pxr-exact-review-intake"],
        "pxr_exact_evidence_review_intake_template_ready",
        extra_summary={"pxr_exact_review_intake_ready": True, "review_template_row_count": 6},
    )

    intake = cli.build_cli_status("scope-evidence-intake-readiness", root=tmp_path)
    transporter = cli.build_cli_status("transporter-manual-review-intake", root=tmp_path)
    pxr = cli.build_cli_status("pxr-exact-review-intake", root=tmp_path)

    assert intake["summary"]["row_count"] == 21
    assert transporter["summary"]["manual_review_template_row_count"] == 11
    assert pxr["summary"]["review_template_row_count"] == 6
    assert intake["external_state_mutated"] is False
    assert transporter["execution_enabled"] is False
    assert pxr["docking_results_emitted"] is False


def test_product_cli_reads_production_ai_promotion_workbench_status(tmp_path: Path) -> None:
    _write_packet(
        tmp_path,
        cli.ARTIFACTS["production-ai-promotion-workbench"],
        "blocked_product_production_ai_promotion_workbench",
        extra_summary={
            "promotion_workbench_ready": True,
            "production_ai_promotion_ready": False,
            "first_blocked_stage_id": "gpu_return_receipt",
        },
    )

    payload = cli.build_cli_status("production-ai-promotion-workbench", root=tmp_path)

    assert payload["status"] == "blocked_product_production_ai_promotion_workbench"
    assert payload["summary"]["promotion_workbench_ready"] is True
    assert payload["summary"]["first_blocked_stage_id"] == "gpu_return_receipt"
    assert payload["execution_enabled"] is False
    assert payload["external_state_mutated"] is False


def test_product_cli_reads_production_ai_gpu_return_intake_status(tmp_path: Path) -> None:
    _write_packet(
        tmp_path,
        cli.ARTIFACTS["production-ai-gpu-return-intake"],
        "blocked_product_production_ai_gpu_return_intake",
        extra_summary={
            "gpu_return_intake_ready": True,
            "gpu_return_artifacts_ready": False,
            "failed_check_ids": ["actual_summary_returned_complete"],
        },
    )

    payload = cli.build_cli_status("production-ai-gpu-return-intake", root=tmp_path)

    assert payload["status"] == "blocked_product_production_ai_gpu_return_intake"
    assert payload["summary"]["gpu_return_intake_ready"] is True
    assert payload["summary"]["gpu_return_artifacts_ready"] is False
    assert payload["execution_enabled"] is False
    assert payload["external_state_mutated"] is False


def test_product_cli_reads_public_benchmark_work_order_status(tmp_path: Path) -> None:
    _write_packet(
        tmp_path,
        cli.ARTIFACTS["public-benchmark"],
        "product_public_benchmark_work_order_ready",
        extra_summary={
            "public_benchmark_validation_ready": False,
            "open_suite_count": 5,
            "materialization_required_suite_count": 5,
            "scorecard_required_suite_count": 0,
            "continuous_validation_command_count": 5,
            "suite_run_command_count": 5,
            "suite_materialization_run_command_count": 5,
            "suite_scorecard_command_count": 5,
            "suite_result_provenance_command_count": 5,
            "suite_result_provenance_present_count": 0,
            "suite_threshold_count": 5,
            "suite_blocker_count": 5,
            "suite_materialization_manifest_count": 5,
            "suite_scorecard_row_csv_count": 5,
            "suite_required_output_count": 5,
            "suite_no_external_dependency_count": 5,
            "local_artifact_preflight_ready_suite_count": 0,
            "local_artifact_preflight_blocked_suite_count": 5,
            "missing_local_input_artifact_count": 8,
            "missing_local_output_artifact_count": 6,
        },
    )

    payload = cli.build_cli_status("public-benchmark", root=tmp_path)

    assert payload["status"] == "product_public_benchmark_work_order_ready"
    assert payload["artifact_present"] is True
    assert payload["summary"]["open_suite_count"] == 5
    assert payload["summary"]["suite_run_command_count"] == 5
    assert payload["execution_enabled"] is False
    assert payload["external_state_mutated"] is False


def test_product_cli_reads_ai_report_and_decision_graph_status(tmp_path: Path) -> None:
    _write_packet(
        tmp_path,
        cli.ARTIFACTS["ai-decision-graph"],
        "product_ai_decision_graph_contract_ready",
        extra_summary={"closed_loop_decision_graph_ready": True, "node_count": 7},
    )
    _write_packet(
        tmp_path,
        cli.ARTIFACTS["ai-report-ux"],
        "product_ai_report_ux_contract_ready",
        extra_summary={"ai_report_ux_ready": True, "section_count": 7},
    )

    graph = cli.build_cli_status("ai-decision-graph", root=tmp_path)
    report = cli.build_cli_status("ai-report-ux", root=tmp_path)

    assert graph["status"] == "product_ai_decision_graph_contract_ready"
    assert graph["summary"]["closed_loop_decision_graph_ready"] is True
    assert report["status"] == "product_ai_report_ux_contract_ready"
    assert report["summary"]["ai_report_ux_ready"] is True
    assert graph["external_state_mutated"] is False
    assert report["execution_enabled"] is False


def test_product_cli_reads_cameo_live_validation_without_release_token_rollup(tmp_path: Path) -> None:
    _write_packet(
        tmp_path,
        cli.ARTIFACTS["cameo-live-validation"],
        "blocked_cameo_validation_operations_dossier",
        extra_summary={
            "validation_ready": False,
            "official_result_required": True,
            "official_results_intake_ready": False,
            "public_registration_allowed": False,
            "approval_tokens_required": [
                "APPROVE_CAMEO_OUTBOUND_EMAIL",
                "APPROVE_CAMEO_SERVER_REGISTRATION",
            ],
        },
    )

    payload = cli.build_cli_status("cameo-live-validation", root=tmp_path)

    assert payload["status"] == "blocked_cameo_validation_operations_dossier"
    assert payload["summary"]["official_result_required"] is True
    assert payload["execution_enabled"] is False
    assert payload["external_state_mutated"] is False


def test_product_cli_all_rolls_up_public_benchmark_suite_evidence_counts(tmp_path: Path) -> None:
    _write_packet(tmp_path, cli.ARTIFACTS["capabilities"], "product_capability_surface_contract_ready")
    _write_packet(
        tmp_path,
        cli.ARTIFACTS["public-benchmark"],
        "product_public_benchmark_work_order_ready",
        extra_summary={
            "public_benchmark_validation_ready": False,
            "open_suite_count": 5,
            "materialization_required_suite_count": 5,
            "scorecard_required_suite_count": 0,
                "continuous_validation_command_count": 5,
                "suite_run_command_count": 5,
                "suite_materialization_run_command_count": 5,
                "suite_scorecard_command_count": 5,
                "suite_result_provenance_command_count": 5,
                "suite_result_provenance_present_count": 0,
                "suite_threshold_count": 5,
                "suite_blocker_count": 5,
            "suite_materialization_manifest_count": 5,
            "suite_scorecard_row_csv_count": 5,
            "suite_required_output_count": 5,
            "suite_no_external_dependency_count": 5,
            "local_artifact_preflight_ready_suite_count": 0,
            "local_artifact_preflight_blocked_suite_count": 5,
            "missing_local_input_artifact_count": 8,
            "missing_local_output_artifact_count": 6,
        },
    )
    _write_packet(
        tmp_path,
        cli.ARTIFACTS["goal-completion-audit"],
        "blocked_product_goal_completion_audit",
        extra_summary={
            "goal_complete": False,
            "pass_count": 3,
            "fail_count": 2,
            "primary_bottleneck_phase": "P1_product_commercial_independence",
            "approval_tokens_required": ["APPROVE_PRODUCT_LICENSE_FILE_CREATION"],
        },
    )

    payload = cli.build_all_status(root=tmp_path)

    assert payload["public_benchmark_work_order_status"] == "product_public_benchmark_work_order_ready"
    assert payload["public_benchmark_open_suite_count"] == 5
    assert payload["public_benchmark_materialization_required_suite_count"] == 5
    assert payload["public_benchmark_continuous_validation_command_count"] == 5
    assert payload["public_benchmark_suite_run_command_count"] == 5
    assert payload["public_benchmark_suite_materialization_run_command_count"] == 5
    assert payload["public_benchmark_suite_scorecard_command_count"] == 5
    assert payload["public_benchmark_suite_result_provenance_command_count"] == 5
    assert payload["public_benchmark_suite_result_provenance_present_count"] == 0
    assert payload["public_benchmark_suite_threshold_count"] == 5
    assert payload["public_benchmark_suite_blocker_count"] == 5
    assert payload["public_benchmark_suite_materialization_manifest_count"] == 5
    assert payload["public_benchmark_suite_scorecard_row_csv_count"] == 5
    assert payload["public_benchmark_suite_required_output_count"] == 5
    assert payload["public_benchmark_suite_no_external_dependency_count"] == 5
    assert payload["public_benchmark_local_artifact_preflight_ready_suite_count"] == 0
    assert payload["public_benchmark_local_artifact_preflight_blocked_suite_count"] == 5
    assert payload["public_benchmark_missing_local_input_artifact_count"] == 8
    assert payload["public_benchmark_missing_local_output_artifact_count"] == 6
    assert payload["execution_enabled"] is False
    assert payload["external_state_mutated"] is False


def test_product_cli_all_surfaces_blocked_when_required_artifacts_missing(tmp_path: Path) -> None:
    _write_packet(tmp_path, cli.ARTIFACTS["capabilities"], "product_capability_surface_contract_ready")
    _write_packet(
        tmp_path,
        cli.ARTIFACTS["operations"],
        "blocked_product_release_operations_dossier",
        extra_summary={
            "stage_count": 10,
            "blocked_stage_count": 4,
            "approval_required_stage_count": 2,
            "approval_tokens_required": [
                "APPROVE_PRODUCT_DOCKING_EXECUTION",
                "APPROVE_PRODUCT_LICENSE_FILE_CREATION",
            ],
            "capability_surface_ready": True,
            "structure_analysis_capability_ready": True,
            "ligand_docking_capability_ready": True,
            "product_api_surface_ready": True,
            "operational_quality_ready": True,
            "architecture_release_ready": False,
            "cameo_architecture_validation_ready": False,
            "cleanup_postcheck_contract_ready": True,
            "commercial_independence_ready": False,
            "license_present": False,
            "license_authorized_for_file_creation_review": False,
            "license_decision_packet_ready": True,
            "license_decision_option_count": 5,
            "license_file_creation_review_ready": False,
            "authorized_for_execution": False,
            "bundle_assembled": False,
            "bundle_validation_passed": False,
            "delivery_ready_claim_allowed": False,
            "pilot_delivery_ready": False,
        },
    )
    _write_packet(
        tmp_path,
        cli.ARTIFACTS["cameo-live-validation"],
        "blocked_cameo_validation_operations_dossier",
        extra_summary={
            "validation_ready": False,
            "official_result_required": True,
            "official_results_intake_ready": False,
            "public_registration_allowed": False,
            "approval_tokens_required": [
                "APPROVE_CAMEO_OUTBOUND_EMAIL",
                "APPROVE_CAMEO_SERVER_REGISTRATION",
            ],
        },
    )

    payload = cli.build_all_status(root=tmp_path)

    assert payload["status"] == "blocked_product_cli_status_set"
    assert payload["core_product_cli_status_set_ready"] is False
    assert payload["command_count"] == len(cli.ARTIFACTS)
    assert payload["blocked_or_missing_command_count"] == len(cli.ARTIFACTS) - 1
    assert "capabilities" not in payload["blocked_or_missing_commands"]
    assert payload["approval_token_count"] == 2
    assert payload["approval_tokens_required"] == [
        "APPROVE_PRODUCT_DOCKING_EXECUTION",
        "APPROVE_PRODUCT_LICENSE_FILE_CREATION",
    ]
    assert payload["operations_stage_count"] == 10
    assert payload["operations_blocked_stage_count"] == 4
    assert payload["operations_approval_required_stage_count"] == 2
    assert payload["capability_surface_ready"] is True
    assert payload["structure_analysis_capability_ready"] is True
    assert payload["ligand_docking_capability_ready"] is True
    assert payload["product_api_surface_ready"] is True
    assert payload["operational_quality_ready"] is True
    assert payload["architecture_release_ready"] is False
    assert payload["cameo_architecture_validation_ready"] is False
    assert payload["cleanup_postcheck_contract_ready"] is True
    assert payload["commercial_independence_ready"] is False
    assert payload["public_benchmark_work_order_status"] == "missing_public_benchmark_artifact"
    assert payload["public_benchmark_validation_ready"] is False
    assert payload["public_benchmark_open_suite_count"] == 0
    assert payload["public_benchmark_materialization_required_suite_count"] == 0
    assert payload["public_benchmark_scorecard_required_suite_count"] == 0
    assert payload["public_benchmark_continuous_validation_command_count"] == 0
    assert payload["public_benchmark_suite_run_command_count"] == 0
    assert payload["public_benchmark_suite_threshold_count"] == 0
    assert payload["public_benchmark_suite_materialization_manifest_count"] == 0
    assert payload["public_benchmark_suite_scorecard_row_csv_count"] == 0
    assert payload["public_benchmark_suite_required_output_count"] == 0
    assert payload["public_benchmark_suite_no_external_dependency_count"] == 0
    assert payload["public_benchmark_local_artifact_preflight_ready_suite_count"] == 0
    assert payload["public_benchmark_local_artifact_preflight_blocked_suite_count"] == 0
    assert payload["public_benchmark_missing_local_input_artifact_count"] == 0
    assert payload["public_benchmark_missing_local_output_artifact_count"] == 0
    assert payload["cameo_live_validation_status"] == "blocked_cameo_validation_operations_dossier"
    assert payload["cameo_live_validation_ready"] is False
    assert payload["cameo_live_official_results_intake_ready"] is False
    assert payload["cameo_live_official_result_required"] is True
    assert payload["cameo_live_public_registration_allowed"] is False
    assert payload["cameo_live_approval_token_count"] == 2
    assert payload["cameo_live_approval_tokens_required"] == [
        "APPROVE_CAMEO_OUTBOUND_EMAIL",
        "APPROVE_CAMEO_SERVER_REGISTRATION",
    ]
    assert payload["license_present"] is False
    assert payload["license_authorized_for_file_creation_review"] is False
    assert payload["license_decision_packet_ready"] is True
    assert payload["license_decision_option_count"] == 5
    assert payload["license_file_creation_review_ready"] is False
    assert payload["goal_completion_audit_status"] == "missing_goal_completion_audit_artifact"
    assert payload["goal_complete"] is False
    assert payload["goal_completion_pass_count"] == 0
    assert payload["goal_completion_fail_count"] == 0
    assert payload["goal_completion_primary_bottleneck_phase"] == ""
    assert payload["goal_completion_next_command"] == ""
    assert payload["goal_completion_next_command_candidate_count"] == 0
    assert payload["goal_completion_next_command_candidates"] == []
    assert payload["authorized_for_execution"] is False
    assert payload["bundle_assembled"] is False
    assert payload["bundle_validation_passed"] is False
    assert payload["delivery_ready_claim_allowed"] is False
    assert payload["pilot_delivery_ready"] is False
    assert payload["execution_enabled"] is False
    assert payload["docking_results_emitted"] is False
    assert payload["external_state_mutated"] is False


def test_product_cli_core_ready_when_only_optional_lanes_blocked(tmp_path: Path) -> None:
    for command, rel_path in cli.ARTIFACTS.items():
        if command in cli.OPTIONAL_NON_BLOCKING_COMMANDS:
            _write_packet(tmp_path, rel_path, f"blocked_{command.replace('-', '_')}")
            continue
        status = "product_release_operations_dossier_ready" if command in {"operations", "release-readiness"} else "ready"
        extra = {}
        if command in {"operations", "release-readiness"}:
            extra = {
                "stage_count": 1,
                "blocked_stage_count": 0,
                "approval_required_stage_count": 0,
                "capability_surface_ready": True,
                "operational_quality_ready": True,
                "architecture_release_ready": True,
                "commercial_independence_ready": True,
                "authorized_for_execution": True,
                "bundle_validation_passed": True,
                "delivery_ready_claim_allowed": True,
                "pilot_delivery_ready": True,
            }
        _write_packet(tmp_path, rel_path, status, extra_summary=extra)

    payload = cli.build_all_status(root=tmp_path)

    assert payload["status"] == "product_cli_status_set_ready"
    assert payload["core_product_cli_status_set_ready"] is True
    assert payload["optional_blocked_or_missing_command_count"] == len(cli.OPTIONAL_NON_BLOCKING_COMMANDS)
    assert payload["core_blocked_or_missing_command_count"] == 0
    assert payload["delivery_ready_claim_allowed"] is True
