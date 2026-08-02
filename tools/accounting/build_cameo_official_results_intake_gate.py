#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from betelgeuze_cameo.official_results import build_cameo_official_results_intake_gate
from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RESULTS_CSV = "runs/cameo_official_results_operator_intake.csv"
DEFAULT_TEMPLATE_CSV = "runs/cameo_official_results_operator_template_current.csv"
DEFAULT_OUT_JSON = "runs/cameo_official_results_intake_gate_current.json"
DEFAULT_OUT_CSV = "runs/cameo_official_results_intake_gate_current.csv"
DEFAULT_OUT_MD = "runs/cameo_official_results_intake_gate_current.md"


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_csv_rows(path_like: str | Path) -> list[dict[str, Any]]:
    path = _resolve(path_like)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_template(path_like: str | Path) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "target_id,candidate_id,cameo_model_rank,result_source_kind,result_source_url,result_record_id,retrieved_at_utc,assessment_date,lddt,tm_score,qs_score,rmsd_A,operator_note",
        "OPERATOR_FILL_CAMEO_TARGET_ID,OPERATOR_FILL_CANDIDATE_ID,1,official_cameo,OPERATOR_FILL_CAMEO_RESULT_URL,OPERATOR_FILL_CAMEO_RECORD_ID,OPERATOR_FILL_UTC_TIMESTAMP,OPERATOR_FILL_ASSESSMENT_DATE,OPERATOR_FILL_OR_BLANK,OPERATOR_FILL_OR_BLANK,OPERATOR_FILL_OR_BLANK,OPERATOR_FILL_OR_BLANK,official CAMEO metrics only",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# CAMEO Official Results Intake Gate",
        "",
        f"- status: `{s['status']}`",
        f"- official_result_intake_ready: `{s['official_result_intake_ready']}`",
        f"- result_row_count: `{s['result_row_count']}`",
        f"- accepted_official_result_count: `{s['accepted_official_result_count']}`",
        f"- rejected_official_result_count: `{s['rejected_official_result_count']}`",
        f"- model1_official_result_ready: `{s['model1_official_result_ready']}`",
        f"- blocker_count: `{s['blocker_count']}`",
        f"- blocker_codes: `{','.join(s['blocker_codes'])}`",
        f"- operator_action_required_count: `{s['operator_action_required_count']}`",
        f"- operator_action_required_row_count: `{s['operator_action_required_row_count']}`",
        f"- primary_blocker_code: `{s['primary_blocker_code']}`",
        f"- primary_required_action: `{s['primary_required_action']}`",
        f"- required_columns: `{','.join(s['required_columns'])}`",
        f"- missing_required_columns: `{','.join(s['missing_required_columns'])}`",
        f"- official_metric_columns: `{','.join(s['official_metric_columns'])}`",
        f"- disallowed_local_accuracy_columns: `{','.join(s['disallowed_local_accuracy_columns'])}`",
        f"- allowed_result_source_kinds: `{','.join(s['allowed_result_source_kinds'])}`",
        f"- source_provenance_ready_row_count: `{s['source_provenance_ready_row_count']}`",
        f"- official_metric_ready_row_count: `{s['official_metric_ready_row_count']}`",
        f"- local_native_accuracy_blocker_count: `{s['local_native_accuracy_blocker_count']}`",
        f"- operator_template_csv: `{s['operator_template_csv']}`",
        f"- operator_intake_csv: `{s['operator_intake_csv']}`",
        f"- native_local_accuracy_used: `{s['native_local_accuracy_used']}`",
        f"- official_cameo_results_used: `{s['official_cameo_results_used']}`",
        f"- outbound_email_enabled: `{s['outbound_email_enabled']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Rows",
        "",
        "| row | target | candidate | rank | ready | provenance | metrics | local/native absent | blockers | action |",
        "| ---: | --- | --- | ---: | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload.get("rows") or []:
        lines.append(
            f"| `{row['row_number']}` | `{row['target_id']}` | `{row['candidate_id']}` | `{row['cameo_model_rank']}` | "
            f"`{row['ready']}` | `{row['source_provenance_ready']}` | `{row['official_metric_ready']}` | "
            f"`{row['local_native_accuracy_absent']}` | `{row['blockers']}` | {row['required_action']} |"
        )
    lines.extend(["", "## Blockers", ""])
    blockers = payload.get("blockers") or []
    if blockers:
        lines.extend(
            f"- `{blocker['code']}`: {blocker['reason']} Action: {blocker['required_action']}"
            for blocker in blockers
        )
    else:
        lines.append("- none")
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate operator-provided official CAMEO result rows without fetching or mutating external state.")
    parser.add_argument("--results-csv", default=DEFAULT_RESULTS_CSV)
    parser.add_argument("--allow-missing-model1", action="store_true")
    parser.add_argument("--template-csv", default=DEFAULT_TEMPLATE_CSV)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_cameo_official_results_intake_gate(
        result_rows=_read_csv_rows(args.results_csv),
        require_model1=not args.allow_missing_model1,
        operator_template_csv=args.template_csv,
        operator_intake_csv=args.results_csv,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)
    _write_template(args.template_csv)


if __name__ == "__main__":
    main()
