#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPURPOSING_FILL_MAP_JSON = "runs/wetlab_dpre1_repurposing_fill_map_current.json"
DEFAULT_OUT_JSON = "runs/wetlab_dpre1_novelty_fill_map_current.json"
DEFAULT_OUT_CSV = "runs/wetlab_dpre1_novelty_fill_map_current.csv"
DEFAULT_OUT_MD = "runs/wetlab_dpre1_novelty_fill_map_current.md"
FIRST_CONTACT_PACKET_ARTIFACT = "runs/dpre1_tb_alliance_export_current.md"
TARGET_BRIEF_ARTIFACT = "runs/dpre1_render_suite_current.md"

ROW_SPECS: list[dict[str, Any]] = [
    {
        "priority_rank": 10,
        "target_id": "DprE1",
        "outreach_track_id": "TB_Alliance",
        "slot_rank": 1,
        "novelty_compound_name": "OPC-167832",
        "novelty_seed_status": "clinical_stage_dpre1_anchor",
        "novelty_axis": "benchmark_control",
        "brief_slot_name": "novelty_1",
        "first_contact_use_mode": "proceed_now",
        "vendor_check_required": False,
        "cost_check_required": False,
        "novelty_rationale": "Best proceed-now DprE1 novelty anchor because it has direct enzymatic, intracellular, and regimen-combination support.",
        "selectivity_note": "Use as the main DprE1 biochemical-to-whole-cell bridge before asking a partner lab to consider stranger scaffolds.",
        "must_not_do": "Do not collapse the whole packet into OPC-167832-only thinking; it is the anchor, not the entire thesis.",
        "source_anchor": "OPC-167832 DprE1 paper",
        "source_url": "https://pubmed.ncbi.nlm.nih.gov/32229496/",
    },
    {
        "priority_rank": 10,
        "target_id": "DprE1",
        "outreach_track_id": "TB_Alliance",
        "slot_rank": 2,
        "novelty_compound_name": "PBTZ169",
        "novelty_seed_status": "benzothiazinone_clinical_family_anchor",
        "novelty_axis": "scaffold_novelty",
        "brief_slot_name": "novelty_2",
        "first_contact_use_mode": "benchmark_control",
        "vendor_check_required": False,
        "cost_check_required": False,
        "novelty_rationale": "Keeps the DprE1 packet anchored to the strongest benzothiazinone clinical family while still leaving room for non-BTZ chemistry.",
        "selectivity_note": "Carry this as a mechanistic benchmark and resistance-monitoring anchor rather than as proof every DprE1 row should be covalent.",
        "must_not_do": "Do not present PBTZ169 as generic whole-cell TB chemistry divorced from DprE1.",
        "source_anchor": "PBTZ169 DprE1 paper",
        "source_url": "https://pubmed.ncbi.nlm.nih.gov/24500695/",
    },
    {
        "priority_rank": 10,
        "target_id": "DprE1",
        "outreach_track_id": "TB_Alliance",
        "slot_rank": 3,
        "novelty_compound_name": "TBA-7371",
        "novelty_seed_status": "non_btz_dpre1_clinical_comparator",
        "novelty_axis": "condition_novelty",
        "brief_slot_name": "novelty_3",
        "first_contact_use_mode": "comparator_only",
        "vendor_check_required": False,
        "cost_check_required": False,
        "novelty_rationale": "Adds a non-BTZ clinical-stage DprE1 comparator so the packet can test whether activity survives beyond the benzothiazinone bias.",
        "selectivity_note": "Use as a family-diversity comparator when interpreting biochemical-to-whole-cell consistency.",
        "must_not_do": "Do not overstate TBA-7371 as the default lead over OPC-167832 in a first packet.",
        "source_anchor": "TB Alliance DprE1 inhibitor portfolio context",
        "source_url": "https://www.tballiance.org/wp-content/uploads/assets-from-drupal/AboutTBAlliance_September2023.pdf",
    },
]

NOVELTY_AXIS_ENUM = "scaffold_novelty ; state_novelty ; condition_novelty ; selectivity_novelty ; benchmark_control"
FIRST_CONTACT_USE_MODE_ENUM = "proceed_now ; comparator_only ; benchmark_control ; hold"


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


def build_payload(repurposing_fill_map: dict[str, Any] | None = None) -> dict:
    rep_bound = bool((repurposing_fill_map or {}).get("rows"))
    rows = []
    for spec in ROW_SPECS:
        row = dict(spec)
        row["target_brief_artifact"] = TARGET_BRIEF_ARTIFACT
        row["first_contact_packet_artifact"] = FIRST_CONTACT_PACKET_ARTIFACT
        row["row_status"] = "ready"
        if rep_bound:
            row["source_repurposing_fill_bound"] = True
        rows.append(row)
    return {
        "summary": {
            "status": "wetlab_dpre1_novelty_fill_map_ready",
            "target_count": 1,
            "row_count": len(rows),
            "novelty_slot_count": 3,
            "novelty_axis_enum": NOVELTY_AXIS_ENUM,
            "first_contact_use_mode_enum": FIRST_CONTACT_USE_MODE_ENUM,
            "next_required_step": "Render these DprE1 novelty rows into the TB rail packet, then keep the target serialized behind Dengue until predecessor resolution.",
        },
        "rows": rows,
    }


def _write_markdown(path: Path, payload: dict) -> None:
    s = payload["summary"]
    lines = [
        "# Wet-Lab DprE1 Novelty Fill Map",
        "",
        f"- status: `{s['status']}`",
        f"- target_count: `{s['target_count']}`",
        f"- row_count: `{s['row_count']}`",
        "",
        "| slot_rank | novelty_compound_name | novelty_axis | first_contact_use_mode |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(f"| `{row['slot_rank']}` | `{row['novelty_compound_name']}` | `{row['novelty_axis']}` | `{row['first_contact_use_mode']}` |")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the DprE1 novelty fill map.")
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
