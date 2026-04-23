from pathlib import Path
import json

from tools import build_ligand_scaleup_benchmark_summary as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _contains_tokens(text: str, *tokens: str) -> None:
    lowered = text.lower()
    for token in tokens:
        assert token.lower() in lowered


def _write_pipeline_summary(path: Path, *, total_latency_sec: float, stage2_latency_sec: float, queue_rate_stage2_rows_per_sec: float) -> None:
    _write_json(
        path,
        {
            "stages": {
                "stage8_sla": {
                    "total_latency_sec": total_latency_sec,
                    "queue_rate_stage2_rows_per_sec": queue_rate_stage2_rows_per_sec,
                    "durations_sec": {
                        "stage2_trajectory_sec": stage2_latency_sec,
                    },
                }
            }
        },
    )


def _write_run_summary_with_tasks(path: Path, task_rows: list[dict], *, set_pass: bool = True) -> None:
    _write_json(
        path,
        {
            "sets": [
                {
                    "set_id": "set1_core_blind",
                    "pass": set_pass,
                    "tasks": task_rows,
                }
            ]
        },
    )


def test_build_payload_prelaunch_pending_guardrails(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    _write_json(
        tmp_path / "runs/ligand_scaleup_100k_pilot_current.json",
        {
            "comparison_kind": "size_shift_operational_regression",
            "scope_summary": {
                "full_task_count_100k": 6,
                "smoke_task_count_unchanged": 3,
                "domains_touched": ["gpcr", "ion_channel", "kinase"],
            },
            "guardrail_rows": [
                {"guardrail_id": "no_pass_to_fail", "metric": "set_pass_transition", "threshold": "0 pass->fail transitions", "scope": "regression slice"},
                {"guardrail_id": "pr_auc_drop_max_0p02", "metric": "ranking_pr_auc_delta", "threshold": ">= -0.02 absolute", "scope": "regression slice"},
                {"guardrail_id": "top20_hit_drop_max_1", "metric": "top20_hit_count_delta", "threshold": ">= -1 hit", "scope": "regression slice"},
                {"guardrail_id": "slowest_domain_speedup_min_1p8x", "metric": "measured_end_to_end_speedup", "threshold": ">= 1.8x on slowest domain", "scope": "throughput benchmark"},
            ],
            "preflight_notes": ["pilot scaffold note"],
        },
    )
    _write_json(
        tmp_path / "runs/ligand_scaleup_kpi_current.json",
        {
            "summary": {
                "slowest_task_at_1m": {
                    "task_id": "ion_trpv1_chembl50_full",
                    "domain": "ion_channel",
                    "projected_1m_wall_hr": 16.2,
                    "stage2_share_pct": 89.9,
                }
            }
        },
    )
    _write_json(
        tmp_path / "runs/external_validation_blind_runs/external_validation_blind_runs_2026-03-22_biorxiv_v7r1/summary.json",
        {"sets": [{"set_id": "set1", "pass": True}, {"set_id": "set2", "pass": True}]},
    )

    payload = mod.build_payload(
        pilot_json="runs/ligand_scaleup_100k_pilot_current.json",
        kpi_json="runs/ligand_scaleup_kpi_current.json",
        comparison_json="runs/missing_comparison.json",
        baseline_summary_json="runs/external_validation_blind_runs/external_validation_blind_runs_2026-03-22_biorxiv_v7r1/summary.json",
        candidate_summary_json="runs/missing_candidate_summary.json",
    )

    assert payload["benchmark_stage"] == "prelaunch_scaffold"
    assert payload["comparison_artifact_ready"] is False
    assert payload["claim_safe"] is None
    assert payload["guardrail_pending_count"] >= 4
    _contains_tokens(payload["recommended_next_action"], "baseline", "candidate", "artifacts")
    speed_row = next(row for row in payload["guardrail_rows"] if row["guardrail_id"] == "slowest_domain_speedup_min_1p8x")
    assert speed_row["observed_value"] == "pending"


def test_build_payload_with_comparison_evaluates_guardrails(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    _write_json(
        tmp_path / "runs/ligand_scaleup_100k_pilot_current.json",
        {
            "comparison_kind": "size_shift_operational_regression",
            "scope_summary": {"full_task_count_100k": 6, "smoke_task_count_unchanged": 3, "domains_touched": ["gpcr"]},
            "guardrail_rows": [
                {"guardrail_id": "no_pass_to_fail", "metric": "set_pass_transition", "threshold": "0 pass->fail transitions", "scope": "regression slice"},
                {"guardrail_id": "pr_auc_drop_max_0p02", "metric": "ranking_pr_auc_delta", "threshold": ">= -0.02 absolute", "scope": "regression slice"},
                {"guardrail_id": "top20_hit_drop_max_1", "metric": "top20_hit_count_delta", "threshold": ">= -1 hit", "scope": "regression slice"},
            ],
        },
    )
    _write_json(
        tmp_path / "runs/ligand_scaleup_kpi_current.json",
        {"summary": {"slowest_task_at_1m": {"task_id": "gpcr_core_full", "domain": "gpcr", "projected_1m_wall_hr": 4.0, "stage2_share_pct": 80.0}}},
    )
    _write_json(
        tmp_path / "runs/comparison.json",
        {
            "tasks_with_pr_improvement": 0,
            "tasks_with_pr_regression": 2,
            "profile_changed_task_count": 6,
            "task_rows": [
                {
                    "task_id": "gpcr_core_full",
                    "kind": "ligand_stress",
                    "baseline_pass": True,
                    "candidate_pass": True,
                    "delta_pr_auc": -0.01,
                    "delta_top20_hit_rate": 0.0,
                },
                {
                    "task_id": "ion_trpv1_chembl20_full",
                    "kind": "ligand_stress",
                    "baseline_pass": True,
                    "candidate_pass": True,
                    "delta_pr_auc": -0.015,
                    "delta_top20_hit_rate": -0.05,
                },
            ],
        },
    )
    _write_json(
        tmp_path / "runs/baseline_summary.json",
        {"sets": [{"set_id": "set1", "pass": True}, {"set_id": "set2", "pass": True}, {"set_id": "set3", "pass": True}]},
    )
    _write_json(
        tmp_path / "runs/candidate_summary.json",
        {"sets": [{"set_id": "set1", "pass": True}, {"set_id": "set2", "pass": True}, {"set_id": "set3", "pass": True}]},
    )

    payload = mod.build_payload(
        pilot_json="runs/ligand_scaleup_100k_pilot_current.json",
        kpi_json="runs/ligand_scaleup_kpi_current.json",
        comparison_json="runs/comparison.json",
        baseline_summary_json="runs/baseline_summary.json",
        candidate_summary_json="runs/candidate_summary.json",
    )

    assert payload["benchmark_stage"] == "post_run_comparison"
    assert payload["comparison_artifact_ready"] is True
    assert payload["claim_safe"] is True
    assert payload["comparison_metrics"]["pass_to_fail_count"] == 0
    assert payload["comparison_metrics"]["max_pr_auc_drop"] == -0.015
    pr_row = next(row for row in payload["guardrail_rows"] if row["guardrail_id"] == "pr_auc_drop_max_0p02")
    assert pr_row["pass"] is True
    top20_row = next(row for row in payload["guardrail_rows"] if row["guardrail_id"] == "top20_hit_drop_max_1")
    assert top20_row["pass"] is True
    _contains_tokens(payload["recommended_next_action"], "claim-safe", "throughput", "artifact-size")


def test_build_payload_with_measured_speedup_promotes_post_run_evidence(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    _write_json(
        tmp_path / "runs/ligand_scaleup_100k_pilot_current.json",
        {
            "comparison_kind": "size_shift_operational_regression",
            "scope_summary": {"full_task_count_100k": 6, "smoke_task_count_unchanged": 3, "domains_touched": ["ion_channel"]},
            "guardrail_rows": [
                {"guardrail_id": "no_pass_to_fail", "metric": "set_pass_transition", "threshold": "0 pass->fail transitions", "scope": "regression slice"},
                {"guardrail_id": "pr_auc_drop_max_0p02", "metric": "ranking_pr_auc_delta", "threshold": ">= -0.02 absolute", "scope": "regression slice"},
                {"guardrail_id": "top20_hit_drop_max_1", "metric": "top20_hit_count_delta", "threshold": ">= -1 hit", "scope": "regression slice"},
                {"guardrail_id": "slowest_domain_speedup_min_1p8x", "metric": "measured_end_to_end_speedup", "threshold": ">= 1.8x on slowest domain", "scope": "throughput benchmark"},
            ],
        },
    )
    _write_json(
        tmp_path / "runs/ligand_scaleup_kpi_current.json",
        {
            "summary": {
                "slowest_task_at_1m": {
                    "task_id": "ion_trpv1_chembl50_full",
                    "domain": "ion_channel",
                    "projected_1m_wall_hr": 16.2,
                    "stage2_share_pct": 89.9,
                }
            }
        },
    )
    _write_json(
        tmp_path / "runs/comparison.json",
        {
            "tasks_with_pr_improvement": 0,
            "tasks_with_pr_regression": 1,
            "profile_changed_task_count": 2,
            "task_rows": [
                {
                    "task_id": "ion_trpv1_chembl50_full",
                    "kind": "ligand_stress",
                    "baseline_pass": True,
                    "candidate_pass": True,
                    "delta_pr_auc": -0.010,
                    "delta_top20_hit_rate": 0.0,
                }
            ],
        },
    )
    _write_pipeline_summary(
        tmp_path / "runs/base_trpv1_pipeline_summary.json",
        total_latency_sec=600.0,
        stage2_latency_sec=540.0,
        queue_rate_stage2_rows_per_sec=18.5,
    )
    _write_pipeline_summary(
        tmp_path / "runs/cand_trpv1_pipeline_summary.json",
        total_latency_sec=300.0,
        stage2_latency_sec=250.0,
        queue_rate_stage2_rows_per_sec=36.0,
    )
    _write_run_summary_with_tasks(
        tmp_path / "runs/baseline_summary.json",
        [
            {
                "task_id": "ion_trpv1_chembl50_full",
                "domain": "ion_channel",
                "kind": "ligand_stress",
                "pipeline_summary_json": str(tmp_path / "runs/base_trpv1_pipeline_summary.json"),
            }
        ],
    )
    _write_run_summary_with_tasks(
        tmp_path / "runs/candidate_summary.json",
        [
            {
                "task_id": "ion_trpv1_chembl50_full",
                "domain": "ion_channel",
                "kind": "ligand_stress",
                "pipeline_summary_json": str(tmp_path / "runs/cand_trpv1_pipeline_summary.json"),
            }
        ],
    )

    payload = mod.build_payload(
        pilot_json="runs/ligand_scaleup_100k_pilot_current.json",
        kpi_json="runs/ligand_scaleup_kpi_current.json",
        comparison_json="runs/comparison.json",
        baseline_summary_json="runs/baseline_summary.json",
        candidate_summary_json="runs/candidate_summary.json",
    )

    speed_row = next(row for row in payload["guardrail_rows"] if row["guardrail_id"] == "slowest_domain_speedup_min_1p8x")
    assert speed_row["pass"] is True
    assert speed_row["observed_value"] == "2.000x"
    assert payload["measured_speedup_summary"]["slowest_task_measured"] is True
    assert payload["measured_speedup_summary"]["slowest_task"]["task_id"] == "ion_trpv1_chembl50_full"
    assert payload["claim_safe"] is True
    assert payload["claim_safe_status"] == "claim_safe_with_measured_speedup"
    _contains_tokens(payload["recommended_next_action"], "claim-safe", "measured", "speedup", "throughput")


def test_build_payload_with_measured_speedup_below_threshold_marks_speed_guardrail_fail(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    _write_json(
        tmp_path / "runs/ligand_scaleup_100k_pilot_current.json",
        {
            "comparison_kind": "size_shift_operational_regression",
            "scope_summary": {"full_task_count_100k": 6, "smoke_task_count_unchanged": 3, "domains_touched": ["gpcr"]},
            "guardrail_rows": [
                {"guardrail_id": "no_pass_to_fail", "metric": "set_pass_transition", "threshold": "0 pass->fail transitions", "scope": "regression slice"},
                {"guardrail_id": "pr_auc_drop_max_0p02", "metric": "ranking_pr_auc_delta", "threshold": ">= -0.02 absolute", "scope": "regression slice"},
                {"guardrail_id": "top20_hit_drop_max_1", "metric": "top20_hit_count_delta", "threshold": ">= -1 hit", "scope": "regression slice"},
                {"guardrail_id": "slowest_domain_speedup_min_1p8x", "metric": "measured_end_to_end_speedup", "threshold": ">= 1.8x on slowest domain", "scope": "throughput benchmark"},
            ],
        },
    )
    _write_json(
        tmp_path / "runs/ligand_scaleup_kpi_current.json",
        {
            "summary": {
                "slowest_task_at_1m": {
                    "task_id": "gpcr_core_full",
                    "domain": "gpcr",
                    "projected_1m_wall_hr": 4.2,
                    "stage2_share_pct": 82.0,
                }
            }
        },
    )
    _write_json(
        tmp_path / "runs/comparison.json",
        {
            "tasks_with_pr_improvement": 0,
            "tasks_with_pr_regression": 1,
            "profile_changed_task_count": 1,
            "task_rows": [
                {
                    "task_id": "gpcr_core_full",
                    "kind": "ligand_stress",
                    "baseline_pass": True,
                    "candidate_pass": True,
                    "delta_pr_auc": -0.005,
                    "delta_top20_hit_rate": 0.0,
                }
            ],
        },
    )
    _write_pipeline_summary(
        tmp_path / "runs/base_gpcr_pipeline_summary.json",
        total_latency_sec=180.0,
        stage2_latency_sec=140.0,
        queue_rate_stage2_rows_per_sec=70.0,
    )
    _write_pipeline_summary(
        tmp_path / "runs/cand_gpcr_pipeline_summary.json",
        total_latency_sec=150.0,
        stage2_latency_sec=120.0,
        queue_rate_stage2_rows_per_sec=82.0,
    )
    _write_run_summary_with_tasks(
        tmp_path / "runs/baseline_summary.json",
        [
            {
                "task_id": "gpcr_core_full",
                "domain": "gpcr",
                "kind": "ligand_stress",
                "pipeline_summary_json": str(tmp_path / "runs/base_gpcr_pipeline_summary.json"),
            }
        ],
    )
    _write_run_summary_with_tasks(
        tmp_path / "runs/candidate_summary.json",
        [
            {
                "task_id": "gpcr_core_full",
                "domain": "gpcr",
                "kind": "ligand_stress",
                "pipeline_summary_json": str(tmp_path / "runs/cand_gpcr_pipeline_summary.json"),
            }
        ],
    )

    payload = mod.build_payload(
        pilot_json="runs/ligand_scaleup_100k_pilot_current.json",
        kpi_json="runs/ligand_scaleup_kpi_current.json",
        comparison_json="runs/comparison.json",
        baseline_summary_json="runs/baseline_summary.json",
        candidate_summary_json="runs/candidate_summary.json",
    )

    speed_row = next(row for row in payload["guardrail_rows"] if row["guardrail_id"] == "slowest_domain_speedup_min_1p8x")
    assert speed_row["pass"] is False
    assert speed_row["observed_value"] == "1.200x"
    assert payload["claim_safe"] is True
    assert payload["claim_safe_status"] == "claim_safe_but_speedup_guardrail_failed"
    _contains_tokens(payload["recommended_next_action"], "speedup", "below", "slowest", "launch")
