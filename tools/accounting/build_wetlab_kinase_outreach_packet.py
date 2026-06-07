#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_KINASE_FIRST_CONTACT_JSON = "runs/wetlab_wave1_kinase_first_contact_packets_current.json"
DEFAULT_OUTREACH_JSON = "runs/wetlab_partner_outreach_tracks_current.json"
DEFAULT_OUT_JSON = "runs/wetlab_kinase_outreach_packet_current.json"
DEFAULT_OUT_CSV = "runs/wetlab_kinase_outreach_packet_current.csv"
DEFAULT_OUT_MD = "runs/wetlab_kinase_outreach_packet_current.md"

SEQUENCE_PRESETS = {
    "ALK2": 1,
    "STK17B (DRAK2)": 2,
}

EMAIL_PRESETS: dict[str, dict[str, str]] = {
    "ALK2": {
        "first_email_subject_hint": "Open-science ALK2 validation packet for mutant-aware rare-disease kinase triage",
        "first_email_body_brief": "We have a compact ALK2 first-contact packet built around public M4K structure and chemistry context, with a cheap mutant-aware biochemical or DSF entry readout, mutant-versus-wild-type comparison, and an ALK-family mini-panel before any broader expansion. The ask is a small open-science validation step, not a full kinase campaign.",
    },
    "STK17B (DRAK2)": {
        "first_email_subject_hint": "Open-set benchmark STK17B packet for fast DSF or biochemical validation",
        "first_email_body_brief": "We have a compact STK17B first-contact packet benchmarked against a published PKIS trio plus the 11-series open probe frame, with DSF or biochemical entry readout and a neighborhood dark-kinase counterscreen. The ask is a low-risk structural-biology-style validation step that tests whether our dynamic P-loop ranking adds signal inside an existing open-set benchmark, not just against a single public probe.",
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


def _rows_by_target(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("target_id", "")): dict(row)
        for row in payload.get("rows", []) or []
        if str(row.get("target_id", ""))
    }


def _rows_by_track(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("track_id", "")): dict(row)
        for row in payload.get("rows", []) or []
        if str(row.get("track_id", ""))
    }


def build_payload(kinase_first_contact: dict[str, Any], outreach: dict[str, Any]) -> dict[str, Any]:
    source_rows = _rows_by_target(kinase_first_contact)
    outreach_rows = _rows_by_track(outreach)

    rows: list[dict[str, Any]] = []
    for target_id in ("ALK2", "STK17B (DRAK2)"):
        source = source_rows[target_id]
        track = outreach_rows[source["partner_track_id"]]
        email = EMAIL_PRESETS[target_id]
        rows.append(
            {
                "target_id": target_id,
                "partner_track_id": source["partner_track_id"],
                "why_this_rail": f"{track['track_label']} is the right first rail because {source['why_now']}",
                "what_to_send_first": track["what_to_send_first"],
                "offer_model": track["offer_model"],
                "target_sequence": SEQUENCE_PRESETS[target_id],
                "first_email_subject_hint": email["first_email_subject_hint"],
                "first_email_body_brief": email["first_email_body_brief"],
                "one_page_headline": source["one_page_headline"],
                "first_assay": source["first_assay"],
                "anti_target_panel": source["anti_target_panel"],
                "first_packet_goal": source["first_packet_goal"],
                "main_external_objection": source["main_external_objection"],
                "objection_answer": source["objection_answer"],
                "repurposing_fill_status": source.get("repurposing_fill_status", "repurposing_pending"),
                "repurposing_compounds": source.get("repurposing_compounds", ""),
                "novelty_fill_status": source.get("novelty_fill_status", "novelty_pending"),
                "novelty_compounds": source.get("novelty_compounds", ""),
                "source_anchor": source["source_anchor"],
                "source_url": source["source_url"],
                "track_label": track["track_label"],
                "pitch_angle": track["pitch_angle"],
                "status": "ready_for_partner_specific_export" if source.get("repurposing_compounds") and source.get("novelty_compounds") else "awaiting_compound_fill",
            }
        )

    if all(row["status"] == "ready_for_partner_specific_export" for row in rows):
        next_required_step = "Export the M4K and SGC partner-facing emails now that both kinase rows have bound repurposing and novelty lanes."
    else:
        next_required_step = "Attach actual top-3 repurposing and top-3 novelty candidates to these two outreach rows, then export partner-facing emails and one-page attachments."

    summary = {
        "status": "wetlab_kinase_outreach_packet_ready",
        "row_count": len(rows),
        "track_count": len({row["partner_track_id"] for row in rows}),
        "explicit_track_difference": "M4K_open_science expects an open-science rare-disease kinase packet with mutant-aware selectivity; SGC_dark_kinase expects a probe-benchmarked dark-kinase packet with positive/negative-control framing.",
        "next_required_step": next_required_step,
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Wet-Lab Kinase Outreach Packet",
        "",
        f"- status: `{s['status']}`",
        f"- row_count: `{s['row_count']}`",
        f"- track_count: `{s['track_count']}`",
        f"- explicit_track_difference: {s['explicit_track_difference']}",
        "",
        "| target_sequence | target_id | partner_track_id | first_email_subject_hint | status |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_sequence']}` | `{row['target_id']}` | `{row['partner_track_id']}` | {row['first_email_subject_hint']} | `{row['status']}` |"
        )
    lines.extend(["", "## Packets", ""])
    for row in payload["rows"]:
        lines.extend(
            [
                f"## {row['target_id']}",
                "",
                f"- partner_track_id: `{row['partner_track_id']}`",
                f"- why_this_rail: {row['why_this_rail']}",
                f"- what_to_send_first: {row['what_to_send_first']}",
                f"- offer_model: {row['offer_model']}",
                f"- target_sequence: `{row['target_sequence']}`",
                f"- first_email_subject_hint: {row['first_email_subject_hint']}",
                f"- first_email_body_brief: {row['first_email_body_brief']}",
                f"- one_page_headline: {row['one_page_headline']}",
                f"- first_assay: {row['first_assay']}",
                f"- anti_target_panel: {row['anti_target_panel']}",
                f"- first_packet_goal: {row['first_packet_goal']}",
                f"- main_external_objection: {row['main_external_objection']}",
                f"- objection_answer: {row['objection_answer']}",
                f"- repurposing_fill_status: `{row['repurposing_fill_status']}`",
                f"- repurposing_compounds: `{row['repurposing_compounds']}`",
                f"- novelty_fill_status: `{row['novelty_fill_status']}`",
                f"- novelty_compounds: `{row['novelty_compounds']}`",
                f"- status: `{row['status']}`",
                f"- source_anchor: [{row['source_anchor']}]({row['source_url']})",
                "",
            ]
        )
    lines.extend(["## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the kinase outreach export packet for ALK2 and STK17B.")
    parser.add_argument("--kinase-first-contact-json", default=DEFAULT_KINASE_FIRST_CONTACT_JSON)
    parser.add_argument("--outreach-json", default=DEFAULT_OUTREACH_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.kinase_first_contact_json),
        _load_json(args.outreach_json),
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv_rows(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
