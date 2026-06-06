#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/wetlab_neglected_outreach_packet_current.json"
DEFAULT_OUT_CSV = "runs/wetlab_neglected_outreach_packet_current.csv"
DEFAULT_OUT_MD = "runs/wetlab_neglected_outreach_packet_current.md"
DEFAULT_INPUT_JSON = "runs/wetlab_neglected_first_contact_packets_current.json"

TARGET_SEQUENCE = [
    "T. cruzi PDE",
    "Cruzain",
    "Leishmania braziliensis DHODH",
]


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _load_first_contact_rows(input_json: Path) -> list[dict[str, Any]]:
    payload = json.loads(input_json.read_text(encoding="utf-8"))
    rows = {row["target_id"]: row for row in payload["rows"]}
    return [
        {
            "priority_rank": idx + 1,
            "target_id": target_id,
            **rows[target_id],
        }
        for idx, target_id in enumerate(TARGET_SEQUENCE)
    ]


def build_payload(input_json: str = DEFAULT_INPUT_JSON) -> dict[str, Any]:
    resolved_input = _resolve(input_json)
    rows = _load_first_contact_rows(resolved_input)
    try:
        source_artifact = str(resolved_input.relative_to(ROOT))
    except ValueError:
        source_artifact = str(resolved_input)
    summary = {
        "status": "wetlab_neglected_outreach_packet_ready",
        "partner_track_id": "DNDi_IPK",
        "row_count": len(rows),
        "why_this_rail": (
            "DNDi/IPK is the strongest low-friction neglected-disease rail because it combines official or adjacent "
            "mission pull, cheap enzyme or protease assay entry, and an immediate host-vs-pathogen selectivity story."
        ),
        "what_to_send_first": (
            "Send one bundled DNDi/IPK first-contact packet containing three target briefs, each with one-page "
            "headline, why-now framing, first assay stack, anti-target panel, and a filtered first-packet goal before "
            "compound identities are finalized."
        ),
        "offer_model": "mission-aligned micro-validation with shared assay burden",
        "target_sequence": "T. cruzi PDE -> Cruzain -> Leishmania braziliensis DHODH",
        "first_email_subject_hint": (
            "Mission-aligned neglected-disease micro-validation packet: Chagas PDE, Cruzain, and Leishmania DHODH"
        ),
        "first_email_body_brief": (
            "We are sending a DNDi/IPK-aligned outbound packet built around three low-friction neglected-disease "
            "targets with immediate host-selectivity guardrails. The ask is a micro-validation conversation, not a "
            "broad discovery burden: start with recombinant assay entry, counterscreens up front, and a small filtered "
            "shortlist once the rail fit is confirmed."
        ),
        "source_artifact": source_artifact,
        "next_required_step": (
            "Attach target-specific top-3 repurposing, top-3 novelty, and control compounds, then export this bundle "
            "as the DNDi/IPK first-contact outbound packet."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Wet-Lab Neglected-Disease Outreach Packet",
        "",
        f"- status: `{s['status']}`",
        f"- partner_track_id: `{s['partner_track_id']}`",
        f"- row_count: `{s['row_count']}`",
        f"- why_this_rail: {s['why_this_rail']}",
        f"- what_to_send_first: {s['what_to_send_first']}",
        f"- offer_model: `{s['offer_model']}`",
        f"- target_sequence: `{s['target_sequence']}`",
        f"- first_email_subject_hint: {s['first_email_subject_hint']}",
        f"- first_email_body_brief: {s['first_email_body_brief']}",
        f"- source_artifact: `{s['source_artifact']}`",
        "",
        "## Targets",
        "",
    ]
    for row in payload["rows"]:
        lines.extend([
            f"### {row['priority_rank']}. {row['target_id']}",
            "",
            f"- partner_track_id: `{row['partner_track_id']}`",
            f"- one_page_headline: {row['one_page_headline']}",
            f"- why_now: {row['why_now']}",
            f"- first_assay: {row['first_assay']}",
            f"- anti_target_panel: {row['anti_target_panel']}",
            f"- first_packet_goal: {row['first_packet_goal']}",
            f"- main_external_objection: {row['main_external_objection']}",
            f"- objection_answer: {row['objection_answer']}",
            f"- source_anchor: `{row['source_anchor']}`",
            f"- source_url: {row['source_url']}",
            "",
        ])
    lines.extend(["## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build DNDi/IPK neglected-disease outreach export packet.")
    parser.add_argument("--input-json", default=DEFAULT_INPUT_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(input_json=args.input_json)
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv_rows(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
