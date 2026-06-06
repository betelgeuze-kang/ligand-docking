#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_JSON = "runs/wetlab_neglected_wave1_rows_current.json"
DEFAULT_OUT_CSV = "runs/wetlab_neglected_wave1_rows_current.csv"
DEFAULT_OUT_MD = "runs/wetlab_neglected_wave1_rows_current.md"

ROWS: list[dict[str, Any]] = [
    {
        "target_id": "T. cruzi PDE",
        "partner_track": "DNDi_IPK",
        "top3_repurposing_slot_criteria": (
            "approved or cheaply purchasable cyclic-nucleotide or PDE-adjacent small molecules with fast procurement, "
            "no obvious pan-human-PDE baggage, and a concrete parasite-vs-human selectivity hypothesis before assay entry"
        ),
        "top3_novelty_slot_criteria": (
            "parasite-biased heteroaromatic or subpocket-seeking scaffolds that exploit dynamic pocket or water-network "
            "differences while minimizing overlap with known human PDE chemotypes"
        ),
        "anti_target_selectivity_panel": (
            "human PDE family mini-panel at minimum, plus simple mammalian cytotoxicity sanity check; do not ship a PDE "
            "packet without an explicit parasite-vs-human separation readout in stage 0"
        ),
        "first_assay_stack": (
            "recombinant T. cruzi PDE inhibition assay -> human PDE counterscreen -> orthogonal thermal or secondary "
            "biochemical confirmation -> only then cell-facing follow-up"
        ),
        "one_page_brief_headline": (
            "Selectivity-first Chagas PDE validation packet built to prove parasite PDE signal before any lab spends time "
            "on human-PDE liabilities."
        ),
        "main_external_lab_objection": (
            "The PDE field has a history of false hope because human PDE off-target activity overwhelms parasite "
            "selectivity."
        ),
        "objection_answer": (
            "This packet makes human PDE separation part of the first assay stack, so the lab is not being asked to do "
            "generic hit fishing but filtered parasite-biased triage."
        ),
    },
    {
        "target_id": "Cruzain",
        "partner_track": "DNDi_IPK",
        "top3_repurposing_slot_criteria": (
            "cheap purchasable cysteine-protease-adjacent molecules only if they avoid obvious thiol-reactive junk, can "
            "run cleanly in fluorogenic format, and remain operationally simple for a low-cost first pass"
        ),
        "top3_novelty_slot_criteria": (
            "non-peptidic desolvation-aware scaffolds chosen to exploit Cruzain groove dynamics while avoiding generic "
            "electrophile-driven or aggregation-driven false positives"
        ),
        "anti_target_selectivity_panel": (
            "host cysteine protease mini-panel plus explicit thiol-reactivity and aggregation filters; reactive or sticky "
            "hits should fail before any external expansion"
        ),
        "first_assay_stack": (
            "fluorogenic Cruzain assay -> host cysteine protease counterscreen -> thiol-reactivity and aggregation sanity "
            "checks -> orthogonal confirmation"
        ),
        "one_page_brief_headline": (
            "Desolvation-aware Cruzain packet designed to remove reactive protease noise before external Chagas validation "
            "begins."
        ),
        "main_external_lab_objection": (
            "Protease hit lists are usually dominated by reactive artifacts and broad cysteine-protease noise."
        ),
        "objection_answer": (
            "The outbound packet already includes host protease, reactivity, and aggregation filters, so the lab receives "
            "a cleaner shortlist rather than a raw fluorogenic false-positive dump."
        ),
    },
    {
        "target_id": "Leishmania braziliensis DHODH",
        "partner_track": "DNDi_IPK",
        "top3_repurposing_slot_criteria": (
            "approved or commoditized heteroaromatic enzyme-compatible molecules with easy procurement, manageable "
            "solubility handling, and a plausible host-vs-parasite separation story"
        ),
        "top3_novelty_slot_criteria": (
            "parasite-biased DHODH scaffolds, including covalent-enabled or barbituric-acid-like chemotypes, prioritized "
            "for clean host DHODH separation rather than broad repurposing appeal"
        ),
        "anti_target_selectivity_panel": (
            "host DHODH counterscreen plus basic cell-viability sanity check; a neglected-enzyme packet is only credible "
            "if host-enzyme separation is visible immediately"
        ),
        "first_assay_stack": (
            "recombinant L. braziliensis DHODH enzyme assay -> host DHODH counterscreen -> orthogonal enzyme-format "
            "confirmation -> optional simple cellular sanity follow-up"
        ),
        "one_page_brief_headline": (
            "Low-friction Leishmania DHODH packet that keeps host DHODH separation visible from the first wet-lab pass."
        ),
        "main_external_lab_objection": (
            "The repurposing lane looks thin, so this can read like a niche medicinal-chemistry project rather than a "
            "fast validation opportunity."
        ),
        "objection_answer": (
            "Repurposing is treated as a cheap triage lane only; the main value is a neglected-disease enzyme packet with "
            "clear host-enzyme separation and a simple recombinant assay path."
        ),
    },
]


def build_payload() -> dict[str, Any]:
    return {
        "summary": {
            "status": "wetlab_neglected_wave1_rows_ready",
            "target_count": len(ROWS),
            "partner_track": "DNDi_IPK",
            "required_field_count": 8,
            "source_artifacts": (
                "runs/wetlab_partner_target_portfolio_current.md; "
                "runs/wetlab_wave1_campaign_blueprint_current.md; "
                "runs/wetlab_validation_companion_panels_current.md; "
                "runs/wetlab_partner_outreach_tracks_current.md"
            ),
            "next_required_step": (
                "Fill compound identities into the repurposing and novelty slots, then fork these rows into DNDi/IPK "
                "one-page briefs and first-contact wet-lab packets."
            ),
        },
        "rows": ROWS,
    }


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# Wet-Lab Neglected-Disease Wave 1 Rows",
        "",
        f"- status: `{summary['status']}`",
        f"- target_count: `{summary['target_count']}`",
        f"- partner_track: `{summary['partner_track']}`",
        f"- required_field_count: `{summary['required_field_count']}`",
        f"- source_artifacts: `{summary['source_artifacts']}`",
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
    lines.extend(["## Next Step", "", f"- {summary['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build neglected-disease Wave 1 wet-lab row recommendations.")
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
