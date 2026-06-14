#!/usr/bin/env python3
"""Fail-closed receipt gate for broad GPCR claim review evidence."""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RECEIPT_CSV = "config/gpcr_broad_claim_review_receipt_current.csv"
DEFAULT_OUT_JSON = "runs/gpcr_broad_claim_review_receipt_current.json"
DEFAULT_OUT_CSV = "runs/gpcr_broad_claim_review_receipt_current.csv"
DEFAULT_OUT_MD = "runs/gpcr_broad_claim_review_receipt_current.md"
APPROVAL_TOKEN = "APPROVE_GPCR_BROAD_CLAIM_REVIEW"

CLAIM_BOUNDARY = (
    "GPCR broad claim review receipt only; it validates local operator-provided evidence packets for "
    "target-held-out broad claim review and scorer/router promotion gate approval. It does not run docking, "
    "promote claims, mutate router defaults, upload, email, commit, push, or mutate external state."
)

REQUIRED_REVIEW_IDS = [
    "target_heldout_broad_scope_review_not_approved",
    "scorer_router_promotion_gate_not_approved",
]

REQUIRED_COLUMNS = [
    "review_id",
    "evidence_artifact",
    "evidence_status",
    "claim_ready",
    "reviewer",
    "reviewed_at_utc",
    "provenance_kind",
    "license_ok",
    "external_engine_calls",
    "approval_token",
    "operator_attestation",
    "notes",
]

MANUAL_REVIEW_FIELDS = [
    "evidence_artifact",
    "claim_ready",
    "reviewer",
    "reviewed_at_utc",
    "license_ok",
    "approval_token",
    "operator_attestation",
    "notes",
]

ALLOWED_PROVENANCE_KINDS = {
    "target_heldout_public_benchmark_review",
    "scorer_router_promotion_gate",
    "operator_curated_public",
    "independent_science_review",
}

EXPECTED_EVIDENCE = {
    "target_heldout_broad_scope_review_not_approved": {
        "status": "gpcr_target_heldout_broad_claim_review_ready",
        "true_fields": ["target_heldout_broad_scope_review_approved"],
    },
    "scorer_router_promotion_gate_not_approved": {
        "status": "gpcr_scorer_router_promotion_gate_ready",
        "true_fields": [
            "scorer_router_promotion_gate_ready",
            "active_scorer_apply_allowed",
            "router_claim_allowed",
            "platform_claim_allowed",
        ],
    },
}

PLACEHOLDER_PREFIXES = ("OPERATOR_FILL", "OPERATOR_CONFIRM")


def _resolve(path_like: str | Path, *, root: Path = ROOT) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else root / path


def _text(value: Any) -> str:
    return str(value or "").strip()


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).lower() in {"1", "true", "yes", "y"}


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(float(_text(value)))
    except (TypeError, ValueError):
        return default


def _read_csv(path_like: str | Path, *, root: Path = ROOT) -> tuple[list[dict[str, Any]], list[str], bool]:
    path = _resolve(path_like, root=root)
    if not path.exists():
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
    return any(_text(value).startswith(PLACEHOLDER_PREFIXES) for value in row.values())


def _reviewed_at_valid(value: Any) -> bool:
    text = _text(value)
    if not text:
        return False
    try:
        dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _split_blockers(value: Any) -> list[str]:
    return [item for item in _text(value).split(";") if item]


def _is_placeholder(value: Any) -> bool:
    return _text(value).startswith(PLACEHOLDER_PREFIXES)


def _manual_pending_fields(row: dict[str, Any], *, evidence_present: bool) -> list[str]:
    pending: list[str] = []
    if not _text(row.get("evidence_artifact")) or _is_placeholder(row.get("evidence_artifact")) or not evidence_present:
        pending.append("evidence_artifact")
    if _bool(row.get("claim_ready")) is not True:
        pending.append("claim_ready")
    if not _text(row.get("reviewer")) or _is_placeholder(row.get("reviewer")):
        pending.append("reviewer")
    if not _reviewed_at_valid(row.get("reviewed_at_utc")):
        pending.append("reviewed_at_utc")
    if _bool(row.get("license_ok")) is not True:
        pending.append("license_ok")
    if _text(row.get("approval_token")) != APPROVAL_TOKEN:
        pending.append("approval_token")
    if _text(row.get("operator_attestation")) != "reviewed_for_broad_gpcr_claim":
        pending.append("operator_attestation")
    if not _text(row.get("notes")) or _is_placeholder(row.get("notes")):
        pending.append("notes")
    return pending


def _most_common_blocker(rows: list[dict[str, Any]]) -> str:
    counts: dict[str, int] = {}
    first_seen: dict[str, int] = {}
    for row in rows:
        for blocker in _split_blockers(row.get("blockers")):
            if blocker not in first_seen:
                first_seen[blocker] = len(first_seen)
            counts[blocker] = counts.get(blocker, 0) + 1
    if not counts:
        return ""
    return sorted(counts.items(), key=lambda item: (-item[1], first_seen[item[0]]))[0][0]


def _row_status(
    row: dict[str, Any],
    *,
    duplicate_review_ids: set[str],
    root: Path = ROOT,
) -> dict[str, Any]:
    review_id = _text(row.get("review_id"))
    expected = EXPECTED_EVIDENCE.get(review_id, {})
    evidence_artifact = _text(row.get("evidence_artifact"))
    evidence_packet, evidence_present = _read_json(evidence_artifact, root=root) if evidence_artifact else ({}, False)
    evidence_summary = _summary(evidence_packet)
    expected_status = _text(expected.get("status"))
    expected_true_fields = [str(field) for field in expected.get("true_fields", [])]
    missing_true_fields = [field for field in expected_true_fields if evidence_summary.get(field) is not True]
    manual_pending_fields = _manual_pending_fields(row, evidence_present=evidence_present)
    evidence_status_contract_present = bool(
        expected_status and _text(row.get("evidence_status")) == expected_status
    )
    provenance_kind_accepted = _text(row.get("provenance_kind")) in ALLOWED_PROVENANCE_KINDS
    external_engine_calls_zero = _int(row.get("external_engine_calls"), default=999999) == 0
    operator_review_surface_ready = bool(
        review_id in REQUIRED_REVIEW_IDS
        and expected_status
        and expected_true_fields
        and evidence_status_contract_present
        and provenance_kind_accepted
        and external_engine_calls_zero
    )
    blockers: list[str] = []

    if review_id not in REQUIRED_REVIEW_IDS:
        blockers.append("review_id_missing_or_unrecognized")
    if review_id in duplicate_review_ids:
        blockers.append("duplicate_review_id")
    if _has_placeholder(row):
        blockers.append("operator_placeholders_unfilled")
    if not evidence_artifact:
        blockers.append("evidence_artifact_missing")
    elif not evidence_present:
        blockers.append("evidence_artifact_not_found")
    elif not evidence_summary:
        blockers.append("evidence_json_unreadable_or_missing_status")
    if evidence_summary and expected_status and _text(evidence_summary.get("status")) != expected_status:
        blockers.append("evidence_status_mismatch")
    if missing_true_fields:
        blockers.append("evidence_true_fields_missing:" + ",".join(missing_true_fields))
    if _text(row.get("evidence_status")) != expected_status:
        blockers.append("receipt_evidence_status_mismatch")
    if _bool(row.get("claim_ready")) is not True:
        blockers.append("claim_ready_not_true")
    if not _text(row.get("reviewer")):
        blockers.append("reviewer_missing")
    if not _reviewed_at_valid(row.get("reviewed_at_utc")):
        blockers.append("reviewed_at_utc_missing_or_invalid")
    if _text(row.get("provenance_kind")) not in ALLOWED_PROVENANCE_KINDS:
        blockers.append("provenance_kind_unaccepted")
    if _bool(row.get("license_ok")) is not True:
        blockers.append("license_not_ok")
    if _int(row.get("external_engine_calls"), default=999999) != 0:
        blockers.append("external_engine_calls_present")
    if _text(row.get("approval_token")) != APPROVAL_TOKEN:
        blockers.append("approval_token_missing_or_invalid")
    if _text(row.get("operator_attestation")) != "reviewed_for_broad_gpcr_claim":
        blockers.append("operator_attestation_missing_or_unaccepted")

    return {
        **{column: row.get(column, "") for column in REQUIRED_COLUMNS},
        "row_status": "pass" if not blockers else "blocked",
        "blockers": ";".join(blockers),
        "expected_evidence_status": expected_status,
        "expected_true_fields": ";".join(expected_true_fields),
        "expected_true_field_count": len(expected_true_fields),
        "missing_true_fields": ";".join(missing_true_fields),
        "evidence_artifact_present": evidence_present,
        "observed_evidence_status": _text(evidence_summary.get("status")) or "missing",
        "evidence_status_contract_present": evidence_status_contract_present,
        "provenance_kind_accepted": provenance_kind_accepted,
        "external_engine_calls_zero": external_engine_calls_zero,
        "operator_review_surface_ready": operator_review_surface_ready,
        "operator_manual_pending_fields": ";".join(manual_pending_fields),
        "operator_manual_pending_field_count": len(manual_pending_fields),
        "external_state_mutated": False,
    }


def build_gpcr_broad_claim_review_receipt(
    *,
    receipt_csv: str | Path = DEFAULT_RECEIPT_CSV,
    root: str | Path = ROOT,
) -> dict[str, Any]:
    root_path = Path(root)
    raw_rows, columns, present = _read_csv(receipt_csv, root=root_path)
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in columns] if present else list(REQUIRED_COLUMNS)
    review_ids = [_text(row.get("review_id")) for row in raw_rows if _text(row.get("review_id"))]
    duplicate_review_ids = sorted({review_id for review_id in review_ids if review_ids.count(review_id) > 1})
    rows = [_row_status(row, duplicate_review_ids=set(duplicate_review_ids), root=root_path) for row in raw_rows]
    present_review_ids = {_text(row.get("review_id")) for row in raw_rows}
    missing_required_reviews = [review_id for review_id in REQUIRED_REVIEW_IDS if review_id not in present_review_ids]
    blocked_rows = [row for row in rows if row["row_status"] != "pass"]
    pass_rows = [row for row in rows if row["row_status"] == "pass"]
    operator_review_surface_ready_rows = [
        row for row in rows if row.get("operator_review_surface_ready") is True
    ]
    operator_review_surface_blocked_rows = [
        row for row in rows if row.get("operator_review_surface_ready") is not True
    ]
    row_blocker_tokens = sorted({blocker for row in rows for blocker in _split_blockers(row.get("blockers"))})
    target_review_pass = any(
        row["review_id"] == "target_heldout_broad_scope_review_not_approved" and row["row_status"] == "pass"
        for row in rows
    )
    scorer_router_pass = any(
        row["review_id"] == "scorer_router_promotion_gate_not_approved" and row["row_status"] == "pass"
        for row in rows
    )

    blockers: list[str] = []
    if not present:
        blockers.append("receipt_csv_missing")
    if missing_columns:
        blockers.append("receipt_columns_missing")
    if missing_required_reviews:
        blockers.append("required_review_rows_missing")
    if duplicate_review_ids:
        blockers.append("duplicate_review_ids_present")
    if blocked_rows:
        blockers.append("blocked_receipt_rows_present")

    receipt_ready = bool(present and not blockers and len(pass_rows) == len(REQUIRED_REVIEW_IDS))
    first_blocked = blocked_rows[0] if blocked_rows else {}
    summary = {
        "packet_type": "gpcr_broad_claim_review_receipt",
        "status": "gpcr_broad_claim_review_receipt_ready" if receipt_ready else "blocked_gpcr_broad_claim_review_receipt",
        "receipt_csv": str(receipt_csv),
        "receipt_csv_present": present,
        "receipt_row_count": len(raw_rows),
        "required_review_count": len(REQUIRED_REVIEW_IDS),
        "missing_required_review_count": len(missing_required_reviews),
        "missing_required_reviews": missing_required_reviews,
        "duplicate_review_id_count": len(duplicate_review_ids),
        "duplicate_review_ids": duplicate_review_ids,
        "missing_required_column_count": len(missing_columns),
        "missing_required_columns": missing_columns,
        "pass_row_count": len(pass_rows),
        "blocked_row_count": len(blocked_rows),
        "operator_review_surface_ready_count": len(operator_review_surface_ready_rows),
        "operator_review_surface_blocked_count": len(operator_review_surface_blocked_rows),
        "evidence_artifact_present_count": len(
            [row for row in rows if row.get("evidence_artifact_present") is True]
        ),
        "evidence_status_contract_present_count": len(
            [row for row in rows if row.get("evidence_status_contract_present") is True]
        ),
        "expected_true_fields_present_count": len(
            [row for row in rows if _int(row.get("expected_true_field_count")) > 0]
        ),
        "provenance_kind_accepted_count": len(
            [row for row in rows if row.get("provenance_kind_accepted") is True]
        ),
        "external_engine_calls_zero_count": len(
            [row for row in rows if row.get("external_engine_calls_zero") is True]
        ),
        "receipt_manual_field_pending_count": sum(
            _int(row.get("operator_manual_pending_field_count")) for row in rows
        ),
        "receipt_evidence_artifact_pending_count": len(
            [row for row in rows if "evidence_artifact" in _split_blockers(row.get("operator_manual_pending_fields"))]
        ),
        "receipt_claim_ready_pending_count": len(
            [row for row in rows if "claim_ready" in _split_blockers(row.get("operator_manual_pending_fields"))]
        ),
        "receipt_reviewer_pending_count": len(
            [row for row in rows if "reviewer" in _split_blockers(row.get("operator_manual_pending_fields"))]
        ),
        "receipt_reviewed_at_utc_pending_count": len(
            [row for row in rows if "reviewed_at_utc" in _split_blockers(row.get("operator_manual_pending_fields"))]
        ),
        "receipt_license_ok_pending_count": len(
            [row for row in rows if "license_ok" in _split_blockers(row.get("operator_manual_pending_fields"))]
        ),
        "receipt_approval_token_pending_count": len(
            [row for row in rows if "approval_token" in _split_blockers(row.get("operator_manual_pending_fields"))]
        ),
        "receipt_operator_attestation_pending_count": len(
            [
                row
                for row in rows
                if "operator_attestation" in _split_blockers(row.get("operator_manual_pending_fields"))
            ]
        ),
        "receipt_notes_pending_count": len(
            [row for row in rows if "notes" in _split_blockers(row.get("operator_manual_pending_fields"))]
        ),
        "row_blocker_count": len(row_blocker_tokens),
        "most_common_row_blocker": _most_common_blocker(rows),
        "first_blocked_review_id": _text(first_blocked.get("review_id")),
        "first_blocked_evidence_artifact": _text(first_blocked.get("evidence_artifact")),
        "first_blocked_expected_evidence_status": _text(first_blocked.get("expected_evidence_status")),
        "first_blocked_observed_evidence_status": _text(first_blocked.get("observed_evidence_status")),
        "first_blocked_row_blockers": _split_blockers(first_blocked.get("blockers")),
        "target_heldout_broad_scope_review_approved": target_review_pass,
        "scorer_router_promotion_gate_approved": scorer_router_pass,
        "broad_claim_review_receipt_ready": receipt_ready,
        "approval_token_required": APPROVAL_TOKEN,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "claim_boundary": CLAIM_BOUNDARY,
        "execution_enabled": False,
        "external_state_mutated": False,
        "next_required_step": (
            "Receipt ready; GPCR broad claim-scope readiness can consume this review evidence."
            if receipt_ready
            else "Replace placeholder GPCR broad-claim review rows with local evidence JSON paths, reviewed provenance, "
            "license flags, zero external engine calls, and APPROVE_GPCR_BROAD_CLAIM_REVIEW "
            f"(operator_review_surface_ready_count={len(operator_review_surface_ready_rows)}, "
            f"receipt_manual_field_pending_count="
            f"{sum(_int(row.get('operator_manual_pending_field_count')) for row in rows)})."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    return "\n".join(
        [
            "# GPCR Broad Claim Review Receipt",
            "",
            f"- status: `{summary['status']}`",
            f"- receipt_csv_present: `{summary['receipt_csv_present']}`",
            f"- pass/blocked rows: `{summary['pass_row_count']}/{summary['blocked_row_count']}`",
            f"- operator_review_surface_ready/blocked: `{summary['operator_review_surface_ready_count']}/"
            f"{summary['operator_review_surface_blocked_count']}`",
            f"- receipt_manual_field_pending_count: `{summary['receipt_manual_field_pending_count']}`",
            f"- target_heldout_broad_scope_review_approved: `{summary['target_heldout_broad_scope_review_approved']}`",
            f"- scorer_router_promotion_gate_approved: `{summary['scorer_router_promotion_gate_approved']}`",
            f"- approval_token_required: `{summary['approval_token_required']}`",
            f"- blockers: `{', '.join(summary['blockers']) or 'none'}`",
            "",
            "## Next Step",
            "",
            f"- {summary['next_required_step']}",
            "",
        ]
    )


def write_outputs(
    *,
    receipt_csv: str | Path = DEFAULT_RECEIPT_CSV,
    out_json: str | Path = DEFAULT_OUT_JSON,
    out_csv: str | Path = DEFAULT_OUT_CSV,
    out_md: str | Path = DEFAULT_OUT_MD,
    root: str | Path = ROOT,
) -> dict[str, Any]:
    root_path = Path(root)
    payload = build_gpcr_broad_claim_review_receipt(receipt_csv=receipt_csv, root=root_path)
    _write_json(out_json, payload, root=root_path)
    write_csv_rows(_resolve(out_csv, root=root_path), payload["rows"])
    out_md_path = _resolve(out_md, root=root_path)
    out_md_path.parent.mkdir(parents=True, exist_ok=True)
    out_md_path.write_text(render_markdown(payload), encoding="utf-8")
    return payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build GPCR broad claim review receipt.")
    parser.add_argument("--receipt-csv", default=DEFAULT_RECEIPT_CSV)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--root", default=str(ROOT))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = write_outputs(
        receipt_csv=args.receipt_csv,
        out_json=args.out_json,
        out_csv=args.out_csv,
        out_md=args.out_md,
        root=args.root,
    )
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
