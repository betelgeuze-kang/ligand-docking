from __future__ import annotations

import argparse
import csv
from pathlib import Path

from tools.casp17.build_casp_archive_structure_regression_results import build_results


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_build_casp_archive_structure_regression_results_parses_local_pdbs(tmp_path: Path) -> None:
    dataset = tmp_path / "casp" / "extracted" / "archive"
    dataset.mkdir(parents=True)
    (dataset / "T0001.pdb").write_text(
        "ATOM      1  CA  GLY A   1       0.0   0.0   0.0  1.00 10.00           C\n",
        encoding="utf-8",
    )
    out_csv = tmp_path / "results.csv"

    payload = build_results(
        argparse.Namespace(
            dataset_artifact=str(tmp_path / "casp"),
            max_targets=0,
            threshold=0.5,
            out_csv=str(out_csv),
            out_json=str(tmp_path / "results.json"),
            out_md=str(tmp_path / "results.md"),
        )
    )

    assert payload["summary"]["status"] == "casp_archive_structure_regression_results_ready"
    assert payload["summary"]["target_pass_rate"] == 1.0
    assert _rows(out_csv)[0]["target_id"] == "T0001"


def test_build_casp_archive_structure_regression_results_blocks_without_targets(tmp_path: Path) -> None:
    dataset = tmp_path / "casp"
    dataset.mkdir()

    payload = build_results(
        argparse.Namespace(
            dataset_artifact=str(dataset),
            max_targets=0,
            threshold=0.5,
            out_csv=str(tmp_path / "results.csv"),
            out_json=str(tmp_path / "results.json"),
            out_md=str(tmp_path / "results.md"),
        )
    )

    assert payload["summary"]["status"] == "blocked_casp_archive_structure_regression_results"
    assert "casp_archive_pdb_targets_missing" in payload["summary"]["blockers"]
