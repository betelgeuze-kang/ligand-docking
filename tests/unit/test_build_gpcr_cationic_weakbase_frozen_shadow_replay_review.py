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


def test_build_gpcr_cationic_weakbase_frozen_shadow_replay_review_blocks_partial_decoy_intrusion(
    tmp_path: Path,
) -> None:
    scores = tmp_path / "scores.csv"
    labels = tmp_path / "labels.csv"
    summary = tmp_path / "summary.json"
    out_json = tmp_path / "review.json"
    out_md = tmp_path / "review.md"
    _write_csv(
        scores,
        [
            {
                "target": "T1",
                "ligand_id": "D1",
                "base_score": -1.0,
                "binding_score_composite_v7_residual_shadow": -5.0,
                "basic_amine_count": 1,
                "label_free_support_pressure": 1.0,
                "weak_base_rescue_support_pressure": 1.0,
            },
            {
                "target": "T1",
                "ligand_id": "P1",
                "base_score": 0.0,
                "binding_score_composite_v7_residual_shadow": -2.0,
                "basic_amine_count": 2,
                "label_free_support_pressure": 0.5,
                "weak_base_rescue_support_pressure": 0.5,
            },
        ],
    )
    _write_csv(
        labels,
        [
            {"target": "T1", "ligand_id": "D1", "is_binder": "false"},
            {"target": "T1", "ligand_id": "P1", "is_binder": "true"},
        ],
    )
    summary.write_text(
        json.dumps({"summary": {"status": "ready_for_evaluation", "active_score_locked_to_base": True}}),
        encoding="utf-8",
    )

    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/gpcr_replay/build_gpcr_cationic_weakbase_frozen_shadow_replay_review.py"),
            "--input-scores-csv",
            str(scores),
            "--input-summary-json",
            str(summary),
            "--label-csv",
            str(labels),
            "--expected-complete-rows",
            "3",
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ],
        check=True,
        cwd=ROOT,
    )
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    review = payload["summary"]

    assert review["status"] == "blocked_frozen_shadow_review_claim_locked"
    assert "partial_frozen_coverage_only" in review["blockers"]
    assert "T1_decoys_above_positive:1" in review["blockers"]
    assert review["claim_promotion_allowed"] is False
    assert payload["claim_boundary"]["labels_used_for_scoring"] is False
    assert "claim_promotion_allowed: `false`" in out_md.read_text(encoding="utf-8")
