from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from tools.product.build_lit_pcba_product_scores_from_htvs import build_scores


def test_build_lit_pcba_product_scores_from_htvs_aggregates_replicates(tmp_path: Path) -> None:
    source = tmp_path / "stage3.csv"
    source.write_text(
        "target,ligand_id,binding_score_composite_v7\nADRB2,a,-2.0\nADRB2,a,-4.0\nADRB2,b,-1.0\n",
        encoding="utf-8",
    )
    summary = tmp_path / "summary.json"
    summary.write_text(json.dumps({"pass": True}), encoding="utf-8")
    out_scores = tmp_path / "scores.csv"
    out_json = tmp_path / "scores.json"

    build_scores(
        argparse.Namespace(
            htvs_scores_csv=str(source),
            execution_summary_json=str(summary),
            score_col="binding_score_composite_v7",
            out_scores_csv=str(out_scores),
            out_json=str(out_json),
            out_md=str(tmp_path / "scores.md"),
        )
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["status"] == "lit_pcba_product_scores_ready"
    assert payload["summary"]["execution_summary_pass"] is True
    with out_scores.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["ligand_id"] == "a"
    assert float(rows[0]["binding_score"]) == -3.0
    assert rows[0]["replicate_count"] == "2"
