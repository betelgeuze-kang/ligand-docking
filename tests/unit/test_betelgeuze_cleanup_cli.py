from __future__ import annotations

import json
from pathlib import Path

from betelgeuze_cleanup import cli


def _write_packet(root: Path, rel_path: str, status: str, **summary_extra) -> None:
    path = root / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    summary = {
        "status": status,
        "blocker_count": 0,
        "delete_enabled": False,
        "delete_executed": False,
        "external_state_mutated": False,
    }
    summary.update(summary_extra)
    path.write_text(json.dumps({"summary": summary, "rows": [{"status": "ready"}]}) + "\n", encoding="utf-8")


def test_cleanup_cli_reads_local_status_artifact_without_execution(tmp_path: Path) -> None:
    _write_packet(tmp_path, cli.ARTIFACTS["approval-dossier"], "cleanup_execution_approval_dossier_ready")

    payload = cli.build_cli_status("approval-dossier", root=tmp_path)

    assert payload["status"] == "cleanup_execution_approval_dossier_ready"
    assert payload["artifact_present"] is True
    assert payload["row_count"] == 1
    assert payload["blocker_count"] == 0
    assert payload["execution_enabled"] is False
    assert payload["delete_enabled"] is False
    assert payload["delete_executed"] is False
    assert payload["archive_executed"] is False
    assert payload["externalize_executed"] is False
    assert payload["external_state_mutated"] is False


def test_cleanup_cli_blocks_missing_artifact_without_mutation(tmp_path: Path) -> None:
    payload = cli.build_cli_status("completion", root=tmp_path)

    assert payload["status"] == "missing_cleanup_completion_artifact"
    assert payload["artifact_present"] is False
    assert payload["blocker_count"] == 1
    assert payload["delete_enabled"] is False
    assert payload["external_state_mutated"] is False


def test_cleanup_cli_main_prints_json(tmp_path: Path, capsys) -> None:
    _write_packet(tmp_path, cli.ARTIFACTS["protected-policy"], "blocked_protected_cleanup_policy_decision_gate", blocker_count=3)

    assert cli.main(["protected-policy", "--root", str(tmp_path)]) == 0
    output = json.loads(capsys.readouterr().out)

    assert output["command"] == "protected-policy"
    assert output["status"] == "blocked_protected_cleanup_policy_decision_gate"
    assert output["blocker_count"] == 3
    assert output["delete_executed"] is False


def test_cleanup_cli_all_surfaces_reports_missing_and_approval_required(tmp_path: Path) -> None:
    _write_packet(
        tmp_path,
        cli.ARTIFACTS["approval-gate"],
        "blocked_cleanup_execution_operator_approval_gate",
        awaiting_operator_approval_row_count=5,
        total_reclaim_size_gb=49.216,
        authorized_reclaim_size_gb=0.0,
        approval_tokens_required=[
            "APPROVE_DELETE_STALE_LIGAND_HEAVY_PAYLOADS",
            "APPROVE_EXTERNALIZE_HEAVY_ARTIFACTS",
        ],
    )
    _write_packet(
        tmp_path,
        cli.ARTIFACTS["postcheck"],
        "cleanup_postcheck_contract_ready",
        postcheck_contract_ready=True,
        row_count=7,
        blocked_row_count=0,
        global_refresh_command_count=9,
    )
    _write_packet(
        tmp_path,
        cli.ARTIFACTS["protected-policy"],
        "blocked_protected_cleanup_policy_decision_gate",
        protected_payload_size_gb=396.794,
        policy_change_required_count=2,
        policy_resolved=False,
    )

    payload = cli.build_all_status(root=tmp_path)

    assert payload["status"] == "blocked_cleanup_cli_status_set"
    assert payload["command_count"] == len(cli.ARTIFACTS)
    assert payload["blocked_or_missing_command_count"] == len(cli.ARTIFACTS) - 1
    assert "approval-gate" in payload["approval_required_commands"]
    assert payload["approval_token_count"] == 2
    assert payload["approval_tokens_required"] == [
        "APPROVE_DELETE_STALE_LIGAND_HEAVY_PAYLOADS",
        "APPROVE_EXTERNALIZE_HEAVY_ARTIFACTS",
    ]
    assert payload["awaiting_operator_approval_row_count"] == 5
    assert payload["approval_reclaim_size_gb"] == 49.216
    assert payload["authorized_reclaim_size_gb"] == 0.0
    assert payload["postcheck_contract_ready"] is True
    assert payload["postcheck_row_count"] == 7
    assert payload["postcheck_blocked_row_count"] == 0
    assert payload["postcheck_global_refresh_command_count"] == 9
    assert payload["protected_payload_size_gb"] == 396.794
    assert payload["protected_policy_change_required_count"] == 2
    assert payload["protected_policy_resolved"] is False
    assert payload["delete_enabled"] is False
    assert payload["external_state_mutated"] is False
