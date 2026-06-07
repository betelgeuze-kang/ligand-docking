#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/wetlab_partner_target_portfolio_current.json"
DEFAULT_OUT_CSV = "runs/wetlab_partner_target_portfolio_current.csv"
DEFAULT_OUT_MD = "runs/wetlab_partner_target_portfolio_current.md"

TARGET_ROWS: list[dict[str, Any]] = [
    {
        "target_id": "T. cruzi PDE",
        "group_label": "A",
        "domain_family": "parasite_enzyme",
        "disease_area": "Chagas disease",
        "wave": "Wave 1",
        "partner_rail": "DNDi/IPK neglected-disease rail",
        "rail_confidence": "direct_official",
        "assay_friction_score": 5,
        "partner_fit_score": 5,
        "repurposing_fit_score": 3,
        "primary_strength": "Official DNDi PDE lead-identification rail plus cheap enzyme validation and strong human/parasite selectivity story.",
        "main_risk": "Repurposing lane must clear human PDE anti-target risk early.",
        "source_anchor": "DNDi Chagas PDE project",
        "source_url": "https://dndi.org/news/2026/dndi-welcomes-ghit-support-lead-identification-novel-chemical-series-eisai-led-chagas-project/",
    },
    {
        "target_id": "Cruzain",
        "group_label": "A",
        "domain_family": "parasite_protease",
        "disease_area": "Chagas disease",
        "wave": "Wave 1",
        "partner_rail": "DNDi/IPK neglected-disease rail",
        "rail_confidence": "adjacent_official",
        "assay_friction_score": 5,
        "partner_fit_score": 5,
        "repurposing_fit_score": 2,
        "primary_strength": "Very cheap protease assays and a strong dynamic/desolvation narrative for reducing false positives.",
        "main_risk": "Need careful cysteine-reactivity and selectivity triage to avoid noisy false positives.",
        "source_anchor": "IPK DNDi Chagas screening lane",
        "source_url": "https://www.ip-korea.org/impact/service.php",
    },
    {
        "target_id": "DprE1",
        "group_label": "A",
        "domain_family": "bacterial_enzyme",
        "disease_area": "Tuberculosis",
        "wave": "Wave 2",
        "partner_rail": "TB Alliance / academic TB rail",
        "rail_confidence": "direct_official",
        "assay_friction_score": 3,
        "partner_fit_score": 4,
        "repurposing_fit_score": 2,
        "primary_strength": "Official TB Alliance interest and strong novelty value for OOD scaffold discovery.",
        "main_risk": "Chemistry and whole-cell follow-up are heavier than the cheapest enzyme/protease rails.",
        "source_anchor": "TB Alliance DprE1 inhibitor portfolio context",
        "source_url": "https://www.tballiance.org/wp-content/uploads/assets-from-drupal/AboutTBAlliance_September2023.pdf",
    },
    {
        "target_id": "ALK2",
        "group_label": "B",
        "domain_family": "kinase",
        "disease_area": "DIPG / pediatric brain cancer",
        "wave": "Wave 1",
        "partner_rail": "M4K / open-science kinase rail",
        "rail_confidence": "direct_official",
        "assay_friction_score": 4,
        "partner_fit_score": 5,
        "repurposing_fit_score": 3,
        "primary_strength": "Direct open-science rare-disease rail with public ALK2 focus and strong paper/collaboration incentive.",
        "main_risk": "Repurposing lane must respect BBB and mutant/wild-type selectivity constraints.",
        "source_anchor": "M4K ALK2 DIPG program",
        "source_url": "https://m4kpharma.com/",
    },
    {
        "target_id": "LRRK2",
        "group_label": "B",
        "domain_family": "kinase",
        "disease_area": "Parkinson's disease",
        "wave": "Wave 2",
        "partner_rail": "MJFF translational Parkinson's rail",
        "rail_confidence": "direct_official",
        "assay_friction_score": 2,
        "partner_fit_score": 4,
        "repurposing_fit_score": 2,
        "primary_strength": "Major translational disease interest and real target-validation community support.",
        "main_risk": "Large flexible kinase with higher assay and biology friction than the first-wave kinase targets.",
        "source_anchor": "MJFF LRRK2 targets-to-therapies context",
        "source_url": "https://www.michaeljfox.org/targets-therapies-initiative",
    },
    {
        "target_id": "STK17B (DRAK2)",
        "group_label": "B",
        "domain_family": "dark_kinase",
        "disease_area": "Autoimmune disease / glioblastoma",
        "wave": "Wave 1",
        "partner_rail": "SGC-UNC / dark kinase open-probe rail",
        "rail_confidence": "direct_official",
        "assay_friction_score": 4,
        "partner_fit_score": 5,
        "repurposing_fit_score": 2,
        "primary_strength": "Open probe ecosystem and strong structural-biology appeal for dynamic P-loop stories.",
        "main_risk": "Repurposing lane is weaker than the open-probe / fresh-chemotype lane.",
        "source_anchor": "SGC-UNC STK17B probe page",
        "source_url": "https://www.sgc-unc.org/main-st",
    },
    {
        "target_id": "CA IX",
        "group_label": "C",
        "domain_family": "condition_aware_enzyme",
        "disease_area": "Hypoxic solid tumors",
        "wave": "Wave 1",
        "partner_rail": "oncology condition-aware rail",
        "rail_confidence": "adjacent_literature",
        "assay_friction_score": 4,
        "partner_fit_score": 4,
        "repurposing_fit_score": 5,
        "primary_strength": "Best showcase target for pH-conditioned scoring and cheap approved-carbonic-anhydrase inhibitor triage.",
        "main_risk": "Must prove CA IX selectivity over CA II / CA XII to stay convincing.",
        "source_anchor": "CA IX/XII tumor pH review",
        "source_url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC5876008/",
    },
    {
        "target_id": "Cathepsin K",
        "group_label": "C",
        "domain_family": "acidic_protease",
        "disease_area": "Bone disease / bone metastasis",
        "wave": "Wave 2",
        "partner_rail": "acidic protease condition-aware rail",
        "rail_confidence": "adjacent_literature",
        "assay_friction_score": 4,
        "partner_fit_score": 3,
        "repurposing_fit_score": 2,
        "primary_strength": "Good acidic-pH mechanistic demo with tractable protease biochemistry.",
        "main_risk": "External partner pull is weaker than CA IX and prior target history is more mixed.",
        "source_anchor": "Cathepsin K acidic condition activity literature",
        "source_url": "https://pubmed.ncbi.nlm.nih.gov/24958728/",
    },
    {
        "target_id": "SARS-CoV-2 PLpro",
        "group_label": "D",
        "domain_family": "viral_protease",
        "disease_area": "Pan-coronavirus / pandemic preparedness",
        "wave": "Wave 1",
        "partner_rail": "READDI / Korea antiviral rail",
        "rail_confidence": "adjacent_official",
        "assay_friction_score": 4,
        "partner_fit_score": 5,
        "repurposing_fit_score": 3,
        "primary_strength": "READDI/Korea antiviral partnership context plus cheap protease-first validation path.",
        "main_risk": "Need host DUB-like anti-target sanity checks and shallow-pocket robustness.",
        "source_anchor": "READDI Korea collaboration context",
        "source_url": "https://readdi.org/stories/readdi-to-partner-with-south-koreas-national-institute-of-infectious-diseases-nih-kdca/",
    },
    {
        "target_id": "Dengue NS2B-NS3 protease",
        "group_label": "D",
        "domain_family": "viral_protease",
        "disease_area": "Dengue / Zika",
        "wave": "Wave 2",
        "partner_rail": "IPK / dengue antiviral rail",
        "rail_confidence": "adjacent_official",
        "assay_friction_score": 3,
        "partner_fit_score": 4,
        "repurposing_fit_score": 2,
        "primary_strength": "Strong fit for shallow wet pocket and SASA-driven discrimination; partner context exists in anti-dengue screening lanes.",
        "main_risk": "Flat water-exposed pocket lowers first-pass hit probability versus PLpro/Mpro.",
        "source_anchor": "IPK anti-dengue screening service context",
        "source_url": "https://www.ip-korea.org/impact/service.php",
    },
    {
        "target_id": "SARS-CoV-2 Mpro",
        "group_label": "Added",
        "domain_family": "viral_protease",
        "disease_area": "Pan-coronavirus / pandemic preparedness",
        "wave": "Wave 1",
        "partner_rail": "COVID Moonshot / READDI adjacent rail",
        "rail_confidence": "direct_open_science",
        "assay_friction_score": 5,
        "partner_fit_score": 4,
        "repurposing_fit_score": 4,
        "primary_strength": "Probably the cheapest high-signal viral protease validation rail with deep open-science precedent.",
        "main_risk": "Crowded field, so the story needs to emphasize dynamics/selectivity rather than generic hit finding.",
        "source_anchor": "COVID Moonshot",
        "source_url": "https://postera.ai/moonshot/",
    },
    {
        "target_id": "Leishmania braziliensis DHODH",
        "group_label": "Added",
        "domain_family": "parasite_enzyme",
        "disease_area": "Leishmaniasis",
        "wave": "Wave 1",
        "partner_rail": "DNDi leishmaniasis rail",
        "rail_confidence": "direct_official",
        "assay_friction_score": 4,
        "partner_fit_score": 4,
        "repurposing_fit_score": 2,
        "primary_strength": "DNDi-validated neglected-disease enzyme target with relatively clean recombinant assay path.",
        "main_risk": "Repurposing lane is thinner; likely stronger as a novel chemistry or covalent-enzyme story.",
        "source_anchor": "DNDi LbDHODH target validation article",
        "source_url": "https://dndi.org/scientific-articles/2025/barbituric-acid-derivatives-as-covalent-inhibitors-of-leishmania-braziliensis-dihydroorotate-dehydrogenase/",
    },
    {
        "target_id": "T. cruzi KRS1",
        "group_label": "Added",
        "domain_family": "parasite_enzyme",
        "disease_area": "Chagas disease",
        "wave": "Wave 2",
        "partner_rail": "DNDi Chagas backup rail",
        "rail_confidence": "direct_official",
        "assay_friction_score": 3,
        "partner_fit_score": 4,
        "repurposing_fit_score": 2,
        "primary_strength": "Officially validated druggable Chagas target that broadens the disease rail beyond PDE and Cruzain.",
        "main_risk": "Wet-lab path is less commodity-grade than PDE/protease assays, so it is better as second-wave neglected backup.",
        "source_anchor": "DNDi T. cruzi KRS1 article",
        "source_url": "https://dndi.org/scientific-articles/2025/antitrypanosomal-quinazolines-targeting-lysyl-trna-synthetase-show-partial-efficacy-in-a-mouse-model-of-acute-chagas-disease/",
    },
    {
        "target_id": "CA XII",
        "group_label": "Added",
        "domain_family": "condition_aware_companion",
        "disease_area": "Hypoxic solid tumors",
        "wave": "Validation Companion",
        "partner_rail": "CA IX selectivity / validation companion",
        "rail_confidence": "companion_literature",
        "assay_friction_score": 4,
        "partner_fit_score": 4,
        "repurposing_fit_score": 5,
        "primary_strength": "Best companion screen for proving CA IX selectivity under pH-conditioned oncology stories.",
        "main_risk": "Useful mainly as a selectivity and validation panel, not as the lead outbound campaign by itself.",
        "source_anchor": "CA IX/XII tumor pH review",
        "source_url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC5876008/",
    },
]


for row in TARGET_ROWS:
    row["total_priority_score"] = int(row["assay_friction_score"]) + int(row["partner_fit_score"]) + int(row["repurposing_fit_score"])


WAVE_ORDER = {"Wave 1": 0, "Wave 2": 1, "Validation Companion": 2}


def build_payload() -> dict[str, Any]:
    rows = sorted(
        TARGET_ROWS,
        key=lambda row: (WAVE_ORDER.get(str(row["wave"]), 99), -int(row["total_priority_score"]), str(row["target_id"])),
    )
    summary = {
        "status": "wetlab_partner_target_portfolio_ready",
        "total_target_count": len(rows),
        "wave1_count": sum(1 for row in rows if row["wave"] == "Wave 1"),
        "wave2_count": sum(1 for row in rows if row["wave"] == "Wave 2"),
        "validation_companion_count": sum(1 for row in rows if row["wave"] == "Validation Companion"),
        "scoring_scale": "1_to_5_higher_is_better",
        "assay_friction_definition": "5 means very low-friction wet-lab entry with standard biochemical or DSF-style validation; 1 means high operational friction.",
        "partner_fit_definition": "5 means direct official or strong open-science rail with clear collaborator pull; 1 means weak external pull.",
        "repurposing_fit_definition": "5 means cheap approved or commoditized compounds plausibly support a fast repurposing-first lane; 1 means repurposing is weak.",
        "wave1_priority_targets": ", ".join(row["target_id"] for row in rows if row["wave"] == "Wave 1"),
        "next_required_step": "Use Wave 1 for immediate outbound wet-lab packaging, keep Wave 2 behind first external traction, and always include CA XII as the CA IX selectivity companion screen rather than as a standalone first campaign.",
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    rows = payload["rows"]
    lines = [
        "# Wet-Lab Partner Target Portfolio",
        "",
        f"- status: `{s['status']}`",
        f"- total_target_count: `{s['total_target_count']}`",
        f"- wave1_count: `{s['wave1_count']}`",
        f"- wave2_count: `{s['wave2_count']}`",
        f"- validation_companion_count: `{s['validation_companion_count']}`",
        f"- scoring_scale: `{s['scoring_scale']}`",
        "",
        "## Scoring Rubric",
        "",
        f"- assay_friction_score: {s['assay_friction_definition']}",
        f"- partner_fit_score: {s['partner_fit_definition']}",
        f"- repurposing_fit_score: {s['repurposing_fit_definition']}",
        "",
    ]
    for wave in ["Wave 1", "Wave 2", "Validation Companion"]:
        wave_rows = [row for row in rows if row["wave"] == wave]
        lines.extend([
            f"## {wave}",
            "",
            "| target_id | domain_family | disease_area | partner_rail | rail_confidence | assay_friction | partner_fit | repurposing_fit | total |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ])
        for row in wave_rows:
            lines.append(
                f"| `{row['target_id']}` | `{row['domain_family']}` | `{row['disease_area']}` | `{row['partner_rail']}` | `{row['rail_confidence']}` | `{row['assay_friction_score']}` | `{row['partner_fit_score']}` | `{row['repurposing_fit_score']}` | `{row['total_priority_score']}` |"
            )
        lines.extend(["", f"### {wave} Notes", ""])
        for row in wave_rows:
            lines.extend([
                f"- `{row['target_id']}`: {row['primary_strength']}",
                f"  Risk: {row['main_risk']}",
                f"  Source: [{row['source_anchor']}]({row['source_url']})",
            ])
        lines.append("")
    lines.extend(["## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the wet-lab partner target portfolio wave table and scoring grid.")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists() or not str(path_like).startswith("runs/"):
        return cwd_path
    return (ROOT / path).resolve()


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
