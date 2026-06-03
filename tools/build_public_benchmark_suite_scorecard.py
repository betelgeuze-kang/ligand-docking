#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from betelgeuze_product.public_benchmark_scorecard import build_public_benchmark_suite_scorecard, write_scorecard
from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Public Benchmark Suite Scorecard",
        "",
        f"- status: `{s['status']}`",
        f"- pass: `{s['pass']}`",
        f"- suite_id: `{s['suite_id']}`",
        f"- benchmark_family: `{s['benchmark_family']}`",
        f"- dataset_source_url: `{s['dataset_source_url']}`",
        f"- evidence_artifact: `{s['evidence_artifact']}`",
        f"- evidence_artifact_present: `{s['evidence_artifact_present']}`",
        f"- evidence_row_count: `{s['evidence_row_count']}`",
        f"- primary_metric: `{s['primary_metric']}`",
        f"- primary_metric_value: `{s['primary_metric_value']}`",
        f"- primary_metric_threshold: `{s['primary_metric_threshold']}`",
        f"- regression_baseline_ref: `{s['regression_baseline_ref']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Blockers",
        "",
    ]
    blockers = s.get("blockers") or []
    if blockers:
        lines.extend(f"- `{blocker}`" for blocker in blockers)
    else:
        lines.append("- none")
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _default_out_json(suite_id: str) -> str:
    return f"runs/{suite_id}_scorecard_current.json"


def _default_out_md(suite_id: str) -> str:
    return f"runs/{suite_id}_scorecard_current.md"


def _default_row_csv(suite_id: str) -> str:
    return f"runs/{suite_id}_scorecard_row_current.csv"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a product public benchmark suite scorecard row from operator evidence.")
    parser.add_argument("--suite-id", required=True)
    parser.add_argument("--primary-metric-value", type=float, required=True)
    parser.add_argument("--primary-metric-name", default="")
    parser.add_argument("--primary-metric-threshold", type=float)
    parser.add_argument("--evidence-artifact", default="")
    parser.add_argument("--evidence-row-count", type=int, default=0)
    parser.add_argument("--min-evidence-rows", type=int, default=1)
    parser.add_argument("--regression-baseline-ref", default="")
    parser.add_argument("--run-command", default="")
    parser.add_argument("--out-json", default="")
    parser.add_argument("--out-md", default="")
    parser.add_argument("--row-csv", default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    out_json = args.out_json or _default_out_json(args.suite_id)
    out_md = args.out_md or _default_out_md(args.suite_id)
    row_csv = args.row_csv or _default_row_csv(args.suite_id)
    run_command = args.run_command or (
        "python3 tools/build_public_benchmark_suite_scorecard.py "
        f"--suite-id {args.suite_id} --primary-metric-value {args.primary_metric_value}"
    )
    payload = build_public_benchmark_suite_scorecard(
        suite_id=args.suite_id,
        primary_metric_value=args.primary_metric_value,
        primary_metric_name=args.primary_metric_name,
        primary_metric_threshold=args.primary_metric_threshold,
        evidence_artifact=_resolve(args.evidence_artifact) if args.evidence_artifact else "",
        evidence_row_count=args.evidence_row_count,
        min_evidence_rows=args.min_evidence_rows,
        regression_baseline_ref=args.regression_baseline_ref,
        run_command=run_command,
        out_json=_resolve(out_json),
    )
    write_scorecard(_resolve(out_json), payload)
    write_csv_rows(_resolve(row_csv), [payload["scorecard_row"]])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
