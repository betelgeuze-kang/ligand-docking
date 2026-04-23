#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab_target_render_utils import load_json, payload_summary, rows_by_target, write_artifact

DEFAULT_PORTFOLIO_JSON = "runs/wetlab_partner_target_portfolio_current.json"
DEFAULT_VALIDATION_JSON = "runs/wetlab_validation_companion_panels_current.json"
DEFAULT_REPURPOSING_FILL_JSON = "runs/wetlab_tcruzi_krs1_repurposing_fill_map_current.json"
DEFAULT_NOVELTY_FILL_JSON = "runs/wetlab_tcruzi_krs1_novelty_fill_map_current.json"
DEFAULT_SUITE_MD = "runs/tcruzi_krs1_render_suite_current.md"
DEFAULT_CONDITION_CARD_MD = "runs/tcruzi_krs1_condition_card_current.md"
DEFAULT_PANEL_MD = "runs/tcruzi_krs1_host_aars_selectivity_panel_current.md"
DEFAULT_ASSAY_MD = "runs/tcruzi_krs1_assay_packet_current.md"
DEFAULT_GONOGO_MD = "runs/tcruzi_krs1_go_no_go_card_current.md"
DEFAULT_EXPORT_MD = "runs/tcruzi_krs1_dndi_backup_export_current.md"
TARGET_ID = "T. cruzi KRS1"


def build_payload(portfolio_payload: dict[str, Any], validation_payload: dict[str, Any], repurposing_fill_payload: dict[str, Any] | None = None, novelty_fill_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    portfolio_row = rows_by_target(portfolio_payload)[TARGET_ID]
    validation_row = rows_by_target(validation_payload)[TARGET_ID]
    rep_rows = [dict(row) for row in ((repurposing_fill_payload or {}).get("rows", []) or []) if str(row.get("target_id", "")).strip() == TARGET_ID]
    nov_rows = [dict(row) for row in ((novelty_fill_payload or {}).get("rows", []) or []) if str(row.get("target_id", "")).strip() == TARGET_ID]
    rep_controls = "; ".join(str(row.get("compound_name", "")).strip() for row in rep_rows if str(row.get("compound_name", "")).strip())
    nov_controls = "; ".join(str(row.get("novelty_compound_name", "")).strip() for row in nov_rows if str(row.get("novelty_compound_name", "")).strip())
    content_ready = len(rep_rows) >= 3 and len(nov_rows) >= 3

    condition_card = {
        "summary": payload_summary("tcruzi_krs1_condition_card_ready", TARGET_ID, "condition_card", 4, "Use this card as the fixed TcKRS1 assay context before interpreting any parasite aaRS signal."),
        "structured": {
            "target_id": TARGET_ID,
            "partner_track_id": "DNDi_Chagas_backup",
            "primary_biochemical_arm": "recombinant T. cruzi KRS1 enzymatic inhibition arm with simple target-engagement framing",
            "whole_parasite_arm": "bounded parasite replay only after host aaRS separation survives",
            "host_aars_sanity": validation_row["primary_companion_panel"],
            "first_go_no_go": "promote only rows that keep TcKRS1 biochemical signal while surviving host aaRS separation and bounded parasite replay",
            "repurposing_controls": rep_controls or "pending_wave2_compound_fill",
            "novelty_controls": nov_controls or "pending_wave2_compound_fill",
            "content_ready": content_ready,
            "source_anchor": portfolio_row["source_anchor"],
            "source_url": portfolio_row["source_url"],
        },
        "rows": [
            {"condition_name": "primary_tckrs1_biochemical_arm", "value": "recombinant T. cruzi KRS1 enzymatic inhibition assay", "why": "keeps the packet target-centered before more expensive parasite-context work", "source_anchor": portfolio_row["source_anchor"]},
            {"condition_name": "host_aars_selectivity", "value": validation_row["primary_companion_panel"], "why": "aaRS programs fail fast on host-target separation", "source_anchor": validation_row["companion_why"]},
            {"condition_name": "bounded_parasite_replay", "value": "clean subset only", "why": "prevents whole-parasite carryover from outrunning KRS1 evidence", "source_anchor": portfolio_row["primary_strength"]},
            {"condition_name": "first_packet_scope", "value": "biochemical-first KRS1 packet before broader Chagas interpretation", "why": "keeps the first KRS1 ask tractable for a backup DNDi rail", "source_anchor": portfolio_row["main_risk"]},
        ],
    }

    selectivity_panel = {
        "summary": payload_summary("tcruzi_krs1_host_aars_selectivity_panel_ready", TARGET_ID, "selectivity_panel", 4, "Run this host-aaRS panel in the first packet so parasite and host synthetase signal do not get mixed."),
        "structured": {
            "target_id": TARGET_ID,
            "panel_label": validation_row["primary_companion_panel"],
            "panel_rationale": validation_row["companion_why"],
            "classification_rule": "promote only rows that retain TcKRS1 biochemical signal and survive host aaRS separation",
            "outbound_rule": validation_row["outbound_rule"],
        },
        "rows": [
            {"step_rank": "1", "step_label": "tckrs1_primary", "plan": "measure TcKRS1 inhibition in the primary biochemical arm first", "source_anchor": portfolio_row["source_anchor"]},
            {"step_rank": "2", "step_label": "host_aars_sanity", "plan": "use a host aaRS sanity panel before treating any biochemical row as actionable", "source_anchor": validation_row["companion_why"]},
            {"step_rank": "3", "step_label": "bounded_parasite_replay", "plan": "replay only the clean subset in a simple parasite-context orthogonal arm", "source_anchor": portfolio_row["primary_strength"]},
            {"step_rank": "4", "step_label": "chagas_context", "plan": "contextualize clean rows against practical Chagas comparators rather than treating them as regimen-ready leads", "source_anchor": portfolio_row["main_risk"]},
        ],
    }

    assay_packet = {
        "summary": payload_summary("tcruzi_krs1_assay_packet_ready", TARGET_ID, "assay_packet", 4, "Use this packet as the executable first-pass assay stack for the T. cruzi KRS1 DNDi backup rail."),
        "structured": {
            "target_id": TARGET_ID,
            "first_assay": "recombinant TcKRS1 biochemical inhibition assay followed by bounded parasite replay",
            "first_packet_goal": "determine whether the shortlist contains genuine TcKRS1-biased signal rather than generic Chagas whole-parasite behavior",
            "buffer_program": "primary TcKRS1 biochemical arm plus host aaRS sanity and bounded parasite replay",
            "companion_panel": validation_row["primary_companion_panel"],
            "offer_model": "serialized_wave2_after_final2",
        },
        "rows": [
            {"step_rank": "1", "step_label": "primary_biochemical_assay", "assay": "run a bounded recombinant TcKRS1 inhibition assay first", "source_anchor": portfolio_row["source_anchor"]},
            {"step_rank": "2", "step_label": "host_aars_sanity", "assay": "apply a host aaRS sanity check before external interpretation", "source_anchor": validation_row["companion_why"]},
            {"step_rank": "3", "step_label": "bounded_parasite_replay", "assay": "retest survivors in a simple parasite-context orthogonal replay", "source_anchor": portfolio_row["primary_strength"]},
            {"step_rank": "4", "step_label": "optional_followup", "assay": "open broader Chagas follow-up only for rows that stay clean across biochemical and orthogonal replay", "source_anchor": portfolio_row["main_risk"]},
        ],
    }

    go_no_go = {
        "summary": payload_summary("tcruzi_krs1_go_no_go_card_ready", TARGET_ID, "go_no_go_card", 4, "Use this card to separate genuine TcKRS1 progression from generic parasite-context background signal."),
        "structured": {
            "target_id": TARGET_ID,
            "primary_promote_rule": "TcKRS1 biochemical signal survives host aaRS separation and bounded parasite replay",
            "dual_bucket_rule": "signal appears real in both biochemical and parasite replay but still needs bounded chemistry follow-up",
            "reject_rule": "biochemical signal collapses under host aaRS or parasite replay",
            "headline": "TcKRS1 packet built to keep Chagas context subordinate to direct KRS1 evidence.",
        },
        "rows": [
            {"decision_case": "promote_clean_tckrs1_biochemical_bias", "decision_rule": "TcKRS1 signal remains while host aaRS and parasite replay stay favorable", "action": "promote to bounded Wave 2 follow-up"},
            {"decision_case": "hold_parasite_biochemical_split", "decision_rule": "signal is present but biochemical and parasite-context interpretations diverge", "action": "hold for bounded clarification"},
            {"decision_case": "reject_host_aars_or_parasite_carryover", "decision_rule": "signal carries into host aaRS or parasite replay without a clean TcKRS1-biased profile", "action": "reject as non-specific carryover"},
            {"decision_case": "reject_noisy_chagas_context", "decision_rule": "signal only survives as broad parasite-context noise rather than target-led evidence", "action": "reject as non-decision-grade"},
        ],
    }

    export_payload = {
        "summary": payload_summary("tcruzi_krs1_dndi_backup_export_ready", TARGET_ID, "partner_export", 4, "Use this export only after the TcKRS1 compound lanes are filled and the first-pass packet is no longer content-blocked."),
        "structured": {
            "target_id": TARGET_ID,
            "partner_track_id": "DNDi_Chagas_backup",
            "partner_track_label": "DNDi Chagas backup rail",
            "email_subject": "T. cruzi KRS1 micro-validation packet with bounded host-aaRS separation",
            "proposal_title": "T. cruzi KRS1 biochemical-first micro-validation packet",
            "proposal_summary": "A Wave 2 packet that asks one narrow question: does the shortlist contain TcKRS1-biased signal that survives host aaRS separation and a bounded parasite replay?",
            "email_opening_angle": "Lead with TcKRS1 as a bounded biochemical-to-parasite triage problem, not as a fully de-risked Chagas program.",
        },
        "rows": [
            {"attachment_rank": "1", "artifact": DEFAULT_CONDITION_CARD_MD, "why": "fixes the TcKRS1 assay context before interpretation"},
            {"attachment_rank": "2", "artifact": DEFAULT_PANEL_MD, "why": "shows host aaRS cleanup is day-one work"},
            {"attachment_rank": "3", "artifact": DEFAULT_ASSAY_MD, "why": "gives a bounded executable TcKRS1 assay stack"},
            {"attachment_rank": "4", "artifact": DEFAULT_GONOGO_MD, "why": "keeps biochemical-versus-parasite outcomes explicit"},
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
            "status": "tcruzi_krs1_render_suite_ready",
            "target_id": TARGET_ID,
            "artifact_count": len(suite_rows),
            "partner_track_id": "DNDi_Chagas_backup",
            "repurposing_filled_slot_count": len(rep_rows),
            "novelty_filled_slot_count": len(nov_rows),
            "content_ready": content_ready,
            "next_required_step": "Use the generated TcKRS1 packet set as the fourth live Wave 2 target overlay once DprE1 resolves." if content_ready else "Use the generated TcKRS1 packet set as the fourth Wave 2 target overlay once DprE1 resolves and compound fill is real.",
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
    write_artifact(DEFAULT_SUITE_MD, "T. cruzi KRS1 Render Suite", {"summary": payload["summary"], "structured": {"target_id": payload["summary"]["target_id"], "partner_track_id": payload["summary"]["partner_track_id"]}, "rows": payload["rows"]})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the T. cruzi KRS1 target-specific Wave 2 overlay packet set.")
    parser.add_argument("--portfolio-json", default=DEFAULT_PORTFOLIO_JSON)
    parser.add_argument("--validation-json", default=DEFAULT_VALIDATION_JSON)
    parser.add_argument("--repurposing-fill-json", default=DEFAULT_REPURPOSING_FILL_JSON)
    parser.add_argument("--novelty-fill-json", default=DEFAULT_NOVELTY_FILL_JSON)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(load_json(args.portfolio_json), load_json(args.validation_json), load_json(args.repurposing_fill_json), load_json(args.novelty_fill_json))
    write_artifact(DEFAULT_CONDITION_CARD_MD, "T. cruzi KRS1 Condition Card", payload["artifacts"]["condition_card"])
    write_artifact(DEFAULT_PANEL_MD, "T. cruzi KRS1 Host aaRS Selectivity Panel", payload["artifacts"]["selectivity_panel"])
    write_artifact(DEFAULT_ASSAY_MD, "T. cruzi KRS1 Assay Packet", payload["artifacts"]["assay_packet"])
    write_artifact(DEFAULT_GONOGO_MD, "T. cruzi KRS1 Go / No-Go Card", payload["artifacts"]["go_no_go_card"])
    write_artifact(DEFAULT_EXPORT_MD, "T. cruzi KRS1 DNDi Backup Export", payload["artifacts"]["partner_export"])
    _write_suite(payload)


if __name__ == "__main__":
    main()
