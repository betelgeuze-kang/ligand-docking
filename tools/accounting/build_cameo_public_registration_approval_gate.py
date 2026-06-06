#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from tools.builder_table_utils import write_csv_rows
from tools.build_cameo_capability_preflight import DEFAULT_OUT_JSON as DEFAULT_CAPABILITY_JSON
from tools.build_cameo_validation_operations_dossier import DEFAULT_OUT_JSON as DEFAULT_OPERATIONS_DOSSIER_JSON

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OPERATOR_APPROVAL_CSV = "runs/cameo_public_registration_operator_approval_intake.csv"
DEFAULT_TEMPLATE_CSV = "runs/cameo_public_registration_operator_approval_template_current.csv"
DEFAULT_OUT_JSON = "runs/cameo_public_registration_approval_gate_current.json"
DEFAULT_OUT_CSV = "runs/cameo_public_registration_approval_gate_current.csv"
DEFAULT_OUT_MD = "runs/cameo_public_registration_approval_gate_current.md"

REGISTRATION_APPROVAL_TOKEN = "APPROVE_CAMEO_SERVER_REGISTRATION"
OUTBOUND_EMAIL_APPROVAL_TOKEN = "APPROVE_CAMEO_OUTBOUND_EMAIL"
APPROVE_DECISION = "approve"
SKIP_DECISION = "skip"
VALID_DECISIONS = {APPROVE_DECISION, SKIP_DECISION}

CLAIM_BOUNDARY = (
    "CAMEO public registration approval gate only; it validates operator registration/email approval intake and required "
    "public endpoint metadata. It does not register a CAMEO server, submit predictions, send email, start a server, run "
    "prediction generation, install packages, or mutate external state."
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


def _read_csv_rows(path_like: str | Path) -> list[dict[str, str]]:
    path = _resolve(path_like)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


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


def _valid_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"https", "http"} and bool(parsed.netloc)


def _valid_email(value: str) -> bool:
    return "@" in value and "." in value.rsplit("@", 1)[-1]


def _write_template(path_like: str | Path, target_id: str = "") -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "target_id",
        "operator_decision",
        "registration_approval_token",
        "outbound_email_approval_token",
        "public_endpoint_url",
        "results_email",
        "contact_email",
        "operator_note",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerow(
            {
                "target_id": target_id,
                "operator_decision": "",
                "registration_approval_token": "",
                "outbound_email_approval_token": "",
                "public_endpoint_url": "",
                "results_email": "",
                "contact_email": "",
                "operator_note": "",
            }
        )


def build_cameo_public_registration_approval_gate(
    *,
    capability_packet: dict[str, Any],
    operations_dossier_packet: dict[str, Any],
    operator_approval_rows: list[dict[str, Any]],
    capability_json: str = DEFAULT_CAPABILITY_JSON,
    operations_dossier_json: str = DEFAULT_OPERATIONS_DOSSIER_JSON,
    operator_approval_csv: str = DEFAULT_OPERATOR_APPROVAL_CSV,
    template_csv: str = DEFAULT_TEMPLATE_CSV,
    operator_approval_csv_present: bool = True,
) -> dict[str, Any]:
    capability = _summary(capability_packet)
    operations = _summary(operations_dossier_packet)
    blockers: list[str] = []
    capability_ready = (
        _text(capability.get("status")) == "cameo_public_registration_preflight_ready"
        and bool(capability.get("public_registration_allowed") is True)
    )
    validation_ready = bool(operations.get("validation_ready") is True) and bool(operations.get("official_cameo_results_used") is True)
    receiver_ready = _text(operations.get("receiver_smoke_status")) == "cameo_receiver_smoke_ready"
    if not capability_ready:
        blockers.append("cameo_capability_public_registration_not_ready")
    if not validation_ready:
        blockers.append("official_cameo_validation_evidence_not_ready")
    if not receiver_ready:
        blockers.append("cameo_receiver_smoke_not_ready")
    if not operator_approval_csv_present:
        blockers.append("operator_approval_csv_missing")
    if len(operator_approval_rows) > 1:
        blockers.append("duplicate_operator_approval_rows")

    row_input = operator_approval_rows[0] if operator_approval_rows else {}
    decision = _text(row_input.get("operator_decision")).lower()
    registration_token = _text(row_input.get("registration_approval_token"))
    outbound_email_token = _text(row_input.get("outbound_email_approval_token"))
    endpoint_url = _text(row_input.get("public_endpoint_url"))
    results_email = _text(row_input.get("results_email"))
    contact_email = _text(row_input.get("contact_email"))
    target_id = _text(row_input.get("target_id") or operations.get("target_id") or capability.get("target_id"))
    row_blockers: list[str] = []

    if not row_input:
        gate_status = "awaiting_operator_approval"
        row_blockers.append("operator_decision_missing")
    elif decision not in VALID_DECISIONS:
        gate_status = "blocked_before_registration"
        row_blockers.append("operator_decision_invalid")
    elif decision == SKIP_DECISION:
        gate_status = "skipped_by_operator"
    else:
        gate_status = "approved_for_separate_registration_review"
        if registration_token != REGISTRATION_APPROVAL_TOKEN:
            row_blockers.append("registration_approval_token_mismatch")
        if outbound_email_token != OUTBOUND_EMAIL_APPROVAL_TOKEN:
            row_blockers.append("outbound_email_approval_token_mismatch")
        if not _valid_url(endpoint_url):
            row_blockers.append("public_endpoint_url_invalid")
        if not _valid_email(results_email):
            row_blockers.append("results_email_invalid")
        if not _valid_email(contact_email):
            row_blockers.append("contact_email_invalid")
        if row_blockers:
            gate_status = "blocked_before_registration"
    blockers.extend(row_blockers)

    row = {
        "target_id": target_id,
        "approval_gate_status": gate_status,
        "operator_decision": decision,
        "registration_approval_token_required": REGISTRATION_APPROVAL_TOKEN,
        "registration_approval_token_present": bool(registration_token),
        "outbound_email_approval_token_required": OUTBOUND_EMAIL_APPROVAL_TOKEN,
        "outbound_email_approval_token_present": bool(outbound_email_token),
        "public_endpoint_url_present": bool(endpoint_url),
        "results_email_present": bool(results_email),
        "contact_email_present": bool(contact_email),
        "blockers": ",".join(row_blockers),
        "server_registration_mutated": False,
        "outbound_email_enabled": False,
        "prediction_generation_enabled": False,
        "external_state_mutated": False,
    }
    authorized = gate_status == "approved_for_separate_registration_review" and not blockers
    skipped = gate_status == "skipped_by_operator" and not row_blockers
    status = "cameo_public_registration_approval_gate_ready" if authorized else "blocked_cameo_public_registration_approval_gate"
    summary = {
        "packet_type": "cameo_public_registration_approval_gate",
        "status": status,
        "source_capability_json": capability_json,
        "source_capability_status": _text(capability.get("status")),
        "source_operations_dossier_json": operations_dossier_json,
        "source_operations_dossier_status": _text(operations.get("status")),
        "operator_approval_csv": operator_approval_csv,
        "operator_approval_csv_present": bool(operator_approval_csv_present),
        "operator_template_csv": template_csv,
        "target_id": target_id,
        "capability_public_registration_ready": capability_ready,
        "official_cameo_validation_evidence_ready": validation_ready,
        "receiver_smoke_ready": receiver_ready,
        "authorized_for_registration_review": bool(authorized),
        "authorized_row_count": 1 if authorized else 0,
        "awaiting_operator_approval_row_count": 1 if gate_status == "awaiting_operator_approval" else 0,
        "skipped_row_count": 1 if skipped else 0,
        "blocked_row_count": 1 if blockers else 0,
        "blocker_count": len(blockers),
        "blockers": sorted(set(blockers)),
        "registration_approval_token_required": REGISTRATION_APPROVAL_TOKEN,
        "outbound_email_approval_token_required": OUTBOUND_EMAIL_APPROVAL_TOKEN,
        "server_registration_mutated": False,
        "outbound_email_enabled": False,
        "prediction_generation_enabled": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Use the approved metadata only in the separate operator-run public CAMEO registration process."
            if authorized
            else f"Fill `{template_csv}` into `{operator_approval_csv}` after receiver smoke, official CAMEO evidence, and capability preflight are ready."
        ),
    }
    return {"summary": summary, "rows": [row]}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# CAMEO Public Registration Approval Gate",
        "",
        f"- status: `{s['status']}`",
        f"- capability_public_registration_ready: `{s['capability_public_registration_ready']}`",
        f"- official_cameo_validation_evidence_ready: `{s['official_cameo_validation_evidence_ready']}`",
        f"- receiver_smoke_ready: `{s['receiver_smoke_ready']}`",
        f"- operator_approval_csv_present: `{s['operator_approval_csv_present']}`",
        f"- authorized_for_registration_review: `{s['authorized_for_registration_review']}`",
        f"- authorized_row_count: `{s['authorized_row_count']}`",
        f"- awaiting_operator_approval_row_count: `{s['awaiting_operator_approval_row_count']}`",
        f"- blocked_row_count: `{s['blocked_row_count']}`",
        f"- server_registration_mutated: `{s['server_registration_mutated']}`",
        f"- outbound_email_enabled: `{s['outbound_email_enabled']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Rows",
        "",
        "| gate_status | decision | endpoint | results_email | contact_email | blockers |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['approval_gate_status']}` | `{row['operator_decision']}` | `{row['public_endpoint_url_present']}` | "
            f"`{row['results_email_present']}` | `{row['contact_email_present']}` | `{row['blockers']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate CAMEO public registration approval intake without registering or sending email.")
    parser.add_argument("--capability-json", default=DEFAULT_CAPABILITY_JSON)
    parser.add_argument("--operations-dossier-json", default=DEFAULT_OPERATIONS_DOSSIER_JSON)
    parser.add_argument("--operator-approval-csv", default=DEFAULT_OPERATOR_APPROVAL_CSV)
    parser.add_argument("--template-csv", default=DEFAULT_TEMPLATE_CSV)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    operations = _read_json_if_present(args.operations_dossier_json)
    operator_path = _resolve(args.operator_approval_csv)
    payload = build_cameo_public_registration_approval_gate(
        capability_packet=_read_json_if_present(args.capability_json),
        operations_dossier_packet=operations,
        operator_approval_rows=_read_csv_rows(args.operator_approval_csv),
        capability_json=args.capability_json,
        operations_dossier_json=args.operations_dossier_json,
        operator_approval_csv=args.operator_approval_csv,
        template_csv=args.template_csv,
        operator_approval_csv_present=operator_path.exists(),
    )
    _write_template(args.template_csv, _text(_summary(operations).get("target_id")))
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
