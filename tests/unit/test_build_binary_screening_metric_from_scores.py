from __future__ import annotations

import argparse
from pathlib import Path

from tools.build_binary_screening_metric_from_scores import build_metric


def test_build_binary_screening_metric_from_scores_passes_auc(tmp_path: Path) -> None:
    scores = tmp_path / "scores.csv"
    labels = tmp_path / "labels.csv"
    scores.write_text(
        "target,ligand_id,binding_score\n"
        "T,A,-4.0\n"
        "T,B,-3.0\n"
        "T,C,2.0\n"
        "T,D,3.0\n",
        encoding="utf-8",
    )
    labels.write_text(
        "target,ligand_id,is_binder\n"
        "T,A,1\n"
        "T,B,1\n"
        "T,C,0\n"
        "T,D,0\n",
        encoding="utf-8",
    )

    payload = build_metric(
        argparse.Namespace(
            suite_id="dude_z_decoy_smoke",
            scores_csv=str(scores),
            labels_csv=str(labels),
            score_col="binding_score",
            target_col="target",
            ligand_col="ligand_id",
            binder_col="is_binder",
            threshold=0.6,
            lower_better=True,
            out_json=str(tmp_path / "metric.json"),
            out_md=str(tmp_path / "metric.md"),
        )
    )

    assert payload["summary"]["status"] == "binary_screening_metric_pass"
    assert payload["summary"]["roc_auc"] == 1.0
