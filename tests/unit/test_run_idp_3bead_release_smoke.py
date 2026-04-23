import json
from pathlib import Path

from tools import run_idp_3bead_release_smoke as smoke


def test_build_smoke_baseline_manifest_filters_and_reindexes(tmp_path):
    baseline_manifest = tmp_path / "baseline_manifest.json"
    baseline_manifest.write_text(
        json.dumps(
            {
                "release_label": "baseline_release",
                "acceptance": {
                    "pass": True,
                    "all_fold_pass": True,
                    "combined_gate_pass": True,
                    "fold_count": 3,
                    "baseline_pass_folds": 3,
                    "corrected_pass_folds": 3,
                },
                "fold_artifacts": [
                    {"fold_index": 1, "holdout": "alpha_synuclein_full", "baseline_gate_pass": True, "corrected_gate_pass": True},
                    {"fold_index": 2, "holdout": "tau_2n4r_fragment", "baseline_gate_pass": True, "corrected_gate_pass": True},
                    {"fold_index": 3, "holdout": "ews_lcd", "baseline_gate_pass": True, "corrected_gate_pass": True},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    out_json = tmp_path / "smoke_baseline_manifest.json"
    payload = smoke._build_smoke_baseline_manifest(
        str(baseline_manifest),
        holdouts=["tau_2n4r_fragment", "ews_lcd"],
        out_json=str(out_json),
    )

    assert payload["release_kind"] == "idp_3bead_smoke_baseline"
    assert payload["release_label"] == "baseline_release_smoke"
    assert payload["acceptance"]["fold_count"] == 2
    assert payload["acceptance"]["corrected_pass_folds"] == 2
    assert [row["holdout"] for row in payload["fold_artifacts"]] == ["tau_2n4r_fragment", "ews_lcd"]
    assert [row["fold_index"] for row in payload["fold_artifacts"]] == [1, 2]
    assert [row["source_fold_index"] for row in payload["fold_artifacts"]] == [2, 3]
    assert out_json.exists()


def test_run_smoke_uses_full_baseline_for_frozen_labels_and_smoke_baseline_for_regression(tmp_path, monkeypatch):
    config_json = tmp_path / "config.json"
    config_json.write_text(
        json.dumps(
            {
                "targets": [
                    {"name": "a1", "split_group": "alpha_synuclein_full"},
                    {"name": "t1", "split_group": "tau_2n4r_fragment"},
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    baseline_manifest_json = tmp_path / "baseline_manifest.json"
    baseline_manifest_json.write_text(
        json.dumps(
            {
                "release_label": "baseline_release",
                "fold_artifacts": [
                    {"fold_index": 1, "holdout": "alpha_synuclein_full", "baseline_gate_pass": True, "corrected_gate_pass": True},
                    {"fold_index": 10, "holdout": "tau_2n4r_fragment", "baseline_gate_pass": True, "corrected_gate_pass": True},
                ],
                "acceptance": {
                    "pass": True,
                    "all_fold_pass": True,
                    "combined_gate_pass": True,
                    "fold_count": 2,
                    "baseline_pass_folds": 2,
                    "corrected_pass_folds": 2,
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    captured = {}

    def _fake_run(cmd):
        captured["cmd"] = list(cmd)
        out_prefix = str(tmp_path / "smoke")
        summary_json = f"{out_prefix}_summary.json"
        regression_json = f"{out_prefix}_release_regression.json"
        candidate_eval_json = f"{out_prefix}_release_candidate_eval.json"
        Path(summary_json).write_text(
            json.dumps({"pass": True, "all_fold_pass": True, "corrected_pass_folds": 2, "fold_count": 2}, ensure_ascii=False),
            encoding="utf-8",
        )
        Path(regression_json).write_text(
            json.dumps({"summary": {"pass": True, "failure_count": 0}}, ensure_ascii=False),
            encoding="utf-8",
        )
        Path(candidate_eval_json).write_text(
            json.dumps({"recommendation": {"decision": "keep_baseline_insufficient_gain"}}, ensure_ascii=False),
            encoding="utf-8",
        )
        return {"cmd": list(cmd), "rc": 0, "stdout_tail": "", "stderr_tail": ""}

    monkeypatch.setattr(smoke, "_run", _fake_run)

    parser = smoke.build_parser()
    args = parser.parse_args(
        [
            "--config-json",
            str(config_json),
            "--baseline-manifest-json",
            str(baseline_manifest_json),
            "--holdouts",
            "alpha_synuclein_full,tau_2n4r_fragment",
            "--device",
            "cpu",
            "--out-prefix",
            str(tmp_path / "smoke"),
        ]
    )

    payload = smoke.run_smoke(args)

    cmd = captured["cmd"]
    assert "--baseline-manifest-json" in cmd
    assert "--frozen-labels-manifest-json" in cmd
    baseline_idx = cmd.index("--baseline-manifest-json")
    frozen_idx = cmd.index("--frozen-labels-manifest-json")
    assert cmd[baseline_idx + 1].endswith("_baseline_manifest.json")
    assert cmd[frozen_idx + 1] == str(baseline_manifest_json)
    assert payload["pass"] is True
    assert payload["smoke_baseline_acceptance"]["fold_count"] == 2
    assert payload["smoke_holdouts"] == ["alpha_synuclein_full", "tau_2n4r_fragment"]


def test_run_smoke_respects_explicit_frozen_labels_manifest(tmp_path, monkeypatch):
    config_json = tmp_path / "config.json"
    config_json.write_text(
        json.dumps({"targets": [{"name": "a1", "split_group": "alpha_synuclein_full"}]}, ensure_ascii=False),
        encoding="utf-8",
    )
    baseline_manifest_json = tmp_path / "smoke_baseline_source.json"
    baseline_manifest_json.write_text(
        json.dumps(
            {
                "release_label": "smoke_source",
                "fold_artifacts": [
                    {"fold_index": 1, "holdout": "alpha_synuclein_full", "baseline_gate_pass": True, "corrected_gate_pass": True}
                ],
                "acceptance": {"pass": True, "all_fold_pass": True, "combined_gate_pass": True, "fold_count": 1, "baseline_pass_folds": 1, "corrected_pass_folds": 1},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    frozen_manifest_json = tmp_path / "release_manifest_current.json"
    frozen_manifest_json.write_text(json.dumps({"release_label": "current_release"}, ensure_ascii=False), encoding="utf-8")

    captured = {}

    def _fake_run(cmd):
        captured["cmd"] = list(cmd)
        out_prefix = str(tmp_path / "smoke")
        Path(f"{out_prefix}_summary.json").write_text(
            json.dumps({"pass": True, "all_fold_pass": True, "corrected_pass_folds": 1, "fold_count": 1}, ensure_ascii=False),
            encoding="utf-8",
        )
        Path(f"{out_prefix}_release_regression.json").write_text(
            json.dumps({"summary": {"pass": True, "failure_count": 0}}, ensure_ascii=False),
            encoding="utf-8",
        )
        Path(f"{out_prefix}_release_candidate_eval.json").write_text(
            json.dumps({"recommendation": {"decision": "keep_baseline_insufficient_gain"}}, ensure_ascii=False),
            encoding="utf-8",
        )
        return {"cmd": list(cmd), "rc": 0, "stdout_tail": "", "stderr_tail": ""}

    monkeypatch.setattr(smoke, "_run", _fake_run)

    args = smoke.build_parser().parse_args(
        [
            "--config-json",
            str(config_json),
            "--baseline-manifest-json",
            str(baseline_manifest_json),
            "--frozen-labels-manifest-json",
            str(frozen_manifest_json),
            "--holdouts",
            "alpha_synuclein_full",
            "--device",
            "cpu",
            "--out-prefix",
            str(tmp_path / "smoke"),
        ]
    )
    smoke.run_smoke(args)
    cmd = captured["cmd"]
    assert cmd[cmd.index("--baseline-manifest-json") + 1].endswith("_baseline_manifest.json")
    assert cmd[cmd.index("--frozen-labels-manifest-json") + 1] == str(frozen_manifest_json)
