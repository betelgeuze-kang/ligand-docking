#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from betelgeuze_cameo.repair_preflight import build_repair_execution_preflight
from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPAIR_JSON = "runs/cameo_validation_repair_work_order_current.json"
DEFAULT_INPUT_VALIDATION_JSON = "runs/cameo_operator_input_validation_current.json"
DEFAULT_OUT_JSON = "runs/cameo_repair_execution_preflight_current.json"
DEFAULT_OUT_CSV = "runs/cameo_repair_execution_preflight_current.csv"
DEFAULT_OUT_MD = "runs/cameo_repair_execution_preflight_current.md"


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# CAMEO Repair Execution Preflight",
        "",
        f"- status: `{s['status']}`",
        f"- source_repair_status: `{s['source_repair_status']}`",
        f"- source_operator_input_validation_status: `{s['source_operator_input_validation_status']}`",
        f"- command_count: `{s['command_count']}`",
        f"- blocker_count: `{s['blocker_count']}`",
        f"- input_blocker_count: `{s['input_blocker_count']}`",
        f"- action_executed: `{s['action_executed']}`",
        f"- outbound_email_enabled: `{s['outbound_email_enabled']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        f"- native_local_accuracy_used: `{s['native_local_accuracy_used']}`",
        f"- validated_without_execution: `{s['validated_without_execution']}`",
        "",
        "## Command Checks",
        "",
        "| step | needed_now | status | input | blockers |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload.get("rows") or []:
        lines.append(
            f"| `{row['step']}` | `{row['needed_now']}` | `{row['preflight_status']}` | "
            f"`{row['input_value']}` | `{row['blockers']}` |"
        )
    lines.extend(["", "## Blockers", ""])
    blockers = payload.get("blockers") or []
    if blockers:
        lines.extend(
            f"- `{blocker['code']}`"
            f"{' step ' + str(blocker.get('step')) if blocker.get('step') else ''}: {blocker['reason']}"
            for blocker in blockers
        )
    else:
        lines.append("- none")
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Preflight local CAMEO repair commands without executing them.")
    parser.add_argument("--repair-json", default=DEFAULT_REPAIR_JSON)
    parser.add_argument("--operator-input-validation-json", default=DEFAULT_INPUT_VALIDATION_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_repair_execution_preflight(
        _read_json(args.repair_json),
        _read_json(args.operator_input_validation_json),
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
