#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_WORKBENCH_JSON = "runs/idp_page4_manual_confirmation_workbench_current.json"
DEFAULT_OUT_JSON = "runs/idp_page4_manual_confirmation_note_templates_current.json"
DEFAULT_OUT_CSV = "runs/idp_page4_manual_confirmation_note_templates_current.csv"
DEFAULT_OUT_MD = "runs/idp_page4_manual_confirmation_note_templates_current.md"


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


def _build_template(row: dict[str, Any]) -> str:
    item = str(row.get("confirmation_item", "")).strip()
    source_anchor = str(row.get("source_anchor", "")).strip() or "anchor pending"
    decision = str(row.get("suggested_manual_confirmation_decision", "")).strip() or "accept_with_guardrails"
    guardrail_focus = str(row.get("guardrail_focus", "")).strip() or "keep the state mapping explicit"
    reopen_effect = (str(row.get("reopen_effect_if_accepted", "")).strip().rstrip(".") or "supports the page4 candidate review")
    return (
        f"Suggested confirmation note for `{item}`: `{decision}` under the explicit guardrail that {guardrail_focus}. "
        f"Anchor `{source_anchor}` is the citation basis. If accepted, this {reopen_effect}."
    )


def build_payload(workbench_payload: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for row in workbench_payload.get("rows", []) or []:
        template = _build_template(row)
        rows.append(
            {
                "confirmation_item": str(row.get("confirmation_item", "")).strip(),
                "source_anchor": str(row.get("source_anchor", "")).strip(),
                "suggested_manual_confirmation_decision": str(row.get("suggested_manual_confirmation_decision", "")).strip(),
                "manual_confirmation_note_template": template,
                "template_ready": bool(template),
            }
        )
    summary = {
        "status": "page4_manual_confirmation_note_templates_ready",
        "target_name": "page4",
        "template_row_count": len(rows),
        "template_ready_count": sum(1 for row in rows if row["template_ready"]),
        "next_required_step": "Use these note templates as reviewer-facing starting points only; keep manual confirmation explicit in the confirmation sheet.",
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# IDP Page4 Manual Confirmation Note Templates",
        "",
        f"- status: `{s['status']}`",
        f"- target_name: `{s['target_name']}`",
        f"- template_row_count: `{s['template_row_count']}`",
        f"- template_ready_count: `{s['template_ready_count']}`",
        "",
        "## Templates",
        "",
        "| confirmation_item | source_anchor | suggested_manual_confirmation_decision | template_ready |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['confirmation_item']}` | `{row['source_anchor']}` | `{row['suggested_manual_confirmation_decision']}` | `{row['template_ready']}` |"
        )
        lines.append("")
        lines.append(f"- Template: {row['manual_confirmation_note_template']}")
        lines.append("")
    lines.extend(["## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build page4 manual confirmation note templates.")
    parser.add_argument("--workbench-json", default=DEFAULT_WORKBENCH_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(_load_json(args.workbench_json))
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv_rows(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
