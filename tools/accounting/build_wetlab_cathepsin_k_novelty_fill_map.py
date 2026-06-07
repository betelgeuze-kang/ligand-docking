#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPURPOSING_FILL_MAP_JSON = "runs/wetlab_cathepsin_k_repurposing_fill_map_current.json"
DEFAULT_OUT_JSON = "runs/wetlab_cathepsin_k_novelty_fill_map_current.json"
DEFAULT_OUT_CSV = "runs/wetlab_cathepsin_k_novelty_fill_map_current.csv"
DEFAULT_OUT_MD = "runs/wetlab_cathepsin_k_novelty_fill_map_current.md"

ROW_SPECS: list[dict[str, Any]] = [
    {
        "priority_rank": 9,
        "target_id": "Cathepsin K",
        "outreach_track_id": "acidic_protease_wave2",
        "slot_rank": 1,
        "novelty_compound_name": "Odanacatib (MK-0822)",
        "novelty_seed_status": "flagship_active_site_reference",
        "novelty_axis": "benchmark_control",
        "brief_slot_name": "novelty_1",
        "first_contact_use_mode": "benchmark_control",
        "vendor_check_required": False,
        "cost_check_required": False,
        "novelty_rationale": "Odanacatib is the cleanest flagship Cathepsin K active-site anchor, so it stabilizes the Wave 2 packet around a literature-recognizable reference before newer mechanism claims are interpreted.",
        "selectivity_note": "Use as the active-site reference for the acidic-arm and related-cathepsin cleanup story, not as proof that the shortlist is already class-selective.",
        "must_not_do": "Do not present odanacatib as a default clean win without the same-packet Cathepsin B/L/S and neutral-context filters.",
        "source_anchor": "Odanacatib discovery paper",
        "source_url": "https://pubmed.ncbi.nlm.nih.gov/18226527/",
    },
    {
        "priority_rank": 9,
        "target_id": "Cathepsin K",
        "outreach_track_id": "acidic_protease_wave2",
        "slot_rank": 2,
        "novelty_compound_name": "MIV-711",
        "novelty_seed_status": "selective_clinical_follow_on",
        "novelty_axis": "selectivity_novelty",
        "brief_slot_name": "novelty_2",
        "first_contact_use_mode": "proceed_now",
        "vendor_check_required": False,
        "cost_check_required": False,
        "novelty_rationale": "MIV-711 is the best proceed-now Cathepsin K novelty row because the literature frames it as a potent, highly selective clinical-stage follow-on rather than a generic cysteine-protease inhibitor.",
        "selectivity_note": "Keep this row tied to the related-cathepsin mini-panel; its value is the reported Cathepsin K selectivity, not a claim that the whole packet can skip family cleanup.",
        "must_not_do": "Do not oversell the clinical literature as if it replaces the Wave 2 acidic-context and related-cathepsin validation stack.",
        "source_anchor": "MIV-711 Cathepsin K pharmacology paper",
        "source_url": "https://pubmed.ncbi.nlm.nih.gov/29743078/",
    },
    {
        "priority_rank": 9,
        "target_id": "Cathepsin K",
        "outreach_track_id": "acidic_protease_wave2",
        "slot_rank": 3,
        "novelty_compound_name": "T06 ectosteric Cathepsin K inhibitor",
        "novelty_seed_status": "ectosteric_condition_mechanism",
        "novelty_axis": "condition_novelty",
        "brief_slot_name": "novelty_3",
        "first_contact_use_mode": "comparator_only",
        "vendor_check_required": False,
        "cost_check_required": False,
        "novelty_rationale": "T06 adds a mechanism-diverse ectosteric row that can stress-test whether the packet is only rewarding standard active-site chemistry or can notice collagen-processing-biased Cathepsin K behavior.",
        "selectivity_note": "Use as a mechanism comparator when interpreting acidic-context Cathepsin K behavior, especially if fluorogenic and matrix-facing readouts diverge.",
        "must_not_do": "Do not treat T06 as a drop-in primary fluorogenic benchmark because the literature positions it as an ectosteric collagen-degradation stress test.",
        "source_anchor": "T06 ectosteric Cathepsin K inhibitor paper",
        "source_url": "https://pubmed.ncbi.nlm.nih.gov/28745432/",
    },
]

NOVELTY_AXIS_ENUM = "scaffold_novelty ; state_novelty ; condition_novelty ; selectivity_novelty ; benchmark_control"
FIRST_CONTACT_USE_MODE_ENUM = "proceed_now ; comparator_only ; benchmark_control ; hold"
FIRST_CONTACT_PACKET_ARTIFACT = "runs/cathepsin_k_acidic_protease_export_current.md"
TARGET_BRIEF_ARTIFACT = "runs/cathepsin_k_render_suite_current.md"


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
        "status": "wetlab_cathepsin_k_novelty_fill_map_ready",
        "source_cathepsin_k_repurposing_fill_map_artifact": "runs/wetlab_cathepsin_k_repurposing_fill_map_current.md",
        "target_count": 1,
        "row_count": len(rows),
        "novelty_slot_count": 3,
        "novelty_axis_enum": NOVELTY_AXIS_ENUM,
        "first_contact_use_mode_enum": FIRST_CONTACT_USE_MODE_ENUM,
        "next_required_step": "Render these rows into the Cathepsin K render suite and acidic-protease export packet, then keep Wave 2 content-blocked until the repurposing lane is real.",
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Wet-Lab Cathepsin K Novelty Fill Map",
        "",
        f"- status: `{s['status']}`",
        f"- source_cathepsin_k_repurposing_fill_map_artifact: `{s['source_cathepsin_k_repurposing_fill_map_artifact']}`",
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
    parser = argparse.ArgumentParser(description="Build the Cathepsin K novelty and flagship-inhibitor fill map.")
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
