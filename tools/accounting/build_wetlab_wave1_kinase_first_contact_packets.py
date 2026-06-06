#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_KINASE_RAIL_JSON = "runs/wetlab_wave1_kinase_rail_packets_current.json"
DEFAULT_FIRST_CONTACT_BUNDLE_JSON = "runs/wetlab_first_contact_brief_bundle_current.json"
DEFAULT_SCHEMA_JSON = "runs/wetlab_one_page_brief_schema_current.json"
DEFAULT_OUTREACH_JSON = "runs/wetlab_partner_outreach_tracks_current.json"
DEFAULT_NEXT3_REPURPOSING_FILL_JSON = "runs/wetlab_next3_repurposing_fill_map_current.json"
DEFAULT_NEXT3_NOVELTY_FILL_JSON = "runs/wetlab_next3_novelty_fill_map_current.json"
DEFAULT_STK17B_REPURPOSING_FILL_JSON = "runs/wetlab_stk17b_repurposing_fill_map_current.json"
DEFAULT_STK17B_NOVELTY_FILL_JSON = "runs/wetlab_stk17b_novelty_fill_map_current.json"
DEFAULT_OUT_JSON = "runs/wetlab_wave1_kinase_first_contact_packets_current.json"
DEFAULT_OUT_CSV = "runs/wetlab_wave1_kinase_first_contact_packets_current.csv"
DEFAULT_OUT_MD = "runs/wetlab_wave1_kinase_first_contact_packets_current.md"

TARGET_PRESETS: dict[str, dict[str, str]] = {
    "ALK2": {
        "why_now": "M4K already gives this target a rare-disease open-science rail with public structure and chemistry context, so the external ask can stay small: a cheap mutant-aware biochemical or DSF validation instead of a full kinase campaign.",
        "first_packet_goal": "Show a clean ALK2 engagement signal that survives mutant or wild-type comparison and an ALK-family mini-panel before asking for any broader cell or medicinal-chemistry work.",
    },
    "STK17B (DRAK2)": {
        "why_now": "STK17B already comes with a published PKIS benchmark trio, the 11-series open probe frame, and a concrete P-loop story, so the partner lab can run an open-set benchmark instead of starting from dark-kinase ambiguity.",
        "first_packet_goal": "Show DSF or biochemical signal that orders the PKIS and 11-series benchmark set coherently and still survives a neighborhood dark-kinase counterscreen before any deeper biology claim.",
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
    kinase_rail: dict[str, Any],
    first_contact_bundle: dict[str, Any],
    schema: dict[str, Any],
    outreach: dict[str, Any],
    repurposing_fill: dict[str, Any] | None = None,
    novelty_fill: dict[str, Any] | None = None,
    stk17b_repurposing_fill: dict[str, Any] | None = None,
    stk17b_novelty_fill: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rail_rows = _rows_by_target(kinase_rail)
    outreach_rows = _rows_by_track(outreach)
    bundle_summary = dict(first_contact_bundle.get("summary", {}) or {})
    schema_summary = dict(schema.get("summary", {}) or {})
    repurposing_rows = _group_rows_by_target(repurposing_fill or {})
    for target_id, rows_for_target in _group_rows_by_target(stk17b_repurposing_fill or {}).items():
        repurposing_rows.setdefault(target_id, []).extend(rows_for_target)
    novelty_rows = _group_rows_by_target(novelty_fill or {})
    for target_id, rows_for_target in _group_rows_by_target(stk17b_novelty_fill or {}).items():
        novelty_rows.setdefault(target_id, []).extend(rows_for_target)

    rows: list[dict[str, Any]] = []
    export_ready_count = 0
    for target_id in ("ALK2", "STK17B (DRAK2)"):
        rail = rail_rows[target_id]
        preset = TARGET_PRESETS[target_id]
        track = outreach_rows[rail["partner_track_id"]]
        target_repurposing = sorted(repurposing_rows.get(target_id, []), key=lambda item: int(item.get("slot_rank", 0) or 0))
        target_novelty = sorted(novelty_rows.get(target_id, []), key=lambda item: int(item.get("slot_rank", 0) or 0))
        row = {
            "target_id": target_id,
            "partner_track_id": rail["partner_track_id"],
            "one_page_headline": rail["one_page_brief_headline"],
            "why_now": preset["why_now"],
            "first_assay": rail["first_assay_stack"],
            "anti_target_panel": rail["selectivity_anti_target_panel"],
            "first_packet_goal": preset["first_packet_goal"],
            "main_external_objection": rail["main_external_lab_objection"],
            "objection_answer": rail["objection_answer"],
            "source_anchor": rail["source_anchor_1_label"],
            "source_url": rail["source_anchor_1_url"],
            "track_label": track["track_label"],
            "pitch_angle": track["pitch_angle"],
            "what_to_send_first": track["what_to_send_first"],
            "offer_model": track["offer_model"],
            "repurposing_fill_status": "repurposing_pending",
            "repurposing_compounds": "",
            "novelty_fill_status": "novelty_pending",
            "novelty_compounds": "",
            "status": "ready_for_first_contact_fill",
        }
        if target_repurposing:
            row["repurposing_fill_status"] = "next3_repurposing_seed_fill_bound"
            row["repurposing_fill_artifact"] = "runs/wetlab_next3_repurposing_fill_map_current.md"
            row["repurposing_compounds"] = "; ".join(item["compound_name"] for item in target_repurposing)
        if target_novelty:
            row["novelty_fill_status"] = "next3_novelty_seed_fill_bound"
            row["novelty_fill_artifact"] = "runs/wetlab_next3_novelty_fill_map_current.md"
            row["novelty_compounds"] = "; ".join(item["novelty_compound_name"] for item in target_novelty)
        if row["repurposing_compounds"] and row["novelty_compounds"]:
            row["status"] = "ready_for_partner_specific_export"
            export_ready_count += 1
        rows.append(row)

    if export_ready_count == len(rows):
        next_required_step = "Export both ALK2 and STK17B kinase rows now that the repurposing, novelty, and benchmark-control lanes are bound."
    else:
        next_required_step = "Export the ALK2 row now that its repurposing and novelty lanes are bound, and keep STK17B on the same packet frame until its compounds are filled."

    summary = {
        "status": "wetlab_wave1_kinase_first_contact_packets_ready",
        "row_count": len(rows),
        "export_ready_count": export_ready_count,
        "schema_summary_field_count": int(schema_summary.get("summary_field_count", 0) or 0),
        "bundle_style_anchor_status": str(bundle_summary.get("status", "")),
        "track_scope": "M4K_open_science + SGC_dark_kinase",
        "next_required_step": next_required_step,
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Wet-Lab Wave 1 Kinase First Contact Packets",
        "",
        f"- status: `{s['status']}`",
        f"- row_count: `{s['row_count']}`",
        f"- schema_summary_field_count: `{s['schema_summary_field_count']}`",
        f"- bundle_style_anchor_status: `{s['bundle_style_anchor_status']}`",
        f"- track_scope: `{s['track_scope']}`",
        "",
        "| target_id | partner_track_id | one_page_headline | first_assay | anti_target_panel | status |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['partner_track_id']}` | {row['one_page_headline']} | {row['first_assay']} | {row['anti_target_panel']} | `{row['status']}` |"
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
                f"- source_anchor: [{row['source_anchor']}]({row['source_url']})",
                f"- track_label: `{row['track_label']}`",
                f"- pitch_angle: {row['pitch_angle']}",
                f"- what_to_send_first: {row['what_to_send_first']}",
                f"- offer_model: {row['offer_model']}",
                f"- repurposing_fill_status: `{row['repurposing_fill_status']}`",
                f"- repurposing_compounds: `{row['repurposing_compounds']}`",
                f"- novelty_fill_status: `{row['novelty_fill_status']}`",
                f"- novelty_compounds: `{row['novelty_compounds']}`",
                f"- status: `{row['status']}`",
                "",
            ]
        )
    lines.extend(["## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Wave 1 kinase first-contact packet rows for ALK2 and STK17B.")
    parser.add_argument("--kinase-rail-json", default=DEFAULT_KINASE_RAIL_JSON)
    parser.add_argument("--first-contact-bundle-json", default=DEFAULT_FIRST_CONTACT_BUNDLE_JSON)
    parser.add_argument("--schema-json", default=DEFAULT_SCHEMA_JSON)
    parser.add_argument("--outreach-json", default=DEFAULT_OUTREACH_JSON)
    parser.add_argument("--repurposing-fill-json", default=DEFAULT_NEXT3_REPURPOSING_FILL_JSON)
    parser.add_argument("--novelty-fill-json", default=DEFAULT_NEXT3_NOVELTY_FILL_JSON)
    parser.add_argument("--stk17b-repurposing-fill-json", default=DEFAULT_STK17B_REPURPOSING_FILL_JSON)
    parser.add_argument("--stk17b-novelty-fill-json", default=DEFAULT_STK17B_NOVELTY_FILL_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.kinase_rail_json),
        _load_json(args.first_contact_bundle_json),
        _load_json(args.schema_json),
        _load_json(args.outreach_json),
        _load_json(args.repurposing_fill_json),
        _load_json(args.novelty_fill_json),
        _load_json(args.stk17b_repurposing_fill_json),
        _load_json(args.stk17b_novelty_fill_json),
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
