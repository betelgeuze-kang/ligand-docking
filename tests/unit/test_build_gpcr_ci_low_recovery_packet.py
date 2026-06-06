from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
import csv

from tools.gpcr_replay import build_gpcr_ci_low_recovery_packet as mod

ROOT = Path(__file__).resolve().parents[2]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _summary_payload(stage6: dict) -> dict:
    return {"stages": {"stage6_operational_gate": stage6}}


def test_ci_low_blocker_payload_includes_claim_boundaries_and_triage_context(tmp_path: Path) -> None:
    summary_json = tmp_path / "runs" / "summary.json"
    triage_json = tmp_path / "runs" / "triage.json"
    _write_json(
        summary_json,
        _summary_payload(
            {
                "pass": False,
                "failed_metrics": [{"metric": "ranking_pr_auc_ci_low", "value": 0.128, "threshold": 0.45}],
                "ranking_pr_auc": 0.593,
                "ranking_pr_auc_ci_low": 0.128,
                "ranking_topk_hit_rate": 0.25,
                "ranking_positive_count": 6,
                "ranking_topk_hit_rate_max_possible": 0.3,
                "ranking_unique_auc": 0.996,
                "ranking_score_col_used": "binding_score_composite_v7_residual_active",
            }
        ),
    )
    _write_json(
        triage_json,
        {
            "summary": {
                "claim_safe_status": "regression_guardrail_failed",
                "candidate_count": 3,
                "rejected_candidate_count": 2,
            }
        },
    )
    _write_json(
        tmp_path / "runs" / "summary_stage5_ranking_summary.json",
        {
            "metrics_ci": {
                "pr_auc_unique_key": {
                    "low": 0.128,
                    "high": 1.0,
                    "mean": 0.59,
                    "std": 0.21,
                    "n": 796,
                }
            }
        },
    )
    _write_csv(
        tmp_path / "runs" / "summary_stage5_ranking_rows.csv",
        [
            {
                "target": "ADRB2",
                "ligand_id": "carvedilol",
                "is_binder": "1",
                "reference_binding_kcal_mol": "-9.1",
                "binding_score_composite_v7_residual_active": "-21.6",
                "mean_min_distance_A": "4.31",
            },
            {
                "target": "ADRB2",
                "ligand_id": "timolol",
                "is_binder": "1",
                "reference_binding_kcal_mol": "-8.5",
                "binding_score_composite_v7_residual_active": "-14.7",
                "mean_min_distance_A": "4.32",
            },
            {
                "target": "ADRB2",
                "ligand_id": "decoy_a",
                "is_binder": "0",
                "reference_binding_kcal_mol": "",
                "binding_score_composite_v7_residual_active": "-13.0",
                "mean_min_distance_A": "4.50",
            },
            {
                "target": "ADRB2",
                "ligand_id": "pindolol",
                "is_binder": "1",
                "reference_binding_kcal_mol": "-8.2",
                "binding_score_composite_v7_residual_active": "-7.3",
                "mean_min_distance_A": "4.17",
            },
        ],
    )

    payload = mod.build_packet(summary_json=summary_json, triage_json=triage_json)

    assert payload["summary"]["ci_low_blocker"] is True
    assert payload["summary"]["threshold"] == 0.45
    assert payload["summary"]["ranking_pr_auc_ci_low"] == 0.128
    assert payload["summary"]["ranking_score_col_used"] == "binding_score_composite_v7_residual_active"
    assert payload["recovery_interpretation"] == {
        "claim_safe": False,
        "comparison_only": True,
        "claim_promotion_allowed": False,
    }
    assert payload["input_context"]["claim_safe_status"] == "regression_guardrail_failed"
    assert payload["input_context"]["candidate_count"] == 3
    assert payload["input_context"]["rejected_candidate_count"] == 2
    assert payload["rank_diagnostics"]["positive_rank_list"] == [1, 2, 4]
    assert payload["rank_diagnostics"]["top20_hit_count"] == 3
    assert payload["rank_diagnostics"]["top20_hit_rate_max_possible"] == 0.3
    assert payload["bootstrap_diagnostics"]["source"] == "pr_auc_unique_key"
    assert payload["bootstrap_diagnostics"]["valid_bootstrap_n"] == 796
    assert payload["bootstrap_diagnostics"]["std"] == 0.21
    requirement = payload["claim_coverage_requirement"]
    assert requirement["ci_low_policy"]["status"] == "blocked"
    assert requirement["ci_low_policy"]["claim_promotion_allowed"] is False
    assert requirement["ci_low_policy"]["threshold_relaxation_allowed"] is False
    assert requirement["observed_positive_count"] == 6
    assert requirement["minimum_positive_count_for_claim"] == 9
    assert requirement["positive_coverage_gap"] == 3
    assert requirement["top20_ceiling_observed"] == 0.3
    assert requirement["top20_ceiling_threshold"] == 0.45
    assert requirement["top20_ceiling_gap_to_threshold"] == 0.15
    assert requirement["required_next_evidence"] == [
        "add at least 3 non-leaky GPCR positive examples before re-claiming",
        "rebuild the blind ranking packet with top20 ceiling >= 0.45",
        "demonstrate ranking_pr_auc_ci_low >= 0.45 under the unchanged operational gate",
        "keep claim_promotion_allowed=false until both positive coverage and CI-low gates clear",
    ]
    actions = " ".join(payload["recommended_next_actions"])
    assert "non-leaky positive coverage expansion" in actions
    assert "family-held-out scorecard" in actions
    assert "bootstrap stability validation" in actions
    assert "no threshold relaxation/fake pass" in actions


def test_pass_payload_uses_threshold_fallback_and_missing_triage_fallback(tmp_path: Path) -> None:
    summary_json = tmp_path / "runs" / "summary.json"
    _write_json(
        summary_json,
        _summary_payload(
            {
                "pass": True,
                "failed_metrics": [],
                "ranking_pr_auc": 0.88,
                "ranking_pr_auc_ci_low": 0.51,
                "ranking_topk_hit_rate": 0.3,
                "ranking_positive_count": 6,
                "ranking_topk_hit_rate_max_possible": 0.3,
                "ranking_unique_auc": 0.99,
                "ranking_score_col_used": "binding_score_composite_v7",
            }
        ),
    )

    payload = mod.build_packet(summary_json=summary_json, triage_json=None)

    assert payload["summary"]["ci_low_blocker"] is False
    assert payload["summary"]["threshold"] == 0.45
    assert payload["input_context"]["triage_json_available"] is False
    assert payload["input_context"]["claim_safe_status"] is None
    assert payload["recovery_interpretation"]["claim_safe"] is False
    assert payload["recovery_interpretation"]["comparison_only"] is True
    assert payload["recovery_interpretation"]["claim_promotion_allowed"] is False
    requirement = payload["claim_coverage_requirement"]
    assert requirement["ci_low_policy"]["status"] == "meets_threshold"
    assert requirement["minimum_positive_count_for_claim"] == 9
    assert requirement["positive_coverage_gap"] == 3
    assert requirement["top20_ceiling_gap_to_threshold"] == 0.15


def test_cli_writes_operator_json_and_markdown(tmp_path: Path) -> None:
    summary_json = tmp_path / "runs" / "summary.json"
    out_json = tmp_path / "runs" / "packet.json"
    out_md = tmp_path / "runs" / "packet.md"
    _write_json(
        summary_json,
        _summary_payload(
            {
                "pass": False,
                "failed_metrics": [{"metric": "ranking_pr_auc_ci_low", "value": 0.2, "threshold": 0.45}],
                "ranking_pr_auc": 0.59,
                "ranking_pr_auc_ci_low": 0.2,
                "ranking_topk_hit_rate": 0.25,
                "ranking_positive_count": 6,
                "ranking_topk_hit_rate_max_possible": 0.3,
                "ranking_unique_auc": 0.996,
                "ranking_score_col_used": "binding_score_composite_v7_residual_active",
            }
        ),
    )
    _write_json(
        tmp_path / "runs" / "summary_stage5_ranking_summary.json",
        {"metrics_ci": {"pr_auc_unique_key": {"low": 0.2, "high": 1.0, "mean": 0.6, "std": 0.2, "n": 796}}},
    )
    _write_csv(
        tmp_path / "runs" / "summary_stage5_ranking_rows.csv",
        [
            {
                "target": "ADRB2",
                "ligand_id": "pindolol",
                "is_binder": "1",
                "reference_binding_kcal_mol": "-8.2",
                "binding_score_composite_v7_residual_active": "-7.3",
                "mean_min_distance_A": "4.17",
            }
        ],
    )

    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/gpcr_replay/build_gpcr_ci_low_recovery_packet.py"),
            "--summary-json",
            str(summary_json),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ],
        check=True,
        cwd=ROOT,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    md = out_md.read_text(encoding="utf-8")
    assert payload["summary"]["ci_low_blocker"] is True
    assert "GPCR CI-low Recovery Packet" in md
    assert "| ranking_pr_auc_ci_low | 0.2 | 0.45 | blocker |" in md
    assert "Claim Boundary" in md
    assert "claim_safe=false" in md
    assert "Claim Coverage Requirement" in md
    assert "minimum_positive_count_for_claim=9" in md
    assert "positive_coverage_gap=3" in md
    assert "top20_ceiling_gap_to_threshold=0.15" in md
    assert "threshold_relaxation_allowed=false" in md
    assert "positive_ranks=[1]" in md
    assert "bootstrap_valid_n=796" in md
