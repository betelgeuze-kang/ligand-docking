#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from betelgeuze_cameo.outbound_email_draft import build_outbound_email_draft
from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_HANDOFF_JSON = "runs/cameo_dry_run_handoff_packet_current.json"
DEFAULT_DRAFT_EML = "runs/cameo_outbound_email_draft_current.eml"
DEFAULT_OUT_JSON = "runs/cameo_outbound_email_draft_current.json"
DEFAULT_OUT_CSV = "runs/cameo_outbound_email_draft_current.csv"
DEFAULT_OUT_MD = "runs/cameo_outbound_email_draft_current.md"


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# CAMEO Outbound Email Draft",
        "",
        f"- status: `{s['status']}`",
        f"- target_id: `{s['target_id']}`",
        f"- recipient_email: `{s['recipient_email']}`",
        f"- sender_email: `{s['sender_email']}`",
        f"- draft_eml_path: `{s['draft_eml_path']}`",
        f"- draft_eml_written: `{s['draft_eml_written']}`",
        f"- draft_eml_size_bytes: `{s['draft_eml_size_bytes']}`",
        f"- attachment_count: `{s['attachment_count']}`",
        f"- outbound_email_enabled: `{s['outbound_email_enabled']}`",
        f"- email_sent: `{s['email_sent']}`",
        f"- smtp_connection_opened: `{s['smtp_connection_opened']}`",
        f"- approval_token_required_for_future_send: `{s['approval_token_required_for_future_send']}`",
        "",
        "## Attachments",
        "",
        "| rank | candidate | filename | present | size | path |",
        "| ---: | --- | --- | --- | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['cameo_model_rank']} | `{row['candidate_id']}` | `{row['attachment_filename']}` | "
            f"`{row['source_file_present']}` | {row['source_size_bytes']} | `{row['model_path']}` |"
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
    parser = argparse.ArgumentParser(description="Build a local CAMEO outbound email .eml draft without sending email.")
    parser.add_argument("--handoff-json", default=DEFAULT_HANDOFF_JSON)
    parser.add_argument("--recipient-email", default="results@example.invalid")
    parser.add_argument("--sender-email", default="operator@example.invalid")
    parser.add_argument("--subject-prefix", default="CAMEO prediction dry-run")
    parser.add_argument("--draft-eml", default=DEFAULT_DRAFT_EML)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_outbound_email_draft(
        handoff_packet=_read_json(args.handoff_json),
        recipient_email=args.recipient_email,
        sender_email=args.sender_email,
        draft_eml_path=args.draft_eml,
        root=ROOT,
        subject_prefix=args.subject_prefix,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
