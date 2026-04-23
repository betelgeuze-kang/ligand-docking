from __future__ import annotations

import json
from pathlib import Path

from tools import build_wetlab_lbdhodh_gate51_validation_review_surface as mod


def test_build_wetlab_lbdhodh_gate51_validation_review_surface_promotes_validated_branch(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    runs = tmp_path / "runs" / "wetlab_broad_screen_throughput" / "leishmania_braziliensis_dhodh"
    for shard_id, mean_min_distance in [
        ("09_of_20", 4.996),
        ("10_of_20", 5.004),
        ("11_of_20", 5.010),
        ("12_of_20", 5.015),
        ("13_of_20", 5.018),
        ("14_of_20", 5.021),
        ("15_of_20", 5.024),
        ("16_of_20", 5.027),
        ("17_of_20", 5.031),
        ("18_of_20", 5.037),
        ("19_of_20", 5.043),
        ("20_of_20", 5.049),
    ]:
        shard_dir = runs / shard_id
        shard_dir.mkdir(parents=True, exist_ok=True)
        (shard_dir / "throughput_run_gate51_summary.json").write_text(
            json.dumps(
                {
                    "service_result": {"status": "ok", "error_code": "HTVS_OK", "failed_stage": None},
                    "stages": {
                        "stage6_operational_gate": {
                            "pass": True,
                            "mean_min_distance_A": mean_min_distance,
                            "gate_threshold_A": 5.1,
                            "mean_min_distance_A_source": "test",
                            "min_frames_observed": 138,
                        }
                    },
                }
            ),
            encoding="utf-8",
        )

    queue_payload = {
        "rows": [
            *[
                {
                    "target_id": mod.TARGET_ID,
                    "shard_id": f"{i:02d}_of_20",
                    "queue_status": "explicit_hold",
                    "execution_state": "explicit_hold",
                    "notes": "auto_hold",
                }
                for i in range(1, 9)
            ],
            *[
                {
                    "target_id": mod.TARGET_ID,
                    "shard_id": f"{i:02d}_of_20",
                    "queue_status": "result_ready",
                    "execution_state": "result_ready",
                    "notes": "auto_complete",
                }
                for i in range(9, 21)
            ],
        ]
    }
    tuning_payload = {"summary": {"recommended_observed_threshold_A": 5.1, "next_retry_shard_id": "20_of_20"}}
    retry_payload = {"summary": {"campaign_start_shard_id": "01_of_20"}}

    payload = mod.build_payload(queue_payload, tuning_payload, retry_payload)
    summary = payload["summary"]

    assert summary["status"] == "wetlab_lbdhodh_gate51_validation_review_surface_ready"
    assert summary["validated"] is True
    assert summary["gate51_validated"] is True
    assert summary["decision"] == "promote_gate51_validated_keep_default_closed"
    assert summary["default_lane_reopen_allowed"] is False
    assert summary["branch_to_gate51_only"] is True
    assert summary["default_lane_hold_count"] == 8
    assert summary["gate51_validation_row_count"] == 12
    assert summary["gate51_validation_success_count"] == 12
    assert summary["gate51_validation_success_pct"] == 100.0
    assert summary["validated_command_kind"] == "throughput_preflight_tuned_gate51"
    assert summary["validated_threshold_A"] == 5.1
    assert summary["gate51_validation_start_shard_id"] == "09_of_20"
    assert summary["gate51_validation_end_shard_id"] == "20_of_20"
    assert summary["next_required_step"] == "Promote DHODH gate5.1 as validated, keep the default lane closed, and reserve any future DHODH reopen for an explicit new review."
