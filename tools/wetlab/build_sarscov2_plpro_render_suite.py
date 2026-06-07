#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab_target_render_utils import load_json, payload_summary, rows_by_target, rows_by_track, write_artifact

DEFAULT_BRIEF_INDEX_JSON = "runs/wetlab_wave1_target_brief_index_current.json"
DEFAULT_ANTIVIRAL_RAIL_JSON = "runs/wetlab_antiviral_wave1_rail_current.json"
DEFAULT_ANTIVIRAL_PACKET_JSON = "runs/wetlab_antiviral_first_contact_packets_current.json"
DEFAULT_EXPORT_BUNDLE_JSON = "runs/wetlab_partner_first_contact_export_bundle_current.json"
DEFAULT_SUITE_MD = "runs/sarscov2_plpro_render_suite_current.md"
DEFAULT_CONDITION_CARD_MD = "runs/sarscov2_plpro_condition_card_current.md"
DEFAULT_PANEL_MD = "runs/sarscov2_plpro_host_dub_panel_current.md"
DEFAULT_ASSAY_MD = "runs/sarscov2_plpro_assay_packet_current.md"
DEFAULT_GONOGO_MD = "runs/sarscov2_plpro_go_no_go_card_current.md"
DEFAULT_EXPORT_MD = "runs/sarscov2_plpro_readdi_export_current.md"


def build_payload(
    brief_index: dict[str, Any],
    antiviral_rail: dict[str, Any],
    antiviral_packet: dict[str, Any],
    export_bundle: dict[str, Any],
) -> dict[str, Any]:
    brief = rows_by_target(brief_index)["SARS-CoV-2 PLpro"]
    rail = rows_by_target(antiviral_rail)["SARS-CoV-2 PLpro"]
    packet = rows_by_target(antiviral_packet)["SARS-CoV-2 PLpro"]
    export_row = rows_by_track(export_bundle)["READDI_Korea"]

    condition_card = {
        "summary": payload_summary(
            "sarscov2_plpro_condition_card_ready",
            "SARS-CoV-2 PLpro",
            "condition_card",
            4,
            "Use this card as the fixed PLpro assay context before interpreting any shallow-pocket hit list.",
        ),
        "structured": {
            "target_id": "SARS-CoV-2 PLpro",
            "partner_track": brief["partner_track"],
            "primary_assay_context": brief["first_assay"],
            "groove_focus": "BL2 or adjacent shallow-groove engagement with explicit DUB deselection",
            "comparison_controls": packet["repurposing_compounds"],
            "novelty_controls": packet["novelty_compounds"],
            "primary_risk": "host DUB-like crossover and shallow-pocket assay artifact",
        },
        "rows": [
            {"condition_name": "primary_plpro_arm", "value": "fluorogenic PLpro biochemical assay", "why": "keeps the first pass cheap and executable", "source_anchor": rail["primary_source_1_label"]},
            {"condition_name": "human_dub_counterpanel", "value": rail["host_off_target_counterscreens"], "why": "host DUB cleanup must happen on day one", "source_anchor": rail["primary_source_2_label"]},
            {"condition_name": "cell_followup_gate", "value": "in-cell PLpro only after biochemical and DUB cleanup", "why": "prevents expanding shallow-pocket noise", "source_anchor": rail["open_science_source_label"]},
            {"condition_name": "orthogonal_confirmation", "value": "thermal or repeat biochemical confirmation", "why": "keeps the packet decision-grade before outward claims", "source_anchor": rail["primary_source_2_label"]},
        ],
    }

    host_panel = {
        "summary": payload_summary(
            "sarscov2_plpro_host_dub_panel_ready",
            "SARS-CoV-2 PLpro",
            "host_dub_panel",
            4,
            "Run this panel in the same packet so host-DUB or shallow-pocket artifact rows fail immediately.",
        ),
        "structured": {
            "target_id": "SARS-CoV-2 PLpro",
            "panel_label": brief["anti_target_panel"],
            "packet_role": "day-one host-liability panel",
            "promote_rule": "advance only PLpro rows that survive human-DUB and artifact cleanup",
            "reject_rule": "reject rows that look host-like or shallow-pocket-artifactual",
        },
        "rows": [
            {"step_rank": "1", "step_label": "human_dub_primary", "plan": "run the human DUB mini-panel on the same shortlist", "decision_rule": "fail if host DUB tracks with PLpro signal"},
            {"step_rank": "2", "step_label": "legacy_usp_check", "plan": "keep a legacy USP-like biochemical check in the panel", "decision_rule": "fail if signal looks like generic DUB behavior"},
            {"step_rank": "3", "step_label": "reactivity_or_host_protease_sanity", "plan": "use generic cysteine-protease or reactivity sanity filters", "decision_rule": "fail if the shortlist behaves like broad cysteine noise"},
            {"step_rank": "4", "step_label": "clean_subset_only", "plan": "carry only DUB-clean survivors into cell follow-up", "decision_rule": "no outward antiviral claim before the clean subset is isolated"},
        ],
    }

    assay_packet = {
        "summary": payload_summary(
            "sarscov2_plpro_assay_packet_ready",
            "SARS-CoV-2 PLpro",
            "assay_packet",
            4,
            "Use this assay packet as the executable first-pass stack for the READDI PLpro rail.",
        ),
        "structured": {
            "target_id": "SARS-CoV-2 PLpro",
            "first_assay": packet["first_assay"],
            "first_packet_goal": packet["first_packet_goal"],
            "repurposing_compounds": packet["repurposing_compounds"],
            "novelty_compounds": packet["novelty_compounds"],
            "go_no_go_rule": "promote only reproducible PLpro signal that survives the human-DUB-first counterscreen",
        },
        "rows": [
            {"step_rank": "1", "step_label": "primary_plpro", "step": "run fluorogenic PLpro assay on top-3 repurposing and top-3 novelty rows", "success_signal": "repeatable PLpro inhibition"},
            {"step_rank": "2", "step_label": "human_dub_cleanup", "step": "run human DUB panel on the same shortlist", "success_signal": "signal remains PLpro-favored rather than DUB-like"},
            {"step_rank": "3", "step_label": "cell_or_orthogonal_confirmation", "step": "confirm clean survivors by in-cell PLpro or orthogonal biochemical format", "success_signal": "signal survives beyond the shallow-pocket biochemical entry assay"},
            {"step_rank": "4", "step_label": "bounded_followup", "step": "keep any broader antiviral claim behind the clean subset only", "success_signal": "partner ask stays narrow and interpretable"},
        ],
    }

    go_no_go = {
        "summary": payload_summary(
            "sarscov2_plpro_go_no_go_card_ready",
            "SARS-CoV-2 PLpro",
            "go_no_go_card",
            4,
            "Use this card to separate clean PLpro rows from host-DUB-like or shallow-pocket artifact noise.",
        ),
        "structured": {
            "target_id": "SARS-CoV-2 PLpro",
            "promote_rule": "repeatable PLpro signal plus clean human-DUB panel outcome",
            "hold_rule": "partial PLpro signal that still needs cell or orthogonal confirmation",
            "reject_rule": "host-like DUB behavior or shallow-pocket artifact",
            "headline": brief["headline"],
        },
        "rows": [
            {"decision_case": "promote_clean_plpro_favored", "decision_rule": "repeatable PLpro signal survives human-DUB cleanup", "action": "promote to antiviral follow-up"},
            {"decision_case": "hold_partial_cleanliness", "decision_rule": "PLpro signal exists but orthogonal or in-cell confirmation is incomplete", "action": "hold for bounded follow-up"},
            {"decision_case": "reject_host_dub_like", "decision_rule": "human DUB panel tracks with the apparent PLpro signal", "action": "reject as host-liability carryover"},
            {"decision_case": "reject_shallow_artifact", "decision_rule": "reactivity or shallow-pocket artifact explains the signal", "action": "reject as non-decision-grade antiviral chemistry"},
        ],
    }

    export_payload = {
        "summary": payload_summary(
            "sarscov2_plpro_readdi_export_ready",
            "SARS-CoV-2 PLpro",
            "partner_export",
            4,
            "Send this target-specific PLpro export after attaching the condition card, host-DUB panel, assay packet, and go/no-go card.",
        ),
        "structured": {
            "target_id": "SARS-CoV-2 PLpro",
            "partner_track_id": export_row["track_id"],
            "partner_track_label": export_row["track_label"],
            "email_subject": "PLpro micro-validation packet with day-one host-DUB cleanup",
            "proposal_title": "READDI PLpro micro-validation with host-DUB-first deselection",
            "proposal_summary": "A target-specific PLpro export that keeps the first ask narrow: cheap biochemical signal, immediate DUB cleanup, and bounded follow-up only for clean shallow-groove survivors.",
            "email_opening_angle": "Lead with PLpro as the host-liability-sensitive companion rail to Mpro, not as an open-ended shallow-pocket fishing exercise.",
        },
        "rows": [
            {"attachment_rank": "1", "artifact": DEFAULT_CONDITION_CARD_MD, "why": "locks the PLpro assay context"},
            {"attachment_rank": "2", "artifact": DEFAULT_PANEL_MD, "why": "shows human-DUB cleanup is day-one work"},
            {"attachment_rank": "3", "artifact": DEFAULT_ASSAY_MD, "why": "gives READDI a bounded executable stack"},
            {"attachment_rank": "4", "artifact": DEFAULT_GONOGO_MD, "why": "keeps clean versus noisy outcomes explicit"},
        ],
    }

    suite_rows = [
        {"artifact_kind": "condition_card", "artifact_path": DEFAULT_CONDITION_CARD_MD, "status": condition_card["summary"]["status"]},
        {"artifact_kind": "host_dub_panel", "artifact_path": DEFAULT_PANEL_MD, "status": host_panel["summary"]["status"]},
        {"artifact_kind": "assay_packet", "artifact_path": DEFAULT_ASSAY_MD, "status": assay_packet["summary"]["status"]},
        {"artifact_kind": "go_no_go_card", "artifact_path": DEFAULT_GONOGO_MD, "status": go_no_go["summary"]["status"]},
        {"artifact_kind": "partner_export", "artifact_path": DEFAULT_EXPORT_MD, "status": export_payload["summary"]["status"]},
    ]
    return {
        "summary": {
            "status": "sarscov2_plpro_render_suite_ready",
            "target_id": "SARS-CoV-2 PLpro",
            "artifact_count": len(suite_rows),
            "partner_track_id": export_row["track_id"],
            "next_required_step": "Use the generated PLpro packet set as the second target overlay in the next3 serialized chain.",
        },
        "artifacts": {
            "condition_card": condition_card,
            "host_dub_panel": host_panel,
            "assay_packet": assay_packet,
            "go_no_go_card": go_no_go,
            "partner_export": export_payload,
        },
        "rows": suite_rows,
    }


def _write_suite(suite_md: str, payload: dict[str, Any]) -> None:
    write_artifact(
        suite_md,
        "SARS-CoV-2 PLpro Render Suite",
        {"summary": payload["summary"], "structured": {"target_id": payload["summary"]["target_id"], "partner_track_id": payload["summary"]["partner_track_id"]}, "rows": payload["rows"]},
    )


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build the SARS-CoV-2 PLpro target-specific wet-lab overlay packet set.")
    p.add_argument("--brief-index-json", default=DEFAULT_BRIEF_INDEX_JSON)
    p.add_argument("--antiviral-rail-json", default=DEFAULT_ANTIVIRAL_RAIL_JSON)
    p.add_argument("--antiviral-packet-json", default=DEFAULT_ANTIVIRAL_PACKET_JSON)
    p.add_argument("--export-bundle-json", default=DEFAULT_EXPORT_BUNDLE_JSON)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        load_json(args.brief_index_json),
        load_json(args.antiviral_rail_json),
        load_json(args.antiviral_packet_json),
        load_json(args.export_bundle_json),
    )
    write_artifact(DEFAULT_CONDITION_CARD_MD, "SARS-CoV-2 PLpro Condition Card", payload["artifacts"]["condition_card"])
    write_artifact(DEFAULT_PANEL_MD, "SARS-CoV-2 PLpro Host DUB Panel", payload["artifacts"]["host_dub_panel"])
    write_artifact(DEFAULT_ASSAY_MD, "SARS-CoV-2 PLpro Assay Packet", payload["artifacts"]["assay_packet"])
    write_artifact(DEFAULT_GONOGO_MD, "SARS-CoV-2 PLpro Go / No-Go Card", payload["artifacts"]["go_no_go_card"])
    write_artifact(DEFAULT_EXPORT_MD, "SARS-CoV-2 PLpro READDI Export", payload["artifacts"]["partner_export"])
    _write_suite(DEFAULT_SUITE_MD, payload)


if __name__ == "__main__":
    main()
