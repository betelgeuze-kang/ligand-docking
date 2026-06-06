#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab_target_render_utils import load_json, payload_summary, rows_by_target, write_artifact

DEFAULT_PORTFOLIO_JSON = "runs/wetlab_partner_target_portfolio_current.json"
DEFAULT_VALIDATION_JSON = "runs/wetlab_validation_companion_panels_current.json"
DEFAULT_REPURPOSING_FILL_JSON = "runs/wetlab_dpre1_repurposing_fill_map_current.json"
DEFAULT_NOVELTY_FILL_JSON = "runs/wetlab_dpre1_novelty_fill_map_current.json"
DEFAULT_SUITE_MD = "runs/dpre1_render_suite_current.md"
DEFAULT_CONDITION_CARD_MD = "runs/dpre1_condition_card_current.md"
DEFAULT_PANEL_MD = "runs/dpre1_selectivity_panel_current.md"
DEFAULT_ASSAY_MD = "runs/dpre1_assay_packet_current.md"
DEFAULT_GONOGO_MD = "runs/dpre1_go_no_go_card_current.md"
DEFAULT_EXPORT_MD = "runs/dpre1_tb_alliance_export_current.md"
TARGET_ID = "DprE1"


def build_payload(portfolio_payload: dict[str, Any], validation_payload: dict[str, Any], repurposing_fill_payload: dict[str, Any] | None = None, novelty_fill_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    portfolio_row = rows_by_target(portfolio_payload)[TARGET_ID]
    validation_row = rows_by_target(validation_payload)[TARGET_ID]
    rep_rows = [dict(row) for row in ((repurposing_fill_payload or {}).get("rows", []) or []) if str(row.get("target_id", "")).strip() == TARGET_ID]
    nov_rows = [dict(row) for row in ((novelty_fill_payload or {}).get("rows", []) or []) if str(row.get("target_id", "")).strip() == TARGET_ID]
    rep_controls = "; ".join(str(row.get("compound_name", "")).strip() for row in rep_rows if str(row.get("compound_name", "")).strip())
    nov_controls = "; ".join(str(row.get("novelty_compound_name", "")).strip() for row in nov_rows if str(row.get("novelty_compound_name", "")).strip())
    content_ready = len(rep_rows) >= 3 and len(nov_rows) >= 3

    condition_card = {
        "summary": payload_summary("dpre1_condition_card_ready", TARGET_ID, "condition_card", 4, "Use this card as the fixed DprE1 biochemical-plus-whole-cell context before interpreting any TB expansion claim."),
        "structured": {
            "target_id": TARGET_ID,
            "partner_track_id": "TB_Alliance",
            "primary_biochemical_arm": "recombinant DprE1 enzymatic inhibition arm with simple target-engagement framing",
            "whole_cell_arm": "whole-cell M. tuberculosis orthogonal replay after biochemical survivors are cleaned",
            "host_enzyme_sanity": "host-enzyme sanity plus whole-cell orthogonal validation panel",
            "first_go_no_go": "promote only rows that keep DprE1 biochemical signal while surviving host-enzyme sanity and whole-cell orthogonal replay",
            "repurposing_controls": rep_controls or "pending_wave2_compound_fill",
            "novelty_controls": nov_controls or "pending_wave2_compound_fill",
            "content_ready": content_ready,
            "source_anchor": portfolio_row["source_anchor"],
            "source_url": portfolio_row["source_url"],
        },
        "rows": [
            {"condition_name": "primary_dpre1_biochemical_arm", "value": "recombinant DprE1 inhibition assay", "why": "keeps the packet target-centered before more expensive whole-cell work", "source_anchor": portfolio_row["source_anchor"]},
            {"condition_name": "whole_cell_orthogonal_arm", "value": validation_row["primary_companion_panel"], "why": "novel TB enzyme hits need an orthogonal whole-cell sanity check before expansion", "source_anchor": validation_row["primary_companion_panel"]},
            {"condition_name": "host_enzyme_sanity", "value": "host-enzyme counterscreen before whole-cell escalation", "why": "removes broad enzyme or redox noise before DprE1-specific claims", "source_anchor": validation_row["companion_why"]},
            {"condition_name": "first_packet_scope", "value": "bounded biochemical packet first, then whole-cell orthogonal replay for cleaned survivors", "why": "keeps the first DprE1 packet cheaper than a full TB progression study", "source_anchor": portfolio_row["primary_strength"]},
        ],
    }

    selectivity_panel = {
        "summary": payload_summary("dpre1_selectivity_panel_ready", TARGET_ID, "selectivity_panel", 4, "Run host-enzyme and whole-cell orthogonal checks in the first packet so DprE1 rows do not jump straight from enzyme noise to TB claims."),
        "structured": {
            "target_id": TARGET_ID,
            "panel_label": validation_row["primary_companion_panel"],
            "panel_rationale": validation_row["companion_why"],
            "classification_rule": "promote only rows that retain DprE1 biochemical signal and survive host-enzyme sanity plus whole-cell orthogonal replay",
            "outbound_rule": validation_row["outbound_rule"],
        },
        "rows": [
            {"step_rank": "1", "step_label": "dpre1_primary", "plan": "measure DprE1 inhibition in the primary biochemical arm first", "source_anchor": portfolio_row["source_anchor"]},
            {"step_rank": "2", "step_label": "host_enzyme_sanity", "plan": "use a simple host-enzyme sanity panel before treating any biochemical row as actionable", "source_anchor": validation_row["companion_why"]},
            {"step_rank": "3", "step_label": "whole_cell_orthogonal_replay", "plan": "replay cleaned rows in a whole-cell TB orthogonal arm before external claims", "source_anchor": validation_row["primary_companion_panel"]},
            {"step_rank": "4", "step_label": "regimen_context", "plan": "contextualize cleaned rows against practical TB regimen comparators rather than treating them as regimen-ready leads", "source_anchor": portfolio_row["primary_strength"]},
        ],
    }

    assay_packet = {
        "summary": payload_summary("dpre1_assay_packet_ready", TARGET_ID, "assay_packet", 4, "Use this packet as the executable first-pass assay stack for the DprE1 TB rail."),
        "structured": {
            "target_id": TARGET_ID,
            "first_assay": "recombinant DprE1 biochemical inhibition assay followed by whole-cell orthogonal replay",
            "first_packet_goal": "determine whether the shortlist contains genuine DprE1-biased signal rather than generic TB whole-cell or broad-enzyme behavior",
            "buffer_program": "primary DprE1 biochemical arm plus host-enzyme sanity and whole-cell orthogonal replay",
            "companion_panel": validation_row["primary_companion_panel"],
            "offer_model": "serialized_wave2_after_final2",
        },
        "rows": [
            {"step_rank": "1", "step_label": "primary_biochemical_assay", "assay": "run a bounded recombinant DprE1 inhibition assay first", "source_anchor": portfolio_row["source_anchor"]},
            {"step_rank": "2", "step_label": "host_enzyme_sanity", "assay": "apply a simple host-enzyme sanity check before external interpretation", "source_anchor": validation_row["companion_why"]},
            {"step_rank": "3", "step_label": "whole_cell_replay", "assay": "retest survivors in a simple whole-cell TB orthogonal replay", "source_anchor": validation_row["primary_companion_panel"]},
            {"step_rank": "4", "step_label": "optional_regimen_followup", "assay": "open regimen-context follow-up only for rows that stay clean across biochemical and orthogonal replay", "source_anchor": portfolio_row["primary_strength"]},
        ],
    }

    go_no_go = {
        "summary": payload_summary("dpre1_go_no_go_card_ready", TARGET_ID, "go_no_go_card", 4, "Use this card to separate genuine DprE1 progression from generic TB background signal."),
        "structured": {
            "target_id": TARGET_ID,
            "primary_promote_rule": "DprE1 biochemical signal survives host-enzyme sanity and whole-cell orthogonal replay",
            "dual_bucket_rule": "signal appears real in both biochemical and whole-cell arms but still needs bounded chemistry follow-up",
            "reject_rule": "biochemical signal collapses under orthogonal or host-enzyme sanity replay",
            "headline": "DprE1 packet built to keep TB whole-cell context subordinate to direct target evidence.",
        },
        "rows": [
            {"decision_case": "promote_clean_dpre1_biochemical_bias", "decision_rule": "DprE1 signal remains while host-enzyme and whole-cell orthogonal replay stay favorable", "action": "promote to bounded Wave 2 follow-up"},
            {"decision_case": "hold_whole_cell_biochemical_split", "decision_rule": "signal is present but biochemical and whole-cell interpretations diverge", "action": "hold for bounded clarification"},
            {"decision_case": "reject_host_enzyme_or_whole_cell_carryover", "decision_rule": "signal carries into sanity panels without a clean DprE1-biased profile", "action": "reject as non-specific carryover"},
            {"decision_case": "reject_noisy_tb_context", "decision_rule": "signal only survives as broad TB-context noise rather than target-led evidence", "action": "reject as non-decision-grade"},
        ],
    }

    export_payload = {
        "summary": payload_summary("dpre1_tb_alliance_export_ready", TARGET_ID, "partner_export", 4, "Use this export only after the DprE1 compound lanes are filled and the first-pass packet is no longer content-blocked."),
        "structured": {
            "target_id": TARGET_ID,
            "partner_track_id": "TB_Alliance",
            "partner_track_label": "TB Alliance / academic TB rail",
            "email_subject": "DprE1 micro-validation packet with bounded biochemical and whole-cell replay",
            "proposal_title": "DprE1 biochemical-first micro-validation packet",
            "proposal_summary": "A Wave 2 packet that asks one narrow question: does the shortlist contain DprE1-biased signal that survives host-enzyme sanity and a simple whole-cell orthogonal replay?",
            "email_opening_angle": "Lead with DprE1 as a bounded biochemical-to-whole-cell triage problem, not as a fully de-risked TB program.",
        },
        "rows": [
            {"attachment_rank": "1", "artifact": DEFAULT_CONDITION_CARD_MD, "why": "fixes the DprE1 assay context before interpretation"},
            {"attachment_rank": "2", "artifact": DEFAULT_PANEL_MD, "why": "shows host-enzyme plus whole-cell cleanup is day-one work"},
            {"attachment_rank": "3", "artifact": DEFAULT_ASSAY_MD, "why": "gives a bounded executable DprE1 assay stack"},
            {"attachment_rank": "4", "artifact": DEFAULT_GONOGO_MD, "why": "keeps biochemical-versus-whole-cell outcomes explicit"},
        ],
    }

    suite_rows = [
        {"artifact_kind": "condition_card", "artifact_path": DEFAULT_CONDITION_CARD_MD, "status": condition_card["summary"]["status"]},
        {"artifact_kind": "selectivity_panel", "artifact_path": DEFAULT_PANEL_MD, "status": selectivity_panel["summary"]["status"]},
        {"artifact_kind": "assay_packet", "artifact_path": DEFAULT_ASSAY_MD, "status": assay_packet["summary"]["status"]},
        {"artifact_kind": "go_no_go_card", "artifact_path": DEFAULT_GONOGO_MD, "status": go_no_go["summary"]["status"]},
        {"artifact_kind": "partner_export", "artifact_path": DEFAULT_EXPORT_MD, "status": export_payload["summary"]["status"]},
    ]

    return {
        "summary": {
            "status": "dpre1_render_suite_ready",
            "target_id": TARGET_ID,
            "artifact_count": len(suite_rows),
            "partner_track_id": "TB_Alliance",
            "repurposing_filled_slot_count": len(rep_rows),
            "novelty_filled_slot_count": len(nov_rows),
            "content_ready": content_ready,
            "next_required_step": "Use the generated DprE1 packet set as the third live Wave 2 target overlay once Dengue resolves." if content_ready else "Use the generated DprE1 packet set as the third Wave 2 target overlay once Dengue resolves and compound fill is real.",
        },
        "artifacts": {
            "condition_card": condition_card,
            "selectivity_panel": selectivity_panel,
            "assay_packet": assay_packet,
            "go_no_go_card": go_no_go,
            "partner_export": export_payload,
        },
        "rows": suite_rows,
    }


def _write_suite(payload: dict[str, Any]) -> None:
    write_artifact(DEFAULT_SUITE_MD, "DprE1 Render Suite", {"summary": payload["summary"], "structured": {"target_id": payload["summary"]["target_id"], "partner_track_id": payload["summary"]["partner_track_id"]}, "rows": payload["rows"]})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the DprE1 target-specific Wave 2 overlay packet set.")
    parser.add_argument("--portfolio-json", default=DEFAULT_PORTFOLIO_JSON)
    parser.add_argument("--validation-json", default=DEFAULT_VALIDATION_JSON)
    parser.add_argument("--repurposing-fill-json", default=DEFAULT_REPURPOSING_FILL_JSON)
    parser.add_argument("--novelty-fill-json", default=DEFAULT_NOVELTY_FILL_JSON)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(load_json(args.portfolio_json), load_json(args.validation_json), load_json(args.repurposing_fill_json), load_json(args.novelty_fill_json))
    write_artifact(DEFAULT_CONDITION_CARD_MD, "DprE1 Condition Card", payload["artifacts"]["condition_card"])
    write_artifact(DEFAULT_PANEL_MD, "DprE1 Selectivity Panel", payload["artifacts"]["selectivity_panel"])
    write_artifact(DEFAULT_ASSAY_MD, "DprE1 Assay Packet", payload["artifacts"]["assay_packet"])
    write_artifact(DEFAULT_GONOGO_MD, "DprE1 Go / No-Go Card", payload["artifacts"]["go_no_go_card"])
    write_artifact(DEFAULT_EXPORT_MD, "DprE1 TB Alliance Export", payload["artifacts"]["partner_export"])
    _write_suite(payload)


if __name__ == "__main__":
    main()
