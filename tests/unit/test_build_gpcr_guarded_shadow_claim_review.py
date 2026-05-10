from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

from tools import build_gpcr_guarded_shadow_claim_review as mod

ROOT = Path(__file__).resolve().parents[2]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_scores(path: Path, score_col: str = "score") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        ("CHEMBL217_DRD2_HUMAN", "CHEMBL301265", 1.0),
        ("CHEMBL224_HTR2A_HUMAN", "CHEMBL83894", 2.0),
        ("CHEMBL233_OPRM1_HUMAN", "CHEMBL331883", 3.0),
        ("CHEMBL217_DRD2_HUMAN", "decoy_drd2_1", 4.0),
        ("CHEMBL224_HTR2A_HUMAN", "decoy_htr2a_1", 5.0),
        ("CHEMBL233_OPRM1_HUMAN", "decoy_oprm1_1", 6.0),
    ]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["target", "ligand_id", score_col])
        writer.writeheader()
        for target, ligand_id, score in rows:
            writer.writerow({"target": target, "ligand_id": ligand_id, score_col: score})


def test_build_review_marks_green_diagnostic_when_shadow_metrics_clear(tmp_path: Path) -> None:
    scores = tmp_path / "scores.csv"
    pose_gap = tmp_path / "pose_gap.json"
    queue = tmp_path / "queue.json"
    _write_scores(scores)
    _write_json(
        pose_gap,
        {
            "target_summaries": [
                {"target": "CHEMBL224_HTR2A_HUMAN", "ligand_id": "CHEMBL83894"},
                {"target": "CHEMBL233_OPRM1_HUMAN", "ligand_id": "CHEMBL331883"},
            ]
        },
    )
    _write_json(queue, {"summary": {"guarded_100k_rerun_allowed_now": True}})

    payload, rows = mod.build_review(
        scores_csv=scores,
        score_col="score",
        pose_gap_json=pose_gap,
        a1_queue_json=queue,
        bootstrap_n=0,
        generated_at_local="2026-05-09T00:00:00+09:00",
    )

    summary = payload["summary"]
    assert summary["status"] == "guarded_shadow_claim_review_green_diagnostic_only"
    assert summary["input_rows"] == 6
    assert summary["positive_count"] == 3
    assert summary["ranking_pr_auc"] == 1.0
    assert summary["ranking_pr_auc_ci_low"] == 1.0
    assert summary["top20_positive_count"] == 3
    assert summary["top20_positive_recall"] == 1.0
    assert summary["all_positive_target_rank_1"] is True
    assert summary["claim_promotion_allowed"] is False
    assert payload["claim_boundary"]["full_100k_claim_review_required"] is True
    assert [row["target_rank"] for row in payload["positive_summaries"]] == [1, 1, 1]
    assert rows[0]["row_kind"] == "topk_positive"
    assert rows[-1]["row_kind"] == "topk_decoy"


def test_build_review_blocks_when_ci_low_gate_fails(tmp_path: Path) -> None:
    scores = tmp_path / "scores.csv"
    pose_gap = tmp_path / "pose_gap.json"
    queue = tmp_path / "queue.json"
    _write_scores(scores)
    _write_json(pose_gap, {"target_summaries": []})
    _write_json(queue, {"summary": {"guarded_100k_rerun_allowed_now": True}})

    payload, _ = mod.build_review(
        scores_csv=scores,
        score_col="score",
        pose_gap_json=pose_gap,
        a1_queue_json=queue,
        bootstrap_n=0,
        pr_auc_ci_low_min=1.01,
        generated_at_local="2026-05-09T00:00:00+09:00",
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_guarded_shadow_claim_review_ci_low"
    assert summary["blockers"] == ["ranking_pr_auc_ci_low_below_threshold"]
    assert summary["guarded_shadow_claim_review_passed"] is False
    assert "does not certify PR-AUC CI-low stability" in summary["next_required_step"]


def test_cli_writes_review_artifacts(tmp_path: Path) -> None:
    scores = tmp_path / "scores.csv"
    pose_gap = tmp_path / "pose_gap.json"
    queue = tmp_path / "queue.json"
    out_json = tmp_path / "review.json"
    out_md = tmp_path / "review.md"
    out_rows = tmp_path / "review_rows.csv"
    _write_scores(scores)
    _write_json(pose_gap, {"target_summaries": []})
    _write_json(queue, {"summary": {"guarded_100k_rerun_allowed_now": True}})

    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_gpcr_guarded_shadow_claim_review.py"),
            "--scores-csv",
            str(scores),
            "--score-col",
            "score",
            "--pose-gap-json",
            str(pose_gap),
            "--a1-queue-json",
            str(queue),
            "--bootstrap-n",
            "0",
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
            "--out-rows-csv",
            str(out_rows),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    rendered_md = out_md.read_text(encoding="utf-8")
    rendered_rows = out_rows.read_text(encoding="utf-8")
    assert payload["packet_type"] == "gpcr_guarded_shadow_claim_review"
    assert "GPCR Guarded Shadow Claim Review" in rendered_md
    assert "topk_positive" in rendered_rows
