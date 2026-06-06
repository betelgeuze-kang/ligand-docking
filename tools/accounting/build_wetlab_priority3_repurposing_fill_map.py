#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.wetlab_target_render_utils import materialize_repurposing_rows, maybe_load_json

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SEED_POOL_JSON = "runs/wetlab_priority3_repurposing_seed_pool_current.json"
DEFAULT_BRIEF_FILL_QUEUE_JSON = "runs/wetlab_wave1_brief_fill_queue_current.json"
DEFAULT_PACKET_QUEUE_JSON = "runs/wetlab_wave1_packet_queue_current.json"
DEFAULT_OUT_JSON = "runs/wetlab_priority3_repurposing_fill_map_current.json"
DEFAULT_OUT_CSV = "runs/wetlab_priority3_repurposing_fill_map_current.csv"
DEFAULT_OUT_MD = "runs/wetlab_priority3_repurposing_fill_map_current.md"
DEFAULT_BROAD_SCREEN_AUTOFILL_JSON = "runs/wetlab_broad_screen_repurposing_autofill_current.json"

FIRST_CONTACT_PACKET_FOR_TRACK = {
    "DNDi_IPK": "runs/wetlab_neglected_first_contact_packets_current.md",
    "READDI_Korea": "runs/wetlab_antiviral_first_contact_packets_current.md",
    "oncology_condition_aware": "runs/wetlab_oncology_first_contact_packet_current.md",
}

ROW_POLICY = {
    ("T. cruzi PDE", "Dipyridamole"): {
        "first_contact_use_mode": "proceed_now",
        "selectivity_note": "Disease-facing repurposing seed with Chagas-relevant activity; keep human-PDE deselection in the same packet.",
        "usage_rationale": "Best low-friction disease-facing seed in the neglected rail and the cleanest place to start a cheap first-contact experiment.",
        "must_not_do": "Do not describe this as proof of parasite-specific PDE engagement before the human PDE mini-panel is run.",
        "vendor_check_required": False,
        "cost_check_required": False,
    },
    ("T. cruzi PDE", "Sildenafil"): {
        "first_contact_use_mode": "comparator_only",
        "selectivity_note": "Human-PDE class comparator used to stress-test parasite-vs-human separation, not to claim parasite potency.",
        "usage_rationale": "This gives the external lab a familiar PDE5 benchmark to reject or deprioritize when the selectivity story is working.",
        "must_not_do": "Do not pitch this as a parasite hit or as a lead compound for the Chagas program.",
        "vendor_check_required": False,
        "cost_check_required": False,
    },
    ("T. cruzi PDE", "Tadalafil"): {
        "first_contact_use_mode": "comparator_only",
        "selectivity_note": "Second human-PDE class comparator used to show the packet can reject human-like PDE behavior consistently.",
        "usage_rationale": "Adds a differentiated clinical PDE5 comparator so the selectivity logic is not overfit to sildenafil alone.",
        "must_not_do": "Do not present this as parasite-target evidence or as a priority neglected-disease lead.",
        "vendor_check_required": False,
        "cost_check_required": False,
    },
    ("CA IX", "Acetazolamide"): {
        "first_contact_use_mode": "benchmark_control",
        "selectivity_note": "Canonical carbonic-anhydrase benchmark control; required to verify acidic-arm assay behavior before any CA IX-bias claim.",
        "usage_rationale": "Most recognizable low-friction CA benchmark for oncology labs and the fastest sanity check for the condition-aware buffer setup.",
        "must_not_do": "Do not describe this as CA IX-selective or tumor-selective before CA II and CA XII counterscreens are complete.",
        "vendor_check_required": False,
        "cost_check_required": False,
    },
    ("CA IX", "Methazolamide"): {
        "first_contact_use_mode": "benchmark_control",
        "selectivity_note": "Systemic CA benchmark that broadens the acidic-arm control set beyond acetazolamide.",
        "usage_rationale": "Helps test whether the condition-aware setup behaves consistently across more than one clinically familiar CA scaffold.",
        "must_not_do": "Do not sell this as CA IX-biased or as a tumor-microenvironment-specific hypothesis without counterscreen evidence.",
        "vendor_check_required": False,
        "cost_check_required": False,
    },
    ("CA IX", "Dichlorphenamide"): {
        "first_contact_use_mode": "benchmark_control",
        "selectivity_note": "Second differentiated CA benchmark used to keep the first packet from depending on one sulfonamide control only.",
        "usage_rationale": "Adds scaffold diversity to the benchmark lane while staying inexpensive and assay-friendly.",
        "must_not_do": "Do not frame this as CA IX bias or as a finished oncology candidate before CA II/CA XII deselection is shown.",
        "vendor_check_required": False,
        "cost_check_required": False,
    },
    ("SARS-CoV-2 Mpro", "Nirmatrelvir"): {
        "first_contact_use_mode": "benchmark_control",
        "selectivity_note": "Clinical Mpro benchmark for assay calibration and partner confidence, not the novelty story.",
        "usage_rationale": "Best practical control for proving the Mpro packet can see a real signal before asking a lab to inspect weaker repurposing candidates.",
        "must_not_do": "Do not treat this as the cheap default packet component without an explicit cost/procurement note.",
        "vendor_check_required": False,
        "cost_check_required": True,
    },
    ("SARS-CoV-2 Mpro", "Boceprevir"): {
        "first_contact_use_mode": "proceed_now",
        "selectivity_note": "Direct Mpro literature-backed repurposing seed with known host-protease and procurement checks still required.",
        "usage_rationale": "One of the clearest human-use protease scaffolds with direct Mpro evidence, making it a strong outbound seed once vendor details are checked.",
        "must_not_do": "Do not call this a cheap default or a clean host-liability-free choice until vendor and counterscreen checks are logged.",
        "vendor_check_required": True,
        "cost_check_required": True,
    },
    ("SARS-CoV-2 Mpro", "Telaprevir"): {
        "first_contact_use_mode": "proceed_now",
        "selectivity_note": "Second approved-history protease scaffold seed used to diversify the first Mpro repurposing packet.",
        "usage_rationale": "Useful follow-on scaffold seed for the antiviral rail once procurement and current pricing are explicitly checked.",
        "must_not_do": "Do not present this as a guaranteed low-cost packet component before vendor and host-liability review.",
        "vendor_check_required": True,
        "cost_check_required": True,
    },
}

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


def _rows_by_target(payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in payload.get("rows", []) or []:
        target_id = str(row.get("target_id", "")).strip()
        if not target_id:
            continue
        grouped.setdefault(target_id, []).append(dict(row))
    return grouped


def build_payload(
    seed_pool: dict[str, Any],
    brief_fill_queue: dict[str, Any],
    packet_queue: dict[str, Any],
    broad_screen_autofill: dict[str, Any] | None = None,
) -> dict[str, Any]:
    fill_queue_rows = {str(row.get("target_id", "")): dict(row) for row in brief_fill_queue.get("rows", []) or []}
    packet_queue_rows = {str(row.get("target_id", "")): dict(row) for row in packet_queue.get("rows", []) or []}

    manual_rows_by_target: dict[str, list[dict[str, Any]]] = {}
    for row in seed_pool.get("rows", []) or []:
        target_id = str(row["target_id"])
        queue_row = fill_queue_rows[target_id]
        packet_row = packet_queue_rows[target_id]
        policy = ROW_POLICY[(target_id, str(row["compound_name"]))]
        track_id = str(queue_row["track_id"])
        manual_rows_by_target.setdefault(target_id, []).append(
            {
                "priority_rank": row["priority_rank"],
                "outreach_track_id": track_id,
                "slot_rank": row["slot_rank"],
                "compound_name": row["compound_name"],
                "seed_status": row["seed_status"],
                "brief_slot_name": f"repurposing_{row['slot_rank']}",
                "first_contact_use_mode": policy["first_contact_use_mode"],
                "vendor_check_required": policy["vendor_check_required"],
                "cost_check_required": policy["cost_check_required"],
                "selectivity_note": policy["selectivity_note"],
                "usage_rationale": policy["usage_rationale"],
                "must_not_do": policy["must_not_do"],
                "source_anchor": row["source_anchor"],
                "source_url": row["source_url"],
            }
        )

    rows: list[dict[str, Any]] = []
    bulk_override_target_count = 0
    for target_id, manual_rows in manual_rows_by_target.items():
        queue_row = fill_queue_rows[target_id]
        packet_row = packet_queue_rows[target_id]
        track_id = str(queue_row["track_id"])
        materialized_rows, bulk_override_applied = materialize_repurposing_rows(
            target_id=target_id,
            manual_rows=manual_rows,
            bulk_autofill_payload=broad_screen_autofill,
            target_brief_artifact=queue_row["brief_artifact_planned"],
            first_contact_packet_artifact=FIRST_CONTACT_PACKET_FOR_TRACK[track_id],
            track_label=str(packet_row.get("track_label", "")).strip(),
            default_outreach_track_id=track_id,
        )
        if bulk_override_applied:
            bulk_override_target_count += 1
        rows.extend(materialized_rows)

    by_target = _rows_by_target({"rows": rows})
    targets_with_vendor = sum(1 for target_rows in by_target.values() if any(r["vendor_check_required"] for r in target_rows))
    targets_with_cost = sum(1 for target_rows in by_target.values() if any(r["cost_check_required"] for r in target_rows))
    summary = {
        "status": "wetlab_priority3_repurposing_fill_map_ready",
        "source_seed_pool_artifact": "runs/wetlab_priority3_repurposing_seed_pool_current.md",
        "source_brief_fill_queue_artifact": "runs/wetlab_wave1_brief_fill_queue_current.md",
        "source_packet_queue_artifact": "runs/wetlab_wave1_packet_queue_current.md",
        "priority_target_count": len(by_target),
        "seed_row_count": len(rows),
        "bulk_override_target_count": bulk_override_target_count,
        "usage_enum": USAGE_ENUM,
        "targets_with_vendor_check_count": targets_with_vendor,
        "targets_with_cost_check_count": targets_with_cost,
        "next_required_step": "Render these rows into the three priority target briefs and the matching first-contact packets, then fill novelty lanes for the same targets.",
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Wet-Lab Priority-3 Repurposing Fill Map",
        "",
        f"- status: `{s['status']}`",
        f"- source_seed_pool_artifact: `{s['source_seed_pool_artifact']}`",
        f"- source_brief_fill_queue_artifact: `{s['source_brief_fill_queue_artifact']}`",
        f"- source_packet_queue_artifact: `{s['source_packet_queue_artifact']}`",
        f"- priority_target_count: `{s['priority_target_count']}`",
        f"- seed_row_count: `{s['seed_row_count']}`",
        f"- usage_enum: `{s['usage_enum']}`",
        f"- targets_with_vendor_check_count: `{s['targets_with_vendor_check_count']}`",
        f"- targets_with_cost_check_count: `{s['targets_with_cost_check_count']}`",
        "",
        "| target_id | slot_rank | compound_name | first_contact_use_mode | vendor_check_required | cost_check_required | target_brief_artifact |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['slot_rank']}` | `{row['compound_name']}` | `{row['first_contact_use_mode']}` | `{row['vendor_check_required']}` | `{row['cost_check_required']}` | `{row['target_brief_artifact']}` |"
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
    parser = argparse.ArgumentParser(description="Build the fill map that binds the top-3 priority repurposing seeds to briefs and first-contact packets.")
    parser.add_argument("--seed-pool-json", default=DEFAULT_SEED_POOL_JSON)
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
        _load_json(args.seed_pool_json),
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
