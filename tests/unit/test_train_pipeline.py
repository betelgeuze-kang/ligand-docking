import json
from pathlib import Path

from train import train_pipeline as tp


def test_run_training_pipeline_all_carry_over_checkpoint(tmp_path, monkeypatch):
    out_json = tmp_path / "summary.json"
    out_csv = tmp_path / "summary.csv"
    ckpt_dir = tmp_path / "models"
    initial_ckpt = str(tmp_path / "seed_checkpoint.pth")

    calls = []

    def _mock_single(**kwargs):
        idx = len(calls) + 1
        calls.append(kwargs)
        target = kwargs["target"]
        best_ckpt = str(ckpt_dir / f"{idx:02d}_{target}.pth")
        Path(best_ckpt).parent.mkdir(parents=True, exist_ok=True)
        Path(best_ckpt).write_text("ok", encoding="utf-8")
        return {
            "target": target,
            "mode": "default",
            "checkpoint_loaded": bool(kwargs.get("initial_checkpoint")),
            "checkpoint_load_meta": {"loaded": bool(kwargs.get("initial_checkpoint"))},
            "best_checkpoint_path": best_ckpt,
            "best_val_loss": 0.1 * idx,
            "epochs_trained": 1,
            "test_rmse": 0.2 * idx,
            "test_mae": 0.3 * idx,
        }

    monkeypatch.setattr(tp, "resolve_targets", lambda **kwargs: ["A", "B", "C"])
    monkeypatch.setattr(tp, "_run_single_target_training", _mock_single)

    payload = tp.run_training_pipeline(
        target="all",
        use_hp_search=False,
        schedule="defined",
        seed=7,
        data_source="distilled",
        distilled_manifest="runs/dummy.csv",
        distilled_split_col="generalization_split",
        initial_checkpoint=initial_ckpt,
        carry_over_checkpoint=True,
        checkpoint_dir=str(ckpt_dir),
        curriculum_summary_json=str(out_json),
        curriculum_summary_csv=str(out_csv),
        run_tag="carry",
    )

    assert payload["target_mode"] == "all"
    assert len(payload["targets"]) == 3
    assert calls[0]["initial_checkpoint"] == initial_ckpt
    assert calls[1]["initial_checkpoint"].endswith("01_A.pth")
    assert calls[2]["initial_checkpoint"].endswith("02_B.pth")
    assert calls[0]["distilled_split_col"] == "generalization_split"
    assert out_json.exists()
    assert out_csv.exists()

    saved = json.loads(out_json.read_text(encoding="utf-8"))
    assert saved["summary"]["targets"] == 3
    csv_lines = out_csv.read_text(encoding="utf-8").strip().splitlines()
    assert len(csv_lines) == 4  # header + 3 rows


def test_run_training_pipeline_all_without_carry_over_uses_base_checkpoint(tmp_path, monkeypatch):
    ckpt_dir = tmp_path / "models"
    initial_ckpt = str(tmp_path / "seed_checkpoint.pth")
    calls = []

    def _mock_single(**kwargs):
        calls.append(kwargs)
        target = kwargs["target"]
        return {
            "target": target,
            "mode": "default",
            "checkpoint_loaded": bool(kwargs.get("initial_checkpoint")),
            "checkpoint_load_meta": {"loaded": bool(kwargs.get("initial_checkpoint"))},
            "best_checkpoint_path": str(ckpt_dir / f"{target}.pth"),
            "best_val_loss": 0.1,
            "epochs_trained": 1,
            "test_rmse": 0.2,
            "test_mae": 0.3,
        }

    monkeypatch.setattr(tp, "resolve_targets", lambda **kwargs: ["A", "B"])
    monkeypatch.setattr(tp, "_run_single_target_training", _mock_single)

    tp.run_training_pipeline(
        target="all",
        use_hp_search=False,
        schedule="defined",
        data_source="hdf5",
        initial_checkpoint=initial_ckpt,
        carry_over_checkpoint=False,
        checkpoint_dir=str(ckpt_dir),
        run_tag="nocarry",
    )

    assert len(calls) == 2
    assert calls[0]["initial_checkpoint"] == initial_ckpt
    assert calls[1]["initial_checkpoint"] == initial_ckpt


def test_run_training_pipeline_single_forwards_distilled_split_col(tmp_path, monkeypatch):
    out_json = tmp_path / "single.json"
    out_csv = tmp_path / "single.csv"
    captured = {}

    def _mock_single(**kwargs):
        captured.update(kwargs)
        return {
            "target": kwargs["target"],
            "mode": "default",
            "checkpoint_loaded": False,
            "checkpoint_load_meta": {"loaded": False},
            "best_checkpoint_path": str(tmp_path / "best.pth"),
            "best_val_loss": 0.12,
            "epochs_trained": 2,
            "test_rmse": 0.21,
            "test_mae": 0.09,
        }

    monkeypatch.setattr(tp, "_run_single_target_training", _mock_single)

    payload = tp.run_training_pipeline(
        target="Chignolin",
        use_hp_search=False,
        data_source="distilled",
        distilled_manifest="runs/manifest.csv",
        distilled_split_col="generalization_split",
        initial_checkpoint="",
        checkpoint_dir=str(tmp_path / "models"),
        curriculum_summary_json=str(out_json),
        curriculum_summary_csv=str(out_csv),
        run_tag="single",
    )

    assert payload["target_mode"] == "single"
    assert captured["distilled_split_col"] == "generalization_split"
    assert captured["target"] == "Chignolin"
    assert out_json.exists()
    assert out_csv.exists()
