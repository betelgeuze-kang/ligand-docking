from __future__ import annotations

import json
from pathlib import Path

from tools.product import build_developer_preview_large_model_oom_guard_receipt as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _ligand_source(*, claim_safe: bool = False) -> dict:
    return {
        "benchmark_stage": "post_run_comparison",
        "baseline_artifact_ready": True,
        "candidate_artifact_ready": True,
        "comparison_artifact_ready": True,
        "claim_safe": claim_safe,
        "claim_safe_status": "claim_safe_with_measured_speedup"
        if claim_safe
        else "regression_guardrail_failed",
        "guardrail_fail_count": 3,
        "kpi_summary": {"coverage_summary": {"missing_artifact_count": 0}},
    }


def _rocm_source(**overrides: object) -> dict:
    summary = {
        "status": "product_end_to_end_rocm_benchmark_ready",
        "benchmark_ready": True,
        "actual_end_to_end_run_evidence_ready": True,
        "run_pass": True,
        "failed_jobs": 0,
        "failure_rate": 0.0,
        "processed_jobs": 10000,
        "rocm_visible_device_count": 1,
        "rocm_end_to_end_throughput_ready": True,
        "rocm_hip_rust_runtime_ready": True,
    }
    summary.update(overrides)
    return {"summary": summary}


def test_ligand_scaleup_large_model_oom_guard_ready_without_promoting_regression_claim(
    tmp_path: Path,
) -> None:
    source = tmp_path / "runs/ligand_scaleup_benchmark_summary_current.json"
    _write_json(source, _ligand_source(claim_safe=False))

    payload = mod.build_developer_preview_large_model_oom_guard_receipt(
        guard_kind="ligand-scaleup",
        source_json=source,
        root=tmp_path,
    )
    summary = payload["summary"]

    assert summary["status"] == "developer_preview_large_model_oom_guard_ready"
    assert summary["crash_oom_free"] is True
    assert summary["crash_count"] == 0
    assert summary["oom_count"] == 0
    assert summary["blocker_count"] == 0
    assert summary["source_claim_safe"] is False
    assert summary["regression_guardrail_passed"] is False
    assert summary["claim_promotion_allowed"] is False
    assert summary["performance_regression_claim_allowed"] is False
    assert summary["execution_enabled"] is False
    assert summary["external_state_mutated"] is False


def test_rocm_large_model_guard_ready(tmp_path: Path) -> None:
    source = tmp_path / "runs/product_end_to_end_rocm_benchmark_current.json"
    _write_json(source, _rocm_source())

    payload = mod.build_developer_preview_large_model_oom_guard_receipt(
        guard_kind="rocm",
        source_json=source,
        root=tmp_path,
    )
    summary = payload["summary"]

    assert summary["status"] == "developer_preview_rocm_large_model_guard_ready"
    assert summary["source_summary_ready"] is True
    assert summary["crash_oom_free"] is True
    assert summary["crash_count"] == 0
    assert summary["oom_count"] == 0
    assert summary["failure_signal_count"] == 0
    assert summary["blocker_count"] == 0


def test_large_model_guard_blocks_nonzero_oom_counter(tmp_path: Path) -> None:
    source = tmp_path / "runs/product_end_to_end_rocm_benchmark_current.json"
    _write_json(source, _rocm_source(oom_count=1))

    payload = mod.build_developer_preview_large_model_oom_guard_receipt(
        guard_kind="rocm",
        source_json=source,
        root=tmp_path,
    )
    summary = payload["summary"]
    blockers = ";".join(summary["blockers"])

    assert summary["status"] == "blocked_developer_preview_rocm_large_model_guard"
    assert summary["crash_oom_free"] is False
    assert summary["oom_count"] == 1
    assert "oom_count_nonzero=1" in blockers


def test_large_model_guard_blocks_rocm_failed_jobs(tmp_path: Path) -> None:
    source = tmp_path / "runs/product_end_to_end_rocm_benchmark_current.json"
    _write_json(source, _rocm_source(failed_jobs=2, failure_rate=0.2))

    payload = mod.build_developer_preview_large_model_oom_guard_receipt(
        guard_kind="rocm",
        source_json=source,
        root=tmp_path,
    )
    summary = payload["summary"]
    blockers = ";".join(summary["blockers"])

    assert summary["status"] == "blocked_developer_preview_rocm_large_model_guard"
    assert summary["source_summary_ready"] is False
    assert summary["failure_signal_count"] == 2
    assert "failed_jobs_nonzero" in blockers
    assert "failure_rate_nonzero" in blockers


def test_large_model_guard_cli_writes_outputs(tmp_path: Path) -> None:
    source = tmp_path / "runs/ligand_scaleup_benchmark_summary_current.json"
    out_json = tmp_path / ".betelgeuze/developer_preview_large_model_oom_guard.json"
    out_md = tmp_path / ".betelgeuze/developer_preview_large_model_oom_guard.md"
    _write_json(source, _ligand_source())

    assert mod.main(
        [
            "--guard-kind",
            "ligand-scaleup",
            "--source-json",
            str(source),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ]
    ) == 0

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["packet_type"] == "developer_preview_large_model_oom_guard_receipt"
    assert "Developer Preview Large Model OOM Guard Receipt" in out_md.read_text(encoding="utf-8")
