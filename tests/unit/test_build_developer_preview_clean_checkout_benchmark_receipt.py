from __future__ import annotations

import json
from pathlib import Path

from tools.product import build_developer_preview_clean_checkout_benchmark_receipt as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_ready_sources(root: Path) -> tuple[Path, Path]:
    ai_verify_log = root / ".betelgeuze/developer_preview_clean_checkout_ai_verify.log"
    ai_verify_log.parent.mkdir(parents=True, exist_ok=True)
    ai_verify_log.write_text("==> python syntax smoke\nverify ok (smoke)\n", encoding="utf-8")

    bundle_root = root / ".betelgeuze/developer_preview_external_baselines" / (
        "biorxiv_baseline_comparison_developer_preview_clean_checkout"
    )
    ranking_summary = bundle_root / "tasks/set1__gpcr/current_summary.json"
    _write_json(ranking_summary, {"metrics_unique": {"pr_auc": 1.0}})
    (bundle_root / "score_leaderboard.csv").parent.mkdir(parents=True, exist_ok=True)
    (bundle_root / "score_leaderboard.csv").write_text(
        "score_alias,score_col,task_count,wins_pr_auc\n"
        "composite_v7,binding_score_composite_v7,1,1\n",
        encoding="utf-8",
    )
    baseline_summary = bundle_root / "summary.json"
    _write_json(
        baseline_summary,
        {
            "bundle_root": str(bundle_root),
            "task_count": 1,
            "task_winner_count_current": 1,
            "task_winner_count_noncurrent": 0,
            "score_leaderboard": [
                {
                    "score_alias": "composite_v7",
                    "score_col": "binding_score_composite_v7",
                    "task_count": 1,
                    "wins_pr_auc": 1,
                }
            ],
            "tasks": [
                {
                    "set_id": "set1",
                    "task_id": "gpcr",
                    "current_score_col": "binding_score_composite_v7",
                    "score_rows": [
                        {
                            "score_col": "binding_score_composite_v7",
                            "ranking_summary_json": str(ranking_summary),
                        }
                    ],
                }
            ],
        },
    )
    return ai_verify_log, baseline_summary


def test_clean_checkout_benchmark_receipt_ready_after_review(tmp_path: Path) -> None:
    ai_verify_log, baseline_summary = _write_ready_sources(tmp_path)

    payload = mod.build_developer_preview_clean_checkout_benchmark_receipt(
        ai_verify_log=ai_verify_log,
        baseline_summary_json=baseline_summary,
        reviewed_receipt_attached=True,
        reviewer_id="operator-a",
        reviewed_at_utc="2026-07-03T00:00:00Z",
        root=tmp_path,
    )
    summary = payload["summary"]

    assert summary["status"] == "developer_preview_clean_checkout_benchmark_receipt_ready"
    assert summary["clean_checkout_benchmark_regenerated"] is True
    assert summary["ai_verify_passed"] is True
    assert summary["reviewed_receipt_attached"] is True
    assert summary["blocker_count"] == 0
    assert summary["failed_count"] == 0
    assert summary["baseline_task_count"] == 1
    assert summary["claim_promotion_allowed"] is False
    assert summary["execution_enabled"] is False
    assert summary["external_state_mutated"] is False


def test_clean_checkout_benchmark_receipt_blocks_missing_sources(tmp_path: Path) -> None:
    payload = mod.build_developer_preview_clean_checkout_benchmark_receipt(root=tmp_path)
    summary = payload["summary"]
    blockers = ";".join(summary["blockers"])

    assert summary["status"] == "blocked_developer_preview_clean_checkout_benchmark_receipt"
    assert summary["clean_checkout_benchmark_regenerated"] is False
    assert summary["ai_verify_passed"] is False
    assert summary["reviewed_receipt_attached"] is False
    assert summary["failed_count"] > 0
    assert "developer_preview_clean_checkout_ai_verify.log:missing" in blockers
    assert "summary.json:missing_or_invalid" in blockers
    assert "reviewed_receipt_attached_not_true" in blockers
    assert "reviewer_id_missing" in blockers
    assert "reviewed_at_utc_missing" in blockers


def test_clean_checkout_benchmark_receipt_cli_writes_outputs(tmp_path: Path) -> None:
    ai_verify_log, baseline_summary = _write_ready_sources(tmp_path)
    out_json = tmp_path / ".betelgeuze/developer_preview_clean_checkout_benchmark_receipt.json"
    out_md = tmp_path / ".betelgeuze/developer_preview_clean_checkout_benchmark_receipt.md"

    assert mod.main(
        [
            "--ai-verify-log",
            str(ai_verify_log),
            "--baseline-summary-json",
            str(baseline_summary),
            "--reviewed-receipt-attached",
            "--reviewer-id",
            "operator-a",
            "--reviewed-at-utc",
            "2026-07-03T00:00:00Z",
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ]
    ) == 0

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["packet_type"] == "developer_preview_clean_checkout_benchmark_receipt"
    assert "Developer Preview Clean-Checkout Benchmark Receipt" in out_md.read_text(
        encoding="utf-8"
    )
