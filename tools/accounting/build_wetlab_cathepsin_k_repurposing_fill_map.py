#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.wetlab_target_render_utils import materialize_repurposing_rows, maybe_load_json

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BRIEF_FILL_QUEUE_JSON = "runs/wetlab_wave2_brief_fill_queue_current.json"
DEFAULT_PACKET_QUEUE_JSON = "runs/wetlab_wave2_packet_queue_current.json"
DEFAULT_OUT_JSON = "runs/wetlab_cathepsin_k_repurposing_fill_map_current.json"
DEFAULT_OUT_CSV = "runs/wetlab_cathepsin_k_repurposing_fill_map_current.csv"
DEFAULT_OUT_MD = "runs/wetlab_cathepsin_k_repurposing_fill_map_current.md"
DEFAULT_BROAD_SCREEN_AUTOFILL_JSON = "runs/wetlab_broad_screen_repurposing_autofill_current.json"
DEFAULT_TARGET_BRIEF_ARTIFACT = "runs/wetlab_target_brief_cathepsin_k_current.md"
DEFAULT_TRACK_LABEL = "acidic protease condition-aware rail"
FIRST_CONTACT_PACKET_ARTIFACT = "runs/cathepsin_k_launch_packet_current.md"

ROW_SPECS: list[dict[str, Any]] = [
    {
        "priority_rank": 9,
        "target_id": "Cathepsin K",
        "outreach_track_id": "acidic_protease_wave2",
        "slot_rank": 1,
        "compound_name": "Odanacatib",
        "seed_status": "clinical_cathepsin_k_benchmark",
        "brief_slot_name": "repurposing_1",
        "first_contact_use_mode": "benchmark_control",
        "vendor_check_required": False,
        "cost_check_required": False,
        "selectivity_note": "Use as the cleanest literature benchmark for Cathepsin K-focused inhibition and acidic-context assay behavior, not as a development-ready repurposing claim.",
        "usage_rationale": "Best first cheap-validation control because it gives the packet a selective, clinically legible Cathepsin K reference before we ask the lab to judge any family-selectivity story.",
        "must_not_do": "Do not present odanacatib as an approved therapy or as proof that any Cathepsin K hit is automatically class-selective.",
        "source_anchor": "odanacatib discovery paper",
        "source_url": "https://pubmed.ncbi.nlm.nih.gov/18226527/",
    },
    {
        "priority_rank": 9,
        "target_id": "Cathepsin K",
        "outreach_track_id": "acidic_protease_wave2",
        "slot_rank": 2,
        "compound_name": "Balicatib",
        "seed_status": "cathepsin_k_family_benchmark",
        "brief_slot_name": "repurposing_2",
        "first_contact_use_mode": "benchmark_control",
        "vendor_check_required": False,
        "cost_check_required": False,
        "selectivity_note": "Use as the family-stress benchmark that reminds the first packet to watch related-cathepsin carryover and lysosomal/basicity liabilities.",
        "usage_rationale": "Pairs with odanacatib as a cheaper benchmark contrast because it keeps the first packet focused on whether the assay can tell a cleaner Cathepsin K story from a broader cathepsin inhibitor profile.",
        "must_not_do": "Do not treat balicatib as the preferred lead chemistry; its role is to stress-test the family selectivity frame.",
        "source_anchor": "balicatib monkey efficacy paper",
        "source_url": "https://pubmed.ncbi.nlm.nih.gov/21380636/",
    },
    {
        "priority_rank": 9,
        "target_id": "Cathepsin K",
        "outreach_track_id": "acidic_protease_wave2",
        "slot_rank": 3,
        "compound_name": "Relacatib",
        "seed_status": "cathepsin_k_comparator_control",
        "brief_slot_name": "repurposing_3",
        "first_contact_use_mode": "comparator_only",
        "vendor_check_required": False,
        "cost_check_required": False,
        "selectivity_note": "Use as the third literature comparator to keep the packet honest about family selectivity and biomarker-response translation, not as a preferred wave2 lead.",
        "usage_rationale": "Rounds out the cheap-validation lane with a second-generation Cathepsin K comparator so the external lab sees an anchored benchmark set instead of a single-control story.",
        "must_not_do": "Do not oversell relacatib as cleaner than odanacatib without direct family-panel evidence from the Cathepsin K packet.",
        "source_anchor": "relacatib pharmacology paper",
        "source_url": "https://pubmed.ncbi.nlm.nih.gov/16962401/",
    },
]

USAGE_ENUM = "proceed_now ; comparator_only ; benchmark_control ; hold"


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _maybe_load_json(path_like: str) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def build_payload(
    brief_fill_queue: dict[str, Any] | None = None,
    packet_queue: dict[str, Any] | None = None,
    broad_screen_autofill: dict[str, Any] | None = None,
) -> dict[str, Any]:
    fill_queue_rows = {
        str(row.get("target_id", "")): dict(row)
        for row in ((brief_fill_queue or {}).get("rows", []) or [])
        if str(row.get("target_id", "")).strip()
    }
    packet_queue_rows = {
        str(row.get("target_id", "")): dict(row)
        for row in ((packet_queue or {}).get("rows", []) or [])
        if str(row.get("target_id", "")).strip()
    }

    queue_row = fill_queue_rows.get("Cathepsin K", {"brief_artifact_planned": DEFAULT_TARGET_BRIEF_ARTIFACT})
    packet_row = packet_queue_rows.get("Cathepsin K", {"track_label": DEFAULT_TRACK_LABEL})

    rows, bulk_override_applied = materialize_repurposing_rows(
        target_id="Cathepsin K",
        manual_rows=[dict(spec) for spec in ROW_SPECS],
        bulk_autofill_payload=broad_screen_autofill,
        target_brief_artifact=str(queue_row.get("brief_artifact_planned", DEFAULT_TARGET_BRIEF_ARTIFACT)).strip() or DEFAULT_TARGET_BRIEF_ARTIFACT,
        first_contact_packet_artifact=FIRST_CONTACT_PACKET_ARTIFACT,
        track_label=str(packet_row.get("track_label", DEFAULT_TRACK_LABEL)).strip() or DEFAULT_TRACK_LABEL,
        default_outreach_track_id="acidic_protease_wave2",
    )

    summary = {
        "status": "wetlab_cathepsin_k_repurposing_fill_map_ready",
        "source_brief_fill_queue_artifact": "runs/wetlab_wave2_brief_fill_queue_current.md",
        "source_packet_queue_artifact": "runs/wetlab_wave2_packet_queue_current.md",
        "target_count": 1,
        "row_count": len(rows),
        "bulk_override_applied": bulk_override_applied,
        "usage_enum": USAGE_ENUM,
        "next_required_step": "Render these rows into the Cathepsin K brief, bind them into the first wave2 launch packet, and use the family-selectivity panel before treating any compound as a live successor-opening result.",
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Wet-Lab Cathepsin K Repurposing Fill Map",
        "",
        f"- status: `{s['status']}`",
        f"- source_brief_fill_queue_artifact: `{s['source_brief_fill_queue_artifact']}`",
        f"- source_packet_queue_artifact: `{s['source_packet_queue_artifact']}`",
        f"- target_count: `{s['target_count']}`",
        f"- row_count: `{s['row_count']}`",
        f"- usage_enum: `{s['usage_enum']}`",
        "",
        "| slot_rank | compound_name | first_contact_use_mode | target_brief_artifact |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['slot_rank']}` | `{row['compound_name']}` | `{row['first_contact_use_mode']}` | `{row['target_brief_artifact']}` |"
        )
    lines.extend(["", "## Usage Notes", ""])
    for row in payload["rows"]:
        lines.extend(
            [
                f"- `{row['compound_name']}` -> `{row['first_contact_use_mode']}` via `{row['brief_slot_name']}`",
                f"  Rationale: {row['usage_rationale']}",
                f"  Selectivity note: {row['selectivity_note']}",
                f"  Must not do: {row['must_not_do']}",
                f"  Source: [{row['source_anchor']}]({row['source_url']})",
                "",
            ]
        )
    lines.extend(["## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the Cathepsin K repurposing and benchmark-control fill map.")
    parser.add_argument("--brief-fill-queue-json", default=DEFAULT_BRIEF_FILL_QUEUE_JSON)
    parser.add_argument("--packet-queue-json", default=DEFAULT_PACKET_QUEUE_JSON)
    parser.add_argument("--broad-screen-autofill-json", default=DEFAULT_BROAD_SCREEN_AUTOFILL_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _maybe_load_json(args.brief_fill_queue_json),
        _maybe_load_json(args.packet_queue_json),
        maybe_load_json(args.broad_screen_autofill_json),
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
