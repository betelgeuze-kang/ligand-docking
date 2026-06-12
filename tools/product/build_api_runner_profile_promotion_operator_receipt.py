#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.product.build_api_runner_profile_promotion_readiness import (
    APPROVAL_TOKEN,
    DEFAULT_OPERATOR_TEMPLATE_CSV,
    DEFAULT_OUT_JSON as DEFAULT_READINESS_JSON,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/api_runner_profile_promotion_operator_receipt_current.json"
DEFAULT_OUT_CSV = "runs/api_runner_profile_promotion_operator_receipt_current.csv"
DEFAULT_OUT_MD = "runs/api_runner_profile_promotion_operator_receipt_current.md"

REQUIRED_COLUMNS = [
    "profile_id",
    "operator_decision",
    "approval_token",
    "input_contract_reviewed",
    "output_contract_reviewed",
    "claim_boundary_reviewed",
    "gate_policy_reviewed",
    "fake_result_emission_forbidden",
    "gate_policy_artifact",
    "reviewer",
    "reviewed_at_utc",
    "operator_note",
]
REQUIRED_TRUE_FIELDS = [
    "input_contract_reviewed",
    "output_contract_reviewed",
    "claim_boundary_reviewed",
    "gate_policy_reviewed",
    "fake_result_emission_forbidden",
]
APPROVED_DECISIONS = {"promote", "keep_enabled"}
VALID_DECISIONS = APPROVED_DECISIONS | {"hold"}
PLACEHOLDER_PREFIXES = ("OPERATOR_FILL", "OPERATOR_CONFIRM")
CLAIM_BOUNDARY = (
    "API runner profile promotion operator receipt only; it verifies local operator review rows for profile "
    "promotion decisions. It does not edit profile JSON, enable profiles, run scientific runners, submit jobs, "
    "emit fake results, or mutate external state."
)


def _resolve(path_like: str | Path, *, root: Path = ROOT) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else root / path


def _display_path(path: Path, *, root: Path = ROOT) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _read_json_if_present(path_like: str | Path, *, root: Path = ROOT) -> dict[str, Any]:
    path = _resolve(path_like, root=root)
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _bool_text(value: Any) -> bool:
    return _text(value).lower() in {"true", "1", "yes", "y"}


def _has_placeholder(value: Any) -> bool:
    text = _text(value)
    return any(text.startswith(prefix) for prefix in PLACEHOLDER_PREFIXES)


def _is_iso_timestamp(value: Any) -> bool:
    text = _text(value)
    if not text:
        return False
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    if isinstance(summary, dict):
        return summary
    return packet if isinstance(packet, dict) else {}


def _rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    return [row for row in packet.get("rows", []) or [] if isinstance(row, dict)]


def _read_csv_rows(path_like: str | Path, *, root: Path = ROOT) -> tuple[list[dict[str, str]], list[str]]:
    path = _resolve(path_like, root=root)
    if not path.is_file():
        return [], REQUIRED_COLUMNS
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = [dict(row) for row in reader]
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in fieldnames]
    return rows, missing_columns


def _readiness_index(readiness_packet: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        _text(row.get("profile_id")): row
        for row in _rows(readiness_packet)
        if _text(row.get("profile_id"))
    }


def _gate_policy_artifact_ready(value: Any, *, root: Path) -> bool:
    text = _text(value)
    return bool(text and not _has_placeholder(text) and _resolve(text, root=root).is_file())


def _build_row(
    source_row: dict[str, Any],
    *,
    readiness: dict[str, Any],
    missing_columns: list[str],
    root: Path,
) -> dict[str, Any]:
    profile_id = _text(source_row.get("profile_id"))
    decision = _text(source_row.get("operator_decision")).lower()
    blockers: list[str] = []
    if missing_columns:
        blockers.append("receipt_columns_missing")
    if not profile_id or _has_placeholder(profile_id):
        blockers.append("profile_id_missing")
    if not decision:
        blockers.append("operator_decision_missing")
    elif decision not in VALID_DECISIONS:
        blockers.append("operator_decision_invalid")
    if _text(source_row.get("approval_token")) != APPROVAL_TOKEN:
        blockers.append("approval_token_invalid")
    for field in REQUIRED_TRUE_FIELDS:
        if not _bool_text(source_row.get(field)):
            blockers.append(f"{field}_not_true")
    if not _gate_policy_artifact_ready(source_row.get("gate_policy_artifact"), root=root):
        blockers.append("gate_policy_artifact_missing_or_unreadable")
    if not _text(source_row.get("reviewer")) or _has_placeholder(source_row.get("reviewer")):
        blockers.append("reviewer_missing")
    if not _is_iso_timestamp(source_row.get("reviewed_at_utc")):
        blockers.append("reviewed_at_utc_invalid")
    if any(_has_placeholder(source_row.get(column)) for column in REQUIRED_COLUMNS):
        blockers.append("operator_placeholders_unfilled")
    if not readiness:
        blockers.append("readiness_profile_missing")
    elif decision in APPROVED_DECISIONS and readiness.get("promotion_ready") is not True:
        blockers.append("readiness_not_promotion_ready")

    return {
        "profile_id": profile_id,
        "operator_decision": decision,
        "row_status": "pass" if not blockers else "blocked",
        "blocker_count": len(blockers),
        "blockers": ";".join(blockers),
        "approval_token": _text(source_row.get("approval_token")),
        "input_contract_reviewed": _bool_text(source_row.get("input_contract_reviewed")),
        "output_contract_reviewed": _bool_text(source_row.get("output_contract_reviewed")),
        "claim_boundary_reviewed": _bool_text(source_row.get("claim_boundary_reviewed")),
        "gate_policy_reviewed": _bool_text(source_row.get("gate_policy_reviewed")),
        "fake_result_emission_forbidden": _bool_text(source_row.get("fake_result_emission_forbidden")),
        "gate_policy_artifact": _text(source_row.get("gate_policy_artifact")),
        "reviewer": _text(source_row.get("reviewer")),
        "reviewed_at_utc": _text(source_row.get("reviewed_at_utc")),
        "operator_note": _text(source_row.get("operator_note")),
        "readiness_promotion_ready": readiness.get("promotion_ready") is True,
        "readiness_enabled": readiness.get("enabled") is True,
        "readiness_profile_path": _text(readiness.get("profile_path")),
        "profile_enabled_by_this_tool": False,
        "runner_executed": False,
        "external_state_mutated": False,
    }


def build_api_runner_profile_promotion_operator_receipt(
    *,
    operator_template_csv: str | Path = DEFAULT_OPERATOR_TEMPLATE_CSV,
    readiness_json: str | Path = DEFAULT_READINESS_JSON,
    root: str | Path = ROOT,
) -> dict[str, Any]:
    root_path = Path(root)
    readiness_packet = _read_json_if_present(readiness_json, root=root_path)
    readiness_summary = _summary(readiness_packet)
    readiness = _readiness_index(readiness_packet)
    source_rows, missing_columns = _read_csv_rows(operator_template_csv, root=root_path)
    seen_profiles = {_text(row.get("profile_id")) for row in source_rows if _text(row.get("profile_id"))}
    missing_profiles = sorted(profile_id for profile_id in readiness if profile_id not in seen_profiles)
    duplicate_profiles = sorted(
        profile_id
        for profile_id in seen_profiles
        if sum(1 for row in source_rows if _text(row.get("profile_id")) == profile_id) > 1
    )
    rows = [
        _build_row(row, readiness=readiness.get(_text(row.get("profile_id")), {}), missing_columns=missing_columns, root=root_path)
        for row in source_rows
    ]
    for profile_id in missing_profiles:
        ready_row = readiness[profile_id]
        rows.append(
            {
                "profile_id": profile_id,
                "operator_decision": "",
                "row_status": "blocked",
                "blocker_count": 1,
                "blockers": "operator_receipt_row_missing",
                "approval_token": "",
                "input_contract_reviewed": False,
                "output_contract_reviewed": False,
                "claim_boundary_reviewed": False,
                "gate_policy_reviewed": False,
                "fake_result_emission_forbidden": False,
                "gate_policy_artifact": "",
                "reviewer": "",
                "reviewed_at_utc": "",
                "operator_note": "",
                "readiness_promotion_ready": ready_row.get("promotion_ready") is True,
                "readiness_enabled": ready_row.get("enabled") is True,
                "readiness_profile_path": _text(ready_row.get("profile_path")),
                "profile_enabled_by_this_tool": False,
                "runner_executed": False,
                "external_state_mutated": False,
            }
        )
    for row in rows:
        if row["profile_id"] in duplicate_profiles and "duplicate_profile_receipt_row" not in row["blockers"]:
            blockers = [part for part in _text(row["blockers"]).split(";") if part]
            blockers.append("duplicate_profile_receipt_row")
            row["blockers"] = ";".join(blockers)
            row["blocker_count"] = len(blockers)
            row["row_status"] = "blocked"

    blocked_rows = [row for row in rows if row["row_status"] != "pass"]
    summary_blockers: list[str] = []
    if not readiness:
        summary_blockers.append("readiness_packet_missing_or_empty")
    if missing_columns:
        summary_blockers.append("receipt_columns_missing")
    if missing_profiles:
        summary_blockers.append("receipt_rows_missing_for_profiles")
    if duplicate_profiles:
        summary_blockers.append("duplicate_profile_receipt_rows")
    if blocked_rows:
        summary_blockers.append("blocked_receipt_rows_present")
    ready = bool(rows) and not summary_blockers
    summary = {
        "packet_type": "api_runner_profile_promotion_operator_receipt",
        "status": (
            "api_runner_profile_promotion_operator_receipt_ready"
            if ready
            else "blocked_api_runner_profile_promotion_operator_receipt"
        ),
        "operator_receipt_ready": ready,
        "readiness_artifact": _display_path(_resolve(readiness_json, root=root_path), root=root_path),
        "readiness_status": _text(readiness_summary.get("status")),
        "operator_template_csv": _display_path(_resolve(operator_template_csv, root=root_path), root=root_path),
        "profile_count": len(readiness),
        "receipt_row_count": len(source_rows),
        "pass_row_count": len(rows) - len(blocked_rows),
        "blocked_row_count": len(blocked_rows),
        "approved_profile_count": sum(1 for row in rows if row["operator_decision"] in APPROVED_DECISIONS and row["row_status"] == "pass"),
        "held_profile_count": sum(1 for row in rows if row["operator_decision"] == "hold" and row["row_status"] == "pass"),
        "missing_profile_count": len(missing_profiles),
        "duplicate_profile_count": len(duplicate_profiles),
        "missing_columns": missing_columns,
        "approval_token_required": APPROVAL_TOKEN,
        "profile_enabled_by_this_tool": False,
        "runner_executed": False,
        "external_state_mutated": False,
        "blocker_count": len(summary_blockers),
        "blockers": summary_blockers,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Use a separate operator-approved profile edit or keep-current decision after this receipt is reviewed."
            if ready
            else "Fill the API runner profile promotion operator template with reviewed decisions, approval token, "
            "true contract checks, reviewer metadata, and local gate policy artifact paths."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    s = payload["summary"]
    lines = [
        "# API Runner Profile Promotion Operator Receipt",
        "",
        f"- status: `{s['status']}`",
        f"- operator_receipt_ready: `{s['operator_receipt_ready']}`",
        f"- profile_count: `{s['profile_count']}`",
        f"- receipt_row_count: `{s['receipt_row_count']}`",
        f"- pass_row_count: `{s['pass_row_count']}`",
        f"- blocked_row_count: `{s['blocked_row_count']}`",
        f"- approval_token_required: `{s['approval_token_required']}`",
        f"- profile_enabled_by_this_tool: `{s['profile_enabled_by_this_tool']}`",
        f"- runner_executed: `{s['runner_executed']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Profiles",
        "",
        "| profile | decision | status | blockers |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['profile_id']}` | `{row['operator_decision']}` | "
            f"`{row['row_status']}` | `{row['blockers']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build API runner profile promotion operator receipt gate.")
    parser.add_argument("--operator-template-csv", default=DEFAULT_OPERATOR_TEMPLATE_CSV)
    parser.add_argument("--readiness-json", default=DEFAULT_READINESS_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_api_runner_profile_promotion_operator_receipt(
        operator_template_csv=args.operator_template_csv,
        readiness_json=args.readiness_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
