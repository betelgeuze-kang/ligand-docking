#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.wetlab_target_render_utils import materialize_repurposing_rows, maybe_load_json

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/wetlab_dengue_ns2b_ns3_protease_repurposing_fill_map_current.json"
DEFAULT_OUT_CSV = "runs/wetlab_dengue_ns2b_ns3_protease_repurposing_fill_map_current.csv"
DEFAULT_OUT_MD = "runs/wetlab_dengue_ns2b_ns3_protease_repurposing_fill_map_current.md"
DEFAULT_BROAD_SCREEN_AUTOFILL_JSON = "runs/wetlab_broad_screen_repurposing_autofill_current.json"
DEFAULT_TARGET_BRIEF_ARTIFACT = "runs/wetlab_target_brief_dengue_ns2b_ns3_protease_current.md"
DEFAULT_TRACK_LABEL = "IPK dengue antiviral rail"
FIRST_CONTACT_PACKET_ARTIFACT = "runs/dengue_ns2b_ns3_protease_launch_packet_current.md"

ROW_SPECS: list[dict[str, Any]] = [
    {
        "priority_rank": 9,
        "target_id": "Dengue NS2B-NS3 protease",
        "outreach_track_id": "IPK_dengue",
        "slot_rank": 1,
        "compound_name": "Eltrombopag",
        "seed_status": "approved_allosteric_benchmark",
        "brief_slot_name": "repurposing_1",
        "first_contact_use_mode": "proceed_now",
        "vendor_check_required": False,
        "cost_check_required": False,
        "selectivity_note": "Use as the primary approved-drug benchmark because the literature places eltrombopag at a dengue-protease allosteric site rather than a generic sticky flaviviral screen hit.",
        "usage_rationale": "Best first proceed-now row for the IPK dengue packet because it is approved, mechanistically legible, and directly tied to NS2B-NS3 protease inhibition.",
        "must_not_do": "Do not present eltrombopag as clinically validated for dengue; its role here is to anchor a bounded protease-focused repurposing test.",
        "source_anchor": "Eltrombopag allosteric dengue protease paper",
        "source_url": "https://pubmed.ncbi.nlm.nih.gov/40447137/",
    },
    {
        "priority_rank": 9,
        "target_id": "Dengue NS2B-NS3 protease",
        "outreach_track_id": "IPK_dengue",
        "slot_rank": 2,
        "compound_name": "Policresulen",
        "seed_status": "approved_old_drug_protease_hit",
        "brief_slot_name": "repurposing_2",
        "first_contact_use_mode": "benchmark_control",
        "vendor_check_required": False,
        "cost_check_required": False,
        "selectivity_note": "Keep this row tied to the flaviviral orthogonal panel; the value is that an old-drug library hit reached both enzymology and cell replication readouts, not that it is already cleanly selective.",
        "usage_rationale": "Good benchmark-control row because it gives the packet a low-cost old-drug hit from a direct DENV2 NS2B-NS3 protease screen.",
        "must_not_do": "Do not infer that policresulen is safe or development-ready for systemic dengue use; keep it framed as a cheap validation anchor.",
        "source_anchor": "Policresulen old-drug dengue protease paper",
        "source_url": "https://pubmed.ncbi.nlm.nih.gov/26279156/",
    },
    {
        "priority_rank": 9,
        "target_id": "Dengue NS2B-NS3 protease",
        "outreach_track_id": "IPK_dengue",
        "slot_rank": 3,
        "compound_name": "Boceprevir",
        "seed_status": "approved_protease_class_comparator",
        "brief_slot_name": "repurposing_3",
        "first_contact_use_mode": "comparator_only",
        "vendor_check_required": False,
        "cost_check_required": False,
        "selectivity_note": "Use as a protease-class comparator to stress-test whether the packet is only rewarding generic protease-like chemistry or a cleaner dengue NS2B-NS3 story.",
        "usage_rationale": "Rounds out the approved-drug lane with a known viral-protease comparator that already appears as a positive-control context in dengue protease discovery work.",
        "must_not_do": "Do not treat boceprevir as a primary dengue lead just because it is an approved viral protease inhibitor in another disease area.",
        "source_anchor": "Boceprevir dengue protease discovery comparator paper",
        "source_url": "https://pubmed.ncbi.nlm.nih.gov/25487800/",
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


def build_payload(broad_screen_autofill: dict[str, Any] | None = None) -> dict[str, Any]:
    rows, bulk_override_applied = materialize_repurposing_rows(
        target_id="Dengue NS2B-NS3 protease",
        manual_rows=[dict(spec) for spec in ROW_SPECS],
        bulk_autofill_payload=broad_screen_autofill,
        target_brief_artifact=DEFAULT_TARGET_BRIEF_ARTIFACT,
        first_contact_packet_artifact=FIRST_CONTACT_PACKET_ARTIFACT,
        track_label=DEFAULT_TRACK_LABEL,
        default_outreach_track_id="IPK_dengue",
    )

    summary = {
        "status": "wetlab_dengue_ns2b_ns3_protease_repurposing_fill_map_ready",
        "target_count": 1,
        "row_count": len(rows),
        "bulk_override_applied": bulk_override_applied,
        "usage_enum": USAGE_ENUM,
        "next_required_step": "Render these approved-drug rows into the Dengue NS2B-NS3 protease suite, then keep the target blocked behind Cathepsin K until the serialized predecessor resolves.",
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Wet-Lab Dengue NS2B-NS3 Protease Repurposing Fill Map",
        "",
        f"- status: `{s['status']}`",
        f"- target_count: `{s['target_count']}`",
        f"- row_count: `{s['row_count']}`",
        f"- usage_enum: `{s['usage_enum']}`",
        "",
        "| slot_rank | compound_name | first_contact_use_mode | target_brief_artifact |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['slot_rank']}` | `{row['compound_name']}` | `{row['first_contact_use_mode']}` | `{row['target_brief_artifact']}` |"
        )
    lines.extend(["", "## Usage Notes", ""])
    for row in payload["rows"]:
        lines.extend(
            [
                f"- `{row['compound_name']}` -> `{row['first_contact_use_mode']}` via `{row['brief_slot_name']}`",
                f"  Rationale: {row['usage_rationale']}",
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
    parser = argparse.ArgumentParser(description="Build the Dengue NS2B-NS3 protease approved-drug repurposing fill map.")
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
