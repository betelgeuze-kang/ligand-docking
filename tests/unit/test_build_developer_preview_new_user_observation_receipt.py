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


def test_new_user_observation_receipt_ready_with_signoff(tmp_path: Path) -> None:
    work_order, preflight = _write_ready_sources(tmp_path)

    payload = mod.build_developer_preview_new_user_observation_receipt(
        work_order_json=work_order,
        preflight_json=preflight,
        observer_id="reviewer-a",
        observed_at_utc="2026-07-03T00:00:00Z",
        anonymized_summary="Completed core workflow with no hidden local state.",
        observer_signoff=True,
        anonymized_notes_only=True,
        root=tmp_path,
    )
    summary = payload["summary"]

    assert summary["status"] == "developer_preview_new_user_observation_receipt_ready"
    assert summary["observer_signoff"] is True
    assert summary["anonymized_notes_only"] is True
    assert summary["blocker_count"] == 0
    assert summary["hidden_state_blocker_count"] == 0
    assert summary["observation_review_required_field_count"] == 8
    assert summary["observation_review_ready_field_count"] == 8
    assert summary["observation_review_blocked_field_count"] == 0
    assert summary["observation_review_primary_field_id"] == ""
    assert summary["work_order_ready"] is True
    assert summary["preflight_ready"] is True
    assert summary["raw_customer_data_stored_in_repo"] is False
    assert summary["customer_retained_raw_data"] is True
    assert summary["claim_promotion_allowed"] is False


def test_new_user_observation_receipt_blocks_without_signoff(tmp_path: Path) -> None:
    work_order, preflight = _write_ready_sources(tmp_path)

    payload = mod.build_developer_preview_new_user_observation_receipt(
        work_order_json=work_order,
        preflight_json=preflight,
        hidden_state_blockers=["operator needed an undocumented local path"],
        root=tmp_path,
    )
    summary = payload["summary"]
    blockers = ";".join(summary["blockers"])
    template_rows = {
        row["field_id"]: row for row in payload["observation_review_template_rows"]
    }

    assert summary["status"] == "blocked_developer_preview_new_user_observation_receipt"
    assert summary["observer_signoff"] is False
    assert summary["anonymized_notes_only"] is False
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
    assert summary["observation_review_ready_field_count"] == 2
    assert summary["observation_review_blocked_field_count"] == 6
    assert summary["observation_review_primary_field_id"] == "observer_id_present"
    assert summary["observation_review_primary_blocker"] == "observer_id_missing"
    assert summary["observation_review_primary_required_action"] == (
        "Record a non-secret observer id in the reviewed receipt."
    )
    assert "observer_signoff_missing" in blockers
    assert "anonymized_notes_only_not_true" in blockers
    assert "hidden_state_blockers_present" in blockers
    assert template_rows["observer_signoff"]["status"] == "blocked"
    assert template_rows["hidden_state_blockers_absent"]["observed"] == (
        "hidden_state_blocker_count=1"
    )
    assert template_rows["raw_customer_data_not_stored_in_repo"]["status"] == "pass"
    assert all(row["execution_enabled"] is False for row in template_rows.values())


def test_new_user_observation_receipt_cli_writes_outputs(tmp_path: Path) -> None:
    work_order, preflight = _write_ready_sources(tmp_path)
    out_json = tmp_path / ".betelgeuze/developer_preview_new_user_observation_receipt.json"
    out_md = tmp_path / ".betelgeuze/developer_preview_new_user_observation_receipt.md"

    assert mod.main(
        [
            "--work-order-json",
            str(work_order),
            "--preflight-json",
            str(preflight),
            "--observer-id",
            "reviewer-a",
            "--observed-at-utc",
            "2026-07-03T00:00:00Z",
            "--anonymized-summary",
            "Completed core workflow with no hidden local state.",
            "--observer-signoff",
            "--anonymized-notes-only",
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ]
    ) == 0

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["packet_type"] == "developer_preview_new_user_observation_receipt"
    assert "Developer Preview New-User Observation Receipt" in out_md.read_text(encoding="utf-8")
    assert "Observation Review Template" in out_md.read_text(encoding="utf-8")
