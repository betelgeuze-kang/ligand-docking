#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from tools.builder_table_utils import write_csv_rows
from tools.wetlab_target_render_utils import materialize_repurposing_rows, maybe_load_json

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_JSON = "runs/wetlab_dpre1_repurposing_fill_map_current.json"
DEFAULT_OUT_CSV = "runs/wetlab_dpre1_repurposing_fill_map_current.csv"
DEFAULT_OUT_MD = "runs/wetlab_dpre1_repurposing_fill_map_current.md"
DEFAULT_BROAD_SCREEN_AUTOFILL_JSON = "runs/wetlab_broad_screen_repurposing_autofill_current.json"
DEFAULT_TARGET_BRIEF_ARTIFACT = "runs/dpre1_render_suite_current.md"
FIRST_CONTACT_PACKET_ARTIFACT = "runs/dpre1_launch_packet_current.md"
DEFAULT_TRACK_LABEL = "TB Alliance / academic TB rail"

ROW_SPECS: list[dict[str, Any]] = [
    {
        "priority_rank": 10,
        "target_id": "DprE1",
        "outreach_track_id": "TB_Alliance",
        "slot_rank": 1,
        "compound_name": "Delamanid",
        "seed_status": "approved_tb_regimen_benchmark",
        "brief_slot_name": "repurposing_1",
        "first_contact_use_mode": "benchmark_control",
        "vendor_check_required": False,
        "cost_check_required": False,
        "selectivity_note": "Use as a regimen-facing benchmark row, not as a claim that delamanid is a direct DprE1 inhibitor.",
        "usage_rationale": "Best approved-TB benchmark for the DprE1 packet because OPC-167832 combination work gives the partner a clean regimen-comparison frame.",
        "must_not_do": "Do not present delamanid as direct DprE1 chemistry.",
        "source_anchor": "OPC-167832 antituberculosis activity paper",
        "source_url": "https://pubmed.ncbi.nlm.nih.gov/32229496/",
    },
    {
        "priority_rank": 10,
        "target_id": "DprE1",
        "outreach_track_id": "TB_Alliance",
        "slot_rank": 2,
        "compound_name": "Pretomanid",
        "seed_status": "approved_tb_whole_cell_comparator",
        "brief_slot_name": "repurposing_2",
        "first_contact_use_mode": "comparator_only",
        "vendor_check_required": False,
        "cost_check_required": False,
        "selectivity_note": "Comparator-only TB whole-cell anchor so the packet can separate DprE1-on-target behavior from generic regimen efficacy.",
        "usage_rationale": "Useful comparator because it is an approved TB drug with real regimen relevance, even though it is not DprE1-directed.",
        "must_not_do": "Do not treat pretomanid as evidence for DprE1 target engagement.",
        "source_anchor": "TB regimen comparator context",
        "source_url": "https://www.tballiance.org/wp-content/uploads/assets-from-drupal/AboutTBAlliance_September2023.pdf",
    },
    {
        "priority_rank": 10,
        "target_id": "DprE1",
        "outreach_track_id": "TB_Alliance",
        "slot_rank": 3,
        "compound_name": "Bedaquiline",
        "seed_status": "approved_tb_regimen_comparator",
        "brief_slot_name": "repurposing_3",
        "first_contact_use_mode": "comparator_only",
        "vendor_check_required": False,
        "cost_check_required": False,
        "selectivity_note": "Use as a regimen comparator and whole-cell anchor only; it helps contextualize whole-cell follow-up after a biochemical DprE1 hit.",
        "usage_rationale": "Rounds out the approved-drug lane with the clearest modern TB regimen comparator for a partner lab that wants practical follow-up framing.",
        "must_not_do": "Do not claim any bedaquiline row is DprE1-targeted.",
        "source_anchor": "TB Alliance DprE1 inhibitor portfolio context",
        "source_url": "https://www.tballiance.org/wp-content/uploads/assets-from-drupal/AboutTBAlliance_September2023.pdf",
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


def build_payload(broad_screen_autofill: dict | None = None) -> dict:
    rows, bulk_override_applied = materialize_repurposing_rows(
        target_id="DprE1",
        manual_rows=[dict(spec) for spec in ROW_SPECS],
        bulk_autofill_payload=broad_screen_autofill,
        target_brief_artifact=DEFAULT_TARGET_BRIEF_ARTIFACT,
        first_contact_packet_artifact=FIRST_CONTACT_PACKET_ARTIFACT,
        track_label=DEFAULT_TRACK_LABEL,
        default_outreach_track_id="TB_Alliance",
    )
    return {
        "summary": {
            "status": "wetlab_dpre1_repurposing_fill_map_ready",
            "target_count": 1,
            "row_count": len(rows),
            "bulk_override_applied": bulk_override_applied,
            "usage_enum": USAGE_ENUM,
            "next_required_step": "Render these TB-regimen comparator rows into the DprE1 suite, then keep DprE1 serialized behind Dengue until the predecessor resolves.",
        },
        "rows": rows,
    }


def _write_markdown(path: Path, payload: dict) -> None:
    s = payload["summary"]
    lines = [
        "# Wet-Lab DprE1 Repurposing Fill Map",
        "",
        f"- status: `{s['status']}`",
        f"- target_count: `{s['target_count']}`",
        f"- row_count: `{s['row_count']}`",
        "",
        "| slot_rank | compound_name | first_contact_use_mode |",
        "| --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(f"| `{row['slot_rank']}` | `{row['compound_name']}` | `{row['first_contact_use_mode']}` |")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the DprE1 repurposing fill map.")
    parser.add_argument("--broad-screen-autofill-json", default=DEFAULT_BROAD_SCREEN_AUTOFILL_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(maybe_load_json(args.broad_screen_autofill_json))
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv_rows(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
