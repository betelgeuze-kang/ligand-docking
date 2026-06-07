#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from betelgeuze_product.public_benchmark_provenance import (
    build_public_benchmark_result_provenance,
    write_provenance,
)
from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _default_out_json(suite_id: str) -> str:
    return f"runs/{suite_id}_result_provenance_current.json"


def _default_out_csv(suite_id: str) -> str:
    return f"runs/{suite_id}_result_provenance_current.csv"


def _default_out_md(suite_id: str) -> str:
    return f"runs/{suite_id}_result_provenance_current.md"


def _write_markdown(path_like: str | Path, payload: dict) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Public Benchmark Result Provenance",
        "",
        f"- status: `{s['status']}`",
        f"- product_engine_result: `{s['product_engine_result']}`",
        f"- suite_id: `{s['suite_id']}`",
        f"- source_engine: `{s['source_engine']}`",
        f"- result_artifact: `{s['result_artifact']}`",
        f"- result_artifact_present: `{s['result_artifact_present']}`",
        f"- result_artifact_sha256: `{s['result_artifact_sha256']}`",
        f"- result_row_count: `{s['result_row_count']}`",
        f"- min_result_rows: `{s['min_result_rows']}`",
        f"- execution_summary_json: `{s['execution_summary_json']}`",
        f"- execution_summary_pass: `{s['execution_summary_pass']}`",
        f"- blocker_count: `{s['blocker_count']}`",
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


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fingerprint product-engine public benchmark result evidence.")
    parser.add_argument("--suite-id", required=True)
    parser.add_argument("--result-artifact", required=True)
    parser.add_argument("--execution-summary-json", default="")
    parser.add_argument("--source-engine", default="betelgeuze_product")
    parser.add_argument("--min-result-rows", type=int, default=1)
    parser.add_argument("--out-json", default="")
    parser.add_argument("--out-csv", default="")
    parser.add_argument("--out-md", default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    out_json = args.out_json or _default_out_json(args.suite_id)
    out_csv = args.out_csv or _default_out_csv(args.suite_id)
    out_md = args.out_md or _default_out_md(args.suite_id)
    payload = build_public_benchmark_result_provenance(
        suite_id=args.suite_id,
        result_artifact=_resolve(args.result_artifact),
        execution_summary_json=_resolve(args.execution_summary_json) if args.execution_summary_json else "",
        source_engine=args.source_engine,
        min_result_rows=args.min_result_rows,
    )
    write_provenance(_resolve(out_json), payload)
    write_csv_rows(_resolve(out_csv), payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
