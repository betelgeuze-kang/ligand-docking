#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shlex
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_API_DEPENDENCY_JSON = "runs/cameo_api_dependency_readiness_current.json"
DEFAULT_RECEIVER_SMOKE_JSON = "runs/cameo_receiver_smoke_contract_current.json"
DEFAULT_CAPABILITY_JSON = "runs/cameo_capability_preflight_current.json"
DEFAULT_OUT_JSON = "runs/cameo_runtime_repair_work_order_current.json"
DEFAULT_OUT_CSV = "runs/cameo_runtime_repair_work_order_current.csv"
DEFAULT_OUT_MD = "runs/cameo_runtime_repair_work_order_current.md"
APPROVAL_TOKEN = "APPROVE_API_DEPENDENCY_INSTALL"

CLAIM_BOUNDARY = (
    "CAMEO runtime repair work order only; it records operator-reviewed API dependency activation and local smoke rerun "
    "commands. It does not install packages, start a server, register CAMEO, submit predictions, send email, run prediction "
    "generation, or mutate external state."
)


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


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _quote(parts: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in parts)


def _row(
    *,
    step: str,
    command: str,
    status: str,
    reason: str,
    requires_approval_token: bool = False,
    approval_token_required: str = "",
) -> dict[str, Any]:
    return {
        "step": step,
        "status": status,
        "command": command,
        "reason": reason,
        "requires_approval_token": requires_approval_token,
        "approval_token_required": approval_token_required,
        "package_install_executed": False,
        "server_started": False,
        "prediction_generation_enabled": False,
        "outbound_email_enabled": False,
        "external_state_mutated": False,
    }


def build_cameo_runtime_repair_work_order(
    *,
    api_dependency_packet: dict[str, Any],
    receiver_smoke_packet: dict[str, Any],
    capability_preflight_packet: dict[str, Any],
    requirements_api: str = "requirements-api.txt",
    api_dependency_json: str = DEFAULT_API_DEPENDENCY_JSON,
    receiver_smoke_json: str = DEFAULT_RECEIVER_SMOKE_JSON,
    capability_json: str = DEFAULT_CAPABILITY_JSON,
) -> dict[str, Any]:
    api_dep = _summary(api_dependency_packet)
    smoke = _summary(receiver_smoke_packet)
    capability = _summary(capability_preflight_packet)
    rows: list[dict[str, Any]] = []
    blockers: list[dict[str, str]] = []

    api_dep_status = _text(api_dep.get("status"))
    smoke_status = _text(smoke.get("status"))
    capability_status = _text(capability.get("status"))
    api_dep_blocked = api_dep_status == "blocked_cameo_api_dependency_readiness"
    smoke_blocked = smoke_status == "blocked_cameo_receiver_smoke"
    capability_blocked = capability_status == "blocked_cameo_capability_preflight"

    if not api_dependency_packet:
        blockers.append({"code": "api_dependency_artifact_missing", "severity": "hard", "reason": "CAMEO API dependency readiness artifact is missing."})
    if not receiver_smoke_packet:
        blockers.append({"code": "receiver_smoke_artifact_missing", "severity": "hard", "reason": "CAMEO receiver smoke artifact is missing."})
    if not capability_preflight_packet:
        blockers.append({"code": "capability_preflight_artifact_missing", "severity": "hard", "reason": "CAMEO capability preflight artifact is missing."})

    missing = api_dep.get("missing_or_unimportable") if isinstance(api_dep.get("missing_or_unimportable"), list) else []
    if api_dep_blocked:
        rows.append(
            _row(
                step="install_or_activate_api_dependency_profile",
                command=_quote(["python3", "-m", "pip", "install", "-r", requirements_api]),
                status="approval_required",
                requires_approval_token=True,
                approval_token_required=APPROVAL_TOKEN,
                reason="API dependency profile is blocked: " + ", ".join(str(item) for item in missing),
            )
        )

    rows.extend(
        [
            _row(
                step="refresh_api_dependency_readiness",
                command=_quote(["python3", "tools/product/build_cameo_api_dependency_readiness.py", "--requirements-api", requirements_api]),
                status="ready_to_run_after_dependency_profile_review" if api_dep_blocked else "ready_to_run",
                reason=f"Current API dependency status is {api_dep_status or 'missing'}.",
            ),
            _row(
                step="rerun_receiver_smoke",
                command=_quote(["python3", "tools/build_cameo_receiver_smoke_contract.py", "--api-dependency-json", api_dependency_json]),
                status="blocked_until_api_dependency_ready" if api_dep_blocked else "ready_to_run",
                reason=f"Current receiver smoke status is {smoke_status or 'missing'}.",
            ),
            _row(
                step="refresh_capability_preflight",
                command=_quote(["python3", "tools/build_cameo_capability_preflight.py", "--receiver-smoke-json", receiver_smoke_json]),
                status="blocked_until_receiver_smoke_ready" if smoke_blocked else "ready_to_run",
                reason=f"Current capability preflight status is {capability_status or 'missing'}.",
            ),
            _row(
                step="refresh_goal_surfaces",
                command=_quote(["python3", "tools/build_goal_readiness_rollup.py"]) + " && " + _quote(["python3", "tools/build_goal_operator_action_board.py"]),
                status="ready_to_run_after_previous_steps",
                reason="Refresh top-level goal readiness and operator actions after runtime repair artifacts are rebuilt.",
            ),
        ]
    )

    status = "blocked_cameo_runtime_repair_work_order" if blockers else "cameo_runtime_repair_work_order_ready"
    summary = {
        "packet_type": "cameo_runtime_repair_work_order",
        "status": status,
        "source_api_dependency_json": api_dependency_json,
        "source_receiver_smoke_json": receiver_smoke_json,
        "source_capability_preflight_json": capability_json,
        "source_api_dependency_status": api_dep_status,
        "source_receiver_smoke_status": smoke_status,
        "source_capability_preflight_status": capability_status,
        "missing_or_unimportable_count": _int(api_dep.get("missing_or_unimportable_count")),
        "install_approval_required": bool(api_dep_blocked),
        "approval_token_required": APPROVAL_TOKEN if api_dep_blocked else "",
        "command_count": len(rows),
        "approval_required_command_count": sum(1 for row in rows if row["requires_approval_token"]),
        "blocker_count": len(blockers),
        "package_install_executed": False,
        "server_started": False,
        "prediction_generation_enabled": False,
        "outbound_email_enabled": False,
        "server_registration_mutated": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            f"Review API dependency activation and provide `{APPROVAL_TOKEN}` only if package installation should run; then rerun the recorded local smoke commands."
            if api_dep_blocked
            else "Run the recorded local smoke refresh commands and inspect CAMEO capability preflight."
        ),
    }
    return {"summary": summary, "blockers": blockers, "rows": rows}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# CAMEO Runtime Repair Work Order",
        "",
        f"- status: `{s['status']}`",
        f"- source_api_dependency_status: `{s['source_api_dependency_status']}`",
        f"- source_receiver_smoke_status: `{s['source_receiver_smoke_status']}`",
        f"- source_capability_preflight_status: `{s['source_capability_preflight_status']}`",
        f"- missing_or_unimportable_count: `{s['missing_or_unimportable_count']}`",
        f"- install_approval_required: `{s['install_approval_required']}`",
        f"- approval_token_required: `{s['approval_token_required']}`",
        f"- command_count: `{s['command_count']}`",
        f"- package_install_executed: `{s['package_install_executed']}`",
        f"- server_started: `{s['server_started']}`",
        f"- outbound_email_enabled: `{s['outbound_email_enabled']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Commands",
        "",
        "| step | status | approval | command | reason |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['step']}` | `{row['status']}` | `{row['approval_token_required']}` | `{row['command']}` | {row['reason']} |"
        )
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
    parser = argparse.ArgumentParser(description="Build a CAMEO runtime repair work order without installing packages or starting a server.")
    parser.add_argument("--api-dependency-json", default=DEFAULT_API_DEPENDENCY_JSON)
    parser.add_argument("--receiver-smoke-json", default=DEFAULT_RECEIVER_SMOKE_JSON)
    parser.add_argument("--capability-json", default=DEFAULT_CAPABILITY_JSON)
    parser.add_argument("--requirements-api", default="requirements-api.txt")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_cameo_runtime_repair_work_order(
        api_dependency_packet=_read_json_if_present(args.api_dependency_json),
        receiver_smoke_packet=_read_json_if_present(args.receiver_smoke_json),
        capability_preflight_packet=_read_json_if_present(args.capability_json),
        requirements_api=args.requirements_api,
        api_dependency_json=args.api_dependency_json,
        receiver_smoke_json=args.receiver_smoke_json,
        capability_json=args.capability_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
