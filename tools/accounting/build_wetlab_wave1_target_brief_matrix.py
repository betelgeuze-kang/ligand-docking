#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/wetlab_wave1_target_brief_matrix_current.json"
DEFAULT_OUT_CSV = "runs/wetlab_wave1_target_brief_matrix_current.csv"
DEFAULT_OUT_MD = "runs/wetlab_wave1_target_brief_matrix_current.md"

ROWS = [
    {
        "target_id": "T. cruzi PDE",
        "top_3_repurposing_slot_criteria": "Cheap approved oral small molecules with PDE-like hinge recognition or cyclic-nucleotide-pocket compatibility, low PAINS/reactivity, and early human PDE counterscreen tractability.",
        "top_3_novelty_slot_criteria": "Parasite-selective pocket vectors, non-classical PDE chemotypes, rigid heteroaromatic cores, and explicit human-PDE anti-target separation.",
        "anti_target_panel": "human PDE family mini-panel",
        "first_assay_stack": "recombinant parasite PDE assay -> human PDE counterscreen -> orthogonal thermal or enzyme-repeat confirmation",
        "one_page_brief_headline": "Exploit parasite-selective PDE dynamics to beat the human-PDE selectivity trap in low-cost Chagas enzyme validation.",
        "main_external_lab_objection": "This will probably just rediscover non-selective human PDE inhibitors.",
        "objection_answer": "The packet is only valid if parasite PDE signal is paired with an immediate human PDE counterscreen and the shortlist is pre-filtered for anti-target separation rather than raw potency alone.",
    },
    {
        "target_id": "Cruzain",
        "top_3_repurposing_slot_criteria": "Cheap approved or commoditized small molecules with cysteine-protease-compatible geometry, good assay solubility, and no generic thiol-reactivity red flags.",
        "top_3_novelty_slot_criteria": "Desolvation-aware binders that use pocket-shape drift, non-panreactive reversible warheads or warhead-free anchors, and explicit host cysteine-protease separation.",
        "anti_target_panel": "host cysteine protease plus thiol-reactivity sanity set",
        "first_assay_stack": "fluorogenic Cruzain assay -> thiol-reactivity check -> host cysteine protease counterscreen",
        "one_page_brief_headline": "Use dynamics plus desolvation to cut through Cruzain false positives before wet-lab money is wasted.",
        "main_external_lab_objection": "Cheap protease hits here are usually just reactive junk.",
        "objection_answer": "The outbound packet makes reactivity filtering and host-protease counterscreen part of the first pass, so the lab is not being asked to sort reactive noise after the fact.",
    },
    {
        "target_id": "ALK2",
        "top_3_repurposing_slot_criteria": "Approved or late-stage kinase-like compounds with ALK2-compatible hinge motif, acceptable CNS plausibility, strong assay solubility, and early mutant-vs-wild-type discrimination potential.",
        "top_3_novelty_slot_criteria": "Fresh type-I or nearby-state chemotypes that exploit dynamic kinase-state differences while remaining small, synthesis-light, and assay-friendly.",
        "anti_target_panel": "ALK2 close-kinase selectivity mini-panel with mutant/wild-type comparison",
        "first_assay_stack": "biochemical ALK2 assay or DSF -> mutant/wild-type comparison -> close-kinase counterscreen",
        "one_page_brief_headline": "Turn open-science ALK2 infrastructure into a fast repurposing-plus-novelty validation loop for DIPG-relevant kinase dynamics.",
        "main_external_lab_objection": "Interesting kinase story, but the shortlist will collapse once selectivity and CNS reality are checked.",
        "objection_answer": "The Wave 1 packet requires mutant/wild-type and mini-selectivity gates up front, so only compounds that survive both are promoted to external validation.",
    },
    {
        "target_id": "STK17B (DRAK2)",
        "top_3_repurposing_slot_criteria": "Clinically exposed kinase-like compounds with compact ATP-site-compatible cores, strong DSF handling, and limited broad-cytotoxic baggage.",
        "top_3_novelty_slot_criteria": "P-loop-sensitive chemotypes benchmarkable against the open probe and negative control, with a clear structural-biology readout story.",
        "anti_target_panel": "open-probe positive/negative controls plus neighborhood kinase panel",
        "first_assay_stack": "DSF or kinase engagement assay -> open-probe benchmark -> neighborhood kinase counterscreen",
        "one_page_brief_headline": "Use dynamic P-loop discrimination to make STK17B a dark-kinase validation story a structural-biology lab can say yes to quickly.",
        "main_external_lab_objection": "Dark kinase hits are hard to trust without a benchmarked probe context.",
        "objection_answer": "The first packet is explicitly probe-benchmarked and includes negative-control context, so the lab can judge novelty against a known reference instead of a black-box ranking.",
    },
    {
        "target_id": "CA IX",
        "top_3_repurposing_slot_criteria": "Low-cost approved sulfonamide or carbonic-anhydrase-active compounds that remain tractable in acidic tumor-like buffer and can be counterscreened against CA II and CA XII immediately.",
        "top_3_novelty_slot_criteria": "pH-biased CA IX chemotypes with extra vectors for IX-selective recognition, low-cost synthesis paths, and explicit CA II/CA XII separation logic.",
        "anti_target_panel": "CA II plus CA XII counterscreen",
        "first_assay_stack": "acidic-buffer CA IX enzyme assay -> CA II/CA XII counterscreen -> optional neutral-buffer contrast run",
        "one_page_brief_headline": "Give oncology labs a pH-conditioned CA IX shortlist that behaves like their buffer, not a generic neutral-pH docking story.",
        "main_external_lab_objection": "This will just rediscover non-selective carbonic anhydrase inhibitors.",
        "objection_answer": "The packet only advances compounds that show acidic-condition advantage together with immediate CA II and CA XII counterscreen separation.",
    },
    {
        "target_id": "SARS-CoV-2 PLpro",
        "top_3_repurposing_slot_criteria": "Cheap approved or heavily commoditized small molecules with protease-compatible polarity, low aggregation risk, and no obvious broad DUB-like liability.",
        "top_3_novelty_slot_criteria": "Shallow-groove PLpro chemotypes optimized for dynamic contact persistence and early host-DUB separation rather than generic cysteine-reactive behavior.",
        "anti_target_panel": "host DUB-like or cysteine-protease counterscreen",
        "first_assay_stack": "fluorogenic PLpro assay -> host DUB-like counterscreen -> orthogonal repeat or thermal confirmation",
        "one_page_brief_headline": "Offer READDI-style labs a low-friction PLpro package that screens dynamics-driven hits without offloading host-liability cleanup onto them.",
        "main_external_lab_objection": "PLpro hits are often host-like DUB liabilities or shallow-pocket artifacts.",
        "objection_answer": "The first-pass packet includes host-like counterscreens and only promotes compounds whose story is dynamic contact persistence plus early off-target separation.",
    },
    {
        "target_id": "SARS-CoV-2 Mpro",
        "top_3_repurposing_slot_criteria": "Cheap approved or commoditized antiviral/protease-adjacent small molecules with high assay tractability, low aggregation risk, and immediate follow-up availability.",
        "top_3_novelty_slot_criteria": "Fresh Mpro chemotypes that are not generic covalent protease clichés, with clear pocket occupancy logic and a low-friction assay story.",
        "anti_target_panel": "host cysteine protease sanity panel",
        "first_assay_stack": "fluorogenic Mpro assay -> orthogonal biochemical or thermal confirmation -> host cysteine protease sanity check",
        "one_page_brief_headline": "Use the cheapest serious antiviral protease assay rail to prove the platform can hand labs hits they can validate in days, not months.",
        "main_external_lab_objection": "Mpro is crowded, so this is unlikely to look novel or worth a lab's time.",
        "objection_answer": "The pitch is not generic Mpro hit-finding; it is a low-friction dynamics-and-selectivity package where novelty is framed against crowded-field baseline rather than ignored.",
    },
    {
        "target_id": "Leishmania braziliensis DHODH",
        "top_3_repurposing_slot_criteria": "Cheap approved or commoditized enzyme-active heteroaromatics with DHODH-like tractability, reasonable assay solubility, and immediate host-DHODH counterscreenability.",
        "top_3_novelty_slot_criteria": "Neglected-disease enzyme chemotypes that exploit parasite-enzyme divergence, support low-cost synthesis, and preserve a clear host-DHODH separation story.",
        "anti_target_panel": "host DHODH or close-enzyme counterscreen",
        "first_assay_stack": "recombinant parasite DHODH assay -> host DHODH counterscreen -> orthogonal enzyme-repeat confirmation",
        "one_page_brief_headline": "Convert a DNDi-validated leishmaniasis enzyme into a low-friction validation package with host-enzyme separation built in from day one.",
        "main_external_lab_objection": "Interesting neglected-disease enzyme, but the repurposing angle may be too thin to justify quick external work.",
        "objection_answer": "The campaign treats repurposing as the cheap first triage lane and keeps the stronger value proposition in the novelty lane, both anchored by a simple host-DHODH counterscreen.",
    },
]


def build_payload() -> dict[str, Any]:
    summary = {
        "status": "wetlab_wave1_target_brief_matrix_ready",
        "row_count": len(ROWS),
        "wave1_target_count": len(ROWS),
        "required_slot_count_per_lane": 3,
        "required_lane_set": "repurposing + novelty + anti_target_panel",
        "next_required_step": "Use this matrix to fill target-specific one-page brief packets, starting with T. cruzi PDE, CA IX, and SARS-CoV-2 Mpro as the fastest mixed portfolio demonstration.",
    }
    return {"summary": summary, "rows": ROWS}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Wet-Lab Wave 1 Target Brief Matrix",
        "",
        f"- status: `{s['status']}`",
        f"- row_count: `{s['row_count']}`",
        f"- required_slot_count_per_lane: `{s['required_slot_count_per_lane']}`",
        f"- required_lane_set: `{s['required_lane_set']}`",
        "",
        "| target_id | anti_target_panel | one_page_brief_headline |",
        "| --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | {row['anti_target_panel']} | {row['one_page_brief_headline']} |"
        )
    lines.extend(["", "## Target Rows", ""])
    for row in payload["rows"]:
        lines.extend([
            f"### {row['target_id']}",
            "",
            f"- top_3_repurposing_slot_criteria: {row['top_3_repurposing_slot_criteria']}",
            f"- top_3_novelty_slot_criteria: {row['top_3_novelty_slot_criteria']}",
            f"- anti_target_panel: {row['anti_target_panel']}",
            f"- first_assay_stack: {row['first_assay_stack']}",
            f"- one_page_brief_headline: {row['one_page_brief_headline']}",
            f"- main_external_lab_objection: {row['main_external_lab_objection']}",
            f"- objection_answer: {row['objection_answer']}",
            "",
        ])
    lines.extend(["## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the Wave 1 target brief matrix for outbound wet-lab packets.")
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
