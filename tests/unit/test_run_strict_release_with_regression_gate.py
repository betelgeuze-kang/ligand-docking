import json
from pathlib import Path

import pytest

from tools import run_strict_release_with_regression_gate as e2e_gate


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _base_args(tmp_path: Path):
    baseline = tmp_path / "baseline.json"
    _write_json(
        baseline,
        {
            "summary": {"pass": True},
            "gates": {
                "speed": {"avg_speedup_on_vs_off": 100.0},
                "accuracy_gate": {
                    "avg_e2e_rmse_raw": 0.2,
                    "avg_e2e_rel_rmse_mean_clipped": 1e-7,
                    "avg_neighbor_jaccard": 1.0,
                },
            },
            "artifacts": {"accuracy_external_csv": str(tmp_path / "baseline_acc.csv")},
        },
    )
    (tmp_path / "baseline_acc.csv").write_text(
        "target,avg_rmsd_aligned,avg_rmsd_vs_native_aligned\nChignolin,5.0,0.05\n",
        encoding="utf-8",
    )
    parser = e2e_gate.build_parser()
    return parser.parse_args(
        [
            "--baseline-summary-json",
            str(baseline),
            "--baseline-accuracy-csv",
            str(tmp_path / "baseline_acc.csv"),
            "--regression-out-json",
            str(tmp_path / "regression.json"),
            "--regression-out-csv",
            str(tmp_path / "regression.csv"),
            "--out-json",
            str(tmp_path / "e2e.json"),
        ]
    )


def test_skip_strict_run_uses_provided_candidate(monkeypatch, tmp_path):
    args = _base_args(tmp_path)
    candidate = tmp_path / "candidate.json"
    candidate_acc = tmp_path / "candidate_acc.csv"
    _write_json(candidate, {"summary": {"pass": True}, "gates": {}, "artifacts": {}})
    candidate_acc.write_text(
        "target,avg_rmsd_aligned,avg_rmsd_vs_native_aligned\nChignolin,4.9,0.04\n",
        encoding="utf-8",
    )

    args.skip_strict_run = True
    args.candidate_summary_json = str(candidate)
    args.candidate_accuracy_csv = str(candidate_acc)

    captured = {}

    def _fake_run_check(ns):
        captured["candidate_summary_json"] = ns.candidate_summary_json
        captured["candidate_accuracy_csv"] = ns.candidate_accuracy_csv
        return {"summary": {"pass": True}, "failures": [], "inputs": {}}

    monkeypatch.setattr(e2e_gate.regression_gate, "run_check", _fake_run_check)

    payload = e2e_gate.run_pipeline(args)
    assert payload["summary"]["pass"] is True
    assert captured["candidate_summary_json"] == str(candidate)
    assert captured["candidate_accuracy_csv"] == str(candidate_acc)


def test_runs_strict_release_and_forwards_artifacts(monkeypatch, tmp_path):
    args = _base_args(tmp_path)
    args.skip_strict_run = False

    candidate_summary = tmp_path / "candidate_summary.json"
    candidate_acc = tmp_path / "candidate_acc.csv"
    _write_json(candidate_summary, {"summary": {"pass": True}})
    candidate_acc.write_text(
        "target,avg_rmsd_aligned,avg_rmsd_vs_native_aligned\nChignolin,4.8,0.04\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        e2e_gate.strict_release,
        "run_release",
        lambda _ns: {
            "summary": {"pass": True},
            "artifacts": {
                "summary_json": str(candidate_summary),
                "accuracy_external_csv": str(candidate_acc),
            },
        },
    )

    seen = {}

    def _fake_run_check(ns):
        seen["candidate_summary_json"] = ns.candidate_summary_json
        seen["candidate_accuracy_csv"] = ns.candidate_accuracy_csv
        return {"summary": {"pass": True}, "failures": [], "inputs": {}}

    monkeypatch.setattr(e2e_gate.regression_gate, "run_check", _fake_run_check)

    payload = e2e_gate.run_pipeline(args)
    assert payload["summary"]["strict_run_executed"] is True
    assert seen["candidate_summary_json"] == str(candidate_summary)
    assert seen["candidate_accuracy_csv"] == str(candidate_acc)


def test_main_exits_nonzero_on_regression_fail(monkeypatch, tmp_path):
    args = _base_args(tmp_path)
    candidate = tmp_path / "candidate.json"
    _write_json(candidate, {"summary": {"pass": True}})

    monkeypatch.setattr(
        e2e_gate,
        "run_pipeline",
        lambda _args: {"summary": {"pass": False}},
    )

    with pytest.raises(SystemExit) as exc_info:
        e2e_gate.main(
            [
                "--baseline-summary-json",
                str(tmp_path / "baseline.json"),
                "--skip-strict-run",
                "--candidate-summary-json",
                str(candidate),
            ]
        )
    assert exc_info.value.code == 2

