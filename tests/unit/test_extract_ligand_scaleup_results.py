from pathlib import Path
import json

from tools.product import extract_ligand_scaleup_results as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_build_payload_uses_run_summary_then_pipeline_summary_then_sla_summary_contract(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    baseline_root = tmp_path / "runs/baseline_run"
    candidate_root = tmp_path / "runs/candidate_run"

    baseline_pipeline = tmp_path / "runs/baseline_task_summary.json"
    candidate_pipeline = tmp_path / "runs/candidate_task_summary.json"
    baseline_sla = tmp_path / "runs/baseline_task_sla.json"
    candidate_sla = tmp_path / "runs/candidate_task_sla.json"

    _write_json(
        baseline_pipeline,
        {"artifacts": {"sla_summary_json": str(baseline_sla)}},
    )
    _write_json(
        candidate_pipeline,
        {
            "artifacts": {"sla_summary_json": str(candidate_sla)},
            "stages": {"stage2_trajectory_generation": {"duration_sec": 90.0}},
        },
    )
    _write_json(
        baseline_sla,
        {
            "queue_rows": 10000,
            "total_latency_sec": 200.0,
            "queue_rate_stage2_rows_per_sec": 50.0,
            "queue_rate_stage3_rows_per_sec": 200.0,
            "durations_sec": {"stage2_trajectory_sec": 150.0},
        },
    )
    _write_json(
        candidate_sla,
        {
            "queue_rows": 10000,
            "total_latency_sec": 160.0,
            "queue_rate_stage2_rows_per_sec": 70.0,
            "queue_rate_stage3_rows_per_sec": 220.0,
            "durations_sec": {"stage2_trajectory_sec": 0.0},
        },
    )
    _write_json(
        baseline_root / "summary.json",
        {
            "sets": [
                {
                    "set_id": "set1",
                    "tasks": [
                        {
                            "task_id": "trpv1_full",
                            "kind": "ligand_stress",
                            "domain": "ion_channel",
                            "pass": True,
                            "pipeline_summary_json": str(baseline_pipeline),
                        }
                    ],
                }
            ]
        },
    )
    _write_json(
        candidate_root / "summary.json",
        {
            "sets": [
                {
                    "set_id": "set1",
                    "tasks": [
                        {
                            "task_id": "trpv1_full",
                            "kind": "ligand_stress",
                            "domain": "ion_channel",
                            "pass": True,
                            "pipeline_summary_json": str(candidate_pipeline),
                        }
                    ],
                }
            ]
        },
    )

    payload = mod.build_payload(
        baseline_run_root="runs/baseline_run",
        candidate_run_root="runs/candidate_run",
        comparison_json="",
    )

    assert payload["task_count"] == 1
    assert payload["measured_stage2_speedup_count"] == 1
    assert payload["measured_total_speedup_count"] == 1
    row = payload["rows"][0]
    assert row["baseline_stage2_runtime_sec"] == 150.0
    assert row["candidate_stage2_runtime_sec"] == 90.0
    assert row["baseline_total_runtime_sec"] == 200.0
    assert row["candidate_total_runtime_sec"] == 160.0
    assert row["baseline_queue_rows"] == 10000.0
    assert row["measured_stage2_speedup"] == 150.0 / 90.0
    assert row["measured_total_speedup"] == 200.0 / 160.0
    assert row["baseline_stage2_share_pct"] == 75.0
    assert row["candidate_stage2_share_pct"] == 56.25


def test_build_payload_can_merge_comparison_only_when_runtime_artifacts_are_missing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    _write_json(
        tmp_path / "runs/comparison.json",
        {
            "task_rows": [
                {
                    "set_id": "set2",
                    "task_id": "gpcr_core_full",
                    "kind": "ligand_stress",
                    "domain": "gpcr",
                    "baseline_pass": True,
                    "candidate_pass": True,
                    "delta_pr_auc": -0.01,
                    "delta_top20_hit_rate": -0.05,
                }
            ]
        },
    )

    payload = mod.build_payload(
        baseline_run_root="",
        candidate_run_root="",
        comparison_json="runs/comparison.json",
    )

    assert payload["task_count"] == 1
    assert payload["measured_stage2_speedup_count"] == 0
    row = payload["rows"][0]
    assert row["set_id"] == "set2"
    assert row["task_id"] == "gpcr_core_full"
    assert row["delta_pr_auc"] == -0.01
    assert row["delta_top20_hit_rate"] == -0.05
    assert row["measured_stage2_speedup"] is None
    assert row["baseline_stage2_runtime_sec"] is None


def test_build_payload_falls_back_to_copied_pipeline_stage8_sla(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    baseline_root = tmp_path / "runs/baseline_run"
    candidate_root = tmp_path / "runs/candidate_run"
    copied_pipeline = baseline_root / "set1/files/ion_channel/baseline_pipeline_summary.json"
    candidate_pipeline = tmp_path / "runs/candidate_pipeline_summary.json"
    candidate_sla = tmp_path / "runs/candidate_sla.json"

    _write_json(
        copied_pipeline,
        {
            "stages": {
                "stage8_sla": {
                    "queue_rows": 10000,
                    "total_latency_sec": 200.0,
                    "queue_rate_stage2_rows_per_sec": 50.0,
                    "durations_sec": {"stage2_trajectory_sec": 150.0},
                }
            }
        },
    )
    _write_json(candidate_pipeline, {"artifacts": {"sla_summary_json": str(candidate_sla)}})
    _write_json(
        candidate_sla,
        {
            "queue_rows": 10000,
            "total_latency_sec": 160.0,
            "queue_rate_stage2_rows_per_sec": 70.0,
            "durations_sec": {"stage2_trajectory_sec": 75.0},
        },
    )
    _write_json(
        baseline_root / "summary.json",
        {
            "sets": [
                {
                    "set_id": "set1",
                    "tasks": [
                        {
                            "task_id": "trpv1_full",
                            "kind": "ligand_stress",
                            "domain": "ion_channel",
                            "pass": True,
                            "pipeline_summary_json": str(tmp_path / "runs/missing_pipeline_summary.json"),
                            "copied_files": [
                                {
                                    "src": str(tmp_path / "runs/missing_pipeline_summary.json"),
                                    "dst": str(copied_pipeline),
                                }
                            ],
                        }
                    ],
                }
            ]
        },
    )
    _write_json(
        candidate_root / "summary.json",
        {
            "sets": [
                {
                    "set_id": "set1",
                    "tasks": [
                        {
                            "task_id": "trpv1_full",
                            "kind": "ligand_stress",
                            "domain": "ion_channel",
                            "pass": True,
                            "pipeline_summary_json": str(candidate_pipeline),
                        }
                    ],
                }
            ]
        },
    )

    payload = mod.build_payload(
        baseline_run_root="runs/baseline_run",
        candidate_run_root="runs/candidate_run",
        comparison_json="",
    )

    assert payload["measured_stage2_speedup_count"] == 1
    row = payload["rows"][0]
    assert row["baseline_pipeline_summary_json"] == str(copied_pipeline)
    assert row["baseline_stage2_runtime_sec"] == 150.0
    assert row["candidate_stage2_runtime_sec"] == 75.0
    assert row["measured_stage2_speedup"] == 2.0


def test_build_payload_recovers_stage2_duration_from_task_log_after_stage3_only_resume(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    baseline_root = tmp_path / "runs/baseline_run"
    candidate_root = tmp_path / "runs/candidate_run"
    baseline_pipeline = tmp_path / "runs/baseline_pipeline.json"
    candidate_pipeline = tmp_path / "runs/candidate_pipeline.json"
    baseline_sla = tmp_path / "runs/baseline_sla.json"
    candidate_sla = tmp_path / "runs/candidate_sla.json"
    candidate_log = tmp_path / "runs/candidate.log"
    candidate_log.parent.mkdir(parents=True, exist_ok=True)
    candidate_log.write_text(
        '"stage2_trajectory_generation": {\n  "ok": true,\n  "duration_sec": 80.0\n}\n',
        encoding="utf-8",
    )
    _write_json(baseline_pipeline, {"artifacts": {"sla_summary_json": str(baseline_sla)}})
    _write_json(candidate_pipeline, {"artifacts": {"sla_summary_json": str(candidate_sla)}, "stages": {"stage2_trajectory_generation": {"skipped": True}}})
    _write_json(baseline_sla, {"total_latency_sec": 200.0, "durations_sec": {"stage2_trajectory_sec": 160.0}})
    _write_json(candidate_sla, {"total_latency_sec": 20.0, "durations_sec": {"stage2_trajectory_sec": 0.0}})
    _write_json(
        baseline_root / "summary.json",
        {"sets": [{"set_id": "set1", "tasks": [{"task_id": "trpv1_full", "kind": "ligand_stress", "domain": "ion_channel", "pass": True, "pipeline_summary_json": str(baseline_pipeline)}]}]},
    )
    _write_json(
        candidate_root / "summary.json",
        {"sets": [{"set_id": "set1", "tasks": [{"task_id": "trpv1_full", "kind": "ligand_stress", "domain": "ion_channel", "pass": True, "pipeline_summary_json": str(candidate_pipeline), "run_log": str(candidate_log)}]}]},
    )

    payload = mod.build_payload(
        baseline_run_root="runs/baseline_run",
        candidate_run_root="runs/candidate_run",
        comparison_json="",
    )

    row = payload["rows"][0]
    assert row["candidate_stage2_runtime_sec"] == 80.0
    assert row["measured_stage2_speedup"] == 2.0
