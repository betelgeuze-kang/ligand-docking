#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shlex
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_READINESS_JSON = "runs/cameo_validation_readiness_gate_current.json"
DEFAULT_OUT_JSON = "runs/cameo_validation_repair_work_order_current.json"
DEFAULT_OUT_CSV = "runs/cameo_validation_repair_work_order_current.csv"
DEFAULT_OUT_MD = "runs/cameo_validation_repair_work_order_current.md"
CLAIM_BOUNDARY = (
    "CAMEO validation repair work order only; it records local commands needed to rebuild missing CAMEO artifacts. "
    "It does not submit predictions, send email, register a CAMEO server, use local native accuracy, or mutate external state."
)


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


def _text(value: Any) -> str:
    return str(value or "").strip()


def _quote(parts: list[str]) -> str:
    return " ".join(shlex.quote(str(part)) for part in parts)


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _blocked_stages(readiness_packet: dict[str, Any]) -> set[str]:
    stages: set[str] = set()
    for blocker in readiness_packet.get("blockers", []) or []:
        if isinstance(blocker, dict) and _text(blocker.get("stage")):
            stages.add(_text(blocker.get("stage")))
    for row in readiness_packet.get("rows", []) or []:
        if isinstance(row, dict) and not bool(row.get("ready", False)):
            stages.add(_text(row.get("stage")))
    return stages


def build_work_order(
    readiness_packet: dict[str, Any],
    *,
    readiness_json: str = DEFAULT_READINESS_JSON,
    candidates_csv: str = "OPERATOR_FILL_CAMEO_CANDIDATES_CSV",
    models_csv: str = "OPERATOR_FILL_CAMEO_SELECTED_MODELS_CSV",
    official_results_csv: str = "",
    target_id: str = "",
) -> dict[str, Any]:
    summary = _summary(readiness_packet)
    status = _text(summary.get("status"))
    blocked_stages = _blocked_stages(readiness_packet)
    target = target_id or _text(summary.get("target_id"))
    input_missing: list[str] = []
    if "selection" in blocked_stages and candidates_csv.startswith("OPERATOR_FILL"):
        input_missing.append("candidates_csv")
    if "format" in blocked_stages and models_csv.startswith("OPERATOR_FILL"):
        input_missing.append("models_csv")

    selection_cmd = [
        "python3",
        "tools/build_cameo_model1_selection_packet.py",
        "--candidates-csv",
        candidates_csv,
    ]
    if target:
        selection_cmd.extend(["--target-id", target])

    format_cmd = [
        "python3",
        "tools/build_cameo_format_validation_packet.py",
        "--models-csv",
        models_csv,
    ]
    if target:
        format_cmd.extend(["--target-id", target])

    handoff_cmd = ["python3", "tools/build_cameo_dry_run_handoff_packet.py"]
    performance_cmd = ["python3", "tools/build_cameo_performance_scorecard.py"]
    if official_results_csv:
        performance_cmd.extend(["--results-csv", official_results_csv])
    readiness_cmd = ["python3", "tools/build_cameo_validation_readiness_gate.py"]

    rows = [
        {
            "step": "selection",
            "needed_now": "selection" in blocked_stages,
            "input_required": "candidates_csv",
            "input_value": candidates_csv,
            "command": _quote(selection_cmd),
            "action_executed": False,
        },
        {
            "step": "format",
            "needed_now": "format" in blocked_stages,
            "input_required": "models_csv",
            "input_value": models_csv,
            "command": _quote(format_cmd),
            "action_executed": False,
        },
        {
            "step": "handoff",
            "needed_now": "handoff" in blocked_stages,
            "input_required": "",
            "input_value": "",
            "command": _quote(handoff_cmd),
            "action_executed": False,
        },
        {
            "step": "performance",
            "needed_now": "performance" in blocked_stages,
            "input_required": "official_results_csv_optional",
            "input_value": official_results_csv,
            "command": _quote(performance_cmd),
            "action_executed": False,
        },
        {
            "step": "readiness_refresh",
            "needed_now": True,
            "input_required": "",
            "input_value": "",
            "command": _quote(readiness_cmd),
            "action_executed": False,
        },
    ]

    if not readiness_packet:
        work_status = "blocked_cameo_validation_repair_work_order"
        blockers = [{"code": "readiness_artifact_missing", "severity": "hard", "reason": "CAMEO validation readiness artifact is required."}]
    else:
        blockers = []
        if status in {"cameo_validation_evidence_ready", "cameo_validation_pending_official_results"} and not blocked_stages:
            work_status = "cameo_validation_repair_not_required"
        elif input_missing:
            work_status = "operator_input_required"
        else:
            work_status = "cameo_validation_repair_work_order_ready"

    work_summary = {
        "packet_type": "cameo_validation_repair_work_order",
        "status": work_status,
        "source_readiness_json": readiness_json,
        "source_readiness_status": status,
        "blocked_stage_count": len(blocked_stages),
        "blocked_stages": sorted(blocked_stages),
        "operator_input_missing_count": len(input_missing),
        "operator_input_missing": input_missing,
        "command_count": len(rows),
        "action_executed": False,
        "outbound_email_enabled": False,
        "external_state_mutated": False,
        "native_local_accuracy_used": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Fill missing operator inputs, then run the listed local artifact-build commands in order."
            if work_status == "operator_input_required"
            else (
                "Run the listed local artifact-build commands in order, then refresh the goal readiness rollup."
                if work_status == "cameo_validation_repair_work_order_ready"
                else (
                    "No repair is required for the current CAMEO validation readiness state."
                    if work_status == "cameo_validation_repair_not_required"
                    else "Generate CAMEO validation readiness first."
                )
            )
        ),
    }
    return {"summary": work_summary, "blockers": blockers, "rows": rows}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# CAMEO Validation Repair Work Order",
        "",
        f"- status: `{s['status']}`",
        f"- source_readiness_status: `{s['source_readiness_status']}`",
        f"- blocked_stages: `{','.join(s['blocked_stages'])}`",
        f"- operator_input_missing_count: `{s['operator_input_missing_count']}`",
        f"- action_executed: `{s['action_executed']}`",
        f"- outbound_email_enabled: `{s['outbound_email_enabled']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Commands",
        "",
        "| step | needed_now | input_required | command |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(f"| `{row['step']}` | `{row['needed_now']}` | `{row['input_required']}` | `{row['command']}` |")
    lines.extend(["", "## Blockers", ""])
    blockers = payload.get("blockers") or []
    if blockers:
        lines.extend(f"- `{blocker['code']}`: {blocker['reason']}" for blocker in blockers)
    else:
        lines.append("- none")
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a local CAMEO validation repair work order.")
    parser.add_argument("--readiness-json", default=DEFAULT_READINESS_JSON)
    parser.add_argument("--candidates-csv", default="OPERATOR_FILL_CAMEO_CANDIDATES_CSV")
    parser.add_argument("--models-csv", default="OPERATOR_FILL_CAMEO_SELECTED_MODELS_CSV")
    parser.add_argument("--official-results-csv", default="")
    parser.add_argument("--target-id", default="")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_work_order(
        _read_json(args.readiness_json),
        readiness_json=str(args.readiness_json),
        candidates_csv=str(args.candidates_csv),
        models_csv=str(args.models_csv),
        official_results_csv=str(args.official_results_csv),
        target_id=str(args.target_id),
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
