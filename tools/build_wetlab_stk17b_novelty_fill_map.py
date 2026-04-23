#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPURPOSING_FILL_MAP_JSON = "runs/wetlab_stk17b_repurposing_fill_map_current.json"
DEFAULT_OUT_JSON = "runs/wetlab_stk17b_novelty_fill_map_current.json"
DEFAULT_OUT_CSV = "runs/wetlab_stk17b_novelty_fill_map_current.csv"
DEFAULT_OUT_MD = "runs/wetlab_stk17b_novelty_fill_map_current.md"

ROW_SPECS: list[dict[str, Any]] = [
    {
        "priority_rank": 7,
        "target_id": "STK17B (DRAK2)",
        "outreach_track_id": "SGC_dark_kinase",
        "slot_rank": 1,
        "novelty_compound_name": "SGC-STK17B-1 (11s)",
        "novelty_seed_status": "open_probe_anchor_series",
        "novelty_axis": "benchmark_control",
        "brief_slot_name": "novelty_1",
        "first_contact_use_mode": "benchmark_control",
        "vendor_check_required": False,
        "cost_check_required": False,
        "novelty_rationale": "The 11s probe is the open-probe anchor that makes the STK17B novelty lane legible from the first experiment and ties directly to the published P-loop story.",
        "selectivity_note": "Use as the positive benchmark for the open-probe lane, not as the packet's novelty claim by itself.",
        "must_not_do": "Do not describe the probe anchor as new discovery chemistry; its role is to stabilize the comparison frame.",
        "source_anchor": "STK17B probe paper 11s",
        "source_url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC7816213/",
    },
    {
        "priority_rank": 7,
        "target_id": "STK17B (DRAK2)",
        "outreach_track_id": "SGC_dark_kinase",
        "slot_rank": 2,
        "novelty_compound_name": "11h quinazoline analog",
        "novelty_seed_status": "open_probe_follow_on_series",
        "novelty_axis": "state_novelty",
        "brief_slot_name": "novelty_2",
        "first_contact_use_mode": "proceed_now",
        "vendor_check_required": False,
        "cost_check_required": False,
        "novelty_rationale": "11h is the cleanest follow-on novelty row because it stays in the published 11-series frame while still making the first packet ask a real state-sensitive question.",
        "selectivity_note": "Keep the story on P-loop and conformation-aware separation inside the 11-series, not on broad dark-kinase potency claims.",
        "must_not_do": "Do not claim this is already validated beyond the published STK17B open-probe series frame.",
        "source_anchor": "STK17B probe paper 11h",
        "source_url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC7816213/",
    },
    {
        "priority_rank": 7,
        "target_id": "STK17B (DRAK2)",
        "outreach_track_id": "SGC_dark_kinase",
        "slot_rank": 3,
        "novelty_compound_name": "11aa quinazoline analog",
        "novelty_seed_status": "open_probe_follow_on_series",
        "novelty_axis": "benchmark_control",
        "brief_slot_name": "novelty_3",
        "first_contact_use_mode": "benchmark_control",
        "vendor_check_required": False,
        "cost_check_required": False,
        "novelty_rationale": "11aa completes the open-probe comparator triangle so the first packet can ask whether the dynamic model is ranking meaningfully inside a published series, not just against one probe.",
        "selectivity_note": "Use as a benchmark comparator within the 11-series, not as a stand-alone hit claim.",
        "must_not_do": "Do not overstate novelty beyond the published probe-series frame.",
        "source_anchor": "STK17B probe paper 11aa",
        "source_url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC7816213/",
    },
]

NOVELTY_AXIS_ENUM = "scaffold_novelty ; state_novelty ; condition_novelty ; selectivity_novelty ; benchmark_control"
FIRST_CONTACT_USE_MODE_ENUM = "proceed_now ; comparator_only ; benchmark_control ; hold"
FIRST_CONTACT_PACKET_ARTIFACT = "runs/wetlab_wave1_kinase_first_contact_packets_current.md"
TARGET_BRIEF_ARTIFACT = "runs/wetlab_target_brief_stk17b_current.md"


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


def build_payload(repurposing_fill_map: dict[str, Any] | None = None) -> dict[str, Any]:
    rep_bound = bool((repurposing_fill_map or {}).get("rows"))
    rows: list[dict[str, Any]] = []
    for spec in ROW_SPECS:
        row = dict(spec)
        row["target_brief_artifact"] = TARGET_BRIEF_ARTIFACT
        row["first_contact_packet_artifact"] = FIRST_CONTACT_PACKET_ARTIFACT
        row["novelty_fill_status"] = "ready"
        row["row_status"] = "ready"
        if rep_bound:
            row["source_repurposing_fill_bound"] = True
        rows.append(row)

    summary = {
        "status": "wetlab_stk17b_novelty_fill_map_ready",
        "source_stk17b_repurposing_fill_map_artifact": "runs/wetlab_stk17b_repurposing_fill_map_current.md",
        "target_count": 1,
        "row_count": len(rows),
        "novelty_slot_count": 3,
        "novelty_axis_enum": NOVELTY_AXIS_ENUM,
        "first_contact_use_mode_enum": FIRST_CONTACT_USE_MODE_ENUM,
        "next_required_step": "Render these rows into the STK17B target brief, rebuild the kinase first-contact packet, then export the SGC dark-kinase outreach row.",
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Wet-Lab STK17B Novelty Fill Map",
        "",
        f"- status: `{s['status']}`",
        f"- source_stk17b_repurposing_fill_map_artifact: `{s['source_stk17b_repurposing_fill_map_artifact']}`",
        f"- target_count: `{s['target_count']}`",
        f"- row_count: `{s['row_count']}`",
        f"- novelty_slot_count: `{s['novelty_slot_count']}`",
        f"- novelty_axis_enum: `{s['novelty_axis_enum']}`",
        "",
        "| slot_rank | novelty_compound_name | novelty_axis | first_contact_use_mode |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['slot_rank']}` | `{row['novelty_compound_name']}` | `{row['novelty_axis']}` | `{row['first_contact_use_mode']}` |"
        )
    lines.extend(["", "## Usage Notes", ""])
    for row in payload["rows"]:
        lines.extend(
            [
                f"- `{row['novelty_compound_name']}` -> `{row['first_contact_use_mode']}` via `{row['brief_slot_name']}`",
                f"  Rationale: {row['novelty_rationale']}",
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
    parser = argparse.ArgumentParser(description="Build the STK17B novelty and benchmark-control fill map.")
    parser.add_argument("--repurposing-fill-map-json", default=DEFAULT_REPURPOSING_FILL_MAP_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(_maybe_load_json(args.repurposing_fill_map_json))
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv_rows(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
