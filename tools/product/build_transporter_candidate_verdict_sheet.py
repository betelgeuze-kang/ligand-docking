#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

FAMILY_SPECS = {
    "aqp1": {
        "seed_json": "runs/aqp1_external_evidence_seed_current.json",
        "out_json": "runs/aqp1_candidate_verdict_sheet_current.json",
        "out_csv": "runs/aqp1_candidate_verdict_sheet_current.csv",
        "out_md": "runs/aqp1_candidate_verdict_sheet_current.md",
        "title": "AQP1 Candidate Verdict Sheet",
    },
    "glut1": {
        "seed_json": "runs/glut1_external_evidence_seed_current.json",
        "out_json": "runs/glut1_candidate_verdict_sheet_current.json",
        "out_csv": "runs/glut1_candidate_verdict_sheet_current.csv",
        "out_md": "runs/glut1_candidate_verdict_sheet_current.md",
        "title": "GLUT1 Candidate Verdict Sheet",
    },
}


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


def build_payload(family: str, external_seed: dict[str, Any]) -> dict[str, Any]:
    seed_rows = [dict(row) for row in (external_seed.get("rows", []) or [])]
    verdict_rows: list[dict[str, Any]] = []
    for row in seed_rows:
        verdict_rows.append(
            {
                "candidate_name": str(row.get("candidate_name", "")).strip(),
                "proposed_packet_step": str(row.get("proposed_packet_step", "")).strip(),
                "review_bucket": str(row.get("recommended_review_bucket", "")).strip(),
                "recommended_verdict": str(row.get("recommended_verdict", "")).strip(),
                "promotion_policy": str(row.get("promotion_policy", "")).strip(),
                "source_anchor": str(row.get("source_anchor", "")).strip(),
                "caution": str(row.get("caution", "")).strip(),
            }
        )
    summary = {
        "family": family,
        "candidate_count": len(verdict_rows),
        "keep_review_only_count": sum(1 for row in verdict_rows if row["recommended_verdict"] == "keep_review_only"),
        "caution_only_count": sum(1 for row in verdict_rows if row["recommended_verdict"] == "caution_only"),
        "defer_count": sum(1 for row in verdict_rows if row["recommended_verdict"] == "defer"),
        "next_required_step": "Treat this verdict sheet as the current manual-review policy. Do not promote any transporter row to authoritative apply from this sheet alone.",
    }
    return {"summary": summary, "rows": verdict_rows}


def _write_markdown(path: Path, payload: dict[str, Any], title: str) -> None:
    s = payload["summary"]
    lines = [
        f"# {title}",
        "",
        f"- family: `{s['family']}`",
        f"- candidate_count: `{s['candidate_count']}`",
        f"- keep_review_only_count: `{s['keep_review_only_count']}`",
        f"- caution_only_count: `{s['caution_only_count']}`",
        f"- defer_count: `{s['defer_count']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Verdicts",
        "",
        "| candidate_name | proposed_packet_step | review_bucket | recommended_verdict | source_anchor |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['candidate_name']}` | `{row['proposed_packet_step']}` | `{row['review_bucket']}` | `{row['recommended_verdict']}` | `{row['source_anchor']}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build transporter candidate verdict sheet from external evidence seed.")
    parser.add_argument("--family", choices=sorted(FAMILY_SPECS.keys()), required=True)
    parser.add_argument("--external-seed-json")
    parser.add_argument("--out-json")
    parser.add_argument("--out-csv")
    parser.add_argument("--out-md")
    args = parser.parse_args()
    spec = FAMILY_SPECS[args.family]
    if not args.external_seed_json:
        args.external_seed_json = spec["seed_json"]
    if not args.out_json:
        args.out_json = spec["out_json"]
    if not args.out_csv:
        args.out_csv = spec["out_csv"]
    if not args.out_md:
        args.out_md = spec["out_md"]
    return args


def main() -> None:
    args = parse_args()
    spec = FAMILY_SPECS[args.family]
    payload = build_payload(args.family, _load_json(args.external_seed_json))
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(out_csv, payload["rows"])
    _write_markdown(out_md, payload, spec["title"])


if __name__ == "__main__":
    main()
