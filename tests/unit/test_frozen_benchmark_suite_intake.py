"""Operator intake tests for the frozen public benchmark suite (P1-8)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from betelgeuze_product.frozen_benchmark_suite import (
    MIN_FROZEN_CASE_COUNT,
    REQUIRED_METRICS,
    REQUIRED_STRATIFICATION_AXES,
)
from tools.product import build_frozen_benchmark_suite_intake as mod


def _write_cases(path: Path, count: int, *, buckets: int = 2, drop_axis: str = "") -> None:
    columns = list(mod.REQUIRED_CASE_COLUMNS)
    if drop_axis:
        columns = [name for name in columns if name != drop_axis]
    lines = [",".join(columns)]
    for index in range(count):
        row = {
            "case_id": f"case_{index:03d}",
            "target_id": f"target_{index % 7}",
            "ligand_id": f"ligand_{index}",
            "provenance_id": "operator_curated_public",
        }
        for axis in REQUIRED_STRATIFICATION_AXES:
            row[axis] = f"{axis}_bucket_{index % max(buckets, 1)}"
        lines.append(",".join(row[name] for name in columns))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _metrics_payload(case_count: int) -> dict[str, Any]:
    metrics: dict[str, Any] = {
        metric_id: 0.5
        for metric_id in REQUIRED_METRICS
        if metric_id not in {"rotor_subgroup_success", "size_subgroup_success"}
    }
    metrics["rotor_subgroup_success"] = {"rotors_0_3": 0.61, "rotors_4_plus": 0.29}
    metrics["size_subgroup_success"] = {"small": 0.58, "large": 0.27}
    metrics["attempted_case_count"] = case_count
    return {
        "frozen_at_utc": "2026-07-27T00:00:00Z",
        "metrics": metrics,
        "bootstrap_intervals": [
            {
                "metric_id": "top1_rmsd_success_rate_2a",
                "point_estimate": 0.5,
                "ci_low": 0.42,
                "ci_high": 0.58,
                "iterations": 2000,
                "seed": 11,
            }
        ],
        "paired_baseline_deltas": [
            {
                "baseline_engine": "vina",
                "metric_id": "top1_rmsd_success_rate_2a",
                "subject_value": 0.5,
                "baseline_value": 0.54,
                "paired_case_count": case_count,
            }
        ],
    }


@pytest.fixture()
def intake(tmp_path: Path):
    def _build(case_count: int = 120, **overrides):
        cases = tmp_path / "cases.csv"
        metrics = tmp_path / "metrics.json"
        _write_cases(
            cases,
            case_count,
            buckets=overrides.pop("buckets", 2),
            drop_axis=overrides.pop("drop_axis", ""),
        )
        payload = overrides.pop("metrics_payload", _metrics_payload(case_count))
        case_rows, _ = mod._read_cases(cases)
        expected_hash = mod.build_frozen_benchmark_suite(
            suite_id="test_suite",
            frozen_at_utc="",
            cases=case_rows,
        ).case_set_hash
        if isinstance(payload, dict):
            payload.setdefault("case_set_hash", expected_hash)
        metrics.write_text(json.dumps(payload), encoding="utf-8")
        kwargs: dict[str, Any] = {"cases_csv": cases, "metrics_json": metrics}
        kwargs.update(overrides)
        return mod.build_frozen_benchmark_suite_intake(**kwargs)

    return _build


def test_complete_intake_is_ready(intake) -> None:
    summary = intake()["summary"]

    assert summary["status"] == mod.STATUS_READY
    assert summary["ready"] is True
    assert summary["blockers"] == []
    assert summary["case_count"] == 120
    assert summary["present_metric_count"] == len(REQUIRED_METRICS)
    assert summary["missing_metric_ids"] == []


def test_intake_never_downloads_or_executes(intake) -> None:
    summary = intake()["summary"]

    assert summary["datasets_downloaded"] is False
    assert summary["docking_executed"] is False
    assert summary["baseline_executed"] is False
    assert summary["external_state_mutated"] is False


def test_case_set_hash_is_recorded_and_stable(intake) -> None:
    first = intake()["summary"]["case_set_hash"]
    second = intake()["summary"]["case_set_hash"]

    assert first
    assert first == second


def test_metrics_case_set_hash_must_match_frozen_cases(intake) -> None:
    payload = _metrics_payload(120)
    payload["case_set_hash"] = "0" * 64
    summary = intake(120, metrics_payload=payload)["summary"]

    assert "metrics_case_set_hash_mismatch" in summary["blockers"]
    assert summary["metrics_case_set_hash_matches"] is False


def test_metrics_freeze_time_must_match_explicit_suite_freeze(intake) -> None:
    payload = _metrics_payload(120)
    summary = intake(
        120,
        metrics_payload=payload,
        frozen_at_utc="2026-07-28T00:00:00Z",
    )["summary"]

    assert "metrics_frozen_at_utc_mismatch" in summary["blockers"]


def test_missing_inputs_block_with_named_next_step() -> None:
    packet = mod.build_frozen_benchmark_suite_intake(
        cases_csv="does/not/exist.csv", metrics_json="does/not/exist.json"
    )
    summary = packet["summary"]

    assert summary["status"] == mod.STATUS_BLOCKED
    assert any(b.startswith("cases_csv_missing") for b in summary["blockers"])
    assert any(b.startswith("metrics_json_missing") for b in summary["blockers"])
    assert "Create the operator case CSV" in summary["next_required_step"]


def test_too_few_cases_blocks_and_names_the_shortfall(intake) -> None:
    summary = intake(10)["summary"]

    assert summary["ready"] is False
    assert any(b.startswith("case_count_below_minimum") for b in summary["blockers"])
    assert str(MIN_FROZEN_CASE_COUNT) in summary["next_required_step"]


def test_missing_stratification_column_is_reported(intake) -> None:
    summary = intake(120, drop_axis="pocket_polarity")["summary"]

    assert summary["ready"] is False
    assert "cases_csv_missing_columns:pocket_polarity" in summary["blockers"]


def test_single_bucket_stratification_blocks_with_diversity_step(intake) -> None:
    summary = intake(120, buckets=1)["summary"]

    assert summary["ready"] is False
    assert any(b.startswith("stratification_axis_single_bucket") for b in summary["blockers"])
    assert "Diversify stratification" in summary["next_required_step"]


def test_missing_metric_is_named_in_the_next_step(intake) -> None:
    payload = _metrics_payload(120)
    payload["metrics"].pop("top3_success_rate")
    summary = intake(120, metrics_payload=payload)["summary"]

    assert "required_metric_missing:top3_success_rate" in summary["blockers"]
    assert "top3_success_rate" in summary["next_required_step"]
    assert summary["missing_metric_ids"] == ["top3_success_rate"]


def test_missing_paired_baseline_asks_for_an_offline_run(intake) -> None:
    payload = _metrics_payload(120)
    payload["paired_baseline_deltas"] = []
    summary = intake(120, metrics_payload=payload)["summary"]

    assert "paired_baseline_delta_missing" in summary["blockers"]
    assert "offline baseline" in summary["next_required_step"]


def test_missing_bootstrap_ci_is_blocked(intake) -> None:
    payload = _metrics_payload(120)
    payload["bootstrap_intervals"] = []
    summary = intake(120, metrics_payload=payload)["summary"]

    assert "bootstrap_ci_missing" in summary["blockers"]


def test_subset_paired_delta_is_rejected(intake) -> None:
    payload = _metrics_payload(120)
    payload["paired_baseline_deltas"][0]["paired_case_count"] = 40
    summary = intake(120, metrics_payload=payload)["summary"]

    assert "baseline_delta_not_paired_over_full_suite:vina" in summary["blockers"]


def test_unparseable_metrics_json_is_blocked(tmp_path: Path) -> None:
    cases = tmp_path / "cases.csv"
    _write_cases(cases, 120)
    metrics = tmp_path / "metrics.json"
    metrics.write_text("{not json", encoding="utf-8")

    summary = mod.build_frozen_benchmark_suite_intake(
        cases_csv=cases, metrics_json=metrics
    )["summary"]

    assert any(b.startswith("metrics_json_unparseable") for b in summary["blockers"])


def test_blank_case_identity_is_reported(tmp_path: Path) -> None:
    cases = tmp_path / "cases.csv"
    _write_cases(cases, 120)
    lines = cases.read_text(encoding="utf-8").splitlines()
    fields = lines[1].split(",")
    fields[0] = ""
    lines[1] = ",".join(fields)
    cases.write_text("\n".join(lines) + "\n", encoding="utf-8")
    metrics = tmp_path / "metrics.json"
    metrics.write_text(json.dumps(_metrics_payload(120)), encoding="utf-8")

    summary = mod.build_frozen_benchmark_suite_intake(
        cases_csv=cases, metrics_json=metrics
    )["summary"]

    assert any(b.startswith("case_row_missing_identity") for b in summary["blockers"])


def test_rows_expose_per_case_stratification(intake) -> None:
    rows = intake()["rows"]

    assert len(rows) == 120
    assert rows[0]["missing_stratification_axes"] == ""
    for axis in REQUIRED_STRATIFICATION_AXES:
        assert rows[0][axis]


def test_markdown_reports_coverage_and_blockers(intake) -> None:
    rendered = mod.render_markdown(intake(10))

    assert "Frozen Public Docking Benchmark Suite Intake" in rendered
    for axis in REQUIRED_STRATIFICATION_AXES:
        assert f"- {axis}: " in rendered
    assert "## Blockers" in rendered
    assert "## Next Required Step" in rendered


def test_cli_exits_nonzero_while_intake_is_blocked(tmp_path: Path) -> None:
    exit_code = mod.main(
        [
            "--cases-csv",
            str(tmp_path / "absent.csv"),
            "--metrics-json",
            str(tmp_path / "absent.json"),
            "--out-json",
            str(tmp_path / "out.json"),
            "--out-csv",
            str(tmp_path / "out.csv"),
            "--out-md",
            str(tmp_path / "out.md"),
            "--quiet",
        ]
    )

    assert exit_code == 1
    assert (tmp_path / "out.json").is_file()
    assert (tmp_path / "out.md").is_file()


def test_cli_exits_zero_when_intake_is_complete(tmp_path: Path) -> None:
    cases = tmp_path / "cases.csv"
    _write_cases(cases, 120)
    metrics = tmp_path / "metrics.json"
    case_rows, _ = mod._read_cases(cases)
    payload = _metrics_payload(120)
    payload["case_set_hash"] = mod.build_frozen_benchmark_suite(
        suite_id="test_suite",
        frozen_at_utc="",
        cases=case_rows,
    ).case_set_hash
    metrics.write_text(json.dumps(payload), encoding="utf-8")

    exit_code = mod.main(
        [
            "--cases-csv",
            str(cases),
            "--metrics-json",
            str(metrics),
            "--out-json",
            str(tmp_path / "out.json"),
            "--out-csv",
            str(tmp_path / "out.csv"),
            "--out-md",
            str(tmp_path / "out.md"),
            "--quiet",
        ]
    )

    assert exit_code == 0
    payload = json.loads((tmp_path / "out.json").read_text(encoding="utf-8"))
    assert payload["summary"]["ready"] is True
    assert payload["suite"]["ready"] is True
