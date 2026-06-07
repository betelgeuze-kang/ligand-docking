#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/wetlab_priority3_repurposing_seed_pool_current.json"
DEFAULT_OUT_CSV = "runs/wetlab_priority3_repurposing_seed_pool_current.csv"
DEFAULT_OUT_MD = "runs/wetlab_priority3_repurposing_seed_pool_current.md"

ROWS: list[dict[str, Any]] = [
    {
        "priority_rank": 1,
        "target_id": "T. cruzi PDE",
        "slot_rank": 1,
        "compound_name": "Dipyridamole",
        "compound_role": "disease-facing repurposing seed",
        "seed_status": "literature_backed_seed_not_final_shortlist",
        "why_selected": "Cheap, widely known human-use vasodilator/antiplatelet with reported trypanocidal plus nifurtimox-potentiating activity in acute Chagas myocarditis, making it a pragmatic first neglected-disease wet-lab entry compound.",
        "key_caution": "Useful for the disease rail, but not clean evidence of parasite-PDE selectivity; keep it as a repurposing seed and mechanistic stress-test rather than as proof of parasite-specific PDE engagement.",
        "source_anchor": "TcrPDEC validation + dipyridamole acute Chagas myocarditis",
        "source_url": "https://pubmed.ncbi.nlm.nih.gov/20625148/ ; https://pubmed.ncbi.nlm.nih.gov/28902285/",
    },
    {
        "priority_rank": 1,
        "target_id": "T. cruzi PDE",
        "slot_rank": 2,
        "compound_name": "Sildenafil",
        "compound_role": "human-PDE selectivity stress comparator",
        "seed_status": "approved_class_comparator_not_claimed_parasite_hit",
        "why_selected": "Well-known oral PDE5 inhibitor with low conceptual and procurement friction; useful as a deliberate comparator for whether the outbound packet can separate human-PDE pharmacology from parasite-biased signal.",
        "key_caution": "Do not market as a parasite hit. It belongs in the packet to stress-test human-PDE deselection and to anchor the selectivity story.",
        "source_anchor": "TcrPDEC validation + PDE5 inhibitor clinical class review",
        "source_url": "https://pubmed.ncbi.nlm.nih.gov/20625148/ ; https://pubmed.ncbi.nlm.nih.gov/31643519/",
    },
    {
        "priority_rank": 1,
        "target_id": "T. cruzi PDE",
        "slot_rank": 3,
        "compound_name": "Tadalafil",
        "compound_role": "second human-PDE selectivity stress comparator",
        "seed_status": "approved_class_comparator_not_claimed_parasite_hit",
        "why_selected": "A second clinically used PDE5 inhibitor with different exposure and physicochemical behavior than sildenafil, which helps test whether the packet can reject human-PDE-like behavior consistently instead of overfitting to one comparator.",
        "key_caution": "Use as a differentiated human-PDE comparator, not as parasite-target evidence.",
        "source_anchor": "TcrPDEC validation + PDE5 inhibitor clinical class review",
        "source_url": "https://pubmed.ncbi.nlm.nih.gov/20625148/ ; https://pubmed.ncbi.nlm.nih.gov/31643519/",
    },
    {
        "priority_rank": 2,
        "target_id": "CA IX",
        "slot_rank": 1,
        "compound_name": "Acetazolamide",
        "compound_role": "classical CA benchmark repurposing control",
        "seed_status": "clinical_benchmark_seed_not_selective_claim",
        "why_selected": "Direct structural CA IX benchmark and the cleanest low-friction positive control for the acidic-arm packet; if this does not behave as expected, the assay setup is suspect before the ranking model is.",
        "key_caution": "Treat as a benchmark control, not as a CA IX-selective hypothesis.",
        "source_anchor": "CA IX structure with acetazolamide",
        "source_url": "https://pubmed.ncbi.nlm.nih.gov/19805286/",
    },
    {
        "priority_rank": 2,
        "target_id": "CA IX",
        "slot_rank": 2,
        "compound_name": "Methazolamide",
        "compound_role": "systemic CA inhibitor alternative repurposing seed",
        "seed_status": "clinical_CA_inhibitor_seed_not_selective_claim",
        "why_selected": "Systemic carbonic anhydrase inhibitor alternative to acetazolamide that lets us test whether the acidic-arm plus CA II/CA XII counterscreen triangle is robust across more than one classical CA chemotype.",
        "key_caution": "Not a tumor-CA-selective claim; use as a second systemic CA benchmark under the same buffer program.",
        "source_anchor": "Methazolamide carbonic anhydrase inhibitor review",
        "source_url": "https://pubmed.ncbi.nlm.nih.gov/32251722/",
    },
    {
        "priority_rank": 2,
        "target_id": "CA IX",
        "slot_rank": 3,
        "compound_name": "Dichlorphenamide",
        "compound_role": "second systemic CA benchmark with different substitution pattern",
        "seed_status": "human_use_CA_inhibitor_seed_not_selective_claim",
        "why_selected": "Adds a differentiated systemic CA inhibitor benchmark so the first packet is not over-anchored to one sulfonamide control and can compare acidic-arm behavior across multiple human-use CA inhibitor scaffolds.",
        "key_caution": "Keep in the benchmark lane; do not present it as evidence of CA IX bias before CA II/CA XII counterscreens are run.",
        "source_anchor": "Dichlorphenamide and acetazolamide carbonic anhydrase inhibitor comparison",
        "source_url": "https://pubmed.ncbi.nlm.nih.gov/16368240/",
    },
    {
        "priority_rank": 3,
        "target_id": "SARS-CoV-2 Mpro",
        "slot_rank": 1,
        "compound_name": "Nirmatrelvir",
        "compound_role": "current clinical Mpro benchmark",
        "seed_status": "clinical_benchmark_seed_higher_cost_check_required",
        "why_selected": "The current practical benchmark for Mpro-directed antiviral activity and the cleanest way to calibrate assay sensitivity and partner confidence before asking a lab to inspect weaker repurposing candidates.",
        "key_caution": "Excellent benchmark, but likely not the cheapest seed in the set; keep cost and procurement friction explicit.",
        "source_anchor": "Nirmatrelvir coronavirus Mpro potency paper",
        "source_url": "https://pubmed.ncbi.nlm.nih.gov/36791846/",
    },
    {
        "priority_rank": 3,
        "target_id": "SARS-CoV-2 Mpro",
        "slot_rank": 2,
        "compound_name": "Boceprevir",
        "compound_role": "approved-history HCV protease repurposing seed",
        "seed_status": "direct_mpro_literature_seed_vendor_check_required",
        "why_selected": "One of the clearest human-use protease scaffolds with direct published SARS-CoV-2 Mpro inhibition and cell activity, making it a strong low-friction repurposing benchmark for the antiviral rail.",
        "key_caution": "Good mechanistic seed, but vendor availability and current pricing need to be checked before calling it a cheap packet component.",
        "source_anchor": "Boceprevir directly inhibits SARS-CoV-2 Mpro",
        "source_url": "https://pubmed.ncbi.nlm.nih.gov/32887884/",
    },
    {
        "priority_rank": 3,
        "target_id": "SARS-CoV-2 Mpro",
        "slot_rank": 3,
        "compound_name": "Telaprevir",
        "compound_role": "second approved-history HCV protease scaffold seed",
        "seed_status": "repurposing_screen_seed_vendor_check_required",
        "why_selected": "Gives the Mpro packet a second clinically used HCV protease scaffold family to test alongside boceprevir, and is directly cited in repurposing screens and derivative Mpro programs.",
        "key_caution": "Treat as a seed with procurement review pending, not as a guaranteed cheap current-market option.",
        "source_anchor": "HCV protease inhibitors as Mpro repurposing hits and derivative scaffold source",
        "source_url": "https://pubmed.ncbi.nlm.nih.gov/33524017/ ; https://pubmed.ncbi.nlm.nih.gov/33602867/",
    },
]


def build_payload() -> dict[str, Any]:
    summary = {
        "status": "wetlab_priority3_repurposing_seed_pool_ready",
        "target_count": len({row["target_id"] for row in ROWS}),
        "row_count": len(ROWS),
        "priority_targets": "T. cruzi PDE ; CA IX ; SARS-CoV-2 Mpro",
        "next_required_step": "Use this seed pool to fill the first-contact repurposing slots for the top-3 priority targets, then run vendor/cost checks before locking the outbound packets.",
    }
    return {"summary": summary, "rows": ROWS}


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Wet-Lab Priority-3 Repurposing Seed Pool",
        "",
        f"- status: `{s['status']}`",
        f"- target_count: `{s['target_count']}`",
        f"- row_count: `{s['row_count']}`",
        f"- priority_targets: `{s['priority_targets']}`",
        "",
        "| priority_rank | target_id | slot_rank | compound_name | compound_role | seed_status |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['priority_rank']}` | `{row['target_id']}` | `{row['slot_rank']}` | `{row['compound_name']}` | {row['compound_role']} | `{row['seed_status']}` |"
        )
    lines.extend(["", "## Seed Notes", ""])
    current_target = None
    for row in payload["rows"]:
        if row["target_id"] != current_target:
            current_target = row["target_id"]
            lines.extend([f"### {current_target}", ""])
        lines.extend([
            f"- `{row['compound_name']}`: {row['why_selected']}",
            f"  Caution: {row['key_caution']}",
            f"  Source: `{row['source_anchor']}` ({row['source_url']})",
        ])
    lines.extend(["", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the repurposing seed pool for the first three wet-lab contact targets.")
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
