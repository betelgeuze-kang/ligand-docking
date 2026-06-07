#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_AQP1_VERDICT_JSON = "runs/aqp1_candidate_verdict_sheet_current.json"
DEFAULT_GLUT1_VERDICT_JSON = "runs/glut1_candidate_verdict_sheet_current.json"
DEFAULT_OUT_JSON = "runs/transporter_verdict_summary_current.json"
DEFAULT_OUT_CSV = "runs/transporter_verdict_summary_current.csv"
DEFAULT_OUT_MD = "runs/transporter_verdict_summary_current.md"


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


def _family_row(name: str, verdict_payload: dict[str, Any]) -> dict[str, Any]:
    summary = dict(verdict_payload.get("summary", {}) or {})
    return {
        "family": name,
        "candidate_count": summary.get("candidate_count", 0),
        "keep_review_only_count": summary.get("keep_review_only_count", 0),
        "caution_only_count": summary.get("caution_only_count", 0),
        "defer_count": summary.get("defer_count", 0),
        "next_required_step": summary.get("next_required_step", ""),
    }


def build_payload(aqp1_verdict: dict[str, Any], glut1_verdict: dict[str, Any]) -> dict[str, Any]:
    rows = [
        _family_row("aqp1", aqp1_verdict),
        _family_row("glut1", glut1_verdict),
    ]
    summary = {
        "family_count": len(rows),
        "candidate_count": sum(int(row["candidate_count"]) for row in rows),
        "keep_review_only_count": sum(int(row["keep_review_only_count"]) for row in rows),
        "caution_only_count": sum(int(row["caution_only_count"]) for row in rows),
        "defer_count": sum(int(row["defer_count"]) for row in rows),
        "policy_status": "reviewer_state_only_blocker_closure",
        "next_required_step": (
            "Keep transporter candidates in reviewer-state only. Advance AQP1 first-wave blocker closure first, keep GLUT1 as second-wave, "
            "and do not promote any transporter packet row to authoritative apply from verdict counts alone."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# Transporter Verdict Summary",
        "",
        f"- family_count: `{summary['family_count']}`",
        f"- candidate_count: `{summary['candidate_count']}`",
        f"- keep_review_only_count: `{summary['keep_review_only_count']}`",
        f"- caution_only_count: `{summary['caution_only_count']}`",
        f"- defer_count: `{summary['defer_count']}`",
        f"- policy_status: `{summary['policy_status']}`",
        "",
        "## Next Step",
        "",
        f"- {summary['next_required_step']}",
        "",
        "## Families",
        "",
        "| family | candidate_count | keep_review_only_count | caution_only_count | defer_count |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['family']}` | {row['candidate_count']} | {row['keep_review_only_count']} | {row['caution_only_count']} | {row['defer_count']} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a compact transporter verdict summary from AQP1 and GLUT1 verdict sheets.")
    parser.add_argument("--aqp1-verdict-json", default=DEFAULT_AQP1_VERDICT_JSON)
    parser.add_argument("--glut1-verdict-json", default=DEFAULT_GLUT1_VERDICT_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.aqp1_verdict_json),
        _load_json(args.glut1_verdict_json),
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
