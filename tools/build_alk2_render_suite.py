#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab_target_render_utils import load_json, payload_summary, rows_by_target, rows_by_track, write_artifact

DEFAULT_BRIEF_INDEX_JSON = "runs/wetlab_wave1_target_brief_index_current.json"
DEFAULT_KINASE_PACKET_JSON = "runs/wetlab_wave1_kinase_first_contact_packets_current.json"
DEFAULT_KINASE_OUTREACH_JSON = "runs/wetlab_kinase_outreach_packet_current.json"
DEFAULT_EXPORT_BUNDLE_JSON = "runs/wetlab_partner_first_contact_export_bundle_current.json"
DEFAULT_SUITE_MD = "runs/alk2_render_suite_current.md"
DEFAULT_CONDITION_CARD_MD = "runs/alk2_condition_card_current.md"
DEFAULT_PANEL_MD = "runs/alk2_kinase_selectivity_panel_current.md"
DEFAULT_ASSAY_MD = "runs/alk2_assay_packet_current.md"
DEFAULT_GONOGO_MD = "runs/alk2_go_no_go_card_current.md"
DEFAULT_EXPORT_MD = "runs/alk2_m4k_export_current.md"


def build_payload(
    brief_index: dict[str, Any],
    kinase_packet: dict[str, Any],
    kinase_outreach: dict[str, Any],
    export_bundle: dict[str, Any],
) -> dict[str, Any]:
    brief = rows_by_target(brief_index)["ALK2"]
    packet = rows_by_target(kinase_packet)["ALK2"]
    outreach_row = rows_by_target(kinase_outreach)["ALK2"]
    export_row = rows_by_track(export_bundle)["M4K_open_science"]

    condition_card = {
        "summary": payload_summary(
            "alk2_condition_card_ready",
            "ALK2",
            "condition_card",
            4,
            "Use this card as the fixed ALK2 assay context before interpreting any kinase signal.",
        ),
        "structured": {
            "target_id": "ALK2",
            "partner_track": brief["partner_track"],
            "primary_assay_context": brief["first_assay"],
            "mutant_context": "mutant-or-wild-type comparison must be part of the first cheap pass",
            "comparison_controls": packet["repurposing_compounds"],
            "novelty_controls": packet["novelty_compounds"],
            "primary_risk": "ALK-family spillover and translational liability rather than clean ALK2 selectivity",
        },
        "rows": [
            {"condition_name": "biochemical_or_dsf_primary", "value": "low-friction ALK2 biochemical assay or DSF", "why": "keeps the first packet cheap and executable", "source_anchor": packet["source_anchor"]},
            {"condition_name": "mutant_wildtype_split", "value": "compare mutant and wild-type contexts in the first packet", "why": "rare-disease relevance belongs at stage 0", "source_anchor": outreach_row["why_this_rail"]},
            {"condition_name": "alk_family_panel", "value": packet["anti_target_panel"], "why": "prevents generic ALK-family carryover from looking interesting", "source_anchor": packet["source_anchor"]},
            {"condition_name": "orthogonal_followup", "value": "NanoBRET-style or orthogonal binding follow-up only after clean biochemical entry", "why": "keeps the first ask bounded", "source_anchor": outreach_row["what_to_send_first"]},
        ],
    }

    selectivity_panel = {
        "summary": payload_summary(
            "alk2_kinase_selectivity_panel_ready",
            "ALK2",
            "selectivity_panel",
            4,
            "Run this panel in the same packet so ALK-family spillover is visible before any outward claim.",
        ),
        "structured": {
            "target_id": "ALK2",
            "panel_label": brief["anti_target_panel"],
            "packet_role": "day-one kinase deselection panel",
            "promote_rule": "advance only ALK2 rows that survive mutant/wild-type framing and ALK-family cleanup",
            "reject_rule": "reject rows dominated by ALK-family spillover or translationally hopeless liability",
        },
        "rows": [
            {"step_rank": "1", "step_label": "mutant_wildtype_primary", "plan": "compare mutant and wild-type ALK2 contexts", "decision_rule": "prefer rows with interpretable mutant-aware behavior"},
            {"step_rank": "2", "step_label": "alk_family_panel", "plan": "run ALK1/ALK3/ALK5/ALK6 mini-panel", "decision_rule": "fail if the row behaves like generic family spillover"},
            {"step_rank": "3", "step_label": "translational_sanity", "plan": "carry a simple BBB or liability note in the first review", "decision_rule": "do not oversell chemically doomed rows"},
            {"step_rank": "4", "step_label": "clean_subset_only", "plan": "carry only clean mutant-aware survivors into deeper follow-up", "decision_rule": "no broader kinase campaign before the clean subset is isolated"},
        ],
    }

    assay_packet = {
        "summary": payload_summary(
            "alk2_assay_packet_ready",
            "ALK2",
            "assay_packet",
            4,
            "Use this assay packet as the executable first-pass stack for the M4K ALK2 rail.",
        ),
        "structured": {
            "target_id": "ALK2",
            "first_assay": packet["first_assay"],
            "first_packet_goal": packet["first_packet_goal"],
            "repurposing_compounds": packet["repurposing_compounds"],
            "novelty_compounds": packet["novelty_compounds"],
            "go_no_go_rule": "promote only reproducible ALK2 signal that survives mutant-aware and close-kinase cleanup",
        },
        "rows": [
            {"step_rank": "1", "step_label": "primary_alk2", "step": "run low-friction biochemical or DSF ALK2 assay on top-3 repurposing and top-3 novelty rows", "success_signal": "repeatable ALK2 engagement"},
            {"step_rank": "2", "step_label": "mutant_and_family_cleanup", "step": "run mutant/wild-type comparison plus ALK-family mini-panel", "success_signal": "signal remains ALK2-favored rather than family-generic"},
            {"step_rank": "3", "step_label": "orthogonal_confirmation", "step": "use orthogonal binding or DSF confirmation on clean survivors", "success_signal": "signal survives beyond one assay format"},
            {"step_rank": "4", "step_label": "bounded_followup", "step": "open broader cell or co-development follow-up only for clean survivors", "success_signal": "partner ask stays narrow and interpretable"},
        ],
    }

    go_no_go = {
        "summary": payload_summary(
            "alk2_go_no_go_card_ready",
            "ALK2",
            "go_no_go_card",
            4,
            "Use this card to separate clean ALK2 rows from ALK-family spillover or translational noise.",
        ),
        "structured": {
            "target_id": "ALK2",
            "promote_rule": "repeatable ALK2 signal plus mutant-aware and close-kinase separation",
            "hold_rule": "promising ALK2 signal that still needs orthogonal or liability clarification",
            "reject_rule": "ALK-family spillover or translationally weak liability profile",
            "headline": brief["headline"],
        },
        "rows": [
            {"decision_case": "promote_clean_alk2_favored", "decision_rule": "repeatable ALK2 signal survives mutant-aware and ALK-family cleanup", "action": "promote to rare-disease follow-up"},
            {"decision_case": "hold_partial_selectivity", "decision_rule": "ALK2 signal exists but selectivity or translational framing is incomplete", "action": "hold for bounded follow-up"},
            {"decision_case": "reject_family_spillover", "decision_rule": "ALK-family mini-panel collapses selectivity", "action": "reject as generic family-active kinase chemistry"},
            {"decision_case": "reject_translational_noise", "decision_rule": "signal is undermined by obvious translational liability", "action": "reject as non-decision-grade rare-disease chemistry"},
        ],
    }

    export_payload = {
        "summary": payload_summary(
            "alk2_m4k_export_ready",
            "ALK2",
            "partner_export",
            4,
            "Send this target-specific ALK2 export after attaching the condition card, kinase selectivity panel, assay packet, and go/no-go card.",
        ),
        "structured": {
            "target_id": "ALK2",
            "partner_track_id": export_row["track_id"],
            "partner_track_label": export_row["track_label"],
            "email_subject": "ALK2 micro-validation packet with mutant-aware kinase cleanup",
            "proposal_title": "M4K ALK2 micro-validation with mutant-aware and ALK-family separation",
            "proposal_summary": "A target-specific ALK2 export that keeps the first ask narrow: cheap biochemical or DSF signal, immediate mutant-aware and ALK-family cleanup, and bounded follow-up only for clean survivors.",
            "email_opening_angle": "Lead with ALK2 as a compact rare-disease kinase validation packet rather than a broad kinase campaign.",
        },
        "rows": [
            {"attachment_rank": "1", "artifact": DEFAULT_CONDITION_CARD_MD, "why": "locks the ALK2 assay context"},
            {"attachment_rank": "2", "artifact": DEFAULT_PANEL_MD, "why": "shows mutant-aware and ALK-family cleanup is day-one work"},
            {"attachment_rank": "3", "artifact": DEFAULT_ASSAY_MD, "why": "gives M4K a bounded executable stack"},
            {"attachment_rank": "4", "artifact": DEFAULT_GONOGO_MD, "why": "keeps clean versus noisy outcomes explicit"},
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
            "status": "alk2_render_suite_ready",
            "target_id": "ALK2",
            "artifact_count": len(suite_rows),
            "partner_track_id": export_row["track_id"],
            "next_required_step": "Use the generated ALK2 packet set as the third target overlay in the next3 serialized chain.",
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


def _write_suite(suite_md: str, payload: dict[str, Any]) -> None:
    write_artifact(
        suite_md,
        "ALK2 Render Suite",
        {"summary": payload["summary"], "structured": {"target_id": payload["summary"]["target_id"], "partner_track_id": payload["summary"]["partner_track_id"]}, "rows": payload["rows"]},
    )


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build the ALK2 target-specific wet-lab overlay packet set.")
    p.add_argument("--brief-index-json", default=DEFAULT_BRIEF_INDEX_JSON)
    p.add_argument("--kinase-packet-json", default=DEFAULT_KINASE_PACKET_JSON)
    p.add_argument("--kinase-outreach-json", default=DEFAULT_KINASE_OUTREACH_JSON)
    p.add_argument("--export-bundle-json", default=DEFAULT_EXPORT_BUNDLE_JSON)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        load_json(args.brief_index_json),
        load_json(args.kinase_packet_json),
        load_json(args.kinase_outreach_json),
        load_json(args.export_bundle_json),
    )
    write_artifact(DEFAULT_CONDITION_CARD_MD, "ALK2 Condition Card", payload["artifacts"]["condition_card"])
    write_artifact(DEFAULT_PANEL_MD, "ALK2 Kinase Selectivity Panel", payload["artifacts"]["selectivity_panel"])
    write_artifact(DEFAULT_ASSAY_MD, "ALK2 Assay Packet", payload["artifacts"]["assay_packet"])
    write_artifact(DEFAULT_GONOGO_MD, "ALK2 Go / No-Go Card", payload["artifacts"]["go_no_go_card"])
    write_artifact(DEFAULT_EXPORT_MD, "ALK2 M4K Export", payload["artifacts"]["partner_export"])
    _write_suite(DEFAULT_SUITE_MD, payload)


if __name__ == "__main__":
    main()
