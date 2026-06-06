#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from betelgeuze_cameo.operator_inputs import build_operator_input_validation
from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CANDIDATES_CSV = "runs/cameo_operator_input_kit_current/candidates_template.csv"
DEFAULT_MODELS_CSV = "runs/cameo_operator_input_kit_current/models_template.csv"
DEFAULT_OFFICIAL_RESULTS_CSV = "runs/cameo_operator_input_kit_current/official_results_template.csv"
DEFAULT_OUT_JSON = "runs/cameo_operator_input_validation_current.json"
DEFAULT_OUT_CSV = "runs/cameo_operator_input_validation_current.csv"
DEFAULT_OUT_MD = "runs/cameo_operator_input_validation_current.md"


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_csv_rows(path_like: str | Path) -> list[dict[str, Any]]:
    path = _resolve(path_like)
    if not str(path_like).strip() or not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# CAMEO Operator Input Validation",
        "",
        f"- status: `{s['status']}`",
        f"- candidate_row_count: `{s['candidate_row_count']}`",
        f"- model_row_count: `{s['model_row_count']}`",
        f"- official_result_row_count: `{s['official_result_row_count']}`",
        f"- blocker_count: `{s['blocker_count']}`",
        f"- warning_count: `{s['warning_count']}`",
        f"- action_executed: `{s['action_executed']}`",
        f"- outbound_email_enabled: `{s['outbound_email_enabled']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        f"- native_local_accuracy_used: `{s['native_local_accuracy_used']}`",
        "",
        "## Rows",
        "",
        "| input | row | ready | target | candidate | rank | blockers |",
        "| --- | ---: | --- | --- | --- | ---: | --- |",
    ]
    for row in payload.get("rows") or []:
        lines.append(
            f"| `{row.get('input_name', '')}` | `{row.get('row_number', '')}` | `{row.get('ready', '')}` | "
            f"`{row.get('target_id', '')}` | `{row.get('candidate_id', '')}` | `{row.get('cameo_model_rank', '')}` | "
            f"`{row.get('blockers', '')}` |"
        )

    lines.extend(["", "## Blockers", ""])
    blockers = payload.get("blockers") or []
    if blockers:
        lines.extend(
            f"- `{blocker['code']}`"
            f"{' row ' + str(blocker.get('row_number')) if blocker.get('row_number') else ''}: {blocker['reason']}"
            for blocker in blockers
        )
    else:
        lines.append("- none")

    lines.extend(["", "## Warnings", ""])
    warnings = payload.get("warnings") or []
    if warnings:
        lines.extend(
            f"- `{warning['code']}`"
            f"{' row ' + str(warning.get('row_number')) if warning.get('row_number') else ''}: {warning['reason']}"
            for warning in warnings
        )
    else:
        lines.append("- none")

    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate filled CAMEO operator input CSVs without rebuilding artifacts.")
    parser.add_argument("--candidates-csv", default=DEFAULT_CANDIDATES_CSV)
    parser.add_argument("--models-csv", default=DEFAULT_MODELS_CSV)
    parser.add_argument("--official-results-csv", default=DEFAULT_OFFICIAL_RESULTS_CSV)
    parser.add_argument("--base-dir", default=str(ROOT))
    parser.add_argument("--require-official-results", action="store_true")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_operator_input_validation(
        candidates_rows=_read_csv_rows(args.candidates_csv),
        model_rows=_read_csv_rows(args.models_csv),
        official_result_rows=_read_csv_rows(args.official_results_csv),
        base_dir=args.base_dir,
        require_official_results=bool(args.require_official_results),
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
