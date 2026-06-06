#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/wetlab_one_page_brief_schema_current.json"
DEFAULT_OUT_MD = "runs/wetlab_one_page_brief_schema_current.md"

SUMMARY_FIELDS = [
    "target_id",
    "wave",
    "partner_track",
    "headline",
    "disease_area",
    "domain_family",
    "first_assay",
    "anti_target_panel",
    "first_go_no_go",
    "main_external_objection",
    "objection_answer",
]

ROW_FIELDS = [
    "lane_type",
    "slot_rank",
    "selection_rule",
    "why_it_exists",
    "must_not_do",
]


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def build_payload() -> dict:
    return {
        "summary": {
            "status": "wetlab_one_page_brief_schema_ready",
            "summary_field_count": len(SUMMARY_FIELDS),
            "row_field_count": len(ROW_FIELDS),
            "summary_fields": SUMMARY_FIELDS,
            "row_fields": ROW_FIELDS,
            "suggested_artifact_pattern": "runs/wetlab_target_brief_<slug>_current.md",
            "next_required_step": "Use this schema to generate one-page brief packets for each Wave 1 target, then fill the repurposing and novelty slot rows with actual compound shortlists.",
        }
    }


def _write_markdown(path: Path, payload: dict) -> None:
    s = payload["summary"]
    lines = [
        "# Wet-Lab One-Page Brief Schema",
        "",
        f"- status: `{s['status']}`",
        f"- summary_field_count: `{s['summary_field_count']}`",
        f"- row_field_count: `{s['row_field_count']}`",
        f"- suggested_artifact_pattern: `{s['suggested_artifact_pattern']}`",
        "",
        "## Summary Fields",
        "",
    ]
    lines.extend(f"- `{field}`" for field in s["summary_fields"])
    lines.extend(["", "## Row Fields", ""])
    lines.extend(f"- `{field}`" for field in s["row_fields"])
    lines.extend(["", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the shared one-page brief schema for wet-lab partner packets.")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload()
    out_json = _resolve(args.out_json)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
