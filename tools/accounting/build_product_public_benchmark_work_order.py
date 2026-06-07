#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from betelgeuze_product.public_benchmark_work_order import build_product_public_benchmark_work_order
from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PUBLIC_BENCHMARK_JSON = "runs/product_public_benchmark_contract_current.json"
DEFAULT_OUT_JSON = "runs/product_public_benchmark_work_order_current.json"
DEFAULT_OUT_CSV = "runs/product_public_benchmark_work_order_current.csv"
DEFAULT_OUT_MD = "runs/product_public_benchmark_work_order_current.md"


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_json_if_present(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Product Public Benchmark Work Order",
        "",
        f"- status: `{s['status']}`",
        f"- source_public_benchmark_status: `{s['source_public_benchmark_status']}`",
        f"- public_benchmark_validation_ready: `{s['public_benchmark_validation_ready']}`",
        f"- suite_count: `{s['suite_count']}`",
        f"- open_suite_count: `{s['open_suite_count']}`",
        f"- materialization_required_suite_count: `{s['materialization_required_suite_count']}`",
        f"- scorecard_required_suite_count: `{s['scorecard_required_suite_count']}`",
        f"- continuous_validation_command_count: `{s['continuous_validation_command_count']}`",
        f"- suite_run_command_count: `{s['suite_run_command_count']}`",
        f"- suite_materialization_run_command_count: `{s['suite_materialization_run_command_count']}`",
        f"- suite_scorecard_command_count: `{s['suite_scorecard_command_count']}`",
        f"- suite_result_provenance_command_count: `{s['suite_result_provenance_command_count']}`",
        f"- suite_result_provenance_present_count: `{s['suite_result_provenance_present_count']}`",
        f"- suite_threshold_count: `{s['suite_threshold_count']}`",
        f"- suite_blocker_count: `{s['suite_blocker_count']}`",
        f"- suite_materialization_manifest_count: `{s['suite_materialization_manifest_count']}`",
        f"- suite_scorecard_row_csv_count: `{s['suite_scorecard_row_csv_count']}`",
        f"- suite_required_output_count: `{s['suite_required_output_count']}`",
        f"- suite_no_external_dependency_count: `{s['suite_no_external_dependency_count']}`",
        f"- local_artifact_preflight_ready_suite_count: `{s['local_artifact_preflight_ready_suite_count']}`",
        f"- local_artifact_preflight_blocked_suite_count: `{s['local_artifact_preflight_blocked_suite_count']}`",
        f"- local_artifact_placement_required_suite_count: `{s['local_artifact_placement_required_suite_count']}`",
        f"- download_approval_required_suite_count: `{s['download_approval_required_suite_count']}`",
        f"- download_approval_token_required: `{s['download_approval_token_required']}`",
        f"- download_approval_granted: `{s['download_approval_granted']}`",
        f"- result_generation_required_suite_count: `{s['result_generation_required_suite_count']}`",
        f"- benchmark_result_missing_artifact_count: `{s['benchmark_result_missing_artifact_count']}`",
        f"- benchmark_result_missing_artifacts: `{';'.join(s['benchmark_result_missing_artifacts'])}`",
        f"- result_generation_approval_token_required: `{s['result_generation_approval_token_required']}`",
        f"- missing_local_input_artifact_count: `{s['missing_local_input_artifact_count']}`",
        f"- missing_local_output_artifact_count: `{s['missing_local_output_artifact_count']}`",
        f"- missing_local_input_artifacts: `{';'.join(s['missing_local_input_artifacts'])}`",
        f"- missing_local_output_artifacts: `{';'.join(s['missing_local_output_artifacts'])}`",
        f"- scorecard_intake_sync_command: `{s['scorecard_intake_sync_command']}`",
        f"- scorecard_row_csvs: `{';'.join(s['scorecard_row_csvs'])}`",
        f"- ready_required_suite_count: `{s['ready_required_suite_count']}`",
        f"- required_suite_count: `{s['required_suite_count']}`",
        f"- blocked_suite_count: `{s['blocked_suite_count']}`",
        f"- requires_24h_server: `{s['requires_24h_server']}`",
        f"- requires_competition_season: `{s['requires_competition_season']}`",
        f"- requires_paid_vps: `{s['requires_paid_vps']}`",
        f"- execution_enabled: `{s['execution_enabled']}`",
        f"- download_executed: `{s['download_executed']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Suites",
        "",
        "| suite | status | metric | threshold | provenance | missing inputs | missing outputs | result generation | result token | expected result schema | input artifacts | output artifacts | required_input | required_output | blocker |",
        "| --- | --- | --- | ---: | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['suite_id']}` | `{row['work_order_status']}` | `{row['primary_metric']}` | "
            f"`{row['threshold']}` | `{row['result_provenance_json']}` | `{row['missing_local_input_artifacts']}` | "
            f"`{row['missing_local_output_artifacts']}` | `{row['result_generation_required']}` | "
            f"`{row['result_generation_approval_token_required']}` | `{row['expected_result_schema']}` | "
            f"`{row['operator_input_artifacts']}` | `{row['operator_output_artifacts']}` | "
            f"`{row['required_input']}` | `{row['required_output']}` | `{row['blocker']}` |"
        )
    lines.extend(["", "## Commands", ""])
    lines.extend(["### Continuous Validation", "", f"- command: `{s['continuous_validation_command']}`", ""])
    for row in payload["rows"]:
        lines.extend(
            [
                f"### {row['suite_id']}",
                "",
                f"- run_command: `{row['run_command']}`",
                f"- continuous_validation_command: `{row['continuous_validation_command']}`",
                f"- materialization: `{row['materialization_command']}`",
                f"- result_provenance_json: `{row['result_provenance_json']}`",
                f"- result_provenance_present: `{row['result_provenance_present']}`",
                f"- result_provenance_min_result_rows: `{row['result_provenance_min_result_rows']}`",
                f"- result_provenance: `{row['result_provenance_command']}`",
                f"- scorecard: `{row['scorecard_command']}`",
                f"- scorecard_source: `{row['scorecard_command_source']}`",
                f"- scorecard_template: `{row['scorecard_command_template']}`",
                f"- scorecard_row_csv: `{row['scorecard_row_csv']}`",
                f"- local_artifact_preflight_ready: `{row['local_artifact_preflight_ready']}`",
                f"- local_artifact_placement_required: `{row['local_artifact_placement_required']}`",
                f"- requires_download_approval: `{row['requires_download_approval']}`",
                f"- download_approval_artifacts: `{row['download_approval_artifacts']}`",
                f"- download_approval_token_required: `{row['download_approval_token_required']}`",
                f"- local_result_source_artifacts: `{row['local_result_source_artifacts']}`",
                f"- benchmark_result_missing_artifacts: `{row['benchmark_result_missing_artifacts']}`",
                f"- result_generation_required: `{row['result_generation_required']}`",
                f"- result_generation_approval_token_required: `{row['result_generation_approval_token_required']}`",
                f"- expected_result_schema: `{row['expected_result_schema']}`",
                f"- missing_local_input_artifacts: `{row['missing_local_input_artifacts']}`",
                f"- missing_local_output_artifacts: `{row['missing_local_output_artifacts']}`",
                f"- scorecard_intake_sync: `{row['scorecard_intake_sync_command']}`",
                f"- refresh: `{row['refresh_command']}`",
                "",
            ]
        )
    lines.extend(["## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the operator work order for product public benchmark blockers.")
    parser.add_argument("--public-benchmark-json", default=DEFAULT_PUBLIC_BENCHMARK_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_product_public_benchmark_work_order(
        public_benchmark_packet=_read_json_if_present(args.public_benchmark_json),
        public_benchmark_path=args.public_benchmark_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
