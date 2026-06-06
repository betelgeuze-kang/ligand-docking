from __future__ import annotations

import json
from pathlib import Path

from tools.product import build_gpcr_residual_assist_candidate_selection as mod


def _mode_packet() -> dict[str, object]:
    return {
        "rows": [
            {
                "task_id": "gpcr_core_full",
                "baseline_pass": True,
                "shadow_pass": True,
                "apply_pass": True,
                "shadow_complete": True,
                "apply_complete": True,
                "delta_pr_auc_shadow_vs_baseline": 0.0,
                "delta_pr_auc_apply_vs_baseline": -0.05,
                "delta_ef1_shadow_vs_baseline": 0.0,
                "delta_ef1_apply_vs_baseline": 0.0,
                "shadow_residual_mean_delta": 0.0002,
                "apply_residual_mean_delta": 0.0002,
            },
            {
                "task_id": "gpcr_chembl50_full",
                "baseline_pass": True,
                "shadow_pass": True,
                "apply_pass": True,
                "shadow_complete": True,
                "apply_complete": True,
                "delta_pr_auc_shadow_vs_baseline": 0.0002,
                "delta_pr_auc_apply_vs_baseline": 0.0016,
                "delta_ef1_shadow_vs_baseline": 1.7,
                "delta_ef1_apply_vs_baseline": 1.7,
                "shadow_residual_mean_delta": 0.0003,
                "apply_residual_mean_delta": 0.00025,
            },
        ]
    }


def test_gpcr_residual_assist_candidate_selection_ready() -> None:
    payload = mod.build_gpcr_residual_assist_candidate_selection(mode_comparison_packet=_mode_packet())

    summary = payload["summary"]
    assert summary["status"] == "gpcr_residual_assist_candidate_selection_ready"
    assert summary["assist_candidate_ready"] is True
    assert summary["pr_auc_regression_warning_count"] == 0
    assert summary["residual_applied_task_count"] == 1
    rows = {row["task_id"]: row for row in payload["rows"]}
    assert rows["gpcr_core_full"]["selected_mode"] == "shadow"
    assert rows["gpcr_chembl50_full"]["selected_mode"] == "apply"


def test_gpcr_residual_assist_candidate_selection_blocks_without_clean_residual_gain() -> None:
    packet = _mode_packet()
    packet["rows"][1]["delta_pr_auc_shadow_vs_baseline"] = -0.1  # type: ignore[index]
    packet["rows"][1]["delta_pr_auc_apply_vs_baseline"] = -0.1  # type: ignore[index]

    payload = mod.build_gpcr_residual_assist_candidate_selection(mode_comparison_packet=packet)

    summary = payload["summary"]
    assert summary["status"] == "blocked_gpcr_residual_assist_candidate_selection"
    assert summary["assist_candidate_ready"] is False
    assert summary["residual_applied_task_count"] == 0


def test_gpcr_residual_assist_candidate_selection_cli_writes_outputs(tmp_path: Path) -> None:
    mode_json = tmp_path / "mode.json"
    out_json = tmp_path / "selection.json"
    out_csv = tmp_path / "selection.csv"
    out_md = tmp_path / "selection.md"
    mode_json.write_text(json.dumps(_mode_packet()) + "\n", encoding="utf-8")

    mod.main(
        [
            "--mode-comparison-json",
            str(mode_json),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["assist_candidate_ready"] is True
    assert "task_id" in out_csv.read_text(encoding="utf-8")
    assert "GPCR Residual Assist Candidate Selection" in out_md.read_text(encoding="utf-8")
