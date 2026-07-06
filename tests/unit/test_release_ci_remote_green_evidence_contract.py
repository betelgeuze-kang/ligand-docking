from __future__ import annotations

import json
from pathlib import Path

from tools.product.release_ci_remote_green_evidence_contract import (
    CONTRACT_SCHEMA_VERSION,
    EVIDENCE_INPUTS,
    PLACEHOLDER_STATUS,
    build_release_ci_remote_green_placeholder_payload,
    build_release_ci_remote_green_evidence_collect_manifest,
    build_release_ci_remote_green_evidence_contract,
    emit_release_ci_remote_green_collect_commands,
    emit_release_ci_remote_green_collect_shell_script,
    emit_release_ci_remote_green_placeholder_evidence,
    execute_release_ci_remote_green_collect_commands,
    validate_release_ci_remote_green_evidence_files,
    validate_release_ci_remote_green_evidence_payload,
)
from tools.product.build_release_ci_remote_green_receipt import (
    build_release_ci_remote_green_receipt,
)


def test_release_ci_evidence_contract_lists_all_receipt_inputs() -> None:
    contract = build_release_ci_remote_green_evidence_contract()

    assert contract["schema_version"] == CONTRACT_SCHEMA_VERSION
    assert contract["external_state_mutated"] is False
    assert len(contract["inputs"]) == len(EVIDENCE_INPUTS)
    receipt_args = {row["receipt_arg"] for row in contract["inputs"]}
    assert receipt_args == {
        "runner_inventory_json",
        "branch_json",
        "required_checks_json",
        "schedule_runs_json",
        "failed_run_artifacts_json",
        "release_tag_runs_json",
    }
    for row in contract["inputs"]:
        assert "gh api" in row["collect_command"]
        assert row["external_state_mutated"] is False
    assert "--emit-placeholders" in contract["placeholder_builder_command"]


def test_release_ci_evidence_collect_commands_include_failed_run_discovery() -> None:
    commands = emit_release_ci_remote_green_collect_commands()

    assert any("RELEASE_CI_FAILED_RUN_ID" in command for command in commands)
    assert any("status=failure" in command for command in commands)
    assert any("actions/runners" in command for command in commands)
    assert any("protection/required_status_checks" in command for command in commands)
    assert any("required_status_checks_unavailable_or_branch_unprotected" in command for command in commands)
    assert any("event=schedule" in command for command in commands)
    assert any("event=push" in command for command in commands)


def test_release_ci_evidence_shell_script_is_executable_bash_without_subprocess() -> None:
    script = emit_release_ci_remote_green_collect_shell_script()

    assert script.startswith("#!/usr/bin/env bash")
    assert "set -euo pipefail" in script
    assert "build_release_ci_remote_green_receipt.py" in script


def test_release_ci_evidence_payload_validation_accepts_structured_inputs() -> None:
    valid = validate_release_ci_remote_green_evidence_payload(
        "runner_inventory",
        {"runners": [], "total_count": 0},
    )
    assert valid["valid"] is True
    assert valid["present"] is True


def test_release_ci_evidence_payload_validation_rejects_missing_or_malformed() -> None:
    missing = validate_release_ci_remote_green_evidence_payload("schedule_runs", {})
    assert missing["valid"] is False
    assert missing["error"] == "missing_or_empty_payload"

    malformed = validate_release_ci_remote_green_evidence_payload("main_branch", ["not", "a", "dict"])
    assert malformed["valid"] is False
    assert malformed["error"] == "payload_not_object"

    incomplete = validate_release_ci_remote_green_evidence_payload(
        "main_branch",
        {"name": "main"},
    )
    assert incomplete["valid"] is False
    assert incomplete["error"] == "missing_required_keys"
    assert "protected" in incomplete["missing_keys"]


def test_release_ci_evidence_file_validation_is_fail_closed_for_absent_files(tmp_path: Path) -> None:
    validation = validate_release_ci_remote_green_evidence_files(root=tmp_path)

    assert validation["valid"] is False
    assert validation["invalid_count"] == len(EVIDENCE_INPUTS)
    assert all(not row["valid"] for row in validation["rows"])


def test_release_ci_evidence_file_validation_passes_for_complete_bundle(tmp_path: Path) -> None:
    paths = {
        "runner_inventory": tmp_path / "runners.json",
        "main_branch": tmp_path / "branch.json",
        "main_required_checks": tmp_path / "required_checks.json",
        "schedule_runs": tmp_path / "schedule_runs.json",
        "failed_run_artifacts": tmp_path / "failed_artifacts.json",
        "release_tag_runs": tmp_path / "tag_runs.json",
    }
    paths["runner_inventory"].write_text(json.dumps({"runners": []}) + "\n", encoding="utf-8")
    paths["main_branch"].write_text(json.dumps({"name": "main", "protected": False}) + "\n", encoding="utf-8")
    paths["main_required_checks"].write_text(json.dumps({"contexts": []}) + "\n", encoding="utf-8")
    paths["schedule_runs"].write_text(json.dumps({"workflow_runs": []}) + "\n", encoding="utf-8")
    paths["failed_run_artifacts"].write_text(json.dumps({"artifacts": []}) + "\n", encoding="utf-8")
    paths["release_tag_runs"].write_text(json.dumps({"workflow_runs": []}) + "\n", encoding="utf-8")

    validation = validate_release_ci_remote_green_evidence_files(root=tmp_path, paths=paths)

    assert validation["valid"] is True
    assert validation["invalid_count"] == 0


def test_release_ci_placeholder_payloads_are_shape_valid_but_fail_closed() -> None:
    required_checks = build_release_ci_remote_green_placeholder_payload("main_required_checks")
    assert required_checks["contexts"] == []
    assert required_checks["placeholder"]["status"] == PLACEHOLDER_STATUS
    assert required_checks["placeholder"]["external_state_mutated"] is False

    validation = validate_release_ci_remote_green_evidence_payload(
        "main_required_checks",
        required_checks,
    )

    assert validation["valid"] is True


def test_release_ci_placeholder_emission_preserves_existing_evidence(tmp_path: Path) -> None:
    required_checks = tmp_path / "required_checks.json"
    required_checks.write_text(
        json.dumps({"contexts": ["product-image-build-smoke"], "checks": []}) + "\n",
        encoding="utf-8",
    )
    paths = {"main_required_checks": required_checks}

    result = emit_release_ci_remote_green_placeholder_evidence(root=tmp_path, paths=paths)
    rows = {row["input_id"]: row for row in result["rows"]}

    assert rows["main_required_checks"]["existed_before"] is True
    assert rows["main_required_checks"]["wrote_placeholder"] is False
    assert json.loads(required_checks.read_text(encoding="utf-8")) == {
        "contexts": ["product-image-build-smoke"],
        "checks": [],
    }


def test_release_ci_placeholder_bundle_keeps_receipt_blocked(tmp_path: Path) -> None:
    emit_release_ci_remote_green_placeholder_evidence(root=tmp_path)
    workflow = tmp_path / ".github/workflows/product-image-smoke.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text("name: product-image-smoke\n", encoding="utf-8")

    payload = build_release_ci_remote_green_receipt(
        root=tmp_path,
        runner_inventory_json="runs/github_self_hosted_runner_inventory_current.json",
        branch_json="runs/release_ci_branch_main_current.json",
        required_checks_json="runs/release_ci_required_status_checks_main_current.json",
        schedule_runs_json="runs/release_ci_product_image_smoke_schedule_runs_current.json",
        failed_run_artifacts_json="runs/release_ci_failed_run_artifacts_current.json",
        release_tag_runs_json="runs/release_ci_product_image_smoke_push_runs_current.json",
        workflow_yml=".github/workflows/product-image-smoke.yml",
    )

    summary = payload["summary"]
    blocker_codes = {row["code"] for row in payload["blockers"]}
    assert summary["status"] == "blocked_release_ci_remote_green"
    assert summary["main_required_checks_ready"] is False
    assert summary["external_state_mutated"] is False
    assert "main_branch_required_checks_configured" in blocker_codes


def test_release_ci_evidence_collect_manifest_embeds_contract_and_validation(tmp_path: Path) -> None:
    manifest = build_release_ci_remote_green_evidence_collect_manifest(root=tmp_path)

    summary = manifest["summary"]
    assert summary["packet_type"] == "release_ci_remote_green_evidence_collect_manifest"
    assert summary["validation_valid"] is False
    assert summary["collect_command_count"] == len(emit_release_ci_remote_green_collect_commands())
    assert manifest["contract"]["schema_version"] == CONTRACT_SCHEMA_VERSION
    assert manifest["validation"]["external_state_mutated"] is False


def test_release_ci_evidence_execute_uses_injected_runner_without_subprocess() -> None:
    seen: list[str] = []

    def fake_execute(command: str) -> int:
        seen.append(command)
        return 0

    result = execute_release_ci_remote_green_collect_commands(execute_fn=fake_execute)

    assert result["executed"] is True
    assert result["passed"] is True
    assert seen
    assert all("gh api" in command or "RELEASE_CI_FAILED_RUN_ID" in command for command in seen)
    failed_run_rows = [row for row in result["rows"] if row["input_id"] == "failed_run_artifacts"]
    assert len(failed_run_rows) == 1
    assert len(failed_run_rows[0]["commands"]) == 1
    assert "RELEASE_CI_FAILED_RUN_ID=$(gh api" in failed_run_rows[0]["commands"][0]
    assert "status=failure" in failed_run_rows[0]["commands"][0]
    assert "actions/runs/${RELEASE_CI_FAILED_RUN_ID}/artifacts" in failed_run_rows[0]["commands"][0]
    assert "no_failed_product_image_run_found" in failed_run_rows[0]["commands"][0]


def test_release_ci_evidence_payload_validation_rejects_unknown_input_id() -> None:
    result = validate_release_ci_remote_green_evidence_payload("unknown_input", {"runners": []})
    assert result["valid"] is False
    assert result["error"] == "unknown_input_id"
