#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_BINDER_SHEET_JSON = "runs/glut1_binder_verdict_update_sheet_current.json"
DEFAULT_OUT_JSON = "runs/glut1_manual_verdict_apply_draft_current.json"
DEFAULT_OUT_CSV = "runs/glut1_manual_verdict_apply_draft_current.csv"
DEFAULT_OUT_MD = "runs/glut1_manual_verdict_apply_draft_current.md"


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


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _build_draft_row(row: dict[str, Any]) -> dict[str, Any]:
    manual_verdict = str(row.get("manual_verdict_update", "")).strip()
    manual_conf = str(row.get("manual_confidence_update", "")).strip()
    manual_note = str(row.get("manual_decision_note", "")).strip()
    has_authoritative = any((manual_verdict, manual_conf, manual_note))
    return {
        "priority_rank": str(row.get("priority_rank", "")).strip(),
        "target_id": str(row.get("target_id", "")).strip() or "GLUT1",
        "packet_step": str(row.get("packet_step", "")).strip(),
        "candidate_name": str(row.get("candidate_name", "")).strip(),
        "source_anchor": str(row.get("source_anchor", "")).strip(),
        "source_url": str(row.get("source_url", "")).strip(),
        "current_recommended_verdict": str(row.get("current_recommended_verdict", "")).strip(),
        "suggested_manual_verdict": str(row.get("suggested_manual_verdict", "")).strip(),
        "suggested_manual_confidence_update": str(row.get("suggested_manual_confidence_update", "")).strip(),
        "suggested_manual_decision_note": str(row.get("suggested_manual_decision_note", "")).strip(),
        "draft_manual_verdict_update": str(row.get("suggested_manual_verdict", "")).strip(),
        "draft_manual_confidence_update": str(row.get("suggested_manual_confidence_update", "")).strip(),
        "draft_manual_decision_note": str(row.get("suggested_manual_decision_note", "")).strip(),
        "authoritative_manual_verdict_update": manual_verdict,
        "authoritative_manual_confidence_update": manual_conf,
        "authoritative_manual_decision_note": manual_note,
        "authoritative_manual_fields_touched": "yes" if has_authoritative else "no",
        "draft_update_status": (
            "needs_manual_review"
            if not has_authoritative
            else "authoritative_manual_input_present"
        ),
        "next_required_action": str(row.get("next_required_action", "")).strip(),
        "promotion_blocker": str(row.get("promotion_blocker", "")).strip(),
    }


def build_payload(binder_sheet_payload: dict[str, Any]) -> dict[str, Any]:
    rows = [_build_draft_row(row) for row in binder_sheet_payload.get("sheet_rows", []) or []]
    summary = {
        "target_id": "GLUT1",
        "binder_slot_count": len(rows),
        "draft_prefilled_count": sum(1 for row in rows if row["draft_manual_verdict_update"]),
        "pending_reviewer_action_count": sum(1 for row in rows if row["draft_update_status"] == "needs_manual_review"),
        "authoritative_manual_fields_touched_count": sum(
            1 for row in rows if row["authoritative_manual_fields_touched"] == "yes"
        ),
        "next_required_step": (
            "Use this GLUT1-only draft packet as a reviewer-side staging artifact. "
            "Do not copy draft_manual_* values into authoritative manual_* fields without explicit reviewer confirmation."
        ),
    }
    return {"summary": summary, "draft_rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# GLUT1 Manual Verdict Apply Draft",
        "",
        f"- target_id: `{s['target_id']}`",
        f"- binder_slot_count: `{s['binder_slot_count']}`",
        f"- draft_prefilled_count: `{s['draft_prefilled_count']}`",
        f"- pending_reviewer_action_count: `{s['pending_reviewer_action_count']}`",
        f"- authoritative_manual_fields_touched_count: `{s['authoritative_manual_fields_touched_count']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Draft Rows",
        "",
        "| priority_rank | packet_step | candidate_name | draft_manual_verdict_update | draft_manual_confidence_update | authoritative_manual_fields_touched | draft_update_status |",
        "| ---: | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["draft_rows"]:
        lines.append(
            f"| {row['priority_rank']} | `{row['packet_step']}` | `{row['candidate_name']}` | "
            f"`{row['draft_manual_verdict_update']}` | `{row['draft_manual_confidence_update']}` | "
            f"`{row['authoritative_manual_fields_touched']}` | `{row['draft_update_status']}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a GLUT1-only manual-verdict draft packet from the current binder verdict update sheet.")
    parser.add_argument("--binder-sheet-json", default=DEFAULT_BINDER_SHEET_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(_load_json(args.binder_sheet_json))
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(out_csv, payload["draft_rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
