import json
from pathlib import Path
from types import SimpleNamespace

from tools import monitor_ligand_scaleup_suite as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _contains_tokens(text: str, *tokens: str) -> None:
    lowered = text.lower()
    for token in tokens:
        assert token.lower() in lowered


def test_build_suite_payload_handles_prelaunch_and_benchmark_ready(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setattr(mod, "_proc_lines", lambda pattern: [])

    runs = tmp_path / "runs"
    _write_json(
        runs / "ligand_speedpack_ab_summary_current.json",
        {
            "benchmark_stage": "prelaunch_ab_scaffold",
            "comparison_artifact_ready": False,
            "recommended_next_action": "prepare equal-size A/B baseline and candidate artifacts",
        },
    )
    _write_json(
        runs / "ligand_scaleup_100k_pilot_dryrun_current.json",
        {
            "candidate_run_root": str(runs / "external_validation_blind_runs/external_validation_blind_runs_2026-03-23_scaleup_100k_pilot_v1"),
            "launch_readiness": {
                "ready": True,
                "status": "ready",
                "blocking_issue_count": 0,
                "comparison_enabled": True,
            },
        },
    )
    _write_json(
        runs / "ligand_scaleup_1m_pilot_dryrun_current.json",
        {
            "candidate_run_root": str(runs / "external_validation_blind_runs/external_validation_blind_runs_2026-03-23_scaleup_1m_pilot_v1"),
            "launch_readiness": {
                "ready": False,
                "status": "blocked",
                "blocking_issue_count": 1,
                "comparison_enabled": True,
            },
        },
    )
    _write_json(
        runs / "ligand_scaleup_benchmark_summary_current.json",
        {
            "benchmark_stage": "comparison_ready",
            "comparison_artifact_ready": True,
            "claim_safe_status": "claim_safe_with_measured_speedup",
            "recommended_next_action": "advance to the next larger scale slice",
            "input_artifacts": {
                "pilot_json": str(runs / "ligand_scaleup_100k_pilot_current.json"),
            },
        },
    )

    args = SimpleNamespace(
        suite_dryrun_json="runs/ligand_scaleup_suite_dryrun_current.json",
        suite_execute_json="runs/ligand_scaleup_suite_current.json",
        ab_current_json="runs/ligand_speedpack_ab_current.json",
        ab_runtime_json="runs/ligand_speedpack_ab_runtime_current.json",
        ab_summary_json="runs/ligand_speedpack_ab_summary_current.json",
        ab_run_root="",
        pilot_100k_json="runs/ligand_scaleup_100k_pilot_current.json",
        pilot_100k_dryrun_json="runs/ligand_scaleup_100k_pilot_dryrun_current.json",
        pilot_100k_run_root="",
        pilot_1m_json="runs/ligand_scaleup_1m_pilot_current.json",
        pilot_1m_dryrun_json="runs/ligand_scaleup_1m_pilot_dryrun_current.json",
        pilot_1m_run_root="",
        benchmark_summary_json="runs/ligand_scaleup_benchmark_summary_current.json",
    )

    payload = mod.build_suite_payload(args)
    stages = {row["stage_id"]: row for row in payload["stages"]}

    assert stages["speedpack_ab"]["status"] == "prelaunch_ab_scaffold"
    assert stages["speedpack_ab"]["comparison"] == "pending"
    assert stages["speedpack_ab"]["refresh_status"] == "summary_attached"
    assert stages["pilot_100k"]["status"] == "comparison_ready"
    assert stages["pilot_100k"]["comparison"] == "ready"
    assert stages["pilot_100k"]["claim_safe_status"] == "claim_safe_with_measured_speedup"
    assert stages["pilot_100k"]["progress_status"] == "post_run_with_summary"
    assert stages["pilot_100k"]["refresh_status"] == "summary_attached"
    assert stages["pilot_1m"]["status"] == "blocked_prelaunch"
    assert stages["pilot_1m"]["comparison"] == "planned"
    assert stages["pilot_1m"]["progress_status"] == "prelaunch"


def test_build_suite_payload_uses_live_run_root_when_completed(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setattr(mod, "_proc_lines", lambda pattern: [])

    runs = tmp_path / "runs"
    run_root = runs / "external_validation_blind_runs/external_validation_blind_runs_2026-03-23_scaleup_1m_pilot_v1"
    _write_json(
        run_root / "summary.json",
        {
            "status": "completed",
            "updated_at_local": "2026-03-23T12:00:00+09:00",
        },
    )
    _write_json(
        runs / "ligand_scaleup_1m_pilot_dryrun_current.json",
        {
            "candidate_run_root": str(run_root),
            "launch_readiness": {
                "ready": True,
                "status": "ready",
                "blocking_issue_count": 0,
            },
        },
    )

    args = SimpleNamespace(
        suite_dryrun_json="runs/ligand_scaleup_suite_dryrun_current.json",
        suite_execute_json="runs/ligand_scaleup_suite_current.json",
        ab_current_json="runs/ligand_speedpack_ab_current.json",
        ab_runtime_json="runs/ligand_speedpack_ab_runtime_current.json",
        ab_summary_json="runs/ligand_speedpack_ab_summary_current.json",
        ab_run_root="",
        pilot_100k_json="runs/ligand_scaleup_100k_pilot_current.json",
        pilot_100k_dryrun_json="runs/ligand_scaleup_100k_pilot_dryrun_current.json",
        pilot_100k_run_root="",
        pilot_1m_json="runs/ligand_scaleup_1m_pilot_current.json",
        pilot_1m_dryrun_json="runs/ligand_scaleup_1m_pilot_dryrun_current.json",
        pilot_1m_run_root="",
        benchmark_summary_json="runs/ligand_scaleup_benchmark_summary_current.json",
    )

    payload = mod.build_suite_payload(args)
    stages = {row["stage_id"]: row for row in payload["stages"]}
    assert stages["pilot_1m"]["status"] == "completed"
    assert stages["pilot_1m"]["run_root"] == str(run_root)


def test_build_suite_payload_uses_suite_runner_artifacts_for_stage_fallback(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setattr(mod, "_proc_lines", lambda pattern: [])

    runs = tmp_path / "runs"
    _write_json(
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
    _write_json(
        runs / "ligand_scaleup_suite_current.json",
        {
            "generated_at_local": "2026-03-23T20:30:00+09:00",
            "completed_stage_count": 1,
            "ok": False,
            "failed_stage_id": "pilot_100k",
            "stage_results": [
                {"stage_id": "pilot_100k", "ok": False, "returncode": 2, "suite_status_refresh": {"ok": False}}
            ],
            "suite_status_refreshes": [{"stage_id": "pilot_100k", "ok": False}],
        },
    )

    args = SimpleNamespace(
        suite_dryrun_json="runs/ligand_scaleup_suite_dryrun_current.json",
        suite_execute_json="runs/ligand_scaleup_suite_current.json",
        ab_current_json="runs/ligand_speedpack_ab_current.json",
        ab_runtime_json="runs/ligand_speedpack_ab_runtime_current.json",
        ab_summary_json="runs/ligand_speedpack_ab_summary_current.json",
        ab_run_root="",
        pilot_100k_json="runs/ligand_scaleup_100k_pilot_current.json",
        pilot_100k_dryrun_json="runs/ligand_scaleup_100k_pilot_dryrun_current.json",
        pilot_100k_run_root="",
        pilot_1m_json="runs/ligand_scaleup_1m_pilot_current.json",
        pilot_1m_dryrun_json="runs/ligand_scaleup_1m_pilot_dryrun_current.json",
        pilot_1m_run_root="",
        benchmark_summary_json="runs/ligand_scaleup_benchmark_summary_current.json",
    )

    payload = mod.build_suite_payload(args)
    stages = {row["stage_id"]: row for row in payload["stages"]}

    assert payload["suite_runner"]["latest_kind"] == "execute"
    assert payload["suite_runner"]["execute_failed_stage_id"] == "pilot_100k"
    assert stages["pilot_100k"]["status"] == "suite_execute_failed"
    assert stages["pilot_100k"]["progress_status"] == "suite_execute_failed"
    assert stages["pilot_100k"]["refresh_status"] == "refresh_failed"
    _contains_tokens(" ".join(stages["pilot_100k"]["notes"]), "100k", "pilot", "suite", "dry-run")
    assert stages["pilot_1m"]["status"] == "suite_stage_disabled"
    assert stages["pilot_1m"]["progress_status"] == "suite_stage_disabled"


def test_build_suite_payload_shows_post_run_refresh_without_benchmark_summary(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setattr(mod, "_proc_lines", lambda pattern: [])

    runs = tmp_path / "runs"
    _write_json(
        runs / "ligand_scaleup_1m_pilot_current.json",
        {
            "ok": True,
            "candidate_run_root": str(runs / "external_validation_blind_runs/external_validation_blind_runs_2026-03-23_scaleup_1m_pilot_v1"),
            "comparison_skipped": True,
            "post_run_refresh": {
                "attempted": True,
                "ok": True,
            },
            "launch_readiness": {"ready": True, "status": "ready"},
        },
    )

    args = SimpleNamespace(
        ab_current_json="runs/ligand_speedpack_ab_current.json",
        ab_runtime_json="runs/ligand_speedpack_ab_runtime_current.json",
        ab_summary_json="runs/ligand_speedpack_ab_summary_current.json",
        ab_run_root="",
        pilot_100k_json="runs/ligand_scaleup_100k_pilot_current.json",
        pilot_100k_dryrun_json="runs/ligand_scaleup_100k_pilot_dryrun_current.json",
        pilot_100k_run_root="",
        pilot_1m_json="runs/ligand_scaleup_1m_pilot_current.json",
        pilot_1m_dryrun_json="runs/ligand_scaleup_1m_pilot_dryrun_current.json",
        pilot_1m_run_root="",
        benchmark_summary_json="runs/ligand_scaleup_benchmark_summary_current.json",
    )

    payload = mod.build_suite_payload(args)
    stages = {row["stage_id"]: row for row in payload["stages"]}
    assert stages["pilot_1m"]["status"] == "post_run_refreshed"
    assert stages["pilot_1m"]["refresh_status"] == "refresh_ok"
    assert stages["pilot_1m"]["progress_status"] == "post_run_partial"


def test_main_json_output(monkeypatch, capsys) -> None:
    fake_payload = {
        "generated_at_local": "2026-03-23T12:00:00+09:00",
        "suite_id": "ligand_scaleup_suite_monitor_current",
        "status_counts": {"prelaunch_ready": 1},
        "stage_count": 3,
        "stages": [],
    }
    monkeypatch.setattr(mod, "build_suite_payload", lambda args: fake_payload)

    rc = mod.main(["--json"])

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["suite_id"] == "ligand_scaleup_suite_monitor_current"
