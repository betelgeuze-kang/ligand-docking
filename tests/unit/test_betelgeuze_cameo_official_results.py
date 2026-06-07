from __future__ import annotations

from betelgeuze_cameo.official_results import build_cameo_official_results_intake_gate


def test_cameo_official_results_intake_blocks_missing_rows() -> None:
    payload = build_cameo_official_results_intake_gate(result_rows=[])

    assert payload["summary"]["status"] == "blocked_cameo_official_results_intake"
    assert payload["summary"]["blocker_count"] >= 1
    assert "target_id" in payload["summary"]["required_columns"]
    assert "lddt" in payload["summary"]["official_metric_columns"]
    assert "native_accuracy" in payload["summary"]["disallowed_local_accuracy_columns"]
    assert payload["summary"]["external_state_mutated"] is False
    assert any(blocker["code"] == "official_result_rows_missing" for blocker in payload["blockers"])


def test_cameo_official_results_intake_accepts_model1_with_provenance() -> None:
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
            }
        ]
    )

    assert payload["summary"]["status"] == "cameo_official_results_intake_ready"
    assert payload["summary"]["accepted_official_result_count"] == 1
    assert payload["summary"]["model1_official_result_ready"] is True
    assert payload["rows"][0]["official_cameo_result_used"] is True


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
    assert "result_source_not_official_cameo" in row["blockers"]
    assert "local_native_accuracy_column_present" in row["blockers"]
