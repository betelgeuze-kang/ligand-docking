#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_GOAL_AUDIT_JSON = "runs/product_goal_completion_audit_current.json"
DEFAULT_OPERATOR_PACKET_JSON = "runs/product_commercial_readiness_operator_packet_current.json"
DEFAULT_OUT_JSON = "runs/product_commercial_readiness_operator_packet_freshness_current.json"
DEFAULT_OUT_CSV = "runs/product_commercial_readiness_operator_packet_freshness_current.csv"
DEFAULT_OUT_MD = "runs/product_commercial_readiness_operator_packet_freshness_current.md"

CLAIM_BOUNDARY = (
    "Product commercial-readiness operator-packet freshness check only; compares the handoff packet fingerprints "
    "against the current goal-completion audit. It does not run docking, run GPU jobs, fill evidence, promote "
    "checkpoints, widen product claims, upload, submit, email, delete, or mutate external state."
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


def _sha256_file_if_present(path_like: str | Path) -> str:
    path = _resolve(path_like)
    if not path.exists() or not path.is_file():
        return ""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_json(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _goal_audit_source_sha256(goal_audit_packet: dict[str, Any]) -> str:
    if not goal_audit_packet:
        return ""
    payload = json.loads(json.dumps(goal_audit_packet))
    summary = payload.get("summary")
    if isinstance(summary, dict):
        for key in list(summary):
            if str(key).startswith("commercial_readiness_handoff_bundle_"):
                summary.pop(key, None)
    return _sha256_json(payload)


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


def _matrix(goal_audit_packet: dict[str, Any]) -> list[dict[str, Any]]:
    summary = _summary(goal_audit_packet)
    rows = summary.get("commercial_readiness_next_action_matrix")
    return [dict(row) for row in (rows or []) if isinstance(row, dict)]


def _python_tool_references(value: Any) -> list[str]:
    refs: list[str] = []
    if isinstance(value, dict):
        for item in value.values():
            refs.extend(_python_tool_references(item))
    elif isinstance(value, list):
        for item in value:
            refs.extend(_python_tool_references(item))
    elif isinstance(value, str):
        refs.extend(re.findall(r"python3\s+(tools/[A-Za-z0-9_./-]+\.py)", value))
    return sorted(set(refs))


def _missing_python_tool_references(value: Any) -> list[str]:
    return [ref for ref in _python_tool_references(value) if not _resolve(ref).is_file()]


def _check(check_id: str, passed: bool, observed: str, required: str) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "status": "pass" if passed else "fail",
        "observed": observed,
        "required": required,
        "release_blocker": not passed,
        "execution_enabled": False,
        "external_state_mutated": False,
    }


def build_product_commercial_readiness_operator_packet_freshness(
    *,
    goal_audit_packet: dict[str, Any],
    operator_packet: dict[str, Any],
    goal_audit_path: str = DEFAULT_GOAL_AUDIT_JSON,
    operator_packet_path: str = DEFAULT_OPERATOR_PACKET_JSON,
) -> dict[str, Any]:
    goal_summary = _summary(goal_audit_packet)
    operator_summary = _summary(operator_packet)
    current_matrix = _matrix(goal_audit_packet)
    current_goal_sha = _goal_audit_source_sha256(goal_audit_packet)
    current_matrix_sha = _sha256_json(current_matrix)
    current_blocked = [row for row in current_matrix if _text(row.get("status")) != "ready"]
    current_first_action_id = _text(current_blocked[0].get("action_id")) if current_blocked else ""
    operator_command_refs = _python_tool_references(operator_packet)
    missing_operator_command_refs = _missing_python_tool_references(operator_packet)
    rows = [
        _check(
            "operator_packet_present",
            bool(operator_summary),
            f"operator_packet_present={bool(operator_summary)};artifact={operator_packet_path}",
            "operator packet JSON artifact is present and has a summary",
        ),
        _check(
            "source_fingerprint_ready",
            bool(operator_summary.get("source_fingerprint_ready") is True),
            f"source_fingerprint_ready={operator_summary.get('source_fingerprint_ready')}",
            "operator packet reports source_fingerprint_ready=true",
        ),
        _check(
            "goal_audit_sha256_matches",
            _text(operator_summary.get("goal_audit_sha256")) == current_goal_sha and bool(current_goal_sha),
            f"operator={_text(operator_summary.get('goal_audit_sha256'))};current={current_goal_sha}",
            "operator packet goal_audit_sha256 equals current goal-audit file sha256",
        ),
        _check(
            "commercial_readiness_matrix_sha256_matches",
            _text(operator_summary.get("commercial_readiness_matrix_sha256")) == current_matrix_sha,
            f"operator={_text(operator_summary.get('commercial_readiness_matrix_sha256'))};current={current_matrix_sha}",
            "operator packet matrix sha256 equals current commercial_readiness_next_action_matrix sha256",
        ),
        _check(
            "action_count_matches",
            _int(operator_summary.get("action_count")) == len(current_matrix),
            f"operator={_int(operator_summary.get('action_count'))};current={len(current_matrix)}",
            "operator action_count equals current matrix row count",
        ),
        _check(
            "blocked_action_count_matches",
            _int(operator_summary.get("blocked_action_count")) == len(current_blocked),
            f"operator={_int(operator_summary.get('blocked_action_count'))};current={len(current_blocked)}",
            "operator blocked_action_count equals current blocked matrix row count",
        ),
        _check(
            "first_action_id_matches",
            _text(operator_summary.get("first_action_id")) == current_first_action_id,
            f"operator={_text(operator_summary.get('first_action_id'))};current={current_first_action_id}",
            "operator first_action_id equals current first blocked action id",
        ),
        _check(
            "operator_python_tool_references_exist",
            not missing_operator_command_refs and bool(operator_command_refs),
            (
                f"reference_count={len(operator_command_refs)};"
                f"missing_count={len(missing_operator_command_refs)};"
                f"missing={','.join(missing_operator_command_refs)}"
            ),
            "every python3 tools/*.py command referenced by the operator packet resolves to a local tool file",
        ),
    ]
    failed = [row for row in rows if row["status"] != "pass"]
    summary = {
        "packet_type": "product_commercial_readiness_operator_packet_freshness",
        "status": (
            "product_commercial_readiness_operator_packet_freshness_ready"
            if not failed
            else "blocked_product_commercial_readiness_operator_packet_freshness"
        ),
        "freshness_ready": not failed,
        "goal_complete": bool(goal_summary.get("goal_complete") is True),
        "goal_audit_artifact": goal_audit_path,
        "operator_packet_artifact": operator_packet_path,
        "current_goal_audit_sha256": current_goal_sha,
        "operator_goal_audit_sha256": _text(operator_summary.get("goal_audit_sha256")),
        "current_commercial_readiness_matrix_sha256": current_matrix_sha,
        "operator_commercial_readiness_matrix_sha256": _text(
            operator_summary.get("commercial_readiness_matrix_sha256")
        ),
        "current_action_count": len(current_matrix),
        "operator_action_count": _int(operator_summary.get("action_count")),
        "current_blocked_action_count": len(current_blocked),
        "operator_blocked_action_count": _int(operator_summary.get("blocked_action_count")),
        "current_first_action_id": current_first_action_id,
        "operator_first_action_id": _text(operator_summary.get("first_action_id")),
        "command_references_ready": not missing_operator_command_refs and bool(operator_command_refs),
        "operator_python_tool_reference_count": len(operator_command_refs),
        "operator_missing_python_tool_reference_count": len(missing_operator_command_refs),
        "operator_python_tool_references": operator_command_refs,
        "operator_missing_python_tool_references": missing_operator_command_refs,
        "check_count": len(rows),
        "pass_count": len(rows) - len(failed),
        "fail_count": len(failed),
        "failed_check_ids": [row["check_id"] for row in failed],
        "next_required_step": (
            "Use the current operator packet for commercial-readiness handoff."
            if not failed
            else "Rebuild product_commercial_readiness_operator_packet_current from the current goal-completion audit."
        ),
        "claim_boundary": CLAIM_BOUNDARY,
        "execution_enabled": False,
        "external_state_mutated": False,
        "docking_results_emitted": False,
        "scope_widened": False,
        "checkpoint_promoted": False,
    }
    return {"summary": summary, "rows": rows, "blockers": failed}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Product Commercial Readiness Operator Packet Freshness",
        "",
        f"- status: `{s['status']}`",
        f"- freshness_ready: `{s['freshness_ready']}`",
        f"- goal_complete: `{s['goal_complete']}`",
        f"- current_goal_audit_sha256: `{s['current_goal_audit_sha256']}`",
        f"- operator_goal_audit_sha256: `{s['operator_goal_audit_sha256']}`",
        f"- current_commercial_readiness_matrix_sha256: `{s['current_commercial_readiness_matrix_sha256']}`",
        f"- operator_commercial_readiness_matrix_sha256: `{s['operator_commercial_readiness_matrix_sha256']}`",
        f"- fail_count: `{s['fail_count']}`",
        f"- command_references_ready: `{s['command_references_ready']}`",
        f"- operator_python_tool_reference_count: `{s['operator_python_tool_reference_count']}`",
        f"- operator_missing_python_tool_reference_count: `{s['operator_missing_python_tool_reference_count']}`",
        f"- next_required_step: `{s['next_required_step']}`",
        "",
        "## Checks",
        "",
        "| check | status | observed | required |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['check_id']}` | `{row['status']}` | `{row['observed']}` | `{row['required']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify freshness of the commercial-readiness operator packet.")
    parser.add_argument("--goal-audit-json", default=DEFAULT_GOAL_AUDIT_JSON)
    parser.add_argument("--operator-packet-json", default=DEFAULT_OPERATOR_PACKET_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_product_commercial_readiness_operator_packet_freshness(
        goal_audit_packet=_read_json_if_present(args.goal_audit_json),
        operator_packet=_read_json_if_present(args.operator_packet_json),
        goal_audit_path=args.goal_audit_json,
        operator_packet_path=args.operator_packet_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
