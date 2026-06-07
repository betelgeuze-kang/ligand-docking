#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab_target_render_utils import load_json, payload_summary, rows_by_target, rows_by_track, write_artifact

DEFAULT_BRIEF_INDEX_JSON = "runs/wetlab_wave1_target_brief_index_current.json"
DEFAULT_KINASE_PACKET_JSON = "runs/wetlab_wave1_kinase_first_contact_packets_current.json"
DEFAULT_KINASE_OUTREACH_JSON = "runs/wetlab_kinase_outreach_packet_current.json"
DEFAULT_EXPORT_BUNDLE_JSON = "runs/wetlab_partner_first_contact_export_bundle_current.json"
DEFAULT_SUITE_MD = "runs/stk17b_render_suite_current.md"
DEFAULT_CONDITION_CARD_MD = "runs/stk17b_condition_card_current.md"
DEFAULT_PANEL_MD = "runs/stk17b_kinase_selectivity_panel_current.md"
DEFAULT_ASSAY_MD = "runs/stk17b_assay_packet_current.md"
DEFAULT_GONOGO_MD = "runs/stk17b_go_no_go_card_current.md"
DEFAULT_EXPORT_MD = "runs/stk17b_sgc_export_current.md"
TARGET_ID = "STK17B (DRAK2)"
TRACK_ID = "SGC_dark_kinase"


def build_payload(
    brief_index: dict[str, Any],
    kinase_packet: dict[str, Any],
    kinase_outreach: dict[str, Any],
    export_bundle: dict[str, Any],
) -> dict[str, Any]:
    brief = rows_by_target(brief_index)[TARGET_ID]
    packet = rows_by_target(kinase_packet)[TARGET_ID]
    outreach_row = rows_by_target(kinase_outreach)[TARGET_ID]
    export_row = rows_by_track(export_bundle)[TRACK_ID]

    condition_card = {
        "summary": payload_summary(
            "stk17b_condition_card_ready",
            TARGET_ID,
            "condition_card",
            4,
            "Use this card as the fixed STK17B assay context before interpreting any dark-kinase signal.",
        ),
        "structured": {
            "target_id": TARGET_ID,
            "partner_track": brief["partner_track"],
            "primary_assay_context": brief["first_assay"],
            "probe_frame": "published PKIS trio plus 11-series open-probe frame",
            "comparison_controls": packet["repurposing_compounds"],
            "novelty_controls": packet["novelty_compounds"],
            "primary_risk": "generic kinase noise that does not outperform the open benchmark frame",
        },
        "rows": [
            {"condition_name": "dsf_or_biochemical_entry", "value": brief["first_assay"], "why": "keeps the first dark-kinase ask cheap and executable", "source_anchor": packet["source_anchor"]},
            {"condition_name": "probe_positive_negative_frame", "value": brief["anti_target_panel"], "why": "the partner should evaluate signal inside a known open benchmark frame", "source_anchor": outreach_row["why_this_rail"]},
            {"condition_name": "open_set_benchmark", "value": packet["repurposing_compounds"], "why": "benchmark first, then ask whether dynamics add value beyond published ordering", "source_anchor": packet["source_anchor"]},
            {"condition_name": "structural_followup_only_after_clean_entry", "value": "reserve structural biology or cell-engagement follow-up for clean benchmark-beating survivors", "why": "keeps the first packet bounded", "source_anchor": outreach_row["what_to_send_first"]},
        ],
    }

    selectivity_panel = {
        "summary": payload_summary(
            "stk17b_kinase_selectivity_panel_ready",
            TARGET_ID,
            "selectivity_panel",
            4,
            "Run this panel in the same packet so probe-frame separation is visible before any partner-facing novelty claim.",
        ),
        "structured": {
            "target_id": TARGET_ID,
            "panel_label": brief["anti_target_panel"],
            "packet_role": "benchmark-first dark-kinase deselection panel",
            "promote_rule": "advance only rows that beat the open benchmark frame and survive neighborhood kinase cleanup",
            "reject_rule": "reject rows that collapse into generic hinge-binder or neighborhood-kinase behavior",
        },
        "rows": [
            {"step_rank": "1", "step_label": "pkis_benchmark", "plan": "run the published PKIS benchmark trio as the first comparison frame", "decision_rule": "fail if the packet does not separate the open benchmark meaningfully"},
            {"step_rank": "2", "step_label": "open_probe_controls", "plan": "anchor the first pass against the positive and negative open-probe controls", "decision_rule": "fail if novelty cannot be interpreted against the open probe frame"},
            {"step_rank": "3", "step_label": "neighborhood_kinase_panel", "plan": "run a compact neighborhood kinase panel", "decision_rule": "fail if signal looks like generic neighborhood kinase spillover"},
            {"step_rank": "4", "step_label": "clean_subset_only", "plan": "carry only clean benchmark-beating survivors into structural follow-up", "decision_rule": "no outward novelty claim before a clean subset exists"},
        ],
    }

    assay_packet = {
        "summary": payload_summary(
            "stk17b_assay_packet_ready",
            TARGET_ID,
            "assay_packet",
            4,
            "Use this assay packet as the executable first-pass stack for the SGC STK17B rail.",
        ),
        "structured": {
            "target_id": TARGET_ID,
            "first_assay": packet["first_assay"],
            "first_packet_goal": packet["first_packet_goal"],
            "benchmark_story": "ask whether dynamics add signal inside a published open-set benchmark rather than outside it",
            "parallel_export_freeze": export_row["status"],
        },
        "rows": [
            {"step_rank": "1", "step_label": "primary_entry", "artifact": DEFAULT_CONDITION_CARD_MD, "execution_note": packet["first_assay"]},
            {"step_rank": "2", "step_label": "benchmark_controls", "artifact": DEFAULT_PANEL_MD, "execution_note": packet["repurposing_compounds"]},
            {"step_rank": "3", "step_label": "novelty_frame", "artifact": DEFAULT_EXPORT_MD, "execution_note": packet["novelty_compounds"]},
            {"step_rank": "4", "step_label": "go_no_go", "artifact": DEFAULT_GONOGO_MD, "execution_note": packet["first_packet_goal"]},
        ],
    }

    go_no_go = {
        "summary": payload_summary(
            "stk17b_go_no_go_card_ready",
            TARGET_ID,
            "go_no_go_card",
            4,
            "Freeze these benchmark-first outcomes before moving STK17B into the final2 serialized queue.",
        ),
        "structured": {
            "target_id": TARGET_ID,
            "promote_case": "benchmark_beating_dark_kinase_signal",
            "hold_case": "interesting_but_not_yet_better_than_open_probe_frame",
            "reject_case": "generic_neighborhood_kinase_or_probe_like_noise",
            "review_rule": "do not treat benchmark-control chemistry as discovery output",
        },
        "rows": [
            {"decision_case": "promote_clean_stk17b_favored", "meaning": "signal survives the benchmark frame and neighborhood kinase cleanup", "action": "promote"},
            {"decision_case": "hold_probe_frame_ambiguous", "meaning": "signal is interesting but not clearly better than the open benchmark frame", "action": "hold"},
            {"decision_case": "reject_neighborhood_kinase_like", "meaning": "signal collapses into generic kinase or control-like behavior", "action": "reject"},
            {"decision_case": "explicit_hold", "meaning": "manual review requested before successor release", "action": "hold"},
        ],
    }

    export_payload = {
        "summary": payload_summary(
            "stk17b_sgc_export_ready",
            TARGET_ID,
            "partner_export",
            4,
            "Use this export only after the final2 first slot is genuinely ready for a benchmark-first STK17B pass.",
        ),
        "structured": {
            "target_id": TARGET_ID,
            "partner_track_id": TRACK_ID,
            "track_label": export_row["track_label"],
            "email_subject": export_row["email_subject"],
            "proposal_title": export_row["proposal_title"],
            "status": export_row["status"],
        },
        "rows": [
            {"export_item": "track_label", "value": export_row["track_label"], "role": "partner_destination"},
            {"export_item": "email_subject", "value": export_row["email_subject"], "role": "first_subject_line"},
            {"export_item": "email_body", "value": export_row["email_body"], "role": "first_contact_body"},
            {"export_item": "attachment_artifacts", "value": export_row["attachment_artifacts"], "role": "send_with_render_suite"},
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
            "status": "stk17b_render_suite_ready",
            "target_id": TARGET_ID,
            "artifact_count": len(suite_rows),
            "partner_track_id": TRACK_ID,
            "next_required_step": "Use the generated STK17B packet set as the first target overlay in the final2 serialized chain once next3 resolves.",
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
        "STK17B Render Suite",
        {"summary": payload["summary"], "structured": {"target_id": payload["summary"]["target_id"], "partner_track_id": payload["summary"]["partner_track_id"]}, "rows": payload["rows"]},
    )


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build the STK17B target-specific wet-lab overlay packet set.")
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
    write_artifact(DEFAULT_CONDITION_CARD_MD, "STK17B Condition Card", payload["artifacts"]["condition_card"])
    write_artifact(DEFAULT_PANEL_MD, "STK17B Kinase Selectivity Panel", payload["artifacts"]["selectivity_panel"])
    write_artifact(DEFAULT_ASSAY_MD, "STK17B Assay Packet", payload["artifacts"]["assay_packet"])
    write_artifact(DEFAULT_GONOGO_MD, "STK17B Go / No-Go Card", payload["artifacts"]["go_no_go_card"])
    write_artifact(DEFAULT_EXPORT_MD, "STK17B SGC Export", payload["artifacts"]["partner_export"])
    _write_suite(DEFAULT_SUITE_MD, payload)


if __name__ == "__main__":
    main()
