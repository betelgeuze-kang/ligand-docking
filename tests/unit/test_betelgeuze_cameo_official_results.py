from __future__ import annotations

from betelgeuze_cameo.official_results import build_cameo_official_results_intake_gate


def test_cameo_official_results_intake_blocks_missing_rows() -> None:
    payload = build_cameo_official_results_intake_gate(result_rows=[])

    assert payload["summary"]["status"] == "blocked_cameo_official_results_intake"
    assert payload["summary"]["blocker_count"] >= 1
    assert payload["summary"]["official_result_intake_ready"] is False
    assert "target_id" in payload["summary"]["required_columns"]
    assert "lddt" in payload["summary"]["official_metric_columns"]
    assert "native_accuracy" in payload["summary"]["disallowed_local_accuracy_columns"]
    assert "official_cameo" in payload["summary"]["allowed_result_source_kinds"]
    assert payload["summary"]["operator_action_required_count"] >= 1
    assert payload["summary"]["operator_action_required_row_count"] == 0
    assert payload["summary"]["primary_blocker_code"] == "official_result_rows_missing"
    assert payload["summary"]["primary_required_action"] == (
        "Fill at least one official CAMEO result row in the operator intake CSV."
    )
    assert payload["summary"]["external_state_mutated"] is False
    assert any(blocker["code"] == "official_result_rows_missing" for blocker in payload["blockers"])
    assert payload["blockers"][0]["execution_enabled"] is False


def test_cameo_official_results_intake_accepts_model1_with_provenance() -> None:
    payload = build_cameo_official_results_intake_gate(
        result_rows=[
            {
                "target_id": "CAMEO100",
                "candidate_id": "model1",
                "cameo_model_rank": "1",
                "result_source_kind": "OFFICIAL_CAMEO",
                "result_source_url": "https://cameo3d.org/modeling/CAMEO100",
                "result_record_id": "CAMEO100:model1",
                "retrieved_at_utc": "2026-06-03T00:00:00Z",
                "assessment_date": "2026-06-03",
                "lddt": "0.72",
            }
        ]
    )

    assert payload["summary"]["status"] == "cameo_official_results_intake_ready"
    assert payload["summary"]["official_result_intake_ready"] is True
    assert payload["summary"]["accepted_official_result_count"] == 1
    assert payload["summary"]["operator_action_required_count"] == 0
    assert payload["summary"]["operator_action_required_row_count"] == 0
    assert payload["summary"]["source_provenance_ready_row_count"] == 1
    assert payload["summary"]["official_metric_ready_row_count"] == 1
    assert payload["summary"]["local_native_accuracy_blocker_count"] == 0
    assert payload["summary"]["model1_official_result_ready"] is True
    assert payload["rows"][0]["official_cameo_result_used"] is True
    assert payload["rows"][0]["result_source_kind"] == "official_cameo"
    assert payload["rows"][0]["source_provenance_ready"] is True
    assert payload["rows"][0]["official_metric_ready"] is True
    assert payload["rows"][0]["local_native_accuracy_absent"] is True
    assert payload["rows"][0]["operator_action_required"] is False
    assert payload["rows"][0]["claim_promotion_allowed"] is False


def test_cameo_official_results_intake_blocks_local_or_unproven_rows() -> None:
    payload = build_cameo_official_results_intake_gate(
        result_rows=[
            {
                "target_id": "CAMEO100",
                "candidate_id": "model1",
                "cameo_model_rank": "1",
                "result_source_kind": "local_native",
                "result_source_url": "file:///tmp/native.json",
                "result_record_id": "",
                "retrieved_at_utc": "not-a-date",
                "assessment_date": "not-a-date",
                "native_accuracy": "0.99",
            }
        ]
    )

    assert payload["summary"]["status"] == "blocked_cameo_official_results_intake"
    row = payload["rows"][0]
    assert row["ready"] is False
    assert row["operator_action_required"] is True
    assert row["source_provenance_ready"] is False
    assert row["official_metric_ready"] is False
    assert row["local_native_accuracy_absent"] is False
    assert "result_source_not_official_cameo" in row["blockers"]
    assert "local_native_accuracy_column_present" in row["blockers"]
    assert "Use an official CAMEO result source kind only." in row["required_action"]
    assert payload["summary"]["operator_action_required_count"] >= 1
    assert payload["summary"]["operator_action_required_row_count"] == 1
    assert payload["summary"]["local_native_accuracy_blocker_count"] == 1


def test_cameo_official_results_intake_blocks_blank_local_accuracy_column() -> None:
    payload = build_cameo_official_results_intake_gate(
        result_rows=[
            {
                "target_id": "CAMEO100",
                "candidate_id": "model1",
                "cameo_model_rank": "1",
                "result_source_kind": "official_cameo",
                "result_source_url": "https://cameo3d.org/modeling/CAMEO100",
                "result_record_id": "CAMEO100:model1",
                "retrieved_at_utc": "2026-06-03T00:00:00Z",
                "assessment_date": "2026-06-03",
                "lddt": "0.72",
                "Native_Accuracy": "",
            }
        ]
    )

    assert payload["summary"]["status"] == "blocked_cameo_official_results_intake"
    row = payload["rows"][0]
    assert row["ready"] is False
    assert row["source_provenance_ready"] is True
    assert row["official_metric_ready"] is True
    assert row["local_native_accuracy_absent"] is False
    assert row["disallowed_local_accuracy_columns_present"] == "native_accuracy"
    assert "local_native_accuracy_column_present" in row["blockers"]
    assert row["required_action"] == (
        "Remove local/native accuracy columns; use official CAMEO metrics only."
    )
