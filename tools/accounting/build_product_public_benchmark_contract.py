#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from betelgeuze_product.public_benchmark import BENCHMARK_SUITES, REQUIRED_SCORECARD_FIELDS, build_product_public_benchmark_contract
from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCORECARD_CSV = "runs/product_public_benchmark_scorecard_intake.csv"
DEFAULT_TEMPLATE_CSV = "runs/product_public_benchmark_scorecard_template_current.csv"
DEFAULT_OUT_JSON = "runs/product_public_benchmark_contract_current.json"
DEFAULT_OUT_CSV = "runs/product_public_benchmark_contract_current.csv"
DEFAULT_OUT_MD = "runs/product_public_benchmark_contract_current.md"


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_template(path_like: str | Path) -> None:
    rows = []
    for suite in BENCHMARK_SUITES:
        rows.append(
            {
                "suite_id": suite["suite_id"],
                "benchmark_family": suite["benchmark_family"],
                "dataset_source_url": suite["dataset_source_url"],
                "scorecard_json": "OPERATOR_FILL_SCORECARD_JSON",
                "status": "OPERATOR_FILL_pass_or_fail",
                "primary_metric": suite["primary_metric"],
                "primary_metric_value": "OPERATOR_FILL_VALUE",
                "primary_metric_threshold": suite["primary_metric_threshold"],
                "regression_baseline_ref": "OPERATOR_FILL_BASELINE_REF",
                "run_command": "OPERATOR_FILL_REPRODUCIBLE_COMMAND",
            }
        )
    write_csv_rows(_resolve(path_like), rows)


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Product Public Benchmark Contract",
        "",
        f"- status: `{s['status']}`",
        f"- public_benchmark_validation_ready: `{s['public_benchmark_validation_ready']}`",
        f"- benchmark_mode: `{s['benchmark_mode']}`",
        f"- requires_institution_registration: `{s['requires_institution_registration']}`",
        f"- requires_24h_server: `{s['requires_24h_server']}`",
        f"- requires_competition_season: `{s['requires_competition_season']}`",
        f"- requires_paid_vps: `{s['requires_paid_vps']}`",
        f"- scorecard_csv: `{s['scorecard_csv']}`",
        f"- scorecard_csv_present: `{s['scorecard_csv_present']}`",
        f"- suite_count: `{s['suite_count']}`",
        f"- required_suite_count: `{s['required_suite_count']}`",
        f"- ready_required_suite_count: `{s['ready_required_suite_count']}`",
        f"- blocked_suite_count: `{s['blocked_suite_count']}`",
        f"- suite_materialization_manifest_count: `{s['suite_materialization_manifest_count']}`",
        f"- suite_scorecard_row_csv_count: `{s['suite_scorecard_row_csv_count']}`",
        f"- suite_threshold_count: `{s['suite_threshold_count']}`",
        f"- suite_blocker_count: `{s['suite_blocker_count']}`",
        f"- suite_run_command_count: `{s['suite_run_command_count']}`",
        f"- suite_materialization_run_command_count: `{s['suite_materialization_run_command_count']}`",
        f"- suite_no_external_dependency_count: `{s['suite_no_external_dependency_count']}`",
        "",
        "## Suites",
        "",
        "| suite | family | status | materialization | scorecard row | metric | threshold | blocker | run command |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['suite_id']}` | `{row['benchmark_family']}` | `{row['status']}` | "
            f"`{row['materialization_manifest_status'] or 'missing'}` | "
            f"`{row['scorecard_row_csv']}` | "
            f"`{row['primary_metric']}` | `{row['threshold']}` | "
            f"`{row['blocker']}` | `{row['run_command'] or 'missing'}` |"
        )
    lines.extend(["", "## Required Scorecard Fields", "", ", ".join(f"`{field}`" for field in REQUIRED_SCORECARD_FIELDS)])
    lines.extend(["", "## Blockers", ""])
    if payload["blockers"]:
        lines.extend(f"- `{blocker['code']}`: {blocker['reason']}" for blocker in payload["blockers"])
    else:
        lines.append("- none")
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the product public benchmark contract without running benchmark jobs.")
    parser.add_argument("--scorecard-csv", default=DEFAULT_SCORECARD_CSV)
    parser.add_argument("--template-csv", default=DEFAULT_TEMPLATE_CSV)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_product_public_benchmark_contract(scorecard_csv=_resolve(args.scorecard_csv), root=ROOT)
    _write_template(args.template_csv)
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
