from __future__ import annotations

import json
import subprocess
from pathlib import Path

from tools import build_bm5_capri_complex_source_manifest as mod


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    return path


def _bm5_ready_inputs(tmp_path: Path) -> dict[str, Path]:
    dataset = tmp_path / "data/public_benchmarks/protein_protein_docking_benchmark_v5"
    dataset.mkdir(parents=True)
    materialization = _write_json(
        tmp_path / "runs/protein_protein_docking_benchmark_v5_materialization_manifest_current.json",
        {
            "summary": {
                "suite_id": "protein_protein_docking_benchmark_v5",
                "status": "public_benchmark_materialization_ready",
                "materialized": True,
            }
        },
    )
    provenance = _write_json(
        tmp_path / "runs/protein_protein_docking_benchmark_v5_result_provenance_current.json",
        {
            "summary": {
                "status": "public_benchmark_result_provenance_ready",
                "result_artifact_sha256": "a" * 64,
            }
        },
    )
    scorecard = _write_json(
        tmp_path / "runs/protein_protein_docking_benchmark_v5_scorecard_current.json",
        {
            "summary": {
                "status": "public_benchmark_suite_scorecard_pass",
                "evidence_artifact_sha256": "a" * 64,
            }
        },
    )
    return {
        "bm5_dataset_dir": dataset,
        "bm5_materialization_manifest": materialization,
        "bm5_result_provenance_json": provenance,
        "bm5_scorecard_json": scorecard,
    }


def test_bm5_capri_complex_source_manifest_reports_bm5_ready_capri_blocked(tmp_path: Path) -> None:
    inputs = _bm5_ready_inputs(tmp_path)
    out_json = tmp_path / "manifest.json"
    out_csv = tmp_path / "manifest.csv"
    out_md = tmp_path / "manifest.md"

    mod.main(
        [
            "--bm5-dataset-dir",
            str(inputs["bm5_dataset_dir"]),
            "--bm5-materialization-manifest",
            str(inputs["bm5_materialization_manifest"]),
            "--bm5-result-provenance-json",
            str(inputs["bm5_result_provenance_json"]),
            "--bm5-scorecard-json",
            str(inputs["bm5_scorecard_json"]),
            "--capri-score-set-source-manifest",
            str(tmp_path / "missing_capri_source.csv"),
            "--capri-score-set-checksum-manifest",
            str(tmp_path / "missing_capri_checksums.sha256"),
            "--capri-score-set-materialization-manifest",
            str(tmp_path / "missing_capri_materialization.json"),
            "--capri-score-set-scorecard-json",
            str(tmp_path / "missing_capri_scorecard.json"),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    summary = payload["summary"]
    assert summary["status"] == "blocked_bm5_capri_complex_competition_credibility"
    assert summary["bm5_complex_benchmark_ready"] is True
    assert summary["capri_score_set_ready"] is False
    assert summary["competition_credibility_ready"] is False
    assert summary["small_molecule_ligand_claim_allowed"] is False
    assert "capri_score_set_source_manifest_missing" in summary["blockers"]
    assert "https://zlab.wenglab.org/benchmark/" in out_md.read_text(encoding="utf-8")
    assert out_csv.read_text(encoding="utf-8").startswith("source_id,source_kind,")


def test_bm5_capri_complex_source_manifest_ready_with_operator_capri_receipts(tmp_path: Path) -> None:
    inputs = _bm5_ready_inputs(tmp_path)
    capri_source = tmp_path / "capri/source_manifest.csv"
    capri_checksums = tmp_path / "capri/checksums.sha256"
    capri_source.parent.mkdir(parents=True)
    capri_source.write_text("dataset_id,source_url\ncapri_score_set,operator://local\n", encoding="utf-8")
    capri_checksums.write_text("b  capri/score_set.csv\n", encoding="utf-8")
    capri_materialization = _write_json(
        tmp_path / "capri/materialization.json",
        {"summary": {"status": "capri_score_set_materialization_ready"}},
    )
    capri_scorecard = _write_json(
        tmp_path / "runs/capri_score_set_scorecard_current.json",
        {"summary": {"status": "capri_score_set_scorecard_ready"}},
    )

    payload = mod.build_bm5_capri_complex_source_manifest(
        **inputs,
        capri_score_set_source_manifest=capri_source,
        capri_score_set_checksum_manifest=capri_checksums,
        capri_score_set_materialization_manifest=capri_materialization,
        capri_score_set_scorecard_json=capri_scorecard,
    )
    summary = payload["summary"]

    assert summary["status"] == "bm5_capri_complex_competition_credibility_ready"
    assert summary["competition_credibility_ready"] is True
    assert summary["bm5_complex_benchmark_ready"] is True
    assert summary["capri_score_set_ready"] is True
    assert summary["blockers"] == []
    assert summary["raw_data_committed"] is False
    assert summary["raw_data_custody_ready"] is True


def test_bm5_capri_complex_source_manifest_blocks_tracked_raw_data(tmp_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    inputs = _bm5_ready_inputs(tmp_path)
    raw_structure = inputs["bm5_dataset_dir"] / "structures-matched" / "tracked_raw.pdb"
    raw_structure.parent.mkdir(parents=True)
    raw_structure.write_text("ATOM      1  N   GLY A   1      0.0 0.0 0.0\n", encoding="utf-8")
    subprocess.run(["git", "add", str(raw_structure)], cwd=tmp_path, check=True, capture_output=True)
    capri_source = tmp_path / "capri/source_manifest.csv"
    capri_checksums = tmp_path / "capri/checksums.sha256"
    capri_source.parent.mkdir(parents=True)
    capri_source.write_text("dataset_id,source_url\ncapri_score_set,operator://local\n", encoding="utf-8")
    capri_checksums.write_text("b  capri/score_set.csv\n", encoding="utf-8")
    capri_materialization = _write_json(
        tmp_path / "capri/materialization.json",
        {"summary": {"status": "capri_score_set_materialization_ready"}},
    )
    capri_scorecard = _write_json(
        tmp_path / "runs/capri_score_set_scorecard_current.json",
        {"summary": {"status": "capri_score_set_scorecard_ready"}},
    )

    payload = mod.build_bm5_capri_complex_source_manifest(
        **inputs,
        capri_score_set_source_manifest=capri_source,
        capri_score_set_checksum_manifest=capri_checksums,
        capri_score_set_materialization_manifest=capri_materialization,
        capri_score_set_scorecard_json=capri_scorecard,
    )
    summary = payload["summary"]

    assert summary["status"] == "blocked_bm5_capri_complex_competition_credibility"
    assert summary["bm5_complex_benchmark_ready"] is True
    assert summary["capri_score_set_ready"] is True
    assert summary["raw_data_committed"] is True
    assert summary["raw_data_custody_ready"] is False
    assert summary["raw_data_git_tracked_file_count"] == 1
    assert summary["bm5_raw_data_git_tracked_file_count"] == 1
    assert summary["capri_raw_data_git_tracked_file_count"] == 0
    assert summary["raw_data_git_tracked_sample_paths"] == [
        "data/public_benchmarks/protein_protein_docking_benchmark_v5/structures-matched/tracked_raw.pdb"
    ]
    assert summary["raw_data_custody_plan_json"] == (
        "runs/bm5_capri_raw_data_custody_plan_current.json"
    )
    assert summary["raw_data_custody_plan_csv"] == (
        "runs/bm5_capri_raw_data_custody_plan_current.csv"
    )
    assert summary["raw_data_custody_plan_command"] == (
        "python3 tools/build_bm5_capri_raw_data_custody_plan.py --compute-sha256"
    )
    assert "raw_data_committed_in_repo" in summary["blockers"]
