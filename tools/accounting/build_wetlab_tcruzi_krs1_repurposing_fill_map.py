#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from tools.builder_table_utils import write_csv_rows
from tools.wetlab_target_render_utils import materialize_repurposing_rows, maybe_load_json

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/wetlab_tcruzi_krs1_repurposing_fill_map_current.json"
DEFAULT_OUT_CSV = "runs/wetlab_tcruzi_krs1_repurposing_fill_map_current.csv"
DEFAULT_OUT_MD = "runs/wetlab_tcruzi_krs1_repurposing_fill_map_current.md"
DEFAULT_BROAD_SCREEN_AUTOFILL_JSON = "runs/wetlab_broad_screen_repurposing_autofill_current.json"
DEFAULT_TARGET_BRIEF_ARTIFACT = "runs/tcruzi_krs1_render_suite_current.md"
FIRST_CONTACT_PACKET_ARTIFACT = "runs/tcruzi_krs1_launch_packet_current.md"
DEFAULT_TRACK_LABEL = "DNDi Chagas backup rail"

ROW_SPECS: list[dict[str, Any]] = [
    {
        "priority_rank": 11,
        "target_id": "T. cruzi KRS1",
        "outreach_track_id": "DNDi_Chagas_backup",
        "slot_rank": 1,
        "compound_name": "Benznidazole",
        "seed_status": "approved_chagas_benchmark",
        "brief_slot_name": "repurposing_1",
        "first_contact_use_mode": "benchmark_control",
        "vendor_check_required": False,
        "cost_check_required": False,
        "selectivity_note": "Use as the approved Chagas benchmark row, not as a direct KRS1 claim.",
        "usage_rationale": "Keeps the KRS1 packet grounded in the actual standard-of-care comparator used throughout Chagas development.",
        "must_not_do": "Do not present benznidazole as KRS1-directed chemistry.",
        "source_anchor": "Sci Transl Med TcKRS1 efficacy paper",
        "source_url": "https://pubmed.ncbi.nlm.nih.gov/40632837/",
    },
    {
        "priority_rank": 11,
        "target_id": "T. cruzi KRS1",
        "outreach_track_id": "DNDi_Chagas_backup",
        "slot_rank": 2,
        "compound_name": "Nifurtimox",
        "seed_status": "approved_chagas_comparator",
        "brief_slot_name": "repurposing_2",
        "first_contact_use_mode": "comparator_only",
        "vendor_check_required": False,
        "cost_check_required": False,
        "selectivity_note": "Comparator-only Chagas therapy anchor to keep whole-parasite context explicit while KRS1 remains biochemical-first.",
        "usage_rationale": "Rounds out the approved-drug lane with the second standard Chagas therapy while preserving target-specific caution.",
        "must_not_do": "Do not treat nifurtimox as evidence of KRS1 target engagement.",
        "source_anchor": "Current Chagas therapy comparator context",
        "source_url": "https://dndi.org/scientific-articles/2025/antitrypanosomal-quinazolines-targeting-lysyl-trna-synthetase-show-partial-efficacy-in-a-mouse-model-of-acute-chagas-disease/",
    },
    {
        "priority_rank": 11,
        "target_id": "T. cruzi KRS1",
        "outreach_track_id": "DNDi_Chagas_backup",
        "slot_rank": 3,
        "compound_name": "Posaconazole",
        "seed_status": "approved_antifungal_chagas_comparator",
        "brief_slot_name": "repurposing_3",
        "first_contact_use_mode": "comparator_only",
        "vendor_check_required": False,
        "cost_check_required": False,
        "selectivity_note": "Comparator-only non-KRS1 whole-parasite anchor to prevent overreading parasite-kill signal as KRS1 bias.",
        "usage_rationale": "Useful whole-parasite comparator because it adds a familiar approved molecule with Chagas development history without pretending to be KRS1-specific.",
        "must_not_do": "Do not present posaconazole as KRS1 chemistry.",
        "source_anchor": "Chagas non-KRS1 comparator context",
        "source_url": "https://dndi.org/scientific-articles/2025/antitrypanosomal-quinazolines-targeting-lysyl-trna-synthetase-show-partial-efficacy-in-a-mouse-model-of-acute-chagas-disease/",
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
        target_id="T. cruzi KRS1",
        manual_rows=[dict(spec) for spec in ROW_SPECS],
        bulk_autofill_payload=broad_screen_autofill,
        target_brief_artifact=DEFAULT_TARGET_BRIEF_ARTIFACT,
        first_contact_packet_artifact=FIRST_CONTACT_PACKET_ARTIFACT,
        track_label=DEFAULT_TRACK_LABEL,
        default_outreach_track_id="DNDi_Chagas_backup",
    )
    return {
        "summary": {
            "status": "wetlab_tcruzi_krs1_repurposing_fill_map_ready",
            "target_count": 1,
            "row_count": len(rows),
            "bulk_override_applied": bulk_override_applied,
            "usage_enum": USAGE_ENUM,
            "next_required_step": "Render these Chagas comparator rows into the KRS1 suite, then keep KRS1 serialized behind DprE1 until the predecessor resolves.",
        },
        "rows": rows,
    }


def _write_markdown(path: Path, payload: dict) -> None:
    s = payload["summary"]
    lines = [
        "# Wet-Lab T. cruzi KRS1 Repurposing Fill Map",
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
    parser = argparse.ArgumentParser(description="Build the T. cruzi KRS1 repurposing fill map.")
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
