#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PORTFOLIO_JSON = "runs/wetlab_partner_target_portfolio_current.json"
DEFAULT_BLUEPRINT_JSON = "runs/wetlab_wave1_campaign_blueprint_current.json"
DEFAULT_OUTREACH_JSON = "runs/wetlab_partner_outreach_tracks_current.json"
DEFAULT_OUT_JSON = "runs/wetlab_wave1_one_page_briefs_current.json"
DEFAULT_OUT_CSV = "runs/wetlab_wave1_one_page_briefs_current.csv"
DEFAULT_OUT_MD = "runs/wetlab_wave1_one_page_briefs_current.md"

BRIEF_PRESETS: dict[str, dict[str, str]] = {
    "T. cruzi PDE": {
        "headline": "Selective parasite PDE triage for cheap Chagas validation without human PDE spillover.",
        "objection": "Human PDE cross-reactivity will bury any apparent hit.",
        "answer": "We ship the parasite assay with a human PDE counterscreen on day one, so the pitch is selectivity-first rather than raw hit finding.",
    },
    "Cruzain": {
        "headline": "Cruzain hit-finding focused on dynamic desolvation rather than generic cysteine-protease noise.",
        "objection": "Cheap Cruzain hits are often just reactive electrophiles.",
        "answer": "The first stack pairs fluorogenic Cruzain screening with thiol-reactivity and host protease sanity checks, so we reject generic reactivity early.",
    },
    "ALK2": {
        "headline": "Open-science ALK2 triage with dynamic kinase-state separation and a fast biochemical entry point.",
        "objection": "This is just another generic kinase docking story.",
        "answer": "We frame the packet around mutant/wild-type comparison and state-selective geometry, not generic hinge-binding rank alone.",
    },
    "STK17B (DRAK2)": {
        "headline": "Dark-kinase packet for STK17B built around dynamic P-loop control and probe-benchmarked validation.",
        "objection": "Dark kinase work is too ambiguous without a trusted benchmark.",
        "answer": "The packet is benchmarked against the open probe/negative-control ecosystem, so the first readout is relative to a known public reference frame.",
    },
    "CA IX": {
        "headline": "Condition-aware CA IX packet tuned to acidic tumor-like buffer rather than neutral-condition rank alone.",
        "objection": "This will just rediscover nonselective carbonic anhydrase inhibitors.",
        "answer": "The first assay is run under acidic buffer with explicit CA II/CA XII counterscreens, so the value proposition is condition-specific selectivity, not generic CA binding.",
    },
    "SARS-CoV-2 PLpro": {
        "headline": "PLpro validation packet centered on dynamic shallow-pocket capture with immediate host-like counterscreens.",
        "objection": "PLpro hits often fail because they look like sticky host-reactive cysteine-protease chemistry.",
        "answer": "The first stack includes host-like counterscreens and shallow-pocket-specific triage, so the packet is designed to answer that objection up front.",
    },
    "SARS-CoV-2 Mpro": {
        "headline": "Fast Mpro micro-validation packet that turns a crowded target into a low-friction proof engine.",
        "objection": "Mpro is too crowded to be interesting.",
        "answer": "We use Mpro as the cheapest antiviral proof rail: fast yes/no validation, explicit controls, and a dynamics/selectivity story rather than generic rediscovery.",
    },
    "Leishmania braziliensis DHODH": {
        "headline": "Neglected-disease DHODH packet with early host-enzyme separation instead of expensive late-stage deselection.",
        "objection": "DHODH campaigns can collapse if host-enzyme separation comes too late.",
        "answer": "The packet starts with parasite and host-enzyme separation as part of the first assay stack, so the external lab is not asked to absorb that risk blindly.",
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


def build_payload(portfolio: dict[str, Any], blueprint: dict[str, Any], outreach: dict[str, Any]) -> dict[str, Any]:
    blueprint_rows = {row["target_id"]: row for row in blueprint.get("rows", []) or []}
    outreach_rows = outreach.get("rows", []) or []
    rows: list[dict[str, Any]] = []
    for row in portfolio.get("rows", []) or []:
        if row.get("wave") != "Wave 1":
            continue
        target_id = str(row["target_id"])
        preset = BRIEF_PRESETS[target_id]
        partner_track = next((track["track_label"] for track in outreach_rows if target_id in str(track.get("best_targets", ""))), row["partner_rail"])
        bp = blueprint_rows[target_id]
        rows.append(
            {
                "target_id": target_id,
                "partner_track": partner_track,
                "headline": preset["headline"],
                "first_assay": bp["first_assay"],
                "anti_target_panel": bp["anti_target_panel"],
                "main_objection": preset["objection"],
                "answer_to_objection": preset["answer"],
                "repurposing_slots_required": 3,
                "novelty_slots_required": 3,
                "status": "ready_for_target_specific_fill",
            }
        )
    summary = {
        "status": "wetlab_wave1_one_page_briefs_ready",
        "row_count": len(rows),
        "next_required_step": "For each Wave 1 row, fill the six compound slots from the workbook, then expand this starter brief into the exact first-contact packet for the matching partner track.",
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Wet-Lab Wave 1 One-Page Brief Starters",
        "",
        f"- status: `{s['status']}`",
        f"- row_count: `{s['row_count']}`",
        "",
        "| target_id | partner_track | headline | first_assay | anti_target_panel | status |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['partner_track']}` | {row['headline']} | {row['first_assay']} | {row['anti_target_panel']} | `{row['status']}` |"
        )
    lines.extend(["", "## Objections", ""])
    for row in payload["rows"]:
        lines.extend([
            f"- `{row['target_id']}` objection: {row['main_objection']}",
            f"  Answer: {row['answer_to_objection']}",
        ])
    lines.extend(["", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the Wave 1 one-page brief starter rows.")
    parser.add_argument("--portfolio-json", default=DEFAULT_PORTFOLIO_JSON)
    parser.add_argument("--blueprint-json", default=DEFAULT_BLUEPRINT_JSON)
    parser.add_argument("--outreach-json", default=DEFAULT_OUTREACH_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.portfolio_json),
        _load_json(args.blueprint_json),
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
