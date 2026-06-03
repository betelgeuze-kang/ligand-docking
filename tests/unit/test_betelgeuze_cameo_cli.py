from __future__ import annotations

import json
from pathlib import Path

from betelgeuze_cameo import cli


def _write_packet(
    root: Path,
    rel_path: str,
    status: str,
    *,
    summary_extra: dict[str, object] | None = None,
    rows: list[dict[str, object]] | None = None,
) -> None:
    path = root / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    summary = {
        "status": status,
        "blocker_count": 0,
        "prediction_generation_enabled": False,
        "outbound_email_enabled": False,
        "external_state_mutated": False,
    }
    summary.update(summary_extra or {})
    path.write_text(
        json.dumps(
            {
                "summary": summary,
                "rows": rows if rows is not None else [{"status": "ready"}],
            }
        )
        + "\n",
        encoding="utf-8",
    )


def test_cameo_cli_reads_local_status_artifact_without_execution(tmp_path: Path) -> None:
    _write_packet(tmp_path, cli.ARTIFACTS["operations"], "cameo_validation_operations_dossier_ready")

    payload = cli.build_cli_status("operations", root=tmp_path)

    assert payload["status"] == "cameo_validation_operations_dossier_ready"
    assert payload["artifact_present"] is True
    assert payload["row_count"] == 1
    assert payload["blocker_count"] == 0
    assert payload["package_install_executed"] is False
    assert payload["server_registration_mutated"] is False
    assert payload["prediction_generation_enabled"] is False
    assert payload["outbound_email_enabled"] is False
    assert payload["official_results_fetched"] is False
    assert payload["native_local_accuracy_used"] is False
    assert payload["external_state_mutated"] is False


def test_cameo_cli_blocks_missing_artifact_without_mutation(tmp_path: Path) -> None:
    payload = cli.build_cli_status("official-results", root=tmp_path)

    assert payload["status"] == "missing_cameo_official_results_artifact"
    assert payload["artifact_present"] is False
    assert payload["blocker_count"] == 1
    assert payload["server_started"] is False
    assert payload["official_results_fetched"] is False
    assert payload["external_state_mutated"] is False


def test_cameo_cli_main_prints_json(tmp_path: Path, capsys) -> None:
    _write_packet(tmp_path, cli.ARTIFACTS["architecture"], "cameo_architecture_validation_contract_ready")

    assert cli.main(["architecture", "--root", str(tmp_path)]) == 0
    output = json.loads(capsys.readouterr().out)

    assert output["command"] == "architecture"
    assert output["status"] == "cameo_architecture_validation_contract_ready"
    assert output["prediction_generation_enabled"] is False


def test_cameo_cli_all_surfaces_blocked_when_required_artifacts_missing(tmp_path: Path) -> None:
    _write_packet(tmp_path, cli.ARTIFACTS["operator-inputs"], "cameo_operator_inputs_ready")

    payload = cli.build_all_status(root=tmp_path)

    assert payload["status"] == "blocked_cameo_cli_status_set"
    assert payload["command_count"] == len(cli.ARTIFACTS)
    assert payload["blocked_or_missing_command_count"] == len(cli.ARTIFACTS) - 1
    assert "operator-inputs" not in payload["blocked_or_missing_commands"]
    assert "api-contract" in payload["blocked_or_missing_commands"]
    assert "service-boundary" in payload["blocked_or_missing_commands"]
    assert payload["server_registration_mutated"] is False
    assert payload["prediction_generation_enabled"] is False
    assert payload["external_state_mutated"] is False


def test_cameo_cli_all_aggregates_approval_tokens_official_results_and_registration_state(tmp_path: Path) -> None:
    _write_packet(
        tmp_path,
        cli.ARTIFACTS["operations"],
        "blocked_cameo_validation_operations_dossier",
        summary_extra={
            "approval_tokens_required": [
                "APPROVE_API_DEPENDENCY_INSTALL",
                "APPROVE_CAMEO_SERVER_REGISTRATION",
                "APPROVE_CAMEO_OUTBOUND_EMAIL",
            ],
            "approval_required_stage_count": 2,
            "official_result_required": True,
            "official_results_intake_ready": False,
            "official_model1_result_ready": False,
            "official_cameo_results_used": False,
            "validation_ready": False,
            "runtime_install_approval_required": True,
            "public_registration_allowed": False,
            "api_dependency_status": "blocked_cameo_api_dependency_readiness",
            "receiver_smoke_status": "blocked_cameo_receiver_smoke",
        },
    )
    _write_packet(
        tmp_path,
        cli.ARTIFACTS["official-results"],
        "blocked_cameo_official_results_intake",
        summary_extra={
            "result_row_count": 0,
            "accepted_official_result_count": 0,
            "model1_official_result_ready": False,
            "official_cameo_results_used": False,
        },
    )
    _write_packet(
        tmp_path,
        cli.ARTIFACTS["readiness"],
        "cameo_validation_pending_official_results",
        summary_extra={"official_cameo_results_used": False},
    )
    _write_packet(
        tmp_path,
        cli.ARTIFACTS["performance"],
        "cameo_performance_pending_official_results",
        summary_extra={"threshold_policy_ready": True, "official_cameo_results_used": False},
    )
    _write_packet(
        tmp_path,
        cli.ARTIFACTS["runtime"],
        "blocked_cameo_api_dependency_readiness",
        summary_extra={"missing_or_unimportable_count": 4},
    )
    _write_packet(
        tmp_path,
        cli.ARTIFACTS["receiver-smoke"],
        "blocked_cameo_receiver_smoke",
        summary_extra={"blocker_count": 1},
    )
    _write_packet(
        tmp_path,
        cli.ARTIFACTS["registration-approval"],
        "blocked_cameo_public_registration_approval_gate",
        summary_extra={
            "authorized_for_registration_review": False,
            "awaiting_operator_approval_row_count": 1,
            "blocked_row_count": 1,
            "registration_approval_token_required": "APPROVE_CAMEO_SERVER_REGISTRATION",
            "outbound_email_approval_token_required": "APPROVE_CAMEO_OUTBOUND_EMAIL",
        },
    )

    payload = cli.build_all_status(root=tmp_path)

    assert payload["approval_token_count"] == 3
    assert payload["approval_tokens_required"] == [
        "APPROVE_API_DEPENDENCY_INSTALL",
        "APPROVE_CAMEO_OUTBOUND_EMAIL",
        "APPROVE_CAMEO_SERVER_REGISTRATION",
    ]
    assert payload["approval_required_command_count"] == 1
    assert payload["official_result_required"] is True
    assert payload["official_results_intake_ready"] is False
    assert payload["official_results_result_row_count"] == 0
    assert payload["official_results_accepted_count"] == 0
    assert payload["official_model1_result_ready"] is False
    assert payload["official_cameo_results_used"] is False
    assert payload["validation_ready"] is False
    assert payload["performance_threshold_policy_ready"] is True
    assert payload["api_install_approval_required"] is True
    assert payload["api_dependency_status"] == "blocked_cameo_api_dependency_readiness"
    assert payload["receiver_smoke_status"] == "blocked_cameo_receiver_smoke"
    assert payload["public_registration_allowed"] is False
    assert payload["public_registration_authorized"] is False
    assert payload["registration_awaiting_operator_approval_row_count"] == 1
    assert payload["registration_blocked_row_count"] == 1
    assert payload["server_registration_mutated"] is False
    assert payload["prediction_generation_enabled"] is False
    assert payload["outbound_email_enabled"] is False
    assert payload["external_state_mutated"] is False
