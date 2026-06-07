#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/wetlab_wave1_target_packets_current.json"
DEFAULT_OUT_CSV = "runs/wetlab_wave1_target_packets_current.csv"
DEFAULT_OUT_MD = "runs/wetlab_wave1_target_packets_current.md"

ROWS: list[dict[str, Any]] = [
    {
        "target_id": "T. cruzi PDE",
        "partner_track": "DNDi_IPK",
        "top3_repurposing_slot_criteria": "approved or low-cost cyclic-nucleotide/PDE-adjacent small molecules with easy procurement, no obvious pan-PDE red flags, and tractable parasite-vs-human selectivity hypothesis",
        "top3_novelty_slot_criteria": "parasite-biased heteroaromatic scaffolds that exploit dynamic subpockets or water-network differences while minimizing human PDE chemotype overlap",
        "anti_target_selectivity_panel": "human PDE family mini-panel plus simple cytotoxicity sanity check",
        "first_assay_stack": "recombinant parasite PDE enzyme assay -> human PDE counterscreen -> orthogonal thermal or secondary biochemical confirmation",
        "one_page_brief_headline": "Dynamic selectivity-first Chagas PDE packet designed to separate parasite PDE signal from human PDE liabilities before wet-lab scale-up.",
        "main_external_lab_objection": "PDE space has burned teams before because human PDE off-target risk overwhelms parasite selectivity.",
        "objection_answer": "We make human PDE separation part of stage-0 validation, so the first packet is not raw hit finding but filtered parasite-biased triage.",
    },
    {
        "target_id": "Cruzain",
        "partner_track": "DNDi_IPK",
        "top3_repurposing_slot_criteria": "cheap purchasable cysteine-protease-adjacent small molecules that are not obvious thiol-reactive junk and can be screened quickly in fluorogenic assays",
        "top3_novelty_slot_criteria": "non-peptidic desolvation-aware scaffolds that exploit the dynamic groove while avoiding generic electrophile dependence",
        "anti_target_selectivity_panel": "host cysteine protease mini-panel plus thiol-reactivity and aggregation sanity filters",
        "first_assay_stack": "fluorogenic Cruzain assay -> host cysteine protease counterscreen -> thiol-reactivity or aggregation sanity check -> orthogonal confirmation",
        "one_page_brief_headline": "Desolvation-aware Cruzain packet built to cut reactive false positives before external protease validation starts.",
        "main_external_lab_objection": "Protease hit lists are usually full of reactive artifacts and pan-cysteine noise.",
        "objection_answer": "We ship Cruzain with host protease, thiol-reactivity, and aggregation filters baked in so the lab sees a cleaner shortlist from day one.",
    },
    {
        "target_id": "Leishmania braziliensis DHODH",
        "partner_track": "DNDi_IPK",
        "top3_repurposing_slot_criteria": "approved or commoditized redox-enzyme-compatible heteroaromatics with easy procurement, simple solubility handling, and plausible host-parasite separation",
        "top3_novelty_slot_criteria": "parasite-biased enzyme scaffolds, including covalent-enabled or barbituric-acid-like chemotypes, chosen for cleaner host DHODH separation rather than broad repurposing appeal",
        "anti_target_selectivity_panel": "host DHODH counterscreen plus basic cell viability sanity check",
        "first_assay_stack": "recombinant LbDHODH enzyme assay -> host DHODH counterscreen -> orthogonal enzyme-format confirmation",
        "one_page_brief_headline": "Low-friction Leishmania DHODH packet that keeps host DHODH separation visible from the first wet-lab pass.",
        "main_external_lab_objection": "The repurposing lane is thinner here, so this can look like a niche chemistry project.",
        "objection_answer": "We treat repurposing as a fast screen only; the packet is primarily a neglected-enzyme validation story with explicit host-enzyme separation.",
    },
    {
        "target_id": "ALK2",
        "partner_track": "M4K_open_science",
        "top3_repurposing_slot_criteria": "approved or clinically familiar kinase-like compounds with manageable CNS path assumptions, plausible ALK2 hinge engagement, and low obvious pan-kinase baggage",
        "top3_novelty_slot_criteria": "fresh kinase scaffolds selected for dynamic ALK2 state discrimination, mutant or state preference, and reduced BMPR/TGF-beta spillover",
        "anti_target_selectivity_panel": "ALK2 close-kinase mini-panel with mutant-versus-wild-type comparison",
        "first_assay_stack": "biochemical ALK2 kinase assay -> DSF or orthogonal binding readout -> mutant/wild-type comparison -> mini-panel counterscreen",
        "one_page_brief_headline": "Open-science ALK2 packet focused on dynamic state discrimination rather than generic kinase hinge recycling.",
        "main_external_lab_objection": "Kinase repurposing often collapses into generic hinge binders with weak selectivity.",
        "objection_answer": "The packet splits repurposing and novelty lanes and requires mutant/wild-type plus mini-panel separation before any broader push.",
    },
    {
        "target_id": "STK17B (DRAK2)",
        "partner_track": "SGC_dark_kinase",
        "top3_repurposing_slot_criteria": "approved kinase-adjacent molecules only if they plausibly exploit STK17B P-loop dynamics and do not simply replay known broad kinase liabilities",
        "top3_novelty_slot_criteria": "probe-benchmarked scaffolds chosen to exploit transient P-loop states beyond the existing open-probe and negative-control envelope",
        "anti_target_selectivity_panel": "open-probe positive/negative controls plus neighborhood dark-kinase mini-panel",
        "first_assay_stack": "DSF or biochemical STK17B assay -> benchmark against open probe and negative control -> neighborhood kinase counterscreen",
        "one_page_brief_headline": "Dark-kinase STK17B packet that turns transient P-loop dynamics into a fast structural-biology validation story.",
        "main_external_lab_objection": "Dark kinases can look biologically interesting but too under-validated to justify effort.",
        "objection_answer": "We position STK17B as a low-cost physical-validation story against an existing open-probe baseline, which is publication-friendly even before deeper disease work.",
    },
    {
        "target_id": "CA IX",
        "partner_track": "oncology_condition_aware",
        "top3_repurposing_slot_criteria": "cheap approved carbonic-anhydrase inhibitor chemotypes that can be profiled under acidic tumor-like buffer and are easy to procure immediately",
        "top3_novelty_slot_criteria": "pH-biased CA IX scaffolds selected for acidic-condition advantage and reduced CA II or CA XII overlap, including non-classical zinc-binding options",
        "anti_target_selectivity_panel": "CA II plus CA XII counterscreen with acidic and neutral condition comparison",
        "first_assay_stack": "CA IX enzyme assay in acidic tumor-like buffer -> CA II or CA XII counterscreen -> neutral-buffer comparison -> optional hypoxia-context follow-up",
        "one_page_brief_headline": "Condition-aware CA IX packet built around acidic-buffer selectivity rather than generic pan-carbonic-anhydrase inhibition.",
        "main_external_lab_objection": "This may just rediscover nonselective carbonic-anhydrase inhibitors.",
        "objection_answer": "We only ship compounds if the packet preserves an acidic-condition CA IX edge against CA II and CA XII counterscreens.",
    },
    {
        "target_id": "SARS-CoV-2 PLpro",
        "partner_track": "READDI_Korea",
        "top3_repurposing_slot_criteria": "cheap or approved antiviral/proteostasis-adjacent molecules that are easy to source and not obvious generic thiol traps, with plausible PLpro engagement hypotheses",
        "top3_novelty_slot_criteria": "shallow-pocket or surface-clamping scaffolds chosen for PLpro dynamics and reduced host-like DUB overlap",
        "anti_target_selectivity_panel": "host DUB-like or cysteine-protease counterscreen plus simple reactivity sanity filter",
        "first_assay_stack": "fluorogenic PLpro assay -> host DUB-like counterscreen -> orthogonal protease or thermal confirmation",
        "one_page_brief_headline": "PLpro packet that starts with host-liability filtering instead of asking a partner lab to sift shallow-pocket noise.",
        "main_external_lab_objection": "PLpro hits frequently cross-hit host deubiquitinase-like proteins.",
        "objection_answer": "That exact counterscreen is in stage 0, so the outbound packet is framed as filtered antiviral triage rather than generic hit fishing.",
    },
    {
        "target_id": "SARS-CoV-2 Mpro",
        "partner_track": "READDI_Korea",
        "top3_repurposing_slot_criteria": "cheap approved or commoditized small molecules compatible with fast fluorogenic screening, low procurement friction, and low obvious PAINS or reactivity flags",
        "top3_novelty_slot_criteria": "dynamic subsite-aware or dimer-context scaffolds that differentiate the campaign from crowded generic warhead-first Mpro screening",
        "anti_target_selectivity_panel": "host cysteine protease sanity panel plus aggregation or reactivity filter",
        "first_assay_stack": "fluorogenic Mpro assay -> orthogonal thermal or biochemical confirmation -> host cysteine protease sanity panel",
        "one_page_brief_headline": "Fast Mpro micro-validation packet positioned as a dynamics-selectivity proving ground, not another generic crowded protease screen.",
        "main_external_lab_objection": "Mpro is too crowded to justify another external validation effort.",
        "objection_answer": "We pitch Mpro as the cheapest fast-validation rail for the engine's dynamics and selectivity filters, which lowers partner risk and shortens time to a clean yes or no.",
    },
]


def build_payload() -> dict[str, Any]:
    summary = {
        "status": "wetlab_wave1_target_packets_ready",
        "row_count": len(ROWS),
        "partner_track_count": len({row["partner_track"] for row in ROWS}),
        "required_fields_count": 8,
        "next_required_step": "Use these target rows as the source material for target-specific one-page briefs and partner-first outbound packets; fill compound identities into the repurposing and novelty slots next.",
    }
    return {"summary": summary, "rows": ROWS}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Wet-Lab Wave 1 Target Packets",
        "",
        f"- status: `{s['status']}`",
        f"- row_count: `{s['row_count']}`",
        f"- partner_track_count: `{s['partner_track_count']}`",
        f"- required_fields_count: `{s['required_fields_count']}`",
        "",
    ]
    for row in payload["rows"]:
        lines.extend([
            f"## {row['target_id']}",
            "",
            f"- partner_track: `{row['partner_track']}`",
            f"- top3_repurposing_slot_criteria: {row['top3_repurposing_slot_criteria']}",
            f"- top3_novelty_slot_criteria: {row['top3_novelty_slot_criteria']}",
            f"- anti_target_selectivity_panel: {row['anti_target_selectivity_panel']}",
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
    parser = argparse.ArgumentParser(description="Build Wave 1 target-specific wet-lab packet rows.")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
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
