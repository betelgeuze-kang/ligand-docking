"""Synthetic cache admission only: checkpoint contents are literal dummy bytes."""

import csv
import hashlib
import json
from pathlib import Path

import pytest

from tools import train_residual_production_score_model as trainer


@pytest.fixture(autouse=True)
def forbid_model_execution(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("model execution is outside this cache admission test")

    monkeypatch.setattr(trainer, "ResidualScoreMLP", forbidden)
    monkeypatch.setattr(trainer.torch, "load", forbidden)
    monkeypatch.setattr(trainer.torch, "save", forbidden)
    monkeypatch.setattr(trainer.torch.optim, "Adam", forbidden)


def _cache(tmp_path, label):
    source = tmp_path / f"{label}.csv"
    with source.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["ligand_id", "raw_score", "is_binder", "delta_score", "role"],
        )
        writer.writeheader()
        writer.writerows(
            {"ligand_id": f"synthetic-{label}-{index}", "raw_score": index + 1,
             "is_binder": index, "delta_score": 0, "role": "fit"}
            for index in range(2)
        )
    receipt = tmp_path / f"{label}.force.json"
    receipt.write_text("{}", encoding="utf-8")
    arguments = {
        "input_csv": str(source), "force_derivation_json": str(receipt),
        "epochs": 2, "hidden_dim": 8, "batch_size": 8, "lr": 1e-3,
        "weight_decay": 1e-5, "train_ratio": 0.8, "seed": 42,
    }
    fingerprint = trainer.build_train_fingerprint(**arguments)
    fingerprint_path = tmp_path / f"{label}.fingerprint.json"
    trainer.write_train_fingerprint(fingerprint_path, fingerprint)
    checkpoint = tmp_path / f"{label}.pt"
    checkpoint.write_bytes(f"synthetic-dummy-cache-bytes-{label}".encode())
    payload = {
        "status": "residual_production_score_model_trained",
        "trainer_contract_version": trainer.TRAINER_CONTRACT_VERSION,
        "production_checkpoint_ready": False,
        "delta_force_head_trained": False,
        "uncertainty_calibrated": False,
        "checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
        "input_csv": str(source), "checkpoint": str(checkpoint), "synthetic_marker": label,
        "train_fingerprint_digest": fingerprint["digest"], "train_fingerprint": fingerprint,
    }
    summary = tmp_path / f"{label}.summary.json"
    summary.write_text(json.dumps(payload), encoding="utf-8")
    return dict(
        **arguments, fingerprint_json=str(fingerprint_path),
        out_checkpoint=str(checkpoint), out_json=str(summary),
    ), payload


def test_same_input_and_outputs_reuse_without_loading_checkpoint(tmp_path):
    arguments, payload = _cache(tmp_path, "A")
    result = trainer.try_skip_training(**arguments)
    assert result == {
        **payload, "training_skipped": True, "training_executed": False,
        "training_skip_reason": "inputs_unchanged",
    }


def test_other_inputs_fingerprint_cannot_relabel_checkpoint_and_summary(tmp_path):
    arguments_a, payload_a = _cache(tmp_path, "A")
    arguments_b, payload_b = _cache(tmp_path, "B")
    assert payload_a["train_fingerprint_digest"] != payload_b["train_fingerprint_digest"]
    arguments_b.update(
        out_checkpoint=arguments_a["out_checkpoint"], out_json=arguments_a["out_json"],
    )
    assert trainer.try_skip_training(**arguments_b) is None


@pytest.mark.parametrize("field", ["train_fingerprint", "train_fingerprint_digest"])
def test_legacy_summary_without_input_binding_is_cache_miss(tmp_path, field):
    arguments, payload = _cache(tmp_path, "A")
    del payload[field]
    Path(arguments["out_json"]).write_text(json.dumps(payload), encoding="utf-8")
    assert trainer.try_skip_training(**arguments) is None


@pytest.mark.parametrize("change", ["digest", "fingerprint", "checkpoint", "receipt", "settings"])
def test_changed_binding_or_output_is_cache_miss(tmp_path, change):
    arguments, payload = _cache(tmp_path, "A")
    if change == "digest":
        payload["train_fingerprint_digest"] = "0" * 64
    elif change == "fingerprint":
        payload["train_fingerprint"]["epochs"] += 1
    elif change == "checkpoint":
        Path(arguments["out_checkpoint"]).write_bytes(b"different-synthetic-dummy-bytes")
    elif change == "receipt":
        Path(arguments["force_derivation_json"]).write_text('{"changed": true}', encoding="utf-8")
    elif change == "settings":
        arguments["epochs"] += 1
    Path(arguments["out_json"]).write_text(json.dumps(payload), encoding="utf-8")
    assert trainer.try_skip_training(**arguments) is None


def test_input_change_during_admission_stops_before_model_creation(tmp_path, monkeypatch):
    arguments, _ = _cache(tmp_path, "A")
    original_load = trainer._load_rows

    def changing_load(path):
        rows = original_load(path)
        source = Path(path)
        source.write_text(source.read_text(encoding="utf-8").replace("synthetic-A", "synthetic-B"), encoding="utf-8")
        return rows

    monkeypatch.setattr(trainer, "_load_rows", changing_load)
    arguments.pop("fingerprint_json")
    arguments.pop("out_json")
    before = Path(arguments["out_checkpoint"]).read_bytes()
    with pytest.raises(ValueError, match="training_inputs_changed_during_load"):
        trainer.train_residual_production_score_model(**arguments)
    assert Path(arguments["out_checkpoint"]).read_bytes() == before


def test_cli_writes_the_trainers_input_binding_without_rehashing_later_input(tmp_path, monkeypatch):
    arguments, payload = _cache(tmp_path, "A")
    original_digest = payload["train_fingerprint_digest"]

    def completed_synthetic_training(**kwargs):
        source = Path(kwargs["input_csv"])
        source.write_text(source.read_text(encoding="utf-8").replace("synthetic-A", "synthetic-B"), encoding="utf-8")
        return payload

    monkeypatch.setattr(trainer, "train_residual_production_score_model", completed_synthetic_training)
    monkeypatch.setattr(trainer, "_write_markdown", lambda *args: None)
    cli_arguments = []
    for key, value in arguments.items():
        option = "train-fingerprint-json" if key == "fingerprint_json" else key.replace("_", "-")
        cli_arguments.extend([f"--{option}", str(value)])
    trainer.main(cli_arguments)
    written = json.loads(Path(arguments["fingerprint_json"]).read_text(encoding="utf-8"))
    assert written == payload["train_fingerprint"]
    assert written["digest"] == original_digest
    assert trainer.try_skip_training(**arguments) is None
