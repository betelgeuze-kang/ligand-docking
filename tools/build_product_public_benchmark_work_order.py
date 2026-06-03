#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from betelgeuze_product.public_benchmark_work_order import build_product_public_benchmark_work_order
from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
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
        "| suite | status | metric | threshold | materialization | scorecard |",
        "| --- | --- | --- | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['suite_id']}` | `{row['work_order_status']}` | `{row['primary_metric']}` | "
            f"`{row['primary_metric_threshold']}` | `{row['materialization_status']}` | `{row['scorecard_status']}` |"
        )
    lines.extend(["", "## Commands", ""])
    for row in payload["rows"]:
        lines.extend(
            [
                f"### {row['suite_id']}",
                "",
                f"- materialization: `{row['materialization_command']}`",
                f"- scorecard: `{row['scorecard_command']}`",
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
