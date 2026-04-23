from __future__ import annotations

import json
from pathlib import Path

from tools import build_gpcr_residual_chembl50_v3_decision as mod


def test_build_gpcr_residual_chembl50_v3_decision(tmp_path: Path) -> None:
    vs_baseline = tmp_path / "vs_baseline.json"
    vs_narrow = tmp_path / "vs_narrow.json"
    vs_baseline.write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "task_id": "gpcr_core_full",
                        "baseline_pass": True,
                        "candidate_pass": True,
                        "delta_pr_auc": 0.0,
                        "delta_ef1": 0.0,
                        "residual_positive_delta_count": 4,
                        "residual_mean_delta": 0.0002,
                    },
                    {
                        "task_id": "gpcr_chembl50_full",
                        "baseline_pass": True,
                        "candidate_pass": True,
                        "delta_pr_auc": 0.0002,
                        "delta_ef1": 1.7,
                        "residual_positive_delta_count": 6,
                        "residual_mean_delta": 0.0003,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    vs_narrow.write_text(
        json.dumps(
            {
                "rows": [
                    {"task_id": "gpcr_core_full", "delta_pr_auc": 0.05, "delta_ef1": 0.0},
                    {"task_id": "gpcr_chembl50_full", "delta_pr_auc": -0.00005, "delta_ef1": 0.0},
                ]
            }
        ),
        encoding="utf-8",
    )
    payload = mod.build_payload(vs_baseline_json=vs_baseline, vs_narrow_v2_json=vs_narrow)
    assert payload["decision"] == "go_for_locked_decoy_apply_trial"
    assert payload["pass_regressions"] == 0
    assert payload["pr_regressions_vs_baseline"] == 0
    assert payload["improved_vs_narrow_v2_count"] == 1
    assert payload["variant_label"] == "chembl50_v3"


def test_build_gpcr_residual_chembl50_variant_decision_label(tmp_path: Path) -> None:
    vs_baseline = tmp_path / "vs_baseline.json"
    vs_narrow = tmp_path / "vs_narrow.json"
    vs_baseline.write_text(json.dumps({"rows": []}), encoding="utf-8")
    vs_narrow.write_text(json.dumps({"rows": []}), encoding="utf-8")
    payload = mod.build_payload(
        vs_baseline_json=vs_baseline,
        vs_narrow_v2_json=vs_narrow,
        variant_label="chembl50_v4",
    )
    assert payload["variant_label"] == "chembl50_v4"
