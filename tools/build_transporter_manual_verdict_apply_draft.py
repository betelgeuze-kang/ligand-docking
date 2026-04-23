#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_AQP1_BINDER_SHEET_JSON = "runs/aqp1_binder_verdict_update_sheet_current.json"
DEFAULT_GLUT1_BINDER_SHEET_JSON = "runs/glut1_binder_verdict_update_sheet_current.json"
DEFAULT_OUT_JSON = "runs/transporter_manual_verdict_apply_draft_current.json"
DEFAULT_OUT_CSV = "runs/transporter_manual_verdict_apply_draft_current.csv"
DEFAULT_OUT_MD = "runs/transporter_manual_verdict_apply_draft_current.md"


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


def _collect_rows(target_id: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in payload.get("sheet_rows", []) or []:
        rows.append(
            {
                "target_id": target_id,
                "priority_rank": str(row.get("priority_rank", "")).strip(),
                "packet_step": str(row.get("packet_step", "")).strip(),
                "candidate_name": str(row.get("candidate_name", "")).strip(),
                "source_anchor": str(row.get("source_anchor", "")).strip(),
                "current_recommended_verdict": str(row.get("current_recommended_verdict", "")).strip(),
                "draft_manual_verdict_update": str(row.get("suggested_manual_verdict", "")).strip(),
                "draft_manual_confidence_update": str(row.get("suggested_manual_confidence_update", "")).strip(),
                "draft_manual_decision_note": str(row.get("suggested_manual_decision_note", "")).strip(),
                "draft_ready": "1" if str(row.get("suggested_manual_verdict", "")).strip() else "0",
                "manual_verdict_update": str(row.get("manual_verdict_update", "")).strip(),
                "manual_confidence_update": str(row.get("manual_confidence_update", "")).strip(),
                "manual_decision_note": str(row.get("manual_decision_note", "")).strip(),
                "update_status": str(row.get("update_status", "")).strip(),
            }
        )
    return rows


def build_payload(aqp1_sheet: dict[str, Any], glut1_sheet: dict[str, Any]) -> dict[str, Any]:
    rows = _collect_rows("AQP1", aqp1_sheet) + _collect_rows("GLUT1", glut1_sheet)
    summary = {
        "target_count": len({row["target_id"] for row in rows}),
        "row_count": len(rows),
        "draft_ready_count": sum(1 for row in rows if row["draft_ready"] == "1"),
        "manual_verdict_filled_count": sum(1 for row in rows if row["manual_verdict_update"]),
        "aqp1_draft_ready_count": sum(1 for row in rows if row["target_id"] == "AQP1" and row["draft_ready"] == "1"),
        "glut1_draft_ready_count": sum(1 for row in rows if row["target_id"] == "GLUT1" and row["draft_ready"] == "1"),
        "next_required_step": "Use the draft columns as reviewer starting points only. Keep manual_verdict_update explicit and leave authoritative transporter promotion blocked.",
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Transporter Manual Verdict Apply Draft",
        "",
        f"- target_count: `{s['target_count']}`",
        f"- row_count: `{s['row_count']}`",
        f"- draft_ready_count: `{s['draft_ready_count']}`",
        f"- manual_verdict_filled_count: `{s['manual_verdict_filled_count']}`",
        f"- aqp1_draft_ready_count: `{s['aqp1_draft_ready_count']}`",
        f"- glut1_draft_ready_count: `{s['glut1_draft_ready_count']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Draft Rows",
        "",
        "| target_id | priority_rank | packet_step | candidate_name | draft_manual_verdict_update | draft_manual_confidence_update | update_status |",
        "| --- | ---: | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['target_id']} | {row['priority_rank']} | `{row['packet_step']}` | `{row['candidate_name']}` | "
            f"`{row['draft_manual_verdict_update']}` | `{row['draft_manual_confidence_update']}` | `{row['update_status']}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build draft reviewer-applied verdict values for transporter binders without touching manual fields.")
    parser.add_argument("--aqp1-binder-sheet-json", default=DEFAULT_AQP1_BINDER_SHEET_JSON)
    parser.add_argument("--glut1-binder-sheet-json", default=DEFAULT_GLUT1_BINDER_SHEET_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.aqp1_binder_sheet_json),
        _load_json(args.glut1_binder_sheet_json),
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
