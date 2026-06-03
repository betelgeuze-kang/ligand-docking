#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from betelgeuze_product.public_benchmark import BENCHMARK_SUITES, REQUIRED_SCORECARD_FIELDS
from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROW_CSVS = (
    "runs/lit_pcba_scorecard_row_current.csv",
    "runs/dude_z_decoy_smoke_scorecard_row_current.csv",
    "runs/pdbbind_casf_pose_affinity_scorecard_row_current.csv",
    "runs/protein_protein_docking_benchmark_v5_scorecard_row_current.csv",
    "runs/casp_archive_structure_regression_scorecard_row_current.csv",
)
DEFAULT_OUT_CSV = "runs/product_public_benchmark_scorecard_intake.csv"
DEFAULT_OUT_JSON = "runs/product_public_benchmark_scorecard_intake_sync_current.json"
DEFAULT_OUT_MD = "runs/product_public_benchmark_scorecard_intake_sync_current.md"


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _text(value: Any) -> str:
    return str(value or "").strip()


def _read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [{str(k): _text(v) for k, v in row.items()} for row in csv.DictReader(handle)]


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def build_sync_payload(row_csvs: list[str | Path]) -> dict[str, Any]:
    known_suites = {_text(suite["suite_id"]) for suite in BENCHMARK_SUITES}
    selected: dict[str, dict[str, str]] = {}
    source_rows: list[dict[str, Any]] = []
    duplicate_suite_ids: list[str] = []
    unknown_suite_ids: list[str] = []
    for row_csv in row_csvs:
        path = _resolve(row_csv)
        rows = _read_rows(path)
        source_rows.append({"row_csv": str(path), "row_count": len(rows), "present": path.exists()})
        for row in rows:
            suite_id = _text(row.get("suite_id"))
            if suite_id not in known_suites:
                unknown_suite_ids.append(suite_id or "missing_suite_id")
                continue
            if suite_id in selected:
                duplicate_suite_ids.append(suite_id)
                continue
            selected[suite_id] = {field: _text(row.get(field)) for field in REQUIRED_SCORECARD_FIELDS}
    output_rows = [selected[suite_id] for suite_id in sorted(selected)]
    missing_suite_ids = sorted(known_suites - set(selected))
    blockers: list[str] = []
    if duplicate_suite_ids:
        blockers.append("duplicate_suite_rows")
    if unknown_suite_ids:
        blockers.append("unknown_suite_rows")
    summary = {
        "packet_type": "product_public_benchmark_scorecard_intake_sync",
        "status": "product_public_benchmark_scorecard_intake_synced" if not blockers else "blocked_product_public_benchmark_scorecard_intake_sync",
        "output_row_count": len(output_rows),
        "known_suite_count": len(known_suites),
        "missing_suite_count": len(missing_suite_ids),
        "missing_suite_ids": missing_suite_ids,
        "duplicate_suite_ids": duplicate_suite_ids,
        "unknown_suite_ids": unknown_suite_ids,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "external_state_mutated": False,
        "claim_boundary": (
            "Product public benchmark scorecard intake sync only; it merges local scorecard row CSVs into the product "
            "benchmark intake CSV. It does not run benchmarks, download datasets, or mutate external state."
        ),
        "next_required_step": "Run missing benchmark scorecards, rerun this sync, then rebuild the product public benchmark contract.",
    }
    return {"summary": summary, "rows": output_rows, "sources": source_rows}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Product Public Benchmark Scorecard Intake Sync",
        "",
        f"- status: `{s['status']}`",
        f"- output_row_count: `{s['output_row_count']}`",
        f"- missing_suite_count: `{s['missing_suite_count']}`",
        f"- blocker_count: `{s['blocker_count']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Missing Suites",
        "",
    ]
    lines.extend(f"- `{suite_id}`" for suite_id in s["missing_suite_ids"]) if s["missing_suite_ids"] else lines.append("- none")
    lines.extend(["", "## Sources", "", "| source | present | rows |", "| --- | --- | --- |"])
    for row in payload["sources"]:
        lines.append(f"| `{row['row_csv']}` | `{row['present']}` | `{row['row_count']}` |")
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync individual public benchmark scorecard rows into the product benchmark intake CSV.")
    parser.add_argument("--row-csv", action="append", default=[], help="Scorecard row CSV to include; may be repeated.")
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    row_csvs = args.row_csv or list(DEFAULT_ROW_CSVS)
    payload = build_sync_payload(row_csvs)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_json(args.out_json, payload)
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
