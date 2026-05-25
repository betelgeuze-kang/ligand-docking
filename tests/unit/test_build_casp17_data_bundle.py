from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_build_casp17_data_bundle_mirrors_runs_docs_and_config(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    docs = tmp_path / "docs"
    config = tmp_path / "config"
    (runs / "casp17_packet_current").mkdir(parents=True)
    (runs / "casp17_packet_current" / "packet.json").write_text('{"ok": true}\n', encoding="utf-8")
    (runs / "casp17_summary_current.json").write_text('{"summary": {}}\n', encoding="utf-8")
    (runs / "not_casp17.json").write_text("{}\n", encoding="utf-8")
    docs.mkdir(parents=True)
    (docs / "casp17_note.md").write_text("# CASP17\n", encoding="utf-8")
    (docs / "other.md").write_text("# Other\n", encoding="utf-8")
    config.mkdir(parents=True)
    (config / "casp17_target_template.csv").write_text("target_id,sequence\n", encoding="utf-8")
    (config / "other_template.csv").write_text("name\n", encoding="utf-8")

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_casp17_data_bundle.py"),
            "--runs-dir",
            str(runs),
            "--docs-dir",
            str(docs),
            "--config-dir",
            str(config),
            "--out-dir",
            str(tmp_path / "casp17"),
            "--out-json",
            str(tmp_path / "casp17/manifest.json"),
            "--out-csv",
            str(tmp_path / "casp17/manifest.csv"),
            "--out-md",
            str(tmp_path / "casp17/README.md"),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads((tmp_path / "casp17/manifest.json").read_text(encoding="utf-8"))
    summary = payload["summary"]
    names = {row["name"] for row in payload["rows"]}

    assert summary["bundle_status"] == "ready"
    assert summary["runs_artifact_count"] == 2
    assert summary["docs_artifact_count"] == 1
    assert summary["config_artifact_count"] == 1
    assert "casp17_packet_current" in names
    assert "casp17_summary_current.json" in names
    assert "casp17_note.md" in names
    assert "casp17_target_template.csv" in names
    assert "not_casp17.json" not in names
    assert "other_template.csv" not in names
    assert (tmp_path / "casp17/runs/casp17_packet_current/packet.json").exists()
    assert (tmp_path / "casp17/runs/casp17_summary_current.json").exists()
    assert (tmp_path / "casp17/docs/casp17_note.md").exists()
    assert (tmp_path / "casp17/config/casp17_target_template.csv").exists()
    assert "Local CASP17 data mirror only" in (tmp_path / "casp17/README.md").read_text(encoding="utf-8")


def test_build_casp17_data_bundle_manifest_only_does_not_copy(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    docs = tmp_path / "docs"
    config = tmp_path / "config"
    runs.mkdir()
    docs.mkdir()
    config.mkdir()
    (runs / "casp17_packet_current.json").write_text("{}\n", encoding="utf-8")
    (docs / "casp17_note.md").write_text("# CASP17\n", encoding="utf-8")

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_casp17_data_bundle.py"),
            "--runs-dir",
            str(runs),
            "--docs-dir",
            str(docs),
            "--config-dir",
            str(config),
            "--out-dir",
            str(tmp_path / "casp17"),
            "--manifest-only",
            "--out-json",
            str(tmp_path / "casp17/manifest.json"),
            "--out-csv",
            str(tmp_path / "casp17/manifest.csv"),
            "--out-md",
            str(tmp_path / "casp17/README.md"),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads((tmp_path / "casp17/manifest.json").read_text(encoding="utf-8"))

    assert payload["summary"]["bundle_status"] == "blocked"
    assert payload["summary"]["missing_bundle_count"] == 2
    assert not (tmp_path / "casp17/runs/casp17_packet_current.json").exists()
    assert (tmp_path / "casp17/README.md").exists()
