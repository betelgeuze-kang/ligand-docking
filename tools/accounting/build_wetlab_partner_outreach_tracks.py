#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/wetlab_partner_outreach_tracks_current.json"
DEFAULT_OUT_CSV = "runs/wetlab_partner_outreach_tracks_current.csv"
DEFAULT_OUT_MD = "runs/wetlab_partner_outreach_tracks_current.md"

TRACK_ROWS = [
    {
        "track_id": "DNDi_IPK",
        "track_label": "DNDi / Institut Pasteur Korea",
        "best_targets": "T. cruzi PDE, Cruzain, Leishmania braziliensis DHODH",
        "pitch_angle": "Cheap neglected-disease enzyme/protease validation with immediate pathogen-vs-host selectivity story.",
        "what_to_send_first": "1-page brief plus top-3 repurposing/top-3 novelty shortlist and anti-target plan.",
        "offer_model": "mission-aligned micro-validation with shared assay burden",
    },
    {
        "track_id": "M4K_open_science",
        "track_label": "M4K / rare-disease open-science kinase",
        "best_targets": "ALK2",
        "pitch_angle": "Dynamic kinase-state discrimination with cheap early biochemical or DSF validation and repurposing fallback.",
        "what_to_send_first": "ALK2 top-3 repurposing plus top-3 novelty packet with mutant/wild-type and kinase-selectivity plan.",
        "offer_model": "open-science co-development with strong publication logic",
    },
    {
        "track_id": "READDI_Korea",
        "track_label": "READDI / Korea antiviral rail",
        "best_targets": "SARS-CoV-2 PLpro, SARS-CoV-2 Mpro",
        "pitch_angle": "Fast low-friction antiviral protease validation with dynamics-first selectivity framing.",
        "what_to_send_first": "paired PLpro/Mpro packet showing top-3 compounds, controls, and host-protease counterscreens.",
        "offer_model": "rapid micro-validation with pandemic-preparedness framing",
    },
    {
        "track_id": "oncology_condition_aware",
        "track_label": "Condition-aware oncology labs",
        "best_targets": "CA IX with CA XII companion",
        "pitch_angle": "Assay-conditioned pH-aware ranking in tumor-like buffer with explicit selectivity panel.",
        "what_to_send_first": "CA IX packet with acidic-buffer setup, CA II/CA XII panel, and top-3 approved low-cost compounds.",
        "offer_model": "small-budget condition-specific validation collaboration",
    },
    {
        "track_id": "SGC_dark_kinase",
        "track_label": "SGC / dark kinase structural-biology labs",
        "best_targets": "STK17B (DRAK2)",
        "pitch_angle": "P-loop and conformational dynamics story benchmarked against open probe/negative-control ecosystem.",
        "what_to_send_first": "probe-benchmarked novelty packet plus DSF or biochemical validation plan.",
        "offer_model": "probe-informed collaboration with fast structural-biology validation",
    },
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
    summary = {
        "status": "wetlab_partner_outreach_tracks_ready",
        "track_count": len(TRACK_ROWS),
        "primary_track_order": "DNDi_IPK -> M4K_open_science -> READDI_Korea -> oncology_condition_aware -> SGC_dark_kinase",
        "next_required_step": "Use these outreach tracks to fork the same scientific core into partner-specific first-contact packets instead of sending the same generic deck to every lab.",
    }
    return {"summary": summary, "rows": TRACK_ROWS}


def _write_markdown(path: Path, payload: dict) -> None:
    s = payload["summary"]
    lines = [
        "# Wet-Lab Partner Outreach Tracks",
        "",
        f"- status: `{s['status']}`",
        f"- track_count: `{s['track_count']}`",
        f"- primary_track_order: `{s['primary_track_order']}`",
        "",
        "| track_id | track_label | best_targets | offer_model |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['track_id']}` | `{row['track_label']}` | {row['best_targets']} | {row['offer_model']} |"
        )
    lines.extend(["", "## Track Notes", ""])
    for row in payload["rows"]:
        lines.extend([
            f"- `{row['track_label']}`: {row['pitch_angle']}",
            f"  Send first: {row['what_to_send_first']}",
        ])
    lines.extend(["", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build partner-specific wet-lab outreach track guidance.")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload()
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv_rows(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
