#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from betelgeuze_cameo.readiness import build_cameo_validation_readiness_gate
from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SELECTION_JSON = "runs/cameo_model1_selection_packet_current.json"
DEFAULT_FORMAT_JSON = "runs/cameo_format_validation_packet_current.json"
DEFAULT_HANDOFF_JSON = "runs/cameo_dry_run_handoff_packet_current.json"
DEFAULT_PERFORMANCE_JSON = "runs/cameo_performance_scorecard_current.json"
DEFAULT_OUT_JSON = "runs/cameo_validation_readiness_gate_current.json"
DEFAULT_OUT_CSV = "runs/cameo_validation_readiness_gate_current.csv"
DEFAULT_OUT_MD = "runs/cameo_validation_readiness_gate_current.md"


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
        "# CAMEO Validation Readiness Gate",
        "",
        f"- status: `{s['status']}`",
        f"- target_id: `{s['target_id']}`",
        f"- ready_stage_count: `{s['ready_stage_count']}` / `{s['stage_count']}`",
        f"- missing_stage_count: `{s['missing_stage_count']}`",
        f"- blocker_count: `{s['blocker_count']}`",
        f"- performance_status: `{s['performance_status']}`",
        f"- official_cameo_results_used: `{s['official_cameo_results_used']}`",
        f"- native_local_accuracy_used: `{s['native_local_accuracy_used']}`",
        f"- outbound_email_enabled: `{s['outbound_email_enabled']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Stages",
        "",
        "| stage | present | ready | status | path |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload.get("rows") or []:
        lines.append(
            f"| `{row.get('stage', '')}` | `{row.get('present')}` | `{row.get('ready')}` | "
            f"`{row.get('status_value', '')}` | `{row.get('path', '')}` |"
        )
    lines.extend(["", "## Blockers", ""])
    blockers = payload.get("blockers") or []
    if blockers:
        lines.extend(f"- `{blocker['code']}` ({blocker['stage']}): {blocker['reason']}" for blocker in blockers)
    else:
        lines.append("- none")
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a fail-closed CAMEO validation readiness gate.")
    parser.add_argument("--selection-json", default=DEFAULT_SELECTION_JSON)
    parser.add_argument("--format-json", default=DEFAULT_FORMAT_JSON)
    parser.add_argument("--handoff-json", default=DEFAULT_HANDOFF_JSON)
    parser.add_argument("--performance-json", default=DEFAULT_PERFORMANCE_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_cameo_validation_readiness_gate(
        selection_packet=_read_json_if_present(args.selection_json),
        format_packet=_read_json_if_present(args.format_json),
        handoff_packet=_read_json_if_present(args.handoff_json),
        performance_packet=_read_json_if_present(args.performance_json),
        selection_path=args.selection_json,
        format_path=args.format_json,
        handoff_path=args.handoff_json,
        performance_path=args.performance_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
