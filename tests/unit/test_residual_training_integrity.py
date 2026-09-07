"""Synthetic regression training, metric oracles and cascade input contracts.

No production data, holdout, molecular calculation or model promotion is used.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import pytest
import torch
from sklearn.metrics import average_precision_score, auc, precision_recall_curve, roc_auc_score

from tools import train_residual_production_score_model as mod
from tools.product.stage2_skip_router import apply_stage2_skip_router, route_stage2_candidate


@pytest.fixture(autouse=True)
def single_cpu_thread():
    previous = torch.get_num_threads()
    torch.set_num_threads(1)
    yield
    torch.set_num_threads(previous)


def _rows(n=40):
    return [dict(ligand_id=f"lig{i}", target="synthetic_target", family="synthetic_family",
                 role="fit", is_binder=i % 2, raw_score=float(i % 4),
                 mean_min_distance_A=3., delta_score=0.2 * (i % 3), delta_energy=0.,
                 delta_force=12., refine_tier_label=99.) for i in range(n)]


def _train(tmp_path, rows=None, **kwargs):
    tmp_path.mkdir(parents=True, exist_ok=True)
    rows = _rows() if rows is None else rows
    dataset = tmp_path / "synthetic.csv"
    with dataset.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    receipt = tmp_path / "unbound_receipt.json"
    receipt.write_text(json.dumps({"summary": {"delta_force_derivation_validation_ready": True}}))
    params = dict(input_csv=str(dataset), out_checkpoint=str(tmp_path / "candidate.pt"),
                  epochs=2, hidden_dim=8, batch_size=8, device_name="cpu",
                  force_derivation_json=str(receipt))
    params.update(kwargs)
    summary = mod.train_residual_production_score_model(**params)
    return summary, torch.load(params["out_checkpoint"], map_location="cpu", weights_only=False)


@pytest.mark.parametrize("labels", [[0, 1], [1, 0]])
def test_all_ties_have_order_independent_distinct_metrics(labels):
    assert mod._auc_binary(labels, [.5, .5]) == .5
    assert mod._pr_auc_binary(labels, [.5, .5]) == .75
    assert mod._average_precision_binary(labels, [.5, .5]) == .5


@pytest.mark.parametrize("seed", range(16))
def test_metrics_match_sklearn_on_tied_random_scores(seed):
    rng = np.random.default_rng(seed)
    labels = [0, 1] + rng.integers(0, 2, size=38).tolist()
    scores = rng.integers(-3, 4, size=40).astype(float).tolist()
    precision, recall, _ = precision_recall_curve(labels, scores)
    assert mod._auc_binary(labels, scores) == pytest.approx(roc_auc_score(labels, scores), abs=1e-14)
    assert mod._pr_auc_binary(labels, scores) == pytest.approx(auc(recall, precision), abs=1e-14)
    assert mod._average_precision_binary(labels, scores) == pytest.approx(average_precision_score(labels, scores), abs=1e-14)
    permutation = rng.permutation(len(labels))
    for fn in (mod._auc_binary, mod._pr_auc_binary, mod._average_precision_binary):
        assert fn([labels[i] for i in permutation], [scores[i] for i in permutation]) == fn(labels, scores)


@pytest.mark.parametrize("labels,scores", [([], []), ([0, 1], [0.]), ([0, 2], [0., 1.]),
                                          ([0, 1], [float("nan"), 0.]), ([0, 1], [0., float("inf")])])
@pytest.mark.parametrize("name", ["_auc_binary", "_pr_auc_binary", "_average_precision_binary"])
def test_metrics_reject_invalid_inputs(labels, scores, name):
    with pytest.raises(ValueError):
        getattr(mod, name)(labels, scores)


@pytest.mark.parametrize("labels", [[0, 0], [1, 1]])
def test_undefined_roc_is_not_reported_as_chance(labels):
    assert mod._auc_binary(labels, [.1, .2]) is None
    if labels[0] == 0:
        assert mod._pr_auc_binary(labels, [.1, .2]) is None
        assert mod._average_precision_binary(labels, [.1, .2]) is None


def test_checkpoint_snapshot_owns_its_storage():
    model = mod.ResidualScoreMLP(2, 4)
    snapshot = mod._snapshot_state_dict(model)
    expected = {key: value.clone() for key, value in snapshot.items()}
    with torch.no_grad():
        for parameter in model.parameters():
            parameter.add_(1.)
    for key, value in snapshot.items():
        assert torch.equal(value, expected[key])
        assert value.data_ptr() != model.state_dict()[key].data_ptr()


def test_best_checkpoint_keeps_early_epoch_when_later_training_worsens(tmp_path, monkeypatch):
    real_snapshot = mod._snapshot_state_dict
    captured = []

    def snapshot(model):
        result = real_snapshot(model)
        captured.append({k: v.clone() for k, v in result.items()})
        return result

    values = iter([1., 0., 0.])
    monkeypatch.setattr(mod, "_snapshot_state_dict", snapshot)
    monkeypatch.setattr(mod, "_average_precision_binary", lambda *args: next(values))
    summary, payload = _train(tmp_path, epochs=3)
    assert summary["best"]["epoch"] == 1
    assert len(captured) == 1
    assert all(torch.equal(payload["state_dict"][k], v) for k, v in captured[0].items())


def test_real_training_does_not_claim_force_or_uncertainty_learning(tmp_path):
    summary, payload = _train(tmp_path)
    assert summary["delta_force_label_rows"] == 40
    assert summary["delta_force_derivation_validation_ready"] is True
    for output in (summary, payload):
        assert output["delta_force_head_trained"] is False
        assert output["delta_force_head_supervised"] is False
        assert output["delta_force_head_derivation_stub"] is False
        assert output["uncertainty_calibrated"] is False
        assert "delta_force" not in output["learned_output_fields"]
        assert "uncertainty" not in output["learned_output_fields"]
        assert output["physical_energy_residual_validated"] is False
    assert summary["production_checkpoint_ready"] is False
    assert summary["model_promoted"] is False
    assert summary["execution_enabled"] is False
    assert summary["missing_production_output_fields"] == ["delta_force", "uncertainty"]


def test_grouped_split_prevents_ligand_overlap_across_targets_and_poses():
    rows = [dict(ligand_id=f"lig{i // 3}", target=f"target{i % 3}") for i in range(30)]
    train, val = mod._split_indices(rows, 42, .8)
    assert train and val and sorted(train + val) == list(range(len(rows)))
    assert {rows[i]["ligand_id"] for i in train}.isdisjoint({rows[i]["ligand_id"] for i in val})
    assert mod._split_indices(rows, 42, .8) == (train, val)


@pytest.mark.parametrize("ratio", [0., 1., -1., float("nan"), float("inf")])
def test_invalid_split_ratio_is_rejected(ratio):
    with pytest.raises(ValueError):
        mod._split_indices(_rows(), 42, ratio)


@pytest.mark.parametrize("rows", [[{}, {}], [dict(ligand_id="same"), dict(ligand_id="same")]])
def test_no_independent_ligand_groups_is_an_error(rows):
    with pytest.raises(ValueError):
        mod._split_indices(rows, 42, .8)


def test_role_labels_never_enter_features():
    rows = _rows(2)
    rows[0]["role"], rows[1]["role"] = "positive", "negative"
    x1, *_, names = mod._matrix(rows, ["synthetic_family"], ["positive", "negative"])
    rows[0]["role"], rows[1]["role"] = "negative", "positive"
    x2, *_ = mod._matrix(rows, ["synthetic_family"], ["positive", "negative"])
    assert not any(name.startswith("role=") for name in names)
    assert torch.equal(x1, x2)


def test_true_zero_energy_label_does_not_use_refine_proxy():
    _, _, _, energy, mask, _ = mod._matrix(_rows(2), [], [])
    assert energy.tolist() == [0., 0.] and mask.tolist() == [1., 1.]


def test_refine_label_is_not_automatically_delta_energy():
    rows = _rows(2)
    for row in rows:
        row.pop("delta_energy")
    _, _, _, energy, mask, _ = mod._matrix(rows, [], [])
    assert energy.tolist() == [0., 0.] and mask.tolist() == [0., 0.]


def test_validation_labels_cannot_count_as_energy_head_training(tmp_path):
    rows = _rows(40)
    train, val = mod._split_indices(rows, 42, .5)
    for idx in train:
        rows[idx]["delta_energy"] = ""
    summary, _ = _train(tmp_path, rows, train_ratio=.5)
    assert summary["delta_energy_label_rows"] == len(val)
    assert summary["delta_energy_train_label_rows"] == 0
    assert summary["delta_energy_head_trained"] is False
    assert summary["best"]["energy_rmse"] is not None


def test_missing_energy_validation_is_unmeasured_not_zero(tmp_path):
    rows = _rows()
    for row in rows:
        row["delta_energy"] = ""
    summary, _ = _train(tmp_path, rows)
    assert summary["best"]["energy_rmse"] is None


def test_two_row_training_is_finite_and_deterministic(tmp_path):
    a, pa = _train(tmp_path / "a", _rows(2))
    b, pb = _train(tmp_path / "b", _rows(2))
    assert a["best"] == b["best"]
    assert all(torch.equal(pa["state_dict"][k], pb["state_dict"][k]) for k in pa["state_dict"])
    assert torch.isfinite(pa["x_std"]).all()


@pytest.mark.parametrize("params", [dict(epochs=0), dict(epochs=-1), dict(epochs=True), dict(hidden_dim=0),
                                   dict(batch_size=0), dict(lr=0.), dict(lr=float("nan")), dict(weight_decay=-1.)])
def test_invalid_training_parameters_do_not_write_checkpoint(tmp_path, params):
    with pytest.raises(ValueError):
        _train(tmp_path, **params)
    assert not (tmp_path / "candidate.pt").exists()


@pytest.mark.parametrize("key,value", [("is_binder", 1.7), ("is_binder", ""), ("delta_score", ""),
                                     ("raw_score", float("inf")), ("delta_score", float("nan"))])
def test_invalid_targets_or_features_do_not_create_a_model(tmp_path, key, value):
    rows = _rows()
    rows[0][key] = value
    with pytest.raises(ValueError):
        _train(tmp_path, rows)
    assert not (tmp_path / "candidate.pt").exists()


def test_old_or_modified_checkpoints_are_not_reused(tmp_path):
    summary, _ = _train(tmp_path)
    params = dict(input_csv=str(tmp_path / "synthetic.csv"), out_checkpoint=str(tmp_path / "candidate.pt"),
                  out_json=str(tmp_path / "summary.json"), force_derivation_json=str(tmp_path / "unbound_receipt.json"),
                  fingerprint_json=str(tmp_path / "fingerprint.json"), epochs=2, hidden_dim=8, batch_size=8,
                  lr=1e-3, weight_decay=1e-5, train_ratio=.8, seed=42)
    fingerprint_args = {k: v for k, v in params.items() if k not in ("out_checkpoint", "out_json", "fingerprint_json")}
    fingerprint = mod.build_train_fingerprint(**fingerprint_args)
    assert fingerprint["trainer_source_sha256"]
    mod.write_train_fingerprint(params["fingerprint_json"], fingerprint)
    Path(params["out_json"]).write_text(json.dumps(summary))
    assert mod.try_skip_training(**params) is not None
    legacy = dict(summary)
    legacy.pop("trainer_contract_version")
    Path(params["out_json"]).write_text(json.dumps(legacy))
    assert mod.try_skip_training(**params) is None
    Path(params["out_json"]).write_text(json.dumps(summary))
    Path(params["out_checkpoint"]).write_bytes(b"modified")
    assert mod.try_skip_training(**params) is None


@pytest.mark.parametrize("row", [{"prior_rank_proxy": 0.}, {"prior_rank_proxy": 0}, {"rank_pct": 0.},
                                {"prior_rank_proxy": "", "rank_pct": 0.}, {"prior_rank_proxy": None, "rank_pct": "0"}])
def test_cascade_zero_rank_does_not_become_tail(row):
    before = row.copy()
    retained, summary = apply_stage2_skip_router([row], family="gpcr")
    assert len(retained) == 1
    assert summary["stage2_skip_count"] == 0
    assert retained[0]["stage2_prior_rank_proxy"] == 0.
    assert row == before


@pytest.mark.parametrize("rank", [.01, .25, .5, 1.])
def test_nonzero_router_semantics_remain_unchanged(rank):
    _, summary = apply_stage2_skip_router([dict(prior_rank_proxy=rank)], family="gpcr")
    expected = route_stage2_candidate(family="gpcr", prior_rank_proxy=rank)
    assert all(summary["routed_rows"][0][key] == value for key, value in expected.items())
