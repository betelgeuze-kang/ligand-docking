import json
from pathlib import Path

from tools import build_caix_broad_screen_runtime_profile as prof


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def test_build_payload_profiles_caix_07_08():
    progress = {
        "rows": [
            {"target_id": "CA IX", "shard_id": "01_of_20", "started_at": "2026-03-29T22:45:00", "completed_at": "2026-03-29T23:10:00", "queue_status": "result_ready"},
            {"target_id": "CA IX", "shard_id": "02_of_20", "started_at": "2026-03-29T23:11:00", "completed_at": "2026-03-29T23:32:00", "queue_status": "result_ready"},
            {"target_id": "CA IX", "shard_id": "03_of_20", "started_at": "2026-03-29T23:33:00", "completed_at": "2026-03-29T23:58:00", "queue_status": "result_ready"},
            {"target_id": "CA IX", "shard_id": "04_of_20", "started_at": "2026-03-29T23:59:00", "completed_at": "2026-03-30T00:18:00", "queue_status": "result_ready"},
            {"target_id": "CA IX", "shard_id": "05_of_20", "started_at": "2026-03-30T00:21:00", "completed_at": "2026-03-30T00:41:00", "queue_status": "result_ready"},
            {"target_id": "CA IX", "shard_id": "06_of_20", "started_at": "2026-03-30T00:45:00", "completed_at": "2026-03-30T01:02:00", "queue_status": "result_ready"},
            {"target_id": "CA IX", "shard_id": "07_of_20", "started_at": "2026-03-30T01:04:00", "completed_at": "2026-03-30T02:15:00", "queue_status": "result_ready", "notes": "broad_screen_bootstrap_execution_only_no_wetlab_claim"},
            {"target_id": "CA IX", "shard_id": "08_of_20", "started_at": "2026-03-30T21:33:00", "completed_at": "2026-03-30T23:12:05", "queue_status": "result_ready", "notes": "speedpack_preflight_gate_failed_mean_min_distance_runtime_validation_only"},
        ]
    }
    events = [
        {"target_id": "CA IX", "shard_id": "07_of_20", "event": "start"},
        {"target_id": "CA IX", "shard_id": "07_of_20", "event": "complete"},
        {"target_id": "CA IX", "shard_id": "08_of_20", "event": "start"},
        {"target_id": "CA IX", "shard_id": "08_of_20", "event": "reset"},
        {"target_id": "CA IX", "shard_id": "08_of_20", "event": "start"},
        {"target_id": "CA IX", "shard_id": "08_of_20", "event": "heartbeat"},
        {"target_id": "CA IX", "shard_id": "08_of_20", "event": "complete"},
    ]
    throughput_08 = {
        "failed_stage": "stage6_operational_gate",
        "stages": {"stage6_operational_gate": {"pass": False, "mean_min_distance_A": 5.02, "gate_threshold_A": 2.5}},
    }
    result_07 = {"summary": {"row_count": 1}}
    result_08 = {"summary": {"row_count": 3}}

    payload = prof.build_payload(progress, events, {}, throughput_08, result_07, result_08)

    assert payload["summary"]["overall_median_completed_shard_minutes"] == 23.0
    rows = {row["shard_id"]: row for row in payload["rows"]}
    assert rows["07_of_20"]["suspected_cause"] == "bootstrap_only_uninstrumented_long_shard"
    assert rows["08_of_20"]["suspected_cause"] == "speedpack_preflight_stage6_gate_failure"
    assert rows["08_of_20"]["mean_min_distance_A"] == 5.02
