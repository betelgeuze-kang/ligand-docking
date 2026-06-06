#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PORTFOLIO_JSON = "runs/wetlab_partner_target_portfolio_current.json"
DEFAULT_BLUEPRINT_JSON = "runs/wetlab_wave1_campaign_blueprint_current.json"
DEFAULT_COMPANION_JSON = "runs/wetlab_validation_companion_panels_current.json"
DEFAULT_OUTREACH_JSON = "runs/wetlab_partner_outreach_tracks_current.json"
DEFAULT_OUT_JSON = "runs/ca_ix_one_page_brief_current.json"
DEFAULT_OUT_CSV = "runs/ca_ix_one_page_brief_current.csv"
DEFAULT_OUT_MD = "runs/ca_ix_one_page_brief_current.md"

SOURCE_ARTIFACTS_MD = [
    "runs/wetlab_partner_target_portfolio_current.md",
    "runs/wetlab_wave1_campaign_blueprint_current.md",
    "runs/wetlab_validation_companion_panels_current.md",
    "runs/wetlab_partner_outreach_tracks_current.md",
]

PRIMARY_SOURCES = [
    {
        "source_anchor": "Alterio et al. 2009 CA IX structure with acetazolamide",
        "source_url": "https://pubmed.ncbi.nlm.nih.gov/19805286/",
        "why_used": "Supports classical sulfonamide benchmarking on CA IX and structural differences from CA II/CA XII-family comparators.",
    },
    {
        "source_anchor": "Mahon et al. 2016 CA IX low-pH catalysis",
        "source_url": "https://pubmed.ncbi.nlm.nih.gov/27439028/",
        "why_used": "Supports running the primary CA IX biochemical screen in an acidic arm because CA IX is adapted for low-pH catalysis.",
    },
    {
        "source_anchor": "Lee et al. 2018 CA IX pH-stat in vivo",
        "source_url": "https://pubmed.ncbi.nlm.nih.gov/30206370/",
        "why_used": "Supports tumor-like extracellular pH near 6.7 and justifies the acidic primary arm rather than a neutral-only assay.",
    },
    {
        "source_anchor": "Yudowski et al. 2018 MES vs HEPES acidic media",
        "source_url": "https://pubmed.ncbi.nlm.nih.gov/29631360/",
        "why_used": "Supports a practical MES-buffered acidic arm (pH 6.8/6.6/6.2) paired with a HEPES-buffered pH 7.4 contrast arm.",
    },
    {
        "source_anchor": "Whittington et al. 2001 CA XII extracellular tumor-associated structure",
        "source_url": "https://pubmed.ncbi.nlm.nih.gov/11493685/",
        "why_used": "Supports CA XII as a real tumor-associated extracellular validation companion, not just a bookkeeping anti-target.",
    },
    {
        "source_anchor": "Abdoli et al. 2018 heterocoumarins selective for CA IX/XII over CA II",
        "source_url": "https://pubmed.ncbi.nlm.nih.gov/30258546/",
        "why_used": "Supports a novelty lane that is not limited to generic sulfonamides and uses CA II separation explicitly.",
    },
    {
        "source_anchor": "Kamel et al. 2025 allosteric CA IX-selective resin acids",
        "source_url": "https://pubmed.ncbi.nlm.nih.gov/40860057/",
        "why_used": "Supports a novelty lane for non-competitive, CA IX-biased scaffolds and a first-packet story beyond classical zinc-binding chemistry.",
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



def _load_json(path_like: str) -> dict[str, Any]:
    with _resolve(path_like).open("r", encoding="utf-8") as fh:
        return json.load(fh)



def _rows_by_target(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("target_id", "")): dict(row)
        for row in payload.get("rows", []) or []
        if str(row.get("target_id", ""))
    }



def _rows_by_track(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("track_id", "")): dict(row)
        for row in payload.get("rows", []) or []
        if str(row.get("track_id", ""))
    }



def build_payload(
    portfolio: dict[str, Any],
    blueprint: dict[str, Any],
    companion: dict[str, Any],
    outreach: dict[str, Any],
) -> dict[str, Any]:
    portfolio_row = _rows_by_target(portfolio)["CA IX"]
    blueprint_row = _rows_by_target(blueprint)["CA IX"]
    companion_row = _rows_by_target(companion)["CA IX"]
    outreach_row = _rows_by_track(outreach)["oncology_condition_aware"]

    repurposing_slots = [
        {
            "slot_rank": 1,
            "slot_label": "repurposing_slot_1",
            "criteria": "Approved, low-cost, directly procurable carbonic-anhydrase-active scaffolds with real biochemical assay precedent, so the first wet-lab pass measures condition-aware ranking rather than procurement friction.",
            "rationale": "CA IX is already crystallized with acetazolamide, so classical CA-active scaffolds are the right low-friction benchmark lane before any new chemistry claims.",
            "source_anchor": "Alterio et al. 2009 CA IX structure with acetazolamide",
            "source_url": "https://pubmed.ncbi.nlm.nih.gov/19805286/",
        },
        {
            "slot_rank": 2,
            "slot_label": "repurposing_slot_2",
            "criteria": "Approved or clinically mature CA-active compounds whose tail groups, overall charge, or exposure profile create a plausible CA IX versus CA II/CA XII separation hypothesis in the same first packet.",
            "rationale": "The first repurposing lane is not generic potency hunting; it has to test whether condition-aware ranking can separate tumor-facing CA IX from the housekeeping and companion isoforms immediately.",
            "source_anchor": "Whittington et al. 2001 CA XII extracellular tumor-associated structure",
            "source_url": "https://pubmed.ncbi.nlm.nih.gov/11493685/",
        },
        {
            "slot_rank": 3,
            "slot_label": "repurposing_slot_3",
            "criteria": "Only compounds that keep interpretable signal in a MES-buffered acidic arm and remain assay-tractable enough to run matched CA IX, CA XII, and CA II counterscreens on day one.",
            "rationale": "The packet should reward compounds that survive the tumor-like buffer setup rather than compounds that only look good in a neutral default solvent assumption.",
            "source_anchor": "Yudowski et al. 2018 MES vs HEPES acidic media",
            "source_url": "https://pubmed.ncbi.nlm.nih.gov/29631360/",
        },
    ]

    novelty_slots = [
        {
            "slot_rank": 1,
            "slot_label": "novelty_slot_1",
            "criteria": "II-sparing tumor-CA chemotypes with literature precedent for CA IX/XII engagement outside the generic arylsulfonamide story, including coumarin-like or other non-classical extracellular binders.",
            "rationale": "This gives the novelty lane a credible route away from the standard 'just another sulfonamide' objection while preserving tumor-CA relevance.",
            "source_anchor": "Abdoli et al. 2018 heterocoumarins selective for CA IX/XII over CA II",
            "source_url": "https://pubmed.ncbi.nlm.nih.gov/30258546/",
        },
        {
            "slot_rank": 2,
            "slot_label": "novelty_slot_2",
            "criteria": "CA IX-biased scaffolds that exploit the isoform's extracellular structural features or adjacent hydrophobic cleft instead of relying only on generic zinc-binding pharmacophores.",
            "rationale": "CA IX structural work supports an isoform-specific geometry story, which is exactly the kind of mechanistic difference an oncology lab can find interesting.",
            "source_anchor": "Alterio et al. 2009 CA IX structure with acetazolamide",
            "source_url": "https://pubmed.ncbi.nlm.nih.gov/19805286/",
        },
        {
            "slot_rank": 3,
            "slot_label": "novelty_slot_3",
            "criteria": "Low-step, low-cost, allosteric or non-competitive CA IX candidates that preserve acidic-condition fit and can be explained as tumor-microenvironment ligands rather than broad CA poisons.",
            "rationale": "Recent primary literature already supports non-competitive CA IX-selective chemistry, so the novelty lane can legitimately include a non-classical route.",
            "source_anchor": "Kamel et al. 2025 allosteric CA IX-selective resin acids",
            "source_url": "https://pubmed.ncbi.nlm.nih.gov/40860057/",
        },
    ]

    selectivity_steps = [
        {
            "step_rank": 1,
            "step_label": "caix_primary_acidic_arm",
            "plan": "Run the primary biochemical screen on CA IX in a tumor-like acidic arm first, then treat all later selectivity calls as downstream of that arm rather than of a neutral default screen.",
            "source_anchor": "Lee et al. 2018 CA IX pH-stat in vivo",
            "source_url": "https://pubmed.ncbi.nlm.nih.gov/30206370/",
        },
        {
            "step_rank": 2,
            "step_label": "caxii_companion_counterscreen",
            "plan": "Run CA XII on the same compound set as a tumor-associated extracellular companion counterscreen, so compounds can be classified as CA IX-biased versus IX/XII-dual rather than being mislabeled as IX-selective by omission.",
            "source_anchor": "Whittington et al. 2001 CA XII extracellular tumor-associated structure",
            "source_url": "https://pubmed.ncbi.nlm.nih.gov/11493685/",
        },
        {
            "step_rank": 3,
            "step_label": "caii_housekeeping_deselection",
            "plan": "Run CA II as the housekeeping counterscreen in the first packet and reject compounds that collapse into generic carbonic-anhydrase behavior once CA II is measured.",
            "source_anchor": "Abdoli et al. 2018 heterocoumarins selective for CA IX/XII over CA II",
            "source_url": "https://pubmed.ncbi.nlm.nih.gov/30258546/",
        },
        {
            "step_rank": 4,
            "step_label": "classification_rule",
            "plan": "Advance only compounds that retain acidic-arm CA IX activity together with CA II separation; keep CA XII-dual compounds in a separate tumor-CA bucket and do not market them as CA IX-biased hits.",
            "source_anchor": "CA IX and CA XII are both tumor-associated extracellular carbonic anhydrases",
            "source_url": "https://pubmed.ncbi.nlm.nih.gov/11493685/ ; https://pubmed.ncbi.nlm.nih.gov/30258546/",
        },
    ]

    assay_steps = [
        {
            "step_rank": 1,
            "step_label": "acidic_primary",
            "assay": "Primary enzyme arm: recombinant or catalytic-domain CA IX CO2 hydration assay in MES-buffered acidic conditions centered on pH 6.6, aligned to tumor-like extracellular acidity rather than a neutral default.",
            "source_anchor": "Lee et al. 2018 CA IX pH-stat in vivo + Yudowski et al. 2018 MES acidic media",
            "source_url": "https://pubmed.ncbi.nlm.nih.gov/30206370/ ; https://pubmed.ncbi.nlm.nih.gov/29631360/",
        },
        {
            "step_rank": 2,
            "step_label": "neutral_contrast",
            "assay": "Neutral contrast arm: matched CA IX run in HEPES-buffered pH 7.4 so the packet can quantify acidic-condition advantage instead of reporting a single-context potency number.",
            "source_anchor": "Yudowski et al. 2018 HEPES pH 7.4 versus MES acidic arms",
            "source_url": "https://pubmed.ncbi.nlm.nih.gov/29631360/",
        },
        {
            "step_rank": 3,
            "step_label": "companion_and_housekeeping_counterscreens",
            "assay": "Immediate counterscreens: same compound set on CA XII and CA II, with CA XII used to identify tumor-CA dual activity and CA II used as the first housekeeping deselection gate.",
            "source_anchor": "Whittington et al. 2001 CA XII structure + Abdoli et al. 2018 IX/XII versus II selectivity",
            "source_url": "https://pubmed.ncbi.nlm.nih.gov/11493685/ ; https://pubmed.ncbi.nlm.nih.gov/30258546/",
        },
        {
            "step_rank": 4,
            "step_label": "optional_cell_follow_up",
            "assay": "Optional follow-up: hypoxia/acidosis cell-surface or extracellular-pH readout using CA IX-positive models, only after the biochemical packet shows acidic-arm CA IX signal plus counterscreen discipline.",
            "source_anchor": "Yudowski et al. 2018 SLC-0111 and acetazolamide in acidic media + Lee et al. 2018 in vivo acidic tumor pHe",
            "source_url": "https://pubmed.ncbi.nlm.nih.gov/29631360/ ; https://pubmed.ncbi.nlm.nih.gov/30206370/",
        },
    ]

    headline = (
        "Acidic-buffer CA IX screening with immediate CA II and CA XII deselection, "
        "so oncology labs test tumor-like conditions instead of generic pan-carbonic-anhydrase hits."
    )
    objection = (
        "Most CA IX hit lists collapse into generic carbonic anhydrase inhibition, so a new screen will not give an external lab a cleaner starting point."
    )
    objection_answer = (
        "This packet is not a neutral-pH generic CA screen: it runs CA IX in a MES-buffered pH 6.6 arm, "
        "pairs every hit with CA XII and physiological CA II counterscreens, and only advances compounds as CA IX-biased "
        "or explicitly IX/XII-dual tumor-CA agents."
    )

    structured = {
        "target_id": portfolio_row["target_id"],
        "partner_track": outreach_row["track_id"],
        "partner_track_label": outreach_row["track_label"],
        "partner_rail": portfolio_row["partner_rail"],
        "disease_area": portfolio_row["disease_area"],
        "validation_companion_target": "CA XII",
        "headline": headline,
        "main_external_lab_objection": objection,
        "objection_answer": objection_answer,
        "top_3_repurposing_slot_criteria": repurposing_slots,
        "top_3_novelty_slot_criteria": novelty_slots,
        "ca_ii_ca_xii_selectivity_counterscreen_plan": {
            "primary_panel": companion_row["primary_companion_panel"],
            "panel_rationale": companion_row["companion_why"],
            "plan_steps": selectivity_steps,
        },
        "first_assay_stack_under_acidic_tumor_like_buffer": {
            "blueprint_first_assay": blueprint_row["first_assay"],
            "buffer_primary_arm": "MES-buffered acidic arm centered on pH 6.6",
            "buffer_neutral_contrast_arm": "HEPES-buffered neutral contrast arm at pH 7.4",
            "first_go_no_go": blueprint_row["first_go_no_go"],
            "assay_steps": assay_steps,
        },
        "source_artifact_md_refs": SOURCE_ARTIFACTS_MD,
        "primary_sources": PRIMARY_SOURCES,
    }

    rows: list[dict[str, Any]] = []
    for slot in repurposing_slots:
        rows.append({
            "section": "repurposing_slot_criteria",
            "rank": slot["slot_rank"],
            "label": slot["slot_label"],
            "content": slot["criteria"],
            "source_anchor": slot["source_anchor"],
            "source_url": slot["source_url"],
        })
    for slot in novelty_slots:
        rows.append({
            "section": "novelty_slot_criteria",
            "rank": slot["slot_rank"],
            "label": slot["slot_label"],
            "content": slot["criteria"],
            "source_anchor": slot["source_anchor"],
            "source_url": slot["source_url"],
        })
    for step in selectivity_steps:
        rows.append({
            "section": "selectivity_counterscreen_plan",
            "rank": step["step_rank"],
            "label": step["step_label"],
            "content": step["plan"],
            "source_anchor": step["source_anchor"],
            "source_url": step["source_url"],
        })
    for step in assay_steps:
        rows.append({
            "section": "acidic_tumor_like_first_assay_stack",
            "rank": step["step_rank"],
            "label": step["step_label"],
            "content": step["assay"],
            "source_anchor": step["source_anchor"],
            "source_url": step["source_url"],
        })
    rows.extend([
        {
            "section": "one_page_brief_headline",
            "rank": 1,
            "label": "headline",
            "content": headline,
            "source_anchor": "portfolio+blueprint alignment",
            "source_url": "",
        },
        {
            "section": "main_external_lab_objection",
            "rank": 1,
            "label": "objection",
            "content": objection,
            "source_anchor": "external-lab risk framing",
            "source_url": "",
        },
        {
            "section": "main_external_lab_objection",
            "rank": 2,
            "label": "answer",
            "content": objection_answer,
            "source_anchor": "external-lab risk framing",
            "source_url": "",
        },
    ])

    summary = {
        "status": "ca_ix_one_page_brief_ready",
        "target_id": portfolio_row["target_id"],
        "partner_track": outreach_row["track_id"],
        "validation_companion_target": "CA XII",
        "source_artifact_count": len(SOURCE_ARTIFACTS_MD),
        "primary_source_count": len(PRIMARY_SOURCES),
        "row_count": len(rows),
        "next_required_step": "Fill actual compounds into the three repurposing and three novelty slots, then outbound the CA IX packet with the CA II/CA XII counterscreen plan intact.",
    }
    return {"summary": summary, "structured": structured, "rows": rows}



def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    p = payload["structured"]
    lines = [
        "# CA IX One-Page Brief",
        "",
        f"- status: `{s['status']}`",
        f"- target_id: `{s['target_id']}`",
        f"- partner_track: `{s['partner_track']}`",
        f"- validation_companion_target: `{s['validation_companion_target']}`",
        f"- source_artifact_count: `{s['source_artifact_count']}`",
        f"- primary_source_count: `{s['primary_source_count']}`",
        "",
        "## Source Artifacts",
        "",
    ]
    for ref in p["source_artifact_md_refs"]:
        lines.append(f"- `{ref}`")
    lines.extend([
        "",
        "## One-Page Brief Headline",
        "",
        f"- {p['headline']}",
        "",
        "## Top-3 Repurposing Slot Criteria",
        "",
        "| slot_rank | criteria | rationale | source_anchor |",
        "| --- | --- | --- | --- |",
    ])
    for row in p["top_3_repurposing_slot_criteria"]:
        lines.append(
            f"| `{row['slot_rank']}` | {row['criteria']} | {row['rationale']} | [{row['source_anchor']}]({row['source_url']}) |"
        )
    lines.extend([
        "",
        "## Top-3 Novelty Slot Criteria",
        "",
        "| slot_rank | criteria | rationale | source_anchor |",
        "| --- | --- | --- | --- |",
    ])
    for row in p["top_3_novelty_slot_criteria"]:
        lines.append(
            f"| `{row['slot_rank']}` | {row['criteria']} | {row['rationale']} | [{row['source_anchor']}]({row['source_url']}) |"
        )
    lines.extend([
        "",
        "## CA II / CA XII Selectivity and Counterscreen Plan",
        "",
        f"- primary_panel: {p['ca_ii_ca_xii_selectivity_counterscreen_plan']['primary_panel']}",
        f"- panel_rationale: {p['ca_ii_ca_xii_selectivity_counterscreen_plan']['panel_rationale']}",
        "",
        "| step_rank | plan_step | source_anchor |",
        "| --- | --- | --- |",
    ])
    for row in p["ca_ii_ca_xii_selectivity_counterscreen_plan"]["plan_steps"]:
        lines.append(
            f"| `{row['step_rank']}` | {row['plan']} | [{row['source_anchor']}]({row['source_url']}) |"
        )
    assay = p["first_assay_stack_under_acidic_tumor_like_buffer"]
    lines.extend([
        "",
        "## First Assay Stack Under Acidic Tumor-Like Buffer",
        "",
        f"- blueprint_first_assay: {assay['blueprint_first_assay']}",
        f"- buffer_primary_arm: {assay['buffer_primary_arm']}",
        f"- buffer_neutral_contrast_arm: {assay['buffer_neutral_contrast_arm']}",
        f"- first_go_no_go: {assay['first_go_no_go']}",
        "",
        "| step_rank | assay_step | source_anchor |",
        "| --- | --- | --- |",
    ])
    for row in assay["assay_steps"]:
        lines.append(
            f"| `{row['step_rank']}` | {row['assay']} | [{row['source_anchor']}]({row['source_url']}) |"
        )
    lines.extend([
        "",
        "## Main External-Lab Objection and Answer",
        "",
        f"- objection: {p['main_external_lab_objection']}",
        f"- answer: {p['objection_answer']}",
        "",
        "## Primary Sources",
        "",
    ])
    for src in p["primary_sources"]:
        lines.append(f"- [{src['source_anchor']}]({src['source_url']}): {src['why_used']}")
    lines.extend([
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")



def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the CA IX condition-aware one-page brief packet.")
    parser.add_argument("--portfolio-json", default=DEFAULT_PORTFOLIO_JSON)
    parser.add_argument("--blueprint-json", default=DEFAULT_BLUEPRINT_JSON)
    parser.add_argument("--companion-json", default=DEFAULT_COMPANION_JSON)
    parser.add_argument("--outreach-json", default=DEFAULT_OUTREACH_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()



def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.portfolio_json),
        _load_json(args.blueprint_json),
        _load_json(args.companion_json),
        _load_json(args.outreach_json),
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
