from __future__ import annotations

import json
from pathlib import Path

from tools.product import build_gpcr_hard_decoy_residual_proof as mod


def _mode_packet(*, apply_pass: bool = True, apply_mean_delta: float = 0.0001) -> dict[str, object]:
    return {
        "rows": [
            {
                "task_id": "gpcr_core_full",
                "baseline_pass": True,
                "shadow_pass": True,
                "apply_pass": apply_pass,
                "delta_ef1_shadow_vs_baseline": 0.0,
                "delta_ef1_apply_vs_baseline": 0.0,
                "delta_pr_auc_shadow_vs_baseline": 0.0,
                "delta_pr_auc_apply_vs_baseline": 0.0,
                "shadow_residual_mean_delta": 0.0,
                "apply_residual_mean_delta": apply_mean_delta,
            },
            {
                "task_id": "gpcr_chembl50_full",
                "baseline_pass": True,
                "shadow_pass": True,
                "apply_pass": True,
                "delta_ef1_shadow_vs_baseline": 0.0,
                "delta_ef1_apply_vs_baseline": 1.7,
                "delta_pr_auc_shadow_vs_baseline": 0.0005,
                "delta_pr_auc_apply_vs_baseline": -0.0001,
                "shadow_residual_mean_delta": 0.00007,
                "apply_residual_mean_delta": 0.000035,
            },
        ]
    }


def _failure_packet() -> dict[str, object]:
    return {
        "summary": {
            "status": "computed",
            "source_rows_available": True,
            "baseline_top20_binder_count": 3,
            "scaleup_top20_binder_count": 3,
            "first_positive_rank_shift": 0,
        }
    }


def test_build_gpcr_hard_decoy_residual_proof_ready() -> None:
    payload = mod.build_gpcr_hard_decoy_residual_proof(
        mode_comparison_packet=_mode_packet(),
        progression_packet={"summary": {"core_v4_apply_preserves_baseline": True, "chembl50_v4_apply_has_ef1_gain": True}},
        decision_packet={"pass_regressions": 0},
        failure_analysis_packet=_failure_packet(),
    )

    summary = payload["summary"]
    assert summary["status"] == "gpcr_hard_decoy_residual_proof_ready"
    assert summary["proof_ready"] is True
    assert summary["intrusion_reduction_task_count"] == 1
    assert summary["pass_to_fail_regression_count"] == 0
    assert summary["correction_norm_fail_count"] == 0
    assert summary["binder_retention_fail_count"] == 0
    assert summary["pr_auc_regression_warning_count"] == 1
    assert summary["assist_promotion_allowed"] is False
    assert summary["production_promotion_allowed"] is False
    assert summary["external_state_mutated"] is False


def test_build_gpcr_hard_decoy_residual_proof_blocks_pass_to_fail() -> None:
    payload = mod.build_gpcr_hard_decoy_residual_proof(
        mode_comparison_packet=_mode_packet(apply_pass=False),
        decision_packet={"pass_regressions": 1},
        failure_analysis_packet=_failure_packet(),
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_gpcr_hard_decoy_residual_proof"
    assert summary["proof_ready"] is False
    assert summary["pass_to_fail_regression_count"] == 1


def test_build_gpcr_hard_decoy_residual_proof_blocks_correction_norm_cap() -> None:
    payload = mod.build_gpcr_hard_decoy_residual_proof(
        mode_comparison_packet=_mode_packet(apply_mean_delta=0.25),
        decision_packet={"pass_regressions": 0},
        failure_analysis_packet=_failure_packet(),
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_gpcr_hard_decoy_residual_proof"
    assert summary["proof_ready"] is False
    assert summary["correction_norm_fail_count"] == 1


def test_gpcr_hard_decoy_residual_proof_cli_writes_outputs(tmp_path: Path) -> None:
    mode = tmp_path / "mode.json"
    progress = tmp_path / "progress.json"
    decision = tmp_path / "decision.json"
    failure = tmp_path / "failure.json"
    out_json = tmp_path / "proof.json"
    out_csv = tmp_path / "proof.csv"
    out_md = tmp_path / "proof.md"
    mode.write_text(json.dumps(_mode_packet()) + "\n", encoding="utf-8")
    progress.write_text(json.dumps({"summary": {"core_v4_apply_preserves_baseline": True}}) + "\n", encoding="utf-8")
    decision.write_text(json.dumps({"pass_regressions": 0}) + "\n", encoding="utf-8")
    failure.write_text(json.dumps(_failure_packet()) + "\n", encoding="utf-8")

    mod.main(
        [
            "--mode-comparison-json",
            str(mode),
            "--progression-json",
            str(progress),
            "--decision-json",
            str(decision),
            "--failure-analysis-json",
            str(failure),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["proof_ready"] is True
    assert "task_id" in out_csv.read_text(encoding="utf-8")
    assert "GPCR Hard-Decoy Residual Proof" in out_md.read_text(encoding="utf-8")
