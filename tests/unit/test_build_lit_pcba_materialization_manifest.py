from __future__ import annotations

import json
from pathlib import Path

from tools import build_lit_pcba_materialization_manifest as mod


def test_build_lit_pcba_materialization_manifest_tool_writes_outputs(tmp_path: Path) -> None:
    out_json = tmp_path / "manifest.json"
    out_csv = tmp_path / "manifest.csv"
    out_md = tmp_path / "manifest.md"

    mod.main(
        [
            "--archive-path",
            str(tmp_path / "missing.tar.xz"),
            "--extracted-dir",
            str(tmp_path / "missing"),
            "--source-score-csv",
            str(tmp_path / "source_scores.csv"),
            "--source-label-csv",
            str(tmp_path / "source_labels.csv"),
            "--out-scores-csv",
            str(tmp_path / "scores.csv"),
            "--out-labels-csv",
            str(tmp_path / "labels.csv"),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["status"] == "blocked_lit_pcba_materialization"
    assert payload["summary"]["suite_id"] == "lit_pcba_virtual_screening"
    assert payload["summary"]["dataset_record_url"] == "https://zenodo.org/records/4588239"
    assert payload["summary"]["dataset_source_url"] == "https://zenodo.org/records/4588239"
    assert payload["summary"]["run_command"].startswith("python3 tools/build_lit_pcba_materialization_manifest.py")
    assert str(tmp_path / "source_scores.csv") in payload["summary"]["operator_input_artifacts"]
    assert str(tmp_path / "scores.csv") in payload["summary"]["operator_output_artifacts"]
    assert str(tmp_path / "source_scores.csv") in payload["summary"]["missing_input_artifacts"]
    assert str(tmp_path / "scores.csv") in payload["summary"]["missing_output_artifacts"]
    assert out_csv.read_text(encoding="utf-8").startswith("check,status,")
    md_text = out_md.read_text(encoding="utf-8")
    assert "LIT-PCBA Materialization Manifest" in md_text
    assert "operator_input_artifacts" in md_text
