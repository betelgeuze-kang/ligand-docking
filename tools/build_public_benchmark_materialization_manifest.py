#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from betelgeuze_product.public_benchmark_materialization import (
    build_public_benchmark_materialization_manifest,
    write_manifest,
)
from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Public Benchmark Materialization Manifest",
        "",
        f"- status: `{s['status']}`",
        f"- materialized: `{s['materialized']}`",
        f"- suite_id: `{s['suite_id']}`",
        f"- benchmark_family: `{s['benchmark_family']}`",
        f"- dataset_source_url: `{s['dataset_source_url']}`",
        f"- dataset_artifact: `{s['dataset_artifact']}`",
        f"- dataset_artifact_present: `{s['dataset_artifact_present']}`",
        f"- result_artifact: `{s['result_artifact']}`",
        f"- result_artifact_present: `{s['result_artifact_present']}`",
        f"- result_row_count: `{s['result_row_count']}`",
        f"- min_result_rows: `{s['min_result_rows']}`",
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
    lines.extend(["", "## Checks", "", "| check | status | observed | required |", "| --- | --- | --- | --- |"])
    for row in payload["rows"]:
        lines.append(f"| `{row['check']}` | `{row['status']}` | `{row['observed']}` | `{row['required']}` |")
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _default_dataset_artifact(suite_id: str) -> str:
    return f"data/public_benchmarks/{suite_id}"


def _default_result_artifact(suite_id: str) -> str:
    return f"runs/{suite_id}_benchmark_results_current.csv"


def _default_out_json(suite_id: str) -> str:
    return f"runs/{suite_id}_materialization_manifest_current.json"


def _default_out_csv(suite_id: str) -> str:
    return f"runs/{suite_id}_materialization_manifest_current.csv"


def _default_out_md(suite_id: str) -> str:
    return f"runs/{suite_id}_materialization_manifest_current.md"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a local materialization manifest for one product public benchmark suite.")
    parser.add_argument("--suite-id", required=True)
    parser.add_argument("--dataset-artifact", default="")
    parser.add_argument("--result-artifact", default="")
    parser.add_argument("--min-result-rows", type=int, default=1)
    parser.add_argument("--out-json", default="")
    parser.add_argument("--out-csv", default="")
    parser.add_argument("--out-md", default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    dataset_artifact = args.dataset_artifact or _default_dataset_artifact(args.suite_id)
    result_artifact = args.result_artifact or _default_result_artifact(args.suite_id)
    out_json = args.out_json or _default_out_json(args.suite_id)
    out_csv = args.out_csv or _default_out_csv(args.suite_id)
    out_md = args.out_md or _default_out_md(args.suite_id)
    payload = build_public_benchmark_materialization_manifest(
        suite_id=args.suite_id,
        dataset_artifact=_resolve(dataset_artifact),
        result_artifact=_resolve(result_artifact),
        min_result_rows=args.min_result_rows,
    )
    write_manifest(_resolve(out_json), payload)
    write_csv_rows(_resolve(out_csv), payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
