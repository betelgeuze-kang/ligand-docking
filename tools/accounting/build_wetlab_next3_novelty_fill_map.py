#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPURPOSING_FILL_MAP_JSON = "runs/wetlab_next3_repurposing_fill_map_current.json"
DEFAULT_OUT_JSON = "runs/wetlab_next3_novelty_fill_map_current.json"
DEFAULT_OUT_CSV = "runs/wetlab_next3_novelty_fill_map_current.csv"
DEFAULT_OUT_MD = "runs/wetlab_next3_novelty_fill_map_current.md"

FIRST_CONTACT_PACKET_FOR_TRACK = {
    "DNDi_IPK": "runs/wetlab_neglected_first_contact_packets_current.md",
    "READDI_Korea": "runs/wetlab_antiviral_first_contact_packets_current.md",
    "M4K_open_science": "runs/wetlab_wave1_kinase_first_contact_packets_current.md",
}

ROW_SPECS: list[dict[str, Any]] = [
    {
        "priority_rank": 4,
        "target_id": "Cruzain",
        "outreach_track_id": "DNDi_IPK",
        "slot_rank": 1,
        "novelty_compound_name": "ML217 benzimidazole series",
        "novelty_seed_status": "reversible_noncovalent_probe_series",
        "novelty_axis": "scaffold_novelty",
        "brief_slot_name": "novelty_1",
        "first_contact_use_mode": "proceed_now",
        "vendor_check_required": False,
        "cost_check_required": False,
        "novelty_rationale": "Strongest noncovalent Cruzain novelty anchor because it already carries mouse-model efficacy and an explicit reversible-mechanism story.",
        "selectivity_note": "Use this as the clean nonreactive novelty reference rather than as the cheapest procurement-first reagent.",
        "must_not_do": "Do not present the series as solubility-solved; keep procurement and assay-format realism explicit.",
        "source_anchor": "ML217 reversible noncovalent cruzain probe",
        "source_url": "https://www.ncbi.nlm.nih.gov/books/NBK133417/",
    },
    {
        "priority_rank": 4,
        "target_id": "Cruzain",
        "outreach_track_id": "DNDi_IPK",
        "slot_rank": 2,
        "novelty_compound_name": "10j cyclic imide series",
        "novelty_seed_status": "reversible_nonpeptidic_series",
        "novelty_axis": "scaffold_novelty",
        "brief_slot_name": "novelty_2",
        "first_contact_use_mode": "proceed_now",
        "vendor_check_required": False,
        "cost_check_required": False,
        "novelty_rationale": "Adds a reversible nonpeptidic scaffold with intracellular amastigote activity, which is a better partner-facing novelty story than raw electrophile potency.",
        "selectivity_note": "Keep the value proposition on reversible protease engagement plus cell activity, not on brute-force covalent reactivity.",
        "must_not_do": "Do not flatten this into a generic cysteine-protease claim without the host-protease mini-panel.",
        "source_anchor": "10j cyclic imide cruzain series",
        "source_url": "https://pubmed.ncbi.nlm.nih.gov/31824926/",
    },
    {
        "priority_rank": 4,
        "target_id": "Cruzain",
        "outreach_track_id": "DNDi_IPK",
        "slot_rank": 3,
        "novelty_compound_name": "Carbamoyl imidazole series (compound 45-led)",
        "novelty_seed_status": "competitive_nonpeptidic_series",
        "novelty_axis": "selectivity_novelty",
        "brief_slot_name": "novelty_3",
        "first_contact_use_mode": "proceed_now",
        "vendor_check_required": False,
        "cost_check_required": False,
        "novelty_rationale": "Competitive nonpeptidic Cruzain chemistry with in vitro and in vivo support, giving the packet a tractable medicinal-chemistry follow-up lane if the first validation is clean.",
        "selectivity_note": "Best used as the follow-on novelty scaffold rather than the cheapest first assay reagent.",
        "must_not_do": "Do not imply off-the-shelf simplicity; this is a follow-up chemistry lane, not the cheap comparator lane.",
        "source_anchor": "Carbamoyl imidazole cruzain series",
        "source_url": "https://pubmed.ncbi.nlm.nih.gov/31765144/",
    },
    {
        "priority_rank": 5,
        "target_id": "SARS-CoV-2 PLpro",
        "outreach_track_id": "READDI_Korea",
        "slot_rank": 1,
        "novelty_compound_name": "PF-07957472",
        "novelty_seed_status": "oral_plpro_clinical_series",
        "novelty_axis": "selectivity_novelty",
        "brief_slot_name": "novelty_1",
        "first_contact_use_mode": "proceed_now",
        "vendor_check_required": False,
        "cost_check_required": False,
        "novelty_rationale": "Cleanest modern PLpro novelty seed because it already represents an oral, partner-legible scaffold with explicit PLpro optimization rather than only the canonical GRL-0617 story.",
        "selectivity_note": "Use it as the flagship novelty lane for READDI rather than a cheap procurement-first control.",
        "must_not_do": "Do not imply off-the-shelf availability or skip the DUB-first counterscreen because the scaffold is advanced.",
        "source_anchor": "PF-07957472 oral PLpro inhibitor",
        "source_url": "https://doi.org/10.1038/s41467-023-37254-w",
    },
    {
        "priority_rank": 5,
        "target_id": "SARS-CoV-2 PLpro",
        "outreach_track_id": "READDI_Korea",
        "slot_rank": 2,
        "novelty_compound_name": "WEHI-P8",
        "novelty_seed_status": "pancoronavirus_followup_series",
        "novelty_axis": "state_novelty",
        "brief_slot_name": "novelty_2",
        "first_contact_use_mode": "proceed_now",
        "vendor_check_required": False,
        "cost_check_required": False,
        "novelty_rationale": "Strong follow-on PLpro scaffold because it extends the mechanistic story beyond enzyme inhibition into longer-term antiviral phenotype and long-COVID-style disease framing.",
        "selectivity_note": "Good second novelty lane because it keeps the READDI packet focused on partner-relevant antiviral follow-up instead of only crystallography history.",
        "must_not_do": "Do not present this as a cheap comparator or as already procurement-ready without a separate sourcing plan.",
        "source_anchor": "WEHI-P8 PLpro follow-up work",
        "source_url": "https://pubmed.ncbi.nlm.nih.gov/40911642/",
    },
    {
        "priority_rank": 5,
        "target_id": "SARS-CoV-2 PLpro",
        "outreach_track_id": "READDI_Korea",
        "slot_rank": 3,
        "novelty_compound_name": "GRL-0617",
        "novelty_seed_status": "canonical_noncovalent_reference",
        "novelty_axis": "benchmark_control",
        "brief_slot_name": "novelty_3",
        "first_contact_use_mode": "benchmark_control",
        "vendor_check_required": False,
        "cost_check_required": False,
        "novelty_rationale": "Canonical noncovalent PLpro reference scaffold that keeps the packet anchored to the best-known BL2-groove validation point.",
        "selectivity_note": "Best used as the benchmark-control novelty anchor rather than the flagship outbound differentiator.",
        "must_not_do": "Do not market this as novel chemistry; its value is that it stabilizes the rest of the PLpro packet.",
        "source_anchor": "GRL-0617 PLpro structure-led reference",
        "source_url": "https://pubmed.ncbi.nlm.nih.gov/33473130/",
    },
    {
        "priority_rank": 6,
        "target_id": "ALK2",
        "outreach_track_id": "M4K_open_science",
        "slot_rank": 1,
        "novelty_compound_name": "M4K2009",
        "novelty_seed_status": "open_science_benchmark_series",
        "novelty_axis": "scaffold_novelty",
        "brief_slot_name": "novelty_1",
        "first_contact_use_mode": "proceed_now",
        "vendor_check_required": False,
        "cost_check_required": False,
        "novelty_rationale": "Open-science benchmark novelty scaffold that ties the packet directly to the public M4K ALK2 chemistry story.",
        "selectivity_note": "Use as the anchor novelty benchmark, with the hERG caveat stated rather than buried.",
        "must_not_do": "Do not present it as the liability-solved endpoint of the ALK2 chemistry story.",
        "source_anchor": "M4K2009 open-science ALK2 series",
        "source_url": "https://pubmed.ncbi.nlm.nih.gov/32369358/",
    },
    {
        "priority_rank": 6,
        "target_id": "ALK2",
        "outreach_track_id": "M4K_open_science",
        "slot_rank": 2,
        "novelty_compound_name": "M4K2149",
        "novelty_seed_status": "liability_optimized_open_science_series",
        "novelty_axis": "selectivity_novelty",
        "brief_slot_name": "novelty_2",
        "first_contact_use_mode": "proceed_now",
        "vendor_check_required": False,
        "cost_check_required": False,
        "novelty_rationale": "Best selectivity/liability-flavored follow-on within the same open-science series because it keeps potency while lowering the most obvious ion-channel concern.",
        "selectivity_note": "Use it to answer the usual ALK2 objection that novelty chemistry will collapse under liability review.",
        "must_not_do": "Do not pretend this resolves every CNS or selectivity issue; it is the better open-science follow-on, not the finished drug.",
        "source_anchor": "M4K2149 open-science ALK2 follow-on",
        "source_url": "https://pubmed.ncbi.nlm.nih.gov/32369358/",
    },
    {
        "priority_rank": 6,
        "target_id": "ALK2",
        "outreach_track_id": "M4K_open_science",
        "slot_rank": 3,
        "novelty_compound_name": "M4K2304",
        "novelty_seed_status": "next_generation_brain_penetrant_series",
        "novelty_axis": "state_novelty",
        "brief_slot_name": "novelty_3",
        "first_contact_use_mode": "proceed_now",
        "vendor_check_required": False,
        "cost_check_required": False,
        "novelty_rationale": "Flagship next-generation novelty scaffold because it pushes the open-science ALK2 story into a more selective and brain-exposure-aware chemical space.",
        "selectivity_note": "Best used as the aspirational open-science lead, not as the cheapest validation reagent.",
        "must_not_do": "Do not present this as off-the-shelf repurposing chemistry; it belongs in the novelty lane precisely because it is the flagship open-science scaffold.",
        "source_anchor": "M4K2304 next-generation ALK2 series",
        "source_url": "https://pubmed.ncbi.nlm.nih.gov/38498998/",
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
            "Cruzain": "runs/wetlab_target_brief_cruzain_current.md",
            "SARS-CoV-2 PLpro": "runs/wetlab_target_brief_sarscov2_plpro_current.md",
            "ALK2": "runs/wetlab_target_brief_alk2_current.md",
        }[str(spec["target_id"])]
        row["first_contact_packet_artifact"] = FIRST_CONTACT_PACKET_FOR_TRACK[str(spec["outreach_track_id"])]
        row["novelty_fill_status"] = "ready"
        row["row_status"] = "ready"
        if rep_rows.get(str(spec["target_id"])):
            row["source_repurposing_fill_bound"] = True
        rows.append(row)

    target_ids = sorted({str(row["target_id"]) for row in rows})
    summary = {
        "status": "wetlab_next3_novelty_fill_map_ready",
        "source_next3_repurposing_fill_map_artifact": "runs/wetlab_next3_repurposing_fill_map_current.md",
        "next3_target_count": len(target_ids),
        "row_count": len(rows),
        "novelty_slot_count": 3,
        "novelty_axis_enum": NOVELTY_AXIS_ENUM,
        "first_contact_use_mode_enum": FIRST_CONTACT_USE_MODE_ENUM,
        "next_required_step": "Render these rows into the Cruzain, PLpro, and ALK2 target briefs, then rebuild the neglected, antiviral, and kinase rail packets for outbound use.",
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Wet-Lab Next-3 Novelty Fill Map",
        "",
        f"- status: `{s['status']}`",
        f"- source_next3_repurposing_fill_map_artifact: `{s['source_next3_repurposing_fill_map_artifact']}`",
        f"- next3_target_count: `{s['next3_target_count']}`",
        f"- row_count: `{s['row_count']}`",
        f"- novelty_slot_count: `{s['novelty_slot_count']}`",
        f"- novelty_axis_enum: `{s['novelty_axis_enum']}`",
        f"- first_contact_use_mode_enum: `{s['first_contact_use_mode_enum']}`",
        "",
        "| target_id | slot_rank | novelty_compound_name | first_contact_use_mode | novelty_axis | target_brief_artifact |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['slot_rank']}` | `{row['novelty_compound_name']}` | `{row['first_contact_use_mode']}` | `{row['novelty_axis']}` | `{row['target_brief_artifact']}` |"
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
    parser = argparse.ArgumentParser(description="Build the novelty fill map for the next three Wave 1 targets.")
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
