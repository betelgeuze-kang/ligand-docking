from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import build_customer_shadow_evidence_status as mod


FIELDNAMES = [
    "case_id",
    "row_kind",
    "raw_data_custody",
    "customer_retained_raw_data",
    "redistribution_allowed",
    "raw_data_stored_in_repo",
    "derived_metadata_fields",
    "anonymized_result_summary",
    "reviewer_signoff_status",
    "reviewer_id",
    "reviewed_at_utc",
    "source_artifact_fingerprint",
]


def _write_intake(path: Path, rows: list[dict[str, str]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames or FIELDNAMES, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _valid_row(case_id: str, row_kind: str = "customer_shadow") -> dict[str, str]:
    return {
        "case_id": case_id,
        "row_kind": row_kind,
        "raw_data_custody": "customer_retained",
        "customer_retained_raw_data": "true",
        "redistribution_allowed": "false",
        "raw_data_stored_in_repo": "false",
        "derived_metadata_fields": (
            "case_domain;input_size_class;runner_profile;result_metric_summary;artifact_fingerprint"
        ),
        "anonymized_result_summary": "Reviewed anonymized aggregate metrics for retained customer input.",
        "reviewer_signoff_status": "approved",
        "reviewer_id": "reviewer_alpha",
        "reviewed_at_utc": "2026-06-29T00:00:00Z",
        "source_artifact_fingerprint": "a" * 64,
    }


def test_header_only_template_blocks_until_three_real_cases(tmp_path: Path) -> None:
    intake = tmp_path / "intake.csv"
    _write_intake(intake, [])

    payload = mod.build_customer_shadow_evidence_status(intake_csv=str(intake))

    summary = payload["summary"]
    assert summary["status"] == "blocked_customer_shadow_evidence_status"
    assert summary["customer_shadow_intake_schema_ready"] is True
    assert summary["real_customer_shadow_row_count"] == 0
    assert summary["completed_customer_shadow_case_count"] == 0
    assert summary["missing_completed_customer_shadow_case_count"] == 3
    assert summary["customer_retained_raw_data_count"] == 0
    assert summary["redistribution_allowed_false_count"] == 0
    assert summary["anonymized_result_summary_count"] == 0
    assert summary["reviewer_signoff_count"] == 0
    assert summary["customer_shadow_work_order_ready"] is False
    assert summary["customer_shadow_work_order_row_count"] == 3
    assert summary["customer_shadow_work_order_primary_case_slot_id"] == "customer_shadow_case_1"
    assert summary["customer_shadow_work_order_primary_operator_csv"] == str(intake)
    assert summary["customer_shadow_work_order_primary_required_row_kind"] == "customer_shadow"
    assert summary["customer_shadow_work_order_primary_required_raw_data_custody"] == "customer_retained"
    assert summary["customer_shadow_work_order_primary_required_customer_retained_raw_data"] is True
    assert summary["customer_shadow_work_order_primary_required_redistribution_allowed"] is False
    assert summary["customer_shadow_work_order_primary_required_raw_data_stored_in_repo"] is False
    assert summary["customer_shadow_work_order_primary_required_derived_metadata_fields"] == sorted(
        mod.REQUIRED_DERIVED_METADATA_FIELDS
    )
    assert summary["customer_shadow_work_order_primary_required_reviewer_signoff_status"] == "approved"
    assert summary["customer_shadow_work_order_primary_required_source_artifact_fingerprint"] == "sha256"
    assert summary["blocker_count"] == 1
    assert summary["paid_pilot_evidence_ready"] is False
    assert summary["paid_pilot_claim_allowed"] is False
    assert summary["commercial_readiness_promotion_allowed"] is False
    assert summary["paid_pilot_requirement_ids"] == [
        "customer_shadow_intake_schema_ready",
        "completed_customer_shadow_cases",
        "real_customer_shadow_rows",
        "customer_retained_raw_data",
        "redistribution_allowed_false",
        "anonymized_result_summary",
        "reviewer_signoff",
        "no_invalid_customer_shadow_rows",
        "customer_raw_data_not_stored_in_repo",
        "redistribution_allowed_required_value_false",
        "customer_shadow_work_order_closed",
        "paid_pilot_evidence_ready",
        "paid_pilot_claim_allowed",
        "commercial_readiness_promotion_allowed",
    ]
    assert summary["paid_pilot_requirement_row_count"] == 14
    assert summary["paid_pilot_requirement_ready_row_count"] == 4
    assert summary["paid_pilot_requirement_blocked_row_count"] == 10
    assert summary["paid_pilot_requirement_primary_id"] == "completed_customer_shadow_cases"
    assert summary["paid_pilot_requirement_primary_blocker"] == (
        "completed_customer_shadow_cases_below_required:0/3"
    )
    assert summary["paid_pilot_requirement_primary_action"] == (
        "Collect reviewed customer-shadow rows that count toward the minimum."
    )
    assert payload["blockers"][0]["case_id"] == "minimum_completed_cases"
    requirements = {row["requirement_id"]: row for row in payload["paid_pilot_requirement_rows"]}
    assert requirements["customer_shadow_intake_schema_ready"]["ready"] is True
    assert requirements["completed_customer_shadow_cases"]["observed_count"] == 0
    assert requirements["completed_customer_shadow_cases"]["required_count"] == 3
    assert requirements["customer_shadow_work_order_closed"]["blocker"] == (
        "customer_shadow_work_order_rows_open:3"
    )
    assert all(
        row["paid_pilot_wording_allowed"] is False
        and row["claim_promotion_allowed"] is False
        and row["execution_enabled"] is False
        and row["external_state_mutated"] is False
        for row in payload["paid_pilot_requirement_rows"]
    )
    work_orders = payload["customer_shadow_work_order_rows"]
    assert [row["case_slot_id"] for row in work_orders] == [
        "customer_shadow_case_1",
        "customer_shadow_case_2",
        "customer_shadow_case_3",
    ]
    assert work_orders[0]["required_redistribution_allowed"] is False
    assert work_orders[0]["required_customer_retained_raw_data"] is True
    assert work_orders[0]["required_raw_data_stored_in_repo"] is False
    assert work_orders[0]["execution_enabled"] is False
    assert work_orders[0]["paid_pilot_claim_allowed"] is False


def test_mock_fixture_is_valid_but_does_not_count_toward_minimum(tmp_path: Path) -> None:
    intake = tmp_path / "intake.csv"
    _write_intake(intake, [_valid_row("mock_customer_shadow_fixture", "mock_fixture")])

    payload = mod.build_customer_shadow_evidence_status(intake_csv=str(intake))

    summary = payload["summary"]
    assert summary["status"] == "blocked_customer_shadow_evidence_status"
    assert summary["real_customer_shadow_row_count"] == 0
    assert summary["mock_fixture_row_count"] == 1
    assert summary["invalid_row_count"] == 0
    assert summary["completed_customer_shadow_case_count"] == 0
    assert summary["customer_retained_raw_data_count"] == 0
    assert summary["redistribution_allowed_false_count"] == 0
    assert summary["anonymized_result_summary_count"] == 0
    assert summary["reviewer_signoff_count"] == 0
    assert summary["customer_shadow_work_order_ready"] is False
    assert summary["customer_shadow_work_order_row_count"] == 3
    assert summary["blocker_count"] == 1
    assert payload["rows"][0]["completed_schema_valid"] is True
    assert payload["rows"][0]["counts_toward_minimum"] is False
    assert payload["customer_shadow_work_order_rows"][0]["case_slot_id"] == "customer_shadow_case_1"


def test_three_completed_customer_shadow_rows_ready_but_do_not_promote_claims(tmp_path: Path) -> None:
    intake = tmp_path / "intake.csv"
    _write_intake(intake, [_valid_row("case_1"), _valid_row("case_2"), _valid_row("case_3")])

    payload = mod.build_customer_shadow_evidence_status(intake_csv=str(intake))

    summary = payload["summary"]
    assert summary["status"] == "customer_shadow_evidence_status_ready"
    assert summary["real_customer_shadow_row_count"] == 3
    assert summary["completed_customer_shadow_case_count"] == 3
    assert summary["customer_shadow_minimum_met"] is True
    assert summary["customer_retained_raw_data_count"] == 3
    assert summary["redistribution_allowed_false_count"] == 3
    assert summary["anonymized_result_summary_count"] == 3
    assert summary["reviewer_signoff_count"] == 3
    assert summary["blocker_count"] == 0
    assert summary["paid_pilot_evidence_ready"] is True
    assert summary["paid_pilot_claim_allowed"] is False
    assert summary["commercial_readiness_promotion_allowed"] is False
    assert summary["readiness_promotion_allowed"] is False
    assert summary["customer_shadow_work_order_ready"] is True
    assert summary["customer_shadow_work_order_row_count"] == 0
    assert summary["paid_pilot_requirement_row_count"] == 14
    assert summary["paid_pilot_requirement_ready_row_count"] == 12
    assert summary["paid_pilot_requirement_blocked_row_count"] == 2
    assert summary["paid_pilot_requirement_primary_id"] == "paid_pilot_claim_allowed"
    assert summary["paid_pilot_requirement_primary_blocker"] == "paid_pilot_claim_not_approved"
    requirement_rows = {
        row["requirement_id"]: row for row in payload["paid_pilot_requirement_rows"]
    }
    assert requirement_rows["completed_customer_shadow_cases"]["ready"] is True
    assert requirement_rows["paid_pilot_evidence_ready"]["ready"] is True
    assert requirement_rows["paid_pilot_claim_allowed"]["ready"] is False
    assert requirement_rows["commercial_readiness_promotion_allowed"]["ready"] is False
    assert summary["customer_shadow_work_order_primary_case_slot_id"] == ""
    assert summary["customer_shadow_work_order_primary_operator_csv"] == ""
    assert summary["customer_shadow_work_order_primary_required_derived_metadata_fields"] == []
    assert payload["blockers"] == []
    assert payload["customer_shadow_work_order_rows"] == []


def test_reviewed_at_must_be_timezone_aware_iso_timestamp(tmp_path: Path) -> None:
    row = _valid_row("case_1")
    row["reviewed_at_utc"] = "2026-06-29"
    intake = tmp_path / "intake.csv"
    _write_intake(intake, [row])

    payload = mod.build_customer_shadow_evidence_status(intake_csv=str(intake))

    assert payload["summary"]["status"] == "blocked_customer_shadow_evidence_status"
    assert "reviewed_at_utc_missing_or_invalid" in payload["rows"][0]["blockers"]


def test_private_or_redistributable_raw_data_declarations_block(tmp_path: Path) -> None:
    row = _valid_row("case_1")
    row["redistribution_allowed"] = "true"
    row["raw_data_stored_in_repo"] = "true"
    row["customer_email"] = "private@example.test"
    intake = tmp_path / "intake.csv"
    _write_intake(intake, [row], fieldnames=FIELDNAMES + ["customer_email"])

    payload = mod.build_customer_shadow_evidence_status(intake_csv=str(intake))

    summary = payload["summary"]
    blockers = payload["rows"][0]["blockers"]
    assert summary["status"] == "blocked_customer_shadow_evidence_status"
    assert summary["customer_raw_data_stored_in_repo"] is True
    assert "redistribution_allowed_not_false" in blockers
    assert "raw_data_stored_in_repo_not_false" in blockers
    assert "private_column_present:customer_email" in blockers


def test_cli_writes_json_csv_and_markdown(tmp_path: Path) -> None:
    intake = tmp_path / "intake.csv"
    out_json = tmp_path / "status.json"
    out_csv = tmp_path / "status.csv"
    out_md = tmp_path / "status.md"
    _write_intake(intake, [_valid_row("case_1"), _valid_row("case_2"), _valid_row("case_3")])

    mod.main(
        [
            "--intake-csv",
            str(intake),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["status"] == "customer_shadow_evidence_status_ready"
    assert out_csv.read_text(encoding="utf-8").startswith("case_id,row_kind,status,")
    md = out_md.read_text(encoding="utf-8")
    assert "Customer Shadow Evidence Status" in md
    assert "Customer Shadow Work Order" in md
    assert "Paid Pilot Requirement Checklist" in md
