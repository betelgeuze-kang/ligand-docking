from __future__ import annotations

import json
from pathlib import Path

from tools.product import build_developer_preview_final_gate_audit as mod


def _write_json(path: Path, summary: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"summary": summary}, indent=2) + "\n", encoding="utf-8")


def _write_register(root: Path) -> None:
    path = root / "docs/developer_preview_final_gate_action_register.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(spec["gate_id"] for spec in mod.GATE_SPECS), encoding="utf-8")


def _write_ready_receipts(root: Path) -> None:
    _write_json(
        root / ".betelgeuze/developer_preview_clean_checkout_benchmark_receipt.json",
        {
            "status": "developer_preview_clean_checkout_benchmark_receipt_ready",
            "clean_checkout_benchmark_regenerated": True,
            "ai_verify_passed": True,
            "reviewed_receipt_attached": True,
            "blocker_count": 0,
            "failed_count": 0,
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
            "observer_signoff": True,
            "anonymized_notes_only": True,
            "blocker_count": 0,
            "hidden_state_blocker_count": 0,
        },
    )


def test_developer_preview_final_gate_audit_blocks_missing_receipts(tmp_path: Path) -> None:
    _write_register(tmp_path)

    payload = mod.build_developer_preview_final_gate_audit(root=tmp_path)
    summary = payload["summary"]
    rows = {row["gate_id"]: row for row in payload["rows"]}

    assert summary["status"] == "blocked_developer_preview_final_gate_audit"
    assert summary["developer_preview_clean_baseline_ready"] is False
    assert summary["gate_count"] == 6
    assert summary["ready_gate_count"] == 0
    assert summary["blocked_gate_count"] == 6
    assert summary["primary_blocker_id"] == "benchmark_results_clean_checkout_regenerated"
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
        "ai_verify_passed",
        "reviewed_receipt_attached",
    ]
    assert payload["receipt_work_order_rows"][0]["required_zero_fields"] == [
        "blocker_count",
        "failed_count",
    ]
    assert summary["receipt_work_order_primary_required_receipt_status"] == (
        "developer_preview_clean_checkout_benchmark_receipt_ready"
    )
    assert summary["receipt_work_order_primary_required_true_fields"] == [
        "clean_checkout_benchmark_regenerated",
        "ai_verify_passed",
        "reviewed_receipt_attached",
    ]
    assert summary["receipt_work_order_primary_required_zero_fields"] == [
        "blocker_count",
        "failed_count",
    ]
    assert summary["receipt_work_order_source_blocker_count"] == 0
    assert summary["receipt_work_order_primary_source_blocker_gate_id"] == ""
    assert summary["receipt_work_order_primary_source_blocker_receipt_artifact"] == ""
    assert summary["receipt_work_order_primary_source_blocker"] == ""
    assert summary["receipt_work_order_primary_source_blocker_required_action"] == ""
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
        "observer_signoff",
        "anonymized_notes_only",
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


def test_developer_preview_final_gate_audit_ready_when_all_receipts_pass(tmp_path: Path) -> None:
    _write_register(tmp_path)
    _write_ready_receipts(tmp_path)

    payload = mod.build_developer_preview_final_gate_audit(root=tmp_path)
    summary = payload["summary"]

    assert summary["status"] == "developer_preview_final_gate_audit_ready"
    assert summary["developer_preview_clean_baseline_ready"] is True
    assert summary["ready_gate_count"] == 6
    assert summary["blocked_gate_count"] == 0
    assert summary["missing_receipt_count"] == 0
    assert summary["blockers"] == []
    assert summary["receipt_work_order_ready"] is True
    assert summary["receipt_work_order_row_count"] == 0
    assert summary["receipt_work_order_source_blocker_count"] == 0
    assert summary["receipt_work_order_primary_source_blocker"] == ""
    assert payload["receipt_work_order_rows"] == []
    assert summary["claim_promotion_allowed"] is False


def test_developer_preview_final_gate_audit_cli_writes_outputs(tmp_path: Path) -> None:
    _write_register(tmp_path)
    out_json = tmp_path / "runs/developer_preview_final_gate_audit_current.json"
    out_csv = tmp_path / "runs/developer_preview_final_gate_audit_current.csv"
    out_md = tmp_path / "runs/developer_preview_final_gate_audit_current.md"

    assert mod.main(
        [
            "--register-md",
            str(tmp_path / "docs/developer_preview_final_gate_action_register.md"),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    ) == 0

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["packet_type"] == (
        "developer_preview_final_gate_audit"
    )
    assert out_csv.read_text(encoding="utf-8").startswith("priority,gate_id,status,")
    md = out_md.read_text(encoding="utf-8")
    assert "Developer Preview Final Gate Audit" in md
    assert "Receipt Work Order" in md
    assert "expected status" in md
