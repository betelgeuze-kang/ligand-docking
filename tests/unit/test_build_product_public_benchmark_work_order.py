from __future__ import annotations

import json
from pathlib import Path

from betelgeuze_product.public_benchmark_work_order import build_product_public_benchmark_work_order
from tools import build_product_public_benchmark_work_order as mod


def _blocked_public_benchmark_packet() -> dict:
    return {
        "summary": {
            "status": "blocked_product_public_benchmark_contract",
            "public_benchmark_validation_ready": False,
            "required_suite_count": 2,
            "ready_required_suite_count": 0,
            "blocked_suite_count": 2,
        },
        "rows": [
            {
                "suite_id": "dude_z_decoy_smoke",
                "benchmark_family": "protein_ligand_decoy_screening",
                "status": "blocked",
                "required_for_commercial_release": True,
                "dataset_source_url": "https://dude.docking.org/",
                "materialization_manifest_json": "runs/dude_z_decoy_smoke_materialization_manifest_current.json",
                "scorecard_json": "runs/dude_z_decoy_smoke_scorecard_current.json",
                "primary_metric": "ROC_AUC",
                "primary_metric_value": 0.0,
                "primary_metric_threshold": 0.6,
                "materialization_manifest_status": "blocked_public_benchmark_materialization",
                "materialization_manifest_blockers": "dataset_artifact_missing;result_artifact_missing",
                "scorecard_json_summary_status": "blocked_public_benchmark_suite_scorecard",
                "blockers": "materialization_manifest_not_ready,scorecard_json_status_not_pass",
                "materialization_run_command": "python3 tools/build_public_benchmark_materialization_manifest.py --suite-id dude_z_decoy_smoke",
                "run_command": "python3 tools/build_public_benchmark_suite_scorecard.py --suite-id dude_z_decoy_smoke",
            },
            {
                "suite_id": "casp_archive_structure_regression",
                "benchmark_family": "structure_prediction_regression",
                "status": "blocked",
                "required_for_commercial_release": True,
                "dataset_source_url": "https://predictioncenter.org/",
                "materialization_manifest_json": "runs/casp_archive_structure_regression_materialization_manifest_current.json",
                "scorecard_json": "runs/casp_archive_structure_regression_scorecard_current.json",
                "primary_metric": "target_pass_rate",
                "primary_metric_value": 0.0,
                "primary_metric_threshold": 0.5,
                "materialization_manifest_status": "public_benchmark_materialization_ready",
                "scorecard_json_summary_status": "blocked_public_benchmark_suite_scorecard",
                "blockers": "scorecard_json_status_not_pass,scorecard_status_not_pass",
                "materialization_run_command": "python3 tools/build_public_benchmark_materialization_manifest.py --suite-id casp_archive_structure_regression",
                "run_command": "python3 tools/build_public_benchmark_suite_scorecard.py --suite-id casp_archive_structure_regression",
            },
        ],
    }


def test_product_public_benchmark_work_order_maps_suite_blockers_to_commands() -> None:
    payload = build_product_public_benchmark_work_order(public_benchmark_packet=_blocked_public_benchmark_packet())

    summary = payload["summary"]
    assert summary["status"] == "product_public_benchmark_work_order_ready"
    assert summary["open_suite_count"] == 2
    assert summary["materialization_required_suite_count"] == 1
    assert summary["scorecard_required_suite_count"] == 1
    assert summary["requires_24h_server"] is False
    assert summary["download_executed"] is False
    assert summary["external_state_mutated"] is False
    rows_by_suite = {row["suite_id"]: row for row in payload["rows"]}
    assert rows_by_suite["dude_z_decoy_smoke"]["work_order_status"] == "materialization_required"
    assert rows_by_suite["casp_archive_structure_regression"]["work_order_status"] == "scorecard_required"
    for row in payload["rows"]:
        assert row["materialization_manifest"].startswith("runs/")
        assert row["scorecard_row"].startswith("runs/")
        assert row["threshold"] == row["primary_metric_threshold"]
        assert row["blocker"]
        assert row["run_command"]
    assert "build_public_benchmark_materialization_manifest.py" in rows_by_suite["dude_z_decoy_smoke"]["materialization_command"]
    assert "build_public_benchmark_materialization_manifest.py" in rows_by_suite["dude_z_decoy_smoke"]["run_command"]
    assert "build_public_benchmark_suite_scorecard.py" in rows_by_suite["casp_archive_structure_regression"]["run_command"]
    assert "build_product_public_benchmark_contract.py" in rows_by_suite["dude_z_decoy_smoke"]["refresh_command"]
    assert "build_goal_release_decision_gate.py" in rows_by_suite["dude_z_decoy_smoke"]["refresh_command"]
    assert "build_goal_bottleneck_briefing.py" in rows_by_suite["dude_z_decoy_smoke"]["refresh_command"]


def test_build_product_public_benchmark_work_order_tool_writes_outputs(tmp_path: Path) -> None:
    public_benchmark = tmp_path / "public_benchmark.json"
    public_benchmark.write_text(json.dumps(_blocked_public_benchmark_packet()) + "\n", encoding="utf-8")
    out_json = tmp_path / "work_order.json"
    out_csv = tmp_path / "work_order.csv"
    out_md = tmp_path / "work_order.md"

    mod.main(
        [
            "--public-benchmark-json",
            str(public_benchmark),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["status"] == "product_public_benchmark_work_order_ready"
    csv_text = out_csv.read_text(encoding="utf-8")
    md_text = out_md.read_text(encoding="utf-8")
    assert csv_text.startswith("sequence,suite_id,")
    assert "materialization_manifest" in csv_text
    assert "run_command" in csv_text
    assert "Product Public Benchmark Work Order" in md_text
    assert "run_command" in md_text
