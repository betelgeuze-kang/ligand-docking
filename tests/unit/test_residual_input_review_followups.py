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


@pytest.mark.parametrize("field", ["mean_min_distance_A", "refine_tier_delta"])
@pytest.mark.parametrize("training_missing", [False, True])
def test_unseen_optional_variation_has_zero_checkpoint_contribution(tmp_path, field, training_missing):
    rows = _rows()
    train, val = mod._split_indices(rows, 42, .8)
    for i, row in enumerate(rows):
        missing = training_missing if i in train else not training_missing
        row[field] = "" if missing else 3.0
    summary, payload = _train(tmp_path, rows, weight_decay=0., epochs=3)
    names = payload["feature_names"]
    neutral = summary["neutralized_feature_names"]
    if training_missing and field == "refine_tier_delta":
        assert field not in names and field + "_missing" not in names
        return
    for name in (field, field + "_missing"):
        index = names.index(name)
        assert name in neutral
        assert torch.count_nonzero(payload["state_dict"]["trunk.0.weight"][:, index]) == 0
    model = mod.ResidualScoreMLP(len(names), 8)
    model.load_state_dict(payload["state_dict"])
    model.eval()
    left = torch.zeros((3, len(names)))
    right = left.clone()
    right[:, names.index(field)] = 10000.0
    right[:, names.index(field + "_missing")] = 1.0
    with torch.no_grad():
        a, b = model(left), model(right)
    assert all(torch.equal(x, y) for x, y in zip(a, b))
    assert payload["constant_feature_policy"] == "zero_normalized_inputs_and_first_layer_weights"


def test_observed_missingness_variation_is_not_neutralized(tmp_path):
    rows = _rows()
    for i, row in enumerate(rows):
        row["refine_tier_delta"] = "" if i % 2 else float(i + 1)
    summary, payload = _train(tmp_path, rows, weight_decay=0.)
    name = "refine_tier_delta_missing"
    assert name in payload["feature_names"]
    assert name not in summary["neutralized_feature_names"]
    column = payload["feature_names"].index(name)
    assert torch.count_nonzero(payload["state_dict"]["trunk.0.weight"][:, column]) > 0


def test_unseen_missingness_does_not_change_validation_or_epoch_selection(tmp_path):
    rows = _rows()
    for row in rows:
        row["refine_tier_delta"] = 7.0
    baseline, first = _train(tmp_path / "observed", rows, weight_decay=0., epochs=3)
    _, val = mod._split_indices(rows, 42, .8)
    for i in val:
        rows[i]["refine_tier_delta"] = ""
        rows[i]["mean_min_distance_A"] = ""
    alternate, second = _train(tmp_path / "unseen", rows, weight_decay=0., epochs=3)
    assert baseline["best"] == alternate["best"]
    assert all(torch.equal(v, second["state_dict"][k]) for k, v in first["state_dict"].items())


def _duplicate_csv(path, key, *, alias=None, stage5=False):
    if stage5:
        row = dict(target="synthetic", ligand_id="lig1", is_binder=1,
                   reference_binding_kcal_mol=-1., binding_score_composite_v7=-2.)
    else:
        row = _rows(2)[0]
    row[key] = "true" if key == "evaluation_only" else "holdout"
    safe = "false" if key == "evaluation_only" else "fit"
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow([*row, alias or key])
        writer.writerow([*row.values(), safe])


@pytest.mark.parametrize("key", ["role", "split", "dataset_split", "evaluation_only"])
@pytest.mark.parametrize("alias_kind", ["same", "case", "space"])
def test_duplicate_policy_csv_headers_cannot_erase_exclusion(tmp_path, key, alias_kind):
    path = tmp_path / "duplicate.csv"
    alias = key if alias_kind == "same" else key.upper() if alias_kind == "case" else " " + key + " "
    _duplicate_csv(path, key, alias=alias)
    with pytest.raises(ValueError, match="duplicate_csv_column"):
        mod._load_rows(path)


def test_duplicate_headers_are_rejected_before_model_creation(tmp_path, monkeypatch):
    path = tmp_path / "duplicate.csv"
    _duplicate_csv(path, "role")
    def forbidden(*args, **kwargs):
        pytest.fail("lossy CSV reached model creation")
    monkeypatch.setattr(mod, "ResidualScoreMLP", forbidden)
    with pytest.raises(ValueError, match="duplicate_csv_column"):
        mod.train_residual_production_score_model(input_csv=str(path), out_checkpoint=str(tmp_path / "out.pt"))
    assert not (tmp_path / "out.pt").exists()


@pytest.mark.parametrize("key", ["role", "split", "dataset_split", "evaluation_only"])
def test_materializer_rejects_duplicate_policy_headers_too(tmp_path, key):
    path = tmp_path / "synthetic_stage5_ranking_rows.csv"
    _duplicate_csv(path, key, stage5=True)
    result = builder.build_residual_production_supervised_dataset(stage5_glob=str(path), min_rows=1, min_targets=1)
    assert result["rows"] == []
    assert "duplicate_csv_column" in result["sources"][0]["status"]


@pytest.mark.parametrize("delta", [-1, 1])
def test_wrong_csv_row_width_is_not_silently_repaired(tmp_path, delta):
    row = _rows(2)[0]
    path = tmp_path / "wrong_width.csv"
    values = list(row.values())
    values = values[:-1] if delta < 0 else values + ["holdout"]
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh); w.writerow(row); w.writerow(values)
    with pytest.raises(ValueError, match="csv_row_width_mismatch"):
        mod._load_rows(path)


@pytest.mark.parametrize("header", ["role,role", "raw_score,raw_score", "role, Role ", "role,", ""])
def test_ambiguous_or_empty_headers_are_rejected_even_without_data(tmp_path, header):
    path = tmp_path / "bad_header.csv"
    path.write_text(header + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="csv_header|csv_column"):
        mod._load_rows(path)


def test_single_policy_header_alias_is_normalized_not_ignored(tmp_path):
    path = tmp_path / "capitalized.csv"
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh); w.writerow([" Role "]); w.writerow(["holdout"])
    with pytest.raises(ValueError, match="evaluation_only_training_input"):
        mod._load_rows(path)


def test_duplicate_stage3_proxy_columns_are_not_last_value_wins(tmp_path):
    path = tmp_path / "stage3.csv"
    path.write_text("target,ligand_id,binding_energy_proxy,binding_energy_proxy\nsynthetic,lig1,-3,-4\n", encoding="utf-8")
    values, status = builder._load_energy_proxy_map(path)
    assert values == {}
    assert "duplicate_csv_column" in status["stage3_energy_proxy_status"]
