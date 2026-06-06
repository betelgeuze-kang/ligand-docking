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
DEFAULT_OUT_JSON = "runs/wetlab_next3_repurposing_fill_map_current.json"
DEFAULT_OUT_CSV = "runs/wetlab_next3_repurposing_fill_map_current.csv"
DEFAULT_OUT_MD = "runs/wetlab_next3_repurposing_fill_map_current.md"
DEFAULT_BROAD_SCREEN_AUTOFILL_JSON = "runs/wetlab_broad_screen_repurposing_autofill_current.json"

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
        "compound_name": "Benidipine",
        "seed_status": "repurposing_literature_anchor",
        "brief_slot_name": "repurposing_1",
        "first_contact_use_mode": "proceed_now",
        "vendor_check_required": False,
        "cost_check_required": False,
        "selectivity_note": "Direct cruzipain-repositioning seed with host cysteine-protease and aggregation filters still required on day one.",
        "usage_rationale": "Best disease-facing cheap-validation seed for Cruzain because the same repositioning paper and follow-on mouse work keep the enzyme story connected to Chagas efficacy.",
        "must_not_do": "Do not describe this as Cruzain-selective before host cysteine-protease counterscreens and fluorogenic-assay interference checks are complete.",
        "source_anchor": "Benidipine cruzipain repositioning series",
        "source_url": "https://pubmed.ncbi.nlm.nih.gov/25707014/",
    },
    {
        "priority_rank": 4,
        "target_id": "Cruzain",
        "outreach_track_id": "DNDi_IPK",
        "slot_rank": 2,
        "compound_name": "Clofazimine",
        "seed_status": "repurposing_literature_anchor",
        "brief_slot_name": "repurposing_2",
        "first_contact_use_mode": "proceed_now",
        "vendor_check_required": False,
        "cost_check_required": False,
        "selectivity_note": "Disease-facing repositioning seed that needs fluorescence, aggregation, and host-protease sanity checks before any protease-specific claim.",
        "usage_rationale": "Strong second low-friction seed because cruzipain validation was carried through into chronic Chagas in vivo follow-up, making it a credible partner-facing comparator.",
        "must_not_do": "Do not oversell this as a clean enzymology tool without explicitly flagging lipophilicity and assay-artifact risk.",
        "source_anchor": "Clofazimine cruzipain repositioning follow-up",
        "source_url": "https://pubmed.ncbi.nlm.nih.gov/27216381/",
    },
    {
        "priority_rank": 4,
        "target_id": "Cruzain",
        "outreach_track_id": "DNDi_IPK",
        "slot_rank": 3,
        "compound_name": "Bromocriptine",
        "seed_status": "repurposing_literature_anchor",
        "brief_slot_name": "repurposing_3",
        "first_contact_use_mode": "comparator_only",
        "vendor_check_required": False,
        "cost_check_required": False,
        "selectivity_note": "Useful cheap-validation comparator with direct cruzain inhibition, but broad CNS and endocrine polypharmacology keep it in the guarded lane.",
        "usage_rationale": "Adds a third clinically familiar scaffold with direct cruzain evidence without pretending it is a clean neglected-disease lead.",
        "must_not_do": "Do not frame this as a disease-facing lead or as mechanistically clean Cruzain evidence without broader liability review.",
        "source_anchor": "Bromocriptine cruzain DrugBank repositioning study",
        "source_url": "https://doi.org/10.1021/ci400284v",
    },
    {
        "priority_rank": 5,
        "target_id": "SARS-CoV-2 PLpro",
        "outreach_track_id": "READDI_Korea",
        "slot_rank": 1,
        "compound_name": "Sitagliptin",
        "seed_status": "repurposing_literature_anchor",
        "brief_slot_name": "repurposing_1",
        "first_contact_use_mode": "proceed_now",
        "vendor_check_required": False,
        "cost_check_required": False,
        "selectivity_note": "Cheap approved PLpro repurposing seed with direct in-cell antiviral data; still keep human DUB counterscreens in the first packet.",
        "usage_rationale": "Best low-friction PLpro outbound seed because it is approved, inexpensive, and already tied to a live-cell PLpro assay rather than only docking.",
        "must_not_do": "Do not present this as host-liability-free or as a pandemic-proof lead before the DUB counterscreen is run.",
        "source_anchor": "Sitagliptin PLpro in-cell inhibitor",
        "source_url": "https://www.nature.com/articles/s42003-022-03090-9",
    },
    {
        "priority_rank": 5,
        "target_id": "SARS-CoV-2 PLpro",
        "outreach_track_id": "READDI_Korea",
        "slot_rank": 2,
        "compound_name": "Daclatasvir",
        "seed_status": "repurposing_literature_anchor",
        "brief_slot_name": "repurposing_2",
        "first_contact_use_mode": "proceed_now",
        "vendor_check_required": False,
        "cost_check_required": False,
        "selectivity_note": "Approved antiviral comparator with PLpro activity in cells, but likely allosteric and still dependent on DUB-first counterscreen logic.",
        "usage_rationale": "Gives the PLpro packet a second clinically legible and easy-to-procure seed that does not depend on generic cysteine-reactive chemistry.",
        "must_not_do": "Do not claim active-site mechanism certainty or skip the host DUB counterscreen because the likely binding mode is not cleanly catalytic-site only.",
        "source_anchor": "Daclatasvir PLpro in-cell inhibitor",
        "source_url": "https://www.nature.com/articles/s42003-022-03090-9",
    },
    {
        "priority_rank": 5,
        "target_id": "SARS-CoV-2 PLpro",
        "outreach_track_id": "READDI_Korea",
        "slot_rank": 3,
        "compound_name": "6-Thioguanine",
        "seed_status": "repurposing_literature_anchor",
        "brief_slot_name": "repurposing_3",
        "first_contact_use_mode": "comparator_only",
        "vendor_check_required": False,
        "cost_check_required": False,
        "selectivity_note": "Useful approved comparator with direct PLpro literature, but immune and host-liability baggage keep it in the guarded comparator lane.",
        "usage_rationale": "Adds a cheap, clinically familiar PLpro reference compound that helps stress-test the READDI packet beyond the sitagliptin and daclatasvir pair.",
        "must_not_do": "Do not present this as the clean primary antiviral candidate or as a host-liability-light choice.",
        "source_anchor": "6-thioguanine PLpro replication study",
        "source_url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC8487320/",
    },
    {
        "priority_rank": 6,
        "target_id": "ALK2",
        "outreach_track_id": "M4K_open_science",
        "slot_rank": 1,
        "compound_name": "Vandetanib",
        "seed_status": "repurposing_literature_anchor",
        "brief_slot_name": "repurposing_1",
        "first_contact_use_mode": "proceed_now",
        "vendor_check_required": False,
        "cost_check_required": False,
        "selectivity_note": "Clinically familiar ALK2/ACVR1 repurposing seed with direct DIPG relevance, but still requires mutant-versus-wild-type and kinase-neighborhood separation.",
        "usage_rationale": "Strongest repurposing-facing ALK2 packet lead because the DIPG story is already explicit rather than inferred from general kinase similarity.",
        "must_not_do": "Do not oversell this as a solved CNS monotherapy story; the strongest literature frame is still combination-aware and selectivity-sensitive.",
        "source_anchor": "Vandetanib ACVR1-mutant DIPG study",
        "source_url": "https://pubmed.ncbi.nlm.nih.gov/34551970/",
    },
    {
        "priority_rank": 6,
        "target_id": "ALK2",
        "outreach_track_id": "M4K_open_science",
        "slot_rank": 2,
        "compound_name": "Momelotinib",
        "seed_status": "repurposing_literature_anchor",
        "brief_slot_name": "repurposing_2",
        "first_contact_use_mode": "proceed_now",
        "vendor_check_required": False,
        "cost_check_required": False,
        "selectivity_note": "Approved oral ACVR1/ALK2-active seed that brings strong translational legibility, but JAK baggage means it still needs close-kinase framing.",
        "usage_rationale": "Best approved fallback compound for an ALK2 packet because it gives the first-contact deck a genuinely drug-like repurposing anchor.",
        "must_not_do": "Do not present this as ALK2-selective or as a DIPG-tailored compound before the close-kinase mini-panel is complete.",
        "source_anchor": "Momelotinib ACVR1 inhibitor paper",
        "source_url": "https://pubmed.ncbi.nlm.nih.gov/28188131/",
    },
    {
        "priority_rank": 6,
        "target_id": "ALK2",
        "outreach_track_id": "M4K_open_science",
        "slot_rank": 3,
        "compound_name": "LDN-214117",
        "seed_status": "validation_benchmark_anchor",
        "brief_slot_name": "repurposing_3",
        "first_contact_use_mode": "benchmark_control",
        "vendor_check_required": False,
        "cost_check_required": False,
        "selectivity_note": "Direct ALK2 benchmark rather than repurposing proof; useful because it already links brain exposure, orthotopic efficacy, and ACVR1 biology.",
        "usage_rationale": "Best positive-control-style bridge between repurposing and M4K novelty chemistry for a cheap mutant-aware kinase validation packet.",
        "must_not_do": "Do not package this as an approved repositioning candidate; use it as the validation anchor it actually is.",
        "source_anchor": "LDN-214117 DIPG ALK2 benchmark",
        "source_url": "https://pubmed.ncbi.nlm.nih.gov/31098401/",
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

    manual_rows_by_target: dict[str, list[dict[str, Any]]] = {}
    for spec in ROW_SPECS:
        manual_rows_by_target.setdefault(str(spec["target_id"]), []).append(dict(spec))

    rows: list[dict[str, Any]] = []
    bulk_override_target_count = 0
    for target_id, manual_rows in manual_rows_by_target.items():
        queue_row = fill_queue_rows[target_id]
        packet_row = packet_queue_rows[target_id]
        track_id = str(manual_rows[0]["outreach_track_id"])
        materialized_rows, bulk_override_applied = materialize_repurposing_rows(
            target_id=target_id,
            manual_rows=manual_rows,
            bulk_autofill_payload=broad_screen_autofill,
            target_brief_artifact=queue_row["brief_artifact_planned"],
            first_contact_packet_artifact=FIRST_CONTACT_PACKET_FOR_TRACK[track_id],
            track_label=packet_row["track_label"],
            default_outreach_track_id=track_id,
        )
        if bulk_override_applied:
            bulk_override_target_count += 1
        rows.extend(materialized_rows)

    target_ids = sorted({str(row["target_id"]) for row in rows})
    summary = {
        "status": "wetlab_next3_repurposing_fill_map_ready",
        "source_brief_fill_queue_artifact": "runs/wetlab_wave1_brief_fill_queue_current.md",
        "source_packet_queue_artifact": "runs/wetlab_wave1_packet_queue_current.md",
        "next3_target_count": len(target_ids),
        "row_count": len(rows),
        "bulk_override_target_count": bulk_override_target_count,
        "usage_enum": USAGE_ENUM,
        "next_required_step": "Render these rows into the Cruzain, PLpro, and ALK2 target briefs, then rebuild the neglected, antiviral, and kinase rail packets so the next outbound lanes are opened.",
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Wet-Lab Next-3 Repurposing Fill Map",
        "",
        f"- status: `{s['status']}`",
        f"- source_brief_fill_queue_artifact: `{s['source_brief_fill_queue_artifact']}`",
        f"- source_packet_queue_artifact: `{s['source_packet_queue_artifact']}`",
        f"- next3_target_count: `{s['next3_target_count']}`",
        f"- row_count: `{s['row_count']}`",
        f"- usage_enum: `{s['usage_enum']}`",
        "",
        "| target_id | slot_rank | compound_name | first_contact_use_mode | target_brief_artifact |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['slot_rank']}` | `{row['compound_name']}` | `{row['first_contact_use_mode']}` | `{row['target_brief_artifact']}` |"
        )
    lines.extend(["", "## Usage Notes", ""])
    current_target = None
    for row in payload["rows"]:
        if row["target_id"] != current_target:
            current_target = row["target_id"]
            lines.extend([f"### {current_target}", ""])
        lines.extend(
            [
                f"- `{row['compound_name']}` -> `{row['first_contact_use_mode']}` via `{row['brief_slot_name']}`",
                f"  Rationale: {row['usage_rationale']}",
                f"  Selectivity note: {row['selectivity_note']}",
                f"  Must not do: {row['must_not_do']}",
                f"  Source: `{row['source_anchor']}` ({row['source_url']})",
            ]
        )
    lines.extend(["", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the repurposing fill map for the next three Wave 1 targets.")
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
