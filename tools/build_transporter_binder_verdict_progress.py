#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AQP1_SHEET_JSON = "runs/aqp1_binder_verdict_update_sheet_current.json"
DEFAULT_GLUT1_SHEET_JSON = "runs/glut1_binder_verdict_update_sheet_current.json"
DEFAULT_OUT_JSON = "runs/transporter_binder_verdict_progress_current.json"
DEFAULT_OUT_CSV = "runs/transporter_binder_verdict_progress_current.csv"
DEFAULT_OUT_MD = "runs/transporter_binder_verdict_progress_current.md"


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


def _family_row(family: str, payload: dict[str, Any]) -> dict[str, Any]:
    summary = dict(payload.get("summary", {}) or {})
    return {
        "family": family,
        "binder_slot_count": summary.get("binder_slot_count", 0),
        "suggested_prefill_count": summary.get("suggested_prefill_count", 0),
        "pending_manual_verdict_count": summary.get("pending_manual_verdict_count", 0),
        "completed_manual_verdict_count": summary.get("completed_manual_verdict_count", 0),
    }


def build_payload(aqp1_sheet: dict[str, Any], glut1_sheet: dict[str, Any]) -> dict[str, Any]:
    rows = [
        _family_row("aqp1", aqp1_sheet),
        _family_row("glut1", glut1_sheet),
    ]
    pending_total = sum(int(row["pending_manual_verdict_count"]) for row in rows)
    summary = {
        "family_count": len(rows),
        "binder_slot_count": sum(int(row["binder_slot_count"]) for row in rows),
        "suggested_prefill_count": sum(int(row["suggested_prefill_count"]) for row in rows),
        "pending_manual_verdict_count": pending_total,
        "completed_manual_verdict_count": sum(int(row["completed_manual_verdict_count"]) for row in rows),
        "next_required_step": (
            "Burn down AQP1 binder verdict updates first, then move to GLUT1 once AQP1 first-wave review has explicit manual verdicts."
            if pending_total > 0
            else "Manual verdict backlog is cleared. Use AQP1 binder rows first for transporter seed-row promotion and keep GLUT1 as second-wave follow-up."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# Transporter Binder Verdict Progress",
        "",
        f"- family_count: `{summary['family_count']}`",
        f"- binder_slot_count: `{summary['binder_slot_count']}`",
        f"- suggested_prefill_count: `{summary['suggested_prefill_count']}`",
        f"- pending_manual_verdict_count: `{summary['pending_manual_verdict_count']}`",
        f"- completed_manual_verdict_count: `{summary['completed_manual_verdict_count']}`",
        "",
        "## Next Step",
        "",
        f"- {summary['next_required_step']}",
        "",
        "## Families",
        "",
        "| family | binder_slot_count | suggested_prefill_count | pending_manual_verdict_count | completed_manual_verdict_count |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['family']}` | {row['binder_slot_count']} | {row['suggested_prefill_count']} | {row['pending_manual_verdict_count']} | {row['completed_manual_verdict_count']} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build progress summary for transporter binder verdict update sheets.")
    parser.add_argument("--aqp1-sheet-json", default=DEFAULT_AQP1_SHEET_JSON)
    parser.add_argument("--glut1-sheet-json", default=DEFAULT_GLUT1_SHEET_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.aqp1_sheet_json),
        _load_json(args.glut1_sheet_json),
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
