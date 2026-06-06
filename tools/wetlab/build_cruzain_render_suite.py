#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab_target_render_utils import load_json, payload_summary, rows_by_target, rows_by_track, write_artifact

DEFAULT_BRIEF_INDEX_JSON = "runs/wetlab_wave1_target_brief_index_current.json"
DEFAULT_NEGLECTED_ROWS_JSON = "runs/wetlab_neglected_wave1_rows_current.json"
DEFAULT_NEGLECTED_PACKET_JSON = "runs/wetlab_neglected_first_contact_packets_current.json"
DEFAULT_EXPORT_BUNDLE_JSON = "runs/wetlab_partner_first_contact_export_bundle_current.json"
DEFAULT_SUITE_MD = "runs/cruzain_render_suite_current.md"
DEFAULT_CONDITION_CARD_MD = "runs/cruzain_condition_card_current.md"
DEFAULT_PANEL_MD = "runs/cruzain_host_protease_panel_current.md"
DEFAULT_ASSAY_MD = "runs/cruzain_assay_packet_current.md"
DEFAULT_GONOGO_MD = "runs/cruzain_go_no_go_card_current.md"
DEFAULT_EXPORT_MD = "runs/cruzain_dndi_ipk_export_current.md"


def build_payload(
    brief_index: dict[str, Any],
    neglected_rows: dict[str, Any],
    neglected_packet: dict[str, Any],
    export_bundle: dict[str, Any],
) -> dict[str, Any]:
    brief = rows_by_target(brief_index)["Cruzain"]
    row = rows_by_target(neglected_rows)["Cruzain"]
    packet = rows_by_target(neglected_packet)["Cruzain"]
    export_row = rows_by_track(export_bundle)["DNDi_IPK"]

    condition_card = {
        "summary": payload_summary(
            "cruzain_condition_card_ready",
            "Cruzain",
            "condition_card",
            4,
            "Use this card as the fixed Cruzain wet-lab context before interpreting any protease signal.",
        ),
        "structured": {
            "target_id": "Cruzain",
            "partner_track": brief["partner_track"],
            "primary_assay_context": brief["first_assay"],
            "solvent_context": "fluorogenic soluble protease assay with matched DMSO and same-day artifact checks",
            "comparison_controls": packet["repurposing_compounds"],
            "novelty_controls": packet["novelty_compounds"],
            "primary_risk": "reactive or sticky protease false positives rather than clean Cruzain selectivity",
        },
        "rows": [
            {"condition_name": "cruzain_primary_arm", "value": "fluorogenic Cruzain assay", "why": "keeps the first packet cheap and fast", "source_anchor": packet["source_anchor"]},
            {"condition_name": "host_protease_counterpanel", "value": packet["anti_target_panel"], "why": "separates pathogen-facing hits from host protease carryover", "source_anchor": packet["source_anchor"]},
            {"condition_name": "reactivity_filter", "value": "same-packet thiol-reactivity sanity check", "why": "cysteine-protease noise is the first failure mode to remove", "source_anchor": row["main_external_lab_objection"]},
            {"condition_name": "aggregation_filter", "value": "same-packet aggregation or detergent sanity row", "why": "prevents sticky protease artifacts from looking actionable", "source_anchor": row["objection_answer"]},
        ],
    }

    host_panel = {
        "summary": payload_summary(
            "cruzain_host_protease_panel_ready",
            "Cruzain",
            "host_protease_panel",
            4,
            "Run this panel in the same packet so reactive or host-protease-biased rows fail immediately.",
        ),
        "structured": {
            "target_id": "Cruzain",
            "panel_label": brief["anti_target_panel"],
            "packet_role": "day-one deselection panel",
            "promote_rule": "advance only Cruzain rows that survive host protease, reactivity, and aggregation sanity checks",
            "reject_rule": "reject rows that collapse under host protease or artifact filters",
        },
        "rows": [
            {"step_rank": "1", "step_label": "host_cysteine_primary", "plan": "run host cysteine protease mini-panel on the same shortlist", "decision_rule": "fail if host protease follows Cruzain signal"},
            {"step_rank": "2", "step_label": "thiol_reactivity", "plan": "measure simple thiol-reactivity liability", "decision_rule": "fail if signal can be explained by generic thiol reactivity"},
            {"step_rank": "3", "step_label": "aggregation_filter", "plan": "use aggregation sanity check or detergent rescue row", "decision_rule": "fail if signal behaves like sticky protease noise"},
            {"step_rank": "4", "step_label": "clean_subset_only", "plan": "carry only clean survivors into orthogonal confirmation", "decision_rule": "no partner-facing claim before the clean subset is isolated"},
        ],
    }

    assay_packet = {
        "summary": payload_summary(
            "cruzain_assay_packet_ready",
            "Cruzain",
            "assay_packet",
            4,
            "Use this assay packet as the executable first-pass stack for the DNDi/IPK Cruzain rail.",
        ),
        "structured": {
            "target_id": "Cruzain",
            "first_assay": packet["first_assay"],
            "first_packet_goal": packet["first_packet_goal"],
            "repurposing_compounds": packet["repurposing_compounds"],
            "novelty_compounds": packet["novelty_compounds"],
            "go_no_go_rule": "promote only reproducible Cruzain signal that stays clean on host-protease and artifact filters",
        },
        "rows": [
            {"step_rank": "1", "step_label": "primary_cruzain", "step": "run fluorogenic Cruzain assay on top-3 repurposing and top-3 novelty rows", "success_signal": "repeatable Cruzain inhibition"},
            {"step_rank": "2", "step_label": "host_and_artifact_panel", "step": "run host protease, thiol-reactivity, and aggregation sanity checks", "success_signal": "signal remains Cruzain-favored and non-reactive"},
            {"step_rank": "3", "step_label": "orthogonal_confirmation", "step": "confirm clean survivors by orthogonal biochemical format", "success_signal": "signal survives format change"},
            {"step_rank": "4", "step_label": "bounded_followup", "step": "open any extra pathogen-facing follow-up only for clean survivors", "success_signal": "keeps the partner ask small and decision-grade"},
        ],
    }

    go_no_go = {
        "summary": payload_summary(
            "cruzain_go_no_go_card_ready",
            "Cruzain",
            "go_no_go_card",
            4,
            "Use this card to separate clean Cruzain rows from host-like or reactive noise before any outward claim.",
        ),
        "structured": {
            "target_id": "Cruzain",
            "promote_rule": "repeatable Cruzain signal plus clean host-protease and artifact panel outcome",
            "hold_rule": "partial cleanliness that still needs orthogonal confirmation",
            "reject_rule": "host-like, reactive, or sticky protease behavior",
            "headline": brief["headline"],
        },
        "rows": [
            {"decision_case": "promote_clean_cruzain_favored", "decision_rule": "repeatable Cruzain signal survives host and artifact panels", "action": "promote to neglected-disease follow-up"},
            {"decision_case": "hold_partial_cleanliness", "decision_rule": "Cruzain signal exists but orthogonal or artifact cleanup is incomplete", "action": "hold for bounded follow-up"},
            {"decision_case": "reject_host_like", "decision_rule": "host cysteine protease panel tracks with the apparent Cruzain signal", "action": "reject as host-liability carryover"},
            {"decision_case": "reject_reactive_or_sticky", "decision_rule": "thiol-reactivity or aggregation explains the signal", "action": "reject as non-decision-grade protease chemistry"},
        ],
    }

    export_payload = {
        "summary": payload_summary(
            "cruzain_dndi_ipk_export_ready",
            "Cruzain",
            "partner_export",
            4,
            "Send this target-specific Cruzain export after attaching the condition card, host panel, assay packet, and go/no-go card.",
        ),
        "structured": {
            "target_id": "Cruzain",
            "partner_track_id": export_row["track_id"],
            "partner_track_label": export_row["track_label"],
            "email_subject": "Cruzain micro-validation packet with day-one host-protease and artifact cleanup",
            "proposal_title": "DNDi/IPK Cruzain micro-validation with built-in reactive-noise filtering",
            "proposal_summary": "A target-specific Cruzain export that keeps the first ask narrow: cheap protease signal, immediate host-protease cleanup, and explicit reactivity/aggregation filtering.",
            "email_opening_angle": "Lead with Cruzain as the low-friction Chagas protease rail that already includes false-positive filtering rather than asking the partner to debug it later.",
        },
        "rows": [
            {"attachment_rank": "1", "artifact": DEFAULT_CONDITION_CARD_MD, "why": "locks the protease assay context"},
            {"attachment_rank": "2", "artifact": DEFAULT_PANEL_MD, "why": "shows host-protease and artifact cleanup is day-one work"},
            {"attachment_rank": "3", "artifact": DEFAULT_ASSAY_MD, "why": "gives DNDi/IPK a bounded executable stack"},
            {"attachment_rank": "4", "artifact": DEFAULT_GONOGO_MD, "why": "keeps clean versus noisy outcomes explicit"},
        ],
    }

    suite_rows = [
        {"artifact_kind": "condition_card", "artifact_path": DEFAULT_CONDITION_CARD_MD, "status": condition_card["summary"]["status"]},
        {"artifact_kind": "host_protease_panel", "artifact_path": DEFAULT_PANEL_MD, "status": host_panel["summary"]["status"]},
        {"artifact_kind": "assay_packet", "artifact_path": DEFAULT_ASSAY_MD, "status": assay_packet["summary"]["status"]},
        {"artifact_kind": "go_no_go_card", "artifact_path": DEFAULT_GONOGO_MD, "status": go_no_go["summary"]["status"]},
        {"artifact_kind": "partner_export", "artifact_path": DEFAULT_EXPORT_MD, "status": export_payload["summary"]["status"]},
    ]
    return {
        "summary": {
            "status": "cruzain_render_suite_ready",
            "target_id": "Cruzain",
            "artifact_count": len(suite_rows),
            "partner_track_id": export_row["track_id"],
            "next_required_step": "Use the generated Cruzain packet set as the first target overlay in the next3 serialized chain once priority3 is resolved.",
        },
        "artifacts": {
            "condition_card": condition_card,
            "host_protease_panel": host_panel,
            "assay_packet": assay_packet,
            "go_no_go_card": go_no_go,
            "partner_export": export_payload,
        },
        "rows": suite_rows,
    }


def _write_suite(suite_md: str, payload: dict[str, Any]) -> None:
    write_artifact(
        suite_md,
        "Cruzain Render Suite",
        {"summary": payload["summary"], "structured": {"target_id": payload["summary"]["target_id"], "partner_track_id": payload["summary"]["partner_track_id"]}, "rows": payload["rows"]},
    )


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build the Cruzain target-specific wet-lab overlay packet set.")
    p.add_argument("--brief-index-json", default=DEFAULT_BRIEF_INDEX_JSON)
    p.add_argument("--neglected-rows-json", default=DEFAULT_NEGLECTED_ROWS_JSON)
    p.add_argument("--neglected-packet-json", default=DEFAULT_NEGLECTED_PACKET_JSON)
    p.add_argument("--export-bundle-json", default=DEFAULT_EXPORT_BUNDLE_JSON)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        load_json(args.brief_index_json),
        load_json(args.neglected_rows_json),
        load_json(args.neglected_packet_json),
        load_json(args.export_bundle_json),
    )
    write_artifact(DEFAULT_CONDITION_CARD_MD, "Cruzain Condition Card", payload["artifacts"]["condition_card"])
    write_artifact(DEFAULT_PANEL_MD, "Cruzain Host Protease Panel", payload["artifacts"]["host_protease_panel"])
    write_artifact(DEFAULT_ASSAY_MD, "Cruzain Assay Packet", payload["artifacts"]["assay_packet"])
    write_artifact(DEFAULT_GONOGO_MD, "Cruzain Go / No-Go Card", payload["artifacts"]["go_no_go_card"])
    write_artifact(DEFAULT_EXPORT_MD, "Cruzain DNDi / IPK Export", payload["artifacts"]["partner_export"])
    _write_suite(DEFAULT_SUITE_MD, payload)


if __name__ == "__main__":
    main()
