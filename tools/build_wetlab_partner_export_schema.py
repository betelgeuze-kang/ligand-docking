#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_JSON = "runs/wetlab_partner_export_schema_current.json"
DEFAULT_OUT_CSV = "runs/wetlab_partner_export_schema_current.csv"
DEFAULT_OUT_MD = "runs/wetlab_partner_export_schema_current.md"

ROWS = [
    {
        "partner_track_id": "DNDi_IPK",
        "partner_label": "DNDi / Institut Pasteur Korea",
        "lead_domain_families": "parasite_pde ; cysteine_protease ; parasite_oxidoreductase",
        "required_export_artifacts": "email_subject ; email_body ; proposal_summary ; neglected_target_brief ; selectivity_panel ; first_assay_packet",
        "email_angle": "low-friction neglected-disease micro-validation with day-one parasite-vs-host separation",
        "first_ask": "cheap enzyme assay plus counterscreen stack",
        "must_include": "why_now ; parasite-vs-host selectivity ; cheap assay logic ; follow-on neglected target",
        "must_not_do": "do not pitch as generic docking-only lead generation",
    },
    {
        "partner_track_id": "M4K_open_science",
        "partner_label": "M4K / rare-disease open-science kinase",
        "lead_domain_families": "kinase",
        "required_export_artifacts": "email_subject ; email_body ; proposal_summary ; kinase_target_brief ; mutant_or_wt_note ; kinase_selectivity_panel",
        "email_angle": "mutant-aware open-science kinase triage with fast biochemical or DSF entry",
        "first_ask": "mutant-vs-wt biochemical or DSF pass",
        "must_include": "mutant_or_context_frame ; kinase selectivity note ; low-friction first readout",
        "must_not_do": "do not oversell cell efficacy or BBB conclusions from the first packet",
    },
    {
        "partner_track_id": "SGC_dark_kinase",
        "partner_label": "SGC / dark kinase structural-biology labs",
        "lead_domain_families": "kinase",
        "required_export_artifacts": "email_subject ; email_body ; proposal_summary ; benchmark_target_brief ; PKIS_control_rows ; neighborhood_kinase_panel",
        "email_angle": "benchmark-first P-loop and conformational-state validation inside a published open set",
        "first_ask": "DSF or biochemical benchmark pass against PKIS plus 11-series frame",
        "must_include": "published benchmark controls ; open-probe frame ; P-loop rationale",
        "must_not_do": "do not frame the first packet as a generic dark-kinase fishing expedition",
    },
    {
        "partner_track_id": "oncology_condition_aware",
        "partner_label": "Condition-aware oncology labs",
        "lead_domain_families": "carbonic_anhydrase",
        "required_export_artifacts": "email_subject ; email_body ; proposal_summary ; condition_card ; CA_selectivity_panel ; acidic_vs_neutral_go_no_go",
        "email_angle": "tumor-like acidic-buffer validation with same-packet CA II and CA XII deselection",
        "first_ask": "acidic-buffer CA IX pass plus same-packet counterscreens",
        "must_include": "buffer recipe logic ; condition-aware reason ; CA II/CA XII panel",
        "must_not_do": "do not present generic carbonic-anhydrase binding as the core claim",
    },
    {
        "partner_track_id": "READDI_Korea",
        "partner_label": "READDI / Korea antiviral rail",
        "lead_domain_families": "cysteine_protease",
        "required_export_artifacts": "email_subject ; email_body ; proposal_summary ; antiviral_target_brief ; host_protease_panel ; procurement_sheet",
        "email_angle": "paired low-friction antiviral protease packet with host-liability cleanup built in",
        "first_ask": "fast fluorogenic protease assay plus host-liability counterscreen",
        "must_include": "paired target logic ; host counterscreen ; procurement-ready controls",
        "must_not_do": "do not send a crowded-field hit list without host-liability framing",
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
            "status": "wetlab_partner_export_schema_ready",
            "partner_track_count": len(ROWS),
            "next_required_step": "Render each target packet through the partner-specific export schema so the same core evidence is phrased differently for DNDi/IPK, M4K, SGC, oncology, and READDI.",
        },
        "rows": ROWS,
    }


def _write_markdown(path: Path, payload: dict) -> None:
    s = payload["summary"]
    lines = [
        "# Wet-Lab Partner Export Schema",
        "",
        f"- status: `{s['status']}`",
        f"- partner_track_count: `{s['partner_track_count']}`",
        "",
        "| partner_track_id | partner_label | lead_domain_families | first_ask | must_include |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['partner_track_id']}` | `{row['partner_label']}` | `{row['lead_domain_families']}` | {row['first_ask']} | {row['must_include']} |"
        )
    lines.extend(["", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the wet-lab partner-specific export schema.")
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
