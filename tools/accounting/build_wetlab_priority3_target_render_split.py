#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_JSON = "runs/wetlab_priority3_target_render_split_current.json"
DEFAULT_OUT_CSV = "runs/wetlab_priority3_target_render_split_current.csv"
DEFAULT_OUT_MD = "runs/wetlab_priority3_target_render_split_current.md"

ROWS = [
    {
        "priority_rank": 1,
        "target_id": "T. cruzi PDE",
        "domain_family": "parasite_pde",
        "partner_track_id": "DNDi_IPK",
        "current_core_artifact": "runs/wetlab_target_brief_tcruzi_pde_current.md",
        "planned_condition_card_artifact": "runs/tcruzi_pde_condition_card_current.md",
        "planned_selectivity_panel_artifact": "runs/tcruzi_pde_human_pde_selectivity_panel_current.md",
        "planned_assay_packet_artifact": "runs/tcruzi_pde_assay_packet_current.md",
        "planned_go_no_go_artifact": "runs/tcruzi_pde_go_no_go_card_current.md",
        "planned_partner_export_artifact": "runs/tcruzi_pde_dndi_ipk_export_current.md",
        "existing_compound_fill_artifacts": "runs/wetlab_priority3_repurposing_fill_map_current.md ; runs/wetlab_priority3_novelty_fill_map_current.md",
        "render_sequence": "core_brief -> condition_card -> selectivity_panel -> assay_packet -> go_no_go_card -> partner_export",
    },
    {
        "priority_rank": 2,
        "target_id": "CA IX",
        "domain_family": "carbonic_anhydrase",
        "partner_track_id": "oncology_condition_aware",
        "current_core_artifact": "runs/wetlab_target_brief_caix_current.md",
        "planned_condition_card_artifact": "runs/caix_condition_card_current.md",
        "planned_selectivity_panel_artifact": "runs/caix_ca2_ca12_selectivity_panel_current.md",
        "planned_assay_packet_artifact": "runs/caix_acidic_buffer_assay_packet_current.md",
        "planned_go_no_go_artifact": "runs/caix_condition_aware_go_no_go_card_current.md",
        "planned_partner_export_artifact": "runs/caix_oncology_export_current.md",
        "existing_compound_fill_artifacts": "runs/wetlab_priority3_repurposing_fill_map_current.md ; runs/wetlab_priority3_novelty_fill_map_current.md ; runs/ca_ix_one_page_brief_current.md",
        "render_sequence": "core_brief -> condition_card -> CA_selectivity_panel -> assay_packet -> go_no_go_card -> partner_export",
    },
    {
        "priority_rank": 3,
        "target_id": "SARS-CoV-2 Mpro",
        "domain_family": "cysteine_protease",
        "partner_track_id": "READDI_Korea",
        "current_core_artifact": "runs/wetlab_target_brief_sarscov2_mpro_current.md",
        "planned_condition_card_artifact": "runs/sarscov2_mpro_condition_card_current.md",
        "planned_selectivity_panel_artifact": "runs/sarscov2_mpro_host_protease_panel_current.md",
        "planned_assay_packet_artifact": "runs/sarscov2_mpro_assay_packet_current.md",
        "planned_go_no_go_artifact": "runs/sarscov2_mpro_go_no_go_card_current.md",
        "planned_partner_export_artifact": "runs/sarscov2_mpro_readdi_export_current.md",
        "existing_compound_fill_artifacts": "runs/wetlab_priority3_repurposing_fill_map_current.md ; runs/wetlab_priority3_novelty_fill_map_current.md ; runs/wetlab_mpro_vendor_cost_check_current.md",
        "render_sequence": "core_brief -> condition_card -> host_protease_panel -> assay_packet -> go_no_go_card -> partner_export",
    },
]


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def build_payload() -> dict:
    return {
        "summary": {
            "status": "wetlab_priority3_target_render_split_ready",
            "target_count": len(ROWS),
            "domain_generation_schema_artifact": "runs/wetlab_domain_generation_schema_current.md",
            "partner_export_schema_artifact": "runs/wetlab_partner_export_schema_current.md",
            "next_required_step": "Build target-specific condition cards, selectivity panels, assay packets, and partner exports for Mpro, CA IX, and T. cruzi PDE in that order or in parallel prep while execution stays serialized.",
        },
        "rows": ROWS,
    }


def _write_markdown(path: Path, payload: dict) -> None:
    s = payload["summary"]
    lines = [
        "# Wet-Lab Priority 3 Target Render Split",
        "",
        f"- status: `{s['status']}`",
        f"- target_count: `{s['target_count']}`",
        f"- domain_generation_schema_artifact: `{s['domain_generation_schema_artifact']}`",
        f"- partner_export_schema_artifact: `{s['partner_export_schema_artifact']}`",
        "",
        "| priority_rank | target_id | domain_family | partner_track_id | current_core_artifact | planned_partner_export_artifact |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['priority_rank']}` | `{row['target_id']}` | `{row['domain_family']}` | `{row['partner_track_id']}` | `{row['current_core_artifact']}` | `{row['planned_partner_export_artifact']}` |"
        )
    lines.extend(["", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the target-specific render split for the priority three wet-lab targets.")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload()
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv_rows(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
