from __future__ import annotations

import csv
import itertools
import json
import math
from pathlib import Path

import numpy as np
import pytest
import torch

from tools import train_residual_production_score_model as mod
from tools.product import stage2_skip_router as router


def _write_dataset(path: Path, rows: int = 40, *, include_delta_energy: bool = False) -> None:
    energy_header = ",delta_energy,delta_energy_label_source" if include_delta_energy else ""
    path.write_text(
        "target,family,ligand_id,is_binder,role,reference_binding_kcal_mol,raw_score,score_col,delta_score,corrected_score,mean_min_distance_A,source_csv,label_source"
        + energy_header
        + "\n"
        + "\n".join(
            (
                f"ADRB2_GPCR_BLIND,gpcr,lig{i},{1 if i % 2 == 0 else 0},fit,"
                f"{-9.0 if i % 2 == 0 else -2.0},{-8.0 if i % 2 == 0 else -1.0},"
                f"binding_score_composite_v7,{(-9.0 if i % 2 == 0 else -2.0) - (-8.0 if i % 2 == 0 else -1.0)},"
                f"{-9.0 if i % 2 == 0 else -2.0},3.0,fixture,fixture"
                + (f",{-8.5 + i * 0.01},fixture_energy_proxy" if include_delta_energy else "")
            )
            for i in range(rows)
        )
        + "\n",
        encoding="utf-8",
    )


def test_train_default_force_derivation_path_does_not_read_repo_artifact(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset.csv"
    checkpoint = tmp_path / "model.pt"
    _write_dataset(dataset, rows=12, include_delta_energy=True)

    summary = mod.train_residual_production_score_model(
        input_csv=str(dataset),
        out_checkpoint=str(checkpoint),
        epochs=1,
        hidden_dim=8,
        batch_size=8,
        device_name="cpu",
        force_derivation_json=mod.DEFAULT_FORCE_DERIVATION_JSON,
    )

    assert summary["delta_force_head_derivation_stub"] is False
    assert summary["production_checkpoint_ready"] is False
    assert "delta_force" in summary["missing_production_output_fields"]


def test_train_residual_production_score_model_writes_checkpoint(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset.csv"
    checkpoint = tmp_path / "model.pt"
    _write_dataset(dataset)

    summary = mod.train_residual_production_score_model(
        input_csv=str(dataset),
        out_checkpoint=str(checkpoint),
        epochs=2,
        hidden_dim=8,
        batch_size=8,
        device_name="cpu",
        force_derivation_json=str(tmp_path / "missing_derivation.json"),
    )
    assert summary["train_rows"] > 0
    assert summary["val_rows"] > 0
    assert checkpoint.exists()
    assert summary["production_checkpoint_ready"] is False
    assert summary["policy_output_adapter_ready"] is True
    assert summary["policy_output_fields"] == ["abstention_reason", "stage2_route_decision"]
    assert summary["missing_production_output_fields"] == ["delta_energy", "delta_force"]
    assert summary["delta_energy_head_trained"] is False
    assert summary["delta_energy_label_rows"] == 0


def test_train_residual_production_score_model_trains_delta_energy_head_when_labels_exist(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset.csv"
    checkpoint = tmp_path / "model.pt"
    _write_dataset(dataset, rows=40, include_delta_energy=True)

    summary = mod.train_residual_production_score_model(
        input_csv=str(dataset),
        out_checkpoint=str(checkpoint),
        epochs=2,
        hidden_dim=8,
        batch_size=8,
        device_name="cpu",
        force_derivation_json=str(tmp_path / "missing_derivation.json"),
    )

    checkpoint_payload = torch.load(checkpoint, map_location="cpu", weights_only=False)
    assert summary["delta_energy_head_trained"] is True
    assert summary["delta_energy_label_rows"] == 40
    assert "delta_energy" in summary["learned_output_fields"]
    assert summary["missing_production_output_fields"] == ["delta_force"]
    assert checkpoint_payload["delta_energy_head_trained"] is True
    assert "delta_energy" in checkpoint_payload["learned_output_fields"]
    assert "delta_energy" in checkpoint_payload["output_fields"]


def test_train_residual_production_score_model_does_not_claim_force_training_from_derivation(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset.csv"
    checkpoint = tmp_path / "model.pt"
    derivation_json = tmp_path / "derivation.json"
    _write_dataset(dataset, rows=40, include_delta_energy=True)
    derivation_json.write_text(
        json.dumps({"summary": {"delta_force_derivation_validation_ready": True}}) + "\n",
        encoding="utf-8",
    )

    summary = mod.train_residual_production_score_model(
        input_csv=str(dataset),
        out_checkpoint=str(checkpoint),
        epochs=2,
        hidden_dim=8,
        batch_size=8,
        device_name="cpu",
        force_derivation_json=str(derivation_json),
    )

    checkpoint_payload = torch.load(checkpoint, map_location="cpu", weights_only=False)
    assert summary["delta_force_head_trained"] is False
    assert summary["delta_force_head_supervised"] is False
    assert summary["delta_force_head_derivation_stub"] is False
    assert summary["delta_force_derivation_validation_ready"] is True
    assert "delta_force" not in summary["learned_output_fields"]
    assert summary["missing_production_output_fields"] == ["delta_force"]
    assert summary["production_checkpoint_ready"] is False
    assert "delta_force" not in checkpoint_payload["output_fields"]


def test_train_residual_production_score_model_skip_if_unchanged(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset.csv"
    checkpoint = tmp_path / "model.pt"
    out_json = tmp_path / "model.json"
    fingerprint = tmp_path / "fingerprint.json"
    derivation_json = tmp_path / "derivation.json"
    _write_dataset(dataset, rows=40, include_delta_energy=True)
    derivation_json.write_text(
        json.dumps({"summary": {"delta_force_derivation_validation_ready": True}}) + "\n",
        encoding="utf-8",
    )
    summary = mod.train_residual_production_score_model(
        input_csv=str(dataset),
        out_checkpoint=str(checkpoint),
        epochs=2,
        hidden_dim=8,
        batch_size=8,
        device_name="cpu",
        force_derivation_json=str(derivation_json),
    )
    mod.write_train_fingerprint(
        fingerprint,
        mod.build_train_fingerprint(
            input_csv=str(dataset),
            force_derivation_json=str(derivation_json),
            epochs=2,
            hidden_dim=8,
            batch_size=8,
            seed=42,
        ),
    )
    out_json.write_text(
        json.dumps(summary)
        + "\n",
        encoding="utf-8",
    )
    skipped = mod.try_skip_training(
        input_csv=str(dataset),
        out_checkpoint=str(checkpoint),
        out_json=str(out_json),
        force_derivation_json=str(derivation_json),
        fingerprint_json=str(fingerprint),
        epochs=2,
        hidden_dim=8,
        batch_size=8,
        lr=1e-3,
        weight_decay=1e-5,
        train_ratio=0.8,
        seed=42,
    )
    assert skipped is not None
    assert skipped["training_skipped"] is True
    assert skipped["training_skip_reason"] == "inputs_unchanged"


def test_train_residual_production_score_model_cli_writes_outputs(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset.csv"
    _write_dataset(dataset)
    checkpoint = tmp_path / "model.pt"
    out_json = tmp_path / "model.json"
    out_md = tmp_path / "model.md"

    mod.main(
        [
            "--input-csv",
            str(dataset),
            "--out-checkpoint",
            str(checkpoint),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
            "--train-fingerprint-json",
            str(tmp_path / "fingerprint.json"),
            "--epochs",
            "2",
            "--hidden-dim",
            "8",
            "--batch-size",
            "8",
            "--device",
            "cpu",
            "--force-derivation-json",
            str(tmp_path / "missing_derivation.json"),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["checkpoint"] == str(checkpoint)
    assert "Residual Production Score Model" in out_md.read_text(encoding="utf-8")


# Numerical evidence is checked against an external implementation in CI, not
# inferred from self-consistency or the presence of a metadata field.
@pytest.mark.parametrize("labels", list(itertools.permutations([0, 0, 1, 1])))
def test_tied_metrics_are_order_independent(labels):
    labels = list(labels)
    scores = [0.5] * len(labels)
    assert mod._auc_binary(labels, scores) == 0.5
    assert mod._pr_auc_binary(labels, scores) == 0.75
    assert mod._average_precision_binary(labels, scores) == 0.5


@pytest.mark.parametrize("labels,scores", [
    ([], []), ([0, 1], [0.5]), ([0, 2], [0.5, 0.6]),
    ([0, 1], [math.nan, 0.5]), ([0, 1], [math.inf, 0.5]),
])
@pytest.mark.parametrize("metric", ["_auc_binary", "_pr_auc_binary", "_average_precision_binary"])
def test_invalid_metric_rows_do_not_report_a_score(metric, labels, scores):
    with pytest.raises(ValueError):
        getattr(mod, metric)(labels, scores)


def test_metrics_match_sklearn_on_200_tied_and_untied_cases():
    from sklearn.metrics import auc, average_precision_score, precision_recall_curve, roc_auc_score

    rng = np.random.default_rng(20260907)
    for index in range(200):
        labels = rng.integers(0, 2, size=12 + index % 37)
        labels[0], labels[1] = 0, 1
        scores = rng.normal(size=len(labels))
        if index % 2:
            scores = np.round(scores, 0)
        precision, recall, _ = precision_recall_curve(labels, scores)
        actual = (mod._auc_binary(labels.tolist(), scores.tolist()),
                  mod._pr_auc_binary(labels.tolist(), scores.tolist()),
                  mod._average_precision_binary(labels.tolist(), scores.tolist()))
        expected = (roc_auc_score(labels, scores), auc(recall, precision), average_precision_score(labels, scores))
        np.testing.assert_allclose(actual, expected, rtol=0, atol=1e-12)


def test_snapshot_does_not_share_storage_with_live_cpu_weights():
    model = mod.ResidualScoreMLP(3, 4)
    state = mod._snapshot_state(model)
    before = {key: value.clone() for key, value in state.items()}
    with torch.no_grad():
        for value in model.parameters():
            value.add_(10)
    for key in state:
        assert torch.equal(state[key], before[key])
        assert state[key].data_ptr() != model.state_dict()[key].data_ptr()


def _tiny_train(tmp_path, *, name="model", rows=16, epochs=2, **kwargs):
    dataset = tmp_path / "dataset.csv"
    if not dataset.exists():
        _write_dataset(dataset, rows=rows, include_delta_energy=True)
    checkpoint = tmp_path / f"{name}.pt"
    summary = mod.train_residual_production_score_model(
        input_csv=str(dataset), out_checkpoint=str(checkpoint), epochs=epochs,
        hidden_dim=4, batch_size=4, device_name="cpu", **kwargs,
    )
    return summary, torch.load(checkpoint, map_location="cpu", weights_only=True)


def test_two_cpu_trainings_replay_exactly(tmp_path):
    summary1, payload1 = _tiny_train(tmp_path, name="first")
    torch.rand(1000)  # unrelated caller activity must not change this trainer
    summary2, payload2 = _tiny_train(tmp_path, name="second")
    assert summary1["best"] == summary2["best"]
    for key, value in payload1["state_dict"].items():
        assert torch.equal(value, payload2["state_dict"][key])
    assert summary2["uncertainty_calibrated"] is False
    assert "uncertainty" not in payload2["learned_output_fields"]


def test_serialized_best_epoch_does_not_follow_later_optimizer_updates(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "_average_precision_binary", lambda *args: 1.0)
    summary1, payload1 = _tiny_train(tmp_path, name="one_epoch", epochs=1)
    values = iter([1.0, 0.0])
    monkeypatch.setattr(mod, "_average_precision_binary", lambda *args: next(values))
    summary2, payload2 = _tiny_train(tmp_path, name="two_epochs", epochs=2)
    assert summary1["best"]["epoch"] == summary2["best"]["epoch"] == 1
    for key, value in payload1["state_dict"].items():
        assert torch.equal(value, payload2["state_dict"][key]), key


def test_force_labels_do_not_train_the_unused_scalar_force_head(tmp_path):
    dataset = tmp_path / "dataset.csv"
    _write_dataset(dataset, rows=40, include_delta_energy=True)
    with dataset.open() as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        row["delta_force"] = "0.01"
    with dataset.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    summary, payload = _tiny_train(tmp_path)
    assert summary["delta_force_label_rows"] == 40
    assert summary["delta_force_head_trained"] is False
    assert summary["delta_force_head_supervised"] is False
    assert summary["production_checkpoint_ready"] is False
    assert "delta_force" not in payload["output_fields"]


def test_zero_energy_is_not_replaced_by_a_refinement_proxy():
    row = {"raw_score": 0, "is_binder": 1, "delta_score": 0,
           "delta_energy": 0, "refine_tier_label": 20, "refine_confidence": 0}
    _, _, _, energy, mask, features = mod._matrix([row], [], [])
    assert energy.tolist() == [0.0]
    assert mask.tolist() == [1.0]
    assert "refine_confidence" in features


def test_validation_only_energy_labels_do_not_claim_the_energy_head_was_trained(tmp_path):
    dataset = tmp_path / "dataset.csv"
    _write_dataset(dataset, rows=40, include_delta_energy=True)
    with dataset.open() as handle:
        rows = list(csv.DictReader(handle))
    train, _ = mod._split_indices(rows, 42, 0.5)
    for index in train:
        rows[index]["delta_energy"] = ""
    with dataset.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    summary, _ = _tiny_train(tmp_path, train_ratio=0.5)
    assert summary["delta_energy_label_rows"] == 20
    assert summary["delta_energy_train_label_rows"] == 0
    assert summary["delta_energy_head_trained"] is False


def test_one_training_row_has_finite_normalization_and_undefined_auc_is_labeled(tmp_path):
    summary, payload = _tiny_train(tmp_path, rows=2, train_ratio=0.5)
    assert summary["train_rows"] == 1
    assert torch.isfinite(payload["x_std"]).all()
    assert summary["best"]["roc_auc_defined"] is False


@pytest.mark.parametrize("epochs", [0, -1, True, 1.5])
def test_invalid_epoch_count_never_creates_a_checkpoint(tmp_path, epochs):
    with pytest.raises(ValueError, match="epochs"):
        _tiny_train(tmp_path, epochs=epochs)
    assert not (tmp_path / "model.pt").exists()


@pytest.mark.parametrize("field,value", [
    ("is_binder", 0.5), ("is_binder", "bad"), ("delta_score", ""),
    ("delta_score", "inf"), ("raw_score", None), ("raw_score", "nan"),
])
def test_invalid_mandatory_training_values_do_not_become_zero(field, value):
    row = {"raw_score": 0, "is_binder": 1, "delta_score": 0}
    row[field] = value
    with pytest.raises(ValueError):
        mod._matrix([row], [], [])


def test_repeated_target_ligand_observations_stay_in_one_split():
    rows = [{"target": "T", "ligand_id": f"L{index // 3}"} for index in range(30)]
    train, val = mod._split_indices(rows, 42, 0.8)
    assert len(train) + len(val) == len(rows)
    assert not ({rows[i]["ligand_id"] for i in train} & {rows[i]["ligand_id"] for i in val})
    assert (train, val) == mod._split_indices(rows, 42, 0.8)


def test_role_is_not_a_feature_and_validation_only_vocab_is_not_fitted(tmp_path):
    summary, payload = _tiny_train(tmp_path)
    assert not any(name.startswith("role=") for name in payload["feature_names"])
    assert summary["role_feature_used"] is False
    assert payload["roles"] == []


def test_legacy_or_tampered_training_cache_cannot_be_skipped(tmp_path):
    summary, _ = _tiny_train(tmp_path)
    dataset, checkpoint = tmp_path / "dataset.csv", tmp_path / "model.pt"
    output, fingerprint = tmp_path / "summary.json", tmp_path / "fingerprint.json"
    kwargs = dict(input_csv=str(dataset), force_derivation_json="/dev/null", epochs=2,
                  hidden_dim=4, batch_size=4, lr=1e-3, weight_decay=1e-5, train_ratio=0.8, seed=42)
    mod.write_train_fingerprint(fingerprint, mod.build_train_fingerprint(**kwargs))
    output.write_text(json.dumps(summary))
    skip_kwargs = dict(kwargs, out_checkpoint=str(checkpoint), out_json=str(output), fingerprint_json=str(fingerprint))
    assert mod.try_skip_training(**skip_kwargs) is not None
    output.write_text(json.dumps(dict(summary, trainer_revision="legacy")))
    assert mod.try_skip_training(**skip_kwargs) is None
    output.write_text(json.dumps(summary))
    checkpoint.write_bytes(b"not the measured checkpoint")
    assert mod.try_skip_training(**skip_kwargs) is None


@pytest.mark.parametrize("key,value", [("prior_rank_proxy", 0.0), ("rank_pct", 0), ("prior_rank_proxy", "0.0")])
def test_zero_rank_keeps_the_best_candidate_on_full_trajectory(key, value):
    row = {key: value}
    trajectories, summary = router.apply_stage2_skip_router([row])
    assert len(trajectories) == 1
    assert summary["stage2_skip_count"] == 0
    assert summary["routed_rows"][0]["stage2_prior_rank_proxy"] == 0
    assert row == {key: value}


@pytest.mark.parametrize("rank", [None, "", "  "])
def test_missing_primary_rank_uses_secondary_zero(rank):
    rows, _ = router.apply_stage2_skip_router([{"prior_rank_proxy": rank, "rank_pct": 0.0}])
    assert len(rows) == 1


@pytest.mark.parametrize("rank", [float("nan"), float("inf"), True])
def test_invalid_rank_is_not_an_automatic_skip(rank):
    with pytest.raises(ValueError):
        router.apply_stage2_skip_router([{"prior_rank_proxy": rank}])
