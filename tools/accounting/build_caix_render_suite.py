#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab_target_render_utils import load_json, payload_summary, rows_by_target, rows_by_track, write_artifact

DEFAULT_BRIEF_INDEX_JSON = "runs/wetlab_wave1_target_brief_index_current.json"
DEFAULT_CAIX_BRIEF_JSON = "runs/ca_ix_one_page_brief_current.json"
DEFAULT_ONCOLOGY_PACKET_JSON = "runs/wetlab_oncology_first_contact_packet_current.json"
DEFAULT_EXPORT_BUNDLE_JSON = "runs/wetlab_partner_first_contact_export_bundle_current.json"
DEFAULT_SUITE_MD = "runs/caix_render_suite_current.md"
DEFAULT_CONDITION_CARD_MD = "runs/caix_condition_card_current.md"
DEFAULT_PANEL_MD = "runs/caix_ca2_ca12_selectivity_panel_current.md"
DEFAULT_ASSAY_MD = "runs/caix_acidic_buffer_assay_packet_current.md"
DEFAULT_GONOGO_MD = "runs/caix_condition_aware_go_no_go_card_current.md"
DEFAULT_EXPORT_MD = "runs/caix_oncology_export_current.md"


def build_payload(
    brief_index: dict[str, Any],
    caix_brief: dict[str, Any],
    oncology_packet: dict[str, Any],
    export_bundle: dict[str, Any],
) -> dict[str, Any]:
    brief = rows_by_target(brief_index)["CA IX"]
    structured = caix_brief["structured"]
    packet = oncology_packet["structured"]
    export_row = rows_by_track(export_bundle)["oncology_condition_aware"]

    assay_block = structured["first_assay_stack_under_acidic_tumor_like_buffer"]
    selectivity_block = structured["ca_ii_ca_xii_selectivity_counterscreen_plan"]

    condition_card = {
        "summary": payload_summary(
            "caix_condition_card_ready",
            "CA IX",
            "condition_card",
            4,
            "Use this condition card as the fixed assay context for the CA IX condition-aware packet before reading any potency or selectivity result.",
        ),
        "structured": {
            "target_id": "CA IX",
            "partner_track": brief["partner_track"],
            "acidic_primary_arm": assay_block["buffer_primary_arm"],
            "neutral_contrast_arm": assay_block["buffer_neutral_contrast_arm"],
            "first_go_no_go": assay_block["first_go_no_go"],
            "repurposing_controls": packet["repurposing_compounds"],
            "novelty_controls": packet["novelty_compounds"],
        },
        "rows": [
            {"condition_name": "primary_acidic_arm", "value": assay_block["buffer_primary_arm"], "why": "keeps the assay aligned with tumor-like extracellular acidity", "source_anchor": "Lee et al. 2018 / Yudowski et al. 2018"},
            {"condition_name": "neutral_contrast_arm", "value": assay_block["buffer_neutral_contrast_arm"], "why": "quantifies acidic-condition advantage instead of a single-context score", "source_anchor": "Yudowski et al. 2018"},
            {"condition_name": "companion_counterscreen", "value": "CA XII same-packet counterscreen", "why": "separates CA IX-biased from tumor-CA-dual compounds", "source_anchor": "Whittington et al. 2001"},
            {"condition_name": "housekeeping_deselection", "value": "CA II same-packet deselection", "why": "rejects generic carbonic-anhydrase behavior early", "source_anchor": "Abdoli et al. 2018"},
        ],
    }

    selectivity_panel = {
        "summary": payload_summary(
            "caix_selectivity_panel_ready",
            "CA IX",
            "selectivity_panel",
            len(selectivity_block["plan_steps"]),
            "Run CA XII and CA II in the same packet and keep IX/XII-dual rows separate from CA IX-biased rows.",
        ),
        "structured": {
            "target_id": "CA IX",
            "panel_label": selectivity_block["primary_panel"],
            "panel_rationale": selectivity_block["panel_rationale"],
            "classification_rule": selectivity_block["plan_steps"][3]["plan"],
            "outbound_rule": "do not call anything CA IX-biased before CA II separation is visible",
        },
        "rows": [
            {"step_rank": str(step["step_rank"]), "step_label": step["step_label"], "plan": step["plan"], "source_anchor": step["source_anchor"]}
            for step in selectivity_block["plan_steps"]
        ],
    }

    assay_packet = {
        "summary": payload_summary(
            "caix_acidic_buffer_assay_packet_ready",
            "CA IX",
            "assay_packet",
            len(assay_block["assay_steps"]),
            "Use the acidic arm first, then the neutral contrast and counterscreens, and only then open any optional cell follow-up.",
        ),
        "structured": {
            "target_id": "CA IX",
            "first_assay": packet["first_assay"],
            "first_packet_goal": packet["first_packet_goal"],
            "buffer_program": "acidic primary arm plus neutral contrast arm",
            "companion_panel": packet["companion_panel_label"],
            "offer_model": packet["offer_model"],
        },
        "rows": [
            {"step_rank": str(step["step_rank"]), "step_label": step["step_label"], "assay": step["assay"], "source_anchor": step["source_anchor"]}
            for step in assay_block["assay_steps"]
        ],
    }

    go_no_go = {
        "summary": payload_summary(
            "caix_condition_aware_go_no_go_card_ready",
            "CA IX",
            "go_no_go_card",
            4,
            "Use this card to classify CA IX-biased, IX/XII-dual, or reject outcomes after the acidic-arm packet is complete.",
        ),
        "structured": {
            "target_id": "CA IX",
            "primary_promote_rule": "acidic-arm CA IX activity plus visible CA II separation",
            "dual_bucket_rule": "CA IX and CA XII both active but CA II still separated",
            "reject_rule": "CA II collapse or no acidic-condition advantage",
            "headline": structured["headline"],
        },
        "rows": [
            {"decision_case": "promote_caix_biased", "decision_rule": "acidic-arm CA IX signal with CA II separation and acceptable CA XII interpretation", "action": "promote to condition-aware oncology follow-up"},
            {"decision_case": "tumor_ca_dual", "decision_rule": "CA IX and CA XII both active but CA II still separated", "action": "keep in tumor-CA-dual bucket, do not market as CA IX-biased"},
            {"decision_case": "generic_ca_reject", "decision_rule": "CA II counterscreen collapses selectivity", "action": "reject as generic carbonic-anhydrase behavior"},
            {"decision_case": "neutral_only_signal", "decision_rule": "signal appears only in neutral or without acidic advantage", "action": "do not treat as condition-aware win"},
        ],
    }

    export_payload = {
        "summary": payload_summary(
            "caix_oncology_export_ready",
            "CA IX",
            "partner_export",
            4,
            "Send this CA IX-specific export with the condition card, selectivity panel, assay packet, and go/no-go card attached.",
        ),
        "structured": {
            "target_id": "CA IX",
            "partner_track_id": export_row["track_id"],
            "partner_track_label": export_row["track_label"],
            "email_subject": export_row["email_subject"],
            "proposal_title": export_row["proposal_title"],
            "proposal_summary": export_row["proposal_summary"],
            "email_opening_angle": "Lead with acidic-buffer CA IX as a condition-aware packet rather than a generic carbonic-anhydrase screen.",
        },
        "rows": [
            {"attachment_rank": "1", "artifact": DEFAULT_CONDITION_CARD_MD, "why": "fixes the assay environment before ranking claims"},
            {"attachment_rank": "2", "artifact": DEFAULT_PANEL_MD, "why": "shows CA II / CA XII selectivity is not deferred"},
            {"attachment_rank": "3", "artifact": DEFAULT_ASSAY_MD, "why": "gives a bounded acidic-arm assay stack"},
            {"attachment_rank": "4", "artifact": DEFAULT_GONOGO_MD, "why": "keeps CA IX-biased versus dual-bucket decisions explicit"},
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
            "status": "caix_render_suite_ready",
            "target_id": "CA IX",
            "artifact_count": len(suite_rows),
            "partner_track_id": export_row["track_id"],
            "next_required_step": "Use the generated CA IX packet set as the second target overlay after Mpro and before T. cruzi PDE.",
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
        "CA IX Render Suite",
        {"summary": payload["summary"], "structured": {"target_id": payload["summary"]["target_id"], "partner_track_id": payload["summary"]["partner_track_id"]}, "rows": payload["rows"]},
    )


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build the CA IX target-specific wet-lab overlay packet set.")
    p.add_argument("--brief-index-json", default=DEFAULT_BRIEF_INDEX_JSON)
    p.add_argument("--caix-brief-json", default=DEFAULT_CAIX_BRIEF_JSON)
    p.add_argument("--oncology-packet-json", default=DEFAULT_ONCOLOGY_PACKET_JSON)
    p.add_argument("--export-bundle-json", default=DEFAULT_EXPORT_BUNDLE_JSON)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        load_json(args.brief_index_json),
        load_json(args.caix_brief_json),
        load_json(args.oncology_packet_json),
        load_json(args.export_bundle_json),
    )
    write_artifact(DEFAULT_CONDITION_CARD_MD, "CA IX Condition Card", payload["artifacts"]["condition_card"])
    write_artifact(DEFAULT_PANEL_MD, "CA IX CA II / CA XII Selectivity Panel", payload["artifacts"]["selectivity_panel"])
    write_artifact(DEFAULT_ASSAY_MD, "CA IX Acidic Buffer Assay Packet", payload["artifacts"]["assay_packet"])
    write_artifact(DEFAULT_GONOGO_MD, "CA IX Condition-Aware Go / No-Go Card", payload["artifacts"]["go_no_go_card"])
    write_artifact(DEFAULT_EXPORT_MD, "CA IX Oncology Export", payload["artifacts"]["partner_export"])
    _write_suite(DEFAULT_SUITE_MD, payload)


if __name__ == "__main__":
    main()
