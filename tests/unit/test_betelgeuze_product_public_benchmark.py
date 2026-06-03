from __future__ import annotations

from pathlib import Path

from betelgeuze_product.public_benchmark import BENCHMARK_SUITES, build_product_public_benchmark_contract


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
