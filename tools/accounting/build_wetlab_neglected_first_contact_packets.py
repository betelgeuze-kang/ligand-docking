#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIRST_CONTACT_BUNDLE_JSON = "runs/wetlab_first_contact_brief_bundle_current.json"
DEFAULT_REPURPOSING_FILL_JSON = "runs/wetlab_next3_repurposing_fill_map_current.json"
DEFAULT_NOVELTY_FILL_JSON = "runs/wetlab_next3_novelty_fill_map_current.json"
DEFAULT_LBDHODH_REPURPOSING_FILL_JSON = "runs/wetlab_lbdhodh_repurposing_fill_map_current.json"
DEFAULT_LBDHODH_NOVELTY_FILL_JSON = "runs/wetlab_lbdhodh_novelty_fill_map_current.json"
DEFAULT_OUT_JSON = "runs/wetlab_neglected_first_contact_packets_current.json"
DEFAULT_OUT_CSV = "runs/wetlab_neglected_first_contact_packets_current.csv"
DEFAULT_OUT_MD = "runs/wetlab_neglected_first_contact_packets_current.md"

ROWS: list[dict[str, Any]] = [
    {
        "target_id": "T. cruzi PDE",
        "partner_track_id": "DNDi_IPK",
        "one_page_headline": "Cheap Chagas enzyme validation with parasite-vs-human selectivity built into the first packet.",
        "why_now": (
            "DNDi already has an official Chagas PDE lead-identification rail, so this target can be positioned as a "
            "mission-aligned micro-validation rather than a cold-start collaboration ask."
        ),
        "first_assay": (
            "recombinant parasite PDE inhibition assay plus immediate human PDE mini-panel counterscreen, followed by "
            "orthogonal thermal or secondary biochemical confirmation"
        ),
        "anti_target_panel": "human PDE family mini-panel plus simple mammalian cytotoxicity sanity check",
        "first_packet_goal": (
            "Show parasite PDE signal with early human PDE separation on top-3 repurposing and top-3 novelty "
            "candidates before any broader assay burden is requested."
        ),
        "main_external_objection": "How do we know this is not just another broad human PDE hit list?",
        "objection_answer": (
            "The first packet makes selectivity part of the day-one assay stack, so the external lab is not being asked "
            "to absorb avoidable anti-target risk."
        ),
        "source_anchor": "DNDi Chagas PDE project",
        "source_url": "https://dndi.org/news/2026/dndi-welcomes-ghit-support-lead-identification-novel-chemical-series-eisai-led-chagas-project/",
    },
    {
        "target_id": "Cruzain",
        "partner_track_id": "DNDi_IPK",
        "one_page_headline": "Low-friction Chagas protease validation with desolvation-aware triage and built-in false-positive filtering.",
        "why_now": (
            "Cruzain sits on the same DNDi/IPK neglected-disease rail as the PDE program but offers an even cheaper "
            "fluorogenic protease entry point for a partner lab willing to validate a filtered shortlist fast."
        ),
        "first_assay": (
            "fluorogenic Cruzain assay followed by host cysteine protease counterscreen and thiol-reactivity or "
            "aggregation sanity checks"
        ),
        "anti_target_panel": "host cysteine protease mini-panel plus thiol-reactivity and aggregation filters",
        "first_packet_goal": (
            "Demonstrate clean Cruzain inhibition without broad reactive noise, using a shortlist that already carries "
            "host-protease and artifact filters."
        ),
        "main_external_objection": "Protease hit lists are usually dominated by reactive artifacts and generic cysteine noise.",
        "objection_answer": (
            "This packet starts with host protease, reactivity, and aggregation filters, so the lab receives cleaned "
            "triage candidates instead of a raw fluorogenic false-positive set."
        ),
        "source_anchor": "Institut Pasteur Korea DNDi Chagas screening lane",
        "source_url": "https://www.ip-korea.org/impact/service.php",
    },
    {
        "target_id": "Leishmania braziliensis DHODH",
        "partner_track_id": "DNDi_IPK",
        "one_page_headline": "Neglected-disease enzyme packet that keeps host DHODH separation visible from the first wet-lab pass.",
        "why_now": (
            "DNDi has already highlighted LbDHODH as a validated leishmaniasis enzyme target, giving us a mission-fit "
            "neglected-disease packet with a tractable recombinant assay path."
        ),
        "first_assay": (
            "recombinant L. braziliensis DHODH inhibition assay followed by host DHODH counterscreen and orthogonal "
            "enzyme-format confirmation"
        ),
        "anti_target_panel": "host DHODH counterscreen plus basic cell-viability sanity check",
        "first_packet_goal": (
            "Show parasite-enzyme signal with immediate host-enzyme separation, using repurposing as a cheap triage "
            "lane and novelty chemistry as the stronger primary story."
        ),
        "main_external_objection": "This can look like a niche medicinal-chemistry project because the repurposing lane is thin.",
        "objection_answer": (
            "The packet is framed as a low-friction neglected-enzyme validation story with explicit host-enzyme "
            "separation, not as a claim that repurposing alone will solve the program."
        ),
        "source_anchor": "DNDi LbDHODH target-validation article",
        "source_url": "https://dndi.org/scientific-articles/2025/barbituric-acid-derivatives-as-covalent-inhibitors-of-leishmania-braziliensis-dihydroorotate-dehydrogenase/",
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


def _load_json(path_like: str) -> dict[str, Any]:
    with _resolve(path_like).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _rows_by_target(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("target_id", "")): dict(row)
        for row in payload.get("rows", []) or []
        if str(row.get("target_id", ""))
    }


def build_payload(
    first_contact_bundle: dict[str, Any] | None = None,
    repurposing_fill: dict[str, Any] | None = None,
    novelty_fill: dict[str, Any] | None = None,
    lbdhodh_repurposing_fill: dict[str, Any] | None = None,
    lbdhodh_novelty_fill: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rows = [dict(row) for row in ROWS]
    bundle_rows = _rows_by_target(first_contact_bundle or {})
    repurposing_rows_by_target: dict[str, list[dict[str, Any]]] = {}
    for row in (repurposing_fill or {}).get("rows", []) or []:
        target_id = str(row.get("target_id", "")).strip()
        if target_id:
            repurposing_rows_by_target.setdefault(target_id, []).append(dict(row))
    for row in (lbdhodh_repurposing_fill or {}).get("rows", []) or []:
        target_id = str(row.get("target_id", "")).strip()
        if target_id:
            repurposing_rows_by_target.setdefault(target_id, []).append(dict(row))
    novelty_rows_by_target: dict[str, list[dict[str, Any]]] = {}
    for row in (novelty_fill or {}).get("rows", []) or []:
        target_id = str(row.get("target_id", "")).strip()
        if target_id:
            novelty_rows_by_target.setdefault(target_id, []).append(dict(row))
    for row in (lbdhodh_novelty_fill or {}).get("rows", []) or []:
        target_id = str(row.get("target_id", "")).strip()
        if target_id:
            novelty_rows_by_target.setdefault(target_id, []).append(dict(row))

    export_ready_count = 0
    for row in rows:
        target_id = str(row["target_id"])
        bundle_row = bundle_rows.get(target_id, {})
        row["repurposing_fill_status"] = bundle_row.get("repurposing_fill_status", "repurposing_pending")
        row["repurposing_compounds"] = bundle_row.get("repurposing_compounds", "")
        row["repurposing_fill_artifact"] = bundle_row.get("repurposing_fill_artifact", "")
        target_repurposing = sorted(repurposing_rows_by_target.get(target_id, []), key=lambda item: int(item.get("slot_rank", 0) or 0))
        if not row["repurposing_compounds"] and target_repurposing:
            row["repurposing_fill_status"] = (
                "priority3_repurposing_seed_fill_bound"
                if target_id == "T. cruzi PDE"
                else "lbdhodh_repurposing_seed_fill_bound"
                if target_id == "Leishmania braziliensis DHODH"
                else "next3_repurposing_seed_fill_bound"
            )
            row["repurposing_fill_artifact"] = (
                "runs/wetlab_priority3_repurposing_fill_map_current.md"
                if target_id == "T. cruzi PDE"
                else "runs/wetlab_lbdhodh_repurposing_fill_map_current.md"
                if target_id == "Leishmania braziliensis DHODH"
                else "runs/wetlab_next3_repurposing_fill_map_current.md"
            )
            row["repurposing_compounds"] = "; ".join(item["compound_name"] for item in target_repurposing)
        row["novelty_fill_status"] = bundle_row.get("novelty_fill_status", "novelty_pending")
        row["novelty_compounds"] = bundle_row.get("novelty_compounds", "")
        if bundle_row.get("novelty_fill_artifact"):
            row["novelty_fill_artifact"] = bundle_row["novelty_fill_artifact"]
        target_novelty = sorted(novelty_rows_by_target.get(target_id, []), key=lambda item: int(item.get("slot_rank", 0) or 0))
        if target_novelty:
            row["novelty_fill_status"] = (
                "priority3_novelty_seed_fill_bound"
                if target_id == "T. cruzi PDE"
                else "lbdhodh_novelty_seed_fill_bound"
                if target_id == "Leishmania braziliensis DHODH"
                else "next3_novelty_seed_fill_bound"
            )
            row["novelty_fill_artifact"] = (
                "runs/wetlab_priority3_novelty_fill_map_current.md"
                if target_id == "T. cruzi PDE"
                else "runs/wetlab_lbdhodh_novelty_fill_map_current.md"
                if target_id == "Leishmania braziliensis DHODH"
                else "runs/wetlab_next3_novelty_fill_map_current.md"
            )
            row["novelty_compounds"] = "; ".join(item["novelty_compound_name"] for item in target_novelty)
        row["status"] = (
            "ready_for_outbound_send"
            if row["repurposing_compounds"] and row["novelty_compounds"]
            else "awaiting_compound_fill"
        )
        if row["status"] == "ready_for_outbound_send":
            export_ready_count += 1

    return {
        "summary": {
            "status": "wetlab_neglected_first_contact_packets_ready",
            "target_count": len(rows),
            "partner_track_id": "DNDi_IPK",
            "export_ready_count": export_ready_count,
            "source_artifacts": (
                "runs/wetlab_neglected_wave1_rows_current.md; "
                "runs/wetlab_first_contact_brief_bundle_current.md; "
                "runs/wetlab_priority3_novelty_fill_map_current.md; "
                "runs/wetlab_next3_repurposing_fill_map_current.md; "
                "runs/wetlab_next3_novelty_fill_map_current.md; "
                "runs/wetlab_lbdhodh_repurposing_fill_map_current.md; "
                "runs/wetlab_lbdhodh_novelty_fill_map_current.md; "
                "runs/wetlab_partner_outreach_tracks_current.md"
            ),
            "next_required_step": (
                "Route the T. cruzi PDE plus Cruzain DNDi/IPK first-contact packet now, then treat LbDHODH as the neglected-enzyme follow-on once the first Chagas packet is scoped."
            ),
        },
        "rows": rows,
    }


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# Wet-Lab Neglected-Disease First-Contact Packets",
        "",
        f"- status: `{summary['status']}`",
        f"- target_count: `{summary['target_count']}`",
        f"- partner_track_id: `{summary['partner_track_id']}`",
        f"- export_ready_count: `{summary['export_ready_count']}`",
        f"- source_artifacts: `{summary['source_artifacts']}`",
        "",
    ]
    for row in payload["rows"]:
        lines.extend([
            f"## {row['target_id']}",
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
            f"- repurposing_fill_status: `{row['repurposing_fill_status']}`",
            f"- repurposing_compounds: `{row['repurposing_compounds']}`",
            f"- novelty_fill_status: `{row['novelty_fill_status']}`",
            f"- novelty_compounds: `{row['novelty_compounds']}`",
            f"- status: `{row['status']}`",
            "",
        ])
        if row.get("repurposing_fill_artifact"):
            lines.append(f"- repurposing_fill_artifact: `{row['repurposing_fill_artifact']}`")
        if row.get("novelty_fill_artifact"):
            lines.append(f"- novelty_fill_artifact: `{row['novelty_fill_artifact']}`")
        lines.append("")
    lines.extend(["## Next Step", "", f"- {summary['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build DNDi/IPK neglected-disease first-contact packet rows.")
    parser.add_argument("--first-contact-bundle-json", default=DEFAULT_FIRST_CONTACT_BUNDLE_JSON)
    parser.add_argument("--repurposing-fill-json", default=DEFAULT_REPURPOSING_FILL_JSON)
    parser.add_argument("--novelty-fill-json", default=DEFAULT_NOVELTY_FILL_JSON)
    parser.add_argument("--lbdhodh-repurposing-fill-json", default=DEFAULT_LBDHODH_REPURPOSING_FILL_JSON)
    parser.add_argument("--lbdhodh-novelty-fill-json", default=DEFAULT_LBDHODH_NOVELTY_FILL_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.first_contact_bundle_json),
        _load_json(args.repurposing_fill_json),
        _load_json(args.novelty_fill_json),
        _load_json(args.lbdhodh_repurposing_fill_json),
        _load_json(args.lbdhodh_novelty_fill_json),
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
