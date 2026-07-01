from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from tools.product import build_gpcr_hard_decoy_current_fit_closure_probe as mod


TARGETS = (
    "CHEMBL217_DRD2_HUMAN",
    "CHEMBL224_HTR2A_HUMAN",
    "CHEMBL233_OPRM1_HUMAN",
)


def _write_fixture_inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    scores_csv = tmp_path / "scores.csv"
    labels_csv = tmp_path / "labels.csv"
    split_csv = tmp_path / "split.csv"

    score_rows: list[dict[str, object]] = []
    label_rows: list[dict[str, object]] = []
    split_rows: list[dict[str, object]] = []
    idx = 0
    for target_index, target in enumerate(TARGETS):
        for row_index in range(12):
            is_binder = row_index < 3
            ligand_id = f"{target_index}_{row_index}"
            signal = 50.0 + idx if is_binder else -50.0 - idx
            score_rows.append(
                {
                    "target": target,
                    "ligand_id": ligand_id,
                    "mean_min_distance_A": 4.0 if is_binder else 4.8 + row_index * 0.01,
                    "signal_a": signal,
                    "signal_b": signal * 0.5,
                    "reference_binding_kcal_mol": -12.0 if is_binder else -2.0,
                    "rank_artifact": 0 if is_binder else row_index,
                    "coverage_v2_adaptive_rank_rescue_shadow_fake": signal * 100.0,
                }
            )
            label_rows.append(
                {
                    "target": target,
                    "ligand_id": ligand_id,
                    "is_binder": 1 if is_binder else 0,
                    "reference_binding_kcal_mol": -12.0 if is_binder else -2.0,
                }
            )
            split_rows.append({"target": target, "ligand_id": ligand_id, "role": "far_ood_eval"})
            idx += 1

    for path, rows in ((scores_csv, score_rows), (labels_csv, label_rows), (split_csv, split_rows)):
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    return scores_csv, labels_csv, split_csv


def test_current_fit_closure_probe_is_claim_locked_and_excludes_forbidden_features(tmp_path: Path) -> None:
    if mod.LogisticRegression is None:
        pytest.skip("scikit-learn is not available")
    scores_csv, labels_csv, split_csv = _write_fixture_inputs(tmp_path)

    scores_out, payload = mod.build_probe(
        scores_csv=scores_csv,
        labels_csv=labels_csv,
        split_csv=split_csv,
        c_grid=(0.1,),
        bootstrap_n=20,
        bootstrap_seed=3,
    )

    assert payload["diagnostic_current_fit_used_labels"] is True
    assert payload["claim_promotion_allowed"] is False
    assert payload["scorer_apply_allowed"] is False
    assert payload["current_fit_closure_gate_pass"] is True
    assert payload["score_col"] == mod.SCORE_COL
    assert payload["target_heldout_score_col"] == mod.TARGET_HELDOUT_SCORE_COL
    assert mod.SCORE_COL in scores_out.columns
    assert mod.TARGET_HELDOUT_SCORE_COL in scores_out.columns
    assert set(scores_out["target"]) == set(TARGETS)
    assert payload["selected_target_heldout_positive_rank_rows"]
    assert payload["selected_target_heldout_target_metric_rows"]
    assert payload["selected_target_heldout_worst_positive_rank"] >= 1
    assert payload["selected_target_heldout_top20_positive_count"] >= 1
    assert "signal_a" in payload["feature_columns"]
    assert "reference_binding_kcal_mol" not in payload["feature_columns"]
    assert "rank_artifact" not in payload["feature_columns"]
    assert "coverage_v2_adaptive_rank_rescue_shadow_fake" not in payload["feature_columns"]


def test_main_writes_current_fit_probe_artifacts(tmp_path: Path) -> None:
    if mod.LogisticRegression is None:
        pytest.skip("scikit-learn is not available")
    scores_csv, labels_csv, split_csv = _write_fixture_inputs(tmp_path)
    out_scores = tmp_path / "out_scores.csv"
    out_json = tmp_path / "out.json"
    out_md = tmp_path / "out.md"

    rc = mod.main(
        [
            "--scores-csv",
            str(scores_csv),
            "--labels-csv",
            str(labels_csv),
            "--split-csv",
            str(split_csv),
            "--c-grid",
            "0.1",
            "--bootstrap-n",
            "20",
            "--out-scores-csv",
            str(out_scores),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ]
    )

    assert rc == 0
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["claim_promotion_allowed"] is False
    assert payload["status"] == "gpcr_hard_decoy_current_fit_closure_probe_ready_claim_locked"
    assert out_md.read_text(encoding="utf-8").startswith("# GPCR Hard-Decoy Current-Fit Closure Probe")
    rows = list(csv.DictReader(out_scores.open(encoding="utf-8")))
    assert len(rows) == 36
    assert mod.SCORE_COL in rows[0]
    assert mod.TARGET_HELDOUT_SCORE_COL in rows[0]
    assert payload["selected_target_heldout_positive_rank_rows"]
