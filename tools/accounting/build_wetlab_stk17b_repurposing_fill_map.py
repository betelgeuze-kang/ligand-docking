#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.wetlab_target_render_utils import materialize_repurposing_rows, maybe_load_json

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BRIEF_FILL_QUEUE_JSON = "runs/wetlab_wave1_brief_fill_queue_current.json"
DEFAULT_PACKET_QUEUE_JSON = "runs/wetlab_wave1_packet_queue_current.json"
DEFAULT_OUT_JSON = "runs/wetlab_stk17b_repurposing_fill_map_current.json"
DEFAULT_OUT_CSV = "runs/wetlab_stk17b_repurposing_fill_map_current.csv"
DEFAULT_OUT_MD = "runs/wetlab_stk17b_repurposing_fill_map_current.md"
DEFAULT_BROAD_SCREEN_AUTOFILL_JSON = "runs/wetlab_broad_screen_repurposing_autofill_current.json"

ROW_SPECS: list[dict[str, Any]] = [
    {
        "priority_rank": 7,
        "target_id": "STK17B (DRAK2)",
        "outreach_track_id": "SGC_dark_kinase",
        "slot_rank": 1,
        "compound_name": "PFE-PKIS 43 (4)",
        "seed_status": "open_set_pkis_benchmark_from_probe_paper",
        "brief_slot_name": "repurposing_1",
        "first_contact_use_mode": "benchmark_control",
        "vendor_check_required": False,
        "cost_check_required": False,
        "selectivity_note": "Use as a published PKIS benchmark that already sits inside the STK17B P-loop reference frame, not as disease-facing lead chemistry.",
        "usage_rationale": "Best first benchmark for a cheap-validation/open-set packet because it gives the lab a known literature reference before we ask it to trust any dynamic ranking claim.",
        "must_not_do": "Do not describe this as a selective or development-ready STK17B lead.",
        "source_anchor": "STK17B probe paper PKIS benchmark 4",
        "source_url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC7816213/",
    },
    {
        "priority_rank": 7,
        "target_id": "STK17B (DRAK2)",
        "outreach_track_id": "SGC_dark_kinase",
        "slot_rank": 2,
        "compound_name": "PFE-PKIS 14 (5)",
        "seed_status": "open_set_pkis_benchmark_from_probe_paper",
        "brief_slot_name": "repurposing_2",
        "first_contact_use_mode": "benchmark_control",
        "vendor_check_required": False,
        "cost_check_required": False,
        "selectivity_note": "Use as the second PKIS benchmark to check whether the P-loop-aware packet can separate related published binders before claiming novelty.",
        "usage_rationale": "Pairs naturally with benchmark 4 so the first packet is an open-set literature comparison, not a dark-kinase fishing trip.",
        "must_not_do": "Do not package this as a priority hit or as selective kinase chemistry.",
        "source_anchor": "STK17B probe paper PKIS benchmark 5",
        "source_url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC7816213/",
    },
    {
        "priority_rank": 7,
        "target_id": "STK17B (DRAK2)",
        "outreach_track_id": "SGC_dark_kinase",
        "slot_rank": 3,
        "compound_name": "PFE-PKIS 9 (6)",
        "seed_status": "open_set_pkis_comparator_from_probe_paper",
        "brief_slot_name": "repurposing_3",
        "first_contact_use_mode": "comparator_only",
        "vendor_check_required": False,
        "cost_check_required": False,
        "selectivity_note": "Use as the open-set comparator that makes the first packet answer a sharper benchmark question than probe-versus-probe alone.",
        "usage_rationale": "Rounds out the cheap-validation lane with a third published STK17B binder so the external lab can judge whether the dynamic model adds value across an existing open-set panel.",
        "must_not_do": "Do not market this as repurposed clinical chemistry or as a front-running STK17B hit.",
        "source_anchor": "STK17B probe paper PKIS comparator 6",
        "source_url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC7816213/",
    },
]

USAGE_ENUM = "proceed_now ; comparator_only ; benchmark_control ; hold"
FIRST_CONTACT_PACKET_ARTIFACT = "runs/wetlab_wave1_kinase_first_contact_packets_current.md"


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


def build_payload(
    brief_fill_queue: dict[str, Any],
    packet_queue: dict[str, Any],
    broad_screen_autofill: dict[str, Any] | None = None,
) -> dict[str, Any]:
    fill_queue_rows = {str(row.get("target_id", "")): dict(row) for row in brief_fill_queue.get("rows", []) or []}
    packet_queue_rows = {str(row.get("target_id", "")): dict(row) for row in packet_queue.get("rows", []) or []}

    queue_row = fill_queue_rows["STK17B (DRAK2)"]
    packet_row = packet_queue_rows["STK17B (DRAK2)"]
    rows, bulk_override_applied = materialize_repurposing_rows(
        target_id="STK17B (DRAK2)",
        manual_rows=[dict(spec) for spec in ROW_SPECS],
        bulk_autofill_payload=broad_screen_autofill,
        target_brief_artifact=queue_row["brief_artifact_planned"],
        first_contact_packet_artifact=FIRST_CONTACT_PACKET_ARTIFACT,
        track_label=packet_row["track_label"],
        default_outreach_track_id="SGC_dark_kinase",
    )

    summary = {
        "status": "wetlab_stk17b_repurposing_fill_map_ready",
        "source_brief_fill_queue_artifact": "runs/wetlab_wave1_brief_fill_queue_current.md",
        "source_packet_queue_artifact": "runs/wetlab_wave1_packet_queue_current.md",
        "target_count": 1,
        "row_count": len(rows),
        "bulk_override_applied": bulk_override_applied,
        "usage_enum": USAGE_ENUM,
        "next_required_step": "Render these rows into the STK17B target brief, bind the novelty lane beside the probe ecosystem, then export the SGC first-contact packet.",
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Wet-Lab STK17B Repurposing Fill Map",
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
    parser = argparse.ArgumentParser(description="Build the STK17B cheap-validation and open-set benchmark fill map.")
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
        _load_json(args.brief_fill_queue_json),
        _load_json(args.packet_queue_json),
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
