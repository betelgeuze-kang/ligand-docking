#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import shlex
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_LAUNCH_PACKET_JSON = "runs/casp17_prediction_launch_packet_current.json"
DEFAULT_ATTEMPT_DIR = "runs/casp17_target_attempts_current"
DEFAULT_OUT_JSON = "runs/casp17_prediction_batch_gate_current.json"
DEFAULT_OUT_CSV = "runs/casp17_prediction_batch_gate_current.csv"
DEFAULT_OUT_MD = "runs/casp17_prediction_batch_gate_current.md"

STEP_ORDER = ("backend_job", "contract", "conversion", "import", "validation", "scorecard", "submission_gate")


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _artifact(path_like: str | Path) -> str:
    path = _resolve(path_like).resolve()
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _read_json(path_like: str | Path) -> dict[str, Any]:
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


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    if not fieldnames:
        fieldnames = ["target_id"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _shell_join(parts: list[str]) -> str:
    return " ".join(shlex.quote(str(part)) for part in parts)


def _launch_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    return rows if isinstance(rows, list) else []


def _attempt_paths(attempt_dir: str | Path, target_id: str) -> dict[str, str]:
    root = _resolve(attempt_dir)
    return {
        "out_json": _artifact(root / f"{target_id}_attempt.json"),
        "out_csv": _artifact(root / f"{target_id}_attempt.csv"),
        "out_md": _artifact(root / f"{target_id}_attempt.md"),
    }


def _attempt_command(args: argparse.Namespace, target_id: str) -> list[str]:
    paths = _attempt_paths(args.attempt_dir, target_id)
    command = [
        "python3",
        "tools/run_casp17_target_attempt_gate.py",
        "--target-id",
        target_id,
        "--launch-packet-json",
        args.launch_packet_json,
        "--stop-after",
        args.stop_after,
        "--timeout-seconds",
        str(args.timeout_seconds),
        "--out-json",
        paths["out_json"],
        "--out-csv",
        paths["out_csv"],
        "--out-md",
        paths["out_md"],
    ]
    if _text(args.author_code):
        command.extend(["--author-code", _text(args.author_code)])
    if args.execute:
        command.append("--execute")
    return command


def _selected_rows(payload: dict[str, Any], target_limit: int) -> list[dict[str, Any]]:
    rows = _launch_rows(payload)
    if target_limit > 0:
        return rows[:target_limit]
    return rows


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    launch_packet = _read_json(args.launch_packet_json)
    rows: list[dict[str, Any]] = []
    batch_status = "ready_not_executed"
    blocker_count = 0
    completed_count = 0
    failed_count = 0
    executed_count = 0
    planned_count = 0
    ready_count = 0
    blocked_count = 0

    for launch_row in _selected_rows(launch_packet, args.target_limit):
        target_id = _text(launch_row.get("target_id")).upper()
        launch_status = _text(launch_row.get("launch_status"))
        command = _attempt_command(args, target_id) if target_id else []
        paths = _attempt_paths(args.attempt_dir, target_id) if target_id else {"out_json": "", "out_csv": "", "out_md": ""}
        row = {
            "target_id": target_id,
            "target_kind": _text(launch_row.get("target_kind")),
            "launch_status": launch_status,
            "batch_status": "",
            "returncode": "",
            "attempt_status": "",
            "submission_decision": "",
            "attempt_json": paths["out_json"],
            "command": _shell_join(command) if command else "",
            "blocker": "",
        }
        if not target_id:
            row["batch_status"] = "blocked"
            row["blocker"] = "target_id_missing"
            blocked_count += 1
            blocker_count += 1
            rows.append(row)
            continue
        if launch_status != "ready_to_launch":
            row["batch_status"] = "blocked_by_launch_packet"
            row["blocker"] = _text(launch_row.get("blockers")) or f"launch_status:{launch_status}"
            blocked_count += 1
            blocker_count += 1
            rows.append(row)
            continue
        ready_count += 1
        if not args.execute:
            row["batch_status"] = "planned"
            planned_count += 1
            rows.append(row)
            continue

        executed_count += 1
        run = subprocess.run(command, check=False, capture_output=True, text=True, cwd=str(ROOT), timeout=int(args.timeout_seconds) + 30)
        row["returncode"] = int(run.returncode)
        attempt_payload = _read_json(paths["out_json"])
        attempt_summary = attempt_payload.get("summary") if isinstance(attempt_payload.get("summary"), dict) else {}
        row["attempt_status"] = _text(attempt_summary.get("attempt_status"))
        row["submission_decision"] = _text(attempt_summary.get("submission_decision"))
        if run.returncode == 0:
            row["batch_status"] = "completed"
            completed_count += 1
        else:
            row["batch_status"] = "failed"
            row["blocker"] = _text(attempt_summary.get("blockers")) or (run.stderr[-500:] if run.stderr else "target_attempt_failed")
            failed_count += 1
            blocker_count += 1
            rows.append(row)
            if not args.continue_on_error:
                batch_status = "blocked"
                break
            continue
        rows.append(row)

    if args.execute and failed_count == 0 and rows:
        batch_status = f"completed_to_{args.stop_after}"
    elif not rows:
        batch_status = "blocked_no_launch_rows"
        blocker_count += 1
    elif blocked_count and not args.execute:
        batch_status = "blocked_by_launch_packet"

    summary = {
        "packet_type": "casp17_prediction_batch_gate",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "launch_packet_json": _artifact(args.launch_packet_json),
        "attempt_dir": _artifact(args.attempt_dir),
        "execute": bool(args.execute),
        "stop_after": args.stop_after,
        "target_count": len(rows),
        "ready_count": ready_count,
        "planned_count": planned_count,
        "executed_count": executed_count,
        "completed_count": completed_count,
        "blocked_count": blocked_count,
        "failed_count": failed_count,
        "blocker_count": blocker_count,
        "batch_status": batch_status,
        "claim_boundary": "CASP17 batch attempt orchestration only; not public submission or official performance evidence.",
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Prediction Batch Gate",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- launch packet: `{summary['launch_packet_json']}`",
        f"- execute: `{summary['execute']}`",
        f"- stop after: `{summary['stop_after']}`",
        f"- batch status: `{summary['batch_status']}`",
        f"- targets ready/planned/executed/completed/blocked/failed: "
        f"`{summary['ready_count']}/{summary['planned_count']}/{summary['executed_count']}/"
        f"{summary['completed_count']}/{summary['blocked_count']}/{summary['failed_count']}`",
        "",
        "## Rows",
        "",
        "| target | kind | launch | batch | returncode | attempt | submission | blocker | attempt json |",
        "| --- | --- | --- | --- | ---: | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row.get('target_kind') or '-'}` | `{row['launch_status']}` | "
            f"`{row['batch_status']}` | `{row.get('returncode', '')}` | `{row.get('attempt_status') or '-'}` | "
            f"`{row.get('submission_decision') or '-'}` | {row.get('blocker') or '-'} | `{row.get('attempt_json') or '-'}` |"
        )
    if not payload["rows"]:
        lines.append("| - | - | - | `no_rows` | - | - | - | - | - |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plan or execute CASP17 prediction attempts across every launch row.")
    parser.add_argument("--launch-packet-json", default=DEFAULT_LAUNCH_PACKET_JSON)
    parser.add_argument("--attempt-dir", default=DEFAULT_ATTEMPT_DIR)
    parser.add_argument("--author-code", default="")
    parser.add_argument("--execute", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--stop-after", choices=STEP_ORDER, default="submission_gate")
    parser.add_argument("--target-limit", type=int, default=0)
    parser.add_argument("--timeout-seconds", type=int, default=21600)
    parser.add_argument("--continue-on-error", action="store_true")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)
    if args.execute and payload["summary"]["failed_count"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
