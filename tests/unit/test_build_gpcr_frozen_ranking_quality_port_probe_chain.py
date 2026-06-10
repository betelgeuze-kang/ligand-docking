from __future__ import annotations

import csv
from pathlib import Path

from tools.gpcr_replay.build_gpcr_frozen_ranking_quality_port_probe_chain import build_probe_subset


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def test_build_probe_subset_includes_positives_slice_and_top_decoys(tmp_path: Path) -> None:
    stage3 = tmp_path / "stage3.csv"
    stage5 = tmp_path / "stage5.csv"
    slice_rows = tmp_path / "slice.csv"
    review = tmp_path / "review.json"
    out = tmp_path / "subset.csv"
    _write_csv(
        stage3,
        [
            {"target": "CHEMBL217_DRD2_HUMAN", "ligand_id": "CHEMBL301265"},
            {"target": "CHEMBL217_DRD2_HUMAN", "ligand_id": "decoy_a"},
            {"target": "CHEMBL224_HTR2A_HUMAN", "ligand_id": "CHEMBL83894"},
            {"target": "CHEMBL233_OPRM1_HUMAN", "ligand_id": "CHEMBL331883"},
        ],
    )
    _write_csv(
        stage5,
        [
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "CHEMBL301265",
                "is_binder": "1",
                "binding_score_composite_v7_residual_active": "-1.0",
            },
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "decoy_a",
                "is_binder": "0",
                "binding_score_composite_v7_residual_active": "-2.0",
            },
        ],
    )
    _write_csv(
        slice_rows,
        [{"target": "CHEMBL217_DRD2_HUMAN", "ligand_id": "decoy_a"}],
    )
    review.write_text(
        '{"summary":{"shadow_score_summary":{"top10":[{"target":"CHEMBL224_HTR2A_HUMAN","ligand_id":"decoy_htr2a"}]}}}',
        encoding="utf-8",
    )

    summary = build_probe_subset(
        stage3_scores_csv=stage3,
        stage5_rows_csv=stage5,
        slice_rows_csv=slice_rows,
        v11_review_json=review,
        out_csv=out,
        top_decoys_per_target=1,
    )

    assert summary["subset_row_count"] == 4
    assert summary["target_row_counts"]["CHEMBL217_DRD2_HUMAN"] == 2
    assert summary["target_row_counts"]["CHEMBL224_HTR2A_HUMAN"] == 1
