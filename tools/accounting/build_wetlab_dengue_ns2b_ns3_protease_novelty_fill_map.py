#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPURPOSING_FILL_MAP_JSON = "runs/wetlab_dengue_ns2b_ns3_protease_repurposing_fill_map_current.json"
DEFAULT_OUT_JSON = "runs/wetlab_dengue_ns2b_ns3_protease_novelty_fill_map_current.json"
DEFAULT_OUT_CSV = "runs/wetlab_dengue_ns2b_ns3_protease_novelty_fill_map_current.csv"
DEFAULT_OUT_MD = "runs/wetlab_dengue_ns2b_ns3_protease_novelty_fill_map_current.md"
FIRST_CONTACT_PACKET_ARTIFACT = "runs/dengue_ns2b_ns3_protease_ipk_export_current.md"
TARGET_BRIEF_ARTIFACT = "runs/dengue_ns2b_ns3_protease_render_suite_current.md"

ROW_SPECS: list[dict[str, Any]] = [
    {
        "priority_rank": 9,
        "target_id": "Dengue NS2B-NS3 protease",
        "outreach_track_id": "IPK_dengue",
        "slot_rank": 1,
        "novelty_compound_name": "BP2109",
        "novelty_seed_status": "dengue_specific_mechanistic_anchor",
        "novelty_axis": "benchmark_control",
        "brief_slot_name": "novelty_1",
        "first_contact_use_mode": "benchmark_control",
        "vendor_check_required": False,
        "cost_check_required": False,
        "novelty_rationale": "BP2109 is the cleanest dengue-specific novelty anchor because it came from a direct recombinant DENV NS2B-NS3 screen and carries a mechanistic resistance story back into NS2B.",
        "selectivity_note": "Use as the dengue-specific mechanistic reference rather than as proof that later shallow-pocket rows are automatically clean.",
        "must_not_do": "Do not describe BP2109 as an approved repurposing candidate; it belongs in the novelty lane only.",
        "source_anchor": "BP2109 dengue inhibitor paper",
        "source_url": "https://pubmed.ncbi.nlm.nih.gov/20937790/",
    },
    {
        "priority_rank": 9,
        "target_id": "Dengue NS2B-NS3 protease",
        "outreach_track_id": "IPK_dengue",
        "slot_rank": 2,
        "novelty_compound_name": "Curcumin",
        "novelty_seed_status": "allosteric_state_lock_reference",
        "novelty_axis": "state_novelty",
        "brief_slot_name": "novelty_2",
        "first_contact_use_mode": "proceed_now",
        "vendor_check_required": False,
        "cost_check_required": False,
        "novelty_rationale": "Curcumin gives the packet a state-locking allosteric row, which is exactly the kind of conformational discrimination we want to test in the shallow-pocket flaviviral protease rail.",
        "selectivity_note": "Keep this row coupled to the orthogonal flaviviral panel because the claim is conformational gating, not blind potency.",
        "must_not_do": "Do not present curcumin as a clean development candidate without the same-packet counterscreens and stickiness controls.",
        "source_anchor": "Curcumin allosteric dengue protease paper",
        "source_url": "https://pubmed.ncbi.nlm.nih.gov/33073093/",
    },
    {
        "priority_rank": 9,
        "target_id": "Dengue NS2B-NS3 protease",
        "outreach_track_id": "IPK_dengue",
        "slot_rank": 3,
        "novelty_compound_name": "Punicalagin",
        "novelty_seed_status": "pan_serotype_active_site_reference",
        "novelty_axis": "condition_novelty",
        "brief_slot_name": "novelty_3",
        "first_contact_use_mode": "comparator_only",
        "vendor_check_required": False,
        "cost_check_required": False,
        "novelty_rationale": "Punicalagin adds a pan-serotype row that can stress-test whether the packet notices genuine dengue protease signal across serotypes rather than a single-enzyme artifact.",
        "selectivity_note": "Use as a pan-serotype comparator when the first packet needs to separate flaviviral protease engagement from shallow-pocket false positives.",
        "must_not_do": "Do not treat punicalagin as the default first biochemical benchmark ahead of BP2109 or the approved-drug lane.",
        "source_anchor": "Punicalagin pan-serotype dengue protease paper",
        "source_url": "https://pubmed.ncbi.nlm.nih.gov/38373021/",
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
        "status": "wetlab_dengue_ns2b_ns3_protease_novelty_fill_map_ready",
        "source_dengue_ns2b_ns3_protease_repurposing_fill_map_artifact": "runs/wetlab_dengue_ns2b_ns3_protease_repurposing_fill_map_current.md",
        "target_count": 1,
        "row_count": len(rows),
        "novelty_slot_count": 3,
        "novelty_axis_enum": NOVELTY_AXIS_ENUM,
        "first_contact_use_mode_enum": FIRST_CONTACT_USE_MODE_ENUM,
        "next_required_step": "Render these novelty rows into the Dengue NS2B-NS3 protease suite, then keep the target content-ready but still serialized behind Cathepsin K.",
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Wet-Lab Dengue NS2B-NS3 Protease Novelty Fill Map",
        "",
        f"- status: `{s['status']}`",
        f"- source_dengue_ns2b_ns3_protease_repurposing_fill_map_artifact: `{s['source_dengue_ns2b_ns3_protease_repurposing_fill_map_artifact']}`",
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
    parser = argparse.ArgumentParser(description="Build the Dengue NS2B-NS3 protease novelty fill map.")
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
