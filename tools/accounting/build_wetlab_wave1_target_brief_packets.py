#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PORTFOLIO_JSON = "runs/wetlab_partner_target_portfolio_current.json"
DEFAULT_BLUEPRINT_JSON = "runs/wetlab_wave1_campaign_blueprint_current.json"
DEFAULT_COMPANION_JSON = "runs/wetlab_validation_companion_panels_current.json"
DEFAULT_OUTREACH_JSON = "runs/wetlab_partner_outreach_tracks_current.json"
DEFAULT_SCHEMA_JSON = "runs/wetlab_one_page_brief_schema_current.json"
DEFAULT_PRIORITY3_FILL_MAP_JSON = "runs/wetlab_priority3_repurposing_fill_map_current.json"
DEFAULT_PRIORITY3_NOVELTY_FILL_MAP_JSON = "runs/wetlab_priority3_novelty_fill_map_current.json"
DEFAULT_NEXT3_FILL_MAP_JSON = "runs/wetlab_next3_repurposing_fill_map_current.json"
DEFAULT_NEXT3_NOVELTY_FILL_MAP_JSON = "runs/wetlab_next3_novelty_fill_map_current.json"
DEFAULT_STK17B_FILL_MAP_JSON = "runs/wetlab_stk17b_repurposing_fill_map_current.json"
DEFAULT_STK17B_NOVELTY_FILL_MAP_JSON = "runs/wetlab_stk17b_novelty_fill_map_current.json"
DEFAULT_OUT_JSON = "runs/wetlab_wave1_target_brief_index_current.json"
DEFAULT_OUT_CSV = "runs/wetlab_wave1_target_brief_index_current.csv"
DEFAULT_OUT_MD = "runs/wetlab_wave1_target_brief_index_current.md"

TARGET_DETAILS = {
    "T. cruzi PDE": {
        "slug": "tcruzi_pde",
        "partner_track": "DNDi_IPK",
        "headline": "Selective parasite PDE triage for low-cost Chagas validation before medicinal chemistry spend.",
        "main_external_objection": "You will just rediscover human PDE inhibitors.",
        "objection_answer": "Lead with a human PDE mini-panel and require parasite-vs-human separation before any expansion decision.",
        "repurposing_rules": [
            "Approved or cheap clinical-stage PDE-adjacent small molecules with low procurement friction.",
            "Predicted parasite-pocket engagement without matching the strongest human PDE selectivity hotspots.",
            "Clean aqueous enzyme-assay behavior without obvious fluorescence or solubility liabilities.",
        ],
        "novelty_rules": [
            "Non-canonical scaffold relative to marketed human PDE inhibitor families.",
            "Preserves parasite-shape fit while avoiding the most human-like hinge or clamp motifs.",
            "Synthesis or procurement path is still realistic enough for a fast follow-up series.",
        ],
    },
    "Cruzain": {
        "slug": "cruzain",
        "partner_track": "DNDi_IPK",
        "headline": "Desolvation-aware Cruzain screening that trades reactive noise for clean protease validation.",
        "main_external_objection": "Protease hits at this stage are often just reactive false positives.",
        "objection_answer": "Bundle thiol-reactivity and host cysteine-protease sanity checks into the first validation packet so noisy hits are filtered immediately.",
        "repurposing_rules": [
            "Cheap approved or heavily commoditized molecules with plausible cysteine-protease compatibility but no obvious pan-reactive alerts.",
            "Reasonable aqueous behavior under fluorogenic protease assay conditions.",
            "A scaffold family that can be counter-screened quickly against host cysteine proteases.",
        ],
        "novelty_rules": [
            "Desolvation-favored pocket occupiers that are not generic electrophile traps.",
            "Non-PAINS chemistry with tractable follow-up synthesis or procurement.",
            "Selectivity-friendly geometry rather than brute-force covalent reactivity.",
        ],
    },
    "ALK2": {
        "slug": "alk2",
        "partner_track": "M4K_open_science",
        "headline": "Dynamic ALK2 state discrimination packaged for fast rare-disease kinase validation.",
        "main_external_objection": "Interesting kinase story, but BBB and selectivity will kill it later.",
        "objection_answer": "Make mutant-or-context selectivity and a BBB-aware repurposing lane part of the first packet instead of a later cleanup.",
        "repurposing_rules": [
            "Approved or cheap kinase-like molecules with at least a plausible CNS path or acceptable translational fallback.",
            "Predicted ALK2 engagement with early separation from the closest kinase liabilities.",
            "Chemotypes that survive simple DSF or biochemical assay conditions without formulation drama.",
        ],
        "novelty_rules": [
            "Scaffolds that exploit ALK2 state-specific or pocket-shape features rather than generic hinge binding.",
            "Selectivity-aware chemistry with a realistic route to mutant or pathway-biased follow-up.",
            "Not obviously doomed by CNS-exposure constraints if DIPG remains the lead use-case.",
        ],
    },
    "STK17B (DRAK2)": {
        "slug": "stk17b",
        "partner_track": "SGC_dark_kinase",
        "headline": "Open-set, P-loop-aware STK17B packets benchmarked against public PKIS and open-probe chemistry.",
        "main_external_objection": "Dark kinase stories often collapse into probe-chasing or generic kinase noise.",
        "objection_answer": "Start from the published PKIS benchmark trio and the 11-series open probe frame, then ask whether the dynamic model separates that open set better than the baseline literature ordering.",
        "repurposing_section_title": "Top-3 Cheap-Validation / Open-Set Slot Criteria",
        "current_repurposing_section_title": "Current Cheap-Validation / Open-Set Fill",
        "novelty_section_title": "Top-3 Open-Probe Novelty Slot Criteria",
        "current_novelty_section_title": "Current Open-Probe Novelty Fill",
        "repurposing_rules": [
            "Published low-friction PKIS or cheap-validation compounds that let the lab benchmark the packet before trusting dark-kinase novelty claims.",
            "A small open set that probes the STK17B P-loop frame without collapsing into generic hinge-binder noise.",
            "Clear benchmark value even if none of the rows become disease-facing leads.",
        ],
        "novelty_rules": [
            "Published 11-series or open-probe chemotypes chosen for P-loop-state discrimination rather than generic ATP-pocket occupancy.",
            "Comparable against the benchmark trio from the first DSF or biochemical pass.",
            "Strong enough structural-biology logic that a partner can decide quickly whether the dynamic model is adding value inside a known open set.",
        ],
    },
    "CA IX": {
        "slug": "caix",
        "partner_track": "oncology_condition_aware",
        "headline": "pH-conditioned CA IX ranking designed to hold up in tumor-like buffer, not just neutral default solvent.",
        "main_external_objection": "CA IX hits usually end up being just generic carbonic anhydrase inhibitors.",
        "objection_answer": "Run CA IX under acidic tumor-like buffer and ship CA II/CA XII counterscreens in the first packet so selectivity is tested immediately.",
        "repurposing_rules": [
            "Approved or cheap carbonic-anhydrase inhibitor chemotypes with straightforward procurement and assay history.",
            "Signal improves under acidic tumor-like buffer rather than only at neutral default conditions.",
            "A credible path to CA IX-biased behavior once CA II and CA XII are counterscreened.",
        ],
        "novelty_rules": [
            "Scaffolds selected for acidity-biased pocket occupancy or extracellular tumor-microenvironment fit.",
            "Not just another generic sulfonamide without a selectivity story.",
            "Can be explained in a one-page packet as a condition-aware hit rather than a generic CA binder.",
        ],
    },
    "SARS-CoV-2 PLpro": {
        "slug": "sarscov2_plpro",
        "partner_track": "READDI_Korea",
        "headline": "Low-friction PLpro packets with host-DUB liability addressed up front rather than after the first hit list.",
        "main_external_objection": "PLpro hits often bleed into host DUB-like liabilities and shallow-pocket artifacts.",
        "objection_answer": "Pair the first PLpro assay with host DUB-like counterscreens and require a dynamics-based pocket rationale, not just docking rank.",
        "repurposing_rules": [
            "Cheap approved or clinical-stage molecules that are unlikely to be generic thiol-reactive liabilities.",
            "Predicted to survive shallow-pocket validation better than simple sticky hydrophobes.",
            "Clean behavior in cheap fluorogenic protease assays.",
        ],
        "novelty_rules": [
            "Shallow-pocket or surface-anchoring scaffolds chosen for residence and contact persistence, not just score.",
            "Chemistry that can separate PLpro from host DUB-like liabilities early.",
            "A crisp selectivity narrative for a pandemic-preparedness pitch.",
        ],
    },
    "SARS-CoV-2 Mpro": {
        "slug": "sarscov2_mpro",
        "partner_track": "READDI_Korea",
        "headline": "Fast Mpro validation packets that compete on dynamics and selectivity, not just crowded-field hit lists.",
        "main_external_objection": "Mpro is crowded, so why should another hit list matter?",
        "objection_answer": "Use Mpro as the lowest-friction validation rail and differentiate on dynamic pocket occupancy, counterscreens, and fast repeatability.",
        "repurposing_rules": [
            "Approved or cheap protease-adjacent molecules with tractable procurement and low assay friction.",
            "No obvious host cysteine-protease liability in the first-pass counterscreen logic.",
            "Stable behavior in the cheapest fluorogenic Mpro assay stack.",
        ],
        "novelty_rules": [
            "Scaffolds chosen for dynamic pocket occupancy and follow-up novelty, not only for a crowded benchmark score.",
            "Differentiable from obvious pandemic-era chemotypes or generic reactive motifs.",
            "Rapidly testable with orthogonal biochemical or thermal confirmation.",
        ],
    },
    "Leishmania braziliensis DHODH": {
        "slug": "lbdhodh",
        "partner_track": "DNDi_IPK",
        "headline": "Neglected-disease DHODH packets that make host-enzyme separation part of the first experiment.",
        "main_external_objection": "DHODH stories can collapse if host-enzyme separation is weak.",
        "objection_answer": "Make host DHODH counterscreening a first-packet requirement so the neglected-disease story starts with selectivity, not hope.",
        "repurposing_rules": [
            "Cheap approved or commodity small molecules with plausible redox-enzyme compatibility and low procurement friction.",
            "Predicted parasite-enzyme fit that can be separated from host DHODH early.",
            "Assay-friendly chemistry without obvious redox or fluorescence artifacts.",
        ],
        "novelty_rules": [
            "Parasite-pocket-biased scaffolds that do not rely on obvious host-DHODH mimicry.",
            "Chemotypes suitable for fast follow-up if the first neglected-disease signal is clean.",
            "A strong enough mechanistic story for DNDi-style partner review even if repurposing is weak.",
        ],
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


def _maybe_load_json(path_like: str) -> dict[str, Any] | None:
    path = _resolve(path_like)
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _rows_by_target(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row.get("target_id", "")): dict(row) for row in payload.get("rows", []) or [] if str(row.get("target_id", ""))}


def _rows_by_target_grouped(payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in payload.get("rows", []) or []:
        target_id = str(row.get("target_id", "")).strip()
        if not target_id:
            continue
        grouped.setdefault(target_id, []).append(dict(row))
    return grouped


def build_payload(
    portfolio: dict[str, Any],
    blueprint: dict[str, Any],
    companion: dict[str, Any],
    outreach: dict[str, Any],
    schema: dict[str, Any],
    priority3_fill_map: dict[str, Any] | None = None,
    priority3_novelty_fill_map: dict[str, Any] | None = None,
    next3_fill_map: dict[str, Any] | None = None,
    next3_novelty_fill_map: dict[str, Any] | None = None,
    stk17b_fill_map: dict[str, Any] | None = None,
    stk17b_novelty_fill_map: dict[str, Any] | None = None,
) -> dict[str, Any]:
    portfolio_rows = _rows_by_target(portfolio)
    blueprint_rows = _rows_by_target(blueprint)
    companion_rows = _rows_by_target(companion)
    outreach_rows = {str(row.get("track_id", "")): dict(row) for row in outreach.get("rows", []) or []}
    schema_s = dict(schema.get("summary", {}) or {})
    fill_rows_by_target: dict[str, list[dict[str, Any]]] = {}
    for payload in (priority3_fill_map or {}, next3_fill_map or {}, stk17b_fill_map or {}):
        for target_id, target_rows in _rows_by_target_grouped(payload).items():
            fill_rows_by_target.setdefault(target_id, []).extend(target_rows)
    novelty_rows_by_target: dict[str, list[dict[str, Any]]] = {}
    for payload in (priority3_novelty_fill_map or {}, next3_novelty_fill_map or {}, stk17b_novelty_fill_map or {}):
        for target_id, target_rows in _rows_by_target_grouped(payload).items():
            novelty_rows_by_target.setdefault(target_id, []).extend(target_rows)

    rows: list[dict[str, Any]] = []
    for target_id, details in TARGET_DETAILS.items():
        p = portfolio_rows[target_id]
        b = blueprint_rows[target_id]
        c = companion_rows[target_id]
        track = outreach_rows[details["partner_track"]]
        fill_rows = sorted(fill_rows_by_target.get(target_id, []), key=lambda row: int(row.get("slot_rank", 0) or 0))
        novelty_rows = sorted(novelty_rows_by_target.get(target_id, []), key=lambda row: int(row.get("slot_rank", 0) or 0))
        rows.append(
            {
                "target_id": target_id,
                "artifact_path": f"runs/wetlab_target_brief_{details['slug']}_current.md",
                "wave": p["wave"],
                "partner_track": details["partner_track"],
                "headline": details["headline"],
                "first_assay": b["first_assay"],
                "anti_target_panel": c["primary_companion_panel"],
                "main_external_objection": details["main_external_objection"],
                "objection_answer": details["objection_answer"],
                "repurposing_rule_count": len(details["repurposing_rules"]),
                "novelty_rule_count": len(details["novelty_rules"]),
                "repurposing_fill_status": "actual_priority_fill_bound" if fill_rows else "slot_criteria_only",
                "repurposing_filled_slot_count": len(fill_rows),
                "novelty_fill_status": "actual_priority_fill_bound" if novelty_rows else "slot_criteria_only",
                "novelty_filled_slot_count": len(novelty_rows),
                "schema_summary_field_count": int(schema_s.get("summary_field_count", 0) or 0),
            }
        )

        brief_lines = [
            f"# Wet-Lab Target Brief: {target_id}",
            "",
            f"- target_id: `{target_id}`",
            f"- wave: `{p['wave']}`",
            f"- partner_track: `{details['partner_track']}`",
            f"- partner_rail: `{p['partner_rail']}`",
            f"- disease_area: `{p['disease_area']}`",
            f"- domain_family: `{p['domain_family']}`",
            f"- headline: {details['headline']}",
            f"- first_assay: {b['first_assay']}",
            f"- anti_target_panel: {c['primary_companion_panel']}",
            f"- first_go_no_go: {b['first_go_no_go']}",
            "",
            f"## {details.get('repurposing_section_title', 'Top-3 Repurposing Slot Criteria')}",
            "",
        ]
        brief_lines.extend(f"- {rule}" for rule in details["repurposing_rules"])
        if fill_rows:
            brief_lines.extend(["", f"## {details.get('current_repurposing_section_title', 'Current Repurposing Fill')}", ""])
            for row in fill_rows:
                flags: list[str] = [str(row["first_contact_use_mode"])]
                if row.get("vendor_check_required"):
                    flags.append("vendor_check_required")
                if row.get("cost_check_required"):
                    flags.append("cost_check_required")
                flag_text = ", ".join(flags)
                brief_lines.extend(
                    [
                        f"- `{row['brief_slot_name']}`: `{row['compound_name']}`",
                        f"  Usage: `{flag_text}`",
                        f"  Selectivity note: {row['selectivity_note']}",
                        f"  Must not do: {row['must_not_do']}",
                        f"  Source: `{row['source_anchor']}` ({row['source_url']})",
                    ]
                )
        if novelty_rows:
            brief_lines.extend(["", f"## {details.get('current_novelty_section_title', 'Current Novelty Fill')}", ""])
            for row in novelty_rows:
                flags: list[str] = [str(row["first_contact_use_mode"]), str(row["novelty_axis"])]
                if row.get("vendor_check_required"):
                    flags.append("vendor_check_required")
                if row.get("cost_check_required"):
                    flags.append("cost_check_required")
                flag_text = ", ".join(flags)
                brief_lines.extend(
                    [
                        f"- `{row['brief_slot_name']}`: `{row['novelty_compound_name']}`",
                        f"  Usage: `{flag_text}`",
                        f"  Selectivity note: {row['selectivity_note']}",
                        f"  Must not do: {row['must_not_do']}",
                        f"  Source: `{row['source_anchor']}` ({row['source_url']})",
                    ]
                )
        brief_lines.extend(["", f"## {details.get('novelty_section_title', 'Top-3 Novelty Slot Criteria')}", ""])
        brief_lines.extend(f"- {rule}" for rule in details["novelty_rules"])
        brief_lines.extend([
            "",
            "## External-Lab Objection",
            "",
            f"- objection: {details['main_external_objection']}",
            f"- answer: {details['objection_answer']}",
            "",
            "## Partner Track",
            "",
            f"- track_label: `{track['track_label']}`",
            f"- pitch_angle: {track['pitch_angle']}",
            f"- what_to_send_first: {track['what_to_send_first']}",
            f"- offer_model: {track['offer_model']}",
            "",
        ])
        out_path = _resolve(f"runs/wetlab_target_brief_{details['slug']}_current.md")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text("\n".join(brief_lines), encoding="utf-8")

    summary = {
        "status": "wetlab_wave1_target_brief_packets_ready",
        "target_count": len(rows),
        "schema_summary_field_count": int(schema_s.get("summary_field_count", 0) or 0),
        "open_first_target": "runs/wetlab_target_brief_tcruzi_pde_current.md",
        "next_required_step": "Fill actual top-3 repurposing and top-3 novelty candidates into these eight target briefs, then export partner-specific first-contact packets from the matching outreach track.",
    }
    return {"summary": summary, "rows": rows}


def _write_index_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Wet-Lab Wave 1 Target Brief Index",
        "",
        f"- status: `{s['status']}`",
        f"- target_count: `{s['target_count']}`",
        f"- schema_summary_field_count: `{s['schema_summary_field_count']}`",
        f"- open_first_target: `{s['open_first_target']}`",
        "",
        "| target_id | wave | partner_track | artifact_path | first_assay | anti_target_panel |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['wave']}` | `{row['partner_track']}` | `{row['artifact_path']}` | {row['first_assay']} | {row['anti_target_panel']} |"
        )
    lines.extend(["", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Wave 1 target-specific one-page wet-lab brief packets.")
    parser.add_argument("--portfolio-json", default=DEFAULT_PORTFOLIO_JSON)
    parser.add_argument("--blueprint-json", default=DEFAULT_BLUEPRINT_JSON)
    parser.add_argument("--companion-json", default=DEFAULT_COMPANION_JSON)
    parser.add_argument("--outreach-json", default=DEFAULT_OUTREACH_JSON)
    parser.add_argument("--schema-json", default=DEFAULT_SCHEMA_JSON)
    parser.add_argument("--priority3-fill-map-json", default=DEFAULT_PRIORITY3_FILL_MAP_JSON)
    parser.add_argument("--priority3-novelty-fill-map-json", default=DEFAULT_PRIORITY3_NOVELTY_FILL_MAP_JSON)
    parser.add_argument("--next3-fill-map-json", default=DEFAULT_NEXT3_FILL_MAP_JSON)
    parser.add_argument("--next3-novelty-fill-map-json", default=DEFAULT_NEXT3_NOVELTY_FILL_MAP_JSON)
    parser.add_argument("--stk17b-fill-map-json", default=DEFAULT_STK17B_FILL_MAP_JSON)
    parser.add_argument("--stk17b-novelty-fill-map-json", default=DEFAULT_STK17B_NOVELTY_FILL_MAP_JSON)
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
        _load_json(args.schema_json),
        _maybe_load_json(args.priority3_fill_map_json),
        _maybe_load_json(args.priority3_novelty_fill_map_json),
        _maybe_load_json(args.next3_fill_map_json),
        _maybe_load_json(args.next3_novelty_fill_map_json),
        _maybe_load_json(args.stk17b_fill_map_json),
        _maybe_load_json(args.stk17b_novelty_fill_map_json),
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv_rows(out_csv, payload["rows"])
    _write_index_markdown(out_md, payload)


if __name__ == "__main__":
    main()
