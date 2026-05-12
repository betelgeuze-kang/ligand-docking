from pathlib import Path
import json

from tools import build_ligand_speedpack_ab_summary as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _contains_tokens(text: str, *tokens: str) -> None:
    lowered = text.lower()
    for token in tokens:
        assert token.lower() in lowered


def test_build_payload_prelaunch_ab_pending_speed_and_comparison(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    _write_json(
        tmp_path / "runs/ligand_speedpack_ab_current.json",
        {
            "comparison_kind": "equal_size_speedpack_ab",
            "scope_summary": {"ligand_task_count": 1, "domains_touched": ["ion_channel"]},
            "preflight_notes": ["TRPV1 equal-size A/B pending comparison"],
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
                }
            }
        },
    )

    payload = mod.build_payload(
        ab_json="runs/ligand_speedpack_ab_current.json",
        ab_spec_json="runs/ligand_speedpack_ab_current/specs/ligand_speedpack_ab_current_v1.json",
        comparison_json="runs/missing_comparison.json",
        baseline_summary_json="runs/missing_baseline.json",
        candidate_summary_json="runs/missing_candidate.json",
        baseline_sla_json="runs/missing_baseline_sla.json",
        candidate_sla_json="runs/missing_candidate_sla.json",
        kpi_json="runs/ligand_scaleup_kpi_current.json",
    )

    assert payload["benchmark_stage"] == "prelaunch_ab_scaffold"
    assert payload["comparison_artifact_ready"] is False
    assert payload["sla_artifact_ready"] is False
    assert payload["claim_safe"] is None
    assert payload["commercialization_ready"] is None
    assert payload["guardrail_pending_count"] >= 3
    _contains_tokens(payload["recommended_next_action"], "equal-size", "baseline", "candidate", "artifacts")


def test_build_payload_post_run_ab_with_speed(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    _write_json(
        tmp_path / "runs/ligand_speedpack_ab_current.json",
        {"comparison_kind": "equal_size_speedpack_ab", "scope_summary": {"ligand_task_count": 1, "domains_touched": ["ion_channel"]}},
    )
    _write_json(
        tmp_path / "runs/comparison.json",
        {
            "tasks_with_pr_improvement": 0,
            "tasks_with_pr_regression": 1,
            "profile_changed_task_count": 1,
            "task_rows": [
                {
                    "task_id": "ion_trpv1_chembl50_full",
                    "kind": "ligand_stress",
                    "domain": "ion_channel",
                    "baseline_pass": True,
                    "candidate_pass": True,
                    "delta_pr_auc": -0.008,
                    "delta_top20_hit_rate": 0.0,
                }
            ],
        },
    )
    _write_json(
        tmp_path / "runs/baseline_summary.json",
        {"sets": [{"set_id": "set1", "pass": True}, {"set_id": "set2", "pass": True}]},
    )
    _write_json(
        tmp_path / "runs/candidate_summary.json",
        {"sets": [{"set_id": "set1", "pass": True}, {"set_id": "set2", "pass": True}]},
    )
    _write_json(
        tmp_path / "runs/baseline_sla.json",
        {
            "total_latency_sec": 600.0,
            "queue_rate_stage2_rows_per_sec": 20.0,
            "durations_sec": {"stage2_trajectory_sec": 500.0},
        },
    )
    _write_json(
        tmp_path / "runs/candidate_sla.json",
        {
            "total_latency_sec": 450.0,
            "queue_rate_stage2_rows_per_sec": 26.0,
            "durations_sec": {"stage2_trajectory_sec": 380.0},
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
                }
            }
        },
    )

    payload = mod.build_payload(
        ab_json="runs/ligand_speedpack_ab_current.json",
        ab_spec_json="runs/ligand_speedpack_ab_current/specs/ligand_speedpack_ab_current_v1.json",
        comparison_json="runs/comparison.json",
        baseline_summary_json="runs/baseline_summary.json",
        candidate_summary_json="runs/candidate_summary.json",
        baseline_sla_json="runs/baseline_sla.json",
        candidate_sla_json="runs/candidate_sla.json",
        kpi_json="runs/ligand_scaleup_kpi_current.json",
    )

    assert payload["benchmark_stage"] == "post_run_ab_with_speed"
    assert payload["claim_safe"] is True
    assert payload["commercialization_ready"] is True
    assert payload["sla_metrics"]["stage2_latency_speedup"] > 1.2
    assert payload["sla_metrics"]["total_latency_speedup"] > 1.0
    pr_row = next(row for row in payload["guardrail_rows"] if row["guardrail_id"] == "pr_auc_drop_max_0p01")
    assert pr_row["pass"] is True
    speed_row = next(row for row in payload["guardrail_rows"] if row["guardrail_id"] == "stage2_speedup_min_1p2x")
    assert speed_row["pass"] is True
    _contains_tokens(payload["recommended_next_action"], "claim-safe", "speed-positive", "100k/1m", "throughput")


def test_build_payload_post_run_ab_missing_optional_speed_and_top20_are_pending(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    _write_json(
        tmp_path / "runs/ligand_speedpack_ab_current.json",
        {"comparison_kind": "equal_size_speedpack_ab", "scope_summary": {"ligand_task_count": 1, "domains_touched": ["ion_channel"]}},
    )
    _write_json(
        tmp_path / "runs/comparison.json",
        {
            "task_rows": [
                {
                    "task_id": "ion_trpv1_chembl50_full",
                    "kind": "ligand_stress",
                    "domain": "ion_channel",
                    "baseline_pass": True,
                    "candidate_pass": True,
                    "delta_pr_auc": -0.001,
                    "delta_top20_hit_rate": None,
                }
            ],
        },
    )
    _write_json(tmp_path / "runs/baseline_summary.json", {"sets": [{"set_id": "set1", "pass": True}]})
    _write_json(tmp_path / "runs/candidate_summary.json", {"sets": [{"set_id": "set1", "pass": True}]})

    payload = mod.build_payload(
        ab_json="runs/ligand_speedpack_ab_current.json",
        ab_spec_json="runs/ligand_speedpack_ab_current/specs/ligand_speedpack_ab_current_v1.json",
        comparison_json="runs/comparison.json",
        baseline_summary_json="runs/baseline_summary.json",
        candidate_summary_json="runs/candidate_summary.json",
        baseline_sla_json="runs/missing_baseline_sla.json",
        candidate_sla_json="runs/missing_candidate_sla.json",
        kpi_json="runs/missing_kpi.json",
    )

    assert payload["benchmark_stage"] == "post_run_ab_no_speed"
    assert payload["claim_safe"] is True
    assert payload["commercialization_ready"] is None
    top20_row = next(row for row in payload["guardrail_rows"] if row["guardrail_id"] == "top20_hit_rate_drop_max_0p05")
    speed_row = next(row for row in payload["guardrail_rows"] if row["guardrail_id"] == "stage2_speedup_min_1p2x")
    assert top20_row["pass"] is None
    assert speed_row["pass"] is None


def test_build_payload_uses_runtime_json_for_multi_task_speed_guardrail(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    _write_json(
        tmp_path / "runs/ligand_speedpack_ab_current.json",
        {"comparison_kind": "equal_size_speedpack_ab", "scope_summary": {"ligand_task_count": 2, "domains_touched": ["ion_channel"]}},
    )
    _write_json(
        tmp_path / "runs/comparison.json",
        {
            "task_rows": [
                {
                    "task_id": "ion_trpv1_chembl20_full",
                    "kind": "ligand_stress",
                    "domain": "ion_channel",
                    "baseline_pass": True,
                    "candidate_pass": True,
                    "delta_pr_auc": 0.02,
                },
                {
                    "task_id": "ion_trpv1_chembl50_full",
                    "kind": "ligand_stress",
                    "domain": "ion_channel",
                    "baseline_pass": True,
                    "candidate_pass": True,
                    "delta_pr_auc": 0.01,
                },
            ],
        },
    )
    _write_json(tmp_path / "runs/baseline_summary.json", {"sets": [{"set_id": "set1", "pass": True}, {"set_id": "set2", "pass": True}]})
    _write_json(tmp_path / "runs/candidate_summary.json", {"sets": [{"set_id": "set1", "pass": True}, {"set_id": "set2", "pass": True}]})
    _write_json(
        tmp_path / "runs/runtime.json",
        {
            "rows": [
                {
                    "task_id": "ion_trpv1_chembl20_full",
                    "measured_stage2_speedup": None,
                    "baseline_stage2_runtime_sec": 500.0,
                    "candidate_stage2_runtime_sec": 350.0,
                },
                {
                    "task_id": "ion_trpv1_chembl50_full",
                    "measured_stage2_speedup": 1.30,
                },
            ]
        },
    )

    payload = mod.build_payload(
        ab_json="runs/ligand_speedpack_ab_current.json",
        ab_spec_json="runs/ligand_speedpack_ab_current/specs/ligand_speedpack_ab_current_v1.json",
        comparison_json="runs/comparison.json",
        baseline_summary_json="runs/baseline_summary.json",
        candidate_summary_json="runs/candidate_summary.json",
        baseline_sla_json="runs/missing_baseline_sla.json",
        candidate_sla_json="runs/missing_candidate_sla.json",
        runtime_json="runs/runtime.json",
        kpi_json="runs/missing_kpi.json",
    )

    assert payload["benchmark_stage"] == "post_run_ab_with_speed"
    assert payload["sla_metrics"]["source"] == "runtime_json"
    assert payload["sla_metrics"]["stage2_latency_speedup"] == 1.30
    assert payload["claim_safe"] is True
    assert payload["commercialization_ready"] is True


def test_build_payload_falls_back_to_candidate_spec_when_ab_json_missing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    _write_json(
        tmp_path / "runs/ligand_speedpack_ab_current/specs/ligand_speedpack_ab_current_v1.json",
        {
            "protocol_id": "ligand_speedpack_ab_v1",
            "global_governance": {"comparison_kind": "equal_size_speedpack_ab"},
            "sets": [
                {
                    "set_id": "set1_core_blind",
                    "tasks": [
                        {
                            "task_id": "ion_trpv1_chembl20_full",
                            "kind": "ligand_stress",
                            "domain": "ion_channel",
                            "ligand_sizes": "10000",
                        }
                    ],
                },
                {
                    "set_id": "set2_expanded_ood",
                    "tasks": [
                        {
                            "task_id": "ion_trpv1_chembl50_full",
                            "kind": "ligand_stress",
                            "domain": "ion_channel",
                            "ligand_sizes": "10000",
                        }
                    ],
                },
            ],
        },
    )

    payload = mod.build_payload(
        ab_json="runs/missing_ab.json",
        ab_spec_json="runs/ligand_speedpack_ab_current/specs/ligand_speedpack_ab_current_v1.json",
        comparison_json="runs/missing_comparison.json",
        baseline_summary_json="runs/missing_baseline.json",
        candidate_summary_json="runs/missing_candidate.json",
        baseline_sla_json="runs/missing_baseline_sla.json",
        candidate_sla_json="runs/missing_candidate_sla.json",
        kpi_json="runs/missing_kpi.json",
    )

    assert payload["comparison_kind"] == "equal_size_speedpack_ab"
    assert payload["scope_summary"]["ligand_task_count"] == 2
    assert payload["scope_summary"]["selected_full_task_count"] == 2
    assert payload["scope_summary"]["domains_touched"] == ["ion_channel"]
    assert "reconstructed from candidate spec" in payload["preflight_notes"][0]
    assert payload["input_artifacts"]["ab_spec_json"].endswith("runs/ligand_speedpack_ab_current/specs/ligand_speedpack_ab_current_v1.json")
