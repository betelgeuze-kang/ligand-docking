#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import signal
import shlex
import subprocess
from pathlib import Path
from typing import Any

from tools.product.build_product_release_source_of_truth_gate import RELEASE_REFRESH_COMMANDS

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/product_release_current_refresh_plan_current.json"
DEFAULT_OUT_MD = "runs/product_release_current_refresh_plan_current.md"
DEFAULT_COMMAND_TIMEOUT_SECONDS = 420

CLAIM_BOUNDARY = (
    "Product release current refresh runner only; it executes the listed local artifact builders and local release "
    "smoke commands when --execute is provided, then verifies the final release gates. It does not submit external "
    "validation, upload, email, delete, commit, push, or mutate external services."
)

FINAL_GATE_SPECS = [
    {
        "gate_id": "product_release_source_of_truth_gate",
        "artifact_path": "runs/product_release_source_of_truth_gate_current.json",
        "required_status": "product_release_source_of_truth_gate_ready",
        "required_true_fields": ["release_source_of_truth_ready"],
        "required_zero_fields": ["blocker_count", "stale_artifact_count", "readme_drift_count"],
    },
    {
        "gate_id": "goal_release_decision_gate",
        "artifact_path": "runs/goal_release_decision_gate_current.json",
        "required_status": "goal_release_ready",
        "required_true_fields": ["release_allowed"],
        "required_zero_fields": ["blocker_count"],
    },
]


def _resolve(path_like: str | Path, *, root: Path = ROOT) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else root / path


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _run_command(command: str, *, cwd: Path, timeout_seconds: int) -> dict[str, Any]:
    proc = subprocess.Popen(shlex.split(command), cwd=cwd, start_new_session=True)
    try:
        returncode = proc.wait(timeout=max(1, int(timeout_seconds)))
        return {"returncode": int(returncode), "timed_out": False}
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        returncode = proc.wait()
        return {"returncode": int(returncode), "timed_out": True}


def _command_timeout_seconds(command: str, default_timeout_seconds: int) -> int:
    parts = shlex.split(command)
    for index, part in enumerate(parts):
        if part == "--timeout-seconds" and index + 1 < len(parts):
            try:
                return max(1, int(parts[index + 1]) + 30)
            except ValueError:
                return int(default_timeout_seconds)
        if part.startswith("--timeout-seconds="):
            try:
                return max(1, int(part.split("=", 1)[1]) + 30)
            except ValueError:
                return int(default_timeout_seconds)
    return int(default_timeout_seconds)


def _read_json_if_present(path_like: str | Path, *, root: Path = ROOT) -> dict[str, Any]:
    path = _resolve(path_like, root=root)
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else packet


def _verify_final_gate(spec: dict[str, Any], *, root: Path) -> dict[str, Any]:
    artifact_path = str(spec["artifact_path"])
    packet = _read_json_if_present(artifact_path, root=root)
    summary = _summary(packet) if packet else {}
    required_status = str(spec["required_status"])
    required_true_fields = [str(item) for item in spec.get("required_true_fields") or []]
    required_zero_fields = [str(item) for item in spec.get("required_zero_fields") or []]
    missing_true_fields = [field for field in required_true_fields if summary.get(field) is not True]
    nonzero_fields = [field for field in required_zero_fields if int(summary.get(field) or 0) != 0]
    observed_status = str(summary.get("status", "") or "missing")
    passed = bool(summary) and observed_status == required_status and not missing_true_fields and not nonzero_fields
    return {
        "gate_id": str(spec["gate_id"]),
        "artifact_path": artifact_path,
        "status": "pass" if passed else "fail",
        "artifact_present": bool(packet),
        "required_status": required_status,
        "observed_status": observed_status,
        "required_true_fields": required_true_fields,
        "missing_true_fields": missing_true_fields,
        "required_zero_fields": required_zero_fields,
        "nonzero_fields": nonzero_fields,
        "observed": (
            f"status={observed_status};missing_true_fields={len(missing_true_fields)};"
            f"nonzero_fields={len(nonzero_fields)}"
        ),
        "required": (
            f"status={required_status};true={','.join(required_true_fields) or 'none'};"
            f"zero={','.join(required_zero_fields) or 'none'}"
        ),
        "release_blocker": not passed,
        "execution_enabled": False,
        "external_state_mutated": False,
    }


def _verify_final_gates(*, root: Path) -> list[dict[str, Any]]:
    return [_verify_final_gate(spec, root=root) for spec in FINAL_GATE_SPECS]


def run_product_release_current_refresh(
    *,
    execute: bool = False,
    root: str | Path = ROOT,
    commands: list[str] | None = None,
    command_timeout_seconds: int = DEFAULT_COMMAND_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    root_path = Path(root)
    commands = list(commands or RELEASE_REFRESH_COMMANDS)
    rows: list[dict[str, Any]] = []
    failed = False
    for index, command in enumerate(commands, start=1):
        row: dict[str, Any] = {
            "step_index": index,
            "command": command,
            "status": "planned",
            "returncode": None,
            "executed": False,
            "release_blocker": False,
            "timed_out": False,
            "timeout_seconds": int(command_timeout_seconds),
        }
        if execute and not failed:
            row_timeout_seconds = _command_timeout_seconds(command, int(command_timeout_seconds))
            row["timeout_seconds"] = row_timeout_seconds
            completed = _run_command(command, cwd=root_path, timeout_seconds=row_timeout_seconds)
            row["executed"] = True
            row["returncode"] = completed["returncode"]
            row["timed_out"] = bool(completed["timed_out"])
            row["status"] = "timeout" if row["timed_out"] else "pass" if completed["returncode"] == 0 else "fail"
            row["release_blocker"] = completed["returncode"] != 0 or row["timed_out"]
            failed = bool(row["release_blocker"])
        rows.append(row)

    verification_rows = _verify_final_gates(root=root_path) if execute and not failed else []
    final_gate_blocker_count = sum(1 for row in verification_rows if row["release_blocker"])
    final_gate_verification_ready = bool(execute and not failed and verification_rows and final_gate_blocker_count == 0)

    status = "product_release_current_refresh_planned"
    if execute and failed:
        status = "blocked_product_release_current_refresh"
    elif execute and final_gate_verification_ready:
        status = "product_release_current_refresh_verified"
    elif execute:
        status = "blocked_product_release_current_refresh"
    summary = {
        "packet_type": "product_release_current_refresh_plan",
        "status": status,
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "execute": execute,
        "command_count": len(commands),
        "executed_count": sum(1 for row in rows if row["executed"]),
        "failed_count": sum(1 for row in rows if row["status"] in {"fail", "timeout"}),
        "timed_out_count": sum(1 for row in rows if row["timed_out"]),
        "command_timeout_seconds": int(command_timeout_seconds),
        "release_blocker_count": sum(1 for row in rows if row["release_blocker"]),
        "final_gate_verification_ready": final_gate_verification_ready,
        "final_gate_blocker_count": final_gate_blocker_count,
        "final_gate_count": len(verification_rows),
        "commands": commands,
        "claim_boundary": CLAIM_BOUNDARY,
        "execution_enabled": execute,
        "external_state_mutated": False,
        "next_required_step": (
            "Refresh executed and final release gates verified."
            if execute and final_gate_verification_ready
            else "Run with --execute to regenerate current release artifacts in order."
            if not execute
            else "Fix the failed builder or blocked final release gate, then rerun this refresh command."
        ),
    }
    return {"summary": summary, "rows": rows, "verification_rows": verification_rows}


def _write_markdown(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    s = payload["summary"]
    lines = [
        "# Product Release Current Refresh Plan",
        "",
        f"- status: `{s['status']}`",
        f"- execute: `{s['execute']}`",
        f"- command_count: `{s['command_count']}`",
        f"- executed_count: `{s['executed_count']}`",
        f"- failed_count: `{s['failed_count']}`",
        "",
        "## Commands",
        "",
    ]
    for row in payload["rows"]:
        lines.append(f"- {row['step_index']}. `{row['command']}` status=`{row['status']}`")
    if payload.get("verification_rows"):
        lines.extend(["", "## Final Gate Verification", ""])
        for row in payload["verification_rows"]:
            lines.append(f"- `{row['gate_id']}` status=`{row['status']}` observed=`{row['observed']}`")
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Regenerate current product release artifacts in source-of-truth order.")
    parser.add_argument("--execute", action="store_true", help="Run the refresh commands. Without this, only writes a plan.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--command-timeout-seconds", type=int, default=DEFAULT_COMMAND_TIMEOUT_SECONDS)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    root = Path(args.root)
    payload = run_product_release_current_refresh(
        execute=args.execute,
        root=root,
        command_timeout_seconds=max(1, int(args.command_timeout_seconds)),
    )
    _write_json(args.out_json, payload, root=root)
    _write_markdown(args.out_md, payload, root=root)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
