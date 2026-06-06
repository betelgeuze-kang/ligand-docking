from __future__ import annotations

from pathlib import Path

from tools.wetlab import build_wetlab_data_quality_assessment as mod


def test_build_wetlab_data_quality_assessment_separates_operational_and_measurement_quality(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runs = Path("runs")
    runs.mkdir()
    for name in [
        "wetlab_priority3_runtime_event_log.jsonl",
        "wetlab_next3_runtime_event_log.jsonl",
        "wetlab_final2_runtime_event_log.jsonl",
        "wetlab_wave2_runtime_event_log.jsonl",
    ]:
        (runs / name).write_text('{"note":"workflow_validation_only_no_wetlab_claim"}\n', encoding="utf-8")

    master_queue = {"summary": {"queue_target_count": 13, "resolved_target_count": 13}}
    master_terminal_review = {"summary": {"campaign_terminal_state": "complete"}}
    export_bundle = {"summary": {"track_count": 5, "ready_to_send_count": 5}}
    blueprint = {"summary": {"wave1_target_count": 8}}

    payload = mod.build_payload(
        master_queue,
        master_terminal_review,
        export_bundle,
        blueprint,
        [
            "runs/wetlab_priority3_runtime_event_log.jsonl",
            "runs/wetlab_next3_runtime_event_log.jsonl",
            "runs/wetlab_final2_runtime_event_log.jsonl",
            "runs/wetlab_wave2_runtime_event_log.jsonl",
        ],
    )

    summary = payload["summary"]
    assert summary["status"] == "wetlab_data_quality_assessment_ready"
    assert summary["overall_operational_band"] == "high"
    assert summary["partner_outreach_readiness"] == "ready"
    assert summary["therapeutic_claim_readiness"] == "not_ready"
