from __future__ import annotations

from tools import build_wetlab_broad_screen_stability_score as mod


def test_build_wetlab_broad_screen_stability_score_marks_stable_provisional_target() -> None:
    payload = mod.build_payload(
        queue_payload={"rows": [{"target_id": "CA IX", "shard_id": f"{idx:02d}_of_20"} for idx in range(1, 21)]},
        source_payload={
            "rows": [
                {"target_id": "CA IX", "compound_name": "Acetazolamide", "bulk_rank": 1, "bulk_score": 93.2, "seed_status": "broad_screen_runtime_validation_result", "shard_id": "06_of_20"},
                {"target_id": "CA IX", "compound_name": "Methazolamide", "bulk_rank": 2, "bulk_score": 89.1, "seed_status": "broad_screen_actual_result_example", "shard_id": "03_of_20"},
                {"target_id": "CA IX", "compound_name": "Dichlorphenamide", "bulk_rank": 3, "bulk_score": 97.0, "seed_status": "broad_screen_runtime_validation_result", "shard_id": "04_of_20"},
            ]
        },
        progress_payload={"rows": [{"target_id": "CA IX", "queue_status": "result_ready"} for _ in range(6)]},
        rerank_payload={"rows": [{"target_id": "CA IX", "rerank_status": "full_bulk_top3_ready"}]},
    )
    summary = payload["summary"]
    row = payload["rows"][0]
    assert summary["status"] == "wetlab_broad_screen_stability_score_ready"
    assert row["target_id"] == "CA IX"
    assert row["stability_band"] == "stable_provisional"
    assert row["stability_score"] >= 70.0
