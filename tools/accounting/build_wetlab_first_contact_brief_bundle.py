#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPURPOSING_FILL_JSON = "runs/wetlab_priority3_repurposing_fill_map_current.json"
DEFAULT_NOVELTY_FILL_JSON = "runs/wetlab_priority3_novelty_fill_map_current.json"
DEFAULT_MPRO_VENDOR_COST_JSON = "runs/wetlab_mpro_vendor_cost_check_current.json"
DEFAULT_OUT_JSON = "runs/wetlab_first_contact_brief_bundle_current.json"
DEFAULT_OUT_CSV = "runs/wetlab_first_contact_brief_bundle_current.csv"
DEFAULT_OUT_MD = "runs/wetlab_first_contact_brief_bundle_current.md"

ROWS: list[dict[str, Any]] = [
    {
        "priority_rank": 1,
        "target_id": "T. cruzi PDE",
        "outreach_track_id": "DNDi_IPK",
        "one_page_headline": "Cheap Chagas enzyme validation with a built-in parasite-vs-human selectivity story.",
        "why_now": "DNDi already has an official Chagas PDE lead-identification rail, so this target can be pitched as a low-friction neglected-disease micro-validation instead of a cold-start collaboration.",
        "first_assay": "recombinant parasite PDE inhibition plus human PDE mini-panel",
        "anti_target_panel": "human PDE family mini-panel",
        "first_packet_goal": "Show parasite PDE signal with early human PDE separation on top-3 repurposing and top-3 novelty compounds.",
        "main_external_objection": "How do we know this is not just another broad human PDE hit list?",
        "objection_answer": "The first packet makes selectivity part of the day-one assay stack instead of a later follow-up, so the external lab is not being asked to shoulder avoidable anti-target risk.",
        "source_anchor": "DNDi Chagas PDE project",
        "source_url": "https://dndi.org/news/2026/dndi-welcomes-ghit-support-lead-identification-novel-chemical-series-eisai-led-chagas-project/",
    },
    {
        "priority_rank": 2,
        "target_id": "CA IX",
        "outreach_track_id": "oncology_condition_aware",
        "one_page_headline": "Assay-conditioned CA IX screening in acidic tumor-like buffer with immediate CA II/CA XII selectivity built in.",
        "why_now": "This is the cleanest demo of the platform's condition-aware branch layer because the biological story and the wet-lab buffer story are the same thing.",
        "first_assay": "CA IX enzyme assay in acidic tumor-like buffer plus CA II and CA XII counterscreen",
        "anti_target_panel": "CA II plus CA XII selectivity panel",
        "first_packet_goal": "Show that the condition-aware packet improves CA IX-biased triage under tumor-like pH while preserving immediate selectivity checks.",
        "main_external_objection": "Why should we believe the pH-conditioned ranking is more useful than a normal CA inhibitor screen?",
        "objection_answer": "The packet is not selling generic CA inhibition; it is selling a tumor-condition-specific assay setup plus explicit CA II/CA XII separation, which gives the wet-lab a sharper yes/no decision than a flat screen.",
        "source_anchor": "CA IX/XII tumor pH review",
        "source_url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC5876008/",
    },
    {
        "priority_rank": 3,
        "target_id": "SARS-CoV-2 Mpro",
        "outreach_track_id": "READDI_Korea",
        "one_page_headline": "Fast, low-friction antiviral protease validation with dynamics-first prioritization and explicit host-protease sanity checks.",
        "why_now": "Mpro offers the fastest cheap protease readout in the whole portfolio and lets us prove the outbound model before asking partners to touch harder shallow-pocket or host-liability targets.",
        "first_assay": "cheap fluorogenic Mpro assay with orthogonal biochemical or thermal confirmation",
        "anti_target_panel": "host cysteine protease sanity panel",
        "first_packet_goal": "Get a fast yes/no on top-3 repurposing and top-3 novelty candidates while filtering out obvious reactive or host-like noise immediately.",
        "main_external_objection": "Why should an external lab care when Mpro is such a crowded target?",
        "objection_answer": "The value is not another generic Mpro hit list; it is a low-cost proof packet for the platform's dynamics-first triage and partner workflow, using a target where the lab can answer quickly.",
        "source_anchor": "COVID Moonshot",
        "source_url": "https://postera.ai/moonshot/",
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


def _maybe_load_json(path_like: str) -> dict[str, Any] | None:
    path = _resolve(path_like)
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _fill_rows_by_target(payload: dict[str, Any] | None) -> dict[str, list[dict[str, Any]]]:
    if not payload:
        return {}
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in payload.get("rows", []) or []:
        target_id = str(row.get("target_id", "")).strip()
        if not target_id:
            continue
        grouped.setdefault(target_id, []).append(dict(row))
    return grouped


def build_payload(
    repurposing_fill: dict[str, Any] | None = None,
    novelty_fill: dict[str, Any] | None = None,
    mpro_vendor_cost: dict[str, Any] | None = None,
) -> dict[str, Any]:
    fill_rows = _fill_rows_by_target(repurposing_fill)
    novelty_rows = _fill_rows_by_target(novelty_fill)
    mpro_vendor_ready = str((mpro_vendor_cost or {}).get("summary", {}).get("status", "")) == "wetlab_mpro_vendor_cost_check_ready"
    rows = [dict(row) for row in ROWS]
    filled_target_count = 0
    novelty_filled_target_count = 0
    for row in rows:
        row["mpro_vendor_cost_check_ready"] = False
        row["mpro_vendor_cost_check_artifact"] = ""
        target_fill = sorted(fill_rows.get(str(row["target_id"])) or [], key=lambda item: int(item.get("slot_rank", 0) or 0))
        target_novelty = sorted(novelty_rows.get(str(row["target_id"])) or [], key=lambda item: int(item.get("slot_rank", 0) or 0))
        if not target_fill:
            row["repurposing_fill_status"] = "repurposing_pending"
            row["repurposing_filled_slot_count"] = 0
        else:
            filled_target_count += 1
            row["repurposing_fill_status"] = "priority3_repurposing_seed_fill_bound"
            row["repurposing_fill_artifact"] = "runs/wetlab_priority3_repurposing_fill_map_current.md"
            row["repurposing_filled_slot_count"] = len(target_fill)
            row["repurposing_compounds"] = "; ".join(fill_row["compound_name"] for fill_row in target_fill)
        if not target_novelty:
            row["novelty_fill_status"] = "novelty_pending"
            row["novelty_filled_slot_count"] = 0
        else:
            novelty_filled_target_count += 1
            row["novelty_fill_status"] = "priority3_novelty_seed_fill_bound"
            row["novelty_fill_artifact"] = "runs/wetlab_priority3_novelty_fill_map_current.md"
            row["novelty_filled_slot_count"] = len(target_novelty)
            row["novelty_compounds"] = "; ".join(fill_row["novelty_compound_name"] for fill_row in target_novelty)
        if row["target_id"] == "SARS-CoV-2 Mpro" and mpro_vendor_ready:
            row["mpro_vendor_cost_check_artifact"] = "runs/wetlab_mpro_vendor_cost_check_current.md"
            row["mpro_vendor_cost_check_ready"] = True
        row["launch_packet_artifact"] = {
            "T. cruzi PDE": "runs/tcruzi_pde_launch_packet_current.md",
            "CA IX": "runs/caix_launch_packet_current.md",
            "SARS-CoV-2 Mpro": "runs/sarscov2_mpro_launch_packet_current.md",
        }[row["target_id"]]

    summary = {
        "status": "wetlab_first_contact_brief_bundle_ready",
        "row_count": len(rows),
        "priority_rule": "Start with one neglected-disease enzyme rail, one condition-aware oncology rail, and one ultra-low-friction antiviral protease rail.",
        "priority3_repurposing_fill_ready_count": filled_target_count,
        "priority3_novelty_fill_ready_count": novelty_filled_target_count,
        "priority3_repurposing_fill_artifact": "runs/wetlab_priority3_repurposing_fill_map_current.md" if filled_target_count else "",
        "priority3_novelty_fill_artifact": "runs/wetlab_priority3_novelty_fill_map_current.md" if novelty_filled_target_count else "",
        "mpro_vendor_cost_check_ready": mpro_vendor_ready,
        "mpro_vendor_cost_check_artifact": "runs/wetlab_mpro_vendor_cost_check_current.md" if mpro_vendor_ready else "",
        "priority3_target_render_split_artifact": "runs/wetlab_priority3_target_render_split_current.md",
        "priority3_protein_run_queue_artifact": "runs/wetlab_priority3_protein_run_queue_current.md",
        "prep_artifact_lane_artifact": "runs/wetlab_prep_artifact_lane_current.md",
        "next_required_step": "Use the render split and the serialized protein run queue to launch Mpro first, then CA IX, then T. cruzi PDE, while partner exports stay frozen and only prep/artifact work runs in parallel.",
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Wet-Lab First Contact Brief Bundle",
        "",
        f"- status: `{s['status']}`",
        f"- row_count: `{s['row_count']}`",
        f"- priority_rule: {s['priority_rule']}",
        f"- priority3_repurposing_fill_ready_count: `{s['priority3_repurposing_fill_ready_count']}`",
        f"- priority3_novelty_fill_ready_count: `{s['priority3_novelty_fill_ready_count']}`",
        "",
        "| priority_rank | target_id | outreach_track_id | repurposing_fill_status | novelty_fill_status | repurposing_filled_slots | novelty_filled_slots | first_assay | anti_target_panel |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    if s["priority3_repurposing_fill_artifact"]:
        lines.insert(5, f"- priority3_repurposing_fill_artifact: `{s['priority3_repurposing_fill_artifact']}`")
    if s["priority3_novelty_fill_artifact"]:
        lines.insert(6, f"- priority3_novelty_fill_artifact: `{s['priority3_novelty_fill_artifact']}`")
    if s["mpro_vendor_cost_check_artifact"]:
        lines.insert(7, f"- mpro_vendor_cost_check_artifact: `{s['mpro_vendor_cost_check_artifact']}`")
    lines.insert(8, f"- priority3_target_render_split_artifact: `{s['priority3_target_render_split_artifact']}`")
    lines.insert(9, f"- priority3_protein_run_queue_artifact: `{s['priority3_protein_run_queue_artifact']}`")
    lines.insert(10, f"- prep_artifact_lane_artifact: `{s['prep_artifact_lane_artifact']}`")
    for row in payload["rows"]:
        lines.append(
            f"| `{row['priority_rank']}` | `{row['target_id']}` | `{row['outreach_track_id']}` | `{row.get('repurposing_fill_status', 'repurposing_pending')}` | `{row.get('novelty_fill_status', 'novelty_pending')}` | `{row.get('repurposing_filled_slot_count', 0)}` | `{row.get('novelty_filled_slot_count', 0)}` | {row['first_assay']} | {row['anti_target_panel']} |"
        )
    lines.extend(["", "## Briefs", ""])
    for row in payload["rows"]:
        lines.extend([
            f"### {row['priority_rank']}. `{row['target_id']}`",
            "",
            f"- one_page_headline: {row['one_page_headline']}",
            f"- why_now: {row['why_now']}",
            f"- first_packet_goal: {row['first_packet_goal']}",
            f"- main_external_objection: {row['main_external_objection']}",
            f"- objection_answer: {row['objection_answer']}",
            f"- source: [{row['source_anchor']}]({row['source_url']})",
        ])
        if row.get("repurposing_fill_status"):
            lines.extend([
                f"- repurposing_fill_status: `{row['repurposing_fill_status']}`",
                f"- repurposing_filled_slot_count: `{row.get('repurposing_filled_slot_count', 0)}`",
                f"- repurposing_fill_artifact: `{row['repurposing_fill_artifact']}`",
                f"- repurposing_compounds: `{row['repurposing_compounds']}`",
                f"- launch_packet_artifact: `{row['launch_packet_artifact']}`",
            ])
        if row.get("novelty_fill_status"):
            lines.extend([
                f"- novelty_fill_status: `{row['novelty_fill_status']}`",
                f"- novelty_filled_slot_count: `{row.get('novelty_filled_slot_count', 0)}`",
            ])
            if row.get("novelty_fill_artifact"):
                lines.append(f"- novelty_fill_artifact: `{row['novelty_fill_artifact']}`")
            if row.get("novelty_compounds"):
                lines.append(f"- novelty_compounds: `{row['novelty_compounds']}`")
        if row.get("mpro_vendor_cost_check_ready"):
            lines.extend(
                [
                    f"- mpro_vendor_cost_check_ready: `{row['mpro_vendor_cost_check_ready']}`",
                    f"- mpro_vendor_cost_check_artifact: `{row['mpro_vendor_cost_check_artifact']}`",
                ]
            )
        lines.append("")
    lines.extend(["## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the first-contact wet-lab brief bundle for the first three external packets.")
    parser.add_argument("--repurposing-fill-json", default=DEFAULT_REPURPOSING_FILL_JSON)
    parser.add_argument("--novelty-fill-json", default=DEFAULT_NOVELTY_FILL_JSON)
    parser.add_argument("--mpro-vendor-cost-json", default=DEFAULT_MPRO_VENDOR_COST_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _maybe_load_json(args.repurposing_fill_json),
        _maybe_load_json(args.novelty_fill_json),
        _maybe_load_json(args.mpro_vendor_cost_json),
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
