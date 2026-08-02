from __future__ import annotations

import json
import subprocess
from pathlib import Path

from tools import build_casp16_ligand_source_manifest as mod


def test_casp16_ligand_source_manifest_blocks_without_local_receipts(tmp_path: Path) -> None:
    out_json = tmp_path / "manifest.json"
    out_csv = tmp_path / "manifest.csv"
    out_md = tmp_path / "manifest.md"
    source_template = tmp_path / "operator_source_manifest_template.csv"
    checksum_template = tmp_path / "operator_checksums_template.sha256"
    scorecard_template = tmp_path / "operator_scorecard_rows_template.csv"
    fill_in_md = tmp_path / "operator_fill_in.md"

    mod.main(
        [
            "--local-source-manifest-csv",
            str(tmp_path / "missing_source_manifest.csv"),
            "--local-checksum-manifest",
            str(tmp_path / "missing_checksums.sha256"),
            "--local-materialization-manifest",
            str(tmp_path / "missing_materialization.json"),
            "--scorecard-json",
            str(tmp_path / "missing_scorecard.json"),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
            "--operator-source-manifest-template-csv",
            str(source_template),
            "--operator-checksum-manifest-template",
            str(checksum_template),
            "--operator-scorecard-rows-template-csv",
            str(scorecard_template),
            "--operator-fill-in-md",
            str(fill_in_md),
        ]
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    summary = payload["summary"]
    assert summary["status"] == "blocked_casp16_ligand_competition_credibility"
    assert summary["source_manifest_ready"] is True
    assert summary["materialization_ready"] is False
    assert summary["scorecard_ready"] is False
    assert summary["pharma_pose_ligand_target_count"] == 233
    assert summary["pharma_affinity_ligand_target_count"] == 140
    assert summary["download_executed"] is False
    assert summary["external_state_mutated"] is False
    assert summary["operator_input_schema_ready"] is True
    assert summary["operator_templates_written"] is True
    assert summary["source_manifest_required_columns"] == ["target_id", "source_url", "sha256"]
    assert summary["scorecard_required_columns"] == [
        "target_id",
        "task_type",
        "metric_name",
        "metric_value",
        "result_source",
    ]
    assert summary["operator_source_manifest_template_csv"] == str(source_template)
    assert summary["operator_checksum_manifest_template"] == str(checksum_template)
    assert summary["operator_scorecard_rows_template_csv"] == str(scorecard_template)
    assert summary["operator_receipt_fill_in_md"] == str(fill_in_md)
    assert "tools/build_casp16_ligand_materialization_manifest.py" in summary[
        "materialization_command_template"
    ]
    assert "runs/casp16_ligand_materialization_manifest_current.json" in summary[
        "materialization_command_template"
    ]
    assert "tools/build_casp16_ligand_scorecard.py" in summary[
        "scorecard_run_command_template"
    ]
    assert "runs/casp16_ligand_materialization_manifest_current.json" in summary[
        "scorecard_run_command_template"
    ]
    assert "--scorecard-rows-csv OPERATOR_REVIEWED_SCORECARD_ROWS_CSV" in summary[
        "scorecard_run_command_template"
    ]
    assert "local_source_manifest_csv_missing" in summary["blockers"]
    assert source_template.read_text(encoding="utf-8") == "target_id,source_url,sha256\n"
    assert checksum_template.read_text(encoding="utf-8").startswith(
        "# CASP16 ligand checksum manifest template."
    )
    assert scorecard_template.read_text(encoding="utf-8").startswith(
        "target_id,task_type,metric_name,metric_value,result_source\n"
    )
    assert "Do not copy raw CASP16 ligand structures" in fill_in_md.read_text(
        encoding="utf-8"
    )
    assert "https://predictioncenter.org/casp16/index.cgi?page=format" in out_md.read_text(encoding="utf-8")
    assert out_csv.read_text(encoding="utf-8").startswith("source_id,source_kind,")


def test_casp16_ligand_source_manifest_accepts_operator_receipts(tmp_path: Path) -> None:
    local_manifest = tmp_path / "source_manifest.csv"
    checksum_manifest = tmp_path / "checksums.sha256"
    materialization = tmp_path / "materialization.json"
    scorecard = tmp_path / "scorecard.json"
    local_manifest.write_text("target_id,source_url,sha256\nL1001,operator://local,abc\n", encoding="utf-8")
    checksum_manifest.write_text("abc  local/source.csv\n", encoding="utf-8")
    materialization.write_text(
        json.dumps({"summary": {"status": "casp16_ligand_materialization_ready"}}) + "\n",
        encoding="utf-8",
    )
    scorecard.write_text(
        json.dumps({"summary": {"status": "casp16_ligand_scorecard_ready"}}) + "\n",
        encoding="utf-8",
    )

    payload = mod.build_casp16_ligand_source_manifest(
        local_source_manifest_csv=local_manifest,
        local_checksum_manifest=checksum_manifest,
        local_materialization_manifest=materialization,
        scorecard_json=scorecard,
    )
    summary = payload["summary"]

    assert summary["status"] == "casp16_ligand_competition_credibility_ready"
    assert summary["competition_credibility_ready"] is True
    assert summary["materialization_ready"] is True
    assert summary["scorecard_ready"] is True
    assert summary["blockers"] == []
    assert summary["raw_data_committed"] is False
    assert summary["raw_data_custody_ready"] is True


def test_casp16_ligand_source_manifest_blocks_tracked_raw_data(tmp_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    local_manifest = tmp_path / "data/competition_benchmarks/casp16_ligand/source_manifest.csv"
    checksum_manifest = local_manifest.parent / "checksums.sha256"
    materialization = local_manifest.parent / "materialization_manifest.json"
    raw_structure = local_manifest.parent / "target_raw.pdb"
    scorecard = tmp_path / "runs/casp16_ligand_scorecard_current.json"
    local_manifest.parent.mkdir(parents=True)
    scorecard.parent.mkdir(parents=True)
    local_manifest.write_text("target_id,source_url,sha256\nL1001,operator://local,abc\n", encoding="utf-8")
    checksum_manifest.write_text("abc  local/source.csv\n", encoding="utf-8")
    raw_structure.write_text("ATOM      1  N   GLY A   1      0.0 0.0 0.0\n", encoding="utf-8")
    materialization.write_text(
        json.dumps({"summary": {"status": "casp16_ligand_materialization_ready"}}) + "\n",
        encoding="utf-8",
    )
    scorecard.write_text(
        json.dumps({"summary": {"status": "casp16_ligand_scorecard_ready"}}) + "\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", str(raw_structure)], cwd=tmp_path, check=True, capture_output=True)

    payload = mod.build_casp16_ligand_source_manifest(
        local_source_manifest_csv=local_manifest,
        local_checksum_manifest=checksum_manifest,
        local_materialization_manifest=materialization,
        scorecard_json=scorecard,
    )
    summary = payload["summary"]

    assert summary["status"] == "blocked_casp16_ligand_competition_credibility"
    assert summary["materialization_ready"] is True
    assert summary["scorecard_ready"] is True
    assert summary["raw_data_committed"] is True
    assert summary["raw_data_custody_ready"] is False
    assert summary["raw_data_git_tracked_file_count"] == 1
    assert summary["raw_data_git_tracked_sample_paths"] == [
        "data/competition_benchmarks/casp16_ligand/target_raw.pdb"
    ]
    assert "raw_data_committed_in_repo" in summary["blockers"]
