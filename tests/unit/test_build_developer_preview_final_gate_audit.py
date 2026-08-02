from __future__ import annotations

import json
from pathlib import Path

from tools.product import build_developer_preview_final_gate_audit as mod


def _write_json(path: Path, summary: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"summary": summary}, indent=2) + "\n", encoding="utf-8")


def _write_payload(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_register(root: Path) -> None:
    path = root / "docs/developer_preview_final_gate_action_register.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                *(spec["gate_id"] for spec in mod.GATE_SPECS),
                *mod.REGISTER_FAIL_CLOSED_REQUIRED_TOKENS,
            ]
        ),
        encoding="utf-8",
    )


def _write_ready_receipts(root: Path) -> None:
    _write_json(
        root / ".betelgeuze/developer_preview_clean_checkout_benchmark_receipt.json",
        {
            "status": "developer_preview_clean_checkout_benchmark_receipt_ready",
            "clean_checkout_benchmark_regenerated": True,
            "clean_checkout_provenance_ready": True,
            "clean_checkout_source_repo_url_present": True,
            "clean_checkout_working_tree_clean": True,
            "ai_verify_passed": True,
            "reviewed_receipt_attached": True,
            "stage5_input_family_ready": True,
            "blocker_count": 0,
            "failed_count": 0,
            "clean_checkout_dirty_path_count": 0,
            "stage5_missing_source_artifact_count": 0,
            "stage5_incomplete_task_count": 0,
        },
    )
    _write_json(
        root / ".betelgeuze/developer_preview_silent_import_loss_receipt.json",
        {
            "status": "developer_preview_silent_import_loss_receipt_ready",
            "import_cli_tests_passed": True,
            "capability_matrix_checked": True,
            "silent_import_loss_zero": True,
            "blocker_count": 0,
            "missing_required_surface_count": 0,
            "unimportable_required_surface_count": 0,
        },
    )
    _write_json(
        root / ".betelgeuze/developer_preview_medium_pose_sampling_readiness.json",
        {
            "status": "product_pose_sampling_readiness_ready",
            "pose_sampling_readiness_ready": True,
            "blocker_count": 0,
        },
    )
    _write_json(
        root / ".betelgeuze/developer_preview_medium_backmapping_smoke.json",
        {
            "status": "backmapping_scoring_batch_smoke_benchmark_ready",
            "benchmark_ready": True,
            "blocker_count": 0,
            "failed_count": 0,
        },
    )
    for name, status in (
        ("developer_preview_large_model_oom_guard", "developer_preview_large_model_oom_guard_ready"),
        ("developer_preview_rocm_large_model_guard", "developer_preview_rocm_large_model_guard_ready"),
    ):
        _write_json(
            root / f".betelgeuze/{name}.json",
            {
                "status": status,
                "crash_oom_free": True,
                "blocker_count": 0,
                "crash_count": 0,
                "oom_count": 0,
            },
        )
    _write_json(
        root / ".betelgeuze/developer_preview_linux_reproducibility_receipt.json",
        {
            "status": "developer_preview_platform_reproducibility_receipt_ready",
            "command_set_passed": True,
            "linux_receipt": True,
            "blocker_count": 0,
        },
    )
    _write_json(
        root / ".betelgeuze/developer_preview_windows_reproducibility_receipt.json",
        {
            "status": "developer_preview_platform_reproducibility_receipt_ready",
            "command_set_passed": True,
            "windows_receipt": True,
            "blocker_count": 0,
        },
    )
    _write_json(
        root / ".betelgeuze/developer_preview_new_user_execution_work_order.json",
        {
            "status": "product_execution_work_order_ready",
            "profile_command_generated": True,
            "blocker_count": 0,
        },
    )
    _write_json(
        root / ".betelgeuze/developer_preview_new_user_execution_preflight.json",
        {
            "status": "product_execution_preflight_ready",
            "validated_without_execution": True,
            "blocker_count": 0,
            "unknown_arg_count": 0,
        },
    )
    _write_json(
        root / ".betelgeuze/developer_preview_new_user_observation_receipt.json",
        {
            "status": "developer_preview_new_user_observation_receipt_ready",
            "new_user_draft_fail_closed_ready": False,
            "runbook_ready": True,
            "core_workflow_receipt_path_documented": True,
            "core_workflow_command_set_documented": True,
            "observation_checklist_path_documented": True,
            "developer_preview_exit_receipt_path_documented": True,
            "developer_preview_exit_command_set_documented": True,
            "clean_checkout_bootstrap_documented": True,
            "linux_bootstrap_command_set_documented": True,
            "windows_bootstrap_command_set_documented": True,
            "clean_checkout_receipt_path_documented": True,
            "platform_reproducibility_receipt_paths_documented": True,
            "observer_signoff": True,
            "anonymized_notes_only": True,
            "raw_customer_data_not_stored_in_repo": True,
            "customer_retained_raw_data": True,
            "blocker_count": 0,
            "hidden_state_blocker_count": 0,
            "observation_input_json_present": True,
            "observation_input_contract_ready": True,
            "observation_input_policy_ready": True,
            "new_user_observation_template_next_action": (
                "Copy the generated observation input template to "
                ".betelgeuze/developer_preview_new_user_observation_input.json, "
                "fill only derived/anonymized observer metadata, then run the "
                "new-user-final command-pack target."
            ),
            "primary_required_action": "",
        },
    )


def test_developer_preview_final_gate_audit_blocks_missing_receipts(tmp_path: Path) -> None:
    _write_register(tmp_path)

    payload = mod.build_developer_preview_final_gate_audit(root=tmp_path)
    summary = payload["summary"]
    rows = {row["gate_id"]: row for row in payload["rows"]}

    assert summary["status"] == "blocked_developer_preview_final_gate_audit"
    assert summary["developer_preview_clean_baseline_ready"] is False
    assert summary["developer_preview_exit_ready"] is False
    assert summary["clean_checkout_ready"] is False
    assert summary["linux_windows_reproducibility_ready"] is False
    assert summary["windows_reproducibility_ready"] is False
    assert summary["new_user_observation_ready"] is False
    assert summary["gate_count"] == 6
    assert summary["ready_gate_count"] == 0
    assert summary["blocked_gate_count"] == 6
    assert summary["primary_blocker_id"] == "benchmark_results_clean_checkout_regenerated"
    assert summary["primary_blocker"] == summary["blockers"][0]
    assert summary["primary_blocker_detail"] == (
        ".betelgeuze/developer_preview_clean_checkout_benchmark_receipt.json:missing"
    )
    assert summary["claim_promotion_allowed"] is False
    assert summary["receipt_work_order_ready"] is False
    assert summary["receipt_work_order_row_count"] >= summary["missing_receipt_count"]
    assert summary["receipt_work_order_blocked_gate_count"] == 6
    assert summary["receipt_work_order_primary_gate_id"] == "benchmark_results_clean_checkout_regenerated"
    assert summary["receipt_work_order_primary_receipt_artifact"] == (
        ".betelgeuze/developer_preview_clean_checkout_benchmark_receipt.json"
    )
    assert summary["receipt_work_order_primary_blocker"] == "missing"
    assert payload["receipt_work_order_rows"][0]["required_action"] == (
        "Create or attach the required receipt artifact."
    )
    assert payload["receipt_work_order_rows"][0]["required_receipt_status"] == (
        "developer_preview_clean_checkout_benchmark_receipt_ready"
    )
    assert payload["receipt_work_order_rows"][0]["required_true_fields"] == [
        "clean_checkout_benchmark_regenerated",
        "clean_checkout_provenance_ready",
        "clean_checkout_source_repo_url_present",
        "clean_checkout_working_tree_clean",
        "ai_verify_passed",
        "reviewed_receipt_attached",
        "stage5_input_family_ready",
    ]
    assert payload["receipt_work_order_rows"][0]["required_zero_fields"] == [
        "blocker_count",
        "failed_count",
        "clean_checkout_dirty_path_count",
        "stage5_missing_source_artifact_count",
        "stage5_incomplete_task_count",
    ]
    assert summary["receipt_work_order_primary_required_receipt_status"] == (
        "developer_preview_clean_checkout_benchmark_receipt_ready"
    )
    assert summary["receipt_work_order_primary_required_true_fields"] == [
        "clean_checkout_benchmark_regenerated",
        "clean_checkout_provenance_ready",
        "clean_checkout_source_repo_url_present",
        "clean_checkout_working_tree_clean",
        "ai_verify_passed",
        "reviewed_receipt_attached",
        "stage5_input_family_ready",
    ]
    assert summary["receipt_work_order_primary_required_zero_fields"] == [
        "blocker_count",
        "failed_count",
        "clean_checkout_dirty_path_count",
        "stage5_missing_source_artifact_count",
        "stage5_incomplete_task_count",
    ]
    assert summary["receipt_work_order_source_blocker_count"] == 0
    assert summary["receipt_work_order_primary_source_blocker_gate_id"] == ""
    assert summary["receipt_work_order_primary_source_blocker_receipt_artifact"] == ""
    assert summary["receipt_work_order_primary_source_blocker"] == ""
    assert summary["receipt_work_order_primary_source_blocker_required_action"] == ""
    assert summary["stage5_recovery_work_order_ready"] is True
    assert summary["stage5_recovery_operator_work_order_ready"] is True
    assert summary["stage5_recovery_operator_work_order_materialized"] is False
    assert summary["stage5_input_family_csv_present"] is False
    assert summary["stage5_input_family_md_present"] is False
    assert summary["stage5_recovery_row_count"] == 0
    assert summary["stage5_missing_source_artifact_count"] == 0
    assert summary["stage5_primary_task_key"] == ""
    assert summary["stage5_restore_packet_json_path"] == (
        "runs/developer_preview_stage5_restore_packet_current.json"
    )
    assert summary["stage5_restore_packet_json_present"] is False
    assert summary["stage5_restore_packet_status"] == ""
    assert summary["stage5_restore_packet_ready"] is False
    assert summary["stage5_restore_packet_fail_closed_restore_receipt_ready"] is False
    assert summary["stage5_restore_packet_operator_restore_queue_ready"] is False
    assert summary["stage5_restore_packet_operator_restore_queue_row_count"] == 0
    assert summary["stage5_restore_packet_missing_source_artifact_count"] == 0
    assert summary["stage5_restore_packet_primary_blocker"] == ""
    assert summary["stage5_restore_packet_primary_missing_source_artifact_path"] == ""
    assert summary["stage5_restore_packet_primary_missing_restore_instruction"] == ""
    assert summary["stage5_restore_packet_next_required_step"] == ""
    assert summary["stage5_restore_packet_operator_action_required"] is False
    assert payload["stage5_recovery_rows"] == []
    assert summary["external_operator_work_order_json_path"] == (
        "runs/developer_preview_external_operator_work_order_current.json"
    )
    assert summary["external_operator_work_order_csv_path"] == (
        "runs/developer_preview_external_operator_work_order_current.csv"
    )
    assert summary["external_operator_work_order_md_path"] == (
        "runs/developer_preview_external_operator_work_order_current.md"
    )
    assert summary["external_operator_command_pack_target_count"] == 7
    assert summary["next_operator_command_pack_target"] == "clean-checkout"
    assert summary["next_operator_command_pack_command"] == (
        "bash runs/developer_preview_external_operator_command_pack_current.sh clean-checkout"
    )
    assert summary["next_operator_command_pack_required_platform"] == "fresh local clone"
    assert summary["next_operator_command_pack_required_env_vars"] == [
        "DEVELOPER_PREVIEW_REPO_URL",
        "DEVELOPER_PREVIEW_REVIEWER_ID",
        "DEVELOPER_PREVIEW_REVIEWED_AT_UTC",
    ]
    assert summary["external_operator_work_order_ready"] is False
    assert summary["external_operator_work_order_row_count"] == 4
    assert summary["external_operator_work_order_blocked_row_count"] == 4
    assert summary["external_operator_work_order_primary_flow_id"] == (
        "clean_checkout_benchmark_receipt"
    )
    assert summary["external_operator_work_order_primary_gate_id"] == (
        "benchmark_results_clean_checkout_regenerated"
    )
    assert summary["external_operator_work_order_primary_receipt_artifact"] == (
        ".betelgeuze/developer_preview_clean_checkout_benchmark_receipt.json"
    )
    assert summary["external_operator_work_order_primary_blocker"] == (
        ".betelgeuze/developer_preview_clean_checkout_benchmark_receipt.json:missing"
    )
    assert summary["external_operator_work_order_primary_required_action"] == (
        "Run Gate A from a fresh clone, keep the ai-verify log and baseline summary, "
        "then rebuild the reviewed clean-checkout benchmark receipt."
    )
    assert summary["blocker_count"] == len(summary["blockers"])
    assert summary["blocker_count"] == summary["blocked_gate_count"]
    assert summary["clean_checkout_operator_work_order_ready"] is False
    assert summary["linux_reproducibility_operator_work_order_ready"] is False
    assert summary["windows_reproducibility_operator_work_order_ready"] is False
    assert summary["new_user_observation_operator_work_order_ready"] is False
    assert summary["new_user_observation_draft_fail_closed_ready"] is False
    assert summary["new_user_observation_input_json"] == (
        ".betelgeuze/developer_preview_new_user_observation_input.json"
    )
    assert summary["new_user_observation_input_template_json"] == (
        ".betelgeuze/developer_preview_new_user_observation_input_template.json"
    )
    assert summary["new_user_observation_input_json_present"] is False
    assert summary["new_user_observation_input_contract_ready"] is False
    assert summary["new_user_observation_input_policy_ready"] is False
    assert summary["new_user_observation_checklist_csv"] == (
        ".betelgeuze/developer_preview_new_user_observation_checklist.csv"
    )
    assert summary["new_user_observation_checklist_md"] == (
        ".betelgeuze/developer_preview_new_user_observation_checklist.md"
    )
    assert summary["new_user_observation_checklist_path_documented"] is False
    assert summary["new_user_observation_template_next_action"] == ""
    assert summary["new_user_observation_primary_required_action"] == ""
    operator_rows = {
        row["operator_flow_id"]: row
        for row in payload["external_operator_work_order_rows"]
    }
    assert operator_rows["windows_reproducibility_receipt"]["required_platform"] == (
        "Windows checkout"
    )
    assert operator_rows["windows_reproducibility_receipt"]["fail_closed_command_token"] == (
        "tools/product/build_developer_preview_platform_reproducibility_receipt.py "
        "--platform windows --allow-blocked"
    )
    assert operator_rows["new_user_observation_receipt"]["required_receipt_count"] == 3
    assert operator_rows["new_user_observation_receipt"]["operator_action_required"] is True
    assert payload["receipt_work_order_rows"][0]["blocker_scope"] == "receipt_contract"
    assert rows["benchmark_results_clean_checkout_regenerated"]["blocker"].endswith(":missing")
    assert rows["linux_windows_reproducibility_confirmed"]["required_receipt_count"] == 2
    assert summary["execution_enabled"] is False
    assert summary["external_state_mutated"] is False


def test_developer_preview_medium_gate_accepts_approved_review(tmp_path: Path) -> None:
    _write_register(tmp_path)
    _write_json(
        tmp_path / ".betelgeuze/developer_preview_medium_model_operator_review.json",
        {
            "status": "developer_preview_medium_model_operator_review_approved",
            "approved_review": True,
            "blocker_count": 0,
        },
    )

    payload = mod.build_developer_preview_final_gate_audit(root=tmp_path)
    row = {
        item["gate_id"]: item
        for item in payload["rows"]
    }["selected_medium_models_pass_or_approved_review"]

    assert row["ready"] is True
    assert row["primary_metric"] == "required_ready=false; review_ready=true"
    assert row["claim_promotion_allowed"] is False


def test_developer_preview_final_gate_audit_surfaces_present_blocked_receipt_details(
    tmp_path: Path,
) -> None:
    _write_register(tmp_path)
    _write_ready_receipts(tmp_path)
    _write_json(
        tmp_path / ".betelgeuze/developer_preview_new_user_observation_receipt.json",
        {
            "status": "blocked_developer_preview_new_user_observation_receipt",
            "observer_signoff": False,
            "anonymized_notes_only": False,
            "new_user_draft_fail_closed_ready": True,
            "observation_input_json_present": True,
            "observation_input_contract_ready": True,
            "observation_input_policy_ready": True,
            "observation_checklist_path_documented": True,
            "new_user_observation_template_next_action": (
                "Copy the generated observation input template to "
                ".betelgeuze/developer_preview_new_user_observation_input.json, "
                "fill only derived/anonymized observer metadata, then run the "
                "new-user-final command-pack target."
            ),
            "primary_required_action": (
                "Record a non-secret observer id in the reviewed receipt."
            ),
            "blocker_count": 5,
            "hidden_state_blocker_count": 0,
            "blockers": [
                "observer_id_missing",
                "observed_at_utc_missing",
                "observer_signoff_missing",
                "anonymized_notes_only_not_true",
                "anonymized_summary_missing",
            ],
        },
    )

    payload = mod.build_developer_preview_final_gate_audit(root=tmp_path)
    summary = payload["summary"]
    row = {
        item["gate_id"]: item
        for item in payload["rows"]
    }["new_user_core_workflow_observation_passed"]
    receipt_blockers = ";".join(row["receipt_blockers"])

    assert summary["status"] == "blocked_developer_preview_final_gate_audit"
    assert summary["missing_receipt_count"] == 0
    assert summary["present_blocked_receipt_count"] == 1
    assert row["present_blocked_receipt_count"] == 1
    assert row["blocker"] == (
        ".betelgeuze/developer_preview_new_user_observation_receipt.json:"
        "status=blocked_developer_preview_new_user_observation_receipt"
    )
    assert "source_blocker=observer_id_missing" in receipt_blockers
    assert "source_blocker=anonymized_summary_missing" in receipt_blockers
    assert summary["receipt_blocker_count"] == len(summary["receipt_blockers"])
    assert summary["blocker_count"] == len(summary["blockers"])
    assert summary["receipt_work_order_ready"] is False
    assert summary["receipt_work_order_row_count"] == len(payload["receipt_work_order_rows"])
    assert summary["receipt_work_order_blocked_gate_count"] == 1
    assert summary["receipt_work_order_source_blocker_count"] == 5
    assert summary["receipt_work_order_primary_source_blocker_gate_id"] == (
        "new_user_core_workflow_observation_passed"
    )
    assert summary["receipt_work_order_primary_source_blocker_receipt_artifact"] == (
        ".betelgeuze/developer_preview_new_user_observation_receipt.json"
    )
    assert summary["receipt_work_order_primary_source_blocker"] == "observer_id_missing"
    assert summary["receipt_work_order_primary_source_blocker_required_action"] == (
        "Attach the missing source evidence required by the receipt."
    )
    work_rows = {
        item["blocker_detail"]: item for item in payload["receipt_work_order_rows"]
    }
    assert work_rows["observer_id_missing"]["blocker_scope"] == "receipt_source"
    assert work_rows["observer_signoff_not_true"]["blocker_scope"] == "receipt_contract"
    assert work_rows["observer_signoff_missing"]["receipt_artifact"] == (
        ".betelgeuze/developer_preview_new_user_observation_receipt.json"
    )
    assert work_rows["observer_signoff_missing"]["required_receipt_status"] == (
        "developer_preview_new_user_observation_receipt_ready"
    )
    assert work_rows["observer_signoff_missing"]["required_true_fields"] == [
        "runbook_ready",
        "core_workflow_receipt_path_documented",
        "core_workflow_command_set_documented",
        "observation_checklist_path_documented",
        "developer_preview_exit_receipt_path_documented",
        "developer_preview_exit_command_set_documented",
        "clean_checkout_bootstrap_documented",
        "linux_bootstrap_command_set_documented",
        "windows_bootstrap_command_set_documented",
        "clean_checkout_receipt_path_documented",
        "platform_reproducibility_receipt_paths_documented",
        "observer_signoff",
        "anonymized_notes_only",
        "raw_customer_data_not_stored_in_repo",
        "customer_retained_raw_data",
    ]
    assert work_rows["observer_signoff_missing"]["required_zero_fields"] == [
        "blocker_count",
        "hidden_state_blocker_count",
    ]
    assert work_rows["observer_signoff_missing"]["required_action"] == (
        "Attach the missing source evidence required by the receipt."
    )
    assert work_rows["observer_signoff_not_true"]["required_action"] == (
        "Provide evidence so observer_signoff is true."
    )
    assert summary["next_operator_command_pack_target"] == "new-user-final"
    assert summary["next_operator_command_pack_command"] == (
        "bash runs/developer_preview_external_operator_command_pack_current.sh new-user-final"
    )
    assert summary["next_operator_command_pack_required_input_artifacts"] == [
        ".betelgeuze/developer_preview_new_user_execution_work_order.json",
        ".betelgeuze/developer_preview_new_user_execution_preflight.json",
        ".betelgeuze/developer_preview_new_user_observation_input.json",
    ]
    assert summary["new_user_observation_draft_fail_closed_ready"] is True
    assert summary["new_user_observation_input_json_present"] is True
    assert summary["new_user_observation_input_contract_ready"] is True
    assert summary["new_user_observation_input_policy_ready"] is True
    assert summary["new_user_observation_checklist_path_documented"] is True
    assert "new-user-final" in summary["new_user_observation_template_next_action"]
    assert summary["new_user_observation_primary_required_action"] == (
        "Record a non-secret observer id in the reviewed receipt."
    )


def test_developer_preview_final_gate_audit_guides_stage5_input_recovery(
    tmp_path: Path,
) -> None:
    _write_register(tmp_path)
    _write_ready_receipts(tmp_path)
    _write_json(
        tmp_path / ".betelgeuze/developer_preview_clean_checkout_benchmark_receipt.json",
        {
            "status": "blocked_developer_preview_clean_checkout_benchmark_receipt",
            "clean_checkout_benchmark_regenerated": False,
            "ai_verify_passed": True,
            "reviewed_receipt_attached": False,
            "blocker_count": 3,
            "failed_count": 2,
            "blockers": [
                "baseline_source_blocker=stage5_input_missing:--scores-csv:/tmp/missing_scores.csv",
                "baseline_task_source_error_count_nonzero",
                "reviewed_receipt_attached_not_true",
            ],
        },
    )

    payload = mod.build_developer_preview_final_gate_audit(root=tmp_path)
    summary = payload["summary"]
    source_rows = [
        row
        for row in payload["receipt_work_order_rows"]
        if row["blocker_scope"] == "receipt_source"
    ]

    assert summary["status"] == "blocked_developer_preview_final_gate_audit"
    assert summary["receipt_work_order_primary_source_blocker_gate_id"] == (
        "benchmark_results_clean_checkout_regenerated"
    )
    assert summary["receipt_work_order_primary_source_blocker"] == (
        "baseline_source_blocker=stage5_input_missing:--scores-csv:/tmp/missing_scores.csv"
    )
    assert summary["receipt_work_order_primary_source_blocker_required_action"] == (
        "Restore or regenerate the missing clean-checkout stage5 input CSVs "
        "(scores, labels, split, and expected-key queue), then rebuild the baseline receipt."
    )
    assert summary["stage5_recovery_work_order_ready"] is False
    assert summary["stage5_recovery_operator_work_order_ready"] is False
    assert summary["stage5_recovery_operator_work_order_materialized"] is False
    assert summary["stage5_recovery_row_count"] == 1
    assert summary["stage5_missing_source_artifact_count"] == 1
    assert summary["stage5_required_argument_count"] == 4
    assert summary["stage5_primary_task_key"] == "missing_scores"
    assert summary["stage5_primary_source_argument"] == "--scores-csv"
    assert summary["stage5_primary_source_artifact_path"] == "/tmp/missing_scores.csv"
    assert source_rows[0]["required_action"] == (
        "Restore or regenerate the missing clean-checkout stage5 input CSVs "
        "(scores, labels, split, and expected-key queue), then rebuild the baseline receipt."
    )
    assert source_rows[0]["source_label"] == "baseline_source_blocker"
    assert source_rows[0]["blocker_id"] == "stage5_input_missing"
    assert source_rows[0]["source_argument"] == "--scores-csv"
    assert source_rows[0]["source_artifact_path"] == "/tmp/missing_scores.csv"
    assert source_rows[0]["source_artifact_present"] is False
    assert payload["stage5_recovery_rows"] == [
        {
            "priority": "A",
            "gate_id": "benchmark_results_clean_checkout_regenerated",
            "receipt_artifact": (
                ".betelgeuze/developer_preview_clean_checkout_benchmark_receipt.json"
            ),
            "receipt_kind": "required",
            "blocker_detail": (
                "baseline_source_blocker=stage5_input_missing:"
                "--scores-csv:/tmp/missing_scores.csv"
            ),
            "source_label": "baseline_source_blocker",
            "blocker_id": "stage5_input_missing",
            "source_argument": "--scores-csv",
            "source_artifact_path": "/tmp/missing_scores.csv",
            "source_artifact_present": False,
            "task_key": "missing_scores",
            "required_stage5_arguments": [
                "--scores-csv",
                "--labels-csv",
                "--split-csv",
                "--expected-keys-csv",
            ],
            "required_stage5_argument_count": 4,
            "required_action": (
                "Restore or regenerate this stage5 input family from the clean-checkout "
                "baseline run, then rebuild the clean-checkout benchmark receipt."
            ),
            "operator_action_required": True,
            "execution_enabled": False,
            "external_state_mutated": False,
            "claim_promotion_allowed": False,
            "claim_boundary": mod.CLAIM_BOUNDARY,
        }
    ]


def test_developer_preview_final_gate_audit_uses_stage5_input_family_rows(
    tmp_path: Path,
) -> None:
    _write_register(tmp_path)
    _write_ready_receipts(tmp_path)
    receipt_path = tmp_path / ".betelgeuze/developer_preview_clean_checkout_benchmark_receipt.json"
    _write_payload(
        receipt_path,
        {
            "summary": {
                "status": "blocked_developer_preview_clean_checkout_benchmark_receipt",
                "clean_checkout_benchmark_regenerated": False,
                "ai_verify_passed": True,
                "reviewed_receipt_attached": False,
                "blocker_count": 3,
                "failed_count": 2,
                "blockers": [
                    (
                        "baseline_source_blocker=stage5_input_missing:"
                        "--scores-csv:runs/dp_task_stage3_scores.csv"
                    ),
                    "baseline_task_source_error_count_nonzero",
                    "reviewed_receipt_attached_not_true",
                ],
            },
            "stage5_input_family_rows": [
                {
                    "task_key": "dp_task",
                    "source_argument": "--scores-csv",
                    "source_artifact_path": "runs/dp_task_stage3_scores.csv",
                    "source_artifact_present": False,
                    "source_artifact_missing": True,
                    "operator_action_required": True,
                },
                {
                    "task_key": "dp_task",
                    "source_argument": "--labels-csv",
                    "source_artifact_path": "runs/dp_task_labels.csv",
                    "source_artifact_present": True,
                    "source_artifact_missing": False,
                    "operator_action_required": False,
                },
                {
                    "task_key": "dp_task",
                    "source_argument": "--split-csv",
                    "source_artifact_path": "runs/dp_task_split.csv",
                    "source_artifact_present": False,
                    "source_artifact_missing": True,
                    "operator_action_required": True,
                },
                {
                    "task_key": "dp_task",
                    "source_argument": "--expected-keys-csv",
                    "source_artifact_path": "runs/dp_task_expected_keys.csv",
                    "source_artifact_present": False,
                    "source_artifact_missing": True,
                    "operator_action_required": True,
                },
            ],
        },
    )
    stage5_csv = (
        tmp_path / ".betelgeuze/developer_preview_clean_checkout_stage5_input_family_current.csv"
    )
    stage5_md = (
        tmp_path / ".betelgeuze/developer_preview_clean_checkout_stage5_input_family_current.md"
    )
    stage5_csv.write_text("task_key,source_argument,source_artifact_path\n", encoding="utf-8")
    stage5_md.write_text("# Developer Preview Clean-Checkout Stage5 Input Family\n", encoding="utf-8")
    _write_json(
        tmp_path / "runs/developer_preview_stage5_restore_packet_current.json",
        {
            "status": "blocked_developer_preview_stage5_restore_packet",
            "stage5_fail_closed_restore_receipt_ready": True,
            "stage5_operator_restore_queue_ready": True,
            "stage5_operator_restore_queue_row_count": 3,
            "missing_source_artifact_count": 3,
            "primary_blocker": "stage5_source_artifacts_missing:3",
            "primary_missing_source_argument": "--scores-csv",
            "primary_missing_source_artifact_path": "runs/dp_task_stage3_scores.csv",
            "primary_missing_pipeline_summary_json": (
                "runs/external_validation_blind_runs/demo/set1_core_blind/files/gpcr/demo_summary.json"
            ),
            "primary_missing_pipeline_summary_present": True,
            "primary_missing_profile_json": "config/demo_profile.json",
            "primary_missing_profile_present": True,
            "primary_missing_restore_queue_ready": True,
            "primary_missing_restore_instruction": (
                "Restore or regenerate --scores-csv at runs/dp_task_stage3_scores.csv "
                "from the approved clean-checkout baseline."
            ),
            "next_required_step": (
                "Restore or regenerate the missing stage5 input CSVs from the approved "
                "clean-checkout baseline material."
            ),
        },
    )

    payload = mod.build_developer_preview_final_gate_audit(root=tmp_path)
    summary = payload["summary"]
    recovery_rows = payload["stage5_recovery_rows"]
    recovery_args = {row["source_argument"] for row in recovery_rows}

    assert summary["stage5_recovery_work_order_ready"] is False
    assert summary["stage5_recovery_operator_work_order_ready"] is True
    assert summary["stage5_recovery_operator_work_order_materialized"] is True
    assert summary["blocker_count"] == len(summary["blockers"])
    assert summary["next_operator_command_pack_target"] == "stage5-recovery"
    assert summary["next_operator_command_pack_command"] == (
        "bash runs/developer_preview_external_operator_command_pack_current.sh stage5-recovery"
    )
    assert summary["next_operator_command_pack_required_input_artifacts"] == [
        ".betelgeuze/developer_preview_clean_checkout_benchmark_receipt.json",
        ".betelgeuze/developer_preview_clean_checkout_stage5_input_family_current.csv",
        ".betelgeuze/developer_preview_clean_checkout_stage5_input_family_current.md",
    ]
    assert summary["stage5_input_family_csv_path"] == (
        ".betelgeuze/developer_preview_clean_checkout_stage5_input_family_current.csv"
    )
    assert summary["stage5_input_family_md_path"] == (
        ".betelgeuze/developer_preview_clean_checkout_stage5_input_family_current.md"
    )
    assert summary["stage5_input_family_csv_present"] is True
    assert summary["stage5_input_family_md_present"] is True
    assert summary["stage5_recovery_row_count"] == 3
    assert summary["stage5_missing_source_artifact_count"] == 3
    assert summary["stage5_restore_packet_json_present"] is True
    assert summary["stage5_restore_packet_status"] == (
        "blocked_developer_preview_stage5_restore_packet"
    )
    assert summary["stage5_restore_packet_ready"] is False
    assert summary["stage5_restore_packet_fail_closed_restore_receipt_ready"] is True
    assert summary["stage5_restore_packet_operator_restore_queue_ready"] is True
    assert summary["stage5_restore_packet_operator_restore_queue_row_count"] == 3
    assert summary["stage5_restore_packet_missing_source_artifact_count"] == 3
    assert summary["stage5_restore_packet_primary_blocker"] == (
        "stage5_source_artifacts_missing:3"
    )
    assert summary["stage5_restore_packet_primary_missing_source_argument"] == (
        "--scores-csv"
    )
    assert summary["stage5_restore_packet_primary_missing_source_artifact_path"] == (
        "runs/dp_task_stage3_scores.csv"
    )
    assert summary[
        "stage5_restore_packet_primary_missing_pipeline_summary_json"
    ] == (
        "runs/external_validation_blind_runs/demo/set1_core_blind/files/gpcr/demo_summary.json"
    )
    assert (
        summary["stage5_restore_packet_primary_missing_pipeline_summary_present"]
        is True
    )
    assert summary["stage5_restore_packet_primary_missing_profile_json"] == (
        "config/demo_profile.json"
    )
    assert summary["stage5_restore_packet_primary_missing_profile_present"] is True
    assert summary["stage5_restore_packet_primary_missing_restore_queue_ready"] is True
    assert summary["stage5_restore_packet_primary_missing_restore_instruction"] == (
        "Restore or regenerate --scores-csv at runs/dp_task_stage3_scores.csv "
        "from the approved clean-checkout baseline."
    )
    assert summary["next_required_step"] == (
        "Restore or regenerate --scores-csv at runs/dp_task_stage3_scores.csv "
        "from the approved clean-checkout baseline."
    )
    assert summary["stage5_restore_packet_operator_action_required"] is True
    command_pack = mod.build_developer_preview_external_operator_command_pack(payload)
    command_summary = command_pack["summary"]
    assert command_summary["recommended_next_target"] == "stage5-recovery"
    assert command_summary["recommended_next_action"] == (
        "Restore or regenerate --scores-csv at runs/dp_task_stage3_scores.csv "
        "from the approved clean-checkout baseline."
    )
    assert command_summary["recommended_stage5_restore_packet_status"] == (
        "blocked_developer_preview_stage5_restore_packet"
    )
    assert command_summary[
        "recommended_stage5_restore_packet_primary_missing_source_artifact_path"
    ] == "runs/dp_task_stage3_scores.csv"
    assert command_summary[
        "recommended_stage5_restore_packet_primary_missing_source_argument"
    ] == "--scores-csv"
    assert command_summary[
        "recommended_stage5_restore_packet_primary_missing_pipeline_summary_json"
    ] == (
        "runs/external_validation_blind_runs/demo/set1_core_blind/files/gpcr/demo_summary.json"
    )
    assert (
        command_summary[
            "recommended_stage5_restore_packet_primary_missing_pipeline_summary_present"
        ]
        is True
    )
    assert command_summary[
        "recommended_stage5_restore_packet_primary_missing_profile_json"
    ] == "config/demo_profile.json"
    assert (
        command_summary[
            "recommended_stage5_restore_packet_primary_missing_profile_present"
        ]
        is True
    )
    assert (
        command_summary[
            "recommended_stage5_restore_packet_primary_missing_restore_queue_ready"
        ]
        is True
    )
    assert recovery_args == {"--scores-csv", "--split-csv", "--expected-keys-csv"}
    assert [row["source_argument"] for row in recovery_rows].count("--scores-csv") == 1
    assert {row["source_label"] for row in recovery_rows} == {"stage5_input_family"}
    assert {
        row["blocker_detail"] for row in recovery_rows
    } == {
        "stage5_input_missing:--scores-csv:runs/dp_task_stage3_scores.csv",
        "stage5_input_missing:--split-csv:runs/dp_task_split.csv",
        "stage5_input_missing:--expected-keys-csv:runs/dp_task_expected_keys.csv",
    }


def test_developer_preview_final_gate_audit_ready_when_all_receipts_pass(tmp_path: Path) -> None:
    _write_register(tmp_path)
    _write_ready_receipts(tmp_path)

    payload = mod.build_developer_preview_final_gate_audit(root=tmp_path)
    summary = payload["summary"]

    assert summary["status"] == "developer_preview_final_gate_audit_ready"
    assert summary["developer_preview_clean_baseline_ready"] is True
    assert summary["developer_preview_exit_ready"] is True
    assert summary["clean_checkout_ready"] is True
    assert summary["linux_windows_reproducibility_ready"] is True
    assert summary["windows_reproducibility_ready"] is True
    assert summary["new_user_observation_ready"] is True
    assert summary["ready_gate_count"] == 6
    assert summary["blocked_gate_count"] == 0
    assert summary["blocker_count"] == 0
    assert summary["missing_receipt_count"] == 0
    assert summary["blockers"] == []
    assert summary["receipt_work_order_ready"] is True
    assert summary["receipt_work_order_row_count"] == 0
    assert summary["receipt_work_order_source_blocker_count"] == 0
    assert summary["receipt_work_order_primary_source_blocker"] == ""
    assert summary["stage5_recovery_work_order_ready"] is True
    assert summary["stage5_recovery_operator_work_order_ready"] is True
    assert summary["stage5_recovery_operator_work_order_materialized"] is False
    assert summary["stage5_recovery_row_count"] == 0
    assert summary["stage5_missing_source_artifact_count"] == 0
    assert payload["stage5_recovery_rows"] == []
    assert summary["external_operator_work_order_ready"] is True
    assert summary["external_operator_work_order_row_count"] == 4
    assert summary["external_operator_work_order_blocked_row_count"] == 0
    assert summary["external_operator_work_order_primary_flow_id"] == ""
    assert summary["external_operator_work_order_primary_blocker"] == ""
    assert summary["next_operator_command_pack_target"] == ""
    assert summary["next_operator_command_pack_command"] == ""
    assert summary["clean_checkout_operator_work_order_ready"] is True
    assert summary["linux_reproducibility_operator_work_order_ready"] is True
    assert summary["windows_reproducibility_operator_work_order_ready"] is True
    assert summary["new_user_observation_operator_work_order_ready"] is True
    assert summary["new_user_observation_draft_fail_closed_ready"] is False
    assert summary["new_user_observation_input_json_present"] is True
    assert summary["new_user_observation_input_contract_ready"] is True
    assert summary["new_user_observation_input_policy_ready"] is True
    assert summary["new_user_observation_checklist_path_documented"] is True
    assert "new-user-final" in summary["new_user_observation_template_next_action"]
    assert summary["new_user_observation_primary_required_action"] == ""
    assert all(row["ready"] is True for row in payload["external_operator_work_order_rows"])
    assert payload["receipt_work_order_rows"] == []
    assert summary["register_gate_ids_complete"] is True
    assert summary["register_fail_closed_command_contract_ready"] is True
    assert summary["register_fail_closed_missing_token_count"] == 0
    assert summary["register_contract_blocker_count"] == 0
    assert summary["claim_promotion_allowed"] is False


def test_developer_preview_final_gate_audit_separates_windows_reproducibility_work_order(
    tmp_path: Path,
) -> None:
    _write_register(tmp_path)
    _write_ready_receipts(tmp_path)
    _write_json(
        tmp_path / ".betelgeuze/developer_preview_windows_reproducibility_receipt.json",
        {
            "status": "blocked_developer_preview_platform_reproducibility_receipt",
            "command_set_passed": False,
            "windows_receipt": False,
            "blocker_count": 1,
            "blockers": ["platform_mismatch"],
        },
    )

    payload = mod.build_developer_preview_final_gate_audit(root=tmp_path)
    summary = payload["summary"]
    operator_rows = {
        row["operator_flow_id"]: row
        for row in payload["external_operator_work_order_rows"]
    }

    assert summary["status"] == "blocked_developer_preview_final_gate_audit"
    assert summary["developer_preview_exit_ready"] is False
    assert summary["clean_checkout_ready"] is True
    assert summary["linux_windows_reproducibility_ready"] is False
    assert summary["windows_reproducibility_ready"] is False
    assert summary["new_user_observation_ready"] is True
    assert summary["linux_reproducibility_operator_work_order_ready"] is True
    assert summary["windows_reproducibility_operator_work_order_ready"] is False
    assert summary["external_operator_work_order_blocked_row_count"] == 1
    assert summary["external_operator_work_order_primary_flow_id"] == (
        "windows_reproducibility_receipt"
    )
    assert summary["external_operator_work_order_primary_receipt_artifact"] == (
        ".betelgeuze/developer_preview_windows_reproducibility_receipt.json"
    )
    assert summary["external_operator_work_order_primary_blocker"] == (
        ".betelgeuze/developer_preview_windows_reproducibility_receipt.json:"
        "status=blocked_developer_preview_platform_reproducibility_receipt"
    )
    assert operator_rows["linux_reproducibility_receipt"]["ready"] is True
    assert operator_rows["windows_reproducibility_receipt"]["ready"] is False
    assert operator_rows["windows_reproducibility_receipt"]["source_blocker_count"] == 1
    assert operator_rows["windows_reproducibility_receipt"]["required_action"] == (
        "Run the same documented command set on Windows and rebuild the Windows receipt; "
        "do not copy a Linux receipt into the Windows slot."
    )


def test_developer_preview_final_gate_audit_blocks_weak_action_register(
    tmp_path: Path,
) -> None:
    path = tmp_path / "docs/developer_preview_final_gate_action_register.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(spec["gate_id"] for spec in mod.GATE_SPECS), encoding="utf-8")
    _write_ready_receipts(tmp_path)

    payload = mod.build_developer_preview_final_gate_audit(root=tmp_path)
    summary = payload["summary"]

    assert summary["status"] == "blocked_developer_preview_final_gate_audit"
    assert summary["developer_preview_clean_baseline_ready"] is False
    assert summary["ready_gate_count"] == 6
    assert summary["blocked_gate_count"] == 0
    assert summary["register_gate_ids_complete"] is True
    assert summary["register_fail_closed_command_contract_ready"] is False
    assert summary["register_fail_closed_missing_token_count"] == len(
        mod.REGISTER_FAIL_CLOSED_REQUIRED_TOKENS
    )
    assert summary["primary_blocker_id"] == "developer_preview_action_register_fail_closed_contract"
    assert summary["primary_blocker"] == summary["blockers"][0]
    assert summary["primary_blocker_detail"] == summary["blockers"][0]
    assert summary["primary_blocker"].startswith(
        "developer_preview_action_register:missing_fail_closed_token:"
    )
    assert summary["register_contract_blocker_count"] == len(
        mod.REGISTER_FAIL_CLOSED_REQUIRED_TOKENS
    )
    assert summary["blocker_count"] == len(summary["blockers"])
    assert summary["blockers"] == summary["register_contract_blockers"]
    assert summary["claim_promotion_allowed"] is False


def test_developer_preview_final_gate_audit_cli_writes_outputs(tmp_path: Path) -> None:
    _write_register(tmp_path)
    out_json = tmp_path / "runs/developer_preview_final_gate_audit_current.json"
    out_csv = tmp_path / "runs/developer_preview_final_gate_audit_current.csv"
    out_md = tmp_path / "runs/developer_preview_final_gate_audit_current.md"
    out_operator_json = (
        tmp_path / "runs/developer_preview_external_operator_work_order_current.json"
    )
    out_operator_csv = (
        tmp_path / "runs/developer_preview_external_operator_work_order_current.csv"
    )
    out_operator_md = (
        tmp_path / "runs/developer_preview_external_operator_work_order_current.md"
    )
    out_command_pack_json = (
        tmp_path / "runs/developer_preview_external_operator_command_pack_current.json"
    )
    out_command_pack_sh = (
        tmp_path / "runs/developer_preview_external_operator_command_pack_current.sh"
    )
    out_command_pack_ps1 = (
        tmp_path / "runs/developer_preview_external_operator_command_pack_current.ps1"
    )
    out_command_pack_md = (
        tmp_path / "runs/developer_preview_external_operator_command_pack_current.md"
    )

    assert mod.main(
        [
            "--root",
            str(tmp_path),
            "--register-md",
            str(tmp_path / "docs/developer_preview_final_gate_action_register.md"),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
            "--out-operator-work-order-json",
            str(out_operator_json),
            "--out-operator-work-order-csv",
            str(out_operator_csv),
            "--out-operator-work-order-md",
            str(out_operator_md),
            "--out-operator-command-pack-json",
            str(out_command_pack_json),
            "--out-operator-command-pack-sh",
            str(out_command_pack_sh),
            "--out-operator-command-pack-ps1",
            str(out_command_pack_ps1),
            "--out-operator-command-pack-md",
            str(out_command_pack_md),
        ]
    ) == 0

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["packet_type"] == (
        "developer_preview_final_gate_audit"
    )
    assert out_csv.read_text(encoding="utf-8").startswith("priority,gate_id,status,")
    md = out_md.read_text(encoding="utf-8")
    assert "Developer Preview Final Gate Audit" in md
    assert "Receipt Work Order" in md
    assert "External Operator Work Order" in md
    assert "Stage5 Source Recovery" in md
    assert "expected status" in md
    operator_payload = json.loads(out_operator_json.read_text(encoding="utf-8"))
    assert operator_payload["summary"]["packet_type"] == (
        "developer_preview_external_operator_work_order"
    )
    assert operator_payload["summary"]["status"] == (
        "developer_preview_external_operator_work_order_ready"
    )
    assert operator_payload["summary"]["operator_work_order_materialized"] is True
    assert operator_payload["summary"]["expected_operator_flow_count"] == 4
    assert operator_payload["summary"]["operator_flow_count"] == 4
    assert operator_payload["summary"]["operator_flow_ready"] is False
    assert operator_payload["summary"]["blocked_operator_flow_count"] == 4
    assert operator_payload["rows"][0]["operator_flow_id"] == (
        "clean_checkout_benchmark_receipt"
    )
    assert out_operator_csv.read_text(encoding="utf-8").startswith(
        "operator_flow_id,gate_id,label,"
    )
    operator_md = out_operator_md.read_text(encoding="utf-8")
    assert "Developer Preview External Operator Work Order" in operator_md
    assert "Clean checkout benchmark receipt" in operator_md
    command_pack_payload = json.loads(out_command_pack_json.read_text(encoding="utf-8"))
    command_pack_summary = command_pack_payload["summary"]
    assert command_pack_summary["packet_type"] == (
        "developer_preview_external_operator_command_pack"
    )
    assert command_pack_summary["status"] == (
        "developer_preview_external_operator_command_pack_ready"
    )
    assert command_pack_summary["command_pack_ready"] is True
    assert command_pack_summary["blockers"] == []
    assert command_pack_summary["blocker_count"] == 0
    assert command_pack_summary["primary_blocker"] == ""
    assert command_pack_summary["target_count"] == 7
    assert command_pack_summary["required_env_var_count"] == 3
    assert command_pack_summary["required_input_artifact_count"] == 6
    assert command_pack_summary["platform_guard_count"] == 2
    assert command_pack_summary["optional_export_env_var"] == "DEVELOPER_PREVIEW_EXPORT_DIR"
    assert command_pack_summary["powershell_script_path"] == (
        "runs/developer_preview_external_operator_command_pack_current.ps1"
    )
    assert command_pack_summary["powershell_targets"] == ["windows-repro", "final-gate"]
    assert command_pack_summary["powershell_target_count"] == 2
    assert command_pack_summary["powershell_scope"].startswith(
        "PowerShell command pack intentionally supports only windows-repro"
    )
    assert command_pack_summary["windows_repro_powershell_command_pack_ready"] is True
    assert command_pack_summary["shell_platform_guard_normalizes_observed_platform"] is True
    assert command_pack_summary["shell_platform_guard_accepts_git_bash_windows"] is True
    assert command_pack_summary["clean_checkout_default_workdir_pattern"] == (
        "${RUNNER_TEMP:-${TMPDIR:-/tmp}}/betelgeuze-developer-preview-<UTC timestamp>"
    )
    assert command_pack_summary["clean_checkout_existing_workdir_fail_closed"] is True
    assert command_pack_summary["operator_must_explicitly_run_target"] is True
    assert command_pack_summary["human_review_required_before_external_operator_run"] is True
    assert command_pack_summary["generated_scripts_non_executable_by_default"] is True
    assert command_pack_summary["optional_clean_checkout_ref_env_var"] == (
        "DEVELOPER_PREVIEW_REF"
    )
    assert command_pack_summary["clean_checkout_ref_checkout_supported"] is True
    assert command_pack_summary["recommended_next_target"] == "clean-checkout"
    assert command_pack_summary["recommended_next_command"] == (
        "bash runs/developer_preview_external_operator_command_pack_current.sh clean-checkout"
    )
    assert command_pack_summary["recommended_next_action"] == (
        "Run the clean-checkout benchmark regeneration command from the action register and attach "
        "a reviewed receipt at .betelgeuze/developer_preview_clean_checkout_benchmark_receipt.json."
    )
    shell_pack = out_command_pack_sh.read_text(encoding="utf-8")
    assert "require_env DEVELOPER_PREVIEW_REPO_URL" in shell_pack
    assert "require_env DEVELOPER_PREVIEW_REVIEWER_ID" in shell_pack
    assert "require_env DEVELOPER_PREVIEW_REVIEWED_AT_UTC" in shell_pack
    assert "clean checkout workdir already exists" in shell_pack
    assert "git clone --no-hardlinks" in shell_pack
    assert 'git fetch origin "${DEVELOPER_PREVIEW_REF}"' in shell_pack
    assert "require_platform linux" in shell_pack
    assert "require_platform windows" in shell_pack
    assert "windows*|win32*|cygwin*|cygwin_nt*|msys*|mingw*" in shell_pack
    assert (
        "require_file .betelgeuze/developer_preview_clean_checkout_stage5_input_family_current.csv"
        in shell_pack
    )
    assert (
        "require_file .betelgeuze/developer_preview_new_user_observation_input.json"
        in shell_pack
    )
    assert (
        "tools/product/build_developer_preview_new_user_observation_receipt.py"
        in shell_pack
    )
    assert "usage: $0 {clean-checkout|stage5-recovery|linux-repro|windows-repro|new-user-draft|new-user-final|final-gate}" in shell_pack
    powershell_pack = out_command_pack_ps1.read_text(encoding="utf-8")
    assert "[ValidateSet('windows-repro','final-gate')]" in powershell_pack
    assert "Require-Platform 'windows'" in powershell_pack
    assert "developer_preview_windows_reproducibility_receipt.json" in powershell_pack
    assert command_pack_summary["recommended_next_required_platform"] == "fresh local clone"
    assert command_pack_summary["recommended_next_required_env_vars"] == [
        "DEVELOPER_PREVIEW_REPO_URL",
        "DEVELOPER_PREVIEW_REVIEWER_ID",
        "DEVELOPER_PREVIEW_REVIEWED_AT_UTC",
    ]
    assert command_pack_summary["recommended_stage5_restore_packet_path"] == (
        "runs/developer_preview_stage5_restore_packet_current.json"
    )
    assert command_pack_summary["recommended_stage5_restore_packet_status"] == ""
    assert command_pack_summary[
        "recommended_stage5_restore_packet_missing_source_artifact_count"
    ] == 0
    assert command_pack_summary[
        "recommended_stage5_restore_packet_primary_missing_source_artifact_path"
    ] == ""
    assert command_pack_summary[
        "recommended_stage5_restore_packet_primary_missing_restore_instruction"
    ] == ""
    assert "generated receipt artifacts" in command_pack_summary[
        "optional_export_behavior"
    ]
    assert "clean-checkout" in command_pack_summary["targets"]
    assert "stage5-recovery" in command_pack_summary["targets"]
    assert "windows-repro" in command_pack_summary["targets"]
    command_pack_rows = {row["target"]: row for row in command_pack_payload["rows"]}
    assert command_pack_rows["clean-checkout"]["required_env_vars"] == [
        "DEVELOPER_PREVIEW_REPO_URL",
        "DEVELOPER_PREVIEW_REVIEWER_ID",
        "DEVELOPER_PREVIEW_REVIEWED_AT_UTC",
    ]
    assert (
        ".betelgeuze/developer_preview_clean_checkout_source_provenance.json"
        in command_pack_rows["clean-checkout"]["receipt_artifacts"]
    )
    assert (
        ".betelgeuze/developer_preview_external_baselines/developer_preview_clean_checkout_status.txt"
        in command_pack_rows["clean-checkout"]["receipt_artifacts"]
    )
    clean_checkout_commands = "\n".join(command_pack_rows["clean-checkout"]["commands"])
    assert 'workdir="$(resolve_clean_checkout_workdir)"' in clean_checkout_commands
    assert 'if [[ -n "${DEVELOPER_PREVIEW_REF:-}" ]]' in clean_checkout_commands
    assert 'git fetch origin "${DEVELOPER_PREVIEW_REF}"' in clean_checkout_commands
    assert "git checkout --detach FETCH_HEAD" in clean_checkout_commands
    assert (
        "write_clean_checkout_source_provenance "
        ".betelgeuze/developer_preview_clean_checkout_source_provenance.json"
        in clean_checkout_commands
    )
    assert (
        "--checkout-provenance-json "
        ".betelgeuze/developer_preview_clean_checkout_source_provenance.json"
        in clean_checkout_commands
    )
    assert "set +e" in clean_checkout_commands
    assert "baseline_rc=$?" in clean_checkout_commands
    assert "run_external_validation_baselines_exit_code=%s" in clean_checkout_commands
    assert "build_developer_preview_clean_checkout_benchmark_receipt.py" in clean_checkout_commands
    assert 'export_artifacts "clean-checkout"' in clean_checkout_commands
    assert (
        '" .betelgeuze/developer_preview_clean_checkout_benchmark_receipt.json"'
        not in clean_checkout_commands
    )
    assert (
        '".betelgeuze/developer_preview_clean_checkout_benchmark_receipt.json"'
        in clean_checkout_commands
    )
    assert command_pack_rows["clean-checkout"]["optional_export_env_var"] == (
        "DEVELOPER_PREVIEW_EXPORT_DIR"
    )
    assert command_pack_rows["stage5-recovery"]["required_input_artifacts"] == [
        ".betelgeuze/developer_preview_clean_checkout_benchmark_receipt.json",
        ".betelgeuze/developer_preview_clean_checkout_stage5_input_family_current.csv",
        ".betelgeuze/developer_preview_clean_checkout_stage5_input_family_current.md",
    ]
    assert (
        "runs/developer_preview_stage5_restore_packet_current.json"
        in command_pack_rows["stage5-recovery"]["receipt_artifacts"]
    )
    assert (
        "runs/developer_preview_stage5_restore_packet_current.csv"
        in command_pack_rows["stage5-recovery"]["receipt_artifacts"]
    )
    assert (
        "runs/developer_preview_stage5_restore_packet_current.md"
        in command_pack_rows["stage5-recovery"]["receipt_artifacts"]
    )
    stage5_recovery_commands = "\n".join(command_pack_rows["stage5-recovery"]["commands"])
    assert "build_developer_preview_final_gate_audit.py" in stage5_recovery_commands
    assert "build_developer_preview_stage5_restore_packet.py" in stage5_recovery_commands
    assert stage5_recovery_commands.index(
        "build_developer_preview_stage5_restore_packet.py"
    ) < stage5_recovery_commands.index("build_developer_preview_final_gate_audit.py")
    assert (
        "--stage5-input-family-csv "
        ".betelgeuze/developer_preview_clean_checkout_stage5_input_family_current.csv"
        in stage5_recovery_commands
    )
    assert (
        "--out-json runs/developer_preview_stage5_restore_packet_current.json"
        in stage5_recovery_commands
    )
    assert 'export_artifacts "stage5-recovery"' in stage5_recovery_commands
    assert (
        '"runs/developer_preview_stage5_restore_packet_current.json"'
        in stage5_recovery_commands
    )
    assert command_pack_rows["linux-repro"]["platform_guard"] == "linux"
    assert command_pack_rows["windows-repro"]["platform_guard"] == "windows"
    assert command_pack_rows["new-user-final"]["required_env_vars"] == []
    assert command_pack_rows["new-user-final"]["required_input_artifacts"] == [
        ".betelgeuze/developer_preview_new_user_execution_work_order.json",
        ".betelgeuze/developer_preview_new_user_execution_preflight.json",
        ".betelgeuze/developer_preview_new_user_observation_input.json",
    ]
    assert "--platform windows" in "\n".join(command_pack_rows["windows-repro"]["commands"])
    assert (
        "--observation-input-json .betelgeuze/developer_preview_new_user_observation_input.json"
        in "\n".join(command_pack_rows["new-user-final"]["commands"])
    )
    assert "--out-observation-input-template-json" in "\n".join(
        command_pack_rows["new-user-final"]["commands"]
    )
    assert (
        ".betelgeuze/developer_preview_new_user_observation_input_template.json"
        in command_pack_rows["new-user-draft"]["receipt_artifacts"]
    )
    assert (
        ".betelgeuze/developer_preview_new_user_observation_input.json"
        in command_pack_rows["new-user-draft"]["receipt_artifacts"]
    )
    command_pack_sh = out_command_pack_sh.read_text(encoding="utf-8")
    assert out_command_pack_sh.stat().st_mode & 0o111 == 0
    assert out_command_pack_ps1.stat().st_mode & 0o111 == 0
    assert command_pack_sh.startswith("#!/usr/bin/env bash")
    assert "detect_python()" in command_pack_sh
    assert "COMMAND_PACK_ROOT=\"$(pwd)\"" in command_pack_sh
    assert "DEVELOPER_PREVIEW_EXPORT_DIR" in command_pack_sh
    assert "export_artifacts()" in command_pack_sh
    assert "resolve_clean_checkout_workdir()" in command_pack_sh
    assert "write_clean_checkout_source_provenance()" in command_pack_sh
    assert "source_repo_url_fingerprint" in command_pack_sh
    assert "source_ref_requested" in command_pack_sh
    assert "DEVELOPER_PREVIEW_REF" in command_pack_sh
    assert "source_remote_url_redacted" in command_pack_sh
    assert "git_status_porcelain_empty" in command_pack_sh
    assert (
        "${RUNNER_TEMP:-${TMPDIR:-/tmp}}/betelgeuze-developer-preview-$(date -u +%Y%m%dT%H%M%SZ)"
        in command_pack_sh
    )
    assert "clean checkout workdir already exists" in command_pack_sh
    assert 'git fetch origin "${DEVELOPER_PREVIEW_REF}"' in command_pack_sh
    assert "git checkout --detach FETCH_HEAD" in command_pack_sh
    assert "exit 7" in command_pack_sh
    assert "cp -R \"${artifact}\"" in command_pack_sh
    assert "PYTHON_BIN=\"$(detect_python)\"" in command_pack_sh
    assert "observed_raw=\"$(${PYTHON_BIN} -c 'import platform; print(platform.system().lower())')\"" in command_pack_sh
    assert "windows*|win32*|cygwin*|cygwin_nt*|msys*|mingw*) observed=\"windows\" ;;" in command_pack_sh
    assert "target ${target} requires ${expected}; observed ${observed_raw}" in command_pack_sh
    assert "\"${PYTHON_BIN}\" -m pytest -q" in command_pack_sh
    assert "require_file()" in command_pack_sh
    assert "case \"$target\" in" in command_pack_sh
    assert "require_env DEVELOPER_PREVIEW_REPO_URL" in command_pack_sh
    assert "baseline_rc=$?" in command_pack_sh
    assert "developer_preview_clean_checkout_status.txt" in command_pack_sh
    assert "build_developer_preview_clean_checkout_benchmark_receipt.py" in command_pack_sh
    assert (
        "require_file .betelgeuze/developer_preview_new_user_execution_work_order.json"
        in command_pack_sh
    )
    assert (
        "require_file .betelgeuze/developer_preview_new_user_execution_preflight.json"
        in command_pack_sh
    )
    assert (
        "require_file .betelgeuze/developer_preview_new_user_observation_input.json"
        in command_pack_sh
    )
    assert "developer_preview_new_user_observation_input_template.json" in command_pack_sh
    assert (
        "require_file .betelgeuze/developer_preview_clean_checkout_stage5_input_family_current.csv"
        in command_pack_sh
    )
    assert "require_platform linux" in command_pack_sh
    assert "require_platform windows" in command_pack_sh
    assert "clean-checkout)" in command_pack_sh
    assert "stage5-recovery)" in command_pack_sh
    assert "windows-repro)" in command_pack_sh
    command_pack_ps1 = out_command_pack_ps1.read_text(encoding="utf-8")
    assert "ValidateSet('windows-repro','final-gate')" in command_pack_ps1
    assert "Use the shell command pack for clean-checkout" in command_pack_ps1
    assert "Require-Platform 'windows'" in command_pack_ps1
    assert "developer_preview_windows_ai_verify.log" in command_pack_ps1
    assert "developer_preview_windows_reproducibility_pytest.xml" in command_pack_ps1
    assert "--platform','windows" in command_pack_ps1
    assert "DEVELOPER_PREVIEW_EXPORT_DIR" in command_pack_ps1
    assert "--out-operator-command-pack-ps1" in command_pack_ps1
    command_pack_md = out_command_pack_md.read_text(encoding="utf-8")
    assert "Developer Preview External Operator Command Pack" in command_pack_md
    assert "bash runs/developer_preview_external_operator_command_pack_current.sh <target>" in command_pack_md
    assert (
        "pwsh -File runs/developer_preview_external_operator_command_pack_current.ps1 -Target windows-repro"
        in command_pack_md
    )
    assert "optional_export_env_var" in command_pack_md
    assert "powershell_scope" in command_pack_md
    assert "shell_platform_guard_accepts_git_bash_windows" in command_pack_md
    assert "clean_checkout_default_workdir_pattern" in command_pack_md
    assert "clean_checkout_existing_workdir_fail_closed" in command_pack_md
    assert "optional_clean_checkout_ref_env_var" in command_pack_md
    assert "clean_checkout_ref_checkout_supported" in command_pack_md
    assert "timestamped fresh clone" in command_pack_md
    assert "hidden local state" in command_pack_md
    assert "stage5-recovery" in command_pack_md
    assert "build the stage5 restore packet" in command_pack_md
    assert "recommended_next_target" in command_pack_md
    assert "recommended_stage5_restore_packet_primary_missing_source_argument" in (
        command_pack_md
    )
    assert "recommended_stage5_restore_packet_primary_missing_pipeline_summary_json" in (
        command_pack_md
    )
    assert "recommended_stage5_restore_packet_primary_missing_profile_json" in (
        command_pack_md
    )
    assert "recommended_stage5_restore_packet_primary_missing_restore_queue_ready" in (
        command_pack_md
    )
    assert (
        "bash runs/developer_preview_external_operator_command_pack_current.sh clean-checkout"
        in command_pack_md
    )
    assert "required_env_vars" in command_pack_md
    assert "required_inputs" in command_pack_md
