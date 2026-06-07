#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab_target_render_utils import load_json, payload_summary, rows_by_target, rows_by_track, write_artifact

DEFAULT_BRIEF_INDEX_JSON = "runs/wetlab_wave1_target_brief_index_current.json"
DEFAULT_NEGLECTED_PACKET_JSON = "runs/wetlab_neglected_first_contact_packets_current.json"
DEFAULT_EXPORT_BUNDLE_JSON = "runs/wetlab_partner_first_contact_export_bundle_current.json"
DEFAULT_SUITE_MD = "runs/tcruzi_pde_render_suite_current.md"
DEFAULT_CONDITION_CARD_MD = "runs/tcruzi_pde_condition_card_current.md"
DEFAULT_PANEL_MD = "runs/tcruzi_pde_human_pde_selectivity_panel_current.md"
DEFAULT_ASSAY_MD = "runs/tcruzi_pde_assay_packet_current.md"
DEFAULT_GONOGO_MD = "runs/tcruzi_pde_go_no_go_card_current.md"
DEFAULT_EXPORT_MD = "runs/tcruzi_pde_dndi_ipk_export_current.md"


def build_payload(
    brief_index: dict[str, Any],
    neglected_packet: dict[str, Any],
    export_bundle: dict[str, Any],
) -> dict[str, Any]:
    brief = rows_by_target(brief_index)["T. cruzi PDE"]
    packet = rows_by_target(neglected_packet)["T. cruzi PDE"]
    export_row = rows_by_track(export_bundle)["DNDi_IPK"]

    condition_card = {
        "summary": payload_summary(
            "tcruzi_pde_condition_card_ready",
            "T. cruzi PDE",
            "condition_card",
            4,
            "Use this condition card to keep the parasite-primary / human-counterpanel logic fixed across the first T. cruzi PDE assay pass.",
        ),
        "structured": {
            "target_id": "T. cruzi PDE",
            "partner_track": brief["partner_track"],
            "primary_assay_context": brief["first_assay"],
            "solvent_context": "aqueous recombinant enzyme assay with matched DMSO and comparator controls",
            "comparison_controls": packet["repurposing_compounds"],
            "novelty_controls": packet["novelty_compounds"],
            "primary_risk": "human-PDE-like carryover rather than parasite-selective signal",
        },
        "rows": [
            {"condition_name": "parasite_primary", "value": "recombinant parasite PDE inhibition arm", "why": "keeps the first packet cheap and target-facing"},
            {"condition_name": "human_counterpanel", "value": "same-packet human PDE mini-panel", "why": "tests selectivity on day one instead of later"},
            {"condition_name": "comparator_lane", "value": "sildenafil and tadalafil remain comparator-only stress rows", "why": "shows whether the packet can reject human-like PDE behavior"},
            {"condition_name": "orthogonal_followup", "value": "secondary biochemical or thermal confirmation after selectivity survives", "why": "keeps the first ask bounded"},
        ],
    }

    selectivity_panel = {
        "summary": payload_summary(
            "tcruzi_pde_human_pde_selectivity_panel_ready",
            "T. cruzi PDE",
            "selectivity_panel",
            4,
            "Run this human-PDE panel in the same packet so the T. cruzi PDE story starts with pathogen-vs-host separation.",
        ),
        "structured": {
            "target_id": "T. cruzi PDE",
            "panel_label": brief["anti_target_panel"],
            "panel_role": "day-one anti-target deselection",
            "promote_rule": "advance only compounds with parasite signal that do not behave like the human PDE comparator lane",
            "reject_rule": "reject compounds that align with sildenafil/tadalafil-like human-PDE behavior",
        },
        "rows": [
            {"step_rank": "1", "step_label": "parasite_signal_first", "plan": "record parasite PDE signal before any expansion discussion", "decision_rule": "requires measurable parasite activity"},
            {"step_rank": "2", "step_label": "human_panel_match", "plan": "run human PDE mini-panel on the same shortlist", "decision_rule": "fails if parasite and human profiles collapse together"},
            {"step_rank": "3", "step_label": "comparator_stress", "plan": "use sildenafil and tadalafil as explicit human-like comparators", "decision_rule": "packet is healthier if comparator rows stay comparator-like"},
            {"step_rank": "4", "step_label": "cytotoxicity_sanity", "plan": "keep a simple mammalian cytotoxicity sanity check downstream of enzyme selectivity", "decision_rule": "avoids handing noisy host-active chemistry to the partner"},
        ],
    }

    assay_packet = {
        "summary": payload_summary(
            "tcruzi_pde_assay_packet_ready",
            "T. cruzi PDE",
            "assay_packet",
            4,
            "Use this assay packet for the first DNDi/IPK-facing T. cruzi PDE pass.",
        ),
        "structured": {
            "target_id": "T. cruzi PDE",
            "first_assay": packet["first_assay"],
            "first_packet_goal": packet["first_packet_goal"],
            "repurposing_compounds": packet["repurposing_compounds"],
            "novelty_compounds": packet["novelty_compounds"],
            "go_no_go_rule": "promote only parasite-positive rows that preserve visible human-PDE separation in the same packet",
        },
        "rows": [
            {"step_rank": "1", "step_label": "parasite_pde_primary", "step": "run recombinant parasite PDE inhibition on repurposing and novelty shortlist", "success_signal": "repeatable parasite PDE signal"},
            {"step_rank": "2", "step_label": "human_pde_counterpanel", "step": "run human PDE mini-panel on same shortlist", "success_signal": "parasite-favored separation visible on day one"},
            {"step_rank": "3", "step_label": "orthogonal_confirm", "step": "use thermal or second biochemical confirmation only for parasite-favored survivors", "success_signal": "signal remains after format change"},
            {"step_rank": "4", "step_label": "simple_host_sanity", "step": "keep basic mammalian sanity check downstream of enzyme selectivity", "success_signal": "prevents host-noisy chemistry from becoming the outward story"},
        ],
    }

    go_no_go = {
        "summary": payload_summary(
            "tcruzi_pde_go_no_go_card_ready",
            "T. cruzi PDE",
            "go_no_go_card",
            4,
            "Use this go/no-go card to separate parasite-favored, hold-for-review, and reject outcomes in the first PDE packet.",
        ),
        "structured": {
            "target_id": "T. cruzi PDE",
            "promote_rule": "parasite PDE signal plus human PDE separation",
            "hold_rule": "mixed parasite and human activity that needs manual review",
            "reject_rule": "human-like comparator behavior or host-sanity failure",
            "headline": brief["headline"],
        },
        "rows": [
            {"decision_case": "promote_parasite_favored", "decision_rule": "parasite signal with same-packet human separation", "action": "promote to neglected-disease follow-up"},
            {"decision_case": "hold_mixed_profile", "decision_rule": "parasite and human PDE both move in a hard-to-separate way", "action": "hold for manual review, not for outbound celebration"},
            {"decision_case": "reject_human_like", "decision_rule": "tracks sildenafil/tadalafil-like human PDE behavior", "action": "reject from parasite-priority lane"},
            {"decision_case": "reject_host_noise", "decision_rule": "fails simple mammalian sanity after enzyme triage", "action": "reject as partner-noisy chemistry"},
        ],
    }

    export_payload = {
        "summary": payload_summary(
            "tcruzi_pde_dndi_ipk_export_ready",
            "T. cruzi PDE",
            "partner_export",
            4,
            "Send this PDE-specific export first, with Cruzain left as the optional follow-on in the DNDi/IPK conversation.",
        ),
        "structured": {
            "target_id": "T. cruzi PDE",
            "partner_track_id": export_row["track_id"],
            "partner_track_label": export_row["track_label"],
            "email_subject": "T. cruzi PDE micro-validation packet with day-one human PDE deselection",
            "proposal_title": "DNDi/IPK T. cruzi PDE micro-validation with parasite-vs-human separation",
            "proposal_summary": "A target-specific T. cruzi PDE export that keeps the first ask cheap and selective: recombinant parasite PDE, same-packet human PDE mini-panel, and bounded follow-up only for parasite-favored rows.",
            "email_opening_angle": "Lead with T. cruzi PDE as the cleaner neglected-disease enzyme proof rail and present Cruzain as the optional second packet.",
        },
        "rows": [
            {"attachment_rank": "1", "artifact": DEFAULT_CONDITION_CARD_MD, "why": "locks the parasite-primary assay context"},
            {"attachment_rank": "2", "artifact": DEFAULT_PANEL_MD, "why": "shows human-PDE anti-target logic is day-one work"},
            {"attachment_rank": "3", "artifact": DEFAULT_ASSAY_MD, "why": "gives DNDi/IPK a bounded low-friction assay packet"},
            {"attachment_rank": "4", "artifact": DEFAULT_GONOGO_MD, "why": "keeps parasite-favored versus human-like outcomes explicit"},
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
            "status": "tcruzi_pde_render_suite_ready",
            "target_id": "T. cruzi PDE",
            "artifact_count": len(suite_rows),
            "partner_track_id": export_row["track_id"],
            "next_required_step": "Use the generated T. cruzi PDE packet set as the third priority target overlay after Mpro and CA IX.",
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
        "T. cruzi PDE Render Suite",
        {"summary": payload["summary"], "structured": {"target_id": payload["summary"]["target_id"], "partner_track_id": payload["summary"]["partner_track_id"]}, "rows": payload["rows"]},
    )


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build the T. cruzi PDE target-specific wet-lab overlay packet set.")
    p.add_argument("--brief-index-json", default=DEFAULT_BRIEF_INDEX_JSON)
    p.add_argument("--neglected-packet-json", default=DEFAULT_NEGLECTED_PACKET_JSON)
    p.add_argument("--export-bundle-json", default=DEFAULT_EXPORT_BUNDLE_JSON)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        load_json(args.brief_index_json),
        load_json(args.neglected_packet_json),
        load_json(args.export_bundle_json),
    )
    write_artifact(DEFAULT_CONDITION_CARD_MD, "T. cruzi PDE Condition Card", payload["artifacts"]["condition_card"])
    write_artifact(DEFAULT_PANEL_MD, "T. cruzi PDE Human PDE Selectivity Panel", payload["artifacts"]["selectivity_panel"])
    write_artifact(DEFAULT_ASSAY_MD, "T. cruzi PDE Assay Packet", payload["artifacts"]["assay_packet"])
    write_artifact(DEFAULT_GONOGO_MD, "T. cruzi PDE Go / No-Go Card", payload["artifacts"]["go_no_go_card"])
    write_artifact(DEFAULT_EXPORT_MD, "T. cruzi PDE DNDi / IPK Export", payload["artifacts"]["partner_export"])
    _write_suite(DEFAULT_SUITE_MD, payload)


if __name__ == "__main__":
    main()
