#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.product.build_product_rollout_execution_readiness import (
    APPROVAL_TOKEN,
    DEFAULT_OUT_JSON as DEFAULT_READINESS_JSON,
    HOSTED_EXPOSURE_TOKEN,
    VALID_TARGETS,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RECEIPT_CSV = "runs/product_rollout_execution_smoke_receipt_operator_intake.csv"
DEFAULT_TEMPLATE_CSV = "runs/product_rollout_execution_smoke_receipt_operator_template_current.csv"
DEFAULT_OUT_JSON = "runs/product_rollout_execution_smoke_receipt_current.json"
DEFAULT_OUT_CSV = "runs/product_rollout_execution_smoke_receipt_current.csv"
DEFAULT_OUT_MD = "runs/product_rollout_execution_smoke_receipt_current.md"

REQUIRED_COLUMNS = [
    "operator_decision",
    "rollout_approval_token",
    "hosted_exposure_approval_token",
    "target_environment",
    "image_digest_or_tag",
    "rollout_command_summary",
    "image_pushed",
    "service_restarted",
    "live_healthcheck_passed",
    "metrics_scrape_verified",
    "audit_log_write_verified",
    "rollback_probe_verified",
    "pager_provider_contacted",
    "ingress_certificate_verified_live",
    "external_state_mutated",
    "operator_name",
    "reviewed_at_utc",
    "operator_note",
]
REQUIRED_TRUE_FIELDS = [
    "image_pushed",
    "service_restarted",
    "live_healthcheck_passed",
    "metrics_scrape_verified",
    "audit_log_write_verified",
    "rollback_probe_verified",
    "pager_provider_contacted",
    "ingress_certificate_verified_live",
    "external_state_mutated",
]
VALID_DECISIONS = {"executed", "defer"}
CLAIM_BOUNDARY = (
    "Product rollout execution smoke receipt only; it validates an operator-provided receipt from a separate "
    "R4-approved rollout execution. This builder is read-only: it does not build images, push containers, apply "
    "manifests, restart services, contact providers, verify certificates, roll back services, or mutate external state."
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


def _read_csv_rows(path_like: str | Path) -> tuple[list[dict[str, str]], list[str]]:
    path = _resolve(path_like)
    if not path.exists():
        return [], []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = [dict(row) for row in reader]
    return rows, [column for column in REQUIRED_COLUMNS if column not in fieldnames]


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_template(path_like: str | Path) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REQUIRED_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerow({column: "" for column in REQUIRED_COLUMNS})


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else packet if isinstance(packet, dict) else {}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _bool_text(value: Any) -> bool:
    return _text(value).lower() in {"1", "true", "yes", "y"}


def _is_iso_timestamp(value: Any) -> bool:
    text = _text(value)
    if not text:
        return False
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _readiness_ready(readiness_packet: dict[str, Any]) -> bool:
    readiness = _summary(readiness_packet)
    return (
        _text(readiness.get("status")) == "product_rollout_execution_readiness_ready"
        and readiness.get("authorized_for_separate_operator_execution") is True
        and int(readiness.get("blocker_count") or 0) == 0
        and readiness.get("rollout_executed") is False
        and readiness.get("external_state_mutated") is False
    )


def _build_row(row_in: dict[str, Any], *, missing_columns: list[str], readiness_ready: bool) -> dict[str, Any]:
    decision = _text(row_in.get("operator_decision")).lower()
    target = _text(row_in.get("target_environment")).lower()
    rollout_token = _text(row_in.get("rollout_approval_token"))
    hosted_token = _text(row_in.get("hosted_exposure_approval_token"))
    image = _text(row_in.get("image_digest_or_tag"))
    command_summary = _text(row_in.get("rollout_command_summary"))
    operator_name = _text(row_in.get("operator_name"))
    reviewed_at_utc = _text(row_in.get("reviewed_at_utc"))
    blockers: list[str] = []
    if missing_columns:
        blockers.append("receipt_columns_missing")
    if not readiness_ready:
        blockers.append("rollout_execution_readiness_not_ready")
    if decision not in VALID_DECISIONS:
        blockers.append("operator_decision_invalid")
    if decision == "defer":
        blockers.append("operator_deferred_execution")
    if rollout_token != APPROVAL_TOKEN:
        blockers.append("rollout_approval_token_mismatch")
    if hosted_token != HOSTED_EXPOSURE_TOKEN:
        blockers.append("hosted_exposure_approval_token_mismatch")
    if target not in VALID_TARGETS:
        blockers.append("target_environment_invalid")
    if not image:
        blockers.append("image_digest_or_tag_missing")
    if not command_summary:
        blockers.append("rollout_command_summary_missing")
    for field in REQUIRED_TRUE_FIELDS:
        if not _bool_text(row_in.get(field)):
            blockers.append(f"{field}_not_true")
    if not operator_name:
        blockers.append("operator_name_missing")
    if not _is_iso_timestamp(reviewed_at_utc):
        blockers.append("reviewed_at_utc_invalid")
    return {
        "receipt_status": "pass" if not blockers else "blocked",
        "operator_decision": decision,
        "target_environment": target,
        "image_digest_or_tag": image,
        "rollout_command_summary": command_summary,
        "blocker_count": len(blockers),
        "blockers": ";".join(blockers),
        "rollout_approval_token_present": bool(rollout_token),
        "hosted_exposure_approval_token_present": bool(hosted_token),
        "image_pushed": _bool_text(row_in.get("image_pushed")),
        "service_restarted": _bool_text(row_in.get("service_restarted")),
        "live_healthcheck_passed": _bool_text(row_in.get("live_healthcheck_passed")),
        "metrics_scrape_verified": _bool_text(row_in.get("metrics_scrape_verified")),
        "audit_log_write_verified": _bool_text(row_in.get("audit_log_write_verified")),
        "rollback_probe_verified": _bool_text(row_in.get("rollback_probe_verified")),
        "pager_provider_contacted": _bool_text(row_in.get("pager_provider_contacted")),
        "ingress_certificate_verified_live": _bool_text(row_in.get("ingress_certificate_verified_live")),
        "external_state_mutated": _bool_text(row_in.get("external_state_mutated")),
        "operator_name_present": bool(operator_name),
        "reviewed_at_utc": reviewed_at_utc,
        "operator_note": _text(row_in.get("operator_note")),
    }


def build_product_rollout_execution_smoke_receipt(
    *,
    readiness_packet: dict[str, Any],
    receipt_rows: list[dict[str, Any]],
    receipt_csv_present: bool,
    receipt_csv: str = DEFAULT_RECEIPT_CSV,
    template_csv: str = DEFAULT_TEMPLATE_CSV,
    missing_columns: list[str] | None = None,
) -> dict[str, Any]:
    missing_columns = missing_columns or []
    readiness = _summary(readiness_packet)
    readiness_ok = _readiness_ready(readiness_packet)
    blockers: list[str] = []
    if not readiness_ok:
        blockers.append("rollout_execution_readiness_not_ready")
    if not receipt_csv_present:
        blockers.append("operator_rollout_execution_smoke_receipt_csv_missing")
    if not receipt_rows:
        blockers.append("operator_rollout_execution_smoke_receipt_row_missing")
    if len(receipt_rows) > 1:
        blockers.append("duplicate_operator_rollout_execution_smoke_receipt_rows")
    if missing_columns:
        blockers.append("receipt_columns_missing")
    rows = [
        _build_row(row, missing_columns=missing_columns, readiness_ready=readiness_ok)
        for row in receipt_rows
    ]
    for row in rows:
        if row["receipt_status"] != "pass":
            blockers.extend(row["blockers"].split(";") if row["blockers"] else [])
    ready_rows = [row for row in rows if row["receipt_status"] == "pass"]
    ready = bool(receipt_csv_present and readiness_ok and len(rows) == 1 and len(ready_rows) == 1 and not blockers)
    first_row = rows[0] if rows else {}
    summary = {
        "packet_type": "product_rollout_execution_smoke_receipt",
        "status": "product_rollout_execution_smoke_receipt_ready" if ready else "blocked_product_rollout_execution_smoke_receipt",
        "rollout_execution_smoke_receipt_ready": ready,
        "source_rollout_execution_readiness_status": _text(readiness.get("status")),
        "source_authorized_for_separate_operator_execution": readiness.get(
            "authorized_for_separate_operator_execution"
        )
        is True,
        "source_rollout_executed": readiness.get("rollout_executed") is True,
        "receipt_csv": receipt_csv,
        "receipt_csv_present": bool(receipt_csv_present),
        "operator_template_csv": template_csv,
        "receipt_row_count": len(rows),
        "ready_receipt_row_count": len(ready_rows),
        "blocker_count": len(sorted(set(blockers))),
        "blockers": sorted(set(blockers)),
        "target_environment": first_row.get("target_environment", ""),
        "rollout_executed": bool(first_row.get("receipt_status") == "pass"),
        "image_pushed": bool(first_row.get("image_pushed") is True),
        "service_restarted": bool(first_row.get("service_restarted") is True),
        "pager_provider_contacted": bool(first_row.get("pager_provider_contacted") is True),
        "ingress_certificate_verified_live": bool(first_row.get("ingress_certificate_verified_live") is True),
        "external_state_mutated": bool(first_row.get("external_state_mutated") is True),
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Attach the rollout smoke receipt to final commercial release evidence."
            if ready
            else f"Run the separate R4-approved rollout execution smoke and record one row in `{receipt_csv}`."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Product Rollout Execution Smoke Receipt",
        "",
        f"- status: `{s['status']}`",
        f"- rollout_execution_smoke_receipt_ready: `{s['rollout_execution_smoke_receipt_ready']}`",
        f"- receipt_csv_present: `{s['receipt_csv_present']}`",
        f"- receipt_row_count: `{s['receipt_row_count']}`",
        f"- blocker_count: `{s['blocker_count']}`",
        f"- rollout_executed: `{s['rollout_executed']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        f"- pager_provider_contacted: `{s['pager_provider_contacted']}`",
        f"- ingress_certificate_verified_live: `{s['ingress_certificate_verified_live']}`",
        "",
        "## Rows",
        "",
        "| receipt_status | target_environment | blockers |",
        "| --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['receipt_status']}` | `{row['target_environment']}` | `{row['blockers']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build product rollout execution smoke receipt.")
    parser.add_argument("--readiness-json", default=DEFAULT_READINESS_JSON)
    parser.add_argument("--receipt-csv", default=DEFAULT_RECEIPT_CSV)
    parser.add_argument("--template-csv", default=DEFAULT_TEMPLATE_CSV)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    args = parser.parse_args(argv)
    rows, missing_columns = _read_csv_rows(args.receipt_csv)
    receipt_csv_present = _resolve(args.receipt_csv).exists()
    payload = build_product_rollout_execution_smoke_receipt(
        readiness_packet=_read_json_if_present(args.readiness_json),
        receipt_rows=rows,
        receipt_csv_present=receipt_csv_present,
        receipt_csv=args.receipt_csv,
        template_csv=args.template_csv,
        missing_columns=missing_columns,
    )
    _write_template(args.template_csv)
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
