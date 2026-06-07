#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab_target_render_utils import load_json, payload_summary, resolve, rows_by_target, rows_by_track, write_artifact

DEFAULT_BRIEF_INDEX_JSON = "runs/wetlab_wave1_target_brief_index_current.json"
DEFAULT_ANTIVIRAL_RAIL_JSON = "runs/wetlab_antiviral_wave1_rail_current.json"
DEFAULT_ANTIVIRAL_FIRST_CONTACT_JSON = "runs/wetlab_antiviral_first_contact_packets_current.json"
DEFAULT_EXPORT_BUNDLE_JSON = "runs/wetlab_partner_first_contact_export_bundle_current.json"
DEFAULT_VENDOR_COST_JSON = "runs/wetlab_mpro_vendor_cost_check_current.json"
DEFAULT_SUITE_MD = "runs/sarscov2_mpro_render_suite_current.md"
DEFAULT_CONDITION_CARD_MD = "runs/sarscov2_mpro_condition_card_current.md"
DEFAULT_PANEL_MD = "runs/sarscov2_mpro_host_protease_panel_current.md"
DEFAULT_ASSAY_MD = "runs/sarscov2_mpro_assay_packet_current.md"
DEFAULT_GONOGO_MD = "runs/sarscov2_mpro_go_no_go_card_current.md"
DEFAULT_EXPORT_MD = "runs/sarscov2_mpro_readdi_export_current.md"


def _vendor_summary(vendor_payload: dict[str, Any]) -> str:
    parts = []
    for row in vendor_payload.get("rows", []) or []:
        parts.append(f"{row['compound_name']} {row['listed_price']} {row['listed_currency']} / {row['listed_pack_size']}")
    return "; ".join(parts)


def build_payload(
    brief_index: dict[str, Any],
    antiviral_rail: dict[str, Any],
    antiviral_first_contact: dict[str, Any],
    export_bundle: dict[str, Any],
    vendor_cost: dict[str, Any],
) -> dict[str, Any]:
    brief = rows_by_target(brief_index)["SARS-CoV-2 Mpro"]
    rail = rows_by_target(antiviral_rail)["SARS-CoV-2 Mpro"]
    first_contact = rows_by_target(antiviral_first_contact)["SARS-CoV-2 Mpro"]
    export_row = rows_by_track(export_bundle)["READDI_Korea"]

    condition_card = {
        "summary": payload_summary(
            "sarscov2_mpro_condition_card_ready",
            "SARS-CoV-2 Mpro",
            "condition_card",
            5,
            "Use this card as the fixed wet-lab context when the Mpro repurposing and novelty shortlist is handed to a READDI-style lab.",
        ),
        "structured": {
            "target_id": "SARS-CoV-2 Mpro",
            "partner_track": brief["partner_track"],
            "assay_mode": brief["first_assay"],
            "primary_buffer_context": "standard soluble Mpro biochemical buffer with matched DMSO and reducing-agent sanity checks",
            "temperature_context": "room-temperature biochemical pass first, then orthogonal confirmation under the same solvent discipline",
            "control_stack": first_contact["repurposing_compounds"],
            "vendor_cost_summary": _vendor_summary(vendor_cost),
            "source_anchor": rail["primary_source_2_label"],
            "source_url": rail["primary_source_2_url"],
        },
        "rows": [
            {"condition_name": "primary_assay_format", "value": "cheap fluorogenic or fluorescence-polarization Mpro assay", "why": "lowest-friction proof rail for fast antiviral validation", "source_anchor": rail["primary_source_2_label"]},
            {"condition_name": "protein_state", "value": "recombinant dimer-competent Mpro preparation", "why": "keeps the first pass aligned with the established biochemical rail", "source_anchor": rail["primary_source_1_label"]},
            {"condition_name": "solvent_window", "value": "matched DMSO across controls and shortlist", "why": "prevents crowded-field false positives from looking like dynamics signal", "source_anchor": rail["primary_source_1_label"]},
            {"condition_name": "reducing_context", "value": "explicit reducing-agent sanity check before hit interpretation", "why": "filters generic cysteine-reactive behavior early", "source_anchor": rail["primary_source_1_label"]},
            {"condition_name": "orthogonal_confirmation_gate", "value": "thermal or second biochemical confirmation only after host-panel survival", "why": "keeps the packet cheap first and stricter second", "source_anchor": rail["open_science_source_label"]},
        ],
    }

    host_panel = {
        "summary": payload_summary(
            "sarscov2_mpro_host_protease_panel_ready",
            "SARS-CoV-2 Mpro",
            "host_protease_panel",
            4,
            "Run this panel alongside the first Mpro pass so crowded-field protease noise is rejected before any follow-up claim is made.",
        ),
        "structured": {
            "target_id": "SARS-CoV-2 Mpro",
            "panel_label": rail["host_off_target_counterscreens"],
            "primary_host_risk": "host cysteine-protease crossover and generic reactivity",
            "packet_role": "first-pass deselection panel",
            "promote_rule": "advance only compounds that hold Mpro signal while staying clean on the host-protease sanity panel",
        },
        "rows": [
            {"panel_step": "1", "label": "cathepsin_L_primary", "purpose": "primary host cysteine-protease sanity check", "decision_rule": "fail if host protease signal tracks with Mpro signal"},
            {"panel_step": "2", "label": "cathepsin_B_secondary", "purpose": "second host-protease liability check", "decision_rule": "use to distinguish specific Mpro behavior from generic cysteine-protease carryover"},
            {"panel_step": "3", "label": "aggregation_or_reactivity_filter", "purpose": "remove dual-liability false positives", "decision_rule": "reject compounds that only survive via sticky or reactive behavior"},
            {"panel_step": "4", "label": "report_clean_subset_only", "purpose": "keep the outbound packet decision-grade", "decision_rule": "only clean survivors move to orthogonal confirmation"},
        ],
    }

    assay_packet = {
        "summary": payload_summary(
            "sarscov2_mpro_assay_packet_ready",
            "SARS-CoV-2 Mpro",
            "assay_packet",
            4,
            "Use this packet as the executable first-pass assay stack for the Mpro READDI rail.",
        ),
        "structured": {
            "target_id": "SARS-CoV-2 Mpro",
            "first_assay": first_contact["first_assay"],
            "first_packet_goal": first_contact["first_packet_goal"],
            "go_no_go_rule": "at least one proceed-now repurposing row or one novelty row must show reproducible Mpro signal and survive the host-protease panel before the packet is considered partner-positive",
            "repurposing_compounds": first_contact["repurposing_compounds"],
            "novelty_compounds": first_contact["novelty_compounds"],
        },
        "rows": [
            {"step_rank": "1", "step_label": "primary_biochemical", "step": "run cheap fluorogenic Mpro assay on top-3 repurposing and top-3 novelty compounds", "success_signal": "repeatable biochemical inhibition above benchmark noise"},
            {"step_rank": "2", "step_label": "host_panel", "step": "run cathepsin-led host protease sanity panel on the same shortlist", "success_signal": "signal stays Mpro-favored rather than host-like"},
            {"step_rank": "3", "step_label": "orthogonal_confirmation", "step": "confirm clean survivors by thermal or orthogonal biochemical method", "success_signal": "same direction of effect without assay-format collapse"},
            {"step_rank": "4", "step_label": "optional_reporter_followup", "step": "open cell-based reporter only for clean biochemical survivors", "success_signal": "keeps the first partner ask bounded and low-friction"},
        ],
    }

    go_no_go = {
        "summary": payload_summary(
            "sarscov2_mpro_go_no_go_card_ready",
            "SARS-CoV-2 Mpro",
            "go_no_go_card",
            4,
            "Use this card to separate clean Mpro-favored rows from host-like or reactive noise before any outward antiviral claim is made.",
        ),
        "structured": {
            "target_id": "SARS-CoV-2 Mpro",
            "promote_rule": "reproducible Mpro signal plus a clean host-protease panel outcome",
            "hold_rule": "partially clean biochemical signal that needs orthogonal confirmation before partner-facing interpretation",
            "reject_rule": "host-like, reactive, or aggregation-led behavior",
            "headline": brief["headline"],
        },
        "rows": [
            {"decision_case": "promote_clean_mpro_favored", "decision_rule": "repeatable Mpro signal survives host-protease sanity panel and orthogonal confirmation", "action": "promote to antiviral follow-up"},
            {"decision_case": "hold_partial_cleanliness", "decision_rule": "Mpro signal is present but orthogonal or host-panel evidence is still incomplete", "action": "hold for bounded follow-up before export claims widen"},
            {"decision_case": "reject_host_like", "decision_rule": "host protease panel tracks with the apparent Mpro signal", "action": "reject as host-liability carryover"},
            {"decision_case": "reject_reactive_or_sticky", "decision_rule": "aggregation or reactivity filter explains the signal", "action": "reject as non-decision-grade antiviral chemistry"},
        ],
    }

    export_payload = {
        "summary": payload_summary(
            "sarscov2_mpro_readdi_export_ready",
            "SARS-CoV-2 Mpro",
            "partner_export",
            5,
            "Send this target-specific export after attaching the condition card, host panel, assay packet, and current procurement sheet.",
        ),
        "structured": {
            "target_id": "SARS-CoV-2 Mpro",
            "partner_track_id": export_row["track_id"],
            "partner_track_label": export_row["track_label"],
            "email_subject": "Mpro micro-validation packet with host-protease deselection built in",
            "proposal_title": "READDI Mpro micro-validation packet with fast host-liability cleanup",
            "proposal_summary": "A target-specific Mpro export that keeps the first ask narrow: cheap biochemical signal, immediate host-protease cleanup, and procurement-ready controls.",
            "email_opening_angle": "Lead with Mpro as the lowest-friction proof rail and position PLpro as the optional follow-on once the first packet stays clean.",
        },
        "rows": [
            {"attachment_rank": "1", "artifact": DEFAULT_CONDITION_CARD_MD, "why": "locks the wet-lab context before interpretation"},
            {"attachment_rank": "2", "artifact": DEFAULT_PANEL_MD, "why": "shows host-liability cleanup is day-one work"},
            {"attachment_rank": "3", "artifact": DEFAULT_ASSAY_MD, "why": "gives the lab a bounded executable stack"},
            {"attachment_rank": "4", "artifact": DEFAULT_GONOGO_MD, "why": "keeps clean versus noisy outcomes explicit before outward reporting"},
            {"attachment_rank": "5", "artifact": "runs/wetlab_mpro_vendor_cost_check_current.md", "why": "keeps the repurposing controls procurement-ready"},
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
            "status": "sarscov2_mpro_render_suite_ready",
            "target_id": "SARS-CoV-2 Mpro",
            "artifact_count": len(suite_rows),
            "partner_track_id": export_row["track_id"],
            "next_required_step": "Use the generated Mpro packet set as the first executable wet-lab target overlay before moving to CA IX.",
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
        "SARS-CoV-2 Mpro Render Suite",
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
    p = argparse.ArgumentParser(description="Build the SARS-CoV-2 Mpro target-specific wet-lab overlay packet set.")
    p.add_argument("--brief-index-json", default=DEFAULT_BRIEF_INDEX_JSON)
    p.add_argument("--antiviral-rail-json", default=DEFAULT_ANTIVIRAL_RAIL_JSON)
    p.add_argument("--antiviral-first-contact-json", default=DEFAULT_ANTIVIRAL_FIRST_CONTACT_JSON)
    p.add_argument("--export-bundle-json", default=DEFAULT_EXPORT_BUNDLE_JSON)
    p.add_argument("--vendor-cost-json", default=DEFAULT_VENDOR_COST_JSON)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        load_json(args.brief_index_json),
        load_json(args.antiviral_rail_json),
        load_json(args.antiviral_first_contact_json),
        load_json(args.export_bundle_json),
        load_json(args.vendor_cost_json),
    )
    write_artifact(DEFAULT_CONDITION_CARD_MD, "SARS-CoV-2 Mpro Condition Card", payload["artifacts"]["condition_card"])
    write_artifact(DEFAULT_PANEL_MD, "SARS-CoV-2 Mpro Host Protease Panel", payload["artifacts"]["host_protease_panel"])
    write_artifact(DEFAULT_ASSAY_MD, "SARS-CoV-2 Mpro Assay Packet", payload["artifacts"]["assay_packet"])
    write_artifact(DEFAULT_GONOGO_MD, "SARS-CoV-2 Mpro Go / No-Go Card", payload["artifacts"]["go_no_go_card"])
    write_artifact(DEFAULT_EXPORT_MD, "SARS-CoV-2 Mpro READDI Export", payload["artifacts"]["partner_export"])
    _write_suite(DEFAULT_SUITE_MD, payload)


if __name__ == "__main__":
    main()
