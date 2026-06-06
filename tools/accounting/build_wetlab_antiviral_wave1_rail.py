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
DEFAULT_OUT_JSON = "runs/wetlab_antiviral_wave1_rail_current.json"
DEFAULT_OUT_CSV = "runs/wetlab_antiviral_wave1_rail_current.csv"
DEFAULT_OUT_MD = "runs/wetlab_antiviral_wave1_rail_current.md"

TARGET_ORDER = ["SARS-CoV-2 PLpro", "SARS-CoV-2 Mpro"]

TARGET_DETAILS: dict[str, dict[str, Any]] = {
    "SARS-CoV-2 PLpro": {
        "top_3_repurposing_slot_criteria": (
            "Cheap approved or clinic-exposed molecules with clean procurement, no obvious broad thiol-reactivity, "
            "and a plausible BL2-groove or substrate-cleft engagement story that can survive both biochemical and "
            "cell-based PLpro follow-up."
        ),
        "top_3_novelty_slot_criteria": (
            "Non-GRL0617-clone shallow-groove chemotypes prioritized for contact persistence in the BL2/S1-prime region, "
            "early human-DUB separation, and a tractable medicinal-chemistry path instead of generic cysteine-protease reactivity."
        ),
        "host_off_target_counterscreens": (
            "Human DUB panel first, especially USP12 or USP46 class deubiquitinases, plus a legacy USP21-style biochemical "
            "check and a generic cysteine-protease or reactivity sanity filter."
        ),
        "first_assay_stack": (
            "fluorogenic PLpro biochemical assay (Ub-rhodamine or comparable ISG15/Ub substrate) -> human DUB counterscreen -> "
            "in-cell PLpro assay such as BRET reporter confirmation -> orthogonal thermal or repeat biochemical confirmation"
        ),
        "one_page_brief_headline": (
            "PLpro micro-validation packet for READDI-style antiviral labs that starts by removing host-DUB liabilities instead "
            "of asking them to debug shallow-pocket artifacts."
        ),
        "main_external_lab_objection": (
            "PLpro hits are usually shallow-pocket artifacts or host-like DUB liabilities, so a new shortlist is not worth the screening effort."
        ),
        "objection_answer": (
            "The packet treats that objection as stage-0 design logic: only compounds with an explicit BL2-groove rationale, a human-DUB "
            "counterscreen plan, and an in-cell PLpro follow-up path are allowed into the top-3 slots."
        ),
        "primary_source_1_label": "PLpro mechanism-and-inhibition primary paper",
        "primary_source_1_url": "https://pubmed.ncbi.nlm.nih.gov/32845033/",
        "primary_source_2_label": "PLpro in-cell BRET assay paper",
        "primary_source_2_url": "https://pubmed.ncbi.nlm.nih.gov/39163165/",
        "open_science_source_label": "READDI coronavirus collaboration context",
        "open_science_source_url": "https://readdi.org/stories/the-readdi-forethought-team-aims-to-treat-current-and-future-coronaviruses/",
    },
    "SARS-CoV-2 Mpro": {
        "top_3_repurposing_slot_criteria": (
            "Cheap approved or commoditized antiviral or protease-adjacent molecules that tolerate rapid fluorogenic or fluorescence-polarization "
            "Mpro assays, have immediate commercial availability, and do not look like generic host-cysteine-protease liabilities."
        ),
        "top_3_novelty_slot_criteria": (
            "Non-nirmatrelvir-follow-on chemotypes chosen for dynamic subsite occupancy or dimer-context leverage, with a clear explanation for why "
            "they should outperform crowded-field generic warhead-first Mpro chemistry."
        ),
        "host_off_target_counterscreens": (
            "Host cysteine-protease sanity panel led by cathepsin L, then cathepsin B or related protease checks, plus aggregation or reactivity "
            "filters to remove dual-liability antiviral false positives."
        ),
        "first_assay_stack": (
            "fluorogenic or fluorescence-polarization Mpro biochemical assay -> host cysteine-protease counterscreen, especially cathepsin L -> "
            "orthogonal biochemical or thermal confirmation -> cell-based Mpro reporter confirmation if the biochemical signal survives"
        ),
        "one_page_brief_headline": (
            "Mpro fast-validation packet that uses the cheapest serious coronavirus protease rail to prove dynamics, selectivity, and repeatability in days."
        ),
        "main_external_lab_objection": (
            "Mpro is already crowded, so another external screen is unlikely to produce anything novel or worth scarce antiviral assay time."
        ),
        "objection_answer": (
            "The point is not another crowded hit list; it is a low-friction proof rail where compounds must survive cathepsin-led counterscreens, "
            "show dynamic pocket logic, and reproduce quickly enough to justify a partner lab's time."
        ),
        "primary_source_1_label": "Mpro assay-development and selectivity account",
        "primary_source_1_url": "https://pubmed.ncbi.nlm.nih.gov/36580641/",
        "primary_source_2_label": "Mpro fluorescence-polarization screening protocol",
        "primary_source_2_url": "https://pubmed.ncbi.nlm.nih.gov/36317181/",
        "open_science_source_label": "COVID Moonshot launch context",
        "open_science_source_url": "https://postera.ai/news/postera-and-collaborators-launch-covid-moonshot/",
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


def _rows_by_target(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("target_id", "")): dict(row)
        for row in payload.get("rows", []) or []
        if str(row.get("target_id", ""))
    }


def build_payload(
    portfolio: dict[str, Any],
    blueprint: dict[str, Any],
    companion: dict[str, Any],
    outreach: dict[str, Any],
) -> dict[str, Any]:
    portfolio_rows = _rows_by_target(portfolio)
    blueprint_rows = _rows_by_target(blueprint)
    companion_rows = _rows_by_target(companion)
    outreach_rows = {
        str(row.get("track_id", "")): dict(row)
        for row in outreach.get("rows", []) or []
        if str(row.get("track_id", ""))
    }

    rows: list[dict[str, Any]] = []
    for target_id in TARGET_ORDER:
        p = portfolio_rows[target_id]
        b = blueprint_rows[target_id]
        c = companion_rows[target_id]
        details = TARGET_DETAILS[target_id]
        track = outreach_rows[b["outreach_track_id"]]
        rows.append(
            {
                "target_id": target_id,
                "wave": p["wave"],
                "partner_track_id": b["outreach_track_id"],
                "partner_track_label": track["track_label"],
                "partner_rail": p["partner_rail"],
                "top_3_repurposing_slot_criteria": details["top_3_repurposing_slot_criteria"],
                "top_3_novelty_slot_criteria": details["top_3_novelty_slot_criteria"],
                "host_off_target_counterscreens": details["host_off_target_counterscreens"],
                "first_assay_stack": details["first_assay_stack"],
                "one_page_brief_headline": details["one_page_brief_headline"],
                "main_external_lab_objection": details["main_external_lab_objection"],
                "objection_answer": details["objection_answer"],
                "shared_wave1_assay_baseline": b["first_assay"],
                "shared_wave1_companion_panel": c["primary_companion_panel"],
                "primary_source_1_label": details["primary_source_1_label"],
                "primary_source_1_url": details["primary_source_1_url"],
                "primary_source_2_label": details["primary_source_2_label"],
                "primary_source_2_url": details["primary_source_2_url"],
                "open_science_source_label": details["open_science_source_label"],
                "open_science_source_url": details["open_science_source_url"],
            }
        )

    summary = {
        "status": "wetlab_antiviral_wave1_rail_ready",
        "target_count": len(rows),
        "track_id": "READDI_Korea",
        "required_slot_count_per_lane": 3,
        "source_policy": "primary_and_open_science_preferred",
        "next_required_step": (
            "Fill compound identities into the top-3 repurposing and top-3 novelty slots, then render a paired READDI_Korea "
            "first-contact packet for PLpro and Mpro together."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Wet-Lab Antiviral Wave 1 Rail",
        "",
        f"- status: `{s['status']}`",
        f"- target_count: `{s['target_count']}`",
        f"- track_id: `{s['track_id']}`",
        f"- required_slot_count_per_lane: `{s['required_slot_count_per_lane']}`",
        f"- source_policy: `{s['source_policy']}`",
        "",
    ]
    for row in payload["rows"]:
        lines.extend(
            [
                f"## {row['target_id']}",
                "",
                f"- wave: `{row['wave']}`",
                f"- partner_track_id: `{row['partner_track_id']}`",
                f"- partner_track_label: `{row['partner_track_label']}`",
                f"- partner_rail: `{row['partner_rail']}`",
                f"- top_3_repurposing_slot_criteria: {row['top_3_repurposing_slot_criteria']}",
                f"- top_3_novelty_slot_criteria: {row['top_3_novelty_slot_criteria']}",
                f"- host_off_target_counterscreens: {row['host_off_target_counterscreens']}",
                f"- first_assay_stack: {row['first_assay_stack']}",
                f"- one_page_brief_headline: {row['one_page_brief_headline']}",
                f"- main_external_lab_objection: {row['main_external_lab_objection']}",
                f"- objection_answer: {row['objection_answer']}",
                f"- shared_wave1_assay_baseline: {row['shared_wave1_assay_baseline']}",
                f"- shared_wave1_companion_panel: {row['shared_wave1_companion_panel']}",
                "",
                "### Sources",
                "",
                f"- {row['primary_source_1_label']}: {row['primary_source_1_url']}",
                f"- {row['primary_source_2_label']}: {row['primary_source_2_url']}",
                f"- {row['open_science_source_label']}: {row['open_science_source_url']}",
                "",
            ]
        )
    lines.extend(["## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the antiviral-only Wave 1 wet-lab rail packet.")
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
