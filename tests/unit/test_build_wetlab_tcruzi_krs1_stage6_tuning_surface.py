from __future__ import annotations

from tools import build_wetlab_tcruzi_krs1_stage6_tuning_surface as mod


def test_build_wetlab_tcruzi_krs1_stage6_tuning_surface_reads_t_cruzi_slug(monkeypatch) -> None:
    summaries = {
        "runs/wetlab_broad_screen_throughput/t_cruzi_krs1/01_of_20/throughput_run_gate51_summary.json": {
            "service_result": {
                "status": "error",
                "error_code": "HTVS_GATE_FAILED",
                "failed_stage": "stage6_operational_gate",
            },
            "stages": {
                "stage6_operational_gate": {
                    "mean_min_distance_A": 5.02,
                    "mean_min_distance_A_source": "stage6_operational_gate",
                    "min_frames_observed": 138,
                }
            },
        },
        "runs/wetlab_broad_screen_throughput/t_cruzi_krs1/02_of_20/throughput_run_gate51_summary.json": {
            "service_result": {
                "status": "error",
                "error_code": "HTVS_GATE_FAILED",
                "failed_stage": "stage6_operational_gate",
            },
            "stages": {
                "stage6_operational_gate": {
                    "mean_min_distance_A": 5.04,
                    "mean_min_distance_A_source": "stage6_operational_gate",
                    "min_frames_observed": 138,
                }
            },
        },
    }
    requested_paths: list[str] = []

    def _fake_load(path: str) -> dict:
        requested_paths.append(path)
        for suffix, payload in summaries.items():
            if path.endswith(suffix):
                return payload
        return {}

    monkeypatch.setattr(mod, "maybe_load_json", _fake_load)

    payload = mod.build_payload(
        {
            "rows": [
                {"target_id": "T. cruzi KRS1", "shard_id": "01_of_20", "queue_status": "explicit_hold"},
                {"target_id": "T. cruzi KRS1", "shard_id": "02_of_20", "queue_status": "explicit_hold"},
                {"target_id": "T. cruzi KRS1", "shard_id": "03_of_20", "queue_status": "ready_after_previous_shard"},
            ]
        },
        {
            "rows": [
                {"command_kind": "throughput_preflight_tuned_gate51", "command": "python3 tools/run_ligand_htvs_pipeline.py --gate51"},
                {"command_kind": "throughput_preflight_tuned_gate55", "command": "python3 tools/run_ligand_htvs_pipeline.py --gate55"},
            ],
        },
    )

    summary = payload["summary"]
    assert summary["status"] == "wetlab_tcruzi_krs1_stage6_tuning_surface_ready"
    assert summary["target_id"] == "T. cruzi KRS1"
    assert summary["observed_row_count"] == 2
    assert summary["next_retry_shard_id"] == "03_of_20"
    assert summary["recommended_observed_threshold_A"] == 5.05
    assert summary["immediately_runnable_threshold_A"] == 5.1
    assert summary["immediately_runnable_command_kind"] == "throughput_preflight_tuned_gate51"
    assert "gate5.1 retry for 03_of_20" in summary["next_required_step"]

    detail_rows = [row for row in payload["rows"] if row.get("row_kind") == "stage6_retry_observation"]
    assert [row["shard_id"] for row in detail_rows] == ["01_of_20", "02_of_20"]
    assert detail_rows[0]["summary_json"].endswith("t_cruzi_krs1/01_of_20/throughput_run_gate51_summary.json")
    assert detail_rows[1]["summary_json"].endswith("t_cruzi_krs1/02_of_20/throughput_run_gate51_summary.json")
    assert any("/t_cruzi_krs1/" in path for path in requested_paths)

    candidate_rows = [row for row in payload["rows"] if row.get("row_kind") == "threshold_candidate"]
    labels = {row["candidate_label"] for row in candidate_rows}
    assert {"candidate_5.0", "candidate_5.05", "candidate_5.1", "candidate_5.5"}.issubset(labels)


def test_build_wetlab_tcruzi_krs1_stage6_tuning_surface_marks_gate51_validated(monkeypatch) -> None:
    summaries = {
        "runs/wetlab_broad_screen_throughput/t_cruzi_krs1/01_of_20/throughput_run_summary.json": {
            "service_result": {
                "status": "error",
                "error_code": "HTVS_GATE_FAILED",
                "failed_stage": "stage6_operational_gate",
            },
            "stages": {
                "stage6_operational_gate": {
                    "mean_min_distance_A": 5.02,
                    "mean_min_distance_A_source": "stage6_operational_gate",
                    "min_frames_observed": 138,
                }
            },
        },
        "runs/wetlab_broad_screen_throughput/t_cruzi_krs1/02_of_20/throughput_run_gate51_summary.json": {
            "pass": True,
            "service_result": {"status": "ok", "error_code": "HTVS_OK"},
            "stages": {
                "stage6_operational_gate": {
                    "pass": True,
                    "mean_min_distance_A": 5.03,
                    "mean_min_distance_A_source": "stage6_operational_gate",
                    "min_frames_observed": 162,
                }
            },
        },
        "runs/wetlab_broad_screen_throughput/t_cruzi_krs1/03_of_20/throughput_run_gate51_summary.json": {
            "pass": True,
            "service_result": {"status": "ok", "error_code": "HTVS_OK"},
            "stages": {
                "stage6_operational_gate": {
                    "pass": True,
                    "mean_min_distance_A": 5.01,
                    "mean_min_distance_A_source": "stage6_operational_gate",
                    "min_frames_observed": 162,
                }
            },
        },
    }

    def _fake_load(path: str) -> dict:
        for suffix, payload in summaries.items():
            if path.endswith(suffix):
                return payload
        return {}

    monkeypatch.setattr(mod, "maybe_load_json", _fake_load)

    payload = mod.build_payload(
        {
            "rows": [
                {"target_id": "T. cruzi KRS1", "shard_id": "01_of_20", "queue_status": "explicit_hold"},
                {"target_id": "T. cruzi KRS1", "shard_id": "02_of_20", "queue_status": "result_ready"},
                {"target_id": "T. cruzi KRS1", "shard_id": "03_of_20", "queue_status": "result_ready"},
            ]
        },
        {
            "rows": [
                {"command_kind": "throughput_preflight_tuned_gate51", "command": "python3 tools/run_ligand_htvs_pipeline.py --gate51"},
            ],
        },
    )

    summary = payload["summary"]
    assert summary["stage6_tuning_state"] == "guarded_gate51_validated_default_lane_closed"
    assert summary["gate51_validation_row_count"] == 2
    assert summary["gate51_validation_success_count"] == 2
    assert summary["gate51_validation_all_post_hold_success"] is True
    assert summary["gate51_validation_start_shard_id"] == "02_of_20"
    assert summary["gate51_validation_end_shard_id"] == "03_of_20"
    assert summary["next_retry_shard_id"] == ""
    assert "Promote T. cruzi KRS1 guarded gate5.1" in summary["next_required_step"]

    validation_rows = [row for row in payload["rows"] if row.get("row_kind") == "gate51_validation_observation"]
    assert [row["shard_id"] for row in validation_rows] == ["02_of_20", "03_of_20"]
    assert all(row["pass"] is True for row in validation_rows)
