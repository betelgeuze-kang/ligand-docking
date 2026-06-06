#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/wetlab_domain_generation_schema_current.json"
DEFAULT_OUT_CSV = "runs/wetlab_domain_generation_schema_current.csv"
DEFAULT_OUT_MD = "runs/wetlab_domain_generation_schema_current.md"

ROWS = [
    {
        "domain_family": "parasite_pde",
        "lead_targets": "T. cruzi PDE",
        "core_artifacts": "target_brief ; repurposing_fill_map ; novelty_fill_map",
        "target_overlay_artifacts": "condition_card ; human_pde_selectivity_panel ; assay_packet ; go_no_go_card",
        "condition_overlay_fields": "buffer_pH ; ionic_strength_mM ; temperature_C ; parasite_enzyme_buffer_id",
        "selectivity_overlay_fields": "human_pde_family_panel ; assay_interference_note ; solubility_note",
        "default_first_assay_packet": "recombinant parasite PDE inhibition plus human PDE mini-panel",
        "default_partner_tracks": "DNDi_IPK",
        "render_policy": "cheap_enzyme_selectivity_first",
    },
    {
        "domain_family": "cysteine_protease",
        "lead_targets": "Cruzain ; SARS-CoV-2 PLpro ; SARS-CoV-2 Mpro",
        "core_artifacts": "target_brief ; repurposing_fill_map ; novelty_fill_map",
        "target_overlay_artifacts": "condition_card ; host_protease_panel ; assay_packet ; go_no_go_card",
        "condition_overlay_fields": "buffer_pH ; reductant_state ; detergent_context ; temperature_C",
        "selectivity_overlay_fields": "host_cysteine_protease_panel ; thiol_reactivity_note ; shallow_pocket_note",
        "default_first_assay_packet": "fluorogenic protease assay plus host-reactivity counterscreen",
        "default_partner_tracks": "DNDi_IPK ; READDI_Korea",
        "render_policy": "artifact_rejection_first",
    },
    {
        "domain_family": "kinase",
        "lead_targets": "ALK2 ; STK17B (DRAK2)",
        "core_artifacts": "target_brief ; repurposing_fill_map ; novelty_fill_map",
        "target_overlay_artifacts": "condition_card ; kinase_selectivity_panel ; assay_packet ; go_no_go_card",
        "condition_overlay_fields": "ATP_Mg_state ; temperature_C ; phospho_context ; mutant_or_wt_context",
        "selectivity_overlay_fields": "kinome_minipanel ; mutant_vs_wt_note ; BBB_or_cell_context_note",
        "default_first_assay_packet": "biochemical or DSF kinase assay plus neighborhood kinase panel",
        "default_partner_tracks": "M4K_open_science ; SGC_dark_kinase",
        "render_policy": "state_sensitive_kinase_benchmark_first",
    },
    {
        "domain_family": "carbonic_anhydrase",
        "lead_targets": "CA IX ; CA XII",
        "core_artifacts": "target_brief ; repurposing_fill_map ; novelty_fill_map",
        "target_overlay_artifacts": "condition_card ; CA_selectivity_panel ; assay_packet ; go_no_go_card",
        "condition_overlay_fields": "buffer_pH ; bicarbonate_context ; ionic_strength_mM ; temperature_C",
        "selectivity_overlay_fields": "CA_II_panel ; CA_XII_panel ; neutral_vs_acidic_delta_note",
        "default_first_assay_packet": "acidic-buffer CA IX assay plus CA II and CA XII counterscreen",
        "default_partner_tracks": "oncology_condition_aware",
        "render_policy": "condition_aware_selectivity_first",
    },
    {
        "domain_family": "parasite_oxidoreductase",
        "lead_targets": "Leishmania braziliensis DHODH",
        "core_artifacts": "target_brief ; repurposing_fill_map ; novelty_fill_map",
        "target_overlay_artifacts": "condition_card ; host_dhodh_selectivity_panel ; assay_packet ; go_no_go_card",
        "condition_overlay_fields": "redox_state ; cofactor_state ; temperature_C ; ionic_strength_mM",
        "selectivity_overlay_fields": "host_dhodh_panel ; fluorescence_interference_note ; redox_artifact_note",
        "default_first_assay_packet": "parasite DHODH enzyme assay plus host DHODH counterscreen",
        "default_partner_tracks": "DNDi_IPK",
        "render_policy": "host_enzyme_separation_first",
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
            "status": "wetlab_domain_generation_schema_ready",
            "domain_family_count": len(ROWS),
            "renderer_layer_count": 3,
            "core_layer_name": "domain_core",
            "target_layer_name": "target_overlay",
            "partner_layer_name": "partner_export",
            "next_required_step": "Use this schema to keep shared core generation stable while target overlays and partner exports diverge by domain family.",
        },
        "rows": ROWS,
    }


def _write_markdown(path: Path, payload: dict) -> None:
    s = payload["summary"]
    lines = [
        "# Wet-Lab Domain Generation Schema",
        "",
        f"- status: `{s['status']}`",
        f"- domain_family_count: `{s['domain_family_count']}`",
        f"- renderer_layer_count: `{s['renderer_layer_count']}`",
        f"- core_layer_name: `{s['core_layer_name']}`",
        f"- target_layer_name: `{s['target_layer_name']}`",
        f"- partner_layer_name: `{s['partner_layer_name']}`",
        "",
        "| domain_family | lead_targets | core_artifacts | target_overlay_artifacts | default_partner_tracks | render_policy |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['domain_family']}` | `{row['lead_targets']}` | `{row['core_artifacts']}` | `{row['target_overlay_artifacts']}` | `{row['default_partner_tracks']}` | `{row['render_policy']}` |"
        )
    lines.extend(["", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the wet-lab domain-family generation schema.")
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
