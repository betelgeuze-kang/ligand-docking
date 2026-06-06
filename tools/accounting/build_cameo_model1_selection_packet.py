#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from betelgeuze_cameo.selector import build_selection_packet
from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/cameo_model1_selection_packet_current.json"
DEFAULT_OUT_CSV = "runs/cameo_model1_selection_packet_current.csv"
DEFAULT_OUT_MD = "runs/cameo_model1_selection_packet_current.md"


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_csv_rows(path_like: str | Path) -> list[dict[str, Any]]:
    path = _resolve(path_like)
    with path.open("r", encoding="utf-8", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# CAMEO Model1 Selection Packet",
        "",
        f"- status: `{s['selection_status']}`",
        f"- target_id: `{s['target_id']}`",
        f"- candidates/eligible/top5/model1: `{s['candidate_count']}/{s['eligible_candidate_count']}/{s['top5_candidate_count']}/{s['model1_candidate_count']}`",
        f"- model1: `{s['model1_candidate_id'] or '-'}` path `{s['model1_model_path'] or '-'}` score `{s['model1_selection_score']}`",
        f"- native_or_external_accuracy_used: `{s['native_or_external_accuracy_used']}`",
        f"- outbound_email_enabled: `{s['outbound_email_enabled']}`",
        "",
        "## Rows",
        "",
        "| rank | candidate | status | score | validation | source | blockers | model_path |",
        "| ---: | --- | --- | ---: | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['cameo_model_rank']} | `{row['candidate_id']}` | `{row['selection_status']}` | "
            f"{row['selection_score']} | `{row['validation_status']}` | `{row['source_kind']}` | "
            f"`{row['selector_blockers']}` | `{row.get('model_path', '')}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a CAMEO model1/top5 selection packet from candidate rows.")
    parser.add_argument("--candidates-csv", required=True)
    parser.add_argument("--target-id", default="")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_selection_packet(_read_csv_rows(args.candidates_csv), target_id=args.target_id)
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()

