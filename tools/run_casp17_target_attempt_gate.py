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
DEFAULT_INTAKE_CSV = "runs/casp17_target_intake_seed_with_sequences_current.csv"
DEFAULT_PREDICTION_DIR = "runs/casp17_predictions_current"
DEFAULT_IMPORT_JSON = "runs/casp17_prediction_import_packet_current.json"
DEFAULT_IMPORT_CSV = "runs/casp17_prediction_import_packet_current.csv"
DEFAULT_IMPORT_MD = "runs/casp17_prediction_import_packet_current.md"
DEFAULT_IMPORTED_INTAKE_CSV = "runs/casp17_target_intake_prediction_imported_current.csv"
DEFAULT_VALIDATION_DIR = "runs/casp17_validations_current"
DEFAULT_VALIDATION_JSON = "runs/casp17_prediction_validation_batch_current.json"
DEFAULT_VALIDATION_CSV = "runs/casp17_prediction_validation_batch_current.csv"
DEFAULT_VALIDATION_MD = "runs/casp17_prediction_validation_batch_current.md"
DEFAULT_VALIDATED_INTAKE_CSV = "runs/casp17_target_intake_validated_current.csv"
DEFAULT_SCORECARD_DIR = "runs/casp17_internal_scorecards_current"
DEFAULT_SCORECARD_JSON = "runs/casp17_internal_scorecard_batch_current.json"
DEFAULT_SCORECARD_CSV = "runs/casp17_internal_scorecard_batch_current.csv"
DEFAULT_SCORECARD_MD = "runs/casp17_internal_scorecard_batch_current.md"
DEFAULT_SCORED_INTAKE_CSV = "runs/casp17_target_intake_scored_current.csv"
DEFAULT_SUBMISSION_GATE_JSON = "runs/casp17_submission_gate_packet_current.json"
DEFAULT_SUBMISSION_GATE_CSV = "runs/casp17_submission_gate_packet_current.csv"
DEFAULT_SUBMISSION_GATE_MD = "runs/casp17_submission_gate_packet_current.md"
DEFAULT_OUT_JSON = "runs/casp17_target_attempt_gate_current.json"
DEFAULT_OUT_CSV = "runs/casp17_target_attempt_gate_current.csv"
DEFAULT_OUT_MD = "runs/casp17_target_attempt_gate_current.md"

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
    fieldnames = [
        "step",
        "status",
        "returncode",
        "command",
        "stdout_tail",
        "stderr_tail",
        "blocker",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _launch_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    return rows if isinstance(rows, list) else []


def _row_for_target(payload: dict[str, Any], target_id: str) -> dict[str, Any]:
    target_upper = target_id.upper()
    for row in _launch_rows(payload):
        if isinstance(row, dict) and _text(row.get("target_id")).upper() == target_upper:
            return row
    return {}


def _shell_join(parts: list[str]) -> str:
    return " ".join(shlex.quote(str(part)) for part in parts)


def _replace_author_code(command: str, author_code: str) -> str:
    if "<CASP_AUTHOR_CODE>" not in command:
        return command
    return command.replace("<CASP_AUTHOR_CODE>", author_code)


def _command_rows(row: dict[str, Any], args: argparse.Namespace) -> list[dict[str, Any]]:
    conversion_command = _replace_author_code(_text(row.get("conversion_command")), _text(args.author_code))
    return [
        {"step": "backend_job", "command": _text(row.get("command"))},
        {"step": "contract", "command": _text(row.get("contract_command"))},
        {"step": "conversion", "command": conversion_command},
        {
            "step": "import",
            "command": _shell_join(
                [
                    "python3",
                    "tools/build_casp17_prediction_import_packet.py",
                    "--intake-csv",
                    args.intake_csv,
                    "--prediction-dir",
                    args.prediction_dir,
                    "--out-json",
                    args.import_json,
                    "--out-csv",
                    args.import_csv,
                    "--out-md",
                    args.import_md,
                    "--out-intake-csv",
                    args.imported_intake_csv,
                ]
            ),
        },
        {
            "step": "validation",
            "command": _shell_join(
                [
                    "python3",
                    "tools/build_casp17_prediction_validation_batch.py",
                    "--intake-csv",
                    args.imported_intake_csv,
                    "--out-dir",
                    args.validation_dir,
                    "--out-json",
                    args.validation_json,
                    "--out-csv",
                    args.validation_csv,
                    "--out-md",
                    args.validation_md,
                    "--out-intake-csv",
                    args.validated_intake_csv,
                ]
            ),
        },
        {
            "step": "scorecard",
            "command": _shell_join(
                [
                    "python3",
                    "tools/build_casp17_internal_scorecard_batch.py",
                    "--intake-csv",
                    args.validated_intake_csv,
                    "--out-dir",
                    args.scorecard_dir,
                    "--out-json",
                    args.scorecard_json,
                    "--out-csv",
                    args.scorecard_csv,
                    "--out-md",
                    args.scorecard_md,
                    "--out-intake-csv",
                    args.scored_intake_csv,
                ]
            ),
        },
        {
            "step": "submission_gate",
            "command": _shell_join(
                [
                    "python3",
                    "tools/build_casp17_submission_gate_packet.py",
                    "--intake-csv",
                    args.scored_intake_csv,
                    "--out-json",
                    args.submission_gate_json,
                    "--out-csv",
                    args.submission_gate_csv,
                    "--out-md",
                    args.submission_gate_md,
                ]
            ),
        },
    ]


def _step_limit(stop_after: str) -> set[str]:
    stop_index = STEP_ORDER.index(stop_after)
    return set(STEP_ORDER[: stop_index + 1])


def _run_step(command: str, timeout_seconds: int) -> tuple[int, str, str]:
    try:
        run = subprocess.run(
            shlex.split(command),
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            cwd=str(ROOT),
        )
        return int(run.returncode), run.stdout or "", run.stderr or ""
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else str(exc.stdout or "")
        stderr = exc.stderr.decode("utf-8", errors="replace") if isinstance(exc.stderr, bytes) else str(exc.stderr or "")
        return 124, stdout, stderr
    except Exception as exc:  # noqa: BLE001 - preserve failure as packet evidence.
        return 125, "", f"{type(exc).__name__}: {exc}"


def _submission_decision(path_like: str | Path, target_id: str) -> str:
    payload = _read_json(path_like)
    rows = payload.get("target_rows")
    if not isinstance(rows, list):
        return ""
    target_upper = target_id.upper()
    for row in rows:
        if isinstance(row, dict) and _text(row.get("target_id")).upper() == target_upper:
            return _text(row.get("submission_decision"))
    return ""


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    target_id = _text(args.target_id).upper()
    launch_packet = _read_json(args.launch_packet_json)
    launch_row = _row_for_target(launch_packet, target_id)
    rows: list[dict[str, Any]] = []
    blockers: list[str] = []
    status = "blocked_by_launch_packet"

    if not launch_row:
        blockers.append("launch_row_missing")
        rows.append({"step": "launch_packet", "status": "blocked", "returncode": "", "command": "", "blocker": "launch_row_missing"})
    elif _text(launch_row.get("launch_status")) != "ready_to_launch":
        blocker = _text(launch_row.get("blockers")) or f"launch_status:{_text(launch_row.get('launch_status'))}"
        blockers.append(blocker)
        rows.append({"step": "launch_packet", "status": "blocked", "returncode": "", "command": "", "blocker": blocker})
    else:
        command_rows = _command_rows(launch_row, args)
        stop_steps = _step_limit(args.stop_after)
        selected_rows = [row for row in command_rows if row["step"] in stop_steps]
        if not args.execute:
            status = "ready_not_executed"
            rows.extend({**row, "status": "planned", "returncode": "", "stdout_tail": "", "stderr_tail": "", "blocker": ""} for row in selected_rows)
        else:
            status = f"completed_to_{args.stop_after}"
            for row in selected_rows:
                step = row["step"]
                command = _text(row.get("command"))
                blocker = ""
                if not command:
                    blocker = f"{step}_command_missing"
                if step == "conversion" and "<CASP_AUTHOR_CODE>" in _text(launch_row.get("conversion_command")) and not _text(args.author_code):
                    blocker = "missing_author_code"
                if blocker:
                    blockers.append(blocker)
                    rows.append({**row, "status": "blocked", "returncode": "", "stdout_tail": "", "stderr_tail": "", "blocker": blocker})
                    status = "blocked"
                    break
                returncode, stdout, stderr = _run_step(command, timeout_seconds=args.timeout_seconds)
                step_status = "pass" if returncode == 0 else "fail"
                rows.append(
                    {
                        **row,
                        "status": step_status,
                        "returncode": returncode,
                        "stdout_tail": stdout[-1000:],
                        "stderr_tail": stderr[-1000:],
                        "blocker": "" if returncode == 0 else f"{step}_failed",
                    }
                )
                if returncode != 0:
                    blockers.append(f"{step}_failed")
                    status = "blocked"
                    break

    submission_decision = _submission_decision(args.submission_gate_json, target_id)
    summary = {
        "packet_type": "casp17_target_attempt_gate",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "target_id": target_id,
        "launch_packet_json": _artifact(args.launch_packet_json),
        "execute": bool(args.execute),
        "stop_after": args.stop_after,
        "attempt_status": status,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "submission_decision": submission_decision,
        "claim_boundary": "Single-target CASP17 attempt orchestration only; not public submission or official performance evidence.",
    }
    return {"summary": summary, "steps": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Target Attempt Gate",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- target: `{summary['target_id']}`",
        f"- execute: `{summary['execute']}`",
        f"- stop after: `{summary['stop_after']}`",
        f"- attempt status: `{summary['attempt_status']}`",
        f"- blockers: `{';'.join(summary['blockers']) if summary['blockers'] else '-'}`",
        f"- submission decision: `{summary['submission_decision'] or '-'}`",
        "",
        "## Steps",
        "",
        "| step | status | returncode | blocker | command |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["steps"]:
        lines.append(
            f"| `{row['step']}` | `{row.get('status', '')}` | `{row.get('returncode', '')}` | "
            f"`{row.get('blocker', '') or '-'}` | `{row.get('command', '') or '-'}` |"
        )
    if not payload["steps"]:
        lines.append("| - | `no_steps` | - | - | - |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run or plan one fail-closed CASP17 target attempt from launch row to gate.")
    parser.add_argument("--target-id", required=True)
    parser.add_argument("--launch-packet-json", default=DEFAULT_LAUNCH_PACKET_JSON)
    parser.add_argument("--author-code", default="")
    parser.add_argument("--execute", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--stop-after", choices=STEP_ORDER, default="submission_gate")
    parser.add_argument("--timeout-seconds", type=int, default=21600)
    parser.add_argument("--intake-csv", default=DEFAULT_INTAKE_CSV)
    parser.add_argument("--prediction-dir", default=DEFAULT_PREDICTION_DIR)
    parser.add_argument("--import-json", default=DEFAULT_IMPORT_JSON)
    parser.add_argument("--import-csv", default=DEFAULT_IMPORT_CSV)
    parser.add_argument("--import-md", default=DEFAULT_IMPORT_MD)
    parser.add_argument("--imported-intake-csv", default=DEFAULT_IMPORTED_INTAKE_CSV)
    parser.add_argument("--validation-dir", default=DEFAULT_VALIDATION_DIR)
    parser.add_argument("--validation-json", default=DEFAULT_VALIDATION_JSON)
    parser.add_argument("--validation-csv", default=DEFAULT_VALIDATION_CSV)
    parser.add_argument("--validation-md", default=DEFAULT_VALIDATION_MD)
    parser.add_argument("--validated-intake-csv", default=DEFAULT_VALIDATED_INTAKE_CSV)
    parser.add_argument("--scorecard-dir", default=DEFAULT_SCORECARD_DIR)
    parser.add_argument("--scorecard-json", default=DEFAULT_SCORECARD_JSON)
    parser.add_argument("--scorecard-csv", default=DEFAULT_SCORECARD_CSV)
    parser.add_argument("--scorecard-md", default=DEFAULT_SCORECARD_MD)
    parser.add_argument("--scored-intake-csv", default=DEFAULT_SCORED_INTAKE_CSV)
    parser.add_argument("--submission-gate-json", default=DEFAULT_SUBMISSION_GATE_JSON)
    parser.add_argument("--submission-gate-csv", default=DEFAULT_SUBMISSION_GATE_CSV)
    parser.add_argument("--submission-gate-md", default=DEFAULT_SUBMISSION_GATE_MD)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["steps"])
    _write_md(args.out_md, payload)
    if args.execute and payload["summary"]["attempt_status"] == "blocked":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
