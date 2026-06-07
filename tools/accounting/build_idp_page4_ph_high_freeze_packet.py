#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_PH_HIGH_FILL_JSON = "runs/idp_page4_ph_high_fill_value_packet_current.json"
DEFAULT_OUT_JSON = "runs/idp_page4_ph_high_freeze_packet_current.json"
DEFAULT_OUT_CSV = "runs/idp_page4_ph_high_freeze_packet_current.csv"
DEFAULT_OUT_MD = "runs/idp_page4_ph_high_freeze_packet_current.md"


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _load_json(path_like: str) -> dict[str, Any]:
    with _resolve(path_like).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def build_payload(ph_high_fill_payload: dict[str, Any]) -> dict[str, Any]:
    fill_s = dict((ph_high_fill_payload.get("summary") if isinstance(ph_high_fill_payload.get("summary"), dict) else {}) or {})
    fill_rows = [dict(row) for row in ph_high_fill_payload.get("rows", []) or []]
    rows = [
        {
            "fill_field": str(row.get("fill_field", "")).strip(),
            "source_anchor": str(row.get("source_anchor", "")).strip(),
            "freeze_decision": "draft_ready_review_only",
            "freeze_guardrail": str(row.get("guardrail", "")).strip(),
            "next_action": "Freeze only after expanded-state mapping stays explicit and the signal is not recast as true aggregation-positive.",
        }
        for row in fill_rows
    ]
    summary = {
        "status": "page4_ph_high_freeze_packet_ready",
        "target_name": "page4",
        "condition_name": str(fill_s.get("condition_name", "ph_high")).strip(),
        "source_anchor": str(fill_s.get("source_anchor", "PMID 28289210")).strip(),
        "freeze_row_count": len(rows),
        "freeze_ready": True,
        "promotion_ready": False,
        "next_required_step": "Use this packet as the ph_high freeze decision surface, then combine it with the ph_low freeze packet before any anchor-backed candidate decision.",
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# IDP Page4 ph_high Freeze Packet",
        "",
        f"- status: `{s['status']}`",
        f"- target_name: `{s['target_name']}`",
        f"- condition_name: `{s['condition_name']}`",
        f"- source_anchor: `{s['source_anchor']}`",
        f"- freeze_row_count: `{s['freeze_row_count']}`",
        f"- freeze_ready: `{s['freeze_ready']}`",
        f"- promotion_ready: `{s['promotion_ready']}`",
        "",
        "## Freeze Rows",
        "",
        "| fill_field | source_anchor | freeze_decision | freeze_guardrail | next_action |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['fill_field']}` | `{row['source_anchor']}` | `{row['freeze_decision']}` | `{row['freeze_guardrail']}` | {row['next_action']} |"
        )
    lines.extend(["", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a ph_high freeze packet for page4.")
    parser.add_argument("--ph-high-fill-json", default=DEFAULT_PH_HIGH_FILL_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(_load_json(args.ph_high_fill_json))
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv_rows(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
