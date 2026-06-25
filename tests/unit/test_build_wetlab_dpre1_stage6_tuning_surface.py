from __future__ import annotations

from tools import build_wetlab_dpre1_stage6_tuning_surface as mod


def test_build_wetlab_dpre1_stage6_tuning_surface_summarizes_gate51_band(monkeypatch) -> None:
    observed_by_shard = {
        "01_of_20": 5.0,
        "02_of_20": 5.02,
        "03_of_20": 5.05,
    }

    def fake_maybe_load_json(path_like: str) -> dict[str, object]:
        for shard_id, observed in observed_by_shard.items():
            if shard_id in path_like:
                return {
                    "service_result": {
                        "status": "error",
                        "failed_stage": "stage6_operational_gate",
                    },
                    "stages": {
                        "stage6_operational_gate": {
                            "gate_threshold_A": 2.5,
                            "mean_min_distance_A": observed,
                            "mean_min_distance_A_source": "unit_fixture",
                            "min_frames_observed": 12,
                        }
                    },
                }
        return {}

    monkeypatch.setattr(mod, "maybe_load_json", fake_maybe_load_json)

    payload = mod.build_payload(
        {
            "rows": [
                {"target_id": "DprE1", "shard_id": "01_of_20", "queue_status": "explicit_hold"},
                {"target_id": "DprE1", "shard_id": "02_of_20", "queue_status": "explicit_hold"},
                {"target_id": "DprE1", "shard_id": "03_of_20", "queue_status": "explicit_hold"},
                {"target_id": "DprE1", "shard_id": "04_of_20", "queue_status": "ready_after_previous_shard"},
            ]
        },
        {
            "structured": {"preferred_summary_json": "runs/wetlab_broad_screen_throughput/dpre1/04_of_20/throughput_run_gate51_summary.json"},
            "rows": [
                {"command_kind": "throughput_preflight_tuned_gate51", "command": "python3 tools/run_ligand_htvs_pipeline.py --gate51"},
                {"command_kind": "throughput_preflight_tuned_gate55", "command": "python3 tools/run_ligand_htvs_pipeline.py --gate55"},
            ],
        },
    )

    summary = payload["summary"]
    assert summary["status"] == "wetlab_dpre1_stage6_tuning_surface_ready"
    assert summary["target_id"] == "DprE1"
    assert summary["next_retry_shard_id"] == "04_of_20"
    assert summary["recommended_observed_threshold_A"] == 5.05
    assert summary["immediately_runnable_threshold_A"] == 5.1
    assert summary["immediately_runnable_command_kind"] == "throughput_preflight_tuned_gate51"

    candidate_rows = [row for row in payload["rows"] if row.get("row_kind") == "threshold_candidate"]
    labels = {row["candidate_label"] for row in candidate_rows}
    assert {"candidate_5.0", "candidate_5.05", "candidate_5.1", "candidate_5.5"}.issubset(labels)
