#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from betelgeuze_cameo.receiver_smoke import build_cameo_receiver_smoke_contract
from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/cameo_receiver_smoke_contract_current.json"
DEFAULT_OUT_CSV = "runs/cameo_receiver_smoke_contract_current.csv"
DEFAULT_OUT_MD = "runs/cameo_receiver_smoke_contract_current.md"
DEFAULT_API_DEPENDENCY_JSON = "runs/cameo_api_dependency_readiness_current.json"


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _read_json_if_present(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# CAMEO Receiver Smoke Contract",
        "",
        f"- status: `{s['status']}`",
        f"- blocker_count: `{s['blocker_count']}`",
        f"- warning_count: `{s['warning_count']}`",
        f"- source_route_present: `{s['source_route_present']}`",
        f"- source_api_dependency_status: `{s['source_api_dependency_status']}`",
        f"- api_dependency_ready: `{s['api_dependency_ready']}`",
        f"- api_dependency_blocker_count: `{s['api_dependency_blocker_count']}`",
        f"- runtime_smoke_requested: `{s['runtime_smoke_requested']}`",
        f"- runtime_dependency_present: `{s['runtime_dependency_present']}`",
        f"- api_import_ok: `{s['api_import_ok']}`",
        f"- post_status_code: `{s['post_status_code']}`",
        f"- post_200_ok: `{s['post_200_ok']}`",
        f"- ledger_written: `{s['ledger_written']}`",
        f"- prediction_generation_enabled: `{s['prediction_generation_enabled']}`",
        f"- outbound_email_enabled: `{s['outbound_email_enabled']}`",
        f"- server_started: `{s['server_started']}`",
        f"- server_registration_mutated: `{s['server_registration_mutated']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Checks",
        "",
        "| check | status | observed | required |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(f"| `{row['check']}` | `{row['status']}` | `{row['observed']}` | `{row['required']}` |")

    lines.extend(["", "## Blockers", ""])
    blockers = payload.get("blockers") or []
    if blockers:
        lines.extend(f"- `{blocker['code']}`: {blocker['reason']}" for blocker in blockers)
    else:
        lines.append("- none")

    lines.extend(["", "## Warnings", ""])
    warnings = payload.get("warnings") or []
    if warnings:
        lines.extend(f"- `{warning['code']}`: {warning['reason']}" for warning in warnings)
    else:
        lines.append("- none")

    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a local CAMEO receiver smoke contract without starting a public server.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--api-dependency-json", default=DEFAULT_API_DEPENDENCY_JSON)
    parser.add_argument("--no-runtime-smoke", action="store_true")
    parser.add_argument("--smoke-results-dir", default="")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_cameo_receiver_smoke_contract(
        root=args.root,
        run_runtime_smoke=not args.no_runtime_smoke,
        smoke_results_dir=args.smoke_results_dir,
        api_dependency_packet=_read_json_if_present(args.api_dependency_json),
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
