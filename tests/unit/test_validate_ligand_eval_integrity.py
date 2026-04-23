from pathlib import Path

import pandas as pd

from tools import validate_ligand_eval_integrity as mod


def test_integrity_pass_zero_overlap(tmp_path: Path):
    split_csv = tmp_path / "split.csv"
    out_json = tmp_path / "out.json"
    out_csv = tmp_path / "out.csv"
    out_md = tmp_path / "out.md"
    split = pd.DataFrame(
        [
            {"target": "T1", "ligand_id": "A", "role": "fit"},
            {"target": "T1", "ligand_id": "B", "role": "fit"},
            {"target": "T2", "ligand_id": "A", "role": "eval"},
            {"target": "T2", "ligand_id": "B", "role": "eval"},
        ]
    )
    split.to_csv(split_csv, index=False)
    args = mod.build_parser().parse_args(
        [
            "--split-csv",
            str(split_csv),
            "--fit-roles",
            "fit",
            "--eval-roles",
            "eval",
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )
    payload = mod.run_validation(args)
    assert bool(payload["pass"]) is True
    assert int(payload["fit_eval_overlap_count"]) == 0


def test_integrity_fail_overlap(tmp_path: Path):
    split_csv = tmp_path / "split.csv"
    split = pd.DataFrame(
        [
            {"target": "T1", "ligand_id": "A", "role": "fit"},
            {"target": "T1", "ligand_id": "A", "role": "eval"},
        ]
    )
    split.to_csv(split_csv, index=False)
    args = mod.build_parser().parse_args(
        [
            "--split-csv",
            str(split_csv),
            "--fit-roles",
            "fit",
            "--eval-roles",
            "eval",
            "--out-json",
            str(tmp_path / "out.json"),
            "--out-csv",
            str(tmp_path / "out.csv"),
            "--out-md",
            str(tmp_path / "out.md"),
        ]
    )
    payload = mod.run_validation(args)
    assert bool(payload["pass"]) is False
    assert int(payload["fit_eval_overlap_count"]) == 1


def test_integrity_fail_on_observed_coverage_threshold(tmp_path: Path):
    split_csv = tmp_path / "split.csv"
    scores_csv = tmp_path / "scores.csv"
    split = pd.DataFrame(
        [
            {"target": "T1", "ligand_id": "A", "role": "fit"},
            {"target": "T1", "ligand_id": "B", "role": "fit"},
            {"target": "T2", "ligand_id": "C", "role": "eval"},
            {"target": "T2", "ligand_id": "D", "role": "eval"},
        ]
    )
    # Only one eval key is observed -> eval coverage 0.5
    scores = pd.DataFrame(
        [
            {"target": "T1", "ligand_id": "A", "score": -1.0},
            {"target": "T1", "ligand_id": "B", "score": -2.0},
            {"target": "T2", "ligand_id": "C", "score": -3.0},
        ]
    )
    split.to_csv(split_csv, index=False)
    scores.to_csv(scores_csv, index=False)
    args = mod.build_parser().parse_args(
        [
            "--split-csv",
            str(split_csv),
            "--scores-csv",
            str(scores_csv),
            "--fit-roles",
            "fit",
            "--eval-roles",
            "eval",
            "--min-observed-eval-coverage-ratio",
            "0.9",
            "--out-json",
            str(tmp_path / "out.json"),
            "--out-csv",
            str(tmp_path / "out.csv"),
            "--out-md",
            str(tmp_path / "out.md"),
        ]
    )
    payload = mod.run_validation(args)
    assert bool(payload["pass"]) is False
    assert float(payload["observed_eval_coverage_ratio"]) == 0.5
