from __future__ import annotations

import json
import subprocess
from pathlib import Path

from tools.product import build_casp16_ligand_materialization_manifest as mod


def test_casp16_ligand_materialization_blocks_missing_inputs(tmp_path: Path) -> None:
    payload = mod.build_casp16_ligand_materialization_manifest(
        source_manifest_csv=tmp_path / "missing_source_manifest.csv",
        checksum_manifest=tmp_path / "missing_checksums.sha256",
        root=tmp_path,
    )
    summary = payload["summary"]

    assert summary["status"] == "blocked_casp16_ligand_materialization"
    assert summary["materialization_ready"] is False
    assert "source_manifest_csv_missing" in summary["blockers"]
    assert "checksum_manifest_missing" in summary["blockers"]
    assert summary["download_executed"] is False
    assert summary["external_state_mutated"] is False
    assert summary["claim_promotion_allowed"] is False


def test_casp16_ligand_materialization_ready_with_source_and_checksum_manifests(
    tmp_path: Path,
) -> None:
    source_manifest = tmp_path / "data/competition_benchmarks/casp16_ligand/source_manifest.csv"
    checksum_manifest = source_manifest.parent / "checksums.sha256"
    source_manifest.parent.mkdir(parents=True)
    source_manifest.write_text(
        "target_id,source_url,sha256\n"
        "L1001,operator://casp16/L1001,abc123\n",
        encoding="utf-8",
    )
    checksum_manifest.write_text("abc123  external/casp16/L1001/source.csv\n", encoding="utf-8")

    payload = mod.build_casp16_ligand_materialization_manifest(
        source_manifest_csv=source_manifest,
        checksum_manifest=checksum_manifest,
        root=tmp_path,
    )
    summary = payload["summary"]

    assert summary["status"] == "casp16_ligand_materialization_ready"
    assert summary["materialization_ready"] is True
    assert summary["blockers"] == []
    assert summary["source_manifest_row_count"] == 1
    assert summary["checksum_manifest_line_count"] == 1
    assert summary["raw_data_committed"] is False
    assert summary["raw_data_git_tracked_file_count"] == 0
    assert all(row["status"] == "pass" for row in payload["rows"])


def test_casp16_ligand_materialization_blocks_tracked_raw_data(tmp_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    source_manifest = tmp_path / "data/competition_benchmarks/casp16_ligand/source_manifest.csv"
    checksum_manifest = source_manifest.parent / "checksums.sha256"
    raw_structure = source_manifest.parent / "target_raw.pdb"
    source_manifest.parent.mkdir(parents=True)
    source_manifest.write_text(
        "target_id,source_url,sha256\n"
        "L1001,operator://casp16/L1001,abc123\n",
        encoding="utf-8",
    )
    checksum_manifest.write_text("abc123  external/casp16/L1001/source.csv\n", encoding="utf-8")
    raw_structure.write_text("ATOM      1  N   GLY A   1      0.0 0.0 0.0\n", encoding="utf-8")
    subprocess.run(["git", "add", str(raw_structure)], cwd=tmp_path, check=True, capture_output=True)

    payload = mod.build_casp16_ligand_materialization_manifest(
        source_manifest_csv=source_manifest,
        checksum_manifest=checksum_manifest,
        root=tmp_path,
    )
    summary = payload["summary"]

    assert summary["status"] == "blocked_casp16_ligand_materialization"
    assert summary["materialization_ready"] is False
    assert summary["raw_data_committed"] is True
    assert summary["raw_data_git_tracked_file_count"] == 1
    assert summary["raw_data_git_tracked_sample_paths"] == [
        "data/competition_benchmarks/casp16_ligand/target_raw.pdb"
    ]
    assert "raw_data_committed_in_repo" in summary["blockers"]


def test_casp16_ligand_materialization_cli_writes_outputs(tmp_path: Path) -> None:
    source_manifest = tmp_path / "source_manifest.csv"
    checksum_manifest = tmp_path / "checksums.sha256"
    out_json = tmp_path / "materialization_manifest.json"
    out_csv = tmp_path / "materialization_manifest.csv"
    out_md = tmp_path / "materialization_manifest.md"
    source_manifest.write_text(
        "target_id,source_url,sha256\n"
        "L1001,operator://casp16/L1001,abc123\n",
        encoding="utf-8",
    )
    checksum_manifest.write_text("abc123  external/casp16/L1001/source.csv\n", encoding="utf-8")

    assert mod.main(
        [
            "--source-manifest-csv",
            str(source_manifest),
            "--checksum-manifest",
            str(checksum_manifest),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    ) == 0

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["packet_type"] == "casp16_ligand_materialization_manifest"
    assert out_csv.read_text(encoding="utf-8").startswith("check,status,observed,required")
    assert "CASP16 Ligand Materialization Manifest" in out_md.read_text(encoding="utf-8")


def test_casp16_ligand_materialization_defaults_to_current_runs_receipts() -> None:
    assert mod.DEFAULT_OUT_JSON == "runs/casp16_ligand_materialization_manifest_current.json"
    assert mod.DEFAULT_OUT_CSV == "runs/casp16_ligand_materialization_manifest_current.csv"
    assert mod.DEFAULT_OUT_MD == "runs/casp16_ligand_materialization_manifest_current.md"
