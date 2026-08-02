from __future__ import annotations

import json
from pathlib import Path

from tools.product import build_developer_preview_new_user_observation_receipt as mod


def _write_json(path: Path, summary: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"summary": summary}, indent=2) + "\n", encoding="utf-8")


def _write_ready_sources(root: Path) -> tuple[Path, Path]:
    work_order = root / ".betelgeuze/developer_preview_new_user_execution_work_order.json"
    preflight = root / ".betelgeuze/developer_preview_new_user_execution_preflight.json"
    _write_json(
        work_order,
        {
            "status": "product_execution_work_order_ready",
            "profile_command_generated": True,
            "blocker_count": 0,
        },
    )
    _write_json(
        preflight,
        {
            "status": "product_execution_preflight_ready",
            "validated_without_execution": True,
            "blocker_count": 0,
            "unknown_arg_count": 0,
        },
    )
    return work_order, preflight


def _write_runbook(root: Path) -> Path:
    runbook = root / "docs/developer_preview_core_workflow_quickstart.md"
    runbook.parent.mkdir(parents=True, exist_ok=True)
    runbook.write_text(
        "\n".join(mod.RUNBOOK_REQUIRED_TOKENS)
        + "\n",
        encoding="utf-8",
    )
    return runbook


def test_new_user_observation_receipt_ready_with_signoff(tmp_path: Path) -> None:
    work_order, preflight = _write_ready_sources(tmp_path)
    runbook = _write_runbook(tmp_path)

    payload = mod.build_developer_preview_new_user_observation_receipt(
        work_order_json=work_order,
        preflight_json=preflight,
        runbook_md=runbook,
        observer_id="reviewer-a",
        observed_at_utc="2026-07-03T00:00:00Z",
        anonymized_summary="Completed core workflow with no hidden local state.",
        observer_signoff=True,
        anonymized_notes_only=True,
        raw_customer_data_not_stored_in_repo=True,
        customer_retained_raw_data=True,
        root=tmp_path,
    )
    summary = payload["summary"]

    assert summary["status"] == "developer_preview_new_user_observation_receipt_ready"
    assert summary["new_user_observation_ready"] is True
    assert summary["observation_ready"] is True
    assert summary["new_user_draft_fail_closed_ready"] is False
    assert summary["observer_signoff"] is True
    assert summary["anonymized_notes_only"] is True
    assert summary["runbook_ready"] is True
    assert summary["runbook_required_token_count"] >= 20
    assert summary["runbook_missing_required_token_count"] == 0
    assert summary["core_workflow_receipt_path_documented"] is True
    assert summary["core_workflow_command_set_documented"] is True
    assert summary["observation_checklist_path_documented"] is True
    assert summary["developer_preview_exit_receipt_path_documented"] is True
    assert summary["developer_preview_exit_command_set_documented"] is True
    assert summary["clean_checkout_bootstrap_documented"] is True
    assert summary["linux_bootstrap_command_set_documented"] is True
    assert summary["windows_bootstrap_command_set_documented"] is True
    assert summary["clean_checkout_receipt_path_documented"] is True
    assert summary["platform_reproducibility_receipt_paths_documented"] is True
    assert summary["blocker_count"] == 0
    assert summary["primary_blocker"] == ""
    assert summary["primary_required_action"] == ""
    assert summary["hidden_state_blocker_count"] == 0
    assert summary["observation_review_required_field_count"] == 8
    assert summary["observation_review_ready_field_count"] == 8
    assert summary["observation_review_blocked_field_count"] == 0
    assert summary["observation_review_primary_field_id"] == ""
    assert summary["work_order_ready"] is True
    assert summary["preflight_ready"] is True
    assert summary["observation_input_template_json"] == (
        ".betelgeuze/developer_preview_new_user_observation_input_template.json"
    )
    assert summary["new_user_final_required_input_artifact"] == (
        ".betelgeuze/developer_preview_new_user_observation_input.json"
    )
    assert summary["new_user_draft_command_target"] == "new-user-draft"
    assert summary["new_user_final_command_target"] == "new-user-final"
    assert "derived/anonymized observer metadata" in summary[
        "new_user_observation_template_next_action"
    ]
    assert summary["raw_customer_data_not_stored_in_repo"] is True
    assert summary["raw_customer_data_stored_in_repo"] is False
    assert summary["customer_retained_raw_data"] is True
    assert summary["claim_promotion_allowed"] is False


def test_new_user_observation_receipt_blocks_without_signoff(tmp_path: Path) -> None:
    work_order, preflight = _write_ready_sources(tmp_path)
    runbook = _write_runbook(tmp_path)

    payload = mod.build_developer_preview_new_user_observation_receipt(
        work_order_json=work_order,
        preflight_json=preflight,
        runbook_md=runbook,
        hidden_state_blockers=["operator needed an undocumented local path"],
        root=tmp_path,
    )
    summary = payload["summary"]
    blockers = ";".join(summary["blockers"])
    template_rows = {
        row["field_id"]: row for row in payload["observation_review_template_rows"]
    }

    assert summary["status"] == "blocked_developer_preview_new_user_observation_receipt"
    assert summary["new_user_observation_ready"] is False
    assert summary["observation_ready"] is False
    assert summary["new_user_draft_fail_closed_ready"] is False
    assert summary["observer_signoff"] is False
    assert summary["anonymized_notes_only"] is False
    assert summary["runbook_ready"] is True
    assert summary["developer_preview_exit_receipt_path_documented"] is True
    assert summary["developer_preview_exit_command_set_documented"] is True
    assert summary["observation_checklist_path_documented"] is True
    assert summary["clean_checkout_bootstrap_documented"] is True
    assert summary["linux_bootstrap_command_set_documented"] is True
    assert summary["windows_bootstrap_command_set_documented"] is True
    assert summary["hidden_state_blocker_count"] == 1
    assert summary["observation_review_required_field_ids"] == [
        "observer_id_present",
        "observed_at_utc_present",
        "observer_signoff",
        "anonymized_notes_only",
        "anonymized_summary_present",
        "hidden_state_blockers_absent",
        "raw_customer_data_not_stored_in_repo",
        "customer_retained_raw_data",
    ]
    assert summary["observation_review_required_field_count"] == 8
    assert summary["observation_review_ready_field_count"] == 0
    assert summary["observation_review_blocked_field_count"] == 8
    assert summary["observation_review_primary_field_id"] == "observer_id_present"
    assert summary["observation_review_primary_blocker"] == "observer_id_missing"
    assert summary["observation_review_primary_required_action"] == (
        "Record a non-secret observer id in the reviewed receipt."
    )
    assert summary["primary_blocker"] == "observer_id_missing"
    assert summary["primary_required_action"] == summary[
        "observation_review_primary_required_action"
    ]
    assert summary["next_required_step"] == summary["primary_required_action"]
    assert "observer_signoff_missing" in blockers
    assert "anonymized_notes_only_not_true" in blockers
    assert "hidden_state_blockers_present" in blockers
    assert "raw_customer_data_not_confirmed_outside_repo" in blockers
    assert "customer_retained_raw_data_not_true" in blockers
    assert template_rows["observer_signoff"]["status"] == "blocked"
    assert template_rows["hidden_state_blockers_absent"]["observed"] == (
        "hidden_state_blocker_count=1"
    )
    assert template_rows["raw_customer_data_not_stored_in_repo"]["status"] == "blocked"
    assert template_rows["raw_customer_data_not_stored_in_repo"]["observed"] == "unverified"
    assert template_rows["customer_retained_raw_data"]["status"] == "blocked"
    assert all(row["execution_enabled"] is False for row in template_rows.values())


def test_new_user_observation_receipt_blocks_missing_runbook_token(tmp_path: Path) -> None:
    work_order, preflight = _write_ready_sources(tmp_path)
    runbook = tmp_path / "docs/developer_preview_core_workflow_quickstart.md"
    runbook.parent.mkdir(parents=True, exist_ok=True)
    runbook.write_text("tools/build_product_execution_work_order.py\n", encoding="utf-8")

    payload = mod.build_developer_preview_new_user_observation_receipt(
        work_order_json=work_order,
        preflight_json=preflight,
        runbook_md=runbook,
        observer_id="reviewer-a",
        observed_at_utc="2026-07-03T00:00:00Z",
        anonymized_summary="Completed core workflow with no hidden local state.",
        observer_signoff=True,
        anonymized_notes_only=True,
        raw_customer_data_not_stored_in_repo=True,
        customer_retained_raw_data=True,
        root=tmp_path,
    )
    summary = payload["summary"]
    runbook_row = {row["check"]: row for row in payload["rows"]}["runbook"]

    assert summary["status"] == "blocked_developer_preview_new_user_observation_receipt"
    assert summary["runbook_ready"] is False
    assert summary["runbook_missing_required_token_count"] > 0
    assert "tools/build_product_execution_preflight.py" in summary[
        "runbook_missing_required_tokens"
    ]
    assert "tools/product/build_developer_preview_clean_checkout_benchmark_receipt.py" in summary[
        "runbook_missing_required_tokens"
    ]
    assert ".betelgeuze/developer_preview_new_user_observation_checklist.csv" in summary[
        "runbook_missing_required_tokens"
    ]
    assert (
        "pwsh -File runs/developer_preview_external_operator_command_pack_current.ps1 -Target windows-repro"
        in summary["runbook_missing_required_tokens"]
    )
    assert summary["developer_preview_exit_receipt_path_documented"] is False
    assert summary["developer_preview_exit_command_set_documented"] is False
    assert summary["observation_checklist_path_documented"] is False
    assert summary["clean_checkout_bootstrap_documented"] is False
    assert summary["linux_bootstrap_command_set_documented"] is False
    assert summary["windows_bootstrap_command_set_documented"] is False
    assert summary["clean_checkout_receipt_path_documented"] is False
    assert summary["platform_reproducibility_receipt_paths_documented"] is False
    assert "python3 -m venv .venv" in summary["runbook_missing_required_tokens"]
    assert "docs/developer_preview_core_workflow_quickstart.md:missing_required_tokens" in summary[
        "blockers"
    ]
    assert runbook_row["status"] == "blocked"


def test_new_user_observation_receipt_accepts_observation_input_json(
    tmp_path: Path,
) -> None:
    work_order, preflight = _write_ready_sources(tmp_path)
    runbook = _write_runbook(tmp_path)
    observation_input = tmp_path / ".betelgeuze/developer_preview_new_user_observation_input.json"
    observation_input.write_text(
        json.dumps(
            {
                "packet_type": "developer_preview_new_user_observation_input",
                "schema_version": "developer_preview_new_user_observation_input_v1",
                "observer_id": "reviewer-a",
                "observed_at_utc": "2026-07-03T00:00:00Z",
                "anonymized_summary": "Completed core workflow with no hidden local state.",
                "observer_signoff": True,
                "anonymized_notes_only": True,
                "raw_customer_data_not_stored_in_repo": True,
                "customer_retained_raw_data": True,
                "hidden_state_blockers": [],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    payload = mod.build_developer_preview_new_user_observation_receipt(
        work_order_json=work_order,
        preflight_json=preflight,
        runbook_md=runbook,
        observation_input_json=observation_input,
        root=tmp_path,
    )
    summary = payload["summary"]
    rows = {row["check"]: row for row in payload["rows"]}

    assert summary["status"] == "developer_preview_new_user_observation_receipt_ready"
    assert summary["observation_input_json"] == (
        ".betelgeuze/developer_preview_new_user_observation_input.json"
    )
    assert summary["observation_input_json_present"] is True
    assert summary["observation_input_contract_ready"] is True
    assert summary["observation_input_packet_type"] == (
        "developer_preview_new_user_observation_input"
    )
    assert summary["observation_input_packet_type_valid"] is True
    assert summary["observation_input_schema_version"] == (
        "developer_preview_new_user_observation_input_v1"
    )
    assert summary["observation_input_schema_version_valid"] is True
    assert summary["observation_input_policy_ready"] is True
    assert summary["observation_input_raw_customer_data_allowed"] is False
    assert summary["observation_input_stores_private_notes"] is False
    assert summary["observer_id_present"] is True
    assert summary["observer_signoff"] is True
    assert summary["anonymized_notes_only"] is True
    assert summary["raw_customer_data_not_stored_in_repo"] is True
    assert summary["customer_retained_raw_data"] is True
    assert summary["blocker_count"] == 0
    assert rows["observation_input"]["status"] == "pass"
    assert rows["observation_input"]["observation_input_contract_ready"] is True


def test_new_user_observation_receipt_blocks_invalid_observation_input_contract(
    tmp_path: Path,
) -> None:
    work_order, preflight = _write_ready_sources(tmp_path)
    runbook = _write_runbook(tmp_path)
    observation_input = tmp_path / ".betelgeuze/developer_preview_new_user_observation_input.json"
    observation_input.write_text(
        json.dumps(
            {
                "packet_type": "wrong_packet",
                "schema_version": "wrong_schema",
                "observer_id": "reviewer-a",
                "observed_at_utc": "2026-07-03T00:00:00Z",
                "anonymized_summary": "Completed core workflow with no hidden local state.",
                "observer_signoff": True,
                "anonymized_notes_only": True,
                "raw_customer_data_not_stored_in_repo": True,
                "customer_retained_raw_data": True,
                "hidden_state_blockers": [],
                "raw_customer_data_allowed": True,
                "stores_private_notes": True,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    payload = mod.build_developer_preview_new_user_observation_receipt(
        work_order_json=work_order,
        preflight_json=preflight,
        runbook_md=runbook,
        observation_input_json=observation_input,
        root=tmp_path,
    )
    summary = payload["summary"]
    rows = {row["check"]: row for row in payload["rows"]}
    blockers = ";".join(summary["blockers"])

    assert summary["status"] == "blocked_developer_preview_new_user_observation_receipt"
    assert summary["observation_input_contract_ready"] is False
    assert summary["observation_input_packet_type_valid"] is False
    assert summary["observation_input_schema_version_valid"] is False
    assert summary["observation_input_policy_ready"] is False
    assert summary["observation_input_raw_customer_data_allowed"] is True
    assert summary["observation_input_stores_private_notes"] is True
    assert ".betelgeuze/developer_preview_new_user_observation_input.json:invalid_packet_type" in blockers
    assert ".betelgeuze/developer_preview_new_user_observation_input.json:invalid_schema_version" in blockers
    assert ".betelgeuze/developer_preview_new_user_observation_input.json:raw_customer_data_allowed_true" in blockers
    assert ".betelgeuze/developer_preview_new_user_observation_input.json:stores_private_notes_true" in blockers
    assert rows["observation_input"]["status"] == "blocked"
    assert rows["observation_input"]["observation_input_contract_ready"] is False


def test_new_user_observation_receipt_cli_writes_outputs(tmp_path: Path) -> None:
    work_order, preflight = _write_ready_sources(tmp_path)
    runbook = _write_runbook(tmp_path)
    out_json = tmp_path / ".betelgeuze/developer_preview_new_user_observation_receipt.json"
    out_md = tmp_path / ".betelgeuze/developer_preview_new_user_observation_receipt.md"
    out_checklist_csv = (
        tmp_path / ".betelgeuze/developer_preview_new_user_observation_checklist.csv"
    )
    out_checklist_md = (
        tmp_path / ".betelgeuze/developer_preview_new_user_observation_checklist.md"
    )
    out_observation_input_template = (
        tmp_path / ".betelgeuze/developer_preview_new_user_observation_input_template.json"
    )

    assert mod.main(
        [
            "--work-order-json",
            str(work_order),
            "--preflight-json",
            str(preflight),
            "--runbook-md",
            str(runbook),
            "--observer-id",
            "reviewer-a",
            "--observed-at-utc",
            "2026-07-03T00:00:00Z",
            "--anonymized-summary",
            "Completed core workflow with no hidden local state.",
            "--observer-signoff",
            "--anonymized-notes-only",
            "--raw-customer-data-not-stored-in-repo",
            "--customer-retained-raw-data",
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
            "--out-checklist-csv",
            str(out_checklist_csv),
            "--out-checklist-md",
            str(out_checklist_md),
            "--out-observation-input-template-json",
            str(out_observation_input_template),
        ]
    ) == 0

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    input_template = json.loads(out_observation_input_template.read_text(encoding="utf-8"))
    assert payload["summary"]["packet_type"] == "developer_preview_new_user_observation_receipt"
    assert payload["summary"]["observation_input_template_json"] == str(
        out_observation_input_template
    )
    assert payload["summary"]["new_user_final_required_input_artifact"] == (
        ".betelgeuze/developer_preview_new_user_observation_input.json"
    )
    assert "Developer Preview New-User Observation Receipt" in out_md.read_text(encoding="utf-8")
    assert "Observation Review Template" in out_md.read_text(encoding="utf-8")
    assert "new_user_final_required_input_artifact" in out_md.read_text(encoding="utf-8")
    assert "observer_id_present" in out_checklist_csv.read_text(encoding="utf-8")
    assert "Developer Preview New-User Observation Checklist" in out_checklist_md.read_text(
        encoding="utf-8"
    )
    assert "Raw customer data and private notes stay outside this repository" in (
        out_checklist_md.read_text(encoding="utf-8")
    )
    assert input_template["packet_type"] == "developer_preview_new_user_observation_input"
    assert input_template["schema_version"] == "developer_preview_new_user_observation_input_v1"
    assert input_template["raw_customer_data_allowed"] is False
    assert input_template["stores_private_notes"] is False


def test_new_user_observation_receipt_cli_allow_blocked_writes_fail_closed_outputs(
    tmp_path: Path,
) -> None:
    work_order, preflight = _write_ready_sources(tmp_path)
    runbook = _write_runbook(tmp_path)
    out_json = tmp_path / ".betelgeuze/developer_preview_new_user_observation_receipt.json"
    out_md = tmp_path / ".betelgeuze/developer_preview_new_user_observation_receipt.md"
    out_checklist_csv = (
        tmp_path / ".betelgeuze/developer_preview_new_user_observation_checklist.csv"
    )
    out_checklist_md = (
        tmp_path / ".betelgeuze/developer_preview_new_user_observation_checklist.md"
    )
    out_observation_input_template = (
        tmp_path / ".betelgeuze/developer_preview_new_user_observation_input_template.json"
    )

    assert mod.main(
        [
            "--work-order-json",
            str(work_order),
            "--preflight-json",
            str(preflight),
            "--runbook-md",
            str(runbook),
            "--allow-blocked",
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
            "--out-checklist-csv",
            str(out_checklist_csv),
            "--out-checklist-md",
            str(out_checklist_md),
            "--out-observation-input-template-json",
            str(out_observation_input_template),
        ]
    ) == 0

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    summary = payload["summary"]
    assert summary["status"] == "blocked_developer_preview_new_user_observation_receipt"
    assert summary["new_user_observation_ready"] is False
    assert summary["observation_ready"] is False
    assert summary["new_user_draft_fail_closed_ready"] is True
    assert summary["work_order_ready"] is True
    assert summary["preflight_ready"] is True
    assert summary["observation_input_template_json"] == str(out_observation_input_template)
    assert summary["new_user_final_required_input_artifact"] == (
        ".betelgeuze/developer_preview_new_user_observation_input.json"
    )
    assert summary["new_user_observation_template_next_action"].startswith(
        "Copy the generated observation input template"
    )
    assert summary["observer_signoff"] is False
    assert summary["claim_promotion_allowed"] is False
    assert out_md.is_file()
    assert out_checklist_csv.is_file()
    assert out_checklist_md.is_file()
    assert out_observation_input_template.is_file()
