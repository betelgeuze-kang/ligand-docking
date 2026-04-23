import argparse

import pandas as pd
import pytest

from tools import import_real_md_and_run_gate as mod


def _args(tmp_path, source_manifest: str, **overrides):
    data = {
        "label": "real",
        "date_stamp": "2026-02-15",
        "out_dir": str(tmp_path),
        "base_metadata_csv": str(tmp_path / "base.csv"),
        "template_csv": str(tmp_path / "template.csv"),
        "source_manifest_csv": source_manifest,
        "input_manifest": str(tmp_path / "input.csv"),
        "md_engine_regex": r"(openmm|amber|gromacs)",
        "md_engine_from": "engine",
        "source_engine_from": "engine",
        "source_path_from": "path",
        "source_label_from": "label",
        "note_tag": "REAL_MD_IMPORTED",
        "overwrite_existing_nonempty": False,
        "forbid_proxy_engines": True,
        "targets": "all",
        "steps": 1,
        "runs": 1,
        "noise": 0.02,
        "seed_base": 42,
        "expected_target_count": 1,
    }
    data.update(overrides)
    return argparse.Namespace(**data)


def test_import_real_md_and_run_gate_fails_on_proxy_manifest(tmp_path):
    src = tmp_path / "src.csv"
    pd.DataFrame([{"target": "Chignolin", "engine": "openmm_proxy_external", "path": "/tmp/a.npy"}]).to_csv(
        src, index=False
    )
    (tmp_path / "base.csv").write_text("target,md_engine,source_engine,source_path\nChignolin,,,\n", encoding="utf-8")
    (tmp_path / "template.csv").write_text("target\nChignolin\n", encoding="utf-8")
    (tmp_path / "input.csv").write_text("target,path\nChignolin,/tmp/a.npy\n", encoding="utf-8")

    with pytest.raises(RuntimeError):
        mod.import_real_md_and_run_gate(_args(tmp_path, str(src), forbid_proxy_engines=True))


def test_import_real_md_and_run_gate_pass_with_mocked_pipeline(tmp_path, monkeypatch):
    src = tmp_path / "src.csv"
    pd.DataFrame([{"target": "Chignolin", "engine": "openmm", "path": "/tmp/a.npy", "label": "x"}]).to_csv(
        src, index=False
    )
    (tmp_path / "base.csv").write_text("target,md_engine,source_engine,source_path\nChignolin,,,\n", encoding="utf-8")
    (tmp_path / "template.csv").write_text("target\nChignolin\n", encoding="utf-8")
    (tmp_path / "input.csv").write_text("target,path\nChignolin,/tmp/a.npy\n", encoding="utf-8")

    monkeypatch.setattr(mod, "bootstrap_real_md_metadata", lambda **kwargs: {"summary": {"ok": True}})
    monkeypatch.setattr(mod, "report_real_md_metadata_gaps", lambda **kwargs: {"summary": {"strict_ready": True}})
    monkeypatch.setattr(mod, "prepare_real_md_manifest", lambda **kwargs: {"summary": {"ready": True}})
    monkeypatch.setattr(
        mod,
        "run_strict_md_eval",
        lambda _args: {"checks": {"pass": True}, "accuracy_summary": {"targets": 1}},
    )

    payload = mod.import_real_md_and_run_gate(_args(tmp_path, str(src), forbid_proxy_engines=True))
    assert payload["strict_checks"]["pass"] is True
    assert payload["strict_accuracy_summary"]["targets"] == 1

