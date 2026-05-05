from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def test_build_gpcr_cationic_pose_distortion_shadow_replay_review_green_claim_locked(tmp_path: Path) -> None:
    scores_csv = tmp_path / "scores.csv"
    summary_json = tmp_path / "summary.json"
    out_json = tmp_path / "review.json"
    out_md = tmp_path / "review.md"
    _write_csv(
        scores_csv,
        [
            {
                "ligand_id": "CHEMBL301265",
                "is_binder": 1,
                "binding_score_composite_v7_residual_shadow": -10.0,
            },
            {
                "ligand_id": "decoy_1",
                "is_binder": 0,
                "binding_score_composite_v7_residual_shadow": -1.0,
            },
        ],
    )
    summary_json.write_text(
        json.dumps({"summary": {"status": "ready_for_evaluation", "active_score_locked_to_base": True}}),
        encoding="utf-8",
    )

    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_gpcr_cationic_pose_distortion_shadow_replay_review.py"),
            "--input-scores-csv",
            str(scores_csv),
            "--input-summary-json",
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
    summary = payload["summary"]

    assert summary["status"] == "selected_slice_shadow_green_claim_locked"
    assert summary["selected_slice_positive_rank"] == 1
    assert summary["selected_slice_decoys_above_positive_count"] == 0
    assert summary["claim_promotion_allowed"] is False
    assert summary["scorer_apply_allowed"] is False
    assert payload["claim_boundary"]["selected_slice_green_is_not_claim_evidence"] is True
    assert "selected-slice green is not enough" in out_md.read_text(encoding="utf-8")


def test_build_gpcr_cationic_pose_distortion_shadow_replay_review_blocks_when_active_unlocked(
    tmp_path: Path,
) -> None:
    scores_csv = tmp_path / "scores.csv"
    summary_json = tmp_path / "summary.json"
    out_json = tmp_path / "review.json"
    out_md = tmp_path / "review.md"
    _write_csv(
        scores_csv,
        [
            {
                "ligand_id": "decoy_1",
                "is_binder": 0,
                "binding_score_composite_v7_residual_shadow": -10.0,
            },
            {
                "ligand_id": "CHEMBL301265",
                "is_binder": 1,
                "binding_score_composite_v7_residual_shadow": -1.0,
            },
        ],
    )
    summary_json.write_text(
        json.dumps({"summary": {"status": "ready_for_evaluation", "active_score_locked_to_base": False}}),
        encoding="utf-8",
    )

    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_gpcr_cationic_pose_distortion_shadow_replay_review.py"),
            "--input-scores-csv",
            str(scores_csv),
            "--input-summary-json",
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
    summary = payload["summary"]

    assert summary["status"] == "blocked_internal_review"
    assert "active_score_not_locked_to_base" in summary["blockers"]
    assert "selected_slice_positive_not_top_ranked" in summary["blockers"]
