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
            "suite_threshold_count": 5,
            "suite_materialization_manifest_count": 5,
            "suite_scorecard_row_csv_count": 5,
            "suite_required_output_count": 5,
            "suite_no_external_dependency_count": 5,
        },
    )

    payload = cli.build_cli_status("public-benchmark", root=tmp_path)

    assert payload["status"] == "product_public_benchmark_work_order_ready"
    assert payload["artifact_present"] is True
    assert payload["summary"]["open_suite_count"] == 5
    assert payload["summary"]["suite_run_command_count"] == 5
    assert payload["execution_enabled"] is False
    assert payload["external_state_mutated"] is False


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
            "suite_threshold_count": 5,
            "suite_materialization_manifest_count": 5,
            "suite_scorecard_row_csv_count": 5,
            "suite_required_output_count": 5,
            "suite_no_external_dependency_count": 5,
        },
    )

    payload = cli.build_all_status(root=tmp_path)

    assert payload["public_benchmark_work_order_status"] == "product_public_benchmark_work_order_ready"
    assert payload["public_benchmark_open_suite_count"] == 5
    assert payload["public_benchmark_materialization_required_suite_count"] == 5
    assert payload["public_benchmark_continuous_validation_command_count"] == 5
    assert payload["public_benchmark_suite_run_command_count"] == 5
    assert payload["public_benchmark_suite_threshold_count"] == 5
    assert payload["public_benchmark_suite_materialization_manifest_count"] == 5
    assert payload["public_benchmark_suite_scorecard_row_csv_count"] == 5
    assert payload["public_benchmark_suite_required_output_count"] == 5
    assert payload["public_benchmark_suite_no_external_dependency_count"] == 5
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
    assert payload["authorized_for_execution"] is False
    assert payload["bundle_assembled"] is False
    assert payload["bundle_validation_passed"] is False
    assert payload["delivery_ready_claim_allowed"] is False
    assert payload["pilot_delivery_ready"] is False
    assert payload["execution_enabled"] is False
    assert payload["docking_results_emitted"] is False
    assert payload["external_state_mutated"] is False
