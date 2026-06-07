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
DEFAULT_OUT_JSON = "runs/wetlab_wave1_kinase_rail_packets_current.json"
DEFAULT_OUT_CSV = "runs/wetlab_wave1_kinase_rail_packets_current.csv"
DEFAULT_OUT_MD = "runs/wetlab_wave1_kinase_rail_packets_current.md"

KINASE_TARGETS = ("ALK2", "STK17B (DRAK2)")

SOURCE_PRESETS: dict[str, list[dict[str, str]]] = {
    "ALK2": [
        {
            "label": "M4K Pharma ALK2 DIPG open-science program",
            "url": "https://m4kpharma.com/",
        },
        {
            "label": "M4K Pharma ALK2 structure note for PDB 6SRH",
            "url": "https://m4kpharma.com/newsandblogs/iumrjoyjvef62ejzqbk1heul3jjgfw",
        },
        {
            "label": "PubMed 32787083 open-science CNS-penetrant ALK2 inhibitor paper",
            "url": "https://pubmed.ncbi.nlm.nih.gov/32787083/",
        },
        {
            "label": "M4K note on ALK2 NanoBRET cellular assay work",
            "url": "https://m4kpharma.com/newsandblogs/98ip1li3wit5u0lvkw23v4uqjo187y",
        },
    ],
    "STK17B (DRAK2)": [
        {
            "label": "SGC STK17B probe page for SGC-STK17B-1 and SGC-STK17B-1N",
            "url": "https://www.thesgc.org/chemical-probes/sgc-stk17b-1",
        },
        {
            "label": "PubMed 33215924 STK17B probe and unique P-loop conformation",
            "url": "https://pubmed.ncbi.nlm.nih.gov/33215924/",
        },
        {
            "label": "PMC full text for STK17B probe paper",
            "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC7816213/",
        },
    ],
}

DETAIL_PRESETS: dict[str, dict[str, Any]] = {
    "ALK2": {
        "top3_repurposing_slot_1_criteria": "Clinically familiar kinase scaffold with a plausible ALK2 or ACVR1 engagement hypothesis and a realistic pediatric CNS or BBB story on day one.",
        "top3_repurposing_slot_2_criteria": "BMP or TGF-beta pathway-adjacent kinase-active scaffold that can be purchased quickly and screened with an explicit plan to clear ALK5 spillover early.",
        "top3_repurposing_slot_3_criteria": "Repurposing-friendly kinase chemotype that can be benchmarked against public M4K ALK2 potency and NanoBRET-style cellular expectations without relying on de novo medicinal chemistry first.",
        "top3_novelty_slot_1_criteria": "State-discriminative ALK2 scaffold guided by the public M4K structural series and bound ALK2 geometry, rather than generic hinge-only kinase recycling.",
        "top3_novelty_slot_2_criteria": "Brain-penetrant novelty chemotype prioritized for ALK2 potency plus early separation from ALK5 and nearby BMP receptor kinases, using open-science reference series as the minimum benchmark.",
        "top3_novelty_slot_3_criteria": "Mutant-aware ALK2 or ACVR1 scaffold designed to exploit dynamic kinase-state differences while keeping oral or CNS tractability in scope for rare-disease follow-up.",
        "selectivity_anti_target_panel": "ALK2 mutant-versus-wild-type comparison plus an ALK1/ALK3/ALK5/ALK6 mini-panel, with an early CNS-friendly liability sanity note rather than a late apology.",
        "first_assay_stack": "Low-friction biochemical ALK2 kinase assay -> mutant or wild-type comparison -> DSF or orthogonal binding readout -> close-kinase mini-panel, with NanoBRET-style cellular engagement reserved as the first expansion step if the cheap stack is clean.",
        "one_page_brief_headline": "Open-science ALK2 packet that turns public structure, mutant-aware biology, and brain-penetrant benchmark chemistry into a fast rare-disease kinase validation plan.",
        "main_external_lab_objection": "Another kinase docking story is not enough, especially if BBB, mutant relevance, and ALK5-family selectivity are still fuzzy.",
        "objection_answer": "This packet is anchored to M4K's public ALK2 program, public structure 6SRH, and published brain-penetrant reference chemistry; the lab is asked for a cheap mutant-aware biochemical or DSF readout first, not an open-ended kinase campaign.",
    },
    "STK17B (DRAK2)": {
        "top3_repurposing_slot_1_criteria": "Clinically familiar or easily purchased kinase scaffold only if it plausibly exploits STK17B P-loop behavior and can be benchmarked against the public SGC-STK17B-1 and SGC-STK17B-1N pair.",
        "top3_repurposing_slot_2_criteria": "Cell-compatible kinase-active chemotype with manageable CAMK-family baggage and enough tractability to survive DSF or biochemical triage against a public probe baseline.",
        "top3_repurposing_slot_3_criteria": "Repurposing-friendly scaffold with a plausible route to the STK17B R41 or P-loop interaction logic, rather than a generic hinge-binder that immediately collapses under the probe benchmark.",
        "top3_novelty_slot_1_criteria": "Novel chemotype selected to induce or exploit the unique STK17B P-loop flip without simply copying the thieno[3,2-d]pyrimidine probe scaffold.",
        "top3_novelty_slot_2_criteria": "Dark-kinase scaffold that preserves STK17B versus STK17A discrimination and remains interpretable against public cocrystal and negative-control data.",
        "top3_novelty_slot_3_criteria": "Structure-biology-friendly chemotype suitable for DSF, biochemical, and follow-on cocrystal work if it beats the public negative-control envelope rather than merely matching it.",
        "selectivity_anti_target_panel": "SGC-STK17B-1 positive control, SGC-STK17B-1N negative control, and a neighborhood panel centered on STK17A and nearby DAPK-family kinases.",
        "first_assay_stack": "DSF or biochemical STK17B assay -> direct benchmark against the SGC-STK17B-1 positive probe and SGC-STK17B-1N negative control -> neighborhood kinase mini-panel, with cell engagement or structural follow-up only after the benchmark-first stack stays clean.",
        "one_page_brief_headline": "Probe-benchmarked STK17B packet built around unique P-loop dynamics instead of dark-kinase hand-waving.",
        "main_external_lab_objection": "Dark kinase projects often look interesting on slides but too under-validated to justify real lab effort.",
        "objection_answer": "This packet uses the public SGC probe, negative control, and P-loop structural story as the reference frame, so the first ask is a low-risk physical-validation exercise rather than a vague biology expedition.",
    },
}


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


def build_payload(
    portfolio: dict[str, Any],
    blueprint: dict[str, Any],
    companion: dict[str, Any],
    outreach: dict[str, Any],
) -> dict[str, Any]:
    portfolio_rows = {row["target_id"]: row for row in portfolio.get("rows", []) or []}
    blueprint_rows = {row["target_id"]: row for row in blueprint.get("rows", []) or []}
    companion_rows = {row["target_id"]: row for row in companion.get("rows", []) or []}
    outreach_rows = outreach.get("rows", []) or []

    rows: list[dict[str, Any]] = []
    for target_id in KINASE_TARGETS:
        p = portfolio_rows[target_id]
        b = blueprint_rows[target_id]
        c = companion_rows[target_id]
        detail = DETAIL_PRESETS[target_id]
        track = next((row for row in outreach_rows if target_id in str(row.get("best_targets", ""))), None)
        if track is None:
            raise KeyError(f"Missing outreach track for {target_id}")
        source_entries = SOURCE_PRESETS[target_id]
        row = {
            "target_id": target_id,
            "domain_family": p["domain_family"],
            "disease_area": p["disease_area"],
            "partner_track_id": track["track_id"],
            "partner_track_label": track["track_label"],
            "partner_rail": p["partner_rail"],
            "source_anchor_1_label": source_entries[0]["label"],
            "source_anchor_1_url": source_entries[0]["url"],
            "source_anchor_2_label": source_entries[1]["label"],
            "source_anchor_2_url": source_entries[1]["url"],
            "source_anchor_3_label": source_entries[2]["label"],
            "source_anchor_3_url": source_entries[2]["url"],
            "top3_repurposing_slot_1_criteria": detail["top3_repurposing_slot_1_criteria"],
            "top3_repurposing_slot_2_criteria": detail["top3_repurposing_slot_2_criteria"],
            "top3_repurposing_slot_3_criteria": detail["top3_repurposing_slot_3_criteria"],
            "top3_novelty_slot_1_criteria": detail["top3_novelty_slot_1_criteria"],
            "top3_novelty_slot_2_criteria": detail["top3_novelty_slot_2_criteria"],
            "top3_novelty_slot_3_criteria": detail["top3_novelty_slot_3_criteria"],
            "selectivity_anti_target_panel": detail["selectivity_anti_target_panel"],
            "selectivity_panel_anchor": c["primary_companion_panel"],
            "first_assay_stack": detail["first_assay_stack"],
            "first_assay_stack_anchor": b["first_assay"],
            "one_page_brief_headline": detail["one_page_brief_headline"],
            "main_external_lab_objection": detail["main_external_lab_objection"],
            "objection_answer": detail["objection_answer"],
            "status": "builder_ready_structured_content",
        }
        rows.append(row)

    summary = {
        "status": "wetlab_wave1_kinase_rail_packets_ready",
        "target_count": len(rows),
        "target_ids": ", ".join(KINASE_TARGETS),
        "input_artifact_count": 4,
        "required_section_count": 6,
        "next_required_step": "Use these rows as the source for target-specific ALK2 and STK17B first-contact packets, then fill actual top-3 repurposing and top-3 novelty compounds against the slot criteria.",
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Wet-Lab Wave 1 Kinase Rail Packets",
        "",
        f"- status: `{s['status']}`",
        f"- target_count: `{s['target_count']}`",
        f"- target_ids: `{s['target_ids']}`",
        f"- input_artifact_count: `{s['input_artifact_count']}`",
        f"- required_section_count: `{s['required_section_count']}`",
        "",
    ]
    for row in payload["rows"]:
        lines.extend([
            f"## {row['target_id']}",
            "",
            f"- partner_track: `{row['partner_track_label']}`",
            f"- partner_rail: `{row['partner_rail']}`",
            f"- source_anchor_1: [{row['source_anchor_1_label']}]({row['source_anchor_1_url']})",
            f"- source_anchor_2: [{row['source_anchor_2_label']}]({row['source_anchor_2_url']})",
            f"- source_anchor_3: [{row['source_anchor_3_label']}]({row['source_anchor_3_url']})",
            "",
            "### Top-3 Repurposing Slot Criteria",
            "",
            f"1. {row['top3_repurposing_slot_1_criteria']}",
            f"2. {row['top3_repurposing_slot_2_criteria']}",
            f"3. {row['top3_repurposing_slot_3_criteria']}",
            "",
            "### Top-3 Novelty Slot Criteria",
            "",
            f"1. {row['top3_novelty_slot_1_criteria']}",
            f"2. {row['top3_novelty_slot_2_criteria']}",
            f"3. {row['top3_novelty_slot_3_criteria']}",
            "",
            f"- selectivity_anti_target_panel: {row['selectivity_anti_target_panel']}",
            f"  Base panel anchor: {row['selectivity_panel_anchor']}",
            f"- first_assay_stack: {row['first_assay_stack']}",
            f"  Base assay anchor: {row['first_assay_stack_anchor']}",
            f"- one_page_brief_headline: {row['one_page_brief_headline']}",
            f"- main_external_lab_objection: {row['main_external_lab_objection']}",
            f"- objection_answer: {row['objection_answer']}",
            "",
        ])
    lines.extend(["## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build builder-ready Wave 1 kinase rail packet content for ALK2 and STK17B.")
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
