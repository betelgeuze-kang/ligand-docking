#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from betelgeuze_cameo.outbound_email_send_preflight import build_outbound_email_send_preflight
from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DRAFT_JSON = "runs/cameo_outbound_email_draft_current.json"
DEFAULT_REGISTRATION_APPROVAL_JSON = "runs/cameo_public_registration_approval_gate_current.json"
DEFAULT_OPERATOR_SEND_CSV = "runs/cameo_outbound_email_send_operator_approval_intake.csv"
DEFAULT_TEMPLATE_CSV = "runs/cameo_outbound_email_send_operator_approval_template_current.csv"
DEFAULT_OUT_JSON = "runs/cameo_outbound_email_send_preflight_current.json"
DEFAULT_OUT_CSV = "runs/cameo_outbound_email_send_preflight_current.csv"
DEFAULT_OUT_MD = "runs/cameo_outbound_email_send_preflight_current.md"


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


def _write_template(path_like: str | Path, target_id: str = "", sender_email: str = "", recipient_email: str = "") -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "target_id",
        "operator_decision",
        "outbound_email_approval_token",
        "smtp_profile_id",
        "smtp_host",
        "smtp_port",
        "envelope_sender",
        "envelope_recipient",
        "operator_note",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerow(
            {
                "target_id": target_id,
                "operator_decision": "",
                "outbound_email_approval_token": "",
                "smtp_profile_id": "",
                "smtp_host": "",
                "smtp_port": "",
                "envelope_sender": sender_email,
                "envelope_recipient": recipient_email,
                "operator_note": "",
            }
        )


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# CAMEO Outbound Email Send Preflight",
        "",
        f"- status: `{s['status']}`",
        f"- draft_ready: `{s['draft_ready']}`",
        f"- draft_eml_present: `{s['draft_eml_present']}`",
        f"- registration_email_approval_ready: `{s['registration_email_approval_ready']}`",
        f"- operator_send_csv_present: `{s['operator_send_csv_present']}`",
        f"- authorized_for_separate_operator_send: `{s['authorized_for_separate_operator_send']}`",
        f"- blocker_count: `{s['blocker_count']}`",
        f"- blockers: `{';'.join(s['blockers'])}`",
        f"- smtp_connection_opened: `{s['smtp_connection_opened']}`",
        f"- email_sent: `{s['email_sent']}`",
        f"- outbound_email_enabled: `{s['outbound_email_enabled']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Rows",
        "",
        "| gate_status | decision | smtp_profile | smtp_host | smtp_port | sender | recipient | blockers |",
        "| --- | --- | --- | --- | ---: | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['send_preflight_status']}` | `{row['operator_decision']}` | `{row['smtp_profile_id_present']}` | "
            f"`{row['smtp_host_present']}` | `{row['smtp_port']}` | `{row['envelope_sender_present']}` | "
            f"`{row['envelope_recipient_present']}` | `{row['blockers']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate CAMEO outbound email send readiness without SMTP connection or send.")
    parser.add_argument("--draft-json", default=DEFAULT_DRAFT_JSON)
    parser.add_argument("--registration-approval-json", default=DEFAULT_REGISTRATION_APPROVAL_JSON)
    parser.add_argument("--operator-send-csv", default=DEFAULT_OPERATOR_SEND_CSV)
    parser.add_argument("--template-csv", default=DEFAULT_TEMPLATE_CSV)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    draft = _read_json_if_present(args.draft_json)
    draft_summary = _summary(draft)
    operator_path = _resolve(args.operator_send_csv)
    payload = build_outbound_email_send_preflight(
        draft_packet=draft,
        registration_approval_packet=_read_json_if_present(args.registration_approval_json),
        operator_send_rows=_read_csv_rows(args.operator_send_csv),
        operator_send_csv_present=operator_path.exists(),
        root=ROOT,
        operator_send_csv=args.operator_send_csv,
        template_csv=args.template_csv,
    )
    _write_template(
        args.template_csv,
        target_id=_text(draft_summary.get("target_id")),
        sender_email=_text(draft_summary.get("sender_email")),
        recipient_email=_text(draft_summary.get("recipient_email")),
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
