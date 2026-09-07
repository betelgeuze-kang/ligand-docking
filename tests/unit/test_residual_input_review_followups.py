"""Regressions for cached-data admission and scalar feature representations."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
import torch

from tools import train_residual_production_score_model as mod
from tools.product import build_residual_production_supervised_dataset as builder
from tests.unit.test_residual_training_integrity import _rows, _train


@pytest.mark.parametrize("field", ["raw_score", "mean_min_distance_A", "refine_tier_delta"])
@pytest.mark.parametrize("value", [
    np.bool_(True), np.array(1.), np.array([1.]),
    np.ma.array(1., mask=True), torch.tensor(1.),
])
def test_only_real_scalar_or_csv_text_features_are_accepted(field, value):
    rows = _rows(2)
    rows[0][field] = value
    with pytest.raises(ValueError, match="invalid_training_feature"):
        mod._matrix(rows, [], [])


@pytest.mark.parametrize("value", [0., 0, np.int64(0), np.float32(0.), "0"])
def test_valid_scalar_zero_is_still_an_observation(value):
    observed, missing = mod._feature_value({"raw_score": value}, "raw_score", required=True)
    assert observed == 0. and missing == 0.


@pytest.mark.parametrize("role", ["holdout", "eval", "ood_eval", "far_ood_eval"])
def test_cached_training_path_rejects_evaluation_rows_even_with_matching_fingerprint(tmp_path, role):
    # Build a real synthetic candidate first; then form a matching cache fixture
    # for evaluation-tagged rows to exercise admission, not cryptographic trust.
    summary, _ = _train(tmp_path)
    dataset = tmp_path / "synthetic.csv"
    rows = _rows()
    rows[-1]["role"] = role
    with dataset.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    params = dict(input_csv=str(dataset), out_checkpoint=str(tmp_path / "candidate.pt"),
                  out_json=str(tmp_path / "summary.json"),
                  force_derivation_json=str(tmp_path / "unbound_receipt.json"),
                  fingerprint_json=str(tmp_path / "fingerprint.json"), epochs=2,
                  hidden_dim=8, batch_size=8, lr=1e-3, weight_decay=1e-5,
                  train_ratio=.8, seed=42)
    fargs = {k: v for k, v in params.items() if k not in ("out_checkpoint", "out_json", "fingerprint_json")}
    mod.write_train_fingerprint(params["fingerprint_json"], mod.build_train_fingerprint(**fargs))
    Path(params["out_json"]).write_text(json.dumps(summary), encoding="utf-8")
    before = hashlib.sha256(Path(params["out_checkpoint"]).read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="evaluation_only_training_input"):
        mod.try_skip_training(**params)
    assert hashlib.sha256(Path(params["out_checkpoint"]).read_bytes()).hexdigest() == before


@pytest.mark.parametrize("field", ["role", "split", "dataset_split"])
@pytest.mark.parametrize("role", ["eval", "ood_eval", "id_eval", "near_ood_eval", "far_ood_eval"])
def test_shared_policy_also_protects_dataset_materialization(tmp_path, field, role):
    row = dict(target="synthetic", ligand_id="lig1", is_binder=1,
               reference_binding_kcal_mol=-1., binding_score_composite_v7=-2., **{field: role})
    path = tmp_path / "synthetic_stage5_ranking_rows.csv"
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)
    result = builder.build_residual_production_supervised_dataset(
        stage5_glob=str(path), min_rows=1, min_targets=1,
    )
    assert result["rows"] == []
    assert result["sources"][0]["rejections"][0]["reason"] == "evaluation_only_row"
