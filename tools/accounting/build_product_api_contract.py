#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from betelgeuze_product.api_contract import build_product_api_contract
from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_JSON = "runs/product_api_contract_current.json"
DEFAULT_OUT_CSV = "runs/product_api_contract_current.csv"
DEFAULT_OUT_MD = "runs/product_api_contract_current.md"


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _write_json(path_like: str | Path, payload: dict) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Product API Contract",
        "",
        f"- status: `{s['status']}`",
        f"- api_contract_ready: `{s['api_contract_ready']}`",
        f"- check_count: `{s['check_count']}`",
        f"- pass_count: `{s['pass_count']}`",
        f"- blocker_count: `{s['blocker_count']}`",
        f"- expected_route_count: `{s['expected_route_count']}`",
        f"- missing_route_count: `{s['missing_route_count']}`",
        f"- request_model_count: `{s['request_model_count']}`",
        f"- missing_request_model_field_count: `{s['missing_request_model_field_count']}`",
        f"- docking_response_missing_key_count: `{s['docking_response_missing_key_count']}`",
        f"- status_response_missing_key_count: `{s['status_response_missing_key_count']}`",
        f"- status_response_domain_missing_key_count: `{s['status_response_domain_missing_key_count']}`",
        f"- server_started: `{s['server_started']}`",
        f"- execution_enabled: `{s['execution_enabled']}`",
        f"- docking_results_emitted: `{s['docking_results_emitted']}`",
        f"- license_file_written: `{s['license_file_written']}`",
        f"- bundle_assembled: `{s['bundle_assembled']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Checks",
        "",
        "| check | status | observed | required | artifact | reason |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['check']}` | `{row['status']}` | `{row['observed']}` | `{row['required']}` | "
            f"`{row['artifact_path']}` | {row['reason']} |"
        )
    lines.extend(["", "## Blockers", ""])
    if payload["blockers"]:
        lines.extend(f"- `{blocker['code']}`: {blocker['reason']}" for blocker in payload["blockers"])
    else:
        lines.append("- none")
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the product API contract from local source files.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_product_api_contract(root=args.root)
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
