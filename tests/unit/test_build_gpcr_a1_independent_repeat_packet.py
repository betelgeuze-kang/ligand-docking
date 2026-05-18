from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools import build_gpcr_a1_independent_repeat_packet as mod

ROOT = Path(__file__).resolve().parents[2]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def test_build_packet_ready_when_a1_cleared_and_metrics_green(tmp_path: Path) -> None:
    a1 = tmp_path / "a1.json"
    scorecard = tmp_path / "scorecard.json"
    ranking = tmp_path / "ranking.json"
    set_spec = tmp_path / "set_spec.json"
    _write_json(
        a1,
        {
            "summary": {
                "status": "a1_accuracy_repair_queue_cleared_claim_locked",
                "full_guarded_100k_review_passed": True,
                "open_queue_row_count": 0,
            }
        },
    )
    _write_json(scorecard, {"summary": {"status": "blocked_accuracy_parity", "blocked_row_count": 4}})
    _write_json(
        ranking,
        {
            "metrics": {
                "pr_auc": 0.879215438805593,
                "positive_count": 13,
                "probability_score_col_used": "binding_score_composite_v7_residual_active",
            },
            "metrics_ci_unique": {"pr_auc": {"low": 0.6758817928374873}},
            "topk_unique": [{"k": 20, "hit_rate": 0.6}],
        },
    )
    _write_json(set_spec, {"sets": []})

    payload = mod.build_packet(
        a1_queue_json=a1,
        accuracy_scorecard_json=scorecard,
        ranking_json=ranking,
        set_spec_json=set_spec,
        repeat_tag="repeat_r2",
        generated_at_local="2026-05-13T00:00:00+09:00",
    )

    summary = payload["summary"]
    assert summary["status"] == "independent_repeat_ready_claim_locked"
    assert summary["independent_repeat_ready"] is True
    assert summary["claim_promotion_allowed"] is False
    assert summary["blockers"] == []
    assert summary["ranking_pr_auc_ci_low"] == 0.6758817928374873
    assert "--validate-only" in summary["validate_command"]
    assert "--tag repeat_r2" in summary["run_command"]
    assert payload["claim_boundary"]["threshold_relaxation_allowed"] is False


def test_build_packet_marks_completed_repeat_metric_blocked(tmp_path: Path) -> None:
    a1 = tmp_path / "a1.json"
    scorecard = tmp_path / "scorecard.json"
    ranking = (
        tmp_path
        / "external_validation_2026-05-13_gpcr_a1_independent_repeat_r2_set1_core_blind_gpcr_core_full_p0_n100000_r1_stage5_ranking_summary.json"
    )
    set_spec = tmp_path / "set_spec.json"
    _write_json(
        a1,
        {
            "summary": {
                "status": "a1_accuracy_repair_queue_cleared_claim_locked",
                "full_guarded_100k_review_passed": True,
                "open_queue_row_count": 0,
            }
        },
    )
    _write_json(scorecard, {"summary": {"status": "blocked_accuracy_parity", "blocked_row_count": 3}})
    _write_json(
        ranking,
        {
            "metrics": {"pr_auc": 0.1575, "positive_count": 13},
            "metrics_ci_unique": {"pr_auc": {"low": 0.0013}},
            "topk_unique": [{"k": 20, "hit_rate": 0.1}],
        },
    )
    _write_json(set_spec, {"sets": []})

    payload = mod.build_packet(
        a1_queue_json=a1,
        accuracy_scorecard_json=scorecard,
        ranking_json=ranking,
        set_spec_json=set_spec,
        repeat_tag="2026-05-13_gpcr_a1_independent_repeat_r2",
        generated_at_local="2026-05-13T00:00:00+09:00",
    )

    summary = payload["summary"]
    assert summary["status"] == "independent_repeat_completed_metric_blocked"
    assert summary["independent_repeat_completed"] is True
    assert summary["independent_repeat_ready"] is False
    assert summary["independent_repeat_result_passed"] is False
    assert "ranking_pr_auc_below_threshold" in summary["blockers"]
    assert "ranking_top20_hit_rate_below_threshold" in summary["blockers"]


def test_build_packet_blocks_when_a1_not_cleared(tmp_path: Path) -> None:
    a1 = tmp_path / "a1.json"
    scorecard = tmp_path / "scorecard.json"
    ranking = tmp_path / "ranking.json"
    set_spec = tmp_path / "set_spec.json"
    _write_json(a1, {"summary": {"status": "open_a1_repair_queue", "open_queue_row_count": 1}})
    _write_json(scorecard, {"summary": {"status": "blocked_accuracy_parity"}})
    _write_json(ranking, {"metrics": {"pr_auc": 0.1}, "metrics_ci_unique": {"pr_auc": {"low": 0.01}}})
    _write_json(set_spec, {"sets": []})

    payload = mod.build_packet(
        a1_queue_json=a1,
        accuracy_scorecard_json=scorecard,
        ranking_json=ranking,
        set_spec_json=set_spec,
        generated_at_local="2026-05-13T00:00:00+09:00",
    )

    summary = payload["summary"]
    assert summary["status"] == "independent_repeat_blocked"
    assert summary["independent_repeat_ready"] is False
    assert "a1_queue_not_cleared_claim_locked" in summary["blockers"]
    assert "ranking_pr_auc_ci_low_below_threshold" in summary["blockers"]


def test_cli_writes_outputs(tmp_path: Path) -> None:
    good = tmp_path / "good.json"
    set_spec = tmp_path / "set_spec.json"
    out_json = tmp_path / "repeat.json"
    out_md = tmp_path / "repeat.md"
    _write_json(
        good,
        {
            "summary": {
                "status": "a1_accuracy_repair_queue_cleared_claim_locked",
                "full_guarded_100k_review_passed": True,
                "open_queue_row_count": 0,
                "blocked_row_count": 4,
            },
            "metrics": {"pr_auc": 0.9, "positive_count": 13},
            "metrics_ci_unique": {"pr_auc": {"low": 0.7}},
            "topk_unique": [{"k": 20, "hit_rate": 0.6}],
        },
    )
    _write_json(set_spec, {"sets": []})

    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_gpcr_a1_independent_repeat_packet.py"),
            "--a1-queue-json",
            str(good),
            "--accuracy-scorecard-json",
            str(good),
            "--ranking-json",
            str(good),
            "--set-spec-json",
            str(set_spec),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ],
        cwd=ROOT,
        check=True,
    )
    assert json.loads(out_json.read_text(encoding="utf-8"))["packet_type"] == "gpcr_a1_independent_repeat_packet"
    assert "GPCR A1 Independent Repeat Packet" in out_md.read_text(encoding="utf-8")
