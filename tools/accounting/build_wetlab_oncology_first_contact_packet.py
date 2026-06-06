#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CAIX_BRIEF_JSON = "runs/ca_ix_one_page_brief_current.json"
DEFAULT_FIRST_CONTACT_BUNDLE_JSON = "runs/wetlab_first_contact_brief_bundle_current.json"
DEFAULT_OUTREACH_JSON = "runs/wetlab_partner_outreach_tracks_current.json"
DEFAULT_COMPANION_JSON = "runs/wetlab_validation_companion_panels_current.json"
DEFAULT_REPURPOSING_FILL_JSON = "runs/wetlab_priority3_repurposing_fill_map_current.json"
DEFAULT_NOVELTY_FILL_JSON = "runs/wetlab_priority3_novelty_fill_map_current.json"
DEFAULT_OUT_JSON = "runs/wetlab_oncology_first_contact_packet_current.json"
DEFAULT_OUT_CSV = "runs/wetlab_oncology_first_contact_packet_current.csv"
DEFAULT_OUT_MD = "runs/wetlab_oncology_first_contact_packet_current.md"


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


def _row_by_target(payload: dict[str, Any], target_id: str) -> dict[str, Any]:
    for row in payload.get("rows", []) or []:
        if str(row.get("target_id", "")).strip() == target_id:
            return dict(row)
    raise KeyError(target_id)


def _row_by_track(payload: dict[str, Any], track_id: str) -> dict[str, Any]:
    for row in payload.get("rows", []) or []:
        if str(row.get("track_id", "")).strip() == track_id:
            return dict(row)
    raise KeyError(track_id)


def _primary_source(brief: dict[str, Any], anchor_prefix: str) -> dict[str, str]:
    for row in brief.get("structured", {}).get("primary_sources", []) or []:
        anchor = str(row.get("source_anchor", "")).strip()
        if anchor.startswith(anchor_prefix):
            return {
                "source_anchor": anchor,
                "source_url": str(row.get("source_url", "")).strip(),
            }
    raise KeyError(anchor_prefix)


def build_payload(
    caix_brief: dict[str, Any],
    first_contact_bundle: dict[str, Any],
    outreach_tracks: dict[str, Any],
    companion_panels: dict[str, Any],
    repurposing_fill: dict[str, Any] | None = None,
    novelty_fill: dict[str, Any] | None = None,
) -> dict[str, Any]:
    bundle_row = _row_by_target(first_contact_bundle, "CA IX")
    outreach_row = _row_by_track(outreach_tracks, str(bundle_row.get("outreach_track_id", "")).strip())
    companion_row = _row_by_target(companion_panels, "CA IX")
    brief_s = dict(caix_brief.get("structured", {}) or {})
    assay_s = dict(brief_s.get("first_assay_stack_under_acidic_tumor_like_buffer", {}) or {})
    selectivity_s = dict(brief_s.get("ca_ii_ca_xii_selectivity_counterscreen_plan", {}) or {})
    caix_novelty_rows = sorted(
        [
            dict(row)
            for row in (novelty_fill or {}).get("rows", []) or []
            if str(row.get("target_id", "")).strip() == "CA IX"
        ],
        key=lambda item: int(item.get("slot_rank", 0) or 0),
    )
    caix_repurposing_rows = sorted(
        [
            dict(row)
            for row in (repurposing_fill or {}).get("rows", []) or []
            if str(row.get("target_id", "")).strip() == "CA IX"
        ],
        key=lambda item: int(item.get("slot_rank", 0) or 0),
    )

    acidic_source = _primary_source(caix_brief, "Lee et al. 2018 CA IX pH-stat in vivo")
    media_source = _primary_source(caix_brief, "Yudowski et al. 2018 MES vs HEPES acidic media")

    anti_target_panel = "CA IX primary acidic arm with explicit CA XII companion counterscreen and CA II housekeeping deselection"
    first_packet_goal = (
        f"{bundle_row['first_packet_goal']} Require same-packet CA XII companion classification and CA II deselection "
        "before any compound is described as CA IX-biased."
    )
    objection_answer = (
        f"{bundle_row['objection_answer']} The first-contact packet therefore treats CA XII as a required tumor-CA companion "
        "and CA II as the immediate deselection gate, not as optional follow-up work."
    )

    buffer_program = {
        "primary_buffer_arm": str(assay_s.get("buffer_primary_arm", "MES-buffered acidic arm centered on pH 6.6")).strip(),
        "neutral_contrast_arm": str(assay_s.get("buffer_neutral_contrast_arm", "HEPES-buffered neutral contrast arm at pH 7.4")).strip(),
        "counterscreen_program": "Run the same compound set on CA XII and CA II after the acidic CA IX arm, then compare against the neutral CA IX contrast arm.",
        "go_no_go_rule": str(assay_s.get("first_go_no_go", "acidic-condition advantage with CA IX-biased selectivity")).strip(),
        "buffer_source_anchor": f"{acidic_source['source_anchor']} + {media_source['source_anchor']}",
        "buffer_source_url": f"{acidic_source['source_url']} ; {media_source['source_url']}",
    }

    structured = {
        "partner_track_id": outreach_row["track_id"],
        "one_page_headline": bundle_row["one_page_headline"],
        "why_now": bundle_row["why_now"],
        "first_assay": bundle_row["first_assay"],
        "anti_target_panel": anti_target_panel,
        "first_packet_goal": first_packet_goal,
        "main_external_objection": bundle_row["main_external_objection"],
        "objection_answer": objection_answer,
        "source_anchor": acidic_source["source_anchor"],
        "source_url": acidic_source["source_url"],
        "buffer_program": buffer_program,
        "companion_panel_label": companion_row["primary_companion_panel"],
        "companion_panel_rationale": companion_row["companion_why"],
        "pitch_angle": outreach_row["pitch_angle"],
        "what_to_send_first": outreach_row["what_to_send_first"],
        "offer_model": outreach_row["offer_model"],
        "repurposing_fill_artifact": "runs/wetlab_priority3_repurposing_fill_map_current.md" if caix_repurposing_rows else "",
        "repurposing_compounds": "; ".join(row["compound_name"] for row in caix_repurposing_rows),
        "novelty_fill_artifact": "runs/wetlab_priority3_novelty_fill_map_current.md" if caix_novelty_rows else "",
        "novelty_compounds": "; ".join(row["novelty_compound_name"] for row in caix_novelty_rows),
    }

    rows = [
        {"section": "partner_track_id", "rank": 1, "label": "partner_track_id", "content": structured["partner_track_id"], "source_anchor": "outreach_track", "source_url": ""},
        {"section": "one_page_headline", "rank": 1, "label": "one_page_headline", "content": structured["one_page_headline"], "source_anchor": bundle_row["source_anchor"], "source_url": bundle_row["source_url"]},
        {"section": "why_now", "rank": 1, "label": "why_now", "content": structured["why_now"], "source_anchor": bundle_row["source_anchor"], "source_url": bundle_row["source_url"]},
        {"section": "first_assay", "rank": 1, "label": "first_assay", "content": structured["first_assay"], "source_anchor": buffer_program["buffer_source_anchor"], "source_url": buffer_program["buffer_source_url"]},
        {"section": "anti_target_panel", "rank": 1, "label": "anti_target_panel", "content": structured["anti_target_panel"], "source_anchor": companion_row["primary_companion_panel"], "source_url": ""},
        {"section": "first_packet_goal", "rank": 1, "label": "first_packet_goal", "content": structured["first_packet_goal"], "source_anchor": bundle_row["source_anchor"], "source_url": bundle_row["source_url"]},
        {"section": "main_external_objection", "rank": 1, "label": "main_external_objection", "content": structured["main_external_objection"], "source_anchor": bundle_row["source_anchor"], "source_url": bundle_row["source_url"]},
        {"section": "objection_answer", "rank": 1, "label": "objection_answer", "content": structured["objection_answer"], "source_anchor": buffer_program["buffer_source_anchor"], "source_url": buffer_program["buffer_source_url"]},
        {"section": "source_anchor", "rank": 1, "label": "source_anchor", "content": structured["source_anchor"], "source_anchor": structured["source_anchor"], "source_url": structured["source_url"]},
        {"section": "source_url", "rank": 1, "label": "source_url", "content": structured["source_url"], "source_anchor": structured["source_anchor"], "source_url": structured["source_url"]},
        {"section": "buffer_program", "rank": 1, "label": "primary_buffer_arm", "content": buffer_program["primary_buffer_arm"], "source_anchor": buffer_program["buffer_source_anchor"], "source_url": buffer_program["buffer_source_url"]},
        {"section": "buffer_program", "rank": 2, "label": "neutral_contrast_arm", "content": buffer_program["neutral_contrast_arm"], "source_anchor": media_source["source_anchor"], "source_url": media_source["source_url"]},
        {"section": "buffer_program", "rank": 3, "label": "counterscreen_program", "content": buffer_program["counterscreen_program"], "source_anchor": selectivity_s.get("primary_panel", "CA II plus CA XII counterscreen"), "source_url": ""},
        {"section": "buffer_program", "rank": 4, "label": "go_no_go_rule", "content": buffer_program["go_no_go_rule"], "source_anchor": assay_s.get("first_go_no_go", "acidic-condition advantage with CA IX-biased selectivity"), "source_url": ""},
    ]

    summary = {
        "status": "wetlab_oncology_first_contact_packet_ready",
        "target_id": "CA IX",
        "partner_track_id": structured["partner_track_id"],
        "validation_companion_target": "CA XII",
        "housekeeping_deselection_target": "CA II",
        "row_count": len(rows),
        "export_ready": bool(caix_novelty_rows),
        "next_required_step": "Route the CA IX-enriched oncology condition-aware first-contact packet with the bound novelty trio and explicit CA II/CA XII deselection.",
    }
    return {"summary": summary, "structured": structured, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    p = payload["structured"]
    b = p["buffer_program"]
    lines = [
        "# Wet-Lab Oncology First Contact Packet",
        "",
        f"- status: `{s['status']}`",
        f"- target_id: `{s['target_id']}`",
        f"- partner_track_id: `{s['partner_track_id']}`",
        f"- validation_companion_target: `{s['validation_companion_target']}`",
        f"- housekeeping_deselection_target: `{s['housekeeping_deselection_target']}`",
        f"- row_count: `{s['row_count']}`",
        f"- export_ready: `{s['export_ready']}`",
        "",
        "## Partner Track",
        "",
        f"- partner_track_id: `{p['partner_track_id']}`",
        f"- pitch_angle: {p['pitch_angle']}",
        f"- what_to_send_first: {p['what_to_send_first']}",
        f"- offer_model: {p['offer_model']}",
        "",
        "## One-Page Headline",
        "",
        f"- {p['one_page_headline']}",
        "",
        "## Why Now",
        "",
        f"- {p['why_now']}",
        "",
        "## First Assay",
        "",
        f"- {p['first_assay']}",
        "",
        "## Anti-Target Panel",
        "",
        f"- {p['anti_target_panel']}",
        f"- companion_panel_label: {p['companion_panel_label']}",
        f"- companion_panel_rationale: {p['companion_panel_rationale']}",
        f"- repurposing_fill_artifact: `{p['repurposing_fill_artifact']}`",
        f"- repurposing_compounds: `{p['repurposing_compounds']}`",
        f"- novelty_fill_artifact: `{p['novelty_fill_artifact']}`",
        f"- novelty_compounds: `{p['novelty_compounds']}`",
        "",
        "## First Packet Goal",
        "",
        f"- {p['first_packet_goal']}",
        "",
        "## Main External Objection",
        "",
        f"- {p['main_external_objection']}",
        "",
        "## Objection Answer",
        "",
        f"- {p['objection_answer']}",
        "",
        "## Source",
        "",
        f"- source_anchor: `{p['source_anchor']}`",
        f"- source_url: {p['source_url']}",
        "",
        "## Buffer Program",
        "",
        f"- primary_buffer_arm: {b['primary_buffer_arm']}",
        f"- neutral_contrast_arm: {b['neutral_contrast_arm']}",
        f"- counterscreen_program: {b['counterscreen_program']}",
        f"- go_no_go_rule: {b['go_no_go_rule']}",
        f"- buffer_source_anchor: `{b['buffer_source_anchor']}`",
        f"- buffer_source_url: {b['buffer_source_url']}",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the oncology condition-aware first-contact packet for CA IX.")
    parser.add_argument("--caix-brief-json", default=DEFAULT_CAIX_BRIEF_JSON)
    parser.add_argument("--first-contact-bundle-json", default=DEFAULT_FIRST_CONTACT_BUNDLE_JSON)
    parser.add_argument("--outreach-json", default=DEFAULT_OUTREACH_JSON)
    parser.add_argument("--companion-json", default=DEFAULT_COMPANION_JSON)
    parser.add_argument("--repurposing-fill-json", default=DEFAULT_REPURPOSING_FILL_JSON)
    parser.add_argument("--novelty-fill-json", default=DEFAULT_NOVELTY_FILL_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.caix_brief_json),
        _load_json(args.first_contact_bundle_json),
        _load_json(args.outreach_json),
        _load_json(args.companion_json),
        _load_json(args.repurposing_fill_json),
        _load_json(args.novelty_fill_json),
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
