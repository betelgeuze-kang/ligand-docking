from __future__ import annotations

from tools import build_wetlab_broad_screen_antitarget_throughput_bridge as mod


def test_build_antitarget_throughput_bridge_uses_antitarget_and_primary_shard_slice() -> None:
    payload = mod.build_payload(
        antitarget_execution_queue={
            "summary": {
                "first_actionable_primary_target_id": "CA IX",
                "first_actionable_anti_target_id": "CA II",
                "first_actionable_shard_id": "01_of_20",
            },
            "rows": [
                {
                    "primary_target_id": "CA IX",
                    "anti_target_id": "CA II",
                    "primary_shard_id": "01_of_20",
                    "queue_status": "ready_first_counterscreen",
                }
            ],
        },
        primary_queue={
            "rows": [
                {
                    "target_id": "CA IX",
                    "shard_id": "01_of_20",
                    "compound_index_start": 1,
                    "compound_index_end": 2,
                }
            ]
        },
        compound_universe={
            "rows": [
                {"compound_index": 1, "canonical_smiles": "CCO", "compound_name": "Acetazolamide"},
                {"compound_index": 2, "canonical_smiles": "CCN", "compound_name": "Methazolamide"},
            ]
        },
        portfolio={
            "rows": [
                {"target_id": "CA IX", "domain_family": "condition_aware_enzyme"},
            ]
        },
    )

    summary = payload["summary"]
    assert summary["status"] == "wetlab_broad_screen_antitarget_throughput_bridge_ready"
    assert summary["primary_target_id"] == "CA IX"
    assert summary["anti_target_id"] == "CA II"
    assert summary["shard_id"] == "01_of_20"
    assert summary["manifest_row_count"] == 2
    assert summary["preferred_command_kind"] == "throughput_preflight_tuned_gate55"
    assert "CA II" in payload["rows"][0]["command"]
