#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPURPOSING_FILL_MAP_JSON = "runs/wetlab_priority3_repurposing_fill_map_current.json"
DEFAULT_OUT_JSON = "runs/wetlab_priority3_novelty_fill_map_current.json"
DEFAULT_OUT_CSV = "runs/wetlab_priority3_novelty_fill_map_current.csv"
DEFAULT_OUT_MD = "runs/wetlab_priority3_novelty_fill_map_current.md"

FIRST_CONTACT_PACKET_FOR_TRACK = {
    "DNDi_IPK": "runs/wetlab_neglected_first_contact_packets_current.md",
    "READDI_Korea": "runs/wetlab_antiviral_first_contact_packets_current.md",
    "oncology_condition_aware": "runs/wetlab_oncology_first_contact_packet_current.md",
}

ROW_SPECS: list[dict[str, Any]] = [
    {
        "priority_rank": 1,
        "target_id": "T. cruzi PDE",
        "outreach_track_id": "DNDi_IPK",
        "slot_rank": 1,
        "novelty_compound_name": "NPD-227 pyrazolone series",
        "novelty_seed_status": "mouse_validated_pyrazolone_series",
        "novelty_axis": "scaffold_novelty",
        "brief_slot_name": "novelty_1",
        "first_contact_use_mode": "proceed_now",
        "vendor_check_required": False,
        "cost_check_required": False,
        "novelty_rationale": "Pyrazolone-series PDE inhibitors already showed in vivo Chagas efficacy, so they are the cleanest novelty lane for a parasite-first packet rather than just a human-PDE class echo.",
        "selectivity_note": "Treat this as a parasite-PDE novelty series only if the human PDE mini-panel remains in the same first packet.",
        "must_not_do": "Do not describe the series as human-PDE de-risked without the paired mammalian PDE deselection data.",
        "source_anchor": "NPD-227 pyrazolone TcrPDEC series",
        "source_url": "https://www.scielo.br/j/mioc/a/xXMmWpP9qNQKQsB4DNSV7BQ/?format=pdf&lang=en",
    },
    {
        "priority_rank": 1,
        "target_id": "T. cruzi PDE",
        "outreach_track_id": "DNDi_IPK",
        "slot_rank": 2,
        "novelty_compound_name": "NPD-008 tetrahydrophthalazinone series",
        "novelty_seed_status": "tetrahydrophthalazinone_pocket_validated_series",
        "novelty_axis": "selectivity_novelty",
        "brief_slot_name": "novelty_2",
        "first_contact_use_mode": "proceed_now",
        "vendor_check_required": False,
        "cost_check_required": False,
        "novelty_rationale": "The tetrahydrophthalazinone scaffold was optimized around parasite PDE pocket shape and remains one of the best literature-backed routes to parasite-biased PDE engagement.",
        "selectivity_note": "Keep the story focused on parasite-pocket fit and not on blanket PDE inhibition.",
        "must_not_do": "Do not present this as a cheap off-the-shelf comparator; it is a novelty chemistry lane that still needs selective wet-lab confirmation.",
        "source_anchor": "NPD-008 tetrahydrophthalazinone TcrPDEC series",
        "source_url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC8092546/",
    },
    {
        "priority_rank": 1,
        "target_id": "T. cruzi PDE",
        "outreach_track_id": "DNDi_IPK",
        "slot_rank": 3,
        "novelty_compound_name": "GVK14 xanthine-inspired series",
        "novelty_seed_status": "xanthine_analog_selectivity_series",
        "novelty_axis": "selectivity_novelty",
        "brief_slot_name": "novelty_3",
        "first_contact_use_mode": "proceed_now",
        "vendor_check_required": False,
        "cost_check_required": False,
        "novelty_rationale": "GVK14 gives the neglected packet a second distinct parasite-PDE chemical logic and was reported without meaningful inhibition of representative mammalian cAMP PDEs.",
        "selectivity_note": "Use this as the xanthine-inspired selectivity stress test rather than as a default potency claim.",
        "must_not_do": "Do not collapse this into the human PDE comparator lane just because the scaffold family is familiar.",
        "source_anchor": "GVK14 xanthine analog T. cruzi series",
        "source_url": "https://www.mdpi.com/2036-7481/13/4/52",
    },
    {
        "priority_rank": 2,
        "target_id": "CA IX",
        "outreach_track_id": "oncology_condition_aware",
        "slot_rank": 1,
        "novelty_compound_name": "SLC-0111 ureido-benzenesulfonamide",
        "novelty_seed_status": "clinical_grade_caix_selective_reference",
        "novelty_axis": "selectivity_novelty",
        "brief_slot_name": "novelty_1",
        "first_contact_use_mode": "proceed_now",
        "vendor_check_required": False,
        "cost_check_required": False,
        "novelty_rationale": "SLC-0111 is the cleanest CA IX/XII-selective reference scaffold to separate the novelty lane from generic benchmark sulfonamides in acidic tumor-like buffer.",
        "selectivity_note": "Use this as the explicit CA IX-biased novelty anchor against the acetazolamide-class controls.",
        "must_not_do": "Do not present it as if CA II and CA XII deselection are optional; the selectivity story is the point.",
        "source_anchor": "SLC-0111 CA IX/XII-selective inhibitor",
        "source_url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC4258300/",
    },
    {
        "priority_rank": 2,
        "target_id": "CA IX",
        "outreach_track_id": "oncology_condition_aware",
        "slot_rank": 2,
        "novelty_compound_name": "SLC-149 noncatalytic-function CAIX series",
        "novelty_seed_status": "noncatalytic_caix_function_series",
        "novelty_axis": "state_novelty",
        "brief_slot_name": "novelty_2",
        "first_contact_use_mode": "proceed_now",
        "vendor_check_required": False,
        "cost_check_required": False,
        "novelty_rationale": "SLC-149 broadens the CA IX lane beyond catalytic zinc-site inhibition and gives the packet a state/function angle that a flat CA inhibitor screen cannot show.",
        "selectivity_note": "Use this to test whether the packet can recognize CA IX biology beyond generic catalytic blockade.",
        "must_not_do": "Do not mix this with the benchmark-control narrative; it belongs in the novelty lane because the mechanism story is different.",
        "source_anchor": "SLC-149 noncatalytic CAIX inhibitor",
        "source_url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC10440061/",
    },
    {
        "priority_rank": 2,
        "target_id": "CA IX",
        "outreach_track_id": "oncology_condition_aware",
        "slot_rank": 3,
        "novelty_compound_name": "Callitrisic acid allosteric CA IX series",
        "novelty_seed_status": "allosteric_hypoxic_caix_series",
        "novelty_axis": "condition_novelty",
        "brief_slot_name": "novelty_3",
        "first_contact_use_mode": "proceed_now",
        "vendor_check_required": False,
        "cost_check_required": False,
        "novelty_rationale": "Callitrisic-acid derivatives give the condition-aware rail a non-sulfonamide, allosteric CA IX option with an explicit hypoxic-tumor pH rationale.",
        "selectivity_note": "Keep this in the packet as the condition-aware contrast to catalytic sulfonamides, not as a drop-in benchmark control.",
        "must_not_do": "Do not flatten this into a generic CA inhibitor claim; its value is the condition-aware and allosteric story.",
        "source_anchor": "Callitrisic acid allosteric CA IX inhibitor",
        "source_url": "https://openaccess.bezmialem.edu.tr/bitstreams/b7b93d76-2bdf-4f85-80d8-04fe2f0fe628/download",
    },
    {
        "priority_rank": 3,
        "target_id": "SARS-CoV-2 Mpro",
        "outreach_track_id": "READDI_Korea",
        "slot_rank": 1,
        "novelty_compound_name": "WU-04 noncovalent 3CLpro series",
        "novelty_seed_status": "phase3_noncovalent_scaffold_series",
        "novelty_axis": "scaffold_novelty",
        "brief_slot_name": "novelty_1",
        "first_contact_use_mode": "proceed_now",
        "vendor_check_required": False,
        "cost_check_required": False,
        "novelty_rationale": "WU-04 gives the antiviral packet a clearly distinct noncovalent scaffold with resistance-learning value beyond the boceprevir/telaprevir lane.",
        "selectivity_note": "Use it as the cleanest noncovalent novelty anchor rather than as a cheap procurement-first option.",
        "must_not_do": "Do not call this resistance-proof; the M49/M165 liability is exactly why it belongs in a controlled novelty lane.",
        "source_anchor": "WU-04 noncovalent 3CLpro discovery and resistance work",
        "source_url": "https://www.nature.com/articles/s41421-024-00673-0",
    },
    {
        "priority_rank": 3,
        "target_id": "SARS-CoV-2 Mpro",
        "outreach_track_id": "READDI_Korea",
        "slot_rank": 2,
        "novelty_compound_name": "Ensitrelvir (S-217622)",
        "novelty_seed_status": "approved_noncovalent_mpro_reference",
        "novelty_axis": "state_novelty",
        "brief_slot_name": "novelty_2",
        "first_contact_use_mode": "comparator_only",
        "vendor_check_required": False,
        "cost_check_required": False,
        "novelty_rationale": "Ensitrelvir is the cleanest clinically validated noncovalent Mpro comparator and lets the packet benchmark dynamic-pocket claims against an approved noncovalent reference.",
        "selectivity_note": "Treat it as the noncovalent reference comparator for the novelty lane, not as the cheap outbound default.",
        "must_not_do": "Do not package this as the cost-sensitive lead compound without a separate procurement discussion.",
        "source_anchor": "Ensitrelvir S-217622 Mpro paper",
        "source_url": "https://pubmed.ncbi.nlm.nih.gov/36327352/",
    },
    {
        "priority_rank": 3,
        "target_id": "SARS-CoV-2 Mpro",
        "outreach_track_id": "READDI_Korea",
        "slot_rank": 3,
        "novelty_compound_name": "Simnotrelvir (SIM0417)",
        "novelty_seed_status": "oral_follow_on_covalent_mpro_series",
        "novelty_axis": "selectivity_novelty",
        "brief_slot_name": "novelty_3",
        "first_contact_use_mode": "comparator_only",
        "vendor_check_required": False,
        "cost_check_required": False,
        "novelty_rationale": "Simnotrelvir gives the packet a second clinically legible Mpro scaffold family and helps distinguish true pocket-generalization from overfitting to the nirmatrelvir lineage.",
        "selectivity_note": "Use it as a clinically legible comparator for covalent pocket occupancy rather than as the cheapest first outbound reagent.",
        "must_not_do": "Do not oversell it as unrelated chemistry; it is valuable because it sits near the clinical lineage and tests whether the packet still generalizes.",
        "source_anchor": "Simnotrelvir oral 3CLpro inhibitor paper",
        "source_url": "https://www.nature.com/articles/s41467-021-23751-3.pdf",
    },
]

NOVELTY_AXIS_ENUM = "scaffold_novelty ; state_novelty ; condition_novelty ; selectivity_novelty"
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


def _rows_by_target(payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in payload.get("rows", []) or []:
        target_id = str(row.get("target_id", "")).strip()
        if not target_id:
            continue
        grouped.setdefault(target_id, []).append(dict(row))
    return grouped


def build_payload(repurposing_fill_map: dict[str, Any] | None = None) -> dict[str, Any]:
    rep_rows = _rows_by_target(repurposing_fill_map or {})
    rows: list[dict[str, Any]] = []
    for spec in ROW_SPECS:
        row = dict(spec)
        row["target_brief_artifact"] = {
            "T. cruzi PDE": "runs/wetlab_target_brief_tcruzi_pde_current.md",
            "CA IX": "runs/wetlab_target_brief_caix_current.md",
            "SARS-CoV-2 Mpro": "runs/wetlab_target_brief_sarscov2_mpro_current.md",
        }[str(spec["target_id"])]
        row["first_contact_packet_artifact"] = FIRST_CONTACT_PACKET_FOR_TRACK[str(spec["outreach_track_id"])]
        row["novelty_fill_status"] = "ready"
        row["row_status"] = "ready"
        if rep_rows.get(str(spec["target_id"])):
            row["source_priority_fill_bound"] = True
        rows.append(row)

    by_target = _rows_by_target({"rows": rows})
    summary = {
        "status": "wetlab_priority3_novelty_fill_map_ready",
        "source_priority3_repurposing_fill_map_artifact": "runs/wetlab_priority3_repurposing_fill_map_current.md",
        "source_target_brief_index_artifact": "runs/wetlab_wave1_target_brief_index_current.md",
        "source_first_contact_brief_bundle_artifact": "runs/wetlab_first_contact_brief_bundle_current.md",
        "priority_target_count": len(by_target),
        "row_count": len(rows),
        "novelty_slot_count": 3,
        "novelty_axis_enum": NOVELTY_AXIS_ENUM,
        "first_contact_use_mode_enum": FIRST_CONTACT_USE_MODE_ENUM,
        "next_required_step": "Render these rows into the three priority target briefs and first-contact packets, then gate outbound export with the Mpro vendor/cost check.",
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Wet-Lab Priority-3 Novelty Fill Map",
        "",
        f"- status: `{s['status']}`",
        f"- source_priority3_repurposing_fill_map_artifact: `{s['source_priority3_repurposing_fill_map_artifact']}`",
        f"- source_target_brief_index_artifact: `{s['source_target_brief_index_artifact']}`",
        f"- source_first_contact_brief_bundle_artifact: `{s['source_first_contact_brief_bundle_artifact']}`",
        f"- priority_target_count: `{s['priority_target_count']}`",
        f"- row_count: `{s['row_count']}`",
        f"- novelty_slot_count: `{s['novelty_slot_count']}`",
        f"- novelty_axis_enum: `{s['novelty_axis_enum']}`",
        f"- first_contact_use_mode_enum: `{s['first_contact_use_mode_enum']}`",
        "",
        "| target_id | slot_rank | novelty_compound_name | novelty_axis | first_contact_use_mode | target_brief_artifact |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['slot_rank']}` | `{row['novelty_compound_name']}` | `{row['novelty_axis']}` | `{row['first_contact_use_mode']}` | `{row['target_brief_artifact']}` |"
        )
    lines.extend(["", "## Usage Notes", ""])
    current_target = None
    for row in payload["rows"]:
        if row["target_id"] != current_target:
            current_target = row["target_id"]
            lines.extend([f"### {current_target}", ""])
        lines.extend(
            [
                f"- `{row['novelty_compound_name']}` -> `{row['first_contact_use_mode']}` via `{row['brief_slot_name']}`",
                f"  Axis: `{row['novelty_axis']}`",
                f"  Rationale: {row['novelty_rationale']}",
                f"  Selectivity note: {row['selectivity_note']}",
                f"  Must not do: {row['must_not_do']}",
                f"  Source: `{row['source_anchor']}` ({row['source_url']})",
            ]
        )
    lines.extend(["", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the novelty fill map for the three priority outbound wet-lab targets.")
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
