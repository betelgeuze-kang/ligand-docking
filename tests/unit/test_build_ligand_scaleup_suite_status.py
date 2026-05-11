from __future__ import annotations

import json
from pathlib import Path

from tools import build_ligand_scaleup_suite_status as mod


class _Args:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _contains_tokens(text: str, *tokens: str) -> None:
    lowered = text.lower()
    for token in tokens:
        assert token.lower() in lowered


def test_suite_status_uses_available_current_artifacts_and_matches_100k_summary(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    _write(
        runs / "ligand_speedpack_ab_summary_current.json",
        {
            "benchmark_stage": "prelaunch_ab_scaffold",
            "comparison_kind": "equal_size_speedpack_ab",
            "claim_safe": True,
            "commercialization_ready": False,
            "comparison_artifact_ready": False,
            "scope_summary": {
                "selected_task_count": 2,
                "selected_full_task_count": 2,
                "selected_smoke_task_count": 0,
                "domains_touched": ["ion_channel"],
            },
            "recommended_next_action": "Run equal-size A/B.",
        },
    )
    _write(
        runs / "ligand_scaleup_100k_pilot_current.json",
        {
            "comparison_kind": "size_shift_operational_regression",
            "launch_readiness": {"status": "ready", "next_required_step": "Launch 100k pilot."},
            "scope_summary": {
                "ligand_stress_task_count": 9,
                "full_task_count_100k": 6,
                "smoke_task_count_unchanged": 3,
                "domains_touched": ["gpcr", "ion_channel", "kinase"],
            },
        },
    )
    _write(
        runs / "ligand_scaleup_100k_pilot_dryrun_current.json",
        {
            "comparison_enabled": True,
            "launch_readiness": {"status": "ready", "comparison_enabled": True},
        },
    )
    _write(
        runs / "ligand_scaleup_benchmark_summary_current.json",
        {
            "benchmark_stage": "post_run_comparison",
            "comparison_kind": "size_shift_operational_regression",
            "claim_safe_status": "claim_safe",
            "commercialization_ready": True,
            "comparison_artifact_ready": True,
            "recommended_next_action": "Advance to 1M.",
            "input_artifacts": {
                "pilot_json": str((runs / "ligand_scaleup_100k_pilot_current.json").resolve()),
            },
        },
    )
    _write(
        runs / "ligand_scaleup_1m_pilot_current.json",
        {
            "comparison_kind": "size_shift_operational_regression",
            "launch_readiness": {"status": "ready", "next_required_step": "Launch 1M pilot."},
            "scope_summary": {
                "ligand_stress_task_count": 9,
                "full_task_count_target": 6,
                "smoke_task_count_unchanged": 3,
            },
            "target_scale_label": "1M",
        },
    )
    _write(
        runs / "ligand_scaleup_1m_pilot_dryrun_current.json",
        {
            "comparison_enabled": True,
            "launch_readiness": {"status": "ready", "comparison_enabled": True},
            "target_scale_label": "1M",
        },
    )
    args = _Args(
        suite_dryrun_json="runs/ligand_scaleup_suite_dryrun_current.json",
        suite_execute_json="runs/ligand_scaleup_suite_current.json",
        ab_summary_json="runs/ligand_speedpack_ab_summary_current.json",
        pilot_100k_json="runs/ligand_scaleup_100k_pilot_current.json",
        pilot_100k_dryrun_json="runs/ligand_scaleup_100k_pilot_dryrun_current.json",
        pilot_100k_summary_json="runs/ligand_scaleup_benchmark_summary_current.json",
        pilot_1m_json="runs/ligand_scaleup_1m_pilot_current.json",
        pilot_1m_dryrun_json="runs/ligand_scaleup_1m_pilot_dryrun_current.json",
        pilot_1m_summary_json="runs/ligand_scaleup_1m_benchmark_summary_current.json",
        shared_benchmark_summary_json="runs/ligand_scaleup_benchmark_summary_current.json",
    )
    mod.ROOT = tmp_path
    payload = mod.build_suite_status(args)
    rows = {row["suite_id"]: row for row in payload["suite_rows"]}

    assert payload["summary"]["suite_count"] == 3
    assert rows["equal_size_ab"]["comparison_kind"] == "equal_size_speedpack_ab"
    assert rows["equal_size_ab"]["claim_safe_status"] == "claim_safe"
    assert rows["equal_size_ab"]["progress_status"] == "prelaunch_scaffold"
    assert rows["equal_size_ab"]["refresh_status"] == "summary_attached"
    assert rows["pilot_100k"]["summary_attached"] is True
    assert rows["pilot_100k"]["benchmark_stage"] == "post_run_comparison"
    assert rows["pilot_100k"]["claim_safe_status"] == "claim_safe"
    assert rows["pilot_100k"]["commercialization_ready"] is True
    assert rows["pilot_100k"]["progress_status"] == "post_run_with_summary"
    assert rows["pilot_100k"]["refresh_status"] == "summary_attached"
    assert rows["pilot_1m"]["summary_attached"] is False
    assert rows["pilot_1m"]["benchmark_stage"] == "prelaunch_scaffold"
    assert rows["pilot_1m"]["readiness_status"] == "ready"
    assert payload["summary"]["post_run_suite_count"] == 1
    assert payload["summary"]["refreshed_suite_count"] == 2

    out_json = runs / "ligand_scaleup_suite_status_current.json"
    out_csv = runs / "ligand_scaleup_suite_status_current.csv"
    out_md = runs / "ligand_scaleup_suite_status_current.md"
    out_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    mod._write_csv(out_csv, payload["suite_rows"])
    mod._write_md(out_md, payload)
    assert out_csv.exists()
    assert out_md.exists()
    assert "pilot_100k" in out_md.read_text(encoding="utf-8")


def test_suite_status_marks_100k_ready_from_gpcr_frontier_recovery(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    _write(
        runs / "ligand_scaleup_100k_pilot_current.json",
        {
            "comparison_kind": "size_shift_operational_regression",
            "launch_readiness": {"status": "ready", "next_required_step": "Launch 100k pilot."},
            "scope_summary": {
                "ligand_stress_task_count": 9,
                "full_task_count_100k": 6,
                "smoke_task_count_unchanged": 3,
                "domains_touched": ["gpcr", "ion_channel", "kinase"],
            },
        },
    )
    _write(
        runs / "ligand_scaleup_100k_pilot_dryrun_current.json",
        {"comparison_enabled": True, "launch_readiness": {"status": "ready"}},
    )
    _write(
        runs / "ligand_scaleup_benchmark_summary_current.json",
        {
            "benchmark_stage": "post_run_comparison",
            "comparison_kind": "size_shift_operational_regression",
            "claim_safe": False,
            "claim_safe_status": "regression_guardrail_failed",
            "commercialization_ready": False,
            "comparison_artifact_ready": True,
            "recommended_next_action": "Rerun GPCR comparison.",
            "input_artifacts": {
                "pilot_json": str((runs / "ligand_scaleup_100k_pilot_current.json").resolve()),
            },
        },
    )
    _write(
        runs / "gpcr_scaleup_guardrail_frontier_packet_current.json",
        {
            "summary": {
                "packet_ready": True,
                "claim_safe": True,
                "claim_safe_status": "guardrail_recovered_candidate_available",
                "top_candidate_id": "2026-05-10_beta_blocker_rescue_v2_family_balanced100k_r1",
                "packet_artifact": "runs/gpcr_scaleup_guardrail_frontier_packet_current.md",
                "next_required_step": "Promote the family-balanced GPCR 100k recovery candidate.",
            }
        },
    )
    args = _Args(
        suite_dryrun_json="runs/ligand_scaleup_suite_dryrun_current.json",
        suite_execute_json="runs/ligand_scaleup_suite_current.json",
        ab_summary_json="runs/ligand_speedpack_ab_summary_current.json",
        pilot_100k_json="runs/ligand_scaleup_100k_pilot_current.json",
        pilot_100k_dryrun_json="runs/ligand_scaleup_100k_pilot_dryrun_current.json",
        pilot_100k_summary_json="runs/ligand_scaleup_benchmark_summary_current.json",
        pilot_1m_json="runs/ligand_scaleup_1m_pilot_current.json",
        pilot_1m_dryrun_json="runs/ligand_scaleup_1m_pilot_dryrun_current.json",
        pilot_1m_summary_json="runs/ligand_scaleup_1m_benchmark_summary_current.json",
        shared_benchmark_summary_json="runs/ligand_scaleup_benchmark_summary_current.json",
        gpcr_scaleup_frontier_json="runs/gpcr_scaleup_guardrail_frontier_packet_current.json",
    )
    mod.ROOT = tmp_path
    payload = mod.build_suite_status(args)
    rows = {row["suite_id"]: row for row in payload["suite_rows"]}

    assert rows["pilot_100k"]["claim_safe_status"] == "guardrail_recovered_candidate_available"
    assert rows["pilot_100k"]["commercialization_ready"] is True
    assert rows["pilot_100k"]["guardrail_frontier_top_candidate_id"].endswith("family_balanced100k_r1")
    assert payload["summary"]["commercialization_ready_suite_count"] == 1
    assert payload["summary"]["pending_suite_ids"] == ["equal_size_ab", "pilot_1m"]
    assert payload["summary"]["gpcr_guardrail_frontier_status"] == "guardrail_recovered_candidate_available"


def test_suite_status_missing_artifacts_falls_back_cleanly_and_ignores_mismatched_summary(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    _write(
        runs / "ligand_scaleup_100k_pilot_current.json",
        {
            "comparison_kind": "size_shift_operational_regression",
            "launch_readiness": {"status": "ready"},
            "scope_summary": {"ligand_stress_task_count": 9, "full_task_count_100k": 6, "smoke_task_count_unchanged": 3},
        },
    )
    _write(
        runs / "ligand_scaleup_benchmark_summary_current.json",
        {
            "benchmark_stage": "post_run_comparison",
            "claim_safe_status": "claim_safe",
            "commercialization_ready": True,
            "input_artifacts": {
                "pilot_json": str((runs / "ligand_scaleup_1m_pilot_current.json").resolve()),
            },
        },
    )
    args = _Args(
        suite_dryrun_json="runs/ligand_scaleup_suite_dryrun_current.json",
        suite_execute_json="runs/ligand_scaleup_suite_current.json",
        ab_summary_json="runs/ligand_speedpack_ab_summary_current.json",
        pilot_100k_json="runs/ligand_scaleup_100k_pilot_current.json",
        pilot_100k_dryrun_json="runs/ligand_scaleup_100k_pilot_dryrun_current.json",
        pilot_100k_summary_json="runs/ligand_scaleup_benchmark_summary_current.json",
        pilot_1m_json="runs/ligand_scaleup_1m_pilot_current.json",
        pilot_1m_dryrun_json="runs/ligand_scaleup_1m_pilot_dryrun_current.json",
        pilot_1m_summary_json="runs/ligand_scaleup_1m_benchmark_summary_current.json",
        shared_benchmark_summary_json="runs/ligand_scaleup_benchmark_summary_current.json",
    )
    mod.ROOT = tmp_path
    payload = mod.build_suite_status(args)
    rows = {row["suite_id"]: row for row in payload["suite_rows"]}

    assert rows["equal_size_ab"]["artifact_state"] == "missing"
    assert rows["pilot_100k"]["summary_attached"] is False
    assert rows["pilot_100k"]["benchmark_stage"] == "prelaunch_scaffold"
    assert rows["pilot_100k"]["claim_safe_status"] == "pending"
    assert rows["pilot_100k"]["progress_status"] == "prelaunch_ready"
    assert rows["pilot_100k"]["refresh_status"] == "missing"
    assert rows["pilot_1m"]["artifact_state"] == "missing"
    assert payload["summary"]["summary_attached_suite_count"] == 0


def test_suite_status_uses_shared_summary_for_1m_and_marks_post_run_refresh(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    _write(
        runs / "ligand_scaleup_1m_pilot_current.json",
        {
            "ok": True,
            "candidate_run_root": str((runs / "external_validation_blind_runs/external_validation_blind_runs_2026-03-23_scaleup_1m_pilot_v1").resolve()),
            "comparison_skipped": True,
            "comparison_kind": "size_shift_operational_regression",
            "post_run_refresh": {"attempted": True, "ok": True},
            "launch_readiness": {"status": "ready"},
            "scope_summary": {
                "ligand_stress_task_count": 9,
                "full_task_count_target": 6,
                "smoke_task_count_unchanged": 3,
            },
            "target_scale_label": "1M",
        },
    )
    _write(
        runs / "ligand_scaleup_benchmark_summary_current.json",
        {
            "benchmark_stage": "post_run_comparison",
            "comparison_kind": "size_shift_operational_regression",
            "claim_safe_status": "claim_safe_pending_speed_evidence",
            "commercialization_ready": False,
            "comparison_artifact_ready": True,
            "recommended_next_action": "Collect measured 1M throughput.",
            "input_artifacts": {
                "pilot_json": str((runs / "ligand_scaleup_1m_pilot_current.json").resolve()),
            },
        },
    )
    args = _Args(
        suite_dryrun_json="runs/ligand_scaleup_suite_dryrun_current.json",
        suite_execute_json="runs/ligand_scaleup_suite_current.json",
        ab_summary_json="runs/ligand_speedpack_ab_summary_current.json",
        pilot_100k_json="runs/ligand_scaleup_100k_pilot_current.json",
        pilot_100k_dryrun_json="runs/ligand_scaleup_100k_pilot_dryrun_current.json",
        pilot_100k_summary_json="runs/ligand_scaleup_benchmark_summary_current.json",
        pilot_1m_json="runs/ligand_scaleup_1m_pilot_current.json",
        pilot_1m_dryrun_json="runs/ligand_scaleup_1m_pilot_dryrun_current.json",
        pilot_1m_summary_json="runs/ligand_scaleup_1m_benchmark_summary_current.json",
        shared_benchmark_summary_json="runs/ligand_scaleup_benchmark_summary_current.json",
    )
    mod.ROOT = tmp_path
    payload = mod.build_suite_status(args)
    rows = {row["suite_id"]: row for row in payload["suite_rows"]}

    assert rows["pilot_1m"]["summary_attached"] is True
    assert rows["pilot_1m"]["benchmark_stage"] == "post_run_comparison"
    assert rows["pilot_1m"]["progress_status"] == "post_run_with_summary"
    assert rows["pilot_1m"]["refresh_status"] == "summary_attached"
    assert rows["pilot_1m"]["comparison_status"] == "available"


def test_suite_status_uses_suite_runner_dry_run_and_execute_artifacts(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    _write(
        runs / "ligand_scaleup_suite_dryrun_current.json",
        {
            "generated_at_local": "2026-03-23T20:00:00+09:00",
            "enabled_stage_count": 2,
            "stages": [
                {"stage_id": "pilot_100k", "enabled": True, "note": "100k pilot planned from suite dry-run"},
                {"stage_id": "pilot_1m", "enabled": False, "note": "1M disabled in suite dry-run"},
            ],
        },
    )
    _write(
        runs / "ligand_scaleup_suite_current.json",
        {
            "generated_at_local": "2026-03-23T20:30:00+09:00",
            "completed_stage_count": 1,
            "ok": False,
            "failed_stage_id": "pilot_100k",
            "stage_results": [
                {
                    "stage_id": "pilot_100k",
                    "ok": False,
                    "returncode": 2,
                    "suite_status_refresh": {"ok": False},
                }
            ],
            "suite_status_refreshes": [{"stage_id": "pilot_100k", "ok": False}],
        },
    )
    args = _Args(
        suite_dryrun_json="runs/ligand_scaleup_suite_dryrun_current.json",
        suite_execute_json="runs/ligand_scaleup_suite_current.json",
        ab_summary_json="runs/ligand_speedpack_ab_summary_current.json",
        pilot_100k_json="runs/ligand_scaleup_100k_pilot_current.json",
        pilot_100k_dryrun_json="runs/ligand_scaleup_100k_pilot_dryrun_current.json",
        pilot_100k_summary_json="runs/ligand_scaleup_benchmark_summary_current.json",
        pilot_1m_json="runs/ligand_scaleup_1m_pilot_current.json",
        pilot_1m_dryrun_json="runs/ligand_scaleup_1m_pilot_dryrun_current.json",
        pilot_1m_summary_json="runs/ligand_scaleup_1m_benchmark_summary_current.json",
        shared_benchmark_summary_json="runs/ligand_scaleup_benchmark_summary_current.json",
    )
    mod.ROOT = tmp_path
    payload = mod.build_suite_status(args)
    rows = {row["suite_id"]: row for row in payload["suite_rows"]}

    assert payload["suite_runner"]["latest_kind"] == "execute"
    assert payload["suite_runner"]["execute_ok"] is False
    assert rows["pilot_100k"]["artifact_state"] == "partial"
    assert rows["pilot_100k"]["progress_status"] == "suite_execute_failed"
    assert rows["pilot_100k"]["benchmark_stage"] == "suite_execute_failed"
    assert rows["pilot_100k"]["refresh_status"] == "refresh_failed"
    _contains_tokens(rows["pilot_100k"]["recommended_next_action"], "100k", "planned", "dry-run")
    assert rows["pilot_1m"]["progress_status"] == "suite_stage_disabled"
    assert rows["pilot_1m"]["benchmark_stage"] == "suite_stage_disabled"
