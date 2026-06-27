from __future__ import annotations

from tools import build_wetlab_dengue_ns2b_ns3_stage6_tuning_surface as mod


def test_build_wetlab_dengue_ns2b_ns3_stage6_tuning_surface_summarizes_gate45_band(monkeypatch) -> None:
    observed_by_shard = {
        "01_of_20": 4.4,
        "02_of_20": 4.45,
        "03_of_20": 4.5,
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
                {"target_id": "Dengue NS2B-NS3 protease", "shard_id": "01_of_20", "queue_status": "explicit_hold"},
                {"target_id": "Dengue NS2B-NS3 protease", "shard_id": "02_of_20", "queue_status": "explicit_hold"},
                {"target_id": "Dengue NS2B-NS3 protease", "shard_id": "03_of_20", "queue_status": "explicit_hold"},
                {"target_id": "Dengue NS2B-NS3 protease", "shard_id": "05_of_20", "queue_status": "ready_after_previous_shard"},
            ]
        },
        {
            "structured": {"preferred_summary_json": "runs/wetlab_broad_screen_throughput/dengue_ns2b_ns3_protease/05_of_20/throughput_run_gate45_summary.json"},
            "rows": [
                {"command_kind": "throughput_preflight_tuned_gate45", "command": "python3 tools/run_ligand_htvs_pipeline.py --gate45"},
                {"command_kind": "throughput_preflight_tuned_gate55", "command": "python3 tools/run_ligand_htvs_pipeline.py --gate55"},
            ],
        },
    )

    summary = payload["summary"]
    assert summary["status"] == "wetlab_dengue_ns2b_ns3_protease_stage6_tuning_surface_ready"
    assert summary["target_id"] == "Dengue NS2B-NS3 protease"
    assert summary["next_retry_shard_id"] == "05_of_20"
    assert summary["recommended_observed_threshold_A"] == 4.5
    assert summary["immediately_runnable_threshold_A"] == 4.5
    assert summary["immediately_runnable_command_kind"] == "throughput_preflight_tuned_gate45"

    candidate_rows = [row for row in payload["rows"] if row.get("row_kind") == "threshold_candidate"]
    labels = {row["candidate_label"] for row in candidate_rows}
    assert {"candidate_4.4", "candidate_4.45", "candidate_4.5", "candidate_5.1", "candidate_5.5"}.issubset(labels)


def test_build_wetlab_dengue_ns2b_ns3_stage6_tuning_surface_ignores_mismatched_bridge_fallback() -> None:
    payload = mod.build_payload(
        {
            "rows": [
                {"target_id": "Dengue NS2B-NS3 protease", "shard_id": "01_of_20", "queue_status": "explicit_hold"},
                {"target_id": "Dengue NS2B-NS3 protease", "shard_id": "02_of_20", "queue_status": "explicit_hold"},
            ]
        },
        {
            "summary": {"target_id": "DprE1", "shard_id": "04_of_20"},
            "structured": {"preferred_summary_json": "runs/wetlab_broad_screen_throughput/dpre1/04_of_20/throughput_run_summary.json"},
            "rows": [
                {"command_kind": "throughput_preflight_tuned_gate45", "command": "python3 tools/run_ligand_htvs_pipeline.py --gate45"},
            ],
        },
    )

    summary = payload["summary"]
    assert summary["next_retry_shard_id"] == ""
    assert summary["next_required_step"] == "Keep the Dengue NS2B-NS3 protease default lane closed until a tuned stage6 retry family is selected."
