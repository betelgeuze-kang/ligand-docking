#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from betelgeuze_cameo.handoff import build_dry_run_handoff_packet
from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SELECTION_JSON = "runs/cameo_model1_selection_packet_current.json"
DEFAULT_FORMAT_JSON = "runs/cameo_format_validation_packet_current.json"
DEFAULT_OUT_JSON = "runs/cameo_dry_run_handoff_packet_current.json"
DEFAULT_OUT_CSV = "runs/cameo_dry_run_handoff_packet_current.csv"
DEFAULT_OUT_MD = "runs/cameo_dry_run_handoff_packet_current.md"


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
        "# CAMEO Dry-Run Handoff Packet",
        "",
        f"- status: `{s['status']}`",
        f"- target_id: `{s['target_id']}`",
        f"- attachment_count: `{s['attachment_count']}`",
        f"- model1_attachment_count: `{s['model1_attachment_count']}`",
        f"- outbound_email_enabled: `{s['outbound_email_enabled']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        f"- email_approval_token_required: `{s['email_approval_token_required']}`",
        "",
        "## Attachments",
        "",
        "| rank | candidate | filename | format | atoms | models | path |",
        "| ---: | --- | --- | --- | ---: | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['cameo_model_rank']} | `{row['candidate_id']}` | `{row['attachment_filename']}` | "
            f"`{row['detected_format']}` | {row['atom_count']} | {row['model_count']} | `{row['model_path']}` |"
        )
    lines.extend(["", "## Blockers", ""])
    blockers = s.get("blockers") or []
    if blockers:
        lines.extend(f"- `{blocker['code']}`: {blocker['reason']}" for blocker in blockers)
    else:
        lines.append("- none")
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a CAMEO dry-run handoff packet from selection and format-validation packets.")
    parser.add_argument("--selection-json", default=DEFAULT_SELECTION_JSON)
    parser.add_argument("--format-json", default=DEFAULT_FORMAT_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_dry_run_handoff_packet(_read_json(args.selection_json), _read_json(args.format_json))
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
