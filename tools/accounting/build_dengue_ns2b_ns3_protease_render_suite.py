#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab_target_render_utils import load_json, payload_summary, rows_by_target, write_artifact

DEFAULT_PORTFOLIO_JSON = "runs/wetlab_partner_target_portfolio_current.json"
DEFAULT_VALIDATION_JSON = "runs/wetlab_validation_companion_panels_current.json"
DEFAULT_REPURPOSING_FILL_JSON = "runs/wetlab_dengue_ns2b_ns3_protease_repurposing_fill_map_current.json"
DEFAULT_NOVELTY_FILL_JSON = "runs/wetlab_dengue_ns2b_ns3_protease_novelty_fill_map_current.json"
DEFAULT_SUITE_MD = "runs/dengue_ns2b_ns3_protease_render_suite_current.md"
DEFAULT_CONDITION_CARD_MD = "runs/dengue_ns2b_ns3_protease_condition_card_current.md"
DEFAULT_PANEL_MD = "runs/dengue_ns2b_ns3_protease_flaviviral_selectivity_panel_current.md"
DEFAULT_ASSAY_MD = "runs/dengue_ns2b_ns3_protease_assay_packet_current.md"
DEFAULT_GONOGO_MD = "runs/dengue_ns2b_ns3_protease_go_no_go_card_current.md"
DEFAULT_EXPORT_MD = "runs/dengue_ns2b_ns3_protease_ipk_export_current.md"
TARGET_ID = "Dengue NS2B-NS3 protease"


def build_payload(
    portfolio_payload: dict[str, Any],
    validation_payload: dict[str, Any],
    repurposing_fill_payload: dict[str, Any] | None = None,
    novelty_fill_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    portfolio_row = rows_by_target(portfolio_payload)[TARGET_ID]
    validation_row = rows_by_target(validation_payload)[TARGET_ID]
    rep_rows = [
        dict(row)
        for row in ((repurposing_fill_payload or {}).get("rows", []) or [])
        if str(row.get("target_id", "")).strip() == TARGET_ID
    ]
    nov_rows = [
        dict(row)
        for row in ((novelty_fill_payload or {}).get("rows", []) or [])
        if str(row.get("target_id", "")).strip() == TARGET_ID
    ]
    rep_controls = "; ".join(
        str(row.get("compound_name", "")).strip()
        for row in rep_rows
        if str(row.get("compound_name", "")).strip()
    )
    nov_controls = "; ".join(
        str(row.get("novelty_compound_name", "")).strip()
        for row in nov_rows
        if str(row.get("novelty_compound_name", "")).strip()
    )
    content_ready = len(rep_rows) >= 3 and len(nov_rows) >= 3

    condition_card = {
        "summary": payload_summary(
            "dengue_ns2b_ns3_protease_condition_card_ready",
            TARGET_ID,
            "condition_card",
            4,
            "Use this card as the fixed dengue shallow-pocket protease context before interpreting any potency or broad-flaviviral claim.",
        ),
        "structured": {
            "target_id": TARGET_ID,
            "partner_track_id": "IPK_dengue",
            "primary_biochemical_arm": "fluorogenic or AlphaScreen NS2B-NS3 protease arm under neutral-to-mildly basic assay conditions",
            "orthogonal_flaviviral_arm": "dengue-versus-related-flavivirus or serotype-contrast NS2B-NS3 replay",
            "sticky_false_positive_filter": "shallow-pocket negative controls plus detergent or aggregation sanity replay",
            "first_go_no_go": "promote only rows that keep dengue NS2B-NS3 signal while surviving orthogonal flaviviral replay and shallow-pocket false-positive cleanup",
            "repurposing_controls": rep_controls or "pending_wave2_compound_fill",
            "novelty_controls": nov_controls or "pending_wave2_compound_fill",
            "content_ready": content_ready,
            "source_anchor": portfolio_row["source_anchor"],
            "source_url": portfolio_row["source_url"],
        },
        "rows": [
            {
                "condition_name": "primary_dengue_arm",
                "value": "dengue NS2B-NS3 biochemical primary arm",
                "why": "keeps the packet centered on the actual dengue shallow-pocket protease question rather than generic antiviral inhibition",
                "source_anchor": portfolio_row["source_anchor"],
            },
            {
                "condition_name": "flaviviral_orthogonal_arm",
                "value": validation_row["primary_companion_panel"],
                "why": "tests whether the shortlist is dengue-favored or just broadly sticky across related flaviviral NS2B-NS3 systems",
                "source_anchor": validation_row["primary_companion_panel"],
            },
            {
                "condition_name": "shallow_pocket_negative_controls",
                "value": "detergent-sensitive and shallow-pocket false-positive cleanup",
                "why": "flat water-exposed protease pockets are vulnerable to sticky chemistry that looks active in a single assay",
                "source_anchor": validation_row["companion_why"],
            },
            {
                "condition_name": "first_packet_scope",
                "value": "bounded biochemical protease packet first, optional cell-facing follow-up only for cleaned survivors",
                "why": "keeps Wave 2 low-friction before asking any external lab for deeper dengue biology",
                "source_anchor": portfolio_row["primary_strength"],
            },
        ],
    }

    selectivity_panel = {
        "summary": payload_summary(
            "dengue_ns2b_ns3_protease_flaviviral_selectivity_panel_ready",
            TARGET_ID,
            "selectivity_panel",
            4,
            "Run flaviviral orthogonal and shallow-pocket cleanup checks in the first packet so sticky interface chemistry does not masquerade as dengue signal.",
        ),
        "structured": {
            "target_id": TARGET_ID,
            "panel_label": validation_row["primary_companion_panel"],
            "panel_rationale": validation_row["companion_why"],
            "classification_rule": "promote only rows that retain dengue NS2B-NS3 signal, survive orthogonal flaviviral replay, and collapse in shallow-pocket false-positive cleanup",
            "outbound_rule": validation_row["outbound_rule"],
        },
        "rows": [
            {
                "step_rank": "1",
                "step_label": "dengue_primary",
                "plan": "measure dengue NS2B-NS3 inhibition in the primary biochemical arm first",
                "source_anchor": portfolio_row["source_anchor"],
            },
            {
                "step_rank": "2",
                "step_label": "flaviviral_orthogonal_panel",
                "plan": "replay survivors in a related flaviviral or serotype-contrast NS2B-NS3 arm before any partner-facing interpretation",
                "source_anchor": validation_row["primary_companion_panel"],
            },
            {
                "step_rank": "3",
                "step_label": "shallow_pocket_negative_controls",
                "plan": "use detergent-sensitive or sticky-chemistry sanity checks to strip out shallow-pocket false positives",
                "source_anchor": validation_row["companion_why"],
            },
            {
                "step_rank": "4",
                "step_label": "host_serine_protease_sanity",
                "plan": "keep a simple host serine-protease or generic protease sanity check in the packet if available so flaviviral signal is not just generic protease suppression",
                "source_anchor": validation_row["outbound_rule"],
            },
        ],
    }

    assay_packet = {
        "summary": payload_summary(
            "dengue_ns2b_ns3_protease_assay_packet_ready",
            TARGET_ID,
            "assay_packet",
            4,
            "Use this packet as the executable first-pass assay stack for the Dengue NS2B-NS3 shallow-pocket lane.",
        ),
        "structured": {
            "target_id": TARGET_ID,
            "first_assay": "fluorogenic or AlphaScreen NS2B-NS3 protease arm under neutral-to-mildly basic assay conditions",
            "first_packet_goal": "determine whether the shortlist contains dengue-favored shallow-pocket signal rather than sticky flaviviral interface chemistry",
            "buffer_program": "primary dengue biochemical arm plus orthogonal flaviviral replay and shallow-pocket negative controls",
            "companion_panel": validation_row["primary_companion_panel"],
            "offer_model": "serialized_wave2_after_final2",
        },
        "rows": [
            {
                "step_rank": "1",
                "step_label": "primary_biochemical_assay",
                "assay": "run a bounded dengue NS2B-NS3 biochemical assay first, using the published shallow-pocket screening frame as the reference context",
                "source_anchor": "AlphaScreen dengue NS2B/NS3 assay paper",
            },
            {
                "step_rank": "2",
                "step_label": "orthogonal_flaviviral_replay",
                "assay": "retest survivors in a related flaviviral or serotype-contrast NS2B-NS3 arm before advancing them",
                "source_anchor": validation_row["primary_companion_panel"],
            },
            {
                "step_rank": "3",
                "step_label": "shallow_pocket_false_positive_cleanup",
                "assay": "apply detergent-sensitive and sticky-chemistry cleanup so broad shallow-pocket noise does not look like a dengue hit",
                "source_anchor": validation_row["companion_why"],
            },
            {
                "step_rank": "4",
                "step_label": "optional_cell_followup",
                "assay": "open a cell-facing follow-up only for rows that stay dengue-favored after orthogonal replay and cleanup",
                "source_anchor": portfolio_row["primary_strength"],
            },
        ],
    }

    go_no_go = {
        "summary": payload_summary(
            "dengue_ns2b_ns3_protease_go_no_go_card_ready",
            TARGET_ID,
            "go_no_go_card",
            4,
            "Use this card to separate dengue-favored shallow-pocket signal from generic sticky flaviviral interface behavior.",
        ),
        "structured": {
            "target_id": TARGET_ID,
            "primary_promote_rule": "dengue NS2B-NS3 signal survives the orthogonal flaviviral replay and shallow-pocket cleanup",
            "dual_bucket_rule": "signal appears real across flaviviral NS2B-NS3 systems but remains bounded by selectivity uncertainty",
            "reject_rule": "sticky shallow-pocket behavior or loss of signal under orthogonal replay",
            "headline": "Dengue NS2B-NS3 packet built to separate shallow-pocket allosteric signal from broad sticky interface chemistry.",
        },
        "rows": [
            {
                "decision_case": "promote_clean_dengue_shallow_pocket_bias",
                "decision_rule": "dengue signal remains while orthogonal flaviviral and shallow-pocket cleanup stay favorable",
                "action": "promote to bounded Wave 2 follow-up",
            },
            {
                "decision_case": "hold_pan_flaviviral_interface_signal",
                "decision_rule": "signal is real but behaves as a broader flaviviral NS2B-NS3 interface effect rather than a dengue-favored row",
                "action": "hold for bounded orthogonal clarification",
            },
            {
                "decision_case": "reject_sticky_shallow_pocket_behavior",
                "decision_rule": "signal collapses under shallow-pocket cleanup or looks like detergent-sensitive sticky chemistry",
                "action": "reject as shallow-pocket false positive",
            },
            {
                "decision_case": "reject_counterpanel_or_host_carryover",
                "decision_rule": "signal carries over into orthogonal counterpanels without a clean dengue-favored profile",
                "action": "reject as non-specific protease or interface carryover",
            },
        ],
    }

    export_payload = {
        "summary": payload_summary(
            "dengue_ns2b_ns3_protease_ipk_export_ready",
            TARGET_ID,
            "partner_export",
            4,
            "Use this export only after the Dengue NS2B-NS3 compound lanes are filled and the shallow-pocket cleanup packet is no longer content-blocked.",
        ),
        "structured": {
            "target_id": TARGET_ID,
            "partner_track_id": "IPK_dengue",
            "partner_track_label": "IPK / dengue antiviral rail",
            "email_subject": "Dengue NS2B-NS3 shallow-pocket micro-validation packet with flaviviral cleanup",
            "proposal_title": "Dengue NS2B-NS3 protease micro-validation packet",
            "proposal_summary": "A Wave 2 packet that asks one narrow question: does the shortlist contain dengue-favored shallow-pocket NS2B-NS3 chemistry once orthogonal flaviviral replay and sticky-pocket cleanup are applied immediately?",
            "email_opening_angle": "Lead with Dengue NS2B-NS3 as a shallow-pocket triage problem that the packet already bounds with orthogonal flaviviral and false-positive cleanup, not as a broad antiviral claim.",
        },
        "rows": [
            {"attachment_rank": "1", "artifact": DEFAULT_CONDITION_CARD_MD, "why": "fixes the dengue shallow-pocket assay context before interpretation"},
            {"attachment_rank": "2", "artifact": DEFAULT_PANEL_MD, "why": "shows flaviviral orthogonal cleanup is day-one work"},
            {"attachment_rank": "3", "artifact": DEFAULT_ASSAY_MD, "why": "gives a bounded executable dengue protease assay stack"},
            {"attachment_rank": "4", "artifact": DEFAULT_GONOGO_MD, "why": "keeps dengue-favored versus generic interface outcomes explicit"},
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
            "status": "dengue_ns2b_ns3_protease_render_suite_ready",
            "target_id": TARGET_ID,
            "artifact_count": len(suite_rows),
            "partner_track_id": "IPK_dengue",
            "repurposing_filled_slot_count": len(rep_rows),
            "novelty_filled_slot_count": len(nov_rows),
            "content_ready": content_ready,
            "next_required_step": (
                "Use the generated Dengue NS2B-NS3 packet set as the second live Wave 2 target overlay once Cathepsin K resolves."
                if content_ready
                else "Use the generated Dengue NS2B-NS3 packet set as the second Wave 2 target overlay once Cathepsin K resolves and compound fill is real."
            ),
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
    write_artifact(
        DEFAULT_SUITE_MD,
        "Dengue NS2B-NS3 Protease Render Suite",
        {
            "summary": payload["summary"],
            "structured": {
                "target_id": payload["summary"]["target_id"],
                "partner_track_id": payload["summary"]["partner_track_id"],
            },
            "rows": payload["rows"],
        },
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the Dengue NS2B-NS3 protease target-specific Wave 2 overlay packet set.")
    parser.add_argument("--portfolio-json", default=DEFAULT_PORTFOLIO_JSON)
    parser.add_argument("--validation-json", default=DEFAULT_VALIDATION_JSON)
    parser.add_argument("--repurposing-fill-json", default=DEFAULT_REPURPOSING_FILL_JSON)
    parser.add_argument("--novelty-fill-json", default=DEFAULT_NOVELTY_FILL_JSON)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        load_json(args.portfolio_json),
        load_json(args.validation_json),
        load_json(args.repurposing_fill_json),
        load_json(args.novelty_fill_json),
    )
    write_artifact(DEFAULT_CONDITION_CARD_MD, "Dengue NS2B-NS3 Protease Condition Card", payload["artifacts"]["condition_card"])
    write_artifact(DEFAULT_PANEL_MD, "Dengue NS2B-NS3 Protease Flaviviral Selectivity Panel", payload["artifacts"]["selectivity_panel"])
    write_artifact(DEFAULT_ASSAY_MD, "Dengue NS2B-NS3 Protease Assay Packet", payload["artifacts"]["assay_packet"])
    write_artifact(DEFAULT_GONOGO_MD, "Dengue NS2B-NS3 Protease Go / No-Go Card", payload["artifacts"]["go_no_go_card"])
    write_artifact(DEFAULT_EXPORT_MD, "Dengue NS2B-NS3 Protease IPK Export", payload["artifacts"]["partner_export"])
    _write_suite(payload)


if __name__ == "__main__":
    main()
