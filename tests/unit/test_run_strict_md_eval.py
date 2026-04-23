import argparse
import json

import pytest

from tools import run_strict_md_eval as mod


def _args(tmp_path, **overrides):
    data = {
        "manifest_csv": str(tmp_path / "manifest.csv"),
        "label": "proxy_openmm",
        "out_dir": str(tmp_path),
        "date_stamp": "2026-02-14",
        "targets": "all",
        "steps": 10,
        "runs": 1,
        "noise": 0.02,
        "seed_base": 42,
        "md_engine_regex": r"(openmm|amber|gromacs)",
        "expected_target_count": 10,
        "strict_validation": True,
        "require_gap_ready": True,
    }
    data.update(overrides)
    return argparse.Namespace(**data)


def test_run_strict_md_eval_pass(tmp_path, monkeypatch):
    (tmp_path / "manifest.csv").write_text("target,path,engine\n", encoding="utf-8")

    def _fake_validate_md_reference_set(**kwargs):
        return {"summary": {"ready": True, "md_ok_targets": 10}}

    def _fake_run_accuracy_report(_args):
        return {"summary": {"targets": 10, "avg_rmsd_vs_native": 0.2}}

    def _fake_build_gap_report(**kwargs):
        return {"status": {"real_md_comparison_ready": True}}

    monkeypatch.setattr(mod, "validate_md_reference_set", _fake_validate_md_reference_set)
    monkeypatch.setattr(mod, "run_accuracy_report", _fake_run_accuracy_report)
    monkeypatch.setattr(mod, "build_gap_report", _fake_build_gap_report)

    payload = mod.run_strict_md_eval(_args(tmp_path))
    assert payload["checks"]["pass"] is True
    assert payload["checks"]["failed_checks"] == []
    out_path = payload["outputs"]["summary_json"]
    with open(out_path, "r", encoding="utf-8") as f:
        saved = json.load(f)
    assert saved["checks"]["pass"] is True
    assert saved["accuracy_summary"]["avg_rmsd_vs_native"] == 0.2


def test_run_strict_md_eval_fails_when_gap_not_ready(tmp_path, monkeypatch):
    (tmp_path / "manifest.csv").write_text("target,path,engine\n", encoding="utf-8")

    def _fake_validate_md_reference_set(**kwargs):
        return {"summary": {"ready": True}}

    def _fake_run_accuracy_report(_args):
        return {"summary": {"targets": 10}}

    def _fake_build_gap_report(**kwargs):
        return {"status": {"real_md_comparison_ready": False}}

    monkeypatch.setattr(mod, "validate_md_reference_set", _fake_validate_md_reference_set)
    monkeypatch.setattr(mod, "run_accuracy_report", _fake_run_accuracy_report)
    monkeypatch.setattr(mod, "build_gap_report", _fake_build_gap_report)

    with pytest.raises(RuntimeError):
        mod.run_strict_md_eval(_args(tmp_path))


def test_run_strict_md_eval_fails_when_provenance_gate_enabled(tmp_path, monkeypatch):
    (tmp_path / "manifest.csv").write_text("target,path,engine\n", encoding="utf-8")

    def _fake_validate_md_reference_set(**kwargs):
        return {"summary": {"ready": True}}

    def _fake_run_accuracy_report(_args):
        return {"summary": {"targets": 10}}

    def _fake_build_gap_report(**kwargs):
        return {"status": {"real_md_comparison_ready": True}}

    def _fake_validate_md_provenance(**kwargs):
        return {"summary": {"ready": False}}

    monkeypatch.setattr(mod, "validate_md_reference_set", _fake_validate_md_reference_set)
    monkeypatch.setattr(mod, "run_accuracy_report", _fake_run_accuracy_report)
    monkeypatch.setattr(mod, "build_gap_report", _fake_build_gap_report)
    monkeypatch.setattr(mod, "validate_md_provenance", _fake_validate_md_provenance)

    args = _args(
        tmp_path,
        run_provenance_validation=True,
        enforce_provenance_gate=True,
        provenance_require_source_engine=True,
        provenance_require_source_path=False,
        provenance_source_engine_regex=r"(openmm|amber|gromacs)",
        provenance_strict=False,
    )
    with pytest.raises(RuntimeError):
        mod.run_strict_md_eval(args)
