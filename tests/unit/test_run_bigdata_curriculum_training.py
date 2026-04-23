import json
from pathlib import Path

from tools import run_bigdata_curriculum_training as mod


def test_run_bigdata_curriculum_builds_manifest_and_trains(tmp_path, monkeypatch):
    out_json = tmp_path / "summary.json"
    out_manifest = tmp_path / "merged.csv"
    out_manifest_summary = tmp_path / "merged_summary.json"

    calls = {"build": 0, "train": 0}

    def _mock_build(**kwargs):
        calls["build"] += 1
        Path(kwargs["out_manifest_csv"]).parent.mkdir(parents=True, exist_ok=True)
        Path(kwargs["out_manifest_csv"]).write_text("target,split,output_npz\n", encoding="utf-8")
        Path(kwargs["out_summary_json"]).write_text("{}", encoding="utf-8")
        return {"rows_total": 1}

    def _mock_train(**kwargs):
        calls["train"] += 1
        assert kwargs["target"] == "all"
        assert kwargs["data_source"] == "distilled"
        assert kwargs["distilled_manifest"] == str(out_manifest)
        return {"target_mode": "all", "summary": {"targets": 2}}

    monkeypatch.setattr(mod, "build_bigdata_residual_manifest", _mock_build)
    monkeypatch.setattr(mod, "run_training_pipeline", _mock_train)

    parser = mod.build_parser()
    args = parser.parse_args(
        [
            "--targets",
            "all",
            "--base-manifest-csv",
            str(tmp_path / "base.csv"),
            "--hardcase-manifest-csv",
            str(tmp_path / "hard.csv"),
            "--out-merged-manifest-csv",
            str(out_manifest),
            "--out-merged-summary-json",
            str(out_manifest_summary),
            "--out-json",
            str(out_json),
        ]
    )
    payload = mod.run_bigdata_curriculum(args)

    assert calls["build"] == 1
    assert calls["train"] == 1
    assert payload["manifest_built"] is True
    assert out_json.exists()
    saved = json.loads(out_json.read_text(encoding="utf-8"))
    assert saved["training"]["summary"]["targets"] == 2


def test_run_bigdata_curriculum_skip_manifest_build(tmp_path, monkeypatch):
    out_manifest = tmp_path / "merged.csv"
    out_manifest.write_text("target,split,output_npz\n", encoding="utf-8")
    out_manifest_summary = tmp_path / "merged_summary.json"
    out_manifest_summary.write_text("{}", encoding="utf-8")

    called = {"build": False}

    def _mock_build(**kwargs):
        called["build"] = True
        return {"rows_total": 1}

    monkeypatch.setattr(mod, "build_bigdata_residual_manifest", _mock_build)
    monkeypatch.setattr(mod, "run_training_pipeline", lambda **kwargs: {"target_mode": "all"})

    parser = mod.build_parser()
    args = parser.parse_args(
        [
            "--skip-manifest-build",
            "--out-merged-manifest-csv",
            str(out_manifest),
            "--out-merged-summary-json",
            str(out_manifest_summary),
            "--out-json",
            str(tmp_path / "summary.json"),
        ]
    )
    payload = mod.run_bigdata_curriculum(args)
    assert called["build"] is False
    assert payload["manifest_built"] is False


def test_run_bigdata_curriculum_auto_hard_mining_sets_target_weights(tmp_path, monkeypatch):
    out_manifest = tmp_path / "merged.csv"
    out_manifest_summary = tmp_path / "merged_summary.json"
    out_weights = tmp_path / "hard_weights.csv"
    out_summary_json = tmp_path / "hard_summary.json"

    calls = {"hard": 0, "build": 0}

    def _mock_hard(**kwargs):
        calls["hard"] += 1
        Path(kwargs["out_target_weights_csv"]).write_text(
            "target,multiplier,hard_score,selected\nA,2.0,1.0,1\n",
            encoding="utf-8",
        )
        Path(kwargs["out_summary_json"]).write_text("{}", encoding="utf-8")
        return {"summary": {"selected_targets_count": 1}}

    def _mock_build(**kwargs):
        calls["build"] += 1
        assert kwargs["target_weights_csv"] == str(out_weights)
        Path(kwargs["out_manifest_csv"]).write_text("target,split,output_npz\n", encoding="utf-8")
        Path(kwargs["out_summary_json"]).write_text("{}", encoding="utf-8")
        return {"rows_total": 1}

    monkeypatch.setattr(mod, "build_hard_mining_target_weights", _mock_hard)
    monkeypatch.setattr(mod, "build_bigdata_residual_manifest", _mock_build)
    monkeypatch.setattr(mod, "run_training_pipeline", lambda **kwargs: {"target_mode": "all"})

    args = mod.build_parser().parse_args(
        [
            "--targets",
            "A,B",
            "--base-manifest-csv",
            str(tmp_path / "base.csv"),
            "--hardcase-manifest-csv",
            str(tmp_path / "hard.csv"),
            "--out-merged-manifest-csv",
            str(out_manifest),
            "--out-merged-summary-json",
            str(out_manifest_summary),
            "--auto-hard-mining",
            "--hard-mining-ood-pair-csv",
            str(tmp_path / "pair.csv"),
            "--hard-mining-out-target-weights-csv",
            str(out_weights),
            "--hard-mining-out-summary-json",
            str(out_summary_json),
            "--out-json",
            str(tmp_path / "summary.json"),
        ]
    )
    payload = mod.run_bigdata_curriculum(args)
    assert calls["hard"] == 1
    assert calls["build"] == 1
    assert payload["hard_mining_enabled"] is True
    assert payload["artifacts"]["target_weights_csv"] == str(out_weights)


def test_run_bigdata_curriculum_with_empty_hardcase_manifest_uses_base_only(tmp_path, monkeypatch):
    base_manifest = tmp_path / "base.csv"
    hard_manifest = tmp_path / "hard_empty.csv"
    out_manifest = tmp_path / "merged.csv"
    out_summary = tmp_path / "merged_summary.json"
    out_json = tmp_path / "summary.json"

    base_manifest.write_text(
        "target,split,output_npz\nChignolin,train,/tmp/nonexistent_output.npz\n",
        encoding="utf-8",
    )
    hard_manifest.write_text("", encoding="utf-8")
    monkeypatch.setattr(mod, "run_training_pipeline", lambda **kwargs: {"target_mode": "all"})

    args = mod.build_parser().parse_args(
        [
            "--targets",
            "Chignolin",
            "--base-manifest-csv",
            str(base_manifest),
            "--hardcase-manifest-csv",
            str(hard_manifest),
            "--no-skip-missing-output-npz",
            "--out-merged-manifest-csv",
            str(out_manifest),
            "--out-merged-summary-json",
            str(out_summary),
            "--out-json",
            str(out_json),
        ]
    )
    payload = mod.run_bigdata_curriculum(args)
    assert payload["manifest_built"] is True
