from __future__ import annotations

from pathlib import Path

from betelgeuze_product.public_benchmark_materialization import build_public_benchmark_materialization_manifest


def test_public_benchmark_materialization_blocks_missing_artifacts(tmp_path: Path) -> None:
    payload = build_public_benchmark_materialization_manifest(
        suite_id="protein_protein_docking_benchmark_v5",
        dataset_artifact=tmp_path / "dataset",
        result_artifact=tmp_path / "results.csv",
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_public_benchmark_materialization"
    assert "dataset_artifact_missing" in summary["blockers"]
    assert "result_artifact_missing" in summary["blockers"]
    assert summary["primary_metric"] == "dockq_acceptable_rate"
    assert summary["primary_metric_threshold"] == 0.2
    assert "--suite-id protein_protein_docking_benchmark_v5" in summary["run_command"]
    assert summary["download_executed"] is False


def test_public_benchmark_materialization_ready_with_local_artifacts(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    results = tmp_path / "results.csv"
    results.write_text("target,dockq_acceptable_rate\ncomplex1,0.25\n", encoding="utf-8")

    payload = build_public_benchmark_materialization_manifest(
        suite_id="protein_protein_docking_benchmark_v5",
        dataset_artifact=dataset,
        result_artifact=results,
    )

    summary = payload["summary"]
    assert summary["status"] == "public_benchmark_materialization_ready"
    assert summary["materialized"] is True
    assert summary["result_row_count"] == 1
    assert summary["scorecard_run_command_template"].startswith("python3 tools/build_public_benchmark_suite_scorecard.py")
    assert all(row["status"] == "pass" for row in payload["rows"])
