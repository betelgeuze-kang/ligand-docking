from __future__ import annotations

import argparse
import csv
from pathlib import Path

from tools.product.build_public_benchmark_product_scores_from_htvs import build_scores


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_build_public_benchmark_product_scores_from_htvs_groups_scores(tmp_path: Path) -> None:
    source = tmp_path / "stage3.csv"
    source.write_text(
        "target,ligand_id,binding_score_composite_v7\n"
        "AA2AR,L1,-2.0\n"
        "AA2AR,L1,-4.0\n"
        "AA2AR,L2,1.0\n",
        encoding="utf-8",
    )
    out = tmp_path / "scores.csv"

    payload = build_scores(
        argparse.Namespace(
            suite_id="dude_z_decoy_smoke",
            htvs_scores_csv=str(source),
            execution_summary_json="",
            score_col="binding_score_composite_v7",
            target_col="target",
            ligand_col="ligand_id",
            out_scores_csv=str(out),
            out_json=str(tmp_path / "scores.json"),
            out_md=str(tmp_path / "scores.md"),
        )
    )

    assert payload["summary"]["status"] == "public_benchmark_product_scores_ready"
    assert payload["summary"]["output_rows"] == 2
    rows = _rows(out)
    assert rows[0]["ligand_id"] == "L1"
    assert rows[0]["binding_score"] == "-3.0"


