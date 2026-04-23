#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab_target_render_utils import load_json, payload_summary, rows_by_target, write_artifact

DEFAULT_PORTFOLIO_JSON = "runs/wetlab_partner_target_portfolio_current.json"
DEFAULT_VALIDATION_JSON = "runs/wetlab_validation_companion_panels_current.json"
DEFAULT_REPURPOSING_FILL_JSON = "runs/wetlab_cathepsin_k_repurposing_fill_map_current.json"
DEFAULT_NOVELTY_FILL_JSON = "runs/wetlab_cathepsin_k_novelty_fill_map_current.json"
DEFAULT_SUITE_MD = "runs/cathepsin_k_render_suite_current.md"
DEFAULT_CONDITION_CARD_MD = "runs/cathepsin_k_condition_card_current.md"
DEFAULT_PANEL_MD = "runs/cathepsin_k_related_cathepsin_selectivity_panel_current.md"
DEFAULT_ASSAY_MD = "runs/cathepsin_k_assay_packet_current.md"
DEFAULT_GONOGO_MD = "runs/cathepsin_k_go_no_go_card_current.md"
DEFAULT_EXPORT_MD = "runs/cathepsin_k_acidic_protease_export_current.md"


def build_payload(
    portfolio_payload: dict[str, Any],
    validation_payload: dict[str, Any],
    repurposing_fill_payload: dict[str, Any] | None = None,
    novelty_fill_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    portfolio_row = rows_by_target(portfolio_payload)["Cathepsin K"]
    validation_row = rows_by_target(validation_payload)["Cathepsin K"]
    rep_rows = [
        dict(row)
        for row in ((repurposing_fill_payload or {}).get("rows", []) or [])
        if str(row.get("target_id", "")).strip() == "Cathepsin K"
    ]
    nov_rows = [
        dict(row)
        for row in ((novelty_fill_payload or {}).get("rows", []) or [])
        if str(row.get("target_id", "")).strip() == "Cathepsin K"
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
            "cathepsin_k_condition_card_ready",
            "Cathepsin K",
            "condition_card",
            4,
            "Use this card as the fixed acidic-protease context before interpreting any Cathepsin K potency or selectivity claim.",
        ),
        "structured": {
            "target_id": "Cathepsin K",
            "partner_track_id": "acidic_protease_wave2",
            "acidic_primary_arm": "sodium-acetate or MES-like acidic arm centered on pH 4.5 to 5.0",
            "neutral_contrast_arm": "HEPES-buffered neutral contrast arm at pH 7.4",
            "first_go_no_go": "promote only rows that keep acidic-arm Cathepsin K signal while degrading in neutral contrast and separating from related cathepsins",
            "repurposing_controls": rep_controls or "pending_wave2_compound_fill",
            "novelty_controls": nov_controls or "pending_wave2_compound_fill",
            "content_ready": content_ready,
            "source_anchor": portfolio_row["source_anchor"],
            "source_url": portfolio_row["source_url"],
        },
        "rows": [
            {
                "condition_name": "primary_acidic_arm",
                "value": "pH 4.5 to 5.0 protease arm",
                "why": "keeps Cathepsin K in the osteoclast-like acidic context where the enzyme is actually active",
                "source_anchor": portfolio_row["source_anchor"],
            },
            {
                "condition_name": "neutral_contrast_arm",
                "value": "pH 7.4 contrast arm",
                "why": "measures whether the signal is truly acidic-context dependent rather than generic protease stickiness",
                "source_anchor": validation_row["primary_companion_panel"],
            },
            {
                "condition_name": "related_cathepsin_panel",
                "value": validation_row["primary_companion_panel"],
                "why": "separates Cathepsin K-biased behavior from broader acidic-protease carryover",
                "source_anchor": validation_row["primary_companion_panel"],
            },
            {
                "condition_name": "first_packet_scope",
                "value": "cheap fluorogenic enzymology first, optional matrix-degradation or cell-facing follow-up later",
                "why": "keeps Wave 2 bounded and low-friction before any broader biology ask",
                "source_anchor": portfolio_row["primary_strength"],
            },
        ],
    }

    selectivity_panel = {
        "summary": payload_summary(
            "cathepsin_k_related_cathepsin_selectivity_panel_ready",
            "Cathepsin K",
            "selectivity_panel",
            4,
            "Run related cathepsin and off-pH specificity checks in the first packet so acidic-protease noise does not masquerade as Cathepsin K signal.",
        ),
        "structured": {
            "target_id": "Cathepsin K",
            "panel_label": validation_row["primary_companion_panel"],
            "panel_rationale": validation_row["companion_why"],
            "classification_rule": "promote only rows that hold acidic Cathepsin K signal, separate from Cathepsin B/L/S, and collapse in neutral contrast",
            "outbound_rule": validation_row["outbound_rule"],
        },
        "rows": [
            {
                "step_rank": "1",
                "step_label": "cathepsin_k_primary",
                "plan": "measure Cathepsin K inhibition in the acidic primary arm first",
                "source_anchor": portfolio_row["source_anchor"],
            },
            {
                "step_rank": "2",
                "step_label": "related_cathepsin_panel",
                "plan": "run Cathepsin B/L/S or closest available related-cathepsin counterscreens on the same shortlist",
                "source_anchor": validation_row["primary_companion_panel"],
            },
            {
                "step_rank": "3",
                "step_label": "neutral_context_dropoff",
                "plan": "confirm that the apparent signal weakens under neutral pH rather than persisting as a generic protease effect",
                "source_anchor": validation_row["primary_companion_panel"],
            },
            {
                "step_rank": "4",
                "step_label": "report_clean_subset_only",
                "plan": "only carry forward rows that survive both the related-cathepsin and neutral-context filters",
                "source_anchor": validation_row["outbound_rule"],
            },
        ],
    }

    assay_packet = {
        "summary": payload_summary(
            "cathepsin_k_assay_packet_ready",
            "Cathepsin K",
            "assay_packet",
            4,
            "Use this packet as the executable first-pass assay stack for the Cathepsin K acidic-protease lane.",
        ),
        "structured": {
            "target_id": "Cathepsin K",
            "first_assay": "acidic fluorogenic Cathepsin K assay with same-packet related-cathepsin and neutral-pH checks",
            "first_packet_goal": "determine whether the shortlist contains acidic-context Cathepsin K-biased rows rather than generic cathepsin-active chemistry",
            "buffer_program": "acidic primary arm plus neutral contrast arm",
            "companion_panel": validation_row["primary_companion_panel"],
            "offer_model": "serialized_wave2_after_final2",
        },
        "rows": [
            {
                "step_rank": "1",
                "step_label": "acidic_primary_assay",
                "assay": "run fluorogenic Cathepsin K biochemistry in the acidic primary arm",
                "source_anchor": portfolio_row["source_anchor"],
            },
            {
                "step_rank": "2",
                "step_label": "related_cathepsin_counterscreen",
                "assay": "run related cathepsin counterscreens on the same shortlist before any partner-facing interpretation",
                "source_anchor": validation_row["primary_companion_panel"],
            },
            {
                "step_rank": "3",
                "step_label": "neutral_contrast",
                "assay": "replay survivors under neutral pH to confirm acidic-context preference",
                "source_anchor": validation_row["companion_why"],
            },
            {
                "step_rank": "4",
                "step_label": "optional_matrix_followup",
                "assay": "open matrix-degradation or osteoclast-facing follow-up only for clean acidic-context survivors",
                "source_anchor": portfolio_row["primary_strength"],
            },
        ],
    }

    go_no_go = {
        "summary": payload_summary(
            "cathepsin_k_go_no_go_card_ready",
            "Cathepsin K",
            "go_no_go_card",
            4,
            "Use this card to separate Cathepsin K-biased acidic rows from generic related-cathepsin or neutral-context noise.",
        ),
        "structured": {
            "target_id": "Cathepsin K",
            "primary_promote_rule": "acidic-arm Cathepsin K signal plus related-cathepsin separation and visible neutral-context drop-off",
            "dual_bucket_rule": "acidic protease signal persists across the related-cathepsin mini-panel but still carries bounded mechanistic value",
            "reject_rule": "neutral-context persistence or broad related-cathepsin carryover",
            "headline": "Acidic-context Cathepsin K packet built to distinguish true acidic-protease signal from broader cathepsin carryover.",
        },
        "rows": [
            {
                "decision_case": "promote_clean_cathepsin_k_acidic_bias",
                "decision_rule": "acidic Cathepsin K signal survives while related cathepsin activity and neutral-context signal remain separated",
                "action": "promote to bounded Wave 2 follow-up",
            },
            {
                "decision_case": "hold_acidic_family_dual_signal",
                "decision_rule": "acidic protease signal is real but not yet cleanly separated from the related cathepsin panel",
                "action": "hold for bounded acidic-protease clarification",
            },
            {
                "decision_case": "reject_generic_cathepsin_behavior",
                "decision_rule": "signal follows the related cathepsin panel broadly rather than remaining Cathepsin K-favored",
                "action": "reject as generic acidic-protease carryover",
            },
            {
                "decision_case": "reject_neutral_context_persistence",
                "decision_rule": "signal remains comparable at neutral pH and therefore does not behave like a condition-aware acidic-protease win",
                "action": "reject as off-context or sticky behavior",
            },
        ],
    }

    export_payload = {
        "summary": payload_summary(
            "cathepsin_k_acidic_protease_export_ready",
            "Cathepsin K",
            "partner_export",
            4,
            "Use this export only after the Cathepsin K compound lanes are filled and the acidic-protease packet is no longer content-blocked.",
        ),
        "structured": {
            "target_id": "Cathepsin K",
            "partner_track_id": "acidic_protease_wave2",
            "partner_track_label": "acidic protease condition-aware rail",
            "email_subject": "Cathepsin K acidic-context micro-validation packet with related-cathepsin cleanup",
            "proposal_title": "Cathepsin K acidic-protease micro-validation packet",
            "proposal_summary": "A Wave 2 packet that asks one narrow question: does the shortlist contain acidic-context Cathepsin K-biased chemistry once related cathepsin and neutral-pH filters are applied immediately?",
            "email_opening_angle": "Lead with Cathepsin K as a condition-aware acidic-protease demo, not as a broad bone-disease claim.",
        },
        "rows": [
            {"attachment_rank": "1", "artifact": DEFAULT_CONDITION_CARD_MD, "why": "fixes the acidic assay context before interpretation"},
            {"attachment_rank": "2", "artifact": DEFAULT_PANEL_MD, "why": "shows related cathepsin cleanup is day-one work"},
            {"attachment_rank": "3", "artifact": DEFAULT_ASSAY_MD, "why": "gives a bounded executable acidic-protease assay stack"},
            {"attachment_rank": "4", "artifact": DEFAULT_GONOGO_MD, "why": "keeps Cathepsin K-biased versus generic acidic-protease outcomes explicit"},
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
            "status": "cathepsin_k_render_suite_ready",
            "target_id": "Cathepsin K",
            "artifact_count": len(suite_rows),
            "partner_track_id": "acidic_protease_wave2",
            "repurposing_filled_slot_count": len(rep_rows),
            "novelty_filled_slot_count": len(nov_rows),
            "content_ready": content_ready,
            "next_required_step": (
                "Use the generated Cathepsin K packet set as the first live Wave 2 target overlay once final2 opens."
                if content_ready
                else "Use the generated Cathepsin K packet set as the first Wave 2 target overlay once final2 opens and compound fill is real."
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
        "Cathepsin K Render Suite",
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
    parser = argparse.ArgumentParser(description="Build the Cathepsin K target-specific Wave 2 overlay packet set.")
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
    write_artifact(DEFAULT_CONDITION_CARD_MD, "Cathepsin K Condition Card", payload["artifacts"]["condition_card"])
    write_artifact(DEFAULT_PANEL_MD, "Cathepsin K Related Cathepsin Selectivity Panel", payload["artifacts"]["selectivity_panel"])
    write_artifact(DEFAULT_ASSAY_MD, "Cathepsin K Assay Packet", payload["artifacts"]["assay_packet"])
    write_artifact(DEFAULT_GONOGO_MD, "Cathepsin K Go / No-Go Card", payload["artifacts"]["go_no_go_card"])
    write_artifact(DEFAULT_EXPORT_MD, "Cathepsin K Acidic Protease Export", payload["artifacts"]["partner_export"])
    _write_suite(payload)


if __name__ == "__main__":
    main()
