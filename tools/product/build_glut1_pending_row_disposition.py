#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WORKBOOK_CSV = "runs/glut1_packet_replacement_workbook_current.csv"
DEFAULT_OUT_JSON = "runs/glut1_pending_row_disposition_current.json"
DEFAULT_OUT_CSV = "runs/glut1_pending_row_disposition_current.csv"
DEFAULT_OUT_MD = "runs/glut1_pending_row_disposition_current.md"


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _classify(row: dict[str, str]) -> dict[str, str]:
    is_binder = str(row.get("replacement_is_binder", "")).strip() == "1"
    if is_binder:
        return {
            "disposition": "defer_pending_target_specific_evidence",
            "promotion_blocker": "no_local_target_activity_curated",
            "next_required_action": "manual_curated_search_or_defer",
            "notes": "GLUT1 binder rows remain deferred until transporter-specific target evidence is curated.",
        }
    return {
        "disposition": "review_only_negative_evidence",
        "promotion_blocker": "no_quantitative_transporter_negative_evidence_curated",
        "next_required_action": "manual_negative_evidence_review",
        "notes": "GLUT1 negative-like rows stay review-only; do not inject proxy non-binder values.",
    }


def build_payload(rows: list[dict[str, str]]) -> dict[str, Any]:
    disposition_rows: list[dict[str, Any]] = []
    for idx, row in enumerate(rows, start=1):
        classified = _classify(row)
        disposition_rows.append(
            {
                "priority_rank": idx,
                "packet_step": str(row.get("packet_step", "")).strip(),
                "replacement_ligand_id": str(row.get("replacement_ligand_id", "")).strip(),
                "replacement_is_binder": str(row.get("replacement_is_binder", "")).strip(),
                "required_missing_fields": str(row.get("required_missing_fields", "")).strip(),
                **classified,
            }
        )
    review_only_rows = sum(1 for row in disposition_rows if row["disposition"] == "review_only_negative_evidence")
    defer_rows = sum(1 for row in disposition_rows if row["disposition"] == "defer_pending_target_specific_evidence")
    return {
        "summary": {
            "family": "glut1",
            "total_rows": len(rows),
            "verified_rows": 0,
            "pending_rows": len(disposition_rows),
            "review_only_rows": review_only_rows,
            "defer_rows": defer_rows,
            "pending_binder_rows": defer_rows,
            "next_required_step": "Keep all GLUT1 rows draft-only. Defer binder slots until target-specific evidence exists, and keep non-binder slots review-only until quantitative transporter negative evidence is curated.",
        },
        "rows": disposition_rows,
    }


def _write_md(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# GLUT1 Pending Row Disposition",
        "",
        f"- total_rows: `{s['total_rows']}`",
        f"- verified_rows: `{s['verified_rows']}`",
        f"- pending_rows: `{s['pending_rows']}`",
        f"- review_only_rows: `{s['review_only_rows']}`",
        f"- defer_rows: `{s['defer_rows']}`",
        f"- pending_binder_rows: `{s['pending_binder_rows']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Rows",
        "",
        "| priority_rank | packet_step | disposition | promotion_blocker | next_required_action |",
        "| ---: | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['priority_rank']} | {row['packet_step']} | `{row['disposition']}` | `{row['promotion_blocker']}` | `{row['next_required_action']}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build pending-row disposition for GLUT1 transporter scaffold rows.")
    p.add_argument("--workbook-csv", default=DEFAULT_WORKBOOK_CSV)
    p.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    p.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    p.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    rows = _read_csv(_resolve(args.workbook_csv))
    payload = build_payload(rows)
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(out_csv, payload["rows"])
    _write_md(out_md, payload)


if __name__ == "__main__":
    main()
