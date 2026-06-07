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

from tools import convert_casp17_ts_prediction_from_pdb as converter


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_RAW_GATE_JSON = "runs/casp17_internal_physics_raw_gate_packet_current.json"
DEFAULT_LAUNCH_PACKET_JSON = "runs/casp17_prediction_launch_packet_current.json"
DEFAULT_INTAKE_CSV = "runs/casp17_target_intake_seed_with_sequences_current.csv"
DEFAULT_PREDICTION_DIR = "runs/casp17_predictions_current"
DEFAULT_OUT_DIR = "runs/casp17_internal_physics_ts_gate_current"
DEFAULT_OUT_JSON = "runs/casp17_internal_physics_ts_gate_batch_current.json"
DEFAULT_OUT_CSV = "runs/casp17_internal_physics_ts_gate_batch_current.csv"
DEFAULT_OUT_MD = "runs/casp17_internal_physics_ts_gate_batch_current.md"

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

STEP_ORDER = ("conversion", "import", "validation", "scorecard", "submission_gate")
PLACEHOLDER_AUTHOR_CODES = {"", "TEST", "PLACEHOLDER", "<CASP_AUTHOR_CODE>", "CASP_AUTHOR_CODE", "XXXX", "TODO"}


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


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = []
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


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Internal Physics TS Gate Batch",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- execute: `{summary['execute']}`",
        f"- stop after: `{summary['stop_after']}`",
        f"- batch status: `{summary['batch_status']}`",
        f"- target count: `{summary['target_count']}`",
        f"- converted/planned/blocked/failed: `{summary['converted_count']}/{summary['planned_count']}/{summary['blocked_count']}/{summary['failed_count']}`",
        f"- downstream steps completed: `{summary['downstream_completed_steps']}`",
        f"- prediction dir: `{summary['prediction_dir']}`",
        "",
        "## Rows",
        "",
        "| target | raw gate | ts status | atom count | blocker | output TS |",
        "| --- | --- | --- | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['raw_gate_status']}` | `{row['ts_conversion_status']}` | "
            f"`{row.get('atom_count', 0)}` | {row.get('blockers') or '-'} | `{row.get('ts_pdb') or '-'}` |"
        )
    if not payload["rows"]:
        lines.append("| - | - | `no_rows` | 0 | - | - |")
    lines.extend(["", "## Downstream Steps", ""])
    for step in payload.get("downstream_steps", []):
        lines.append(f"- `{step['step']}`: `{step['status']}` returncode=`{step['returncode']}` blocker=`{step.get('blocker') or '-'}`")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    return rows if isinstance(rows, list) else []


def _launch_index(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {_text(row.get("target_id")).upper(): row for row in _rows(payload) if isinstance(row, dict)}


def _author_code_blocker(author_code: str) -> str:
    text = _text(author_code)
    if text.upper() in PLACEHOLDER_AUTHOR_CODES:
        return "missing_or_placeholder_author_code"
    if len(text) < 3:
        return "author_code_too_short"
    if any(char.isspace() for char in text):
        return "author_code_contains_whitespace"
    return ""


def _shell_join(parts: list[str]) -> str:
    return " ".join(shlex.quote(str(part)) for part in parts)


def _target_paths(out_dir: Path, target_id: str) -> dict[str, Path]:
    return {
        "conversion_json": out_dir / f"{target_id}_ts_conversion.json",
        "conversion_csv": out_dir / f"{target_id}_ts_conversion.csv",
        "conversion_md": out_dir / f"{target_id}_ts_conversion.md",
    }


def _convert_row(row: dict[str, Any], launch_by_target: dict[str, dict[str, Any]], args: argparse.Namespace, out_dir: Path) -> dict[str, Any]:
    target_id = _text(row.get("target_id")).upper()
    launch_row = launch_by_target.get(target_id, {})
    raw_gate_status = _text(row.get("raw_gate_status"))
    raw_pdb = _text(row.get("raw_pdb"))
    sequence_path = _text(launch_row.get("sequence_path"))
    ts_pdb = _artifact(_resolve(args.prediction_dir) / f"{target_id}TS.pdb")
    paths = _target_paths(out_dir, target_id)
    blockers: list[str] = []

    if not target_id:
        blockers.append("missing_target_id")
    if raw_gate_status != "pass":
        blockers.append(f"raw_gate_not_pass:{raw_gate_status or 'missing'}")
    if not raw_pdb:
        blockers.append("missing_raw_pdb")
    elif not _resolve(raw_pdb).exists():
        blockers.append("raw_pdb_missing")
    if not sequence_path:
        blockers.append("missing_sequence_path")
    elif not _resolve(sequence_path).exists():
        blockers.append("sequence_path_missing")

    command = _shell_join(
        [
            "python3",
            "tools/convert_casp17_ts_prediction_from_pdb.py",
            "--target-id",
            target_id or "<TARGET_ID>",
            "--input-pdb",
            raw_pdb or "<RAW_PDB>",
            "--sequence-path",
            sequence_path or "<SEQUENCE_PATH>",
            "--author-code",
            "<CASP_AUTHOR_CODE>",
            "--out-pdb",
            ts_pdb,
        ]
    )

    author_blocker = _author_code_blocker(args.author_code)
    if author_blocker:
        blockers.append(author_blocker)
    if not args.execute:
        return {
            "target_id": target_id,
            "raw_gate_status": raw_gate_status,
            "ts_conversion_status": "planned" if not blockers else "blocked",
            "raw_pdb": _artifact(raw_pdb) if raw_pdb else "",
            "sequence_path": _artifact(sequence_path) if sequence_path else "",
            "ts_pdb": ts_pdb,
            "atom_count": 0,
            "conversion_json": "",
            "command": command,
            "blockers": ";".join(dict.fromkeys(blockers)),
        }
    if blockers:
        return {
            "target_id": target_id,
            "raw_gate_status": raw_gate_status,
            "ts_conversion_status": "blocked",
            "raw_pdb": _artifact(raw_pdb) if raw_pdb else "",
            "sequence_path": _artifact(sequence_path) if sequence_path else "",
            "ts_pdb": ts_pdb,
            "atom_count": 0,
            "conversion_json": "",
            "command": command,
            "blockers": ";".join(dict.fromkeys(blockers)),
        }

    convert_args = argparse.Namespace(
        target_id=target_id,
        input_pdb=raw_pdb,
        sequence_path=sequence_path,
        author_code=args.author_code,
        method="Internal CASP17 target-specific physics baseline; repo-local torch/coarse-grain ensemble, no external predictor or template structure.",
        parent="N/A",
        out_pdb=ts_pdb,
    )
    payload = converter.convert_prediction(convert_args)
    converter._write_json(paths["conversion_json"], payload)
    converter._write_csv(paths["conversion_csv"], [payload["summary"]])
    converter._write_md(paths["conversion_md"], payload)
    conversion_blockers = [f"conversion:{_text(blocker.get('code'))}" for blocker in payload.get("blockers", []) if isinstance(blocker, dict)]
    return {
        "target_id": target_id,
        "raw_gate_status": raw_gate_status,
        "ts_conversion_status": "converted" if not conversion_blockers else "failed",
        "raw_pdb": _artifact(raw_pdb),
        "sequence_path": _artifact(sequence_path),
        "ts_pdb": _artifact(ts_pdb),
        "atom_count": payload["summary"].get("atom_count", 0),
        "conversion_json": _artifact(paths["conversion_json"]),
        "command": command.replace("<CASP_AUTHOR_CODE>", "<redacted_author_code>"),
        "blockers": ";".join(dict.fromkeys(conversion_blockers)),
    }


def _run_step(step: str, command: list[str], timeout_seconds: int) -> dict[str, Any]:
    try:
        run = subprocess.run(command, cwd=str(ROOT), capture_output=True, text=True, check=False, timeout=timeout_seconds)
        return {
            "step": step,
            "status": "pass" if int(run.returncode) == 0 else "fail",
            "returncode": int(run.returncode),
            "command": _shell_join(command),
            "stdout_tail": (run.stdout or "")[-1000:],
            "stderr_tail": (run.stderr or "")[-1000:],
            "blocker": "" if int(run.returncode) == 0 else f"{step}_failed",
        }
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else str(exc.stdout or "")
        stderr = exc.stderr.decode("utf-8", errors="replace") if isinstance(exc.stderr, bytes) else str(exc.stderr or "")
        return {
            "step": step,
            "status": "fail",
            "returncode": 124,
            "command": _shell_join(command),
            "stdout_tail": stdout[-1000:],
            "stderr_tail": stderr[-1000:],
            "blocker": f"{step}_timeout",
        }


def _downstream_commands(args: argparse.Namespace) -> list[tuple[str, list[str]]]:
    return [
        (
            "import",
            [
                "python3",
                "tools/casp17/build_casp17_prediction_import_packet.py",
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
            ],
        ),
        (
            "validation",
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
            ],
        ),
        (
            "scorecard",
            [
                "python3",
                "tools/casp17/build_casp17_internal_scorecard_batch.py",
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
            ],
        ),
        (
            "submission_gate",
            [
                "python3",
                "tools/casp17/build_casp17_submission_gate_packet.py",
                "--intake-csv",
                args.scored_intake_csv,
                "--out-json",
                args.submission_gate_json,
                "--out-csv",
                args.submission_gate_csv,
                "--out-md",
                args.submission_gate_md,
            ],
        ),
    ]


def _selected_downstream(args: argparse.Namespace) -> list[tuple[str, list[str]]]:
    stop_index = STEP_ORDER.index(args.stop_after)
    allowed = set(STEP_ORDER[1 : stop_index + 1])
    return [(step, command) for step, command in _downstream_commands(args) if step in allowed]


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    raw_gate = _read_json(args.raw_gate_json)
    launch_packet = _read_json(args.launch_packet_json)
    launch_by_target = _launch_index(launch_packet)
    out_dir = _resolve(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = [_convert_row(row, launch_by_target, args, out_dir) for row in _rows(raw_gate)]

    converted_count = sum(1 for row in rows if row["ts_conversion_status"] == "converted")
    planned_count = sum(1 for row in rows if row["ts_conversion_status"] == "planned")
    blocked_count = sum(1 for row in rows if row["ts_conversion_status"] == "blocked")
    failed_count = sum(1 for row in rows if row["ts_conversion_status"] == "failed")
    downstream_steps: list[dict[str, Any]] = []
    if args.execute and args.stop_after != "conversion" and converted_count == len(rows) and rows:
        for step, command in _selected_downstream(args):
            result = _run_step(step, command, timeout_seconds=int(args.timeout_seconds))
            downstream_steps.append(result)
            if result["status"] != "pass":
                failed_count += 1
                if not args.continue_on_error:
                    break

    downstream_completed_steps = [step["step"] for step in downstream_steps if step["status"] == "pass"]
    batch_status = "ready_not_executed"
    if not rows:
        batch_status = "blocked_no_raw_gate_rows"
    elif failed_count:
        batch_status = "failed"
    elif blocked_count:
        batch_status = "blocked"
    elif args.execute and converted_count == len(rows):
        batch_status = f"completed_to_{args.stop_after}" if len(downstream_completed_steps) == len(_selected_downstream(args)) else "converted"
    elif planned_count:
        batch_status = "planned"

    summary = {
        "packet_type": "casp17_internal_physics_ts_gate_batch",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "raw_gate_json": _artifact(args.raw_gate_json),
        "launch_packet_json": _artifact(args.launch_packet_json),
        "intake_csv": _artifact(args.intake_csv),
        "prediction_dir": _artifact(args.prediction_dir),
        "out_dir": _artifact(args.out_dir),
        "execute": bool(args.execute),
        "stop_after": args.stop_after,
        "target_count": len(rows),
        "converted_count": converted_count,
        "planned_count": planned_count,
        "blocked_count": blocked_count,
        "failed_count": failed_count,
        "downstream_completed_steps": ",".join(downstream_completed_steps),
        "batch_status": batch_status,
        "claim_boundary": "Internal raw-to-TS CASP17 gate orchestration only; not public submission or official accuracy evidence.",
    }
    return {"summary": summary, "rows": rows, "downstream_steps": downstream_steps}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert internal physics raw PDBs to CASP TS and run the existing validation chain.")
    parser.add_argument("--raw-gate-json", default=DEFAULT_RAW_GATE_JSON)
    parser.add_argument("--launch-packet-json", default=DEFAULT_LAUNCH_PACKET_JSON)
    parser.add_argument("--intake-csv", default=DEFAULT_INTAKE_CSV)
    parser.add_argument("--prediction-dir", default=DEFAULT_PREDICTION_DIR)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--author-code", default="")
    parser.add_argument("--execute", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--stop-after", choices=STEP_ORDER, default="submission_gate")
    parser.add_argument("--timeout-seconds", type=int, default=21600)
    parser.add_argument("--continue-on-error", action="store_true")
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
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)
    if args.execute and payload["summary"]["batch_status"] in {"blocked", "failed", "blocked_no_raw_gate_rows"}:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
