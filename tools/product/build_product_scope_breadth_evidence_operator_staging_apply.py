#!/usr/bin/env python3
"""Preview and optionally apply operator-filled R8 scope-breadth evidence receipts."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.product.build_product_scope_breadth_evidence_operator_field_worksheet import (
    DEFAULT_OUT_JSON as DEFAULT_FIELD_WORKSHEET_JSON,
)
from tools.product.build_product_scope_breadth_evidence_receipt import (
    APPROVAL_TOKEN,
    DEFAULT_RECEIPT_CSV,
    DEFAULT_SCOPE_CHECKLIST_JSON,
    REQUIRED_COLUMNS,
    build_product_scope_breadth_evidence_receipt,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STAGING_RECEIPT_CSV = DEFAULT_RECEIPT_CSV
DEFAULT_LIVE_RECEIPT_CSV = DEFAULT_RECEIPT_CSV
DEFAULT_OUT_JSON = "runs/product_scope_breadth_evidence_operator_staging_apply_current.json"
DEFAULT_OUT_CSV = "runs/product_scope_breadth_evidence_operator_staging_apply_current.csv"
DEFAULT_OUT_MD = "runs/product_scope_breadth_evidence_operator_staging_apply_current.md"
DEFAULT_CANDIDATE_RECEIPT_CSV = "runs/product_scope_breadth_evidence_receipt_candidate_current.csv"

CLAIM_BOUNDARY = (
    "Product scope breadth evidence operator staging apply only; it validates an operator-filled R8 "
    "scope-breadth evidence receipt CSV before canonical receipt copy. Preview mode does not edit "
    "tracked receipt inputs, acquire evidence, run docking, promote claims, upload, email, delete, "
    "commit, push, or mutate external state."
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


def _row_reports(receipt_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    reports: list[dict[str, Any]] = []
    for idx, row in enumerate(receipt_rows, start=1):
        reports.append(
            {
                "staging_row_index": idx,
                "scope_blocker_id": _text(row.get("scope_blocker_id")),
                "candidate_row_status": _text(row.get("row_status")),
                "candidate_blockers": _text(row.get("blockers")),
                "candidate_observed_evidence_status": _text(row.get("observed_evidence_status")),
                "candidate_expected_evidence_status": _text(row.get("expected_evidence_status")),
                "candidate_missing_true_fields": _text(row.get("missing_true_fields")),
                "candidate_evidence_artifact": _text(row.get("evidence_artifact")),
                "candidate_copy_allowed": _text(row.get("row_status")) == "pass",
                "claim_promoted": False,
                "external_state_mutated": False,
            }
        )
    return reports


def build_product_scope_breadth_evidence_operator_staging_apply(
    *,
    staging_csv: str | Path = DEFAULT_STAGING_RECEIPT_CSV,
    live_receipt_csv: str | Path = DEFAULT_LIVE_RECEIPT_CSV,
    scope_checklist_json: str | Path = DEFAULT_SCOPE_CHECKLIST_JSON,
    field_worksheet_json: str | Path = DEFAULT_FIELD_WORKSHEET_JSON,
    candidate_receipt_csv: str | Path = DEFAULT_CANDIDATE_RECEIPT_CSV,
    mode: str = "preview",
    write_canonical_receipt: bool = False,
    approval_token: str = "",
    root: str | Path = ROOT,
) -> dict[str, Any]:
    root_path = Path(root)
    staging_rows, staging_columns, staging_present = _read_csv(staging_csv, root=root_path)
    live_rows, _, live_present = _read_csv(live_receipt_csv, root=root_path)
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in staging_columns] if staging_present else list(REQUIRED_COLUMNS)
    field_worksheet_packet, field_worksheet_present = _read_json(field_worksheet_json, root=root_path)
    field_worksheet = _summary(field_worksheet_packet)
    candidate_payload = build_product_scope_breadth_evidence_receipt(
        receipt_csv=staging_csv,
        scope_checklist_json=scope_checklist_json,
        root=root_path,
    )
    candidate_summary = candidate_payload["summary"]
    candidate_ready = bool(candidate_summary.get("full_scope_evidence_receipt_ready") is True)
    placeholder_row_count = sum(1 for row in staging_rows if _has_placeholder(row))
    approval_token_present = bool(_text(approval_token))
    approval_token_accepted = _text(approval_token) == APPROVAL_TOKEN
    live_copy_allowed = (
        mode == "live_apply"
        and candidate_ready
        and not missing_columns
        and staging_present
        and approval_token_accepted
    )

    blockers: list[str] = []
    if not staging_present:
        blockers.append("staging_receipt_csv_missing")
    if missing_columns:
        blockers.append("staging_receipt_columns_missing:" + ",".join(missing_columns))
    if not staging_rows:
        blockers.append("staging_receipt_rows_missing")
    if not field_worksheet_present:
        blockers.append("operator_field_worksheet_missing")
    if not candidate_ready:
        blockers.append("candidate_receipt_not_ready")
    if write_canonical_receipt and not approval_token_accepted:
        blockers.append("write_canonical_receipt_approval_token_missing_or_invalid")
    if write_canonical_receipt and not live_copy_allowed:
        blockers.append("write_canonical_receipt_blocked_until_candidate_ready")

    candidate_written = False
    canonical_receipt_written = False
    if candidate_ready:
        write_csv_rows(_resolve(candidate_receipt_csv, root=root_path), _candidate_rows(staging_rows))
        candidate_written = True
    if write_canonical_receipt and live_copy_allowed:
        write_csv_rows(_resolve(live_receipt_csv, root=root_path), _candidate_rows(staging_rows))
        canonical_receipt_written = True
        live_rows = _candidate_rows(staging_rows)

    if canonical_receipt_written:
        status = "product_scope_breadth_evidence_receipt_canonical_written"
        next_required_step = "Canonical R8 scope-breadth evidence receipt updated; rerun receipt, goal audit, release bundle, and source-of-truth gates."
    elif live_copy_allowed:
        status = "product_scope_breadth_evidence_operator_staging_apply_ready_for_live_copy"
        next_required_step = "Candidate receipt is ready. Rerun with --write-canonical-receipt and the approval token only after operator review."
    elif candidate_ready:
        status = "product_scope_breadth_evidence_operator_staging_preview_ready"
        next_required_step = "Review the candidate receipt CSV, then use live_apply mode with the approval token to update the canonical R8 receipt."
    else:
        status = "blocked_product_scope_breadth_evidence_operator_staging_apply"
        next_required_step = "Fill or repair the R8 staging receipt rows until the candidate receipt gate passes before touching the canonical receipt CSV."

    summary = {
        "packet_type": "product_scope_breadth_evidence_operator_staging_apply",
        "status": status,
        "mode": mode,
        "staging_csv": _display_path(staging_csv, root=root_path),
        "staging_csv_present": staging_present,
        "staging_row_count": len(staging_rows),
        "staging_missing_required_column_count": len(missing_columns),
        "staging_placeholder_row_count": placeholder_row_count,
        "live_receipt_csv": _display_path(live_receipt_csv, root=root_path),
        "live_receipt_csv_present": live_present,
        "live_receipt_row_count": len(live_rows),
        "candidate_receipt_csv": _display_path(candidate_receipt_csv, root=root_path),
        "candidate_receipt_written": candidate_written,
        "candidate_receipt_ready": candidate_ready,
        "candidate_receipt_status": _text(candidate_summary.get("status")),
        "candidate_pass_row_count": int(candidate_summary.get("pass_row_count") or 0),
        "candidate_blocked_row_count": int(candidate_summary.get("blocked_row_count") or 0),
        "candidate_blocker_count": int(candidate_summary.get("blocker_count") or 0),
        "candidate_evidence_artifact_present_count": int(candidate_summary.get("evidence_artifact_present_count") or 0),
        "candidate_evidence_status_verified_count": int(candidate_summary.get("evidence_status_verified_count") or 0),
        "candidate_first_blocked_scope_blocker_id": _text(candidate_summary.get("first_blocked_scope_blocker_id")),
        "candidate_first_blocked_evidence_artifact": _text(candidate_summary.get("first_blocked_evidence_artifact")),
        "candidate_first_blocked_expected_evidence_status": _text(candidate_summary.get("first_blocked_expected_evidence_status")),
        "candidate_first_blocked_observed_evidence_status": _text(candidate_summary.get("first_blocked_observed_evidence_status")),
        "candidate_most_common_row_blocker": _text(candidate_summary.get("most_common_row_blocker")),
        "field_worksheet_artifact": _display_path(field_worksheet_json, root=root_path),
        "field_worksheet_present": field_worksheet_present,
        "field_worksheet_status": _text(field_worksheet.get("status")),
        "field_worksheet_pending_field_count": int(field_worksheet.get("operator_fill_pending_field_count") or 0),
        "field_worksheet_top_blocker_id": _text(field_worksheet.get("top_blocker_id")),
        "field_worksheet_top_item_id": _text(field_worksheet.get("top_item_id")),
        "field_worksheet_top_bucket": _text(field_worksheet.get("top_bucket")),
        "approval_token_required": APPROVAL_TOKEN if mode == "live_apply" or write_canonical_receipt else "",
        "approval_token_present": approval_token_present,
        "approval_token_accepted": approval_token_accepted if mode == "live_apply" or write_canonical_receipt else False,
        "live_copy_allowed": live_copy_allowed,
        "write_canonical_receipt_requested": bool(write_canonical_receipt),
        "canonical_receipt_written": canonical_receipt_written,
        "claim_promotion_allowed": False,
        "claim_promoted": False,
        "external_state_mutated": False,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": next_required_step,
        "source_artifacts": [
            str(staging_csv),
            str(live_receipt_csv),
            str(scope_checklist_json),
            str(field_worksheet_json),
        ],
    }
    return {
        "summary": summary,
        "rows": _row_reports(candidate_payload["rows"]),
        "candidate_receipt_rows": _candidate_rows(staging_rows),
        "candidate_receipt_summary": candidate_summary,
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
        "# Product Scope Breadth Evidence Operator Staging Apply",
        "",
        f"- status: `{summary['status']}`",
        f"- mode: `{summary['mode']}`",
        f"- candidate_receipt_ready: `{summary['candidate_receipt_ready']}`",
        f"- candidate pass/blocked: `{summary['candidate_pass_row_count']}/{summary['candidate_blocked_row_count']}`",
        f"- staging_placeholder_row_count: `{summary['staging_placeholder_row_count']}`",
        f"- candidate_first_blocked_scope_blocker_id: `{summary['candidate_first_blocked_scope_blocker_id']}`",
        f"- candidate_most_common_row_blocker: `{summary['candidate_most_common_row_blocker']}`",
        f"- field_worksheet_pending_field_count: `{summary['field_worksheet_pending_field_count']}`",
        f"- live_copy_allowed: `{summary['live_copy_allowed']}`",
        f"- canonical_receipt_written: `{summary['canonical_receipt_written']}`",
        f"- approval_token_required: `{summary['approval_token_required']}`",
        "",
        "## Paths",
        "",
        f"- staging_csv: `{summary['staging_csv']}`",
        f"- live_receipt_csv: `{summary['live_receipt_csv']}`",
        f"- candidate_receipt_csv: `{summary['candidate_receipt_csv']}`",
        "",
        "## Blockers",
    ]
    lines.extend(f"- `{blocker}`" for blocker in summary["blockers"])
    if not summary["blockers"]:
        lines.append("- none")
    lines.extend(["", "## Rows", "", "| scope blocker | status | observed | blockers |", "| --- | --- | --- | --- |"])
    for row in payload["rows"]:
        lines.append(
            f"| `{row['scope_blocker_id']}` | `{row['candidate_row_status']}` | "
            f"`{row['candidate_observed_evidence_status']}` | `{row['candidate_blockers']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", summary["claim_boundary"], ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Preview and optionally apply an operator-filled R8 scope-breadth evidence receipt."
    )
    parser.add_argument("--staging-csv", default=DEFAULT_STAGING_RECEIPT_CSV)
    parser.add_argument("--live-receipt-csv", default=DEFAULT_LIVE_RECEIPT_CSV)
    parser.add_argument("--scope-checklist-json", default=DEFAULT_SCOPE_CHECKLIST_JSON)
    parser.add_argument("--field-worksheet-json", default=DEFAULT_FIELD_WORKSHEET_JSON)
    parser.add_argument("--candidate-receipt-csv", default=DEFAULT_CANDIDATE_RECEIPT_CSV)
    parser.add_argument("--mode", choices=("preview", "live_apply"), default="preview")
    parser.add_argument("--write-canonical-receipt", action="store_true")
    parser.add_argument("--approval-token", default="")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    root = Path(args.root)
    payload = build_product_scope_breadth_evidence_operator_staging_apply(
        staging_csv=args.staging_csv,
        live_receipt_csv=args.live_receipt_csv,
        scope_checklist_json=args.scope_checklist_json,
        field_worksheet_json=args.field_worksheet_json,
        candidate_receipt_csv=args.candidate_receipt_csv,
        mode=args.mode,
        write_canonical_receipt=bool(args.write_canonical_receipt),
        approval_token=args.approval_token,
        root=root,
    )
    _write_json(args.out_json, payload, root=root)
    write_csv_rows(_resolve(args.out_csv, root=root), payload["rows"])
    _write_markdown(args.out_md, payload, root=root)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
