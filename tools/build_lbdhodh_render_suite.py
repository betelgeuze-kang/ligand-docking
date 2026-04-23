#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab_target_render_utils import load_json, maybe_load_json, payload_summary, rows_by_target, rows_by_track, write_artifact

DEFAULT_BRIEF_INDEX_JSON = "runs/wetlab_wave1_target_brief_index_current.json"
DEFAULT_NEGLECTED_ROWS_JSON = "runs/wetlab_neglected_wave1_rows_current.json"
DEFAULT_NEGLECTED_PACKET_JSON = "runs/wetlab_neglected_first_contact_packets_current.json"
DEFAULT_OUTREACH_JSON = "runs/wetlab_neglected_outreach_packet_current.json"
DEFAULT_EXPORT_BUNDLE_JSON = "runs/wetlab_partner_first_contact_export_bundle_current.json"
DEFAULT_REPURPOSING_FILL_JSON = "runs/wetlab_lbdhodh_repurposing_fill_map_current.json"
DEFAULT_NOVELTY_FILL_JSON = "runs/wetlab_lbdhodh_novelty_fill_map_current.json"
DEFAULT_SUITE_MD = "runs/lbdhodh_render_suite_current.md"
DEFAULT_CONDITION_CARD_MD = "runs/lbdhodh_condition_card_current.md"
DEFAULT_PANEL_MD = "runs/lbdhodh_host_dhodh_selectivity_panel_current.md"
DEFAULT_ASSAY_MD = "runs/lbdhodh_assay_packet_current.md"
DEFAULT_GONOGO_MD = "runs/lbdhodh_go_no_go_card_current.md"
DEFAULT_EXPORT_MD = "runs/lbdhodh_dndi_ipk_export_current.md"
TARGET_ID = "Leishmania braziliensis DHODH"
TRACK_ID = "DNDi_IPK"


def _filled_count(value: Any) -> int:
    text = str(value or "").strip()
    if not text:
        return 0
    return len([part for part in text.split(";") if part.strip()])


def build_payload(
    brief_index: dict[str, Any],
    neglected_rows: dict[str, Any],
    neglected_packet: dict[str, Any],
    outreach_payload: dict[str, Any],
    export_bundle: dict[str, Any],
    repurposing_fill_map: dict[str, Any] | None = None,
    novelty_fill_map: dict[str, Any] | None = None,
) -> dict[str, Any]:
    brief = rows_by_target(brief_index)[TARGET_ID]
    row = rows_by_target(neglected_rows)[TARGET_ID]
    packet = rows_by_target(neglected_packet)[TARGET_ID]
    outreach_row = rows_by_target(outreach_payload)[TARGET_ID]
    export_row = rows_by_track(export_bundle)[TRACK_ID]
    rep_rows = [
        dict(fill_row)
        for fill_row in ((repurposing_fill_map or {}).get("rows", []) or [])
        if str(fill_row.get("target_id", "")).strip() == TARGET_ID
    ]
    nov_rows = [
        dict(fill_row)
        for fill_row in ((novelty_fill_map or {}).get("rows", []) or [])
        if str(fill_row.get("target_id", "")).strip() == TARGET_ID
    ]
    rep_filled = len(rep_rows)
    nov_filled = len(nov_rows)
    content_ready = rep_filled >= 3 and nov_filled >= 3
    content_state = "filled" if content_ready else "slot_criteria_only"
    rep_fill_status = "repurposing_ready" if rep_filled >= 3 else "repurposing_pending"
    nov_fill_status = "novelty_ready" if nov_filled >= 3 else "novelty_pending"
    export_status = "lbdhodh_dndi_ipk_export_ready" if content_ready else "lbdhodh_dndi_ipk_export_pending_compound_fill"
    email_subject = "Leishmania DHODH micro-validation packet: host-DHODH separation from the first assay"
    proposal_title = "DNDi/IPK neglected-disease micro-validation: Leishmania braziliensis DHODH"
    email_body = (
        "Hello DNDi/IPK team,\n\n"
        "I’m reaching out with a compact neglected-disease micro-validation packet centered on "
        "Leishmania braziliensis DHODH. The first experiment is intentionally low-friction: a recombinant "
        "LbDHODH inhibition entry assay with host DHODH counterscreen built in from day one, so the packet "
        "stays focused on clean parasite-versus-host separation rather than a broad screening burden.\n\n"
        f"The current packet framing is: {outreach_row['first_packet_goal']} "
        f"The main concern we are explicitly addressing is: {outreach_row['main_external_objection']} "
        f"Our answer is: {outreach_row['objection_answer']}\n\n"
        "If this looks rail-fit for DNDi/IPK, I can send the one-page target brief, the host-DHODH "
        "selectivity plan, and the current compound-fill status in a single attachment set.\n\n"
        "Best,\n강지훈"
    )

    condition_card = {
        "summary": payload_summary(
            "lbdhodh_condition_card_ready",
            TARGET_ID,
            "condition_card",
            4,
            "Use this card as the fixed LbDHODH assay context before interpreting any neglected-enzyme signal.",
        ),
        "structured": {
            "target_id": TARGET_ID,
            "partner_track": brief["partner_track"],
            "primary_assay_context": brief["first_assay"],
            "host_counterframe": brief["anti_target_panel"],
            "repurposing_fill_status": rep_fill_status,
            "novelty_fill_status": nov_fill_status,
            "repurposing_controls": "; ".join(str(fill_row.get("compound_name", "")).strip() for fill_row in rep_rows if str(fill_row.get("compound_name", "")).strip()) or "pending_compound_fill",
            "novelty_controls": "; ".join(str(fill_row.get("novelty_compound_name", "")).strip() for fill_row in nov_rows if str(fill_row.get("novelty_compound_name", "")).strip()) or "pending_compound_fill",
            "content_ready": content_ready,
            "primary_risk": "host-enzyme separation is weak or repurposing lane remains too thin to justify immediate live execution",
        },
        "rows": [
            {"condition_name": "recombinant_dhodh_entry", "value": brief["first_assay"], "why": "keeps the first neglected-enzyme ask low-friction", "source_anchor": packet["source_anchor"]},
            {"condition_name": "host_dhodh_counterscreen", "value": brief["anti_target_panel"], "why": "host-enzyme separation belongs in the first packet", "source_anchor": outreach_row["why_now"]},
            {"condition_name": "repurposing_lane_state", "value": rep_fill_status, "why": "tie launch readiness to explicit repurposing rows rather than stale packet text", "source_anchor": row["main_external_lab_objection"]},
            {"condition_name": "novelty_lane_state", "value": nov_fill_status, "why": "keep launch readiness tied to explicit novelty rows rather than schema existence", "source_anchor": row["objection_answer"]},
        ],
    }

    host_panel = {
        "summary": payload_summary(
            "lbdhodh_host_dhodh_selectivity_panel_ready",
            TARGET_ID,
            "selectivity_panel",
            4,
            "Run this panel in the same packet so host-DHODH carryover fails before any partner-facing neglected-disease claim.",
        ),
        "structured": {
            "target_id": TARGET_ID,
            "panel_label": brief["anti_target_panel"],
            "packet_role": "day-one neglected-enzyme deselection panel",
            "promote_rule": "advance only parasite-facing rows that survive host-DHODH separation",
            "reject_rule": "reject rows that collapse under host-DHODH or basic artifact checks",
        },
        "rows": [
            {"step_rank": "1", "step_label": "host_dhodh_primary", "plan": "run host DHODH counterscreen on the same shortlist", "decision_rule": "fail if host DHODH tracks parasite signal"},
            {"step_rank": "2", "step_label": "basic_viability_sanity", "plan": "carry a basic cell viability sanity note", "decision_rule": "do not oversell toxic or noisy rows"},
            {"step_rank": "3", "step_label": "orthogonal_repeat", "plan": "repeat the clean subset in an orthogonal enzyme format", "decision_rule": "only repeated clean rows survive"},
            {"step_rank": "4", "step_label": "clean_subset_only", "plan": "carry only the clean host-separated subset into later partner review", "decision_rule": "no broader claim before the clean subset is isolated"},
        ],
    }

    assay_packet = {
        "summary": payload_summary(
            "lbdhodh_assay_packet_ready",
            TARGET_ID,
            "assay_packet",
            4,
            "Use this assay packet as the executable first-pass stack for the DNDi/IPK LbDHODH rail.",
        ),
        "structured": {
            "target_id": TARGET_ID,
            "first_assay": packet["first_assay"],
            "first_packet_goal": packet["first_packet_goal"],
            "content_fill_status": content_state,
            "parallel_export_freeze": export_status,
            "repurposing_filled_slot_count": rep_filled,
            "novelty_filled_slot_count": nov_filled,
        },
        "rows": [
            {"step_rank": "1", "step_label": "primary_entry", "artifact": DEFAULT_CONDITION_CARD_MD, "execution_note": packet["first_assay"]},
            {"step_rank": "2", "step_label": "host_separation", "artifact": DEFAULT_PANEL_MD, "execution_note": packet["anti_target_panel"]},
            {"step_rank": "3", "step_label": "content_fill_guard", "artifact": DEFAULT_EXPORT_MD, "execution_note": "freeze live launch until repurposing and novelty lanes are actually filled"},
            {"step_rank": "4", "step_label": "go_no_go", "artifact": DEFAULT_GONOGO_MD, "execution_note": packet["first_packet_goal"]},
        ],
    }

    go_no_go = {
        "summary": payload_summary(
            "lbdhodh_go_no_go_card_ready",
            TARGET_ID,
            "go_no_go_card",
            4,
            "Freeze these host-separation outcomes before moving LbDHODH into live execution.",
        ),
        "structured": {
            "target_id": TARGET_ID,
            "promote_case": "host_separated_lbdhodh_signal",
            "hold_case": "promising_but_compound_fill_or_host_separation_still_incomplete",
            "reject_case": "host_like_or_artifact_heavy_signal",
            "review_rule": "do not open live execution while compound lanes remain slot-criteria-only",
        },
        "rows": [
            {"decision_case": "promote_clean_lbdhodh_favored", "meaning": "signal survives host DHODH separation and the packet content is actually filled", "action": "promote"},
            {"decision_case": "hold_pending_compound_fill", "meaning": "execution context exists but compound content is still incomplete", "action": "hold"},
            {"decision_case": "reject_host_dhodh_like", "meaning": "signal collapses under host-enzyme or artifact checks", "action": "reject"},
            {"decision_case": "explicit_hold", "meaning": "manual review requested before any tail release", "action": "hold"},
        ],
    }

    export_payload = {
        "summary": payload_summary(
            export_status,
            TARGET_ID,
            "partner_export",
            4,
            "Keep this export pending until the LbDHODH repurposing and novelty lanes move past slot-criteria-only.",
        ),
        "structured": {
            "target_id": TARGET_ID,
            "partner_track_id": TRACK_ID,
            "track_label": export_row["track_label"],
            "email_subject": email_subject,
            "proposal_title": proposal_title,
            "status": packet["status"],
            "content_fill_status": content_state,
            "repurposing_filled_slot_count": rep_filled,
            "novelty_filled_slot_count": nov_filled,
        },
        "rows": [
            {"export_item": "track_label", "value": export_row["track_label"], "role": "partner_destination"},
            {"export_item": "email_subject", "value": email_subject, "role": "first_subject_line"},
            {"export_item": "email_body", "value": email_body, "role": "first_contact_body"},
            {"export_item": "content_fill_status", "value": content_state, "role": "block_live_launch_until_filled"},
        ],
    }

    suite_rows = [
        {"artifact_kind": "condition_card", "artifact_path": DEFAULT_CONDITION_CARD_MD, "status": condition_card["summary"]["status"]},
        {"artifact_kind": "selectivity_panel", "artifact_path": DEFAULT_PANEL_MD, "status": host_panel["summary"]["status"]},
        {"artifact_kind": "assay_packet", "artifact_path": DEFAULT_ASSAY_MD, "status": assay_packet["summary"]["status"]},
        {"artifact_kind": "go_no_go_card", "artifact_path": DEFAULT_GONOGO_MD, "status": go_no_go["summary"]["status"]},
        {"artifact_kind": "partner_export", "artifact_path": DEFAULT_EXPORT_MD, "status": export_payload["summary"]["status"]},
    ]
    return {
        "summary": {
            "status": "lbdhodh_render_suite_ready",
            "target_id": TARGET_ID,
            "artifact_count": len(suite_rows),
            "partner_track_id": TRACK_ID,
            "headline": brief["headline"],
            "repurposing_filled_slot_count": rep_filled,
            "novelty_filled_slot_count": nov_filled,
            "content_ready": content_ready,
            "content_fill_status": content_state,
            "next_required_step": "Use the generated LbDHODH packet set as the second target overlay in final2, but keep live launch blocked until compound lanes are actually filled.",
        },
        "artifacts": {
            "condition_card": condition_card,
            "selectivity_panel": host_panel,
            "assay_packet": assay_packet,
            "go_no_go_card": go_no_go,
            "partner_export": export_payload,
        },
        "rows": suite_rows,
    }


def _write_suite(suite_md: str, payload: dict[str, Any]) -> None:
    write_artifact(
        suite_md,
        "LbDHODH Render Suite",
        {"summary": payload["summary"], "structured": {"target_id": payload["summary"]["target_id"], "partner_track_id": payload["summary"]["partner_track_id"]}, "rows": payload["rows"]},
    )


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build the LbDHODH target-specific wet-lab overlay packet set.")
    p.add_argument("--brief-index-json", default=DEFAULT_BRIEF_INDEX_JSON)
    p.add_argument("--neglected-rows-json", default=DEFAULT_NEGLECTED_ROWS_JSON)
    p.add_argument("--neglected-packet-json", default=DEFAULT_NEGLECTED_PACKET_JSON)
    p.add_argument("--outreach-json", default=DEFAULT_OUTREACH_JSON)
    p.add_argument("--export-bundle-json", default=DEFAULT_EXPORT_BUNDLE_JSON)
    p.add_argument("--repurposing-fill-json", default=DEFAULT_REPURPOSING_FILL_JSON)
    p.add_argument("--novelty-fill-json", default=DEFAULT_NOVELTY_FILL_JSON)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        load_json(args.brief_index_json),
        load_json(args.neglected_rows_json),
        load_json(args.neglected_packet_json),
        load_json(args.outreach_json),
        load_json(args.export_bundle_json),
        maybe_load_json(args.repurposing_fill_json),
        maybe_load_json(args.novelty_fill_json),
    )
    write_artifact(DEFAULT_CONDITION_CARD_MD, "LbDHODH Condition Card", payload["artifacts"]["condition_card"])
    write_artifact(DEFAULT_PANEL_MD, "LbDHODH Host DHODH Selectivity Panel", payload["artifacts"]["selectivity_panel"])
    write_artifact(DEFAULT_ASSAY_MD, "LbDHODH Assay Packet", payload["artifacts"]["assay_packet"])
    write_artifact(DEFAULT_GONOGO_MD, "LbDHODH Go / No-Go Card", payload["artifacts"]["go_no_go_card"])
    write_artifact(DEFAULT_EXPORT_MD, "LbDHODH DNDi / IPK Export", payload["artifacts"]["partner_export"])
    _write_suite(DEFAULT_SUITE_MD, payload)


if __name__ == "__main__":
    main()
