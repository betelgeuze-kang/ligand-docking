from pathlib import Path

import pandas as pd

from tools import evaluate_ligand_ranking_metrics as mod


def test_ranking_metrics_auc_and_topk(tmp_path: Path):
    scores_csv = tmp_path / "scores.csv"
    labels_csv = tmp_path / "labels.csv"
    out_json = tmp_path / "out.json"
    out_md = tmp_path / "out.md"
    out_rows = tmp_path / "rows.csv"
    out_topk = tmp_path / "topk.csv"

    # Lower score is better; positives should rank at top.
    scores = pd.DataFrame(
        [
            {"target": "T", "ligand_id": "A", "binding_energy_mmpbsa_kcal_mol_calibrated": -9.0},
            {"target": "T", "ligand_id": "B", "binding_energy_mmpbsa_kcal_mol_calibrated": -8.0},
            {"target": "T", "ligand_id": "C", "binding_energy_mmpbsa_kcal_mol_calibrated": -1.0},
            {"target": "T", "ligand_id": "D", "binding_energy_mmpbsa_kcal_mol_calibrated": -0.5},
        ]
    )
    labels = pd.DataFrame(
        [
            {"target": "T", "ligand_id": "A", "is_binder": 1, "reference_binding_kcal_mol": -10.0},
            {"target": "T", "ligand_id": "B", "is_binder": 1, "reference_binding_kcal_mol": -9.0},
            {"target": "T", "ligand_id": "C", "is_binder": 0, "reference_binding_kcal_mol": -1.0},
            {"target": "T", "ligand_id": "D", "is_binder": 0, "reference_binding_kcal_mol": -0.5},
        ]
    )
    scores.to_csv(scores_csv, index=False)
    labels.to_csv(labels_csv, index=False)

    args = mod.build_parser().parse_args(
        [
            "--scores-csv",
            str(scores_csv),
            "--labels-csv",
            str(labels_csv),
            "--bootstrap-n",
            "64",
            "--topk-list",
            "1,2",
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
            "--out-detail-csv",
            str(out_rows),
            "--out-topk-csv",
            str(out_topk),
        ]
    )
    payload = mod.run_eval(args)
    assert bool(payload["pass"]) is True
    assert bool(payload["has_labels"]) is True
    auc = float(payload["metrics"]["roc_auc"])
    assert auc >= 0.99
    assert float(payload["metrics"]["roc_auc_unique_key"]) >= 0.99
    assert float(payload["metrics"]["pr_auc_unique_key"]) >= 0.99
    assert float(payload["metrics"]["ef1_unique_key"]) >= 1.0
    assert int(payload["metrics"]["positive_count_unique_key"]) == 2
    assert "roc_auc_unique_key" in payload["metrics_ci"]
    assert "pr_auc_unique_key" in payload["metrics_ci"]
    topk = payload["topk"]
    assert len(topk) >= 2
    assert float(topk[0]["hit_rate"]) >= 1.0


def test_ranking_metrics_with_split_roles(tmp_path: Path):
    scores_csv = tmp_path / "scores.csv"
    labels_csv = tmp_path / "labels.csv"
    split_csv = tmp_path / "split.csv"
    out_json = tmp_path / "out.json"
    out_rows = tmp_path / "rows.csv"
    out_topk = tmp_path / "topk.csv"
    out_unique = tmp_path / "unique.csv"

    scores = pd.DataFrame(
        [
            {"target": "T1", "ligand_id": "A", "binding_energy_mmpbsa_kcal_mol_calibrated": -9.0},
            {"target": "T1", "ligand_id": "B", "binding_energy_mmpbsa_kcal_mol_calibrated": -1.0},
            {"target": "T2", "ligand_id": "A", "binding_energy_mmpbsa_kcal_mol_calibrated": -8.0},
            {"target": "T2", "ligand_id": "B", "binding_energy_mmpbsa_kcal_mol_calibrated": -0.5},
            {"target": "T3", "ligand_id": "A", "binding_energy_mmpbsa_kcal_mol_calibrated": -7.0},
            {"target": "T3", "ligand_id": "B", "binding_energy_mmpbsa_kcal_mol_calibrated": -0.3},
        ]
    )
    labels = pd.DataFrame(
        [
            {"target": "T1", "ligand_id": "A", "is_binder": 1, "reference_binding_kcal_mol": -10.0},
            {"target": "T1", "ligand_id": "B", "is_binder": 0, "reference_binding_kcal_mol": -1.0},
            {"target": "T2", "ligand_id": "A", "is_binder": 1, "reference_binding_kcal_mol": -9.0},
            {"target": "T2", "ligand_id": "B", "is_binder": 0, "reference_binding_kcal_mol": -1.2},
            {"target": "T3", "ligand_id": "A", "is_binder": 1, "reference_binding_kcal_mol": -8.0},
            {"target": "T3", "ligand_id": "B", "is_binder": 0, "reference_binding_kcal_mol": -0.8},
        ]
    )
    split = pd.DataFrame(
        [
            {"target": "T1", "ligand_id": "A", "role": "fit"},
            {"target": "T1", "ligand_id": "B", "role": "fit"},
            {"target": "T2", "ligand_id": "A", "role": "eval"},
            {"target": "T2", "ligand_id": "B", "role": "eval"},
            {"target": "T3", "ligand_id": "A", "role": "ood_eval"},
            {"target": "T3", "ligand_id": "B", "role": "ood_eval"},
        ]
    )
    scores.to_csv(scores_csv, index=False)
    labels.to_csv(labels_csv, index=False)
    split.to_csv(split_csv, index=False)

    args = mod.build_parser().parse_args(
        [
            "--scores-csv",
            str(scores_csv),
            "--labels-csv",
            str(labels_csv),
            "--split-csv",
            str(split_csv),
            "--eval-roles",
            "eval",
            "--ood-eval-roles",
            "ood_eval",
            "--require-split-for-eval",
            "--require-ood-eval",
            "--bootstrap-n",
            "64",
            "--out-json",
            str(out_json),
            "--out-detail-csv",
            str(out_rows),
            "--out-topk-csv",
            str(out_topk),
            "--out-unique-csv",
            str(out_unique),
        ]
    )
    payload = mod.run_eval(args)
    assert bool(payload["pass"]) is True
    assert int(payload["rows_eval_filtered"]) == 2
    assert int(payload["rows_eval_ood"]) == 2
    assert float(payload["metrics"]["roc_auc_unique_key"]) >= 0.99
    assert float(payload["metrics"]["roc_auc_ood_unique_key"]) >= 0.99
    assert float(payload["metrics"]["pr_auc_unique_key"]) >= 0.99
    assert float(payload["metrics"]["pr_auc_ood_unique_key"]) >= 0.99
    assert int(payload["metrics"]["positive_count_unique_key"]) == 1
    assert int(payload["metrics"]["positive_count_ood_unique_key"]) == 1


def test_ranking_probability_score_is_separated_from_ranking_score(tmp_path: Path):
    scores_csv = tmp_path / "scores.csv"
    labels_csv = tmp_path / "labels.csv"

    scores = pd.DataFrame(
        [
            {"target": "T", "ligand_id": "A", "raw_score": -10.0, "cal_score": 100.0},
            {"target": "T", "ligand_id": "B", "raw_score": -9.0, "cal_score": 90.0},
            {"target": "T", "ligand_id": "C", "raw_score": -1.0, "cal_score": -90.0},
            {"target": "T", "ligand_id": "D", "raw_score": -0.5, "cal_score": -100.0},
        ]
    )
    labels = pd.DataFrame(
        [
            {"target": "T", "ligand_id": "A", "is_binder": 1, "reference_binding_kcal_mol": -10.0},
            {"target": "T", "ligand_id": "B", "is_binder": 1, "reference_binding_kcal_mol": -9.0},
            {"target": "T", "ligand_id": "C", "is_binder": 0, "reference_binding_kcal_mol": -1.0},
            {"target": "T", "ligand_id": "D", "is_binder": 0, "reference_binding_kcal_mol": -0.5},
        ]
    )
    scores.to_csv(scores_csv, index=False)
    labels.to_csv(labels_csv, index=False)

    args_sep = mod.build_parser().parse_args(
        [
            "--scores-csv",
            str(scores_csv),
            "--labels-csv",
            str(labels_csv),
            "--score-col",
            "raw_score",
            "--probability-score-col",
            "cal_score",
            "--bootstrap-n",
            "16",
            "--out-json",
            str(tmp_path / "out_sep.json"),
            "--out-md",
            str(tmp_path / "out_sep.md"),
            "--out-detail-csv",
            str(tmp_path / "rows_sep.csv"),
            "--out-topk-csv",
            str(tmp_path / "topk_sep.csv"),
            "--out-unique-csv",
            str(tmp_path / "unique_sep.csv"),
        ]
    )
    sep = mod.run_eval(args_sep)

    args_raw = mod.build_parser().parse_args(
        [
            "--scores-csv",
            str(scores_csv),
            "--labels-csv",
            str(labels_csv),
            "--score-col",
            "raw_score",
            "--bootstrap-n",
            "16",
            "--out-json",
            str(tmp_path / "out_raw.json"),
            "--out-md",
            str(tmp_path / "out_raw.md"),
            "--out-detail-csv",
            str(tmp_path / "rows_raw.csv"),
            "--out-topk-csv",
            str(tmp_path / "topk_raw.csv"),
            "--out-unique-csv",
            str(tmp_path / "unique_raw.csv"),
        ]
    )
    raw = mod.run_eval(args_raw)

    assert float(sep["metrics"]["roc_auc_unique_key"]) >= 0.99
    assert abs(float(sep["metrics"]["roc_auc_unique_key"]) - float(raw["metrics"]["roc_auc_unique_key"])) < 1e-9
    assert sep["metrics"]["probability_score_col_used"] == "cal_score"
    assert raw["metrics"]["probability_score_col_used"] == "raw_score"
    assert abs(float(sep["metrics"]["brier_unique_key"]) - float(raw["metrics"]["brier_unique_key"])) > 1e-4


def test_ranking_orientation_suspect_flag(tmp_path: Path):
    scores_csv = tmp_path / "scores.csv"
    labels_csv = tmp_path / "labels.csv"

    # Lower is configured as better, but binders have higher scores here.
    scores = pd.DataFrame(
        [
            {"target": "T", "ligand_id": "A", "s": 9.0},
            {"target": "T", "ligand_id": "B", "s": 8.0},
            {"target": "T", "ligand_id": "C", "s": 1.0},
            {"target": "T", "ligand_id": "D", "s": 0.5},
        ]
    )
    labels = pd.DataFrame(
        [
            {"target": "T", "ligand_id": "A", "is_binder": 1, "reference_binding_kcal_mol": -9.0},
            {"target": "T", "ligand_id": "B", "is_binder": 1, "reference_binding_kcal_mol": -8.0},
            {"target": "T", "ligand_id": "C", "is_binder": 0, "reference_binding_kcal_mol": -1.0},
            {"target": "T", "ligand_id": "D", "is_binder": 0, "reference_binding_kcal_mol": -0.5},
        ]
    )
    scores.to_csv(scores_csv, index=False)
    labels.to_csv(labels_csv, index=False)

    args = mod.build_parser().parse_args(
        [
            "--scores-csv",
            str(scores_csv),
            "--labels-csv",
            str(labels_csv),
            "--score-col",
            "s",
            "--bootstrap-n",
            "16",
            "--out-json",
            str(tmp_path / "out.json"),
            "--out-md",
            str(tmp_path / "out.md"),
            "--out-detail-csv",
            str(tmp_path / "rows.csv"),
            "--out-topk-csv",
            str(tmp_path / "topk.csv"),
            "--out-unique-csv",
            str(tmp_path / "unique.csv"),
        ]
    )
    payload = mod.run_eval(args)
    assert float(payload["metrics"]["roc_auc_unique_key"]) <= 0.05
    assert float(payload["metrics"]["roc_auc_if_flipped"]) >= 0.95
    assert bool(payload["metrics"]["score_orientation_suspect"]) is True


def test_ranking_expected_keys_filter_removes_unscored_label_rows(tmp_path: Path):
    scores_csv = tmp_path / "scores.csv"
    labels_csv = tmp_path / "labels.csv"
    expected_csv = tmp_path / "expected.csv"

    scores = pd.DataFrame(
        [
            {"target": "T", "ligand_id": "A", "s": -10.0},
            {"target": "T", "ligand_id": "B", "s": -1.0},
        ]
    )
    labels = pd.DataFrame(
        [
            {"target": "T", "ligand_id": "A", "is_binder": 1, "reference_binding_kcal_mol": -10.0},
            {"target": "T", "ligand_id": "B", "is_binder": 0, "reference_binding_kcal_mol": -1.0},
            # Not part of queue/expected keys; should be excluded from eval.
            {"target": "T", "ligand_id": "C", "is_binder": 0, "reference_binding_kcal_mol": -1.0},
            {"target": "T", "ligand_id": "D", "is_binder": 0, "reference_binding_kcal_mol": -0.5},
        ]
    )
    expected = pd.DataFrame([{"target": "T", "ligand_id": "A"}, {"target": "T", "ligand_id": "B"}])
    scores.to_csv(scores_csv, index=False)
    labels.to_csv(labels_csv, index=False)
    expected.to_csv(expected_csv, index=False)

    args = mod.build_parser().parse_args(
        [
            "--scores-csv",
            str(scores_csv),
            "--labels-csv",
            str(labels_csv),
            "--score-col",
            "s",
            "--expected-keys-csv",
            str(expected_csv),
            "--min-expected-score-coverage",
            "1.0",
            "--bootstrap-n",
            "16",
            "--out-json",
            str(tmp_path / "out.json"),
            "--out-md",
            str(tmp_path / "out.md"),
            "--out-detail-csv",
            str(tmp_path / "rows.csv"),
            "--out-topk-csv",
            str(tmp_path / "topk.csv"),
            "--out-unique-csv",
            str(tmp_path / "unique.csv"),
        ]
    )
    payload = mod.run_eval(args)
    assert int(payload["rows_expected_keys"]) == 2
    assert int(payload["rows_expected_keys_with_score"]) == 2
    assert float(payload["observed_expected_score_coverage_ratio"]) == 1.0
    assert int(payload["rows_eval_filtered"]) == 2
    assert float(payload["metrics"]["roc_auc_unique_key"]) >= 0.99
