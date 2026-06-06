#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from betelgeuze_cameo.format_validation import build_format_validation_packet
from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_JSON = "runs/cameo_format_validation_packet_current.json"
DEFAULT_OUT_CSV = "runs/cameo_format_validation_packet_current.csv"
DEFAULT_OUT_MD = "runs/cameo_format_validation_packet_current.md"


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
        "# CAMEO Format Validation Packet",
        "",
        f"- status: `{s['status']}`",
        f"- target_id: `{s['target_id']}`",
        f"- validated/pass/fail: `{s['validated_model_count']}/{s['format_pass_count']}/{s['format_fail_count']}`",
        f"- model1_format_pass: `{s['model1_format_pass']}`",
        f"- native_or_external_accuracy_used: `{s['native_or_external_accuracy_used']}`",
        f"- outbound_email_enabled: `{s['outbound_email_enabled']}`",
        "",
        "## Rows",
        "",
        "| rank | candidate | format | status | blockers | warnings | atoms | models | chains | residues | model_path |",
        "| ---: | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row.get('cameo_model_rank', '')} | `{row.get('candidate_id', '')}` | `{row.get('detected_format', '')}` | "
            f"`{row.get('format_validation_status', '')}` | `{row.get('format_blockers', '')}` | "
            f"`{row.get('format_warnings', '')}` | {row.get('atom_count', 0)} | {row.get('model_count', 0)} | "
            f"{row.get('chain_count', 0)} | {row.get('residue_count', 0)} | `{row.get('model_path', '')}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a CAMEO PDB/mmCIF validation packet from selected model rows.")
    parser.add_argument("--models-csv", required=True, help="CSV with model_path plus optional target_id, candidate_id, cameo_model_rank.")
    parser.add_argument("--target-id", default="")
    parser.add_argument("--all-rows", action="store_true", help="Validate every row instead of selected top5/model1 rows.")
    parser.add_argument("--base-dir", default=str(ROOT), help="Base directory for relative model_path values.")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_format_validation_packet(
        _read_csv_rows(args.models_csv),
        target_id=args.target_id,
        base_dir=args.base_dir,
        selected_only=not bool(args.all_rows),
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
