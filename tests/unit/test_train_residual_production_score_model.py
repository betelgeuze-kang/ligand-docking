from __future__ import annotations

import json
from pathlib import Path

import torch

from tools import train_residual_production_score_model as mod


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
    assert summary["missing_production_output_fields"] == ["delta_energy", "delta_force", "uncertainty"]
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
    assert summary["missing_production_output_fields"] == ["delta_force", "uncertainty"]
    assert checkpoint_payload["delta_energy_head_trained"] is True
    assert "delta_energy" in checkpoint_payload["learned_output_fields"]
    assert "delta_energy" in checkpoint_payload["output_fields"]


def test_train_residual_production_score_model_does_not_infer_force_training_from_derivation(tmp_path: Path) -> None:
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
    assert summary["missing_production_output_fields"] == ["delta_force", "uncertainty"]
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
    out_json.write_text(json.dumps(summary) + "\n", encoding="utf-8")
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
