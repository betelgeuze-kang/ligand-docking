from __future__ import annotations

import json
from pathlib import Path

from betelgeuze_product.public_benchmark import BENCHMARK_SUITES, build_product_public_benchmark_contract


def _manifest_stem(suite_id: str) -> str:
    return "lit_pcba" if suite_id == "lit_pcba_virtual_screening" else suite_id


def test_public_benchmark_contract_blocks_missing_scorecard_intake(tmp_path: Path) -> None:
    payload = build_product_public_benchmark_contract(scorecard_csv=tmp_path / "missing.csv")

    summary = payload["summary"]
    assert summary["status"] == "blocked_product_public_benchmark_contract"
    assert summary["public_benchmark_validation_ready"] is False
    assert summary["requires_24h_server"] is False
    assert summary["requires_paid_vps"] is False
    assert summary["requires_competition_season"] is False
    assert summary["requires_institution_registration"] is False
    assert summary["blocked_suite_count"] == len(BENCHMARK_SUITES)
    assert all(row["status"] == "blocked" for row in payload["rows"])
    assert all(row["external_state_mutated"] is False for row in payload["rows"])


def test_public_benchmark_contract_ready_with_complete_passing_rows(tmp_path: Path) -> None:
    scorecard = tmp_path / "scorecards.csv"
    lines = [
        "suite_id,benchmark_family,dataset_source_url,scorecard_json,status,primary_metric,primary_metric_value,primary_metric_threshold,regression_baseline_ref,run_command"
    ]
    for suite in BENCHMARK_SUITES:
        scorecard_json = tmp_path / "runs" / f"{suite['suite_id']}_scorecard.json"
        scorecard_json.parent.mkdir(parents=True, exist_ok=True)
        materialization_json = tmp_path / "runs" / f"{_manifest_stem(str(suite['suite_id']))}_materialization_manifest_current.json"
        materialization_json.write_text(
            json.dumps(
                {
                    "summary": {
                        "suite_id": suite["suite_id"],
                        "status": "public_benchmark_materialization_ready",
                        "materialized": True,
                        "blockers": [],
                        "dataset_artifact": f"data/{suite['suite_id']}",
                        "result_artifact": f"runs/{suite['suite_id']}_benchmark_results_current.csv",
                        "run_command": f"python3 tools/build_public_benchmark_materialization_manifest.py --suite-id {suite['suite_id']}",
                        "scorecard_run_command_template": f"python3 tools/build_public_benchmark_suite_scorecard.py --suite-id {suite['suite_id']}",
                    }
                }
            ),
            encoding="utf-8",
        )
        scorecard_json.write_text(
            json.dumps(
                {
                    "summary": {
                        "suite_id": suite["suite_id"],
                        "status": "public_benchmark_suite_scorecard_pass",
                        "pass": True,
                    }
                }
            ),
            encoding="utf-8",
        )
        lines.append(
            ",".join(
                [
                    str(suite["suite_id"]),
                    str(suite["benchmark_family"]),
                    str(suite["dataset_source_url"]),
                    f"runs/{suite['suite_id']}_scorecard.json",
                    "pass",
                    str(suite["primary_metric"]),
                    str(float(suite["primary_metric_threshold"]) + 0.1),
                    str(suite["primary_metric_threshold"]),
                    "baseline:v1",
                    f"python3 tools/run_{suite['suite_id']}.py",
                ]
            )
        )
    scorecard.write_text("\n".join(lines) + "\n", encoding="utf-8")

    payload = build_product_public_benchmark_contract(scorecard_csv=scorecard)

    summary = payload["summary"]
    assert summary["status"] == "product_public_benchmark_contract_ready"
    assert summary["public_benchmark_validation_ready"] is True
    assert summary["ready_required_suite_count"] == len(BENCHMARK_SUITES)
    assert summary["blocked_suite_count"] == 0
    assert payload["blockers"] == []
    assert all(row["status"] == "ready" for row in payload["rows"])
    assert all(row["materialization_manifest_present"] is True for row in payload["rows"])
    assert all(row["operator_input_artifacts"] for row in payload["rows"])
    assert all(row["operator_output_artifacts"] for row in payload["rows"])
    assert all(row["scorecard_run_command_template"] for row in payload["rows"])


def test_public_benchmark_contract_exposes_lit_pcba_operator_artifacts(tmp_path: Path) -> None:
    suite = BENCHMARK_SUITES[0]
    manifest = tmp_path / "runs" / "lit_pcba_materialization_manifest_current.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        json.dumps(
            {
                "summary": {
                    "suite_id": suite["suite_id"],
                    "status": "blocked_lit_pcba_materialization",
                    "materialized": False,
                    "blockers": ["zenodo_archive_missing"],
                    "archive_path": "data/public_benchmarks/lit_pcba/LIT_PCBA_AVE_docked_released.tar.xz",
                    "extracted_dir": "data/public_benchmarks/lit_pcba/LIT_PCBA_AVE_docked_released",
                    "source_score_csv": "data/public_benchmarks/lit_pcba/lit_pcba_source_scores.csv",
                    "source_label_csv": "data/public_benchmarks/lit_pcba/lit_pcba_source_labels.csv",
                    "out_scores_csv": "runs/lit_pcba_scores_current.csv",
                    "out_labels_csv": "runs/lit_pcba_labels_current.csv",
                    "run_command": "python3 tools/build_lit_pcba_materialization_manifest.py",
                    "scorecard_run_command_template": "python3 tools/build_lit_pcba_scorecard.py",
                }
            }
        ),
        encoding="utf-8",
    )

    payload = build_product_public_benchmark_contract(scorecard_csv=tmp_path / "missing.csv", root=tmp_path)

    row = next(row for row in payload["rows"] if row["suite_id"] == suite["suite_id"])
    assert "LIT_PCBA_AVE_docked_released.tar.xz" in row["operator_input_artifacts"]
    assert "lit_pcba_source_scores.csv" in row["operator_input_artifacts"]
    assert "runs/lit_pcba_scores_current.csv" in row["operator_output_artifacts"]
    assert row["scorecard_run_command_template"] == "python3 tools/build_lit_pcba_scorecard.py"


def test_public_benchmark_contract_blocks_passing_row_without_scorecard_json(tmp_path: Path) -> None:
    scorecard = tmp_path / "scorecards.csv"
    suite = BENCHMARK_SUITES[0]
    scorecard.write_text(
        "suite_id,benchmark_family,dataset_source_url,scorecard_json,status,primary_metric,primary_metric_value,primary_metric_threshold,regression_baseline_ref,run_command\n"
        f"{suite['suite_id']},{suite['benchmark_family']},{suite['dataset_source_url']},runs/missing.json,pass,{suite['primary_metric']},999,{suite['primary_metric_threshold']},baseline:v1,cmd\n",
        encoding="utf-8",
    )

    payload = build_product_public_benchmark_contract(scorecard_csv=scorecard)

    row = next(row for row in payload["rows"] if row["suite_id"] == suite["suite_id"])
    assert row["status"] == "blocked"
    assert "scorecard_json_missing" in row["blockers"]


def test_public_benchmark_contract_blocks_row_without_materialization_manifest(tmp_path: Path) -> None:
    scorecard = tmp_path / "scorecards.csv"
    suite = BENCHMARK_SUITES[0]
    scorecard_json = tmp_path / "runs" / "scorecard.json"
    scorecard_json.parent.mkdir(parents=True, exist_ok=True)
    scorecard_json.write_text(
        json.dumps(
            {
                "summary": {
                    "suite_id": suite["suite_id"],
                    "status": "public_benchmark_suite_scorecard_pass",
                    "pass": True,
                }
            }
        ),
        encoding="utf-8",
    )
    scorecard.write_text(
        "suite_id,benchmark_family,dataset_source_url,scorecard_json,status,primary_metric,primary_metric_value,primary_metric_threshold,regression_baseline_ref,run_command\n"
        f"{suite['suite_id']},{suite['benchmark_family']},{suite['dataset_source_url']},runs/scorecard.json,pass,{suite['primary_metric']},999,{suite['primary_metric_threshold']},baseline:v1,cmd\n",
        encoding="utf-8",
    )

    payload = build_product_public_benchmark_contract(scorecard_csv=scorecard)

    row = next(row for row in payload["rows"] if row["suite_id"] == suite["suite_id"])
    assert row["status"] == "blocked"
    assert "materialization_manifest_missing" in row["blockers"]
