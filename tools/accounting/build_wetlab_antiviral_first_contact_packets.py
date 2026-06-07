#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ANTIVIRAL_RAIL_JSON = "runs/wetlab_antiviral_wave1_rail_current.json"
DEFAULT_FIRST_CONTACT_BUNDLE_JSON = "runs/wetlab_first_contact_brief_bundle_current.json"
DEFAULT_OUTREACH_JSON = "runs/wetlab_partner_outreach_tracks_current.json"
DEFAULT_REPURPOSING_FILL_JSON = "runs/wetlab_priority3_repurposing_fill_map_current.json"
DEFAULT_NOVELTY_FILL_JSON = "runs/wetlab_priority3_novelty_fill_map_current.json"
DEFAULT_NEXT3_REPURPOSING_FILL_JSON = "runs/wetlab_next3_repurposing_fill_map_current.json"
DEFAULT_NEXT3_NOVELTY_FILL_JSON = "runs/wetlab_next3_novelty_fill_map_current.json"
DEFAULT_MPRO_VENDOR_COST_CHECK_JSON = "runs/wetlab_mpro_vendor_cost_check_current.json"
DEFAULT_OUT_JSON = "runs/wetlab_antiviral_first_contact_packets_current.json"
DEFAULT_OUT_CSV = "runs/wetlab_antiviral_first_contact_packets_current.csv"
DEFAULT_OUT_MD = "runs/wetlab_antiviral_first_contact_packets_current.md"

TARGET_PRESETS: dict[str, dict[str, str]] = {
    "SARS-CoV-2 PLpro": {
        "why_now": (
            "READDI already frames coronavirus antivirals as a rapid micro-validation collaboration problem, and PLpro is the "
            "most natural second step after Mpro because it tests whether the partner will trust our shallow-pocket and host-liability filters, "
            "not just a cheap protease assay."
        ),
        "first_packet_goal": (
            "Show that the top-3 repurposing and top-3 novelty shortlist can produce a real PLpro signal while surviving a human-DUB-first "
            "counterscreen and at least one in-cell follow-up path."
        ),
    },
    "SARS-CoV-2 Mpro": {
        "why_now": (
            "Mpro remains the fastest low-friction coronavirus protease proof rail in the portfolio, so it is the right lead packet for READDI_Korea "
            "to validate our outbound workflow before they spend effort on host-liability-heavier antiviral targets."
        ),
        "first_packet_goal": (
            "Get a fast yes-or-no on top-3 repurposing and top-3 novelty candidates in the cheapest serious coronavirus assay stack, while filtering "
            "host cysteine-protease and generic reactivity noise immediately."
        ),
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


def _group_rows_by_target(payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in payload.get("rows", []) or []:
        target_id = str(row.get("target_id", "")).strip()
        if not target_id:
            continue
        grouped.setdefault(target_id, []).append(dict(row))
    return grouped


def build_payload(
    antiviral_rail: dict[str, Any],
    first_contact_bundle: dict[str, Any],
    outreach: dict[str, Any],
    repurposing_fill: dict[str, Any] | None = None,
    novelty_fill: dict[str, Any] | None = None,
    next3_repurposing_fill: dict[str, Any] | None = None,
    next3_novelty_fill: dict[str, Any] | None = None,
    mpro_vendor_cost_check: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rail_rows = _rows_by_target(antiviral_rail)
    outreach_rows = _rows_by_track(outreach)
    bundle_rows = _rows_by_target(first_contact_bundle)
    bundle_summary = dict(first_contact_bundle.get("summary", {}) or {})
    repurposing_rows = _group_rows_by_target(repurposing_fill or {})
    for target_id, target_rows in _group_rows_by_target(next3_repurposing_fill or {}).items():
        repurposing_rows.setdefault(target_id, []).extend(target_rows)
    novelty_rows = _group_rows_by_target(novelty_fill or {})
    for target_id, target_rows in _group_rows_by_target(next3_novelty_fill or {}).items():
        novelty_rows.setdefault(target_id, []).extend(target_rows)
    vendor_rows = {
        str(row.get("compound_name", "")).strip(): dict(row)
        for row in (mpro_vendor_cost_check or {}).get("rows", []) or []
        if str(row.get("compound_name", "")).strip()
    }

    rows: list[dict[str, Any]] = []
    export_ready_count = 0
    for target_id in ("SARS-CoV-2 PLpro", "SARS-CoV-2 Mpro"):
        rail = rail_rows[target_id]
        track = outreach_rows[rail["partner_track_id"]]
        preset = TARGET_PRESETS[target_id]
        bundle_row = bundle_rows.get(target_id, {})

        row = {
            "target_id": target_id,
            "partner_track_id": rail["partner_track_id"],
            "one_page_headline": rail["one_page_brief_headline"],
            "why_now": bundle_row.get("why_now") or preset["why_now"],
            "first_assay": rail["first_assay_stack"],
            "anti_target_panel": rail["host_off_target_counterscreens"],
            "first_packet_goal": bundle_row.get("first_packet_goal") or preset["first_packet_goal"],
            "main_external_objection": rail["main_external_lab_objection"],
            "objection_answer": rail["objection_answer"],
            "source_anchor": rail["open_science_source_label"],
            "source_url": rail["open_science_source_url"],
            "track_label": track["track_label"],
            "offer_model": track["offer_model"],
            "what_to_send_first": track["what_to_send_first"],
            "repurposing_fill_status": bundle_row.get("repurposing_fill_status", "repurposing_pending"),
            "repurposing_compounds": bundle_row.get("repurposing_compounds", ""),
            "novelty_fill_status": bundle_row.get("novelty_fill_status", "novelty_pending"),
            "novelty_compounds": bundle_row.get("novelty_compounds", ""),
            "status": "awaiting_compound_fill",
        }
        if not row["repurposing_compounds"] and target_id in repurposing_rows:
            ordered_repurposing = sorted(
                repurposing_rows[target_id],
                key=lambda item: int(item.get("slot_rank", 0) or 0),
            )
            row["repurposing_fill_status"] = (
                "priority3_repurposing_seed_fill_bound"
                if target_id == "SARS-CoV-2 Mpro"
                else "next3_repurposing_seed_fill_bound"
            )
            row["repurposing_compounds"] = "; ".join(item["compound_name"] for item in ordered_repurposing)
            row["repurposing_fill_artifact"] = (
                "runs/wetlab_priority3_repurposing_fill_map_current.md"
                if target_id == "SARS-CoV-2 Mpro"
                else "runs/wetlab_next3_repurposing_fill_map_current.md"
            )
        if bundle_row.get("repurposing_fill_artifact"):
            row["repurposing_fill_artifact"] = bundle_row["repurposing_fill_artifact"]
        if not row["novelty_compounds"] and target_id in novelty_rows:
            ordered_novelty = sorted(
                novelty_rows[target_id],
                key=lambda item: int(item.get("slot_rank", 0) or 0),
            )
            row["novelty_fill_status"] = (
                "priority3_novelty_seed_fill_bound"
                if target_id == "SARS-CoV-2 Mpro"
                else "next3_novelty_seed_fill_bound"
            )
            row["novelty_compounds"] = "; ".join(item["novelty_compound_name"] for item in ordered_novelty)
            row["novelty_fill_artifact"] = (
                "runs/wetlab_priority3_novelty_fill_map_current.md"
                if target_id == "SARS-CoV-2 Mpro"
                else "runs/wetlab_next3_novelty_fill_map_current.md"
            )
        if bundle_row.get("novelty_fill_artifact"):
            row["novelty_fill_artifact"] = bundle_row["novelty_fill_artifact"]
        if target_id == "SARS-CoV-2 Mpro" and vendor_rows:
            row["mpro_vendor_cost_check_artifact"] = "runs/wetlab_mpro_vendor_cost_check_current.md"
            row["vendor_cost_summary"] = "; ".join(
                f"{name}: {item['procurement_action']} at {item['listed_currency']} {item['listed_price']} / {item['listed_pack_size']}"
                for name, item in vendor_rows.items()
            )
        if (
            target_id == "SARS-CoV-2 Mpro"
            and row["repurposing_fill_status"] == "priority3_repurposing_seed_fill_bound"
            and row["novelty_fill_status"] == "priority3_novelty_seed_fill_bound"
            and vendor_rows
        ):
            row["status"] = "ready_for_outbound_send"
            export_ready_count += 1
        elif (
            target_id == "SARS-CoV-2 PLpro"
            and row["repurposing_compounds"]
            and row["novelty_compounds"]
        ):
            row["status"] = "ready_for_outbound_send"
            export_ready_count += 1
        elif target_id == "SARS-CoV-2 PLpro":
            row["status"] = "awaiting_compound_fill"
        rows.append(row)

    summary = {
        "status": "wetlab_antiviral_first_contact_packets_ready",
        "row_count": len(rows),
        "partner_track_id": "READDI_Korea",
        "bundle_style_anchor_status": str(bundle_summary.get("status", "")),
        "mpro_vendor_cost_check_ready": bool(vendor_rows),
        "export_ready_count": export_ready_count,
        "source_artifacts": (
            "runs/wetlab_antiviral_wave1_rail_current.md; "
            "runs/wetlab_first_contact_brief_bundle_current.md; "
            "runs/wetlab_mpro_vendor_cost_check_current.md; "
            "runs/wetlab_partner_outreach_tracks_current.md"
        ),
        "next_required_step": "Route the Mpro-enriched READDI packet now with the vendor/cost sheet attached, then finish the PLpro novelty lane.",
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# Wet-Lab Antiviral First Contact Packets",
        "",
        f"- status: `{summary['status']}`",
        f"- row_count: `{summary['row_count']}`",
        f"- partner_track_id: `{summary['partner_track_id']}`",
        f"- bundle_style_anchor_status: `{summary['bundle_style_anchor_status']}`",
        f"- mpro_vendor_cost_check_ready: `{summary['mpro_vendor_cost_check_ready']}`",
        f"- export_ready_count: `{summary['export_ready_count']}`",
        f"- source_artifacts: `{summary['source_artifacts']}`",
        "",
        "| target_id | partner_track_id | first_assay | repurposing_fill_status | novelty_fill_status | status |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['partner_track_id']}` | {row['first_assay']} | `{row['repurposing_fill_status']}` | `{row['novelty_fill_status']}` | `{row['status']}` |"
        )
    lines.extend(["", "## Packets", ""])
    for row in payload["rows"]:
        lines.extend(
            [
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
                f"- track_label: `{row['track_label']}`",
                f"- offer_model: {row['offer_model']}",
                f"- what_to_send_first: {row['what_to_send_first']}",
                f"- repurposing_fill_status: `{row['repurposing_fill_status']}`",
                f"- repurposing_compounds: `{row['repurposing_compounds']}`",
                f"- novelty_fill_status: `{row['novelty_fill_status']}`",
                f"- novelty_compounds: `{row['novelty_compounds']}`",
                f"- status: `{row['status']}`",
                "",
            ]
        )
        if row.get("mpro_vendor_cost_check_artifact"):
            lines.extend(
                [
                    f"- mpro_vendor_cost_check_artifact: `{row['mpro_vendor_cost_check_artifact']}`",
                    f"- vendor_cost_summary: {row['vendor_cost_summary']}",
                    "",
                ]
            )
    lines.extend(["## Next Step", "", f"- {summary['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build READDI_Korea antiviral first-contact packet rows for PLpro and Mpro.")
    parser.add_argument("--antiviral-rail-json", default=DEFAULT_ANTIVIRAL_RAIL_JSON)
    parser.add_argument("--first-contact-bundle-json", default=DEFAULT_FIRST_CONTACT_BUNDLE_JSON)
    parser.add_argument("--outreach-json", default=DEFAULT_OUTREACH_JSON)
    parser.add_argument("--repurposing-fill-json", default=DEFAULT_REPURPOSING_FILL_JSON)
    parser.add_argument("--novelty-fill-json", default=DEFAULT_NOVELTY_FILL_JSON)
    parser.add_argument("--next3-repurposing-fill-json", default=DEFAULT_NEXT3_REPURPOSING_FILL_JSON)
    parser.add_argument("--next3-novelty-fill-json", default=DEFAULT_NEXT3_NOVELTY_FILL_JSON)
    parser.add_argument("--mpro-vendor-cost-check-json", default=DEFAULT_MPRO_VENDOR_COST_CHECK_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.antiviral_rail_json),
        _load_json(args.first_contact_bundle_json),
        _load_json(args.outreach_json),
        _load_json(args.repurposing_fill_json),
        _load_json(args.novelty_fill_json),
        _load_json(args.next3_repurposing_fill_json),
        _load_json(args.next3_novelty_fill_json),
        _load_json(args.mpro_vendor_cost_check_json),
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
