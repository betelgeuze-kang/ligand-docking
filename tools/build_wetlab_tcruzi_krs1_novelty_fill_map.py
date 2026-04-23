#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPURPOSING_FILL_MAP_JSON = "runs/wetlab_tcruzi_krs1_repurposing_fill_map_current.json"
DEFAULT_OUT_JSON = "runs/wetlab_tcruzi_krs1_novelty_fill_map_current.json"
DEFAULT_OUT_CSV = "runs/wetlab_tcruzi_krs1_novelty_fill_map_current.csv"
DEFAULT_OUT_MD = "runs/wetlab_tcruzi_krs1_novelty_fill_map_current.md"
FIRST_CONTACT_PACKET_ARTIFACT = "runs/tcruzi_krs1_dndi_backup_export_current.md"
TARGET_BRIEF_ARTIFACT = "runs/tcruzi_krs1_render_suite_current.md"

ROW_SPECS: list[dict[str, Any]] = [
    {
        "priority_rank": 11,
        "target_id": "T. cruzi KRS1",
        "outreach_track_id": "DNDi_Chagas_backup",
        "slot_rank": 1,
        "novelty_compound_name": "DMU759",
        "novelty_seed_status": "lead_tc_krs1_quinazoline_anchor",
        "novelty_axis": "benchmark_control",
        "brief_slot_name": "novelty_1",
        "first_contact_use_mode": "proceed_now",
        "vendor_check_required": False,
        "cost_check_required": False,
        "novelty_rationale": "Best proceed-now KRS1 anchor because the mouse-efficacy paper carries it as the lead quinazoline with in vivo signal.",
        "selectivity_note": "Use as the main KRS1 biochemical-to-parasite bridge before asking a partner to consider stranger analogs.",
        "must_not_do": "Do not collapse the whole packet into DMU759-only thinking; it is the lead anchor, not the full thesis.",
        "source_anchor": "Sci Transl Med TcKRS1 quinazoline paper",
        "source_url": "https://pubmed.ncbi.nlm.nih.gov/40632837/",
    },
    {
        "priority_rank": 11,
        "target_id": "T. cruzi KRS1",
        "outreach_track_id": "DNDi_Chagas_backup",
        "slot_rank": 2,
        "novelty_compound_name": "DMU371",
        "novelty_seed_status": "quinazoline_mechanistic_anchor",
        "novelty_axis": "scaffold_novelty",
        "brief_slot_name": "novelty_2",
        "first_contact_use_mode": "benchmark_control",
        "vendor_check_required": False,
        "cost_check_required": False,
        "novelty_rationale": "Keeps the packet tied to the mechanistic quinazoline series member used for orthogonal target-deconvolution and structural work.",
        "selectivity_note": "Carry as the mechanistic series anchor when interpreting whether parasite signal really tracks KRS1.",
        "must_not_do": "Do not present DMU371 as interchangeable with the lead efficacy row without qualification.",
        "source_anchor": "Sci Transl Med TcKRS1 quinazoline paper",
        "source_url": "https://pubmed.ncbi.nlm.nih.gov/40632837/",
    },
    {
        "priority_rank": 11,
        "target_id": "T. cruzi KRS1",
        "outreach_track_id": "DNDi_Chagas_backup",
        "slot_rank": 3,
        "novelty_compound_name": "5,6,8-trifluoroquinazoline follow-up series",
        "novelty_seed_status": "series_expansion_anchor",
        "novelty_axis": "condition_novelty",
        "brief_slot_name": "novelty_3",
        "first_contact_use_mode": "comparator_only",
        "vendor_check_required": False,
        "cost_check_required": False,
        "novelty_rationale": "Adds a series-expansion row so the packet is not forced into a single-compound interpretation while staying inside the literature-anchored KRS1 scaffold family.",
        "selectivity_note": "Use as a family-diversity comparator rather than as a stronger claim than the two named lead quinazolines.",
        "must_not_do": "Do not claim a concrete follow-up analog identity where the current packet only has series-level evidence.",
        "source_anchor": "5,6,8-trifluoroquinazoline patent-linked series context",
        "source_url": "https://pubmed.ncbi.nlm.nih.gov/40632837/",
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
            "status": "wetlab_tcruzi_krs1_novelty_fill_map_ready",
            "target_count": 1,
            "row_count": len(rows),
            "novelty_slot_count": 3,
            "novelty_axis_enum": NOVELTY_AXIS_ENUM,
            "first_contact_use_mode_enum": FIRST_CONTACT_USE_MODE_ENUM,
            "next_required_step": "Render these KRS1 novelty rows into the DNDi backup rail packet, then keep the target serialized behind DprE1 until predecessor resolution.",
        },
        "rows": rows,
    }


def _write_markdown(path: Path, payload: dict) -> None:
    s = payload["summary"]
    lines = [
        "# Wet-Lab T. cruzi KRS1 Novelty Fill Map",
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
    parser = argparse.ArgumentParser(description="Build the T. cruzi KRS1 novelty fill map.")
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
