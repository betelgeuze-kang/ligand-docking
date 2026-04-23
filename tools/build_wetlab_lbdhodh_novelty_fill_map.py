#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPURPOSING_FILL_MAP_JSON = "runs/wetlab_lbdhodh_repurposing_fill_map_current.json"
DEFAULT_OUT_JSON = "runs/wetlab_lbdhodh_novelty_fill_map_current.json"
DEFAULT_OUT_CSV = "runs/wetlab_lbdhodh_novelty_fill_map_current.csv"
DEFAULT_OUT_MD = "runs/wetlab_lbdhodh_novelty_fill_map_current.md"

ROW_SPECS: list[dict[str, Any]] = [
    {
        "priority_rank": 8,
        "target_id": "Leishmania braziliensis DHODH",
        "outreach_track_id": "DNDi_IPK",
        "slot_rank": 1,
        "novelty_compound_name": "2i barbituric-acid covalent series",
        "novelty_seed_status": "parasite_dhodh_barbituric_anchor",
        "novelty_axis": "selectivity_novelty",
        "brief_slot_name": "novelty_1",
        "first_contact_use_mode": "proceed_now",
        "vendor_check_required": False,
        "cost_check_required": False,
        "novelty_rationale": "Best first neglected-enzyme novelty row because it anchors the packet to the DNDi-highlighted barbituric-acid covalent series and keeps host separation central.",
        "selectivity_note": "Use as the primary parasite-pocket-biased novelty row, not as a finished development claim.",
        "must_not_do": "Do not present this as already de-risked host-DHODH chemistry beyond the first counterscreen.",
        "source_anchor": "DNDi LbDHODH barbituric-acid article",
        "source_url": "https://dndi.org/scientific-articles/2025/barbituric-acid-derivatives-as-covalent-inhibitors-of-leishmania-braziliensis-dihydroorotate-dehydrogenase/",
    },
    {
        "priority_rank": 8,
        "target_id": "Leishmania braziliensis DHODH",
        "outreach_track_id": "DNDi_IPK",
        "slot_rank": 2,
        "novelty_compound_name": "2h barbituric-acid follow-on series",
        "novelty_seed_status": "parasite_dhodh_follow_on_series",
        "novelty_axis": "state_novelty",
        "brief_slot_name": "novelty_2",
        "first_contact_use_mode": "benchmark_control",
        "vendor_check_required": False,
        "cost_check_required": False,
        "novelty_rationale": "Provides a same-paper follow-on row so the first packet can ask whether the dynamic model ranks parasite-biased covalent chemistry coherently inside one neglected-enzyme frame.",
        "selectivity_note": "Use as a benchmark comparator beside the lead barbituric-acid row, not as a stand-alone claim.",
        "must_not_do": "Do not oversell this as a host-separated lead before the counterscreen is run.",
        "source_anchor": "DNDi LbDHODH barbituric-acid article",
        "source_url": "https://dndi.org/scientific-articles/2025/barbituric-acid-derivatives-as-covalent-inhibitors-of-leishmania-braziliensis-dihydroorotate-dehydrogenase/",
    },
    {
        "priority_rank": 8,
        "target_id": "Leishmania braziliensis DHODH",
        "outreach_track_id": "DNDi_IPK",
        "slot_rank": 3,
        "novelty_compound_name": "2f barbituric-acid comparator series",
        "novelty_seed_status": "parasite_dhodh_comparator_series",
        "novelty_axis": "benchmark_control",
        "brief_slot_name": "novelty_3",
        "first_contact_use_mode": "benchmark_control",
        "vendor_check_required": False,
        "cost_check_required": False,
        "novelty_rationale": "Rounds out the novelty triangle so the first packet compares parasite-pocket-biased covalent rows inside one interpretable literature frame.",
        "selectivity_note": "Use as a comparator benchmark within the same novelty family, not as an external lead claim.",
        "must_not_do": "Do not present this comparator as independent proof of parasite selectivity.",
        "source_anchor": "DNDi LbDHODH barbituric-acid article",
        "source_url": "https://dndi.org/scientific-articles/2025/barbituric-acid-derivatives-as-covalent-inhibitors-of-leishmania-braziliensis-dihydroorotate-dehydrogenase/",
    },
]

NOVELTY_AXIS_ENUM = "scaffold_novelty ; state_novelty ; condition_novelty ; selectivity_novelty ; benchmark_control"
FIRST_CONTACT_USE_MODE_ENUM = "proceed_now ; comparator_only ; benchmark_control ; hold"
FIRST_CONTACT_PACKET_ARTIFACT = "runs/wetlab_neglected_first_contact_packets_current.md"
TARGET_BRIEF_ARTIFACT = "runs/wetlab_target_brief_lbdhodh_current.md"


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
        "status": "wetlab_lbdhodh_novelty_fill_map_ready",
        "source_lbdhodh_repurposing_fill_map_artifact": "runs/wetlab_lbdhodh_repurposing_fill_map_current.md",
        "target_count": 1,
        "row_count": len(rows),
        "novelty_slot_count": 3,
        "novelty_axis_enum": NOVELTY_AXIS_ENUM,
        "first_contact_use_mode_enum": FIRST_CONTACT_USE_MODE_ENUM,
        "next_required_step": "Render these rows into the LbDHODH target brief, rebuild the neglected first-contact packet, then open the DNDi/IPK follow-on row.",
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Wet-Lab LbDHODH Novelty Fill Map",
        "",
        f"- status: `{s['status']}`",
        f"- source_lbdhodh_repurposing_fill_map_artifact: `{s['source_lbdhodh_repurposing_fill_map_artifact']}`",
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
    parser = argparse.ArgumentParser(description="Build the LbDHODH novelty fill map.")
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
