#!/usr/bin/env python3
"""Preview and optionally apply operator-filled API runner promotion receipts."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.product.build_api_runner_profile_promotion_operator_receipt import (
    APPROVAL_TOKEN,
    DEFAULT_OPERATOR_TEMPLATE_CSV,
    DEFAULT_READINESS_JSON,
    REQUIRED_COLUMNS,
    build_api_runner_profile_promotion_operator_receipt,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STAGING_OPERATOR_TEMPLATE_CSV = DEFAULT_OPERATOR_TEMPLATE_CSV
DEFAULT_LIVE_OPERATOR_TEMPLATE_CSV = DEFAULT_OPERATOR_TEMPLATE_CSV
DEFAULT_ACCURACY_PARITY_JSON = "runs/accuracy_parity_scorecard_current.json"
DEFAULT_SCIENCE_CLAIM_JSON = "runs/science_claim_promotion_gap_closure_current.json"
DEFAULT_OUT_JSON = "runs/api_runner_profile_promotion_operator_staging_apply_current.json"
DEFAULT_OUT_CSV = "runs/api_runner_profile_promotion_operator_staging_apply_current.csv"
DEFAULT_OUT_MD = "runs/api_runner_profile_promotion_operator_staging_apply_current.md"
DEFAULT_CANDIDATE_OPERATOR_TEMPLATE_CSV = (
    "runs/api_runner_profile_promotion_operator_receipt_candidate_current.csv"
)

CLAIM_BOUNDARY = (
    "API runner profile promotion operator staging apply only; it validates an operator-filled profile "
    "promotion receipt CSV and exposes accuracy/science claim gates before canonical operator-template copy. "
    "Preview mode does not edit profile JSON, enable profiles, run scientific runners, emit results, deploy, "
    "upload, email, delete, commit, push, or mutate external state."
)


def _resolve(path_like: str | Path, *, root: Path = ROOT) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else root / path


def _display_path(path_like: str | Path, *, root: Path = ROOT) -> str:
    path = _resolve(path_like, root=root)
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _read_csv(path_like: str | Path, *, root: Path = ROOT) -> tuple[list[dict[str, str]], list[str], bool]:
    path = _resolve(path_like, root=root)
    if not path.is_file():
        return [], [], False
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader], list(reader.fieldnames or []), True


def _read_json(path_like: str | Path, *, root: Path = ROOT) -> tuple[dict[str, Any], bool]:
    path = _resolve(path_like, root=root)
    if not path.is_file():
        return {}, False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, True
    return (payload if isinstance(payload, dict) else {}), True


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    if isinstance(summary, dict):
        return summary
    return packet if packet.get("status") else {}


def _has_placeholder(row: dict[str, Any]) -> bool:
    return any(_text(value).startswith(("OPERATOR_FILL", "OPERATOR_CONFIRM")) for value in row.values())


def _candidate_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [{column: row.get(column, "") for column in REQUIRED_COLUMNS} for row in rows]


def _accuracy_parity_gate(summary: dict[str, Any]) -> bool:
    return (
        summary.get("overall_commercial_tool_accuracy_parity_allowed") is True
        and summary.get("schrodinger_class_claim_allowed") is True
    )


def _science_claim_gate(summary: dict[str, Any]) -> bool:
    return summary.get("claim_promotion_allowed") is True and summary.get("all_gaps_closed") is True


def _row_reports(receipt_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    reports: list[dict[str, Any]] = []
    for idx, row in enumerate(receipt_rows, start=1):
        reports.append(
            {
                "staging_row_index": idx,
                "profile_id": _text(row.get("profile_id")),
                "operator_decision": _text(row.get("operator_decision")),
                "candidate_row_status": _text(row.get("row_status")),
                "candidate_blocker_count": int(row.get("blocker_count") or 0),
                "candidate_blockers": _text(row.get("blockers")),
                "candidate_copy_allowed": _text(row.get("row_status")) == "pass",
                "readiness_promotion_ready": bool(row.get("readiness_promotion_ready") is True),
                "readiness_enabled": bool(row.get("readiness_enabled") is True),
                "profile_enabled_by_this_tool": False,
                "runner_executed": False,
                "external_state_mutated": False,
            }
        )
    return reports


def build_api_runner_profile_promotion_operator_staging_apply(
    *,
    staging_operator_template_csv: str | Path = DEFAULT_STAGING_OPERATOR_TEMPLATE_CSV,
    live_operator_template_csv: str | Path = DEFAULT_LIVE_OPERATOR_TEMPLATE_CSV,
    readiness_json: str | Path = DEFAULT_READINESS_JSON,
    accuracy_parity_json: str | Path = DEFAULT_ACCURACY_PARITY_JSON,
    science_claim_json: str | Path = DEFAULT_SCIENCE_CLAIM_JSON,
    candidate_operator_template_csv: str | Path = DEFAULT_CANDIDATE_OPERATOR_TEMPLATE_CSV,
    mode: str = "preview",
    write_canonical_operator_template: bool = False,
    approval_token: str = "",
    root: str | Path = ROOT,
) -> dict[str, Any]:
    root_path = Path(root)
    staging_rows, staging_columns, staging_present = _read_csv(staging_operator_template_csv, root=root_path)
    live_rows, _, live_present = _read_csv(live_operator_template_csv, root=root_path)
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in staging_columns] if staging_present else list(REQUIRED_COLUMNS)
    accuracy_packet, accuracy_present = _read_json(accuracy_parity_json, root=root_path)
    science_packet, science_present = _read_json(science_claim_json, root=root_path)
    accuracy_summary = _summary(accuracy_packet)
    science_summary = _summary(science_packet)

    candidate_payload = build_api_runner_profile_promotion_operator_receipt(
        operator_template_csv=staging_operator_template_csv,
        readiness_json=readiness_json,
        root=root_path,
    )
    candidate_summary = candidate_payload["summary"]
    candidate_ready = bool(candidate_summary.get("operator_receipt_ready") is True)
    candidate_rows = candidate_payload["rows"]
    candidate_promote_decision_count = sum(
        1
        for row in candidate_rows
        if _text(row.get("operator_decision")) == "promote" and _text(row.get("row_status")) == "pass"
    )
    candidate_keep_enabled_decision_count = sum(
        1
        for row in candidate_rows
        if _text(row.get("operator_decision")) == "keep_enabled" and _text(row.get("row_status")) == "pass"
    )
    broad_promotion_gate_required = candidate_promote_decision_count > 0
    accuracy_gate_ready = _accuracy_parity_gate(accuracy_summary)
    science_gate_ready = _science_claim_gate(science_summary)
    broad_promotion_gate_ready = accuracy_gate_ready and science_gate_ready
    placeholder_row_count = sum(1 for row in staging_rows if _has_placeholder(row))
    approval_token_present = bool(_text(approval_token))
    approval_token_accepted = _text(approval_token) == APPROVAL_TOKEN
    live_copy_allowed = (
        mode == "live_apply"
        and candidate_ready
        and not missing_columns
        and staging_present
        and approval_token_accepted
        and (not broad_promotion_gate_required or broad_promotion_gate_ready)
    )

    blockers: list[str] = []
    if not staging_present:
        blockers.append("staging_operator_template_csv_missing")
    if missing_columns:
        blockers.append("staging_operator_template_columns_missing:" + ",".join(missing_columns))
    if not staging_rows:
        blockers.append("staging_operator_template_rows_missing")
    if not accuracy_present:
        blockers.append("accuracy_parity_scorecard_missing")
    if not science_present:
        blockers.append("science_claim_promotion_gap_closure_missing")
    if not candidate_ready:
        blockers.append("candidate_operator_receipt_not_ready")
    if broad_promotion_gate_required and not accuracy_gate_ready:
        blockers.append("broad_promotion_accuracy_parity_gate_not_ready")
    if broad_promotion_gate_required and not science_gate_ready:
        blockers.append("broad_promotion_science_claim_gate_not_ready")
    if write_canonical_operator_template and not approval_token_accepted:
        blockers.append("write_canonical_operator_template_approval_token_missing_or_invalid")
    if write_canonical_operator_template and not live_copy_allowed:
        blockers.append("write_canonical_operator_template_blocked_until_candidate_ready")

    candidate_written = False
    canonical_operator_template_written = False
    if candidate_ready:
        write_csv_rows(_resolve(candidate_operator_template_csv, root=root_path), _candidate_rows(staging_rows))
        candidate_written = True
    if write_canonical_operator_template and live_copy_allowed:
        write_csv_rows(_resolve(live_operator_template_csv, root=root_path), _candidate_rows(staging_rows))
        canonical_operator_template_written = True
        live_rows = _candidate_rows(staging_rows)

    broad_gate_blocked = broad_promotion_gate_required and not broad_promotion_gate_ready

    if canonical_operator_template_written:
        status = "api_runner_profile_promotion_operator_template_canonical_written"
        next_required_step = "Canonical API runner promotion operator template updated; rerun receipt, profile validation, release bundle, and source-of-truth gates."
    elif live_copy_allowed:
        status = "api_runner_profile_promotion_operator_staging_apply_ready_for_live_copy"
        next_required_step = "Candidate operator receipt is ready. Rerun with --write-canonical-operator-template and approval token only after operator review."
    elif candidate_ready and not broad_gate_blocked:
        status = "api_runner_profile_promotion_operator_staging_preview_ready"
        next_required_step = "Review the candidate operator receipt and science/accuracy gate state before any canonical operator-template copy."
    else:
        status = "blocked_api_runner_profile_promotion_operator_staging_apply"
        next_required_step = (
            "Clear the candidate receipt and any required broad-promotion accuracy/science gates before touching "
            "the canonical operator template."
        )

    summary = {
        "packet_type": "api_runner_profile_promotion_operator_staging_apply",
        "status": status,
        "mode": mode,
        "staging_operator_template_csv": _display_path(staging_operator_template_csv, root=root_path),
        "staging_operator_template_csv_present": staging_present,
        "staging_row_count": len(staging_rows),
        "staging_missing_required_column_count": len(missing_columns),
        "staging_placeholder_row_count": placeholder_row_count,
        "live_operator_template_csv": _display_path(live_operator_template_csv, root=root_path),
        "live_operator_template_csv_present": live_present,
        "live_operator_template_row_count": len(live_rows),
        "candidate_operator_template_csv": _display_path(candidate_operator_template_csv, root=root_path),
        "candidate_operator_template_written": candidate_written,
        "candidate_operator_receipt_ready": candidate_ready,
        "candidate_operator_receipt_status": _text(candidate_summary.get("status")),
        "candidate_profile_count": int(candidate_summary.get("profile_count") or 0),
        "candidate_pass_row_count": int(candidate_summary.get("pass_row_count") or 0),
        "candidate_blocked_row_count": int(candidate_summary.get("blocked_row_count") or 0),
        "candidate_blocker_count": int(candidate_summary.get("blocker_count") or 0),
        "candidate_first_blocked_profile_id": _text(candidate_summary.get("first_blocked_profile_id")),
        "candidate_first_blocked_row_blocker": _text(candidate_summary.get("first_blocked_row_blocker")),
        "candidate_most_common_row_blocker": _text(candidate_summary.get("most_common_row_blocker")),
        "candidate_approved_profile_count": int(candidate_summary.get("approved_profile_count") or 0),
        "candidate_promote_decision_count": candidate_promote_decision_count,
        "candidate_keep_enabled_decision_count": candidate_keep_enabled_decision_count,
        "accuracy_parity_artifact": _display_path(accuracy_parity_json, root=root_path),
        "accuracy_parity_present": accuracy_present,
        "accuracy_parity_status": _text(accuracy_summary.get("status")),
        "accuracy_parity_gate_ready": accuracy_gate_ready,
        "overall_commercial_tool_accuracy_parity_allowed": bool(
            accuracy_summary.get("overall_commercial_tool_accuracy_parity_allowed") is True
        ),
        "schrodinger_class_claim_allowed": bool(accuracy_summary.get("schrodinger_class_claim_allowed") is True),
        "science_claim_artifact": _display_path(science_claim_json, root=root_path),
        "science_claim_present": science_present,
        "science_claim_status": _text(science_summary.get("status")),
        "science_claim_gate_ready": science_gate_ready,
        "science_claim_promotion_allowed": bool(science_summary.get("claim_promotion_allowed") is True),
        "science_claim_open_gap_count": int(science_summary.get("open_gap_count") or 0),
        "science_claim_open_gap_ids": list(science_summary.get("open_gap_ids") or []),
        "broad_promotion_gate_required": broad_promotion_gate_required,
        "broad_promotion_gate_ready": broad_promotion_gate_ready,
        "broad_commercial_profile_promotion_allowed": bool(
            candidate_ready and (not broad_promotion_gate_required or broad_promotion_gate_ready)
        ),
        "approval_token_required": APPROVAL_TOKEN if mode == "live_apply" or write_canonical_operator_template else "",
        "approval_token_present": approval_token_present,
        "approval_token_accepted": approval_token_accepted if mode == "live_apply" or write_canonical_operator_template else False,
        "live_copy_allowed": live_copy_allowed,
        "write_canonical_operator_template_requested": bool(write_canonical_operator_template),
        "canonical_operator_template_written": canonical_operator_template_written,
        "profile_json_edited_by_this_tool": False,
        "profile_enabled_by_this_tool": False,
        "runner_executed": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": next_required_step,
        "source_artifacts": [
            str(staging_operator_template_csv),
            str(live_operator_template_csv),
            str(readiness_json),
            str(accuracy_parity_json),
            str(science_claim_json),
        ],
    }
    return {
        "summary": summary,
        "rows": _row_reports(candidate_rows),
        "candidate_operator_template_rows": _candidate_rows(staging_rows),
        "candidate_operator_receipt_summary": candidate_summary,
        "required_columns": list(REQUIRED_COLUMNS),
    }


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    summary = payload["summary"]
    lines = [
        "# API Runner Profile Promotion Operator Staging Apply",
        "",
        f"- status: `{summary['status']}`",
        f"- mode: `{summary['mode']}`",
        f"- candidate_operator_receipt_ready: `{summary['candidate_operator_receipt_ready']}`",
        f"- candidate pass/blocked: `{summary['candidate_pass_row_count']}/{summary['candidate_blocked_row_count']}`",
        f"- candidate_first_blocked_profile_id: `{summary['candidate_first_blocked_profile_id']}`",
        f"- candidate_most_common_row_blocker: `{summary['candidate_most_common_row_blocker']}`",
        f"- accuracy_parity_gate_ready: `{summary['accuracy_parity_gate_ready']}`",
        f"- science_claim_gate_ready: `{summary['science_claim_gate_ready']}`",
        f"- broad_promotion_gate_required: `{summary['broad_promotion_gate_required']}`",
        f"- broad_promotion_gate_ready: `{summary['broad_promotion_gate_ready']}`",
        f"- live_copy_allowed: `{summary['live_copy_allowed']}`",
        f"- canonical_operator_template_written: `{summary['canonical_operator_template_written']}`",
        "",
        "## Paths",
        "",
        f"- staging_operator_template_csv: `{summary['staging_operator_template_csv']}`",
        f"- live_operator_template_csv: `{summary['live_operator_template_csv']}`",
        f"- candidate_operator_template_csv: `{summary['candidate_operator_template_csv']}`",
        "",
        "## Blockers",
    ]
    blockers = summary.get("blockers") or []
    if blockers:
        lines.extend(f"- `{blocker}`" for blocker in blockers)
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Profiles",
            "",
            "| profile | decision | candidate status | blockers |",
            "| --- | --- | --- | --- |",
        ]
    )
    for row in payload["rows"]:
        lines.append(
            f"| `{row['profile_id']}` | `{row['operator_decision']}` | "
            f"`{row['candidate_row_status']}` | `{row['candidate_blockers']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", summary["claim_boundary"], "", "## Next Step", "", f"- {summary['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build API runner profile promotion operator staging apply preview.")
    parser.add_argument("--staging-operator-template-csv", default=DEFAULT_STAGING_OPERATOR_TEMPLATE_CSV)
    parser.add_argument("--live-operator-template-csv", default=DEFAULT_LIVE_OPERATOR_TEMPLATE_CSV)
    parser.add_argument("--readiness-json", default=DEFAULT_READINESS_JSON)
    parser.add_argument("--accuracy-parity-json", default=DEFAULT_ACCURACY_PARITY_JSON)
    parser.add_argument("--science-claim-json", default=DEFAULT_SCIENCE_CLAIM_JSON)
    parser.add_argument("--candidate-operator-template-csv", default=DEFAULT_CANDIDATE_OPERATOR_TEMPLATE_CSV)
    parser.add_argument("--mode", choices=["preview", "live_apply"], default="preview")
    parser.add_argument("--write-canonical-operator-template", action="store_true")
    parser.add_argument("--approval-token", default="")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_api_runner_profile_promotion_operator_staging_apply(
        staging_operator_template_csv=args.staging_operator_template_csv,
        live_operator_template_csv=args.live_operator_template_csv,
        readiness_json=args.readiness_json,
        accuracy_parity_json=args.accuracy_parity_json,
        science_claim_json=args.science_claim_json,
        candidate_operator_template_csv=args.candidate_operator_template_csv,
        mode=args.mode,
        write_canonical_operator_template=args.write_canonical_operator_template,
        approval_token=args.approval_token,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
